=================
ApplicationEntity
=================

ApplicationEntity (or AE) is the main class for constructing a DICOM Application
Entity. 

Initialisation
==============

.. code-block:: python

        from pydicom.uid import ImplicitVRLittleEndian
        from pynetdicom3 import AE, VerificationSOPClass
        
        ae = AE(ae_title='PYNETDICOM', 
                port=11112, 
                scu_sop_class=[VerificationSOPClass], 
                scp_sop_class=[VerificationSOPClass],
                transfer_syntax=[ImplicitVRLittleEndian])

Service Class User
==================

Maximum PDU Size
----------------
Each association request can specify its own maximum PDU receive size. A value
of None indicates that there is no maximum size limit.
>>> ae = AE(scu_sop_class=[VerificationSOPClass]
>>> assoc1 = ae.associate('127.0.0.1', 11112, max_pdu=16382)
>>> assoc2 = ae.associate('127.0.0.1', 11112, max_pdu=None)

Service Class Provider
======================
The following parameters should be set prior to calling `start()`.

AE Title Matching
-----------------
The called and/or calling AE title can be set to be required to match against 
an expected value, with the association being rejected if they fail. A value
of '' means that no matching will be performed.
>>> ae = AE(port=11112, scp_sop_class=[VerificationSOPClass])
>>> ae.require_calling_aet = 'CALLING_AET'
>>> ae.require_called_aet = 'CALLED_AET'
>>> ae.start()

Maximum Number of Associations
------------------------------
The maximum number of simultaneous associations that the AE will support. Any
additional association requests be rejected with a reason of 
'Local limit exceeded'.
>>> ae = AE(port=11112, scp_sop_class=[VerificationSOPClass])
>>> ae.maximum_associations = 3
>>> ae.start()

Timeouts
--------
Timeouts for ACSE, DIMSE and network messages
>>> ae = AE(scu_sop_class=[VerificationSOPClass])
>>> ae.dimse_timeout = 30
>>> ae.acse_timeout = 60
>>> ae.network_timeout = 60
>>> ae.start()

Maximum PDU Size
----------------
A value of None indicates that there is no maximum PDU size limit.
>>> ae = AE(port=11112, scp_sop_class=[VerificationSOPClass]
>>> ae.maximum_pdu_size = 16382
>>> ae.start()


Association
===========
