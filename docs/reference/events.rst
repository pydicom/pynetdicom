.. _api_events:

.. py:module:: pynetdicom.events

Events and Handlers (:mod:`pynetdicom.events`)
==============================================

.. currentmodule:: pynetdicom.events

.. autosummary::
   :toctree: generated/

   Event
   InterventionEvent
   NotificationEvent
   trigger

Documentation for Intervention Event Handlers
---------------------------------------------

.. currentmodule:: pynetdicom._handlers

.. autosummary::
   :toctree: generated/

   doc_handle_echo
   doc_handle_find
   doc_handle_c_get
   doc_handle_move
   doc_handle_store
   doc_handle_action
   doc_handle_create
   doc_handle_delete
   doc_handle_event_report
   doc_handle_n_get
   doc_handle_set
   doc_handle_async
   doc_handle_sop_common
   doc_handle_sop_extended
   doc_handle_userid


Documentation for Notification Event Handlers
---------------------------------------------

.. autosummary::
   :toctree: generated/

   doc_handle_acse
   doc_handle_assoc
   doc_handle_dimse
   doc_handle_data
   doc_handle_fsm
   doc_handle_pdu
   doc_handle_transport
