.. _service_appevent:

Application Event Logging Service Class
=======================================
The :dcm:`Application Event Logging Service Class<part04/chapter_P.html>`
defines a service that uses the DIMSE N-ACTION service to facilitate the
transfer of Event Log Records to be logged

.. _app_event_sops:

Supported SOP Classes
---------------------

+--------------------+----------------------------------------+
| UID                | SOP Class                              |
+====================+========================================+
| 1.2.840.10008.1.40 | ProceduralEventLogging                 |
+--------------------+----------------------------------------+
| 1.2.840.10008.1.42 | SubstanceAdministrationLogging         |
+--------------------+----------------------------------------+


DIMSE Services
--------------

+-----------------+----------------------------+
| DIMSE Service   | Usage SCU/SCP              |
+=================+============================+
| *Procedural Event Logging SOP Class*         |
+-----------------+----------------------------+
| N-ACTION        | Mandatory/Mandatory        |
+-----------------+----------------------------+
| *Substance Administration Logging SOP Class* |
+-----------------+----------------------------+
| N-CREATE        | Mandatory/Mandatory        |
+-----------------+----------------------------+


.. _app_event_statuses:

Statuses
--------

N-ACTION Statuses
~~~~~~~~~~~~~~~~~

+------------------+----------+-----------------------------------------------+
| Code (hex)       | Category | Description                                   |
+==================+==========+===============================================+
| 0x0000           | Success  | Success                                       |
+------------------+----------+-----------------------------------------------+
| 0x0112           | Failure  | No such SOP Instance                          |
+------------------+----------+-----------------------------------------------+
| 0x0114           | Failure  | No such argument                              |
+------------------+----------+-----------------------------------------------+
| 0x0115           | Failure  | Invalid argument value                        |
+------------------+----------+-----------------------------------------------+
| 0x0117           | Failure  | Invalid object instance                       |
+------------------+----------+-----------------------------------------------+
| 0x0118           | Failure  | No such SOP Class                             |
+------------------+----------+-----------------------------------------------+
| 0x0119           | Failure  | Class-Instance conflict                       |
+------------------+----------+-----------------------------------------------+
| 0x0123           | Failure  | No such action                                |
+------------------+----------+-----------------------------------------------+
| 0x0124           | Failure  | Refused: not authorised                       |
+------------------+----------+-----------------------------------------------+
| 0x0210           | Failure  | Duplicate invocation                          |
+------------------+----------+-----------------------------------------------+
| 0x0211           | Failure  | Unrecognised operation                        |
+------------------+----------+-----------------------------------------------+
| 0x0212           | Failure  | Mistyped argument                             |
+------------------+----------+-----------------------------------------------+
| 0x0213           | Failure  | Resource limitation                           |
+------------------+----------+-----------------------------------------------+

Application Event Logging Service Statuses
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+------------------+----------+-----------------------------------------------+
| Code (hex)       | Category | Description                                   |
+==================+==========+===============================================+
| 0xB101           | Warning  | Specified Synchronisation Frame of Reference  |
|                  |          | UID does not match SCP Synchronisation Frame  |
|                  |          | of Reference                                  |
+------------------+----------+-----------------------------------------------+
| 0xB102           | Warning  | Study Instance UID coercion; Event logged     |
|                  |          | under a different Study Instance UID          |
+------------------+----------+-----------------------------------------------+
| 0xB104           | Warning  | IDs inconsistent in matching current study;   |
|                  |          | Event logged                                  |
+------------------+----------+-----------------------------------------------+
| 0xC101           | Failure  | Procedural Logging not available for          |
|                  |          | specified Study Instance UID                  |
+------------------+----------+-----------------------------------------------+
| 0xC102           | Failure  | Event Information does not match Template     |
+------------------+----------+-----------------------------------------------+
| 0xC103           | Failure  | Cannot match event to a current study         |
+------------------+----------+-----------------------------------------------+
| 0xC104           | Failure  | IDs inconsistent in matching a current study; |
|                  |          | Event not logged                              |
+------------------+----------+-----------------------------------------------+
| 0xC10E           | Failure  | Operator not authorised to add entry to       |
|                  |          | Medication Administration Record              |
+------------------+----------+-----------------------------------------------+
| 0xC110           | Failure  | Patient cannot be identified from Patient ID  |
|                  |          | (0010,0020) or Admission ID (0038,0010)       |
+------------------+----------+-----------------------------------------------+
| 0xC111           | Failure  | Update of Medication Administration Record    |
|                  |          | failed                                        |
+------------------+----------+-----------------------------------------------+
