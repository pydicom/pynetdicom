"""Tests for the RelevantPatientInformationQueryServiceClass."""

from io import BytesIO
import os
import time

import pytest

from pydicom.dataset import Dataset
from pydicom.uid import ExplicitVRLittleEndian

from pynetdicom import AE, evt, debug_logger
from pynetdicom.dimse_primitives import C_FIND
from pynetdicom.service_class import (
    RelevantPatientInformationQueryServiceClass
)
from pynetdicom.sop_class import (
    GeneralRelevantPatientInformationQuery,
    BreastImagingRelevantPatientInformationQuery,
    CardiacRelevantPatientInformationQuery,
)

from .dummy_c_scp import (
    DummyFindSCP,
    DummyBaseSCP
)


#debug_logger()


class TestRelevantPatientServiceClass(object):
    """Test the RelevantPatientInformationQueryServiceClass"""
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
                for elem in event.identifier.iterall():
                    pass
            except:
                yield 0xC310, None
            yield 0xFF00, self.query

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(GeneralRelevantPatientInformationQuery)
        ae.add_requested_context(
            GeneralRelevantPatientInformationQuery,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        req = C_FIND()
        req.MessageID = 1
        req.AffectedSOPClassUID = GeneralRelevantPatientInformationQuery
        req.Priority = 2
        req.Identifier = BytesIO(b'\x08\x00\x01\x00\x40\x40\x00\x00\x00\x00\x00\x08\x00\x49')
        assoc._reactor_checkpoint.clear()
        assoc.dimse.send_msg(req, 1)
        cx_id, rsp = assoc.dimse.get_msg(True)
        assoc._reactor_checkpoint.set()
        assert rsp.Status == 0xC310

        assoc.release()
        scp.shutdown()

    def test_handler_status_dataset(self):
        """Test handler yielding a Dataset status"""
        def handle(event):
            status = Dataset()
            status.Status = 0xFF00
            yield status,  self.query

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(GeneralRelevantPatientInformationQuery)
        ae.add_requested_context(
            GeneralRelevantPatientInformationQuery,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, GeneralRelevantPatientInformationQuery)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        status, identifier = next(result)
        assert status.Status == 0x0000

        assoc.release()
        scp.shutdown()

    def test_handler_status_dataset_multi(self):
        """Test handler yielding a Dataset status with other elements"""
        def handle(event):
            status = Dataset()
            status.Status = 0xFF00
            status.ErrorComment = "Test"
            status.OffendingElement = 0x00010001
            yield status,  self.query

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(GeneralRelevantPatientInformationQuery)
        ae.add_requested_context(GeneralRelevantPatientInformationQuery)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, GeneralRelevantPatientInformationQuery)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert status.ErrorComment == 'Test'
        assert status.OffendingElement == 0x00010001
        status, identifier = next(result)
        assert status.Status == 0x0000

        assoc.release()
        scp.shutdown()

    def test_handler_status_int(self):
        """Test handler yielding an int status"""
        def handle(event):
            yield 0xFF00, self.query

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(GeneralRelevantPatientInformationQuery)
        ae.add_requested_context(GeneralRelevantPatientInformationQuery)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, GeneralRelevantPatientInformationQuery)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        status, identifier = next(result)
        assert status.Status == 0x0000

        assoc.release()
        scp.shutdown()

    def test_handler_status_unknown(self):
        """Test SCP handles handler yielding a unknown status"""
        def handle(event):
            yield 0xFFF0, self.query

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(GeneralRelevantPatientInformationQuery)
        ae.add_requested_context(GeneralRelevantPatientInformationQuery)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, GeneralRelevantPatientInformationQuery)
        status, identifier = next(result)
        assert status.Status == 0xFFF0
        pytest.raises(StopIteration, next, result)
        assoc.release()
        scp.shutdown()

    def test_handler_status_invalid(self):
        """Test SCP handles handler yielding a invalid status"""
        def handle(event):
            yield 'Failed',  self.query

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(GeneralRelevantPatientInformationQuery)
        ae.add_requested_context(GeneralRelevantPatientInformationQuery)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, GeneralRelevantPatientInformationQuery)
        status, identifier = next(result)
        assert status.Status == 0xC002
        pytest.raises(StopIteration, next, result)
        assoc.release()
        scp.shutdown()

    def test_handler_status_none(self):
        """Test SCP handles handler not yielding a status"""
        def handle(event):
            yield None,  self.query

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(GeneralRelevantPatientInformationQuery)
        ae.add_requested_context(GeneralRelevantPatientInformationQuery)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, GeneralRelevantPatientInformationQuery)
        status, identifier = next(result)
        assert status.Status == 0xC002
        pytest.raises(StopIteration, next, result)
        assoc.release()
        scp.shutdown()

    def test_handler_exception(self):
        """Test SCP handles handler yielding an exception"""
        def handle(event):
            raise ValueError
            yield 0xFF00, self.query

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(GeneralRelevantPatientInformationQuery)
        ae.add_requested_context(GeneralRelevantPatientInformationQuery)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, GeneralRelevantPatientInformationQuery)
        status, identifier = next(result)
        assert status.Status == 0xC311
        pytest.raises(StopIteration, next, result)
        assoc.release()
        scp.shutdown()

    def test_handler_bad_identifier(self):
        """Test SCP handles a bad handler identifier"""
        def handle(event):
            yield 0xFF00, None

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(GeneralRelevantPatientInformationQuery)
        ae.add_requested_context(GeneralRelevantPatientInformationQuery)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, GeneralRelevantPatientInformationQuery)
        status, identifier = next(result)
        assert status.Status == 0xC312
        pytest.raises(StopIteration, next, result)

        assoc.release()
        scp.shutdown()

    def test_pending_cancel(self):
        """Test handler yielding pending then cancel status"""
        # Note: success should be second, cancel should get ignored
        def handle(event):
            yield 0xFF00, self.query
            yield 0xFE00, None

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(GeneralRelevantPatientInformationQuery)
        ae.add_requested_context(GeneralRelevantPatientInformationQuery)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, GeneralRelevantPatientInformationQuery)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier == self.query
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        pytest.raises(StopIteration, next, result)

        assoc.release()
        scp.shutdown()

    def test_pending_success(self):
        """Test handler yielding pending then success status"""
        def handle(event):
            yield 0xFF00, self.query
            yield 0x0000, None

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(GeneralRelevantPatientInformationQuery)
        ae.add_requested_context(GeneralRelevantPatientInformationQuery)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, GeneralRelevantPatientInformationQuery)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier == self.query
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        pytest.raises(StopIteration, next, result)

        assoc.release()
        scp.shutdown()

    def test_pending_failure(self):
        """Test handler yielding pending then failure status"""
        def handle(event):
            yield 0xFF00, self.query
            yield 0xA700, None

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(GeneralRelevantPatientInformationQuery)
        ae.add_requested_context(GeneralRelevantPatientInformationQuery)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, GeneralRelevantPatientInformationQuery)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier == self.query
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        pytest.raises(StopIteration, next, result)

        assoc.release()
        scp.shutdown()

    def test_cancel(self):
        """Test handler yielding cancel status"""
        def handle(event):
            yield 0xFE00, None

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(GeneralRelevantPatientInformationQuery)
        ae.add_requested_context(GeneralRelevantPatientInformationQuery)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, GeneralRelevantPatientInformationQuery)
        status, identifier = next(result)
        assert status.Status == 0xFE00
        assert identifier is None
        pytest.raises(StopIteration, next, result)

        assoc.release()
        scp.shutdown()

    def test_failure(self):
        """Test handler yielding failure status"""
        def handle(event):
            yield 0xA700, None

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(GeneralRelevantPatientInformationQuery)
        ae.add_requested_context(GeneralRelevantPatientInformationQuery)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, GeneralRelevantPatientInformationQuery)
        status, identifier = next(result)
        assert status.Status == 0xA700
        assert identifier is None
        pytest.raises(StopIteration, next, result)

        assoc.release()
        scp.shutdown()

    def test_success(self):
        """Test handler yielding success status"""
        def handle(event):
            yield 0x0000, None

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(GeneralRelevantPatientInformationQuery)
        ae.add_requested_context(GeneralRelevantPatientInformationQuery)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, GeneralRelevantPatientInformationQuery)
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        pytest.raises(StopIteration, next, result)

        assoc.release()
        scp.shutdown()

    def test_no_response(self):
        """Test handler yielding success status"""
        def handle(event):
            pass

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(GeneralRelevantPatientInformationQuery)
        ae.add_requested_context(GeneralRelevantPatientInformationQuery)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, GeneralRelevantPatientInformationQuery)
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        pytest.raises(StopIteration, next, result)

        assoc.release()
        scp.shutdown()

    def test_scp_handler_context(self):
        """Test handler event's context attribute"""
        attrs = {}
        def handle(event):
            attrs['context'] = event.context
            attrs['identifier'] = event.identifier
            attrs['request'] = event.request
            attrs['assoc'] = event.assoc
            yield 0xFF00, self.query

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(GeneralRelevantPatientInformationQuery)
        ae.add_requested_context(GeneralRelevantPatientInformationQuery)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, GeneralRelevantPatientInformationQuery)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        status, identifier = next(result)
        assert status.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        cx = attrs['context']
        assert cx.context_id == 1
        assert cx.abstract_syntax == GeneralRelevantPatientInformationQuery
        assert cx.transfer_syntax == '1.2.840.10008.1.2'

        scp.shutdown()

    def test_scp_handler_assoc(self):
        """Test handler event's assoc attribute"""
        attrs = {}
        def handle(event):
            attrs['context'] = event.context
            attrs['identifier'] = event.identifier
            attrs['request'] = event.request
            attrs['assoc'] = event.assoc
            yield 0xFF00, self.query

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(GeneralRelevantPatientInformationQuery)
        ae.add_requested_context(GeneralRelevantPatientInformationQuery)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, GeneralRelevantPatientInformationQuery)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        status, identifier = next(result)
        assert status.Status == 0x0000

        scp_assoc = attrs['assoc']
        assert scp_assoc == scp.active_associations[0]
        scp_assoc.release()
        assert scp_assoc.is_released

        scp.shutdown()

    def test_scp_handler_request(self):
        """Test handler event's request attribute"""
        attrs = {}
        def handle(event):
            attrs['context'] = event.context
            attrs['identifier'] = event.identifier
            attrs['request'] = event.request
            attrs['assoc'] = event.assoc
            yield 0xFF00, self.query

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(GeneralRelevantPatientInformationQuery)
        ae.add_requested_context(GeneralRelevantPatientInformationQuery)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, GeneralRelevantPatientInformationQuery)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        status, identifier = next(result)
        assert status.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        req = attrs['request']
        assert isinstance(req, C_FIND)

        scp.shutdown()

    def test_scp_handler_identifier(self):
        """Test handler event's identifier property"""
        attrs = {}
        def handle(event):
            attrs['context'] = event.context
            attrs['identifier'] = event.identifier
            attrs['request'] = event.request
            attrs['assoc'] = event.assoc
            yield 0xFF00, self.query

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(GeneralRelevantPatientInformationQuery)
        ae.add_requested_context(GeneralRelevantPatientInformationQuery)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, GeneralRelevantPatientInformationQuery)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        status, identifier = next(result)
        assert status.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        ds = attrs['identifier']
        assert ds.PatientName == '*'

        scp.shutdown()

    def test_scp_handler_aborts_before(self):
        """Test handler aborts before any yields"""
        def handle(event):
            event.assoc.abort()
            yield 0xFF00, self.query

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(GeneralRelevantPatientInformationQuery)
        ae.add_requested_context(GeneralRelevantPatientInformationQuery)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(
            self.query, GeneralRelevantPatientInformationQuery
        )
        status, identifier = next(result)
        assert status == Dataset()
        assert identifier is None

        time.sleep(0.1)
        assert assoc.is_aborted
        scp.shutdown()

    def test_scp_handler_aborts_before_solo(self):
        """Test handler aborts before any yields"""
        def handle(event):
            event.assoc.abort()

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(GeneralRelevantPatientInformationQuery)
        ae.add_requested_context(GeneralRelevantPatientInformationQuery)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(
            self.query, GeneralRelevantPatientInformationQuery
        )
        status, identifier = next(result)
        assert status == Dataset()
        assert identifier is None

        time.sleep(0.1)
        assert assoc.is_aborted
        scp.shutdown()
