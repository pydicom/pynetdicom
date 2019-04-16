#!/usr/bin/env python

"""
    A getscp application.
"""

import argparse
import logging
from logging.config import fileConfig
import os
import socket
import sys
import time

from pydicom import dcmread
from pydicom.dataset import Dataset
from pydicom.uid import (
    ExplicitVRLittleEndian, ImplicitVRLittleEndian, ExplicitVRBigEndian
)

from pynetdicom import (
    AE, evt,
    QueryRetrievePresentationContexts,
    StoragePresentationContexts
)


VERSION = '0.4.1'


def _setup_argparser():
    """Setup the command line arguments"""
    # Description
    parser = argparse.ArgumentParser(
        description="The getscp application implements a Service Class "
                    "Provider (SCP) for the Query/Retrieve (QR) Service Class "
                    "and the Basic Worklist Management (BWM) Service Class. "
                    "getscp only supports query functionality using the C-GET "
                    "message. It receives query keys from an SCU and sends a "
                    "response. The application can be used to test SCUs of the "
                    "QR and BWM Service Classes.",
        usage="getscp [options] port")

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
                          help="set my AE title (default: GETSCP)",
                          type=str,
                          default='GETSCP')
    net_opts.add_argument("-to", "--timeout", metavar='[s]econds',
                          help="timeout for connection requests",
                          type=int,
                          default=None)
    net_opts.add_argument("-ta", "--acse-timeout", metavar='[s]econds',
                          help="timeout for ACSE messages",
                          type=int,
                          default=60)
    net_opts.add_argument("-td", "--dimse-timeout", metavar='[s]econds',
                          help="timeout for DIMSE messages",
                          type=int,
                          default=None)
    net_opts.add_argument("-pdu", "--max-pdu", metavar='[n]umber of bytes',
                          help="set max receive pdu to n bytes",
                          type=int,
                          default=16384)

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

# Logging/Output
def setup_logger():
    """Setup the echoscu logging"""
    logger = logging.Logger('getscp')
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(levelname).1s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.ERROR)

    return logger

APP_LOGGER = setup_logger()

def _setup_logging(level):
    APP_LOGGER.setLevel(level)
    pynetdicom_logger = logging.getLogger('pynetdicom')
    handler = logging.StreamHandler()
    pynetdicom_logger.setLevel(level)
    formatter = logging.Formatter('%(levelname).1s: %(message)s')
    handler.setFormatter(formatter)
    pynetdicom_logger.addHandler(handler)

if args.quiet:
    for hh in APP_LOGGER.handlers:
        APP_LOGGER.removeHandler(hh)

    APP_LOGGER.addHandler(logging.NullHandler())

if args.verbose:
    _setup_logging(logging.INFO)

if args.debug:
    _setup_logging(logging.DEBUG)

if args.log_level:
    levels = {'critical' : logging.CRITICAL,
              'error'    : logging.ERROR,
              'warn'     : logging.WARNING,
              'info'     : logging.INFO,
              'debug'    : logging.DEBUG}
    _setup_logging(levels[args.log_level])

if args.log_config:
    fileConfig(args.log_config)

APP_LOGGER.debug('$getscp.py v{0!s}'.format(VERSION))
APP_LOGGER.debug('')

# Validate port
if isinstance(args.port, int):
    test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        test_socket.bind((os.popen('hostname').read()[:-1], args.port))
        test_socket.close()
    except socket.error:
        APP_LOGGER.error("Cannot listen on port {0:d}, insufficient priveleges".format(args.port))
        sys.exit()

# Set Transfer Syntax options
transfer_syntax = [ImplicitVRLittleEndian,
                   ExplicitVRLittleEndian,
                   ExplicitVRBigEndian]

if args.implicit:
    transfer_syntax = [ImplicitVRLittleEndian]

if args.prefer_little and ExplicitVRLittleEndian in transfer_syntax:
        transfer_syntax.remove(ExplicitVRLittleEndian)
        transfer_syntax.insert(0, ExplicitVRLittleEndian)

if args.prefer_big and ExplicitVRBigEndian in transfer_syntax:
        transfer_syntax.remove(ExplicitVRBigEndian)
        transfer_syntax.insert(0, ExplicitVRBigEndian)

def handle_get(event):
    """Implement the evt.EVT_C_GET handler"""
    try:
        APP_DIR = os.path.join(os.path.dirname(__file__))
        DATA_DIR = os.path.join(APP_DIR, '../', '../', 'tests', 'dicom_files')
        dcm_files = ['RTImageStorage.dcm', 'CTImageStorage.dcm']
        dcm_files = [os.path.join(DATA_DIR, x) for x in dcm_files]
        yield len(dcm_files)
    except:
        dcm_files = []
        yield 0

    for dcm in dcm_files:
        ds = dcmread(dcm, force=True)
        yield 0xFF00, ds

handlers = [(evt.EVT_C_GET, handle_get)]

# Create application entity
ae = AE(ae_title=args.aetitle)

for context in StoragePresentationContexts:
    ae.add_supported_context(
        context.abstract_syntax, transfer_syntax, scp_role=True, scu_role=False
    )
for context in QueryRetrievePresentationContexts:
    ae.add_supported_context(context.abstract_syntax, transfer_syntax)

ae.maximum_pdu_size = args.max_pdu

# Set timeouts
ae.network_timeout = args.timeout
ae.acse_timeout = args.acse_timeout
ae.dimse_timeout = args.dimse_timeout

ae.start_server(('', args.port), evt_handlers=handlers)
