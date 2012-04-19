.. _usecases:

=================
Typical use cases
=================


Directly send DICOM data from python
====================================

pynetdicom allows DICOM data (datasets) to be sent to a remote SCP
directly from python.

.. literalinclude:: examples/storescu.py
    :language: python



DICOM storage server
=====================================
Create a storage SCP which can accept DICOM data from remote SCUs. On
reception of the data, a user-defined callback function is called.

.. literalinclude:: examples/storescp.py
    :language: python

Query
=====
You can query a Q/R SCP for available data

.. literalinclude:: examples/findscu.py
    :language: python


Query/Retrieve
==============
Here is how to query and retrieve some dataset from a Q/R SCP.

.. literalinclude:: examples/qrscu.py
    :language: python

.. ====================================
.. DICOM bridge
.. ===================================
.. With pynetdicom, one can easily create a service that will accept DICOM
.. data from an AE A, process it and redirect it to some other AE B.

