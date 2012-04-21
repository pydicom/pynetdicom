#
# Copyright (c) 2012 Patrice Munger
# This file is part of pynetdicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pynetdicom.googlecode.com
#

"""
Client AE example.

This demonstrates a simple application entity that support the RT Plan
Storage SOP Class as SCU. For this example to work, you need to setup
a SCP provider listening on port 8888 on localhost. With the offis
dicom toolkit for instance, this can be done with the command:

storescp -v 8888
"""

import sys
import os
sys.path.append('..')
import time
from applicationentity import AE
from SOPclass import *
import dicom
import dcmqrscp
from utils import testfiles_dir

# start peer
dcmqrscp.start_dcmqrscp()

# call back
def OnAssociateResponse(association):
    print "Association response received"

# create application entity
MyAE = AE('localhost', 9999, [RTPlanStorageSOPClass, VerificationSOPClass],[])
MyAE.OnAssociateResponse = OnAssociateResponse

# remote application entity
RemoteAE = {'Address':'localhost','Port':2000,'AET':'OFFIS_AE'}

# create some dataset
d = dicom.read_file(os.path.join(testfiles_dir(),"rtplan.dcm"))

# create association with remote AE
print "Request association"
assoc = MyAE.RequestAssociation(RemoteAE)

        
# perform a DICOM ECHO
#time.sleep(2)
print "DICOM Echo ... ",
st = assoc.VerificationSOPClass.SCU(1)
print 'done with status "%s"' % st


# send dataset using RTPlanStorageSOPClass
#time.sleep(2)
print "DICOM StoreSCP ... ",
st = assoc.RTPlanStorageSOPClass.SCU(d, 1)
print 'done with status "%s"' % st

print "Release association"
assoc.Release(0)

# done
MyAE.Quit()




