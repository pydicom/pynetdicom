#
# Copyright (c) 2012 Patrice Munger
# This file is part of pynetdicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pynetdicom.googlecode.com


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

from io import StringIO, BytesIO
import logging
from struct import *

from pydicom.uid import UID

from pynetdicom.DULparameters import *
from pynetdicom.utils import wrap_list

logger = logging.getLogger('pynetdicom.pdu')


class PDU:
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
            if not (self.__dict__[ii] == other.__dict__[ii]):
                return False
        
        return True
    
    def encode(self):
        """
        Encode the DUL parameters as binary data according using the required
        format
        
        Returns
        -------
        encoded_data
            The PDU encoded as binary data
        """
        # This is sufficient for most PDUs
        encoded_data = b''
        for (value, fmt) in self.parameters:
            encoded_data += struct.pack(fmt, value)
        
        # A_ASSOCIATE_RQ, A_ASSOCIATE_AC, P_DATA_TF, PresentationContextItemRQ,
        # PresentationContextItemAC, UserInformationItem all have additional 
        # items requiring encoding
        for item in self.additional_items:
            encoded_data += item.encode()
            
        return encoded_data
    
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

    def validate_additional_items(self):
        pass

    def put_parameters(self, parameters):
        pass
        
    def get_parameters(self):
        pass


class A_ASSOCIATE_RQ_PDU(PDU):
    '''This class represents the A-ASSOCIATE-RQ PDU

    The A-ASSOCIATE-RQ PDU is sent at the start of association negotiation when
    either the local or the peer AE wants to to request an association.
    
    This PDU is the first piece of data sent

    See PS3.8 Section 9.3.2 for the structure of the PDU, especially Table 9-11
    for a description of each field
    '''
    def __init__(self):
        # Unsigned byte
        self.PDUType = 0x01
        # Unsigned int
        self.PDULength = None
        # Unsigned short
        self.ProtocolVersion = 1
        # string of length 16
        self.bCalledAETitle = None
        # string of length 16
        self.bCallingAETitle = None
        
        # VariableItems is a list containing the following:
        #   1 ApplicationContextItem
        #   1 or more PresentationContextItemRQ
        #   1 UserInformationItem
        self.VariableItems = []

    def FromParams(self, Params):
        """
        Setup the PDU with the parameter values
        
        Parameters
        ----------
        Params - A_ASSOCIATE_ServiceParameters
            The parameters to use for setting up the PDU
        """
        self.bCallingAETitle = Params.CallingAETitle
        self.bCalledAETitle = Params.CalledAETitle
        
        tmp_app_cont = ApplicationContextItem()
        tmp_app_cont.FromParams(Params.ApplicationContextName)
        self.VariableItems.append(tmp_app_cont)

        # Make presentation contexts
        for ii in Params.PresentationContextDefinitionList:
            tmp_pres_cont = PresentationContextItemRQ()
            tmp_pres_cont.FromParams(ii)
            self.VariableItems.append(tmp_pres_cont)

        # Make user information
        tmp_user_info = UserInformationItem()
        tmp_user_info.FromParams(Params.UserInformationItem)
        self.VariableItems.append(tmp_user_info)

        self.PDULength = 68
        for ii in self.VariableItems:
            self.PDULength = self.PDULength + ii.TotalLength()

    def ToParams(self):
        # Returns an A_ASSOCIATE_ServiceParameters object
        ass = A_ASSOCIATE_ServiceParameters()
        ass.CallingAETitle = self.bCallingAETitle
        ass.CalledAETitle = self.bCalledAETitle
        ass.ApplicationContextName = self.VariableItems[
            0].ApplicationContextName
        # Write presentation contexts
        for ii in self.VariableItems[1:-1]:
            ass.PresentationContextDefinitionList.append(ii.ToParams())
        # Write user information
        ass.UserInformationItem = self.VariableItems[-1].ToParams()
        return ass

    def Encode(self):
        
        logger.debug('Constructing Associate RQ PDU')
        
        # Python3 must implicitly define string as bytes
        tmp = b''
        tmp = tmp + pack('B',   self.PDUType)
        tmp = tmp + pack('B',   0x00)
        tmp = tmp + pack('>I',  self.PDULength)
        tmp = tmp + pack('>H',  self.ProtocolVersion)
        tmp = tmp + pack('>H',  0x00)
        tmp = tmp + pack('16s', bytes(self.bCalledAETitle, 'utf-8'))
        tmp = tmp + pack('16s', bytes(self.bCallingAETitle, 'utf-8'))
        tmp = tmp + pack('>8I', 0, 0, 0, 0, 0, 0, 0, 0)
        
        # variable item elements
        for ii in self.VariableItems:
            tmp = tmp + ii.Encode()
        
        return tmp

    def Decode(self, rawstring):
        s = BytesIO(rawstring)
        
        logger.debug('PDU Type: Associate Request, PDU Length: %s + %s bytes '
                        'PDU header' %(len(s.getvalue()), 6))
        
        for line in wrap_list(s, max_size=512):
            logger.debug('  ' + line)
        
        logger.debug('Parsing an A-ASSOCIATE PDU')
        
        (self.PDUType, 
         _, 
         self.PDULength,
         self.ProtocolVersion, 
         _, 
         self.bCalledAETitle,
         self.bCallingAETitle) = unpack('> B B I H H 16s 16s', s.read(42))
        s.read(32)
        
        
        while 1:
            type = NextType(s)
            
            if type == 0x10:
                tmp = ApplicationContextItem()
            elif type == 0x20:
                tmp = PresentationContextItemRQ()
            elif type == 0x50:
                tmp = UserInformationItem()
            elif type is None:
                break
            else:
                raise #'InvalidVariableItem'
                
            tmp.Decode(s)
            self.VariableItems.append(tmp)

    def TotalLength(self):
        return 6 + self.PDULength

    def __repr__(self):
        tmp = "A-ASSOCIATE-RQ PDU\n"
        tmp = tmp + " PDU type: 0x%02x\n" % self.PDUType
        tmp = tmp + " PDU length: %d\n" % self.PDULength
        tmp = tmp + " Called AE title: %s\n" % self.CalledAETitle
        tmp = tmp + " Calling AE title: %s\n" % self.CallingAETitle
        for ii in self.VariableItems:
            tmp = tmp + ii.__repr__()
        return tmp + "\n"

    @property
    def ApplicationContext(self):
        """
        See PS3.8 9.3.2, 7.1.1.2
        
        Returns
        -------
        pydicom.uid.UID
            The Requestor AE's Application Context Name
        """
        for ii in self.VariableItems:
            if isinstance(ii, ApplicationContextItem):
                return UID(ii.ApplicationContextName.decode('utf-8'))
        
    @property
    def PresentationContext(self):
        """
        See PS3.8 9.3.2, 7.1.1.13
        
        Also sets a SCP and SCU variable for each of the PresentationContextAC 
        instances that can be used to track the SCP/SCU role negotiation. 
        See the PresentationContextItemRQ and documentation for more information
        
        Returns
        -------
        list of pynetdicom.PDU.PresentationContextItemRQ
            The Requestor AE's Presentation Context objects
        """
        contexts = []
        for ii in self.VariableItems[1:]:
            if isinstance(ii, PresentationContextItemRQ):
                # We determine if there are any SCP/SCU Role Negotiations
                #   for each Transfer Syntax in each Presentation Context
                #   and if so we set the SCP and SCU attributes.
                if self.UserInformation.RoleSelection is not None:
                    # Iterate through the role negotiations looking for a 
                    #   SOP Class match to the Abstract Syntaxes
                    for role in self.UserInformation.RoleSelection:
                        for sop_class in ii.AbstractSyntax:
                            if role.SOPClass == sop_class:
                                ii.SCP = role.SCP
                                ii.SCU = role.SCU
                contexts.append(ii)
        return contexts
        
    @property
    def UserInformation(self):
        """
        See PS3.8 9.3.2, 7.1.1.6
        
        Returns
        -------
        pynetdicom.PDU.UserInformationItem
            The Requestor AE's User Information object
        """
        for ii in self.VariableItems[1:]:
            if isinstance(ii, UserInformationItem):
                return ii
 
    @property
    def CalledAETitle(self):
        """
        While the standard says this value should match the A-ASSOCIATE-RQ
        value there is no guarantee and this should not be used as a check
        value
        
        Returns
        -------
        str
            The Requestor's AE Called AE Title
        """
        return self.bCalledAETitle.decode('utf-8')
    
    @property
    def CallingAETitle(self):
        """
        While the standard says this value should match the A-ASSOCIATE-RQ
        value there is no guarantee and this should not be used as a check
        value
        
        Returns
        -------
        str
            The Requestor's AE Calling AE Title
        """
        return self.bCallingAETitle.decode('utf-8')


class A_ASSOCIATE_AC_PDU(PDU):
    '''This class represents the A-ASSOCIATE-AC PDU'''
    def __init__(self):
        self.PDUType = 0x02                                     # Unsigned byte
        self.Reserved1 = 0x00                                   # Unsigned byte
        self.PDULength = None                                   # Unsigned int
        # Unsigned short
        self.ProtocolVersion = 1
        # Unsigned short
        self.Reserved2 = 0x00
        # string of length 16
        self.Reserved3 = None
        # string of length 16
        self.Reserved4 = None
        self.Reserved5 = (0x0000, 0x0000, 0x0000, 0x0000)  # 32 bytes
        # VariablesItems is a list containing the following:
        #   1 ApplicationContextItem
        #   1 or more PresentationContextItemAC
        #   1 UserInformationItem
        self.VariableItems = []
    
    def FromParams(self, Params):
        # Params is an A_ASSOCIATE_ServiceParameters object
        self.Reserved3 = Params.CalledAETitle
        self.Reserved4 = Params.CallingAETitle
        # Make application context
        tmp_app_cont = ApplicationContextItem()
        tmp_app_cont.FromParams(Params.ApplicationContextName)
        self.VariableItems.append(tmp_app_cont)
        # Make presentation contexts
        for ii in Params.PresentationContextDefinitionResultList:
            tmp_pres_cont = PresentationContextItemAC()
            tmp_pres_cont.FromParams(ii)
            self.VariableItems.append(tmp_pres_cont)
        # Make user information
        tmp_user_info = UserInformationItem()
        tmp_user_info.FromParams(Params.UserInformationItem)
        self.VariableItems.append(tmp_user_info)
        # Compute PDU length
        self.PDULength = 68
        for ii in self.VariableItems:
            self.PDULength = self.PDULength + ii.TotalLength()

    def ToParams(self):
        ass = A_ASSOCIATE_ServiceParameters()
        
        # Reserved3 and Reserved4 shouldn't be used like this
        ass.CalledAETitle = self.Reserved3
        ass.CallingAETitle = self.Reserved4
        ass.ApplicationContextName = self.VariableItems[0].ToParams()

        # Write presentation context
        for ii in self.VariableItems[1:-1]:
            ass.PresentationContextDefinitionResultList.append(ii.ToParams())

        # Write user information
        ass.UserInformationItem = self.VariableItems[-1].ToParams()
        ass.Result = 'Accepted'
        return ass

    def Encode(self):
        tmp = b''
        tmp = tmp + pack('B',   self.PDUType)
        tmp = tmp + pack('B',   self.Reserved1)
        tmp = tmp + pack('>I',  self.PDULength)
        tmp = tmp + pack('>H',  self.ProtocolVersion)
        tmp = tmp + pack('>H',  self.Reserved2)
        tmp = tmp + pack('16s', self.Reserved3)
        tmp = tmp + pack('16s', self.Reserved4)
        tmp = tmp + pack('>8I', 0, 0, 0, 0, 0, 0, 0, 0)
        
        # variable item elements
        for ii in self.VariableItems:
            tmp = tmp + ii.Encode()
        return tmp

    def Decode(self, rawstring):
        
        s = BytesIO(rawstring)
        logger.debug('PDU Type: Associate Accept, PDU Length: %s + %s bytes '
                        'PDU header' %(len(s.getvalue()), 6))
        
        for line in wrap_list(s):
            logger.debug('  ' + line)
        
        logger.debug('Parsing an A-ASSOCIATE PDU')
        
        (self.PDUType, 
         self.Reserved1, 
         self.PDULength,
         self.ProtocolVersion, 
         self.Reserved2, 
         self.Reserved3,
         self.Reserved4) = unpack('> B B I H H 16s 16s', s.read(42))
        self.Reserved5 = unpack('>8I', s.read(32))
        
        while 1:
            Type = NextType(s)
            if Type == 0x10:
                tmp = ApplicationContextItem()
            elif Type == 0x21:
                tmp = PresentationContextItemAC()
            elif Type == 0x50:
                tmp = UserInformationItem()
            elif Type is None:
                break
            else:
                raise #'InvalidVariableItem'
            tmp.Decode(s)
            self.VariableItems.append(tmp)

    def TotalLength(self):
        return 6 + self.PDULength

    def __repr__(self):
        tmp = "A-ASSOCIATE-AC PDU\n"
        tmp = tmp + " PDU type: 0x%02x\n" % self.PDUType
        tmp = tmp + " PDU length: %d\n" % self.PDULength
        tmp = tmp + " Called AE title: %s\n" % self.Reserved3
        tmp = tmp + " Calling AE title: %s\n" % self.Reserved4
        for ii in self.VariableItems:
            tmp = tmp + ii.__repr__()
        return tmp + "\n"

    @property
    def ApplicationContext(self):
        """
        See PS3.8 9.3.2, 7.1.1.2
        
        Returns
        -------
        pydicom.uid.UID
            The Acceptor AE's Application Context Name
        """
        for ii in self.VariableItems:
            if isinstance(ii, ApplicationContextItem):
                return UID(ii.ApplicationContextName.decode('utf-8'))
        
    @property
    def PresentationContext(self):
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
        for ii in self.VariableItems[1:]:
            if isinstance(ii, PresentationContextItemAC):
                # We determine if there are any SCP/SCU Role Negotiations
                #   for each Transfer Syntax in each Presentation Context
                #   and if so we set the SCP and SCU attributes
                if self.UserInformation.RoleSelection is not None:
                    # Iterate through the role negotiations looking for a 
                    #   SOP Class match to the Abstract Syntaxes
                    for role in self.UserInformation.RoleSelection:
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
    def UserInformation(self):
        """
        See PS3.8 9.3.2, 7.1.1.6
        
        Returns
        -------
        pynetdicom.PDU.UserInformationItem
            The Acceptor AE's User Information object
        """
        for ii in self.VariableItems[1:]:
            if isinstance(ii, UserInformationItem):
                return ii
        
    @property
    def CalledAETitle(self):
        """
        While the standard says this value should match the A-ASSOCIATE-RQ
        value there is no guarantee and this should not be used as a check
        value
        
        Returns
        -------
        str
            The Requestor's AE Called AE Title
        """
        return self.Reserved3.decode('utf-8')
    
    @property
    def CallingAETitle(self):
        """
        While the standard says this value should match the A-ASSOCIATE-RQ
        value there is no guarantee and this should not be used as a check
        value
        
        Returns
        -------
        str
            The Requestor's AE Calling AE Title
        """
        return self.Reserved4.decode('utf-8')


class A_ASSOCIATE_RJ_PDU(PDU):
    '''This class represents the A-ASSOCIATE-RJ PDU'''
    def __init__(self):
        self.PDUType = 0x03                           # Unsigned byte
        self.PDULength = 0x00000004             # Unsigned int
        self.Result = None                  # Unsigned byte
        self.Source = None                            # Unsigned byte
        self.ReasonDiag = None                      # Unsigned byte

    def FromParams(self, Params):
        # Params is an A_ASSOCIATE_ServiceParameters object
        self.Result = Params.Result
        self.Source = Params.ResultSource
        self.ReasonDiag = Params.Diagnostic

    def ToParams(self):
        tmp = A_ASSOCIATE_ServiceParameters()
        tmp.Result = self.Result
        tmp.ResultSource = self.Source
        tmp.Diagnostic = self.ReasonDiag
        return tmp

    def Encode(self):
        tmp = b''
        tmp = tmp + pack('B', self.PDUType)
        tmp = tmp + pack('B', 0x00)
        tmp = tmp + pack('>I', self.PDULength)
        tmp = tmp + pack('B', 0x00)
        tmp = tmp + pack('B', self.Result)
        tmp = tmp + pack('B', self.Source)
        tmp = tmp + pack('B', self.ReasonDiag)
        return tmp

    def Decode(self, rawstring):
        Stream = BytesIO(rawstring)
        (self.PDUType, 
         _, 
         self.PDULength, 
         _,
         self.Result, 
         self.Source, 
         self.ReasonDiag) = unpack('> B B I B B B B', Stream.read(10))

    def TotalLength(self):
        return 10

    def __repr__(self):
        tmp = "A-ASSOCIATE-RJ PDU\n"
        tmp = tmp + " PDU type: 0x%02x\n" % self.PDUType
        tmp = tmp + " PDU length: %d\n" % self.PDULength
        tmp = tmp + " Result: %d\n" % self.Result
        tmp = tmp + " Source: %s\n" % str(self.Source)
        tmp = tmp + " Reason/Diagnostic: %s\n" % str(self.ReasonDiag)
        return tmp + "\n"

    @property
    def ResultString(self):
        """
        See PS3.8 9.3.4
        
        Returns
        -------
        str
            The type of Association rejection
        """
        if self.Result == 0x01:
            return 'Rejected (Permanent)'
        else:
            return 'Rejected (Transient)'
    
    @property
    def SourceString(self):
        """
        See PS3.8 9.3.4
        
        Returns
        -------
        str
            The source of the Association rejection
        """
        if self.Source == 0x01:
            return 'User'
        elif self.Source == 0x02:
            return 'Provider (ACSE)'
        else:
            return 'Provider (Presentation)'
    
    @property
    def Reason(self):
        """
        See PS3.8 9.3.4
        
        Returns
        -------
        str
            The reason given for the Association rejection
        """
        if self.Source == 0x01:
            reason_str = { 1 : "No reason given",
                           2 : "Application context name not supported",
                           3 : "Calling AE title not recognised",
                           4 : "Reserved",
                           5 : "Reserved",
                           6 : "Reserved",
                           7 : "Called AE title not recognised",
                           8 : "Reserved",
                           9 : "Reserved",
                          10: "Reserved"}
        elif self.Source == 0x02:
            reason_str = { 1 : "No reason given",
                           2 : "Protocol version not supported"}
        else:
            reason_str = { 0 : "Reserved",
                           1 : "Temporary congestion",
                           2 : "Local limit exceeded",
                           3 : "Reserved",
                           4 : "Reserved",
                           5 : "Reserved",
                           6 : "Reserved",
                           7 : "Reserved"}
        return reason_str[self.ReasonDiag]
                          

class P_DATA_TF_PDU(PDU):
    '''This class represents the P-DATA-TF PDU'''
    def __init__(self):
        self.PDUType = 0x04                     # Unsigned byte
        self.PDULength = None                   # Unsigned int
        # List of one of more PresentationDataValueItem
        self.PresentationDataValueItems = []

    def FromParams(self, Params):
        # Params is an P_DATA_ServiceParameters object
        for ii in Params.PresentationDataValueList:
            tmp = PresentationDataValueItem()
            tmp.FromParams(ii)
            self.PresentationDataValueItems.append(tmp)
        self.PDULength = 0
        for ii in self.PresentationDataValueItems:
            self.PDULength = self.PDULength + ii.TotalLength()

    def ToParams(self):
        tmp = P_DATA_ServiceParameters()
        tmp.PresentationDataValueList = []
        for ii in self.PresentationDataValueItems:
            tmp.PresentationDataValueList.append([ii.PresentationContextID,
                                                  ii.PresentationDataValue])
        return tmp

    def Encode(self):
        tmp = b''
        tmp = tmp + pack('B', self.PDUType)
        tmp = tmp + pack('B', 0x00)
        tmp = tmp + pack('>I', self.PDULength)
        
        for ii in self.PresentationDataValueItems:
            tmp = tmp + ii.Encode()
        return tmp

    def Decode(self, rawstring):
        Stream = BytesIO(rawstring)
        
        (self.PDUType, 
         _,
         self.PDULength) = unpack('> B B I', Stream.read(6))
        
        length_read = 0
        while length_read != self.PDULength:
            tmp = PresentationDataValueItem()
            tmp.Decode(Stream)
            length_read = length_read + tmp.TotalLength()
            self.PresentationDataValueItems.append(tmp)

    def TotalLength(self):
        return 6 + self.PDULength

    def __repr__(self):
        tmp = "P-DATA-TF PDU\n"
        tmp = tmp + " PDU type: 0x%02x\n" % self.PDUType
        tmp = tmp + " PDU length: %d\n" % self.PDULength
        for ii in self.PresentationDataValueItems:
            tmp = tmp + ii.__repr__()
        return tmp + "\n"

    @property
    def PDVs(self):
        return self.PresentationDataValueItems


class A_RELEASE_RQ_PDU(PDU):
    '''This class represents the A-ASSOCIATE-RQ PDU'''
    def __init__(self):
        self.PDUType = 0x05                     # Unsigned byte
        self.PDULength = 0x00000004         # Unsigned int

    def FromParams(self, Params=None):
        # Params is an A_RELEASE_ServiceParameters object. It is optional.
        # nothing to do
        pass

    def ToParams(self):
        tmp = A_RELEASE_ServiceParameters()
        #tmp.Reason = 'normal'
        tmp.Result = 'affirmative'
        #return A_RELEASE_ServiceParameters()
        return tmp
        
    def Encode(self):
        tmp = b''
        tmp = tmp + pack('B', self.PDUType)
        tmp = tmp + pack('B', 0x00)
        tmp = tmp + pack('>I', self.PDULength)
        tmp = tmp + pack('>I', 0x00000000)
        return tmp

    def Decode(self, rawstring):
        Stream = BytesIO(rawstring)
        
        (self.PDUType, 
         _,
         self.PDULength, 
         _) = unpack('> B B I I', Stream.read(10))

    def TotalLength(self):
        return 10

    def __repr__(self):
        tmp = "A-RELEASE-RQ PDU\n"
        tmp = tmp + " PDU type: 0x%02x\n" % self.PDUType
        tmp = tmp + " PDU length: %d\n" % self.PDULength
        return tmp + "\n"


class A_RELEASE_RP_PDU(PDU):
    '''This class represents the A-RELEASE-RP PDU'''
    def __init__(self):
        self.PDUType = 0x06                     # Unsigned byte
        self.PDULength = 0x00000004         # Unsigned int

    def FromParams(self, Params=None):
        # Params is an A_RELEASE_ServiceParameters object. It is optional.
        # nothing to do
        pass

    def ToParams(self):
        tmp = A_RELEASE_ServiceParameters()
        #tmp.Reason = 'normal'
        tmp.Result = 'affirmative'
        return tmp
        

    def Encode(self):
        tmp = b''
        tmp = tmp + pack('B', self.PDUType)
        tmp = tmp + pack('B', 0x00)
        tmp = tmp + pack('>I', self.PDULength)
        tmp = tmp + pack('>I', 0x00000000)
        return tmp

    def Decode(self, rawstring):
        Stream = BytesIO(rawstring)
        
        (self.PDUType, 
         _,
         self.PDULength, 
         _) = unpack('> B B I I', Stream.read(10))

    def TotalLength(self):
        return 10

    def __repr__(self):
        tmp = "A-RELEASE-RP PDU\n"
        tmp = tmp + " PDU type: 0x%02x\n" % self.PDUType
        tmp = tmp + " PDU length: %d\n" % self.PDULength
        return tmp + "\n"


class A_ABORT_PDU(PDU):
    """
    This class represents the A-ABORT PDU
    """
    def __init__(self):
        self.PDUType = 0x07
        self.PDULength = 0x00000004
        self.AbortSource = None
        self.ReasonDiag = None

    def FromParams(self, Params):
        # Params can be an A_ABORT_ServiceParamters or A_P_ABORT_ServiceParamters
        # object.
        if Params.__class__ == A_ABORT_ServiceParameters:
            # User initiated abort
            self.ReasonDiag = 0
            self.AbortSource = Params.AbortSource
        elif Params.__class__ == A_P_ABORT_ServiceParameters:
            # User provider initiated abort
            self.AbortSource = Params.AbortSource
            self.ReasonDiag = None

    def ToParams(self):
        # Returns either a A-ABORT of an A-P-ABORT
        if self.AbortSource is not None:
            tmp = A_ABORT_ServiceParameters()
            tmp.AbortSource = self.AbortSource
        elif self.ReasonDiag is not None:
            tmp = A_P_ABORT_ServiceParameters()
            tmp.ProviderReason = self.ReasonDiag
        return tmp

    def Encode(self):
        tmp = b''
        tmp = tmp + pack('B', 0x07)
        tmp = tmp + pack('B', 0x00)
        tmp = tmp + pack('>I', 0x00000004)
        tmp = tmp + pack('B', 0x00)
        tmp = tmp + pack('B', 0x00)
        tmp = tmp + pack('B', self.AbortSource)
        tmp = tmp + pack('B', self.ReasonDiag)
        return tmp

    def Decode(self, rawstring):
        Stream = BytesIO(rawstring)
        
        (self.PDUType, 
         _, 
         self.PDULength, 
         _,
         _, 
         self.AbortSource, 
         self.ReasonDiag) = unpack('> B B I B B B B', Stream.read(10))

    def TotalLength(self):
        return 10

    def __repr__(self):
        tmp = "A-ABORT PDU\n"
        tmp = tmp + " PDU type: 0x%02x\n" % self.PDUType
        tmp = tmp + " PDU length: %d\n" % self.PDULength
        tmp = tmp + " Abort Source: %d\n" % self.AbortSource
        tmp = tmp + " Reason/Diagnostic: %d\n" % self.ReasonDiag
        return tmp + "\n"

    @property
    def Source(self):
        """
        See PS3.8 9.3.8
        
        Returns
        -------
        str
            The source of the Association abort
        """
        if self.AbortSource == 0x00:
            return 'DUL User'
        elif self.AbortSource == 0x01:
            return 'Reserved'
        else:
            return 'DUL Provider'
    
    @property
    def Reason(self):
        """
        See PS3.8 9.3.8
        
        Returns
        -------
        str
            The reason given for the Association abort
        """
        if self.Source == 0x02:
            reason_str = { 0 : "No reason given",
                           1 : "Unrecognised PDU",
                           2 : "Unexpected PDU",
                           3 : "Reserved",
                           4 : "Unrecognised PDU parameter",
                           5 : "Unexpected PDU parameter",
                           6 : "Invalid PDU parameter value"}
            return reason_str[self.ReasonDiag]
        else:
            return 'No reason given'


# Items and sub-items classes
class ApplicationContextItem(PDU):
    """
    The Application Context Name identifies the application context 
    proposed by the requestor. An application context is an explicitly defined
    set of application service elements, related options, and any other 
    information necessary for the interworking of application entities on an
    association.
    
    Used in: A_ASSOCIATE_RQ, A_ASSOCIATE_AC
    """
    def __init__(self):
        # Unsigned byte
        self.ItemType = 0x10
        # Unsigned short
        self.ItemLength = None
        # String
        self.ApplicationContextName = None

    def FromParams(self, params):
        self.ApplicationContextName = params
        self.ItemLength = len(self.ApplicationContextName)

    def ToParams(self):
        return self.ApplicationContextName

    def Encode(self):
        tmp = b''
        tmp = tmp + pack('B', self.ItemType)
        tmp = tmp + pack('B', 0x00)
        tmp = tmp + pack('>H', self.ItemLength)
        tmp = tmp + self.ApplicationContextName
        return tmp

    def Decode(self, Stream):
        (self.ItemType, 
         _,
         self.ItemLength) = unpack('> B B H', Stream.read(4))
        
        self.ApplicationContextName = Stream.read(self.ItemLength)

    def TotalLength(self):
        return 4 + self.ItemLength

    def __repr__(self):
        tmp = " Application context item\n"
        tmp = tmp + "  Item type: 0x%02x\n" % self.ItemType
        tmp = tmp + "  Item length: %d\n" % self.ItemLength
        tmp = tmp + \
            "  Presentation context ID: %s\n" % self.ApplicationContextName
        return tmp

class PresentationContextItemRQ(PDU):
    """
    Attributes
    ----------
    SCP - None or int
        Defaults to None if SCP/SCU role negotiation not used, 0 or 1 if used
    SCU - None or int
        Defaults to None if SCP/SCU role negotiation not used, 0 or 1 if used
    """
    def __init__(self):
        # Unsigned byte
        self.ItemType = 0x20
        # Unsigned short
        self.ItemLength = None
        # Unsigned byte
        self.PresentationContextID = None
        
        # Use for tracking SCP/SCU Role Negotiation
        self.SCP = None
        self.SCU = None
        
        # AbstractTransferSyntaxSubItems is a list
        # containing the following elements:
        #   One AbstractSyntaxtSubItem
        #   One or more TransferSyntaxSubItem
        self.AbstractTransferSyntaxSubItems = []

    def FromParams(self, Params):
        # Params is a list of the form [ID, AbstractSyntaxName,
        # [TransferSyntaxNames]]
        self.PresentationContextID = Params[0]
        tmp_abs_syn = AbstractSyntaxSubItem()
        tmp_abs_syn.FromParams(Params[1])
        self.AbstractTransferSyntaxSubItems.append(tmp_abs_syn)
        for ii in Params[2]:
            tmp_tr_syn = TransferSyntaxSubItem()
            tmp_tr_syn.FromParams(ii)
            self.AbstractTransferSyntaxSubItems.append(tmp_tr_syn)
        self.ItemLength = 4
        for ii in self.AbstractTransferSyntaxSubItems:
            self.ItemLength = self.ItemLength + ii.TotalLength()

    def ToParams(self):
        # Returns a list of the form [ID, AbstractSyntaxName,
        # [TransferSyntaxNames]]
        tmp = [None, None, []]
        tmp[0] = self.PresentationContextID
        tmp[1] = self.AbstractTransferSyntaxSubItems[0].ToParams()
        for ii in self.AbstractTransferSyntaxSubItems[1:]:
            tmp[2].append(ii.ToParams())
        return tmp

    def Encode(self):
        tmp = b''
        tmp = tmp + pack('B', self.ItemType)
        tmp = tmp + pack('B', 0x00)
        tmp = tmp + pack('>H', self.ItemLength)
        tmp = tmp + pack('B', self.PresentationContextID)
        tmp = tmp + pack('B', 0x00)
        tmp = tmp + pack('B', 0x00)
        tmp = tmp + pack('B', 0x00)
        
        for ii in self.AbstractTransferSyntaxSubItems:
            tmp = tmp + ii.Encode()
        return tmp

    def Decode(self, Stream):
        (self.ItemType, 
         _, 
         self.ItemLength,
         self.PresentationContextID, 
         _, 
         _,
         _) = unpack('> B B H B B B B', Stream.read(8))
        
        tmp = AbstractSyntaxSubItem()
        tmp.Decode(Stream)
        self.AbstractTransferSyntaxSubItems.append(tmp)
        NextItemType = NextType(Stream)
        
        while NextItemType == 0x40:
            tmp = TransferSyntaxSubItem()
            tmp.Decode(Stream)
            self.AbstractTransferSyntaxSubItems.append(tmp)
            NextItemType = NextType(Stream)

    def TotalLength(self):
        return 4 + self.ItemLength

    def __repr__(self):
        tmp = " Presentation context RQ item\n"
        tmp = tmp + "  Item type: 0x%02x\n" % self.ItemType
        tmp = tmp + "  Item length: %d\n" % self.ItemLength
        tmp = tmp + \
            "  Presentation context ID: %d\n" % self.PresentationContextID
        for ii in self.AbstractTransferSyntaxSubItems:
            tmp = tmp + ii.__repr__()
        return tmp

    @property
    def ID(self):
        """
        See PS3.8 9.3.2.2
        
        Returns
        -------
        int
            Odd number between 1 and 255 (inclusive)
        """
        return self.PresentationContextID

    @property
    def AbstractSyntax(self):
        """
        See PS3.8 9.3.2.2
        
        Returns
        -------
        pydicom.uid.UID
            The Requestor AE's Presentation Context item's Abstract Syntax
        """
        for ii in self.AbstractTransferSyntaxSubItems:
            if isinstance(ii, AbstractSyntaxSubItem):
                return UID(ii.AbstractSyntaxName.decode('utf-8'))
                
    @property
    def TransferSyntax(self):
        """
        See PS3.8 9.3.2.2
        
        Returns
        -------
        list of pydicom.uid.UID
            The Requestor AE's Presentation Context item's Transfer Syntax(es)
        """
        syntaxes = []
        for ii in self.AbstractTransferSyntaxSubItems:
            if isinstance(ii, TransferSyntaxSubItem):
                syntaxes.append( UID(ii.TransferSyntaxName.decode('utf-8')) )
                
        return syntaxes

class PresentationContextItemAC(PDU):
    """
    Attributes
    ----------
    SCP - None or int
        Defaults to None if SCP/SCU role negotiation not used, 0 or 1 if used
    SCU - None or int
        Defaults to None if SCP/SCU role negotiation not used, 0 or 1 if used
    """
    def __init__(self):
        self.ItemType = 0x21                        # Unsigned byte
        self.ItemLength = None                  # Unsigned short
        self.PresentationContextID = None   # Unsigned byte
        self.ResultReason = None                # Unsigned byte
        self.TransferSyntaxSubItem = None   # TransferSyntaxSubItem object

        # Use for tracking SCP/SCU Role Negotiation
        self.SCP = None
        self.SCU = None

    def FromParams(self, Params):
        # Params is a list of the form [ID, Response, TransferSyntax].
        self.PresentationContextID = Params[0]
        self.ResultReason = Params[1]
        self.TransferSyntaxSubItem = TransferSyntaxSubItem()
        self.TransferSyntaxSubItem.FromParams(Params[2])
        self.ItemLength = 4 + self.TransferSyntaxSubItem.TotalLength()

    def ToParams(self):
        # Returns a list of the form [ID, Response, TransferSyntax].
        tmp = [None, None, None]
        tmp[0] = self.PresentationContextID
        tmp[1] = self.ResultReason
        tmp[2] = self.TransferSyntaxSubItem.ToParams()
        return tmp

    def Encode(self):
        tmp = b''
        tmp = tmp + pack('B', self.ItemType)
        tmp = tmp + pack('B', 0x00)
        tmp = tmp + pack('>H', self.ItemLength)
        tmp = tmp + pack('B', self.PresentationContextID)
        tmp = tmp + pack('B', 0x00)
        tmp = tmp + pack('B', self.ResultReason)
        tmp = tmp + pack('B', 0x00)
        tmp = tmp + self.TransferSyntaxSubItem.Encode()
        return tmp

    def Decode(self, Stream):
        (self.ItemType, 
         _, 
         self.ItemLength,
         self.PresentationContextID, 
         _, 
         self.ResultReason,
         _) = unpack('> B B H B B B B', Stream.read(8))
        
        self.TransferSyntaxSubItem = TransferSyntaxSubItem()
        self.TransferSyntaxSubItem.Decode(Stream)

    def TotalLength(self):
        return 4 + self.ItemLength

    def __repr__(self):
        tmp = " Presentation context AC item\n"
        tmp = tmp + "  Item type: 0x%02x\n" % self.ItemType
        tmp = tmp + "  Item length: %d\n" % self.ItemLength
        tmp = tmp + \
            "  Presentation context ID: %d\n" % self.PresentationContextID
        tmp = tmp + "  Result/Reason: %d\n" % self.ResultReason
        tmp = tmp + self.TransferSyntaxSubItem.__repr__()
        return tmp

    @property
    def ID(self):
        """
        See PS3.8 9.3.2.2
        
        Returns
        -------
        int
            Odd number between 1 and 255 (inclusive)
        """
        return self.PresentationContextID

    @property
    def Result(self):
        """
        Returns
        -------
        str
            The Acceptor AE's Presentation Context item's acceptance Result 
        """
        result_options = {0 : 'Accepted', 
                          1 : 'User Rejection', 
                          2 : 'Provider Rejection',
                          3 : 'Provider Rejection',
                          4 : 'Provider Rejection'} 
        return result_options[self.ResultReason]

    @property
    def TransferSyntax(self):
        """
        See PS3.8 9.3.2.2
        
        Returns
        -------
        pydicom.uid.UID
            The Acceptor AE's Presentation Context item's accepted Transfer 
            Syntax. The UID instance has been extended with two variables
            for tracking if SCP/SCU role negotiation has been accepted:
            pydicom.uid.UID.SCP: Defaults to None if not used, 0 or 1 if used
            pydicom.uid.UID.SCU: Defaults to None if not used, 0 or 1 if used
        """
        ts_uid = self.TransferSyntaxSubItem.TransferSyntaxName
        return ts_uid

class AbstractSyntaxSubItem(PDU):
    def __init__(self):
        self.ItemType = 0x30                            # Unsigned byte
        self.ItemLength = None                      # Unsigned short
        self.AbstractSyntaxName = None        # String

    def FromParams(self, Params):
        # Params is a string
        self.AbstractSyntaxName = Params
        self.ItemLength = len(self.AbstractSyntaxName)

    def ToParams(self):
        # Retruns the abstract syntax name
        return self.AbstractSyntaxName

    def Encode(self):
        tmp = b''
        tmp = tmp + pack('B', self.ItemType)
        tmp = tmp + pack('B', 0x00)
        tmp = tmp + pack('>H', self.ItemLength)
        tmp = tmp + bytes(self.AbstractSyntaxName, 'utf-8')
        return tmp

    def Decode(self, Stream):
        (self.ItemType, 
         _,
         self.ItemLength) = unpack('> B B H', Stream.read(4))
        self.AbstractSyntaxName = Stream.read(self.ItemLength)

    def TotalLength(self):
        return 4 + self.ItemLength

    def __repr__(self):
        tmp = "  Abstract syntax sub item\n"
        tmp = tmp + "   Item type: 0x%02x\n" % self.ItemType
        tmp = tmp + "   Item length: %d\n" % self.ItemLength
        tmp = tmp + "   Abstract syntax name: %s\n" % self.AbstractSyntaxName
        return tmp

class TransferSyntaxSubItem(PDU):
    def __init__(self):
        self.ItemType = 0x40                            # Unsigned byte
        self.ItemLength = None                      # Unsigned short
        self.TransferSyntaxName = None          # String

    def FromParams(self, Params):
        # Params is a string.
        self.TransferSyntaxName = Params
        self.ItemLength = len(self.TransferSyntaxName)

    def ToParams(self):
        # Returns the transfer syntax name
        return self.TransferSyntaxName

    def Encode(self):
        tmp = b''
        tmp = tmp + pack('B', self.ItemType)
        tmp = tmp + pack('B', 0x00)
        tmp = tmp + pack('>H', self.ItemLength)
        tmp = tmp + bytes(self.TransferSyntaxName, 'utf-8')
        return tmp

    def Decode(self, Stream):
        (self.ItemType, 
         _,
         self.ItemLength) = unpack('> B B H', Stream.read(4))
        self.TransferSyntaxName = Stream.read(self.ItemLength)

    def TotalLength(self):
        return 4 + self.ItemLength

    def __repr__(self):
        tmp = "  Transfer syntax sub item\n"
        tmp = tmp + "   Item type: 0x%02x\n" % self.ItemType
        tmp = tmp + "   Item length: %d\n" % self.ItemLength
        tmp = tmp + "   Transfer syntax name: %s\n" % self.TransferSyntaxName
        return tmp


class UserInformationItem(PDU):
    def __init__(self):
        # Unsigned byte
        self.ItemType = 0x50
        # Unsigned short
        self.ItemLength = None
        #  UserData is a list containing the following:
        #  1 MaximumLengthItem
        #  0 or more raw strings encoding user data items
        # List  of subitems
        self.UserData = []

    def FromParams(self, Params):
        # Params is a UserData
        for ii in Params:
            self.UserData.append(ii.ToParams())
        self.ItemLength = 0
        for ii in self.UserData:
            self.ItemLength = self.ItemLength + ii.TotalLength()

    def ToParams(self):
        tmp = []
        for ii in self.UserData:
            tmp.append(ii.ToParams())
        return tmp

    def Encode(self):
        tmp = b''
        tmp = tmp + pack('B', self.ItemType)
        tmp = tmp + pack('B', 0x00)
        tmp = tmp + pack('>H', self.ItemLength)
        
        for ii in self.UserData:
            tmp += ii.Encode()
        return tmp

    def Decode(self, Stream):
        (self.ItemType, 
         _,
         self.ItemLength) = unpack('> B B H', Stream.read(4))
        # read the rest of user info
        self.UserData = []
        while NextSubItemType(Stream) is not None:
            tmp = NextSubItemType(Stream)()
            tmp.Decode(Stream)
            self.UserData.append(tmp)

    def TotalLength(self):
        return 4 + self.ItemLength

    def __repr__(self):
        tmp = " User information item\n"
        tmp = tmp + "  Item type: 0x%02x\n" % self.ItemType
        tmp = tmp + "  Item length: %d\n" % self.ItemLength
        tmp = tmp + "  User Data:\n "
        if len(self.UserData) > 1:
            tmp = tmp + str(self.UserData[0])
            for ii in self.UserData[1:]:
                tmp = tmp + "   User Data Item: " + str(ii) + "\n"
        return tmp

    @property
    def MaximumLength(self):
        """
        See PS3.7 D3.3.1, PS3.8 Annex D.1
        
        Mandatory
        
        Returns
        -------
        int
            Association Requestor's MaximumLengthReceived
        """
        for ii in self.UserData:
            if isinstance(ii, MaximumLengthSubItem):
                return ii.MaximumLengthReceived
        
    @property
    def ImplementationClassUID(self):
        """
        See PS3.7 D3.3.2
        
        Mandatory
        
        Returns
        -------
        pydicom.uid.UID
            Association Requestor's ImplementationClassUID
        """
        for ii in self.UserData:
            if isinstance(ii, ImplementationClassUIDSubItem):
                return UID(ii.ImplementationClassUID.decode('utf-8'))
    
    @property
    def ImplementationVersionName(self):
        """
        See PS3.7 D3.3.2
        
        Optional
        
        Returns
        -------
        str
            Association Requestor's ImplementationVersionName or '' if not available
        """
        # Optional
        for ii in self.UserData:
            if isinstance(ii, ImplementationVersionNameSubItem):
                return ii.ImplementationVersionName.decode('utf-8')
        
        return ''
    
    @property
    def MaximumOperationsInvoked(self):
        """
        See PS3.7 D3.3.3
        
        Optional
        
        Returns
        -------
        int
            Association Requestor's MaximumOperationsInvoked
        """
        for ii in self.UserData:
            if isinstance(ii, AsynchronousOperationsWindowSubItem):
                return ii.MaximumNumberOperationsInvoked
    
    @property
    def MaximumOperationsPerformed(self):
        """
        See PS3.7 D3.3.3
        
        Optional
        
        Returns
        -------
        int
            Association Requestor's MaximumOperationsPerformed
        """
        for ii in self.UserData:
            if isinstance(ii, AsynchronousOperationsWindowSubItem):
                return ii.MaximumNumberOperationsPerformed
        
    @property
    def RoleSelection(self):
        """
        See PS3.7 D3.3.4
        
        Optional
        
        Returns
        -------
        list of pynetdicom.PDU.SCP_SCU_RolesSelectionSubItem
            A list of the Association Requestor's Role Selection sub item objects
        """
        roles = []
        for ii in self.UserData:
            if isinstance(ii, SCP_SCU_RoleSelectionSubItem):
                roles.append(ii)
        return roles
        
    @property
    def ExtendedNegotiation(self):
        """
        See PS3.7 D3.3.5
        
        Optional
        
        Raises
        -------
        NotImplementedError
        """
        raise NotImplementedError()
        
    @property
    def CommonExtendedNegotiation(self):
        """
        See PS3.7 D3.3.6
        
        Optional
        
        Raises
        -------
        NotImplementedError
        """
        raise NotImplementedError()
        
    @property
    def UserIdentity(self):
        """
        See PS3.7 D3.3.7
        
        Optional
        
        Returns
        -------
        pynetdicom.PDU.UserIdentityItem
            The Requestor AE's User Identity object if available, None otherwise
        """
        for ii in self.UserData:
            if isinstance(ii, UserIdentitySubItemRQ):
                return ii
            elif isinstance(ii, UserIdentitySubItemAC):
                return ii
        
        return None


class MaximumLengthParameters(PDU):
    def __init__(self):
        self.MaximumLengthReceived = None

    def ToParams(self):
        tmp = MaximumLengthSubItem()
        tmp.FromParams(self)
        return tmp

    def __eq__(self, other):
        return self.MaximumLengthReceived == other.MaximumLengthReceived

class MaximumLengthSubItem(PDU):
    def __init__(self):
        self.ItemType = 0x51                        # Unsigned byte
        self.ItemLength = 0x0004                # Unsigned short
        self.MaximumLengthReceived = None   # Unsigned int

    def FromParams(self, Params):
        self.MaximumLengthReceived = Params.MaximumLengthReceived

    def ToParams(self):
        tmp = MaximumLengthParameters()
        tmp.MaximumLengthReceived = self.MaximumLengthReceived
        return tmp

    def Encode(self):
        tmp = b''
        tmp = tmp + pack('B', self.ItemType)
        tmp = tmp + pack('B', 0x00)
        tmp = tmp + pack('>H', self.ItemLength)
        tmp = tmp + pack('>I', self.MaximumLengthReceived)
        return tmp

    def Decode(self, Stream):
        (self.ItemType, 
         _,
         self.ItemLength, 
         self.MaximumLengthReceived) = unpack('> B B H I', Stream.read(8))

    def TotalLength(self):
        return 0x08

    def __repr__(self):
        tmp = "  Maximum length sub item\n"
        tmp = tmp + "    Item type: 0x%02x\n" % self.ItemType
        tmp = tmp + "    Item length: %d\n" % self.ItemLength
        tmp = tmp + \
            "    Maximum Length Received: %d\n" % self.MaximumLengthReceived
        return tmp

class PresentationDataValueItem(PDU):
    def __init__(self):
        self.ItemLength = None                      # Unsigned int
        self.PresentationContextID = None       # Unsigned byte
        self.PresentationDataValue = None       # String

    def FromParams(self, Params):
        # Takes a PresentationDataValue object
        self.PresentationContextID = Params[0]
        self.PresentationDataValue = Params[1]
        self.ItemLength = 1 + len(self.PresentationDataValue)

    def ToParams(self):
        # Returns a PresentationDataValue
        tmp = PresentationDataValue()
        tmp.PresentationContextID = self.PresentationContextID
        tmp.PresentationDataValue = self.PresentationDataValue

    def Encode(self):
        tmp = b''
        tmp = tmp + pack('>I', self.ItemLength)
        tmp = tmp + pack('B', self.PresentationContextID)
        tmp = tmp + self.PresentationDataValue
        return tmp

    def Decode(self, Stream):
        (self.ItemLength, 
         self.PresentationContextID) = unpack('> I B', Stream.read(5))
        # Presentation data value is left in raw string format.
        # The Application Entity is responsible for dealing with it.
        self.PresentationDataValue = Stream.read(int(self.ItemLength) - 1)

    def TotalLength(self):
        return 4 + self.ItemLength

    def __repr__(self):
        tmp = " Presentation value data item\n"
        tmp = tmp + "  Item length: %d\n" % self.ItemLength
        tmp = tmp + \
            "  Presentation context ID: %d\n" % self.PresentationContextID
        tmp = tmp + \
            "  Presentation data value: %s ...\n" % self.PresentationDataValue[
                :20]
        return tmp
        
    @property
    def ID(self):
        """
        See PS3.8 9.3.5
        
        Returns
        -------
        int
            The Presentation Context ID (odd number 1 to 255)
        """
        return self.PresentationContextID
    
    @property
    def MessageControlHeader(self):
        """
        See PS3.8 9.3.5
        
        Returns
        -------
        str
            The value of the Message Control Header byte formatted as an 8-bit
            binary
        """
        return "{:08b}".format(self.PresentationDataValue[0])
    
    @property
    def Value(self, bytes_per_line=16, delimiter='  ', max_size=512):
        """
        See PS3.8 9.3.5
        
        Parameters
        ----------
        bytes_per_line - int, optional
            The number of bytes to per line
        max_size - int, optional
            The total number of bytes to return
        delimiter - str, optional
            The delimiter of the bytes
        
        Returns
        -------
        list of str
            The first N bytes of the PDV formatted as a list of hex strings
            with M bytes per line
        """
        str_list = wrap_list(self.PresentationDataValue, 
                             items_per_line=bytes_per_line, 
                             delimiter=delimiter, 
                             max_size=max_size)
        return str_list
    
    @property
    def Length(self):
        """
        Returns
        -------
        int
            The length of the PDV in bytes
        """
        return  self.TotalLength()

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

    def TotalLength(self):
        return 4 + self.ItemLength

    def __repr__(self):
        tmp = "User data item\n"
        tmp = tmp + "  Item type: %d\n" % self.ItemType
        tmp = tmp + "  Item length: %d\n" % self.ItemLength
        if len(self.UserData) > 1:
            tmp = tmp + "  User data: %s ...\n" % self.UserData[:10]
        return tmp

# Extended association stuff: Defined in part 3.7
class ImplementationClassUIDParameters:

    def __init__(self):
        self.ImplementationClassUID = None

    def ToParams(self):
        tmp = ImplementationClassUIDSubItem()
        tmp.FromParams(self)
        return tmp

class ImplementationClassUIDSubItem:

    def __init__(self):
        self.ItemType = 0x52                                # Unsigned byte
        # Unsigned byte 0x00
        self.Reserved = 0x00
        self.ItemLength = None                          # Unsigned short
        self.ImplementationClassUID = None          # String

    def FromParams(self, Params):
        self.ImplementationClassUID = Params.ImplementationClassUID
        self.ItemLength = len(self.ImplementationClassUID)

    def ToParams(self):
        tmp = ImplementationClassUIDParameters()
        tmp.ImplementationClassUID = self.ImplementationClassUID
        return tmp

    def Encode(self):
        tmp = b''
        tmp = tmp + pack('B', self.ItemType)
        tmp = tmp + pack('B', self.Reserved)
        tmp = tmp + pack('>H', self.ItemLength)
        tmp = tmp + self.ImplementationClassUID
        return tmp

    def Decode(self, Stream):
        (self.ItemType, self.Reserved,
         self.ItemLength) = unpack('> B B H', Stream.read(4))
        self.ImplementationClassUID = Stream.read(self.ItemLength)

    def TotalLength(self):
        return 4 + self.ItemLength

    def __repr__(self):
        tmp = "  Implementation class UID sub item\n"
        tmp = tmp + "   Item type: 0x%02x\n" % self.ItemType
        tmp = tmp + "   Item length: %d\n" % self.ItemLength
        tmp = tmp + \
            "   SOP class UID length: %s\n" % self.ImplementationClassUID
        return tmp

class ImplementationVersionNameParameters:

    def __init__(self):
        self.ImplementationVersionName = None

    def ToParams(self):
        tmp = ImplementationVersionNameSubItem()
        tmp.FromParams(self)
        return tmp

class ImplementationVersionNameSubItem:

    def __init__(self):
        self.ItemType = 0x55                                # Unsigned byte
        # Unsigned byte 0x00
        self.Reserved = 0x00
        self.ItemLength = None                          # Unsigned short
        self.ImplementationVersionName = None       # String

    def FromParams(self, Params):
        self.ImplementationVersionName = Params.ImplementationVersionName
        self.ItemLength = len(self.ImplementationVersionName)

    def ToParams(self):
        tmp = ImplementationVersionNameParameters()
        tmp.ImplementationVersionName = self.ImplementationVersionName
        return tmp

    def Encode(self):
        tmp = b''
        tmp = tmp + pack('B', self.ItemType)
        tmp = tmp + pack('B', self.Reserved)
        tmp = tmp + pack('>H', self.ItemLength)
        tmp = tmp + self.ImplementationVersionName
        return tmp

    def Decode(self, Stream):
        (self.ItemType, self.Reserved,
         self.ItemLength) = unpack('> B B H', Stream.read(4))
        self.ImplementationVersionName = Stream.read(self.ItemLength)

    def TotalLength(self):
        return 4 + self.ItemLength

    def __repr__(self):
        tmp = "  Implementation version name sub item\n"
        tmp = tmp + "   Item type: 0x%02x\n" % self.ItemType
        tmp = tmp + "   Item length: %d\n" % self.ItemLength
        tmp = tmp + \
            "   SOP class UID length: %s\n" % self.ImplementationVersionName
        return tmp

class AsynchronousOperationsWindowSubItem:

    def __init__(self):
        # Unsigned byte
        self.ItemType = 0x53
        # Unsigned byte
        self.Reserved = 0x00
        # Unsigned short
        self.ItemLength = 0x0004
        self.MaximumNumberOperationsInvoked = None          # Unsigned short
        # Unsigned short
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
        tmp = tmp + pack('B', self.Reserved)
        tmp = tmp + pack('>H', self.ItemLength)
        tmp = tmp + pack('>H', self.MaximumNumberOperationsInvoked)
        tmp = tmp + pack('>H', self.MaximumNumberOperationsPerformed)
        return tmp

    def Decode(self, Stream):
        (self.ItemType, self.Reserved, self.ItemLength,
         self.MaximumNumberOperationsInvoked,
         self.MaximumNumberOperationsPerformed) = unpack('> B B H H H',
                                                                Stream.read(8))

    def TotalLength(self):
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

class SCP_SCU_RoleSelectionParameters:
    def __init__(self):
        self.SOPClassUID = None
        self.SCURole = None
        self.SCPRole = None

    def ToParams(self):
        tmp = SCP_SCU_RoleSelectionSubItem()
        tmp.FromParams(self)
        return tmp

class SCP_SCU_RoleSelectionSubItem:
    def __init__(self):
        self.ItemType = 0x54            # Unsigned byte
        self.Reserved = 0x00            # Unsigned byte 0x00
        self.ItemLength = None          # Unsigned short
        self.UIDLength = None           # Unsigned short
        self.SOPClassUID = None         # String
        self.SCURole = None         # Unsigned byte
        self.SCPRole = None         # Unsigned byte

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
        tmp += pack('B', self.Reserved)
        tmp += pack('>H', self.ItemLength)
        tmp += pack('>H', self.UIDLength)
        tmp += bytes(self.SOPClassUID, 'utf-8')
        tmp += pack('B B', self.SCURole, self.SCPRole)
        return tmp

    def Decode(self, Stream):
        (self.ItemType, 
         self.Reserved,
         self.ItemLength, 
         self.UIDLength) = unpack('> B B H H', Stream.read(6))
        self.SOPClassUID = Stream.read(self.UIDLength)
        (self.SCURole, self.SCPRole) = unpack('B B', Stream.read(2))

    def TotalLength(self):
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

class UserIdentityParameters:
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

class UserIdentitySubItemRQ:
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

    def TotalLength(self):
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

class UserIdentitySubItemAC:
    pass


def get_next_item_type(s):
    """
    Peek at the io.StringIO stream `s` and see what PDU sub-item type
    it is. Each valid PDU sub item has an Item-type as the first byte, so
    we look at the first byte in the stream, then reverse back to the start
    of the stream
    
    Parameters
    ----------
    s - io.StringIO
        The stream to peek
        
    Returns
    -------
    item_type
        The first byte of the stream
    None
        If the stream is empty
    """
    first_byte = s.read(1)
    
    # If the stream is empty
    if first_byte == '':
        return None

    # Reverse our peek
    s.seek(-1, 1)
    
    return struct.unpack('B', chr)[0]

def next_item(s):
    """ 
    Peek at the stream `s` and see what the next item type
    it is. Each valid PDU/item/subitem has an Item-type as the first byte, so
    we look at the first byte in the stream, then reverse back to the start
    of the stream
    
    Parameters
    ----------
    s - io.ByteIO
        The stream to peek
        
    Returns
    -------
    PDU
        A PDU subclass instance corresponding to the next item in the stream
    None
        If the stream is empty
    
    Raises
    ------
    ValueError
        If the next item type is invalid
    """

    item_type = get_next_item_type(s)

    if item_type == 0x01:
        return A_ASSOCIATE_RQ_PDU()
    elif item_type == 0x02:
        return A_ASSOCIATE_AC_PDU()
    elif item_type == 0x03:
        return A_ASSOCIATE_RJ_PDU()
    elif item_type == 0x04:
        return P_DATA_TF_PDU()
    elif item_type == 0x05:
        return A_RELEASE_RQ_PDU()
    elif item_type == 0x06:
        return A_RELEASE_RP_PDU()
    elif item_type == 0x07:
        return A_ABORT_PDU()
    elif item_type == 0x10:
        return ApplicationContextItem()
    elif item_type == 0x20:
        return PresentationContextItemRQ()
    elif item_type == 0x21:
        return PresentationContextItemAC()
    elif item_type == 0x30:
        return AbstractSyntaxSubItem()
    elif item_type == 0x40:
        return TransferSyntaxSubItem()
    elif item_type == 0x50:
        return UserInformationItem()
    elif item_type == 0x52:
        return ImplementationClassUIDSubItem()
    elif item_type == 0x51:
        return MaximumLengthSubItem()
    elif item_type == 0x55:
        return ImplementationVersionNameSubItem()
    elif item_type == 0x53:
        return AsynchronousOperationsWindowSubItem()
    elif item_type == 0x54:
        return SCP_SCU_RoleSelectionSubItem()
    elif item_type == 0x56:
        return SOPClassExtendedNegotiationSubItem()
    elif item_type is None:
        # if we are at the end of stream
        return None
    else:
        raise ValueError("During PDU decoding we received an invalid "
                    "PDU type: %s" %pdu_type)


# Used twice during ::Decode
def NextType(Stream):
    """ """
    chr = Stream.read(1)
    if chr == b'':
        # we are at the end of the file
        return None
    Stream.seek(-1, 1)

    return unpack('B', chr)[0]

# Not used
def NextPDUType(Stream):
    """ """
    Type = NextType(Stream)
    if Type == 0x01:
        return A_ASSOCIATE_RQ_PDU
    elif Type == 0x02:
        return A_ASSOCIATE_AC_PDU
    elif Type == 0x03:
        return A_ASSOCIATE_RJ_PDU
    elif Type == 0x04:
        return P_DATA_TF_PDU
    elif Type == 0x05:
        return A_RELEASE_RQ_PDU
    elif Type == 0x06:
        return A_RELEASE_RP_PDU
    elif Type == 0x07:
        return A_ABORT_PDU
    elif Type is None:
        # end of file
        return None
    else:
        raise #'InvalidPDU'

# Used once in UserInformationItem::Decode
def NextSubItemType(Stream):
    """
    Parameters
    ----------
    Stream - ?
        ???
        
    Returns
    -------
    sub_item
        The PDU sub item type
    """
    ItemType = NextType(Stream)
    if ItemType == 0x52:
        return ImplementationClassUIDSubItem
    elif ItemType == 0x51:
        return MaximumLengthSubItem
    elif ItemType == 0x55:
        return ImplementationVersionNameSubItem
    elif ItemType == 0x53:
        return AsynchronousOperationsWindowSubItem
    elif ItemType == 0x54:
        return SCP_SCU_RoleSelectionSubItem
    elif ItemType == 0x56:
        return SOPClassExtentedNegociationSubItem
    elif ItemType is None:
        return None
    else:
        raise #'Invalid Sub Item', "0x%X" % ItemType

# Not used
def DecodePDU(rawstring):
    """Takes an encoded PDU as a string and return a PDU object
    
    Parameters
    ----------
    rawstring - str
        PDU encoded as a string
        
    Returns
    -------
    PDU
        The PDU object that was encoded in `rawstring`
    """
    chr = unpack('B', rawstring[0])[0]
    if chr == 0x01:
        PDU = A_ASSOCIATE_RQ_PDU()
    elif chr == 0x02:
        PDU = A_ASSOCIATE_AC_PDU()
    elif chr == 0x03:
        PDU = A_ASSOCIATE_RJ_PDU()
    elif chr == 0x04:
        PDU = P_DATA_TF_PDU()
    elif chr == 0x05:
        PDU = A_RELEASE_RQ_PDU()
    elif chr == 0x06:
        PDU = A_RELEASE_RP_PDU()
    elif chr == 0x07:
        PDU = A_ABORT_PDU()
    else:
        raise #'InvalidPDUType'
    
    PDU.Decode(rawstring)
    return PDU
