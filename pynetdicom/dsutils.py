#
# Copyright (c) 2012 Patrice Munger
# This file is part of pynetdicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pynetdicom.googlecode.com
#

from io import StringIO, BytesIO
import logging

import pydicom

from pydicom.filebase import DicomBytesIO
from pydicom.filereader import read_dataset
from pydicom.filewriter import write_dataset, write_data_element

logger = logging.getLogger('pynetdicom.dsutils')

def decode(b, is_implicit_VR, is_little_endian):
    """
    When sent a DIMSE Message from a peer AE, decode the data and convert
    it to a pydicom Dataset instance
    
    Parameters
    ----------
    b - io.BytesIO
        The DIMSE Message sent from the peer AE
    is_implicit_VR - bool
        Is implicit or explicit VR
    is_little_endian - bool
        The byte ordering, little or big endian
        
    Returns
    -------
    pydicom.Dataset
        The Message contents decoded into a Dataset
    """
    if is_little_endian:
        transfer_syntax = "Little Endian"
    else:
        transfer_syntax = "Big Endian"
    
    if is_implicit_VR:
        transfer_syntax += " Implicit"
    else:
        transfer_syntax += " Explicit"
    
    logger.debug('pydicom::read_dataset() TransferSyntax="%s"' %transfer_syntax)
    
    # Rewind to the start of the stream
    b.seek(0)
    return read_dataset(b, is_implicit_VR, is_little_endian)

def encode(ds, is_implicit_VR, is_little_endian):
    f = DicomBytesIO()
    f.is_implicit_VR = is_implicit_VR
    f.is_little_endian = is_little_endian
    write_dataset(f, ds)
    rawstr = f.parent.getvalue()
    f.close()
    return rawstr

def encode_element(el, is_implicit_VR, is_little_endian):
    f = DicomBytesIO()
    f.is_implicit_VR = is_implicit_VR
    f.is_little_endian = is_little_endian
    write_data_element(f, el)
    rawstr = f.parent.getvalue()
    f.close()
    return rawstr
