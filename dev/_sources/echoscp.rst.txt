=======
echoscp
=======
    ``echoscp [options] port``

Description
===========
The ``echoscp`` application implements a Service Class Provider (SCP) for the
*Verification SOP Class* (UID 1.2.840.10008.1.1) [#]_. It establishes an
Association with peer Application Entities (AEs) and receives DICOM C-ECHO-RQ
[#]_ message to which it responds with a DICOM C-ECHO-RSP message. The
application can be used to verify basic DICOM connectivity.

The following example shows what happens when it is started and receives
a C-ECHO from a peer:
::
    
   user@host: echoscp 11112


More information is available when a connection is received while running with
the ``-v`` option:
::
   
    user@host: echoscp 11112 -v
    I: Association Received
    I: Association Acknowledged
    I: Received Echo Request (MsgID 1)
    I: Association Released

When a peer AE attempts to send non C-ECHO message:
::
   
    user@host: echoscu 192.168.2.1 11112 -v
    I: Association Received
    I: Association Acknowledged
    I: Association Aborted

Much more information is available when a connection is received while
running with the ``-d`` option:
::
   
    user@host: echoscp 11112 -d
    D: $echosco.py v0.2.0 2016-03-15 $
    D:
    D: Starting DICOM UL service "Thread-1"
    D: PDU Type: Associate Request, PDU Length: 215 + 6 bytes PDU header
    D:     01 00 00 00 00 d1 00 01 00 00 41 4e 59 2d 53 43
    ...
    D: Request Parameters:
    D: ====================== BEGIN A-ASSOCIATE-RQ =============================
    D: Their Implementation Class UID: 1.2.826.0.1.3680043.9.381.0.9.0
    ...
    I: Received Echo Request (MsgID 1)
    ...
    I: Association Released
    D: DICOM UL service "Thread-1" stopped


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
              logging messages with corresponding level l or higher
    ``-lc   --log-config [f]ilename (str)``
              use python logging config [#]_ file f for the logger

Application Entity Titles
-------------------------
    ``-aet  --aetitle [a]etitle (str)``
              set my AE title (default: ECHOSCP)

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

DICOM Conformance
=================
The ``echoscp`` application supports the following SOP Class as an SCP:
::
   
    Verification SOP Class          1.2.840.10008.1.1

The supported Transfer Syntaxes [#]_ are:
::
   
    Little Endian Implicit VR       1.2.840.10008.1.2
    Little Endian Explicit VR       1.2.840.10008.1.2.1
    Big Endian Explicit VR          1.2.840.10008.1.2.2

.. rubric:: Footnotes

.. [#] See DICOM Standard 2015b PS3.6 Table A-1
.. [#] See DICOM Standard 2015b PS3.7 Sections 9.1.5 and 9.3.5
.. [#] See DICOM Standard 2015b PS3.8 Sections 7.1.1.13 and 9.3.2.2
.. [#] See `the Python documentation <https://docs.python.org/3.5/library/logging.config.html#logging-config-fileformat>`_
.. [#] See DICOM Standard 2015b PS3.5 Section 10 and Annex A
