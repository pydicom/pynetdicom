
:html_theme.sidebar_secondary.remove: true

==========
pynetdicom
==========

*pynetdicom* is a `Python <https://www.python.org/>`_ package that implements the
`DICOM <https://www.dicomstandard.org/>`_ networking protocol. Working with
:gh:`pydicom <pydicom>`, it allows the easy creation of DICOM Application Entities,
which can then act as *Service Class Users* (SCUs) and *Service Class Providers*
(SCPs) by associating with other DICOM applications.


..
    For the navigation links in the top bar, hidden to avoid clutter

.. toctree::
    :maxdepth: 1
    :hidden:

    user/index
    tutorials/index
    examples/index
    reference/index
    service_classes/index
    changelog/index


Install
=======

.. tab-set::
    :class: sd-width-content-min

    .. tab-item:: pip

        .. code-block:: bash

            pip install pynetdicom

    .. tab-item:: conda

        .. code-block:: bash

            conda install -c conda-forge pynetdicom


For more detailed instructions, see the :doc:`installation guide<user/installation>`.

Examples
========

.. tab-set::
    :class: sd-width-content-min

    .. tab-item:: Echo SCU

        .. code-block:: python

            # Request a peer AE respond to a DICOM C-ECHO

            from pynetdicom import AE
            from pynetdicom.sop_class import Verification

            ae = AE(ae_title="MY_AE_TITLE")
            ae.add_requested_context(Verification)

            # Send an association request to the peer at IP 127.0.0.1, port 11112
            assoc = ae.associate("127.0.0.1", 11112)
            if assoc.is_established:
                # Send a C-ECHO request, returns the response status as a pydicom Dataset
                status = assoc.send_c_echo()
                if status:
                    # A success response is 0x0000
                    print(f"C-ECHO response: 0x{status.Status:04X}")
                else:
                    print("Connection timed out, was aborted or received an invalid response")

                # Release the association
                assoc.release()
            else:
                print("Association request rejected, aborted or never connected")

    .. tab-item:: Storage SCU

        .. code-block:: python

            # Request a peer AE store a DICOM dataset

            from pydicom import examples, dcmread
            from pynetdicom import AE
            from pynetdicom.sop_class import CTImageStorage

            # pydicom's example CT dataset
            ds = dcmread(examples.get_path("ct"))

            ae = AE(ae_title="MY_AE_TITLE")
            ae.add_requested_context(CTImageStorage)  # Must match the dataset being sent
            assoc = ae.associate("127.0.0.1", 11112)
            if assoc.is_established:
                # Send a C-STORE request, returns the response status as a pydicom Dataset
                status = assoc.send_c_store(ds)  # May also be the path to the dataset
                if status:
                    # A success response is 0x0000
                    print(f"C-STORE response: 0x{status.Status:04X}")
                else:
                    print("Connection timed out, was aborted or received an invalid response")

                # Release the association
                assoc.release()
            else:
                print("Association request rejected, aborted or never connected")

    .. tab-item:: Storage SCP

        .. code-block:: python

            # Listen for storage requests from peer AEs

            from uuid import uuid4
            from pynetdicom import AE, evt, AllStoragePresentationContexts

            def handle_store(event):
                """Handle a C-STORE request event."""
                # Write the received dataset directly to file
                with open(str(uuid4()), 'wb') as f:
                    f.write(event.encoded_dataset())

                # Return a 'Success' status
                return 0x0000

            handlers = [(evt.EVT_C_STORE, handle_store)]

            ae = AE(ae_title="MY_AE_TITLE")
            ae.supported_contexts = AllStoragePresentationContexts

            # Start listening for incoming association requests
            ae.start_server(("127.0.0.1", 11112), evt_handlers=handlers)

More service class-specific code examples can be found :doc:`here</examples/index>`.


Documentation
=============

.. grid:: 1 1 2 2
    :gutter: 2 3 4 4

    .. grid-item-card::
        :img-top: _static/img/user-guide.svg
        :text-align: center

        **User guide**
        ^^^

        The user guide contains an introduction to relevant DICOM concepts
        and usage of *pynetdicom's* core classes and functions.

        +++

        .. button-ref:: user/index
            :expand:
            :color: primary
            :click-parent:

            User guide

    .. grid-item-card::
        :img-top: _static/img/learning.svg
        :text-align: center

        **Learning resources**
        ^^^

        Our collection of code examples and tutorials should help you learn the basics
        of creating your own SCUs and SCPs.

        +++

        .. button-ref:: /learning/index
            :expand:
            :color: primary
            :click-parent:

            Learning resources

    .. grid-item-card::
        :img-top: _static/img/service-classes.svg
        :text-align: center

        **Service classes**
        ^^^

        The service class documentation contains information on each of the DICOM
        services supported by *pynetdicom*.

        +++

        .. button-ref:: /service_classes/index
            :expand:
            :color: primary
            :click-parent:

            Service classes

    .. grid-item-card::
        :img-top: _static/img/api-reference.svg
        :text-align: center

        **API reference**
        ^^^

        The API reference documentation contains detailed descriptions of the classes,
        functions, modules and other objects included in *pynetdicom*.

        +++

        .. button-ref:: reference/index
            :expand:
            :color: primary
            :click-parent:

            API reference
