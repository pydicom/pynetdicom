#!/usr/bin/env python
"""An Echo, Storage and QR SCP application.

For receiving Echo, Storage and Query/Retrieve (QR) requests.
"""

import argparse
import os
import sys

from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import (
    ExplicitVRLittleEndian, ImplicitVRLittleEndian, ExplicitVRBigEndian
)

from pynetdicom import (
    AE, evt,
    VerificationPresentationContexts,
    StoragePresentationContexts,
    QueryRetrievePresentationContexts,
)
from pynetdicom.apps.common import (
    setup_logging, create_dataset, SOP_CLASS_PREFIXES
)


__version__ = '0.0.0'


def _setup_argparser():
    """Setup the command line arguments"""
    # Description
    parser = argparse.ArgumentParser(
        description=(
            "The movescp application implements a Service Class User (SCU) "
            "for the Query/Retrieve (QR) Service Class and (optionally) a "
            "Storage SCP for the Storage Service Class. movescu supports "
            "retrieve functionality using the C-MOVE message. It sends query "
            "keys to an SCP and waits for a response. It will accept "
            "associations for the purpose of receiving images sent as a "
            "result of the C-MOVE request. movescu can initiate the transfer "
            "of images to a third party or can retrieve images to itself "
            "(note: the use of the term 'move' is a misnomer, the C-MOVE "
            "operation performs a SOP Instance copy only)"
        ),
        usage="movescu [options] peer port dcmfile-in"
    )

    # Parameters
    req_opts = parser.add_argument_group('Parameters')
    req_opts.add_argument(
        "peer", help="TCP/IP address of DICOM peer", type=str
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
        help="set my calling AE title (default: MOVESCU)",
        type=str,
        default='MOVESCU'
    )
    net_opts.add_argument(
        "-aec", "--called-aet", metavar='[a]etitle',
        help="set called AE title of peer (default: ANY-SCP)",
        type=str,
        default='ANY-SCP'
    )
    net_opts.add_argument(
        "-aem", "--move-aet", metavar='[a]etitle',
        help="set move destination AE title (default: STORESCP)",
        type=str,
        default='STORESCP'
    )

    # Query information model choices
    qr_group = parser.add_argument_group('Query Information Model Options')
    qr_model = qr_group.add_mutually_exclusive_group()
    qr_model.add_argument(
        "-P", "--patient",
        help="use patient root information model",
        action="store_true"
    )
    qr_model.add_argument(
        "-S", "--study",
        help="use study root information model",
        action="store_true"
    )
    qr_model.add_argument(
        "-O", "--psonly",
        help="use patient/study only information model",
        action="store_true"
    )

    # Query Options
    qr_query = parser.add_argument_group('Query Options')
    qr_query.add_argument(
        '-k', '--keyword',
        metavar='[k]eyword: "gggg,eeee=str", "keyword=str"',
        help=(
            "add or override a query element using either an element tag as "
            "(group,element) or the element's keyword (such as PatientName)"
        ),
        type=str,
        action='append',
    )
    qr_query.add_argument(
        '-f', '--file',
        metavar='path to [f]ile',
        help=(
            "use a DICOM file as the query dataset, if "
            "used with -k then the elements will be added to or overwrite "
            "those present in the file"
        ),
        type=str,
    )

    # Store SCP options
    store_group = parser.add_argument_group('Storage SCP Options')
    store_group.add_argument(
        "--store",
        help="start a Storage SCP that can be used as the move destination",
        action="store_true",
        default=False
    )
    store_group.add_argument(
        "--store-port",
        help="the port number to use for the Storage SCP",
        type=int,
        default=11113
    )
    store_group.add_argument(
        "--store_aet",
        help="the AE title to use for the Storage SCP",
        type=str,
        default="STORESCP"
    )

    # Output Options
    out_opts = parser.add_argument_group('Output Options')
    out_opts.add_argument(
        '-od', "--output-directory", metavar="[d]irectory",
        help="write received objects to existing directory d",
        type=str
    )

    # Miscellaneous
    misc_opts = parser.add_argument_group('Miscellaneous')
    misc_opts.add_argument(
        '--ignore',
        help="receive data but don't store it",
        action="store_true"
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

    def handle_store(event):
        return 0x0000

    def handle_find(event):
        return 0x0000

    def handle_get(event):
        return 0x0000

    def handle_move(event):
        return 0x0000
