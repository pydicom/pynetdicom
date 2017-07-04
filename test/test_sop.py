"""Unit tests for the Status class."""

import logging
import os
import unittest

from pydicom import read_file
from pydicom.dataset import Dataset

from pynetdicom3 import AE
from pynetdicom3.dimse_primitives import C_ECHO
from dummy_c_scp import DummyVerificationSCP, DummyStorageSCP
from pynetdicom3.sop_class import (Status, uid_to_sop_class,
                                   VerificationServiceClass,
                                   StorageServiceClass,
                                   QueryRetrieveGetServiceClass,
                                   QueryRetrieveFindServiceClass,
                                   QueryRetrieveMoveServiceClass,
                                   ModalityWorklistServiceSOPClass,
                                   VerificationSOPClass,
                                   CTImageStorage)

LOGGER = logging.getLogger('pynetdicom3')
LOGGER.setLevel(logging.DEBUG)

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
    def test_scp_callback_return_dataset(self):
        """Test on_c_echo returning a Dataset status"""
        scp = DummyVerificationSCP()
        scp.status = Dataset()
        scp.status.Status = 0x0001
        scp.start()

        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        rsp = assoc.send_c_echo()
        self.assertEqual(rsp.Status, 0x0001)
        assoc.release()
        scp.stop()

    def test_scp_callback_return_dataset_multi(self):
        """Test on_c_echo returning a Dataset status with other elements"""
        scp = DummyVerificationSCP()
        scp.status = Dataset()
        scp.status.Status = 0x0001
        scp.status.ErrorComment = 'Test'
        scp.start()

        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        rsp = assoc.send_c_echo()
        self.assertEqual(rsp.Status, 0x0001)
        self.assertEqual(rsp.ErrorComment, 'Test')
        assoc.release()
        scp.stop()

    def test_scp_callback_return_int(self):
        """Test on_c_echo returning an int status"""
        scp = DummyVerificationSCP()
        scp.status = 0x0002
        scp.start()

        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        rsp = assoc.send_c_echo()
        self.assertEqual(rsp.Status, 0x0002)
        self.assertFalse('ErrorComment' in rsp)
        assoc.release()
        scp.stop()

    def test_scp_callback_return_valid(self):
        """Test on_c_echo returning a valid status"""
        scp = DummyVerificationSCP()
        scp.status = 0x0000
        scp.start()

        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        rsp = assoc.send_c_echo()
        self.assertEqual(rsp.Status, 0x0000)
        assoc.release()
        scp.stop()

    def test_scp_callback_no_status(self):
        """Test on_c_echo not returning a status"""
        scp = DummyVerificationSCP()
        scp.status = None
        scp.start()

        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        rsp = assoc.send_c_echo()
        self.assertEqual(rsp.Status, 0x0000)
        assoc.release()
        scp.stop()

    def test_scp_callback_exception(self):
        """Test on_c_echo raising an exception"""
        scp = DummyVerificationSCP()
        def on_c_echo(): raise ValueError
        scp.ae.on_c_echo = on_c_echo
        scp.start()

        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        rsp = assoc.send_c_echo()
        self.assertEqual(rsp.Status, 0x0000)
        assoc.release()
        scp.stop()


class TestStorageServiceClass(unittest.TestCase):
    """Test the StorageServiceClass"""
    def test_scp_callback_return_dataset(self):
        """Test on_c_store returning a Dataset status"""
        scp = DummyStorageSCP()
        scp.status = Dataset()
        scp.status.Status = 0x0001
        scp.start()

        ae = AE(scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        rsp = assoc.send_c_store(DATASET)
        self.assertEqual(rsp.Status, 0x0001)
        assoc.release()
        scp.stop()

    def test_scp_callback_return_dataset_multi(self):
        """Test on_c_store returning a Dataset status with other elements"""
        scp = DummyStorageSCP()
        scp.status = Dataset()
        scp.status.Status = 0x0001
        scp.status.ErrorComment = 'Test'
        scp.status.OffendingElement = 0x00080010
        scp.start()

        ae = AE(scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        rsp = assoc.send_c_store(DATASET)
        self.assertEqual(rsp.Status, 0x0001)
        self.assertEqual(rsp.ErrorComment, 'Test')
        self.assertEqual(rsp.OffendingElement, 0x00080010)
        assoc.release()
        scp.stop()

    def test_scp_callback_return_int(self):
        """Test on_c_echo returning an int status"""
        scp = DummyStorageSCP()
        scp.status = 0x0002
        scp.start()

        ae = AE(scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        rsp = assoc.send_c_store(DATASET)
        self.assertEqual(rsp.Status, 0x0002)
        self.assertFalse('ErrorComment' in rsp)
        assoc.release()
        scp.stop()

    def test_scp_callback_return_valid(self):
        """Test on_c_store returning a valid status"""
        scp = DummyStorageSCP()
        scp.status = 0x0000
        scp.start()

        ae = AE(scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        rsp = assoc.send_c_store(DATASET)
        self.assertEqual(rsp.Status, 0x0000)
        assoc.release()
        scp.stop()

    def test_scp_callback_no_status(self):
        """Test on_c_store not returning a status"""
        scp = DummyStorageSCP()
        scp.status = None
        scp.start()

        ae = AE(scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        rsp = assoc.send_c_store(DATASET)
        self.assertEqual(rsp.Status, 0xC103)
        assoc.release()
        scp.stop()

    def test_scp_callback_exception(self):
        """Test on_c_store raising an exception"""
        scp = DummyStorageSCP()
        def on_c_store(ds): raise ValueError
        scp.ae.on_c_store = on_c_store
        scp.start()

        ae = AE(scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        rsp = assoc.send_c_store(DATASET)
        self.assertEqual(rsp.Status, 0xC101)
        assoc.release()
        scp.stop()


class TestQRFindServiceClass(unittest.TestCase):
    def test_scp(self):
        """Test SCP"""
        pass


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
