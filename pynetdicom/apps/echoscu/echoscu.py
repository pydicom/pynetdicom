#!../../../venv/bin/python

"""
    A dcmtk style echoscu application. 
    
    Used for verifying basic DICOM connectivity and as such has a focus on
    providing useful debugging and logging information.
"""

import argparse
import logging
import os
import socket
import sys

from pynetdicom.applicationentity import AE
from pynetdicom.SOPclass import VerificationSOPClass
from pydicom.uid import ExplicitVRLittleEndian

logger = logging.Logger('echoscu')
stream_logger = logging.StreamHandler()
formatter = logging.Formatter('%(levelname).1s: %(message)s')
stream_logger.setFormatter(formatter)
logger.addHandler(stream_logger)
logger.setLevel(logging.ERROR)

def _setup_argparser():
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

    return parser.parse_args()

args = _setup_argparser()

if args.verbose:
    logger.setLevel(logging.INFO)
    
if args.debug:
    logger.setLevel(logging.DEBUG)
    pynetdicom_logger = logging.getLogger('pynetdicom')
    pynetdicom_logger.setLevel(logging.DEBUG)

logger.debug('$echoscu.py v%s %s $' %('0.1.0', '2016-02-01'))
logger.debug('')

called_ae = {'AET' : args.called_aet, 
             'Address' : args.peer, 
             'Port' : args.port}

def OnAssociateRequest(association):
    pass

def OnAssociateResponse(answer):
    if answer:
        logger.info('Association Accepted (Max Send PDV: %s)' %'[FIXME]')
    else:
        logger.error('Association Request Failed: %s' %'[FIXME]')
        #logger.error('0006:0317 Peer aborted Association (or never connected)')
        #logger.error('0006:031c TCP Initialisation Error: Connection refused')

def OnReceiveEcho():
    logger.info('Received Echo Response (Status: %s)' %'Success')
    return True

# Create application entity
# Bind to port 0, OS will pick an available port
ae = AE(args.calling_aet, 0, [], [VerificationSOPClass], 
        SupportedTransferSyntax=[ExplicitVRLittleEndian])
ae.OnAssociateRequest = OnAssociateRequest
ae.OnAssociateResponse = OnAssociateResponse
ae.OnReceiveEcho = OnReceiveEcho

# Request association with remote
#logger.info('Requesting Association')
assoc = ae.RequestAssociation(called_ae)

if assoc is not None:
    logger.info('Sending Echo Request: MsgID %s' %'[FIXME]')
    status = assoc.VerificationSOPClass.SCU(1)
    
    if status:
        logger.info('Received Echo Response (Status: %s)' %'Success')

    # Release association
    logger.info('Releasing Association')
    assoc.Release(0)

# Quit
ae.Quit()


