"""
Defines the Association class which handles associating with peers.
"""
from io import BytesIO
import logging
import threading
import time

from pydicom.dataset import Dataset
from pydicom.uid import UID

# pylint: disable=no-name-in-module
from pynetdicom.acse import ACSE
from pynetdicom import _config
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
        True if the association has been aborted, False otherwise.
    is_established : bool
        True if the association has been established, False otherwise.
    is_rejected : bool
        True if the association was rejected, False otherwise.
    is_released : bool
        True if the association has been released, False otherwise.
    mode : str
        The mode of the local AE, either the association 'requestor' or
        association 'acceptor'.
    requestor : association.ServiceUser
        Representation of the association's requestor AE.
    """
    def __init__(self, ae, mode):
        """Create a new Association instance.

        The Association starts in State 1 (idle). Association negotiation
        won't begin until an AssociationSocket is assigned using set_socket()
        and Association.start() is called.

        Parameters
        ----------
        ae : ae.ApplicationEntity
            The local AE.
        mode : str
            Must be "requestor" or "acceptor".
        """
        self._ae = ae
        self.mode = mode

        # Represents the association requestor and acceptor users
        self.requestor = ServiceUser(self, MODE_REQUESTOR)
        self.acceptor = ServiceUser(self, MODE_ACCEPTOR)

        # Status attributes
        self.is_established = False
        self.is_rejected = False
        self.is_aborted = False
        self.is_released = False

        # Accepted and rejected presentation contexts
        self._accepted_cx = []
        self._rejected_cx = []

        # Service providers
        self.acse = ACSE()
        self.dul = DULServiceProvider(self)
        self.dimse = DIMSEServiceProvider(self.dul, self.ae.dimse_timeout)

        # Timeouts (in seconds), needs to be set after DUL init
        self.acse_timeout = self.ae.acse_timeout
        self.dimse_timeout = self.ae.dimse_timeout
        self.network_timeout = self.ae.network_timeout

        # Kills the thread loop in run()
        self._kill = False
        # Flag for whether or not the DUL thread has been started
        self._started_dul = False
        # Used to pause the association reactor until the DUL is ready
        self._dul_ready = threading.Event()

        # Send A-ABORT/A-P-ABORT when an A-ASSOCIATE request is received
        self._a_abort_assoc_rq = False
        self._a_p_abort_assoc_rq = False

        # Point the public send_c_cancel_* functions to the actual function
        # TODO: Deprecated, to be removed in v1.3
        self.send_c_cancel_find = self.send_c_cancel
        self.send_c_cancel_move = self.send_c_cancel
        self.send_c_cancel_get = self.send_c_cancel

        # Thread setup
        threading.Thread.__init__(self)
        self.daemon = True

    def abort(self):
        """Sends an A-ABORT to the remote AE and kills the Association."""
        if not self.is_released:
            self.acse.send_abort(self, 0x00)
            self.kill()

        # Add short delay to ensure everything shuts down
        time.sleep(0.1)

    @property
    def accepted_contexts(self):
        """Return a list of accepted Presentation Contexts."""
        # Accepted contexts are stored internally as {context ID : context}
        return sorted(self._accepted_cx.values(), key=lambda x: x.context_id)

    @property
    def acse_timeout(self):
        """Return the ACSE timeout in seconds."""
        return self._acse_timeout

    @acse_timeout.setter
    def acse_timeout(self, value):
        """Set the ACSE timeout using numeric or None."""
        self.dul.artim_timer.timeout = value
        self._acse_timeout = value

    @property
    def ae(self):
        """Return the Association's parent ApplicationEntity."""
        return self._ae

    def _check_received_status(self, rsp):
        """Return a pydicom Dataset containing status related elements.

        Parameters
        ----------
        rsp : dimse_primitives.DIMSEMessage
            The DIMSE Message primitive received from the peer in response
            to a service request.

        Returns
        -------
        pydicom.dataset.Dataset
            If no response or an invalid response was received from the peer
            then an empty Dataset, if a valid response was received from the
            peer then (at a minimum) a Dataset containing an (0000,0900)
            *Status* element, and any included optional status related
            elements.
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
        """Set the DIMSE timeout using numeric or None."""
        self.dimse.dimse_timeout = value
        self._dimse_timeout = value

    def _get_valid_context(self, ab_syntax, tr_syntax, role, context_id=None):
        """Return a valid Presentation Context matching the parameters.

        Parameters
        ----------
        ab_syntax : str or pydicom.uid.UID
            The abstract syntax to match.
        tr_syntax : str or pydicom.uid.UID
            The transfer syntax to match, if an empty string is used then
            the transfer syntax will not be used for matching. If the value
            corresponds to an uncompressed syntax then matches will be made
            with any uncompressed transfer syntaxes.
        role : str
            One of 'scu' or 'scp', the required role of the context.
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
        """Return True if the local AE is the association acceptor."""
        return self.mode == MODE_ACCEPTOR

    @property
    def is_requestor(self):
        """Return True if the local AE is the association requestor."""
        return self.mode == MODE_REQUESTOR

    def kill(self):
        """Kill the main association thread loop."""
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
            The mode of the Association, must be either "requestor" or
            "acceptor". If "requestor" then its assumed that the local AE
            requests an association with peers and (by default) acts as the
            SCU. If "acceptor" then its assumed that the local AE is listening
            for association requests and (by default) acts as the SCP.
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
        """Set the network timeout using numeric or None."""
        self.dul._idle_timer.timeout = value
        self._network_timeout = value

    @property
    def rejected_contexts(self):
        """Return a list of rejected Presentation Contexts."""
        return self._rejected_cx

    def release(self):
        """Send an A-RELEASE request and initiate association release."""
        if self.is_established:
            self.acse.negotiate_release(self)

    @property
    def remote(self):
        """Return a dict with information about the peer AE."""
        if self.is_acceptor:
            return self.requestor.info

        return self.acceptor.info

    def request(self):
        """Request an association with a peer.

        A request can only be made once the Association instance has been
        configured for requestor mode and been assigned an AssociationSocket.
        """
        # Start the DUL thread if not already started
        self.dul.start()
        self._started_dul = True
        # Wait until the DUL is up and running
        self._dul_ready.wait()
        # Start association negotiation
        self.acse.negotiate_association(self)

    def run(self):
        """The main Association control."""
        # Start the DUL thread if not already started
        if not self._started_dul:
            self.dul.start()
            self._started_dul = True
            # Wait until the DUL is up and running
            self._dul_ready.wait()
            #time.sleep(0.05)

        if self.is_acceptor:
            primitive = self.dul.receive_pdu(wait=True,
                                             timeout=self.acse_timeout)

            # Timed out waiting for A-ASSOCIATE request
            if primitive is None:
                self.kill()
                return

            self.requestor.primitive = primitive

            # (Optionally) send an A-ABORT/A-P-ABORT in response
            if self._a_abort_assoc_rq:
                self.acse.send_abort(self, 0x00)
                self.kill()
                return
            elif self._a_p_abort_assoc_rq:
                self.acse.send_ap_abort(self, 0x00)
                self.kill()
                return

            self.acse.negotiate_association(self)
            if self.is_established:
                self.dimse.maximum_pdu_size = self.requestor.maximum_length
                self._run_as_acceptor()
        else:
            # Association requestor
            # Allow non-blocking negotiation
            if (not self.is_established and not self.is_aborted
                    and not self.is_released and not self.is_rejected):
                self.acse.negotiate_association(self)

            if self.is_established:
                self.dimse.maximum_pdu_size = self.acceptor.maximum_length
                self._run_as_requestor()

    def _run_as_acceptor(self):
        """Run the Association acceptor reactor loop.

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
        info = {
            'requestor' : self.requestor.info,
            'acceptor' : self.acceptor.info,
            'sop_class_extended' : self.acceptor.sop_class_extended,
            'sop_class_common_extended' : (
                self.acceptor.accepted_common_extended
            ),
        }

        while not self._kill:
            time.sleep(0.001)

            # Check with the DIMSE provider to see if a completely decoded
            #   message is available
            msg_context_id, msg = self.dimse.get_msg(block=False)

            # DIMSE message received, should be a service request
            if msg:
                # Use the Message's Affected SOP Class UID or Requested SOP
                #   Class UID to determine which service to use
                # If there's no AffectedSOPClassUID or RequestedSOPClassUID
                #   then we received a C-CANCEL request
                if getattr(msg, 'AffectedSOPClassUID', None) is not None:
                    # DIMSE-C, N-EVENT-REPORT, N-CREATE use AffectedSOPClassUID
                    class_uid = msg.AffectedSOPClassUID
                elif getattr(msg, 'RequestedSOPClassUID', None) is not None:
                    # N-GET, N-SET, N-ACTION, N-DELETE use RequestedSOPClassUID
                    class_uid = msg.RequestedSOPClassUID

                # SOP Class Common Extended Negotiation
                try:
                    # The service class UID
                    class_uid = (
                        self.acceptor.accepted_common_extended[class_uid][0]
                    )
                except KeyError:
                    pass

                # Convert the SOP/Service UID to the corresponding service
                service_class = uid_to_service_class(class_uid)(self)

                try:
                    context = self._accepted_cx[msg_context_id]
                except KeyError:
                    LOGGER.info(
                        "Received DIMSE message with invalid or rejected "
                        "context ID: %d", msg_context_id
                    )
                    LOGGER.debug("%s", msg)
                    self.abort()
                    return

                # Run corresponding Service Class in SCP mode
                try:
                    # Clear out any C-CANCEL requests received beforehand
                    self.dimse.cancel_req = {}
                    service_class.SCP(msg, context, info)
                    # Clear out any unacted upon requests received during
                    self.dimse.cancel_req = {}
                except NotImplementedError:
                    # SCP isn't implemented
                    LOGGER.warning(
                        "No service class implementation for '{}'"
                        .format(context.abstract_syntax)
                    )
                    self.abort()
                    return

            # Check for release request
            if self.acse.is_release_requested(self):
                # Send A-RELEASE response
                self.acse.send_release(self, is_response=True)
                self.is_released = True
                self.is_established = False
                # Callback triggers
                self.ae.on_association_released()
                self.debug_association_released()
                self.kill()
                return

            # Check for abort
            if self.acse.is_aborted(self):
                self.is_aborted = True
                self.is_established = False
                # Callback trigger
                self.debug_association_aborted()
                self.ae.on_association_aborted(None)
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

    def _run_as_requestor(self):
        """Run the association as the requestor."""
        # Listen for further messages from the peer
        while not self._kill:
            time.sleep(0.1)

            # Check for release request
            if self.acse.is_release_requested(self):
                # Send A-RELEASE response
                self.acse.send_release(self, is_response=True)
                self.is_released = True
                self.is_established = False
                # Callback triggers
                self.ae.on_association_released()
                self.debug_association_released()
                self.kill()
                return

            # Check for abort
            if self.acse.is_aborted(self):
                self.is_aborted = True
                self.is_established = False
                # Callback trigger
                self.ae.on_association_aborted()
                self.debug_association_aborted()
                self.kill()
                return

            # Check if the DULServiceProvider thread is
            #   still running. DUL.is_alive() is inherited from
            #   threading.thread
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

        # Attempt to decode the dataset
        # pylint: disable=broad-except
        transfer_syntax = context.transfer_syntax[0]
        if _config.DECODE_STORE_DATASETS:
            try:
                ds = decode(req.DataSet,
                            transfer_syntax.is_implicit_VR,
                            transfer_syntax.is_little_endian)
            except Exception as ex:
                LOGGER.error('Failed to decode the received dataset')
                LOGGER.exception(ex)
                rsp.Status = 0xC210
                rsp.ErrorComment = 'Unable to decode the dataset'
                self.dimse.send_msg(rsp, context.context_id)
                return
        else:
            ds = req.DataSet.getvalue()

        info = {
            'acceptor' : self.acceptor.info,
            'requestor': self.requestor.info,
            'parameters' : {
                'message_id' : req.MessageID,
                'priority' : req.Priority,
                'originator_aet' : req.MoveOriginatorApplicationEntityTitle,
                'original_message_id' : req.MoveOriginatorMessageID
            }
        }

        #  Attempt to run the ApplicationEntity's on_c_store callback
        try:
            status = self.ae.on_c_store(ds, context.as_tuple, info)
        except Exception as ex:
            LOGGER.error("Exception in the "
                         "ApplicationEntity.on_c_store() callback")
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
            The message ID of the C-GET/MOVE/FIND operation we want to cancel.
            Must be between 0 and 65535, inclusive.
        context_id : int
            The presentation context ID of the original C-GET/MOVE/FIND
            service request.
        """
        # Can't send a C-CANCEL without an Association
        if not self.is_established:
            raise RuntimeError("The association with a peer SCP must be "
                               "established before sending a C-CANCEL request.")

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
            Status value, may optionally contain additional elements (see
            DICOM Standard Part 7, Annex C).

            The DICOM Standard Part 7, Table 9.3-13 indicates that the Status
            value of a C-ECHO response "shall have a value of Success". However
            Section 9.1.5.1.4 indicates it may have any of the following
            values:

            Success
              | ``0x0000`` Success

            Failure
              | ``0x0122`` SOP class not supported
              | ``0x0210`` Duplicate invocation
              | ``0x0211`` Unrecognised operation
              | ``0x0212`` Mistyped argument

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
        ae.ApplicationEntity.on_c_echo
        dimse_primitives.C_ECHO
        service_class.VerificationServiceClass

        References
        ----------

        * DICOM Standard Part 4, `Annex A <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_A>`_
        * DICOM Standard Part 7, Sections
          `9.1.5 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.1.5>`_,
           and `9.3.5 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.5>`_
          `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_
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
        self.dimse.send_msg(primitive, context.context_id)
        cx_id, rsp = self.dimse.get_msg(block=True)

        # If `rsp` is None then the DIMSE timeout expired so abort
        if rsp is None:
            if self.is_established:
                LOGGER.error("Connection closed or timed-out")
                self.abort()
            return Dataset()

        # Determine validity of the response and get the status
        status = self._check_received_status(rsp)

        return status

    def send_c_find(self, dataset, msg_id=1, priority=2, query_model='P'):
        """Send a C-FIND request to the peer AE.

        Yields ``(status, identifier)`` pairs.

        Parameters
        ----------
        dataset : pydicom.dataset.Dataset
            The C-FIND request's *Identifier* dataset. The exact requirements
            for the *Identifier* dataset are Service Class specific (see the
            DICOM Standard, Part 4).
        msg_id : int, optional
            The DIMSE *Message ID*, must be between 0 and 65535, inclusive,
            (default 1).
        priority : int, optional
            The C-FIND operation *Priority* (may not be supported by the peer),
            one of:

            - ``0`` - Medium
            - ``1`` - High
            - ``2`` - Low (default)

        query_model : str, optional
            The Information Model to use, one of the following:

            - ``P`` - *Patient Root Information Model - FIND*
              1.2.840.10008.5.1.4.1.2.1.1 (default)
            - ``S`` - *Study Root Information Model - FIND*
              1.2.840.10008.5.1.4.1.2.2.1
            - ``O`` - *Patient Study Only Information Model - FIND*
              1.2.840.10008.5.1.4.1.2.3.1
            - ``W`` - *Modality Worklist Information - FIND*
              1.2.840.10008.5.1.4.31
            - ``G`` - *General Relevant Patient Information Query*
              1.2.840.10008.5.1.4.37.1
            - ``B`` - *Breast Imaging Relevant Patient Information Query*
              1.2.840.10008.5.1.4.37.2
            - ``C`` - *Cardiac Relevant Patient Information Query*
              1.2.840.10008.5.1.4.37.3
            - ``PC`` - *Product Characteristics Query Information Model - FIND*
              1.2.840.10008.5.1.4.41
            - ``SA`` - *Substance Approval Query Information Model - FIND*
              1.2.840.10008.5.1.4.42
            - ``H`` - *Hanging Protocol Information Model - FIND*
              1.2.840.10008.5.1.4.38.2
            - ``D`` - *Defined Procedure Protocol Information Model - FIND*
              1.2.840.10008.5.1.4.20.1
            - ``CP`` - *Color Palette Information Model - FIND*
              1.2.840.10008.5.1.4.39.2
            - ``IG`` - *Generic Implant Template Information Model - FIND*
              1.2.840.10008.5.1.4.43.2
            - ``IA`` - *Implant Assembly Template Information Model - FIND*
              1.2.840.10008.5.1.4.44.2
            - ``IT`` - *Implant Template Group Information Model - FIND*
              1.2.840.10008.5.1.4.44.2

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
            following values, but as the returned value depends
            on the peer this can't be assumed:

            General C-FIND (Part 7, Section 9.1.2.1.5 and Annex C)

            Cancel
              | ``0xFE00`` Matching terminated due to Cancel request

            Success
              | ``0x0000`` Matching is complete: no final Identifier is
                supplied

            Failure
              | ``0x0122`` SOP class not supported

            Query/Retrieve Service, Basic Worklist Management Service,
            Hanging Protocol Query/Retrieve Service, Defined Procedure Protocol
            Query/Retrieve Service, Substance Administration Query Service,
            Color Palette Query/Retrieve Service and Implant Template
            Query/Retrieve Service specific
            (DICOM Standard Part 4, Annexes C.4.1, K.4.1.1.4, U.4.1, HH,
            V.4.1.1.4, X and BB):

            Failure
              | ``0xA700`` Out of resources
              | ``0xA900`` Identifier does not match SOP Class
              | ``0xC000`` to ``0xCFFF`` Unable to process

            Pending
              | ``0xFF00`` Matches are continuing: current match is supplied
                and any Optional Keys were supported in the same manner as
                Required Keys
              | ``0xFF01`` Matches are continuing: warning that one or more
                Optional Keys were not supported for existence and/or matching
                for this Identifier)

            Relevant Patient Information Query Service specific (DICOM
            Standard Part 4, Annex Q.2.1.1.4):

            Failure
              | ``0xA700`` Out of resources
              | ``0xA900`` Identifier does not match SOP Class
              | ``0xC000`` Unable to process
              | ``0xC100`` More than one match found
              | ``0xC200`` Unable to support requested template

            Pending
              | ``0xFF00`` Matches are continuing: current match is supplied
                and any Optional Keys were supported in the same manner as
                Required Keys

        identifier : pydicom.dataset.Dataset or None
            If the status is 'Pending' then the C-FIND response's *Identifier*
            ``Dataset``. If the status is not 'Pending' this will be ``None``.
            The exact contents of the response *Identifier* are Service Class
            specific (see the DICOM Standard, Part 4).

        Raises
        ------
        RuntimeError
            If ``send_c_find`` is called with no established association.
        ValueError
            If no accepted Presentation Context for `dataset` exists or if
            unable to encode the *Identifier* `dataset`.

        See Also
        --------
        ae.ApplicationEntity.on_c_find
        dimse_primitives.C_FIND
        service_class.QueryRetrieveFindServiceClass
        service_class.RelevantPatientInformationQueryServiceClass
        service_class.SubstanceAdministrationQueryServiceClass
        service_class.HangingProtocolQueryRetrieveServiceClass
        service_class.DefinedProcedureProtocolQueryRetrieveServiceClass
        service_class.ColorPaletteQueryRetrieveServiceClass
        service_class.ImplantTemplateQueryRetrieveServiceClass

        References
        ----------

        * DICOM Standard Part 4, `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_C>`_
        * DICOM Standard Part 4, `Annex Q <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_Q>`_
        * DICOM Standard Part 4, `Annex U <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_U>`_
        * DICOM Standard Part 4, `Annex V <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_V>`_
        * DICOM Standard Part 4, `Annex X <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_X>`_
        * DICOM Standard Part 4, `Annex BB <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_BB>`_
        * DICOM Standard Part 4, `Annex HH <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_HH>`_
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
        }

        try:
            sop_class = _sop_classes[query_model]
        except KeyError:
            raise ValueError(
                "Unsupported value for `query_model`: {}".format(query_model)
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

        LOGGER.info('Find SCU Request Identifiers:')
        LOGGER.info('')
        LOGGER.info('# DICOM Dataset')
        for elem in dataset:
            LOGGER.info(elem)
        LOGGER.info('')

        # Send C-FIND request to the peer via DIMSE
        self.dimse.send_msg(req, context.context_id)

        # Get the responses from the peer
        # Wrap the generator so the C-FIND-RQ is sent immediately on
        #   executing this function, otherwise sending C-CANCEL requests
        #   may end up being sent first unless next() is called
        return self._wrap_find_responses(transfer_syntax)

    def send_c_get(self, dataset, msg_id=1, priority=2, query_model='P'):
        """Send a C-GET request to the peer AE.

        Yields ``(status, identifier)`` pairs.

        The ``AE.on_c_store`` callback should be implemented prior
        to calling ``send_c_get`` as the peer will return any matches via a
        C-STORE sub-operation over the current association. In addition,
        SCP/SCU Role Selection Negotiation must be supported by the
        Association.

        Parameters
        ----------
        dataset : pydicom.dataset.Dataset
            The C-GET request's *Identifier* ``Dataset``. The exact
            requirements for the *Identifier* are Service Class specific (see
            the DICOM Standard, Part 4).
        msg_id : int, optional
            The DIMSE *Message ID*, must be between 0 and 65535, inclusive,
            (default 1).
        priority : int, optional
            The C-GET operation *Priority* (may not be supported by the peer),
            one of:

            - ``0`` - Medium
            - ``1`` - High
            - ``2`` - Low (default)

        query_model : str, optional
            The Query/Retrieve Information Model to use, one of the following:

            - ``P`` - *Patient Root Information Model - GET*
              1.2.840.10008.5.1.4.1.2.1.3 (default)
            - ``S`` - *Study Root Information Model - GET*
              1.2.840.10008.5.1.4.1.2.2.3
            - ``O`` - *Patient Study Only Information Model - GET*
              1.2.840.10008.5.1.4.1.2.3.3
            - ``C`` - *Composite Instance Root Retrieve - GET*
              1.2.840.10008.5.1.4.1.2.4.3
            - ``CB`` - *Composite Instance Retrieve Without Bulk Data - GET*
              1.2.840.10008.5.1.4.1.2.5.3
            - ``H`` - *Hanging Protocol Information Model - GET*
              1.2.840.10008.5.1.4.38.4
            - ``D`` - *Defined Procedure  Protocol Information Model - GET*
              1.2.840.10008.5.1.4.20.3
            - ``CP`` - *Palette Color Information Model - GET*
              1.2.840.10008.5.1.4.39.4
            - ``IG`` - *Generic Implant Template Information Model - GET*
              1.2.840.10008.5.1.4.43.4
            - ``IA`` - *Implant Assembly Template Information Model - GET*
              1.2.840.10008.5.1.4.44.4
            - ``IT`` - *Implant Template Group Information Model - GET*
              1.2.840.10008.5.1.4.44.4

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
            following values, but as the returned value depends on the
            peer this can't be assumed:

            General C-GET (DICOM Standard Part 7, Section 9.1.3 and Annex C)

            Success
              | ``0x0000`` Sub-operations complete: no failures or warnings

            Failure
              | ``0x0122`` SOP class not supported
              | ``0x0124`` Not authorised
              | ``0x0210`` Duplicate invocation
              | ``0x0211`` Unrecognised operation
              | ``0x0212`` Mistyped argument

            Query/Retrieve Service, Hanging Protocol Query/Retrieve Service,
            Defined Procedure Protocol Query/Retrieve Service, Color Palette
            Query/Retrieve Service and Implant Template Query/Retrieve Service
            specific (DICOM Standard Part 4, Annexes C.4.3, Y.C.4.2.1.4,
            Z.4.2.1.4, U.4.3, X, BB and HH):

            Pending
              | ``0xFF00`` Sub-operations are continuing

            Cancel
              | ``0xFE00`` Sub-operations terminated due to Cancel indication

            Failure
              | ``0xA701`` Out of resources: unable to calculate number of
                 matches
              | ``0xA702`` Out of resources: unable to perform sub-operations
              | ``0xA900`` Identifier does not match SOP class
              | ``0xAA00`` None of the frames requested were found in the SOP
                instance
              | ``0xAA01`` Unable to create new object for this SOP class
              | ``0xAA02`` Unable to extract frames
              | ``0xAA03`` Time-based request received for a non-time-based
                original SOP Instance
              | ``0xAA04`` Invalid request
              | ``0xC000`` to ``0xCFFF`` Unable to process

            Warning
              | ``0xB000`` Sub-operations completed: one or more failures or
                 warnings

        identifier : pydicom.dataset.Dataset or None
            If the status is 'Pending' or 'Success' then yields ``None``. If
            the status is 'Warning', 'Failure' or 'Cancel' then yields a
            ``Dataset`` which should contain an (0008,0058) *Failed SOP
            Instance UID List* element, however this is not guaranteed and may
            instead return an empty ``Dataset``.

        Raises
        ------
        RuntimeError
            If ``send_c_get`` is called with no established association.
        ValueError
            If no accepted Presentation Context for `dataset` exists or if
            unable to encode the *Identifier* `dataset`.

        See Also
        --------
        ae.ApplicationEntity.on_c_get
        ae.ApplicationEntity.on_c_store
        service_class.QueryRetrieveGetServiceClass
        service_class.HangingProtocolQueryRetrieveServiceClass
        service_class.DefinedProcedureProtocolQueryRetrieveServiceClass
        service_class.ColorPaletteQueryRetrieveServiceClass
        service_class.ImplantTemplateQueryRetrieveServiceClass
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
        * DICOM Standard Part 7, Sections
          `9.1.3 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.1.3>`_,
          `9.3.3 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.3>`_
          and `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_
        """
        # Can't send a C-GET without an Association
        if not self.is_established:
            raise RuntimeError("The association with a peer SCP must be "
                               "established before sending a C-GET request")

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
        }

        try:
            sop_class = _sop_classes[query_model]
        except KeyError:
            raise ValueError(
                "Unsupported value for `query_model`: {}".format(query_model)
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

        LOGGER.info('Get SCU Request Identifier:')
        LOGGER.info('')
        LOGGER.info('# DICOM Dataset')
        for elem in dataset:
            LOGGER.info(elem)
        LOGGER.info('')

        # Send C-GET request to the peer via DIMSE
        self.dimse.send_msg(req, context.context_id)

        # Get the responses from the peer
        # Wrap the generator so the C-GET-RQ is sent immediately on
        #   executing this function, otherwise sending C-CANCEL requests
        #   may end up being sent first unless next() is called
        return self._wrap_get_move_responses(transfer_syntax)

    def send_c_move(self, dataset, move_aet, msg_id=1, priority=2,
                    query_model='P'):
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
            The AE title of the destination for the C-STORE sub-operations
            performed by the peer.
        msg_id : int, optional
            The DIMSE *Message ID*, must be between 0 and 65535, inclusive,
            (default 1).
        priority : int, optional
            The C-MOVE operation *Priority* (if supported by the peer), one of:

            - ``0`` - Medium
            - ``1`` - High
            - ``2`` - Low (default)

        query_model : str, optional
            The Query/Retrieve Information Model to use, one of the following:

            - ``P`` - *Patient Root Information Model - MOVE*
              1.2.840.10008.5.1.4.1.2.1.2 (default)
            - ``S`` - *Study Root Information Model - MOVE*
              1.2.840.10008.5.1.4.1.2.2.2
            - ``O`` - *Patient Study Only Information Model - MOVE*
              1.2.840.10008.5.1.4.1.2.3.2
            - ``C`` - *Composite Instance Root Retrieve - MOVE*
              1.2.840.10008.5.1.4.1.2.4.2
            - ``H`` - *Hanging Protocol Information Model - MOVE*
              1.2.840.10008.5.1.4.38.3
            - ``D`` - *Defined Procedure Protocol Information Model - MOVE*
              1.2.840.10008.5.1.4.20.2
            - ``CP`` - *Color Palette Information Model - MOVE*
              1.2.840.10008.5.1.4.39.3
            - ``IG`` - *Generic Implant Template Information Model - MOVE*
              1.2.840.10008.5.1.4.43.3
            - ``IA`` - *Implant Assembly Template Information Model - MOVE*
              1.2.840.10008.5.1.4.44.3
            - ``IT`` - *Implant Template Group Information Model - MOVE*
              1.2.840.10008.5.1.4.44.3

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
            following values, but as the returned value depends
            on the peer this can't be assumed:

            General C-MOVE (DICOM Standard Part 7, 9.1.4.1.7 and Annex C)

            Cancel
              | ``0xFE00`` Sub-operations terminated due to Cancel indication

            Success
              | ``0x0000`` Sub-operations complete: no failures

            Failure
              | ``0x0122`` SOP class not supported

            Query/Retrieve Service, Hanging Protocol Query/Retrieve Service,
            Defined Procedure Protocol Query/Retrieve Service, Color Palette
            Query/Retrieve Service and Implant Template Query/Retreive
            Service
            specific (DICOM Standard Part 4, Annexes C, U, Y, X, BB and HH):

            Failure
              | ``0xA701`` Out of resources: unable to calculate number of
                matches
              | ``0xA702`` Out of resources: unable to perform sub-operations
              | ``0xA801`` Move destination unknown
              | ``0xA900`` Identifier does not match SOP Class
              | ``0xAA00`` None of the frames requested were found in the SOP
                instance
              | ``0xAA01`` Unable to create new object for this SOP class
              | ``0xAA02`` Unable to extract frames
              | ``0xAA03`` Time-based request received for a non-time-based
                original SOP Instance
              | ``0xAA04`` Invalid request
              | ``0xC000`` to ``0xCFFF`` Unable to process

            Pending
              | ``0xFF00`` Sub-operations are continuing

            Warning
              | ``0xB000`` Sub-operations complete: one or more failures

        identifier : pydicom.dataset.Dataset or None
            If the status is 'Pending' or 'Success' then yields ``None``. If
            the status is 'Warning', 'Failure' or 'Cancel' then yields a
            ``Dataset`` which should contain an (0008,0058) *Failed SOP
            Instance UID List* element, however this is not guaranteed and may
            instead return an empty ``Dataset``.

        See Also
        --------
        ae.ApplicationEntity.on_c_move
        ae.ApplicationEntity.on_c_store
        dimse_primitives.C_MOVE
        service_class.QueryRetrieveMoveServiceClass
        service_class.HangingProtocolQueryRetrieveServiceClass
        service_class.ColorPaletteQueryRetrieveServiceClass
        service_class.ImplantTemplateQueryRetrieveServiceClass

        References
        ----------

        * DICOM Standard Part 4, `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_C>`_
        * DICOM Standard Part 4, `Annex U <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_U>`_
        * DICOM Standard Part 4, `Annex X <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_X>`_
        * DICOM Standard Part 4, `Annex Y <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_Y>`_
        * DICOM Standard Part 4, `Annex BB <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_BB>`_
        * DICOM Standard Part 4, `Annex HH <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_HH>`_
        * DICOM Standard Part 7, Sections
          `9.1.4 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.1.4>`_,
          `9.3.4 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.4>`_
          and `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_
        """
        # Can't send a C-MOVE without an Association
        if not self.is_established:
            raise RuntimeError("The association with a peer SCP must be "
                               "established before sending a C-MOVE request")

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
        }

        try:
            sop_class = _sop_classes[query_model]
        except KeyError:
            raise ValueError(
                "Unsupported value for `query_model`: {}".format(query_model)
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

        LOGGER.info('Move SCU Request Identifier:')
        LOGGER.info('')
        LOGGER.info('# DICOM Dataset')
        for elem in dataset:
            LOGGER.info(elem)
        LOGGER.info('')

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
            The AE title of the peer that invoked the C-MOVE operation for
            which this C-STORE sub-operation is being performed (default
            ``None``).
        originator_id : int, optional
            The Message ID of the C-MOVE request primitive from which this
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

            General C-STORE (DICOM Standard Part 7, 9.1.1.1.9 and Annex C):

            Success
              | ``0x0000`` Success

            Failure
              | ``0x0117`` Invalid SOP instance
              | ``0x0122`` SOP class not supported
              | ``0x0124`` Not authorised
              | ``0x0210`` Duplicate invocation
              | ``0x0211`` Unrecognised operation
              | ``0x0212`` Mistyped argument

            Storage Service and Non-Patient Object Storage Service specific
            (DICOM Standard Part 4, Annexes B.2.3 and GG):

            Failure
              | ``0xA700`` to ``0xA7FF`` Out of resources
              | ``0xA900`` to ``0xA9FF`` Data set does not match SOP class
              | ``0xC000`` to ``0xCFFF`` Cannot understand

            Warning
              | ``0xB000`` Coercion of data elements
              | ``0xB006`` Element discarded
              | ``0xB007`` Data set does not match SOP class

            Non-Patient Object Service Class specific (DICOM Standard Part 4,
            Annex GG.4.2)

            Failure
              | ``0xA700`` Out of resources
              | ``0xA900`` Data set does not match SOP class
              | ``0xC000`` Cannot understand

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
        ae.ApplicationEntity.on_c_store
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

        # Send C-STORE request to the peer via DIMSE and wait for the response
        self.dimse.send_msg(req, context.context_id)
        cx_id, rsp = self.dimse.get_msg(block=True)

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
                yield Dataset(), None
                return

            if not isinstance(rsp, C_FIND):
                LOGGER.error(
                    'Received an unexpected {} message from the peer'
                    .format(rsp.__class__.__name__.replace('_', '-'))
                )
                self.abort()
                yield Dataset(), None
                return

            if not rsp.is_valid_response:
                LOGGER.error(
                    'Received an invalid C-FIND response from the peer'
                )
                self.abort()
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
                    "Find SCP Response: {} (Pending)".format(operation_no)
                )
            elif category in [STATUS_SUCCESS, STATUS_CANCEL, STATUS_WARNING]:
                LOGGER.info(
                    'Find SCP Result: ({})'.format(category)
                )
            elif category == STATUS_FAILURE:
                LOGGER.info(
                    'Find SCP Result: (Failure - 0x{:04x})'
                    .format(status.Status)
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
                    LOGGER.debug('# DICOM Dataset')
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
            yield status, identifier
            break

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
                yield Dataset(), None
                return

            if not isinstance(rsp, (C_STORE, C_GET, C_MOVE)):
                LOGGER.error(
                    'Received an unexpected {} message from the peer'
                    .format(rsp_type)
                )
                self.abort()
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
                    "{} SCP Response: {} (Pending)"
                    .format(rsp_name[rsp_type], operation_no + 1)
                )
            elif category in [STATUS_SUCCESS, STATUS_CANCEL, STATUS_WARNING]:
                LOGGER.info(
                    '{} SCP Result: ({})'.format(rsp_name[rsp_type], category)
                )
            elif category == STATUS_FAILURE:
                LOGGER.info(
                    '{} SCP Result: (Failure - 0x{:04x})'
                    .format(rsp_name[rsp_type], status.Status)
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
                    LOGGER.debug('')
                    LOGGER.debug('# DICOM Dataset')
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
            yield status, identifier
            break

    # DIMSE-N services provided by the Association
    def send_n_action(self, dataset, action_type, class_uid, instance_uid,
                      msg_id=1):
        """Send an N-ACTION request message to the peer AE.

        Parameters
        ----------
        dataset : pydicom.dataset.Dataset or None
            The dataset that will be sent as the *Action Information*
            parameter in the N-ACTION request, or None if not required.
        action_type : int
            The value of the request's (0000,1008) *Action Type ID* element.
        class_uid : pydicom.uid.UID
            The UID to be sent in the request's (0000,0003) *Requested SOP
            Class UID* element.
        instance_uid : pydicom.uid.UID
            The UID to be sent in the request's (0000,1001) *Requested SOP
            Instance UID* element.
        msg_id : int, optional
            The DIMSE *Message ID*, must be between 0 and 65535, inclusive,
            (default 1).

        Returns
        -------
        status : pydicom.dataset.Dataset
            If the peer timed out, aborted or sent an invalid response then
            returns an empty ``Dataset``. If a response was received from the
            peer then returns a ``Dataset`` containing at least a (0000,0900)
            *Status* element, and depending on the returned value, may
            optionally contain additional elements (see the DICOM Standard,
            Part 7, Section 9.1.2.1.5 and Annex C).

            General N-ACTION (DICOM Standard Part 7, Section 10.1.4 and
            Annex C)

            Success
              | ``0x0000`` Successful operation

            Failure
              | ``0x0110`` Processing failure
              | ``0x0112`` No such SOP Instance
              | ``0x0114`` No such argument
              | ``0x0115`` Invalid argument value
              | ``0x0117`` Invalid object instance
              | ``0x0118`` No such SOP Class
              | ``0x0119`` Class-Instance conflict
              | ``0x0123`` No such action
              | ``0x0124`` Not authorised
              | ``0x0210`` Duplicate invocation
              | ``0x0211`` Unrecognised operation
              | ``0x0212`` Mistyped argument
              | ``0x0213`` Resource limitation

        action_reply : pydicom.dataset.Dataset or None
            If the status is 'Success' then a ``Dataset`` containing attributes
            corresponding to those supplied in the *Action Reply*,
            otherwise returns None.

        See Also
        --------
        ae.ApplicationEntity.on_n_action
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
        context = self._get_valid_context(class_uid, '', 'scu')
        transfer_syntax = context.transfer_syntax[0]

        # Build N-ACTION request primitive
        #   (M) Message ID
        #   (M) Requested SOP Class UID
        #   (M) Requested SOP Instance UID
        #   (M) Action Type ID
        req = N_ACTION()
        req.MessageID = msg_id
        req.RequestedSOPClassUID = class_uid
        req.RequestedSOPInstanceUID = instance_uid
        req.ActionTypeID = action_type

        # Encode the `dataset` using the agreed transfer syntax
        #   Will return None if failed to encode
        bytestream = encode(dataset,
                            transfer_syntax.is_implicit_VR,
                            transfer_syntax.is_little_endian)

        if bytestream is not None:
            req.ActionInformation = BytesIO(bytestream)
        else:
            LOGGER.error("Failed to encode the supplied Dataset")
            raise ValueError('Failed to encode the supplied Dataset')

        # Send N-ACTION request to the peer via DIMSE and wait for the response
        self.dimse.send_msg(req, context.context_id)
        cx_id, rsp = self.dimse.get_msg(block=True)

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

            # Attempt to decode the response's dataset
            # pylint: disable=broad-except
            try:
                action_reply = decode(rsp.ActionReply,
                                      transfer_syntax.is_implicit_VR,
                                      transfer_syntax.is_little_endian)
            except Exception as ex:
                LOGGER.error("Failed to decode the received dataset")
                LOGGER.exception(ex)
                # Failure: Processing failure
                status.Status = 0x0110

        return status, action_reply

    def send_n_create(self, dataset, class_uid, instance_uid, msg_id=1):
        """Send an N-CREATE request message to the peer AE.

        Parameters
        ----------
        dataset : pydicom.dataset.Dataset or None
            The dataset that will be sent as the *Attribute List*
            parameter in the N-CREATE request, or None if not required.
        class_uid : pydicom.uid.UID
            The UID to be sent in the request's (0000,0002) *Affected SOP
            Class UID* element.
        instance_uid : pydicom.uid.UID or None
            The UID to be sent in the request's (0000,1000) *Affected SOP
            Instance UID* element or None if not required.
        msg_id : int, optional
            The DIMSE *Message ID*, must be between 0 and 65535, inclusive,
            (default 1).

        Returns
        -------
        status : pydicom.dataset.Dataset
            If the peer timed out, aborted or sent an invalid response then
            returns an empty ``Dataset``. If a response was received from the
            peer then returns a ``Dataset`` containing at least a (0000,0900)
            *Status* element, and depending on the returned value, may
            optionally contain additional elements (see the DICOM Standard,
            Part 7, Section 9.1.2.1.5 and Annex C).

            General N-CREATE (DICOM Standard Part 7, Section 10.1.5 and
            Annex C)

            Success
              | ``0x0000`` Successful operation

            Failure
              | ``0x0110`` Processing failure
              | ``0x0112`` No such SOP Instance
              | ``0x0114`` No such argument
              | ``0x0115`` Invalid argument value
              | ``0x0117`` Invalid object instance
              | ``0x0118`` No such SOP Class
              | ``0x0119`` Class-Instance conflict
              | ``0x0123`` No such action
              | ``0x0124`` Not authorised
              | ``0x0210`` Duplicate invocation
              | ``0x0211`` Unrecognised operation
              | ``0x0212`` Mistyped argument
              | ``0x0213`` Resource limitation

        attribute_list : pydicom.dataset.Dataset or None
            If the status is 'Success' then a ``Dataset`` containing attributes
            corresponding to those supplied in the *Attribute List*,
            otherwise returns None.

        See Also
        --------
        ae.ApplicationEntity.on_n_create
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
        context = self._get_valid_context(class_uid, '', 'scu')
        transfer_syntax = context.transfer_syntax[0]

        # Build N-CREATE request primitive
        #   (M) Message ID
        #   (M) Affected SOP Class UID
        #   (M) Affected SOP Instance UID
        req = N_CREATE()
        req.MessageID = msg_id
        req.AffectedSOPClassUID = class_uid
        req.AffectedSOPInstanceUID = instance_uid

        # Encode the `dataset` using the agreed transfer syntax
        #   Will return None if failed to encode
        bytestream = encode(dataset,
                            transfer_syntax.is_implicit_VR,
                            transfer_syntax.is_little_endian)

        if bytestream is not None:
            req.AttributeList = BytesIO(bytestream)
        else:
            LOGGER.error("Failed to encode the supplied Dataset")
            raise ValueError('Failed to encode the supplied Dataset')

        # Send N-CREATE request to the peer via DIMSE and wait for the response
        self.dimse.send_msg(req, context.context_id)
        cx_id, rsp = self.dimse.get_msg(block=True)

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

            # Attempt to decode the response's dataset
            # pylint: disable=broad-except
            try:
                attribute_list = decode(rsp.AttributeList,
                                        transfer_syntax.is_implicit_VR,
                                        transfer_syntax.is_little_endian)
            except Exception as ex:
                LOGGER.error("Failed to decode the received dataset")
                LOGGER.exception(ex)
                # Failure: Processing failure
                status.Status = 0x0110

        return status, attribute_list

    def send_n_delete(self, class_uid, instance_uid, msg_id=1):
        """Send an N-DELETE request message to the peer AE.

        Parameters
        ----------
        class_uid : pydicom.uid.UID
            The UID to be sent in the request's (0000,0003) *Requested SOP
            Class UID* element.
        instance_uid : pydicom.uid.UID
            The UID to be sent in the request's (0000,1001) *Requested SOP
            Instance UID* element.
        msg_id : int, optional
            The DIMSE *Message ID*, must be between 0 and 65535, inclusive,
            (default 1).

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
              | ``0x0000`` Successful operation

            Failure
              | ``0x0110`` Processing failure
              | ``0x0112`` No such SOP Instance
              | ``0x0117`` Invalid object instance
              | ``0x0118`` No such SOP Class
              | ``0x0119`` Class-Instance conflict
              | ``0x0124`` Not authorised
              | ``0x0210`` Duplicate invocation
              | ``0x0211`` Unrecognised operation
              | ``0x0212`` Mistyped argument
              | ``0x0213`` Resource limitation

        See Also
        --------
        ae.ApplicationEntity.on_n_delete
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
        context = self._get_valid_context(class_uid, '', 'scu')

        # Build N-DELETE request primitive
        #   (M) Message ID
        #   (M) Requested SOP Class UID
        #   (M) Requested SOP Instance UID
        req = N_DELETE()
        req.MessageID = msg_id
        req.RequestedSOPClassUID = class_uid
        req.RequestedSOPInstanceUID = instance_uid

        # Send N-DELETE request to the peer via DIMSE and wait for the response
        self.dimse.send_msg(req, context.context_id)
        cx_id, rsp = self.dimse.get_msg(block=True)

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
                            instance_uid, msg_id=1):
        """Send an N-EVENT-REPORT request message to the peer AE.

        Parameters
        ----------
        dataset : pydicom.dataset.Dataset
            The dataset that will be sent as the *Event Information* parameter
            in the N-EVENT-REPORT request.
        event_type : int
            The value to be sent in the request's (0000,10002) *Event Type ID*
            element.
        class_uid : pydicom.uid.UID
            The UID to be sent in the request's (0000,0003) *Affected SOP
            Class UID* element.
        instance_uid : pydicom.uid.UID
            The UID to be sent in the request's (0000,1001) *Affected SOP
            Instance UID* element.
        msg_id : int, optional
            The DIMSE *Message ID*, must be between 0 and 65535, inclusive,
            (default 1).

        Returns
        -------
        status : pydicom.dataset.Dataset
            If the peer timed out, aborted or sent an invalid response then
            returns an empty ``Dataset``. If a response was received from the
            peer then returns a ``Dataset`` containing at least a (0000,0900)
            *Status* element, and depending on the returned value, may
            optionally contain additional elements (see the DICOM Standard,
            Part 7, Section 9.1.2.1.5 and Annex C).

            General N-EVENT-REPORT (DICOM Standard Part 7, Section 10.1.1
            and Annex C)

            Success
              | ``0x0000`` Successful operation

            Failure
              | ``0x0110`` Processing failure
              | ``0x0112`` No such SOP Instance
              | ``0x0113`` No such event type
              | ``0x0114`` No such argument
              | ``0x0115`` Invalid argument value
              | ``0x0117`` Invalid object instance
              | ``0x0118`` No such SOP Class
              | ``0x0119`` Class-Instance conflict
              | ``0x0210`` Duplicate invocation
              | ``0x0211`` Unrecognised operation
              | ``0x0212`` Mistyped argument
              | ``0x0213`` Resource limitation

        event_reply : pydicom.dataset.Dataset or None
            If the status is 'Success' then a ``Dataset`` containing the
            optional reply to the event report.

        See Also
        --------
        ae.ApplicationEntity.on_n_event_report
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
        transfer_syntax = None
        context = self._get_valid_context(class_uid, '', 'scu')

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

        # Encode the `dataset` using the agreed transfer syntax
        #   Will return None if failed to encode
        transfer_syntax = context.transfer_syntax[0]
        bytestream = encode(dataset,
                            transfer_syntax.is_implicit_VR,
                            transfer_syntax.is_little_endian)

        if bytestream is not None:
            req.EventInformation = BytesIO(bytestream)
        else:
            LOGGER.error("Failed to encode the supplied dataset")
            raise ValueError('Failed to encode the supplied dataset')

        # Send N-EVENT-REPORT request to the peer via DIMSE and wait for
        # the response primitive
        self.dimse.send_msg(req, context.context_id)
        cx_id, rsp = self.dimse.get_msg(block=True)

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

            # Attempt to decode the response's dataset
            # pylint: disable=broad-except
            try:
                event_reply = decode(rsp.EventReply,
                                     transfer_syntax.is_implicit_VR,
                                     transfer_syntax.is_little_endian)
            except Exception as ex:
                LOGGER.error("Failed to decode the received dataset")
                LOGGER.exception(ex)
                # Failure: Processing failure
                status.Status = 0x0110

        return status, event_reply

    def send_n_get(self, identifier_list, class_uid, instance_uid, msg_id=1):
        """Send an N-GET request message to the peer AE.

        Parameters
        ----------
        identifier_list : list of pydicom.tag.Tag
            A list of DICOM Data Element tags to be sent in the request's
            (0000,1005) *Attribute Identifier List* element. Should either be
            a list of pydicom Tag objects or a list of values that is
            acceptable for creating pydicom Tag objects.
        class_uid : pydicom.uid.UID
            The UID to be sent in the request's (0000,0003) *Requested SOP
            Class UID* element.
        instance_uid : pydicom.uid.UID
            The UID to be sent in the request's (0000,1001) *Requested SOP
            Instance UID* element.
        msg_id : int, optional
            The DIMSE *Message ID*, must be between 0 and 65535, inclusive,
            (default 1).

        Returns
        -------
        status : pydicom.dataset.Dataset
            If the peer timed out, aborted or sent an invalid response then
            returns an empty ``Dataset``. If a response was received from the
            peer then returns a ``Dataset`` containing at least a (0000,0900)
            *Status* element, and depending on the returned value, may
            optionally contain additional elements (see the DICOM Standard,
            Part 7, Section 9.1.2.1.5 and Annex C).

            General N-GET (DICOM Standard Part 7, Section 10.1.2 and Annex C)

            Success
              | ``0x0000`` Successful operation

            Warning
              | ``0x0107`` Attribute list error

            Failure
              | ``0x0110`` Processing failure
              | ``0x0112`` No such SOP Instance
              | ``0x0117`` Invalid object instance
              | ``0x0118`` No such SOP Class
              | ``0x0119`` Class-Instance conflict
              | ``0x0122`` SOP class not supported
              | ``0x0124`` Not authorised
              | ``0x0210`` Duplicate invocation
              | ``0x0211`` Unrecognised operation
              | ``0x0212`` Mistyped argument
              | ``0x0213`` Resource limitation

        attribute_list : pydicom.dataset.Dataset or None
            If the status is 'Success' then a ``Dataset`` containing attributes
            corresponding to those supplied in the *Attribute Identifier List*,
            otherwise returns None.

        See Also
        --------
        ae.ApplicationEntity.on_n_get
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
        context = self._get_valid_context(class_uid, '', 'scu')
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
        self.dimse.send_msg(req, context.context_id)
        cx_id, rsp = self.dimse.get_msg(block=True)

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

            # Attempt to decode the response's dataset
            # pylint: disable=broad-except
            try:
                attribute_list = decode(rsp.AttributeList,
                                        transfer_syntax.is_implicit_VR,
                                        transfer_syntax.is_little_endian)
            except Exception as ex:
                LOGGER.error("Failed to decode the received dataset")
                LOGGER.exception(ex)
                # Failure: Processing failure
                status.Status = 0x0110

        return status, attribute_list

    def send_n_set(self, dataset, class_uid, instance_uid, msg_id=1):
        """Send an N-SET request message to the peer AE.

        Parameters
        ----------
        dataset : pydicom.dataset.Dataset
            The dataset that will be sent as the *Modification List* parameter
            in the N-SET request.
        class_uid : pydicom.uid.UID
            The UID to be sent in the request's (0000,0003) *Requested SOP
            Class UID* element.
        instance_uid : pydicom.uid.UID
            The UID to be sent in the request's (0000,1001) *Requested SOP
            Instance UID* element.
        msg_id : int, optional
            The DIMSE *Message ID*, must be between 0 and 65535, inclusive,
            (default 1).

        Returns
        -------
        status : pydicom.dataset.Dataset
            If the peer timed out, aborted or sent an invalid response then
            returns an empty ``Dataset``. If a response was received from the
            peer then returns a ``Dataset`` containing at least a (0000,0900)
            *Status* element, and depending on the returned value, may
            optionally contain additional elements (see the DICOM Standard,
            Part 7, Section 9.1.2.1.5 and Annex C).

            General N-SET (DICOM Standard Part 7, Section 10.1.3 and Annex C)

            Success
              | ``0x0000`` Successful operation

            Warning
              | ``0x0107`` Attribute list error
              | ``0x0116`` Attribute value out of range

            Failure
              | ``0x0105`` No such attribute
              | ``0x0106`` Invalid attribute value
              | ``0x0110`` Processing failure
              | ``0x0112`` No such SOP Instance
              | ``0x0117`` Invalid object instance
              | ``0x0118`` No such SOP Class
              | ``0x0119`` Class-Instance conflict
              | ``0x0121`` Missing attribute value
              | ``0x0122`` SOP class not supported
              | ``0x0124`` Not authorised
              | ``0x0210`` Duplicate invocation
              | ``0x0211`` Unrecognised operation
              | ``0x0212`` Mistyped argument
              | ``0x0213`` Resource limitation

        attribute_list : pydicom.dataset.Dataset or None
            If the status is 'Success' then a ``Dataset`` containing attributes
            corresponding to those supplied in the *Attribute List*,
            otherwise returns None.

        See Also
        --------
        ae.ApplicationEntity.on_n_set
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
        context = self._get_valid_context(class_uid, '', 'scu')
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
            LOGGER.error("Failed to encode the supplied Dataset")
            raise ValueError('Failed to encode the supplied Dataset')

        # Send N-SET request to the peer via DIMSE and wait for the response
        self.dimse.send_msg(req, context.context_id)
        cx_id, rsp = self.dimse.get_msg(block=True)

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

            # Attempt to decode the response's dataset
            # pylint: disable=broad-except
            try:
                attribute_list = decode(rsp.AttributeList,
                                        transfer_syntax.is_implicit_VR,
                                        transfer_syntax.is_little_endian)
            except Exception as ex:
                LOGGER.error("Failed to decode the received dataset")
                LOGGER.exception(ex)
                # Failure: Processing failure
                status.Status = 0x0110

        return status, attribute_list

    # Association logging/debugging functions
    @staticmethod
    def debug_association_aborted(primitive=None):
        """Debugging information when an A-ABORT request received.

        Parameters
        ----------
        assoc_primitive : pynetdicom.pdu_primitives.A_ABORT
            The A-ABORT (RQ) primitive received from the DICOM Upper Layer
        """
        LOGGER.error('Association Aborted')

    @staticmethod
    def debug_association_accepted(primitive):
        """Debugging information when an A-ASSOCIATE accept is received.

        Parameters
        ----------
        primitive : pynetdicom.pdu_primitives.A_ASSOCIATE
            The A-ASSOCIATE (AC) PDU received from the DICOM Upper Layer
        """
        pass

    @staticmethod
    def debug_association_rejected(primitive):
        """Debugging information when an A-ASSOCIATE rejection received.

        Parameters
        ----------
        assoc_primitive : pynetdicom.pdu_primitives.A_ASSOCIATE
            The A-ASSOCIATE (RJ) primitive received from the DICOM Upper Layer
        """
        # See PS3.8 Section 7.1.1.9 but mainly Section 9.3.4 and Table 9-21
        #   for information on the result and diagnostic information
        source = primitive.result_source
        result = primitive.result
        reason = primitive.diagnostic

        source_str = {1 : 'Service User',
                      2 : 'Service Provider (ACSE)',
                      3 : 'Service Provider (Presentation)'}

        reason_str = [{1 : 'No reason given',
                       2 : 'Application context name not supported',
                       3 : 'Calling AE title not recognised',
                       4 : 'Reserved',
                       5 : 'Reserved',
                       6 : 'Reserved',
                       7 : 'Called AE title not recognised',
                       8 : 'Reserved',
                       9 : 'Reserved',
                       10 : 'Reserved'},
                      {1 : 'No reason given',
                       2 : 'Protocol version not supported'},
                      {0 : 'Reserved',
                       1 : 'Temporary congestion',
                       2 : 'Local limit exceeded',
                       3 : 'Reserved',
                       4 : 'Reserved',
                       5 : 'Reserved',
                       6 : 'Reserved',
                       7 : 'Reserved'}]

        result_str = {1 : 'Rejected Permanent',
                      2 : 'Rejected Transient'}

        LOGGER.error('Association Rejected:')
        LOGGER.error('Result: %s, Source: %s', result_str[result],
                     source_str[source])
        LOGGER.error('Reason: %s', reason_str[source - 1][reason])

    @staticmethod
    def debug_association_released(primitive=None):
        """Debugging information when an A-RELEASE request received.

        Parameters
        ----------
        assoc_primitive : pynetdicom.pdu_primitives.A_RELEASE
            The A-RELEASE (RQ) primitive received from the DICOM Upper Layer
        """
        LOGGER.info('Association Released')

    @staticmethod
    def debug_association_requested(primitive):
        """Debugging information when an A-ASSOCIATE request received.

        Parameters
        ----------
        primitive : pynetdicom.pdu_primitives.A_ASSOCIATE
            The A-ASSOCIATE (RQ) PDU received from the DICOM Upper Layer
        """
        pass


class ServiceUser(object):
    """Convenience class for the Association Service User.

    An Association object has two ServiceUser attributes, one representing the
    association requestor and the other the association acceptor. Once both
    ServiceUser's have been defined sufficiently to be considered valid then
    association negotiation can begin. The requestor ServiceUser requires
    (at a minimum) the following in order to be valid:

    * For association as requestor:

        * AE title (ae_title)
        * Address and port number (address and port)
        * Maximum PDU length (maximum_length)
        * Implementation class UID (implementation_class_uid)
        * At least one presentation context (requested_contexts)
    * For association as acceptor:

        * AE title
        * Address and port number

    The acceptor ServiceUser requires (at a minimum) the following in order
    to be valid:

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
