"""
MoveSCU AE example.

This demonstrates a simple application entity that support the Patient Root
Move SOP Class as SCU. The example sets up a SCP provider listening
on port 2001 on localhost using the dcmqrscp command from the offis toolkit. 
"""

import sys
sys.path.append('..')
import time
from applicationentity import AE
from SOPclass import PatientRootMoveSOPClass, VerificationSOPClass
from dcmqrscp import start_dcmqrscp
from dicom.dataset import Dataset

# first create a partner
start_dcmqrscp(server_port=2001, server_AET='AE1', populate=True)
start_dcmqrscp(server_port=2002, server_AET='AE2', populate=True)
for ii in range(20): print

# call back
def OnAssociateResponse(association):
    print "Association response received"

# create application entity
MyAE = AE('LocalAE', 9998, [PatientRootMoveSOPClass, VerificationSOPClass],[])
MyAE.OnAssociateResponse = OnAssociateResponse

# remote application entity
RemoteAE = {'Address':'localhost','Port':2001,'AET':'AE1'}

# create association with remote AE
print "Request association"
assoc = MyAE.RequestAssociation(RemoteAE)

        
# perform a DICOM ECHO
print "DICOM Echo ... ",
st = assoc.VerificationSOPClass.SCU(1)
print 'done with status "%s"' % st

# send dataset using RTPlanStorageSOPClass
print "DICOM MoveSCU ... ",
d = Dataset()
d.PatientsName = '*'
d.QueryRetrieveLevel = "PATIENT"
st = assoc.PatientRootMoveSOPClass.SCU(d, 'AE2', 1)
print 'done with status "%s"' % st

print "Results"
for ss in st:
    print
    print ss

print "Release association"
assoc.Release(0)

# done
MyAE.Quit()




