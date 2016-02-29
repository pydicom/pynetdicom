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
from pynetdicom.SOPclass import *
from pynetdicom.utils import PresentationContext


logger = logging.getLogger('pynetdicom')
handler = logging.StreamHandler()
logger.setLevel(logging.WARNING)
formatter = logging.Formatter('%(levelname).1s: %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


class ApplicationEntity(threading.Thread):
    """Represents a DICOM application entity
    
    As per PS3.7, the DICOM Application Entity (AE) is specified by the 
    following parts of the DICOM Standard:
        * PS3.3 IODs: provides data models and attributes used for defining
            SOP Instances.
        * PS3.4 Service Classes: defines the set of operations that can be 
            performed on SOP Instances.
        * PS3.6 Data Dictionary: contains registry of Data Elements
        
    The AE uses the Association and Presentation data services provided by the
    Upper Layer Service.

    Once instantiated, starts a new thread and enters an event loop,
    where events are association requests from remote AEs.
    
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
    scu_supported_sop - List of SOP Classes
        The SOP Classes supported when acting as an SCU
    scp_supported_sop - List of SOP Classes
        The SOP Classes supported when acting as an SCP
    transfer_syntaxes - List of pydicom.uid.UID
        The supported transfer syntaxes
    presentation_contexts_scu - List of pynetdicom.utils.PresentationContext
        The presentation context list when acting as an SCU
    presentation_contexts_scp - List of pynetdicom.utils.PresentationContext
        The presentation context list when acting as an SCP
    """
    def __init__(self, 
                 AET, 
                 port, 
                 SOPSCU, 
                 SOPSCP,
                 SupportedTransferSyntax=[ExplicitVRLittleEndian,
                                          ImplicitVRLittleEndian,
                                          ExplicitVRBigEndian],
                 MaxPDULength=16384):

        self.LocalAE = {'Address': platform.node(), 'Port': port, 'AET': AET}
        self.scu_supported_sop = SOPSCU
        self.scp_supported_sop = SOPSCP
    
        # Check and add transfer syntaxes
        if not isinstance(SupportedTransferSyntax, list):
            raise ValueError("SupportedTransferSyntax must be a list of "
                "pydicom.uid.UID Transfer Syntaxes supported by the AE")
        
        self.transfer_syntaxes = []
        for syntax in SupportedTransferSyntax:
            # Check that the transfer_syntax is a pydicom.uid.UID
            if isinstance(syntax, UID):
                # Check that the UID is one of the valid transfer syntaxes
                if syntax.is_transfer_syntax:
                    self.transfer_syntaxes.append(syntax)
            else:
                raise ValueError("Attempted to instantiate Application "
                    "Entity using invalid transfer syntax: %s" %syntax)
        
        self.MaxPDULength = MaxPDULength
        self.MaxNumberOfAssociations = 2
        
        # maximum amount of time this association can be idle before it gets
        # terminated
        self.MaxAssociationIdleSeconds = None
        
        # All three timeouts are set in their respective service providers 
        #   during association
        #
        # ACSE timeout: the maximum amount of time (in seconds) that the 
        #   association can be idle before it gets terminated
        self.acse_timeout = None
        # DUL timeout: the maximum amount of time (in seconds) to wait for
        #   connection requests
        self.dul_timeout = None
        # DIMSE timeout: the maximum amount of time (in seconds) to wait for
        #   DIMSE messages before the association gets released
        self.dimse_timeout = None
        
        # Build presentation context list to be:
        #   * sent to remote AE when requesting association
        #       (presentation_contexts_scu)
        #   * used to decide whether to accept or reject when remote AE 
        #       requests association (presentation_contexts_scp)
        #
        #   See PS3.8 Sections 7.1.1.13 and 9.3.2.2
        self.presentation_contexts_scu = []
        self.presentation_contexts_scp = []
        
        for [pc_output, sop_input] in \
                    [[self.presentation_contexts_scu, self.scu_supported_sop],
                     [self.presentation_contexts_scp, self.scp_supported_sop]]:
            
            for ii, sop_class in enumerate(sop_input):
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
                    
                # If the supplied SOP class is one of the pynetdicom.SOPclass 
                #   SOP class instances, convert it to pydicom UID 
                else:
                    abstract_syntax = UID(sop_class.UID)
                
                # Add the Presentation Context Definition Item
                # If we have too many Items, warn and skip the rest
                if presentation_context_id < 255:
                    pc_item = PresentationContext(presentation_context_id,
                                                  abstract_syntax,
                                                  self.transfer_syntaxes[:])
                                                  
                    pc_output.append(pc_item)
                else:
                    raise UserWarning("More than 126 supported SOP Classes "
                        "have been supplied to the Application Entity, but the "
                        "Presentation Context Definition ID can only be an odd "
                        "integer between 1 and 255. The remaining SOP Classes "
                        "will not be included")
                    break

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
        on `local_socket` and attempts to Associate with them. 
        Successful associations get added to `Associations`
        """
        
        # If the SCP has no supported SOP Classes then there's no point 
        #   running as a server
        if self.scp_supported_sop == []:
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
        When the AE is running it can be killed through a keyboard interrupt
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

    def request_association(self, ip_address, port, ae_title='ANY-SCP'):
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

        # Associate
        assoc = Association(self, 
                            RemoteAE=peer_ae, 
                            acse_timeout=self.acse_timeout,
                            dimse_timeout=self.dimse_timeout)

        # Endlessly loops while the Association negotiation is taking place
        while not assoc.AssociationEstablished \
                and not assoc.AssociationRefused and not assoc.DUL.kill:
            time.sleep(0.1)

        # If the Association was established
        if assoc.AssociationEstablished:
            self.Associations.append(assoc)
            return assoc

        return assoc

    def RequestAssociation(self, remoteAE):
        return self.request_association(remoteAE['Port'], 
                                         remoteAE['Address'], 
                                         remoteAE['AET'])

    # Timeout setters
    def set_network_timeout(self, timeout):
        """ 
        The maximum amount of time that the DUL provider should wait before 
        terminating the connection
        
        Parameters
        ----------
        timeout - float
            The maximum amount of time (in seconds) to wait
        """
        self.dul_timeout = timeout
        self.MaxAssociationIdleSeconds = timeout
        
    def set_acse_timeout(self, timeout):
        """ 
        The maximum amount of time that the ACSE provider should wait for 
        messages before aborting the association
        
        Parameters
        ----------
        timeout - float
            The maximum amount of time (in seconds) to wait
        """
        self.acse_timeout = timeout
        
    def set_dimse_timeout(self, timeout):
        """ 
        The maximum amount of time that the DIMSE provider should wait for 
        messages before aborting the association
        
        Parameters
        ----------
        timeout - float
            The maximum amount of time (in seconds) to wait
        """
        self.dimse_timeout = timeout


    # Communication related callback
    def on_receive_connection(self):
        pass


    # High-level Association related callbacks
    def on_association_established(self):
        pass

    def on_association_requested(self):
        pass

    def on_association_accepted(self, associate_ac_pdu):
        """
        Placeholder for a function callback. Function will be called 
        when an association attempt is accepted by either the local or peer AE
        
        Parameters
        ----------
        associate_ac_pdu - pynetdicom.PDU.A_ASSOCIATE_AC_PDU
            The A-ASSOCIATE-AC PDU instance received from the peer AE
        """
        pass

    def on_association_rejected(self, associate_rj_pdu):
        """
        Placeholder for a function callback. Function will be called 
        when an association attempt is rejected by a peer AE
        
        Parameters
        ----------
        associate_rq_pdu - pynetdicom.PDU.A_ASSOCIATE_RJ_PDU
            The A-ASSOCIATE-RJ PDU instance received from the peer AE
        """
        pass

    def on_association_released(self):
        pass

    def on_association_aborted(self):
        pass


    # Low-level Association ACSE related callbacks
    def on_send_associate_rq(self, a_associate_rq):
        """
        Placeholder for a function callback. Function will be called 
        immediately prior to encoding and sending an A-ASSOCIATE-RQ to 
        a peer AE
        
        Called by fsm.StateMachine::do_action(AE_2)
        
        Parameters
        ----------
        a_associate_rq - pynetdicom.PDU.A_ASSOCIATE_RQ_PDU
            The A-ASSOCIATE-RQ PDU instance to be encoded and sent
        """
        pass

    def on_send_associate_ac(self, a_associate_ac):
        """
        Placeholder for a function callback. Function will be called 
        immediately prior to encoding and sending an A-ASSOCIATE-AC to a peer AE
        
        Called by fsm.StateMachine::do_action(AE_7)
        
        Parameters
        ----------
        a_associate_ac - pynetdicom.PDU.A_ASSOCIATE_AC_PDU
            The A-ASSOCIATE-AC PDU instance
        """
        pass

    def on_send_associate_rj(self, a_associate_rj):
        """
        Placeholder for a function callback. Function will be called 
        immediately prior to encoding and sending an A-ASSOCIATE-RJ to a peer AE
        
        Called by fsm.StateMachine::do_action(AE_8)
        
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
        
        Called by fsm.StateMachine::do_action(DT_1 or AR_7)
        
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
        
        Called by fsm.StateMachine::do_action(AR_1)
        
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
        
        Called by fsm.StateMachine::do_action(AR_4 or AR_9)
        
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
        
        Called by fsm.StateMachine::do_action(AA_1 or AA_7 or AA_8)
        
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
        
        Called by DULprovider.DULServiceProvider::Socket2PDU()
        
        Parameters
        ----------
        a_associate_rq - pynetdicom.PDU.A_ASSOCIATE_RQ_PDU
            The A-ASSOCIATE-RQ PDU instance
        """
        pass

    def on_receive_associate_ac(self, a_associate_ac):
        """
        Placeholder for a function callback. Function will be called 
        immediately after receiving and decoding an A-ASSOCIATE-AC
        
        Called by DULprovider.DULServiceProvider::Socket2PDU()
        
        Parameters
        ----------
        a_associate_ac - pynetdicom.PDU.A_ASSOCIATE_AC_PDU
            The A-ASSOCIATE-AC PDU instance
        """
        pass

    def on_receive_associate_rj(self, a_associate_rj):
        """
        Placeholder for a function callback. Function will be called 
        immediately after receiving and decoding an A-ASSOCIATE-RJ
        
        Called by DULprovider.DULServiceProvider::Socket2PDU()
        
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
        
        Called by DULprovider.DULServiceProvider::Socket2PDU()
        
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
        
        Called by DULprovider.DULServiceProvider::Socket2PDU()
        
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
        
        Called by DULprovider.DULServiceProvider::Socket2PDU()
        
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
        
        Called by DULprovider.DULServiceProvider::Socket2PDU()
        
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
        
        Called by DIMSEprovider.DIMSEServiceProvider.Send()
        
        Parameters
        ----------
        dimse_msg - pynetdicom.SOPclass.C_ECHO_RQ 
        """
        pass

    def on_send_c_echo_rsp(self, dimse_msg):
        """
        
        Called by DIMSEprovider.DIMSEServiceProvider.Send()
        
        Parameters
        ----------
        dimse_msg - pynetdicom.SOPclass.C_ECHO_RSP
        """

    def on_send_c_store_rq(self, dimse_msg):
        """
        
        Called by DIMSEprovider.DIMSEServiceProvider.Send()
        
        Parameters
        ----------
        store - pynetdicom.SOPclass.C_STORE_RQ 
        """
        pass

    def on_send_c_store_rsp(self, dimse_msg):
        """
        
        Called by DIMSEprovider.DIMSEServiceProvider.Send()
        
        Parameters
        ----------
        store - pynetdicom.SOPclass.C_STORE_RSP
        """
        pass

    def on_send_c_find_rq(self, dimse_msg):
        """
        
        Called by DIMSEprovider.DIMSEServiceProvider.Send()
        
        Parameters
        ----------
        store - pynetdicom.SOPclass.C_FIND_RQ 
        """
        pass

    def on_send_c_find_rsp(self, dimse_msg):
        """
        
        Called by DIMSEprovider.DIMSEServiceProvider.Send()
        
        Parameters
        ----------
        store - pynetdicom.SOPclass.C_FIND_RSP
        """
        pass

    def on_send_c_get_rq(self, dimse_msg):
        """
        Placeholder for a function callback. Function will be called 
        on receiving a C-GET-RQ. The C-GET service is used by a DIMSE to match
        a set of Attributes against the Attributes of a set of composite SOP
        Instances maintained by a peer DIMSE user, and retrieve all composite
        SOP Instances that match. It triggers one or more C-STORE 
        sub-operations on the same Association.
        
        Called by DIMSEprovider.DIMSEServiceProvider.Receive()
        
        Parameters
        ----------
        
            
        Returns
        -------
        matching_sop_instances - list of pydicom.Dataset
            The matching SOP Instances to be sent via C-STORE sub-operations. If
            no matching SOP Instances are found then return the empty list or
            None.
        """
        return None

    def on_send_c_get_rsp(self, dimse_msg):
        """
        Placeholder for a function callback. Function will be called 
        on receiving a C-GET-RQ. The C-GET service is used by a DIMSE to match
        a set of Attributes against the Attributes of a set of composite SOP
        Instances maintained by a peer DIMSE user, and retrieve all composite
        SOP Instances that match. It triggers one or more C-STORE 
        sub-operations on the same Association.
        
        Called by DIMSEprovider.DIMSEServiceProvider.Receive()
        
        Parameters
        ----------
        
            
        Returns
        -------
        matching_sop_instances - list of pydicom.Dataset
            The matching SOP Instances to be sent via C-STORE sub-operations. If
            no matching SOP Instances are found then return the empty list or
            None.
        """
        return None

    def on_send_c_move_rq(self, dimse_msg):
        """
        Placeholder for a function callback. Function will be called 
        on receiving a C-MOVE-RQ. The C-MOVE service is used by a DIMSE to match
        a set of Attributes against the Attributes of a set of composite SOP
        Instances maintained by a peer DIMSE user, and retrieve all composite
        SOP Instances that match. It triggers one or more C-STORE 
        sub-operations on the same Association.
        
        Called by DIMSEprovider.DIMSEServiceProvider.Receive()
        
        Parameters
        ----------
            
        Returns
        -------
        matching_sop_instances - list of pydicom.Dataset
            The matching SOP Instances to be sent via C-STORE sub-operations. If
            no matching SOP Instances are found then return the empty list or
            None.
        """
        return None

    def on_send_c_move_rsp(self, dimse_msg):
        """
        Placeholder for a function callback. Function will be called 
        on receiving a C-MOVE-RQ. The C-MOVE service is used by a DIMSE to match
        a set of Attributes against the Attributes of a set of composite SOP
        Instances maintained by a peer DIMSE user, and retrieve all composite
        SOP Instances that match. It triggers one or more C-STORE 
        sub-operations on the same Association.
        
        Called by DIMSEprovider.DIMSEServiceProvider.Receive()
        
        Parameters
        ----------
            
        Returns
        -------
        matching_sop_instances - list of pydicom.Dataset
            The matching SOP Instances to be sent via C-STORE sub-operations. If
            no matching SOP Instances are found then return the empty list or
            None.
        """
        return None


    def on_receive_c_echo_rq(self, dimse_msg):
        """
        Placeholder for a function callback. Function will be called 
        after receiving and decoding a C-ECHO-RQ. The C-ECHO service is used
        to verify end-to-end communications with a peer DIMSE user.
        
        Called by DIMSEprovider.DIMSEServiceProvider.Receive()
        """
        pass

    def on_receive_c_echo_rsp(self, dimse_msg):
        """
        
        Called by DIMSEprovider.DIMSEServiceProvider.Receive()
        
        Parameters
        ----------
        dimse_msg - pynetdicom.SOPclass.C_ECHO_RSP
        """
        pass

    def on_receive_c_store_rq(self, dimse_msg):
        """
        Placeholder for a function callback. Function will be called 
        on receiving a C-STORE-RQ
        
        Called by DIMSEprovider.DIMSEServiceProvider.Receive()
        
        Parameters
        ----------
        dimse_msg - 
        """
        pass

    def on_receive_c_store_rsp(self, dimse_msg):
        """
        Placeholder for a function callback. Function will be called 
        on receiving a C-STORE-RSP
        
        Called by DIMSEprovider.DIMSEServiceProvider.Receive()
        
        Parameters
        ----------
        dimse_msg - 
        """
        pass

    def on_receive_c_find_rq(self, dimse_msg):
        """
        Placeholder for a function callback. Function will be called 
        on receiving a C-FIND-RQ. The C-FIND service is used by a DIMSE to match
        a set of Attributes against the Attributes of a set of composite SOP
        Instances maintained by a peer DIMSE user, and retrieve all composite
        SOP Instances that match. It triggers one or more C-STORE 
        sub-operations on the same Association.
        
        Called by DIMSEprovider.DIMSEServiceProvider.Receive()
        
        Parameters
        ----------
        
        Returns
        -------
        matching_sop_instances - list of pydicom.Dataset
            The matching SOP Instances. If no matching SOP Instances are found 
            then return the empty list or None.
        """
        return None

    def on_receive_c_find_rsp(self, dimse_msg):
        """
        Placeholder for a function callback. Function will be called 
        on receiving a C-FIND-RSP. The C-FIND service is used by a DIMSE to match
        a set of Attributes against the Attributes of a set of composite SOP
        Instances maintained by a peer DIMSE user, and retrieve all composite
        SOP Instances that match. It triggers one or more C-STORE 
        sub-operations on the same Association.
        
        Called by DIMSEprovider.DIMSEServiceProvider.Receive()
        
        Parameters
        ----------
        
            
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
        
        Called by DIMSEprovider.DIMSEServiceProvider.Receive()
        
        Parameters
        ----------
        
            
        Returns
        -------
        matching_sop_instances - list of pydicom.Dataset
            The matching SOP Instances to be sent via C-STORE sub-operations. If
            no matching SOP Instances are found then return the empty list or
            None.
        """
        return None

    def on_receive_c_get_rsp(self, dimse_msg):
        """
        Placeholder for a function callback. Function will be called 
        on receiving a C-GET-RQ. The C-GET service is used by a DIMSE to match
        a set of Attributes against the Attributes of a set of composite SOP
        Instances maintained by a peer DIMSE user, and retrieve all composite
        SOP Instances that match. It triggers one or more C-STORE 
        sub-operations on the same Association.
        
        Called by DIMSEprovider.DIMSEServiceProvider.Receive()
        
        Parameters
        ----------
        
            
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
        
        Called by DIMSEprovider.DIMSEServiceProvider.Receive()
        
        Parameters
        ----------
            
        Returns
        -------
        matching_sop_instances - list of pydicom.Dataset
            The matching SOP Instances to be sent via C-STORE sub-operations. If
            no matching SOP Instances are found then return the empty list or
            None.
        """
        return None

    def on_receive_c_move_rsp(self, dimse_msg):
        """
        Placeholder for a function callback. Function will be called 
        on receiving a C-MOVE-RQ. The C-MOVE service is used by a DIMSE to match
        a set of Attributes against the Attributes of a set of composite SOP
        Instances maintained by a peer DIMSE user, and retrieve all composite
        SOP Instances that match. It triggers one or more C-STORE 
        sub-operations on the same Association.
        
        Called by DIMSEprovider.DIMSEServiceProvider.Receive()
        
        Parameters
        ----------
            
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
        
        Called by DIMSEprovider.DIMSEServiceProvider.Send()
        
        Parameters
        ----------
        message - pynetdicom.DIMSEmessage.DIMSEMessage
            The DIMSE message to be sent
        """
        pass

    def on_receive_dimse_message(self, message):
        """
        Placeholder for a function callback. Function will be called 
        immediately after receiving and decoding a DIMSE message
        
        Called by DIMSEprovider.DIMSEServiceProvider.Receive()
        
        Parameters
        ----------
        sop_class - pynetdicom.SOPclass.SOPClass
            A SOP Class instance of the type referred to by the message
        message - pydicom.Dataset
            The DIMSE message that was received as a Dataset
        """
        pass
