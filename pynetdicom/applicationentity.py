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
from struct import pack
import sys
import time
import warnings

from pydicom.uid import ExplicitVRLittleEndian, ImplicitVRLittleEndian, \
    ExplicitVRBigEndian, UID, InvalidUID

from pynetdicom.association import Association
from pynetdicom.DULprovider import DULServiceProvider
from pynetdicom.utils import PresentationContext, validate_ae_title

logger = logging.getLogger('pynetdicom')
handler = logging.StreamHandler()
logger.setLevel(logging.WARNING)
formatter = logging.Formatter('%(levelname).1s: %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


class ApplicationEntity(object):
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

    To use as an SCU (C-ECHO example):
        from pynetdicom.ae import AE
        from pynetdicom.uid import VerificationSOPClass
        
        # Specify which SOP Classes are supported as an SCU
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate(192.168.2.1, 104)
        
        if assoc.is_established:
            status = assoc.send_c_echo()
            
            assoc.Release()
            
        ae.quit()
        
    To use as an SCP (C-STORE example):
        from pynetdicom.ae import AE
        from pynetdicom.SOPclasses import CTImageStorageSOPClass
    
        # Specify the listen port and which SOP Classes are supported as an SCP
        ae = AE(port=104, scp_sop_class=[CTImageStorageSOPClass])
        
        # Define your callbacks
        def on_c_store(sop_class, dataset):
            # Insert your C-STORE handling code here
            
        ae.on_c_store = on_c_store
        
        # Start the SCP server
        ae.start()

    Parameters
    ----------
    ae_title - str, optional
        The AE title of the Application Entity (default: PYNETDICOM)
    port - int, optional
        The port number to listen for connections on when acting as an SCP and
        to use for making connections to the peer when acting as an SCU
        (default: the first available port)
    scu_sop_class - list of pydicom.uid.UID or list of str or list of 
    pynetdicom.SOPclass.ServiceClass subclasses, optional
        List of the supported SOP classes when the AE is operating as an SCU. 
        Either scu_sop_class or scp_sop_class must have values
    scp_sop_class - list of pydicom.uid.UID or list of UID strings or list of 
    pynetdicom.SOPclass.ServiceClass subclasses, optional
        List of the supported SOP classes when the AE is operating as an SCP
        Either scu_sop_class or scp_sop_class must have values
    transfer_syntax - list of pydicom.uid.UID or list of str or list of 
    pynetdicom.SOPclass.ServiceClass subclasses, optional
        List of supported Transfer Syntax UIDs (default: Explicit VR Little 
        Endian, Implicit VR Little Endian, Explicit VR Big Endian)

    Attributes
    ----------
    acse_timeout - int
        The maximum amount of time (in seconds) to wait for association related
        messages. A value of 0 means no timeout.
    active_associations - list of pynetdicom.association.Association
        The currently active associations between the local and peer AEs
    address - str
        The local AE's TCP/IP address
    ae_title - str
        The local AE's title
    client_socket - socket.socket
        The socket used for connections with peer AEs
    dimse_timeout - int
        The maximum amount of time (in seconds) to wait for DIMSE related
        messages. A value of 0 means no timeout.
    network_timeout - int
        The maximum amount of time (in seconds) to wait for network messages. 
        A value of 0 means no timeout.
    maximum_associations - int
        The maximum number of simultaneous associations (default: 2)
    maximum_pdu_size - int
        The maximum PDU receive size in bytes. A value of 0 means there is no 
        maximum size (default: 16382)
    port - int
        The local AE's listen port number when acting as an SCP or connection
        port when acting as an SCU. A value of 0 indicates that the operating
        system should choose the port.
    presentation_contexts_scu - List of pynetdicom.utils.PresentationContext
        The presentation context list when acting as an SCU (SCU only)
    presentation_contexts_scp - List of pynetdicom.utils.PresentationContext
        The presentation context list when acting as an SCP (SCP only)
    require_calling_aet - str
        If not empty str, the calling AE title must match `require_calling_aet`
        (SCP only)
    require_called_aet - str
        If not empty str the called AE title must match `required_called_aet`
        (SCP only)
    scu_supported_sop - List of pydicom.uid.UID
        The SOP Classes supported when acting as an SCU (SCU only)
    scp_supported_sop - List of pydicom.uid.UID
        The SOP Classes supported when acting as an SCP (SCP only)
    transfer_syntaxes - List of pydicom.uid.UID
        The supported transfer syntaxes
    """
    def __init__(self, 
                 ae_title='PYNETDICOM',
                 port=0, 
                 scu_sop_class=[], 
                 scp_sop_class=[],
                 transfer_syntax=[ExplicitVRLittleEndian,
                                  ImplicitVRLittleEndian,
                                  ExplicitVRBigEndian]):

        self.address = platform.node()
        self.port = port
        self.ae_title = ae_title

        if scu_sop_class == [] and scp_sop_class == []:
            raise ValueError("No supported SOP Class UIDs supplied during "
                "ApplicationEntity instantiation")

        self.scu_supported_sop = scu_sop_class
        self.scp_supported_sop = scp_sop_class

        # The transfer syntax(es) available to the AE
        #   At a minimum this must be ... FIXME
        self.transfer_syntaxes = transfer_syntax
        
        # Default maximum simultaneous associations
        self.maximum_associations = 2
        
        # Default maximum PDU receive size (in bytes)
        self.maximum_pdu_size = 16382
        
        # Default timeouts
        self.acse_timeout = 0
        self.network_timeout = 60
        self.dimse_timeout = 0
        
        # Require Calling/Called AE titles to match if value is non-empty str
        self.require_calling_aet = ''
        self.require_called_aet = ''
        
        # List of active association objects
        self.active_associations = []
        
        # Build presentation context list to be:
        #   * sent to remote AE when requesting association
        #       (presentation_contexts_scu)
        #   * used to decide whether to accept or reject when remote AE 
        #       requests association (presentation_contexts_scp)
        #       although I think they should be accepted and then aborted
        #       due to no acceptable presentation contexts rather than rejected
        #
        #   See PS3.8 Sections 7.1.1.13 and 9.3.2.2
        #
        # This should maybe be given its own property setter/getter
        #   for when the user changes scu_supported_sop and/or scp_supported_sop
        self.presentation_contexts_scu = []
        self.presentation_contexts_scp = []
        for [pc_output, sop_input] in \
                    [[self.presentation_contexts_scu, self.scu_supported_sop],
                     [self.presentation_contexts_scp, self.scp_supported_sop]]:
            
            for ii, sop_class in enumerate(sop_input):
                # Must be an odd integer between 1 and 255
                presentation_context_id = ii * 2 + 1
                abstract_syntax = None
                
                # If supplied SOP Class is already a pydicom.UID class
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
                    logger.warning("More than 126 supported SOP Classes "
                        "have been supplied to the Application Entity, but the "
                        "Presentation Context Definition ID can only be an odd "
                        "integer between 1 and 255. The remaining SOP Classes "
                        "will not be included")
                    break

        self.local_socket = None

        # Used to terminate AE when running as an SCP
        self.__Quit = False

    def start(self):
        """
        When running the AE as an SCP this needs to be called to start the main 
        loop, it listens for connection attempts on `local_socket` and attempts 
        to Associate with them. 
        
        Successful associations get added to `active_associations`
        """

        # If the SCP has no supported SOP Classes then there's no point 
        #   running as a server
        if self.scp_supported_sop == []:
            logger.error("AE is running as an SCP but no supported SOP classes "
                "for use with the SCP have been included during"
                "ApplicationEntity() initialisation or by setting the "
                "scp_supported_sop attribute")
            return

        # The socket to listen for connections on, port is always specified
        self.local_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.local_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.local_socket.bind(('', self.port))
        self.local_socket.listen(1)

        no_loops = 0
        while True:
            try:
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
                                             pack('ll', 10, 0))
                    
                    # Create a new Association
                    # Association(local_ae, local_socket=None, peer_ae=None)
                    assoc = Association(self, 
                                        client_socket, 
                                        max_pdu=self.maximum_pdu_size)
                    self.active_associations.append(assoc)

                # Delete dead associations
                #   assoc.is_alive() is inherited from threading.thread
                self.active_associations[:] = [assoc for assoc in 
                    self.active_associations if assoc.is_alive()]
                    
                # Every 50 loops run the garbage collection
                if no_loops % 51 == 0:
                    gc.collect()
                    no_loops = 0
                
                no_loops += 1
            
            except KeyboardInterrupt:
                self.stop()

    def stop(self):
        for aa in self.active_associations:
            aa.Kill()
            if self.local_socket:
                self.local_socket.close()
        self.__Quit = True
        
        while True:
            sys.exit(0)

    def quit(self):
        self.stop()

    def associate(self, addr, port, ae_title='ANY-SCP', 
                                max_pdu=16382, ext_neg=None):
        """Attempts to associate with a remote application entity
        
        When requesting an association the local AE is acting as an SCU
        
        Parameters
        ----------
        addr - str
            The peer AE's TCP/IP address (IPv4)
        port - int
            The peer AE's listen port number
        ae_title - str, optional
            The peer AE's title
        max_pdu - int, optional
            The maximum PDV receive size in bytes to use when negotiating the 
            association
        ext_neg - List of UserInformation objects, optional
            Used if extended association negotiation is required
            
        Returns
        -------
        assoc : pynetdicom.association.Association or None
            The Association if it was successfully established, None if failed
            or was rejected or aborted
        """
        if not isinstance(addr, str):
            raise ValueError("ip_address must be a valid IPv4 string")

        if not isinstance(port, int):
            raise ValueError("port must be a valid port number")

        peer_ae = {'AET' : validate_ae_title(ae_title), 
                   'Address' : addr, 
                   'Port' : port}

        # Associate
        assoc = Association(self, 
                            RemoteAE=peer_ae,
                            acse_timeout=self.acse_timeout,
                            dimse_timeout=self.dimse_timeout,
                            max_pdu=max_pdu,
                            ext_neg=ext_neg)

        # Endlessly loops while the Association negotiation is taking place
        while not assoc.AssociationEstablished \
                and not assoc.AssociationRefused and not assoc.DUL.kill:
            time.sleep(0.1)

        # If the Association was established
        if assoc.AssociationEstablished:
            self.active_associations.append(assoc)
            return assoc

        return assoc
    
    def __str__(self):
        """ Prints out the attribute values and status for the AE """
        s = "\n"
        s += "Application Entity '%s' on %s:%s\n" %(self.ae_title, self.address, self.port)

        s += "\n"
        s += "  Available Transfer Syntax(es):\n"
        for syntax in self.transfer_syntaxes:
            s += "\t%s\n" %syntax
        
        s += "\n"
        s += "  Supported SOP Classes (SCU):\n"
        if len(self.scu_supported_sop) == 0:
            s += "\tNone\n"
        for sop_class in self.scu_supported_sop:
            s += "\t%s\n" %sop_class
        
        s += "\n"
        s += "  Supported SOP Classes (SCP):\n"
        if len(self.scp_supported_sop) == 0:
            s += "\tNone\n"
        for sop_class in self.scp_supported_sop:
            s += "\t%s\n" %sop_class
        
        s += "\n"
        s += "  ACSE timeout: %s s\n" %self.acse_timeout
        s += "  DIMSE timeout: %s s\n" %self.dimse_timeout
        s += "  Network timeout: %s s\n" %self.network_timeout
        
        if self.require_called_aet != '' or self.require_calling_aet != '':
            s += "\n"
        if self.require_calling_aet != '':
            s += "  Required calling AE title: %s\n" %self.require_calling_aet
        if self.require_called_aet != '':
            s += "  Required called AE title: %s\n" %self.require_called_aet
        
        s += "\n"
        
        # Association information
        s += '  Association(s): %s/%s\n' %(len(self.active_associations), self.maximum_associations)
        
        for assoc in self.active_associations:
            s += '\tPeer: %s on %s:%s\n' %(assoc.RemoteAE['AET'], assoc.RemoteAE['Address'], assoc.RemoteAE['Port'])
        
        return s

    @property
    def acse_timeout(self):
        return self.__acse_timeout
        
    @acse_timeout.setter
    def acse_timeout(self, value):
        try:
            if 0 <= value:
                self.__acse_timeout = value
            else:
                self.__acse_timeout = 0
                
            return
        except:
            logger.warning("ACSE timeout must be a numeric "
                "value greater than or equal to 0. Defaulting to 0 (no "
                "timeout)")
        
        self.__acse_timeout = 0

    @property
    def ae_title(self):
        return self.__ae_title

    @ae_title.setter
    def ae_title(self, value):
        try:
            self.__ae_title = validate_ae_title(value)
        except:
            raise

    @property
    def dimse_timeout(self):
        return self.__dimse_timeout
        
    @dimse_timeout.setter
    def dimse_timeout(self, value):
        try:
            if 0 <= value:
                self.__dimse_timeout = value
            else:
                self.__dimse_timeout = 0
                
            return
        except:
            logger.warning("ApplicationEntity DIMSE timeout must be a numeric "
                "value greater than or equal to 0. Defaulting to 0 (no "
                "timeout)")
        
        self.__dimse_timeout = 0
        
    @property
    def network_timeout(self):
        return self.__network_timeout
        
    @network_timeout.setter
    def network_timeout(self, value):
        try:
            if 0 <= value:
                self.__network_timeout = value
            else:
                self.__network_timeout = 60
                
            return
        except:
            logger.warning("ApplicationEntity network timeout must be a "
                "numeric value greater than or equal to 0. Defaulting to 60 "
                "seconds")
        
        self.__network_timeout = 60
    
    @property
    def maximum_associations(self):
        return self.__maximum_associations
        
    @maximum_associations.setter
    def maximum_associations(self, value):
        try:
            if 1 <= value:
                self.__maximum_associations = value
                return
            else:
                logger.warning("AE maximum associations must be greater than "
                    "or equal to 1")
                self.__maximum_associations = 1
        except:
            logger.warning("AE maximum associations must be a numerical value "
                "greater than or equal to 1. Defaulting to 1")
                
        self.__maximum_associations = 1

    @property
    def maximum_pdu_size(self):
        return self.__maximum_pdu_size

    @maximum_pdu_size.setter
    def maximum_pdu_size(self, value):
        # Bounds and type checking of the received maximum length of the 
        #   variable field of P-DATA-TF PDUs (in bytes)
        #   * Must be numerical, greater than or equal to 0 (0 indicates
        #       no maximum length (PS3.8 Annex D.1.1)
        try:
            if 0 <= value:
                self.__maximum_pdu_size = value
                return
        except:
            logger.warning("ApplicationEntity failed to set maximum PDU size "
                    "of '%s', defaulting to 16832 bytes" %value)
        
        self.__maximum_pdu_size = 16382

    @property
    def port(self):
        return self.__port
        
    @port.setter
    def port(self, value):
        try:
            if isinstance(value, int):
                if 0 <= value:
                    self.__port = value
                    return
                else:
                    raise ValueError("AE port number must be greater than or "
                            "equal to 0")
                    return
            else:
                raise TypeError("AE port number must be an integer greater "
                        "than or equal to 0")
                return
                            
        except Exception as e:
            raise e

    @property
    def require_calling_aet(self):
        return self.__require_calling_aet
        
    @require_calling_aet.setter
    def require_calling_aet(self, value):
        try:
            if 0 < len(value.strip()) <= 16:
                self.__require_calling_aet = value.strip()
            elif len(value.strip()) > 16:
                self.__require_calling_aet = value.strip()[:16]
                logger.warning("ApplicationEntity tried to set required "
                    "calling AE title with more than 16 characters; title will "
                    "be truncated to '%s'" %value)
            else:
                self.__require_calling_aet = ''
            return
        
        except:
            logger.warning("ApplicationEntity failed to set required calling "
                "AE title, defaulting to empty string (i.e. calling AE title "
                "not required to match)")

        self.__require_calling_aet = ''
        
    @property
    def require_called_aet(self):
        return self.__require_called_aet
        
    @require_called_aet.setter
    def require_called_aet(self, value):
        try:
            if 0 < len(value.strip()) <= 16:
                self.__require_called_aet = value.strip()
            elif len(value.strip()) > 16:
                self.__require_called_aet = value.strip()[:16]
                logger.warning("ApplicationEntity tried to set required "
                    "called AE title with more than 16 characters; title will "
                    "be truncated to '%s'" %value)
            else:
                self.__require_called_aet = ''
            return
        except:
            logger.warning("ApplicationEntity failed to set required called AE "
                "title, defaulting to empty string (i.e. called AE title not "
                "required to match)")

        self.__require_called_aet = ''

    @property
    def scu_supported_sop(self):
        return self.__scu_supported_sop
    
    @scu_supported_sop.setter
    def scu_supported_sop(self, sop_list):
        """
        A valid SOP is either a str UID (ie '1.2.840.10008.1.1') or a
        valid pydicom.uid.UID object (UID.is_valid() shouldn't cause an 
        exception) or a pynetdicom.SOPclass.ServiceClass subclass with a UID 
        attribute(ie VerificationSOPClass)
        """
        self.__scu_supported_sop = []
        
        try:
            for sop_class in sop_list:
                try:
                    if isinstance(sop_class, str):
                        sop_uid = UID(sop_class)
                        sop_uid.is_valid()
                    elif isinstance(sop_class, UID):
                        sop_uid = sop_class
                        sop_uid.is_valid()
                    elif 'UID' in sop_class.__dict__.keys():
                        sop_uid = UID(sop_class.UID)
                        sop_uid.is_valid()
                    else:
                        raise ValueError("SCU SOP class must be a UID str, "
                                "UID or ServiceClass subclass")
                                
                    self.__scu_supported_sop.append(sop_uid)
                
                except InvalidUID:
                    raise ValueError("SCU SOP classes contained an invalid "
                            "UID string")
                except Exception as e:
                    logger.warning("Invalid SCU SOP class '%s'" %sop_class)

            if sop_list != [] and self.__scu_supported_sop == []:
                raise ValueError("No valid SCU SOP classes were supplied")
        except TypeError:
            raise ValueError("scu_sop_class must be a list")
        except:
            raise ValueError("scu_sop_class must be a list of SOP Classes")

    @property
    def scp_supported_sop(self):
        return self.__scp_supported_sop
    
    @scp_supported_sop.setter
    def scp_supported_sop(self, sop_list):
        """
        A valid SOP is either a str UID (ie '1.2.840.10008.1.1') or a
        valid pydicom.uid.UID object (UID.is_valid() shouldn't cause an 
        exception) or a pynetdicom.SOPclass.ServiceClass subclass with a UID 
        attribute(ie VerificationSOPClass)
        """
        self.__scp_supported_sop = []

        try:
            for sop_class in sop_list:
                try:
                    if isinstance(sop_class, str):
                        sop_uid = UID(sop_class)
                        sop_uid.is_valid()
                    elif isinstance(sop_class, UID):
                        sop_uid = sop_class
                        sop_uid.is_valid()
                    elif 'UID' in sop_class.__dict__.keys():
                        sop_uid = UID(sop_class.UID)
                        sop_uid.is_valid()
                    else:
                        raise ValueError("SCU SOP class must be a UID str, "
                                "UID or ServiceClass subclass")

                    self.__scp_supported_sop.append(sop_uid)

                except InvalidUID:
                    raise ValueError("scp_sop_class must be a list of "
                            "SOP Classes")
                except Exception as e:
                    logger.warning("Invalid SCP SOP class '%s'" %sop_class)

            if sop_list != [] and self.__scp_supported_sop == []:
                raise ValueError("No valid SCP SOP classes were supplied")
        except TypeError:
            raise ValueError("scp_sop_class must be a list")
        except:
            raise ValueError("scp_sop_class must be a list of SOP Classes")

    @property
    def transfer_syntaxes(self):
        return self.__transfer_syntaxes
        
    @transfer_syntaxes.setter
    def transfer_syntaxes(self, transfer_syntaxes):
        
        self.__transfer_syntaxes = []
        
        try:
            for syntax in transfer_syntaxes:
                try:
                    if isinstance(syntax, str):
                        sop_uid = UID(syntax)
                        sop_uid.is_valid()
                    elif isinstance(syntax, UID):
                        sop_uid = syntax
                        sop_uid.is_valid()
                    elif 'UID' in sop_class.__dict__.keys():
                        sop_uid = UID(syntax.UID)
                        sop_uid.is_valid()
                    else:
                        raise ValueError("Transfer syntax SOP class must be "
                                    "a UID str, UID or ServiceClass subclass")
                    
                    if sop_uid.is_transfer_syntax:
                        self.__transfer_syntaxes.append(sop_uid)
                    else:
                        logger.warning("Attempted to add a non-transfer syntax "
                            "UID '%s'" %syntax)
                
                except InvalidUID:
                    raise ValueError("Transfer syntax contained an invalid "
                            "UID string")
            if self.__transfer_syntaxes == []:
                raise ValueError("Transfer syntax must be a list of SOP Classes")
        except:
            raise ValueError("Transfer syntax SOP class must be a "
                                "UID str, UID or ServiceClass subclass")


    # Communication related callback
    def on_receive_connection(self):
        pass


    # High-level Association related callbacks
    def on_association_requested(self, primitive):
        pass

    def on_association_accepted(self, primitive):
        """
        Placeholder for a function callback. Function will be called 
        when an association attempt is accepted by either the local or peer AE
        
        Parameters
        ----------
        associate_ac_pdu - pynetdicom.PDU.A_ASSOCIATE_AC_PDU
            The A-ASSOCIATE-AC PDU instance received from the peer AE
        """
        pass

    def on_association_rejected(self, primitive):
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

    def on_association_aborted(self, primitive):
        pass


    # Association PDU send/receive related callbacks
    def on_send_associate_rq(self, a_associate_rq):
        """
        Placeholder for a function callback. Function will be called 
        immediately prior to encoding and sending an A-ASSOCIATE-RQ PDU to 
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
        immediately prior to encoding and sending an A-ASSOCIATE-AC PDU to a
        peer AE
        
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
        immediately prior to encoding and sending an A-ASSOCIATE-RJ PDU to a 
        peer AE
        
        Called by fsm.StateMachine::do_action(AE_8)
        
        Parameters
        ----------
        a_associate_rj - pynetdicom.PDU.A_ASSOCIATE_RJ_PDU
            The A-ASSOCIATE-RJ PDU instance
        """
        pass

    def on_send_release_rq(self, a_release_rq):
        """
        Placeholder for a function callback. Function will be called 
        immediately prior to encoding and sending an A-RELEASE-RQ  PDU to a 
        peer AE
        
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
        immediately prior to encoding and sending an A-RELEASE-RP PDU to a 
        peer AE
        
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
        immediately prior to encoding and sending an A-ABORT PDU to a peer AE
        
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


    # Data PDU send/receive callbacks
    def on_send_data_tf(self, p_data_tf):
        """
        Placeholder for a function callback. Function will be called 
        immediately prior to encoding and sending an P-DATA-TF PDU to a peer AE
        
        Called by fsm.StateMachine::do_action(DT_1 or AR_7)
        
        Parameters
        ----------
        a_release_rq - pynetdicom.PDU.P_DATA_TF_PDU
            The P-DATA-TF PDU instance
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


    # DIMSE message send/receive related callbacks
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
