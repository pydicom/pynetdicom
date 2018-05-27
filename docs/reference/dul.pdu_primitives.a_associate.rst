A-ASSOCIATE
===========

.. currentmodule:: pynetdicom3.pdu_primitives

The establishment of an association between two Application Entities shall be
performed through ACSE A-ASSOCIATE request, indication, response and
confirmation primitives.

.. autosummary::
   :toctree: generated/

   A_ASSOCIATE

The A-ASSOCIATE service makes use of one or more of the following User
Information primitives:

.. autosummary::
   :toctree: generated/

   MaximumLengthNegotiation
   ImplementationClassUIDNotification
   ImplementationVersionNameNotification
   AsynchronousOperationsWindowNegotiation
   SCP_SCU_RoleSelectionNegotiation
   SOPClassExtendedNegotiation
   SOPClassCommonExtendedNegotiation
   UserIdentityNegotiation

References
----------

1. DICOM Standard, Part 8, Section
   `7.1 <http://dicom.nema.org/medical/dicom/current/output/html/part08.html#sect_7.1>`_
