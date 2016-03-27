#
# Copyright (c) 2012 Patrice Munger
# This file is part of pynetdicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pynetdicom.googlecode.com
#
from io import BytesIO
import itertools
import logging
from struct import pack, unpack

from pydicom.dataset import Dataset
from pydicom._dicom_dict import DicomDictionary
from pydicom.uid import ImplicitVRLittleEndian

from pynetdicom.DIMSEparameters import *
from pynetdicom.dsutils import encode_element, encode, decode
from pynetdicom.DULparameters import *
from pynetdicom.utils import fragment

logger = logging.getLogger('pynetdicom.dimse')


class DIMSEMessage:
    """
    All DIMSE Message classes implement the following methods:

    FromParams(DIMSEServiceParameter) :  Builds a DIMSE message from a
                                         DULServiceParameter
                                         object. Used when receiving
                                         primitives from the
                                         DIMSEServiceUser.
    ToParams()                        :  Convert the Message into a
                                         DIMSEServiceParameter object.
                                         Used for sending primitives to
                                         the DIMSEServiceUser.
    Encode()                          :  Returns the encoded message in
                                         one or several P-DATA parameters
                                         structure.
    Decode(pdata)                     :  Construct the message from one
                                         or several P-DATA primitives

                             FromParams              Encode
    .----------------------.  ----->   .----------.  ----->  .---------------.
    |   DIMSE parameters   |           |   DIMSE  |          |     P-DATA    |
    |        object        |           |  message |          |  primitive(s) |
    .----------------------.  <-----   .----------.  <-----  .---------------.
                              ToParams               Decode

    Attributes
    ----------
    CommandSet - pydicom.dataset.Dataset
        The message Command Information (PS3.7 6.3)
    DataSet : pydicom.dataset.Dataset
        The message Data Set (PS3.7 6.3)
    ID : int
        The presentation context ID
    """
    def __init__(self):
        self.CommandSet = None
        self.DataSet = BytesIO()
        self.ID = None
        
        self.EncodedDataSet = None
        self.encoded_command_set = BytesIO()

        self.ts = ImplicitVRLittleEndian  # imposed by standard

        
        if self.__class__ != DIMSEMessage:
            self.CommandSet = Dataset()
            for ii in self.CommandFields:
                self.CommandSet.add_new(ii[1], ii[2], '')

    def Encode(self, context_id, max_pdu):
        """
        Encode the DIMSE primitive as one or more P-DATA-TF Presentation Data 
        Value Items
        
        PS3.7 6.3.1
        The encoding of the Command Set shall be Little Endian Implicit VR
        
        Parameters
        ----------
        context_id - int
            The ID of the presentation context agreed to under which we are
            sending the data
        max_pdu_length - int
            The maximum PDU length in bytes
            
        Returns
        -------
        p_data_list - list of BytesIO 
            A list of one or more P-DATA-TF Presentation Data Value Items
        """
        self.ID = context_id
        p_data_list = []
        
        encoded_command_set = encode(self.CommandSet, 
                                     self.ts.is_implicit_VR, 
                                     self.ts.is_little_endian)

        ## COMMAND SET
        # Split the command set into framents with maximum size max_pdu
        pdvs = fragment(max_pdu, encoded_command_set)
        
        # First to (n - 1)th command data fragment - b XXXXXX01
        for ii in pdvs[:-1]:
            pdata = P_DATA_ServiceParameters()
            pdata.PresentationDataValueList = [[self.ID, pack('b', 1) + ii]]
            
            p_data_list.append(pdata)
        
        # Nth command data fragment - b XXXXXX11
        pdata = P_DATA_ServiceParameters()
        pdata.PresentationDataValueList = [[self.ID, pack('b', 3) + pdvs[-1]]]
       
        p_data_list.append(pdata)


        ## DATASET (if available)
        # Split out dataset up into fragment with maximum size of max_pdu
        if 'DataSet' in self.__dict__ and self.DataSet.getvalue() != b'':
            pdvs = fragment(max_pdu, self.DataSet)

            # First to (n - 1)th dataset fragment - b XXXXXX00
            for ii in pdvs[:-1]:
                pdata = P_DATA_ServiceParameters()
                pdata.PresentationDataValueList = [[self.ID, pack('b', 0) + ii]]
                p_data_list.append(pdata)
            
            # Nth dataset fragment - b XXXXXX10
            pdata = P_DATA_ServiceParameters()
            pdata.PresentationDataValueList = \
                                        [[self.ID, pack('b', 2) + pdvs[-1]]]
            
            p_data_list.append(pdata)

        return p_data_list

    def Decode(self, pdata):
        """Constructs itself receiving a series of P-DATA primitives.
        
        PS3.9 Section 9.3.1: The encoding of the DICOM UL PDUs is
        big endian byte ordering, while the encoding of the PDV message
        fragments is defined by the negotiated Transfer Syntax at association
        establishment
        
        Parameters
        ----------
        pdata : pynetdicom. 
        
        Returns
        -------
        bool
            True when complete, False otherwise.
        """
        # Make sure this is a P-DATA
        if pdata.__class__ != P_DATA_ServiceParameters or pdata is None:
            return False

        for pdv_item in pdata.PresentationDataValueList:
            # Presentation Context ID
            self.ID = pdv_item[0]

            # The first byte of the P-DATA is the Message Control Header
            # See PS3.8 Annex E.2
            # xxxxxx00 - Message Dataset information, not the last fragment
            # xxxxxx01 - Command information, not the last fragment
            # xxxxxx10 - Message Dataset information, the last fragment
            # xxxxxx11 - Command information, the last fragment
            control_header_byte = pdv_item[1][0]

            ## COMMAND SET
            # P-DATA fragment contains Command information (xxxxxx01, xxxxxx11)
            if control_header_byte & 1:
                self.encoded_command_set.write(pdv_item[1][1:])

                # The P-DATA fragment is the last one (xxxxxx11)
                if control_header_byte & 2:
                    self.CommandSet = decode(self.encoded_command_set, 
                                             self.ts.is_implicit_VR,
                                             self.ts.is_little_endian)

                    # Determine which class to use
                    self.__class__ = MessageType[
                        self.CommandSet[(0x0000, 0x0100)].value]

                    # (0000, 0800) CommandDataSetType US 1
                    #   if value is 0101H no dataset present
                    #   otherwise a dataset is included in the Message
                    if self.CommandSet[(0x0000, 0x0800)].value == 0x0101:
                        return True

            ## DATA SET
            # P-DATA fragment contains Message Dataset information (xxxxxx00, xxxxxx10)
            else:
                self.DataSet.write(pdv_item[1][1:])

                # The P-DATA fragment is the last one (xxxxxx10)
                if control_header_byte & 2 != 0:
                    return True

        return False

    def SetLength(self):
        # Compute length
        length = 0
        
        for ii in list(self.CommandSet.values())[1:]:
            length += len(encode_element(ii,
                                         self.ts.is_implicit_VR,
                                         self.ts.is_little_endian))
        
        self.CommandSet[(0x0000, 0x0000)].value = length


# DIMSE-C
class C_ECHO_RQ_Message(DIMSEMessage):
    """ 
    PS3.7 Section 9.3.5.1 and Table 9.3-12
    
    Required Fields
    (0000,0000) CommandGroupLength          UL 1 
    (0000,0002) AffectedSOPClassUID         UI 1
    (0000,0100) CommandField                US 1    (=0x00 0x30)
    (0000,0110) MessageID                   US 1
    (0000,0800) CommandDataSetType          US 1    (=0x01 0x01)
    """
    
    CommandFields = [
        ('Group Length', (0x0000, 0x0000), 'UL', 1),
        ('Affected SOP Class UID', (0x0000, 0x0002), 'UI', 1),
        ('Command Field', (0x0000, 0x0100), 'US', 1),
        ('Message ID', (0x0000, 0x0110), 'US', 1),
        ('Data Set Type', (0x0000, 0x0800), 'US', 1)
    ]
    DataField = None

    def FromParams(self, params):
        self.CommandSet[(0x0000, 0x0002)].value = params.AffectedSOPClassUID
        self.CommandSet[(0x0000, 0x0100)].value = 0x0030
        self.CommandSet[(0x0000, 0x0110)].value = params.MessageID
        self.CommandSet[(0x0000, 0x0800)].value = 0x0101
        self.DataSet = BytesIO()
        self.SetLength()

    def ToParams(self):
        tmp = C_ECHO_ServiceParameters()
        tmp.MessageID = self.CommandSet[(0x0000, 0x0110)]
        tmp.AffectedSOPClassUID = self.CommandSet[(0x0000, 0x0002)]
        return tmp


class C_ECHO_RSP_Message(DIMSEMessage):
    """ 
    PS3.7 Section 9.3.5.2 and Table 9.3-13
    
    Required Fields
    (0000,0000) CommandGroupLength          UL 1 
    (0000,0002) AffectedSOPClassUID         UI 1
    (0000,0100) CommandField                US 1    (=0x80 0x30)
    (0000,0120) MessageIDBeingRespondedTo   US 1
    (0000,0800) CommandDataSetType          US 1    (=0x01 0x01)
    (0000,0900) Status                      US 1    (=0x00 0x00 Success)
    """
    CommandFields = [
        ('Group Length', (0x0000, 0x0000), 'UL', 1),
        ('Affected SOP Class UID', (0x0000, 0x0002), 'UI', 1),
        ('Command Field', (0x0000, 0x0100), 'US', 1),
        ('Message ID Being Responded To', (0x0000, 0x0120), 'US', 1),
        ('Data Set Type', (0x0000, 0x0800), 'US', 1),
        ('Status', (0x0000, 0x0900), 'US', 1)
    ]
    DataField = None

    def FromParams(self, params):
        if params.AffectedSOPClassUID:
            self.CommandSet[(0x0000, 0x0002)].value = params.AffectedSOPClassUID
        self.CommandSet[(0x0000, 0x0100)].value = 0x8030
        self.CommandSet[(0x0000, 0x0120)
                        ].value = params.MessageIDBeingRespondedTo
        self.CommandSet[(0x0000, 0x0800)].value = 0x0101
        self.CommandSet[(0x0000, 0x0900)].value = params.Status
        self.SetLength()

    def ToParams(self):
        tmp = C_ECHO_ServiceParameters()
        tmp.AffectedSOPClassUID = self.CommandSet[(0x0000, 0x0002)]
        tmp.MessageIDBeingRespondedTo = self.CommandSet[(0x0000, 0x0120)]
        tmp.Status = 0
        return tmp


class C_STORE_RQ_Message(DIMSEMessage):
    CommandFields = [('Group Length', (0x0000, 0x0000), 'UL', 1),
                     ('Affected SOP Class UID', (0x0000, 0x0002), 'UI', 1),
                     ('Command Field', (0x0000, 0x0100), 'US', 1),
                     ('Message ID', (0x0000, 0x0110), 'US', 1),
                     ('Priority', (0x0000, 0x0700), 'US', 1),
                     ('Data Set Type', (0x0000, 0x0800), 'US', 1),
                     ('Affected SOP Instance UID', (0x0000, 0x1000), 'UI', 1),
                     ('Move Originator Application Entity Title',
                            (0x0000, 0x1030), 'AE', 1),
                     ('Move Originator Message ID', (0x0000, 0x1031), 'US', 1)]
    
    DataField = 'Data Set'

    def FromParams(self, params):
        self.CommandSet[(0x0000, 0x0002)].value = params.AffectedSOPClassUID
        self.CommandSet[(0x0000, 0x0100)].value = 0x0001
        self.CommandSet[(0x0000, 0x0110)].value = params.MessageID
        self.CommandSet[(0x0000, 0x0700)].value = params.Priority
        self.CommandSet[(0x0000, 0x0800)].value = 0x0001
        self.CommandSet[(0x0000, 0x1000)].value = params.AffectedSOPInstanceUID
        
        if params.MoveOriginatorApplicationEntityTitle:
            self.CommandSet[(0x0000, 0x1030)].value = \
                params.MoveOriginatorApplicationEntityTitle
        else:
            self.CommandSet[(0x0000, 0x1030)].value = ""
        
        if params.MoveOriginatorMessageID:
            self.CommandSet[(0x0000, 0x1031)
                            ].value = params.MoveOriginatorMessageID
        else:
            self.CommandSet[(0x0000, 0x1031)].value = ""
        
        self.DataSet = params.DataSet
        self.SetLength()

    def ToParams(self):
        tmp = C_STORE_ServiceParameters()
        tmp.AffectedSOPClassUID = self.CommandSet[(0x0000, 0x0002)]
        tmp.AffectedSOPInstanceUID = self.CommandSet[(0x0000, 0x1000)]
        tmp.Priority = self.CommandSet[(0x0000, 0x0700)]
        tmp.DataSet = self.DataSet
        tmp.MessageID = self.CommandSet[(0x0000, 0x0110)]
        return tmp


class C_STORE_RSP_Message(DIMSEMessage):
    CommandFields = [
        ('Group Length',
         (0x0000, 0x0000), 'UL', 1),
        ('Affected SOP Class UID',
         (0x0000, 0x0002), 'UI', 1),
        ('Command Field',
         (0x0000, 0x0100), 'US', 1),
        ('Message ID Being Responded To',
         (0x0000, 0x0120), 'US', 1),
        ('Data Set Type',
         (0x0000, 0x0800), 'US', 1),
        ('Status',
         (0x0000, 0x0900), 'US', 1),
        ('Affected SOP Instance UID',                (0x0000, 0x1000), 'UI', 1)
    ]

    def FromParams(self, params):
        self.CommandSet[(0x0000, 0x0002)
                        ].value = params.AffectedSOPClassUID.value
        self.CommandSet[(0x0000, 0x0100)].value = 0x8001
        self.CommandSet[(0x0000, 0x0120)
                        ].value = params.MessageIDBeingRespondedTo.value
        self.CommandSet[(0x0000, 0x0800)].value = 0x0101
        self.CommandSet[(0x0000, 0x0900)].value = params.Status
        self.CommandSet[(0x0000, 0x1000)
                        ].value = params.AffectedSOPInstanceUID.value
        self.DataSet = BytesIO()
        self.SetLength()

    def ToParams(self):
        tmp = C_STORE_ServiceParameters()
        tmp.AffectedSOPClassUID = self.CommandSet[(0x0000, 0x0002)]
        tmp.MessageIDBeingRespondedTo = self.CommandSet[(0x0000, 0x0120)]
        tmp.Status = self.CommandSet[(0x0000, 0x0900)]
        tmp.AffectedSOPInstanceUID = self.CommandSet[(0x0000, 0x1000)]
        tmp.DataSet = self.DataSet
        return tmp


class C_FIND_RQ_Message(DIMSEMessage):
    CommandFields = [('Group Length', (0x0000, 0x0000), 'UL', 1),
                     ('Affected SOP Class UID', (0x0000, 0x0002), 'UI', 1),
                     ('Command Field', (0x0000, 0x0100), 'US', 1),
                     ('Message ID', (0x0000, 0x0110), 'US', 1),
                     ('Data Set Type', (0x0000, 0x0800), 'US', 1),
                     ('Priority', (0x0000, 0x0700), 'US', 1)]
    DataField = 'Identifier'

    def FromParams(self, params):
        self.CommandSet[(0x0000, 0x0002)].value = params.AffectedSOPClassUID
        self.CommandSet[(0x0000, 0x0100)].value = 0x0020
        self.CommandSet[(0x0000, 0x0110)].value = params.MessageID
        self.CommandSet[(0x0000, 0x0700)].value = params.Priority
        self.CommandSet[(0x0000, 0x0800)].value = 0x0001
        self.DataSet = params.Identifier
        self.SetLength()

    def ToParams(self):
        tmp = C_FIND_ServiceParameters()
        tmp.AffectedSOPClassUID = self.CommandSet[(0x0000, 0x0002)]
        tmp.Priority = self.CommandSet[(0x0000, 0x0700)]
        tmp.Identifier = self.DataSet
        tmp.MessageID = self.CommandSet[(0x0000, 0x0110)]
        return tmp


class C_FIND_RSP_Message(DIMSEMessage):
    CommandFields = [
        ('Group Length',
         (0x0000, 0x0000), 'UL', 1),
        ('Affected SOP Class UID',
         (0x0000, 0x0002), 'UI', 1),
        ('Command Field',
         (0x0000, 0x0100), 'US', 1),
        ('Message ID Being Responded To',
         (0x0000, 0x0120), 'US', 1),
        ('Data Set Type',
         (0x0000, 0x0800), 'US', 1),
        ('Status',
         (0x0000, 0x0900), 'US', 1),
    ]
    DataField = 'Identifier'

    def FromParams(self, params):
        self.CommandSet[(0x0000, 0x0002)
                        ].value = params.AffectedSOPClassUID.value
        self.CommandSet[(0x0000, 0x0100)].value = 0x8020
        self.CommandSet[(0x0000, 0x0120)
                        ].value = params.MessageIDBeingRespondedTo.value
        if not params.Identifier:
            self.CommandSet[(0x0000, 0x0800)].value = 0x0101
        else:
            self.CommandSet[(0x0000, 0x0800)].value = 0x000
        self.CommandSet[(0x0000, 0x0900)].value = params.Status
        self.DataSet = params.Identifier
        self.SetLength()

    def ToParams(self):
        tmp = C_FIND_ServiceParameters()
        tmp.AffectedSOPClassUID = self.CommandSet[(0x0000, 0x0002)]
        tmp.MessageIDBeingRespondedTo = self.CommandSet[(0x0000, 0x0120)]
        tmp.Status = self.CommandSet[(0x0000, 0x0900)]
        tmp.Identifier = self.DataSet
        return tmp

    @property
    def Dataset(self):
        if self.DataSet.getvalue() != b'':
            return self.Dataset
        else:
            return None
    
    @property
    def Status(self):
        status = {0x0000 : 'Success',
                  0x0001 : 'Warning',
                  0x0107 : 'Attribute List Error',
                  0x0116 : 'Attribute Value Out of Range',
                  0xfe00 : 'Cancel',
                  0xff00 : 'Pending',
                  0xff01 : 'Pending'}

        status_str = '0x%04X (%s)' %(self.CommandSet.Status, 
                                     status[self.CommandSet.Status])
        return status_str


class C_GET_RQ_Message(DIMSEMessage):
    CommandFields = [
        ('Group Length',
         (0x0000, 0x0000), 'UL', 1),
        ('Affected SOP Class UID',
         (0x0000, 0x0002), 'UI', 1),
        ('Command Field',
         (0x0000, 0x0100), 'US', 1),
        ('Message ID',
         (0x0000, 0x0110), 'US', 1),
        ('Priority',
         (0x0000, 0x0700), 'US', 1),
        ('Data Set Type',
         (0x0000, 0x0800), 'US', 1),
    ]
    DataField = 'Identifier'

    def FromParams(self, params):
        self.CommandSet[(0x0000, 0x0002)].value = params.AffectedSOPClassUID
        self.CommandSet[(0x0000, 0x0100)].value = 0x0010
        self.CommandSet[(0x0000, 0x0110)].value = params.MessageID
        self.CommandSet[(0x0000, 0x0700)].value = params.Priority
        self.CommandSet[(0x0000, 0x0800)].value = 0x0001
        self.DataSet = params.Identifier
        self.SetLength()

    def ToParams(self):
        tmp = C_GET_ServiceParameters()
        tmp.MessageID = self.CommandSet[(0x0000, 0x0110)].value
        tmp.AffectedSOPClassUID = self.CommandSet[(0x0000, 0x0002)].value
        tmp.Priority = self.CommandSet[(0x0000, 0x0700)].value
        tmp.Identifier = self.DataSet
        return tmp


class C_GET_RSP_Message(DIMSEMessage):
    CommandFields = [
        ('Group Length', (0x0000, 0x0000), 'UL', 1),
        ('Affected SOP Class UID', (0x0000, 0x0002), 'UI', 1),
        ('Command Field', (0x0000, 0x0100), 'US', 1),
        ('Message ID Being Responded To', (0x0000, 0x0120), 'US', 1),
        ('Data Set Type', (0x0000, 0x0800), 'US', 1), 
        ('Status', (0x0000, 0x0900), 'US', 1),
        ('Number of Remaining Sub-operations', (0x0000, 0x1020), 'US', 1),
        ('Number of Complete Sub-operations', (0x0000, 0x1021), 'US', 1),
        ('Number of Failed Sub-operations', (0x0000, 0x1022), 'US', 1),
        ('Number of Warning Sub-operations', (0x0000, 0x1023), 'US', 1)]
    DataField = 'Identifier'

    def FromParams(self, params):
        self.CommandSet[(0x0000, 0x0002)].value = params.AffectedSOPClassUID
        self.CommandSet[(0x0000, 0x0100)].value = 0x8010
        self.CommandSet[(0x0000, 0x0120)
                        ].value = params.MessageIDBeingRespondedTo
        self.CommandSet[(0x0000, 0x0800)].value = 0x0101
        self.CommandSet[(0x0000, 0x0900)].value = params.Status
        self.CommandSet[(0x0000, 0x1020)
                        ].value = params.NumberOfRemainingSubOperations
        self.CommandSet[(0x0000, 0x1021)
                        ].value = params.NumberOfCompletedSubOperations
        self.CommandSet[(0x0000, 0x1022)
                        ].value = params.NumberOfFailedSubOperations
        self.CommandSet[(0x0000, 0x1023)
                        ].value = params.NumberOfWarningSubOperations
        self.SetLength()

    def ToParams(self):
        tmp = C_GET_ServiceParameters()
        tmp.AffectedSOPClassUID = self.CommandSet[(0x0000, 0x0002)]
        tmp.MessageIDBeingRespondedTo = self.CommandSet[(0x0000, 0x0120)]
        tmp.Status = self.CommandSet[(0x0000, 0x0900)]
        try:
            tmp.NumberOfRemainingSubOperations = self.CommandSet[
                (0x0000, 0x1020)]
        except:
            pass
        tmp.NumberOfCompletedSubOperations = self.CommandSet[(0x0000, 0x1021)]
        tmp.NumberOfFailedSubOperations = self.CommandSet[(0x0000, 0x1022)]
        tmp.NumberOfWarningSubOperations = self.CommandSet[(0x0000, 0x1023)]
        tmp.Identifier = self.DataSet
        return tmp
    
    @property
    def AffectedSOPClassUID(self):
        return self.CommandSet.AffectedSOPClassUID
        
    @property
    def RespondingMessageID(self):
        return self.CommandSet.MessageIDBeingRespondedTo
        
    @property
    def Status(self):
        return self.CommandSet.Status
    
    @property
    def RemainingOperations(self):
        return self.CommandSet.NumberOfRemainingSubOperations
        
    @property
    def CompletedOperations(self):
        return self.CommandSet.NumberOfCompletedSubOperations
        
    @property
    def FailedOperations(self):
        return self.CommandSet.NumberOfFailedOperations
        
    @property
    def WarningOperations(self):
        return self.CommandSet.NumberOfWarningSubOperations
        
    @property
    def Dataset(self):
        return self.Identifier


class C_MOVE_RQ_Message(DIMSEMessage):
    CommandFields = [
        ('Group Length',
         (0x0000, 0x0000), 'UL', 1),
        ('Affected SOP Class UID',
         (0x0000, 0x0002), 'UI', 1),
        ('Command Field',
         (0x0000, 0x0100), 'US', 1),
        ('Message ID',
         (0x0000, 0x0110), 'US', 1),
        ('Priority',
         (0x0000, 0x0700), 'US', 1),
        ('Data Set Type',
         (0x0000, 0x0800), 'US', 1),
        ('Move Destination',
         (0x0000, 0x0600), 'AE', 1),
    ]
    DataField = 'Identifier'

    def FromParams(self, params):
        self.CommandSet[(0x0000, 0x0002)].value = params.AffectedSOPClassUID
        self.CommandSet[(0x0000, 0x0100)].value = 0x0021
        self.CommandSet[(0x0000, 0x0110)].value = params.MessageID
        self.CommandSet[(0x0000, 0x0700)].value = params.Priority
        self.CommandSet[(0x0000, 0x0800)].value = 0x0001
        self.CommandSet[(0x0000, 0x0600)].value = params.MoveDestination

        self.DataSet = params.Identifier
        self.SetLength()

    def ToParams(self):
        tmp = C_MOVE_ServiceParameters()
        tmp.MessageID = self.CommandSet[(0x0000, 0x0110)]
        tmp.AffectedSOPClassUID = self.CommandSet[(0x0000, 0x0002)]
        tmp.Priority = self.CommandSet[(0x0000, 0x0700)]
        tmp.MoveDestination = self.CommandSet[(0x0000, 0x0600)]
        tmp.Identifier = self.DataSet
        return tmp


class C_MOVE_RSP_Message(DIMSEMessage):
    CommandFields = [
        ('Group Length', (0x0000, 0x0000), 'UL', 1),
        ('Affected SOP Class UID', (0x0000, 0x0002), 'UI', 1),
        ('Command Field', (0x0000, 0x0100), 'US', 1),
        ('Message ID Being Responded To', (0x0000, 0x0120), 'US', 1),
        ('Data Set Type', (0x0000, 0x0800), 'US', 1),
        ('Status', (0x0000, 0x0900), 'US', 1),
        ('Number of Remaining Sub-operations', (0x0000, 0x1020), 'US', 1),
        ('Number of Complete Sub-operations', (0x0000, 0x1021), 'US', 1),
        ('Number of Failed Sub-operations', (0x0000, 0x1022), 'US', 1),
        ('Number of Warning Sub-operations', (0x0000, 0x1023), 'US', 1)]
    DataField = 'Identifier'

    def FromParams(self, params):
        self.CommandSet[(0x0000, 0x0002)].value = params.AffectedSOPClassUID
        self.CommandSet[(0x0000, 0x0100)].value = 0x8021
        self.CommandSet[(0x0000, 0x0120)
                        ].value = params.MessageIDBeingRespondedTo
        self.CommandSet[(0x0000, 0x0800)].value = 0x0101
        self.CommandSet[(0x0000, 0x0900)].value = params.Status
        self.CommandSet[(0x0000, 0x1020)
                        ].value = params.NumberOfRemainingSubOperations
        self.CommandSet[(0x0000, 0x1021)
                        ].value = params.NumberOfCompletedSubOperations
        self.CommandSet[(0x0000, 0x1022)
                        ].value = params.NumberOfFailedSubOperations
        self.CommandSet[(0x0000, 0x1023)
                        ].value = params.NumberOfWarningSubOperations
        self.SetLength()

    def ToParams(self):
        tmp = C_MOVE_ServiceParameters()
        tmp.AffectedSOPClassUID = self.CommandSet[(0x0000, 0x0002)]
        tmp.MessageIDBeingRespondedTo = self.CommandSet[(0x0000, 0x0120)]
        tmp.Status = self.CommandSet[(0x0000, 0x0900)]
        try:
            tmp.NumberOfRemainingSubOperations = self.CommandSet[
                (0x0000, 0x1020)]
        except:
            pass
        tmp.NumberOfCompletedSubOperations = self.CommandSet[(0x0000, 0x1021)]
        tmp.NumberOfFailedSubOperations = self.CommandSet[(0x0000, 0x1022)]
        tmp.NumberOfWarningSubOperations = self.CommandSet[(0x0000, 0x1023)]
        tmp.Identifier = self.DataSet
        return tmp


class C_CANCEL_RQ_Message(DIMSEMessage):
    CommandFields = [
        ('Group Length',
         (0x0000, 0x0000), 'UL', 1),
        ('Command Field',
         (0x0000, 0x0100), 'US', 1),
        ('Message ID Being Responded To',
         (0x0000, 0x0120), 'US', 1),
        ('Data Set Type',
         (0x0000, 0x0800), 'US', 1),
    ]
    DataField = 'Identifier'

    def FromParams(self, params):
        self.CommandSet[(0x0000, 0x0100)].value = 0x0FFF
        self.CommandSet[(0x0000, 0x0120)
                        ].value = params.MessageIDBeingRespondedTo
        self.CommandSet[(0x0000, 0x0800)].value = 0x0101
        self.SetLength()


class C_CANCEL_FIND_RQ_Message(C_CANCEL_RQ_Message):

    def ToParams(self):
        tmp = C_FIND_ServiceParameters()
        tmp.MessageIDBeingRespondedTo = self.CommandSet[(0x0000, 0x0120)]
        return tmp


class C_CANCEL_GET_RQ_Message(C_CANCEL_RQ_Message):

    def ToParams(self):
        tmp = C_GET_ServiceParameters()
        tmp.MessageIDBeingRespondedTo = self.CommandSet[(0x0000, 0x0120)]
        return tmp


class C_CANCEL_MOVE_RQ_Message(C_CANCEL_RQ_Message):

    def ToParams(self):
        tmp = C_MOVE_ServiceParameters()
        tmp.MessageIDBeingRespondedTo = self.CommandSet[(0x0000, 0x0120)]
        return tmp


# DIMSE-N
class N_EVENT_REPORT_RQ_Message(DIMSEMessage): 
    CommandFields = [
        ('Group Length', (0x0000, 0x0000), 'UL', 1),
        ('Affected SOP Class UID', (0x0000, 0x0002), 'UI', 1),
        ('Command Field', (0x0000, 0x0100), 'US', 1),
        ('Message ID', (0x0000, 0x0110), 'US', 1),
        ('Data Set Type', (0x0000, 0x0800), 'US', 1),
        ('Affected SOP Instance UID', (0x0000, 0x1000), 'UI', 1),
        ('Event Type ID', (0x0000, 0x1002), 'US', 1)]
    DataField = 'Event Information'


class N_EVENT_REPORT_RSP_Message(DIMSEMessage): 
    CommandFields = [
        ('Group Length', (0x0000, 0x0000), 'UL', 1),
        ('Affected SOP Class UID', (0x0000, 0x0002), 'UI', 1),
        ('Command Field', (0x0000, 0x0100), 'US', 1),
        ('Message ID Being Responded To', (0x0000, 0x0120), 'US', 1),
        ('Data Set Type', (0x0000, 0x0800), 'US', 1),
        ('Status', (0x0000, 0x0900), 'US', 1),
        ('Affected SOP Instance UID', (0x0000, 0x1000), 'UI', 1),
        ('Event Type ID', (0x0000, 0x1002), 'US', 1)]
    DataField = 'Event Information'


class N_GET_RQ_Message(DIMSEMessage): 
    CommandFields = [
        ('Group Length', (0x0000, 0x0000), 'UL', 1),
        ('Requested SOP Class UID', (0x0000, 0x0003), 'UI', 1),
        ('Command Field', (0x0000, 0x0100), 'US', 1),
        ('Message ID', (0x0000, 0x0110), 'US', 1),
        ('Data Set Type', (0x0000, 0x0800), 'US', 1),
        ('Requested SOP Instance UID', (0x0000, 0x1001), 'UI', 1)]
    DataField = 'Attribute Identifier List'


class N_GET_RSP_Message(DIMSEMessage):
    CommandFields = [
        ('Group Length', (0x0000, 0x0000), 'UL', 1),
        ('Affected SOP Class UID', (0x0000, 0x0002), 'UI', 1),
        ('Command Field', (0x0000, 0x0100), 'US', 1),
        ('Message ID Being Responded To', (0x0000, 0x0120), 'US', 1),
        ('Data Set Type', (0x0000, 0x0800), 'US', 1),
        ('Status', (0x0000, 0x0900), 'US', 1),
        ('Affected SOP Instance UID', (0x0000, 0x1000), 'UI', 1)]
    DataField = 'Attribute List'


class N_SET_RQ_Message(DIMSEMessage):
    CommandFields = [
        ('Group Length', (0x0000, 0x0000), 'UL', 1),
        ('Requested SOP Class UID', (0x0000, 0x0003), 'UI', 1),
        ('Command Field', (0x0000, 0x0100), 'US', 1),
        ('Message ID', (0x0000, 0x0110), 'US', 1),
        ('Data Set Type', (0x0000, 0x0800), 'US', 1),
        ('Requested SOP Instance UID', (0x0000, 0x1001), 'UI', 1)]
    DataField = 'Modification List'


class N_SET_RSP_Message(DIMSEMessage):
    CommandFields = [
        ('Group Length', (0x0000, 0x0000), 'UL', 1),
        ('Affected SOP Class UID', (0x0000, 0x0002), 'UI', 1),
        ('Command Field', (0x0000, 0x0100), 'US', 1),
        ('Message ID Being Responded To', (0x0000, 0x0120), 'US', 1),
        ('Data Set Type', (0x0000, 0x0800), 'US', 1),
        ('Status', (0x0000, 0x0900), 'US', 1),
        ('Affected SOP Instance UID', (0x0000, 0x1000), 'UI', 1)]
    DataField = 'Attribute List'


class N_ACTION_RQ_Message(DIMSEMessage):
    CommandFields = [
        ('Group Length', (0x0000, 0x0000), 'UL', 1),
        ('Requested SOP Class UID', (0x0000, 0x0003), 'UI', 1),
        ('Command Field', (0x0000, 0x0100), 'US', 1),
        ('Message ID', (0x0000, 0x0110), 'US', 1),
        ('Data Set Type', (0x0000, 0x0800), 'US', 1),
        ('Requested SOP Instance UID', (0x0000, 0x1001), 'UI', 1),
        ('Action Type ID', (0x0000, 0x1008), 'US', 1)]
    DataField = 'Action Information'


class N_ACTION_RSP_Message(DIMSEMessage):
    CommandFields = [
        ('Group Length', (0x0000, 0x0000), 'UL', 1),
        ('Affected SOP Class UID', (0x0000, 0x0002), 'UI', 1),
        ('Command Field', (0x0000, 0x0100), 'US', 1),
        ('Message ID Being Responded To', (0x0000, 0x0120), 'US', 1),
        ('Data Set Type', (0x0000, 0x0800), 'US', 1),
        ('Status', (0x0000, 0x0900), 'US', 1),
        ('Affected SOP Instance UID', (0x0000, 0x1000), 'UI', 1),
        ('Action Type ID', (0x0000, 0x1000), 'UI', 1)]
    DataField = 'Action Reply'


class N_CREATE_RQ_Message(DIMSEMessage):
    CommandFields = [
        ('Group Length', (0x0000, 0x0000), 'UL', 1),
        ('Affected SOP Class UID', (0x0000, 0x0002), 'UI', 1),
        ('Command Field', (0x0000, 0x0100), 'US', 1),
        ('Message ID', (0x0000, 0x0110), 'US', 1),
        ('Data Set Type', (0x0000, 0x0800), 'US', 1),
        ('Affected SOP Instance UID', (0x0000, 0x1000), 'UI', 1)]
    DataField = 'Attribute List'


class N_CREATE_RSP_Message(DIMSEMessage):
    CommandFields = [
        ('Group Length', (0x0000, 0x0000), 'UL', 1),
        ('Affected SOP Class UID', (0x0000, 0x0002), 'UI', 1),
        ('Command Field', (0x0000, 0x0100), 'US', 1),
        ('Message ID Being Responded To', (0x0000, 0x0120), 'US', 1),
        ('Data Set Type', (0x0000, 0x0800), 'US', 1),
        ('Status', (0x0000, 0x0900), 'US', 1),
        ('Affected SOP Instance UID', (0x0000, 0x1000), 'UI', 1)]
    DataField = 'Attribute List'


class N_DELETE_RQ_Message(DIMSEMessage):
    CommandFields = [
        ('Group Length', (0x0000, 0x0000), 'UL', 1),
        ('Requested SOP Class UID', (0x0000, 0x0003), 'UI', 1),
        ('Command Field', (0x0000, 0x0100), 'US', 1),
        ('Message ID', (0x0000, 0x0110), 'US', 1),
        ('Data Set Type', (0x0000, 0x0800), 'US', 1),
        ('Requested SOP Instance UID', (0x0000, 0x1001), 'UI', 1)]


class N_DELETE_RSP_Message(DIMSEMessage):
    CommandFields = [
        ('Group Length', (0x0000, 0x0000), 'UL', 1),
        ('Affected SOP Class UID', (0x0000, 0x0002), 'UI', 1),
        ('Command Field', (0x0000, 0x0100), 'US', 1),
        ('Message ID Being Responded To', (0x0000, 0x0120), 'US', 1),
        ('Data Set Type', (0x0000, 0x0800), 'US', 1),
        ('Status', (0x0000, 0x0900), 'US', 1),
        ('Affected SOP Instance UID', (0x0000, 0x1000), 'UI', 1)]


MessageType = {0x0001 : C_STORE_RQ_Message,
               0x8001 : C_STORE_RSP_Message,
               0x0020 : C_FIND_RQ_Message,
               0x8020 : C_FIND_RSP_Message,
               0x0FFF : C_CANCEL_RQ_Message,
               0x0010 : C_GET_RQ_Message,
               0x8010 : C_GET_RSP_Message,
               0x0021 : C_MOVE_RQ_Message,
               0x8021 : C_MOVE_RSP_Message,
               0x0030 : C_ECHO_RQ_Message,
               0x8030 : C_ECHO_RSP_Message,
               0x0100 : N_EVENT_REPORT_RQ_Message,
               0x8100 : N_EVENT_REPORT_RSP_Message,
               0x0110 : N_GET_RQ_Message,
               0x8110 : N_GET_RSP_Message,
               0x0120 : N_SET_RQ_Message,
               0x8120 : N_SET_RSP_Message,
               0x0130 : N_ACTION_RQ_Message,
               0x8130 : N_ACTION_RSP_Message,
               0x0140 : N_CREATE_RQ_Message,
               0x8140 : N_CREATE_RSP_Message,
               0x0150 : N_DELETE_RQ_Message,
               0x8150 : N_DELETE_RSP_Message}
