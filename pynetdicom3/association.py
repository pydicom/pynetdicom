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
from pynetdicom3.dimse_primitives import (C_ECHO, C_MOVE, C_STORE, C_GET,
                                          C_FIND, C_CANCEL)
from pynetdicom3.dsutils import decode, encode
from pynetdicom3.dul import DULServiceProvider
from pynetdicom3.sop_class import (
    uid_to_sop_class,
    ModalityWorklistInformationFind,
    PatientRootQueryRetrieveInformationModelFind,
    StudyRootQueryRetrieveInformationModelFind,
    PatientStudyOnlyQueryRetrieveInformationModelFind,
    PatientRootQueryRetrieveInformationModelMove,
    StudyRootQueryRetrieveInformationModelMove,
    PatientStudyOnlyQueryRetrieveInformationModelMove,
    PatientRootQueryRetrieveInformationModelGet,
    StudyRootQueryRetrieveInformationModelGet,
    PatientStudyOnlyQueryRetrieveInformationModelGet)
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
        self.dul = DULServiceProvider(socket=client_socket,
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
        assoc_rq = self.dul.receive_pdu(wait=True, timeout=self.acse.acse_timeout)

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
        self.acse.rejected_contexts = self.acse.context_manager.rejected

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
                for context in self.acse.accepted_contexts:
                    if context.ID == msg_context_id:
                        sop_class.pcid = context.ID
                        sop_class.sopclass = context.AbstractSyntax
                        sop_class.transfersyntax = context.TransferSyntax[0]
                        sop_class.maxpdulength = self.peer_max_pdu
                        sop_class.DIMSE = self.dimse
                        sop_class.ACSE = self.acse
                        sop_class.AE = self.ae

                        # Run SOPClass in SCP mode
                        sop_class.SCP(msg)
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
            The message ID, must be between 0 and 65535, inclusive, (default
            1).

        Returns
        -------
        status : pydicom.dataset.Dataset
            If the peer timed out or sent an invalid response then returns an
            empty Dataset. If a valid response was received from the peer then
            returns a Dataset containing at least a (0000,0900) Status element,
            and, depending on the returned Status value, may optionally contain
            additional elements (see DICOM Standard Part 7, Annex C).

            The DICOM Standard Part 7, Table 9.3-13 indicates that the Status
            value of a C-ECHO response "shall have a value of Success". However
            Section 9.1.5.1.4 indicates it may have any of the following
            values:

            Success

              * 0x0000 - Success

            Failure

              * 0x0122 - SOP class not supported
              * 0x0210 - Duplicate invocation
              * 0x0211 - Unrecognised operation
              * 0x0212 - Mistyped argument

            As the actual status depends on the peer SCP, it shouldn't be
            assumed that it will be one of these.

        Raises
        ------
        RuntimeError
            If called without an association to a peer SCP.
        ValueError
            If no accepted Presentation Context for 'Verification SOP Class'.

        See Also
        --------
        applicationentity.ApplicationEntity.on_c_echo
        dimse_primitives.C_ECHO
        sop_class.VerificationServiceClass

        References
        ----------
        DICOM Standard Part 4, Annex A
        DICOM Standard Part 7, Sections 9.1.5, 9.3.5 and Annex C

        Examples
        --------
        >>> assoc = ae.associate(addr, port)
        >>> if assoc.is_established:
        >>>     status = assoc.send_c_echo()
        >>>     if status:
        >>>         print('C-ECHO Response: 0x{0:04x}'.format(status.Status))
        >>>     assoc.release()
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
            if uid == context.AbstractSyntax:
                context_id = context.ID

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
            The message ID, must be between 0 and 65535, inclusive, (default
            1).
        priority : int, optional
            The C-STORE operation priority (may not be supported by the peer),
            one of:

            - 0 - Medium
            - 1 - High
            - 2 - Low (default)

        originator_aet : str, optional
            The AE title of the peer that invoked the C-MOVE operation for
            which this C-STORE sub-operation is being performed (default None).
        originator_id : int, optional
            The Message ID of the C-MOVE request primitive from which this
            C-STORE sub-operation is being performed (default None).

        Returns
        -------
        status : pydicom.dataset.Dataset
            If the peer timed out or sent an invalid response then returns an
            empty Dataset. If a valid response was received from the peer then
            returns a Dataset containing at least a (0000,0900) Status element,
            and, depending on the returned Status value, may optionally contain
            additional elements (see DICOM Standard Part 7, Annex C).

            The status for the requested C-STORE operation should be one of the
            following, but as the value depends on the peer SCP this can't be
            assumed:

            General C-STORE (DICOM Standard Part 7, 9.1.1.1.9 and Annex C):

            - Success

              * 0x0000 - Success

            - Failure

              * 0x0117 - Invalid SOP instance
              * 0x0122 - SOP class not supported
              * 0x0124 - Not authorised
              * 0x0210 - Duplicate invocation
              * 0x0211 - Unrecognised operation
              * 0x0212 - Mistyped argument

            Storage Service Class specific (DICOM Standard Part 4, Annex
            B.2.3):

            - Failure

              * 0xA700 to 0xA7FF - Out of resources
              * 0xA900 to 0xA9FF - Data set does not match SOP class
              * 0xC000 to 0xCFFF - Cannot understand

            - Warning

              * 0xB000 - Coercion of data elements
              * 0xB006 - Element discarded
              * 0xB007 - Data set does not match SOP class

            Non-Patient Object Service Class specific (DICOM Standard Part 4,
            Annex GG.4.2)

            - Failure

              * 0xA700 - Out of resources
              * 0xA900 - Data set does not match SOP class
              * 0xC000 - Cannot understand

        Raises
        ------
        RuntimeError
            If send_c_store is called with no established association.
        AttributeError
            If `dataset` is missing (0008,0016) 'SOP Class UID' or
            (0008,0018) 'SOP Instance UID' elements.
        ValueError
            If no accepted Presentation Context for `dataset` exists or if
            unable to encode the `dataset`.

        See Also
        --------
        applicationentity.ApplicationEntity.on_c_store
        dimse_primitives.C_STORE
        sop_class.StorageServiceClass

        References
        ----------
        DICOM Standard Part 4, Annexes B, GG
        DICOM Standard Part 7, Sections 9.1.1, 9.3.1 and Annex C

        Examples
        --------
        >>> ds = read_file('file-in.dcm')
        >>> assoc = ae.associate(addr, port)
        >>> if assoc.is_established:
        >>>     status = assoc.send_c_store(ds)
        >>>     if status:
        >>>         print('C-STORE Response: 0x{0:04x}'.format(status.Status))
        >>>     assoc.release()
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
                if dataset.SOPClassUID == context.AbstractSyntax:
                    transfer_syntax = context.TransferSyntax[0]
                    context_id = context.ID
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

    def send_c_find(self, dataset, msg_id=1, priority=2, query_model='W'):
        """Send a C-FIND request to the peer AE.

        Yields (status, identifier) pairs.

        Parameters
        ----------
        dataset : pydicom.dataset.Dataset
            The C-FIND request's Identifier dataset. The exact requirements for
            the Identifier dataset are Service Class specific (see the DICOM
            Standard, Part 4).
        msg_id : int, optional
            The message ID, must be between 0 and 65535, inclusive, (default
            1).
        priority : int, optional
            The C-FIND operation priority (may not be supported by the peer),
            one of:

            - 0 - Medium
            - 1 - High
            - 2 - Low (default)

        query_model : str, optional
            The Query/Retrieve Information Model to use, one of the following:

            - 'W' - Modality Worklist Information - FIND (default)
              1.2.840.10008.5.1.4.31
            - 'P' - Patient Root Information Model - FIND
              1.2.840.10008.5.1.4.1.2.1.1
            - 'S' - Study Root Information Model - FIND
              1.2.840.10008.5.1.4.1.2.2.1
            - 'O' - Patient Study Only Information Model - FIND
              1.2.840.10008.5.1.4.1.2.3.1

        Yields
        ------
        status : pydicom.dataset.Dataset
            If the peer timed out or sent an invalid response then yields an
            empty Dataset. If a response was received from the peer then
            yields a Dataset containing at least a (0000,0900) Status element,
            and depending on the returned Status value, may optionally contain
            additional elements (see PS3.7 9.1.2.1.5 and Annex C).

            The status for the requested C-FIND operation should be one of the
            following Status objects/codes, but as the returned value depends
            on the peer this can't be assumed:

            General C-FIND (PS3.7 9.1.2.1.5 and Annex C)

            - Cancel

              * 0xFE00 - Matching terminated due to Cancel request

            - Success

              * 0x0000 - Matching is complete: no final Identifier is supplied

            - Failure

              * 0x0122 - SOP class not supported

            Query/Retrieve Service Class Specific (PS3.4 Annex C.4.1):

            - Failure

              * 0xA700 - Out of resources
              * 0xA900 - Identifier does not match SOP Class
              * 0xC000 to 0xCFFF - Unable to process

            - Pending

              * 0xFF00 - Matches are continuing: current match is supplied and
                any Optional Keys were supported in the same manner as Required
                Keys
              * 0xFF01 - Matches are continuing: warning that one or more
                Optional Keys were not supported for existence and/or matching
                for this Identifier)

        identifier : pydicom.dataset.Dataset or None
            If the status is 'Pending' then the C-FIND response's Identifier
            dataset. If the status is not 'Pending' this will be None. The
            exact contents of the response Identifier are Service Class
            specific (see the DICOM Standard, Part 4).

        Raises
        ------
        RuntimeError
            If send_c_find is called with no established association.
        ValueError
            If no accepted Presentation Context for `dataset` exists or if
            unable to encode the Identifier `dataset`.

        See Also
        --------
        applicationentity.ApplicationEntity.on_c_find
        dimse_primitives.C_FIND
        sop_class.QueryRetrieveFindServiceClass

        References
        ----------
        DICOM Standard Part 4, Annex C
        DICOM Standard Part 7, Sections 9.1.2, 9.3.2 and Annex C
        """
        # Can't send a C-FIND without an Association
        if not self.is_established:
            raise RuntimeError("The association with a peer SCP must be "
                               "established before sending a C-FIND request")

        if query_model == 'W':
            sop_class = ModalityWorklistInformationFind()
        elif query_model == "P":
            sop_class = PatientRootQueryRetrieveInformationModelFind()
        elif query_model == "S":
            sop_class = StudyRootQueryRetrieveInformationModelFind()
        elif query_model == "O":
            sop_class = PatientStudyOnlyQueryRetrieveInformationModelFind()
        else:
            raise ValueError("Association.send_c_find - 'query_model' "
                             "must be 'W', 'P', 'S' or 'O'")

        # Determine the Presentation Context we are operating under
        #   and hence the transfer syntax to use for encoding `dataset`
        transfer_syntax = None
        for context in self.acse.context_manager.accepted:
            if sop_class.UID == context.AbstractSyntax:
                transfer_syntax = context.TransferSyntax[0]
                context_id = context.ID

        if transfer_syntax is None:
            LOGGER.error("No accepted Presentation Context for: '%s'",
                         sop_class.UID)
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
        req.AffectedSOPClassUID = sop_class.UID
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

        Yields (status, identifier) pairs.

        The ApplicationEntity.on_c_store callback should be implemented prior
        to calling send_c_move as the peer may either return any matches
        via a C-STORE sub-operation over the current association or request a
        new association over which to return any matches.

        Parameters
        ----------
        dataset : pydicom.dataset.Dataset
            The C-MOVE request's Identifier dataset. The exact requirements for
            the Identifier dataset are Service Class specific (see the DICOM
            Standard, Part 4).
        move_aet : str
            The AE title of the destination for the C-STORE sub-operations
            performed by the peer.
        msg_id : int, optional
            The message ID, must be between 0 and 65535, inclusive, (default
            1).
        priority : int, optional
            The C-MOVE operation priority (if supported by the peer), one of:

            - 0 - Medium
            - 1 - High
            - 2 - Low (default)

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
        status : pydicom.dataset.Dataset
            If the peer timed out or sent an invalid response then yields an
            empty Dataset. If a response was received from the peer then
            yields a Dataset containing at least a (0000,0900) Status element,
            and depending on the returned Status value, may optionally contain
            additional elements (see DICOM Standard Part 7, Section 9.1.4 and
            Annex C).

            The status for the requested C-MOVE operation should be one of the
            following Status objects/codes, but as the returned value depends
            on the peer this can't be assumed:

            General C-MOVE (DICOM Standard Part 7, 9.1.4.1.7 and Annex C)

            - Cancel

              * 0xFE00 - Sub-operations terminated due to Cancel indication

            - Success

              * 0x0000 - Sub-operations complete: no failures

            - Failure

              * 0x0122 - SOP class not supported

            Query/Retrieve Service Class Specific (DICOM Standard Part 4, Annex
            C):

            - Failure

              * 0xA701 - Out of resources: unable to calculate number of
                matches
              * 0xA702 - Out of resources: unable to perform sub-operations
              * 0xA801 - Move destination unknown
              * 0xA900 - Identifier does not match SOP Class
              * 0xC000 to 0xCFFF - Unable to process

            - Pending

              * 0xFF00 - Sub-operations are continuing

            - Warning

              * 0xB000 - Sub-operations complete: one or more failures

        identifier : pydicom.dataset.Dataset or None
            If the status is 'Pending' or 'Success' then yields None. If the
            status is 'Warning', 'Failure' or 'Cancel' then yields a Dataset
            which should contain an (0008,0058) 'Failed SOP Instance UID List'
            element, however this is not guaranteed and may return an empty
            Dataset.

        See Also
        --------
        applicationentity.ApplicationEntity.on_c_move
        applicationentity.ApplicationEntity.on_c_store
        dimse_primitives.C_MOVE
        sop_class.QueryRetrieveMoveServiceClass

        References
        ----------
        DICOM Standard Part 4, Annex C
        DICOM Standard Part 7, Sections 9.1.4, 9.3.4 and Annex C
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
            raise ValueError("Association.send_c_move - 'query_model' must "
                             "be 'P', 'S' or 'O'")

        # Determine the Presentation Context we are operating under
        #   and hence the transfer syntax to use for encoding `dataset`
        transfer_syntax = None
        for context in self.acse.context_manager.accepted:
            if sop_class.UID == context.AbstractSyntax:
                transfer_syntax = context.TransferSyntax[0]
                context_id = context.ID

        if transfer_syntax is None:
            LOGGER.error("No accepted Presentation Context for: '%s'",
                         sop_class.UID)
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
        req.AffectedSOPClassUID = sop_class.UID
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

        Yields (status, identifier) pairs.

        The ApplicationEntity.on_c_store callback should be implemented prior
        to calling send_c_get as the peer will return any matches via a C-STORE
        sub-operation over the current association.

        Parameters
        ----------
        dataset : pydicom.dataset.Dataset
            The C-GET request's Identifier dataset. The exact requirements for
            the Identifier dataset are Service Class specific (see the DICOM
            Standard, Part 4).
        msg_id : int, optional
            The message ID, must be between 0 and 65535, inclusive, (default
            1).
        priority : int, optional
            The C-GET operation priority (may not be supported by the peer),
            one of:

            - 0 - Medium
            - 1 - High
            - 2 - Low (default)

        query_model : str, optional
            The Query/Retrieve Information Model to use, one of the following:

            - 'P' - Patient Root Information Model - GET
              1.2.840.10008.5.1.4.1.2.1.3 (default)
            - 'S' - Study Root Information Model - GET
              1.2.840.10008.5.1.4.1.2.2.3
            - 'O' - Patient Study Only Information Model - GET
              1.2.840.10008.5.1.4.1.2.3.3

        Yields
        ------
        status : pydicom.dataset.Dataset
            If the peer timed out or sent an invalid response then yields an
            empty Dataset. If a response was received from the peer then yields
            a Dataset containing at least a (0000,0900) Status element, and
            depending on the returned Status value may optionally contain
            additional elements (see DICOM Standard Part 7, Section 9.1.2.1.5
            and Annex C).

            The status for the requested C-GET operation should be one of the
            following Status codes, but as the returned value depends on the
            peer this can't be assumed:

            General C-GET (DICOM Standard Part 7, Section 9.1.3 and Annex C)

            - Success

              * 0x0000 - Sub-operations complete: no failures or warnings

            - Failure

              * 0x0122 - SOP class not supported
              * 0x0124 - Not authorised
              * 0x0210 - Duplicate invocation
              * 0x0211 - Unrecognised operation
              * 0x0212 - Mistyped argument

            Query/Retrieve Service Class Specific (DICOM Standard Part 4, Annex
            C.4.3):

            - Pending

              * 0xFF00 - Sub-operations are continuing

            - Cancel

              * 0xFE00 - Sub-operations terminated due to Cancel indication

            - Failure

              *  0xA701 - Out of resources: unable to calculate number of
                 matches
              *  0xA702 - Out of resources: unable to perform sub-operations
              *  0xA900 - Identifier does not match SOP class
              *  0xC000 to 0xCFFF - Unable to process

            - Warning

              *  0xB000 - Sub-operations completed: one or more failures or
                 warnings

        identifier : pydicom.dataset.Dataset or None
            If the status is 'Pending' or 'Success' then yields None. If the
            status is 'Warning', 'Failure' or 'Cancel' then yields a Dataset
            which should contain an (0008,0058) 'Failed SOP Instance UID List'
            element, however this is not guaranteed and may return an empty
            Dataset.

        Raises
        ------
        RuntimeError
            If send_c_get is called with no established association.
        ValueError
            If no accepted Presentation Context for `dataset` exists or if
            unable to encode the Identifier `dataset`.

        See Also
        --------
        applicationentity.ApplicationEntity.on_c_get
        applicationentity.ApplicationEntity.on_c_store
        sop_class.QueryRetrieveGetServiceClass
        dimse_primitives.C_GET

        References
        ----------
        DICOM Standard Part 4, Annex C
        DICOM Standard Part 7, Sections 9.1.3, 9.3.3 and Annex C
        """
        # Can't send a C-GET without an Association
        if not self.is_established:
            raise RuntimeError("The association with a peer SCP must be "
                               "established before sending a C-GET request")

        if query_model == "P":
            sop_class = PatientRootQueryRetrieveInformationModelGet()
        elif query_model == "S":
            sop_class = StudyRootQueryRetrieveInformationModelGet()
        elif query_model == "O":
            sop_class = PatientStudyOnlyQueryRetrieveInformationModelGet()
        else:
            raise ValueError("Association.send_c_get() query_model "
                             "must be 'P', 'S' or 'O']")

        # Determine the Presentation Context we are operating under
        #   and hence the transfer syntax to use for encoding `dataset`
        transfer_syntax = None
        for context in self.acse.context_manager.accepted:
            if sop_class.UID == context.AbstractSyntax:
                transfer_syntax = context.TransferSyntax[0]
                context_id = context.ID

        if transfer_syntax is None:
            LOGGER.error("No accepted Presentation Context for: '%s'",
                         sop_class.UID)
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
        req.AffectedSOPClassUID = sop_class.UID
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
            if req.AffectedSOPClassUID == context.AbstractSyntax:
                transfer_syntax = context.TransferSyntax[0]
                context_id = context.ID

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
            self.dimse.send_msg(rsp, context_id)
            return

        #  Attempt to run the ApplicationEntity's on_c_store callback
        try:
            status = self.ae.on_c_store(ds)
        except Exception as ex:
            LOGGER.error("Exception in the "
                         "ApplicationEntity.on_c_store() callback")
            LOGGER.exception(ex)
            rsp.Status = 0xC211
            self.dimse.send_msg(rsp, context_id)
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
        self.dimse.send_msg(rsp, context_id)

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

    def send_n_get(self):
        """Send an N-GET request message to the peer AE."""
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
