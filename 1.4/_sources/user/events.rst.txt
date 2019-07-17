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

+----------------------------+--------------------------------+--------------------------------------------------------------------------------+
| Event                      | Description                    |                                                                                |
+============================+================================+================================================================================+
| Association request includes extended negotiation items                                                                                      |
+----------------------------+--------------------------------+--------------------------------------------------------------------------------+
| ``evt.EVT_ASYNC_OPS``      | Association request includes   | `Handler documentation                                                         |
|                            | Asynchronous Operations Window | <../reference/generated/pynetdicom._handlers.doc_handle_async.html>`_          |
|                            | negotiation item               |                                                                                |
+----------------------------+--------------------------------+--------------------------------------------------------------------------------+
| ``evt.EVT_SOP_COMMON``     | Association request includes   | `Handler documentation                                                         |
|                            | SOP Class Common Extended      | <../reference/generated/pynetdicom._handlers.doc_handle_sop_common.html>`_     |
|                            | negotiation item(s)            |                                                                                |
+----------------------------+--------------------------------+--------------------------------------------------------------------------------+
| ``evt.EVT_SOP_EXTENDED``   | Association request includes   | `Handler documentation                                                         |
|                            | SOP Class Extended negotiation | <../reference/generated/pynetdicom._handlers.doc_handle_sop_extended.html>`_   |
|                            | item(s)                        |                                                                                |
+----------------------------+--------------------------------+--------------------------------------------------------------------------------+
| ``evt.EVT_USER_ID``        | Association request includes   | `Handler documentation                                                         |
|                            | User Identity negotiation item | <../reference/generated/pynetdicom._handlers.doc_handle_userid.html>`_         |
+----------------------------+--------------------------------+--------------------------------------------------------------------------------+
| Service class received a DIMSE service request                                                                                               |
+----------------------------+--------------------------------+--------------------------------------------------------------------------------+
| ``evt.EVT_C_ECHO``         | Service class received         | `Handler documentation                                                         |
|                            | C-ECHO request                 | <../reference/generated/pynetdicom._handlers.doc_handle_echo.html>`_           |
+----------------------------+--------------------------------+--------------------------------------------------------------------------------+
| ``evt.EVT_C_FIND``         | Service class received         | `Handler documentation                                                         |
|                            | C-FIND request                 | <../reference/generated/pynetdicom._handlers.doc_handle_find.html>`_           |
+----------------------------+--------------------------------+--------------------------------------------------------------------------------+
| ``evt.EVT_C_GET``          | Service class received         | `Handler documentation                                                         |
|                            | C-GET request                  | <../reference/generated/pynetdicom._handlers.doc_handle_c_get.html>`_          |
+----------------------------+--------------------------------+--------------------------------------------------------------------------------+
| ``evt.EVT_C_MOVE``         | Service class received         | `Handler documentation                                                         |
|                            | C-MOVE request                 | <../reference/generated/pynetdicom._handlers.doc_handle_move.html>`_           |
+----------------------------+--------------------------------+--------------------------------------------------------------------------------+
| ``evt.EVT_C_STORE``        | Service class received         | `Handler documentation                                                         |
|                            | C-STORE request                | <../reference/generated/pynetdicom._handlers.doc_handle_store.html>`_          |
+----------------------------+--------------------------------+--------------------------------------------------------------------------------+
| ``evt.EVT_N_ACTION``       | Service class received         | `Handler documentation                                                         |
|                            | N-ACTION request               | <../reference/generated/pynetdicom._handlers.doc_handle_n_action.html>`_       |
+----------------------------+--------------------------------+--------------------------------------------------------------------------------+
| ``evt.EVT_N_CREATE``       | Service class received         | `Handler documentation                                                         |
|                            | N-CREATE request               | <../reference/generated/pynetdicom._handlers.doc_handle_n_create.html>`_       |
+----------------------------+--------------------------------+--------------------------------------------------------------------------------+
| ``evt.EVT_N_DELETE``       | Service class received         | `Handler documentation                                                         |
|                            | N-DELETE request               | <../reference/generated/pynetdicom._handlers.doc_handle_n_delete.html>`_       |
+----------------------------+--------------------------------+--------------------------------------------------------------------------------+
| ``evt.EVT_N_EVENT_REPORT`` | Service class received         | `Handler documentation                                                         |
|                            | N-EVENT-REPORT request         | <../reference/generated/pynetdicom._handlers.doc_handle_n_event_report.html>`_ |
+----------------------------+--------------------------------+--------------------------------------------------------------------------------+
| ``evt.EVT_N_GET``          | Service class received         | `Handler documentation                                                         |
|                            | N-GET request                  | <../reference/generated/pynetdicom._handlers.doc_handle_n_get.html>`_          |
+----------------------------+--------------------------------+--------------------------------------------------------------------------------+
| ``evt.EVT_N_SET``          | Service class received         | `Handler documentation                                                         |
|                            | N-SET request                  | <../reference/generated/pynetdicom._handlers.doc_handle_n_set.html>`_          |
+----------------------------+--------------------------------+--------------------------------------------------------------------------------+


Event Handlers
..............

Event handlers are callable functions bound to an event that get passed a single
parameter, *event*, which is an :py:class:`Event <pynetdicom.events.Event>`
instance. All ``Event`` instances come with at least three attributes:

* ``Event.assoc`` - the
  :py:class:`Association <pynetdicom.association.Association>` in which the
  event occurred
* ``Event.event`` - the corresponding event, as a python
  `namedtuple <https://docs.python.org/3/library/collections.html#collections.namedtuple>`_
* ``Event.timestamp`` - the date and time the event occurred at, as a python
  `datetime <https://docs.python.org/3/library/datetime.html#datetime-objects>`_

Additional attributes and properties are available depending on the event type,
see the `handler implementation documentation
<../reference/events.html>`_ for more information.

Handlers can be bound to events through the ``bind(event, handler)`` methods
in the ``Association`` and ``AssociationServer`` classes or by using the
``evt_handlers`` keyword argument to ``AE.associate()`` and
``AE.start_server()``. Handlers can be unbound with the
``unbind(event, handler)`` methods in the ``Association`` and
``AssociationServer`` classes. See the :ref:`Association<association>`
guide for more details.
