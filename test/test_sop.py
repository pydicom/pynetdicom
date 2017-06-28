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
    def send_msg(self, msg, context_id, length):
        """Dummy Send method"""
        pass


class TestServiceClass(unittest.TestCase):
    def test_is_valid_status(self):
        """Test that is_valid_status returns correct values"""
        sop = StorageServiceClass()
        st = Status(0x0101)
        self.assertFalse(sop.is_valid_status(st))
        st = Status(0x0000)
        self.assertTrue(sop.is_valid_status(st))


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


class TestUIDtoSOPlass(unittest.TestCase):
    def test_missing_sop(self):
        """Test raise if SOP Class not found."""
        with self.assertRaises(NotImplementedError):
            uid_to_sop_class('1.2.3.4')


if __name__ == "__main__":
    unittest.main()
