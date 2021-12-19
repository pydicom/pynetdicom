Query/Retrieve (Move) Service Examples
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The DICOM `Query/Retrieve Service <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_C>`_
provides a mechanism for a service user to query and retrieve the SOP Instances
managed by a QR SCP. The QR (Move) SOP classes allow an SCU to request an SCP
send matching SOP Instances to a known Storage SCP over a new association.
This is accomplished through the DIMSE C-MOVE and C-STORE services.

One limitation of the C-MOVE service is that the Move SCP/Storage SCU must
know in advance the details (AE title, IP address, port number) of the
destination Storage SCP. If the Move SCP doesn't know the destination AE then
it will usually respond with an ``0xA801`` status code.

With *pynetdicom* its possible to start a non-blocking Storage SCP and use
that as the destination for a C-MOVE request sent by the same AE instance.

Query/Retrieve (Move) SCU
.........................

Associate with a peer DICOM Application Entity and request it send
all SOP Instances for the patient with *Patient ID* ``1234567`` belonging to the
series with *Study Instance UID* ``1.2.3`` and *Series Instance UID*
``1.2.3.4`` to a Storage SCP with AE title ``b'STORE_SCP'``.

.. code-block:: python

    from pydicom.dataset import Dataset

    from pynetdicom import AE
    from pynetdicom.sop_class import PatientRootQueryRetrieveInformationModelMove

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
    assoc = ae.associate('127.0.0.1', 11112)

    if assoc.is_established:
        # Use the C-MOVE service to send the identifier
        # A query_model value of 'P' means use the 'Patient Root Query
        #   Retrieve Information Model - Move' presentation context
        responses = assoc.send_c_move(ds, b'STORE_SCP', query_model='P')

        for (status, identifier) in responses:
            if status:
                print('C-MOVE query status: 0x{0:04x}'.format(status.Status))

                # If the status is 'Pending' then the identifier is the C-MOVE response
                if status.Status in (0xFF00, 0xFF01):
                    print(identifier)
            else:
                print('Connection timed out, was aborted or received invalid response')

        # Release the association
        assoc.release()
    else:
        print('Association rejected, aborted or never connected')

The responses received from the SCP include notifications on whether or not
the storage sub-operations have been successful.

Do the same thing, but send the SOP Instances to a non-blocking Storage SCP
being run from the same AE as the C-MOVE request:

.. code-block:: python

    from pydicom.dataset import Dataset

    from pynetdicom import AE, StoragePresentationContexts
    from pynetdicom.sop_class import PatientRootQueryRetrieveInformationModelMove

    # Initialise the Application Entity
    ae = AE()

    # Add the storage SCP's supported presentation contexts
    ae.supported_contexts = StoragePresentationContexts

    # Implement the on_c_store callback
    def on_c_store(ds, context, info):
        # Don't store anything, just return Success
        return 0x0000

    # Start the storage SCP on port 11113
    ae.ae_title = b'STORE_SCP'
    ae.on_c_store = on_c_store
    scp = ae.start_server(('', 11113), block=False)

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
    # Note: the peer AE must know the IP and port for our move destination
    assoc = ae.associate('127.0.0.1', 11112)

    if assoc.is_established:
        responses = assoc.send_c_move(ds, b'STORE_SCP', query_model='P')

        for (status, identifier) in responses:
            if status:
                print('C-MOVE query status: 0x{0:04x}'.format(status.Status))
                if status.Status in (0xFF00, 0xFF01):
                    print(identifier)
            else:
                print('Connection timed out, was aborted or received invalid response')

        assoc.release()
    else:
        print('Association rejected, aborted or never connected')

    # Shutdown the storage SCP
    scp.shutdown()


Query/Retrieve (Move) SCP
.........................

The following represents a toy implementation of a Query/Retrieve (Move) SCP
where the SCU has sent the following *Identifier* dataset under the *Patient
Root Query Retrieve Information Model - Move* context and the move destination
AE title ``b'STORE_SCP`` is known to correspond to the IP address ``127.0.0.1``
and listen port number ``11113``.

.. code-block:: python

    ds = Dataset()
    ds.QueryRetrieveLevel = 'PATIENT'
    ds.PatientID = '1234567'

This is a very bad way of managing stored SOP Instances, in reality its
probably best to store the instance attributes in a database and run the
query against that.

.. code-block:: python

    import os

    from pydicom import dcmread
    from pydicom.dataset import Dataset

    from pynetdicom import AE, StoragePresentationContexts
    from pynetdicom.sop_class import PatientRootQueryRetrieveInformationModelMove

    # Create application entity
    ae = AE()

    # Add the requested presentation contexts (Storage SCU)
    ae.requested_contexts = StoragePresentationContexts
    # Add a supported presentation context (QR Move SCP)
    ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)

    # Implement the AE.on_c_move callback
    def on_c_move(self, ds, move_aet, context, info):
        """Respond to a C-MOVE request Identifier `ds`.

        Parameters
        ----------
        ds : pydicom.dataset.Dataset
            The Identifier dataset sent by the peer.
        move_aet : bytes
            The destination AE title that matching SOP Instances will be sent
            to using C-STORE sub-operations. ``move_aet`` will be a correctly
            formatted AE title (16 chars, with trailing spaces as padding).
        context : presentation.PresentationContextTuple
            The presentation context that the C-MOVE message was sent under.
        info : dict
            A dict containing information about the current association.

        Yields
        ------
        addr, port : str, int or None, None
            The first yield should be the TCP/IP address and port number of the
            destination AE (if known) or ``(None, None)`` if unknown. If
            ``(None, None)`` is yielded then the SCP will send a C-MOVE
            response with a 'Failure' Status of ``0xA801`` (move destination
            unknown), in which case nothing more needs to be yielded.
        int
            The second yield should be the number of C-STORE sub-operations
            required to complete the C-MOVE operation. In other words, this is
            the number of matching SOP Instances to be sent to the peer.
        status : pydiom.dataset.Dataset or int
            The status returned to the peer AE in the C-MOVE response. Must be
            a valid C-MOVE status value for the applicable Service Class as
            either an ``int`` or a ``Dataset`` containing (at a minimum) a
            (0000,0900) *Status* element. If returning a ``Dataset`` then it
            may also contain optional elements related to the Status (as in
            DICOM Standard Part 7, Annex C).
        dataset : pydicom.dataset.Dataset or None
            If the status is 'Pending' then yield the ``Dataset``
            to send to the peer via a C-STORE sub-operation over a new
            association.

            If the status is 'Failed', 'Warning' or 'Cancel' then yield a
            ``Dataset`` with a (0008,0058) *Failed SOP Instance UID List*
            element containing the list of the C-STORE sub-operation SOP
            Instance UIDs for which the C-MOVE operation has failed.

            If the status is 'Success' then yield ``None``, although yielding a
            final 'Success' status is not required and will be ignored if
            necessary.
        """
        if 'QueryRetrieveLevel' not in ds:
            # Failure
            yield 0xC000, None
            return

        # Check move_aet is known
        # get_known_aet() is here to represent a user-implemented method of
        #   getting known AEs
        known_aet_dict = get_known_aet()
        if move_aet not in known_aet_dict:
            # Unknown destination AE
            yield (None, None)
            return

        # Assuming known_ae_dict is {b'STORE_SCP       ' : ('127.0.0.1', 11113)}
        (addr, port) = known_ae_dict[move_ae]

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
        yield len(instances)

        # Yield the matching instances
        for instance in matching:
            # Pending
            yield (0xFF00, instance)

    ae.on_c_move = on_c_move

    # Start listening for incoming association requests
    ae.start_server(('', 11112))
