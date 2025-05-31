=======
findscu
=======

.. versionadded:: 1.5

.. code-block:: text

    $ python -m pynetdicom findscu [options] addr port (-k keyword and/or -f file-in)

Description
===========
The ``findscu`` application implements a Service Class User (SCU) for
the :dcm:`Query/Retrieve<part04/chapter_C.html>` and
:dcm:`Basic Worklist Management<part04/chapter_K.html>` service classes. It
requests an association with a peer Application Entity and once established,
sends a C-FIND query to be matched against the SCP's managed SOP Instances.
The SCP then responds with the matching query keys.

The source code for the application can be found :gh:`here
<pynetdicom/tree/main/pynetdicom/apps/findscu>`

Usage
=====

The following example shows what happens when it is successfully run on
an SCP at IP ``127.0.0.1`` and listen port ``11112`` that supports the
Query/Retrieve (Find) service:

.. code-block:: text

    $ python -m pynetdicom findscu 127.0.0.1 11112 -k QueryRetrieveLevel=PATIENT -k PatientName=
    I: Requesting Association
    I: Association Accepted
    I: Sending Find Request: MsgID 1
    I:
    I: # Request Identifier
    I: (0008,0052) CS [PATIENT]                                # 1 QueryRetrieveLevel
    I: (0010,0010) PN (no value available)                     # 0 PatientName
    I:
    I: Find SCP Response: 1 - 0xFF00 (Pending)
    I:
    I: # Response Identifier
    I: (0008,0052) CS [PATIENT]                                # 1 QueryRetrieveLevel
    I: (0008,0054) AE [QRSCP]                                  # 1 RetrieveAETitle
    I: (0010,0010) PN [CompressedSamples^CT1]                  # 1 PatientName
    I:
    I: Find SCP Result: 0x0000 (Success)
    I: Releasing Association

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
            set maximum receive PDU bytes to n bytes (default: 16382)

Query Information Model Options
-------------------------------
``-P    --patient``
            use patient root information model (default)
``-S    --study``
            use study root information model
``-O    --psonly``
            use patient/study only information model
``-W    --worklist``
            use modality worklist information model
``-U    --ups``
            use unified procedure step pull information model

Query Options
-------------
``-k [k]eyword: (gggg,eeee)=str, keyword=str``
            add or override a query element using either an element tag as
            (group,element) or the element's keyword (such as PatientName).
            See the *keyword pathing* section for more information.
``-f path to [f]ile (str)``
            use a DICOM file as the query dataset, if used with ``-k``
            then the elements will be added to or overwrite those
            present in the file

Extended Negotiation Options
----------------------------
``--relational-query``
            request the use of relational queries (not with ``-W``)
``--dt-matching``
            request the use of date-time matching (not with ``-W``)
``--fuzzy-names``
            request the use of fuzzy semantic matching of person names
``--timezone-adj``
            request the use of timezone query adjustment
``--enhanced-conversion``
            request the use of enhanced multi-frame image conversion (not with
            ``-W``)

Output Options
--------------
``-w    --write``
            write the responses to file as ``rsp000001.dcm``,
            ``rsp000002.dcm``, ...


.. include:: keyword_pathing.rst


DICOM Conformance
=================

The ``findscu`` application supports the Query/Retrieve and Basic Worklist
Management services as an SCU. The following SOP classes are supported:

Query/Retrieve Service
----------------------

SOP Classes
...........

+-----------------------------+-----------------------------------------------+
| UID                         | Transfer Syntax                               |
+=============================+===============================================+
| 1.2.840.10008.5.1.4.1.2.1.1 | Patient Root Query/Retrieve Information Model |
|                             | - FIND                                        |
+-----------------------------+-----------------------------------------------+
| 1.2.840.10008.5.1.4.1.2.2.1 | Study Root Query/Retrieve Information Model   |
|                             | - FIND                                        |
+-----------------------------+-----------------------------------------------+
| 1.2.840.10008.5.1.4.1.2.3.1 | Patient Study Only Query/Retrieve Information |
|                             | - FIND                                        |
+-----------------------------+-----------------------------------------------+


Transfer Syntaxes
.................

+------------------------+----------------------------------------------------+
| UID                    | Transfer Syntax                                    |
+========================+====================================================+
| 1.2.840.10008.1.2      | Implicit VR Little Endian                          |
+------------------------+----------------------------------------------------+
| 1.2.840.10008.1.2.1    | Explicit VR Little Endian                          |
+------------------------+----------------------------------------------------+
| 1.2.840.10008.1.2.1.99 | Deflated Explicit VR Little Endian                 |
+------------------------+----------------------------------------------------+
| 1.2.840.10008.1.2.2    | Explicit VR Big Endian                             |
+------------------------+----------------------------------------------------+

Basic Worklist Management Service
---------------------------------

SOP Classes
...........

+-----------------------------+-----------------------------------------------+
| UID                         | Transfer Syntax                               |
+=============================+===============================================+
| 1.2.840.10008.5.1.4.31      | Modality Worklist Information Model - FIND    |
+-----------------------------+-----------------------------------------------+


Transfer Syntaxes
.................

+------------------------+----------------------------------------------------+
| UID                    | Transfer Syntax                                    |
+========================+====================================================+
| 1.2.840.10008.1.2      | Implicit VR Little Endian                          |
+------------------------+----------------------------------------------------+
| 1.2.840.10008.1.2.1    | Explicit VR Little Endian                          |
+------------------------+----------------------------------------------------+
| 1.2.840.10008.1.2.1.99 | Deflated Explicit VR Little Endian                 |
+------------------------+----------------------------------------------------+
| 1.2.840.10008.1.2.2    | Explicit VR Big Endian                             |
+------------------------+----------------------------------------------------+

Unified Procedure Step  Service
-------------------------------


SOP Classes
...........

+-----------------------------+-----------------------------------------------+
| UID                         | Transfer Syntax                               |
+=============================+===============================================+
| 1.2.840.10008.5.1.4.34.6.3  | UPS Pull Information Model - FIND             |
+-----------------------------+-----------------------------------------------+


Transfer Syntaxes
.................

+------------------------+----------------------------------------------------+
| UID                    | Transfer Syntax                                    |
+========================+====================================================+
| 1.2.840.10008.1.2      | Implicit VR Little Endian                          |
+------------------------+----------------------------------------------------+
| 1.2.840.10008.1.2.1    | Explicit VR Little Endian                          |
+------------------------+----------------------------------------------------+
| 1.2.840.10008.1.2.1.99 | Deflated Explicit VR Little Endian                 |
+------------------------+----------------------------------------------------+
| 1.2.840.10008.1.2.2    | Explicit VR Big Endian                             |
+------------------------+----------------------------------------------------+
