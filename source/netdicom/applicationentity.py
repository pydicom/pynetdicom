#
# Copyright (c) 2012 Patrice Munger
# This file is part of pynetdicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pynetdicom.googlecode.com
#

import threading
import time
import socket
import os
import sys
import select
import platform
from SOPclass import *
from dicom.UID import ExplicitVRLittleEndian, ImplicitVRLittleEndian, ExplicitVRBigEndian, UID
from DULprovider import DULServiceProvider
from DIMSEprovider import DIMSEServiceProvider
from ACSEprovider import ACSEServiceProvider
from DIMSEparameters import *



class Association(threading.Thread):
    def __init__(self, LocalAE, ClientSocket = None, RemoteAE = None):
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
        self.DUL=DULServiceProvider(ClientSocket)
        self.AE=LocalAE
        self.RemoteAE = RemoteAE
        self._Kill = False  
        threading.Thread.__init__(self)
        self.SOPClassesAsSCP = []
        self.SOPClassesAsSCU = []
        self.AssociationEstablished = False
        self.AssociationRefused = None
        self.start()

    def GetSOPClass(self, ds):
        sopclass = UID2SOPClass(ds.SOPClassUID)


    def SCU(self, ds, id):
        obj = UID2SOPClass(ds.SOPClassUID)()
        try:
            obj.pcid, obj.sopclass, obj.transfersyntax = \
                      [x for x in self.SOPClassesAsSCU if \
                       x[1]==obj.__class__][0]
        except IndexError:
            return
            raise Exception, "SOP Class %s not supported as SCU"
            

        obj.maxpdulength = self.ACSE.MaxPDULength
        obj.DIMSE = self.DIMSE
        obj.AE = self.AE
        return obj.SCU(ds, id)


    def __getattr__(self, attr):
        #while not self.AssociationEstablished:
        #    time.sleep(0.001)

        obj = eval(attr)()
        try:
            obj.pcid, obj.sopclass, obj.transfersyntax = \
                      [x for x in self.SOPClassesAsSCU if \
                       x[1]==obj.__class__][0]
        except IndexError:
            return
            raise "SOP Class %s not supported as SCU" % attr
        obj.maxpdulength = self.ACSE.MaxPDULength
        obj.DIMSE = self.DIMSE
        obj.AE = self.AE
        return obj

                
    def Kill(self):
        self._Kill = True
	for ii in range(100):
	    if self.DUL.Stop(): return
	    time.sleep(0.001)
	self.DUL.Kill()


    def Release(self, reason):
        self.ACSE.Release(reason)
	self.Kill()



    def Abort(self, reason):
        self.ACSE.Abort(reason)     
	self.Kill()



    def run(self):
        self.ACSE = ACSEServiceProvider(self.DUL)
        self.DIMSE = DIMSEServiceProvider(self.DUL)
        if self.Mode == 'Acceptor':
            self.ACSE.Accept(self.ClientSocket,
                             self.AE.AcceptablePresentationContexts)
            # call back
            self.AE.OnAssociateRequest(self)
            # build list of SOPClasses supported
            self.SOPClassesAsSCP = []
            for ss in self.ACSE.AcceptedPresentationContexts:
                self.SOPClassesAsSCP.append( (ss[0], \
                                              UID2SOPClass(ss[1]), ss[2]))

        else: # Requestor mode
            # build role extended negociation
            ext = []
            for ii in self.AE.AcceptablePresentationContexts:
                tmp = SCP_SCU_RoleSelectionParameters()
                tmp.SOPClassUID = ii[0]
                tmp.SCURole = 0
                tmp.SCPRole = 1
                ext.append(tmp)
            
            ans = self.ACSE.Request(self.AE.LocalAE, self.RemoteAE,
                                    self.AE.MaxPDULength,
                                    self.AE.PresentationContextDefinitionList,\
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
                self.SOPClassesAsSCU.append( (ss[0], 
                                              UID2SOPClass(ss[1]), ss[2]))

	self.AssociationEstablished = True

        # association established. Listening on local and remote interfaces
        while not self._Kill:
            time.sleep(0.001)
            # look for incoming DIMSE message
            if self.Mode == 'Acceptor':
                dimsemsg,pcid = self.DIMSE.Receive(Wait=False, Timeout=None)
                if dimsemsg:
                    # dimse message received
                    uid = dimsemsg.AffectedSOPClassUID
                    obj = UID2SOPClass(uid.value)()
                    try:
                        obj.pcid, obj.sopclass, obj.transfersyntax = \
                                  [x for x in self.SOPClassesAsSCP \
                                   if x[0]==pcid][0]
                    except IndexError:
                        raise "SOP Class %s not supported as SCP" % uid
                    obj.maxpdulength = self.ACSE.MaxPDULength
                    obj.DIMSE = self.DIMSE
                    obj.ACSE = self.ACSE
                    obj.AE = self.AE

                    # run SCP
                    obj.SCP(dimsemsg)

                # check for release request
                if self.ACSE.CheckRelease():
                    print "Release requested"
                    self.Kill()

                # check for abort
                if self.ACSE.CheckAbort():
                    print "Abort requested"
                    self.Kill()
                	




class AE(threading.Thread):
    """Represents a DICOM application entity

    Instance if this class represent an application entity. Once
    instanciated, it starts a new thread and enters an event loop,
    where events are association requests from remote AEs. Events
    trigger callback functions that perform user defined actions based
    on received events.
    """
    def __init__(self, AET, port, SOPSCU, SOPSCP, 
                 SupportedTransferSyntax=[
                                          ExplicitVRLittleEndian, 
                                          ImplicitVRLittleEndian, 
                                          ExplicitVRBigEndian
                                          ], 
                 MaxPDULength=16000):
        self.LocalAE = {'Address': platform.node(), 'Port': port, 'AET':AET}
        self.SupportedSOPClassesAsSCU = SOPSCU
        self.SupportedSOPClassesAsSCP = SOPSCP
        self.SupportedTransferSyntax = SupportedTransferSyntax
        self.MaxNumberOfAssociations = 25
        threading.Thread.__init__(self, name=self.LocalAE['AET'])

        self.SOPUID = [x for x in self.SupportedSOPClassesAsSCP]
        self.LocalServerSocket = socket.socket(socket.AF_INET, \
                                               socket.SOCK_STREAM)
        self.LocalServerSocket.setsockopt(socket.SOL_SOCKET, \
                                          socket.SO_REUSEADDR,1)
        self.LocalServerSocket.bind(('', port))     
        self.LocalServerSocket.listen(1)
        self.MaxPDULength = MaxPDULength

        # build presentation context definition list to be sent to remote AE when
        # requesting association. 
        count = 1
        self.PresentationContextDefinitionList = []
        for ii in self.SupportedSOPClassesAsSCU+self.SupportedSOPClassesAsSCP:
            if ii.__subclasses__():
                for jj in ii.__subclasses__():
                    self.PresentationContextDefinitionList.append(
                        [count, UID(jj.UID), [x for x in self.SupportedTransferSyntax]])
                    count += 2
            else:
                self.PresentationContextDefinitionList.append(
                    [count, UID(ii.UID), [x for x in self.SupportedTransferSyntax]])
                count += 2

        # build acceptable context definition list used to decide
        # weither an association from a remote AE will be accepted or
        # not. This is based on the SupportedSOPClassesAsSCP and
        # SupportedTransferSyntax values set for this AE.
        self.AcceptablePresentationContexts = []
        for ii in self.SupportedSOPClassesAsSCP:
            if ii.__subclasses__():
                for jj in ii.__subclasses__():
                    self.AcceptablePresentationContexts.append(
                        [jj.UID, [x for x in self.SupportedTransferSyntax]])
            else:
                self.AcceptablePresentationContexts.append(
                    [ii.UID, [x for x in self.SupportedTransferSyntax]])

        # used to terminate AE
        self.__Quit = False
	
        # list of active association objects
	self.Associations = []



    def run(self):
        if not self.SupportedSOPClassesAsSCP:
	    # no need to loop. This is just a client AE. All events will be triggered by the user
            return
        while 1:
            # main loop
            time.sleep(0.1)
            if self.__Quit: break
            [a,b,c] = select.select([self.LocalServerSocket],[],[],0)
            if a:
                # got an incoming connection
                client_socket, remote_address = self.LocalServerSocket.accept()
                # create a new association
                self.Associations.append(Association(self, client_socket))
            #print [x.isAlive() for x in self.Associations if x.isAlive()]



    def Quit(self):
	for aa in self.Associations:
	    aa.Kill()	    
	self.__Quit = True
       
	
    def QuitOnKeyboardInterrupt(self):
        # must be called from the main thread in order to catch the KeyboardInterrupt exception
        while 1:
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                self.Quit()
                sys.exit(0)


    def RequestAssociation(self, remoteAE):
        """Requests association to a remote application entity"""
        assoc = Association(self, RemoteAE=remoteAE)
	while not assoc.AssociationEstablished and not assoc.AssociationRefused:
            time.sleep(0.1)
        if assoc.AssociationEstablished:
            self.Associations.append(assoc)
            return assoc
        else:
            return None

        
