#!/usr/bin/env python

"""
    A dcmtk style movescu application

    Used for
"""

import argparse
import logging
import os
import socket
import sys
import time

from pydicom.dataset import Dataset
from pydicom.uid import ExplicitVRLittleEndian, ImplicitVRLittleEndian, \
    ExplicitVRBigEndian

from pynetdicom3 import (
    AE,
    StorageSOPClassList,
    QueryRetrieveSOPClassList,
    pynetdicom_version,
    pynetdicom_implementation_uid
)
from pynetdicom3.pdu_primitives import SCP_SCU_RoleSelectionNegotiation

logger = logging.Logger('movescu')
stream_logger = logging.StreamHandler()
formatter = logging.Formatter('%(levelname).1s: %(message)s')
stream_logger.setFormatter(formatter)
logger.addHandler(stream_logger)
logger.setLevel(logging.ERROR)


VERSION = '0.2.1'


def _setup_argparser():
    """Setup the command line arguments"""
    # Description
    parser = argparse.ArgumentParser(
        description="The movescu application implements a Service Class User "
                    "(SCU) for the Query/Retrieve (QR) Service Class and a SCP "
                    " for the Storage Service Class. movescu "
                    "supports retrieve functionality using the C-MOVE "
                    "message. It sends query keys to an SCP and waits for a "
                    "response. It will accept associations for the purpose of "
                    "receiving images sent as a result of the C-MOVE request. "
                    "The application can be used to test SCPs of the "
                    "QR Service Classes. movescu can initiate the transfer of "
                    "images to a third party or can retrieve images to itself "
                    "(note: the use of the term 'move' is a misnomer, the "
                    "C-MOVE operation performs an image copy only)",
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
                          help="use patient root information model (default)",
                          action="store_true",
                          )
    qr_model.add_argument("-S", "--study",
                          help="use study root information model",
                          action="store_true")
    qr_model.add_argument("-O", "--psonly",
                          help="use patient/study only information model",
                          action="store_true")

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

if args.verbose:
    logger.setLevel(logging.INFO)
    pynetdicom_logger = logging.getLogger('PYNETDICOM3_')
    pynetdicom_logger.setLevel(logging.INFO)

if args.debug:
    logger.setLevel(logging.DEBUG)
    pynetdicom_logger = logging.getLogger('pynetdicom3')
    pynetdicom_logger.setLevel(logging.DEBUG)

logger.debug('$movescu.py v{0!s}'.format(VERSION))
logger.debug('')

# Create application entity
# Binding to port 0 lets the OS pick an available port
ae = AE(ae_title=args.calling_aet,
        port=11113,
        scu_sop_class=QueryRetrieveSOPClassList,
        scp_sop_class=StorageSOPClassList,
        transfer_syntax=[ExplicitVRLittleEndian])

# Set the extended negotiation SCP/SCU role selection to allow us to receive
#   C-STORE requests for the supported SOP classes
ext_neg = []
for context in ae.presentation_contexts_scu:
    tmp = SCP_SCU_RoleSelectionNegotiation()
    tmp.sop_class_uid = context.abstract_syntax
    tmp.scu_role = False
    tmp.scp_role = True

    ext_neg.append(tmp)

# Request association with remote
assoc = ae.associate(args.peer, args.port, args.called_aet, ext_neg=ext_neg)

# Create query dataset
d = Dataset()
d.PatientName = '*'
d.QueryRetrieveLevel = "PATIENT"

if args.patient:
    query_model = 'P'
elif args.study:
    query_model = 'S'
elif args.psonly:
    query_model = 'O'
else:
    query_model = 'P'

def on_c_store(dataset, context, info):
    """
    Function replacing ApplicationEntity.on_store(). Called when a dataset is
    received following a C-STORE. Write the received dataset to file

    Parameters
    ----------
    dataset : pydicom.Dataset
        The DICOM dataset sent via the C-STORE
    context : pynetdicom3.presentation.PresentationContextTuple
        Details of the presentation context the dataset was sent under.
    info : dict
        A dict containing information about the association and DIMSE message.

    Returns
    -------
    status : pynetdicom.sop_class.Status or int
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
        mode_prefix = mode_prefixes[dataset.SOPClassUID.name]
    except KeyError:
        mode_prefix = 'UN'

    filename = '{0!s}.{1!s}'.format(mode_prefix, dataset.SOPInstanceUID)
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
    meta.MediaStorageSOPClassUID = dataset.SOPClassUID
    meta.MediaStorageSOPInstanceUID = dataset.SOPInstanceUID
    meta.ImplementationClassUID = pynetdicom_implementation_uid
    meta.TransferSyntaxUID = context.transfer_syntax

    # The following is not mandatory, set for convenience
    meta.ImplementationVersionName = pynetdicom_version

    ds = FileDataset(filename, {}, file_meta=meta, preamble=b"\0" * 128)
    ds.update(dataset)
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

ae.on_c_store = on_c_store

# Send query
if assoc.is_established:
    if args.move_aet:
        response = assoc.send_c_move(d, args.move_aet, query_model=query_model)
    else:
        response = assoc.send_c_move(d, args.calling_aet, query_model=query_model)

    time.sleep(1)
    for (status, d) in response:
        pass

    assoc.release()
