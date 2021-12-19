.. _presentation:

Presentation Service (:mod:`pynetdicom.presentation`)
======================================================

.. currentmodule:: pynetdicom.presentation

The Presentation Service supports the creation of Presentation Contexts and
their negotiation during association.

Creation

.. autosummary::
   :toctree: generated/

   PresentationContext
   build_context
   build_role

Negotiation

.. autosummary::
   :toctree: generated/

   negotiate_as_acceptor
   negotiate_as_requestor
