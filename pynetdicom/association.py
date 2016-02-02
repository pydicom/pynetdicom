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
from pynetdicom.DIMSEparameters import *
from pynetdicom.DULparameters import *
from pynetdicom.DULprovider import DULServiceProvider
from pynetdicom.SOPclass import *


logger = logging.getLogger('netdicom.association')


class Association(threading.Thread):
    """
    
    
    
    Parameters
    ----------
    local_ae - dict
        The AE title, host and port of the local AE
    peer_socket - socket.socket, optional
        The socket to listen for incoming Association requests
    remote_ae - dict, optional
        If acting as an SCU this is the AE title, host and port of the peer AE

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
        'Acceptor'
    peer_ae - ApplicationEntity
        The peer ApplicationEntity instance
    socket - socket.socket
        The socket to use for connections with the peer AE
    supported_sop_classes_scu
        A list of the supported SOP classes when acting as an SCU
    supported_sop_classes_scp
        A list of the supported SOP classes when acting as an SCP
    """
    def __init__(self, LocalAE, ClientSocket=None, RemoteAE=None):
        
        if not ClientSocket and not RemoteAE:
            raise
        if ClientSocket and RemoteAE:
            raise
        
        if ClientSocket:
            # must respond for request from a remote AE
            self.Mode = 'Acceptor'
        if RemoteAE:
            # must request
            self.Mode = 'Requestor'
        
        self.ClientSocket = ClientSocket
        self.AE = LocalAE
        self.DUL = DULServiceProvider(ClientSocket,
                        MaxIdleSeconds=self.AE.MaxAssociationIdleSeconds)
        self.RemoteAE = RemoteAE
        self.SOPClassesAsSCP = []
        self.SOPClassesAsSCU = []
        self.AssociationEstablished = False
        self.AssociationRefused = None
        
        self.dimse = None
        self.acse = None
        
        self._Kill = False
        
        threading.Thread.__init__(self)
        self.daemon = True

        self.start()

    """
    def GetSOPClass(self, ds):
        
        Does this even do anything?
        
        Parameters
        ----------
        ds
        
        sopclass = UID2SOPClass(ds.SOPClassUID)
    """

    def SCU(self, ds, id):
        
        obj = UID2SOPClass(ds.SOPClassUID)()
        
        try:
            obj.pcid, obj.sopclass, obj.transfersyntax = \
                [x for x in self.SOPClassesAsSCU if x[1] == obj.__class__][0]
        except IndexError:
            raise Exception("SOP Class %s not supported as SCU" % ds.SOPClassUID)

        obj.maxpdulength = self.ACSE.MaxPDULength
        obj.DIMSE = self.DIMSE
        obj.AE = self.AE
        
        return obj.SCU(ds, id)

    def __getattr__(self, attr):
        # while not self.AssociationEstablished:
        #    time.sleep(0.001)
        obj = eval(attr)()
        
        try:
            obj.pcid, obj.sopclass, obj.transfersyntax = \
                [x for x in self.SOPClassesAsSCU if
                 x[1] == obj.__class__][0]
        except IndexError:
            raise #"SOP Class %s not supported as SCU" % attr

        obj.maxpdulength = self.ACSE.MaxPDULength
        obj.DIMSE = self.DIMSE
        obj.AE = self.AE
        obj.RemoteAE = self.AE
        
        return obj

    def Kill(self):
        self._Kill = True
        
        for ii in range(1000):
            if self.DUL.Stop():
                continue
            time.sleep(0.001)
        
        self.DUL.Kill()

    def Release(self, reason):
        """
        Release the association
        
        Parameters
        ----------
        reason - int
            The reason for releasing the association 
        """
        self.ACSE.Release(reason)
        self.Kill()

    def Abort(self, reason):
        self.ACSE.Abort(reason)
        self.Kill()

    def run(self):
        self.ACSE = ACSEServiceProvider(self.DUL)
        self.DIMSE = DIMSEServiceProvider(self.DUL)
        result = None
        diag  = None
        
        if self.Mode == 'Acceptor':
            time.sleep(0.1) # needed because of some thread-related problem. To investiguate.
            if len(self.AE.Associations)>self.AE.MaxNumberOfAssociations:
                result = A_ASSOCIATE_Result_RejectedTransient
                diag = A_ASSOCIATE_Diag_LocalLimitExceeded
            
            assoc = self.ACSE.Accept(self.ClientSocket,
                                     self.AE.AcceptablePresentationContexts, 
                                     result=result, 
                                     diag=diag)
            
            if assoc is None:
                self.Kill()
                return

            # call back
            self.AE.OnAssociateRequest(self)
            # build list of SOPClasses supported
            self.SOPClassesAsSCP = []
            for ss in self.ACSE.AcceptedPresentationContexts:
                self.SOPClassesAsSCP.append((ss[0],
                                             UID2SOPClass(ss[1]), 
                                             ss[2]))

        else:  # Requestor mode
            # build role extended negotiation
            ext = []
            for ii in self.AE.AcceptablePresentationContexts:
                tmp = SCP_SCU_RoleSelectionParameters()
                tmp.SOPClassUID = ii[0]
                tmp.SCURole = 0
                tmp.SCPRole = 1
                ext.append(tmp)
            
            ans = self.ACSE.Request(self.AE.LocalAE, 
                                    self.RemoteAE,
                                    self.AE.MaxPDULength,
                                    self.AE.PresentationContextDefinitionList,
                                    userspdu=ext)
            if ans:
                # call back
                if 'OnAssociateResponse' in self.AE.__dict__:
                    self.AE.OnAssociateResponse(ans)
            else:
                self.AssociationRefused = True
                self.DUL.Kill()
                return
                
            self.SOPClassesAsSCU = []
            for ss in self.ACSE.AcceptedPresentationContexts:
                self.SOPClassesAsSCU.append((ss[0],
                                             UID2SOPClass(ss[1]), 
                                             ss[2]))

        self.AssociationEstablished = True

        # association established. Listening on local and remote interfaces
        while not self._Kill:
            time.sleep(0.001)
            # time.sleep(1)
            # look for incoming DIMSE message
            if self.Mode == 'Acceptor':
                dimsemsg, pcid = self.DIMSE.Receive(Wait=False, Timeout=None)
                if dimsemsg:
                    # dimse message received
                    uid = dimsemsg.AffectedSOPClassUID
                    obj = UID2SOPClass(uid.value)()
                    try:
                        obj.pcid, obj.sopclass, obj.transfersyntax = \
                            [x for x in self.SOPClassesAsSCP
                                if x[0] == pcid][0]
                    except IndexError:
                        raise "SOP Class %s not supported as SCP" % uid
                    obj.maxpdulength = self.ACSE.MaxPDULength
                    obj.DIMSE = self.DIMSE
                    obj.ACSE = self.ACSE
                    obj.AE = self.AE
                    obj.assoc = assoc
                    # run SCP
                    obj.SCP(dimsemsg)

                # check for release request
                if self.ACSE.CheckRelease():
                    self.Kill()

                # check for abort
                if self.ACSE.CheckAbort():
                    self.Kill()
                    return

                # check if the DULServiceProvider thread is still running
                if not self.DUL.isAlive():
                    logger.warning("DUL provider thread is not running any more; quitting")
                    self.Kill()

                # check if idle timer has expired
                logger.debug("checking DUL idle timer")
                if self.DUL.idle_timer_expired():
                    logger.warning('%s: DUL provider idle timer expired' % (self.name))  
                    self.Kill()
