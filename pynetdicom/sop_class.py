"""Generates the supported SOP Classes and well-known SOP Instances."""

import inspect
from keyword import iskeyword
import logging
import sys
from typing import Optional, Type, cast, Dict

from pydicom.uid import UID

from pynetdicom.service_class import (
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
    ServiceClass,
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


LOGGER = logging.getLogger(__name__)


def uid_to_service_class(uid: str) -> Type[ServiceClass]:
    """Return the :class:`~pynetdicom.service_class.ServiceClass` object
    corresponding to `uid`.

    Parameters
    ----------
    uid : pydicom.uid.UID
        The SOP or Service Class UID to use to find the corresponding Service
        Class.

    Returns
    -------
    subclass of service_class.ServiceClass
        The Service Class corresponding to the SOP Class UID or the base class
        if support for the SOP Class isn't implemented.
    """
    if uid in _VERIFICATION_CLASSES.values():
        return VerificationServiceClass

    if uid in _QR_CLASSES.values():
        return QueryRetrieveServiceClass

    if uid in _STORAGE_CLASSES.values():
        return StorageServiceClass

    if uid in _SERVICE_CLASSES:
        return _SERVICE_CLASSES[uid]

    if uid in _APPLICATION_EVENT_CLASSES.values():
        return ApplicationEventLoggingServiceClass

    if uid in _BASIC_WORKLIST_CLASSES.values():
        return BasicWorklistManagementServiceClass

    if uid in _COLOR_PALETTE_CLASSES.values():
        return ColorPaletteQueryRetrieveServiceClass

    if uid in _DEFINED_PROCEDURE_CLASSES.values():
        return DefinedProcedureProtocolQueryRetrieveServiceClass

    if uid in _DISPLAY_SYSTEM_CLASSES.values():
        return DisplaySystemManagementServiceClass

    if uid in _HANGING_PROTOCOL_CLASSES.values():
        return HangingProtocolQueryRetrieveServiceClass

    if uid in _IMPLANT_TEMPLATE_CLASSES.values():
        return ImplantTemplateQueryRetrieveServiceClass

    if uid in _INSTANCE_AVAILABILITY_CLASSES.values():
        return InstanceAvailabilityNotificationServiceClass

    if uid in _INVENTORY_CLASSES.values():
        return InventoryQueryRetrieveServiceClass

    if uid in _MEDIA_CREATION_CLASSES.values():
        return MediaCreationManagementServiceClass

    if uid in _MEDIA_STORAGE_CLASSES.values():
        return ServiceClass  # Not yet implemented

    if uid in _NON_PATIENT_OBJECT_CLASSES.values():
        return NonPatientObjectStorageServiceClass

    if uid in _PRINT_MANAGEMENT_CLASSES.values():
        return PrintManagementServiceClass

    if uid in _PROCEDURE_STEP_CLASSES.values():
        return ProcedureStepServiceClass

    if uid in _PROTOCOL_APPROVAL_CLASSES.values():
        return ProtocolApprovalQueryRetrieveServiceClass

    if uid in _RELEVANT_PATIENT_QUERY_CLASSES.values():
        return RelevantPatientInformationQueryServiceClass

    if uid in _RT_MACHINE_VERIFICATION_CLASSES.values():
        return RTMachineVerificationServiceClass

    if uid in _STORAGE_COMMITMENT_CLASSES.values():
        return StorageCommitmentServiceClass

    if uid in _STORAGE_MANAGEMENT_CLASSES.values():
        return StorageManagementServiceClass

    if uid in _SUBSTANCE_ADMINISTRATION_CLASSES.values():
        return SubstanceAdministrationQueryServiceClass

    if uid in _UNIFIED_PROCEDURE_STEP_CLASSES.values():
        return UnifiedProcedureStepServiceClass

    # No SCP implemented
    return ServiceClass


class SOPClass(UID):
    """Extend :class:`~pydicom.uid.UID` to include the corresponding Service
    Class.

    """

    _service_class: Optional[Type[ServiceClass]] = None
    _name: str = ""

    def __new__(cls: Type["SOPClass"], val: str) -> "SOPClass":
        if isinstance(val, SOPClass):
            return val

        return cast("SOPClass", super().__new__(cls, val))

    @property
    def service_class(self) -> ServiceClass:
        """Return the corresponding Service Class implementation."""
        return cast(ServiceClass, self._service_class)


def _generate_sop_classes(sop_class_dict: Dict[str, str]) -> None:
    """Generate the SOP Classes."""
    for name in sop_class_dict:
        uid = sop_class_dict[name]
        sop_class: SOPClass = SOPClass(uid)
        sop_class._service_class = uid_to_service_class(uid)
        docstring = f"``{uid}``"
        # if uid in _x:
        #     docstring += "\n\n.. versionadded:: 1.4"

        sop_class.__doc__ = docstring
        globals()[name] = sop_class


# Table of service classes with assigned UIDs
_SERVICE_CLASSES = {
    "1.2.840.10008.4.2": StorageServiceClass,
    "1.2.840.10008.5.1.4.34.6": UnifiedProcedureStepServiceClass,
}

# Generate the various SOP classes
# pylint: disable=line-too-long
_APPLICATION_EVENT_CLASSES = {
    "ProceduralEventLogging": "1.2.840.10008.1.40",
    "SubstanceAdministrationLogging": "1.2.840.10008.1.42",
}
_BASIC_WORKLIST_CLASSES = {
    "ModalityWorklistInformationFind": "1.2.840.10008.5.1.4.31",
}
_COLOR_PALETTE_CLASSES = {
    "ColorPaletteInformationModelFind": "1.2.840.10008.5.1.4.39.2",
    "ColorPaletteInformationModelMove": "1.2.840.10008.5.1.4.39.3",
    "ColorPaletteInformationModelGet": "1.2.840.10008.5.1.4.39.4",
}
_DEFINED_PROCEDURE_CLASSES = {
    "DefinedProcedureProtocolInformationModelFind": "1.2.840.10008.5.1.4.20.1",
    "DefinedProcedureProtocolInformationModelMove": "1.2.840.10008.5.1.4.20.2",
    "DefinedProcedureProtocolInformationModelGet": "1.2.840.10008.5.1.4.20.3",
}
_DISPLAY_SYSTEM_CLASSES = {
    "DisplaySystem": "1.2.840.10008.5.1.1.40",
}
_HANGING_PROTOCOL_CLASSES = {
    "HangingProtocolInformationModelFind": "1.2.840.10008.5.1.4.38.2",
    "HangingProtocolInformationModelMove": "1.2.840.10008.5.1.4.38.3",
    "HangingProtocolInformationModelGet": "1.2.840.10008.5.1.4.38.4",
}
_IMPLANT_TEMPLATE_CLASSES = {
    "GenericImplantTemplateInformationModelFind": "1.2.840.10008.5.1.4.43.2",
    "GenericImplantTemplateInformationModelMove": "1.2.840.10008.5.1.4.43.3",
    "GenericImplantTemplateInformationModelGet": "1.2.840.10008.5.1.4.43.4",
    "ImplantAssemblyTemplateInformationModelFind": "1.2.840.10008.5.1.4.44.2",
    "ImplantAssemblyTemplateInformationModelMove": "1.2.840.10008.5.1.4.44.3",
    "ImplantAssemblyTemplateInformationModelGet": "1.2.840.10008.5.1.4.44.4",
    "ImplantTemplateGroupInformationModelFind": "1.2.840.10008.5.1.4.45.2",
    "ImplantTemplateGroupInformationModelMove": "1.2.840.10008.5.1.4.45.3",
    "ImplantTemplateGroupInformationModelGet": "1.2.840.10008.5.1.4.45.4",
}
_INSTANCE_AVAILABILITY_CLASSES = {
    "InstanceAvailabilityNotification": "1.2.840.10008.5.1.4.33",
}
_INVENTORY_CLASSES = {
    "InventoryFind": "1.2.840.10008.5.1.4.1.1.201.2",
    "InventoryMove": "1.2.840.10008.5.1.4.1.1.201.3",
    "InventoryGet": "1.2.840.10008.5.1.4.1.1.201.4",
}
_MEDIA_CREATION_CLASSES = {
    "MediaCreationManagement": "1.2.840.10008.5.1.1.33",
}
_MEDIA_STORAGE_CLASSES = {
    "MediaStorageDirectoryStorage": "1.2.840.10008.1.3.10",
}
_NON_PATIENT_OBJECT_CLASSES = {
    "HangingProtocolStorage": "1.2.840.10008.5.1.4.38.1",
    "ColorPaletteStorage": "1.2.840.10008.5.1.4.39.1",
    "GenericImplantTemplateStorage": "1.2.840.10008.5.1.4.43.1",
    "ImplantAssemblyTemplateStorage": "1.2.840.10008.5.1.4.44.1",
    "ImplantTemplateGroupStorage": "1.2.840.10008.5.1.4.45.1",
    "CTDefinedProcedureProtocolStorage": "1.2.840.10008.5.1.4.1.1.200.1",
    "ProtocolApprovalStorage": "1.2.840.10008.5.1.4.1.1.200.3",
    "XADefinedProcedureProtocolStorage": "1.2.840.10008.5.1.4.1.1.200.7",
    "InventoryStorage": "1.2.840.10008.5.1.4.1.1.201.1",
}
_PRINT_MANAGEMENT_CLASSES = {
    "BasicFilmSession": "1.2.840.10008.5.1.1.1",
    "BasicFilmBox": "1.2.840.10008.5.1.1.2",
    "BasicGrayscaleImageBox": "1.2.840.10008.5.1.1.4",
    "BasicColorImageBox": "1.2.840.10008.5.1.1.4.1",
    "PrintJob": "1.2.840.10008.5.1.1.14",
    "BasicAnnotationBox": "1.2.840.10008.5.1.1.15",
    "Printer": "1.2.840.10008.5.1.1.16",
    "PrinterConfigurationRetrieval": "1.2.840.10008.5.1.1.16.376",
    "PresentationLUT": "1.2.840.10008.5.1.1.23",
    # Print Management Meta SOP Classes
    # Basic Film Session, Basic Film Box, Basic Grayscale, Printer
    "BasicGrayscalePrintManagementMeta": "1.2.840.10008.5.1.1.9",
    # Basic Film Session, Basic Film Box, Basic Color, Printer
    "BasicColorPrintManagementMeta": "1.2.840.10008.5.1.1.18",
}
_PROCEDURE_STEP_CLASSES = {
    "ModalityPerformedProcedureStep": "1.2.840.10008.3.1.2.3.3",
    "ModalityPerformedProcedureStepRetrieve": "1.2.840.10008.3.1.2.3.4",
    "ModalityPerformedProcedureStepNotification": "1.2.840.10008.3.1.2.3.5",
}
_PROTOCOL_APPROVAL_CLASSES = {
    "ProtocolApprovalInformationModelFind": "1.2.840.10008.5.1.4.1.1.200.4",
    "ProtocolApprovalInformationModelMove": "1.2.840.10008.5.1.4.1.1.200.5",
    "ProtocolApprovalInformationModelGet": "1.2.840.10008.5.1.4.1.1.200.6",
}
_QR_CLASSES = {
    "PatientRootQueryRetrieveInformationModelFind": "1.2.840.10008.5.1.4.1.2.1.1",
    "PatientRootQueryRetrieveInformationModelMove": "1.2.840.10008.5.1.4.1.2.1.2",
    "PatientRootQueryRetrieveInformationModelGet": "1.2.840.10008.5.1.4.1.2.1.3",
    "StudyRootQueryRetrieveInformationModelFind": "1.2.840.10008.5.1.4.1.2.2.1",
    "StudyRootQueryRetrieveInformationModelMove": "1.2.840.10008.5.1.4.1.2.2.2",
    "StudyRootQueryRetrieveInformationModelGet": "1.2.840.10008.5.1.4.1.2.2.3",
    "PatientStudyOnlyQueryRetrieveInformationModelFind": "1.2.840.10008.5.1.4.1.2.3.1",
    "PatientStudyOnlyQueryRetrieveInformationModelMove": "1.2.840.10008.5.1.4.1.2.3.2",
    "PatientStudyOnlyQueryRetrieveInformationModelGet": "1.2.840.10008.5.1.4.1.2.3.3",
    "CompositeInstanceRootRetrieveMove": "1.2.840.10008.5.1.4.1.2.4.2",
    "CompositeInstanceRootRetrieveGet": "1.2.840.10008.5.1.4.1.2.4.3",
    "CompositeInstanceRetrieveWithoutBulkDataGet": "1.2.840.10008.5.1.4.1.2.5.3",
    "RepositoryQuery": "1.2.840.10008.5.1.4.1.1.201.6",
}
_RELEVANT_PATIENT_QUERY_CLASSES = {
    "GeneralRelevantPatientInformationQuery": "1.2.840.10008.5.1.4.37.1",
    "BreastImagingRelevantPatientInformationQuery": "1.2.840.10008.5.1.4.37.2",
    "CardiacRelevantPatientInformationQuery": "1.2.840.10008.5.1.4.37.3",
}
_RT_MACHINE_VERIFICATION_CLASSES = {
    "RTConventionalMachineVerification": "1.2.840.10008.5.1.4.34.8",
    "RTIonMachineVerification": "1.2.840.10008.5.1.4.34.9",
}
_STORAGE_CLASSES = {
    "ComputedRadiographyImageStorage": "1.2.840.10008.5.1.4.1.1.1",  # A.2
    "DigitalXRayImageStorageForPresentation": "1.2.840.10008.5.1.4.1.1.1.1",  # A.26
    "DigitalXRayImageStorageForProcessing": "1.2.840.10008.5.1.4.1.1.1.1.1",  # A.26
    "DigitalMammographyXRayImageStorageForPresentation": "1.2.840.10008.5.1.4.1.1.1.2",  # A.27
    "DigitalMammographyXRayImageStorageForProcessing": "1.2.840.10008.5.1.4.1.1.1.2.1",  # A.27
    "DigitalIntraOralXRayImageStorageForPresentation": "1.2.840.10008.5.1.4.1.1.1.3",  # A.28
    "DigitalIntraOralXRayImageStorageForProcessing": "1.2.840.10008.5.1.4.1.1.1.3.1",  # A.28
    "CTImageStorage": "1.2.840.10008.5.1.4.1.1.2",  # A.3
    "EnhancedCTImageStorage": "1.2.840.10008.5.1.4.1.1.2.1",  # A.38
    "LegacyConvertedEnhancedCTImageStorage": "1.2.840.10008.5.1.4.1.1.2.2",  # A.70
    "UltrasoundMultiFrameImageStorage": "1.2.840.10008.5.1.4.1.1.3.1",  # A.7
    "MRImageStorage": "1.2.840.10008.5.1.4.1.1.4",  # A.4
    "EnhancedMRImageStorage": "1.2.840.10008.5.1.4.1.1.4.1",  # A.36.2
    "MRSpectroscopyStorage": "1.2.840.10008.5.1.4.1.1.4.2",  # A.36.3
    "EnhancedMRColorImageStorage": "1.2.840.10008.5.1.4.1.1.4.3",  # A.36.4
    "LegacyConvertedEnhancedMRImageStorage": "1.2.840.10008.5.1.4.1.1.4.4",  # A.71
    "UltrasoundImageStorage": "1.2.840.10008.5.1.4.1.1.6.1",  # A.6
    "EnhancedUSVolumeStorage": "1.2.840.10008.5.1.4.1.1.6.2",  # A.59
    "PhotoacousticImageStorage": "1.2.840.10008.5.1.4.1.1.6.3",
    "SecondaryCaptureImageStorage": "1.2.840.10008.5.1.4.1.1.7",  # A.8.1
    "MultiFrameSingleBitSecondaryCaptureImageStorage": "1.2.840.10008.5.1.4.1.1.7.1",  # A.8.2
    "MultiFrameGrayscaleByteSecondaryCaptureImageStorage": "1.2.840.10008.5.1.4.1.1.7.2",  # A.8.3
    "MultiFrameGrayscaleWordSecondaryCaptureImageStorage": "1.2.840.10008.5.1.4.1.1.7.3",  # A.8.4
    "MultiFrameTrueColorSecondaryCaptureImageStorage": "1.2.840.10008.5.1.4.1.1.7.4",  # A.8.5
    "TwelveLeadECGWaveformStorage": "1.2.840.10008.5.1.4.1.1.9.1.1",  # A.34.3
    "GeneralECGWaveformStorage": "1.2.840.10008.5.1.4.1.1.9.1.2",  # A.34.4
    "AmbulatoryECGWaveformStorage": "1.2.840.10008.5.1.4.1.1.9.1.3",  # A.34.5
    "General32bitECGWaveformStorage": "1.2.840.10008.5.1.4.1.1.9.1.4",
    "HemodynamicWaveformStorage": "1.2.840.10008.5.1.4.1.1.9.2.1",  # A.34.6
    "CardiacElectrophysiologyWaveformStorage": "1.2.840.10008.5.1.4.1.1.9.3.1",  # A.34.7
    "BasicVoiceAudioWaveformStorage": "1.2.840.10008.5.1.4.1.1.9.4.1",  # A.34.2
    "GeneralAudioWaveformStorage": "1.2.840.10008.5.1.4.1.1.9.4.2",  # A.34.10
    "ArterialPulseWaveformStorage": "1.2.840.10008.5.1.4.1.1.9.5.1",  # A.34.8
    "RespiratoryWaveformStorage": "1.2.840.10008.5.1.4.1.1.9.6.1",  # A.34.9
    "MultichannelRespiratoryWaveformStorage": "1.2.840.10008.5.1.4.1.1.9.6.2",  # A.34.16
    "RoutineScalpElectroencephalogramWaveformStorage": "1.2.840.10008.5.1.4.1.1.9.7.1",  # A.34.12
    "ElectromyogramWaveformStorage": "1.2.840.10008.5.1.4.1.1.9.7.2",  # A.34.13
    "ElectrooculogramWaveformStorage": "1.2.840.10008.5.1.4.1.1.9.7.3",  # A.34.14
    "SleepElectroencephalogramWaveformStorage": "1.2.840.10008.5.1.4.1.1.9.7.4",  # A.34.15
    "BodyPositionWaveformStorage": "1.2.840.10008.5.1.4.1.1.9.8.1",  # A.34.17
    "WaveformPresentationStateStorage": "1.2.840.10008.5.1.4.1.1.9.100.1",
    "WaveformAcquisitionPresentationStateStorage": "1.2.840.10008.5.1.4.1.1.9.100.2",
    "GrayscaleSoftcopyPresentationStateStorage": "1.2.840.10008.5.1.4.1.1.11.1",  # A.33.1
    "ColorSoftcopyPresentationStateStorage": "1.2.840.10008.5.1.4.1.1.11.2",  # A.33.2
    "PseudoColorSoftcopyPresentationStageStorage": "1.2.840.10008.5.1.4.1.1.11.3",  # A.33.3
    "BlendingSoftcopyPresentationStateStorage": "1.2.840.10008.5.1.4.1.1.11.4",  # A.33.4
    "XAXRFGrayscaleSoftcopyPresentationStateStorage": "1.2.840.10008.5.1.4.1.1.11.5",  # A.33.6
    "GrayscalePlanarMPRVolumetricPresentationStateStorage": "1.2.840.10008.5.1.4.1.1.11.6",  # A.80.1
    "CompositingPlanarMPRVolumetricPresentationStateStorage": "1.2.840.10008.5.1.4.1.1.11.7",  # A.80.1
    "AdvancedBlendingPresentationStateStorage": "1.2.840.10008.5.1.4.1.1.11.8",  # A.33.7
    "VolumeRenderingVolumetricPresentationStateStorage": "1.2.840.10008.5.1.4.1.1.11.9",  # A.80.2
    "SegmentedVolumeRenderingVolumetricPresentationStateStorage": "1.2.840.10008.5.1.4.1.1.11.10",  # A.80.2
    "MultipleVolumeRenderingVolumetricPresentationStateStorage": "1.2.840.10008.5.1.4.1.1.11.11",  # A.80.2
    "VariableModalityLUTSoftcopyPresentationStageStorage": "1.2.840.10008.5.1.4.1.1.11.12",
    "XRayAngiographicImageStorage": "1.2.840.10008.5.1.4.1.1.12.1",  # A.14
    "EnhancedXAImageStorage": "1.2.840.10008.5.1.4.1.1.12.1.1",  # A.47
    "XRayRadiofluoroscopicImageStorage": "1.2.840.10008.5.1.4.1.1.12.2",  # A.16
    "EnhancedXRFImageStorage": "1.2.840.10008.5.1.4.1.1.12.2.1",  # A.48
    "XRay3DAngiographicImageStorage": "1.2.840.10008.5.1.4.1.1.13.1.1",  # A.53
    "XRay3DCraniofacialImageStorage": "1.2.840.10008.5.1.4.1.1.13.1.2",  # A.54
    "BreastTomosynthesisImageStorage": "1.2.840.10008.5.1.4.1.1.13.1.3",  # A.55
    "BreastProjectionXRayImageStorageForPresentation": "1.2.840.10008.5.1.4.1.1.13.1.4",  # A.74
    "BreastProjectionXRayImageStorageForProcessing": "1.2.840.10008.5.1.4.1.1.13.1.5",  # A.74
    "IntravascularOpticalCoherenceTomographyImageStorageForPresentation": "1.2.840.10008.5.1.4.1.1.14.1",  # A.66
    "IntravascularOpticalCoherenceTomographyImageStorageForProcessing": "1.2.840.10008.5.1.4.1.1.14.2",  # A.66
    "NuclearMedicineImageStorage": "1.2.840.10008.5.1.4.1.1.20",  # A.5
    "ParametricMapStorage": "1.2.840.10008.5.1.4.1.1.30",  # A.75
    "RawDataStorage": "1.2.840.10008.5.1.4.1.1.66",  # A.37
    "SpatialRegistrationStorage": "1.2.840.10008.5.1.4.1.1.66.1",  # A.39.1
    "SpatialFiducialsStorage": "1.2.840.10008.5.1.4.1.1.66.2",  # A.40
    "DeformableSpatialRegistrationStorage": "1.2.840.10008.5.1.4.1.1.66.3",  # A.39.2
    "SegmentationStorage": "1.2.840.10008.5.1.4.1.1.66.4",  # A.51
    "SurfaceSegmentationStorage": "1.2.840.10008.5.1.4.1.1.66.5",  # A.57
    "TractographyResultsStorage": "1.2.840.10008.5.1.4.1.1.66.6",  # A.78
    "LabelMapSegmentationStorage": "1.2.840.10008.5.1.4.1.1.66.7",
    "HeightMapSegmentationStorage": "1.2.840.10008.5.1.4.1.1.66.8",
    "RealWorldValueMappingStorage": "1.2.840.10008.5.1.4.1.1.67",  # A.46
    "SurfaceScanMeshStorage": "1.2.840.10008.5.1.4.1.1.68.1",  # A.68
    "SurfaceScanPointCloudStorage": "1.2.840.10008.5.1.4.1.1.68.2",  # A.69
    "VLEndoscopicImageStorage": "1.2.840.10008.5.1.4.1.1.77.1.1",  # A.32.1
    "VideoEndoscopicImageStorage": "1.2.840.10008.5.1.4.1.1.77.1.1.1",  # A.32.5
    "VLMicroscopicImageStorage": "1.2.840.10008.5.1.4.1.1.77.1.2",  # A.32.2
    "VideoMicroscopicImageStorage": "1.2.840.10008.5.1.4.1.1.77.1.2.1",  # A.32.6
    "VLSlideCoordinatesMicroscopicImageStorage": "1.2.840.10008.5.1.4.1.1.77.1.3",  # A.32.3
    "VLPhotographicImageStorage": "1.2.840.10008.5.1.4.1.1.77.1.4",  # A.32.4
    "VideoPhotographicImageStorage": "1.2.840.10008.5.1.4.1.1.77.1.4.1",  # A.32.7
    "OphthalmicPhotography8BitImageStorage": "1.2.840.10008.5.1.4.1.1.77.1.5.1",  # A.41
    "OphthalmicPhotography16BitImageStorage": "1.2.840.10008.5.1.4.1.1.77.1.5.2",  # A.42
    "StereometricRelationshipStorage": "1.2.840.10008.5.1.4.1.1.77.1.5.3",  # A.43
    "OphthalmicTomographyImageStorage": "1.2.840.10008.5.1.4.1.1.77.1.5.4",  # A.52
    "WideFieldOphthalmicPhotographyStereographicProjectionImageStorage": "1.2.840.10008.5.1.4.1.1.77.1.5.5",  # A.76
    "WideFieldOphthalmicPhotography3DCoordinatesImageStorage": "1.2.840.10008.5.1.4.1.1.77.1.5.6",  # A.77
    "OphthalmicOpticalCoherenceTomographyEnFaceImageStorage": "1.2.840.10008.5.1.4.1.1.77.1.5.7",  # A.83
    "OphthlamicOpticalCoherenceTomographyBscanVolumeAnalysisStorage": "1.2.840.10008.5.1.4.1.1.77.1.5.8",  # A.84
    "VLWholeSlideMicroscopyImageStorage": "1.2.840.10008.5.1.4.1.1.77.1.6",  # A.32.8
    "DermoscopicPhotographyImageStorage": "1.2.840.10008.5.1.4.1.1.77.1.7",  # A.32.11
    "ConfocalMicroscopyImageStorage": "1.2.840.10008.5.1.4.1.1.77.1.8",
    "ConfocalMicroscopyTiledPyramidalImageStorage": "1.2.840.10008.5.1.4.1.1.77.1.9",
    "LensometryMeasurementsStorage": "1.2.840.10008.5.1.4.1.1.78.1",  # A.60.1
    "AutorefractionMeasurementsStorage": "1.2.840.10008.5.1.4.1.1.78.2",  # A.60.2
    "KeratometryMeasurementsStorage": "1.2.840.10008.5.1.4.1.1.78.3",  # A.60.3
    "SubjectiveRefractionMeasurementsStorage": "1.2.840.10008.5.1.4.1.1.78.4",  # A.60.4
    "VisualAcuityMeasurementsStorage": "1.2.840.10008.5.1.4.1.1.78.5",  # A.60.5
    "SpectaclePrescriptionReportStorage": "1.2.840.10008.5.1.4.1.1.78.6",  # A.35.9
    "OphthalmicAxialMeasurementsStorage": "1.2.840.10008.5.1.4.1.1.78.7",  # A.60.6
    "IntraocularLensCalculationsStorage": "1.2.840.10008.5.1.4.1.1.78.8",  # A.60.7
    "MacularGridThicknessAndVolumeReportStorage": "1.2.840.10008.5.1.4.1.1.79.1",  # A.35.11
    "OphthalmicVisualFieldStaticPerimetryMeasurementsStorage": "1.2.840.10008.5.1.4.1.1.80.1",  # A.65
    "OphthalmicThicknessMapStorage": "1.2.840.10008.5.1.4.1.1.81.1",  # A.67
    "CornealTopographyMapStorage": "1.2.840.10008.5.1.4.1.1.82.1",  # A.73
    "BasicTextSRStorage": "1.2.840.10008.5.1.4.1.1.88.11",  # A.35.1
    "EnhancedSRStorage": "1.2.840.10008.5.1.4.1.1.88.22",  # A.35.2
    "ComprehensiveSRStorage": "1.2.840.10008.5.1.4.1.1.88.33",  # A.35.3
    "Comprehensive3DSRStorage": "1.2.840.10008.5.1.4.1.1.88.34",  # A.35.13
    "ExtensibleSRStorage": "1.2.840.10008.5.1.4.1.1.88.35",  # A.35.15
    "ProcedureLogStorage": "1.2.840.10008.5.1.4.1.1.88.40",  # A.35.7
    "MammographyCADSRStorage": "1.2.840.10008.5.1.4.1.1.88.50",  # A.35.5
    "KeyObjectSelectionDocumentStorage": "1.2.840.10008.5.1.4.1.1.88.59",  # A.35.4
    "ChestCADSRStorage": "1.2.840.10008.5.1.4.1.1.88.65",  # A.35.6
    "XRayRadiationDoseSRStorage": "1.2.840.10008.5.1.4.1.1.88.67",  # A.35.8
    "RadiopharmaceuticalRadiationDoseSRStorage": "1.2.840.10008.5.1.4.1.1.88.68",  # A.35.14
    "ColonCADSRStorage": "1.2.840.10008.5.1.4.1.1.88.69",  # A.35.10
    "ImplantationPlanSRStorage": "1.2.840.10008.5.1.4.1.1.88.70",  # A.35.12
    "AcquisitionContextSRStorage": "1.2.840.10008.5.1.4.1.1.88.71",  # A.35.16
    "SimplifiedAdultEchoSRStorage": "1.2.840.10008.5.1.4.1.1.88.72",  # A.35.17
    "PatientRadiationDoseSRStorage": "1.2.840.10008.5.1.4.1.1.88.73",  # A.35.18
    "PlannedImagingAgentAdministrationSRStorage": "1.2.840.10008.5.1.4.1.1.88.74",  # A.35.19
    "PerformedImagingAgentAdministrationSRStorage": "1.2.840.10008.5.1.4.1.1.88.75",  # A.35.20
    "EnhancedXRayRadiationDoseSRStorage": "1.2.840.10008.5.1.4.1.1.88.76",  # A.35.
    "WaveformAnnotationSRStorage": "1.2.840.10008.5.1.4.1.1.88.77",
    "ContentAssessmentResultsStorage": "1.2.840.10008.5.1.4.1.1.90.1",  # A.81
    "MicroscopyBulkSimpleAnnotationsStorage": "1.2.840.10008.5.1.4.1.1.91.1",
    "EncapsulatedPDFStorage": "1.2.840.10008.5.1.4.1.1.104.1",  # A.45.1
    "EncapsulatedCDAStorage": "1.2.840.10008.5.1.4.1.1.104.2",  # A.45.2
    "EncapsulatedSTLStorage": "1.2.840.10008.5.1.4.1.1.104.3",  # A.85.1
    "EncapsulatedOBJStorage": "1.2.840.10008.5.1.4.1.1.104.4",  # A.85.2
    "EncapsulatedMTLStorage": "1.2.840.10008.5.1.4.1.1.104.5",  # A.85.3
    "PositronEmissionTomographyImageStorage": "1.2.840.10008.5.1.4.1.1.128",  # A.21
    "LegacyConvertedEnhancedPETImageStorage": "1.2.840.10008.5.1.4.1.1.128.1",  # A.72
    "EnhancedPETImageStorage": "1.2.840.10008.5.1.4.1.1.130",  # A.56
    "BasicStructuredDisplayStorage": "1.2.840.10008.5.1.4.1.1.131",  # A.33.5
    "CTPerformedProcedureProtocolStorage": "1.2.840.10008.5.1.4.1.1.200.2",  # A.82.1
    "XAPerformedProcedureProtocolStorage": "1.2.840.10008.5.1.4.1.1.200.8",
    "RTImageStorage": "1.2.840.10008.5.1.4.1.1.481.1",  # A.17
    "RTDoseStorage": "1.2.840.10008.5.1.4.1.1.481.2",  # A.18
    "RTStructureSetStorage": "1.2.840.10008.5.1.4.1.1.481.3",  # A.19
    "RTBeamsTreatmentRecordStorage": "1.2.840.10008.5.1.4.1.1.481.4",  # A.29
    "RTPlanStorage": "1.2.840.10008.5.1.4.1.1.481.5",  # A.20
    "RTBrachyTreatmentRecordStorage": "1.2.840.10008.5.1.4.1.1.481.6",  # A.20
    "RTTreatmentSummaryRecordStorage": "1.2.840.10008.5.1.4.1.1.481.7",  # A.31
    "RTIonPlanStorage": "1.2.840.10008.5.1.4.1.1.481.8",  # A.49
    "RTIonBeamsTreatmentRecordStorage": "1.2.840.10008.5.1.4.1.1.481.9",  # A.50
    "RTPhysicianIntentStorage": "1.2.840.10008.5.1.4.1.1.481.10",  # A.86.1.2
    "RTSegmentAnnotationStorage": "1.2.840.10008.5.1.4.1.1.481.11",  # A.86.1.3
    "RTRadiationSetStorage": "1.2.840.10008.5.1.4.1.1.481.12",  # A.86.1.4
    "CArmPhotonElectronRadiationStorage": "1.2.840.10008.5.1.4.1.1.481.13",  # A.86.1.5
    "TomotherapeuticRadiationStorage": "1.2.840.10008.5.1.4.1.1.481.14",  # A.86.1.6
    "RoboticArmRadiationStorage": "1.2.840.10008.5.1.4.1.1.481.15",  # A.86.1.7
    "RTRadiationRecordSetStorage": "1.2.840.10008.5.1.4.1.1.481.16",  # A.86.1.8
    "RTRadiationSalvageRecordStorage": "1.2.840.10008.5.1.4.1.1.481.17",  # A.86.1.9
    "TomotherapeuticRadiationRecordStorage": "1.2.840.10008.5.1.4.1.1.481.18",  # A.86.1.10
    "CArmPhotonElectronRadiationRecordStorage": "1.2.840.10008.5.1.4.1.1.481.19",  # A.86.1.11
    "RoboticArmRadiationRecordStorage": "1.2.840.10008.5.1.4.1.1.481.20",  # A.86.1.12
    "RTRadiationSetDeliveryInstructionStorage": "1.2.840.10008.5.1.4.1.1.481.21",
    "RTTreatmentPreparationStorage": "1.2.840.10008.5.1.4.1.1.481.22",
    "EnhancedRTImageStorage": "1.2.840.10008.5.1.4.1.1.481.23",
    "EnhancedContinuousRTImageStorage": "1.2.840.10008.5.1.4.1.1.481.24",
    "RTPatientPositionAcquisitionInstructionStorage": "1.2.840.10008.5.1.4.1.1.481.25",
    "RTBeamsDeliveryInstructionStorage": "1.2.840.10008.5.1.4.34.7",  # A.64
    "RTBrachyApplicationSetupDeliveryInstructionsStorage": "1.2.840.10008.5.1.4.34.10",  # A.79
}
_STORAGE_COMMITMENT_CLASSES = {
    "StorageCommitmentPushModel": "1.2.840.10008.1.20.1",
}
_STORAGE_MANAGEMENT_CLASSES = {
    "InventoryCreation": "1.2.840.10008.5.1.4.1.1.201.5",
}
_SUBSTANCE_ADMINISTRATION_CLASSES = {
    "ProductCharacteristicsQuery": "1.2.840.10008.5.1.4.41",
    "SubstanceApprovalQuery": "1.2.840.10008.5.1.4.42",
}
_UNIFIED_PROCEDURE_STEP_CLASSES = {
    "UnifiedProcedureStepPush": "1.2.840.10008.5.1.4.34.6.1",
    "UnifiedProcedureStepWatch": "1.2.840.10008.5.1.4.34.6.2",
    "UnifiedProcedureStepPull": "1.2.840.10008.5.1.4.34.6.3",
    "UnifiedProcedureStepEvent": "1.2.840.10008.5.1.4.34.6.4",
    "UnifiedProcedureStepQuery": "1.2.840.10008.5.1.4.34.6.5",
}
_VERIFICATION_CLASSES = {
    "Verification": "1.2.840.10008.1.1",
}


_SERVICE_TO_UID_GROUP = {
    VerificationServiceClass: _VERIFICATION_CLASSES,
    QueryRetrieveServiceClass: _QR_CLASSES,
    StorageServiceClass: _STORAGE_CLASSES,
    ApplicationEventLoggingServiceClass: _APPLICATION_EVENT_CLASSES,
    BasicWorklistManagementServiceClass: _BASIC_WORKLIST_CLASSES,
    ColorPaletteQueryRetrieveServiceClass: _COLOR_PALETTE_CLASSES,
    DefinedProcedureProtocolQueryRetrieveServiceClass: _DEFINED_PROCEDURE_CLASSES,
    DisplaySystemManagementServiceClass: _DISPLAY_SYSTEM_CLASSES,
    HangingProtocolQueryRetrieveServiceClass: _HANGING_PROTOCOL_CLASSES,
    ImplantTemplateQueryRetrieveServiceClass: _IMPLANT_TEMPLATE_CLASSES,
    InstanceAvailabilityNotificationServiceClass: _INSTANCE_AVAILABILITY_CLASSES,
    MediaCreationManagementServiceClass: _MEDIA_CREATION_CLASSES,
    NonPatientObjectStorageServiceClass: _NON_PATIENT_OBJECT_CLASSES,
    PrintManagementServiceClass: _PRINT_MANAGEMENT_CLASSES,
    ProcedureStepServiceClass: _PROCEDURE_STEP_CLASSES,
    ProtocolApprovalQueryRetrieveServiceClass: _PROTOCOL_APPROVAL_CLASSES,
    RelevantPatientInformationQueryServiceClass: _RELEVANT_PATIENT_QUERY_CLASSES,
    RTMachineVerificationServiceClass: _RT_MACHINE_VERIFICATION_CLASSES,
    StorageCommitmentServiceClass: _STORAGE_COMMITMENT_CLASSES,
    SubstanceAdministrationQueryServiceClass: _SUBSTANCE_ADMINISTRATION_CLASSES,
    UnifiedProcedureStepServiceClass: _UNIFIED_PROCEDURE_STEP_CLASSES,
}


# pylint: enable=line-too-long
_generate_sop_classes(_APPLICATION_EVENT_CLASSES)
_generate_sop_classes(_BASIC_WORKLIST_CLASSES)
_generate_sop_classes(_COLOR_PALETTE_CLASSES)
_generate_sop_classes(_DEFINED_PROCEDURE_CLASSES)
_generate_sop_classes(_DISPLAY_SYSTEM_CLASSES)
_generate_sop_classes(_HANGING_PROTOCOL_CLASSES)
_generate_sop_classes(_IMPLANT_TEMPLATE_CLASSES)
_generate_sop_classes(_INSTANCE_AVAILABILITY_CLASSES)
_generate_sop_classes(_INVENTORY_CLASSES)
_generate_sop_classes(_MEDIA_CREATION_CLASSES)
_generate_sop_classes(_MEDIA_STORAGE_CLASSES)
_generate_sop_classes(_NON_PATIENT_OBJECT_CLASSES)
_generate_sop_classes(_PRINT_MANAGEMENT_CLASSES)
_generate_sop_classes(_PROCEDURE_STEP_CLASSES)
_generate_sop_classes(_PROTOCOL_APPROVAL_CLASSES)
_generate_sop_classes(_QR_CLASSES)
_generate_sop_classes(_RELEVANT_PATIENT_QUERY_CLASSES)
_generate_sop_classes(_RT_MACHINE_VERIFICATION_CLASSES)
_generate_sop_classes(_STORAGE_CLASSES)
_generate_sop_classes(_STORAGE_COMMITMENT_CLASSES)
_generate_sop_classes(_STORAGE_MANAGEMENT_CLASSES)
_generate_sop_classes(_SUBSTANCE_ADMINISTRATION_CLASSES)
_generate_sop_classes(_UNIFIED_PROCEDURE_STEP_CLASSES)
_generate_sop_classes(_VERIFICATION_CLASSES)


def uid_to_sop_class(uid: str) -> SOPClass:
    """Return the :class:`SOPClass` object corresponding to `uid`.

    Parameters
    ----------
    uid : pydicom.uid.UID
        Return the corresponding object for this UID.

    Returns
    -------
    sop_class.SOPClass subclass
        The SOP class corresponding to `uid`.

    Raises
    ------
    NotImplementedError
        If the SOP Class corresponding to the given UID has not been
        implemented.
    """
    # Get a list of all the class members of the current module
    members = inspect.getmembers(
        sys.modules[__name__], lambda mbr: isinstance(mbr, str)
    )

    for obj in members:
        if hasattr(obj[1], "service_class") and obj[1] == uid:
            return cast(SOPClass, obj[1])

    sop_class = SOPClass(uid)
    sop_class._service_class = ServiceClass

    return sop_class


def register_uid(
    uid: str,
    keyword: str,
    service_class: Type[ServiceClass],
    dimse_msg_type: str = "",
) -> None:
    """Register a private or public SOP Class UID `uid` with the
    :mod:`~pynetdicom.sop_class` module.

    Examples
    --------

    Register the UID ``1.2.246.352.70.1.70`` with the
    :class:`~pynetdicom.service_class.StorageServiceClass`::

        >>> from pynetdicom import register_uid
        >>> from pynetdicom.service_class import StorageServiceClass
        >>> register_uid(
        ...     "1.2.246.352.70.1.70",
        ...     "FooStorage",
        ...     StorageServiceClass,
        ... )

    Using a UID after registration::

        >>> from pynetdicom import AE
        >>> from pynetdicom.sop_class import FooStorage
        >>> ae = AE()
        >>> ae.add_supported_context(FooStorage)

    Parameters
    ----------
    uid : str
        The UID to be registered.
    keyword : str
        The keyword to use for the UID, must be a valid Python identifier and
        may not be a Python keyword.
    service_class : pynetdicom.service_class.ServiceClass
        The service that the `uid` will be registered with, such as
        :class:`~pynetdicom.service_class.StorageServiceClass`. Note that this
        must be the class object itself and not a class instance.
    dimse_msg_type : str, optional
        If `service_class` is
        :class:`~pynetdicom.service_class.QueryRetrieveServiceClass` then this
        should be the DIMSE service message type that the `uid` is being
        registered to. One of (``"C-FIND"``, ``"C-GET"``, ``"C-MOVE"``).
    """
    if not keyword.isidentifier() or iskeyword(keyword):
        raise ValueError(
            f"The keyword '{keyword}' is not a valid Python identifier or is "
            "a Python keyword"
        )

    if not inspect.isclass(service_class):
        raise TypeError("'service_class' must be a class object not a class instance")

    if not issubclass(service_class, ServiceClass):
        raise TypeError(
            "'service_class' must be a ServiceClass subclass object "
            "such as 'StorageServiceClass'"
        )

    group = _SERVICE_TO_UID_GROUP[service_class]
    group[keyword] = uid

    sop_class = SOPClass(uid)
    sop_class._service_class = uid_to_service_class(uid)
    globals()[keyword] = sop_class

    if issubclass(service_class, QueryRetrieveServiceClass):
        if service_class is QueryRetrieveServiceClass:
            if dimse_msg_type not in ("C-FIND", "C-GET", "C-MOVE"):
                raise ValueError(
                    "'dimse_msg_type' must be 'C-FIND', 'C-GET' or 'C-MOVE' "
                    "when registering a UID with QueryRetrieveServiceClass"
                )
            service_class._SUPPORTED_UIDS[dimse_msg_type].append(uid)
        else:
            service_class._SUPPORTED_UIDS["C-FIND"].append(uid)


# Well-known SOP Instance UIDs for the supported Service Classes
DisplaySystemInstance = UID("1.2.840.10008.5.1.1.40.1")
"""``1.2.840.10008.5.1.1.40.1``"""
PrinterConfigurationRetrievalInstance = UID("1.2.840.10008.5.1.1.17.376")
"""``1.2.840.10008.5.1.1.17.376``"""
PrinterInstance = UID("1.2.840.10008.5.1.1.17")
"""``1.2.840.10008.5.1.1.17``"""
ProceduralEventLoggingInstance = UID("1.2.840.10008.1.40.1")
"""``1.2.840.10008.1.40.1``"""
StorageCommitmentPushModelInstance = UID("1.2.840.10008.1.20.1.1")
"""``1.2.840.10008.1.20.1.1``"""
StorageManagementInstance = UID("1.2.840.10008.5.1.4.1.1.201.1.1")
"""``1.2.840.10008.5.1.4.1.1.201.1.1``

.. versionadded:: 2.1
"""
SubstanceAdministrationLoggingInstance = UID("1.2.840.10008.1.42.1")
"""``1.2.840.10008.1.42.1``"""
UPSFilteredGlobalSubscriptionInstance = UID("1.2.840.10008.5.1.4.34.5.1")
"""``1.2.840.10008.5.1.4.34.5.1``"""
UPSGlobalSubscriptionInstance = UID("1.2.840.10008.5.1.4.34.5")
"""``1.2.840.10008.5.1.4.34.5``"""
