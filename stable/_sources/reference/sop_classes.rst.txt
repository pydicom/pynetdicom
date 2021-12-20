.. _api_sopclasses:

.. py:module:: pynetdicom.sop_class

SOP Classes (:mod:`pynetdicom.sop_class`)
==============================================

.. currentmodule:: pynetdicom.sop_class

SOP Class Utilities
-------------------

.. autosummary::
   :toctree: generated/

   SOPClass
   uid_to_sop_class
   uid_to_service_class

SOP Classes
-----------

Application Event
.................

.. autosummary::
   :toctree: generated/

   ProceduralEventLoggingSOPClass
   SubstanceAdministrationLoggingSOPClass

Basic Worklist
..............

.. autosummary::
   :toctree: generated/

   ModalityWorklistInformationFind

Color Palette
.............

.. autosummary::
   :toctree: generated/

   ColorPaletteInformationModelFind
   ColorPaletteInformationModelGet
   ColorPaletteInformationModelMove

Defined Procedure
.................

.. autosummary::
   :toctree: generated/

   DefinedProcedureProtocolInformationModelFind
   DefinedProcedureProtocolInformationModelGet
   DefinedProcedureProtocolInformationModelMove

Display System
..............

.. autosummary::
   :toctree: generated/

   DisplaySystemSOPClass

Hanging Protocol
................

.. autosummary::
   :toctree: generated/

   HangingProtocolInformationModelFind
   HangingProtocolInformationModelGet
   HangingProtocolInformationModelMove

Implant Template
................

.. autosummary::
   :toctree: generated/

   GenericImplantTemplateInformationModelFind
   GenericImplantTemplateInformationModelGet
   GenericImplantTemplateInformationModelMove
   ImplantAssemblyTemplateInformationModelFind
   ImplantAssemblyTemplateInformationModelGet
   ImplantAssemblyTemplateInformationModelMove
   ImplantTemplateGroupInformationModelFind
   ImplantTemplateGroupInformationModelGet
   ImplantTemplateGroupInformationModelMove

Instance Availability
.....................

.. autosummary::
   :toctree: generated/

   InstanceAvailabilityNotificationSOPClass

Media Creation
..............

.. autosummary::
   :toctree: generated/

   MediaCreationManagementSOPClass

Media Storage
.............

.. autosummary::
   :toctree: generated/

   MediaStorageDirectoryStorage

Non-patient Object
..................

.. autosummary::
   :toctree: generated/

   ColorPaletteStorage
   CTDefinedProcedureProtocolStorage
   GenericImplantTemplateStorage
   HangingProtocolStorage
   ImplantAssemblyTemplateStorage
   ImplantTemplateGroupStorage
   ProtocolApprovalStorage

Print Management
................

.. autosummary::
   :toctree: generated/

   BasicFilmSessionSOPClass
   BasicFilmBoxSOPClass
   BasicGrayscaleImageBoxSOPClass
   BasicColorImageBoxSOPClass
   PrintJobSOPClass
   BasicAnnotationBoxSOPClass
   PrinterSOPClass
   PrinterConfigurationRetrievalSOPClass
   PresentationLUTSOPClass
   BasicGrayscalePrintManagementMetaSOPClass
   BasicColorPrintManagementMetaSOPClass

Procedure Step
..............

.. autosummary::
   :toctree: generated/

   ModalityPerformedProcedureStepNotificationSOPClass
   ModalityPerformedProcedureStepRetrieveSOPClass
   ModalityPerformedProcedureStepSOPClass

Protocol Approval
.................

.. autosummary::
   :toctree: generated/

   ProtocolApprovalInformationModelFind
   ProtocolApprovalInformationModelGet
   ProtocolApprovalInformationModelMove

Query/Retrieve
..............

.. autosummary::
   :toctree: generated/

   CompositeInstanceRetrieveWithoutBulkDataGet
   CompositeInstanceRootRetrieveGet
   CompositeInstanceRootRetrieveMove
   PatientRootQueryRetrieveInformationModelFind
   PatientRootQueryRetrieveInformationModelGet
   PatientRootQueryRetrieveInformationModelMove
   PatientStudyOnlyQueryRetrieveInformationModelFind
   PatientStudyOnlyQueryRetrieveInformationModelGet
   PatientStudyOnlyQueryRetrieveInformationModelMove
   StudyRootQueryRetrieveInformationModelFind
   StudyRootQueryRetrieveInformationModelGet
   StudyRootQueryRetrieveInformationModelMove

Relevant Patient
................

.. autosummary::
   :toctree: generated/

   BreastImagingRelevantPatientInformationQuery
   CardiacRelevantPatientInformationQuery
   GeneralRelevantPatientInformationQuery

RT Machine Verification
.......................

.. autosummary::
   :toctree: generated/

   RTConventionalMachineVerification
   RTIonMachineVerification

Storage
.......

.. autosummary::
   :toctree: generated/

   AcquisitionContextSRStorage
   AdvancedBlendingPresentationStateStorage
   AmbulatoryECGWaveformStorage
   ArterialPulseWaveformStorage
   AutorefractionMeasurementsStorage
   BasicStructuredDisplayStorage
   BasicTextSRStorage
   BasicVoiceAudioWaveformStorage
   BlendingSoftcopyPresentationStateStorage
   BreastProjectionXRayImagePresentationStorage
   BreastProjectionXRayImageProcessingStorage
   BreastTomosynthesisImageStorage
   CardiacElectrophysiologyWaveformStorage
   ChestCADSRStorage
   ColonCADSRStorage
   ColorSoftcopyPresentationStateStorage
   CompositingPlanarMPRVolumetricPresentationStateStorage
   ComprehensiveSRStorage
   Comprehensive3DSRStorage
   ComputedRadiographyImageStorage
   ContentAssessmentResultsStorage
   CornealTopographyMapStorage
   CTImageStorage
   CTPerformedProcedureProtocolStorage
   DeformableSpatialRegistrationStorage
   DigitalIntraOralXRayImagePresentationStorage
   DigitalIntraOralXRayImageProcessingStorage
   DigitalMammographyXRayImagePresentationStorage
   DigitalMammographyXRayImageProcessingStorage
   DigitalXRayImagePresentationStorage
   DigitalXRayImageProcessingStorage
   EncapsulatedCDAStorage
   EncapsulatedPDFStorage
   EncapsulatedSTLStorage
   EnhancedCTImageStorage
   EnhancedMRColorImageStorage
   EnhancedMRImageStorage
   EnhancedPETImageStorage
   EnhancedSRStorage
   EnhancedUSVolumeStorage
   EnhancedXAImageStorage
   EnhancedXRFImageStorage
   ExtensibleSRStorage
   GeneralAudioWaveformStorage
   GeneralECGWaveformStorage
   GrayscalePlanarMPRVolumetricPresentationStateStorage
   GrayscaleSoftcopyPresentationStateStorage
   HemodynamicWaveformStorage
   ImplantationPlanSRStorage
   IntraocularLensCalculationsStorage
   IntravascularOpticalCoherenceTomographyImagePresentationStorage
   IntravascularOpticalCoherenceTomographyImageProcessingStorage
   KeratometryMeasurementsStorage
   KeyObjectSelectionStorage
   LegacyConvertedEnhancedCTImageStorage
   LegacyConvertedEnhancedMRImageStorage
   LegacyConvertedEnhancedPETImageStorage
   LensometryMeasurementsStorage
   MacularGridThicknessAndVolumeReport
   MammographyCADSRStorage
   MRImageStorage
   MRSpectroscopyStorage
   MultiframeGrayscaleByteSecondaryCaptureImageStorage
   MultiframeGrayscaleWordSecondaryCaptureImageStorage
   MultiframeSingleBitSecondaryCaptureImageStorage
   MultiframeTrueColorSecondaryCaptureImageStorage
   MultipleVolumeRenderingVolumetricPresentationStateStorage
   NuclearMedicineImageStorage
   OphthalmicAxialMeasurementsStorage
   OphthlamicOpticalCoherenceTomographyBScanVolumeAnalysisStorage
   OphthalmicOpticalCoherenceTomographyEnFaceImageStorage
   OphthalmicPhotography16BitImageStorage
   OphthalmicPhotography8BitImageStorage
   OphthalmicThicknessMapStorage
   OphthalmicTomographyImageStorage
   OphthalmicVisualFieldStaticPerimetryMeasurementsStorage
   ParametricMapStorage
   PatientRadiationDoseSRStorage
   PositronEmissionTomographyImageStorage
   ProcedureSRStorage
   PseudocolorSoftcopyPresentationStageStorage
   RadiopharmaceuticalRadiationDoseSRStorage
   RawDataStorage
   RealWorldValueMappingStorage
   RespiratoryWaveformStorage
   RTBeamsDeliveryInstructionStorage
   RTBeamsTreatmentRecordStorage
   RTBrachyApplicationSetupDeliveryInstructionsStorage
   RTBrachyTreatmentRecordStorage
   RTDoseStorage
   RTImageStorage
   RTIonBeamsTreatmentRecordStorage
   RTIonPlanStorage
   RTPlanStorage
   RTStructureSetStorage
   RTTreatmentSummaryRecordStorage
   SecondaryCaptureImageStorage
   SegmentationStorage
   SegmentedVolumeRenderingVolumetricPresentationStateStorage
   SimplifiedAdultEchoSRStorage
   SpatialFiducialsStorage
   SpatialRegistrationStorage
   SpectaclePrescriptionReportStorage
   StereometricRelationshipStorage
   SubjectiveRefractionMeasurementsStorage
   SurfaceScanMeshStorage
   SurfaceScanPointCloudStorage
   SurfaceSegmentationStorage
   TractographyResultsStorage
   TwelveLeadECGWaveformStorage
   UltrasoundImageStorage
   UltrasoundMultiframeImageStorage
   VideoEndoscopicImageStorage
   VideoMicroscopicImageStorage
   VideoPhotographicImageStorage
   VisualAcuityMeasurementsStorage
   VLEndoscopicImageStorage
   VLMicroscopicImageStorage
   VLPhotographicImageStorage
   VLSlideCoordinatesMicroscopicImageStorage
   VLWholeSlideMicroscopyImageStorage
   VolumeRenderingVolumetricPresentationStateStorage
   WideFieldOphthalmicPhotography3DCoordinatesImageStorage
   WideFieldOphthalmicPhotographyStereographicProjectionImageStorage
   XAXRFGrayscaleSoftcopyPresentationStateStorage
   XRay3DAngiographicImageStorage
   XRay3DCraniofacialImageStorage
   XRayAngiographicImageStorage
   XRayRadiationDoseSRStorage
   XRayRadiofluoroscopicImageStorage

Storage Commitment
..................

.. autosummary::
   :toctree: generated/

   StorageCommitmentPushModelSOPClass

Substance Availability
......................

.. autosummary::
   :toctree: generated/

   ProductCharacteristicsQueryInformationModelFind
   SubstanceApprovalQueryInformationModelFind

Unified Procedure Step
......................

.. autosummary::
   :toctree: generated/

   UnifiedProcedureStepEventSOPClass
   UnifiedProcedureStepPullSOPClass
   UnifiedProcedureStepPushSOPClass
   UnifiedProcedureStepQuerySOPClass
   UnifiedProcedureStepWatchSOPClass

Verification
............

.. autosummary::
   :toctree: generated/

   VerificationSOPClass


Well-known SOP Instances
------------------------

.. autosummary::
   :toctree: generated/

   DisplaySystemSOPInstance
   PrinterConfigurationRetrievalSOPInstance
   PrinterSOPInstance
   ProceduralEventLoggingSOPInstance
   StorageCommitmentPushModelSOPInstance
   SubstanceAdministrationLoggingSOPInstance
   UPSFilteredGlobalSubscriptionSOPInstance
   UPSGlobalSubscriptionSOPInstance
