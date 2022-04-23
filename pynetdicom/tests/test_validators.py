"""Tests for the _validators module"""

import pytest

from pydicom import config as PYD_CONFIG

from pynetdicom import _config
from pynetdicom._validators import validate_ae, validate_ui


if hasattr(PYD_CONFIG, "settings"):
    PYD_CONFIG.settings.reading_validation_mode = 0


AE_REFERENCE = [
    ("", True, ""),
    ("A", True, ""),
    ("Z", True, ""),
    ("a", True, ""),
    ("z", True, ""),
    ("1", True, ""),
    ("0", True, ""),
    ("aaaaaaaaaaaaaaaa", True, ""),
    ("               a", True, ""),
    ("a               ", True, ""),
    ("        a       ", True, ""),
    ("                ", True, ""),
    ("                 ", False, "must not exceed 16 characters"),
    ("aaaaaaaaaaaaaaaaa", False, "must not exceed 16 characters"),
    ("\\", False, "must not contain control characters or backslashes"),
    ("\n", False, "must not contain control characters or backslashes"),
    ("\t", False, "must not contain control characters or backslashes"),
    ("\r", False, "must not contain control characters or backslashes"),
    (b"A", False, "must be str"),
    # zero-width space
    ("\u200b5", False, "must only contain ASCII characters"),
]


@pytest.mark.parametrize("value, ref_result, ref_msg", AE_REFERENCE)
def test_validate_ae(value, ref_result, ref_msg):
    """Tests for validate_ae()"""
    result, msg = validate_ae(value)
    assert result == ref_result
    assert ref_msg == msg


UI_REFERENCE = [
    # value, result if enforcing conf, result if not enforcing conf
    ("", (False, "UID is non-conformant"), (False, "must not be an empty str")),
    (" ", (False, "UID is non-conformant"), (False, "must not be an empty str")),
    ("a", (False, "UID is non-conformant"), (True, "")),
    (
        "a" * 65,
        (False, "UID is non-conformant"),
        (False, "must not exceed 64 characters"),
    ),
    ("1", (True, ""), (True, "")),
    (" 1", (True, ""), (True, "")),
    (b"1", (False, "must be pydicom.uid.UID"), (False, "must be pydicom.uid.UID")),
    ("1.2.03", (False, "UID is non-conformant"), (True, "")),
    ("1.2.840.10008.1.2", (True, ""), (True, "")),
]


@pytest.fixture()
def enforce_uid_conformance():
    _config.ENFORCE_UID_CONFORMANCE = True
    yield
    _config.ENFORCE_UID_CONFORMANCE = False


@pytest.mark.parametrize("value, conf, nonconf", UI_REFERENCE)
def test_validate_ui_conf(value, conf, nonconf, enforce_uid_conformance):
    """Tests for validate_ui() if enforcing conformance"""
    assert validate_ui(value) == conf


@pytest.mark.parametrize("value, conf, nonconf", UI_REFERENCE)
def test_validate_ui_nonconf(value, conf, nonconf):
    """Tests for validate_ui() if not enforcing conformance"""
    assert validate_ui(value) == nonconf
