"""
Storage SCP example.

This demonstrates a simple application entity that support a number of
Storage service classes. For this example to work, you need an SCU
sending to the specified host and port.
"""

import sys
from netdicom.applicationentity import AE
from netdicom.SOPclass import *
from dicom.dataset import Dataset, FileDataset
import tempfile

# parse commandline
port = int(sys.argv[1])


# callbacks
def OnAssociateRequest(association):
    print "association requested"

def OnAssociateResponse(association):
    print "Association response received"

def OnReceiveEcho(self):
    print "Echo received"
 
def OnReceiveStore(SOPClass, DS):
    print "Received C-STORE"
    # do something with dataset. For instance, store it on disk.
    file_meta = Dataset()
    file_meta.MediaStorageSOPClassUID = DS.SOPClassUID
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


# setup AE
MyAE = AE('MYAET', port, [],[StorageSOPClass, VerificationSOPClass])
MyAE.OnAssociateRequest = OnAssociateRequest
MyAE.OnAssociateResponse = OnAssociateResponse
MyAE.OnReceiveStore = OnReceiveStore
MyAE.OnReceiveEcho = OnReceiveEcho

# start AE
print "starting AE ...,"
MyAE.start()
print "done"
MyAE.QuitOnKeyboardInterrupt()




