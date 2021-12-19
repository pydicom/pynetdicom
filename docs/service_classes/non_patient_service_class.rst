.. _service_nonpat:

Non-Patient Object Storage Service Class
========================================
The :dcm:`Non-Patient Object Storage Service Class <part04/chapter_GG.html>`
defines a service that facilitates the transfer of non-patient related
information to another AE.

.. _nonpat_sops:

Supported SOP Classes
---------------------

+-------------------------------+-------------------------------------+
| UID                           | SOP Class                           |
+===============================+=====================================+
| 1.2.840.10008.5.1.4.38.1      | HangingProtocolStorage              |
+-------------------------------+-------------------------------------+
| 1.2.840.10008.5.1.4.39.1      | ColorPaletteStorage                 |
+-------------------------------+-------------------------------------+
| 1.2.840.10008.5.1.4.43.1      | GenericImplantTemplateStorage       |
+-------------------------------+-------------------------------------+
| 1.2.840.10008.5.1.4.44.1      | ImplantAssemblyTemplateStorage      |
+-------------------------------+-------------------------------------+
| 1.2.840.10008.5.1.4.45.1      | ImplantTemplateGroupStorage         |
+-------------------------------+-------------------------------------+
| 1.2.840.10008.5.1.4.1.1.200.1 | CTDefinedProcedureProtocolStorage   |
+-------------------------------+-------------------------------------+
| 1.2.840.10008.5.1.4.1.1.200.3 | ProtocolApprovalStorage             |
+-------------------------------+-------------------------------------+
| 1.2.840.10008.5.1.4.1.1.200.7 | XADefinedProcedureProtocolStorage   |
+-------------------------------+-------------------------------------+

DIMSE Services
--------------

+-----------------+-----------------------------------------+
| DIMSE Service   | Usage SCU/SCP                           |
+=================+=========================================+
| C-STORE         | Mandatory/Mandatory                     |
+-----------------+-----------------------------------------+

.. _nonpat_statuses:

Statuses
--------

C-STORE Statuses
~~~~~~~~~~~~~~~~

+------------+----------+----------------------------------+
| Code (hex) | Category | Description                      |
+============+==========+==================================+
| 0x0000     | Success  | Success                          |
+------------+----------+----------------------------------+
| 0x0117     | Failure  | Invalid object instance          |
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

Non-Patient Object Storage Service Statuses
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+------------------+----------+----------------------------------+
| Code (hex)       | Category | Description                      |
+==================+==========+==================================+
| 0xA700           | Failure  | Out of resources                 |
+------------------+----------+----------------------------------+
| 0xA900           | Failure  | Dataset doesn't match SOP Class  |
+------------------+----------+----------------------------------+
| 0xC000           | Failure  | Cannot understand                |
+------------------+----------+----------------------------------+

pynetdicom Statuses
~~~~~~~~~~~~~~~~~~~

When pynetdicom is acting as a Non-Patient Object Storage SCP it uses the
following status codes values to indicate the corresponding issue has
occurred to help aid in debugging.

+------------------+----------+-----------------------------------------------+
| Code (hex)       | Category | Description                                   |
+==================+==========+===============================================+
| 0xC001           | Failure  | Handler bound to ``evt.EVT_C_STORE`` returned |
|                  |          | a status Dataset with no (0000,0900) *Status* |
|                  |          | element                                       |
+------------------+----------+-----------------------------------------------+
| 0xC002           | Failure  | Handler bound to ``evt.EVT_C_STORE`` returned |
|                  |          | an invalid status object (not a pydicom       |
|                  |          | Dataset or an int)                            |
+------------------+----------+-----------------------------------------------+
| 0xC210           | Failure  | Failed to decode the dataset received from    |
|                  |          | the peer                                      |
+------------------+----------+-----------------------------------------------+
| 0xC211           | Failure  | Unhandled exception raised by the handler     |
|                  |          | bound to ``evt.EVT_C_STORE``                  |
+------------------+----------+-----------------------------------------------+
