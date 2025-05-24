Query/Retrieve (Move) Service Examples
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The DICOM :dcm:`Query/Retrieve Service <part04/chapter_C.html>`
provides a mechanism for a service user to query and retrieve the SOP Instances
managed by a QR SCP. The QR (Move) SOP classes allow an SCU to request an SCP
send up to 65535 matching SOP Instances to a known Storage SCP over a new association.
This is accomplished through the DIMSE C-MOVE and C-STORE services.

One limitation of the C-MOVE service is that the Move SCP/Storage SCU must
know in advance the details (AE title, IP address, port number) of the
destination Storage SCP. If the Move SCP doesn't know the destination AE then
it will usually respond with an ``0xA801`` status code.


Query/Retrieve (Move) SCU
.........................

Associate with a peer DICOM Application Entity and request it send
all SOP Instances for the patient with *Patient ID* ``1234567`` belonging to the
series with *Study Instance UID* ``1.2.3`` and *Series Instance UID*
``1.2.3.4`` to a Storage SCP with AE title ``'STORE_SCP'``.

.. code-block:: python

    from pydicom.dataset import Dataset

    from pynetdicom import AE, debug_logger
    from pynetdicom.sop_class import PatientRootQueryRetrieveInformationModelMove

    debug_logger()

    # Initialise the Application Entity
    ae = AE()

    # Add a requested presentation context
    ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)

    # Create out identifier (query) dataset
    ds = Dataset()
    ds.QueryRetrieveLevel = 'SERIES'
    # Unique key for PATIENT level
    ds.PatientID = '1234567'
    # Unique key for STUDY level
    ds.StudyInstanceUID = '1.2.3'
    # Unique key for SERIES level
    ds.SeriesInstanceUID = '1.2.3.4'

    # Associate with peer AE at IP 127.0.0.1 and port 11112
    assoc = ae.associate("127.0.0.1", 11112)

    if assoc.is_established:
        # Use the C-MOVE service to send the identifier
        responses = assoc.send_c_move(ds, 'STORE_SCP', PatientRootQueryRetrieveInformationModelMove)
        for (status, identifier) in responses:
            if status:
                print(f"C-MOVE query status: 0x{status.Status:04x}")
            else:
                print('Connection timed out, was aborted or received invalid response')

        # Release the association
        assoc.release()
    else:
        print('Association rejected, aborted or never connected')

The responses received from the SCP include notifications on whether or not
the storage sub-operations have been successful.

In the next example we use a Storage SCP running within the same AE as the
*Move Destination*. Remember that the Move SCP must first be configured with
the IP and port number of the corresponding AE title. Check the
:func:`handler implementation documentation
<pynetdicom._handlers.doc_handle_store>`
to see the requirements for the ``evt.EVT_C_STORE`` handler.

.. code-block:: python

    from pydicom.dataset import Dataset

    from pynetdicom import AE, evt, StoragePresentationContexts, debug_logger
    from pynetdicom.sop_class import PatientRootQueryRetrieveInformationModelMove

    debug_logger()

    def handle_store(event):
        """Handle a C-STORE service request"""
        # Ignore the request and return Success
        return 0x0000

    handlers = [(evt.EVT_C_STORE, handle_store)]

    # Initialise the Application Entity
    ae = AE()

    # Add a requested presentation context
    ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)

    # Add the Storage SCP's supported presentation contexts
    ae.supported_contexts = StoragePresentationContexts

    # Start our Storage SCP in non-blocking mode, listening on port 11120
    ae.ae_title = 'OUR_STORE_SCP'
    scp = ae.start_server(("127.0.0.1", 11120), block=False, evt_handlers=handlers)

    # Create out identifier (query) dataset
    ds = Dataset()
    ds.QueryRetrieveLevel = 'SERIES'
    # Unique key for PATIENT level
    ds.PatientID = '1234567'
    # Unique key for STUDY level
    ds.StudyInstanceUID = '1.2.3'
    # Unique key for SERIES level
    ds.SeriesInstanceUID = '1.2.3.4'

    # Associate with peer AE at IP 127.0.0.1 and port 11112
    assoc = ae.associate("127.0.0.1", 11112)

    if assoc.is_established:
        # Use the C-MOVE service to send the identifier
        responses = assoc.send_c_move(ds, 'OUR_STORE_SCP', PatientRootQueryRetrieveInformationModelMove)

        for (status, identifier) in responses:
            if status:
                print(f"C-MOVE query status: 0x{status.Status:04x}")
            else:
                print('Connection timed out, was aborted or received invalid response')

        # Release the association
        assoc.release()
    else:
        print('Association rejected, aborted or never connected')

    # Stop our Storage SCP
    scp.shutdown()

.. _example_qrmove_scp:

Query/Retrieve (Move) SCP
.........................

The following represents a toy implementation of a Query/Retrieve (Move) SCP
where the SCU has sent the following *Identifier* dataset under the *Patient
Root Query Retrieve Information Model - Move* context and the move destination
AE title ``"STORE_SCP" is known to correspond to the IP address ``127.0.0.1``
and listen port number ``11113``.

.. code-block:: python

    ds = Dataset()
    ds.QueryRetrieveLevel = 'PATIENT'
    ds.PatientID = '1234567'

This is a very bad way of managing stored SOP Instances, in reality its
probably best to store the instance attributes in a database and run the
query against that, which is the approach taken by the
:doc:`qrscp application<../apps/qrscp>`.

Check the :func:`handler implementation documentation
<pynetdicom._handlers.doc_handle_move>` to see the requirements for the
``evt.EVT_C_MOVE`` handler.

.. code-block:: python

    import os

    from pydicom import dcmread
    from pydicom.dataset import Dataset

    from pynetdicom import AE, StoragePresentationContexts, evt
    from pynetdicom.sop_class import PatientRootQueryRetrieveInformationModelMove

    # Implement the evt.EVT_C_MOVE handler
    def handle_move(event):
        """Handle a C-MOVE request event."""
        ds = event.identifier

        if 'QueryRetrieveLevel' not in ds:
            # Failure
            yield 0xC000, None
            return

        # get_known_aet() is here to represent a user-implemented method of
        #   getting known AEs, for this example it returns a dict with the
        #   AE titles as keys
        known_aet_dict = get_known_aet()
        try:
            (addr, port) = known_aet_dict[event.move_destination]
        except KeyError:
            # Unknown destination AE
            yield (None, None)
            return

        # Yield the IP address and listen port of the destination AE
        yield (addr, port)

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
        yield len(matching)

        # Yield the matching instances
        for instance in matching:
            # Check if C-CANCEL has been received
            if event.is_cancelled:
                yield (0xFE00, None)
                return

            # Pending
            yield (0xFF00, instance)

    handlers = [(evt.EVT_C_MOVE, handle_move)]

    # Create application entity
    ae = AE()

    # Add the requested presentation contexts (Storage SCU)
    ae.requested_contexts = StoragePresentationContexts
    # Add a supported presentation context (QR Move SCP)
    ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)

    # Start listening for incoming association requests
    ae.start_server(("127.0.0.1", 11112), evt_handlers=handlers)

It's also possible to get more control over the association with the Storage
SCP that'll be receiving any matching datasets by yielding ``(addr, port,
kwargs)`` instead of ``(addr, port)``, where ``kwargs`` is a :class:`dict`
containing keyword parameters that'll be passed to
:meth:`AE.associate()<pynetdicom.ae.ApplicationEntity.associate>`. In
particular, this allows you to tailor the presentation contexts that will be
requested to the datasets matching the query (via the *contexts* keyword
parameter).
