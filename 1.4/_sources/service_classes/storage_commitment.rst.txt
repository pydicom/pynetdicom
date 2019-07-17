Storage Commitment Service Class
================================
The `Storage Commitment Service Class
<http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_J>`_
defines a service that uses the DIMSE N-ACTION and N-EVENT-REPORT services to
provide a mechanism for the SCU to request the SCP make a commitment for the
safekeeping of SOP Instances.

.. _commitment_sops:

Supported SOP Classes
---------------------

+----------------------------+------------------------------------------------+
| UID                        | SOP Class                                      |
+============================+================================================+
| 1.2.840.10008.1.20.1       | StorageCommitmentPushModelSOPClass             |
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


References
----------

* DICOM Standard, Part 4, `Annex J <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_J>`_
* DICOM Standard, Part 7, `Section 10.1.4.1.10 <http://dicom.nema.org/medical/dicom/current/output/chtml/part07/chapter_10.html#sect_10.1.4.1.10>`_
* DICOM Standard, Part 7, `Section 10.1.1.1.8 <http://dicom.nema.org/medical/dicom/current/output/chtml/part07/chapter_10.html#sect_10.1.1.1.8>`_
