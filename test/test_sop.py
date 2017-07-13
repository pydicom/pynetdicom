"""Unit tests for the Status class."""

import logging
import os
import threading
import time
import unittest

from pydicom import read_file
from pydicom.dataset import Dataset

from pynetdicom3 import AE
from pynetdicom3.dimse_primitives import C_ECHO
from dummy_c_scp import (DummyVerificationSCP, DummyStorageSCP, DummyFindSCP,
                         DummyBaseSCP)
from pynetdicom3.sop_class import (uid_to_sop_class,
                                   VerificationServiceClass,
                                   StorageServiceClass,
                                   QueryRetrieveGetServiceClass,
                                   QueryRetrieveFindServiceClass,
                                   QueryRetrieveMoveServiceClass,
                                   ModalityWorklistServiceSOPClass,
                                   VerificationSOPClass,
                                   CTImageStorage,
                                   PatientRootQueryRetrieveInformationModelFind)

LOGGER = logging.getLogger('pynetdicom3')
#LOGGER.setLevel(logging.DEBUG)
LOGGER.setLevel(logging.CRITICAL)

TEST_DS_DIR = os.path.join(os.path.dirname(__file__), 'dicom_files')
DATASET = read_file(os.path.join(TEST_DS_DIR, 'CTImageStorage.dcm'))

class DummyAE(object):
    """Dummy class for testing callback errors"""
    @staticmethod
    def on_c_echo():
        """Dummy method to test callback errors"""
        raise ValueError

    @staticmethod
    def on_c_store():
        """Dummy method to test callback errors"""
        raise ValueError

    @staticmethod
    def on_c_find():
        """Dummy method to test callback errors"""
        raise ValueError

    @staticmethod
    def on_c_cancel_find():
        """Dummy method to test callback errors"""
        raise ValueError

    @staticmethod
    def on_c_get():
        """Dummy method to test callback errors"""
        raise ValueError

    @staticmethod
    def on_c_cancel_get():
        """Dummy method to test callback errors"""
        raise ValueError

    @staticmethod
    def on_c_move():
        """Dummy method to test callback errors"""
        raise ValueError

    @staticmethod
    def on_c_cancel_move():
        """Dummy method to test callback errors"""
        raise ValueError


class DummyDIMSE(object):
    """Dummy DIMSE provider"""
    def send_msg(self, msg, context_id, length):
        """Dummy Send method"""
        pass


class TestServiceClass(unittest.TestCase):
    def test_is_valid_status(self):
        """Test that is_valid_status returns correct values"""
        sop = StorageServiceClass()
        self.assertFalse(sop.is_valid_status(0x0101))
        self.assertTrue(sop.is_valid_status(0x0000))


class TestVerificationServiceClass(unittest.TestCase):
    """Test the VerifictionSOPClass"""
    def setUp(self):
        """Run prior to each test"""
        self.scp = None

    def tearDown(self):
        """Clear any active threads"""
        if self.scp:
            self.scp.abort()

        time.sleep(0.1)

        for thread in threading.enumerate():
            if isinstance(thread, DummyBaseSCP):
                thread.abort()
                thread.stop()

    def test_scp_callback_return_dataset(self):
        """Test on_c_echo returning a Dataset status"""
        self.scp = DummyVerificationSCP()
        self.scp.status = Dataset()
        self.scp.status.Status = 0x0001
        self.scp.start()

        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        rsp = assoc.send_c_echo()
        self.assertEqual(rsp.Status, 0x0001)
        assoc.release()
        self.scp.stop()

    def test_scp_callback_return_dataset_multi(self):
        """Test on_c_echo returning a Dataset status with other elements"""
        self.scp = DummyVerificationSCP()
        self.scp.status = Dataset()
        self.scp.status.Status = 0x0001
        self.scp.status.ErrorComment = 'Test'
        self.scp.start()

        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        rsp = assoc.send_c_echo()
        self.assertEqual(rsp.Status, 0x0001)
        self.assertEqual(rsp.ErrorComment, 'Test')
        assoc.release()
        self.scp.stop()

    def test_scp_callback_return_int(self):
        """Test on_c_echo returning an int status"""
        self.scp = DummyVerificationSCP()
        self.scp.status = 0x0002
        self.scp.start()

        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        rsp = assoc.send_c_echo()
        self.assertEqual(rsp.Status, 0x0002)
        self.assertFalse('ErrorComment' in rsp)
        assoc.release()
        self.scp.stop()

    def test_scp_callback_return_valid(self):
        """Test on_c_echo returning a valid status"""
        self.scp = DummyVerificationSCP()
        self.scp.status = 0x0000
        self.scp.start()

        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        rsp = assoc.send_c_echo()
        self.assertEqual(rsp.Status, 0x0000)
        assoc.release()
        self.scp.stop()

    def test_scp_callback_no_status(self):
        """Test on_c_echo not returning a status"""
        self.scp = DummyVerificationSCP()
        self.scp.status = None
        self.scp.start()

        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        rsp = assoc.send_c_echo()
        self.assertEqual(rsp.Status, 0x0000)
        assoc.release()
        self.scp.stop()

    def test_scp_callback_exception(self):
        """Test on_c_echo raising an exception"""
        self.scp = DummyVerificationSCP()
        def on_c_echo(): raise ValueError
        self.scp.ae.on_c_echo = on_c_echo
        self.scp.start()

        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        rsp = assoc.send_c_echo()
        self.assertEqual(rsp.Status, 0x0000)
        assoc.release()
        self.scp.stop()


class TestStorageServiceClass(unittest.TestCase):
    """Test the StorageServiceClass"""
    def setUp(self):
        """Run prior to each test"""
        self.scp = None

    def tearDown(self):
        """Clear any active threads"""
        if self.scp:
            self.scp.abort()

        time.sleep(0.1)

        for thread in threading.enumerate():
            if isinstance(thread, DummyBaseSCP):
                thread.abort()
                thread.stop()

    def test_scp_callback_return_dataset(self):
        """Test on_c_store returning a Dataset status"""
        self.scp = DummyStorageSCP()
        self.scp.status = Dataset()
        self.scp.status.Status = 0x0001
        self.scp.start()

        ae = AE(scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        rsp = assoc.send_c_store(DATASET)
        self.assertEqual(rsp.Status, 0x0001)
        assoc.release()
        self.scp.stop()

    def test_scp_callback_return_dataset_multi(self):
        """Test on_c_store returning a Dataset status with other elements"""
        self.scp = DummyStorageSCP()
        self.scp.status = Dataset()
        self.scp.status.Status = 0x0001
        self.scp.status.ErrorComment = 'Test'
        self.scp.status.OffendingElement = 0x00080010
        self.scp.start()

        ae = AE(scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        rsp = assoc.send_c_store(DATASET)
        self.assertEqual(rsp.Status, 0x0001)
        self.assertEqual(rsp.ErrorComment, 'Test')
        self.assertEqual(rsp.OffendingElement, 0x00080010)
        assoc.release()
        self.scp.stop()

    def test_scp_callback_return_int(self):
        """Test on_c_echo returning an int status"""
        self.scp = DummyStorageSCP()
        self.scp.status = 0x0000
        self.scp.start()

        ae = AE(scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        rsp = assoc.send_c_store(DATASET)
        self.assertEqual(rsp.Status, 0x0000)
        self.assertFalse('ErrorComment' in rsp)
        assoc.release()
        self.scp.stop()

    def test_scp_callback_return_invalid(self):
        """Test on_c_store returning a valid status"""
        self.scp = DummyStorageSCP()
        self.scp.status = 0xFFF0
        self.scp.start()

        ae = AE(scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        rsp = assoc.send_c_store(DATASET)
        self.assertEqual(rsp.Status, 0xFFF0)
        assoc.release()
        self.scp.stop()

    def test_scp_callback_no_status(self):
        """Test on_c_store not returning a status"""
        self.scp = DummyStorageSCP()
        self.scp.status = None
        self.scp.start()

        ae = AE(scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        rsp = assoc.send_c_store(DATASET)
        self.assertEqual(rsp.Status, 0xC103)
        assoc.release()
        self.scp.stop()

    def test_scp_callback_exception(self):
        """Test on_c_store raising an exception"""
        self.scp = DummyStorageSCP()
        def on_c_store(ds): raise ValueError
        self.scp.ae.on_c_store = on_c_store
        self.scp.start()

        ae = AE(scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        rsp = assoc.send_c_store(DATASET)
        self.assertEqual(rsp.Status, 0xC101)
        assoc.release()
        self.scp.stop()


class TestQRFindServiceClass(unittest.TestCase):
    """Test the QueryRetrieveFindServiceClass"""
    def setUp(self):
        """Run prior to each test"""
        self.query = Dataset()
        self.query.PatientName = '*'
        self.query.QueryRetrieveLevel = "PATIENT"

        self.scp = None

    def tearDown(self):
        """Clear any active threads"""
        if self.scp:
            self.scp.abort()

        time.sleep(0.1)

        for thread in threading.enumerate():
            if isinstance(thread, DummyBaseSCP):
                thread.abort()
                thread.stop()

    def test_scp_callback_return_dataset(self):
        """Test on_c_find returning a Dataset status"""
        self.scp = DummyFindSCP()
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_find(self.query, query_model='P')
        status, identifier = next(result)
        self.assertEqual(status.Status, 0xFF00)
        status, identifier = next(result)
        self.assertEqual(status.Status, 0x0000)

        assoc.release()
        self.scp.stop()

    def test_scp_callback_return_dataset_multi(self):
        """Test on_c_store returning a Dataset status with other elements"""
        self.scp = DummyFindSCP()
        self.scp.status = Dataset()
        self.scp.status.Status = 0xFF00
        self.scp.status.ErrorComment = 'Test'
        self.scp.status.OffendingElement = 0x00010001
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_find(self.query, query_model='P')
        status, identifier = next(result)
        self.assertEqual(status.Status, 0xFF00)
        self.assertEqual(status.ErrorComment, 'Test')
        self.assertEqual(status.OffendingElement, 0x00010001)
        status, identifier = next(result)
        self.assertEqual(status.Status, 0x0000)

        assoc.release()
        self.scp.stop()

    def test_scp_callback_return_int(self):
        """Test on_c_find returning an int status"""
        self.scp = DummyFindSCP()
        self.scp.status = 0xFF00
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_find(self.query, query_model='P')
        status, identifier = next(result)
        self.assertEqual(status.Status, 0xFF00)
        status, identifier = next(result)
        self.assertEqual(status.Status, 0x0000)

        assoc.release()
        self.scp.stop()

    def test_scp_callback_return_invalid(self):
        """Test on_c_store returning a invalid status"""
        self.scp = DummyFindSCP()
        self.scp.status = 0xFFF0
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_find(self.query, query_model='P')
        status, identifier = next(result)
        self.assertEqual(status.Status, 0xFFF0)
        self.assertRaises(StopIteration, next, result)
        assoc.release()
        self.scp.stop()

    def test_scp_callback_no_status(self):
        """Test on_c_store not returning a status"""
        self.scp = DummyFindSCP()
        self.scp.status = None
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_find(self.query, query_model='P')
        status, identifier = next(result)
        self.assertEqual(status.Status, 0xC000)
        self.assertRaises(StopIteration, next, result)
        assoc.release()
        self.scp.stop()

    def test_scp_callback_exception(self):
        """Test on_c_store raising an exception"""
        self.scp = DummyFindSCP()
        def on_c_find(ds): raise ValueError
        self.scp.ae.on_c_find = on_c_find
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_find(self.query, query_model='P')
        status, identifier = next(result)
        self.assertEqual(status.Status, 0xC001)
        self.assertRaises(StopIteration, next, result)
        assoc.release()
        self.scp.stop()


class TestQRGetServiceClass(unittest.TestCase):
    def test_scp(self):
        """Test SCP"""
        pass


class TestQRMoveServiceClass(unittest.TestCase):
    def test_scp(self):
        """Test SCP"""
        pass


class TestModalityWorklistServiceClass(unittest.TestCase):
    def test_scp(self):
        """Test SCP"""
        pass


class TestRTMachineVerificationServiceClass(unittest.TestCase):
    def test_scp(self):
        """Test SCP"""
        pass


class TestUIDtoSOPlass(unittest.TestCase):
    def test_missing_sop(self):
        """Test raise if SOP Class not found."""
        with self.assertRaises(NotImplementedError):
            uid_to_sop_class('1.2.3.4')


if __name__ == "__main__":
    unittest.main()
