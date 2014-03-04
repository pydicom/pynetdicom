#
# Copyright (c) 2012 Patrice Munger
# This file is part of pynetdicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pynetdicom.googlecode.com
#

# Timer class
import time
import logging

logger = logging.getLogger('netdicom.DUL')


class Timer:

    def __init__(self, MaxNbSeconds):
        self.__MaxNbSeconds = MaxNbSeconds
        self.__StartTime = None

    def Start(self):
        logger.debug("Timer started")
        self.__StartTime = time.time()

    def Stop(self):
        logger.debug("Timer stopped")
        self.__StartTime = None

    def Restart(self):
        if self.__StartTime is not None:
            self.Stop()
            self.Start()
        else:
            self.Start()

    def Check(self):
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
