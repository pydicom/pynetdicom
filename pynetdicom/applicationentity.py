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

from pynetdicom.__init__ import pynetdicom_uid_prefix
from pynetdicom.__version__ import __version__
from pynetdicom.ACSEprovider import ACSEServiceProvider
from pynetdicom.association import Association
from pynetdicom.DIMSEmessages import *
from pynetdicom.DIMSEprovider import DIMSEServiceProvider
from pynetdicom.DIMSEparameters import *
from pynetdicom.DULparameters import *
from pynetdicom.DULprovider import DULServiceProvider
from pynetdicom.PDU import *
from pynetdicom.SOPclass import *


logger = logging.getLogger('pynetdicom')
handler = logging.StreamHandler()
logger.setLevel(logging.WARNING)
formatter = logging.Formatter('%(levelname).1s: %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


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
        The port number to listen for connections on when acting as an SCP
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
        
        # To be implemented
        self.acse_timeout = None
        self.dul_timeout = None
        self.dimse_timeout = None
        
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
        
        threading.Thread.__init__(self, name=self.LocalAE['AET'])
        
        self.daemon = True
        
        # The socket to listen for connections on, port is always specified
        #   When acting as an SCU this isn't really necessary?
        self.local_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.local_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.local_socket.bind(('', port))
        self.local_socket.listen(1)

    def run(self):
        """
        The main threading.Thread loop, it listens for connection attempts
        on self.local_socket and attempts to Associate with them. 
        Successful associations get added to self.Associations
        """
        
        # If the SCP has no supported SOP Classes then there's no point 
        #   running as a server
        if self.SupportedSOPClassesAsSCP == []:
            logger.info("AE is running as an SCP but no supported SOP Classes "
                "have been included")
            return
        
        no_loops = 0
        while True:
            
            time.sleep(0.1)
            
            if self.__Quit:
                break
            
            # Monitor the local socket to see if anyone tries to connect
            read_list, _, _ = select.select([self.local_socket], [], [], 0)
            
            # If theres a connection
            if read_list:
                client_socket, remote_address = self.local_socket.accept()
                client_socket.setsockopt(socket.SOL_SOCKET, 
                                         socket.SO_RCVTIMEO, 
                                         struct.pack('ll', 10, 0))
                
                # Create a new Association
                # Association(local_ae, local_socket=None, peer_ae=None)
                assoc = Association(self, client_socket)
                self.Associations.append(assoc)

            # Delete dead associations
            self.Associations[:] = [active_assoc for active_assoc in 
                self.Associations if active_assoc.isAlive()]
                
            # Every 50 loops run the garbage collection
            if no_loops % 51 == 0:
                gc.collect()
                no_loops = 0
            
            no_loops += 1

    def Quit(self):
        """
        """
        for aa in self.Associations:
            aa.Kill()
            if self.local_socket:
                self.local_socket.close()
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

    def request_association(self, ip_address, port, ae_title='ANYSCP'):
        """Requests association to a remote application entity
        
        When requesting an association the local AE is acting as an SCU and
        hence passes the remote AE's dict to Association
        
        Parameters
        ----------
        ip_address - str
            The peer AE's IP/TCP address (IPv4)
        port - int
            The peer AE's listen port number
        ae_title - str, optional
            The peer AE's title, must conform to AE title requirements as per
            PS (16 char max, not allowed to be all spaces)
            
        Returns
        -------
        assoc
            The Association if it was successfully established
        None
            If the association failed or was rejected
        """
        
        if not isinstance(ip_address, str):
            raise ValueError("ip_address must be a valid IPv4 string")
            
        if not isinstance(port, int):
            raise ValueError("port must be a valid port number")
            
        if not isinstance(ae_title, str):
            raise ValueError("ae_title must be a valid AE title string")
        
        # Check AE title is OK
        if ae_title.strip() == '':
            raise ValueError("ae_title must not be all spaces")
            
        if len(ae_title) > 16:
            logger.info("Supplied local AE title is greater than 16 characters "
                "and will be truncated")
        
        peer_ae = {'AET' : ae_title[:16], 
                   'Address' : ip_address, 
                   'Port' : port}
        
        # Association(local_ae, local_socket=None, remote_ae=None)
        assoc = Association(self, RemoteAE=peer_ae)
        
        # Endlessly loops while the Association negotiation is taking place
        while not assoc.AssociationEstablished \
                and not assoc.AssociationRefused and not assoc.DUL.kill:
            time.sleep(0.1)
        
        # If the Association was established
        if assoc.AssociationEstablished:
            self.Associations.append(assoc)
            return assoc

        return None

    def RequestAssociation(self, remoteAE):
        return self.request_association(remoteAE['Port'], 
                                         remoteAE['Address'], 
                                         remoteAE['AET'])


    # Communication related callback
    def on_receive_connection(self):
        pass


    # High-level Association related callbacks
    def on_association_established(self):
        pass
    
    def on_association_requested(self):
        pass
    
    def on_association_accepted(self, assoc):
        """
        Placeholder for a function callback. Function will be called 
        when an association attempt is accepted by either the local or peer AE
        
        The default implementation is used for logging debugging information
        
        Parameters
        ----------
        assoc - pynetdicom.Association
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

    
    def on_association_rejected(self, associate_rj_pdu):
        """
        Placeholder for a function callback. Function will be called 
        when an association attempt is rejected by a peer AE
        
        The default implementation is used for logging debugging information
        
        Parameters
        ----------
        associate_rq_pdu - pynetdicom.PDU.A_ASSOCIATE_RJ_PDU
            The A-ASSOCIATE-RJ PDU instance received from the peer AE
        """
        
        # See PS3.8 Section 7.1.1.9 but mainly Section 9.3.4 and Table 9-21
        #   for information on the result and diagnostic information
        source = associate_rj_pdu.ResultSource
        result = associate_rj_pdu.Result
        reason = associate_rj_pdu.Diagnostic
        
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
        
    def on_association_released(self):
        logger.info('Association Release')
        
    def on_association_aborted(self):
        pass


    # Low-level Association ACSE related callbacks
    def on_send_associate_rq(self, a_associate_rq):
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
        
    def on_send_associate_ac(self, a_associate_ac):
        """
        Placeholder for a function callback. Function will be called 
        immediately prior to encoding and sending an A-ASSOCIATE-AC to a peer AE
        
        Parameters
        ----------
        a_associate_ac - pynetdicom.PDU.A_ASSOCIATE_AC_PDU
            The A-ASSOCIATE-AC PDU instance
        """
        app_context = a_associate_ac.VariableItems[0]
        pres_context_items = a_associate_ac.VariableItems[1:-1]
        user_information = a_associate_ac.VariableItems[-1]
        
        app_context_name = app_context.ApplicationContextName.decode('utf-8')
        calling_ae = a_associate_ac.Reserved4.decode('utf-8')
        called_ae = a_associate_ac.Reserved3.decode('utf-8')
        responding_ae = 'resp. AP Title'
        
        our_class_uid = pynetdicom_uid_prefix
        our_version = 'PYNETDICOM_' + ''.join(__version__.split('.'))
        our_max_pdu_length = 'unknown'
        
        their_class_uid = 'unknown'
        their_version = 'unknown'
        their_max_pdu_length = 'unknown'
        
        for user_data in user_information.UserData:
            if user_data.__class__ == MaximumLengthSubItem:
                their_max_pdu_length = user_data.MaximumLengthReceived
        
        s = ['Association Parameters Negotiated:']
        s.append('====================== BEGIN A-ASSOCIATE-AC ================'
                '=====')
        
        s.append('Our Implementation Class UID:      %s' %our_class_uid)
        s.append('Our Implementation Version Name:   %s' %our_version)
        s.append('Their Implementation Class UID:    %s' %their_class_uid)
        s.append('Their Implementation Version Name: %s' %their_version)
        s.append('Application Context Name:    %s' %app_context_name)
        s.append('Calling Application Name:    %s' %calling_ae)
        s.append('Called Application Name:     %s' %called_ae)
        #s.append('Responding Application Name: %s' %responding_ae)
        s.append('Our Max PDU Receive Size:    %s' %our_max_pdu_length)
        s.append('Their Max PDU Receive Size:  %s' %their_max_pdu_length)
        s.append('Presentation Contexts:')
        
        result_options = {0 : 'Accepted', 
                          1 : 'User Rejection', 
                          2 : 'Provider Rejection',
                          3 : 'Provider Rejection',
                          4 : 'Provider Rejection'} 
        
        for item in pres_context_items:
            context_id = item.PresentationContextID
            result = result_options[item.ResultReason]
            s.append('  Context ID:        %s (%s)' %(context_id, result))
            
            sop_class = item.TransferSyntaxSubItem
            s.append('    Abstract Syntax: =%s' %'FIXME')
            s.append('    Proposed SCP/SCU Role: %s' %'[FIXME]')
            
            # If Presentation Context was accepted show the SCU/SCP role and
            #   transfer syntax
            if item.ResultReason == 0:
                s.append('    Accepted SCP/SCU Role: %s' %'[FIXME]')
                #syntax_name = UID(sop_class.TransferSyntaxName.decode('utf-8'))
                #syntax_name = ''.join(syntax_name.name.split(' '))
                #s.append('    Accepted Transfer Syntax: =%s' %syntax_name)
                
        s.append('Requested Extended Negotiation: %s' %'[FIXME]')
        s.append('Accepted Extended Negotiation:  %s' %'[FIXME]')
        s.append('Requested User Identity Negotiation: %s' %'[FIXME]')
        s.append('User Identity Negotiation Response:  %s' %'[FIXME]')
        s.append('======================= END A-ASSOCIATE-AC =================='
                '====')
        
        for line in s:
            logger.debug(line)
        
    def on_send_associate_rj(self, a_associate_rj):
        """
        Placeholder for a function callback. Function will be called 
        immediately prior to encoding and sending an A-ASSOCIATE-RJ to a peer AE
        
        Parameters
        ----------
        a_associate_rj - pynetdicom.PDU.A_ASSOCIATE_RJ_PDU
            The A-ASSOCIATE-RJ PDU instance
        """
        pass
    
    def on_send_data_tf(self, p_data_tf):
        """
        Placeholder for a function callback. Function will be called 
        immediately prior to encoding and sending an P-DATA-TF to a peer AE
        
        Parameters
        ----------
        a_release_rq - pynetdicom.PDU.P_DATA_TF_PDU
            The P-DATA-TF PDU instance
        """
        pass
    
    def on_send_release_rq(self, a_release_rq):
        """
        Placeholder for a function callback. Function will be called 
        immediately prior to encoding and sending an A-RELEASE-RQ to a peer AE
        
        Parameters
        ----------
        a_release_rq - pynetdicom.PDU.A_RELEASE_RQ_PDU
            The A-RELEASE-RQ PDU instance
        """
        pass
        
    def on_send_release_rp(self, a_release_rp):
        """
        Placeholder for a function callback. Function will be called 
        immediately prior to encoding and sending an A-RELEASE-RP to a peer AE
        
        Parameters
        ----------
        a_release_rp - pynetdicom.PDU.A_RELEASE_RP_PDU
            The A-RELEASE-RP PDU instance
        """
        pass
        
    def on_send_abort(self, a_abort):
        """
        Placeholder for a function callback. Function will be called 
        immediately prior to encoding and sending an A-ABORT to a peer AE
        
        Parameters
        ----------
        a_abort - pynetdicom.PDU.A_ABORT_PDU
            The A-ABORT PDU instance
        """
        pass


    def on_receive_associate_rq(self, a_associate_rq):
        """
        Placeholder for a function callback. Function will be called 
        immediately after receiving and decoding an A-ASSOCIATE-RQ
        
        Parameters
        ----------
        a_associate_rq - pynetdicom.PDU.A_ASSOCIATE_RQ_PDU
            The A-ASSOCIATE-RQ PDU instance
        """
        application_context = a_associate_rq.VariableItems[0]
        presentation_context_items = a_associate_rq.VariableItems[1:-1]
        user_information = a_associate_rq.VariableItems[-1]
        
        max_pdu_length = 'none'
        for user_data in user_information.UserData:
            if user_data.__class__ == MaximumLengthSubItem:
                max_pdu_length = user_data.MaximumLengthReceived
        
        s = ['Request Parameters:']
        s.append('====================== BEGIN A-ASSOCIATE-RQ ================'
                '=====')
        
        s.append('Our Implementation Class UID:      %s' %pynetdicom_uid_prefix)
        s.append('Our Implementation Version Name:   %s' %(
                'PYNETDICOM_' + ''.join(__version__.split('.'))))
        
        s.append('Their Implementation Class UID:')
        s.append('Their Implementation Version Name:')
        s.append('Application Context Name:    %s' %(
                application_context.ApplicationContextName.decode('utf-8')))
        
        s.append('Calling Application Name:    %s' %(
                a_associate_rq.CallingAETitle.decode('utf-8')))
        
        s.append('Called Application Name:     %s' %(
                a_associate_rq.CalledAETitle.decode('utf-8')))
        
        s.append('Responding Application Name: resp. AP Title')
        s.append('Our Max PDU Receive Size:    %s' %max_pdu_length)
        s.append('Their Max PDU Receive Size:  0')
        s.append('Presentation Contexts:')
        for item in presentation_context_items:
            s.append('  Context ID:        %s (Proposed)' %(
                    item.PresentationContextID))
            
            sop_class = item.AbstractTransferSyntaxSubItems[0]
            s.append('    Abstract Syntax: =%s' %sop_class.AbstractSyntaxName.decode('utf-8'))
            s.append('    Proposed SCP/SCU Role: %s' %'test')
            s.append('    Proposed Transfer Syntax(es):')
            for transfer_syntax in item.AbstractTransferSyntaxSubItems[1:]:
                s.append('      =%s' %transfer_syntax.TransferSyntaxName.decode('utf-8'))
        s.append('Requested Extended Negotiation: %s' %'test')
        s.append('Accepted Extended Negotiation:  none')
        s.append('Requested User Identity Negotiation: %s' %'test')
        s.append('User Identity Negotiation Response:  none')
        s.append('======================= END A-ASSOCIATE-RQ =================='
                '====')
        
        for line in s:
            logger.debug(line)
        
    def on_receive_associate_ac(self, a_associate_ac):
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
        s.append('Accepted Extended Negotiation: %s' %ext_nego)
        
        usr_id = 'None'
        if assoc_ac.UserInformation.UserIdentity is not None:
            usr_id = 'Yes'
        
        s.append('User Identity Negotiation Response:  %s' %usr_id)
        s.append('======================= END A-ASSOCIATE-AC =================='
                '====')
        
        for line in s:
            logger.debug(line)
        
    def on_receive_associate_rj(self, a_associate_rj):
        """
        Placeholder for a function callback. Function will be called 
        immediately after receiving and decoding an A-ASSOCIATE-RJ
        
        Parameters
        ----------
        a_associate_rj - pynetdicom.PDU.A_ASSOCIATE_RJ_PDU
            The A-ASSOCIATE-RJ PDU instance
        """
        pass
    
    def on_receive_data_tf(self, p_data_tf):
        """
        Placeholder for a function callback. Function will be called 
        immediately after receiving and decoding an P-DATA-TF
        
        Parameters
        ----------
        a_release_rq - pynetdicom.PDU.P_DATA_TF_PDU
            The P-DATA-TF PDU instance
        """
        pass
        
    def on_receive_release_rq(self, a_release_rq):
        """
        Placeholder for a function callback. Function will be called 
        immediately after receiving and decoding an A-RELEASE-RQ
        
        Parameters
        ----------
        a_release_rq - pynetdicom.PDU.A_RELEASE_RQ_PDU
            The A-RELEASE-RQ PDU instance
        """
        pass
        
    def on_receive_release_rp(self, a_release_rp):
        """
        Placeholder for a function callback. Function will be called 
        immediately after receiving and decoding an A-RELEASE-RP
        
        Parameters
        ----------
        a_release_rp - pynetdicom.PDU.A_RELEASE_RP_PDU
            The A-RELEASE-RP PDU instance
        """
        pass
        
    def on_receive_abort(self, a_abort):
        """
        Placeholder for a function callback. Function will be called 
        immediately after receiving and decoding an A-ABORT
        
        Parameters
        ----------
        a_abort - pynetdicom.PDU.A_ABORT_PDU
            The A-ABORT PDU instance
        """
        pass


    # High-level DIMSE related callbacks
    def on_c_echo(self):
        pass
    
    def on_c_store(self, sop_class, dataset):
        """
        Function callback called when a dataset is received following a C-STORE.
        
        Parameters
        ----------
        sop_class - pydicom.SOPclass.StorageServiceClass
            The StorageServiceClass representing the object
        dataset - pydicom.Dataset
            The DICOM dataset sent via the C-STORE
            
        Returns
        -------
        status
            A valid return status, see the StorageServiceClass for the 
            available statuses
        """
        return sop_class.Success
        
    def on_c_find(self, dataset):
        pass
        
    def on_c_get(self, dataset):
        pass
        
    def on_c_move(self, dataset):
        pass
    
    
    # Mid-level DIMSE related callbacks
    def on_send_c_echo_rq(self, dimse_msg):
        """
        Parameters
        ----------
        dimse_msg - pynetdicom.SOPclass.C_ECHO_RQ 
        """
        d = dimse_msg.CommandSet
        logger.info("Sending Echo Request: MsgID %s" %(d.MessageID))
        
    def on_send_c_echo_rsp(self, dimse_msg):
        pass
    
    def on_send_c_store_rq(self, dimse_msg):
        """
        Parameters
        ----------
        store - pynetdicom.SOPclass.C_STORE_RQ 
        """
        d = dimse_msg.CommandSet

        priority_str = {2 : 'Low',
                        0 : 'Medium',
                        1 : 'High'}
        priority = priority_str[d.Priority]

        dataset = 'None'
        if 'DataSet' in dimse_msg.__dict__.keys():
            dataset = 'Present'
            
        if d.AffectedSOPClassUID == 'CT Image Storage':
            dataset_type = ', (CT)'
        if d.AffectedSOPClassUID == 'MR Image Storage':
            dataset_type = ', (MR)'
        else:
            dataset_type = ''
        
        logger.info("Sending Store Request: MsgID %s%s" 
                %(d.MessageID, dataset_type))
        
        s = []
        s.append('===================== OUTGOING DIMSE MESSAGE ================'
                 '====')
        s.append('Message Type                  : %s' %'C-STORE RQ')
        s.append('Message ID                    : %s' %d.MessageID)
        s.append('Affected SOP Class UID        : %s' %d.AffectedSOPClassUID)
        s.append('Affected SOP Instance UID     : %s' %d.AffectedSOPInstanceUID)
        s.append('Data Set                      : %s' %dataset)
        s.append('Priority                      : %s' %priority)
        s.append('======================= END DIMSE MESSAGE ==================='
                 '====')
        for line in s:
            logger.debug(line)
    
    def on_send_c_store_rsp(self, dimse_msg):
        pass
    
    
    def on_receive_c_echo_rq(self, dimse_msg):
        """
        Placeholder for a function callback. Function will be called 
        after receiving and decoding a C-ECHO-RQ. The C-ECHO service is used
        to verify end-to-end communications with a peer DIMSE user.
        """
        d = dimse_msg.CommandSet
        
        s = ['Received Echo Request']
        s.append('===================== INCOMING DIMSE MESSAGE ================'
                 '====')
        s.append('Message Type                  : %s' %'C-ECHO RQ')
        s.append('Presentation Context ID       : %s' %dimse_msg.ID)
        s.append('Message ID                    : %s' %d.MessageID)
        s.append('Data Set                      : %s' %'none')
        s.append('======================= END DIMSE MESSAGE ==================='
                 '====')
                 
        for line in s:
            logger.debug(line)
    
    def on_receive_c_echo_rsp(self, dimse_msg):
        """
        Parameters
        ----------
        dimse_msg - pynetdicom.SOPclass.C_ECHO_RSP
        """
        d = dimse_msg.CommandSet
        
        # Status must always be Success for C_ECHO_RSP
        logger.info("Received Echo Response (Status: Success)")
        
    def on_receive_c_store_rq(self, dimse_msg):
        """
        Placeholder for a function callback. Function will be called 
        on receiving a C-STORE-RQ
        
        Parameters
        ----------
        dataset - pydicom.Dataset
            The dataset sent to the local AE
        """
        d = dimse_msg.CommandSet
        
        priority_str = {2 : 'Low',
                        0 : 'Medium',
                        1 : 'High'}
        priority = priority_str[d.Priority]

        dataset = 'None'
        if 'DataSet' in dimse_msg.__dict__.keys():
            dataset = 'Present'
        
        logger.info('Received Store Request')
        
        s = []
        s.append('===================== INCOMING DIMSE MESSAGE ================'
                 '====')
        s.append('Message Type                  : %s' %'C-STORE RQ')
        s.append('Presentation Context ID       : %s' %dimse_msg.ID)
        s.append('Message ID                    : %s' %d.MessageID)
        s.append('Affected SOP Class UID        : %s' %d.AffectedSOPClassUID)
        s.append('Affected SOP Instance UID     : %s' %d.AffectedSOPInstanceUID)
        s.append('Data Set                      : %s' %dataset)
        s.append('Priority                      : %s' %priority)
        s.append('======================= END DIMSE MESSAGE ==================='
                 '====')
        for line in s:
            logger.debug(line)

    def on_receive_c_store_rsp(self, dimse_msg):

        d = dimse_msg.CommandSet
        
        dataset = 'None'
        if 'DataSet' in dimse_msg.__dict__.keys():
            if dimse_msg.DataSet.getvalue() != b'':
                dataset = 'Present'
        
        status = '0x%04x' %d.Status
        if status == '0x0000':
            status += ': Success'
        else:
            pass
        
        logger.info('Received Store Response')
        s = []
        s.append('===================== INCOMING DIMSE MESSAGE ================'
                 '====')
        s.append('Message Type                  : %s' %'C-STORE RSP')
        s.append('Presentation Context ID       : %s' %dimse_msg.ID)
        s.append('Message ID Being Responded To : %s' %d.MessageIDBeingRespondedTo)
        s.append('Affected SOP Class UID        : %s' %d.AffectedSOPClassUID)
        s.append('Affected SOP Instance UID     : %s' %d.AffectedSOPInstanceUID)
        s.append('Data Set                      : %s' %dataset)
        s.append('DIMSE Status                  : %s' %status)
        
        s.append('======================= END DIMSE MESSAGE ==================='
                 '====')
                 
        for line in s:
            logger.debug(line)

    def on_receive_c_find_rq(self, dimse_msg):
        """
        Placeholder for a function callback. Function will be called 
        on receiving a C-FIND-RQ. The C-FIND service is used by a DIMSE to match
        a set of Attributes against the Attributes of a set of composite SOP
        Instances maintained by a peer DIMSE user, and retrieve all composite
        SOP Instances that match. It triggers one or more C-STORE 
        sub-operations on the same Association.
        
        Parameters
        ----------
        attributes - pydicom.Dataset
            A Dataset containing the attributes to match against.
            
        Returns
        -------
        matching_sop_instances - list of pydicom.Dataset
            The matching SOP Instances. If no matching SOP Instances are found 
            then return the empty list or None.
        """
        return None
        
    def on_receive_c_get_rq(self, dimse_msg):
        """
        Placeholder for a function callback. Function will be called 
        on receiving a C-GET-RQ. The C-GET service is used by a DIMSE to match
        a set of Attributes against the Attributes of a set of composite SOP
        Instances maintained by a peer DIMSE user, and retrieve all composite
        SOP Instances that match. It triggers one or more C-STORE 
        sub-operations on the same Association.
        
        Parameters
        ----------
        attributes - pydicom.Dataset
            A Dataset containing the attributes to match against.
            
        Returns
        -------
        matching_sop_instances - list of pydicom.Dataset
            The matching SOP Instances to be sent via C-STORE sub-operations. If
            no matching SOP Instances are found then return the empty list or
            None.
        """
        return None
        
    def on_receive_c_move_rq(self, dimse_msg):
        """
        Placeholder for a function callback. Function will be called 
        on receiving a C-MOVE-RQ. The C-MOVE service is used by a DIMSE to match
        a set of Attributes against the Attributes of a set of composite SOP
        Instances maintained by a peer DIMSE user, and retrieve all composite
        SOP Instances that match. It triggers one or more C-STORE 
        sub-operations on the same Association.
        
        Parameters
        ----------
        attributes - pydicom.Dataset
            A Dataset containing the attributes to match against.
            
        Returns
        -------
        matching_sop_instances - list of pydicom.Dataset
            The matching SOP Instances to be sent via C-STORE sub-operations. If
            no matching SOP Instances are found then return the empty list or
            None.
        """
        return None


    def on_receive_n_event_report_rq(self, dimse_msg):
        """
        Placeholder for a function callback. Function will be called 
        on receiving an N-EVENT-REPORT-RQ. The N-EVENT-REPORT service is used 
        by a DIMSE to report an event to a peer DIMSE user.
        
        Not currently implemented
        
        Parameters
        ----------
        event - ???
            ???
        """
        raise NotImplementedError
        
    def on_receive_n_get_rq(self, dimse_msg):
        """
        Placeholder for a function callback. Function will be called 
        on receiving an N-GET-RQ. The N-GET service is used 
        by a DIMSE to retrieve Attribute values from a peer DIMSE user.
        
        Not currently implemented
        
        Parameters
        ----------
        attributes - ???
            ???
            
        Returns
        values - ???
            The attribute values to be retrieved
        """
        raise NotImplementedError
        
    def on_receive_n_set_rq(self, dimse_msg):
        """
        Placeholder for a function callback. Function will be called 
        on receiving an N-SET-RQ. The N-SET service is used 
        by a DIMSE to request the modification of Attribute values from a peer 
        DIMSE user.
        
        Not currently implemented
        
        Parameters
        ----------
        attributes - ???
            ???
        """
        raise NotImplementedError
        
    def on_receive_n_action_rq(self, dimse_msg):
        """
        Placeholder for a function callback. Function will be called 
        on receiving an N-ACTION-RQ. The N-ACTION service is used 
        by a DIMSE to request an action by a peer DIMSE user.
        
        Not currently implemented
        
        Parameters
        ----------
        actions - ???
            ???
        """
        raise NotImplementedError
        
    def on_receive_n_create_rq(self, dimse_msg):
        """
        Placeholder for a function callback. Function will be called 
        on receiving an N-CREATE-RQ. The N-CREATE service is used 
        by a DIMSE to create a new managed SOP Instance, complete with its
        identification and the values of its association Attributes to register
        its identification.
        
        Not currently implemented
        
        Parameters
        ----------
        attributes - ???
            ???
        """
        raise NotImplementedError
        
    def on_receive_n_delete_rq(self, dimse_msg):
        """
        Placeholder for a function callback. Function will be called 
        on receiving an N-DELETE-RQ. The N-DELETE service is used 
        by a DIMSE to request a peer DIMSE user delete a managed SOP Instance
        a deregister its identification.
        
        Not currently implemented
        
        Parameters
        ----------
        attributes - ???
            ???
        """
        raise NotImplementedError


    # Low-level DIMSE related callbacks
    def on_send_dimse_message(self, message):
        """
        Placeholder for a function callback. Function will be called 
        immediately prior to encoding and sending a DIMSE message
        
        Parameters
        ----------
        message - pynetdicom.DIMSEmessage.DIMSEMessage
            The DIMSE message to be sent
        """
        #logger.info('ae::on_send_dimse_message: %s' %type(message))
                
        callback = {C_ECHO_RQ_Message   : self.on_send_c_echo_rq,
                    C_ECHO_RSP_Message  : self.on_send_c_echo_rsp,
                    C_STORE_RQ_Message  : self.on_send_c_store_rq,
                    C_STORE_RSP_Message : self.on_send_c_store_rsp}

        callback[type(message)](message)
        
    def on_receive_dimse_message(self, message):
        """
        Placeholder for a function callback. Function will be called 
        immediately after receiving and decoding a DIMSE message
        
        Parameters
        ----------
        sop_class - pynetdicom.SOPclass.SOPClass
            A SOP Class instance of the type referred to by the message
        message - pydicom.Dataset
            The DIMSE message that was received as a Dataset
        """
        #logger.info('ae::on_receive_dimse_message: %s' %type(message))
                
        callback = {C_ECHO_RQ_Message   : self.on_receive_c_echo_rq,
                    C_ECHO_RSP_Message  : self.on_receive_c_echo_rsp,
                    C_STORE_RQ_Message  : self.on_receive_c_store_rq,
                    C_STORE_RSP_Message : self.on_receive_c_store_rsp}

        callback[type(message)](message)


class AE(ApplicationEntity):
    pass
