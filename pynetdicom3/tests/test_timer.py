"""Unit tests for the Timer class."""

import logging
import time
import unittest

from pynetdicom3.timer import Timer

LOGGER = logging.getLogger('pynetdicom3')
LOGGER.setLevel(logging.CRITICAL)


class TestTimer(unittest.TestCase):
    """Test the Timer class."""
    def test_init(self):
        """Test Timer initialisation"""
        timer = Timer(10)
        self.assertTrue(timer.timeout_seconds == 10)
        timer = Timer(0)
        self.assertTrue(timer.timeout_seconds == 0)
        timer = Timer(None)
        self.assertTrue(timer.timeout_seconds is None)

    def test_property_setters_getters(self):
        """Test Timer property setters and getters."""
        timer = Timer(0)
        self.assertEqual(timer.timeout_seconds, 0)
        self.assertFalse(timer.is_expired)
        self.assertEqual(timer.time_remaining, 0)

        timer = Timer(None)
        self.assertEqual(timer.timeout_seconds, None)
        self.assertFalse(timer.is_expired)
        self.assertEqual(timer.time_remaining, -1)

        timer.timeout_seconds = 10
        self.assertEqual(timer.timeout_seconds, 10)
        self.assertFalse(timer.is_expired)
        self.assertEqual(timer.time_remaining, 10)

        timer.timeout_seconds = 0.2
        timer.start()
        time.sleep(0.1)
        self.assertTrue(timer.time_remaining < 0.1)
        self.assertFalse(timer.is_expired)
        time.sleep(0.1)
        self.assertTrue(timer.is_expired)

        timer.timeout_seconds = None
        self.assertEqual(timer.timeout_seconds, None)

    def test_start_stop(self):
        """Test Timer stops."""
        timer = Timer(0.2)
        timer.start()
        time.sleep(0.1)
        timer.stop()
        time.sleep(0.2)
        self.assertFalse(timer.is_expired)

    def test_restart(self):
        """Test Timer restarts correctly."""
        timer = Timer(0.2)
        timer.start()
        time.sleep(0.1)
        timer.restart()
        time.sleep(0.15)
        self.assertFalse(timer.is_expired)
        time.sleep(0.05)
        self.assertTrue(timer.is_expired)


if __name__ == "__main__":
    unittest.main()
