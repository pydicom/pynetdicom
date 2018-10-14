========
storescu
========
    ``storescu [options] addr port dcmfile``

Description
===========
The ``storescu`` application implements a *Service Class User* (SCU) for
the *Storage Service Class* [#]_. It requests an association with a peer
Application Entity on IP address ``addr`` and ``port`` and, once an
Association is established, requests the transfer of the Storage SOP Instance
in ``dcmfile``.

The following simple example shows what happens when it is succesfully run on
a Storage SCP:
::

    user@host: storescu 127.0.0.1 11112 path/to/file
    user@host:

When attempting to use the Storage Service for a unsupported SOP Class:
::

    user@host: storescu 127.0.0.1 11112 path/to/file
    E: No Acceptable Presentation Contexts
    user@host:

More information is available with the ``-d`` flag:
::

    user@host: storescu 127.0.0.1 11112 path/to/file -d
    D: $storescu.py v0.1.3
    D:
    D: Checking input file
    I: Requesting Association
    D: Request Parameters:
    D: ====================== BEGIN A-ASSOCIATE-RQ =====================
    ...
    D: ======================= END A-ASSOCIATE-AC ======================
    I: Association Accepted
    I: Sending file: CTImageStorage.dcm
    I: Sending Store Request: MsgID 1, (CT)
    D: ===================== OUTGOING DIMSE MESSAGE ====================
    D: Message Type                  : C-STORE RQ
    D: Message ID                    : 1
    D: Affected SOP Class UID        : 1.2.840.10008.5.1.4.1.1.2
    D: Affected SOP Instance UID     : 1.2.3.4.5.6
    D: Data Set                      : Present
    D: Priority                      : Low
    D: ======================= END DIMSE MESSAGE =======================
    D: pydicom.read_dataset() TransferSyntax="Little Endian Implicit"
    I: Received Store Reponse
    D: ===================== INCOMING DIMSE MESSAGE ====================
    D: Message Type                  : C-STORE RSP
    D: Presentation Context ID       : 15
    D: Message ID Being Responded To : 1
    D: Affected SOP Class UID        : 1.2.840.10008.5.1.4.1.1.2
    D: Affected SOP Instance UID     : 1.2.3.4.5.6
    D: Data Set                      : None
    D: DIMSE Status                  : 0x0000 - Success
    D: ======================= END DIMSE MESSAGE =======================
    I: Releasing Association
    user@host:

Options
=======
Logging
-------
    ``-q    --quiet``
              quiet mode, prints no warnings or errors
    ``-v    --verbose``
              verbose mode, prints processing details
    ``-d    --debug``
              debug mode, prints debugging information
    ``-ll   --log-level [l]evel (str)``
              One of ['critical', 'error', 'warning', 'info', 'debug'], prints
              logging messages with corresponding level or higher
    ``-lc   --log-config [f]ilename (str)``
              use python logging config [#]_ file f for the logger

Application Entity Titles
-------------------------
    ``-aet  --calling-aet [a]etitle (str)``
              set the local AE title (default: ECHOSCU)
    ``-aec  --called-aet [a]etitle (str)``
              set the called AE title for the peer AE (default: ANY-SCP)

Association Negotiation Debugging
---------------------------------
    ``-pts  --propose-ts [n]umber (int)``
              propose n transfer syntaxes (1-3)

Miscellaneous DICOM
-------------------
    ``-to   --timeout [s]econds (int)``
              timeout for connection requests (default: unlimited)
    ``-ta   --acse-timeout [s]econds (int)``
              timeout for ACSE messages (default: 30)
    ``-td   --dimse-timeout [s]econds (int)``
              timeout for DIMSE messages (default: unlimited)
    ``-pdu  --max-pdu [n]umber of bytes (int)``
              set maximum receive PDU bytes to n bytes (default: 16384)
    ``--repeat [n]umber (int)``
        repeat echo n times
    ``--abort``
        abort association instead of releasing it


DICOM Conformance
=================
The storescu application supports the following SOP Class as an SCU:

+------------------+------------------------+
| UID              | SOP Class              |
+==================+========================+
|1.2.840.10008.1.1 | Verification SOP Class |
+------------------+------------------------+

Unless the ``--propose-ts`` option is used, the storescu application will only
propose the *Little Endian Implicit VR Transfer Syntax* (UID 1.2.840.10008.1.2).
The supported Transfer Syntaxes [#]_ are:

+--------------------+---------------------------+
| UID                | Transfer Syntax           |
+====================+===========================+
|1.2.840.10008.1.2   | Little Endian Implicit VR |
+--------------------+---------------------------+
|1.2.840.10008.1.2.1 | Little Endian Explicit VR |
+--------------------+---------------------------+
|1.2.840.10008.1.2.2 | Big Endian Explicit VR    |
+--------------------+---------------------------+

.. rubric:: Footnotes

.. [#] DICOM Standard, Part 6, Table A-1
.. [#] DICOM Standard, Part 7, Sections 9.1.5 and 9.3.5
.. [#] DICOM Standard, Part 8, Sections 7.1.1.13 and 9.3.2.2
