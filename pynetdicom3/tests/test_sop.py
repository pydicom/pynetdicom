"""Tests for the sop_class module."""

import pytest

from pynetdicom3.sop_class import (
    uid_to_sop_class,
    uid_to_service_class,
    SOPClass,
    _VERIFICATION_CLASSES,
    _STORAGE_CLASSES,
    _QR_CLASSES,
    _BASIC_WORKLIST_CLASSES,
    VerificationSOPClass,
    CTImageStorage,
    StudyRootQueryRetrieveInformationModelFind,
    ModalityWorklistInformationFind,
)
from pynetdicom3.service_class import (
    VerificationServiceClass,
    StorageServiceClass,
    QueryRetrieveServiceClass,
    BasicWorklistManagementServiceClass,
)


class TestUIDtoSOPlass(object):
    """Tests for uid_to_sop_class"""
    def test_missing_sop(self):
        """Test raise if SOP Class not found."""
        with pytest.raises(NotImplementedError):
            uid_to_sop_class('1.2.3.4')

    def test_verification_uid(self):
        """Test normal function"""
        assert uid_to_sop_class('1.2.840.10008.1.1') == VerificationSOPClass


class TestUIDToServiceClass(object):
    """Tests for sop_class.uid_to_service_class."""
    def test_verification_uids(self):
        """Test that the Verification SOP Class UIDs work correctly."""
        for uid in _VERIFICATION_CLASSES.values():
            assert uid_to_service_class(uid) == VerificationServiceClass

    def test_storage_uids(self):
        """Test that the Storage SOP Class UIDs work correctly."""
        for uid in _STORAGE_CLASSES.values():
            assert uid_to_service_class(uid) == StorageServiceClass

    def test_qr_uids(self):
        """Test that the QR SOP Class UIDs work correctly."""
        for uid in _QR_CLASSES.values():
            assert uid_to_service_class(uid) == QueryRetrieveServiceClass

    def test_basic_worklist_uids(self):
        """Test that the Basic Worklist SOP Class UIDs work correctly."""
        for uid in _BASIC_WORKLIST_CLASSES.values():
            assert uid_to_service_class(uid) == BasicWorklistManagementServiceClass

    def test_unknown_uid_raises(self):
        """Test that an unknown UID raises exception."""
        with pytest.raises(NotImplementedError):
            uid_to_service_class('1.2.3')


class TestSOPClass(object):
    """Tests for sop_class.SOPClass."""
    def test_functional(self):
        """Test basic functionality."""
        sop = SOPClass('1.2.3', '1.2.3', VerificationServiceClass)
        assert sop.uid == '1.2.3'
        assert sop.UID == '1.2.3'
        assert sop.service_class == VerificationServiceClass

    def test_verification_sop(self):
        """Test a Verification Service SOP Class."""
        assert VerificationSOPClass.uid == '1.2.840.10008.1.1'
        assert VerificationSOPClass.UID == '1.2.840.10008.1.1'
        assert VerificationSOPClass.service_class == VerificationServiceClass

    def test_storage_sop(self):
        """Test a Storage Service SOP Class."""
        assert CTImageStorage.uid == '1.2.840.10008.5.1.4.1.1.2'
        assert CTImageStorage.UID == '1.2.840.10008.5.1.4.1.1.2'
        assert CTImageStorage.service_class == StorageServiceClass

    def test_qr_sop(self):
        """Test a Query/Retrieve Service SOP Class."""
        assert StudyRootQueryRetrieveInformationModelFind.uid == '1.2.840.10008.5.1.4.1.2.2.1'
        assert StudyRootQueryRetrieveInformationModelFind.UID == '1.2.840.10008.5.1.4.1.2.2.1'
        assert StudyRootQueryRetrieveInformationModelFind.service_class == QueryRetrieveServiceClass

    def test_basic_worklist_sop(self):
        """Test a Basic Worklist Service SOP Class."""
        assert ModalityWorklistInformationFind.uid == '1.2.840.10008.5.1.4.31'
        assert ModalityWorklistInformationFind.UID == '1.2.840.10008.5.1.4.31'
        assert ModalityWorklistInformationFind.service_class == BasicWorklistManagementServiceClass
