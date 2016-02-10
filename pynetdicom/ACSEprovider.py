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
        mp - ?
            ???
        pcdl - ?
            ???
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
            assoc_rq.UserInformation = [MaxPDULengthPar] + userspdu
        else:
            assoc_rq.UserInformation = [MaxPDULengthPar]
        
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

        self.MaxPDULength = assoc.UserInformation[0].MaximumLengthReceived

        if result is not None and diag is not None:
            # Association is rejected
            res = assoc
            res.PresentationContextDefinitionList = []
            res.PresentationContextDefinitionResultList = []
            res.Result = result
            res.Diagnostic = diag
            res.UserInformation = []
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
        #res.UserInformation = []
        #res.UserInformation = [ass.UserInformation[0]]
        res.UserInformation = assoc.UserInformation
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
