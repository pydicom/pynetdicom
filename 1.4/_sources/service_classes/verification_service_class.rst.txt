Verification Service Class
==========================
The `Verification Service Class <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_A>`_
defines a service that verifies application
level communication between peer DICOM Application Entities. This
verification is accomplished on an established association using the C-ECHO
DIMSE-C service.

.. _verification_sops:

Supported SOP Classes
---------------------

+-------------------+---------------------------+
| UID               | SOP Class                 |
+===================+===========================+
| 1.2.840.10008.1.1 | VerificationSOPClass      |
+-------------------+---------------------------+


DIMSE Services
--------------

+-----------------+----------------------------+
| DIMSE Service   | Usage SCU/SCP              |
+=================+============================+
| C-ECHO          | Mandatory/Mandatory        |
+-----------------+----------------------------+


.. _verification_statuses:

Statuses
--------

C-ECHO Statuses
~~~~~~~~~~~~~~~

+------------+----------+----------------------------------+
| Code (hex) | Category | Description                      |
+============+==========+==================================+
| 0x0000     | Success  | Success                          |
+------------+----------+----------------------------------+
| 0x0122     | Failure  | Refused: SOP Class not supported |
+------------+----------+----------------------------------+
| 0x0210     | Failure  | Duplicate invocation             |
+------------+----------+----------------------------------+
| 0x0211     | Failure  | Unrecognised operation           |
+------------+----------+----------------------------------+
| 0x0212     | Failure  | Mistyped argument                |
+------------+----------+----------------------------------+


References
----------

* DICOM Standard, Part 4, `Annex A <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_A>`_
* DICOM Standard, Part 7, `Section 9.1.5.1.4 <http://dicom.nema.org/medical/dicom/current/output/chtml/part07/chapter_9.html#sect_9.1.5.1.4>`_
