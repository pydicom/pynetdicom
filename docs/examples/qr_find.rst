Query/Retrieve (Find) Service Examples
--------------------------------------

The DICOM `Query/Retrieve Service <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_C>`_
provides a mechanism for a service user (an SCU) to request the SCP search its
managed SOP Instances.

of supported :ref:`Storage SOP Class Instances <storage_sops>` to
the service provider (the SCP). Transfer is accomplished by utilising the
DIMSE C-STORE service.

In essence, if you want to send or receive DICOM images or waveforms or any
other type of data supported by the Storage SOP Classes, then the Storage
Service is what you're looking for.

Query/Retrieve - FIND SCU
~~~~~~~~~~~~~~~~~~~~~~~~~

Associate with a peer DICOM Application Entity and request the SCP search for
SOP Instances with a PatientName matching 'CITIZEN^Jan' at the Patient level.

.. code-block:: python

   from pydicom import dcmread

   from pynetdicom3 import AE
   from pynetdicom3.sop_class import CTImageStorage

   # Initialise the Application Entity
   ae = AE()

   # Add a requested presentation context
   ae.add_requested_context(CTImageStorage)

   # Associate with peer AE at IP 127.0.0.1 and port 11112
   assoc = ae.associate('127.0.0.1', 11112)

   # Read in our DICOM CT dataset
   ds = dcmread('path/to/CT/dataset')

   if assoc.is_established:
       # Use the C-STORE service to send the dataset
       # returns a pydicom Dataset
       response = assoc.send_c_store(ds)

       # Check the status of the storage request
       if 'Status' in status:
           # If the storage request succeeded this will be 0x0000
           print('C-STORE request status: 0x{0:04x}'.format(status.Status))
       else:
           print('Connection timed out or invalid response from peer')

       # Release the association
       assoc.release()
   else:
       print('Association rejected or aborted')


Query/Retrieve - FIND SCP
~~~~~~~~~~~~~~~~~~~~~~~~~
