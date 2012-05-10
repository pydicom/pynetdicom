"""
Query/Retrieve SCU AE example.

This demonstrates a simple application entity that support the Patient
Root Find and Move SOP Classes as SCU. In order to receive retrieved
datasets, this application entity must support the CT Image Storage
SOP Class as SCP as well. For this example to work, there must be an
SCP listening on the specified host and port.

For help on usage, 
python qrscu.py -h 
"""

import argparse
from netdicom.applicationentity import AE
from netdicom.SOPclass import *
from dicom.dataset import Dataset, FileDataset
from dicom.UID import ExplicitVRLittleEndian, ImplicitVRLittleEndian, ExplicitVRBigEndian
import netdicom
#netdicom.debug(True)
import tempfile

# parse commandline
parser = argparse.ArgumentParser(description='storage SCU example')
parser.add_argument('remotehost')
parser.add_argument('remoteport', type=int)
parser.add_argument('searchstring')
parser.add_argument('-p', help='local server port', type=int, default=9999)
parser.add_argument('-aet', help='calling AE title', default='PYNETDICOM')
parser.add_argument('-aec', help='called AE title', default='REMOTESCU')
parser.add_argument('-implicit', action='store_true', help='negociate implicit transfer syntax only', default=False)
parser.add_argument('-explicit', action='store_true', help='negociate explicit transfer syntax only', default=False)

args = parser.parse_args()

if args.implicit:
    ts = [ImplicitVRLittleEndian]
elif args.explicit:
    ts = [ExplicitVRLittleEndian]
else:
    ts = [
        ExplicitVRLittleEndian, 
        ImplicitVRLittleEndian, 
        ExplicitVRBigEndian
        ]

# call back
def OnAssociateResponse(association):
    print "Association response received"


def OnAssociateRequest(association):
    print "Association resquested"
    return True

def OnReceiveStore(SOPClass, DS):
    print "Received C-STORE", DS.PatientName
    try:
        # do something with dataset. For instance, store it.
        file_meta = Dataset()
        file_meta.MediaStorageSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
        file_meta.MediaStorageSOPInstanceUID = "1.2.3"  # !! Need valid UID here
        file_meta.ImplementationClassUID = "1.2.3.4"  # !!! Need valid UIDs here
        filename = '%s/%s.dcm' % (tempfile.gettempdir(), DS.SOPInstanceUID)
        ds = FileDataset(filename, {}, file_meta=file_meta, preamble="\0" * 128)
        ds.update(DS)
        #ds.is_little_endian = True
        #ds.is_implicit_VR = True
        ds.save_as(filename)
        print "File %s written" % filename
    except:
        pass
    # must return appropriate status
    return SOPClass.Success


# create application entity
MyAE = AE(args.aet, args.p, [PatientRootFindSOPClass,
                             PatientRootMoveSOPClass,
                             VerificationSOPClass], [StorageSOPClass], ts)
MyAE.OnAssociateResponse = OnAssociateResponse
MyAE.OnAssociateRequest = OnAssociateRequest
MyAE.OnReceiveStore = OnReceiveStore
MyAE.start()


# remote application entity
RemoteAE = dict(Address=args.remotehost, Port=args.remoteport, AET=args.aec)

# create association with remote AE
print "Request association"
assoc = MyAE.RequestAssociation(RemoteAE)


# perform a DICOM ECHO
print "DICOM Echo ... ",
st = assoc.VerificationSOPClass.SCU(1)
print 'done with status "%s"' % st

print "DICOM FindSCU ... ",
d = Dataset()
d.PatientsName = args.searchstring
d.QueryRetrieveLevel = "PATIENT"
d.PatientID = "*"
st = assoc.PatientRootFindSOPClass.SCU(d, 1)
print 'done with status "%s"' % st

for ss in st:
    if not ss[1]: continue
    #print ss[1]
    try:
        d.PatientID = ss[1].PatientID
    except:
        continue
    print "Moving"
    print d
    assoc2 = MyAE.RequestAssociation(RemoteAE)
    gen = assoc2.PatientRootMoveSOPClass.SCU(d, 'PYNETDICOM', 1)
    for gg in gen:
        print
        print gg
    assoc2.Release(0)
    print "QWEQWE"

print "Release association"
assoc.Release(0)

# done
MyAE.Quit()
