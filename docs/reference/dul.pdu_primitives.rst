.. _api_dul_primitives:

.. py:module:: pynetdicom.pdu_primitives

Service Primitives (:mod:`pynetdicom.pdu_primitives`)
======================================================

.. currentmodule:: pynetdicom.pdu_primitives

Protocol Data Units (PDUs) are the message formats exchanged between peer
application entities within a layer. A PDU consists of protocol control
information and user data and is constructed using mandatory fixed fields
followed by optional variable fields that contain one or more items and/or
sub-items.

The DICOM Upper Layer Services are:

.. toctree::
   :maxdepth: 1

   dul.pdu_primitives.a_associate
   dul.pdu_primitives.a_release
   dul.pdu_primitives.a_abort
   dul.pdu_primitives.a_p_abort
   dul.pdu_primitives.p_data
