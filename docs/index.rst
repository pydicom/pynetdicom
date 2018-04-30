pynetdicom3 Documentation
=========================
Welcome to the documentation for pynetdicom3.

Description
-----------

DICOM
~~~~~
`DICOM <http://dicom.nema.org/>`_ is the international standard for medical
images and related information. It defines the formats and communication
protocols for media exchange in radiology, cardiology, radiotherapy and
other medical domains.

pynetdicom3
~~~~~~~~~~~
pynetdicom3 is a pure Python 2.7/3+ library that implements the DICOM
networking protocol. Working with
`pydicom <https://github.com/pydicom/pydicom>`_, it allows the easy creation
of DICOM Application Entities (AEs) which can then act as *Service Class Users*
and/or *Service Class Providers* by associating with other AEs.

Supported Service Classes
-------------------------
pynetdicom3 currently supports the following DICOM service classes:

* `Verification Service Class <verification_service_class.rst>`_
* `Storage Service Class <storage_service_class.rst>`_
* `Query/Retrieve Service Class <query_retrieve_service_class.rst>`_

User Guide
----------
The user guide is intended as an introduction to pynetdicom3 and explains how
to install and use the API, as well as covering the basics of DICOM. For
detailed reference documentation of the functions and classes see the API
Reference.

* Installation
* DICOM Basics
  * DICOM Datasets and the DICOM File Format
  * Association and the ACSE provider
  * Message exchange and the DIMSE provider
* Quickstart guide to SCUs
* Quickstart guide to SCPs
* Conformance Statements

API Reference
-------------

.. toctree::
   :maxdepth: 1

   reference/index
