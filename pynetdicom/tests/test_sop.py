"""Tests for the sop_class module."""

import pytest

from pydicom._uid_dict import UID_dictionary

from pynetdicom.sop_class import (
    uid_to_sop_class,
    uid_to_service_class,
    SOPClass,
    _SERVICE_CLASSES,
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
    _UNIFIED_PROCEDURE_STEP_CLASSES,
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
from pynetdicom.service_class import (
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
from pynetdicom.service_class_n import (
    DisplaySystemManagementServiceClass,
)


def test_all_sop_classes():
    """Test that all the SOP Class UIDs are correct."""
    for uid in _VERIFICATION_CLASSES.values():
        assert uid in UID_dictionary
    for uid in _STORAGE_CLASSES.values():
        assert uid in UID_dictionary
    for uid in _QR_CLASSES.values():
        assert uid in UID_dictionary
    for uid in _BASIC_WORKLIST_CLASSES.values():
        assert uid in UID_dictionary
    for uid in _RELEVANT_PATIENT_QUERY_CLASSES.values():
        assert uid in UID_dictionary
    for uid in _SUBSTANCE_ADMINISTRATION_CLASSES.values():
        assert uid in UID_dictionary
    for uid in _NON_PATIENT_OBJECT_CLASSES.values():
        assert uid in UID_dictionary
    for uid in _PRINT_MANAGEMENT_CLASSES.values():
        assert uid in UID_dictionary
    for uid in _PROCEDURE_STEP_CLASSES.values():
        assert uid in UID_dictionary
    for uid in _DISPLAY_SYSTEM_CLASSES.values():
        assert uid in UID_dictionary
    for uid in _MEDIA_STORAGE_CLASSES.values():
        assert uid in UID_dictionary
    for uid in _UNIFIED_PROCEDURE_STEP_CLASSES.values():
        assert uid in UID_dictionary
    for uid in _RT_MACHINE_VERIFICATION_CLASSES.values():
        assert uid in UID_dictionary

def test_all_service_classes():
    """Test that all the Service Class UIDs are correct."""
    for uid in _SERVICE_CLASSES:
        assert uid in UID_dictionary


class TestUIDtoSOPlass(object):
    """Tests for uid_to_sop_class"""
    def test_missing_sop(self):
        """Test SOP Class if UID not found."""
        sop_class = uid_to_sop_class('1.2.3.4')
        assert sop_class == '1.2.3.4'
        assert sop_class.service_class == ServiceClass

    def test_verification_uid(self):
        """Test normal function"""
        assert uid_to_sop_class('1.2.840.10008.1.1') == VerificationSOPClass

    def test_existing(self):
        """Test that the existing class is returned."""
        original = VerificationSOPClass
        sop_class = uid_to_sop_class('1.2.840.10008.1.1')
        assert id(sop_class) == id(original)


class TestUIDToServiceClass(object):
    """Tests for sop_class.uid_to_service_class."""
    def test_service_class_uid(self):
        uid = '1.2.840.10008.4.2'
        assert uid_to_service_class(uid) == StorageServiceClass

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
        for uid in _UNIFIED_PROCEDURE_STEP_CLASSES.values():
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
    def test_creation(self):
        """Test creating a new UIDSOPClass."""
        sop_class = SOPClass('1.2.3')
        sop_class._service_class = ServiceClass

        assert sop_class == '1.2.3'
        assert sop_class.service_class == ServiceClass

        sop_class_b = SOPClass(sop_class)
        assert sop_class == sop_class_b
        assert sop_class_b == '1.2.3'
        assert sop_class_b.service_class == ServiceClass

    def test_verification_sop(self):
        """Test a Verification Service SOP Class."""
        assert VerificationSOPClass == '1.2.840.10008.1.1'
        assert VerificationSOPClass.service_class == VerificationServiceClass

    def test_storage_sop(self):
        """Test a Storage Service SOP Class."""
        assert CTImageStorage == '1.2.840.10008.5.1.4.1.1.2'
        assert CTImageStorage.service_class == StorageServiceClass

    def test_qr_sop(self):
        """Test a Query/Retrieve Service SOP Class."""
        assert StudyRootQueryRetrieveInformationModelFind == '1.2.840.10008.5.1.4.1.2.2.1'
        assert StudyRootQueryRetrieveInformationModelFind.service_class == QueryRetrieveServiceClass

    def test_basic_worklist_sop(self):
        """Test a Basic Worklist Service SOP Class."""
        assert ModalityWorklistInformationFind == '1.2.840.10008.5.1.4.31'
        assert ModalityWorklistInformationFind.service_class == BasicWorklistManagementServiceClass

    def test_relevant_patient_info_sop(self):
        """Test a Relevant Patient Information Query Service SOP Class."""
        assert GeneralRelevantPatientInformationQuery == '1.2.840.10008.5.1.4.37.1'
        assert GeneralRelevantPatientInformationQuery.service_class == RelevantPatientInformationQueryServiceClass

    def test_substance_admin_sop(self):
        """Test s Substance Administration Query Service SOP Class."""
        assert ProductCharacteristicsQueryInformationModelFind == '1.2.840.10008.5.1.4.41'
        assert ProductCharacteristicsQueryInformationModelFind.service_class == SubstanceAdministrationQueryServiceClass

    def test_non_patient_sop(self):
        """Test a Non-Patient Object Service SOP Class."""
        assert HangingProtocolStorage == '1.2.840.10008.5.1.4.38.1'
        assert HangingProtocolStorage.service_class == NonPatientObjectStorageServiceClass

    def test_hanging_protocol_sop(self):
        """Test a Hanging Protocol Service SOP Class."""
        assert HangingProtocolInformationModelGet == '1.2.840.10008.5.1.4.38.4'
        assert HangingProtocolInformationModelGet.service_class == HangingProtocolQueryRetrieveServiceClass

    def test_defined_procedure_sop(self):
        """Test a Defined Procedure Protocol Service SOP Class."""
        assert DefinedProcedureProtocolInformationModelFind == '1.2.840.10008.5.1.4.20.1'
        assert DefinedProcedureProtocolInformationModelFind.service_class == DefinedProcedureProtocolQueryRetrieveServiceClass

    def test_color_palette_sop(self):
        """Test a Color Palette Service SOP Class."""
        assert ColorPaletteInformationModelMove == '1.2.840.10008.5.1.4.39.3'
        assert ColorPaletteInformationModelMove.service_class == ColorPaletteQueryRetrieveServiceClass

    def test_implant_template_sop(self):
        """Test an Implant Template Service SOP Class."""
        assert ImplantTemplateGroupInformationModelFind == '1.2.840.10008.5.1.4.45.2'
        assert ImplantTemplateGroupInformationModelFind.service_class == ImplantTemplateQueryRetrieveServiceClass
