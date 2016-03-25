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
    """
    Represents a DICOM Application Entity (AE)
    
    An AE may be either a server (Service Class Provider or SCP) or a client
    (Service Class User or SCU).
    
    SCP 
    ---
    To use an AE as an SCP, you need to specify the listen `port` number that 
    peer AE SCUs can use to request Associations over, as well as the SOP 
    Classes that the SCP supports (`scp_sop_class`). If the SCP is being used
    for anything other than the C-ECHO DIMSE service you also need to implement
    the required callbacks.
    
    The SCP can then be started using `ApplicationEntity.start()`
    
    C-STORE SCP Example
    ~~~~~~~~~~~~~~~~~~~
    .. code-block:: python 

            from pynetdicom import AE, StorageSOPClassList
    
            # Specify the listen port and which SOP Classes are supported
            ae = AE(port=11112, scp_sop_class=StorageSOPClassList)

            # Define the callback for receiving a C-STORE request
            def on_c_store(dataset):
                # Insert your C-STORE handling code here

                # Must return a valid C-STORE status - 0x0000 is Success
                return 0x0000

            ae.on_c_store = on_c_store

            # Start the SCP
            ae.start()
        
    SCU
    ---
    To use an AE as an SCU you only need to specify the SOP Classes that the SCU
    supports (`scu_sop_class`) and then call `ApplicationEntity.associate(addr, 
    port)` where *addr* and *port* are the TCP/IP address and the listen port
    number of the peer SCP, respectively. 
    
    Once the Association is established you can then request any of the DIMSE-C 
    or DIMSE-N services.
    
    C-ECHO SCU Example
    ~~~~~~~~~~~~~~~~~~
    .. code-block:: python

            from pynetdicom import AE, VerificationSOPClass

            # Specify which SOP Classes are supported as an SCU
            ae = AE(scu_sop_class=[VerificationSOPClass])
            
            # Request an association with a peer SCP
            assoc = ae.associate(addr=192.168.2.1, port=104)

            if assoc.is_established:
                status = assoc.send_c_echo()

                # Release the association
                assoc.Release()

    Parameters
    ----------
    ae_title : str, optional
        The AE title of the Application Entity (default: PYNETDICOM)
    port : int, optional
        The port number to listen for connections on when acting as an SCP
        (default: the first available port)
    scu_sop_class : list of pydicom.uid.UID or list of str or list of 
    pynetdicom.SOPclass.ServiceClass subclasses, optional
        List of the supported SOP Class UIDs when running as an SCU. 
        Either `scu_sop_class` or `scp_sop_class` must have values
    scp_sop_class : list of pydicom.uid.UID or list of UID strings or list of 
    pynetdicom.SOPclass.ServiceClass subclasses, optional
        List of the supported SOP Class UIDs when running as an SCP.
        Either scu_`sop_class` or `scp_sop_class` must have values
    transfer_syntax : list of pydicom.uid.UID or list of str or list of 
    pynetdicom.SOPclass.ServiceClass subclasses, optional
        List of supported Transfer Syntax UIDs (default: Explicit VR Little 
        Endian, Implicit VR Little Endian, Explicit VR Big Endian)

    Attributes
    ----------
    acse_timeout : int
        The maximum amount of time (in seconds) to wait for association related
        messages. A value of 0 means no timeout. (default: 0)
    active_associations : list of pynetdicom.association.Association
        The currently active associations between the local and peer AEs
    address : str
        The local AE's TCP/IP address
    ae_title : str
        The local AE's title
    client_socket : socket.socket
        The socket used for connections with peer AEs
    dimse_timeout : int
        The maximum amount of time (in seconds) to wait for DIMSE related
        messages. A value of 0 means no timeout. (default: 0)
    network_timeout : int
        The maximum amount of time (in seconds) to wait for network messages. 
        A value of 0 means no timeout. (default: 60)
    maximum_associations : int
        The maximum number of simultaneous associations (default: 2)
    maximum_pdu_size : int
        The maximum PDU receive size in bytes. A value of 0 means there is no 
        maximum size (default: 16382)
    port : int
        The local AE's listen port number when acting as an SCP or connection
        port when acting as an SCU. A value of 0 indicates that the operating
        system should choose the port.
    presentation_contexts_scu : List of pynetdicom.utils.PresentationContext
        The presentation context list when acting as an SCU (SCU only)
    presentation_contexts_scp : List of pynetdicom.utils.PresentationContext
        The presentation context list when acting as an SCP (SCP only)
    require_calling_aet : str
        If not empty str, the calling AE title must match `require_calling_aet`
        (SCP only)
    require_called_aet : str
        If not empty str the called AE title must match `required_called_aet`
        (SCP only)
    scu_supported_sop : List of pydicom.uid.UID
        The SOP Classes supported when acting as an SCU (SCU only)
    scp_supported_sop : List of pydicom.uid.UID
        The SOP Classes supported when acting as an SCP (SCP only)
    transfer_syntaxes : List of pydicom.uid.UID
        The supported transfer syntaxes
    """
    def __init__(self, ae_title='PYNETDICOM',
                       port=0, 
                       scu_sop_class=[], 
                       scp_sop_class=[],
                       transfer_syntax=[ExplicitVRLittleEndian,
                                        ImplicitVRLittleEndian,
                                        ExplicitVRBigEndian]):

        self.address = platform.node()
        self.port = port
        self.ae_title = ae_title

        # Make sure that one of scu_sop_class/scp_sop_class is not empty
        if scu_sop_class == [] and scp_sop_class == []:
            raise ValueError("No supported SOP Class UIDs supplied during "
                "ApplicationEntity instantiation")

        self.scu_supported_sop = scu_sop_class
        self.scp_supported_sop = scp_sop_class

        # The transfer syntax(es) available to the AE
        #   At a minimum this must be ... FIXME
        self.transfer_syntaxes = transfer_syntax
        
        # The user may require the use of Extended Negotiation items
        self.extended_negotiation = []
        
        # Default maximum simultaneous associations
        self.maximum_associations = 2
        
        # Default maximum PDU receive size (in bytes)
        self.maximum_pdu_size = 16382
        
        # Default timeouts - 0 means no timeout
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
        self.__quit = False

    def start(self):
        """
        When running the AE as an SCP this needs to be called to start the main 
        loop, it listens for connections on `local_socket` and if they request
        association starts a new Association thread
        
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

        # Bind the local_socket to the specified listen port
        self.__bind_socket()

        no_loops = 0
        while True:
            try:
                time.sleep(0.1)
                
                if self.__quit:
                    break
                
                # Monitor client_socket for association requests and
                #   appends any associations to self.active_associations
                self.__monitor_socket()
                
                # Delete dead associations
                self.__cleanup_associations()

                # Every 50 loops run the garbage collection
                if no_loops % 51 == 0:
                    gc.collect()
                    no_loops = 0
                
                no_loops += 1
            
            except KeyboardInterrupt:
                self.stop()

    def __bind_socket(self):
        """ 
        AE.start(): Set up and bind the socket. Separated out from start() to 
        enable better unit testing
        """
        # The socket to listen for connections on, port is always specified
        self.local_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.local_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.local_socket.bind(('', self.port))
        self.local_socket.listen(1)

    def __monitor_socket(self):
        """ 
        AE.start(): Monitors the local socket to see if anyone tries to connect 
        and if so, creates a new association. Separated out from start() to 
        enable better unit testing
        """
        read_list, _, _ = select.select([self.local_socket], [], [], 0)

        # If theres a connection
        if read_list:
            client_socket, remote_address = self.local_socket.accept()
            client_socket.setsockopt(socket.SOL_SOCKET, 
                                     socket.SO_RCVTIMEO, 
                                     pack('ll', 10, 0))

            # Create a new Association
            # Association(local_ae, local_socket=None, max_pdu=16382)
            assoc = Association(self, 
                                client_socket, 
                                max_pdu=self.maximum_pdu_size,
                                acse_timeout=self.acse_timeout,
                                dimse_timeout=self.dimse_timeout)

            self.active_associations.append(assoc)

    def __cleanup_associations(self):
        """ 
        AE.start(): Removes any dead associations from self.active_associations 
        by checking to see if the association thread is still alive. Separated 
        out from start() to enable better unit testing
        """
        #   assoc.is_alive() is inherited from threading.thread
        self.active_associations = [assoc for assoc in 
                    self.active_associations if assoc.is_alive()]

    def stop(self):
        """
        When running as an SCP, calling stop() will kill all associations,
        close the listen socket and quit
        """
        for aa in self.active_associations:
            aa.kill()
        
        if self.local_socket:
            self.local_socket.close()
        
        self.__quit = True
        
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
        addr : str
            The peer AE's TCP/IP address (IPv4)
        port : int
            The peer AE's listen port number
        ae_title : str, optional
            The peer AE's title
        max_pdu : int, optional
            The maximum PDV receive size in bytes to use when negotiating the 
            association
        ext_neg : List of UserInformation objects, optional
            Used if extended association negotiation is required

        Returns
        -------
        assoc : pynetdicom.association.Association
            The Association thread
        """
        if not isinstance(addr, str):
            raise ValueError("ip_address must be a valid IPv4 string")

        if not isinstance(port, int):
            raise ValueError("port must be a valid port number")

        peer_ae = {'AET' : validate_ae_title(ae_title), 
                   'Address' : addr, 
                   'Port' : port}

        # Associate
        assoc = Association(local_ae=self,
                            peer_ae=peer_ae,
                            acse_timeout=self.acse_timeout,
                            dimse_timeout=self.dimse_timeout,
                            max_pdu=max_pdu,
                            ext_neg=ext_neg)

        # Endlessly loops while the Association negotiation is taking place
        while (not assoc.is_established and 
                not assoc.is_refused and 
                not assoc.is_aborted and
                not assoc.dul.kill):
            time.sleep(0.1)

        # If the Association was established
        if assoc.is_established:
            self.active_associations.append(assoc)

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
        s += '  Association(s): %s/%s\n' %(len(self.active_associations), 
                                           self.maximum_associations)
        
        for assoc in self.active_associations:
            s += '\tPeer: %s on %s:%s\n' %(assoc.peer_ae['AET'], 
                                           assoc.peer_ae['Address'], 
                                           assoc.peer_ae['Port'])
        
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


    # High-level DIMSE-C callbacks - user should implement these as required
    def on_c_echo(self):
        """
        Function callback for when a C-ECHO request is received. Must be 
        defined by the user prior to calling AE.start()
        
        Called during pynetdicom.SOPclass.VerificationServiceClass::SCP() prior
        to sending a response
        
        Example
        -------
        def on_c_echo():
            print('Received C-ECHO')
            
        ae = AE()
        ae.on_c_echo = on_c_echo
        
        ae.start()
        """
        raise NotImplementedError("User must implement the AE.on_c_echo "
                    "function prior to calling AE.start()")

    def on_c_store(self, dataset):
        """
        Function callback for when a dataset is received following a C-STORE 
        request from a peer AE. Must be defined by the user prior to calling 
        AE.start() and must return a valid C-STORE status value or the 
        corresponding pynetdicom.SOPclass.Status object.
        
        Example
        -------
        from pynetdicom import AE, StorageSOPClassList
        
        def on_c_store(dataset):
            print(dataset.PatientID)
            
            return 0x0000
            
        ae = AE(11112, scp_sop_class=StorageSOPClassList)
        ae.on_c_store = on_c_store
        
        ae.start()
        
        Parameters
        ----------
        dataset : pydicom.dataset.Dataset
            The DICOM dataset sent in the C-STORE request
            
        Returns
        -------
        status : pynetdicom.SOPclass.Status or int
            A valid return status for the C-STORE operation (see PS3.4 Annex 
            B.2.3), must be one of the following Status objects or the 
            corresponding integer value:
                Success status
                    StorageServiceClass.Success
                        Success - 0x0000
                    
                Failure statuses
                    StorageServiceClass.OutOfResources
                        Refused: Out of Resources - 0xA7xx
                    StorageServiceClass.DataSetDoesNotMatchingSOPClassFailure
                        Error: Data Set does not match SOP Class - 0xA9xx
                    StorageServiceClass.CannotUnderstand
                        Error: Cannot understand - 0xCxxx
                
                Warning statuses
                    StorageServiceClass.CoercionOfDataElements
                        Coercion of Data Elements - 0xB000
                    StorageServiceClass.DataSetDoesNotMatchSOPClassWarning
                        Data Set does not matching SOP Class - 0xB007
                    StorageServiceClass.ElementsDiscarded
                        Elements Discarded - 0xB006
        """
        raise NotImplementedError("User must implement the AE.on_c_store "
                    "function prior to calling AE.start()")

    def on_c_find(self, dataset):
        """
        Function callback for when a dataset is received following a C-FIND.
        Must be defined by the user prior to calling AE.start() and must return
        a valid pynetdicom.SOPclass.Status object. In addition,the 
        AE.on_c_find_cancel() callback must also be defined
        
        Called by QueryRetrieveFindSOPClass subclasses in SCP()
        
        Parameters
        ----------
        dataset : pydicom.dataset.Dataset
            The DICOM dataset sent via the C-FIND
            
        Yields
        ------
        status : pynetdicom.SOPclass.Status or int
            A valid return status for the C-FIND operation (see PS3.4 Annex 
            C.4.1.1.4), must be one of the following Status objects or the 
            corresponding integer value:
                Success status
                    QueryRetrieveFindSOPClass.Success
                        Matching is complete - No final Identifier is 
                        supplied - 0x0000
                    
                Failure statuses
                    QueryRetrieveFindSOPClass.OutOfResources
                        Refused: Out of Resources - 0xA700
                    QueryRetrieveFindSOPClass.IdentifierDoesNotMatchSOPClass
                        Identifier does not match SOP Class - 0xA900
                    QueryRetrieveFindSOPClass.UnableToProcess
                        Unable to process - 0xCxxx
                
                Cancel status
                    QueryRetrieveFindSOPClass.MatchingTerminatedDueToCancelRequest
                        Matching terminated due to Cancel request - 0xFE00
                    
                Pending statuses
                    QueryRetrieveFindSOPClass.Pending
                        Matches are continuing - Current Match is supplied and 
                        any Optional Keys were supported in the same manner as 
                        Required Keys - 0xFF00
                    QueryRetrieveFindSOPClass.PendingWarning
                        Matches are continuing - Warning that one or more 
                        Optional Keys were not supported for existence and/or
                        matching for this Identifier - 0xFF01
        dataset : pydicom.dataset.Dataset or None
            A matching dataset if the status is Pending, None otherwise
        """
        raise NotImplementedError("User must implement the AE.on_c_find "
                    "function prior to calling AE.start()")

    def on_c_find_cancel(self):
        raise NotImplementedError("User must implement the "
                    "AE.on_c_find_cancel function prior to calling AE.start()")

    def on_c_get(self, dataset):
        """
        Function callback for when a dataset is received following a C-STORE.
        Must be defined by the user prior to calling AE.start() and must return
        a valid pynetdicom.SOPclass.Status object. In addition,the 
        AE.on_c_get_cancel() callback must also be defined
        
        Parameters
        ----------
        dataset : pydicom.dataset.Dataset
            The DICOM dataset sent via the C-STORE
            
        Returns
        -------
        status : pynetdicom.SOPclass.Status or int
            A valid return status for the C-GET operation (see PS3.4 Annex 
            C.4.3.1.4), must be one of the following Status objects or the
            corresponding integer value:
                Success status
                    QueryRetrieveGetSOPClass.Success
                        Sub-operations complete - 0x0000
                    
                Failure statuses
                    QueryRetrieveGetSOPClass.OutOfResourcesNumberOfMatches
                        Refused: Out of Resources - Unable to calculate number
                        of matches - 0xA701
                    QueryRetrieveGetSOPClass.OutOfResourcesUnableToPerform
                        Refused: Out of Resources - Unable to perform 
                        sub-operations - 0xA702
                    QueryRetrieveGetSOPClass.IdentifierDoesNotMatchSOPClass
                        Identifier does not match SOP Class - 0xA900
                    QueryRetrieveGetSOPClass.UnableToProcess
                        Unable to process - 0xCxxx
                
                Cancel status
                    QueryRetrieveGetSOPClass.Cancel
                        Sub-operations terminated due to Cancel indication 
                        - 0xFE00
                
                Warning statuses
                    QueryRetrieveGetSOPClass.Warning
                        Sub-operations complete - one or more failures or 
                        warnings - 0xB000
                        
                Pending status
                    QueryRetrieveGetSOPClass.Pending
                        Sub-operations are continuing - 0xFF00
        """
        raise NotImplementedError("User must implement the AE.on_c_get "
                    "function prior to calling AE.start()")
    
    def on_c_get_cancel(self):
        raise NotImplementedError("User must implement the "
                    "AE.on_c_get_cancel function prior to calling AE.start()")

    def on_c_move(self, dataset):
        """
        Function callback for when a dataset is received following a C-STORE.
        Must be defined by the user prior to calling AE.start() and must return
        a valid status. In addition,the AE.on_c_move_cancel() callback must 
        also be defined

        Parameters
        ----------
        dataset : pydicom.dataset.Dataset
            The DICOM dataset sent via the C-MOVE

        Returns
        -------
        status : pynetdicom.SOPclass.Status or int
            A valid return status for the C-MOVE operation (see PS3.4 Annex 
            C.4.2.1.5), must be one of the following Status objects or the
            corresponding integer value:
                Success status
                    sop_class.Success
                        Sub-operations complete - no failures - 0x0000

                Failure statuses
                    sop_class.OutOfResourcesNumberOfMatches
                        Refused: Out of Resources - Unable to calculate number
                        of matches - 0xA701
                    sop_class.OutOfResourcesUnableToPerform
                        Refused: Out of Resources - Unable to perform 
                        sub-operations - 0xA702
                    sop_class.MoveDestinationUnknown
                        Refused: Move destination unknown - 0xA801
                    sop_class.IdentifierDoesNotMatchSOPClass
                        Identifier does not match SOP Class - 0xA900
                    sop_class.UnableToProcess
                        Unable to process - 0xCxxx

                Cancel status
                    sop_class.Cancel
                        Sub-operations terminated due to Cancel indication 
                        - 0xFE00

                Warning statuses
                    sop_class.Warning
                        Sub-operations complete - one or more failures or 
                        warnings - 0xB000

                Pending status
                    sop_class.Pending
                        Sub-operations are continuing - 0xFF00
        """
        raise NotImplementedError("User must implement the AE.on_c_move "
                    "function prior to calling AE.start()")

    def on_c_move_cancel(self):
        raise NotImplementedError("User must implement the "
                    "AE.on_c_move_cancel function prior to calling AE.start()")


    # High-level DIMSE-N callbacks - user should implement these as required
    def on_n_event_report(self):
        raise NotImplementedError("User must implement the "
                    "AE.on_n_event_report function prior to calling AE.start()")

    def on_n_get(self):
        raise NotImplementedError("User must implement the "
                    "AE.on_n_get function prior to calling AE.start()")

    def on_n_set(self):
        raise NotImplementedError("User must implement the "
                    "AE.on_n_set function prior to calling AE.start()")

    def on_n_action(self):
        raise NotImplementedError("User must implement the "
                    "AE.on_n_action function prior to calling AE.start()")

    def on_n_create(self):
        raise NotImplementedError("User must implement the "
                    "AE.on_n_create function prior to calling AE.start()")

    def on_n_delete(self):
        raise NotImplementedError("User must implement the "
                    "AE.on_n_delete function prior to calling AE.start()")


    # Communication related callbacks
    def on_receive_connection(self):
        raise NotImplementedError()
    
    def on_make_connection(self):
        raise NotImplementedError()


    # High-level Association related callbacks
    def on_association_requested(self, primitive):
        pass

    def on_association_accepted(self, primitive):
        """
        Placeholder for a function callback. Function will be called 
        when an association attempt is accepted by either the local or peer AE
        
        Parameters
        ----------
        primitive - pynetdicom
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

    def on_association_aborted(self, primitive=None):
        # FIXME: Need to standardise callback parameters for A-ABORT
        pass
