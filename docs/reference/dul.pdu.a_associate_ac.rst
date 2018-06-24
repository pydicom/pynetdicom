A-ASSOCIATE-AC PDU
==================

.. currentmodule:: pynetdicom3.pdu

An A-ASSOCIATE-AC PDU is made of a sequence of mandatory fields followed by a
variable length field that must contain one Application Context item, one or
more Presentation Context items and one User Information item. Sub-items shall
exist for the Presentation Context and User Information items.

PDU
---

.. autosummary::
   :toctree: generated/

   A_ASSOCIATE_AC

Variable Items
--------------
.. currentmodule:: pynetdicom3.pdu_items

.. autosummary::
   :toctree: generated/

   ApplicationContextItem
   PresentationContextItemRQ
   UserInformationItem

Presentation Context Sub-items
------------------------------

.. autosummary::
   :toctree: generated/

   AbstractSyntaxSubItem
   TransferSyntaxSubItem

User Information Sub-items
--------------------------

.. autosummary::
   :toctree: generated/

   MaximumLengthSubItem
   ImplementationClassUIDSubItem
   ImplementationVersionNameSubItem
   SCP_SCU_RoleSelectionSubItem
   AsynchronousOperationsWindowSubItem
   UserIdentitySubItemAC
   SOPClassExtendedNegotiationSubItem
   SOPClassCommonExtendedNegotiationSubItem

References
----------

1. DICOM Standard, Part 8, Section
   `9.3.3 <http://dicom.nema.org/medical/dicom/current/output/html/part08.html#sect_9.3.3>`_
