#!/usr/bin/env python
"""Test DIMSE-C operations."""

from io import BytesIO
import logging
import unittest

import pytest

from pydicom.dataset import Dataset
from pydicom.uid import UID

from pynetdicom3.dimse_messages import (
    C_STORE_RQ, C_STORE_RSP,C_MOVE_RQ, C_MOVE_RSP, C_ECHO_RQ, C_ECHO_RSP,
    C_FIND_RQ, C_FIND_RSP, C_GET_RQ, C_GET_RSP
)
from pynetdicom3.dimse_primitives import (
    C_ECHO, C_MOVE, C_STORE, C_GET, C_FIND, C_CANCEL
)
from pynetdicom3.dsutils import encode
from pynetdicom3.utils import validate_ae_title
#from pynetdicom3.utils import pretty_bytes
from .encoded_dimse_msg import (
    c_echo_rq_cmd, c_echo_rsp_cmd, c_store_rq_cmd_b, c_store_rq_ds_b,
    c_store_rsp_cmd, c_find_rq_cmd, c_find_rq_ds, c_find_rsp_cmd,
    c_find_rsp_ds, c_get_rq_cmd, c_get_rq_ds, c_get_rsp_cmd, c_get_rsp_ds,
    c_move_rq_cmd, c_move_rq_ds, c_move_rsp_cmd, c_move_rsp_ds
)


LOGGER = logging.getLogger('pynetdicom3')
LOGGER.setLevel(logging.CRITICAL)


class TestPrimitive_C_CANCEL(unittest.TestCase):
    """Test DIMSE C-CANCEL operations."""
    def test_assignment(self):
        """ Check assignment works correctly """
        primitive = C_CANCEL()

        primitive.MessageIDBeingRespondedTo = 13
        self.assertEqual(primitive.MessageIDBeingRespondedTo, 13)
        with self.assertRaises(ValueError):
            primitive.MessageIDBeingRespondedTo = 100000
        with self.assertRaises(TypeError):
            primitive.MessageIDBeingRespondedTo = 'test'


class TestPrimitive_C_STORE(unittest.TestCase):
    """Test DIMSE C-STORE operations."""
    def test_assignment(self):
        """ Check assignment works correctly """
        primitive = C_STORE()

        primitive.MessageID = 11
        self.assertEqual(primitive.MessageID, 11)

        primitive.MessageIDBeingRespondedTo = 13
        self.assertEqual(primitive.MessageIDBeingRespondedTo, 13)

        # AffectedSOPClassUID
        primitive.AffectedSOPClassUID = '1.1.1'
        self.assertEqual(primitive.AffectedSOPClassUID, UID('1.1.1'))
        self.assertTrue(isinstance(primitive.AffectedSOPClassUID, UID))
        primitive.AffectedSOPClassUID = UID('1.1.2')
        self.assertEqual(primitive.AffectedSOPClassUID, UID('1.1.2'))
        self.assertTrue(isinstance(primitive.AffectedSOPClassUID, UID))
        primitive.AffectedSOPClassUID = b'1.1.3'
        self.assertEqual(primitive.AffectedSOPClassUID, UID('1.1.3'))
        self.assertTrue(isinstance(primitive.AffectedSOPClassUID, UID))

        # AffectedSOPInstanceUID
        primitive.AffectedSOPInstanceUID = b'1.2.1'
        self.assertEqual(primitive.AffectedSOPInstanceUID, UID('1.2.1'))
        self.assertTrue(isinstance(primitive.AffectedSOPClassUID, UID))
        primitive.AffectedSOPInstanceUID = UID('1.2.2')
        self.assertEqual(primitive.AffectedSOPInstanceUID, UID('1.2.2'))
        self.assertTrue(isinstance(primitive.AffectedSOPClassUID, UID))
        primitive.AffectedSOPInstanceUID = '1.2.3'
        self.assertEqual(primitive.AffectedSOPInstanceUID, UID('1.2.3'))
        self.assertTrue(isinstance(primitive.AffectedSOPClassUID, UID))

        primitive.Priority = 0x02
        self.assertEqual(primitive.Priority, 0x02)

        primitive.MoveOriginatorApplicationEntityTitle = 'UNITTEST_SCP'
        self.assertEqual(primitive.MoveOriginatorApplicationEntityTitle, b'UNITTEST_SCP    ')
        primitive.MoveOriginatorApplicationEntityTitle = b'UNITTEST_SCP'
        self.assertEqual(primitive.MoveOriginatorApplicationEntityTitle, b'UNITTEST_SCP    ')

        primitive.MoveOriginatorMessageID = 15
        self.assertEqual(primitive.MoveOriginatorMessageID, 15)

        ref_ds = Dataset()
        ref_ds.PatientID = 1234567

        primitive.DataSet = BytesIO(encode(ref_ds, True, True))
        #self.assertEqual(primitive.DataSet, ref_ds)

        primitive.Status = 0x0000
        self.assertEqual(primitive.Status, 0x0000)

        primitive.Status = 0xC123
        self.assertEqual(primitive.Status, 0xC123)

        primitive.Status = 0xEE01
        self.assertEqual(primitive.Status, 0xEE01)

    def test_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        primitive = C_STORE()

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

    def test_conversion_rq(self):
        """ Check conversion to a -RQ PDU produces the correct output """
        primitive = C_STORE()
        primitive.MessageID = 7
        primitive.AffectedSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
        primitive.AffectedSOPInstanceUID = '1.2.392.200036.9116.2.6.1.48.' \
                                           '1215709044.1459316254.522441'
        primitive.Priority = 0x02
        primitive.MoveOriginatorApplicationEntityTitle = 'UNITTEST_SCP'
        primitive.MoveOriginatorMessageID = 3

        ref_ds = Dataset()
        ref_ds.PatientID = 'Test1101'
        ref_ds.PatientName = "Tube HeNe"

        primitive.DataSet = BytesIO(encode(ref_ds, True, True))

        dimse_msg = C_STORE_RQ()
        dimse_msg.primitive_to_message(primitive)

        pdvs = []
        for fragment in dimse_msg.encode_msg(1, 16382):
            pdvs.append(fragment)
        cs_pdv = pdvs[0].presentation_data_value_list[0][1]
        ds_pdv = pdvs[1].presentation_data_value_list[0][1]
        self.assertEqual(cs_pdv, c_store_rq_cmd_b)
        self.assertEqual(ds_pdv, c_store_rq_ds_b)

    def test_conversion_rsp(self):
        """ Check conversion to a -RSP PDU produces the correct output """
        primitive = C_STORE()
        primitive.MessageIDBeingRespondedTo = 5
        primitive.AffectedSOPClassUID = '1.2.4.10'
        primitive.AffectedSOPInstanceUID = '1.2.4.5.7.8'
        primitive.Status = 0x0000

        dimse_msg = C_STORE_RSP()
        dimse_msg.primitive_to_message(primitive)

        pdvs = []
        for fragment in dimse_msg.encode_msg(1, 16382):
            pdvs.append(fragment)
        cs_pdv = pdvs[0].presentation_data_value_list[0][1]
        self.assertEqual(cs_pdv, c_store_rsp_cmd)

    def test_is_valid_request(self):
        """Test C_STORE.is_valid_request"""
        primitive = C_STORE()
        assert not primitive.is_valid_request
        primitive.MessageID = 1
        assert not primitive.is_valid_request
        primitive.AffectedSOPClassUID = '1.2'
        assert not primitive.is_valid_request
        primitive.Priority = 2
        assert not primitive.is_valid_request
        primitive.AffectedSOPInstanceUID = '1.2.1'
        assert not primitive.is_valid_request
        primitive.DataSet = BytesIO()
        assert primitive.is_valid_request

    def test_is_valid_resposne(self):
        """Test C_STORE.is_valid_response."""
        primitive = C_STORE()
        assert not primitive.is_valid_response
        primitive.MessageIDBeingRespondedTo = 1
        assert not primitive.is_valid_response
        primitive.Status = 0x0000
        assert primitive.is_valid_response


class TestPrimitive_C_FIND(unittest.TestCase):
    """Test DIMSE C-FIND operations."""
    def test_assignment(self):
        """ Check assignment works correctly """
        primitive = C_FIND()

        primitive.MessageID = 11
        self.assertEqual(primitive.MessageID, 11)

        primitive.MessageIDBeingRespondedTo = 13
        self.assertEqual(primitive.MessageIDBeingRespondedTo, 13)

        # AffectedSOPClassUID
        primitive.AffectedSOPClassUID = '1.1.1'
        self.assertEqual(primitive.AffectedSOPClassUID, UID('1.1.1'))
        self.assertTrue(isinstance(primitive.AffectedSOPClassUID, UID))
        primitive.AffectedSOPClassUID = UID('1.1.2')
        self.assertEqual(primitive.AffectedSOPClassUID, UID('1.1.2'))
        self.assertTrue(isinstance(primitive.AffectedSOPClassUID, UID))
        primitive.AffectedSOPClassUID = b'1.1.3'
        self.assertEqual(primitive.AffectedSOPClassUID, UID('1.1.3'))
        self.assertTrue(isinstance(primitive.AffectedSOPClassUID, UID))

        primitive.Priority = 0x02
        self.assertEqual(primitive.Priority, 0x02)

        ref_ds = Dataset()
        ref_ds.PatientID = '*'
        ref_ds.QueryRetrieveLevel = "PATIENT"

        primitive.Identifier = BytesIO(encode(ref_ds, True, True))
        #self.assertEqual(primitive.DataSet, ref_ds)

        primitive.Status = 0x0000
        self.assertEqual(primitive.Status, 0x0000)

        primitive.Status = 0xC123
        self.assertEqual(primitive.Status, 0xC123)

        primitive.Status = 0xEE01
        self.assertEqual(primitive.Status, 0xEE01)

    def test_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        primitive = C_FIND()

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

    def test_conversion_rq(self):
        """ Check conversion to a -RQ PDU produces the correct output """
        primitive = C_FIND()
        primitive.MessageID = 7
        primitive.AffectedSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
        primitive.Priority = 0x02

        ref_identifier = Dataset()
        ref_identifier.PatientID = '*'
        ref_identifier.QueryRetrieveLevel = "PATIENT"

        primitive.Identifier = BytesIO(encode(ref_identifier, True, True))

        dimse_msg = C_FIND_RQ()
        dimse_msg.primitive_to_message(primitive)

        pdvs = []
        for fragment in dimse_msg.encode_msg(1, 16382):
            pdvs.append(fragment)
        cs_pdv = pdvs[0].presentation_data_value_list[0][1]
        ds_pdv = pdvs[1].presentation_data_value_list[0][1]
        self.assertEqual(cs_pdv, c_find_rq_cmd)
        self.assertEqual(ds_pdv, c_find_rq_ds)

    def test_conversion_rsp(self):
        """ Check conversion to a -RSP PDU produces the correct output """
        primitive = C_FIND()
        primitive.MessageIDBeingRespondedTo = 5
        primitive.AffectedSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
        primitive.Status = 0xFF00

        ref_identifier = Dataset()
        ref_identifier.QueryRetrieveLevel = "PATIENT"
        ref_identifier.RetrieveAETitle = validate_ae_title("FINDSCP")
        ref_identifier.PatientName = "ANON^A^B^C^D"

        primitive.Identifier = BytesIO(encode(ref_identifier, True, True))

        dimse_msg = C_FIND_RSP()
        dimse_msg.primitive_to_message(primitive)

        pdvs = []
        for fragment in dimse_msg.encode_msg(1, 16382):
            pdvs.append(fragment)
        cs_pdv = pdvs[0].presentation_data_value_list[0][1]
        ds_pdv = pdvs[1].presentation_data_value_list[0][1]
        self.assertEqual(cs_pdv, c_find_rsp_cmd)
        self.assertEqual(ds_pdv, c_find_rsp_ds)

    def test_is_valid_request(self):
        """Test C_FIND.is_valid_request"""
        primitive = C_FIND()
        assert not primitive.is_valid_request
        primitive.MessageID = 1
        assert not primitive.is_valid_request
        primitive.AffectedSOPClassUID = '1.2'
        assert not primitive.is_valid_request
        primitive.Priority = 2
        assert not primitive.is_valid_request
        primitive.Identifier = BytesIO()
        assert primitive.is_valid_request

    def test_is_valid_resposne(self):
        """Test C_FIND.is_valid_response."""
        primitive = C_FIND()
        assert not primitive.is_valid_response
        primitive.MessageIDBeingRespondedTo = 1
        assert not primitive.is_valid_response
        primitive.Status = 0x0000
        assert primitive.is_valid_response


class TestPrimitive_C_GET(unittest.TestCase):
    """Test DIMSE C-GET operations."""
    def test_assignment(self):
        """ Check assignment works correctly """
        primitive = C_GET()

        primitive.MessageID = 11
        self.assertEqual(primitive.MessageID, 11)

        primitive.MessageIDBeingRespondedTo = 13
        self.assertEqual(primitive.MessageIDBeingRespondedTo, 13)

        # AffectedSOPClassUID
        primitive.AffectedSOPClassUID = '1.1.1'
        self.assertEqual(primitive.AffectedSOPClassUID, UID('1.1.1'))
        self.assertTrue(isinstance(primitive.AffectedSOPClassUID, UID))
        primitive.AffectedSOPClassUID = UID('1.1.2')
        self.assertEqual(primitive.AffectedSOPClassUID, UID('1.1.2'))
        self.assertTrue(isinstance(primitive.AffectedSOPClassUID, UID))
        primitive.AffectedSOPClassUID = b'1.1.3'
        self.assertEqual(primitive.AffectedSOPClassUID, UID('1.1.3'))
        self.assertTrue(isinstance(primitive.AffectedSOPClassUID, UID))

        primitive.Priority = 0x02
        self.assertEqual(primitive.Priority, 0x02)

        ref_ds = Dataset()
        ref_ds.PatientID = 1234567

        primitive.Identifier = BytesIO(encode(ref_ds, True, True))
        #self.assertEqual(primitive.DataSet, ref_ds)

        primitive.Status = 0x0000
        self.assertEqual(primitive.Status, 0x0000)

        primitive.Status = 0xC123
        self.assertEqual(primitive.Status, 0xC123)

        primitive.Status = 0xEE01
        self.assertEqual(primitive.Status, 0xEE01)

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
        primitive = C_GET()

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

        # NumberOfRemainingSuboperations
        with self.assertRaises(TypeError):
            primitive.NumberOfRemainingSuboperations = 'halp'
        with self.assertRaises(TypeError):
            primitive.NumberOfRemainingSuboperations = 1.111
        with self.assertRaises(ValueError):
            primitive.NumberOfRemainingSuboperations = -1

        # NumberOfCompletedSuboperations
        with self.assertRaises(TypeError):
            primitive.NumberOfCompletedSuboperations = 'halp'
        with self.assertRaises(TypeError):
            primitive.NumberOfCompletedSuboperations = 1.111
        with self.assertRaises(ValueError):
            primitive.NumberOfCompletedSuboperations = -1

        # NumberOfFailedSuboperations
        with self.assertRaises(TypeError):
            primitive.NumberOfFailedSuboperations = 'halp'
        with self.assertRaises(TypeError):
            primitive.NumberOfFailedSuboperations = 1.111
        with self.assertRaises(ValueError):
            primitive.NumberOfFailedSuboperations = -1

        # NumberOfWarningSuboperations
        with self.assertRaises(TypeError):
            primitive.NumberOfWarningSuboperations = 'halp'
        with self.assertRaises(TypeError):
            primitive.NumberOfWarningSuboperations = 1.111
        with self.assertRaises(ValueError):
            primitive.NumberOfWarningSuboperations = -1

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

    def test_conversion_rq(self):
        """ Check conversion to a -RQ PDU produces the correct output """
        primitive = C_GET()
        primitive.MessageID = 7
        primitive.AffectedSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
        primitive.Priority = 0x02

        ref_identifier = Dataset()
        ref_identifier.PatientID = '*'
        ref_identifier.QueryRetrieveLevel = "PATIENT"

        primitive.Identifier = BytesIO(encode(ref_identifier, True, True))

        dimse_msg = C_GET_RQ()
        dimse_msg.primitive_to_message(primitive)

        pdvs = []
        for fragment in dimse_msg.encode_msg(1, 16382):
            pdvs.append(fragment)
        cs_pdv = pdvs[0].presentation_data_value_list[0][1]
        ds_pdv = pdvs[1].presentation_data_value_list[0][1]
        self.assertEqual(cs_pdv, c_get_rq_cmd)
        self.assertEqual(ds_pdv, c_get_rq_ds)

    def test_conversion_rsp(self):
        """ Check conversion to a -RSP PDU produces the correct output """
        primitive = C_GET()
        primitive.MessageIDBeingRespondedTo = 5
        primitive.AffectedSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
        primitive.Status = 0xFF00
        primitive.NumberOfRemainingSuboperations = 3
        primitive.NumberOfCompletedSuboperations = 1
        primitive.NumberOfFailedSuboperations = 2
        primitive.NumberOfWarningSuboperations = 4

        ref_identifier = Dataset()
        ref_identifier.QueryRetrieveLevel = "PATIENT"
        ref_identifier.PatientID = "*"

        primitive.Identifier = BytesIO(encode(ref_identifier, True, True))

        dimse_msg = C_GET_RSP()
        dimse_msg.primitive_to_message(primitive)

        pdvs = []
        for fragment in dimse_msg.encode_msg(1, 16382):
            pdvs.append(fragment)
        cs_pdv = pdvs[0].presentation_data_value_list[0][1]
        ds_pdv = pdvs[1].presentation_data_value_list[0][1]
        self.assertEqual(cs_pdv, c_get_rsp_cmd)
        self.assertEqual(ds_pdv, c_get_rsp_ds)

    def test_is_valid_request(self):
        """Test C_GET.is_valid_request"""
        primitive = C_GET()
        assert not primitive.is_valid_request
        primitive.MessageID = 1
        assert not primitive.is_valid_request
        primitive.AffectedSOPClassUID = '1.2'
        assert not primitive.is_valid_request
        primitive.Priority = 2
        assert not primitive.is_valid_request
        primitive.Identifier = BytesIO()
        assert primitive.is_valid_request

    def test_is_valid_resposne(self):
        """Test C_GET.is_valid_response."""
        primitive = C_GET()
        assert not primitive.is_valid_response
        primitive.MessageIDBeingRespondedTo = 1
        assert not primitive.is_valid_response
        primitive.Status = 0x0000
        assert primitive.is_valid_response


class TestPrimitive_C_MOVE(unittest.TestCase):
    """Test DIMSE C-MOVE operations."""
    def test_assignment(self):
        """ Check assignment works correctly """
        primitive = C_MOVE()

        primitive.MessageID = 11
        self.assertEqual(primitive.MessageID, 11)

        primitive.MessageIDBeingRespondedTo = 13
        self.assertEqual(primitive.MessageIDBeingRespondedTo, 13)

        # AffectedSOPClassUID
        primitive.AffectedSOPClassUID = '1.1.1'
        self.assertEqual(primitive.AffectedSOPClassUID, UID('1.1.1'))
        self.assertTrue(isinstance(primitive.AffectedSOPClassUID, UID))
        primitive.AffectedSOPClassUID = UID('1.1.2')
        self.assertEqual(primitive.AffectedSOPClassUID, UID('1.1.2'))
        self.assertTrue(isinstance(primitive.AffectedSOPClassUID, UID))
        primitive.AffectedSOPClassUID = b'1.1.3'
        self.assertEqual(primitive.AffectedSOPClassUID, UID('1.1.3'))
        self.assertTrue(isinstance(primitive.AffectedSOPClassUID, UID))

        primitive.Priority = 0x02
        self.assertEqual(primitive.Priority, 0x02)

        primitive.MoveDestination = 'UNITTEST_SCP'
        self.assertEqual(primitive.MoveDestination, b'UNITTEST_SCP    ')

        ref_ds = Dataset()
        ref_ds.PatientID = 1234567

        primitive.Identifier = BytesIO(encode(ref_ds, True, True))
        #self.assertEqual(primitive.DataSet, ref_ds)

        primitive.Status = 0x0000
        self.assertEqual(primitive.Status, 0x0000)

        primitive.Status = 0xC123
        self.assertEqual(primitive.Status, 0xC123)

        primitive.Status = 0xEE01
        self.assertEqual(primitive.Status, 0xEE01)

    def test_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        primitive = C_MOVE()

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

        # NumberOfRemainingSuboperations
        with self.assertRaises(TypeError):
            primitive.NumberOfRemainingSuboperations = 'halp'
        with self.assertRaises(TypeError):
            primitive.NumberOfRemainingSuboperations = 1.111
        with self.assertRaises(ValueError):
            primitive.NumberOfRemainingSuboperations = -1

        # NumberOfCompletedSuboperations
        with self.assertRaises(TypeError):
            primitive.NumberOfCompletedSuboperations = 'halp'
        with self.assertRaises(TypeError):
            primitive.NumberOfCompletedSuboperations = 1.111
        with self.assertRaises(ValueError):
            primitive.NumberOfCompletedSuboperations = -1

        # NumberOfFailedSuboperations
        with self.assertRaises(TypeError):
            primitive.NumberOfFailedSuboperations = 'halp'
        with self.assertRaises(TypeError):
            primitive.NumberOfFailedSuboperations = 1.111
        with self.assertRaises(ValueError):
            primitive.NumberOfFailedSuboperations = -1

        # NumberOfWarningSuboperations
        with self.assertRaises(TypeError):
            primitive.NumberOfWarningSuboperations = 'halp'
        with self.assertRaises(TypeError):
            primitive.NumberOfWarningSuboperations = 1.111
        with self.assertRaises(ValueError):
            primitive.NumberOfWarningSuboperations = -1

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

    def test_conversion_rq(self):
        """ Check conversion to a -RQ PDU produces the correct output """
        primitive = C_MOVE()
        primitive.MessageID = 7
        primitive.AffectedSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
        primitive.Priority = 0x02
        primitive.MoveDestination = validate_ae_title("MOVE_SCP")

        ref_identifier = Dataset()
        ref_identifier.PatientID = '*'
        ref_identifier.QueryRetrieveLevel = "PATIENT"

        primitive.Identifier = BytesIO(encode(ref_identifier, True, True))

        dimse_msg = C_MOVE_RQ()
        dimse_msg.primitive_to_message(primitive)

        pdvs = []
        for fragment in dimse_msg.encode_msg(1, 16382):
            pdvs.append(fragment)

        cs_pdv = pdvs[0].presentation_data_value_list[0][1]
        ds_pdv = pdvs[1].presentation_data_value_list[0][1]
        self.assertEqual(cs_pdv, c_move_rq_cmd)
        self.assertEqual(ds_pdv, c_move_rq_ds)

    def test_conversion_rsp(self):
        """ Check conversion to a -RSP PDU produces the correct output """
        primitive = C_MOVE()
        primitive.MessageIDBeingRespondedTo = 5
        primitive.AffectedSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
        primitive.Status = 0xFF00
        primitive.NumberOfRemainingSuboperations = 3
        primitive.NumberOfCompletedSuboperations = 1
        primitive.NumberOfFailedSuboperations = 2
        primitive.NumberOfWarningSuboperations = 4

        ref_identifier = Dataset()
        ref_identifier.QueryRetrieveLevel = "PATIENT"
        ref_identifier.PatientID = "*"

        primitive.Identifier = BytesIO(encode(ref_identifier, True, True))

        dimse_msg = C_MOVE_RSP()
        dimse_msg.primitive_to_message(primitive)

        pdvs = []
        for fragment in dimse_msg.encode_msg(1, 16382):
            pdvs.append(fragment)
        cs_pdv = pdvs[0].presentation_data_value_list[0][1]
        ds_pdv = pdvs[1].presentation_data_value_list[0][1]
        self.assertEqual(cs_pdv, c_move_rsp_cmd)
        self.assertEqual(ds_pdv, c_move_rsp_ds)

    def test_is_valid_request(self):
        """Test C_MOVE.is_valid_request"""
        primitive = C_MOVE()
        assert not primitive.is_valid_request
        primitive.MessageID = 1
        assert not primitive.is_valid_request
        primitive.AffectedSOPClassUID = '1.2'
        assert not primitive.is_valid_request
        primitive.Priority = 2
        assert not primitive.is_valid_request
        primitive.MoveDestination = b'1234567890123456'
        assert not primitive.is_valid_request
        primitive.Identifier = BytesIO()
        assert primitive.is_valid_request

    def test_is_valid_resposne(self):
        """Test C_MOVE.is_valid_response."""
        primitive = C_MOVE()
        assert not primitive.is_valid_response
        primitive.MessageIDBeingRespondedTo = 1
        assert not primitive.is_valid_response
        primitive.Status = 0x0000
        assert primitive.is_valid_response


class TestPrimitive_C_ECHO(unittest.TestCase):
    """Test DIMSE C-ECHO operations."""
    def test_assignment(self):
        """ Check assignment works correctly """
        primitive = C_ECHO()

        primitive.MessageID = 11
        self.assertEqual(primitive.MessageID, 11)

        primitive.MessageIDBeingRespondedTo = 13
        self.assertEqual(primitive.MessageIDBeingRespondedTo, 13)

        # AffectedSOPClassUID
        primitive.AffectedSOPClassUID = '1.1.1'
        self.assertEqual(primitive.AffectedSOPClassUID, UID('1.1.1'))
        self.assertTrue(isinstance(primitive.AffectedSOPClassUID, UID))
        primitive.AffectedSOPClassUID = UID('1.1.2')
        self.assertEqual(primitive.AffectedSOPClassUID, UID('1.1.2'))
        self.assertTrue(isinstance(primitive.AffectedSOPClassUID, UID))
        primitive.AffectedSOPClassUID = b'1.1.3'
        self.assertEqual(primitive.AffectedSOPClassUID, UID('1.1.3'))
        self.assertTrue(isinstance(primitive.AffectedSOPClassUID, UID))

        # Known status
        primitive.Status = 0x0000
        self.assertEqual(primitive.Status, 0x0000)
        # Unknown status
        primitive.Status = 0x9999
        self.assertEqual(primitive.Status, 0x9999)

        primitive.Status = 0xEE01
        self.assertEqual(primitive.Status, 0xEE01)

    def test_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        primitive = C_ECHO()

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
        with self.assertRaises(TypeError):
            primitive.Status = 19.4

    def test_conversion_rq(self):
        """ Check conversion to a -RQ PDU produces the correct output """
        primitive = C_ECHO()
        primitive.MessageID = 7
        primitive.AffectedSOPClassUID = '1.2.840.10008.1.1'

        dimse_msg = C_ECHO_RQ()
        dimse_msg.primitive_to_message(primitive)

        pdvs = []
        for fragment in dimse_msg.encode_msg(1, 16382):
            pdvs.append(fragment)
        cs_pdv = pdvs[0].presentation_data_value_list[0][1]
        self.assertEqual(cs_pdv, c_echo_rq_cmd)

    def test_conversion_rsp(self):
        """ Check conversion to a -RQ PDU produces the correct output """
        primitive = C_ECHO()
        primitive.MessageIDBeingRespondedTo = 8
        primitive.AffectedSOPClassUID = '1.2.840.10008.1.1'
        primitive.Status = 0x0000

        dimse_msg = C_ECHO_RSP()
        dimse_msg.primitive_to_message(primitive)

        pdvs = []
        for fragment in dimse_msg.encode_msg(1, 16382):
            pdvs.append(fragment)
        cs_pdv = pdvs[0].presentation_data_value_list[0][1]
        self.assertEqual(cs_pdv, c_echo_rsp_cmd)

    def test_is_valid_request(self):
        """Test C_ECHO.is_valid_request"""
        primitive = C_ECHO()
        assert not primitive.is_valid_request
        primitive.MessageID = 1
        assert not primitive.is_valid_request
        primitive.AffectedSOPClassUID = '1.2'
        assert primitive.is_valid_request

    def test_is_valid_resposne(self):
        """Test C_ECHO.is_valid_response."""
        primitive = C_ECHO()
        assert not primitive.is_valid_response
        primitive.MessageIDBeingRespondedTo = 1
        assert not primitive.is_valid_response
        primitive.Status = 0x0000
        assert primitive.is_valid_response

if __name__ == "__main__":
    unittest.main()
