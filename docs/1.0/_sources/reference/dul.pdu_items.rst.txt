PDU Items and Sub-items (:mod:`pynetdicom.pdu_items`)
======================================================

.. currentmodule:: pynetdicom.pdu_items

.. autosummary::
   :toctree: generated/
   :nosignatures:

   ApplicationContextItem
   PresentationContextItemRQ
   PresentationContextItemAC
   UserInformationItem
   AbstractSyntaxSubItem
   TransferSyntaxSubItem
   MaximumLengthSubItem
   ImplementationClassUIDSubItem
   ImplementationVersionNameSubItem
   SCP_SCU_RoleSelectionSubItem
   AsynchronousOperationsWindowSubItem
   UserIdentitySubItemRQ
   UserIdentitySubItemAC
   SOPClassExtendedNegotiationSubItem
   SOPClassCommonExtendedNegotiationSubItem
   PresentationDataValueItem

The encoding of DICOM Upper Layer PDU Items and Sub-items is always Big Endian
byte ordering [1].

References
----------

1. DICOM Standard, Part 8, Section
   `9.3.1 <http://dicom.nema.org/medical/dicom/current/output/html/part08.html#sect_9.3.1>`_
