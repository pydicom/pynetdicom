"""Implementation of the DIMSE Status values."""

from pydicom.dataset import Dataset


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
for _code in range(0xA700, 0xA7FF + 1):
    STORAGE_SERVICE_CLASS_STATUS[_code] = ('Failure',
                                           'Refused: Out of Resources')
for _code in range(0xA900, 0xA9FF + 1):
    STORAGE_SERVICE_CLASS_STATUS[_code] = ('Failure',
                                           'Data Set Does Not Match SOP Class')
for _code in range(0xC000, 0xCFFF + 1):
    STORAGE_SERVICE_CLASS_STATUS[_code] = ('Failure', 'Cannot Understand')

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
for _code in range(0xC000, 0xCFFF + 1):
    QR_FIND_SERVICE_CLASS_STATUS[_code] = ('Failure', 'Unable to Process')

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
    0xB000 : ('Warning', 'Sub-operations completed, one or more failures')
}

# Ranged values
for _code in range(0xC000, 0xCFFF + 1):
    QR_MOVE_SERVICE_CLASS_STATUS[_code] = ('Failure', 'Unable to Process')

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
    0xB000 : ('Warning', 'Sub-operations complete, one or more failures or '
                         'warnings'),
}

# Ranged values
for _code in range(0xC000, 0xCFFF + 1):
    QR_GET_SERVICE_CLASS_STATUS[_code] = ('Failure', 'Unable to Process')

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
for _code in range(0xC000, 0xCFFF + 1):
    MODALITY_WORKLIST_SERVICE_CLASS_STATUS[_code] = ('Failure',
                                                     'Unable to Process')

# Add the General status code values - PS3.7 Annex C
MODALITY_WORKLIST_SERVICE_CLASS_STATUS.update(GENERAL_STATUS)


def code_to_status(code):
    """Return a Dataset with Status element matching `code`."""
    if isinstance(code, int) and code >= 0:
        ds = Dataset()
        ds.Status = code
        return ds
    else:
        raise ValueError("'code' must be a positive integer.")

def code_to_category(code):
    """Return a Status' category as a str or 'Unknown' if not recognised.

    References
    ----------
    DICOM Standard Part 7, Annex C
    DICOM Standard Part 4
    """
    # pylint: disable=too-many-return-statements
    if isinstance(code, int) and code >= 0:
        if code == 0x0000:
            return 'Success'
        elif code in [0xFF00, 0xFF01]:
            return 'Pending'
        elif code == 0xFE00:
            return 'Cancel'
        elif code in [0x0105, 0x0106, 0x0110, 0x0111, 0x0112, 0x0113, 0x0114,
                      0x0115, 0x0117, 0x0118, 0x0119, 0x0120, 0x0121, 0x0122,
                      0x0123, 0x0124, 0x0210, 0x0211, 0x0212, 0x0213]:
            return 'Failure'
        elif code in range(0xA000, 0xB000):
            return 'Failure'
        elif code in range(0xC000, 0xD000):
            return 'Failure'
        elif code in [0x0107, 0x0116]:
            return 'Warning'
        elif code in range(0xB000, 0xC000):
            return 'Warning'
        elif code == 0x0001:
            return 'Warning'

        return 'Unknown'
    else:
        raise ValueError("'code' must be a positive integer.")
