Print Management Service Class
==============================
The `Print Management Service Class
<http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_H>`_
defines a service that uses the DIMSE N-CREATE, N-SET, N-DELETE, N-ACTION,
N-EVENT-REPORT and N-GET services to
facilitate the print of images and image related data.

.. _print_sops:

Supported SOP Classes
---------------------

+----------------------------+------------------------------------------------+
| UID                        | SOP Class                                      |
+============================+================================================+
| 1.2.840.10008.5.1.1.1      | BasicFilmSessionSOPClass                       |
+----------------------------+------------------------------------------------+
| 1.2.840.10008.5.1.1.2      | BasicFilmBoxSOPClass                           |
+----------------------------+------------------------------------------------+
| 1.2.840.10008.5.1.1.4      | BasicGrayscaleImageBoxSOPClass                 |
+----------------------------+------------------------------------------------+
| 1.2.840.10008.5.1.1.4.1    | BasicColorImageBoxSOPClass                     |
+----------------------------+------------------------------------------------+
| 1.2.840.10008.5.1.1.9      | BasicGrayscalePrintManagementMetaSOPClass      |
+----------------------------+------------------------------------------------+
| 1.2.840.10008.5.1.1.14     | PrintJobSOPClass                               |
+----------------------------+------------------------------------------------+
| 1.2.840.10008.5.1.1.15     | BasicAnnotationBoxSOPClass                     |
+----------------------------+------------------------------------------------+
| 1.2.840.10008.5.1.1.16     | PrinterSOPClass                                |
+----------------------------+------------------------------------------------+
| 1.2.840.10008.5.1.1.16.376 | PrinterConfigurationRetrievalSOPClass          |
+----------------------------+------------------------------------------------+
| 1.2.840.10008.5.1.1.18     | BasicColorPrintManagementMetaSOPClass          |
+----------------------------+------------------------------------------------+
| 1.2.840.10008.5.1.1.23     | PresentationLUTSOPClass                        |
+----------------------------+------------------------------------------------+


Meta SOP Classes
----------------

+------------------------------------------+-----------------------+
| SOP Class                                | Usage SCU/SCP         |
+==========================================+=======================+
| *Basic Grayscale Print Management Meta SOP Class*                |
+------------------------------------------+-----------------------+
| *Basic Film Session SOP Class*           | Mandatory/Mandatory   |
+------------------------------------------+-----------------------+
| *Basic Film Box SOP Class*               | Mandatory/Mandatory   |
+------------------------------------------+-----------------------+
| *Basic Grayscale Image Box SOP Class*    | Mandatory/Mandatory   |
+------------------------------------------+-----------------------+
| *Printer SOP Class*                      | Mandatory/Mandatory   |
+------------------------------------------+-----------------------+

+------------------------------------------+-----------------------+
| SOP Class                                | Usage SCU/SCP         |
+==========================================+=======================+
| *Basic Color Print Management Meta SOP Class*                    |
+------------------------------------------+-----------------------+
| *Basic Film Session SOP Class*           | Mandatory/Mandatory   |
+------------------------------------------+-----------------------+
| *Basic Film Box SOP Class*               | Mandatory/Mandatory   |
+------------------------------------------+-----------------------+
| *Basic Color Image Box SOP Class*        | Mandatory/Mandatory   |
+------------------------------------------+-----------------------+
| *Printer SOP Class*                      | Mandatory/Mandatory   |
+------------------------------------------+-----------------------+


DIMSE Services
--------------

+-----------------+-----------------------------------------+
| DIMSE Service   | Usage SCU/SCP                           |
+=================+=========================================+
| *Basic Film Session SOP Class*                            |
+-----------------+-----------------------------------------+
| N-CREATE        | Mandatory/Mandatory                     |
+-----------------+-----------------------------------------+
| N-SET           | Optional/Mandatory                      |
+-----------------+-----------------------------------------+
| N-DELETE        | Optional/Mandatory                      |
+-----------------+-----------------------------------------+
| N-ACTION        | Optional/Optional                       |
+-----------------+-----------------------------------------+
| *Basic Film Box SOP Class*                                |
+-----------------+-----------------------------------------+
| N-CREATE        | Mandatory/Mandatory                     |
+-----------------+-----------------------------------------+
| N-ACTION        | Mandatory/Mandatory                     |
+-----------------+-----------------------------------------+
| N-DELETE        | Optional/Mandatory                      |
+-----------------+-----------------------------------------+
| N-SET           | Optional/Optional                       |
+-----------------+-----------------------------------------+
| *Basic Grayscale Image Box SOP Class*                     |
+-----------------+-----------------------------------------+
| *Basic Color Image Box SOP Class*                         |
+-----------------+-----------------------------------------+
| N-SET           | Mandatory/Mandatory                     |
+-----------------+-----------------------------------------+
| *Basic Annotation Box SOP Class*                          |
+-----------------+-----------------------------------------+
| N-SET           | Optional/Mandatory                      |
+-----------------+-----------------------------------------+
| *Print Job SOP Class*                                     |
+-----------------+-----------------------------------------+
| *Printer SOP Class*                                       |
+-----------------+-----------------------------------------+
| N-EVENT-REPORT  | Mandatory/Mandatory                     |
+-----------------+-----------------------------------------+
| N-GET           | Optional/Mandatory                      |
+-----------------+-----------------------------------------+
| *Presentation LUT SOP Class*                              |
+-----------------+-----------------------------------------+
| N-CREATE        | Mandatory/Mandatory                     |
+-----------------+-----------------------------------------+
| N-DELETE        | Optional/Mandatory                      |
+-----------------+-----------------------------------------+
| *Printer Configuration Retrieval SOP Class*               |
+-----------------+-----------------------------------------+
| N-GET           | Mandatory/Mandatory                     |
+-----------------+-----------------------------------------+


.. _print_statuses:

Statuses
--------

N-ACTION Statuses
~~~~~~~~~~~~~~~~~

+------------------+----------+-----------------------------------------------+
| Code (hex)       | Category | Description                                   |
+==================+==========+===============================================+
| 0x0000           | Success  | Success                                       |
+------------------+----------+-----------------------------------------------+
| 0x0112           | Failure  | No such SOP Instance                          |
+------------------+----------+-----------------------------------------------+
| 0x0114           | Failure  | No such argument                              |
+------------------+----------+-----------------------------------------------+
| 0x0115           | Failure  | Invalid argument value                        |
+------------------+----------+-----------------------------------------------+
| 0x0117           | Failure  | Invalid object instance                       |
+------------------+----------+-----------------------------------------------+
| 0x0118           | Failure  | No such SOP Class                             |
+------------------+----------+-----------------------------------------------+
| 0x0119           | Failure  | Class-Instance conflict                       |
+------------------+----------+-----------------------------------------------+
| 0x0123           | Failure  | No such action                                |
+------------------+----------+-----------------------------------------------+
| 0x0124           | Failure  | Refused: not authorised                       |
+------------------+----------+-----------------------------------------------+
| 0x0210           | Failure  | Duplicate invocation                          |
+------------------+----------+-----------------------------------------------+
| 0x0211           | Failure  | Unrecognised operation                        |
+------------------+----------+-----------------------------------------------+
| 0x0212           | Failure  | Mistyped argument                             |
+------------------+----------+-----------------------------------------------+
| 0x0213           | Failure  | Resource limitation                           |
+------------------+----------+-----------------------------------------------+

Print Management N-ACTION Service Statuses
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+------------------+----------+-----------------------------------------------+
| Code (hex)       | Category | Description                                   |
+==================+==========+===============================================+
| 0xB601           | Warning  | Film session printing (collation) is not      |
|                  |          | supported                                     |
+------------------+----------+-----------------------------------------------+
| 0xB602           | Warning  | Film Session SOP Instance hierarchy does not  |
|                  |          | contain Image Box SOP Instances (empty page)  |
+------------------+----------+-----------------------------------------------+
| 0xB603           | Warning  | Film Box SOP Instance hierarchy does not      |
|                  |          | contain Film Box SOP Instances (empty page)   |
+------------------+----------+-----------------------------------------------+
| 0xB604           | Warning  | Image size is larger than image box size, the |
|                  |          | image has been demagnified                    |
+------------------+----------+-----------------------------------------------+
| 0xB609           | Warning  | Image size is larger than image box size, the |
|                  |          | image has been cropped to fit                 |
+------------------+----------+-----------------------------------------------+
| 0xB60A           | Warning  | Image size or Combined Print Image size is    |
|                  |          | larger than the Image Box size. Image or      |
|                  |          | Combined Print Image has been decimated to fit|
+------------------+----------+-----------------------------------------------+
| 0xC600           | Failure  | Film Session SOP Instance hierarchy does not  |
|                  |          | contain Film Box SOP Instances                |
+------------------+----------+-----------------------------------------------+
| 0xC601           | Failure  | Unable to create Print Job SOP Instance; print|
|                  |          | queue is full                                 |
+------------------+----------+-----------------------------------------------+
| 0xC602           | Failure  | Unable to create Print Job SOP Instance; print|
|                  |          | queue is full                                 |
+------------------+----------+-----------------------------------------------+
| 0xC603           | Failure  | Image size is larger than image box size      |
+------------------+----------+-----------------------------------------------+
| 0xC613           | Failure  | Combined Print Image size is larger than the  |
|                  |          | Image Box size                                |
+------------------+----------+-----------------------------------------------+


N-CREATE Statuses
~~~~~~~~~~~~~~~~~

+------------------+----------+-----------------------------------------------+
| Code (hex)       | Category | Description                                   |
+==================+==========+===============================================+
| 0x0000           | Success  | Success                                       |
+------------------+----------+-----------------------------------------------+
| 0x0105           | Success  | No such attribute                             |
+------------------+----------+-----------------------------------------------+
| 0x0106           | Success  | Invalid attribute value                       |
+------------------+----------+-----------------------------------------------+
| 0x0107           | Success  | Attribute list error                          |
+------------------+----------+-----------------------------------------------+
| 0x0110           | Success  | Processing failure                            |
+------------------+----------+-----------------------------------------------+
| 0x0111           | Success  | Duplicate SOP Instance                        |
+------------------+----------+-----------------------------------------------+
| 0x0116           | Success  | Attribute value out of range                  |
+------------------+----------+-----------------------------------------------+
| 0x0117           | Success  | Invalid object instance                       |
+------------------+----------+-----------------------------------------------+
| 0x0118           | Success  | No such SOP Class                             |
+------------------+----------+-----------------------------------------------+
| 0x0120           | Success  | Missing attribute                             |
+------------------+----------+-----------------------------------------------+
| 0x0121           | Success  | Missing attribute value                       |
+------------------+----------+-----------------------------------------------+
| 0x0124           | Success  | Refused: not authorised                       |
+------------------+----------+-----------------------------------------------+
| 0x0210           | Success  | Duplicate invocation                          |
+------------------+----------+-----------------------------------------------+
| 0x0211           | Success  | Unrecognised operation                        |
+------------------+----------+-----------------------------------------------+
| 0x0212           | Success  | Mistyped argument                             |
+------------------+----------+-----------------------------------------------+
| 0x0213           | Success  | Resource limitation                           |
+------------------+----------+-----------------------------------------------+

Print Management N-CREATE Service Statuses
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+------------------+----------+-----------------------------------------------+
| Code (hex)       | Category | Description                                   |
+==================+==========+===============================================+
| 0xB600           | Warning  | Memory allocation not supported               |
+------------------+----------+-----------------------------------------------+
| 0xB605           | Warning  | Requested Min Density outside of printer's    |
|                  |          | operating range. The printer will use its     |
|                  |          | respective minimum or maximum density value   |
|                  |          | instead                                       |
+------------------+----------+-----------------------------------------------+
| 0xC616           | Failure  | There is an existing Film Box that has not    |
|                  |          | been printed and N-ACTION at the Film Session |
|                  |          | level is not supported. A new Film Box will   |
|                  |          | not be created when a previous Film Box has   |
|                  |          | not been printed                              |
+------------------+----------+-----------------------------------------------+

N-DELETE Statuses
~~~~~~~~~~~~~~~~~

+------------------+----------+----------------------------------+
| Code (hex)       | Category | Description                      |
+==================+==========+==================================+
| 0x0000           | Success  | Success                          |
+------------------+----------+----------------------------------+
| 0x0110           | Failure  | Processing failure               |
+------------------+----------+----------------------------------+
| 0x0112           | Failure  | No such SOP Instance             |
+------------------+----------+----------------------------------+
| 0x0117           | Failure  | Invalid object Instance          |
+------------------+----------+----------------------------------+
| 0x0118           | Failure  | Not such SOP Class               |
+------------------+----------+----------------------------------+
| 0x0119           | Failure  | Class-Instance conflict          |
+------------------+----------+----------------------------------+
| 0x0124           | Failure  | Not authorised                   |
+------------------+----------+----------------------------------+
| 0x0210           | Failure  | Duplicate invocation             |
+------------------+----------+----------------------------------+
| 0x0211           | Failure  | Unrecognised operation           |
+------------------+----------+----------------------------------+
| 0x0212           | Failure  | Mistyped argument                |
+------------------+----------+----------------------------------+
| 0x0213           | Failure  | Resource limitation              |
+------------------+----------+----------------------------------+

N-EVENT-REPORT Statuses
~~~~~~~~~~~~~~~~~~~~~~~

+------------------+----------+----------------------------------+
| Code (hex)       | Category | Description                      |
+==================+==========+==================================+
| 0x0000           | Success  | Success                          |
+------------------+----------+----------------------------------+
| 0x0110           | Failure  | Processing failure               |
+------------------+----------+----------------------------------+
| 0x0112           | Failure  | No such SOP Instance             |
+------------------+----------+----------------------------------+
| 0x0113           | Failure  | No such event type               |
+------------------+----------+----------------------------------+
| 0x0114           | Failure  | No such argument                 |
+------------------+----------+----------------------------------+
| 0x0115           | Failure  | Invalid argument value           |
+------------------+----------+----------------------------------+
| 0x0117           | Failure  | Invalid object Instance          |
+------------------+----------+----------------------------------+
| 0x0118           | Failure  | No such SOP Class                |
+------------------+----------+----------------------------------+
| 0x0119           | Failure  | Class-Instance conflict          |
+------------------+----------+----------------------------------+
| 0x0210           | Failure  | Duplicate invocation             |
+------------------+----------+----------------------------------+
| 0x0211           | Failure  | Unrecognised operation           |
+------------------+----------+----------------------------------+
| 0x0212           | Failure  | Mistyped argument                |
+------------------+----------+----------------------------------+
| 0x0213           | Failure  | Resource limitation              |
+------------------+----------+----------------------------------+


N-GET Statuses
~~~~~~~~~~~~~~~

+------------+----------+----------------------------------+
| Code (hex) | Category | Description                      |
+============+==========+==================================+
| 0x0000     | Success  | Success                          |
+------------+----------+----------------------------------+
| 0x0107     | Warning  | SOP Class not supported          |
+------------+----------+----------------------------------+
| 0x0110     | Failure  | Processing failure               |
+------------+----------+----------------------------------+
| 0x0112     | Failure  | No such SOP Instance             |
+------------+----------+----------------------------------+
| 0x0117     | Failure  | Invalid object instance          |
+------------+----------+----------------------------------+
| 0x0118     | Failure  | No such SOP Class                |
+------------+----------+----------------------------------+
| 0x0119     | Failure  | Class-Instance conflict          |
+------------+----------+----------------------------------+
| 0x0122     | Failure  | SOP class not supported          |
+------------+----------+----------------------------------+
| 0x0124     | Failure  | Not authorised                   |
+------------+----------+----------------------------------+
| 0x0210     | Failure  | Duplicate invocation             |
+------------+----------+----------------------------------+
| 0x0211     | Failure  | Unrecognised operation           |
+------------+----------+----------------------------------+
| 0x0212     | Failure  | Mistyped argument                |
+------------+----------+----------------------------------+
| 0x0213     | Failure  | Resource limitation              |
+------------+----------+----------------------------------+

N-SET Statuses
~~~~~~~~~~~~~~~

+------------------+----------+----------------------------------+
| Code (hex)       | Category | Description                      |
+==================+==========+==================================+
| 0x0000           | Success  | Success                          |
+------------------+----------+----------------------------------+
| 0x0105           | Failure  | No such attribute                |
+------------------+----------+----------------------------------+
| 0x0106           | Failure  | Invalid attribute value          |
+------------------+----------+----------------------------------+
| 0x0110           | Failure  | Processing failure               |
+------------------+----------+----------------------------------+
| 0x0112           | Failure  | SOP Instance not recognised      |
+------------------+----------+----------------------------------+
| 0x0116           | Failure  | Attribute value out of range     |
+------------------+----------+----------------------------------+
| 0x0117           | Failure  | Invalid object instance          |
+------------------+----------+----------------------------------+
| 0x0118           | Failure  | No such SOP Class                |
+------------------+----------+----------------------------------+
| 0x0119           | Failure  | Class-Instance conflict          |
+------------------+----------+----------------------------------+
| 0x0121           | Failure  | Missing attribute value          |
+------------------+----------+----------------------------------+
| 0x0124           | Failure  | Refused: not authorised          |
+------------------+----------+----------------------------------+
| 0x0210           | Failure  | Duplicate invocation             |
+------------------+----------+----------------------------------+
| 0x0211           | Failure  | Unrecognised operation           |
+------------------+----------+----------------------------------+
| 0x0212           | Failure  | Mistyped argument                |
+------------------+----------+----------------------------------+
| 0x0213           | Failure  | Resource limitation              |
+------------------+----------+----------------------------------+

Print Management N-SET Service Statuses
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

+------------------+----------+-----------------------------------------------+
| Code (hex)       | Category | Description                                   |
+==================+==========+===============================================+
| 0xB600           | Warning  | Memory allocation not supported               |
+------------------+----------+-----------------------------------------------+
| 0xB604           | Warning  | Image size larger than image box size, the    |
|                  |          | image has been demagnified                    |
+------------------+----------+-----------------------------------------------+
| 0xB605           | Warning  | Requested Min Density outside of printer's    |
|                  |          | operating range. The printer will use its     |
|                  |          | respective minimum or maximum density value   |
|                  |          | instead                                       |
+------------------+----------+-----------------------------------------------+
| 0xB609           | Warning  | Image size is larger than image box size, the |
|                  |          | image has been cropped to fit                 |
+------------------+----------+-----------------------------------------------+
| 0xB60A           | Warning  | Image size or Combined Print Image size is    |
|                  |          | larger than the Image Box size. Image or      |
|                  |          | Combined Print Image has been decimated to fit|
+------------------+----------+-----------------------------------------------+
| 0xC603           | Failure  | Image size is larger than image box size      |
+------------------+----------+-----------------------------------------------+
| 0xC605           | Failure  | Insufficient memory in printer to store image |
+------------------+----------+-----------------------------------------------+
| 0xC613           | Failure  | Combined Print Image size is larger than the  |
|                  |          | Image Box size                                |
+------------------+----------+-----------------------------------------------+
| 0xC616           | Failure  | There is an existing Film Box that has not    |
|                  |          | been printed and N-ACTION at the Film Session |
|                  |          | level is not supported. A new Film Box will   |
|                  |          | not be created when a previous Film Box has   |
|                  |          | not been printed                              |
+------------------+----------+-----------------------------------------------+



References
----------

* DICOM Standard, Part 4, `Annex S <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_S>`_
* DICOM Standard, Part 7, `Section 10.1.4.1.10 <http://dicom.nema.org/medical/dicom/current/output/chtml/part07/chapter_10.html#sect_10.1.4.1.10>`_
* DICOM Standard, Part 7, `Section 10.1.5.1.6 <http://dicom.nema.org/medical/dicom/current/output/chtml/part07/chapter_10.html#sect_10.1.5.1.6>`_
* DICOM Standard, Part 7, `Section 10.1.6.1.7 <http://dicom.nema.org/medical/dicom/current/output/chtml/part07/chapter_10.html#sect_10.1.6.1.7>`_
* DICOM Standard, Part 7, `Section 10.1.1.1.8 <http://dicom.nema.org/medical/dicom/current/output/chtml/part07/chapter_10.html#sect_10.1.1.1.8>`_
* DICOM Standard, Part 7, `Section 10.1.2.1.9 <http://dicom.nema.org/medical/dicom/current/output/chtml/part07/chapter_10.html#sect_10.1.2.1.9>`_
* DICOM Standard, Part 7, `Section 10.1.3.1.9 <http://dicom.nema.org/medical/dicom/current/output/chtml/part07/chapter_10.html#sect_10.1.3.1.9>`_
