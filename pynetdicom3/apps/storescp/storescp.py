#!/usr/bin/env python

"""
    A dcmtk style storescp application.

    Used as a SCP for sending DICOM objects to
"""

import argparse
import logging
import os
import socket
import sys

from pydicom.dataset import Dataset, FileDataset
from pydicom.filewriter import write_file
from pydicom.uid import ExplicitVRLittleEndian, ImplicitVRLittleEndian, \
    ExplicitVRBigEndian, DeflatedExplicitVRLittleEndian

from pynetdicom3 import AE, StorageSOPClassList, VerificationSOPClass
from pynetdicom3 import pynetdicom_uid_prefix

def setup_logger():
    logger = logging.Logger('storescp')
    stream_logger = logging.StreamHandler()
    formatter = logging.Formatter('%(levelname).1s: %(message)s')
    stream_logger.setFormatter(formatter)
    logger.addHandler(stream_logger)
    logger.setLevel(logging.ERROR)

    return logger

LOGGER = setup_logger()

def _setup_argparser():
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
    net_opts.add_argument("-aet", "--aetitle", metavar='[a]etitle',
                          help="set my AE title (default: STORESCP)",
                          type=str,
                          default='STORESCP')
    net_opts.add_argument("-to", "--timeout", metavar='[s]econds',
                          help="timeout for connection requests",
                          type=int,
                          default=0)
    net_opts.add_argument("-ta", "--acse-timeout", metavar='[s]econds',
                          help="timeout for ACSE messages",
                          type=int,
                          default=30)
    net_opts.add_argument("-td", "--dimse-timeout", metavar='[s]econds',
                          help="timeout for DIMSE messages",
                          type=int,
                          default=0)
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

if args.debug:
    LOGGER.setLevel(logging.DEBUG)
    pynetdicom_logger = logging.getLogger('pynetdicom3')
    pynetdicom_logger.setLevel(logging.DEBUG)

LOGGER.debug('$storescp.py v%s %s $' %('0.2.0', '2016-03-23'))
LOGGER.debug('')

# Validate port
if isinstance(args.port, int):
    test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        test_socket.bind((os.popen('hostname').read()[:-1], args.port))
    except socket.error:
        LOGGER.error("Cannot listen on port %d, insufficient priveleges"
            %args.port)
        sys.exit()

# Set Transfer Syntax options
transfer_syntax = [ImplicitVRLittleEndian,
                   ExplicitVRLittleEndian,
                   DeflatedExplicitVRLittleEndian,
                   ExplicitVRBigEndian]

if args.implicit:
    transfer_syntax = [ImplicitVRLittleEndian]

if args.prefer_little:
    if ExplicitVRLittleEndian in transfer_syntax:
        transfer_syntax.remove(ExplicitVRLittleEndian)
        transfer_syntax.insert(0, ExplicitVRLittleEndian)

if args.prefer_big:
    if ExplicitVRBigEndian in transfer_syntax:
        transfer_syntax.remove(ExplicitVRBigEndian)
        transfer_syntax.insert(0, ExplicitVRBigEndian)

def on_c_store(dataset):
    """
    Write `dataset` to file as little endian implicit VR

    Parameters
    ----------
    dataset - pydicom.Dataset
        The DICOM dataset sent via the C-STORE

    Returns
    -------
    status
        A valid return status code, see PS3.4 Annex B.2.3 or the
        StorageServiceClass implementation for the available statuses
    """
    mode_prefix = 'UN'
    mode_prefixes = {'CT Image Storage' : 'CT',
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
                     'Secondary Capture Image Storage' : 'SC'}

    try:
        mode_prefix = mode_prefixes[dataset.SOPClassUID.__str__()]
    except:
        pass

    filename = '%s.%s' %(mode_prefix, dataset.SOPInstanceUID)
    LOGGER.info('Storing DICOM file: %s' %filename)

    if os.path.exists(filename):
        LOGGER.warning('DICOM file already exists, overwriting')

    meta = Dataset()
    meta.MediaStorageSOPClassUID = dataset.SOPClassUID
    meta.MediaStorageSOPInstanceUID = dataset.SOPInstanceUID
    meta.ImplementationClassUID = pynetdicom_uid_prefix

    ds = FileDataset(filename, {}, file_meta=meta, preamble=b"\0" * 128)
    ds.update(dataset)

    ds.is_little_endian = True
    ds.is_implicit_VR = True

    if not args.ignore:
        # Try to save to output-directory
        if args.output_directory is not None:
            filename = os.path.join(args.output_directory, filename)

        try:
            ds.save_as(filename)
        except IOError:
            LOGGER.error('Could not write file to specified directory:')
            LOGGER.error("    %s" %os.path.dirname(filename))
            LOGGER.error('Directory may not exist or you may not have write '
                    'permission')
            return 0xA700 # Failed - Out of Resources
        except:
            LOGGER.error('Could not write file to specified directory:')
            LOGGER.error("    %s" %os.path.dirname(filename))
            return 0xA700 # Failed - Out of Resources

    return 0x0000 # Success

# Test output-directory
if args.output_directory is not None:
    if not os.access(args.output_directory, os.W_OK|os.X_OK):
        LOGGER.error("No write permissions or the output directory may not exist:")
        LOGGER.error("    %s" %args.output_directory)
        sys.exit()

scp_classes = [x for x in StorageSOPClassList]
scp_classes.append(VerificationSOPClass)

# Create application entity
ae = AE(ae_title=args.aetitle,
        port=args.port,
        scu_sop_class=[],
        scp_sop_class=scp_classes,
        transfer_syntax=transfer_syntax)

ae.maximum_pdu_size = args.max_pdu

# Set timeouts
ae.network_timeout = args.timeout
ae.acse_timeout = args.acse_timeout
ae.dimse_timeout = args.dimse_timeout

ae.on_c_store = on_c_store

ae.start()
