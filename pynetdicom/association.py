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


logger = logging.getLogger('pynetdicom.assoc')


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
        
        # Received a connection from a peer AE
        if ClientSocket:
            self.mode = 'Acceptor'
        # Initiated a connection to a peer AE
        if RemoteAE:
            self.mode = 'Requestor'
        
        self.ClientSocket = ClientSocket
        self.AE = LocalAE
        self.DUL = DULServiceProvider(ClientSocket,
                        timeout_seconds=self.AE.MaxAssociationIdleSeconds,
                        local_ae=self.AE)
        
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
        """
        The main Association thread
        """
        # Set new ACSE and DIMSE providers
        self.ACSE = ACSEServiceProvider(self.DUL)
        self.DIMSE = DIMSEServiceProvider(self.DUL)
        
        result = None
        diag  = None
        
        # If the remote AE initiated the Association
        if self.mode == 'Acceptor':
            
            # needed because of some thread-related problem. To investiguate.
            time.sleep(0.1)
            
            # If we are already at the limit of the number of associations
            if len(self.AE.Associations) > self.AE.MaxNumberOfAssociations:
                # Reject the Association and give the reason
                result = A_ASSOCIATE_Result_RejectedTransient
                diag = A_ASSOCIATE_Diag_LocalLimitExceeded
            
            # Send the Association response via the ACSE
            assoc = self.ACSE.Accept(self.ClientSocket,
                                     self.AE.AcceptablePresentationContexts, 
                                     result=result, 
                                     diag=diag)
            
            if assoc is None:
                self.Kill()
                return

            # Callbacks
            self.AE.OnAssociateRequest(self)
            self.AE.on_association_accepted()
            
            # Build supported SOP Classes for the Association
            self.SOPClassesAsSCP = []
            for context in self.ACSE.AcceptedPresentationContexts:
                self.SOPClassesAsSCP.append((context[0],
                                             UID2SOPClass(context[1]), 
                                             context[2]))
        
        # If the local AE initiated the Association
        else:  # Requestor mode
            
            # Build role extended negotiation
            ext = []
            for ii in self.AE.AcceptablePresentationContexts:
                tmp = SCP_SCU_RoleSelectionParameters()
                tmp.SOPClassUID = ii[0]
                tmp.SCURole = 0
                tmp.SCPRole = 1
                ext.append(tmp)
            
            # Request an Association via the ACSE
            ans = self.ACSE.Request(self.AE.LocalAE, 
                                    self.RemoteAE,
                                    self.AE.MaxPDULength,
                                    self.AE.PresentationContextDefinitionList,
                                    userspdu=ext)
            
            # Reply from the remote AE
            if ans:
                # Callback trigger
                if 'OnAssociateResponse' in self.AE.__dict__:
                    self.AE.OnAssociateResponse(ans)
                    
            else:
                # Callback trigger
                self.AE.on_association_refused()
                self.AssociationRefused = True
                self.DUL.Kill()
                return
            
            # Build supported SOP Classes for the Association
            self.SOPClassesAsSCU = []
            for context in self.ACSE.AcceptedPresentationContexts:
                self.SOPClassesAsSCU.append((context[0],
                                             UID2SOPClass(context[1]), 
                                             context[2]))

        # Assocation established OK
        self.AssociationEstablished = True
        
        # Callback trigger
        self.AE.on_association_established()

        # If acting as an SCP, listen for further messages on the Association
        while not self._Kill:
            time.sleep(0.001)
            
            if self.mode == 'Acceptor':
                # Check with the DIMSE provider for incoming messages
                msg, pcid = self.DIMSE.Receive(Wait=False, Timeout=None)
                if msg:
                    # DIMSE message received
                    uid = msg.AffectedSOPClassUID
                    # New SOPClass instance
                    obj = UID2SOPClass(uid.value)()
                    
                    print(uid, obj)
                    
                    matching_sop = False
                    for sop_class in self.SOPClassesAsSCP:
                        # (pc id, SOPClass(), TransferSyntax)
                        if sop_class[0] == pcid:
                            obj.pcid = sop_class[0]
                            obj.sopclass = sop_class[1]
                            obj.transfersyntax = sop_class[2]
                            
                            matching_sop = True
                    
                    # If we don't have any matching SOP classes then ???
                    if not matching_sop:
                        pass
                    
                    obj.maxpdulength = self.ACSE.MaxPDULength
                    obj.DIMSE = self.DIMSE
                    obj.ACSE = self.ACSE
                    obj.AE = self.AE
                    obj.assoc = assoc
                    
                    # Callback trigger
                    self.AE.on_receive_dimse_message(obj, msg)
                    
                    # Run SOPClass in SCP mode
                    obj.SCP(msg)

                # Check for release request
                if self.ACSE.CheckRelease():
                    # Callback trigger
                    self.AE.on_association_released()
                    self.Kill()

                # Check for abort
                if self.ACSE.CheckAbort():
                    # Callback trigger
                    self.AE.on_association_aborted()
                    self.Kill()
                    return

                # Check if the DULServiceProvider thread is still running
                if not self.DUL.isAlive():
                    self.Kill()

                # Check if idle timer has expired
                if self.DUL.idle_timer_expired():
                    self.Kill()
