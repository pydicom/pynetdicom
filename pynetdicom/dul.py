"""
Implements the DICOM Upper Layer service provider.
"""

import logging
import os
try:
    import queue
except ImportError:
    import Queue as queue  # Python 2 compatibility
import select
import socket
from struct import unpack
from threading import Thread
import time

from pynetdicom.fsm import StateMachine, InvalidEventError
from pynetdicom.pdu import (
    A_ASSOCIATE_RQ, A_ASSOCIATE_AC, A_ASSOCIATE_RJ,
    P_DATA_TF, A_RELEASE_RQ, A_RELEASE_RP, A_ABORT_RQ
)
from pynetdicom.pdu_primitives import (
    A_ASSOCIATE, A_RELEASE, A_ABORT, A_P_ABORT, P_DATA
)
from pynetdicom.timer import Timer

LOGGER = logging.getLogger('pynetdicom.dul')


class DULServiceProvider(Thread):
    """The DICOM Upper Layer Service Provider.

    Attributes
    ----------
    artim_timer : timer.Timer
        The ARTIM timer
    association : association.Association
        The DUL's current Association
    client_socket : transport.AssociationSocket
        A wrapped socket.socket object used to communicate with the peer.
    to_provider_queue : queue.Queue
        Queue of PDUs from the DUL service user to be processed by the DUL
        provider
    to_user_queue : queue.Queue
        Queue of primitives from the DUL service to be processed by the DUL user
    event_queue : queue.Queue
        List of queued events to be processed by the state machine
    state_machine : fsm.StateMachine
        The DICOM Upper Layer's State Machine
    """
    def __init__(self, assoc):
        """
        Parameters
        ----------
        assoc : association.Association
            The DUL's parent Association instance.
        """
        # The association thread
        self.assoc = assoc
        self.socket = None

        # Current primitive and PDU
        # TODO: Don't do it this way
        self.primitive = None
        self.pdu = None

        # Tracks the events the state machine needs to process
        self.event_queue = queue.Queue()
        # These queues provide communication between the DUL service
        #   user and the DUL service provider.
        # An event occurs when the DUL service user adds to
        #   the to_provider_queue
        self.to_provider_queue = queue.Queue()
        # A primitive is sent to the service user when the DUL service provider
        # adds to the to_user_queue.
        self.to_user_queue = queue.Queue()

        # Setup the idle and  ARTIM timer
        # FIXME: Why do we have an idle timer?
        self._idle_timer = Timer(self.assoc.network_timeout)
        self.artim_timer = Timer(self.assoc.acse_timeout)

        # State machine - PS3.8 Section 9.2
        self.state_machine = StateMachine(self)

        # Controls the minimum delay between loops in run()
        # TODO: try and make this event based rather than running loops
        self._run_loop_delay = 0.001

        Thread.__init__(self)
        self.daemon = False
        self._kill_thread = False

    def idle_timer_expired(self):
        """
        Checks if the idle timer has expired

        Returns
        -------
        bool
            True if the idle timer has expired, False otherwise
        """
        if self._idle_timer is None:
            return False

        if self._idle_timer.is_expired:
            return True

        return False

    def kill_dul(self):
        """Immediately interrupts the thread"""
        self._kill_thread = True

    def peek_next_pdu(self):
        """Check the next PDU to be processed."""
        try:
            return self.to_user_queue.queue[0]
        except (queue.Empty, IndexError):
            return None

    def receive_pdu(self, wait=False, timeout=None):
        """
        Get the next item to be processed out of the queue of items sent
        from the DUL service provider to the service user

        Parameters
        ----------
        wait : bool, optional
            If `wait` is True and `timeout` is None, blocks until an item
            is available. If `timeout` is a positive number, blocks at most
            `timeout` seconds. Otherwise returns an item if one is immediately
            available.
        timeout : int or None
            See the definition of `wait`

        Returns
        -------
        queue_item
            The next object in the to_user_queue.
        None
            If the queue is empty.
        """
        try:
            # Remove and return an item from the queue
            #   If block is True and timeout is None then block until an item
            #       is available.
            #   If timeout is a positive number, blocks timeout seconds and
            #       raises queue.Empty if no item was available in that time.
            #   If block is False, return an item if one is immediately
            #       available, otherwise raise queue.Empty
            queue_item = self.to_user_queue.get(block=wait, timeout=timeout)
            return queue_item
        except queue.Empty:
            return None

    def run(self):
        """
        The main threading.Thread run loop. Runs constantly, checking the
        connection for incoming data. When incoming data is received it
        categorises it and add its to the `to_user_queue`.

        Ripping out this loop and replacing it with event-driven reactor would
            be nice.
        """
        # Main DUL loop
        if self._idle_timer is not None:
            self._idle_timer.start()

        while True:
            # This effectively controls how often the DUL checks the network
            time.sleep(self._run_loop_delay)

            if self._kill_thread:
                break

            # Check the connection for incoming data
            try:
                # If local AE is SCU also calls _check_incoming_pdu()
                if self._is_transport_event() and self._idle_timer is not None:
                    self._idle_timer.restart()
                elif self._check_incoming_primitive():
                    pass

                if self._is_artim_expired():
                    self._kill_thread = True

            except Exception as exc:
                # FIXME: This catch all should be removed
                self._kill_thread = True
                raise

            # Check the event queue to see if there is anything to do
            try:
                event = self.event_queue.get(block=False)
            # If the queue is empty, return to the start of the loop
            except queue.Empty:
                continue

            self.state_machine.do_action(event)

    # TODO docstring
    def send_pdu(self, params):
        """

        Parameters
        ----------
        params -
            The parameters to put on FromServiceUser [FIXME]
        """
        self.to_provider_queue.put(params)

    def stop_dul(self):
        """
        Interrupts the thread if state is "Sta1"

        Returns
        -------
        bool
            True if Sta1, False otherwise
        """
        if self.state_machine.current_state == 'Sta1':
            self._kill_thread = True
            # Fix for Issue 39
            # Give the DUL thread time to exit
            while self.is_alive():
                time.sleep(0.001)

            return True

        return False

    # New, keep -> TODO docstring
    def _receive_pdu(self):
        bytestream = bytearray()

        # Try and read the PDU type and length from the socket
        try:
            bytestream.extend(self.socket.recv(6))
        except (socket.error, socket.timeout):
            # Evt17: Transport connection closed
            self.event_queue.put('Evt17')
            return None

        try:
            # Byte 1 is always the PDU type
            # Byte 2 is always reserved
            # Bytes 3-6 are always the PDU length
            pdu_type, _, pdu_length = unpack('>BBL', bytestream)
        except struct.error:
            # Raised if there's not enough data
            # Evt17: Transport connection closed
            self.event_queue.put('Evt17')
            return None

        # If the `pdu_type` is unrecognised
        if pdu_type not in (0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07):
            # Evt19: Unrecognised or invalid PDU received
            self.event_queue.put('Evt19')
            return None

        # Try and read the rest of the PDU
        try:
            bytestream += self.socket.recv(pdu_length)
        except (socket.error, socket.timeout):
            # Evt17: Transport connection closed
            self.event_queue.put('Evt17')
            return None

        # Check that the PDU data was completely read
        if len(bytestream) != 6 + pdu_length:
            # Evt17: Transport connection closed
            self.event_queue.put('Evt17')
            return None

        try:
            # Decode the PDU data, get corresponding FSM and callback events
            pdu, event = self._process_pdu(bytestream)
            self.event_queue.put(event)
        except Exception as exc:
            LOGGER.error('Unable to decode the received PDU data')
            LOGGER.exception(exc)
            # Evt19: Unrecognised or invalid PDU received
            self.event_queue.put('Evt19')
            return None

        self.pdu = pdu
        self.primitive = self.pdu.to_primitive()

    # New, keep -> TODO: docstring
    def _process_pdu(self, bytestream):
        acse = self.assoc.acse
        pdu_types = {
            0x01 : (A_ASSOCIATE_RQ, 'Evt6', acse.debug_receive_associate_rq),
            0x02 : (A_ASSOCIATE_AC, 'Evt3', acse.debug_receive_associate_ac),
            0x03 : (A_ASSOCIATE_RJ, 'Evt4', acse.debug_receive_associate_rj),
            0x04 : (P_DATA_TF, 'Evt10', acse.debug_receive_data_tf),
            0x05 : (A_RELEASE_RQ, 'Evt12', acse.debug_receive_release_rq),
            0x06 : (A_RELEASE_RP, 'Evt13', acse.debug_receive_release_rp),
            0x07 : (A_ABORT_RQ, 'Evt16', acse.debug_receive_abort)
        }

        pdu, event, acse_callback = pdu_types[bytestream[0]]
        pdu = pdu()
        pdu.decode(bytestream)

        # ACSE callback
        acse_callback(pdu)

        return pdu, event

    def _check_incoming_pdu(self):
        """
        Converts an incoming PDU from the peer AE back into a primitive (ie one
        of the following: A-ASSOCIATE, A-RELEASE, A-ABORT, P-DATA, A-P-ABORT)
        """
        bytestream = bytes()

        # Try and read data from the socket
        try:
            # Get the data from the socket
            bytestream = self.socket.recv(1)
        except socket.error:
            self.event_queue.put('Evt17')
            self.socket.close()
            LOGGER.error('DUL: Error reading data from the socket')
            return

        # Remote port has been closed
        if bytestream == bytes():
            self.event_queue.put('Evt17')
            self.socket.close()
            LOGGER.error('Peer has closed transport connection')
            return

        # Incoming data is OK
        else:
            # First byte is always PDU type
            #   0x01 - A-ASSOCIATE-RQ   1, 2, 3-6
            #   0x02 - A-ASSOCIATE-AC   1, 2, 3-6
            #   0x03 - A-ASSOCIATE-RJ   1, 2, 3-6
            #   0x04 - P-DATA-TF        1, 2, 3-6
            #   0x05 - A-RELEASE-RQ     1, 2, 3-6
            #   0x06 - A-RELEASE-RP     1, 2, 3-6
            #   0x07 - A-ABORT          1, 2, 3-6

            # We do all this just to get the length of the PDU
            # Byte 1 is PDU type
            #   (value, )
            pdu_type = unpack('B', bytestream)[0]

            # Unrecognised PDU type - Evt19 in the State Machine
            if pdu_type not in [0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07]:
                LOGGER.error("Unrecognised PDU type: 0x%02x", pdu_type)
                self.event_queue.put('Evt19')
                return

            # Byte 2 is Reserved
            result = self._recvn(self.scu_socket, 1)
            bytestream += result

            # Bytes 3-6 is the PDU length
            result = unpack('B', result)
            length = self._recvn(self.scu_socket, 4)

            bytestream += length
            length = unpack('>L', length)

            # Bytes 7-xxxx is the rest of the PDU
            result = self._recvn(self.scu_socket, length[0])
            bytestream += result

            # Determine the type of PDU coming on remote port, then decode
            # the raw bytestream to the corresponding PDU class
            self.pdu = self._socket_to_pdu(bytestream)

            # Put the event corresponding to the incoming PDU on the queue
            self.event_queue.put(self._pdu_to_event(self.pdu))

            # Convert the incoming PDU to a corresponding ServiceParameters
            #   object
            self.primitive = self.pdu.to_primitive()

    # Neutral
    def _check_incoming_primitive(self):
        """Check the incoming primitive."""
        try:
            # Check the queue and see if there are any primitives
            # If so then put the corresponding event on the event queue
            self.primitive = self.to_provider_queue.get(False)
            self.event_queue.put(self._primitive_to_event(self.primitive))
            return True
        except queue.Empty:
            return False

    def _is_artim_expired(self):
        """Return if the state machine's ARTIM timer has expired.

        If it has then 'Evt18' is added to the event queue.

        Returns
        -------
        bool
            True if the ARTIM timer has expired, False otherwise
        """
        if self.artim_timer.is_expired:
            self.event_queue.put('Evt18')
            return True

        return False

    # Update -> docstring and check
    def _is_transport_event(self):
        """Check to see if the transport connection has incoming data

        Returns
        -------
        bool
            True if an event has been added, False otherwise
        """
        # Sta13: waiting for the transport connection to close
        # however it may still receive data that needs to be acted on
        if self.state_machine.current_state == 'Sta13':
            # If we have no connection to the SCU
            if self.socket is None:
                return False

            # Check to see if there's more data to be read
            #   Might be any incoming PDU or valid/invalid data
            # AssociationSocket.ready will add an event if the connection closes
            # TODO Check ^ works as expected
            if self.socket.ready:
                # Data still available, grab it
                self._receive_pdu()
                return True

            # Once we have no more incoming data close the socket and
            #   add the corresponding event to the queue
            #self.scu_socket.shutdown(socket.SHUT_RDWR)
            self.socket.close()

            return True

        # If we are awaiting transport connection opening to complete
        #   (from local transport service) then issue the corresponding
        #   indication (Sta4 + Evt2 -> AE-2 -> Sta5)
        if self.state_machine.current_state == 'Sta4':
            # TODO: change so this is no longer implicit
            self.event_queue.put('Evt2')
            return True

        # By this point the connection should be established
        #   If theres incoming data on the connection then check the PDU
        #   type
        # Fix for #28 - caused by peer disconnecting before run loop is
        #   stopped by assoc.release()
        if self.socket.ready:
            self._receive_pdu()
            return True

        return False

    # OBSOLETE, remove
    @staticmethod
    def _pdu_to_event(pdu):
        """Returns the event associated with the PDU.

        Parameters
        ----------
        pdu : pdu.PDU
            The PDU

        Returns
        -------
        str
            The event str associated with the PDU
        """
        if pdu.__class__ == A_ASSOCIATE_RQ:
            event_str = 'Evt6'
        elif pdu.__class__ == A_ASSOCIATE_AC:
            event_str = 'Evt3'
        elif pdu.__class__ == A_ASSOCIATE_RJ:
            event_str = 'Evt4'
        elif pdu.__class__ == P_DATA_TF:
            event_str = 'Evt10'
        elif pdu.__class__ == A_RELEASE_RQ:
            event_str = 'Evt12'
        elif pdu.__class__ == A_RELEASE_RP:
            event_str = 'Evt13'
        elif pdu.__class__ == A_ABORT_RQ:
            event_str = 'Evt16'
        else:
            #"Unrecognized or invalid PDU"
            event_str = 'Evt19'

        return event_str

    @staticmethod
    def _primitive_to_event(primitive):
        """Returns the state machine event associated with sending a primitive.

        Parameters
        ----------
        primitive : pdu_primitives.ServiceParameter
            The Association primitive

        Returns
        -------
        str
            The event associated with the primitive
        """
        if primitive.__class__ == A_ASSOCIATE:
            if primitive.result is None:
                # A-ASSOCIATE Request
                event_str = 'Evt1'
            elif primitive.result == 0x00:
                # A-ASSOCIATE Response (accept)
                event_str = 'Evt7'
            else:
                # A-ASSOCIATE Response (reject)
                event_str = 'Evt8'
        elif primitive.__class__ == A_RELEASE:
            if primitive.result is None:
                # A-Release Request
                event_str = 'Evt11'
            else:
                # A-Release Response
                # result is 'affirmative'
                event_str = 'Evt14'
        elif primitive.__class__ in (A_ABORT, A_P_ABORT):
            event_str = 'Evt15'
        elif primitive.__class__ == P_DATA:
            event_str = 'Evt9'
        else:
            raise ValueError("_primitive_to_event(): invalid primitive")

        return event_str

    # OBSOLETE, remove
    @staticmethod
    def _recvn(sock, n_bytes):
        """Read `n_bytes` from a socket.

        Parameters
        ----------
        sock : socket.socket
            The socket to read from
        n_bytes : int
            The number of bytes to read
        """
        ret = b''
        read_length = 0
        while read_length < n_bytes:
            tmp = sock.recv(n_bytes - read_length)

            if not tmp:
                return ret

            ret += tmp
            read_length += len(tmp)

        if read_length != n_bytes:
            raise RuntimeError("_recvn(socket, {}) - Error reading data from "
                               "socket.".format(n_bytes))

        return ret

    # OBSOLETE, remove
    def _socket_to_pdu(self, data):
        """Returns the PDU object associated with an incoming data stream.

        Parameters
        ----------
        data : bytes
            The incoming data stream

        Returns
        -------
        pdu : pdu.PDU
            The decoded data as a PDU object
        """
        pdutype = unpack('B', data[:1])[0]

        acse = self.assoc.acse
        _pdu_types = {
            0x01 : (A_ASSOCIATE_RQ, acse.debug_receive_associate_rq),
            0x02 : (A_ASSOCIATE_AC, acse.debug_receive_associate_ac),
            0x03 : (A_ASSOCIATE_RJ, acse.debug_receive_associate_rj),
            0x04 : (P_DATA_TF, acse.debug_receive_data_tf),
            0x05 : (A_RELEASE_RQ, acse.debug_receive_release_rq),
            0x06 : (A_RELEASE_RP, acse.debug_receive_release_rp),
            0x07 : (A_ABORT_RQ, acse.debug_receive_abort)
        }

        if pdutype in _pdu_types:
            (pdu, acse_callback) = _pdu_types[pdutype]
            pdu = pdu()
            pdu.decode(data)

            # ACSE callbacks
            acse_callback(pdu)

            return pdu

        return None
