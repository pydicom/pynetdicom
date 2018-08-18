Important Concepts
==================

DICOM Information Model
-----------------------
Information Object Definition (IOD)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
An IOD is an object-orientated abstract data model use to specify information
about a class of real-world objects that share the same properties.
For example, a *Patient*, a *Study*, an imaging *Series* and a piece of imaging
*Equipment* are all real world objects. An IOD, then, is the data model used to
define the relationship between the objects (the *Patient* has
one or more *Studies*, each contains one or more *Series* and each *Series*
is created by a piece of *Equipment*).

IODs come in two types; composite and normalised IODs. Normalised IODs
generally represent only a single class of real-world objects (such as a
*Print Job*). Composite IODs include
information about related real-world objects (such as the
*Patient/Study/Series/Equipment* example given above).

IODs are defined in `Part 3 <http://dicom.nema.org/medical/dicom/current/output/html/part03.html>`_
of the DICOM Standard.

SOP Classes
~~~~~~~~~~~
A Service-Object Pair (SOP) Class is defined by the union of an IOD and a DIMSE
service group.

* **Composite SOP Classes** are the union of Composite IODs and
  DIMSE-C services. An example of a Composite SOP Class is the *CT Image
  Storage SOP Class*, which is the union of the *CT Image IOD* and the DIMSE
  C-STORE service and stores information about a
  single slice of a patient's CT scan. A complete scan (a *Series*) would
  then be made up of one or more *CT Image Storage SOP Class* instances, all
  with the same *Series Instance UID* value.
* **Normalised SOP Classes** are the union of Normalised IODs and DIMSE-N
  services. An example of a Normalised SOP Class is the *Print Job SOP
  Class*, which is the union of the *Print Job IOD* and the DIMSE
  N-EVENT-REPORT and N-GET services. The *Print Job SOP Class* is abstraction
  of a print job containing one or more films to be printed.

The DIMSE Services are defined in `Part 7 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html>`_
of the DICOM Standard.

Service Classes
~~~~~~~~~~~~~~~
A DICOM Service Class defines a group of one or more SOP Classes related to a
service that is to be used by communicating application  entities, as well as
the rules that are to govern the provision of the service. Services
include storage of SOP Class instances, verification of DICOM connectivity,
querying and retrieval of managed SOP instances, printing of images and many
others.

Service Classes are defined in `Part 4 <http://dicom.nema.org/medical/dicom/current/output/html/part04.html>`_
of the DICOM Standard.


Association
-----------


Presentation Contexts
---------------------
A Presentation Context consists of an Abstract Syntax and one or more Transfer
Syntaxes, along with an ID value. Presentation Contexts are used during the
negotiation of an association

1. The association requestor will propose one or more presentation contexts
   for use in the association.
2. For each proposed presentation context, the association acceptor will
   either agree to one of the transfer syntaxes or reject the context.

* The requestor may offer multiple presentation contexts per association
* Each presentation context supports one Abstract Syntax (related to a SOP
  Class or Meta SOP Class) and one or more Transfer Syntaxes.
* The acceptor may accept or reject each presentation context individually
* The acceptor selects a suitable Transfer Syntax for each accepted
  presentation context.


Abstract Syntax
~~~~~~~~~~~~~~~
An Abstract Syntax is something. It allows communicating AEs to negotiate an
agreed set of DICOM Data Elements and/or IODs. DICOM registered abstract. This
is terrible.

Transfer Syntax
~~~~~~~~~~~~~~~
A Transfer Syntax defines a set of encoding rules able to unambiguously
represent the data elements defined by one or more Abstract Syntaxes. In
particular, the negotiation of transfer syntaxes allows communicating AEs to
agree on the encoding techniques they are able to support (i.e. byte ordering,
compression, etc.).

An example is an SCU sending a presentation context proposing the use
of the 1.2.840.10008.1.2.4.50 (JPEG Baseline) transfer syntax, which, if the
SCP didn't support, would respond to the proposal with *'transfer syntax
not supported'*.
