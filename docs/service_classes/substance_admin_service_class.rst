.. _service_subadmin:

Substance Administration Query Service Class
============================================
The :dcm:`Substance Administration Query Service Class<part04/chapter_V.html>`
defines a service that facilitates obtaining information about substances or
devices used in imaging, image-guided treatment and related procedures.


.. _subadm_sops:

Supported SOP Classes
---------------------

+------------------------+-------------------------------------------------+
| UID                    | SOP Class                                       |
+========================+=================================================+
| 1.2.840.10008.5.1.4.41 | ProductCharacteristicsQuery                     |
+------------------------+-------------------------------------------------+
| 1.2.840.10008.5.1.4.42 | SubstanceApprovalQuery                          |
+------------------------+-------------------------------------------------+


DIMSE Services
--------------

+-----------------+-----------------------------------------+
| DIMSE Service   | Usage SCU/SCP                           |
+=================+=========================================+
| C-FIND          | Mandatory/Mandatory                     |
+-----------------+-----------------------------------------+


.. _subadm_statuses:

Statuses
--------

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


Substance Administration Query Service Statuses
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+------------------+----------+----------------------------------------------+
| Code (hex)       | Category | Description                                  |
+==================+==========+==============================================+
| 0xA700           | Failure  | Out of resources                             |
+------------------+----------+----------------------------------------------+
| 0xA900           | Failure  | Identifier does not match SOP Class          |
+------------------+----------+----------------------------------------------+
| 0xC000 to 0xCFFF | Failure  | Unable to process                            |
+------------------+----------+----------------------------------------------+
| 0xFF00           | Pending  | Matches are continuing                       |
+------------------+----------+----------------------------------------------+

pynetdicom Substance Administration Query Statuses
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When pynetdicom is acting as a Substance Administration SCP it uses the
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
