.. _api_sopclasses:

.. py:module:: pynetdicom.sop_class

SOP Classes (:mod:`pynetdicom.sop_class`)
==============================================

.. currentmodule:: pynetdicom.sop_class

SOP Class Utilities
-------------------

.. autosummary::
   :toctree: generated/

   register_uid
   SOPClass
   uid_to_sop_class
   uid_to_service_class

SOP Classes
-----------

Application Event
.................

.. autosummary::
   :toctree: generated/

   ProceduralEventLogging
   SubstanceAdministrationLogging

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

   DisplaySystem

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

   InstanceAvailabilityNotification

Inventory Query/Retrieve
........................

.. autosummary::
   :toctree: generated/

   InventoryFind
   InventoryGet
   InventoryMove

Media Creation
..............

.. autosummary::
   :toctree: generated/

   MediaCreationManagement

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
   InventoryStorage
   ProtocolApprovalStorage
   XADefinedProcedureProtocolStorage

Print Management
................

.. autosummary::
   :toctree: generated/

   BasicFilmSession
   BasicFilmBox
   BasicGrayscaleImageBox
   BasicColorImageBox
   PrintJob
   BasicAnnotationBox
   Printer
   PrinterConfigurationRetrieval
   PresentationLUT
   BasicGrayscalePrintManagementMeta
   BasicColorPrintManagementMeta

Procedure Step
..............

.. autosummary::
   :toctree: generated/

   ModalityPerformedProcedureStepNotification
   ModalityPerformedProcedureStepRetrieve
   ModalityPerformedProcedureStep

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
   RepositoryQuery

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
   BodyPositionWaveformStorage
   BlendingSoftcopyPresentationStateStorage
   BreastProjectionXRayImageStorageForPresentation
   BreastProjectionXRayImageStorageForProcessing
   BreastTomosynthesisImageStorage
   CardiacElectrophysiologyWaveformStorage
   CArmPhotonElectronRadiationRecordStorage
   CArmPhotonElectronRadiationStorage
   ChestCADSRStorage
   ColonCADSRStorage
   ColorSoftcopyPresentationStateStorage
   CompositingPlanarMPRVolumetricPresentationStateStorage
   ComprehensiveSRStorage
   Comprehensive3DSRStorage
   ComputedRadiographyImageStorage
   ConfocalMicroscopyImageStorage
   ConfocalMicroscopyTiledPyramidalImageStorage
   ContentAssessmentResultsStorage
   CornealTopographyMapStorage
   CTImageStorage
   CTPerformedProcedureProtocolStorage
   DeformableSpatialRegistrationStorage
   DermoscopicPhotographyImageStorage
   DigitalIntraOralXRayImageStorageForPresentation
   DigitalIntraOralXRayImageStorageForProcessing
   DigitalMammographyXRayImageStorageForPresentation
   DigitalMammographyXRayImageStorageForProcessing
   DigitalXRayImageStorageForPresentation
   DigitalXRayImageStorageForProcessing
   ElectromyogramWaveformStorage
   ElectrooculogramWaveformStorage
   EncapsulatedCDAStorage
   EncapsulatedMTLStorage
   EncapsulatedOBJStorage
   EncapsulatedPDFStorage
   EncapsulatedSTLStorage
   EnhancedContinuousRTImageStorage
   EnhancedCTImageStorage
   EnhancedMRColorImageStorage
   EnhancedMRImageStorage
   EnhancedPETImageStorage
   EnhancedRTImageStorage
   EnhancedSRStorage
   EnhancedUSVolumeStorage
   EnhancedXAImageStorage
   EnhancedXRayRadiationDoseSRStorage
   EnhancedXRFImageStorage
   ExtensibleSRStorage
   GeneralAudioWaveformStorage
   GeneralECGWaveformStorage
   General32bitECGWaveformStorage
   GrayscalePlanarMPRVolumetricPresentationStateStorage
   GrayscaleSoftcopyPresentationStateStorage
   HeightMapSegmentationStorage
   HemodynamicWaveformStorage
   ImplantationPlanSRStorage
   IntraocularLensCalculationsStorage
   IntravascularOpticalCoherenceTomographyImageStorageForPresentation
   IntravascularOpticalCoherenceTomographyImageStorageForProcessing
   KeratometryMeasurementsStorage
   KeyObjectSelectionDocumentStorage
   LabelMapSegmentationStorage
   LegacyConvertedEnhancedCTImageStorage
   LegacyConvertedEnhancedMRImageStorage
   LegacyConvertedEnhancedPETImageStorage
   LensometryMeasurementsStorage
   MacularGridThicknessAndVolumeReportStorage
   MammographyCADSRStorage
   MicroscopyBulkSimpleAnnotationsStorage
   MRImageStorage
   MRSpectroscopyStorage
   MultichannelRespiratoryWaveformStorage
   MultiFrameGrayscaleByteSecondaryCaptureImageStorage
   MultiFrameGrayscaleWordSecondaryCaptureImageStorage
   MultiFrameSingleBitSecondaryCaptureImageStorage
   MultiFrameTrueColorSecondaryCaptureImageStorage
   MultipleVolumeRenderingVolumetricPresentationStateStorage
   NuclearMedicineImageStorage
   OphthalmicAxialMeasurementsStorage
   OphthlamicOpticalCoherenceTomographyBscanVolumeAnalysisStorage
   OphthalmicOpticalCoherenceTomographyEnFaceImageStorage
   OphthalmicPhotography16BitImageStorage
   OphthalmicPhotography8BitImageStorage
   OphthalmicThicknessMapStorage
   OphthalmicTomographyImageStorage
   OphthalmicVisualFieldStaticPerimetryMeasurementsStorage
   ParametricMapStorage
   PatientRadiationDoseSRStorage
   PerformedImagingAgentAdministrationSRStorage
   PhotoacousticImageStorage
   PlannedImagingAgentAdministrationSRStorage
   PositronEmissionTomographyImageStorage
   ProcedureLogStorage
   PseudoColorSoftcopyPresentationStageStorage
   RadiopharmaceuticalRadiationDoseSRStorage
   RawDataStorage
   RealWorldValueMappingStorage
   RespiratoryWaveformStorage
   RoboticArmRadiationRecordStorage
   RoboticArmRadiationStorage
   RoutineScalpElectroencephalogramWaveformStorage
   RTBeamsDeliveryInstructionStorage
   RTBeamsTreatmentRecordStorage
   RTBrachyApplicationSetupDeliveryInstructionsStorage
   RTBrachyTreatmentRecordStorage
   RTDoseStorage
   RTImageStorage
   RTIonBeamsTreatmentRecordStorage
   RTIonPlanStorage
   RTPatientPositionAcquisitionInstructionStorage
   RTPhysicianIntentStorage
   RTPlanStorage
   RTRadiationRecordSetStorage
   RTRadiationSalvageRecordStorage
   RTRadiationSetDeliveryInstructionStorage
   RTRadiationSetStorage
   RTSegmentAnnotationStorage
   RTStructureSetStorage
   RTTreatmentPreparationStorage
   RTTreatmentSummaryRecordStorage
   SecondaryCaptureImageStorage
   SegmentationStorage
   SegmentedVolumeRenderingVolumetricPresentationStateStorage
   SimplifiedAdultEchoSRStorage
   SleepElectroencephalogramWaveformStorage
   SpatialFiducialsStorage
   SpatialRegistrationStorage
   SpectaclePrescriptionReportStorage
   StereometricRelationshipStorage
   SubjectiveRefractionMeasurementsStorage
   SurfaceScanMeshStorage
   SurfaceScanPointCloudStorage
   SurfaceSegmentationStorage
   TomotherapeuticRadiationRecordStorage
   TomotherapeuticRadiationStorage
   TractographyResultsStorage
   TwelveLeadECGWaveformStorage
   UltrasoundImageStorage
   UltrasoundMultiFrameImageStorage
   VariableModalityLUTSoftcopyPresentationStageStorage
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
   WaveformAcquisitionPresentationStateStorage
   WaveformAnnotationSRStorage
   WaveformPresentationStateStorage
   WideFieldOphthalmicPhotography3DCoordinatesImageStorage
   WideFieldOphthalmicPhotographyStereographicProjectionImageStorage
   XAPerformedProcedureProtocolStorage
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

   StorageCommitmentPushModel

Storage Management
..................

.. autosummary::
   :toctree: generated/

   InventoryCreation

Substance Availability
......................

.. autosummary::
   :toctree: generated/

   ProductCharacteristicsQuery
   SubstanceApprovalQuery

Unified Procedure Step
......................

.. autosummary::
   :toctree: generated/

   UnifiedProcedureStepEvent
   UnifiedProcedureStepPull
   UnifiedProcedureStepPush
   UnifiedProcedureStepQuery
   UnifiedProcedureStepWatch

Verification
............

.. autosummary::
   :toctree: generated/

   Verification


Well-known SOP Instances
------------------------

.. autosummary::
   :toctree: generated/

   DisplaySystemInstance
   PrinterConfigurationRetrievalInstance
   PrinterInstance
   ProceduralEventLoggingInstance
   StorageCommitmentPushModelInstance
   StorageManagementInstance
   SubstanceAdministrationLoggingInstance
   UPSFilteredGlobalSubscriptionInstance
   UPSGlobalSubscriptionInstance
