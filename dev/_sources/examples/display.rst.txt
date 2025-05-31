Display System Management Service Examples
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The DICOM :dcm:`Display System Management Service <part04/chapter_EE.html>`
allows an Application Entity to retrieve Display Subsystem parameters from a
peer by using the N-GET service. It only has a single
:ref:`supported SOP Class <display_sops>`.

Display System Management SCU
.............................

Associate with a peer DICOM Application Entity and request the use of the
Display System Management Service.

.. code-block:: python

    from pynetdicom import AE, debug_logger
    from pynetdicom.sop_class import (
        DisplaySystem, DisplaySystemInstance
    )
    from pynetdicom.status import code_to_category

    debug_logger()

    # Initialise the Application Entity
    ae = AE()

    # Add a requested presentation context
    ae.add_requested_context(DisplaySystem)

    # Associate with peer AE at IP 127.0.0.1 and port 11112
    assoc = ae.associate("127.0.0.1", 11112)

    if assoc.is_established:
        # Use the N-GET service to send the request, returns the
        #  response status a pydicom Dataset and the AttributeList dataset
        status, attr_list = assoc.send_n_get(
            [(0x0008, 0x0070)],
            DisplaySystem,
            DisplaySystemInstance  # Well-known SOP Instance
        )

        # Check the status of the display system request
        if status:
            print(f"N-GET request status: 0x{status.Status:04x}")

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


.. _example_nget_scp:

Display System Management SCP
.............................

The following represents a toy implementation of a Display System Management
SCP, where the SCU has sent a request with an *Attribute Identifier List*
containing the single tag (0008,0070).

Check the
:attr:`handler implementation documentation
<pynetdicom._handlers.doc_handle_n_get>`
to see the requirements for the ``evt.EVT_N_GET`` handler.

.. code-block:: python

    from pynetdicom import AE, evt
    from pynetdicom.sop_class import DisplaySystem

    from my_code import create_attribute_list

    # Implement a handler evt.EVT_N_GET
    def handle_get(event):
        """Handle an N-GET request event."""
        attr = event.request.AttributeIdentifierList
        # User defined function to generate the required attribute list dataset
        # implementation is outside the scope of the current example
        # We pretend it returns a pydicom Dataset
        dataset = create_attribute_list(attr)

        # Return success status and dataset
        return 0x0000, dataset

    handlers = [(evt.EVT_N_GET, handle_get)]

    # Initialise the Application Entity and specify the listen port
    ae = AE()

    # Add the supported presentation context
    ae.add_supported_context(DisplaySystem)

    # Start listening for incoming association requests
    ae.start_server(("127.0.0.1", 11112), evt_handlers=handlers)
