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
import netdicom


#netdicom.debug(True)

# parse commandline
port = int(sys.argv[1])


# callbacks
def OnAssociateRequest(association):
    print "association requested"
    print association

def OnAssociateResponse(association):
    print "Association response received"

def OnReceiveEcho(self):
    print "Echo received"
    return True
 
def OnReceiveStore(SOPClass, DS):
    print "Received C-STORE"
    # do something with dataset. For instance, store it.
    file_meta = Dataset()
    file_meta.MediaStorageSOPClassUID = '1.2.840.10008.5.1.4.1.1.2' # CT Image Storage
    file_meta.MediaStorageSOPInstanceUID = "1.2.3" # !! Need valid UID here for real work
    file_meta.ImplementationClassUID = "1.2.3.4" # !!! Need valid UIDs here
    filename = '/tmp/%s.dcm' % DS.SOPInstanceUID
    ds = FileDataset(filename, {}, file_meta=file_meta, preamble="\0"*128)
    ds.update(DS)
    ds.is_little_endian = True
    ds.is_implicit_VR = True
    ds.save_as(filename)
    print "File %s written" % filename
    # must return appropriate status
    return 0

# setup AE
MyAE = AE('MYAET', port, [],[MRImageStorageSOPClass,
                            CTImageStorageSOPClass,
                            RTImageStorageSOPClass,
                            RTPlanStorageSOPClass,
                            RTStructureSetStorageSOPClass, 
                            RTDoseStorageSOPClass, 
                            VerificationSOPClass])
MyAE.OnAssociateRequest = OnAssociateRequest
MyAE.OnAssociateResponse = OnAssociateResponse
MyAE.OnReceiveStore = OnReceiveStore
MyAE.OnReceiveEcho = OnReceiveEcho



# start AE
print "starting AE ...,"
MyAE.start()
print "done"
MyAE.QuitOnKeyboardInterrupt()




