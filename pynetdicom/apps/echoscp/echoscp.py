#!/usr/bin/env python
"""A Verification SCP application."""

import argparse
import sys

from pydicom.uid import (
    ExplicitVRLittleEndian, ImplicitVRLittleEndian, ExplicitVRBigEndian
)

from pynetdicom import AE, evt
from pynetdicom.apps.common import setup_logging
from pynetdicom._globals import ALL_TRANSFER_SYNTAXES, DEFAULT_MAX_LENGTH
from pynetdicom.sop_class import VerificationSOPClass


__version__ = '0.7.0'


def _setup_argparser():
    """Setup the command line arguments"""
    # Description
    parser = argparse.ArgumentParser(
        description=(
            "The echoscp application implements a Service Class "
            "Provider (SCP) for the Verification SOP Class. It "
            "listens for a DICOM C-ECHO message from a Service Class "
            "User (SCU) and sends a response. The application can be "
            "used to verify basic DICOM connectivity."
        ),
        usage="echoscp [options] port"
    )

    # Parameters
    req_opts = parser.add_argument_group('Parameters')
    req_opts.add_argument(
        "port",
        help="TCP/IP port number to listen on",
        type=int
    )

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

    # Network Options
    net_opts = parser.add_argument_group('Network Options')
    net_opts.add_argument(
        "-aet", "--ae-title", metavar='[a]etitle',
        help="set my AE title (default: ECHOSCP)",
        type=str,
        default='ECHOSCP'
    )
    net_opts.add_argument(
        "-ta", "--acse-timeout", metavar='[s]econds',
        help="timeout for ACSE messages (default: 30 s)",
        type=float,
        default=30
    )
    net_opts.add_argument(
        "-td", "--dimse-timeout", metavar='[s]econds',
        help="timeout for DIMSE messages (default: 30 s)",
        type=float,
        default=30
    )
    net_opts.add_argument(
        "-tn", "--network-timeout", metavar='[s]econds',
        help="timeout for the network (default: 30 s)",
        type=float,
        default=30
    )
    net_opts.add_argument(
        "-pdu", "--max-pdu", metavar='[n]umber of bytes',
        help=(
            "set max receive pdu to n bytes (0 for unlimited, default: {})"
            .format(DEFAULT_MAX_LENGTH)
        ),
        type=int,
        default=DEFAULT_MAX_LENGTH
    )
    net_opts.add_argument(
        "-ba", "--bind-address", metavar="[a]ddress",
        help=(
            "The address of the network interface to "
            "listen on. If unset, listen on all interfaces."
        ),
        default=''
    )

    # Transfer Syntaxes
    ts_opts = parser.add_argument_group('Preferred Transfer Syntaxes')
    ts = ts_opts.add_mutually_exclusive_group()
    ts.add_argument(
        "-x=", "--prefer-uncompr",
        help="prefer explicit VR local byte order",
        action="store_true"
    )
    ts.add_argument(
        "-xe", "--prefer-little",
        help="prefer explicit VR little endian TS",
        action="store_true"
    )
    ts.add_argument(
        "-xb", "--prefer-big",
        help="prefer explicit VR big endian TS",
        action="store_true"
    )
    ts.add_argument(
        "-xi", "--implicit",
        help="accept implicit VR little endian TS only",
        action="store_true"
    )

    return parser.parse_args()


def handle_echo(event):
    """Optional implementation of the evt.EVT_C_ECHO handler."""
    # Return a Success response to the peer
    # We could also return a pydicom Dataset with a (0000, 0900) Status
    #   element
    return 0x0000


def main(args=None):
    """Run the application."""
    if args is not None:
        sys.argv = args

    args = _setup_argparser()

    if args.version:
        print('echoscp.py v{}'.format(__version__))
        sys.exit()

    APP_LOGGER = setup_logging(args, 'echoscp')
    APP_LOGGER.debug('echoscp.py v{0!s}'.format(__version__))
    APP_LOGGER.debug('')

    # Set Transfer Syntax options
    transfer_syntax = ALL_TRANSFER_SYNTAXES[:]

    if args.prefer_uncompr:
        transfer_syntax.remove(str(ImplicitVRLittleEndian))
        transfer_syntax.append(ImplicitVRLittleEndian)
    elif args.prefer_little:
        transfer_syntax.remove(str(ExplicitVRLittleEndian))
        transfer_syntax.insert(0, ExplicitVRLittleEndian)
    elif args.prefer_big:
        transfer_syntax.remove(str(ExplicitVRBigEndian))
        transfer_syntax.insert(0, ExplicitVRBigEndian)
    elif args.implicit:
        transfer_syntax = [ImplicitVRLittleEndian]

    handlers = [(evt.EVT_C_ECHO, handle_echo)]

    # Create application entity
    ae = AE(ae_title=args.ae_title)
    ae.add_supported_context(VerificationSOPClass, transfer_syntax)
    ae.maximum_pdu_size = args.max_pdu
    ae.network_timeout = args.network_timeout
    ae.acse_timeout = args.acse_timeout
    ae.dimse_timeout = args.dimse_timeout

    ae.start_server((args.bind_address, args.port), evt_handlers=handlers)


if __name__ == "__main__":
    main()
