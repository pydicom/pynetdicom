"""
A generic timer class suitable for use as the DICOM UL's ARTIM timer.
"""
import logging
import time

LOGGER = logging.getLogger('pynetdicom3.artim')


class Timer(object):
    """A generic timer.

    Implementation of the DICOM Upper Layer's ARTIM timer as per PS3.8 Section
    9.1.5. The ARTIM timer is used by the state machine to monitor connection
    and response timeouts. This class may also be used as a general purpose
    expiry timer.
    """
    def __init__(self, max_number_seconds):
        """Create a new Timer.

        Parameters
        ---------
        max_number_seconds : int or float or None
            The number of seconds before the timer expires. A value of None
            means no timeout.
        """
        self._start_time = None
        self.timeout_seconds = max_number_seconds

    def start(self):
        """Resets and starts the timer running."""
        self._start_time = time.time()

    def stop(self):
        """Stops the timer and resets it."""
        self._start_time = None

    def restart(self):
        """Restart the timer.

        If the timer has already started then stop it, reset it and start it.
        If the timer isn't running then reset it and start it.
        """
        self.start()

    @property
    def is_expired(self):
        """Check if the timer has expired.

        Returns
        -------
        bool
            True if the timer has expired, False otherwise
        """
        if self._start_time is not None and self.timeout_seconds is not None:
            if self.time_remaining < 0:
                return True

        return False

    @property
    def timeout_seconds(self):
        """Return the number of seconds set for timeout."""
        return self._max_number_seconds

    @timeout_seconds.setter
    def timeout_seconds(self, value):
        """Set the number of seconds before the timer expires.

        Parameters
        ----------
        value : float or int or None
            The number of seconds before the timer expires. A value of None
            means no timeout.
        """
        self._max_number_seconds = value

    @property
    def time_remaining(self):
        """Return the number of seconds remaining until timeout.

        Returns -1 if the timer is set to unlimited timeout.
        """
        if self._start_time is None:
            if self.timeout_seconds is None:
                return -1

            return self.timeout_seconds

        seconds_elapsed = time.time() - self._start_time
        return self.timeout_seconds - seconds_elapsed
