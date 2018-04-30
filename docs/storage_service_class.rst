Storage Service Class
=====================
The Storage Service Class defines a service that facilitates the simple
transfer of DICOM information Instances. It allows one DICOM Application Entity
to send images, waveforms, reports, etc., to another using the C-STORE DIMSE-C
service.

Supported SOP Classes
---------------------

* AmbulatoryECGWaveformStorage - 1.2.840.10008.5.1.4.1.1.9.1.3
* ArterialPulseWaveformStorage - 1.2.840.10008.5.1.4.1.1.9.5.1
* AutorefractionMeasurementsStorage - 1.2.840.10008.5.1.4.1.1.78.2
* BasicStructuredDisplayStorage - 1.2.840.10008.5.1.4.1.1.131
* BasicTextSRStorage - 1.2.840.10008.5.1.4.1.1.88.11
* BasicVoiceAudioWaveformStorage - 1.2.840.10008.5.1.4.1.1.9.4.1
* BlendingSoftcopyPresentationStateStorage - 1.2.840.10008.5.1.4.1.1.11.4
* BreastProjectionXRayImagePresentationStorage - 1.2.840.10008.5.1.4.1.1.13.1.4
* BreastProjectionXRayImageProcessingStorage - 1.2.840.10008.5.1.4.1.1.13.1.5
* BreastTomosynthesisImageStorage - 1.2.840.10008.5.1.4.1.1.13.1.3
* CardiacElectrophysiologyWaveformStorage - 1.2.840.10008.5.1.4.1.1.9.3.1
* ChestCADSRStorage - 1.2.840.10008.5.1.4.1.1.88.65
* ColonCADSRStorage - 1.2.840.10008.5.1.4.1.1.88.69
* ColorSoftcopyPresentationStateStorage - 1.2.840.10008.5.1.4.1.1.11.2
* Comprehensive3DSRStorage - 1.2.840.10008.5.1.4.1.1.88.34
* ComprehensiveSRStorage - 1.2.840.10008.5.1.4.1.1.88.33
* ComputedRadiographyImageStorage - 1.2.840.10008.5.1.4.1.1.1
* CornealTopographyMapStorage - 1.2.840.10008.5.1.4.1.1.82.1
* CTImageStorage - 1.2.840.10008.5.1.4.1.1.2
* DeformableSpatialRegistrationStorage - 1.2.840.10008.5.1.4.1.1.66.3
* DigitalIntraOralXRayImagePresentationStorage - 1.2.840.10008.5.1.4.1.1.1.3
* DigitalIntraOralXRayImageProcessingStorage - 1.2.840.10008.5.1.1.4.1.1.3.1
* DigitalMammographyXRayImagePresentationStorage - 1.2.840.10008.5.1.4.1.1.1.2
* DigitalMammographyXRayImageProcessingStorage - 1.2.840.10008.5.1.4.1.1.1.2.1
* DigitalXRayImagePresentationStorage - 1.2.840.10008.5.1.4.1.1.1.1
* DigitalXRayImageProcessingStorage - 1.2.840.10008.5.1.4.1.1.1.1.1.1
* EncapsulatedCDAStorage - 1.2.840.10008.5.1.4.1.1.104.2
* EncapsulatedPDFStorage - 1.2.840.10008.5.1.4.1.1.104.1
* EnhancedCTImageStorage - 1.2.840.10008.5.1.4.1.1.2.1
* EnhancedMRColorImageStorage - 1.2.840.10008.5.1.4.1.1.4.3
* EnhancedMRImageStorage - 1.2.840.10008.5.1.4.1.1.4.1
* EnhancedPETImageStorage - 1.2.840.10008.5.1.4.1.1.130
* EnhancedSRStorage - 1.2.840.10008.5.1.4.1.1.88.22
* EnhancedUSVolumeStorage - 1.2.840.10008.5.1.4.1.1.6.2
* EnhancedXAImageStorage - 1.2.840.10008.5.1.4.1.1.12.1.1
* EnhancedXRFImageStorage - 1.2.840.10008.5.1.4.1.1.12.2.1
* ExtensibleSRStorage - 1.2.840.10008.5.1.4.1.1.88.35
* GeneralAudioWaveformStorage - 1.2.840.10008.5.1.4.1.1.9.4.2
* GeneralECGWaveformStorage - 1.2.840.10008.5.1.4.1.1.9.1.2
* GenericImplantTemplateStorage - 1.2.840.10008.5.1.4.43.1
* GrayscaleSoftcopyPresentationStateStorage - 1.2.840.10008.5.1.4.1.1.11.1
* HemodynamicWaveformStorage - 1.2.840.10008.5.1.4.1.1.9.2.1
* ImplantAssemblyTemplateStorage - 1.2.840.10008.5.1.4.44.1
* ImplantTemplateGroupStorage - 1.2.840.10008.5.1.4.45.1
* ImplantationPlanSRDocumentStorage - 1.2.840.10008.5.1.4.1.1.88.70
* IntraocularLensCalculationsStorage - 1.2.840.10008.5.1.4.1.1.78.8
* IntravascularOpticalCoherenceTomographyImagePresentationStorage - 1.2.840.10008.5.1.4.1.1.14.1
* IntravascularOpticalCoherenceTomographyImageProcessingStorage - 1.2.840.10008.5.1.4.1.1.14.2
* KeratometryMeasurementsStorage - 1.2.840.10008.5.1.4.1.1.78.3
* KeyObjectSelectionStorage - 1.2.840.10008.5.1.4.1.1.88.59
* LegacyConvertedEnhancedCTImageStorage - 1.2.840.10008.5.1.4.1.1.2.2
* LegacyConvertedEnhancedMRImageStorage - 1.2.840.10008.5.1.4.1.1.4.4
* LegacyConvertedEnhancedPETImageStorage - 1.2.840.10008.5.1.4.1.1.128.1
* LensometryMeasurementsStorage - 1.2.840.10008.5.1.4.1.1.78.1
* MacularGridThicknessAndVolumeReport - 1.2.840.10008.5.1.4.1.1.79.1
* MammographyCADSRStorage - 1.2.840.10008.5.1.4.1.1.88.50
* MRImageStorage - 1.2.840.10008.5.1.4.1.1.4
* MRSpectroscopyStorage - 1.2.840.10008.5.1.4.1.1.4.2
* MultiframeGrayscaleByteSecondaryCaptureImageStorage - 1.2.840.10008.5.1.4.1.1.7.2
* MultiframeGrayscaleWordSecondaryCaptureImageStorage - 1.2.840.10008.5.1.4.1.1.7.3
* MultiframeSingleBitSecondaryCaptureImageStorage - 1.2.840.10008.5.1.4.1.1.7.1
* MultiframeTrueColorSecondaryCaptureImageStorage - 1.2.840.10008.5.1.4.1.1.7.4
* NuclearMedicineImageStorage - 1.2.840.10008.5.1.4.1.1.20
* OphthalmicAxialMeasurementsStorage - 1.2.840.10008.5.1.4.1.1.78.7
* OphthalmicPhotography16BitImageStorage - 1.2.840.10008.5.1.4.1.1.77.1.5.2
* OphthalmicPhotography8BitImageStorage - 1.2.840.10008.5.1.4.1.1.77.1.5.1
* OphthalmicThicknessMapStorage - 1.2.840.10008.5.1.4.1.1.81.1
* OphthalmicTomographyImageStorage - 1.2.840.10008.5.1.4.1.1.77.1.5.4
* OphthalmicVisualFieldStaticPerimetryMeasurementsStorag - 1.2.840.10008.5.1.4.1.1.80.1
* ParametricMapStorage - 1.2.840.10008.5.1.4.1.1.30
* PositronEmissionTomographyImageStorage - 1.2.840.10008.5.1.4.1.1.128
* ProcedureSRStorage - 1.2.840.10008.5.1.4.1.1.88.40
* PseudocolorSoftcopyPresentationStageStorage - 1.2.840.10008.5.1.4.1.1.11.3
* RadiopharmaceuticalRadiationDoseSRStorage - 1.2.840.10008.5.1.4.1.1.88.68
* RawDataStorage - 1.2.840.10008.5.1.4.1.1.66
* RealWorldValueMappingStorage - 1.2.840.10008.5.1.4.1.1.67
* RespiratoryWaveformStorage - 1.2.840.10008.5.1.4.1.1.9.6.1
* RTBeamsDeliveryInstructionStorage - 1.2.840.10008.5.1.4.34.7
* RTBeamsTreatmentRecordStorage - 1.2.840.10008.5.1.4.1.1.481.4
* RTBrachyTreatmentRecordStorage - 1.2.840.10008.5.1.4.1.1.481.6
* RTDoseStorage - 1.2.840.10008.5.1.4.1.1.481.2
* RTImageStorage - 1.2.840.10008.5.1.4.1.1.481.1
* RTIonPlanStorage - 1.2.840.10008.5.1.4.1.1.481.8
* RTIonBeamsTreatmentRecordStorage - 1.2.840.10008.5.1.4.1.1.481.9
* RTPlanStorage - 1.2.840.10008.5.1.4.1.1.481.5
* RTStructureSetStorage - 1.2.840.10008.5.1.4.1.1.481.3
* RTTreatmentSummaryRecordStorage - 1.2.840.10008.5.1.4.1.1.481.7
* SecondaryCaptureImageStorage - 1.2.840.10008.5.1.4.1.1.7
* SegmentationStorage - 1.2.840.10008.5.1.4.1.1.66.4
* SpatialFiducialsStorage - 1.2.840.10008.5.1.4.1.1.66.2
* SpatialRegistrationStorage - 1.2.840.10008.5.1.4.1.1.66.1
* SpectaclePrescriptionReportStorage - 1.2.840.10008.5.1.4.1.1.78.6
* StereometricRelationshipStorage - 1.2.840.10008.5.1.4.1.1.77.1.5.3
* SubjectiveRefractionMeasurementsStorage - 1.2.840.10008.5.1.4.1.1.78.4
* SurfaceScanMeshStorage - 1.2.840.10008.5.1.4.1.1.68.1
* SurfaceScanPointCloudStorage - 1.2.840.10008.5.1.4.1.1.68.2
* SurfaceSegmentationStorage - 1.2.840.10008.5.1.4.1.1.66.5
* TwelveLeadECGWaveformStorage - 1.2.840.10008.5.1.4.1.1.9.1.1
* UltrasoundImageStorage - 1.2.840.10008.5.1.4.1.1.6.1
* UltrasoundMultiframeImageStorage - 1.2.840.10008.5.1.4.1.1.3.1
* VideoEndoscopicImageStorage - 1.2.840.10008.5.1.4.1.1.77.1.1.1
* VideoMicroscopicImageStorage - 1.2.840.10008.5.1.4.1.1.77.1.2.1
* VideoPhotographicImageStorage - 1.2.840.10008.5.1.4.1.1.77.1.4.1
* VisualAcuityMeasurementsStorage - 1.2.840.10008.5.1.4.1.1.78.5
* VLEndoscopicImageStorage - 1.2.840.10008.5.1.4.1.1.77.1.1
* VLMicroscopicImageStorage - 1.2.840.10008.5.1.4.1.1.77.1.2
* VLPhotographicImageStorage - 1.2.840.10008.5.1.4.1.1.77.1.4
* VLSlideCoordinatesMicroscopicImageStorage - 1.2.840.10008.5.1.4.1.1.77.1.3
* VLWholeSlideMicroscopyImageStorage - 1.2.840.10008.5.1.4.1.1.77.1.6
* WideFieldOpthalmicPhotography3DCoordinatesImageStorage - 1.2.840.10008.5.1.4.1.1.77.1.5.6
* WideFieldOpthalmicPhotographyStereographicProjectionImageStorage - 1.2.840.10008.5.1.4.1.1.77.1.5.5
* XAXRFGrayscaleSoftcopyPresentationStateStorage - 1.2.840.10008.5.1.4.1.1.11.5
* XRay3DAngiographicImageStorage - 1.2.840.10008.5.1.4.1.1.13.1.1
* XRay3DCraniofacialImageStorage - 1.2.840.10008.5.1.4.1.1.13.1.2
* XRayAngiographicImageStorage - 1.2.840.10008.5.1.4.1.1.12.1
* XRayRadiationDoseSRStorage - 1.2.840.10008.5.1.4.1.1.88.67
* XRayRadiofluoroscopicImageStorage - 1.2.840.10008.5.1.4.1.1.12.2

References
----------
DICOM Standard, Part 4, `Annex B <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_B>`_
