#!/usr/bin/env python
"""A Verification, Storage and Query/Retrieve SCP application."""

import argparse
import os
import sys

try:
    import sqlalchemy
    import sqlite3
except ImportError:
    sys.exit("qrscp.py requires the sqlalchemy and sqlite3 packages")

from pydicom.dataset import Dataset
from pydicom.uid import (
    ExplicitVRLittleEndian, ImplicitVRLittleEndian, ExplicitVRBigEndian,
    DeflatedExplicitVRLittleEndian, JPEGBaseline, JPEGExtended,
    JPEGLosslessP14, JPEGLossless, JPEGLSLossless, JPEGLSLossy,
    JPEG2000Lossless, JPEG2000, JPEG2000MultiComponentLossless,
    JPEG2000MultiComponent, RLELossless
)

from pynetdicom import (
    AE, evt, QueryRetrievePresentationContexts, AllStoragePresentationContexts,
    VerificationPresentationContexts
)
from pynetdicom.apps.common import setup_logging
from pynetdicom.sop_class import VerificationSOPClass
from handlers import (
    handle_echo, handle_find, handle_get, handle_move, handle_store
)


__version__ = '0.0.0alpha1'


def _setup_argparser():
    """Setup the command line arguments"""
    # Description
    parser = argparse.ArgumentParser(
        description=(
            "The qrscp application implements a Service Class Provider (SCP) "
            "for the Verification, Storage and Query/Retrieve (QR) Service "
            "Classes."""
        ),
        usage="qrscp [options] port"
    )

    # Parameters
    req_opts = parser.add_argument_group('Parameters')
    req_opts.add_argument("port", help="TCP/IP listen port number", type=int)

    # General Options
    gen_opts = parser.add_argument_group('General Options')
    gen_opts.add_argument(
        "--version",
        help="print version information and exit",
        action="store_true"
    )
    output = gen_opts.add_mutually_exclusive_group()
    output.add_argument(
        "-q", "--quiet",
        help="quiet mode, print no warnings and errors",
        action="store_const",
        dest='log_type', const='q'
    )
    output.add_argument(
        "-v", "--verbose",
        help="verbose mode, print processing details",
        action="store_const",
        dest='log_type', const='v'
    )
    output.add_argument(
        "-d", "--debug",
        help="debug mode, print debug information",
        action="store_const",
        dest='log_type', const='d'
    )
    gen_opts.add_argument(
        "-ll", "--log-level", metavar='[l]',
        help=(
            "use level l for the logger (critical, error, warn, info, debug)"
        ),
        type=str,
        choices=['critical', 'error', 'warn', 'info', 'debug']
    )
    gen_opts.add_argument(
        '-c', '--config', metavar='[f]ilename',
        help="use configuration file f",
        type=str,
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = _setup_argparser()

    if args.version:
        print('qrscp.py v{}'.format(__version__))
        sys.exit()

    APP_LOGGER = setup_logging(args, 'qrscp')
    APP_LOGGER.debug('qrscp.py v{0!s}'.format(__version__))
    APP_LOGGER.debug('')

    handlers = [
        (evt.EVT_C_ECHO, handle_echo, [args, APP_LOGGER]),
        (evt.EVT_C_FIND, handle_find, [args, APP_LOGGER]),
        (evt.EVT_C_GET, handle_get, [args, APP_LOGGER]),
        (evt.EVT_C_MOVE, handle_move, [args, APP_LOGGER]),
        (evt.EVT_C_STORE, handle_store, [args, APP_LOGGER]),
    ]

    ae = AE()
    ae.add_supported_context(VerificationSOPClass)
    ae.start_server(('', 11112), evt_handlers=handlers)
