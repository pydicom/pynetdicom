Query/Retrieve (Find) Service Examples
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The DICOM `Query/Retrieve Service <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_C>`_
provides a mechanism for a service user to query the SOP Instances managed
by a QR SCP. The QR (Find) SOP classes allow an SCU to receive a list of
attributes matching the requested query. This is accomplished through the
DIMSE C-FIND service.


Query/Retrieve (Find) SCU
.........................

Associate with a peer DICOM Application Entity and request the SCP search for
SOP Instances with a *Patient Name* matching ``CITIZEN^Jan`` using the *Patient
Root Query/Retrieve Information Model - Find* at the *Patient* level.

.. code-block:: python

   from pydicom.dataset import Dataset

   from pynetdicom import AE
   from pynetdicom.sop_class import PatientRootQueryRetrieveInformationModelFind

   # Initialise the Application Entity
   ae = AE()

   # Add a requested presentation context
   ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)

   # Create our Identifier (query) dataset
   ds = Dataset()
   ds.PatientName = 'CITIZEN^Jan'
   ds.QueryRetrieveLevel = 'PATIENT'

   # Associate with peer AE at IP 127.0.0.1 and port 11112
   assoc = ae.associate('127.0.0.1', 11112)

   if assoc.is_established:
       # Use the C-FIND service to send the identifier
       responses = assoc.send_c_find(ds, PatientRootQueryRetrieveInformationModelFind)

       for (status, identifier) in responses:
           if status:
               print('C-FIND query status: 0x{0:04x}'.format(status.Status))

               # If the status is 'Pending' then identifier is the C-FIND response
               if status.Status in (0xFF00, 0xFF01):
                   print(identifier)
           else:
               print('Connection timed out, was aborted or received invalid response')

        # Release the association
       assoc.release()
   else:
       print('Association rejected, aborted or never connected')

The responses received from the SCP are dependent on the *Identifier* dataset
keys and values, the Query/Retrieve level and the information model. For
example, the following query dataset should yield C-FIND responses containing
the various *SOP Class UIDs* that make are in each study for a patient with
*Patient ID* ``1234567``.

.. code-block:: python

    ds = Dataset()
    ds.SOPClassesInStudy = ''
    ds.PatientID = '1234567'
    ds.StudyInstanceUID = '*'
    ds.QueryRetrieveLevel = 'STUDY'

.. _example_qrfind_scp:

Query/Retrieve (Find) SCP
.........................

The following represents a toy implementation of a Query/Retrieve (Find) SCP
where the SCU has sent the following *Identifier* dataset under the *Patient
Root Query Retrieve Information Model - Find* context.

.. code-block:: python

   ds = Dataset()
   ds.PatientName = 'CITIZEN^Jan'
   ds.QueryRetrieveLevel = 'PATIENT'

This is a very bad way of managing stored SOP Instances, in reality its
probably best to store the instance attributes in a database and run the
query against that.

Check the
`handler implementation documentation
<../reference/generated/pynetdicom._handlers.doc_handle_find.html>`_
to see the requirements for the ``evt.EVT_C_FIND`` handler.

.. code-block:: python

    import os

    from pydicom import dcmread
    from pydicom.dataset import Dataset

    from pynetdicom import AE, evt
    from pynetdicom.sop_class import PatientRootQueryRetrieveInformationModelFind

    # Implement the handler for evt.EVT_C_FIND
    def handle_find(event):
        """Handle a C-FIND request event."""
        ds = event.identifier

        # Import stored SOP Instances
        instances = []
        fdir = '/path/to/directory'
        for fpath in os.listdir(fdir):
            instances.append(dcmread(os.path.join(fdir, fpath)))

        if 'QueryRetrieveLevel' not in ds:
            # Failure
            yield 0xC000, None
            return

        if ds.QueryRetrieveLevel == 'PATIENT':
            if 'PatientName' in ds:
                if ds.PatientName not in ['*', '', '?']:
                    matching = [
                        inst for inst in instances if inst.PatientName == ds.PatientName
                    ]

                # Skip the other possibile values...

            # Skip the other possible attributes...

        # Skip the other QR levels...

        for instance in matching:
            # Check if C-CANCEL has been received
            if event.is_cancelled:
                yield (0xFE00, None)
                return

            identifier = Dataset()
            identifier.PatientName = instance.PatientName
            identifier.QueryRetrieveLevel = ds.QueryRetrieveLevel

            # Pending
            yield (0xFF00, identifier)

   handlers = [(evt.EVT_C_FIND, handle_find)]

   # Initialise the Application Entity and specify the listen port
   ae = AE()

   # Add the supported presentation context
   ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)

   # Start listening for incoming association requests
   ae.start_server(('', 11112), evt_handlers=handlers)
