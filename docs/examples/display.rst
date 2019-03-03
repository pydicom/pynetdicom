Display System Management Service Examples
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The DICOM `Display System Management Service <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_EE>`_
allows an Application Entity to retrieve Display Subsystem parameters from a
peer by using the N-GET service. It only has a single
:ref:`supported SOP Class <display_sops>`.

Display System Management SCU
.............................

Associate with a peer DICOM Application Entity and request the use of the
Display System Management Service.

.. code-block:: python

    from pynetdicom import AE
    from pynetdicom.sop_class import DisplaySystemSOPClass
    from pynetdicom.status import code_to_category

    # Initialise the Application Entity
    ae = AE()

    # Add a requested presentation context
    ae.add_requested_context(DisplaySystemSOPClass)

    # Associate with peer AE at IP 127.0.0.1 and port 11112
    assoc = ae.associate('127.0.0.1', 11112)

    if assoc.is_established:
        # Use the N-GET service to send the request, returns the
        #  response status a pydicom Dataset and the AttributeList dataset
        status, attr_list = assoc.send_n_get(
            [(0x0008,0x0070)],
            DisplaySystemSOPClass,
            '1.2.840.10008.5.1.1.40.1'
        )

        # Check the status of the display system request
        if status:
            print('N-GET request status: 0x{0:04x}'.format(status.Status))

            # If the display system request succeeded the status category may
            # be either success or warning
            category = code_to_category(status.Status)
            if category in ['Warning', 'Success']:
                # `attr_list` is a pydicom Dataset containing attribute values
                print(attr_list)
        else:
            print('Connection timed out, was aborted or received invalid response')

        # Release the association
        assoc.release()
    else:
        print('Association rejected, aborted or never connected')

You can also use the inbuilt ``DisplaySystemPresentationContexts`` when setting
the requested contexts.

.. code-block:: python

   from pynetdicom import AE, DisplaySystemPresentationContexts

   ae = AE()
   ae.requested_contexts = DisplaySystemPresentationContexts


.. _example_nget_scp:

Display System Management SCP
.............................

The following represents a toy implementation of a Display System Management
SCP, where the SCU has sent a request with an *Attribute Identifier List*
containing the single tag (0008,0070).

Check the
`handler implementation documentation
<../reference/generated/pynetdicom._handlers.doc_handle_n_get.html>`_
to see the requirements for the ``evt.EVT_N_GET`` handler.

.. code-block:: python

    from pynetdicom import AE, evt
    from pynetdicom.sop_class import DisplaySystemSOPClass

    # Implement a handler evt.EVT_N_GET
    def handle_get(event):
        """Handle an N-GET request event."""
        attr = event.request.AttributeIdentifierList
        # User defined function to generate the required attribute list dataset
        # implementation is outside the scope of the current example
        # We pretend it returns a pydicom Dataset
        dataset = create_attribute_list(attr)

        # If Display System Management returns an attribute list then the
        # SOP Class UID and SOP Instance UID must always be as given below
        assert dataset.SOPClassUID = '1.2.840.10008.5.1.1.40'
        assert dataset.SOPInstanceUID = '1.2.840.10008.5.1.1.40.1'

        # Return status, dataset
        return 0x0000, dataset

    handlers = [(evt.EVT_N_GET, handle_get)]

    # Initialise the Application Entity and specify the listen port
    ae = AE()

    # Add the supported presentation context
    ae.add_supported_context(DisplaySystemSOPClass)

    # Start listening for incoming association requests
    ae.start_server(('', 11112), evt_handlers=handlers)
