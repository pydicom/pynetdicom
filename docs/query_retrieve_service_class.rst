Query/Retrieve Service Class
============================
The Query/Retrieve Service Class defines a service that facilitates querying
and retrieval of stored Instances. This allows a DICOM Application Entity (AE)
to retrieve Instances from a remote AE or request the remote AE initiate
transfer of Instances to another DICOM AE by using the C-FIND, C-GET and C-MOVE
DIMSE-C services.

Supported SOP Classes
---------------------

* PatientRootQueryRetrieveInformationModelFind - 1.2.840.10008.5.1.4.1.2.1.1
* StudyRootQueryRetrieveInformationModelFind - 1.2.840.10008.5.1.4.1.2.2.1
* PatientStudyOnlyQueryRetrieveInformationModelFind - 1.2.840.10008.5.1.4.1.2.3.1
* ModalityWorklistInformationFind - 1.2.840.10008.5.1.4.31
* PatientRootQueryRetrieveInformationModelMove - 1.2.840.10008.5.1.4.1.2.1.2
* StudyRootQueryRetrieveInformationModelMove - 1.2.840.10008.5.1.4.1.2.2.2
* PatientStudyOnlyQueryRetrieveInformationModelMove - 1.2.840.10008.5.1.4.1.2.3.2
* PatientRootQueryRetrieveInformationModelGet - 1.2.840.10008.5.1.4.1.2.1.3
* StudyRootQueryRetrieveInformationModelGet - 1.2.840.10008.5.1.4.1.2.2.3
* PatientStudyOnlyQueryRetrieveInformationModelGet - 1.2.840.10008.5.1.4.1.2.3.3

References
----------
DICOM Standard, Part 4, `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_C>`_
