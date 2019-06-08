"""Association testing for DIMSE-N services"""

from io import BytesIO
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
    BasicGrayscalePrintManagementMetaSOPClass,
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
            r"No suitable presentation context for the SCU role has been "
            r"accepted by the peer for the SOP Class 'Verification SOP Class'"
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
            def send_msg(*args, **kwargs): return
            def get_msg(*args, **kwargs): return None, DummyResponse()

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
            def send_msg(*args, **kwargs):
                return

            def get_msg(*args, **kwargs):
                rsp = DummyMessage()
                return 1, rsp

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
            r"No suitable presentation context for the SCU role has been "
            r"accepted by the peer for the SOP Class 'Verification SOP Class'"
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
            def send_msg(*args, **kwargs): return
            def get_msg(*args, **kwargs): return None, DummyResponse()

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
            def send_msg(*args, **kwargs):
                return

            def get_msg(*args, **kwargs):
                rsp = DummyMessage()
                return 1, rsp

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
            r"No suitable presentation context for the SCU role has been "
            r"accepted by the peer for the SOP Class 'Verification SOP Class'"
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
            def send_msg(*args, **kwargs): return
            def get_msg(*args, **kwargs): return None, DummyResponse()

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
            def send_msg(*args, **kwargs):
                return

            def get_msg(*args, **kwargs):
                rsp = DummyMessage()
                return 1, rsp

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


class TestAssociationSendNAction(object):
    """Run tests on Assocation send_n_action."""
    def _scp(self, req, context):
        rsp = N_ACTION()
        rsp.MessageIDBeingRespondedTo = req.MessageID
        rsp.AffectedSOPClassUID = req.RequestedSOPClassUID
        rsp.AffectedSOPInstanceUID = req.RequestedSOPInstanceUID
        rsp.ActionTypeID = req.ActionTypeID

        acceptors = [
            aa for aa in self.ae.active_associations if 'Acceptor' in aa.name
        ]

        status, ds = evt.trigger(
            acceptors[0],
            evt.EVT_N_ACTION,
            {'request' : req, 'context' : context.as_tuple}
        )

        if isinstance(status, Dataset):
            if 'Status' not in status:
                raise AttributeError("The 'status' dataset returned by "
                                     "'on_n_set' must contain"
                                     "a (0000,0900) Status element")
            for elem in status:
                if hasattr(rsp, elem.keyword):
                    setattr(rsp, elem.keyword, elem.value)
                else:
                    LOGGER.warning("The 'status' dataset returned by "
                                   "'on_n_set' contained an unsupported "
                                   "Element '%s'.", elem.keyword)
        elif isinstance(status, int):
            rsp.Status = status

        if ds:
            rsp.ActionReply = BytesIO(encode(ds, True, True))

        acceptors[0].dimse.send_msg(rsp, context.context_id)

    def setup(self):
        self._orig_scp = ServiceClass.SCP

        self.ae = None

    def teardown(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

        ServiceClass.SCP = self._orig_scp

    def test_must_be_associated(self):
        """Test can't send without association."""
        def handle(event):
            return 0x0000, event.action_information

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(VerificationSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_ACTION, handle)]
        )

        ae.add_requested_context(VerificationSOPClass)
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
        ae.add_supported_context(DisplaySystemSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_ACTION, handle)]
        )

        ae.add_requested_context(DisplaySystemSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        msg = (
            r"No suitable presentation context for the SCU role has been "
            r"accepted by the peer for the SOP Class 'Verification SOP Class'"
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
        ae.add_supported_context(DisplaySystemSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_ACTION, handle)]
        )

        ae.add_requested_context(
            DisplaySystemSOPClass,
            ExplicitVRLittleEndian
        )
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        ds = Dataset()
        ds.PerimeterValue = b'\x00\x01'
        msg = r"Failed to encode the supplied 'Action Information' dataset"
        with pytest.raises(ValueError, match=msg):
            assoc.send_n_action(ds, 1, DisplaySystemSOPClass, '1.2.3')
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_none(self):
        """Test no response from peer"""
        def handle(event):
            time.sleep(0.5)
            return 0x0000, event.action_information

        ServiceClass.SCP = self._scp

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 0.4
        ae.network_timeout = 5
        ae.add_supported_context(PrintJobSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_ACTION, handle)]
        )

        ae.add_requested_context(PrintJobSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        class DummyDIMSE():
            def send_msg(*args, **kwargs): return

            def get_msg(*args, **kwargs): return None, None

        assoc.dimse = DummyDIMSE()
        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_action(
            ds, 1, PrintJobSOPClass, '1.2.840.10008.5.1.1.40.1'
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
        ae.add_supported_context(PrintJobSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_ACTION, handle)]
        )

        ae.add_requested_context(PrintJobSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        class DummyResponse():
            is_valid_response = False

        class DummyDIMSE():
            def send_msg(*args, **kwargs): return
            def get_msg(*args, **kwargs): return None, DummyResponse()

        assoc.dimse = DummyDIMSE()
        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_action(
            ds, 1, PrintJobSOPClass, '1.2.840.10008.5.1.1.40.1'
        )
        assert status == Dataset()
        assert ds is None
        assert assoc.is_aborted

        scp.shutdown()

    def test_rsp_failure(self):
        """Test receiving a failure response from the peer"""
        def handle(event):
            return 0x0112, None

        ServiceClass.SCP = self._scp

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
        assert status.Status == 0x0112
        assert ds is None
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_warning(self):
        """Test receiving a warning response from the peer"""
        def handle(event):
            return 0x0116, event.action_information

        ServiceClass.SCP = self._scp

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
        assert status.Status == 0x0116
        assert ds.PatientName == 'Test^test'
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_success(self):
        """Test receiving a success response from the peer"""
        def handle(event):
            return 0x0000, event.action_information

        ServiceClass.SCP = self._scp

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
        assert status.Status == 0x0000
        assert ds.PatientName == 'Test^test'
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_unknown_status(self):
        """Test unknown status value returned by peer"""
        def handle(event):
            return 0xFFF0, event.action_information

        ServiceClass.SCP = self._scp

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
        assert ds is None
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_bad_dataset(self):
        """Test bad dataset received from peer"""
        def handle(event):
            return 0x0000, event.action_information

        ServiceClass.SCP = self._scp

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
            def send_msg(*args, **kwargs):
                return

            def get_msg(*args, **kwargs):
                rsp = DummyMessage()
                return 1, rsp

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

        ServiceClass.SCP = self._scp

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
            r"No suitable presentation context for the SCU role has been "
            r"accepted by the peer for the SOP Class 'Verification SOP Class'"
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
            def send_msg(*args, **kwargs): return
            def get_msg(*args, **kwargs): return None, DummyResponse()

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
            AttributeList = DummyReply()
            Status = 0x0000
            STATUS_OPTIONAL_KEYWORDS = []

        class DummyDIMSE():
            def send_msg(*args, **kwargs):
                return

            def get_msg(*args, **kwargs):
                rsp = DummyMessage()
                return 1, rsp

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


class TestAssociationSendNDelete(object):
    """Run tests on Assocation send_n_delete."""
    def _scp(self, req, context):
        rsp = N_DELETE()
        rsp.MessageIDBeingRespondedTo = req.MessageID

        acceptors = [
            aa for aa in self.ae.active_associations if 'Acceptor' in aa.name
        ]

        status = evt.trigger(
            acceptors[0],
            evt.EVT_N_DELETE,
            {'request' : req, 'context' : context.as_tuple}
        )
        if isinstance(status, Dataset):
            if 'Status' not in status:
                raise AttributeError("The 'status' dataset returned by "
                                     "the handler must contain"
                                     "a (0000,0900) Status element")
            for elem in status:
                if hasattr(rsp, elem.keyword):
                    setattr(rsp, elem.keyword, elem.value)
                else:
                    LOGGER.warning("The 'status' dataset returned by "
                                   "the handler contained an unsupported "
                                   "Element '%s'.", elem.keyword)
        elif isinstance(status, int):
            rsp.Status = status

        acceptors[0].dimse.send_msg(rsp, context.context_id)

    def setup(self):
        self.ae = None
        self._orig_scp = ServiceClass.SCP

    def teardown(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

        ServiceClass.SCP = self._orig_scp

    def test_must_be_associated(self):
        """Test can't send without association."""
        def handle(event):
            return 0x0000

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(PrintJobSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_DELETE, handle)]
        )

        ae.add_requested_context(PrintJobSOPClass)
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
        ae.add_supported_context(PrintJobSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_DELETE, handle)]
        )

        ae.add_requested_context(PrintJobSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        msg = (
            r"No suitable presentation context for the SCU role has been "
            r"accepted by the peer for the SOP Class 'Verification SOP Class'"
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

        ServiceClass.SCP = self._scp

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 0.4
        ae.network_timeout = 5
        ae.add_supported_context(PrintJobSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_DELETE, handle)]
        )

        ae.add_requested_context(PrintJobSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        status = assoc.send_n_delete(PrintJobSOPClass,
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
        ae.add_supported_context(PrintJobSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_DELETE, handle)]
        )

        ae.add_requested_context(PrintJobSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        class DummyResponse():
            is_valid_response = False

        class DummyDIMSE():
            def send_msg(*args, **kwargs): return
            def get_msg(*args, **kwargs): return None, DummyResponse()

        assoc.dimse = DummyDIMSE()
        status = assoc.send_n_delete(PrintJobSOPClass,
                                     '1.2.840.10008.5.1.1.40.1')
        assert status == Dataset()
        assert assoc.is_aborted

        scp.shutdown()

    def test_rsp_failure(self):
        """Test receiving a failure response from the peer"""
        def handle(event):
            return 0x0112

        ServiceClass.SCP = self._scp

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(PrintJobSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_DELETE, handle)]
        )

        ae.add_requested_context(PrintJobSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        status = assoc.send_n_delete(PrintJobSOPClass,
                                     '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0x0112
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_success(self):
        """Test receiving a success response from the peer"""
        def handle(event):
            return 0x0000

        ServiceClass.SCP = self._scp

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(PrintJobSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_DELETE, handle)]
        )

        ae.add_requested_context(PrintJobSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        status = assoc.send_n_delete(PrintJobSOPClass,
                                     '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_unknown_status(self):
        """Test unknown status value returned by peer"""
        def handle(event):
            return 0xFFF0

        ServiceClass.SCP = self._scp

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(PrintJobSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_DELETE, handle)]
        )

        ae.add_requested_context(PrintJobSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        status = assoc.send_n_delete(PrintJobSOPClass,
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

        ServiceClass.SCP = self._scp

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(PrintJobSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_N_DELETE, handle)]
        )

        ae.add_requested_context(PrintJobSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        status = assoc.send_n_delete(PrintJobSOPClass,
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
