.. _user_events:

Events
------

*pynetdicom* uses events to something

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
