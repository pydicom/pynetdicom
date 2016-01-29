#
# Copyright (c) 2012 Patrice Munger
# This file is part of pynetdicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pynetdicom.googlecode.com
#

"""
FindSCP AE example.

This demonstrates a simple application entity that support the Patient
Root Move SOP Class as SCP. For this example to work, you need a findscu client
to query our server. With the offis toolkit, this can be achieved with the
command:

movescu -v -P -aem AE1 -k 0010,0010="*" -k 0008,0052="PATIENT" localhost 9999
"""

import sys
sys.path.append('..')
import os
import time
from applicationentity import AE
from SOPclass import PatientRootMoveSOPClass, VerificationSOPClass, \
    RTPlanStorageSOPClass
import dicom
from dcmqrscp import start_dcmqrscp
import dcmtkscu
from utils import testfiles_dir

# first create a partner
start_dcmqrscp(server_port=2001, server_AET='AE1')
for ii in range(20):
    print


# call backs
def OnAssociateRequest(association):
    print "Association request received"


def OnReceiveEcho(self):
    print
    print "Echo received"
    return True


def OnReceiveMove(self, ident, remoteAE):
    # ds is the identifyer dataset
    # pretend that we lookup the database to find a list of datasets to be
    # moved
    yield dict(AET=remoteAE, Port=2001, Address='localhost')

    nop = 10
    yield nop

    for ii in range(nop):
        # create fake dataset
        ds = dicom.read_file(os.path.join(testfiles_dir(), "rtplan.dcm"))
        print "sending fake dataset"
        yield ds


# create application entity
MyAE = AE('localhost', 9999, [RTPlanStorageSOPClass],
          [PatientRootMoveSOPClass, VerificationSOPClass])
MyAE.OnAssociateRequest = OnAssociateRequest
MyAE.OnReceiveEcho = OnReceiveEcho
MyAE.OnReceiveMove = OnReceiveMove


dcmtkscu.run_in_term(
    'movescu -v -P -aem AE1 -k 0010,0010="*" -k 0008,0052="PATIENT" '
    'localhost 9999')

# start application entity
MyAE.start()
MyAE.QuitOnKeyboardInterrupt()
