.. _usecases:


====================================
Directly send DICOM data from python
====================================

pynetdicom allows to send DICOM data (datasets) directly from python
to a remote SCP.

=====================================
DICOM storage server
=====================================

Create a storage SCP which can accept DICOM data from remote SCUs. On
reception of the data, a user-defined callback function is called.

====================================
DICOM bridge
===================================
With pynetdicom, one can easily create a service that will accept DICOM
data from an AE A, process it and redirect it to some other AE B.

