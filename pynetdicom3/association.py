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
    N_EVENT_REPORT, N_GET, N_SET, N_CREATE, N_ACTION, N_DELETE
)
from pynetdicom3.dsutils import decode, encode
from pynetdicom3.dul import DULServiceProvider
from pynetdicom3.presentation import negotiate_as_acceptor
from pynetdicom3.sop_class import (
    uid_to_sop_class,
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
from pynetdicom3.pdu_primitives import (
    UserIdentityNegotiation,
    AsynchronousOperationsWindowNegotiation,
    SOPClassExtendedNegotiation,
    SOPClassCommonExtendedNegotiation,
    SCP_SCU_RoleSelectionNegotiation,
    A_ASSOCIATE, A_ABORT, A_P_ABORT
)
from pynetdicom3.status import (
    code_to_status, code_to_category, STORAGE_SERVICE_CLASS_STATUS,
    STATUS_WARNING, STATUS_SUCCESS, STATUS_CANCEL, STATUS_PENDING,
    STATUS_FAILURE
)
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

    @property
    def accepted_contexts(self):
        """Return a list of accepted PresentationContexts."""
        return self.acse.accepted_contexts

    def _check_received_status(self, rsp):
        """Return a dataset containing status related elements.

        Parameters
        ----------
        rsp : pynetdicom3.dimse_primitives
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
        if rsp is None:
            LOGGER.error('DIMSE service timed out')
            self.abort()
        elif rsp.is_valid_response:
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

    def _get_valid_context(self, ab_syntax, tr_syntax, role, context_id=None):
        """

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

    @property
    def rejected_contexts(self):
        """Return a list of rejected PresentationContexts."""
        return self.acse.rejected_contexts

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
        # User Identity Negotiation (PS3.7 Annex D.3.3.7)
        # TODO: Implement propoerly but for now just remove items
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
        assoc_rq.user_information[:] = (
            ii for ii in assoc_rq.user_information
                if not isinstance(ii, UserIdentityNegotiation)
        )

        # Extended Negotiation
        # TODO: Implement propoerly but for now just remove items
        assoc_rq.user_information[:] = (
            ii for ii in assoc_rq.user_information
                if not isinstance(ii, SOPClassExtendedNegotiation)
        )

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

        ## Negotiate Presentation Contexts
        # SCP/SCU Role Selection Negotiation request items
        # {SOP Class UID : (SCU role, SCP role)}
        rq_roles = {}
        for ii in assoc_rq.user_information:
            if isinstance(ii, SCP_SCU_RoleSelectionNegotiation):
                rq_roles[ii.sop_class_uid] = (ii.scu_role, ii.scp_role)

        # Remove role selection items
        assoc_rq.user_information[:] = (
            ii for ii in assoc_rq.user_information
                if not isinstance(ii, SCP_SCU_RoleSelectionNegotiation)
        )

        result, ac_roles = negotiate_as_acceptor(
            assoc_rq.presentation_context_definition_list,
            self.ae.supported_contexts,
            rq_roles
        )
        self.acse.accepted_contexts = [
            cx for cx in result if cx.result == 0x00
        ]

        self.acse.rejected_contexts = [
            cx for cx in result if cx.result != 0x00
        ]

        # Add any SCP/SCU Role Selection Negotiation response items
        assoc_rq.user_information.extend(ac_roles)

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
            # FIXME: This is not a good way to handle messages, they should
            #   be managed via their message ID and/or SOP Class UIDs
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
                else:
                    # FIXME: C-CANCEL requests are not being handled correctly
                    #   need a way to identify which service it belongs to
                    #   or maybe just call the callback now?
                    self.abort()
                    return

                # Convert the SOP Class UID to the corresponding service
                service_class = uid_to_service_class(class_uid)()

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
                        try:
                            service_class.SCP(msg, context, info)
                        except NotImplementedError:
                            # SCP isn't implemented
                            self.abort()
                            return
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

        local_ae = {'address' : self.ae.address,
                    'port' : self.ae.port,
                    'ae_title' : self.ae.ae_title}

        # Apply requestor's SCP/SCU role selection (if any)
        roles = {}
        for ii in self.ext_neg:
            if isinstance(ii, SCP_SCU_RoleSelectionNegotiation):
                roles[ii.sop_class_uid] = (ii.scu_role, ii.scp_role)

        if roles:
            for cx in self.requested_contexts:
                try:
                    (cx.scu_role, cx.scp_role) = roles[cx.abstract_syntax]
                except KeyError:
                    pass

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
        rsp, _ = self.dimse.receive_msg(wait=True)

        # Determine validity of the response and get the status
        status = self._check_received_status(rsp)

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
          `9.3.1 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.1>`_ and
          `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`__
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
        rsp, _ = self.dimse.receive_msg(wait=True)

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

        SOP_CLASSES = {
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
            sop_class = SOP_CLASSES[query_model]
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
            for keyword in rsp.STATUS_OPTIONAL_KEYWORDS:
                if getattr(rsp, keyword) is not None:
                    setattr(status, keyword, getattr(rsp, keyword))

            status_category = code_to_category(status.Status)

            LOGGER.debug('-' * 65)
            LOGGER.debug('Find SCP Response: {2} (0x{0:04x} - {1})'
                         .format(status.Status, status_category, ii))

            # We want to exit the wait loop if we receive a Failure, Cancel or
            #   Success status type
            if status_category != STATUS_PENDING:
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

        SOP_CLASSES = {
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
            sop_class = SOP_CLASSES[query_model]
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
                for keyword in rsp.STATUS_OPTIONAL_KEYWORDS:
                    if getattr(rsp, keyword) is not None:
                        setattr(status, keyword, getattr(rsp, keyword))

                # If the Status is 'Pending' then the processing of matches
                #   and sub-operations are initiated or continuing
                # If the Status is 'Cancel', 'Failure', 'Warning' or 'Success'
                #   then we are finished
                category = code_to_category(status.Status)

                # Log status type
                LOGGER.debug('')
                if category == STATUS_PENDING:
                    LOGGER.info("Move SCP Response: %s (Pending)", operation_no)
                elif category in [STATUS_SUCCESS, STATUS_CANCEL, STATUS_WARNING]:
                    LOGGER.info("Move SCP Result: (%s)", category)
                elif category == STATUS_FAILURE:
                    LOGGER.info("Move SCP Result: (Failure - 0x%04x)",
                                status.Status)

                # Log number of remaining sub-operations
                LOGGER.info(
                    "Sub-Operations Remaining: %s, Completed: %s, "
                    "Failed: %s, Warning: %s",
                    rsp.NumberOfRemainingSuboperations or '0',
                    rsp.NumberOfCompletedSuboperations or '0',
                    rsp.NumberOfFailedSuboperations or '0',
                    rsp.NumberOfWarningSuboperations or '0'
                )

                # Yields - 'Success', 'Warning', 'Cancel', 'Failure' are final
                #   yields, 'Pending' means more to come
                identifier = None
                if category == STATUS_PENDING:
                    operation_no += 1
                    yield status, identifier
                    continue
                elif rsp.Identifier and category in [STATUS_CANCEL,
                                                     STATUS_WARNING,
                                                     STATUS_FAILURE]:
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
                        identifier = None

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

        SOP_CLASSES = {
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
            sop_class = SOP_CLASSES[query_model]
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
                for keyword in rsp.STATUS_OPTIONAL_KEYWORDS:
                    if getattr(rsp, keyword) is not None:
                        setattr(status, keyword, getattr(rsp, keyword))

                # If the Status is 'Pending' then the processing of
                #   matches and sub-operations are initiated or continuing
                # If the Status is 'Cancel', 'Failure', 'Warning' or 'Success'
                #   then we are finished
                category = code_to_category(status.Status)

                # Log status type
                LOGGER.debug('')
                if category == STATUS_PENDING:
                    LOGGER.info("Get SCP Response: %s (Pending)", operation_no)
                elif category in [STATUS_SUCCESS, STATUS_CANCEL, STATUS_WARNING]:
                    LOGGER.info('Get SCP Result: (%s)', category)
                elif category == STATUS_FAILURE:
                    LOGGER.info('Get SCP Result: (Failure - 0x%04x)',
                                status.Status)

                # Log number of remaining sub-operations
                LOGGER.info(
                    "Sub-Operations Remaining: %s, Completed: %s, "
                    "Failed: %s, Warning: %s",
                    rsp.NumberOfRemainingSuboperations or '0',
                    rsp.NumberOfCompletedSuboperations or '0',
                    rsp.NumberOfFailedSuboperations or '0',
                    rsp.NumberOfWarningSuboperations or '0'
                )

                # Yields - 'Success', 'Warning', 'Failure', 'Cancel' are
                #   final yields, 'Pending' means more to come
                identifier = None
                if category in [STATUS_PENDING]:
                    operation_no += 1
                    yield status, identifier
                    continue
                elif rsp.Identifier and category in [STATUS_CANCEL,
                                                     STATUS_WARNING,
                                                     STATUS_FAILURE]:
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
                        identifier = None

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
        transfer_syntax = context.transfer_syntax[0]
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
            If the peer timed out or sent an invalid response then yields an
            empty ``Dataset``. If a response was received from the peer then
            yields a ``Dataset`` containing at least a (0000,0900) *Status*
            element, and depending on the returned value, may optionally
            contain additional elements (see the DICOM Standard, Part 7,
            Section 9.1.2.1.5 and Annex C).

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
          `10.3.1 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_10.3.1>`_ and
          `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`__
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
        rsp, _ = self.dimse.receive_msg(wait=True)

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
            If the peer timed out or sent an invalid response then yields an
            empty ``Dataset``. If a response was received from the peer then
            yields a ``Dataset`` containing at least a (0000,0900) *Status*
            element, and depending on the returned value, may optionally
            contain additional elements (see the DICOM Standard, Part 7,
            Section 9.1.2.1.5 and Annex C).

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
          `10.3.2 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_10.3.2>`_ and
          `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`__
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
        rsp, _ = self.dimse.receive_msg(wait=True)

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
            If the peer timed out or sent an invalid response then yields an
            empty ``Dataset``. If a response was received from the peer then
            yields a ``Dataset`` containing at least a (0000,0900) *Status*
            element, and depending on the returned value, may optionally
            contain additional elements (see the DICOM Standard, Part 7,
            Section 9.1.2.1.5 and Annex C).

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
          `10.3.3 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_10.3.3>`_ and
          `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`__
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
        rsp, _ = self.dimse.receive_msg(wait=True)

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

    def send_n_action(self, dataset, action_type, class_uid, instance_uid, msg_id=1):
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
            If the peer timed out or sent an invalid response then yields an
            empty ``Dataset``. If a response was received from the peer then
            yields a ``Dataset`` containing at least a (0000,0900) *Status*
            element, and depending on the returned value, may optionally
            contain additional elements (see the DICOM Standard, Part 7,
            Section 9.1.2.1.5 and Annex C).

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
          `10.3.3 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_10.3.3>`_ and
          `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`__
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
        rsp, _ = self.dimse.receive_msg(wait=True)

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
            If the peer timed out or sent an invalid response then yields an
            empty ``Dataset``. If a response was received from the peer then
            yields a ``Dataset`` containing at least a (0000,0900) *Status*
            element, and depending on the returned value, may optionally
            contain additional elements (see the DICOM Standard, Part 7,
            Section 9.1.2.1.5 and Annex C).

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
          `10.3.5 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_10.3.5>`_ and
          `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`__
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
        rsp, _ = self.dimse.receive_msg(wait=True)

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
            If the peer timed out or sent an invalid response then yields an
            empty ``Dataset``. If a response was received from the peer then
            yields a ``Dataset`` containing at least a (0000,0900) *Status*
            element, and depending on the returned value, may optionally
            contain additional elements (see the DICOM Standard, Part 7,
            Section 9.1.2.1.5 and Annex C).

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
          `10.3.6 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_10.3.6>`_ and
          `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`__
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
        transfer_syntax = context.transfer_syntax[0]

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
        rsp, _ = self.dimse.receive_msg(wait=True)

        # Determine validity of the response and get the status
        status = self._check_received_status(rsp)

        return status


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
