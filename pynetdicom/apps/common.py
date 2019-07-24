"""Utility classes and functions for the apps."""

import logging
import os
from struct import pack

from pydicom import dcmread
from pydicom.datadict import tag_for_keyword, repeater_has_keyword, get_entry
from pydicom.dataset import Dataset
from pydicom.tag import Tag


def create_dataset(args, logger=None):
    """Return a new or updated dataset.

    The DICOM dataset at ``args.file='path/to/file'`` will be read and updated
    using the values in ``args.keyword`` (if specified). If ``args.file=None``
    then a new dataset will be created using the values in ``args.keyword``.

    Parameters
    ----------
    args : argparse.Namespace
        The namespace containing the keywords and/or dataset file to use.
        The namespace should contain ``args.keyword=['list', 'of', 'str']``
        and ``file='path/to/dataset'`` attributes.
    logger : logging.Logger, optional
        The logger to use for logging.

    Returns
    -------
    pydicom.dataset.Dataset
        The created and/or updated dataset.
    """
    query = Dataset()

    if args.file:
        try:
            with open(args.file, 'rb') as fp:
                query = dcmread(fp, force=True)
                # Only way to check for a bad decode is to iterate the dataset
                query.iterall()
        except IOError as exc:
            if logger:
                logger.error(
                    'Unable to read the file: {}'.format(args.file)
                )
            raise exc
        except Exception as exc:
            if logger:
                logger.error(
                    'Exception raised decoding the file, the file may be '
                    'corrupt, non-conformant or may not be DICOM'
                )
            raise exc

    if args.keyword:
        try:
            elements = [ElementPath(path) for path in args.keyword]
            for elem in elements:
                query = elem.update(query)
        except Exception as exc:
            if logger:
                logger.error(
                    'Exception raised trying to parse the supplied keywords'
                )
            raise exc

    return query


class ElementPath(object):
    """Class for parsing DICOM data elements defined using a string path.

    **Path Format**

    The path for the element is defined as
    ``{element(item number).}*element=value``.

    Examples
    --------

    Empty (0010,0010) *Patient Name* element

    >>> ElementPath('PatientName=')
    >>> ElementPath('(0010,0010)=')

    *Patient Name* set to ``CITIZEN^Jan``

    >>> ElementPath('PatientName=CITIZEN^Jan')
    >>> ElementPath('(0010,0010)=CITIZEN^Jan')

    Numeric VRs like (0028,0011) *Columns* are converted to either ``int``
    or ``float``.

    >>> ElementPath('Columns=1024')

    Byte VRs like (7fe0,0010) *Pixel Data* are converted to bytes

    >>> ElementPath('PixelData=00ffea08')

    Elements with VM > 1 can be set by using '\' (where appropriate)

    >>> ElementPath('AcquisitionIndex=1\2\3\4')

    Empty (300a,00b0) *Beam Sequence*

    >>> ElementPath('BeamSequence=')
    >>> ElementPath('(300a,00b0)=')

    *Beam Sequence* with one empty item

    >>> ElementPath('BeamSequence[0]=')

    *Beam Sequence* with one non-empty item

    >>> ElementPath('BeamSequence[0].PatientName=CITIZEN^Jan')

    Nested sequence items

    >>> ElementPath('BeamSequence[0].BeamLimitingDeviceSequence[0].NumberOfLeafJawPairs=1')

    *Beam Sequence* with 4 empty items

    >>> ElementPath('BeamSequence[3]=')
    """
    def __init__(self, path, parent=None):
        """Initialise a new ElementPath.

        Parameters
        ----------
        path : str
            The string describing the complete path of a DICOM data element.
        parent : ElementPath or None
            The parent of the current ``ElementPath`` (if there is one) or
            ``None``.
        """
        # Default pydicom empty value
        self._value = ''

        self.components = path
        self._parent = parent

    @property
    def child(self):
        """Return the current object's child ElementPath (or None).

        Returns
        -------
        ElementPath or None
            If the path ends with the current object then returns ``None``,
            otherwise returns an ``ElementPath`` instance for the next
            component of the path.
        """
        if len(self.components) == 1:
            return None

        return ElementPath('.'.join(self.components[1:]), self)

    @property
    def components(self):
        """Return the current Element's components as list of str.

        Returns
        -------
        list of str
            The path starting from the current object.
        """
        return self._components

    @components.setter
    def components(self, path):
        """Set the element's components str.

        Parameters
        ----------
        str
            The path to use for the current object.
        """
        value = ''
        if '=' in path:
            path, value = path.split('=', 1)

        self._components = path.split('.')

        # Parse current component and set attributes accordingly
        tag = self.tag
        try:
            # Try DICOM dictionary for public elements
            self._entry = get_entry(tag)
        except Exception as exc:
            # Private element
            self._entry = ('UN', '1', 'Unknown', False, 'Unknown')

        # Try to convert value to appropriate type
        self.value = value

    @property
    def is_sequence(self):
        """Return True if the current component is a sequence."""
        start = self.components[0].find('[')
        end = self.components[0].find(']')
        if start >= 0 or end >= 0:
            is_valid = True
            if not (start >= 0 and end >= 0):
                is_valid = False
            if start > end:
                is_valid = False
            if start + 1 == end:
                is_valid = False

            if is_valid:
                try:
                    item_nr = int(self.components[0][start + 1:end])
                    if item_nr < 0:
                        is_valid = False
                except:
                    is_valid = False

            if not is_valid:
                raise ValueError(
                    "Element path contains an invalid component: '{}'"
                    .format(self.components[0])
                )
            self._item_nr = item_nr

            return True

        return False

    @property
    def item_nr(self):
        """Return the element's sequence item number.

        Returns
        -------
        int or None
            If the current component of the path is a sequence then returns
            the item number, otherwise returns ``None``.
        """
        if self.is_sequence:
            return self._item_nr

        return None

    @property
    def keyword(self):
        """Return the element's keyword as a str.

        Returns
        -------
        str
            The element's keyword if an official DICOM element, otherwise
            'Unknown'.
        """
        return self._entry[4]

    @property
    def parent(self):
        """Return the current object's parent ElementPath.

        Returns
        -------
        ElementPath or None
            If the current component was part of a larger path then returns
            the previous component as an ``ElementPath``, otherwise returns
            ``None``.
        """
        return self._parent

    @property
    def tag(self):
        """Return the element's tag as a pydicom.tag.Tag."""
        tag = self.components[0]
        if self.is_sequence:
            tag = tag.split('[')[0]

        # (gggg,eeee) based tag
        if ',' in tag:
            group, element = tag.split(',')
            if '(' in group:
                group = group.replace('(', '')
            if ')' in element:
                element = element.replace(')', '')

            if len(group) != 4 or len(element) != 4:
                raise ValueError(
                    "Unable to parse element path component: '{}'"
                    .format(self.components[0])
                )

            return Tag(group, element)

        # From this point on we assume that a keyword was supplied
        kw = tag
        # Keyword based tag - private keywords not allowed
        if repeater_has_keyword(kw):
            raise ValueError(
                "Repeating group elements must be specified using "
                "(gggg,eeee): '{}'".format(self.components[0])
            )

        tag = tag_for_keyword(kw)
        # Test against None as 0x00000000 is a valid tag
        if tag is not None:
            return Tag(tag)

        raise ValueError(
            "Unable to parse element path component: '{}'"
            .format(self.components[0])
        )

    def update(self, ds):
        """Return a pydicom Dataset after updating it.

        Parameters
        ----------
        ds : pydicom.dataset.Dataset
            The dataset to update.

        Returns
        -------
        pydicom.dataset.Dataset
            The updated dataset.
        """
        if self.tag not in ds:
            # Add new element or sequence to dataset
            if self.is_sequence:
                # Add new SequenceElement with no items
                ds.add_new(self.tag, self.VR, [])

                # Add [N] empty items
                if self.item_nr is not None:
                    for ii in range(self.item_nr + 1):
                        ds[self.tag].value.append(Dataset())

                # SequenceElement=
                if self.child is None:
                    return ds
            else:
                # Element=(value)
                ds.add_new(self.tag, self.VR, self.value)
                return ds

        else:
            elem = ds[self.tag]
            # Either update or add new item
            if not self.is_sequence:
                # Update Element=(value)
                elem.value = self.value
                return ds

            # Check if we need to add a new item to an existing sequence
            # SequenceElement currently has N items
            nr_items = len(elem.value)
            if nr_items - self.item_nr == 0:
                # New SequenceElement[N + 1] item
                elem.value.append(Dataset())
            elif nr_items < self.item_nr:
                for ii in range(self.item_nr - nr_items):
                    elem.value.append(Dataset())

        if self.child:
            self.child.update(ds[self.tag].value[self.item_nr])

        return ds

    @property
    def value(self):
        """Return the value assigned to the data element."""
        if self.parent is None:
            return self._value

        parent = self.parent
        while parent.parent:
            parent = parent.parent

        return parent._value

    @value.setter
    def value(self, value):
        """Set the element's value.

        Parameters
        ----------
        value : str
            A string representation of the value to use for the element.

            * If the element VR is AE, AS, AT, CS, DA, DS, DT, IS, LO, LT, PN,
              SH, ST, TM, UC, UI, UR or UT then no conversion will be
              performed.
            * If the element VR is SL, SS, UL or US then the ``str`` will be
              converted to an ``int`` using ``int(value)``.
            * If the element VR is FD or FL then the ``str`` will be converted
              to a ``float`` using ``float(value)``.
            * If the VR is not one of the above then the ``str`` will be
              converted to ``bytes`` using the assumption that ``value`` is a
              string of hex bytes with the correct endianness (e.g.
              '0aff00f0ec').
        """
        _str = [
            'AE', 'AS', 'AT', 'CS', 'DA', 'DS', 'DT', 'IS', 'LO',
            'LT', 'PN', 'SH', 'ST', 'TM', 'UC', 'UI', 'UR', 'UT'
        ]
        _int = ['SL', 'SS', 'UL', 'US']
        _float = ['FD', 'FL']
        _byte = ['OB', 'OD', 'OF', 'OL', 'OW', 'OV', 'UN']

        # Try to convert value to appropriate type
        if self.VR == 'AT' and '\\' in value:
            value = value.split('\\')
        elif self.VR in _str or self.VR == 'SQ':
            pass
        elif self.VR in _int and value:
            if '\\' in value:
                value = [int(vv) for vv in value.split('\\')]
            else:
                value = int(value)
        elif self.VR in _float and value:
            if '\\' in value:
                value = [float(vv) for vv in value.split('\\')]
            else:
                value = float(value)
        elif not value:
            value = ''
        else:
            # Convert to byte, assuming str is in hex
            value = [
                value[ii] + value[ii + 1] for ii in range(0, len(value), 2)
            ]
            value = [int(ii, 16) for ii in value]
            value = pack('{}B'.format(len(value)), *value)

        self._value = value

    @property
    def VR(self):
        """Return the element's VR as str."""
        return self._entry[0]
