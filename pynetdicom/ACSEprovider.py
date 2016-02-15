#
# Copyright (c) 2012 Patrice Munger
# This file is part of pynetdicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pynetdicom.googlecode.com
#


# This module provides association services

import logging
import socket
import time

from pydicom.uid import UID

from pynetdicom.__init__ import pynetdicom_uid_prefix
from pynetdicom.__version__ import __version__
from pynetdicom.DULparameters import *
from pynetdicom.exceptions import AssociationRefused, NoAcceptablePresentationContext
from pynetdicom.PDU import MaximumLengthParameters


logger = logging.getLogger('pynetdicom.acse')


class ACSEServiceProvider(object):
    """ 
    Association Control Service Provider
    
    Parameters
    ----------
    DUL - pynetdicom.DULprovider.DULServiceProvider
        The DICOM UL service provider instance
    """
    def __init__(self, DUL):
        self.DUL = DUL
        # DICOM Application Context Name, see PS3.7 Annex A.2.1
        self.ApplicationContextName = b'1.2.840.10008.3.1.1.1'

    def Request(self, local_ae, peer_ae, mp, pcdl, userspdu=None, timeout=30):
        """
        Requests an association with a remote AE and waits for association
        response.
        
        Parameters
        ----------
        local_ae - pynetdicom.applicationentity.ApplicationEntity
            The local AE instance
        peer_ae - dict
            A dict containing the peer AE's IP/TCP address, port and title
        mp - int
            Maximum PDV length in bytes
        pcdl - ?
            Presentation Context Definition List
        userpdu - ?
            ???
        timeout - int
            ???
            
        Returns
        -------
        bool
            True if the Association was accepted, false otherwise
        assoc_rsp - pynetdicom..A_ASSOCIATE_ServiceParameters
            The Association response
        """
        self.LocalAE = local_ae
        self.RemoteAE = peer_ae
        self.MaxPDULength = mp

        # Build association service parameters object
        assoc_rq = A_ASSOCIATE_ServiceParameters()
        assoc_rq.ApplicationContextName = self.ApplicationContextName
        assoc_rq.CallingAETitle = self.LocalAE['AET']
        assoc_rq.CalledAETitle = self.RemoteAE['AET']
        
        MaxPDULengthPar = MaximumLengthParameters()
        MaxPDULengthPar.MaximumLengthReceived = mp
        
        if userspdu is not None:
            assoc_rq.UserInformationItem = [MaxPDULengthPar] + userspdu
        else:
            assoc_rq.UserInformationItem = [MaxPDULengthPar]
        
        assoc_rq.CallingPresentationAddress = (self.LocalAE['Address'], 
                                               self.LocalAE['Port'])
        assoc_rq.CalledPresentationAddress = (self.RemoteAE['Address'], 
                                              self.RemoteAE['Port'])
        assoc_rq.PresentationContextDefinitionList = pcdl
        #logger.debug(pcdl)
        
        logger.info("Requesting Association")
        self.DUL.Send(assoc_rq)

        # Association response
        assoc_rsp = self.DUL.Receive(True, timeout)
        
        if not assoc_rsp:
            return False, assoc_rsp
        
        try:
            if assoc_rsp.Result != 'Accepted':
                return False, assoc_rsp
        except AttributeError:
            return False, assoc_rsp

        # Get maximum pdu length from answer
        try:
            self.MaxPDULength = \
                assoc_rsp.UserInformation[0].MaximumLengthReceived
        except:
            self.MaxPDULength = 16000

        # Get accepted presentation contexts
        self.AcceptedPresentationContexts = []
        for cc in assoc_rsp.PresentationContextDefinitionResultList:
            if cc[1] == 0:
                transfer_syntax = UID(cc[2].decode('utf-8'))
                uid = [x[1] for x in pcdl if x[0] == cc[0]][0]
                self.AcceptedPresentationContexts.append((cc[0], 
                                                          uid, 
                                                          transfer_syntax))
        
        return True, assoc_rsp

    def Accept(self, client_socket=None, AcceptablePresentationContexts=None,
               Wait=True, result=None, diag=None):
        """
        When an AE gets a connection on its listen socket it creates an
        Association instance which creates an ACSE instance and forwards
        the socket onwards (`client_socket`).
        
        Waits for an association request from a remote AE. Upon reception
        of the request sends association response based on
        AcceptablePresentationContexts
        
        The acceptability of the proposed Transfer Syntax is checked in the 
        order of appearance in the local AE's SupportedTransferSyntax list
        """
        
        # If the DUL provider hasn't been created
        # I don't think its even possible to get to this stage without
        #   a DUL
        if self.DUL is None:
            self.DUL = DUL(Socket=client_socket)
        
        # 
        assoc = self.DUL.Receive(Wait=True)
        if assoc is None:
            return None

        self.MaxPDULength = assoc.UserInformationItem[0].MaximumLengthReceived

        if result is not None and diag is not None:
            # Association is rejected
            res = assoc
            res.PresentationContextDefinitionList = []
            res.PresentationContextDefinitionResultList = []
            res.Result = result
            res.Diagnostic = diag
            res.UserInformationItem = []
            #res.UserInformation = ass.UserInformation
            self.DUL.Send(res)
            return None

        # analyse proposed presentation contexts
        rsp = []
        self.AcceptedPresentationContexts = []
        # [SOP Class UID, [Transfer Syntax UIDs]]
        acceptable_sop_classes = [x[0] for x in AcceptablePresentationContexts]

        # Our Transfer Syntax are ordered in terms of preference
        for context_definition in assoc.PresentationContextDefinitionList:
            # The proposed_ values come from the peer AE, the acceptable_
            #   values from the local AE
            
            # Presentation Context ID
            pcid = context_definition[0]
            # SOP Class UID
            proposed_sop = context_definition[1].decode('utf-8')
            # Transfer Syntax list - preference ordered
            proposed_ts = [x.decode('utf-8') for x in context_definition[2]]
            
            if proposed_sop in acceptable_sop_classes:
                acceptable_ts = [x[1] for x in AcceptablePresentationContexts
                                 if x[0] == proposed_sop][0]
                
                for transfer_syntax in acceptable_ts:
                    ok = False
  
                    if transfer_syntax in proposed_ts:
                        # accept sop class and ts
                        rsp.append((context_definition[0], 0, transfer_syntax))
                        self.AcceptedPresentationContexts.append(
                            (context_definition[0], 
                             proposed_sop, 
                             UID(transfer_syntax)))
                        
                        ok = True
                        break
                
                if not ok:
                    # Refuse sop class because of TS not supported
                    rsp.append((context_definition[0], 1, ''))
            
            else:
                # Refuse sop class because of SOP class not supported
                rsp.append((context_definition[0], 1, ''))

        # Send response
        res = assoc
        res.PresentationContextDefinitionList = []
        res.PresentationContextDefinitionResultList = rsp
        res.Result = 0
        res.UserInformationItem = assoc.UserInformationItem
        self.DUL.Send(res)
        return assoc

    def Release(self, reason):
        """
        Requests the release of the associations and waits for confirmation.
        A-RELEASE always gives a reason of 'normal' and a result of 
        'affirmative'
        
        Returns
        -------
        response 
            The A-RELEASE-RSP
        """
        release = A_RELEASE_ServiceParameters()
        self.DUL.Send(release)
        response = self.DUL.Receive(Wait=True)

        return response

    def Abort(self, reason):
        """
        Sends an A-ABORT to the peer AE
        
        Parameters
        ----------
        reason - ?
        """
        abort = A_ABORT_ServiceParameters()
        abort.AbortSource = 0
        self.DUL.Send(abort)
        time.sleep(0.5)

    def CheckRelease(self):
        """Checks for release request from the remote AE. Upon reception of
        the request a confirmation is sent"""
        rel = self.DUL.Peek()
        if rel.__class__ == A_RELEASE_ServiceParameters:
            self.DUL.Receive(Wait=False)
            relrsp = A_RELEASE_ServiceParameters()
            relrsp.Result = 0
            self.DUL.Send(relrsp)
            return True
        else:
            return False

    def CheckAbort(self):
        """Checks for abort indication from the remote AE. """
        rel = self.DUL.Peek()
        if rel.__class__ in (A_ABORT_ServiceParameters,
                             A_P_ABORT_ServiceParameters):
            self.DUL.Receive(Wait=False)
            return True
        else:
            return False

    def Status(self):
        return self.DUL.state_machine.current_state()

    def Kill(self):
        self.DUL.Kill()


    # ACSE logging/debugging functions
    # Local AE sending PDU to peer AE
    def debug_send_associate_rq(self, a_associate_rq):
        """
        Placeholder for a function callback. Function will be called 
        immediately prior to encoding and sending an A-ASSOCIATE-RQ to 
        a peer AE
        
        The default implementation is used for logging debugging information
        
        Parameters
        ----------
        a_associate_rq - pynetdicom.PDU.A_ASSOCIATE_RQ_PDU
            The A-ASSOCIATE-RQ PDU instance to be encoded and sent
        """
        pynetdicom_version = 'PYNETDICOM_' + ''.join(__version__.split('.'))
        
        # Shorthand
        assoc_rq = a_associate_rq
        
        app_context   = assoc_rq.ApplicationContext.__repr__()[1:-1]
        pres_contexts = assoc_rq.PresentationContext
        user_info     = assoc_rq.UserInformation
        
        s = ['Request Parameters:']
        s.append('====================== BEGIN A-ASSOCIATE-RQ ================'
                '=====')
        
        s.append('Our Implementation Class UID:      %s' %pynetdicom_uid_prefix)
        s.append('Our Implementation Version Name:   %s' %pynetdicom_version)
        s.append('Application Context Name:    %s' %app_context)
        s.append('Calling Application Name:    %s' %assoc_rq.CallingAETitle)
        s.append('Called Application Name:     %s' %assoc_rq.CalledAETitle)
        s.append('Our Max PDU Receive Size:    %s' %user_info.MaximumLength)
        
        # Presentation Contexts
        if len(pres_contexts) == 1:
            s.append('Presentation Context:')
        else:
            s.append('Presentation Contexts:')

        for context in pres_contexts:
            s.append('  Context ID:        %s (Proposed)' %(context.ID))
            s.append('    Abstract Syntax: =%s' %context.AbstractSyntax)
            
            if 'SCU' in context.__dict__.keys():
                scp_scu_role = '%s/%s' %(context.SCP, context.SCU)
            else:
                scp_scu_role = 'Default'
            s.append('    Proposed SCP/SCU Role: %s' %scp_scu_role)
            
            # Transfer Syntaxes
            if len(context.TransferSyntax) == 1:
                s.append('    Proposed Transfer Syntax:')
            else:
                s.append('    Proposed Transfer Syntaxes:')
                
            for ts in context.TransferSyntax:
                s.append('      =%s' %ts.name)
        
        ext_nego = 'None'
        #if assoc_rq.UserInformation.ExtendedNegotiation is not None:
        #    ext_nego = 'Yes'
        s.append('Requested Extended Negotiation: %s' %ext_nego)
        
        usr_id = 'None'
        if assoc_rq.UserInformation.UserIdentity is not None:
            usr_id = 'Yes'
        s.append('Requested User Identity Negotiation: %s' %usr_id)
        s.append('======================= END A-ASSOCIATE-RQ =================='
                '====')
        
        for line in s:
            logger.debug(line)
        
    def debug_send_associate_ac(self, a_associate_ac):
        """
        Placeholder for a function callback. Function will be called 
        immediately prior to encoding and sending an A-ASSOCIATE-AC to a peer AE
        
        Parameters
        ----------
        a_associate_ac - pynetdicom.PDU.A_ASSOCIATE_AC_PDU
            The A-ASSOCIATE-AC PDU instance
        """
        pynetdicom_version = 'PYNETDICOM_' + ''.join(__version__.split('.'))
                
        # Shorthand
        assoc_ac = a_associate_ac
        
        # Needs some cleanup
        app_context   = assoc_ac.ApplicationContext.__repr__()[1:-1]
        pres_contexts = assoc_ac.PresentationContext
        user_info     = assoc_ac.UserInformation
        
        responding_ae = 'resp. AP Title'
        
        our_class_uid = pynetdicom_uid_prefix
        our_version = 'PYNETDICOM_' + ''.join(__version__.split('.'))
        
        s = ['Accept Parameters:']
        s.append('====================== BEGIN A-ASSOCIATE-AC ================'
                '=====')
        
        s.append('Our Implementation Class UID:      %s' %our_class_uid)
        s.append('Our Implementation Version Name:   %s' %our_version)
        s.append('Application Context Name:    %s' %app_context)
        s.append('Responding Application Name: %s' %responding_ae)
        s.append('Our Max PDU Receive Size:    %s' %user_info.MaximumLength)
        s.append('Presentation Contexts:')
        
        for item in pres_contexts:
            s.append('  Context ID:        %s (%s)' %(item.ID, item.Result))
            
            # If Presentation Context was accepted
            if item.ResultReason == 0:
                if item.SCP is None and item.SCU is None:
                    ac_scp_scu_role = 'Default'
                else:
                    ac_scp_scu_role = '%s/%s' %(item.SCP, item.SCU)
                s.append('    Accepted SCP/SCU Role: %s' %ac_scp_scu_role)
                s.append('    Accepted Transfer Syntax: =%s' %item.TransferSyntax)
                
        ext_nego = 'None'
        #if assoc_ac.UserInformation.ExtendedNegotiation is not None:
        #    ext_nego = 'Yes'
        s.append('Accepted Extended Negotiation: %s' %ext_nego)
        
        usr_id = 'None'
        if assoc_ac.UserInformation.UserIdentity is not None:
            usr_id = 'Yes'
        
        s.append('User Identity Negotiation Response:  %s' %usr_id)
        s.append('======================= END A-ASSOCIATE-AC =================='
                '====')
        
        for line in s:
            logger.debug(line)
        
    def debug_send_associate_rj(self, a_associate_rj):
        """
        Placeholder for a function callback. Function will be called 
        immediately prior to encoding and sending an A-ASSOCIATE-RJ to a peer AE
        
        Parameters
        ----------
        a_associate_rj - pynetdicom.PDU.A_ASSOCIATE_RJ_PDU
            The A-ASSOCIATE-RJ PDU instance
        """
        pass
    
    def debug_send_data_tf(self, p_data_tf):
        """
        Placeholder for a function callback. Function will be called 
        immediately prior to encoding and sending an P-DATA-TF to a peer AE
        
        Parameters
        ----------
        a_release_rq - pynetdicom.PDU.P_DATA_TF_PDU
            The P-DATA-TF PDU instance
        """
        pass
    
    def debug_send_release_rq(self, a_release_rq):
        """
        Placeholder for a function callback. Function will be called 
        immediately prior to encoding and sending an A-RELEASE-RQ to a peer AE
        
        Parameters
        ----------
        a_release_rq - pynetdicom.PDU.A_RELEASE_RQ_PDU
            The A-RELEASE-RQ PDU instance
        """
        pass
        
    def debug_send_release_rp(self, a_release_rp):
        """
        Placeholder for a function callback. Function will be called 
        immediately prior to encoding and sending an A-RELEASE-RP to a peer AE
        
        Parameters
        ----------
        a_release_rp - pynetdicom.PDU.A_RELEASE_RP_PDU
            The A-RELEASE-RP PDU instance
        """
        pass
        
    def debug_send_abort(self, a_abort):
        """
        Placeholder for a function callback. Function will be called 
        immediately prior to encoding and sending an A-ABORT to a peer AE
        
        Parameters
        ----------
        a_abort - pynetdicom.PDU.A_ABORT_PDU
            The A-ABORT PDU instance
        """
        pass

    # Local AE receiving PDU from peer AE
    def debug_receive_associate_rq(self, a_associate_rq):
        """
        Placeholder for a function callback. Function will be called 
        immediately after receiving and decoding an A-ASSOCIATE-RQ
        
        Parameters
        ----------
        a_associate_rq - pynetdicom.PDU.A_ASSOCIATE_RQ_PDU
            The A-ASSOCIATE-RQ PDU instance
        """
        # Shorthand
        assoc_rq = a_associate_rq
        
        app_context   = assoc_rq.ApplicationContext.__repr__()[1:-1]
        pres_contexts = assoc_rq.PresentationContext
        user_info     = assoc_rq.UserInformation
        
        responding_ae = 'resp. AP Title'
        their_class_uid = 'unknown'
        their_version = 'unknown'
        
        if user_info.ImplementationClassUID:
            their_class_uid = user_info.ImplementationClassUID
        if user_info.ImplementationVersionName:
            their_version = user_info.ImplementationVersionName
        
        s = ['Request Parameters:']
        s.append('====================== BEGIN A-ASSOCIATE-RQ ================'
                '=====')
        s.append('Their Implementation Class UID:    %s' %their_class_uid)
        s.append('Their Implementation Version Name: %s' %their_version)
        s.append('Application Context Name:    %s' %app_context)
        s.append('Calling Application Name:    %s' %assoc_rq.CallingAETitle)
        s.append('Called Application Name:     %s' %assoc_rq.CalledAETitle)
        s.append('Their Max PDU Receive Size:  %s' %user_info.MaximumLength)
        s.append('Presentation Contexts:')
        for item in pres_contexts:
            s.append('  Context ID:        %s (Proposed)' %item.ID)
            s.append('    Abstract Syntax: =%s' %item.AbstractSyntax)
            
            if item.SCU is None and item.SCP is None:
                scp_scu_role = 'Default'
            else:
                scp_scu_role = '%s/%s' %(item.SCP, item.SCU)
            
            s.append('    Proposed SCP/SCU Role: %s' %scp_scu_role)
            s.append('    Proposed Transfer Syntax(es):')
            for ts in item.TransferSyntax:
                s.append('      =%s' %ts)
        
        ext_nego = 'None'
        #if assoc_rq.UserInformation.ExtendedNegotiation is not None:
        #    ext_nego = 'Yes'
        s.append('Requested Extended Negotiation: %s' %ext_nego)
        
        usr_id = 'None'
        if user_info.UserIdentity is not None:
            usr_id = 'Yes'
        s.append('Requested User Identity Negotiation: %s' %usr_id)
        s.append('======================= END A-ASSOCIATE-RQ =================='
                '====')
        
        for line in s:
            logger.debug(line)
        
    def debug_receive_associate_ac(self, a_associate_ac):
        """
        Placeholder for a function callback. Function will be called 
        immediately after receiving and decoding an A-ASSOCIATE-AC
        
        The default implementation is used for logging debugging information
        
        Most of this should be moved to on_association_accepted()
        
        Parameters
        ----------
        a_associate_ac - pynetdicom.PDU.A_ASSOCIATE_AC_PDU
            The A-ASSOCIATE-AC PDU instance
        """
        pynetdicom_version = 'PYNETDICOM_' + ''.join(__version__.split('.'))
                
        # Shorthand
        assoc_ac = a_associate_ac
        
        # Needs some cleanup
        app_context   = assoc_ac.ApplicationContext.__repr__()[1:-1]
        pres_contexts = assoc_ac.PresentationContext
        user_info     = assoc_ac.UserInformation
        
        responding_ae = 'resp. AP Title'
        their_class_uid = 'unknown'
        their_version = 'unknown'
        
        if user_info.ImplementationClassUID:
            their_class_uid = user_info.ImplementationClassUID
        if user_info.ImplementationVersionName:
            their_version = user_info.ImplementationVersionName
        
        s = ['Accept Parameters:']
        s.append('====================== BEGIN A-ASSOCIATE-AC ================'
                '=====')
        
        s.append('Their Implementation Class UID:    %s' %their_class_uid)
        s.append('Their Implementation Version Name: %s' %their_version)
        s.append('Application Context Name:    %s' %app_context)
        s.append('Calling Application Name:    %s' %assoc_ac.CallingAETitle)
        s.append('Called Application Name:     %s' %assoc_ac.CalledAETitle)
        s.append('Their Max PDU Receive Size:  %s' %user_info.MaximumLength)
        s.append('Presentation Contexts:')
        
        for item in pres_contexts:
            s.append('  Context ID:        %s (%s)' %(item.ID, item.Result))
            s.append('    Abstract Syntax: =%s' %'FIXME')

            if item.ResultReason == 0:
                if item.SCP is None and item.SCU is None:
                    ac_scp_scu_role = 'Default'
                    rq_scp_scu_role = 'Default'
                else:
                    ac_scp_scu_role = '%s/%s' %(item.SCP, item.SCU)
                s.append('    Proposed SCP/SCU Role: %s' %rq_scp_scu_role)
                s.append('    Accepted SCP/SCU Role: %s' %ac_scp_scu_role)
                s.append('    Accepted Transfer Syntax: =%s' 
                                            %item.TransferSyntax)
        
        ext_nego = 'None'
        #if assoc_ac.UserInformation.ExtendedNegotiation is not None:
        #    ext_nego = 'Yes'
        s.append('Accepted Extended Negotiation: %s' %ext_nego)
        
        usr_id = 'None'
        if assoc_ac.UserInformation.UserIdentity is not None:
            usr_id = 'Yes'
        
        s.append('User Identity Negotiation Response:  %s' %usr_id)
        s.append('======================= END A-ASSOCIATE-AC =================='
                '====')
        
        for line in s:
            logger.debug(line)
        
    def debug_receive_associate_rj(self, a_associate_rj):
        """
        Placeholder for a function callback. Function will be called 
        immediately after receiving and decoding an A-ASSOCIATE-RJ
        
        Parameters
        ----------
        a_associate_rj - pynetdicom.PDU.A_ASSOCIATE_RJ_PDU
            The A-ASSOCIATE-RJ PDU instance
        """
        # Shorthand
        assoc_rj = a_associate_rj
        
        s = ['Reject Parameters:']
        s.append('====================== BEGIN A-ASSOCIATE-RJ ================'
                '=====')
        s.append('Rejection Result: %s' %assoc_rj.ResultString)
        s.append('Rejection Source: %s' %assoc_rj.SourceString)
        s.append('Rejection Reason: %s' %assoc_rj.Reason)
        s.append('======================= END A-ASSOCIATE-RJ =================='
                '====')
        for line in s:
            logger.debug(line)
    
    def debug_receive_data_tf(self, p_data_tf):
        """
        Placeholder for a function callback. Function will be called 
        immediately after receiving and decoding an P-DATA-TF
        
        Parameters
        ----------
        a_release_rq - pynetdicom.PDU.P_DATA_TF_PDU
            The P-DATA-TF PDU instance
        """
        # Shorthand
        p_data = p_data_tf
        
        s = ['Data Parameters:']
        s.append('========================= BEGIN P-DATA-TF ==================='
                '=====')
        s.append('Number of PDVs Received: %d' %len(p_data.PDVs))
        
        for ii, pdv in enumerate(p_data.PDVs):
            s.append('PDV %d' %(ii + 1))
            s.append('  Presentation context ID: %s' %pdv.ID)
            s.append('  Message control header byte: %s' %pdv.MessageControlHeader)
            s.append('  Size: %s bytes' %pdv.Length)
        
        s.append('========================== END P-DATA-TF ===================='
                '====')
        for line in s:
            logger.debug(line)
        
    def debug_receive_release_rq(self, a_release_rq):
        """
        Placeholder for a function callback. Function will be called 
        immediately after receiving and decoding an A-RELEASE-RQ
        
        Parameters
        ----------
        a_release_rq - pynetdicom.PDU.A_RELEASE_RQ_PDU
            The A-RELEASE-RQ PDU instance
        """
        pass
        
    def debug_receive_release_rp(self, a_release_rp):
        """
        Placeholder for a function callback. Function will be called 
        immediately after receiving and decoding an A-RELEASE-RP
        
        Parameters
        ----------
        a_release_rp - pynetdicom.PDU.A_RELEASE_RP_PDU
            The A-RELEASE-RP PDU instance
        """
        pass
        
    def debug_receive_abort(self, a_abort):
        """
        Placeholder for a function callback. Function will be called 
        immediately after receiving and decoding an A-ABORT
        
        Parameters
        ----------
        a_abort - pynetdicom.PDU.A_ABORT_PDU
            The A-ABORT PDU instance
        """
        
        s = ['Abort Parameters:']
        s.append('========================== BEGIN A-ABORT ===================='
                '=====')
        s.append('Abort Source: %s' %a_abort.Source)
        s.append('Abort Reason: %s' %a_abort.Reason)
        s.append('=========================== END A-ABORT ====================='
                '====')
        for line in s:
            logger.debug(line)

