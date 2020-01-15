"""Tests for the sop_class module."""

import pytest

from pydicom._uid_dict import UID_dictionary

from pynetdicom.sop_class import (
    uid_to_sop_class,
    uid_to_service_class,
    SOPClass,
    _SERVICE_CLASSES,
    _APPLICATION_EVENT_CLASSES,
    ProceduralEventLoggingSOPClass,
    _BASIC_WORKLIST_CLASSES,
    ModalityWorklistInformationFind,
    _COLOR_PALETTE_CLASSES,
    ColorPaletteInformationModelMove,
    _DEFINED_PROCEDURE_CLASSES,
    DefinedProcedureProtocolInformationModelFind,
    _DISPLAY_SYSTEM_CLASSES,
    DisplaySystemSOPClass,
    _HANGING_PROTOCOL_CLASSES,
    HangingProtocolInformationModelGet,
    _IMPLANT_TEMPLATE_CLASSES,
    ImplantTemplateGroupInformationModelFind,
    _INSTANCE_AVAILABILITY_CLASSES,
    InstanceAvailabilityNotificationSOPClass,
    _MEDIA_CREATION_CLASSES,
    MediaCreationManagementSOPClass,
    _MEDIA_STORAGE_CLASSES,
    MediaStorageDirectoryStorage,
    _NON_PATIENT_OBJECT_CLASSES,
    HangingProtocolStorage,
    _PRINT_MANAGEMENT_CLASSES,
    PrintJobSOPClass,
    _PROCEDURE_STEP_CLASSES,
    ModalityPerformedProcedureStepSOPClass,
    _PROTOCOL_APPROVAL_CLASSES,
    ProtocolApprovalInformationModelFind,
    ProtocolApprovalInformationModelMove,
    ProtocolApprovalInformationModelGet,
    _QR_CLASSES,
    StudyRootQueryRetrieveInformationModelFind,
    _RELEVANT_PATIENT_QUERY_CLASSES,
    GeneralRelevantPatientInformationQuery,
    _RT_MACHINE_VERIFICATION_CLASSES,
    RTConventionalMachineVerification,
    _STORAGE_CLASSES,
    CTImageStorage,
    _STORAGE_COMMITMENT_CLASSES,
    StorageCommitmentPushModelSOPClass,
    _SUBSTANCE_ADMINISTRATION_CLASSES,
    ProductCharacteristicsQueryInformationModelFind,
    _UNIFIED_PROCEDURE_STEP_CLASSES,
    UnifiedProcedureStepPullSOPClass,
    _VERIFICATION_CLASSES,
    VerificationSOPClass,
    DisplaySystemSOPInstance,
    PrinterConfigurationRetrievalSOPInstance,
    PrinterSOPInstance,
    ProceduralEventLoggingSOPInstance,
    StorageCommitmentPushModelSOPInstance,
    SubstanceAdministrationLoggingSOPInstance,
    UPSFilteredGlobalSubscriptionSOPInstance,
    UPSGlobalSubscriptionSOPInstance
)
from pynetdicom.service_class import (
    ServiceClass,
    BasicWorklistManagementServiceClass,
    ColorPaletteQueryRetrieveServiceClass,
    DefinedProcedureProtocolQueryRetrieveServiceClass,
    HangingProtocolQueryRetrieveServiceClass,
    ImplantTemplateQueryRetrieveServiceClass,
    NonPatientObjectStorageServiceClass,
    ProtocolApprovalQueryRetrieveServiceClass,
    QueryRetrieveServiceClass,
    RelevantPatientInformationQueryServiceClass,
    StorageServiceClass,
    SubstanceAdministrationQueryServiceClass,
    VerificationServiceClass,
)
from pynetdicom.service_class_n import (
    ApplicationEventLoggingServiceClass,
    DisplaySystemManagementServiceClass,
    InstanceAvailabilityNotificationServiceClass,
    MediaCreationManagementServiceClass,
    PrintManagementServiceClass,
    ProcedureStepServiceClass,
    RTMachineVerificationServiceClass,
    StorageCommitmentServiceClass,
    UnifiedProcedureStepServiceClass,
)


def test_all_sop_classes():
    """Test that all the SOP Class UIDs are correct."""
    for uid in _APPLICATION_EVENT_CLASSES.values():
        assert uid in UID_dictionary
    for uid in _BASIC_WORKLIST_CLASSES.values():
        assert uid in UID_dictionary
    for uid in _COLOR_PALETTE_CLASSES.values():
        assert uid in UID_dictionary
    for uid in _DEFINED_PROCEDURE_CLASSES.values():
        assert uid in UID_dictionary
    for uid in _DISPLAY_SYSTEM_CLASSES.values():
        assert uid in UID_dictionary
    for uid in _HANGING_PROTOCOL_CLASSES.values():
        assert uid in UID_dictionary
    for uid in _IMPLANT_TEMPLATE_CLASSES.values():
        assert uid in UID_dictionary
    for uid in _INSTANCE_AVAILABILITY_CLASSES.values():
        assert uid in UID_dictionary
    for uid in _MEDIA_CREATION_CLASSES.values():
        assert uid in UID_dictionary
    for uid in _MEDIA_STORAGE_CLASSES.values():
        assert uid in UID_dictionary
    for uid in _NON_PATIENT_OBJECT_CLASSES.values():
        assert uid in UID_dictionary
    for uid in _PRINT_MANAGEMENT_CLASSES.values():
        assert uid in UID_dictionary
    for uid in _PROCEDURE_STEP_CLASSES.values():
        assert uid in UID_dictionary
    for uid in _PROTOCOL_APPROVAL_CLASSES.values():
        assert uid in UID_dictionary
    for uid in _QR_CLASSES.values():
        assert uid in UID_dictionary
    for uid in _RELEVANT_PATIENT_QUERY_CLASSES.values():
        assert uid in UID_dictionary
    for uid in _RT_MACHINE_VERIFICATION_CLASSES.values():
        assert uid in UID_dictionary
    for uid in _STORAGE_CLASSES.values():
        assert uid in UID_dictionary
    for uid in _STORAGE_COMMITMENT_CLASSES.values():
        assert uid in UID_dictionary
    for uid in _SUBSTANCE_ADMINISTRATION_CLASSES.values():
        assert uid in UID_dictionary
    for uid in _UNIFIED_PROCEDURE_STEP_CLASSES.values():
        assert uid in UID_dictionary
    for uid in _VERIFICATION_CLASSES.values():
        assert uid in UID_dictionary


def test_all_service_classes():
    """Test that all the Service Class UIDs are correct."""
    for uid in _SERVICE_CLASSES:
        assert uid in UID_dictionary


def test_all_sop_instances():
    """Test the well-known SOP Instances are correct."""
    assert DisplaySystemSOPInstance in UID_dictionary
    assert PrinterConfigurationRetrievalSOPInstance in UID_dictionary
    assert PrinterSOPInstance in UID_dictionary
    assert ProceduralEventLoggingSOPInstance in UID_dictionary
    assert StorageCommitmentPushModelSOPInstance in UID_dictionary
    assert SubstanceAdministrationLoggingSOPInstance in UID_dictionary
    assert UPSFilteredGlobalSubscriptionSOPInstance in UID_dictionary
    assert UPSGlobalSubscriptionSOPInstance in UID_dictionary


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

    def test_app_logging_uids(self):
        """Test that the Application Event SOP Class UIDs work correctly."""
        for uid in _APPLICATION_EVENT_CLASSES.values():
            assert uid_to_service_class(uid) == ApplicationEventLoggingServiceClass

    def test_basic_worklist_uids(self):
        """Test that the Basic Worklist SOP Class UIDs work correctly."""
        for uid in _BASIC_WORKLIST_CLASSES.values():
            assert uid_to_service_class(uid) == BasicWorklistManagementServiceClass

    def test_color_palette_uids(self):
        """Test that the Color Paletter SOP Class UIDs work correctly."""
        for uid in _COLOR_PALETTE_CLASSES.values():
            assert uid_to_service_class(uid) == ColorPaletteQueryRetrieveServiceClass

    def test_defined_procedure_uids(self):
        """Test that the Defined Procedure SOP Class UIDs work correctly."""
        for uid in _DEFINED_PROCEDURE_CLASSES.values():
            assert uid_to_service_class(uid) == DefinedProcedureProtocolQueryRetrieveServiceClass

    def test_display_system_uids(self):
        """Test that Display System SOP Class UIDs work correctly."""
        for uid in _DISPLAY_SYSTEM_CLASSES.values():
            assert uid_to_service_class(uid) == DisplaySystemManagementServiceClass

    def test_hanging_protocol_uids(self):
        """Test that the Hanging Protocol SOP Class UIDs work correctly."""
        for uid in _HANGING_PROTOCOL_CLASSES.values():
            assert uid_to_service_class(uid) == HangingProtocolQueryRetrieveServiceClass

    def test_implant_template_uids(self):
        """Test that the Implant Template SOP Class UIDs work correctly."""
        for uid in _IMPLANT_TEMPLATE_CLASSES.values():
            assert uid_to_service_class(uid) == ImplantTemplateQueryRetrieveServiceClass

    def test_instance_uids(self):
        """Test that the Instance Availability SOP Class UIDs work correctly."""
        for uid in _INSTANCE_AVAILABILITY_CLASSES.values():
            assert uid_to_service_class(uid) == InstanceAvailabilityNotificationServiceClass

    def test_media_creation_uids(self):
        """Test that the Media Creation SOP Class UIDs work correctly."""
        for uid in _MEDIA_CREATION_CLASSES.values():
            assert uid_to_service_class(uid) == MediaCreationManagementServiceClass

    def test_media_storage_uids(self):
        """Test that the Media Storage SOP Class UIDs work correctly."""
        for uid in _MEDIA_STORAGE_CLASSES.values():
            assert uid_to_service_class(uid) == ServiceClass

    def test_non_patient_uids(self):
        """Test that the Non-Patient Object SOP Class UIDs work correctly."""
        for uid in _NON_PATIENT_OBJECT_CLASSES.values():
            assert uid_to_service_class(uid) == NonPatientObjectStorageServiceClass

    def test_print_uids(self):
        """Test that the Print SOP Class UIDs work correctly."""
        for uid in _PRINT_MANAGEMENT_CLASSES.values():
            assert uid_to_service_class(uid) == PrintManagementServiceClass

    def test_procedure_step_uids(self):
        """Test that the Procedure SOP Class UIDs work correctly."""
        for uid in _PROCEDURE_STEP_CLASSES.values():
            assert uid_to_service_class(uid) == ProcedureStepServiceClass

    def test_protocol_approval_uids(self):
        """Test that Protocol Approval SOP Class UIDs work correctly."""
        for uid in _PROTOCOL_APPROVAL_CLASSES.values():
            assert uid_to_service_class(uid) == ProtocolApprovalQueryRetrieveServiceClass

    def test_qr_uids(self):
        """Test that the QR SOP Class UIDs work correctly."""
        for uid in _QR_CLASSES.values():
            assert uid_to_service_class(uid) == QueryRetrieveServiceClass

    def test_relevant_patient_uids(self):
        """Test that the Relevant Patient SOP Class UIDs work correctly."""
        for uid in _RELEVANT_PATIENT_QUERY_CLASSES.values():
            assert uid_to_service_class(uid) == RelevantPatientInformationQueryServiceClass

    def test_rt_machine_uids(self):
        """Test that the RT Verification SOP Class UIDs work correctly."""
        for uid in _RT_MACHINE_VERIFICATION_CLASSES.values():
            assert uid_to_service_class(uid) == RTMachineVerificationServiceClass

    def test_storage_uids(self):
        """Test that the Storage SOP Class UIDs work correctly."""
        for uid in _STORAGE_CLASSES.values():
            assert uid_to_service_class(uid) == StorageServiceClass

    def test_storage_commitment_uids(self):
        """Test that the Storage Commitment SOP Class UIDs work correctly."""
        for uid in _STORAGE_COMMITMENT_CLASSES.values():
            assert uid_to_service_class(uid) == StorageCommitmentServiceClass

    def test_substance_admin_uids(self):
        """Test that the Substance Administration SOP Class UIDs work correctly."""
        for uid in _SUBSTANCE_ADMINISTRATION_CLASSES.values():
            assert uid_to_service_class(uid) == SubstanceAdministrationQueryServiceClass

    def test_ups_uids(self):
        """Test that the UPS SOP Class UIDs work correctly."""
        for uid in _UNIFIED_PROCEDURE_STEP_CLASSES.values():
            assert uid_to_service_class(uid) == UnifiedProcedureStepServiceClass

    def test_verification_uids(self):
        """Test that the Verification SOP Class UIDs work correctly."""
        for uid in _VERIFICATION_CLASSES.values():
            assert uid_to_service_class(uid) == VerificationServiceClass

    def test_unknown_uid(self):
        """Test that an unknown UID returns default service class."""
        assert uid_to_service_class('1.2.3') == ServiceClass


class TestSOPClass(object):
    """Tests for sop_class.SOPClass."""
    def test_app_logging_sop(self):
        assert ProceduralEventLoggingSOPClass == '1.2.840.10008.1.40'
        assert ProceduralEventLoggingSOPClass.service_class == ApplicationEventLoggingServiceClass

    def test_basic_worklist_sop(self):
        """Test a Basic Worklist Service SOP Class."""
        assert ModalityWorklistInformationFind == '1.2.840.10008.5.1.4.31'
        assert ModalityWorklistInformationFind.service_class == BasicWorklistManagementServiceClass

    def test_color_palette_sop(self):
        """Test a Color Palette Service SOP Class."""
        assert ColorPaletteInformationModelMove == '1.2.840.10008.5.1.4.39.3'
        assert ColorPaletteInformationModelMove.service_class == ColorPaletteQueryRetrieveServiceClass

    def test_defined_procedure_sop(self):
        """Test a Defined Procedure Protocol Service SOP Class."""
        assert DefinedProcedureProtocolInformationModelFind == '1.2.840.10008.5.1.4.20.1'
        assert DefinedProcedureProtocolInformationModelFind.service_class == DefinedProcedureProtocolQueryRetrieveServiceClass

    def test_display_sop(self):
        assert DisplaySystemSOPClass == '1.2.840.10008.5.1.1.40'
        assert DisplaySystemSOPClass.service_class == DisplaySystemManagementServiceClass

    def test_hanging_protocol_sop(self):
        """Test a Hanging Protocol Service SOP Class."""
        assert HangingProtocolInformationModelGet == '1.2.840.10008.5.1.4.38.4'
        assert HangingProtocolInformationModelGet.service_class == HangingProtocolQueryRetrieveServiceClass

    def test_implant_template_sop(self):
        """Test an Implant Template Service SOP Class."""
        assert ImplantTemplateGroupInformationModelFind == '1.2.840.10008.5.1.4.45.2'
        assert ImplantTemplateGroupInformationModelFind.service_class == ImplantTemplateQueryRetrieveServiceClass

    def test_instance_sop(self):
        assert InstanceAvailabilityNotificationSOPClass == '1.2.840.10008.5.1.4.33'
        assert InstanceAvailabilityNotificationSOPClass.service_class == InstanceAvailabilityNotificationServiceClass

    def test_media_creation_sop(self):
        assert MediaCreationManagementSOPClass == '1.2.840.10008.5.1.1.33'
        assert MediaCreationManagementSOPClass.service_class == MediaCreationManagementServiceClass

    def test_media_storage_sop(self):
        assert MediaStorageDirectoryStorage == '1.2.840.10008.1.3.10'
        assert MediaStorageDirectoryStorage.service_class == ServiceClass

    def test_non_patient_sop(self):
        """Test a Non-Patient Object Service SOP Class."""
        assert HangingProtocolStorage == '1.2.840.10008.5.1.4.38.1'
        assert HangingProtocolStorage.service_class == NonPatientObjectStorageServiceClass

    def test_print_sop(self):
        assert PrintJobSOPClass == '1.2.840.10008.5.1.1.14'
        assert PrintJobSOPClass.service_class == PrintManagementServiceClass

    def test_procedure_step_sop(self):
        assert ModalityPerformedProcedureStepSOPClass == '1.2.840.10008.3.1.2.3.3'
        assert ModalityPerformedProcedureStepSOPClass.service_class == ProcedureStepServiceClass

    def test_protocol_approval_sop(self):
        """Test an Protocol Approval Service SOP Class."""
        assert ProtocolApprovalInformationModelFind == '1.2.840.10008.5.1.4.1.1.200.4'
        assert ProtocolApprovalInformationModelFind.service_class == ProtocolApprovalQueryRetrieveServiceClass

    def test_qr_sop(self):
        """Test a Query/Retrieve Service SOP Class."""
        assert StudyRootQueryRetrieveInformationModelFind == '1.2.840.10008.5.1.4.1.2.2.1'
        assert StudyRootQueryRetrieveInformationModelFind.service_class == QueryRetrieveServiceClass

    def test_relevant_patient_info_sop(self):
        """Test a Relevant Patient Information Query Service SOP Class."""
        assert GeneralRelevantPatientInformationQuery == '1.2.840.10008.5.1.4.37.1'
        assert GeneralRelevantPatientInformationQuery.service_class == RelevantPatientInformationQueryServiceClass

    def test_rt_sop(self):
        assert RTConventionalMachineVerification == '1.2.840.10008.5.1.4.34.8'
        assert RTConventionalMachineVerification.service_class == RTMachineVerificationServiceClass

    def test_storage_sop(self):
        """Test a Storage Service SOP Class."""
        assert CTImageStorage == '1.2.840.10008.5.1.4.1.1.2'
        assert CTImageStorage.service_class == StorageServiceClass

    def test_storage_commitment_sop(self):
        assert StorageCommitmentPushModelSOPClass == '1.2.840.10008.1.20.1'
        assert StorageCommitmentPushModelSOPClass.service_class == StorageCommitmentServiceClass

    def test_substance_admin_sop(self):
        """Test s Substance Administration Query Service SOP Class."""
        assert ProductCharacteristicsQueryInformationModelFind == '1.2.840.10008.5.1.4.41'
        assert ProductCharacteristicsQueryInformationModelFind.service_class == SubstanceAdministrationQueryServiceClass

    def test_ups_sop(self):
        assert UnifiedProcedureStepPullSOPClass == '1.2.840.10008.5.1.4.34.6.3'
        assert UnifiedProcedureStepPullSOPClass.service_class == UnifiedProcedureStepServiceClass

    def test_verification_sop(self):
        """Test a Verification Service SOP Class."""
        assert VerificationSOPClass == '1.2.840.10008.1.1'
        assert VerificationSOPClass.service_class == VerificationServiceClass

    def test_uid_creation(self):
        """Test creating a new UIDSOPClass."""
        sop_class = SOPClass('1.2.3')
        sop_class._service_class = ServiceClass

        assert sop_class == '1.2.3'
        assert sop_class.service_class == ServiceClass

        sop_class_b = SOPClass(sop_class)
        assert sop_class == sop_class_b
        assert sop_class_b == '1.2.3'
        assert sop_class_b.service_class == ServiceClass
