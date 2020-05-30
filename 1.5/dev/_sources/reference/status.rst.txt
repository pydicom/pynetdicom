.. _api_status:

.. py:module:: pynetdicom.status

Statuses (:mod:`pynetdicom.status`)
====================================

.. currentmodule:: pynetdicom.status

Certain service classes allow assigning custom values to specific general
status types provided that they lay within a given range. The following status
codes are used internally within pynetdicom to help aid in debugging.

+------------------+---------------------------------------------------------+
| Code             | Description                                             |
+==================+=========================================================+
| 0xC000 to 0xC0FF | Non-service specific                                    |
+------------------+---------------------------------------------------------+
| 0xC001           | Event handler returned/yielded a status                 |
|                  | dataset with no (0000,0900) *Status* element.           |
+------------------+---------------------------------------------------------+
| 0xC002           | Event handler returned/yielded an invalid               |
|                  | status object (not a pydicom Dataset or an int)         |
+------------------+---------------------------------------------------------+
| 0xC200 to 0xC2FF | C-STORE related                                         |
+------------------+---------------------------------------------------------+
| 0xC210           | Failed to decode the dataset received from the peer     |
+------------------+---------------------------------------------------------+
| 0xC211           | Unhandled exception raised by the handler bound to      |
|                  | ``evt.EVT_C_STORE``                                     |
+------------------+---------------------------------------------------------+
| 0xC300 to 0xC3FF | C-FIND related                                          |
+------------------+---------------------------------------------------------+
| 0xC310           | Failed to decode the dataset received from the peer     |
+------------------+---------------------------------------------------------+
| 0xC311           | Unhandled exception raised by the handler bound to      |
|                  | ``evt.EVT_C_FIND``                                      |
+------------------+---------------------------------------------------------+
| 0xC312           | Failed to encode the dataset received from the handler  |
|                  | bound to ``evt.EVT_C_FIND``                             |
+------------------+---------------------------------------------------------+
| 0xC400 to 0xC4FF | C-GET related                                           |
+------------------+---------------------------------------------------------+
| 0xC410           | Failed to decode the dataset received from the peer     |
+------------------+---------------------------------------------------------+
| 0xC411           | Unhandled exception raised by the handler bound to      |
|                  | ``evt.EVT_C_GET``                                       |
+------------------+---------------------------------------------------------+
| 0xC413           | The handler bound to ``evt.EVT_C_GET``                  |
|                  | yielded an invalid number of sub-operations value       |
+------------------+---------------------------------------------------------+
| 0xC500 to 0xC5FF | C-MOVE related                                          |
+------------------+---------------------------------------------------------+
| 0xC510           | Failed to decode the dataset received from the peer     |
+------------------+---------------------------------------------------------+
| 0xC511           | Unhandled exception raised by the handler bound to      |
|                  | ``evt.EVT_C_MOVE``                                      |
+------------------+---------------------------------------------------------+
| 0xC513           | The handler bound to ``evt.EVT_C_MOVE``                 |
|                  | yielded an invalid number of sub-operations value       |
+------------------+---------------------------------------------------------+
| 0xC514           | The handler bound to ``evt.EVT_C_MOVE``                 |
|                  | failed to yield the (address, port) pair and/or the     |
|                  | number of sub-operations value                          |
+------------------+---------------------------------------------------------+
| 0xC515           | The handler bound to ``evt.EVT_C_MOVE``                 |
|                  | failed to yield a valid (address, port) pair            |
+------------------+---------------------------------------------------------+

.. autosummary::
   :toctree: generated/

   code_to_category
   code_to_status
   Status
