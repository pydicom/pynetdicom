"""
Implements the DICOM Upper Layer service provider.
"""

import logging
import queue
import struct
from threading import Thread
import time
from typing import TYPE_CHECKING, cast, Type

from pynetdicom import evt
from pynetdicom.fsm import StateMachine
from pynetdicom.pdu import (
    A_ASSOCIATE_RQ,
    A_ASSOCIATE_AC,
    A_ASSOCIATE_RJ,
    P_DATA_TF,
    A_RELEASE_RQ,
    A_RELEASE_RP,
    A_ABORT_RQ,
    _PDUType,
)
from pynetdicom.pdu_primitives import (
    A_ASSOCIATE,
    A_RELEASE,
    A_ABORT,
    A_P_ABORT,
    P_DATA,
    _PDUPrimitiveType,
)
from pynetdicom.timer import Timer
from pynetdicom.transport import T_CONNECT
from pynetdicom.utils import make_target

if TYPE_CHECKING:  # pragma: no cover
    from pynetdicom.association import Association
    from pynetdicom.transport import AssociationSocket

    _QueueType = queue.Queue[_PDUPrimitiveType | T_CONNECT]
    _UserQueuePrimitives = A_ASSOCIATE | A_RELEASE | A_ABORT | A_P_ABORT


LOGGER = logging.getLogger(__name__)


class DULServiceProvider(Thread):
    """The DICOM Upper Layer Service Provider.

    Attributes
    ----------
    artim_timer : timer.Timer
        The :dcm:`ARTIM<part08/chapter_9.html#sect_9.1.5>` timer.
    socket : transport.AssociationSocket
        A wrapped `socket
        <https://docs.python.org/3/library/socket.html#socket-objects>`_
        object used to communicate with the peer.
    to_provider_queue : queue.Queue
        Queue of primitives received from the peer to be processed by the service user.
    to_user_queue : queue.Queue
        Queue of processed PDUs for the DUL service user.
    event_queue : queue.Queue
        List of queued events to be processed by the state machine.
    state_machine : fsm.StateMachine
        The DICOM Upper Layer's State Machine.
    """

    def __init__(self, assoc: "Association") -> None:
        """Create a new DUL service provider for `assoc`.

        Parameters
        ----------
        assoc : association.Association
            The DUL's parent :class:`~pynetdicom.association.Association`
            instance.
        """
        # The association thread
        self._assoc = assoc
        self.socket: "AssociationSocket | None" = None

        # Tracks the events the state machine needs to process
        self.event_queue: "queue.Queue[str]" = queue.Queue()
        # These queues provide communication between the DUL service
        #   user and the DUL service provider.
        # An event occurs when the DUL service user adds to
        #   the to_provider_queue
        # The queue contains A-ASSOCIATE, A-RELEASE, A-ABORT, A-P-ABORT, P-DATA and
        #   T-CONNECT primitives from the local user that are to be sent to the peer
        self.to_provider_queue: "_QueueType" = queue.Queue()
        # A primitive is sent to the service user when the DUL service provider
        # adds to the to_user_queue.
        self.to_user_queue: "queue.Queue[_UserQueuePrimitives]" = queue.Queue()

        # A queue storing PDUs received from the peer
        self._recv_pdu: "queue.Queue[_PDUType]" = queue.Queue()

        # Set the (network) idle and ARTIM timers
        # Timeouts gets set after DUL init so these are temporary
        self._idle_timer = Timer(60)
        self.artim_timer = Timer(30)

        # State machine - PS3.8 Section 9.2
        self.state_machine = StateMachine(self)

        # Controls the minimum delay between loops in run() in seconds
        # TODO: try and make this event based rather than running loops
        self._run_loop_delay = 0.001

        Thread.__init__(self, target=make_target(self.run_reactor))
        self.daemon = False
        self._kill_thread = False

    @property
    def assoc(self) -> "Association":
        """Return the parent :class:`~pynetdicom.association.Association`."""
        return self._assoc

    def _decode_pdu(self, bytestream: bytearray) -> tuple[_PDUType, str]:
        """Decode a received PDU.

        Parameters
        ----------
        bytestream : bytearray
            The received PDU.

        Returns
        -------
        pdu.PDU subclass, str
            The PDU subclass corresponding to the PDU and the event string
            corresponding to receiving that PDU type.
        """
        # Trigger before data is decoded in case of exception in decoding
        b = bytes(bytestream)
        evt.trigger(self.assoc, evt.EVT_DATA_RECV, {"data": b})

        pdu_cls, event = _PDU_TYPES[b[0:1]]
        pdu = pdu_cls()
        pdu.decode(b)

        evt.trigger(self.assoc, evt.EVT_PDU_RECV, {"pdu": pdu})

        return pdu, event

    def idle_timer_expired(self) -> bool:
        """Return ``True`` if the network idle timer has expired."""
        return self._idle_timer.expired

    def _is_transport_event(self) -> bool:
        """Check to see if the socket has incoming data

        Returns
        -------
        bool
            True if an event has been added to the event queue, False
            otherwise. Returning True restarts the idle timer and skips the
            incoming primitive check.
        """
        # Sta13: waiting for the transport connection to close
        # however it may still receive data that needs to be acted on
        self.socket = cast("AssociationSocket", self.socket)
        if self.state_machine.current_state == "Sta13":
            # Check to see if there's more data to be read
            #   Might be any incoming PDU or valid/invalid data
            if self.socket and self.socket.ready:
                # Data still available, grab it
                self._read_pdu_data()
                return True

            # Once we have no more incoming data close the socket and
            #   add the corresponding event to the queue
            self.socket.close()

            return True

        # By this point the connection should be established
        #   If there's incoming data on the connection then check the PDU
        #   type
        # Fix for #28 - caused by peer disconnecting before run loop is
        #   stopped by assoc.release()
        if self.socket and self.socket.ready:
            self._read_pdu_data()
            return True

        return False

    def kill_dul(self) -> None:
        """Kill the DUL reactor and stop the thread"""
        self._kill_thread = True

    @property
    def network_timeout(self) -> float | None:
        """Return the network timeout (in seconds)."""
        return self.assoc.network_timeout

    def peek_next_pdu(self) -> "_UserQueuePrimitives | None":
        """Check the next PDU to be processed."""
        try:
            return cast("_UserQueuePrimitives", self.to_user_queue.queue[0])
        except (queue.Empty, IndexError):
            return None

    def _process_recv_primitive(self) -> bool:
        """Check to see if the local user has sent any primitives to the DUL"""
        # Check the queue and see if there are any primitives
        # If so then put the corresponding event on the event queue
        try:
            primitive = self.to_provider_queue.queue[0]
        except (queue.Empty, IndexError):
            return False

        if isinstance(primitive, T_CONNECT):
            # Evt2 or Evt17, depending on whether successful or not
            event = primitive.result
        elif isinstance(primitive, A_ASSOCIATE):
            if primitive.result is None:
                # A-ASSOCIATE Request
                event = "Evt1"
            elif primitive.result == 0x00:
                # A-ASSOCIATE Response (accept)
                event = "Evt7"
            else:
                # A-ASSOCIATE Response (reject)
                event = "Evt8"
        elif isinstance(primitive, A_RELEASE):
            if primitive.result is None:
                # A-Release Request
                event = "Evt11"
            else:
                # A-Release Response
                # result is 'affirmative'
                event = "Evt14"
        elif isinstance(primitive, (A_ABORT, A_P_ABORT)):
            event = "Evt15"
        elif isinstance(primitive, P_DATA):
            event = "Evt9"
        else:
            raise ValueError(
                f"Unknown primitive type '{primitive.__class__.__name__}' received"
            )

        self.event_queue.put(event)

        return True

    def _read_pdu_data(self) -> None:
        """Read PDU data sent by the peer from the socket.

        Receives the PDU, attempts to decode it, places the corresponding
        event in the event queue and converts it a primitive (if possible).

        If the decoding and conversion is successful then `pdu` and `primitive`
        are set to corresponding class instances.

        **Events Emitted**

        - Evt6: A-ASSOCIATE-RQ PDU received
        - Evt3: A-ASSOCIATE-AC PDU received
        - Evt4: A-ASSOCIATE-RJ PDU received
        - Evt10: P-DATA-TF PDU received
        - Evt12: A-RELEASE-RQ PDU received
        - Evt13: A-RELEASE-RP PDU received
        - Evt16: A-ABORT PDU received
        - Evt17: Transport connection closed
        - Evt19: Invalid or unrecognised PDU
        """
        bytestream = bytearray()
        self.socket = cast("AssociationSocket", self.socket)

        # Try and read the PDU type and length from the socket
        try:
            bytestream.extend(self.socket.recv(6))
        except (OSError, TimeoutError) as exc:
            # READ_PDU_EXC_A
            LOGGER.error("Connection closed before the entire PDU was received")
            LOGGER.exception(exc)
            # Evt17: Transport connection closed
            self.event_queue.put("Evt17")
            return

        try:
            # Byte 1 is always the PDU type
            # Byte 2 is always reserved
            # Bytes 3-6 are always the PDU length
            pdu_type, _, pdu_length = struct.unpack(">BBL", bytestream)
        except struct.error:
            # READ_PDU_EXC_B
            # LOGGER.error("Insufficient data received to decode the PDU")
            # Evt17: Transport connection closed
            self.event_queue.put("Evt17")
            return

        # If the `pdu_type` is unrecognised
        if pdu_type not in (0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07):
            # READ_PDU_EXC_C
            LOGGER.error(f"Unknown PDU type received '0x{pdu_type:02X}'")
            # Evt19: Unrecognised or invalid PDU received
            self.event_queue.put("Evt19")
            return

        # Try and read the rest of the PDU
        try:
            bytestream += self.socket.recv(pdu_length)
        except (OSError, TimeoutError) as exc:
            # READ_PDU_EXC_D
            LOGGER.error("Connection closed before the entire PDU was received")
            LOGGER.exception(exc)
            # Evt17: Transport connection closed
            self.event_queue.put("Evt17")
            return

        # Check that the PDU data was completely read
        if len(bytestream) != 6 + pdu_length:
            # READ_PDU_EXC_E
            # Evt17: Transport connection closed
            LOGGER.error(
                f"The received PDU is shorter than expected ({len(bytestream)} of "
                f"{6 + pdu_length} bytes received)"
            )
            self.event_queue.put("Evt17")
            return

        try:
            # Decode the PDU data, get corresponding FSM event
            pdu, event = self._decode_pdu(bytestream)
            self.event_queue.put(event)
        except Exception as exc:
            # READ_PDU_EXC_F
            LOGGER.error("Unable to decode the received PDU data")
            LOGGER.exception(exc)
            # Evt19: Unrecognised or invalid PDU received
            self.event_queue.put("Evt19")
            return

        self._recv_pdu.put(pdu)

    def receive_pdu(
        self, wait: bool = False, timeout: float | None = None
    ) -> "_UserQueuePrimitives | None":
        """Return an item from the queue if one is available.

        Get the next service primitive to be processed out of the queue of items sent
        from the DUL service provider to the service user

        Parameters
        ----------
        wait : bool, optional
            If `wait` is ``True`` and `timeout` is ``None``, blocks until an
            item is available. If `timeout` is a positive number, blocks at
            most `timeout` seconds. Otherwise returns an item if one is
            immediately available.
        timeout : int or None
            See the definition of `wait`

        Returns
        -------
        A_ASSOCIATE | A_RELEASE | A_ABORT | A_P_ABORT
            The next primitive in the :attr:`~DULServiceProvider.to_user_queue`, or
            ``None`` if the queue is empty.
        """
        try:
            # If block is True and timeout is None then block until an item
            #   is available.
            # If timeout is a positive number, blocks timeout seconds and
            #   raises queue.Empty if no item was available in that time.
            # If block is False, return an item if one is immediately
            #   available, otherwise raise queue.Empty
            primitive = self.to_user_queue.get(block=wait, timeout=timeout)

            # Event handler - ACSE received primitive from DUL service
            if isinstance(primitive, (A_ASSOCIATE, A_RELEASE, A_ABORT, A_P_ABORT)):
                evt.trigger(self.assoc, evt.EVT_ACSE_RECV, {"primitive": primitive})

            return primitive
        except queue.Empty:
            return None

    def run_reactor(self) -> None:
        """Run the DUL reactor.

        The main :class:`threading.Thread` run loop. Runs constantly, checking
        the connection for incoming data. When incoming data is received it
        categorises it and add its to the
        :attr:`~DULServiceProvider.to_user_queue`.
        """
        # Main DUL loop
        self._idle_timer.start()
        self.socket = cast("AssociationSocket", self.socket)
        sleep = False

        while True:
            # Let the assoc reactor off the leash
            if not self.assoc._dul_ready.is_set():
                self.assoc._dul_ready.set()
                # When single-stepping the reactor, sleep between events so that
                # test code has time to run.
                sleep = True

            if sleep:
                # If there were no events to process on the previous loop,
                #   sleep before checking again, otherwise check immediately
                # Setting `_run_loop_delay` higher will use less CPU when idle, but
                #   will also increase the latency to respond to new requests
                time.sleep(self._run_loop_delay)

            if self._kill_thread:
                break

            # Check the ARTIM timer first so its event is placed on the queue
            #   ahead of any other events this loop
            if self.artim_timer.expired:
                self.event_queue.put("Evt18")

            # Check the connection for incoming data
            try:
                # We can either encode and send a primitive **OR**
                #   receive and decode a PDU per loop of the reactor
                if self._process_recv_primitive():  # encode (sent by state machine)
                    pass
                elif self._is_transport_event():  # receive and decode PDU
                    self._idle_timer.restart()
            except Exception as exc:
                LOGGER.error("Exception in DUL.run(), aborting association")
                LOGGER.exception(exc)
                # Bypass the state machine and send an A-ABORT
                #   we do it this way because an exception here will mess up
                #   the state machine and we can't guarantee it'll get sent
                #   otherwise
                abort_pdu = A_ABORT_RQ()
                abort_pdu.source = 0x02
                abort_pdu.reason_diagnostic = 0x00
                self.socket.send(abort_pdu.encode())
                self.assoc.is_aborted = True
                self.assoc.is_established = False
                # Hard shutdown of the Association and DUL reactors
                self.assoc._kill = True
                self._kill_thread = True
                return

            # Check the event queue to see if there is anything to do
            try:
                event = self.event_queue.get(block=False)
            # If the queue is empty, return to the start of the loop
            except queue.Empty:
                sleep = True
                continue

            self.state_machine.do_action(event)
            sleep = False

    def _send(self, pdu: _PDUType) -> None:
        """Encode and send a PDU to the peer.

        Parameters
        ----------
        pdu : pynetdicom.pdu.PDU
            The PDU to be encoded and sent to the peer.
        """
        if self.socket is not None:
            self.socket.send(pdu.encode())
            evt.trigger(self.assoc, evt.EVT_PDU_SENT, {"pdu": pdu})
        else:
            LOGGER.warning("Attempted to send data over closed connection")

    def send_pdu(self, primitive: _PDUPrimitiveType) -> None:
        """Place a primitive in the provider queue to be sent to the peer.

        Primitives are converted to the corresponding PDU and encoded before
        sending.

        Parameters
        ----------
        primitive : pdu_primitives.PDU sub-class
            A service primitive, one of:

            .. currentmodule:: pynetdicom.pdu_primitives

            * :class:`A_ASSOCIATE`
            * :class:`A_RELEASE`
            * :class:`A_ABORT`
            * :class:`A_P_ABORT`
            * :class:`P_DATA`
        """
        # Event handler - ACSE sent primitive to the DUL service
        if isinstance(primitive, (A_ASSOCIATE, A_RELEASE, A_ABORT, A_P_ABORT)):
            evt.trigger(self.assoc, evt.EVT_ACSE_SENT, {"primitive": primitive})

        self.to_provider_queue.put(primitive)

    def stop_dul(self) -> bool:
        """Stop the reactor if current state is ``'Sta1'``

        Returns
        -------
        bool
            ``True`` if ``'Sta1'`` and the reactor has stopped, ``False``
            otherwise
        """
        if self.state_machine.current_state == "Sta1":
            self._kill_thread = True
            # Fix for Issue 39
            # Give the DUL thread time to exit
            while self.is_alive():
                time.sleep(self._run_loop_delay)

            return True

        return False


_PDU_TYPES: dict[bytes, tuple[Type[_PDUType], str]] = {
    b"\x01": (A_ASSOCIATE_RQ, "Evt6"),
    b"\x02": (A_ASSOCIATE_AC, "Evt3"),
    b"\x03": (A_ASSOCIATE_RJ, "Evt4"),
    b"\x04": (P_DATA_TF, "Evt10"),
    b"\x05": (A_RELEASE_RQ, "Evt12"),
    b"\x06": (A_RELEASE_RP, "Evt13"),
    b"\x07": (A_ABORT_RQ, "Evt16"),
}
