#!/usr/bin/env python
"""A QR Move SCU application.

For sending Query/Retrieve (QR) C-MOVE requests to a QR Move SCP.
"""

import argparse
import os
import sys

from pydicom.dataset import Dataset

from pynetdicom import (
    AE, evt, QueryRetrievePresentationContexts, AllStoragePresentationContexts
)
from pynetdicom.apps.common import (
    setup_logging, create_dataset, SOP_CLASS_PREFIXES
)
from pynetdicom._globals import ALL_TRANSFER_SYNTAXES, DEFAULT_MAX_LENGTH
from pynetdicom.sop_class import (
    PatientRootQueryRetrieveInformationModelMove,
    StudyRootQueryRetrieveInformationModelMove,
    PatientStudyOnlyQueryRetrieveInformationModelMove,
)


__version__ = '0.4.0'


def _setup_argparser():
    """Setup the command line arguments"""
    # Description
    parser = argparse.ArgumentParser(
        description=(
            "The movescu application implements a Service Class User (SCU) "
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
        usage="movescu [options] addr port"
    )

    # Parameters
    req_opts = parser.add_argument_group('Parameters')
    req_opts.add_argument(
        "addr", help="TCP/IP address or hostname of DICOM peer", type=str
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
    gen_opts.add_argument(
        "-lc", "--log-config", metavar='[f]',
        help="use config file f for the logger",
        type=str
    )
    parser.set_defaults(log_type='v')

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
        metavar='[k]eyword: (gggg,eeee)=str, keyword=str',
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
        "--store-port", metavar='[p]ort',
        help="the port number to use for the Storage SCP",
        type=int,
        default=11113
    )
    store_group.add_argument(
        "--store-aet", metavar='[a]etitle',
        help="the AE title to use for the Storage SCP",
        type=str,
        default="STORESCP"
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

    ns = parser.parse_args()
    if ns.version:
        pass
    elif not bool(ns.file) and not bool(ns.keyword):
        parser.error('-f and/or -k must be specified')

    return ns


def handle_store(event):
    """Handle a C-STORE request."""
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

    status = Dataset()
    status.Status = 0x0000

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
        status.Status = 0x0000 # Success
    except IOError as exc:
        APP_LOGGER.error('Could not write file to specified directory:')
        APP_LOGGER.error("    {0!s}".format(os.path.dirname(filename)))
        APP_LOGGER.exception(exc)
        # Failed - Out of Resources - IOError
        status.Status = 0xA700
    except Exception as exc:
        APP_LOGGER.error('Could not write file to specified directory:')
        APP_LOGGER.error("    {0!s}".format(os.path.dirname(filename)))
        APP_LOGGER.exception(exc)
        # Failed - Out of Resources - Miscellaneous error
        status.Status = 0xA701

    return status


if __name__ == "__main__":
    args = _setup_argparser()

    if args.version:
        print('movescu.py v{}'.format(__version__))
        sys.exit()

    APP_LOGGER = setup_logging(args, 'movescu')
    APP_LOGGER.debug('movescu.py v{0!s}'.format(__version__))
    APP_LOGGER.debug('')

    # Create query (identifier) dataset
    try:
        # If you're looking at this to see how QR Get works then `identifer`
        # is a pydicom Dataset instance with your query keys, e.g.:
        #     identifier = Dataset()
        #     identifier.QueryRetrieveLevel = 'PATIENT'
        #     identifier.PatientName = '*'
        identifier = create_dataset(args, APP_LOGGER)
    except Exception as exc:
        APP_LOGGER.exception(exc)
        sys.exit(1)

    # Create application entity
    # Binding to port 0 lets the OS pick an available port
    ae = AE()

    # Start the Store SCP (optional)
    scp = None
    if args.store:
        transfer_syntax = ALL_TRANSFER_SYNTAXES[:]
        store_handlers = [(evt.EVT_C_STORE, handle_store)]
        ae.ae_title = args.store_aet
        for cx in AllStoragePresentationContexts:
            ae.add_supported_context(cx.abstract_syntax, transfer_syntax)

        scp = ae.start_server(
            ('', args.store_port), block=False, evt_handlers=store_handlers
        )

    ae.ae_title = args.calling_aet
    ae.acse_timeout = args.acse_timeout
    ae.dimse_timeout = args.dimse_timeout
    ae.network_timeout = args.network_timeout
    ae.requested_contexts = QueryRetrievePresentationContexts

    # Query/Retrieve Information Models
    if args.study:
        query_model = StudyRootQueryRetrieveInformationModelMove
    elif args.psonly:
        query_model = PatientStudyOnlyQueryRetrieveInformationModelMove
    else:
        query_model = PatientRootQueryRetrieveInformationModelMove

    # Request association with remote AE
    assoc = ae.associate(
        args.addr, args.port, ae_title=args.called_aet, max_pdu=args.max_pdu
    )
    if assoc.is_established:
        # Send query
        move_aet = args.move_aet or args.calling_aet
        responses = assoc.send_c_move(identifier, move_aet, query_model)
        for (status, rsp_identifier) in responses:
            # If `status.Status` is one of the 'Pending' statuses then
            #   `rsp_identifier` is the C-MOVE response's Identifier dataset
            if status and status.Status in [0xFF00, 0xFF01]:
                # `rsp_identifier` is a pydicom Dataset containing a query
                # response. You may want to do something interesting here...
                pass

        assoc.release()
        _EXIT_VALUE = 0
    else:
        _EXIT_VALUE = 1

    # Shutdown the Storage SCP (if used)
    if scp:
        scp.shutdown()

    sys.exit(_EXIT_VALUE)
