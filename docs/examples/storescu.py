"""
Storage SCU example.

This demonstrates a simple application entity that support the RT Plan
Storage SOP Class as SCU. For this example to work, there must be an
SCP listening on the specified host and port. 
"""

import sys
from netdicom.applicationentity import AE
from netdicom.SOPclass import *
import dicom

# parse commandline
remote_host = sys.argv[1]
remote_port = int(sys.argv[2])
files = sys.argv[3:]


# call back
def OnAssociateResponse(association):
    print "Association response received"


# create application entity
MyAE = AE('localhost', 9999, [StorageSOPClass,  VerificationSOPClass], [])
MyAE.OnAssociateResponse = OnAssociateResponse

# remote application entity
RemoteAE = dict(Address=remote_host, Port=remote_port, AET='REMOTE_AE')

# create association with remote AE
print "Request association"
assoc = MyAE.RequestAssociation(RemoteAE)

# perform a DICOM ECHO, just to make sure remote AE is listening
print "DICOM Echo ... ",
st = assoc.VerificationSOPClass.SCU(1)
print 'done with status "%s"' % st

# create some dataset
for ii in files:
    print 
    print ii
    d = dicom.read_file(ii)
    print "DICOM StoreSCU ... ",
    try:
        st = assoc.SCU(d, 1)
        print 'done with status "%s"' % st
    except:
        print "problem", d.SOPClassUID
print "Release association"
assoc.Release(0)

# done
MyAE.Quit()
