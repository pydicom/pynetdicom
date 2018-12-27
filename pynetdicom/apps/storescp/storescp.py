#!/usr/bin/env python
"""An implementation of a Storage Service Class Provider (Storage SCP)."""

import argparse
import logging
import os
import socket
import sys

from pydicom.dataset import Dataset
from pydicom.uid import (
    ExplicitVRLittleEndian,
    ImplicitVRLittleEndian,
    ExplicitVRBigEndian,
    DeflatedExplicitVRLittleEndian
)

from pynetdicom import (
    AE,
    StoragePresentationContexts,
    VerificationPresentationContexts,
    PYNETDICOM_IMPLEMENTATION_UID,
    PYNETDICOM_IMPLEMENTATION_VERSION
)


def setup_logger():
    """Setup the logger"""
    logger = logging.Logger('storescp')
    stream_logger = logging.StreamHandler()
    formatter = logging.Formatter('%(levelname).1s: %(message)s')
    stream_logger.setFormatter(formatter)
    logger.addHandler(stream_logger)
    logger.setLevel(logging.ERROR)

    return logger


LOGGER = setup_logger()
VERSION = '0.3.3'


def _setup_argparser():
    """Setup the command line arguments"""
    # Description
    parser = argparse.ArgumentParser(
        description="The storescp application implements a Service Class "
                    "Provider (SCP) for the Storage SOP Class. It listens "
                    "for a DICOM C-STORE message from a Service Class User "
                    "(SCU) and stores the resulting DICOM dataset.",
        usage="storescp [options] port")

    # Parameters
    req_opts = parser.add_argument_group('Parameters')
    req_opts.add_argument("port",
                          help="TCP/IP port number to listen on",
                          type=int)
    req_opts.add_argument("--bind_addr",
                          help="The IP address of the network interface to "
                          "listen on. If unset, listen on all interfaces.",
                          default='')

    # General Options
    gen_opts = parser.add_argument_group('General Options')
    gen_opts.add_argument("--version",
                          help="print version information and exit",
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

    # Network Options
    net_opts = parser.add_argument_group('Network Options')
    net_opts.add_argument("-aet", "--aetitle", metavar='[a]etitle',
                          help="set my AE title (default: STORESCP)",
                          type=str,
                          default='STORESCP')
    net_opts.add_argument("-to", "--timeout", metavar='[s]econds',
                          help="timeout for connection requests",
                          type=int,
                          default=None)
    net_opts.add_argument("-ta", "--acse-timeout", metavar='[s]econds',
                          help="timeout for ACSE messages",
                          type=int,
                          default=30)
    net_opts.add_argument("-td", "--dimse-timeout", metavar='[s]econds',
                          help="timeout for DIMSE messages",
                          type=int,
                          default=None)
    net_opts.add_argument("-pdu", "--max-pdu", metavar='[n]umber of bytes',
                          help="set max receive pdu to n bytes (4096..131072)",
                          type=int,
                          default=16384)

    # Transfer Syntaxes
    ts_opts = parser.add_argument_group('Preferred Transfer Syntaxes')
    ts_opts.add_argument("-x=", "--prefer-uncompr",
                         help="prefer explicit VR local byte order (default)",
                         action="store_true")
    ts_opts.add_argument("-xe", "--prefer-little",
                         help="prefer explicit VR little endian TS",
                         action="store_true")
    ts_opts.add_argument("-xb", "--prefer-big",
                         help="prefer explicit VR big endian TS",
                         action="store_true")
    ts_opts.add_argument("-xi", "--implicit",
                         help="accept implicit VR little endian TS only",
                         action="store_true")

    # Output Options
    out_opts = parser.add_argument_group('Output Options')
    out_opts.add_argument('-od', "--output-directory", metavar="[d]irectory",
                          help="write received objects to existing directory d",
                          type=str)
    """
    out_opts.add_argument('-su', "--sort-on-study-uid",
                          help="sort studies into subdirectories using "
                                "Study Instance UID",
                          action="store_true")
    out_opts.add_argument('-su', "--sort-on-patient-id",
                          help="sort studies into subdirectories using "
                                "Patient ID and a timestamp",
                          action="store_true")
    out_opts.add_argument('-uf', "--default-filenames",
                          help="generate filenames from instance UID",
                          action="store_true",
                          default=True)
    """
    """
    # Event Options
    event_opts = parser.add_argument_group('Event Options')
    event_opts.add_argument('-xcr', "--exec-on-reception",
                            metavar="[c]ommand",
                            help="execute command c after receiving and "
                                "processing one C-STORE-RQ message",
                            type=str)
    """

    # Miscellaneous
    misc_opts = parser.add_argument_group('Miscellaneous')
    misc_opts.add_argument('--ignore',
                           help="receive data but don't store it",
                           action="store_true")

    return parser.parse_args()


args = _setup_argparser()

if args.verbose:
    LOGGER.setLevel(logging.INFO)
    pynetdicom_logger = logging.getLogger('pynetdicom')
    pynetdicom_logger.setLevel(logging.INFO)

if args.debug:
    LOGGER.setLevel(logging.DEBUG)
    pynetdicom_logger = logging.getLogger('pynetdicom')
    pynetdicom_logger.setLevel(logging.DEBUG)

LOGGER.debug('$storescp.py v{0!s}'.format(VERSION))
LOGGER.debug('')

# Validate port
if isinstance(args.port, int):
    test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        test_socket.bind((os.popen('hostname').read()[:-1], args.port))
    except socket.error:
        LOGGER.error("Cannot listen on port {0:d}, insufficient priveleges".format(args.port))
        sys.exit()

# Set Transfer Syntax options
transfer_syntax = [ImplicitVRLittleEndian,
                   ExplicitVRLittleEndian,
                   DeflatedExplicitVRLittleEndian,
                   ExplicitVRBigEndian]

if args.prefer_uncompr and ImplicitVRLittleEndian in transfer_syntax:
    transfer_syntax.remove(ImplicitVRLittleEndian)
    transfer_syntax.append(ImplicitVRLittleEndian)

if args.implicit:
    transfer_syntax = [ImplicitVRLittleEndian]

if args.prefer_little and ExplicitVRLittleEndian in transfer_syntax:
    transfer_syntax.remove(ExplicitVRLittleEndian)
    transfer_syntax.insert(0, ExplicitVRLittleEndian)

if args.prefer_big and ExplicitVRBigEndian in transfer_syntax:
    transfer_syntax.remove(ExplicitVRBigEndian)
    transfer_syntax.insert(0, ExplicitVRBigEndian)


def on_c_store(ds, context, info):
    """Store the pydicom Dataset `ds` in the DICOM File Format.

    Parameters
    ----------
    ds : pydicom.Dataset
        The DICOM dataset sent in the C-STORE request.
    context : pynetdicom.presentation.PresentationContextTuple
        Details of the presentation context the dataset was sent under.
    info : dict
        A dict containing information about the association and DIMSE message.

    Returns
    -------
    status : pynetdicom.sop_class.Status or int
        A valid return status code, see PS3.4 Annex B.2.3 or the
        StorageServiceClass implementation for the available statuses
    """
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

    try:
        mode_prefix = mode_prefixes[ds.SOPClassUID.name]
    except KeyError:
        mode_prefix = 'UN'

    filename = '{0!s}.{1!s}'.format(mode_prefix, ds.SOPInstanceUID)
    LOGGER.info('Storing DICOM file: {0!s}'.format(filename))

    if os.path.exists(filename):
        LOGGER.warning('DICOM file already exists, overwriting')

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
    meta.MediaStorageSOPClassUID = ds.SOPClassUID
    meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
    meta.ImplementationClassUID = PYNETDICOM_IMPLEMENTATION_UID
    meta.TransferSyntaxUID = context.transfer_syntax

    # The following is not mandatory, set for convenience
    meta.ImplementationVersionName = PYNETDICOM_IMPLEMENTATION_VERSION

    ds.file_meta = meta
    ds.is_little_endian = context.transfer_syntax.is_little_endian
    ds.is_implicit_VR = context.transfer_syntax.is_implicit_VR

    status_ds = Dataset()
    status_ds.Status = 0x0000

    if not args.ignore:
        # Try to save to output-directory
        if args.output_directory is not None:
            filename = os.path.join(args.output_directory, filename)

        try:
            # We use `write_like_original=False` to ensure that a compliant
            #   File Meta Information Header is written
            ds.save_as(filename, write_like_original=False)
            status_ds.Status = 0x0000 # Success
        except IOError:
            LOGGER.error('Could not write file to specified directory:')
            LOGGER.error("    {0!s}".format(os.path.dirname(filename)))
            LOGGER.error('Directory may not exist or you may not have write '
                         'permission')
            # Failed - Out of Resources - IOError
            status_ds.Status = 0xA700
        except:
            LOGGER.error('Could not write file to specified directory:')
            LOGGER.error("    {0!s}".format(os.path.dirname(filename)))
            # Failed - Out of Resources - Miscellaneous error
            status_ds.Status = 0xA701

    return status_ds

# Test output-directory
if args.output_directory is not None:
    if not os.access(args.output_directory, os.W_OK|os.X_OK):
        LOGGER.error('No write permissions or the output '
                     'directory may not exist:')
        LOGGER.error("    {0!s}".format(args.output_directory))
        sys.exit()

# Create application entity
ae = AE(ae_title=args.aetitle, port=args.port)

ae.bind_addr = args.bind_addr

# Add presentation contexts with specified transfer syntaxes
for context in StoragePresentationContexts:
    ae.add_supported_context(context.abstract_syntax, transfer_syntax)
for context in VerificationPresentationContexts:
    ae.add_supported_context(context.abstract_syntax, transfer_syntax)

ae.maximum_pdu_size = args.max_pdu

# Set timeouts
ae.network_timeout = args.timeout
ae.acse_timeout = args.acse_timeout
ae.dimse_timeout = args.dimse_timeout

ae.on_c_store = on_c_store

ae.start()
