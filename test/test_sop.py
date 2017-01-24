"""Unit tests for the Status class."""

import logging
import unittest

from pynetdicom3.SOPclass import Status, uid_to_sop_class, \
                                 VerificationServiceClass, \
                                 StorageServiceClass, \
                                 QueryRetrieveGetServiceClass, \
                                 QueryRetrieveFindServiceClass, \
                                 QueryRetrieveMoveServiceClass, \
                                 ModalityWorklistServiceSOPClass, \
                                 RTMachineVerificationServiceClass

LOGGER = logging.getLogger('pynetdicom3')
LOGGER.setLevel(logging.CRITICAL)


class TestServiceClass(unittest.TestCase):
    def test_code_to_status(self):
        """Test conversion of status code to Status class."""
        sop = VerificationServiceClass()
        with self.assertRaises(ValueError):
            sop.code_to_status(0x0001)


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
