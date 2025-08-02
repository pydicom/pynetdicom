:orphan:

==================
Learning resources
==================


Tutorials
=========

Step-by-step tutorials on using *pynetdicom* to create your own Verification SCU and
Storage SCP.

.. toctree::
   :maxdepth: 1

   /tutorials/create_scu
   /tutorials/create_scp


Code examples
=============

Short service class-specific examples covering each of the DIMSE-C and DIMSE-N messages
types.

* :doc:`Basic Worklist Management (C-FIND) </examples/basic_worklist>`
* :doc:`Display System Management (N-GET) </examples/display>`
* Modality Performed Procedure Step Management

  * :doc:`MPPS (N-CREATE and N-SET) </examples/mpps>`
* Print Management

  * :doc:`Basic Grayscale Print Management (N-CREATE, N-SET, N-GET, N-DELETE, N-ACTION) </examples/print>`
* Query/Retrieve

  * :doc:`Query/Retrieve - Find (C-FIND) </examples/qr_find>`
  * :doc:`Query/Retrieve - Get (C-GET and C-STORE) </examples/qr_get>`
  * :doc:`Query/Retrieve - Move (C-MOVE and C-STORE) </examples/qr_move>`
* :doc:`Relevant Patient Information Query (C-FIND) </examples/relevant_patient>`
* :doc:`Storage (C-STORE) </examples/storage>`
* :doc:`Verification (C-ECHO) </examples/verification>`

Example applications
====================

While the following are all functional DICOM applications, their primary purpose is to
provide more advanced examples on how to use *pynetdicom*.

.. toctree::
   :maxdepth: 1

   /apps/echoscu
   /apps/echoscp
   /apps/findscu
   /apps/getscu
   /apps/movescu
   /apps/qrscp
   /apps/storescu
   /apps/storescp
