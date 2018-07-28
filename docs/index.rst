Welcome to the documentation for `pynetdicom <https://github.com/pydicom/pynetdicom3>`_.


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


pynetdicom
~~~~~~~~~~
*pynetdicom* is a pure Python 2.7/3.4+ package that implements the DICOM
networking protocol. Working with
`pydicom <https://github.com/pydicom/pydicom>`_, it allows the easy creation
of DICOM Application Entities (AEs), which can then act as *Service Class
Users* (SCUs) and *Service Class Providers* (SCPs) by associating with other
AEs and providing or using one or more of the services available to the
association.


Supported Service Classes
-------------------------
pynetdicom currently supports the following DICOM service classes:

.. toctree::
   :maxdepth: 1

   verification_service_class
   storage_service_class
   query_retrieve_service_class
   basic_worklist_service_class


User Guide
----------
The :ref:`user_guide` is intended as an introduction to pynetdicom and
explains how to install and use the API, as well as covering the basics of
DICOM networking. For detailed reference documentation of the functions and
classes see the :ref:`reference`.

.. toctree::
   :maxdepth: 2

   user/index


Examples
--------

.. toctree::
   :maxdepth: 1

   examples/verification
   examples/storage
   examples/qr_find
   examples/qr_get
   examples/qr_move
   examples/basic_worklist


API Reference
-------------

.. toctree::
   :maxdepth: 2

   reference/index

Release Notes
-------------

.. toctree::
   :maxdepth: 1

   release_notes
