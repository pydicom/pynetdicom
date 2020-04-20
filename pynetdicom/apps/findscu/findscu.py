#!/usr/bin/env python
"""A QR and BWM Find SCU application.

For sending Query/Retrieve (QR) and Basic Worklist Modality (BWM) C-FIND
requests to a QR/BWM - Find SCP.
"""

import argparse
import os
import sys

from pydicom import dcmread
from pydicom.dataset import Dataset
from pydicom.uid import (
    ExplicitVRLittleEndian, ImplicitVRLittleEndian, ExplicitVRBigEndian,
    generate_uid
)

from pynetdicom import (
    AE, QueryRetrievePresentationContexts,
    BasicWorklistManagementPresentationContexts,
    PYNETDICOM_UID_PREFIX,
    PYNETDICOM_IMPLEMENTATION_UID,
    PYNETDICOM_IMPLEMENTATION_VERSION
)
from pynetdicom.apps.common import create_dataset, setup_logging
from pynetdicom._globals import DEFAULT_MAX_LENGTH
from pynetdicom.pdu_primitives import SOPClassExtendedNegotiation
from pynetdicom.sop_class import (
    ModalityWorklistInformationFind,
    PatientRootQueryRetrieveInformationModelFind,
    StudyRootQueryRetrieveInformationModelFind,
    PatientStudyOnlyQueryRetrieveInformationModelFind,
)


__version__ = '0.2.0'


def _setup_argparser():
    """Setup the command line arguments"""
    # Description
    parser = argparse.ArgumentParser(
        description=(
            "The findscu application implements a Service Class User "
            "(SCU) for the Query/Retrieve (QR) and Basic Worklist Management "
            "(BWM) Service Classes. findscu only supports query functionality "
            "using the C-FIND message. It sends query keys to an SCP and "
            "waits for a response. The application can be used to test SCPs "
            "of the QR and BWM Service Classes."
        ),
        usage="findscu [options] addr port"
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
            "use level l for the logger (fatal, error, warn, info, debug, "
            "trace)"
        ),
        type=str,
        choices=['fatal', 'error', 'warn', 'info', 'debug', 'trace']
    )
    parser.set_defaults(log_type='v')

    # Network Options
    net_opts = parser.add_argument_group('Network Options')
    net_opts.add_argument(
        "-aet", "--calling-aet", metavar='[a]etitle',
        help="set my calling AE title (default: FINDSCU)",
        type=str,
        default='FINDSCU'
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

    # Query information model choices
    qr_group = parser.add_argument_group('Query Information Model Options')
    qr_model = qr_group.add_mutually_exclusive_group()
    qr_model.add_argument(
        "-P", "--patient",
        help="use patient root information model (default)",
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
    qr_model.add_argument(
        "-W", "--worklist",
        help="use modality worklist information model",
        action="store_true"
    )

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

    out_opts = parser.add_argument_group('Output Options')
    out_opts.add_argument(
        '-w', '--write',
        help=(
            "write the responses to file as rsp000001.dcm, rsp000002.dcm, ..."
        ),
        action="store_true"
    )

    ext_neg = parser.add_argument_group('Extended Negotiation Options')
    ext_neg.add_argument(
        '--relational-query',
        help="request the use of relational queries",
        action="store_true",
    )
    ext_neg.add_argument(
        '--dt-matching',
        help="request the use of date-time matching",
        action="store_true",
    )
    ext_neg.add_argument(
        '--fuzzy-names',
        help="request the use of fuzzy semantic matching of person names",
        action="store_true",
    )
    ext_neg.add_argument(
        '--timezone-adj',
        help="request the use of timezone query adjustment",
        action="store_true",
    )
    ext_neg.add_argument(
        '--enhanced-conversion',
        help="request the use of enhanced multi-frame image conversion",
        action="store_true",
    )

    ns = parser.parse_args()
    if ns.version:
        pass
    elif not bool(ns.file) and not bool(ns.keyword):
        parser.error('-f and/or -k must be specified')

    return ns


def get_file_meta(assoc, query_model):
    """Return a Dataset containing sufficient File Meta elements
    for conformance.
    """
    cx = assoc._get_valid_context(query_model, '', 'scu')
    file_meta = Dataset()
    file_meta.TransferSyntaxUID = cx.transfer_syntax[0]
    file_meta.MediaStorageSOPClassUID = query_model
    file_meta.MediaStorageSOPInstanceUID = generate_uid(
        prefix=PYNETDICOM_UID_PREFIX
    )
    file_meta.ImplementationClassUID = PYNETDICOM_IMPLEMENTATION_UID
    file_meta.ImplementationVersionName = PYNETDICOM_IMPLEMENTATION_VERSION

    return file_meta


def generate_filename():
    """Return a `str` filename for extracted C-FIND responses."""
    ii = 1
    while True:
        yield 'rsp{:06d}.dcm'.format(ii)
        ii += 1


def main(args=None):
    """Run the application."""
    if args is not None:
        sys.argv = args

    args = _setup_argparser()

    if args.version:
        print('findscu.py v{}'.format(__version__))
        sys.exit()

    APP_LOGGER = setup_logging(args, 'findscu')
    APP_LOGGER.debug('findscu.py v{0!s}'.format(__version__))
    APP_LOGGER.debug('')

    # Create query (identifier) dataset
    try:
        # If you're looking at this to see how QR Find works then `identifer`
        # is a pydicom Dataset instance with your query keys, e.g.:
        #     identifier = Dataset()
        #     identifier.QueryRetrieveLevel = 'PATIENT'
        #     identifier.PatientName = ''
        identifier = create_dataset(args, APP_LOGGER)
    except Exception as exc:
        APP_LOGGER.exception(exc)
        raise exc
        sys.exit(1)

    # Create application entity
    # Binding to port 0 lets the OS pick an available port
    ae = AE(ae_title=args.calling_aet)

    # Set timeouts
    ae.acse_timeout = args.acse_timeout
    ae.dimse_timeout = args.dimse_timeout
    ae.network_timeout = args.network_timeout

    # Set the Presentation Contexts we are requesting the Find SCP support
    ae.requested_contexts = (
        QueryRetrievePresentationContexts
        + BasicWorklistManagementPresentationContexts
    )

    # Query/Retrieve Information Models
    if args.worklist:
        query_model = ModalityWorklistInformationFind
    elif args.study:
        query_model = StudyRootQueryRetrieveInformationModelFind
    elif args.psonly:
        query_model = PatientStudyOnlyQueryRetrieveInformationModelFind
    else:
        query_model = PatientRootQueryRetrieveInformationModelFind

    # Extended Negotiation
    ext_neg = []
    ext_opts = [
        args.relational_query, args.dt_matching, args.fuzzy_names,
        args.timezone_adj, args.enhanced_conversion
    ]
    if not args.worklist and any(ext_opts):
        app_info = b''
        for option in ext_opts:
            app_info += b'\x01' if option else b'\x00'

        item = SOPClassExtendedNegotiation()
        item.sop_class_uid = query_model
        item.service_class_application_information = app_info
        ext_neg = [item]
    elif args.worklist and any([args.fuzzy_names, args.timezone_adj]):
        app_info = b'\x01\x01'
        for option in [args.fuzzy_names, args.timezone_adj]:
            app_info += b'\x01' if option else b'\x00'

        item = SOPClassExtendedNegotiation()
        item.sop_class_uid = query_model
        item.service_class_application_information = app_info
        ext_neg = [item]

    # Request association with (QR/BWM) Find SCP
    assoc = ae.associate(
        args.addr, args.port, ae_title=args.called_aet, max_pdu=args.max_pdu,
        ext_neg=ext_neg
    )
    if assoc.is_established:
        # Send C-FIND request, `responses` is a generator
        responses = assoc.send_c_find(identifier, query_model)
        # Used to generate filenames if args.write used
        fname = generate_filename()
        for (status, rsp_identifier) in responses:
            # If `status.Status` is one of the 'Pending' statuses then
            #   `rsp_identifier` is the C-FIND response's Identifier dataset
            if status and status.Status in [0xFF00, 0xFF01]:
                if args.write:
                    rsp_identifier.file_meta = get_file_meta(
                        assoc, query_model
                    )
                    rsp_identifier.save_as(
                        next(fname), write_like_original=False
                    )

        # Release the association
        assoc.release()
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
