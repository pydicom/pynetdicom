#!../../../venv/bin/python

"""
    A dcmtk style storescu application. 
    
    Used for verifying basic DICOM connectivity and as such has a focus on
    providing useful debugging and logging information.
"""

import argparse
import logging
import os
import socket
import sys

from pydicom import read_file

from pynetdicom.applicationentity import AE
from pynetdicom.SOPclass import VerificationSOPClass, CTImageStorageSOPClass
from pydicom.uid import ExplicitVRLittleEndian, ImplicitVRLittleEndian, \
    ExplicitVRBigEndian

logger = logging.Logger('storescu')
stream_logger = logging.StreamHandler()
formatter = logging.Formatter('%(levelname).1s: %(message)s')
stream_logger.setFormatter(formatter)
logger.addHandler(stream_logger)
logger.setLevel(logging.ERROR)

def _setup_argparser():
    # Description
    parser = argparse.ArgumentParser(
        description="The storescu application implements a Service Class User "
                    "(SCU) for the Storage Service Class. For each DICOM "
                    "file on the command line it sends a C-STORE message to a  "
                    "Storage Service Class Provider (SCP) and waits for a "
                    "response. The application can be used to transmit DICOM "
                    "images and other composite objectes.", 
        usage="echoscu [options] peer port")
        
    # Parameters
    req_opts = parser.add_argument_group('Parameters')
    req_opts.add_argument("peer", help="hostname of DICOM peer", type=str)
    req_opts.add_argument("port", help="TCP/IP port number of peer", type=int)
    req_opts.add_argument("dcmfile_in", 
                          metavar="dcmfile-in",
                          help="DICOM file or directory to be transmitted", 
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
                          help="set my calling AE title (default: STORESCU)", 
                          type=str, 
                          default='ECHOSCU')
    net_opts.add_argument("-aec", "--called-aet", metavar='[a]etitle', 
                          help="set called AE title of peer (default: ANY-SCP)", 
                          type=str, 
                          default='ANY-SCP')

    return parser.parse_args()

args = _setup_argparser()

if args.verbose:
    logger.setLevel(logging.INFO)
    
if args.debug:
    logger.setLevel(logging.DEBUG)
    pynetdicom_logger = logging.getLogger('pynetdicom')
    pynetdicom_logger.setLevel(logging.DEBUG)

logger.debug('$storescu.py v%s %s $' %('0.1.0', '2016-02-10'))
logger.debug('')

# Check file exists and is readable and DICOM
logger.debug('Checking input files')
try:
    f = open(args.dcmfile_in, 'rb')
    dataset = read_file(f, force=True)
    f.close()
except IOError:
    logger.error('Cannot read input file %s' %args.dcmfile_in)
    f.close()
    sys.exit()
except:
    logger.error('File may not be DICOM %s' %args.dcmfile_in)
    f.close()
    sys.exit()

if dataset.file_meta.TransferSyntaxUID in ['1.2.840.10008.1.2', 
                                            '1.2.840.10008.1.2.1']:
    byte_order = 'little'
else:
    byte_order = 'big'
    


# Create application entity
# Set Transfer Syntax options
transfer_syntax = [ImplicitVRLittleEndian,
                   ExplicitVRLittleEndian,
                   ExplicitVRBigEndian]

# Bind to port 0, OS will pick an available port
ae = AE(args.calling_aet,
        0,
        [], 
        [VerificationSOPClass, CTImageStorageSOPClass],
        SupportedTransferSyntax=transfer_syntax)

# Request association with remote
assoc = ae.request_association(args.peer, args.port, args.called_aet)

if assoc is not None:
    logger.info('Sending file: %s' %args.dcmfile_in)
    
    for elem in dataset:
        elem_name = ''.join(elem.description().split(' '))
        elem_group = elem.tag.group
        elem_element = elem.tag.elem
        if elem.VR == 'US or SS':
            
            logger.debug("Setting undefined VR of %s (%04x, %04x) to 'US'" 
                %(elem_name, elem_group, elem_element))
            elem.VR = 'US'
            elem.value = int.from_bytes(elem.value, byteorder=byte_order)
        if elem.VR == 'OB or OW':
            logger.debug("Setting undefined VR of %s (%04x, %04x) to 'OW'" 
               %(elem_name, elem_group, elem_element))
            elem.VR = 'OW'
    
    status = None

    #try:
    status = assoc.CTImageStorageSOPClass.SCU(dataset, 1)
    #except:
    #    logger.info('Aborting Association')
    #    assoc.Abort(0)
    
    if status is not None:
        # Release association
        logger.info('Releasing Association')
        assoc.Release(0)

# Quit
ae.Quit()


