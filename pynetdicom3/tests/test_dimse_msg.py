"""Unit tests for the DIMSE Message classes."""

from io import BytesIO
import logging

import pytest

from pydicom.dataset import Dataset
from pydicom.uid import UID

from pynetdicom3.dimse_messages import (
    C_STORE_RQ, C_STORE_RSP, DIMSEMessage, C_ECHO_RQ, C_ECHO_RSP, C_FIND_RQ,
    C_FIND_RSP, C_MOVE_RQ, C_MOVE_RSP, C_GET_RQ, C_GET_RSP, N_EVENT_REPORT_RQ,
    N_EVENT_REPORT_RSP, N_SET_RQ, N_SET_RSP, N_GET_RQ, N_GET_RSP, N_ACTION_RQ,
    N_ACTION_RSP, N_CREATE_RQ, N_CREATE_RSP, N_DELETE_RQ, N_DELETE_RSP,
    C_CANCEL_RQ
)
from pynetdicom3.dimse_primitives import (
    C_STORE, C_ECHO, C_GET, C_MOVE, C_FIND, N_EVENT_REPORT, N_GET, N_SET,
    N_ACTION, N_CREATE, N_DELETE, C_CANCEL
)
from pynetdicom3.dsutils import encode, decode
from pynetdicom3.pdu_primitives import P_DATA
from pynetdicom3.utils import pretty_bytes
from .encoded_dimse_msg import (
    c_echo_rq_cmd, c_echo_rsp_cmd, c_store_rq_cmd, c_store_ds, c_store_rsp_cmd,
    c_find_rq_cmd, c_find_rq_ds, c_find_rsp_cmd, c_find_rsp_ds, c_get_rq_cmd,
    c_get_rq_ds, c_get_rsp_cmd, c_get_rsp_ds, c_move_rq_cmd, c_move_rq_ds,
    c_move_rsp_cmd, c_move_rsp_ds
)


LOGGER = logging.getLogger('pynetdicom3')
LOGGER.setLevel(logging.CRITICAL)

def print_nice_bytes(bytestream):
    """Nice output for bytestream."""
    str_list = pretty_bytes(bytestream, prefix="b'\\x", delimiter='\\x',
                        items_per_line=10, suffix="' \\")
    for string in str_list:
        print(string)


class TestDIMSEMessage(object):
    """Test DIMSEMessage class"""
    def test_fragment_pdv(self):
        """Test that the PDV fragmenter is working correctly."""
        dimse_msg = C_STORE_RQ()
        frag = dimse_msg._generate_pdv_fragments

        result = []
        for fragment in frag(c_echo_rsp_cmd, 1000):
            result.append(fragment)
        assert len(result) == 1
        assert result[0] == c_echo_rsp_cmd
        assert isinstance(result[0], bytes)
        assert result[-1] != b''

        result = []
        for fragment in frag(c_echo_rsp_cmd, 10):
            result.append(fragment)
        assert len(result) == 20
        assert result[0] == c_echo_rsp_cmd[:4]
        assert isinstance(result[0], bytes)
        assert result[-1] != b''

        with pytest.raises(ValueError):
            next(frag(c_echo_rsp_cmd, 6))

    def test_encode(self):
        """Test encoding of a DIMSE message."""
        primitive = C_STORE()
        primitive.MessageID = 7
        primitive.AffectedSOPClassUID = '1.1.1'
        primitive.AffectedSOPInstanceUID = '1.2.1'
        primitive.Priority = 0x02
        primitive.MoveOriginatorApplicationEntityTitle = 'UNITTEST'
        primitive.MoveOriginatorMessageID = 3

        # Test encode without dataset
        dimse_msg = C_STORE_RQ()
        dimse_msg.primitive_to_message(primitive)
        p_data_list = []
        for pdata in dimse_msg.encode_msg(12, 16):
            p_data_list.append(pdata)
        assert p_data_list[0].presentation_data_value_list[0][1][0:1] == b'\x01'
        assert p_data_list[-1].presentation_data_value_list[0][1][0:1] == b'\x03'
        assert dimse_msg.ID == 12

        # Test encode with dataset
        ds = Dataset()
        ds.PatientID = 'Test1101'
        ds.PatientName = 'Tube^HeNe'
        primitive.DataSet = BytesIO(encode(ds, True, True))

        dimse_msg = C_STORE_RQ()
        dimse_msg.primitive_to_message(primitive)
        p_data_list = []
        for pdata in dimse_msg.encode_msg(13, 10):
            p_data_list.append(pdata)

        assert p_data_list[0].presentation_data_value_list[0][1][0:1] == b'\x01'
        assert p_data_list[-1].presentation_data_value_list[0][1][0:1] == b'\x02'
        assert p_data_list[-2].presentation_data_value_list[0][1][0:1] == b'\x00'
        assert p_data_list[-10].presentation_data_value_list[0][1][0:1] == b'\x03'
        assert dimse_msg.ID == 13

        p_data_list = []
        for pdata in dimse_msg.encode_msg(1, 31682):
            p_data_list.append(pdata)
        assert p_data_list[0].presentation_data_value_list[0][1] == c_store_rq_cmd
        assert p_data_list[1].presentation_data_value_list[0][1] == c_store_ds

    def test_decode(self):
        """Test decoding of a DIMSE message."""
        primitive = C_STORE()
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
        p_data = dimse_msg.encode_msg(12, 24)

        # Command set decoding
        dimse_msg.decode_msg(next(p_data)) # MCHB 1
        dimse_msg.decode_msg(next(p_data)) # MCHB 1
        dimse_msg.decode_msg(next(p_data)) # MCHB 1
        dimse_msg.decode_msg(next(p_data)) # MCHB 1
        dimse_msg.decode_msg(next(p_data)) # MCHB 3 - end of command set
        assert dimse_msg.__class__ == C_STORE_RQ

        # Test decoded command set
        cs = dimse_msg.command_set
        assert cs.CommandGroupLength == 102
        assert cs.AffectedSOPClassUID == UID('1.1.1')
        assert cs.AffectedSOPInstanceUID == UID('1.2.1')
        assert cs.Priority == 2
        assert cs.CommandDataSetType == 1
        assert cs.CommandField == 1
        assert cs.MoveOriginatorApplicationEntityTitle == 'UNITTEST        '
        assert cs.MoveOriginatorMessageID == 3

        # Test decoded dataset
        dimse_msg.decode_msg(next(p_data)) # MCHB 1 # MCHB 0
        dimse_msg.decode_msg(next(p_data)) # MCHB 1 # MCHB 2
        assert dimse_msg.data_set.getvalue() == c_store_ds[1:]

        # Test returns false
        msg = C_STORE_RSP()
        assert not msg.decode_msg(c_store_rsp_cmd)

    def test_primitive_to_message(self):
        """Test converting a DIMSE primitive to a DIMSE message."""
        primitive = C_STORE()
        primitive.MessageID = 7
        primitive.AffectedSOPClassUID = '1.1.1'
        primitive.AffectedSOPInstanceUID = '1.2.1'
        primitive.Priority = 0x02
        msg = C_STORE_RQ()
        msg.primitive_to_message(primitive)
        # Test unused command set elements are deleted
        assert not 'MoveOriginatorApplicationEntityTitle' in msg.command_set

        # Test raise error for unknown DIMSE message type
        msg.__class__.__name__ = 'TestClass'
        with pytest.raises(ValueError):
            msg.primitive_to_message(primitive)

        # Reset name to avoid errors in other tests
        msg.__class__.__name__ = 'C_STORE_RQ'

    # DIMSE-C
    def test_message_to_primitive_c_store(self):
        """Test converting C_STORE_RQ and _RSP to C_STORE primitive."""
        msg = C_STORE_RQ()
        for data in [c_store_rq_cmd, c_store_ds]:
            p_data = P_DATA()
            p_data.presentation_data_value_list.append([0, data])
            msg.decode_msg(p_data)
        primitive = msg.message_to_primitive()
        assert isinstance(primitive, C_STORE)
        assert isinstance(primitive.DataSet, BytesIO)
        assert primitive.AffectedSOPClassUID == UID('1.1.1')
        assert primitive.AffectedSOPInstanceUID == UID('1.2.1')
        assert primitive.Priority == 2
        assert primitive.MoveOriginatorApplicationEntityTitle == b'UNITTEST        '
        assert primitive.MoveOriginatorMessageID == 3

        ds = decode(primitive.DataSet, True, True)
        assert ds.PatientName == 'Tube^HeNe'
        assert ds.PatientID == 'Test1101'

        msg = C_STORE_RSP()
        p_data = P_DATA()
        p_data.presentation_data_value_list.append([0, c_store_rsp_cmd])
        msg.decode_msg(p_data)
        primitive = msg.message_to_primitive()
        assert isinstance(primitive, C_STORE)
        assert primitive.DataSet is None
        for elem in msg.command_set:
            if hasattr(primitive, elem.keyword):
                item = getattr(primitive, elem.keyword)
                assert item == elem.value

    def test_message_to_primitive_c_echo(self):
        """Test converting C_ECHO_RQ to C_ECHO primitive."""
        msg = C_ECHO_RQ()
        p_data = P_DATA()
        p_data.presentation_data_value_list.append([0, c_echo_rq_cmd])
        msg.decode_msg(p_data)
        primitive = msg.message_to_primitive()
        assert isinstance(primitive, C_ECHO)
        assert primitive.AffectedSOPClassUID == UID('1.2.840.10008.1.1')
        assert primitive.MessageID == 7

        msg = C_ECHO_RSP()
        p_data = P_DATA()
        p_data.presentation_data_value_list.append([0, c_echo_rsp_cmd])
        msg.decode_msg(p_data)
        primitive = msg.message_to_primitive()
        assert isinstance(primitive, C_ECHO)
        assert primitive.AffectedSOPClassUID == UID('1.2.840.10008.1.1')
        assert primitive.MessageIDBeingRespondedTo == 8
        assert primitive.Status == 0

    def test_message_to_primitive_c_get(self):
        """Test converting C_GET_RQ to C_GET primitive."""
        msg = C_GET_RQ()
        for data in [c_get_rq_cmd, c_get_rq_ds]:
            p_data = P_DATA()
            p_data.presentation_data_value_list.append([0, data])
            msg.decode_msg(p_data)
        primitive = msg.message_to_primitive()
        assert isinstance(primitive, C_GET)
        assert isinstance(primitive.Identifier, BytesIO)
        assert primitive.AffectedSOPClassUID == UID('1.2.840.10008.5.1.4.1.1.2')
        assert primitive.Priority == 2
        assert primitive.MessageID == 7

        ds = decode(primitive.Identifier, True, True)
        assert ds.QueryRetrieveLevel == 'PATIENT'
        assert ds.PatientID == '*'

        msg = C_GET_RSP()
        for data in [c_get_rsp_cmd, c_get_rsp_ds]:
            p_data = P_DATA()
            p_data.presentation_data_value_list.append([0, data])
            msg.decode_msg(p_data)
        primitive = msg.message_to_primitive()
        assert isinstance(primitive, C_GET)
        assert isinstance(primitive.Identifier, BytesIO)
        assert primitive.AffectedSOPClassUID == UID('1.2.840.10008.5.1.4.1.1.2')
        assert primitive.Status == 65280
        assert primitive.MessageIDBeingRespondedTo == 5
        assert primitive.NumberOfRemainingSuboperations == 3
        assert primitive.NumberOfCompletedSuboperations == 1
        assert primitive.NumberOfFailedSuboperations == 2
        assert primitive.NumberOfWarningSuboperations == 4

        ds = decode(primitive.Identifier, True, True)
        assert ds.QueryRetrieveLevel == 'PATIENT'
        assert ds.PatientID == '*'

    def test_message_to_primitive_c_move(self):
        """Test converting C_MOVE_RQ to C_MOVE primitive."""
        msg = C_MOVE_RQ()
        for data in [c_move_rq_cmd, c_move_rq_ds]:
            p_data = P_DATA()
            p_data.presentation_data_value_list.append([0, data])
            msg.decode_msg(p_data)
        primitive = msg.message_to_primitive()
        assert isinstance(primitive, C_MOVE)
        assert isinstance(primitive.Identifier, BytesIO)
        assert primitive.AffectedSOPClassUID == UID('1.2.840.10008.5.1.4.1.1.2')
        assert primitive.Priority == 2
        assert primitive.MoveDestination == b'MOVE_SCP        '
        assert primitive.MessageID == 7

        ds = decode(primitive.Identifier, True, True)
        assert ds.QueryRetrieveLevel == 'PATIENT'
        assert ds.PatientID == '*'

        msg = C_MOVE_RSP()
        for data in [c_move_rsp_cmd, c_move_rsp_ds]:
            p_data = P_DATA()
            p_data.presentation_data_value_list.append([0, data])
            msg.decode_msg(p_data)
        primitive = msg.message_to_primitive()
        assert isinstance(primitive, C_MOVE)
        assert isinstance(primitive.Identifier, BytesIO)
        assert primitive.AffectedSOPClassUID == UID('1.2.840.10008.5.1.4.1.1.2')
        assert primitive.Status == 65280
        assert primitive.MessageIDBeingRespondedTo == 5
        assert primitive.NumberOfRemainingSuboperations == 3
        assert primitive.NumberOfCompletedSuboperations == 1
        assert primitive.NumberOfFailedSuboperations == 2
        assert primitive.NumberOfWarningSuboperations == 4

        ds = decode(primitive.Identifier, True, True)
        assert ds.QueryRetrieveLevel == 'PATIENT'
        assert ds.PatientID == '*'

    def test_message_to_primitive_c_find(self):
        """Test converting C_FIND_RQ to C_FIND primitive."""
        msg = C_FIND_RQ()
        for data in [c_find_rq_cmd, c_find_rq_ds]:
            p_data = P_DATA()
            p_data.presentation_data_value_list.append([0, data])
            msg.decode_msg(p_data)
        primitive = msg.message_to_primitive()
        assert isinstance(primitive, C_FIND)
        assert isinstance(primitive.Identifier, BytesIO)
        assert primitive.AffectedSOPClassUID == UID('1.2.840.10008.5.1.4.1.1.2')
        assert primitive.Priority == 2
        assert primitive.MessageID == 7

        ds = decode(primitive.Identifier, True, True)
        assert ds.QueryRetrieveLevel == 'PATIENT'
        assert ds.PatientID == '*'

        msg = C_GET_RSP()
        for data in [c_find_rsp_cmd, c_find_rsp_ds]:
            p_data = P_DATA()
            p_data.presentation_data_value_list.append([0, data])
            msg.decode_msg(p_data)
        primitive = msg.message_to_primitive()
        assert isinstance(primitive, C_FIND)
        assert isinstance(primitive.Identifier, BytesIO)
        assert primitive.AffectedSOPClassUID == UID('1.2.840.10008.5.1.4.1.1.2')
        assert primitive.Status == 65280

        ds = decode(primitive.Identifier, True, True)
        assert ds.QueryRetrieveLevel == 'PATIENT'
        assert ds.RetrieveAETitle == 'FINDSCP'

        assert ds.PatientName == 'ANON^A^B^C^D'

    def test_message_to_primitive_c_cancel(self):
        """Test converting C_CANCEL_rq to C_CANCEL primitive."""
        msg = C_CANCEL_RQ()
        cs = Dataset()
        cs.MessageIDBeingRespondedTo = 1
        msg.command_set = cs
        primitive = msg.message_to_primitive()
        assert isinstance(primitive, C_CANCEL)
        assert primitive.MessageIDBeingRespondedTo == 1

    # DIMSE-N
    def test_message_to_primitive_n_event_report(self):
        """Test converting N_EVENT_REPORT_RQ and _RSP to primitive."""
        # N-EVENT-REPORT-RQ
        msg = N_EVENT_REPORT_RQ()
        primitive = msg.message_to_primitive()
        assert isinstance(primitive, N_EVENT_REPORT)

        # N-EVENT-REPORT-RSP
        msg = N_EVENT_REPORT_RSP()
        primitive = msg.message_to_primitive()
        assert isinstance(primitive, N_EVENT_REPORT)

    def test_message_to_primitive_n_get(self):
        """Test converting N_GET_RQ and _RSP to primitive."""
        # N-GET-RQ
        msg = N_GET_RQ()
        primitive = msg.message_to_primitive()
        assert isinstance(primitive, N_GET)

        # N-GET-RSP
        msg = N_GET_RSP()
        primitive = msg.message_to_primitive()
        assert isinstance(primitive, N_GET)

    def test_message_to_primitive_n_set(self):
        """Test converting N_SET_RQ and _RSP to primitive."""
        # N-SET-RQ
        msg = N_SET_RQ()
        primitive = msg.message_to_primitive()
        assert isinstance(primitive, N_SET)

        # N-SET-RSP
        msg = N_SET_RSP()
        primitive = msg.message_to_primitive()
        assert isinstance(primitive, N_SET)

    def test_message_to_primitive_n_action(self):
        """Test converting N_ACTION_RQ and _RSP to primitive."""
        # N-ACTION-RQ
        msg = N_ACTION_RQ()
        primitive = msg.message_to_primitive()
        assert isinstance(primitive, N_ACTION)

        # N-ACTION-RSP
        msg = N_ACTION_RSP()
        primitive = msg.message_to_primitive()
        assert isinstance(primitive, N_ACTION)

    def test_message_to_primitive_n_create(self):
        """Test converting N_CREATE_RQ and _RSP to primitive."""
        # N-CREATE-RQ
        msg = N_CREATE_RQ()
        primitive = msg.message_to_primitive()
        assert isinstance(primitive, N_CREATE)

        # N-CREATE-RSP
        msg = N_CREATE_RSP()
        primitive = msg.message_to_primitive()
        assert isinstance(primitive, N_CREATE)

    def test_message_to_primitive_n_delete(self):
        """Test converting N_DELETE_RQ and _RSP to primitive."""
        # N-DELETE-RQ
        msg = N_DELETE_RQ()
        primitive = msg.message_to_primitive()
        assert isinstance(primitive, N_DELETE)

        # N-DELETE-RSP
        msg = N_DELETE_RSP()
        primitive = msg.message_to_primitive()
        assert isinstance(primitive, N_DELETE)
