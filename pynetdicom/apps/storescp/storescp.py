#!../../../venv/bin/python

"""
    A dcmtk style echoscu application. 
    
    Used for verifying basic DICOM connectivity and as such has a focus on
    providing useful debugging and logging information.
"""

import argparse
import logging
import os
import socket
import sys

from pydicom.dataset import Dataset, FileDataset
from pydicom.filewriter import write_file

from pynetdicom.applicationentity import ApplicationEntity as AE
from pynetdicom.SOPclass import VerificationSOPClass, CTImageStorageSOPClass, \
    Status
from pydicom.uid import ExplicitVRLittleEndian, ImplicitVRLittleEndian, \
    ExplicitVRBigEndian

logger = logging.Logger('')
stream_logger = logging.StreamHandler()
formatter = logging.Formatter('%(levelname).1s: %(message)s')
stream_logger.setFormatter(formatter)
logger.addHandler(stream_logger)
logger.setLevel(logging.ERROR)

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
                          help="set my AE title (default: ECHOSCP)", 
                          type=str, 
                          default='ECHOSCP')

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
    
    return parser.parse_args()

args = _setup_argparser()

if args.verbose:
    logger.setLevel(logging.INFO)
    
if args.debug:
    logger.setLevel(logging.DEBUG)
    pynetdicom_logger = logging.getLogger('pynetdicom')
    pynetdicom_logger.setLevel(logging.DEBUG)

logger.debug('$storescp.py v%s %s $' %('0.1.0', '2016-02-10'))
logger.debug('')

# Validate port
if isinstance(args.port, int):
    test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        test_socket.bind((os.popen('hostname').read()[:-1], args.port))
    except socket.error:
        logger.error("Cannot listen on port %d, insufficient priveleges" 
            %args.port)
        sys.exit()

# Set Transfer Syntax options
transfer_syntax = [ImplicitVRLittleEndian,
                   ExplicitVRLittleEndian,
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

def on_store(sop_class, dataset):
    """
    Function replacing ApplicationEntity.on_store(). Called when a dataset is 
    received following a C-STORE. Write the received dataset to file 
    
    Parameters
    ----------
    sop_class - pydicom.SOPclass.StorageServiceClass
        The StorageServiceClass representing the object
    dataset - pydicom.Dataset
        The DICOM dataset sent via the C-STORE
            
    Returns
    -------
    status
        A valid return status, see the StorageServiceClass for the 
        available statuses
    """
    filename = 'CT.%s' %dataset.SOPInstanceUID
    logger.info('Storing DICOM file: %s' %filename)
    
    if os.path.exists(filename):
        logger.warning('DICOM file already exists, overwriting')
    
    #logger.debug("pydicom::Dataset()")
    meta = Dataset()
    meta.MediaStorageSOPClassUID = dataset.SOPClassUID
    meta.MediaStorageSOPInstanceUID = '1.2.3'
    meta.ImplementationClassUID = '1.2.3.4'
    
    #logger.debug("pydicom::FileDataset()")
    ds = FileDataset(filename, {}, file_meta=meta, preamble=b"\0" * 128)
    ds.update(dataset)
    ds.is_little_endian = True
    ds.is_implicit_VR = True
    #logger.debug("pydicom::save_as()")
    ds.save_as(filename)
        
    return sop_class.Success

# Create application entity
ae = AE(args.aetitle,
        args.port,
        [], 
        [VerificationSOPClass, CTImageStorageSOPClass],
        SupportedTransferSyntax=transfer_syntax)

ae.on_store = on_store

ae.start()
ae.QuitOnKeyboardInterrupt()


