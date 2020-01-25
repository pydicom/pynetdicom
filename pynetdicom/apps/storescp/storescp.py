#!/usr/bin/env python
"""A Storage SCP application.

Used for receiving DICOM SOP Instances transferred from an SCU.
"""

import argparse
import os
import sys

from pydicom.dataset import Dataset
from pydicom.uid import (
    ExplicitVRLittleEndian, ImplicitVRLittleEndian, ExplicitVRBigEndian
)

from pynetdicom import (
    AE, evt,
    AllStoragePresentationContexts,
    VerificationPresentationContexts,
)
from pynetdicom.apps.common import setup_logging, SOP_CLASS_PREFIXES
from pynetdicom._globals import ALL_TRANSFER_SYNTAXES, DEFAULT_MAX_LENGTH


__version__ = '0.6.0'


def _setup_argparser():
    """Setup the command line arguments"""
    # Description
    parser = argparse.ArgumentParser(
        description=(
            "The storescp application implements a Service Class "
            "Provider (SCP) for the Storage and Verification SOP Classes. It "
            "listens for a DICOM C-STORE message from a Service Class User "
            "(SCU) and stores the resulting DICOM dataset."
        ),
        usage="storescp [options] port"
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
    gen_opts.add_argument(
        "-lc", "--log-config", metavar='[f]',
        help="use config file f for the logger",
        type=str
    )

    # Network Options
    net_opts = parser.add_argument_group('Network Options')
    net_opts.add_argument(
        "-aet", "--ae-title", metavar='[a]etitle',
        help="set my AE title (default: STORESCP)",
        type=str,
        default='STORESCP'
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

    # Output Options
    out_opts = parser.add_argument_group('Output Options')
    out_opts.add_argument(
        '-od', "--output-directory", metavar="[d]irectory",
        help="write received objects to directory d",
        type=str
    )
    out_opts.add_argument(
        '--ignore',
        help="receive data but don't store it",
        action="store_true"
    )

    return parser.parse_args()


def handle_store(event):
    """Handle a C-STORE request.

    Parameters
    ----------
    event : pynetdicom.event.event
        The event corresponding to a C-STORE request.

    Returns
    -------
    status : pynetdicom.sop_class.Status or int
        A valid return status code, see PS3.4 Annex B.2.3 or the
        ``StorageServiceClass`` implementation for the available statuses
    """
    if args.ignore:
        return 0x0000

    ds = event.dataset
    # Remove any Group 0x0002 elements that may have been included
    ds = ds[0x00030000:]

    # Add the file meta information elements
    ds.file_meta = event.file_meta

    # Because pydicom uses deferred reads for its decoding, decoding errors
    #   are hidden until encountered by accessing a faulty element
    try:
        sop_class = ds.SOPClassUID
        sop_instance = ds.SOPInstanceUID
    except Exception as exc:
        APP_LOGGER.error(
            "Unable to decode the received dataset or missing 'SOP Class "
            "UID' and/or 'SOP Instance UID' elements"
        )
        APP_LOGGER.exception(exc)
        # Unable to decode dataset
        return 0xC210

    try:
        # Get the elements we need
        mode_prefix = SOP_CLASS_PREFIXES[sop_class][0]
    except KeyError:
        mode_prefix = 'UN'

    filename = '{0!s}.{1!s}'.format(mode_prefix, sop_instance)
    APP_LOGGER.info('Storing DICOM file: {0!s}'.format(filename))

    if os.path.exists(filename):
        APP_LOGGER.warning('DICOM file already exists, overwriting')

    status_ds = Dataset()
    status_ds.Status = 0x0000

    # Try to save to output-directory
    if args.output_directory is not None:
        filename = os.path.join(args.output_directory, filename)
        try:
            os.makedirs(args.output_directory)
        except Exception as exc:
            APP_LOGGER.error('Unable to create the output directory:')
            APP_LOGGER.error("    {0!s}".format(args.output_directory))
            APP_LOGGER.exception(exc)
            # Failed - Out of Resources - IOError
            status.Status = 0xA700
            return status

    try:
        # We use `write_like_original=False` to ensure that a compliant
        #   File Meta Information Header is written
        ds.save_as(filename, write_like_original=False)
        status_ds.Status = 0x0000 # Success
    except IOError:
        APP_LOGGER.error('Could not write file to specified directory:')
        APP_LOGGER.error("    {0!s}".format(os.path.dirname(filename)))
        APP_LOGGER.error(
            'Directory may not exist or you may not have write permission '
        )
        # Failed - Out of Resources - IOError
        status_ds.Status = 0xA700
    except Exception as exc:
        APP_LOGGER.error('Could not write file to specified directory:')
        APP_LOGGER.error("    {0!s}".format(os.path.dirname(filename)))
        APP_LOGGER.exception(exc)
        # Failed - Out of Resources - Miscellaneous error
        status_ds.Status = 0xA701

    return status_ds


if __name__ == "__main__":
    args = _setup_argparser()

    if args.version:
        print('storescp.py v{}'.format(__version__))
        sys.exit()

    APP_LOGGER = setup_logging(args, 'storescp')
    APP_LOGGER.debug('storescp.py v{0!s}'.format(__version__))
    APP_LOGGER.debug('')

    # Set Transfer Syntax options
    transfer_syntax = ALL_TRANSFER_SYNTAXES[:]

    if args.prefer_uncompr:
        transfer_syntax.remove(ImplicitVRLittleEndian)
        transfer_syntax.append(ImplicitVRLittleEndian)
    elif args.prefer_little:
        transfer_syntax.remove(ExplicitVRLittleEndian)
        transfer_syntax.insert(0, ExplicitVRLittleEndian)
    elif args.prefer_big:
        transfer_syntax.remove(ExplicitVRBigEndian)
        transfer_syntax.insert(0, ExplicitVRBigEndian)
    elif args.implicit:
        transfer_syntax = [ImplicitVRLittleEndian]

    handlers = [(evt.EVT_C_STORE, handle_store)]

    # Create application entity
    ae = AE(ae_title=args.ae_title)

    # Add presentation contexts with specified transfer syntaxes
    for context in AllStoragePresentationContexts:
        ae.add_supported_context(context.abstract_syntax, transfer_syntax)
    for context in VerificationPresentationContexts:
        ae.add_supported_context(context.abstract_syntax, transfer_syntax)

    ae.maximum_pdu_size = args.max_pdu

    # Set timeouts
    ae.network_timeout = args.network_timeout
    ae.acse_timeout = args.acse_timeout
    ae.dimse_timeout = args.dimse_timeout

    ae.start_server((args.bind_address, args.port), evt_handlers=handlers)
