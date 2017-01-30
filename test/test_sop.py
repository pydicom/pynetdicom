"""Unit tests for the Status class."""

import logging
import unittest

from pynetdicom3.dimse_primitives import C_ECHO
from pynetdicom3.sop_class import Status, uid_to_sop_class, \
                                 VerificationServiceClass, \
                                 StorageServiceClass, \
                                 QueryRetrieveGetServiceClass, \
                                 QueryRetrieveFindServiceClass, \
                                 QueryRetrieveMoveServiceClass, \
                                 ModalityWorklistServiceSOPClass, \
                                 RTMachineVerificationServiceClass, \
                                 VerificationSOPClass

LOGGER = logging.getLogger('pynetdicom3')
LOGGER.setLevel(logging.CRITICAL)


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
    def Send(self, msg, context_id, length):
        """Dummy Send method"""
        pass


class TestServiceClass(unittest.TestCase):
    def test_code_to_status(self):
        """Test conversion of status code to Status class."""
        sop = VerificationServiceClass()
        with self.assertRaises(ValueError):
            sop.code_to_status(0x0001)
            
        with self.assertRaises(TypeError):
            sop.code_to_status('test')

    def test_is_valid_status(self):
        """Test that is_valid_status returns correct values"""
        sop = StorageServiceClass()
        status = Status('Test', 'A test status', range(0x0101, 0x0101 + 1))
        self.assertFalse(sop.is_valid_status(status))
        self.assertTrue(sop.is_valid_status(sop.Success))


class TestVerificationServiceClass(unittest.TestCase):
    """Test the VerifictionSOPClass"""
    def test_scp_callback_exception(self):
        """Test errors in on_c_echo are caught"""
        sop = VerificationSOPClass()
        sop.ae = DummyAE()
        sop.DIMSE = DummyDIMSE()
        sop.pcid = 1
        sop.maxpdulength = 10

        msg = C_ECHO()
        msg.MessageID = 12
        # compatibility error python3.3
        #with self.assertLogs('pynetdicom3') as log:
        #    sop.SCP(msg)
        #self.assertTrue("Exception in the AE.on_c_echo() callback" in log.output[0])


class TestStorageServiceClass(unittest.TestCase):
    def test_scp(self):
        """Test SCP"""
        pass


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


class TestStatus(unittest.TestCase):
    def test_init(self):
        """Test Status initialisation."""
        status = Status('Success', 'A test status', range(0x0000, 0x0000 + 2))
        self.assertEqual(status.status_type, 'Success')
        self.assertEqual(status.description, 'A test status')
        self.assertEqual(status.code_range, range(0x0000, 0x0000 + 2))

    def test_assign_code(self):
        """Test assigning a specific code to a Status."""
        status = Status('Success', 'A test status', range(0x0000, 0x0000 + 2))
        status.code = 0x0001
        self.assertEqual(status.code, 0x0001)
        with self.assertRaises(ValueError):
            status.code = 0x0002
        with self.assertRaises(TypeError):
            status.code = 'a'

    def test_int(self):
        """Test the Status __int__ method."""
        status = Status('Success', 'A test status', range(0x0000, 0x0000 + 2))
        # Test default code
        self.assertEqual(int(status), 0x0000)
        status.code = 0x0001
        # Test assigned code
        self.assertEqual(int(status), 0x0001)

    def test_str(self):
        """Test the Status __str__ method."""
        status = Status('Success', 'A test status', range(0x0000, 0x0000 + 2))
        self.assertEqual(str(status), '0x0000: Success - A test status')


class TestUIDtoSOPlass(unittest.TestCase):
    def test_missing_sop(self):
        """Test raise if SOP Class not found."""
        with self.assertRaises(NotImplementedError):
            uid_to_sop_class('1.2.3.4')


if __name__ == "__main__":
    unittest.main()
