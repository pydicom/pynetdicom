#!/usr/bin/env python
"""An application for sending Query/Retrieve (QR) and Basic Worklist Modality
(BWM) C-FIND requests to a QR/BWM - Find SCP.

"""

import argparse
import logging
from logging.config import fileConfig
import os
import sys

from pydicom import dcmread
from pydicom.uid import (
    ExplicitVRLittleEndian, ImplicitVRLittleEndian, ExplicitVRBigEndian
)

from pynetdicom import (
    AE, QueryRetrievePresentationContexts,
    BasicWorklistManagementPresentationContexts
)
from pynetdicom.apps.common import create_dataset, setup_logging
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
        usage="findscu [options] peer port"
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
            "use level l for the logger (fatal, error, warn, info, debug, "
            "trace)"
        ),
        type=str,
        choices=['fatal', 'error', 'warn', 'info', 'debug', 'trace']
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
    qr_model.add_argument(
        "-W", "--worklist",
        help="use modality worklist information model",
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

    ns = parser.parse_args()
    if not bool(ns.file) and not bool(ns.keyword):
        parser.error('-f and/or -k must be specified')

    return ns


if __name__ == '__main__':
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
        #     identifier.PatientName = '*'
        identifier = create_dataset(args, APP_LOGGER)
    except Exception as exc:
        APP_LOGGER.exception(exc)
        sys.exit()

    # Create application entity
    # Binding to port 0 lets the OS pick an available port
    ae = AE(ae_title=args.calling_aet)
    # Set the Presentation Contexts we are requesting the Find SCP support
    ae.requested_contexts = (
        QueryRetrievePresentationContexts
        + BasicWorklistManagementPresentationContexts
    )

    # Query/Retrieve Information Models
    if args.worklist:
        query_model = ModalityWorklistInformationFind
    elif args.patient:
        query_model = PatientRootQueryRetrieveInformationModelFind
    elif args.study:
        query_model = StudyRootQueryRetrieveInformationModelFind
    elif args.psonly:
        query_model = PatientStudyOnlyQueryRetrieveInformationModelFind
    else:
        query_model = PatientRootQueryRetrieveInformationModelFind

    # Request association with (QR/BWM) Find SCP
    assoc = ae.associate(args.peer, args.port, ae_title=args.called_aet)
    if assoc.is_established:
        # Send C-FIND request, `responses` is a generator
        responses = assoc.send_c_find(identifier, query_model)
        for (status, identifier) in responses:
            # If `status.Status` is one of the 'Pending' statuses then
            #   `identifier` is the C-FIND response's Identifier dataset
            if status and status.Status in [0xFF00, 0xFF01]:
                # `identifier` is a pydicom Dataset containing a query reponse
                # You may want to do something interesting here...
                pass

        # Release the association
        assoc.release()
