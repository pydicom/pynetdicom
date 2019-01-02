"""Performance tests for sending DIMSE-C messages."""

import os
import threading
import time

from pydicom import dcmread

from pynetdicom import AE
from pynetdicom.sop_class import CTImageStorage, VerificationSOPClass
from pynetdicom.tests.dummy_c_scp import (
    DummyVerificationSCP, DummyStorageSCP, DummyFindSCP, DummyBaseSCP,
    DummyGetSCP, DummyMoveSCP
)


DS_DIR = os.path.join(os.path.dirname(__file__), '../tests', 'dicom_files')
DATASET = dcmread(os.path.join(DS_DIR, 'CTImageStorage.dcm'))


class TestSendCEcho(object):
    def setup(self):
        """Run prior to each test"""
        self.scp = DummyVerificationSCP()
        self.scp.start()

        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        self.assoc = ae.associate('localhost', 11112)

    def teardown(self):
        """Clear any active threads"""
        if self.scp:
            self.scp.abort()

        time.sleep(0.1)

        for thread in threading.enumerate():
            if isinstance(thread, DummyBaseSCP):
                thread.abort()
                thread.stop()

    def time_send_c_echo(self):
        "Test sending 100 C-ECHO messages over the same association."
        if self.assoc.is_established:
            for ii in range(100):
                rsp = self.assoc.send_c_echo()
                assert rsp.Status == 0x0000

            self.assoc.release()
        else:
            raise RuntimeError('Unable to associate with the echo SCP')


class TestSendCStore(object):
    def setup(self):
        """Run prior to each test"""
        self.scp = DummyStorageSCP()
        self.scp.status = 0x0000
        self.scp.start()

        ae = AE()
        ae.add_requested_context(CTImageStorage)
        self.assoc = ae.associate('localhost', 11112)

    def teardown(self):
        """Clear any active threads"""
        if self.scp:
            self.scp.abort()

        time.sleep(0.1)

        for thread in threading.enumerate():
            if isinstance(thread, DummyBaseSCP):
                thread.abort()
                thread.stop()

    def time_send_c_store(self):
        "Test sending 100 C-STORE messages over the same association."
        if self.assoc.is_established:
            for ii in range(100):
                rsp = self.assoc.send_c_store(DATASET)
                assert rsp.Status == 0x0000

            self.assoc.release()
        else:
            raise RuntimeError('Unable to associate with the echo SCP')
