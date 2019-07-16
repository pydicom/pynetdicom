Modality Performed Procedure Step Management
============================================
`Modality Performed Procedure Step Management <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_F>`_
defines a service that facilitates logging and tracking of procedures performed
by a modality.

.. _mpps_sops:

Supported SOP Classes
---------------------

+-----------------------------+----------------------------------------------------+
| UID                         | SOP Class                                          |
+=============================+====================================================+
| 1.2.840.10008.3.1.2.3.3     | ModalityPerformedProcedureStepSOPClass             |
+-----------------------------+----------------------------------------------------+
| 1.2.840.10008.3.1.2.3.4     | ModalityPerformedProcedureStepRetrieveSOPClass     |
+-----------------------------+----------------------------------------------------+
| 1.2.840.10008.3.1.2.3.5     | ModalityPerformedProcedureStepNotificationSOPClass |
+-----------------------------+----------------------------------------------------+


DIMSE Services
--------------

+-----------------+------------------------------------------+
| DIMSE Service   | Usage SCU/SCP                            |
+=================+==========================================+
| *Modality Performed Procedure Step SOP Class*              |
+-----------------+------------------------------------------+
| N-CREATE        | Mandatory/Mandatory                      |
+-----------------+------------------------------------------+
| N-SET           | Mandatory/Mandatory                      |
+-----------------+------------------------------------------+
| *Modality Performed Procedure Step Retrieve SOP Class*     |
+-----------------+------------------------------------------+
| N-GET           | Mandatory/Mandatory                      |
+-----------------+------------------------------------------+
| *Modality Performed Procedure Step Notification SOP Class* |
+-----------------+------------------------------------------+
| N-EVENT-REPORT  | Mandatory/Mandatory                      |
+-----------------+------------------------------------------+


.. _mpps_statuses:

Statuses
--------

N-CREATE Statuses
~~~~~~~~~~~~~~~~~

+------------+----------+----------------------------------+
| Code (hex) | Category | Description                      |
+============+==========+==================================+
| 0x0000     | Success  | Success                          |
+------------+----------+----------------------------------+
| 0x0105     | Failure  | No such attribute                |
+------------+----------+----------------------------------+
| 0x0106     | Failure  | Invalid attribute value          |
+------------+----------+----------------------------------+
| 0x0107     | Failure  | Attribute list error             |
+------------+----------+----------------------------------+
| 0x0110     | Failure  | Processing failure               |
+------------+----------+----------------------------------+
| 0x0111     | Failure  | Duplicate SOP Instance           |
+------------+----------+----------------------------------+
| 0x0116     | Failure  | Attribute value out of range     |
+------------+----------+----------------------------------+
| 0x0117     | Failure  | Invalid object instance          |
+------------+----------+----------------------------------+
| 0x0118     | Failure  | No such SOP Class                |
+------------+----------+----------------------------------+
| 0x0120     | Failure  | Missing attribute                |
+------------+----------+----------------------------------+
| 0x0121     | Failure  | Missing attribute value          |
+------------+----------+----------------------------------+
| 0x0124     | Failure  | Not authorised                   |
+------------+----------+----------------------------------+
| 0x0210     | Failure  | Duplicate invocation             |
+------------+----------+----------------------------------+
| 0x0211     | Failure  | Unrecognised operation           |
+------------+----------+----------------------------------+
| 0x0212     | Failure  | Mistyped argument                |
+------------+----------+----------------------------------+
| 0x0213     | Failure  | Resource limitation              |
+------------+----------+----------------------------------+

N-EVENT-REPORT Statuses
~~~~~~~~~~~~~~~~~~~~~~~

+------------+----------+----------------------------------+
| Code (hex) | Category | Description                      |
+============+==========+==================================+
| 0x0000     | Success  | Success                          |
+------------+----------+----------------------------------+
| 0x0110     | Failure  | Processing failure               |
+------------+----------+----------------------------------+
| 0x0112     | Failure  | No such SOP Instance             |
+------------+----------+----------------------------------+
| 0x0113     | Failure  | No such event type               |
+------------+----------+----------------------------------+
| 0x0114     | Failure  | No such argument                 |
+------------+----------+----------------------------------+
| 0x0115     | Failure  | Invalid argument value           |
+------------+----------+----------------------------------+
| 0x0117     | Failure  | Invalid object instance          |
+------------+----------+----------------------------------+
| 0x0118     | Failure  | No such SOP Class                |
+------------+----------+----------------------------------+
| 0x0119     | Failure  | Class-Instance conflict          |
+------------+----------+----------------------------------+
| 0x0210     | Failure  | Duplicate invocation             |
+------------+----------+----------------------------------+
| 0x0211     | Failure  | Unrecognised operation           |
+------------+----------+----------------------------------+
| 0x0212     | Failure  | Mistyped argument                |
+------------+----------+----------------------------------+
| 0x0213     | Failure  | Resource limitation              |
+------------+----------+----------------------------------+

N-GET Statuses
~~~~~~~~~~~~~~~

+------------+----------+----------------------------------+
| Code (hex) | Category | Description                      |
+============+==========+==================================+
| 0x0000     | Success  | Success                          |
+------------+----------+----------------------------------+
| 0x0107     | Warning  | SOP Class not supported          |
+------------+----------+----------------------------------+
| 0x0110     | Failure  | Processing failure               |
+------------+----------+----------------------------------+
| 0x0112     | Failure  | No such SOP Instance             |
+------------+----------+----------------------------------+
| 0x0117     | Failure  | Invalid object instance          |
+------------+----------+----------------------------------+
| 0x0118     | Failure  | No such SOP Class                |
+------------+----------+----------------------------------+
| 0x0119     | Failure  | Class-Instance conflict          |
+------------+----------+----------------------------------+
| 0x0122     | Failure  | SOP Class not supported          |
+------------+----------+----------------------------------+
| 0x0124     | Failure  | Not authorised                   |
+------------+----------+----------------------------------+
| 0x0210     | Failure  | Duplicate invocation             |
+------------+----------+----------------------------------+
| 0x0211     | Failure  | Unrecognised operation           |
+------------+----------+----------------------------------+
| 0x0212     | Failure  | Mistyped argument                |
+------------+----------+----------------------------------+
| 0x0213     | Failure  | Resource limitation              |
+------------+----------+----------------------------------+

N-SET Statuses
~~~~~~~~~~~~~~~

+------------+----------+----------------------------------+
| Code (hex) | Category | Description                      |
+============+==========+==================================+
| 0x0000     | Success  | Success                          |
+------------+----------+----------------------------------+
| 0x0105     | Warning  | No such attribute                |
+------------+----------+----------------------------------+
| 0x0106     | Warning  | Invalid attribute value          |
+------------+----------+----------------------------------+
| 0x0110     | Failure  | Processing failure               |
+------------+----------+----------------------------------+
| 0x0112     | Failure  | SOP Instance not recognised      |
+------------+----------+----------------------------------+
| 0x0116     | Failure  | Attribute value out of range     |
+------------+----------+----------------------------------+
| 0x0117     | Failure  | Invalid object instance          |
+------------+----------+----------------------------------+
| 0x0118     | Failure  | No such SOP Class                |
+------------+----------+----------------------------------+
| 0x0119     | Failure  | Class-Instance conflict          |
+------------+----------+----------------------------------+
| 0x0121     | Failure  | Missing attribute value          |
+------------+----------+----------------------------------+
| 0x0124     | Failure  | Not authorised                   |
+------------+----------+----------------------------------+
| 0x0210     | Failure  | Duplicate invocation             |
+------------+----------+----------------------------------+
| 0x0211     | Failure  | Unrecognised operation           |
+------------+----------+----------------------------------+
| 0x0212     | Failure  | Mistyped argument                |
+------------+----------+----------------------------------+
| 0x0213     | Failure  | Resource limitation              |
+------------+----------+----------------------------------+


References
----------

* DICOM Standard, Part 4, `Annex F <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_F>`_
* DICOM Standard, Part 7, Section
  `10.1.1 <http://dicom.nema.org/medical/dicom/current/output/chtml/part07/chapter_9.html#sect_10.1.1>`_
* DICOM Standard, Part 7, Section
  `10.1.2 <http://dicom.nema.org/medical/dicom/current/output/chtml/part07/chapter_9.html#sect_10.1.2>`_
* DICOM Standard, Part 7, Section
  `10.1.3 <http://dicom.nema.org/medical/dicom/current/output/chtml/part07/chapter_9.html#sect_10.1.3>`_
* DICOM Standard, Part 7, Section
  `10.1.5 <http://dicom.nema.org/medical/dicom/current/output/chtml/part07/chapter_9.html#sect_10.1.5>`_
