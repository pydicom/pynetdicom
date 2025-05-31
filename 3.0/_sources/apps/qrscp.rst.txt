=====
qrscp
=====

.. versionadded:: 1.5

.. code-block:: text

    $ python -m pynetdicom qrscp [options]

Description
===========

The ``qrscp`` application implements a Service Class Provider (SCP) for the
:dcm:`Verification<part04/chapter_A.html>`, :dcm:`Storage
<part04/chapter_B.html>` and :dcm:`Query/Retrieve<part04/chapter_C.html>`
service classes. It listens for incoming association requests on the
configured port, and once an association is established, allows Service Class
Users (SCUs) to:

* Verify the DICOM connection
* Request the application store SOP Instances
* Query the application for its stored SOP Instances
* Request the retrieval of stored SOP Instances

SOP Instances sent to the application using the Storage service have some of
their attributes added to a sqlite database that is used to manage Instances
for the Query/Retrieve service.

In addition, the ``qrscp`` application implements a Service Class Provider (SCP) for the
:dcm:`Basic Modality Worklist<part04/chapter_K.html>`, and :dcm:`Unified Procedure Step<part04/Chapter_CC>`
service classes, but currently will only return empty results (0 records)

.. warning::

    In addition to the standard *pynetdicom* dependencies, the ``qrscp``
    application requires the `sqlalchemy <https://www.sqlalchemy.org/>`_
    package

The source code for the application can be found :gh:`here
<pynetdicom/tree/main/pynetdicom/apps/qrscp>`

Usage
=====

Start the application using the default configuration, which listens on port
11112:

.. code-block:: text

    $ python -m pynetdicom qrscp

Start the application using a custom configuration file:

.. code-block:: text

    $ python -m pynetdicom qrscp -c my_config.ini

More information is available when starting the application with the ``-v`` or
``-d`` options:

.. code-block:: text

    $ python -m pynetdicom qrscp -d


Options
=======
General Options
---------------
``-c    --config [f]ilename``
            use configuration file f, see the *configuration file* section for
            more information
``--version``
            print version information and exit
``-q    --quiet``
            quiet mode, prints no warnings or errors
``-v    --verbose``
            verbose mode, prints processing details
``-d    --debug``
            debug mode, prints debugging information
``-ll   --log-level [l]evel (str)``
            One of [``'critical'``, ``'error'``, ``'warning'``, ``'info'``,
            ``'debug'``], prints logging messages with corresponding level
            or lower

Network Options
---------------
``-aet  --ae-title [a]etitle (str)``
            override the configured local AE title
``--port [p]ort (int)``
            override the configured listen port
``-ba   --bind-address [a]ddress (str)``
            override the configured bind address
``-ta   --acse-timeout [s]econds (float)``
            override the configured timeout for ACSE messages
``-td   --dimse-timeout [s]econds (float)``
            override the configured timeout for DIMSE messages
``-tn   --network-timeout [s]econds (float)``
            override the configured timeout for the network
``-pdu  --max-pdu [n]umber of bytes (int)``
            override the configured maximum receive PDU bytes

Database Options
----------------
``--database-location [f]ile (str)``
            override the location of the database using file f
``--instance-location [d]irectory (str)``
            override the configured instance storage location to directory d
``--clean``
            remove all entries from the database and delete the corresponding
            stored instances


Configuration File
==================

The ``qrscp`` application uses a configuration file format compatible with the
:mod:`configparser` Python module. The ``[DEFAULT]`` section contains the
configuration options for the application itself while all other sections
are assumed to be definitions for the Query/Retrieve service's *Move
Destinations*:

.. code-block:: text

    [DEFAULT]
    # Our AE Title
    ae_title: QRSCP
    # Our listen port
    port: 11112
    # Our maximum PDU size; 0 for unlimited
    max_pdu: 16382
    # The ACSE, DIMSE and network timeouts (in seconds)
    acse_timeout: 30
    dimse_timeout: 30
    network_timeout: 30
    # The address of the network interface to listen on
    # If unset, listen on all interfaces
    bind_address:
    # Directory where SOP Instances received from Storage SCUs will be stored
    #   This directory contains the QR service's managed SOP Instances
    instance_location: instances
    # Location of sqlite3 database for the QR service's managed SOP Instances
    database_location: instances.sqlite

    # Move Destination 1
    # The AE title of the move destination, as ASCII
    [STORESCP]
        # The IP address and listen port of the destination
        address: 8.8.8.8
        port: 11112

    # Move Destination 2
    [PACS_SCP]
        address: 192.168.2.1
        port: 104

DICOM Conformance
=================
The ``qrscp`` application supports the Verification, Storage and Query/Retrieve
service classes as an SCP. The following SOP classes are supported:

Verification Service
--------------------

SOP Classes
...........

+----------------------------------+------------------------------------------+
| UID                              | SOP Class                                |
+==================================+==========================================+
|1.2.840.10008.1.1                 | Verification SOP Class                   |
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
| 1.2.840.10008.1.2.2    | Explicit VR Big Endian                             |
+------------------------+----------------------------------------------------+
| 1.2.840.10008.1.2.1.99 | Deflated Explicit VR Little Endian                 |
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
| 1.2.840.10008.5.1.4.1.1.9.6.2    | Multichannel Respiratory Waveform Storage|
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.9.7.1    | Routine Scalp SleepElectroencephalogram  |
|                                  | Waveform Storage                         |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.9.7.2    | Electromyogram Waveform Storage          |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.9.7.3    | Electrooculogram Waveform Storage        |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.9.7.4    | Sleep Electroencephalogram Waveform      |
|                                  | Storage                                  |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.9.8.1    | Body Position Waveform Storage           |
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
| 1.2.840.10008.5.1.4.1.1.77.1.7   | Dermoscopic Photography Image Storage    |
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
| 1.2.840.10008.5.1.4.1.1.88.76    | Enhanced X-Ray Radiation Dose SR Storage |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.90.1     | Content Assessment Results Storage       |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.91.1     | Microscopy Bulk Simple Annotations       |
|                                  | Storage                                  |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.104.1    | Encapsulated PDF Storage                 |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.104.2    | Encapsulated CDA Storage                 |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.104.3    | Encapsulated STL Storage                 |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.104.4    | Encapsulated OBJ Storage                 |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.104.5    | Encapsulated MTL Storage                 |
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
| 1.2.840.10008.5.1.4.1.1.200.8    | XA Performed Procedure Protocol Storage  |
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
| 1.2.840.10008.5.1.4.1.1.481.14   | Tomotherapeutic Radiation Storage        |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.481.15   | Robotic Arm Radiation Storage            |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.481.16   | RT Radiation Record Set Storage          |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.481.17   | RT Radiation Salvage Record Storage      |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.481.18   | Tomotherapeutic Radiation Record Storage |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.481.19   | C-Arm Photon-Electron Radiation Record   |
|                                  | Storage                                  |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.481.20   | Robotic Arm Radiation Record Storage     |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.481.21   | RT Radiation Set Delivery Instruction    |
|                                  | Storage                                  |
+----------------------------------+------------------------------------------+
| 1.2.840.10008.5.1.4.1.1.481.22   | RT Treatment Preparation Storage         |
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
| 1.2.840.10008.1.2.2    | Explicit VR Big Endian                             |
+------------------------+----------------------------------------------------+
| 1.2.840.10008.1.2.1.99 | Deflated Explicit VR Little Endian                 |
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


Query/Retrieve Service
----------------------

SOP Classes
...........

+----------------------------------+------------------------------------------+
| UID                              | SOP Class                                |
+==================================+==========================================+
|1.2.840.10008.5.1.4.1.2.1.1       | Patient Root Query/Retrieve Information  |
|                                  | Model - FIND                             |
+----------------------------------+------------------------------------------+
|1.2.840.10008.5.1.4.1.2.1.2       | Patient Root Query/Retrieve Information  |
|                                  | Model - MOVE                             |
+----------------------------------+------------------------------------------+
|1.2.840.10008.5.1.4.1.2.1.3       | Patient Root Query/Retrieve Information  |
|                                  | Model - GET                              |
+----------------------------------+------------------------------------------+
|1.2.840.10008.5.1.4.1.2.2.1       | Study Root Query/Retrieve Information    |
|                                  | Model - FIND                             |
+----------------------------------+------------------------------------------+
|1.2.840.10008.5.1.4.1.2.2.2       | Study Root Query/Retrieve Information    |
|                                  | Model - MOVE                             |
+----------------------------------+------------------------------------------+
|1.2.840.10008.5.1.4.1.2.2.3       | Study Root Query/Retrieve Information    |
|                                  | Model - GET                              |
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
