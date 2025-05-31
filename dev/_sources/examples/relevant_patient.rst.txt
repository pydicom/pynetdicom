Relevant Patient Information Query Service Examples
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The DICOM :dcm:`Relevant Patient Information Query Service
<part04/chapter_Q.html>`
provides a mechanism for an SCU to access relevant patient information managed
by an SCP. This is accomplished through the DIMSE C-FIND service.


Relevant Patient Information SCU
................................

Associate with a peer DICOM Application Entity and request information on a
single patient with ID ``1234567``.

.. code-block:: python

    from pydicom.dataset import Dataset

    from pynetdicom import AE, debug_logger
    from pynetdicom.sop_class import GeneralRelevantPatientInformationQuery

    debug_logger()

    # Initialise the Application Entity
    ae = AE()

    # Add a requested presentation context
    ae.add_requested_context(GeneralRelevantPatientInformationQuery)

    # Create our Identifier (query) dataset
    ds = Dataset()
    ds.PatientName = ''
    ds.PatientID = '1234567'
    ds.ContentTemplateSequence = [Dataset()]
    # Request the General Relevant Patient Information template (TID 9007)
    # See DICOM Standard, Part 16, Annex A, TID 9000-9007
    ds.ContentTemplateSequence[0].MappingResource = 'DCMR'
    ds.ContentTemplateSequence[0].TemplateIdentifier = '9007'

    # Associate with peer AE at IP 127.0.0.1 and port 11112
    assoc = ae.associate("127.0.0.1", 11112)

    if assoc.is_established:
        # Use the C-FIND service to send the identifier
        responses = assoc.send_c_find(ds, GeneralRelevantPatientInformationQuery)
        for (status, identifier) in responses:
            if status:
                print(f"C-FIND query status: 0x{status.Status:04x}")
            else:
                print('Connection timed out, was aborted or received invalid response')

        # Release the association
        assoc.release()
    else:
        print('Association rejected, aborted or never connected')


Relevant Patient Information SCP
................................

The following represents a toy implementation of a Relevant Patient
Information Query SCP where the SCU has sent the following *Identifier*
dataset under the *General Relevant Patient Information Model Query* context.
Its important to note that in the case of a successful match the response
from the SCP includes an Identifier that meets the requirements of the
requested template.

.. code-block:: python

    ds = Dataset()
    ds.PatientName = ''
    ds.PatientID = '1234567'
    ds.ContentTemplateSequence = [Dataset()]
    ds.ContentTemplateSequence[0].MappingResource = 'DCMR'
    ds.ContentTemplateSequence[0].TemplateIdentifier = '9007'

This is a very bad way of managing stored SOP Instances, in reality its
probably best to store the instance attributes in a database and run the
query against that.

Check the
:func:`handler implementation documentation
<pynetdicom._handlers.doc_handle_find>`
to see the requirements for the ``evt.EVT_C_FIND`` handler.

.. code-block:: python

    import os

    from pydicom import dcmread
    from pydicom.dataset import Dataset

    from pynetdicom import AE, evt
    from pynetdicom.sop_class import GeneralRelevantPatientInformationQuery

    # Implement the evt.EVT_C_FIND handler
    def handle_find(event):
        """Handle a C-FIND service request"""
        ds = event.identifier

        # Import stored SOP Instances
        instances = []
        fdir = '/path/to/directory'
        for fpath in os.listdir(fdir):
           instances.append(dcmread(os.path.join(fdir, fpath)))

        # Not a good example of how to match
        matching = [
            inst for inst in instances if inst.PatientID == ds.PatientID
        ]

        # There must either be no match or 1 match, everything else
        #   is a failure
        if len(matching) == 1:
            # User-defined function to create the identifier based off a
            #   template, outside the scope of the current example
            identifier = create_template(matching[0], ds)
            yield (0xFF00, identifier)
        elif len(matching) > 1:
            # More than 1 match found
            yield (0xC100, None)

    handlers = [(evt.EVT_C_FIND, handle_find)]

    # Initialise the Application Entity and specify the listen port
    ae = AE()

    # Add the supported presentation context
    ae.add_supported_context(GeneralRelevantPatientInformationQuery)

    # Start listening for incoming association requests
    ae.start_server(("127.0.0.1", 11112), evt_handlers=handlers)
