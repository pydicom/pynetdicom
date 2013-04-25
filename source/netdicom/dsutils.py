#
# Copyright (c) 2012 Patrice Munger
# This file is part of pynetdicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pynetdicom.googlecode.com
#

import StringIO
import dicom
if dicom.__version_info__ >= (0,9,8):
    from dicom.filebase import DicomBytesIO
else:
    from dicom.filebase import DicomStringIO as DicomBytesIO
from dicom.filereader import read_dataset
from dicom.filewriter import write_dataset, write_data_element


def decode(rawstr, is_implicit_VR, is_little_endian):
    s = StringIO.StringIO(rawstr)
    ds = read_dataset(s, is_implicit_VR, is_little_endian)
    return ds

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
