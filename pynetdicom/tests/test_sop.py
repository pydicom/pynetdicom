"""Tests for the sop_class module."""

import pytest

from pynetdicom import __version__
from pydicom._uid_dict import UID_dictionary

from pynetdicom import sop_class
from pynetdicom.sop_class import (
    uid_to_sop_class,
    uid_to_service_class,
    SOPClass,
    _SERVICE_CLASSES,
    _APPLICATION_EVENT_CLASSES,
    ProceduralEventLogging,
    _BASIC_WORKLIST_CLASSES,
    ModalityWorklistInformationFind,
    _COLOR_PALETTE_CLASSES,
    ColorPaletteInformationModelMove,
    _DEFINED_PROCEDURE_CLASSES,
    DefinedProcedureProtocolInformationModelFind,
    _DISPLAY_SYSTEM_CLASSES,
    DisplaySystem,
    _HANGING_PROTOCOL_CLASSES,
    HangingProtocolInformationModelGet,
    _IMPLANT_TEMPLATE_CLASSES,
    ImplantTemplateGroupInformationModelFind,
    _INSTANCE_AVAILABILITY_CLASSES,
    InstanceAvailabilityNotification,
    _INVENTORY_CLASSES,
    InventoryFind,
    _MEDIA_CREATION_CLASSES,
    MediaCreationManagement,
    _MEDIA_STORAGE_CLASSES,
    MediaStorageDirectoryStorage,
    _NON_PATIENT_OBJECT_CLASSES,
    HangingProtocolStorage,
    _PRINT_MANAGEMENT_CLASSES,
    PrintJob,
    _PROCEDURE_STEP_CLASSES,
    ModalityPerformedProcedureStep,
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
    StorageCommitmentPushModel,
    _STORAGE_MANAGEMENT_CLASSES,
    InventoryCreation,
    _SUBSTANCE_ADMINISTRATION_CLASSES,
    ProductCharacteristicsQuery,
    _UNIFIED_PROCEDURE_STEP_CLASSES,
    UnifiedProcedureStepPull,
    _VERIFICATION_CLASSES,
    Verification,
    DisplaySystemInstance,
    PrinterConfigurationRetrievalInstance,
    PrinterInstance,
    ProceduralEventLoggingInstance,
    StorageCommitmentPushModelInstance,
    StorageManagementInstance,
    SubstanceAdministrationLoggingInstance,
    UPSFilteredGlobalSubscriptionInstance,
    UPSGlobalSubscriptionInstance,
    register_uid,
)
from pynetdicom.service_class import (
    ServiceClass,
    BasicWorklistManagementServiceClass,
    ColorPaletteQueryRetrieveServiceClass,
    DefinedProcedureProtocolQueryRetrieveServiceClass,
    HangingProtocolQueryRetrieveServiceClass,
    ImplantTemplateQueryRetrieveServiceClass,
    InventoryQueryRetrieveServiceClass,
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
    StorageManagementServiceClass,
    UnifiedProcedureStepServiceClass,
)


PYDICOM_VERSION = __version__.split(".")[:2]


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
    for uid in _INVENTORY_CLASSES.values():
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
        # UIDs not yet in pydicom
        if uid in (
            "1.2.840.10008.5.1.4.1.1.9.100.1",
            "1.2.840.10008.5.1.4.1.1.9.100.2",
            "1.2.840.10008.5.1.4.1.1.66.7",
            "1.2.840.10008.5.1.4.1.1.66.8",
        ):
            continue

        assert uid in UID_dictionary
    for uid in _STORAGE_COMMITMENT_CLASSES.values():
        assert uid in UID_dictionary
    for uid in _STORAGE_MANAGEMENT_CLASSES.values():
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
    assert DisplaySystemInstance in UID_dictionary
    assert PrinterConfigurationRetrievalInstance in UID_dictionary
    assert PrinterInstance in UID_dictionary
    assert ProceduralEventLoggingInstance in UID_dictionary
    assert StorageCommitmentPushModelInstance in UID_dictionary
    assert StorageManagementInstance in UID_dictionary
    assert SubstanceAdministrationLoggingInstance in UID_dictionary
    assert UPSFilteredGlobalSubscriptionInstance in UID_dictionary
    assert UPSGlobalSubscriptionInstance in UID_dictionary


class TestUIDtoSOPlass:
    """Tests for uid_to_sop_class"""

    def test_missing_sop_class(self):
        """Test SOP Class if UID not found."""
        sop = uid_to_sop_class("1.2.3.4")
        assert sop == "1.2.3.4"
        assert sop.service_class == ServiceClass

    def test_verification_uid(self):
        """Test normal function"""
        assert uid_to_sop_class("1.2.840.10008.1.1") == Verification

    def test_existing(self):
        """Test that the existing class is returned."""
        original = Verification
        sop = uid_to_sop_class("1.2.840.10008.1.1")
        assert id(sop) == id(original)


class TestUIDToServiceClass:
    """Tests for sop_class.uid_to_service_class."""

    def test_service_class_uid(self):
        uid = "1.2.840.10008.4.2"
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
            assert (
                uid_to_service_class(uid)
                == DefinedProcedureProtocolQueryRetrieveServiceClass
            )

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
            assert (
                uid_to_service_class(uid)
                == InstanceAvailabilityNotificationServiceClass
            )

    def test_inventory_uids(self):
        """Test that the Inventory QR SOP Class UIDs work correctly."""
        for uid in _INVENTORY_CLASSES.values():
            assert uid_to_service_class(uid) == InventoryQueryRetrieveServiceClass

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
            assert (
                uid_to_service_class(uid) == ProtocolApprovalQueryRetrieveServiceClass
            )

    def test_qr_uids(self):
        """Test that the QR SOP Class UIDs work correctly."""
        for uid in _QR_CLASSES.values():
            assert uid_to_service_class(uid) == QueryRetrieveServiceClass

    def test_relevant_patient_uids(self):
        """Test that the Relevant Patient SOP Class UIDs work correctly."""
        for uid in _RELEVANT_PATIENT_QUERY_CLASSES.values():
            assert (
                uid_to_service_class(uid) == RelevantPatientInformationQueryServiceClass
            )

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

    def test_storage_management_uids(self):
        """Test that the Storage Management SOP Class UIDs work correctly."""
        for uid in _STORAGE_MANAGEMENT_CLASSES.values():
            assert uid_to_service_class(uid) == StorageManagementServiceClass

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
        assert uid_to_service_class("1.2.3") == ServiceClass


class TestSOPClass:
    """Tests for sop_class.SOPClass."""

    def test_class_type(self):
        """Test the class type is correct."""
        sop = SOPClass("1.2.840.10008.5.1.4.1.1.2")
        assert isinstance(sop, SOPClass)
        assert isinstance(SOPClass(sop), SOPClass)

    def test_app_logging_sop(self):
        assert ProceduralEventLogging == "1.2.840.10008.1.40"
        assert (
            ProceduralEventLogging.service_class == ApplicationEventLoggingServiceClass
        )

    def test_basic_worklist_sop(self):
        """Test a Basic Worklist Service SOP Class."""
        assert ModalityWorklistInformationFind == "1.2.840.10008.5.1.4.31"
        assert (
            ModalityWorklistInformationFind.service_class
            == BasicWorklistManagementServiceClass
        )

    def test_color_palette_sop(self):
        """Test a Color Palette Service SOP Class."""
        assert ColorPaletteInformationModelMove == "1.2.840.10008.5.1.4.39.3"
        assert (
            ColorPaletteInformationModelMove.service_class
            == ColorPaletteQueryRetrieveServiceClass
        )

    def test_defined_procedure_sop(self):
        """Test a Defined Procedure Protocol Service SOP Class."""
        assert (
            DefinedProcedureProtocolInformationModelFind == "1.2.840.10008.5.1.4.20.1"
        )
        assert (
            DefinedProcedureProtocolInformationModelFind.service_class
            == DefinedProcedureProtocolQueryRetrieveServiceClass
        )

    def test_display_sop(self):
        assert DisplaySystem == "1.2.840.10008.5.1.1.40"
        assert DisplaySystem.service_class == DisplaySystemManagementServiceClass

    def test_hanging_protocol_sop(self):
        """Test a Hanging Protocol Service SOP Class."""
        assert HangingProtocolInformationModelGet == "1.2.840.10008.5.1.4.38.4"
        assert (
            HangingProtocolInformationModelGet.service_class
            == HangingProtocolQueryRetrieveServiceClass
        )

    def test_implant_template_sop(self):
        """Test an Implant Template Service SOP Class."""
        assert ImplantTemplateGroupInformationModelFind == "1.2.840.10008.5.1.4.45.2"
        assert (
            ImplantTemplateGroupInformationModelFind.service_class
            == ImplantTemplateQueryRetrieveServiceClass
        )

    def test_instance_sop(self):
        assert InstanceAvailabilityNotification == "1.2.840.10008.5.1.4.33"
        assert (
            InstanceAvailabilityNotification.service_class
            == InstanceAvailabilityNotificationServiceClass
        )

    def test_instance_sop(self):
        assert InventoryFind == "1.2.840.10008.5.1.4.1.1.201.2"
        assert InventoryFind.service_class == InventoryQueryRetrieveServiceClass

    def test_media_creation_sop(self):
        assert MediaCreationManagement == "1.2.840.10008.5.1.1.33"
        assert (
            MediaCreationManagement.service_class == MediaCreationManagementServiceClass
        )

    def test_media_storage_sop(self):
        assert MediaStorageDirectoryStorage == "1.2.840.10008.1.3.10"
        assert MediaStorageDirectoryStorage.service_class == ServiceClass

    def test_non_patient_sop(self):
        """Test a Non-Patient Object Service SOP Class."""
        assert HangingProtocolStorage == "1.2.840.10008.5.1.4.38.1"
        assert (
            HangingProtocolStorage.service_class == NonPatientObjectStorageServiceClass
        )

    def test_print_sop(self):
        assert PrintJob == "1.2.840.10008.5.1.1.14"
        assert PrintJob.service_class == PrintManagementServiceClass

    def test_procedure_step_sop(self):
        assert ModalityPerformedProcedureStep == "1.2.840.10008.3.1.2.3.3"
        assert ModalityPerformedProcedureStep.service_class == ProcedureStepServiceClass

    def test_protocol_approval_sop(self):
        """Test an Protocol Approval Service SOP Class."""
        assert ProtocolApprovalInformationModelFind == "1.2.840.10008.5.1.4.1.1.200.4"
        assert (
            ProtocolApprovalInformationModelFind.service_class
            == ProtocolApprovalQueryRetrieveServiceClass
        )

    def test_qr_sop(self):
        """Test a Query/Retrieve Service SOP Class."""
        assert (
            StudyRootQueryRetrieveInformationModelFind == "1.2.840.10008.5.1.4.1.2.2.1"
        )
        assert (
            StudyRootQueryRetrieveInformationModelFind.service_class
            == QueryRetrieveServiceClass
        )

    def test_relevant_patient_info_sop(self):
        """Test a Relevant Patient Information Query Service SOP Class."""
        assert GeneralRelevantPatientInformationQuery == "1.2.840.10008.5.1.4.37.1"
        assert (
            GeneralRelevantPatientInformationQuery.service_class
            == RelevantPatientInformationQueryServiceClass
        )

    def test_rt_sop(self):
        assert RTConventionalMachineVerification == "1.2.840.10008.5.1.4.34.8"
        assert (
            RTConventionalMachineVerification.service_class
            == RTMachineVerificationServiceClass
        )

    def test_storage_sop(self):
        """Test a Storage Service SOP Class."""
        assert CTImageStorage == "1.2.840.10008.5.1.4.1.1.2"
        assert CTImageStorage.service_class == StorageServiceClass

    def test_storage_commitment_sop(self):
        assert StorageCommitmentPushModel == "1.2.840.10008.1.20.1"
        assert StorageCommitmentPushModel.service_class == StorageCommitmentServiceClass

    def test_storage_management_sop(self):
        assert InventoryCreation == "1.2.840.10008.5.1.4.1.1.201.5"
        assert InventoryCreation.service_class == StorageManagementServiceClass

    def test_substance_admin_sop(self):
        """Test s Substance Administration Query Service SOP Class."""
        assert ProductCharacteristicsQuery == "1.2.840.10008.5.1.4.41"
        assert (
            ProductCharacteristicsQuery.service_class
            == SubstanceAdministrationQueryServiceClass
        )

    def test_ups_sop(self):
        assert UnifiedProcedureStepPull == "1.2.840.10008.5.1.4.34.6.3"
        assert (
            UnifiedProcedureStepPull.service_class == UnifiedProcedureStepServiceClass
        )

    def test_verification_sop(self):
        """Test a Verification Service SOP Class."""
        assert Verification == "1.2.840.10008.1.1"
        assert Verification.service_class == VerificationServiceClass

    def test_uid_creation(self):
        """Test creating a new UIDSOPClass."""
        sop = SOPClass("1.2.3")
        sop._service_class = ServiceClass

        assert sop == "1.2.3"
        assert sop.service_class == ServiceClass

        sop_b = SOPClass(sop)
        assert sop == sop_b
        assert sop_b == "1.2.3"
        assert sop_b.service_class == ServiceClass


class TestRegisterUID:
    def test_register_storage(self):
        """Test registering to the storage service."""
        register_uid(
            "1.2.3.4",
            "FooStorage",
            StorageServiceClass,
        )

        sop = sop_class.FooStorage
        assert sop == "1.2.3.4"
        assert sop.service_class == StorageServiceClass

        del _STORAGE_CLASSES["FooStorage"]
        delattr(sop_class, "FooStorage")

    def test_register_qr_find(self):
        """Test registering to the QR service - FIND."""
        register_uid(
            "1.2.3.4",
            "FooFind",
            QueryRetrieveServiceClass,
            dimse_msg_type="C-FIND",
        )

        sop = sop_class.FooFind
        assert sop == "1.2.3.4"
        assert sop.service_class == QueryRetrieveServiceClass
        assert sop in QueryRetrieveServiceClass._SUPPORTED_UIDS["C-FIND"]

        del _QR_CLASSES["FooFind"]
        QueryRetrieveServiceClass._SUPPORTED_UIDS["C-FIND"].remove(sop)
        delattr(sop_class, "FooFind")

    def test_register_qr_get(self):
        """Test registering to the QR service - GET."""
        register_uid(
            "1.2.3.4",
            "FooGet",
            QueryRetrieveServiceClass,
            dimse_msg_type="C-GET",
        )

        sop = sop_class.FooGet
        assert sop == "1.2.3.4"
        assert sop.service_class == QueryRetrieveServiceClass
        assert sop in QueryRetrieveServiceClass._SUPPORTED_UIDS["C-GET"]

        del _QR_CLASSES["FooGet"]
        QueryRetrieveServiceClass._SUPPORTED_UIDS["C-GET"].remove(sop)
        delattr(sop_class, "FooGet")

    def test_register_qr_move(self):
        """Test registering to the QR service - MOVE."""
        register_uid(
            "1.2.3.4",
            "FooMove",
            QueryRetrieveServiceClass,
            dimse_msg_type="C-MOVE",
        )

        sop = sop_class.FooMove
        assert sop == "1.2.3.4"
        assert sop.service_class == QueryRetrieveServiceClass
        assert sop in QueryRetrieveServiceClass._SUPPORTED_UIDS["C-MOVE"]

        del _QR_CLASSES["FooMove"]
        QueryRetrieveServiceClass._SUPPORTED_UIDS["C-MOVE"].remove(sop)
        delattr(sop_class, "FooMove")

    def test_register_bwm_find(self):
        """Test registering to the BWM service."""
        register_uid(
            "1.2.3.4",
            "FooFind",
            BasicWorklistManagementServiceClass,
            dimse_msg_type="C-FIND",
        )

        sop = sop_class.FooFind
        assert sop == "1.2.3.4"
        assert sop.service_class == BasicWorklistManagementServiceClass
        assert sop in BasicWorklistManagementServiceClass._SUPPORTED_UIDS["C-FIND"]

        del _BASIC_WORKLIST_CLASSES["FooFind"]
        BasicWorklistManagementServiceClass._SUPPORTED_UIDS["C-FIND"].remove(sop)
        delattr(sop_class, "FooFind")

    def test_register_substance_admin_find(self):
        """Test registering to the Substance Admin QR service."""
        register_uid(
            "1.2.3.4",
            "FooFind",
            SubstanceAdministrationQueryServiceClass,
            dimse_msg_type="C-FIND",
        )

        sop = sop_class.FooFind
        assert sop == "1.2.3.4"
        assert sop.service_class == SubstanceAdministrationQueryServiceClass
        assert sop in SubstanceAdministrationQueryServiceClass._SUPPORTED_UIDS["C-FIND"]

        del _SUBSTANCE_ADMINISTRATION_CLASSES["FooFind"]
        SubstanceAdministrationQueryServiceClass._SUPPORTED_UIDS["C-FIND"].remove(sop)
        delattr(sop_class, "FooFind")

    def test_invalid_keyword_raises(self):
        """Test invalid keyword raises exceptions."""
        msg = (
            "The keyword '2coo' is not a valid Python identifier or is "
            "a Python keyword"
        )
        with pytest.raises(ValueError, match=msg):
            register_uid("", "2coo", ServiceClass)

        msg = (
            "The keyword 'def' is not a valid Python identifier or is "
            "a Python keyword"
        )
        with pytest.raises(ValueError, match=msg):
            register_uid("", "def", ServiceClass)

    def test_invalid_service_class_raises(self):
        """Test that an invalid service_class raises exceptions."""
        msg = "'service_class' must be a class object not a class instance"
        with pytest.raises(TypeError, match=msg):
            register_uid("", "Foo", "")

        msg = (
            "'service_class' must be a ServiceClass subclass object "
            "such as 'StorageServiceClass'"
        )
        with pytest.raises(TypeError, match=msg):
            register_uid("", "Foo", str)

    def test_invalid_dimse_msg_type_raises(self):
        """Test that an invalid dimse_msg_type raises exceptions."""
        msg = (
            "'dimse_msg_type' must be 'C-FIND', 'C-GET' or 'C-MOVE' "
            "when registering a UID with QueryRetrieveServiceClass"
        )
        with pytest.raises(ValueError, match=msg):
            register_uid("", "Foo", QueryRetrieveServiceClass, "Foo")
