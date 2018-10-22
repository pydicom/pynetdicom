"""
Defines the Association class which handles associating with peers.
"""
from io import BytesIO
import logging
import socket
import threading
import time

from pydicom.dataset import Dataset
from pydicom.uid import UID

# pylint: disable=no-name-in-module
from pynetdicom3.acse import ACSEServiceProvider
from pynetdicom3.dimse import DIMSEServiceProvider
from pynetdicom3.dimse_primitives import (
    C_ECHO, C_MOVE, C_STORE, C_GET, C_FIND, C_CANCEL,
    N_GET
)
from pynetdicom3.dsutils import decode, encode
from pynetdicom3.dul import DULServiceProvider
from pynetdicom3.sop_class import (
    uid_to_sop_class,
    uid_to_service_class,
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
from pynetdicom3.pdu_primitives import (UserIdentityNegotiation,
                                        SOPClassExtendedNegotiation,
                                        SOPClassCommonExtendedNegotiation,
                                        A_ASSOCIATE, A_ABORT, A_P_ABORT)
from pynetdicom3.status import (code_to_status, code_to_category,
                                STORAGE_SERVICE_CLASS_STATUS)
from pynetdicom3.utils import PresentationContextManager
# pylint: enable=no-name-in-module

LOGGER = logging.getLogger('pynetdicom3.assoc')


class Association(threading.Thread):
    """Manage an Association with a peer AE.

    Attributes
    ----------
    acse : acse.ACSEServiceProvider
        The Association Control Service Element provider.
    ae : ae.ApplicationEntity
        The local AE.
    dimse : dimse.DIMSEServiceProvider
        The DICOM Message Service Element provider.
    dul : dul.DULServiceProvider
        The DICOM Upper Layer service provider instance.
    is_aborted : bool
        True if the association has been aborted, False otherwise.
    is_established : bool
        True if the association has been established, False otherwise.
    is_rejected : bool
        True if the association was rejected, False otherwise.
    is_released : bool
        True if the association has been released, False otherwise.
    local_ae : dict
        The local Application Entity details, keys: 'port', 'address',
        'ae_title', 'pdv_size'.
    mode : str
        Whether the local AE is acting as the Association 'Requestor' or
        'Acceptor' (i.e. SCU or SCP).
    peer_ae : dict
        The peer Application Entity details, keys: 'port', 'address',
        'ae_title', 'pdv_size'.
    client_socket : socket.socket
        The socket to use for connections with the peer AE.
    requested_contexts : list of presentation.PresentationContext
        A list of the requested Presentation Contexts sent or received during
        association negotiation.
    supported_contexts : list of presentation.PresentationContext
        A list of the supported Presentation Contexts sent or received during
        association negotiation.
    """
    def __init__(self, local_ae, client_socket=None, peer_ae=None,
                 acse_timeout=60, dimse_timeout=None, max_pdu=16382,
                 ext_neg=None):
        """Create a new Association.

        Parameters
        ----------
        local_ae : ae.ApplicationEntity
            The local AE instance.
        client_socket : socket.socket or None, optional
            If the local AE is acting as an SCP, this is the listen socket for
            incoming connection requests. A value of None is used when acting
            as an SCU.
        peer_ae : dict, optional
            If the local AE is acting as an SCU this is the AE title, host and
            port of the peer AE that we want to Associate with. Keys: 'port',
            'address', 'ae_title'.
        acse_timeout : int, optional
            The maximum amount of time to wait for a reply during association,
            in seconds. A value of 0 means no timeout (default: 30).
        dimse_timeout : int, optional
            The maximum amount of time to wait for a reply during DIMSE, in
            seconds. A value of 0 means no timeout (default: 0).
        max_pdu : int, optional
            The maximum PDU receive size in bytes for the association. A value
            of 0 means no maximum size (default: 16382 bytes).
        ext_neg : list of pdu_primitives User Information items, optional
            If the association requires an extended negotiation then `ext_neg`
            is a list containing the negotiation objects (default: None).
        """
        self.peer_ae = {'port' : None,
                        'address' : None,
                        'ae_title' : None,
                        'pdv_size' : None}

        if [client_socket, peer_ae] == [None, None]:
            raise TypeError("Association must be initialised with either "
                            "the client_socket or peer_ae parameters")

        if client_socket and peer_ae:
            raise TypeError("Association must be initialised with either "
                            "client_socket or peer_ae parameter not both")

        # Received a connection from a peer AE
        if isinstance(client_socket, socket.socket):
            self._mode = 'Acceptor'
        elif client_socket is not None:
            raise TypeError("client_socket must be a socket.socket")

        # Initiated a connection to a peer AE
        if isinstance(peer_ae, dict):
            self._mode = 'Requestor'
            for key in ['ae_title', 'port', 'address']:
                if key not in peer_ae:
                    raise KeyError("peer_ae must contain 'ae_title', 'port' "
                                   "and 'address' entries")

            self.peer_ae.update(peer_ae)
        elif peer_ae is not None:
            raise TypeError("peer_ae must be a dict")

        # The socket.socket used for connections
        self.client_socket = client_socket

        # The parent AE object
        from pynetdicom3 import AE # Imported here to avoid circular import
        if isinstance(local_ae, AE):
            self.ae = local_ae
        else:
            raise TypeError("local_ae must be a pynetdicom3.AE")

        self.local_ae = {'port' : None,
                         'address' : None,
                         'ae_title' : local_ae.ae_title,
                         'pdv_size' : None}

        # Why do we instantiate the DUL provider with a socket when acting
        #   as an SCU?
        # Q. Why do we need to feed the DUL an ACSE timeout?
        # A. ARTIM timer
        self.dul = DULServiceProvider(socket=client_socket,
                                      dul_timeout=self.ae.network_timeout,
                                      assoc=self)

        self.requested_contexts = []
        self.supported_contexts = []

        # Status attributes
        self.is_established = False
        self.is_rejected = False
        self.is_aborted = False
        self.is_released = False

        # Timeouts for the DIMSE and ACSE service providers
        if dimse_timeout is None:
            self.dimse_timeout = None
        elif isinstance(dimse_timeout, (int, float)):
            self.dimse_timeout = dimse_timeout
        else:
            raise TypeError("dimse_timeout must be numeric or None")

        if acse_timeout is None:
            self.acse_timeout = None
        elif isinstance(acse_timeout, (int, float)):
            self.acse_timeout = acse_timeout
        else:
            raise TypeError("acse_timeout must be numeric or None")

        # Maximum PDU sizes (in bytes) for the local and peer AE
        if isinstance(max_pdu, int):
            self.local_ae['pdv_size'] = max_pdu
            self.local_max_pdu = max_pdu
        else:
            raise TypeError("max_pdu must be an int")
        self.peer_max_pdu = None

        # A list of extended negotiation objects
        ext_neg = ext_neg or []
        if isinstance(ext_neg, list):
            self.ext_neg = ext_neg
        else:
            raise TypeError("ext_neg must be a list of Extended "
                            "Negotiation items or None")

        # Set new ACSE and DIMSE providers
        self.acse = ACSEServiceProvider(self, self.acse_timeout)
        # FIXME: DIMSE max pdu should be the peer max
        self.dimse = DIMSEServiceProvider(self.dul, self.dimse_timeout,
                                          self.local_max_pdu)

        # Kills the thread loop in run()
        self._kill = False
        self._is_running = False

        # Send an A-ABORT when an association request is received
        self._a_abort_assoc_rq = False
        # Send an A-P-ABORT when an association request is received
        self._a_p_abort_assoc_rq = False
        # Disconnect from the peer when an association request is received
        self._disconnect_assoc_rq = False

        # Point the public send_c_cancel_* functions to the actual function
        self.send_c_cancel_find = self._send_c_cancel
        self.send_c_cancel_move = self._send_c_cancel
        self.send_c_cancel_get = self._send_c_cancel

        # Thread setup
        threading.Thread.__init__(self)
        self.daemon = True

    def kill(self):
        """Kill the main association thread loop."""
        self._kill = True
        self.is_established = False
        while not self.dul.stop_dul():
            time.sleep(0.001)

        self.ae.cleanup_associations()

    def release(self):
        """Release the association."""
        if self.is_established:
            if self.acse.release_assoc():
                # Got release reply within timeout window
                self.kill()
                self.is_released = True
            else:
                # No release reply within timeout window
                self.abort()

    def abort(self):
        """Abort the association.

        DUL service user association abort. Always gives the source as the
        DUL service user and sets the abort reason to 0x00 (not significant)

        See PS3.8, 7.3-4 and 9.3.8.
        """
        if not self.is_released:
            self.acse.abort_assoc(source=0x00, reason=0x00)
            self.kill()
            self.is_aborted = True

        # Add short delay to ensure everything shuts down
        time.sleep(0.1)

    def run(self):
        """The main Association control."""
        self.dul.start()

        # When the AE is acting as an SCP (Association Acceptor)
        if self._mode == 'Acceptor':
            self._run_as_acceptor()
        # If the local AE initiated the Association
        elif self._mode == 'Requestor':
            self._run_as_requestor()

    def _run_as_acceptor(self):
        """Run as an Association Acceptor."""
        # FIXME: needed because of some thread-related problem
        time.sleep(0.1)

        # Got an A-ASSOCIATE request primitive from the DICOM UL
        assoc_rq = self.dul.receive_pdu(wait=True,
                                        timeout=self.acse.acse_timeout)

        if assoc_rq is None:
            self.kill()
            return

        # (Optionally) send an A-ABORT/A-P-ABORT in response
        if self._a_abort_assoc_rq:
            self.acse.abort_assoc(0x00, 0x00)
            self.kill()
            return
        elif self._a_p_abort_assoc_rq:
            self.acse.abort_assoc(0x02, 0x00)
            self.kill()
            return

        # If the remote AE initiated the Association then reject it if:
        # Rejection reasons:
        #   a) DUL user
        #       0x02 unsupported application context name
        #   b) DUL ACSE related
        #       0x01 no reason given
        #       0x02 protocol version not supported
        #   c) DUL Presentation related
        #       0x01 temporary congestion

        ## DUL User Related Rejections
        #
        # [result, source, diagnostic]
        reject_assoc_rsd = []

        # Calling AE Title not recognised
        if (self.ae.require_calling_aet != b''
            and self.ae.require_calling_aet != assoc_rq.calling_ae_title):
                reject_assoc_rsd = [(0x01, 0x01, 0x03)]

        # Called AE Title not recognised
        if (self.ae.require_called_aet != b''
            and self.ae.require_called_aet != assoc_rq.called_ae_title):
                reject_assoc_rsd = [(0x01, 0x01, 0x07)]

        ## DUL ACSE Related Rejections
        #
        # User Identity Negotiation (PS3.7 Annex D.3.3.7)
        for ii in assoc_rq.user_information:
            if isinstance(ii, UserIdentityNegotiation):
                # Used to notify the association acceptor of the user
                #   identity of the association requestor. It may also
                #   request that the Acceptor response with the server
                #   identity.
                #
                # The Acceptor does not provide an A-ASSOCIATE response
                #   unless a positive response is requested and user
                #   authentication succeeded. If a positive response
                #   was requested, the A-ASSOCIATE response shall contain
                #   a User Identity sub-item. If a Kerberos ticket is used
                #   the response shall include a Kerberos server ticket
                #
                # A positive response must be requested if the association
                #   requestor requires confirmation. If the Acceptor does
                #   not support user identification it will accept the
                #   association without making a positive response. The
                #   Requestor can then decide whether to proceed

                #user_authorised = self.ae.on_user_identity(
                #                       ii.UserIdentityType,
                #                       ii.PrimaryField,
                #                       ii.SecondaryField)

                # Associate with all requestors
                assoc_rq.user_information.remove(ii)

                # Testing
                #if ii.PositiveResponseRequested:
                #    ii.ServerResponse = b''

        # Extended Negotiation
        for ii in assoc_rq.user_information:
            if isinstance(ii, SOPClassExtendedNegotiation):
                assoc_rq.user_information.remove(ii)

        ## DUL Presentation Related Rejections
        #
        # Maximum number of associations reached (local-limit-exceeded)
        if len(self.ae.active_associations) > self.ae.maximum_associations:
            reject_assoc_rsd = [(0x02, 0x03, 0x02)]

        for (result, src, diag) in reject_assoc_rsd:
            assoc_rj = self.acse.reject_assoc(assoc_rq, result, src, diag)
            self.debug_association_rejected(assoc_rj)
            self.ae.on_association_rejected(assoc_rj)
            self.kill()
            return

        ## Presentation Contexts
        self.acse.context_manager = PresentationContextManager()
        self.acse.context_manager.requestor_contexts = \
                            assoc_rq.presentation_context_definition_list
        self.acse.context_manager.acceptor_contexts = self.ae.supported_contexts

        self.acse.accepted_contexts = self.acse.context_manager.accepted
        self.acse.rejected_contexts = self.acse.context_manager.rejected

        # Save the peer AE details
        self.peer_ae['ae_title'] = assoc_rq.calling_ae_title
        self.peer_ae['called_aet'] = assoc_rq.called_ae_title
        self.peer_ae['pdv_size'] = assoc_rq.maximum_length_received
        peer_info = self.client_socket.getpeername()
        self.peer_ae['address'] = peer_info[0]
        self.peer_ae['port'] = peer_info[1]
        local_info = self.client_socket.getsockname()
        self.local_ae['address'] = local_info[0]
        self.local_ae['port'] = local_info[1]

        # Set maximum PDU send length
        self.peer_max_pdu = assoc_rq.maximum_length_received # TODO: Remove?
        self.dimse.maximum_pdu_size = assoc_rq.maximum_length_received

        # Set Responding AE title
        assoc_rq.called_ae_title = self.ae.ae_title

        # Set maximum PDU receive length
        assoc_rq.maximum_length_received = self.local_max_pdu # TODO: Rename?
        #for user_item in assoc_rq.user_information:
        #    if isinstance(user_item, MaximumLengthNegotiation):
        #        user_item.maximum_length_received = self.local_max_pdu

        # Issue the A-ASSOCIATE indication (accept) primitive using the ACSE
        # FIXME: Is this correct? Do we send Accept then Abort if no
        #   presentation contexts?
        assoc_ac = self.acse.accept_assoc(assoc_rq)

        if assoc_ac is None:
            #self.abort()
            self.kill()
            return

        # Callbacks/Logging
        self.debug_association_accepted(assoc_ac)
        self.ae.on_association_accepted(assoc_ac)

        # No valid presentation contexts, abort the association
        if self.acse.accepted_contexts == []:
            self.acse.abort_assoc(0x02, 0x00)
            self.kill()
            return

        # Assocation established OK
        self.is_established = True

        # Start the SCP loop
        self._run_as_acceptor_loop()

    def _run_as_acceptor_loop(self):
        """Run the Association Acceptor reactor loop.

        Main SCP run loop
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
            'requestor' : {
                'ae_title' : self.peer_ae['ae_title'],
                'called_aet' : self.peer_ae['called_aet'],
                'port' : self.peer_ae['port'],
                'address' : self.peer_ae['address'],
            },
            'acceptor' : {
                'ae_title' : self.local_ae['ae_title'],
                'address' : self.local_ae['address'],
                'port' : self.local_ae['port'],
            }
        }

        self._is_running = True
        while not self._kill:
            time.sleep(0.001)

            # Check with the DIMSE provider for incoming messages
            #   all messages should be a DIMSEMessage subclass
            msg, msg_context_id = self.dimse.receive_msg(wait=False)

            # DIMSE message received
            if msg:
                # Use the Message's Affected SOP Class UID to create a new
                #   SOP Class instance, if there's no AffectedSOPClassUID
                #   then we received a C-CANCEL request
                # FIXME
                if not hasattr(msg, 'AffectedSOPClassUID'):
                    self.abort()
                    return

                service_class = uid_to_service_class(msg.AffectedSOPClassUID)()

                # Check that the SOP Class is supported by the AE
                # New method
                #pc_accepted = self.acse.accepted_contexts
                #context = [
                #    pc for pc in pc_accepted if pc.context_id == msg_context_id
                #]

                # Matching context
                #if context:
                #    service_class.presentation_context = context[0]
                #else:
                #    # No matching presentation context
                #    pass

                # Old method
                # TODO: Index contexts in a dict using context ID
                for context in self.acse.accepted_contexts:
                    if context.context_id == msg_context_id:
                        service_class.maxpdulength = self.peer_max_pdu
                        service_class.DIMSE = self.dimse
                        service_class.ACSE = self.acse
                        service_class.AE = self.ae

                        # Run SOPClass in SCP mode
                        service_class.SCP(msg, context, info)
                        break
                else:
                    LOGGER.info("Received message with invalid or rejected "
                                "context ID %d", msg_context_id)
                    LOGGER.debug("%s", msg)

            # Check for release request
            if self.acse.CheckRelease():
                # Callback trigger
                self.debug_association_released()
                self.ae.on_association_released()
                self.kill()

            # Check for abort
            if self.acse.CheckAbort():
                # Callback trigger
                self.debug_association_aborted()
                self.ae.on_association_aborted(None)
                self.kill()

            # Check if the DULServiceProvider thread is still running
            #   DUL.is_alive() is inherited from threading.thread
            if not self.dul.is_alive():
                self.kill()

            # Check if idle timer has expired
            if self.dul.idle_timer_expired():
                self.abort()

    def _run_as_requestor(self):
        """Run as the Association Requestor."""
        if not self.requested_contexts:
            LOGGER.error("No requested Presentation Contexts specified")
            self.kill()
            return

        # Build role extended negotiation - FIXME - needs updating
        #   in particular, when running a C-GET user the role selection
        #   needs to be set prior to association
        #
        # SCP/SCU Role Negotiation (optional)
        #self.ext_neg = []
        #for context in self.AE.presentation_contexts_scu:
        #    tmp = SCP_SCU_RoleSelectionParameters()
        #    tmp.SOPClassUID = context.abstract_syntax
        #    tmp.SCURole = 0
        #    tmp.SCPRole = 1
        #
        #    self.ext_neg.append(tmp)

        local_ae = {'address' : self.ae.address,
                    'port' : self.ae.port,
                    'ae_title' : self.ae.ae_title}

        # Request an Association via the ACSE
        is_accepted, assoc_rsp = self.acse.request_assoc(
            local_ae,
            self.peer_ae,
            self.local_ae['pdv_size'],
            self.requested_contexts,
            userspdu=self.ext_neg
        )

        # Association was accepted or rejected
        if isinstance(assoc_rsp, A_ASSOCIATE):
            # Association was accepted
            if is_accepted:
                self.debug_association_accepted(assoc_rsp)
                self.ae.on_association_accepted(assoc_rsp)

                # No acceptable presentation contexts
                if self.acse.accepted_contexts == []:
                    LOGGER.error("No Acceptable Presentation Contexts")
                    self.is_aborted = True
                    self.is_established = False
                    self.acse.abort_assoc(0x02, 0x00)
                    self.kill()

                    return

                # Build supported SOP Classes for the Association
                self.scu_supported_sop = []
                for context in self.acse.accepted_contexts:
                    self.scu_supported_sop.append(
                        (context.context_id,
                         uid_to_sop_class(context.abstract_syntax),
                         context.transfer_syntax[0]))

                # Assocation established OK
                self.is_established = True

                # This seems like it should be event driven rather than
                #   driven by a loop
                #
                # Listen for further messages from the peer
                while not self._kill:
                    time.sleep(0.1)

                    # Check for release request
                    if self.acse.CheckRelease():
                        self.is_released = True
                        self.is_established = False
                        # Callback trigger
                        self.ae.on_association_released()
                        self.debug_association_released()
                        self.kill()
                        return

                    # Check for abort
                    if self.acse.CheckAbort():
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
                        self.kill()
                        return

            # Association was rejected
            else:
                self.ae.on_association_rejected(assoc_rsp)
                self.debug_association_rejected(assoc_rsp)
                self.is_rejected = True
                self.is_established = False
                self.dul.kill_dul()
                return

        # Association was aborted by peer
        elif isinstance(assoc_rsp, A_ABORT):
            self.ae.on_association_aborted(assoc_rsp)
            self.debug_association_aborted(assoc_rsp)
            self.is_established = False
            self.is_aborted = True
            self.dul.kill_dul()
            return

        # Association was aborted by DUL provider
        elif isinstance(assoc_rsp, A_P_ABORT):
            self.is_aborted = True
            self.is_established = False
            self.dul.kill_dul()
            return

        # Association failed for any other reason (No peer, etc)
        else:
            self.is_established = False
            self.dul.kill_dul()
            return


    # DIMSE-C services provided by the Association
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
            If the peer timed out or sent an invalid response then returns an
            empty ``Dataset``. If a valid response was received from the peer
            then returns a ``Dataset`` containing at least a (0000,0900)
            *Status* element, and, depending on the returned Status value, may
            optionally contain additional elements (see DICOM Standard Part 7,
            Annex C).

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

        Examples
        --------
        >>> assoc = ae.associate(addr, port)
        >>> if assoc.is_established:
        ...     status = assoc.send_c_echo()
        ...     if status:
        ...         print('C-ECHO Response: 0x{0:04x}'.format(status.Status))
        ...     assoc.release()

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
          `9.3.5 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.5>`_ and
          `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`__
        """
        # Can't send a C-ECHO without an Association
        if not self.is_established:
            raise RuntimeError("The association with a peer SCP must be "
                               "established before sending a C-ECHO request")

        # Verification SOP Class
        uid = UID('1.2.840.10008.1.1')

        # Get the Presentation Context we are operating under
        context_id = None
        for context in self.acse.context_manager.accepted:
            if uid == context.abstract_syntax:
                context_id = context.context_id
                break

        if context_id is None:
            LOGGER.error("No accepted Presentation Context for '%s'", uid)
            raise ValueError("No accepted Presentation Context for "
                             "'Verification SOP Class'.")

        # Build C-STORE request primitive
        #   (M) Message ID
        #   (M) Affected SOP Class UID
        primitive = C_ECHO()
        primitive.MessageID = msg_id
        primitive.AffectedSOPClassUID = uid

        # Send C-ECHO request to the peer via DIMSE and wait for the response
        self.dimse.send_msg(primitive, context_id)
        rsp, _ = self.dimse.receive_msg(wait=True)

        # Determine validity of the response and get the status
        status = Dataset()
        if rsp is None:
            LOGGER.error('DIMSE service timed out')
            self.abort()
        elif rsp.is_valid_response:
            status.Status = rsp.Status
            if getattr(rsp, 'ErrorComment') is not None:
                status.ErrorComment = rsp.ErrorComment
        else:
            LOGGER.error('Received an invalid C-ECHO response from the peer')
            self.abort()

        return status

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
            If the peer timed out or sent an invalid response then returns an
            empty ``Dataset``. If a valid response was received from the peer
            then returns a ``Dataset`` containing at least a (0000,0900)
            *Status* element, and, depending on the returned value, may
            optionally contain additional elements (see DICOM Standard Part 7,
            Annex C).

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
            If `dataset` is missing (0008,0016) *SOP Class UID* or
            (0008,0018) *SOP Instance UID* elements.
        ValueError
            If no accepted Presentation Context for `dataset` exists or if
            unable to encode the `dataset`.

        Examples
        --------

        >>> ds = pydicom.dcmread('file-in.dcm')
        >>> assoc = ae.associate(addr, port)
        >>> if assoc.is_established:
        ...     status = assoc.send_c_store(ds)
        ...     if status:
        ...         print('C-STORE Response: 0x{0:04x}'.format(status.Status))
        ...     assoc.release()

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
          `9.3.1 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.1>`_ and
          `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`__
        """
        # Can't send a C-STORE without an Association
        if not self.is_established:
            raise RuntimeError("The association with a peer SCP must be "
                               "established before sending a C-STORE request")

        # Determine the Presentation Context we are operating under
        #   and hence the transfer syntax to use for encoding `dataset`
        transfer_syntax = None
        for context in self.acse.context_manager.accepted:
            try:
                if dataset.SOPClassUID == context.abstract_syntax:
                    transfer_syntax = context.transfer_syntax[0]
                    context_id = context.context_id
                    break
            except AttributeError as ex:
                LOGGER.error("Association.send_c_store - unable to determine "
                             "Presentation Context as "
                             "Dataset has no 'SOP Class UID' element")
                LOGGER.error("Store SCU failed due to there being no valid "
                             "presentation context for the current dataset")
                raise ex

        if transfer_syntax is None:
            LOGGER.error("Association.send_c_store - no accepted Presentation "
                         " Context for: '%s'", dataset.SOPClassUID)
            LOGGER.error("Store SCU failed due to there being no accepted "
                         "presentation context for the current dataset")
            raise ValueError("No accepted Presentation Context for 'dataset'.")

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
        self.dimse.send_msg(req, context_id)
        rsp, _ = self.dimse.receive_msg(wait=True)

        # Determine validity of the response and get the status
        status = Dataset()
        if rsp is None:
            LOGGER.error('DIMSE service timed out')
            self.abort()
        elif rsp.is_valid_response:
            status.Status = rsp.Status
            for keyword in ['ErrorComment', 'OffendingElement']:
                if getattr(rsp, keyword) is not None:
                    setattr(status, keyword, getattr(rsp, keyword))
        else:
            LOGGER.error('Received an invalid C-STORE response from the peer')
            self.abort()

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
            If the peer timed out or sent an invalid response then yields an
            empty ``Dataset``. If a response was received from the peer then
            yields a ``Dataset`` containing at least a (0000,0900) *Status*
            element, and depending on the returned value, may optionally
            contain additional elements (see the DICOM Standard, Part 7,
            Section 9.1.2.1.5 and Annex C).

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
              | ``0xFF00`` Matches are continuing: current match is supplied and
                any Optional Keys were supported in the same manner as Required
                Keys
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
              | ``0xFF00`` Matches are continuing: current match is supplied and
                any Optional Keys were supported in the same manner as Required
                Keys

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

        Examples
        --------

        >>> ds = Dataset()
        >>> ds.QueryRetrieveLevel = 'PATIENT'
        >>> ds.PatientName = '*'
        >>> assoc = ae.associate(addr, port)
        >>> if assoc.is_established:
        ...     response = assoc.send_c_find(ds, query_model='P')
        ...     for (status, identifier) in response:
        ...         print('C-FIND Response: 0x{0:04x}'.format(status.Status))
        ...     assoc.release()

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
          Annexes `C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_ and
          `K <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_K>`_
        """
        # Can't send a C-FIND without an Association
        if not self.is_established:
            raise RuntimeError("The association with a peer SCP must be "
                               "established before sending a C-FIND request")

        if query_model == 'W':
            sop_class = ModalityWorklistInformationFind
        elif query_model == "P":
            sop_class = PatientRootQueryRetrieveInformationModelFind
        elif query_model == "S":
            sop_class = StudyRootQueryRetrieveInformationModelFind
        elif query_model == "O":
            sop_class = PatientStudyOnlyQueryRetrieveInformationModelFind
        elif query_model == "G":
            sop_class = GeneralRelevantPatientInformationQuery
        elif query_model == "B":
            sop_class = BreastImagingRelevantPatientInformationQuery
        elif query_model == "C":
            sop_class = CardiacRelevantPatientInformationQuery
        elif query_model == "PC":
            sop_class = ProductCharacteristicsQueryInformationModelFind
        elif query_model == "SA":
            sop_class = SubstanceApprovalQueryInformationModelFind
        elif query_model == "H":
            sop_class = HangingProtocolInformationModelFind
        elif query_model == "D":
            sop_class = DefinedProcedureProtocolInformationModelFind
        elif query_model == "CP":
            sop_class = ColorPaletteInformationModelFind
        elif query_model == "IG":
            sop_class = GenericImplantTemplateInformationModelFind
        elif query_model == "IA":
            sop_class = ImplantAssemblyTemplateInformationModelFind
        elif query_model == "IT":
            sop_class = ImplantTemplateGroupInformationModelFind
        else:
            raise ValueError(
                "Unsupported value for `query_model`: {}".format(query_model)
            )

        # Determine the Presentation Context we are operating under
        #   and hence the transfer syntax to use for encoding `dataset`
        transfer_syntax = None
        for context in self.acse.context_manager.accepted:
            if sop_class.uid == context.abstract_syntax:
                transfer_syntax = context.transfer_syntax[0]
                context_id = context.context_id
                break

        if transfer_syntax is None:
            LOGGER.error("No accepted Presentation Context for: '%s'",
                         sop_class.uid)
            LOGGER.error("Find SCU failed due to there being no accepted "
                         "presentation context for the current dataset")
            raise ValueError("No accepted Presentation Context for 'dataset'")

        # Build C-FIND request primitive
        #   (M) Message ID
        #   (M) Affected SOP Class UID
        #   (M) Priority
        #   (M) Identifier
        req = C_FIND()
        req.MessageID = msg_id
        req.AffectedSOPClassUID = sop_class.uid
        req.Priority = priority

        # Encode the Identifier `dataset` using the agreed transfer syntax
        #   Will return None if failed to encode
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
        self.dimse.send_msg(req, context_id)

        # Get the responses from the peer
        ii = 1
        while True:
            # Wait for C-FIND response
            rsp, _ = self.dimse.receive_msg(wait=True)

            # If no response received, start loop again
            if not rsp:
                LOGGER.error("Connection closed or timed-out")
                self.abort()
                return
            elif not rsp.is_valid_response:
                LOGGER.error('Received an invalid C-FIND response from ' \
                             'the peer')
                self.abort()
                return

            # Status may be 'Failure', 'Cancel', 'Success' or 'Pending'
            status = Dataset()
            status.Status = rsp.Status
            for keyword in ['OffendingElement', 'ErrorComment']:
                if getattr(rsp, keyword) is not None:
                    setattr(status, keyword, getattr(rsp, keyword))

            status_category = code_to_category(status.Status)

            LOGGER.debug('-' * 65)
            LOGGER.debug('Find SCP Response: {2} (0x{0:04x} - {1})'
                         .format(status.Status, status_category, ii))

            # We want to exit the wait loop if we receive a Failure, Cancel or
            #   Success status type
            if status_category != 'Pending':
                identifier = None
                break

            # Status must be Pending, so decode the Identifier dataset
            try:
                identifier = decode(rsp.Identifier,
                                    transfer_syntax.is_implicit_VR,
                                    transfer_syntax.is_little_endian)

                LOGGER.debug('')
                LOGGER.debug('# DICOM Dataset')
                for elem in identifier:
                    LOGGER.debug(elem)
                LOGGER.debug('')
            except:
                LOGGER.error("Failed to decode the received Identifier dataset")
                yield status, None

            ii += 1

            yield status, identifier

        yield status, identifier

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
            If the peer timed out or sent an invalid response then yields an
            empty ``Dataset``. If a response was received from the peer then
            yields a ``Dataset`` containing at least a (0000,0900) *Status*
            element, and depending on the returned value, may optionally
            contain additional elements (see DICOM Standard Part 7, Section
            9.1.4 and Annex C).

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
          `9.3.4 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.4>`_ and
          `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`__
        """
        # Can't send a C-MOVE without an Association
        if not self.is_established:
            raise RuntimeError("The association with a peer SCP must be "
                               "established before sending a C-MOVE request")

        if query_model == "P":
            sop_class = PatientRootQueryRetrieveInformationModelMove
        elif query_model == "S":
            sop_class = StudyRootQueryRetrieveInformationModelMove
        elif query_model == "O":
            sop_class = PatientStudyOnlyQueryRetrieveInformationModelMove
        elif query_model == "C":
            sop_class = CompositeInstanceRootRetrieveMove
        elif query_model == "H":
            sop_class = HangingProtocolInformationModelMove
        elif query_model == "D":
            sop_class = DefinedProcedureProtocolInformationModelMove
        elif query_model == "CP":
            sop_class = ColorPaletteInformationModelMove
        elif query_model == "IG":
            sop_class = GenericImplantTemplateInformationModelMove
        elif query_model == "IA":
            sop_class = ImplantAssemblyTemplateInformationModelMove
        elif query_model == "IT":
            sop_class = ImplantTemplateGroupInformationModelMove
        else:
            raise ValueError(
                "Unsupported value for `query_model`: {}".format(query_model)
            )

        # Determine the Presentation Context we are operating under
        #   and hence the transfer syntax to use for encoding `dataset`
        transfer_syntax = None
        for context in self.acse.context_manager.accepted:
            if sop_class.uid == context.abstract_syntax:
                transfer_syntax = context.transfer_syntax[0]
                context_id = context.context_id
                break

        if transfer_syntax is None:
            LOGGER.error("No accepted Presentation Context for: '%s'",
                         sop_class.uid)
            LOGGER.error("Move SCU failed due to there being no accepted "
                         "presentation context\n   for the current dataset")
            raise ValueError("No accepted Presentation Context for 'dataset'")

        # Build C-MOVE request primitive
        #   (M) Message ID
        #   (M) Affected SOP Class UID
        #   (M) Priority
        #   (M) Move Destination
        #   (M) Identifier
        req = C_MOVE()
        req.MessageID = msg_id
        req.AffectedSOPClassUID = sop_class.uid
        req.Priority = priority
        req.MoveDestination = move_aet

        # Encode the Identifier `dataset` using the agreed transfer syntax;
        #   will return None if failed to encode
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
        self.dimse.send_msg(req, context_id)

        # Get the responses from peer
        operation_no = 1
        while True:
            rsp, context_id = self.dimse.receive_msg(wait=True)

            # If nothing received from the peer, try again
            if not rsp:
                LOGGER.error("Connection closed or timed-out")
                self.abort()
                return

            # Received a C-MOVE response from the peer
            if rsp.__class__ == C_MOVE:
                status = Dataset()
                status.Status = rsp.Status
                for keyword in ['ErrorComment', 'OffendingElement',
                                'NumberOfRemainingSuboperations',
                                'NumberOfCompletedSuboperations',
                                'NumberOfFailedSuboperations',
                                'NumberOfWarningSuboperations']:
                    if getattr(rsp, keyword) is not None:
                        setattr(status, keyword, getattr(rsp, keyword))

                # If the Status is 'Pending' then the processing of matches
                #   and sub-operations are initiated or continuing
                # If the Status is 'Cancel', 'Failure', 'Warning' or 'Success'
                #   then we are finished
                category = code_to_category(status.Status)

                # Log status type
                LOGGER.debug('')
                if category == 'Pending':
                    LOGGER.info("Move SCP Response: %s (Pending)", operation_no)
                elif category in ['Success', 'Cancel', 'Warning']:
                    LOGGER.info("Move SCP Result: (%s)", category)
                elif category == 'Failure':
                    LOGGER.info("Move SCP Result: (Failure - 0x%04x)",
                                status.Status)

                # Log number of remaining sub-operations
                LOGGER.info("Sub-Operations Remaining: %s, Completed: %s, "
                            "Failed: %s, Warning: %s",
                            rsp.NumberOfRemainingSuboperations or '0',
                            rsp.NumberOfCompletedSuboperations or '0',
                            rsp.NumberOfFailedSuboperations or '0',
                            rsp.NumberOfWarningSuboperations or '0')

                # Yields - 'Success', 'Warning', 'Cancel', 'Failure' are final
                #   yields, 'Pending' means more to come
                identifier = None
                if category == 'Pending':
                    operation_no += 1
                    yield status, identifier
                    continue
                elif rsp.Identifier and category in ['Cancel', 'Warning',
                                                     'Failure']:
                    # From Part 4, Annex C.4.2, responses with these statuses
                    #   should contain an Identifier dataset with a
                    #   (0008,0058) Failed SOP Instance UID List element
                    #   however this can't be assumed
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
                        LOGGER.error("Failed to decode the received Identifier "
                                     "dataset")
                        LOGGER.exception(ex)

                yield status, identifier
                break

            # Received a C-STORE request from the peer
            #   C-STORE requests can be over the same association for C-MOVE
            elif rsp.__class__ == C_STORE:
                self._c_store_scp(rsp)

            # Received a C-CANCEL request from the peer
            elif rsp.__class__ == C_CANCEL and rsp.MessageID == msg_id:
                pass

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
            If the peer timed out or sent an invalid response then yields an
            empty ``Dataset``. If a response was received from the peer then
            yields a ``Dataset`` containing at least a (0000,0900) *Status*
            element, and depending on the returned value may optionally contain
            additional elements (see DICOM Standard Part 7, Section 9.1.2.1.5
            and Annex C).

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
          `9.3.3 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.3>`_ and
          `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`__
        """
        # Can't send a C-GET without an Association
        if not self.is_established:
            raise RuntimeError("The association with a peer SCP must be "
                               "established before sending a C-GET request")

        if query_model == "P":
            sop_class = PatientRootQueryRetrieveInformationModelGet
        elif query_model == "S":
            sop_class = StudyRootQueryRetrieveInformationModelGet
        elif query_model == "O":
            sop_class = PatientStudyOnlyQueryRetrieveInformationModelGet
        elif query_model == "C":
            sop_class = CompositeInstanceRootRetrieveGet
        elif query_model == "CB":
            sop_class = CompositeInstanceRetrieveWithoutBulkDataGet
        elif query_model == "H":
            sop_class = HangingProtocolInformationModelGet
        elif query_model == "D":
            sop_class = DefinedProcedureProtocolInformationModelGet
        elif query_model == "CP":
            sop_class = ColorPaletteInformationModelGet
        elif query_model == "IG":
            sop_class = GenericImplantTemplateInformationModelGet
        elif query_model == "IA":
            sop_class = ImplantAssemblyTemplateInformationModelGet
        elif query_model == "IT":
            sop_class = ImplantTemplateGroupInformationModelGet
        else:
            raise ValueError(
                "Unsupported value for `query_model`: {}".format(query_model)
            )

        # Determine the Presentation Context we are operating under
        #   and hence the transfer syntax to use for encoding `dataset`
        transfer_syntax = None
        for context in self.acse.context_manager.accepted:
            if sop_class.uid == context.abstract_syntax:
                transfer_syntax = context.transfer_syntax[0]
                context_id = context.context_id
                break

        if transfer_syntax is None:
            LOGGER.error("No accepted Presentation Context for: '%s'",
                         sop_class.uid)
            LOGGER.error("Get SCU failed due to there being no accepted "
                         "presentation context for the current dataset")
            raise ValueError("No accepted Presentation Context for 'dataset'")

        # Build C-GET request primitive
        #   (M) Message ID
        #   (M) Affected SOP Class UID
        #   (M) Priority
        #   (M) Identifier
        req = C_GET()
        req.MessageID = msg_id
        req.AffectedSOPClassUID = sop_class.uid
        req.Priority = priority

        # Encode the Identifier `dataset` using the agreed transfer syntax
        #   Will return None if failed to encode
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
        self.dimse.send_msg(req, context_id)

        # Get the responses from the peer
        operation_no = 1
        while True:
            # Wait for DIMSE message, may be either a C-GET response or a
            #   C-STORE request
            rsp, context_id = self.dimse.receive_msg(wait=True)

            # If nothing received from the peer, try again
            if not rsp:
                LOGGER.error("Connection closed or timed-out")
                self.abort()
                return

            # Received a C-GET response from the peer
            if rsp.__class__ == C_GET:
                status = Dataset()
                status.Status = rsp.Status
                for keyword in ['ErrorComment', 'OffendingElement',
                                'NumberOfRemainingSuboperations',
                                'NumberOfCompletedSuboperations',
                                'NumberOfFailedSuboperations',
                                'NumberOfWarningSuboperations']:
                    if getattr(rsp, keyword) is not None:
                        setattr(status, keyword, getattr(rsp, keyword))

                # If the Status is 'Pending' then the processing of
                #   matches and sub-operations are initiated or continuing
                # If the Status is 'Cancel', 'Failure', 'Warning' or 'Success'
                #   then we are finished
                category = code_to_category(status.Status)

                # Log status type
                LOGGER.debug('')
                if category == 'Pending':
                    LOGGER.info("Get SCP Response: %s (Pending)", operation_no)
                elif category in ['Success', 'Cancel', 'Warning']:
                    LOGGER.info('Get SCP Result: (%s)', category)
                elif category == "Failure":
                    LOGGER.info('Get SCP Result: (Failure - 0x%04x)',
                                status.Status)

                # Log number of remaining sub-operations
                LOGGER.info("Sub-Operations Remaining: %s, Completed: %s, "
                            "Failed: %s, Warning: %s",
                            rsp.NumberOfRemainingSuboperations or '0',
                            rsp.NumberOfCompletedSuboperations or '0',
                            rsp.NumberOfFailedSuboperations or '0',
                            rsp.NumberOfWarningSuboperations or '0')

                # Yields - 'Success', 'Warning', 'Failure', 'Cancel' are
                #   final yields, 'Pending' means more to come
                identifier = None
                if category in ['Pending']:
                    operation_no += 1
                    yield status, identifier
                    continue
                elif rsp.Identifier and category in ['Cancel', 'Warning',
                                                     'Failure']:
                    # From Part 4, Annex C.4.3, responses with these statuses
                    #   should contain an Identifier dataset with a
                    #   (0008,0058) Failed SOP Instance UID List element
                    #   however this can't be assumed
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
                        LOGGER.error("Failed to decode the received Identifier "
                                     "dataset")
                        LOGGER.exception(ex)

                yield status, identifier
                break

            # Received a C-STORE request from the peer
            elif rsp.__class__ == C_STORE:
                self._c_store_scp(rsp)

            # Received a C-CANCEL request from the peer
            elif rsp.__class__ == C_CANCEL and rsp.MessageID == msg_id:
                pass

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

        transfer_syntax = None
        for context in self.acse.context_manager.accepted:
            if req.AffectedSOPClassUID == context.abstract_syntax:
                transfer_syntax = context.transfer_syntax[0]
                break

        if transfer_syntax is None:
            LOGGER.error("No accepted Presentation Context for: '%s'",
                         req.AffectedSOPClassUID)
            # SOP Class not supported, no context ID?
            rsp.Status = 0x0122
            self.dimse.send_msg(rsp, 1)
            return

        # Attempt to decode the dataset
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

        info = {
            'acceptor' : self.local_ae,
            'requestor': self.peer_ae,
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

    def _send_c_cancel(self, msg_id):
        """Send a C-CANCEL-* request to the peer AE.

        See PS3.7 9.3.2.3

        Parameters
        ----------
        msg_id : int
            The message ID of the C-GET/MOVE/FIND operation we want to cancel.
            Must be between 0 and 65535, inclusive.
        """
        # Can't send a C-CANCEL without an Association
        if not self.is_established:
            raise RuntimeError("The association with a peer SCP must be "
                               "established before sending a C-CANCEL request.")

        if not isinstance(msg_id, int):
            # FIXME: Add more detail to exception
            raise TypeError("msg_id must be an integer.")

        # FIXME: Add validity checks to msg_id value

        # Build C-CANCEL primitive
        primitive = C_CANCEL()
        primitive.MessageIDBeingRespondedTo = msg_id

        LOGGER.info('Sending C-CANCEL')

        # Send C-CANCEL request
        # FIXME: need context ID, not msg ID. maybe
        self.dimse.send_msg(primitive, msg_id)


    # DIMSE-N services provided by the Association
    # TODO: Implement DIMSE-N services
    def send_n_event_report(self):
        """Send an N-EVENT-REPORT request message to the peer AE."""
        # Can't send an N-EVENT-REPORT without an Association
        if not self.is_established:
            raise RuntimeError("The association with a peer SCP must be "
                               "established before sending an N-EVENT-REPORT "
                               "request")
        raise NotImplementedError

    def send_n_get(self, attribute_list, sop_class, sop_instance, msg_id=1):
        """Send an N-GET request message to the peer AE.

        Parameters
        ----------
        attribute_list : list of pydicom.tag.Tag
            A list of DICOM Data Element tags to be sent in the request's
            (0000,1005) *Attribute Identifier List* element.
        sop_class : pydicom.uid.UID
            The SOP Class UID to be sent in the request's (0000,0003)
            *Requested SOP Class UID* element.

            Display System SOP Class : 1.2.840.10008.5.1.1.40
            Media Creation Management SOP Class : 1.2.840.10008.5.1.1.33
            Print Job SOP Class : 1.2.840.10008.5.1.1.14
            Printer SOP Class : 1.2.840.10008.5.1.1.16
            Printer Configuration Retrieval SOP Class : 1.2.840.10008.5.1.1.16.376

        sop_instance : pydicom.uid.UID
            The SOP Class UID to be sent in the request's (0000,1001)
            *Requested SOP Instance UID* element.

            Display System SOP Instance : 1.2.840.10008.5.1.1.40.1
            Printer SOP Instance : 1.2.840.10008.5.1.1.17
            Printer Configuration Retrieval SOP Instance : 1.2.840.10008.5.1.1.17.376

        msg_id : int, optional
            The DIMSE *Message ID*, must be between 0 and 65535, inclusive,
            (default 1).

        Returns
        -------
        status : pydicom.dataset.Dataset
            If the peer timed out or sent an invalid response then yields an
            empty ``Dataset``. If a response was received from the peer then
            yields a ``Dataset`` containing at least a (0000,0900) *Status*
            element, and depending on the returned value, may optionally
            contain additional elements (see the DICOM Standard, Part 7,
            Section 9.1.2.1.5 and Annex C).
        attribute_list : pydicom.dataset.Dataset
            A dataset containing the values of the attributes.
        """
        # Can't send an N-GET without an Association
        if not self.is_established:
            raise RuntimeError(
                "The association with a peer SCP must be established before "
                "sending an N-GET request."
            )

        # Determine the Presentation Context we are operating under
        #   and hence the transfer syntax to use for encoding `dataset`
        transfer_syntax = None
        for context in self.acse.context_manager.accepted:
            if sop_class == context.abstract_syntax:
                transfer_syntax = context.transfer_syntax[0]
                context_id = context.context_id
                break
        else:
            LOGGER.error(
                "Association.send_n_get - no accepted Presentation Context "
                "for: '{}'".format(sop_class)
            )
            LOGGER.error(
                "Get SCU failed due to there being no accepted presentation "
                "context"
            )
            raise ValueError(
                "No accepted Presentation Context for the SOP Class UID '{}'"
                .format(sop_class)
            )

        # Build N-GET request primitive
        #   (M) Message ID
        #   (M) Requested SOP Class UID
        #   (M) Requested SOP Instance UID
        #   (U) Attribute Identifier List
        req = N_GET()
        req.MessageID = msg_id
        req.RequestedSOPClassUID = sop_class
        req.RequestedSOPInstanceUID = sop_instance
        req.AttributeIdentifierList = attribute_list

        # Send N-GET request to the peer via DIMSE and wait for the response
        self.dimse.send_msg(req, context_id)
        rsp, _ = self.dimse.receive_msg(wait=True)

        # Determine validity of the response and get the status
        status = Dataset()
        if rsp is None:
            LOGGER.error('DIMSE service timed out')
            self.abort()
        elif rsp.is_valid_response:
            status.Status = rsp.Status
            for keyword in ['ErrorComment', 'OffendingElement']:
                if getattr(rsp, keyword) is not None:
                    setattr(status, keyword, getattr(rsp, keyword))
        else:
            LOGGER.error('Received an invalid N-GET response from the peer')
            self.abort()

        return status, rsp.AttributeList

    def send_n_set(self):
        """Send an N-SET request message to the peer AE."""
        # Can't send an N-SET without an Association
        if not self.is_established:
            raise RuntimeError("The association with a peer SCP must be "
                               "established before sending an N-SET "
                               "request.")
        raise NotImplementedError

    def send_n_action(self):
        """Send an N-ACTION request message to the peer AE."""
        # Can't send an N-ACTION without an Association
        if not self.is_established:
            raise RuntimeError("The association with a peer SCP must be "
                               "established before sending an N-ACTION "
                               "request.")
        raise NotImplementedError

    def send_n_create(self):
        """Send an N-CREATE request message to the peer AE."""
        # Can't send an N-CREATE without an Association
        if not self.is_established:
            raise RuntimeError("The association with a peer SCP must be "
                               "established before sending an N-CREATE "
                               "request.")
        raise NotImplementedError

    def send_n_delete(self):
        """Send an N-DELETE request message to the peer AE."""
        # Can't send an N-DELETE without an Association
        if not self.is_established:
            raise RuntimeError("The association with a peer SCP must be "
                               "established before sending an N-DELETE "
                               "request.")
        raise NotImplementedError


    # Association logging/debugging functions
    @staticmethod
    def debug_association_requested(primitive):
        """Debugging information when an A-ASSOCIATE request received.

        Parameters
        ----------
        primitive : pynetdicom3.pdu_primitives.A_ASSOCIATE
            The A-ASSOCIATE (RQ) PDU received from the DICOM Upper Layer
        """
        pass

    @staticmethod
    def debug_association_accepted(primitive):
        """Debugging information when an A-ASSOCIATE accept is received.

        Parameters
        ----------
        primitive : pynetdicom3.pdu_primitives.A_ASSOCIATE
            The A-ASSOCIATE (AC) PDU received from the DICOM Upper Layer
        """
        pass

    @staticmethod
    def debug_association_rejected(primitive):
        """Debugging information when an A-ASSOCIATE rejection received.

        Parameters
        ----------
        assoc_primitive : pynetdicom3.pdu_primitives.A_ASSOCIATE
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
        assoc_primitive : pynetdicom3.pdu_primitives.A_RELEASE
            The A-RELEASE (RQ) primitive received from the DICOM Upper Layer
        """
        LOGGER.info('Association Released')

    @staticmethod
    def debug_association_aborted(primitive=None):
        """Debugging information when an A-ABORT request received.

        Parameters
        ----------
        assoc_primitive : pynetdicom3.pdu_primitives.A_ABORT
            The A-ABORT (RQ) primitive received from the DICOM Upper Layer
        """
        LOGGER.error('Association Aborted')