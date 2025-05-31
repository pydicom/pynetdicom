.. _user_events:


Event types
-----------

*pynetdicom* uses an event-handler system to give the user access to the
data exchanged between different services within an AE as well as the PDUs
and data sent between the local and peer AEs. Two different types of events
are used: *notification events* and *intervention events*. Events are imported
using ``from pynetdicom import evt``


.. _events_notification:

Notification Events
-------------------

Notification events are those events where bound event handlers don't need
to return or yield anything (i.e. the user is *notified* some event has
occurred). Each notification event can have multiple handlers
bound to it and any exceptions raised by the handlers are caught
and the exception message logged instead. The table below lists the available
notification events.

.. currentmodule:: pynetdicom._handlers

.. csv-table::
   :header: Event, Description
   :widths: 15, 30

   :func:`evt.EVT_ABORTED<doc_handle_assoc>`,Association aborted
   :func:`evt.EVT_ACCEPTED<doc_handle_assoc>`,Association accepted
   :func:`evt.EVT_ACSE_RECV<doc_handle_acse>`,ACSE received a primitive from the DUL service provider
   :func:`evt.EVT_ACSE_SENT<doc_handle_acse>`,ACSE sent a primitive to the DUL service provider
   :func:`evt.EVT_CONN_CLOSE<doc_handle_transport>`,Connection with remote closed
   :func:`evt.EVT_CONN_OPEN<doc_handle_transport>`, Connection with remote opened
   :func:`evt.EVT_DATA_RECV<doc_handle_data>`,Data received from the peer AE
   :func:`evt.EVT_DATA_SENT<doc_handle_data>`,Data sent to the peer AE
   :func:`evt.EVT_DIMSE_RECV<doc_handle_dimse>`,DIMSE service received and decoded a message
   :func:`evt.EVT_DIMSE_SENT<doc_handle_dimse>`,DIMSE service encoded and sent a message
   :func:`evt.EVT_ESTABLISHED<doc_handle_assoc>`,Association established
   :func:`evt.EVT_FSM_TRANSITION<doc_handle_fsm>`,State machine transitioning
   :func:`evt.EVT_PDU_RECV<doc_handle_pdu>`,PDU received from the peer AE
   :func:`evt.EVT_PDU_SENT<doc_handle_pdu>`,PDU sent to the peer AE
   :func:`evt.EVT_REJECTED<doc_handle_assoc>`,Association rejected
   :func:`evt.EVT_RELEASED<doc_handle_assoc>`,Association released
   :func:`evt.EVT_REQUESTED<doc_handle_assoc>`,Association requested

By default a number of notification handlers are bound for logging purposes.
If you wish to remove these then you can do the following before creating any
associations:

::

    from pynetdicom import _config

    # Don't bind any of the default notification handlers
    _config.LOG_HANDLER_LEVEL = 'none'


.. _events_intervention:

Intervention Events
-------------------

Intervention events are those events where the bound event handler *must* return
or yield certain expected values so that *pynetdicom* can complete an action
(i.e. user *intervention* is required).
Each intervention event has only a single handler bound to it at all times.
If the user hasn't bound their own handler then a default will be
used, which usually returns a negative response (i.e. service request failed,
or extended negotiation ignored). The sole exception is the default handler
for ``evt.EVT_C_ECHO`` which returns an ``0x0000`` *Success* status. The
table below lists the possible intervention events.

.. currentmodule:: pynetdicom._handlers

Association related
~~~~~~~~~~~~~~~~~~~~

.. csv-table::
   :header: Event, Description
   :widths: 10, 30

   :func:`evt.EVT_ASYNC_OPS<doc_handle_async>`,Association request includes asynchronous operations negotiation item
   :func:`evt.EVT_SOP_COMMON<doc_handle_sop_common>`,Association request includes SOP Class Common Extended negotiation item(s)
   :func:`evt.EVT_SOP_EXTENDED<doc_handle_sop_extended>`,Association request includes SOP Class Extended negotiation item(s)
   :func:`evt.EVT_USER_ID<doc_handle_userid>`,Association request includes User Identity negotiation item


Service Class related
~~~~~~~~~~~~~~~~~~~~~

.. csv-table::
   :header: Event, Description
   :widths: 15, 30

   :func:`evt.EVT_C_ECHO<doc_handle_echo>`,Received C-ECHO request
   :func:`evt.EVT_C_FIND<doc_handle_find>`,Received C-FIND request
   :func:`evt.EVT_C_GET<doc_handle_c_get>`,Received C-GET request
   :func:`evt.EVT_C_MOVE<doc_handle_move>`,Received C-MOVE request
   :func:`evt.EVT_C_STORE<doc_handle_store>`,Received C-STORE request
   :func:`evt.EVT_N_ACTION<doc_handle_action>`,Received N-ACTION request
   :func:`evt.EVT_N_CREATE<doc_handle_create>`,Received N-CREATE request
   :func:`evt.EVT_N_DELETE<doc_handle_delete>`,Received N-DELETE request
   :func:`evt.EVT_N_EVENT_REPORT<doc_handle_event_report>`,Received N-EVENT-REPORT request
   :func:`evt.EVT_N_GET<doc_handle_n_get>`,Received N-GET request
   :func:`evt.EVT_N_SET<doc_handle_set>`,Received N-SET request

.. currentmodule:: pynetdicom.events
