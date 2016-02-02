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
from struct import *
#from StringIO import StringIO

from pynetdicom.DIMSEparameters import *
from pynetdicom.DULparameters import *


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
        # Unsigned byte
        self.Reserved1 = 0x00
        # Unsigned int
        self.PDULength = None
        # Unsigned short
        self.ProtocolVersion = 1
        # Unsigned short
        self.Reserved2 = 0x00
        # string of length 16
        self.CalledAETitle = None
        # string of length 16
        self.CallingAETitle = None
        # 32 bytes
        self.Reserved3 = (0, 0, 0, 0, 0, 0, 0, 0)
        
        # VariableItems is a list containing the following:
        #   1 ApplicationContextItem
        #   1 or more PresentationContextItemRQ
        #   1 UserInformationItem
        self.VariableItems = []
        
        # Refactor
        #self.parameters = [(0x01, 'B')                 # PDU-type
        #                   (0x00, 'B')                 # Reserved
        #                   (None, '>I')                # PDU-length
        #                   (1, '>H')                   # Protocol-version
        #                   (0x00, '>H')                # Reserved
        #                   (None, '16s')               # Called-AE-title
        #                   (None,'16s')                # Calling-AE-title
        #                   ((0,0,0,0,0,0,0,0), '>8I')] # Reserved
        
        #                                               # Variable items

    def FromParams(self, Params):
        """
        Setup the PDU with the parameter values
        
        Parameters
        ----------
        Params - A_ASSOCIATE_ServiceParameters
            The parameters to use for setting up the PDU
        """
        self.CallingAETitle = Params.CallingAETitle
        self.CalledAETitle = Params.CalledAETitle
        
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
        tmp_user_info.FromParams(Params.UserInformation)
        self.VariableItems.append(tmp_user_info)

        self.PDULength = 68
        for ii in self.VariableItems:
            self.PDULength = self.PDULength + ii.TotalLength()

    def ToParams(self):
        # Returns an A_ASSOCIATE_ServiceParameters object
        ass = A_ASSOCIATE_ServiceParameters()
        ass.CallingAETitle = self.CallingAETitle
        ass.CalledAETitle = self.CalledAETitle
        ass.ApplicationContextName = self.VariableItems[
            0].ApplicationContextName
        # Write presentation contexts
        for ii in self.VariableItems[1:-1]:
            ass.PresentationContextDefinitionList.append(ii.ToParams())
        # Write user information
        ass.UserInformation = self.VariableItems[-1].ToParams()
        return ass

    def Encode(self):
        # Python3 must implicitly defined string as bytes
        tmp = b''
        tmp = tmp + pack('B',   self.PDUType)
        tmp = tmp + pack('B',   self.Reserved1)
        tmp = tmp + pack('>I',  self.PDULength)
        tmp = tmp + pack('>H',  self.ProtocolVersion)
        tmp = tmp + pack('>H',  self.Reserved2)
        tmp = tmp + pack('16s', bytes(self.CalledAETitle, 'utf-8'))
        tmp = tmp + pack('16s', bytes(self.CallingAETitle, 'utf-8'))
        tmp = tmp + pack('>8I', 0, 0, 0, 0, 0, 0, 0, 0)
        
        # variable item elements
        for ii in self.VariableItems:
            tmp = tmp + ii.Encode()
        return tmp

    def Decode(self, rawstring):
        Stream = BytesIO(rawstring)
        
        (self.PDUType, 
         self.Reserved1, 
         self.PDULength,
         self.ProtocolVersion, 
         self.Reserved2, 
         self.CalledAETitle,
         self.CallingAETitle) = unpack('> B B I H H 16s 16s', Stream.read(42))
        self.Reserved3 = unpack('> 8I', Stream.read(32))
        
        while 1:
            type = NextType(Stream)
            
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
            tmp.Decode(Stream)
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
        tmp_user_info.FromParams(Params.UserInformation)
        self.VariableItems.append(tmp_user_info)
        # Compute PDU length
        self.PDULength = 68
        for ii in self.VariableItems:
            self.PDULength = self.PDULength + ii.TotalLength()

    def ToParams(self):
        ass = A_ASSOCIATE_ServiceParameters()
        ass.CalledAETitle = self.Reserved3
        ass.CallingAETitle = self.Reserved4
        ass.ApplicationContextName = self.VariableItems[0].ToParams()

        # Write presentation context
        for ii in self.VariableItems[1:-1]:
            ass.PresentationContextDefinitionResultList.append(ii.ToParams())

        # Write user information
        ass.UserInformation = self.VariableItems[-1].ToParams()
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
        Stream = BytesIO(rawstring)
        (self.PDUType, 
         self.Reserved1, 
         self.PDULength,
         self.ProtocolVersion, 
         self.Reserved2, 
         self.Reserved3,
         self.Reserved4) = unpack('> B B I H H 16s 16s', Stream.read(42))
        self.Reserved5 = unpack('>8I', Stream.read(32))
        
        while 1:
            Type = NextType(Stream)
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
            tmp.Decode(Stream)
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


class A_ASSOCIATE_RJ_PDU(PDU):
    '''This class represents the A-ASSOCIATE-RJ PDU'''
    def __init__(self):
        self.PDUType = 0x03                           # Unsigned byte
        self.Reserved1 = 0x00                         # Unsigned byte
        self.PDULength = 0x00000004             # Unsigned int
        self.Reserved2 = 0x00                         # Unsigned byte
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
        tmp = tmp + pack('B', self.Reserved1)
        tmp = tmp + pack('>I', self.PDULength)
        tmp = tmp + pack('B', self.Reserved2)
        tmp = tmp + pack('B', self.Result)
        tmp = tmp + pack('B', self.Source)
        tmp = tmp + pack('B', self.ReasonDiag)
        return tmp

    def Decode(self, rawstring):
        Stream = BytesIO(rawstring)
        (self.PDUType, 
         self.Reserved1, 
         self.PDULength, 
         self.Reserved2,
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


class P_DATA_TF_PDU(PDU):
    '''This class represents the P-DATA-TF PDU'''
    def __init__(self):
        self.PDUType = 0x04                     # Unsigned byte
        self.Reserved = 0x00                        # Unsigned byte
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
        tmp = tmp + pack('B', self.Reserved)
        tmp = tmp + pack('>I', self.PDULength)
        
        for ii in self.PresentationDataValueItems:
            tmp = tmp + ii.Encode()
        return tmp

    def Decode(self, rawstring):
        Stream = BytesIO(rawstring)
        
        (self.PDUType, 
         self.Reserved,
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


class A_RELEASE_RQ_PDU(PDU):
    '''This class represents the A-ASSOCIATE-RQ PDU'''
    def __init__(self):
        self.PDUType = 0x05                     # Unsigned byte
        self.Reserved1 = 0x00                   # Unsigned byte
        self.PDULength = 0x00000004         # Unsigned int
        self.Reserved2 = 0x00000000         # Unsigned int

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
        tmp = tmp + pack('B', self.Reserved1)
        tmp = tmp + pack('>I', self.PDULength)
        tmp = tmp + pack('>I', self.Reserved2)
        return tmp

    def Decode(self, rawstring):
        Stream = BytesIO(rawstring)
        
        (self.PDUType, 
         self.Reserved1,
         self.PDULength, 
         self.Reserved2) = unpack('> B B I I', Stream.read(10))

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
        self.Reserved1 = 0x00                   # Unsigned byte
        self.PDULength = 0x00000004         # Unsigned int
        self.Reserved2 = 0x00000000         # Unsigned int

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
        tmp = tmp + pack('B', self.Reserved1)
        tmp = tmp + pack('>I', self.PDULength)
        tmp = tmp + pack('>I', self.Reserved2)
        return tmp

    def Decode(self, rawstring):
        Stream = BytesIO(rawstring)
        
        (self.PDUType, 
         self.Reserved1,
         self.PDULength, 
         self.Reserved2) = unpack('> B B I I', Stream.read(10))

    def TotalLength(self):
        return 10

    def __repr__(self):
        tmp = "A-RELEASE-RP PDU\n"
        tmp = tmp + " PDU type: 0x%02x\n" % self.PDUType
        tmp = tmp + " PDU length: %d\n" % self.PDULength
        return tmp + "\n"


class A_ABORT_PDU(PDU):
    '''This class represents the A-ABORT PDU'''
    def __init__(self):
        self.PDUType = 0x07                         # Unsigned byte
        self.Reserved1 = 0x00                       # Unsigned byte
        self.PDULength = 0x00000004         # Unsigned int
        self.Reserved2 = 0x00                       # Unsigned byte
        self.Reserved3 = 0x00           # Unsigned byte
        self.AbortSource = None                          # Unsigned byte
        self.ReasonDiag = None              # Unsigned byte

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
        tmp = tmp + pack('B', self.PDUType)
        tmp = tmp + pack('B', self.Reserved1)
        tmp = tmp + pack('>I', self.PDULength)
        tmp = tmp + pack('B', self.Reserved2)
        tmp = tmp + pack('B', self.Reserved3)
        tmp = tmp + pack('B', self.AbortSource)
        tmp = tmp + pack('B', self.ReasonDiag)
        return tmp

    def Decode(self, rawstring):
        Stream = BytesIO(rawstring)
        
        (self.PDUType, 
         self.Reserved1, 
         self.PDULength, 
         self.Reserved2,
         self.Reserved3, 
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


# Items and sub-items classes
class ApplicationContextItem(PDU):
    def __init__(self):
        self.ItemType = 0x10                                    # Unsigned byte
        self.Reserved = 0x00                                    # Unsigned byte
        self.ItemLength = None                              # Unsigned short
        self.ApplicationContextName = None              # String

    def FromParams(self, params):
        # params is a string
        self.ApplicationContextName = params
        self.ItemLength = len(self.ApplicationContextName)

    def ToParams(self):
        # Returns the application context name
        return self.ApplicationContextName

    def Encode(self):
        tmp = b''
        tmp = tmp + pack('B', self.ItemType)
        tmp = tmp + pack('B', self.Reserved)
        tmp = tmp + pack('>H', self.ItemLength)
        tmp = tmp + self.ApplicationContextName
        return tmp

    def Decode(self, Stream):
        (self.ItemType, 
         self.Reserved,
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
    def __init__(self):
        # Unsigned byte
        self.ItemType = 0x20
        # Unsigned byte
        self.Reserved1 = 0x00
        # Unsigned short
        self.ItemLength = None
        self.PresentationContextID = None                       # Unsigned byte
        # Unsigned byte
        self.Reserved2 = 0x00
        # Unsigned byte
        self.Reserved3 = 0x00
        # Unsigned byte
        self.Reserved4 = 0x00
        # AbstractTransferSyntaxSubItems is a list
        # containing the following elements:
        #         One AbstractSyntaxtSubItem
        #     One of more TransferSyntaxSubItem
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
        tmp = tmp + pack('B', self.Reserved1)
        tmp = tmp + pack('>H', self.ItemLength)
        tmp = tmp + pack('B', self.PresentationContextID)
        tmp = tmp + pack('B', self.Reserved2)
        tmp = tmp + pack('B', self.Reserved3)
        tmp = tmp + pack('B', self.Reserved4)
        
        for ii in self.AbstractTransferSyntaxSubItems:
            tmp = tmp + ii.Encode()
        return tmp

    def Decode(self, Stream):
        (self.ItemType, 
         self.Reserved1, 
         self.ItemLength,
         self.PresentationContextID, 
         self.Reserved2, 
         self.Reserved3,
         self.Reserved4) = unpack('> B B H B B B B', Stream.read(8))
        
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


class PresentationContextItemAC(PDU):
    def __init__(self):
        self.ItemType = 0x21                        # Unsigned byte
        self.Reserved1 = 0x00                   # Unsigned byte
        self.ItemLength = None                  # Unsigned short
        self.PresentationContextID = None   # Unsigned byte
        self.Reserved2 = 0x00                   # Unsigned byte
        self.ResultReason = None                # Unsigned byte
        self.Reserved3 = 0x00                   # Unsigned byte
        self.TransferSyntaxSubItem = None   # TransferSyntaxSubItem object

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
        tmp = tmp + pack('B', self.Reserved1)
        tmp = tmp + pack('>H', self.ItemLength)
        tmp = tmp + pack('B', self.PresentationContextID)
        tmp = tmp + pack('B', self.Reserved2)
        tmp = tmp + pack('B', self.ResultReason)
        tmp = tmp + pack('B', self.Reserved3)
        tmp = tmp + self.TransferSyntaxSubItem.Encode()
        return tmp

    def Decode(self, Stream):
        (self.ItemType, 
         self.Reserved1, 
         self.ItemLength,
         self.PresentationContextID, 
         self.Reserved2, 
         self.ResultReason,
         self.Reserved3) = unpack('> B B H B B B B', Stream.read(8))
        
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


class AbstractSyntaxSubItem(PDU):
    def __init__(self):
        self.ItemType = 0x30                            # Unsigned byte
        self.Reserved = 0x00                            # Unsigned byte
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
        tmp = tmp + pack('B', self.Reserved)
        tmp = tmp + pack('>H', self.ItemLength)
        tmp = tmp + bytes(self.AbstractSyntaxName, 'utf-8')
        return tmp

    def Decode(self, Stream):
        (self.ItemType, 
         self.Reserved,
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
        self.Reserved = 0x00                            # Unsigned byte
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
        tmp = tmp + pack('B', self.Reserved)
        tmp = tmp + pack('>H', self.ItemLength)
        tmp = tmp + bytes(self.TransferSyntaxName, 'utf-8')
        return tmp

    def Decode(self, Stream):
        (self.ItemType, 
         self.Reserved,
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
        # Unsigned byte
        self.Reserved = 0x00
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
        tmp = tmp + pack('B', self.Reserved)
        tmp = tmp + pack('>H', self.ItemLength)
        
        for ii in self.UserData:
            tmp += ii.Encode()
        return tmp

    def Decode(self, Stream):
        (self.ItemType, 
         self.Reserved,
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
        self.Reserved = 0x00                        # Unsigned byte
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
        tmp = tmp + pack('B', self.Reserved)
        tmp = tmp + pack('>H', self.ItemLength)
        tmp = tmp + pack('>I', self.MaximumLengthReceived)
        return tmp

    def Decode(self, Stream):
        (self.ItemType, 
         self.Reserved,
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


class GenericUserDataSubItem(PDU):
    """
    This class is provided only to allow user data to converted to and from
    PDUs. The actual data is not interpreted. This is left to the user.
    """
    def __init__(self):
        self.ItemType = None                # Unsigned byte
        self.Reserved = 0x00                # Unsigned byte
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
        tmp = tmp + pack('B', self.Reserved)
        tmp = tmp + pack('>H', self.ItemLength)
        tmp = tmp + self.UserData
        return tmp

    def Decode(self, Stream):
        (self.ItemType, 
         self.Reserved,
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
    Peek at the io.StringIO stream `s` and see what the next item type
    it is. Each valid PDU/item/subitem has an Item-type as the first byte, so
    we look at the first byte in the stream, then reverse back to the start
    of the stream
    
    Parameters
    ----------
    s - io.StringIO
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
