#
# Copyright (c) 2012 Patrice Munger
# This file is part of pynetdicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pynetdicom.googlecode.com
#

"""
EchoSCP AE example.

This demonstrates a simple application entity that support the Verification
SOP Class as SCP. For this example to work, you need a echoscu client to query
our server. With the offis toolkit, this can be achieved with the command:

echoscu -v  localhost 9999
"""

import sys
sys.path.append('..')
import time
import netdicom
import dcmtkscu

# call backs


def OnAssociateRequest(association):
    print "Association request received"


def OnReceiveEcho(self):
    print "Echo received"
    return True

# create application entity
MyAE = netdicom. AE('localhost', 9999, [], [netdicom.VerificationSOPClass])
MyAE.OnAssociateRequest = OnAssociateRequest
MyAE.OnReceiveEcho = OnReceiveEcho

dcmtkscu.run_in_term('echoscu -v localhost 9999')

# start application entity
MyAE.start()
MyAE.QuitOnKeyboardInterrupt()
