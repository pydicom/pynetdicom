"""
Defines the supported Service Classes and generates their SOP Classes.
"""
import inspect
import logging
import sys

from pydicom.uid import UID

from pynetdicom3.service_classes import (
    VerificationServiceClass,
    StorageServiceClass,
    QueryRetrieveServiceClass,
    QueryRetrieveFindServiceClass,
    QueryRetrieveMoveServiceClass,
    QueryRetrieveGetServiceClass,
    BasicWorklistManagementServiceClass,
)

LOGGER = logging.getLogger('pynetdicom3.sop')


# Deprecated, will be removed
def _class_factory(name, uid, base_cls):
    """Generates a SOP Class subclass of `base_cls` called `name`.

    Parameters
    ----------
    name : str
        The name of the SOP class
    uid : pydicom.uid.UID
        The UID of the SOP class
    base_cls : pynetdicom3.sop_class.ServiceClass subclass
        One of the following Service classes:
            VerificationServiceClass
            StorageServiceClass
            QueryRetrieveFindServiceClass
            QueryRetrieveGetServiceClass
            QueryRetrieveMoveServiceClass

    Returns
    -------
    subclass of BaseClass
        The new class
    """
    def __init__(self):
        base_cls.__init__(self)

    new_class = type(name, (base_cls,), {"__init__": __init__})
    new_class.UID = uid

    return new_class

# Deprecated, will be removed
def _generate_service_sop_classes(sop_class_list, service_class):
    """Generate the SOP Classes."""
    for name in sop_class_list:
        cls = _class_factory(name, UID(sop_class_list[name]), service_class)
        globals()[cls.__name__] = cls


def _sop_class_factory(name, uid):
    """Return a SOPClass subclass called `name`.

    Parameters
    ----------
    name : str
        The name of the SOP class
    uid : pydicom.uid.UID
        The UID of the SOP class

    Returns
    -------
    subclass of sop_class.SOPClass
        The new class
    """
    def __init__(self):
        SOPClass.__init__(self)

    new_class = type(name, (SOPClass,), {"__init__": __init__})
    new_class._uid = uid

    return new_class


def _generate_sop_classes(sop_class_dict):
    """Generate the SOP Classes."""
    for name in sop_class_dict:
        cls = _sop_class_factory(name, UID(sop_class_dict[name]))
        globals()[cls.__name__] = cls


class SOPClass(object):
    # The SOP Class UID
    _uid = None

    @property
    def service_class(self):
        """Return the Service Class corresponding to the SOP Class.

        Returns
        -------
        service_classes.ServiceClass
            The Service Class corresponding to the SOP Class.
        """
        return uid_to_service_class(self.uid)

    @property
    def UID(self):
        """Return the SOP Class' UID as a pydicom UID."""
        return self._uid

    @property
    def uid(self):
        """Return the SOP Class' UID as a pydicom UID."""
        return self._uid


# Generate the various SOP classes
_VERIFICATION_CLASSES = {'VerificationSOPClass' : '1.2.840.10008.1.1'}

# pylint: disable=line-too-long
_STORAGE_CLASSES = {
    'ComputedRadiographyImageStorage' : '1.2.840.10008.5.1.4.1.1.1',
    'DigitalXRayImagePresentationStorage' : '1.2.840.10008.5.1.4.1.1.1.1',
    'DigitalXRayImageProcessingStorage' : '1.2.840.10008.5.1.4.1.1.1.1.1.1',
    'DigitalMammographyXRayImagePresentationStorage' : '1.2.840.10008.5.1.4.1.1.1.2',
    'DigitalMammographyXRayImageProcessingStorage' : '1.2.840.10008.5.1.4.1.1.1.2.1',
    'DigitalIntraOralXRayImagePresentationStorage' : '1.2.840.10008.5.1.4.1.1.1.3',
    'DigitalIntraOralXRayImageProcessingStorage' : '1.2.840.10008.5.1.1.4.1.1.3.1',
    'CTImageStorage' : '1.2.840.10008.5.1.4.1.1.2',
    'EnhancedCTImageStorage' : '1.2.840.10008.5.1.4.1.1.2.1',
    'LegacyConvertedEnhancedCTImageStorage' : '1.2.840.10008.5.1.4.1.1.2.2',
    'UltrasoundMultiframeImageStorage' : '1.2.840.10008.5.1.4.1.1.3.1',
    'MRImageStorage' : '1.2.840.10008.5.1.4.1.1.4',
    'EnhancedMRImageStorage' : '1.2.840.10008.5.1.4.1.1.4.1',
    'MRSpectroscopyStorage' : '1.2.840.10008.5.1.4.1.1.4.2',
    'EnhancedMRColorImageStorage' : '1.2.840.10008.5.1.4.1.1.4.3',
    'LegacyConvertedEnhancedMRImageStorage' : '1.2.840.10008.5.1.4.1.1.4.4',
    'UltrasoundImageStorage' : '1.2.840.10008.5.1.4.1.1.6.1',
    'EnhancedUSVolumeStorage' : '1.2.840.10008.5.1.4.1.1.6.2',
    'SecondaryCaptureImageStorage' : '1.2.840.10008.5.1.4.1.1.7',
    'MultiframeSingleBitSecondaryCaptureImageStorage' : '1.2.840.10008.5.1.4.1.1.7.1',
    'MultiframeGrayscaleByteSecondaryCaptureImageStorage' : '1.2.840.10008.5.1.4.1.1.7.2',
    'MultiframeGrayscaleWordSecondaryCaptureImageStorage' : '1.2.840.10008.5.1.4.1.1.7.3',
    'MultiframeTrueColorSecondaryCaptureImageStorage' : '1.2.840.10008.5.1.4.1.1.7.4',
    'TwelveLeadECGWaveformStorage' : '1.2.840.10008.5.1.4.1.1.9.1.1',
    'GeneralECGWaveformStorage' : '1.2.840.10008.5.1.4.1.1.9.1.2',
    'AmbulatoryECGWaveformStorage' : '1.2.840.10008.5.1.4.1.1.9.1.3',
    'HemodynamicWaveformStorage' : '1.2.840.10008.5.1.4.1.1.9.2.1',
    'CardiacElectrophysiologyWaveformStorage' : '1.2.840.10008.5.1.4.1.1.9.3.1',
    'BasicVoiceAudioWaveformStorage' : '1.2.840.10008.5.1.4.1.1.9.4.1',
    'GeneralAudioWaveformStorage' : '1.2.840.10008.5.1.4.1.1.9.4.2',
    'ArterialPulseWaveformStorage' : '1.2.840.10008.5.1.4.1.1.9.5.1',
    'RespiratoryWaveformStorage' : '1.2.840.10008.5.1.4.1.1.9.6.1',
    'GrayscaleSoftcopyPresentationStateStorage' : '1.2.840.10008.5.1.4.1.1.11.1',
    'ColorSoftcopyPresentationStateStorage' : '1.2.840.10008.5.1.4.1.1.11.2',
    'PseudocolorSoftcopyPresentationStageStorage' : '1.2.840.10008.5.1.4.1.1.11.3',
    'BlendingSoftcopyPresentationStateStorage' : '1.2.840.10008.5.1.4.1.1.11.4',
    'XAXRFGrayscaleSoftcopyPresentationStateStorage' : '1.2.840.10008.5.1.4.1.1.11.5',
    'XRayAngiographicImageStorage' : '1.2.840.10008.5.1.4.1.1.12.1',
    'EnhancedXAImageStorage' : '1.2.840.10008.5.1.4.1.1.12.1.1',
    'XRayRadiofluoroscopicImageStorage' : '1.2.840.10008.5.1.4.1.1.12.2',
    'EnhancedXRFImageStorage' : '1.2.840.10008.5.1.4.1.1.12.2.1',
    'XRay3DAngiographicImageStorage' : '1.2.840.10008.5.1.4.1.1.13.1.1',
    'XRay3DCraniofacialImageStorage' : '1.2.840.10008.5.1.4.1.1.13.1.2',
    'BreastTomosynthesisImageStorage' : '1.2.840.10008.5.1.4.1.1.13.1.3',
    'BreastProjectionXRayImagePresentationStorage' : '1.2.840.10008.5.1.4.1.1.13.1.4',
    'BreastProjectionXRayImageProcessingStorage' : '1.2.840.10008.5.1.4.1.1.13.1.5',
    'IntravascularOpticalCoherenceTomographyImagePresentationStorage' : '1.2.840.10008.5.1.4.1.1.14.1',
    'IntravascularOpticalCoherenceTomographyImageProcessingStorage' : '1.2.840.10008.5.1.4.1.1.14.2',
    'NuclearMedicineImageStorage' : '1.2.840.10008.5.1.4.1.1.20',
    'ParametricMapStorage' : '1.2.840.10008.5.1.4.1.1.30',
    'RawDataStorage' : '1.2.840.10008.5.1.4.1.1.66',
    'SpatialRegistrationStorage' : '1.2.840.10008.5.1.4.1.1.66.1',
    'SpatialFiducialsStorage' : '1.2.840.10008.5.1.4.1.1.66.2',
    'DeformableSpatialRegistrationStorage' : '1.2.840.10008.5.1.4.1.1.66.3',
    'SegmentationStorage' : '1.2.840.10008.5.1.4.1.1.66.4',
    'SurfaceSegmentationStorage' : '1.2.840.10008.5.1.4.1.1.66.5',
    'RealWorldValueMappingStorage' : '1.2.840.10008.5.1.4.1.1.67',
    'SurfaceScanMeshStorage' : '1.2.840.10008.5.1.4.1.1.68.1',
    'SurfaceScanPointCloudStorage' : '1.2.840.10008.5.1.4.1.1.68.2',
    'VLEndoscopicImageStorage' : '1.2.840.10008.5.1.4.1.1.77.1.1',
    'VideoEndoscopicImageStorage' : '1.2.840.10008.5.1.4.1.1.77.1.1.1',
    'VLMicroscopicImageStorage' : '1.2.840.10008.5.1.4.1.1.77.1.2',
    'VideoMicroscopicImageStorage' : '1.2.840.10008.5.1.4.1.1.77.1.2.1',
    'VLSlideCoordinatesMicroscopicImageStorage' : '1.2.840.10008.5.1.4.1.1.77.1.3',
    'VLPhotographicImageStorage' : '1.2.840.10008.5.1.4.1.1.77.1.4',
    'VideoPhotographicImageStorage' : '1.2.840.10008.5.1.4.1.1.77.1.4.1',
    'OphthalmicPhotography8BitImageStorage' : '1.2.840.10008.5.1.4.1.1.77.1.5.1',
    'OphthalmicPhotography16BitImageStorage' : '1.2.840.10008.5.1.4.1.1.77.1.5.2',
    'StereometricRelationshipStorage' : '1.2.840.10008.5.1.4.1.1.77.1.5.3',
    'OpthalmicTomographyImageStorage' : '1.2.840.10008.5.1.4.1.1.77.1.5.4',
    'WideFieldOpthalmicPhotographyStereographicProjectionImageStorage' : '1.2.840.10008.5.1.4.1.1.77.1.5.5',
    'WideFieldOpthalmicPhotography3DCoordinatesImageStorage' : '1.2.840.10008.5.1.4.1.1.77.1.5.6',
    'VLWholeSlideMicroscopyImageStorage' : '1.2.840.10008.5.1.4.1.1.77.1.6',
    'LensometryMeasurementsStorage' : '1.2.840.10008.5.1.4.1.1.78.1',
    'AutorefractionMeasurementsStorage' : '1.2.840.10008.5.1.4.1.1.78.2',
    'KeratometryMeasurementsStorage' : '1.2.840.10008.5.1.4.1.1.78.3',
    'SubjectiveRefractionMeasurementsStorage' : '1.2.840.10008.5.1.4.1.1.78.4',
    'VisualAcuityMeasurementsStorage' : '1.2.840.10008.5.1.4.1.1.78.5',
    'SpectaclePrescriptionReportStorage' : '1.2.840.10008.5.1.4.1.1.78.6',
    'OpthalmicAxialMeasurementsStorage' : '1.2.840.10008.5.1.4.1.1.78.7',
    'IntraocularLensCalculationsStorage' : '1.2.840.10008.5.1.4.1.1.78.8',
    'MacularGridThicknessAndVolumeReport' : '1.2.840.10008.5.1.4.1.1.79.1',
    'OpthalmicVisualFieldStaticPerimetryMeasurementsStorag' : '1.2.840.10008.5.1.4.1.1.80.1',
    'OpthalmicThicknessMapStorage' : '1.2.840.10008.5.1.4.1.1.81.1',
    'CornealTopographyMapStorage' : '1.2.840.10008.5.1.4.1.1.82.1',
    'BasicTextSRStorage' : '1.2.840.10008.5.1.4.1.1.88.11',
    'EnhancedSRStorage' : '1.2.840.10008.5.1.4.1.1.88.22',
    'ComprehensiveSRStorage' : '1.2.840.10008.5.1.4.1.1.88.33',
    'Comprehenseice3DSRStorage' : '1.2.840.10008.5.1.4.1.1.88.34',
    'ExtensibleSRStorage' : '1.2.840.10008.5.1.4.1.1.88.35',
    'ProcedureSRStorage' : '1.2.840.10008.5.1.4.1.1.88.40',
    'MammographyCADSRStorage' : '1.2.840.10008.5.1.4.1.1.88.50',
    'KeyObjectSelectionStorage' : '1.2.840.10008.5.1.4.1.1.88.59',
    'ChestCADSRStorage' : '1.2.840.10008.5.1.4.1.1.88.65',
    'XRayRadiationDoseSRStorage' : '1.2.840.10008.5.1.4.1.1.88.67',
    'RadiopharmaceuticalRadiationDoseSRStorage' : '1.2.840.10008.5.1.4.1.1.88.68',
    'ColonCADSRStorage' : '1.2.840.10008.5.1.4.1.1.88.69',
    'ImplantationPlanSRDocumentStorage' : '1.2.840.10008.5.1.4.1.1.88.70',
    'EncapsulatedPDFStorage' : '1.2.840.10008.5.1.4.1.1.104.1',
    'EncapsulatedCDAStorage' : '1.2.840.10008.5.1.4.1.1.104.2',
    'PositronEmissionTomographyImageStorage' : '1.2.840.10008.5.1.4.1.1.128',
    'EnhancedPETImageStorage' : '1.2.840.10008.5.1.4.1.1.130',
    'LegacyConvertedEnhancedPETImageStorage' : '1.2.840.10008.5.1.4.1.1.128.1',
    'BasicStructuredDisplayStorage' : '1.2.840.10008.5.1.4.1.1.131',
    'RTImageStorage' : '1.2.840.10008.5.1.4.1.1.481.1',
    'RTDoseStorage' : '1.2.840.10008.5.1.4.1.1.481.2',
    'RTStructureSetStorage' : '1.2.840.10008.5.1.4.1.1.481.3',
    'RTBeamsTreatmentRecordStorage' : '1.2.840.10008.5.1.4.1.1.481.4',
    'RTPlanStorage' : '1.2.840.10008.5.1.4.1.1.481.5',
    'RTBrachyTreatmentRecordStorage' : '1.2.840.10008.5.1.4.1.1.481.6',
    'RTTreatmentSummaryRecordStorage' : '1.2.840.10008.5.1.4.1.1.481.7',
    'RTIonPlanStorage' : '1.2.840.10008.5.1.4.1.1.481.8',
    'RTIonBeamsTreatmentRecordStorage' : '1.2.840.10008.5.1.4.1.1.481.9',
    'RTBeamsDeliveryInstructionStorage' : '1.2.840.10008.5.1.4.34.7',
    'GenericImplantTemplateStorage' : '1.2.840.10008.5.1.4.43.1',
    'ImplantAssemblyTemplateStorage' : '1.2.840.10008.5.1.4.44.1',
    'ImplantTemplateGroupStorage' : '1.2.840.10008.5.1.4.45.1'
}

_QR_FIND_CLASSES = {
    'PatientRootQueryRetrieveInformationModelFind' : '1.2.840.10008.5.1.4.1.2.1.1',
    'StudyRootQueryRetrieveInformationModelFind' : '1.2.840.10008.5.1.4.1.2.2.1',
    'PatientStudyOnlyQueryRetrieveInformationModelFind' : '1.2.840.10008.5.1.4.1.2.3.1',
    'ModalityWorklistInformationFind' : '1.2.840.10008.5.1.4.31'
}

_QR_MOVE_CLASSES = {
    'PatientRootQueryRetrieveInformationModelMove' : '1.2.840.10008.5.1.4.1.2.1.2',
    'StudyRootQueryRetrieveInformationModelMove' : '1.2.840.10008.5.1.4.1.2.2.2',
    'PatientStudyOnlyQueryRetrieveInformationModelMove' : '1.2.840.10008.5.1.4.1.2.3.2'
}

_QR_GET_CLASSES = {
    'PatientRootQueryRetrieveInformationModelGet' : '1.2.840.10008.5.1.4.1.2.1.3',
    'StudyRootQueryRetrieveInformationModelGet' : '1.2.840.10008.5.1.4.1.2.2.3',
    'PatientStudyOnlyQueryRetrieveInformationModelGet' : '1.2.840.10008.5.1.4.1.2.3.3'
}

_BASIC_WORKLIST_CLASSES = {
    'ModalityWorklistInformationFind' : '1.2.840.10008.5.1.4.31'
}

# pylint: enable=line-too-long
_generate_sop_classes(_VERIFICATION_CLASSES)
_generate_sop_classes(_STORAGE_CLASSES)
_generate_sop_classes(_QR_FIND_CLASSES)
_generate_sop_classes(_QR_MOVE_CLASSES)
_generate_sop_classes(_QR_GET_CLASSES)

# Deprecated, will be removed in v1.0 to be replaced with ENUM?
# pylint: enable=line-too-long
_generate_service_sop_classes(_VERIFICATION_CLASSES, VerificationServiceClass)
_generate_service_sop_classes(_STORAGE_CLASSES, StorageServiceClass)
_generate_service_sop_classes(_QR_FIND_CLASSES, QueryRetrieveFindServiceClass)
_generate_service_sop_classes(_QR_MOVE_CLASSES, QueryRetrieveMoveServiceClass)
_generate_service_sop_classes(_QR_GET_CLASSES, QueryRetrieveGetServiceClass)

# pylint: disable=no-member
# Deprecated, will be removed in v1.0
STORAGE_CLASS_LIST = StorageServiceClass.__subclasses__()
QR_FIND_CLASS_LIST = QueryRetrieveFindServiceClass.__subclasses__()
QR_MOVE_CLASS_LIST = QueryRetrieveMoveServiceClass.__subclasses__()
QR_GET_CLASS_LIST = QueryRetrieveGetServiceClass.__subclasses__()
# pylint: enable=no-member

# Deprecated, will be removed in v1.0
QR_CLASS_LIST = []
for class_list in [QR_FIND_CLASS_LIST, QR_MOVE_CLASS_LIST, QR_GET_CLASS_LIST]:
    QR_CLASS_LIST.extend(class_list)

# New approach - service class orientated
_SUPPORTED_VERIFICATION_SOP_CLASSES = {
    '1.2.840.10008.1.1' : VerificationServiceClass,
}
_SUPPORTED_STORAGE_SOP_CLASSES = {
    '1.2.840.10008.5.1.4.1.1.1' : StorageServiceClass,
}
_SUPPORTED_QR_SOP_CLASSES = {
    '1.2.840.10008.5.1.4.1.2.1.1' : QueryRetrieveFindServiceClass,
    '1.2.840.10008.5.1.4.1.2.2.1' : QueryRetrieveFindServiceClass,
    '1.2.840.10008.5.1.4.1.2.3.1' : QueryRetrieveFindServiceClass,
    '1.2.840.10008.5.1.4.1.2.1.2' : QueryRetrieveMoveServiceClass,
    '1.2.840.10008.5.1.4.1.2.2.2' : QueryRetrieveMoveServiceClass,
    '1.2.840.10008.5.1.4.1.2.3.2' : QueryRetrieveMoveServiceClass,
    '1.2.840.10008.5.1.4.1.2.1.3' : QueryRetrieveGetServiceClass,
    '1.2.840.10008.5.1.4.1.2.2.3' : QueryRetrieveGetServiceClass,
    '1.2.840.10008.5.1.4.1.2.3.3' : QueryRetrieveGetServiceClass,
}
_SUPPORTED_BASIC_WORKLIST_SOP_CLASSES = {
    '1.2.840.10008.5.1.4.31' : QueryRetrieveFindServiceClass,
}

SUPPORTED_SOP_CLASSES = {}
SUPPORTED_SOP_CLASSES.update(_SUPPORTED_VERIFICATION_SOP_CLASSES)
SUPPORTED_SOP_CLASSES.update(_SUPPORTED_STORAGE_SOP_CLASSES)
SUPPORTED_SOP_CLASSES.update(_SUPPORTED_QR_SOP_CLASSES)
SUPPORTED_SOP_CLASSES.update(_SUPPORTED_BASIC_WORKLIST_SOP_CLASSES)


def uid_to_service_class(uid):
    """Return the ServiceClass object corresponding to `uid`.

    Parameters
    ----------
    uid : pydicom.uid.UID
        The SOP Class UID to find the corresponding Service Class.

    Returns
    -------
    sop_class.ServiceClass
        The Service Class corresponding to the SOP Class UID.

    Raises
    ------
    NotImplementedError
        If the Service Class corresponding to the SOP Class `uid` hasn't been
        implemented.
    """
    if uid not in SUPPORTED_SOP_CLASSES:
        raise NotImplementedError(
            "The SOP Class for UID '{}' has not been implemented".format(uid)
        )

    return SUPPORTED_SOP_CLASSES[uid]


def uid_to_sop_class(uid):
    """Given a `uid` return the corresponding SOP Class.

    Parameters
    ----------
    uid : pydicom.uid.UID

    Returns
    -------
    subclass of pynetdicom3.sopclass.ServiceClass
        The SOP class corresponding to `uid`

    Raises
    ------
    NotImplementedError
        The the SOP class for the given UID has not been implemented.
    """
    # Get a list of all the class members of the current module
    members = inspect.getmembers(sys.modules[__name__],
                                 lambda member: inspect.isclass(member) and \
                                                member.__module__ == __name__)

    for obj in members:
        if hasattr(obj[1], 'UID') and obj[1].UID == uid:
            return obj[1]

    raise NotImplementedError("The SOP Class for UID '{}' has not been " \
                              "implemented".format(uid))
