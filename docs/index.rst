
========================
pynetdicom Documentation
========================

`pynetdicom <https://github.com/pydicom/pynetdicom>`_ is a pure Python
2.7/3.5+ package that implements the `DICOM <http://dicom.nema.org/>`_
networking protocol. Working with
`pydicom <https://github.com/pydicom/pydicom>`_, it allows the easy creation
of DICOM Application Entities (AEs), which can then act as *Service Class
Users* (SCUs) and *Service Class Providers* (SCPs) by associating with other
AEs and using or providing the services available to the association.

Getting started
===============

If you're new to *pynetdicom* then start here:

* **Basics**: :doc:`Installation</tutorials/installation>` |
  :doc:`Writing your first SCU</tutorials/create_scu>` |
  :doc:`Writing your first SCP</tutorials/create_scp>` |
* **Intermediate**: :doc:`Using TLS</tutorials/using_tls>`


User Guide
==========
The :ref:`user_guide` is intended as an introduction to *pynetdicom* and
explains how to install the API and covers basic usage. For detailed
documentation of the functions and classes see the
:ref:`API reference <reference>`.

.. _index_examples:

Examples
========

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

The :doc:`API Reference <reference/index>` provides documentation of the
important functions and classes.


Supported Service Classes
=========================
*pynetdicom* currently supports the following `DICOM service classes
<http://dicom.nema.org/medical/dicom/current/output/chtml/part04/PS3.4.html>`_:

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


Applications
============

* :doc:`echoscu <apps/echoscu>`
* :doc:`echoscp <apps/echoscp>`
* :doc:`findscu <apps/findscu>`
* :doc:`getscu <apps/getscu>`
* :doc:`movescu <apps/movescu>`
* :doc:`storescu <apps/storescu>`
* :doc:`storescp <apps/storescp>`

Release Notes
=============

* :doc:`v1.5.0 </changelog/v1.5.0>`
* :doc:`v1.4.1 </changelog/v1.4.1>`
* :doc:`v1.4.0 </changelog/v1.4.0>`
* :doc:`v1.3.1 </changelog/v1.3.1>`
* :doc:`v1.3.0 </changelog/v1.3.0>`
* :doc:`v1.2.0 </changelog/v1.2.0>`
* :doc:`v1.1.0 </changelog/v1.1.0>`
* :doc:`v1.0.0 </changelog/v1.0.0>`


.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Documentation

   user/index
   tutorials/index
   service_classes/index
   reference/index

.. toctree::
   :maxdepth: 2
   :hidden:
   :caption: Examples

   examples/index

.. toctree::
   :maxdepth: 1
   :hidden:
   :caption: Additional Information

   apps/index
   changelog/index
