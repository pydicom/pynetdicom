#
# Copyright (c) 2012 Patrice Munger
# This file is part of pynetdicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pynetdicom.googlecode.com
#

# Timer class
import time

class Timer:
    def __init__(self, MaxNbSeconds):
        self.__MaxNbSeconds = MaxNbSeconds
        self.__StartTime = None

    def Start(self):
        self.__StartTime = time.time()
        
    def Stop(self):
        self.__StartTime = None

    def Restart(self):
        if self.__StartTime != None:
            self.Stop()
            self.Start()
        else:
            self.Start()

    def Check(self):
        if self.__StartTime:
            if time.time() - self.__StartTime > self.__MaxNbSeconds:
                print "Timer expired"
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




