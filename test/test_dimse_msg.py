"""Unit tests for the DIMSE Message classes."""

from io import BytesIO
import logging
import unittest

from pydicom.dataset import Dataset
from pydicom.uid import UID

from encoded_dimse_msg import c_echo_rq_cmd, c_echo_rsp_cmd, \
                              c_store_rq_cmd, c_store_ds, \
                              c_store_rsp_cmd, \
                              c_find_rq_cmd, c_find_rq_ds, \
                              c_find_rsp_cmd, c_find_rsp_ds, \
                              c_get_rq_cmd, c_get_rq_ds, \
                              c_get_rsp_cmd, c_get_rsp_ds, \
                              c_move_rq_cmd, c_move_rq_ds, \
                              c_move_rsp_cmd, c_move_rsp_ds
from pynetdicom3.DIMSEmessages import C_STORE_RQ, C_STORE_RSP, DIMSEMessage, \
                                      C_ECHO_RQ, C_ECHO_RSP, \
                                      C_FIND_RQ, C_FIND_RSP, \
                                      C_MOVE_RQ, C_MOVE_RSP, \
                                      C_GET_RQ, C_GET_RSP
from pynetdicom3.DIMSEparameters import C_STORE_ServiceParameters, \
                                        C_ECHO_ServiceParameters, \
                                        C_GET_ServiceParameters, \
                                        C_MOVE_ServiceParameters, \
                                        C_FIND_ServiceParameters
from pynetdicom3.dsutils import encode, decode
from pynetdicom3.primitives import P_DATA
from pynetdicom3.utils import wrap_list

LOGGER = logging.getLogger('pynetdicom3')
LOGGER.setLevel(logging.CRITICAL)

def print_nice_bytes(bytestream):
    """Nice output for bytestream."""
    str_list = wrap_list(bytestream, prefix="b'\\x", delimiter='\\x',
                        items_per_line=10, suffix="' \\")
    for string in str_list:
        print(string)


class TestDIMSEMessage(unittest.TestCase):
    """Test DIMSEMessage class"""
    def test_fragment_pdv(self):
        """Test that the PDV fragmenter is working correctly."""
        dimse_msg = C_STORE_RQ()
        frag = dimse_msg._fragment_pdv

        result = frag(c_echo_rsp_cmd, 1000)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], c_echo_rsp_cmd)
        self.assertTrue(isinstance(result[0], bytes))
        self.assertTrue(result[-1] != b'')

        result = frag(c_echo_rsp_cmd, 10)
        self.assertEqual(len(result), 8)
        self.assertEqual(result[0], c_echo_rsp_cmd[:10])
        self.assertTrue(isinstance(result[0], bytes))
        self.assertTrue(result[-1] != b'')

        byteio = BytesIO()
        byteio.write(c_echo_rsp_cmd)
        result = frag(byteio, 1000)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], c_echo_rsp_cmd)
        self.assertTrue(isinstance(result[0], bytes))

        with self.assertRaises(TypeError):
            frag([], 10)
        with self.assertRaises(TypeError):
            frag(c_echo_rsp_cmd, 'test')
        with self.assertRaises(ValueError):
            frag(c_echo_rsp_cmd, 0)

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
        p_data_list = dimse_msg.Encode(13, 10)
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
        p_data_list = dimse_msg.Encode(12, 24)

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

        # Test returns false
        msg = C_STORE_RSP()
        self.assertFalse(msg.Decode(c_store_rsp_cmd))

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
        
        # Reset name to avoid errors in other tests
        msg.__class__.__name__ = 'C_STORE_RQ'
        

    def test_message_to_primitive_c_store(self):
        """Test converting C_STORE_RQ and _RSP to C_STORE primitive."""
        msg = C_STORE_RQ()
        for data in [c_store_rq_cmd, c_store_ds]:
            p_data = P_DATA()
            p_data.presentation_data_value_list.append([0, data])
            msg.Decode(p_data)
        primitive = msg.message_to_primitive()
        self.assertTrue(isinstance(primitive, C_STORE_ServiceParameters))
        self.assertTrue(isinstance(primitive.DataSet, BytesIO))
        self.assertTrue(primitive.AffectedSOPClassUID == UID('1.1.1'))
        self.assertTrue(primitive.AffectedSOPInstanceUID == UID('1.2.1'))
        self.assertTrue(primitive.Priority == 2)
        self.assertTrue(primitive.MoveOriginatorApplicationEntityTitle == b'UNITTEST        ')
        self.assertTrue(primitive.MoveOriginatorMessageID == 3)

        ds = decode(primitive.DataSet, True, True)
        self.assertEqual(ds.PatientName, 'Tube^HeNe')
        self.assertEqual(ds.PatientID, 'Test1101')

        msg = C_STORE_RSP()
        p_data = P_DATA()
        p_data.presentation_data_value_list.append([0, c_store_rsp_cmd])
        msg.Decode(p_data)
        primitive = msg.message_to_primitive()
        self.assertTrue(isinstance(primitive, C_STORE_ServiceParameters))
        self.assertEqual(primitive.DataSet, None)
        for elem in msg.command_set:
            if hasattr(primitive, elem.keyword):
                item = getattr(primitive, elem.keyword)
                self.assertEqual(item, elem.value)

    def test_message_to_primitive_c_echo(self):
        """Test converting C_ECHO_RQ to C_ECHO primitive."""
        msg = C_ECHO_RQ()
        p_data = P_DATA()
        p_data.presentation_data_value_list.append([0, c_echo_rq_cmd])
        msg.Decode(p_data)
        primitive = msg.message_to_primitive()
        self.assertTrue(isinstance(primitive, C_ECHO_ServiceParameters))
        self.assertTrue(primitive.AffectedSOPClassUID == UID('1.2.840.10008.1.1'))
        self.assertTrue(primitive.MessageID == 7)

        msg = C_ECHO_RSP()
        p_data = P_DATA()
        p_data.presentation_data_value_list.append([0, c_echo_rsp_cmd])
        msg.Decode(p_data)
        primitive = msg.message_to_primitive()
        self.assertTrue(isinstance(primitive, C_ECHO_ServiceParameters))
        self.assertTrue(primitive.AffectedSOPClassUID == UID('1.2.840.10008.1.1'))
        self.assertTrue(primitive.MessageIDBeingRespondedTo == 8)
        self.assertTrue(primitive.Status == 0)

    def test_message_to_primitive_c_get(self):
        """Test converting C_GET_RQ to C_GET primitive."""
        msg = C_GET_RQ()
        for data in [c_get_rq_cmd, c_get_rq_ds]:
            p_data = P_DATA()
            p_data.presentation_data_value_list.append([0, data])
            msg.Decode(p_data)
        primitive = msg.message_to_primitive()
        self.assertTrue(isinstance(primitive, C_GET_ServiceParameters))
        self.assertTrue(isinstance(primitive.Identifier, BytesIO))
        self.assertTrue(primitive.AffectedSOPClassUID == UID('1.2.840.10008.5.1.4.1.1.2'))
        self.assertTrue(primitive.Priority == 2)
        self.assertTrue(primitive.MessageID == 7)

        ds = decode(primitive.Identifier, True, True)
        self.assertEqual(ds.QueryRetrieveLevel, 'PATIENT')
        self.assertEqual(ds.PatientID, '*')

        msg = C_GET_RSP()
        for data in [c_get_rsp_cmd, c_get_rsp_ds]:
            p_data = P_DATA()
            p_data.presentation_data_value_list.append([0, data])
            msg.Decode(p_data)
        primitive = msg.message_to_primitive()
        self.assertTrue(isinstance(primitive, C_GET_ServiceParameters))
        self.assertTrue(isinstance(primitive.Identifier, BytesIO))
        self.assertTrue(primitive.AffectedSOPClassUID == UID('1.2.840.10008.5.1.4.1.1.2'))
        self.assertTrue(primitive.Status == 65280)
        self.assertTrue(primitive.MessageIDBeingRespondedTo == 5)
        self.assertTrue(primitive.NumberOfRemainingSuboperations == 3)
        self.assertTrue(primitive.NumberOfCompletedSuboperations == 1)
        self.assertTrue(primitive.NumberOfFailedSuboperations == 2)
        self.assertTrue(primitive.NumberOfWarningSuboperations == 4)

        ds = decode(primitive.Identifier, True, True)
        self.assertEqual(ds.QueryRetrieveLevel, 'PATIENT')
        self.assertEqual(ds.PatientID, '*')

    def test_message_to_primitive_c_move(self):
        """Test converting C_MOVE_RQ to C_MOVE primitive."""
        msg = C_MOVE_RQ()
        for data in [c_move_rq_cmd, c_move_rq_ds]:
            p_data = P_DATA()
            p_data.presentation_data_value_list.append([0, data])
            msg.Decode(p_data)
        primitive = msg.message_to_primitive()
        self.assertTrue(isinstance(primitive, C_MOVE_ServiceParameters))
        self.assertTrue(isinstance(primitive.Identifier, BytesIO))
        self.assertTrue(primitive.AffectedSOPClassUID == UID('1.2.840.10008.5.1.4.1.1.2'))
        self.assertTrue(primitive.Priority == 2)
        self.assertTrue(primitive.MoveDestination == b'MOVE_SCP        ')
        self.assertTrue(primitive.MessageID == 7)

        ds = decode(primitive.Identifier, True, True)
        self.assertEqual(ds.QueryRetrieveLevel, 'PATIENT')
        self.assertEqual(ds.PatientID, '*')

        msg = C_MOVE_RSP()
        for data in [c_move_rsp_cmd, c_move_rsp_ds]:
            p_data = P_DATA()
            p_data.presentation_data_value_list.append([0, data])
            msg.Decode(p_data)
        primitive = msg.message_to_primitive()
        self.assertTrue(isinstance(primitive, C_MOVE_ServiceParameters))
        self.assertTrue(isinstance(primitive.Identifier, BytesIO))
        self.assertTrue(primitive.AffectedSOPClassUID == UID('1.2.840.10008.5.1.4.1.1.2'))
        self.assertTrue(primitive.Status == 65280)
        self.assertTrue(primitive.MessageIDBeingRespondedTo == 5)
        self.assertTrue(primitive.NumberOfRemainingSuboperations == 3)
        self.assertTrue(primitive.NumberOfCompletedSuboperations == 1)
        self.assertTrue(primitive.NumberOfFailedSuboperations == 2)
        self.assertTrue(primitive.NumberOfWarningSuboperations == 4)

        ds = decode(primitive.Identifier, True, True)
        self.assertEqual(ds.QueryRetrieveLevel, 'PATIENT')
        self.assertEqual(ds.PatientID, '*')

    def test_message_to_primitive_c_find(self):
        """Test converting C_FIND_RQ to C_FIND primitive."""
        msg = C_FIND_RQ()
        for data in [c_find_rq_cmd, c_find_rq_ds]:
            p_data = P_DATA()
            p_data.presentation_data_value_list.append([0, data])
            msg.Decode(p_data)
        primitive = msg.message_to_primitive()
        self.assertTrue(isinstance(primitive, C_FIND_ServiceParameters))
        self.assertTrue(isinstance(primitive.Identifier, BytesIO))
        self.assertTrue(primitive.AffectedSOPClassUID == UID('1.2.840.10008.5.1.4.1.1.2'))
        self.assertTrue(primitive.Priority == 2)
        self.assertTrue(primitive.MessageID == 7)

        ds = decode(primitive.Identifier, True, True)
        self.assertEqual(ds.QueryRetrieveLevel, 'PATIENT')
        self.assertEqual(ds.PatientID, '*')

        msg = C_GET_RSP()
        for data in [c_find_rsp_cmd, c_find_rsp_ds]:
            p_data = P_DATA()
            p_data.presentation_data_value_list.append([0, data])
            msg.Decode(p_data)
        primitive = msg.message_to_primitive()
        self.assertTrue(isinstance(primitive, C_FIND_ServiceParameters))
        self.assertTrue(isinstance(primitive.Identifier, BytesIO))
        self.assertTrue(primitive.AffectedSOPClassUID == UID('1.2.840.10008.5.1.4.1.1.2'))
        self.assertTrue(primitive.Status == 65280)

        ds = decode(primitive.Identifier, True, True)
        self.assertEqual(ds.QueryRetrieveLevel, 'PATIENT')
        self.assertEqual(ds.RetrieveAETitle, 'FINDSCP        ')

        self.assertEqual(ds.PatientName, 'ANON^A^B^C^D')


if __name__ == "__main__":
    unittest.main()
