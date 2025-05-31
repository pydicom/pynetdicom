Query/Retrieve (Get) Service Examples
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The DICOM :dcm:`Query/Retrieve Service <part04/chapter_C.html>`
provides a mechanism for a service user to query and retrieve the SOP Instances
managed by a QR SCP. The QR (Get) SOP classes allow an SCU to receive up to 65535 SOP
Instances that match the requested query. This is accomplished through the
DIMSE C-GET and C-STORE services. Both query and
retrieval occur over the same association, with the SCP of the Query/Retrieve
Service acting as the SCU of the Storage Service (and vice versa).

Query/Retrieve (Get) SCU
........................

Associate with a peer DICOM Application Entity and request the retrieval of
all CT datasets for the patient with *Patient ID* ``1234567`` belonging to the
series with *Study Instance UID* ``1.2.3`` and *Series Instance UID*
``1.2.3.4``.

The value of the *Query Retrieve Level* determines what SOP Instances are
actually transferred; to transfer all datasets in the series we use
the SERIES level.

+--------------------+--------------------------------------------------------+
| Query Retrieve     |                                                        |
| Level              | Effect                                                 |
+====================+========================================================+
| PATIENT            | All SOP Instances related to a patient shall be        |
|                    | transferred                                            |
+--------------------+--------------------------------------------------------+
| STUDY              | All SOP Instances related to a study shall be          |
|                    | transferred                                            |
+--------------------+--------------------------------------------------------+
| SERIES             | All SOP Instances related to a series shall be         |
|                    | transferred                                            |
+--------------------+--------------------------------------------------------+
| IMAGE              | Selected individual SOP Instances shall be transferred |
+--------------------+--------------------------------------------------------+

One extra step needed with the Query/Retrieve (Get) Service is
that during association we need to include a :class:`SCP/SCU Role Selection
Negotiation <pynetdicom.pdu_items.SCP_SCU_RoleSelectionSubItem>`
item for each of the supported presentation contexts that may be used with
the C-STORE requests.

If you're going to write SOP Instances (datasets) to file it's recommended
that you ensure the file is conformant with the
:dcm:`DICOM File Format <part10/chapter_7.html>`, which requires adding the
File Meta Information.

Check the
:func:`handler implementation documentation
<pynetdicom._handlers.doc_handle_store>`
to see the requirements for the ``evt.EVT_C_STORE`` handler.

.. code-block:: python

    from pydicom.dataset import Dataset

    from pynetdicom import AE, evt, build_role, debug_logger
    from pynetdicom.sop_class import (
        PatientRootQueryRetrieveInformationModelGet,
        CTImageStorage
    )

    debug_logger()

    # Implement the handler for evt.EVT_C_STORE
    def handle_store(event):
        """Handle a C-STORE request event."""
        ds = event.dataset
        ds.file_meta = event.file_meta

        # Save the dataset using the SOP Instance UID as the filename
        ds.save_as(ds.SOPInstanceUID, write_like_original=False)

        # Return a 'Success' status
        return 0x0000

    handlers = [(evt.EVT_C_STORE, handle_store)]

    # Initialise the Application Entity
    ae = AE()

    # Add the requested presentation contexts (QR SCU)
    ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
    # Add the requested presentation context (Storage SCP)
    ae.add_requested_context(CTImageStorage)

    # Create an SCP/SCU Role Selection Negotiation item for CT Image Storage
    role = build_role(CTImageStorage, scp_role=True)

    # Create our Identifier (query) dataset
    # We need to supply a Unique Key Attribute for each level above the
    #   Query/Retrieve level
    ds = Dataset()
    ds.QueryRetrieveLevel = 'SERIES'
    # Unique key for PATIENT level
    ds.PatientID = '1234567'
    # Unique key for STUDY level
    ds.StudyInstanceUID = '1.2.3'
    # Unique key for SERIES level
    ds.SeriesInstanceUID = '1.2.3.4'

    # Associate with peer AE at IP 127.0.0.1 and port 11112
    assoc = ae.associate("127.0.0.1", 11112, ext_neg=[role], evt_handlers=handlers)

    if assoc.is_established:
        # Use the C-GET service to send the identifier
        responses = assoc.send_c_get(ds, PatientRootQueryRetrieveInformationModelGet)
        for (status, identifier) in responses:
            if status:
                print(f"C-GET query status: 0x{status.Status:04x}")
            else:
                print('Connection timed out, was aborted or received invalid response')

        # Release the association
        assoc.release()
    else:
        print('Association rejected, aborted or never connected')


The responses received from the SCP are dependent on the *Identifier* dataset
keys and values, the Query/Retrieve level and the information model.

.. _example_qrget_scp:

Query/Retrieve (Get) SCP
........................

The following represents a toy implementation of a Query/Retrieve (Get) SCP
where the SCU has sent the following *Identifier* dataset under the *Patient
Root Query Retrieve Information Model - Get* context.

.. code-block:: python

    ds = Dataset()
    ds.QueryRetrieveLevel = 'PATIENT'
    ds.PatientID = '1234567'

This is a very bad way of managing stored SOP Instances, in reality its
probably best to store the instance attributes in a database and run the
query against that, which is the approach taken by the
:doc:`qrscp application<../apps/qrscp>`.

Check the
:func:`handler implementation documentation
<pynetdicom._handlers.doc_handle_c_get>` to see the requirements for the
``evt.EVT_C_GET`` handler.

.. code-block:: python

    import os

    from pydicom import dcmread
    from pydicom.dataset import Dataset

    from pynetdicom import AE, StoragePresentationContexts, evt
    from pynetdicom.sop_class import PatientRootQueryRetrieveInformationModelGet

    # Implement the handler for evt.EVT_C_GET
    def handle_get(event):
        """Handle a C-GET request event."""
        ds = event.identifier
        if 'QueryRetrieveLevel' not in ds:
            # Failure
            yield 0xC000, None
            return

        # Import stored SOP Instances
        instances = []
        matching = []
        fdir = '/path/to/directory'
        for fpath in os.listdir(fdir):
            instances.append(dcmread(os.path.join(fdir, fpath)))

        if ds.QueryRetrieveLevel == 'PATIENT':
            if 'PatientID' in ds:
                matching = [
                    inst for inst in instances if inst.PatientID == ds.PatientID
                ]

            # Skip the other possible attributes...

        # Skip the other QR levels...

        # Yield the total number of C-STORE sub-operations required
        yield len(instances)

        # Yield the matching instances
        for instance in matching:
            # Check if C-CANCEL has been received
            if event.is_cancelled:
                yield (0xFE00, None)
                return

            # Pending
            yield (0xFF00, instance)

    handlers = [(evt.EVT_C_GET, handle_get)]

    # Create application entity
    ae = AE()

    # Add the supported presentation contexts (Storage SCU)
    ae.supported_contexts = StoragePresentationContexts

    # Accept the association requestor's proposed SCP role in the
    #   SCP/SCU Role Selection Negotiation items
    for cx in ae.supported_contexts:
        cx.scp_role = True
        cx.scu_role = False

    # Add a supported presentation context (QR Get SCP)
    ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)

    # Start listening for incoming association requests
    ae.start_server(("127.0.0.1", 11112), evt_handlers=handlers)
