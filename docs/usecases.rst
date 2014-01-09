.. _usecases:

=================
Typical use cases
=================


Send DICOM data from python
===========================
pynetdicom allows DICOM data (datasets) to be sent to a remote SCP
directly from python.

:download:`get source (storescu.py) <../source/netdicom/examples/storescu.py>`

.. literalinclude:: ../source/netdicom/examples/storescu.py
    :language: python


Receive DICOM data from python
==============================
Create a storage SCP which can accept DICOM data from remote SCUs. On
reception of the data, a user-defined callback function is called.

:download:`get source (storescp.py) <../source/netdicom/examples/storescp.py>`

.. literalinclude:: ../source/netdicom/examples/storescp.py
    :language: python


Query/Retrieve from python
==========================
Here is how to query and retrieve some dataset from a Q/R SCP.

:download:`get source (qrscu.py) <../source/netdicom/examples/qrscu.py>`

.. literalinclude:: ../source/netdicom/examples/qrscu.py
    :language: python

.. ====================================
.. DICOM bridge
.. ===================================
.. With pynetdicom, one can easily create a service that will accept DICOM
.. data from an AE A, process it and redirect it to some other AE B.

