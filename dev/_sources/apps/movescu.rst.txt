=======
movescu
=======

.. versionadded:: 1.5

.. code-block:: text

    $ python -m pynetdicom movescu [options] addr port (-k keyword and/or -f file-in)

Description
===========
The ``movescu`` application implements a Service Class User (SCU) for
the :dcm:`Query/Retrieve<part04/chapter_C.html>` service class and optionally
a Service Class Provider (SCP) for the :dcm:`Storage<part04/chapter_B.html>`
service class. It requests an association with a peer Application Entity and
once established, sends a C-MOVE query to be matched against
the Query/Retrieve SCP's managed SOP Instances. The QR SCP then responds by
sending a copy of the matching SOP Instances to the Storage SCP specified
using the C-MOVE query's *Move Destination* AE title.

The source code for the application can be found :gh:`here
<pynetdicom/tree/main/pynetdicom/apps/movescu>`

Usage
=====

The following example shows what happens when it is successfully run on
an SCP at IP ``127.0.0.1`` and listen port ``11112`` that supports the
Query/Retrieve service with the default *Move Destination* AE title
``STORESCP``:

.. code-block:: text

    $ python -m pynetdicom movescu 127.0.0.1 11112 -k QueryRetrieveLevel=PATIENT -k PatientName=
    I: Requesting Association
    I: Association Accepted
    I: Sending Move Request: MsgID 1
    I:
    I: # Request Identifier
    I: (0008,0052) CS [PATIENT]                                # 1 QueryRetrieveLevel
    I: (0010,0010) PN (no value available)                     # 0 PatientName
    I:
    I: Move SCP Response: 1 - 0xFF00 (Pending)
    I: Sub-Operations Remaining: 0, Completed: 1, Failed: 0, Warning: 0
    I: Move SCP Result: 0x0000 (Success)
    I: Sub-Operations Remaining: 0, Completed: 1, Failed: 0, Warning: 0
    I: Releasing Association

The *Move Destination* AE title can be specified using the ``-aem aetitle``
flag.

You can also use the ``--store`` option to start a Storage SCP on port
``11113`` that can be used as the move destination. The AE title and port of
the Storage SCP can be configured using the ``--store-aet`` and
``--store-port`` flags:

.. code-block:: text

    $ python -m pynetdicom movescu 127.0.0.1 11112 -k QueryRetrieveLevel=PATIENT -k PatientName= --store
    I: Requesting Association
    I: Association Accepted
    I: Sending Move Request: MsgID 1
    I:
    I: # Request Identifier
    I: (0008,0052) CS [PATIENT]                                # 1 QueryRetrieveLevel
    I: (0010,0010) PN (no value available)                     # 0 PatientName
    I:
    I: Accepting Association
    I: Received Store Request
    I: Storing DICOM file: CT.1.3.6.1.4.1.5962.1.1.1.1.1.20040119072730.12322
    I: Association Released
    I: Move SCP Response: 1 - 0xFF00 (Pending)
    I: Sub-Operations Remaining: 0, Completed: 1, Failed: 0, Warning: 0
    I: Move SCP Result: 0x0000 (Success)
    I: Sub-Operations Remaining: 0, Completed: 1, Failed: 0, Warning: 0
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
            set the local AE title (default: MOVESCU)
``-aec  --called-aet [a]etitle (str)``
            set the called AE title for the peer AE (default: ANY-SCP)
``-aem  --move-aet [a]etitle (str)``
            set the move destination AE title (default: STORESCP)
``-ta   --acse-timeout [s]econds (float)``
            timeout for ACSE messages (default: 30)
``-td   --dimse-timeout [s]econds (float)``
            timeout for DIMSE messages (default: 30)
``-tn   --network-timeout [s]econds (float)``
            timeout for the network (default: 30)
``-pdu  --max-pdu [n]umber of bytes (int)``
            set maximum receive PDU bytes to n bytes (default: 16382)

Storage SCP Options
-------------------
``--store``
            start a Storage SCP that can be used as the move destination
``--store-port [p]ort (int)``
            the listen port number to use for the Storage SCP (default: 11113)
``--store-aet [a]etitle (str)``
            the AE title to use for the Storage SCP (default: STORESCP)


Query Information Model Options
-------------------------------
``-P    --patient``
            use patient root information model (default)
``-S    --study``
            use study root information model
``-O    --psonly``
            use patient/study only information model

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
``--relational-retrieval``
            request the use of relational retrieval
``--enhanced-conversion``
            request the use of enhanced multi-frame image conversion

Output Options
--------------
``-od [d]irectory, --output-directory [d]irectory (str)``
            write received objects to directory ``d`` (with ``--store``)
``--ignore``
            receive data but don't store it (with ``--store``)


.. include:: keyword_pathing.rst


DICOM Conformance
=================

The ``movescu`` application supports the Query/Retrieve service classes as an
SCU and the Storage service as an SCP (with the ``--store`` option). The
following SOP classes are supported:

Query/Retrieve Service
----------------------

SOP Classes
...........

+-----------------------------+-----------------------------------------------+
| UID                         | Transfer Syntax                               |
+=============================+===============================================+
| 1.2.840.10008.5.1.4.1.2.1.2 | Patient Root Query/Retrieve Information Model |
|                             | - MOVE                                        |
+-----------------------------+-----------------------------------------------+
| 1.2.840.10008.5.1.4.1.2.2.2 | Study Root Query/Retrieve Information Model   |
|                             | - MOVE                                        |
+-----------------------------+-----------------------------------------------+
| 1.2.840.10008.5.1.4.1.2.3.2 | Patient Study Only Query/Retrieve Information |
|                             | - MOVE                                        |
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

Storage Service
---------------

SOP Classes
...........

+----------------------------------+------------------------------------------+
| UID                              | SOP Class                                |
+==================================+==========================================+
| 1.2.840.10008.5.1.4.1.1.1        | Computed Radiography Image Storage       |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.1.1      | Digital X-Ray Image Storage              |
|                                  | - For Presentation                       |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.1.1.1.1  | Digital X-Ray Image Storage              |
|                                  | - For Processing                         |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.1.2      | Digital Mammography X-Ray Image Storage  |
|                                  | - For Presentation                       |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.1.2.1    | Digital Mammography X-Ray Image Storage  |
|                                  | - For Processing                         |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.1.3      | Digital Intra-Oral X-Ray Image Storage   |
|                                  | - For Presentation                       |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.1.4.1.1.3.1    | Digital Intra-Oral X-Ray Image Storage   |
|                                  | - For Processing                         |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.2        | CT Image Storage                         |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.2.1      | Enhanced CT Image Storage                |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.2.2      | Legacy Converted Enhanced CT Image       |
|                                  | Storage                                  |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.3.1      | Ultrasound Multi-frame Image Storage     |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.4        | MR Image Storage                         |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.4.1      | Enhanced MR Image Storage                |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.4.2      | MR Spectroscopy Storage                  |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.4.3      | Enhanced MR Color Image Storage          |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.4.4      | Legacy Converted Enhanced MR Image       |
|                                  | Storage                                  |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.6.1      | Ultrasound Image Storage                 |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.6.2      | Enhanced US Volume Storage               |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.7        | Secondary Capture Image Storage          |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.7.1      | Multi-frame Single Bit Secondary Capture |
|                                  | Image Storage                            |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.7.2      | Multi-frame Grayscale Byte Secondary     |
|                                  | Capture Image Storage                    |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.7.3      | Multi-frame Grayscale Word Secondary     |
|                                  | Capture Image Storage                    |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.7.4      | Multi-frame True Color Secondary Capture |
|                                  | Image Storage                            |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.9.1.1    | 12-lead ECG Waveform Storage             |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.9.1.2    | General ECG Waveform Storage             |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.9.1.3    | Ambulatory ECG Waveform Storage          |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.9.2.1    | Hemodynamic Waveform Storage             |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.9.3.1    | Cardiac Electrophysiology Waveform       |
|                                  | Storage                                  |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.9.4.1    | Basic Voice Audio Waveform Storage       |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.9.4.2    | General Audio Waveform Storage           |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.9.5.1    | Arterial Pulse Waveform Storage          |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.9.6.1    | Respiratory Waveform Storage             |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.11.1     | Grayscale Softcopy Presentation State    |
|                                  | Storage                                  |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.11.2     | Color Softcopy Presentation State        |
|                                  | Storage                                  |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.11.3     | Pseudo-Color Softcopy Presentation State |
|                                  | Storage                                  |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.11.4     | Blending Softcopy Presentation State     |
|                                  | Storage                                  |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.11.5     | XA/XRF Grayscale Softcopy Presentation   |
|                                  | State Storage                            |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.11.6     | Grayscale Planar MPR Volumetric          |
|                                  | Presentation State Storage               |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.11.7     | Compositing Planar MPR Volumetric        |
|                                  | Presentation State Storage               |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.11.8     | Advanced Blending Presentation State     |
|                                  | Storage                                  |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.11.9     | Volume Rendering Volumetric Presentation |
|                                  | State Storage                            |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.11.10    | Segmented Volume Rendering Volumetric    |
|                                  | Presentation State Storage               |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.11.11    | Multiple Volume Rendering Volumetric     |
|                                  | Presentation State Storage               |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.12.1     | X-Ray Angiographic Image Storage         |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.12.1.1   | Enhanced XA Image Storage                |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.12.2     | X-Ray Radiofluoroscopic Image Storage    |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.12.2.1   | Enhanced XRF Image Storage               |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.13.1.1   | X-Ray 3D Angiographic Image Storage      |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.13.1.2   | X-Ray 3D Craniofacial Image Storage      |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.13.1.3   | Breast Tomosynthesis Image Storage       |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.13.1.4   | Breast Projection X-Ray Image Storage    |
|                                  | - For Presentation                       |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.13.1.5   | Breast Projection X-Ray Image Storage    |
|                                  | - For Processing                         |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.14.1     | Intravascular Optical Coherence          |
|                                  | Tomography Image Storage - For           |
|                                  | Presentation                             |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.14.2     | Intravascular Optical Coherence          |
|                                  | Tomography Image Storage - For           |
|                                  | Processing                               |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.20       | Nuclear Medicine Image Storage           |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.30       | Parametric Map Storage                   |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.66       | Raw Data Storage                         |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.66.1     | Spatial Registration Storage             |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.66.2     | Spatial Fiducials Storage                |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.66.3     | Deformable Spatial Registration Storage  |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.66.4     | Segmentation Storage                     |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.66.5     | Surface Segmentation Storage             |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.66.6     | Tractography Results Storage             |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.67       | Real World Value Mapping Storage         |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.68.1     | Surface Scan Mesh Storage                |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.68.2     | Surface Scan Point Cloud Storage         |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.77.1.1   | VL Endoscopic Image Storage              |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.77.1.1.1 | Video Endoscopic Image Storage           |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.77.1.2   | VL Microscopic Image Storage             |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.77.1.2.1 | Video Microscopic Image Storage          |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.77.1.3   | VL Slide-Coordinates Microscopic Image   |
|                                  | Storage                                  |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.77.1.4   | VL Photographic Image Storage            |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.77.1.4.1 | Video Photographic Image Storage         |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.77.1.5.1 | Ophthalmic Photography 8 Bit Image       |
|                                  | Storage                                  |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.77.1.5.2 | Ophthalmic Photography 16 Bit Image      |
|                                  | Storage                                  |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.77.1.5.3 | Stereometric Relationship Storage        |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.77.1.5.4 | Ophthalmic Tomography Image Storage      |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.77.1.5.5 | Wide Field Ophthalmic Photography        |
|                                  | Stereographic Projection Image Storage   |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.77.1.5.6 | Wide Field Ophthalmic Photography 3D     |
|                                  | Coordinates Image Storage                |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.77.1.5.7 | Ophthalmic Optical Coherence Tomography  |
|                                  | En Face Image Storage                    |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.77.1.5.8 | Ophthalmic Optical Coherence Tomography  |
|                                  | B-scan Volume Analysis Storage           |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.77.1.6   | VL Whole Slide Microscopy Image Storage  |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.78.1     | Lensometry Measurements Storage          |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.78.2     | Autorefraction Measurements Storage      |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.78.3     | Keratometry Measurements Storage         |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.78.4     | Subjective Refraction Measurements       |
|                                  | Storage                                  |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.78.5     | Visual Acuity Measurements Storage       |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.78.6     | Spectacle Prescription Report Storage    |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.78.7     | Ophthalmic Axial Measurements Storage    |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.78.8     | Intraocular Lens Calculations Storage    |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.79.1     | Macular Grid Thickness and Volume Report |
|                                  | Storage                                  |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.80.1     | Ophthalmic Visual Field Static Perimetry |
|                                  | Measurements Storage                     |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.81.1     | Ophthalmic Thickness Map Storage         |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.82.1     | Corneal Topography Map Storage           |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.88.11    | Basic Text SR Storage                    |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.88.22    | Enhanced SR Storage                      |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.88.33    | Comprehensive SR Storage                 |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.88.34    | Comprehensive 3D SR Storage              |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.88.35    | Extensible SR Storage                    |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.88.40    | Procedure Log Storage                    |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.88.50    | Mammography CAD SR Storage               |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.88.59    | Key Object Selection Document Storage    |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.88.65    | Chest CAD SR Storage                     |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.88.67    | X-Ray Radiation Dose SR Storage          |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.88.68    | Radiopharmaceutical Radiation Dose SR    |
|                                  | Storage                                  |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.88.69    | Colon CAD SR Storage                     |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.88.70    | Implantation Plan SR Storage             |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.88.71    | Acquisition Context SR Storage           |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.88.72    | Simplified Adult Echo SR Storage         |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.88.73    | Patient Radiation Dose SR Storage        |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.88.74    | Planned Imaging Agent Administration SR  |
|                                  | Storage                                  |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.88.75    | Performed Imaging Agent Administration   |
|                                  | SR Storage                               |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.90.1     | Content Assessment Results Storage       |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.104.1    | Encapsulated PDF Storage                 |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.104.2    | Encapsulated CDA Storage                 |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.104.3    | Encapsulated STL Storage                 |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.128      | Positron Emission Tomography Image       |
|                                  | Storage                                  |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.128.1    | Legacy Converted Enhanced PET Image      |
|                                  | Storage                                  |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.130      | Enhanced PET Image Storage               |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.131      | Basic Structured Display Storage         |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.200.2    | CT Performed Procedure Protocol Storage  |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.481.1    | RT Image Storage                         |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.481.2    | RT Dose Storage                          |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.481.3    | RT Structure Set Storage                 |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.481.4    | RT Beams Treatment Record Storage        |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.481.5    | RT Plan Storage                          |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.481.6    | RT Brachy Treatment Record Storage       |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.481.7    | RT Treatment Summary Record Storage      |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.481.8    | RT Ion Plan Storage                      |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.481.9    | RT Ion Beams Treatment Record Storage    |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.481.10   | RT Physician Intent Storage              |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.481.11   | RT Segmentation Annotation Storage       |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.481.12   | RT Radiation Set Storage                 |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.481.13   | C-Arm Photon-Electron Radiation Storage  |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.34.7         | RT Beams Delivery Instruction Storage    |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.34.10        | RT Brachy Application Setup Delivery     |
|                                  | Instructions Storage                     |
+----------------------------------+------------------------------------------+


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
| 1.2.840.10008.1.2.4.50 | JPEG Baseline (Process 1)                          |
+------------------------+----------------------------------------------------+
| 1.2.840.10008.1.2.4.51 | JPEG Extended (Process 2 and 4)                    |
+------------------------+----------------------------------------------------+
| 1.2.840.10008.1.2.4.57 | JPEG Lossless, Non-Hierarchical (Process 14)       |
+------------------------+----------------------------------------------------+
| 1.2.840.10008.1.2.4.70 | JPEG Lossless, Non-Hierarchical, First-Order       |
|                        | Prediction (Process 14 [Selection Value 1])        |
+------------------------+----------------------------------------------------+
| 1.2.840.10008.1.2.4.80 | JPEG-LS Lossless Image Compression                 |
+------------------------+----------------------------------------------------+
| 1.2.840.10008.1.2.4.81 | JPEG-LS Lossy (Near-Lossless) Image Compression    |
+------------------------+----------------------------------------------------+
| 1.2.840.10008.1.2.4.90 | JPEG 2000 Image Compression (Lossless Only)        |
+------------------------+----------------------------------------------------+
| 1.2.840.10008.1.2.4.91 | JPEG 2000 Image Compression                        |
+------------------------+----------------------------------------------------+
| 1.2.840.10008.1.2.4.92 | JPEG 2000 Part 2 Multi-component Image Compression |
|                        | (Lossless Only)                                    |
+------------------------+----------------------------------------------------+
| 1.2.840.10008.1.2.4.93 | JPEG 2000 Part 2 Multi-component Image Compression |
+------------------------+----------------------------------------------------+
| 1.2.840.10008.1.2.5    | RLE Lossless                                       |
+------------------------+----------------------------------------------------+
