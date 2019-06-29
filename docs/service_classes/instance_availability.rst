Instance Availability Notification Service Class
================================================
The `Instance Availability Notification Service Class
<http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_R>`_
defines a service that uses the DIMSE N-CREATE service to allow one AE to
notify another AE of the presence and availability of SOP instances that may
be retrieved.

.. _instance_sops:

Supported SOP Classes
---------------------

+------------------------+--------------------------------------------------+
| UID                    | SOP Class                                        |
+========================+==================================================+
| 1.2.840.10008.5.1.4.33 | InstanceAvailabilityNotificationSOPClass         |
+------------------------+--------------------------------------------------+


DIMSE Services
--------------

+-----------------+-----------------------------------------+
| DIMSE Service   | Usage SCU/SCP                           |
+=================+=========================================+
| N-CREATE        | Mandatory/Mandatory                     |
+-----------------+-----------------------------------------+

.. _instance_statuses:

Statuses
--------

N-CREATE Statuses
~~~~~~~~~~~~~~~~~

+------------------+----------+-----------------------------------------------+
| Code (hex)       | Category | Description                                   |
+==================+==========+===============================================+
| 0x0000           | Success  | Success                                       |
+------------------+----------+-----------------------------------------------+
| 0x0105           | Failure  | No such attribute                             |
+------------------+----------+-----------------------------------------------+
| 0x0106           | Failure  | Invalid attribute value                       |
+------------------+----------+-----------------------------------------------+
| 0x0107           | Failure  | Attribute list error                          |
+------------------+----------+-----------------------------------------------+
| 0x0110           | Failure  | Processing failure                            |
+------------------+----------+-----------------------------------------------+
| 0x0111           | Failure  | Duplicate SOP Instance                        |
+------------------+----------+-----------------------------------------------+
| 0x0116           | Failure  | Attribute value out of range                  |
+------------------+----------+-----------------------------------------------+
| 0x0117           | Failure  | Invalid object instance                       |
+------------------+----------+-----------------------------------------------+
| 0x0118           | Failure  | No such SOP Class                             |
+------------------+----------+-----------------------------------------------+
| 0x0120           | Failure  | Missing attribute                             |
+------------------+----------+-----------------------------------------------+
| 0x0121           | Failure  | Missing attribute value                       |
+------------------+----------+-----------------------------------------------+
| 0x0124           | Failure  | Refused: not authorised                       |
+------------------+----------+-----------------------------------------------+
| 0x0210           | Failure  | Duplicate invocation                          |
+------------------+----------+-----------------------------------------------+
| 0x0211           | Failure  | Unrecognised operation                        |
+------------------+----------+-----------------------------------------------+
| 0x0212           | Failure  | Mistyped argument                             |
+------------------+----------+-----------------------------------------------+
| 0x0213           | Failure  | Resource limitation                           |
+------------------+----------+-----------------------------------------------+


References
----------

* DICOM Standard, Part 4, `Annex R <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_R>`_
* DICOM Standard, Part 7, `Section 10.1.5.1.6 <http://dicom.nema.org/medical/dicom/current/output/chtml/part07/chapter_10.html#sect_10.1.5.1.6>`_
