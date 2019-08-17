"""
A generic timer class suitable for use as the DICOM UL's ARTIM timer.
"""
import logging
import time


LOGGER = logging.getLogger('pynetdicom.artim')


class Timer(object):
    """A generic timer.

    Implementation of the DICOM Upper Layer's ARTIM timer. The ARTIM timer is
    used by the state machine to monitor connection and response timeouts.
    This class may also be used as a general purpose expiry timer.

    A :attr:`~Timer.timeout` of ``None`` implies that :attr:`~Timer.expired`
    always returns ``False`` and :attr:`~Timer.remaining` always returns ``1``.
    A :attr:`~Timer.timeout` of :class:`float` implies that:

    - If not yet started, :attr:`~Timer.expired` returns ``False`` and
      :attr:`~Timer.remaining` returns :attr:`~Timer.timeout`
    - If started then :attr:`~Timer.expired` returns ``False`` until the time
      since starting is greater than :attr:`~Timer.timeout` after which it
      returns ``True``. :attr:`~Timer.remaining` returns the number of seconds
      until :attr:`~Timer.expired` returns ``True`` (will return negative
      value after expiry)
    - If started then stopped before the timeout then :attr:`~Timer.expired`
      returns ``False``, if stopped after the time since starting is greater
      than :attr:`~Timer.timeout` then returns ``True``.
      :attr:`~Timer.remaining` always returns the number of seconds until
      :attr:`~Timer.expired` returns ``True``.

    References
    ----------

    * DICOM Standard, Part 8,
      :dcm:`Section 9.1.5<part08/chapter_9.html#sect_9.1.5>`.
    """
    def __init__(self, timeout):
        """Create a new :class:`Timer`.

        Parameters
        ---------
        timeout : numeric or None
            The number of seconds before the timer expires. A value of ``None``
            means the timer never expires.
        """
        self._start_time = None
        self._end_time = None
        self.timeout = timeout

    @property
    def expired(self):
        """Check if the timer has expired.

        Returns
        -------
        bool
            ``True`` if the timer has expired, ``False`` otherwise
        """
        # Timer never expires
        if self.timeout is None:
            return False

        # Timer hasn't started
        if self._start_time is None:
            return False

        # Timer has started
        if self.remaining < 0:
            return True

        return False

    @property
    def remaining(self):
        """Return the number of seconds remaining until timeout.

        Returns ``1`` if the timer is set to never expire.
        """
        # Timer never expires
        if self.timeout is None:
            return 1

        # Timer hasn't started
        if self._start_time is None:
            return self.timeout

        # Timer has started and hasn't been stopped
        if self._end_time is None:
            return self.timeout - (time.time() - self._start_time)

        # Time has been start and been stopped
        return self.timeout - (self._end_time - self._start_time)

    def restart(self):
        """Restart the timer."""
        self.start()

    def start(self):
        """Resets and starts the timer running."""
        self._start_time = time.time()
        self._end_time = None

    def stop(self):
        """Stops the timer and resets it."""
        self._end_time = time.time()

    @property
    def timeout(self):
        """Return the number of seconds set for :attr:`~Timer.timeout`."""
        return self._timeout

    @timeout.setter
    def timeout(self, value):
        """Set the number of seconds before the timer expires.

        Parameters
        ----------
        value : numeric or None
            The number of seconds before the timer expires. A value of ``None``
            means the timer never expires.
        """
        # pylint: disable=attribute-defined-outside-init
        self._timeout = value
