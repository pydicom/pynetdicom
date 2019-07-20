#!/usr/bin/env python

"""
A findscu application.

"ScheduledProcedureStepSequence[0].Modality=CT"
"ScheduledProcedureStepSequence[0].BeamSequence[0].BeamName=Beam1"
"(0010,0010)='SOME VALUE'"
"PatientID='12345678'"
"(0020,0020)=12345"
"(0020,0020)="

{sequence[item-number].}*element

TODO: use regex instead

BWM:
ds = Dataset()
ds.PatientName = '*'
ds.ScheduledProcedureStepSequence = [Dataset()]
item = ds.ScheduledProcedureStepSequence[0]
item.ScheduledStationAETitle = 'CTSCANNER'
item.ScheduledProcedureStepStartDate = '20181005'
item.Modality = 'CT'

Interpret unknown VR as bytes
"""

import argparse
import logging
from logging.config import fileConfig
import os
import sys

from pydicom import dcmread
from pydicom.dataset import Dataset
from pydicom.datadict import tag_for_keyword, get_entry
from pydicom.tag import Tag
from pydicom.uid import (
    ExplicitVRLittleEndian, ImplicitVRLittleEndian, ExplicitVRBigEndian
)

from pynetdicom import (
    AE,
    QueryRetrievePresentationContexts,
    BasicWorklistManagementPresentationContexts
)
from pynetdicom.sop_class import (
    ModalityWorklistInformationFind,
    PatientRootQueryRetrieveInformationModelFind,
    StudyRootQueryRetrieveInformationModelFind,
    PatientStudyOnlyQueryRetrieveInformationModelFind,
)


VERSION = '0.2.0'


def _setup_argparser():
    """Setup the command line arguments"""
    # Description
    parser = argparse.ArgumentParser(
        description="The findscu application implements a Service Class User "
                    "(SCU) for the Query/Retrieve (QR) Service Class and the "
                    "Basic Worklist Management (BWM) Service Class. findscu "
                    "only supports query functionality using the C-FIND "
                    "message. It sends query keys to an SCP and waits for a "
                    "response. The application can be used to test SCPs of the "
                    "QR and BWM Service Classes.",
        usage="findscu [options] peer port")

    # Parameters
    req_opts = parser.add_argument_group('Parameters')
    req_opts.add_argument("peer", help="hostname of DICOM peer", type=str)
    req_opts.add_argument("port", help="TCP/IP port number of peer", type=int)

    # General Options
    gen_opts = parser.add_argument_group('General Options')
    gen_opts.add_argument("--version",
                          help="print version information and exit",
                          action="store_true")
    gen_opts.add_argument("--arguments",
                          help="print expanded command line arguments",
                          action="store_true")
    gen_opts.add_argument("-q", "--quiet",
                          help="quiet mode, print no warnings and errors",
                          action="store_true")
    gen_opts.add_argument("-v", "--verbose",
                          help="verbose mode, print processing details",
                          action="store_true")
    gen_opts.add_argument("-d", "--debug",
                          help="debug mode, print debug information",
                          action="store_true")
    gen_opts.add_argument("-ll", "--log-level", metavar='[l]',
                          help="use level l for the logger (fatal, error, warn, "
                               "info, debug, trace)",
                          type=str,
                          choices=['fatal', 'error', 'warn',
                                   'info', 'debug', 'trace'])
    gen_opts.add_argument("-lc", "--log-config", metavar='[f]',
                          help="use config file f for the logger",
                          type=str)

    # Network Options
    net_opts = parser.add_argument_group('Network Options')
    net_opts.add_argument("-aet", "--calling-aet", metavar='[a]etitle',
                          help="set my calling AE title (default: FINDSCU)",
                          type=str,
                          default='FINDSCU')
    net_opts.add_argument("-aec", "--called-aet", metavar='[a]etitle',
                          help="set called AE title of peer (default: ANY-SCP)",
                          type=str,
                          default='ANY-SCP')

    # Query information model choices
    qr_group = parser.add_argument_group('Query Information Model Options')
    qr_model = qr_group.add_mutually_exclusive_group()
    qr_model.add_argument("-W", "--worklist",
                          help="use modality worklist information model",
                          action="store_true")
    qr_model.add_argument("-P", "--patient",
                          help="use patient root information model",
                          action="store_true")
    qr_model.add_argument("-S", "--study",
                          help="use study root information model",
                          action="store_true")
    qr_model.add_argument("-O", "--psonly",
                          help="use patient/study only information model",
                          action="store_true")

    qr_query = parser.add_argument_group('Query Options')
    qr_query.add_argument(
        '-k', '--keyword',
        metavar='[k]eyword: gggg,eeee="str", keyword="str"',
        help=(
            "add or override a query element using either an element tag as "
            "group,element or the element's keyword (such as PatientName)",
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


# Logging/Output
def setup_logger():
    """Setup the findscu logger."""
    logger = logging.Logger('findscu')
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(levelname).1s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.ERROR)

    return logger

def _setup_logging(level):
    """Setup the pynetdicom logger."""
    APP_LOGGER.setLevel(level)
    pynetdicom_logger = logging.getLogger('pynetdicom')
    handler = logging.StreamHandler()
    pynetdicom_logger.setLevel(level)
    formatter = logging.Formatter('%(levelname).1s: %(message)s')
    handler.setFormatter(formatter)
    pynetdicom_logger.addHandler(handler)

def _dev_setup_logging(args):

    if args.quiet:
        for hh in APP_LOGGER.handlers:
            APP_LOGGER.removeHandler(hh)

        APP_LOGGER.addHandler(logging.NullHandler())

    if args.verbose:
        _setup_logging(logging.INFO)

    if args.debug:
        _setup_logging(logging.DEBUG)

    if args.log_level:
        levels = {'critical' : logging.CRITICAL,
                  'error'    : logging.ERROR,
                  'warn'     : logging.WARNING,
                  'info'     : logging.INFO,
                  'debug'    : logging.DEBUG}
        _setup_logging(levels[args.log_level])

    if args.log_config:
        fileConfig(args.log_config)


def create_query(args):
    """
    """
    query = Dataset()

    # Import query dataset
    if args.file:
        # Check file exists and is readable and DICOM
        try:
            with open(args.file, 'rb') as fp:
                query = dcmread(fp, force=True)
                # Only way to check for a bad decode is to iterate the dataset
                query.iterall()
        except IOError as exc:
            APP_LOGGER.error(
                'Unable to read the file: {}'.format(args.file)
            )
            APP_LOGGER.exception(exc)
            sys.exit()
        except Exception as exc:
            APP_LOGGER.error(
                'Exception raised decoding the file, the file may be '
                'corrupt, non-conformant or may not be DICOM {}'
                .format(args.file)
            )
            APP_LOGGER.exception(exc)
            sys.exit()

    if args.keyword:
        _VR_STR = [
            'AE', 'AS', 'AT', 'CS', 'DA', 'DS', 'DT', 'IS', 'LO', 'LT',
            'PN', 'SH', 'ST', 'TM', 'UC', 'UI', 'UR', 'UT'
        ]
        _VR_INT = ['SL', 'SS', 'UL', 'US']
        _VR_FLOAT = ['FD', 'FL', ]
        _VR_BYTE = ['OB', 'OD', 'OF', 'OL', 'OW', 'OV', 'UN', ]
        for kw in args.keyword:
            # Only split at the first occurrence
            tag, value = kw.split('=', 1)

            components = tag.split(',', 1)
            if len(components) == 2:
                # Element tag
                tag = Tag(components)
            elif len(components) == 1:
                # Element keyword
                tag = Tag(tag_for_keyword(components[0]))
            else:
                APP_LOGGER.error("Unable to parse '{}'".format(kw))

            vr, vm, name, is_retired, keyword = get_entry(tag)

            # Try to convert value to appropriate type
            try:
                if vr in _VR_STR:
                    pass
                elif vr in _VR_INT and value:
                    value = int(value)
                elif vr in _VR_FLOAT and value:
                    value = float(value)
            except Exception as exc:
                APP_LOGGER.error(
                    "Unable to convert the value '{}' for element {} with VR "
                    "{} to an appropriate type"
                    .format(value, tag, entry[0])
                )
                APP_LOGGER.exception(exc)
                continue

            query.add_new(tag, vr, value)

    return query


if __name__ == '__main__':
    args = _setup_argparser()

    APP_LOGGER = setup_logger()
    _dev_setup_logging(args)

    APP_LOGGER.debug('$findscu.py v{0!s}'.format(VERSION))
    APP_LOGGER.debug('')

    # Create query (identifier) dataset
    identifier = create_query(args)

    # Create application entity
    # Binding to port 0 lets the OS pick an available port
    ae = AE(ae_title=args.calling_aet)
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

    # Request association with remote
    assoc = ae.associate(args.peer, args.port, ae_title=args.called_aet)

    if assoc.is_established:
        # Send query, yields (status, identifier)
        # If `status` is one of the 'Pending' statuses then `identifier` is the
        #   C-FIND response's Identifier dataset, otherwise `identifier` is None
        responses = assoc.send_c_find(identifier, query_model)
        for status, ds in responses:
            if status and status.Status in [0xFF00, 0xFF01]:
                # Pending responses should return matching datasets
                pass

        assoc.release()
