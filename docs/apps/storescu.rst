========
storescu
========

Description
===========
The ``storescu`` application implements a *Service Class User* (SCU) for
the :dcm:`Storage Service Class<part04/chapter_B.html>`. It requests an
association with a peer Application Entity on IP address ``addr`` and listen
port ``port`` and once established requests the transfer
of the SOP Instance in ``dcmfile-in``.

Invocation
==========

If you've invoking ``storescu`` from source then use:

.. code-block:: text

    $ python storescu.py [options] addr port dcmfile-in

Alternatively, it can be invoked with:

.. code-block:: text

    $ python -m pynetdicom storescu [options] addr port dcmfile-in

Usage
=====

The following example shows what happens when it is succesfully run on
an SCP at IP 127.0.0.1 and listen port 11112 that supports the *Storage
Service*:

.. code-block:: text

    $ python storescu.py 127.0.0.1 11112 path/to/file
    $

When attempting to use the SCP with an unsupported SOP Class:

.. code-block:: text

    $ python storescu.py 127.0.0.1 11112 path/to/file
    E: No accepted presentation contexts
    $

More information is available with the ``-d`` flag:

.. code-block:: text

    $ python storescu.py 127.0.0.1 11112 path/to/file -d
    D: storescu.py v0.3.0
    D:
    D: Checking input file
    I: Requesting Association
    D: Request Parameters:
    D: ========================= BEGIN A-ASSOCIATE-RQ PDU =========================
    ...
    D: ========================== END A-ASSOCIATE-AC PDU ==========================
    I: Association Accepted
    I: Sending file: CTImageStorage.dcm
    I: Sending Store Request: MsgID 1, (CT)
    D: ========================== OUTGOING DIMSE MESSAGE ==========================
    D: Message Type                  : C-STORE RQ
    D: Message ID                    : 1
    D: Affected SOP Class UID        : CT Image Storage
    D: Affected SOP Instance UID     : 1.3.6.1.4.1.5962.1.1.1.1.1.20040119072730.12322
    D: Data Set                      : Present
    D: Priority                      : Low
    D: ============================ END DIMSE MESSAGE =============================
    D: pydicom.read_dataset() TransferSyntax="Little Endian Implicit"
    I: Received Store Response (Status: 0x0000 - Success)
    D: ========================== INCOMING DIMSE MESSAGE ==========================
    D: Message Type                  : C-STORE RSP
    D: Presentation Context ID       : 73
    D: Message ID Being Responded To : 1
    D: Affected SOP Class UID        : CT Image Storage
    D: Affected SOP Instance UID     : 1.3.6.1.4.1.5962.1.1.1.1.1.20040119072730.12322
    D: Status                        : 0x0000 - Success
    D: ============================ END DIMSE MESSAGE =============================
    I: Releasing Association
    $

Parameters
==========
``addr``
            TCP/IP address or hostname of DICOM peer
``port``
            TCP/IP port number of peer
``dcmfile-in``
            DICOM file to be transmitted

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
            set the local AE title (default: STORESCU)
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

Transfer Syntax Options
-----------------------
``-xe   --request-little``
            request explicit VR little endian TS only
``-xb   --request-big``
            request explicit VR big endian TS only
``-xi   --request-implicit``
            request implicit VR little endian TS only


Miscellaneous Options
---------------------
``-cx   --single-context``
            only request a single presentation context that matches the input
            DICOM file


DICOM Conformance
=================
The storescu application supports all of the *Storage Service Class'* supported
SOP Classes as SCU.

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
| 1.2.840.10008.1.2.1.99 | Deflated Explicit VR Little Endian                 |
+------------------------+----------------------------------------------------+
