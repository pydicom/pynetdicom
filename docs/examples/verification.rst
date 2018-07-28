Verification Service Examples
-----------------------------

The DICOM `Verification Service <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_A>`_
allows an Application Entity to verify application level communication between
itself and another AE by using the DIMSE C-ECHO service. It only has a single
:ref:`supported SOP Class <verification_sops>`.

The Verification Service is mostly used to verify basic connectivity and as a
starting point when troubleshooting associations.

Verification SCU
~~~~~~~~~~~~~~~~

Associate with a peer DICOM Application Entity and request the use of the
Verification Service.

.. code-block:: python

   from pydicom import dcmread

   from pynetdicom3 import AE
   from pynetdicom3.sop_class import VerificationSOPClass

   # Initialise the Application Entity
   ae = AE()

   # Add a requested presentation context
   ae.add_requested_context(VerificationSOPClass)

   # Associate with peer AE at IP 127.0.0.1 and port 11112
   assoc = ae.associate('127.0.0.1', 11112)

   if assoc.is_established:
       # Use the C-ECHO service to send the request
       # returns a pydicom Dataset
       response = assoc.send_c_echo()

       # Check the status of the verification request
       if 'Status' in status:
           # If the verification request succeeded this will be 0x0000
           print('C-ECHO request status: 0x{0:04x}'.format(status.Status))
       else:
           print('Connection timed out or invalid response from peer')

       # Release the association
       assoc.release()
   else:
       print('Association rejected or aborted')

You can also use the inbuilt ``VerificationPresentationContexts`` when setting
the requested contexts.

.. code-block:: python

   from pynetdicom3 import AE, VerificationPresentationContexts

   ae = AE()
   ae.requested_contexts = VerificationPresentationContexts


Verification SCP
~~~~~~~~~~~~~~~~

Create an AE that supports the Verification Service and then listen for
association requests on port 11112. When a verification request is received
over the association we rely on the default implementation of ``AE.on_c_echo``
to return an 0x0000 *Success* status.

.. code-block:: python

   from pynetdicom3 import AE
   from pynetdicom3.sop_class import VerificationSOPClass

   # Initialise the Application Entity and specify the listen port
   ae = AE(port=11112)

   # Add the supported presentation context
   ae.add_supported_context(VerificationSOPClass)

   # Start listening for incoming association requests
   ae.start()

You can also optionally implement the ``on_c_echo`` callback.

.. code-block:: python

   from pynetdicom3 import AE
   from pynetdicom3.sop_class import VerificationSOPClass

   # Initialise the Application Entity and specify the listen port
   ae = AE(port=11112)

   # Add the supported presentation context
   ae.add_supported_context(VerificationSOPClass)

   def on_c_echo(context, info):
       """Respond to a C-ECHO service request.

       Parameters
       ----------
       context : namedtuple
           The presentation context that the verification request was sent under.
       info : dict
           Information about the association and verification request.

       Returns
       -------
       status : int or pydicom.dataset.Dataset
           The status returned to the peer AE in the C-ECHO response. Must be
           a valid C-ECHO status value for the applicable Service Class as
           either an ``int`` or a ``Dataset`` object containing (at a
           minimum) a (0000,0900) *Status* element.
       """
       return 0x0000

   ae.on_c_echo = on_c_echo

   # Start listening for incoming association requests
   ae.start()
