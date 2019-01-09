P-DATA-TF PDU
=============

.. currentmodule:: pynetdicom.pdu

A P-DATA-TF PDU is made of a sequence of mandatory fields followed by a
variable length field. The variable data field shall contain one or more
Presentation Data Value items.

PDU
---

.. autosummary::
   :toctree: generated/

   P_DATA_TF

Variable Items
--------------

.. autosummary::
   :toctree: generated/

   PresentationDataValueItem

References
----------

1. DICOM Standard, Part 8, Section
   `9.3.5 <http://dicom.nema.org/medical/dicom/current/output/html/part08.html#sect_9.3.5>`_
