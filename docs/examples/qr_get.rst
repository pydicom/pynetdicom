Query/Retrieve (Get) Service Examples
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The DICOM `Query/Retrieve Service <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_C>`_
provides a mechanism for a service user to query and retrieve the SOP Instances
managed by a QR SCP. The QR (Get) SOP classes allow an SCU to receive SOP
Instances that match the requested query. This is accomplished through the
DIMSE C-GET and C-STORE services. Both query and
retrieval occur over the same association, with the SCP of the Query/Retrieve
Service acting as the SCU of the Storage Service (and vice versa).

Query/Retrieve (Get) SCU
........................

Associate with a peer DICOM Application Entity and request the retrieval of
all CT datasets for the patient with *Patient ID* '1234567' belonging to the
series with *Study Instance UID* '1.2.3' and *Series Instance UID* '1.2.3.4'.

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
that during association we need to include a :py:class:`SCP/SCU Role Selection
Negotation <pynetdicom3.pdu_items.SCP_SCU_RoleSelectionSubItem>`
item for each of the supported presentation contexts that may be used with
the C-STORE requests.

If you're going to write SOP Instances (datasets) to file it's recommended
that you ensure the file is conformant with the
`DICOM File Format <http://dicom.nema.org/medical/dicom/current/output/html/part10.html#chapter_7>`_,
which requires adding the File Meta Information.

.. code-block:: python

    from pydicom.dataset import Dataset

    from pynetdicom3 import (
        AE,
        PYNETDICOM_IMPLEMENTATION_UID,
        PYNETDICOM_IMPLEMENTATION_VERSION
    )
    from pynetdicom3.pdu_primitives import SCP_SCU_RoleSelectionNegotiation
    from pynetdicom3.sop_class import (
        PatientRootQueryRetrieveInformationModelGet,
        CTImageStorage
    )

    # Initialise the Application Entity
    ae = AE()

    # Add the requested presentation contexts (QR SCU)
    ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
    # Add the requested presentation context (Storage SCP)
    ae.add_requested_context(CTImageStorage)

    # Add an SCP/SCU Role Selection Negotiation item for CT Image Storage
    role = SCP_SCU_RoleSelectionNegotiation()
    role.sop_class_uid = CTImageStorage
    # We will be acting as an SCP for CT Image Storage
    role.scp_role = True

    # Extended negotiation items
    ext_neg = [role]

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
        ds.save_as(ds.SOPInstanceUID, write_like_original=False)

        # Return a 'Success' status
        return 0x0000

    ae.on_c_store = on_c_store

    # Associate with peer AE at IP 127.0.0.1 and port 11112
    assoc = ae.associate('127.0.0.1', 11112, ext_neg=ext_neg)

    if assoc.is_established:
        # Use the C-GET service to send the identifier
        # A query_model value of 'P' means use the 'Patient Root Query Retrieve
        #     Information Model - Get' presentation context
        responses = assoc.send_c_get(ds, query_model='P')

        for (status, identifier) in responses:
            print('C-GET query status: 0x{0:04x}'.format(status.Status))

            # If the status is 'Pending' then identifier is the C-GET response
            if status.Status in (0xFF00, 0xFF01):
                print(identifier)

        # Release the association
        assoc.release()
    else:
        print('Association rejected or aborted')


The responses received from the SCP are dependent on the *Identifier* dataset
keys and values, the Query/Retrieve level and the information model.


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
query against that.

.. code-block:: python

    import os

    from pydicom import dcmread
    from pydicom.dataset import Dataset

    from pynetdicom3 import AE, StoragePresentationContexts
    from pynetdicom3.sop_class import PatientRootQueryRetrieveInformationModelGet

    # Create application entity
    ae = AE(port=11112)

    # Add the supported presentation contexts (Storage SCU)
    ae.supported_contexts = StoragePresentationContexts

    # Accept the association requestor's proposed SCP role in the
    #   SCP/SCU Role Selection Negotiation items
    for cx in self.supported_contexts:
        cx.scp_role = True
        cx.scu_role = False

    # Add a supported presentation context (QR Get SCP)
    ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)

    # Implement the AE.on_c_get callback
    def on_c_get(dataset, context, info):
        """Respond to a C-GET request Identifier `ds`.

        Parameters
        ----------
        dataset : pydicom.dataset.Dataset
            The Identifier dataset sent by the peer.
        context : presentation.PresentationContextTuple
            The presentation context that the C-GET message was sent under.
        info : dict
            A dict containing information about the current association.

        Yields
        ------
        int
            The first yielded value should be the total number of C-STORE
            sub-operations necessary to complete the C-GET operation. In other
            words, this is the number of matching SOP Instances to be sent to
            the peer.
        status : pydicom.dataset.Dataset or int
            The status returned to the peer AE in the C-GET response. Must be a
            valid C-GET status value for the applicable Service Class as either
            an ``int`` or a ``Dataset`` object containing (at a minimum) a
            (0000,0900) *Status* element. If returning a Dataset object then
            it may also contain optional elements related to the Status (as in
            DICOM Standard Part 7, Annex C).
        dataset : pydicom.dataset.Dataset or None
            If the status is 'Pending' then yield the ``Dataset`` to send to
            the peer via a C-STORE sub-operation over the current association.

            If the status is 'Failed', 'Warning' or 'Cancel' then yield a
            ``Dataset`` with a (0008,0058) *Failed SOP Instance UID List*
            element containing a list of the C-STORE sub-operation SOP Instance
            UIDs for which the C-GET operation has failed.

            If the status is 'Success' then yield ``None``, although yielding a
            final 'Success' status is not required and will be ignored if
            necessary
        """
        if 'QueryRetrieveLevel' not in ds:
            # Failure
            yield 0xC000, None
            return

        # Import stored SOP Instances
        instances = []
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


    ae.on_c_get = on_c_get

    # Start listening for incoming association requests
    ae.start()
