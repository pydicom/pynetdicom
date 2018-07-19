#!/usr/bin/env python

"""
An echoscu application.

Used for verifying basic DICOM connectivity and as such has a focus on
providing useful debugging and logging information.
"""

import argparse
import logging
from logging.config import fileConfig
import sys

from pydicom.uid import (
    ExplicitVRLittleEndian, ImplicitVRLittleEndian, ExplicitVRBigEndian
)

from pynetdicom3 import AE
from pynetdicom3.sop_class import VerificationSOPClass


def setup_logger():
    """Setup the logging"""
    logger = logging.Logger('echoscu')
    stream_logger = logging.StreamHandler()
    formatter = logging.Formatter('%(levelname).1s: %(message)s')
    stream_logger.setFormatter(formatter)
    logger.addHandler(stream_logger)
    logger.setLevel(logging.ERROR)

    return logger


LOGGER = setup_logger()

VERSION = '0.6.1'


def _setup_argparser():
    """Setup the command line arguments"""
    # Description
    parser = argparse.ArgumentParser(
        description="The echoscu application implements a Service Class User "
                    "(SCU) for the Verification SOP Class. It sends a DICOM "
                    "C-ECHO message to a Service Class Provider (SCP) and "
                    "waits for a response. The application can be used to "
                    "verify basic DICOM connectivity.",
        usage="echoscu [options] peer port"
    )

    # Parameters
    req_opts = parser.add_argument_group('Parameters')
    req_opts.add_argument("peer", help="hostname of DICOM peer", type=str)
    req_opts.add_argument("port", help="TCP/IP port number of peer", type=int)

    # General Options
    gen_opts = parser.add_argument_group('General Options')
    gen_opts.add_argument("--version",
                          help="print version information and exit",
                          action="store_true")
    output = gen_opts.add_mutually_exclusive_group()
    output.add_argument("-q", "--quiet",
                        help="quiet mode, print no warnings and errors",
                        action="store_true")
    output.add_argument("-v", "--verbose",
                        help="verbose mode, print processing details",
                        action="store_true")
    output.add_argument("-d", "--debug",
                        help="debug mode, print debug information",
                        action="store_true")
    gen_opts.add_argument("-ll", "--log-level", metavar='[l]',
                          help="use level l for the logger (critical, error, "
                               "warn, info, debug)",
                          type=str,
                          choices=['critical', 'error', 'warn', 'info', 'debug'])
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
                          help="propose n transfer syntaxes (1 - 3)",
                          type=int)
    #net_opts.add_argument("-ppc", "--propose-pc", metavar='[n]umber',
    #                      help="propose n presentation contexts (1 - 128)",
    #                      type=int)
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
                          help="set max receive pdu to n bytes (4096..131072)",
                          type=int,
                          default=16384)
    net_opts.add_argument("--repeat", metavar='[n]umber',
                          help="repeat n times",
                          type=int,
                          default=1)
    net_opts.add_argument("--abort",
                          help="abort association instead of releasing it",
                          action="store_true")

    return parser.parse_args()


args = _setup_argparser()

#--------------------------- SETUP USING ARGUMENTS ----------------------------

# Logging/Output
if args.quiet:
    for h in LOGGER.handlers:
        LOGGER.removeHandler(h)

    LOGGER.addHandler(logging.NullHandler())

    pynetdicom_logger = logging.getLogger('pynetdicom3')
    for h in pynetdicom_logger.handlers:
        pynetdicom_logger.removeHandler(h)

    pynetdicom_logger.addHandler(logging.NullHandler())

if args.verbose:
    LOGGER.setLevel(logging.INFO)
    pynetdicom_logger = logging.getLogger('pynetdicom3')
    pynetdicom_logger.setLevel(logging.INFO)

if args.debug:
    LOGGER.setLevel(logging.DEBUG)
    pynetdicom_logger = logging.getLogger('pynetdicom3')
    pynetdicom_logger.setLevel(logging.DEBUG)

if args.log_level:
    levels = {'critical' : logging.CRITICAL,
              'error'    : logging.ERROR,
              'warn'     : logging.WARNING,
              'info'     : logging.INFO,
              'debug'    : logging.DEBUG}
    LOGGER.setLevel(levels[args.log_level])
    pynetdicom_logger = logging.getLogger('pynetdicom3')
    pynetdicom_logger.setLevel(levels[args.log_level])

if args.log_config:
    fileConfig(args.log_config)

# Propose extra transfer syntaxes
try:
    if 2 <= args.propose_ts:
        transfer_syntax = [ImplicitVRLittleEndian,
                           ExplicitVRLittleEndian,
                           ExplicitVRBigEndian]
        transfer_syntax = [ts for ts in transfer_syntax[:args.propose_ts]]
    else:
        transfer_syntax = [ImplicitVRLittleEndian]
except:
    transfer_syntax = [ImplicitVRLittleEndian]

#-------------------------- CREATE AE and ASSOCIATE ---------------------------

if args.version:
    print('echoscu.py v%s' %(VERSION))
    sys.exit()

LOGGER.debug('echoscu.py v%s', VERSION)
LOGGER.debug('')


# Create local AE
# Binding to port 0, OS will pick an available port
ae = AE(ae_title=args.calling_aet, port=0)

ae.add_requested_context(VerificationSOPClass, transfer_syntax)

# Set timeouts
ae.network_timeout = args.timeout
ae.acse_timeout = args.acse_timeout
ae.dimse_timeout = args.dimse_timeout

# Request association with remote AE
assoc = ae.associate(args.peer,
                     args.port,
                     ae_title=args.called_aet,
                     max_pdu=args.max_pdu)

# If we successfully Associated then send N DIMSE C-ECHOs
if assoc.is_established:
    for ii in range(args.repeat):
        # `status` is a pydicom Dataset
        status = assoc.send_c_echo()

    # Abort or release association
    if args.abort:
        assoc.abort()
    else:
        assoc.release()
