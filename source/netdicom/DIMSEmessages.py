#
# Copyright (c) 2012 Patrice Munger
# This file is part of pynetdicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pynetdicom.googlecode.com
#

from DIMSEparameters import *
from DULparameters import *
from dicom.dataset import Dataset
import dsutils
from struct import pack, unpack
from dicom.UID import ImplicitVRLittleEndian
#
#  pydicom's dictionnary misses command tags. Add them.
#
from dicom._dicom_dict import DicomDictionary
import itertools

import logging

logger = logging.getLogger('netdicom.DIMSE')


DicomDictionary.update({

    0x00000000: ('UL', '1', "CommandGroupLength", ''),
    0x00000002: ('UI', '1', "Affected SOP class", ''),
    0x00000003: ('UI', '1', "RequestedSOPClassUID", ''),
    0x00000100: ('US', '1', "CommandField", ''),
    0x00000110: ('US', '1', "MessageID", ''),
    0x00000120: ('US', '1', "MessageIDBeingRespondedTo", ''),
    0x00000600: ('AE', '1', "MoveDestination", ''),
    0x00000700: ('US', '1', "Priority", ''),
    0x00000800: ('US', '1', "DataSetType", ''),
    0x00000900: ('US', '1', "Status", ''),
    0x00000901: ('AT', '1', "OffendingElement", ''),
    0x00000902: ('LO', '1', "ErrorComment", ''),
    0x00000903: ('US', '1', "ErrorID", ''),
    0x00001000: ('UI', '1', " AffectedSOPInstanceUID", ''),
    0x00001001: ('UI', '1', "RequestedSOPInstanceUID", ''),
    0x00001002: ('US', '1', "EventTypeID", ''),
    0x00001005: ('AT', '1', "AttributeIdentifierList", ''),
    0x00001008: ('US', '1', "ActionTypeID", ''),
    0x00001020: ('US', '1', "NumberOfRemainingSuboperations", ''),
    0x00001021: ('US', '1', "NumberOfCompletedSuboperations", ''),
    0x00001022: ('US', '1', "NumberOfFailedSuboperations", ''),
    0x00001023: ('US', '1', "NumberOfWarningSuboperations", ''),
    0x00001030: ('AE', '1', "MoveOriginatorApplicationEntityTitle", ''),
    0x00001031: ('US', '1', "MoveOriginatorMessageID", ''),

})


"""
    All DIMSE Message classes implement the following methods:

      FromParams(DIMSEServiceParameter)    :  Builds a DIMSE message from a
                                              DULServiceParameter
                                              object. Used when receiving
                                              primitives from the
                                              DIMSEServiceUser.
      ToParams()                           :  Convert the Message into a
                                              DIMSEServiceParameter object.
                                              Used for sending primitives to
                                              the DIMSEServiceUser.
      Encode()                             :  Returns the encoded message in
                                              one or several P-DATA parameters
                                              structure.
      Decode(pdata)                        :  Construct the message from one
                                              or several P-DATA primitives

                          FromParams               Encode
  |----------------------| ------->  |----------| -------> |---------------|
  | Service parameters   |           |   DIMSE  |          |     P-DATA    |
  |      object          |           |  message |          |  primitive(s) |
  |______________________| <-------  |__________| <------- |_______________|
                           ToParams                Decode
"""

DEBUG = False


def fragment(maxpdulength, str):
    s = str
    fragments = []
    maxsize = maxpdulength - 6
    while 1:
        fragments.append(s[:maxsize])
        s = s[maxsize:]
        if len(s) <= maxsize:
            if len(s) > 0:
                fragments.append(s)
            return fragments


class DIMSEMessage:

    def __init__(self):
        self.CommandSet = None
        self.EncodedDataSet = None
        self.DataSet = ''
        self.encoded_command_set = ''
        self.ID = id

        self.ts = ImplicitVRLittleEndian  # imposed by standard.
        if self.__class__ != DIMSEMessage:
            self.CommandSet = Dataset()
            for ii in self.CommandFields:
                self.CommandSet.add_new(ii[1], ii[2], '')

    def Encode(self, id, maxpdulength):
        """Returns the encoded message as a series of P-DATA service
        parameter objects"""
        self.ID = id
        pdatas = []
        encoded_command_set = dsutils.encode(
            self.CommandSet, self.ts.is_implicit_VR, self.ts.is_little_endian)

        # fragment command set
        pdvs = fragment(maxpdulength, encoded_command_set)
        assert ''.join(pdvs) == encoded_command_set
        for ii in pdvs[:-1]:
            # send only one pdv per pdata primitive
            pdata = P_DATA_ServiceParameters()
            # not last command fragment
            pdata.PresentationDataValueList = [[self.ID, pack('b', 1) + ii]]
            pdatas.append(pdata)
        # last command fragment
        pdata = P_DATA_ServiceParameters()
        # last command fragment
        pdata.PresentationDataValueList = [[self.ID, pack('b', 3) + pdvs[-1]]]
        pdatas.append(pdata)

        # fragment data set
        #if self.__dict__.has_key('DataSet') and self.DataSet:
        if 'DataSet' in self.DataSet:
            pdvs = fragment(maxpdulength, self.DataSet)
            assert ''.join(pdvs) == self.DataSet
            for ii in pdvs[:-1]:
                pdata = P_DATA_ServiceParameters()
                # not last data fragment
                pdata.PresentationDataValueList = [
                    [self.ID, pack('b', 0) + ii]]
                pdatas.append(pdata)
            pdata = P_DATA_ServiceParameters()
            # last data fragment
            pdata.PresentationDataValueList = [
                [self.ID, pack('b', 2) + pdvs[-1]]]
            pdatas.append(pdata)

        return pdatas

    def Decode(self, pdata):
        """Constructs itself receiving a series of P-DATA primitives.
        Returns True when complete, False otherwise."""
        if pdata.__class__ != P_DATA_ServiceParameters:
            # not a pdata
            return False
        if pdata is None:
            return False
        ii = pdata
        for vv in ii.PresentationDataValueList:
            # must be able to read P-DATA with several PDVs
            self.ID = vv[0]
            if unpack('b', vv[1][0])[0] in (1, 3):
                logger.debug("  command fragment %s", self.ID)
                self.encoded_command_set += vv[1][1:]
                if unpack('b', vv[1][0])[0] == 3:
                    logger.debug("  last command fragment %s", self.ID)
                    self.CommandSet = dsutils.decode(
                        self.encoded_command_set, self.ts.is_implicit_VR,
                        self.ts.is_little_endian)
                    self.__class__ = MessageType[
                        self.CommandSet[(0x0000, 0x0100)].value]
                    if self.CommandSet[(0x0000, 0x0800)].value == 0x0101:
                        # response: no dataset
                        return True
            elif unpack('b', vv[1][0])[0] in (0, 2):
                self.DataSet += vv[1][1:]
                logger.debug("  data fragment %s", self.ID)
                if unpack('b', vv[1][0])[0] == 2:
                    logger.debug("  last data fragment %s", self.ID)
                    return True
            else:
                raise "Error"

        return False

    def SetLength(self):
        # compute length
        l = 0
        for ii in self.CommandSet.values()[1:]:
            l += len(dsutils.encode_element(ii,
                                            self.ts.is_implicit_VR,
                                            self.ts.is_little_endian))
        # if self.DataSet<>None:
        #    l += len(self.DataSet)
        self.CommandSet[(0x0000, 0x0000)].value = l

    def __repr__(self):
        return str(self.CommandSet) + '\n'


class C_ECHO_RQ_Message(DIMSEMessage):
    CommandFields = [
        ('Group Length',
         (0x0000, 0x0000), 'UL', 1),
        ('Affected SOP Class UID',
         (0x0000, 0x0002), 'UI', 1),
        ('Command Field',
         (0x0000, 0x0100), 'US', 1),
        ('Message ID',
         (0x0000, 0x0110), 'US', 1),
        ('Data Set Type',                            (0x0000, 0x0800), 'US', 1)
    ]
    DataField = None

    def FromParams(self, params):
        self.CommandSet[(0x0000, 0x0002)].value = params.AffectedSOPClassUID
        self.CommandSet[(0x0000, 0x0100)].value = 0x0030
        self.CommandSet[(0x0000, 0x0110)].value = params.MessageID
        self.CommandSet[(0x0000, 0x0800)].value = 0x0101
        self.DataSet = None
        self.SetLength()

    def ToParams(self):
        tmp = C_ECHO_ServiceParameters()
        tmp.MessageID = self.CommandSet[(0x0000, 0x0110)]
        tmp.AffectedSOPClassUID = self.CommandSet[(0x0000, 0x0002)]
        return tmp


class C_ECHO_RSP_Message(DIMSEMessage):
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
        ('Status',                                   (0x0000, 0x0900), 'US', 1)
    ]
    DataField = None

    def FromParams(self, params):
        if params.AffectedSOPClassUID:
            self.CommandSet[(0x0000, 0x0002)
                            ].value = params.AffectedSOPClassUID
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
        ('Affected SOP Instance UID',
         (0x0000, 0x1000), 'UI', 1),
        ('Move Originator Application Entity Title',
         (0x0000, 0x1030), 'AE', 1),
        ('Move Originator Message ID',
         (0x0000, 0x1031), 'US', 1),
    ]
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
        self.DataSet = None
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
    CommandFields = [
        ('Group Length',
         (0x0000, 0x0000), 'UL', 1),
        ('Affected SOP Class UID',
         (0x0000, 0x0002), 'UI', 1),
        ('Command Field',
         (0x0000, 0x0100), 'US', 1),
        ('Message ID',
         (0x0000, 0x0110), 'US', 1),
        ('Data Set Type',
         (0x0000, 0x0800), 'US', 1),
        ('Priority',
         (0x0000, 0x0700), 'US', 1),
    ]
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
        ('Number of Remaining Sub-operations',
         (0x0000, 0x1020), 'US', 1),
        ('Number of Complete Sub-operations',
         (0x0000, 0x1021), 'US', 1),
        ('Number of Failed Sub-operations',      (0x0000, 0x1022), 'US', 1),
        ('Number of Warning Sub-operations',
         (0x0000, 0x1023), 'US', 1),

    ]
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
        ('Number of Remaining Sub-operations',
         (0x0000, 0x1020), 'US', 1),
        ('Number of Complete Sub-operations',
         (0x0000, 0x1021), 'US', 1),
        ('Number of Failed Sub-operations',      (0x0000, 0x1022), 'US', 1),
        ('Number of Warning Sub-operations',
         (0x0000, 0x1023), 'US', 1),

    ]
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
        tmp = C_Find_ServiceParameters()
        tmp.MessageIDBeingRespondedTo = self.CommandSet[(0x0000, 0x0120)]
        return tmp


class C_CANCEL_GET_RQ_Message(C_CANCEL_RQ_Message):

    def ToParams(self):
        tmp = C_Get_ServiceParameters()
        tmp.MessageIDBeingRespondedTo = self.CommandSet[(0x0000, 0x0120)]
        return tmp


class C_CANCEL_MOVE_RQ_Message(C_CANCEL_RQ_Message):

    def ToParams(self):
        tmp = C_Move_ServiceParameters()
        tmp.MessageIDBeingRespondedTo = self.CommandSet[(0x0000, 0x0120)]
        return tmp


MessageType = {
    0x0001: C_STORE_RQ_Message,
    0x8001: C_STORE_RSP_Message,
    0x0020: C_FIND_RQ_Message,
    0x8020: C_FIND_RSP_Message,
    0x0FFF: C_CANCEL_RQ_Message,
    0x0010: C_GET_RQ_Message,
    0x8010: C_GET_RSP_Message,
    0x0021: C_MOVE_RQ_Message,
    0x8021: C_MOVE_RSP_Message,
    0x0030: C_ECHO_RQ_Message,
    0x8030: C_ECHO_RSP_Message
}


if __name__ == '__main__':

    c = C_ECHO_ServiceParameters()
    c.MessageID = 0
    c.AffectedSOPClassUID = '12.1232.23.123.231.'

    C_ECHO_msg = C_ECHO_RQ_Message()
    C_ECHO_msg.FromParams(c)
    print C_ECHO_msg
    print C_ECHO_msg.ToParams()
    print C_ECHO_msg.Encode(1, 100)
