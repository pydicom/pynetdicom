.. _ae:

Application Entity
==================

.. currentmodule:: pynetdicom3.AE

A DICOM Application Entity (AE) is a conceptual representation of the software
that sends or receives DICOM information objects or messages. In pynetdicom3,
``AE`` is the highest level of the API and can be used to start associations
with peer AEs (as a *Service Class User*), listen for association requests
(as a *Service Class Provider*) or as a mix of the two. Once an association
has been established, AE is used when acting as an SCP to provide access to
the DIMSE messages sent by the peer.

.. toctree::
   :maxdepth: 2

   ae.init
   ae.scu
   ae.scp
