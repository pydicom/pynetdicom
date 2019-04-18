"""Tests for the DIMSE-N Service Classes."""

import pytest

from pydicom.dataset import Dataset
from pydicom.uid import ImplicitVRLittleEndian

from pynetdicom import AE, evt, debug_logger
from pynetdicom.dimse_primitives import (
    N_ACTION, N_CREATE, N_DELETE, N_EVENT_REPORT, N_GET, N_SET, C_FIND
)
from pynetdicom.sop_class import (
    DisplaySystemSOPClass,  # Display Sysyem Management - N-GET
    # Modality Performed Procedure - N-CREATE, N-SET
    ModalityPerformedProcedureStepSOPClass,
    ModalityPerformedProcedureStepRetrieveSOPClass,  # N-GET
    ModalityPerformedProcedureStepNotificationSOPClass,  # N-EVENT-REPORT
    # Print Management - N-ACTION, N-CREATE, N-DELETE, N-SET
    BasicFilmSessionSOPClass,
    PrintJobSOPClass,  # N-EVENT-REPORT, N-GET
    # Storage Commitment - N-ACTION, N-EVENT-REPORT
    StorageCommitmentPushModelSOPClass,
    # Application Event Logging - N-ACTION
    ProceduralEventLoggingSOPClass,
    # Instance Availability - N-CREATE
    InstanceAvailabilityNotificationSOPClass,
    # Media Creation - N-ACTION, N-CREATE, N-GET
    MediaCreationManagementSOPClass,
    # Unified Procedure Step - N-ACTION, N-CREATE, N-GET
    UnifiedProcedureStepPushSOPClass,
    UnifiedProcedureStepPullSOPClass,  # N-GET, N-SET, C-FIND
    UnifiedProcedureStepEventSOPClass,  # N-EVENT-REPORT
    # RT Machine Verification - All DIMSE-N
    RTConventionalMachineVerification,
)


#debug_logger()


REFERENCE_REQUESTS = [
    # SOP Class, DIMSE msg, warning status, custom failure status
    (DisplaySystemSOPClass, "N-GET", None, None),
    (ModalityPerformedProcedureStepSOPClass, "N-CREATE", None, None),
    (ModalityPerformedProcedureStepSOPClass, "N-SET", None, None),
    (ModalityPerformedProcedureStepRetrieveSOPClass, "N-GET", 0x0001, None),
    (ModalityPerformedProcedureStepNotificationSOPClass, "N-EVENT-REPORT", None, None),
    (BasicFilmSessionSOPClass, "N-ACTION", None, None),
    (BasicFilmSessionSOPClass, "N-CREATE", 0xB600, 0xC616),
    (BasicFilmSessionSOPClass, "N-DELETE", None, None),
    (BasicFilmSessionSOPClass, "N-SET", 0xB600, 0xC616),
    (PrintJobSOPClass, "N-EVENT-REPORT", None, None),
    (PrintJobSOPClass, "N-GET", None, None),
    (StorageCommitmentPushModelSOPClass, "N-ACTION", None, None),
    (StorageCommitmentPushModelSOPClass, "N-EVENT-REPORT", None, None),
    (ProceduralEventLoggingSOPClass, "N-ACTION", 0xB101, 0xC101),
    (InstanceAvailabilityNotificationSOPClass, "N-CREATE", None, None),
    (MediaCreationManagementSOPClass, "N-ACTION", None, 0xC201),
    (MediaCreationManagementSOPClass, "N-CREATE", None, 0xA510),
    (MediaCreationManagementSOPClass, "N-GET", 0x0001, None),
    (UnifiedProcedureStepPushSOPClass, "N-ACTION", 0xB301, 0xC300),
    (UnifiedProcedureStepPushSOPClass, "N-CREATE", 0xB300, 0xC309),
    (UnifiedProcedureStepPushSOPClass, "N-GET", 0x0001, 0xC307),
    (UnifiedProcedureStepPullSOPClass, "N-SET", 0xB305, 0xC310),
    #(UnifiedProcedureStepPullSOPClass, "C_FIND", None, 0xA700),
    (UnifiedProcedureStepEventSOPClass, "N-EVENT-REPORT", None, None),
    (RTConventionalMachineVerification, "N-ACTION", None, 0xC112),
    (RTConventionalMachineVerification, "N-CREATE", None, 0xC227),
    (RTConventionalMachineVerification, "N-DELETE", None, None),
    (RTConventionalMachineVerification, "N-EVENT-REPORT", None, None),
    (RTConventionalMachineVerification, "N-GET", None, 0xC112),
    (RTConventionalMachineVerification, "N-SET", None, 0xC224),
]


class TestNServiceClass(object):
    """Generic tests for the DIMSE-N Service Classes"""
    def setup(self):
        """Run prior to each test"""
        self.ae = None

        ds = Dataset()
        ds.PatientName = 'Test'
        ds.SOPClassUID = DisplaySystemSOPClass
        ds.SOPInstanceUID = '1.2.3.4'
        self.ds = ds

        self.event = None

    def teardown(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

    def handle_dual(self, status, ds, raise_exc=False):
        """Return a callable function that returns two value.

        Parameters
        ----------
        status : int or pydicom.dataset.Dataset
            The first value the callable should return
        ds : None or pydicom.dataset.Dataset
            The second value the callable should return
        raise_exc : bool, optional
            If True raise a ValueError exception in the handler.

        Returns
        -------
        callable
        """
        def handler(event):
            if raise_exc:
                raise ValueError("Exception raised in handler")

            self.event = event

            return status, ds

        return handler

    def handle_single(self, status, raise_exc=False):
        """Return a callable function that returns only a single value.

        Parameters
        ----------
        status : int or pydicom.dataset.Dataset
            The first value the callable should return
        raise_exc : bool, optional
            If True raise a ValueError exception in the handler.

        Returns
        -------
        callable
        """
        def handler(event):
            if raise_exc:
                raise ValueError("Exception raised in handler")

            self.event = event

            return status

        return handler

    @staticmethod
    def handle_yield(generator):
        def handle(event):
            for ii in generator:
                yield ii

        return handle

    @staticmethod
    def send_action(assoc, class_uid, action_type=1, action_info=None):
        """Send an N-ACTION request via `assoc`

        The *Requested SOP Instance UID will always be '1.2.3.4'.

        Parameters
        ----------
        assoc : association.Association
            The association sending the request.
        class_uid : pydicom.uid.UID
            The *Requested SOP Class UID* to use.
        action_type : int, optional
            The *Action Type ID* to use.
        action_info : None or pydicom.dataset.Dataset, optional
            The *Action Information* to use.
        """
        return assoc.send_n_action(
            action_info, action_type, class_uid, '1.2.3.4'
        )

    @staticmethod
    def send_create(assoc, class_uid, attr_list=None):
        """Send an N-CREATE request via `assoc`

        The *Affected SOP Instance UID will always be '1.2.3.4'.

        Parameters
        ----------
        assoc : association.Association
            The association sending the request.
        class_uid : pydicom.uid.UID
            The *Affected SOP Class UID* to use.
        attr_list : None or pydicom.dataset.Dataset
            The *Attribute List* to use.
        """
        return assoc.send_n_create(
            attr_list, class_uid, '1.2.3.4'
        )

    @staticmethod
    def send_delete(assoc, class_uid):
        """Send an N-DELETE request via `assoc`

        The *Requested SOP Instance UID will always be '1.2.3.4'.

        Parameters
        ----------
        assoc : association.Association
            The association sending the request.
        class_uid : pydicom.uid.UID
            The *Requested SOP Class UID* to use.
        """
        return assoc.send_n_delete(class_uid, '1.2.3.4')

    @staticmethod
    def send_event_report(assoc, class_uid, event_type=1, event_info=None):
        """Send an N-EVENT-REPORT request via `assoc`

        The *Affected SOP Instance UID will always be '1.2.3.4'.

        Parameters
        ----------
        assoc : association.Association
            The association sending the request.
        class_uid : pydicom.uid.UID
            The *Affected SOP Class UID* to use.
        event_type : int, optional
            The *Event Type ID* to use.
        event_info : None or pydicom.dataset.Dataset, optional
            The *Event Information* to use.
        """
        return assoc.send_n_event_report(
            event_info, event_type, class_uid, '1.2.3.4'
        )

    @staticmethod
    def send_get(assoc, class_uid, attr_list=None):
        """Send an N-GET request via `assoc`

        The *Requested SOP Instance UID will always be '1.2.3.4'.

        Parameters
        ----------
        assoc : association.Association
            The association sending the request.
        class_uid : pydicom.uid.UID
            The *Requested SOP Class UID* to use.
        attr_list : list of int, optional
            The *Attribute Identifier List* to use.
        """
        attr_list = [] or attr_list
        return assoc.send_n_get(
            attr_list, class_uid, '1.2.3.4'
        )

    @staticmethod
    def send_set(assoc, class_uid, mod_list):
        """Send an N-SET request via `assoc`

        The *Requested SOP Instance UID will always be '1.2.3.4'.

        Parameters
        ----------
        assoc : association.Association
            The association sending the request.
        class_uid : pydicom.uid.UID
            The *Requested SOP Class UID* to use.
        mod_list : pydicom.dataset.Dataset
            The *Modification List* to use.
        """
        return assoc.send_n_set(
            mod_list, class_uid, '1.2.3.4'
        )

    @staticmethod
    def send_find(assoc):
        pass

    @pytest.mark.parametrize("sop_class, msg_type, warn, fail", REFERENCE_REQUESTS)
    def test_handler_status_dataset(self, sop_class, msg_type, warn, fail):
        """Test the handler returning a status Dataset."""
        status = Dataset()
        status.Status = 0x0000

        ds = Dataset()
        ds.PatientName = 'Test^test'

        ds_in = Dataset()
        ds_in.PatientName = 'TEST^Test^test'

        handle_function = {
            'N-ACTION' : (evt.EVT_N_ACTION, self.handle_dual, [status, ds]),
            'N-CREATE' : (evt.EVT_N_CREATE, self.handle_dual, [status, ds]),
            'N-DELETE' : (evt.EVT_N_DELETE, self.handle_single, [status]),
            'N-EVENT-REPORT' : (evt.EVT_N_EVENT_REPORT, self.handle_dual, [status, ds]),
            'N-GET' : (evt.EVT_N_GET, self.handle_dual, [status, ds]),
            'N-SET' : (evt.EVT_N_SET, self.handle_dual, [status, ds]),
        }

        send_function = {
            'N-ACTION' : (self.send_action, [sop_class]),
            'N-CREATE' : (self.send_create, [sop_class]),
            'N-DELETE' : (self.send_delete, [sop_class]),
            'N-EVENT-REPORT' : (self.send_event_report, [sop_class]),
            'N-GET' : (self.send_get, [sop_class]),
            'N-SET' : (self.send_set, [sop_class, ds_in]),
        }

        event, get_handler, args = handle_function[msg_type]
        handlers = [(event, get_handler(*args))]

        self.ae = ae = AE()
        ae.add_supported_context(sop_class)
        ae.add_requested_context(sop_class)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        (func, args) = send_function[msg_type]
        rsp = func(assoc, *args)
        if msg_type != "N-DELETE":
            status, ds = rsp
            assert status.Status == 0x0000
            assert ds.PatientName == 'Test^test'
        else:
            assert rsp.Status == 0x0000

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    @pytest.mark.parametrize("sop_class, msg_type, warn, fail", REFERENCE_REQUESTS)
    def test_handler_status_dataset_multi(self, sop_class, msg_type, warn, fail):
        """Test the handler returning a status Dataset w/ extra elements."""
        status = Dataset()
        status.Status = 0x0000
        status.ErrorComment = 'Test'
        status.OffendingElement = 0x00080010
        status.ErrorID = 12

        ds = Dataset()
        ds.PatientName = 'Test^test'

        ds_in = Dataset()
        ds_in.PatientName = 'TEST^Test^test'

        handle_function = {
            'N-ACTION' : (evt.EVT_N_ACTION, self.handle_dual, [status, ds]),
            'N-CREATE' : (evt.EVT_N_CREATE, self.handle_dual, [status, ds]),
            'N-DELETE' : (evt.EVT_N_DELETE, self.handle_single, [status]),
            'N-EVENT-REPORT' : (evt.EVT_N_EVENT_REPORT, self.handle_dual, [status, ds]),
            'N-GET' : (evt.EVT_N_GET, self.handle_dual, [status, ds]),
            'N-SET' : (evt.EVT_N_SET, self.handle_dual, [status, ds]),
        }

        send_function = {
            'N-ACTION' : (self.send_action, [sop_class]),
            'N-CREATE' : (self.send_create, [sop_class]),
            'N-DELETE' : (self.send_delete, [sop_class]),
            'N-EVENT-REPORT' : (self.send_event_report, [sop_class]),
            'N-GET' : (self.send_get, [sop_class]),
            'N-SET' : (self.send_set, [sop_class, ds_in]),
        }

        event, get_handler, args = handle_function[msg_type]
        handlers = [(event, get_handler(*args))]

        self.ae = ae = AE()
        ae.add_supported_context(sop_class)
        ae.add_requested_context(sop_class)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        (func, args) = send_function[msg_type]
        rsp = func(assoc, *args)
        if msg_type != "N-DELETE":
            status, ds = rsp
            assert status.Status == 0x0000
            assert ds.PatientName == 'Test^test'
            assert status.ErrorComment == 'Test'
            assert status.ErrorID == 12
            assert 'OffendingElement' not in status
        else:
            assert rsp.Status == 0x0000

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    @pytest.mark.parametrize("sop_class, msg_type, warn, fail", REFERENCE_REQUESTS)
    def test_handler_status_int(self, sop_class, msg_type, warn, fail):
        """Test the handler returning a known int status."""
        ds = Dataset()
        ds.PatientName = 'Test^test'

        ds_in = Dataset()
        ds_in.PatientName = 'TEST^Test^test'

        handle_function = {
            'N-ACTION' : (evt.EVT_N_ACTION, self.handle_dual, [0x0000, ds]),
            'N-CREATE' : (evt.EVT_N_CREATE, self.handle_dual, [0x0000, ds]),
            'N-DELETE' : (evt.EVT_N_DELETE, self.handle_single, [0x0000]),
            'N-EVENT-REPORT' : (evt.EVT_N_EVENT_REPORT, self.handle_dual, [0x0000, ds]),
            'N-GET' : (evt.EVT_N_GET, self.handle_dual, [0x0000, ds]),
            'N-SET' : (evt.EVT_N_SET, self.handle_dual, [0x0000, ds]),
        }

        send_function = {
            'N-ACTION' : (self.send_action, [sop_class]),
            'N-CREATE' : (self.send_create, [sop_class]),
            'N-DELETE' : (self.send_delete, [sop_class]),
            'N-EVENT-REPORT' : (self.send_event_report, [sop_class]),
            'N-GET' : (self.send_get, [sop_class]),
            'N-SET' : (self.send_set, [sop_class, ds_in]),
        }

        event, get_handler, args = handle_function[msg_type]
        handlers = [(event, get_handler(*args))]

        self.ae = ae = AE()
        ae.add_supported_context(sop_class)
        ae.add_requested_context(sop_class)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        (func, args) = send_function[msg_type]
        rsp = func(assoc, *args)
        if msg_type != "N-DELETE":
            status, ds = rsp
            assert status.Status == 0x0000
            assert ds.PatientName == 'Test^test'
        else:
            assert rsp.Status == 0x0000

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    @pytest.mark.parametrize("sop_class, msg_type, warn, fail", REFERENCE_REQUESTS)
    def test_handler_status_int_unknown(self, sop_class, msg_type, warn, fail):
        """Test the handler returning an unknown int status."""
        ds = Dataset()
        ds.PatientName = 'Test^test'

        ds_in = Dataset()
        ds_in.PatientName = 'TEST^Test^test'

        handle_function = {
            'N-ACTION' : (evt.EVT_N_ACTION, self.handle_dual, [0xFFF0, ds]),
            'N-CREATE' : (evt.EVT_N_CREATE, self.handle_dual, [0xFFF0, ds]),
            'N-DELETE' : (evt.EVT_N_DELETE, self.handle_single, [0xFFF0]),
            'N-EVENT-REPORT' : (evt.EVT_N_EVENT_REPORT, self.handle_dual, [0xFFF0, ds]),
            'N-GET' : (evt.EVT_N_GET, self.handle_dual, [0xFFF0, ds]),
            'N-SET' : (evt.EVT_N_SET, self.handle_dual, [0xFFF0, ds]),
        }

        send_function = {
            'N-ACTION' : (self.send_action, [sop_class]),
            'N-CREATE' : (self.send_create, [sop_class]),
            'N-DELETE' : (self.send_delete, [sop_class]),
            'N-EVENT-REPORT' : (self.send_event_report, [sop_class]),
            'N-GET' : (self.send_get, [sop_class]),
            'N-SET' : (self.send_set, [sop_class, ds_in]),
        }

        event, get_handler, args = handle_function[msg_type]
        handlers = [(event, get_handler(*args))]

        self.ae = ae = AE()
        ae.add_supported_context(sop_class)
        ae.add_requested_context(sop_class)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        (func, args) = send_function[msg_type]
        rsp = func(assoc, *args)
        if msg_type != "N-DELETE":
            status, ds = rsp
            assert status.Status == 0xFFF0
            assert ds is None
        else:
            assert rsp.Status == 0xFFF0

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    @pytest.mark.parametrize("sop_class, msg_type, warn, fail", REFERENCE_REQUESTS)
    def test_handler_status_none(self, sop_class, msg_type, warn, fail):
        """Test the handler returning a `None` status."""
        ds = Dataset()
        ds.PatientName = 'Test^test'

        ds_in = Dataset()
        ds_in.PatientName = 'TEST^Test^test'

        handle_function = {
            'N-ACTION' : (evt.EVT_N_ACTION, self.handle_dual, [None, ds]),
            'N-CREATE' : (evt.EVT_N_CREATE, self.handle_dual, [None, ds]),
            'N-DELETE' : (evt.EVT_N_DELETE, self.handle_single, [None]),
            'N-EVENT-REPORT' : (evt.EVT_N_EVENT_REPORT, self.handle_dual, [None, ds]),
            'N-GET' : (evt.EVT_N_GET, self.handle_dual, [None, ds]),
            'N-SET' : (evt.EVT_N_SET, self.handle_dual, [None, ds]),
        }

        send_function = {
            'N-ACTION' : (self.send_action, [sop_class]),
            'N-CREATE' : (self.send_create, [sop_class]),
            'N-DELETE' : (self.send_delete, [sop_class]),
            'N-EVENT-REPORT' : (self.send_event_report, [sop_class]),
            'N-GET' : (self.send_get, [sop_class]),
            'N-SET' : (self.send_set, [sop_class, ds_in]),
        }

        event, get_handler, args = handle_function[msg_type]
        handlers = [(event, get_handler(*args))]

        self.ae = ae = AE()
        ae.add_supported_context(sop_class)
        ae.add_requested_context(sop_class)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        (func, args) = send_function[msg_type]
        rsp = func(assoc, *args)
        if msg_type != "N-DELETE":
            status, ds = rsp
            assert status.Status == 0xC002
            assert ds is None
        else:
            assert rsp.Status == 0xC002

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    @pytest.mark.parametrize("sop_class, msg_type, warn, fail", REFERENCE_REQUESTS)
    def test_handler_exception(self, sop_class, msg_type, warn, fail):
        """Test the handler raising an exception."""
        ds = Dataset()
        ds.PatientName = 'Test^test'

        ds_in = Dataset()
        ds_in.PatientName = 'TEST^Test^test'

        handle_function = {
            'N-ACTION' : (evt.EVT_N_ACTION, self.handle_dual, [0x0000, ds, True]),
            'N-CREATE' : (evt.EVT_N_CREATE, self.handle_dual, [0x0000, ds, True]),
            'N-DELETE' : (evt.EVT_N_DELETE, self.handle_single, [0x0000, True]),
            'N-EVENT-REPORT' : (evt.EVT_N_EVENT_REPORT, self.handle_dual, [0x0000, ds, True]),
            'N-GET' : (evt.EVT_N_GET, self.handle_dual, [0x0000, ds, True]),
            'N-SET' : (evt.EVT_N_SET, self.handle_dual, [0x0000, ds, True]),
        }

        send_function = {
            'N-ACTION' : (self.send_action, [sop_class]),
            'N-CREATE' : (self.send_create, [sop_class]),
            'N-DELETE' : (self.send_delete, [sop_class]),
            'N-EVENT-REPORT' : (self.send_event_report, [sop_class]),
            'N-GET' : (self.send_get, [sop_class]),
            'N-SET' : (self.send_set, [sop_class, ds_in]),
        }

        event, get_handler, args = handle_function[msg_type]
        handlers = [(event, get_handler(*args))]

        self.ae = ae = AE()
        ae.add_supported_context(sop_class)
        ae.add_requested_context(sop_class)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        (func, args) = send_function[msg_type]
        rsp = func(assoc, *args)
        if msg_type != "N-DELETE":
            status, ds = rsp
            assert status.Status == 0x0110
            assert ds is None
        else:
            assert rsp.Status == 0x0110

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    @pytest.mark.parametrize("sop_class, msg_type, warn, fail", REFERENCE_REQUESTS)
    def test_handler_event(self, sop_class, msg_type, warn, fail):
        """Test the handler's event.context attribute."""
        ds = Dataset()
        ds.PatientName = 'Test^test'

        ds_in = Dataset()
        ds_in.PatientName = 'TEST^Test^test'

        handle_function = {
            'N-ACTION' : (evt.EVT_N_ACTION, self.handle_dual, [0x0000, ds]),
            'N-CREATE' : (evt.EVT_N_CREATE, self.handle_dual, [0x0000, ds]),
            'N-DELETE' : (evt.EVT_N_DELETE, self.handle_single, [0x0000]),
            'N-EVENT-REPORT' : (evt.EVT_N_EVENT_REPORT, self.handle_dual, [0x0000, ds]),
            'N-GET' : (evt.EVT_N_GET, self.handle_dual, [0x0000, ds]),
            'N-SET' : (evt.EVT_N_SET, self.handle_dual, [0x0000, ds]),
        }

        send_function = {
            'N-ACTION' : (self.send_action, [sop_class]),
            'N-CREATE' : (self.send_create, [sop_class]),
            'N-DELETE' : (self.send_delete, [sop_class]),
            'N-EVENT-REPORT' : (self.send_event_report, [sop_class]),
            'N-GET' : (self.send_get, [sop_class]),
            'N-SET' : (self.send_set, [sop_class, ds_in]),
        }

        event, get_handler, args = handle_function[msg_type]
        handlers = [(event, get_handler(*args))]

        self.ae = ae = AE()
        ae.add_supported_context(sop_class)
        ae.add_requested_context(sop_class)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        (func, args) = send_function[msg_type]
        rsp = func(assoc, *args)
        if msg_type != "N-DELETE":
            status, ds = rsp
            assert status.Status == 0x0000
        else:
            assert rsp.Status == 0x0000

        # Test context
        cx = self.event.context
        assert cx.context_id == 1
        assert cx.abstract_syntax == sop_class
        assert cx.transfer_syntax == '1.2.840.10008.1.2'

        # Test assoc
        assert self.event.assoc == scp.active_associations[0]

        # Test request
        request_classes = {
            'N-ACTION' : N_ACTION, 'N-CREATE' : N_CREATE,
            'N-DELETE' : N_DELETE, 'N-EVENT-REPORT' : N_EVENT_REPORT,
            'N-GET' : N_GET, 'N-SET' : N_SET,
        }

        req = self.event.request
        assert isinstance(req, request_classes[msg_type])

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

        # Test dataset-likes
        dataset_likes = {
            'N-ACTION' : 'action_information',
            'N-CREATE' : 'attribute_list',
            'N-EVENT-REPORT' : 'event_information',
            'N-GET' : 'attribute_identifiers',
            'N-SET' : 'modification_list',
        }
        if msg_type in dataset_likes:
            ds = getattr(self.event, dataset_likes[msg_type])
            if msg_type != "N-GET":
                assert isinstance(ds, Dataset)
            else:
                assert isinstance(ds, list)

    @pytest.mark.parametrize("sop_class, msg_type, warn, fail", REFERENCE_REQUESTS)
    def test_handler_success(self, sop_class, msg_type, warn, fail):
        """Test the handler returning a success status."""
        ds = Dataset()
        ds.PatientName = 'Test^test'

        ds_in = Dataset()
        ds_in.PatientName = 'TEST^Test^test'

        handle_function = {
            'N-ACTION' : (evt.EVT_N_ACTION, self.handle_dual, [0x0000, ds]),
            'N-CREATE' : (evt.EVT_N_CREATE, self.handle_dual, [0x0000, ds]),
            'N-DELETE' : (evt.EVT_N_DELETE, self.handle_single, [0x0000]),
            'N-EVENT-REPORT' : (evt.EVT_N_EVENT_REPORT, self.handle_dual, [0x0000, ds]),
            'N-GET' : (evt.EVT_N_GET, self.handle_dual, [0x0000, ds]),
            'N-SET' : (evt.EVT_N_SET, self.handle_dual, [0x0000, ds]),
        }

        send_function = {
            'N-ACTION' : (self.send_action, [sop_class]),
            'N-CREATE' : (self.send_create, [sop_class]),
            'N-DELETE' : (self.send_delete, [sop_class]),
            'N-EVENT-REPORT' : (self.send_event_report, [sop_class]),
            'N-GET' : (self.send_get, [sop_class]),
            'N-SET' : (self.send_set, [sop_class, ds_in]),
        }

        event, get_handler, args = handle_function[msg_type]
        handlers = [(event, get_handler(*args))]

        self.ae = ae = AE()
        ae.add_supported_context(sop_class)
        ae.add_requested_context(sop_class)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        (func, args) = send_function[msg_type]
        rsp = func(assoc, *args)
        if msg_type != "N-DELETE":
            status, ds = rsp
            assert status.Status == 0x0000
            assert ds.PatientName == 'Test^test'
        else:
            assert rsp.Status == 0x0000

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    @pytest.mark.parametrize("sop_class, msg_type, warn, fail", REFERENCE_REQUESTS)
    def test_handler_failure_general(self, sop_class, msg_type, warn, fail):
        """Test the handler returning a general failure status."""
        ds = Dataset()
        ds.PatientName = 'Test^test'

        ds_in = Dataset()
        ds_in.PatientName = 'TEST^Test^test'

        handle_function = {
            'N-ACTION' : (evt.EVT_N_ACTION, self.handle_dual, [0x0110, ds]),
            'N-CREATE' : (evt.EVT_N_CREATE, self.handle_dual, [0x0110, ds]),
            'N-DELETE' : (evt.EVT_N_DELETE, self.handle_single, [0x0110]),
            'N-EVENT-REPORT' : (evt.EVT_N_EVENT_REPORT, self.handle_dual, [0x0110, ds]),
            'N-GET' : (evt.EVT_N_GET, self.handle_dual, [0x0110, ds]),
            'N-SET' : (evt.EVT_N_SET, self.handle_dual, [0x0110, ds]),
        }

        send_function = {
            'N-ACTION' : (self.send_action, [sop_class]),
            'N-CREATE' : (self.send_create, [sop_class]),
            'N-DELETE' : (self.send_delete, [sop_class]),
            'N-EVENT-REPORT' : (self.send_event_report, [sop_class]),
            'N-GET' : (self.send_get, [sop_class]),
            'N-SET' : (self.send_set, [sop_class, ds_in]),
        }

        event, get_handler, args = handle_function[msg_type]
        handlers = [(event, get_handler(*args))]

        self.ae = ae = AE()
        ae.add_supported_context(sop_class)
        ae.add_requested_context(sop_class)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        (func, args) = send_function[msg_type]
        rsp = func(assoc, *args)
        if msg_type != "N-DELETE":
            status, ds = rsp
            assert status.Status == 0x0110
            assert ds is None
        else:
            assert rsp.Status == 0x0110

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    @pytest.mark.parametrize("sop_class, msg_type, warn, fail", REFERENCE_REQUESTS)
    def test_handler_failure_custom(self, sop_class, msg_type, warn, fail):
        """Test the handler returning a service specific failure status."""
        if fail is None:
            return

        ds = Dataset()
        ds.PatientName = 'Test^test'

        ds_in = Dataset()
        ds_in.PatientName = 'TEST^Test^test'

        handle_function = {
            'N-ACTION' : (evt.EVT_N_ACTION, self.handle_dual, [fail, ds]),
            'N-CREATE' : (evt.EVT_N_CREATE, self.handle_dual, [fail, ds]),
            'N-DELETE' : (evt.EVT_N_DELETE, self.handle_single, [fail]),
            'N-EVENT-REPORT' : (evt.EVT_N_EVENT_REPORT, self.handle_dual, [fail, ds]),
            'N-GET' : (evt.EVT_N_GET, self.handle_dual, [fail, ds]),
            'N-SET' : (evt.EVT_N_SET, self.handle_dual, [fail, ds]),
        }

        send_function = {
            'N-ACTION' : (self.send_action, [sop_class]),
            'N-CREATE' : (self.send_create, [sop_class]),
            'N-DELETE' : (self.send_delete, [sop_class]),
            'N-EVENT-REPORT' : (self.send_event_report, [sop_class]),
            'N-GET' : (self.send_get, [sop_class]),
            'N-SET' : (self.send_set, [sop_class, ds_in]),
        }

        event, get_handler, args = handle_function[msg_type]
        handlers = [(event, get_handler(*args))]

        self.ae = ae = AE()
        ae.add_supported_context(sop_class)
        ae.add_requested_context(sop_class)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        (func, args) = send_function[msg_type]
        rsp = func(assoc, *args)
        if msg_type != "N-DELETE":
            status, ds = rsp
            assert status.Status == fail
            assert ds is None
        else:
            assert rsp.Status == fail

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    @pytest.mark.parametrize("sop_class, msg_type, warn, fail", REFERENCE_REQUESTS)
    def test_handler_warning(self, sop_class, msg_type, warn, fail):
        """Test the handler returning a warning status."""
        if warn is None:
            return

        ds = Dataset()
        ds.PatientName = 'Test^test'

        ds_in = Dataset()
        ds_in.PatientName = 'TEST^Test^test'

        handle_function = {
            'N-ACTION' : (evt.EVT_N_ACTION, self.handle_dual, [warn, ds]),
            'N-CREATE' : (evt.EVT_N_CREATE, self.handle_dual, [warn, ds]),
            'N-DELETE' : (evt.EVT_N_DELETE, self.handle_single, [warn]),
            'N-EVENT-REPORT' : (evt.EVT_N_EVENT_REPORT, self.handle_dual, [warn, ds]),
            'N-GET' : (evt.EVT_N_GET, self.handle_dual, [warn, ds]),
            'N-SET' : (evt.EVT_N_SET, self.handle_dual, [warn, ds]),
        }

        send_function = {
            'N-ACTION' : (self.send_action, [sop_class]),
            'N-CREATE' : (self.send_create, [sop_class]),
            'N-DELETE' : (self.send_delete, [sop_class]),
            'N-EVENT-REPORT' : (self.send_event_report, [sop_class]),
            'N-GET' : (self.send_get, [sop_class]),
            'N-SET' : (self.send_set, [sop_class, ds_in]),
        }

        event, get_handler, args = handle_function[msg_type]
        handlers = [(event, get_handler(*args))]

        self.ae = ae = AE()
        ae.add_supported_context(sop_class)
        ae.add_requested_context(sop_class)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        (func, args) = send_function[msg_type]
        rsp = func(assoc, *args)
        if msg_type != "N-DELETE":
            status, ds = rsp
            assert status.Status == warn
            assert ds.PatientName == 'Test^test'
        else:
            assert rsp.Status == warn

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    @pytest.mark.parametrize("sop_class, msg_type, warn, fail", REFERENCE_REQUESTS)
    def test_handler_none(self, sop_class, msg_type, warn, fail):
        """Test the handler returning None."""
        if msg_type == 'N-DELETE':
            return

        ds = Dataset()
        ds.PatientName = 'Test^test'

        ds_in = Dataset()
        ds_in.PatientName = 'TEST^Test^test'

        handle_function = {
            'N-ACTION' : (evt.EVT_N_ACTION, self.handle_dual, [0x0000, None]),
            'N-CREATE' : (evt.EVT_N_CREATE, self.handle_dual, [0x0000, None]),
            'N-DELETE' : (evt.EVT_N_DELETE, self.handle_single, [0x0000]),
            'N-EVENT-REPORT' : (evt.EVT_N_EVENT_REPORT, self.handle_dual, [0x0000, None]),
            'N-GET' : (evt.EVT_N_GET, self.handle_dual, [0x0000, None]),
            'N-SET' : (evt.EVT_N_SET, self.handle_dual, [0x0000, None]),
        }

        send_function = {
            'N-ACTION' : (self.send_action, [sop_class]),
            'N-CREATE' : (self.send_create, [sop_class]),
            'N-DELETE' : (self.send_delete, [sop_class]),
            'N-EVENT-REPORT' : (self.send_event_report, [sop_class]),
            'N-GET' : (self.send_get, [sop_class]),
            'N-SET' : (self.send_set, [sop_class, ds_in]),
        }

        event, get_handler, args = handle_function[msg_type]
        handlers = [(event, get_handler(*args))]

        self.ae = ae = AE()
        ae.add_supported_context(sop_class)
        ae.add_requested_context(sop_class)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        (func, args) = send_function[msg_type]
        rsp = func(assoc, *args)
        status, ds = rsp
        assert status.Status == 0x0000
        assert ds == Dataset()

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    @pytest.mark.parametrize("sop_class, msg_type, warn, fail", REFERENCE_REQUESTS)
    def test_handler_bad_dataset(self, sop_class, msg_type, warn, fail):
        """Test the handler returning an unencodable dataset."""
        if msg_type == 'N-DELETE':
            return

        ds = Dataset()
        ds.PatientName = 'Test^test'

        ds_in = Dataset()
        ds_in.PatientName = 'TEST^Test^test'

        def test():
            pass

        handle_function = {
            'N-ACTION' : (evt.EVT_N_ACTION, self.handle_dual, [0x0000, test]),
            'N-CREATE' : (evt.EVT_N_CREATE, self.handle_dual, [0x0000, test]),
            'N-DELETE' : (evt.EVT_N_DELETE, self.handle_single, [0x0000]),
            'N-EVENT-REPORT' : (evt.EVT_N_EVENT_REPORT, self.handle_dual, [0x0000, test]),
            'N-GET' : (evt.EVT_N_GET, self.handle_dual, [0x0000, test]),
            'N-SET' : (evt.EVT_N_SET, self.handle_dual, [0x0000, test]),
        }

        send_function = {
            'N-ACTION' : (self.send_action, [sop_class]),
            'N-CREATE' : (self.send_create, [sop_class]),
            'N-DELETE' : (self.send_delete, [sop_class]),
            'N-EVENT-REPORT' : (self.send_event_report, [sop_class]),
            'N-GET' : (self.send_get, [sop_class]),
            'N-SET' : (self.send_set, [sop_class, ds_in]),
        }

        event, get_handler, args = handle_function[msg_type]
        handlers = [(event, get_handler(*args))]

        self.ae = ae = AE()
        ae.add_supported_context(sop_class)
        ae.add_requested_context(sop_class)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        (func, args) = send_function[msg_type]
        rsp = func(assoc, *args)
        status, ds = rsp
        assert status.Status == 0x0110
        assert ds is None

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    @pytest.mark.parametrize("sop_class, msg_type, warn, fail", REFERENCE_REQUESTS)
    def test_bad_request(self, sop_class, msg_type, warn, fail):
        """Test the SCP receiving an invalid DIMSE message type."""
        ds = Dataset()
        ds.SOPClassUID = sop_class
        ds.SOPInstanceUID = '1.2.3.4'
        ds.file_meta = Dataset()
        ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian

        self.ae = ae = AE()
        ae.add_supported_context(sop_class)
        ae.add_requested_context(sop_class)
        scp = ae.start_server(('', 11112), block=False)

        ae.acse_timeout = 5
        ae.dimse_timeout = 0.5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        status = assoc.send_c_store(ds)
        assert status == Dataset()
        assert assoc.is_aborted

        scp.shutdown()


# TODO: Test UPS C-FIND separately
