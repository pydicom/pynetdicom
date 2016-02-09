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

from pynetdicom.applicationentity import ApplicationEntity as AE
from pynetdicom.SOPclass import VerificationSOPClass
from pydicom.uid import ExplicitVRLittleEndian, ImplicitVRLittleEndian, \
    ExplicitVRBigEndian

logger = logging.Logger('')
stream_logger = logging.StreamHandler()
formatter = logging.Formatter('%(levelname).1s: %(message)s')
stream_logger.setFormatter(formatter)
logger.addHandler(stream_logger)
logger.setLevel(logging.ERROR)

def _setup_argparser():
    # Description
    parser = argparse.ArgumentParser(
        description="The echoscp application implements a Service Class "
                    "Provider (SCP) for the Verification SOP Class. It listens "
                    "for a DICOM C-ECHO message from a Service Class User "
                    "(SCU) and sends a response. The application can be used "
                    "to verify basic DICOM connectivity.", 
        usage="echoscp [options] port")
        
    # Parameters
    req_opts = parser.add_argument_group('Parameters')
    req_opts.add_argument("port", 
                          help="TCP/IP port number to listen on", 
                          type=int)

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
    net_opts.add_argument("-aet", "--aetitle", metavar='[a]etitle', 
                          help="set my AE title (default: ECHOSCP)", 
                          type=str, 
                          default='ECHOSCP')

    # Transfer Syntaxes
    ts_opts = parser.add_argument_group('Preferred Transfer Syntaxes')
    ts_opts.add_argument("-x=", "--prefer-uncompr",
                         help="prefer explicit VR local byte order (default)",
                         action="store_true")
    ts_opts.add_argument("-xe", "--prefer-little",
                         help="prefer explicit VR little endian TS",
                         action="store_true")
    ts_opts.add_argument("-xb", "--prefer-big",
                         help="prefer explicit VR big endian TS",
                         action="store_true")
    ts_opts.add_argument("-xi", "--implicit",
                         help="accept implicit VR little endian TS only",
                         action="store_true")
    
    return parser.parse_args()

args = _setup_argparser()

if args.verbose:
    logger.setLevel(logging.INFO)
    
if args.debug:
    logger.setLevel(logging.DEBUG)
    pynetdicom_logger = logging.getLogger('pynetdicom')
    pynetdicom_logger.setLevel(logging.DEBUG)

logger.debug('$echoscp.py v%s %s $' %('0.0.1', '2016-02-01'))
logger.debug('')

def OnAssociateRequest(association):
    logger.info("Association Received")

def OnAssociateResponse(answer):
    if answer:
        logger.info('Association Acknowledged (Max Send PDV: %s)' %'[FIXME]')
    else:
        logger.error('Association Request Failed: %s' %'[FIXME]')
        #logger.error('0006:0317 Peer aborted Association (or never connected)')
        #logger.error('0006:031c TCP Initialisation Error: Connection refused')
        
def OnAssociateRelease():
    pass

def OnReceiveEcho():
    logger.info('Received Echo Request')
    return True

# Validate port
if isinstance(args.port, int):
    test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        test_socket.bind((os.popen('hostname').read()[:-1], args.port))
    except socket.error:
        logger.error("Cannot listen on port %d, insufficient priveleges" 
            %args.port)
        sys.exit()

# Set Transfer Syntax options
transfer_syntax = [ImplicitVRLittleEndian, 
                   ExplicitVRLittleEndian,
                   ExplicitVRBigEndian]

if args.implicit:
    transfer_syntax = [ImplicitVRLittleEndian]
    
if args.prefer_little:
    if ExplicitVRLittleEndian in transfer_syntax:
        transfer_syntax.remove(ExplicitVRLittleEndian)
        transfer_syntax.insert(0, ExplicitVRLittleEndian)

if args.prefer_big:
    if ExplicitVRBigEndian in transfer_syntax:
        transfer_syntax.remove(ExplicitVRBigEndian)
        transfer_syntax.insert(0, ExplicitVRBigEndian)

# Create application entity
ae = AE(args.aetitle, args.port, [], [VerificationSOPClass], 
        SupportedTransferSyntax=transfer_syntax)
ae.OnAssociateRequest = OnAssociateRequest
ae.OnAssociateResponse = OnAssociateResponse
ae.OnReceiveEcho = OnReceiveEcho

ae.start()
ae.QuitOnKeyboardInterrupt()


