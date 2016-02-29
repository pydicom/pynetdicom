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
    
    Parameters
    ----------
    local_ae - dict
        The AE title, host and port of the local AE
    local_socket - socket.socket, optional
        If the local AE is acting as an SCP, this is the listen socket for 
        incoming connection requests
    peer_ae - dict, optional
        If the local AE is acting as an SCU this is the AE title, host and port 
        of the peer AE that we want to Associate with

    Attributes
    ----------
    acse - ACSEServiceProvider
        The Association Control Service Element provider
    dimse - DIMSEServiceProvider
        The DICOM Message Service Element provider
    dul - DUL
        The DICOM Upper Layer service provider instance
    local_ae - ApplicationEntity
        The local ApplicationEntity instance
    mode - str
        Whether the local AE is acting as the Association 'Requestor' or 
        'Acceptor' (i.e. SCU or SCP)
    peer_ae - ApplicationEntity
        The peer ApplicationEntity instance
    require_calling_ae - str
        If not empty, the calling AE title must match `require_calling_ae`
    require_called_ae - str
        If not empty, the called AE title must match `required_called_ae`
    socket - socket.socket
        The socket to use for connections with the peer AE
    supported_sop_classes_scu
        A list of the supported SOP classes when acting as an SCU
    supported_sop_classes_scp
        A list of the supported SOP classes when acting as an SCP
    """
    def __init__(self, LocalAE, 
                       ClientSocket=None, 
                       RemoteAE=None, 
                       acse_timeout=30,
                       dimse_timeout=None):
        
        if [ClientSocket, RemoteAE] == [None, None]:
            raise ValueError("Association can't be initialised with both "
                                        "ClientSocket and RemoteAE parameters")
        
        if ClientSocket and RemoteAE:
            raise ValueError("Association must be initialised with either "
                                        "ClientSocket or RemoteAE parameter")
        
        # Received a connection from a peer AE
        if ClientSocket:
            self.mode = 'Acceptor'
        
        # Initiated a connection to a peer AE
        if RemoteAE:
            self.mode = 'Requestor'
        
        self.ClientSocket = ClientSocket
        self.AE = LocalAE
        
        self.require_calling_aet = ''
        self.require_called_aet = ''
        
        # Why do we instantiate the DUL provider with a socket when acting
        #   as an SCU?
        self.DUL = DULServiceProvider(ClientSocket,
                            dul_timeout=self.AE.dul_timeout,
                            acse_timeout=acse_timeout,
                            local_ae=LocalAE,
                            assoc=self)
                            
        self.RemoteAE = RemoteAE
        
        self.SOPClassesAsSCP = []
        self.SOPClassesAsSCU = []
        
        self.AssociationEstablished = False
        self.AssociationRefused = None
        
        self.established = False
        
        self.dimse_timeout = dimse_timeout
        self.acse_timeout = acse_timeout
        
        self._Kill = False
        
        threading.Thread.__init__(self)
        self.daemon = True

        self.start()

    def SCU(self, dataset, id):

        obj = UID2SOPClass(ds.SOPClassUID)()
        
        try:
            obj.pcid, obj.sopclass, obj.transfersyntax = \
                [x for x in self.SOPClassesAsSCU if x[1] == obj.__class__][0]
        except IndexError:
            raise ValueError("'%s' is not listed as one of the AE's "
                    "supported SCU SOP Classes" %obj.__class__.__name__)

        obj.maxpdulength = self.ACSE.MaxPDULength
        obj.DIMSE = self.DIMSE
        obj.AE = self.AE
        
        return obj.SCU(dataset, id)

    def __getattr__(self, attr):
        """
        
        """
        # Wow, eval? Really?
        obj = eval(attr)()
        
        found_match = False
        for sop_class in self.SOPClassesAsSCU:
            if sop_class[1] == obj.__class__:
                obj.pcid = sop_class[0]
                obj.sopclass = sop_class[1]
                obj.transfersyntax = sop_class[2]
                
                found_match = True
                
        if not found_match:
            raise ValueError("'%s' is not listed as one of the AE's "
                    "supported SOP Classes" %obj.__class__.__name__)
            
        
        #try:
        #    obj.pcid, obj.sopclass, obj.transfersyntax = \
        #        [x for x in self.SOPClassesAsSCU if x[1] == obj.__class__][0]
        #except IndexError:
        #    raise ValueError("'%s' is not listed as one of the AE's "
        #            "supported SOP Classes" %obj.__class__.__name__)

        obj.maxpdulength = self.ACSE.MaxPDULength
        obj.DIMSE = self.DIMSE
        obj.AE = self.AE
        obj.RemoteAE = self.AE
        
        return obj

    def Kill(self):
        self._Kill = True
        self.AssociationEstablished = False
        while not self.DUL.Stop():
            time.sleep(0.001)

    def Release(self):
        """
        Release the association
        """
        self.ACSE.Release()
        self.Kill()

    def Abort(self, reason):
        """
        Abort the Association
        
        Parameters
        ----------
        reason - in
            The reason to abort the association. Need to find a list of reasons
        """
        self.ACSE.Abort(reason)
        self.Kill()

    def run(self):
        """
        The main Association thread
        """
        # Set new ACSE and DIMSE providers
        self.ACSE = ACSEServiceProvider(self.DUL, self.acse_timeout)
        self.DIMSE = DIMSEServiceProvider(self.DUL, self.dimse_timeout)
        
        result = None
        diag  = None
        
        # If the remote AE initiated the Association then either accept
        #   or reject it
        # Rejection reasons: 
        #   a) DUL user
        #       0x02 unsupported application context name
        #   b) DUL ACSE related
        #       0x01 no reason given
        #       0x02 protocol version not supported
        #   c) DUL Presentation related
        #       0x01 temporary congestion
        if self.mode == 'Acceptor':
            # needed because of some thread-related problem. To investigate.
            time.sleep(0.1)
            
            # Get A-ASSOCIATE request primitive from the DICOM UL
            assoc_rq = self.DUL.Receive(Wait=True)
            
            if assoc_rq is None:
                self.Kill()
                return
            
            ## DUL User Related Rejections
            #
            # Calling AE Title not recognised
            if self.require_calling_aet != '':
                peer_calling_aet = assoc_rq.CallingAETitle.decode('utf-8').strip()
                if self.require_calling_aet != peer_calling_aet:
                    assoc_rj = self.ACSE.Reject(assoc_rq, 0x01, 0x01, 0x03)
                    self.debug_association_rejected(assoc_rj)
                    self.AE.on_association_rejected(assoc_rj)
                    self.Kill()
                    return
            
            # Called AE Title not recognised
            if self.require_called_aet != '':
                peer_called_aet = assoc_rq.CalledAETitle.decode('utf-8').strip()
                if self.require_called_aet != peer_called_aet:
                    assoc_rj = self.ACSE.Reject(assoc_rq, 0x01, 0x01, 0x07)
                    self.debug_association_rejected(assoc_rj)
                    self.AE.on_association_rejected(assoc_rj)
                    self.Kill()
                    return
            
            # DUL Presentation Related Rejections
            #
            # Maximum number of associations reached (local-limit-exceeded)
            if len(self.AE.Associations) > self.AE.MaxNumberOfAssociations:
                assoc_rj = self.ACSE.Reject(assoc_rq, 0x02, 0x03, 0x02)
                self.debug_association_rejected(assoc_rj)
                self.AE.on_association_rejected(assoc_rj)
                self.Kill()
                return
            
            # Determine acceptable presentation contexts
            # analyse proposed presentation contexts
            rsp = []
            self.ACSE.AcceptedPresentationContexts = []
            # [SOP Class UID, [Transfer Syntax UIDs]]
            acceptable_sop_classes = [x.AbstractSyntax for x in \
                                        self.AE.presentation_contexts_scp]

            # For each presentation context in the association request
            #   received from the peer AE
            # Proposed values are from the peer, acceptable values from 
            #   the local
            for context in assoc_rq.PresentationContextDefinitionList:
                if context.AbstractSyntax in acceptable_sop_classes:
                    acceptable_ts = [x.TransferSyntax for x in \
                                    self.AE.presentation_contexts_scp if \
                                    x.ID == context.ID][0]
                    
                    # We accept the first matching transfer syntax
                    for transfer_syntax in acceptable_ts:
                        # the local transfer syntax is used in order to 
                        #   enforce preference based on position
                        matching_ts = False
                        if transfer_syntax in context.TransferSyntax:
                            rsp.append((context.ID, 0, transfer_syntax))
                            temp_context = PresentationContext(
                                                    context.ID, 
                                                    context.AbstractSyntax, 
                                                    [transfer_syntax])
                            temp_context.Result = 0x00
                            self.ACSE.AcceptedPresentationContexts.append(temp_context)
                            
                            matching_ts = True
                            break
                    
                    if not matching_ts:
                        # Refuse sop class because of TS not supported
                        temp_context = PresentationContext(
                                                    context.ID, 
                                                    context.AbstractSyntax, 
                                                    [transfer_syntax])
                        temp_context.Result = 0x01
                        self.ACSE.AcceptedPresentationContexts.append(temp_context)
                
                else:
                    # Refuse sop class because of SOP class not supported
                    temp_context = PresentationContext(
                                                    context.ID, 
                                                    context.AbstractSyntax, 
                                                    context.TransferSyntax)
                    temp_context.Result = 0x01
                    self.ACSE.AcceptedPresentationContexts.append(temp_context)
            
            # Issue the A-ASSOCIATE indication (accept) primitive using the ACSE
            assoc_ac = self.ACSE.Accept(assoc_rq)
            
            # Callbacks/Logging
            self.debug_association_accepted(assoc_ac)
            self.AE.on_association_accepted(assoc_ac)
            
            if assoc_ac is None:
                self.Kill()
                return
            
            if self.ACSE.AcceptedPresentationContexts == []:
                # No valid presentation contexts, abort the association
                self.ACSE.Abort(0x02, 0x00)
                self.Kill()
                return
            
            # Assocation established OK
            self.AssociationEstablished = True
            
            while not self._Kill:
                time.sleep(0.001)
                
                # Check with the DIMSE provider for incoming messages
                msg, pcid = self.DIMSE.Receive(False, self.dimse_timeout)
                
                if msg:
                    # DIMSE message received
                    uid = msg.AffectedSOPClassUID

                    # New SOPClass instance
                    obj = UID2SOPClass(uid.value)()
                    
                    matching_sop = False
                    for sop_class in self.ACSE.AcceptedPresentationContexts:
                        if sop_class.ID == pcid:
                            obj.pcid = sop_class.ID
                            obj.sopclass = sop_class.AbstractSyntax
                            obj.transfersyntax = sop_class.TransferSyntax
                            
                            matching_sop = True
                    
                    # If we don't have any matching SOP classes then ???
                    if not matching_sop:
                        pass
                    
                    obj.maxpdulength = self.ACSE.MaxPDULength
                    obj.DIMSE = self.DIMSE
                    obj.ACSE = self.ACSE
                    obj.AE = self.AE
                    obj.assoc = assoc_ac
                    
                    # Run SOPClass in SCP mode
                    obj.SCP(msg)

                # Check for release request
                if self.ACSE.CheckRelease():
                    # Callback trigger
                    self.debug_association_released()
                    self.AE.on_association_released()
                    self.Kill()

                # Check for abort
                if self.ACSE.CheckAbort():
                    # Callback trigger
                    self.debug_association_aborted()
                    self.AE.on_association_aborted()
                    self.Kill()

                # Check if the DULServiceProvider thread is still running
                if not self.DUL.isAlive():
                    self.Kill()

                # Check if idle timer has expired
                if self.DUL.idle_timer_expired():
                    self.Kill()
        
        # If the local AE initiated the Association
        elif self.mode == 'Requestor':
            
            if self.AE.presentation_contexts_scu == []:
                logger.error("No presentation contexts set for the SCU")
                self.Kill()
                return
            
            # Build role extended negotiation - needs updating
            #
            # SCP/SCU Role Negotiation (optional)
            ext = []
            #for context in self.AE.presentation_contexts_scu:
            #    tmp = SCP_SCU_RoleSelectionParameters()
            #    tmp.SOPClassUID = context.AbstractSyntax
            #    tmp.SCURole = 0
            #    tmp.SCPRole = 1
            #    
            #    ext.append(tmp)
            
            # Request an Association via the ACSE
            is_accepted, assoc_rsp = self.ACSE.Request(
                                        self.AE.LocalAE, 
                                        self.RemoteAE,
                                        self.AE.MaxPDULength,
                                        self.AE.presentation_contexts_scu,
                                        userspdu=ext)

            # Association was accepted or rejected
            if isinstance(assoc_rsp, A_ASSOCIATE_ServiceParameters):
                # Association was accepted
                if is_accepted:
                    self.debug_association_accepted(assoc_rsp)
                    self.AE.on_association_accepted(assoc_rsp)
                    
                    # Build supported SOP Classes for the Association
                    self.SOPClassesAsSCU = []
                    for context in self.ACSE.presentation_contexts_accepted:
                        self.SOPClassesAsSCU.append(
                                       (context.ID,
                                        UID2SOPClass(context.AbstractSyntax), 
                                        context.TransferSyntax[0]))
                    
                    if self.ACSE.presentation_contexts_accepted == []:
                        self.ACSE.Abort(0x02, 0x00)
                        self.Kill()
                        return
                        
                    """
                    # No acceptable presentation contexts so release the association
                    # Is it even possible to get here without an accepted context?
                    if self.SOPClassesAsSCU == []:
                        logger.error("No Acceptable Presentation Contexts")
                        self.Abort(0x00)
                        return
                    """
                
                    # Assocation established OK
                    self.AssociationEstablished = True
                    
                    # This seems like it should be event driven rather than
                    #   driven by a loop
                    #
                    # Listen for further messages from the peer
                    while not self._Kill:
                        time.sleep(0.001)
                        
                        # Check for release request
                        if self.ACSE.CheckRelease():
                            # Callback trigger
                            self.debug_association_released()
                            self.AE.on_association_released()
                            self.Kill()
                            return

                        # Check for abort
                        if self.ACSE.CheckAbort():
                            # Callback trigger
                            self.debug_association_aborted()
                            self.AE.on_association_aborted()
                            self.Kill()
                            return
                            
                        # Check if the DULServiceProvider thread is still running
                        if not self.DUL.isAlive():
                            self.Kill()
                            return

                        # Check if idle timer has expired
                        if self.DUL.idle_timer_expired():
                            self.Kill()
                            return
                
                # Association was rejected
                else:
                    self.debug_association_rejected(assoc_rsp)
                    self.AE.on_association_rejected(assoc_rsp)
                    
                    self.AssociationRefused = True
                    self.DUL.Kill()
                    return
            
            # Association was aborted
            elif isinstance(assoc_rsp, A_ABORT_ServiceParameters) or \
                  isinstance(assoc_rsp, A_P_ABORT_ServiceParameters):
                self.debug_association_aborted(assoc_rsp)
                self.AE.on_association_aborted(assoc_rsp)
                
                self.AssociationAborted = True
                self.DUL.Kill()
                return

    @property
    def Established(self):
        return self.AssociationEstablished
    
    
    # DIMSE services provided by the Association
    # Replaces the old assoc.SOPClass.SCU method
    def send_c_store(self, dataset, msg_id=1, priority=2):
        # Select appropriate SOP Class for dataset
        data_sop = dataset.SOPClassUID.__repr__()[1:-1]
        sop_class = UID2SOPClass(data_sop)
        found_match = False
        for scu_sop_class in self.SOPClassesAsSCU:
            if scu_sop_class[1] == sop_class:
                sop_class.pcid = scu_sop_class[0]
                sop_class.sopclass = scu_sop_class[1]
                sop_class.transfersyntax = scu_sop_class[2]
                
                found_match = True
                
        if not found_match:
            logger.error("'%s' is not one of the AE's supported SOP Classes" \
                                                    %UID(sop_class.UID))
            return None
            
        sop_class.maxpdulength = self.ACSE.MaxPDULength
        sop_class.DIMSE = self.DIMSE
        sop_class.AE = self.AE
        sop_class.RemoteAE = self.AE

        # Send the query
        return sop_class().SCU(dataset, msg_id, priority)
        
    def send_c_echo(self, msg_id=1):
        sop_class = VerificationSOPClass()
        
        found_match = False
        for scu_sop_class in self.SOPClassesAsSCU:
            if scu_sop_class[1] == sop_class.__class__:
                sop_class.pcid = scu_sop_class[0]
                sop_class.sopclass = scu_sop_class[1]
                sop_class.transfersyntax = scu_sop_class[2]
                
                found_match = True
                
        if not found_match:
            raise ValueError("'%s' is not listed as one of the AE's "
                    "supported SOP Classes" %sop_class.__class__.__name__)
            
        sop_class.maxpdulength = self.ACSE.MaxPDULength
        sop_class.DIMSE = self.DIMSE
        sop_class.AE = self.AE
        sop_class.RemoteAE = self.AE
        
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
        for scu_sop_class in self.SOPClassesAsSCU:
            if scu_sop_class[1] == sop_class.__class__:
                sop_class.pcid = scu_sop_class[0]
                sop_class.sopclass = scu_sop_class[1]
                sop_class.transfersyntax = scu_sop_class[2]
                
                found_match = True
                
        if not found_match:
            raise ValueError("'%s' is not listed as one of the AE's "
                    "supported SOP Classes" %sop_class.__class__.__name__)
            
        sop_class.maxpdulength = self.ACSE.MaxPDULength
        sop_class.DIMSE = self.DIMSE
        sop_class.AE = self.AE
        sop_class.RemoteAE = self.AE
        
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
        for scu_sop_class in self.SOPClassesAsSCU:
            if scu_sop_class[1] == sop_class.__class__:
                sop_class.pcid = scu_sop_class[0]
                sop_class.sopclass = scu_sop_class[1]
                sop_class.transfersyntax = scu_sop_class[2]
                
                found_match = True
                
        if not found_match:
            raise ValueError("'%s' is not listed as one of the AE's "
                    "supported SOP Classes" %sop_class.__class__.__name__)
            
        sop_class.maxpdulength = self.ACSE.MaxPDULength
        sop_class.DIMSE = self.DIMSE
        sop_class.AE = self.AE
        sop_class.RemoteAE = self.AE
        
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

