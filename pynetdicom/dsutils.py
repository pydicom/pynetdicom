#
# Copyright (c) 2012 Patrice Munger
# This file is part of pynetdicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pynetdicom.googlecode.com
#

from io import StringIO, BytesIO

import pydicom

#if dicom.__version_info__ >= (0, 9, 8):
from pydicom.filebase import DicomBytesIO
#else:
#    from dicom.filebase import DicomStringIO as DicomBytesIO
from pydicom.filereader import read_dataset
from pydicom.filewriter import write_dataset, write_data_element

def wrap_list(lst, items_per_line=16):
    lines = []
    for i in range(0, len(lst), items_per_line):
        chunk = lst[i:i + items_per_line]
        line = 'D:   ' + '  '.join(format(x, '02x') for x in chunk)
        lines.append(line)
    return "\n".join(lines)

def decode(s, is_implicit_VR, is_little_endian):
    """
    When sent a DIMSE Message from a peer AE, decode the data and convert
    it to a pydicom Dataset instance
    
    Parameters
    ----------
    s - io.BytesIO
        The DIMSE Message sent from the peer AE
    is_implicit_VR - bool
        The Transfer Syntax type
    is_little_endian - bool
        The byte ordering
        
    Returns
    -------
    pydicom.Dataset
        The Message contents decoded into a Dataset
    """
    # Rewind to the start of the stream
    s.seek(0)
    s.seek(0)
    return read_dataset(s, is_implicit_VR, is_little_endian)

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
