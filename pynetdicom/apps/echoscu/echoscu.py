#!/usr/bin/env python
"""An Echo SCU application.

Used for verifying basic DICOM connectivity and as such has a focus on
providing useful debugging and logging information.
"""

import argparse
import sys

from pydicom.uid import (
    ExplicitVRLittleEndian, ImplicitVRLittleEndian,
    ExplicitVRBigEndian, DeflatedExplicitVRLittleEndian
)

from pynetdicom import AE
from pynetdicom.apps.common import setup_logging
from pynetdicom._globals import DEFAULT_MAX_LENGTH
from pynetdicom.sop_class import VerificationSOPClass


__version__ = '0.7.0'


def _setup_argparser():
    """Setup the command line arguments"""
    # Description
    parser = argparse.ArgumentParser(
        description=(
            "The echoscu application implements a Service Class User "
            "(SCU) for the Verification Service Class. It sends a DICOM "
            "C-ECHO message to a Service Class Provider (SCP) and "
            "waits for a response. The application can be used to "
            "verify basic DICOM connectivity."
        ),
        usage="echoscu [options] addr port"
    )

    # Parameters
    req_opts = parser.add_argument_group('Parameters')
    req_opts.add_argument(
        "addr", help="TCP/IP address of DICOM peer", type=str
    )
    req_opts.add_argument("port", help="TCP/IP port number of peer", type=int)

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
        "-aet", "--calling-aet", metavar='[a]etitle',
        help="set my calling AE title (default: ECHOSCU)",
        type=str,
        default='ECHOSCU'
    )
    net_opts.add_argument(
        "-aec", "--called-aet", metavar='[a]etitle',
        help="set called AE title of peer (default: ANY-SCP)",
        type=str,
        default='ANY-SCP'
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

    # Transfer Syntaxes
    ts_opts = parser.add_argument_group("Transfer Syntax Options")
    syntax = ts_opts.add_mutually_exclusive_group()
    syntax.add_argument(
        "-xe", "--request-little",
        help="request explicit VR little endian TS only",
        action="store_true"
    )
    syntax.add_argument(
        "-xb", "--request-big",
        help="request explicit VR big endian TS only",
        action="store_true"
    )
    syntax.add_argument(
        "-xi", "--request-implicit",
        help="request implicit VR little endian TS only",
        action="store_true"
    )

    # Miscellaneous Options
    misc_opts = parser.add_argument_group('Miscellaneous Options')
    misc_opts.add_argument(
        "--repeat", metavar='[n]umber',
        help="repeat echo request n times",
        type=int,
        default=1
    )
    misc_opts.add_argument(
        "--abort",
        help="abort association instead of releasing it",
        action="store_true"
    )

    return parser.parse_args()


def main(args=None):
    """Run the application."""
    if args is not None:
        sys.argv = args

    args = _setup_argparser()

    if args.version:
        print('echoscu.py v{}'.format(__version__))
        sys.exit()

    APP_LOGGER = setup_logging(args, 'echoscu')
    APP_LOGGER.debug('echoscu.py v%s', __version__)
    APP_LOGGER.debug('')

    # Set Transfer Syntax options
    transfer_syntax = [
        ExplicitVRLittleEndian,
        ImplicitVRLittleEndian,
        DeflatedExplicitVRLittleEndian,
        ExplicitVRBigEndian
    ]

    if args.request_little:
        transfer_syntax = [ExplicitVRLittleEndian]
    elif args.request_big:
        transfer_syntax = [ExplicitVRBigEndian]
    elif args.request_implicit:
        transfer_syntax = [ImplicitVRLittleEndian]

    # Create local AE
    ae = AE(ae_title=args.calling_aet)
    ae.add_requested_context(VerificationSOPClass, transfer_syntax)

    # Set timeouts
    ae.acse_timeout = args.acse_timeout
    ae.dimse_timeout = args.dimse_timeout
    ae.network_timeout = args.network_timeout

    # Request association with remote AE
    assoc = ae.associate(
        args.addr, args.port, ae_title=args.called_aet, max_pdu=args.max_pdu
    )

    # If we successfully associated then send C-ECHO
    if assoc.is_established:
        for ii in range(args.repeat):
            # `status` is a pydicom Dataset
            status = assoc.send_c_echo()

        # Abort or release association
        if args.abort:
            assoc.abort()
        else:
            assoc.release()
    else:
        # Failed to associate: timeout, refused, connection closed, aborted
        sys.exit(1)


if __name__ == "__main__":
    main()
