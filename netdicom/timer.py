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
    timeouts
    
    Arguments
    ---------
    MaxNbSeconds - int, float
        The number of seconds before the connection time-outs
    """
    def __init__(self, MaxNbSeconds):
        self.__MaxNbSeconds = MaxNbSeconds
        self.__StartTime = None

    def start(self):
        """ Start the ARTIM timer """
        self.__StartTime = time.time()
        logger.debug("ARTIM timer started at %s")
        
    def stop(self):
        

    def Start(self):
        """ 
        Start the ARTIM timer
        
        .. note:: Deprecated in v1.0.0
            `Start` will be removed in version 1.5.0 and will be replaced by
            `start` as this conforms to PEP-8
        """
        self.start()
        
    

    def Stop(self):
        """ Stop the ARTIM timer """
        logger.debug("Timer stopped")
        self.__StartTime = None

    def Restart(self):
        """ Restart the ARTIM timer """
        if self.__StartTime is not None:
            self.Stop()
            self.Start()
        else:
            self.Start()

    def Check(self):
        """ Check if the ARTIM timer has expired 
        
        Returns
        -------
        bool 
            False if the timer has expired, True otherwise
        """
        
        if self.__StartTime:
            if time.time() - self.__StartTime > self.__MaxNbSeconds:
                logger.warning("Timer expired")
                return False
            else:
                return True
        else:
            return True


if __name__ == '__main__':

    t = Timer(3)

    t.Start()
    for ii in range(32):
        time.sleep(0.2)
        print t.Check()
