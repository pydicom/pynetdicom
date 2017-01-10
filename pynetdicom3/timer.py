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

    Parameters
    ---------
    max_number_seconds : int, float
        The number of seconds before the timer expires. A value of 0 means
        no timeout
    """
    def __init__(self, max_number_seconds):
        self._start_time = None

        if max_number_seconds == 0:
            max_number_seconds = None

        self._max_number_seconds = max_number_seconds

    def start(self):
        """Resets and starts the timer running."""
        self._start_time = time.time()
        #LOGGER.debug("Timer started at %s" %time.ctime(self._start_time))

    def stop(self):
        """Stops the timer and resets it."""
        self._start_time = None
        #LOGGER.debug("Timer stopped at %s" %time.ctime(time.time()))

    def restart(self):
        """Restart the timer.

        If the timer has already started then stop it, reset it and start it.
        If the timer isn't running then reset it and start it.
        """
        self.start()

    def is_expired(self):
        """Check if the timer has expired.

        Returns
        -------
        bool
            True if the timer has expired, False otherwise
        """
        if self._start_time is not None and \
                self._max_number_seconds is not None:
            if (time.time() - self._start_time) > self._max_number_seconds:
                #logger.debug("ARTIM timer has expired")
                return True

        return False

    def set_timeout(self, timeout_seconds):
        """Set the number of seconds before the timer expires.

        Parameters
        ----------
        timeout_seconds : float or int
            The number of seconds before the timer expires. A value of 0 means
            no timeout
        """
        if timeout_seconds == 0:
            timeout_seconds = None

        self._max_number_seconds = timeout_seconds
