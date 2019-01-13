#!/usr/bin/env python

"""
    A dcmtk style movescu application

    Used for
"""

import argparse
import logging
import os
import socket
import sys
import time

from pydicom.dataset import Dataset
from pydicom.uid import (
    ExplicitVRLittleEndian, ImplicitVRLittleEndian, ExplicitVRBigEndian
)

from pynetdicom import (
    AE,
    QueryRetrievePresentationContexts,
    PYNETDICOM_IMPLEMENTATION_VERSION,
    PYNETDICOM_IMPLEMENTATION_UID
)

logger = logging.Logger('movescu')
stream_logger = logging.StreamHandler()
formatter = logging.Formatter('%(levelname).1s: %(message)s')
stream_logger.setFormatter(formatter)
logger.addHandler(stream_logger)
logger.setLevel(logging.ERROR)


VERSION = '0.3.0'


def _setup_argparser():
    """Setup the command line arguments"""
    # Description
    parser = argparse.ArgumentParser(
        description="The movescu application implements a Service Class User "
                    "(SCU) for the Query/Retrieve (QR) Service Class and a SCP "
                    " for the Storage Service Class. movescu "
                    "supports retrieve functionality using the C-MOVE "
                    "message. It sends query keys to an SCP and waits for a "
                    "response. It will accept associations for the purpose of "
                    "receiving images sent as a result of the C-MOVE request. "
                    "The application can be used to test SCPs of the "
                    "QR Service Classes. movescu can initiate the transfer of "
                    "images to a third party or can retrieve images to itself "
                    "(note: the use of the term 'move' is a misnomer, the "
                    "C-MOVE operation performs an image copy only)",
        usage="movescu [options] peer port dcmfile-in")

    # Parameters
    req_opts = parser.add_argument_group('Parameters')
    req_opts.add_argument("peer", help="hostname of DICOM peer", type=str)
    req_opts.add_argument("port", help="TCP/IP port number of peer", type=int)
    req_opts.add_argument("dcmfile_in",
                          metavar="dcmfile-in",
                          help="DICOM query file(s)",
                          type=str)

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
                          help="set my calling AE title (default: MOVESCU)",
                          type=str,
                          default='MOVESCU')
    net_opts.add_argument("-aec", "--called-aet", metavar='[a]etitle',
                          help="set called AE title of peer (default: ANY-SCP)",
                          type=str,
                          default='ANY-SCP')
    net_opts.add_argument("-aem", "--move-aet", metavar='[a]etitle',
                          help="set move destination AE title (default: "
                                "MOVESCP)",
                          type=str,
                          default='MOVESCP')

    # Query information model choices
    qr_group = parser.add_argument_group('Query Information Model Options')
    qr_model = qr_group.add_mutually_exclusive_group()
    qr_model.add_argument("-P", "--patient",
                          help="use patient root information model (default)",
                          action="store_true",
                          )
    qr_model.add_argument("-S", "--study",
                          help="use study root information model",
                          action="store_true")
    qr_model.add_argument("-O", "--psonly",
                          help="use patient/study only information model",
                          action="store_true")

    # Output Options
    out_opts = parser.add_argument_group('Output Options')
    out_opts.add_argument('-od', "--output-directory", metavar="[d]irectory",
                          help="write received objects to existing directory d",
                          type=str)

    # Miscellaneous
    misc_opts = parser.add_argument_group('Miscellaneous')
    misc_opts.add_argument('--ignore',
                           help="receive data but don't store it",
                           action="store_true")

    return parser.parse_args()

args = _setup_argparser()

if args.verbose:
    logger.setLevel(logging.INFO)
    pynetdicom_logger = logging.getLogger('PYNETDICOM3_')
    pynetdicom_logger.setLevel(logging.INFO)

if args.debug:
    logger.setLevel(logging.DEBUG)
    pynetdicom_logger = logging.getLogger('pynetdicom')
    pynetdicom_logger.setLevel(logging.DEBUG)

logger.debug('$movescu.py v{0!s}'.format(VERSION))
logger.debug('')

# Create application entity
# Binding to port 0 lets the OS pick an available port
ae = AE(ae_title=args.calling_aet)
ae.requested_contexts = QueryRetrievePresentationContexts

# Request association with remote AE
assoc = ae.associate(args.peer, args.port, ae_title=args.called_aet)

if assoc.is_established:
    # Create query dataset
    ds = Dataset()
    ds.PatientName = '*'
    ds.QueryRetrieveLevel = "PATIENT"

    if args.patient:
        query_model = 'P'
    elif args.study:
        query_model = 'S'
    elif args.psonly:
        query_model = 'O'
    else:
        query_model = 'P'

    if args.move_aet:
        move_aet = args.move_aet
    else:
        move_aet = args.calling_aet

    # Send query
    response = assoc.send_c_move(ds, move_aet, query_model=query_model)

    for (status, identifier) in response:
        pass

    assoc.release()
