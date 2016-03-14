#
# Copyright (c) 2012 Patrice Munger
# This file is part of pynetdicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pynetdicom.googlecode.com

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
from pynetdicom.PDU import *
from pynetdicom.DULparameters import *
from pynetdicom.DULprovider import DULServiceProvider
from pynetdicom.SOPclass import *
from pynetdicom.utils import PresentationContextManager


logger = logging.getLogger('pynetdicom.assoc')


class Association(threading.Thread):
    """
    A higher level class that handles incoming and outgoing Associations. The
    actual low level work done for Associations is performed by 
    pynetdicom.ACSEprovider.ACSEServiceProvider
    
    When the local AE is acting as an SCP, initialise the Association using 
    the socket to listen on for incoming Association requests. When the local 
    AE is acting as an SCU, initialise the Association with the details of the 
    peer AE
    
    When AE is acting as an SCP:
        assoc = Association(self, client_socket, max_pdu=self.maximum_pdu_size)
        
    When AE is acting as an SCU:
        assoc = Association(self, 
                            RemoteAE=peer_ae, 
                            acse_timeout=self.acse_timeout,
                            dimse_timeout=self.dimse_timeout,
                            max_pdu=max_pdu,
                            ext_neg=ext_neg)
    
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
        means no maximum size.
    ext_neg - list of extended negotiation parameters objects, optional
        If the association requires an extended negotiation then `ext_neg` is
        a list containing the negotiation objects
    

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
        The peer ApplicationEntity details (Port, Address, Title)
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
        self.acse.Release()
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
        self.acse = ACSEServiceProvider(self.dul, self.acse_timeout)
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
                    reject_assoc_rsd = [0x01, 0x01, 0x03]

            # Called AE Title not recognised
            if self.ae.require_called_aet != '':
                if self.AE.require_called_aet != assoc_rq.CalledAETitle:
                    reject_assoc_rsd = [0x01, 0x01, 0x07]

            # DUL Presentation Related Rejections
            #
            # Maximum number of associations reached (local-limit-exceeded)
            if len(self.ae.active_associations) > self.ae.maximum_associations:
                reject_assoc_rsd = [0x02, 0x03, 0x02]

            for [result, src, diag] in reject_assoc_rsd:
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
                msg, msg_id = self.dimse.Receive(False, 
                                                         self.dimse_timeout)
                
                # DIMSE message received
                if msg:
                    # Convert the message's affected SOP class to a UID
                    uid = msg.AffectedSOPClassUID

                    # Use the UID to create a new SOP Class instance of the
                    #   corresponding value
                    sop_class = UID2SOPClass(uid.value)()
                    
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
                        sop_class.maxpdulength = self.acse.MaxPDULength
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
                            self.debug_association_released()
                            self.ae.on_association_released()
                            self.kill()
                            return

                        # Check for abort
                        if self.acse.CheckAbort():
                            # Callback trigger
                            self.debug_association_aborted()
                            self.ae.on_association_aborted()
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
                    self.debug_association_rejected(assoc_rsp)
                    self.ae.on_association_rejected(assoc_rsp)
                    
                    self.is_refused = True
                    self.dul.Kill()
                    return
            
            # Association was aborted by peer
            elif isinstance(assoc_rsp, A_ABORT_ServiceParameters):
                self.debug_association_aborted(assoc_rsp)
                self.ae.on_association_aborted(assoc_rsp)
                
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


    # DIMSE services provided by the Association
    def send_c_store(self, dataset, msg_id=1, priority=2):
        # Select appropriate SOP Class for dataset
        data_sop = dataset.SOPClassUID.__repr__()[1:-1]
        sop_class = UID2SOPClass(data_sop)
        
        # Check that the dataset's SOP Class belongs to one of the ACSE's 
        #   accepted presentation contexts
        found_match = False
        for context in self.acse.context_manager.accepted:
            if sop_class.UID == context.AbstractSyntax:
                sop_class.pcid = context.ID
                sop_class.sopclass = context.AbstractSyntax
                sop_class.transfersyntax = context.TransferSyntax[0]
    
                found_match = True

        if not found_match:
            logger.error("No Presentation Context for: '%s'"
                                                       %UID(sop_class.UID))
            logger.error("Store SCU Failed: DIMSE No valid presentation context ID")
            return None
            
        sop_class.maxpdulength = self.acse.MaxPDULength
        sop_class.DIMSE = self.dimse
        sop_class.AE = self.ae
        sop_class.RemoteAE = self.peer_ae

        # Send the query
        return sop_class().SCU(dataset, msg_id, priority)
        
    def send_c_echo(self, msg_id=1):
        sop_class = VerificationSOPClass()
        
        found_match = False
        for scu_sop_class in self.scu_supported_sop:
            if scu_sop_class[1] == sop_class.__class__:
                sop_class.pcid = scu_sop_class[0]
                sop_class.sopclass = scu_sop_class[1]
                sop_class.transfersyntax = scu_sop_class[2]
                
                found_match = True
                
        if not found_match:
            raise ValueError("'%s' is not listed as one of the AE's "
                    "supported SOP Classes" %sop_class.__class__.__name__)
            
        sop_class.maxpdulength = self.acse.MaxPDULength
        sop_class.DIMSE = self.dimse
        sop_class.AE = self.ae
        sop_class.RemoteAE = self.peer_ae
        
        status = sop_class.SCU(msg_id)
        
    def send_c_find(self, dataset, query_model='W', msg_id=1, query_priority=2):

        if query_model == 'W':
            sop_class = ModalityWorklistInformationFindSOPClass()
        elif query_model == "P":
            sop_class = PatientRootFindSOPClass()
        elif query_model == "S":
            sop_class = StudyRootFindSOPClass()
        elif query_model == "O":
            sop_class = PatientStudyOnlyFindSOPClass()
        else:
            raise ValueError("Association::send_c_find() query_model must be "
                "one of ['W'|'P'|'S'|'O']")

        found_match = False
        for scu_sop_class in self.scu_supported_sop:
            if scu_sop_class[1] == sop_class.__class__:
                sop_class.pcid = scu_sop_class[0]
                sop_class.sopclass = scu_sop_class[1]
                sop_class.transfersyntax = scu_sop_class[2]
                
                found_match = True
                
        if not found_match:
            raise ValueError("'%s' is not listed as one of the AE's "
                    "supported SOP Classes" %sop_class.__class__.__name__)
            
        sop_class.maxpdulength = self.acse.MaxPDULength
        sop_class.DIMSE = self.dimse
        sop_class.AE = self.ae
        sop_class.RemoteAE = self.peer_ae
        
        # Send the query
        return sop_class.SCU(dataset, msg_id, query_priority)
        
    def send_c_move(self, dataset):
        pass
        
    def send_c_get(self, dataset, query_model='W', msg_id=1, query_priority=2):
        if query_model == 'W':
            sop_class = ModalityWorklistInformationGetSOPClass()
        elif query_model == "P":
            sop_class = PatientRootGetSOPClass()
        elif query_model == "S":
            sop_class = StudyRootGetSOPClass()
        elif query_model == "O":
            sop_class = PatientStudyOnlyGetSOPClass()
        else:
            raise ValueError("Association::send_c_get() query_model must be "
                "one of ['W'|'P'|'S'|'O']")

        found_match = False
        for scu_sop_class in self.scu_supported_sop:
            if scu_sop_class[1] == sop_class.__class__:
                sop_class.pcid = scu_sop_class[0]
                sop_class.sopclass = scu_sop_class[1]
                sop_class.transfersyntax = scu_sop_class[2]
                
                found_match = True
                
        if not found_match:
            raise ValueError("'%s' is not listed as one of the AE's "
                    "supported SOP Classes" %sop_class.__class__.__name__)
            
        sop_class.maxpdulength = self.acse.MaxPDULength
        sop_class.DIMSE = self.dimse
        sop_class.AE = self.ae
        sop_class.RemoteAE = self.peer_ae
        
        # Send the query
        return sop_class.SCU(dataset, msg_id, query_priority)


    # Association logging/debugging functions
    def debug_association_requested(self):
        pass
    
    def debug_association_accepted(self, assoc):
        """
        Placeholder for a function callback. Function will be called 
        when an association attempt is accepted by either the local or peer AE
        
        The default implementation is used for logging debugging information
        
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
        Placeholder for a function callback. Function will be called 
        when an association attempt is rejected by a peer AE
        
        The default implementation is used for logging debugging information
        
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


    # Deprecated functions
    def Release(self):
        self.release()

    def Abort(self, reason):
        self.abort(reason)

    def Kill(self):
        self.kill()
    
    @property
    def AssociationEstablished(self):
        return self.is_established
