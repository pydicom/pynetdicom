"""
FindSCU AE example.

This demonstrates a simple application entity that support the Patient
Root Find SOP Class as SCU. For this example to work, there must be an
SCP listening on the specified host and port.
"""

import sys
from netdicom.applicationentity import AE
from netdicom.SOPclass import PatientRootFindSOPClass, VerificationSOPClass
import dicom
from dicom.dataset import Dataset


# parse commandline
remote_host = sys.argv[1]
remote_port = int(sys.argv[2])
files = sys.argv[3:]


# call back
def OnAssociateResponse(association):
    print "Association response received"

# create application entity
MyAE = AE('localhost', 9999, [PatientRootFindSOPClass, VerificationSOPClass],[])
MyAE.OnAssociateResponse = OnAssociateResponse

# remote application entity
RemoteAE = dict(Address=remote_host, Port=remote_port, AET='AE1')

# create association with remote AE
print "Request association"
assoc = MyAE.RequestAssociation(RemoteAE)

        
# perform a DICOM ECHO
print "DICOM Echo ... ",
st = assoc.VerificationSOPClass.SCU(1)
print 'done with status "%s"' % st

print "DICOM FindSCU ... ",
d = Dataset()
d.PatientsName = '*'
d.QueryRetrieveLevel = "PATIENT"
st = assoc.PatientRootFindSOPClass.SCU(d, 1)
print 'done with status "%s"' % st

print "Results"
for ss in st:
    print
    print ss

print "Release association"
assoc.Release(0)

# done
MyAE.Quit()




