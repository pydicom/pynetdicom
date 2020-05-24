"""Tests for the SubstanceAdministrationQueryServiceClass."""

from io import BytesIO
import time

import pytest

from pydicom.dataset import Dataset
from pydicom.uid import ExplicitVRLittleEndian

from pynetdicom import AE, evt, debug_logger
from pynetdicom.dimse_primitives import C_FIND
from pynetdicom.presentation import PresentationContext
from pynetdicom.service_class import (
    SubstanceAdministrationQueryServiceClass,
)
from pynetdicom.sop_class import (
    ProductCharacteristicsQueryInformationModelFind,
)
from .dummy_c_scp import (
    DummyFindSCP,
    DummyBaseSCP,
)


#debug_logger()


class TestSubstanceAdministrationQueryServiceClass(object):
    """Test the SubstanceAdministrationQueryServiceClass.

    Subclass of QR Find Service class with its own statuses.
    """
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
        ae.add_supported_context(ProductCharacteristicsQueryInformationModelFind)
        ae.add_requested_context(
            ProductCharacteristicsQueryInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        req = C_FIND()
        req.MessageID = 1
        req.AffectedSOPClassUID = ProductCharacteristicsQueryInformationModelFind
        req.Priority = 2
        req.Identifier = BytesIO(
            b'\x08\x00\x01\x00\x40\x40\x00\x00\x00\x00\x00\x08\x00\x49'
        )
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
        ae.add_supported_context(ProductCharacteristicsQueryInformationModelFind)
        ae.add_requested_context(
            ProductCharacteristicsQueryInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, ProductCharacteristicsQueryInformationModelFind)
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
        ae.add_supported_context(ProductCharacteristicsQueryInformationModelFind)
        ae.add_requested_context(
            ProductCharacteristicsQueryInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, ProductCharacteristicsQueryInformationModelFind)
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
        ae.add_supported_context(ProductCharacteristicsQueryInformationModelFind)
        ae.add_requested_context(
            ProductCharacteristicsQueryInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, ProductCharacteristicsQueryInformationModelFind)
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
        ae.add_supported_context(ProductCharacteristicsQueryInformationModelFind)
        ae.add_requested_context(
            ProductCharacteristicsQueryInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, ProductCharacteristicsQueryInformationModelFind)
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
        ae.add_supported_context(ProductCharacteristicsQueryInformationModelFind)
        ae.add_requested_context(
            ProductCharacteristicsQueryInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, ProductCharacteristicsQueryInformationModelFind)
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
        ae.add_supported_context(ProductCharacteristicsQueryInformationModelFind)
        ae.add_requested_context(
            ProductCharacteristicsQueryInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, ProductCharacteristicsQueryInformationModelFind)
        status, identifier = next(result)
        assert status.Status == 0xC002
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
        ae.add_supported_context(ProductCharacteristicsQueryInformationModelFind)
        ae.add_requested_context(
            ProductCharacteristicsQueryInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, ProductCharacteristicsQueryInformationModelFind)
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
        ae.add_supported_context(ProductCharacteristicsQueryInformationModelFind)
        ae.add_requested_context(
            ProductCharacteristicsQueryInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, ProductCharacteristicsQueryInformationModelFind)
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
        ae.add_supported_context(ProductCharacteristicsQueryInformationModelFind)
        ae.add_requested_context(
            ProductCharacteristicsQueryInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, ProductCharacteristicsQueryInformationModelFind)
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
        ae.add_supported_context(ProductCharacteristicsQueryInformationModelFind)
        ae.add_requested_context(
            ProductCharacteristicsQueryInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, ProductCharacteristicsQueryInformationModelFind)
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
        ae.add_supported_context(ProductCharacteristicsQueryInformationModelFind)
        ae.add_requested_context(
            ProductCharacteristicsQueryInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, ProductCharacteristicsQueryInformationModelFind)
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
        ae.add_supported_context(ProductCharacteristicsQueryInformationModelFind)
        ae.add_requested_context(
            ProductCharacteristicsQueryInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, ProductCharacteristicsQueryInformationModelFind)
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
        ae.add_supported_context(ProductCharacteristicsQueryInformationModelFind)
        ae.add_requested_context(
            ProductCharacteristicsQueryInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, ProductCharacteristicsQueryInformationModelFind)
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
        ae.add_supported_context(ProductCharacteristicsQueryInformationModelFind)
        ae.add_requested_context(
            ProductCharacteristicsQueryInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, ProductCharacteristicsQueryInformationModelFind)
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
        ae.add_supported_context(ProductCharacteristicsQueryInformationModelFind)
        ae.add_requested_context(
            ProductCharacteristicsQueryInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, ProductCharacteristicsQueryInformationModelFind)
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
        ae.add_supported_context(ProductCharacteristicsQueryInformationModelFind)
        ae.add_requested_context(
            ProductCharacteristicsQueryInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, ProductCharacteristicsQueryInformationModelFind)
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
        ae.add_supported_context(ProductCharacteristicsQueryInformationModelFind)
        ae.add_requested_context(ProductCharacteristicsQueryInformationModelFind)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, ProductCharacteristicsQueryInformationModelFind)
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
        assert cx.abstract_syntax == ProductCharacteristicsQueryInformationModelFind
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
        ae.add_supported_context(ProductCharacteristicsQueryInformationModelFind)
        ae.add_requested_context(ProductCharacteristicsQueryInformationModelFind)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, ProductCharacteristicsQueryInformationModelFind)
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
        ae.add_supported_context(ProductCharacteristicsQueryInformationModelFind)
        ae.add_requested_context(ProductCharacteristicsQueryInformationModelFind)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, ProductCharacteristicsQueryInformationModelFind)
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
            yield 0xFF00, self.query

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ProductCharacteristicsQueryInformationModelFind)
        ae.add_requested_context(ProductCharacteristicsQueryInformationModelFind)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, ProductCharacteristicsQueryInformationModelFind)
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
        ae.add_supported_context(ProductCharacteristicsQueryInformationModelFind)
        ae.add_requested_context(ProductCharacteristicsQueryInformationModelFind)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        identifier = Dataset()
        identifier.PatientID = '*'
        results = assoc.send_c_find(
            identifier, ProductCharacteristicsQueryInformationModelFind, msg_id=11142
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
