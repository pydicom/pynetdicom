"""
DICOM Dataset utility functions.
"""
import logging

from pydicom.filebase import DicomBytesIO
from pydicom.filereader import read_dataset
from pydicom.filewriter import write_dataset, write_data_element

LOGGER = logging.getLogger('pynetdicom3.dsutils')

def decode(bytestring, is_implicit_VR, is_little_endian):
    """Decode a bytestream to a pydicom Dataset.

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

    LOGGER.debug('pydicom::read_dataset() TransferSyntax="%s"', transfer_syntax)

    # Rewind to the start of the stream
    bytestring.seek(0)
    return read_dataset(bytestring, is_implicit_VR, is_little_endian)

def encode(ds, is_implicit_VR, is_little_endian):
    """Encode a pydicom Dataset to a byte stream.

    Parameters
    ----------
    ds - pydicom.dataset.Dataset
        The dataset to encode
    is_implicit_VR - bool
        Transfer syntax implicit/explicit VR
    is_little_endian - bool
        Transfer syntax byte ordering

    Returns
    -------
    bytes or None
        The encoded dataset (if successful), None if encoding failed.
    """
    fp = DicomBytesIO()
    fp.is_implicit_VR = is_implicit_VR
    fp.is_little_endian = is_little_endian
    try:
        write_dataset(fp, ds)
    except Exception as ex:
        LOGGER.error("pydicom.write_dataset() failed:")
        LOGGER.error(ex)
        fp.close()
        return None

    rawstr = fp.parent.getvalue()
    fp.close()

    return rawstr

def encode_element(elem, is_implicit_VR, is_little_endian):
    """Encode a pydicom DataElement to a byte stream."""
    fp = DicomBytesIO()
    fp.is_implicit_VR = is_implicit_VR
    fp.is_little_endian = is_little_endian
    write_data_element(fp, elem)
    rawstr = fp.parent.getvalue()
    fp.close()

    return rawstr
