#
# Copyright (c) 2012 Patrice Munger
# This file is part of pynetdicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pynetdicom.googlecode.com
#

import os
import sys

try:
    import dicom
except:
    raise Exception("dicom package not found. Please install it")


def testfiles_dir():
    """returns the testfiles directory"""

    d, f = os.path.split(dicom.__file__)
    return os.path.join(d, 'testfiles')


def set_path():
    thisdir = os.path.dirname(os.path.abspath(__file__))
    for pp in sys.path:
        if 'pynetdicom' in pp:
            sys.path.remove(pp)
    sys.path.append(thisdir)
