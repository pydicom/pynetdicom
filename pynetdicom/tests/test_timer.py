"""Unit tests for the Timer class."""

import logging
import time

import pytest

from pynetdicom.timer import Timer

LOGGER = logging.getLogger('pynetdicom')
LOGGER.setLevel(logging.CRITICAL)


class TestTimer(object):
    """Test the Timer class."""
    def test_init(self):
        """Test Timer initialisation"""
        timer = Timer(10)
        assert timer.timeout_seconds == 10
        timer = Timer(0)
        assert timer.timeout_seconds == 0
        timer = Timer(None)
        assert timer.timeout_seconds is None

    def test_property_setters_getters(self):
        """Test Timer property setters and getters."""
        timer = Timer(0)
        assert timer.timeout_seconds == 0
        assert not timer.is_expired
        assert timer.time_remaining == 0

        timer = Timer(None)
        assert timer.timeout_seconds is None
        assert not timer.is_expired
        assert timer.time_remaining == -1

        timer.timeout_seconds = 10
        assert timer.timeout_seconds == 10
        assert not timer.is_expired
        assert timer.time_remaining == 10

        timer.timeout_seconds = 0.2
        timer.start()
        time.sleep(0.1)
        assert timer.time_remaining < 0.1
        assert not timer.is_expired
        time.sleep(0.1)
        assert timer.is_expired

        timer.timeout_seconds = None
        assert timer.timeout_seconds is None

    def test_start_stop(self):
        """Test Timer stops."""
        timer = Timer(0.2)
        timer.start()
        time.sleep(0.1)
        timer.stop()
        time.sleep(0.2)
        assert not timer.is_expired

    def test_restart(self):
        """Test Timer restarts correctly."""
        timer = Timer(0.2)
        timer.start()
        time.sleep(0.1)
        timer.restart()
        time.sleep(0.15)
        assert not timer.is_expired
        time.sleep(0.05)
        assert timer.is_expired
