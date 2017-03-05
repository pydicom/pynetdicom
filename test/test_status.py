#!/usr/bin/env python
"""Status testing"""

import logging
import unittest

from pynetdicom3.status import code_to_status

LOGGER = logging.getLogger('pynetdicom3')
LOGGER.setLevel(logging.CRITICAL)

class TestStatus(unittest.TestCase):
    """Test the Status"""
    def test_assigned(self):
        """Test fetching status works"""
        status = code_to_status(0x0123)
        print(status)
        print(status.description)
        print(status.category)
        print(status.text)


if __name__ == "__main__":
    unittest.main()
