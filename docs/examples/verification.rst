Verification Service Examples
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The DICOM :dcm:`Verification Service <part04/chapter_A.html>`
allows an Application Entity to verify application level communication between
itself and another AE by using the DIMSE C-ECHO service. It only has a single
:ref:`supported SOP Class <verification_sops>`.

The Verification Service is mostly used to verify basic connectivity and as a
starting point when troubleshooting associations, particularly when handlers
are bound to the more fundamental :ref:`notification events<events_notification>`
like  ``evt.EVT_PDU_RECV`` or ``evt.EVT_DATA_RECV`` or with the log level set
to debug:

::

    from pynetdicom import debug_logger

    debug_logger()


Verification SCU
................

Associate with a peer DICOM Application Entity and request the use of the
Verification Service.

.. code-block:: python

   from pynetdicom import AE
   from pynetdicom.sop_class import Verification

   # Initialise the Application Entity
   ae = AE()

   # Add a requested presentation context
   ae.add_requested_context(Verification)

   # Associate with peer AE at IP 127.0.0.1 and port 11112
   assoc = ae.associate("127.0.0.1", 11112)

   if assoc.is_established:
       # Use the C-ECHO service to send the request
       # returns the response status a pydicom Dataset
       status = assoc.send_c_echo()

       # Check the status of the verification request
       if status:
           # If the verification request succeeded this will be 0x0000
           print(f"C-ECHO request status: 0x{status.Status:04x}")
       else:
           print('Connection timed out, was aborted or received invalid response')

       # Release the association
       assoc.release()
   else:
       print('Association rejected, aborted or never connected')

You can also use the inbuilt
:attr:`~pynetdicom.presentation.VerificationPresentationContexts` when setting
the requested contexts.

.. code-block:: python

   from pynetdicom import AE, VerificationPresentationContexts

   ae = AE()
   ae.requested_contexts = VerificationPresentationContexts


.. _example_verification_scp:

Verification SCP
................

Create an :class:`AE <pynetdicom.ae.ApplicationEntity>` that supports the
Verification Service and then listen for
association requests on port 11112. When a verification request is received
over the association we rely on the default handler bound to ``evt.EVT_C_ECHO``
to return an ``0x0000`` *Success* :ref:`status <verification_statuses>`.

.. code-block:: python

    from pynetdicom import AE
    from pynetdicom.sop_class import Verification

    # Initialise the Application Entity
    ae = AE()

    # Add the supported presentation context
    ae.add_supported_context(Verification)

   # Start listening for incoming association requests in blocking mode
   ae.start_server(("127.0.0.1", 11112), block=True)

You can also optionally bind your own handler to ``evt.EVT_C_ECHO``. Check the
:func:`handler implementation documentation
<pynetdicom._handlers.doc_handle_echo>`
to see the requirements for the ``evt.EVT_C_ECHO`` handler.

.. code-block:: python

    from pynetdicom import AE, evt
    from pynetdicom.sop_class import Verification

    # Implement a handler for evt.EVT_C_ECHO
    def handle_echo(event):
        """Handle a C-ECHO request event."""
        return 0x0000

    handlers = [(evt.EVT_C_ECHO, handle_echo)]

    ae = AE()
    ae.add_supported_context(Verification)
    ae.start_server(("127.0.0.1", 11112), evt_handlers=handlers)
