"""Defines the Association class which handles associating with peers."""

from io import BytesIO
import logging
import os
from pathlib import Path
import threading
import time
from typing import (
    Callable,
    Any,
    Iterator,
    TYPE_CHECKING,
    cast,
)
import warnings

from pydicom import dcmread
from pydicom.dataset import Dataset
from pydicom.tag import BaseTag
from pydicom.uid import UID, ImplicitVRLittleEndian, ExplicitVRBigEndian

# pylint: disable=no-name-in-module
from pynetdicom.acse import ACSE
from pynetdicom import _config, evt
from pynetdicom.dimse import DIMSEServiceProvider
from pynetdicom.dimse_primitives import (
    C_ECHO,
    C_MOVE,
    C_STORE,
    C_GET,
    C_FIND,
    C_CANCEL,
    N_EVENT_REPORT,
    N_GET,
    N_SET,
    N_CREATE,
    N_ACTION,
    N_DELETE,
    DimseServiceType,
)
from pynetdicom.dsutils import decode, encode, pretty_dataset, split_dataset
from pynetdicom.dul import DULServiceProvider
from pynetdicom._globals import (
    MODE_REQUESTOR,
    MODE_ACCEPTOR,
    DEFAULT_MAX_LENGTH,
    STATUS_WARNING,
    STATUS_SUCCESS,
    STATUS_CANCEL,
    STATUS_PENDING,
    STATUS_FAILURE,
)
from pynetdicom._handlers import (
    standard_dimse_recv_handler,
    standard_dimse_sent_handler,
    standard_pdu_recv_handler,
    standard_pdu_sent_handler,
)
from pynetdicom.pdu_primitives import (
    UserIdentityNegotiation,
    MaximumLengthNotification,
    ImplementationClassUIDNotification,
    ImplementationVersionNameNotification,
    AsynchronousOperationsWindowNegotiation,
    SOPClassExtendedNegotiation,
    SOPClassCommonExtendedNegotiation,
    SCP_SCU_RoleSelectionNegotiation,
    A_ASSOCIATE,
    _UI,
    _UITypes,
)
from pynetdicom.presentation import PresentationContext
from pynetdicom.sop_class import (  # type: ignore
    RepositoryQuery,
    uid_to_service_class,
    UnifiedProcedureStepPull,
    UnifiedProcedureStepPush,
    UnifiedProcedureStepEvent,
    UnifiedProcedureStepQuery,
    UnifiedProcedureStepWatch,
    Verification,
)
from pynetdicom.status import code_to_category, STORAGE_SERVICE_CLASS_STATUS
from pynetdicom.transport import AddressInformation
from pynetdicom.utils import make_target, set_timer_resolution, set_ae, decode_bytes

if TYPE_CHECKING:  # pragma: no cover
    from pynetdicom.ae import ApplicationEntity
    from pynetdicom.transport import AssociationServer, AssociationSocket


# pylint: enable=no-name-in-module
LOGGER = logging.getLogger(__name__)
HandlerType = dict[
    evt.EventType,
    (list[tuple[Callable, None | list[Any]]] | tuple[Callable, None | list[Any]]),
]


class Association(threading.Thread):
    """Manage an Association with a peer AE.

    Attributes
    ----------
    acceptor : association.ServiceUser
        Representation of the association's *acceptor* AE.
    acse : acse.ACSE
        The Association Control Service Element provider.
    dimse : dimse.DIMSEServiceProvider
        The DICOM Message Service Element provider.
    dul : dul.DULServiceProvider
        The DICOM Upper Layer service provider.
    is_aborted : bool
        ``True`` if the association has been aborted, ``False`` otherwise.
    is_established : bool
        ``True`` if the association has been established, ``False`` otherwise.
    is_rejected : bool
        ``True`` if the association was rejected, ``False`` otherwise.
    is_released : bool
        ``True`` if the association has been released, ``False`` otherwise.
    network_timeout_response : str
        If ``"A-RELEASE"`` then initiate a normal association release on expiry of the
        network timeout, otherwise issue an A-ABORT (default).
    requestor : association.ServiceUser
        Representation of the association's *requestor* AE.
    """

    def __init__(self, ae: "ApplicationEntity", mode: str) -> None:
        """Create a new :class:`Association` instance.

        The association starts in State 1 (idle). Association negotiation
        won't begin until an :class:`~pynetdicom.transport.AssociationSocket`
        is assigned using :meth:`set_socket` and
        :meth:`~threading.Thread.start` is called.

        Parameters
        ----------
        ae : ae.ApplicationEntity
            The local AE.
        mode : str
            Must be ``'requestor'`` or ``'acceptor'``.
        """
        self._ae: "ApplicationEntity" = ae
        self.mode: str = mode

        # If acceptor this is the parent AssociationServer, used to identify
        #   the thread when updating bound event-handlers
        self._server: None | "AssociationServer" = None

        # Represents the association requestor and acceptor users
        self.requestor: ServiceUser = ServiceUser(self, MODE_REQUESTOR)
        self.acceptor: ServiceUser = ServiceUser(self, MODE_ACCEPTOR)

        # Status attributes
        self.is_established: bool = False
        self.is_rejected: bool = False
        self.is_aborted: bool = False
        self.is_released: bool = False

        # Track whether we've sent an abort or not for the abort() method
        self._sent_abort: bool = False
        # Track whether we've sent a release or not
        self._sent_release: bool = False

        # Accepted and rejected presentation contexts
        self._accepted_cx: dict[int, PresentationContext] = {}
        self._rejected_cx: list[PresentationContext] = []

        # Service providers
        self.acse: ACSE = ACSE(self)
        self.dul: DULServiceProvider = DULServiceProvider(self)
        self.dimse: DIMSEServiceProvider = DIMSEServiceProvider(self)

        # Timeouts (in seconds), needs to be set after DUL init
        self.acse_timeout: float | None = self.ae.acse_timeout
        self.connection_timeout: float | None = self.ae.connection_timeout
        self.dimse_timeout: float | None = self.ae.dimse_timeout
        self.network_timeout: float | None = self.ae.network_timeout

        # Allow customising the response to a network timeout
        self.network_timeout_response = "A-ABORT"

        # Event handlers
        self._handlers: HandlerType = {}
        self._bind_defaults()

        # Kills the thread loop in run()
        self._kill: bool = False
        # Flag for whether or not the DUL thread has been started
        self._started_dul: bool = False
        # Used to pause the association reactor until the DUL is ready
        self._dul_ready: threading.Event = threading.Event()
        # Used to pause the association reactor while a service is being used
        self._reactor_checkpoint: threading.Event = threading.Event()
        self._reactor_checkpoint.set()
        # Used to ensure the reactor is paused before DIMSE messaging
        self._is_paused: bool = False

        # Windows timer resolution
        self._timer_resolution: float | None = _config.WINDOWS_TIMER_RESOLUTION

        # Thread setup
        threading.Thread.__init__(self, target=make_target(self.run_reactor))
        self.daemon: bool = True

    def abort(self, block: bool = True) -> None:
        """Abort the :class:`Association` by sending an A-ABORT to the remote
        AE.

        .. versionchanged:: 3.0

            Added the `block` keyword parameter.

        Parameters
        ----------
        block : bool, optional

            * If ``True`` then this function blocks until the A-ABORT PDU has been sent
              to  the peer, the connection shutdown and the state machine returned to
              State 1 (idle). This is the default when ``abort()`` is called outside
              of an event handler.
            * If ``False`` then the function returns after adding an A-ABORT request
              primitive to the outgoing queue. This is the default when ``abort()``
              is called inside an event handler.
        """
        return self._abort_blocking(block)

    def _abort_blocking(self, block: bool = True) -> None:
        """Blocking implementation of Association.abort()"""
        # Only allow a single abort message to be sent
        if self._sent_abort:
            return

        if self.is_released:
            return

        # Set before restarting the reactor to prevent race condition
        self._sent_abort = True
        # Ensure the reactor is running so it can be exited
        self._reactor_checkpoint.set()
        LOGGER.info("Aborting Association")
        self.acse.send_abort(0x00)

        # Event handler - association aborted
        evt.trigger(self, evt.EVT_ABORTED, {})

        if block is False:
            return

        self.kill()

        # Ensure socket is shutdown and closed
        try:
            cast(AssociationSocket, self.dul.socket)._shutdown_socket()
        except Exception:
            pass

        # Add short delay to ensure everything shuts down
        time.sleep(0.1)

    def _abort_nonblocking(self, block: bool = False) -> None:
        """Non-blocking implementation of Association.abort()"""
        return self._abort_blocking(block)

    @property
    def accepted_contexts(self) -> list[PresentationContext]:
        """Return a :class:`list` of accepted
        :class:`~pynetdicom.presentation.PresentationContext` items."""
        # Accepted contexts are stored internally as {context ID : context}
        return sorted(self._accepted_cx.values(), key=lambda x: cast(int, x.context_id))

    @property
    def acse_timeout(self) -> float | None:
        """The ACSE timeout (in seconds)."""
        return self._acse_timeout

    @acse_timeout.setter
    def acse_timeout(self, value: float | None) -> None:
        """Set the ACSE timeout using numeric or ``None``."""
        with self.lock:
            self.dul.artim_timer.timeout = value
            self._acse_timeout = value

    @property
    def ae(self) -> "ApplicationEntity":
        """Return the parent :class:`~pynetdicom.ae.ApplicationEntity`."""
        return self._ae

    def bind(
        self, event: evt.EventType, handler: Callable, args: None | list[Any] = None
    ) -> None:
        """Bind a callable `handler` to an `event`.

        Parameters
        ----------
        event : collections.namedtuple
            The event to bind the function to.
        handler : callable
            The function that will be called if the event occurs.
        args : list, optional
            Optional extra arguments to be passed to the handler (default:
            no extra arguments passed to the handler).
        """
        # Make sure no access to `_handlers` while its being changed
        with self.lock:
            evt._add_handler(event, self._handlers, (handler, args))

    def _bind_defaults(self) -> None:
        """Bind the default event handlers."""
        # Intervention event handlers
        for event in evt._INTERVENTION_EVENTS:
            handler = evt.get_default_handler(event)
            self.bind(event, handler)

        # Notification event handlers
        if _config.LOG_HANDLER_LEVEL == "standard":
            self.bind(evt.EVT_DIMSE_RECV, standard_dimse_recv_handler)
            self.bind(evt.EVT_DIMSE_SENT, standard_dimse_sent_handler)
            self.bind(evt.EVT_PDU_RECV, standard_pdu_recv_handler)
            self.bind(evt.EVT_PDU_SENT, standard_pdu_sent_handler)

    def _check_received_status(self, rsp: DimseServiceType) -> Dataset:
        """Return a :class:`~pydicom.dataset.Dataset` containing status
        related elements.

        Parameters
        ----------
        rsp : dimse_primitives.DIMSEMessage
            The DIMSE Message primitive received from the peer in response
            to a service request.

        Returns
        -------
        pydicom.dataset.Dataset
            If no response or an invalid response was received from the peer
            then an empty :class:`~pydicom.dataset.Dataset`, if a valid
            response was received from the peer then (at a minimum) a
            :class:`~pydicom.dataset.Dataset` containing an
            (0000,0900) *Status* element, and any included optional status
            related elements.
        """
        msg_type = rsp.__class__.__name__
        msg_type = msg_type.replace("_", "-")

        status = Dataset()
        if rsp.is_valid_response:
            status.Status = rsp.Status
            for keyword in rsp.STATUS_OPTIONAL_KEYWORDS:
                if getattr(rsp, keyword, None) is not None:
                    setattr(status, keyword, getattr(rsp, keyword))
        else:
            LOGGER.error(f"Received an invalid {msg_type} response from the peer")
            self.abort()

        return status

    @property
    def dimse_timeout(self) -> int | float | None:
        """The DIMSE timeout (in seconds)."""
        return self._dimse_timeout

    @dimse_timeout.setter
    def dimse_timeout(self, value: int | float | None) -> None:
        """Set the DIMSE timeout using numeric or ``None``."""
        with self.lock:
            self._dimse_timeout = value

    def get_events(self) -> list[evt.EventType]:
        """Return a :class:`list` of currently bound events."""
        return sorted(self._handlers.keys(), key=lambda x: x.name)

    def get_handlers(self, event: evt.EventType) -> evt.HandlerArgType:
        """Return the handlers bound to a specific `event`.

        Parameters
        ----------
        event : namedtuple
            The event bound to the handlers.

        Returns
        -------
        2-tuple of (callable, args), list of 2-tuple
            If the event is a notification event then returns a list of
            2-tuples containing the callable functions bound to `event` and
            the arguments passed to the callable as ``(callable, args)``. If
            the event is an intervention event then returns either a 2-tuple of
            (callable, args) if a handler is bound to the event or
            ``(None, None)`` if no handler has been bound.
        """
        if event not in self._handlers:
            return []

        return self._handlers[event]

    def _get_valid_context(
        self,
        ab_syntax: str | UID,
        tr_syntax: str | UID,
        role: str | None = None,
        context_id: int | None = None,
        allow_conversion: bool = True,
    ) -> PresentationContext:
        """Return a valid presentation context matching the parameters.

        .. versionchanged:: 2.0

            Added `allow_conversion` keyword parameter.

        Parameters
        ----------
        ab_syntax : str or pydicom.uid.UID
            The abstract syntax to match.
        tr_syntax : str or pydicom.uid.UID
            The transfer syntax to match, if an empty string is used then
            the transfer syntax will not be used for matching. If the value
            corresponds to an uncompressed syntax then matches will be made
            with any uncompressed transfer syntax but an exact match will
            be preferred.
        role : str, optional
            One of ``'scu'`` or ``'scp'``, the required role of the context.
            If not used then the accepted role will be ignored.
        context_id : int, optional
            If used then the ID of the presentation context to use. It
            will be checked against the available parameter values. If the ID
            isn't found then will check against all accepted contexts.
        allow_conversion : bool, optional
            If ``True`` (default), then if there's no exact matching accepted
            presentation context then use a convertible one instead. If
            ``False`` then an exact matching context is required.

        Returns
        -------
        presentation.PresentationContext
            An accepted presentation context.
        """
        ab_syntax = UID(ab_syntax)
        tr_syntax = UID(tr_syntax)

        try:
            possible_contexts = [self._accepted_cx[context_id]]  # type: ignore
        except KeyError:
            possible_contexts = self.accepted_contexts

        # Filter by abstract syntax
        possible_contexts = [
            cx for cx in possible_contexts if ab_syntax == cx.abstract_syntax
        ]

        # For UPS we can also match UPS Push to Pull/Watch/Event/Query
        if ab_syntax == UnifiedProcedureStepPush and not possible_contexts:
            LOGGER.info(
                "No exact matching context found for 'Unified Procedure Step "
                "- Push SOP Class', checking accepted contexts for other UPS "
                "SOP classes"
            )
            ups = [
                UnifiedProcedureStepPull,
                UnifiedProcedureStepWatch,
                UnifiedProcedureStepEvent,
                UnifiedProcedureStepQuery,
            ]
            possible_contexts.extend(
                [cx for cx in self._accepted_cx.values() if cx.abstract_syntax in ups]
            )

        # Filter by role
        if role == "scu":
            possible_contexts = [cx for cx in possible_contexts if cx.as_scu is True]
        if role == "scp":
            possible_contexts = [cx for cx in possible_contexts if cx.as_scp is True]

        matches = []
        for cx in possible_contexts:
            cx_syntax = cx.transfer_syntax[0]
            if tr_syntax:
                if tr_syntax == cx_syntax:
                    # Exact match to transfer syntax
                    return cx

                # Compressed transfer syntaxes are not convertible
                #   This excludes deflated transfer syntaxes
                if tr_syntax.is_compressed or cx_syntax.is_compressed:
                    continue

                # Filter out contexts where the endianness doesn't match
                if tr_syntax.is_little_endian != cx_syntax.is_little_endian:
                    continue

            # Match to convertible transfer syntaxes
            #   Allowable matches:
            #       explicit VR <-> implicit VR
            #       deflated <-> inflated
            matches.append(cx)

        if allow_conversion and matches:
            return matches[0]

        role = role or "scu"
        msg = (
            f"No presentation context for '{ab_syntax.name}' has been "
            f"accepted by the peer"
        )
        if tr_syntax:
            msg += f" with '{tr_syntax.name}' transfer syntax"
        msg += f" for the {role.upper()} role"

        LOGGER.error(msg)
        raise ValueError(msg)

    def _handle_no_response(self) -> None:
        """Common reaction when DIMSE timeout hit or no response message."""
        # Avoids writing the same unit test for each send_ method
        if self.acse.is_aborted("a-abort"):
            # Let the main reactor loop handle A-ABORT logging
            pass
        elif self.acse.is_aborted("a-p-abort"):
            # Evt17 occurred while in Sta6
            LOGGER.error("Connection closed while waiting for DIMSE message")
        elif self.is_established:
            LOGGER.error("DIMSE timeout reached while waiting for message response")
            self.abort()

    @property
    def is_acceptor(self) -> bool:
        """Return ``True`` if the local AE is the association *acceptor*."""
        return self.mode == MODE_ACCEPTOR

    @property
    def is_requestor(self) -> bool:
        """Return ``True`` if the local AE is the association *requestor*."""
        return self.mode == MODE_REQUESTOR

    def kill(self) -> None:
        """Kill the :class:`Association` thread."""
        # Ensure the reactor is running so it can be exited
        self._reactor_checkpoint.set()
        self._kill = True
        self.is_established = False
        self._is_paused = True
        while self.dul.is_alive() and not self.dul.stop_dul():
            time.sleep(0.01)

    @property
    def local(self) -> dict[str, Any]:
        """Return a :class:`dict` with information about the local AE."""
        if self.is_acceptor:
            return self.acceptor.info

        return self.requestor.info

    @property
    def lock(self) -> threading.Lock:
        """Return the AE's :class:`threading.Lock`."""
        return self.ae._lock

    @property
    def mode(self) -> str:
        """The Association's `mode` as a :class:`str`.

        Parameters
        ----------
        mode : str
            The mode of the Association, must be either ``'requestor'`` or
            ``'acceptor'``. If ``'requestor'`` then its assumed that the local
            AE requests an association with peers and (by default) acts as the
            SCU. If ``'acceptor'`` then its assumed that the local AE is
            listening for association requests and (by default) acts as the
            SCP.
        """
        return self._mode

    @mode.setter
    def mode(self, mode: str) -> None:
        """Set the Association's mode."""
        mode = mode.lower()
        if mode not in [MODE_REQUESTOR, MODE_ACCEPTOR]:
            raise ValueError(
                "Invalid association `mode` value, must be either 'requestor' "
                "or 'acceptor'"
            )

        # pylint: disable=attribute-defined-outside-init
        self._mode = mode

    @property
    def network_timeout(self) -> int | float | None:
        """The network timeout (in seconds)."""
        return self._network_timeout

    @network_timeout.setter
    def network_timeout(self, value: int | float | None) -> None:
        """Set the network timeout using numeric or ``None``."""
        with self.lock:
            self.dul._idle_timer.timeout = value
            self._network_timeout = value

    @property
    def rejected_contexts(self) -> list[PresentationContext]:
        """Return a :class:`list` of rejected
        :class:`~pynetdicom.presentation.PresentationContext`.
        """
        return self._rejected_cx

    def release(self) -> None:
        """Initiate association release by sending an A-RELEASE request."""
        if self.is_established:
            # Ensure the reactor is paused so it doesn't
            #   steal incoming ACSE messages
            self._reactor_checkpoint.clear()
            while not self._is_paused:
                time.sleep(0.0001)

            LOGGER.info("Releasing Association")
            self.acse.negotiate_release()
            # Restart reactor
            self._reactor_checkpoint.set()

    @property
    def remote(self) -> dict[str, Any]:
        """Return a :class:`dict` with information about the peer AE."""
        if self.is_acceptor:
            return self.requestor.info

        return self.acceptor.info

    def request(self) -> None:
        """Request an association with a peer.

        A request can only be made once the :class:`Association` instance has
        been configured for requestor mode and been assigned an
        :class:`~pynetdicom.transport.AssociationSocket`.
        """
        # Start the DUL thread if not already started
        self.dul.start()
        self._started_dul = True
        # Wait until the DUL is up and running
        self._dul_ready.wait()
        # Start association negotiation
        LOGGER.info("Requesting Association")
        self.acse.negotiate_association()

    def run_reactor(self) -> None:
        """The main :class:`Association` reactor."""
        # Start the DUL thread if not already started
        if not self._started_dul:
            self.dul.start()
            self._started_dul = True
            # Wait until the DUL is up and running
            self._dul_ready.wait()

        if self.is_acceptor:
            primitive = self.dul.receive_pdu(wait=True, timeout=self.acse_timeout)

            # Timed out waiting for A-ASSOCIATE request
            if primitive is None:
                self.kill()

                # Ensure the connection is shutdown properly
                sock = cast("AssociationSocket", self.dul.socket)
                if self._server and sock.socket:
                    self._server.shutdown_request(sock.socket)

                return

            self.requestor.primitive = cast(A_ASSOCIATE, primitive)
            evt.trigger(self, evt.EVT_REQUESTED, {})

            # User used EVT_REQUESTED to send an A-ABORT or A-ASSOCIATE-RJ
            if not self.is_aborted and not self.is_rejected:
                self.acse.negotiate_association()

            if self.is_established:
                with set_timer_resolution(self._timer_resolution):
                    self._run_reactor()

            # Ensure the connection is shutdown properly
            sock = cast("AssociationSocket", self.dul.socket)
            if self._server and sock.socket:
                self._server.shutdown_request(sock.socket)
        else:
            # Association requestor
            # Allow non-blocking negotiation
            if (
                not self.is_established
                and not self.is_aborted
                and not self.is_released
                and not self.is_rejected
            ):
                self.acse.negotiate_association()

            if self.is_established:
                with set_timer_resolution(self._timer_resolution):
                    self._run_reactor()

    def _run_reactor(self) -> None:
        """Run the ``Association`` acceptor reactor loop.

        Main acceptor run loop
        1. Checks for incoming DIMSE messages
            If DIMSE message then run corresponding service class' SCP
            method
        2. Checks for peer A-RELEASE request primitive
            If present then kill thread
        3. Checks for peer A-ABORT request primitive
            If present then kill thread
        4. Checks DUL provider still running
            If not then kill thread
        5. Checks DUL idle timeout
            If timed out then kill thread
        """
        self._is_paused = False
        while not self._kill:
            time.sleep(0.001)

            # A race condition may occur if the Acceptor uses the send_*()
            #   methods as the received DIMSE message may be taken off the
            #   queue before the send_*() method gets to it, so we allow
            #   the reactor to be paused
            # We also need to be careful that the reactor actually stops
            #   before attempting DIMSE or ACSE messaging
            # Will block until `_reactor_checkpoint` is set()
            self._is_paused = True
            self._reactor_checkpoint.wait()
            self._is_paused = False

            # Check with the DIMSE provider to see if a completely decoded
            #   message is available
            context_id, msg = self.dimse.get_msg(block=False)
            if msg:
                self._serve_request(msg, cast(int, context_id))

            # Check for release request from the peer
            if self.is_established and self.acse.is_release_requested():
                # Send A-RELEASE response
                self.acse.send_release(is_response=True)
                LOGGER.info("Association Released")
                self.is_released = True
                self.is_established = False
                evt.trigger(self, evt.EVT_RELEASED, {})
                self.kill()
                return

            # Check for abort from either locally or the peer
            if self.acse.is_aborted():
                log_msg = "Association Aborted"
                if self.acse.is_aborted("a-p-abort"):
                    log_msg += " (A-P-ABORT)"
                LOGGER.info(log_msg)
                # Ensure that EVT_ASCE_RECV fires for subscribers
                self.dul.receive_pdu(wait=False)
                self.is_aborted = True
                self.is_established = False
                evt.trigger(self, evt.EVT_ABORTED, {})
                self.kill()
                return

            # Check if the DULServiceProvider thread is still running
            #   DUL.is_alive() is inherited from threading.thread
            if not self.dul.is_alive():
                self.kill()
                return

            # Check if network_timeout has expired
            if self.dul.idle_timer_expired():
                LOGGER.error("Network timeout reached")
                if self.network_timeout_response == "A-RELEASE":
                    self._is_paused = True
                    self._reactor_checkpoint.wait()
                    self.release()
                    self._is_paused = False
                else:
                    self.abort()

                self.kill()
                return

    def set_socket(self, socket: "AssociationSocket") -> None:
        """Set the `socket` to use for communicating with the peer.

        Parameters
        ----------
        socket : transport.AssociationSocket
            The socket to use.

        Raises
        ------
        RuntimeError
            If the :class:`Association` already has a socket set.
        """
        if self.dul.socket is not None:
            raise RuntimeError("The Association already has a socket set")

        self.dul.socket = socket

    def unbind(self, event: evt.EventType, handler: Callable) -> None:
        """Unbind a callable `handler` from an `event`.

        Parameters
        ----------
        event : namedtuple
            The event to unbind the function from.
        handler : callable
            The function that will no longer be called if the event occurs.
        """
        # Make sure no access to `_handlers` while its being changed
        with self.lock:
            evt._remove_handler(event, self._handlers, handler)

    # DIMSE-C services provided by the Association
    def _c_store_scp(self, req: C_STORE) -> None:
        """A C-STORE SCP implementation.

        Handles C-STORE requests from the peer over the same association as
        the local AE sent a C-MOVE or C-GET request.

        Must always send a C-STORE response back to the peer.

        C-STORE Request
        ---------------
        Parameters
        ~~~~~~~~~~
        (M) Message ID
        (M) Affected SOP Class UID
        (M) Affected SOP Instance UID
        (M) Priority
        (U) Move Originator Application Entity Title
        (U) Move Originator Message ID
        (M) Data Set

        Parameters
        ----------
        req : dimse_primitives.C_STORE
            The C-STORE request primitive received from the peer.
        """
        # Build C-STORE response primitive
        #   (U) Message ID
        #   (M) Message ID Being Responded To
        #   (U) Affected SOP Class UID
        #   (U) Affected SOP Instance UID
        #   (M) Status
        rsp = C_STORE()
        rsp.MessageID = req.MessageID
        rsp.MessageIDBeingRespondedTo = req.MessageID
        rsp.AffectedSOPInstanceUID = req.AffectedSOPInstanceUID
        rsp.AffectedSOPClassUID = req.AffectedSOPClassUID

        try:
            context = self._get_valid_context(
                cast(UID, req.AffectedSOPClassUID),
                "",
                "scp",
                context_id=req._context_id,
            )
        except ValueError:
            # SOP Class not supported, no context ID?
            rsp.Status = 0x0122
            self.dimse.send_msg(rsp, 1)
            return

        # Attempt to handle the service request
        try:
            status = evt.trigger(
                self, evt.EVT_C_STORE, {"request": req, "context": context.as_tuple}
            )
        except Exception as ex:
            LOGGER.error("Exception in the handler bound to 'evt.EVT_C_STORE'")
            LOGGER.exception(ex)
            rsp.Status = 0xC211
            self.dimse.send_msg(rsp, cast(int, context.context_id))
            return

        # Check the callback's returned status
        if isinstance(status, Dataset):
            if "Status" in status:
                # For the elements in the status dataset, try and set
                #   the corresponding response primitive attribute
                for elem in status:
                    if hasattr(rsp, elem.keyword):
                        setattr(rsp, elem.keyword, elem.value)
                    else:
                        LOGGER.warning(
                            "Status dataset returned from the EVT_C_STORE "
                            "handler contained an unsupported element "
                            f"'{elem.keyword}'"
                        )
            else:
                LOGGER.error(
                    "The EVT_C_STORE handler returned a Dataset without a "
                    "'Status' element"
                )
                rsp.Status = 0xC001
        elif isinstance(status, int):
            rsp.Status = status
        else:
            LOGGER.error("Invalid status returned by the EVT_C_STORE handler")
            rsp.Status = 0xC002

        if rsp.Status not in STORAGE_SERVICE_CLASS_STATUS:
            LOGGER.warning(
                "Unknown status value returned by the EVT_C_STORE handler: "
                f"0x{rsp.Status:04X}"
            )

        # Send C-STORE confirmation back to peer
        self.dimse.send_msg(rsp, cast(int, context.context_id))

    def send_c_cancel(
        self,
        msg_id: int,
        context_id: int | None = None,
        query_model: str | UID | None = None,
    ) -> None:
        """Send a C-CANCEL request to the peer AE.

        .. versionchanged:: 2.0

            Added `query_model` and made `context_id` optional

        Parameters
        ----------
        msg_id : int
            The *Message ID* of the C-GET/C-MOVE/C-FIND operation to be
            cancelled. Must be between 0 and 65535, inclusive.
        context_id : int, optional
            The presentation context ID of the original C-GET/C-MOVE/C-FIND
            service request. Required if `query_model` is not used.
        query_model : str or pydicom.uid.UID, optional
            The query model used with the original C-GET/C-MOVE/C-FIND service
            request. Required if `context_id` is not used.
        """
        # Can't send a C-CANCEL without an Association
        if not self.is_established:
            raise RuntimeError(
                "The association with a peer SCP must be "
                "established before sending a C-CANCEL request"
            )

        if isinstance(query_model, (str, UID)):
            cx = self._get_valid_context(query_model, "", "scu")
            context_id = cx.context_id
        elif isinstance(context_id, int):
            pass
        else:
            raise ValueError(
                "'send_c_cancel' requires either the 'query_model' used for "
                "the service request or the corresponding 'context_id'"
            )

        # Build C-CANCEL primitive
        primitive = C_CANCEL()
        primitive.MessageIDBeingRespondedTo = msg_id

        LOGGER.info("Sending C-CANCEL request")

        # Send C-CANCEL request
        self.dimse.send_msg(primitive, cast(int, context_id))

    def send_c_echo(self, msg_id: int = 1) -> Dataset:
        """Send a C-ECHO request to the peer AE.

        Parameters
        ----------
        msg_id : int, optional
            The C-ECHO request's *Message ID*, must be between 0 and 65535,
            inclusive, (default ``1``).

        Returns
        -------
        status : pydicom.dataset.Dataset
            If the peer timed out, aborted or sent an invalid response then
            returns an empty :class:`~pydicom.dataset.Dataset`. If a valid
            response was received from the peer then returns a
            :class:`~pydicom.dataset.Dataset` containing at least a
            (0000,0900) *Status* element, and, depending on the returned
            *Status* value, may optionally contain additional elements (see
            DICOM Standard, Part 7, :dcm:`Annex C<part07/chapter_C.html>`).

            The DICOM Standard, Part 7, :dcm:`Table 9.3-13
            <part07/sect_9.3.5.2.html>` indicates that the *Status*
            value of a C-ECHO response "shall have a value of Success". However
            :dcm:`Section 9.1.5.1.4<part07/chapter_9.html#sect_9.1.5.1.4>`
            indicates it may have any of the following
            values:

            Success
              | ``0x0000`` - Success

            Failure
              | ``0x0122`` - SOP class not supported
              | ``0x0210`` - Duplicate invocation
              | ``0x0211`` - Unrecognised operation
              | ``0x0212`` - Mistyped argument

            As the actual status depends on the peer SCP, it shouldn't be
            assumed that it will be one of these.

        Raises
        ------
        RuntimeError
            If called without an association to a peer SCP.
        ValueError
            If the association has no accepted presentation context for
            *Verification SOP Class*.

        See Also
        --------
        :class:`~pynetdicom.dimse_primitives.C_ECHO`
        :class:`~pynetdicom.service_class.VerificationServiceClass`

        References
        ----------

        * DICOM Standard, Part 4, :dcm:`Annex A<part04/chapter_A.html>`
        * DICOM Standard, Part 7, Sections
          :dcm:`9.1.5<part07/chapter_9.html#sect_9.1.5>`,
          :dcm:`9.3.5<part07/sect_9.3.5.html>`, and
          :dcm:`Annex C<part07/chapter_C.html>`
        """
        # Can't send a C-ECHO without an Association
        if not self.is_established:
            raise RuntimeError(
                "The association with a peer SCP must be established before "
                "sending a C-ECHO request"
            )

        # Get a Presentation Context to use for sending the message
        context = self._get_valid_context(Verification, "", "scu")

        # Build C-STORE request primitive
        #   (M) Message ID
        #   (M) Affected SOP Class UID
        primitive = C_ECHO()
        primitive.MessageID = msg_id
        primitive.AffectedSOPClassUID = Verification

        # Send C-ECHO request to the peer via DIMSE and wait for the response
        LOGGER.info(f"Sending Echo Request: MsgID {msg_id}")

        # Pause the reactor to prevent a race condition
        self._reactor_checkpoint.clear()
        while not self._is_paused:
            time.sleep(0.0001)

        self.dimse.send_msg(primitive, cast(int, context.context_id))
        cx_id, rsp = self.dimse.get_msg(block=True)

        # Unpause the reactor
        self._reactor_checkpoint.set()

        # If `rsp` is None then the DIMSE timeout expired so abort
        if rsp is None:
            self._handle_no_response()
            return Dataset()

        # Determine validity of the response and get the status
        status = self._check_received_status(rsp)

        return status

    def send_c_find(
        self,
        dataset: Dataset,
        query_model: str | UID,
        msg_id: int = 1,
        priority: int = 2,
    ) -> Iterator[tuple[Dataset, Dataset | None]]:
        """Send a C-FIND request to the peer AE.

        Yields (*status*, *identifier*) pairs for each response from the peer.

        .. versionchanged:: 2.1

            Added support for *Repository Query*

        Parameters
        ----------
        dataset : pydicom.dataset.Dataset
            The C-FIND request's *Identifier* dataset. The exact requirements
            for the *Identifier* dataset are Service Class specific (see the
            DICOM Standard, :dcm:`Part 4<part04/PS3.4.html>`).
        query_model : pydicom.uid.UID or str
            The value to use for the C-FIND request's (0000,0002) *Affected
            SOP Class UID* parameter, which usually corresponds to the
            Information Model that is to be used.
        msg_id : int, optional
            The C-FIND request's *Message ID*, must be between 0 and 65535,
            inclusive, (default ``1``).
        priority : int, optional
            The value of the C-FIND request's *Priority* parameter (may not be
            supported by the peer), one of:

            - ``0`` - Medium
            - ``1`` - High
            - ``2`` - Low (default)

        Yields
        ------
        status : pydicom.dataset.Dataset
            If the peer timed out, aborted or sent an invalid response then
            yields an empty :class:`~pydicom.dataset.Dataset`. If a response
            was received from the peer then yields a
            :class:`~pydicom.dataset.Dataset` containing at least a (0000,0900)
            *Status* element, and depending on the returned value, may
            optionally contain additional elements (see the DICOM Standard,
            Part 7, :dcm:`Section 9.1.2.1.6
            <part07/chapter_9.html#sect_9.1.2.1.6>` and
            :dcm:`Annex C<part07/chapter_C.html>`).

            The status for the requested C-FIND operation should be one of the
            following values, but as the value depends
            on the peer this can't be assumed:

            *General C-FIND* (Part 7, Section 9.1.2.1.6 and Annex C)

            Cancel
              | ``0xFE00`` - Matching terminated due to Cancel request

            Success
              | ``0x0000`` - Matching is complete: no final Identifier is
                supplied

            Failure
              | ``0x0122`` - SOP class not supported

            *Query/Retrieve Service, Basic Worklist Management Service,
            Hanging Protocol Query/Retrieve Service, Defined Procedure Protocol
            Query/Retrieve Service, Substance Administration Query Service,
            Color Palette Query/Retrieve Service*, *Implant Template
            Query/Retrieve Service*, *Inventory Query/Retrieve Service*,
            *Protocol Approval Query/Retrieve Service* and *Unified Protocol
            Step Service* specific (DICOM Standard, Part 4, Annexes C.4.1,
            K.4.1.1.4, U.4.1, HH, V.4.1.1.4, X, BB, II, JJ and CC):

            Failure
              | ``0xA700`` - Out of resources
              | ``0xA900`` - Identifier does not match SOP Class
              | ``0xC000`` to ``0xCFFF`` - Unable to process

            Pending
              | ``0xFF00`` - Matches are continuing: current match is supplied
                and any Optional Keys were supported in the same manner as
                Required Keys
              | ``0xFF01`` - Matches are continuing: warning that one or more
                Optional Keys were not supported for existence and/or matching
                for this Identifier)

            *Query/Retrieve Service - Repository Query* specific (DICOM Standard,
            Part 5, Annex C.6.4):

            Warning
              | ``0xB001`` - Matching reached response limit, subsequent
                request may return additional matches

            Failure
              | ``0xA710`` - Invalid prior record key

            *Relevant Patient Information Query Service* specific (DICOM
            Standard Part 4, Annex Q.2.1.1.4):

            Failure
              | ``0xA700`` - Out of resources
              | ``0xA900`` - Identifier does not match SOP Class
              | ``0xC000`` - Unable to process
              | ``0xC100`` - More than one match found
              | ``0xC200`` - Unable to support requested template

            Pending
              | ``0xFF00`` - Matches are continuing: current match is supplied
                and any Optional Keys were supported in the same manner as
                Required Keys

        identifier : pydicom.dataset.Dataset or None
            If the status category is 'Pending' then the C-FIND response's
            *Identifier* :class:`~pydicom.dataset.Dataset` If the status
            category is not 'Pending' this will be ``None``. The exact contents
            of the response *Identifier* are Service Class specific (see the
            DICOM Standard, :dcm:`Part 4<part04.html>`).

        Raises
        ------
        RuntimeError
            If ``send_c_find`` is called with no established association.
        ValueError
            If no accepted Presentation Context for `query_model` exists or if
            unable to encode the *Identifier* `dataset`.

        See Also
        --------

        :class:`~pynetdicom.dimse_primitives.C_FIND`
        :class:`~pynetdicom.service_class.BasicWorklistManagementServiceClass`
        :class:`~pynetdicom.service_class.ColorPaletteQueryRetrieveServiceClass`
        :class:`~pynetdicom.service_class.DefinedProcedureProtocolQueryRetrieveServiceClass`
        :class:`~pynetdicom.service_class.HangingProtocolQueryRetrieveServiceClass`
        :class:`~pynetdicom.service_class.ImplantTemplateQueryRetrieveServiceClass`
        :class:`~pynetdicom.service_class.InventoryQueryRetrieveServiceClass`
        :class:`~pynetdicom.service_class.ProtocolApprovalQueryRetrieveServiceClass`
        :class:`~pynetdicom.service_class.QueryRetrieveServiceClass`
        :class:`~pynetdicom.service_class.RelevantPatientInformationQueryServiceClass`
        :class:`~pynetdicom.service_class.SubstanceAdministrationQueryServiceClass`
        :class:`~pynetdicom.service_class_n.UnifiedProcedureStepServiceClass`

        References
        ----------

        * DICOM Standard, Part 4, :dcm:`Annex C<part04/chapter_C.html>`
        * DICOM Standard, Part 4, :dcm:`Annex K<part04/chapter_K.html>`
        * DICOM Standard, Part 4, :dcm:`Annex Q<part04/chapter_Q.html>`
        * DICOM Standard, Part 4, :dcm:`Annex U<part04/chapter_U.html>`
        * DICOM Standard, Part 4, :dcm:`Annex V<part04/chapter_V.html>`
        * DICOM Standard, Part 4, :dcm:`Annex X<part04/chapter_X.html>`
        * DICOM Standard, Part 4, :dcm:`Annex BB<part04/chapter_BB.html>`
        * DICOM Standard, Part 4, :dcm:`Annex CC<part04/chapter_CC.html>`
        * DICOM Standard, Part 4, :dcm:`Annex HH<part04/chapter_HH.html>`
        * DICOM Standard, Part 4, :dcm:`Annex II<part04/chapter_II.html>`
        * DICOM Standard, Part 4, :dcm:`Annex JJ<part04/chapter_JJ.html>`
        * DICOM Standard, Part 7, Sections
          :dcm:`9.1.2<part07/chapter_9.html#sect_9.1.2>`,
          :dcm:`9.3.2<part07/sect_9.3.2.html>` and
          :dcm:`Annex C<part07/chapter_C.html>`
        """
        # Can't send a C-FIND without an Association
        if not self.is_established:
            raise RuntimeError(
                "The association with a peer SCP must be established before "
                "sending a C-FIND request"
            )

        # Determine the Presentation Context we are operating under
        #   and hence the transfer syntax to use for encoding `dataset`
        context = self._get_valid_context(query_model, "", "scu")
        if context.abstract_syntax != query_model:
            LOGGER.info("Using Presentation Context:")
            LOGGER.info(f"  Context ID:        {context.context_id}")
            LOGGER.info(
                "  Abstract Syntax:   =" f"{cast(UID, context.abstract_syntax).name}"
            )

        query_model = UID(query_model)

        # Build C-FIND request primitive
        #   (M) Message ID
        #   (M) Affected SOP Class UID
        #   (M) Priority
        #   (M) Identifier
        req = C_FIND()
        req.MessageID = msg_id
        req.AffectedSOPClassUID = query_model
        req.Priority = priority

        # Encode the Identifier `dataset` using the agreed transfer syntax
        #   Will return None if failed to encode
        transfer_syntax = context.transfer_syntax[0]
        bytestream = encode(
            dataset,
            transfer_syntax.is_implicit_VR,
            transfer_syntax.is_little_endian,
            transfer_syntax.is_deflated,
        )

        if bytestream is not None:
            req.Identifier = BytesIO(bytestream)
        else:
            LOGGER.error("Failed to encode the supplied Dataset")
            raise ValueError("Failed to encode the supplied Dataset")

        LOGGER.info(f"Sending Find Request: MsgID {msg_id}")
        LOGGER.info("")
        if _config.LOG_REQUEST_IDENTIFIERS:
            LOGGER.info("# Request Identifier")
            for line in pretty_dataset(dataset):
                LOGGER.info(line)

            LOGGER.info("")

        # Pause the reactor to prevent a race condition
        self._reactor_checkpoint.clear()
        while not self._is_paused:
            time.sleep(0.0001)

        # Send C-FIND request to the peer via DIMSE
        self.dimse.send_msg(req, cast(int, context.context_id))

        # Get the responses from the peer
        # Wrap the generator so the C-FIND-RQ is sent immediately on
        #   executing this function, otherwise sending C-CANCEL requests
        #   may end up being sent first unless next() is called
        return self._wrap_find_responses(transfer_syntax, query_model)

    def send_c_get(
        self,
        dataset: Dataset,
        query_model: str | UID,
        msg_id: int = 1,
        priority: int = 2,
    ) -> Iterator[tuple[Dataset, Dataset | None]]:
        """Send a C-GET request to the peer AE.

        Yields (*status*, *identifier*) pairs for each response from the peer.

        A :meth:`C-STORE handler<pynetdicom._handlers.doc_handle_store>`
        should be implemented and bound to ``evt.EVT_C_STORE``
        prior to calling :meth:`send_c_get` as the peer will return any matches
        via a C-STORE sub-operation over the current association. In addition,
        :ref:`SCP/SCU Role Selection Negotiation <user_ae_role_negotiation>`
        must be supported by the :class:`Association`.

        Parameters
        ----------
        dataset : pydicom.dataset.Dataset
            The C-GET request's *Identifier* dataset. The exact
            requirements for the *Identifier* are Service Class specific (see
            the DICOM Standard, :dcm:`Part 4<part04/PS3.4.html>`).
        query_model : pydicom.uid.UID or str
            The value to use for the C-GET request's (0000,0002) *Affected
            SOP Class UID* parameter, which usually corresponds to the
            Information Model that is to be used.
        msg_id : int, optional
            The C-GET request's *Message ID*, must be between 0 and 65535,
            inclusive, (default ``1``).
        priority : int, optional
            The value of the C-GET request's *Priority* parameter (may not be
            supported by the peer), one of:

            - ``0`` - Medium
            - ``1`` - High
            - ``2`` - Low (default)

        Yields
        ------
        status : pydicom.dataset.Dataset
            If the peer timed out, aborted or sent an invalid response then
            yields an empty :class:`~pydicom.dataset.Dataset`. If a response
            was received from the peer then yields a
            :class:`~pydicom.dataset.Dataset` containing at least a (0000,0900)
            *Status* element, and depending on the returned value may
            optionally contain additional elements (see the DICOM Standard,
            Part 7, :dcm:`Section 9.1.3.1.6
            <part07/chapter_9.html#sect_9.1.3.1.6>` and
            :dcm:`Annex C<part07/chapter_C.html>`).

            The status for the requested C-GET operation should be one of the
            following values, but as the value depends on the peer this
            can't be assumed:

            *General C-GET* (DICOM Standard, Part 7, Section 9.1.3 and Annex C)

            Success
              | ``0x0000`` - Sub-operations complete: no failures or warnings

            Failure
              | ``0x0122`` - SOP class not supported
              | ``0x0124`` - Not authorised
              | ``0x0210`` - Duplicate invocation
              | ``0x0211`` - Unrecognised operation
              | ``0x0212`` - Mistyped argument

            *Query/Retrieve Service, Hanging Protocol Query/Retrieve Service,
            Defined Procedure Protocol Query/Retrieve Service, Color Palette
            Query/Retrieve Service*, *Implant Template Query/Retrieve
            Service*, *Inventory Query/Retrieve Service* and *Protocol Approval
            Query/Retrieve Service* specific (DICOM Standard, Part 4, Annexes
            C.4.3, Y.C.4.2.1.4, Z.4.2.1.4, U.4.3, X, BB, HH, II and JJ):

            Pending
              | ``0xFF00`` - Sub-operations are continuing

            Cancel
              | ``0xFE00`` - Sub-operations terminated due to Cancel indication

            Failure
              | ``0xA701`` - Out of resources: unable to calculate number of
                 matches
              | ``0xA702`` - Out of resources: unable to perform sub-operations
              | ``0xA900`` - Identifier does not match SOP class
              | ``0xAA00`` - None of the frames requested were found in the SOP
                instance
              | ``0xAA01`` - Unable to create new object for this SOP class
              | ``0xAA02`` - Unable to extract frames
              | ``0xAA03`` - Time-based request received for a non-time-based
                original SOP Instance
              | ``0xAA04`` - Invalid request
              | ``0xC000`` to ``0xCFFF`` - Unable to process

            Warning
              | ``0xB000`` - Sub-operations completed: one or more failures or
                 warnings

        identifier : pydicom.dataset.Dataset or None
            If the status category is 'Pending' or 'Success' then yields
            ``None``. If the status category is 'Warning', 'Failure' or
            'Cancel' then yields a :class:`~pydicom.dataset.Dataset` which
            should contain an (0008,0058) *Failed SOP Instance UID List*
            element, however as this comes from the peer this is not guaranteed
            and may instead be an empty :class:`~pydicom.dataset.Dataset`.

        Raises
        ------
        RuntimeError
            If :meth:`send_c_get` is called with no established association.
        ValueError
            If no accepted Presentation Context for `query_model` exists or if
            unable to encode the *Identifier* `dataset`.

        See Also
        --------

        :class:`~pynetdicom.dimse_primitives.C_GET`
        :class:`~pynetdicom.service_class.QueryRetrieveServiceClass`
        :class:`~pynetdicom.service_class.HangingProtocolQueryRetrieveServiceClass`
        :class:`~pynetdicom.service_class.DefinedProcedureProtocolQueryRetrieveServiceClass`
        :class:`~pynetdicom.service_class.ColorPaletteQueryRetrieveServiceClass`
        :class:`~pynetdicom.service_class.ImplantTemplateQueryRetrieveServiceClass`
        :class:`~pynetdicom.service_class.InventoryQueryRetrieveServiceClass`
        :class:`~pynetdicom.service_class.ProtocolApprovalQueryRetrieveServiceClass`

        References
        ----------

        * DICOM Standard, Part 4, :dcm:`Annex C<part04/chapter_C.html>`
        * DICOM Standard, Part 4, :dcm:`Annex U<part04/chapter_U.html>`
        * DICOM Standard, Part 4, :dcm:`Annex X<part04/chapter_X.html>`
        * DICOM Standard, Part 4, :dcm:`Annex Y<part04/chapter_Y.html>`
        * DICOM Standard, Part 4, :dcm:`Annex Z<part04/chapter_Z.html>`
        * DICOM Standard, Part 4, :dcm:`Annex BB<part04/chapter_BB.html>`
        * DICOM Standard, Part 4, :dcm:`Annex HH<part04/chapter_HH.html>`
        * DICOM Standard, Part 4, :dcm:`Annex II<part04/chapter_II.html>`
        * DICOM Standard, Part 4, :dcm:`Annex JJ<part04/chapter_JJ.html>`
        * DICOM Standard, Part 7, Sections
          :dcm:`9.1.3<part07/chapter_9.html#sect_9.1.3>`,
          :dcm:`9.3.3<part07/sect_9.3.3.html>` and
          :dcm:`Annex C<part07/chapter_C.html>`
        """
        # Can't send a C-GET without an Association
        if not self.is_established:
            raise RuntimeError(
                "The association with a peer SCP must be established before "
                "sending a C-GET request"
            )

        # Determine the Presentation Context we are operating under
        #   and hence the transfer syntax to use for encoding `dataset`
        context = self._get_valid_context(query_model, "", "scu")

        # Build C-GET request primitive
        #   (M) Message ID
        #   (M) Affected SOP Class UID
        #   (M) Priority
        #   (M) Identifier
        req = C_GET()
        req.MessageID = msg_id
        req.AffectedSOPClassUID = UID(query_model)
        req.Priority = priority

        # Encode the Identifier `dataset` using the agreed transfer syntax
        #   Will return None if failed to encode
        transfer_syntax = context.transfer_syntax[0]
        bytestream = encode(
            dataset,
            transfer_syntax.is_implicit_VR,
            transfer_syntax.is_little_endian,
            transfer_syntax.is_deflated,
        )

        if bytestream is not None:
            req.Identifier = BytesIO(bytestream)
        else:
            LOGGER.error("Failed to encode the supplied Identifier dataset")
            raise ValueError("Failed to encode the supplied Identifier dataset")

        LOGGER.info(f"Sending Get Request: MsgID {msg_id}")
        LOGGER.info("")
        if _config.LOG_REQUEST_IDENTIFIERS:
            LOGGER.info("# Request Identifier")
            for line in pretty_dataset(dataset):
                LOGGER.info(line)

            LOGGER.info("")

        # Pause the reactor to prevent a race condition
        self._reactor_checkpoint.clear()
        while not self._is_paused:
            time.sleep(0.0001)

        # Send C-GET request to the peer via DIMSE
        self.dimse.send_msg(req, cast(int, context.context_id))

        # Get the responses from the peer
        # Wrap the generator so the C-GET-RQ is sent immediately on
        #   executing this function, otherwise sending C-CANCEL requests
        #   may end up being sent first unless next() is called
        return self._wrap_get_move_responses(transfer_syntax)

    def send_c_move(
        self,
        dataset: Dataset,
        move_aet: str,
        query_model: str | UID,
        msg_id: int = 1,
        priority: int = 2,
    ) -> Iterator[tuple[Dataset, Dataset | None]]:
        """Send a C-MOVE request to the peer AE.

        Yields (*status*, *identifier*) pairs for each response from the peer.

        The peer will attempt to start a new association with an Storage SCP
        with AE title `move_aet` and hence the Storage SCP must be known to
        the Move SCP. Once the association has been established, the peer will
        use the C-STORE service to send any matching datasets to the nominated
        Storage SCP.

        .. versionchanged:: 2.0

            `move_aet` should be :class:`str`

        Parameters
        ----------
        dataset : pydicom.dataset.Dataset
            The C-MOVE request's *Identifier* dataset. The exact
            requirements for the *Identifier* are Service Class specific (see
            the DICOM Standard, :dcm:`Part 4<part04/PS3.4.html>`).
        move_aet : str
            The value of the *Move Destination* parameter for the C-MOVE
            request, should be the AE title of the Storage SCP for the
            C-STORE sub-operations performed by the peer.
        query_model : pydicom.uid.UID or str
            The value to use for the C-MOVE request's (0000,0002) *Affected
            SOP Class UID* parameter, which usually corresponds to the
            Information Model that is to be used when querying.
        msg_id : int, optional
            The C-MOVE request's *Message ID*, must be between 0 and 65535,
            inclusive, (default ``1``).
        priority : int, optional
            The value of the C-MOVE request's *Priority* parameter (may not be
            supported by the peer), one of:

            - ``0`` - Medium
            - ``1`` - High
            - ``2`` - Low (default)

        Yields
        ------
        status : pydicom.dataset.Dataset
            If the peer timed out, aborted or sent an invalid response then
            yields an empty :class:`~pydicom.dataset.Dataset`. If a response
            was received from the peer then yields a
            :class:`~pydicom.dataset.Dataset` containing at least a (0000,0900)
            *Status* element, and depending on the returned value, may
            optionally contain additional elements (see the DICOM Standard,
            Part 7, :dcm:`Section 9.1.4.1.7
            <part07/chapter_9.html#sect_9.1.4.1.7>` and
            :dcm:`Annex C<part07/chapter_C.html>`).

            The status for the requested C-MOVE operation should be one of the
            following values, but as the value depends
            on the peer this can't be assumed:

            *General C-MOVE* (DICOM Standard, Part 7, 9.1.4.1.7 and Annex C)

            Cancel
              | ``0xFE00`` - Sub-operations terminated due to Cancel indication

            Success
              | ``0x0000`` - Sub-operations complete: no failures

            Failure
              | ``0x0122`` - SOP class not supported

            *Query/Retrieve Service, Hanging Protocol Query/Retrieve Service,
            Defined Procedure Protocol Query/Retrieve Service, Color Palette
            Query/Retrieve Service* , *Implant Template Query/Retrieve
            Service*, *Inventory Query/Retrieve Service* and *Protocol Approval
            Query/Retrieve Service* specific (DICOM Standard, Part 4, Annexes
            C, U, Y, X, BB, HH and JJ):

            Failure
              | ``0xA701`` - Out of resources: unable to calculate number of
                matches
              | ``0xA702`` - Out of resources: unable to perform sub-operations
              | ``0xA801`` - Move destination unknown
              | ``0xA900`` - Identifier does not match SOP Class
              | ``0xAA00`` - None of the frames requested were found in the SOP
                instance
              | ``0xAA01`` - Unable to create new object for this SOP class
              | ``0xAA02`` - Unable to extract frames
              | ``0xAA03`` - Time-based request received for a non-time-based
                original SOP Instance
              | ``0xAA04`` - Invalid request
              | ``0xC000`` to ``0xCFFF`` - Unable to process

            Pending
              | ``0xFF00`` - Sub-operations are continuing

            Warning
              | ``0xB000`` - Sub-operations complete: one or more failures

        identifier : pydicom.dataset.Dataset or None
            If the status category is 'Pending' or 'Success' then yields
            ``None``. If the status category is 'Warning', 'Failure' or
            'Cancel' then yields a :class:`~pydicom.dataset.Dataset` which
            should contain an (0008,0058) *Failed SOP Instance UID List*
            element, however as this comes from the peer this is not guaranteed
            and may instead be an empty :class:`~pydicom.dataset.Dataset`.

        Raises
        ------
        RuntimeError
            If :meth:`send_c_move` is called with no established association.
        ValueError
            If no accepted Presentation Context for `query_model` exists or if
            unable to encode the `dataset`.

        See Also
        --------

        :class:`~pynetdicom.dimse_primitives.C_MOVE`
        :class:`~pynetdicom.service_class.QueryRetrieveServiceClass`
        :class:`~pynetdicom.service_class.HangingProtocolQueryRetrieveServiceClass`
        :class:`~pynetdicom.service_class.ColorPaletteQueryRetrieveServiceClass`
        :class:`~pynetdicom.service_class.ImplantTemplateQueryRetrieveServiceClass`
        :class:`~pynetdicom.service_class.InventoryQueryRetrieveServiceClass`
        :class:`~pynetdicom.service_class.ProtocolApprovalQueryRetrieveServiceClass`

        References
        ----------

        * DICOM Standard, Part 4, :dcm:`Annex C<part04/chapter_C.html>`
        * DICOM Standard, Part 4, :dcm:`Annex U<part04/chapter_U.html>`
        * DICOM Standard, Part 4, :dcm:`Annex X<part04/chapter_X.html>`
        * DICOM Standard, Part 4, :dcm:`Annex Y<part04/chapter_Y.html>`
        * DICOM Standard, Part 4, :dcm:`Annex BB<part04/chapter_BB.html>`
        * DICOM Standard, Part 4, :dcm:`Annex HH<part04/chapter_HH.html>`
        * DICOM Standard, Part 4, :dcm:`Annex II<part04/chapter_II.html>`
        * DICOM Standard, Part 4, :dcm:`Annex JJ<part04/chapter_JJ.html>`
        * DICOM Standard, Part 7, Sections
          :dcm:`9.1.4<part07/chapter_9.html#sect_9.1.4>`,
          :dcm:`9.3.4<part07/sect_9.3.4.html>` and
          :dcm:`Annex C<part07/chapter_C.html>`
        """
        # Can't send a C-MOVE without an Association
        if not self.is_established:
            raise RuntimeError(
                "The association with a peer SCP must be established before "
                "sending a C-MOVE request"
            )

        # Determine the Presentation Context we are operating under
        #   and hence the transfer syntax to use for encoding `dataset`
        context = self._get_valid_context(query_model, "", "scu")

        # Build C-MOVE request primitive
        #   (M) Message ID
        #   (M) Affected SOP Class UID
        #   (M) Priority
        #   (M) Move Destination
        #   (M) Identifier
        req = C_MOVE()
        req.MessageID = msg_id
        req.AffectedSOPClassUID = UID(query_model)
        req.Priority = priority
        req.MoveDestination = move_aet

        # Encode the Identifier `dataset` using the agreed transfer syntax;
        #   will return None if failed to encode
        transfer_syntax = context.transfer_syntax[0]
        bytestream = encode(
            dataset,
            transfer_syntax.is_implicit_VR,
            transfer_syntax.is_little_endian,
            transfer_syntax.is_deflated,
        )

        if bytestream is not None:
            req.Identifier = BytesIO(bytestream)
        else:
            LOGGER.error("Failed to encode the supplied Identifier dataset")
            raise ValueError("Failed to encode the supplied Identifier dataset")

        LOGGER.info(f"Sending Move Request: MsgID {msg_id}")
        LOGGER.info("")
        if _config.LOG_REQUEST_IDENTIFIERS:
            LOGGER.info("# Request Identifier")
            for line in pretty_dataset(dataset):
                LOGGER.info(line)

            LOGGER.info("")

        # Pause the reactor to prevent a race condition
        self._reactor_checkpoint.clear()
        while not self._is_paused:
            time.sleep(0.0001)

        # Send C-MOVE request to the peer via DIMSE and wait for the response
        self.dimse.send_msg(req, cast(int, context.context_id))

        # Get the responses from the peer
        # Wrap the generator so the C-MOVE-RQ is sent immediately on
        #   executing this function, otherwise sending C-CANCEL requests
        #   may end up being sent first unless next() is called
        return self._wrap_get_move_responses(transfer_syntax)

    def send_c_store(
        self,
        dataset: str | Path | Dataset,
        msg_id: int = 1,
        priority: int = 2,
        originator_aet: str | None = None,
        originator_id: int | None = None,
    ) -> Dataset:
        """Send a C-STORE request to the peer AE.

        .. versionchanged:: 2.0

            * Changed `dataset` parameter to either be a dataset or the path to
              a dataset.
            * `originator_aet` should now be :class:`str`

        Parameters
        ----------
        dataset : pydicom.dataset.Dataset, str or pathlib.Path
            The DICOM dataset to send to the peer or the file path to the
            dataset to be sent. If a file path then the dataset will be read
            and decoded using :func:`~pydicom.filereader.dcmread`.
        msg_id : int, optional
            The C-STORE request's *Message ID*, must be between 0 and 65535,
            inclusive, (default ``1``).
        priority : int, optional
            The value of the C-STORE request's *Priority* parameter (may not be
            supported by the peer), one of:

            - ``0`` - Medium
            - ``1`` - High
            - ``2`` - Low (default)
        originator_aet : str, optional
            The value of the *Move Originator Application Entity Title*
            parameter for the C-STORE request. This is the AE title of the
            peer that invoked the C-MOVE operation for which this C-STORE
            sub-operation is being performed (default ``None``).
        originator_id : int, optional
            The value of the *Move Originator Message ID* parameter for the
            C-STORE request. This is the original *Message ID* parameter value
            for the C-MOVE request primitive for which the C-STORE
            sub-operation is being performed (default ``None``).

        Returns
        -------
        status : pydicom.dataset.Dataset
            If the peer timed out, aborted or sent an invalid response then
            returns an empty :class:`~pydicom.dataset.Dataset`. If a valid
            response was received from the peer then returns a
            :class:`~pydicom.dataset.Dataset` containing at least a
            (0000,0900) *Status* element, and, depending on the returned
            value, may optionally contain additional elements (see DICOM
            Standard, Part 7, :dcm:`Annex C<part07/chapter_C.html>`).

            The status for the requested C-STORE operation should be one of the
            following, but as the value depends on the peer SCP this can't be
            assumed:

            *General C-STORE* (DICOM Standard, Part 7, 9.1.1.1.9 and Annex C):

            Success
              | ``0x0000`` - Success

            Failure
              | ``0x0117`` - Invalid SOP instance
              | ``0x0122`` - SOP class not supported
              | ``0x0124`` - Not authorised
              | ``0x0210`` - Duplicate invocation
              | ``0x0211`` - Unrecognised operation
              | ``0x0212`` - Mistyped argument

            *Storage Service* and *Non-Patient Object Storage Service* specific
            (DICOM Standard, Part 4, Annexes B.2.3 and GG):

            Failure
              | ``0xA700`` to ``0xA7FF`` - Out of resources
              | ``0xA900`` to ``0xA9FF`` - Data set does not match SOP class
              | ``0xC000`` to ``0xCFFF`` - Cannot understand

            Warning
              | ``0xB000`` - Coercion of data elements
              | ``0xB006`` - Element discarded
              | ``0xB007`` - Data set does not match SOP class

            *Non-Patient Object Service Class* specific (DICOM Standard, Part
            4, Annex GG.4.2)

            Failure
              | ``0xA700`` - Out of resources
              | ``0xA900`` - Data set does not match SOP class
              | ``0xC000`` - Cannot understand

        Raises
        ------
        RuntimeError
            If :meth:`send_c_store` is called with no established association.
        AttributeError
            If `dataset` is missing (0008,0016) *SOP Class UID*,
            (0008,0018) *SOP Instance UID* elements or the (0002,0010)
            *Transfer Syntax UID* file meta information element.
        ValueError
            If no accepted Presentation Context for `dataset` exists or if
            unable to encode the `dataset`.

        See Also
        --------

        :class:`~pynetdicom.dimse_primitives.C_STORE`
        :class:`~pynetdicom.service_class.StorageServiceClass`
        :class:`~pynetdicom.service_class.NonPatientObjectStorageServiceClass`
        :attr:`~pynetdicom._config.STORE_SEND_CHUNKED_DATASET`

        References
        ----------

        * DICOM Standard, Part 4, :dcm:`Annex B<part04/chapter_B.html>`
        * DICOM Standard, Part 4, :dcm:`Annex GG<part04/chapter_GG.html>`
        * DICOM Standard, Part 7, Sections
          :dcm:`9.1.1<part07/chapter_9.html#sect_9.1.1>`,
          :dcm:`9.3.1<part07/sect_9.3.html#sect_9.3.1>` and
          :dcm:`Annex C<part07/chapter_C.html>`
        """
        # Can't send a C-STORE without an Association
        if not self.is_established:
            raise RuntimeError(
                "The association with a peer SCP must be established before "
                "sending a C-STORE request"
            )

        # Build C-STORE request primitive
        #   (M) Message ID
        #   (M) Affected SOP Class UID
        #   (M) Affected SOP Instance UID
        #   (M) Priority
        #   (U) Move Originator Application Entity Title
        #   (U) Move Originator Message ID
        #   (M) Data Set
        req = C_STORE()
        req.MessageID = msg_id
        req.Priority = priority
        req.MoveOriginatorApplicationEntityTitle = originator_aet
        req.MoveOriginatorMessageID = originator_id

        allow_conversion = True
        if not isinstance(dataset, Dataset):
            fpath = Path(dataset)
            if not _config.STORE_SEND_CHUNKED_DATASET:
                dataset = dcmread(os.fspath(fpath))
            else:
                dataset = None  # type:ignore[assignment]
                allow_conversion = False
                file_meta, offset = split_dataset(fpath)
                req._dataset_path = (fpath, offset)

                missing = [
                    "MediaStorageSOPClassUID",
                    "MediaStorageSOPInstanceUID",
                    "TransferSyntaxUID",
                ]
                missing = [kw for kw in missing if kw not in file_meta]
                if missing:
                    raise AttributeError(
                        "Unable to send the dataset from the file at "
                        f"{os.fspath(fpath)} as one or more required file "
                        "meta information elements are missing: "
                        f"{', '.join(missing)}"
                    )

                sop_class = cast(UID, file_meta.MediaStorageSOPClassUID)
                sop_instance = cast(UID, file_meta.MediaStorageSOPInstanceUID)
                tsyntax = cast(UID, file_meta.TransferSyntaxUID)

        if dataset:
            dataset = cast(Dataset, dataset)
            missing = ["SOPClassUID", "SOPInstanceUID"]
            missing = [kw for kw in missing if kw not in dataset]
            if missing:
                raise AttributeError(
                    "Unable to send the dataset as one or more required "
                    f"element are missing: {', '.join(missing)}"
                )

            sop_class = cast(UID, dataset.SOPClassUID)
            sop_instance = cast(UID, dataset.SOPInstanceUID)

            try:
                tsyntax = dataset.file_meta.TransferSyntaxUID
            except (AssertionError, AttributeError):
                raise AttributeError(
                    "Unable to determine the presentation context to use with "
                    "`dataset` as it contains no '(0002,0010) Transfer Syntax "
                    "UID' file meta information element"
                )

            ts_encoding: tuple[bool, bool] = (
                tsyntax.is_implicit_VR,
                tsyntax.is_little_endian,
            )
            # `dataset` might also be created from scratch
            ds_encoding: tuple[bool | None, bool | None] = (
                (
                    dataset.is_implicit_VR
                    if dataset.original_encoding[0] is None
                    else dataset.original_encoding[0]
                ),
                (
                    dataset.is_little_endian
                    if dataset.original_encoding[1] is None
                    else dataset.original_encoding[1]
                ),
            )
            if None not in ds_encoding and ts_encoding != ds_encoding:
                s = ("explicit VR", "implicit VR")[cast(bool, ds_encoding[0])]
                s += (" big endian", " little endian")[cast(bool, ds_encoding[1])]
                msg = (
                    f"'dataset' is encoded as {s} but the file meta has a "
                    f"(0002,0010) Transfer Syntax UID of '{tsyntax.name}'"
                )
                if ds_encoding == (True, True):
                    LOGGER.warning(f"{msg} - using 'Implicit VR Little Endian' instead")
                    tsyntax = ImplicitVRLittleEndian
                elif ds_encoding == (False, False):
                    LOGGER.warning(f"{msg} - using 'Explicit VR Big Endian' instead")
                    tsyntax = ExplicitVRBigEndian
                else:
                    raise AttributeError(
                        f"{msg} - please set an appropriate Transfer Syntax"
                    )

        # Get a Presentation Context to use for sending the message
        context = self._get_valid_context(
            sop_class, tsyntax, "scu", allow_conversion=allow_conversion
        )
        transfer_syntax = context.transfer_syntax[0]

        req.AffectedSOPClassUID = sop_class
        req.AffectedSOPInstanceUID = sop_instance

        # Encode the `dataset` using the agreed transfer syntax
        #   Will return None if failed to encode
        if dataset:
            bytestream = encode(
                cast(Dataset, dataset),
                transfer_syntax.is_implicit_VR,
                transfer_syntax.is_little_endian,
                transfer_syntax.is_deflated,
            )

            if bytestream is not None:
                req.DataSet = BytesIO(bytestream)
            else:
                LOGGER.error("Failed to encode the supplied dataset")
                raise ValueError("Failed to encode the supplied dataset")

        # Pause the reactor to prevent a race condition
        self._reactor_checkpoint.clear()
        while not self._is_paused:
            time.sleep(0.0001)

        # Send C-STORE request to the peer via DIMSE and wait for the response
        self.dimse.send_msg(req, cast(int, context.context_id))
        cx_id, rsp = self.dimse.get_msg(block=True)

        # Unpause the reactor
        self._reactor_checkpoint.set()

        # If `rsp` is None then the DIMSE timeout expired so abort
        if rsp is None:
            self._handle_no_response()
            return Dataset()

        # Determine validity of the response and get the status
        status = self._check_received_status(rsp)

        return status

    def _wrap_find_responses(
        self,
        transfer_syntax: UID,
        query_model: UID,
    ) -> Iterator[tuple[Dataset, None | Dataset]]:
        """Wrapper for the C-FIND response generator.

        Wrapping the response generators allows us to immediately send the
        service request on calling the ``send_c_find()`` function. This is
        important when it comes to reliably sending C-CANCEL requests
        because otherwise the C-CANCEL may end up being sent prior to the
        C-FIND request.

        Parameters
        ----------
        transfer_syntax : pydicom.uid.UID
            The transfer syntax UID used to encode the responses.
        query_model : pydicom.uid.UID
            The value to use for the C-FIND request's (0000,0002) *Affected
            SOP Class UID* parameter, which usually corresponds to the
            Information Model that is to be used.

        Yields
        ------
        See ``send_c_find()``.
        """
        operation_no = 1
        while True:
            # Wait for DIMSE message
            cx_id, rsp = self.dimse.get_msg(block=True)

            # If `rsp` is None then the DIMSE timeout expired
            #   so abort if the association hasn't already been aborted
            if rsp is None:
                self._handle_no_response()
                self._reactor_checkpoint.set()
                yield Dataset(), None
                return

            if not isinstance(rsp, C_FIND):
                msg_type = rsp.__class__.__name__.replace("_", "-")
                LOGGER.error(f"Received an unexpected {msg_type} message from the peer")
                self.abort()
                self._reactor_checkpoint.set()
                yield Dataset(), None
                return

            if not rsp.is_valid_response:
                LOGGER.error("Received an invalid C-FIND response from the peer")
                self.abort()
                self._reactor_checkpoint.set()
                yield Dataset(), None
                return

            # Status may be 'Failure', 'Cancel', 'Warning', 'Success'
            #   or 'Pending'
            status = Dataset()
            status.Status = rsp.Status
            # Add optional status related elements
            for keyword in rsp.STATUS_OPTIONAL_KEYWORDS:
                if getattr(rsp, keyword) is not None:
                    setattr(status, keyword, getattr(rsp, keyword))

            # If the Status is 'Pending' then the processing of
            #   matches and sub-operations is initiated or continuing
            # If the Status is 'Cancel', 'Failure', 'Warning' or 'Success'
            #   then we are finished
            category = code_to_category(cast(int, status.Status))

            LOGGER.debug("")
            if query_model == RepositoryQuery and status.Status == 0xB001:
                # PS3.4, Annex C.6.4.4
                # 0xB001 conveys end of Pending responses
                LOGGER.info(
                    f"Find SCP Response: {operation_no} - "
                    "0xB001 (Warning - Matching reached response limit, "
                    "subsequent request may return additional matches)"
                )
                yield status, None
                continue

            if category == STATUS_PENDING:
                LOGGER.info(
                    f"Find SCP Response: {operation_no} - "
                    f"0x{status.Status:04X} (Pending)"
                )
            else:
                LOGGER.info(f"Find SCP Result: 0x{status.Status:04X} ({category})")

            # 'Success', 'Warning', 'Failure', 'Cancel' are final yields,
            #   'Pending' means more to come
            identifier = None
            if category == STATUS_PENDING:
                operation_no += 1

                with self.lock:
                    try:
                        identifier = decode(
                            cast(BytesIO, rsp.Identifier),
                            transfer_syntax.is_implicit_VR,
                            transfer_syntax.is_little_endian,
                            transfer_syntax.is_deflated,
                        )
                        if identifier and _config.LOG_RESPONSE_IDENTIFIERS:
                            LOGGER.info("")
                            LOGGER.info("# Response Identifier")
                            for line in pretty_dataset(identifier):
                                LOGGER.info(line)
                            LOGGER.info("")
                    except Exception as exc:
                        LOGGER.error("Failed to decode the received Identifier dataset")
                        LOGGER.exception(exc)
                        yield status, None

                yield status, identifier
                continue

            # Only reach this point if status is Success, Warning, Failure
            #   or Cancel
            self._reactor_checkpoint.set()
            yield status, identifier
            break

        # Unpause the reactor
        self._reactor_checkpoint.set()

    def _wrap_get_move_responses(
        self, transfer_syntax: UID
    ) -> Iterator[tuple[Dataset, Dataset | None]]:
        """Wrapper for the C-GET/C-MOVE response generators.

        Wrapping the response generators allows us to immediately send the
        service request on calling the respective ``send_c_*()`` function.
        This is important when it comes to reliably sending C-CANCEL requests
        because otherwise the C-CANCEL may end up being sent prior to the
        C-GET/MOVE request.

        Parameters
        ----------
        transfer_syntax : pydicom.uid.UID
            The transfer syntax UID used to encode the responses.

        Yields
        ------
        See ``send_c_get()`` and ``send_c_move()``.
        """
        operation_no = 1
        while True:
            # Wait for DIMSE message, should be either a C-GET or
            #   C-MOVE response or a C-STORE request
            cx_id, rsp = self.dimse.get_msg(block=True)
            # Used to describe the response in the log output
            rsp_type = rsp.__class__.__name__.replace("_", "-")
            rsp_name = {"C-GET": "Get", "C-MOVE": "Move"}

            # If `rsp` is None then the DIMSE timeout expired
            #   so abort if the association hasn"t already been aborted
            if rsp is None:
                self._handle_no_response()
                self._reactor_checkpoint.set()
                yield Dataset(), None
                return

            if not isinstance(rsp, (C_STORE, C_GET, C_MOVE)):
                LOGGER.error(f"Received an unexpected {rsp_type} message from the peer")
                self.abort()
                self._reactor_checkpoint.set()
                yield Dataset(), None
                return

            if isinstance(rsp, C_STORE):
                # Received a C-STORE request from the peer
                # Should occur during C-GET and may occur during C-MOVE
                self._c_store_scp(rsp)
                continue

            if not rsp.is_valid_response:
                LOGGER.error(f"Received an invalid {rsp_type} response from the peer")
                self.abort()
                self._reactor_checkpoint.set()
                yield Dataset(), None
                return

            # Status may be 'Failure', 'Cancel', 'Warning', 'Success'
            #   or 'Pending'
            status = Dataset()
            status.Status = rsp.Status
            # Add optional status related elements
            for keyword in rsp.STATUS_OPTIONAL_KEYWORDS:
                if getattr(rsp, keyword) is not None:
                    setattr(status, keyword, getattr(rsp, keyword))

            # If the Status is 'Pending' then the processing of
            #   matches and sub-operations is initiated or continuing
            # If the Status is 'Cancel', 'Failure', 'Warning' or 'Success'
            #   then we are finished
            category = code_to_category(cast(int, status.Status))

            LOGGER.debug("")
            if category == STATUS_PENDING:
                LOGGER.info(
                    f"{rsp_name[rsp_type]} SCP Response: {operation_no} - "
                    f"0x{status.Status:04X} (Pending)"
                )
            else:
                LOGGER.info(
                    f"{rsp_name[rsp_type]} SCP Result: "
                    f"0x{status.Status:04X} ({category})"
                )

            # Log number of remaining sub-operations - C-GET/C-MOVE only
            LOGGER.info(
                "Sub-Operations Remaining: %s, Completed: %s, "
                "Failed: %s, Warning: %s",
                rsp.NumberOfRemainingSuboperations or "0",
                rsp.NumberOfCompletedSuboperations or "0",
                rsp.NumberOfFailedSuboperations or "0",
                rsp.NumberOfWarningSuboperations or "0",
            )

            # 'Success', 'Warning', 'Failure', 'Cancel' are final yields,
            #   'Pending' means more to come
            identifier = None
            if category in [STATUS_PENDING]:
                operation_no += 1
                yield status, identifier
                continue

            if rsp.Identifier and category in [
                STATUS_CANCEL,
                STATUS_WARNING,
                STATUS_FAILURE,
            ]:
                # From Part 4, Annex C.4.3, responses with these
                #   statuses should contain an Identifier dataset
                #   with a (0008,0058) Failed SOP Instance UID List
                #    element however this can't be assumed
                # pylint: disable=broad-except
                with self.lock:
                    try:
                        identifier = decode(
                            rsp.Identifier,
                            transfer_syntax.is_implicit_VR,
                            transfer_syntax.is_little_endian,
                            transfer_syntax.is_deflated,
                        )
                        if identifier and _config.LOG_RESPONSE_IDENTIFIERS:
                            LOGGER.info("")
                            LOGGER.info("# Response Identifier")
                            for elem in identifier:
                                LOGGER.info(elem)
                            LOGGER.info("")
                    except Exception as exc:
                        LOGGER.error("Failed to decode the received Identifier dataset")
                        LOGGER.exception(exc)
                        identifier = None

            # Only reach this point if status is Success, Warning, Failure
            #   or Cancel
            self._reactor_checkpoint.set()
            yield status, identifier
            break

        # Unpause the reactor
        self._reactor_checkpoint.set()

    # DIMSE-N services provided by the Association
    def send_n_action(
        self,
        dataset: Dataset,
        action_type: int,
        class_uid: str | UID,
        instance_uid: str | UID,
        msg_id: int = 1,
        meta_uid: str | UID | None = None,
    ) -> tuple[Dataset, Dataset | None]:
        """Send an N-ACTION request to the peer AE.

        Parameters
        ----------
        dataset : pydicom.dataset.Dataset or None
            The dataset that will be sent as the *Action Information*
            parameter in the request, or ``None`` if not required.
        action_type : int
            The value of the request's (0000,1008) *Action Type ID*
            parameter.
        class_uid : pydicom.uid.UID
            The UID to be sent for the request's (0000,0003)
            *Requested SOP Class UID* parameter.
        instance_uid : pydicom.uid.UID
            The UID to be sent for the request's (0000,1001)
            *Requested SOP Instance UID* parameter.
        msg_id : int, optional
            The request's *Message ID* parameter value, must be
            between 0 and 65535, inclusive, (default ``1``).
        meta_uid : pydicom.uid.UID, optional
            If the service class operates under a presentation context
            negotiated using a *Meta SOP Class* rather than a standard *SOP
            Class* (such as with *Print Management* service class and its
            *Basic Grayscale Print Management Meta SOP Class*) then this
            value will be used to determine the corresponding presentation
            context.

        Returns
        -------
        status : pydicom.dataset.Dataset
            If the peer timed out, aborted or sent an invalid response then
            returns an empty :class:`~pydicom.dataset.Dataset`. If a response
            was received from the peer then returns a
            :class:`~pydicom.dataset.Dataset` containing at least a (0000,0900)
            *Status* element, and depending on the returned value, may
            optionally contain additional elements (see the DICOM Standard,
            Part 7, :dcm:`Section 10.1.4.1.10
            <part07/chapter_10.html#sect_10.1.4.1.10>` and
            :dcm:`Annex C<part07/chapter_C.html>`).

            *General N-ACTION* (DICOM Standard, Part 7, Section 10.1.4 and
            Annex C)

            Success
              | ``0x0000`` - Successful operation

            Failure
              | ``0x0110`` - Processing failure
              | ``0x0112`` - No such SOP Instance
              | ``0x0114`` - No such argument
              | ``0x0115`` - Invalid argument value
              | ``0x0117`` - Invalid object instance
              | ``0x0118`` - No such SOP Class
              | ``0x0119`` - Class-Instance conflict
              | ``0x0123`` - No such action
              | ``0x0124`` - Not authorised
              | ``0x0210`` - Duplicate invocation
              | ``0x0211`` - Unrecognised operation
              | ``0x0212`` - Mistyped argument
              | ``0x0213`` - Resource limitation

            *Storage Management Service* specific (DICOM
            Standard Part 4, Annex KK.2.2.3):

            Warning
              | ``0xB010`` - Attribute list error - One or more of Key
                Attributes are not supported for matching

        action_reply : pydicom.dataset.Dataset or None
            If the status category is 'Success' or 'Warning' then a
            :class:`~pydicom.dataset.Dataset` containing attributes
            corresponding to those supplied in the *Action Reply*. Because
            *Action Reply* is optional the returned
            :class:`~pydicom.dataset.Dataset` may be empty.

            If the status category is 'Failure' or if the peer timed-out,
            aborted, or sent an invalid response then returns ``None``.

        See Also
        --------

        :class:`~pynetdicom.dimse_primitives.N_ACTION`
        :class:`~pynetdicom.service_class_n.ApplicationEventLoggingServiceClass`
        :class:`~pynetdicom.service_class_n.MediaCreationManagementServiceClass`
        :class:`~pynetdicom.service_class_n.PrintManagementServiceClass`
        :class:`~pynetdicom.service_class_n.RTMachineVerificationServiceClass`
        :class:`~pynetdicom.service_class_n.StorageCommitmentServiceClass`
        :class:`~pynetdicom.service_class_n.StorageManagementServiceClass`
        :class:`~pynetdicom.service_class_n.UnifiedProcedureStepServiceClass`

        References
        ----------

        * DICOM Standard, Part 4, :dcm:`Annex H<part04/chapter_H.html>`
        * DICOM Standard, Part 4, :dcm:`Annex J<part04/chapter_J.html>`
        * DICOM Standard, Part 4, :dcm:`Annex P<part04/chapter_P.html>`
        * DICOM Standard, Part 4, :dcm:`Annex S<part04/chapter_S.html>`
        * DICOM Standard, Part 4, :dcm:`Annex CC<part04/chapter_CC.html>`
        * DICOM Standard, Part 4, :dcm:`Annex DD<part04/chapter_DD.html>`
        * DICOM Standard, Part 4, :dcm:`Annex KK<part04/chapter_KK.html>`
        * DICOM Standard, Part 7, Sections
          :dcm:`10.1.4<part07/chapter_10.html#sect_10.1.4>`,
          :dcm:`10.3.4<part07/sect_10.3.4.html>` and
          :dcm:`Annex C<part07/chapter_C.html>`
        """
        # Can't send an N-ACTION without an Association
        if not self.is_established:
            raise RuntimeError(
                "The association with a peer SCP must be established prior "
                "to sending an N-ACTION request"
            )

        # Determine the Presentation Context we are operating under
        #   and hence the transfer syntax to use for encoding `dataset`
        context = self._get_valid_context(meta_uid or class_uid, "", "scu")
        if class_uid and context.abstract_syntax != class_uid:
            LOGGER.info("Using Presentation Context:")
            LOGGER.info(f"  Context ID:        {context.context_id}")
            LOGGER.info(
                "  Abstract Syntax:   =" f"{cast(UID, context.abstract_syntax).name}"
            )
        transfer_syntax = context.transfer_syntax[0]

        # Build N-ACTION request primitive
        #   (M) Message ID
        #   (M) Requested SOP Class UID
        #   (M) Requested SOP Instance UID
        #   (M) Action Type ID
        #   (U) Action Information
        req = N_ACTION()
        req.MessageID = msg_id
        req.RequestedSOPClassUID = UID(class_uid)
        req.RequestedSOPInstanceUID = UID(instance_uid)
        req.ActionTypeID = action_type

        # Action Information is optional
        if dataset is not None:
            # Encode the `dataset` using the agreed transfer syntax
            #   Will return None if failed to encode
            bytestream = encode(
                dataset,
                transfer_syntax.is_implicit_VR,
                transfer_syntax.is_little_endian,
                transfer_syntax.is_deflated,
            )

            if bytestream is not None:
                req.ActionInformation = BytesIO(bytestream)
            else:
                msg = "Failed to encode the supplied 'Action Information' dataset"
                LOGGER.error(msg)
                raise ValueError(msg)

        # Send N-ACTION request to the peer via DIMSE and wait for the response
        LOGGER.info(f"Sending Action Request: MsgID {msg_id}")

        # Pause the reactor to prevent a race condition
        self._reactor_checkpoint.clear()
        while not self._is_paused:
            time.sleep(0.0001)

        self.dimse.send_msg(req, cast(int, context.context_id))
        cx_id, rsp = self.dimse.get_msg(block=True)

        # Unpause the reactor
        self._reactor_checkpoint.set()

        # If `rsp` is None then the DIMSE timeout expired so abort
        if rsp is None:
            self._handle_no_response()
            return Dataset(), None

        # Determine validity of the response and get the status
        status = self._check_received_status(rsp)

        # Warning and Success statuses will return a dataset
        #   we check against None as 0x0000 is a possible status
        action_reply = None
        if getattr(status, "Status", None) is not None:
            category = code_to_category(cast(int, status.Status))
            if category not in [STATUS_WARNING, STATUS_SUCCESS]:
                return status, action_reply

            b: BytesIO = rsp.ActionReply  # type: ignore
            if b and b.getvalue() != b"":
                # Attempt to decode the response's dataset
                # pylint: disable=broad-except
                try:
                    action_reply = decode(
                        b,
                        transfer_syntax.is_implicit_VR,
                        transfer_syntax.is_little_endian,
                        transfer_syntax.is_deflated,
                    )
                except Exception as ex:
                    LOGGER.error("Unable to decode the received 'Action Reply' dataset")
                    LOGGER.exception(ex)
                    # Failure: Processing failure
                    status.Status = 0x0110
            else:
                action_reply = Dataset()

        return status, action_reply

    def send_n_create(
        self,
        dataset: Dataset,
        class_uid: str | UID,
        instance_uid: str | UID | None = None,
        msg_id: int = 1,
        meta_uid: str | UID | None = None,
    ) -> tuple[Dataset, Dataset | None]:
        """Send an N-CREATE request to the peer AE.

        Parameters
        ----------
        dataset : pydicom.dataset.Dataset or None
            The dataset that will be sent as the *Attribute List*
            parameter in the N-CREATE request, or ``None`` if not required.
        class_uid : pydicom.uid.UID
            The UID to be sent for the request's (0000,0002) *Affected SOP
            Class UID* parameter.
        instance_uid : pydicom.uid.UID, optional
            The UID to be sent for the request's (0000,1000) *Affected SOP
            Instance UID* parameter.
        msg_id : int, optional
            The request's *Message ID* parameter value, must be between 0 and
            65535, inclusive, (default ``1``).
        meta_uid : pydicom.uid.UID, optional
            If the service class operates under a presentation context
            negotiated using a *Meta SOP Class* rather than a standard *SOP
            Class* (such as with *Print Management* service class and its
            *Basic Grayscale Print Management Meta SOP Class*) then this
            value will be used to determine the corresponding presentation
            context.

        Returns
        -------
        status : pydicom.dataset.Dataset
            If the peer timed out, aborted or sent an invalid response then
            returns an empty :class:`~pydicom.dataset.Dataset`. If a response
            was received from the peer then returns a
            :class:`~pydicom.dataset.Dataset` containing at least a (0000,0900)
            *Status* element, and depending on the returned value, may
            optionally contain additional elements (see the DICOM Standard,
            Part 7,
            :dcm:`Section 10.1.5.1.6<part07/chapter_10.html#sect_10.1.5.1.6>`
            and :dcm:`Annex C<part07/chapter_C.html>`).

            *General N-CREATE* (DICOM Standard, Part 7, Section 10.1.5 and
            Annex C)

            Success
              | ``0x0000`` - Successful operation

            Failure
              | ``0x0110`` - Processing failure
              | ``0x0112`` - No such SOP Instance
              | ``0x0114`` - No such argument
              | ``0x0115`` - Invalid argument value
              | ``0x0117`` - Invalid object instance
              | ``0x0118`` - No such SOP Class
              | ``0x0119`` - Class-Instance conflict
              | ``0x0123`` - No such action
              | ``0x0124`` - Not authorised
              | ``0x0210`` - Duplicate invocation
              | ``0x0211`` - Unrecognised operation
              | ``0x0212`` - Mistyped argument
              | ``0x0213`` - Resource limitation

            *Print Management Service* specific (DICOM
            Standard Part 4, Annex H.4.1.2.1.2, H.4.2.2.1.2 and H.4.9.2.1.2):

            Warning
              | ``0xB600`` - Memory allocation not supported
              | ``0xB605`` - Requested Min Density or Max Density outside of
                printer's operating range. The printer will use its respective
                minimum or maximum density value instead

            Failure
              | ``0xC616`` - There is an existing Film Box that has not been
                printed and N-ACTION at the Film Session level is not
                supported. A new Film Box will not be created when a previous
                Film Box has not been printed

            *Media Creation Management Service* specific (DICOM
            Standard Part 4, Annex S.3.2.1.4):

            Failure
              | ``0xA510`` - Failed: an initiate media creation action has
                already been received for this SOP Instance

            *Unified Procedure Step Service* specific (DICOM
            Standard Part 4, Annex CC.2.5.4):

            Warning
              | ``0xB300`` - THE UPS was created with modifications

            Failure
              | ``0xC309`` - The provided value of UPS State was not
                'SCHEDULED'

            *RT Machine Verification Service* specific (DICOM
            Standard Part 4, Annex DD.3.2.1.2):

            Failure
              | ``0xC221`` - The Referenced Fraction Group Number does not
                exist in the referenced plan
              | ``0xC222`` - No beams exist within the referenced fraction
                group
              | ``0xC223`` - SCU already verifying and cannot currently process
                this request
              | ``0xC227`` - No such object instance - Referenced RT Plan not
                found

        attribute_list : pydicom.dataset.Dataset or None
            If the status category is 'Success' or 'Warning' then a
            :class:`~pydicom.dataset.Dataset` containing attributes
            corresponding to those supplied in the *Attribute List*. Because
            *Attribute List* is optional the returned
            :class:`~pydicom.dataset.Dataset` may be empty.

            If the status category is 'Failure' or if the peer timed-out,
            aborted, or sent an invalid response then returns ``None``.

        See Also
        --------

        :class:`~pynetdicom.dimse_primitives.N_CREATE`
        :class:`~pynetdicom.service_class_n.InstanceAvailabilityNotificationServiceClass`
        :class:`~pynetdicom.service_class_n.MediaCreationManagementServiceClass`
        :class:`~pynetdicom.service_class_n.PrintManagementServiceClass`
        :class:`~pynetdicom.service_class_n.ProcedureStepServiceClass`
        :class:`~pynetdicom.service_class_n.RTMachineVerificationServiceClass`
        :class:`~pynetdicom.service_class_n.UnifiedProcedureStepServiceClass`

        References
        ----------

        * DICOM Standard, Part 4, :dcm:`Annex F<part04/chapter_F.html>`
        * DICOM Standard, Part 4, :dcm:`Annex H<part04/chapter_H.html>`
        * DICOM Standard, Part 4, :dcm:`Annex R<part04/chapter_R.html>`
        * DICOM Standard, Part 4, :dcm:`Annex S<part04/chapter_S.html>`
        * DICOM Standard, Part 4, :dcm:`Annex CC<part04/chapter_CC.html>`
        * DICOM Standard, Part 4, :dcm:`Annex DD<part04/chapter_DD.html>`
        * DICOM Standard, Part 7, Sections
          :dcm:`10.1.5<part07/chapter_10.html#sect_10.1.5>`,
          :dcm:`10.3.5<part07/sect_10.3.5.html>`
          and :dcm:`Annex C<part07/chapter_C.html>`
        """
        # Can't send an N-CREATE without an Association
        if not self.is_established:
            raise RuntimeError(
                "The association with a peer SCP must be established prior "
                "to sending an N-CREATE request"
            )

        # Determine the Presentation Context we are operating under
        #   and hence the transfer syntax to use for encoding `dataset`
        context = self._get_valid_context(meta_uid or class_uid, "", "scu")
        transfer_syntax = context.transfer_syntax[0]

        # Build N-CREATE request primitive
        #   (M) Message ID
        #   (M) Affected SOP Class UID
        #   (U) Affected SOP Instance UID
        #   (U) Attribute List
        req = N_CREATE()
        req.MessageID = msg_id
        req.AffectedSOPClassUID = UID(class_uid)
        instance_uid = UID(instance_uid) if instance_uid else None
        req.AffectedSOPInstanceUID = instance_uid

        # Attribute List is optional
        if dataset is not None:
            # Encode the `dataset` using the agreed transfer syntax
            #   Will return None if failed to encode
            bytestream = encode(
                dataset,
                transfer_syntax.is_implicit_VR,
                transfer_syntax.is_little_endian,
                transfer_syntax.is_deflated,
            )

            if bytestream is not None:
                req.AttributeList = BytesIO(bytestream)
            else:
                msg = "Failed to encode the supplied 'Attribute List' dataset"
                LOGGER.error(msg)
                raise ValueError(msg)

        # Send N-CREATE request to the peer via DIMSE and wait for the response
        LOGGER.info(f"Sending Create Request: MsgID {msg_id}")

        # Pause the reactor to prevent a race condition
        self._reactor_checkpoint.clear()
        while not self._is_paused:
            time.sleep(0.0001)

        self.dimse.send_msg(req, cast(int, context.context_id))
        cx_id, rsp = self.dimse.get_msg(block=True)

        # Unpause the reactor
        self._reactor_checkpoint.set()

        # If `rsp` is None then the DIMSE timeout expired so abort
        if rsp is None:
            self._handle_no_response()
            return Dataset(), None

        # Determine validity of the response and get the status
        status = self._check_received_status(rsp)

        # Warning and Success statuses will return a dataset
        #   we check against None as 0x0000 is a possible status
        attribute_list = None
        if getattr(status, "Status", None) is not None:
            category = code_to_category(cast(int, status.Status))
            if category not in [STATUS_WARNING, STATUS_SUCCESS]:
                return status, attribute_list

            b: BytesIO = rsp.AttributeList  # type: ignore
            if b and b.getvalue() != b"":
                # Attempt to decode the response's dataset
                # pylint: disable=broad-except
                try:
                    attribute_list = decode(
                        b,
                        transfer_syntax.is_implicit_VR,
                        transfer_syntax.is_little_endian,
                        transfer_syntax.is_deflated,
                    )
                except Exception as ex:
                    LOGGER.error(
                        "Unable to decode the received 'Attribute List' dataset"
                    )
                    LOGGER.exception(ex)
                    # Failure: Processing failure
                    status.Status = 0x0110

            else:
                attribute_list = Dataset()

        return status, attribute_list

    def send_n_delete(
        self,
        class_uid: str | UID,
        instance_uid: str | UID,
        msg_id: int = 1,
        meta_uid: str | UID | None = None,
    ) -> Dataset:
        """Send an N-DELETE request to the peer AE.

        Parameters
        ----------
        class_uid : pydicom.uid.UID
            The UID to be sent for the request's (0000,0003) *Requested SOP
            Class UID* parameter.
        instance_uid : pydicom.uid.UID
            The UID to be sent for the request's (0000,1001) *Requested SOP
            Instance UID* parameter.
        msg_id : int, optional
            The request's *Message ID* parameter value, must be between 0 and
            65535, inclusive, (default ``1``).
        meta_uid : pydicom.uid.UID, optional
            If the service class operates under a presentation context
            negotiated using a *Meta SOP Class* rather than a standard *SOP
            Class* (such as with *Print Management* service class and its
            *Basic Grayscale Print Management Meta SOP Class*) then this
            value will be used to determine the corresponding presentation
            context.

        Returns
        -------
        status : pydicom.dataset.Dataset
            If the peer timed out, aborted or sent an invalid response then
            returns an empty :class:`~pydicom.dataset.Dataset`. If a response
            was received from the peer then returns a
            :class:`~pydicom.dataset.Dataset` containing at least a (0000,0900)
            *Status* element, and depending on the returned value, may
            optionally contain additional elements (see the DICOM Standard,
            Part 7,
            :dcm:`Section 10.1.6.1.7<part07/chapter_10.html#sect_10.1.6.1.7>`
            and :dcm:`Annex C<part07/chapter_C.html>`).

            General N-DELETE (DICOM Standard, Part 7, Section 10.1.6 and
            Annex C)

            Success
              | ``0x0000`` - Successful operation

            Failure
              | ``0x0110`` - Processing failure
              | ``0x0112`` - No such SOP Instance
              | ``0x0117`` - Invalid object instance
              | ``0x0118`` - No such SOP Class
              | ``0x0119`` - Class-Instance conflict
              | ``0x0124`` - Not authorised
              | ``0x0210`` - Duplicate invocation
              | ``0x0211`` - Unrecognised operation
              | ``0x0212`` - Mistyped argument
              | ``0x0213`` - Resource limitation

        See Also
        --------

        :class:`~pynetdicom.dimse_primitives.N_DELETE`
        :class:`~pynetdicom.service_class_n.PrintManagementServiceClass`
        :class:`~pynetdicom.service_class_n.RTMachineVerificationServiceClass`

        References
        ----------

        * DICOM Standard, Part 4, :dcm:`Annex H <part04/chapter_H.html>`
        * DICOM Standard, Part 4, :dcm:`Annex DD <part04/chapter_DD.html>`
        * DICOM Standard, Part 7, Sections
          :dcm:`10.1.6<part07/chapter_10.html#sect_10.1.6>`,
          :dcm:`10.3.6<part07/sect_10.3.6.html>`
          and :dcm:`Annex C<part07/chapter_C.html>`
        """
        # Can't send an N-DELETE without an Association
        if not self.is_established:
            raise RuntimeError(
                "The association with a peer SCP must be established prior "
                "to sending an N-DELETE request"
            )

        # Determine the Presentation Context we are operating under
        #   and hence the transfer syntax to use for encoding `dataset`
        context = self._get_valid_context(meta_uid or class_uid, "", "scu")

        # Build N-DELETE request primitive
        #   (M) Message ID
        #   (M) Requested SOP Class UID
        #   (M) Requested SOP Instance UID
        req = N_DELETE()
        req.MessageID = msg_id
        req.RequestedSOPClassUID = UID(class_uid)
        req.RequestedSOPInstanceUID = UID(instance_uid)

        # Send N-DELETE request to the peer via DIMSE and wait for the response
        LOGGER.info(f"Sending Delete Request: MsgID {msg_id}")

        # Pause the reactor to prevent a race condition
        self._reactor_checkpoint.clear()
        while not self._is_paused:
            time.sleep(0.0001)

        self.dimse.send_msg(req, cast(int, context.context_id))
        cx_id, rsp = self.dimse.get_msg(block=True)

        # Unpause the reactor
        self._reactor_checkpoint.set()

        # If `rsp` is None then the DIMSE timeout expired so abort
        if rsp is None:
            self._handle_no_response()
            return Dataset()

        # Determine validity of the response and get the status
        status = self._check_received_status(rsp)

        return status

    def send_n_event_report(
        self,
        dataset: Dataset,
        event_type: int,
        class_uid: str | UID,
        instance_uid: str | UID,
        msg_id: int = 1,
        meta_uid: str | UID | None = None,
    ) -> tuple[Dataset, Dataset | None]:
        """Send an N-EVENT-REPORT request to the peer AE.

        Parameters
        ----------
        dataset : pydicom.dataset.Dataset or None
            The dataset that will be sent as the *Event Information* parameter
            in the N-EVENT-REPORT request, if no *Event Information* parameter
            is needed then ``None``.
        event_type : int
            The value to be sent for the request's (0000,1002) *Event Type ID*
            parameter.
        class_uid : pydicom.uid.UID
            The UID to be sent for the request's (0000,0003) *Affected SOP
            Class UID* parameter.
        instance_uid : pydicom.uid.UID
            The UID to be sent for the request's (0000,1000) *Affected SOP
            Instance UID* parameter.
        msg_id : int, optional
            The request's *Message ID* parameter value, must be between 0 and
            65535, inclusive, (default ``1``).
        meta_uid : pydicom.uid.UID, optional
            If the service class operates under a presentation context
            negotiated using a *Meta SOP Class* rather than a standard *SOP
            Class* (such as with *Print Management* service class and its
            *Basic Grayscale Print Management Meta SOP Class*) then this
            value will be used to determine the corresponding presentation
            context.

        Returns
        -------
        status : pydicom.dataset.Dataset
            If the peer timed out, aborted or sent an invalid response then
            returns an empty :class:`~pydicom.dataset.Dataset`. If a response
            was received from the peer then returns a
            :class:`~pydicom.dataset.Dataset` containing at least a (0000,0900)
            *Status* element, and depending on the returned value, may
            optionally contain additional elements (see the DICOM Standard,
            Part 7,
            :dcm:`Section 10.1.1.1.8<part07/chapter_10.html#sect_10.1.1.1.8>`
            and :dcm:`Annex C<part07/chapter_C.html>`).

            *General N-EVENT-REPORT* (DICOM Standard, Part 7, Section 10.1.1
            and Annex C)

            Success
              | ``0x0000`` - Successful operation

            Failure
              | ``0x0110`` - Processing failure
              | ``0x0112`` - No such SOP Instance
              | ``0x0113`` - No such event type
              | ``0x0114`` - No such argument
              | ``0x0115`` - Invalid argument value
              | ``0x0117`` - Invalid object instance
              | ``0x0118`` - No such SOP Class
              | ``0x0119`` - Class-Instance conflict
              | ``0x0210`` - Duplicate invocation
              | ``0x0211`` - Unrecognised operation
              | ``0x0212`` - Mistyped argument
              | ``0x0213`` - Resource limitation

        event_reply : pydicom.dataset.Dataset or None
            If the status category is 'Success' or 'Warning' then a
            :class:`~pydicom.dataset.Dataset`
            containing attributes corresponding to those supplied in the
            *Event Reply*. Because *Event Reply* is optional the returned
            :class:`~pydicom.dataset.Dataset` may be empty.

            If the status category is 'Failure' or if the peer timed-out,
            aborted, or sent an invalid response then returns ``None``.

        See Also
        --------

        :class:`~pynetdicom.dimse_primitives.N_EVENT_REPORT`
        :class:`~pynetdicom.service_class_n.PrintManagementServiceClass`
        :class:`~pynetdicom.service_class_n.ProcedureStepServiceClass`
        :class:`~pynetdicom.service_class_n.RTMachineVerificationServiceClass`
        :class:`~pynetdicom.service_class_n.StorageCommitmentServiceClass`
        :class:`~pynetdicom.service_class_n.StorageManagementServiceClass`
        :class:`~pynetdicom.service_class_n.UnifiedProcedureStepServiceClass`

        References
        ----------

        * DICOM Standard, Part 4, :dcm:`Annex F <part04/chapter_F.html>`
        * DICOM Standard, Part 4, :dcm:`Annex H <part04/chapter_H.html>`
        * DICOM Standard, Part 4, :dcm:`Annex J <part04/chapter_J.html>`
        * DICOM Standard, Part 4, :dcm:`Annex CC <part04/chapter_CC.html>`
        * DICOM Standard, Part 4, :dcm:`Annex DD <part04/chapter_DD.html>`
        * DICOM Standard, Part 4, :dcm:`Annex KK <part04/chapter_KK.html>`
        * DICOM Standard, Part 7, Sections
          :dcm:`10.1.1 <part07/chapter_10.html#sect_10.1.1>`,
          :dcm:`10.3.1 <part07/sect_10.3.html#sect_10.3.1>`
          and :dcm:`Annex C <part07/chapter_C.html>`
        """
        # Can't send an N-EVENT-REPORT without an Association
        if not self.is_established:
            raise RuntimeError(
                "The association with a peer SCP must be established prior "
                "to sending an N-EVENT-REPORT request"
            )

        # Determine the Presentation Context we are operating under
        #   and hence the transfer syntax to use for encoding `dataset`
        # As far as I can tell, N-EVENT-REPORT doesn't use SCP/SCU Role
        #   selection negotiation, so we need to ignore the negotiate role
        #   since the SCP will be sending requests to the SCU
        context = self._get_valid_context(meta_uid or class_uid, "", None)
        if class_uid and context.abstract_syntax != class_uid:
            LOGGER.info("Using Presentation Context:")
            LOGGER.info(f"  Context ID:        {context.context_id}")
            LOGGER.info(
                "  Abstract Syntax:   =" f"{cast(UID, context.abstract_syntax).name}"
            )
        transfer_syntax = context.transfer_syntax[0]

        # Build N-EVENT-REPORT request primitive
        #   (M) Message ID
        #   (M) Affected SOP Class UID
        #   (M) Affected SOP Instance UID
        #   (M) Event Type ID
        #   (U) Event Information
        req = N_EVENT_REPORT()
        req.MessageID = msg_id
        req.AffectedSOPClassUID = UID(class_uid)
        req.AffectedSOPInstanceUID = UID(instance_uid)
        req.EventTypeID = event_type

        # *Event Information* is optional
        if dataset is not None:
            # Encode the `dataset` using the agreed transfer syntax
            #   Will return None if failed to encode
            bytestream = encode(
                dataset,
                transfer_syntax.is_implicit_VR,
                transfer_syntax.is_little_endian,
                transfer_syntax.is_deflated,
            )

            if bytestream is not None:
                req.EventInformation = BytesIO(bytestream)
            else:
                msg = "Unable to encode the supplied 'Event Information' dataset"
                LOGGER.error(msg)
                raise ValueError(msg)

        # Send N-EVENT-REPORT request to the peer via DIMSE and wait for
        # the response primitive
        LOGGER.info(f"Sending Event Report Request: MsgID {msg_id}")

        # Pause the reactor to prevent a race condition
        self._reactor_checkpoint.clear()
        while not self._is_paused:
            time.sleep(0.0001)

        self.dimse.send_msg(req, cast(int, context.context_id))
        cx_id, rsp = self.dimse.get_msg(block=True)

        # Unpause the reactor
        self._reactor_checkpoint.set()

        # If `rsp` is None then the DIMSE timeout expired so abort
        if rsp is None:
            self._handle_no_response()
            return Dataset(), None

        # Determine validity of the response and get the status
        status = self._check_received_status(rsp)

        # Warning and Success statuses will return a dataset
        #   we check against None as 0x0000 is a possible status
        event_reply = None
        if getattr(status, "Status", None) is not None:
            category = code_to_category(cast(int, status.Status))
            if category not in [STATUS_WARNING, STATUS_SUCCESS]:
                return status, event_reply

            b: BytesIO = rsp.EventReply  # type: ignore
            if b and b.getvalue() != b"":
                # Attempt to decode the response"s dataset
                # pylint: disable=broad-except
                try:
                    event_reply = decode(
                        b,
                        transfer_syntax.is_implicit_VR,
                        transfer_syntax.is_little_endian,
                        transfer_syntax.is_deflated,
                    )
                except Exception as ex:
                    LOGGER.error("Unable to decode the received 'Event Reply' dataset")
                    LOGGER.exception(ex)
                    # Failure: Processing failure
                    status.Status = 0x0110

            else:
                event_reply = Dataset()

        return status, event_reply

    def send_n_get(
        self,
        identifier_list: list[BaseTag],
        class_uid: str | UID,
        instance_uid: str | UID,
        msg_id: int = 1,
        meta_uid: str | UID | None = None,
    ) -> tuple[Dataset, Dataset | None]:
        """Send an N-GET request to the peer AE.

        Parameters
        ----------
        identifier_list : list of pydicom.tag.BaseTag
            A list of DICOM Data Element tags to be sent for the request's
            (0000,1005) *Attribute Identifier List* parameter. Should either be
            a list of *pydicom* :class:`~pydicom.tag.BaseTag` objects or a
            list of values that is acceptable for creating them.
        class_uid : pydicom.uid.UID
            The UID to be sent for the request's (0000,0003) *Requested SOP
            Class UID* parameter.
        instance_uid : pydicom.uid.UID
            The UID to be sent for the request's (0000,1001) *Requested SOP
            Instance UID* parameter.
        msg_id : int, optional
            The request's *Message ID* parameter value, must be between 0 and
            65535, inclusive, (default ``1``).
        meta_uid : pydicom.uid.UID, optional
            If the service class operates under a presentation context
            negotiated using a *Meta SOP Class* rather than a standard *SOP
            Class* (such as with *Print Management* service class and its
            *Basic Grayscale Print Management Meta SOP Class*) then this
            value will be used to determine the corresponding presentation
            context.

        Returns
        -------
        status : pydicom.dataset.Dataset
            If the peer timed out, aborted or sent an invalid response then
            returns an empty :class:`~pydicom.dataset.Dataset`. If a response
            was received from the peer then returns a
            :class:`~pydicom.dataset.Dataset` containing at least a (0000,0900)
            *Status* element, and depending on the returned value, may
            optionally contain additional elements (see the DICOM Standard,
            Part 7,
            :dcm:`Section 10.1.2.1.9<part07/chapter_10.html#sect_10.1.2.1.9>`
            and :dcm:`Annex C<part07/chapter_C.html>`).

            *General N-GET* (DICOM Standard, Part 7, Section 10.1.2 and
            Annex C)

            Success
              | ``0x0000`` - Successful operation

            Warning
              | ``0x0107`` - Attribute list error

            Failure
              | ``0x0110`` - Processing failure
              | ``0x0112`` - No such SOP Instance
              | ``0x0117`` - Invalid object instance
              | ``0x0118`` - No such SOP Class
              | ``0x0119`` - Class-Instance conflict
              | ``0x0122`` - SOP class not supported
              | ``0x0124`` - Not authorised
              | ``0x0210`` - Duplicate invocation
              | ``0x0211`` - Unrecognised operation
              | ``0x0212`` - Mistyped argument
              | ``0x0213`` - Resource limitation

            *Modality Performed Procedure Step Management Service* and *Media
            Creation Management Service* specific
            (DICOM Standard, Part 4, Annex F.8.2.1.4 and Annex S.3.2.4.4):

            Warning
              | ``0x0001`` - Requested optional Attributes are not supported

            *Unified Procedure Step Service* specific
            (DICOM Standard, Part 4, Annex CC.2.7.4):

            Warning
              | ``0x0001`` - Requested optional Attributes are not supported

            Failure
              | ``0xC307`` - Specified SOP Instance UID doesn't exist or is not
                a UPS Instance managed by this SCP

            *RT Machine Verification Service* specific
            (DICOM Standard, Part 4, Annex DD.3.2.2.3):

            Failure
              | ``0xC112`` - Applicable Machine Verification Instance not found

        attribute_list : pydicom.dataset.Dataset or None
            If the status category is 'Success' or 'Warning' then a
            :class:`~pydicom.dataset.Dataset`
            containing attributes corresponding to those supplied in the
            *Attribute List*. Because *Attribute List* is optional the returned
            :class:`~pydicom.dataset.Dataset` may be empty.

            If the status category is 'Failure' or if the peer timed-out,
            aborted, or sent an invalid response then returns ``None``.

        See Also
        --------

        :class:`~pynetdicom.dimse_primitives.N_GET`
        :class:`~pynetdicom.service_class_n.DisplaySystemManagementServiceClass`
        :class:`~pynetdicom.service_class_n.MediaCreationManagementServiceClass`
        :class:`~pynetdicom.service_class_n.PrintManagementServiceClass`
        :class:`~pynetdicom.service_class_n.ProcedureStepServiceClass`
        :class:`~pynetdicom.service_class_n.RTMachineVerificationServiceClass`
        :class:`~pynetdicom.service_class_n.UnifiedProcedureStepServiceClass`

        References
        ----------

        * DICOM Standard, Part 4, :dcm:`Annex F <part04/chapter_F.html>`
        * DICOM Standard, Part 4, :dcm:`Annex H <part04/chapter_H.html>`
        * DICOM Standard, Part 4, :dcm:`Annex S <part04/chapter_S.html>`
        * DICOM Standard, Part 4, :dcm:`Annex CC <part04/chapter_CC.html>`
        * DICOM Standard, Part 4, :dcm:`Annex DD <part04/chapter_DD.html>`
        * DICOM Standard, Part 4, :dcm:`Annex EE <part04/chapter_EE.html>`
        * DICOM Standard, Part 7, Sections
          :dcm:`10.1.2 <part07/chapter_10.html#sect_10.1.2>`,
          :dcm:`10.3.2 <part07/sect_10.3.2.html>`
          and :dcm:`Annex C <part07/chapter_C.html>`
        """
        # Can't send an N-GET without an Association
        if not self.is_established:
            raise RuntimeError(
                "The association with a peer SCP must be established prior "
                "to sending an N-GET request"
            )

        # Determine the Presentation Context we are operating under
        #   and hence the transfer syntax to use for encoding `dataset`
        context = self._get_valid_context(meta_uid or class_uid, "", "scu")
        if class_uid and context.abstract_syntax != class_uid:
            LOGGER.info("Using Presentation Context:")
            LOGGER.info(f"  Context ID:        {context.context_id}")
            LOGGER.info(
                "  Abstract Syntax:   =" f"{cast(UID, context.abstract_syntax).name}"
            )
        transfer_syntax = context.transfer_syntax[0]

        # Build N-GET request primitive
        #   (M) Message ID
        #   (M) Requested SOP Class UID
        #   (M) Requested SOP Instance UID
        #   (U) Attribute Identifier List
        req = N_GET()
        req.MessageID = msg_id
        req.RequestedSOPClassUID = UID(class_uid)
        req.RequestedSOPInstanceUID = UID(instance_uid)
        req.AttributeIdentifierList = identifier_list

        # Send N-GET request to the peer via DIMSE and wait for the response
        LOGGER.info(f"Sending Get Request: MsgID {msg_id}")

        # Pause the reactor to prevent a race condition
        self._reactor_checkpoint.clear()
        while not self._is_paused:
            time.sleep(0.0001)

        self.dimse.send_msg(req, cast(int, context.context_id))
        cx_id, rsp = self.dimse.get_msg(block=True)

        # Unpause the reactor
        self._reactor_checkpoint.set()

        # If `rsp` is None then the DIMSE timeout expired so abort
        if rsp is None:
            self._handle_no_response()
            return Dataset(), None

        # Determine validity of the response and get the status
        status = self._check_received_status(rsp)

        # Warning and Success statuses will return a dataset
        #   we check against None as 0x0000 is a possible status
        attribute_list = None
        if getattr(status, "Status", None) is not None:
            category = code_to_category(cast(int, status.Status))
            if category not in [STATUS_WARNING, STATUS_SUCCESS]:
                return status, attribute_list

            b: BytesIO = rsp.AttributeList  # type: ignore
            if b and b.getvalue() != b"":
                # Attempt to decode the response"s dataset
                # pylint: disable=broad-except
                try:
                    attribute_list = decode(
                        b,
                        transfer_syntax.is_implicit_VR,
                        transfer_syntax.is_little_endian,
                        transfer_syntax.is_deflated,
                    )
                except Exception as ex:
                    LOGGER.error(
                        "Unable to decode the received 'Attribute List' dataset"
                    )
                    LOGGER.exception(ex)
                    # Failure: Processing failure
                    status.Status = 0x0110

            else:
                attribute_list = Dataset()

        return status, attribute_list

    def send_n_set(
        self,
        dataset: Dataset,
        class_uid: str | UID,
        instance_uid: str | UID,
        msg_id: int = 1,
        meta_uid: str | UID | None = None,
    ) -> tuple[Dataset, Dataset | None]:
        """Send an N-SET request to the peer AE.

        Parameters
        ----------
        dataset : pydicom.dataset.Dataset
            The dataset that will be sent as the *Modification List* parameter
            in the N-SET request.
        class_uid : pydicom.uid.UID
            The UID to be sent for the request's (0000,0003) *Requested SOP
            Class UID* parameter.
        instance_uid : pydicom.uid.UID
            The UID to be sent for the request's (0000,1001) *Requested SOP
            Instance UID* parameter.
        msg_id : int, optional
            The request's *Message ID* parameter value, must be between 0 and
            65535, inclusive, (default ``1``).
        meta_uid : pydicom.uid.UID, optional
            If the service class operates under a presentation context
            negotiated using a *Meta SOP Class* rather than a standard *SOP
            Class* (such as with *Print Management* service class and its
            *Basic Grayscale Print Management Meta SOP Class*) then this
            value will be used to determine the corresponding presentation
            context.

        Returns
        -------
        status : pydicom.dataset.Dataset
            If the peer timed out, aborted or sent an invalid response then
            returns an empty :class:`~pydicom.dataset.Dataset`. If a response
            was received from the peer then returns a
            :class:`~pydicom.dataset.Dataset` containing at least a (0000,0900)
            *Status* element, and depending on the returned value, may
            optionally contain additional elements (see the DICOM Standard,
            Part 7,
            :dcm:`Section 10.1.3.1.9<part07/chapter_10.html#sect_10.1.3.1.9>`
            and :dcm:`Annex C<part07/chapter_C.html>`).

            *General N-SET* (DICOM Standard, Part 7, Section 10.1.3 and
            Annex C)

            Success
              | ``0x0000`` - Successful operation

            Warning
              | ``0x0107`` - Attribute list error
              | ``0x0116`` - Attribute value out of range

            Failure
              | ``0x0105`` - No such attribute
              | ``0x0106`` - Invalid attribute value
              | ``0x0110`` - Processing failure
              | ``0x0112`` - No such SOP Instance
              | ``0x0117`` - Invalid object instance
              | ``0x0118`` - No such SOP Class
              | ``0x0119`` - Class-Instance conflict
              | ``0x0121`` - Missing attribute value
              | ``0x0122`` - SOP class not supported
              | ``0x0124`` - Not authorised
              | ``0x0210`` - Duplicate invocation
              | ``0x0211`` - Unrecognised operation
              | ``0x0212`` - Mistyped argument
              | ``0x0213`` - Resource limitation

            *Print Management Service* specific (DICOM
            Standard Part 4, Annex H.4.1.2.1.2, H.4.2.2.1.2, H.4.3.1.2.1.2 and
            H.4.3.2.2.1.2):

            Warning
              | ``0xB600`` - Memory allocation not supported
              | ``0xB604`` - Image size larger than image box size, the image
                has been demagnified
              | ``0xB605`` - Requested Min Density or Max Density outside of
                printer's operating range. The printer will use its respective
                minimum or maximum density value instead
              | ``0xB609`` - Image size is larger than the Image Box. The Image
                has been cropped to fit
              | ``0xB60A`` - Image size or Combined Print Image size is larger
                than the Image Box size. The Image or Combined Print Image has
                been decimated to fit

            Failure
              | ``0xC603`` - Image size is larger than image box size
              | ``0xC605`` - Insufficient memory in printer to store the image
              | ``0xC613`` - Combined Print Image size is larger than the Image
                Box size
              | ``0xC616`` - There is an existing Film Box that has not been
                printed and N-ACTION at the Film Session level is not
                supported. A new Film Box will not be created when a previous
                Film Box has not been printed

            *Unified Procedure Step Service* specific (DICOM Standard, Part 4,
            Annex CC.2.6.4):

            Warning
              | ``0x0001`` - Requested optional attributes are not supported
              | ``0xB305`` - Coerced invalid values to valid values

            Failure
              | ``0xC300`` - The UPS may no longer be updated
              | ``0xC301`` - The correct Transaction UID was not provided
              | ``0xC307`` - Specified SOP Instance UID does not exist or is
                not a UPS Instance managed by this SCP
              | ``0xC310`` - The UPS is not in the 'IN PROGRESS' state

            *RT Machine Verification Service* specific (DICOM Standard, Part 4,
            Annex DD.3.2.1.2):

            Failure
              | ``0xC224`` - Reference Beam Number not found within the
                referenced Fraction Group
              | ``0xC225`` - Referenced device or accessory not supported
              | ``0xC226`` - Referenced device or accessory not found with the
                referenced beam

        attribute_list : pydicom.dataset.Dataset or None
            If the status category is 'Success' or 'Warning' then a
            :class:`~pydicom.dataset.Dataset`
            containing attributes corresponding to those supplied in the
            *Attribute List*. Because *Attribute List* is optional the returned
            :class:`~pydicom.dataset.Dataset` may be empty.

            If the status category is 'Failure' or if the peer timed-out,
            aborted, or sent an invalid response then returns ``None``.

        See Also
        --------

        :class:`~pynetdicom.dimse_primitives.N_SET`
        :class:`~pynetdicom.service_class_n.PrintManagementServiceClass`
        :class:`~pynetdicom.service_class_n.ProcedureStepServiceClass`
        :class:`~pynetdicom.service_class_n.RTMachineVerificationServiceClass`
        :class:`~pynetdicom.service_class_n.UnifiedProcedureStepServiceClass`

        References
        ----------

        * DICOM Standard, Part 4, :dcm:`Annex F <part04/chapter_F.html>`
        * DICOM Standard, Part 4, :dcm:`Annex H <part04/chapter_H.html>`
        * DICOM Standard, Part 4, :dcm:`Annex CC <part04/chapter_CC.html>`
        * DICOM Standard, Part 4, :dcm:`Annex DD <part04/chapter_DD.html>`
        * DICOM Standard, Part 7, Sections
          :dcm:`10.1.3 <part07/chapter_10.html#sect_10.1.3>`,
          :dcm:`10.3.3 <part07/sect_10.3.3.html>`
          and :dcm:`Annex C <part07/chapter_C.html>`
        """
        # Can't send an N-SET without an Association
        if not self.is_established:
            raise RuntimeError(
                "The association with a peer SCP must be established prior "
                "to sending an N-SET request"
            )

        # Determine the Presentation Context we are operating under
        #   and hence the transfer syntax to use for encoding `dataset`
        context = self._get_valid_context(meta_uid or class_uid, "", "scu")
        if class_uid and context.abstract_syntax != class_uid:
            LOGGER.info("Using Presentation Context:")
            LOGGER.info(f"  Context ID:        {context.context_id}")
            LOGGER.info(
                "  Abstract Syntax:   =" f"{cast(UID, context.abstract_syntax).name}"
            )
        transfer_syntax = context.transfer_syntax[0]

        # Build N-SET request primitive
        #   (M) Message ID
        #   (M) Requested SOP Class UID
        #   (M) Requested SOP Instance UID
        #   (M) Modification List
        req = N_SET()
        req.MessageID = msg_id
        req.RequestedSOPClassUID = UID(class_uid)
        req.RequestedSOPInstanceUID = UID(instance_uid)

        # Encode the `dataset` using the agreed transfer syntax
        #   Will return None if failed to encode
        bytestream = encode(
            dataset,
            transfer_syntax.is_implicit_VR,
            transfer_syntax.is_little_endian,
            transfer_syntax.is_deflated,
        )

        if bytestream is not None:
            req.ModificationList = BytesIO(bytestream)
        else:
            msg = "Failed to encode the supplied 'Modification List' dataset"
            LOGGER.error(msg)
            raise ValueError(msg)

        # Send N-SET request to the peer via DIMSE and wait for the response
        LOGGER.info(f"Sending Set Request: MsgID {msg_id}")

        # Pause the reactor to prevent a race condition
        self._reactor_checkpoint.clear()
        while not self._is_paused:
            time.sleep(0.0001)

        self.dimse.send_msg(req, cast(int, context.context_id))
        cx_id, rsp = self.dimse.get_msg(block=True)

        # Unpause the reactor
        self._reactor_checkpoint.set()

        # If `rsp` is None then the DIMSE timeout expired so abort
        if rsp is None:
            self._handle_no_response()
            return Dataset(), None

        # Determine validity of the response and get the status
        status = self._check_received_status(rsp)

        # Warning and Success statuses will return a dataset
        #   we check against None as 0x0000 is a possible status
        attribute_list = None
        if getattr(status, "Status", None) is not None:
            category = code_to_category(cast(int, status.Status))
            if category not in [STATUS_WARNING, STATUS_SUCCESS]:
                return status, attribute_list

            b: BytesIO = rsp.AttributeList  # type: ignore
            if b and b.getvalue() != b"":
                # Attempt to decode the response's dataset
                # pylint: disable=broad-except
                try:
                    attribute_list = decode(
                        b,
                        transfer_syntax.is_implicit_VR,
                        transfer_syntax.is_little_endian,
                        transfer_syntax.is_deflated,
                    )
                except Exception as ex:
                    LOGGER.error(
                        "Unable to decode the received 'Attribute List' dataset"
                    )
                    LOGGER.exception(ex)
                    # Failure: Processing failure
                    status.Status = 0x0110

            else:
                attribute_list = Dataset()

        return status, attribute_list

    def _serve_request(self, msg: DimseServiceType, context_id: int) -> None:
        """Handle a DIMSE service request.

        Parameters
        ----------
        msg : dimse_primitives.DIMSEPrimitive subclass
            The DIMSE service request primitive.
        context_id : int
            The ID of the presentation context that the request is being
            made under.
        """
        if self._sent_release:
            LOGGER.warning(
                f"{msg.msg_type} message received during association release, ignoring"
            )
            return

        # No message or not a service request
        if not msg.is_valid_request:
            LOGGER.warning(f"Received unexpected {msg.msg_type} service message")
            return

        # Use the Message's Affected SOP Class UID or Requested SOP
        #   Class UID to determine which service to use
        class_uid: str | UID = ""
        if getattr(msg, "AffectedSOPClassUID", None) is not None:
            # DIMSE-C, N-EVENT-REPORT, N-CREATE use AffectedSOPClassUID
            class_uid = cast(UID, msg.AffectedSOPClassUID)
        elif getattr(msg, "RequestedSOPClassUID", None) is not None:
            # N-GET, N-SET, N-ACTION, N-DELETE use RequestedSOPClassUID
            class_uid = msg.RequestedSOPClassUID  # type: ignore

        # SOP Class Common Extended Negotiation
        class_uid = cast(UID, class_uid)
        try:
            # The service class UID
            class_uid = self.acceptor.accepted_common_extended[class_uid][0]
        except KeyError:
            pass

        if _config.UNRESTRICTED_STORAGE_SERVICE and isinstance(msg, C_STORE):
            class_uid = "1.2.840.10008.5.1.4.1.1.1"

        # Convert the SOP/Service UID to the corresponding service
        service_class = uid_to_service_class(class_uid)(self)

        try:
            context = self._accepted_cx[context_id]
        except KeyError:
            LOGGER.info(
                "Received DIMSE message with invalid or rejected "
                f"context ID: {context_id}"
            )
            LOGGER.debug(str(msg))
            self.abort()
            return

        # Run corresponding Service Class in SCP mode
        try:
            # Clear out any C-CANCEL requests received beforehand
            self.dimse.cancel_req = {}
            # In case the SCP calls one of the send_* methods
            self._is_paused = True
            service_class.SCP(msg, context)
            self._is_paused = False
            # Clear out any unacted upon requests received during
            self.dimse.cancel_req = {}
        except NotImplementedError:
            # SCP isn't implemented
            LOGGER.error(
                "No supported service class available for the SOP "
                f"Class UID '{class_uid}', please see the "
                "pynetdicom.sop_class.register_uid() function if you need to add "
                "support for a private, retired or otherwise unknown SOP Class UID"
            )
            self.abort()
            return
        except Exception as exc:
            LOGGER.exception(exc)
            self.abort()
            return


class ServiceUser:
    """Convenience class for the :class:`Association` service user.

    An :class:`Association` object has two :class:`ServiceUser` attributes, one
    representing the association *requestor* and the other the association
    *acceptor*. Once both have been defined sufficiently to be considered
    valid then association negotiation can begin. The *requestor*
    :class:`ServiceUser` requires (at a minimum) the following in order to be
    valid:

    * For association as *requestor*:

        * AE title (`ae_title`)
        * Address and port number (`address` and `port`)
        * Maximum PDU length (`maximum_length`)
        * Implementation class UID (`implementation_class_uid`)
        * At least one presentation context (`requested_contexts`)
    * For association as *acceptor*:

        * AE title
        * Address and port number

    The *acceptor* :class:`ServiceUser` requires (at a minimum) the following
    in order to be valid:

    * For association as *requestor*:

        * Address and port number
    * For association as *acceptor*:

        * AE title
        * Address and port number
        * Maximum PDU length
        * Implementation class UID

    .. versionchanged:: 3.0

        `address` and `port` have been changed to properties and added the
        `address_info` attribute.

    Attributes
    ----------
    address_info : pynetdicom.transport.AddressInformation | None
        The connection properties of the local or remote AE. When the local AE is the
        requestor the IP address and port should be considered nominal until the
        connection with the remote is made.
    primitive : pynetdicom.pdu_primitives.A_ASSOCIATE | None
        The A-ASSOCIATE primitive (request if mode is ``'requestor'``,
        accept/reject if mode is ``'acceptor'``) sent or received by the AE
        during association negotiation.
    """

    def __init__(self, assoc: Association, mode: str) -> None:
        """Create a new :class:`ServiceUser`.

        Parameters
        ----------
        assoc : association.Association
            The parent association.
        mode : str
            The operation mode of the AE represented by the
            :class:`ServiceUser`, either ``'requestor'`` or ``'acceptor'``.
            This is not necessarily the same as the association's
            :attr:`~Association.mode`.
        """
        mode = mode.lower()
        if mode not in [MODE_REQUESTOR, MODE_ACCEPTOR]:
            raise ValueError("The 'mode' must be either 'requestor' or 'acceptor'")

        self.assoc: Association = assoc
        self._mode: str = mode
        self._ae_title: str = ""
        self.primitive: A_ASSOCIATE | None = None

        self.address_info: AddressInformation | None = None

        # If Requestor this is the requested contexts, otherwise this is
        #   the supported contexts
        self._contexts: list[PresentationContext] = []

        # User Information items
        self._user_info: list[_UI] = []
        # Must always be set
        self.maximum_length: int = DEFAULT_MAX_LENGTH
        self.implementation_class_uid: UID = assoc.ae.implementation_class_uid

        # These are the proposed extended negotiation items,
        self._ext_neg: dict[_UITypes, list[_UI]] = {}
        self.reset_negotiation_items()

        # If Acceptor then this the accepted SOP Class Common Extended
        #   negotiation items
        self._common_ext: dict[UID, SOPClassCommonExtendedNegotiation] = {}

    @property
    def accepted_common_extended(self) -> dict[UID, tuple[UID, list[UID]]]:
        """Return a :class:`dict` of the accepted SOP Class Common Extended
        Negotiation.

        Returns
        -------
        dict of 2-tuple
            The ``{'SOP Class UID' : (Service Class UID, Related General SOP
            Class Identification)}`` for the accepted SOP Class Common Extended
            negotiation items.

        Raises
        ------
        RuntimeError
            If called when the *requestor*.
        """
        if not self.is_acceptor:
            raise RuntimeError(
                "'accepted_common_extended' is only available for the 'acceptor'"
            )

        out = {}
        for item in self._common_ext.values():
            out[cast(UID, item.sop_class_uid)] = (
                cast(UID, item.service_class_uid),
                item.related_general_sop_class_identification,
            )

        return out

    def add_negotiation_item(self, item: _UI) -> None:
        """Add an extended negotiation item to the user information.

        Items can only be added prior to starting the association negotiation.

        Parameters
        ----------
        item : pdu_primitives.ServiceParameter
            An extended negotiation item, one of:

            .. currentmodule:: pynetdicom.pdu_primitives

            * :class:`SCP_SCU_RoleSelectionNegotiation`
            * :class:`UserIdentityNegotiation`
            * :class:`AsynchronousOperationsWindowNegotiation`
            * :class:`SOPClassExtendedNegotiation`
            * :class:`SOPClassCommonExtendedNegotiation`

        Raises
        ------
        RuntimeError
            If attempting to add an item after association negotiation has
            started.
        TypeError
            If `item` it not an extended negotiation item.
        """
        if not self.writeable:
            raise RuntimeError(
                "Can't add extended negotiation items after negotiation has started"
            )

        #
        try:
            self._ext_neg[type(item)].append(item)
        except KeyError:
            raise TypeError("'item' is not a valid extended negotiation item")

    @property
    def address(self) -> str:
        """Get the requestor or acceptor's IP address (if set)."""
        if self.address_info is None:
            raise ValueError("No address information has been set")

        return self.address_info.address

    @property
    def ae_title(self) -> str:
        """Get or set the AE title.

        Parameters
        ----------
        value : str
            The AE title as an ASCII string.

        Returns
        -------
        str
            The AE title as an ASCII string.
        """
        return self._ae_title

    @ae_title.setter
    def ae_title(self, value: str) -> None:
        """Set the service user's AE title."""
        if isinstance(value, bytes):
            warnings.warn(
                "The use of bytes with 'ae_title' is deprecated, use an ASCII "
                "str instead",
                DeprecationWarning,
            )
            value = decode_bytes(value)

        self._ae_title = cast(str, set_ae(value, "ae_title", False, False))

    @property
    def asynchronous_operations(self) -> tuple[int, int]:
        """Return the Asynchronous Operations Window operations numbers.

        Returns
        -------
        2-tuple of int
            The (*Maximum Number of Operations Invoked*, *Maximum Number of
            Operations Performed*) or ``(1, 1)`` if no Asynchronous Operations
            Window Negotiation item is in the extended negotiation items.
        """
        if self.writeable:
            for item in self._ext_neg[AsynchronousOperationsWindowNegotiation]:
                item = cast(AsynchronousOperationsWindowNegotiation, item)
                return (
                    item.maximum_number_operations_invoked,
                    item.maximum_number_operations_performed,
                )

        for item in self.user_information:
            if isinstance(item, AsynchronousOperationsWindowNegotiation):
                return (
                    item.maximum_number_operations_invoked,
                    item.maximum_number_operations_performed,
                )

        return (1, 1)

    @property
    def extended_negotiation(self) -> list[_UI]:
        """Return a :class:`list` of Extended Negotiation items.

        Extended Negotiation items are:

        * SCP/SCU Role Selection Negotiation (0 or more)
        * Asynchronous Operations Window Negotiation (0 or 1)
        * SOP Class Extended Negotiation (0 or more)
        * SOP Class Common Extended Negotiation (0 or more)
        * User Identity Negotiation (0 or 1)

        Returns
        -------
        list
            If :meth:`~ServiceUser.mode` is ``'requestor'`` then returns a
            :class:`list` of the proposed extended negotiation items,
            otherwise returns a list of the extended negotiation item
            responses.
        """
        items = []
        if self.writeable:
            for item_type in self._ext_neg:
                items.extend(self._ext_neg[item_type])

            return items

        # pylint: disable=unidiomatic-typecheck
        for item in self.user_information:
            if type(item) in self._ext_neg.keys():
                items.append(item)

        return items

    def get_contexts(self, cx_type: str) -> list[PresentationContext]:
        """Return a :class:`list` of
        :class:`~pynetdicom.presentation.PresentationContext` items
        corresponding to `cx_type`.

        Parameters
        ----------
        cx_type : str
            The type of contexts to return, if `mode` is ``'requestor'``:

            - If the association has not yet been negotiated then
              ``'requested'``.
            - If the association has been negotiated then ``'requested'`` or
              ``'pcdl'``.

            If `mode` is ``'acceptor'``:

            - If the association has not yet been negotiated then
              ``'supported'``.
            - If the association has been negotiated then ``'supported'`` or
              ``'pcdrl'``.

        Returns
        -------
        list of presentation.PresentationContext
            A list of presentations contexts, if `cx_type` is ``'requested'``
            then the requested presentation contexts, if ``'pcdl'`` then the
            presentation contexts from the A-ASSOCIATE (request) primitive's
            Presentation Context Definition List parameter. If ``'supported'``
            then the supported presentation contexts, if ``'pcdrl'`` then the
            presentation contexts from the A-ASSOCIATE (accept) primitive's
            Presentation Context Definition Results List parameter.
        """
        contexts = {"requested": self._contexts, "supported": self._contexts}
        self.primitive = cast(A_ASSOCIATE, self.primitive)
        if not self.writeable:
            contexts.update(
                {
                    "pcdl": self.primitive.presentation_context_definition_list,
                    "pcdrl": (
                        self.primitive.presentation_context_definition_results_list
                    ),
                }
            )

        possible: dict[bool, dict[bool, dict[bool, list[str]]]] = {
            True: {  # self.assoc.is_requestor
                True: {  # self.writeable
                    True: ["requested"],  # self.is_requestor
                    False: [],  # self.is_acceptor
                },
                False: {  # not self.writeable
                    True: ["requested", "pcdl"],  # self.is_requestor
                    False: ["pcdrl"],  # self.is_acceptor
                },
            },
            False: {  # self.assoc.is_acceptor
                True: {  # self.writeable
                    True: [],  # self.is_requestor
                    False: ["supported"],  # self.is_acceptor
                },
                False: {  # not self.writeable
                    True: ["pcdl"],  # self.is_requestor
                    False: ["supported", "pcdrl"],  # self.is_acceptor
                },
            },
        }

        available = possible[self.assoc.is_requestor][self.writeable]
        if cx_type in available[self.is_requestor]:
            return contexts[cx_type]

        raise ValueError(
            f"No '{cx_type}' presentation contexts are available for the "
            f"{('requestor', 'acceptor')[self.is_acceptor]} service user"
        )

    @property
    def implementation_class_uid(self) -> UID | None:
        """The Implementation Class UID as a :class:`~pydicom.uid.UID`.

        Returns
        -------
        pydicom.uid.UID or None
            Returns the Implementation Class UID if the requestor or if
            the acceptor and they have accepted the negotiation. Returns
            ``None`` if the acceptor and they have rejected the negotiation.
        """
        if not self.writeable:
            for item in self.user_information:
                if isinstance(item, ImplementationClassUIDNotification):
                    return item.implementation_class_uid

            return None

        for item in self._user_info:
            if isinstance(item, ImplementationClassUIDNotification):
                return item.implementation_class_uid

        return None

    @implementation_class_uid.setter
    def implementation_class_uid(self, value: UID) -> None:
        """Set the Implementation Class UID (only prior to association).

        Parameters
        ----------
        str or pydicom.uid.UID
            The Implementation Class UID value.
        """
        if not self.writeable:
            raise RuntimeError(
                "Can't set the Implementation Class UID after negotiation "
                "has started"
            )

        for item in self._user_info:
            if isinstance(item, ImplementationClassUIDNotification):
                item.implementation_class_uid = value
                break
        else:
            item = ImplementationClassUIDNotification()
            item.implementation_class_uid = value
            self._user_info.append(item)

    @property
    def implementation_version_name(self) -> str | None:
        """Get or set the *Implementation Version Name*.

        Parameters
        ----------
        value : str or None
            The value to use for the *Implementation Version Name*, or ``None``
            if no Implementation Version Name Notification item is to be
            included in the association negotiation. Can only be set prior
            to association negotiation.

        Returns
        -------
        str or None
            Returns ``None`` if the acceptor and they have rejected the
            negotiation or if no Implementation Version Name Notification item
            has been included in the association negotiation. Otherwise returns
            the Implementation Version Name.
        """
        if not self.writeable:
            for item in self.user_information:
                if isinstance(item, ImplementationVersionNameNotification):
                    return item.implementation_version_name

            return None

        for item in self._user_info:
            if isinstance(item, ImplementationVersionNameNotification):
                return item.implementation_version_name

        return None

    @implementation_version_name.setter
    def implementation_version_name(self, value: str | None) -> None:
        """Set the Implementation Version Name (only prior to association)."""
        if not self.writeable:
            raise RuntimeError(
                "Can't set the Implementation Version Name after negotiation "
                "has started"
            )

        if value is None:
            for item in self._user_info:
                if isinstance(item, ImplementationVersionNameNotification):
                    self._user_info.remove(item)
                    break

            return

        # Validate - diallow an empty str
        value = cast(str, set_ae(value, "implementation_version_name", False, False))

        for item in self._user_info:
            if isinstance(item, ImplementationVersionNameNotification):
                item.implementation_version_name = value
                break
        else:
            item = ImplementationVersionNameNotification()
            item.implementation_version_name = value
            self._user_info.append(item)

    @property
    def info(self) -> dict[str, Any]:
        """Return a :class:`dict` with information about the :class:`ServiceUser`."""
        info = {
            "ae_title": self.ae_title,
            "address": self.address if self.address_info else None,
            "port": self.port if self.address_info else None,
            "mode": self.mode,
        }
        if not self.writeable:
            info["pdv_size"] = self.maximum_length

        return info

    @property
    def is_acceptor(self) -> bool:
        """Return ``True`` if the :class:`ServiceUser` is the association acceptor."""
        return self.mode == MODE_ACCEPTOR

    @property
    def is_requestor(self) -> bool:
        """Return ``True`` if the :class:`ServiceUser` is the association requestor."""
        return self.mode == MODE_REQUESTOR

    @property
    def maximum_length(self) -> int | None:
        """The maximum PDV size as :class:`int`.

        Returns
        -------
        int or None
            Returns the Maximum Received Length if the requestor or if
            the acceptor and they have accepted the negotiation. Returns
            ``None`` if the acceptor and they have rejected the negotiation.
        """
        if not self.writeable:
            for item in self.user_information:
                if isinstance(item, MaximumLengthNotification):
                    return item.maximum_length_received

            return None

        for item in self._user_info:
            if isinstance(item, MaximumLengthNotification):
                return item.maximum_length_received

        return None

    @maximum_length.setter
    def maximum_length(self, value: int) -> None:
        """Set the Maximum PDU Length (only prior to association).

        Parameters
        ----------
        value : int or None
            The value to use in the Maximum Length Negotiation.
        """
        if not self.writeable:
            raise RuntimeError(
                "Can't set the Maximum Length after negotiation has started"
            )

        for item in self._user_info:
            if isinstance(item, MaximumLengthNotification):
                item.maximum_length_received = value
                break
        else:
            item = MaximumLengthNotification()
            item.maximum_length_received = value
            self._user_info.append(item)

    @property
    def mode(self) -> str:
        """Return the mode as :class:`str`, either ``'requestor'`` or
        ``'acceptor'``.
        """
        return self._mode

    @property
    def port(self) -> int:
        """Get the requestor or acceptor's port number (if set)."""
        if self.address_info is None:
            raise ValueError("No address information has been set")

        return self.address_info.port

    @property
    def requested_contexts(self) -> list[PresentationContext]:
        """A :class:`list` of the requestor's requested presentation
        contexts.
        """
        if not self.writeable and self.assoc.is_acceptor:
            return self.get_contexts("pcdl")

        return self.get_contexts("requested")

    @requested_contexts.setter
    def requested_contexts(self, value: list[PresentationContext]) -> None:
        """Set the requested presentation contexts.

        Parameters
        ----------
        value : list of presentation.PresentationContext
            A list of the presentation contexts to propose when acting as the
            association requestor.

        Raises
        ------
        RuntimeError
            If attempting to set the contexts after negotiation has begun.
        AttributeError
            If attempting to set the contexts as the association acceptor.
        """
        if not self.writeable:
            raise RuntimeError(
                "Can't set the requested presentation contexts after "
                "negotiation has started"
            )

        if not self.is_requestor:
            raise AttributeError(
                "'requested_contexts' can only be set for the association requestor"
            )

        self._contexts = value

    def remove_negotiation_item(self, item: _UI) -> None:
        """Remove an extended negotiation item from the user information.

        Items can only be removed prior to starting the association
        negotiation.

        Parameters
        ----------
        item : pdu_primitives.ServiceParameter
            An extended negotiation item, one of:

            .. currentmodule:: pynetdicom.pdu_primitives

            * :class:`SCP_SCU_RoleSelectionNegotiation`
            * :class:`UserIdentityNegotiation`
            * :class:`AsynchronousOperationsWindowNegotiation`
            * :class:`SOPClassExtendedNegotiation`
            * :class:`SOPClassCommonExtendedNegotiation`

        Raises
        ------
        RuntimeError
            If attempting to remove an item after association negotiation has
            started.
        TypeError
            If `item` it not an extended negotiation item.
        """
        if not self.writeable:
            raise RuntimeError(
                "Can't remove extended negotiation items after negotiation "
                "has started"
            )

        # pylint: disable=unidiomatic-typecheck
        if type(item) in self._ext_neg:
            # Do nothing if item not in _ext_neg
            if item in self._ext_neg[type(item)]:
                self._ext_neg[type(item)].remove(item)
        else:
            raise TypeError("'item' is not a valid extended negotiation item")

    def reset_negotiation_items(self) -> None:
        """Remove all extended negotiation items.

        Items can only be removed prior to starting the association
        negotiation.

        Raises
        ------
        RuntimeError
            If attempting to clear the extended negotiation items after
            association negotiation has started.
        """
        if not self.writeable:
            raise RuntimeError(
                "Can't reset the extended negotiation items after negotiation "
                "has started"
            )

        self._ext_neg = {
            SCP_SCU_RoleSelectionNegotiation: [],
            AsynchronousOperationsWindowNegotiation: [],
            UserIdentityNegotiation: [],
            SOPClassExtendedNegotiation: [],
        }
        if self.is_requestor:
            self._ext_neg[SOPClassCommonExtendedNegotiation] = []

    @property
    def role_selection(self) -> dict[UID, SCP_SCU_RoleSelectionNegotiation]:
        """Return any SCP/SCU Role Selection items.

        Returns
        -------
        dict
            The SCP/SCU Role Selection items as ``{'SOP Class UID' :
            SCP_SCU_RoleSelectionNegotiation}``.
        """
        roles = {}
        if self.writeable:
            for item in self._ext_neg[SCP_SCU_RoleSelectionNegotiation]:
                item = cast(SCP_SCU_RoleSelectionNegotiation, item)
                roles[cast(UID, item.sop_class_uid)] = item

            return roles

        for item in self.user_information:
            if isinstance(item, SCP_SCU_RoleSelectionNegotiation):
                roles[cast(UID, item.sop_class_uid)] = item

        return roles

    @property
    def sop_class_common_extended(
        self,
    ) -> dict[UID, SOPClassCommonExtendedNegotiation]:
        """Return the SOP Class Common Extended items.

        If the :class:`ServiceUser` is the association acceptor then no SOP
        Class Common Extended items will be present in the User Information.

        Returns
        -------
        dict
            The SOP Class Common Extended items as
            ``{'SOP Class UID' : item}``.
        """
        if self.is_acceptor:
            return {}

        sop_classes = {}
        if self.writeable:
            for item in self._ext_neg[SOPClassCommonExtendedNegotiation]:
                item = cast(SOPClassCommonExtendedNegotiation, item)
                sop_classes[cast(UID, item.sop_class_uid)] = item

            return sop_classes

        for item in self.user_information:
            if isinstance(item, SOPClassCommonExtendedNegotiation):
                sop_classes[cast(UID, item.sop_class_uid)] = item

        return sop_classes

    @property
    def sop_class_extended(self) -> dict[UID, bytes]:
        """Return any SOP Class Extended items.

        Returns
        -------
        dict
            The SOP Class Extended items as ``{'SOP Class UID' : Service Class
            Application Information}``.
        """
        sop_classes = {}
        if self.writeable:
            for item in self._ext_neg[SOPClassExtendedNegotiation]:
                item = cast(SOPClassExtendedNegotiation, item)
                sop_classes[cast(UID, item.sop_class_uid)] = cast(
                    bytes, item.service_class_application_information
                )

            return sop_classes

        for item in self.user_information:
            if isinstance(item, SOPClassExtendedNegotiation):
                sop_classes[cast(UID, item.sop_class_uid)] = cast(
                    bytes, item.service_class_application_information
                )

        return sop_classes

    @property
    def supported_contexts(self) -> list[PresentationContext]:
        """The supported presentation contexts.

        Returns
        -------
        list of presentation.PresentationContext
            The supported presentation contexts when acting as an acceptor.
        """
        if not self.writeable and self.assoc.is_requestor:
            return self.get_contexts("pcdrl")

        return self.get_contexts("supported")

    @supported_contexts.setter
    def supported_contexts(self, value: list[PresentationContext]) -> None:
        """Set the supported presentation contexts.

        Parameters
        ----------
        value : list of presentation.PresentationContext
            A list of the presentation contexts to support when acting as the
            association acceptor.

        Raises
        ------
        RuntimeError
            If attempting to set the contexts after negotiation has begun.
        AttributeError
            If attempting to set the contexts as the association requestor.
        """
        if not self.writeable:
            raise RuntimeError(
                "Can't set the supported presentation contexts after "
                "negotiation has started"
            )

        if not self.is_acceptor:
            raise AttributeError(
                "'supported_contexts' can only be set for the association acceptor"
            )

        self._contexts = value

    @property
    def user_identity(self) -> UserIdentityNegotiation | None:
        """Return the User Identity Negotiation Item (if available).

        Returns
        -------
        pdu_primitives.UserIdentityNegotiation or None
            Returns the User Identity item if one is available, otherwise
            ``None``.
        """
        if self.writeable:
            items = self._ext_neg[UserIdentityNegotiation]
            if items:
                return cast(UserIdentityNegotiation, items[0])

            return None

        for item in self.user_information:
            if isinstance(item, UserIdentityNegotiation):
                return item

        return None

    @property
    def user_information(self) -> list[_UI]:
        """Returns a :class:`list` of the User Information items."""
        if not self.writeable:
            return cast(A_ASSOCIATE, self.primitive).user_information

        return self._user_info + self.extended_negotiation

    @property
    def writeable(self) -> bool:
        """Return ``True`` if the current object can be changed."""
        return self.primitive is None
