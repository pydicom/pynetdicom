.. _display_service:

Display System Management Service Class
=======================================
The `Display System Management Service Class <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_EE>`_
defines a service that facilitates access to Display System objects.

Supported SOP Classes
---------------------

.. _display_sops:

+-----------------------------+-----------------------------------------------+
| UID                         | SOP Class                                     |
+=============================+===============================================+
| 1.2.840.10008.5.1.1.40      | DisplaySystemSOPClass                         |
+-----------------------------+-----------------------------------------------+


DIMSE Services
--------------

+-----------------+-----------------------------------------+
| DIMSE Service   | Usage SCU/SCP                           |
+=================+=========================================+
| N-GET           | Mandatory/Mandatory                     |
+-----------------+-----------------------------------------+


.. _display_statuses:

Statuses
--------

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
| 0x0122     | Failure  | SOP class not supported          |
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

* DICOM Standard, Part 4, `Annex EE <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_EE>`_
* DICOM Standard, Part 7, Sections
  `10.1.2 <http://dicom.nema.org/medical/dicom/current/output/chtml/part07/chapter_9.html#sect_10.1.2>`_
