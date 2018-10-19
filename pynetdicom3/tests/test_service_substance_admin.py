"""Tests for the QueryRetrieveServiceClass."""

from io import BytesIO
import logging
import os
import threading
import time

import pytest

from pydicom.dataset import Dataset
from pydicom.uid import ExplicitVRLittleEndian

from pynetdicom3 import AE
from pynetdicom3.dimse_primitives import C_FIND
from pynetdicom3.presentation import PresentationContext
from pynetdicom3.service_class import (
    SubstanceAdministrationQueryServiceClass,
)
from pynetdicom3.sop_class import (
    ProductCharacteristicsQueryInformationModelFind,
)
from .dummy_c_scp import (
    DummyFindSCP,
    DummyBaseSCP,
)

LOGGER = logging.getLogger('pynetdicom3')
#LOGGER.setLevel(logging.DEBUG)
LOGGER.setLevel(logging.CRITICAL)


class TestQRFindServiceClass(object):
    """Test the QueryRetrieveFindServiceClass"""
    def setup(self):
        """Run prior to each test"""
        self.query = Dataset()
        self.query.QueryRetrieveLevel = "PATIENT"
        self.query.PatientName = '*'

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

    def test_bad_req_identifier(self):
        """Test SCP handles a bad request identifier"""
        self.scp = DummyFindSCP()
        self.scp.statuses = [0xFF00]
        self.scp.identifiers = [self.query]
        self.scp.start()

        ae = AE()
        ae.add_requested_context(ProductCharacteristicsQueryInformationModelFind,
                                 ExplicitVRLittleEndian)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        req = C_FIND()
        req.MessageID = 1
        req.AffectedSOPClassUID = ProductCharacteristicsQueryInformationModelFind.uid
        req.Priority = 2
        req.Identifier = BytesIO(b'\x08\x00\x01\x00\x04\x00\x00\x00\x00\x08\x00\x49')
        assoc.dimse.send_msg(req, 1)
        rsp, _ = assoc.dimse.receive_msg(True)
        assert rsp.Status == 0xC310

        assoc.release()
        self.scp.stop()

    def test_callback_status_dataset(self):
        """Test on_c_find yielding a Dataset status"""
        self.scp = DummyFindSCP()
        self.scp.statuses = [Dataset(), 0x0000]
        self.scp.statuses[0].Status = 0xFF00
        self.scp.identifers = [self.query, None]
        self.scp.start()

        ae = AE()
        ae.add_requested_context(ProductCharacteristicsQueryInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='PC')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        status, identifier = next(result)
        assert status.Status == 0x0000

        assoc.release()
        self.scp.stop()

    def test_callback_status_dataset_multi(self):
        """Test on_c_find yielding a Dataset status with other elements"""
        self.scp = DummyFindSCP()
        self.scp.statuses = [Dataset()]
        self.scp.statuses[0].Status = 0xFF00
        self.scp.statuses[0].ErrorComment = 'Test'
        self.scp.statuses[0].OffendingElement = 0x00010001
        self.scp.identifiers = [self.query]
        self.scp.start()

        ae = AE()
        ae.add_requested_context(ProductCharacteristicsQueryInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='PC')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert status.ErrorComment == 'Test'
        assert status.OffendingElement == 0x00010001
        status, identifier = next(result)
        assert status.Status == 0x0000

        assoc.release()
        self.scp.stop()

    def test_callback_status_int(self):
        """Test on_c_find yielding an int status"""
        self.scp = DummyFindSCP()
        self.scp.statuses = [0xFF00]
        self.scp.identifiers = [self.query]
        self.scp.start()

        ae = AE()
        ae.add_requested_context(ProductCharacteristicsQueryInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='PC')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        status, identifier = next(result)
        assert status.Status == 0x0000

        assoc.release()
        self.scp.stop()

    def test_callback_status_unknown(self):
        """Test SCP handles on_c_find yielding a unknown status"""
        self.scp = DummyFindSCP()
        self.scp.statuses = [0xFFF0]
        self.scp.start()

        ae = AE()
        ae.add_requested_context(ProductCharacteristicsQueryInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='PC')
        status, identifier = next(result)
        assert status.Status == 0xFFF0
        pytest.raises(StopIteration, next, result)
        assoc.release()
        self.scp.stop()

    def test_callback_status_invalid(self):
        """Test SCP handles on_c_find yielding a invalid status"""
        self.scp = DummyFindSCP()
        self.scp.statuses = ['Failure']
        self.scp.start()

        ae = AE()
        ae.add_requested_context(ProductCharacteristicsQueryInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='PC')
        status, identifier = next(result)
        assert status.Status == 0xC002
        pytest.raises(StopIteration, next, result)
        assoc.release()
        self.scp.stop()

    def test_callback_status_none(self):
        """Test SCP handles on_c_find not yielding a status"""
        self.scp = DummyFindSCP()
        self.scp.statuses = [None]
        self.scp.start()

        ae = AE()
        ae.add_requested_context(ProductCharacteristicsQueryInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='PC')
        status, identifier = next(result)
        assert status.Status == 0xC002
        pytest.raises(StopIteration, next, result)
        assoc.release()
        self.scp.stop()

    def test_callback_exception(self):
        """Test SCP handles on_c_find yielding an exception"""
        self.scp = DummyFindSCP()
        def on_c_find(ds, context, info): raise ValueError
        self.scp.ae.on_c_find = on_c_find
        self.scp.start()

        ae = AE()
        ae.add_requested_context(ProductCharacteristicsQueryInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='PC')
        status, identifier = next(result)
        assert status.Status == 0xC311
        pytest.raises(StopIteration, next, result)
        assoc.release()
        self.scp.stop()

    def test_callback_bad_identifier(self):
        """Test SCP handles a bad callback identifier"""
        self.scp = DummyFindSCP()
        self.scp.statuses = [0xFF00, 0xFE00]
        self.scp.identifiers = [None, None]
        self.scp.start()

        ae = AE()
        ae.add_requested_context(ProductCharacteristicsQueryInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='PC')
        status, identifier = next(result)
        assert status.Status == 0xC312
        pytest.raises(StopIteration, next, result)

        assoc.release()
        self.scp.stop()

    def test_pending_cancel(self):
        """Test on_c_find yielding pending then cancel status"""
        self.scp = DummyFindSCP()
        self.scp.statuses = [0xFF00, 0xFE00]
        self.scp.identifiers = [self.query, None]
        self.scp.start()

        ae = AE()
        ae.add_requested_context(ProductCharacteristicsQueryInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='PC')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier == self.query
        status, identifier = next(result)
        assert status.Status == 0xFE00
        assert identifier is None
        pytest.raises(StopIteration, next, result)

        assoc.release()
        self.scp.stop()

    def test_pending_success(self):
        """Test on_c_find yielding pending then success status"""
        self.scp = DummyFindSCP()
        self.scp.statuses = [0xFF01, 0x0000, 0xA700]
        self.scp.identifiers = [self.query, None]
        self.scp.start()

        ae = AE()
        ae.add_requested_context(ProductCharacteristicsQueryInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='PC')
        status, identifier = next(result)
        assert status.Status == 0xFF01
        assert identifier == self.query
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        pytest.raises(StopIteration, next, result)

        assoc.release()
        self.scp.stop()

    def test_pending_failure(self):
        """Test on_c_find yielding pending then failure status"""
        self.scp = DummyFindSCP()
        self.scp.statuses = [0xFF00, 0xA700, 0x0000]
        self.scp.identifiers = [self.query, None, None]
        self.scp.start()

        ae = AE()
        ae.add_requested_context(ProductCharacteristicsQueryInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='PC')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier == self.query
        status, identifier = next(result)
        assert status.Status == 0xA700
        assert identifier is None
        pytest.raises(StopIteration, next, result)

        assoc.release()
        self.scp.stop()

    def test_multi_pending_cancel(self):
        """Test on_c_find yielding multiple pending then cancel status"""
        self.scp = DummyFindSCP()
        self.scp.statuses = [0xFF00, 0xFF01, 0xFF00, 0xFE00, 0x0000]
        self.scp.identifiers = [self.query, self.query, self.query, None]
        self.scp.start()

        ae = AE()
        ae.add_requested_context(ProductCharacteristicsQueryInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='PC')
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
        pytest.raises(StopIteration, next, result)

        assoc.release()
        self.scp.stop()

    def test_multi_pending_success(self):
        """Test on_c_find yielding multiple pending then success status"""
        self.scp = DummyFindSCP()
        self.scp.statuses = [0xFF00, 0xFF01, 0xFF00, 0x0000, 0xA700]
        self.scp.identifiers = [self.query, self.query, self.query, None]
        self.scp.start()

        ae = AE()
        ae.add_requested_context(ProductCharacteristicsQueryInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='PC')
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
        pytest.raises(StopIteration, next, result)

        assoc.release()
        self.scp.stop()

    def test_multi_pending_failure(self):
        """Test on_c_find yielding multiple pending then failure status"""
        self.scp = DummyFindSCP()
        self.scp.statuses = [0xFF00, 0xFF01, 0xFF00, 0xA700, 0x0000]
        self.scp.identifiers = [self.query, self.query, self.query, None]
        self.scp.start()

        ae = AE()
        ae.add_requested_context(ProductCharacteristicsQueryInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='PC')
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
        pytest.raises(StopIteration, next, result)

        assoc.release()
        self.scp.stop()

    def test_scp_callback_context(self):
        """Test on_c_store caontext parameter"""
        self.scp = DummyFindSCP()
        self.scp.statuses = [Dataset(), 0x0000]
        self.scp.statuses[0].Status = 0xFF00
        self.identifiers = [self.query, None]
        self.scp.start()

        ae = AE()
        ae.add_requested_context(ProductCharacteristicsQueryInformationModelFind,
                                 '1.2.840.10008.1.2.1')
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='PC')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        status, identifier = next(result)
        assert status.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        assert self.scp.context.context_id == 1
        assert self.scp.context.abstract_syntax == ProductCharacteristicsQueryInformationModelFind.uid
        assert self.scp.context.transfer_syntax == '1.2.840.10008.1.2.1'

        self.scp.stop()

    def test_scp_callback_info(self):
        """Test on_c_store caontext parameter"""
        self.scp = DummyFindSCP()
        self.scp.statuses = [Dataset(), 0x0000]
        self.scp.statuses[0].Status = 0xFF00
        self.identifiers = [self.query, None]
        self.scp.start()

        ae = AE()
        ae.add_requested_context(ProductCharacteristicsQueryInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='PC')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        status, identifier = next(result)
        assert status.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        assert self.scp.info['requestor']['address'] == '127.0.0.1'
        assert self.scp.info['requestor']['ae_title'] == b'PYNETDICOM      '
        assert self.scp.info['requestor']['called_aet'] == b'ANY-SCP         '
        assert isinstance(self.scp.info['requestor']['port'], int)
        assert self.scp.info['acceptor']['port'] == 11112
        assert self.scp.info['acceptor']['address'] == '127.0.0.1'
        assert self.scp.info['acceptor']['ae_title'] == b'PYNETDICOM      '
        assert self.scp.info['parameters']['message_id'] == 1
        assert self.scp.info['parameters']['priority'] == 2

        self.scp.stop()
