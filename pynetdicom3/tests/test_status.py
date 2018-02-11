#!/usr/bin/env python
"""Status testing"""

import logging
import unittest

import pytest

from pydicom.dataset import Dataset

from pynetdicom3.status import code_to_category, code_to_status


LOGGER = logging.getLogger('pynetdicom3')
LOGGER.setLevel(logging.CRITICAL)


class TestStatus(unittest.TestCase):
    """Test the status.py module"""
    def test_code_to_status(self):
        """Test converting a status code to a Dataset"""
        status = code_to_status(0x0123)
        self.assertTrue(isinstance(status, Dataset))
        self.assertTrue(status.Status == 0x0123)
        del status.Status
        self.assertEqual(status, Dataset())

        assert pytest.raises(ValueError, code_to_status, -0x0001)

    def test_code_to_category_unknown(self):
        """Test converting an unknown status code to its category"""
        self.assertEqual(code_to_category(0xDF01), 'Unknown')

    def test_code_to_category_general(self):
        """Test converting a general status code to its category"""
        c2c = code_to_category

        # General status
        self.assertEqual(c2c(0x0000), 'Success')
        self.assertEqual(c2c(0xFF00), 'Pending')
        self.assertEqual(c2c(0xFF01), 'Pending')
        self.assertEqual(c2c(0xFE00), 'Cancel')

        assert c2c(0x0107) == 'Warning'

    def test_code_to_category_negative_raises(self):
        """Test code_to_category raises exception if negative."""
        assert pytest.raises(ValueError, code_to_category, -0x0001)

    def test_code_to_category_storage(self):
        """Test converting storage service class status code to its category"""
        # Storage Service Class specific PS3.4 Annex B
        c2c = code_to_category

        for code in range(0xA700, 0xA800):
            self.assertEqual(c2c(code), 'Failure')
        for code in range(0xA900, 0xAA00):
            self.assertEqual(c2c(code), 'Failure')
        for code in range(0xC000, 0xD000):
            self.assertEqual(c2c(code), 'Failure')
        for code in [0xB000, 0xB007, 0xB006]:
            self.assertEqual(c2c(code), 'Warning')
        self.assertEqual(c2c(0x0000), 'Success')

    def test_code_to_category_qr_find(self):
        """Test converting Q/R find service class status code to its category"""
        # Query/Retrieve Service Class specific - Find, PS3.4 Annex C.4.1
        c2c = code_to_category

        self.assertEqual(c2c(0xA700), 'Failure')
        self.assertEqual(c2c(0xA900), 'Failure')
        for code in range(0xC000, 0xD000):
            self.assertEqual(c2c(code), 'Failure')
        self.assertEqual(c2c(0xFE00), 'Cancel')
        for code in [0xFF00, 0xFF01]:
            self.assertEqual(c2c(code), 'Pending')
        self.assertEqual(c2c(0x0000), 'Success')

    def test_code_to_category_qr_move(self):
        """Test converting Q/R move service class status code to its category"""
        # Query/Retrieve Service Class specific - Move, PS3.4 Annex C.4.2
        c2c = code_to_category

        for code in [0xA701, 0xA702, 0xA801, 0xA900]:
            self.assertEqual(c2c(code), 'Failure')
        for code in range(0xC000, 0xD000):
            self.assertEqual(c2c(code), 'Failure')
        self.assertEqual(c2c(0xFE00), 'Cancel')
        self.assertEqual(c2c(0xB000), 'Warning')
        for code in [0xFF00]:
            self.assertEqual(c2c(code), 'Pending')
        self.assertEqual(c2c(0x0000), 'Success')

    def test_code_to_category_qr_get(self):
        """Test converting Q/R get service class status code to its category"""
        # Query/Retrieve Service Class specific - Get, PS3.4 Annex C.4.3
        c2c = code_to_category

        for code in [0xA701, 0xA702, 0xA900]:
            self.assertEqual(c2c(code), 'Failure')
        for code in range(0xC000, 0xD000):
            self.assertEqual(c2c(code), 'Failure')
        self.assertEqual(c2c(0xFE00), 'Cancel')
        self.assertEqual(c2c(0xB000), 'Warning')
        for code in [0xFF00]:
            self.assertEqual(c2c(code), 'Pending')
        self.assertEqual(c2c(0x0000), 'Success')

    def test_code_to_category_proc_step(self):
        """Test converting procedure step status code to its category"""
        # Procedure Step, PS3.4 Annex F
        c2c = code_to_category

        self.assertEqual(c2c(0x0110), 'Failure')
        self.assertEqual(c2c(0x0001), 'Warning')

    def test_code_to_category_print_management(self):
        """Test converting print management status code to its category"""
        # Procedure Step, PS3.4 Annex H
        c2c = code_to_category

        self.assertEqual(c2c(0x0000), 'Success')
        for code in [0xB600, 0xB601, 0xB602, 0xB603, 0xB604, 0xB605, 0xB609,
                     0xB60A]:
            self.assertEqual(c2c(code), 'Warning')
        for code in [0xC600, 0xC601, 0xC602, 0xC603, 0xC605, 0xC613, 0xC616]:
            self.assertEqual(c2c(code), 'Failure')

    def test_code_to_category_basic_worklist(self):
        """Test converting basic worklist status code to its category"""
        # Basic Worklist Management, PS3.4 Annex K
        c2c = code_to_category

        self.assertEqual(c2c(0x0000), 'Success')
        for code in [0xA700, 0xA900]:
            self.assertEqual(c2c(code), 'Failure')
        for code in range(0xC000, 0xD000):
            self.assertEqual(c2c(code), 'Failure')
        self.assertEqual(c2c(0xFE00), 'Cancel')
        self.assertEqual(c2c(0xB000), 'Warning')
        for code in [0xFF00, 0xFF01]:
            self.assertEqual(c2c(code), 'Pending')

    def test_code_to_category_application_event(self):
        """Test converting application event status code to its category"""
        # Application Event Logging, PS3.4 Annex P
        c2c = code_to_category

        self.assertEqual(c2c(0x0000), 'Success')
        for code in [0xC101, 0xC102, 0xC103, 0xC104, 0xC10E, 0xC110, 0xC111]:
            self.assertEqual(c2c(code), 'Failure')
        for code in [0xB101, 0xB102, 0xB104]:
            self.assertEqual(c2c(code), 'Warning')

    def test_code_to_category_relevant_patient(self):
        """Test converting relevant patient status code to its category"""
        # Relevant Patient Information Query, PS3.4 Annex Q
        c2c = code_to_category

        self.assertEqual(c2c(0x0000), 'Success')
        for code in [0xA700, 0xA900, 0xC000, 0xC100, 0xC200]:
            self.assertEqual(c2c(code), 'Failure')
        self.assertEqual(c2c(0xFE00), 'Cancel')
        self.assertEqual(c2c(0xB000), 'Warning')
        for code in [0xFF00]:
            self.assertEqual(c2c(code), 'Pending')

    def test_code_to_category_media_creation(self):
        """Test converting media creation status code to its category"""
        # Media Creation Management, PS3.4 Annex S
        c2c = code_to_category

        for code in [0xA510, 0xC201, 0xC202, 0xC203]:
            self.assertEqual(c2c(code), 'Failure')
        self.assertEqual(c2c(0x0001), 'Warning')

    def test_code_to_category_substance_admin(self):
        """Test converting substance admin status code to its category"""
        # Substance Administration Query, PS3.4 Annex V
        c2c = code_to_category

        self.assertEqual(c2c(0x0000), 'Success')
        for code in [0xA700, 0xA900]:
            self.assertEqual(c2c(code), 'Failure')
        for code in range(0xC000, 0xD000):
            self.assertEqual(c2c(code), 'Failure')
        self.assertEqual(c2c(0xFE00), 'Cancel')
        self.assertEqual(c2c(0xB000), 'Warning')
        for code in [0xFF00, 0xFF01]:
            self.assertEqual(c2c(code), 'Pending')

    def test_code_to_category_instance_frame(self):
        """Test converting instance and frame status code to its category"""
        # Instance and Frame Level Retrieve, PS3.4 Annex Y
        c2c = code_to_category

        self.assertEqual(c2c(0x0000), 'Success')
        for code in [0xA701, 0xA702, 0xA801, 0xA900, 0xAA00, 0xAA01, 0xAA02,
                     0xAA03, 0xAA04]:
            self.assertEqual(c2c(code), 'Failure')
        for code in range(0xC000, 0xD000):
            self.assertEqual(c2c(code), 'Failure')
        self.assertEqual(c2c(0xFE00), 'Cancel')
        self.assertEqual(c2c(0xB000), 'Warning')
        for code in [0xFF00]:
            self.assertEqual(c2c(code), 'Pending')

    def test_code_to_category_composite_instance(self):
        """Test converting composite instance status code to its category"""
        # Composite Instance Retrieve, PS3.4 Annex Z
        c2c = code_to_category

        self.assertEqual(c2c(0x0000), 'Success')
        for code in [0xA701, 0xA702, 0xA900]:
            self.assertEqual(c2c(code), 'Failure')
        for code in range(0xC000, 0xD000):
            self.assertEqual(c2c(code), 'Failure')
        self.assertEqual(c2c(0xFE00), 'Cancel')
        self.assertEqual(c2c(0xB000), 'Warning')
        for code in [0xFF00]:
            self.assertEqual(c2c(code), 'Pending')

    def test_code_to_category_unified_procedure(self):
        """Test converting unified procedure status code to its category"""
        # Unified Procedure Step, PS3.4 Annex CC
        c2c = code_to_category

        self.assertEqual(c2c(0x0000), 'Success')
        for code in [0x0001, 0xB300, 0xB301, 0xB304, 0xB305, 0xB306]:
            self.assertEqual(c2c(code), 'Warning')
        for code in [0xC300, 0xC301, 0xC302, 0xC304, 0xC307, 0xC310, 0xC311,
                     0xC313, 0xC312, 0xC308, 0xC314, 0xC315, 0xC309, 0xA700,
                     0xA900, 0x0122]:
            self.assertEqual(c2c(code), 'Failure')
        for code in range(0xC000, 0xD000):
            self.assertEqual(c2c(code), 'Failure')
        self.assertEqual(c2c(0xFE00), 'Cancel')
        for code in [0xFF00, 0xFF01]:
            self.assertEqual(c2c(code), 'Pending')

    def test_code_to_category_rt_machine(self):
        """Test converting RT machine status code to its category"""
        # RT Machine Verification, PS3.4 Annex DD
        c2c = code_to_category

        self.assertEqual(c2c(0x0000), 'Success')
        for code in [0xC227, 0xC221, 0xC222, 0xC223, 0xC224, 0xC225, 0xC226,
                     0xC112]:
            self.assertEqual(c2c(code), 'Failure')

    def test_code_to_category_non_patient(self):
        """Test converting non-patient object status code to its category"""
        # Non-patient Object Storage, PS3.4 Annex GG
        c2c = code_to_category

        self.assertEqual(c2c(0x0000), 'Success')
        for code in [0xA700, 0xA900, 0xC000]:
            self.assertEqual(c2c(code), 'Failure')


if __name__ == "__main__":
    unittest.main()
