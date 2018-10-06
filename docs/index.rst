

pynetdicom Documentation
========================

DICOM
-----
`DICOM <http://dicom.nema.org/>`_ is the international standard for medical
images and related information. It defines the formats and communication
protocols for media exchange in radiology, cardiology, radiotherapy and
other medical domains. If you've ever had an X-ray or an ultrasound or one of
many other medical procedures, then the chances are that the DICOM standard was
involved in some way.


pynetdicom
----------
`pynetdicom <https://github.com/pydicom/pynetdicom>`_ is a pure Python
2.7/3.4+ package that implements the DICOM networking protocol. Working with
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
==========
The :ref:`user_guide` is intended as an introduction to pynetdicom and
explains how to install the API and covers basic usage. For detailed reference
documentation of the functions and classes see the
:ref:`API reference <reference>`.

.. toctree::
   :maxdepth: 2

   user/index

.. _index_examples:

Examples
========

* :doc:`Verification Service Examples <examples/verification>`
* :doc:`Storage Service Examples <examples/storage>`
* :doc:`Query/Retrieve (Find) Service Examples <examples/qr_find>`
* :doc:`Query/Retrieve (Get) Service Examples <examples/qr_get>`
* :doc:`Query/Retrieve (Move) Service Examples <examples/qr_move>`
* :doc:`Basic Worklist Management Service Examples <examples/basic_worklist>`


API Reference
=============

The :doc:`API Reference <reference/index>` provides documentation of the
important functions and classes.

Applications
============

* :doc:`echoscu <apps/echoscu>`
* :doc:`echoscp <apps/echoscp>`
* :doc:`storescu <apps/storescu>`
* :doc:`storescp <apps/storescp>`

Release Notes
=============

.. toctree::
   :maxdepth: 1

   release_notes
