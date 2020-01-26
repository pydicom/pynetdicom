"""Association testing for DIMSE-N services"""

from io import BytesIO
try:
    import queue
except ImportError:
    import Queue as queue  # Python 2 compatibility
import time

import pytest

from pydicom.dataset import Dataset
from pydicom.tag import Tag
from pydicom.uid import UID, ImplicitVRLittleEndian, ExplicitVRLittleEndian

from pynetdicom import AE, debug_logger, evt
from pynetdicom.dimse_primitives import (
    N_EVENT_REPORT, N_GET, N_SET, N_ACTION, N_CREATE, N_DELETE
)
from pynetdicom.dsutils import encode, decode
from pynetdicom.sop_class import (
    DisplaySystemSOPClass,
    VerificationSOPClass,
    PrintJobSOPClass,
    ModalityPerformedProcedureStepNotificationSOPClass,
    ModalityPerformedProcedureStepRetrieveSOPClass,
    ModalityPerformedProcedureStepSOPClass,
    ProceduralEventLoggingSOPClass,
    BasicFilmSessionSOPClass,
    BasicGrayscalePrintManagementMetaSOPClass,
    BasicColorPrintManagementMetaSOPClass,
    PrinterSOPClass,
)
from pynetdicom.service_class import ServiceClass


#debug_logger()


class DummyDIMSE(object):
    def __init__(self):
        self.status = None

    def send_msg(self, req, context_id):
        self.req = req
        self.context_id = context_id

    def get_msg(self, block=False):
        return None, None


class TestAssociationSendNEventReport(object):
    """Run tests on Assocation send_n_event_report."""
    def setup(self):
        self.ae = None

    def teardown(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

    def test_must_be_associated(self):
        """Test can't send without association."""
        def handle(event):
            return 0x0000, Dataset()

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(ModalityPerformedProcedureStepNotificationSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False,
            evt_handlers=[(evt.EVT_N_EVENT_REPORT, handle)]
        )

        ae.add_requested_context(ModalityPerformedProcedureStepNotificationSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assoc.release()
        assert not assoc.is_established

        with pytest.raises(RuntimeError):
            assoc.send_n_event_report(None, None, None, None)

        scp.shutdown()

    def test_no_abstract_syntax_match(self):
        """Test SCU when no accepted abstract syntax"""
        def handle(event):
            return 0x0000, Dataset()

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(ModalityPerformedProcedureStepNotificationSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False,
            evt_handlers=[(evt.EVT_N_EVENT_REPORT, handle)]
        )

        ae.add_requested_context(ModalityPerformedProcedureStepNotificationSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        msg = (
            r"No presentation context for 'Verification SOP Class' has been "
            r"accepted by the peer for the SCU role"
        )
        with pytest.raises(ValueError, match=msg):
            assoc.send_n_event_report(
                None, None, VerificationSOPClass, None
            )

        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rq_bad_dataset_raises(self):
        """Test sending bad dataset raises exception."""
        def handle(event):
            return 0x0000, Dataset()

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(ModalityPerformedProcedureStepNotificationSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False,
            evt_handlers=[(evt.EVT_N_EVENT_REPORT, handle)]
        )

        ae.add_requested_context(
            ModalityPerformedProcedureStepNotificationSOPClass,
            ExplicitVRLittleEndian
        )
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        ds = Dataset()
        ds.PerimeterValue = b'\x00\x01'
        msg = r"Unable to encode the supplied 'Event Information' dataset"
        with pytest.raises(ValueError, match=msg):
            assoc.send_n_event_report(
                ds, 1,
                ModalityPerformedProcedureStepNotificationSOPClass,
                '1.2.3'
            )

        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_none(self):
        """Test no response from peer"""
        def handle(event):
            time.sleep(0.5)
            return 0x0000, Dataset()

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 0.4
        ae.network_timeout = 5
        ae.add_supported_context(ModalityPerformedProcedureStepNotificationSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False,
            evt_handlers=[(evt.EVT_N_EVENT_REPORT, handle)]
        )

        ae.add_requested_context(ModalityPerformedProcedureStepNotificationSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_event_report(
            ds, 1,
            ModalityPerformedProcedureStepNotificationSOPClass,
            '1.2.840.10008.5.1.1.40.1'
        )
        assert status == Dataset()
        assert ds is None
        assert assoc.is_aborted

        scp.shutdown()

    def test_rsp_invalid(self):
        """Test invalid DIMSE message received from peer"""
        def handle(event):
            return 0x0000, Dataset()

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(ModalityPerformedProcedureStepNotificationSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False,
            evt_handlers=[(evt.EVT_N_EVENT_REPORT, handle)]
        )

        ae.add_requested_context(ModalityPerformedProcedureStepNotificationSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        class DummyResponse():
            is_valid_response = False

        class DummyDIMSE():
            msg_queue = queue.Queue()
            gotten = False
            def send_msg(*args, **kwargs): return
            def get_msg(self, *args, **kwargs):
                if not self.gotten:
                    self.gotten = True
                    return None, DummyResponse()
                return None, None

        assoc._reactor_checkpoint.clear()
        while not assoc._is_paused:
            time.sleep(0.01)
        assoc.dimse = DummyDIMSE()

        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_event_report(
            ds, 1,
            ModalityPerformedProcedureStepNotificationSOPClass,
            '1.2.840.10008.5.1.1.40.1'
        )

        assert status == Dataset()
        assert ds is None
        assert assoc.is_aborted

        scp.shutdown()

    def test_rsp_failure(self):
        """Test receiving a failure response from the peer"""
        def handle(event):
            return 0x0112, None

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(ModalityPerformedProcedureStepNotificationSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False,
            evt_handlers=[(evt.EVT_N_EVENT_REPORT, handle)]
        )

        ae.add_requested_context(ModalityPerformedProcedureStepNotificationSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_event_report(
            ds, 1,
            ModalityPerformedProcedureStepNotificationSOPClass,
            '1.2.840.10008.5.1.1.40.1'
        )
        assert status.Status == 0x0112
        assert ds is None
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_warning(self):
        """Test receiving a warning response from the peer"""
        def handle(event):
            return 0x0116, event.event_information

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(ModalityPerformedProcedureStepNotificationSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False,
            evt_handlers=[(evt.EVT_N_EVENT_REPORT, handle)]
        )

        ae.add_requested_context(ModalityPerformedProcedureStepNotificationSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_event_report(
            ds, 1,
            ModalityPerformedProcedureStepNotificationSOPClass,
            '1.2.840.10008.5.1.1.40.1'
        )
        assert status.Status == 0x0116
        assert ds.PatientName == 'Test^test'
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_success(self):
        """Test receiving a success response from the peer"""
        def handle(event):
            return 0x0000, event.event_information

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(ModalityPerformedProcedureStepNotificationSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False,
            evt_handlers=[(evt.EVT_N_EVENT_REPORT, handle)]
        )

        ae.add_requested_context(ModalityPerformedProcedureStepNotificationSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_event_report(
            ds, 1,
            ModalityPerformedProcedureStepNotificationSOPClass,
            '1.2.840.10008.5.1.1.40.1'
        )
        assert status.Status == 0x0000
        assert ds.PatientName == 'Test^test'
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_unknown_status(self):
        """Test unknown status value returned by peer"""
        def handle(event):
            return 0xFFF0, event.event_information

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(ModalityPerformedProcedureStepNotificationSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False,
            evt_handlers=[(evt.EVT_N_EVENT_REPORT, handle)]
        )

        ae.add_requested_context(ModalityPerformedProcedureStepNotificationSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_event_report(
            ds, 1,
            ModalityPerformedProcedureStepNotificationSOPClass,
            '1.2.840.10008.5.1.1.40.1'
        )
        assert status.Status == 0xFFF0
        assert ds is None
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_bad_dataset(self):
        """Test handler returns bad dataset"""
        def handle(event):
            def test(): pass
            return 0x0000, test

        self.ae = ae = AE()
        ae.add_requested_context(ModalityPerformedProcedureStepNotificationSOPClass)
        ae.add_supported_context(ModalityPerformedProcedureStepNotificationSOPClass)

        handlers = [(evt.EVT_N_EVENT_REPORT, handle)]
        scp = ae.start_server(('', 11112), evt_handlers=handlers, block=False)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established

        # Event Information
        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_event_report(
            ds,
            1,
            ModalityPerformedProcedureStepNotificationSOPClass,
            '1.2.840.10008.5.1.1.40.1'
        )

        assert status.Status == 0x0110
        assert ds is None

        assoc.release()
        scp.shutdown()

    def test_decode_failure(self):
        """Test being unable to decode received dataset"""
        def handle(event):
            def test(): pass
            return 0x0000, test

        self.ae = ae = AE()
        ae.add_requested_context(
            ModalityPerformedProcedureStepNotificationSOPClass,
            ExplicitVRLittleEndian
        )
        ae.add_supported_context(ModalityPerformedProcedureStepNotificationSOPClass)

        handlers = [(evt.EVT_N_EVENT_REPORT, handle)]
        scp = ae.start_server(('', 11112), evt_handlers=handlers, block=False)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        class DummyReply():
            def getvalue(self):
                def test(): pass
                return test

        class DummyMessage():
            is_valid_response = True
            EventReply = DummyReply()
            Status = 0x0000
            STATUS_OPTIONAL_KEYWORDS = []

        class DummyDIMSE():
            msg_queue = queue.Queue()
            gotten = False

            def send_msg(*args, **kwargs):
                return

            def get_msg(self, *args, **kwargs):
                if not self.gotten:
                    self.gotten = True
                    return 1, DummyMessage()
                return None, None

        assoc._reactor_checkpoint.clear()
        while not assoc._is_paused:
            time.sleep(0.01)
        assoc.dimse = DummyDIMSE()
        assert assoc.is_established

        # Event Information
        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_event_report(
            ds,
            1,
            ModalityPerformedProcedureStepNotificationSOPClass,
            '1.2.840.10008.5.1.1.40.1'
        )

        assert status.Status == 0x0110
        assert ds is None

        assoc.release()
        scp.shutdown()

    def test_extra_status(self):
        """Test extra status elements are available."""
        def handle(event):
            status = Dataset()
            status.Status = 0xFFF0
            status.ErrorComment = 'Some comment'
            status.ErrorID = 12
            status.AffectedSOPClassUID = '1.2.3'
            status.AffectedSOPInstanceUID = '1.2.3.4'
            return status, event.event_information

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(ModalityPerformedProcedureStepNotificationSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False,
            evt_handlers=[(evt.EVT_N_EVENT_REPORT, handle)]
        )

        ae.add_requested_context(ModalityPerformedProcedureStepNotificationSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_event_report(
            ds, 1,
            ModalityPerformedProcedureStepNotificationSOPClass,
            '1.2.840.10008.5.1.1.40.1'
        )
        assert status.Status == 0xFFF0
        assert status.ErrorComment == 'Some comment'
        assert status.ErrorID == 12
        assert status.AffectedSOPClassUID == '1.2.3'
        assert status.AffectedSOPInstanceUID == '1.2.3.4'
        assert ds is None
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_meta_uid(self):
        """Test using a Meta SOP Class"""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(BasicGrayscalePrintManagementMetaSOPClass)
        ae.add_supported_context(PrinterSOPClass)
        scp = ae.start_server(('', 11112), block=False)

        ae.add_requested_context(BasicGrayscalePrintManagementMetaSOPClass)
        ae.add_requested_context(PrinterSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        assoc.dimse = DummyDIMSE()

        ds = Dataset()
        ds.PatientName = 'Test^test'
        # Receives None, None from DummyDIMSE, aborts
        status, ds = assoc.send_n_event_report(
            ds, 1,
            PrinterSOPClass,
            '1.2.840.10008.5.1.1.40.1',
            meta_uid=BasicGrayscalePrintManagementMetaSOPClass
        )
        assert assoc.is_aborted

        scp.shutdown()

        assert assoc.dimse.req.AffectedSOPClassUID == PrinterSOPClass
        assert assoc.dimse.context_id == 1
        assert assoc._accepted_cx[1].abstract_syntax == BasicGrayscalePrintManagementMetaSOPClass

    def test_meta_uid_good(self):
        """Test sending a request using a Meta SOP Class."""
        handler_data = []

        def handle(event):
            handler_data.append(event)
            return 0x0000, event.event_information

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(BasicGrayscalePrintManagementMetaSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False,
            evt_handlers=[(evt.EVT_N_EVENT_REPORT, handle)]
        )

        ae.add_requested_context(BasicGrayscalePrintManagementMetaSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_event_report(
            ds, 1,
            BasicFilmSessionSOPClass,
            '1.2.840.10008.5.1.1.40.1',
            meta_uid=BasicGrayscalePrintManagementMetaSOPClass
        )
        assert status.Status == 0x0000
        assert ds.PatientName == 'Test^test'
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

        req = handler_data[0].request
        cx = handler_data[0].context

        assert req.AffectedSOPClassUID == BasicFilmSessionSOPClass
        assert cx.abstract_syntax == BasicGrayscalePrintManagementMetaSOPClass

    def test_meta_uid_bad(self):
        """Test sending a request using a Meta SOP Class."""
        def handle(event):
            return 0x0000, event.event_information

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(BasicGrayscalePrintManagementMetaSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False,
            evt_handlers=[(evt.EVT_N_EVENT_REPORT, handle)]
        )

        ae.add_requested_context(BasicGrayscalePrintManagementMetaSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        ds = Dataset()
        ds.PatientName = 'Test^test'
        msg = (
            r"No presentation context for 'Basic Color Print Management "
            r"Meta SOP Class' has been "
            r"accepted by the peer "
            r"for the SCU role"
        )
        with pytest.raises(ValueError, match=msg):
            assoc.send_n_event_report(
                ds, 1,
                BasicFilmSessionSOPClass,
                '1.2.840.10008.5.1.1.40.1',
                meta_uid=BasicColorPrintManagementMetaSOPClass
            )

        assoc.release()
        assert assoc.is_released

        scp.shutdown()


class TestAssociationSendNGet(object):
    """Run tests on Assocation send_n_get."""
    def setup(self):
        """Run prior to each test"""
        self.ae = None

    def teardown(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

    def test_must_be_associated(self):
        """Test can't send without association."""
        def handle(event):
            ds = Dataset()
            ds.PatientName = 'Test^test'
            return 0x0000, ds

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(DisplaySystemSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_GET, handle)]
        )

        ae.add_requested_context(DisplaySystemSOPClass)
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established
        with pytest.raises(RuntimeError):
            assoc.send_n_get(None, None, None)

        scp.shutdown()

    def test_no_abstract_syntax_match(self):
        """Test SCU when no accepted abstract syntax"""
        def handle(event):
            ds = Dataset()
            ds.PatientName = 'Test^test'
            return 0x0000, ds

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(DisplaySystemSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_GET, handle)]
        )

        ae.add_requested_context(DisplaySystemSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        msg = (
            r"No presentation context for 'Verification SOP Class' has been "
            r"accepted by the peer "
            r"for the SCU role"
        )
        with pytest.raises(ValueError, match=msg):
            assoc.send_n_get(None, VerificationSOPClass, None)

        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_none(self):
        """Test no response from peer"""
        def handle(event):
            ds = Dataset()
            ds.PatientName = 'Test^test'
            time.sleep(0.5)
            return 0x0000, ds

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 0.4
        ae.network_timeout = 5
        ae.add_supported_context(DisplaySystemSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_GET, handle)]
        )

        ae.add_requested_context(DisplaySystemSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        status, ds = assoc.send_n_get(
            [(0x7fe0,0x0010)],
            DisplaySystemSOPClass,
            '1.2.840.10008.5.1.1.40.1'
        )

        assert status == Dataset()
        assert ds is None
        assert assoc.is_aborted

        scp.shutdown()

    def test_rsp_invalid(self):
        """Test invalid DIMSE message received from peer"""
        def handle(event):
            ds = Dataset()
            ds.PatientName = 'Test^test'
            return 0x0000, ds

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(DisplaySystemSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_GET, handle)]
        )

        ae.add_requested_context(DisplaySystemSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        class DummyResponse():
            is_valid_response = False

        class DummyDIMSE():
            msg_queue = queue.Queue()
            gotten = False
            def send_msg(*args, **kwargs): return
            def get_msg(self, *args, **kwargs):
                if not self.gotten:
                    self.gotten = True
                    return None, DummyResponse()
                return None, None

        assoc._reactor_checkpoint.clear()
        while not assoc._is_paused:
            time.sleep(0.01)
        assoc.dimse = DummyDIMSE()
        assert assoc.is_established
        status, ds = assoc.send_n_get([(0x7fe0,0x0010)],
        DisplaySystemSOPClass,
        '1.2.840.10008.5.1.1.40.1')
        assert status == Dataset()
        assert ds is None
        assert assoc.is_aborted

        scp.shutdown()

    def test_rsp_failure(self):
        """Test receiving a failure response from the peer"""
        def handle(event):
            return 0x0112, None

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(DisplaySystemSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_GET, handle)]
        )

        ae.add_requested_context(DisplaySystemSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        status, ds = assoc.send_n_get([(0x7fe0, 0x0010)],
                                      DisplaySystemSOPClass,
                                      '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0x0112
        assert ds is None
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_warning(self):
        """Test receiving a warning response from the peer"""
        def handle(event):
            ds = Dataset()
            ds.PatientName = 'Test'
            ds.SOPClassUID = DisplaySystemSOPClass
            ds.SOPInstanceUID = '1.2.3.4'
            return 0x0116, ds

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(DisplaySystemSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_GET, handle)]
        )

        ae.add_requested_context(DisplaySystemSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        status, ds = assoc.send_n_get([(0x7fe0,0x0010)],
                                      DisplaySystemSOPClass,
                                      '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0x0116
        assert ds is not None
        assert isinstance(ds, Dataset)
        assert ds.PatientName == 'Test'
        assert ds.SOPClassUID == DisplaySystemSOPClass
        assert ds.SOPInstanceUID == '1.2.3.4'
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_success(self):
        """Test receiving a success response from the peer"""
        def handle(event):
            ds = Dataset()
            ds.PatientName = 'Test'
            ds.SOPClassUID = DisplaySystemSOPClass
            ds.SOPInstanceUID = '1.2.3.4'
            return 0x0000, ds

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(DisplaySystemSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_GET, handle)]
        )

        ae.add_requested_context(DisplaySystemSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        status, ds = assoc.send_n_get([(0x7fe0,0x0010)],
                                      DisplaySystemSOPClass,
                                      '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0x0000
        assert ds is not None
        assert isinstance(ds, Dataset)
        assert ds.PatientName == 'Test'
        assert ds.SOPClassUID == DisplaySystemSOPClass
        assert ds.SOPInstanceUID == '1.2.3.4'
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_unknown_status(self):
        """Test unknown status value returned by peer"""
        def handle(event):
            ds = Dataset()
            ds.PatientName = 'Test'
            ds.SOPClassUID = DisplaySystemSOPClass
            ds.SOPInstanceUID = '1.2.3.4'
            return 0xFFF0, ds

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(DisplaySystemSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_GET, handle)]
        )

        ae.add_requested_context(DisplaySystemSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        status, ds = assoc.send_n_get([(0x7fe0,0x0010)],
                                      DisplaySystemSOPClass,
                                      '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0xFFF0
        assert ds is None
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_bad_dataset(self):
        """Test handler returns bad dataset"""
        def handle(event):
            def test(): pass
            return 0x0000, test

        self.ae = ae = AE()
        ae.add_requested_context(ModalityPerformedProcedureStepRetrieveSOPClass)
        ae.add_supported_context(ModalityPerformedProcedureStepRetrieveSOPClass)

        handlers = [(evt.EVT_N_GET, handle)]
        scp = ae.start_server(('', 11112), evt_handlers=handlers, block=False)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established

        # Event Information
        attrs = [0x00100010, 0x00100020]
        status, ds = assoc.send_n_get(
            attrs,
            ModalityPerformedProcedureStepRetrieveSOPClass,
            '1.2.840.10008.5.1.1.40.1'
        )

        assert status.Status == 0x0110
        assert ds is None

        assoc.release()
        scp.shutdown()

    def test_decode_failure(self):
        """Test bad dataset received from peer"""
        def handle(event):
            ds = Dataset()
            ds.PatientName = 'Test^test'
            return 0x0000, ds

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(DisplaySystemSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_GET, handle)]
        )

        ae.add_requested_context(DisplaySystemSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        class DummyReply():
            def getvalue(self):
                def test(): pass
                return test

        class DummyMessage():
            is_valid_response = True
            AttributeList = DummyReply()
            Status = 0x0000
            STATUS_OPTIONAL_KEYWORDS = []

        class DummyDIMSE():
            msg_queue = queue.Queue()
            gotten = False

            def send_msg(*args, **kwargs):
                return

            def get_msg(self, *args, **kwargs):
                if not self.gotten:
                    self.gotten = True
                    return 1, DummyMessage()
                return None, None

        assoc._reactor_checkpoint.clear()
        while not assoc._is_paused:
            time.sleep(0.01)
        assoc.dimse = DummyDIMSE()
        assert assoc.is_established
        status, ds = assoc.send_n_get(
            [(0x7fe0,0x0010)],
            DisplaySystemSOPClass,
            '1.2.840.10008.5.1.1.40.1'
        )

        assert status.Status == 0x0110
        assert ds is None

        scp.shutdown()

    def test_extra_status(self):
        """Test extra status elements are available."""
        def handle(event):
            ds = Dataset()
            ds.Status = 0xFFF0
            ds.ErrorComment = 'Some comment'
            ds.ErrorID = 12
            ds.AttributeIdentifierList = [0x00100020]
            return ds, None

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(DisplaySystemSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_GET, handle)]
        )

        ae.add_requested_context(DisplaySystemSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        status, ds = assoc.send_n_get([(0x7fe0,0x0010)],
                                      DisplaySystemSOPClass,
                                      '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0xFFF0
        assert status.ErrorComment == 'Some comment'
        assert status.ErrorID == 12
        assert status.AttributeIdentifierList == [0x00100020]
        assert ds is None
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_meta_uid(self):
        """Test using a Meta SOP Class"""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(BasicGrayscalePrintManagementMetaSOPClass)
        ae.add_supported_context(PrinterSOPClass)
        scp = ae.start_server(('', 11112), block=False)

        ae.add_requested_context(BasicGrayscalePrintManagementMetaSOPClass)
        ae.add_requested_context(PrinterSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        assoc.dimse = DummyDIMSE()

        ds = Dataset()
        ds.PatientName = 'Test^test'
        # Receives None, None from DummyDIMSE, aborts
        status, ds = assoc.send_n_get(
            [(0x00100010)],
            PrinterSOPClass,
            '1.2.840.10008.5.1.1.40.1',
            meta_uid=BasicGrayscalePrintManagementMetaSOPClass
        )
        assert assoc.is_aborted

        scp.shutdown()

        assert assoc.dimse.req.RequestedSOPClassUID == PrinterSOPClass
        assert assoc.dimse.context_id == 1
        assert assoc._accepted_cx[1].abstract_syntax == BasicGrayscalePrintManagementMetaSOPClass

    def test_meta_uid_good(self):
        """Test sending a request using a Meta SOP Class."""
        handler_data = []

        def handle(event):
            handler_data.append(event)
            ds = Dataset()
            ds.PatientName = 'Test'
            ds.SOPClassUID = DisplaySystemSOPClass
            ds.SOPInstanceUID = '1.2.3.4'
            return 0x0000, ds

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(BasicGrayscalePrintManagementMetaSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_GET, handle)]
        )

        ae.add_requested_context(BasicGrayscalePrintManagementMetaSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_get(
            [(0x7fe0,0x0010)],
            DisplaySystemSOPClass, '1.2.840.10008.5.1.1.40.1',
            meta_uid=BasicGrayscalePrintManagementMetaSOPClass
        )

        assert status.Status == 0x0000
        assert ds is not None
        assert isinstance(ds, Dataset)
        assert ds.PatientName == 'Test'
        assert ds.SOPClassUID == DisplaySystemSOPClass
        assert ds.SOPInstanceUID == '1.2.3.4'
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

        req = handler_data[0].request
        cx = handler_data[0].context

        assert req.RequestedSOPClassUID == DisplaySystemSOPClass
        assert cx.abstract_syntax == BasicGrayscalePrintManagementMetaSOPClass

    def test_meta_uid_bad(self):
        """Test sending a request using a Meta SOP Class."""
        def handle(event):
            ds = Dataset()
            ds.PatientName = 'Test'
            ds.SOPClassUID = DisplaySystemSOPClass
            ds.SOPInstanceUID = '1.2.3.4'
            return 0x0000, ds

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(BasicGrayscalePrintManagementMetaSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False,
            evt_handlers=[(evt.EVT_N_GET, handle)]
        )

        ae.add_requested_context(BasicGrayscalePrintManagementMetaSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        ds = Dataset()
        ds.PatientName = 'Test^test'
        msg = (
            r"No presentation context for 'Basic Color Print Management "
            r"Meta SOP Class' has been "
            r"accepted by the peer "
            r"for the SCU role"
        )
        with pytest.raises(ValueError, match=msg):
            assoc.send_n_get(
                [(0x7fe0,0x0010)],
                DisplaySystemSOPClass, '1.2.840.10008.5.1.1.40.1',
                meta_uid=BasicColorPrintManagementMetaSOPClass
            )

        assoc.release()
        assert assoc.is_released

        scp.shutdown()


class TestAssociationSendNSet(object):
    """Run tests on Assocation send_n_set."""
    def setup(self):
        self.ae = None

    def teardown(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

    def test_must_be_associated(self):
        """Test can't send without association."""
        def handle(event):
            ds = Dataset()
            ds.PatientName = 'Test^test'
            return 0x0000, ds

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_SET, handle)]
        )

        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established
        with pytest.raises(RuntimeError):
            assoc.send_n_set(None, None, None)

        scp.shutdown()

    def test_no_abstract_syntax_match(self):
        """Test SCU when no accepted abstract syntax"""
        def handle(event):
            ds = Dataset()
            ds.PatientName = 'Test^test'
            return 0x0000, ds

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_SET, handle)]
        )

        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        msg = (
            r"No presentation context for 'Verification SOP Class' has been "
            r"accepted by the peer "
            r"for the SCU role"
        )
        with pytest.raises(ValueError, match=msg):
            assoc.send_n_set(None, VerificationSOPClass, None)

        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rq_bad_dataset_raises(self):
        """Test sending bad dataset raises exception."""
        def handle(event):
            ds = Dataset()
            ds.PatientName = 'Test^test'
            return 0x0000, ds

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_SET, handle)]
        )

        ae.add_requested_context(
            ModalityPerformedProcedureStepSOPClass,
            ExplicitVRLittleEndian
        )
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        mod_list = Dataset()
        mod_list.PerimeterValue = b'\x00\x01'
        msg = r"Failed to encode the supplied 'Modification List' dataset"
        with pytest.raises(ValueError, match=msg):
            assoc.send_n_set(
                mod_list, ModalityPerformedProcedureStepSOPClass, '1.2.3'
            )

        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_none(self):
        """Test no response from peer"""
        def handle(event):
            ds = Dataset()
            ds.PatientName = 'Test^test'
            time.sleep(0.5)
            return 0x0000, ds

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 0.4
        ae.network_timeout = 5
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_SET, handle)]
        )

        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        mod_list = Dataset()
        mod_list.PatientName = 'Test^test'
        status, ds = assoc.send_n_set(
            mod_list, ModalityPerformedProcedureStepSOPClass,
            '1.2.840.10008.5.1.1.40.1'
        )

        assert status == Dataset()
        assert ds is None
        assert assoc.is_aborted

        scp.shutdown()

    def test_rsp_invalid(self):
        """Test invalid DIMSE message received from peer"""
        def handle(event):
            ds = Dataset()
            ds.PatientName = 'Test^test'
            return 0x0000, ds

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 0.4
        ae.network_timeout = 5
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_SET, handle)]
        )

        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        class DummyResponse():
            is_valid_response = False

        class DummyDIMSE():
            msg_queue = queue.Queue()
            gotten = False
            def send_msg(*args, **kwargs): return
            def get_msg(self, *args, **kwargs):
                if not self.gotten:
                    self.gotten = True
                    return None, DummyResponse()
                return None, None

        assoc._reactor_checkpoint.clear()
        while not assoc._is_paused:
            time.sleep(0.01)
        assoc.dimse = DummyDIMSE()
        mod_list = Dataset()
        mod_list.PatientName = 'Test^test'
        status, ds = assoc.send_n_set(
            mod_list,
            ModalityPerformedProcedureStepSOPClass,
            '1.2.840.10008.5.1.1.40.1'
        )

        assert status == Dataset()
        assert ds is None
        assert assoc.is_aborted

        scp.shutdown()

    def test_rsp_failure(self):
        """Test receiving a failure response from the peer"""
        def handle(event):
            return 0x0112, None

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_SET, handle)]
        )

        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_set(
            ds,
            ModalityPerformedProcedureStepSOPClass,
            '1.2.840.10008.5.1.1.40.1'
        )
        assert status.Status == 0x0112
        assert ds is None
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_warning(self):
        """Test receiving a warning response from the peer"""
        def handle(event):
            return 0x0116, event.modification_list

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_SET, handle)]
        )

        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_set(
            ds,
            ModalityPerformedProcedureStepSOPClass,
            '1.2.840.10008.5.1.1.40.1'
        )
        assert status.Status == 0x0116
        assert ds.PatientName == 'Test^test'
        assoc.release()
        assert assoc.is_released

    def test_rsp_success(self):
        """Test receiving a success response from the peer"""
        def handle(event):
            return 0x0000, event.modification_list

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_SET, handle)]
        )

        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_set(
            ds,
            ModalityPerformedProcedureStepSOPClass,
            '1.2.840.10008.5.1.1.40.1'
        )
        assert status.Status == 0x0000
        assert ds.PatientName == 'Test^test'
        assoc.release()
        assert assoc.is_released

    def test_rsp_unknown_status(self):
        """Test unknown status value returned by peer"""
        def handle(event):
            return 0xFFF0, event.modification_list

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_SET, handle)]
        )

        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_set(
            ds,
            ModalityPerformedProcedureStepSOPClass,
            '1.2.840.10008.5.1.1.40.1'
        )
        assert status.Status == 0xFFF0
        assert ds is None
        assoc.release()
        assert assoc.is_released

    def test_rsp_bad_dataset(self):
        """Test handler returns bad dataset"""
        def handle(event):
            def test(): pass
            return 0x0000, test

        self.ae = ae = AE()
        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)

        handlers = [(evt.EVT_N_SET, handle)]
        scp = ae.start_server(('', 11112), evt_handlers=handlers, block=False)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established

        # Event Information
        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_set(
            ds,
            ModalityPerformedProcedureStepSOPClass,
            '1.2.840.10008.5.1.1.40.1'
        )

        assert status.Status == 0x0110
        assert ds is None

        assoc.release()
        scp.shutdown()

    def test_decode_failure(self):
        """Test bad dataset received from peer"""
        def handle(event):
            ds = Dataset()
            ds.PatientName = 'Test^test'
            return 0x0000, ds

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 0.4
        ae.network_timeout = 5
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_SET, handle)]
        )

        ae.add_requested_context(
            ModalityPerformedProcedureStepSOPClass,
            ExplicitVRLittleEndian
        )
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        class DummyReply():
            def getvalue(self):
                def test(): pass
                return test

        class DummyMessage():
            is_valid_response = True
            AttributeList = DummyReply()
            Status = 0x0000
            STATUS_OPTIONAL_KEYWORDS = []

        class DummyDIMSE():
            msg_queue = queue.Queue()
            gotten = False

            def send_msg(*args, **kwargs):
                return

            def get_msg(self, *args, **kwargs):
                if not self.gotten:
                    self.gotten = True
                    return 1, DummyMessage()
                return None, None

        assoc._reactor_checkpoint.clear()
        while not assoc._is_paused:
            time.sleep(0.01)
        assoc.dimse = DummyDIMSE()
        assert assoc.is_established
        mod_list = Dataset()
        mod_list.PatientName = 'Test^test'
        status, ds = assoc.send_n_set(
            mod_list,
            ModalityPerformedProcedureStepSOPClass,
            '1.2.840.10008.5.1.1.40.1'
        )

        assert status.Status == 0x0110
        assert ds is None

        scp.shutdown()

    def test_extra_status(self):
        """Test extra status elements are available."""
        def handle(event):
            status = Dataset()
            status.Status = 0xFFF0
            status.ErrorComment = 'Some comment'
            status.ErrorID = 12
            status.AttributeIdentifierList = [0x00100010]
            return status, event.modification_list

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_SET, handle)]
        )

        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_set(
            ds,
            ModalityPerformedProcedureStepSOPClass,
            '1.2.840.10008.5.1.1.40.1'
        )
        assert status.Status == 0xFFF0
        assert status.ErrorComment == 'Some comment'
        assert status.ErrorID == 12
        assert status.AttributeIdentifierList == Tag(0x00100010)
        assert ds is None
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_meta_uid(self):
        """Test using a Meta SOP Class"""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(BasicGrayscalePrintManagementMetaSOPClass)
        ae.add_supported_context(PrinterSOPClass)
        scp = ae.start_server(('', 11112), block=False)

        ae.add_requested_context(BasicGrayscalePrintManagementMetaSOPClass)
        ae.add_requested_context(PrinterSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        assoc.dimse = DummyDIMSE()

        ds = Dataset()
        ds.PatientName = 'Test^test'
        # Receives None, None from DummyDIMSE, aborts
        status, ds = assoc.send_n_set(
            ds,
            PrinterSOPClass,
            '1.2.840.10008.5.1.1.40.1',
            meta_uid=BasicGrayscalePrintManagementMetaSOPClass
        )
        assert assoc.is_aborted

        scp.shutdown()

        assert assoc.dimse.req.RequestedSOPClassUID == PrinterSOPClass
        assert assoc.dimse.context_id == 1
        assert assoc._accepted_cx[1].abstract_syntax == BasicGrayscalePrintManagementMetaSOPClass

    def test_meta_uid_good(self):
        """Test sending a request using a Meta SOP Class."""
        handler_data = []

        def handle(event):
            handler_data.append(event)
            return 0x0000, event.modification_list

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(BasicGrayscalePrintManagementMetaSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_SET, handle)]
        )

        ae.add_requested_context(BasicGrayscalePrintManagementMetaSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_set(
            ds,
            ModalityPerformedProcedureStepSOPClass,
            '1.2.840.10008.5.1.1.40.1',
            meta_uid=BasicGrayscalePrintManagementMetaSOPClass
        )

        assert status.Status == 0x0000
        assert ds is not None
        assert isinstance(ds, Dataset)
        assert status.Status == 0x0000
        assert ds.PatientName == 'Test^test'
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

        req = handler_data[0].request
        cx = handler_data[0].context

        assert req.RequestedSOPClassUID == ModalityPerformedProcedureStepSOPClass
        assert cx.abstract_syntax == BasicGrayscalePrintManagementMetaSOPClass

    def test_meta_uid_bad(self):
        """Test sending a request using a Meta SOP Class."""
        def handle(event):
            ds = Dataset()
            ds.PatientName = 'Test'
            ds.SOPClassUID = DisplaySystemSOPClass
            ds.SOPInstanceUID = '1.2.3.4'
            return 0x0000, ds

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(BasicGrayscalePrintManagementMetaSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False,
            evt_handlers=[(evt.EVT_N_SET, handle)]
        )

        ae.add_requested_context(BasicGrayscalePrintManagementMetaSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        ds = Dataset()
        ds.PatientName = 'Test^test'
        msg = (
            r"No presentation context for 'Basic Color Print Management "
            r"Meta SOP Class' has been "
            r"accepted by the peer "
            r"for the SCU role"
        )
        with pytest.raises(ValueError, match=msg):
            assoc.send_n_set(
                ds,
                ModalityPerformedProcedureStepSOPClass,
                '1.2.840.10008.5.1.1.40.1',
                meta_uid=BasicColorPrintManagementMetaSOPClass
            )

        assoc.release()
        assert assoc.is_released

        scp.shutdown()


class TestAssociationSendNAction(object):
    """Run tests on Assocation send_n_action."""
    def setup(self):
        self.ae = None

    def teardown(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

    def test_must_be_associated(self):
        """Test can't send without association."""
        def handle(event):
            return 0x0000, event.action_information

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(ProceduralEventLoggingSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_ACTION, handle)]
        )

        ae.add_requested_context(ProceduralEventLoggingSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established
        with pytest.raises(RuntimeError):
            assoc.send_n_action(None, None, None, None)

        scp.shutdown()

    def test_no_abstract_syntax_match(self):
        """Test SCU when no accepted abstract syntax"""
        def handle(event):
            return 0x0000, event.action_information

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(ProceduralEventLoggingSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_ACTION, handle)]
        )

        ae.add_requested_context(ProceduralEventLoggingSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        msg = (
            r"No presentation context for 'Verification SOP Class' has been "
            r"accepted by the peer for the SCU role"
        )
        with pytest.raises(ValueError, match=msg):
            assoc.send_n_action(None, 1, VerificationSOPClass, None)
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rq_bad_dataset_raises(self):
        """Test sending bad dataset raises exception."""
        def handle(event):
            return 0x0000, event.action_information

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(ProceduralEventLoggingSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_ACTION, handle)]
        )

        ae.add_requested_context(
            ProceduralEventLoggingSOPClass,
            ExplicitVRLittleEndian
        )
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        ds = Dataset()
        ds.PerimeterValue = b'\x00\x01'
        msg = r"Failed to encode the supplied 'Action Information' dataset"
        with pytest.raises(ValueError, match=msg):
            assoc.send_n_action(ds, 1, ProceduralEventLoggingSOPClass, '1.2.3')
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_none(self):
        """Test no response from peer"""
        def handle(event):
            time.sleep(0.5)
            return 0x0000, event.action_information

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 0.4
        ae.network_timeout = 5
        ae.add_supported_context(ProceduralEventLoggingSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_ACTION, handle)]
        )

        ae.add_requested_context(ProceduralEventLoggingSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        class DummyDIMSE():
            msg_queue = queue.Queue()
            def send_msg(*args, **kwargs): return

            def get_msg(*args, **kwargs): return None, None

        assoc._reactor_checkpoint.clear()
        while not assoc._is_paused:
            time.sleep(0.01)
        assoc.dimse = DummyDIMSE()
        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_action(
            ds, 1, ProceduralEventLoggingSOPClass, '1.2.840.10008.5.1.1.40.1'
        )

        assert status == Dataset()
        assert ds is None
        assert assoc.is_aborted

        scp.shutdown()

    def test_rsp_invalid(self):
        """Test invalid DIMSE message received from peer"""
        def handle(event):
            return 0x0000, event.action_information

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(ProceduralEventLoggingSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_ACTION, handle)]
        )

        ae.add_requested_context(ProceduralEventLoggingSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        class DummyResponse():
            is_valid_response = False

        class DummyDIMSE():
            msg_queue = queue.Queue()
            gotten = False
            def send_msg(*args, **kwargs): return
            def get_msg(self, *args, **kwargs):
                if not self.gotten:
                    self.gotten = True
                    return None, DummyResponse()
                return None, None

        assoc._reactor_checkpoint.clear()
        while not assoc._is_paused:
            time.sleep(0.01)
        assoc.dimse = DummyDIMSE()
        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_action(
            ds, 1, ProceduralEventLoggingSOPClass, '1.2.840.10008.5.1.1.40.1'
        )
        assert status == Dataset()
        assert ds is None
        assert assoc.is_aborted

        scp.shutdown()

    def test_rsp_failure(self):
        """Test receiving a failure response from the peer"""
        def handle(event):
            return 0x0112, None

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(ProceduralEventLoggingSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_ACTION, handle)]
        )

        ae.add_requested_context(ProceduralEventLoggingSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_action(
            ds, 1, ProceduralEventLoggingSOPClass, '1.2.840.10008.5.1.1.40.1'
        )
        assert status.Status == 0x0112
        assert ds is None
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_warning(self):
        """Test receiving a warning response from the peer"""
        def handle(event):
            return 0x0116, event.action_information

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(ProceduralEventLoggingSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_ACTION, handle)]
        )

        ae.add_requested_context(ProceduralEventLoggingSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_action(
            ds, 1, ProceduralEventLoggingSOPClass, '1.2.840.10008.5.1.1.40.1'
        )
        assert status.Status == 0x0116
        assert ds.PatientName == 'Test^test'
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_success(self):
        """Test receiving a success response from the peer"""
        def handle(event):
            return 0x0000, event.action_information

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(ProceduralEventLoggingSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_ACTION, handle)]
        )

        ae.add_requested_context(ProceduralEventLoggingSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_action(
            ds, 1, ProceduralEventLoggingSOPClass, '1.2.840.10008.5.1.1.40.1'
        )
        assert status.Status == 0x0000
        assert ds.PatientName == 'Test^test'
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_unknown_status(self):
        """Test unknown status value returned by peer"""
        def handle(event):
            return 0xFFF0, event.action_information

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(ProceduralEventLoggingSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_ACTION, handle)]
        )

        ae.add_requested_context(ProceduralEventLoggingSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_action(
            ds, 1, ProceduralEventLoggingSOPClass, '1.2.840.10008.5.1.1.40.1'
        )
        assert status.Status == 0xFFF0
        assert ds is None
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_bad_dataset(self):
        """Test bad dataset received from peer"""
        def handle(event):
            return 0x0000, event.action_information

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(PrintJobSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_ACTION, handle)]
        )

        ae.add_requested_context(PrintJobSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        class DummyReply():
            def getvalue(self):
                def test(): pass
                return test

        class DummyMessage():
            is_valid_response = True
            ActionReply = DummyReply()
            Status = 0x0000
            STATUS_OPTIONAL_KEYWORDS = []

        class DummyDIMSE():
            msg_queue = queue.Queue()
            def send_msg(*args, **kwargs):
                return

            def get_msg(*args, **kwargs):
                rsp = DummyMessage()
                return 1, rsp

        assoc._reactor_checkpoint.clear()
        while not assoc._is_paused:
            time.sleep(0.01)
        assoc.dimse = DummyDIMSE()
        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_action(
            ds, 1, PrintJobSOPClass, '1.2.840.10008.5.1.1.40.1'
        )

        assert status.Status == 0x0110
        assert ds is None

        scp.shutdown()

    def test_extra_status(self):
        """Test extra status elements are available."""
        def handle(event):
            ds = Dataset()
            ds.Status = 0xFFF0
            ds.ErrorComment = 'Some comment'
            ds.ErrorID = 12
            return ds, event.action_information

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(PrintJobSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_ACTION, handle)]
        )

        ae.add_requested_context(PrintJobSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_action(
            ds, 1, PrintJobSOPClass, '1.2.840.10008.5.1.1.40.1'
        )
        assert status.Status == 0xFFF0
        assert status.ErrorComment == 'Some comment'
        assert status.ErrorID == 12
        assert ds is None
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_meta_uid(self):
        """Test using a Meta SOP Class"""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(BasicGrayscalePrintManagementMetaSOPClass)
        ae.add_supported_context(PrinterSOPClass)
        scp = ae.start_server(('', 11112), block=False)

        ae.add_requested_context(BasicGrayscalePrintManagementMetaSOPClass)
        ae.add_requested_context(PrinterSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        assoc.dimse = DummyDIMSE()

        ds = Dataset()
        ds.PatientName = 'Test^test'
        # Receives None, None from DummyDIMSE, aborts
        status, ds = assoc.send_n_action(
            ds, 1,
            PrinterSOPClass,
            '1.2.840.10008.5.1.1.40.1',
            meta_uid=BasicGrayscalePrintManagementMetaSOPClass
        )
        assert assoc.is_aborted

        scp.shutdown()

        assert assoc.dimse.req.RequestedSOPClassUID == PrinterSOPClass
        assert assoc.dimse.context_id == 1
        assert assoc._accepted_cx[1].abstract_syntax == BasicGrayscalePrintManagementMetaSOPClass

    def test_meta_uid_good(self):
        """Test sending a request using a Meta SOP Class."""
        handler_data = []

        def handle(event):
            handler_data.append(event)
            return 0x0000, event.action_information

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(BasicGrayscalePrintManagementMetaSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_ACTION, handle)]
        )

        ae.add_requested_context(BasicGrayscalePrintManagementMetaSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_action(
            ds, 1, ProceduralEventLoggingSOPClass, '1.2.840.10008.5.1.1.40.1',
            meta_uid=BasicGrayscalePrintManagementMetaSOPClass
        )
        assert status.Status == 0x0000
        assert ds.PatientName == 'Test^test'
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

        req = handler_data[0].request
        cx = handler_data[0].context

        assert req.RequestedSOPClassUID == ProceduralEventLoggingSOPClass
        assert cx.abstract_syntax == BasicGrayscalePrintManagementMetaSOPClass

    def test_meta_uid_bad(self):
        """Test sending a request using a Meta SOP Class."""
        def handle(event):
            ds = Dataset()
            ds.PatientName = 'Test'
            ds.SOPClassUID = DisplaySystemSOPClass
            ds.SOPInstanceUID = '1.2.3.4'
            return 0x0000, ds

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(BasicGrayscalePrintManagementMetaSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False,
            evt_handlers=[(evt.EVT_N_ACTION, handle)]
        )

        ae.add_requested_context(BasicGrayscalePrintManagementMetaSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        ds = Dataset()
        ds.PatientName = 'Test^test'
        msg = (
            r"No presentation context for 'Basic Color Print Management "
            r"Meta SOP Class' has been "
            r"accepted by the peer "
            r"for the SCU role"
        )
        with pytest.raises(ValueError, match=msg):
            assoc.send_n_action(
                ds, 1, ProceduralEventLoggingSOPClass,
                '1.2.840.10008.5.1.1.40.1',
                meta_uid=BasicColorPrintManagementMetaSOPClass
            )

        assoc.release()
        assert assoc.is_released

        scp.shutdown()


class TestAssociationSendNCreate(object):
    """Run tests on Assocation send_n_create."""
    def setup(self):
        self.ae = None

    def teardown(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

    def test_must_be_associated(self):
        """Test can't send without association."""
        def handle(event):
            return 0x0000, Dataset()

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)

        handlers = [(evt.EVT_N_CREATE, handle)]
        scp = ae.start_server(('', 11112), evt_handlers=handlers, block=False)

        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established
        with pytest.raises(RuntimeError):
            assoc.send_n_create(None, None, None)

        scp.shutdown()

    def test_no_abstract_syntax_match(self):
        """Test SCU when no accepted abstract syntax"""
        def handle(event):
            return 0x0000, Dataset()

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)

        handlers = [(evt.EVT_N_CREATE, handle)]
        scp = ae.start_server(('', 11112), evt_handlers=handlers, block=False)

        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        msg = (
            r"No presentation context for 'Verification SOP Class' has been "
            r"accepted by the peer for the SCU role"
        )
        with pytest.raises(ValueError, match=msg):
            assoc.send_n_create(None, VerificationSOPClass, None)
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rq_bad_dataset_raises(self):
        """Test sending bad dataset raises exception."""
        def handle(event):
            return 0x0000, Dataset()

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)

        handlers = [(evt.EVT_N_CREATE, handle)]
        scp = ae.start_server(('', 11112), evt_handlers=handlers, block=False)

        ae.add_requested_context(
            ModalityPerformedProcedureStepSOPClass,
            ExplicitVRLittleEndian
        )
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        ds = Dataset()
        ds.PerimeterValue = b'\x00\x01'
        msg = r"Failed to encode the supplied 'Attribute List' dataset"
        with pytest.raises(ValueError, match=msg):
            assoc.send_n_create(
                ds, ModalityPerformedProcedureStepSOPClass, '1.2.3'
            )
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_none(self):
        """Test no response from peer"""
        def handle(event):
            time.sleep(0.5)
            return 0x0000, Dataset()

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 0.4
        ae.network_timeout = 5
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)

        handlers = [(evt.EVT_N_CREATE, handle)]
        scp = ae.start_server(('', 11112), evt_handlers=handlers, block=False)

        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_create(
            ds, ModalityPerformedProcedureStepSOPClass,
            '1.2.840.10008.5.1.1.40.1'
        )

        assert status == Dataset()
        assert ds is None
        assert assoc.is_aborted

        scp.shutdown()

    def test_rsp_invalid(self):
        """Test invalid DIMSE message received from peer"""
        def handle(event):
            return 0x0000, Dataset()

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)

        handlers = [(evt.EVT_N_CREATE, handle)]
        scp = ae.start_server(('', 11112), evt_handlers=handlers, block=False)

        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        class DummyResponse():
            is_valid_response = False

        class DummyDIMSE():
            msg_queue = queue.Queue()
            gotten = False
            def send_msg(*args, **kwargs): return
            def get_msg(self, *args, **kwargs):
                if not self.gotten:
                    self.gotten = True
                    return None, DummyResponse()
                return None, None

        assoc._reactor_checkpoint.clear()
        while not assoc._is_paused:
            time.sleep(0.01)
        assoc.dimse = DummyDIMSE()
        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_create(
            ds, ModalityPerformedProcedureStepSOPClass,
            '1.2.840.10008.5.1.1.40.1'
        )
        assert status == Dataset()
        assert ds is None
        assert assoc.is_aborted

        scp.shutdown()

    def test_rsp_failure(self):
        """Test receiving a failure response from the peer"""
        def handle(event):
            return 0x0112, Dataset()

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)

        handlers = [(evt.EVT_N_CREATE, handle)]
        scp = ae.start_server(('', 11112), evt_handlers=handlers, block=False)

        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_create(
            ds, ModalityPerformedProcedureStepSOPClass,
            '1.2.840.10008.5.1.1.40.1'
        )
        assert status.Status == 0x0112
        assert ds is None
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_warning(self):
        """Test receiving a warning response from the peer"""
        def handle(event):
            return 0x0116, event.attribute_list

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)

        handlers = [(evt.EVT_N_CREATE, handle)]
        scp = ae.start_server(('', 11112), evt_handlers=handlers, block=False)

        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_create(
            ds, ModalityPerformedProcedureStepSOPClass,
            '1.2.840.10008.5.1.1.40.1'
        )
        assert status.Status == 0x0116
        assert ds.PatientName == 'Test^test'
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_success(self):
        """Test receiving a success response from the peer"""
        def handle(event):
            return 0x0000, event.attribute_list

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)

        handlers = [(evt.EVT_N_CREATE, handle)]
        scp = ae.start_server(('', 11112), evt_handlers=handlers, block=False)

        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_create(
            ds, ModalityPerformedProcedureStepSOPClass,
            '1.2.840.10008.5.1.1.40.1'
        )
        assert status.Status == 0x0000
        assert ds.PatientName == 'Test^test'
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_unknown_status(self):
        """Test unknown status value returned by peer"""
        def handle(event):
            return 0xFFF0, event.attribute_list

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)

        handlers = [(evt.EVT_N_CREATE, handle)]
        scp = ae.start_server(('', 11112), evt_handlers=handlers, block=False)

        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_create(
            ds, ModalityPerformedProcedureStepSOPClass,
            '1.2.840.10008.5.1.1.40.1'
        )
        assert status.Status == 0xFFF0
        assert ds is None
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_bad_dataset(self):
        """Test handler returns bad dataset"""
        def handle(event):
            def test(): pass
            return 0x0000, test

        self.ae = ae = AE()
        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)

        handlers = [(evt.EVT_N_CREATE, handle)]
        scp = ae.start_server(('', 11112), evt_handlers=handlers, block=False)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established

        # Event Information
        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_create(
            ds,
            ModalityPerformedProcedureStepSOPClass,
            '1.2.840.10008.5.1.1.40.1'
        )

        assert status.Status == 0x0110
        assert ds is None

        assoc.release()
        scp.shutdown()

    def test_decode_failure(self):
        """Test bad dataset received from peer"""
        def handle(event):
            return 0x0000, event.attribute_list

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)

        handlers = [(evt.EVT_N_CREATE, handle)]
        scp = ae.start_server(('', 11112), evt_handlers=handlers, block=False)

        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established


        class DummyReply():
            def getvalue(self):
                def test(): pass
                return test

        class DummyMessage():
            is_valid_response = True
            is_valid_request = False
            AttributeList = DummyReply()
            Status = 0x0000
            STATUS_OPTIONAL_KEYWORDS = []

        class DummyDIMSE():
            msg_queue = queue.Queue()
            gotten = False

            def send_msg(*args, **kwargs):
                return

            def get_msg(self, *args, **kwargs):
                if not self.gotten:
                    self.gotten = True
                    return 1, DummyMessage()
                return None, None

        assoc._reactor_checkpoint.clear()
        while not assoc._is_paused:
            time.sleep(0.01)
        assoc.dimse = DummyDIMSE()
        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_create(
            ds, ModalityPerformedProcedureStepSOPClass,
            '1.2.840.10008.5.1.1.40.1'
        )
        assert status.Status == 0x0110
        assert ds is None
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_extra_status(self):
        """Test extra status elements are available."""
        def handle(event):
            status = Dataset()
            status.Status = 0xFFF0
            status.ErrorComment = 'Some comment'
            status.ErrorID = 12
            return status, event.attribute_list

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)

        handlers = [(evt.EVT_N_CREATE, handle)]
        scp = ae.start_server(('', 11112), evt_handlers=handlers, block=False)

        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_create(
            ds, ModalityPerformedProcedureStepSOPClass,
            '1.2.840.10008.5.1.1.40.1'
        )
        assert status.Status == 0xFFF0
        assert status.ErrorComment == 'Some comment'
        assert status.ErrorID == 12
        assert ds is None
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_meta_uid(self):
        """Test using a Meta SOP Class"""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(BasicGrayscalePrintManagementMetaSOPClass)
        ae.add_supported_context(PrinterSOPClass)
        scp = ae.start_server(('', 11112), block=False)

        ae.add_requested_context(BasicGrayscalePrintManagementMetaSOPClass)
        ae.add_requested_context(PrinterSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        assoc.dimse = DummyDIMSE()

        ds = Dataset()
        ds.PatientName = 'Test^test'
        # Receives None, None from DummyDIMSE, aborts
        status, ds = assoc.send_n_create(
            ds,
            PrinterSOPClass,
            '1.2.840.10008.5.1.1.40.1',
            meta_uid=BasicGrayscalePrintManagementMetaSOPClass
        )
        assert assoc.is_aborted

        scp.shutdown()

        assert assoc.dimse.req.AffectedSOPClassUID == PrinterSOPClass
        assert assoc.dimse.context_id == 1
        assert assoc._accepted_cx[1].abstract_syntax == BasicGrayscalePrintManagementMetaSOPClass

    def test_meta_uid_good(self):
        """Test sending a request using a Meta SOP Class."""
        handler_data = []

        def handle(event):
            handler_data.append(event)
            return 0x0000, event.attribute_list

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(BasicGrayscalePrintManagementMetaSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_CREATE, handle)]
        )

        ae.add_requested_context(BasicGrayscalePrintManagementMetaSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_create(
            ds, ModalityPerformedProcedureStepSOPClass,
            '1.2.840.10008.5.1.1.40.1',
            meta_uid=BasicGrayscalePrintManagementMetaSOPClass
        )
        assert status.Status == 0x0000
        assert ds.PatientName == 'Test^test'
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

        req = handler_data[0].request
        cx = handler_data[0].context

        assert req.AffectedSOPClassUID == ModalityPerformedProcedureStepSOPClass
        assert cx.abstract_syntax == BasicGrayscalePrintManagementMetaSOPClass

    def test_meta_uid_bad(self):
        """Test sending a request using a Meta SOP Class."""
        def handle(event):
            ds = Dataset()
            ds.PatientName = 'Test'
            ds.SOPClassUID = DisplaySystemSOPClass
            ds.SOPInstanceUID = '1.2.3.4'
            return 0x0000, ds

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(BasicGrayscalePrintManagementMetaSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False,
            evt_handlers=[(evt.EVT_N_CREATE, handle)]
        )

        ae.add_requested_context(BasicGrayscalePrintManagementMetaSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        ds = Dataset()
        ds.PatientName = 'Test^test'
        msg = (
            r"No presentation context for 'Basic Color Print Management "
            r"Meta SOP Class' has been "
            r"accepted by the peer "
            r"for the SCU role"
        )
        with pytest.raises(ValueError, match=msg):
            assoc.send_n_create(
                ds, ModalityPerformedProcedureStepSOPClass,
                '1.2.840.10008.5.1.1.40.1',
                meta_uid=BasicColorPrintManagementMetaSOPClass
            )

        assoc.release()
        assert assoc.is_released

        scp.shutdown()


class TestAssociationSendNDelete(object):
    """Run tests on Assocation send_n_delete."""
    def setup(self):
        self.ae = None

    def teardown(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

    def test_must_be_associated(self):
        """Test can't send without association."""
        def handle(event):
            return 0x0000

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(BasicFilmSessionSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_DELETE, handle)]
        )

        ae.add_requested_context(BasicFilmSessionSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established
        with pytest.raises(RuntimeError):
            assoc.send_n_delete(None, None)

        scp.shutdown()

    def test_no_abstract_syntax_match(self):
        """Test SCU when no accepted abstract syntax"""
        def handle(event):
            return 0x0000

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(BasicFilmSessionSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_DELETE, handle)]
        )

        ae.add_requested_context(BasicFilmSessionSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        msg = (
            r"No presentation context for 'Verification SOP Class' has been "
            r"accepted by the peer for the SCU role"
        )
        with pytest.raises(ValueError, match=msg):
            assoc.send_n_delete(VerificationSOPClass, None)
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_none(self):
        """Test no response from peer"""
        def handle(event):
            time.sleep(0.5)
            return 0x0000

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 0.4
        ae.network_timeout = 5
        ae.add_supported_context(BasicFilmSessionSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_DELETE, handle)]
        )

        ae.add_requested_context(BasicFilmSessionSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        status = assoc.send_n_delete(BasicFilmSessionSOPClass,
                                     '1.2.840.10008.5.1.1.40.1')
        assert status == Dataset()
        assert assoc.is_aborted

        scp.shutdown()

    def test_rsp_invalid(self):
        """Test invalid DIMSE message received from peer"""
        def handle(event):
            return 0x0000

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(BasicFilmSessionSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_DELETE, handle)]
        )

        ae.add_requested_context(BasicFilmSessionSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        class DummyResponse():
            is_valid_response = False

        class DummyDIMSE():
            msg_queue = queue.Queue()
            gotten = False
            def send_msg(*args, **kwargs): return
            def get_msg(self, *args, **kwargs):
                if not self.gotten:
                    self.gotten = True
                    return None, DummyResponse()
                return None, None

        assoc._reactor_checkpoint.clear()
        while not assoc._is_paused:
            time.sleep(0.01)
        assoc.dimse = DummyDIMSE()
        status = assoc.send_n_delete(BasicFilmSessionSOPClass,
                                     '1.2.840.10008.5.1.1.40.1')
        assert status == Dataset()
        assert assoc.is_aborted

        scp.shutdown()

    def test_rsp_failure(self):
        """Test receiving a failure response from the peer"""
        def handle(event):
            return 0x0112

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(BasicFilmSessionSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_DELETE, handle)]
        )

        ae.add_requested_context(BasicFilmSessionSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        status = assoc.send_n_delete(BasicFilmSessionSOPClass,
                                     '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0x0112
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_success(self):
        """Test receiving a success response from the peer"""
        def handle(event):
            return 0x0000

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(BasicFilmSessionSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_DELETE, handle)]
        )

        ae.add_requested_context(BasicFilmSessionSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        status = assoc.send_n_delete(BasicFilmSessionSOPClass,
                                     '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_unknown_status(self):
        """Test unknown status value returned by peer"""
        def handle(event):
            return 0xFFF0

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(BasicFilmSessionSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_DELETE, handle)]
        )

        ae.add_requested_context(BasicFilmSessionSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        status = assoc.send_n_delete(BasicFilmSessionSOPClass,
                                     '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0xFFF0
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_extra_status(self):
        """Test extra status elements are available."""
        def handle(event):
            ds = Dataset()
            ds.Status = 0xFFF0
            ds.ErrorComment = 'Some comment'
            ds.ErrorID = 12
            return ds

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(BasicFilmSessionSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_DELETE, handle)]
        )

        ae.add_requested_context(BasicFilmSessionSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        status = assoc.send_n_delete(BasicFilmSessionSOPClass,
                                     '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0xFFF0
        assert status.ErrorComment == 'Some comment'
        assert status.ErrorID == 12
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_meta_uid(self):
        """Test using a Meta SOP Class"""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(BasicGrayscalePrintManagementMetaSOPClass)
        ae.add_supported_context(PrinterSOPClass)
        scp = ae.start_server(('', 11112), block=False)

        ae.add_requested_context(BasicGrayscalePrintManagementMetaSOPClass)
        ae.add_requested_context(PrinterSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        assoc.dimse = DummyDIMSE()

        ds = Dataset()
        ds.PatientName = 'Test^test'
        # Receives None, None from DummyDIMSE, aborts
        status = assoc.send_n_delete(
            PrinterSOPClass,
            '1.2.840.10008.5.1.1.40.1',
            meta_uid=BasicGrayscalePrintManagementMetaSOPClass
        )
        assert assoc.is_aborted

        scp.shutdown()

        assert assoc.dimse.req.RequestedSOPClassUID == PrinterSOPClass
        assert assoc.dimse.context_id == 1
        assert assoc._accepted_cx[1].abstract_syntax == BasicGrayscalePrintManagementMetaSOPClass

    def test_meta_uid_good(self):
        """Test sending a request using a Meta SOP Class."""
        handler_data = []

        def handle(event):
            handler_data.append(event)
            return 0x0000

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(BasicGrayscalePrintManagementMetaSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_DELETE, handle)]
        )

        ae.add_requested_context(BasicGrayscalePrintManagementMetaSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        status = assoc.send_n_delete(
            BasicFilmSessionSOPClass, '1.2.840.10008.5.1.1.40.1',
            meta_uid=BasicGrayscalePrintManagementMetaSOPClass
        )
        assert status.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

        req = handler_data[0].request
        cx = handler_data[0].context

        assert req.RequestedSOPClassUID == BasicFilmSessionSOPClass
        assert cx.abstract_syntax == BasicGrayscalePrintManagementMetaSOPClass

    def test_meta_uid_bad(self):
        """Test sending a request using a Meta SOP Class."""
        def handle(event):
            ds = Dataset()
            ds.PatientName = 'Test'
            ds.SOPClassUID = DisplaySystemSOPClass
            ds.SOPInstanceUID = '1.2.3.4'
            return 0x0000, ds

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(BasicGrayscalePrintManagementMetaSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False,
            evt_handlers=[(evt.EVT_N_DELETE, handle)]
        )

        ae.add_requested_context(BasicGrayscalePrintManagementMetaSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        ds = Dataset()
        ds.PatientName = 'Test^test'
        msg = (
            r"No presentation context for 'Basic Color Print Management "
            r"Meta SOP Class' has been "
            r"accepted by the peer "
            r"for the SCU role"
        )
        with pytest.raises(ValueError, match=msg):
            assoc.send_n_delete(
                BasicFilmSessionSOPClass, '1.2.840.10008.5.1.1.40.1',
                meta_uid=BasicColorPrintManagementMetaSOPClass
            )

        assoc.release()
        assert assoc.is_released

        scp.shutdown()
