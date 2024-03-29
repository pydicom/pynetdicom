.. _service_storecommit:

Storage Commitment Service Class
================================
The :dcm:`Storage Commitment Service Class<part04/chapter_J.html>`
defines a service that uses the DIMSE N-ACTION and N-EVENT-REPORT services to
provide a mechanism for the SCU to request the SCP make a commitment for the
safekeeping of SOP Instances.

.. _commitment_sops:

Supported SOP Classes
---------------------

+----------------------------+------------------------------------------------+
| UID                        | SOP Class                                      |
+============================+================================================+
| 1.2.840.10008.1.20.1       | StorageCommitmentPushModel                     |
+----------------------------+------------------------------------------------+


DIMSE Services
--------------

+-----------------+-----------------------------------------+
| DIMSE Service   | Usage SCU/SCP                           |
+=================+=========================================+
| N-EVENT-REPORT  | Mandatory/Mandatory                     |
+-----------------+-----------------------------------------+
| N-ACTION        | Mandatory/Mandatory                     |
+-----------------+-----------------------------------------+


.. _commitment_statuses:

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

N-EVENT-REPORT Statuses
~~~~~~~~~~~~~~~~~~~~~~~

+------------------+----------+----------------------------------+
| Code (hex)       | Category | Description                      |
+==================+==========+==================================+
| 0x0000           | Success  | Success                          |
+------------------+----------+----------------------------------+
| 0x0110           | Failure  | Processing failure               |
+------------------+----------+----------------------------------+
| 0x0112           | Failure  | No such SOP Instance             |
+------------------+----------+----------------------------------+
| 0x0113           | Failure  | No such event type               |
+------------------+----------+----------------------------------+
| 0x0114           | Failure  | No such argument                 |
+------------------+----------+----------------------------------+
| 0x0115           | Failure  | Invalid argument value           |
+------------------+----------+----------------------------------+
| 0x0117           | Failure  | Invalid object Instance          |
+------------------+----------+----------------------------------+
| 0x0118           | Failure  | No such SOP Class                |
+------------------+----------+----------------------------------+
| 0x0119           | Failure  | Class-Instance conflict          |
+------------------+----------+----------------------------------+
| 0x0210           | Failure  | Duplicate invocation             |
+------------------+----------+----------------------------------+
| 0x0211           | Failure  | Unrecognised operation           |
+------------------+----------+----------------------------------+
| 0x0212           | Failure  | Mistyped argument                |
+------------------+----------+----------------------------------+
| 0x0213           | Failure  | Resource limitation              |
+------------------+----------+----------------------------------+
