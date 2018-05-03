.. _datasets:

The DICOM Dataset
=================

A DICOM data set is constructed of one or more :ref:`Data Elements <elements>`.
The Elements within a Dataset are ordered by increasing Element Tag number and
each element occurs at most once in a Dataset, however an Element may occur
again within nested Datasets (i.e. within Sequences).


References
----------

1. DICOM Standard, Part 5, Section `7 <http://dicom.nema.org/medical/dicom/current/output/html/part05.html#chapter_7>`_
