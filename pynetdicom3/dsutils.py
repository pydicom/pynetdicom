"""
DICOM Dataset utility functions.
"""
import logging

from pydicom.filebase import DicomBytesIO
from pydicom.filereader import read_dataset
from pydicom.filewriter import write_dataset, write_data_element

LOGGER = logging.getLogger('pynetdicom3.dsutils')

def decode(bytestring, is_implicit_vr, is_little_endian):
    """Decode `bytestring` to a pydicom Dataset.

    When sent a DIMSE Message from a peer AE, decode the data and convert
    it to a pydicom Dataset instance.

    Parameters
    ----------
    byestring : io.BytesIO
        The encoded dataset in the DIMSE Message sent from the peer AE.
    is_implicit_vr : bool
        The dataset is encoded as implicit or explicit VR.
    is_little_endian : bool
        The byte ordering of the encoded dataset, little or big endian.

    Returns
    -------
    pydicom.dataset.Dataset
        The decoded dataset.
    """
    ## Logging
    transfer_syntax = "Little Endian" if is_little_endian else "Big Endian"
    if is_implicit_vr:
        transfer_syntax += " Implicit"
    else:
        transfer_syntax += " Explicit"

    LOGGER.debug('pydicom.read_dataset() TransferSyntax="%s"', transfer_syntax)

    ## Decode the dataset
    # Rewind to the start of the stream
    bytestring.seek(0)
    return read_dataset(bytestring, is_implicit_vr, is_little_endian)

def encode(ds, is_implicit_vr, is_little_endian):
    """Encode a pydicom Dataset `ds` to a byte stream.

    Parameters
    ----------
    ds : pydicom.dataset.Dataset
        The dataset to encode
    is_implicit_vr : bool
        The element encoding scheme the dataset will be encoded with.
    is_little_endian : bool
        The byte ordering the dataset will be encoded in.

    Returns
    -------
    bytes or None
        The encoded dataset (if successful), None if the encoding failed.
    """
    # pylint: disable=broad-except
    fp = DicomBytesIO()
    fp.is_implicit_VR = is_implicit_vr
    fp.is_little_endian = is_little_endian
    try:
        write_dataset(fp, ds)
    except Exception as ex:
        LOGGER.error("pydicom.write_dataset() failed:")
        LOGGER.error(ex)
        fp.close()
        return None

    bytestring = fp.parent.getvalue()
    fp.close()

    return bytestring

def encode_element(elem, is_implicit_vr=True, is_little_endian=True):
    """Encode a pydicom DataElement `elem` to a byte stream.

    The default is to encode the element as implicit VR little endian.

    Parameters
    ----------
    elem : pydicom.dataelem.DataElement
        The element to encode
    is_implicit_vr : bool, optional
        The element encoding scheme the element will be encoded with, default
        is True.
    is_little_endian : bool, optional
        The byte ordering the element will be encoded in, default is True.

    Returns
    -------
    bytes
        The encoded element.
    """
    fp = DicomBytesIO()
    fp.is_implicit_VR = is_implicit_vr
    fp.is_little_endian = is_little_endian
    write_data_element(fp, elem)
    bytestring = fp.parent.getvalue()
    fp.close()

    return bytestring
