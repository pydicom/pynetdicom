"""Utility classes and functions for the apps."""

import logging
import os
from struct import pack

from pydicom import dcmread
from pydicom.datadict import tag_for_keyword, repeater_has_keyword, get_entry
from pydicom.dataset import Dataset
from pydicom.filewriter import write_file_meta_info
from pydicom.tag import Tag
from pydicom.uid import DeflatedExplicitVRLittleEndian

from pynetdicom.dsutils import encode


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
    ds = Dataset()

    if args.file:
        try:
            with open(args.file, 'rb') as fp:
                ds = dcmread(fp, force=True)
        except Exception as exc:
            if logger:
                logger.error(
                    'Cannot read input file {0!s}'.format(args.file)
                )
            raise exc

        try:
            # Only way to check for a bad decode is to iterate the dataset
            ds.iterall()
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
                ds = elem.update(ds)
        except Exception as exc:
            if logger:
                logger.error(
                    'Exception raised trying to parse the supplied keywords'
                )
            raise exc

    return ds


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

    Elements with VM > 1 can be set by using '\\' (where appropriate)

    >>> ElementPath('AcquisitionIndex=1\\2\\3\\4')

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
            * If the element VR is SL, SS, SV, UL, US or UV then the ``str``
              will be converted to an ``int`` using ``int(value)``.
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
        _int = ['SL', 'SS', 'SV', 'UL', 'US', 'UV']
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


def get_files(fpaths, recurse=False):
    """Return a list of files.

    Parameters
    ----------
    fpaths : list of str
        A list of the files and/or directories to search.
    recurse : bool, optional
        Recursively search any directories (default: ``False``).

    Returns
    -------
    list of str, list of str
        A list of the files found and a list of files not found.
    """
    out = []
    bad = []
    for fpath in fpaths:
        if os.path.isfile(fpath):
            out.append(fpath)
        elif os.path.isdir(fpath):
            if recurse:
                for root, dirs, files in os.walk(fpath):
                    out += [os.path.join(root, pp) for pp in files]
            else:
                out += [os.path.join(fpath, pp) for pp in os.listdir(fpath)]
        else:
            bad.append(fpath)

    return sorted(list(set([pp for pp in out if os.path.isfile(pp)]))), bad


def setup_logging(args, app_name):
    """Return the application logger.

    Parameters
    ----------
    args : argparse.Namespace
        The namespace containing the keywords and/or dataset file to use.
        The namespace should contain ``args.quiet``, ``args.verbose``.
        ``args.debug``, ``args.log_level`` and ``args.log_config`` attributes.
    app_name : str
        The name of the application.

    Returns
    -------
    logger : logging.Logger, optional
        The logger to use for logging.
    """
    formatter = logging.Formatter('%(levelname).1s: %(message)s')

    # Setup pynetdicom library's logging
    pynd_logger = logging.getLogger('pynetdicom')
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    pynd_logger.addHandler(handler)
    pynd_logger.setLevel(logging.ERROR)

    # Setup application's logging
    app_logger = logging.Logger(app_name)
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    app_logger.addHandler(handler)
    app_logger.setLevel(logging.ERROR)

    if args.log_type == 'q':
        app_logger.handlers = []
        app_logger.addHandler(logging.NullHandler())
        pynd_logger.handlers = []
        pynd_logger.addHandler(logging.NullHandler())
    elif args.log_type == 'v':
        app_logger.setLevel(logging.INFO)
        pynd_logger.setLevel(logging.INFO)
    elif args.log_type == 'd':
        app_logger.setLevel(logging.DEBUG)
        pynd_logger.setLevel(logging.DEBUG)

    if args.log_level:
        levels = {
            'critical' : logging.CRITICAL,
            'error' : logging.ERROR,
            'warn' : logging.WARNING,
            'info' : logging.INFO,
            'debug' : logging.DEBUG
        }
        app_logger.setLevel(levels[args.log_level])
        pynd_logger.setLevel(levels[args.log_level])

    return app_logger


def handle_store(event, args, app_logger):
    """Handle a C-STORE request.

    Parameters
    ----------
    event : pynetdicom.event.event
        The event corresponding to a C-STORE request.
    args : argparse.Namespace
        The namespace containing the arguments to use. The namespace should
        contain ``args.ignore`` and ``args.output_directory`` attributes.
    app_logger : logging.Logger
        The application's logger.

    Returns
    -------
    status : pynetdicom.sop_class.Status or int
        A valid return status code, see PS3.4 Annex B.2.3 or the
        ``StorageServiceClass`` implementation for the available statuses
    """
    if args.ignore:
        return 0x0000

    try:
        ds = event.dataset
        # Remove any Group 0x0002 elements that may have been included
        ds = ds[0x00030000:]
    except Exception as exc:
        app_logger.error("Unable to decode the dataset")
        app_logger.exception(exc)
        # Unable to decode dataset
        return 0x210

    # Add the file meta information elements
    ds.file_meta = event.file_meta

    # Because pydicom uses deferred reads for its decoding, decoding errors
    #   are hidden until encountered by accessing a faulty element
    try:
        sop_class = ds.SOPClassUID
        sop_instance = ds.SOPInstanceUID
    except Exception as exc:
        app_logger.error(
            "Unable to decode the received dataset or missing 'SOP Class "
            "UID' and/or 'SOP Instance UID' elements"
        )
        app_logger.exception(exc)
        # Unable to decode dataset
        return 0xC210

    try:
        # Get the elements we need
        mode_prefix = SOP_CLASS_PREFIXES[sop_class][0]
    except KeyError:
        mode_prefix = 'UN'

    filename = '{0!s}.{1!s}'.format(mode_prefix, sop_instance)
    app_logger.info('Storing DICOM file: {0!s}'.format(filename))

    status_ds = Dataset()
    status_ds.Status = 0x0000

    # Try to save to output-directory
    if args.output_directory is not None:
        filename = os.path.join(args.output_directory, filename)
        try:
            os.makedirs(args.output_directory, exist_ok=True)
        except Exception as exc:
            app_logger.error('Unable to create the output directory:')
            app_logger.error("    {0!s}".format(args.output_directory))
            app_logger.exception(exc)
            # Failed - Out of Resources - IOError
            status_ds.Status = 0xA700
            return status_ds

    if os.path.exists(filename):
        app_logger.warning('DICOM file already exists, overwriting')

    try:
        if event.context.transfer_syntax == DeflatedExplicitVRLittleEndian:
            # Workaround for pydicom issue #1086
            with open(filename, 'wb') as f:
                f.write(b'\x00' * 128)
                f.write(b'DICM')
                f.write(write_file_meta_info(f, event.file_meta))
                f.write(encode(ds, False, True, True))
        else:
            # We use `write_like_original=False` to ensure that a compliant
            #   File Meta Information Header is written
            ds.save_as(filename, write_like_original=False)

        status_ds.Status = 0x0000  # Success
    except IOError as exc:
        app_logger.error('Could not write file to specified directory:')
        app_logger.error("    {0!s}".format(os.path.dirname(filename)))
        app_logger.exception(exc)
        # Failed - Out of Resources - IOError
        status_ds.Status = 0xA700
    except Exception as exc:
        app_logger.error('Could not write file to specified directory:')
        app_logger.error("    {0!s}".format(os.path.dirname(filename)))
        app_logger.exception(exc)
        # Failed - Out of Resources - Miscellaneous error
        status_ds.Status = 0xA701

    return status_ds


SOP_CLASS_PREFIXES = {
    '1.2.840.10008.5.1.4.1.1.2' : ('CT', 'CT Image Storage'),
    '1.2.840.10008.5.1.4.1.1.2.1' : ('CTE', 'Enhanced CT Image Storage'),
    '1.2.840.10008.5.1.4.1.1.4' : ('MR', 'MR Image Storage'),
    '1.2.840.10008.5.1.4.1.1.4.1' : ('MRE', 'Enhanced MR Image Storage'),
    '1.2.840.10008.5.1.4.1.1.128' : (
        'PT', 'Positron Emission Tomography Image Storage'
    ),
    '1.2.840.10008.5.1.4.1.1.130' : ('PTE', 'Enhanced PET Image Storage'),
    '1.2.840.10008.5.1.4.1.1.481.1' : ('RI', 'RT Image Storage'),
    '1.2.840.10008.5.1.4.1.1.481.2' : ('RD', 'RT Dose Storage'),
    '1.2.840.10008.5.1.4.1.1.481.5' : ('RP', 'RT Plan Storage'),
    '1.2.840.10008.5.1.4.1.1.481.3' : ('RS', 'RT Structure Set Storage'),
    '1.2.840.10008.5.1.4.1.1.1' : ('CR', 'Computed Radiography Image Storage'),
    '1.2.840.10008.5.1.4.1.1.6.1' : ('US', 'Ultrasound Image Storage'),
    '1.2.840.10008.5.1.4.1.1.6.2' : ('USE', 'Enhanced US Volume Storage'),
    '1.2.840.10008.5.1.4.1.1.12.1' : (
        'XA', 'X-Ray Angiographic Image Storage'
    ),
    '1.2.840.10008.5.1.4.1.1.12.1.1' : ('XAE', 'Enhanced XA Image Storage'),
    '1.2.840.10008.5.1.4.1.1.20' : ('NM', 'Nuclear Medicine Image Storage'),
    '1.2.840.10008.5.1.4.1.1.7' : ('SC', 'Secondary Capture Image Storage'),
}
