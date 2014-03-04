#
# Copyright (c) 2012 Patrice Munger
# This file is part of pynetdicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pynetdicom.googlecode.com
#

#!/usr/bin/python

import numpy
import sys
sys.path.append('../..')
import time
import stat
import os
import traceback
from dicom.dataset import Dataset, FileDataset
import time
from netdicom.applicationentity import AE
from netdicom.SOPclass import *
from netdicom.examples.dcmqrscp import start_dcmqrscp

REMOTEAE = {'Address': 'localhost', 'Port': 2000, 'AET': 'OFFIS_AE'}


def OnAssociateRequest(association):
    print "Association requested"
    print association


def OnAssociateResponse(association):
    print "Association response received"
    print association


def OnReceiveStore(SOPclass, DS):
    assoc = MyAE.RequestAssociation(REMOTEAE)
    if assoc:
        assoc.CRImageStorageSOPClass.StoreSCU(DS, 1)
        assoc.Release(0)
        return 0
    else:
        return 1


def OnReceiveEcho(self):
    print "Echo received"


if __name__ == '__main__':
    start_dcmqrscp()

    MyAE = AE('NETDICOM', 7654, [CRImageStorageSOPClass],
              [CRImageStorageSOPClass, VerificationSOPClass])
    MyAE.OnAssociateRequest = OnAssociateRequest
    MyAE.OnAssociateResponse = OnAssociateResponse
    MyAE.OnReceiveStore = OnReceiveStore
    MyAE.OnReceiveEcho = OnReceiveEcho

    MyAE.start()
