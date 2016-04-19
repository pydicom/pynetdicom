
import logging
import os
import platform
import select
import socket
import struct
import sys
import threading
import time
from weakref import proxy

from pydicom.uid import ExplicitVRLittleEndian, ImplicitVRLittleEndian, \
    ExplicitVRBigEndian, UID

from pynetdicom.ACSEprovider import ACSEServiceProvider
from pynetdicom.DIMSEprovider import DIMSEServiceProvider
from pynetdicom.DIMSEparameters import *
from pynetdicom.PDU import *
from pynetdicom.DULparameters import *
from pynetdicom.DULprovider import DULServiceProvider
from pynetdicom.SOPclass import *
from pynetdicom.utils import PresentationContextManager, correct_ambiguous_vr


logger = logging.getLogger('pynetdicom.assoc')


class Association(threading.Thread):
    """
    Manages Associations with peer AEs. The actual low level work done for 
    Associations is performed by pynetdicom.ACSEprovider.ACSEServiceProvider
    
    When the local AE is acting as an SCP, initialise the Association using 
    the socket to listen on for incoming Association requests. When the local 
    AE is acting as an SCU, initialise the Association with the details of the 
    peer AE
    
    When AE is acting as an SCP:
        assoc = Association(self, client_socket, max_pdu)
        
    When AE is acting as an SCU:
        assoc = Association(self, 
                            peer_ae, 
                            acse_timeout,
                            dimse_timeout,
                            max_pdu,
                            ext_neg)
    
    Parameters
    ----------
    local_ae - pynetdicom.applicationentity.ApplicationEntity
        The local AE instance
    client_socket - socket.socket, optional
        If the local AE is acting as an SCP, this is the listen socket for 
        incoming connection requests
    peer_ae - dict, optional
        If the local AE is acting as an SCU this is the AE title, host and port 
        of the peer AE that we want to Associate with
    acse_timeout - int, optional
        The maximum amount of time to wait for a reply during association, in
        seconds. A value of 0 means no timeout (default: 30)
    dimse_timeout - int, optional
        The maximum amount of time to wait for a reply during DIMSE, in
        seconds. A value of 0 means no timeout (default: 0)
    max_pdu - int, optional
        The maximum PDU receive size in bytes for the association. A value of 0
        means no maximum size (default: 16382 bytes). 
    ext_neg - list of extended negotiation parameters objects, optional
        If the association requires an extended negotiation then `ext_neg` is
        a list containing the negotiation objects (default: None)

    Attributes
    ----------
    acse - ACSEServiceProvider
        The Association Control Service Element provider
    ae - pynetdicom.applicationentity.ApplicationEntity
        The local AE
    dimse - DIMSEServiceProvider
        The DICOM Message Service Element provider
    dul - DUL
        The DICOM Upper Layer service provider instance
    is_aborted - bool
        True if the association has been aborted
    is_established - bool
        True if the association has been established
    is_released - bool
        True if the association has been released
    mode - str
        Whether the local AE is acting as the Association 'Requestor' or 
        'Acceptor' (i.e. SCU or SCP)
    peer_ae - dict
        The peer Application Entity details (Port, Address, Title)
    client_socket - socket.socket
        The socket to use for connections with the peer AE
    scu_supported_sop
        A list of the supported SOP classes when acting as an SCU
    scp_supported_sop
        A list of the supported SOP classes when acting as an SCP
    """
    def __init__(self, local_ae, 
                       client_socket=None, 
                       peer_ae=None, 
                       acse_timeout=30,
                       dimse_timeout=0,
                       max_pdu=16382,
                       ext_neg=None):
        
        # Why is the AE in charge of supplying the client socket?
        #   Hmm, perhaps because we can have multiple connections on the same
        #       listen port. Does that even work? Probably needs testing
        #   As SCP: supply port number to listen on (listen_port !=None)
        #   As SCU: supply addr/port to make connection on (peer_ae != None)
        if [client_socket, peer_ae] == [None, None]:
            raise ValueError("Association must be initialised with either "
                                "the client_socket or peer_ae parameters")
        
        if client_socket and peer_ae:
            raise ValueError("Association must be initialised with either "
                                "client_socket or peer_ae parameter not both")
        
        # Received a connection from a peer AE
        if client_socket:
            self.mode = 'Acceptor'
        
        # Initiated a connection to a peer AE
        if peer_ae:
            self.mode = 'Requestor'
        
        # The socket.socket used for connections
        self.client_socket = client_socket
        
        # The parent AE object
        self.ae = local_ae

        # Why do we instantiate the DUL provider with a socket when acting
        #   as an SCU?
        # Q. Why do we need to feed the DUL an ACSE timeout? 
        # A. ARTIM timer
        self.dul = DULServiceProvider(client_socket,
                                      dul_timeout=self.ae.network_timeout,
                                      acse_timeout=acse_timeout,
                                      local_ae=local_ae,
                                      assoc=self)
        
        # Dict containing the peer AE title, address and port
        self.peer_ae = peer_ae
        
        # Lists of pynetdicom.utils.PresentationContext items that the local
        #   AE supports when acting as an SCU and SCP
        self.scp_supported_sop = []
        self.scu_supported_sop = []
        
        # Status attributes
        self.is_established = False
        self.is_refused = False
        self.is_aborted = False
        
        # Timeouts for the DIMSE and ACSE service providers
        self.dimse_timeout = dimse_timeout
        self.acse_timeout = acse_timeout
        
        # Maximum PDU sizes (in bytes) for the local and peer AE
        self.local_max_pdu = max_pdu
        self.peer_max_pdu = None
        
        # A list of extended negotiation objects
        self.ext_neg = ext_neg
        
        # Kills the thread loop in run()
        self._Kill = False
        
        # Thread setup
        threading.Thread.__init__(self)
        self.daemon = True

        # Start the thread
        self.start()

    def kill(self):
        """
        Kill the main association thread loop, first checking that the DUL has 
        been stopped
        """
        self._Kill = True
        self.is_established = False
        while not self.dul.Stop():
            time.sleep(0.001)

    def release(self):
        """
        Direct the ACSE to issue an A-RELEASE request primitive to the DUL 
        provider
        """
        # A-RELEASE response primitive
        response = self.acse.Release()
        self.kill()

    def abort(self):
        """
        Direct the ACSE to issue an A-ABORT request primitive to the DUL
        provider
        
        DUL service user association abort. Always gives the source as the 
        DUL service user and sets the abort reason to 0x00 (not significant)
        
        See PS3.8, 7.3-4 and 9.3.8.
        """
        self.acse.Abort(source=0x00, reason=0x00)
        self.kill()

    def run(self):
        """
        The main Association thread
        """
        # Set new ACSE and DIMSE providers
        self.acse = ACSEServiceProvider(self, self.dul, self.acse_timeout)
        self.dimse = DIMSEServiceProvider(self.dul, self.dimse_timeout)
        
        # When the AE is acting as an SCP (Association Acceptor)
        if self.mode == 'Acceptor':
            # needed because of some thread-related problem. To investigate.
            time.sleep(0.1)
            
            # Get A-ASSOCIATE request primitive from the DICOM UL
            assoc_rq = self.dul.Receive(Wait=True)
            
            if assoc_rq is None:
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
            if self.ae.require_calling_aet != '':
                if self.ae.require_calling_aet != assoc_rq.CallingAETitle:
                    reject_assoc_rsd = [(0x01, 0x01, 0x03)]

            # Called AE Title not recognised
            if self.ae.require_called_aet != '':
                if self.AE.require_called_aet != assoc_rq.CalledAETitle:
                    reject_assoc_rsd = [(0x01, 0x01, 0x07)]

            # DUL Presentation Related Rejections
            #
            # Maximum number of associations reached (local-limit-exceeded)
            if len(self.ae.active_associations) > self.ae.maximum_associations:
                reject_assoc_rsd = [(0x02, 0x03, 0x02)]

            for (result, src, diag) in reject_assoc_rsd:
                assoc_rj = self.acse.Reject(assoc_rq, result, src, diag)
                self.debug_association_rejected(assoc_rj)
                self.ae.on_association_rejected(assoc_rj)
                self.kill()
                return
            
            self.acse.context_manager = PresentationContextManager()
            self.acse.context_manager.requestor_contexts = \
                                    assoc_rq.PresentationContextDefinitionList
            self.acse.context_manager.acceptor_contexts = \
                                    self.ae.presentation_contexts_scp
            
            self.acse.presentation_contexts_accepted = \
                                    self.acse.context_manager.accepted
            
            # Set maximum PDU send length
            self.peer_max_pdu = assoc_rq.UserInformationItem[0].MaximumLengthReceived
            
            # Set maximum PDU receive length
            assoc_rq.UserInformationItem[0].MaximumLengthReceived = \
                                                        self.local_max_pdu
            
            # Issue the A-ASSOCIATE indication (accept) primitive using the ACSE
            assoc_ac = self.acse.Accept(assoc_rq)
            
            # Callbacks/Logging
            self.debug_association_accepted(assoc_ac)
            self.ae.on_association_accepted(assoc_ac)
            
            if assoc_ac is None:
                self.kill()
                return
            
            # No valid presentation contexts, abort the association
            if self.acse.presentation_contexts_accepted == []:
                self.acse.Abort(0x02, 0x00)
                self.kill()
                return
            
            # Assocation established OK
            self.is_established = True
            
            # Main SCP run loop 
            #   1. Checks for incoming DIMSE messages
            #       If DIMSE message then run corresponding service class' SCP
            #       method
            #   2. Checks for peer A-RELEASE request primitive
            #       If present then kill thread
            #   3. Checks for peer A-ABORT request primitive
            #       If present then kill thread
            #   4. Checks DUL provider still running
            #       If not then kill thread
            #   5. Checks DUL idle timeout
            #       If timed out then kill thread
            while not self._Kill:
                time.sleep(0.001)
                
                # Check with the DIMSE provider for incoming messages
                #   all messages should be a DIMSEMessage subclass
                msg, msg_context_id = self.dimse.Receive(False, self.dimse_timeout)
                
                # DIMSE message received
                if msg:
                    # Convert the message's affected SOP class to a UID
                    uid = msg.AffectedSOPClassUID

                    # Use the UID to create a new SOP Class instance of the
                    #   corresponding value
                    try:
                        sop_class = UID2SOPClass(uid.value)()
                    except:
                        sop_class = UID2SOPClass(uid)()
                    
                    # Check that the SOP Class is supported by the AE
                    matching_context = False
                    for context in self.acse.presentation_contexts_accepted:
                        if context.ID == msg_context_id:
                            # New method - what is this even used for?
                            sop_class.presentation_context = context
                            
                            # Old method
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
        
        # If the local AE initiated the Association
        elif self.mode == 'Requestor':
            
            if self.ae.presentation_contexts_scu == []:
                logger.error("No presentation contexts set for the SCU")
                self.kill()
                return
            
            # Build role extended negotiation - needs updating
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
            is_accepted, assoc_rsp = self.acse.Request(
                                        local_ae, 
                                        self.peer_ae,
                                        self.local_max_pdu,
                                        self.ae.presentation_contexts_scu,
                                        userspdu=self.ext_neg)

            # Association was accepted or rejected
            if isinstance(assoc_rsp, A_ASSOCIATE_ServiceParameters):
                # Association was accepted
                if is_accepted:
                    self.debug_association_accepted(assoc_rsp)
                    self.ae.on_association_accepted(assoc_rsp)
                    
                    # No acceptable presentation contexts
                    if self.acse.presentation_contexts_accepted == []:
                        logger.error("No Acceptable Presentation Contexts")
                        self.acse.Abort(0x02, 0x00)
                        self.kill()
                        return
                    
                    # Build supported SOP Classes for the Association
                    self.scu_supported_sop = []
                    for context in self.acse.presentation_contexts_accepted:
                        self.scu_supported_sop.append(
                                       (context.ID,
                                        UID2SOPClass(context.AbstractSyntax), 
                                        context.TransferSyntax[0]))

                    # Assocation established OK
                    self.is_established = True
                    
                    # This seems like it should be event driven rather than
                    #   driven by a loop
                    #
                    # Listen for further messages from the peer
                    while not self._Kill:
                        time.sleep(0.001)
                        
                        # Check for release request
                        if self.acse.CheckRelease():
                            # Callback trigger
                            self.ae.on_association_released()
                            self.debug_association_released()
                            self.kill()
                            return

                        # Check for abort
                        if self.acse.CheckAbort():
                            # Callback trigger
                            self.ae.on_association_aborted()
                            self.debug_association_aborted()
                            self.kill()
                            return
                            
                        # Check if the DULServiceProvider thread is 
                        #   still running. DUL.is_alive() is inherited from 
                        #   threading.thread
                        if not self.dul.isAlive():
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

                    self.is_refused = True
                    self.dul.Kill()
                    return
            
            # Association was aborted by peer
            elif isinstance(assoc_rsp, A_ABORT_ServiceParameters):
                self.ae.on_association_aborted(assoc_rsp)
                self.debug_association_aborted(assoc_rsp)
                
                self.is_aborted = True
                self.dul.Kill()
                return
            
            # Association was aborted by DUL provider
            elif isinstance(assoc_rsp, A_P_ABORT_ServiceParameters):
                self.is_aborted = True
                self.dul.Kill()
                return
            
            # Association failed for any other reason (No peer, etc)
            else:
                self.dul.Kill()
                return


    # DIMSE-C services provided by the Association
    def send_c_echo(self, msg_id=1):
        """
        Send a C-ECHO message to the peer AE to verify end-to-end communication
        
        Parameters
        ----------
        msg_id - int, optional
            The message ID to use (default: 1)

        Returns
        -------
        status : pynetdicom.SOPclass.Status or None
            Returns None if no valid presentation context or no response
            from the peer, Success (0x0000) otherwise.
        """
        if self.is_established:
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
                logger.error("No Presentation Context for: '%s'" %uid)
                return None
            
            # Build C-STORE request primitive
            primitive = C_ECHO_ServiceParameters()
            primitive.MessageID = msg_id
            primitive.AffectedSOPClassUID = uid

            self.dimse.Send(primitive, context_id, self.acse.MaxPDULength)

            # If Association is Aborted before we receive the response
            #   then we hang here
            rsp, _ = self.dimse.Receive(True, self.dimse_timeout)
            
            if rsp is None:
                return None
            
            return service_class.Code2Status(rsp.Status)

        else:
            raise RuntimeError("The association with a peer SCP must be "
                "established before sending a C-ECHO request")

    def send_c_store(self, dataset, msg_id=1, priority=2):
        """
        Send a C-STORE request message to the peer AE Storage SCP
        
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
        dataset - pydicom.Dataset
            The DICOM dataset to send to the peer
        msg_id - int, optional
            The message ID (default: 1)
        priority : int, optional
            The C-STORE operation priority (if supported by the peer), one of:
                2 - Low (default)
                1 - High
                0 - Medium

        Returns
        -------
        status : pynetdicom.SOPclass.Status or None
            The status for the requested C-STORE operation (see PS3.4 Annex 
            B.2.3), should be one of the following Status objects:
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
            response
        """
        if self.is_established:
            # Service Class - used to determine Status
            service_class = StorageServiceClass()
            
            # Determine the Presentation Context we are operating under
            #   and hence the transfer syntax to use for encoding `dataset`
            transfer_syntax = None
            for context in self.acse.context_manager.accepted:
                if dataset.SOPClassUID == context.AbstractSyntax:
                    transfer_syntax = context.TransferSyntax[0]
                    context_id = context.ID
                    
            if transfer_syntax is None:
                logger.error("No Presentation Context for: '%s'" 
                                                    %dataset.SOPClassUID)
                logger.error("Store SCU failed due to there being no valid "
                        "presentation context for the current dataset")
                return service_class.CannotUnderstand
            
            # Set the correct VR for ambiguous elements
            dataset = correct_ambiguous_vr(dataset, transfer_syntax)
            
            # Build C-STORE request primitive
            primitive = C_STORE_ServiceParameters()
            primitive.MessageID = msg_id
            primitive.AffectedSOPClassUID = dataset.SOPClassUID
            primitive.AffectedSOPInstanceUID = dataset.SOPInstanceUID
            
            # Message priority
            if priority in [0x0000, 0x0001, 0x0002]:
                primitive.Priority = priority
            else:
                logger.warning("C-STORE SCU: Invalid priority value "
                                                            "'%s'" %priority)
                primitive.Priorty = 0x0000
            
            # Encode the dataset using the agreed transfer syntax
            primitive.DataSet = encode(dataset,
                                       transfer_syntax.is_implicit_VR,
                                       transfer_syntax.is_little_endian)
            
            if primitive.DataSet is not None:
                primitive.DataSet = BytesIO(primitive.DataSet)
            
            # If we failed to encode our dataset
            else:
                return service_class.CannotUnderstand

            # Send C-STORE request primitive to DIMSE
            self.dimse.Send(primitive, context_id, self.acse.MaxPDULength)

            # Wait for C-STORE response primitive
            #   returns a C_STORE_ServiceParameters primitive
            rsp, _ = self.dimse.Receive(True, self.dimse_timeout)
            
            status = None
            if rsp is not None:
                status = service_class.Code2Status(rsp.Status)

            return status

        else:
            raise RuntimeError("The association with a peer SCP must be "
                    "established before sending a C-STORE request")

    def send_c_find(self, dataset, msg_id=1, priority=2, query_model='W'):
        """
        Send a C-FIND request message to the peer AE
        
        See PS3.4 Annex C - Query/Retrieve Service Class

        Parameters
        ----------
        dataset : pydicom.Dataset
            The DICOM dataset to containing the Key Attributes the peer AE 
            should perform the match against
        msg_id : int, optional
            The message ID
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
        status : pynetdicom.SOPclass.Status
            The resulting status(es) from the C-FIND operation
        dataset : pydicom.dataset.Dataset
            The resulting dataset(s) from the C-FIND operation
        """
        if self.is_established:
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
                raise ValueError("Association::send_c_find() query_model "
                    "must be one of ['W'|'P'|'S'|'O']")
            
            # Determine the Presentation Context we are operating under
            #   and hence the transfer syntax to use for encoding `dataset`
            transfer_syntax = None
            for context in self.acse.context_manager.accepted:
                if sop_class.UID == context.AbstractSyntax:
                    transfer_syntax = context.TransferSyntax[0]
                    context_id = context.ID
                    
            if transfer_syntax is None:
                logger.error("No Presentation Context for: '%s'" 
                                                    %sop_class.UID)
                logger.error("Find SCU failed due to there being no valid "
                        "presentation context for the current dataset")
                return service_class.IdentifierDoesNotMatchSOPClass
            
            # Build C-FIND primitive
            primitive = C_FIND_ServiceParameters()
            primitive.MessageID = msg_id
            primitive.AffectedSOPClassUID = sop_class.UID
            primitive.Priority = priority
            primitive.Identifier = encode(dataset,
                                          transfer_syntax.is_implicit_VR,
                                          transfer_syntax.is_little_endian)
            primitive.Identifier = BytesIO(primitive.Identifier)
            
            logger.info('Find SCU Request Identifiers:')
            logger.info('')
            logger.info('# DICOM Dataset')
            for elem in dataset:
                logger.info(elem)
            logger.info('')
            
            # send c-find request
            self.dimse.Send(primitive, context_id, self.acse.MaxPDULength)

            # Get the responses from the peer
            ii = 1
            while True:
                time.sleep(0.001)
                
                # Wait for c-find responses
                rsp, _ = self.dimse.Receive(False, self.dimse.dimse_timeout)
                
                if not rsp:
                    continue

                # Decode the dataset
                d = decode(rsp.Identifier, 
                           transfer_syntax.is_implicit_VR,
                           transfer_syntax.is_little_endian)
                
                # Status may be 'Failure', 'Cancel', 'Success' or 'Pending'
                status = service_class.Code2Status(rsp.Status)
                
                if status.Type == 'Success':
                    # We want to exit the wait loop if we receive
                    #   failure, cancel or success
                    break
                elif status.Type != 'Pending':
                    break
                
                logger.debug('-' * 65)
                logger.debug('Find Response: %s (%s)' %(ii, status.Type))
                logger.debug('')
                logger.debug('# DICOM Dataset')
                for elem in d:
                    logger.debug(elem)
                logger.debug('')
                
                ii += 1
                
                yield status, d

            yield status, d

        else:
            raise RuntimeError("The association with a peer SCP must be "
                "established before sending a C-FIND request")

    def send_c_cancel_find(self, msg_id, query_model):
        """
        See PS3.7 9.3.2.3
        
        Parameters
        ----------
        msg_id : int
            The message ID of the C-FIND operation we want to cancel
        """
        if self.is_established:
            service_class = QueryRetrieveFindServiceClass()
            
            # Build C-FIND primitive
            primitive = C_FIND_ServiceParameters()
            primitive.CommandField = 0x0fff
            primitive.MessageIDBeingRespondedTo = msg_id
            primitive.CommandDataSetType = 0x0101
            
            # We need the Context ID unfortunately...
            if query_model == 'W':
                sop_class = ModalityWorklistInformationFind()
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
                raise ValueError("Association::send_c_cancel_find() "
                    "query_model must be one of ['W'|'P'|'S'|'O']")
            
            # Determine the Presentation Context we are operating under
            #   and hence the transfer syntax to use for encoding `dataset`
            transfer_syntax = None
            for context in self.acse.context_manager.accepted:
                if sop_class.UID == context.AbstractSyntax:
                    transfer_syntax = context.TransferSyntax[0]
                    context_id = context.ID
                    
            if transfer_syntax is None:
                logger.error("No Presentation Context for: '%s'" 
                                                    %sop_class.UID)
                logger.error("Find SCU failed due to there being no valid "
                        "presentation context for the current dataset")
                return service_class.IdentifierDoesNotMatchSOPClass
            
            logger.info('Sending C-CANCEL-FIND')
            
            # send c-find request
            self.dimse.Send(primitive, context_id, self.acse.MaxPDULength)

    def send_c_move(self, dataset, move_aet, msg_id=1, priority=2, query_model='P'):
        """
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
            The dataset containing the Attributes to match against
        move_aet : str
            The AE title for the destination of the C-STORE operations performed
            by the C-MOVE performing DIMSE user
        msg_id : int, optional
            The Message ID to use for the C-MOVE service
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
        """
        
        if self.is_established:
            if query_model == "P":
                sop_class = PatientRootQueryRetrieveInformationModelMove()
            elif query_model == "S":
                sop_class = StudyRootQueryRetrieveInformationModelMove()
            elif query_model == "O":
                sop_class = PatientStudyOnlyQueryRetrieveInformationModelMove()
            else:
                raise ValueError("Association::send_c_move() query_model must "
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
                logger.error("No Presentation Context for: '%s'" 
                                                    %sop_class.UID)
                logger.error("Move SCU failed due to there being no valid "
                        "presentation context for the current dataset")
                return service_class.IdentifierDoesNotMatchSOPClass

            # Build C-MOVE primitive
            primitive = C_MOVE_ServiceParameters()
            primitive.MessageID = msg_id
            primitive.AffectedSOPClassUID = sop_class.UID
            primitive.MoveDestination = move_aet
            primitive.Priority = priority
            primitive.Identifier = encode(dataset, 
                                          transfer_syntax.is_implicit_VR,
                                          transfer_syntax.is_little_endian)
            primitive.Identifier = BytesIO(primitive.Identifier)

            logger.info('Move SCU Request Identifiers:')
            logger.info('')
            logger.info('# DICOM Dataset')
            for elem in dataset:
                logger.info(elem)
            logger.info('')
            
            # Send C-MOVE request to peer
            self.dimse.Send(primitive, context_id, self.acse.MaxPDULength)
            
            # Get the responses from peer
            ii = 1
            while True:
                time.sleep(0.001)
                
                rsp, context_id = self.dimse.Receive(False, self.dimse.dimse_timeout)
                
                if rsp.__class__ == C_MOVE_ServiceParameters:
                    status = service_class.Code2Status(rsp.Status)
                    dataset = decode(rsp.Identifier,
                                     transfer_syntax.is_implicit_VR,
                                     transfer_syntax.is_little_endian)
                    
                    # If the Status is "Pending" then the processing of 
                    #   matches and suboperations is initiated or continuing
                    if status.Type == 'Pending':
                        remain = rsp.NumberOfRemainingSuboperations
                        complete = rsp.NumberOfCompletedSuboperations
                        failed = rsp.NumberOfFailedSuboperations
                        warning = rsp.NumberOfWarningSuboperations
                        
                        # Pending Response
                        logger.debug('')
                        logger.info("Move Response: %s (Pending)" %ii)
                        logger.info("    Sub-Operations Remaining: %s, "
                                "Completed: %s, Failed: %s, Warning: %s" %(
                                                            remain, 
                                                            complete, 
                                                            failed, 
                                                            warning))
                        ii += 1
                        
                        yield status, dataset
                    # If the Status is "Success" then processing is complete
                    elif status.Type == "Success":
                        break
                    # All other possible responses
                    elif status.Type == "Failure":
                        logger.debug('')
                        logger.error('Move Response: %s (Failure)' %ii)
                        logger.error('    %s' %status.Description)

                        break
                    elif status.Type == "Cancel":
                        logger.debug('')
                        logger.info('Move Response: %s (Cancel)' %ii)
                        logger.info('    %s' %status.Description)
                        break
                    elif status.Type == "Warning":
                        logger.debug('')
                        logger.warning('Move Response: %s (Warning)' %ii)
                        logger.warning('    %s' %status.Description)
                        
                        for elem in dataset:
                            logger.warning('%s: %s' %(elem.name, elem.value))
                            
                        break

            yield status, dataset
            
        else:
            raise RuntimeError("The association with a peer SCP must be "
                "established before sending a C-MOVE request")

    def send_c_cancel_move(self, msg_id, query_model):
        """
        See PS3.7 9.3.2.3
        
        Parameters
        ----------
        msg_id : int
            The message ID of the C-MOVE operation we want to cancel
        query_model : str
            The query model SOP class to use (needed to identify context ID)
        """
        if self.is_established:
            service_class = QueryRetrieveMoveServiceClass()
            
            # Build C-MOVE primitive
            primitive = C_MOVE_ServiceParameters()
            primitive.CommandField = 0x0fff
            primitive.MessageIDBeingRespondedTo = msg_id
            primitive.CommandDataSetType = 0x0101
            
            # We need the Context ID unfortunately...
            if query_model == "P":
                sop_class = PatientRootQueryRetrieveInformationModelMove()
            elif query_model == "S":
                sop_class = StudyRootQueryRetrieveInformationModelMove()
            elif query_model == "O":
                sop_class = PatientStudyOnlyQueryRetrieveInformationModelMove()
            else:
                raise ValueError("Association::send_c_cancel_move() query_model "
                    "must be one of ['P'|'S'|'O']")
            
            # Determine the Presentation Context we are operating under
            #   and hence the transfer syntax to use for encoding `dataset`
            transfer_syntax = None
            for context in self.acse.context_manager.accepted:
                if sop_class.UID == context.AbstractSyntax:
                    transfer_syntax = context.TransferSyntax[0]
                    context_id = context.ID
                    
            if transfer_syntax is None:
                logger.error("No Presentation Context for: '%s'" 
                                                    %sop_class.UID)
                logger.error("Move SCU failed due to there being no valid "
                        "presentation context for the current dataset")
                return service_class.IdentifierDoesNotMatchSOPClass
            
            logger.info('Sending C-CANCEL-MOVE')
            
            # Send C-CANCEL-MOVE request
            self.dimse.Send(primitive, context_id, self.acse.MaxPDULength)

    def send_c_get(self, dataset, msg_id=1, priority=2, query_model='P'):
        """
        Send a C-GET request message to the peer AE
        
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
        status : pynetdicom.SOPclass.Status
            The resulting status(es) from the C-GET operation
        dataset : pydicom.dataset.Dataset
            The resulting dataset(s) from the C-GET operation
        """
        if self.is_established:
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
                raise ValueError("Association::send_c_get() query_model "
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
                logger.error("No Presentation Context for: '%s'" 
                                                    %sop_class.UID)
                logger.error("Get SCU failed due to there being no valid "
                        "presentation context for the current dataset")
                return service_class.IdentifierDoesNotMatchSOPClass


            # Build C-GET primitive
            primitive = C_GET_ServiceParameters()
            primitive.MessageID = msg_id
            primitive.AffectedSOPClassUID = sop_class.UID
            primitive.Priority = priority
            primitive.Identifier = encode(dataset,
                                          transfer_syntax.is_implicit_VR,
                                          transfer_syntax.is_little_endian)
            primitive.Identifier = BytesIO(primitive.Identifier)
            
            # Send primitive to peer
            self.dimse.Send(primitive, context_id, self.acse.MaxPDULength)
            
            logger.info('Get SCU Request Identifiers:')
            logger.info('')
            logger.info('# DICOM Dataset')
            for elem in dataset:
                logger.info(elem)
            logger.info('')
            
            ii = 1
            while True:
                rsp, context_id = self.dimse.Receive(True, self.dimse.dimse_timeout)
                
                # Received a C-GET response
                if rsp.__class__ == C_GET_ServiceParameters:
                    
                    status = service_class.Code2Status(rsp.Status)
                    dataset = decode(rsp.Identifier,
                                     transfer_syntax.is_implicit_VR,
                                     transfer_syntax.is_little_endian)
                    
                    # If the Status is "Pending" then the processing of 
                    #   matches and suboperations is initiated or continuing
                    if status.Type == 'Pending':
                        remain = rsp.NumberOfRemainingSuboperations
                        complete = rsp.NumberOfCompletedSuboperations
                        failed = rsp.NumberOfFailedSuboperations
                        warning = rsp.NumberOfWarningSuboperations
                        
                        # Pending Response
                        logger.debug('')
                        logger.info("Find Response: %s (Pending)" %ii)
                        logger.info("    Sub-Operations Remaining: %s, "
                                "Completed: %s, Failed: %s, Warning: %s" %(
                                                            remain, 
                                                            complete, 
                                                            failed, 
                                                            warning))
                        ii += 1
                        
                        yield status, dataset
                        
                    # If the Status is "Success" then processing is complete
                    elif status.Type == "Success":
                        status = service_class.Success
                        break
                    
                    # All other possible responses
                    elif status.Type == "Failure":
                        logger.debug('')
                        logger.error('Find Response: %s (Failure)' %ii)
                        logger.error('    %s' %status.Description)
                        
                        # Print out the status information
                        for elem in dataset:
                            logger.error('%s: %s' %(elem.name, elem.value))
                    
                        break
                    elif status.Type == "Cancel":
                        logger.debug('')
                        logger.info('Find Response: %s (Cancel)' %ii)
                        logger.info('    %s' %status.Description)
                        break
                    elif status.Type == "Warning":
                        logger.debug('')
                        logger.warning('Find Response: %s (Warning)' %ii)
                        logger.warning('    %s' %status.Description)
                        
                        # Print out the status information
                        for elem in dataset:
                            logger.warning('%s: %s' %(elem.name, elem.value))
                            
                        break
                
                # Received a C-STORE request in response to the C-GET
                elif rsp.__class__ == C_STORE_ServiceParameters:
                    
                    c_store_rsp = C_STORE_ServiceParameters()
                    c_store_rsp.MessageIDBeingRespondedTo = rsp.MessageID
                    c_store_rsp.AffectedSOPInstanceUID = \
                                                    rsp.AffectedSOPInstanceUID
                    c_store_rsp.AffectedSOPClassUID = rsp.AffectedSOPClassUID

                    d = decode(rsp.DataSet, 
                               transfer_syntax.is_implicit_VR,
                               transfer_syntax.is_little_endian)

                    #  Callback for C-STORE SCP (user implemented)
                    status = self.ae.on_c_store(d)
                    
                    # Send C-STORE confirmation back to peer
                    c_store_rsp.Status = int(status)
                    self.dimse.Send(c_store_rsp, 
                                    context_id, 
                                    self.acse.MaxPDULength)
            
            yield status, dataset
            
        else:
            raise RuntimeError("The association with a peer SCP must be "
                "established before sending a C-GET request")

    def send_c_cancel_get(self, msg_id, query_model):
        """
        See PS3.7 9.3.2.3
        
        Parameters
        ----------
        msg_id : int
            The message ID of the C-GET operation we want to cancel
        """
        if self.is_established:
            service_class = QueryRetrieveGetServiceClass()
            
            # Build C-GET primitive
            primitive = C_GET_ServiceParameters()
            primitive.CommandField = 0x0fff
            primitive.MessageIDBeingRespondedTo = msg_id
            primitive.CommandDataSetType = 0x0101
            
            # We need the Context ID unfortunately...
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
                raise ValueError("Association::send_c_cancel_get() query_model "
                    "must be one of ['P'|'S'|'O']")
            
            # Determine the Presentation Context we are operating under
            #   and hence the transfer syntax to use for encoding `dataset`
            transfer_syntax = None
            for context in self.acse.context_manager.accepted:
                if sop_class.UID == context.AbstractSyntax:
                    transfer_syntax = context.TransferSyntax[0]
                    context_id = context.ID
                    
            if transfer_syntax is None:
                logger.error("No Presentation Context for: '%s'" 
                                                    %sop_class.UID)
                logger.error("Find SCU failed due to there being no valid "
                        "presentation context for the current dataset")
                return service_class.IdentifierDoesNotMatchSOPClass
            
            logger.info('Sending C-CANCEL-GET')
            
            # Send c-cancel-get request
            self.dimse.Send(primitive, context_id, self.acse.MaxPDULength)


    # DIMSE-N services provided by the Association
    def send_n_event_report(self):
        raise NotImplementedError
    
    def send_n_get(self, msg_id, dataset=None):
        if self.is_established:
            service_class = QueryRetrieveGetServiceClass()
            
            # Determine the Presentation Context we are operating under
            #   and hence the transfer syntax to use for encoding `dataset`
            transfer_syntax = None
            for context in self.acse.context_manager.accepted:
                if sop_class.UID == context.AbstractSyntax:
                    transfer_syntax = context.TransferSyntax[0]
                    context_id = context.ID
                    
            if transfer_syntax is None:
                logger.error("No Presentation Context for: '%s'" 
                                                    %sop_class.UID)
                logger.error("Get SCU failed due to there being no valid "
                        "presentation context for the current dataset")
                return service_class.IdentifierDoesNotMatchSOPClass


            # Build N-GET primitive
            primitive = N_GET_ServiceParameters()
            primitive.MessageID = msg_id
            # The SOP Class for which Attribute Values are to be retrieved
            primitive.RequestedSOPClassUID = None
            # The SOP Instance for which Attribute Values are to be retrieved
            primitive.RequestedSOPInstanceUID = None
            # A set of Attribute identifiers, if omitted then all identifiers are assumed
            #   The definitions of the Attributes are found in PS3.3
            if dataset is not None:
                primitive.AttributeIdentifierList = encode(dataset,
                                                           transfer_syntax.is_implicit_VR,
                                                           transfer_syntax.is_little_endian)
                primitive.AttributeIdentifierList = BytesIO(primitive.AttributeIdentifierList)
            
            # Send primitive to peer
            self.dimse.Send(primitive, context_id, self.acse.MaxPDULength)

    def send_n_set(self):
        raise NotImplementedError

    def send_n_action(self):
        raise NotImplementedError

    def send_n_create(self):
        raise NotImplementedError

    def send_n_delete(self):
        raise NotImplementedError


    # Association logging/debugging functions
    def debug_association_requested(self, primitive):
        """
        Called when an association is reuested by a peer AE, used for 
        logging/debugging information
        
        Parameters
        ----------
        assoc_primitive - pynetdicom.DULparameters.A_ASSOCIATE_ServiceParameter
            The A-ASSOCIATE-RJ PDU instance received from the peer AE
        """
        pass

    def debug_association_accepted(self, assoc):
        """
        Called when an association attempt is accepted by a peer AE, used for 
        logging/debugging information
        
        Parameters
        ----------
        assoc - pynetdicom.DULparameters.A_ASSOCIATE_ServiceParameter
            The Association parameters negotiated between the local and peer AEs
        
        #max_send_pdv = associate_ac_pdu.UserInformationItem[-1].MaximumLengthReceived
        
        #logger.info('Association Accepted (Max Send PDV: %s)' %max_send_pdv)
        
        pynetdicom_version = 'PYNETDICOM_' + ''.join(__version__.split('.'))
                
        # Shorthand
        assoc_ac = a_associate_ac
        
        # Needs some cleanup
        app_context   = assoc_ac.ApplicationContext.__repr__()[1:-1]
        pres_contexts = assoc_ac.PresentationContext
        user_info     = assoc_ac.UserInformation
        
        responding_ae = 'resp. AP Title'
        our_max_pdu_length = '[FIXME]'
        their_class_uid = 'unknown'
        their_version = 'unknown'
        
        if user_info.ImplementationClassUID:
            their_class_uid = user_info.ImplementationClassUID
        if user_info.ImplementationVersionName:
            their_version = user_info.ImplementationVersionName
        
        s = ['Association Parameters Negotiated:']
        s.append('====================== BEGIN A-ASSOCIATE-AC ================'
                '=====')
        
        s.append('Our Implementation Class UID:      %s' %pynetdicom_uid_prefix)
        s.append('Our Implementation Version Name:   %s' %pynetdicom_version)
        s.append('Their Implementation Class UID:    %s' %their_class_uid)
        s.append('Their Implementation Version Name: %s' %their_version)
        s.append('Application Context Name:    %s' %app_context)
        s.append('Calling Application Name:    %s' %assoc_ac.CallingAETitle)
        s.append('Called Application Name:     %s' %assoc_ac.CalledAETitle)
        #s.append('Responding Application Name: %s' %responding_ae)
        s.append('Our Max PDU Receive Size:    %s' %our_max_pdu_length)
        s.append('Their Max PDU Receive Size:  %s' %user_info.MaximumLength)
        s.append('Presentation Contexts:')
        
        for item in pres_contexts:
            context_id = item.PresentationContextID
            s.append('  Context ID:        %s (%s)' %(item.ID, item.Result))
            s.append('    Abstract Syntax: =%s' %'FIXME')
            s.append('    Proposed SCP/SCU Role: %s' %'[FIXME]')

            if item.ResultReason == 0:
                s.append('    Accepted SCP/SCU Role: %s' %'[FIXME]')
                s.append('    Accepted Transfer Syntax: =%s' 
                                            %item.TransferSyntax)
        
        ext_nego = 'None'
        #if assoc_ac.UserInformation.ExtendedNegotiation is not None:
        #    ext_nego = 'Yes'
        s.append('Requested Extended Negotiation: %s' %'[FIXME]')
        s.append('Accepted Extended Negotiation: %s' %ext_nego)
        
        usr_id = 'None'
        if assoc_ac.UserInformation.UserIdentity is not None:
            usr_id = 'Yes'
        
        s.append('Requested User Identity Negotiation: %s' %'[FIXME]')
        s.append('User Identity Negotiation Response:  %s' %usr_id)
        s.append('======================= END A-ASSOCIATE-AC =================='
                '====')
        
        for line in s:
            logger.debug(line)
        """
        pass

    def debug_association_rejected(self, assoc_primitive):
        """
        Called when an association attempt is rejected by a peer AE, used for 
        logging/debugging information
        
        Parameters
        ----------
        assoc_primitive - pynetdicom.DULparameters.A_ASSOCIATE_ServiceParameter
            The A-ASSOCIATE-RJ PDU instance received from the peer AE
        """
        
        # See PS3.8 Section 7.1.1.9 but mainly Section 9.3.4 and Table 9-21
        #   for information on the result and diagnostic information
        source = assoc_primitive.ResultSource
        result = assoc_primitive.Result
        reason = assoc_primitive.Diagnostic
        
        source_str = { 1 : 'Service User',
                       2 : 'Service Provider (ACSE)',
                       3 : 'Service Provider (Presentation)'}
        
        reason_str = [{ 1 : 'No reason given',
                        2 : 'Application context name not supported',
                        3 : 'Calling AE title not recognised',
                        4 : 'Reserved',
                        5 : 'Reserved',
                        6 : 'Reserved',
                        7 : 'Called AE title not recognised',
                        8 : 'Reserved',
                        9 : 'Reserved',
                       10 : 'Reserved'},
                      { 1 : 'No reason given',
                        2 : 'Protocol version not supported'},
                      { 0 : 'Reserved',
                        1 : 'Temporary congestion',
                        2 : 'Local limit exceeded',
                        3 : 'Reserved',
                        4 : 'Reserved',
                        5 : 'Reserved',
                        6 : 'Reserved',
                        7 : 'Reserved'}]
        
        result_str = { 1 : 'Rejected Permanent',
                       2 : 'Rejected Transient'}
        
        logger.error('Association Rejected:')
        logger.error('Result: %s, Source: %s' %(result_str[result], source_str[source]))
        logger.error('Reason: %s' %reason_str[source - 1][reason])

    def debug_association_released(self):
        logger.info('Association Released')

    def debug_association_aborted(self, abort_primitive=None):
        logger.info('Association Aborted')
