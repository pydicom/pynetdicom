#!/usr/bin/env python

"""
    A dcmtk style movescu application

    Used for
"""

import argparse
import logging
from logging.config import fileConfig
import os
import socket
import sys
import time

from pydicom.dataset import Dataset
from pydicom.uid import (
    ExplicitVRLittleEndian, ImplicitVRLittleEndian, ExplicitVRBigEndian
)

from pynetdicom import (
    AE, evt,
    QueryRetrievePresentationContexts,
    StoragePresentationContexts,
    PYNETDICOM_IMPLEMENTATION_VERSION,
    PYNETDICOM_IMPLEMENTATION_UID
)
from pynetdicom.sop_class import (
    PatientRootQueryRetrieveInformationModelMove,
    StudyRootQueryRetrieveInformationModelMove,
    PatientStudyOnlyQueryRetrieveInformationModelMove,
)


VERSION = '0.3.2'


def _setup_argparser():
    """Setup the command line arguments"""
    # Description
    parser = argparse.ArgumentParser(
        description="The movescu application implements a Service Class User "
                    "(SCU) for the Query/Retrieve (QR) Service Class and "
                    "(optionally) a Storage SCP for the Storage Service "
                    "Class. movescu "
                    "supports retrieve functionality using the C-MOVE "
                    "message. It sends query keys to an SCP and waits for a "
                    "response. It will accept associations for the purpose of "
                    "receiving images sent as a result of the C-MOVE request. "
                    "The application can be used to test SCPs of the "
                    "QR Service Classes. movescu can initiate the transfer of "
                    "images to a third party or can retrieve images to itself "
                    "(note: the use of the term 'move' is a misnomer, the "
                    "C-MOVE operation performs a SOP Instance copy only)",
        usage="movescu [options] peer port dcmfile-in")

    # Parameters
    req_opts = parser.add_argument_group('Parameters')
    req_opts.add_argument("peer", help="hostname of DICOM peer", type=str)
    req_opts.add_argument("port", help="TCP/IP port number of peer", type=int)
    req_opts.add_argument("dcmfile_in",
                          metavar="dcmfile-in",
                          help="DICOM query file(s)",
                          type=str)

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
                          help="set my calling AE title (default: MOVESCU)",
                          type=str,
                          default='MOVESCU')
    net_opts.add_argument("-aec", "--called-aet", metavar='[a]etitle',
                          help="set called AE title of peer (default: ANY-SCP)",
                          type=str,
                          default='ANY-SCP')
    net_opts.add_argument("-aem", "--move-aet", metavar='[a]etitle',
                          help="set move destination AE title (default: "
                                "MOVESCP)",
                          type=str,
                          default='MOVESCP')

    # Query information model choices
    qr_group = parser.add_argument_group('Query Information Model Options')
    qr_model = qr_group.add_mutually_exclusive_group()
    qr_model.add_argument("-P", "--patient",
                          help="use patient root information model",
                          action="store_true")
    qr_model.add_argument("-S", "--study",
                          help="use study root information model",
                          action="store_true")
    qr_model.add_argument("-O", "--psonly",
                          help="use patient/study only information model",
                          action="store_true")

    # Store SCP options
    store_group = parser.add_argument_group('Storage SCP Options')
    store_group.add_argument("--store",
                             help=(
                                "start a Storage SCP that can be used as "
                                "the move destination"
                             ),
                             action="store_true",
                             default=False)
    store_group.add_argument("--store-port",
                             help="the port number to use for the Storage SCP",
                             type=int,
                             default=11113)
    store_group.add_argument("--store_aet",
                             help="the AE title to use for the Storage SCP",
                             type=str,
                             default="STORESCP")

    # Output Options
    out_opts = parser.add_argument_group('Output Options')
    out_opts.add_argument('-od', "--output-directory", metavar="[d]irectory",
                          help="write received objects to existing directory d",
                          type=str)

    # Miscellaneous
    misc_opts = parser.add_argument_group('Miscellaneous')
    misc_opts.add_argument('--ignore',
                           help="receive data but don't store it",
                           action="store_true")

    return parser.parse_args()

args = _setup_argparser()

# Logging/Output
def setup_logger():
    """Setup the echoscu logging"""
    logger = logging.Logger('movescu')
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(levelname).1s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.ERROR)

    return logger

APP_LOGGER = setup_logger()

def _setup_logging(level):
    APP_LOGGER.setLevel(level)
    pynetdicom_logger = logging.getLogger('pynetdicom')
    handler = logging.StreamHandler()
    pynetdicom_logger.setLevel(level)
    formatter = logging.Formatter('%(levelname).1s: %(message)s')
    handler.setFormatter(formatter)
    pynetdicom_logger.addHandler(handler)

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

APP_LOGGER.debug('$movescu.py v{0!s}'.format(VERSION))
APP_LOGGER.debug('')

# Create application entity
# Binding to port 0 lets the OS pick an available port
ae = AE()


# Start the Store SCP (optional)
scp = None
if args.store:
    def handle_store(event):
        """Handle a C-STORE request."""
        if args.ignore:
            return 0x0000

        mode_prefixes = {
            'CT Image Storage' : 'CT',
            'Enhanced CT Image Storage' : 'CTE',
            'MR Image Storage' : 'MR',
            'Enhanced MR Image Storage' : 'MRE',
            'Positron Emission Tomography Image Storage' : 'PT',
            'Enhanced PET Image Storage' : 'PTE',
            'RT Image Storage' : 'RI',
            'RT Dose Storage' : 'RD',
            'RT Plan Storage' : 'RP',
            'RT Structure Set Storage' : 'RS',
            'Computed Radiography Image Storage' : 'CR',
            'Ultrasound Image Storage' : 'US',
            'Enhanced Ultrasound Image Storage' : 'USE',
            'X-Ray Angiographic Image Storage' : 'XA',
            'Enhanced XA Image Storage' : 'XAE',
            'Nuclear Medicine Image Storage' : 'NM',
            'Secondary Capture Image Storage' : 'SC'
        }

        ds = event.dataset

        # Because pydicom uses deferred reads for its decoding, decoding errors
        #   are hidden until encountered by accessing a faulty element
        try:
            sop_class = ds.SOPClassUID
            sop_instance = ds.SOPInstanceUID
        except Exception as exc:
            # Unable to decode dataset
            return 0xC210

        try:
            # Get the elements we need
            mode_prefix = mode_prefixes[sop_class.name]
        except KeyError:
            mode_prefix = 'UN'

        filename = '{0!s}.{1!s}'.format(mode_prefix, sop_instance)
        APP_LOGGER.info('Storing DICOM file: {0!s}'.format(filename))

        if os.path.exists(filename):
            APP_LOGGER.warning('DICOM file already exists, overwriting')

        # Presentation context
        cx = event.context

        ## DICOM File Format - File Meta Information Header
        # If a DICOM dataset is to be stored in the DICOM File Format then the
        # File Meta Information Header is required. At a minimum it requires:
        #   * (0002,0000) FileMetaInformationGroupLength, UL, 4
        #   * (0002,0001) FileMetaInformationVersion, OB, 2
        #   * (0002,0002) MediaStorageSOPClassUID, UI, N
        #   * (0002,0003) MediaStorageSOPInstanceUID, UI, N
        #   * (0002,0010) TransferSyntaxUID, UI, N
        #   * (0002,0012) ImplementationClassUID, UI, N
        # (from the DICOM Standard, Part 10, Section 7.1)
        # Of these, we should update the following as pydicom will take care of
        #   the remainder
        meta = Dataset()
        meta.MediaStorageSOPClassUID = sop_class
        meta.MediaStorageSOPInstanceUID = sop_instance
        meta.ImplementationClassUID = PYNETDICOM_IMPLEMENTATION_UID
        meta.TransferSyntaxUID = cx.transfer_syntax

        # The following is not mandatory, set for convenience
        meta.ImplementationVersionName = PYNETDICOM_IMPLEMENTATION_VERSION

        ds.file_meta = meta
        ds.is_little_endian = cx.transfer_syntax.is_little_endian
        ds.is_implicit_VR = cx.transfer_syntax.is_implicit_VR

        status_ds = Dataset()
        status_ds.Status = 0x0000

        # Try to save to output-directory
        if args.output_directory is not None:
            filename = os.path.join(args.output_directory, filename)

        try:
            # We use `write_like_original=False` to ensure that a compliant
            #   File Meta Information Header is written
            ds.save_as(filename, write_like_original=False)
            status_ds.Status = 0x0000 # Success
        except IOError:
            APP_LOGGER.error('Could not write file to specified directory:')
            APP_LOGGER.error("    {0!s}".format(os.path.dirname(filename)))
            APP_LOGGER.error('Directory may not exist or you may not have write '
                         'permission')
            # Failed - Out of Resources - IOError
            status_ds.Status = 0xA700
        except:
            APP_LOGGER.error('Could not write file to specified directory:')
            APP_LOGGER.error("    {0!s}".format(os.path.dirname(filename)))
            # Failed - Out of Resources - Miscellaneous error
            status_ds.Status = 0xA701

        return status_ds

    store_handlers = [(evt.EVT_C_STORE, handle_store)]

    ae.ae_title = args.store_aet
    ae.supported_contexts = StoragePresentationContexts
    scp = ae.start_server(('', args.store_port),
                          block=False,
                          evt_handlers=store_handlers)

ae.ae_title = args.calling_aet
ae.requested_contexts = QueryRetrievePresentationContexts


# Request association with remote AE
assoc = ae.associate(args.peer, args.port, ae_title=args.called_aet)

if assoc.is_established:
    # Create query dataset
    ds = Dataset()
    ds.PatientName = '*'
    ds.QueryRetrieveLevel = "PATIENT"

    if args.patient:
        query_model = PatientRootQueryRetrieveInformationModelMove
    elif args.study:
        query_model = StudyRootQueryRetrieveInformationModelMove
    elif args.psonly:
        query_model = PatientStudyOnlyQueryRetrieveInformationModelMove
    else:
        query_model = PatientRootQueryRetrieveInformationModelMove

    if args.move_aet:
        move_aet = args.move_aet
    else:
        move_aet = args.calling_aet

    # Send query
    response = assoc.send_c_move(ds, move_aet, query_model)

    for (status, identifier) in response:
        pass

    assoc.release()

# Shutdown the Storage SCP (if used)
if scp:
    scp.shutdown()
