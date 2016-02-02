#
# Copyright (c) 2012 Patrice Munger
# This file is part of pynetdicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pynetdicom.googlecode.com

import gc
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
from pynetdicom.association import Association
from pynetdicom.DIMSEprovider import DIMSEServiceProvider
from pynetdicom.DIMSEparameters import *
from pynetdicom.DULparameters import *
from pynetdicom.DULprovider import DULServiceProvider
from pynetdicom.SOPclass import *


logger = logging.getLogger('netdicom.applicationentity')


class ApplicationEntity(threading.Thread):
    """Represents a DICOM application entity

    Once instantiated, starts a new thread and enters an event loop,
    where events are association requests from remote AEs. Events
    trigger callback functions that perform user defined actions based
    on received events.
    
    Parameters
    ----------
    AET - str
        The AE title of the AE, 16 characters max
    port - int
        The port number to user for connections
    SOPSCU - list of DICOM SOP Classes
        Supported SOP Classes when the AE is operating as an SCU
    SOPSCP - list of DICOM SOP Classes
        Supported SOP Classes when the AE is operating as an SCP
    SupportedTransferSyntax - list of pydicom.uid.UID transfer syntaxes
        Supported DICOM Transfer Syntaxes
    MaxPDULength - int
        The maximum supported size of the PDU
        
    Attributes
    ----------
    LocalAE - dict
        Stores the AE's address, port and title
    MaxNumberOfAssociations - int
        The maximum number of simultaneous associations
    LocalServerSocket - socket.socket
        The socket used for connections with remote hosts
    Associations - list of Association
        The associations between the local AE and peer AEs
    """
    def __init__(self, 
                 AET, 
                 port, 
                 SOPSCU, 
                 SOPSCP,
                 SupportedTransferSyntax=[ExplicitVRLittleEndian,
                                          ImplicitVRLittleEndian,
                                          ExplicitVRBigEndian],
                 MaxPDULength=16000):

        self.LocalAE = {'Address': platform.node(), 
                        'Port': port, 
                        'AET': AET}
        self.SupportedSOPClassesAsSCU = SOPSCU
        self.SupportedSOPClassesAsSCP = SOPSCP
    
        # Check and add transfer syntaxes
        self.SupportedTransferSyntax = []
        if not isinstance(SupportedTransferSyntax, list):
            raise ValueError("SupportedTransferSyntax must be a list of "
                "pydicom.uid.UID Transfer Syntaxes supported by the AE")
        
        for transfer_syntax in SupportedTransferSyntax:
            # Check that the transfer_syntax is a pydicom.uid.UID
            if isinstance(transfer_syntax, UID):
                # Check that the UID is one of the valid transfer syntaxes
                if transfer_syntax.is_transfer_syntax:
                    self.SupportedTransferSyntax.append(transfer_syntax)
            else:
                raise ValueError("Attempted to instantiate Application "
                    "Entity using invalid transfer syntax pydicom.uid.UID "
                    "instance: %s" %transfer_syntax)
        
        self.MaxPDULength = MaxPDULength
        self.MaxNumberOfAssociations = 2
        
        # maximum amount of time this association can be idle before it gets
        # terminated
        self.MaxAssociationIdleSeconds = None
        
        threading.Thread.__init__(self, name=self.LocalAE['AET'])
        
        self.daemon = True
        
        self.LocalServerSocket = socket.socket(socket.AF_INET,
                                               socket.SOCK_STREAM)
        self.LocalServerSocket.setsockopt(socket.SOL_SOCKET,
                                          socket.SO_REUSEADDR, 1)
        self.LocalServerSocket.bind(('', port))
        self.LocalServerSocket.listen(1)

        # Build presentation context definition list to be sent to remote AE
        #   when requesting association.
        #
        # Each item in the PresentationContextDefinitionList is made up of
        #   [n, pydicom.UID, [list of Transfer Syntax pydicom.UID]]
        #   where n is the Presentation Context ID and shall be odd integers
        #   between 1 and 255
        # See PS3.8 Sections 7.1.1.13 and 9.3.2.2
        self.PresentationContextDefinitionList = []
        for ii, sop_class in enumerate(self.SupportedSOPClassesAsSCU +
                                             self.SupportedSOPClassesAsSCP):
            
            # Must be an odd integer between 1 and 255
            presentation_context_id = ii * 2 + 1
            abstract_syntax = None

            # If supplied SOPClass is already a pydicom.UID class
            if isinstance(sop_class, UID):
                abstract_syntax = sop_class
            
            # If supplied SOP Class is a UID string, try and see if we can
            #   create a pydicom UID class from it
            elif isinstance(sop_class, str):
                abstract_syntax = UID(sop_class)

            # If the supplied SOP class is one of the pynetdicom.SOPclass SOP 
            #   class instances, convert it to pydicom UID 
            else:
                abstract_syntax = UID(sop_class.UID)
            
            # Add the Presentation Context Definition Item
            # If we have too many Items, warn and skip the rest
            if presentation_context_id < 255:
                self.PresentationContextDefinitionList.append(
                    [presentation_context_id,
                     abstract_syntax,
                     self.SupportedTransferSyntax[:]])
            else:
                raise UserWarning("More than 126 supported SOP Classes have "
                    "been supplied to the Application Entity, but the "
                    "Presentation Context Definition ID can only be an odd "
                    "integer between 1 and 255. The remaining SOP Classes will "
                    "not be included")
                break
            
        # Build acceptable context definition list used to decide
        #   whether an association from a remote AE will be accepted or
        #   not. This is based on the SupportedSOPClassesAsSCP and
        #   SupportedTransferSyntax values set for this AE.
        self.AcceptablePresentationContexts = []
        for sop_class in self.SupportedSOPClassesAsSCP:
            
            # If our sop_class has any subclasses then add those
            if sop_class.__subclasses__():
                for jj in sop_class.__subclasses__():
                    self.AcceptablePresentationContexts.append(
                        [jj.UID, 
                         [x for x in self.SupportedTransferSyntax]])
            else:
                self.AcceptablePresentationContexts.append(
                    [sop_class.UID, 
                     [x for x in self.SupportedTransferSyntax]])
        
        # Used to terminate AE
        self.__Quit = False

        # List of active association objects
        self.Associations = []

    def run(self):
        """
        The main threading.Thread loop, it listens for connection attempts
        on self.LocalServerSocket and attempts to Associate with them. 
        Successful associations get added to self.Associations
        """
        if not self.SupportedSOPClassesAsSCP:
            # no need to loop. This is just a client AE. All events will be
            # triggered by the user
            return
        count = 0
        
        while 1:
            # main loop
            time.sleep(0.1)
            if self.__Quit:
                break
            [a, b, c] = select.select([self.LocalServerSocket], [], [], 0)
            if a:
                # got an incoming connection
                client_socket, remote_address = self.LocalServerSocket.accept()
                client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVTIMEO, struct.pack('ll',10,0))
                # create a new association
                self.Associations.append(Association(self, client_socket))

            # delete dead associations
            #for aa in self.Associations:
            #    if not aa.isAlive():
            #        self.Associations.remove(aa)
            self.Associations[:] = [active_assoc for active_assoc in self.Associations if active_assoc.isAlive()]
            if not count % 50:
                logger.debug("number of active associations: %d", len(self.Associations))
                gc.collect()
            count += 1
            if count > 1e6:
                count = 0

    def Quit(self):
        """
        """
        for aa in self.Associations:
            aa.Kill()
            if self.LocalServerSocket:
                self.LocalServerSocket.close()
        self.__Quit = True

    def QuitOnKeyboardInterrupt(self):
        """
        """
        # must be called from the main thread in order to catch the
        # KeyboardInterrupt exception
        while 1:
            try:
                time.sleep(1)
            except KeyboardInterrupt:
                self.Quit()
                sys.exit(0)
            except IOError:
                # Catch this exception otherwise when we run an app,
                # using this module as a service this exception is raised
                # when we logoff.
                continue

    def RequestAssociation(self, remoteAE):
        """Requests association to a remote application entity
        
        Parameters
        ----------
        remoteAE - dict
            A dict containing the remote AE's address, port and title
            
        Returns
        -------
        assoc
            The Association if it was successfully established
        None
            If the association failed or was rejected
        """
        assoc = Association(self, RemoteAE=remoteAE)
        
        while not assoc.AssociationEstablished \
                and not assoc.AssociationRefused and not assoc.DUL.kill:
            time.sleep(0.1)
        
        if assoc.AssociationEstablished:
            self.Associations.append(assoc)
            return assoc

        return None


class AE(ApplicationEntity):
    pass
