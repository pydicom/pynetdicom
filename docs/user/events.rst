.. _user_events:

Events
------

*pynetdicom* uses an event-based handler system to give the user access to the
data exchanged between different services within the AE as well as the PDUs
received from and sent to the peer AE. *pynetdicom* events come in two types:
*notification events* and *intervention events*.

Notification Events
...................

Notification events are those events for which the event handler doesn't need
to return or yield anything. Notification events can have multiple handlers
bound to each event. The table below lists the available notification
events.

Intervention Events
...................

Intervention events are those events for while the event handler must return
or yield certain expected values so that *pynetdicom* can either complete
the association negotiation or support a service request. Each intervention
has only a single handler bound to it at all times, if the user hasn't bound
their own handler then the default one will be used which usually returns
a negative response (i.e. service request failed, or extended negotiation
ignored). The sole exception is the default handler for ``evt.EVT_C_ECHO``
which returns an ``0x0000`` *Success* status. The table below lists the
available intervention events.

+------------------------+
| Event                  | Description |
+========================+
| evt.EVT_ASYNC_OPS      | Association request includes Asynchronous Operations Window negotiation item
+------------------------+
| evt.EVT_SOP_COMMON     | Association request includes SOP Class Common Extended negotiation item(s)
+------------------------+
| evt.EVT_SOP_EXTENDED   | Association request includes SOP Class Extended negotiation item(s)
+------------------------+
| evt.EVT_USER_ID        | Association request includes User Identity negotiation item
+------------------------+
| evt.EVT_C_ECHO         | Service class received C-ECHO request
+------------------------+
| evt.EVT_C_FIND         | Service class received C-FIND request
+------------------------+
| evt.EVT_C_GET          | Service class received C-GET request
+------------------------+
| evt.EVT_C_MOVE         | Service class received C-MOVE request
+------------------------+
| evt.EVT_C_STORE        | Service class received C-STORE request
+------------------------+
| evt.EVT_N_ACTION       | Service class received N-ACTION request
+------------------------+
| evt.EVT_N_CREATE       | Service class received N-CREATE request
+------------------------+
| evt.EVT_N_DELETE       | Service class received N-DELETE request
+------------------------+
| evt.EVT_N_EVENT_REPORT | Service class received N-EVENT-REPORT request
+------------------------+
| evt.EVT_N_GET          | Service class received N-GET request
+------------------------+
| evt.EVT_N_SET          | Service class received N-SET request
+------------------------+


When an event is triggered it calls the func(evt), where *evt* is a Event
(TODO: add link to API) instance with extra attribute depending on the event
type. For example, if a C-ECHO request is received from a peer then the
Verification Service emits a evt.EVT_C_ECHO which triggers any functions
bound to that event with attributes:

    ::

        def on_c_echo(evt):
            """Something."""
            evt.context
            evt.message
            evt.timestamp
            """
            pass

            return 0x0000

Some events may only have one handler, and some require must return or yield
values.


.. _evt_transport:

Transport Service
.................

+----------------------+-------------------------------+------------+----------+
| Event                | Description                   | Event      | Multiple |
|                      |                               | Attributes | Handlers |
+======================+===============================+============+==========+
| EVT_CONNECTION_OPEN  | Connection with remote opened | address    | Yes      |
+----------------------+-------------------------------+------------+----------+
| EVT_CONNECTION_CLOSE | Connection with remote closed |            | Yes      |
+----------------------+-------------------------------+------------+----------+

.. _evt_verification:

Verification Service
....................

+-----------+-------------------------+------------+----------+---------+
| Event     | Description             | Event      | Multiple | Returns |
|           |                         | Attributes | Handlers |         |
+===========+=========================+============+==========+=========+
| EVT_ECHO  | Received C-ECHO request | context    | No       | int     |
|           |                         | request    |          |         |
|           |                         | info       |          |         |
+-----------+-------------------------+------------+----------+---------+

Where

* *context* is a ``namedtuple`` with attributes ``abstract_syntax``
  and ``transfer_syntax``.
* *request* is the C-ECHO request as a pydicom Dataset
* *info* is a dict containing information about the association

.. _evt_storage:

Storage Service
...............

+-----------+--------------------------+------------+----------+---------+
| Event     | Description              | Event      | Multiple | Returns |
|           |                          | Attributes | Handlers |         |
+===========+==========================+============+==========+=========+
| EVT_STORE | Received C-STORE request | dataset    | No       | int     |
|           |                          | context    |          |         |
|           |                          | request    |          |         |
|           |                          | info       |          |         |
+-----------+--------------------------+------------+----------+---------+

Where
* *dataset* is a pydicom Dataset containing the SOP Instance to be stored.
* *context* is a ``namedtuple`` with attributes ``abstract_syntax``
  and ``transfer_syntax``.
* *request* is the C-ECHO request as a pydicom Dataset
* *info* is a dict containing information about the association

The handler should return the Status of the storage operation as an int or
pydicom Dataset.
