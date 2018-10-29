#!/usr/bin/env python
"""Test DIMSE service provider operations.

TODO: Add testing of maximum pdu length flow from assoc negotiation
"""

from io import BytesIO
import logging

import pytest

from pydicom.dataset import Dataset

from pynetdicom3.dimse import DIMSEServiceProvider
from pynetdicom3.dimse_messages import (
    C_STORE_RQ, C_STORE_RSP, C_FIND_RQ, C_FIND_RSP, C_GET_RQ, C_GET_RSP,
    C_MOVE_RQ, C_MOVE_RSP, C_ECHO_RQ,C_ECHO_RSP, C_CANCEL_RQ,
    N_EVENT_REPORT_RQ, N_EVENT_REPORT_RSP, N_GET_RQ, N_GET_RSP, N_SET_RQ,
    N_SET_RSP, N_ACTION_RQ, N_ACTION_RSP, N_CREATE_RQ, N_CREATE_RSP,
    N_DELETE_RQ, N_DELETE_RSP
)
from pynetdicom3.dimse_primitives import (
    C_STORE, C_ECHO, C_GET, C_MOVE, C_FIND, N_EVENT_REPORT, N_SET, N_GET,
    N_ACTION, N_CREATE, N_DELETE, C_CANCEL
)
from pynetdicom3.dsutils import encode
from .encoded_dimse_msg import c_store_ds
from .encoded_dimse_n_msg import (
    n_er_rq_ds, n_er_rsp_ds, n_get_rsp_ds, n_set_rq_ds, n_set_rsp_ds,
    n_action_rq_ds, n_action_rsp_ds, n_create_rq_ds, n_create_rsp_ds
)

LOGGER = logging.getLogger('pynetdicom3')
LOGGER.setLevel(logging.CRITICAL)


class DummyDUL(object):
    """Dummy DUL class for testing DIMSE provider"""
    @staticmethod
    def is_alive(): return True

    @staticmethod
    def send_pdu(pdv):
        """Dummy Send method to test DIMSEServiceProvider.Send"""
        pass

    @staticmethod
    def receive_pdu():
        """Dummy Receive method to test DIMSEServiceProvider.Receive"""
        pass

    @staticmethod
    def peek_next_pdu():
        return 0x01


REFERENCE_MSG = [
    (C_ECHO(), ('C_ECHO_RQ', 'C_ECHO_RSP')),
    (C_STORE(), ('C_STORE_RQ', 'C_STORE_RSP')),
    (C_FIND(), ('C_FIND_RQ', 'C_FIND_RSP')),
    (C_GET(), ('C_GET_RQ', 'C_GET_RSP')),
    (C_MOVE(), ('C_MOVE_RQ', 'C_MOVE_RSP')),
    (C_CANCEL(), (None, 'C_CANCEL_RQ')),
    (N_EVENT_REPORT(), ('N_EVENT_REPORT_RQ', 'N_EVENT_REPORT_RSP')),
    (N_GET(), ('N_GET_RQ', 'N_GET_RSP')),
    (N_SET(), ('N_SET_RQ', 'N_SET_RSP')),
    (N_ACTION(), ('N_ACTION_RQ', 'N_ACTION_RSP')),
    (N_CREATE(), ('N_CREATE_RQ', 'N_CREATE_RSP')),
    (N_DELETE(), ('N_DELETE_RQ', 'N_DELETE_RSP')),
]


class TestDIMSEProvider(object):
    """Test DIMSE service provider operations."""
    def setup(self):
        """Set up"""
        self.dimse = DIMSEServiceProvider(DummyDUL(), 1)

    def test_receive_not_pdata(self):
        """Test we get back None if not a P_DATA"""
        assert self.dimse.receive_msg(True) == (None, None)

    @pytest.mark.parametrize("primitive, cls_name", REFERENCE_MSG)
    def test_send_msg(self, primitive, cls_name):
        """Check sending DIMSE messages."""
        # -RQ
        primitive.MessageID = 1
        primitive.AffectedSOPClassUID = '1.1.1'

        def test_callback(msg):
            """Callback"""
            assert msg.__class__.__name__ == cls_name[0]

        self.dimse.on_send_dimse_message = test_callback
        if cls_name[0]:
            self.dimse.send_msg(primitive, 1)

        # -RSP
        primitive.MessageIDBeingRespondedTo = 1
        primitive.Status = 0x0000

        def test_callback(msg):
            """Callback"""
            assert msg.__class__.__name__ == cls_name[1]

        self.dimse.on_send_dimse_message = test_callback
        self.dimse.send_msg(primitive, 1)

    # Receive tests
    def test_receive_timeout(self):
        """Test the DIMSE timeout on Receive works"""
        pass

    def test_receive_c_echo(self):
        """Check receiving DIMSE C-ECHO messages."""
        pass

    def test_receive_c_store(self):
        """Check receiving DIMSE C-STORE messages."""
        pass

    def test_receive_c_find(self):
        """Check receiving DIMSE C-FIND messages."""
        pass

    def test_receive_c_get(self):
        """Check receiving DIMSE C-GET messages."""
        pass

    def test_receive_c_move(self):
        """Check receiving DIMSE C-MOVE messages."""
        pass

    def test_receive_n_event_report(self):
        """Check receiving DIMSE N-EVENT-REPORT messages."""
        pass

    def test_receive_n_get(self):
        """Check receiving DIMSE N-GET messages."""
        pass

    def test_receive_n_set(self):
        """Check receiving DIMSE N-SET messages."""
        pass

    def test_receive_n_action(self):
        """Check receiving DIMSE N-ACTION messages."""
        pass

    def test_receive_n_create(self):
        """Check receiving DIMSE N-CREATE messages."""
        pass

    def test_receive_n_delete(self):
        """Check receiving DIMSE N-DELETE messages."""
        pass


class TestDIMSEProviderCallbacks(object):
    """Test the callbacks for the DIMSE Service"""
    def setup(self):
        """Set up"""
        self.dimse = DIMSEServiceProvider(DummyDUL(), 1)

    def test_callback_send_c_echo(self):
        """Check callback for sending DIMSE C-ECHO messages."""
        # C-ECHO-RQ
        primitive = C_ECHO()
        primitive.MessageID = 1
        primitive.AffectedSOPClassUID = '1.1.1'
        self.dimse.send_msg(primitive, 1)

        # C-ECHO-RSP
        primitive = C_ECHO()
        primitive.MessageIDBeingRespondedTo = 1
        primitive.Status = 0x0000
        self.dimse.send_msg(primitive, 1)

    def test_callback_send_c_store(self):
        """Check callback for sending DIMSE C-STORE messages."""
        # C-STORE-RQ
        primitive = C_STORE()
        primitive.MessageID = 1
        primitive.AffectedSOPClassUID = '1.2.840.10008.5.1.4.1.1.2' # CT
        primitive.AffectedSOPInstanceUID = '1.1.2'
        primitive.Priority = 0x02
        primitive.DataSet = BytesIO()
        # CT + no dataset
        self.dimse.send_msg(primitive, 1)
        primitive.AffectedSOPClassUID = '1.1.1'
        # No UID type, no dataset
        # MR + dataset
        primitive.AffectedSOPClassUID = '1.2.840.10008.5.1.4.1.1.4' # MR
        bytestream = BytesIO()
        bytestream.write(c_store_ds)
        primitive.DataSet = bytestream
        self.dimse.send_msg(primitive, 1)

        # C-STORE-RSP
        primitive = C_STORE()
        primitive.MessageIDBeingRespondedTo = 1
        primitive.Status = 0x0000
        self.dimse.send_msg(primitive, 1)

    def test_callback_send_c_find(self):
        """Check callback for sending DIMSE C-FIND messages."""
        # C-FIND-RQ
        primitive = C_FIND()
        primitive.MessageID = 1
        primitive.AffectedSOPClassUID = '1.1.1'
        primitive.Priority = 0x02
        primitive.Identifier = BytesIO()
        # No dataset
        self.dimse.send_msg(primitive, 1)
        # Dataset
        bytestream = BytesIO()
        bytestream.write(c_store_ds)
        primitive.Identifier = bytestream
        self.dimse.send_msg(primitive, 1)

        # C-FIND-RSP
        primitive = C_FIND()
        primitive.MessageIDBeingRespondedTo = 1
        primitive.Status = 0x0000
        primitive.AffectedSOPClassUID = '1.1.1'
        # No dataset
        self.dimse.send_msg(primitive, 1)
        # Dataset
        bytestream = BytesIO()
        bytestream.write(c_store_ds)
        primitive.Identifier = bytestream
        primitive.Status = 0xFF00 # Only has dataset when 0xFF00 or 0xFF01
        self.dimse.send_msg(primitive, 1)

    def test_callback_send_c_get(self):
        """Check callback for sending DIMSE C-GET messages."""
        # C-GET-RQ
        primitive = C_GET()
        primitive.MessageID = 1
        primitive.AffectedSOPClassUID = '1.1.1'
        primitive.Identifier = BytesIO()
        # No dataset
        self.dimse.send_msg(primitive, 1)
        # Dataset
        bytestream = BytesIO()
        bytestream.write(c_store_ds)
        primitive.Identifier = bytestream
        self.dimse.send_msg(primitive, 1)

        # C-GET-RSP
        primitive = C_GET()
        primitive.MessageIDBeingRespondedTo = 1
        primitive.Status = 0x0000
        primitive.Identifier = BytesIO()
        # No dataset
        self.dimse.send_msg(primitive, 1)
        # Dataset
        bytestream = BytesIO()
        bytestream.write(c_store_ds)
        primitive.Identifier = bytestream
        self.dimse.send_msg(primitive, 1)

    def test_callback_send_c_move(self):
        """Check callback for sending DIMSE C-MOVE messages."""
        # C-MOVE-RQ
        primitive = C_MOVE()
        primitive.MessageID = 1
        primitive.AffectedSOPClassUID = '1.1.1'
        primitive.MoveDestination = b'TESTSCP'
        # No dataset
        primitive.Identifier = BytesIO()
        self.dimse.send_msg(primitive, 1)
        # Dataset
        bytestream = BytesIO()
        bytestream.write(c_store_ds)
        primitive.Identifier = bytestream
        self.dimse.send_msg(primitive, 1)

        # C-MOVE-RSP
        primitive = C_MOVE()
        primitive.MessageIDBeingRespondedTo = 1
        primitive.Status = 0x0000
        # No dataset
        primitive.Identifier = BytesIO()
        self.dimse.send_msg(primitive, 1)
        # Dataset
        bytestream = BytesIO()
        bytestream.write(c_store_ds)
        primitive.Identifier = bytestream
        self.dimse.send_msg(primitive, 1)

    def test_callback_send_n_event_report(self):
        """Check callback for sending DIMSE N-EVENT-REPORT messages."""
        # N-EVENT-REPORT-RQ
        primitive = N_EVENT_REPORT()
        primitive.MessageID = 1
        primitive.AffectedSOPClassUID = '1.1.1'
        primitive.AffectedSOPInstanceUID = '1.1.1'
        primitive.EventTypeID = 2
        self.dimse.send_msg(primitive, 1)

        # User defined
        primitive.EventInformation = BytesIO(n_er_rq_ds)
        self.dimse.send_msg(primitive, 1)

        # N-EVENT-REPORT-RSP
        primitive = N_EVENT_REPORT()
        primitive.MessageIDBeingRespondedTo = 1
        primitive.Status = 0x0000
        self.dimse.send_msg(primitive, 1)

        # User defined
        primitive.AffectedSOPClassUID = '1.2'
        primitive.AffectedSOPInstanceUID = '1.2.3'
        primitive.EventTypeID = 4
        primitive.EventReply = BytesIO(n_er_rsp_ds)
        self.dimse.send_msg(primitive, 1)

    def test_callback_send_n_get(self):
        """Check callback for sending DIMSE N-GET messages."""
        # N-GET-RQ
        primitive = N_GET()
        primitive.MessageID = 1
        primitive.RequestedSOPClassUID = '1.1.1'
        primitive.RequestedSOPInstanceUID = '1.1.1.1'
        self.dimse.send_msg(primitive, 1)

        # Plus user defined
        primitive.AttributeIdentifierList = [(0x0000, 0x0000), (0xffff, 0xffff)]
        self.dimse.send_msg(primitive, 1)

        # N-GET-RSP
        # Mandatory elements
        primitive = N_GET()
        primitive.MessageIDBeingRespondedTo = 1
        primitive.Status = 0x0000
        self.dimse.send_msg(primitive, 1)

        # User defined
        primitive.AffectedSOPClassUID = '1.1.1'
        primitive.AffectedSOPInstanceUID = '1.1.1.1'
        self.dimse.send_msg(primitive, 1)

        # Conditional
        primitive.AttributeList = BytesIO(n_get_rsp_ds)
        self.dimse.send_msg(primitive, 1)

    def test_callback_send_n_set(self):
        """Check callback for sending DIMSE N-SET messages."""
        # N-SET-RQ
        primitive = N_SET()
        primitive.MessageID = 1
        primitive.RequestedSOPClassUID = '1.1.1'
        primitive.RequestedSOPInstanceUID = '1.1.1.1'
        primitive.ModificationList = BytesIO(b'\x00\x01')
        self.dimse.send_msg(primitive, 1)

        # N-SET-RSP
        primitive = N_SET()
        primitive.MessageIDBeingRespondedTo = 1
        primitive.Status = 0x0000
        self.dimse.send_msg(primitive, 1)

        # User defined
        primitive.AffectedSOPClassUID = '1.1.1'
        primitive.AffectedSOPInstanceUID = '1.1.1.1'
        primitive.AttributeList = BytesIO(b'\x00\x01')
        self.dimse.send_msg(primitive, 1)

    def test_callback_send_n_action(self):
        """Check callback for sending DIMSE N-ACTION messages."""
        # N-ACTION-RQ
        primitive = N_ACTION()
        primitive.MessageID = 1
        primitive.RequestedSOPClassUID = '1.1.1'
        primitive.RequestedSOPInstanceUID = '1.1.1.2'
        primitive.ActionTypeID = 5
        self.dimse.send_msg(primitive, 1)

        # User defined
        primitive.ActionInformation = BytesIO(b'\x00\x01')
        self.dimse.send_msg(primitive, 1)

        # N-ACTION-RSP
        primitive = N_ACTION()
        primitive.MessageIDBeingRespondedTo = 1
        primitive.Status = 0x0000
        self.dimse.send_msg(primitive, 1)

        # User defined
        primitive.ActionTypeID = 5
        primitive.AffectedSOPClassUID = '1.2'
        primitive.AffectedSOPInstanceUID = '1.2.3'
        primitive.ActionReply = BytesIO(b'\x00\x01')
        self.dimse.send_msg(primitive, 1)

    def test_callback_send_n_create(self):
        """Check callback for sending DIMSE N-CREATE messages."""
        # N-CREATE-RQ
        primitive = N_CREATE()
        primitive.MessageID = 1
        primitive.AffectedSOPClassUID = '1.1.1'
        self.dimse.send_msg(primitive, 1)

        # User defined
        primitive.AffectedSOPInstanceUID = '1.2.3'
        primitive.AttributeList = BytesIO(b'\x00\x01')
        self.dimse.send_msg(primitive, 1)

        # N-CREATE-RSP
        primitive = N_CREATE()
        primitive.MessageIDBeingRespondedTo = 1
        primitive.Status = 0x0000
        self.dimse.send_msg(primitive, 1)

        primitive.AffectedSOPClassUID = '1.2'
        primitive.AffectedSOPInstanceUID = '1.2.3'
        primitive.AattributeList = BytesIO(b'\x00\x01')
        self.dimse.send_msg(primitive, 1)

    def test_callback_send_n_delete(self):
        """Check callback for sending DIMSE N-DELETE messages."""
        # N-DELETE-RQ
        primitive = N_DELETE()
        primitive.MessageID = 1
        primitive.RequestedSOPClassUID = '1.1.1'
        primitive.RequestedSOPInstanceUID = '1.2.3'
        self.dimse.send_msg(primitive, 1)

        # N-DELETE-RSP
        # No affected SOP class/instance
        primitive = N_DELETE()
        primitive.MessageIDBeingRespondedTo = 1
        primitive.Status = 0x0000
        self.dimse.send_msg(primitive, 1)

        # Affected SOP Class
        primitive.AffectedSOPClassUID = '1.1.2'
        self.dimse.send_msg(primitive, 1)

        # Affected SOP Instance
        primitive.AffectedSOPInstanceUID = '1.1.3'
        self.dimse.send_msg(primitive, 1)

    # Receive
    def test_callback_receive_c_echo(self):
        """Check callback for receiving DIMSE C-ECHO messages."""
        # C-ECHO-RQ
        primitive = C_ECHO()
        primitive.MessageID = 7
        primitive.Priority = 0x02
        msg = C_ECHO_RQ()
        msg.primitive_to_message(primitive)
        msg.ID = 1
        self.dimse.debug_receive_c_echo_rq(msg)

        # C-ECHO-RSP
        primitive = C_ECHO()
        primitive.MessageIDBeingRespondedTo = 4
        primitive.Status = 0x0000
        msg = C_ECHO_RSP()
        msg.primitive_to_message(primitive)
        self.dimse.debug_receive_c_echo_rsp(msg)

    def test_callback_receive_c_store(self):
        """Check callback for sending DIMSE C-STORE messages."""
        # C-STORE-RQ
        primitive = C_STORE()
        primitive.MessageID = 7
        primitive.AffectedSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
        primitive.AffectedSOPInstanceUID = '1.2.392.200036.9116.2.6.1.48.' \
                                           '1215709044.1459316254.522441'
        primitive.Priority = 0x02
        primitive.MoveOriginatorApplicationEntityTitle = 'UNITTEST_SCP'
        primitive.MoveOriginatorMessageID = 3
        primitive.DataSet = BytesIO()

        # No dataset
        msg = C_STORE_RQ()
        msg.primitive_to_message(primitive)
        self.dimse.debug_receive_c_store_rq(msg)

        # Dataset
        ref_ds = Dataset()
        ref_ds.PatientID = 'Test1101'
        ref_ds.PatientName = "Tube HeNe"

        primitive.DataSet = BytesIO(encode(ref_ds, True, True))

        msg = C_STORE_RQ()
        msg.primitive_to_message(primitive)
        # Dataset
        self.dimse.debug_receive_c_store_rq(msg)

        # C-STORE-RSP
        primitive = C_STORE()
        primitive.MessageIDBeingRespondedTo = 7
        primitive.AffectedSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
        primitive.AffectedSOPInstanceUID = '1.2.392.200036.9116.2.6.1.48.' \
                                           '1215709044.1459316254.522441'
        primitive.MoveOriginatorApplicationEntityTitle = 'UNITTEST_SCP'
        primitive.MoveOriginatorMessageID = 3
        primitive.DataSet = BytesIO()

        # Check statuses + no dataset
        for status in [0x0000, 0xb000, 0xb007, 0xb006, 0xa700, 0xa900, 0xc000]:
            primitive.Status = status
            msg = C_STORE_RSP()
            msg.primitive_to_message(primitive)
            self.dimse.debug_receive_c_store_rsp(msg)

        # Dataset
        ref_ds = Dataset()
        ref_ds.PatientID = 'Test1101'
        ref_ds.PatientName = "Tube HeNe"

        msg = C_STORE_RSP()
        msg.primitive_to_message(primitive)
        # Dataset
        msg.data_set = BytesIO(encode(ref_ds, True, True))
        self.dimse.debug_receive_c_store_rsp(msg)

    def test_callback_receive_c_find(self):
        """Check callback for receiving DIMSE C-FIND messages."""
        # C-FIND-RQ
        primitive = C_FIND()
        primitive.MessageID = 7
        primitive.AffectedSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
        primitive.AffectedSOPInstanceUID = '1.2.392.200036.9116.2.6.1.48.' \
                                           '1215709044.1459316254.522441'
        primitive.Priority = 0x02
        primitive.MoveOriginatorApplicationEntityTitle = 'UNITTEST_SCP'
        primitive.MoveOriginatorMessageID = 3
        primitive.Identifier = BytesIO()

        # No dataset
        msg = C_FIND_RQ()
        msg.primitive_to_message(primitive)
        self.dimse.debug_receive_c_find_rq(msg)

        # Dataset
        ref_ds = Dataset()
        ref_ds.PatientID = 'Test1101'
        ref_ds.PatientName = "Tube HeNe"

        primitive.Identifier = BytesIO(encode(ref_ds, True, True))

        msg = C_FIND_RQ()
        msg.primitive_to_message(primitive)
        # Dataset
        self.dimse.debug_receive_c_find_rq(msg)

        # C-FIND-RSP
        primitive = C_FIND()
        primitive.MessageIDBeingRespondedTo = 7
        primitive.AffectedSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
        primitive.AffectedSOPInstanceUID = '1.2.392.200036.9116.2.6.1.48.' \
                                           '1215709044.1459316254.522441'
        primitive.MoveOriginatorApplicationEntityTitle = 'UNITTEST_SCP'
        primitive.MoveOriginatorMessageID = 3
        primitive.Identifier = BytesIO()

        # No dataset
        primitive.Status = 0x0000 # Must be for pending

        msg = C_FIND_RSP()
        msg.primitive_to_message(primitive)
        self.dimse.debug_receive_c_find_rsp(msg)

        primitive.Identifier = BytesIO(encode(ref_ds, True, True))
        msg = C_FIND_RSP()
        msg.primitive_to_message(primitive)
        # Dataset
        msg.data_set = BytesIO(encode(ref_ds, True, True))
        self.dimse.debug_receive_c_find_rsp(msg)

        # Non-pending status
        msg.data_set.Status = 0x0001
        self.dimse.debug_receive_c_find_rsp(msg)

        # C-CANCEL-FIND-RQ
        self.dimse.debug_receive_c_cancel_rq(msg)

    def test_callback_receive_c_get(self):
        """Check callback for receiving DIMSE C-GET messages."""
        # C-GET-RQ
        primitive = C_GET()
        primitive.MessageID = 7
        primitive.AffectedSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
        primitive.AffectedSOPInstanceUID = '1.2.392.200036.9116.2.6.1.48.' \
                                           '1215709044.1459316254.522441'
        primitive.Priority = 0x02
        primitive.MoveOriginatorApplicationEntityTitle = 'UNITTEST_SCP'
        primitive.MoveOriginatorMessageID = 3
        primitive.Identifier = BytesIO()

        # No dataset
        msg = C_GET_RQ()
        msg.primitive_to_message(primitive)
        self.dimse.debug_receive_c_get_rq(msg)

        # Dataset
        ref_ds = Dataset()
        ref_ds.PatientID = 'Test1101'
        ref_ds.PatientName = "Tube HeNe"

        primitive.Identifier = BytesIO(encode(ref_ds, True, True))

        msg = C_GET_RQ()
        msg.primitive_to_message(primitive)
        # Dataset
        self.dimse.debug_receive_c_get_rq(msg)

        # C-GET-RSP
        primitive = C_GET()
        primitive.MessageIDBeingRespondedTo = 7
        primitive.AffectedSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
        primitive.AffectedSOPInstanceUID = '1.2.392.200036.9116.2.6.1.48.' \
                                           '1215709044.1459316254.522441'
        primitive.MoveOriginatorApplicationEntityTitle = 'UNITTEST_SCP'
        primitive.MoveOriginatorMessageID = 3
        primitive.Identifier = BytesIO()
        primitive.NumberOfCompletedSuboperations = 1
        primitive.NumberOfWarningSuboperations = 3
        primitive.NumberOfFailedSuboperations = 4

        # No dataset, remaining subops
        primitive.Status = 0x0000 # Must be for pending
        msg = C_GET_RSP()
        msg.primitive_to_message(primitive)
        self.dimse.debug_receive_c_get_rsp(msg)

        # Dataset
        ref_ds = Dataset()
        ref_ds.PatientID = 'Test1101'
        ref_ds.PatientName = "Tube HeNe"
        primitive.Identifier = BytesIO(encode(ref_ds, True, True))
        primitive.NumberOfRemainingSuboperations = 2

        msg = C_GET_RSP()

        msg.primitive_to_message(primitive)

        # Dataset
        self.dimse.debug_receive_c_get_rsp(msg)

        # C-CANCEL-GET-RQ
        self.dimse.debug_receive_c_cancel_rq(msg)

    def test_callback_receive_c_move(self):
        """Check callback for receiving DIMSE C-MOVE messages."""
        # C-MOVE-RQ
        msg = C_MOVE_RQ()
        self.dimse.debug_receive_c_move_rq(msg)

        # C-MOVE-RSP
        primitive = C_MOVE()
        primitive.MessageIDBeingRespondedTo = 7
        primitive.AffectedSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
        primitive.AffectedSOPInstanceUID = '1.2.392.200036.9116.2.6.1.48.' \
                                           '1215709044.1459316254.522441'
        primitive.MoveOriginatorApplicationEntityTitle = 'UNITTEST_SCP'
        primitive.MoveOriginatorMessageID = 3
        primitive.Identifier = BytesIO()
        primitive.NumberOfCompletedSuboperations = 1
        primitive.NumberOfWarningSuboperations = 3
        primitive.NumberOfFailedSuboperations = 4

        # No dataset, remaining subops
        primitive.Status = 0x0000 # Must be for pending
        msg = C_MOVE_RSP()
        msg.primitive_to_message(primitive)
        self.dimse.debug_receive_c_move_rsp(msg)

        # Dataset
        ref_ds = Dataset()
        ref_ds.PatientID = 'Test1101'
        ref_ds.PatientName = "Tube HeNe"
        primitive.Identifier = BytesIO(encode(ref_ds, True, True))
        primitive.NumberOfRemainingSuboperations = 2

        msg = C_GET_RSP()

        msg.primitive_to_message(primitive)

        # Dataset
        self.dimse.debug_receive_c_move_rsp(msg)

        # C-CANCEL-MOVE-RQ
        self.dimse.debug_receive_c_cancel_rq(msg)

    def test_callback_receive_n_event_report(self):
        """Check callback for receiving DIMSE N-EVENT-REPORT messages."""
        # N-EVENT-REPORT-RQ
        primitive = N_EVENT_REPORT()
        primitive.MessageID = 1
        primitive.AffectedSOPClassUID = '1.1.1'
        primitive.AffectedSOPInstanceUID = '1.1.1.1'
        primitive.EventTypeID = 5
        msg = N_EVENT_REPORT_RQ()
        msg.primitive_to_message(primitive)
        msg.ID = 1
        self.dimse.debug_receive_n_event_report_rq(msg)

        # User defined
        primitive.EventInformation = BytesIO(n_er_rq_ds)
        msg = N_EVENT_REPORT_RQ()
        msg.primitive_to_message(primitive)
        msg.ID = 1
        self.dimse.debug_receive_n_event_report_rq(msg)

        # N-EVENT-REPORT-RSP
        primitive = N_EVENT_REPORT()
        primitive.MessageIDBeingRespondedTo = 1
        primitive.Status = 5
        msg = N_EVENT_REPORT_RSP()
        msg.primitive_to_message(primitive)
        msg.ID = 1
        self.dimse.debug_receive_n_event_report_rsp(msg)

        # User defined
        primitive.AffectedSOPClassUID = '1.2.3'
        primitive.AffectedSOPInstanceUID = '1.2.3.4'
        primitive.EventTypeID = 4
        primitive.EventReply = BytesIO(n_er_rsp_ds)
        msg = N_EVENT_REPORT_RSP()
        msg.primitive_to_message(primitive)
        msg.ID = 1
        self.dimse.debug_receive_n_event_report_rsp(msg)

    def test_callback_receive_n_get(self):
        """Check callback for receiving DIMSE N-GET messages."""
        # N-GET-RQ
        primitive = N_GET()
        primitive.MessageID = 1
        primitive.RequestedSOPClassUID = '1.1.1'
        primitive.RequestedSOPInstanceUID = '1.1.1.1'
        msg = N_GET_RQ()
        msg.primitive_to_message(primitive)
        msg.ID = 1
        self.dimse.debug_receive_n_get_rq(msg)

        # Plus user defined
        primitive.AttributeIdentifierList = [(0x0000, 0x0000), (0xffff, 0xffff)]
        msg = N_GET_RQ()
        msg.primitive_to_message(primitive)
        msg.ID = 1
        self.dimse.debug_receive_n_get_rq(msg)

        # N-GET-RSP
        # Mandatory elements
        primitive = N_GET()
        primitive.MessageIDBeingRespondedTo = 1
        primitive.Status = 0x0000
        msg = N_GET_RSP()
        msg.primitive_to_message(primitive)
        msg.ID = 1
        self.dimse.debug_receive_n_get_rsp(msg)

        # User defined
        primitive.AffectedSOPClassUID = '1.1.1'
        primitive.AffectedSOPInstanceUID = '1.1.1.1'
        msg = N_GET_RSP()
        msg.primitive_to_message(primitive)
        msg.ID = 1
        self.dimse.debug_receive_n_get_rsp(msg)

        # Conditional
        primitive.AttributeList = BytesIO(n_get_rsp_ds)
        msg = N_GET_RSP()
        msg.primitive_to_message(primitive)
        msg.ID = 1
        self.dimse.debug_receive_n_get_rsp(msg)

    def test_callback_receive_n_set(self):
        """Check callback for receiving DIMSE N-SET messages."""
        # N-SET-RQ
        primitive = N_SET()
        primitive.MessageID = 1
        primitive.RequestedSOPClassUID = '1.1.1'
        primitive.RequestedSOPInstanceUID = '1.1.1.1'
        primitive.ModificationList = BytesIO(n_set_rq_ds)
        msg = N_SET_RQ()
        msg.primitive_to_message(primitive)
        msg.ID = 1
        self.dimse.debug_receive_n_set_rq(msg)

        # N-SET-RSP
        primitive = N_SET()
        primitive.MessageIDBeingRespondedTo = 1
        primitive.Status = 0x0000
        msg = N_SET_RSP()
        msg.primitive_to_message(primitive)
        msg.ID = 1
        self.dimse.debug_receive_n_set_rsp(msg)

        # User defined
        primitive.AffectedSOPClassUID = '1.1.1'
        primitive.AffectedSOPInstanceUID = '1.1.1.1'
        primitive.ModificationList = BytesIO(n_set_rsp_ds)
        msg = N_GET_RSP()
        msg.primitive_to_message(primitive)
        msg.ID = 1
        self.dimse.debug_receive_n_set_rsp(msg)

    def test_callback_receive_n_action(self):
        """Check callback for receiving DIMSE N-ACTION messages."""
        # N-ACTION-RQ
        primitive = N_ACTION()
        primitive.MessageID = 1
        primitive.RequestedSOPClassUID = '1.1.1'
        primitive.RequestedSOPInstanceUID = '1.1.1.1'
        primitive.ActionTypeID = 2
        msg = N_ACTION_RQ()
        msg.primitive_to_message(primitive)
        msg.ID = 1
        self.dimse.debug_receive_n_action_rq(msg)

        # User defined
        primitive.ActionInformation = BytesIO(n_action_rq_ds)
        msg = N_ACTION_RQ()
        msg.primitive_to_message(primitive)
        msg.ID = 1
        self.dimse.debug_receive_n_action_rq(msg)

        # N-ACTION-RSP
        primitive = N_ACTION()
        primitive.MessageIDBeingRespondedTo = 1
        primitive.Status = 0x0000
        msg = N_ACTION_RSP()
        msg.primitive_to_message(primitive)
        msg.ID = 1
        self.dimse.debug_receive_n_action_rsp(msg)

        # User defined
        primitive.AffectedSOPClassUID = '1.1.1'
        primitive.AffectedSOPInstanceUID = '1.1.1.1'
        primitive.ActionTypeID = 2
        primitive.ActionReply = BytesIO(n_action_rsp_ds)
        msg = N_ACTION_RSP()
        msg.primitive_to_message(primitive)
        msg.ID = 1
        self.dimse.debug_receive_n_action_rsp(msg)

    def test_callback_receive_n_create(self):
        """Check callback for receiving DIMSE N-CREATE messages."""
        # N-CREATE-RQ
        primitive = N_CREATE()
        primitive.MessageID = 1
        primitive.AffectedSOPClassUID = '1.1.1'
        msg = N_CREATE_RQ()
        msg.primitive_to_message(primitive)
        msg.ID = 1
        self.dimse.debug_receive_n_create_rq(msg)

        # User defined
        primitive.AffectedSOPInstanceUID = '1.1.1.1'
        primitive.AttributeList = BytesIO(n_create_rq_ds)
        msg = N_CREATE_RQ()
        msg.primitive_to_message(primitive)
        msg.ID = 1
        self.dimse.debug_receive_n_create_rq(msg)

        # N-CREATE-RSP
        primitive = N_CREATE()
        primitive.MessageIDBeingRespondedTo = 1
        primitive.Status = 0x0000
        msg = N_CREATE_RSP()
        msg.primitive_to_message(primitive)
        msg.ID = 1
        self.dimse.debug_receive_n_create_rsp(msg)

        # User defined
        primitive.AffectedSOPClassUID = '1.1.1'
        primitive.AffectedSOPInstanceUID = '1.1.1.1'
        primitive.AttributeList = BytesIO(n_create_rsp_ds)
        msg = N_CREATE_RSP()
        msg.primitive_to_message(primitive)
        msg.ID = 1
        self.dimse.debug_receive_n_create_rsp(msg)

    def test_callback_receive_n_delete(self):
        """Check callback for receiving DIMSE N-DELETE messages."""
        # N-DELETE-RQ
        primitive = N_DELETE()
        primitive.MessageID = 1
        primitive.RequestedSOPClassUID = '1.1.1'
        primitive.RequestedSOPInstanceUID = '1.1.1.1'
        msg = N_DELETE_RQ()
        msg.primitive_to_message(primitive)
        msg.ID = 1
        self.dimse.debug_receive_n_delete_rq(msg)

        # N-DELETE-RSP
        primitive = N_DELETE()
        primitive.MessageIDBeingRespondedTo = 1
        primitive.Status = 0x0000
        msg = N_DELETE_RSP()
        msg.primitive_to_message(primitive)
        msg.ID = 1
        self.dimse.debug_receive_n_delete_rsp(msg)

        # User optional
        primitive.AffectedSOPClassUID = '1.2.3'
        msg = N_DELETE_RSP()
        msg.primitive_to_message(primitive)
        msg.ID = 1
        self.dimse.debug_receive_n_delete_rsp(msg)

        primitive.AffectedSOPInstanceUID = '1.2.3.4'
        msg = N_DELETE_RSP()
        msg.primitive_to_message(primitive)
        msg.ID = 1
        self.dimse.debug_receive_n_delete_rsp(msg)
