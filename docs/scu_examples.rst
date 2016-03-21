
===========================
Service Class User Examples
===========================


Verification SCU
================
The most basic way of verifying and troubleshooting a connection with a peer
Application Entity (AE) is to send a DICOM C-ECHO, which utilises the 
*Verification SOP Class*

.. code-block:: python 

        from pynetdicom import AE
        
        # The Verification SOP Class has a UID of 1.2.840.10008.1.1
        ae = AE(scu_sop_class=['1.2.840.10008.1.1'])
        
        # Try and associate with the peer AE
        #   Returns the Association thread
        print('Requesting Association with the peer')
        assoc = ae.associate(addr, port)
        
        if assoc.is_established:
            print('Association accepted by the peer')
            # Send a DIMSE C-ECHO request to the peer
            assoc.send_c_echo()
        
            # Release the association
            assoc.release()
        elif assoc.is_rejected:
            print('Association was rejected by the peer')
        elif assoc.is_aborted:
            print('Received an A-ABORT from the peer during Association')

Storage SCU
===========
A common use of a DICOM SCU is to use a DICOM C-STORE message to send DICOM 
datasets to peer AEs. 

.. code-block:: python 

        from pydicom import read_file
        from pynetdicom import AE
        from pynetdicom import StorageSOPClassList
        
        # StorageSOPClassList contains all the Standard SOP Classes supported
        #   by the Storage Service Class (see PS3.4 Annex B.5)
        ae = AE(scu_sop_class=StorageSOPClassList)
        
        # Try and associate with the peer AE
        #   Returns the Association thread
        print('Requesting Association with the peer')
        assoc = ae.associate(addr, port)
        
        if assoc.is_established:
            print('Association accepted by the peer')
            
            # Read the DICOM dataset from file 'dcmfile'
            dataset = read_file('dcmfile')
            
            # Send a DIMSE C-STORE request to the peer
            status = assoc.send_c_echo(dataset)
            print('C-STORE status: %s' %status)
            
            # Release the association
            assoc.release()


Query/Retrieve - Find SCU
=========================
Query the peer AE to see if it contains any Instances with attributes matching
those specified by the user-created *dataset*.

.. code-block:: python 

        from pydicom.dataset import Dataset

        from pynetdicom import AE
        from pynetdicom import QueryRetrieveSOPClassList
        
        # QueryRetrieveSOPClassList contains the SOP Classes supported
        #   by the Query/Retrieve Service Class (see PS3.4 Annex C.6)
        ae = AE(scu_sop_class=QueryRetrieveSOPClassList)
        
        # Try and associate with the peer AE
        #   Returns the Association thread
        print('Requesting Association with the peer')
        assoc = ae.associate(addr, port)
        
        if assoc.is_established:
            print('Association accepted by the peer')
            
            # Creat a new DICOM dataset with the attributes to match against
            #   In this case match any patient's name at the PATIENT query 
            #   level. See PS3.4 Annex C.6 for the complete list of possible 
            #   attributes and query levels.
            dataset = Dataset()
            dataset.PatientsName = '*'
            dataset.QueryRetrieveLevel = "PATIENT"
            
            # Send a DIMSE C-FIND request to the peer
            responses = assoc.send_c_find(dataset)
            
            for rsp in responses:
                # Waiting for more detailed QR.SCU status implementation 
                #   Issue #18
                pass
            
            # Release the association
            assoc.release()
