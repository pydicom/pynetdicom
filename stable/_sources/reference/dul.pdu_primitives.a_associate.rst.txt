.. _api_dul_primitives_aassociate:

A-ASSOCIATE
===========

.. currentmodule:: pynetdicom.pdu_primitives

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

   MaximumLengthNotification
   ImplementationClassUIDNotification
   ImplementationVersionNameNotification
   AsynchronousOperationsWindowNegotiation
   SCP_SCU_RoleSelectionNegotiation
   SOPClassExtendedNegotiation
   SOPClassCommonExtendedNegotiation
   UserIdentityNegotiation
