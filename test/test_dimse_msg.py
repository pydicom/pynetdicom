"""Unit tests for the DIMSE Message classes."""

from io import BytesIO
import logging
import unittest

from pydicom.dataset import Dataset
from pydicom.uid import UID

from encoded_dimse_msg import c_store_rq_cmd, c_store_ds
from pynetdicom3.DIMSEmessages import C_STORE_RQ, C_STORE_RSP, DIMSEMessage, \
                                      C_ECHO_RQ, C_FIND_RQ, C_MOVE_RQ, C_GET_RQ
from pynetdicom3.DIMSEparameters import C_STORE_ServiceParameters, \
                                        C_ECHO_ServiceParameters, \
                                        C_GET_ServiceParameters, \
                                        C_MOVE_ServiceParameters, \
                                        C_FIND_ServiceParameters
from pynetdicom3.dsutils import encode
from pynetdicom3.utils import wrap_list

LOGGER = logging.getLogger('pynetdicom3')
LOGGER.setLevel(logging.CRITICAL)


def print_nice_bytes(bytestream):
    """Nice output for bytestream."""
    str_list = wrap_list(bytestream, prefix="b'\\x", delimiter='\\x',
                        items_per_line=10)
    for string in str_list:
        print(string)


class TestDIMSEMessage(unittest.TestCase):
    """Test DIMSEMessage class"""
    def test_encode(self):
        """Test encoding of a DIMSE message."""
        primitive = C_STORE_ServiceParameters()
        primitive.MessageID = 7
        primitive.AffectedSOPClassUID = '1.1.1'
        primitive.AffectedSOPInstanceUID = '1.2.1'
        primitive.Priority = 0x02
        primitive.MoveOriginatorApplicationEntityTitle = 'UNITTEST'
        primitive.MoveOriginatorMessageID = 3

        # Test encode without dataset
        dimse_msg = C_STORE_RQ()
        dimse_msg.primitive_to_message(primitive)
        p_data_list = dimse_msg.Encode(12, 16)
        self.assertEqual(p_data_list[0].presentation_data_value_list[0][1][0], 1)
        self.assertEqual(p_data_list[-1].presentation_data_value_list[0][1][0], 3)
        self.assertEqual(dimse_msg.ID, 12)

        # Test encode with dataset
        ds = Dataset()
        ds.PatientID = 'Test1101'
        ds.PatientName = 'Tube^HeNe'
        primitive.DataSet = BytesIO(encode(ds, True, True))

        dimse_msg = C_STORE_RQ()
        dimse_msg.primitive_to_message(primitive)
        p_data_list = dimse_msg.Encode(13, 16)
        self.assertEqual(p_data_list[0].presentation_data_value_list[0][1][0], 1)
        self.assertEqual(p_data_list[-1].presentation_data_value_list[0][1][0], 2)
        self.assertEqual(p_data_list[-2].presentation_data_value_list[0][1][0], 0)
        self.assertEqual(p_data_list[-5].presentation_data_value_list[0][1][0], 3)
        self.assertEqual(dimse_msg.ID, 13)

        p_data_list = dimse_msg.Encode(1, 31682)
        self.assertEqual(p_data_list[0].presentation_data_value_list[0][1], c_store_rq_cmd)
        self.assertEqual(p_data_list[1].presentation_data_value_list[0][1], c_store_ds)

    def test_decode(self):
        """Test decoding of a DIMSE message."""
        primitive = C_STORE_ServiceParameters()
        primitive.MessageID = 7
        primitive.AffectedSOPClassUID = '1.1.1'
        primitive.AffectedSOPInstanceUID = '1.2.1'
        primitive.Priority = 0x02
        primitive.MoveOriginatorApplicationEntityTitle = b'UNITTEST'
        primitive.MoveOriginatorMessageID = 3
        ds = Dataset()
        ds.PatientID = 'Test1101'
        ds.PatientName = 'Tube^HeNe'
        primitive.DataSet = BytesIO(encode(ds, True, True))
        dimse_msg = C_STORE_RQ()
        dimse_msg.primitive_to_message(primitive)

        # CMD: (1x4, 3x1), DS: (0x1, 2x1)
        p_data_list = dimse_msg.Encode(12, 30)

        # Command set decoding
        for pdv in p_data_list[:4]:
            dimse_msg.Decode(pdv) # MCHB 1
        dimse_msg.Decode(p_data_list[4]) # MCHB 3 - end of command set
        self.assertEqual(dimse_msg.__class__, C_STORE_RQ)

        # Test decoded command set
        cs = dimse_msg.command_set
        self.assertTrue(cs.CommandGroupLength == 102)
        self.assertTrue(cs.AffectedSOPClassUID == UID('1.1.1'))
        self.assertTrue(cs.AffectedSOPInstanceUID == UID('1.2.1'))
        self.assertTrue(cs.Priority == 2)
        self.assertTrue(cs.CommandDataSetType == 1)
        self.assertTrue(cs.CommandField == 1)
        # Bug in pydicom -> AEs not stripped of trailing spaces
        self.assertTrue(cs.MoveOriginatorApplicationEntityTitle == 'UNITTEST       ')
        self.assertTrue(cs.MoveOriginatorMessageID == 3)

        # Test decoded dataset
        dimse_msg.Decode(p_data_list[5]) # MCHB 0
        dimse_msg.Decode(p_data_list[6]) # MCHB 2
        self.assertTrue(dimse_msg.data_set.getvalue() == c_store_ds[1:])

    def test_primitive_to_message(self):
        """Test converting a DIMSE primitive to a DIMSE message."""
        primitive = C_STORE_ServiceParameters()
        primitive.MessageID = 7
        primitive.AffectedSOPClassUID = '1.1.1'
        primitive.AffectedSOPInstanceUID = '1.2.1'
        primitive.Priority = 0x02
        msg = C_STORE_RQ()
        msg.primitive_to_message(primitive)
        # Test unused command set elements are deleted
        self.assertFalse('MoveOriginatorApplicationEntityTitle' in msg.command_set)

        # Test raise error for unknown DIMSE message type
        msg.__class__.__name__ = 'TestClass'
        with self.assertRaises(ValueError):
            msg.primitive_to_message(primitive)

    def test_message_to_primitive_c_store(self):
        """Test converting C_STORE_RQ to C_STORE primitive."""
        msg = C_STORE_RQ()

    def test_message_to_primitive_c_echo(self):
        """Test converting C_ECHO_RQ to C_ECHO primitive."""
        msg = C_ECHO_RQ()

    def test_message_to_primitive_c_get(self):
        """Test converting C_GET_RQ to C_GET primitive."""
        msg = C_GET_RQ()

    def test_message_to_primitive_c_move(self):
        """Test converting C_MOVE_RQ to C_MOVE primitive."""
        msg = C_MOVE_RQ()

    def test_message_to_primitive_c_find(self):
        """Test converting C_FIND_RQ to C_FIND primitive."""
        msg = C_FIND_RQ()

if __name__ == "__main__":
    unittest.main()
