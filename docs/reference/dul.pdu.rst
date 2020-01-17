.. _api_dul_pdu:

.. py:module:: pynetdicom.pdu

PDUs (:mod:`pynetdicom.pdu`)
=============================

.. currentmodule:: pynetdicom.pdu

Protocol Data Units (PDUs) are the message formats exchanged between peer
application entities within a layer. A PDU consists of protocol control
information and user data and are constructed using mandatory fixed fields
followed by optional variable fields that contain one or more items and/or
sub-items.

The DICOM Upper Layer protocol consists of seven Protocol Data Units:

.. toctree::
   :maxdepth: 1
   :includehidden:

   dul.pdu.a_associate_rq
   dul.pdu.a_associate_ac
   dul.pdu.a_associate_rj
   dul.pdu.p_data_tf
   dul.pdu.a_release_rq
   dul.pdu.a_release_rp
   dul.pdu.a_abort_rq

PDUs should be encoded as binary data prior to being sent to a peer
Application Entities using the ``encode()`` class method. Each encoded PDU has
as its first byte value a corresponding *PDU Type*:

| ``0x01`` - A-ASSOCIATE-RQ
| ``0x02`` - A-ASSOCIATE-AC
| ``0x03`` - A-ASSOCIATE-RJ
| ``0x04`` - P-DATA-TF
| ``0x05`` - A-RELEASE-RQ
| ``0x06`` - A-RELEASE-RP
| ``0x07`` - A-ABORT

The encoding of DICOM Upper Layer PDUs is always Big Endian byte ordering.
