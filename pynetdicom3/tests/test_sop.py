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
    _RELEVANT_PATIENT_QUERY_CLASSES,
    _SUBSTANCE_ADMINISTRATION_CLASSES,
    _NON_PATIENT_OBJECT_CLASSES,
    _PRINT_MANAGEMENT_CLASSES,
    _PROCEDURE_STEP_CLASSES,
    _DISPLAY_SYSTEM_CLASSES,
    _MEDIA_STORAGE_CLASSES,
    _UNITED_PROCEDURE_STEP_CLASSES,
    _RT_MACHINE_VERIFICATION_CLASSES,
    VerificationSOPClass,
    CTImageStorage,
    StudyRootQueryRetrieveInformationModelFind,
    ModalityWorklistInformationFind,
    GeneralRelevantPatientInformationQuery,
    ProductCharacteristicsQueryInformationModelFind,
    HangingProtocolStorage,
    HangingProtocolInformationModelGet,
    DefinedProcedureProtocolInformationModelFind,
    ColorPaletteInformationModelMove,
    ImplantTemplateGroupInformationModelFind,
)
from pynetdicom3.service_class import (
    ServiceClass,
    VerificationServiceClass,
    StorageServiceClass,
    QueryRetrieveServiceClass,
    BasicWorklistManagementServiceClass,
    RelevantPatientInformationQueryServiceClass,
    SubstanceAdministrationQueryServiceClass,
    NonPatientObjectStorageServiceClass,
    HangingProtocolQueryRetrieveServiceClass,
    DefinedProcedureProtocolQueryRetrieveServiceClass,
    ColorPaletteQueryRetrieveServiceClass,
    ImplantTemplateQueryRetrieveServiceClass,
)
from pynetdicom3.service_class_n import (
    DisplaySystemManagementServiceClass,
)


class TestUIDtoSOPlass(object):
    """Tests for uid_to_sop_class"""
    def test_missing_sop(self):
        """Test SOP Class if UID not found."""
        sop_class = uid_to_sop_class('1.2.3.4')
        assert sop_class.uid == '1.2.3.4'
        assert sop_class.UID == '1.2.3.4'
        assert sop_class.service_class == ServiceClass

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

    def test_relevant_patient_uids(self):
        """Test that the Relevant Patient SOP Class UIDs work correctly."""
        for uid in _RELEVANT_PATIENT_QUERY_CLASSES.values():
            assert uid_to_service_class(uid) == RelevantPatientInformationQueryServiceClass

    def test_substance_admin_uids(self):
        """Test that the Substance Administration SOP Class UIDs work correctly."""
        for uid in _SUBSTANCE_ADMINISTRATION_CLASSES.values():
            assert uid_to_service_class(uid) == SubstanceAdministrationQueryServiceClass

    def test_non_patient_uids(self):
        """Test that the Non-Patient Object SOP Class UIDs work correctly."""
        for uid in _NON_PATIENT_OBJECT_CLASSES.values():
            assert uid_to_service_class(uid) == NonPatientObjectStorageServiceClass

    def test_print_uids(self):
        """Test that the Print SOP Class UIDs work correctly."""
        for uid in _PRINT_MANAGEMENT_CLASSES.values():
            assert uid_to_service_class(uid) == ServiceClass

    def test_procedure_uids(self):
        """Test that the Procedure SOP Class UIDs work correctly."""
        for uid in _PROCEDURE_STEP_CLASSES.values():
            assert uid_to_service_class(uid) == ServiceClass

    def test_media_uids(self):
        """Test that the Media Storage SOP Class UIDs work correctly."""
        for uid in _MEDIA_STORAGE_CLASSES.values():
            assert uid_to_service_class(uid) == ServiceClass

    def test_ups_uids(self):
        """Test that the UPS SOP Class UIDs work correctly."""
        for uid in _UNITED_PROCEDURE_STEP_CLASSES.values():
            assert uid_to_service_class(uid) == ServiceClass

    def test_rt_machine_uids(self):
        """Test that the RT Verification SOP Class UIDs work correctly."""
        for uid in _RT_MACHINE_VERIFICATION_CLASSES.values():
            assert uid_to_service_class(uid) == ServiceClass

    def test_display_system_uids(self):
        """Test that Display System SOP Class UIDs work correctly."""
        for uid in _DISPLAY_SYSTEM_CLASSES.values():
            assert uid_to_service_class(uid) == DisplaySystemManagementServiceClass

    def test_unknown_uid(self):
        """Test that an unknown UID returns default service class."""
        assert uid_to_service_class('1.2.3') == ServiceClass


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

    def test_relevant_patient_info_sop(self):
        """Test a Relevant Patient Information Query Service SOP Class."""
        assert GeneralRelevantPatientInformationQuery.uid == '1.2.840.10008.5.1.4.37.1'
        assert GeneralRelevantPatientInformationQuery.UID == '1.2.840.10008.5.1.4.37.1'
        assert GeneralRelevantPatientInformationQuery.service_class == RelevantPatientInformationQueryServiceClass

    def test_substance_admin_sop(self):
        """Test s Substance Administration Query Service SOP Class."""
        assert ProductCharacteristicsQueryInformationModelFind.uid == '1.2.840.10008.5.1.4.41'
        assert ProductCharacteristicsQueryInformationModelFind.UID == '1.2.840.10008.5.1.4.41'
        assert ProductCharacteristicsQueryInformationModelFind.service_class == SubstanceAdministrationQueryServiceClass

    def test_non_patient_sop(self):
        """Test a Non-Patient Object Service SOP Class."""
        assert HangingProtocolStorage.uid == '1.2.840.10008.5.1.4.38.1'
        assert HangingProtocolStorage.UID == '1.2.840.10008.5.1.4.38.1'
        assert HangingProtocolStorage.service_class == NonPatientObjectStorageServiceClass

    def test_hanging_protocol_sop(self):
        """Test a Hanging Protocol Service SOP Class."""
        assert HangingProtocolInformationModelGet.uid == '1.2.840.10008.5.1.4.38.4'
        assert HangingProtocolInformationModelGet.UID == '1.2.840.10008.5.1.4.38.4'
        assert HangingProtocolInformationModelGet.service_class == HangingProtocolQueryRetrieveServiceClass

    def test_defined_procedure_sop(self):
        """Test a Defined Procedure Protocol Service SOP Class."""
        assert DefinedProcedureProtocolInformationModelFind.uid == '1.2.840.10008.5.1.4.20.1'
        assert DefinedProcedureProtocolInformationModelFind.UID == '1.2.840.10008.5.1.4.20.1'
        assert DefinedProcedureProtocolInformationModelFind.service_class == DefinedProcedureProtocolQueryRetrieveServiceClass

    def test_color_palette_sop(self):
        """Test a Color Palette Service SOP Class."""
        assert ColorPaletteInformationModelMove.uid == '1.2.840.10008.5.1.4.39.3'
        assert ColorPaletteInformationModelMove.UID == '1.2.840.10008.5.1.4.39.3'
        assert ColorPaletteInformationModelMove.service_class == ColorPaletteQueryRetrieveServiceClass

    def test_implant_template_sop(self):
        """Test an Implant Template Service SOP Class."""
        assert ImplantTemplateGroupInformationModelFind.uid == '1.2.840.10008.5.1.4.45.2'
        assert ImplantTemplateGroupInformationModelFind.UID == '1.2.840.10008.5.1.4.45.2'
        assert ImplantTemplateGroupInformationModelFind.service_class == ImplantTemplateQueryRetrieveServiceClass
