
.. currentmodule:: pynetdicom.presentation

Registering private or retired SOP Classes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In order to correctly match a DICOM service class to an abstract syntax, the SOP
Class UID used in a presentation context must be known or be included in *pynetdicom* .

.. code-block:: python

    >>> from pynetdicom.sop_class import CTImageStorage
    >>> CTImageStorage.service_class  # Included SOP Class UID
    <class 'pynetdicom.service_class.StorageServiceClass'>

.. code-block:: python

    >>> from pydicom.uid import CTImageStorage
    >>> from pynetdicom.sop_class import uid_to_service_class
    >>> uid_to_service_class(CTImageStorage)  # Known SOP Class UID
    <class 'pynetdicom.service_class.StorageServiceClass'>

However some SOP Class UIDs are not included in *pynetdicom*, either because they're
privately defined, have been retired from the DICOM Standard or are too new to have been
included in the most recent release. If you need to support one of these SOP classes
you should use the :func:`~pynetdicom.sop_class.register_uid` function to match the
UID to an appropriate :mod:`~pynetdicom.service_class` object.

.. code-block:: python

    from pynetdicom import register_uid
    from pynetdicom.service_class import StorageServiceClass

    # Register 1.2.246.352.70.1.70 to the Storage service
    register_uid(
        "1.2.246.352.70.1.70",
        "PrivateRTPlanStorage",
        StorageServiceClass,
    )

The UID itself can then be used directly or imported from the
:mod:`~pynetdicom.sop_class` module and used like other SOP Class UIDs.

.. code-block:: python

    from pynetdicom import AE, evt
    from pynetdicom.sop_class import PrivateRTPlanStorage

    def handle_store(evt):
        ds = event.dataset
        ds.file_meta = event.file_meta
        ds.save_as(ds.SOPInstanceUID)

        return 0x0000

    ae = AE()
    ae.add_supported_context(PrivateRTPlanStorage)
    # or ae.add_supported_context("1.2.246.352.70.1.70")
    ae.start_server(("localhost", 11112), evt_handlers=[(evt.EVT_C_STORE, handle_store)])


When registering a new UID with the
:class:`~pynetdicom.service_class.QueryRetrieveServiceClass`, you must also
specify which of the three DIMSE-C message types the UID is to be used with.

.. code-block:: python

    from pynetdicom import register_uid
    from pynetdicom.service_class import QueryRetrieveServiceClass

    register_uid(
        "1.2.246.352.70.1.70",
        "PrivateQueryFind",
        QueryRetrieveServiceClass,
        dimse_msg_type="C-FIND"  # or "C-GET" or "C-MOVE"
    )
