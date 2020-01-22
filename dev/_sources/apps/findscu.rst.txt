=======
findscu
=======
    ``findscu.py [options] addr port (-k keyword and/or -f file-in)``

Description
===========
The ``findscu`` application implements a *Service Class User* (SCU) for
the :dcm:`Query/Retrieve Service Class<part04/chapter_C.html>`. It requests an
association with a peer Application Entity on IP address ``addr`` and listen
port ``port`` and once established, sends a query to be matched against the
SCP's managed SOP Instances. The SCP then responds with the matching query
keys.

The following example shows what happens when it is succesfully run on
an SCP at IP 127.0.0.1 and listen port 11112 that supports the *QR Find
Service*:

.. code-block:: text

    user@host: python findscu.py 127.0.0.1 11112 -k QueryRetrieveLevel=PATIENT -k PatientName=
    I: Requesting Association
    I: Association Accepted
    I: Sending Find Request: MsgID 1
    I:
    I: # Request Identifier
    I: (0008, 0052) Query/Retrieve Level                CS: 'PATIENT'
    I: (0010, 0010) Patient's Name                      PN: ''
    I:
    I: Find SCP Response: 1 - 0xFF00 (Pending)
    I:
    I: # Response Identifier
    I: (0008, 0052) Query/Retrieve Level                CS: 'PATIENT'
    I: (0008, 0054) Retrieve AE Title                   AE: 'QRSCP'
    I: (0010, 0010) Patient's Name                      PN: 'CompressedSamples^CT1'
    I:
    I: Find SCP Result: 0x0000 (Success)
    I: Releasing Association
    user@host:

Parameters
==========
``addr``
            TCP/IP address or hostname of DICOM peer
``port``
            TCP/IP port number of peer

Options
=======
General Options
---------------
``-q    --quiet``
            quiet mode, prints no warnings or errors
``-v    --verbose``
            verbose mode, prints processing details
``-d    --debug``
            debug mode, prints debugging information
``-ll   --log-level [l]evel (str)``
            One of [``'critical'``, ``'error'``, ``'warning'``, ``'info'``,
            ``'debug'``], prints logging messages with corresponding level
            or higher
``-lc   --log-config [f]ilename (str)``
            use Python logging `config file
            <https://docs.python.org/3/library/logging.config.html#logging.config.fileConfig>`_
            ``f`` for the logger

Network Options
---------------
``-aet  --calling-aet [a]etitle (str)``
            set the local AE title (default: FINDSCU)
``-aec  --called-aet [a]etitle (str)``
            set the called AE title for the peer AE (default: ANY-SCP)
``-ta   --acse-timeout [s]econds (float)``
            timeout for ACSE messages (default: 30)
``-td   --dimse-timeout [s]econds (float)``
            timeout for DIMSE messages (default: 30)
``-tn   --network-timeout [s]econds (float)``
            timeout for the network (default: 30)
``-pdu  --max-pdu [n]umber of bytes (int)``
            set maximum receive PDU bytes to n bytes (default: 16384)

Query Information Model Options
-------------------------------
``-P    --patient``
            use patient root information model
``-S    --study``
            use study root information model
``-O    --psonly``
            use patient/study only information model
``-W    --worklist``
            use modality worklist information model

Query Options
-------------
``-k [k]eyword: (gggg,eeee)=str, keyword=str``
            add or override a query element using either an element tag as
            (group,element) or the element's keyword (such as PatientName).
            See the *keyword pathing* section for more information.
``-f path to [f]ile``
            use a DICOM file as the query dataset, if used with ``-k``
            then the elements will be added to or overwrite those
            present in the file

Output Options
--------------
``-w    --write``
            write the responses to file as ``rsp000001.dcm``,
            ``rsp000002.dcm``, ...


.. include:: keyword_pathing.rst


DICOM Conformance
=================

The ``findscu`` application supports the following SOP Classes as an SCU:

+-----------------------------+-----------------------------------------------+
| UID                         | Transfer Syntax                               |
+=============================+===============================================+
| 1.2.840.10008.5.1.4.1.2.1.1 | Patient Root Query Retrieve Information Model |
|                             | - FIND                                        |
+-----------------------------+-----------------------------------------------+
| 1.2.840.10008.5.1.4.1.2.2.1 | Study Root Query Retrieve Information Model   |
|                             | - FIND                                        |
+-----------------------------+-----------------------------------------------+
| 1.2.840.10008.5.1.4.1.2.3.1 | Patient Study Only Query Retrieve Information |
|                             | - FIND                                        |
+-----------------------------+-----------------------------------------------+
| 1.2.840.10008.5.1.4.31      | Modality Worklist Information Model - FIND    |
+-----------------------------+-----------------------------------------------+


The application will request presentation contexts using these transfer
syntaxes:

+------------------------+----------------------------------------------------+
| UID                    | Transfer Syntax                                    |
+========================+====================================================+
| 1.2.840.10008.1.2      | Implicit VR Little Endian                          |
+------------------------+----------------------------------------------------+
| 1.2.840.10008.1.2.1    | Explicit VR Little Endian                          |
+------------------------+----------------------------------------------------+
| 1.2.840.10008.1.2.2    | Explicit VR Big Endian                             |
+------------------------+----------------------------------------------------+
