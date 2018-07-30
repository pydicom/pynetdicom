========
storescp
========
    ``storescp [options] port``

Description
===========
The ``storescp`` application implements a *Service Class Provider* (SCP) for
the *Storage Service Class* [#]_. It listens on the specified port for
Association requests from peer Application Entities (AEs) and, once an
Association is established, allows Storage SCUs transfer SOP Instances
with SOP Classes matching the presentation contexts accepted during Association
negotation.

The following example shows what happens when it is started and receives
a C-STORE request from a peer:

::

   user@host: storescp 11112


More information is available when a connection is received while running with
the ``-v`` option:

::

    user@host: storescp 11112 -v
    I: Association Received
    I: Association Accepted
    I: Received Store Requeset
    I: Storing DICOM file: CT.1.2.3.4.5.6
    I: Association Released

Much more information is available when a connection is received while
running with the ``-d`` option:

::

    user@host: storescp 11112 -d
    D: $storescp.py v0.3.2
    D:
    I: Association Received
    D: Request Parameters:
    D: ====================== BEGIN A-ASSOCIATE-RQ =====================
    ...
    D: ======================= END A-ASSOCIATE-AC ======================
    D: pydicom.read_dataset() TransferSyntax="Little Endian Implicit"
    I: Received Store Request
    D: ===================== INCOMING DIMSE MESSAGE ====================
    D: Message Type                  : C-STORE RQ
    D: Presentation Context ID       : 41
    D: Message ID                    : 1
    D: Affected SOP Class UID        : 1.2.840.10008.5.1.4.1.1.2
    D: Affected SOP Instance UID     : 1.2.3.4.5.6
    D: Data Set                      : Present
    D: Priority                      : Low
    D: ======================= END DIMSE MESSAGE =======================
    D: pydicom.read_dataset() TransferSyntax="Little Endian Explicit"
    I: Storing DICOM file: CT.1.2.3.4.5.6
    I: Association Released

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

Application Entity Titles
-------------------------
    ``-aet  --aetitle [a]etitle (str)``
              set my AE title (default: STORESCP)

Miscellaneous DICOM
-------------------
    ``-to   --timeout [s]econds (int)``
              timeout for connection requests (default: unlimited)
    ``-ta   --acse-timeout [s]econds (int)``
              timeout for ACSE messages (default: 30)
    ``-td   --dimse-timeout [s]econdsr (int)``
              timeout for DIMSE messages (default: unlimited)
    ``-pdu  --max-pdu [n]umber of bytes (int)``
              set maximum receive PDU bytes to n bytes (default: 16384)
    ``      --ignore``
              receive data but don't store it

Preferred Transfer Syntaxes
---------------------------
    ``-x=   --prefer-uncompr``
              prefer explicit VR local byte order (default)
    ``-xe   --prefer-little``
              prefer explicit VR little endian transfer syntax
    ``-xb   --prefer-big``
              prefer explicit VR big endian transfer syntax
    ``-xi   --implicit``
              accept implicit VR little endian transfer syntax only

Output
------
    ``-od   --output-directory [d]irectory (str)``
              write received objects to existing directory d


DICOM Conformance
=================
The ``storescp`` application supports the following SOP Class as an SCP:

+------------------+------------------------+
| UID              | SOP Class              |
+==================+========================+
|1.2.840.10008.1.1 | Verification SOP Class |
+------------------+------------------------+

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
.. [#] `The Python documentation <https://docs.python.org/3.5/library/logging.config.html#logging-config-fileformat>`_
.. [#] DICOM Standard, Part 5, Section 10 and Annex A
