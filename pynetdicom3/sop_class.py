"""Generates the supported SOP Classes."""

from collections import namedtuple
import inspect
import logging
import sys

from pydicom.uid import UID

from pynetdicom3.service_class import (
    VerificationServiceClass,
    StorageServiceClass,
    QueryRetrieveServiceClass,
    BasicWorklistManagementServiceClass,
)

LOGGER = logging.getLogger('pynetdicom3.sop')


def uid_to_service_class(uid):
    """Return the ServiceClass object corresponding to `uid`.

    Parameters
    ----------
    uid : pydicom.uid.UID
        The SOP Class UID to find the corresponding Service Class.

    Returns
    -------
    service_class.ServiceClass
        The Service Class corresponding to the SOP Class UID.

    Raises
    ------
    NotImplementedError
        If the Service Class corresponding to the SOP Class `uid` hasn't been
        implemented.
    """
    if uid in _VERIFICATION_CLASSES.values():
        return VerificationServiceClass
    elif uid in _STORAGE_CLASSES.values():
        return StorageServiceClass
    elif uid in _QR_CLASSES.values():
        return QueryRetrieveServiceClass
    elif uid in _BASIC_WORKLIST_CLASSES.values():
        return BasicWorklistManagementServiceClass
    else:
        raise NotImplementedError(
            "The Service Class for the SOP Class with UID '{}' has not "
            "been implemented".format(uid)
        )


class SOPClass(namedtuple("SOPClass", ['uid', 'UID', 'service_class'])):
    """A DICOM SOP Class.

    Attributes
    ----------
    service_class : service_class.ServiceClass
        The DICOM Service Class corresponding to the SOP Class.
    uid : pydicom.uid.UID
        The SOP Class UID.
    UID : pydicom.uid.UID
        The SOP Class UID.
    """
    pass


def _generate_sop_classes(sop_class_dict):
    """Generate the SOP Classes."""
    for name in sop_class_dict:
        globals()[name] = SOPClass(
            UID(sop_class_dict[name]),
            UID(sop_class_dict[name]),
            uid_to_service_class(sop_class_dict[name])
        )


# Generate the various SOP classes
_VERIFICATION_CLASSES = {
    'VerificationSOPClass' : '1.2.840.10008.1.1',
}

# pylint: disable=line-too-long
_STORAGE_CLASSES = {
    'ComputedRadiographyImageStorage' : '1.2.840.10008.5.1.4.1.1.1',  # A.2
    'DigitalXRayImagePresentationStorage' : '1.2.840.10008.5.1.4.1.1.1.1',  # A.26
    'DigitalXRayImageProcessingStorage' : '1.2.840.10008.5.1.4.1.1.1.1.1.1',  # A.26
    'DigitalMammographyXRayImagePresentationStorage' : '1.2.840.10008.5.1.4.1.1.1.2',  # A.27
    'DigitalMammographyXRayImageProcessingStorage' : '1.2.840.10008.5.1.4.1.1.1.2.1',  # A.27
    'DigitalIntraOralXRayImagePresentationStorage' : '1.2.840.10008.5.1.4.1.1.1.3',  # A.28
    'DigitalIntraOralXRayImageProcessingStorage' : '1.2.840.10008.5.1.1.4.1.1.3.1',  # A.28
    'CTImageStorage' : '1.2.840.10008.5.1.4.1.1.2',  # A.3
    'EnhancedCTImageStorage' : '1.2.840.10008.5.1.4.1.1.2.1',  # A.38
    'LegacyConvertedEnhancedCTImageStorage' : '1.2.840.10008.5.1.4.1.1.2.2',  # A.70
    'UltrasoundMultiframeImageStorage' : '1.2.840.10008.5.1.4.1.1.3.1',  # A.7
    'MRImageStorage' : '1.2.840.10008.5.1.4.1.1.4',  # A.4
    'EnhancedMRImageStorage' : '1.2.840.10008.5.1.4.1.1.4.1',  # A.36.2
    'MRSpectroscopyStorage' : '1.2.840.10008.5.1.4.1.1.4.2',  # A.36.3
    'EnhancedMRColorImageStorage' : '1.2.840.10008.5.1.4.1.1.4.3',  # A.36.4
    'LegacyConvertedEnhancedMRImageStorage' : '1.2.840.10008.5.1.4.1.1.4.4',  # A.71
    'UltrasoundImageStorage' : '1.2.840.10008.5.1.4.1.1.6.1',  # A.6
    'EnhancedUSVolumeStorage' : '1.2.840.10008.5.1.4.1.1.6.2',  # A.59
    'SecondaryCaptureImageStorage' : '1.2.840.10008.5.1.4.1.1.7',  # A.8.1
    'MultiframeSingleBitSecondaryCaptureImageStorage' : '1.2.840.10008.5.1.4.1.1.7.1',  # A.8.2
    'MultiframeGrayscaleByteSecondaryCaptureImageStorage' : '1.2.840.10008.5.1.4.1.1.7.2',  # A.8.3
    'MultiframeGrayscaleWordSecondaryCaptureImageStorage' : '1.2.840.10008.5.1.4.1.1.7.3',  # A.8.4
    'MultiframeTrueColorSecondaryCaptureImageStorage' : '1.2.840.10008.5.1.4.1.1.7.4',  # A.8.5
    'TwelveLeadECGWaveformStorage' : '1.2.840.10008.5.1.4.1.1.9.1.1',  # A.34.3
    'GeneralECGWaveformStorage' : '1.2.840.10008.5.1.4.1.1.9.1.2',  # A.34.4
    'AmbulatoryECGWaveformStorage' : '1.2.840.10008.5.1.4.1.1.9.1.3',  # A.34.5
    'HemodynamicWaveformStorage' : '1.2.840.10008.5.1.4.1.1.9.2.1',  # A.34.6
    'CardiacElectrophysiologyWaveformStorage' : '1.2.840.10008.5.1.4.1.1.9.3.1',  # A.34.7
    'BasicVoiceAudioWaveformStorage' : '1.2.840.10008.5.1.4.1.1.9.4.1',  # A.34.2
    'GeneralAudioWaveformStorage' : '1.2.840.10008.5.1.4.1.1.9.4.2',  # A.34.10
    'ArterialPulseWaveformStorage' : '1.2.840.10008.5.1.4.1.1.9.5.1',  # A.34.8
    'RespiratoryWaveformStorage' : '1.2.840.10008.5.1.4.1.1.9.6.1',  # A.34.9
    'GrayscaleSoftcopyPresentationStateStorage' : '1.2.840.10008.5.1.4.1.1.11.1',  # A.33.1
    'ColorSoftcopyPresentationStateStorage' : '1.2.840.10008.5.1.4.1.1.11.2',  # A.33.2
    'PseudocolorSoftcopyPresentationStageStorage' : '1.2.840.10008.5.1.4.1.1.11.3',  # A.33.3
    'BlendingSoftcopyPresentationStateStorage' : '1.2.840.10008.5.1.4.1.1.11.4',  # A.33.4
    'XAXRFGrayscaleSoftcopyPresentationStateStorage' : '1.2.840.10008.5.1.4.1.1.11.5',  # A.33.6
    'GrayscalePlanarMPRVolumetricPresentationStateStorage' : '1.2.840.10008.5.1.4.1.1.11.6',  # A.80.1
    'CompositingPlanarMPRVolumetricPresentationStateStorage' : '1.2.840.10008.5.1.4.1.1.11.7',  # A.80.1
    'AdvancedBlendingPresentationStateStorage' : '1.2.840.10008.5.1.4.1.1.11.8',  # A.33.7
    'VolumeRenderingVolumetricPresentationStateStorage' : '1.2.840.10008.5.1.4.1.1.11.9',  # A.80.2
    'SegmentatedVolumeRenderingVolumetricPresentationStateStorage' : '1.2.840.10008.5.1.4.1.1.11.10',  # A.80.2
    'MultipleVolumeRenderingVolumetricPresentationStateStorage' : '1.2.840.10008.5.1.4.1.1.11.11',  # A.80.2
    'XRayAngiographicImageStorage' : '1.2.840.10008.5.1.4.1.1.12.1',  # A.14
    'EnhancedXAImageStorage' : '1.2.840.10008.5.1.4.1.1.12.1.1',  # A.47
    'XRayRadiofluoroscopicImageStorage' : '1.2.840.10008.5.1.4.1.1.12.2',  # A.16
    'EnhancedXRFImageStorage' : '1.2.840.10008.5.1.4.1.1.12.2.1',  # A.48
    'XRay3DAngiographicImageStorage' : '1.2.840.10008.5.1.4.1.1.13.1.1',  # A.53
    'XRay3DCraniofacialImageStorage' : '1.2.840.10008.5.1.4.1.1.13.1.2',  # A.54
    'BreastTomosynthesisImageStorage' : '1.2.840.10008.5.1.4.1.1.13.1.3',  # A.55
    'BreastProjectionXRayImagePresentationStorage' : '1.2.840.10008.5.1.4.1.1.13.1.4',  # A.74
    'BreastProjectionXRayImageProcessingStorage' : '1.2.840.10008.5.1.4.1.1.13.1.5',  # A.74
    'IntravascularOpticalCoherenceTomographyImagePresentationStorage' : '1.2.840.10008.5.1.4.1.1.14.1',  # A.66
    'IntravascularOpticalCoherenceTomographyImageProcessingStorage' : '1.2.840.10008.5.1.4.1.1.14.2',  # A.66
    'NuclearMedicineImageStorage' : '1.2.840.10008.5.1.4.1.1.20',    # A.5
    'ParametricMapStorage' : '1.2.840.10008.5.1.4.1.1.30',  # A.75
    'RawDataStorage' : '1.2.840.10008.5.1.4.1.1.66',  # A.37
    'SpatialRegistrationStorage' : '1.2.840.10008.5.1.4.1.1.66.1',  # A.39.1
    'SpatialFiducialsStorage' : '1.2.840.10008.5.1.4.1.1.66.2',  # A.40
    'DeformableSpatialRegistrationStorage' : '1.2.840.10008.5.1.4.1.1.66.3',  # A.39.2
    'SegmentationStorage' : '1.2.840.10008.5.1.4.1.1.66.4',  # A.51
    'SurfaceSegmentationStorage' : '1.2.840.10008.5.1.4.1.1.66.5',  # A.57
    'TractographyResultsStorage' : '1.2.840.10008.5.1.4.1.1.66.6',  # A.78
    'RealWorldValueMappingStorage' : '1.2.840.10008.5.1.4.1.1.67',  # A.46
    'SurfaceScanMeshStorage' : '1.2.840.10008.5.1.4.1.1.68.1',  # A.68
    'SurfaceScanPointCloudStorage' : '1.2.840.10008.5.1.4.1.1.68.2',  # A.69
    'VLEndoscopicImageStorage' : '1.2.840.10008.5.1.4.1.1.77.1.1',  # A.32.1
    'VideoEndoscopicImageStorage' : '1.2.840.10008.5.1.4.1.1.77.1.1.1',  # A.32.5
    'VLMicroscopicImageStorage' : '1.2.840.10008.5.1.4.1.1.77.1.2',  # A.32.2
    'VideoMicroscopicImageStorage' : '1.2.840.10008.5.1.4.1.1.77.1.2.1',  # A.32.6
    'VLSlideCoordinatesMicroscopicImageStorage' : '1.2.840.10008.5.1.4.1.1.77.1.3',  # A.32.3
    'VLPhotographicImageStorage' : '1.2.840.10008.5.1.4.1.1.77.1.4',  # A.32.4
    'VideoPhotographicImageStorage' : '1.2.840.10008.5.1.4.1.1.77.1.4.1',  # A.32.7
    'OphthalmicPhotography8BitImageStorage' : '1.2.840.10008.5.1.4.1.1.77.1.5.1',  # A.41
    'OphthalmicPhotography16BitImageStorage' : '1.2.840.10008.5.1.4.1.1.77.1.5.2',  # A.42
    'StereometricRelationshipStorage' : '1.2.840.10008.5.1.4.1.1.77.1.5.3',  # A.43
    'OphthalmicTomographyImageStorage' : '1.2.840.10008.5.1.4.1.1.77.1.5.4',  # A.52
    'WideFieldOphthalmicPhotographyStereographicProjectionImageStorage' : '1.2.840.10008.5.1.4.1.1.77.1.5.5',  # A.76
    'WideFieldOphthalmicPhotography3DCoordinatesImageStorage' : '1.2.840.10008.5.1.4.1.1.77.1.5.6',  # A.77
    'OphthalmicOpticalCoherenceTomographyEnFaceImageStorage' : '1.2.840.10008.5.1.4.1.1.77.1.5.7',  # A.83
    'OphthlamicOpticalCoherenceTomographyBScanVolumeAnalysisStorage' : '1.2.840.10008.5.1.4.1.1.77.1.5.8',  # A.84
    'VLWholeSlideMicroscopyImageStorage' : '1.2.840.10008.5.1.4.1.1.77.1.6',  # A.32.8
    'LensometryMeasurementsStorage' : '1.2.840.10008.5.1.4.1.1.78.1',  # A.60.1
    'AutorefractionMeasurementsStorage' : '1.2.840.10008.5.1.4.1.1.78.2',  # A.60.2
    'KeratometryMeasurementsStorage' : '1.2.840.10008.5.1.4.1.1.78.3',  # A.60.3
    'SubjectiveRefractionMeasurementsStorage' : '1.2.840.10008.5.1.4.1.1.78.4',  # A.60.4
    'VisualAcuityMeasurementsStorage' : '1.2.840.10008.5.1.4.1.1.78.5',  # A.60.5
    'SpectaclePrescriptionReportStorage' : '1.2.840.10008.5.1.4.1.1.78.6',  # A.35.9
    'OphthalmicAxialMeasurementsStorage' : '1.2.840.10008.5.1.4.1.1.78.7',  # A.60.6
    'IntraocularLensCalculationsStorage' : '1.2.840.10008.5.1.4.1.1.78.8',  # A.60.7
    'MacularGridThicknessAndVolumeReport' : '1.2.840.10008.5.1.4.1.1.79.1',  # A.35.11
    'OphthalmicVisualFieldStaticPerimetryMeasurementsStorage' : '1.2.840.10008.5.1.4.1.1.80.1',  # A.65
    'OphthalmicThicknessMapStorage' : '1.2.840.10008.5.1.4.1.1.81.1',  # A.67
    'CornealTopographyMapStorage' : '1.2.840.10008.5.1.4.1.1.82.1',  # A.73
    'BasicTextSRStorage' : '1.2.840.10008.5.1.4.1.1.88.11',  # A.35.1
    'EnhancedSRStorage' : '1.2.840.10008.5.1.4.1.1.88.22',  # A.35.2
    'ComprehensiveSRStorage' : '1.2.840.10008.5.1.4.1.1.88.33',  # A.35.3
    'Comprehensive3DSRStorage' : '1.2.840.10008.5.1.4.1.1.88.34',  # A.35.13
    'ExtensibleSRStorage' : '1.2.840.10008.5.1.4.1.1.88.35',  # A.35.15
    'ProcedureSRStorage' : '1.2.840.10008.5.1.4.1.1.88.40',  # A.35.7
    'MammographyCADSRStorage' : '1.2.840.10008.5.1.4.1.1.88.50',  # A.35.5
    'KeyObjectSelectionStorage' : '1.2.840.10008.5.1.4.1.1.88.59',  # A.35.4
    'ChestCADSRStorage' : '1.2.840.10008.5.1.4.1.1.88.65',  # A.35.6
    'XRayRadiationDoseSRStorage' : '1.2.840.10008.5.1.4.1.1.88.67',  # A.35.8
    'RadiopharmaceuticalRadiationDoseSRStorage' : '1.2.840.10008.5.1.4.1.1.88.68',  # A.35.14
    'ColonCADSRStorage' : '1.2.840.10008.5.1.4.1.1.88.69',  # A.35.10
    'ImplantationPlanSRDocumentStorage' : '1.2.840.10008.5.1.4.1.1.88.70',  # A.35.12
    'AcquisitionContextSRStorage' : '1.2.840.10008.5.1.4.1.1.88.71',  # A.35.16
    'SimplifiedAdultEchoSRStorage' : '1.2.840.10008.5.1.4.1.1.88.72',  # A.35.17
    'PatientRadiationDoseSRStorage' : '1.2.840.10008.5.1.4.1.1.88.73',  # A.35.18
    'ContentAssessmentResultsStorage' : '1.2.840.10008.5.1.4.1.1.90.1',  # A.81
    'EncapsulatedPDFStorage' : '1.2.840.10008.5.1.4.1.1.104.1',  # A.45.1
    'EncapsulatedCDAStorage' : '1.2.840.10008.5.1.4.1.1.104.2',  # A.45.2
    'EncapsulatedSTLStorage' : '1.2.840.10008.5.1.4.1.1.104.3',  # A.85.1
    'PositronEmissionTomographyImageStorage' : '1.2.840.10008.5.1.4.1.1.128',  # A.21
    'EnhancedPETImageStorage' : '1.2.840.10008.5.1.4.1.1.130',  # A.56
    'LegacyConvertedEnhancedPETImageStorage' : '1.2.840.10008.5.1.4.1.1.128.1',  # A.72
    'BasicStructuredDisplayStorage' : '1.2.840.10008.5.1.4.1.1.131',  # A.33.5
    'CTPerformedProcedureProtocolStorage' : '1.2.840.10008.5.1.4.1.1.200.2',  # A.82.1
    'RTImageStorage' : '1.2.840.10008.5.1.4.1.1.481.1',  # A.17
    'RTDoseStorage' : '1.2.840.10008.5.1.4.1.1.481.2',  # A.18
    'RTStructureSetStorage' : '1.2.840.10008.5.1.4.1.1.481.3',  # A.19
    'RTBeamsTreatmentRecordStorage' : '1.2.840.10008.5.1.4.1.1.481.4',  # A.29
    'RTPlanStorage' : '1.2.840.10008.5.1.4.1.1.481.5',  # A.20
    'RTBrachyTreatmentRecordStorage' : '1.2.840.10008.5.1.4.1.1.481.6',  # A.20
    'RTTreatmentSummaryRecordStorage' : '1.2.840.10008.5.1.4.1.1.481.7',  # A.31
    'RTIonPlanStorage' : '1.2.840.10008.5.1.4.1.1.481.8',  # A.49
    'RTIonBeamsTreatmentRecordStorage' : '1.2.840.10008.5.1.4.1.1.481.9',  # A.50
    'RTBeamsDeliveryInstructionStorage' : '1.2.840.10008.5.1.4.34.7',  # A.64
    'RTBrachyApplicationSetupDeliveryInstructionsStorage' : '1.2.840.10008.5.1.4.34.10',  # A.79
}

_QR_CLASSES = {
    'PatientRootQueryRetrieveInformationModelFind' : '1.2.840.10008.5.1.4.1.2.1.1',
    'PatientRootQueryRetrieveInformationModelMove' : '1.2.840.10008.5.1.4.1.2.1.2',
    'PatientRootQueryRetrieveInformationModelGet' : '1.2.840.10008.5.1.4.1.2.1.3',
    'StudyRootQueryRetrieveInformationModelFind' : '1.2.840.10008.5.1.4.1.2.2.1',
    'StudyRootQueryRetrieveInformationModelMove' : '1.2.840.10008.5.1.4.1.2.2.2',
    'StudyRootQueryRetrieveInformationModelGet' : '1.2.840.10008.5.1.4.1.2.2.3',
    'PatientStudyOnlyQueryRetrieveInformationModelFind' : '1.2.840.10008.5.1.4.1.2.3.1',
    'PatientStudyOnlyQueryRetrieveInformationModelMove' : '1.2.840.10008.5.1.4.1.2.3.2',
    'PatientStudyOnlyQueryRetrieveInformationModelGet' : '1.2.840.10008.5.1.4.1.2.3.3',
    'CompositeInstanceRetrieveWithoutBulkDataGet' : '1.2.840.10008.5.1.4.1.2.5.3',
}

_BASIC_WORKLIST_CLASSES = {
    'ModalityWorklistInformationFind' : '1.2.840.10008.5.1.4.31',
}

# pylint: enable=line-too-long
_generate_sop_classes(_VERIFICATION_CLASSES)
_generate_sop_classes(_STORAGE_CLASSES)
_generate_sop_classes(_QR_CLASSES)
_generate_sop_classes(_BASIC_WORKLIST_CLASSES)


def uid_to_sop_class(uid):
    """Return the SOPClass object corresponding to `uid`.

    Parameters
    ----------
    uid : pydicom.uid.UID

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
        sys.modules[__name__],
        lambda mbr: isinstance(mbr, tuple)
    )

    for obj in members:
        if hasattr(obj[1], 'uid') and obj[1].uid == uid:
            return obj[1]

    raise NotImplementedError("The SOP Class for UID '{}' has not been " \
                              "implemented".format(uid))
