Basic Worklist Management Service Class
=======================================
The `Basic Worklist Management Service Class <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_K>`_
defines a service that facilitates
access to worklists, where a worklist is a structure that presents information
related to a particular set of tasks and the particular details of each task.

.. _worklist_sops:

Supported SOP Classes
---------------------

+-----------------------------+-----------------------------------------------+
| UID                         | SOP Class                                     |
+=============================+===============================================+
| 1.2.840.10008.5.1.4.31      | ModalityWorklistInformationFind               |
+-----------------------------+-----------------------------------------------+

Statuses
--------

.. _worklist_statuses:

C-FIND Statuses
~~~~~~~~~~~~~~~~

+------------+----------+----------------------------------+
| Code (hex) | Category | Description                      |
+============+==========+==================================+
| 0x0000     | Success  | Success                          |
+------------+----------+----------------------------------+
| 0x0122     | Failure  | SOP Class not supported          |
+------------+----------+----------------------------------+
| 0xFE00     | Cancel   | Processing has been terminated   |
+------------+----------+----------------------------------+

Basic Worklist Management Service Statuses
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+------------------+----------+----------------------------------------------+
| Code (hex)       | Category | Description                                  |
+==================+==========+==============================================+
| 0xA700           | Failure  | Out of resources                             |
+------------------+----------+----------------------------------------------+
| 0xA900           | Failure  | Dataset does not match SOP Class             |
+------------------+----------+----------------------------------------------+
| 0xC000 to 0xCFFF | Failure  | Unable to process                            |
+------------------+----------+----------------------------------------------+
| 0xFF00           | Pending  | Matches are continuing                       |
+------------------+----------+----------------------------------------------+
| 0xFF01           | Pending  | Matches are continuing; one or more Optional |
|                  |          | keys was not supported                       |
+------------------+----------+----------------------------------------------+

References
----------

* DICOM Standard, Part 4, `Annex K <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_K>`_
* DICOM Standard, Part 7, Sections
  `9.1.2.1.5 <http://dicom.nema.org/medical/dicom/current/output/chtml/part07/chapter_9.html#sect_9.1.2.1.5>`_,
