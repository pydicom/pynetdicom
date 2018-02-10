#!/usr/bin/env python
"""Test DIMSE service provider operations.

TODO: Add testing of maximum pdu length flow from assoc negotiation
"""

from io import BytesIO
import logging
import unittest

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


class TestDIMSEProvider(unittest.TestCase):
    """Test DIMSE service provider operations."""
    def setUp(self):
        """Set up"""
        self.dimse = DIMSEServiceProvider(DummyDUL(), 1)

    def test_receive_not_pdata(self):
        """Test we get back None if not a P_DATA"""
        self.assertEqual(self.dimse.receive_msg(True), (None, None))

    def test_send_c_echo(self):
        """Check sending DIMSE C-ECHO messages."""
        # C-ECHO-RQ
        primitive = C_ECHO()
        primitive.MessageID = 1
        primitive.AffectedSOPClassUID = '1.1.1'

        def test_callback(msg):
            """Callback"""
            self.assertEqual(msg.__class__.__name__, 'C_ECHO_RQ')
        self.dimse.on_send_dimse_message = test_callback
        self.dimse.send_msg(primitive, 1)

        # C-ECHO-RSP
        primitive = C_ECHO()
        primitive.MessageIDBeingRespondedTo = 1
        primitive.Status = 0x0000
        def test_callback(msg):
            """Callback"""
            self.assertEqual(msg.__class__.__name__, 'C_ECHO_RSP')
        self.dimse.on_send_dimse_message = test_callback
        self.dimse.send_msg(primitive, 1)

    def test_send_c_store(self):
        """Check sending DIMSE C-STORE messages."""
        # C-STORE-RQ
        primitive = C_STORE()
        primitive.MessageID = 1
        primitive.AffectedSOPClassUID = '1.1.1'

        def test_callback(msg):
            """Callback"""
            self.assertEqual(msg.__class__.__name__, 'C_STORE_RQ')
        self.dimse.on_send_dimse_message = test_callback
        self.dimse.send_msg(primitive, 1)

        # C-STORE-RSP
        primitive = C_STORE()
        primitive.MessageIDBeingRespondedTo = 1
        primitive.Status = 0x0000
        def test_callback(msg):
            """Callback"""
            self.assertEqual(msg.__class__.__name__, 'C_STORE_RSP')
        self.dimse.on_send_dimse_message = test_callback
        self.dimse.send_msg(primitive, 1)

    def test_send_c_find(self):
        """Check sending DIMSE C-FIND messages."""
        # C-FIND-RQ
        primitive = C_FIND()
        primitive.MessageID = 1
        primitive.AffectedSOPClassUID = '1.1.1'

        def test_callback(msg):
            """Callback"""
            self.assertEqual(msg.__class__.__name__, 'C_FIND_RQ')
        self.dimse.on_send_dimse_message = test_callback
        self.dimse.send_msg(primitive, 1)

        # C-FIND-RSP
        primitive = C_FIND()
        primitive.MessageIDBeingRespondedTo = 1
        primitive.Status = 0x0000
        def test_callback(msg):
            """Callback"""
            self.assertEqual(msg.__class__.__name__, 'C_FIND_RSP')
        self.dimse.on_send_dimse_message = test_callback
        self.dimse.send_msg(primitive, 1)

    def test_send_c_get(self):
        """Check sending DIMSE C-GET messages."""
        # C-GET-RQ
        primitive = C_GET()
        primitive.MessageID = 1
        primitive.AffectedSOPClassUID = '1.1.1'

        def test_callback(msg):
            """Callback"""
            self.assertEqual(msg.__class__.__name__, 'C_GET_RQ')
        self.dimse.on_send_dimse_message = test_callback
        self.dimse.send_msg(primitive, 1)

        # C-GET-RSP
        primitive = C_GET()
        primitive.MessageIDBeingRespondedTo = 1
        primitive.Status = 0x0000
        def test_callback(msg):
            """Callback"""
            self.assertEqual(msg.__class__.__name__, 'C_GET_RSP')
        self.dimse.on_send_dimse_message = test_callback
        self.dimse.send_msg(primitive, 1)

    def test_send_c_move(self):
        """Check sending DIMSE C-MOVE messages."""
        # C-MOVE-RQ
        primitive = C_MOVE()
        primitive.MessageID = 1
        primitive.AffectedSOPClassUID = '1.1.1'

        def test_callback(msg):
            """Callback"""
            self.assertEqual(msg.__class__.__name__, 'C_MOVE_RQ')
        self.dimse.on_send_dimse_message = test_callback
        self.dimse.send_msg(primitive, 1)

        # C-MOVE-RSP
        primitive = C_MOVE()
        primitive.MessageIDBeingRespondedTo = 1
        primitive.Status = 0x0000
        def test_callback(msg):
            """Callback"""
            self.assertEqual(msg.__class__.__name__, 'C_MOVE_RSP')
        self.dimse.on_send_dimse_message = test_callback
        self.dimse.send_msg(primitive, 1)

    def test_send_c_cancel_move(self):
        """Test sending c_cancel"""
        # C-MOVE-CANCEL
        primitive = C_CANCEL()
        primitive.MessageIDBeingRespondedTo = 1
        def test_callback(msg):
            """Callback"""
            self.assertEqual(msg.__class__.__name__, 'C_CANCEL_RQ')
        self.dimse.on_send_dimse_message = test_callback
        self.dimse.send_msg(primitive, 1)

    def test_send_n_event_report(self):
        """Check sending DIMSE N-EVENT-REPORT messages."""
        # N-EVENT-REPORT-RQ
        primitive = N_EVENT_REPORT()
        primitive.MessageID = 1
        primitive.AffectedSOPClassUID = '1.1.1'

        def test_callback(msg):
            """Callback"""
            self.assertEqual(msg.__class__.__name__, 'N_EVENT_REPORT_RQ')
        self.dimse.on_send_dimse_message = test_callback
        self.dimse.send_msg(primitive, 1)

        # N-EVENT-REPORT-RSP
        primitive = N_EVENT_REPORT()
        primitive.MessageIDBeingRespondedTo = 1
        primitive.Status = 0x0000
        def test_callback(msg):
            """Callback"""
            self.assertEqual(msg.__class__.__name__, 'N_EVENT_REPORT_RSP')
        self.dimse.on_send_dimse_message = test_callback
        self.dimse.send_msg(primitive, 1)

    def test_send_n_get(self):
        """Check sending DIMSE N-GET messages."""
        # N-GET-RQ
        primitive = N_GET()
        primitive.MessageID = 1
        primitive.AffectedSOPClassUID = '1.1.1'

        def test_callback(msg):
            """Callback"""
            self.assertEqual(msg.__class__.__name__, 'N_GET_RQ')
        self.dimse.on_send_dimse_message = test_callback
        self.dimse.send_msg(primitive, 1)

        # N-GET-RSP
        primitive = N_GET()
        primitive.MessageIDBeingRespondedTo = 1
        primitive.Status = 0x0000
        def test_callback(msg):
            """Callback"""
            self.assertEqual(msg.__class__.__name__, 'N_GET_RSP')
        self.dimse.on_send_dimse_message = test_callback
        self.dimse.send_msg(primitive, 1)

    def test_send_n_set(self):
        """Check sending DIMSE N-SET messages."""
        # N-SET-RQ
        primitive = N_SET()
        primitive.MessageID = 1
        primitive.AffectedSOPClassUID = '1.1.1'

        def test_callback(msg):
            """Callback"""
            self.assertEqual(msg.__class__.__name__, 'N_SET_RQ')
        self.dimse.on_send_dimse_message = test_callback
        self.dimse.send_msg(primitive, 1)

        # N-SET-RSP
        primitive = N_SET()
        primitive.MessageIDBeingRespondedTo = 1
        primitive.Status = 0x0000
        def test_callback(msg):
            """Callback"""
            self.assertEqual(msg.__class__.__name__, 'N_SET_RSP')
        self.dimse.on_send_dimse_message = test_callback
        self.dimse.send_msg(primitive, 1)

    def test_send_n_action(self):
        """Check sending DIMSE N-ACTION messages."""
        # N-ACTION-RQ
        primitive = N_ACTION()
        primitive.MessageID = 1
        primitive.AffectedSOPClassUID = '1.1.1'

        def test_callback(msg):
            """Callback"""
            self.assertEqual(msg.__class__.__name__, 'N_ACTION_RQ')
        self.dimse.on_send_dimse_message = test_callback
        self.dimse.send_msg(primitive, 1)

        # N-ACTION-RSP
        primitive = N_ACTION()
        primitive.MessageIDBeingRespondedTo = 1
        primitive.Status = 0x0000
        def test_callback(msg):
            """Callback"""
            self.assertEqual(msg.__class__.__name__, 'N_ACTION_RSP')
        self.dimse.on_send_dimse_message = test_callback
        self.dimse.send_msg(primitive, 1)

    def test_send_n_create(self):
        """Check sending DIMSE N-CREATE messages."""
        # N-CREATE-RQ
        primitive = N_CREATE()
        primitive.MessageID = 1
        primitive.AffectedSOPClassUID = '1.1.1'

        def test_callback(msg):
            """Callback"""
            self.assertEqual(msg.__class__.__name__, 'N_CREATE_RQ')
        self.dimse.on_send_dimse_message = test_callback
        self.dimse.send_msg(primitive, 1)

        # N-CREATE-RSP
        primitive = N_CREATE()
        primitive.MessageIDBeingRespondedTo = 1
        primitive.Status = 0x0000
        def test_callback(msg):
            """Callback"""
            self.assertEqual(msg.__class__.__name__, 'N_CREATE_RSP')
        self.dimse.on_send_dimse_message = test_callback
        self.dimse.send_msg(primitive, 1)

    def test_send_n_delete(self):
        """Check sending DIMSE N-DELETE messages."""
        # N-DELETE-RQ
        primitive = N_DELETE()
        primitive.MessageID = 1
        primitive.AffectedSOPClassUID = '1.1.1'

        def test_callback(msg):
            """Callback"""
            self.assertEqual(msg.__class__.__name__, 'N_DELETE_RQ')
        self.dimse.on_send_dimse_message = test_callback
        self.dimse.send_msg(primitive, 1)

        # N-DELETE-RSP
        primitive = N_DELETE()
        primitive.MessageIDBeingRespondedTo = 1
        primitive.Status = 0x0000
        def test_callback(msg):
            """Callback"""
            self.assertEqual(msg.__class__.__name__, 'N_DELETE_RSP')
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


class TestDIMSEProviderCallbacks(unittest.TestCase):
    """Test the callbacks for the DIMSE Service"""
    def setUp(self):
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
        self.dimse.send_msg(primitive, 1)

        # N-EVENT-REPORT-RSP
        primitive = N_EVENT_REPORT()
        primitive.MessageIDBeingRespondedTo = 1
        primitive.Status = 0x0000
        self.dimse.send_msg(primitive, 1)

    def test_callback_send_n_get(self):
        """Check callback for sending DIMSE N-GET messages."""
        # N-GET-RQ
        primitive = N_GET()
        primitive.MessageID = 1
        primitive.AffectedSOPClassUID = '1.1.1'
        self.dimse.send_msg(primitive, 1)

        # N-GET-RSP
        primitive = N_GET()
        primitive.MessageIDBeingRespondedTo = 1
        primitive.Status = 0x0000
        self.dimse.send_msg(primitive, 1)

    def test_callback_send_n_set(self):
        """Check callback for sending DIMSE N-SET messages."""
        # N-SET-RQ
        primitive = N_SET()
        primitive.MessageID = 1
        primitive.AffectedSOPClassUID = '1.1.1'
        self.dimse.send_msg(primitive, 1)

        # N-SET-RSP
        primitive = N_SET()
        primitive.MessageIDBeingRespondedTo = 1
        primitive.Status = 0x0000
        self.dimse.send_msg(primitive, 1)

    def test_callback_send_n_action(self):
        """Check callback for sending DIMSE N-ACTION messages."""
        # N-ACTION-RQ
        primitive = N_ACTION()
        primitive.MessageID = 1
        primitive.AffectedSOPClassUID = '1.1.1'
        self.dimse.send_msg(primitive, 1)

        # N-ACTION-RSP
        primitive = N_ACTION()
        primitive.MessageIDBeingRespondedTo = 1
        primitive.Status = 0x0000
        self.dimse.send_msg(primitive, 1)

    def test_callback_send_n_create(self):
        """Check callback for sending DIMSE N-CREATE messages."""
        # N-CREATE-RQ
        primitive = N_CREATE()
        primitive.MessageID = 1
        primitive.AffectedSOPClassUID = '1.1.1'
        self.dimse.send_msg(primitive, 1)

        # N-CREATE-RSP
        primitive = N_CREATE()
        primitive.MessageIDBeingRespondedTo = 1
        primitive.Status = 0x0000
        self.dimse.send_msg(primitive, 1)

    def test_callback_send_n_delete(self):
        """Check callback for sending DIMSE N-DELETE messages."""
        # N-DELETE-RQ
        primitive = N_DELETE()
        primitive.MessageID = 1
        primitive.AffectedSOPClassUID = '1.1.1'
        self.dimse.send_msg(primitive, 1)

        # N-DELETE-RSP
        primitive = N_DELETE()
        primitive.MessageIDBeingRespondedTo = 1
        primitive.Status = 0x0000
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
        msg = N_EVENT_REPORT_RQ()
        self.dimse.debug_receive_n_event_report_rq(msg)

        # N-EVENT-REPORT-RSP
        msg = N_EVENT_REPORT_RSP()
        self.dimse.debug_receive_n_event_report_rsp(msg)

    def test_callback_receive_n_get(self):
        """Check callback for receiving DIMSE N-GET messages."""
        # N-GET-RQ
        msg = N_GET_RQ()
        self.dimse.debug_receive_n_get_rq(msg)

        # N-GET-RSP
        msg = N_GET_RSP()
        self.dimse.debug_receive_n_get_rsp(msg)

    def test_callback_receive_n_set(self):
        """Check callback for receiving DIMSE N-SET messages."""
        # N-SET-RQ
        msg = N_SET_RQ()
        self.dimse.debug_receive_n_set_rq(msg)

        # N-SET-RSP
        msg = N_SET_RSP()
        self.dimse.debug_receive_n_set_rsp(msg)

    def test_callback_receive_n_action(self):
        """Check callback for receiving DIMSE N-ACTION messages."""
        # N-ACTION-RQ
        msg = N_ACTION_RQ()
        self.dimse.debug_receive_n_action_rq(msg)

        # N-ACTION-RSP
        msg = N_ACTION_RQ()
        self.dimse.debug_receive_n_action_rsp(msg)

    def test_callback_receive_n_create(self):
        """Check callback for receiving DIMSE N-CREATE messages."""
        # N-CREATE-RQ
        msg = N_CREATE_RQ()
        self.dimse.debug_receive_n_create_rq(msg)

        # N-CREATE-RSP
        msg = N_CREATE_RQ()
        self.dimse.debug_receive_n_create_rsp(msg)

    def test_callback_receive_n_delete(self):
        """Check callback for receiving DIMSE N-DELETE messages."""
        # N-DELETE-RQ
        msg = N_DELETE_RQ()
        self.dimse.debug_receive_n_delete_rq(msg)

        # N-DELETE-RSP
        msg = N_DELETE_RQ()
        self.dimse.debug_receive_n_delete_rsp(msg)


if __name__ == "__main__":
    unittest.main()
