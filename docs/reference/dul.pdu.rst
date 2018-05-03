PDUs (:mod:`pynetdicom3.pdu`)
=============================

.. currentmodule:: pynetdicom3.pdu

Protocol Data Units (PDUs) are the message formats exchanged between peer
application entities within a layer. A PDU consists of protocol control
information and user data and are constructed using mandatory fixed fields
followed by optional variable fields that contain one or more items and/or
sub-items.

The DICOM Upper Layer protocol consists of seven Protocol Data Units:

.. toctree::
   :maxdepth: 1

   dul.pdu.a_associate_rq
   dul.pdu.a_associate_ac
   dul.pdu.a_associate_rj
   dul.pdu.p_data_tf
   dul.pdu.a_release_rq
   dul.pdu.a_release_rp
   dul.pdu.a_abort_rq

The encoding of DICOM Upper Layer PDUs is always Big Endian byte ordering [1].

References
----------

1. DICOM Standard, Part 8, Section
   `9.3.1 <http://dicom.nema.org/medical/dicom/current/output/html/part08.html#sect_9.3.1>`_
2. [#] DICOM Standard, Part 8, Section
   `9.3 <http://dicom.nema.org/medical/dicom/current/output/html/part08.html#sect_9.3>`_ and
   `Annex D <http://dicom.nema.org/medical/dicom/current/output/html/part08.html#chapter_D>`_
3. [#] DICOM Standard, Part 7, `Annex D.3 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_D.3>`_
