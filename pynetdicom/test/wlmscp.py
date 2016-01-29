"""
Worklist Manager SCP example.

This demonstrates a simple application entity that support a number of
Query service classes. For this example to work, you need an SCU
sending to this host on specified port.

usage: python wlmscp.py
"""

import sys
import datetime
import netdicom
import dcmtkscu

# callbacks


def OnAssociateRequest(association):
    print "association requested", association


def OnReceiveEcho(self):
    print "Echo received"


def OnReceiveFind(self, ds):
    print "Received C-FIND"
    for ii in range(5):
        ds.PatientsName = 'titi' + str(ii)
        print "sending fake response: patient name: %s" % ds.PatientsName
        print ds
        print
        yield ds, 0xFF00
    # responding to find request

# setup AE
print 'Create AE...'
MyAE = netdicom.AE('localhost', 9999,
                   SOPSCU=[],
                   SOPSCP=[netdicom.VerificationSOPClass,
                           netdicom.ModalityWorklistInformationFindSOPClass]
                   )
MyAE.OnAssociateRequest = OnAssociateRequest
MyAE.OnReceiveEcho = OnReceiveEcho
MyAE.OnReceiveFind = OnReceiveFind

# Start modality simulator
dcmtkscu.run_in_term(
    'findscu -v -W -aec AE1 -k 0010,0020="*" -k 0010,0040="*" -k 0010,0030="*" '
    '-k 0008,0052="PATIENT" -k 0008,0060="MR"  -k 0040,0001="*" '
    'localhost 9999')

# start AE
print "starting AE ... "
MyAE.start()
print "Entering processing loop..."
MyAE.QuitOnKeyboardInterrupt()
