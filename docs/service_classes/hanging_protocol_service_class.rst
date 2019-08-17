.. _service_hangproc:

Hanging Protocol Query/Retrieve Service Class
=======================================================
The :dcm:`Hanging Protocol Query/Retrieve Service Class <part04/chapter_U.html>`
defines a service that facilitates access to Hanging Protocol objects.

Supported SOP Classes
---------------------

.. _hang_sops:

+-----------------------------+-----------------------------------------------+
| UID                         | SOP Class                                     |
+=============================+===============================================+
| 1.2.840.10008.5.1.4.38.2    | HangingProtocolInformationModelFind           |
+-----------------------------+-----------------------------------------------+
| 1.2.840.10008.5.1.4.38.3    | HangingProtocolInformationModelMove           |
+-----------------------------+-----------------------------------------------+
| 1.2.840.10008.5.1.4.38.4    | HangingProtocolInformationModelGet            |
+-----------------------------+-----------------------------------------------+

DIMSE Services
--------------

+-----------------+-----------------------------------------+
| DIMSE Service   | Usage SCU/SCP                           |
+=================+=========================================+
| *Hanging Protocol Information Model - Find*               |
+-----------------+-----------------------------------------+
| C-FIND          | Mandatory/Mandatory                     |
+-----------------+-----------------------------------------+
| *Hanging Protocol Information Model - Move*               |
+-----------------+-----------------------------------------+
| C-MOVE          | Mandatory/Mandatory                     |
+-----------------+-----------------------------------------+
| *Hanging Protocol Information Model - Get*                |
+-----------------+-----------------------------------------+
| C-GET           | Mandatory/Mandatory                     |
+-----------------+-----------------------------------------+


.. _hang_statuses:

Statuses
--------

.. _hang_find_statuses:

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

Hanging Protocol Query/Retrieve (Find) Service Statuses
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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

pynetdicom Hanging Protocol Query/Retrieve (Find) Statuses
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When pynetdicom is acting as a Hanging Protocol Query/Retrieve (Find)
SCP it uses the following status codes values to indicate the corresponding
issue has occurred to help aid in debugging.

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


.. _hang_get_statuses:

C-GET Statuses
~~~~~~~~~~~~~~

+------------+----------+----------------------------------+
| Code (hex) | Category | Description                      |
+============+==========+==================================+
| 0x0000     | Success  | Success                          |
+------------+----------+----------------------------------+
| 0x0122     | Failure  | SOP Class not supported          |
+------------+----------+----------------------------------+
| 0x0124     | Failure  | Not authorised                   |
+------------+----------+----------------------------------+
| 0x0210     | Failure  | Duplicate invocation             |
+------------+----------+----------------------------------+
| 0x0212     | Failure  | Mistyped argument                |
+------------+----------+----------------------------------+
| 0xFE00     | Cancel   | Sub-operations terminated        |
+------------+----------+----------------------------------+

Hanging Protocol Query/Retrieve (Get) Service Statuses
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+------------------+----------+----------------------------------------------+
| Code (hex)       | Category | Description                                  |
+==================+==========+==============================================+
| 0xA701           | Failure  | Out of resources; unable to calculate number |
|                  |          | of matches                                   |
+------------------+----------+----------------------------------------------+
| 0xA702           | Failure  | Out of resources; unable to perform          |
|                  |          | sub-operations                               |
+------------------+----------+----------------------------------------------+
| 0xA900           | Failure  | Dataset does not match SOP Class             |
+------------------+----------+----------------------------------------------+
| 0xB000           | Warning  | Sub-operations complete, one or more         |
|                  |          | or warnings                                  |
+------------------+----------+----------------------------------------------+
| 0xC000 to 0xCFFF | Failure  | Unable to process                            |
+------------------+----------+----------------------------------------------+
| 0xFF00           | Pending  | Sub-operations are continuing                |
+------------------+----------+----------------------------------------------+

pynetdicom Hanging Protocol Query/Retrieve (Get) Statuses
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+------------------+----------+-----------------------------------------------+
| Code (hex)       | Category | Description                                   |
+==================+==========+===============================================+
| 0xC001           | Failure  | Handler bound to ``evt.EVT_C_GET`` yielded a  |
|                  |          | status Dataset with no (0000,0900) *Status*   |
|                  |          | element                                       |
+------------------+----------+-----------------------------------------------+
| 0xC002           | Failure  | Handler bound to ``evt.EVT_C_GET`` yielded an |
|                  |          | invalid status object (not a pydicom Dataset  |
|                  |          | or an int)                                    |
+------------------+----------+-----------------------------------------------+
| 0xC410           | Failure  | Failed to decode the dataset received from    |
|                  |          | the peer                                      |
+------------------+----------+-----------------------------------------------+
| 0xC411           | Failure  | Unhandled exception raised by the handler     |
|                  |          | bound to ``evt.EVT_C_GET``                    |
+------------------+----------+-----------------------------------------------+
| 0xC413           | Failure  | The handler bound to ``evt.EVT_C_GET``        |
|                  |          | yielded an invalid number of sub-operations   |
+------------------+----------+-----------------------------------------------+


.. _hang_move_statuses:

C-MOVE Statuses
~~~~~~~~~~~~~~~

+------------+----------+----------------------------------+
| Code (hex) | Category | Description                      |
+============+==========+==================================+
| 0x0000     | Success  | Success                          |
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
| 0xFE00     | Cancel   | Sub-operations terminated        |
+------------+----------+----------------------------------+

Hanging Protocol Query/Retrieve (Move) Service Statuses
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+------------------+----------+----------------------------------------------+
| Code (hex)       | Category | Description                                  |
+==================+==========+==============================================+
| 0xA701           | Failure  | Out of resources; unable to calculate number |
|                  |          | of matches                                   |
+------------------+----------+----------------------------------------------+
| 0xA702           | Failure  | Out of resources; unable to perform          |
|                  |          | sub-operations                               |
+------------------+----------+----------------------------------------------+
| 0xA801           | Failure  | Move destination unknown                     |
+------------------+----------+----------------------------------------------+
| 0xA900           | Failure  | Dataset does not match SOP Class             |
+------------------+----------+----------------------------------------------+
| 0xB000           | Warning  | Sub-operations complete, one or more         |
|                  |          | or warnings                                  |
+------------------+----------+----------------------------------------------+
| 0xC000 to 0xCFFF | Failure  | Unable to process                            |
+------------------+----------+----------------------------------------------+
| 0xFF00           | Pending  | Sub-operations are continuing                |
+------------------+----------+----------------------------------------------+

pynetdicom Hanging Protocol Query/Retrieve (Move) Statuses
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+------------------+----------+-----------------------------------------------+
| Code (hex)       | Category | Description                                   |
+==================+==========+===============================================+
| 0xC001           | Failure  | Handler bound to ``evt.EVT_C_MOVE`` yielded a |
|                  |          | status Dataset with no (0000,0900) *Status*   |
|                  |          | element                                       |
+------------------+----------+-----------------------------------------------+
| 0xC002           | Failure  | Handler bound to ``evt.EVT_C_MOVE`` yielded an|
|                  |          | invalid status object (not a pydicom Dataset  |
|                  |          | or an int)                                    |
+------------------+----------+-----------------------------------------------+
| 0xC510           | Failure  | Failed to decode the dataset received from    |
|                  |          | the peer                                      |
+------------------+----------+-----------------------------------------------+
| 0xC511           | Failure  | Unhandled exception raised by the handler     |
|                  |          | bound to ``evt.EVT_C_MOVE``                   |
+------------------+----------+-----------------------------------------------+
| 0xC513           | Failure  | The handler bound to ``evt.EVT_C_MOVE``       |
|                  |          | yielded an invalid number of sub-operations   |
+------------------+----------+-----------------------------------------------+
| 0xC514           | Failure  | The handler bound to ``evt.EVT_C_MOVE``       |
|                  |          | failed to yield the (address, port)           |
|                  |          | and/or the number of sub-operations           |
+------------------+----------+-----------------------------------------------+
| 0xC515           | Failure  | The handler bound to ``evt.EVT_C_MOVE``       |
|                  |          | failed to yield a valid (address, port) pair  |
+------------------+----------+-----------------------------------------------+
