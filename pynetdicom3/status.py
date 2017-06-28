"""Implementation of the DIMSE Status."""

from pydicom.datadict import tag_for_keyword, dictionary_VR
from pydicom.dataset import Dataset
from pydicom.dataelem import DataElement
from pydicom.tag import Tag


class Status(Dataset):
    """Implementation of the DIMSE Status value.

    Tag = (0000, 0900), Keyword = Status, VR = US,  VM = 1

    Statuses
    --------
    Taken from PS3.7 Annex C

    Success Status Class
    ~~~~~~~~~~~~~~~~~~~~
    * 0x0000 - Success

    Pending Status Class
    ~~~~~~~~~~~~~~~~~~~~
    Service Class Specific: 0xFF00 or 0xFF01

    * (Service Class Specific) - Pending

    Cancel Status Class
    ~~~~~~~~~~~~~~~~~~~
    * 0xFE00 - Cancel

    Warning Status Class
    ~~~~~~~~~~~~~~~~~~~~
    Service Class Specific: 0x0001 or 0xBxxx
    General Annex C assigned: 0x01xx, 0x02xx

    * (Service Class Specific) - Warning
    * 0x0107 - Attribute List Error
    * 0x0116 - Attribute Value Out of Range

    Failure Status Class
    ~~~~~~~~~~~~~~~~~~~~
    Service Class Specific: 0xAxxx and 0xCxxx
    General Annex C assigned: 0x01xx and 0x02xx

    (Service Class Specific) - Error: Cannot Understand
    (Service Class Specific) - Error: Data Set Does Not Match SOP Class
    (Service Class Specific) - Failed
    (Service Class Specific) - Refused: Move Destination Unknown
    (Service Class Specific) - Refused: Out of Resources
    0x0105 - No Such Attribute
    0x0106 - Invalid Attribute Value
    0x0110 - Processing Failure
    0x0111 - Duplicate SOP Instance
    0x0112 - No Such SOP Instance
    0x0113 - No Such Event Type
    0x0114 - No Such Argument
    0x0115 - Invalid Argument Value
    0x0117 - Invalid Object Instance
    0x0118 - No Such SOP Class
    0x0119 - Class-Instance Conflict
    0x0120 - Missing Attribute
    0x0121 - Missing Attribute Value
    0x0122 - Refused: SOP Class Not Supported
    0x0123 - No Such Action Type
    0x0124 - Refused: Not Authorised
    0x0210 - Duplicate Invocation
    0x0211 - Unrecognised Operation
    0x0212 - Mistyped Argument
    0x0213 - Resources Limitation

    Attributes
    ----------
    category : str
        One of ('Success', 'Cancel', 'Warning', 'Pending', 'Failure').
    description : str
        Short summary of the status taken from the DICOM standard.
    text : str
        Longer (optional) description of the status.
    """
    def __init__(self, val, category='', description='', text=''):
        """Create a new Status.

        Parameters
        ----------
        val : int
            The status code.
        category : str
            One of ('Success', 'Cancel', 'Warning', 'Pending', 'Failure').
        description : str
            A short summary of the status, taken from the DICOM standard.
        text : str
            A longer description of the status.
        """
        Dataset.__init__(self)
        self.Status = val
        self._category = category
        self._description = description
        self.text = text

    def __eq__(self, other):
        return self.Status == other

    def __int__(self):
        return self.Status

    def __ne__(self, other):
        return not self == other

    def __setattr__(self, name, value):
        """Intercept any attempts to set a value for an instance attribute.

        If name is a DICOM keyword, set the corresponding tag and DataElement.
        Else, set an instance (python) attribute as any other class would do.

        Only group 0x0000 elements will be accepted

        Parameters
        ----------
        name : str
            The element keyword for the DataElement you wish to add/change. If
            `name` is not a DICOM element keyword then this will be the
            name of the attribute to be added/changed.
        value
            The value for the attribute to be added/changed.
        """
        tag = tag_for_keyword(name)

        # If tag is not None, found DICOM element
        if tag is not None:
            tag = Tag(tag)
            # Check to ensure group 0x0000 and Status value OK
            if tag.group != 0x0000:
                raise ValueError("Only group 0x0000 elements can be added to a" \
                                    "Status dataset")
            elif tag == 0x00000900 and not isinstance(value, int):
                raise ValueError("The value for the Status element must be a " \
                                  "positive integer")
            elif tag == 0x00000900 and value < 0:
                raise ValueError("The value for the Status element must be a " \
                                  "positive integer")
            
            # Tag not yet in Dataset
            if tag not in self:
                VR = dictionary_VR(tag)
                data_element = DataElement(tag, VR, value)

            # Already have this data_element, just changing its value
            else:  
                data_element = self[tag]
                data_element.value = value

            # Now have data_element - store it in this dict
            self[tag] = data_element

        # If tag is None, set class attribute
        else:
            super(Dataset, self).__setattr__(name, value)

    def __setitem__(self, key, value):
        """Operator for Dataset[key] = value.

        Only group 0x0000 elements will be accepted

        Parameters
        ----------
        key : int
            The tag for the element to be added to the Dataset.
        value : pydicom.dataelem.DataElement or pydicom.dataelem.RawDataElement
            The element to add to the Dataset.

        Raises
        ------
        NotImplementedError
            If `key` is a slice.
        ValueError
            If the `key` value doesn't match DataElement.tag.
        """
        if isinstance(key, slice):
            raise NotImplementedError('Slicing is not supported for setting '
                                      'Dataset elements.')

        # OK if is subclass, e.g. DeferredDataElement
        if not isinstance(value, DataElement):
            raise TypeError("Dataset contents must be DataElement instances.")

        tag = Tag(value.tag)
        if tag.group != 0x0000:
            raise ValueError("Only group 0x0000 elements can be added to a" \
                                "Status dataset")

        if key == 0x00000900 and not isinstance(value.value, int):
            raise TypeError("The value for the Status element must be a " \
                              "positive integer")
        elif key == 0x00000900 and value.value < 0:
            raise TypeError("The value for the Status element must be a " \
                              "positive integer")

        if key != tag:
            raise ValueError("DataElement.tag must match the dictionary key")
 
        dict.__setitem__(self, tag, value)

    @property
    def category(self):
        code = int(self)
        if code in GENERAL_STATUS:
            return GENERAL_STATUS[int(self)][0]
        elif code in [0xFF00, 0xFF01]:
            return 'Pending'
        elif code == 0xFE00:
            return 'Cancel'
        elif code in [0x0107, 0x0116]:
            return 'Warning'
        elif code in range(0xA000, 0xB000) or code in range(0xC000, 0xD000):
            return 'Failure'
        elif code in range(0x0100, 0x0200) or code in range(0x0200, 0x0300):
            return 'Failure'

    @property
    def description(self):
        code = int(self)
        if code in GENERAL_STATUS:
            return GENERAL_STATUS[int(self)][1]
        elif self._description != '':
            return self._description
        else:
            return ''


# Non-Service Class specific statuses - PS3.7 Annex C
GENERAL_STATUS = {0x0000 : ('Success', ''),
                  0x0105 : ('Failure', 'No Such Attribute'),
                  0x0106 : ('Failure', 'Invalid Attribute Value'),
                  0x0107 : ('Warning', 'Attribute List Error'),
                  0x0110 : ('Failure', 'Processing Failure'),
                  0x0111 : ('Failure', 'Duplication SOP Instance'),
                  0x0112 : ('Failure', 'No Such SOP Instance'),
                  0x0113 : ('Failure', 'No Such Event Type'),
                  0x0114 : ('Failure', 'No Such Argument'),
                  0x0115 : ('Failure', 'Invalid Argument Value'),
                  0x0116 : ('Warning', 'Attribute Value Out of Range'),
                  0x0117 : ('Failure', 'Invalid Object Instance'),
                  0x0118 : ('Failure', 'No Such SOP Class'),
                  0x0119 : ('Failure', 'Class-Instance Conflict'),
                  0x0120 : ('Failure', 'Missing Attribute'),
                  0x0121 : ('Failure', 'Missing Attribute Value'),
                  0x0122 : ('Failure', 'Refused: SOP Class Not Supported'),
                  0x0123 : ('Failure', 'No Such Action'),
                  0x0124 : ('Failure', 'Refused: Not Authorised'),
                  0x0210 : ('Failure', 'Duplicate Invocation'),
                  0x0211 : ('Failure', 'Unrecognised Operation'),
                  0x0212 : ('Failure', 'Mistyped Argument'),
                  0x0213 : ('Failure', 'Resources Limitation'),
                  0xFE00 : ('Cancel', '')}


## SERVICE CLASS STATUSES
# Verification Service Class specific status code values
VERIFICATION_SERVICE_CLASS_STATUS = GENERAL_STATUS


# Storage Service Class specific status code values - PS3.4 Annex B.2.3
STORAGE_SERVICE_CLASS_STATUS = {
    0xB000 : ('Warning', 'Coercion of Data Elements'),
    0xB007 : ('Warning', 'Data Set Does Not Match SOP Class'),
    0xB006 : ('Warning', 'Element Discarded')
}

# Ranged values
for code in range(0xA700, 0xA7FF + 1):
    STORAGE_SERVICE_CLASS_STATUS[code] = ('Failure',
                                          'Refused: Out of Resources')
for code in range(0xA900, 0xA9FF + 1):
    STORAGE_SERVICE_CLASS_STATUS[code] = ('Failure',
                                          'Data Set Does Not Match SOP Class')
for code in range(0xC000, 0xCFFF + 1):
    STORAGE_SERVICE_CLASS_STATUS[code] = ('Failure', 'Cannot Understand')

# Add the General status code values - PS3.7 9.1.1.1.9 and Annex C
STORAGE_SERVICE_CLASS_STATUS.update(GENERAL_STATUS)


# Query Retrieve Find Service Class specific status code values
#   PS3.4 Annex C.4.1.1.4
QR_FIND_SERVICE_CLASS_STATUS = {
    0xA700 : ('Failure', 'Refused: Out of Resources'),
    0xA900 : ('Failure', 'Identifier Does Not Match SOP Class'),
    0xFF00 : ('Pending', 'Matches are continuing, current match supplied'),
    0xFF01 : ('Pending', 'Matches are continuing, warning')
}

# Ranged values
for code in range(0xC000, 0xCFFF + 1):
    QR_FIND_SERVICE_CLASS_STATUS[code] = ('Failure',
                                                      'Unable to Process')

# Add the General status code values - PS3.7 Annex C
QR_FIND_SERVICE_CLASS_STATUS.update(GENERAL_STATUS)


# Query Retrieve Move Service Class specific status code values
#   PS3.4 Annex C.4.2.1.5
QR_MOVE_SERVICE_CLASS_STATUS = {
    0xA701 : ('Failure', 'Refused: Out of resources, unable to calculate '
                         'number of matches'),
    0xA702 : ('Failure', 'Refused: Out of resources, unable to perform '
                         'sub-operations'),
    0xA801 : ('Failure', 'Move destination unknown'),
    0xA900 : ('Failure', 'Identifier does not match SOP class'),
    0xFF00 : ('Pending', 'Sub-operations are continuing'),
}

# Ranged values
for code in range(0xC000, 0xCFFF + 1):
    QR_MOVE_SERVICE_CLASS_STATUS[code] = ('Failure', 'Unable to Process')

# Add the General status code values - PS3.7 Annex C
QR_MOVE_SERVICE_CLASS_STATUS.update(GENERAL_STATUS)


# Query Retrieve Get Service Class specific status code values
#   PS3.4 Annex C.4.3.1.4
QR_GET_SERVICE_CLASS_STATUS = {
    0xA701 : ('Failure', 'Refused: Out of resources, unable to calculate '
                         'number of matches'),
    0xA702 : ('Failure', 'Refused: Out of resources, unable to perform '
                         'sub-operations'),
    0xA900 : ('Failure', 'Identifier does not match SOP class'),
    0xFF00 : ('Pending', 'Sub-operations are continuing'),
}

# Ranged values
for code in range(0xC000, 0xCFFF + 1):
    QR_GET_SERVICE_CLASS_STATUS[code] = ('Failure', 'Unable to Process')

# Add the General status code values - PS3.7 Annex C
QR_GET_SERVICE_CLASS_STATUS.update(GENERAL_STATUS)


# Modality Worklist Service Class specific status code values
#   PS3.4 Annex FIXME
MODALITY_WORKLIST_SERVICE_CLASS_STATUS = {
    0xA700 : ('Failure', 'Refused: Out of resources'),
    0xA900 : ('Failure', 'Identifier does not match SOP class'),
    0xFF00 : ('Pending', 'Matches are continuing - current match is '
                         'supplied and any Optional Keys were supported in '
                         'the same manner as Required Keys'),
    0xFE00 : ('Pending', 'Matches are continuing - warning that one or '
                         'more Optional Keys were not supported for '
                         'existence for this Identifier'),
}
# Ranged values
for code in range(0xC000, 0xCFFF + 1):
    MODALITY_WORKLIST_SERVICE_CLASS_STATUS[code] = ('Failure',
                                                    'Unable to Process')

# Add the General status code values - PS3.7 Annex C
MODALITY_WORKLIST_SERVICE_CLASS_STATUS.update(GENERAL_STATUS)


def code_to_status(val):
    """Return a Status from a general status code `val`."""
    if val in GENERAL_STATUS:
        return Status(val, *GENERAL_STATUS[val])

    return None
