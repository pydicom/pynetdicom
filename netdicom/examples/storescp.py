"""
Storage SCP example.

This demonstrates a simple application entity that support a number of
Storage service classes. For this example to work, you need an SCU
sending to this host on specified port.

For help on usage,
python storescp.py -h
"""

import argparse
from netdicom import AE, StorageSOPClass, VerificationSOPClass, logger_setup, \
    debug
from dicom.dataset import Dataset, FileDataset
import tempfile

# parse commandline
parser = argparse.ArgumentParser(description='storage SCP example')
parser.add_argument('port', type=int)
parser.add_argument('-aet', help='AE title of this server',
                    default='PYNETDICOM')
args = parser.parse_args()

#logger_setup()
#debug(True)


# callbacks
def OnAssociateRequest(association):
    print "association requested"


def OnAssociateResponse(association):
    print "Association response received"


def OnReceiveEcho(self):
    print "Echo received"


def OnReceiveStore(SOPClass, DS):
    #print "Received C-STORE"
    # do something with dataset. For instance, store it on disk.
    file_meta = Dataset()
    file_meta.MediaStorageSOPClassUID = DS.SOPClassUID
    file_meta.MediaStorageSOPInstanceUID = "1.2.3"  # !! Need valid UID here
    file_meta.ImplementationClassUID = "1.2.3.4"  # !!! Need valid UIDs here
    filename = '%s/%s.dcm' % (tempfile.gettempdir(), DS.SOPInstanceUID)
    ds = FileDataset(filename, {}, file_meta=file_meta, preamble="\0" * 128)
    ds.update(DS)
    ds.is_little_endian = True
    ds.is_implicit_VR = True
    ds.save_as(filename)
    #print "File %s written" % filename
    # must return appropriate status
    return SOPClass.Success


# setup AE
MyAE = AE(args.aet, args.port, [], [StorageSOPClass, VerificationSOPClass])
MyAE.OnAssociateRequest = OnAssociateRequest
MyAE.OnAssociateResponse = OnAssociateResponse
MyAE.OnReceiveStore = OnReceiveStore
MyAE.OnReceiveEcho = OnReceiveEcho

# start AE
print "starting AE ... ",
MyAE.start()
print "done"
MyAE.QuitOnKeyboardInterrupt()
