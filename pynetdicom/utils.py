"""Various utility functions."""

import codecs
from io import BytesIO
import logging
import sys
import unicodedata

from pydicom.datadict import (
    tag_for_keyword, repeater_has_keyword, get_entry
)
from pydicom.dataset import Dataset
from pydicom.tag import Tag

from pynetdicom import _config


LOGGER = logging.getLogger('pynetdicom.utils')


# TODO: Move to dsutils.py instead
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
    def recurse(elem):
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
        ds = Dataset()
        #print('is seq', elem.is_sequence)
        if elem.is_sequence:
            # Fix this -> elem is singleton
            ds.add_new(elem.tag, 'SQ', [])
            ds[elem.tag].value.append(recurse(elem.child))
        else:
            #print('set', elem, elem.tag, elem.value)
            ds.add_new(elem.tag, elem.VR, elem.value)

        return ds

    ds = Dataset()
    elements = [ElementPath(ii) for ii in items]
    # Each element component may be:
    #   tag based: (0010,0010), (0010,0020)[1]
    #   keyword based: PatientName, BeamSequence[0]
    # Can have mixed components within a single element string
    # Can't have comma in keyword based element components
    for elem in elements:
        ds.update(recurse(elem))

    return ds

def pretty_bytes(bytestream, prefix='  ', delimiter='  ', items_per_line=16,
                 max_size=512, suffix=''):
    """Turn the bytestring `bytestream` into a list of nicely formatted str.

    Parameters
    ----------
    bytestream : bytes or io.BytesIO
        The bytes to convert to a nicely formatted string list
    prefix : str
        Insert `prefix` at the start of every item in the output string list
    delimiter : str
        Delimit each of the bytes in `bytestream` using `delimiter`
    items_per_line : int
        The number of bytes in each item of the output string list.
    max_size : int or None
        The maximum number of bytes to add to the output string list. A value
        of None indicates that all of `bytestream` should be output.
    suffix : str
        Append `suffix` to the end of every item in the output string list

    Returns
    -------
    list of str
        The output string list
    """
    lines = []
    if isinstance(bytestream, BytesIO):
        bytestream = bytestream.getvalue()

    cutoff_output = False
    byte_count = 0
    for ii in range(0, len(bytestream), items_per_line):
        # chunk is a bytes in python3 and a str in python2
        chunk = bytestream[ii:ii + items_per_line]
        byte_count += len(chunk)

        # Python 2 compatibility
        if isinstance(chunk, str):
            gen = (format(ord(x), '02x') for x in chunk)
        else:
            gen = (format(x, '02x') for x in chunk)


        if max_size is not None and byte_count <= max_size:
            line = prefix + delimiter.join(gen)
            lines.append(line + suffix)
        elif max_size is not None and byte_count > max_size:
            cutoff_output = True
            break
        else:
            line = prefix + delimiter.join(gen)
            lines.append(line + suffix)

    if cutoff_output:
        lines.insert(0, prefix + 'Only dumping {0!s} bytes.'.format(max_size))

    return lines


def validate_ae_title(ae_title):
    """Return a valid AE title from `ae_title`, if possible.

    An AE title:

    * Must be no more than 16 characters
    * Leading and trailing spaces are not significant
    * The characters should belong to the Default Character Repertoire
      excluding 0x5C (backslash) and all control characters

    If the supplied `ae_title` is greater than 16 characters once
    non-significant spaces have been removed then the returned AE title
    will be truncated to remove the excess characters.

    If the supplied `ae_title` is less than 16 characters once non-significant
    spaces have been removed, the spare trailing characters will be set to
    space (0x20).

    AE titles are made up of the Default Character Repertoire (the Basic
    G0 Set of ISO646) excluding character code 0x5c (backslash) and all
    control characters.

    Parameters
    ----------
    ae_title : bytes
        The AE title to check.

    Returns
    -------
    str or bytes
        A valid AE title truncated to 16 characters if necessary. If Python 3
        then only returns bytes, if Python 2 then returns str.

    Raises
    ------
    ValueError
        If `ae_title` is an empty string, contains only spaces or contains
        control characters or backslash.
    """
    if not isinstance(ae_title, (str, bytes)):
        raise TypeError(
            "AE titles must be str or bytes"
        )

    # Python 2 - convert string to unicode
    if sys.version_info[0] == 2:
        ae_title = unicode(ae_title)

    # If bytes decode to ascii string
    if isinstance(ae_title, bytes):
        ae_title = ae_title.decode('ascii', errors='strict')

    # Strip out any leading or trailing spaces
    ae_title = ae_title.strip()
    # Strip out any leading or trailing nulls - non-conformant
    ae_title = ae_title.strip('\0')
    if not ae_title:
        raise ValueError(
            "AE titles are not allowed to consist entirely of only spaces"
        )

    # Truncate if longer than 16 characters
    ae_title = ae_title[:16]
    # Pad out to 16 characters using spaces
    ae_title = ae_title.ljust(16)

    # Unicode category: 'Cc' is control characters
    invalid = [
        char for char in ae_title
        if unicodedata.category(char)[0] == 'C' or char == '\\'
    ]
    if invalid:
        raise ValueError(
            "AE titles must not contain any control characters or backslashes"
        )

    # Return as bytes (python 3) or str (python 2)
    return ae_title.encode('ascii', errors='strict')


def validate_uid(uid):
    """Return True if `uid` is considered valid.

    If ``pynetdicom._config.ENFORCE_UID_CONFORMANCE = True`` then the following
    rules apply:

    * 1-64 characters, inclusive
    * Each component may not start with 0 unless the component itself is 0
    * Components are separated by '.'
    * Valid component characters are 0-9 of the Basic G0 Set of the
      International Reference Version of ISO 646:1990 (ASCII)

    If ``pynetdicom._config.ENFORCE_UID_CONFORMANCE = False`` then the
    following rules apply:

    * 1-64 characters, inclusive

    Parameters
    ----------
    uid : pydicom.uid.UID
        The UID to check for validity.

    Returns
    -------
    bool
        True if the value is considered valid, False otherwise.
    """
    if _config.ENFORCE_UID_CONFORMANCE:
        return uid.is_valid

    if 0 < len(uid) < 65:
        return True

    return False
