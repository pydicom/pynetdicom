"""Utility classes and functions for the apps."""

from struct import pack

from pydicom.datadict import tag_for_keyword, repeater_has_keyword, get_entry
from pydicom.dataset import Dataset
from pydicom.tag import Tag


def create_query(args, logger):
    """
    Parameters
    ----------
    args:
    logger
    """
    query = Dataset()

    # Import query dataset
    if args.file:
        # Check file exists and is readable and DICOM
        try:
            with open(args.file, 'rb') as fp:
                query = dcmread(fp, force=True)
                # Only way to check for a bad decode is to iterate the dataset
                query.iterall()
        except IOError as exc:
            logger.error(
                'Unable to read the file: {}'.format(args.file)
            )
            logger.exception(exc)
            sys.exit()
        except Exception as exc:
            logger.error(
                'Exception raised decoding the file, the file may be '
                'corrupt, non-conformant or may not be DICOM {}'
                .format(args.file)
            )
            logger.exception(exc)
            sys.exit()

    if args.keyword:
        try:
            elements = [ElementPath(ii) for ii in args.keyword]

            for elem in elements:
                query = elem.update(query)
        except Exception as exc:
            logger.error(
                'Exception raised trying to parse the supplied keywords'
            )
            logger.exception(exc)

    return query


class ElementPath(object):
    """Class for parsing DICOM data elements defined using strings.

    *Format*

    "ElementKeyword="
    "ElementKeyword=some text value"
    "ElementKeyword=some\\text\\values"
    "ElementKeyword=10023"
    "ElementKeyword=10023\\100029"
    "ElementKeyword=-1.45"
    "ElementKeyword=-1.45\\1.928"

    "SequenceKeyword="
    "SequenceKeyword[0]="
    "SequenceKeyword[0].ElementKeyword="
    "SequenceKeyword[0].ElementKeyword=value"
    "SequenceKeyword[0].SequenceKeyword2="
    "SequenceKeyword[0].SequenceKeyword2[0]="
    "SequenceKeyword[0].SequenceKeyword2[0].ElementKeyword="
    "SequenceKeyword[0].SequenceKeyword2[0].ElementKeyword=value"

    and so on...

    When specifying sequence items, new items can only be added if the previous
    item(s) in the sequence already exist. For example the following is
    invalid:

    "Sequence[1].Element=1"

    While this is valid:

    "Sequence[0].Element=1"
    "Sequence[1].Element=2"

    The element tag as "(gggg,eeee)" can be used instead of the keyword,
    where gggg is the tag's group and eeee is the tag's element. Its also
    possible to mix keywords and tags:

    "(gggg,eeee)="
    "(gggg,eeee)[0].Element=1"
    "SequenceElement[0].(gggg,eeee)=2"
    """
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
            'AE', 'AS', 'AT', 'CS', 'DA', 'DS', 'DT', 'IS', 'LO', 'LT', 'PN',
            'SH', 'ST', 'TM', 'UC', 'UI', 'UR', 'UT'
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
            value = None
        else:
            # Convert to byte, assuming str is in hex
            value = [
                value[ii] + value[ii + 1] for ii in range(0, len(value), 2)
            ]
            value = [int(ii, 16) for ii in value]
            value = pack('{}B'.format(len(value)), *value)

        self._value = value

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

        if '=' in value:
            self.value = elem_value

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

            item_nr = int(self.components[0][start + 1:end])
            if item_nr < 0:
                raise ValueError(
                    'Invalid element component: sequence item index must be '
                    'at least 0'
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

        raise ValueError(
            "Unable to parse element '{}'".format(self.components[0])
        )

    def update(self, ds):
        """Update a dataset with the element.

        Parameters
        ----------
        ds : pydicom.dataset.Dataset
            The dataset to update.

        Returns
        -------
        pydicom.dataset.Dataset
            The updated dataset.

        Raises
        ------
        ValueError
            If unable to update the dataset.
        """
        exc_nonseq = ValueError(
            "Unable to update a dataset with non-sequential indexing of "
            "Sequence items (e.g. SequenceElement[1] must be preceeded by "
            "SequenceElement[0])"
        )

        if self.tag not in ds:
            # Add new element or sequence to dataset
            if self.is_sequence:
                if self.item_nr == 0:
                    # Add empty sequence
                    ds.add_new(self.tag, self.VR, [])
                else:
                    # SequenceElement[N > 0]
                    raise exc_nonseq

                # SequenceElement=
                if self.child is None:
                    return ds
            else:
                # Element=(value)
                ds.add_new(self.tag, self.VR, self.value)
                return ds

            nr_items = len(ds[self.tag].value)
            if nr_items - self.item_nr == 0:
                # SequenceElement[0]
                ds[self.tag].value.append(Dataset())
            else:
                # New SequenceElement[N > 0] not allowed
                raise exc_nonseq

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
                # New SequenceElement[N + more than 1]
                raise exc_nonseq

        if self.child:
            self.child.update(ds[self.tag].value[self.item_nr])

        return ds

    @property
    def VR(self):
        """Return the element's VR as str."""
        return self._entry[0]

    @property
    def VM(self):
        """Return the element's VM as str."""
        return self._entry[1]
