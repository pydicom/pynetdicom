#!/usr/bin/env python
"""Status testing"""

import logging
import unittest

from pynetdicom3.status import code_to_status, Status

LOGGER = logging.getLogger('pynetdicom3')
LOGGER.setLevel(logging.CRITICAL)

class TestStatus(unittest.TestCase):
    """Test the Status"""
    def test_bad_init(self):
        """Test bad init of Status"""
        self.assertRaises(TypeError, Status)
        self.assertRaises(ValueError, Status, 'abc')
        self.assertRaises(ValueError, Status, 1.2)
        self.assertRaises(ValueError, Status, -0x0001)

    def test_good_init(self):
        """Test good init of Status"""
        st = Status(0x0000)
        self.assertTrue(st.Status == 0x0000)
        st = Status(0xFFFF)
        self.assertTrue(st.Status == 0xFFFF)

    def test_change_status(self):
        """Changing status value works OK"""
        st = Status(0x0000)
        self.assertTrue(st.Status == 0x0000)
        st.Status = 0xFFFF
        self.assertTrue(st.Status == 0xFFFF)

    def test_status_to_int(self):
        """Test using Status as an int works OK"""
        st = Status(0x0000)
        self.assertEqual(int(st), 0x0000)
        st.Status = 0xFFFF
        self.assertEqual(int(st), 0xFFFF)

    def test_add_non_0000(self):
        """Test adding non group 0x0000 elements raises"""
        st = Status(0x0000)
        def test():
            st.PatientName = 'Test'

        self.assertRaises(ValueError, test)

    def test_add_elem(self):
        """Test adding group 0x0000 elements"""
        st = Status(0x0000)
        st.OffendingElement = 0x00010002
        st.ErrorComment = 'Some comment'
        self.assertTrue('OffendingElement' in st)
        self.assertTrue('ErrorComment' in st)
        self.assertEqual(st.OffendingElement, 0x00010002)
        self.assertEqual(st.ErrorComment, 'Some comment')

    def test_eq(self):
        """Test equality operator"""
        self.assertEqual(Status(0x0000), 0x0000)
        self.assertEqual(Status(0xFFFE), 0xFFFE)
        self.assertEqual(Status(0xFFEE), Status(0xFFEE))

    def test_ne(self):
        """Test inequality operator"""
        self.assertNotEqual(Status(0x0000), 0xFFFF)
        self.assertNotEqual(Status(0xFFFE), 0x0000)
        self.assertNotEqual(Status(0xFFEE), Status(0x0000))

    def test_code_to_status(self):
        """Test fetching status works"""
        status = code_to_status(0x0123)
        self.assertTrue(isinstance(status, Status))
        self.assertTrue(status == 0x0123)
        self.assertTrue(status.Status == 0x0123)
        self.assertEqual(status.description, 'No Such Action')
        self.assertEqual(status.category, 'Failure')
        self.assertEqual(status.text, '')


if __name__ == "__main__":
    unittest.main()
