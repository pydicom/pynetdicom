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
    and response timeouts.
    
    Parameters
    ---------
    max_number_seconds - int, float
        The number of seconds before the ARTIM timer expires
    """
    def __init__(self, max_number_seconds):
        self.__start_time = None
        self.__max_number_seconds = max_number_seconds

    def start(self):
        """ Start the ARTIM timer """
        self.__start_time = time.time()
        logger.debug("ARTIM timer started at %s" %time.ctime(self.__start_time))
        
    def stop(self):
        """ Stop the ARTIM timer """
        logger.debug("ARTIM timer stopped at %s" %time.ctime(time.time()))
        self.__start_time = None
        
    def restart(self):
        """ Restart the ARTIM timer """
        if self.__start_time is not None:
            self.stop()

        self.start()
            
    def is_expired(self):
        """ Check if the ARTIM timer has expired 
        
        Returns
        -------
        bool 
            True if the timer is expired, False otherwise
        """
        if self.__start_time:
            if (time.time() - self.__start_time) > self.__max_number_seconds:
                logger.warning("ARTIM timer has expired")
                return True
        
        return False
        
    def set_timeout(self, timeout_seconds):
        """ Set the number of seconds before the ARTIM timer expires
        
        Parameters
        ----------
        timeout_seconds - float, int
            The number of seconds before the timer expires
        """
        self.__max_number_seconds = timeout_seconds

    def Start(self):
        """ 
        Start the ARTIM timer
        
        .. note:: Deprecated in v1.0.0
            `Start` will be removed in version 1.5.0 and will be replaced by
            `start`
        """
        self.start()

    def Stop(self):
        """ Stop the ARTIM timer 
        
        .. note:: Deprecated in v1.0.0
            `Stop` will be removed in version 1.5.0 and will be replaced by
            `stop`
        """
        self.stop()

    def Restart(self):
        """ Restart the ARTIM timer 
        
        .. note:: Deprecated in v1.0.0
            `Restart` will be removed in version 1.5.0 and will be replaced by
            `restart`
        """
        self.restart()

    def Check(self):
        """ Check if the ARTIM timer has expired 
        
        .. note:: Deprecated in v1.0.0
            `Check` will be removed in version 1.5.0 and will be replaced by
            `is_expired`, however the return values will be reversed
        
        Returns
        -------
        bool 
            False if the timer has expired, True otherwise
        """
        return not self.is_expired()

"""
if __name__ == '__main__':

    t = Timer(3)

    t.Start()
    for ii in range(32):
        time.sleep(0.2)
        print t.Check()
"""
