"""Validation functions used by pynetdicom"""

import logging
from typing import TYPE_CHECKING
import unicodedata

from pydicom.uid import UID

if TYPE_CHECKING:  # pragma: no cover
    from pydicom.dataset import Dataset

LOGGER = logging.getLogger(__name__)


def validate_ae(value: str) -> tuple[bool, str]:
    """Return ``True`` if `value` is a conformant **AE** value.

    An **AE** value:

    * Must be no more than 16 characters
    * Leading and trailing spaces are not significant
    * May only use ASCII characters, excluding ``0x5C`` (backslash) and all
      control characters

    Parameters
    ----------
    value : str
        The **AE** value to check.

    Returns
    -------
    tuple[bool, str]
        A tuple of (bool, str), with the first item being ``True`` if the
        value is conformant to the DICOM Standard and ``False`` otherwise and
        the second item being a short description of why the validation failed
        or ``''`` if validation was successful.
    """
    if not isinstance(value, str):
        return False, "must be str"

    if len(value) > 16:
        return False, "must not exceed 16 characters"

    # All characters use ASCII
    if not value.isascii():
        return False, "must only contain ASCII characters"

    # Unicode category: 'Cc' is control characters
    invalid = [c for c in value if unicodedata.category(c)[0] == "C"]
    if invalid or "\\" in value:
        return False, "must not contain control characters or backslashes"

    return True, ""


def validate_ui(value: UID) -> tuple[bool, str]:
    from pynetdicom import _config

    if not isinstance(value, str):
        return False, "must be pydicom.uid.UID"

    value = UID(value)

    if _config.ENFORCE_UID_CONFORMANCE:
        if value.is_valid:
            return True, ""

        return False, "UID is non-conformant"

    if not len(value):
        return False, "must not be an empty str"

    if len(value) > 64:
        return False, "must not exceed 64 characters"

    return True, ""


# The hierarchical Query/Retrieve information models and the *Query/Retrieve
#   Level* values valid for each (PS3.4 Annex C.6). Other query models (such as
#   Modality Worklist or Unified Procedure Step) do not use *Query/Retrieve
#   Level* and so are not included here.
_QR_LEVELS = {
    # Patient Root (PS3.4 C.6.1)
    "1.2.840.10008.5.1.4.1.2.1.1": ["PATIENT", "STUDY", "SERIES", "IMAGE"],
    "1.2.840.10008.5.1.4.1.2.1.2": ["PATIENT", "STUDY", "SERIES", "IMAGE"],
    "1.2.840.10008.5.1.4.1.2.1.3": ["PATIENT", "STUDY", "SERIES", "IMAGE"],
    # Study Root (PS3.4 C.6.2) - no PATIENT level
    "1.2.840.10008.5.1.4.1.2.2.1": ["STUDY", "SERIES", "IMAGE"],
    "1.2.840.10008.5.1.4.1.2.2.2": ["STUDY", "SERIES", "IMAGE"],
    "1.2.840.10008.5.1.4.1.2.2.3": ["STUDY", "SERIES", "IMAGE"],
    # Patient/Study Only (retired, PS3.4 C.6.1/C.6.2)
    "1.2.840.10008.5.1.4.1.2.3.1": ["PATIENT", "STUDY"],
    "1.2.840.10008.5.1.4.1.2.3.2": ["PATIENT", "STUDY"],
    "1.2.840.10008.5.1.4.1.2.3.3": ["PATIENT", "STUDY"],
}


def validate_query(identifier: "Dataset", query_model: UID) -> tuple[bool, str]:
    """Return ``True`` if `identifier` is a valid query for `query_model`.

    Only the hierarchical Query/Retrieve information models (Patient Root,
    Study Root and Patient/Study Only) are checked, as these are the only
    models that use *Query/Retrieve Level* (PS3.4 Annex C.6). Any other
    `query_model` is assumed to be valid.

    Parameters
    ----------
    identifier : pydicom.dataset.Dataset
        The C-FIND, C-GET or C-MOVE request's *Identifier* dataset.
    query_model : pydicom.uid.UID
        The query model's abstract syntax UID.

    Returns
    -------
    tuple[bool, str]
        A tuple of (bool, str), with the first item being ``True`` if the
        `identifier` is a valid query for `query_model` and ``False``
        otherwise and the second item being a short description of why the
        validation failed or ``''`` if validation was successful.
    """
    levels = _QR_LEVELS.get(query_model)
    if levels is None:
        return True, ""

    if "QueryRetrieveLevel" not in identifier:
        return False, "the Identifier is missing (0008,0052) 'Query/Retrieve Level'"

    level = identifier.QueryRetrieveLevel
    if level not in levels:
        return (
            False,
            f"the Identifier's (0008,0052) 'Query/Retrieve Level' value "
            f"'{level}' is not one of {levels} allowed for the query model",
        )

    return True, ""
