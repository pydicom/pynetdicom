.. _service_bwm:

Basic Worklist Management Service Class
=======================================
The :dcm:`Basic Worklist Management Service Class <part04/chapter_K.html>`
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

DIMSE Services
--------------

+-----------------+----------------------------+
| DIMSE Service   | Usage SCU/SCP              |
+=================+============================+
| C-FIND          | Mandatory/Mandatory        |
+-----------------+----------------------------+


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
| 0xA900           | Failure  | Data Set does not match SOP Class            |
+------------------+----------+----------------------------------------------+
| 0xC000 to 0xCFFF | Failure  | Unable to process                            |
+------------------+----------+----------------------------------------------+
| 0xFF00           | Pending  | Matches are continuing                       |
+------------------+----------+----------------------------------------------+
| 0xFF01           | Pending  | Matches are continuing; one or more Optional |
|                  |          | keys was not supported                       |
+------------------+----------+----------------------------------------------+

pynetdicom Basic Worklist Management Statuses
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When pynetdicom is acting as a Basic Worklist Management SCP it uses the
following status codes values to indicate the corresponding issue has occurred
to help aid in debugging.

+------------------+----------+-----------------------------------------------+
| Code (hex)       | Category | Description                                   |
+==================+==========+===============================================+
| 0xC001           | Failure  | Handler bound to ``evt.EVT_C_FIND`` yielded a |
|                  |          | status Dataset with no (0000,0900) *Status*   |
|                  |          | element                                       |
+------------------+----------+-----------------------------------------------+
| 0xC002           | Failure  | Handler bound to ``evt.EVT_C_FIND`` yielded an|
|                  |          | invalid status object (not a pydicom Dataset  |
|                  |          | or an int)                                    |
+------------------+----------+-----------------------------------------------+
| 0xC310           | Failure  | Failed to decode the dataset received from    |
|                  |          | the peer                                      |
+------------------+----------+-----------------------------------------------+
| 0xC311           | Failure  | Unhandled exception raised by the handler     |
|                  |          | bound to ``evt.EVT_C_FIND``                   |
+------------------+----------+-----------------------------------------------+
| 0xC312           | Failure  | Failed to encode the dataset received from    |
|                  |          | the handler bound to ``evt.EVT_C_FIND``       |
+------------------+----------+-----------------------------------------------+
