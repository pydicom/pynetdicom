#
# Copyright (c) 2012 Patrice Munger
# This file is part of pynetdicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pynetdicom.googlecode.com
#


# This module provides association services
from DULparameters import * 
from PDU import MaximumLengthParameters
from dicom.UID import UID
import socket
import time
DEBUG=True
import logging
logger = logging.getLogger('pynetdicom.ACSE')


class AssociationRefused(Exception):
    def __init__(self, data=None):
        self.data = data

class NoAcceptablePresentationContext(Exception):
    def __init__(self, data=None):
        self.data = data


class ACSEServiceProvider(object):
    def __init__(self, DUL):
        self.DUL = DUL
        self.ApplicationContextName = '1.2.840.10008.3.1.1.1'

        
    def Request(self, localAE, remoteAE, mp, pcdl, userspdu = None):
        """Requests an association with a remote AE and waits for association response."""
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
        if userspdu <> None:
            assrq.UserInformation = [MaxPDULengthPar]+userspdu
        else:
            assrq.UserInformation = [MaxPDULengthPar]
        assrq.CallingPresentationAddress = (self.LocalAE['Address'],self.LocalAE['Port'])
        assrq.CalledPresentationAddress = (self.RemoteAE['Address'],self.RemoteAE['Port'])
        assrq.PresentationContextDefinitionList = pcdl
        if DEBUG: print pcdl
        # send A-Associate request 
        if DEBUG: print "Sending Association Request ...",
        self.DUL.Send(assrq)
        if DEBUG: print " done"     

        # get answer
        if DEBUG: print "Waiting for Association Response ...",
        
        assrsp = self.DUL.Receive(True)
        if DEBUG: print " done"
        if not assrsp:
            return False
            raise AssociationRefused
        if DEBUG: print assrsp
                 
        if assrsp.Result <> 'Accepted':
            return False
            raise AssociationRefused

        # Get maximum pdu length from answer
        #print assrsp
        try:
            self.MaxPDULength = assrsp.UserInformation[0].MaximumLengthReceived
        except:
            self.MaxPDULength = 16000
        print assrsp.UserInformation[0].MaximumLengthReceived
        # Get accepted presentation contexts
        self.AcceptedPresentationContexts = []
        for cc in assrsp.PresentationContextDefinitionResultList:
            if cc[1] == 0:
                uid = [ x[1] for x in pcdl if x[0] == cc[0] ][0]
                self.AcceptedPresentationContexts.append((cc[0],uid,UID(cc[2])))
        return True


    def Accept(self,client_socket = None, AcceptablePresentationContexts = None, Wait=True):
        """Waits for an association request from a remote AE. Upon reception of the request
        sends association response based on AcceptablePresentationContexts"""
        if self.DUL == None:
            self.DUL = DUL(Socket=client_socket)
        ass = self.DUL.Receive(Wait=True)
        if ass == None:
            return None
        
        self.MaxPDULength = ass.UserInformation[0].MaximumLengthReceived
        
        # analyse proposed presentation contexts
        rsp = []
        self.AcceptedPresentationContexts = []
        acceptable_sop = [x[0] for x in AcceptablePresentationContexts]
        for ii in ass.PresentationContextDefinitionList:
            pcid = ii[0]
            proposed_sop = ii[1]
            proposed_ts = ii[2]
            if proposed_sop in acceptable_sop:
                acceptable_ts = [x[1] for x in AcceptablePresentationContexts if x[0]==proposed_sop][0]
                for ts in proposed_ts:
                    ok = False
                    if ts in acceptable_ts:
                        # accept sop class and ts
                        rsp.append((ii[0],0,ts))
                        self.AcceptedPresentationContexts.append((ii[0],proposed_sop,UID(ts)))
                        ok = True
                        break
                if not ok:
                    # Refuse sop class because of TS not supported
                    rsp.append((ii[0],1,''))
            else:
                # Refuse sop class because of SOP class not supported
                rsp.append((ii[0],1,''))

        # Send response
        res = ass
        res.PresentationContextDefinitionList = []
        res.PresentationContextDefinitionResultList = rsp
        res.Result = 0
        res.UserInformation = []
        #res.UserInformation = ass.UserInformation
        #print res
        self.DUL.Send(res)
        #print "response sent"
        return True


#    def Receive(self, Wait):
#        return self.DUL.ReceiveACSE(Wait)
        
    def Release(self, Reason):
        """Requests the release of the associations and waits for confirmation"""
        rel = A_RELEASE_ServiceParameters()
        rel.Reason = Reason
        self.DUL.Send(rel)
        rsp = self.DUL.Receive(Wait=True)
        return rsp
        #self.DUL.Kill()

    def Abort(self):
        """Signifies the abortion of the association."""
        ab = A_ABORT_ServiceParameters()
        self.DUL.Send(rel)
        time.sleep(0.5)
        #self.DUL.Kill()
        
    def CheckRelease(self):
        """Checks for release request from the remote AE. Upon reception of the request
        a confirmation is sent"""
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
        if rel.__class__ in (A_ABORT_ServiceParameters, A_P_ABORT_ServiceParameters):
            self.DUL.Receive(Wait=False)
            return True
        else:
            return False        

        
    def Status(self):
        return self.DUL.SM.CurrentState()

    def Kill(self):
        self.DUL.Kill()

