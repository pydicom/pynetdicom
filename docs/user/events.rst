.. _user_events:

Events
------

*pynetdicom* uses an event handler-based system to give the user access to the
data exchanged between different services within an AE as well as the PDUs
received from and sent to the peer AE. Two different types of events are used:
*notification events* and *intervention events*.


Notification Events
...................

Notification events are those events for which the event handler doesn't need
to return or yield anything (i.e. the user is *notified* some event has
occurred). Notification events can have multiple handlers
bound to each event and any exceptions raised by any bound handlers are caught
and the exception message logged instead. The table below lists the available
notification events.

+----------------------------+-----------------------------------+
| Event                      | Description                       |
+============================+===================================+
| ``evt.EVT_ABORTED``        | Association aborted by local AE   |
+----------------------------+-----------------------------------+
| ``evt.EVT_ACCEPTED``       | Association accepted by local AE  |
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
| ``evt.EVT_DPU_SENT``       | PDU sent to the peer AE           |
+----------------------------+-----------------------------------+
| ``evt.EVT_PEER_ABORTED``   | Association aborted by peer AE    |
+----------------------------+-----------------------------------+
| ``evt.EVT_PEER_ACCEPTED``  | Association accepted by peer AE   |
+----------------------------+-----------------------------------+
| ``evt.EVT_PEER_REJECTED``  | Association rejected by peer AE   |
+----------------------------+-----------------------------------+
| ``evt.EVT_PEER_RELEASED``  | Association released by peer AE   |
+----------------------------+-----------------------------------+
| ``evt.EVT_PEER_REQUESTED`` | Association requested by peer AE  |
+----------------------------+-----------------------------------+
| ``evt.EVT_REJECTED``       | Association rejected by local AE  |
+----------------------------+-----------------------------------+
| ``evt.EVT_RELEASED``       | Association released by local AE  |
+----------------------------+-----------------------------------+
| ``evt.EVT_REQUESTED``      | Association requested by local AE |
+----------------------------+-----------------------------------+


Intervention Events
...................

Intervention events are those events for which the event handler must return
or yield certain expected values so that *pynetdicom* can complete an action
(i.e. user *intervention* is required).
Each intervention event has only a single handler bound to it at all times
and any exceptions raised by the bound handler will be caught and logged
instead. If the user hasn't bound their own handler then a default will be
used, which usually returns a negative response (i.e. service request failed,
or extended negotiation ignored). The sole exception is the default handler
for ``evt.EVT_C_ECHO`` which returns an ``0x0000`` *Success* status. The
table below lists the possible intervention events.

+----------------------------+--------------------------------+---------------------------+
| Event                      | Description                    | Handler Example           |
+============================+================================+===========================+
| Association request includes extended negotiation items                                 |
+----------------------------+--------------------------------+---------------------------+
| ``evt.EVT_ASYNC_OPS``      | Association request includes   | :ref:`example <ex_async>` |
|                            | Asynchronous Operations Window |                           |
|                            | negotiation item               |                           |
+----------------------------+--------------------------------+---------------------------+
| ``evt.EVT_SOP_COMMON``     | Association request includes   |                           |
|                            | SOP Class Common Extended      |                           |
|                            | negotiation item(s)            |                           |
+----------------------------+--------------------------------+---------------------------+
| ``evt.EVT_SOP_EXTENDED``   | Association request includes   |                           |
|                            | SOP Class Extended negotiation |                           |
|                            | item(s)                        |                           |
+----------------------------+--------------------------------+---------------------------+
| ``evt.EVT_USER_ID``        | Association request includes   |                           |
|                            | User Identity negotiation item |                           |
+----------------------------+--------------------------------+---------------------------+
| Service class received a DIMSE service request                                          |
+----------------------------+--------------------------------+---------------------------+
| ``evt.EVT_C_ECHO``         | Service class received         | :ref:`example <ex_verify>`|
|                            | C-ECHO request                 |                           |
+----------------------------+--------------------------------+---------------------------+
| ``evt.EVT_C_FIND``         | Service class received         |                           |
|                            | C-FIND request                 |                           |
+----------------------------+--------------------------------+---------------------------+
| ``evt.EVT_C_GET``          | Service class received         |                           |
|                            | C-GET request                  |                           |
+----------------------------+--------------------------------+---------------------------+
| ``evt.EVT_C_MOVE``         | Service class received         |                           |
|                            | C-MOVE request                 |                           |
+----------------------------+--------------------------------+---------------------------+
| ``evt.EVT_C_STORE``        | Service class received         |                           |
|                            | C-STORE request                |                           |
+----------------------------+--------------------------------+---------------------------+
| ``evt.EVT_N_ACTION``       | Service class received         |                           |
|                            | N-ACTION request               |                           |
+----------------------------+--------------------------------+---------------------------+
| ``evt.EVT_N_CREATE``       | Service class received         |                           |
|                            | N-CREATE request               |                           |
+----------------------------+--------------------------------+---------------------------+
| ``evt.EVT_N_DELETE``       | Service class received         |                           |
|                            | N-DELETE request               |                           |
+----------------------------+--------------------------------+---------------------------+
| ``evt.EVT_N_EVENT_REPORT`` | Service class received         |                           |
|                            | N-EVENT-REPORT request         |                           |
+----------------------------+--------------------------------+---------------------------+
| ``evt.EVT_N_GET``          | Service class received         |                           |
|                            | N-GET request                  |                           |
+----------------------------+--------------------------------+---------------------------+
| ``evt.EVT_N_SET``          | Service class received         |                           |
|                            | N-SET request                  |                           |
+----------------------------+--------------------------------+---------------------------+

Intervention events cover two broad classes of events; those related to
extended association negotiation and those related to supporting service
requests once an association has been established. For example, if a peer AE
requests the use of the Storage service, then the ``evt.EVT_C_STORE`` event
will be triggered and the user expected to handle storing the requested
dataset and returning a *status* value.


Event Handlers
..............
