
DICOM Information Model
-----------------------

.. _concepts_iods:

Information Object Definition (IOD)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
An IOD is an object-orientated abstract data model used to specify information
about a class of real-world objects that share the same properties.
For example, a *Patient*, a *Study*, an imaging *Series* and a piece of imaging
*Equipment* are all real world objects. An IOD, then, is the data model used to
define the relationship between the objects (the *Patient* has
one or more *Studies*, each *Study* contains one or more *Series* and each
*Series* is created by a piece of *Equipment*).

IODs come in two types; composite and normalised IODs. Normalised IODs
generally represent only a single class of real-world objects (such as the
:dcm:`Print Job IOD <part03/sect_B.11.2.html>`). Composite IODs include
information about related real-world objects (such as the
:dcm:`CT Image IOD <part03/sect_A.3.3.html>` which contains objects like
*Patient*, *Study*, *Series*, *Equipment*, etc).

There are many different DICOM IODs and they're all defined in
:dcm:`Part 3 <part03.html>` of the DICOM Standard.

.. _concepts_sop_classes:

SOP Classes
~~~~~~~~~~~
A Service-Object Pair (SOP) Class is defined by the union of an IOD and a
:dcm:`DICOM Message Service Element <part07/PS3.7.html>`
(DIMSE) service group:

* **Composite SOP Classes** are the union of Composite IODs and
  the DIMSE-C service group. An example of a Composite SOP Class is the
  *CT Image Storage SOP Class*, which is the union of the *CT Image IOD* and
  the DIMSE C-STORE service. A *CT Image Storage* instance stores information
  about a single slice of a patient's CT scan. A complete scan (a *Series*) is
  made up of one or more *CT Image Storage SOP Class* instances, all
  with the same *Study Instance UID* and *Series Instance UID* values but
  differing *SOP Instance UID* values (one for each SOP instance within the
  *Series*).
* **Normalised SOP Classes** are the union of Normalised IODs and DIMSE-N
  service group. An example of a Normalised SOP Class is the *Print Job SOP
  Class*, which is the union of the *Print Job IOD* and the DIMSE
  N-EVENT-REPORT and N-GET services. The *Print Job SOP Class* is an
  abstraction of a print job containing one or more films to be printed.

The DIMSE-C and DIMSE-N services are defined in :dcm:`Part 7<part07.html>` of
the DICOM Standard. Every DICOM SOP class has its own UID that can be found in
:dcm:`Part 6<part06/chapter_A.html>`.


.. _concepts_service_classes:

Service Classes
~~~~~~~~~~~~~~~
A DICOM Service Class defines a group of one or more SOP Classes related to a
service that is to be used by communicating application  entities, as well as
the rules that are to govern the provision of the service. Services
include storage of SOP Class instances (*Storage Service Class*), verification
of DICOM connectivity (*Verification Service Class*), querying and retrieval
of managed SOP instances (*Query/Retrieve Service Class*), printing of images
(*Print Management Service Class*) and many others.

The labels *Service Class User* and *Service Class Provider* are derived from
whether or not an AE *uses* or *provides* the services in a Service Class.

Service Classes are defined in :dcm:`Part 4<part04.html>` of the DICOM
Standard.
