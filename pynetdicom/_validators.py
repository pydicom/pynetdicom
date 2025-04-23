"""Validation functions used by pynetdicom"""

import logging
import unicodedata

from pydicom.uid import UID


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

    if not 0 < len(value):
        return False, "must not be an empty str"

    if not len(value) < 65:
        return False, "must not exceed 64 characters"

    return True, ""
