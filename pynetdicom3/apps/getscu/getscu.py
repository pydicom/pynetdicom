#!/usr/bin/env python

"""
    A getscu application.
"""

import argparse
import logging
import os
import socket
import sys
import time

from pydicom.dataset import Dataset, FileDataset
from pydicom.uid import (
    ExplicitVRLittleEndian, ImplicitVRLittleEndian, ExplicitVRBigEndian
)

from pynetdicom3 import (
    AE,
    StoragePresentationContexts,
    QueryRetrievePresentationContexts,
    PYNETDICOM_IMPLEMENTATION_UID,
    PYNETDICOM_IMPLEMENTATION_VERSION
)
from pynetdicom3.pdu_primitives import SCP_SCU_RoleSelectionNegotiation

LOGGER = logging.Logger('getscu')
stream_logger = logging.StreamHandler()
formatter = logging.Formatter('%(levelname).1s: %(message)s')
stream_logger.setFormatter(formatter)
LOGGER.addHandler(stream_logger)
LOGGER.setLevel(logging.ERROR)


VERSION = '0.2.2'


def _setup_argparser():
    """Setup the command line arguments"""
    # Description
    parser = argparse.ArgumentParser(
        description="The getscu application implements a Service Class User "
                    "(SCU) for the Query/Retrieve (QR) Service Class and the "
                    "Basic Worklist Management (BWM) Service Class. getscu "
                    "only supports query functionality using the C-GET "
                    "message. It sends query keys to an SCP and waits for a "
                    "response. The application can be used to test SCPs of the "
                    "QR and BWM Service Classes.",
        usage="getscu [options] peer port")

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

    # Network Options
    net_opts = parser.add_argument_group('Network Options')
    net_opts.add_argument("-aet", "--calling-aet", metavar='[a]etitle',
                          help="set my calling AE title (default: GETSCU)",
                          type=str,
                          default='GETSCU')
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
                          action="store_true", default=True)
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
    LOGGER.setLevel(logging.INFO)
    pynetdicom_logger = logging.getLogger('pynetdicom3')
    pynetdicom_logger.setLevel(logging.INFO)

if args.debug:
    LOGGER.setLevel(logging.DEBUG)
    pynetdicom_logger = logging.getLogger('pynetdicom3')
    pynetdicom_logger.setLevel(logging.DEBUG)

LOGGER.debug('$getscu.py v{0!s}'.format(VERSION))
LOGGER.debug('')


# Create application entity
# Binding to port 0 lets the OS pick an available port
ae = AE(ae_title=args.calling_aet, port=0)

for context in QueryRetrievePresentationContexts:
    ae.add_requested_context(context.abstract_syntax)
for context in StoragePresentationContexts:
    ae.add_requested_context(context.abstract_syntax)

# Add SCP/SCU Role Selection Negotiation to the extended negotiation
# We want to act as a Storage SCP
ext_neg = []
for context in StoragePresentationContexts:
    role = SCP_SCU_RoleSelectionNegotiation()
    role.sop_class_uid = context.abstract_syntax
    role.scp_role = True
    role.scu_role = False
    ext_neg.append(role)

# Create query dataset
d = Dataset()
d.PatientName = '*'
d.QueryRetrieveLevel = "PATIENT"

if args.worklist:
    query_model = 'W'
elif args.patient:
    query_model = 'P'
elif args.study:
    query_model = 'S'
elif args.psonly:
    query_model = 'O'
else:
    query_model = 'W'

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
    meta.ImplementationClassUID = PYNETDICOM_IMPLEMENTATION_UID
    meta.TransferSyntaxUID = context.transfer_syntax

    # The following is not mandatory, set for convenience
    meta.ImplementationVersionName = PYNETDICOM_IMPLEMENTATION_VERSION

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

# Request association with remote
assoc = ae.associate(args.peer,
                     args.port,
                     ae_title=args.called_aet,
                     ext_neg=ext_neg)

# Send query
if assoc.is_established:
    response = assoc.send_c_get(d, query_model=query_model)

    for status, identifier in response:
        pass

    assoc.release()
