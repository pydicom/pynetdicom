"""
Query/Retrieve SCU AE example.

This demonstrates a simple application entity that support the Patient
Root Find and Move SOP Classes as SCU. In order to receive retrived
datasets, this application entity must support the CT Image Storage
SOP Class as SCP as well. For this example to work, there must be an
SCP listening on the specified host and port.
"""

import sys
from netdicom.applicationentity import AE
from netdicom.SOPclass import *
import dicom
from dicom.dataset import Dataset, FileDataset
import tempfile

# parse commandline
remote_host = sys.argv[1]
remote_port = int(sys.argv[2])
files = sys.argv[3:]


# call back
def OnAssociateResponse(association):
    print "Association response received"

def OnAssociateRequest(association):
    print "Association resquested"

def OnReceiveStore(SOPClass, DS):
    print "Received C-STORE"
    # do something with dataset. For instance, store it.
    file_meta = Dataset()
    file_meta.MediaStorageSOPClassUID = '1.2.840.10008.5.1.4.1.1.2' # CT Image Storage
    file_meta.MediaStorageSOPInstanceUID = "1.2.3" # !! Need valid UID here for real work
    file_meta.ImplementationClassUID = "1.2.3.4" # !!! Need valid UIDs here
    filename = '%s/%s.dcm' % (tempfile.gettempdir(),DS.SOPInstanceUID)
    ds = FileDataset(filename, {}, file_meta=file_meta, preamble="\0"*128)
    ds.update(DS)
    ds.is_little_endian = True
    ds.is_implicit_VR = True
    ds.save_as(filename)
    print "File %s written" % filename
    # must return appropriate status
    return SOPClass.Success



# create application entity
MyAE = AE('AE2', 9999, [PatientRootFindSOPClass, 
                              PatientRootMoveSOPClass, 
                              VerificationSOPClass],[StorageSOPClass])
MyAE.OnAssociateResponse = OnAssociateResponse
MyAE.OnAssociateRequest = OnAssociateRequest
MyAE.OnReceiveStore = OnReceiveStore
MyAE.start()


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


print "DICOM MoveSCU ... ",
print "Request association"
assoc = MyAE.RequestAssociation(RemoteAE)
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




