"""Validation functions used by pynetdicom"""

from collections import OrderedDict
import logging
from typing import Union, Dict, Optional, cast
import unicodedata

from pydicom.dataset import Dataset
from pydicom.uid import UID


LOGGER = logging.getLogger('pynetdicom._validators')


def validate_ae(value: str) -> bool:
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
    bool
        ``True`` if the value is conformant to the DICOM Standard, ``False``
        otherwise.
    """
    if not isinstance(value, str):
        LOGGER.warning("Invalid AE value: must be str")
        return False

    if len(value) > 16:
        LOGGER.warning("Invalid AE value: must not exceed 16 characters")
        return False

    # All characters use ASCII
    if not value.isascii():
        LOGGER.warning("Invalid AE value: must only contain ASCII characters")
        return False

    # Unicode category: 'Cc' is control characters
    invalid = [c for c in value if unicodedata.category(c)[0] == 'C']
    if invalid or '\\' in value:
        LOGGER.warning(
            "Invalid AE value: must not contain control characters or "
            "backslashes"
        )
        return False

    return True


def validate_ui(value: UID) -> bool:
    from pynetdicom import _config

    value = UID(value)

    if _config.ENFORCE_UID_CONFORMANCE:
        return value.is_valid

    return 0 < len(value) < 65
