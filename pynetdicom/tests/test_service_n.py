"""Tests for the DIMSE-N Service Classes."""
from io import BytesIO
import time

import pytest

from pydicom.dataset import Dataset
from pydicom.uid import ImplicitVRLittleEndian, ExplicitVRLittleEndian

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

    def abort_dual(self, status, ds):
        """Return a callable function that aborts then returns two values.

        Parameters
        ----------
        status : int or pydicom.dataset.Dataset
            The first value the callable should return
        ds : None or pydicom.dataset.Dataset
            The second value the callable should return

        Returns
        -------
        callable
        """
        def handler(event):
            self.event = event
            event.assoc.abort()
            return status, ds

        return handler

    def abort_single(self, status):
        """Return a callable function that aborts then returns one value.

        Parameters
        ----------
        status : int or pydicom.dataset.Dataset
            The value the callable should return

        Returns
        -------
        callable
        """
        def handler(event):
            self.event = event
            event.assoc.abort()
            return status

        return handler

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

        time.sleep(0.1)
        assert assoc.is_aborted

        scp.shutdown()

    def test_handler_get_empty(self):
        """Test the handler returning None."""
        ds = Dataset()
        ds.PatientName = 'Test^test'
        handlers = [(evt.EVT_N_GET, self.handle_dual(0x0000, ds))]

        self.ae = ae = AE()
        ae.add_supported_context(DisplaySystemSOPClass)
        ae.add_requested_context(DisplaySystemSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get([], DisplaySystemSOPClass, '1.2.3.4')
        assert status.Status == 0x0000
        assert ds.PatientName == 'Test^test'

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    @pytest.mark.parametrize("sop_class, msg_type, warn, fail", REFERENCE_REQUESTS)
    def test_handler_aborts(self, sop_class, msg_type, warn, fail):
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

        def send_abort(event):
            event.assoc.abort()

        event, get_handler, args = handle_function[msg_type]
        handlers = [(event, send_abort)]
        #handlers = [(event, get_handler(*args))]

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
            assert status == Dataset()
            assert ds == None
        else:
            assert rsp == Dataset()

        time.sleep(0.1)
        assert assoc.is_aborted
        scp.shutdown()

    @pytest.mark.parametrize("sop_class, msg_type, warn, fail", REFERENCE_REQUESTS)
    def test_handler_aborts_before(self, sop_class, msg_type, warn, fail):
        """Test the handler returning a success status."""
        ds = Dataset()
        ds.PatientName = 'Test^test'

        ds_in = Dataset()
        ds_in.PatientName = 'TEST^Test^test'

        handle_function = {
            'N-ACTION' : (evt.EVT_N_ACTION, self.abort_dual, [0x0000, ds]),
            'N-CREATE' : (evt.EVT_N_CREATE, self.abort_dual, [0x0000, ds]),
            'N-DELETE' : (evt.EVT_N_DELETE, self.abort_single, [0x0000]),
            'N-EVENT-REPORT' : (evt.EVT_N_EVENT_REPORT, self.abort_dual, [0x0000, ds]),
            'N-GET' : (evt.EVT_N_GET, self.abort_dual, [0x0000, ds]),
            'N-SET' : (evt.EVT_N_SET, self.abort_dual, [0x0000, ds]),
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
            assert status == Dataset()
            assert ds == None
        else:
            assert rsp == Dataset()

        time.sleep(0.1)
        assert assoc.is_aborted
        scp.shutdown()


class TestUPSFindServiceClass(object):
    """Test the Unified Proecedure Step (Find) Service Class"""
    def setup(self):
        """Run prior to each test"""
        self.query = Dataset()
        self.query.QueryRetrieveLevel = "PATIENT"
        self.query.PatientName = '*'

        self.ae = None

    def teardown(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

    def test_bad_req_identifier(self):
        """Test SCP handles a bad request identifier"""
        def handle(event):
            try:
                ds = event.identifier
                for elem in ds.iterall():
                    pass
            except:
                yield 0xC310, None
                return

            yield 0x0000, None

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(UnifiedProcedureStepPullSOPClass)
        ae.add_requested_context(
            UnifiedProcedureStepPullSOPClass,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        req = C_FIND()
        req.MessageID = 1
        req.AffectedSOPClassUID = UnifiedProcedureStepPullSOPClass
        req.Priority = 2
        req.Identifier = BytesIO(b'\x08\x00\x01\x00\x40\x40\x00\x00\x00\x00\x00\x08\x00\x49')
        assoc._reactor_checkpoint.clear()
        assoc.dimse.send_msg(req, 1)
        cx_id, rsp = assoc.dimse.get_msg(True)
        assoc._reactor_checkpoint.set()
        assert rsp.Status == 0xC310

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_handler_status_dataset(self):
        """Test handler yielding a Dataset status"""
        def handle(event):
            status = Dataset()
            status.Status = 0xFF00
            yield status, self.query
            yield 0x0000, None

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(UnifiedProcedureStepPullSOPClass)
        ae.add_requested_context(
            UnifiedProcedureStepPullSOPClass,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(
            self.query,
            UnifiedProcedureStepPullSOPClass
        )
        status, identifier = next(result)
        assert status.Status == 0xFF00
        status, identifier = next(result)
        assert status.Status == 0x0000
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_handler_status_dataset_multi(self):
        """Test handler yielding a Dataset status with other elements"""
        def handle(event):
            status = Dataset()
            status.Status = 0xFF00
            status.ErrorComment = 'Test'
            status.OffendingElement = 0x00010001
            yield status, self.query

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(UnifiedProcedureStepPullSOPClass)
        ae.add_requested_context(
            UnifiedProcedureStepPullSOPClass,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(
            self.query,
            query_model=UnifiedProcedureStepPullSOPClass
        )
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert status.ErrorComment == 'Test'
        assert status.OffendingElement == 0x00010001
        status, identifier = next(result)
        assert status.Status == 0x0000
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_handler_status_int(self):
        """Test handler yielding an int status"""
        def handle(event):
            yield 0xFF00, self.query

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(UnifiedProcedureStepPullSOPClass)
        ae.add_requested_context(
            UnifiedProcedureStepPullSOPClass,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(
            self.query,
            query_model=UnifiedProcedureStepPullSOPClass
        )
        status, identifier = next(result)
        assert status.Status == 0xFF00
        status, identifier = next(result)
        assert status.Status == 0x0000
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_handler_status_unknown(self):
        """Test SCP handles handler yielding a unknown status"""
        def handle(event):
            yield 0xFFF0,  None

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(UnifiedProcedureStepPullSOPClass)
        ae.add_requested_context(
            UnifiedProcedureStepPullSOPClass,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(
            self.query,
            query_model=UnifiedProcedureStepPullSOPClass
        )
        status, identifier = next(result)
        assert status.Status == 0xFFF0
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_handler_status_invalid(self):
        """Test SCP handles handler yielding a invalid status"""
        def handle(event):
            yield 'Failure',  None

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(UnifiedProcedureStepPullSOPClass)
        ae.add_requested_context(
            UnifiedProcedureStepPullSOPClass,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(
            self.query,
            query_model=UnifiedProcedureStepPullSOPClass
        )
        status, identifier = next(result)
        assert status.Status == 0xC002
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_handler_status_none(self):
        """Test SCP handles handler not yielding a status"""
        def handle(event):
            yield None,  self.query

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(UnifiedProcedureStepPullSOPClass)
        ae.add_requested_context(
            UnifiedProcedureStepPullSOPClass,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(
            self.query,
            query_model=UnifiedProcedureStepPullSOPClass
        )
        status, identifier = next(result)
        assert status.Status == 0xC002
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_handler_no_match(self):
        """Test SCP handles handler not yielding a status"""
        def handle(event):
            return

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(UnifiedProcedureStepPullSOPClass)
        ae.add_requested_context(
            UnifiedProcedureStepPullSOPClass,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(
            self.query,
            query_model=UnifiedProcedureStepPullSOPClass
        )
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_handler_exception_prior(self):
        """Test SCP handles handler yielding an exception before yielding"""
        def handle(event):
            raise ValueError
            yield 0xFF00, self.query

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(UnifiedProcedureStepPullSOPClass)
        ae.add_requested_context(
            UnifiedProcedureStepPullSOPClass,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(
            self.query,
            query_model=UnifiedProcedureStepPullSOPClass
        )
        status, identifier = next(result)
        assert status.Status == 0xC311
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_handler_exception_default(self):
        """Test default handler raises exception"""
        self.ae = ae = AE()
        ae.add_supported_context(UnifiedProcedureStepPullSOPClass)
        ae.add_requested_context(
            UnifiedProcedureStepPullSOPClass,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(
            self.query,
            query_model=UnifiedProcedureStepPullSOPClass
        )
        status, identifier = next(result)
        assert status.Status == 0xC311
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_handler_exception_during(self):
        """Test SCP handles handler yielding an exception after first yield"""
        def handle(event):
            yield 0xFF00, self.query
            raise ValueError

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(UnifiedProcedureStepPullSOPClass)
        ae.add_requested_context(
            UnifiedProcedureStepPullSOPClass,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(
            self.query,
            query_model=UnifiedProcedureStepPullSOPClass
        )
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier == self.query
        status, identifier = next(result)
        assert status.Status == 0xC311
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_handler_bad_identifier(self):
        """Test SCP handles a bad handler identifier"""
        def handle(event):
            yield 0xFF00, None
            yield 0xFE00, None

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(UnifiedProcedureStepPullSOPClass)
        ae.add_requested_context(
            UnifiedProcedureStepPullSOPClass,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(
            self.query,
            query_model=UnifiedProcedureStepPullSOPClass
        )
        status, identifier = next(result)
        assert status.Status == 0xC312
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_pending_cancel(self):
        """Test handler yielding pending then cancel status"""
        def handle(event):
            yield 0xFF00, self.query
            yield 0xFE00, None

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(UnifiedProcedureStepPullSOPClass)
        ae.add_requested_context(
            UnifiedProcedureStepPullSOPClass,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(
            self.query,
            query_model=UnifiedProcedureStepPullSOPClass
        )
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier == self.query
        status, identifier = next(result)
        assert status.Status == 0xFE00
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_pending_success(self):
        """Test handler yielding pending then success status"""
        def handle(event):
            yield 0xFF01,  self.query
            yield 0x0000, None
            yield 0xA700, None

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(UnifiedProcedureStepPullSOPClass)
        ae.add_requested_context(
            UnifiedProcedureStepPullSOPClass,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(
            self.query,
            query_model=UnifiedProcedureStepPullSOPClass
        )
        status, identifier = next(result)
        assert status.Status == 0xFF01
        assert identifier == self.query
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_pending_failure(self):
        """Test handler yielding pending then failure status"""
        def handle(event):
            yield 0xFF00, self.query
            yield 0xA700, None
            yield 0x0000, None

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(UnifiedProcedureStepPullSOPClass)
        ae.add_requested_context(
            UnifiedProcedureStepPullSOPClass,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(
            self.query,
            query_model=UnifiedProcedureStepPullSOPClass
        )
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier == self.query
        status, identifier = next(result)
        assert status.Status == 0xA700
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_multi_pending_cancel(self):
        """Test handler yielding multiple pending then cancel status"""
        def handle(event):
            yield 0xFF00, self.query
            yield 0xFF01,  self.query
            yield 0xFF00, self.query
            yield 0xFE00, None
            yield 0x0000, None

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(UnifiedProcedureStepPullSOPClass)
        ae.add_requested_context(
            UnifiedProcedureStepPullSOPClass,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(
            self.query,
            query_model=UnifiedProcedureStepPullSOPClass
        )
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier == self.query
        status, identifier = next(result)
        assert status.Status == 0xFF01
        assert identifier == self.query
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier == self.query
        status, identifier = next(result)
        assert status.Status == 0xFE00
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_multi_pending_success(self):
        """Test handler yielding multiple pending then success status"""
        def handle(event):
            yield 0xFF00, self.query
            yield 0xFF01,  self.query
            yield 0xFF00, self.query
            yield 0x0000, self.query
            yield 0xA700, None

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(UnifiedProcedureStepPullSOPClass)
        ae.add_requested_context(
            UnifiedProcedureStepPullSOPClass,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(
            self.query,
            query_model=UnifiedProcedureStepPullSOPClass
        )
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier == self.query
        status, identifier = next(result)
        assert status.Status == 0xFF01
        assert identifier == self.query
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier == self.query
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_multi_pending_failure(self):
        """Test handler yielding multiple pending then failure status"""
        def handle(event):
            yield 0xFF00, self.query
            yield 0xFF01,  self.query
            yield 0xFF00, self.query
            yield 0xA700, self.query
            yield 0x0000, None

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(UnifiedProcedureStepPullSOPClass)
        ae.add_requested_context(
            UnifiedProcedureStepPullSOPClass,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(
            self.query,
            query_model=UnifiedProcedureStepPullSOPClass
        )
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier == self.query
        status, identifier = next(result)
        assert status.Status == 0xFF01
        assert identifier == self.query
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier == self.query
        status, identifier = next(result)
        assert status.Status == 0xA700
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_scp_handler_context(self):
        """Test handler event's context attribute"""
        attrs = {}
        def handle(event):
            attrs['context'] = event.context
            attrs['assoc'] = event.assoc
            attrs['request'] = event.request
            attrs['identifier'] = event.identifier
            yield 0xFF00, self.query

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(UnifiedProcedureStepPullSOPClass)
        ae.add_requested_context(UnifiedProcedureStepPullSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(
            self.query,
            query_model=UnifiedProcedureStepPullSOPClass
        )
        status, identifier = next(result)
        assert status.Status == 0xFF00
        status, identifier = next(result)
        assert status.Status == 0x0000
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released

        cx = attrs['context']
        assert cx.context_id == 1
        assert cx.abstract_syntax == UnifiedProcedureStepPullSOPClass
        assert cx.transfer_syntax == '1.2.840.10008.1.2'

        scp.shutdown()

    def test_scp_handler_assoc(self):
        """Test handler event's assoc attribute"""
        attrs = {}
        def handle(event):
            attrs['context'] = event.context
            attrs['assoc'] = event.assoc
            attrs['request'] = event.request
            attrs['identifier'] = event.identifier
            yield 0xFF00, self.query

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(UnifiedProcedureStepPullSOPClass)
        ae.add_requested_context(UnifiedProcedureStepPullSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(
            self.query,
            query_model=UnifiedProcedureStepPullSOPClass
        )
        status, identifier = next(result)
        assert status.Status == 0xFF00
        status, identifier = next(result)
        assert status.Status == 0x0000
        with pytest.raises(StopIteration):
            next(result)

        scp_assoc = attrs['assoc']
        assert scp_assoc == scp.active_associations[0]

        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_scp_handler_request(self):
        """Test handler event's request attribute"""
        attrs = {}
        def handle(event):
            attrs['context'] = event.context
            attrs['assoc'] = event.assoc
            attrs['request'] = event.request
            attrs['identifier'] = event.identifier
            yield 0xFF00, self.query

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(UnifiedProcedureStepPullSOPClass)
        ae.add_requested_context(UnifiedProcedureStepPullSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(
            self.query,
            query_model=UnifiedProcedureStepPullSOPClass
        )
        status, identifier = next(result)
        assert status.Status == 0xFF00
        status, identifier = next(result)
        assert status.Status == 0x0000
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released

        req = attrs['request']
        assert req.MessageID == 1
        assert isinstance(req, C_FIND)

        scp.shutdown()

    def test_scp_handler_identifier(self):
        """Test handler event's identifier property"""
        attrs = {}
        def handle(event):
            attrs['context'] = event.context
            attrs['assoc'] = event.assoc
            attrs['request'] = event.request
            attrs['identifier'] = event.identifier

            ds = event.identifier
            yield 0xFF00, self.query

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(UnifiedProcedureStepPullSOPClass)
        ae.add_requested_context(UnifiedProcedureStepPullSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(
            self.query,
            query_model=UnifiedProcedureStepPullSOPClass
        )
        status, identifier = next(result)
        assert status.Status == 0xFF00
        status, identifier = next(result)
        assert status.Status == 0x0000
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released

        ds = attrs['identifier']
        ds.QueryRetrieveLevel = "PATIENT"
        ds.PatientName = '*'

        scp.shutdown()

    def test_scp_cancelled(self):
        """Test is_cancelled works as expected."""
        cancel_results = []
        def handle(event):
            ds = Dataset()
            ds.PatientID = '123456'
            cancel_results.append(event.is_cancelled)
            yield 0xFF00, ds
            time.sleep(0.5)
            cancel_results.append(event.is_cancelled)
            yield 0xFE00, None
            yield 0xFF00, self.query

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(UnifiedProcedureStepPullSOPClass)
        ae.add_requested_context(UnifiedProcedureStepPullSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        identifier = Dataset()
        identifier.PatientID = '*'
        results = assoc.send_c_find(
            identifier,
            msg_id=11142,
            query_model=UnifiedProcedureStepPullSOPClass
        )
        time.sleep(0.2)
        assoc.send_c_cancel(1, 3)
        assoc.send_c_cancel(11142, 1)

        status, ds = next(results)
        assert status.Status == 0xFF00
        assert ds.PatientID == '123456'
        status, ds = next(results)
        assert status.Status == 0xFE00  # Cancelled
        assert ds is None

        with pytest.raises(StopIteration):
            next(results)

        assoc.release()
        assert assoc.is_released

        assert cancel_results == [False, True]

        scp.shutdown()

    def test_handler_aborts_before(self):
        """Test handler aborts before any yields."""
        def handle(event):
            event.assoc.abort()
            yield 0xFF00, self.query

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(UnifiedProcedureStepPullSOPClass)
        ae.add_requested_context(UnifiedProcedureStepPullSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(
            self.query, UnifiedProcedureStepPullSOPClass
        )
        status, identifier = next(result)
        assert status == Dataset()
        assert identifier == None
        with pytest.raises(StopIteration):
            next(result)

        time.sleep(0.1)
        assert assoc.is_aborted
        scp.shutdown()

    def test_handler_aborts_before_solo(self):
        """Test handler aborts before any yields."""
        def handle(event):
            event.assoc.abort()

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(UnifiedProcedureStepPullSOPClass)
        ae.add_requested_context(UnifiedProcedureStepPullSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(
            self.query, UnifiedProcedureStepPullSOPClass
        )
        status, identifier = next(result)
        assert status == Dataset()
        assert identifier == None
        with pytest.raises(StopIteration):
            next(result)

        time.sleep(0.1)
        assert assoc.is_aborted
        scp.shutdown()

    def test_handler_aborts_during(self):
        """Test handler aborts during any yields."""
        def handle(event):
            yield 0xFF00, self.query
            event.assoc.abort()
            yield 0xFF01,  self.query

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(UnifiedProcedureStepPullSOPClass)
        ae.add_requested_context(UnifiedProcedureStepPullSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(
            self.query, UnifiedProcedureStepPullSOPClass
        )
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier == self.query
        status, identifier = next(result)
        with pytest.raises(StopIteration):
            next(result)

        time.sleep(0.1)
        assert assoc.is_aborted
        scp.shutdown()

    def test_handler_aborts_after(self):
        """Test handler aborts after any yields."""
        def handle(event):
            yield 0xFF00, self.query
            yield 0xFF01,  self.query
            event.assoc.abort()

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(UnifiedProcedureStepPullSOPClass)
        ae.add_requested_context(UnifiedProcedureStepPullSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(
            self.query, UnifiedProcedureStepPullSOPClass
        )
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier == self.query
        status, identifier = next(result)
        assert status.Status == 0xFF01
        assert identifier == self.query
        status, identifier = next(result)
        with pytest.raises(StopIteration):
            next(result)

        time.sleep(0.1)
        assert assoc.is_aborted
        scp.shutdown()


class TestNEventReport(object):
    """Functional tests for N-EVENT-REPORT services."""
    def setup(self):
        """Run prior to each test"""
        self.ae = None

    def teardown(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

    def test_same_assoc(self):
        """Test SCP sending over the same association."""
        def trigger_ner(event):
            ds = Dataset()
            ds.PatientName = 'Test2'
            event.assoc.send_n_event_report(
                ds,
                1,
                PrintJobSOPClass,
                '1.2.3'
            )

            ds = Dataset()
            ds.PatientName = 'Test'
            return 0x0000, ds

        scp_hh = [(evt.EVT_N_GET, trigger_ner)]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(PrintJobSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=scp_hh)

        events = []
        def handle_ner(event):
            events.append(event)
            ds = Dataset()
            ds.PatientName = 'Test3'
            return 0x0000, ds

        scu_hh = [(evt.EVT_N_EVENT_REPORT, handle_ner)]

        ae.add_requested_context(PrintJobSOPClass)
        assoc = ae.associate('', 11112, evt_handlers=scu_hh)
        assert assoc.is_established

        status, attr = assoc.send_n_get(
            [(0x00080008)],
            PrintJobSOPClass,
            '1.2.3.4'
        )

        assoc.release()
        assert assoc.is_released

        scp.shutdown()

        e = events[0]
        assert e.event == evt.EVT_N_EVENT_REPORT
        assert e.event_type == 1
        assert e.event_information.PatientName == 'Test2'

    def test_new_assoc(self):
        """Test SCP sending over a new association."""
        def trigger_ner(event):
            ds = Dataset()
            ds.PatientName = 'Test2'

            assoc = event.assoc.ae.associate('', 11113)
            assoc.send_n_event_report(
                ds,
                1,
                PrintJobSOPClass,
                '1.2.3'
            )
            assoc.release()

        scp_hh = [(evt.EVT_ESTABLISHED, trigger_ner)]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(PrintJobSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=scp_hh)

        events = []
        def handle_ner(event):
            events.append(event)
            ds = Dataset()
            ds.PatientName = 'Test3'
            return 0x0000, ds

        scu_hh = [(evt.EVT_N_EVENT_REPORT, handle_ner)]
        ner_scp = ae.start_server(('', 11113), block=False, evt_handlers=scu_hh)

        ae.add_requested_context(PrintJobSOPClass)
        assoc = ae.associate('', 11112)
        assert assoc.is_established

        assoc.release()
        assert assoc.is_released

        scp.shutdown()

        e = events[0]
        assert e.event == evt.EVT_N_EVENT_REPORT
        assert e.event_type == 1
        assert e.event_information.PatientName == 'Test2'
