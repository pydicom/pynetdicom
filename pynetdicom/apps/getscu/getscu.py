#!/usr/bin/env python

"""
    A getscu application.
"""

import argparse
import logging
from logging.config import fileConfig
import os
import socket
import sys
import time

from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import (
    ExplicitVRLittleEndian, ImplicitVRLittleEndian, ExplicitVRBigEndian
)

from pynetdicom import (
    AE, build_role, evt,
    StoragePresentationContexts,
    QueryRetrievePresentationContexts,
    PYNETDICOM_IMPLEMENTATION_UID,
    PYNETDICOM_IMPLEMENTATION___version__
)
from pynetdicom.apps.common import (
    setup_logging, create_dataset, SOP_CLASS_PREFIXES
)
from pynetdicom.sop_class import (
    PatientRootQueryRetrieveInformationModelGet,
    StudyRootQueryRetrieveInformationModelGet,
    PatientStudyOnlyQueryRetrieveInformationModelGet,
)


__version__ = '0.4.0'


def _setup_argparser():
    """Setup the command line arguments"""
    # Description
    parser = argparse.ArgumentParser(
        description=(
            "The getscu application implements a Service Class User "
            "(SCU) for the Query/Retrieve (QR) Service Class. getscu only "
            "supports query functionality using the C-GET message. It sends "
            "query keys to an SCP and waits for a response. The application "
            "can be used to test SCPs of the QR Service Class."
        ),
        usage="getscu [options] peer port"
    )

    # Parameters
    req_opts = parser.add_argument_group('Parameters')
    req_opts.add_argument("peer", help="hostname of DICOM peer", type=str)
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
        help="set my calling AE title (default: GETSCU)",
        type=str,
        default='GETSCU'
    )
    net_opts.add_argument(
        "-aec", "--called-aet", metavar='[a]etitle',
        help="set called AE title of peer (default: ANY-SCP)",
        type=str,
        default='ANY-SCP'
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

    ns = parser.parse_args()
    if not bool(ns.file) and not bool(ns.keyword):
        parser.error('-f and/or -k must be specified')

    return ns


if __name__ == "__main__":
    args = _setup_argparser()

    if args.version:
        print('echoscu.py v{}'.format(__version__))
        sys.exit()

    APP_LOGGER = setup_logging(args, 'getscu')
    APP_LOGGER.debug('$getscu.py v{0!s}'.format(__version__))
    APP_LOGGER.debug('')

    # Create application entity
    # Binding to port 0 lets the OS pick an available port
    ae = AE(ae_title=args.calling_aet)

    for context in QueryRetrievePresentationContexts:
        ae.add_requested_context(context.abstract_syntax)
    for context in StoragePresentationContexts[:115]:
        ae.add_requested_context(context.abstract_syntax)

    # Add SCP/SCU Role Selection Negotiation to the extended negotiation
    # We want to act as a Storage SCP
    ext_neg = []
    for context in StoragePresentationContexts:
        ext_neg.append(build_role(context.abstract_syntax, scp_role=True))

    if args.patient:
        query_model = PatientRootQueryRetrieveInformationModelGet
    elif args.study:
        query_model = StudyRootQueryRetrieveInformationModelGet
    elif args.psonly:
        query_model = PatientStudyOnlyQueryRetrieveInformationModelGet
    else:
        query_model = PatientRootQueryRetrieveInformationModelGet

    def handle_store(event):
        """Handle a C-STORE request."""
        if args.ignore:
            return 0x0000

        ds = event.dataset
        # Remove any Group 0x0002 elements that may have been included
        ds = ds[0x00030000:]

        # Add the file meta information elements
        ds.file_meta = event.file_meta
        ds.is_little_endian = ds.file_meta.TransferSyntaxUID.is_little_endian
        ds.is_implicit_VR = ds.file_meta.TransferSyntaxUID.is_implicit_VR

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
            mode_prefix = SOP_CLASS_PREFIXES[sop_class]
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

    handlers = [(evt.EVT_C_STORE, handle_store)]

    # Request association with remote
    assoc = ae.associate(args.peer,
                         args.port,
                         ae_title=args.called_aet,
                         ext_neg=ext_neg,
                         evt_handlers=handlers)

    # Send query
    if assoc.is_established:
        response = assoc.send_c_get(d, query_model)

        for status, identifier in response:
            pass

        assoc.release()
