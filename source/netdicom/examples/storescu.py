"""
Storage SCU example.

This demonstrates a simple application entity that support the RT Plan
Storage SOP Class as SCU. For this example to work, there must be an
SCP listening on the specified host and port.

For help on usage, 
python storescu.py -h 
"""

import argparse
from netdicom import AE, StorageSOPClass, VerificationSOPClass
from dicom.UID import ExplicitVRLittleEndian, ImplicitVRLittleEndian, ExplicitVRBigEndian
from dicom import read_file


# parse commandline
parser = argparse.ArgumentParser(description='storage SCU example')
parser.add_argument('remotehost')
parser.add_argument('remoteport', type=int)
parser.add_argument('file', nargs='+' )
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

# create application entity
MyAE = AE(args.aet, 9999, [StorageSOPClass,  VerificationSOPClass], [], ts)
MyAE.OnAssociateResponse = OnAssociateResponse

# remote application entity
RemoteAE = dict(Address=args.remotehost, Port=args.remoteport, AET=args.aec)

# create association with remote AE
print "Request association"
assoc = MyAE.RequestAssociation(RemoteAE)

# perform a DICOM ECHO, just to make sure remote AE is listening
print "DICOM Echo ... ",
st = assoc.VerificationSOPClass.SCU(1)
print 'done with status "%s"' % st

# create some dataset
for ii in args.file:
    print
    print ii
    d = read_file(ii)
    print "DICOM StoreSCU ... ",
    try:
        st = assoc.SCU(d, 1)
        print 'done with status "%s"' % st
    except:
        raise
        print "problem", d.SOPClassUID
print "Release association"
assoc.Release(0)

# done
MyAE.Quit()
