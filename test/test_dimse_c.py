#!/usr/bin/env python

import logging
import unittest
from unittest.mock import patch

from pydicom.uid import UID
from pydicom.dataset import Dataset

from pynetdicom3.DIMSEmessages import *
from pynetdicom3.DIMSEparameters import *
from pynetdicom3.utils import wrap_list


logger = logging.getLogger('pynetdicom3')
handler = logging.NullHandler()
for h in logger.handlers:
    logger.removeHandler(h)
logger.addHandler(handler)
logger.setLevel(logging.ERROR)


class TestPrimitive_C_STORE(unittest.TestCase):
    def test_assignment(self):
        """ Check assignment works correctly """
        primitive = C_STORE_ServiceParameters()

        primitive.MessageID = 11
        self.assertEqual(primitive.MessageID, 11)

        primitive.MessageIDBeingRespondedTo = 13
        self.assertEqual(primitive.MessageIDBeingRespondedTo, 13)

        primitive.AffectedSOPClassUID = '1.2.4.10'
        self.assertEqual(primitive.AffectedSOPClassUID, '1.2.4.10')

        primitive.AffectedSOPInstanceUID = '1.2.4.5.7.8'
        self.assertEqual(primitive.AffectedSOPInstanceUID, '1.2.4.5.7.8')

        primitive.Priority = 0x02
        self.assertEqual(primitive.Priority, 0x02)

        primitive.MoveOriginatorApplicationEntityTitle = 'UNITTEST_SCP'
        self.assertEqual(primitive.MoveOriginatorApplicationEntityTitle, b'UNITTEST_SCP    ')

        primitive.MoveOriginatorMessageID = 15
        self.assertEqual(primitive.MoveOriginatorMessageID, 15)

        refDataset = Dataset()
        refDataset.PatientID = 1234567

        primitive.DataSet = BytesIO(encode(refDataset, True, True))
        #self.assertEqual(primitive.DataSet, refDataset)

        primitive.Status = 0x0000
        self.assertEqual(primitive.Status, 0x0000)

        primitive.Status = 0xC123
        self.assertEqual(primitive.Status, 0xC123)

    def test_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        primitive = C_STORE_ServiceParameters()

        # MessageID
        with self.assertRaises(TypeError):
            primitive.MessageID = 'halp'

        with self.assertRaises(TypeError):
            primitive.MessageID = 1.111

        with self.assertRaises(ValueError):
            primitive.MessageID = 65536

        with self.assertRaises(ValueError):
            primitive.MessageID = -1

        # MessageIDBeingRespondedTo
        with self.assertRaises(TypeError):
            primitive.MessageIDBeingRespondedTo = 'halp'

        with self.assertRaises(TypeError):
            primitive.MessageIDBeingRespondedTo = 1.111

        with self.assertRaises(ValueError):
            primitive.MessageIDBeingRespondedTo = 65536

        with self.assertRaises(ValueError):
            primitive.MessageIDBeingRespondedTo = -1

        # AffectedSOPClassUID
        with self.assertRaises(TypeError):
            primitive.AffectedSOPClassUID = 45.2

        with self.assertRaises(TypeError):
            primitive.AffectedSOPClassUID = 100

        with self.assertRaises(ValueError):
            primitive.AffectedSOPClassUID = 'abc'

        # AffectedSOPInstanceUID
        with self.assertRaises(TypeError):
            primitive.AffectedSOPInstanceUID = 45.2

        with self.assertRaises(TypeError):
            primitive.AffectedSOPInstanceUID = 100

        with self.assertRaises(ValueError):
            primitive.AffectedSOPInstanceUID = 'abc'

        # Priority
        with self.assertRaises(ValueError):
            primitive.Priority = 45.2

        with self.assertRaises(ValueError):
            primitive.Priority = 'abc'

        with self.assertRaises(ValueError):
            primitive.Priority = -1

        with self.assertRaises(ValueError):
            primitive.Priority = 3

        # MoveOriginatorApplicationEntityTitle
        with self.assertRaises(TypeError):
            primitive.MoveOriginatorApplicationEntityTitle = 45.2

        with self.assertRaises(TypeError):
            primitive.MoveOriginatorApplicationEntityTitle = 100

        with self.assertRaises(ValueError):
            primitive.MoveOriginatorApplicationEntityTitle = ''

        with self.assertRaises(ValueError):
            primitive.MoveOriginatorApplicationEntityTitle = '    '

        # MoveOriginatorMessageID
        with self.assertRaises(TypeError):
            primitive.MoveOriginatorMessageID = 'halp'

        with self.assertRaises(TypeError):
            primitive.MoveOriginatorMessageID = 1.111

        with self.assertRaises(ValueError):
            primitive.MoveOriginatorMessageID = 65536

        with self.assertRaises(ValueError):
            primitive.MoveOriginatorMessageID = -1

        # DataSet
        with self.assertRaises(TypeError):
            primitive.DataSet = 'halp'

        with self.assertRaises(TypeError):
            primitive.DataSet = 1.111

        with self.assertRaises(TypeError):
            primitive.DataSet = 50

        with self.assertRaises(TypeError):
            primitive.DataSet = [30, 10]

        # Status
        with self.assertRaises(TypeError):
            primitive.Status = 19.4

        with self.assertRaises(ValueError):
            primitive.Status = 0x0010

    def test_conversion_rq(self):
        """ Check conversion to a -RQ PDU produces the correct output """
        primitive = C_STORE_ServiceParameters()
        primitive.MessageID = 7
        primitive.AffectedSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
        primitive.AffectedSOPInstanceUID = '1.2.392.200036.9116.2.6.1.48.1215709044.1459316254.522441'
        primitive.Priority = 0x02
        primitive.MoveOriginatorApplicationEntityTitle = 'UNITTEST_SCP'
        primitive.MoveOriginatorMessageID = 3

        refDataset = Dataset()
        refDataset.PatientID = 'Test1101'
        refDataset.PatientName = "Tube HeNe"

        primitive.DataSet = BytesIO(encode(refDataset, True, True))

        dimse_msg = C_STORE_RQ()
        dimse_msg.primitive_to_message(primitive)

        pdvs = dimse_msg.Encode(1, 16382)

        # Command Set
        ref = b'\x03\x00\x00\x00\x00\x04\x00\x00\x00\xae\x00\x00\x00\x00\x00\x02' \
              b'\x00\x1a\x00\x00\x00\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30' \
              b'\x30\x38\x2e\x35\x2e\x31\x2e\x34\x2e\x31\x2e\x31\x2e\x32\x00\x00' \
              b'\x00\x00\x01\x02\x00\x00\x00\x01\x00\x00\x00\x10\x01\x02\x00\x00' \
              b'\x00\x07\x00\x00\x00\x00\x07\x02\x00\x00\x00\x02\x00\x00\x00\x00' \
              b'\x08\x02\x00\x00\x00\x01\x00\x00\x00\x00\x10\x3a\x00\x00\x00\x31' \
              b'\x2e\x32\x2e\x33\x39\x32\x2e\x32\x30\x30\x30\x33\x36\x2e\x39\x31' \
              b'\x31\x36\x2e\x32\x2e\x36\x2e\x31\x2e\x34\x38\x2e\x31\x32\x31\x35' \
              b'\x37\x30\x39\x30\x34\x34\x2e\x31\x34\x35\x39\x33\x31\x36\x32\x35' \
              b'\x34\x2e\x35\x32\x32\x34\x34\x31\x00\x00\x00\x30\x10\x10\x00\x00' \
              b'\x00\x55\x4e\x49\x54\x54\x45\x53\x54\x5f\x53\x43\x50\x20\x20\x20' \
              b'\x20\x00\x00\x31\x10\x02\x00\x00\x00\x03\x00'
        self.assertEqual(pdvs[0].presentation_data_value_list[0][1], ref)

        # Dataset
        ref = b'\x02\x10\x00\x10\x00\x0a\x00\x00\x00\x54\x75\x62\x65\x20\x48\x65' \
              b'\x4e\x65\x20\x10\x00\x20\x00\x08\x00\x00\x00\x54\x65\x73\x74\x31' \
              b'\x31\x30\x31'
        self.assertEqual(pdvs[1].presentation_data_value_list[0][1], ref)

    def test_conversion_rsp(self):
        """ Check conversion to a -RSP PDU produces the correct output """
        primitive = C_STORE_ServiceParameters()
        primitive.MessageIDBeingRespondedTo = 5
        primitive.AffectedSOPClassUID = '1.2.4.10'
        primitive.AffectedSOPInstanceUID = '1.2.4.5.7.8'
        primitive.Status = 0x0000

        dimse_msg = C_STORE_RSP()
        dimse_msg.primitive_to_message(primitive)

        pdvs = dimse_msg.Encode(1, 16382)

        # Command Set
        ref = b'\x03\x00\x00\x00\x00\x04\x00\x00\x00\x4c\x00\x00\x00\x00\x00\x02' \
              b'\x00\x08\x00\x00\x00\x31\x2e\x32\x2e\x34\x2e\x31\x30\x00\x00\x00' \
              b'\x01\x02\x00\x00\x00\x01\x80\x00\x00\x20\x01\x02\x00\x00\x00\x05' \
              b'\x00\x00\x00\x00\x08\x02\x00\x00\x00\x01\x01\x00\x00\x00\x09\x02' \
              b'\x00\x00\x00\x00\x00\x00\x00\x00\x10\x0c\x00\x00\x00\x31\x2e\x32' \
              b'\x2e\x34\x2e\x35\x2e\x37\x2e\x38\x00'
        self.assertEqual(pdvs[0].presentation_data_value_list[0][1], ref)


class TestPrimitive_C_FIND(unittest.TestCase):
    def test_assignment(self):
        """ Check assignment works correctly """
        primitive = C_FIND_ServiceParameters()

        primitive.MessageID = 11
        self.assertEqual(primitive.MessageID, 11)

        primitive.MessageIDBeingRespondedTo = 13
        self.assertEqual(primitive.MessageIDBeingRespondedTo, 13)

        primitive.AffectedSOPClassUID = '1.2.4.10'
        self.assertEqual(primitive.AffectedSOPClassUID, '1.2.4.10')

        primitive.Priority = 0x02
        self.assertEqual(primitive.Priority, 0x02)

        refDataset = Dataset()
        refDataset.PatientID = '*'
        refDataset.QueryRetrieveLevel = "PATIENT"

        primitive.Identifier = BytesIO(encode(refDataset, True, True))
        #self.assertEqual(primitive.DataSet, refDataset)

        primitive.Status = 0x0000
        self.assertEqual(primitive.Status, 0x0000)

        primitive.Status = 0xC123
        self.assertEqual(primitive.Status, 0xC123)

    def test_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        primitive = C_FIND_ServiceParameters()

        # MessageID
        with self.assertRaises(TypeError):
            primitive.MessageID = 'halp'

        with self.assertRaises(TypeError):
            primitive.MessageID = 1.111

        with self.assertRaises(ValueError):
            primitive.MessageID = 65536

        with self.assertRaises(ValueError):
            primitive.MessageID = -1

        # MessageIDBeingRespondedTo
        with self.assertRaises(TypeError):
            primitive.MessageIDBeingRespondedTo = 'halp'

        with self.assertRaises(TypeError):
            primitive.MessageIDBeingRespondedTo = 1.111

        with self.assertRaises(ValueError):
            primitive.MessageIDBeingRespondedTo = 65536

        with self.assertRaises(ValueError):
            primitive.MessageIDBeingRespondedTo = -1

        # AffectedSOPClassUID
        with self.assertRaises(TypeError):
            primitive.AffectedSOPClassUID = 45.2

        with self.assertRaises(TypeError):
            primitive.AffectedSOPClassUID = 100

        with self.assertRaises(ValueError):
            primitive.AffectedSOPClassUID = 'abc'

        # Priority
        with self.assertRaises(ValueError):
            primitive.Priority = 45.2

        with self.assertRaises(ValueError):
            primitive.Priority = 'abc'

        with self.assertRaises(ValueError):
            primitive.Priority = -1

        with self.assertRaises(ValueError):
            primitive.Priority = 3

        # Identifier
        with self.assertRaises(TypeError):
            primitive.Identifier = 'halp'

        with self.assertRaises(TypeError):
            primitive.Identifier = 1.111

        with self.assertRaises(TypeError):
            primitive.Identifier = 50

        with self.assertRaises(TypeError):
            primitive.Identifier = [30, 10]

        # Status
        with self.assertRaises(TypeError):
            primitive.Status = 19.4

        with self.assertRaises(ValueError):
            primitive.Status = 0x0010

    def test_conversion_rq(self):
        """ Check conversion to a -RQ PDU produces the correct output """
        primitive = C_FIND_ServiceParameters()
        primitive.MessageID = 7
        primitive.AffectedSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
        primitive.Priority = 0x02

        refIdentifier = Dataset()
        refIdentifier.PatientID = '*'
        refIdentifier.QueryRetrieveLevel = "PATIENT"

        primitive.Identifier = BytesIO(encode(refIdentifier, True, True))

        dimse_msg = C_FIND_RQ()
        dimse_msg.primitive_to_message(primitive)

        pdvs = dimse_msg.Encode(1, 16382)

        ## Command Set
        # \x03 Message Control Header Byte
        #
        # \x00\x00\x04\x00\x00\x00\x4a\x00\x00\x00
        # (0000, 0000) UL [74] # 4, 1 Command Group Length
        #
        # \x00\x00\x00\x02\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30
        # \x30\x38\x2e\x35\x2e\x31\x2e\x34\x2e\x31\x2e\x31\x2e\x32\x00
        # (0000, 0002) UI [1.2.840.10008.5.1.4.1.1.2] #  26, 1 Affected SOP Class UID (if odd length, trailing 0x00)
        #
        # \x00\x00\x00\x01\x02\x00\x00\x00\x20\x00
        # (0000, 0100) US [0x00, 0x20] #  2, 1 Command Field
        #
        # \x00\x00\x10\x01\x02\x00\x00\x00\x07\x00
        # (0000, 0110) US [7] #  2, 1 Message ID
        #
        # \x00\x00\x00\x07\x02\x00\x00\x00\x02\x00
        # (0000, 0700) US [2] #  2, 1 Priority
        #
        # \x00\x00\x00\x08\x02\x00\x00\x00\x01\x00
        # (0000, 0800) US [1] #  2, 1 Command Data Set Type
        ref = b'\x03\x00\x00\x00\x00\x04\x00\x00\x00\x4a\x00\x00\x00\x00\x00\x02' \
              b'\x00\x1a\x00\x00\x00\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30' \
              b'\x30\x38\x2e\x35\x2e\x31\x2e\x34\x2e\x31\x2e\x31\x2e\x32\x00\x00' \
              b'\x00\x00\x01\x02\x00\x00\x00\x20\x00\x00\x00\x10\x01\x02\x00\x00' \
              b'\x00\x07\x00\x00\x00\x00\x07\x02\x00\x00\x00\x02\x00\x00\x00\x00' \
              b'\x08\x02\x00\x00\x00\x01\x00'
        self.assertEqual(pdvs[0].presentation_data_value_list[0][1], ref)

        ## Dataset
        # \x02 Message Control Header Byte
        #
        # \x08\x00\x52\x00\x08\x00\x00\x00\x50\x41\x54\x49\x45\x4e\x54\x20
        # (0008, 0052) CS [PATIENT ] #  8, 1 Query/Retrieve Level (leading/trailing spaces non-significant)
        #
        # \x10\x00\x20\x00\x02\x00\x00\x00\x2a\x20
        # (0010, 0020) LO [* ] #  2, 1 Patient ID (may be padded with leading/trailing spaces)
        ref = b'\x02\x08\x00\x52\x00\x08\x00\x00\x00\x50\x41\x54\x49\x45\x4e\x54' \
              b'\x20\x10\x00\x20\x00\x02\x00\x00\x00\x2a\x20'
        self.assertEqual(pdvs[1].presentation_data_value_list[0][1], ref)

    def test_conversion_rsp(self):
        """ Check conversion to a -RSP PDU produces the correct output """
        primitive = C_FIND_ServiceParameters()
        primitive.MessageIDBeingRespondedTo = 5
        primitive.AffectedSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
        primitive.Status = 0xFF00

        refIdentifier = Dataset()
        refIdentifier.QueryRetrieveLevel = "PATIENT"
        refIdentifier.RetrieveAETitle = validate_ae_title("FINDSCP")
        refIdentifier.PatientName = "ANON^A^B^C^D"

        primitive.Identifier = BytesIO(encode(refIdentifier, True, True))

        dimse_msg = C_FIND_RSP()
        dimse_msg.primitive_to_message(primitive)

        pdvs = dimse_msg.Encode(1, 16382)

        # Command Set
        ref = b'\x03\x00\x00\x00\x00\x04\x00\x00\x00\x4a\x00\x00\x00\x00\x00\x02' \
              b'\x00\x1a\x00\x00\x00\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30' \
              b'\x30\x38\x2e\x35\x2e\x31\x2e\x34\x2e\x31\x2e\x31\x2e\x32\x00\x00' \
              b'\x00\x00\x01\x02\x00\x00\x00\x20\x80\x00\x00\x20\x01\x02\x00\x00' \
              b'\x00\x05\x00\x00\x00\x00\x08\x02\x00\x00\x00\x01\x00\x00\x00\x00' \
              b'\x09\x02\x00\x00\x00\x00\xff'
        self.assertEqual(pdvs[0].presentation_data_value_list[0][1], ref)

        ref = b'\x02\x08\x00\x52\x00\x08\x00\x00\x00\x50\x41\x54\x49\x45\x4e\x54' \
              b'\x20\x08\x00\x54\x00\x10\x00\x00\x00\x46\x49\x4e\x44\x53\x43\x50' \
              b'\x20\x20\x20\x20\x20\x20\x20\x20\x20\x10\x00\x10\x00\x0c\x00\x00' \
              b'\x00\x41\x4e\x4f\x4e\x5e\x41\x5e\x42\x5e\x43\x5e\x44'
        self.assertEqual(pdvs[1].presentation_data_value_list[0][1], ref)


class TestPrimitive_C_GET(unittest.TestCase):
    def test_assignment(self):
        """ Check assignment works correctly """
        primitive = C_GET_ServiceParameters()

        primitive.MessageID = 11
        self.assertEqual(primitive.MessageID, 11)

        primitive.MessageIDBeingRespondedTo = 13
        self.assertEqual(primitive.MessageIDBeingRespondedTo, 13)

        primitive.AffectedSOPClassUID = '1.2.4.10'
        self.assertEqual(primitive.AffectedSOPClassUID, '1.2.4.10')

        primitive.Priority = 0x02
        self.assertEqual(primitive.Priority, 0x02)

        refDataset = Dataset()
        refDataset.PatientID = 1234567

        primitive.Identifier = BytesIO(encode(refDataset, True, True))
        #self.assertEqual(primitive.DataSet, refDataset)

        primitive.Status = 0x0000
        self.assertEqual(primitive.Status, 0x0000)

        primitive.Status = 0xC123
        self.assertEqual(primitive.Status, 0xC123)

        primitive.NumberOfRemainingSuboperations = 1
        self.assertEqual(primitive.NumberOfRemainingSuboperations, 1)

        primitive.NumberOfCompletedSuboperations = 2
        self.assertEqual(primitive.NumberOfCompletedSuboperations, 2)

        primitive.NumberOfFailedSuboperations = 3
        self.assertEqual(primitive.NumberOfFailedSuboperations, 3)

        primitive.NumberOfWarningSuboperations = 4
        self.assertEqual(primitive.NumberOfWarningSuboperations, 4)

    def test_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        primitive = C_GET_ServiceParameters()

        # MessageID
        with self.assertRaises(TypeError):
            primitive.MessageID = 'halp'

        with self.assertRaises(TypeError):
            primitive.MessageID = 1.111

        with self.assertRaises(ValueError):
            primitive.MessageID = 65536

        with self.assertRaises(ValueError):
            primitive.MessageID = -1

        # MessageIDBeingRespondedTo
        with self.assertRaises(TypeError):
            primitive.MessageIDBeingRespondedTo = 'halp'

        with self.assertRaises(TypeError):
            primitive.MessageIDBeingRespondedTo = 1.111

        with self.assertRaises(ValueError):
            primitive.MessageIDBeingRespondedTo = 65536

        with self.assertRaises(ValueError):
            primitive.MessageIDBeingRespondedTo = -1

        # AffectedSOPClassUID
        with self.assertRaises(TypeError):
            primitive.AffectedSOPClassUID = 45.2

        with self.assertRaises(TypeError):
            primitive.AffectedSOPClassUID = 100

        with self.assertRaises(ValueError):
            primitive.AffectedSOPClassUID = 'abc'

        # Priority
        with self.assertRaises(ValueError):
            primitive.Priority = 45.2

        with self.assertRaises(ValueError):
            primitive.Priority = 'abc'

        with self.assertRaises(ValueError):
            primitive.Priority = -1

        with self.assertRaises(ValueError):
            primitive.Priority = 3

        # Identifier
        with self.assertRaises(TypeError):
            primitive.Identifier = 'halp'

        with self.assertRaises(TypeError):
            primitive.Identifier = 1.111

        with self.assertRaises(TypeError):
            primitive.Identifier = 50

        with self.assertRaises(TypeError):
            primitive.Identifier = [30, 10]

        # Status
        with self.assertRaises(TypeError):
            primitive.Status = 19.4

        with self.assertRaises(ValueError):
            primitive.Status = 0x0010

    def test_conversion_rq(self):
        """ Check conversion to a -RQ PDU produces the correct output """
        primitive = C_GET_ServiceParameters()
        primitive.MessageID = 7
        primitive.AffectedSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
        primitive.Priority = 0x02

        refIdentifier = Dataset()
        refIdentifier.PatientID = '*'
        refIdentifier.QueryRetrieveLevel = "PATIENT"

        primitive.Identifier = BytesIO(encode(refIdentifier, True, True))

        dimse_msg = C_GET_RQ()
        dimse_msg.primitive_to_message(primitive)

        pdvs = dimse_msg.Encode(1, 16382)

        # Command Set
        ref = b'\x03\x00\x00\x00\x00\x04\x00\x00\x00\x4a\x00\x00\x00\x00\x00\x02' \
              b'\x00\x1a\x00\x00\x00\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30' \
              b'\x30\x38\x2e\x35\x2e\x31\x2e\x34\x2e\x31\x2e\x31\x2e\x32\x00\x00' \
              b'\x00\x00\x01\x02\x00\x00\x00\x10\x00\x00\x00\x10\x01\x02\x00\x00' \
              b'\x00\x07\x00\x00\x00\x00\x07\x02\x00\x00\x00\x02\x00\x00\x00\x00' \
              b'\x08\x02\x00\x00\x00\x01\x00'
        self.assertEqual(pdvs[0].presentation_data_value_list[0][1], ref)

        # Dataset
        ref = b'\x02\x08\x00\x52\x00\x08\x00\x00\x00\x50\x41\x54\x49\x45\x4e\x54' \
              b'\x20\x10\x00\x20\x00\x02\x00\x00\x00\x2a\x20'
        self.assertEqual(pdvs[1].presentation_data_value_list[0][1], ref)

    def test_conversion_rsp(self):
        """ Check conversion to a -RSP PDU produces the correct output """
        primitive = C_GET_ServiceParameters()
        primitive.MessageIDBeingRespondedTo = 5
        primitive.AffectedSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
        primitive.Status = 0xFF00
        primitive.NumberOfRemainingSuboperations = 3
        primitive.NumberOfCompletedSuboperations = 1
        primitive.NumberOfFailedSuboperations = 2
        primitive.NumberOfWarningSuboperations = 4

        refIdentifier = Dataset()
        refIdentifier.QueryRetrieveLevel = "PATIENT"
        refIdentifier.PatientID = "*"

        primitive.Identifier = BytesIO(encode(refIdentifier, True, True))

        dimse_msg = C_GET_RSP()
        dimse_msg.primitive_to_message(primitive)

        pdvs = dimse_msg.Encode(1, 16382)

        # Command Set
        ref = b'\x03\x00\x00\x00\x00\x04\x00\x00\x00\x72\x00\x00\x00\x00\x00\x02' \
              b'\x00\x1a\x00\x00\x00\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30' \
              b'\x30\x38\x2e\x35\x2e\x31\x2e\x34\x2e\x31\x2e\x31\x2e\x32\x00\x00' \
              b'\x00\x00\x01\x02\x00\x00\x00\x10\x80\x00\x00\x20\x01\x02\x00\x00' \
              b'\x00\x05\x00\x00\x00\x00\x08\x02\x00\x00\x00\x01\x00\x00\x00\x00' \
              b'\x09\x02\x00\x00\x00\x00\xff\x00\x00\x20\x10\x02\x00\x00\x00\x03' \
              b'\x00\x00\x00\x21\x10\x02\x00\x00\x00\x01\x00\x00\x00\x22\x10\x02' \
              b'\x00\x00\x00\x02\x00\x00\x00\x23\x10\x02\x00\x00\x00\x04\x00'
        self.assertEqual(pdvs[0].presentation_data_value_list[0][1], ref)

        # Data Set
        ref = b'\x02\x08\x00\x52\x00\x08\x00\x00\x00\x50\x41\x54\x49\x45\x4e\x54' \
              b'\x20\x10\x00\x20\x00\x02\x00\x00\x00\x2a\x20'
        self.assertEqual(pdvs[1].presentation_data_value_list[0][1], ref)


class TestPrimitive_C_MOVE(unittest.TestCase):
    def test_assignment(self):
        """ Check assignment works correctly """
        primitive = C_MOVE_ServiceParameters()

        primitive.MessageID = 11
        self.assertEqual(primitive.MessageID, 11)

        primitive.MessageIDBeingRespondedTo = 13
        self.assertEqual(primitive.MessageIDBeingRespondedTo, 13)

        primitive.AffectedSOPClassUID = '1.2.4.10'
        self.assertEqual(primitive.AffectedSOPClassUID, '1.2.4.10')

        primitive.Priority = 0x02
        self.assertEqual(primitive.Priority, 0x02)

        primitive.MoveDestination = 'UNITTEST_SCP'
        self.assertEqual(primitive.MoveDestination, b'UNITTEST_SCP    ')

        refDataset = Dataset()
        refDataset.PatientID = 1234567

        primitive.Identifier = BytesIO(encode(refDataset, True, True))
        #self.assertEqual(primitive.DataSet, refDataset)

        primitive.Status = 0x0000
        self.assertEqual(primitive.Status, 0x0000)

        primitive.Status = 0xC123
        self.assertEqual(primitive.Status, 0xC123)

    def test_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        primitive = C_MOVE_ServiceParameters()

        # MessageID
        with self.assertRaises(TypeError):
            primitive.MessageID = 'halp'

        with self.assertRaises(TypeError):
            primitive.MessageID = 1.111

        with self.assertRaises(ValueError):
            primitive.MessageID = 65536

        with self.assertRaises(ValueError):
            primitive.MessageID = -1

        # MessageIDBeingRespondedTo
        with self.assertRaises(TypeError):
            primitive.MessageIDBeingRespondedTo = 'halp'

        with self.assertRaises(TypeError):
            primitive.MessageIDBeingRespondedTo = 1.111

        with self.assertRaises(ValueError):
            primitive.MessageIDBeingRespondedTo = 65536

        with self.assertRaises(ValueError):
            primitive.MessageIDBeingRespondedTo = -1

        # AffectedSOPClassUID
        with self.assertRaises(TypeError):
            primitive.AffectedSOPClassUID = 45.2

        with self.assertRaises(TypeError):
            primitive.AffectedSOPClassUID = 100

        with self.assertRaises(ValueError):
            primitive.AffectedSOPClassUID = 'abc'

        # Priority
        with self.assertRaises(ValueError):
            primitive.Priority = 45.2

        with self.assertRaises(ValueError):
            primitive.Priority = 'abc'

        with self.assertRaises(ValueError):
            primitive.Priority = -1

        with self.assertRaises(ValueError):
            primitive.Priority = 3

        # MoveDestination
        with self.assertRaises(TypeError):
            primitive.MoveDestination = 45.2

        with self.assertRaises(TypeError):
            primitive.MoveDestination = 100

        with self.assertRaises(ValueError):
            primitive.MoveDestination = ''

        with self.assertRaises(ValueError):
            primitive.MoveDestination = '    '

        # Identifier
        with self.assertRaises(TypeError):
            primitive.Identifier = 'halp'

        with self.assertRaises(TypeError):
            primitive.Identifier = 1.111

        with self.assertRaises(TypeError):
            primitive.Identifier = 50

        with self.assertRaises(TypeError):
            primitive.Identifier = [30, 10]

        # Status
        with self.assertRaises(TypeError):
            primitive.Status = 19.4

        with self.assertRaises(ValueError):
            primitive.Status = 0x0010

    def test_conversion_rq(self):
        """ Check conversion to a -RQ PDU produces the correct output """
        primitive = C_MOVE_ServiceParameters()
        primitive.MessageID = 7
        primitive.AffectedSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
        primitive.Priority = 0x02
        primitive.MoveDestination = validate_ae_title("MOVE_SCP")

        refIdentifier = Dataset()
        refIdentifier.PatientID = '*'
        refIdentifier.QueryRetrieveLevel = "PATIENT"

        primitive.Identifier = BytesIO(encode(refIdentifier, True, True))

        dimse_msg = C_MOVE_RQ()
        dimse_msg.primitive_to_message(primitive)

        pdvs = dimse_msg.Encode(1, 16382)

        # Command Set
        ref = b'\x03\x00\x00\x00\x00\x04\x00\x00\x00\x62\x00\x00\x00\x00\x00\x02' \
              b'\x00\x1a\x00\x00\x00\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30' \
              b'\x30\x38\x2e\x35\x2e\x31\x2e\x34\x2e\x31\x2e\x31\x2e\x32\x00\x00' \
              b'\x00\x00\x01\x02\x00\x00\x00\x21\x00\x00\x00\x10\x01\x02\x00\x00' \
              b'\x00\x07\x00\x00\x00\x00\x06\x10\x00\x00\x00\x4d\x4f\x56\x45\x5f' \
              b'\x53\x43\x50\x20\x20\x20\x20\x20\x20\x20\x20\x00\x00\x00\x07\x02' \
              b'\x00\x00\x00\x02\x00\x00\x00\x00\x08\x02\x00\x00\x00\x01\x00'
        self.assertEqual(pdvs[0].presentation_data_value_list[0][1], ref)

        # Dataset
        ref = b'\x02\x08\x00\x52\x00\x08\x00\x00\x00\x50\x41\x54\x49\x45\x4e\x54' \
              b'\x20\x10\x00\x20\x00\x02\x00\x00\x00\x2a\x20'
        self.assertEqual(pdvs[1].presentation_data_value_list[0][1], ref)

    def test_conversion_rsp(self):
        """ Check conversion to a -RSP PDU produces the correct output """
        primitive = C_MOVE_ServiceParameters()
        primitive.MessageIDBeingRespondedTo = 5
        primitive.AffectedSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
        primitive.Status = 0xFF00
        primitive.NumberOfRemainingSuboperations = 3
        primitive.NumberOfCompletedSuboperations = 1
        primitive.NumberOfFailedSuboperations = 2
        primitive.NumberOfWarningSuboperations = 4

        refIdentifier = Dataset()
        refIdentifier.QueryRetrieveLevel = "PATIENT"
        refIdentifier.PatientID = "*"

        primitive.Identifier = BytesIO(encode(refIdentifier, True, True))

        dimse_msg = C_MOVE_RSP()
        dimse_msg.primitive_to_message(primitive)

        pdvs = dimse_msg.Encode(1, 16382)

        # Command Set
        ref = b'\x03\x00\x00\x00\x00\x04\x00\x00\x00\x72\x00\x00\x00\x00\x00\x02' \
              b'\x00\x1a\x00\x00\x00\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30' \
              b'\x30\x38\x2e\x35\x2e\x31\x2e\x34\x2e\x31\x2e\x31\x2e\x32\x00\x00' \
              b'\x00\x00\x01\x02\x00\x00\x00\x21\x80\x00\x00\x20\x01\x02\x00\x00' \
              b'\x00\x05\x00\x00\x00\x00\x08\x02\x00\x00\x00\x01\x00\x00\x00\x00' \
              b'\x09\x02\x00\x00\x00\x00\xff\x00\x00\x20\x10\x02\x00\x00\x00\x03' \
              b'\x00\x00\x00\x21\x10\x02\x00\x00\x00\x01\x00\x00\x00\x22\x10\x02' \
              b'\x00\x00\x00\x02\x00\x00\x00\x23\x10\x02\x00\x00\x00\x04\x00'
        self.assertEqual(pdvs[0].presentation_data_value_list[0][1], ref)

        # Data Set
        ref = b'\x02\x08\x00\x52\x00\x08\x00\x00\x00\x50\x41\x54\x49\x45\x4e\x54' \
              b'\x20\x10\x00\x20\x00\x02\x00\x00\x00\x2a\x20'
        self.assertEqual(pdvs[1].presentation_data_value_list[0][1], ref)


class TestPrimitive_C_ECHO(unittest.TestCase):
    def test_assignment(self):
        """ Check assignment works correctly """
        primitive = C_ECHO_ServiceParameters()

        primitive.MessageID = 11
        self.assertEqual(primitive.MessageID, 11)

        primitive.MessageIDBeingRespondedTo = 13
        self.assertEqual(primitive.MessageIDBeingRespondedTo, 13)

        primitive.AffectedSOPClassUID = '1.2.4.10'
        self.assertEqual(primitive.AffectedSOPClassUID, '1.2.4.10')

        primitive.Status = 0x0000
        self.assertEqual(primitive.Status, 0x0000)

    def test_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        primitive = C_ECHO_ServiceParameters()

        # MessageID
        with self.assertRaises(TypeError):
            primitive.MessageID = 'halp'

        with self.assertRaises(TypeError):
            primitive.MessageID = 1.111

        with self.assertRaises(ValueError):
            primitive.MessageID = 65536

        with self.assertRaises(ValueError):
            primitive.MessageID = -1

        # MessageIDBeingRespondedTo
        with self.assertRaises(TypeError):
            primitive.MessageIDBeingRespondedTo = 'halp'

        with self.assertRaises(TypeError):
            primitive.MessageIDBeingRespondedTo = 1.111

        with self.assertRaises(ValueError):
            primitive.MessageIDBeingRespondedTo = 65536

        with self.assertRaises(ValueError):
            primitive.MessageIDBeingRespondedTo = -1

        # AffectedSOPClassUID
        with self.assertRaises(TypeError):
            primitive.AffectedSOPClassUID = 45.2

        with self.assertRaises(TypeError):
            primitive.AffectedSOPClassUID = 100

        with self.assertRaises(ValueError):
            primitive.AffectedSOPClassUID = 'abc'

        # Status
        with self.assertRaises(ValueError):
            primitive.Status = 19.4

        with self.assertRaises(ValueError):
            primitive.Status = 0x0010

    def test_conversion_rq(self):
        """ Check conversion to a -RQ PDU produces the correct output """
        primitive = C_ECHO_ServiceParameters()
        primitive.MessageID = 7
        primitive.AffectedSOPClassUID = '1.2.840.10008.1.1'

        dimse_msg = C_ECHO_RQ()
        dimse_msg.primitive_to_message(primitive)

        pdvs = dimse_msg.Encode(1, 16382)

        # Command Set
        ref = b'\x03\x00\x00\x00\x00\x04\x00\x00\x00\x38\x00\x00\x00\x00\x00\x02' \
              b'\x00\x12\x00\x00\x00\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30' \
              b'\x30\x38\x2e\x31\x2e\x31\x00\x00\x00\x00\x01\x02\x00\x00\x00\x30' \
              b'\x00\x00\x00\x10\x01\x02\x00\x00\x00\x07\x00\x00\x00\x00\x08\x02' \
              b'\x00\x00\x00\x01\x01'

        self.assertEqual(pdvs[0].presentation_data_value_list[0][1], ref)

    def test_conversion_rsp(self):
        """ Check conversion to a -RQ PDU produces the correct output """
        primitive = C_ECHO_ServiceParameters()
        primitive.MessageIDBeingRespondedTo = 8
        primitive.AffectedSOPClassUID = '1.2.840.10008.1.1'
        primitive.Status = 0x0000

        dimse_msg = C_ECHO_RSP()
        dimse_msg.primitive_to_message(primitive)

        pdvs = dimse_msg.Encode(1, 16382)

        # Command Set
        ref = b'\x03\x00\x00\x00\x00\x04\x00\x00\x00\x42\x00\x00\x00\x00\x00\x02' \
              b'\x00\x12\x00\x00\x00\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30' \
              b'\x30\x38\x2e\x31\x2e\x31\x00\x00\x00\x00\x01\x02\x00\x00\x00\x30' \
              b'\x80\x00\x00\x20\x01\x02\x00\x00\x00\x08\x00\x00\x00\x00\x08\x02' \
              b'\x00\x00\x00\x01\x01\x00\x00\x00\x09\x02\x00\x00\x00\x00\x00'

        self.assertEqual(pdvs[0].presentation_data_value_list[0][1], ref)


if __name__ == "__main__":
    unittest.main()
