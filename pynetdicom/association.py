"""
Defines the Association class which handles associating with peers.
"""
import gc
from io import BytesIO
import logging
import threading
import time
import warnings

from pydicom.dataset import Dataset
from pydicom.uid import UID

# pylint: disable=no-name-in-module
from pynetdicom.acse import ACSE
from pynetdicom import _config, evt
from pynetdicom.dimse import DIMSEServiceProvider
from pynetdicom.dimse_primitives import (
    C_ECHO, C_MOVE, C_STORE, C_GET, C_FIND, C_CANCEL,
    N_EVENT_REPORT, N_GET, N_SET, N_CREATE, N_ACTION, N_DELETE
)
from pynetdicom.dsutils import decode, encode
from pynetdicom.dul import DULServiceProvider
from pynetdicom._globals import (
    MODE_REQUESTOR, MODE_ACCEPTOR, DEFAULT_MAX_LENGTH, STATUS_WARNING,
    STATUS_SUCCESS, STATUS_CANCEL, STATUS_PENDING, STATUS_FAILURE
)
from pynetdicom._handlers import (
    standard_dimse_recv_handler, standard_dimse_sent_handler,
    standard_pdu_recv_handler, standard_pdu_sent_handler,
)
from pynetdicom.sop_class import (
    uid_to_service_class,
    VerificationSOPClass,
    ModalityWorklistInformationFind,
    PatientRootQueryRetrieveInformationModelFind,
    StudyRootQueryRetrieveInformationModelFind,
    PatientStudyOnlyQueryRetrieveInformationModelFind,
    PatientRootQueryRetrieveInformationModelMove,
    StudyRootQueryRetrieveInformationModelMove,
    PatientStudyOnlyQueryRetrieveInformationModelMove,
    PatientRootQueryRetrieveInformationModelGet,
    StudyRootQueryRetrieveInformationModelGet,
    PatientStudyOnlyQueryRetrieveInformationModelGet,
    CompositeInstanceRetrieveWithoutBulkDataGet,
    GeneralRelevantPatientInformationQuery,
    BreastImagingRelevantPatientInformationQuery,
    CardiacRelevantPatientInformationQuery,
    ProductCharacteristicsQueryInformationModelFind,
    SubstanceApprovalQueryInformationModelFind,
    CompositeInstanceRootRetrieveGet,
    CompositeInstanceRootRetrieveMove,
    HangingProtocolInformationModelGet,
    HangingProtocolInformationModelFind,
    HangingProtocolInformationModelMove,
    DefinedProcedureProtocolInformationModelGet,
    DefinedProcedureProtocolInformationModelFind,
    DefinedProcedureProtocolInformationModelMove,
    ColorPaletteInformationModelGet,
    ColorPaletteInformationModelFind,
    ColorPaletteInformationModelMove,
    GenericImplantTemplateInformationModelGet,
    GenericImplantTemplateInformationModelFind,
    GenericImplantTemplateInformationModelMove,
    ImplantAssemblyTemplateInformationModelGet,
    ImplantAssemblyTemplateInformationModelFind,
    ImplantAssemblyTemplateInformationModelMove,
    ImplantTemplateGroupInformationModelFind,
    ImplantTemplateGroupInformationModelGet,
    ImplantTemplateGroupInformationModelMove,
    ProtocolApprovalInformationModelFind,
    ProtocolApprovalInformationModelGet,
    ProtocolApprovalInformationModelMove,
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
)
from pynetdicom.status import code_to_category, STORAGE_SERVICE_CLASS_STATUS


# pylint: enable=no-name-in-module
LOGGER = logging.getLogger('pynetdicom.assoc')


class Association(threading.Thread):
    """Manage an Association with a peer AE.

    Attributes
    ----------
    acceptor : association.ServiceUser
        Representation of the association's acceptor AE.
    acse : acse.ACSE
        The Association Control Service Element provider.
    ae : ae.ApplicationEntity
        The local AE.
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
    mode : str
        The mode of the local AE, either the association 'requestor' or
        association 'acceptor'.
    requestor : association.ServiceUser
        Representation of the association's requestor AE.
    """
    def __init__(self, ae, mode):
        """Create a new ``Association`` instance.

        The association starts in State 1 (idle). Association negotiation
        won't begin until an ``AssociationSocket`` is assigned using
        ``set_socket()`` and ``Association.start_server()`` is called.

        Parameters
        ----------
        ae : ae.ApplicationEntity
            The local AE.
        mode : str
            Must be ``"requestor"`` or ``"acceptor"``.
        """
        self._ae = ae
        self.mode = mode

        # If acceptor this is the parent AssociationServer, used to identify
        #   the thread when updating bound event-handlers
        self._server = None

        # Represents the association requestor and acceptor users
        self.requestor = ServiceUser(self, MODE_REQUESTOR)
        self.acceptor = ServiceUser(self, MODE_ACCEPTOR)

        # Status attributes
        self.is_established = False
        self.is_rejected = False
        self.is_aborted = False
        self.is_released = False

        # Accepted and rejected presentation contexts
        self._accepted_cx = {}
        self._rejected_cx = []

        # Service providers
        self.acse = ACSE(self)
        self.dul = DULServiceProvider(self)
        self.dimse = DIMSEServiceProvider(self)

        # Timeouts (in seconds), needs to be set after DUL init
        self.acse_timeout = self.ae.acse_timeout
        self.dimse_timeout = self.ae.dimse_timeout
        self.network_timeout = self.ae.network_timeout

        # Event handlers
        self._handlers = {}
        self._bind_defaults()

        # Kills the thread loop in run()
        self._kill = False
        # Flag for whether or not the DUL thread has been started
        self._started_dul = False
        # Used to pause the association reactor until the DUL is ready
        self._dul_ready = threading.Event()
        # Used to pause the association reactor while a service is being used
        self._reactor_checkpoint = threading.Event()
        self._reactor_checkpoint.set()

        # Thread setup
        threading.Thread.__init__(self)
        self.daemon = True

    def abort(self):
        """Send an A-ABORT to the remote AE and kill the ``Association``."""
        if not self.is_released:
            # Ensure the reactor is running so it can be exited
            self._reactor_checkpoint.set()
            LOGGER.info('Aborting Association')
            self.acse.send_abort(0x00)
            # Event handler - association aborted
            evt.trigger(self, evt.EVT_ABORTED, {})
            self.kill()

        # Add short delay to ensure everything shuts down
        time.sleep(0.1)

    @property
    def accepted_contexts(self):
        """Return a list of accepted ``PresentationContexts``."""
        # Accepted contexts are stored internally as {context ID : context}
        return sorted(self._accepted_cx.values(), key=lambda x: x.context_id)

    @property
    def acse_timeout(self):
        """Return the ACSE timeout in seconds."""
        return self._acse_timeout

    @acse_timeout.setter
    def acse_timeout(self, value):
        """Set the ACSE timeout using numeric or ``None``."""
        with threading.Lock():
            self.dul.artim_timer.timeout = value
            self._acse_timeout = value

    @property
    def ae(self):
        """Return the Association's parent ``ApplicationEntity``."""
        return self._ae

    def bind(self, event, handler):
        """Bind a callable `handler` to an `event`.

        Parameters
        ----------
        event : namedtuple
            The event to bind the function to.
        handler : callable
            The function that will be called if the event occurs.
        """
        # Make sure no access to `_handlers` while its being changed
        with threading.Lock():
            # Notification events - multiple handlers allowed
            if event.is_notification:
                if event not in self._handlers:
                    self._handlers[event] = []
                if handler not in self._handlers[event]:
                    self._handlers[event].append(handler)

            # Intervention events - only one handler allowed
            if event.is_intervention:
                if event not in self._handlers:
                    self._handlers[event] = None

                if self._handlers[event] != handler:
                    self._handlers[event] = handler

    def _bind_defaults(self):
        """Bind the default event handlers."""
        # Intervention event handlers
        for event in evt._INTERVENTION_EVENTS:
            handler = evt.get_default_handler(event)
            self.bind(event, handler)

        # Notification event handlers
        if _config.LOG_HANDLER_LEVEL == 'standard':
            self.bind(evt.EVT_DIMSE_RECV, standard_dimse_recv_handler)
            self.bind(evt.EVT_DIMSE_SENT, standard_dimse_sent_handler)
            self.bind(evt.EVT_PDU_RECV, standard_pdu_recv_handler)
            self.bind(evt.EVT_PDU_SENT, standard_pdu_sent_handler)

    def _check_received_status(self, rsp):
        """Return a pydicom ``Dataset`` containing status related elements.

        Parameters
        ----------
        rsp : dimse_primitives.DIMSEMessage
            The DIMSE Message primitive received from the peer in response
            to a service request.

        Returns
        -------
        pydicom.dataset.Dataset
            If no response or an invalid response was received from the peer
            then an empty ``Dataset``, if a valid response was received from
            the peer then (at a minimum) a ``Dataset`` containing an
            (0000,0900) *Status* element, and any included optional status
            related elements.
        """
        msg_type = rsp.__class__.__name__
        msg_type = msg_type.replace('_', '-')

        status = Dataset()
        if rsp.is_valid_response:
            status.Status = rsp.Status
            for keyword in rsp.STATUS_OPTIONAL_KEYWORDS:
                if getattr(rsp, keyword, None) is not None:
                    setattr(status, keyword, getattr(rsp, keyword))
        else:
            LOGGER.error(
                "Received an invalid {} response from the peer"
                .format(msg_type)
            )
            self.abort()

        return status

    @property
    def dimse_timeout(self):
        """Return the DIMSE timeout in seconds."""
        return self._dimse_timeout

    @dimse_timeout.setter
    def dimse_timeout(self, value):
        """Set the DIMSE timeout using numeric or ``None``."""
        with threading.Lock():
            self._dimse_timeout = value

    def get_events(self):
        """Return a list of currently bound events."""
        return sorted(self._handlers.keys(), key=lambda x: x.name)

    def get_handlers(self, event):
        """Return handlers bound to a specific `event`.

        Parameters
        ----------
        event : namedtuple
            The event bound to the handlers.

        Returns
        -------
        callable, list of callable or None
            If the event is a notification event then returns a list of
            callable functions bound to `event`, if the event is an
            intervention event then returns either a callable function if a
            handler is bound to the event or None if no handler has been bound.
        """
        if event not in self._handlers:
            return []

        return self._handlers[event]

    def _get_valid_context(self, ab_syntax, tr_syntax, role, context_id=None):
        """Return a valid presentation context matching the parameters.

        Parameters
        ----------
        ab_syntax : str or pydicom.uid.UID
            The abstract syntax to match.
        tr_syntax : str or pydicom.uid.UID
            The transfer syntax to match, if an empty string is used then
            the transfer syntax will not be used for matching. If the value
            corresponds to an uncompressed syntax then matches will be made
            with any uncompressed transfer syntaxes.
        role : str or None
            One of 'scu' or 'scp', the required role of the context. If None
            then the accepted role will be ignored.
        context_id : int or None
            If not None then the ID of the presentation context to use. It will
            be checked against the available parameter values.

        Returns
        -------
        presentation.PresentationContext
            An accepted presentation context.
        """
        ab_syntax = UID(ab_syntax)
        tr_syntax = UID(tr_syntax)

        possible_contexts = []
        if context_id is None:
            possible_contexts = self.accepted_contexts
        else:
            for cx in self.accepted_contexts:
                if cx.context_id == context_id:
                    possible_contexts = [cx]
                    break

        for cx in possible_contexts:
            if cx.abstract_syntax != ab_syntax:
                continue

            # Cover both False and None
            if role == 'scu' and cx.as_scu is not True:
                continue

            if role == 'scp' and cx.as_scp is not True:
                continue

            # Allow us to skip the transfer syntax check
            if tr_syntax and tr_syntax != cx.transfer_syntax[0]:
                # Compressed transfer syntaxes are not convertable
                if (tr_syntax.is_compressed
                        or cx.transfer_syntax[0].is_compressed):
                    continue

            # Only a valid presentation context can reach this point
            return cx

        role = role or 'scu'
        msg = (
            "No suitable presentation context for the {} role has been "
            "accepted by the peer for the SOP Class '{}'"
            .format(role.upper(), ab_syntax.name)
        )
        if tr_syntax:
            msg += " with a transfer syntax of '{}'".format(tr_syntax.name)

        LOGGER.error(msg)
        raise ValueError(msg)

    @property
    def is_acceptor(self):
        """Return ``True`` if the local AE is the association *Acceptor*."""
        return self.mode == MODE_ACCEPTOR

    @property
    def is_requestor(self):
        """Return ``True`` if the local AE is the association *Requestor*."""
        return self.mode == MODE_REQUESTOR

    def kill(self):
        """Kill the ``Association`` thread."""
        # Ensure the reactor is running so it can be exited
        self._reactor_checkpoint.set()
        self._kill = True
        self.is_established = False
        while self.dul.is_alive() and not self.dul.stop_dul():
            time.sleep(0.01)

    @property
    def local(self):
        """Return a dict with information about the local AE."""
        if self.is_acceptor:
            return self.acceptor.info

        return self.requestor.info

    @property
    def mode(self):
        """Return the Association's `mode` as a str."""
        return self._mode

    @mode.setter
    def mode(self, mode):
        """Set the Association's mode.

        Parameters
        ----------
        mode : str
            The mode of the Association, must be either ``"requestor"`` or
            ``"acceptor"``. If ``"requestor"`` then its assumed that the local
            AE requests an association with peers and (by default) acts as the
            SCU. If ``"acceptor"`` then its assumed that the local AE is
            listening for association requests and (by default) acts as the SCP.
        """
        mode = mode.lower()
        if mode not in [MODE_REQUESTOR, MODE_ACCEPTOR]:
            raise ValueError(
                "Invalid association `mode` value, must be either 'requestor' "
                "or 'acceptor'"
            )

        # pylint: disable=attribute-defined-outside-init
        self._mode = mode

    @property
    def network_timeout(self):
        """Return the network timeout in seconds."""
        return self._network_timeout

    @network_timeout.setter
    def network_timeout(self, value):
        """Set the network timeout using numeric or ``None``."""
        with threading.Lock():
            self.dul._idle_timer.timeout = value
            self._network_timeout = value

    @property
    def rejected_contexts(self):
        """Return a list of rejected ``PresentationContext``."""
        return self._rejected_cx

    def release(self):
        """Send an A-RELEASE request and initiate association release."""
        if self.is_established:
            # Ensure the reactor is paused so it doesn't
            #   steal incoming ACSE messages
            self._reactor_checkpoint.clear()
            LOGGER.info('Releasing Association')
            self.acse.negotiate_release()
            # Restart reactor
            self._reactor_checkpoint.set()

    @property
    def remote(self):
        """Return a dict with information about the peer AE."""
        if self.is_acceptor:
            return self.requestor.info

        return self.acceptor.info

    def request(self):
        """Request an association with a peer.

        A request can only be made once the ``Association`` instance has been
        configured for requestor mode and been assigned an
        ``AssociationSocket``.
        """
        # Start the DUL thread if not already started
        self.dul.start()
        self._started_dul = True
        # Wait until the DUL is up and running
        self._dul_ready.wait()
        # Start association negotiation
        LOGGER.info("Requesting Association")
        self.acse.negotiate_association()

    def run(self):
        """The main ``Association`` reactor."""
        # Start the DUL thread if not already started
        if not self._started_dul:
            self.dul.start()
            self._started_dul = True
            # Wait until the DUL is up and running
            self._dul_ready.wait()

        if self.is_acceptor:
            primitive = self.dul.receive_pdu(wait=True,
                                             timeout=self.acse_timeout)

            # Timed out waiting for A-ASSOCIATE request
            if primitive is None:
                self.kill()
                return

            self.requestor.primitive = primitive
            evt.trigger(self, evt.EVT_REQUESTED, {})

            self.acse.negotiate_association()
            if self.is_established:
                self._run_reactor()
        else:
            # Association requestor
            # Allow non-blocking negotiation
            if (not self.is_established and not self.is_aborted
                    and not self.is_released and not self.is_rejected):
                self.acse.negotiate_association()

            if self.is_established:
                self._run_reactor()

    def _run_reactor(self):
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
        while not self._kill:
            # A race condition may occur if the Acceptor uses the send_*()
            #   methods as the received DIMSE message may be taken off the
            #   queue before the send_*() method gets to it, so we allow
            #   the reactor to be paused
            # Will block until `_reactor_checkpoint` is True
            self._reactor_checkpoint.wait()

            time.sleep(0.001)

            # Check with the DIMSE provider to see if a completely decoded
            #   message is available
            context_id, msg = self.dimse.get_msg(block=False)
            if msg:
                self._serve_request(msg, context_id)

            # Check for release request
            if self.acse.is_release_requested():
                # Send A-RELEASE response
                self.acse.send_release(is_response=True)
                LOGGER.info('Association Released')
                self.is_released = True
                self.is_established = False
                evt.trigger(self, evt.EVT_RELEASED, {})
                self.kill()
                return

            # Check for abort
            if self.acse.is_aborted():
                LOGGER.info('Association Aborted')
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

            # Check if idle timer has expired
            if self.dul.idle_timer_expired():
                self.abort()
                self.kill()
                return

    def set_socket(self, socket):
        """Set the socket to use for communicating with the peer.

        Parameters
        ----------
        socket : transport.AssociationSocket
            The socket to use.

        Raises
        ------
        RuntimeError
            If the Association already has a socket set.
        """
        if self.dul.socket is not None:
            raise RuntimeError("The Association already has a socket set.")

        self.dul.socket = socket

    def unbind(self, event, handler):
        """Unbind a callable `func` from an `event`.

        Parameters
        ----------
        event : namedtuple
            The event to unbind the function from.
        handler : callable
            The function that will no longer be called if the event occurs.
        """
        if event not in self._handlers:
            return

        # Make sure no access to `_handlers` while its being changed
        with threading.Lock():
            # Notification events
            if event.is_notification and handler in self._handlers[event]:
                self._handlers[event].remove(handler)

                if not self._handlers[event]:
                    del self._handlers[event]

            # Intervention events - unbind and replace with default
            if event.is_intervention and self._handlers[event] == handler:
                self._handlers[event] = evt.get_default_handler(event)

    # DIMSE-C services provided by the Association
    def _c_store_scp(self, req):
        """A C-STORE SCP implementation.

        Handles C-STORE requests from the peer over the same assocation as the
        local AE sent a C-MOVE or C-GET request.

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
                req.AffectedSOPClassUID,
                '',
                'scp',
                context_id=req._context_id
            )
        except ValueError:
            # SOP Class not supported, no context ID?
            rsp.Status = 0x0122
            self.dimse.send_msg(rsp, 1)
            return

        # Attempt to handle the service request
        try:
            status = evt.trigger(
                self,
                evt.EVT_C_STORE,
                {'request' : req, 'context' : context.as_tuple}
            )
        except Exception as ex:
            LOGGER.error(
                "Exception in the handler bound to 'evt.EVT_C_STORE'"
            )
            LOGGER.exception(ex)
            rsp.Status = 0xC211
            self.dimse.send_msg(rsp, context.context_id)
            return

        # Check the callback's returned status
        if isinstance(status, Dataset):
            if 'Status' in status:
                # For the elements in the status dataset, try and set
                #   the corresponding response primitive attribute
                for elem in status:
                    if hasattr(rsp, elem.keyword):
                        setattr(rsp, elem.keyword, elem.value)
                    else:
                        LOGGER.warning("Status dataset returned by "
                                       "callback contained an "
                                       "unsupported element '%s'.",
                                       elem.keyword)
            else:
                LOGGER.error("User callback returned a `Dataset` "
                             "without a Status element.")
                rsp.Status = 0xC001
        elif isinstance(status, int):
            rsp.Status = status
        else:
            LOGGER.error("Invalid status returned by user callback.")
            rsp.Status = 0xC002

        if not rsp.Status in STORAGE_SERVICE_CLASS_STATUS:
            LOGGER.warning("Unknown status value returned by callback "
                           "- 0x{0:04x}".format(rsp.Status))

        # Send C-STORE confirmation back to peer
        self.dimse.send_msg(rsp, context.context_id)

    def send_c_cancel(self, msg_id, context_id):
        """Send a C-CANCEL request to the peer AE.

        Parameters
        ----------
        msg_id : int
            The *Message ID* of the C-GET/C-MOVE/C-FIND operation to be
            cancelled. Must be between 0 and 65535, inclusive.
        context_id : int
            The presentation context ID of the original C-GET/C-MOVE/C-FIND
            service request.
        """
        # Can't send a C-CANCEL without an Association
        if not self.is_established:
            raise RuntimeError(
                "The association with a peer SCP must be "
                "established before sending a C-CANCEL request."
            )

        # Build C-CANCEL primitive
        primitive = C_CANCEL()
        primitive.MessageIDBeingRespondedTo = msg_id

        LOGGER.info('Sending C-CANCEL')

        # Send C-CANCEL request
        self.dimse.send_msg(primitive, context_id)

    def send_c_echo(self, msg_id=1):
        """Send a C-ECHO request to the peer AE.

        Parameters
        ----------
        msg_id : int, optional
            The DIMSE *Message ID*, must be between 0 and 65535, inclusive,
            (default 1).

        Returns
        -------
        status : pydicom.dataset.Dataset
            If the peer timed out, aborted or sent an invalid response then
            returns an empty ``Dataset``. If a valid response was received from
            the peer then returns a ``Dataset`` containing at least a
            (0000,0900) *Status* element, and, depending on the returned
            *Status* value, may optionally contain additional elements (see
            DICOM Standard Part 7, Annex C).

            The DICOM Standard Part 7, Table 9.3-13 indicates that the Status
            value of a C-ECHO response "shall have a value of Success". However
            Section 9.1.5.1.4 indicates it may have any of the following
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
            If the association has no accepted Presentation Context for
            'Verification SOP Class'.

        See Also
        --------
        dimse_primitives.C_ECHO
        service_class.VerificationServiceClass

        References
        ----------

        * DICOM Standard Part 4, `Annex A <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_A>`_
        * DICOM Standard Part 7, Sections
          `9.1.5 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.1.5>`_,
          `9.3.5 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.5>`_,
          and `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_
        """
        # Can't send a C-ECHO without an Association
        if not self.is_established:
            raise RuntimeError("The association with a peer SCP must be "
                               "established before sending a C-ECHO request")

        # Get a Presentation Context to use for sending the message
        context = self._get_valid_context(VerificationSOPClass, '', 'scu')

        # Build C-STORE request primitive
        #   (M) Message ID
        #   (M) Affected SOP Class UID
        primitive = C_ECHO()
        primitive.MessageID = msg_id
        primitive.AffectedSOPClassUID = VerificationSOPClass

        # Send C-ECHO request to the peer via DIMSE and wait for the response
        LOGGER.info('Sending Echo Request: MsgID {}'.format(msg_id))

        # Pause the reactor to prevent a race condition
        self._reactor_checkpoint.clear()

        self.dimse.send_msg(primitive, context.context_id)
        cx_id, rsp = self.dimse.get_msg(block=True)

        # Unpause the reactor
        self._reactor_checkpoint.set()

        # If `rsp` is None then the DIMSE timeout expired so abort
        if rsp is None:
            if self.is_established:
                LOGGER.error("Connection closed or timed-out")
                self.abort()
            return Dataset()

        # Determine validity of the response and get the status
        status = self._check_received_status(rsp)

        return status

    def send_c_find(self, dataset, query_model, msg_id=1, priority=2):
        """Send a C-FIND request to the peer AE.

        Yields ``(status, identifier)`` pairs.

        Parameters
        ----------
        dataset : pydicom.dataset.Dataset
            The C-FIND request's *Identifier* dataset. The exact requirements
            for the *Identifier* dataset are Service Class specific (see the
            DICOM Standard, Part 4).
        query_model : pydicom.uid.UID or str
            The value to use for the C-FIND request's (0000,0002) *Affected
            SOP Class UID* parameter, which usually corresponds to the
            Information Model that is to be used. If supplying a ``str`` key
            (deprecated, to be removed in v1.5.0) then one of the following:

            - ``P`` - 1.2.840.10008.5.1.4.1.2.1.1  -
              *Patient Root Information Model - FIND*
            - ``S`` - 1.2.840.10008.5.1.4.1.2.2.1 -
              *Study Root Information Model - FIND*
            - ``O`` - 1.2.840.10008.5.1.4.1.2.3.1 -
              *Patient Study Only Information Model - FIND*
            - ``W`` - 1.2.840.10008.5.1.4.31 -
              *Modality Worklist Information - FIND*
            - ``G`` - 1.2.840.10008.5.1.4.37.1 -
              *General Relevant Patient Information Query*
            - ``B`` - 1.2.840.10008.5.1.4.37.2 -
              *Breast Imaging Relevant Patient Information Query*
            - ``C`` - 1.2.840.10008.5.1.4.37.3 -
              *Cardiac Relevant Patient Information Query*
            - ``PC`` - 1.2.840.10008.5.1.4.41 -
              *Product Characteristics Query Information Model - FIND*
            - ``SA`` - 1.2.840.10008.5.1.4.42 -
              *Substance Approval Query Information Model - FIND*
            - ``H`` - 1.2.840.10008.5.1.4.38.2 -
              *Hanging Protocol Information Model - FIND*
            - ``D`` - 1.2.840.10008.5.1.4.20.1 -
              *Defined Procedure Protocol Information Model - FIND*
            - ``CP`` - 1.2.840.10008.5.1.4.39.2 -
              *Color Palette Information Model - FIND*
            - ``IG`` - 1.2.840.10008.5.1.4.43.2 -
              *Generic Implant Template Information Model - FIND*
            - ``IA`` - 1.2.840.10008.5.1.4.44.2 -
              *Implant Assembly Template Information Model - FIND*
            - ``IT`` - 1.2.840.10008.5.1.4.44.2 -
              *Implant Template Group Information Model - FIND*
            - ``PA`` - 1.2.840.10008.5.1.4.1.1.200.4 -
              *Protocol Approval Information Model - FIND*
        msg_id : int, optional
            The DIMSE *Message ID*, must be between 0 and 65535, inclusive,
            (default 1).
        priority : int, optional
            The C-FIND operation *Priority* (may not be supported by the peer),
            one of:

            - ``0`` - Medium
            - ``1`` - High
            - ``2`` - Low (default)

        Yields
        ------
        status : pydicom.dataset.Dataset
            If the peer timed out, aborted or sent an invalid response then
            yields an empty ``Dataset``. If a response was received from the
            peer then yields a ``Dataset`` containing at least a (0000,0900)
            *Status* element, and depending on the returned value, may
            optionally contain additional elements (see the DICOM Standard,
            Part 7, Section 9.1.2.1.5 and Annex C).

            The status for the requested C-FIND operation should be one of the
            following values, but as the value depends
            on the peer this can't be assumed:

            *General C-FIND* (Part 7, Section 9.1.2.1.5 and Annex C)

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
            Query/Retrieve Service*, *Protocol Approval Query/Retrieve
            Service* and *Unified Protocol Step Service* specific
            (DICOM Standard Part 4, Annexes C.4.1, K.4.1.1.4, U.4.1, HH,
            V.4.1.1.4, X, BB, II and CC):

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
            *Identifier* ``Dataset``. If the status category is not 'Pending'
            this will be ``None``. The exact contents of the response
            *Identifier* are Service Class specific (see the DICOM Standard,
            Part 4).

        Raises
        ------
        RuntimeError
            If ``send_c_find`` is called with no established association.
        ValueError
            If no accepted Presentation Context for `dataset` exists or if
            unable to encode the *Identifier* `dataset`.

        See Also
        --------
        dimse_primitives.C_FIND
        service_class.ColorPaletteQueryRetrieveServiceClass
        service_class.DefinedProcedureProtocolQueryRetrieveServiceClass
        service_class.HangingProtocolQueryRetrieveServiceClass
        service_class.ImplantTemplateQueryRetrieveServiceClass
        service_class.ProtocolApprovalQueryRetrieveServiceClass
        service_class.QueryRetrieveFindServiceClass
        service_class.RelevantPatientInformationQueryServiceClass
        service_class.SubstanceAdministrationQueryServiceClass
        service_class.UnifiedProcedureStepServiceClass

        References
        ----------

        * DICOM Standard Part 4, `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_C>`_
        * DICOM Standard Part 4, `Annex Q <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_Q>`_
        * DICOM Standard Part 4, `Annex U <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_U>`_
        * DICOM Standard Part 4, `Annex V <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_V>`_
        * DICOM Standard Part 4, `Annex X <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_X>`_
        * DICOM Standard Part 4, `Annex BB <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_BB>`_
        * DICOM Standard Part 4, `Annex HH <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_HH>`_
        * DICOM Standard Part 4, `Annex II <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_II>`_
        * DICOM Standard Part 7, Sections
          `9.1.2 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.1.2>`_,
          `9.3.2 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.2>`_,
          Annexes `C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_
          and `K <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_K>`_
        """
        # Can't send a C-FIND without an Association
        if not self.is_established:
            raise RuntimeError("The association with a peer SCP must be "
                               "established before sending a C-FIND request")

        # TODO: refactor in v1.5
        # Try the UID first
        sop_class = UID(query_model)
        if not sop_class.is_valid:
            # Try the str
            _sop_classes = {
                'W' : ModalityWorklistInformationFind,
                "P" : PatientRootQueryRetrieveInformationModelFind,
                "S" : StudyRootQueryRetrieveInformationModelFind,
                "O" : PatientStudyOnlyQueryRetrieveInformationModelFind,
                "G" : GeneralRelevantPatientInformationQuery,
                "B" : BreastImagingRelevantPatientInformationQuery,
                "C" : CardiacRelevantPatientInformationQuery,
                "PC" : ProductCharacteristicsQueryInformationModelFind,
                "SA" : SubstanceApprovalQueryInformationModelFind,
                "H" : HangingProtocolInformationModelFind,
                "D" : DefinedProcedureProtocolInformationModelFind,
                "CP" : ColorPaletteInformationModelFind,
                "IG" : GenericImplantTemplateInformationModelFind,
                "IA" : ImplantAssemblyTemplateInformationModelFind,
                "IT" : ImplantTemplateGroupInformationModelFind,
                "PA" : ProtocolApprovalInformationModelFind,
            }

            try:
                sop_class = _sop_classes[query_model]
                warnings.warn(
                    "Using `query_model` with a key that corresponds to a "
                    "given UID is deprecated and will be removed in v1.5. "
                    "Pass the required UID directly instead.",
                    DeprecationWarning
                )
            except KeyError:
                raise ValueError(
                    "Unsupported value for `query_model`: {}"
                    .format(query_model)
                )

        # Determine the Presentation Context we are operating under
        #   and hence the transfer syntax to use for encoding `dataset`
        context = self._get_valid_context(sop_class, '', 'scu')

        # Build C-FIND request primitive
        #   (M) Message ID
        #   (M) Affected SOP Class UID
        #   (M) Priority
        #   (M) Identifier
        req = C_FIND()
        req.MessageID = msg_id
        req.AffectedSOPClassUID = sop_class
        req.Priority = priority

        # Encode the Identifier `dataset` using the agreed transfer syntax
        #   Will return None if failed to encode
        transfer_syntax = context.transfer_syntax[0]
        bytestream = encode(dataset,
                            transfer_syntax.is_implicit_VR,
                            transfer_syntax.is_little_endian)

        if bytestream is not None:
            req.Identifier = BytesIO(bytestream)
        else:
            LOGGER.error("Failed to encode the supplied Dataset")
            raise ValueError('Failed to encode the supplied Dataset')

        LOGGER.info('Sending Find Request: MsgID {}'.format(msg_id))
        LOGGER.info('')
        LOGGER.info('# Identifier DICOM Dataset')
        for elem in dataset:
            LOGGER.info(elem)
        LOGGER.info('')

        # Pause the reactor to prevent a race condition
        self._reactor_checkpoint.clear()

        # Send C-FIND request to the peer via DIMSE
        self.dimse.send_msg(req, context.context_id)

        # Get the responses from the peer
        # Wrap the generator so the C-FIND-RQ is sent immediately on
        #   executing this function, otherwise sending C-CANCEL requests
        #   may end up being sent first unless next() is called
        return self._wrap_find_responses(transfer_syntax)

    def send_c_get(self, dataset, query_model, msg_id=1, priority=2):
        """Send a C-GET request to the peer AE.

        Yields ``(status, identifier)`` pairs.

        A :py:meth:`handler <pynetdicom._handlers.doc_handle_store>`
        should be implemented and bound to ``evt.EVT_C_STORE``
        prior to calling ``send_c_get`` as the peer will return any matches
        via a C-STORE sub-operation over the current association. In addition,
        SCP/SCU Role Selection Negotiation must be supported by the
        Association.

        Parameters
        ----------
        dataset : pydicom.dataset.Dataset
            The C-GET request's *Identifier* ``Dataset``. The exact
            requirements for the *Identifier* are Service Class specific (see
            the DICOM Standard, Part 4).
        query_model : pydicom.uid.UID or str
            The value to use for the C-GET request's (0000,0002) *Affected
            SOP Class UID* parameter, which usually corresponds to the
            Information Model that is to be used. If supplying a ``str`` key
            (deprecated, to be removed in v1.5.0) then one of the following:

            - ``P`` - 1.2.840.10008.5.1.4.1.2.1.3 -
              *Patient Root Information Model - GET*
            - ``S`` - 1.2.840.10008.5.1.4.1.2.2.3 -
              *Study Root Information Model - GET*
            - ``O`` - 1.2.840.10008.5.1.4.1.2.3.3 -
              *Patient Study Only Information Model - GET*
            - ``C`` - 1.2.840.10008.5.1.4.1.2.4.3 -
              *Composite Instance Root Retrieve - GET*
            - ``CB`` - 1.2.840.10008.5.1.4.1.2.5.3 -
              *Composite Instance Retrieve Without Bulk Data - GET*
            - ``H`` - 1.2.840.10008.5.1.4.38.4 -
              *Hanging Protocol Information Model - GET*
            - ``D`` - 1.2.840.10008.5.1.4.20.3 -
              *Defined Procedure  Protocol Information Model - GET*
            - ``CP`` - 1.2.840.10008.5.1.4.39.4 -
              *Palette Color Information Model - GET*
            - ``IG`` - 1.2.840.10008.5.1.4.43.4 -
              *Generic Implant Template Information Model - GET*
            - ``IA`` - 1.2.840.10008.5.1.4.44.4 -
              *Implant Assembly Template Information Model - GET*
            - ``IT`` - 1.2.840.10008.5.1.4.44.4 -
              *Implant Template Group Information Model - GET*
            - ``PA`` - 1.2.840.10008.5.1.4.1.1.200.6 -
              *Protocol Approval Information Model - GET*
        msg_id : int, optional
            The DIMSE *Message ID*, must be between 0 and 65535, inclusive,
            (default 1).
        priority : int, optional
            The C-GET operation *Priority* (may not be supported by the peer),
            one of:

            - ``0`` - Medium
            - ``1`` - High
            - ``2`` - Low (default)

        Yields
        ------
        status : pydicom.dataset.Dataset
            If the peer timed out, aborted or sent an invalid response then
            yields an empty ``Dataset``. If a response was received from the
            peer then yields a ``Dataset`` containing at least a (0000,0900)
            *Status* element, and depending on the returned value may
            optionally contain additional elements (see DICOM Standard Part 7,
            Section 9.1.2.1.5 and Annex C).

            The status for the requested C-GET operation should be one of the
            following values, but as the value depends on the peer this
            can't be assumed:

            *General C-GET* (DICOM Standard Part 7, Section 9.1.3 and Annex C)

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
            Service* and *Protocol Approval Query/Retrieve Service* specific
            (DICOM Standard Part 4, Annexes C.4.3,
            Y.C.4.2.1.4, Z.4.2.1.4, U.4.3, X, BB, HH and II):

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
            'Cancel' then yields a ``Dataset`` which should contain an
            (0008,0058) *Failed SOP Instance UID List* element, however this
            is not guaranteed and may instead be an empty ``Dataset``.

        Raises
        ------
        RuntimeError
            If ``send_c_get`` is called with no established association.
        ValueError
            If no accepted Presentation Context for `dataset` exists or if
            unable to encode the *Identifier* `dataset`.

        See Also
        --------
        service_class.QueryRetrieveGetServiceClass
        service_class.HangingProtocolQueryRetrieveServiceClass
        service_class.DefinedProcedureProtocolQueryRetrieveServiceClass
        service_class.ColorPaletteQueryRetrieveServiceClass
        service_class.ImplantTemplateQueryRetrieveServiceClass
        service_class.ProtocolApprovalQueryRetrieveServiceClass
        dimse_primitives.C_GET

        References
        ----------

        * DICOM Standard Part 4, `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_C>`_
        * DICOM Standard Part 4, `Annex U <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_U>`_
        * DICOM Standard Part 4, `Annex X <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_X>`_
        * DICOM Standard Part 4, `Annex Y <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_Y>`_
        * DICOM Standard Part 4, `Annex Z <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_Z>`_
        * DICOM Standard Part 4, `Annex BB <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_BB>`_
        * DICOM Standard Part 4, `Annex HH <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_HH>`_
        * DICOM Standard Part 4, `Annex II <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_II>`_
        * DICOM Standard Part 7, Sections
          `9.1.3 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.1.3>`_,
          `9.3.3 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.3>`_
          and `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_
        """
        # Can't send a C-GET without an Association
        if not self.is_established:
            raise RuntimeError("The association with a peer SCP must be "
                               "established before sending a C-GET request")

        # TODO: refactor in v1.5
        sop_class = UID(query_model)
        if not sop_class.is_valid:
            _sop_classes = {
                "P" : PatientRootQueryRetrieveInformationModelGet,
                "S" : StudyRootQueryRetrieveInformationModelGet,
                "O" : PatientStudyOnlyQueryRetrieveInformationModelGet,
                "C" : CompositeInstanceRootRetrieveGet,
                "CB" : CompositeInstanceRetrieveWithoutBulkDataGet,
                "H" : HangingProtocolInformationModelGet,
                "D" : DefinedProcedureProtocolInformationModelGet,
                "CP" : ColorPaletteInformationModelGet,
                "IG" : GenericImplantTemplateInformationModelGet,
                "IA" : ImplantAssemblyTemplateInformationModelGet,
                "IT" : ImplantTemplateGroupInformationModelGet,
                "PA" : ProtocolApprovalInformationModelGet,
            }

            try:
                sop_class = _sop_classes[query_model]
                warnings.warn(
                    "Using `query_model` with a key that corresponds to a "
                    "given UID is deprecated and will be removed in v1.5. "
                    "Pass the required UID directly instead.",
                    DeprecationWarning
                )
            except KeyError:
                raise ValueError(
                    "Unsupported value for `query_model`: {}"
                    .format(query_model)
                )

        # Determine the Presentation Context we are operating under
        #   and hence the transfer syntax to use for encoding `dataset`
        context = self._get_valid_context(sop_class, '', 'scu')

        # Build C-GET request primitive
        #   (M) Message ID
        #   (M) Affected SOP Class UID
        #   (M) Priority
        #   (M) Identifier
        req = C_GET()
        req.MessageID = msg_id
        req.AffectedSOPClassUID = sop_class
        req.Priority = priority

        # Encode the Identifier `dataset` using the agreed transfer syntax
        #   Will return None if failed to encode
        transfer_syntax = context.transfer_syntax[0]
        bytestream = encode(dataset,
                            transfer_syntax.is_implicit_VR,
                            transfer_syntax.is_little_endian)

        if bytestream is not None:
            req.Identifier = BytesIO(bytestream)
        else:
            LOGGER.error("Failed to encode the supplied Identifier dataset")
            raise ValueError('Failed to encode the supplied Identifer '
                             'dataset')

        LOGGER.info('Sending Get Request: MsgID {}'.format(msg_id))
        LOGGER.info('')
        LOGGER.info('# Identifier DICOM Dataset')
        for elem in dataset:
            LOGGER.info(elem)
        LOGGER.info('')

        # Pause the reactor to prevent a race condition
        self._reactor_checkpoint.clear()

        # Send C-GET request to the peer via DIMSE
        self.dimse.send_msg(req, context.context_id)

        # Get the responses from the peer
        # Wrap the generator so the C-GET-RQ is sent immediately on
        #   executing this function, otherwise sending C-CANCEL requests
        #   may end up being sent first unless next() is called
        return self._wrap_get_move_responses(transfer_syntax)

    def send_c_move(self, dataset, move_aet, query_model, msg_id=1,
                    priority=2):
        """Send a C-MOVE request to the peer AE.

        Yields ``(status, identifier)`` pairs.

        The peer will attempt to start a new association with the AE with
        *AE Title* ``move_aet`` and hence must be known to the SCP. Once the
        association has been established it will use the C-STORE service to
        send any matching datasets.

        Parameters
        ----------
        dataset : pydicom.dataset.Dataset
            The C-MOVE request's *Identifier* ``Dataset``. The exact
            requirements for the *Identifier* are Service Class specific (see
            the DICOM Standard, Part 4).
        move_aet : bytes
            The value of the *Move Destination* parameter for the C-MOVE
            request, should be the AE title of the Storage SCP for the
            C-STORE sub-operations performed by the peer.
        query_model : pydicom.uid.UID or str
            The value to use for the C-MOVE request's (0000,0002) *Affected
            SOP Class UID* parameter, which usually corresponds to the
            Information Model that is to be used. If supplying a ``str`` key
            (deprecated, to be removed in v1.5.0) then one of the following:

            - ``P`` - 1.2.840.10008.5.1.4.1.2.1.2 -
              *Patient Root Information Model - MOVE*
            - ``S`` - 1.2.840.10008.5.1.4.1.2.2.2 -
              *Study Root Information Model - MOVE*
            - ``O`` - 1.2.840.10008.5.1.4.1.2.3.2 -
              *Patient Study Only Information Model - MOVE*
            - ``C`` - 1.2.840.10008.5.1.4.1.2.4.2 -
              *Composite Instance Root Retrieve - MOVE*
            - ``H`` - 1.2.840.10008.5.1.4.38.3 -
              *Hanging Protocol Information Model - MOVE*
            - ``D`` - 1.2.840.10008.5.1.4.20.2 -
              *Defined Procedure Protocol Information Model - MOVE*
            - ``CP`` - 1.2.840.10008.5.1.4.39.3 -
              *Color Palette Information Model - MOVE*
            - ``IG`` - 1.2.840.10008.5.1.4.43.3 -
              *Generic Implant Template Information Model - MOVE*
            - ``IA`` - 1.2.840.10008.5.1.4.44.3 -
              *Implant Assembly Template Information Model - MOVE*
            - ``IT`` - 1.2.840.10008.5.1.4.44.3 -
              *Implant Template Group Information Model - MOVE*
            - ``PA`` - 1.2.840.10008.5.1.4.1.1.200.5 -
              *Protocol Approval Information Model - MOVE*
        msg_id : int, optional
            The DIMSE *Message ID*, must be between 0 and 65535, inclusive,
            (default 1).
        priority : int, optional
            The value of the *Priority* parameter (if supported by the peer),
            one of:

            - ``0`` - Medium
            - ``1`` - High
            - ``2`` - Low (default)

        Yields
        ------
        status : pydicom.dataset.Dataset
            If the peer timed out, aborted or sent an invalid response then
            yields an empty ``Dataset``. If a response was received from the
            peer then yields a ``Dataset`` containing at least a (0000,0900)
            *Status* element, and depending on the returned value, may
            optionally contain additional elements (see DICOM Standard Part 7,
            Section 9.1.4 and Annex C).

            The status for the requested C-MOVE operation should be one of the
            following values, but as the value depends
            on the peer this can't be assumed:

            *General C-MOVE* (DICOM Standard Part 7, 9.1.4.1.7 and Annex C)

            Cancel
              | ``0xFE00`` - Sub-operations terminated due to Cancel indication

            Success
              | ``0x0000`` - Sub-operations complete: no failures

            Failure
              | ``0x0122`` - SOP class not supported

            *Query/Retrieve Service, Hanging Protocol Query/Retrieve Service,
            Defined Procedure Protocol Query/Retrieve Service, Color Palette
            Query/Retrieve Service* , *Implant Template Query/Retreive
            Service* and *Protocol Approval Query/Retrieve Service*
            specific (DICOM Standard Part 4, Annexes C, U, Y, X, BB and HH):

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
            'Cancel' then yields a ``Dataset`` which should contain an
            (0008,0058) *Failed SOP Instance UID List* element, however this
            is not guaranteed and may instead be an empty ``Dataset``.

        See Also
        --------
        dimse_primitives.C_MOVE
        service_class.QueryRetrieveMoveServiceClass
        service_class.HangingProtocolQueryRetrieveServiceClass
        service_class.ColorPaletteQueryRetrieveServiceClass
        service_class.ImplantTemplateQueryRetrieveServiceClass
        service_class.ProtocolApprovalQueryRetrieveServiceClass

        References
        ----------

        * DICOM Standard Part 4, `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_C>`_
        * DICOM Standard Part 4, `Annex U <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_U>`_
        * DICOM Standard Part 4, `Annex X <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_X>`_
        * DICOM Standard Part 4, `Annex Y <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_Y>`_
        * DICOM Standard Part 4, `Annex BB <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_BB>`_
        * DICOM Standard Part 4, `Annex HH <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_HH>`_
        * DICOM Standard Part 4, `Annex II <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_II>`_
        * DICOM Standard Part 7, Sections
          `9.1.4 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.1.4>`_,
          `9.3.4 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.4>`_
          and `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_
        """
        # Can't send a C-MOVE without an Association
        if not self.is_established:
            raise RuntimeError("The association with a peer SCP must be "
                               "established before sending a C-MOVE request")

        # TODO: refactor in v1.5
        sop_class = UID(query_model)
        if not sop_class.is_valid:
            _sop_classes = {
                "P" : PatientRootQueryRetrieveInformationModelMove,
                "S" : StudyRootQueryRetrieveInformationModelMove,
                "O" : PatientStudyOnlyQueryRetrieveInformationModelMove,
                "C" : CompositeInstanceRootRetrieveMove,
                "H" : HangingProtocolInformationModelMove,
                "D" : DefinedProcedureProtocolInformationModelMove,
                "CP" : ColorPaletteInformationModelMove,
                "IG" : GenericImplantTemplateInformationModelMove,
                "IA" : ImplantAssemblyTemplateInformationModelMove,
                "IT" : ImplantTemplateGroupInformationModelMove,
                "PA" : ProtocolApprovalInformationModelMove,
            }

            try:
                sop_class = _sop_classes[query_model]
                warnings.warn(
                    "Using `query_model` with a key that corresponds to a "
                    "given UID is deprecated and will be removed in v1.5. "
                    "Pass the required UID directly instead.",
                    DeprecationWarning
                )
            except KeyError:
                raise ValueError(
                    "Unsupported value for `query_model`: {}"
                    .format(query_model)
                )

        # Determine the Presentation Context we are operating under
        #   and hence the transfer syntax to use for encoding `dataset`
        context = self._get_valid_context(sop_class, '', 'scu')

        # Build C-MOVE request primitive
        #   (M) Message ID
        #   (M) Affected SOP Class UID
        #   (M) Priority
        #   (M) Move Destination
        #   (M) Identifier
        req = C_MOVE()
        req.MessageID = msg_id
        req.AffectedSOPClassUID = sop_class
        req.Priority = priority
        req.MoveDestination = move_aet

        # Encode the Identifier `dataset` using the agreed transfer syntax;
        #   will return None if failed to encode
        transfer_syntax = context.transfer_syntax[0]
        bytestream = encode(dataset,
                            transfer_syntax.is_implicit_VR,
                            transfer_syntax.is_little_endian)

        if bytestream is not None:
            req.Identifier = BytesIO(bytestream)
        else:
            LOGGER.error('Failed to encode the supplied Identifier dataset')
            raise ValueError('Failed to encode the supplied Identifier '
                             'dataset')

        LOGGER.info('Sending Move Request: MsgID {}'.format(msg_id))
        LOGGER.info('')
        LOGGER.info('# Identifier DICOM Dataset')
        for elem in dataset:
            LOGGER.info(elem)
        LOGGER.info('')

        # Pause the reactor to prevent a race condition
        self._reactor_checkpoint.clear()

        # Send C-MOVE request to the peer via DIMSE and wait for the response
        self.dimse.send_msg(req, context.context_id)

        # Get the responses from the peer
        # Wrap the generator so the C-MOVE-RQ is sent immediately on
        #   executing this function, otherwise sending C-CANCEL requests
        #   may end up being sent first unless next() is called
        return self._wrap_get_move_responses(transfer_syntax)

    def send_c_store(self, dataset, msg_id=1, priority=2, originator_aet=None,
                     originator_id=None):
        """Send a C-STORE request to the peer AE.

        Parameters
        ----------
        dataset : pydicom.dataset.Dataset
            The DICOM dataset to send to the peer.
        msg_id : int, optional
            The DIMSE *Message ID*, must be between 0 and 65535, inclusive,
            (default ``1``).
        priority : int, optional
            The C-STORE operation *Priority* (may not be supported by the
            peer), one of:

            - ``0`` - Medium
            - ``1`` - High
            - ``2`` - Low (default)
        originator_aet : bytes, optional
            The value of the *Move Originator Application Entity Title*
            parameter for the C-STORE request. This is the AE title of the
            peer that invoked the C-MOVE operation for
            which this C-STORE sub-operation is being performed (default
            ``None``).
        originator_id : int, optional
            The value of the *Move Originator Message ID* parameter for the
            C-STORE request. This is the original *Message ID* parameter value
            for the C-MOVE request primitive for which the
            C-STORE sub-operation is being performed (default ``None``).

        Returns
        -------
        status : pydicom.dataset.Dataset
            If the peer timed out, aborted or sent an invalid response then
            returns an empty ``Dataset``. If a valid response was received
            from the peer then returns a ``Dataset`` containing at least a
            (0000,0900) *Status* element, and, depending on the returned
            value, may optionally contain additional elements (see DICOM
            Standard Part 7, Annex C).

            The status for the requested C-STORE operation should be one of the
            following, but as the value depends on the peer SCP this can't be
            assumed:

            *General C-STORE* (DICOM Standard Part 7, 9.1.1.1.9 and Annex C):

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
            (DICOM Standard Part 4, Annexes B.2.3 and GG):

            Failure
              | ``0xA700`` to ``0xA7FF`` - Out of resources
              | ``0xA900`` to ``0xA9FF`` - Data set does not match SOP class
              | ``0xC000`` to ``0xCFFF`` - Cannot understand

            Warning
              | ``0xB000`` - Coercion of data elements
              | ``0xB006`` - Element discarded
              | ``0xB007`` - Data set does not match SOP class

            *Non-Patient Object Service Class* specific (DICOM Standard Part 4,
            Annex GG.4.2)

            Failure
              | ``0xA700`` - Out of resources
              | ``0xA900`` - Data set does not match SOP class
              | ``0xC000`` - Cannot understand

        Raises
        ------
        RuntimeError
            If ``send_c_store`` is called with no established association.
        AttributeError
            If `dataset` is missing (0008,0016) *SOP Class UID*,
            (0008,0018) *SOP Instance UID* elements or the (0002,0010)
            *Transfer Syntax UID* file meta information element.
        ValueError
            If no accepted Presentation Context for `dataset` exists or if
            unable to encode the `dataset`.

        See Also
        --------
        dimse_primitives.C_STORE
        service_class.StorageServiceClass
        service_class.NonPatientObjectStorageServiceClass

        References
        ----------

        * DICOM Standard Part 4, Annex `B <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_B>`_
        * DICOM Standard Part 4, Annex `GG <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_GG>`_
        * DICOM Standard Part 7, Sections
          `9.1.1 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.1.1>`_,
          `9.3.1 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.1>`_
          and `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_
        """
        # Can't send a C-STORE without an Association
        if not self.is_established:
            raise RuntimeError("The association with a peer SCP must be "
                               "established before sending a C-STORE request")

        # Check `dataset` has required elements
        if 'SOPClassUID' not in dataset:
            raise AttributeError(
                "Unable to determine the presentation context to use with "
                "`dataset` as it contains no '(0008,0016) SOP Class UID' "
                "element"
            )

        try:
            assert 'TransferSyntaxUID' in dataset.file_meta
        except (AssertionError, AttributeError):
            raise AttributeError(
                "Unable to determine the presentation context to use with "
                "`dataset` as it contains no '(0002,0010) Transfer Syntax "
                "UID' file meta information element"
            )

        # Get a Presentation Context to use for sending the message
        context = self._get_valid_context(
            dataset.SOPClassUID,
            dataset.file_meta.TransferSyntaxUID,
            'scu'
        )
        transfer_syntax = context.transfer_syntax[0]

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
        req.AffectedSOPClassUID = dataset.SOPClassUID
        req.AffectedSOPInstanceUID = dataset.SOPInstanceUID
        req.Priority = priority
        req.MoveOriginatorApplicationEntityTitle = originator_aet
        req.MoveOriginatorMessageID = originator_id

        # Encode the `dataset` using the agreed transfer syntax
        #   Will return None if failed to encode
        bytestream = encode(dataset,
                            transfer_syntax.is_implicit_VR,
                            transfer_syntax.is_little_endian)

        if bytestream is not None:
            req.DataSet = BytesIO(bytestream)
        else:
            LOGGER.error("Failed to encode the supplied Dataset")
            raise ValueError('Failed to encode the supplied Dataset')

        # Pause the reactor to prevent a race condition
        self._reactor_checkpoint.clear()

        # Send C-STORE request to the peer via DIMSE and wait for the response
        self.dimse.send_msg(req, context.context_id)
        cx_id, rsp = self.dimse.get_msg(block=True)

        # Unpause the reactor
        self._reactor_checkpoint.set()

        # If `rsp` is None then the DIMSE timeout expired so abort
        if rsp is None:
            if self.is_established:
                LOGGER.error("Connection closed or timed-out")
                self.abort()
            return Dataset()

        # Determine validity of the response and get the status
        status = self._check_received_status(rsp)

        return status

    def _wrap_find_responses(self, transfer_syntax):
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
                if self.is_established:
                    LOGGER.error("Connection closed or timed-out")
                    self.abort()

                self._reactor_checkpoint.set()
                yield Dataset(), None
                return

            if not isinstance(rsp, C_FIND):
                LOGGER.error(
                    'Received an unexpected {} message from the peer'
                    .format(rsp.__class__.__name__.replace('_', '-'))
                )
                self.abort()
                self._reactor_checkpoint.set()
                yield Dataset(), None
                return

            if not rsp.is_valid_response:
                LOGGER.error(
                    'Received an invalid C-FIND response from the peer'
                )
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
            category = code_to_category(status.Status)

            LOGGER.debug('')
            if category == STATUS_PENDING:
                LOGGER.info(
                    "Find SCP Response: {} - 0x{:04x} (Pending)"
                    .format(operation_no, status.Status)
                )
            else:
                LOGGER.info(
                    'Find SCP Result: 0x{:04x} ({})'
                    .format(status.Status, category)
                )

            # 'Success', 'Warning', 'Failure', 'Cancel' are final yields,
            #   'Pending' means more to come
            identifier = None
            if category in [STATUS_PENDING]:
                operation_no += 1

                try:
                    identifier = decode(rsp.Identifier,
                                        transfer_syntax.is_implicit_VR,
                                        transfer_syntax.is_little_endian)
                    LOGGER.debug('')
                    LOGGER.debug('# Identifier DICOM Dataset')
                    for elem in identifier:
                        LOGGER.debug(elem)
                    LOGGER.debug('')
                except Exception:
                    LOGGER.error(
                        "Failed to decode the received Identifier dataset"
                    )
                    yield status, None

                yield status, identifier
                continue

            # Only reach this point if status is Sucess, Warning, Failure
            #   or Cancel
            self._reactor_checkpoint.set()
            yield status, identifier
            break

        # Unpause the reactor
        self._reactor_checkpoint.set()

    def _wrap_get_move_responses(self, transfer_syntax):
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
            rsp_type = rsp.__class__.__name__.replace('_', '-')
            rsp_name = {'C-GET' : 'Get', 'C-MOVE' : 'Move'}

            # If `rsp` is None then the DIMSE timeout expired
            #   so abort if the association hasn't already been aborted
            if rsp is None:
                if self.is_established:
                    LOGGER.error("Connection closed or timed-out")
                    self.abort()

                self._reactor_checkpoint.set()
                yield Dataset(), None
                return

            if not isinstance(rsp, (C_STORE, C_GET, C_MOVE)):
                LOGGER.error(
                    'Received an unexpected {} message from the peer'
                    .format(rsp_type)
                )
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
                LOGGER.error(
                    'Received an invalid {} response from the peer'
                    .format(rsp_type)
                )
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
            category = code_to_category(status.Status)

            LOGGER.debug('')
            if category == STATUS_PENDING:
                LOGGER.info(
                    "{} SCP Response: {} - 0x{:04x} (Pending)"
                    .format(rsp_name[rsp_type], operation_no, status.Status)
                )
            else:
                LOGGER.info(
                    '{} SCP Result: 0x{:04x} ({})'
                    .format(rsp_name[rsp_type], status.Status, category)
                )

            # Log number of remaining sub-operations - C-GET/C-MOVE only
            LOGGER.info(
                "Sub-Operations Remaining: %s, Completed: %s, "
                "Failed: %s, Warning: %s",
                rsp.NumberOfRemainingSuboperations or '0',
                rsp.NumberOfCompletedSuboperations or '0',
                rsp.NumberOfFailedSuboperations or '0',
                rsp.NumberOfWarningSuboperations or '0'
            )

            # 'Success', 'Warning', 'Failure', 'Cancel' are final yields,
            #   'Pending' means more to come
            identifier = None
            if category in [STATUS_PENDING]:
                operation_no += 1
                yield status, identifier
                continue

            if (rsp.Identifier and category in
                    [STATUS_CANCEL, STATUS_WARNING, STATUS_FAILURE]):
                # From Part 4, Annex C.4.3, responses with these
                #   statuses should contain an Identifier dataset
                #   with a (0008,0058) Failed SOP Instance UID List
                #    element however this can't be assumed
                # pylint: disable=broad-except
                try:
                    identifier = decode(rsp.Identifier,
                                        transfer_syntax.is_implicit_VR,
                                        transfer_syntax.is_little_endian)
                    if identifier:
                        LOGGER.debug('')
                        LOGGER.debug('# Identifier DICOM Dataset')
                        for elem in identifier:
                            LOGGER.debug(elem)
                        LOGGER.debug('')
                except Exception as ex:
                    LOGGER.error(
                        "Failed to decode the received Identifier dataset"
                    )
                    LOGGER.exception(ex)
                    identifier = None

            # Only reach this point if status is Sucess, Warning, Failure
            #   or Cancel
            self._reactor_checkpoint.set()
            yield status, identifier
            break

        # Unpause the reactor
        self._reactor_checkpoint.set()

    # DIMSE-N services provided by the Association
    def send_n_action(self, dataset, action_type, class_uid, instance_uid,
                      msg_id=1, meta_uid=None):
        """Send an N-ACTION request message to the peer AE.

        Parameters
        ----------
        dataset : pydicom.dataset.Dataset or None
            The dataset that will be sent as the *Action Information*
            parameter in the N-ACTION request, or ``None`` if not required.
        action_type : int
            The value of the request's (0000,1008) *Action Type ID* parameter.
        class_uid : pydicom.uid.UID
            The UID to be sent for the request's (0000,0003) *Requested SOP
            Class UID* parameter.
        instance_uid : pydicom.uid.UID
            The UID to be sent for the request's (0000,1001) *Requested SOP
            Instance UID* parameter.
        msg_id : int, optional
            The request's *Message ID* parameter value, must be between 0 and
            65535, inclusive, (default 1).
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
            returns an empty ``Dataset``. If a response was received from the
            peer then returns a ``Dataset`` containing at least a (0000,0900)
            *Status* element, and depending on the returned value, may
            optionally contain additional elements (see the DICOM Standard,
            Part 7, Section 9.1.2.1.5 and Annex C).

            *General N-ACTION* (DICOM Standard Part 7, Section 10.1.4 and
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

        action_reply : pydicom.dataset.Dataset or None
            If the status category is 'Success' or 'Warning' then a ``Dataset``
            containing attributes corresponding to those supplied in the
            *Action Reply*. Because *Action Reply* is optional the returned
            ``Dataset`` may be empty.

            If the status category is 'Failure' or if the peer timed-out,
            aborted, or sent an invalid response then returns ``None``.

        See Also
        --------
        dimse_primitives.N_ACTION

        References
        ----------

        * DICOM Standart Part 4, `Annex F <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_F>`_
        * DICOM Standart Part 4, `Annex H <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_H>`_
        * DICOM Standard Part 4, `Annex CC <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_CC>`_
        * DICOM Standard Part 4, `Annex DD <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_DD>`_
        * DICOM Standard Part 7, Sections
          `10.1.3 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_10.1.3>`_,
          `10.3.3 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_10.3.3>`_
          and `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_
        """
        # Can't send an N-ACTION without an Association
        if not self.is_established:
            raise RuntimeError(
                "The association with a peer SCP must be established prior "
                "to sending an N-ACTION request."
            )

        # Determine the Presentation Context we are operating under
        #   and hence the transfer syntax to use for encoding `dataset`
        context = self._get_valid_context(meta_uid or class_uid, '', 'scu')
        transfer_syntax = context.transfer_syntax[0]

        # Build N-ACTION request primitive
        #   (M) Message ID
        #   (M) Requested SOP Class UID
        #   (M) Requested SOP Instance UID
        #   (M) Action Type ID
        #   (U) Action Information
        req = N_ACTION()
        req.MessageID = msg_id
        req.RequestedSOPClassUID = class_uid
        req.RequestedSOPInstanceUID = instance_uid
        req.ActionTypeID = action_type

        # Action Information is optional
        if dataset is not None:
            # Encode the `dataset` using the agreed transfer syntax
            #   Will return None if failed to encode
            bytestream = encode(dataset,
                                transfer_syntax.is_implicit_VR,
                                transfer_syntax.is_little_endian)

            if bytestream is not None:
                req.ActionInformation = BytesIO(bytestream)
            else:
                msg = (
                    "Failed to encode the supplied 'Action Information' "
                    "dataset"
                )
                LOGGER.error(msg)
                raise ValueError(msg)

        # Send N-ACTION request to the peer via DIMSE and wait for the response
        LOGGER.info('Sending Action Request: MsgID {}'.format(msg_id))

        # Pause the reactor to prevent a race condition
        self._reactor_checkpoint.clear()

        self.dimse.send_msg(req, context.context_id)
        cx_id, rsp = self.dimse.get_msg(block=True)

        # Unpause the reactor
        self._reactor_checkpoint.set()

        # If `rsp` is None then the DIMSE timeout expired so abort
        if rsp is None:
            if self.is_established:
                LOGGER.error("Connection closed or timed-out")
                self.abort()

            return Dataset(), None

        # Determine validity of the response and get the status
        status = self._check_received_status(rsp)

        # Warning and Success statuses will return a dataset
        #   we check against None as 0x0000 is a possible status
        action_reply = None
        if getattr(status, 'Status', None) is not None:
            category = code_to_category(status.Status)
            if category not in [STATUS_WARNING, STATUS_SUCCESS]:
                return status, action_reply

            bytestream = rsp.ActionReply
            if bytestream and bytestream.getvalue() != b'':
                # Attempt to decode the response's dataset
                # pylint: disable=broad-except
                try:
                    action_reply = decode(bytestream,
                                          transfer_syntax.is_implicit_VR,
                                          transfer_syntax.is_little_endian)
                except Exception as ex:
                    LOGGER.error(
                        "Unable to decode the received 'Action Reply' dataset"
                    )
                    LOGGER.exception(ex)
                    # Failure: Processing failure
                    status.Status = 0x0110
            else:
                action_reply = Dataset()

        return status, action_reply

    def send_n_create(self, dataset, class_uid, instance_uid=None, msg_id=1,
                      meta_uid=None):
        """Send an N-CREATE request message to the peer AE.

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
            65535, inclusive, (default 1).
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
            returns an empty ``Dataset``. If a response was received from the
            peer then returns a ``Dataset`` containing at least a (0000,0900)
            *Status* element, and depending on the returned value, may
            optionally contain additional elements (see the DICOM Standard,
            Part 7, Section 9.1.2.1.5 and Annex C).

            *General N-CREATE* (DICOM Standard Part 7, Section 10.1.5 and
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
                printed and N-ACTION at the Film Session level is not supported.
                A new Film Box will not be created when a previous Film Box has
                not been printed

            *Media Creation Management Service* specific (DICOM
            Standard Part 4, Annex S.3.2.1.4):

            Failure
              | ``0xA510`` - Failed: an initiate media creation action has already been
                received for this SOP Instance

            *Unified Procedure Step Service* specific (DICOM
            Standard Part 4, Annex CC.2.5.4):

            Warning
              | ``0xB300`` - THE UPS was created with modifications

            Failure
              | ``0xC309`` - The provided value of UPS State was not 'SCHEDULED'

            *RT Machine Verification Service* specific (DICOM
            Standard Part 4, Annex DD.3.2.1.2):

            Failure
              | ``0xC221`` - The Referenced Fraction Group Number does not exist in the
                referenced plan
              | ``0xC222`` - No beams exist within the referenced fraction group
              | ``0xC223`` - SCU already verifying and cannot currently process this
                request
              | ``0xC227`` - No such object instance - Referenced RT Plan not found

        attribute_list : pydicom.dataset.Dataset or None
            If the status category is 'Success' or 'Warning' then a ``Dataset``
            containing attributes corresponding to those supplied in the
            *Attribute List*. Because *Attribute List* is optional the returned
            ``Dataset`` may be empty.

            If the status category is 'Failure' or if the peer timed-out,
            aborted, or sent an invalid response then returns ``None``.

        See Also
        --------
        dimse_primitives.N_CREATE

        References
        ----------

        * DICOM Standart Part 4, `Annex F <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_F>`_
        * DICOM Standart Part 4, `Annex H <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_H>`_
        * DICOM Standard Part 4, `Annex CC <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_CC>`_
        * DICOM Standard Part 4, `Annex DD <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_DD>`_
        * DICOM Standard Part 7, Sections
          `10.1.5 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_10.1.5>`_,
          `10.3.5 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_10.3.5>`_
          and `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_
        """
        # Can't send an N-CREATE without an Association
        if not self.is_established:
            raise RuntimeError(
                "The association with a peer SCP must be established prior "
                "to sending an N-CREATE request."
            )

        # Determine the Presentation Context we are operating under
        #   and hence the transfer syntax to use for encoding `dataset`
        context = self._get_valid_context(meta_uid or class_uid, '', 'scu')
        transfer_syntax = context.transfer_syntax[0]

        # Build N-CREATE request primitive
        #   (M) Message ID
        #   (M) Affected SOP Class UID
        #   (U) Affected SOP Instance UID
        #   (U) Attribute List
        req = N_CREATE()
        req.MessageID = msg_id
        req.AffectedSOPClassUID = class_uid
        req.AffectedSOPInstanceUID = instance_uid

        # Attribute List is optional
        if dataset is not None:
            # Encode the `dataset` using the agreed transfer syntax
            #   Will return None if failed to encode
            bytestream = encode(dataset,
                                transfer_syntax.is_implicit_VR,
                                transfer_syntax.is_little_endian)

            if bytestream is not None:
                req.AttributeList = BytesIO(bytestream)
            else:
                msg = "Failed to encode the supplied 'Attribute List' dataset"
                LOGGER.error(msg)
                raise ValueError(msg)

        # Send N-CREATE request to the peer via DIMSE and wait for the response
        LOGGER.info('Sending Create Request: MsgID {}'.format(msg_id))

        # Pause the reactor to prevent a race condition
        self._reactor_checkpoint.clear()

        self.dimse.send_msg(req, context.context_id)
        cx_id, rsp = self.dimse.get_msg(block=True)

        # Unpause the reactor
        self._reactor_checkpoint.set()

        # If `rsp` is None then the DIMSE timeout expired so abort
        if rsp is None:
            if self.is_established:
                LOGGER.error("Connection closed or timed-out")
                self.abort()
            return Dataset(), None

        # Determine validity of the response and get the status
        status = self._check_received_status(rsp)

        # Warning and Success statuses will return a dataset
        #   we check against None as 0x0000 is a possible status
        attribute_list = None
        if getattr(status, 'Status', None) is not None:
            category = code_to_category(status.Status)
            if category not in [STATUS_WARNING, STATUS_SUCCESS]:
                return status, attribute_list

            bytestream = rsp.AttributeList
            if bytestream and bytestream.getvalue() != b'':
                # Attempt to decode the response's dataset
                # pylint: disable=broad-except
                try:
                    attribute_list = decode(bytestream,
                                            transfer_syntax.is_implicit_VR,
                                            transfer_syntax.is_little_endian)
                except Exception as ex:
                    LOGGER.error(
                        "Unable to decode the received 'Attribute List' "
                        "dataset"
                    )
                    LOGGER.exception(ex)
                    # Failure: Processing failure
                    status.Status = 0x0110

            else:
                attribute_list = Dataset()

        return status, attribute_list

    def send_n_delete(self, class_uid, instance_uid, msg_id=1, meta_uid=None):
        """Send an N-DELETE request message to the peer AE.

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
            65535, inclusive, (default 1).
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
            returns an empty ``Dataset``. If a response was received from the
            peer then returns a ``Dataset`` containing at least a (0000,0900)
            *Status* element, and depending on the returned value, may
            optionally contain additional elements (see the DICOM Standard,
            Part 7, Section 9.1.2.1.5 and Annex C).

            General N-DELETE (DICOM Standard Part 7, Section 10.1.6 and
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
        dimse_primitives.N_DELETE

        References
        ----------

        * DICOM Standart Part 4, `Annex H <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_H>`_
        * DICOM Standard Part 4, `Annex DD <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_DD>`_
        * DICOM Standard Part 7, Sections
          `10.1.6 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_10.1.6>`_,
          `10.3.6 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_10.3.6>`_
          and `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_
        """
        # Can't send an N-DELETE without an Association
        if not self.is_established:
            raise RuntimeError(
                "The association with a peer SCP must be established prior "
                "to sending an N-DELETE request."
            )

        # Determine the Presentation Context we are operating under
        #   and hence the transfer syntax to use for encoding `dataset`
        context = self._get_valid_context(meta_uid or class_uid, '', 'scu')

        # Build N-DELETE request primitive
        #   (M) Message ID
        #   (M) Requested SOP Class UID
        #   (M) Requested SOP Instance UID
        req = N_DELETE()
        req.MessageID = msg_id
        req.RequestedSOPClassUID = class_uid
        req.RequestedSOPInstanceUID = instance_uid

        # Send N-DELETE request to the peer via DIMSE and wait for the response
        LOGGER.info('Sending Delete Request: MsgID {}'.format(msg_id))

        # Pause the reactor to prevent a race condition
        self._reactor_checkpoint.clear()

        self.dimse.send_msg(req, context.context_id)
        cx_id, rsp = self.dimse.get_msg(block=True)

        # Unpause the reactor
        self._reactor_checkpoint.set()

        # If `rsp` is None then the DIMSE timeout expired so abort
        if rsp is None:
            if self.is_established:
                LOGGER.error("Connection closed or timed-out")
                self.abort()
            return Dataset()

        # Determine validity of the response and get the status
        status = self._check_received_status(rsp)

        return status

    def send_n_event_report(self, dataset, event_type, class_uid,
                            instance_uid, msg_id=1, meta_uid=None):
        """Send an N-EVENT-REPORT request message to the peer AE.

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
            65535, inclusive, (default 1).
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
            returns an empty ``Dataset``. If a response was received from the
            peer then returns a ``Dataset`` containing at least a (0000,0900)
            *Status* element, and depending on the returned value, may
            optionally contain additional elements (see the DICOM Standard,
            Part 7, Section 9.1.2.1.5 and Annex C).

            *General N-EVENT-REPORT* (DICOM Standard Part 7, Section 10.1.1
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
            If the status category is 'Success' or 'Warning' then a ``Dataset``
            containing attributes corresponding to those supplied in the
            *Event Reply*. Because *Event Reply* is optional the returned
            ``Dataset`` may be empty.

            If the status category is 'Failure' or if the peer timed-out,
            aborted, or sent an invalid response then returns ``None``.

        See Also
        --------
        dimse_primitives.N_EVENT_REPORT

        References
        ----------

        * DICOM Standart Part 4, `Annex F <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_F>`_
        * DICOM Standart Part 4, `Annex H <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_H>`_
        * DICOM Standart Part 4, `Annex J <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_J>`_
        * DICOM Standard Part 4, `Annex CC <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_CC>`_
        * DICOM Standard Part 4, `Annex DD <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_DD>`_
        * DICOM Standard Part 7, Sections
          `10.1.1 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_10.1.1>`_,
          `10.3.1 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_10.3.1>`_
          and `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_
        """
        # Can't send an N-EVENT-REPORT without an Association
        if not self.is_established:
            raise RuntimeError(
                "The association with a peer SCP must be established prior "
                "to sending an N-EVENT-REPORT request."
            )

        # Determine the Presentation Context we are operating under
        #   and hence the transfer syntax to use for encoding `dataset`
        # As far as I can tell, N-EVENT-REPORT doesn't use SCP/SCU Role
        #   selection negotiation, so we need to ignore the negotiate role
        #   since the SCP will be sending requests to the SCU
        context = self._get_valid_context(meta_uid or class_uid, '', None)
        transfer_syntax = context.transfer_syntax[0]

        # Build N-EVENT-REPORT request primitive
        #   (M) Message ID
        #   (M) Affected SOP Class UID
        #   (M) Affected SOP Instance UID
        #   (M) Event Type ID
        #   (U) Event Information
        req = N_EVENT_REPORT()
        req.MessageID = msg_id
        req.AffectedSOPClassUID = class_uid
        req.AffectedSOPInstanceUID = instance_uid
        req.EventTypeID = event_type

        # *Event Information* is optional
        if dataset is not None:
            # Encode the `dataset` using the agreed transfer syntax
            #   Will return None if failed to encode
            bytestream = encode(dataset,
                                transfer_syntax.is_implicit_VR,
                                transfer_syntax.is_little_endian)

            if bytestream is not None:
                req.EventInformation = BytesIO(bytestream)
            else:
                msg = (
                    "Unable to encode the supplied 'Event Information' dataset"
                )
                LOGGER.error(msg)
                raise ValueError(msg)

        # Send N-EVENT-REPORT request to the peer via DIMSE and wait for
        # the response primitive
        LOGGER.info('Sending Event Report Request: MsgID {}'.format(msg_id))

        # Pause the reactor to prevent a race condition
        self._reactor_checkpoint.clear()

        self.dimse.send_msg(req, context.context_id)
        cx_id, rsp = self.dimse.get_msg(block=True)

        # Unpause the reactor
        self._reactor_checkpoint.set()

        # If `rsp` is None then the DIMSE timeout expired so abort
        if rsp is None:
            if self.is_established:
                LOGGER.error("Connection closed or timed-out")
                self.abort()
            return Dataset(), None

        # Determine validity of the response and get the status
        status = self._check_received_status(rsp)

        # Warning and Success statuses will return a dataset
        #   we check against None as 0x0000 is a possible status
        event_reply = None
        if getattr(status, 'Status', None) is not None:
            category = code_to_category(status.Status)
            if category not in [STATUS_WARNING, STATUS_SUCCESS]:
                return status, event_reply

            bytestream = rsp.EventReply
            if bytestream and bytestream.getvalue() != b'':
                # Attempt to decode the response's dataset
                # pylint: disable=broad-except
                try:
                    event_reply = decode(bytestream,
                                         transfer_syntax.is_implicit_VR,
                                         transfer_syntax.is_little_endian)
                except Exception as ex:
                    LOGGER.error(
                        "Unable to decode the received 'Event Reply' dataset"
                    )
                    LOGGER.exception(ex)
                    # Failure: Processing failure
                    status.Status = 0x0110

            else:
                event_reply = Dataset()

        return status, event_reply

    def send_n_get(self, identifier_list, class_uid, instance_uid, msg_id=1,
                   meta_uid=None):
        """Send an N-GET request message to the peer AE.

        Parameters
        ----------
        identifier_list : list of pydicom.tag.Tag
            A list of DICOM Data Element tags to be sent for the request's
            (0000,1005) *Attribute Identifier List* parameter. Should either be
            a list of pydicom ``Tag`` objects or a list of values that is
            acceptable for creating pydicom ``Tag`` objects.
        class_uid : pydicom.uid.UID
            The UID to be sent for the request's (0000,0003) *Requested SOP
            Class UID* parameter.
        instance_uid : pydicom.uid.UID
            The UID to be sent for the request's (0000,1001) *Requested SOP
            Instance UID* parameter.
        msg_id : int, optional
            The request's *Message ID* parameter value, must be between 0 and
            65535, inclusive, (default 1).
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
            returns an empty ``Dataset``. If a response was received from the
            peer then returns a ``Dataset`` containing at least a (0000,0900)
            *Status* element, and depending on the returned value, may
            optionally contain additional elements (see the DICOM Standard,
            Part 7, Section 9.1.2.1.5 and Annex C).

            *General N-GET* (DICOM Standard Part 7, Section 10.1.2 and Annex C)

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
            (DICOM Standard Part 4, Annex F.8.2.1.4 and Annex S.3.2.4.4):

            Warning
              | ``0x0001`` - Requested optional Attributes are not supported

            *Unified Procedure Step Service* specific
            (DICOM Standard Part 4, Annex CC.2.7.4):

            Warning
              | ``0x0001`` - Requested optional Attributes are not supported

            Failure
              | ``0xC307`` - Specified SOP Instance UID doesn't exist or is not
                a UPS Instance managed by this SCP

            *RT Machine Verification Service* specific
            (DICOM Standard Part 4, Annex DD.3.2.2.3):

            Failure
              | ``0xC112`` - Applicable Machine Verification Instance not found

        attribute_list : pydicom.dataset.Dataset or None
            If the status category is 'Success' or 'Warning' then a ``Dataset``
            containing attributes corresponding to those supplied in the
            *Attribute List*. Because *Attribute List* is optional the returned
            ``Dataset`` may be empty.

            If the status category is 'Failure' or if the peer timed-out,
            aborted, or sent an invalid response then returns ``None``.

        See Also
        --------
        dimse_primitives.N_GET
        service_class.DisplaySystemManagementServiceClass

        References
        ----------

        * DICOM Standart Part 4, `Annex F <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_F>`_
        * DICOM Standart Part 4, `Annex H <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_H>`_
        * DICOM Standard Part 4, `Annex S <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_S>`_
        * DICOM Standard Part 4, `Annex CC <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_CC>`_
        * DICOM Standard Part 4, `Annex DD <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_DD>`_
        * DICOM Standard Part 4, `Annex EE <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_EE>`_
        * DICOM Standard Part 7, Sections
          `10.1.2 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_10.1.2>`_,
          `10.3.2 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_10.3.2>`_
          and `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_
        """
        # Can't send an N-GET without an Association
        if not self.is_established:
            raise RuntimeError(
                "The association with a peer SCP must be established prior "
                "to sending an N-GET request."
            )

        # Determine the Presentation Context we are operating under
        #   and hence the transfer syntax to use for encoding `dataset`
        context = self._get_valid_context(meta_uid or class_uid, '', 'scu')
        transfer_syntax = context.transfer_syntax[0]

        # Build N-GET request primitive
        #   (M) Message ID
        #   (M) Requested SOP Class UID
        #   (M) Requested SOP Instance UID
        #   (U) Attribute Identifier List
        req = N_GET()
        req.MessageID = msg_id
        req.RequestedSOPClassUID = class_uid
        req.RequestedSOPInstanceUID = instance_uid
        req.AttributeIdentifierList = identifier_list

        # Send N-GET request to the peer via DIMSE and wait for the response
        LOGGER.info('Sending Get Request: MsgID {}'.format(msg_id))

        # Pause the reactor to prevent a race condition
        self._reactor_checkpoint.clear()

        self.dimse.send_msg(req, context.context_id)
        cx_id, rsp = self.dimse.get_msg(block=True)

        # Unpause the reactor
        self._reactor_checkpoint.set()

        # If `rsp` is None then the DIMSE timeout expired so abort
        if rsp is None:
            if self.is_established:
                LOGGER.error("Connection closed or timed-out")
                self.abort()
            return Dataset(), None

        # Determine validity of the response and get the status
        status = self._check_received_status(rsp)

        # Warning and Success statuses will return a dataset
        #   we check against None as 0x0000 is a possible status
        attribute_list = None
        if getattr(status, 'Status', None) is not None:
            category = code_to_category(status.Status)
            if category not in [STATUS_WARNING, STATUS_SUCCESS]:
                return status, attribute_list

            bytestream = rsp.AttributeList
            if bytestream and bytestream.getvalue() != b'':
                # Attempt to decode the response's dataset
                # pylint: disable=broad-except
                try:
                    attribute_list = decode(bytestream,
                                            transfer_syntax.is_implicit_VR,
                                            transfer_syntax.is_little_endian)
                except Exception as ex:
                    LOGGER.error(
                        "Unable to decode the received 'Attribute List' "
                        "dataset"
                    )
                    LOGGER.exception(ex)
                    # Failure: Processing failure
                    status.Status = 0x0110

            else:
                attribute_list = Dataset()

        return status, attribute_list

    def send_n_set(self, dataset, class_uid, instance_uid, msg_id=1,
                   meta_uid=None):
        """Send an N-SET request message to the peer AE.

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
            65535, inclusive, (default 1).
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
            returns an empty ``Dataset``. If a response was received from the
            peer then returns a ``Dataset`` containing at least a (0000,0900)
            *Status* element, and depending on the returned value, may
            optionally contain additional elements (see the DICOM Standard,
            Part 7, Section 9.1.2.1.5 and Annex C).

            *General N-SET* (DICOM Standard Part 7, Section 10.1.3 and Annex C)

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

            *Unified Procedure Step Service* specific (DICOM Standard Part 4,
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

            *RT Machine Verification Service* specific (DICOM Standard Part 4,
            Annex DD.3.2.1.2):

            Failure
              | ``0xC224`` - Reference Beam Number not found within the
                referenced Fraction Group
              | ``0xC225`` - Referenced device or accessory not supported
              | ``0xC226`` - Referenced device or accessory not found with the
                referenced beam

        attribute_list : pydicom.dataset.Dataset or None
            If the status category is 'Success' or 'Warning' then a ``Dataset``
            containing attributes corresponding to those supplied in the
            *Attribute List*. Because *Attribute List* is optional the returned
            ``Dataset`` may be empty.

            If the status category is 'Failure' or if the peer timed-out,
            aborted, or sent an invalid response then returns ``None``.

        See Also
        --------
        dimse_primitives.N_SET

        References
        ----------

        * DICOM Standart Part 4, `Annex F <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_F>`_
        * DICOM Standart Part 4, `Annex H <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_H>`_
        * DICOM Standard Part 4, `Annex CC <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_CC>`_
        * DICOM Standard Part 4, `Annex DD <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_DD>`_
        * DICOM Standard Part 7, Sections
          `10.1.3 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_10.1.3>`_,
          `10.3.3 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_10.3.3>`_
          and `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_
        """
        # Can't send an N-SET without an Association
        if not self.is_established:
            raise RuntimeError(
                "The association with a peer SCP must be established prior "
                "to sending an N-SET request."
            )

        # Determine the Presentation Context we are operating under
        #   and hence the transfer syntax to use for encoding `dataset`
        context = self._get_valid_context(meta_uid or class_uid, '', 'scu')
        transfer_syntax = context.transfer_syntax[0]

        # Build N-SET request primitive
        #   (M) Message ID
        #   (M) Requested SOP Class UID
        #   (M) Requested SOP Instance UID
        #   (M) Modification List
        req = N_SET()
        req.MessageID = msg_id
        req.RequestedSOPClassUID = class_uid
        req.RequestedSOPInstanceUID = instance_uid

        # Encode the `dataset` using the agreed transfer syntax
        #   Will return None if failed to encode
        bytestream = encode(dataset,
                            transfer_syntax.is_implicit_VR,
                            transfer_syntax.is_little_endian)

        if bytestream is not None:
            req.ModificationList = BytesIO(bytestream)
        else:
            msg = "Failed to encode the supplied 'Modification List' dataset"
            LOGGER.error(msg)
            raise ValueError(msg)

        # Send N-SET request to the peer via DIMSE and wait for the response
        LOGGER.info('Sending Set Request: MsgID {}'.format(msg_id))

        # Pause the reactor to prevent a race condition
        self._reactor_checkpoint.clear()

        self.dimse.send_msg(req, context.context_id)
        cx_id, rsp = self.dimse.get_msg(block=True)

        # Unpause the reactor
        self._reactor_checkpoint.set()

        # If `rsp` is None then the DIMSE timeout expired so abort
        if rsp is None:
            if self.is_established:
                LOGGER.error("Connection closed or timed-out")
                self.abort()
            return Dataset(), None

        # Determine validity of the response and get the status
        status = self._check_received_status(rsp)

        # Warning and Success statuses will return a dataset
        #   we check against None as 0x0000 is a possible status
        attribute_list = None
        if getattr(status, 'Status', None) is not None:
            category = code_to_category(status.Status)
            if category not in [STATUS_WARNING, STATUS_SUCCESS]:
                return status, attribute_list

            bytestream = rsp.AttributeList
            if bytestream and bytestream.getvalue() != b'':
                # Attempt to decode the response's dataset
                # pylint: disable=broad-except
                try:
                    attribute_list = decode(rsp.AttributeList,
                                            transfer_syntax.is_implicit_VR,
                                            transfer_syntax.is_little_endian)
                except Exception as ex:
                    LOGGER.error(
                        "Unable to decode the received 'Attribute List' "
                        "dataset"
                    )
                    LOGGER.exception(ex)
                    # Failure: Processing failure
                    status.Status = 0x0110

            else:
                attribute_list = Dataset()

        return status, attribute_list

    def _serve_request(self, msg, context_id):
        """Handle a DIMSE service request.

        Parameters
        ----------
        msg : dimse_primitives.DIMSEPrimitive subclass
            The DIMSE service request primitive.
        context_id : int
            The ID of the presentation context that the request is being
            made under.
        """
        # No message or not a service request
        if not msg.is_valid_request:
            LOGGER.warning(
                "Received unexpected {} service message".format(msg.msg_type)
            )
            return

        # Use the Message's Affected SOP Class UID or Requested SOP
        #   Class UID to determine which service to use
        class_uid = ''
        if getattr(msg, 'AffectedSOPClassUID', None) is not None:
            # DIMSE-C, N-EVENT-REPORT, N-CREATE use AffectedSOPClassUID
            class_uid = msg.AffectedSOPClassUID
        elif getattr(msg, 'RequestedSOPClassUID', None) is not None:
            # N-GET, N-SET, N-ACTION, N-DELETE use RequestedSOPClassUID
            class_uid = msg.RequestedSOPClassUID

        # SOP Class Common Extended Negotiation
        try:
            # The service class UID
            class_uid = self.acceptor.accepted_common_extended[class_uid][0]
        except KeyError:
            pass

        # Convert the SOP/Service UID to the corresponding service
        service_class = uid_to_service_class(class_uid)(self)

        try:
            context = self._accepted_cx[context_id]
        except KeyError:
            LOGGER.info(
                "Received DIMSE message with invalid or rejected "
                "context ID: %d", context_id
            )
            LOGGER.debug("%s", msg)
            self.abort()
            return

        # Run corresponding Service Class in SCP mode
        try:
            # Clear out any C-CANCEL requests received beforehand
            self.dimse.cancel_req = {}
            service_class.SCP(msg, context)
            # Clear out any unacted upon requests received during
            self.dimse.cancel_req = {}
        except NotImplementedError:
            # SCP isn't implemented
            LOGGER.error(
                "No supported service class available for the SOP "
                "Class UID '{}'".format(class_uid)
            )
            self.abort()
            return
        except Exception as exc:
            LOGGER.exception(exc)
            self.abort()
            return


class ServiceUser(object):
    """Convenience class for the ``Association`` service user.

    An ``Association`` object has two ``ServiceUser`` attributes, one
    representing the association *Requestor* and the other the association
    *Acceptor*. Once both have been defined sufficiently to be considered
    valid then association negotiation can begin. The *Requestor*
    ``ServiceUser`` requires (at a minimum) the following in order to be valid:

    * For association as requestor:

        * AE title (ae_title)
        * Address and port number (address and port)
        * Maximum PDU length (maximum_length)
        * Implementation class UID (implementation_class_uid)
        * At least one presentation context (requested_contexts)
    * For association as acceptor:

        * AE title
        * Address and port number

    The *Acceptor* ``ServiceUser`` requires (at a minimum) the following in
    order to be valid:

    * For association as requestor:

        * Address and port number
    * For association as acceptor:

        * AE title
        * Address and port number
        * Maximum PDU length
        * Implementation class UID

    Attributes
    ----------
    address : str
        The TCP/IP address of the AE.
    ae_title : bytes
        The AE's AE title.
    port : int
        The port number of the AE.
    primitive : None or pdu_primitives.A_ASSOCIATE
        The A-ASSOCIATE primitive (request if mode is 'requestor',
        accept/reject if mode is 'acceptor') sent or received by the AE
        during association negotiation.
    """
    def __init__(self, assoc, mode):
        """Create a new ServiceUser.

        Parameters
        ----------
        assoc : association.Association
            The parent Association.
        mode : str
            The operation mode of the AE represented by the ServiceUser, either
            'requestor' or 'acceptor'. This is not necessarily the same as the
            association's mode.
        """
        mode = mode.lower()
        if mode not in [MODE_REQUESTOR, MODE_ACCEPTOR]:
            raise ValueError(
                "The 'mode' must be either 'requestor' or 'acceptor'"
            )

        self.assoc = assoc
        self._mode = mode
        self.primitive = None
        self.ae_title = b''
        self.port = None
        self.address = ''

        # If Requestor this is the requested contexts, otherwise this is
        #   the supported contexts
        self._contexts = []

        # User Information items
        self._user_info = []
        # Must always be set
        self.maximum_length = DEFAULT_MAX_LENGTH
        self.implementation_class_uid = assoc.ae.implementation_class_uid

        # The are the proposed extended negotiation items,
        self._ext_neg = {}
        self.reset_negotiation_items()

        # If Acceptor then this the accepted SOP Class Common Extended
        #   negotiation items
        self._common_ext = {}

    @property
    def accepted_common_extended(self):
        """Return a dict of the accepted SOP Class Common Extended Negotiation.

        Returns
        -------
        dict of 2-tuple
            The {SOP Class UID : (Service Class UID, Related General SOP Class
            Identification)} for the accepted SOP Class Common Extended
            negotiation items.

        Raises
        ------
        RuntimeError
            If called when the requestor.
        """
        if not self.is_acceptor:
            raise RuntimeError(
                "'accepted_common_extended' is only available for the "
                "'acceptor'"
            )

        out = {}
        for item in self._common_ext.values():
            out[item.sop_class_uid] = (
                item.service_class_uid,
                item.related_general_sop_class_identification
            )

        return out

    def add_negotiation_item(self, item):
        """Add an extended negotiation item to the user information.

        Items can only be added prior to starting the association negotiation.

        Parameters
        ----------
        item : pdu_primitives.ServiceParameter
            An extended negotiation item, one of
            SCP_SCU_RoleSelectionNegotiation, UserIdentityNegotiation,
            AsynchronousOperationsWindowNegotiation,
            SOPClassExtendedNegotiation or SOPClassCommonExtendedNegotiation.

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
                "Can't add extended negotiation items after negotiation "
                "has started"
            )

        try:
            self._ext_neg[type(item)].append(item)
        except KeyError:
            raise TypeError(
                "'item' is not a valid extended negotiation item"
            )

    @property
    def asynchronous_operations(self):
        """Return the Asynchronous Operations Window operations numbers.

        Returns
        -------
        2-tuple of int
            The (Maximum Number of Operations Invoked, Maximum Number of
            Operations Performed) or (1, 1) if no Asynchronous Operations
            Window Negotiation item is in the extended negotiation items.
        """
        if self.writeable:
            for item in self._ext_neg[AsynchronousOperationsWindowNegotiation]:
                return (
                    item.maximum_number_operations_invoked,
                    item.maximum_number_operations_performed
                )
        else:
            for item in self.user_information:
                if isinstance(item, AsynchronousOperationsWindowNegotiation):
                    return (
                        item.maximum_number_operations_invoked,
                        item.maximum_number_operations_performed
                    )

        return (1, 1)

    @property
    def extended_negotiation(self):
        """Return a list of Extended Negotiation items.

        Extended Negotiation items are:

        * SCP/SCU Role Selection Negotiation (0 or more)
        * Asynchronous Operations Window Negotiation (0 or 1)
        * SOP Class Extended Negotiation (0 or more)
        * SOP Class Common Extended Negotiation (0 or more)
        * User Identity Negotiation (0 or 1)

        Returns
        -------
        list
            If `mode` is 'requestor' then returns a list of the proposed
            extended negotiation items, otherwise returns a list of the
            extended negotiation item responses.
        """
        items = []
        if self.writeable:
            for negotiation_type in self._ext_neg:
                items.extend(self._ext_neg[negotiation_type])

            return items

        # pylint: disable=unidiomatic-typecheck
        for item in self.user_information:
            if type(item) in self._ext_neg.keys():
                items.append(item)

        return items

    def get_contexts(self, cx_type):
        """Return a list of PresentationContext corresponding to `cx_type`.

        Parameters
        ----------
        cx_type : str
            The type of contexts to return, if `mode` is 'requestor':

            - If the association has not yet been negotiated then 'requested'.
            - If the association has been negotiated then 'requested' or
              'pcdl'.

            If `mode` is 'acceptor':

            - If the association has not yet been negotiated then 'supported'.
            - If the association has been negotiated then 'supported' or
              'pcdrl'.

        Returns
        -------
        list of presentation.PresentationContext
            A list of presentations contexts, if `cx_type` is 'requested' then
            the requested presentation contexts, if 'pcdl' then the
            presentation contexts from the A-ASSOCIATE (request) primitive's
            Presentation Context Definition List parameter. If 'supported' then
            the supported presentation contexts, if 'pcdrl' then the
            presentation contexts from the A-ASSOCIATE (accept) primitive's
            Presentation Context Definition Results List parameter.
        """
        contexts = {'requested' : self._contexts, 'supported' : self._contexts}
        if not self.writeable:
            contexts.update({
                'pcdl' : self.primitive.presentation_context_definition_list,
                'pcdrl' : (
                    self.primitive.presentation_context_definition_results_list
                )
            })

        possible = {
            True : {
                True : ['requested'],
                False : ['supported'],
            },
            False : {
                True : ['requested', 'pcdl'],
                False : ['supported', 'pcdrl'],
            }
        }

        available = possible[self.writeable][self.is_requestor]
        if cx_type in available:
            return contexts[cx_type]

        available = ["'{}'".format(vv) for vv in available]
        raise ValueError(
            "Invalid 'cx_type', must be {}".format(' or '.join(available))
        )

    @property
    def implementation_class_uid(self):
        """Return the Implementation Class UID as a pydicom UID.

        Returns
        -------
        pydicom.uid.UID or None
            Returns the Implementation Class UID if the requestor or if
            the acceptor and they have accepted the negotiation. Returns None
            if the acceptor and they have rejected the negotiation.
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
    def implementation_class_uid(self, value):
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
    def implementation_version_name(self):
        """Return the Implementation Version Name as str (if available).

        Returns
        -------
        str or None
            Returns None if the acceptor and they have rejected the
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
    def implementation_version_name(self, value):
        """Set the Implementation Version Name (only prior to association).

        Parameters
        ----------
        str
            The Implementation Version Name value to use.
        """
        if not self.writeable:
            raise RuntimeError(
                "Can't set the Implementation Version Name after negotiation "
                "has started"
            )

        for item in self._user_info:
            if isinstance(item, ImplementationVersionNameNotification):
                item.implementation_version_name = value
                break
        else:
            item = ImplementationVersionNameNotification()
            item.implementation_version_name = value
            self._user_info.append(item)

    @property
    def info(self):
        """Return a dict with information about the ServiceUser."""
        info = {
            'ae_title' : self.ae_title,
            'address' : self.address,
            'port' : self.port,
            'mode' : self.mode,
        }
        if not self.writeable:
            info['pdv_size'] = self.maximum_length

        return info

    @property
    def is_acceptor(self):
        """Return True if the ServiceUser is the association acceptor."""
        return self.mode == MODE_ACCEPTOR

    @property
    def is_requestor(self):
        """Return True if the ServiceUser is the association requestor."""
        return self.mode == MODE_REQUESTOR

    @property
    def maximum_length(self):
        """Return the maximum PDV size as int.

        Returns
        -------
        int or None
            Returns the Maximum Received Length if the requestor or if
            the acceptor and they have accepted the negotiation. Returns None
            if the acceptor and they have rejected the negotiation.
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
    def maximum_length(self, value):
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
    def mode(self):
        """Return the mode as str, either 'requestor' or 'acceptor'."""
        return self._mode

    @property
    def requested_contexts(self):
        """Return a list of the requestor's requested presentation contexts."""
        return self.get_contexts('requested')

    @requested_contexts.setter
    def requested_contexts(self, value):
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
                "'requested_contexts' can only be set for the association "
                "requestor"
            )

        self._contexts = value

    def remove_negotiation_item(self, item):
        """Remove an extended negotiation item from the user information.

        Items can only be removed prior to starting the association
        negotiation.

        Parameters
        ----------
        item : pdu_primitives.ServiceParameter
            An extended negotiation item, one of
            SCP_SCU_RoleSelectionNegotiation, UserIdentityNegotiation,
            AsynchronousOperationsWindowNegotiation,
            SOPClassExtendedNegotiation or SOPClassCommonExtendedNegotiation.

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
            raise TypeError(
                "'item' is not a valid extended negotiation item"
            )

    def reset_negotiation_items(self):
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
            SCP_SCU_RoleSelectionNegotiation : [],
            AsynchronousOperationsWindowNegotiation : [],
            UserIdentityNegotiation : [],
            SOPClassExtendedNegotiation : [],
        }
        if self.is_requestor:
            self._ext_neg[SOPClassCommonExtendedNegotiation] = []

    @property
    def role_selection(self):
        """Return any SCP/SCU Role Selection items as a dict.

        Returns
        -------
        dict
            The SCP/SCU Role Selection items as {SOP Class UID :
            SCP_SCU_RoleSelectionNegotiation}.
        """
        roles = {}
        if self.writeable:
            for item in self._ext_neg[SCP_SCU_RoleSelectionNegotiation]:
                roles[item.sop_class_uid] = item

            return roles

        for item in self.user_information:
            if isinstance(item, SCP_SCU_RoleSelectionNegotiation):
                roles[item.sop_class_uid] = item

        return roles

    @property
    def sop_class_common_extended(self):
        """Return any SOP Class Common Extended items as dict.

        If the ServiceUser is the association acceptor then no SOP Class
        Common Extended items will be present in the User Information.

        Returns
        -------
        dict
            The SOP Class Common Extended items as {SOP Class UID : item}.
        """
        if self.is_acceptor:
            return {}

        sop_classes = {}
        if self.writeable:
            for item in self._ext_neg[SOPClassCommonExtendedNegotiation]:
                sop_classes[item.sop_class_uid] = item

            return sop_classes

        for item in self.user_information:
            if isinstance(item, SOPClassCommonExtendedNegotiation):
                sop_classes[item.sop_class_uid] = item

        return sop_classes

    @property
    def sop_class_extended(self):
        """Return any SOP Class Extended items as dict.

        Returns
        -------
        dict
            The SOP Class Extended items as {SOP Class UID : Service Class
            Application Information}.
        """
        sop_classes = {}
        if self.writeable:
            for item in self._ext_neg[SOPClassExtendedNegotiation]:
                sop_classes[item.sop_class_uid] = (
                    item.service_class_application_information
                )

            return sop_classes

        for item in self.user_information:
            if isinstance(item, SOPClassExtendedNegotiation):
                sop_classes[item.sop_class_uid] = (
                    item.service_class_application_information
                )

        return sop_classes

    @property
    def supported_contexts(self):
        """Return a list of supported presentation contexts.

        Returns
        -------
        list of presentation.PresentationContext
            The supported presentation contexts when acting as an acceptor.
        """
        return self.get_contexts('supported')

    @supported_contexts.setter
    def supported_contexts(self, value):
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
                "'supported_contexts' can only be set for the association "
                "acceptor"
            )

        self._contexts = value

    @property
    def user_identity(self):
        """Return the User Identity Negotiation Item (if available).

        Returns
        -------
        pdu_primitives.UserIdentityNegotiation or None
            Returns the User Identity item if one is available, otherwise
            None.
        """
        if self.writeable:
            items = self._ext_neg[UserIdentityNegotiation]
            if items:
                return items[0]

            return None

        for item in self.user_information:
            if isinstance(item, UserIdentityNegotiation):
                return item

        return None

    @property
    def user_information(self):
        """Returns a list of the User Information items."""
        if not self.writeable:
            return self.primitive.user_information

        return self._user_info + self.extended_negotiation

    @property
    def writeable(self):
        """Return True if the current object can be changed."""
        return self.primitive is None
