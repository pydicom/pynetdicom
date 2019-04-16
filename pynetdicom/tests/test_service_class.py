"""Tests for the service_class module."""

try:
    import queue
except ImportError:
    import Queue as queue

import pytest

from pydicom.dataset import Dataset

from pynetdicom import build_context
from pynetdicom.dimse_primitives import C_STORE, C_GET, C_MOVE, C_CANCEL
from pynetdicom.service_class import (
    StorageServiceClass,
    ServiceClass
)


class DummyAssoc(object):
    def __init__(self):
        self.dimse = DummyDIMSE()


class DummyDIMSE(object):
    def __init__(self):
        self.msg_queue = queue.Queue()
        self.dimse_timeout = 0.5
        self.cancel_req = {}

    def get_msg(self, block=True):
        try:
            return self.msg_queue.get(block=block)
        except queue.Empty:
            return (None, None)

    def peek_msg(self):
        try:
            return self.msg_queue.queue[0]
        except (queue.Empty, IndexError):
            return (None, None)


class TestServiceClass(object):
    def test_is_valid_status(self):
        """Test that is_valid_status returns correct values"""
        sop = StorageServiceClass(None)
        assert not sop.is_valid_status(0x0101)
        assert sop.is_valid_status(0x0000)

    def test_validate_status_ds(self):
        """Test that validate_status works correctly with dataset"""
        sop = StorageServiceClass(None)
        rsp = C_STORE()
        status = Dataset()
        status.Status = 0x0001
        rsp = sop.validate_status(status, rsp)
        assert rsp.Status == 0x0001

    def test_validate_status_ds_multi(self):
        """Test that validate_status works correctly with dataset multi"""
        sop = StorageServiceClass(None)
        rsp = C_STORE()
        status = Dataset()
        status.Status = 0x0002
        status.ErrorComment = 'test'
        rsp = sop.validate_status(status, rsp)
        assert rsp.Status == 0x0002
        assert rsp.ErrorComment == 'test'

    def test_validate_status_ds_none(self):
        """Test correct status returned if ds has no Status element."""
        sop = StorageServiceClass(None)
        rsp = C_STORE()
        status = Dataset()
        status.ErrorComment = 'Test comment'
        rsp = sop.validate_status(status, rsp)
        assert rsp.Status == 0xC001

    def test_validate_status_ds_unknown(self):
        """Test a status ds with an unknown element."""
        sop = StorageServiceClass(None)
        rsp = C_STORE()
        status = Dataset()
        status.Status = 0x0000
        status.PatientName = 'Test comment'
        rsp = sop.validate_status(status, rsp)

    def test_validate_status_int(self):
        """Test that validate_status works correctly with int"""
        sop = StorageServiceClass(None)
        rsp = C_STORE()
        rsp = sop.validate_status(0x0000, rsp)
        assert rsp.Status == 0x0000

    def test_validate_status_invalid(self):
        """Test exception raised if invalid status value"""
        sop = StorageServiceClass(None)
        rsp = C_STORE()
        rsp = sop.validate_status('test', rsp)
        assert rsp.Status == 0xC002

    def test_validate_status_unknown(self):
        """Test return unknown status"""
        sop = StorageServiceClass(None)
        rsp = C_STORE()
        rsp = sop.validate_status(0xD011, rsp)
        assert rsp.Status == 0xD011

    def test_scp_raises(self):
        """Test that ServiceClass.SCP raises exception"""
        service = ServiceClass(None)
        msg = (
            r"No service class has been implemented for the "
            r"SOP Class UID '1.2.3'"
        )
        with pytest.raises(NotImplementedError, match=msg):
            service.SCP(None, build_context('1.2.3'))

    def test_is_cancelled_no_msg(self):
        """Test is_cancelled with no DIMSE messages in the queue."""
        assoc = DummyAssoc()
        service = ServiceClass(assoc)
        assert service.is_cancelled(1) is False
        assert service.is_cancelled(2) is False

    def test_is_cancelled_no_match(self):
        """Test is_cancelled with no matching C-CANCEL."""
        assoc = DummyAssoc()
        cancel = C_CANCEL()
        cancel.MessageIDBeingRespondedTo = 5
        assoc.dimse.cancel_req[5] = cancel
        assoc.dimse.cancel_req[3] = cancel
        service = ServiceClass(assoc)
        assert service.is_cancelled(1) is False
        assert service.is_cancelled(2) is False

    def test_is_cancelled_match(self):
        """Test is_cancelled with matching C-CANCEL."""
        assoc = DummyAssoc()
        cancel = C_CANCEL()
        cancel.MessageIDBeingRespondedTo = 5
        assoc.dimse.cancel_req[4] = C_GET()
        assoc.dimse.cancel_req[3] = cancel
        service = ServiceClass(assoc)
        assert service.is_cancelled(1) is False
        assert service.is_cancelled(2) is False
        assert service.is_cancelled(3) is True
        service = ServiceClass(assoc)
        assert service.is_cancelled(1) is False
        assert service.is_cancelled(2) is False
        assert service.is_cancelled(3) is False
        assert cancel not in assoc.dimse.cancel_req.values()
