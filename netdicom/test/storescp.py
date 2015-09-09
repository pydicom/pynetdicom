#
# Copyright (c) 2012 Patrice Munger
# This file is part of pynetdicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pynetdicom.googlecode.com
#

"""
Server AE example.

This demonstrates a simple application entity that support a number of
Storage service classes. For this example to work, you need to setup a
Storage SCU sending to port 9999 on localhost. With the offis dicom
toolkit, this can be done with the command:

storescu -v localhost 9999 FILE.dcm
"""

import sys
import os
sys.path.append('../..')
import netdicom
import time
from netdicom.applicationentity import AE
from netdicom.SOPclass import *
from dicom.dataset import Dataset, FileDataset
import dcmtkscu
from utils import testfiles_dir

netdicom.debug(False)

# callbacks


def OnAssociateRequest(association):
    print "association requested"
    print association


def OnAssociateResponse(association):
    print "Association response received"


def OnReceiveEcho(self):
    print
    print "Echo received"
    return True


def OnReceiveStore(SOPClass, DS):
    print "Received C-STORE"
    # do something with dataset. For instance, store it.
    file_meta = Dataset()
    # CT Image Storage
    file_meta.MediaStorageSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
    # !! Need valid UID here for real work
    file_meta.MediaStorageSOPInstanceUID = "1.2.3"
    file_meta.ImplementationClassUID = "1.2.3.4"  # !!! Need valid UIDs here
    filename = '/tmp/%s.dcm' % DS.SOPInstanceUID
    ds = FileDataset(filename, {}, file_meta=file_meta, preamble="\0" * 128)
    ds.update(DS)
    ds.is_little_endian = True
    ds.is_implicit_VR = True
    ds.save_as(filename)
    print "File %s written" % filename
    # must return appropriate status
    return 0

# setup AE
MyAE = AE('SPIN', 9999, [], [MRImageStorageSOPClass,
                             CTImageStorageSOPClass,
                             RTImageStorageSOPClass,
                             RTPlanStorageSOPClass,
                             VerificationSOPClass])
MyAE.OnAssociateRequest = OnAssociateRequest
MyAE.OnAssociateResponse = OnAssociateResponse
MyAE.OnReceiveStore = OnReceiveStore
MyAE.OnReceiveEcho = OnReceiveEcho


dcmtkscu.run_in_term('storescu -d localhost 9999 ' +
                     os.path.join(testfiles_dir(), 'rtplan.dcm'))

# start AE
print "starting AE ...,"
MyAE.start()
print "done"
MyAE.QuitOnKeyboardInterrupt()
