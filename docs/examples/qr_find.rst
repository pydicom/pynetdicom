Query/Retrieve (Find) Service Examples
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The DICOM `Query/Retrieve Service <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_C>`_
provides a mechanism for a service user to query the SOP Instances managed
by a QR SCP. Querying of the SCP is accomplished by utilising the DIMSE
C-FIND service.


Query/Retrieve (Find) SCU
.........................

Associate with a peer DICOM Application Entity and request the SCP search for
SOP Instances with a *Patient Name* matching 'CITIZEN^Jan' using the *Patient
Root Query/Retrieve Information Model* at the *Patient* level.

.. code-block:: python

   from pydicom.dataset import Dataset

   from pynetdicom3 import AE
   from pynetdicom3.sop_class import PatientRootQueryRetrieveInformationModelFind

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
       # A query_model value of 'P' means use the 'Patient Root Query Retrieve
       #     Information Model - Find' presentation context
       responses = assoc.send_c_find(ds, query_model='P')

       for (status, identifier) in responses:
           print('C-FIND query status: 0x{0:04x}'.format(status.Status))

           # If the status is 'Pending' then identifier is the C-FIND response
           if status in (0xFF00, 0xFF01):
               print(identifier)

       # Release the association
       assoc.release()
   else:
       print('Association rejected or aborted')

The responses received from the SCP are dependent on the *Identifier* dataset
keys and values, the Query/Retrieve level and the information model. For
example, the following query dataset should yield C-FIND responses containing
the various *SOP Class UIDs* that make up the each study for a patient with
*Patient ID* '1234567'.

.. code-block:: python

    ds = Dataset()
    ds.SOPClassesInStudy = ''
    ds.PatientID = '1234567'
    ds.StudyInstanceUID = '*'
    ds.QueryRetrieveLevel = 'STUDY'


Query/Retrieve (Find) SCP
.........................

The following represents a toy implementation of a Query/Retrieve (Find) SCP
where the SCU has sent the following *Identifier* dataset under the *Patient
Root Query Retrieve Information Model - Find* context.

.. code-block:: python

   ds = Dataset()
   ds.PatientName = 'CITIZEN^Jan'
   ds.QueryRetrieveLevel = 'PATIENT'


.. code-block:: python

   import os

   from pydicom import dcmread
   from pydicom.dataset import Dataset

   from pynetdicom3 import AE
   from pynetdicom3.sop_class import PatientRootQueryRetrieveInformationModelFind

   # Initialise the Application Entity and specify the listen port
   ae = AE(port=11112)

   # Add a requested presentation context
   ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)

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
           Information about the association and query/retrieve request.

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
           identifier = Dataset()
           identifier.SpecificCharacterSet = instance.SpecificCharacterSet
           identifier.PatientName = instance.PatientName
           identifier.QueryRetrieveLevel = instance.QueryRetrieveLevel

           # Pending
           yield (0xFF00, identifier)

   ae.on_c_find = on_c_find

   # Start listening for incoming association requests
   ae.start()
