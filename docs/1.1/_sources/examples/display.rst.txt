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
        if 'Status' in status:
            print('N-GET request status: 0x{0:04x}'.format(status.Status))

            # If the display system request succeeded the status category may
            # be either success or warning
            category = code_to_category(status.Status)
            if category in ['Warning', 'Success']:
                # `attr_list` is a pydicom Dataset containing attribute values
                print(attr_list)
        else:
            print('Connection timed out or invalid response from peer')

        # Release the association
        assoc.release()
    else:
        print('Association rejected or aborted')

You can also use the inbuilt ``DisplaySystemPresentationContexts`` when setting
the requested contexts.

.. code-block:: python

   from pynetdicom import AE, DisplaySystemPresentationContexts

   ae = AE()
   ae.requested_contexts = DisplaySystemPresentationContexts


Display System Management SCP
.............................

The following represents a toy implementation of a Display System Management
SCP, where the SCU has sent a request with an *Attribute Identifier List*
containing the single tag (0008,0070).

.. code-block:: python

    from pynetdicom import AE
    from pynetdicom.sop_class import DisplaySystemSOPClass

    # Initialise the Application Entity and specify the listen port
    ae = AE(port=11112)

    # Add the supported presentation context
    ae.add_supported_context(DisplaySystemSOPClass)

    def on_n_get(attr, context, info):
        """Callback for when an N-GET request is received.

        Parameters
        ----------
        attr : list of pydicom.tag.Tag
            The value of the (0000,1005) *Attribute Idenfier List* element
            containing the attribute tags for the N-GET operation.
        context : presentation.PresentationContextTuple
            The presentation context that the N-GET message was sent under.
        info : dict
            A dict containing information about the current association.

        Returns
        -------
        status : pydicom.dataset.Dataset or int
            The status returned to the peer AE in the N-GET response. Must be a
            valid N-GET status value for the applicable Service Class as either
            an ``int`` or a ``Dataset`` object containing (at a minimum) a
            (0000,0900) *Status* element. If returning a Dataset object then
            it may also contain optional elements related to the Status (as in
            DICOM Standard Part 7, Annex C).
        dataset : pydicom.dataset.Dataset or None
            If the status category is 'Success' or 'Warning' then a dataset
            containing elements matching the request's Attribute List
            conformant to the specifications in the corresponding Service
            Class.

            If the status is not 'Successs' or 'Warning' then return None.
        """
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

    ae.on_n_get = on_n_get

    # Start listening for incoming association requests
    ae.start()
