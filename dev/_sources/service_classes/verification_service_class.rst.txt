.. _service_verify:

Verification Service Class
==========================
The :dcm:`Verification Service Class <part04/chapter_A.html>`
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
| 1.2.840.10008.1.1 | Verification              |
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
