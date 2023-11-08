===========================
Registering a new SOP Class
===========================

.. currentmodule:: pynetdicom

You may occasionally come across a private SOP Class UID you like to be able
to receive, or perhaps there's a public SOP Class from a recent release of the
DICOM Standard that hasn't yet been added to *pynetdicom*. In this short
tutorial you'll learn how to register your own UID so it can be used like
the SOP Classes included by *pynetdicom*.

To register new UIDs we use the :func:`~pynetdicom.sop_class.register_uid` function,
which takes the UID to be registered, a `keyword` that will be used as the
variable name for the new UID and the *pynetdicom*
:mod:`~pynetdicom.service_class` to register the UID with::

    from pynetdicom import register_uid
    from pynetdicom.service_class import StorageServiceClass

    register_uid(
        "1.2.246.352.70.1.70",
        PrivateRTPlanStorage,
        StorageServiceClass,
    )

The UID can then be imported from the :mod:`~pynetdicom.sop_class` module and
used like other UIDs::

    from pynetdicom import AE, evt
    from pynetdicom.sop_class import PrivateRTPlanStorage

    def handle_store(evt):
        ds = event.dataset
        ds.file_meta = event.file_meta
        ds.save_as(ds.SOPInstanceUID)

        return 0x0000

    ae = AE()
    # or ae.add_supported_context("1.2.246.352.70.1.70")
    ae.add_supported_context(PrivateRTPlanStorage)
    ae.start_server(("localhost", 11112), evt_handlers=[(evt.EVT_C_STORE, handle_store)])


When registering a new UID with the
:class:`~pynetdicom.service_class.QueryRetrieveServiceClass`, you must also
specify which of the three DIMSE-C message types the UID is to be used with::

    from pynetdicom import register_uid
    from pynetdicom.service_class import QueryRetrieveServiceClass

    register_uid(
        "1.2.246.352.70.1.70",
        PrivateQueryFind,
        QueryRetrieveServiceClass,
        dimse_msg_type="C-FIND"  # or "C-GET" or "C-MOVE"
    )
