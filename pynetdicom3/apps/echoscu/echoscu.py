#!/usr/bin/env python
"""A dcmtk style echoscu application.

Used for verifying basic DICOM connectivity and as such has a focus on
providing useful debugging and logging information.
"""

import argparse
import logging
from logging.config import fileConfig
import sys

from pydicom.uid import ExplicitVRLittleEndian, ImplicitVRLittleEndian, \
                        ExplicitVRBigEndian

from pynetdicom3 import AE, VerificationSOPClass

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

VERSION = '0.5.2'

def _setup_argparser():
    """Setup the command line arguments"""
    # Description
    parser = argparse.ArgumentParser(
        description="The echoscu application implements a Service Class User "
                    "(SCU) for the Verification SOP Class. It sends a DICOM "
                    "C-ECHO message to a Service Class Provider (SCP) and "
                    "waits for a response. The application can be used to "
                    "verify basic DICOM connectivity.",
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

    # SSL/TLS Options
    ssl_opts = parser.add_argument_group('SSL/TLS Options')
    ssl_opts.add_argument("-cert", "--cert-file", metavar='[p]ath',
                          help="set the file path of the certificate file",
                          type=str)
    ssl_opts.add_argument("-key", "--key-file", metavar='[p]ath',
                          help="set the file path of the private key file",
                          type=str)
    ssl_opts.add_argument("-validation", "--cert-validation",
                          help="set the file path of the private key file",
                          action="store_true")
    ssl_opts.add_argument("-version", "--ssl-version", metavar='[p]ath',
                          help="set the file path of the private key file",
                          type=str,
                          choices=['sslv23', 'tlsv1', 'tlsv1_1', 'tlsv1_2'])
    ssl_opts.add_argument("-cacerts", "--cacerts-file", metavar='[p]ath',
                          help="set the file path of the certificates"
                               " authority file",
                          type=str)

    # TLS Options
    """
    tls_opts = parser.add_argument_group('Transport Layer Security (TLS) Options')
    tls_opts.add_argument("-dtls", "--disable-tls",
                          help="use normal TCP/IP connection (default)",
                          action="store_true")
    tls_opts.add_argument("-tls", "--enable-tls",
                          metavar="[p]rivate key file, [c]erficiate file",
                          help="use authenticated secure TLD connection",
                          type=str)
    tls_opts.add_argument("-tla", "--anonymous-tls",
                          help="use secure TLD connection without certificate",
                          action="store_true")
    tls_opts.add_argument("-ps", "--std-password",
                          help="prompt user to type password on stdin (default)",
                          action="store_true")
    tls_opts.add_argument("-pw", "--use-password", metavar="[p]assword",
                          help="use specified password",
                          type=str)
    tls_opts.add_argument("-nw", "--null-password",
                          help="use empty string as password",
                          action="store_true")
    tls_opts.add_argument("-pem", "--pem-keys",
                          help="read keys and certificates as PEM file "
                                                                    "(default)",
                          action="store_true")
    tls_opts.add_argument("-der", "--der-keys",
                          help="read keys and certificates as DER file",
                          action="store_true")
    tls_opts.add_argument("-cf", "--add-cert-file",
                          metavar="[c]ertificate filename",
                          help="add certificate file to list of certificates",
                          type=str)
    tls_opts.add_argument("-cd", "--add-cert-dir",
                          metavar="[c]ertificate directory",
                          help="add certificates in d to list of certificates",
                          type=str)
    tls_opts.add_argument("-cs", "--cipher",
                          metavar="[c]iphersuite name",
                          help="add ciphersuite to list of negotiated suites",
                          type=str)
    tls_opts.add_argument("-dp", "--dhparam",
                          metavar="[f]ilename",
                          help="read DH parameters for DH/DSS ciphersuites",
                          type=str)
    tls_opts.add_argument("-rs", "--seed",
                          metavar="[f]ilename",
                          help="seed random generator with contents of f",
                          type=str)
    tls_opts.add_argument("-ws", "--write-seed",
                          help="write back modified seed (only with --seed)",
                          action="store_true")
    tls_opts.add_argument("-wf", "--write-seed-file",
                          metavar="[f]ilename",
                          help="write modified seed to file f",
                          type=str)
    tls_opts.add_argument("-rc", "--require-peer-cert",
                          help="verify peer certificate, fail if absent "
                                        "(default)",
                          action="store_true")
    tls_opts.add_argument("-vc", "--verify-peer-cert",
                          help="verify peer certificate if present",
                          action="store_true")
    tls_opts.add_argument("-ic", "--ignore-peer-cert",
                          help="don't verify peer certificate",
                          action="store_true")
    """

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
        transfer_syntaxes = [ImplicitVRLittleEndian,
                             ExplicitVRLittleEndian,
                             ExplicitVRBigEndian]
        transfer_syntaxes = [ts for ts in transfer_syntaxes[:args.propose_ts]]
    else:
        transfer_syntaxes = [ImplicitVRLittleEndian]
except:
    transfer_syntaxes = [ImplicitVRLittleEndian]

# Repeat presentation contexts - broken as AE checks for duplicates
#try:
#    if 0 < args.propose_pc <= 128:
#        scu_sop_classes = [VerificationSOPClass] * args.propose_pc
#    else:
#        scu_sop_classes = [VerificationSOPClass]
#except:
#    scu_sop_classes = [VerificationSOPClass]

#-------------------------- CREATE AE and ASSOCIATE ---------------------------

if args.version:
    print('echoscu.py v%s %s $' %(VERSION, '2016-04-12'))
    sys.exit()

LOGGER.debug('echoscu.py v%s %s', VERSION, '2017-02-04')
LOGGER.debug('')

# Check SSL/TLS options
sslargs = dict()
sslargs['certfile'] = args.cert_file
sslargs['keyfile'] = args.key_file
sslargs['cert_verify'] = args.cert_validation
if args.cacerts_file:
    sslargs['cacerts'] = args.cacerts_file
if args.ssl_version:
    sslargs['version'] = args.ssl_version


# Create local AE
# Binding to port 0, OS will pick an available port
ae = AE(ae_title=args.calling_aet,
        port=0,
        scu_sop_class=[VerificationSOPClass],
        scp_sop_class=[],
        transfer_syntax=transfer_syntaxes)
ae.add_ssl(**sslargs)

# Set timeouts
ae.network_timeout = args.timeout
ae.acse_timeout = args.acse_timeout
ae.dimse_timeout = args.dimse_timeout

# Request association with remote AE
assoc = ae.associate(args.peer, args.port, args.called_aet,
                     max_pdu=args.max_pdu)

# If we successfully Associated then send N DIMSE C-ECHOs
if assoc.is_established:
    for ii in range(args.repeat):
        status = assoc.send_c_echo()

    if status is not None:
        # Abort or release association
        if args.abort:
            assoc.abort()
        else:
            assoc.release()
