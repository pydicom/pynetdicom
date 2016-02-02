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


logger = logging.getLogger('netdicom.ACSE')


class ACSEServiceProvider(object):
    """ 
    
    """
    def __init__(self, DUL):
        self.DUL = DUL
        self.ApplicationContextName = b'1.2.840.10008.3.1.1.1'

    def Request(self, localAE, remoteAE, mp, pcdl, userspdu=None, timeout=30):
        """Requests an association with a remote AE and waits for association
        response."""
        self.LocalAE = localAE
        self.RemoteAE = remoteAE
        self.MaxPDULength = mp

        # build association service parameters object
        assrq = A_ASSOCIATE_ServiceParameters()
        assrq.ApplicationContextName = self.ApplicationContextName
        assrq.CallingAETitle = self.LocalAE['AET']
        assrq.CalledAETitle = self.RemoteAE['AET']
        MaxPDULengthPar = MaximumLengthParameters()
        MaxPDULengthPar.MaximumLengthReceived = mp
        
        if userspdu is not None:
            assrq.UserInformation = [MaxPDULengthPar] + userspdu
        else:
            assrq.UserInformation = [MaxPDULengthPar]
        assrq.CallingPresentationAddress = (
            self.LocalAE['Address'], self.LocalAE['Port'])
        assrq.CalledPresentationAddress = (
            self.RemoteAE['Address'], self.RemoteAE['Port'])
        assrq.PresentationContextDefinitionList = pcdl
        logger.debug(pcdl)
        # send A-Associate request
        logger.debug("Sending Association Request")
        
        self.DUL.Send(assrq)

        # get answer
        logger.debug("Waiting for Association Response")
        assrsp = self.DUL.Receive(True, timeout)
        
        if not assrsp:
            return False
        
        logger.debug(assrsp)

        try:
            if assrsp.Result != 'Accepted':
                return False
        except AttributeError:
            return False

        # Get maximum pdu length from answer
        try:
            self.MaxPDULength = assrsp.UserInformation[0].MaximumLengthReceived
        except:
            self.MaxPDULength = 16000

        # Get accepted presentation contexts
        self.AcceptedPresentationContexts = []
        for cc in assrsp.PresentationContextDefinitionResultList:
            if cc[1] == 0:
                uid = [x[1] for x in pcdl if x[0] == cc[0]][0]
                self.AcceptedPresentationContexts.append(
                    (cc[0], uid, UID(str(cc[2]))))
        return True

    def Accept(self, client_socket=None, AcceptablePresentationContexts=None,
               Wait=True, result=None, diag=None):
        """Waits for an association request from a remote AE. Upon reception
        of the request sends association response based on
        AcceptablePresentationContexts"""
        if self.DUL is None:
            self.DUL = DUL(Socket=client_socket)
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

        for context_definition in assoc.PresentationContextDefinitionList:
            # Presentation Context ID
            pcid = context_definition[0]
            # SOP Class UID
            proposed_sop = context_definition[1].decode('utf-8')
            # Transfer Syntax list
            proposed_ts = [x.decode('utf-8') for x in context_definition[2]]
            
            if proposed_sop in acceptable_sop_classes:
                acceptable_ts = [x[1] for x in AcceptablePresentationContexts
                                 if x[0] == proposed_sop][0]
                for transfer_syntax in proposed_ts:
                    ok = False
  
                    if transfer_syntax in acceptable_ts:
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

    def Release(self, Reason):
        """
        Requests the release of the associations and waits for confirmation.
        A-RELEASE always gives a reason of 'normal' and a result of 
        'affirmative'
        
        Returns
        -------
        rsp 
            The A-RELEASE-RSP
        """
        rel = A_RELEASE_ServiceParameters()
        #print('ACSE - Before sending release')
        #print('ACSE - Release:' , rel)
        self.DUL.Send(rel)
        #print(self.DUL.SM.CurrentState)
        #print('ACSE - After sending release')
        rsp = self.DUL.Receive(Wait=True)
        #print('ACSE - After receiving response')
        return rsp

    def Abort(self):
        """Signifies the abortion of the association."""
        ab = A_ABORT_ServiceParameters()
        self.DUL.Send(rel)
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
        return self.DUL.SM.CurrentState()

    def Kill(self):
        self.DUL.Kill()
