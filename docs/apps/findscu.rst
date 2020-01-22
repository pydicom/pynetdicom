=======
findscu
=======
    ``findscu [options] addr port (-k keyword|-f file-in)``

Description
===========


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
``-ta   --acse-timeout [s]econds (float)``
            timeout for ACSE messages (default: 30)
``-td   --dimse-timeout [s]econdsr (float)``
            timeout for DIMSE messages (default: 30)
``-tn   --network-timeout [s]econdsr (float)``
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
``-k [k]eyword: "(gggg,eeee)=str", "keyword=str"``
            add or override a query element using either an element tag as
            (group,element) or the element's keyword (such as PatientName).
            See the (element pathing) section for more information.
``-f path to [f]ile``
            use a DICOM file as the query dataset, if used with ``-k``
            then the elements will be added to or overwrite those
            present in the file

Output Options
--------------
``-w    --write``
            write the responses to file as ``rsp000001.dcm``,
            ``rsp000002.dcm``, ...


Element pathing
===============
Bluh
