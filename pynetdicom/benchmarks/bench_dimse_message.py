"""Performance tests for decoding DIMSE messages."""

from io import BytesIO
import os
import threading
import time

from pydicom import dcmread

from pynetdicom.dimse_messages import DIMSEMessage, C_STORE_RQ
from pynetdicom.dimse_primitives import C_STORE
from pynetdicom.dsutils import encode


TEST_DS_DIR = os.path.join(os.path.dirname(__file__), '../tests', 'dicom_files')
DATASET = dcmread(os.path.join(TEST_DS_DIR, 'CTImageStorage.dcm'))


class TestDecodeMessage(object):
    def setup(self):
        """Run prior to each test"""
        primitive = C_STORE()
        primitive.MessageID = 7
        primitive.AffectedSOPClassUID = '1.1.1'
        primitive.AffectedSOPInstanceUID = '1.2.1'
        primitive.Priority = 0x02
        primitive.MoveOriginatorApplicationEntityTitle = b'UNITTEST'
        primitive.MoveOriginatorMessageID = 3
        primitive.DataSet = BytesIO(encode(DATASET, True, True))
        msg = C_STORE_RQ()
        msg.primitive_to_message(primitive)
        self.fragments = msg.encode_msg(1, 16382)

    def time_decode(self):
        """Benchmark for standard decode."""
        for ii in range(100):
            msg = DIMSEMessage()
            for fragment in self.fragments:
                msg.decode_msg(fragment)

class TestEncodeMessage(object):
    def setup(self):
        primitive = C_STORE()
        primitive.MessageID = 7
        primitive.AffectedSOPClassUID = '1.1.1'
        primitive.AffectedSOPInstanceUID = '1.2.1'
        primitive.Priority = 0x02
        primitive.MoveOriginatorApplicationEntityTitle = b'UNITTEST'
        primitive.MoveOriginatorMessageID = 3
        primitive.DataSet = BytesIO(encode(DATASET, True, True))
        self.msg = C_STORE_RQ()
        self.msg.primitive_to_message(primitive)

    def time_encode(self):
        """Benchmark for standard encode."""
        for ii in range(100):
            for fragment in self.msg.encode_msg(1, 16382):
                pass
