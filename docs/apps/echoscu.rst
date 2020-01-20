=======
echoscu
=======
    ``echoscu [options] addr port``

Description
===========
The ``echoscu`` application implements a Service Class User (SCU) for the
*Verification SOP Class* (UID 1.2.840.10008.1.1). It establishes an Association
with a peer Application Entity (AE) which it then sends a DICOM C-ECHO-RQ
message and waits for a response. The application can be used to verify
basic DICOM connectivity.

The following simple example shows what happens when it is succesfully run on
an SCP that supports the *Verification SOP Class*:

.. code-block:: text

    user@host: echoscu 127.0.0.1 11112
    user@host:

When attempting to send a C-ECHO to an SCP that doesn't support the
*Verification SOP Class*:

.. code-block:: text

    user@host: echoscu 127.0.0.1 11112
    E: No Acceptable Presentation Contexts
    user@host:

When attempting to associate with a non-DICOM peer:

.. code-block:: text

    user@host: echoscu 127.0.0.1 11112
    E: Association Request Failed: Failed to establish association
    E: Peer aborted Association (or never connected)
    E: TCP Initialisation Error: Connection refused
    user@host:

More information is available with the ``-d`` flag:

.. code-block:: text

    D: echoscu.py v0.7.0
    D:
    I: Requesting Association
    D: Request Parameters:
    D: ========================= BEGIN A-ASSOCIATE-RQ PDU =========================
    ...
    D: ========================== END A-ASSOCIATE-AC PDU ==========================
    I: Association Accepted
    I: Sending Echo Request: MsgID 1
    D: pydicom.read_dataset() TransferSyntax="Little Endian Implicit"
    I: Received Echo Response (Status: Success)
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
            use Python logging config file f for the logger

Network Options
---------------
``-aet  --calling-aet [a]etitle (str)``
            set the local AE title (default: ECHOSCU)
``-aec  --called-aet [a]etitle (str)``
            set the called AE title for the peer AE (default: ANY-SCP)
``-ta   --acse-timeout [s]econds (int)``
            timeout for ACSE messages (default: 30)
``-td   --dimse-timeout [s]econdsr (int)``
            timeout for DIMSE messages (default: 30)
``-tn   --network-timeout [s]econdsr (int)``
            timeout for the network (default: 30)
``-pdu  --max-pdu [n]umber of bytes (int)``
            set maximum receive PDU bytes to n bytes (default: 16384)

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
``--repeat [n]umber (int)``
            repeat echo request n times
``--abort``
            abort association instead of releasing it


DICOM Conformance
=================
The echoscu application supports the following SOP Class as an SCU:

+------------------------+----------------------------------------------------+
| UID                    | SOP Class                                          |
+========================+====================================================+
|1.2.840.10008.1.1       | Verification SOP Class                             |
+------------------------+----------------------------------------------------+

The supported Transfer Syntaxes are:

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
