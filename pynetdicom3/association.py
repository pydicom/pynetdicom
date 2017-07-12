"""
Defines the Association class
"""
from io import BytesIO
import logging
import socket
import threading
import time

from pydicom.uid import UID

from pynetdicom3.acse import ACSEServiceProvider
from pynetdicom3.dimse import DIMSEServiceProvider
from pynetdicom3.dimse_primitives import C_ECHO, C_MOVE, C_STORE, C_GET, \
                                         C_FIND, C_CANCEL
from pynetdicom3.dsutils import decode, encode
from pynetdicom3.dul import DULServiceProvider
from pynetdicom3.sop_class import uid_to_sop_class, VerificationServiceClass, \
                         StorageServiceClass, \
                         QueryRetrieveGetServiceClass, \
                         QueryRetrieveFindServiceClass, \
                         QueryRetrieveMoveServiceClass, \
                         ModalityWorklistInformationFind, \
                         ModalityWorklistServiceSOPClass, \
                         PatientRootQueryRetrieveInformationModelFind, \
                         StudyRootQueryRetrieveInformationModelFind, \
                         PatientStudyOnlyQueryRetrieveInformationModelFind, \
                         PatientRootQueryRetrieveInformationModelMove, \
                         StudyRootQueryRetrieveInformationModelMove, \
                         PatientStudyOnlyQueryRetrieveInformationModelMove, \
                         PatientRootQueryRetrieveInformationModelGet, \
                         StudyRootQueryRetrieveInformationModelGet, \
                         PatientStudyOnlyQueryRetrieveInformationModelGet
from pynetdicom3.pdu_primitives import UserIdentityNegotiation, \
                                   SOPClassExtendedNegotiation, \
                                   SOPClassCommonExtendedNegotiation, \
                                   A_ASSOCIATE, A_ABORT, A_P_ABORT
from pynetdicom3.utils import PresentationContextManager

LOGGER = logging.getLogger('pynetdicom3.assoc')


class Association(threading.Thread):
    """Manages Associations with peer AEs.

    The actual low level work done for Associations is performed by
    pynetdicom3.acse.ACSEServiceProvider.

    When the local AE is acting as an SCP, initialise the Association using
    the socket to listen on for incoming Association requests. When the local
    AE is acting as an SCU, initialise the Association with the details of the
    peer AE.

    When AE is acting as an SCP:
        assoc = Association(client_socket, max_pdu)

    When AE is acting as an SCU:
        assoc = Association(peer_ae, acse_timeout, dimse_timeout,
                            max_pdu, ext_neg)

    Attributes
    ----------
    acse : ACSEServiceProvider
        The Association Control Service Element provider.
    ae : pynetdicom3.applicationentity.ApplicationEntity
        The local AE.
    dimse : DIMSEServiceProvider
        The DICOM Message Service Element provider.
    dul : DUL
        The DICOM Upper Layer service provider instance.
    is_aborted : bool
        True if the association has been aborted, False otherwise.
    is_established : bool
        True if the association has been established, False otherwise.
    is_rejected : bool
        True if the association was rejected, False otherwise.
    is_released : bool
        True if the association has been released, False otherwise.
    mode : str
        Whether the local AE is acting as the Association 'Requestor' or
        'Acceptor' (i.e. SCU or SCP).
    peer_ae : dict
        The peer Application Entity details, keys: 'Port', 'Address', 'Title'.
    client_socket : socket.socket
        The socket to use for connections with the peer AE.
    scu_supported_sop : list of pynetdicom3.sop_class.ServiceClass
        A list of the supported SOP classes when acting as an SCU.
    scp_supported_sop : list of pynetdicom3.sop_class.ServiceClass
        A list of the supported SOP classes when acting as an SCP.
    """
    def __init__(self, local_ae, client_socket=None, peer_ae=None,
                 acse_timeout=60, dimse_timeout=None, max_pdu=16382, 
                 ext_neg=None):
        """Create a new Association.

        Parameters
        ----------
        local_ae : pynetdicom3.applicationentity.ApplicationEntity
            The local AE instance.
        client_socket : socket.socket or None, optional
            If the local AE is acting as an SCP, this is the listen socket for
            incoming connection requests. A value of None is used when acting
            as an SCU.
        peer_ae : dict, optional
            If the local AE is acting as an SCU this is the AE title, host and
            port of the peer AE that we want to Associate with. Keys: 'Port',
            'Address', 'Title'.
        acse_timeout : int, optional
            The maximum amount of time to wait for a reply during association,
            in seconds. A value of 0 means no timeout (default: 30).
        dimse_timeout : int, optional
            The maximum amount of time to wait for a reply during DIMSE, in
            seconds. A value of 0 means no timeout (default: 0).
        max_pdu : int, optional
            The maximum PDU receive size in bytes for the association. A value
            of 0 means no maximum size (default: 16382 bytes).
        ext_neg : list of extended negotiation parameters objects, optional
            If the association requires an extended negotiation then `ext_neg`
            is a list containing the negotiation objects (default: None).
        """
        # Why is the AE in charge of supplying the client socket?
        #   Hmm, perhaps because we can have multiple connections on the same
        #       listen port. Does that even work? Probably needs testing
        #   As SCP: supply port number to listen on (listen_port != None)
        #   As SCU: supply addr/port to make connection on (peer_ae != None)
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

            for key in ['AET', 'Port', 'Address']:
                if key not in peer_ae:
                    raise KeyError("peer_ae must contain 'AET', 'Port' and "
                                   "'Address' entries")
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

        # Why do we instantiate the DUL provider with a socket when acting
        #   as an SCU?
        # Q. Why do we need to feed the DUL an ACSE timeout?
        # A. ARTIM timer
        self.dul = DULServiceProvider(client_socket,
                                      dul_timeout=self.ae.network_timeout,
                                      assoc=self)

        # Dict containing the peer AE title, address and port
        self.peer_ae = peer_ae

        # Lists of pynetdicom3.utils.PresentationContext items that the local
        #   AE supports when acting as an SCU and SCP
        self.scp_supported_sop = []
        self.scu_supported_sop = []

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
            _ = self.acse.release_assoc()
            self.kill()
            self.is_released = True

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
        assoc_rq = self.dul.receive_pdu(wait=True)

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
        if self.ae.require_calling_aet != '' and \
                    self.ae.require_calling_aet != assoc_rq.calling_ae_title:
            reject_assoc_rsd = [(0x01, 0x01, 0x03)]

        # Called AE Title not recognised
        if self.ae.require_called_aet != '' and \
                        self.ae.require_called_aet != assoc_rq.called_ae_title:
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
        self.acse.context_manager.acceptor_contexts = \
                                self.ae.presentation_contexts_scp

        self.acse.accepted_contexts = self.acse.context_manager.accepted

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
        self._is_running = True
        while not self._kill:
            time.sleep(0.001)

            # Check with the DIMSE provider for incoming messages
            #   all messages should be a DIMSEMessage subclass
            msg, msg_context_id = self.dimse.receive_msg(wait=True)

            # DIMSE message received
            if msg:
                # Use the Message's Affected SOP Class UID to create a new
                #   SOP Class instance, if there's no AffectedSOPClassUID
                #   then we received a C-CANCEL request
                # FIXME
                if not hasattr(msg, 'AffectedSOPClassUID'):
                    self.abort()
                    return

                sop_class = uid_to_sop_class(msg.AffectedSOPClassUID)()

                # Check that the SOP Class is supported by the AE
                # New method
                pc_accepted = self.acse.accepted_contexts
                context = [pc for pc in pc_accepted if pc.ID == msg_context_id]

                # Matching context
                if context:
                    sop_class.presentation_context = context[0]
                else:
                    # No matching presentation context
                    pass

                # Old method
                matching_context = False
                for context in self.acse.accepted_contexts:
                    if context.ID == msg_context_id:
                        sop_class.pcid = context.ID
                        sop_class.sopclass = context.AbstractSyntax
                        sop_class.transfersyntax = context.TransferSyntax[0]
                        matching_context = True
                if matching_context:
                    # Most of these shouldn't be necessary
                    sop_class.maxpdulength = self.peer_max_pdu
                    sop_class.DIMSE = self.dimse
                    sop_class.ACSE = self.acse
                    sop_class.AE = self.ae

                    # Run SOPClass in SCP mode
                    sop_class.SCP(msg)

            # Check for release request
            if self.acse.CheckRelease():
                # Callback trigger
                self.debug_association_released()
                self.ae.on_association_released()
                self.acse.Release()
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
                self.kill()

    def _run_as_requestor(self):
        """Run as the Association Requestor."""
        if self.ae.presentation_contexts_scu == []:
            LOGGER.error("No presentation contexts set for the SCU")
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
        #    tmp.SOPClassUID = context.AbstractSyntax
        #    tmp.SCURole = 0
        #    tmp.SCPRole = 1
        #
        #    self.ext_neg.append(tmp)

        local_ae = {'Address' : self.ae.address,
                    'Port'    : self.ae.port,
                    'AET'     : self.ae.ae_title}

        # Request an Association via the ACSE
        is_accepted, assoc_rsp = \
                self.acse.request_assoc(local_ae, self.peer_ae,
                                        self.local_max_pdu,
                                        self.ae.presentation_contexts_scu,
                                        userspdu=self.ext_neg)

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
                        (context.ID,
                         uid_to_sop_class(context.AbstractSyntax),
                         context.TransferSyntax[0]))

                # Assocation established OK
                self.is_established = True

                # This seems like it should be event driven rather than
                #   driven by a loop
                #
                # Listen for further messages from the peer
                while not self._kill:
                    time.sleep(0.001)

                    # Check for release request
                    if self.acse.CheckRelease():
                        self.is_released = True
                        self.is_established = False
                        # Callback trigger
                        self.ae.on_association_released()
                        self.debug_association_released()
                        self.acse.Release()
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
            The message ID to use (default: 1)

        Returns
        -------
        status : pynetdicom3.sop_class.Status or None
            Returns None if no valid presentation context or no response
            from the peer, Success (0x0000) otherwise.
        """
        # Can't send a C-ECHO without an Association
        if not self.is_established:
            raise RuntimeError("The association with a peer SCP must be "
                               "established before sending a C-ECHO request")

        # Service Class - used to determine Status
        service_class = VerificationServiceClass()

        uid = UID('1.2.840.10008.1.1')

        # Determine the Presentation Context we are operating under
        #   and hence the transfer syntax to use for encoding `dataset`
        transfer_syntax = None
        for context in self.acse.context_manager.accepted:
            if uid == context.AbstractSyntax:
                transfer_syntax = context.TransferSyntax[0]
                context_id = context.ID

        if transfer_syntax is None:
            LOGGER.error("No Presentation Context for: '%s'", uid)
            return None

        # Build C-STORE request primitive
        primitive = C_ECHO()
        primitive.MessageID = msg_id
        primitive.AffectedSOPClassUID = uid

        self.dimse.send_msg(primitive, context_id)

        # FIXME: If Association is Aborted before we receive the response
        #   then we hang here
        # This occurs because we wait for a DIMSE response not an A-ABORT
        rsp, _ = self.dimse.receive_msg(wait=True)

        status = None
        if rsp is not None:
            status = service_class.code_to_status(rsp.Status)
        else:
            # DIMSE service timed out
            self.abort()

        return status

    def send_c_store(self, dataset, msg_id=1, priority=2):
        """Send a C-STORE request to the peer AE.

        PS3.4 Annex B

        Service Definition
        ==================
        Two peer DICOM AEs implement a SOP Class of the Storage Service Class
        with one serving in the SCU role and one service in the SCP role.
        SOP Classes are implemented using the C-STORE DIMSE service. A
        successful completion of the C-STORE has the following semantics:
        - Both the SCU and SCP support the type of information to be stored
        - The information is stored in some medium
        - For some time frame, the information may be accessed

        (For JPIP Referenced Pixel Data transfer syntaxes, transfer may result
        in storage of incomplete information in that the pixel data may be
        partially or completely transferred by some other mechanism at the
        discretion of the SCP)

        Extended Negotiation
        ====================
        Extended negotiation is optional, however SCUs requesting association
        may include:
        - one SOP Class Extended Negotiation Sub-Item for each supported SOP
        Class of the Storage Service Class, as described in PS3.7 Annex D.3.3.5.
        - one SOP Class Common Extended Negotiation Sub-Item for each supported
        SOP Class of the Storage Service Class, as described in PS3.7 Annex
        D.3.3.6

        The SCP accepting association shall optionally support:
        - one SOP Class Extended Negotiation Sub-Item for each supported SOP
        Class of the Storage Service Class, as described in PS3.7 Annex D.3.3.5.

        Use of Extended Negotiation is left up to the end user to implement via
        the ``AE.extended_negotiation`` attribute.


        SOP Class Extended Negotiation
        ------------------------------
        Service Class Application Information (A-ASSOCIATE-RQ)
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        PS3.4 Table B.3-1 shows the format of the SOP Class Extended Negotiation
        Sub-Item's service-class-application-information field when requesting
        association.

        Service Class Application Information (A-ASSOCIATE-AC)
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        PS3.4 Table B.3-2 shows the format of the SOP Class Extended Negotiation
        Sub-Item's service-class-application-information field when accepting
        association.

        SOP Class Common Extended Negotiation
        -------------------------------------
        Service Class UID
        ~~~~~~~~~~~~~~~~~
        The SOP-class-uid field of the SOP Class Common Extended Negotiation
        Sub-Item shall be 1.2.840.10008.4.2

        Related General SOP Classes
        ~~~~~~~~~~~~~~~~~~~~~~~~~~~
        PS3.4 Table B.3-3 identifies the Standard SOP Classes that participate
        in this mechanism. If a Standard SOP Class is not listed, then Related
        General SOP Classes shall not be included.

        Parameters
        ----------
        dataset : pydicom.Dataset
            The DICOM dataset to send to the peer.
        msg_id : int, optional
            The message ID, must be between 0 and 65535, inclusive, (default 1).
        priority : int, optional
            The C-STORE operation priority (if supported by the peer), one of:
                2 - Low (default)
                1 - High
                0 - Medium

        Returns
        -------
        status : pynetdicom3.sop_class.Status or None
            The status for the requested C-STORE operation (see PS3.4 Annex
            B.2.3), should be one of the following Status objects/codes
            (separate causes for each status can be identified through the use
            of different codes within the available range of each status):
                Success status
                    sop_class.Success
                        Success - 0000

                Failure statuses
                    sop_class.OutOfResources
                        Refused: Out of Resources - A7xx
                    sop_class.DataSetDoesNotMatchSOPClassFailure
                        Error: Data Set does not match SOP Class - A9xx
                    sop_class.CannotUnderstand
                        Error: Cannot understand - Cxxx

                Warning statuses
                    sop_class.CoercionOfDataElements
                        Coercion of Data Elements - B000
                    sop_class.DataSetDoesNotMatchSOPClassWarning
                        Data Set does not matching SOP Class - B007
                    sop_class.ElementsDiscarded
                        Elements Discarded - B006

            Returns None if the DIMSE service timed out before receiving a
            response.
        """
        # No longer true?
        # pydicom can only handle uncompressed transfer syntaxes for conversion
        #if not dataset._is_uncompressed_transfer_syntax():
        #    LOGGER.warning("Unable to send the dataset due to pydicom not "
        #                   "supporting compressed datasets")
        #    LOGGER.error('Sending file failed')
        #    return 0xC000

        # Can't send a C-STORE without an Association
        if not self.is_established:
            raise RuntimeError("The association with a peer SCP must be "
                               "established before sending a C-STORE request")


        # Service Class - used to determine Status
        service_class = StorageServiceClass()

        # Determine the Presentation Context we are operating under
        #   and hence the transfer syntax to use for encoding `dataset`
        transfer_syntax = None
        for context in self.acse.context_manager.accepted:
            try:
                if dataset.SOPClassUID == context.AbstractSyntax:
                    transfer_syntax = context.TransferSyntax[0]
                    context_id = context.ID
            except AttributeError:
                LOGGER.error("Unable to determine Presentation Context as "
                             "Dataset has no 'SOP Class UID' element")
                LOGGER.error("Store SCU failed due to there being no valid "
                             "presentation context for the current dataset")
                return service_class.CannotUnderstand

        if transfer_syntax is None:
            LOGGER.error("No Presentation Context for: '%s'",
                         dataset.SOPClassUID)
            LOGGER.error("Store SCU failed due to there being no valid "
                         "presentation context for the current dataset")
            return service_class.CannotUnderstand

        # Build C-STORE request primitive
        primitive = C_STORE()
        primitive.MessageID = msg_id
        primitive.AffectedSOPClassUID = dataset.SOPClassUID
        primitive.AffectedSOPInstanceUID = dataset.SOPInstanceUID

        # Message priority
        if priority in [0x0000, 0x0001, 0x0002]:
            primitive.Priority = priority
        else:
            LOGGER.warning("C-STORE SCU: Invalid priority value '%s'",
                           priority)
            primitive.Priorty = 0x0002

        # Encode the dataset using the agreed transfer syntax
        # Correcting ambiguous VR is handled by pydicom
        # Will return None if failed to encode
        ds = encode(dataset,
                    transfer_syntax.is_implicit_VR,
                    transfer_syntax.is_little_endian)

        if ds is not None:
            primitive.DataSet = BytesIO(ds)
        else:
            # If we failed to encode our dataset
            return service_class.CannotUnderstand

        # Send C-STORE request primitive to DIMSE
        self.dimse.send_msg(primitive, context_id)

        # Wait for C-STORE response primitive
        #   returns a C_STORE primitive
        rsp, _ = self.dimse.receive_msg(wait=True)

        status = None
        if rsp is not None:
            status = service_class.code_to_status(rsp.Status)

        return status

    def send_c_find(self, dataset, msg_id=1, priority=2, query_model='W'):
        """Send a C-FIND request to the peer AE.

        See PS3.4 Annex C - Query/Retrieve Service Class

        Parameters
        ----------
        dataset : pydicom.Dataset
            The DICOM dataset to containing the Key Attributes the peer AE
            should perform the match against.
        msg_id : int, optional
            The message ID.
        priority : int, optional
            The C-FIND operation priority (if supported by the peer), one of:
                2 - Low (default)
                1 - High
                0 - Medium
        query_model : str, optional
            The Query/Retrieve Information Model to use, one of the following:
                'W' - Modality Worklist Information - FIND (default)
                    1.2.840.10008.5.1.4.31
                'P' - Patient Root Information Model - FIND
                    1.2.840.10008.5.1.4.1.2.1.1
                'S' - Study Root Information Model - FIND
                    1.2.840.10008.5.1.4.1.2.2.1
                'O' - Patient Study Only Information Model - FIND
                    1.2.840.10008.5.1.4.1.2.3.1

        Yields
        ------
        status : pynetdicom3.sop_class.Status
            The resulting status(es) from the C-FIND operation.
        dataset : pydicom.dataset.Dataset or None
            The resulting dataset(s) from the C-FIND operation. Yields None if
            no matching Presentation Context.
        """
        # Can't send a C-FIND without an Association
        if not self.is_established:
            raise RuntimeError("The association with a peer SCP must be "
                               "established before sending a C-FIND request")

        service_class = QueryRetrieveFindServiceClass()

        if query_model == 'W':
            sop_class = ModalityWorklistInformationFind()
            service_class = ModalityWorklistServiceSOPClass()
        elif query_model == "P":
            # Four level hierarchy, patient, study, series, composite object
            sop_class = PatientRootQueryRetrieveInformationModelFind()
        elif query_model == "S":
            # Three level hierarchy, study, series, composite object
            sop_class = StudyRootQueryRetrieveInformationModelFind()
        elif query_model == "O":
            # Retired
            sop_class = PatientStudyOnlyQueryRetrieveInformationModelFind()
        else:
            raise ValueError("Association.send_c_find() query_model "
                             "must be one of ['W'|'P'|'S'|'O']")

        # Determine the Presentation Context we are operating under
        #   and hence the transfer syntax to use for encoding `dataset`
        transfer_syntax = None
        for context in self.acse.context_manager.accepted:
            if sop_class.UID == context.AbstractSyntax:
                transfer_syntax = context.TransferSyntax[0]
                context_id = context.ID

        if transfer_syntax is None:
            LOGGER.error("No Presentation Context for: '%s'",
                         sop_class.UID)
            LOGGER.error("Find SCU failed due to there being no valid "
                         "presentation context for the current dataset")
            yield service_class.IdentifierDoesNotMatchSOPClass, None
            return

        # Build C-FIND primitive
        primitive = C_FIND()
        primitive.MessageID = msg_id
        primitive.AffectedSOPClassUID = sop_class.UID
        primitive.Priority = priority
        primitive.Identifier = BytesIO(encode(dataset,
                                              transfer_syntax.is_implicit_VR,
                                              transfer_syntax.is_little_endian))

        LOGGER.info('Find SCU Request Identifiers:')
        LOGGER.info('')
        LOGGER.info('# DICOM Dataset')
        for elem in dataset:
            LOGGER.info(elem)
        LOGGER.info('')

        # Send C-FIND request
        self.dimse.send_msg(primitive, context_id)

        # Get the responses from the peer
        ii = 1
        while True:
            time.sleep(0.001)

            # Wait for C-FIND responses
            rsp, _ = self.dimse.receive_msg(wait=False)

            # If no response received, start loop again
            if not rsp:
                continue

            # Status may be 'Failure', 'Cancel', 'Success' or 'Pending'
            # A700 - Failure (out of resources)
            # A900 - Failure (identifier doesn't match SOP class)
            # Cxxx - Failure (unable to process)
            # FE00 - Cancel (matching terminated due to cancel request)
            # FF00 - Pending (matches are continuing, current match supplied)
            # FF01 - Pending (matches are continuing, optional keys
            #                 not supported)
            # 0000 - Success (matching complete, no final identifier supplied)
            status = service_class.code_to_status(rsp.Status)

            LOGGER.debug('-' * 65)
            LOGGER.debug('Find SCP Response: %s (%s)',
                         ii, status.status_type)

            # We want to exit the wait loop if we receive a Failure, Cancel or
            #   Success status type
            if status.status_type != 'Pending':
                ds = None
                break

            # Decode the dataset
            ds = decode(rsp.Identifier,
                        transfer_syntax.is_implicit_VR,
                        transfer_syntax.is_little_endian)

            LOGGER.debug('')
            LOGGER.debug('# DICOM Dataset')
            for elem in ds:
                LOGGER.debug(elem)
            LOGGER.debug('')

            ii += 1

            yield status, ds

        yield status, ds

    def send_c_move(self, dataset, move_aet, msg_id=1,
                    priority=2, query_model='P'):
        """Send a DIMSE C-MOVE request to a peer AE.

        C-MOVE Service Procedure
        ------------------------
        PS3.7 9.1.4.2

        Invoker
        ~~~~~~~
        The invoking DIMSE user requests a performing DIMSE user match an
        Identifier against the Attributes of all SOP Instances known to the
        performing user and generate a C-STORE sub-operation for each match.

        Performer
        ~~~~~~~~~
        For each matching composite SOP Instance, the C-MOVE performing user
        initiates a C-STORE sub-operation on a different Association than the
        C-MOVE. In this sub-operation the C-MOVE performer becomes the C-STORE
        invoker. The C-STORE performing DIMSE user may or may not be the C-MOVE
        invoking DIMSE user.

        Parameters
        ----------
        dataset : pydicom.dataset.Dataset
            The dataset containing the Attributes to match against.
        move_aet : str
            The AE title for the destination of the C-STORE operations performed
            by the C-MOVE performing DIMSE user.
        msg_id : int, optional
            The Message ID to use for the C-MOVE service.
        priority : int, optional
            The C-MOVE operation priority (if supported by the peer), one of:
                2 - Low (default)
                1 - High
                0 - Medium
        query_model : str, optional
            The Query/Retrieve Information Model to use, one of the following:
                'P' - Patient Root Information Model - MOVE (default)
                    1.2.840.10008.5.1.4.1.2.1.2
                'S' - Study Root Information Model - MOVE
                    1.2.840.10008.5.1.4.1.2.2.2
                'O' - Patient Study Only Information Model - MOVE
                    1.2.840.10008.5.1.4.1.2.3.2

        Yields
        ------
        status : int

        dataset : pydicom.dataset.Dataset
        """
        # Can't send a C-MOVE without an Association
        if not self.is_established:
            raise RuntimeError("The association with a peer SCP must be "
                               "established before sending a C-MOVE request")

        if query_model == "P":
            sop_class = PatientRootQueryRetrieveInformationModelMove()
        elif query_model == "S":
            sop_class = StudyRootQueryRetrieveInformationModelMove()
        elif query_model == "O":
            sop_class = PatientStudyOnlyQueryRetrieveInformationModelMove()
        else:
            raise ValueError("Association.send_c_move() query_model must "
                             "be one of ['P'|'S'|'O']")

        service_class = QueryRetrieveMoveServiceClass()

        # Determine the Presentation Context we are operating under
        #   and hence the transfer syntax to use for encoding `dataset`
        transfer_syntax = None
        for context in self.acse.context_manager.accepted:
            if sop_class.UID == context.AbstractSyntax:
                transfer_syntax = context.TransferSyntax[0]
                context_id = context.ID

        if transfer_syntax is None:
            LOGGER.error("No Presentation Context for: '%s'", sop_class.UID)
            LOGGER.error("Move SCU failed due to there being no valid "
                         "presentation context\n   for the current dataset")
            yield service_class.IdentifierDoesNotMatchSOPClass, None
            return

        # Build C-MOVE primitive
        primitive = C_MOVE()
        primitive.MessageID = msg_id
        primitive.AffectedSOPClassUID = sop_class.UID
        primitive.MoveDestination = move_aet
        primitive.Priority = priority
        primitive.Identifier = BytesIO(encode(dataset,
                                              transfer_syntax.is_implicit_VR,
                                              transfer_syntax.is_little_endian))

        LOGGER.info('Move SCU Request Identifiers:')
        LOGGER.info('')
        LOGGER.info('# DICOM Dataset')
        for elem in dataset:
            LOGGER.info(elem)
        LOGGER.info('')

        # Send C-MOVE primitive to peer
        self.dimse.send_msg(primitive, context_id)

        # Get the responses from peer
        ii = 1
        while True:
            time.sleep(0.001)

            rsp, context_id = self.dimse.receive_msg(wait=False)

            if rsp.__class__ == C_MOVE:
                status = service_class.code_to_status(rsp.Status)
                dataset = decode(rsp.Identifier,
                                 transfer_syntax.is_implicit_VR,
                                 transfer_syntax.is_little_endian)

                # If the Status is "Pending" then the processing of
                #   matches and suboperations is initiated or continuing
                if status.status_type == 'Pending':
                    remain = rsp.NumberOfRemainingSuboperations
                    complete = rsp.NumberOfCompletedSuboperations
                    failed = rsp.NumberOfFailedSuboperations
                    warning = rsp.NumberOfWarningSuboperations

                    # Pending Response
                    LOGGER.debug('')
                    LOGGER.info("Move Response: %s (Pending)", ii)
                    LOGGER.info("    Sub-Operations Remaining: %s, "
                                "Completed: %s, Failed: %s, Warning: %s",
                                remain, complete, failed, warning)
                    ii += 1

                    yield status, dataset

                # If the Status is "Success" then processing is complete
                # PS3.4 Section C.4.2.2
                # Success indicates all sub-ops were successfully completed
                #   interpreted as final response
                # Warning indicates one or more sub-ops were unsuccessful or
                #   had a status of warning, interpreted as final response
                # Failure indicates all sub-ops were unsuccessful
                #   intrepreted as final response
                elif status.status_type == "Success":
                    status = service_class.Success
                    dataset = None
                    break
                # All other possible responses
                elif status.status_type == "Failure":
                    LOGGER.debug('')
                    LOGGER.error('Move Response: %s (Failure)', ii)
                    LOGGER.error('    %s', status.description)
                    break
                elif status.status_type == "Cancel":
                    LOGGER.debug('')
                    LOGGER.info('Move Response: %s (Cancel)', ii)
                    LOGGER.info('    %s', status.description)
                    dataset = None
                    break
                elif status.status_type == "Warning":
                    LOGGER.debug('')
                    LOGGER.warning('Move Response: %s (Warning)', ii)
                    LOGGER.warning('    %s', status.description)

                    for elem in dataset:
                        LOGGER.warning('%s: %s', elem.name, elem.value)

                    break

        yield status, dataset

    def send_c_get(self, dataset, msg_id=1, priority=2, query_model='P'):
        """Send a C-GET request message to the peer AE.

        See PS3.4 Annex C - Query/Retrieve Service Class

        Parameters
        ----------
        dataset : pydicom.Dataset
            The DICOM dataset to containing the Key Attributes the peer AE
            should perform the match against
        msg_id : int, optional
            The message ID
        priority : int, optional
            The C-GET operation priority (if supported by the peer), one of:
                2 - Low (default)
                1 - High
                0 - Medium
        query_model : str, optional
            The Query/Retrieve Information Model to use, one of the following:
                'P' - Patient Root Information Model - GET
                    1.2.840.10008.5.1.4.1.2.1.3
                'S' - Study Root Information Model - GET
                    1.2.840.10008.5.1.4.1.2.2.3
                'O' - Patient Study Only Information Model - GET
                    1.2.840.10008.5.1.4.1.2.3.3

        Yields
        ------
        status : pynetdicom3.sop_class.Status
            The resulting status(es) from the C-GET operation
        dataset : pydicom.dataset.Dataset or None
            The resulting dataset(s) from the C-GET operation. Yields None if
            no valid Presentation Context.
        """
        # Can't send a C-GET without an Association
        if not self.is_established:
            raise RuntimeError("The association with a peer SCP must be "
                               "established before sending a C-GET request")

        if query_model == "P":
            # Four level hierarchy, patient, study, series, composite object
            sop_class = PatientRootQueryRetrieveInformationModelGet()
        elif query_model == "S":
            # Three level hierarchy, study, series, composite object
            sop_class = StudyRootQueryRetrieveInformationModelGet()
        elif query_model == "O":
            # Retired
            sop_class = PatientStudyOnlyQueryRetrieveInformationModelGet()
        else:
            raise ValueError("Association.send_c_get() query_model "
                             "must be one of ['P'|'S'|'O']")

        service_class = QueryRetrieveGetServiceClass()

        # Determine the Presentation Context we are operating under
        #   and hence the transfer syntax to use for encoding `dataset`
        transfer_syntax = None
        for context in self.acse.context_manager.accepted:
            if sop_class.UID == context.AbstractSyntax:
                transfer_syntax = context.TransferSyntax[0]
                context_id = context.ID

        if transfer_syntax is None:
            LOGGER.error("No Presentation Context for: '%s'", sop_class.UID)
            LOGGER.error("Get SCU failed due to there being no valid "
                         "presentation context for the current dataset")
            yield service_class.IdentifierDoesNotMatchSOPClass, None
            return


        # Build C-GET primitive
        primitive = C_GET()
        primitive.MessageID = msg_id
        primitive.AffectedSOPClassUID = sop_class.UID
        primitive.Priority = priority
        primitive.Identifier = \
            BytesIO(encode(dataset, transfer_syntax.is_implicit_VR,
                           transfer_syntax.is_little_endian))

        LOGGER.info('Get SCU Request Identifiers:')
        LOGGER.info('')
        LOGGER.info('# DICOM Dataset')
        for elem in dataset:
            LOGGER.info(elem)
        LOGGER.info('')

        # Send primitive to peer
        self.dimse.send_msg(primitive, context_id)

        ii = 1
        while True:
            rsp, context_id = self.dimse.receive_msg(wait=True)

            # Received a C-GET response
            if rsp.__class__ == C_GET:

                status = service_class.code_to_status(rsp.Status)
                dataset = decode(rsp.Identifier,
                                 transfer_syntax.is_implicit_VR,
                                 transfer_syntax.is_little_endian)

                # If the Status is "Pending" then the processing of
                #   matches and suboperations is initiated or continuing
                if status.status_type == 'Pending':
                    remain = rsp.NumberOfRemainingSuboperations
                    complete = rsp.NumberOfCompletedSuboperations
                    failed = rsp.NumberOfFailedSuboperations
                    warning = rsp.NumberOfWarningSuboperations

                    # Pending Response
                    LOGGER.debug('')
                    LOGGER.info("Find Response: %s (Pending)", ii)
                    LOGGER.info("    Sub-Operations Remaining: %s, "
                                "Completed: %s, Failed: %s, Warning: %s",
                                remain, complete, failed, warning)
                    ii += 1

                    yield status, dataset

                # If the Status is "Success" then processing is complete
                elif status.status_type == "Success":
                    status = service_class.Success
                    dataset = None
                    break

                # All other possible responses
                elif status.status_type == "Failure":
                    LOGGER.debug('')
                    LOGGER.error('Find Response: %s (Failure)', ii)
                    LOGGER.error('    %s', status.description)

                    # Print out the status information
                    for elem in dataset:
                        LOGGER.error('%s: %s', elem.name, elem.value)

                    break
                elif status.status_type == "Cancel":
                    LOGGER.debug('')
                    LOGGER.info('Find Response: %s (Cancel)', ii)
                    LOGGER.info('    %s', status.description)
                    dataset = None
                    break
                elif status.status_type == "Warning":
                    LOGGER.debug('')
                    LOGGER.warning('Find Response: %s (Warning)', ii)
                    LOGGER.warning('    %s', status.description)
                    dataset = None
                    break

            # Received a C-STORE request in response to the C-GET
            elif rsp.__class__ == C_STORE:

                c_store_rsp = C_STORE()
                c_store_rsp.MessageIDBeingRespondedTo = rsp.MessageID
                c_store_rsp.AffectedSOPInstanceUID = \
                                                rsp.AffectedSOPInstanceUID
                c_store_rsp.AffectedSOPClassUID = rsp.AffectedSOPClassUID

                ds = decode(rsp.DataSet,
                            transfer_syntax.is_implicit_VR,
                            transfer_syntax.is_little_endian)

                #  Callback for C-STORE SCP (user implemented)
                status = self.ae.on_c_store(ds)

                # Send C-STORE confirmation back to peer
                c_store_rsp.Status = int(status)
                self.dimse.send_msg(c_store_rsp, context_id)

        yield status, dataset

    def _send_c_cancel(self, msg_id):
        """Send a C-CANCEL-* request to the peer AE.

        See PS3.7 9.3.2.3

        Parameters
        ----------
        msg_id : int
            The message ID of the C-GET/MOVE/FIND operation we want to cancel.
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

    def send_n_get(self):
        """Send an N-GET request message to the peer AE."""
        '''
        service_class = QueryRetrieveGetServiceClass()

        # Determine the Presentation Context we are operating under
        #   and hence the transfer syntax to use for encoding `dataset`
        transfer_syntax = None

        for context in self.acse.context_manager.accepted:
            if sop_class.UID == context.AbstractSyntax:
                transfer_syntax = context.TransferSyntax[0]
                context_id = context.ID

        if transfer_syntax is None:
            LOGGER.error("No Presentation Context for: '%s'", sop_class.UID)
            LOGGER.error("Get SCU failed due to there being no valid "
                         "presentation context for the current dataset")
            return service_class.IdentifierDoesNotMatchSOPClass


        # Build N-GET primitive
        primitive = N_GET()
        primitive.MessageID = msg_id
        # The SOP Class for which Attribute Values are to be retrieved
        primitive.RequestedSOPClassUID = None
        # The SOP Instance for which Attribute Values are to be retrieved
        primitive.RequestedSOPInstanceUID = None
        # A set of Attribute identifiers, if omitted then all identifiers
        #   are assumed. The definitions of the Attributes are found
        #   in PS3.3
        if dataset is not None:
            primitive.AttributeIdentifierList = \
                    encode(dataset, transfer_syntax.is_implicit_VR,
                           transfer_syntax.is_little_endian)
            primitive.AttributeIdentifierList = \
                    BytesIO(primitive.AttributeIdentifierList)

        # Send primitive to peer
        self.dimse.send_msg(primitive, context_id)
        '''
        # Can't send an N-GET without an Association
        if not self.is_established:
            raise RuntimeError("The association with a peer SCP must be "
                               "established before sending an N-GET "
                               "request.")
        raise NotImplementedError

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
