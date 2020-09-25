"""Unit tests for the Timer class."""

import logging

import pytest

from pynetdicom.timer import Timer
from .utils import sleep

LOGGER = logging.getLogger('pynetdicom')
LOGGER.setLevel(logging.CRITICAL)


class TestTimer(object):
    """Test the Timer class."""
    def test_init(self):
        """Test Timer initialisation"""
        timer = Timer(10)
        assert timer.timeout == 10
        timer = Timer(0)
        assert timer.timeout == 0
        timer = Timer(None)
        assert timer.timeout is None

    def test_property_setters_getters(self):
        """Test Timer property setters and getters."""
        timer = Timer(0)
        assert timer.timeout == 0
        assert not timer.expired
        assert timer.remaining == 0

        timer = Timer(None)
        assert timer.timeout is None
        assert not timer.expired
        assert timer.remaining == 1

        timer.timeout = 10
        assert timer.timeout == 10
        assert not timer.expired
        assert timer.remaining == 10

        timer.timeout = 0.2
        timer.start()
        sleep(0.1)
        assert timer.remaining < 0.1
        assert not timer.expired
        sleep(0.1)
        assert timer.expired

        timer.timeout = None
        assert timer.timeout is None

    def test_start_stop(self):
        """Test Timer stops."""
        timer = Timer(0.2)
        timer.start()
        sleep(0.1)
        timer.stop()
        sleep(0.2)
        assert not timer.expired

    def test_restart(self):
        """Test Timer restarts correctly."""
        timer = Timer(0.2)
        timer.start()
        # sleep() may be longer than the called amount - whoof
        timeout = 0
        while timeout < 0.1:
            sleep(0.001)
            timeout += 0.001
        assert timer.expired is False
        timer.restart()
        timeout = 0
        while timeout < 0.15:
            sleep(0.001)
            timeout += 0.001
        assert timer.expired is False
        sleep(0.1)
        assert timer.expired is True

    def test_no_timeout(self):
        """Test the timer with no time out."""
        timer = Timer(None)
        assert timer.timeout is None
        assert timer.expired is False
        assert timer.remaining == 1
        timer.start()
        assert timer.expired is False
        assert timer.remaining == 1
        sleep(0.5)
        assert timer.expired is False
        assert timer.remaining == 1
        timer.stop()
        assert timer.expired is False
        assert timer.remaining == 1

    def test_timeout(self):
        """Test the timer with a time out."""
        timer = Timer(0.1)
        assert timer.timeout == 0.1
        assert timer.expired is False
        assert timer.remaining == 0.1
        timer.start()
        assert timer.expired is False
        assert timer.remaining > 0
        sleep(0.2)
        assert timer.expired is True
        assert timer.remaining < 0
        timer.stop()
        assert timer.expired is True
        assert timer.remaining < 0

    def test_timeout_stop(self):
        """Test stopping the timer."""
        timer = Timer(0.1)
        assert timer.timeout == 0.1
        assert timer.expired is False
        assert timer.remaining == 0.1
        timer.start()
        timer.stop()
        assert timer.timeout == 0.1
        assert timer.expired is False
        assert timer.remaining > 0
        timer.start()
        sleep(0.2)
        timer.stop()
        assert timer.timeout == 0.1
        assert timer.expired is True
        assert timer.remaining < 0
