#!/usr/bin/env python

"""
    A dcmtk style storescu application.

    Used as an SCU for sending DICOM objects from
"""

import argparse
import logging
import os
import socket
import sys

from pydicom import read_file
from pydicom.uid import ExplicitVRLittleEndian, ImplicitVRLittleEndian, \
    ExplicitVRBigEndian, DeflatedExplicitVRLittleEndian

from pynetdicom3 import AE
from pynetdicom3 import StorageSOPClassList

logger = logging.Logger('storescu')
stream_logger = logging.StreamHandler()
formatter = logging.Formatter('%(levelname).1s: %(message)s')
stream_logger.setFormatter(formatter)
logger.addHandler(stream_logger)
logger.setLevel(logging.ERROR)

VERSION = '0.1.1'

def _setup_argparser():
    """Setup the command line arguments"""
    # Description
    parser = argparse.ArgumentParser(
        description="The storescu application implements a Service Class User "
                    "(SCU) for the Storage Service Class. For each DICOM "
                    "file on the command line it sends a C-STORE message to a  "
                    "Storage Service Class Provider (SCP) and waits for a "
                    "response. The application can be used to transmit DICOM "
                    "images and other composite objectes.",
        usage="storescu [options] peer port dcmfile-in")

    # Parameters
    req_opts = parser.add_argument_group('Parameters')
    req_opts.add_argument("peer", help="hostname of DICOM peer", type=str)
    req_opts.add_argument("port", help="TCP/IP port number of peer", type=int)
    req_opts.add_argument("dcmfile_in",
                          metavar="dcmfile-in",
                          help="DICOM file or directory to be transmitted",
                          type=str)

    # General Options
    gen_opts = parser.add_argument_group('General Options')
    gen_opts.add_argument("--version",
                          help="print version information and exit",
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
                          help="set my calling AE title (default: STORESCU)",
                          type=str,
                          default='STORESCU')
    net_opts.add_argument("-aec", "--called-aet", metavar='[a]etitle',
                          help="set called AE title of peer (default: ANY-SCP)",
                          type=str,
                          default='ANY-SCP')

    # Transfer Syntaxes
    ts_opts = parser.add_mutually_exclusive_group()
    ts_opts.add_argument("-xe", "--request-little",
                         help="request explicit VR little endian TS only",
                         action="store_true")
    ts_opts.add_argument("-xb", "--request-big",
                         help="request explicit VR big endian TS only",
                         action="store_true")
    ts_opts.add_argument("-xi", "--request-implicit",
                         help="request implicit VR little endian TS only",
                         action="store_true")

    return parser.parse_args()

args = _setup_argparser()

if args.verbose:
    logger.setLevel(logging.INFO)
    pynetdicom_logger = logging.getLogger('pynetdicom3')
    pynetdicom_logger.setLevel(logging.INFO)

if args.debug:
    logger.setLevel(logging.DEBUG)
    pynetdicom_logger = logging.getLogger('pynetdicom3')
    pynetdicom_logger.setLevel(logging.DEBUG)

if args.version:
    print('storescu.py v{0!s} {1!s} $'.format(VERSION, '2017-02-04'))
    sys.exit()

logger.debug('storescu.py v{0!s} {1!s}'.format(VERSION, '2017-02-04'))
logger.debug('')

# Check file exists and is readable and DICOM
logger.debug('Checking input files')
try:
    f = open(args.dcmfile_in, 'rb')
    dataset = read_file(f, force=True)
    f.close()
except IOError:
    logger.error('Cannot read input file {0!s}'.format(args.dcmfile_in))
    sys.exit()

# Set Transfer Syntax options
transfer_syntax = [ExplicitVRLittleEndian,
                   ImplicitVRLittleEndian,
                   DeflatedExplicitVRLittleEndian,
                   ExplicitVRBigEndian]

if args.request_little:
    transfer_syntax = [ExplicitVRLittleEndian]
elif args.request_big:
    transfer_syntax = [ExplicitVRBigEndian]
elif args.request_implicit:
    transfer_syntax = [ImplicitVRLittleEndian]

# Bind to port 0, OS will pick an available port
ae = AE(ae_title=args.calling_aet,
        port=0,
        scu_sop_class=StorageSOPClassList,
        scp_sop_class=[],
        transfer_syntax=transfer_syntax)

# Request association with remote
assoc = ae.associate(args.peer, args.port, args.called_aet)

if assoc.is_established:
    logger.info('Sending file: {0!s}'.format(args.dcmfile_in))

    status = assoc.send_c_store(dataset)

    assoc.release()
