#!/usr/bin/env python
"""A Storage SCU application.

Used for transferring DICOM SOP Instances to a Storage SCP.
"""

import argparse
import sys

from pydicom import dcmread
from pydicom.uid import (
    ExplicitVRLittleEndian, ImplicitVRLittleEndian,
    ExplicitVRBigEndian, DeflatedExplicitVRLittleEndian
)

from pynetdicom import AE, StoragePresentationContexts
from pynetdicom.apps.common import setup_logging
from pynetdicom.status import STORAGE_SERVICE_CLASS_STATUS

__version__ = '0.3.0'


def _setup_argparser():
    """Setup the command line arguments"""
    # Description
    parser = argparse.ArgumentParser(
        description=(
            "The storescu application implements a Service Class User "
            "(SCU) for the Storage Service Class. For each DICOM "
            "file on the command line it sends a C-STORE message to a "
            "Storage Service Class Provider (SCP) and waits for a response."
        ),
        usage="storescu [options] addr port dcmfile-in"
    )

    # Parameters
    req_opts = parser.add_argument_group('Parameters')
    req_opts.add_argument(
        "addr", help="TCP/IP address or hostname of DICOM peer", type=str
    )
    req_opts.add_argument("port", help="TCP/IP port number of peer", type=int)
    req_opts.add_argument(
        "dcmfile_in",
        metavar="dcmfile-in",
        help="DICOM file to be transmitted",
        type=str
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
        action="store_true"
    )
    output.add_argument(
        "-v", "--verbose",
        help="verbose mode, print processing details",
        action="store_true"
    )
    output.add_argument(
        "-d", "--debug",
        help="debug mode, print debug information",
        action="store_true"
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
        "-lc", "--log-config", metavar='[f]',
        help="use config file f for the logger",
        type=str
    )

    # Network Options
    net_opts = parser.add_argument_group('Network Options')
    net_opts.add_argument(
        "-aet", "--calling-aet", metavar='[a]etitle',
        help="set my calling AE title (default: STORESCU)",
        type=str,
        default='STORESCU'
    )
    net_opts.add_argument(
        "-aec", "--called-aet", metavar='[a]etitle',
        help="set called AE title of peer (default: ANY-SCP)",
        type=str,
        default='ANY-SCP'
    )
    net_opts.add_argument(
        "-ta", "--acse-timeout", metavar='[s]econds',
        help="timeout for ACSE messages",
        type=int,
        default=30
    )
    net_opts.add_argument(
        "-td", "--dimse-timeout", metavar='[s]econds',
        help="timeout for DIMSE messages",
        type=int,
        default=30
    )
    net_opts.add_argument(
        "-tn", "--network-timeout", metavar='[s]econds',
        help="timeout for the network",
        type=int,
        default=30
    )
    net_opts.add_argument(
        "-pdu", "--max-pdu", metavar='[n]umber of bytes',
        help="set max receive pdu to n bytes (4096..131072)",
        type=int,
        default=16384
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

    # Misc Options
    misc_opts = parser.add_argument_group('Miscellaneous Options')
    misc_opts.add_argument(
        "-cx", "--single-context",
        help=(
            "only request a single presentation context that matches the "
            "input DICOM file"
        ),
        action="store_true",
    )

    return parser.parse_args()


if __name__ == "__main__":
    args = _setup_argparser()

    if args.version:
        print('storescu.py v{}'.format(__version__))
        sys.exit()

    APP_LOGGER = setup_logging(args, 'storescu')
    APP_LOGGER.debug('storescu.py v{0!s}'.format(__version__))
    APP_LOGGER.debug('')

    # Check file exists and is readable and DICOM
    APP_LOGGER.debug('Checking input file')
    try:
        with open(args.dcmfile_in, 'rb') as fp:
            ds = dcmread(fp, force=True)
    except Exception as exc:
        APP_LOGGER.error(
            'Cannot read input file {0!s}'.format(args.dcmfile_in)
        )
        APP_LOGGER.exception(exc)
        sys.exit(1)

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

    # Bind to port 0, OS will pick an available port
    ae = AE(ae_title=args.calling_aet)
    ae.acse_timeout = args.acse_timeout
    ae.dimse_timeout = args.dimse_timeout
    ae.network_timeout = args.network_timeout

    # Ensure the dataset is covered by the requested presentation contexts
    if args.single_context:
        ae.add_requested_context(
            ds.SOPClassUID, ds.file_meta.TransferSyntaxUID
        )
    else:
        sop_classes = [
            cx.abstract_syntax for cx in StoragePresentationContexts
        ]
        nr_uids = len(sop_classes)
        if ds.SOPClassUID not in sop_classes:
            ae.add_requested_context(ds.SOPClassUID, transfer_syntax)
            nr_uids -= 1

        for uid in sop_classes[:nr_uids]:
            ae.add_requested_context(uid, transfer_syntax)

    # Request association with remote
    assoc = ae.associate(
        args.addr, args.port, ae_title=args.called_aet, max_pdu=args.max_pdu
    )
    if assoc.is_established:
        APP_LOGGER.info('Sending file: {0!s}'.format(args.dcmfile_in))
        status = assoc.send_c_store(ds)
        assoc.release()
