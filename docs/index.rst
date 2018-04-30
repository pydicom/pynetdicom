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
other medical domains. If you've ever had an X-ray or an ultrasound or one of
many other medical procedures, then the chances are that the DICOM standard was
involved in some way.

pynetdicom3
~~~~~~~~~~~
pynetdicom3 is a pure Python 2.7/3+ library that implements the DICOM
networking protocol. Working with
`pydicom <https://github.com/pydicom/pydicom>`_, it allows the easy creation
of DICOM Application Entities (AEs), which can then act as *Service Class Users*
and/or *Service Class Providers* by associating with other AEs.

Supported Service Classes
-------------------------
pynetdicom3 currently supports the following DICOM service classes:

.. toctree::
   :maxdepth: 1

   verification_service_class
   storage_service_class
   query_retrieve_service_class

User Guide
----------
The user guide is intended as an introduction to pynetdicom3 and explains how
to install and use the API, as well as covering the basics of DICOM. For
detailed reference documentation of the functions and classes see the
:ref:`reference`.

.. toctree::
   :maxdepth: 2

   user/installation
   user/dicom
   user/scu
   user/scp
   user/association
   user/message
   user/conformance

Examples
--------

API Reference
-------------

.. toctree::
   :maxdepth: 1

   reference/index
