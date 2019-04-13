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

    from pynetdicom import AE
    from pynetdicom.sop_class import CTImageStorage

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
        # returns the response status as a pydicom Dataset
        status = assoc.send_c_store(ds)

        # Check the status of the storage request
        if status:
            # If the storage request succeeded this will be 0x0000
            print('C-STORE request status: 0x{0:04x}'.format(status.Status))
        else:
            print('Connection timed out, was aborted or received invalid response')

        # Release the association
        assoc.release()
    else:
        print('Association rejected, aborted or never connected')

Of course it's rarely the case that someone wants to store just CT images,
so you can also use the inbuilt ``StoragePresentationContexts`` when setting
the requested contexts or just add as many contexts as you need.

.. code-block:: python

    from pynetdicom import AE, StoragePresentationContexts

    ae = AE()
    ae.requested_contexts = StoragePresentationContexts

You can also set the requested contexts on a per association basis.

.. code-block:: python

    from pydicom import dcmread

    from pynetdicom import AE, build_context
    from pynetdicom.sop_class import CTImageStorage, MRImageStorage

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

.. _example_storage_scp:

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

Check the
`handler implementation documentation
<../reference/generated/pynetdicom._handlers.doc_handle_store.html>`_
to see the requirements for the ``evt.EVT_C_STORE`` handler.

.. code-block:: python

    from pydicom.dataset import Dataset

    from pynetdicom import (
        AE, evt,
        StoragePresentationContexts,
        PYNETDICOM_IMPLEMENTATION_UID,
        PYNETDICOM_IMPLEMENTATION_VERSION
    )

    # Implement a handler evt.EVT_C_STORE
    def handle_store(event):
        """Handle a C-STORE request event."""
        # Decode the C-STORE request's *Data Set* parameter to a pydicom Dataset
        ds = event.dataset

        # Add the File Meta Information
        ds.file_meta = event.file_meta

        # Save the dataset using the SOP Instance UID as the filename
        ds.save_as(ds.SOPInstanceUID, write_like_original=False)

        # Return a 'Success' status
        return 0x0000

    handlers = [(evt.EVT_C_STORE, handle_store)]

    # Initialise the Application Entity
    ae = AE()

    # Add the supported presentation contexts
    ae.supported_contexts = StoragePresentationContexts

    # Start listening for incoming association requests
    ae.start_server(('', 11112), evt_handlers=handlers)

As with the SCU you can also just support only the contexts you're
interested in.

.. code-block:: python

    from pynetdicom import AE, evt
    from pynetdicom.sop_class import CTImageStorage

    ae = AE()

    # Add a supported presentation context
    ae.add_supported_context(CTImageStorage)

    def handle_store(event):
        # Don't store anything but respond with `Success`
        return 0x0000

    handlers = [(evt.EVT_C_STORE, handle_store)]

    ae.start_server(('', 11112), evt_handlers=handlers)

You can also start the SCP in non-blocking mode:

.. code-block:: python

    from pynetdicom import AE, evt
    from pynetdicom.sop_class import CTImageStorage

    def handle_store(event):
        return 0x0000

    handlers = [(evt.EVT_C_STORE, handle_store)]

    ae = AE()
    ae.add_supported_context(CTImageStorage)
    scp = ae.start_server(('', 11112), block=False evt_handlers=handlers)

    # Zzzz
    time.sleep(60)

    scp.shutdown()
