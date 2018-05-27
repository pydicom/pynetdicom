PDU Items and Sub-items (:mod:`pynetdicom3.pdu_items`)
======================================================

.. toctree::
   :maxdepth: 2

   dul.pdu_items.a_associate_rq

A-ASSOCIATE-AC PDU Items
------------------------
.. autosummary::
   :toctree: generated/

   dul.pdu_items.application_context_item
   dul.pdu_items.presentation_context_item_ac
   dul.pdu_items.user_information_item

P-DATA-TF PDU Items
-------------------
.. autosummary::
   :toctree: generated/

   PresentationDataValueItem


The encoding of DICOM Upper Layer PDU Items and Sub-items is always Big Endian
byte ordering [1].

References
----------

1. DICOM Standard, Part 8, Section
   `9.3.1 <http://dicom.nema.org/medical/dicom/current/output/html/part08.html#sect_9.3.1>`_
2. [#] DICOM Standard, Part 8, Section
   `9.3 <http://dicom.nema.org/medical/dicom/current/output/html/part08.html#sect_9.3>`_ and
   `Annex D <http://dicom.nema.org/medical/dicom/current/output/html/part08.html#chapter_D>`_
3. [#] DICOM Standard, Part 7, `Annex D.3 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_D.3>`_
