#
# Copyright (c) 2012 Patrice Munger
# This file is part of pynetdicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pynetdicom.googlecode.com


import logging
import time


logger = logging.getLogger('netdicom.DUL')


class Timer:
    """
    Implementation of the DICOM Upper Layer's ARTIM timer as per PS3.8 Section
    9.1.5. The ARTIM timer is used by the state machine to monitor connection
    and response timeouts. This class may also be used as a general purpose
    expiry timer.
    
    Parameters
    ---------
    max_number_seconds - int, float
        The number of seconds before the timer expires
    """
    def __init__(self, max_number_seconds):
        self._start_time = None
        self._max_number_seconds = max_number_seconds

    def start(self):
        """ Resets and starts the timer running """
        self._start_time = time.time()
        logger.debug("Timer started at %s" %time.ctime(self._start_time))

    def stop(self):
        """ Stops the timer and resets it """
        logger.debug("Timer stopped at %s" %time.ctime(time.time()))
        self._start_time = None

    def restart(self):
        """ Restart the timer
        
        If the timer has already started then stop it, reset it and start it.
        If the timer isn't running then reset it and start it.
        """
        self.start()

    def is_expired(self):
        """ Check if the timer has expired

        Returns
        -------
        bool 
            True if the timer has expired, False otherwise
        """
        if self._start_time is not None:
            if (time.time() - self._start_time) > self._max_number_seconds:
                logger.debug("Timer has expired")
                return True

        return False

    def set_timeout(self, timeout_seconds):
        """ Set the number of seconds before the timer expires
        
        Parameters
        ----------
        timeout_seconds - float, int
            The number of seconds before the timer expires
        """
        self._max_number_seconds = timeout_seconds


    def Start(self):
        """ 
        Start the ARTIM timer
        
        .. note:: Deprecated in v0.8.1
            `Start` will be removed in version 1.0.0 and will be replaced by
            `start`
        """
        raise DeprecationWarning("Timer::Start() is deprecated and will be "
            "removed in v1.0.0. Replace it with Timer::start()")
        self.start()

    def Stop(self):
        """ Stop the ARTIM timer 
        
        .. note:: Deprecated in v0.8.1
            `Stop` will be removed in version 1.0.0 and will be replaced by
            `stop`
        """
        raise DeprecationWarning("Timer::Stop() is deprecated and will be "
            "removed in v1.0.0. Replace it with Timer::stop()")
        self.stop()

    def Restart(self):
        """ Restart the ARTIM timer 
        
        .. note:: Deprecated in v0.8.1
            `Restart` will be removed in version 1.0.0 and will be replaced by
            `restart`
        """
        raise DeprecationWarning("Timer::Restart() is deprecated and will be "
            "removed in v1.0.0. Replace it with Timer::Restart()")
        self.restart()

    def Check(self):
        """ Check if the ARTIM timer has expired 
        
        .. note:: Deprecated in v0.8.1
            `Check` will be removed in version 1.0.0 and will be replaced by
            `is_expired`, however the return values will be reversed
        
        Returns
        -------
        bool 
            False if the timer has expired, True otherwise
        """
        raise DeprecationWarning("Timer::Check() is deprecated and will be "
            "removed in v1.0.0. Replace it with 'not Timer::is_expired()' as "
            "the return value has been reversed")
        return not self.is_expired()
