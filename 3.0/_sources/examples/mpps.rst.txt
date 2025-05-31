Modality Performed Procedure Step Management Service Examples
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The DICOM :dcm:`Modality Performed Procedure Step Management (MPPS) service
<part04/chapter_F.html>`
allows an Application Entity to log or track procedures performed by a
modality through the N-CREATE, N-SET, N-EVENT-REPORT and N-GET services. It
has :ref:`three SOP Classes <display_sops>`:

* *Modality Performed Procedure Step SOP Class*, used with N-CREATE and N-SET
  to create and set the SOP Instance's attribute values
* *Modality Performed Procedure Step Retrieve SOP Class*, used with N-GET to
  retrieve the SOP Instance's attribute values
* *Modality Performed Procedure Step Notification SOP Class*, used with
  N-EVENT-REPORT to notify a peer of the status of a procedure.

MPPS is usually used in combination with the Modality Worklist Service Class
to provide the modality a mechanism for notifying the RIS (or PACS) that
requested the procedure of it's current status. The modality is typically the
SCU and the RIS (or PACS) the SCP.


MPPS - Create SCU
.................

Associate with a peer and request the use of the MPPS Service to create a new
SOP Instance.

.. code-block:: python

    from pydicom.dataset import Dataset
    from pydicom.uid import generate_uid

    from pynetdicom import AE, debug_logger
    from pynetdicom.sop_class import (
        ModalityPerformedProcedureStep,
        CTImageStorage
    )
    from pynetdicom.status import code_to_category

    debug_logger()

    ct_study_uid = generate_uid()
    mpps_instance_uid = generate_uid()

    # Our N-CREATE *Attribute List*
    def build_attr_list():
        ds = Dataset()
        # Performed Procedure Step Relationship
        ds.ScheduledStepAttributesSequence = [Dataset()]
        step_seq = ds.ScheduledStepAttributesSequence
        step_seq[0].StudyInstanceUID = ct_study_uid
        step_seq[0].ReferencedStudySequence = []
        step_seq[0].AccessionNumber = '1'
        step_seq[0].RequestedProcedureID = "1"
        step_seq[0].RequestedProcedureDescription = 'Some procedure'
        step_seq[0].ScheduledProcedureStepID = "1"
        step_seq[0].ScheduledProcedureStepDescription = 'Some procedure step'
        step_seq[0].ScheduledProcedureProtocolCodeSequence = []
        ds.PatientName = 'Test^Test'
        ds.PatientID = '123456'
        ds.PatientBirthDate = '20000101'
        ds.PatientSex = 'O'
        ds.ReferencedPatientSequence = []
        # Performed Procedure Step Information
        ds.PerformedProcedureStepID = "1"
        ds.PerformedStationAETitle = 'SOMEAE'
        ds.PerformedStationName = 'Some station'
        ds.PerformedLocation = 'Some location'
        ds.PerformedProcedureStepStartDate = '20000101'
        ds.PerformedProcedureStepStartTime = '1200'
        ds.PerformedProcedureStepStatus = 'IN PROGRESS'
        ds.PerformedProcedureStepDescription = 'Some description'
        ds.PerformedProcedureTypeDescription = 'Some type'
        ds.PerformedProcedureCodeSequence = []
        ds.PerformedProcedureStepEndDate = None
        ds.PerformedProcedureStepEndTime = None
        # Image Acquisition Results
        ds.Modality = 'CT'
        ds.StudyID = "1"
        ds.PerformedProtocolCodeSequence = []
        ds.PerformedSeriesSequence = []

        return ds

    # Initialise the Application Entity
    ae = AE()

    # Add a requested presentation context
    ae.add_requested_context(ModalityPerformedProcedureStep)

    # Associate with peer AE at IP 127.0.0.1 and port 11112
    assoc = ae.associate("127.0.0.1", 11112)

    if assoc.is_established:
        # Use the N-CREATE service to send a request to create a SOP Instance
        # should return the Instance itself
        status, attr_list = assoc.send_n_create(
            build_attr_list(),
            ModalityPerformedProcedureStep,
            mpps_instance_uid
        )

        # Check the status of the display system request
        if status:
            print(f"N-CREATE request status: 0x{status.Status:04x}")

            # If the MPPS request succeeded the status category may
            # be either Success or Warning
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

MPPS - Set SCU
..............

Once the MPPS SOP Instance has successfully been created, the modality can send
one or more N-SET requests to the MPPS SCP in order to update the attributes
of the SOP Instance. When the procedure has been completed a final N-SET
request is sent containing a *Modification List* with an (0040,0252) *Performed
Procedure Step Status* of ``"COMPLETED"``.

.. code-block:: python

    # Continuing on from the previous example...
    # Modality performs the procedure, update the MPPS SCP
    # In performing the procedure a series with ten CT Image Storage
    # SOP Instances is generated
    ct_series_uid = generate_uid()
    ct_instance_uids = [generate_uid() for ii in range(10)]

    # Our N-SET *Modification List*
    def build_mod_list(series_instance, sop_instances):
        ds = Dataset()
        ds.PerformedSeriesSequence = [Dataset()]

        series_seq = ds.PerformedSeriesSequence
        series_seq[0].PerformingPhysicianName = None
        series_seq[0].ProtocolName = "Some protocol"
        series_seq[0].OperatorName = None
        series_seq[0].SeriesInstanceUID = series_instance
        series_seq[0].SeriesDescription = "some description"
        series_seq[0].RetrieveAETitle = None
        series_seq[0].ReferencedImageSequence = []

        img_seq = series_seq[0].ReferencedImageSequence
        for uid in sop_instances:
            img_ds = Dataset()
            img_ds.ReferencedSOPClassUID = CTImageStorage
            img_ds.ReferencedSOPInstanceUID = uid
            img_seq.append(img_ds)

        series_seq[0].ReferencedNonImageCompositeSOPInstanceSequence = []

        return ds

    # Our final N-SET *Modification List*
    final_ds = Dataset()
    final_ds.PerformedProcedureStepStatus = "COMPLETED"
    final_ds.PerformedProcedureStepEndDate = "20000101"
    final_ds.PerformedProcedureStepEndTime = "1300"

    # Associate with peer again
    assoc = ae.associate("127.0.0.1", 11112)

    if assoc.is_established:
        # Use the N-SET service to update the SOP Instance
        status, attr_list = assoc.send_n_set(
            build_mod_list(ct_series_uid, ct_instance_uids),
            ModalityPerformedProcedureStep,
            mpps_instance_uid
        )

        if status:
            print(f"N-SET request status: 0x{status.Status:04x}")
            category = code_to_category(status.Status)
            if category in ['Warning', 'Success']:
                # Send completion
                status, attr_list = assoc.send_n_set(
                    final_ds,
                    ModalityPerformedProcedureStep,
                    mpps_instance_uid
                )
                if status:
                    print(f"Final N-SET request status: 0x{status.Status:04x}")
        else:
            print('Connection timed out, was aborted or received invalid response')

        assoc.release()


.. _example_mpps_scp:

MPPS SCP
........

The following represents a toy implementation of an MPPS SCP (Modality
Performed Procedure Step SOP Class only).

Check the
:func:`handler implementation documentation
<pynetdicom._handlers.doc_handle_n_get>`
to see the requirements for the ``evt.EVT_N_CREATE`` and ``evt.EVT_N_SET``
handlers.

.. code-block:: python

    from pydicom.dataset import Dataset

    from pynetdicom import AE, evt
    from pynetdicom.sop_class import ModalityPerformedProcedureStep

    managed_instances = {}

    # Implement the evt.EVT_N_CREATE handler
    def handle_create(event):
        # MPPS' N-CREATE request must have an *Affected SOP Instance UID*
        req = event.request
        if req.AffectedSOPInstanceUID is None:
            # Failed - invalid attribute value
            return 0x0106, None

        # Can't create a duplicate SOP Instance
        if req.AffectedSOPInstanceUID in managed_instances:
            # Failed - duplicate SOP Instance
            return 0x0111, None

        # The N-CREATE request's *Attribute List* dataset
        attr_list = event.attribute_list

        # Performed Procedure Step Status must be 'IN PROGRESS'
        if "PerformedProcedureStepStatus" not in attr_list:
            # Failed - missing attribute
            return 0x0120, None
        if attr_list.PerformedProcedureStepStatus.upper() != 'IN PROGRESS':
            return 0x0106, None

        # Skip other tests...

        # Create a Modality Performed Procedure Step SOP Class Instance
        #   DICOM Standard, Part 3, Annex B.17
        ds = Dataset()

        # Add the SOP Common module elements (Annex C.12.1)
        ds.SOPClassUID = ModalityPerformedProcedureStep
        ds.SOPInstanceUID = req.AffectedSOPInstanceUID

        # Update with the requested attributes
        ds.update(attr_list)

        # Add the dataset to the managed SOP Instances
        managed_instances[ds.SOPInstanceUID] = ds

        # Return status, dataset
        return 0x0000, ds

    # Implement the evt.EVT_N_SET handler
    def handle_set(event):
        req = event.request
        if req.RequestedSOPInstanceUID not in managed_instances:
            # Failure - SOP Instance not recognised
            return 0x0112, None

        ds = managed_instances[req.RequestedSOPInstanceUID]

        # The N-SET request's *Modification List* dataset
        mod_list = event.attribute_list

        # Skip other tests...

        ds.update(mod_list)

        # Return status, dataset
        return 0x0000, ds

    handlers = [(evt.EVT_N_CREATE, handle_create), (evt.EVT_N_SET, handle_set)]

    # Initialise the Application Entity and specify the listen port
    ae = AE()

    # Add the supported presentation context
    ae.add_supported_context(ModalityPerformedProcedureStep)

    # Start listening for incoming association requests
    ae.start_server(("127.0.0.1", 11112), evt_handlers=handlers)
