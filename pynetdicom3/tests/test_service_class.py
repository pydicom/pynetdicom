"""Tests for the service_class module."""

import pytest

from pydicom.dataset import Dataset

from pynetdicom3 import build_context
from pynetdicom3.dimse_primitives import C_STORE
from pynetdicom3.service_class import (
    StorageServiceClass,
    ServiceClass
)


class TestServiceClass(object):
    def test_is_valid_status(self):
        """Test that is_valid_status returns correct values"""
        sop = StorageServiceClass()
        assert not sop.is_valid_status(0x0101)
        assert sop.is_valid_status(0x0000)

    def test_validate_status_ds(self):
        """Test that validate_status works correctly with dataset"""
        sop = StorageServiceClass()
        rsp = C_STORE()
        status = Dataset()
        status.Status = 0x0001
        rsp = sop.validate_status(status, rsp)
        assert rsp.Status == 0x0001

    def test_validate_status_ds_multi(self):
        """Test that validate_status works correctly with dataset multi"""
        sop = StorageServiceClass()
        rsp = C_STORE()
        status = Dataset()
        status.Status = 0x0002
        status.ErrorComment = 'test'
        rsp = sop.validate_status(status, rsp)
        assert rsp.Status == 0x0002
        assert rsp.ErrorComment == 'test'

    def test_validate_status_ds_none(self):
        """Test correct status returned if ds has no Status element."""
        sop = StorageServiceClass()
        rsp = C_STORE()
        status = Dataset()
        status.ErrorComment = 'Test comment'
        rsp = sop.validate_status(status, rsp)
        assert rsp.Status == 0xC001

    def test_validate_status_ds_unknown(self):
        """Test a status ds with an unknown element."""
        sop = StorageServiceClass()
        rsp = C_STORE()
        status = Dataset()
        status.Status = 0x0000
        status.PatientName = 'Test comment'
        rsp = sop.validate_status(status, rsp)

    def test_validate_status_int(self):
        """Test that validate_status works correctly with int"""
        sop = StorageServiceClass()
        rsp = C_STORE()
        rsp = sop.validate_status(0x0000, rsp)
        assert rsp.Status == 0x0000

    def test_validate_status_invalid(self):
        """Test exception raised if invalid status value"""
        sop = StorageServiceClass()
        rsp = C_STORE()
        rsp = sop.validate_status('test', rsp)
        assert rsp.Status == 0xC002

    def test_validate_status_unknown(self):
        """Test return unknown status"""
        sop = StorageServiceClass()
        rsp = C_STORE()
        rsp = sop.validate_status(0xD011, rsp)
        assert rsp.Status == 0xD011

    def test_scp_raises(self):
        """Test that ServiceClass.SCP raises exception"""
        service = ServiceClass()
        msg = (
            r"No service has been implemented for the SOP Class UID '1.2.3'"
        )
        with pytest.raises(NotImplementedError, match=msg):
            service.SCP(None, build_context('1.2.3'), None)
