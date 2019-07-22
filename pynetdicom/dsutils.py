"""DICOM dataset utility functions."""

import logging

from pydicom.filebase import DicomBytesIO
from pydicom.filereader import read_dataset
from pydicom.filewriter import write_dataset, write_data_element
from pydicom.tag import tag_in_exception
from pydicom.uid import UID


LOGGER = logging.getLogger('pynetdicom.dsutils')


def decode(bytestring, is_implicit_vr, is_little_endian):
    """Decode `bytestring` to a pydicom Dataset.

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
    """Encode a pydicom Dataset `ds` to bytes.

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
        The encoded dataset as ``bytes`` (if successful) or ``None`` if the
        encoding failed.
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
    """Encode a pydicom DataElement `elem` to bytes.

    Parameters
    ----------
    elem : pydicom.dataelem.DataElement
        The element to encode.
    is_implicit_vr : bool, optional
        The element encoding scheme the element will be encoded with, default
        True.
    is_little_endian : bool, optional
        The byte ordering the element will be encoded in, default True.

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


def prettify(ds, indent=''):
    """Return a list of pretty str for all the elements in ds."""
    def _value(elem):
        _byte = [
            'OB', 'OW', 'OW/OB', 'OW or OB', 'OB or OW', 'US or SS or OW',
            'US or SS'
        ]
        print(elem.value, type(elem.value))
        print(elem.value is False)

        if not elem.value:
            return "(no value available)"
        elif (elem.VR in _byte and len(str(elem.value)) > 41):
            return "Array of {} bytes".format(len(elem.value))
        elif isinstance(elem.value, UID):
            return elem.value.name
        elif elem.VM > 1:
            return '{}'.format([x for x in elem.value])

        return '[{}]'.format(elem.value)

    out = []

    for elem in ds:
        with tag_in_exception(elem.tag):
            tag = elem.tag
            if elem.VR == "SQ":
                out.append(
                    "{}{} {} {:<42} # {}{} {}"
                    .format(
                        indent,
                        "({0:04x},{1:04x})".format(tag.group, tag.element),
                        elem.VR,
                        '(Sequence with {} item(s))'.format(len(elem.value)),
                        '',
                        elem.VM,
                        elem.keyword,
                    )
                )
                for ds in elem.value:
                    indent += '  '
                    out.extend(prettify(ds, indent))
            else:
                out.append(
                    "{}{} {} {:<42} # {}{} {}"
                    .format(
                        indent,
                        "({0:04x},{1:04x})".format(tag.group, tag.element),
                        elem.VR,
                        _value(elem),
                        '',
                        elem.VM,
                        elem.keyword,
                    )
                )

            indent = ''

    return out
