"""
DICOM Dataset utility functions.
"""
import logging

from pydicom.filebase import DicomBytesIO
from pydicom.filereader import read_dataset
from pydicom.filewriter import write_dataset, write_data_element
from pydicom.datadict import (
    tag_for_keyword, repeater_has_keyword, get_entry
)
from pydicom.dataset import Dataset
from pydicom.tag import Tag



LOGGER = logging.getLogger('pynetdicom.dsutils')


class ElementPath(object):
    """Class for parsing DICOM data elements defined using strings."""
    def __init__(self, elem_path, parent=None):
        """Initialise a new ElementPath.

        Parameters
        ----------
        elem_path : str
            The string describing the complete path of a DICOM data element.
        parent : ElementPath or None
            The parent of the current ElementPath (if there is one) or None.
        """
        self._child = None
        self._value = None

        self.path = elem_path
        self.components = elem_path
        self._parent = parent

    @property
    def child(self):
        """Return the current object's child ElementPath (or None)."""
        return self._child

    @property
    def parent(self):
        """Return the current object's parent ElementPath (or None)."""
        return self._parent

    @property
    def value(self):
        """Return the value assigned to the data element."""
        if self.parent is None:
            return self._value

        parent = self.parent
        while parent.parent:
            parent = parent.parent

        return parent._value

    @property
    def components(self):
        """Return the element's component str."""
        return self._components

    @components.setter
    def components(self, value):
        """Set the element's component str."""
        elem_path = value
        if '=' in value:
            elem_path, elem_value = value.split('=', 1)
            self._value = elem_value

        self._components = elem_path.split('.')

        if len(self._components) > 1:
            self._child = ElementPath('.'.join(self._components[1:]), self)

        # Parse current component
        tag = self.tag
        try:
            # Try DICOM dictionary
            self._entry = get_entry(tag)
        except Exception as exc:
            # Private element
            self._entry = ('UN', '1', 'Unknown', False, 'Unknown')

    @property
    def is_private(self):
        pass

    @property
    def is_sequence(self):
        """Return True if the element component is a sequence."""
        start = self.components[0].find('[')
        end = self.components[0].find(']')
        if start >= 0 or end >= 0:
            if not (start >= 0 and end >= 0):
                raise ValueError(
                    'Invalid element component: missing item bracket'
                )

            if start + 1 == end:
                raise ValueError(
                    'Invalid element component: missing item number'
                )

            self._item_nr = int(self.components[0][start + 1:end])
            return True

        return False

    @property
    def item_nr(self):
        """Return the element's sequence item number.

        Returns
        -------
        int or None
            TODO
        """
        if self.is_sequence:
            return self._item_nr

        return None

    @property
    def keyword(self):
        """Return the element's keyword as a str."""
        return self._entry[4]

    @property
    def tag(self):
        """Return the element's tag as a pydicom.tag.Tag."""
        tag = self.components[0]
        if self.is_sequence:
            tag = tag.split('[')[0]

        # (gggg,eeee) based tag
        if ',' in tag:
            tag_g, tag_e = tag.split(',')
            if '(' in tag_g:
                tag_g = tag_g[1:]
            if ')' in tag_e:
                tag_e = tag_e[:4]

            return Tag(tag_g, tag_e)

        # Keyword based tag - private keywords not allowed
        if repeater_has_keyword(tag):
            raise ValueError("repeater elements must be specified using (gggg,eeee)")

        tag = tag_for_keyword(tag)
        # Test against None as 0x00000000 is a valid tag
        if tag is not None:
            return Tag(tag)

        raise ValueError("Unknown keyword")

    @property
    def VR(self):
        """Return the element's VR as str."""
        return self._entry[0]

    @property
    def VM(self):
        """Return the element's VM as str."""
        return self._entry[1]


def as_dataset(items):
    """

    * VR for private elements will be set to UN

    Parameters
    ----------
    items : list of str
        A list of strings describing the elements that are to be converted
        to a DICOM dataset.

    Returns
    -------
    pydicom.dataset.Dataset
        The DICOM dataset created using the list of element descriptions.
    """
    def recursive_add(ds, elem):
        """
        Parameters
        ----------
        ElementPath
            A list of components describing the path to the element.
        value
            The value of the element.

        Returns
        -------
        pydicom.dataset.Dataset
            A DICOM dataset representation of `elements`.
        """
        if elem.tag not in ds:
            # Add new element or sequence to dataset
            if elem.is_sequence:
                # Add empty sequence
                ds.add_new(elem.tag, elem.VR, [])

                # SequenceElement=
                if elem.child is None:
                    return ds
            else:
                # Element=(value)
                ds.add_new(elem.tag, elem.VR, elem.value)
                return ds

            nr_items = len(ds[elem.tag].value)
            if nr_items - elem.item_nr == 0:
                # SequenceElement[0]
                ds[elem.tag].value.append(Dataset())
            else:
                # New SequenceElement[N > 0] not allowed
                raise ValueError(
                    "Unable to create a dataset with non-sequential indexing "
                    "of Sequence items (i.e. SequenceElement[1] must be "
                    "preceeded by SequenceElement[0])"
                )

        else:
            # Either update or add new item
            if not elem.is_sequence:
                # Update Element=(value)
                ds[elem.tag].value = elem.value
                return ds

            # Check if we need to add a new item to an existing sequence
            # SequenceElement currently has N items
            nr_items = len(ds[elem.tag].value)
            if nr_items - elem.item_nr == 0:
                # New SequenceElement[N + 1] item
                ds[elem.tag].value.append(Dataset())
            elif nr_items - 1 != elem.item_nr:
                # New SequenceElement[N + more than 1]
                raise ValueError(
                    "Unable to create a dataset with non-sequential indexing "
                    "of Sequence items (i.e. SequenceElement[1] must be "
                    "preceeded by SequenceElement[0])"
                )

        # Current SequenceElement[N]
        current = ds[elem.tag].value[elem.item_nr]
        current.update(recursive_add(current, elem.child))

        return ds

    elements = [ElementPath(ii) for ii in items]
    for elem in elements:
        yield recursive_add(Dataset(), elem)


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
