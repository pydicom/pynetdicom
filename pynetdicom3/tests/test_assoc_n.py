"""Association testing for DIMSE-N services"""

from io import BytesIO
import logging
import os
import select
import socket
from struct import pack
import time
import threading

import pytest

from pydicom import read_file
from pydicom.dataset import Dataset
from pydicom.uid import UID, ImplicitVRLittleEndian, ExplicitVRLittleEndian

from pynetdicom3 import AE, VerificationPresentationContexts
from pynetdicom3.association import Association
from pynetdicom3.dimse_primitives import (
    N_EVENT_REPORT, N_GET, N_SET, N_ACTION, N_CREATE, N_DELETE
)
from pynetdicom3.dsutils import encode, decode
from pynetdicom3.pdu_primitives import (
    UserIdentityNegotiation, SOPClassExtendedNegotiation,
    SOPClassCommonExtendedNegotiation
)
from pynetdicom3.sop_class import (
    DisplaySystemSOPClass,
    VerificationSOPClass,
    PrintJobSOPClass,
)
from pynetdicom3.service_class import ServiceClass
from .dummy_c_scp import DummyBaseSCP, DummyVerificationSCP
from .dummy_n_scp import (
    DummyGetSCP, DummySetSCP, DummyDeleteSCP, DummyEventReportSCP,
    DummyCreateSCP, DummyActionSCP
)

LOGGER = logging.getLogger('pynetdicom3')
LOGGER.setLevel(logging.CRITICAL)
#LOGGER.setLevel(logging.DEBUG)


class TestAssociationSendNEventReport(object):
    """Run tests on Assocation send_n_event_report."""
    def _scp(self, req, context, info):
        rsp = N_EVENT_REPORT()
        rsp.MessageIDBeingRespondedTo = req.MessageID
        rsp.AffectedSOPClassUID = req.AffectedSOPClassUID
        rsp.AffectedSOPInstanceUID = req.AffectedSOPInstanceUID

        status, ds = self.scp.ae.on_n_event_report(req.EventInformation,
                                                   context.as_tuple,
                                                   info)
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

        rsp.EventReply = BytesIO(encode(ds, True, True))

        self.scp.ae.active_associations[0].dimse.send_msg(rsp, context.context_id)

    def setup(self):
        self.scp = None
        self._orig_scp = ServiceClass.SCP

    def teardown(self):
        """Clear any active threads"""
        if self.scp:
            self.scp.abort()

        time.sleep(0.1)

        for thread in threading.enumerate():
            if isinstance(thread, DummyBaseSCP):
                thread.abort()
                thread.stop()

        ServiceClass.SCP = self._orig_scp

    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyEventReportSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established
        with pytest.raises(RuntimeError):
            assoc.send_n_event_report(None, None, None, None)
        self.scp.stop()

    def test_no_abstract_syntax_match(self):
        """Test SCU when no accepted abstract syntax"""
        self.scp = DummyEventReportSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        msg = (
            r"No accepted Presentation Context for the SOP Class "
            r"UID '1.2.840.10008.1.1'"
        )
        with pytest.raises(ValueError, match=msg):
            assoc.send_n_event_report(
                None, None, VerificationSOPClass.uid, None
            )
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rq_bad_dataset_raises(self):
        """Test sending bad dataset raises exception."""
        self.scp = DummyEventReportSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass, ExplicitVRLittleEndian)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        ds = Dataset()
        ds.PerimeterValue = b'\x00\x01'
        msg = r"Failed to encode the supplied dataset"
        with pytest.raises(ValueError, match=msg):
            assoc.send_n_event_report(ds, 1, PrintJobSOPClass.uid, '1.2.3')
        assoc.release()
        assert assoc.is_released

        self.scp.stop()

    def test_rsp_none(self):
        """Test no response from peer"""
        self.scp = DummyEventReportSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        class DummyDIMSE():
            def send_msg(*args, **kwargs): return

            def receive_msg(*args, **kwargs): return None, None

        assoc.dimse = DummyDIMSE()
        assert assoc.is_established
        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_event_report(
            ds, 1, PrintJobSOPClass.uid, '1.2.840.10008.5.1.1.40.1'
        )

        assert status == Dataset()
        assert ds is None
        assert assoc.is_aborted

        self.scp.stop()

    def test_rsp_invalid(self):
        """Test invalid DIMSE message received from peer"""
        self.scp = DummyEventReportSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        class DummyResponse():
            is_valid_response = False

        class DummyDIMSE():
            def send_msg(*args, **kwargs): return
            def receive_msg(*args, **kwargs): return DummyResponse(), None

        assoc.dimse = DummyDIMSE()
        assert assoc.is_established
        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_event_report(
            ds, 1, PrintJobSOPClass.uid, '1.2.840.10008.5.1.1.40.1'
        )
        assert status == Dataset()
        assert ds is None
        assert assoc.is_aborted

        self.scp.stop()

    def test_rsp_failure(self):
        """Test receiving a failure response from the peer"""
        self.scp = DummyEventReportSCP()
        self.scp.status = 0x0112
        ServiceClass.SCP = self._scp
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_event_report(
            ds, 1, PrintJobSOPClass.uid, '1.2.840.10008.5.1.1.40.1'
        )
        assert status.Status == 0x0112
        assert ds is None
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rsp_warning(self):
        """Test receiving a warning response from the peer"""
        self.scp = DummyEventReportSCP()
        self.scp.status = 0x0116
        ServiceClass.SCP = self._scp
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_event_report(
            ds, 1, PrintJobSOPClass.uid, '1.2.840.10008.5.1.1.40.1'
        )
        assert status.Status == 0x0116
        assert ds is not None
        assert isinstance(ds, Dataset)
        assert ds.PatientName == 'Test'
        assert ds.SOPClassUID == PrintJobSOPClass.UID
        assert ds.SOPInstanceUID == '1.2.3.4'
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rsp_success(self):
        """Test receiving a success response from the peer"""
        self.scp = DummyEventReportSCP()
        ServiceClass.SCP = self._scp
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_event_report(
            ds, 1, PrintJobSOPClass.uid, '1.2.840.10008.5.1.1.40.1'
        )
        assert status.Status == 0x0000
        assert ds is not None
        assert isinstance(ds, Dataset)
        assert ds.PatientName == 'Test'
        assert ds.SOPClassUID == PrintJobSOPClass.UID
        assert ds.SOPInstanceUID == '1.2.3.4'
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rsp_unknown_status(self):
        """Test unknown status value returned by peer"""
        self.scp = DummyEventReportSCP()
        self.scp.status = 0xFFF0
        ServiceClass.SCP = self._scp
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_event_report(
            ds, 1, PrintJobSOPClass.uid, '1.2.840.10008.5.1.1.40.1'
        )
        assert status.Status == 0xFFF0
        assert ds is None
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rsp_bad_dataset(self):
        """Test bad dataset received from peer"""
        self.scp = DummyEventReportSCP()
        ServiceClass.SCP = self._scp
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        class DummyMessage():
            is_valid_response = True
            EventReply = None
            Status = 0x0000
            STATUS_OPTIONAL_KEYWORDS = []

        class DummyDIMSE():
            def send_msg(*args, **kwargs):
                return

            def receive_msg(*args, **kwargs):
                status = Dataset()
                status.Status = 0x0000

                rsp = DummyMessage()

                return rsp, None

        assoc.dimse = DummyDIMSE()
        assert assoc.is_established
        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_event_report(
            ds, 1, PrintJobSOPClass.uid, '1.2.840.10008.5.1.1.40.1'
        )

        assert status.Status == 0x0110
        assert ds is None

        self.scp.stop()

    def test_extra_status(self):
        """Test extra status elements are available."""
        self.scp = DummyEventReportSCP()
        self.scp.status = Dataset()
        self.scp.status.Status = 0xFFF0
        self.scp.status.ErrorComment = 'Some comment'
        self.scp.status.ErrorID = 12
        self.scp.status.AffectedSOPClassUID = '1.2.3'
        self.scp.status.AffectedSOPInstanceUID = '1.2.3.4'
        ServiceClass.SCP = self._scp
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_event_report(
            ds, 1, PrintJobSOPClass.uid, '1.2.840.10008.5.1.1.40.1'
        )
        assert status.Status == 0xFFF0
        assert status.ErrorComment == 'Some comment'
        assert status.ErrorID == 12
        assert status.AffectedSOPClassUID == '1.2.3'
        assert status.AffectedSOPInstanceUID == '1.2.3.4'
        assert ds is None
        assoc.release()
        assert assoc.is_released
        self.scp.stop()


class TestAssociationSendNGet(object):
    """Run tests on Assocation send_n_get."""
    def setup(self):
        """Run prior to each test"""
        self.scp = None

    def teardown(self):
        """Clear any active threads"""
        if self.scp:
            self.scp.abort()

        time.sleep(0.1)

        for thread in threading.enumerate():
            if isinstance(thread, DummyBaseSCP):
                thread.abort()
                thread.stop()

    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyGetSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(DisplaySystemSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established
        with pytest.raises(RuntimeError):
            assoc.send_n_get(None, None, None)
        self.scp.stop()

    def test_no_abstract_syntax_match(self):
        """Test SCU when no accepted abstract syntax"""
        self.scp = DummyGetSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(DisplaySystemSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        msg = (
            r"No accepted Presentation Context for the SOP Class "
            r"UID '1.2.840.10008.1.1'"
        )
        with pytest.raises(ValueError, match=msg):
            assoc.send_n_get(None, VerificationSOPClass.uid, None)
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_ups_abstract_syntax(self):
        """Test that sending with UPS uses correct SOP Class UID"""
        pass

    def test_rsp_none(self):
        """Test no response from peer"""
        self.scp = DummyGetSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(DisplaySystemSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        class DummyDIMSE():
            def send_msg(*args, **kwargs): return

            def receive_msg(*args, **kwargs): return None, None

        assoc.dimse = DummyDIMSE()
        assert assoc.is_established
        status, ds = assoc.send_n_get([(0x7fe0,0x0010)],
                                      DisplaySystemSOPClass.uid,
                                      '1.2.840.10008.5.1.1.40.1')

        assert status == Dataset()
        assert ds is None
        assert assoc.is_aborted

        self.scp.stop()

    def test_rsp_invalid(self):
        """Test invalid DIMSE message received from peer"""
        self.scp = DummyGetSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(DisplaySystemSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        class DummyResponse():
            is_valid_response = False

        class DummyDIMSE():
            def send_msg(*args, **kwargs): return
            def receive_msg(*args, **kwargs): return DummyResponse(), None

        assoc.dimse = DummyDIMSE()
        assert assoc.is_established
        status, ds = assoc.send_n_get([(0x7fe0,0x0010)],
                                      DisplaySystemSOPClass.uid,
                                      '1.2.840.10008.5.1.1.40.1')
        assert status == Dataset()
        assert ds is None
        assert assoc.is_aborted

        self.scp.stop()

    def test_rsp_failure(self):
        """Test receiving a failure response from the peer"""
        self.scp = DummyGetSCP()
        self.scp.status = 0x0112
        self.scp.start()
        ae = AE()
        ae.add_requested_context(DisplaySystemSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get([(0x7fe0, 0x0010)],
                                      DisplaySystemSOPClass.uid,
                                      '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0x0112
        assert ds is None
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rsp_warning(self):
        """Test receiving a warning response from the peer"""
        self.scp = DummyGetSCP()
        self.scp.status = 0x0116
        self.scp.start()
        ae = AE()
        ae.add_requested_context(DisplaySystemSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get([(0x7fe0,0x0010)],
                                      DisplaySystemSOPClass.uid,
                                      '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0x0116
        assert ds is not None
        assert isinstance(ds, Dataset)
        assert ds.PatientName == 'Test'
        assert ds.SOPClassUID == DisplaySystemSOPClass.UID
        assert ds.SOPInstanceUID == '1.2.3.4'
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rsp_success(self):
        """Test receiving a success response from the peer"""
        self.scp = DummyGetSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(DisplaySystemSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get([(0x7fe0,0x0010)],
                                      DisplaySystemSOPClass.uid,
                                      '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0x0000
        assert ds is not None
        assert isinstance(ds, Dataset)
        assert ds.PatientName == 'Test'
        assert ds.SOPClassUID == DisplaySystemSOPClass.UID
        assert ds.SOPInstanceUID == '1.2.3.4'
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rsp_unknown_status(self):
        """Test unknown status value returned by peer"""
        self.scp = DummyGetSCP()
        self.scp.status = 0xFFF0
        self.scp.start()
        ae = AE()
        ae.add_requested_context(DisplaySystemSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get([(0x7fe0,0x0010)],
                                      DisplaySystemSOPClass.uid,
                                      '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0xFFF0
        assert ds is None
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rsp_bad_dataset(self):
        """Test bad dataset received from peer"""
        self.scp = DummyGetSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(DisplaySystemSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        class DummyMessage():
            is_valid_response = True
            AttributeList = None
            Status = 0x0000

        class DummyDIMSE():
            def send_msg(*args, **kwargs):
                return

            def receive_msg(*args, **kwargs):
                status = Dataset()
                status.Status = 0x0000

                rsp = DummyMessage()

                return rsp, None

        assoc.dimse = DummyDIMSE()
        assert assoc.is_established
        status, ds = assoc.send_n_get([(0x7fe0,0x0010)],
                                      DisplaySystemSOPClass.uid,
                                      '1.2.840.10008.5.1.1.40.1')

        assert status.Status == 0x0110
        assert ds is None

        self.scp.stop()

    def test_extra_status(self):
        """Test extra status elements are available."""
        self.scp = DummyGetSCP()
        self.scp.status = Dataset()
        self.scp.status.Status = 0xFFF0
        self.scp.status.ErrorComment = 'Some comment'
        self.scp.status.ErrorID = 12
        self.scp.start()
        ae = AE()
        ae.add_requested_context(DisplaySystemSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get([(0x7fe0,0x0010)],
                                      DisplaySystemSOPClass.uid,
                                      '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0xFFF0
        assert status.ErrorComment == 'Some comment'
        assert status.ErrorID == 12
        assert ds is None
        assoc.release()
        assert assoc.is_released
        self.scp.stop()


class TestAssociationSendNSet(object):
    """Run tests on Assocation send_n_set."""
    def _scp(self, req, context, info):
        rsp = N_SET()
        rsp.MessageIDBeingRespondedTo = req.MessageID
        rsp.AffectedSOPClassUID = req.RequestedSOPClassUID
        rsp.AffectedSOPInstanceUID = req.RequestedSOPInstanceUID

        status, ds = self.scp.ae.on_n_set(req.ModificationList,
                                          context.as_tuple,
                                          info)
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

        rsp.AttributeList = BytesIO(encode(ds, True, True))

        self.scp.ae.active_associations[0].dimse.send_msg(rsp, context.context_id)

    def setup(self):
        self.scp = None
        self._orig_scp = ServiceClass.SCP

    def teardown(self):
        """Clear any active threads"""
        if self.scp:
            self.scp.abort()

        time.sleep(0.1)

        for thread in threading.enumerate():
            if isinstance(thread, DummyBaseSCP):
                thread.abort()
                thread.stop()

        ServiceClass.SCP = self._orig_scp

    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        self.scp = DummySetSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established
        with pytest.raises(RuntimeError):
            assoc.send_n_set(None, None, None)
        self.scp.stop()

    def test_no_abstract_syntax_match(self):
        """Test SCU when no accepted abstract syntax"""
        self.scp = DummySetSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        msg = (
            r"No accepted Presentation Context for the SOP Class "
            r"UID '1.2.840.10008.1.1'"
        )
        with pytest.raises(ValueError, match=msg):
            assoc.send_n_set(None, VerificationSOPClass.uid, None)
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rq_bad_dataset_raises(self):
        """Test sending bad dataset raises exception."""
        self.scp = DummySetSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass, ExplicitVRLittleEndian)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        mod_list = Dataset()
        mod_list.PerimeterValue = b'\x00\x01'
        msg = r"Failed to encode the supplied Dataset"
        with pytest.raises(ValueError, match=msg):
            assoc.send_n_set(mod_list, PrintJobSOPClass.uid, '1.2.3')
        assoc.release()
        assert assoc.is_released

        self.scp.stop()

    def test_rsp_none(self):
        """Test no response from peer"""
        self.scp = DummySetSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        class DummyDIMSE():
            def send_msg(*args, **kwargs): return

            def receive_msg(*args, **kwargs): return None, None

        assoc.dimse = DummyDIMSE()
        assert assoc.is_established
        mod_list = Dataset()
        mod_list.PatientName = 'Test^test'
        status, ds = assoc.send_n_set(mod_list,
                                      PrintJobSOPClass.uid,
                                      '1.2.840.10008.5.1.1.40.1')

        assert status == Dataset()
        assert ds is None
        assert assoc.is_aborted

        self.scp.stop()

    def test_rsp_invalid(self):
        """Test invalid DIMSE message received from peer"""
        self.scp = DummySetSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        class DummyResponse():
            is_valid_response = False

        class DummyDIMSE():
            def send_msg(*args, **kwargs): return
            def receive_msg(*args, **kwargs): return DummyResponse(), None

        assoc.dimse = DummyDIMSE()
        assert assoc.is_established
        mod_list = Dataset()
        mod_list.PatientName = 'Test^test'
        status, ds = assoc.send_n_set(mod_list,
                                      PrintJobSOPClass.uid,
                                      '1.2.840.10008.5.1.1.40.1')
        assert status == Dataset()
        assert ds is None
        assert assoc.is_aborted

        self.scp.stop()

    def test_rsp_failure(self):
        """Test receiving a failure response from the peer"""
        self.scp = DummySetSCP()
        self.scp.status = 0x0112
        ServiceClass.SCP = self._scp
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        mod_list = Dataset()
        mod_list.PatientName = 'Test^test'
        status, ds = assoc.send_n_set(mod_list,
                                      PrintJobSOPClass.uid,
                                      '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0x0112
        assert ds is None
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rsp_warning(self):
        """Test receiving a warning response from the peer"""
        self.scp = DummySetSCP()
        self.scp.status = 0x0116
        ServiceClass.SCP = self._scp
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        mod_list = Dataset()
        mod_list.PatientName = 'Test^test'
        status, ds = assoc.send_n_set(mod_list,
                                      PrintJobSOPClass.uid,
                                      '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0x0116
        assert ds is not None
        assert isinstance(ds, Dataset)
        assert ds.PatientName == 'Test'
        assert ds.SOPClassUID == PrintJobSOPClass.UID
        assert ds.SOPInstanceUID == '1.2.3.4'
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rsp_success(self):
        """Test receiving a success response from the peer"""
        self.scp = DummySetSCP()
        ServiceClass.SCP = self._scp
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        mod_list = Dataset()
        mod_list.PatientName = 'Test^test'
        status, ds = assoc.send_n_set(mod_list,
                                      PrintJobSOPClass.uid,
                                      '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0x0000
        assert ds is not None
        assert isinstance(ds, Dataset)
        assert ds.PatientName == 'Test'
        assert ds.SOPClassUID == PrintJobSOPClass.UID
        assert ds.SOPInstanceUID == '1.2.3.4'
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rsp_unknown_status(self):
        """Test unknown status value returned by peer"""
        self.scp = DummySetSCP()
        self.scp.status = 0xFFF0
        ServiceClass.SCP = self._scp
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        mod_list = Dataset()
        mod_list.PatientName = 'Test^test'
        status, ds = assoc.send_n_set(mod_list,
                                      PrintJobSOPClass.uid,
                                      '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0xFFF0
        assert ds is None
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rsp_bad_dataset(self):
        """Test bad dataset received from peer"""
        self.scp = DummySetSCP()
        ServiceClass.SCP = self._scp
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        class DummyMessage():
            is_valid_response = True
            ModificationList = None
            Status = 0x0000

        class DummyDIMSE():
            def send_msg(*args, **kwargs):
                return

            def receive_msg(*args, **kwargs):
                status = Dataset()
                status.Status = 0x0000

                rsp = DummyMessage()

                return rsp, None

        assoc.dimse = DummyDIMSE()
        assert assoc.is_established
        mod_list = Dataset()
        mod_list.PatientName = 'Test^test'
        status, ds = assoc.send_n_set(mod_list,
                                      PrintJobSOPClass.uid,
                                      '1.2.840.10008.5.1.1.40.1')

        assert status.Status == 0x0110
        assert ds is None

        self.scp.stop()

    def test_extra_status(self):
        """Test extra status elements are available."""
        self.scp = DummySetSCP()
        self.scp.status = Dataset()
        self.scp.status.Status = 0xFFF0
        self.scp.status.ErrorComment = 'Some comment'
        self.scp.status.ErrorID = 12
        self.scp.status.AttributeIdentifierList = [(0x7fe0,0x0010)]
        ServiceClass.SCP = self._scp
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        mod_list = Dataset()
        mod_list.PatientName = 'Test^test'
        status, ds = assoc.send_n_set(mod_list,
                                      PrintJobSOPClass.uid,
                                      '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0xFFF0
        assert status.ErrorComment == 'Some comment'
        assert status.ErrorID == 12
        assert status.AttributeIdentifierList == (0x7fe0,0x0010)
        assert ds is None
        assoc.release()
        assert assoc.is_released
        self.scp.stop()


class TestAssociationSendNAction(object):
    """Run tests on Assocation send_n_action."""
    def _scp(self, req, context, info):
        rsp = N_ACTION()
        rsp.MessageIDBeingRespondedTo = req.MessageID
        rsp.AffectedSOPClassUID = req.RequestedSOPClassUID
        rsp.AffectedSOPInstanceUID = req.RequestedSOPInstanceUID
        rsp.ActionTypeID = req.ActionTypeID

        status, ds = self.scp.ae.on_n_action(req.ActionInformation,
                                             context.as_tuple,
                                             info)
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

        rsp.ActionReply = BytesIO(encode(ds, True, True))

        self.scp.ae.active_associations[0].dimse.send_msg(rsp, context.context_id)

    def setup(self):
        self.scp = None
        self._orig_scp = ServiceClass.SCP

    def teardown(self):
        """Clear any active threads"""
        if self.scp:
            self.scp.abort()

        time.sleep(0.1)

        for thread in threading.enumerate():
            if isinstance(thread, DummyBaseSCP):
                thread.abort()
                thread.stop()

        ServiceClass.SCP = self._orig_scp

    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyActionSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established
        with pytest.raises(RuntimeError):
            assoc.send_n_action(None, None, None, None)
        self.scp.stop()

    def test_no_abstract_syntax_match(self):
        """Test SCU when no accepted abstract syntax"""
        self.scp = DummyActionSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        msg = (
            r"No accepted Presentation Context for the SOP Class "
            r"UID '1.2.840.10008.1.1'"
        )
        with pytest.raises(ValueError, match=msg):
            assoc.send_n_action(None, 1, VerificationSOPClass.uid, None)
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rq_bad_dataset_raises(self):
        """Test sending bad dataset raises exception."""
        self.scp = DummyActionSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass, ExplicitVRLittleEndian)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        ds = Dataset()
        ds.PerimeterValue = b'\x00\x01'
        msg = r"Failed to encode the supplied Dataset"
        with pytest.raises(ValueError, match=msg):
            assoc.send_n_action(ds, 1, PrintJobSOPClass.uid, '1.2.3')
        assoc.release()
        assert assoc.is_released

        self.scp.stop()

    def test_rsp_none(self):
        """Test no response from peer"""
        self.scp = DummyActionSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        class DummyDIMSE():
            def send_msg(*args, **kwargs): return

            def receive_msg(*args, **kwargs): return None, None

        assoc.dimse = DummyDIMSE()
        assert assoc.is_established
        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_action(
            ds, 1, PrintJobSOPClass.uid, '1.2.840.10008.5.1.1.40.1'
        )

        assert status == Dataset()
        assert ds is None
        assert assoc.is_aborted

        self.scp.stop()

    def test_rsp_invalid(self):
        """Test invalid DIMSE message received from peer"""
        self.scp = DummyActionSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        class DummyResponse():
            is_valid_response = False

        class DummyDIMSE():
            def send_msg(*args, **kwargs): return
            def receive_msg(*args, **kwargs): return DummyResponse(), None

        assoc.dimse = DummyDIMSE()
        assert assoc.is_established
        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_action(
            ds, 1, PrintJobSOPClass.uid, '1.2.840.10008.5.1.1.40.1'
        )
        assert status == Dataset()
        assert ds is None
        assert assoc.is_aborted

        self.scp.stop()

    def test_rsp_failure(self):
        """Test receiving a failure response from the peer"""
        self.scp = DummyActionSCP()
        self.scp.status = 0x0112
        ServiceClass.SCP = self._scp
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_action(
            ds, 1, PrintJobSOPClass.uid, '1.2.840.10008.5.1.1.40.1'
        )
        assert status.Status == 0x0112
        assert ds is None
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rsp_warning(self):
        """Test receiving a warning response from the peer"""
        self.scp = DummyActionSCP()
        self.scp.status = 0x0116
        ServiceClass.SCP = self._scp
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_action(
            ds, 1, PrintJobSOPClass.uid, '1.2.840.10008.5.1.1.40.1'
        )
        assert status.Status == 0x0116
        assert ds is not None
        assert isinstance(ds, Dataset)
        assert ds.PatientName == 'Test'
        assert ds.SOPClassUID == PrintJobSOPClass.UID
        assert ds.SOPInstanceUID == '1.2.3.4'
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rsp_success(self):
        """Test receiving a success response from the peer"""
        self.scp = DummyActionSCP()
        ServiceClass.SCP = self._scp
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_action(
            ds, 1, PrintJobSOPClass.uid, '1.2.840.10008.5.1.1.40.1'
        )
        assert status.Status == 0x0000
        assert ds is not None
        assert isinstance(ds, Dataset)
        assert ds.PatientName == 'Test'
        assert ds.SOPClassUID == PrintJobSOPClass.UID
        assert ds.SOPInstanceUID == '1.2.3.4'
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rsp_unknown_status(self):
        """Test unknown status value returned by peer"""
        self.scp = DummyActionSCP()
        self.scp.status = 0xFFF0
        ServiceClass.SCP = self._scp
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_action(
            ds, 1, PrintJobSOPClass.uid, '1.2.840.10008.5.1.1.40.1'
        )
        assert status.Status == 0xFFF0
        assert ds is None
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rsp_bad_dataset(self):
        """Test bad dataset received from peer"""
        self.scp = DummyActionSCP()
        ServiceClass.SCP = self._scp
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        class DummyMessage():
            is_valid_response = True
            ModificationList = None
            Status = 0x0000

        class DummyDIMSE():
            def send_msg(*args, **kwargs):
                return

            def receive_msg(*args, **kwargs):
                status = Dataset()
                status.Status = 0x0000

                rsp = DummyMessage()

                return rsp, None

        assoc.dimse = DummyDIMSE()
        assert assoc.is_established
        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_action(
            ds, 1, PrintJobSOPClass.uid, '1.2.840.10008.5.1.1.40.1'
        )

        assert status.Status == 0x0110
        assert ds is None

        self.scp.stop()

    def test_extra_status(self):
        """Test extra status elements are available."""
        self.scp = DummyActionSCP()
        self.scp.status = Dataset()
        self.scp.status.Status = 0xFFF0
        self.scp.status.ErrorComment = 'Some comment'
        self.scp.status.ErrorID = 12
        ServiceClass.SCP = self._scp
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_action(
            ds, 1, PrintJobSOPClass.uid, '1.2.840.10008.5.1.1.40.1'
        )
        assert status.Status == 0xFFF0
        assert status.ErrorComment == 'Some comment'
        assert status.ErrorID == 12
        assert ds is None
        assoc.release()
        assert assoc.is_released
        self.scp.stop()


class TestAssociationSendNCreate(object):
    """Run tests on Assocation send_n_create."""
    def _scp(self, req, context, info):
        rsp = N_CREATE()
        rsp.MessageIDBeingRespondedTo = req.MessageID
        rsp.AffectedSOPClassUID = req.AffectedSOPClassUID
        rsp.AffectedSOPInstanceUID = req.AffectedSOPInstanceUID

        status, ds = self.scp.ae.on_n_create(req.AttributeList,
                                             context.as_tuple,
                                             info)

        if isinstance(status, Dataset):
            if 'Status' not in status:
                raise AttributeError("The 'status' dataset returned by "
                                     "'on_n_create' must contain"
                                     "a (0000,0900) Status element")
            for elem in status:
                if hasattr(rsp, elem.keyword):
                    setattr(rsp, elem.keyword, elem.value)
                else:
                    LOGGER.warning("The 'status' dataset returned by "
                                   "'on_n_create' contained an unsupported "
                                   "Element '%s'.", elem.keyword)
        elif isinstance(status, int):
            rsp.Status = status

        rsp.AttributeList = BytesIO(encode(ds, True, True))

        self.scp.ae.active_associations[0].dimse.send_msg(rsp, context.context_id)

    def setup(self):
        self.scp = None
        self._orig_scp = ServiceClass.SCP

    def teardown(self):
        """Clear any active threads"""
        if self.scp:
            self.scp.abort()

        time.sleep(0.1)

        for thread in threading.enumerate():
            if isinstance(thread, DummyBaseSCP):
                thread.abort()
                thread.stop()

        ServiceClass.SCP = self._orig_scp

    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyCreateSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established
        with pytest.raises(RuntimeError):
            assoc.send_n_create(None, None, None)
        self.scp.stop()

    def test_no_abstract_syntax_match(self):
        """Test SCU when no accepted abstract syntax"""
        self.scp = DummyCreateSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        msg = (
            r"No accepted Presentation Context for the SOP Class "
            r"UID '1.2.840.10008.1.1'"
        )
        with pytest.raises(ValueError, match=msg):
            assoc.send_n_create(None, VerificationSOPClass.uid, None)
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rq_bad_dataset_raises(self):
        """Test sending bad dataset raises exception."""
        self.scp = DummyCreateSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass, ExplicitVRLittleEndian)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        ds = Dataset()
        ds.PerimeterValue = b'\x00\x01'
        msg = r"Failed to encode the supplied Dataset"
        with pytest.raises(ValueError, match=msg):
            assoc.send_n_create(ds, PrintJobSOPClass.uid, '1.2.3')
        assoc.release()
        assert assoc.is_released

        self.scp.stop()

    def test_rsp_none(self):
        """Test no response from peer"""
        self.scp = DummyCreateSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        class DummyDIMSE():
            def send_msg(*args, **kwargs): return

            def receive_msg(*args, **kwargs): return None, None

        assoc.dimse = DummyDIMSE()
        assert assoc.is_established
        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_create(
            ds, PrintJobSOPClass.uid, '1.2.840.10008.5.1.1.40.1'
        )

        assert status == Dataset()
        assert ds is None
        assert assoc.is_aborted

        self.scp.stop()

    def test_rsp_invalid(self):
        """Test invalid DIMSE message received from peer"""
        self.scp = DummyCreateSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        class DummyResponse():
            is_valid_response = False

        class DummyDIMSE():
            def send_msg(*args, **kwargs): return
            def receive_msg(*args, **kwargs): return DummyResponse(), None

        assoc.dimse = DummyDIMSE()
        assert assoc.is_established
        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_create(
            ds, PrintJobSOPClass.uid, '1.2.840.10008.5.1.1.40.1'
        )
        assert status == Dataset()
        assert ds is None
        assert assoc.is_aborted

        self.scp.stop()

    def test_rsp_failure(self):
        """Test receiving a failure response from the peer"""
        self.scp = DummyCreateSCP()
        self.scp.status = 0x0112
        ServiceClass.SCP = self._scp
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_create(
            ds, PrintJobSOPClass.uid, '1.2.840.10008.5.1.1.40.1'
        )
        assert status.Status == 0x0112
        assert ds is None
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rsp_warning(self):
        """Test receiving a warning response from the peer"""
        self.scp = DummyCreateSCP()
        self.scp.status = 0x0116
        ServiceClass.SCP = self._scp
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_create(
            ds, PrintJobSOPClass.uid, '1.2.840.10008.5.1.1.40.1'
        )
        assert status.Status == 0x0116
        assert ds is not None
        assert isinstance(ds, Dataset)
        assert ds.PatientName == 'Test'
        assert ds.SOPClassUID == PrintJobSOPClass.UID
        assert ds.SOPInstanceUID == '1.2.3.4'
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rsp_success(self):
        """Test receiving a success response from the peer"""
        self.scp = DummyCreateSCP()
        ServiceClass.SCP = self._scp
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_create(
            ds, PrintJobSOPClass.uid, '1.2.840.10008.5.1.1.40.1'
        )
        assert status.Status == 0x0000
        assert ds is not None
        assert isinstance(ds, Dataset)
        assert ds.PatientName == 'Test'
        assert ds.SOPClassUID == PrintJobSOPClass.UID
        assert ds.SOPInstanceUID == '1.2.3.4'
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rsp_unknown_status(self):
        """Test unknown status value returned by peer"""
        self.scp = DummyCreateSCP()
        self.scp.status = 0xFFF0
        ServiceClass.SCP = self._scp
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_create(
            ds, PrintJobSOPClass.uid, '1.2.840.10008.5.1.1.40.1'
        )
        assert status.Status == 0xFFF0
        assert ds is None
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rsp_bad_dataset(self):
        """Test bad dataset received from peer"""
        self.scp = DummyCreateSCP()
        ServiceClass.SCP = self._scp
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        class DummyMessage():
            is_valid_response = True
            ModificationList = None
            Status = 0x0000

        class DummyDIMSE():
            def send_msg(*args, **kwargs):
                return

            def receive_msg(*args, **kwargs):
                status = Dataset()
                status.Status = 0x0000

                rsp = DummyMessage()

                return rsp, None

        assoc.dimse = DummyDIMSE()
        assert assoc.is_established
        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_create(
            ds, PrintJobSOPClass.uid, '1.2.840.10008.5.1.1.40.1'
        )

        assert status.Status == 0x0110
        assert ds is None

        self.scp.stop()

    def test_extra_status(self):
        """Test extra status elements are available."""
        self.scp = DummyCreateSCP()
        self.scp.status = Dataset()
        self.scp.status.Status = 0xFFF0
        self.scp.status.ErrorComment = 'Some comment'
        self.scp.status.ErrorID = 12
        ServiceClass.SCP = self._scp
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        ds = Dataset()
        ds.PatientName = 'Test^test'
        status, ds = assoc.send_n_create(
            ds, PrintJobSOPClass.uid, '1.2.840.10008.5.1.1.40.1'
        )
        assert status.Status == 0xFFF0
        assert status.ErrorComment == 'Some comment'
        assert status.ErrorID == 12
        assert ds is None
        assoc.release()
        assert assoc.is_released
        self.scp.stop()


class TestAssociationSendNDelete(object):
    """Run tests on Assocation send_n_delete."""
    def _scp(self, req, context, info):
        rsp = N_DELETE()
        rsp.MessageIDBeingRespondedTo = req.MessageID

        status = self.scp.ae.on_n_delete(context.as_tuple, info)
        if isinstance(status, Dataset):
            if 'Status' not in status:
                raise AttributeError("The 'status' dataset returned by "
                                     "'on_c_echo' must contain"
                                     "a (0000,0900) Status element")
            for elem in status:
                if hasattr(rsp, elem.keyword):
                    setattr(rsp, elem.keyword, elem.value)
                else:
                    LOGGER.warning("The 'status' dataset returned by "
                                   "'on_c_echo' contained an unsupported "
                                   "Element '%s'.", elem.keyword)
        elif isinstance(status, int):
            rsp.Status = status

        self.scp.ae.active_associations[0].dimse.send_msg(rsp, context.context_id)

    def setup(self):
        self.scp = None
        self._orig_scp = ServiceClass.SCP

    def teardown(self):
        """Clear any active threads"""
        if self.scp:
            self.scp.abort()

        time.sleep(0.1)

        for thread in threading.enumerate():
            if isinstance(thread, DummyBaseSCP):
                thread.abort()
                thread.stop()

        ServiceClass.SCP = self._orig_scp

    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyDeleteSCP()
        self.scp.start()

        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assoc.release()

        assert assoc.is_released
        assert not assoc.is_established
        with pytest.raises(RuntimeError):
            assoc.send_n_delete(None, None)

        self.scp.stop()

    def test_no_abstract_syntax_match(self):
        """Test SCU when no accepted abstract syntax"""
        self.scp = DummyDeleteSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        msg = (
            r"No accepted Presentation Context for the SOP Class "
            r"UID '1.2.840.10008.1.1'"
        )
        with pytest.raises(ValueError, match=msg):
            assoc.send_n_delete(VerificationSOPClass.uid, None)
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rsp_none(self):
        """Test no response from peer"""
        self.scp = DummyDeleteSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        class DummyDIMSE():
            def send_msg(*args, **kwargs): return

            def receive_msg(*args, **kwargs): return None, None

        assoc.dimse = DummyDIMSE()
        assert assoc.is_established
        status = assoc.send_n_delete(PrintJobSOPClass.uid,
                                     '1.2.840.10008.5.1.1.40.1')

        assert status == Dataset()
        assert assoc.is_aborted

        self.scp.stop()

    def test_rsp_invalid(self):
        """Test invalid DIMSE message received from peer"""
        self.scp = DummyDeleteSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        class DummyResponse():
            is_valid_response = False

        class DummyDIMSE():
            def send_msg(*args, **kwargs): return
            def receive_msg(*args, **kwargs): return DummyResponse(), None

        assoc.dimse = DummyDIMSE()
        assert assoc.is_established
        status = assoc.send_n_delete(PrintJobSOPClass.uid,
                                     '1.2.840.10008.5.1.1.40.1')
        assert status == Dataset()
        assert assoc.is_aborted

        self.scp.stop()

    def test_rsp_failure(self):
        """Test receiving a failure response from the peer"""
        self.scp = DummyDeleteSCP()
        self.scp.status = 0x0112
        ServiceClass.SCP = self._scp
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status = assoc.send_n_delete(PrintJobSOPClass.uid,
                                     '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0x0112
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rsp_success(self):
        """Test receiving a success response from the peer"""
        self.scp = DummyDeleteSCP()
        ServiceClass.SCP = self._scp
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established
        status = assoc.send_n_delete(PrintJobSOPClass.uid,
                                     '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0x0000
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rsp_unknown_status(self):
        """Test unknown status value returned by peer"""
        self.scp = DummyDeleteSCP()
        self.scp.status = 0xFFF0
        ServiceClass.SCP = self._scp
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status = assoc.send_n_delete(PrintJobSOPClass.uid,
                                     '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0xFFF0
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_extra_status(self):
        """Test extra status elements are available."""
        self.scp = DummyDeleteSCP()
        self.scp.status = Dataset()
        self.scp.status.Status = 0xFFF0
        self.scp.status.ErrorComment = 'Some comment'
        self.scp.status.ErrorID = 12
        ServiceClass.SCP = self._scp
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PrintJobSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status = assoc.send_n_delete(PrintJobSOPClass.uid,
                                     '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0xFFF0
        assert status.ErrorComment == 'Some comment'
        assert status.ErrorID == 12
        assoc.release()
        assert assoc.is_released
        self.scp.stop()
