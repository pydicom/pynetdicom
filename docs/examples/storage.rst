Storage Service Examples
~~~~~~~~~~~~~~~~~~~~~~~~

The DICOM `Storage Service <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_B>`_
provides a mechanism for an SCU to request the transfer
of supported :ref:`Storage SOP Class <storage_sops>` instances to
the service provider. Transfer is accomplished by utilising the
DIMSE C-STORE service.

In essence, if you want to send or receive DICOM images or waveforms or any
other type of data supported by the Storage SOP Classes, then the Storage
Service is what you're looking for.

Storage SCU
...........

Associate with a peer DICOM Application Entity and request the transfer of a
single CT dataset.

.. code-block:: python

   from pydicom import dcmread

   from pynetdicom3 import AE
   from pynetdicom3.sop_class import CTImageStorage

   # Initialise the Application Entity
   ae = AE()

   # Add a requested presentation context
   ae.add_requested_context(CTImageStorage)

   # Read in our DICOM CT dataset
   ds = dcmread('path/to/dataset')

   # Associate with peer AE at IP 127.0.0.1 and port 11112
   assoc = ae.associate('127.0.0.1', 11112)

   if assoc.is_established:
       # Use the C-STORE service to send the dataset
       # returns a pydicom Dataset
       status = assoc.send_c_store(ds)

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

Of course it's rarely the case that someone wants to store just CT images,
so you can also use the inbuilt ``StoragePresentationContexts`` when setting
the requested contexts or just add as many contexts as you need.

.. code-block:: python

   from pynetdicom3 import AE, StoragePresentationContexts

   ae = AE()
   ae.requested_contexts = StoragePresentationContexts

You can also set the requested contexts on a per association basis.

.. code-block:: python

   from pydicom import dcmread

   from pynetdicom3 import AE, build_context
   from pynetdicom3.sop_class import CTImageStorage, MRImageStorage

   # Initialise the Application Entity
   ae = AE()

   # Create some presentation contexts
   ct_context = build_context(CTImageStorage)
   mr_context = build_context(MRImageStorage)

   # Associate with peer AE at IP 127.0.0.1 and port 11112
   assoc = ae.associate('127.0.0.1', 11112, contexts=[ct_context])
   assoc.release()

   assoc = ae.associate('127.0.0.1', 11112, contexts=[mr_context])
   assoc.release()


Storage SCP
...........

Create an :ref:`AE <ae>` that supports the Storage Service and then
listen for association requests on port 11112. When a storage request is
received over the association we write the dataset to file and then return
a 0x0000 *Success* :ref:`status <storage_statuses>`.

If you're going to write SOP instances (datasets) to file it's recommended
that you ensure the file is conformant with the
`DICOM File Format <http://dicom.nema.org/medical/dicom/current/output/html/part10.html#chapter_7>`_,
which requires adding the File Meta Information.

.. code-block:: python

   from pydicom.dataset import Dataset

   from pynetdicom3 import (
       AE,
       StoragePresentationContexts,
       PYNETDICOM_IMPLEMENTATION_UID,
       PYNETDICOM_IMPLEMENTATION_VERSION
   )

   # Initialise the Application Entity and specify the listen port
   ae = AE(port=11112)

   # Add the supported presentation contexts
   ae.supported_contexts = StoragePresentationContexts

   # Implement the AE.on_c_store callback
   def on_c_store(ds, context, info):
       """Store the pydicom Dataset `ds`.

       Parameters
       ----------
       ds : pydicom.dataset.Dataset
           The dataset that the peer has requested be stored.
       context : namedtuple
           The presentation context that the dataset was sent under.
       info : dict
           Information about the association and storage request.

       Returns
       -------
       status : int or pydicom.dataset.Dataset
           The status returned to the peer AE in the C-STORE response. Must be
           a valid C-STORE status value for the applicable Service Class as
           either an ``int`` or a ``Dataset`` object containing (at a
           minimum) a (0000,0900) *Status* element.
       """
       # Add the DICOM File Meta Information
       meta = Dataset()
       meta.MediaStorageSOPClassUID = ds.SOPClassUID
       meta.MediaStorageSOPInstanceUID = ds.SOPInstanceUID
       meta.ImplementationClassUID = PYNETDICOM_IMPLEMENTATION_UID
       meta.ImplementationVersionName = PYNETDICOM_IMPLEMENTATION_VERSION
       meta.TransferSyntaxUID = context.transfer_syntax

       # Add the file meta to the dataset
       ds.file_meta = meta

       # Set the transfer syntax attributes of the dataset
       ds.is_little_endian = context.transfer_syntax.is_little_endian
       ds.is_implicit_VR = context.transfer_syntax.is_implicit_VR

       # Save the dataset using the SOP Instance UID as the filename
       ds.save_as(ds.SOPInstanceUID)

       # Return a 'Success' status
       return 0x0000

   ae.on_c_store = on_c_store

   # Start listening for incoming association requests
   ae.start()

As with the SCU you can also just support only the contexts you're
interested in.

.. code-block:: python

   from pynetdicom3 import AE
   from pynetdicom3.sop_class import CTImageStorage

   ae = AE(port=11112)

   # Add a supported presentation context
   ae.add_supported_context(CTImageStorage)

   def on_c_store(ds, context, info):
       # Don't store anything but respond with `Success`
       return 0x0000

   ae.on_c_store = on_c_store

   ae.start()
