#!../../../venv/bin/python

"""
    A dcmtk style echoscu application. 
    
    Used for verifying basic DICOM connectivity and as such has a focus on
    providing useful debugging and logging information.
"""

import argparse
import os
import socket
import sys

from pynetdicom.applicationentity import AE
from pynetdicom.SOPclass import VerificationSOPClass
from pydicom.uid import ExplicitVRLittleEndian

# Temporary until I get better debug logging included
if True:
    print("D: $pynetdicom: echoscu v0.1.0 2016-02-21 $")
    print("D:")

# Description
parser = argparse.ArgumentParser(
    description="The echoscu application implements a Service Class User (SCU) "
                "for the Verification SOP Class. It sends a DICOM C-ECHO "
                "message to a Service Class Provider (SCP) and waits for a "
                "response. The application can be used to verify basic "
                "DICOM connectivity.", 
    usage="echoscu [options] peer port")
    
# Parameters
req_opts = parser.add_argument_group('Parameters')
req_opts.add_argument("peer", help="hostname of DICOM peer", type=str)
req_opts.add_argument("port", help="TCP/IP port number of peer", type=int)

# General Options
gen_opts = parser.add_argument_group('General Options')
gen_opts.add_argument("--version", 
                      help="print version information and exit", 
                      action="store_true")
gen_opts.add_argument("--arguments", 
                      help="print expanded command line arguments", 
                      action="store_true")
gen_opts.add_argument("-q", "--quiet", 
                      help="quiet mode, print no warnings and errors", 
                      action="store_true")
gen_opts.add_argument("-v", "--verbose", 
                      help="verbose mode, print processing details", 
                      action="store_true")
gen_opts.add_argument("-d", "--debug", 
                      help="debug mode, print debug information", 
                      action="store_true")
gen_opts.add_argument("-ll", "--log-level", metavar='[l]', 
                      help="use level l for the logger (fatal, error, warn, "
                           "info, debug, trace)", 
                      type=str, 
                      choices=['fatal', 'error', 'warn', 
                               'info', 'debug', 'trace'])
gen_opts.add_argument("-lc", "--log-config", metavar='[f]', 
                      help="use config file f for the logger", 
                      type=str)

# Network Options
net_opts = parser.add_argument_group('Network Options')
net_opts.add_argument("-aet", "--calling-aet", metavar='[a]etitle', 
                      help="set my calling AE title (default: ECHOSCU)", 
                      type=str, 
                      default='ECHOSCU')
net_opts.add_argument("-aec", "--called-aet", metavar='[a]etitle', 
                      help="set called AE title of peer (default: ANY-SCP)", 
                      type=str, 
                      default='ANY-SCP')
net_opts.add_argument("-pts", "--propose-ts", metavar='[n]umber', 
                      help="propose n transfer syntaxes (1..128)", 
                      type=int)
net_opts.add_argument("-ppc", "--propose-pc", metavar='[n]umber', 
                      help="propose n presentation contexts (1..128)", 
                      type=int)
net_opts.add_argument("-to", "--timeout", metavar='[s]econds', 
                      help="timeout for connection requests", 
                      type=int)
net_opts.add_argument("-ta", "--acse-timeout", metavar='[s]econds', 
                      help="timeout for ACSE messages", 
                      type=int,
                      default=30)
net_opts.add_argument("-td", "--dimse-timeout", metavar='[s]econds', 
                      help="timeout for DIMSE messages", 
                      type=int,
                      default=-1)
net_opts.add_argument("-pdu", "--max-pdu", metavar='[n]umber of bytes', 
                      help="set max receive pdu to n bytes (4096..131072)", 
                      type=int,
                      default=16384)
net_opts.add_argument("--repeat", metavar='[n]umber', 
                      help="repeat n times", 
                      type=int)
net_opts.add_argument("--abort", 
                      help="abort association instead of releasing it", 
                      action="store_true")

args = parser.parse_args()

calling_address = socket.gethostbyname(os.popen('hostname').read()[:-1])

# Binding to port 0 will let the OS pick an available port
calling_ae = {'ae_title' : args.called_aet, 
             'ip_address' : calling_address, 
             'port_number' : 0}
             
called_ae = {'AET' : args.called_aet, 
             'Address' : args.peer, 
             'Port' : args.port}

def OnAssociateRequest(association):
    #print "Association request received"
    pass

def OnAssociateResponse(answer):
    #print(answer)
    pass

def OnReceiveEcho(self):
    #print "Echo received"
    return True

# create application entity
print("ECHOSCU: Creating AE")
ae = AE(args.calling_aet, 11112, [], [VerificationSOPClass], 
        SupportedTransferSyntax=[ExplicitVRLittleEndian])
ae.OnAssociateRequest = OnAssociateRequest
ae.OnAssociateResponse = OnAssociateResponse
ae.OnReceiveEcho = OnReceiveEcho

# Request association with remote
print("ECHOSCU: Associating...")
assoc = ae.RequestAssociation(called_ae)

if assoc is not None:
    # Send echo
    print("ECHOSCU: Sending echo")
    status = assoc.VerificationSOPClass.SCU(1)

    # Release association
    print("ECHOSCU: Releasing")
    assoc.Release(0)
else:
    print("ECHOSCU: Failed to associate")

# Quit
ae.Quit()


