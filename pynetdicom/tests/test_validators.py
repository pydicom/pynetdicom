"""Tests for the _validators module"""

import pytest

from pydicom import config as PYD_CONFIG

from pynetdicom import _config
from pydicom.dataset import Dataset
from pydicom.uid import UID

from pynetdicom._validators import validate_ae, validate_ui, validate_query
from pynetdicom.sop_class import (
    PatientRootQueryRetrieveInformationModelFind,
    StudyRootQueryRetrieveInformationModelMove,
    PatientStudyOnlyQueryRetrieveInformationModelGet,
    ModalityWorklistInformationFind,
)

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


def _query(level=None, **kwargs):
    ds = Dataset()
    if level is not None:
        ds.QueryRetrieveLevel = level
    for kw, val in kwargs.items():
        setattr(ds, kw, val)
    return ds


QUERY_REFERENCE = [
    # (identifier, query_model, (valid, reason))
    # Patient Root - PATIENT/STUDY/SERIES/IMAGE all valid
    (_query("PATIENT"), PatientRootQueryRetrieveInformationModelFind, (True, "")),
    (_query("IMAGE"), PatientRootQueryRetrieveInformationModelFind, (True, "")),
    # Study Root - PATIENT is not a valid level
    (_query("STUDY"), StudyRootQueryRetrieveInformationModelMove, (True, "")),
    (
        _query("PATIENT"),
        StudyRootQueryRetrieveInformationModelMove,
        (
            False,
            "the Identifier's (0008,0052) 'Query/Retrieve Level' value 'PATIENT' "
            "is not one of ['STUDY', 'SERIES', 'IMAGE'] allowed for the query model",
        ),
    ),
    # Patient/Study Only - only PATIENT/STUDY
    (_query("STUDY"), PatientStudyOnlyQueryRetrieveInformationModelGet, (True, "")),
    (
        _query("SERIES"),
        PatientStudyOnlyQueryRetrieveInformationModelGet,
        (
            False,
            "the Identifier's (0008,0052) 'Query/Retrieve Level' value 'SERIES' "
            "is not one of ['PATIENT', 'STUDY'] allowed for the query model",
        ),
    ),
    # Missing Query/Retrieve Level for a hierarchical model
    (
        _query(PatientName="*"),
        PatientRootQueryRetrieveInformationModelFind,
        (False, "the Identifier is missing (0008,0052) 'Query/Retrieve Level'"),
    ),
    # Non-hierarchical model - never validated, so always valid
    (_query(PatientName="*"), ModalityWorklistInformationFind, (True, "")),
    (_query("BOGUS"), ModalityWorklistInformationFind, (True, "")),
]


@pytest.mark.parametrize("identifier, query_model, ref", QUERY_REFERENCE)
def test_validate_query(identifier, query_model, ref):
    """Tests for validate_query()"""
    assert validate_query(identifier, UID(query_model)) == ref
