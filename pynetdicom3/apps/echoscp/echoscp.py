#!/usr/bin/env python

"""
    An echoscp application.

    Used for verifying basic DICOM connectivity and as such has a focus on
    providing useful debugging and logging information.
"""

import argparse
import logging
import os
import socket
import sys

from pydicom.uid import ExplicitVRLittleEndian, ImplicitVRLittleEndian, \
                        ExplicitVRBigEndian

from pynetdicom3 import AE, VerificationSOPClass

logger = logging.Logger('echoscp')
stream_logger = logging.StreamHandler()
formatter = logging.Formatter('%(levelname).1s: %(message)s')
stream_logger.setFormatter(formatter)
logger.addHandler(stream_logger)
logger.setLevel(logging.ERROR)

VERSION = '0.2.1'

def _setup_argparser():
    """Setup the command line arguments"""
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
    net_opts.add_argument("-to", "--timeout", metavar='[s]econds',
                          help="timeout for connection requests",
                          type=int,
                          default=0)
    net_opts.add_argument("-ta", "--acse-timeout", metavar='[s]econds',
                          help="timeout for ACSE messages",
                          type=int,
                          default=30)
    net_opts.add_argument("-td", "--dimse-timeout", metavar='[s]econds',
                          help="timeout for DIMSE messages",
                          type=int,
                          default=0)
    net_opts.add_argument("-pdu", "--max-pdu", metavar='[n]umber of bytes',
                          help="set max receive pdu to n bytes (4096..131072)",
                          type=int,
                          default=16382)

    # Transfer Syntaxes
    ts_opts = parser.add_argument_group('Preferred Transfer Syntaxes')
    ts_opts.add_argument("-x=", "--prefer-uncompr",
                         help="prefer explicit VR local byte order (default)",
                         action="store_true", default=True)
    ts_opts.add_argument("-xe", "--prefer-little",
                         help="prefer explicit VR little endian TS",
                         action="store_true")
    ts_opts.add_argument("-xb", "--prefer-big",
                         help="prefer explicit VR big endian TS",
                         action="store_true")
    ts_opts.add_argument("-xi", "--implicit",
                         help="accept implicit VR little endian TS only",
                         action="store_true")

    # Association Options
    assoc_opts = parser.add_argument_group('Association Options')
    #assoc_opts.add_argument("--refuse",
    #                        help="refuse all associations",
    #                        action="store_true")
    #assoc_opts.add_argument("--abort-after",
    #                        help="abort association after receiving a "
    #                            "C-ECHO-RQ (but before sending response)",
    #                        action="store_true")
    #assoc_opts.add_argument("--abort-during",
    #                        help="abort association during receipt of a "
    #                            "C-ECHO-RQ",
    #                        action="store_true")

    return parser.parse_args()

args = _setup_argparser()

# Logging/Output
if args.quiet:
    for h in logger.handlers:
        logger.removeHandler(h)

    logger.addHandler(logging.NullHandler())

    pynetdicom_logger = logging.getLogger('pynetdicom3')
    for h in pynetdicom_logger.handlers:
        pynetdicom_logger.removeHandler(h)

    pynetdicom_logger.addHandler(logging.NullHandler())

if args.verbose:
    logger.setLevel(logging.INFO)
    pynetdicom_logger = logging.getLogger('pynetdicom3')
    pynetdicom_logger.setLevel(logging.INFO)

if args.debug:
    logger.setLevel(logging.DEBUG)
    pynetdicom_logger = logging.getLogger('pynetdicom3')
    pynetdicom_logger.setLevel(logging.DEBUG)

if args.log_level:
    levels = {'critical' : logging.CRITICAL,
              'error'    : logging.ERROR,
              'warn'     : logging.WARNING,
              'info'     : logging.INFO,
              'debug'    : logging.DEBUG}
    logger.setLevel(levels[args.log_level])
    pynetdicom_logger = logging.getLogger('pynetdicom3')
    pynetdicom_logger.setLevel(levels[args.log_level])

if args.log_config:
    fileConfig(args.log_config)

logger.debug('echoscp.py v{0!s} {1!s}'.format(VERSION, '2017-02-04'))
logger.debug('')

# Validate port
if isinstance(args.port, int):
    test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        test_socket.bind((os.popen('hostname').read()[:-1], args.port))
    except socket.error:
        logger.error("Cannot listen on port {}, insufficient privileges or "
            "already in use".format(args.port))
        sys.exit()

# Set Transfer Syntax options
transfer_syntax = [ImplicitVRLittleEndian,
                   ExplicitVRLittleEndian,
                   ExplicitVRBigEndian]

if args.prefer_uncompr and ImplicitVRLittleEndian in transfer_syntax:
    transfer_syntax.remove(ImplicitVRLittleEndian)
    transfer_syntax.append(ImplicitVRLittleEndian)

if args.implicit:
    transfer_syntax = [ImplicitVRLittleEndian]

if args.prefer_little and ExplicitVRLittleEndian in transfer_syntax:
    transfer_syntax.remove(ExplicitVRLittleEndian)
    transfer_syntax.insert(0, ExplicitVRLittleEndian)

if args.prefer_big and ExplicitVRBigEndian in transfer_syntax:
    transfer_syntax.remove(ExplicitVRBigEndian)
    transfer_syntax.insert(0, ExplicitVRBigEndian)

# Create application entity
ae = AE(ae_title=args.aetitle,
        port=args.port,
        scu_sop_class=[],
        scp_sop_class=[VerificationSOPClass],
        transfer_syntax=transfer_syntax)

ae.maximum_pdu_size = args.max_pdu

# Set timeouts
ae.network_timeout = args.timeout
ae.acse_timeout = args.acse_timeout
ae.dimse_timeout = args.dimse_timeout

ae.start()
