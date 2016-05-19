
"""
Implementation of Dicom Standard, PS 3.8, section 9.3
Dicom Upper Layer Protocol for TCP/IP
Data Unit Structure


Module implementing the Data Unit Structures
There are seven different PDUs, each of them correspong to distinct class.
    A_ASSOCIATE_RQ_PDU
    A_ASSOCIATE_AC_PDU
    A_ASSOCIATE_RJ_PDU
    P_DATA_TF_PDU
    A_RELEASE_RQ_PDU
    A_RELEASE_RP_PDU
    A_ABORT_PDU


    All PDU classes implement the following methods:

      FromParams(DULServiceParameterObject):  Builds a PDU from a
                                              DULServiceParameter object.
                                              Used when receiving primitives
                                              from the DULServiceUser.
      ToParams()                           :  Convert the PDU into a
                                              DULServiceParameter object.
                                              Used for sending primitives to
                                              the DULServiceUser.
      Encode()                     :  Returns the encoded PDU as a string,
                                      ready to be sent over the net.
      Decode(string)               :  Construct PDU from "string".
                                      Used for reading PDU's from the net.

                        FromParams                 Encode
  |------------ -------| ------->  |------------| -------> |------------|
  | Service parameters |           |     PDU    |          |    TCP     |
  |       object       |           |   object   |          |   socket   |
  |____________________| <-------  |____________| <------- |____________|
                         ToParams                  Decode



In addition to PDUs, several items and sub-items classes are implemented.
These classes are:

        ApplicationContextItem
        PresentationContextItemRQ
        AbstractSyntaxSubItem
        TransferSyntaxSubItem
        UserInformationItem
        PresentationContextItemAC
        PresentationDataValueItem
"""

from io import BytesIO
import logging
from struct import *

from pydicom.uid import UID

from pynetdicom.DULparameters import *
from pynetdicom.utils import wrap_list, PresentationContext, validate_ae_title

logger = logging.getLogger('pynetdicom.pdu')


class PDU(object):
    """ Base class for PDUs """
    def __init__(self):
        # The singleton PDU parameters are stored in this list
        #   along with their struct.pack formats as a tuple
        #   ie. [(value1, format1), (value2, format2), ...]
        self.parameters = []
        # Any non-singleton PDU parameters (ie those with required sub items,
        #   such as A-ASSOCIATE-RQ's Variable Items or P-DATA-TF's 
        #   Presentation Data Value Items are listed here
        self.additional_items = []
        
    def __eq__(self, other):
        """Equality of two PDUs"""
        for ii in self.__dict__:
            if ii != 'parameters':
                if not (self.__dict__[ii] == other.__dict__[ii]):
                    print(type(self), ii)
                    print(self.__dict__[ii])
                    print(other.__dict__[ii])
                    return False

        return True
    
    def encode(self):
        """
        Encode the DUL
        
        Returns
        -------
        bytes
            The encoded PDU
        """
        no_formats = len(self.formats)
        
        #print()
        #print(type(self))
        #print(self.formats)
        #print(self.parameters[:no_formats])
        
        # If a parameter is already a bytestring then determine its length
        #   and update the format
        for (ii, ff) in enumerate(self.formats):
            if ff == 's':
                if isinstance(self.parameters[ii], UID):
                    self.parameters[ii] = bytes(self.parameters[ii].title(), 'utf-8')
                
                self.formats[ii] = '%ds' %len(self.parameters[ii])
                # Make sure the parameter is a bytes
                
        
        # Encode using Big Endian as per PS3.8 9.3.1 - PDU headers are Big
        #   Endian byte ordering while the encoding of PDV message fragments
        #   is defined by the negotiated Transfer Syntax
        pack_format = '> ' + ' '.join(self.formats)
        
        #print(pack_format)
        
        bytestream  = bytes()
        bytestream += pack(pack_format, *self.parameters[:no_formats])
        
        #print(bytestream)
        
        # When we have more parameters then format we assume that the extra
        #   parameters is a list of objects needing their own encoding
        for ii in self.parameters[no_formats:]:
            if isinstance(ii, list):
                for item in ii:
                    bytestream += item.encode()
            else:
                bytestream += ii.encode()
        
        return bytestream
            
    def decode(self, encoded_data):
        """
        Decode the binary encoded PDU and sets the PDU class' values using the
        decoded data
        
        Parameters
        ----------
        encoded_data - ?
            The binary encoded PDU
        """
        s = BytesIO(encoded_data)
        
        # We go through the PDU's parameters list and use the associated
        #   formats to decode the data
        for (value, fmt) in self.parameters:
            # Some PDUs have a parameter with unknown length
            #   ApplicationContextItem, AbstractSyntaxSubItem,
            #   PresentationDataValueItem, GenericUserDataSubItem*
            #   TransferSyntaxSubItem
            
            byte_size = struct.calcsize(fmt)
            value = struct.unpack(fmt, s.read(byte_size))
            
        # A_ASSOCIATE_RQ, A_ASSOCIATE_AC, P_DATA_TF and others may have
        # additional sub items requiring decoding
        while True:
            item = next_item(s)

            if item is None:
                # Then the stream is empty so we break out of the loop
                break
            
            item.decode(s)
            self.additional_items.append(item)
            
        # After decoding, check that we have only added allowed items 
        self.validate_additional_items()

    def _next_item_type(self, s):
        """
        Peek at the stream `s` and see what PDU sub-item type
        it is by checking the value of the first byte, then reversing back to 
        the start of the stream. 
        
        Parameters
        ----------
        s : io.BytesIO
            The stream to peek
            
        Returns
        -------
        item_type : int
            The first byte of the stream
        None
            If the stream is empty
        """
        first_byte = s.read(1)
        
        # If the stream is empty
        if first_byte == b'':
            return None

        # Reverse our peek
        s.seek(-1, 1)
        
        first_byte = unpack('B', first_byte)[0]
        
        return first_byte
    
    def _next_item(self, s):
        """ 
        Peek at the stream `s` and see what the next item type
        it is. Each valid PDU/item/subitem has an PDU-type/Item-type as the 
        first byte, so we look at the first byte in the stream, then 
        reverse back to the start of the stream
        
        Parameters
        ----------
        s : io.BytesIO
            The stream to peek
            
        Returns
        -------
        PDU : pynetdicom.PDU.PDU subclass
            A PDU subclass instance corresponding to the next item in the stream
        None
            If the stream is empty
        
        Raises
        ------
        ValueError
            If the item type is not a known value
        """

        item_type = self._next_item_type(s)
        
        if item_type is None:
            return None
        
        item_types = {0x01 : A_ASSOCIATE_RQ_PDU,
                      0x02 : A_ASSOCIATE_AC_PDU,
                      0x03 : A_ASSOCIATE_RJ_PDU,
                      0x04 : P_DATA_TF_PDU,
                      0x05 : A_RELEASE_RQ_PDU,
                      0x06 : A_RELEASE_RP_PDU,
                      0x07 : A_ABORT_PDU,
                      0x10 : ApplicationContextItem,
                      0x20 : PresentationContextItemRQ,
                      0x21 : PresentationContextItemAC,
                      0x30 : AbstractSyntaxSubItem,
                      0x40 : TransferSyntaxSubItem,
                      0x50 : UserInformationItem,
                      0x51 : MaximumLengthSubItem,
                      0x52 : ImplementationClassUIDSubItem,
                      0x53 : AsynchronousOperationsWindowSubItem,
                      0x54 : SCP_SCU_RoleSelectionSubItem,
                      0x55 : ImplementationVersionNameSubItem,
                      0x56 : SOPClassExtendedNegotiationSubItem}
        
        if item_type not in item_types.keys():
            raise ValueError("During PDU decoding we received an invalid "
                        "item type: %s" %item_type)
        
        return item_types[item_type]()

    @property
    def length(self):
        return len(self.Encode())


class A_ASSOCIATE_RQ_PDU(PDU):
    """
    Represents the A-ASSOCIATE-RQ PDU that, when encoded, is received from/sent 
    to the peer AE.

    The A-ASSOCIATE-RQ PDU is sent at the start of association negotiation when
    either the local or the peer AE wants to to request an association.

    An A-ASSOCIATE-RQ requires the following parameters (see PS3.8 Section 
        9.3.2):
        * PDU type (1, fixed value, 0x01)
        * PDU length (1)
        * Protocol version (1, fixed value, 0x01)
        * Called AE title (1)
        * Calling AE title (1)
        * Variable items (1)
          * Application Context Item (1)
            * Item type (1, fixed value, 0x10)
            * Item length (1) 
            * Application Context Name (1, fixed in an application)
          * Presentation Context Item(s) (1 or more)
            * Item type (1, fixed value, 0x21)
            * Item length (1)
            * Context ID (1)
            * Abstract/Transfer Syntax Sub-items (1)
              * Abstract Syntax Sub-item (1)
                * Item type (1, fixed, 0x30)
                * Item length (1)
                * Abstract syntax name (1)
              * Transfer Syntax Sub-items (1 or more)
                * Item type (1, fixed, 0x40)
                * Item length (1)
                * Transfer syntax name(s) (1 or more)
          * User Information Item (1)
            * Item type (1, fixed, 0x50)
            * Item length (1)
            * User data Sub-items (2 or more)
                * Maximum Length Received Sub-item (1)
                * Implementation Class UID Sub-item (1)
                * Optional User Data Sub-items (0 or more)
    
    See PS3.8 Section 9.3.2 for the structure of the PDU, especially Table 9-11.
    
    Attributes
    ----------
    application_context_name : pydicom.uid.UID
        The Association Requestor's Application Context Name as a UID. See 
        PS3.8 9.3.2, 7.1.1.2
    called_ae_title : bytes
        The destination AE title as a 16-byte bytestring.
    calling_ae_title : bytes
        The source AE title as a 16-byte bytestring.
    length : int
        The length of the encoded PDU in bytes
    presentation_context : list of pynetdicom.PDU.PresentationContextItemRQ
        The A-ASSOCIATE-RQ's Presentation Context items
    user_information : pynetdicom.PDU.UserInformationItem
        The A-ASSOCIATE-RQ's User Information item. See PS3.8 9.3.2, 7.1.1.6
    """
    def __init__(self):
        # These either have a fixed value or are set programatically
        self.pdu_type = 0x01
        self.pdu_length = None
        self.protocol_version = 0x01
        self.called_ae_title = "Default"
        self.calling_ae_title = "Default"
        
        # `variable_items` is a list containing the following:
        #   1 ApplicationContextItem
        #   1 or more PresentationContextItemRQ
        #   1 UserInformationItem
        # The order of the items in the list may not be as given above
        self.variable_items = []
        
        self.formats = ['B', 'B', 'I', 'H', 'H', '16s', '16s', 
                        'I', 'I', 'I', 'I', 'I', 'I', 'I', 'I']
        self.parameters = [self.pdu_type, 
                           0x00, # Reserved
                           self.pdu_length, 
                           self.protocol_version,
                           0x00, # Reserved
                           self.called_ae_title,
                           self.calling_ae_title,
                           0x00, 0x00, 0x00, 0x00, # Reserved
                           0x00, 0x00, 0x00, 0x00, # Reserved
                           self.variable_items]
                           
    def FromParams(self, primitive):
        """
        Set up the PDU using the parameter values from the A-ASSOCIATE 
        `primitive`
        
        Parameters
        ----------
        primitive : pynetdicom.DULparameters.A_ASSOCIATE_ServiceParameters
            The parameters to use for setting up the PDU
        """
        self.calling_ae_title = primitive.CallingAETitle
        self.called_ae_title = primitive.CalledAETitle
        
        # Make Application Context
        application_context = ApplicationContextItem()
        application_context.FromParams(primitive.ApplicationContextName)
        self.variable_items.append(application_context)

        # Make Presentation Context(s)
        for contexts in primitive.PresentationContextDefinitionList:
            presentation_context = PresentationContextItemRQ()
            presentation_context.FromParams(contexts)
            self.variable_items.append(presentation_context)

        # Make User Information
        user_information = UserInformationItem()
        user_information.FromParams(primitive.UserInformationItem)
        self.variable_items.append(user_information)

        # Set the pdu_length attribute
        self._update_pdu_length()

    def ToParams(self):
        """ 
        Convert the current A-ASSOCIATE-RQ PDU to a primitive
        
        Returns
        -------
        pynetdicom.DULparameters.A_ASSOCIATE_ServiceParameters
            The primitive to convert the PDU to
        """
        primitive = A_ASSOCIATE_ServiceParameters()

        primitive.CallingAETitle = self.calling_ae_title
        primitive.CalledAETitle  = self.called_ae_title
        primitive.ApplicationContextName = self.application_context_name
        
        for ii in self.variable_items:
            # Add presentation contexts
            if isinstance(ii, PresentationContextItemRQ):
                primitive.PresentationContextDefinitionList.append(ii.ToParams())
            
            # Add user information
            elif isinstance(ii, UserInformationItem):
                primitive.UserInformationItem = ii.ToParams()
        
        return primitive

    def Encode(self):
        """
        Encode the PDU's parameter values into a bytes string
        
        Returns
        -------
        bytestring : bytes
            The encoded PDU that will be sent to the peer AE
        """
        logger.debug('Constructing Associate RQ PDU')
        
        # Encode the PDU parameters up to the Variable Items
        #   See PS3.8 Table 9-11 
        formats = '> B B I H H 16s 16s 8I'
        parameters = [self.pdu_type, 
                      0x00, # Reserved
                      self.pdu_length, 
                      self.protocol_version,
                      0x00, # Reserved
                      self.called_ae_title,
                      self.calling_ae_title,
                      0x00, 0x00, 0x00, 0x00, # Reserved
                      0x00, 0x00, 0x00, 0x00] # Reserved
                      
        bytestring  = bytes()
        bytestring += pack(formats, *parameters)
        
        # Encode the Variable Items
        for ii in self.variable_items:
            bytestring += ii.Encode()
        
        return bytestring

    def Decode(self, bytestring):
        """
        Decode the parameter values for the PDU from the bytes string sent
        by the peer AE
        
        Parameters
        ----------
        bytestring : bytes
            The bytes string received from the peer
        """
        logger.debug('PDU Type: Associate Request, PDU Length: %s + 6 bytes '
                        'PDU header' %(len(bytestring) - 6))
        
        for line in wrap_list(bytestring, max_size=512):
            logger.debug('  ' + line)
        
        logger.debug('Parsing an A-ASSOCIATE PDU')
        
        # Convert `bytestring` to a bytes stream to make things easier 
        #   during decoding of the Variable Items section
        s = BytesIO(bytestring)
        
        # Decode the A-ASSOCIATE-RQ PDU up to the Variable Items section
        (self.pdu_type, 
         _, 
         self.pdu_length,
         self.protocol_version, 
         _, 
         self.called_ae_title,
         self.calling_ae_title,
         _) = unpack('> B B I H H 16s 16s 32s', s.read(74))

        # Decode the Variable Items section of the PDU
        item = self._next_item(s)
        while item is not None:
            item.Decode(s)
            self.variable_items.append(item)
            
            item = self._next_item(s)
            
        self._update_parameters()

    def _update_parameters(self):
        self.parameters = [self.pdu_type, 
                           0x00, # Reserved
                           self.pdu_length, 
                           self.protocol_version,
                           0x00, # Reserved
                           self.called_ae_title,
                           self.calling_ae_title,
                           0x00, 0x00, 0x00, 0x00, # Reserved
                           0x00, 0x00, 0x00, 0x00, # Reserved
                           self.variable_items]

    def _update_pdu_length(self):
        """ Determines the value of the PDU Length parameter """
        # Determine the total length of the PDU, this is the length from the
        #   first byte of the Protocol-version field (byte 7) to the end
        #   of the Variable items field (first byte is 75, unknown length)
        length = 68
        for ii in self.variable_items:
            length += ii.get_length()
        
        self.pdu_length = length

    def get_length(self):
        """ Returns the total length of the PDU in bytes as an int """
        self._update_pdu_length()

        return 6 + self.pdu_length

    @property
    def called_ae_title(self):
        return self._called_aet

    @called_ae_title.setter
    def called_ae_title(self, s):
        """
        Set the Called-AE-title parameter to a 16-byte length byte string
        
        Parameters
        ----------
        s : str or bytes
            The called AE title value you wish to set
        """
        if isinstance(s, str):
            s = bytes(s, 'utf-8')

        self._called_aet = validate_ae_title(s)

    @property
    def calling_ae_title(self):
        return self._calling_aet

    @calling_ae_title.setter
    def calling_ae_title(self, s):
        """
        Set the Calling-AE-title parameter to a 16-byte length byte string
        
        Parameters
        ----------
        s : str or bytes
            The calling AE title value you wish to set
        """
        if isinstance(s, str):
            s = bytes(s, 'utf-8')

        self._calling_aet = validate_ae_title(s)

    @property
    def application_context_name(self):
        for ii in self.variable_items:
            if isinstance(ii, ApplicationContextItem):
                return ii.application_context_name
    
    @application_context_name.setter
    def application_context_name(self, value):
        """Set the Association request's Application Context Name
        
        Parameters
        ----------
        value : pydicom.uid.UID, str or bytes
            The value of the Application Context Name's UID
        """
        for ii in self.variable_items:
            if isinstance(ii, ApplicationContextItem):
                ii.application_context_name = value

    @property
    def presentation_context(self):
        """
        See PS3.8 9.3.2, 7.1.1.13
        
        A list of PresentationContextItemRQ. If extended negotiation Role
        Selection is used then the SCP/SCU roles will also be set.
        
        See the PresentationContextItemRQ and documentation for more information
        
        Returns
        -------
        list of pynetdicom.PDU.PresentationContextItemRQ
            The Requestor AE's Presentation Context objects
        """
        contexts = []
        for ii in self.variable_items:
            if isinstance(ii, PresentationContextItemRQ):
                # We determine if there are any SCP/SCU Role Negotiations
                #   for each Transfer Syntax in each Presentation Context
                #   and if so we set the SCP and SCU attributes.
                if self.user_information.role_selection is not None:
                    # Iterate through the role negotiations looking for a 
                    #   SOP Class match to the Abstract Syntaxes
                    for role in self.user_information.role_selection:
                        for sop_class in ii.AbstractSyntax:
                            if role.SOPClass == sop_class:
                                ii.SCP = role.SCP
                                ii.SCU = role.SCU
                contexts.append(ii)
        return contexts

    @property
    def user_information(self):
        for ii in self.variable_items:
            if isinstance(ii, UserInformationItem):
                return ii

    def __str__(self):
        s = 'A-ASSOCIATE-RQ PDU\n'
        s += '  PDU type: 0x%02x\n' %self.pdu_type
        s += '  PDU length: %d\n' %self.pdu_length
        s += '  Protocol version: %d\n' %self.protocol_version
        s += '  Called AET:  %s\n' %self.called_ae_title
        s += '  Calling AET: %s\n' %self.calling_ae_title
        s += '  Variable items:\n'
        s += '    Application context name: %s\n' %self.application_context_name
        s += '    Presentation context(s):\n'
        for ii in self.presentation_context:
            s += '      %s' %ii
        
        s += '    User information:\n'
        for ii in self.user_information.UserData:
            s += '      %s' %ii
        
        return s


class A_ASSOCIATE_AC_PDU(PDU):
    """
    Represents the A-ASSOCIATE-AC PDU that, when encoded, is received from/sent 
    to the peer AE

    The A-ASSOCIATE-AC PDU is sent when the association request is accepted
    by either the local or the peer AE

    An A-ASSOCIATE-AC requires the following parameters (see PS3.8 Section 
        9.3.2):
        * PDU type (1, fixed value, 0x02)
        * PDU length (1)
        * Protocol version (1, fixed value, 0x01)
        * Variable items (1)
          * Application Context Item (1)
            * Item type (1, fixed value, 0x10)
            * Item length (1) 
            * Application Context Name (1, fixed in an application)
          * Presentation Context Item(s) (1 or more)
            * Item type (1, fixed value, 0x21)
            * Item length (1)
            * Context ID (1)
            * Transfer Syntax Sub-items (1)
              * Item type (1, fixed, 0x40)
              * Item length (1)
              * Transfer syntax name(s) (1)
          * User Information Item (1)
            * Item type (1, fixed, 0x50)
            * Item length (1)
            * User data Sub-items (2 or more)
                * Maximum Length Received Sub-item (1)
                * Implementation Class UID Sub-item (1)
                * Optional User Data Sub-items (0 or more)
    
    See PS3.8 Section 9.3.3 for the structure of the PDU, especially Table 9-17.
    
    Attributes
    ----------
    application_context_name : pydicom.uid.UID
        The Association Requestor's Application Context Name as a UID. See 
        PS3.8 9.3.2, 7.1.1.2
    called_ae_title : bytes
        The destination AE title as a 16-byte bytestring. The value is not
        guaranteed to be the actual title and shall not be tested.
    calling_ae_title : bytes
        The source AE title as a 16-byte bytestring. The value is not
        guaranteed to be the actual title and shall not be tested.
    length : int
        The length of the encoded PDU in bytes
    presentation_context : list of pynetdicom.PDU.PresentationContextItemAC
        The A-ASSOCIATE-AC's Presentation Context items
    user_information : pynetdicom.PDU.UserInformationItem
        The A-ASSOCIATE-AC's User Information item. See PS3.8 9.3.2, 7.1.1.6
    """
    def __init__(self):
        # These either have a fixed value or are set programatically
        self.pdu_type = 0x02
        self.pdu_length = None
        self.protocol_version = 0x01
        
        # Shall be set to called AE title value, but no guarantee
        self.reserved_aet = None 
        # Shall be set to calling AE title value, but no guarantee
        self.reserved_aec = None

        # variable_items is a list containing the following:
        #   1 ApplicationContextItem
        #   1 or more PresentationContextItemAC
        #   1 UserInformationItem
        # The order of the items in the list may not be as given above
        self.variable_items = []
        
        self.formats = ['B', 'B', 'I', 'H', 'H', '16s', '16s', 
                        'I', 'I', 'I', 'I', 'I', 'I', 'I', 'I']
        self.parameters = [self.pdu_type, 
                           0x00, # Reserved
                           self.pdu_length, 
                           self.protocol_version,
                           0x00, # Reserved
                           self.reserved_aet,
                           self.reserved_aec,
                           0x00, 0x00, 0x00, 0x00, # Reserved
                           0x00, 0x00, 0x00, 0x00, # Reserved
                           self.variable_items]
    
    def FromParams(self, primitive):
        """
        Set up the PDU using the parameter values from the A-ASSOCIATE 
        `primitive`
        
        Parameters
        ----------
        primitive : pynetdicom.DULparameters.A_ASSOCIATE_ServiceParameters
            The parameters to use for setting up the PDU
        """
        self.reserved_aet = primitive.CalledAETitle
        self.reserved_aec = primitive.CallingAETitle
        
        # Make application context
        application_context = ApplicationContextItem()
        application_context.FromParams(primitive.ApplicationContextName)
        self.variable_items.append(application_context)
        
        # Make presentation contexts
        for ii in primitive.PresentationContextDefinitionResultList:
            presentation_context = PresentationContextItemAC()
            presentation_context.FromParams(ii)
            self.variable_items.append(presentation_context)
        
        # Make user information
        user_information = UserInformationItem()
        user_information.FromParams(primitive.UserInformationItem)
        self.variable_items.append(user_information)
        
        # Compute PDU length parameter value
        self._update_pdu_length()

    def ToParams(self):
        """ 
        Convert the current A-ASSOCIATE-AC PDU to a primitive
        
        Returns
        -------
        pynetdicom.DULparameters.A_ASSOCIATE_ServiceParameters
            The primitive to convert the PDU to
        """
        primitive = A_ASSOCIATE_ServiceParameters()
        
        # The two reserved parameters at byte offsets 11 and 27 shall be set
        #    to called and calling AET byte the value shall not be
        #   tested when received (PS3.8 Table 9-17)
        primitive.CalledAETitle = self.reserved_aet
        primitive.CallingAETitle = self.reserved_aec
        
        for ii in self.variable_items:
            # Add application context
            if isinstance(ii, ApplicationContextItem):
                primitive.ApplicationContextName = ii.application_context_name
            
            # Add presentation contexts
            elif isinstance(ii, PresentationContextItemAC):
                primitive.PresentationContextDefinitionResultList.append(ii.ToParams())
            
            # Add user information
            elif isinstance(ii, UserInformationItem):
                primitive.UserInformationItem = ii.ToParams()
        
        # 0x00 = Accepted
        primitive.Result = 0x00
        
        return primitive

    def Encode(self):
        """
        Encode the PDU's parameter values into a bytes string
        
        Returns
        -------
        bytestring : bytes
            The encoded PDU that will be sent to the peer AE
        """
        logger.debug('Constructing Associate AC PDU')
        
        formats = '> B B I H H 16s 16s 8I'
        parameters = [self.pdu_type, 
                      0x00, # Reserved
                      self.pdu_length, 
                      self.protocol_version,
                      0x00, # Reserved
                      self.reserved_aet,
                      self.reserved_aec,
                      0x00, 0x00, 0x00, 0x00, # Reserved
                      0x00, 0x00, 0x00, 0x00] # Reserved
                      
        bytestring  = bytes()
        bytestring += pack(formats, *parameters)
        
        for ii in self.variable_items:
            bytestring += ii.Encode()
        
        return bytestring

    def Decode(self, bytestring):
        """
        Decode the parameter values for the PDU from the bytes string sent
        by the peer AE
        
        Parameters
        ----------
        bytestring : bytes
            The bytes string received from the peer
        """
        logger.debug('PDU Type: Associate Accept, PDU Length: %s + 6 bytes '
                        'PDU header' %(len(bytestring) - 6))
        
        for line in wrap_list(bytestring, max_size=512):
            logger.debug('  ' + line)
        
        logger.debug('Parsing an A-ASSOCIATE PDU')
        
        # Convert `bytestring` to a bytes stream to make things easier 
        #   during decoding of the Variable Items section
        s = BytesIO(bytestring)
        
        # Decode the A-ASSOCIATE-AC PDU up to the Variable Items section
        (self.pdu_type, 
         _, 
         self.pdu_length,
         self.protocol_version, 
         _, 
         self.reserved_aet,
         self.reserved_aec,
         _) = unpack('> B B I H H 16s 16s 32s', s.read(74))

        # Decode the Variable Items section of the PDU
        item = self._next_item(s)
        while item is not None:
            item.Decode(s)
            self.variable_items.append(item)
            
            item = self._next_item(s)
            
        self._update_parameters()
        
    def _update_parameters(self):
        self.parameters = [self.pdu_type, 
                           0x00, # Reserved
                           self.pdu_length, 
                           self.protocol_version,
                           0x00, # Reserved
                           self.reserved_aet,
                           self.reserved_aec,
                           0x00, 0x00, 0x00, 0x00, # Reserved
                           0x00, 0x00, 0x00, 0x00, # Reserved
                           self.variable_items]

    def _update_pdu_length(self):
        """ Determines the value of the PDU Length parameter """
        # Determine the total length of the PDU, this is the length from the
        #   first byte of the Protocol-version field (byte 7) to the end
        #   of the Variable items field (first byte is 75, unknown length)
        length = 68
        for ii in self.variable_items:
            length += ii.get_length()
        
        self.pdu_length = length

    def get_length(self):
        self._update_pdu_length()
        
        return 6 + self.pdu_length

    @property
    def application_context_name(self):
        """
        See PS3.8 9.3.2, 7.1.1.2
        
        Returns
        -------
        pydicom.uid.UID
            The Acceptor AE's Application Context Name
        """
        for ii in self.variable_items:
            if isinstance(ii, ApplicationContextItem):
                return ii.application_context_name
        
    @property
    def presentation_context(self):
        """
        See PS3.8 9.3.2, 7.1.1.13
        
        Returns
        -------
        list of pynetdicom.PDU.PresentationContextItemAC
            The Acceptor AE's Presentation Context objects. Each of the 
            Presentation Context items instances in the list has been extended
            with two variables for tracking if SCP/SCU role negotiation has been 
            accepted:
                SCP: Defaults to None if not used, 0 or 1 if used
                SCU: Defaults to None if not used, 0 or 1 if used
        """
        contexts = []
        for ii in self.variable_items:
            if isinstance(ii, PresentationContextItemAC):
                # We determine if there are any SCP/SCU Role Negotiations
                #   for each Transfer Syntax in each Presentation Context
                #   and if so we set the SCP and SCU attributes
                if self.user_information.role_selection is not None:
                    # Iterate through the role negotiations looking for a 
                    #   SOP Class match to the Abstract Syntaxes
                    for role in self.user_information.role_selection:
                        pass
                        # FIXME: Pretty sure -AC has no Abstract Syntax
                        #   need to check against standard
                        #for sop_class in ii.AbstractSyntax:
                        #    if role.SOPClass == sop_class:
                        #        ii.SCP = role.SCP
                        #        ii.SCU = role.SCU
                contexts.append(ii)
        
        return contexts
        
    @property
    def user_information(self):
        """
        See PS3.8 9.3.2, 7.1.1.6
        
        Returns
        -------
        pynetdicom.PDU.UserInformationItem
            The Acceptor AE's User Information object
        """
        for ii in self.variable_items:
            if isinstance(ii, UserInformationItem):
                return ii
        
    @property
    def called_ae_title(self):
        """
        While the standard says this value should match the A-ASSOCIATE-RQ
        value there is no guarantee and this should not be used as a check
        value
        
        Returns
        -------
        bytes
            The Requestor's AE Called AE Title
        """
        ae_title = self.reserved_aet
        if isinstance(ae_title, str):
            ae_title = bytes(self.reserved_aet, 'utf-8')
        elif isinstance(ae_title, bytes):
            pass
        
        return ae_title
    
    @property
    def calling_ae_title(self):
        """
        While the standard says this value should match the A-ASSOCIATE-RQ
        value there is no guarantee and this should not be used as a check
        value
        
        Returns
        -------
        bytes
            The Requestor's AE Calling AE Title
        """
        ae_title = self.reserved_aec
        if isinstance(ae_title, str):
            ae_title = bytes(self.reserved_aec, 'utf-8')
        elif isinstance(ae_title, bytes):
            pass
        
        return ae_title

    def __str__(self):
        s = 'A-ASSOCIATE-AC PDU\n'
        s += '  PDU type: 0x%02x\n' %self.pdu_type
        s += '  PDU length: %d\n' %self.pdu_length
        s += '  Protocol version: %d\n' %self.protocol_version
        s += '  Reserved (Called AET):  %s\n' %self.reserved_aet
        s += '  Reserved (Calling AET): %s\n' %self.reserved_aec
        s += '  Variable items:\n'
        s += '    Application context name: %s\n' %self.application_context_name
        s += '    Presentation context(s):\n'
        for ii in self.presentation_context:
            s += '      %s' %ii
        
        s += '    User information:\n'
        for ii in self.user_information.UserData:
            s += '      %s' %ii
        
        return s


class A_ASSOCIATE_RJ_PDU(PDU):
    """
    Represents the A-ASSOCIATE-RJ PDU that, when encoded, is received from/sent 
    to the peer AE.

    The A-ASSOCIATE-RJ PDU is sent during association negotiation when
    either the local or the peer AE rejects the association request.

    An A-ASSOCIATE-RJ requires the following parameters (see PS3.8 Section 
        9.3.4):
        * PDU type (1, fixed value, 0x03)
        * PDU length (1)
        * Result (1)
        * Source (1)
        * Reason/Diagnostic (1)
        
    See PS3.8 Section 9.3.4 for the structure of the PDU, especially Table 9-21.
    
    Attributes
    ----------
    length : int
        The length of the encoded PDU in bytes
    reason : int
        The raw Reason/Diagnostic parameter value
    reason_str : str
        The reason for the rejection as a string
    result : int
        The raw Result parameter value
    result_str : str
        The result of the rejection, one of ('Rejected (Permanent)', 
        'Rejected (Transient)')
    source : int
        The raw Source parameter value
    source_str : str
        The source of the rejection, one of ('DUL service-user', 
        'DUL service-provider (ACSE related)', 'DUL service-provider 
        (presentation related)')
    """
    def __init__(self):
        self.pdu_type = 0x03
        self.pdu_length = 0x04
        self.result = None
        self.source = None
        self.reason_diagnostic = None
        
        self.formats = ['B', 'B', 'I', 'B', 'B', 'B', 'B']
        self.parameters = [self.pdu_type, 
                           0x00, # Reserved
                           self.pdu_length, 
                           0x00,
                           self.result,
                           self.source,
                           self.reason_diagnostic]

    def FromParams(self, primitive):
        """
        Set up the PDU using the parameter values from the A-ASSOCIATE 
        `primitive`
        
        Parameters
        ----------
        primitive : pynetdicom.DULparameters.A_ASSOCIATE_ServiceParameters
            The parameters to use for setting up the PDU
        """
        self.result = primitive.Result
        self.source = primitive.ResultSource
        self.reason_diagnostic = primitive.Diagnostic

    def ToParams(self):
        """ 
        Convert the current A-ASSOCIATE-RQ PDU to a primitive
        
        Returns
        -------
        pynetdicom.DULparameters.A_ASSOCIATE_ServiceParameters
            The primitive to convert the PDU to
        """
        primitive = A_ASSOCIATE_ServiceParameters()
        primitive.Result = self.result
        primitive.ResultSource = self.source
        primitive.Diagnostic = self.reason_diagnostic
        
        return primitive

    def Encode(self):
        """
        Encode the PDU's parameter values into a bytes string
        
        Returns
        -------
        bytestring : bytes
            The encoded PDU that will be sent to the peer AE
        """
        logger.debug('Constructing Associate RJ PDU')
        
        formats = '> B B I B B B B'
        parameters = [self.pdu_type, 
                      0x00, # Reserved
                      self.pdu_length, 
                      0x00,
                      self.result,
                      self.source,
                      self.reason_diagnostic]
                      
        bytestring  = bytes()
        bytestring += pack(formats, *parameters)
        
        return bytestring

    def Decode(self, bytestring):
        """
        Decode the parameter values for the PDU from the bytes string sent
        by the peer AE
        
        Parameters
        ----------
        bytestring : bytes
            The bytes string received from the peer
        """
        (self.pdu_type, 
         _, 
         self.pdu_length, 
         _,
         self.result, 
         self.source, 
         self.reason_diagnostic) = unpack('> B B I B B B B', bytestring)
         
        self._update_parameters()
        
    def _update_parameters(self):
        self.parameters = [self.pdu_type, 
                           0x00, # Reserved
                           self.pdu_length, 
                           0x00,
                           self.result,
                           self.source,
                           self.reason_diagnostic]

    def get_length(self):
        """ The total length of the encoded PDU in bytes """
        return 10

    @property
    def result(self):
        return self._result

    @result.setter
    def result(self, value):
        self._result = value

    @property
    def result_str(self):
        results = {1 : 'Rejected (Permanent)',
                   2 : 'Rejected (Transient)'}

        if self.result not in results.keys():
            logger.error('Invalid value in Result parameter in A-ASSOCIATE-RJ PDU')
            raise ValueError('Invalid value in Result parameter in A-ASSOCIATE-RJ PDU')
            
        return results[self.result]
    
    @property
    def source(self):
        return self._source
    
    @source.setter
    def source(self, value):
        self._source = value
    
    @property
    def source_str(self):
        sources = {1 : 'DUL service-user',
                   2 : 'DUL service-provider (ACSE related)',
                   3 : 'DUL service-provider (presentation related)'}
                   
        if self.source not in sources.keys():
            logger.error('Invalid value in Source parameter in A-ASSOCIATE-RJ PDU')
            raise ValueError('Invalid value in Source parameter in A-ASSOCIATE-RJ PDU')
            
        return sources[self.source]
    
    @property
    def reason_diagnostic(self):
        return self._reason
    
    @reason_diagnostic.setter
    def reason_diagnostic(self, value):
        self._reason = value
        
    @property
    def reason_str(self):
        reasons = {1 : { 1 : "No reason given",
                         2 : "Application context name not supported",
                         3 : "Calling AE title not recognised",
                         4 : "Reserved",
                         5 : "Reserved",
                         6 : "Reserved",
                         7 : "Called AE title not recognised",
                         8 : "Reserved",
                         9 : "Reserved",
                        10 : "Reserved"},
                   2 : { 1 : "No reason given",
                         2 : "Protocol version not supported"},
                   3 : { 0 : "Reserved",
                         1 : "Temporary congestion",
                         2 : "Local limit exceeded",
                         3 : "Reserved",
                         4 : "Reserved",
                         5 : "Reserved",
                         6 : "Reserved",
                         7 : "Reserved"}}
        
        if self.source not in reasons.keys():
            logger.error('Invalid value in Source parameter in A-ASSOCIATE-RJ PDU')
            raise ValueError('Invalid value in Source parameter in A-ASSOCIATE-RJ PDU')
        
        source_reasons = reasons[self.source]
        
        if self.reason_diagnostic not in source_reasons.keys():
            logger.error('Invalid value in Reason parameter in A-ASSOCIATE-RJ PDU')
            raise ValueError('Invalid value in Reason parameter in A-ASSOCIATE-RJ PDU')
        
        return source_reasons[self.reason_diagnostic]
   
    def __str__(self):
        s = "A-ASSOCIATE-RJ PDU\n"
        s += " PDU type: 0x%02x\n" % self.PDUType
        s += " PDU length: %d\n" % self.PDULength
        s += " Result: %d\n" % self.Result
        s += " Source: %s\n" % str(self.Source)
        s += " Reason/Diagnostic: %s\n" % str(self.ReasonDiag)
        
        return s + "\n"


class P_DATA_TF_PDU(PDU):
    """
    Represents the P-DATA-TF PDU that, when encoded, is received from/sent 
    to the peer AE.

    The P-DATA-TF PDU contains data to be transmitted between two associated
    AEs.

    A P-DATA-TF requires the following parameters (see PS3.8 Section 
        9.3.5):
        * PDU type (1, fixed value, 0x04)
        * PDU length (1)
        * Presentation data value Item(s) (1 or more)
        
    See PS3.8 Section 9.3.5 for the structure of the PDU, especially Table 9-22.
    
    Attributes
    ----------
    length : int
        The length of the encoded PDU in bytes
    PDVs : list of pynetdicom.PDU.PresentationDataValueItem
        The presentation data value items
    """
    def __init__(self):
        self.pdu_type = 0x04
        self.pdu_length = None
        self.presentation_data_value_items = []
        
        self.formats = ['B', 'B', 'I']
        self.parameters = [self.pdu_type, 
                           0x00, # Reserved
                           self.pdu_length, 
                           self.presentation_data_value_items]

    def FromParams(self, primitive):
        """
        Set up the PDU using the parameter values from the P-DATA `primitive`
        
        Parameters
        ----------
        primitive : pynetdicom.DULparameters.P_DATA_ServiceParameters
            The parameters to use for setting up the PDU
        """
        for ii in primitive.PresentationDataValueList:
            presentation_data_value = PresentationDataValueItem()
            presentation_data_value.FromParams(ii)
            self.presentation_data_value_items.append(presentation_data_value)
        
        self._update_pdu_length()

    def ToParams(self):
        """ 
        Convert the current P-DATA-TF PDU to a primitive
        
        Returns
        -------
        pynetdicom.DULparameters.P_DATA_ServiceParameters
            The primitive to convert the PDU to
        """
        primitive = P_DATA_ServiceParameters()
        
        primitive.PresentationDataValueList = []
        for ii in self.presentation_data_value_items:
            primitive.PresentationDataValueList.append([ii.presentation_context_id,
                                                        ii.presentation_data_value])
        return primitive

    def Encode(self):
        """
        Encode the PDU's parameter values into a bytes string
        
        Returns
        -------
        bytestring : bytes
            The encoded PDU that will be sent to the peer AE
        """
        
        formats = '> B B I'
        parameters = [self.pdu_type, 
                      0x00, # Reserved
                      self.pdu_length]
                      
        bytestring  = bytes()
        bytestring += pack(formats, *parameters)
        
        for ii in self.presentation_data_value_items:
            bytestring += ii.Encode()
        
        return bytestring

    def Decode(self, bytestring):
        """
        Decode the parameter values for the PDU from the bytes string sent
        by the peer AE
        
        Parameters
        ----------
        bytestring : bytes
            The bytes string received from the peer
        """
        # Convert `bytestring` to a bytes stream to make things easier 
        #   during decoding of the Presentation Data Value Items section
        s = BytesIO(bytestring)
        
        # Decode the P-DATA-TF PDU up to the Presentation Data Value Items section
        (self.pdu_type, 
         _,
         self.pdu_length) = unpack('> B B I', s.read(6))
        
        # Decode the Presentation Data Value Items section
        length_read = 0
        while length_read != self.pdu_length:
            pdv_item = PresentationDataValueItem()
            pdv_item.Decode(s)
            
            length_read += pdv_item.get_length()
            self.presentation_data_value_items.append(pdv_item)
            
        self._update_parameters()

    def _update_parameters(self):
        self.parameters = [self.pdu_type, 
                           0x00,
                           self.pdu_length, 
                           self.presentation_data_value_items]

    def _update_pdu_length(self):
        self.pdu_length = 0
        for ii in self.presentation_data_value_items:
            self.pdu_length += ii.get_length()

    def get_length(self):
        self._update_pdu_length()
        return 6 + self.pdu_length

    @property
    def PDVs(self):
        return self.presentation_data_value_items

    def __str__(self):
        s  = "P-DATA-TF PDU\n"
        s += " PDU type: 0x%02x\n" % self.pdu_type
        s += " PDU length: %d\n" % self.pdu_length
        
        for ii in self.presentation_data_value_items:
            s += '%s' %ii
        
        return s


class A_RELEASE_RQ_PDU(PDU):
    """
    Represents the A-RELEASE-RQ PDU that, when encoded, is received from/sent 
    to the peer AE.

    The A-RELEASE-RQ PDU requests that the association be released

    A A-RELEASE-RQ requires the following parameters (see PS3.8 Section 
        9.3.6):
        * PDU type (1, fixed value, 0x05)
        * PDU length (1)
        
    See PS3.8 Section 9.3.6 for the structure of the PDU, especially Table 9-24.
    
    Attributes
    ----------
    length : int
        The length of the encoded PDU in bytes
    """
    def __init__(self):
        self.pdu_type = 0x05
        self.pdu_length = 0x04
        
        self.formats = ['B', 'B', 'I', 'I']
        self.parameters = [self.pdu_type, 
                      0x00, # Reserved
                      self.pdu_length,
                      0x0000] # Reserved
        
    def FromParams(self, primitive):
        """
        Set up the PDU using the parameter values from the A-RELEASE `primitive`
        
        Parameters
        ----------
        primitive : pynetdicom.DULparameters.A_RELEASE_ServiceParameters
            The parameters to use for setting up the PDU
        """
        pass

    def ToParams(self):
        """ 
        Convert the current A-RELEASE-RQ PDU to a primitive
        
        Returns
        -------
        pynetdicom.DULparameters.A_RELEASE_ServiceParameters
            The primitive to convert the PDU to
        """
        primitive = A_RELEASE_ServiceParameters()

        return primitive
        
    def Encode(self):
        """
        Encode the PDU's parameter values into a bytes string
        
        Returns
        -------
        bytestring : bytes
            The encoded PDU that will be sent to the peer AE
        """
        formats = '> B B I I'
        parameters = [self.pdu_type, 
                      0x00, # Reserved
                      self.pdu_length,
                      0x0000] # Reserved
                      
        bytestring  = bytes()
        bytestring += pack(formats, *parameters)
        
        return bytestring

    def Decode(self, bytestring):
        """
        Decode the parameter values for the PDU from the bytes string sent
        by the peer AE
        
        Parameters
        ----------
        bytestring : bytes
            The bytes string received from the peer
        """
        # Decode the A-RELEASE-RQ PDU
        (self.pdu_type, 
         _,
         self.pdu_length, 
         _) = unpack('> B B I I', bytestring)
         
        self._update_parameters()
        
    def _update_parameters(self):
        self.parameters = [self.pdu_type, 
                      0x00, # Reserved
                      self.pdu_length,
                      0x0000] # Reserved

    def get_length(self):
        return 10

    def __str__(self):
        s = "A-RELEASE-RQ PDU\n"
        s += " PDU type: 0x%02x\n" % self.pdu_type
        s += " PDU length: %d\n" % self.pdu_length
        
        return s


class A_RELEASE_RP_PDU(PDU):
    """
    Represents the A-RELEASE-RP PDU that, when encoded, is received from/sent 
    to the peer AE.

    The A-RELEASE-RP PDU confirms that the association will be released

    A A-RELEASE-RP requires the following parameters (see PS3.8 Section 
        9.3.7):
        * PDU type (1, fixed value, 0x06)
        * PDU length (1)
        
    See PS3.8 Section 9.3.7 for the structure of the PDU, especially Table 9-25.
    
    Attributes
    ----------
    length : int
        The length of the encoded PDU in bytes
    """
    def __init__(self):
        self.pdu_type = 0x06
        self.pdu_length = 0x04
        
        self.formats = ['B', 'B', 'I', 'I']
        self.parameters = [self.pdu_type, 
                      0x00, # Reserved
                      self.pdu_length,
                      0x0000] # Reserved

    def FromParams(self, primitive):
        """
        Set up the PDU using the parameter values from the A-RELEASE `primitive`
        
        Parameters
        ----------
        primitive : pynetdicom.DULparameters.A_RELEASE_ServiceParameters
            The parameters to use for setting up the PDU
        """
        pass

    def ToParams(self):
        """ 
        Convert the current A-RELEASE-RP PDU to a primitive
        
        Returns
        -------
        pynetdicom.DULparameters.A_RELEASE_ServiceParameters
            The primitive to convert the PDU to
        """
        primitive = A_RELEASE_ServiceParameters()
        primitive.Result = 'affirmative'

        return primitive
        
    def Encode(self):
        """
        Encode the PDU's parameter values into a bytes string
        
        Returns
        -------
        bytestring : bytes
            The encoded PDU that will be sent to the peer AE
        """
        
        formats = '> B B I I'
        parameters = [self.pdu_type, 
                      0x00, # Reserved
                      self.pdu_length,
                      0x0000] # Reserved
                      
        bytestring  = bytes()
        bytestring += pack(formats, *parameters)
        
        return bytestring

    def Decode(self, bytestring):
        """
        Decode the parameter values for the PDU from the bytes string sent
        by the peer AE
        
        Parameters
        ----------
        bytestring : bytes
            The bytes string received from the peer
        """
        # Decode the A-RELEASE-RP PDU
        (self.pdu_type, 
         _,
         self.pdu_length, 
         _) = unpack('> B B I I', bytestring)
         
        self._update_parameters()
        
    def _update_parameters(self):
        self.parameters = [self.pdu_type, 
                      0x00, # Reserved
                      self.pdu_length,
                      0x0000] # Reserved

    def get_length(self):
        return 10

    def __str__(self):
        s  = "A-RELEASE-RP PDU\n"
        s += " PDU type: 0x%02x\n" % self.pdu_type
        s += " PDU length: %d\n" % self.pdu_length
        return s


class A_ABORT_PDU(PDU):
    """
    Represents the A-ABORT PDU that, when encoded, is received from/sent 
    to the peer AE.

    The A-ABORT PDU signals that the association will be aborted

    A A-ABORT requires the following parameters (see PS3.8 Section 
        9.3.8):
        * PDU type (1, fixed value, 0x06)
        * PDU length (1)
        * Source (1)
        * Reason/Diagnostic (1)
        
    See PS3.8 Section 9.3.7 for the structure of the PDU, especially Table 9-25.
    
    Attributes
    ----------
    length : int
        The length of the encoded PDU in bytes
    reason_str : str
        The reason for the abort
    source_str : str
        The source of the abort, one of ('DUL service-user', 
        'DUL service-provider')
    """
    def __init__(self):
        self.pdu_type = 0x07
        self.pdu_length = 0x04
        self.source = None
        self.reason_diagnostic = None
        
        self.formats = ['B', 'B', 'I', 'B', 'B', 'B', 'B']
        self.parameters = [self.pdu_type, 
                      0x00, # Reserved
                      self.pdu_length,
                      0x00, # Reserved
                      0x00, # Reserved
                      self.source,
                      self.reason_diagnostic] # Reserved

    def FromParams(self, primitive):
        """
        Set up the PDU using the parameter values from the A-RELEASE `primitive`
        
        Parameters
        ----------
        primitive : pynetdicom.DULparameters.A_ABORT_ServiceParameters or
        pynetdicom.DULparameters.A_P_ABORT_ServiceParameters
            The parameters to use for setting up the PDU
        """
        # User initiated abort
        if primitive.__class__ == A_ABORT_ServiceParameters:
            # The reason field shall be 0x00 when the source is DUL service-user
            self.reason_diagnostic = 0
            self.source = primitive.AbortSource
        
        # User provider primitive abort
        elif primitive.__class__ == A_P_ABORT_ServiceParameters:
            self.reason_diagnostic = primitive.ProviderReason
            self.source = 2

    def ToParams(self):
        """ 
        Convert the current A-ABORT PDU to a primitive
        
        Returns
        -------
        pynetdicom.DULparameters.A_ABORT_ServiceParameters or 
        pynetdicom.DULparameters.A_P_ABORT_ServiceParameters
            The primitive to convert the PDU to
        """
        # User initiated abort
        if self.source == 0x00:
            primitive = A_ABORT_ServiceParameters()
            primitive.AbortSource = self.source
        
        # User provider primitive abort
        elif self.source == 0x02:
            primitive = A_P_ABORT_ServiceParameters()
            primitive.ProviderReason = self.reason_diagnostic
        
        return primitive

    def Encode(self):
        """
        Encode the PDU's parameter values into a bytes string
        
        Returns
        -------
        bytestring : bytes
            The encoded PDU that will be sent to the peer AE
        """
        formats = '> B B I B B B B'
        parameters = [self.pdu_type, 
                      0x00, # Reserved
                      self.pdu_length,
                      0x00, # Reserved
                      0x00, # Reserved
                      self.source,
                      self.reason_diagnostic]
                      
        bytestring  = bytes()
        bytestring += pack(formats, *parameters)

        return bytestring

    def Decode(self, bytestring):
        """
        Decode the parameter values for the PDU from the bytes string sent
        by the peer AE
        
        Parameters
        ----------
        bytestring : bytes
            The bytes string received from the peer
        """
        # Decode the A-ABORT PDU
        (self.pdu_type, 
         _, 
         self.pdu_length, 
         _,
         _, 
         self.source, 
         self.reason_diagnostic) = unpack('> B B I B B B B', bytestring)
         
        self._update_parameters()
        
    def _update_parameters(self):
        self.parameters = [self.pdu_type, 
                      0x00, # Reserved
                      self.pdu_length,
                      0x00, # Reserved
                      0x00, # Reserved
                      self.source,
                      self.reason_diagnostic] # Reserved

    def get_length(self):
        return 10

    def __str__(self):
        s  = "A-ABORT PDU\n"
        s += " PDU type: 0x%02x\n" % self.pdu_type
        s += " PDU length: %d\n" % self.pdu_length
        s += " Abort Source: %d\n" % self.source
        s += " Reason/Diagnostic: %d\n" % self.reason_diagnostic
        
        return s

    @property
    def source_str(self):
        """
        See PS3.8 9.3.8
        
        Returns
        -------
        str
            The source of the Association abort
        """
        sources = {0 : 'DUL service-user',
                   1 : 'Reserved',
                   2 : 'DUL service-provider'}
        
        return sources[self.source]
    
    @property
    def reason_str(self):
        """
        See PS3.8 9.3.8
        
        Returns
        -------
        str
            The reason given for the Association abort
        """
        if self.source == 2:
            reason_str = { 0 : "No reason given",
                           1 : "Unrecognised PDU",
                           2 : "Unexpected PDU",
                           3 : "Reserved",
                           4 : "Unrecognised PDU parameter",
                           5 : "Unexpected PDU parameter",
                           6 : "Invalid PDU parameter value"}
            return reason_str[self.reason_diagnostic]
        else:
            return 'No reason given'


# Item and sub-item classes
class ApplicationContextItem(PDU):
    """
    Represents the Application Context Item used in A-ASSOCIATE-RQ and 
    A-ASSOCIATE-AC PDUs.

    The Application Context Item requires the following parameters (see PS3.8 
    Section 9.3.2.1):
        * Item type (1, fixed value, 0x10)
        * Item length (1) 
        * Application Context Name (1, fixed in an application)
        
    See PS3.8 Section 9.3.2.1 for the structure of the PDU, especially 
    Table 9-12.
    
    Used in A_ASSOCIATE_RQ_PDU - Variable items
    Used in A_ASSOCIATE_AC_PDU - Variable items
    
    Attributes
    ----------
    application_context_name : pydicom.uid.UID
        The UID for the Application Context Name
    length : int
        The length of the Item in bytes
    """
    def __init__(self):
        self.item_type = 0x10
        self.item_length = None
        self.application_context_name = ''
        
        self.formats = ['B', 'B', 'H', 's']
        self.parameters = [self.item_type, 
                           0x00, # Reserved
                           self.item_length,
                           self.application_context_name]

    def FromParams(self, primitive):
        """
        Set up the Item using the parameter values from the `primitive`
        
        Parameters
        ----------
        primitive : str
            The UID value to use for the Application Context Name
        """
        self.application_context_name = primitive

    def ToParams(self):
        """ 
        Convert the current Item to a primitive
        
        Returns
        -------
        pydicom.uid.UID
            The Application Context Name's UID value
        """
        return self.application_context_name

    def Encode(self):
        """
        Encode the Item's parameter values into a bytes string
        
        Returns
        -------
        bytestring : bytes
            The encoded Item used in the parent PDU
        """
        formats = '> B B H'
        parameters = [self.item_type, 
                      0x00, # Reserved
                      self.item_length]
                      
        bytestring  = bytes()
        bytestring += pack(formats, *parameters)
        bytestring += bytes(self.application_context_name.title(), 'utf-8')
        
        return bytestring

    def Decode(self, bytestream):
        """
        Decode the parameter values for the Item from the parent PDU's byte
        stream
        
        Parameters
        ----------
        bytestream : io.BytesIO
            The byte stream to decode
        """
        (self.item_type, 
         _,
         self.item_length) = unpack('> B B H', bytestream.read(4))
        
        self.application_context_name = bytestream.read(self.item_length)
        
        self._update_parameters()
        
    def _update_parameters(self):
        self.parameters = [self.item_type, 
                           0x00, # Reserved
                           self.item_length,
                           self.application_context_name]

    def get_length(self):
        return 4 + self.item_length

    @property
    def application_context_name(self):
        """ Returns the Application Context Name as a pydicom.uid.UID """
        return self._application_context_name

    @application_context_name.setter
    def application_context_name(self, value):
        """
        Set the application context name

        Parameters
        ----------
        value : pydicom.uid.UID, str or bytes
            The value of the Application Context Name's UID
        """
        if isinstance(value, UID):
            pass
        elif isinstance(value, str):
            value = UID(value)
        elif isinstance(value, bytes):
            value = UID(value.decode('utf-8'))
        else:
            raise TypeError('Application Context Name must be a UID, str or bytes')

        self._application_context_name = value
        
        # Update the item_length parameter to account fo the new value
        self.item_length = len(self.application_context_name)

class PresentationContextItemRQ(PDU):
    """
    Represents a Presentation Context Item used in A-ASSOCIATE-RQ PDUs.

    The Presentation Context Item requires the following parameters (see PS3.8 
    Section 9.3.2.2):
        * Item type (1, fixed value, 0x20)
        * Item length (1)
        * Presentation context ID (1)
        * Abstract/Transfer Syntax Sub-items (1)
          * Abstract Syntax Sub-item (1)
            * Item type (1, fixed, 0x30)
            * Item length (1)
            * Abstract syntax name (1)
          * Transfer Syntax Sub-items (1 or more)
            * Item type (1, fixed, 0x40)
            * Item length (1)
            * Transfer syntax name(s) (1 or more)
        
    See PS3.8 Section 9.3.2.2 for the structure of the item, especially 
    Table 9-13.
    
    Used in A_ASSOCIATE_RQ_PDU - Variable items
    
    Attributes
    ----------
    abstract_syntax : pydicom.uid.UID
        The presentation context's Abstract Syntax value
    length : int
        The length of the item in bytes
    ID : int
        The presentation context's ID
    transfer_syntax : list of pydicom.uid.UID
        The presentation context's Transfer Syntax(es)
        
    SCP : None or int
        Defaults to None if SCP/SCU role negotiation not used, 0 or 1 if used
    SCU : None or int
        Defaults to None if SCP/SCU role negotiation not used, 0 or 1 if used
    """
    def __init__(self):
        self.item_type = 0x20
        self.item_length = None
        self.presentation_context_id = None
        
        # AbstractTransferSyntaxSubItems is a list
        # containing the following elements:
        #   One AbstractSyntaxtSubItem
        #   One or more TransferSyntaxSubItem
        self.abstract_transfer_syntax_sub_items = []
        
        # Non-standard parameters
        #   Used for tracking SCP/SCU Role Negotiation
        # Consider shifting to properties?
        self.SCP = None
        self.SCU = None
        
        self.formats = ['B', 'B', 'H', 'B', 'B', 'B', 'B']
        self.parameters = [self.item_type, 
                           0x00, # Reserved
                           self.item_length,
                           self.presentation_context_id,
                           0x00, # Reserved
                           0x00, # Reserved
                           0x00,
                           self.abstract_transfer_syntax_sub_items] # Reserved
        
    def FromParams(self, primitive):
        """
        Set up the Item using the parameter values from the `primitive`
        
        Parameters
        ----------
        primitive : pynetdicom.utils.PresentationContext
            The PresentationContext object to use to setup the Item
        """
        # Add presentation context ID
        self.presentation_context_id = primitive.ID
        
        # Add abstract syntax
        abstract_syntax = AbstractSyntaxSubItem()
        abstract_syntax.FromParams(primitive.AbstractSyntax)
        self.abstract_transfer_syntax_sub_items.append(abstract_syntax)

        # Add transfer syntax(es)
        for syntax in primitive.TransferSyntax:
            transfer_syntax = TransferSyntaxSubItem()
            transfer_syntax.FromParams(syntax)
            self.abstract_transfer_syntax_sub_items.append(transfer_syntax)
        
        self.get_length()

    def ToParams(self):
        """ 
        Convert the current Item to a primitive
        
        Returns
        -------
        pynetdicom.utils.PresentationContext
            The primitive to covert the Item to
        """
        context = PresentationContext(self.presentation_context_id)
        
        # Add transfer syntax(es)
        for syntax in self.abstract_transfer_syntax_sub_items:
            if isinstance(syntax, TransferSyntaxSubItem):
                context.add_transfer_syntax(syntax.ToParams())
            elif isinstance(syntax, AbstractSyntaxSubItem):
                context.AbstractSyntax = syntax.ToParams()
        
        return context

    def Encode(self):
        """
        Encode the Item's parameter values into a bytes string
        
        Returns
        -------
        bytestring : bytes
            The encoded Item used in the parent PDU
        """
        formats = '> B B H B B B B'
        parameters = [self.item_type, 
                      0x00, # Reserved
                      self.item_length,
                      self.presentation_context_id,
                      0x00, # Reserved
                      0x00, # Reserved
                      0x00] # Reserved
                      
        bytestring  = bytes()
        bytestring += pack(formats, *parameters)
        
        for ii in self.abstract_transfer_syntax_sub_items:
            bytestring += ii.Encode()
        
        return bytestring

    def Decode(self, bytestream):
        """
        Decode the parameter values for the Item from the parent PDU's byte
        stream
        
        Parameters
        ----------
        bytestream : io.BytesIO
            The byte stream to decode
        """
        # Decode the Item parameters up to the Abstract/Transfer Syntax
        (self.item_type, 
         _, 
         self.item_length,
         self.presentation_context_id, 
         _, 
         _,
         _) = unpack('> B B H B B B B', bytestream.read(8))
        
        # Decode the Abstract/Transfer Syntax Sub-items
        item = self._next_item(bytestream)
        while isinstance(item, AbstractSyntaxSubItem) or \
                            isinstance(item, TransferSyntaxSubItem):
            item.Decode(bytestream)
            self.abstract_transfer_syntax_sub_items.append(item)
            
            item = self._next_item(bytestream)

        self._update_parameters()
        
    def _update_parameters(self):
        self.parameters = [self.item_type, 
                           0x00,
                           self.item_length,
                           self.presentation_context_id,
                           0x00,
                           0x00,
                           0x00,
                           self.abstract_transfer_syntax_sub_items]

    def _update_item_length(self):
        self.item_length = 4
        
        for ii in self.abstract_transfer_syntax_sub_items:
            self.item_length += ii.length

    def get_length(self):
        self._update_item_length()
        return 4 + self.item_length

    def __str__(self):
        s  = " Presentation context RQ item\n"
        s += "  Item type: 0x%02x\n" % self.item_type
        s += "  Item length: %d\n" % self.item_length
        s += "  Presentation context ID: %d\n" % self.presentation_context_id
        
        for ii in self.abstract_transfer_syntax_sub_items:
            s += '%s' %ii
            
        return s

    @property
    def ID(self):
        """
        See PS3.8 9.3.2.2
        
        Returns
        -------
        int
            Odd number between 1 and 255 (inclusive)
        """
        return self.presentation_context_id

    @property
    def abstract_syntax(self):
        for ii in self.abstract_transfer_syntax_sub_items:
            if isinstance(ii, AbstractSyntaxSubItem):
                return ii.abstract_syntax_name
                
    @property
    def transfer_syntax(self):
        syntaxes = []
        for ii in self.abstract_transfer_syntax_sub_items:
            if isinstance(ii, TransferSyntaxSubItem):
                syntaxes.append(ii.transfer_syntax_name)

        return syntaxes

class PresentationContextItemAC(PDU):
    """
    Represents a Presentation Context Item used in A-ASSOCIATE-AC PDUs.

    The Presentation Context Item requires the following parameters (see PS3.8 
    Section 9.3.3.2):
        * Item type (1, fixed value, 0x21)
        * Item length (1)
        * Presentation context ID (1)
        * Result/reason (1)
        * Transfer Syntax Sub-item (1)
          * Item type (1, fixed, 0x40)
          * Item length (1)
          * Transfer syntax name (1)
        
    See PS3.8 Section 9.3.3.2 for the structure of the item, especially 
    Table 9-18.
    
    Used in A_ASSOCIATE_AC_PDU - Variable items
    
    Attributes
    ----------
    length : int
        The length of the item in bytes
    ID : int
        The presentation context's ID
    result : int
        The presentation context's result/reason value
    result_str : str
        The result as a string, one of ('Accepted', 'User Rejected', 'No Reason', 
        'Abstract Syntax Not Supported', 'Transfer Syntaxes Not Supported')
    transfer_syntax : pydicom.uid.UID
        The presentation context's Transfer Syntax
    
    SCP : None or int
        Defaults to None if SCP/SCU role negotiation not used, 0 or 1 if used
    SCU : None or int
        Defaults to None if SCP/SCU role negotiation not used, 0 or 1 if used
    """
    def __init__(self):
        self.item_type = 0x21
        self.item_length = None
        self.presentation_context_id = None
        self.result_reason = None
        self.transfer_syntax_sub_item = None

        # Used for tracking SCP/SCU Role Negotiation
        self.SCP = None
        self.SCU = None
        
        self.formats = ['B', 'B', 'H', 'B', 'B', 'B', 'B']
        self.parameters = [self.item_type, 
                           0x00, # Reserved
                           self.item_length,
                           self.presentation_context_id,
                           0x00, # Reserved
                           self.result_reason,
                           0x00, # Reserved
                           self.transfer_syntax_sub_item]

    def FromParams(self, primitive):
        """
        Set up the Item using the parameter values from the `primitive`
        
        Parameters
        ----------
        primitive : pynetdicom.utils.PresentationContext
            The PresentationContext object to use to setup the Item
        """
        # Add presentation context ID
        self.presentation_context_id = primitive.ID
        
        # Add reason
        self.result_reason = primitive.Result
        
        # Add transfer syntax
        self.transfer_syntax_sub_item = TransferSyntaxSubItem()
        self.transfer_syntax_sub_item.FromParams(primitive.TransferSyntax[0])
        
        self.get_length()

    def ToParams(self):
        """ 
        Convert the current Item to a primitive
        
        Returns
        -------
        pynetdicom.utils.PresentationContext
            The primitive to covert the Item to
        """
        primitive = PresentationContext(self.presentation_context_id)
        primitive.Result = self.result_reason
        primitive.add_transfer_syntax(self.transfer_syntax_sub_item.ToParams())

        return primitive

    def Encode(self):
        """
        Encode the Item's parameter values into a bytes string
        
        Returns
        -------
        bytestring : bytes
            The encoded Item used in the parent PDU
        """
        formats = '> B B H B B B B'
        parameters = [self.item_type, 
                      0x00, # Reserved
                      self.item_length,
                      self.presentation_context_id,
                      0x00, # Reserved
                      self.result_reason, # Reserved
                      0x00] # Reserved
                      
        bytestring  = bytes()
        bytestring += pack(formats, *parameters)
        bytestring += self.transfer_syntax_sub_item.Encode()

        return bytestring

    def Decode(self, bytestream):
        """
        Decode the parameter values for the Item from the parent PDU's byte
        stream
        
        Parameters
        ----------
        bytestream : io.BytesIO
            The byte stream to decode
        """
        # Decode the Item parameters up to the Transfer Syntax
        (self.item_type, 
         _, 
         self.item_length,
         self.presentation_context_id, 
         _, 
         self.result_reason,
         _) = unpack('> B B H B B B B', bytestream.read(8))
        
        # Decode the Transfer Syntax
        self.transfer_syntax_sub_item = TransferSyntaxSubItem()
        self.transfer_syntax_sub_item.Decode(bytestream)
        
        self._update_parameters()
        
    def _update_parameters(self):
        self.parameters = [self.item_type, 
                           0x00, # Reserved
                           self.item_length,
                           self.presentation_context_id,
                           0x00, # Reserved
                           self.result_reason,
                           0x00, # Reserved
                           self.transfer_syntax_sub_item]

    def get_length(self):
        self.item_length = 4 + self.transfer_syntax_sub_item.length
        
        return 4 + self.item_length

    def __str__(self):
        s  = " Presentation context AC item\n"
        s += "  Item type:   0x%02x\n" % self.item_type
        s += "  Item length: %d\n" % self.item_length
        s += "  Presentation context ID: %d\n" % self.presentation_context_id
        s += "  Result/Reason: %d\n" % self.result_reason
        s += "  %s" %self.transfer_syntax_sub_item
        return s

    @property
    def ID(self):
        return self.presentation_context_id

    @property
    def result(self):
        return self.result_reason
    
    @property
    def result_str(self):
        result_options = {0 : 'Accepted', 
                          1 : 'User Rejection', 
                          2 : 'Provider Rejection',
                          3 : 'Abstract Syntax Not Supported',
                          4 : 'Transfer Syntax Not Supported'} 
        return result_options[self.result]

    @property
    def transfer_syntax(self):
        return self.transfer_syntax_sub_item.transfer_syntax_name

class AbstractSyntaxSubItem(PDU):
    """
    Represents an Abstract Syntax Sub-item used in A-ASSOCIATE-RQ PDUs.

    The Abstract Syntax Sub-item requires the following parameters (see PS3.8 
    Section 9.3.2.2.1):
        * Item type (1, fixed value, 0x30)
        * Item length (1)
        * Abstract syntax name (1)
        
    See PS3.8 Section 9.3.2.2.1 for the structure of the item, especially 
    Table 9-14.
    
    Used in A_ASSOCIATE_RQ_PDU - Variable items - Presentation Context items - 
    Abstract/Transfer Syntax sub-items
    
    Attributes
    ----------
    abstract_syntax : pydicom.uid.UID
        The abstract syntax
    length : int
        The length of the item in bytes
    """
    def __init__(self):
        self.item_type = 0x30
        self.item_length = None
        self.abstract_syntax_name = None
        
        self.formats = ['B', 'B', 'H', 's']
        self.parameters = [self.item_type, 
                           0x00,
                           self.item_length,
                           self.abstract_syntax_name]

    def FromParams(self, primitive):
        """
        Set up the Item using the parameter values from the `primitive`
        
        Parameters
        ----------
        primitive : pydicom.uid.UID, bytes or str
            The abstract syntax name
        """
        self.abstract_syntax_name = primitive
        self.item_length = len(self.abstract_syntax_name)

    def ToParams(self):
        """ 
        Convert the current Item to a primitive
        
        Returns
        -------
        pydicom.uid.UID
            The Abstract Syntax Name's UID value
        """
        return self.abstract_syntax_name

    def Encode(self):
        """
        Encode the Item's parameter values into a bytes string
        
        Returns
        -------
        bytestring : bytes
            The encoded Item used in the parent PDU
        """
        formats = '> B B H'
        parameters = [self.item_type, 
                      0x00, # Reserved
                      self.item_length]
                      
        bytestring  = bytes()
        bytestring += pack(formats, *parameters)
        bytestring += bytes(self.abstract_syntax_name.title(), 'utf-8')
        
        return bytestring

    def Decode(self, bytestream):
        """
        Decode the parameter values for the Item from the parent PDU's byte
        stream
        
        Parameters
        ----------
        bytestream : io.BytesIO
            The byte stream to decode
        """
        (self.item_type, 
         _,
         self.item_length) = unpack('> B B H', bytestream.read(4))
        
        self.abstract_syntax_name = bytestream.read(self.item_length)
        
        self._update_parameters()
        
    def _update_parameters(self):
        self.parameters = [self.item_type, 
                           0x00,
                           self.item_length,
                           self.abstract_syntax_name]

    def get_length(self):
        self.item_length = len(self.abstract_syntax_name)
        
        return 4 + self.item_length

    def __str__(self):
        s  = "  Abstract syntax sub item\n"
        s += "   Item type: 0x%02x\n" % self.item_type
        s += "   Item length: %d\n" % self.item_length
        s += "   Abstract syntax name: %s\n" % self.abstract_syntax
        
        return s
    
    @property
    def abstract_syntax(self):
        return self.abstract_syntax_name
    
    @property
    def abstract_syntax_name(self):
        return self._abstract_syntax_name
        
    @abstract_syntax_name.setter
    def abstract_syntax_name(self, value):
        """
        Sets the Abstract Syntax Name parameter
        
        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The value for the Abstract Syntax Name
        """
        if isinstance(value, UID):
            pass
        elif isinstance(value, str):
            value = UID(value)
        elif isinstance(value, bytes):
            value = UID(value.decode('utf-8'))
        elif value is None:
            pass
        else:
            raise TypeError('Abstract Syntax must be a pydicom.uid.UID, str or bytes')
        
        self._abstract_syntax_name = value

class TransferSyntaxSubItem(PDU):
    """
    Represents a Transfer Syntax Sub-item used in A-ASSOCIATE-RQ and 
    A-ASSOCIATE-AC PDUs.

    The Abstract Syntax Sub-item requires the following parameters (see PS3.8 
    Section 9.3.2.2.2):
        * Item type (1, fixed value, 0x40)
        * Item length (1)
        * Transfer syntax name (1)
        
    See PS3.8 Section 9.3.2.2.2 for the structure of the item, especially 
    Table 9-15.
    
    Used in A_ASSOCIATE_RQ_PDU - Variable items - Presentation Context items - 
    Abstract/Transfer Syntax sub-items
    Used in A_ASSOCIATE_AC_PDU - Variable items - Presentation Context items - 
    Transfer Syntax sub-item
    
    Attributes
    ----------
    length : int
        The length of the item in bytes
    transfer_syntax : pydicom.uid.UID
        The transfer syntax
    """
    def __init__(self):
        self.item_type = 0x40
        self.item_length = None
        self.transfer_syntax_name = None
        
        self.formats = ['B', 'B', 'H', 's']
        self.parameters = [self.item_type, 
                           0x00, # Reserved
                           self.item_length,
                           self.transfer_syntax_name]

    def FromParams(self, primitive):
        """
        Set up the Item using the parameter values from the `primitive`
        
        Parameters
        ----------
        primitive : pydicom.uid.UID, bytes or str
            The transfer syntax name
        """
        self.transfer_syntax_name = primitive
        self.item_length = len(self.transfer_syntax_name)

    def ToParams(self):
        """ 
        Convert the current Item to a primitive
        
        Returns
        -------
        pydicom.uid.UID
            The Transfer Syntax Name's UID value
        """
        return self.transfer_syntax_name

    def Encode(self):
        """
        Encode the Item's parameter values into a bytes string
        
        Returns
        -------
        bytestring : bytes
            The encoded Item used in the parent PDU
        """
        formats = '> B B H'
        parameters = [self.item_type, 
                      0x00, # Reserved
                      self.item_length]
                      
        bytestring  = bytes()
        bytestring += pack(formats, *parameters)
        bytestring += bytes(self.transfer_syntax_name.title(), 'utf-8')
        
        return bytestring

    def Decode(self, bytestream):
        """
        Decode the parameter values for the Item from the parent PDU's byte
        stream
        
        Parameters
        ----------
        bytestream : io.BytesIO
            The byte stream to decode
        """
        (self.item_type, 
         _,
         self.item_length) = unpack('> B B H', bytestream.read(4))
        
        self.transfer_syntax_name = bytestream.read(self.item_length)
        
        self._update_parameters()
        
    def _update_parameters(self):
        self.parameters = [self.item_type, 
                           0x00,
                           self.item_length,
                           self.transfer_syntax_name]

    def get_length(self):
        self.item_length = len(self.transfer_syntax_name)
        return 4 + self.item_length

    def __str__(self):
        s  = "  Transfer syntax sub item\n"
        s += "   Item type: 0x%02x\n" % self.item_type
        s += "   Item length: %d\n" % self.item_length
        s += "   Transfer syntax name: %s\n" % self.transfer_syntax_name
        
        return s

    @property
    def transfer_syntax(self):
        return self.transfer_syntax_name

    @property
    def transfer_syntax_name(self):
        return self._transfer_syntax_name
        
    @transfer_syntax_name.setter
    def transfer_syntax_name(self, value):
        """
        Sets the Transfer Syntax Name parameter
        
        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The value for the Transfer Syntax Name
        """
        if isinstance(value, UID):
            pass
        elif isinstance(value, str):
            value = UID(value)
        elif isinstance(value, bytes):
            value = UID(value.decode('utf-8'))
        elif value is None:
            pass
        else:
            raise TypeError('Transfer syntax must be a pydicom.uid.UID, bytes or str')
        
        self._transfer_syntax_name = value


class PresentationDataValueItem(PDU):
    """
    Represents a Presentation Data Value Item used in P-DATA-TF PDUs.

    The Presentation Data Value Item requires the following parameters (see 
    PS3.8 Section 9.3.5.1):
        * Item length (1)
        * Presentation context ID (1)
        * Presentation data value (1)
        
    See PS3.8 Section 9.3.5.1 for the structure of the item, especially 
    Table 9-23.
    
    Used in P_DATA_TF_PDU - Presentation data value items
    
    Attributes
    ----------
    data : FIXME
        The presentation data value
    ID : int
        The presentation context ID
    length : int
        The length of the item in bytes
    message_control_header_byte : str
        A string containing the contents of the message control header byte
        formatted as an 8-bit binary. See PS3.8 FIXME
    """
    def __init__(self):
        self.item_length = None
        self.presentation_context_id = None
        self.presentation_data_value = None
        
        self.formats = ['I', 'B', 's']
        self.parameters = [self.item_length, 
                           self.presentation_context_id, 
                           self.presentation_data_value]

    def FromParams(self, primitive):
        """
        Set up the Item using the parameter values from the `primitive`
        
        Parameters
        ----------
        primitive : list
            The Presentation Data as a list [context ID, data]
        """
        self.presentation_context_id = primitive[0]
        self.presentation_data_value = primitive[1]
        self.item_length = 1 + len(self.presentation_data_value)

    def ToParams(self):
        """ 
        Convert the current Item to a primitive
        
        Returns
        -------
        list
            The Presentation Data as a list
        """
        return [self.presentation_context_id, self.presentation_data_value]

    def Encode(self):
        """
        Encode the Item's parameter values into a bytes string
        
        Returns
        -------
        bytestring : bytes
            The encoded Item used in the parent PDU
        """
        formats = '> I B'
        parameters = [self.item_length, 
                      self.presentation_context_id]
                      
        bytestring  = bytes()
        bytestring += pack(formats, *parameters)
        bytestring += self.presentation_data_value
        
        return bytestring

    def Decode(self, bytestream):
        """
        Decode the parameter values for the Item from the parent PDU's byte
        stream
        
        Parameters
        ----------
        bytestream : io.BytesIO
            The byte stream to decode
        """
        (self.item_length, 
         self.presentation_context_id) = unpack('> I B', bytestream.read(5))

        self.presentation_data_value = bytestream.read(int(self.item_length) - 1)
        
        self._update_parameters()

    def _update_parameters(self):
        self.parameters = [self.item_length, 
                           self.presentation_context_id, 
                           self.presentation_data_value]

    def get_length(self):
        self.item_length = 1 + len(self.presentation_data_value)
        return 4 + self.item_length

    def __str__(self):
        s  = " Presentation value data item\n"
        s += "  Item length: %d\n" % self.item_length
        s += "  Presentation context ID: %d\n" % self.presentation_context_id
        s += "  Presentation data value: %s ...\n" % self.presentation_data_value[:20]
        # FIXME
        return s
    
    @property
    def data(self):
        return self.presentation_data_value
    
    @property
    def ID(self):
        return self.presentation_context_id
    
    @property
    def message_control_header_byte(self):
        return "{:08b}".format(self.presentation_data_value[0])

    
class UserInformationItem(PDU):
    """
    Represents the User Information Item used in A-ASSOCIATE-RQ and 
    A-ASSOCIATE-AC PDUs.

    The User Information Item requires the following parameters (see PS3.8 
    Section 9.3.2.3):
        * Item type (1, fixed, 0x50)
        * Item length (1)
        * User data sub-items (2 or more)
            * Maximum Length Received Sub-item (1)
            * Implementation Class UID Sub-item (1)
            * Optional User Data Sub-items (0 or more)
    
    See PS3.8 Section 9.3.2.3 for the structure of the PDU, especially 
    Table 9-16.
    
    Used in A_ASSOCIATE_RQ_PDU - Variable items
    Used in A_ASSOCIATE_AC_PDU - Variable items
    
    Attributes
    ----------
    asynchronous_operations_window : AsynchronousOperationsWindowSubItem or None
        The AsynchronousOperationsWindowSubItem object, or None if the sub-item 
        is not present.
    common_extended_negotiation : SOPClassCommonExtendedNegotiationSubItem or None
        The SOPClassCommonExtendedNegotiationSubItem object, or None if the 
        sub-item is not present.
    extended_negotiation : SOPClassExtendedNegotiationSubItem or None
        The SOPClassExtendedNegotiationSubItem object, or None if the sub-item 
        is not present.
    implementation_class_uid : pydicom.uid.UID
        The implementation class UID for the Implementation Class UID sub-item
    implementation_version_name : str or None
        The implementation version name for the Implementation Version Name 
        sub-item, or None if the sub-item is not present.
    length : int
        The length of the Item in bytes
    maximum_length : int
        The maximum length received value for the Maximum Length sub-item
    maximum_operations_invoked : int or None
        , or None if the sub-item is not present.
    maximum_operations_performed : int or None
        , or None if the sub-item is not present.
    role_selection : SCP_SCU_RoleSelectionSubItem or None
        The SCP_SCU_RoleSelectionSubItem object or None if the sub-item is 
        not present.
    user_identity : UserIdentitySubItemRQ or UserIdentitySubItemAC or None
        The UserIdentitySubItemRQ/UserIdentitySubItemAC object, or None if the 
        sub-item is not present.
    """
    def __init__(self):
        self.item_type = 0x50
        self.item_length = None
        self.user_data = []
        
        self.formats = ['B', 'B', 'H']
        self.parameters = [self.item_type, 
                           0x00, # Reserved
                           self.item_length,
                           self.user_data]

    def FromParams(self, primitive):
        """
        Set up the Item using the parameter values from the `primitive`
        
        Parameters
        ----------
        primitive : FIXME
        """
        for ii in primitive:
            # Why is this ToParams?
            self.user_data.append(ii.ToParams())

        self._update_item_length()

    def ToParams(self):
        """ 
        Convert the current Item to a primitive
        
        Returns
        -------
        list
            
        """
        primitive = []
        for ii in self.user_data:
            primitive.append(ii.ToParams())
        
        return primitive

    def Encode(self):
        """
        Encode the Item's parameter values into a bytes string
        
        Returns
        -------
        bytestring : bytes
            The encoded Item used in the parent PDU
        """
        formats = '> B B H'
        parameters = [self.item_type, 
                      0x00, # Reserved
                      self.item_length]
                      
        bytestring  = bytes()
        bytestring += pack(formats, *parameters)
        
        for ii in self.user_data:
            bytestring += ii.Encode()
        
        return bytestring

    def Decode(self, bytestream):
        """
        Decode the parameter values for the Item from the parent PDU's byte
        stream
        
        Parameters
        ----------
        bytestream : io.BytesIO
            The byte stream to decode
        """
        (self.item_type, 
         _,
         self.item_length) = unpack('> B B H', bytestream.read(4))
        
        # Decode the User Data sub-items section
        item = self._next_item(bytestream)
        while item is not None:
            item.Decode(bytestream)
            self.user_data.append(item)
            
            item = self._next_item(bytestream)
            
        self._update_parameters()
        
    def _update_parameters(self):
        self.parameters = [self.item_type, 
                           0x00, # Reserved
                           self.item_length,
                           self.user_data]

    def _update_item_length(self):
        self.item_length = 0
        for ii in self.user_data:
            self.item_length += ii.length

    def get_length(self):
        self._update_item_length()
        return 4 + self.item_length

    def __str__(self):
        s = " User information item\n"
        s += "  Item type: 0x%02x\n" % self.item_type
        s += "  Item length: %d\n" % self.item_length
        s += "  User Data:\n "
        
        for ii in self.UserData[1:]:
            s += "  %s" %ii
        
        return s

    @property
    def common_extended_negotiation(self):
        raise NotImplementedError()
    
    @property
    def extended_negotiation(self):
        raise NotImplementedError()

    @property
    def implementation_class_uid(self):
        for ii in self.user_data:
            if isinstance(ii, ImplementationClassUIDSubItem):
                return ii.implementation_class_uid
    
    @property
    def implementation_version_name(self):
        for ii in self.user_data:
            if isinstance(ii, ImplementationVersionNameSubItem):
                return ii.implementation_version_name.decode('utf-8')
        
        return None
    
    @property
    def maximum_length(self):
        for ii in self.user_data:
            if isinstance(ii, MaximumLengthSubItem):
                return ii.MaximumLengthReceived
        
    @property
    def maximum_operations_invoked(self):
        for ii in self.user_data:
            if isinstance(ii, AsynchronousOperationsWindowSubItem):
                return ii.MaximumNumberOperationsInvoked
        
        return None
    
    @property
    def maximum_operations_performed(self):
        for ii in self.user_data:
            if isinstance(ii, AsynchronousOperationsWindowSubItem):
                return ii.MaximumNumberOperationsPerformed
        
        return None
        
    @property
    def role_selection(self):
        """
        See PS3.7 D3.3.4
        
        Optional
        
        Returns
        -------
        list of pynetdicom.PDU.SCP_SCU_RolesSelectionSubItem
            A list of the Association Requestor's Role Selection sub item objects
        """
        roles = []
        for ii in self.user_data:
            if isinstance(ii, SCP_SCU_RoleSelectionSubItem):
                roles.append(ii)
        
        if len(roles):
            return roles
            
        return None

    @property
    def user_identity(self):
        for ii in self.user_data:
            if isinstance(ii, UserIdentitySubItemRQ):
                return ii
            elif isinstance(ii, UserIdentitySubItemAC):
                return ii
        
        return None


class MaximumLengthSubItem(PDU):
    """
    PS3.8 Annex D.1.1
    
    Identical for A-ASSOCIATE-RQ and A-ASSOCIATE-AC
    """
    def __init__(self):
        self.ItemType = 0x51
        self.MaximumLengthReceived = None
        
        self.formats = ['B', 'B', 'H', 'I']
        self.parameters = [self.ItemType,
                           0x00,
                           0x0004,
                           self.MaximumLengthReceived]

    def FromParams(self, primitive):
        self.MaximumLengthReceived = primitive.MaximumLengthReceived

    def ToParams(self):
        primitive = MaximumLengthParameters()
        primitive.MaximumLengthReceived = self.MaximumLengthReceived
        return primitive

    def Encode(self):
        bytestream = b''
        bytestream += pack('B', self.ItemType)
        bytestream += pack('B', 0x00) # Reserved (fixed)
        bytestream += pack('>H', 0x0004) # Item Length (fixed)
        bytestream += pack('>I', self.MaximumLengthReceived)
        return bytestream

    def Decode(self, s):
        (self.ItemType, 
         _,
         _, 
         self.MaximumLengthReceived) = unpack('> B B H I', s.read(8))
         
        self._update_parameters()
         
    def _update_parameters(self):
        self.parameters = [self.ItemType,
                           0x00,
                           0x0004,
                           self.MaximumLengthReceived]

    def get_length(self):
        return 0x08

    def __repr__(self):
        s  = "Maximum length sub item\n"
        s += "\tItem type: 0x%02x\n" % self.ItemType
        s += "\tMaximum length received: %d\n" % self.MaximumLengthReceived
        return s


class GenericUserDataSubItem(PDU):
    """
    This class is provided only to allow user data to converted to and from
    PDUs. The actual data is not interpreted. This is left to the user.
    """
    def __init__(self):
        self.ItemType = None                # Unsigned byte
        self.ItemLength = None                        # Unsigned short
        self.UserData = None                # Raw string

    def FromParams(self, Params):
        self.ItemLength = len(Params.UserData)
        self.UserData = Params.UserData
        seld.ItemType = Params.ItemType

    def ToParams(self):
        tmp = GenericUserDataSubItem()
        tmp.ItemType = self.ItemType
        tmp.UserData = self.UserData
        return tmp

    def Encode(self):
        tmp = ''
        tmp = tmp + pack('B', self.ItemType)
        tmp = tmp + pack('B', 0x00)
        tmp = tmp + pack('>H', self.ItemLength)
        tmp = tmp + self.UserData
        return tmp

    def Decode(self, Stream):
        (self.ItemType, 
         _,
         self.ItemLength) = unpack('> B B H', Stream.read(4))
        # User data value is left in raw string format. The Application Entity
        # is responsible for dealing with it.
        self.UserData = Stream.read(int(self.ItemLength) - 1)

    def get_length(self):
        self.ItemLength = len(Params.UserData)
        return 4 + self.ItemLength

    def __repr__(self):
        tmp = "User data item\n"
        tmp = tmp + "  Item type: %d\n" % self.ItemType
        tmp = tmp + "  Item length: %d\n" % self.ItemLength
        if len(self.UserData) > 1:
            tmp = tmp + "  User data: %s ...\n" % self.UserData[:10]
        return tmp

class ImplementationClassUIDSubItem(PDU):
    """
    Implementation Class UID identifies in a unique manner a specific class
    of implementation. Each node claiming conformance to the DICOM Standard
    shall be assigned an Implementation Class UID to distinguish its 
    implementation environment from others.
    
    PS3.7 Annex D.3.3.2.1-2
    
    Identical for A-ASSOCIATE-RQ and A-ASSOCIATE-AC
    """
    def __init__(self):
        self.ItemType = 0x52
        self.ItemLength = None
        self.implementation_class_uid = None
        
        self.formats = ['B', 'B', 'H', 's']
        self.parameters = [self.ItemType,
                           0x00,
                           self.ItemLength,
                           self.implementation_class_uid]

    def FromParams(self, Params):
        self.implementation_class_uid = Params.ImplementationClassUID
        self.ItemLength = len(self.implementation_class_uid)

    def ToParams(self):
        tmp = ImplementationClassUIDParameters()
        tmp.ImplementationClassUID = self.implementation_class_uid
        return tmp

    def Encode(self):
        s = b''
        s += pack('B', self.ItemType)
        s += pack('B', 0x00)
        s += pack('>H', self.ItemLength)
        s += bytes(self.implementation_class_uid.title(), 'utf-8')
        return s

    def Decode(self, s):
        (self.ItemType, 
         _,
         self.ItemLength) = unpack('> B B H', s.read(4))
        self.implementation_class_uid = s.read(self.ItemLength)
        
        self._update_parameters()
        
    def _update_parameters(self):
        self.parameters = [self.ItemType,
                           0x00,
                           self.ItemLength,
                           self.implementation_class_uid]

    def get_length(self):
        self.ItemLength = len(self.implementation_class_uid)
        return 4 + self.ItemLength

    def __repr__(self):
        s  = "Implementation class UID sub item\n"
        s += "\tItem type: 0x%02x\n" %self.ItemType
        s += "\tItem length: %d\n" %self.ItemLength
        s += "\tImplementation class UID: %s\n" %self.implementation_class_uid
        return s
        
    @property
    def implementation_class_uid(self):
        """
        Returns the Implementation Class UID as a UID
        """
        return self._implementation_class_uid
        
    @implementation_class_uid.setter
    def implementation_class_uid(self, value):
        """
        
        """
        if isinstance(value, UID):
            pass
        elif isinstance(value, str):
            value = UID(value)
        elif isinstance(value, bytes):
            value = UID(value.decode('utf-8'))
        
        self._implementation_class_uid = value
        
class ImplementationVersionNameSubItem(PDU):
    """
    PS3.7 Annex D.3.3.2.3-4
    
    Identical for A-ASSOCIATE-RQ and A-ASSOCIATE-AC
    """
    def __init__(self):
        self.ItemType = 0x55
        self.ItemLength = None
        self.implementation_version_name = None
        
        self.formats = ['B', 'B', 'H', 's']
        self.parameters = [self.ItemType,
                           0x00,
                           self.ItemLength,
                           self.implementation_version_name]

    def FromParams(self, Params):
        self.implementation_version_name = Params.ImplementationVersionName
        self.ItemLength = len(self.implementation_version_name)

    def ToParams(self):
        tmp = ImplementationVersionNameParameters()
        tmp.ImplementationVersionName = self.implementation_version_name
        return tmp

    def Encode(self):
        tmp = b''
        tmp = tmp + pack('B', self.ItemType)
        tmp = tmp + pack('B', 0x00)
        tmp = tmp + pack('>H', self.ItemLength)
        tmp = tmp + self.implementation_version_name
        return tmp

    def Decode(self, Stream):
        (self.ItemType, 
         _,
         self.ItemLength) = unpack('> B B H', Stream.read(4))
        self.implementation_version_name = Stream.read(self.ItemLength)
        
        self._update_parameters()
        
    def _update_parameters(self):
        self.parameters = [self.ItemType,
                           0x00,
                           self.ItemLength,
                           self.implementation_version_name]

    def get_length(self):
        self.ItemLength = len(self.implementation_version_name)
        return 4 + self.ItemLength

    def __repr__(self):
        s  = "Implementation version name sub item\n"
        s += "\tItem type: 0x%02x\n" %self.ItemType
        s += "\tItem length: %d\n" %self.ItemLength
        s += "\tImplementation version name: %s\n" %self.implementation_version_name
        return s
        
    @property
    def implementation_version_name(self):
        """ Returns the implementation version name as bytes """
        return self._implementation_version_name
        
    @implementation_version_name.setter
    def implementation_version_name(self, value):
        if isinstance(value, bytes):
            pass
        elif isinstance(value, str):
            value = bytes(value, 'utf-8')
            
        self._implementation_version_name = value

class AsynchronousOperationsWindowSubItem(PDU):
    """
    Used to negotiate the maximum number of outstanding operation or 
    sub-operation requests (ie command requests) for each direction. The
    synchronous operations mode is the default mode and shall be supported by
    all DICOM AEs. This negotiation is optional.
    
    PS3.7 Annex D.3.3.3
    
    Identical for A-ASSOCIATE-RQ and A-ASSOCIATE-AC
    """
    def __init__(self):
        self.ItemType = 0x53
        self.ItemLength = 0x0004
        self.MaximumNumberOperationsInvoked = None
        self.MaximumNumberOperationsPerformed = None

    def FromParams(self, Params):
        self.MaximumNumberOperationsInvoked = \
                                    Params.MaximumNumberOperationsInvoked
        self.MaximumNumberOperationsPerformed = \
                                    Params.MaximumNumberOperationsPerformed

    def ToParams(self):
        tmp = AsynchronousOperationsWindowSubItem()
        tmp.MaximumNumberOperationsInvoked = \
                                    self.MaximumNumberOperationsInvoked
        tmp.MaximumNumberOperationsPerformed = \
                                    self.MaximumNumberOperationsPerformed
        return tmp

    def Encode(self):
        tmp = b''
        tmp = tmp + pack('B', self.ItemType)
        tmp = tmp + pack('B', 0x00)
        tmp = tmp + pack('>H', self.ItemLength)
        tmp = tmp + pack('>H', self.MaximumNumberOperationsInvoked)
        tmp = tmp + pack('>H', self.MaximumNumberOperationsPerformed)
        return tmp

    def Decode(self, Stream):
        (self.ItemType, 
         _, 
         self.ItemLength,
         self.MaximumNumberOperationsInvoked,
         self.MaximumNumberOperationsPerformed) = unpack('>B B H H H',
                                                                Stream.read(8))

    def get_length(self):
        # 0x08
        return 4 + self.ItemLength

    def __repr__(self):
        tmp = "  Asynchoneous operation window sub item\n"
        tmp = tmp + "   Item type: 0x%02x\n" % self.ItemType
        tmp = tmp + "   Item length: %d\n" % self.ItemLength
        tmp = tmp + \
            "   Maximum number of operations invoked: %d\n" % \
            self.MaximumNumberOperationsInvoked
        tmp = tmp + \
            "   Maximum number of operations performed: %d\n" % \
            self.MaximumNumberOperationsPerformed
        return tmp

class SCP_SCU_RoleSelectionSubItem(PDU):
    def __init__(self):
        self.ItemType = 0x54
        self.ItemLength = None
        self.UIDLength = None
        self.SOPClassUID = None
        self.SCURole = None
        self.SCPRole = None

    def FromParams(self, Params):
        self.SOPClassUID = Params.SOPClassUID
        self.SCURole = Params.SCURole
        self.SCPRole = Params.SCPRole
        self.ItemLength = 4 + len(self.SOPClassUID)
        self.UIDLength = len(self.SOPClassUID)

    def ToParams(self):
        tmp = SCP_SCU_RoleSelectionParameters()
        tmp.SOPClassUID = self.SOPClassUID
        tmp.SCURole = self.SCURole
        tmp.SCPRole = self.SCPRole
        return tmp

    def Encode(self):
        tmp = b''
        tmp += pack('B', self.ItemType)
        tmp += pack('B', 0x00)
        tmp += pack('>H', self.ItemLength)
        tmp += pack('>H', self.UIDLength)
        tmp += bytes(self.SOPClass, 'utf-8')
        tmp += pack('B B', self.SCURole, self.SCPRole)
        return tmp

    def Decode(self, Stream):
        (self.ItemType, 
         _,
         self.ItemLength, 
         self.UIDLength) = unpack('> B B H H', Stream.read(6))
        self.SOPClassUID = Stream.read(self.UIDLength)
        (self.SCURole, self.SCPRole) = unpack('B B', Stream.read(2))

    def get_length(self):
        self.ItemLength = 4 + len(self.SOPClassUID)
        return 4 + self.ItemLength

    def __repr__(self):
        tmp = "  SCU/SCP role selection sub item\n"
        tmp = tmp + "   Item type: 0x%02x\n" % self.ItemType
        tmp = tmp + "   Item length: %d\n" % self.ItemLength
        tmp = tmp + "   SOP class UID length: %d\n" % self.UIDLength
        tmp = tmp + "   SOP class UID: %s\n" % self.SOPClassUID
        tmp = tmp + "   SCU Role: %d\n" % self.SCURole
        tmp = tmp + "   SCP Role: %d" % self.SCPRole
        return tmp

    @property
    def SOPClass(self):
        """
        See PS3.7 D3.3.4
        
        Returns
        -------
        pydicom.uid.UID
            The SOP Class UID the Requestor AE is negotiating the role for
        """
        if isinstance(self.SOPClassUID, bytes):
            return UID(self.SOPClassUID.decode('utf-8'))
        elif isinstance(self.SOPClassUID, UID):
            return self.SOPClassUID
        else:
            return UID(self.SOPClassUID)
        
    @property
    def SCU(self):
        """
        See PS3.7 D3.3.4
        
        Returns
        -------
        int
            0 if SCU role isn't supported, 1 if supported
        """
        return self.SCURole
        
    @property
    def SCP(self):
        """
        See PS3.7 D3.3.4
        
        Returns
        -------
        int
            0 if SCP role isn't supported, 1 if supported
        """
        return self.SCPRole

class UserIdentitySubItemRQ(PDU):
    def __init__(self):
        self.ItemType = 0x58
        self.Reserved = 0x00
        self.ItemLength = None
        self.UserIdentityType = None
        self.PositiveResponseRequested = None
        self.PrimaryFieldLength = None
        self.PrimaryField = None
        self.SecondaryFieldLength = None
        self.SecondaryField = None

    def FromParams(self, parameters):
        self.UserIdentityType = parameters.UserIdentityType
        self.PositiveResponseRequested = parameters.PositiveResponseRequested
        self.PrimaryField = parameters.PrimaryField
        self.PrimaryFieldLength = len(self.PrimaryField)
        self.SecondaryField = parameters.SecondaryField
        self.SecondaryFieldLength = len(self.SecondaryField)
        self.ItemLength = 8 + self.PrimaryFieldLength + \
                                self.SecondaryFieldLength

    def ToParams(self):
        tmp = UserIdentityParameters()
        tmp.UserIdentityType = self.UserIdentityType
        tmp.PositiveResponseRequested = self.PositiveResponseRequested
        tmp.PrimaryField = self.PrimaryField
        tmp.SecondaryField = self.SecondaryField
        return tmp

    def Encode(self):
        tmp = b''
        tmp += pack('B', self.ItemType)
        tmp += pack('B', self.Reserved)
        tmp += pack('>H', self.ItemLength)
        tmp += pack('B', self.UserIdentityType)
        tmp += pack('B', self.PositiveResponseRequested)
        tmp += pack('>H', self.PrimaryFieldLength)
        tmp += bytes(self.PrimaryField)
        tmp += pack('>H', self.SecondaryFieldLength)
        if self.UserIdentityType == 0x02:
            tmp += bytes(self.SecondaryField)

        return tmp

    def Decode(self, stream):
        self.ItemType = unpack('>B', stream.read(2))
        self.Reserved = unpack('>B', stream.read(2))
        self.ItemLength = unpack('>H', stream.read(4))
        self.UserIdentityType = unpack('>B', stream.read(2))
        self.PositiveResponseRequested = unpack('>B', stream.read(2))
        self.PrimaryFieldLength = unpack('>H', stream.read(4))
        self.PrimaryField = unpack('>B', stream.read(self.PrimaryFieldLength))
        self.SecondaryFieldLength = unpack('>H', stream.read(4))
        
        if self.UserIdentityType == 0x02:
            self.SecondaryField = unpack('>B', stream.read(self.SecondaryFieldLength))

    def get_length(self):
        self.ItemLength = 8 + self.PrimaryFieldLength + \
                                self.SecondaryFieldLength
        return 4 + self.ItemLength

    @property
    def Type(self):
        """
        See PS3.7 D3.3.7
        
        Returns
        -------
        int
            1: Username as utf-8 string, 
            2: Username as utf-8 string and passcode
            3: Kerberos Service ticket
            4: SAML Assertion
        """
        return self.UserIdentityType
        
    @property
    def ResponseRequested(self):
        """
        See PS3.7 D3.3.7
        
        Returns
        -------
        int
            0 if no response requested, 1 otherwise
        """
        return self.PositiveResponseRequested

class UserIdentitySubItemAC(PDU):
    pass

class SOPClassExtendedNegotiationSubItem(PDU):
    pass

class SOPClassCommonExtendedNegotiationSubItem(PDU):
    pass


class MaximumLengthParameters():
    """
    The maximum length notification allows communicating AEs to limit the size
    of the data for each P-DATA indication. This notification is required for 
    all DICOM v3.0 conforming implementations.
    
    PS3.7 Annex D.3.3.1 and PS3.8 Annex D.1
    """
    def __init__(self):
        self.MaximumLengthReceived = None

    def ToParams(self):
        tmp = MaximumLengthSubItem()
        tmp.FromParams(self)
        return tmp

class ImplementationClassUIDParameters():
    """
    The implementation identification notification allows implementations of
    communicating AEs to identify each other at Association establishment time.
    It is intended to provider respective and non-ambiguous identification in
    the event of communication problems encountered between two nodes. This
    negotiation is required.
    
    Implementation identification relies on two pieces of information:
    - Implementation Class UID (required)
    - Implementation Version Name (optional)
    
    PS3.7 Annex D.3.3.2
    
    """
    def __init__(self):
        self.ImplementationClassUID = None

    def ToParams(self):
        tmp = ImplementationClassUIDSubItem()
        tmp.FromParams(self)
        return tmp

class ImplementationVersionNameParameters():
    def __init__(self):
        self.ImplementationVersionName = None

    def ToParams(self):
        tmp = ImplementationVersionNameSubItem()
        tmp.FromParams(self)
        return tmp

class SCP_SCU_RoleSelectionParameters():
    """
    Allows peer AEs to negotiate the roles in which they will serve for each
    SOP Class or Meta SOP Class supported on the Association. This negotiation
    is optional.
    
    The Association Requestor may use one SCP/SCU Role Selection item for each
    SOP Class as identified by its corresponding Abstract Syntax Name and shall
    be one of three role values:
    - Requestor is SCU only
    - Requestor is SCP only
    - Requestor is both SCU/SCP
    
    If the SCP/SCU Role Selection item is absent the default role for a 
    Requestor is SCU and for an Acceptor is SCP
    
    PS3.7 Annex D.3.3.4
    
    Identical for both A-ASSOCIATE-RQ and A-ASSOCIATE-AC
    """
    def __init__(self):
        self.SOPClassUID = None
        self.SCURole = None
        self.SCPRole = None

    def ToParams(self):
        tmp = SCP_SCU_RoleSelectionSubItem()
        tmp.FromParams(self)
        return tmp

class UserIdentityParameters():
    def __init__(self):
        self.UserIdentityType = None
        self.PositiveResponseRequested = None
        self.PrimaryField = None
        self.ServerResponse = None

    def ToParams(self, is_rq):
        if is_rq:
            tmp = UserIdentitySubItemRQ()
        else:
            tmp = UserIdentitySubItemAC()
        tmp.FromParams(self)
        return tmp
