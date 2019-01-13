Relevant Patient Information Query Service Examples
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The DICOM `Relevant Patient Information Query Service <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_Q>`_
provides a mechanism for an SCU to access relevant patient information managed
by an SCP. This is accomplished through the DIMSE C-FIND service.


Relevant Patient Information SCU
................................

Associate with a peer DICOM Application Entity and request information on a
single patient with ID '1234567'.

.. code-block:: python

   from pydicom.dataset import Dataset

   from pynetdicom import AE
   from pynetdicom.sop_class import GeneralRelevantPatientInformationQuery

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
   assoc = ae.associate('127.0.0.1', 11112)

   if assoc.is_established:
       # Use the C-FIND service to send the identifier
       # A query_model value of 'G' means use the 'General Relevant Patient
       #     Information Model Query' presentation context
       responses = assoc.send_c_find(ds, query_model='G')

       for (status, identifier) in responses:
           print('C-FIND query status: 0x{0:04x}'.format(status.Status))

           # If the status is 'Pending' then identifier is the C-FIND response
           if status.Status in (0xFF00, 0xFF01):
               print(identifier)

       # Release the association
       assoc.release()
   else:
       print('Association rejected or aborted')


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

.. code-block:: python

    import os

    from pydicom import dcmread
    from pydicom.dataset import Dataset

    from pynetdicom import AE
    from pynetdicom.sop_class import GeneralRelevantPatientInformationQuery

    # Initialise the Application Entity and specify the listen port
    ae = AE()

    # Add a requested presentation context
    ae.add_supported_context(GeneralRelevantPatientInformationQuery)

    # Implement the AE.on_c_store callback
    def on_c_find(ds, context, info):
        """Respond to a C-FIND request Identifier `ds`.

        Parameters
        ----------
        ds : pydicom.dataset.Dataset
           The Identifier dataset send by the peer.
        context : namedtuple
           The presentation context that the dataset was sent under.
        info : dict
           Information about the association and relevant patient info request.

        Yields
        ------
        status : int or pydicom.dataset.Dataset
           The status returned to the peer AE in the C-FIND response. Must be
           a valid C-FIND status value for the applicable Service Class as
           either an ``int`` or a ``Dataset`` object containing (at a
           minimum) a (0000,0900) *Status* element.
        identifier : pydicom.dataset.Dataset
           If the status is 'Pending' then the *Identifier* ``Dataset`` for a
           matching SOP Instance. The exact requirements for the C-FIND
           response *Identifier* are Service Class specific (see the
           DICOM Standard, Part 4).

           If the status is 'Failure' or 'Cancel' then yield ``None``.

           If the status is 'Success' then yield ``None``, however yielding a
           final 'Success' status is not required and will be ignored if
           necessary.
        """
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

    ae.on_c_find = on_c_find

    # Start listening for incoming association requests
    ae.start_server(('', 11112))
