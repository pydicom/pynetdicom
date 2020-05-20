"""DICOM dataset utility functions."""

import logging
import zlib

from pydicom.filebase import DicomBytesIO
from pydicom.filereader import read_dataset
from pydicom.filewriter import write_dataset, write_data_element

from pynetdicom.utils import pretty_bytes


LOGGER = logging.getLogger('pynetdicom.dsutils')


def decode(bytestring, is_implicit_vr, is_little_endian, deflated=False):
    """Decode `bytestring` to a *pydicom* :class:`~pydicom.dataset.Dataset`.

    .. versionchanged:: 1.5

        Added `deflated` keyword parameter

    Parameters
    ----------
    byestring : io.BytesIO
        The encoded dataset in the DIMSE Message sent from the peer AE.
    is_implicit_vr : bool
        The dataset is encoded as implicit (``True``) or explicit VR
        (``False``).
    is_little_endian : bool
        The byte ordering of the encoded dataset, ``True`` for little endian,
        ``False`` for big endian.
    deflated : bool, optional
        ``True`` if the dataset has been encoded using *Deflated Explicit VR
        Little Endian* transfer syntax (default ``False``).

    Returns
    -------
    pydicom.dataset.Dataset
        The decoded dataset.
    """
    ## Logging
    transfer_syntax = ''
    if deflated:
        transfer_syntax = "Deflated "

    transfer_syntax += "Little Endian" if is_little_endian else "Big Endian"
    if is_implicit_vr:
        transfer_syntax += " Implicit"
    else:
        transfer_syntax += " Explicit"

    LOGGER.debug('pydicom.read_dataset() TransferSyntax="%s"', transfer_syntax)

    # Rewind to the start of the stream
    bytestring.seek(0)

    if deflated:
        # Decompress the dataset
        bytestring = DicomBytesIO(
            zlib.decompress(bytestring.getvalue(), -zlib.MAX_WBITS)
        )
        bytestring.is_implicit_VR = is_implicit_vr
        bytestring.is_little_endian = is_little_endian

    # Decode the dataset
    return read_dataset(bytestring, is_implicit_vr, is_little_endian)


def encode(ds, is_implicit_vr, is_little_endian, deflated=False):
    """Encode a *pydicom* :class:`~pydicom.dataset.Dataset` `ds`.

    .. versionchanged:: 1.5

        Added `deflated` keyword parameter

    Parameters
    ----------
    ds : pydicom.dataset.Dataset
        The dataset to encode
    is_implicit_vr : bool
        The element encoding scheme the dataset will be encoded with, ``True``
        for implicit VR, ``False`` for explicit VR.
    is_little_endian : bool
        The byte ordering the dataset will be encoded in, ``True`` for little
        endian, ``False`` for big endian.
    deflated : bool, optional
        ``True`` if the dataset is to be encoded using *Deflated Explicit VR
        Little Endian* transfer syntax (default ``False``).

    Returns
    -------
    bytes or None
        The encoded dataset as :class:`bytes` (if successful) or ``None`` if
        the encoding failed.
    """
    # pylint: disable=broad-except
    fp = DicomBytesIO()
    fp.is_implicit_VR = is_implicit_vr
    fp.is_little_endian = is_little_endian
    try:
        write_dataset(fp, ds)
    except Exception as exc:
        LOGGER.error("pydicom.write_dataset() failed:")
        LOGGER.exception(exc)
        fp.close()
        return None

    bytestring = fp.parent.getvalue()
    fp.close()

    if deflated:
        # Compress the encoded dataset
        compressor = zlib.compressobj(
            zlib.Z_DEFAULT_COMPRESSION, zlib.DEFLATED, -zlib.MAX_WBITS
        )
        bytestring = compressor.compress(bytestring)
        bytestring += compressor.flush()
        bytestring += b'\x00' if len(bytestring) % 2 else b''

    return bytestring


def encode_element(elem, is_implicit_vr=True, is_little_endian=True):
    """Encode a *pydicom* :class:`~pydicom.dataelem.DataElement` `elem`.

    .. deprecated:: 1.5

        Will be removed in version 2.0, use *pydicom* instead.

    Parameters
    ----------
    elem : pydicom.dataelem.DataElement
        The element to encode.
    is_implicit_vr : bool, optional
        The element encoding scheme the element will be encoded with, ``True``
        for implicit VR (default), ``False`` for explicit VR.
    is_little_endian : bool, optional
        The byte ordering the element will be encoded in, ``True`` for little
        endian (default), ``False`` for big endian.

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


def pretty_dataset(ds, indent=0, indent_char='  '):
    """Return a list of pretty dataset strings.

    .. versionadded:: 1.5

    Parameters
    ----------
    ds : pydicom.dataset.Dataset
        The dataset to beautify.
    indent : int, optional
        The indentation level of the current dataset (default: ``0``).
    indent_char : str, optional
        The character(s) to use when indenting the dataset (default ``'  '``).

    Returns
    -------
    list of str
    """
    out = []
    for elem in iter(ds):
        if elem.VR == 'SQ':
            out.append(pretty_element(elem))
            for ii, item in enumerate(elem.value):
                msg = '(Sequence item #{})'.format(ii + 1)
                out.append(indent_char * (indent + 1) + msg)
                out.extend(pretty_dataset(item, indent + 2))
        else:
            out.append(indent_char * indent + pretty_element(elem))

    return out


def pretty_element(elem):
    """Return a pretty element string.

    .. versionadded:: 1.5

    Parameters
    ----------
    elem : pydicom.dataelem.DataElement
        The element to beautify.

    Returns
    -------
    str
    """
    try:
        value = elem.value
        if elem.VM == 0 and elem.VR != 'SQ':
            # Empty value
            value = '(no value available)'
        elif elem.VR in ['OB', 'OD', 'OF', 'OL', 'OW', 'OV']:
            # Byte VRs
            if elem.VM == 1:
                # Single value
                length = len(elem.value)
                if length <= 13:
                    value = '[{}]'.format(
                        pretty_bytes(elem.value, prefix='', delimiter=' ')[0]
                    )
                else:
                    value = '({} bytes of binary data)'.format(len(elem.value))
            else:
                # Multiple values - probably non-conformant
                total_length = sum([len(ii) for ii in elem.value])
                value = '({} bytes of binary data)'.format(total_length)
        elif elem.VR != 'SQ':
            # Non-sequence elements
            if elem.VM == 1:
                value = '[{}]'.format(elem.value)
            else:
                value = '[{}]'.format(
                    '\\'.join([str(ii) for ii in elem.value])
                )
        elif elem.VR == 'SQ':
            # Sequence elements
            if elem.VM == 1:
                value = '(Sequence with {} item)'.format(len(elem.value))
            else:
                value = '(Sequence with {} items)'.format(len(elem.value))

    except Exception as exc:
        value = '(pynetdicom failed to beautify value)'

    return '({:04X},{:04X}) {} {: <40} # {} {}'.format(
        elem.tag.group, elem.tag.element,
        elem.VR,
        value,
        elem.VM,
        elem.keyword
    )
