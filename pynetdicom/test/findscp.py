#
# Copyright (c) 2012 Patrice Munger
# This file is part of pynetdicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pynetdicom.googlecode.com
#

"""
FindSCP AE example.

This demonstrates a simple application entity that support the Patient
Root Find SOP Class as SCP. For this example to work, you need a findscu client
to query our server. With the offis toolkit, this can be achieved with the
command:

findscu -v -P -aec AE1 -k 0010,0010="*" -k 0008,0052="PATIENT" localhost 9999
"""

import sys
sys.path.append('..')
import time
from applicationentity import AE
from SOPclass import PatientRootFindSOPClass, VerificationSOPClass
import dicom
from dicom.dataset import Dataset
import dcmtkscu

# call backs


def OnAssociateRequest(association):
    print "Association request received"


def OnReceiveEcho(self):
    print
    print "Echo received"
    return True


def OnReceiveFind(self, ds):
    for ii in range(1000):
        ds.PatientsName = 'titi' + str(ii)
        print "sending fake response: patient name: %s" % ds.PatientsName
        yield ds, 0xFF00
    # responding to find request


# create application entity
MyAE = AE('localhost', 9999, [],
          [PatientRootFindSOPClass, VerificationSOPClass])
MyAE.OnAssociateRequest = OnAssociateRequest
MyAE.OnReceiveEcho = OnReceiveEcho
MyAE.OnReceiveFind = OnReceiveFind


dcmtkscu.run_in_term(
    'findscu -v -P -aec AE1 -k 0010,0010="*" -k 0008,0052="PATIENT"'
    ' localhost 9999')

# start application entity
MyAE.start()
MyAE.QuitOnKeyboardInterrupt()
