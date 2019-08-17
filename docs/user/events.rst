.. _user_events:

Events
------

*pynetdicom* uses an event-handler system to give the user access to the
data exchanged between different services within an AE as well as the PDUs
and data sent between the local and peer AEs. Two different types of events
are used: *notification events* and *intervention events*. Events are imported
using ``from pynetdicom import evt``

.. _events_notification:

Notification Events
...................

Notification events are those events where bound event handlers don't need
to return or yield anything (i.e. the user is *notified* some event has
occurred). Each notification event can have multiple handlers
bound to it and any exceptions raised by the handlers are caught
and the exception message logged instead. The table below lists the available
notification events.

+----------------------------+-----------------------------------+
| Event                      | Description                       |
+============================+===================================+
| ``evt.EVT_ABORTED``        | Association aborted               |
+----------------------------+-----------------------------------+
| ``evt.EVT_ACCEPTED``       | Association accepted              |
+----------------------------+-----------------------------------+
| ``evt.EVT_ACSE_RECV``      | ACSE received a primitive         |
|                            | from the DUL service provider     |
+----------------------------+-----------------------------------+
| ``evt.EVT_ACSE_SENT``      | ACSE sent a primitive             |
|                            | to the DUL service provider       |
+----------------------------+-----------------------------------+
| ``evt.EVT_CONN_CLOSE``     | Connection with remote closed     |
+----------------------------+-----------------------------------+
| ``evt.EVT_CONN_OPEN``      | Connection with remote opened     |
+----------------------------+-----------------------------------+
| ``evt.EVT_DATA_RECV``      | Data received from the peer AE    |
+----------------------------+-----------------------------------+
| ``evt.EVT_DATA_SENT``      | Data sent to the peer AE          |
+----------------------------+-----------------------------------+
| ``evt.EVT_DIMSE_RECV``     | DIMSE service received and        |
|                            | decoded a message                 |
+----------------------------+-----------------------------------+
| ``evt.EVT_DIMSE_SENT``     | DIMSE service encoded and         |
|                            | sent a message                    |
+----------------------------+-----------------------------------+
| ``evt.EVT_ESTABLISHED``    | Association established           |
+----------------------------+-----------------------------------+
| ``evt.EVT_FSM_TRANSITION`` | State machine transitioning       |
+----------------------------+-----------------------------------+
| ``evt.EVT_PDU_RECV``       | PDU received from the peer AE     |
+----------------------------+-----------------------------------+
| ``evt.EVT_PDU_SENT``       | PDU sent to the peer AE           |
+----------------------------+-----------------------------------+
| ``evt.EVT_REJECTED``       | Association rejected              |
+----------------------------+-----------------------------------+
| ``evt.EVT_RELEASED``       | Association released              |
+----------------------------+-----------------------------------+
| ``evt.EVT_REQUESTED``      | Association requested             |
+----------------------------+-----------------------------------+

By default a number of notification handlers are bound for logging purposes.
If you wish to remove these then you can do the following before creating any
associations:

::

    from pynetdicom import _config

    # Don't bind any of the default notification handlers
    _config.LOG_HANDLER_LEVEL = 'none'


.. _events_intervention:

Intervention Events
...................

Intervention events are those events where the bound event handler must return
or yield certain expected values so that *pynetdicom* can complete an action
(i.e. user *intervention* is required).
Each intervention event has only a single handler bound to it at all times.
If the user hasn't bound their own handler then a default will be
used, which usually returns a negative response (i.e. service request failed,
or extended negotiation ignored). The sole exception is the default handler
for ``evt.EVT_C_ECHO`` which returns an ``0x0000`` *Success* status. The
table below lists the possible intervention events.

.. currentmodule:: pynetdicom._handlers

+----------------------------+--------------------------------+----------------------------------------------------------+
| Event                      | Description                    |                                                          |
+============================+================================+==========================================================+
| Association request includes extended negotiation items                                                                |
+----------------------------+--------------------------------+----------------------------------------------------------+
| ``evt.EVT_ASYNC_OPS``      | Association request includes   | :func:`Handler documentation<doc_handle_async>`          |
|                            | Asynchronous Operations Window |                                                          |
|                            | negotiation item               |                                                          |
+----------------------------+--------------------------------+----------------------------------------------------------+
| ``evt.EVT_SOP_COMMON``     | Association request includes   | :func:`Handler documentation<doc_handle_sop_common>`     |
|                            | SOP Class Common Extended      |                                                          |
|                            | negotiation item(s)            |                                                          |
+----------------------------+--------------------------------+----------------------------------------------------------+
| ``evt.EVT_SOP_EXTENDED``   | Association request includes   | :func:`Handler documentation<doc_handle_sop_extended>`   |
|                            | SOP Class Extended negotiation |                                                          |
|                            | item(s)                        |                                                          |
+----------------------------+--------------------------------+----------------------------------------------------------+
| ``evt.EVT_USER_ID``        | Association request includes   | :func:`Handler documentation<doc_handle_userid>`         |
|                            | User Identity negotiation item |                                                          |
+----------------------------+--------------------------------+----------------------------------------------------------+
| Service class received a DIMSE service request                                                                         |
+----------------------------+--------------------------------+----------------------------------------------------------+
| ``evt.EVT_C_ECHO``         | Service class received         | :func:`Handler documentation<doc_handle_echo>`           |
|                            | C-ECHO request                 |                                                          |
+----------------------------+--------------------------------+----------------------------------------------------------+
| ``evt.EVT_C_FIND``         | Service class received         | :func:`Handler documentation<doc_handle_find>`           |
|                            | C-FIND request                 |                                                          |
+----------------------------+--------------------------------+----------------------------------------------------------+
| ``evt.EVT_C_GET``          | Service class received         | :func:`Handler documentation<doc_handle_c_get>`          |
|                            | C-GET request                  |                                                          |
+----------------------------+--------------------------------+----------------------------------------------------------+
| ``evt.EVT_C_MOVE``         | Service class received         | :func:`Handler documentation<doc_handle_move>`           |
|                            | C-MOVE request                 |                                                          |
+----------------------------+--------------------------------+----------------------------------------------------------+
| ``evt.EVT_C_STORE``        | Service class received         | :func:`Handler documentation<doc_handle_store>`          |
|                            | C-STORE request                |                                                          |
+----------------------------+--------------------------------+----------------------------------------------------------+
| ``evt.EVT_N_ACTION``       | Service class received         | :func:`Handler documentation<doc_handle_action>`         |
|                            | N-ACTION request               |                                                          |
+----------------------------+--------------------------------+----------------------------------------------------------+
| ``evt.EVT_N_CREATE``       | Service class received         | :func:`Handler documentation<doc_handle_create>`         |
|                            | N-CREATE request               |                                                          |
+----------------------------+--------------------------------+----------------------------------------------------------+
| ``evt.EVT_N_DELETE``       | Service class received         | :func:`Handler documentation<doc_handle_delete>`         |
|                            | N-DELETE request               |                                                          |
+----------------------------+--------------------------------+----------------------------------------------------------+
| ``evt.EVT_N_EVENT_REPORT`` | Service class received         | :func:`Handler documentation<doc_handle_event_report>`   |
|                            | N-EVENT-REPORT request         |                                                          |
+----------------------------+--------------------------------+----------------------------------------------------------+
| ``evt.EVT_N_GET``          | Service class received         | :func:`Handler documentation<doc_handle_n_get>`          |
|                            | N-GET request                  |                                                          |
+----------------------------+--------------------------------+----------------------------------------------------------+
| ``evt.EVT_N_SET``          | Service class received         | :func:`Handler documentation<doc_handle_set>`            |
|                            | N-SET request                  |                                                          |
+----------------------------+--------------------------------+----------------------------------------------------------+

.. currentmodule:: pynetdicom.events

Event Handlers
..............

Event handlers are callable functions bound to an event that get passed a
single parameter, *event*, which is an :class:`Event` instance. All
:class:`Event` instances come with at least three attributes:

* :attr:`Event.assoc` - the
  :class:`Association <pynetdicom.association.Association>` in which the
  event occurred
* :attr:`Event.event` - the corresponding event, as a python
  :func:`namedtuple<collections.namedtuple>`
* :attr:`Event.timestamp` - the date and time the event occurred at, as a
  Python :class:`datetime.datetime`

Additional attributes and properties are available depending on the event type,
see the `handler implementation documentation
<../reference/events.html>`_ for more information.

Handlers can be bound to events through the ``bind(event, handler)`` methods
in the :class:`~pynetdicom.association.Association` and
:class:`~pynetdicom.transport.AssociationServer` classes or by using the
*evt_handlers* keyword argument with
:meth:`AE.associate()<pynetdicom.ae.ApplicationEntity.associate>` and
:meth:`AE.start_server()<pynetdicom.ae.ApplicationEntity.start_server>`.
Handlers can be unbound with the ``unbind(event, handler)`` methods in the
:class:`~pynetdicom.association.Association` and
:class:`~pynetdicom.transport.AssociationServer` classes. See the
:ref:`Association<association>` guide for more details.
