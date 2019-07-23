

pynetdicom Documentation
========================

DICOM
-----
`DICOM <http://dicom.nema.org/>`_ is the international standard for medical
images and related information. It defines the formats and communication
protocols for media exchange in radiology, cardiology, radiotherapy and
other medical domains. If you've ever had an X-ray, an MR scan, an ultrasound or one of
many other medical procedures, then the chances are that the DICOM standard was
involved in some way.


pynetdicom
----------
`pynetdicom <https://github.com/pydicom/pynetdicom>`_ is a pure Python
2.7/3.5+ package that implements the DICOM networking protocol. Working with
`pydicom <https://github.com/pydicom/pydicom>`_, it allows the easy creation
of DICOM Application Entities (AEs), which can then act as *Service Class
Users* (SCUs) and *Service Class Providers* (SCPs) by associating with other
AEs and using or providing the services available to the association.


Supported Service Classes
-------------------------
*pynetdicom* currently supports the following `DICOM service classes
<http://dicom.nema.org/medical/dicom/current/output/chtml/part04/PS3.4.html>`_:

.. toctree::
   :maxdepth: 2
   :hidden:

   service_classes/index

* :doc:`Application Event Logging <service_classes/application_event>`
* :doc:`Basic Worklist Management<service_classes/basic_worklist_service_class>`
* :doc:`Color Palette Query/Retrieve <service_classes/color_palette_service_class>`
* :doc:`Defined Procedure Protocol Query/Retrieve <service_classes/defined_procedure_service_class>`
* :doc:`Display System Management <service_classes/display_system_service_class>`
* :doc:`Hanging Protocol Query/Retrieve <service_classes/hanging_protocol_service_class>`
* :doc:`Implant Template Query/Retrieve <service_classes/implant_template_service_class>`
* :doc:`Instance Availability Notification <service_classes/instance_availability>`
* :doc:`Media Creation Management <service_classes/media_creation>`
* :doc:`Non-Patient Object Storage <service_classes/non_patient_service_class>`
* :doc:`Print Management <service_classes/print_management>`
* :doc:`Procedure Step <service_classes/modality_performed_procedure_step>`
* :doc:`Protocol Approval Query/Retrieve <service_classes/protocol_approval_service_class>`
* :doc:`Query/Retrieve <service_classes/query_retrieve_service_class>`

  * Composite Instance Retrieve Without Bulk Data
  * Instance and Frame Level Retrieve
* :doc:`Relevant Patient Information Query <service_classes/relevant_patient_service_class>`
* :doc:`RT Machine Verification <service_classes/rt_machine>`
* :doc:`Storage <service_classes/storage_service_class>`

  * Ophthalmic Refractive Measurements
  * Softcopy Presentation State
  * Structured Reporting
  * Volumetric Presentation State
* :doc:`Storage Commitment <service_classes/storage_commitment>`
* :doc:`Substance Administration Query <service_classes/substance_admin_service_class>`
* :doc:`Unified Procedure Step <service_classes/ups>`
* :doc:`Verification <service_classes/verification_service_class>`


User Guide
==========
The :ref:`user_guide` is intended as an introduction to *pynetdicom* and
explains how to install the API and covers basic usage. For detailed
documentation of the functions and classes see the
:ref:`API reference <reference>`.

.. toctree::
   :maxdepth: 3

   user/index

.. _index_examples:

Examples
========

.. toctree::
   :maxdepth: 2
   :hidden:

   examples/index

* :doc:`Basic Worklist Management (C-FIND) <examples/basic_worklist>`
* :doc:`Display System Management (N-GET) <examples/display>`
* Modality Performed Procedure Step Management

  * :doc:`MPPS (N-CREATE and N-SET) <examples/mpps>`
* Print Management

  * :doc:`Basic Grayscale Print Management (N-CREATE, N-SET, N-GET, N-DELETE, N-ACTION) <examples/print>`
* Query/Retrieve

  * :doc:`Query/Retrieve - Find (C-FIND) <examples/qr_find>`
  * :doc:`Query/Retrieve - Get (C-GET and C-STORE) <examples/qr_get>`
  * :doc:`Query/Retrieve - Move (C-MOVE and C-STORE) <examples/qr_move>`
* :doc:`Relevant Patient Information Query (C-FIND) <examples/relevant_patient>`
* :doc:`Storage (C-STORE) <examples/storage>`
* :doc:`Verification (C-ECHO) <examples/verification>`


API Reference
=============

.. toctree::
   :maxdepth: 3
   :hidden:

   reference/index

The :doc:`API Reference <reference/index>` provides documentation of the
important functions and classes.


Applications
============

.. toctree::
   :maxdepth: 1
   :hidden:

   apps/index

* :doc:`echoscu <apps/echoscu>`
* :doc:`echoscp <apps/echoscp>`
* :doc:`storescu <apps/storescu>`
* :doc:`storescp <apps/storescp>`

Release Notes
=============

.. toctree::
   :maxdepth: 1
   :hidden:

   changelog/index

* `v1.4.0 <changelog/index.html#v1-4-0>`_
* `v1.3.1 <changelog/index.html#v1-3-1>`_
* `v1.3.0 <changelog/index.html#v1-3-0>`_
* `v1.2.0 <changelog/index.html#v1-2-0>`_
* `v1.1.0 <changelog/index.html#v1-1-0>`_
* `v1.0.0 <changelog/index.html#v1-0-0>`_
