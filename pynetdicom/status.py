"""Implementation of the DIMSE Status values."""

try:
    from enum import IntEnum
    HAS_ENUM = True
except ImportError:
    HAS_ENUM = False

from pydicom.dataset import Dataset

from pynetdicom._globals import (
    STATUS_SUCCESS,
    STATUS_FAILURE,
    STATUS_WARNING,
    STATUS_CANCEL,
    STATUS_PENDING,
    STATUS_UNKNOWN,
)


# Non-Service Class specific statuses - PS3.7 Annex C
GENERAL_STATUS = {
    0x0000 : (STATUS_SUCCESS, ''),
    0x0105 : (STATUS_FAILURE, 'No Such Attribute'),
    0x0106 : (STATUS_FAILURE, 'Invalid Attribute Value'),
    0x0107 : (STATUS_WARNING, 'Attribute List Error'),
    0x0110 : (STATUS_FAILURE, 'Processing Failure'),
    0x0111 : (STATUS_FAILURE, 'Duplication SOP Instance'),
    0x0112 : (STATUS_FAILURE, 'No Such SOP Instance'),
    0x0113 : (STATUS_FAILURE, 'No Such Event Type'),
    0x0114 : (STATUS_FAILURE, 'No Such Argument'),
    0x0115 : (STATUS_FAILURE, 'Invalid Argument Value'),
    0x0116 : (STATUS_WARNING, 'Attribute Value Out of Range'),
    0x0117 : (STATUS_FAILURE, 'Invalid Object Instance'),
    0x0118 : (STATUS_FAILURE, 'No Such SOP Class'),
    0x0119 : (STATUS_FAILURE, 'Class-Instance Conflict'),
    0x0120 : (STATUS_FAILURE, 'Missing Attribute'),
    0x0121 : (STATUS_FAILURE, 'Missing Attribute Value'),
    0x0122 : (STATUS_FAILURE, 'Refused: SOP Class Not Supported'),
    0x0123 : (STATUS_FAILURE, 'No Such Action'),
    0x0124 : (STATUS_FAILURE, 'Refused: Not Authorised'),
    0x0210 : (STATUS_FAILURE, 'Duplicate Invocation'),
    0x0211 : (STATUS_FAILURE, 'Unrecognised Operation'),
    0x0212 : (STATUS_FAILURE, 'Mistyped Argument'),
    0x0213 : (STATUS_FAILURE, 'Resource Limitation'),
    0xFE00 : (STATUS_CANCEL, '')
}


## SERVICE CLASS STATUSES
# Verification Service Class specific status code values
VERIFICATION_SERVICE_CLASS_STATUS = GENERAL_STATUS


# Storage Service Class specific status code values - PS3.4 Annex B.2.3
STORAGE_SERVICE_CLASS_STATUS = {
    0xB000 : (STATUS_WARNING, 'Coercion of Data Elements'),
    0xB007 : (STATUS_WARNING, 'Data Set Does Not Match SOP Class'),
    0xB006 : (STATUS_WARNING, 'Element Discarded')
}

# Ranged values
for _code in range(0xA700, 0xA7FF + 1):
    STORAGE_SERVICE_CLASS_STATUS[_code] = (STATUS_FAILURE,
                                           'Refused: Out of Resources')
for _code in range(0xA900, 0xA9FF + 1):
    STORAGE_SERVICE_CLASS_STATUS[_code] = (STATUS_FAILURE,
                                           'Data Set Does Not Match SOP Class')
for _code in range(0xC000, 0xCFFF + 1):
    STORAGE_SERVICE_CLASS_STATUS[_code] = (STATUS_FAILURE, 'Cannot Understand')

# Add the General status code values - PS3.7 9.1.1.1.9 and Annex C
STORAGE_SERVICE_CLASS_STATUS.update(GENERAL_STATUS)


# Query Retrieve - FIND specific status code values
#   PS3.4 Annex C.4.1.1.4
# Hanging Protocol - FIND specific status code values
#   PS3.4 Annex U.4.1
# Color Palette - FIND specific status code values
#   PS3.4 Annex X
# Implant Template - FIND specific status code values
#   PS3.4 Annex BB
# Defined Procedure Protocol - FIND specific status code values
#   PS3.4 Annex HH
QR_FIND_SERVICE_CLASS_STATUS = {
    0xA700 : (STATUS_FAILURE, 'Refused: Out of Resources'),
    0xA900 : (STATUS_FAILURE, 'Identifier Does Not Match SOP Class'),
    0xFF00 : (STATUS_PENDING,
              'Matches are continuing, current match supplied'),
    0xFF01 : (STATUS_PENDING, 'Matches are continuing, warning')
}

# Ranged values
for _code in range(0xC000, 0xCFFF + 1):
    QR_FIND_SERVICE_CLASS_STATUS[_code] = (STATUS_FAILURE, 'Unable to Process')

# Add the General status code values - PS3.7 Annex C
QR_FIND_SERVICE_CLASS_STATUS.update(GENERAL_STATUS)


# Query Retrieve - MOVE specific status code values
#   PS3.4 Annex C.4.2.1.5 and Annex Y.4.1.1.4
# Hanging Protocol - MOVE specific status code values
#   PS3.4 Annex U.4.2
# Color Palette - MOVE specific status code values
#   PS3.4 Annex X
# Implant Template - MOVE specific status code values
#   PS3.4 Annex BB
# Defined Procedure Protocol - MOVE specific status code values
#   PS3.4 Annex HH
QR_MOVE_SERVICE_CLASS_STATUS = {
    0xA701 : (STATUS_FAILURE,
              'Refused: Out of resources, unable to calculate '
              'number of matches'),
    0xA702 : (STATUS_FAILURE,
              'Refused: Out of resources, unable to perform sub-operations'),
    0xA801 : (STATUS_FAILURE, 'Move destination unknown'),
    0xA900 : (STATUS_FAILURE, 'Identifier does not match SOP class'),
    0xAA00 : (STATUS_FAILURE,
              "None of the frames requested were found in the SOP instance"),
    0xAA01 : (STATUS_FAILURE,
              "Unable to create new object for this SOP class"),
    0xAA02 : (STATUS_FAILURE, "Unable to extract frames"),
    0xAA03 : (STATUS_FAILURE,
              "Time-based request received for a non-time-based original "
              "SOP Instance"),
    0xAA04 : (STATUS_FAILURE, "Invalid request"),
    0xFF00 : (STATUS_PENDING, 'Sub-operations are continuing'),
    0xB000 : (STATUS_WARNING, 'Sub-operations completed, one or more failures')
}

# Ranged values
for _code in range(0xC000, 0xCFFF + 1):
    QR_MOVE_SERVICE_CLASS_STATUS[_code] = (STATUS_FAILURE, 'Unable to Process')

# Add the General status code values - PS3.7 Annex C
QR_MOVE_SERVICE_CLASS_STATUS.update(GENERAL_STATUS)


# Query Retrieve - GET specific status code values
#   PS3.4 Annex C.4.3.1.4 and Annex Y.4.2.1.4
# Hanging Protocol  - GET specific status code values
#   PS3.4 Annex U.4.3
# Color Palette - GET specific status code values
#   PS3.4 Annex X
# Implant Template - GET specific status code values
#   PS3.4 Annex BB
# Defined Procedure Protocol - GET specific status code values
#   PS3.4 Annex HH
QR_GET_SERVICE_CLASS_STATUS = {
    0xA701 : (STATUS_FAILURE,
              'Refused: Out of resources, unable to calculate '
              'number of matches'),
    0xA702 : (STATUS_FAILURE,
              'Refused: Out of resources, unable to perform sub-operations'),
    0xA900 : (STATUS_FAILURE, 'Identifier does not match SOP class'),
    0xAA00 : (STATUS_FAILURE,
              "None of the frames requested were found in the SOP instance"),
    0xAA01 : (STATUS_FAILURE,
              "Unable to create new object for this SOP class"),
    0xAA02 : (STATUS_FAILURE, "Unable to extract frames"),
    0xAA03 : (STATUS_FAILURE,
              "Time-based request received for a non-time-based original "
              "SOP Instance"),
    0xAA04 : (STATUS_FAILURE, "Invalid request"),
    0xFF00 : (STATUS_PENDING, 'Sub-operations are continuing'),
    0xB000 : (STATUS_WARNING,
              'Sub-operations complete, one or more failures or warnings'),
}

# Ranged values
for _code in range(0xC000, 0xCFFF + 1):
    QR_GET_SERVICE_CLASS_STATUS[_code] = (STATUS_FAILURE, 'Unable to Process')

# Add the General status code values - PS3.7 Annex C
QR_GET_SERVICE_CLASS_STATUS.update(GENERAL_STATUS)


# Modality Worklist Service Class specific status code values
#   PS3.4 Annex K
MODALITY_WORKLIST_SERVICE_CLASS_STATUS = {
    0xA700 : (STATUS_FAILURE, 'Refused: Out of resources'),
    0xA900 : (STATUS_FAILURE, 'Identifier does not match SOP class'),
    0xFF00 : (STATUS_PENDING,
              "Matches are continuing - current match is supplied and any "
              "Optional Keys were supported in the same manner as Required "
              "Keys"),
    0xFF01 : (STATUS_PENDING,
              "Matches are continuing - warning that one or more Optional "
              "Keys were not supported for existence for this Identifier"),
}

# Ranged values
for _code in range(0xC000, 0xCFFF + 1):
    MODALITY_WORKLIST_SERVICE_CLASS_STATUS[_code] = (STATUS_FAILURE,
                                                     'Unable to Process')

# Add the General status code values - PS3.7 Annex C
MODALITY_WORKLIST_SERVICE_CLASS_STATUS.update(GENERAL_STATUS)


# Relevant Patient Information Query Service Class specific status code values
# PS3.4 Annex Q
RELEVANT_PATIENT_SERVICE_CLASS_STATUS = {
    0xA700 : (STATUS_FAILURE, "Out of resources"),
    0xA900 : (STATUS_FAILURE, "Identifier doesn't match SOP Class"),
    0xC000 : (STATUS_FAILURE, "Unable to process"),
    0xC100 : (STATUS_FAILURE, "More than one match found"),
    0xC200 : (STATUS_FAILURE, "Unable to support requested template"),
    0xFF00 : (STATUS_PENDING, "Current match is supplied"),
}
RELEVANT_PATIENT_SERVICE_CLASS_STATUS.update(GENERAL_STATUS)


# Substance Administration Query Service Class specific status code values
#   PS3.4 Annex V
SUBSTANCE_ADMINISTRATION_SERVICE_CLASS_STATUS = {
    0xA700 : (STATUS_FAILURE, "Out of resources"),
    0xA900 : (STATUS_FAILURE, "Data set doesn't match SOP Class"),
    0xFF00 : (STATUS_PENDING,
              "Matches are continuing, current match is supplied and any "
              "Optional Keys were supported in the same manner as Required "
              "Keys"),
    0xFF01 : (STATUS_PENDING,
              "Matches are continuing, warning that one or more Optional "
              "Keys were not supported for existence for this Identifier")
}

# Ranged values
for _code in range(0xC000, 0xCFFF + 1):
    SUBSTANCE_ADMINISTRATION_SERVICE_CLASS_STATUS[_code] = (
        STATUS_FAILURE, 'Unable to Process'
    )

SUBSTANCE_ADMINISTRATION_SERVICE_CLASS_STATUS.update(GENERAL_STATUS)


# Non-Patient Object Storage Service Class specific status code values
#   PS3.4 Annex GG
NON_PATIENT_SERVICE_CLASS_STATUS = {
    0xA700 : (STATUS_FAILURE, "Out of resources"),
    0xA900 : (STATUS_FAILURE, "Data set doesn't match SOP Class"),
    0xC000 : (STATUS_FAILURE, "Cannot understand"),
}
NON_PATIENT_SERVICE_CLASS_STATUS.update(GENERAL_STATUS)


# Procedure Step SOP Class specific status code values
PROCEDURE_STEP_STATUS = {
    0x0001 : (STATUS_WARNING,
              "Requested optional attributes are not supported"),
    0x0110 : (STATUS_FAILURE,
              "Performed Procedure Step object may no longer be updated"),
}
PROCEDURE_STEP_STATUS.update(GENERAL_STATUS)


# Print Job Management Service Class specific status code values
PRINT_JOB_MANAGEMENT_SERVICE_CLASS_STATUS = {
    0xB600 : (STATUS_WARNING, "Memory allocation not supported"),
    0xB601 : (STATUS_WARNING,
              "Film session printing (collation) is not supported"),
    0xB602 : (STATUS_WARNING,
              "Film Session SOP Instance hierarchy does not contain Image "
              "Box SOP Instances (empty page)"),
    0xB603 : (STATUS_WARNING,
              "Film Box SOP Instance hierarchy does not contain Image Box "
              "SOP Instances (empty page)"),
    0xB604 : (STATUS_WARNING,
              "Image size is larger than image box size, the image has been "
              "demagnified"),
    0xB605 : (STATUS_WARNING,
              "Requested minimum density or maximum density outside of "
              "printer's operating range. The print will use its respective "
              "minimum or maximum density value instead"),
    0xB609 : (STATUS_WARNING,
              "Image size is larger than the image box size, the image has "
              "been cropped to fit"),
    0xB60A : (STATUS_WARNING,
              "Image size or Combined Print Image size is larger than the "
              "image box size, image or combined print image has been "
              "decimated to fit"),
    0xC600 : (STATUS_FAILURE,
              "Film Session SOP Instance hierarchy does not contain Film Box "
              "SOP Instances"),
    0xC601 : (STATUS_FAILURE,
              "Unable to create Print Job SOP Instance; print queue is full"),
    0xC602 : (STATUS_FAILURE,
              "Unable to create Print Job SOP instance; print queue is full"),
    0xC603 : (STATUS_FAILURE, "Image size is larger than image box size"),
    0xC605 : (STATUS_FAILURE,
              "Insufficient memory in printer to store the image"),
    0xC613 : (STATUS_FAILURE,
              "Combined print image size is larger than the image box size"),
    0xC616 : (STATUS_FAILURE,
              "There is an existing film box that has not been printed and "
              "N-ACTION at the film session level is not supported. A new "
              "film box will not be created when a previous film box has not "
              "been printed"),
}
PRINT_JOB_MANAGEMENT_SERVICE_CLASS_STATUS.update(GENERAL_STATUS)


# Storage Commitment Service Class specific status code values
STORAGE_COMMITMENT_SERVICE_CLASS_STATUS = GENERAL_STATUS


# Application Event Logging Service Class specific status code values
APPLICATION_EVENT_LOGGING_SERVICE_CLASS_STATUS = {
    0xB101 : (STATUS_WARNING,
              "Specified Synchronisation Frame of Reference UID doesn't "
              "match SCP Synchronization Frame of Reference"),
    0xB102 : (STATUS_WARNING,
              "Study Instance UID coercion; event logged under a different "
              "Study Instance UID"),
    0xB104 : (STATUS_WARNING,
              "IDs inconsistent in matching a current study; event logged"),
    0xC101 : (STATUS_FAILURE,
              "Procedural logging not available for specified Study "
              "Instance UID"),
    0xC102 : (STATUS_FAILURE, "Event Information doesn't match template"),
    0xC103 : (STATUS_FAILURE, "Cannot match event to a current study"),
    0xC104 : (STATUS_FAILURE,
              "IDs inconsistent in matching a current study; event not "
              "logged"),
    0xC10E : (STATUS_FAILURE,
              "Operator not authorised to add entry to Medication "
              "Administration Record"),
    0xC110 : (STATUS_FAILURE,
              "Patient cannot be identified from Patient ID (0010,0020) or "
              "Admission ID (0038,0010)"),
    0xC111 : (STATUS_FAILURE,
              "Update of Medication Administration Record failed"),
}
APPLICATION_EVENT_LOGGING_SERVICE_CLASS_STATUS.update(GENERAL_STATUS)


# Media Creation Management Service Class specific status code values
MEDIA_CREATION_MANAGEMENT_SERVICE_CLASS_STATUS = {
    0x0001 : (STATUS_WARNING,
              "Requested optional Attributes are not supported"),
    0xA510 : (STATUS_FAILURE,
              "An Initiate Media Creation action has already been received "
              "for this SOP Instance"),
    0xC201 : (STATUS_FAILURE, "Media creation request already completed"),
    0xC202 : (STATUS_FAILURE,
              "Media creation request already in progress and cannot be "
              "interrupted"),
    0xC203 : (STATUS_FAILURE, "Cancellation denied for unspecified reason"),
}
MEDIA_CREATION_MANAGEMENT_SERVICE_CLASS_STATUS.update(GENERAL_STATUS)


# Unified Procedure Step Service specific status code values
UNIFIED_PROCEDURE_STEP_SERVICE_CLASS_STATUS = {}
# Ranged values
for _code in range(0xC000, 0xCFFF + 1):
    UNIFIED_PROCEDURE_STEP_SERVICE_CLASS_STATUS[_code] = (
        STATUS_FAILURE, 'Unable to Process'
    )

UNIFIED_PROCEDURE_STEP_SERVICE_CLASS_STATUS.update({
    0x0001 : (STATUS_WARNING,
              "Requested optional attributes are not supported"),
    0xA700 : (STATUS_FAILURE, "Out of resources"),
    0xA900 : (STATUS_FAILURE, "Identifier doesn't match SOP Class"),
    0xB300 : (STATUS_WARNING, "The UPS was created with modifications"),
    0xB301 : (STATUS_WARNING, "Deletion lock not granted"),
    0xB304 : (STATUS_WARNING,
              "The UPS is already in the requested state of CANCELED"),
    0xB305 : (STATUS_WARNING, "Coerced invalid values to valid values"),
    0xB306 : (STATUS_WARNING,
              "The UPS is already in the requested state of COMPLETED"),
    0xC300 : (STATUS_FAILURE, "The UPS may no longer be updated"),
    0xC301 : (STATUS_FAILURE, "The correct Transaction UID was not provided"),
    0xC302 : (STATUS_FAILURE, "The UPS is already IN PROGRESS"),
    0xC303 : (STATUS_FAILURE,
              "The UPS may only become SCHEDULED via N-CREATE, not N-SET or "
              "N-ACTION"),
    0xC304 : (STATUS_FAILURE,
              "The UPS has not met final state requirements for the "
              "requested state change"),
    0xC307 : (STATUS_FAILURE,
              "Specified SOP Instance UID does not exist or is not a UPS "
              "Instance managed by this SCP"),
    0xC308 : (STATUS_FAILURE, "Receiving AE-TITLE is unknown to this SCP"),
    0xC309 : (STATUS_FAILURE,
              "The provided value of UPS State was not SCHEDULED"),
    0xC310 : (STATUS_FAILURE, "The UPS is not yet in the IN PROGRESS state"),
    0xC311 : (STATUS_FAILURE, "The UPS is already COMPLETED"),
    0xC312 : (STATUS_FAILURE, "The performer cannot be contacted"),
    0xC313 : (STATUS_FAILURE, "Performer chooses not to cancel"),
    0xC314 : (STATUS_FAILURE,
              "Specified action is not appropriate for specified instance"),
    0xC315 : (STATUS_FAILURE, "SCP does not support Event Reports"),
    0xFF00 : (STATUS_PENDING,
              "Matches are continuing - current match is supplied an any "
              "Optional Keys were supported in the same manner as Required "
              "Keys"),
    0xFF01 : (STATUS_PENDING,
              "Matches are continuing - current match is supplied an any "
              "Optional Keys were not supported for existence for this "
              "Identifier"),
})
UNIFIED_PROCEDURE_STEP_SERVICE_CLASS_STATUS.update(GENERAL_STATUS)


# RT Machine Verification Service Class specific status code values
RT_MACHINE_VERIFICATION_SERVICE_CLASS_STATUS = {
    0xC112 : (STATUS_FAILURE,
              "No such object instance - applicable Machine Verification "
              "instance not found"),
    0xC221 : (STATUS_FAILURE,
              "The Referenced Fraction Group Number does not exist in "
              "the referenced plan"),
    0xC222 : (STATUS_FAILURE,
              "No beams exist within the referenced fraction group"),
    0xC223 : (STATUS_FAILURE,
              "SCU already verifying and cannot currently process this "
              "request"),
    0xC224 : (STATUS_FAILURE,
              "Referenced Beam Number not found within the referenced "
              "Fraction Group"),
    0xC225 : (STATUS_FAILURE,
              "Referenced device or accessory not supported"),
    0xC226 : (STATUS_FAILURE,
              "Referenced device or accessory not found within the "
              "referenced beam"),
    0xC227 : (STATUS_FAILURE,
              "No such object instance - Referenced RT Plan not found"),
}
RT_MACHINE_VERIFICATION_SERVICE_CLASS_STATUS.update(GENERAL_STATUS)


def code_to_status(code):
    """Return a :class:`~pydicom.dataset.Dataset` with a *Status* element
    value of `code`.
    """
    if isinstance(code, int) and code >= 0:
        ds = Dataset()
        ds.Status = code
        return ds
    else:
        raise ValueError("'code' must be a positive integer.")


def code_to_category(code):
    """Return a *Status* category as :class:`str` or ``'Unknown'`` if not
    recognised.
    """
    # pylint: disable=too-many-return-statements
    if isinstance(code, int) and code >= 0:
        if code == 0x0000:
            return STATUS_SUCCESS
        elif code in [0xFF00, 0xFF01]:
            return STATUS_PENDING
        elif code == 0xFE00:
            return STATUS_CANCEL
        elif code in [0x0105, 0x0106, 0x0110, 0x0111, 0x0112, 0x0113, 0x0114,
                      0x0115, 0x0117, 0x0118, 0x0119, 0x0120, 0x0121, 0x0122,
                      0x0123, 0x0124, 0x0210, 0x0211, 0x0212, 0x0213]:
            return STATUS_FAILURE
        elif code in range(0xA000, 0xB000):
            return STATUS_FAILURE
        elif code in range(0xC000, 0xD000):
            return STATUS_FAILURE
        elif code in [0x0107, 0x0116]:
            return STATUS_WARNING
        elif code in range(0xB000, 0xC000):
            return STATUS_WARNING
        elif code == 0x0001:
            return STATUS_WARNING

        return STATUS_UNKNOWN
    else:
        raise ValueError("'code' must be a positive integer.")


if HAS_ENUM:
    class Status(IntEnum):
        """Constants for common status codes.

        .. versionadded:: 1.5
        .. warning::

            Not available with Python 2 unless the
            `enum34 <https://pypi.org/project/enum34/>`_ package is installed

        New constants can be added with the ``Status.add(name, code)`` method but
        the documentation for it is missing due to a bug in Sphinx. `name` is
        the variable name of the constant to add as a :class:`str` and `code` is
        the corresponding status code as an :class:`int`.

        Examples
        --------

        ::

            from pynetdicom.status import Status

            # Customise the class
            Status.add('UNABLE_TO_PROCESS', 0xC000)

            def handle_store(event):
                try:
                    event.dataset.save_as('temp.dcm')
                except:
                    return Status.UNABLE_TO_PROCESS

                return Status.SUCCESS

        """
        SUCCESS = 0x0000
        """``0x0000`` - Success"""
        CANCEL = 0xFE00
        """``0xFE00`` - Operation terminated"""
        PENDING = 0xFF00
        """``0xFF00`` - Matches or sub-operations are continuing"""
        MOVE_DESTINATION_UNKNOWN = 0xA801
        """``0xA801`` - Move destination unknown"""

        @classmethod
        def add(cls, name, code):
            """Add a new constant to `Status`.

            Parameters
            ----------
            name : str
                The name of the constant to add.
            code : int
                The status code corresponding to the name.
            """
            setattr(cls, name, code)
