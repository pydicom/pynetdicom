.. _api_presentation:

.. py:module:: pynetdicom.presentation

Presentation Service (:mod:`pynetdicom.presentation`)
======================================================

.. currentmodule:: pynetdicom.presentation

The Presentation Service supports the creation of Presentation Contexts and
their negotiation during association.

Presentation Contexts
---------------------

.. autosummary::
   :toctree: generated/

   build_context
   build_role
   PresentationContext
   PresentationContextTuple

Presentation Context Negotiation
--------------------------------

.. autosummary::
   :toctree: generated/

   negotiate_as_acceptor
   negotiate_as_requestor


.. _api_presentation_prebuilt:

Pre-built Presentation Contexts
-------------------------------

.. autosummary::
   :toctree: generated/

   AllStoragePresentationContexts
   ApplicationEventLoggingPresentationContexts
   BasicWorklistManagementPresentationContexts
   ColorPalettePresentationContexts
   DefinedProcedureProtocolPresentationContexts
   DisplaySystemPresentationContexts
   HangingProtocolPresentationContexts
   ImplantTemplatePresentationContexts
   InstanceAvailabilityPresentationContexts
   MediaCreationManagementPresentationContexts
   MediaStoragePresentationContexts
   ModalityPerformedPresentationContexts
   NonPatientObjectPresentationContexts
   PrintManagementPresentationContexts
   ProcedureStepPresentationContexts
   ProtocolApprovalPresentationContexts
   QueryRetrievePresentationContexts
   RelevantPatientInformationPresentationContexts
   RTMachineVerificationPresentationContexts
   StoragePresentationContexts
   StorageCommitmentPresentationContexts
   SubstanceAdministrationPresentationContexts
   UnifiedProcedurePresentationContexts
   VerificationPresentationContexts
