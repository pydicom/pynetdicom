Basic Worklist Management Service Examples
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The DICOM :dcm:`Basic Worklist Management Service <part04/chapter_K.html>`
provides a mechanism for a service user to access worklists on another AE.
Querying of the SCP for worklists is accomplished by utilising the DIMSE
C-FIND service.


Basic Worklist Management SCU
-----------------------------

Associate with a peer DICOM Application Entity and request the
worklist for the application with AE title ``CTSCANNER`` for the 5th October
2018. You may need to change the *Identifier* to meet the requirements of the
SCP so check it's conformance statement. The approach is very similar to that
of a Query/Retrieve (Find) SCU, however BWM uses a different
:dcm:`set of attributes <part04/sect_K.6.html#sect_K.6.1.2>` for the
*Identifier*.

.. code-block:: python

    from pydicom.dataset import Dataset

    from pynetdicom import AE, debug_logger
    from pynetdicom.sop_class import ModalityWorklistInformationFind

    debug_logger()

    # Initialise the Application Entity
    ae = AE()

    # Add a requested presentation context
    ae.add_requested_context(ModalityWorklistInformationFind)

    # Create our Identifier (query) dataset
    ds = Dataset()
    ds.PatientName = '*'
    ds.ScheduledProcedureStepSequence = [Dataset()]
    item = ds.ScheduledProcedureStepSequence[0]
    item.ScheduledStationAETitle = 'CTSCANNER'
    item.ScheduledProcedureStepStartDate = '20181005'
    item.Modality = 'CT'

    # Associate with peer AE at IP 127.0.0.1 and port 11112
    assoc = ae.associate("127.0.0.1", 11112)

    if assoc.is_established:
        # Use the C-FIND service to send the identifier
        responses = assoc.send_c_find(ds, ModalityWorklistInformationFind)
        for (status, identifier) in responses:
            if status:
                print(f"C-FIND query status: 0x{status.Status:04x}")
            else:
                print('Connection timed out, was aborted or received invalid response')

        # Release the association
        assoc.release()
    else:
        print('Association rejected, aborted or never connected')


Basic Worklist Management SCP
-----------------------------

The approach will be similar to the
:doc:`Query/Retrieve (Find) SCP example <qr_find>`.
