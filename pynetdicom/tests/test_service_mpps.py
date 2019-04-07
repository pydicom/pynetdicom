"""Tests for Modality Performed Procedure Step."""

import logging
import os
import threading
import time

import pytest

from pydicom.dataset import Dataset

from pynetdicom import AE, evt, debug_logger
from pynetdicom.dimse_primitives import (
    N_GET, N_CREATE, N_EVENT_REPORT, N_SET
)
from pynetdicom.sop_class import (
    ModalityPerformedProcedureStepSOPClass,
    ModalityPerformedProcedureStepRetrieveSOPClass,
    ModalityPerformedProcedureStepNotificationSOPClass
)


#debug_logger()


class TestMPPSCreate(object):
    """Test the MPPS N-CREATE"""
    def setup(self):
        """Run prior to each test"""
        self.ae = None

        ds = Dataset()
        ds.PatientName = 'Test'
        ds.SOPClassUID = ModalityPerformedProcedureStepSOPClass
        ds.SOPInstanceUID = '1.2.3.4'
        self.ds = ds

    def teardown(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

    def test_scp_handler_return_dataset(self):
        """Test handler returning a Dataset status"""
        def handle(event):
            status = Dataset()
            status.Status = 0x0000
            return status, self.ds

        handlers = [(evt.EVT_N_CREATE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_create(
            self.ds,
            ModalityPerformedProcedureStepSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0x0000
        assert ds.PatientName == 'Test'
        assoc.release()
        scp.shutdown()

    def test_scp_handler_return_dataset_multi(self):
        """Test handler returning a Dataset status with other elements"""
        def handle(event):
            status = Dataset()
            status.Status = 0x0001
            status.ErrorComment = 'Test'
            status.OffendingElement = 0x00080010
            status.ErrorID = 12
            return status, self.ds

        handlers = [(evt.EVT_N_CREATE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_create(
            self.ds,
            ModalityPerformedProcedureStepSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0x0001
        assert status.ErrorComment == 'Test'
        assert status.ErrorID == 12
        assert 'OffendingElement' not in status
        assert ds.PatientName == 'Test'
        assoc.release()
        scp.shutdown()

    def test_scp_handler_return_int(self):
        """Test handler returning an int status"""
        def handle(event):
            return 0x0000, self.ds

        handlers = [(evt.EVT_N_CREATE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_create(
            self.ds,
            ModalityPerformedProcedureStepSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0x0000
        assert not 'ErrorComment' in status
        assoc.release()
        scp.shutdown()

    def test_scp_handler_return_unknown(self):
        """Test handler returning a unknown status"""
        def handle(event):
            return 0xFFF0, self.ds

        handlers = [(evt.EVT_N_CREATE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_create(
            self.ds,
            ModalityPerformedProcedureStepSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0xFFF0
        assert ds is None
        assoc.release()
        scp.shutdown()

    def test_scp_handler_no_status(self):
        """Test handler not returning a status"""
        def handle(event):
            return None, self.ds

        handlers = [(evt.EVT_N_CREATE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_create(
            self.ds,
            ModalityPerformedProcedureStepSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0xC002
        assert ds is None
        assoc.release()
        scp.shutdown()

    def test_scp_handler_exception(self):
        """Test handler raising an exception"""
        def handle(event):
            raise ValueError
            return 0xFFF0, self.ds

        handlers = [(evt.EVT_N_CREATE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_create(
            self.ds,
            ModalityPerformedProcedureStepSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0x0110
        assert ds is None
        assoc.release()
        scp.shutdown()

    def test_scp_handler_context(self):
        """Test handler event's context parameter"""
        attrs = {}
        def handle(event):
            attrs['context'] = event.context
            attrs['assoc'] = event.assoc
            attrs['request'] = event.request
            return 0x0000, self.ds

        handlers = [(evt.EVT_N_CREATE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_create(
            self.ds,
            ModalityPerformedProcedureStepSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0x0000
        assert 'PatientName' in ds
        assoc.release()
        assert assoc.is_released

        cx = attrs['context']
        assert cx.context_id == 1
        assert cx.abstract_syntax == ModalityPerformedProcedureStepSOPClass
        assert cx.transfer_syntax == '1.2.840.10008.1.2'

        scp.shutdown()

    def test_scp_handler_request(self):
        """Test handler event's request parameter"""
        attrs = {}
        def handle(event):
            attrs['context'] = event.context
            attrs['assoc'] = event.assoc
            attrs['request'] = event.request
            return 0x0000, self.ds

        handlers = [(evt.EVT_N_CREATE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_create(
            self.ds,
            ModalityPerformedProcedureStepSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0x0000
        assert 'PatientName' in ds
        assoc.release()
        assert assoc.is_released

        req = attrs['request']
        assert isinstance(req, N_CREATE)
        assert req.AffectedSOPInstanceUID == '1.2.3.4'

        scp.shutdown()

    def test_scp_handler_assoc(self):
        """Test handler context parameter"""
        attrs = {}
        def handle(event):
            attrs['context'] = event.context
            attrs['assoc'] = event.assoc
            attrs['request'] = event.request
            return 0x0000, self.ds

        handlers = [(evt.EVT_N_CREATE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_create(
            self.ds,
            ModalityPerformedProcedureStepSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0x0000
        assert 'PatientName' in ds

        scp_assoc = attrs['assoc']
        assert scp_assoc == scp.active_associations[0]

        assoc.release()
        assert assoc.is_released

        scp.shutdown()


class TestMPPSSet(object):
    """Test the MPPS N-SET"""
    def setup(self):
        """Run prior to each test"""
        self.ae = None

        ds = Dataset()
        ds.PatientName = 'Test'
        ds.SOPClassUID = ModalityPerformedProcedureStepSOPClass
        ds.SOPInstanceUID = '1.2.3.4'
        self.ds = ds

    def teardown(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

    def test_scp_handler_return_dataset(self):
        """Test handler returning a Dataset status"""
        def handle(event):
            status = Dataset()
            status.Status = 0x0000
            return status, self.ds

        handlers = [(evt.EVT_N_SET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_set(
            self.ds,
            ModalityPerformedProcedureStepSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0x0000
        assert ds.PatientName == 'Test'
        assoc.release()
        scp.shutdown()

    def test_scp_handler_return_dataset_multi(self):
        """Test handler returning a Dataset status with other elements"""
        def handle(event):
            status = Dataset()
            status.Status = 0x0001
            status.ErrorComment = 'Test'
            status.OffendingElement = 0x00080010
            status.ErrorID = 12
            return status, self.ds

        handlers = [(evt.EVT_N_SET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_set(
            self.ds,
            ModalityPerformedProcedureStepSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0x0001
        assert status.ErrorComment == 'Test'
        assert status.ErrorID == 12
        assert 'OffendingElement' not in status
        assert ds.PatientName == 'Test'
        assoc.release()
        scp.shutdown()

    def test_scp_handler_return_int(self):
        """Test handler returning an int status"""
        def handle(event):
            return 0x0000, self.ds

        handlers = [(evt.EVT_N_SET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_set(
            self.ds,
            ModalityPerformedProcedureStepSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0x0000
        assert not 'ErrorComment' in status
        assoc.release()
        scp.shutdown()

    def test_scp_handler_return_unknown(self):
        """Test handler returning a unknown status"""
        def handle(event):
            return 0xFFF0, self.ds

        handlers = [(evt.EVT_N_SET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_set(
            self.ds,
            ModalityPerformedProcedureStepSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0xFFF0
        assert ds is None
        assoc.release()
        scp.shutdown()

    def test_scp_handler_no_status(self):
        """Test handler not returning a status"""
        def handle(event):
            return None, self.ds

        handlers = [(evt.EVT_N_SET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_set(
            self.ds,
            ModalityPerformedProcedureStepSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0xC002
        assert ds is None
        assoc.release()
        scp.shutdown()

    def test_scp_handler_exception(self):
        """Test handler raising an exception"""
        def handle(event):
            raise ValueError
            return 0xFFF0, self.ds

        handlers = [(evt.EVT_N_SET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_set(
            self.ds,
            ModalityPerformedProcedureStepSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0x0110
        assert ds is None
        assoc.release()
        scp.shutdown()

    def test_scp_handler_context(self):
        """Test handler event's context parameter"""
        attrs = {}
        def handle(event):
            attrs['context'] = event.context
            attrs['assoc'] = event.assoc
            attrs['request'] = event.request
            return 0x0000, self.ds

        handlers = [(evt.EVT_N_SET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_set(
            self.ds,
            ModalityPerformedProcedureStepSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0x0000
        assert 'PatientName' in ds
        assoc.release()
        assert assoc.is_released

        cx = attrs['context']
        assert cx.context_id == 1
        assert cx.abstract_syntax == ModalityPerformedProcedureStepSOPClass
        assert cx.transfer_syntax == '1.2.840.10008.1.2'

        scp.shutdown()

    def test_scp_handler_request(self):
        """Test handler event's request parameter"""
        attrs = {}
        def handle(event):
            attrs['context'] = event.context
            attrs['assoc'] = event.assoc
            attrs['request'] = event.request
            return 0x0000, self.ds

        handlers = [(evt.EVT_N_SET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_set(
            self.ds,
            ModalityPerformedProcedureStepSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0x0000
        assert 'PatientName' in ds
        assoc.release()
        assert assoc.is_released

        req = attrs['request']
        assert isinstance(req, N_SET)
        assert req.RequestedSOPInstanceUID == '1.2.3.4'

        scp.shutdown()

    def test_scp_handler_assoc(self):
        """Test handler context parameter"""
        attrs = {}
        def handle(event):
            attrs['context'] = event.context
            attrs['assoc'] = event.assoc
            attrs['request'] = event.request
            return 0x0000, self.ds

        handlers = [(evt.EVT_N_SET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_set(
            self.ds,
            ModalityPerformedProcedureStepSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0x0000
        assert 'PatientName' in ds

        scp_assoc = attrs['assoc']
        assert scp_assoc == scp.active_associations[0]

        assoc.release()
        assert assoc.is_released

        scp.shutdown()


class TestMPPSGet(object):
    """Test the MPPS N-GET"""
    def setup(self):
        """Run prior to each test"""
        self.ae = None

        self.tag_list = [0x00100010, 0x00100020]

        ds = Dataset()
        ds.PatientName = 'Test'
        ds.SOPClassUID = ModalityPerformedProcedureStepSOPClass
        ds.SOPInstanceUID = '1.2.3.4'
        self.ds = ds

    def teardown(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

    def test_scp_handler_return_dataset(self):
        """Test handler returning a Dataset status"""
        def handle(event):
            status = Dataset()
            status.Status = 0x0000
            return status, self.ds

        handlers = [(evt.EVT_N_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepRetrieveSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepRetrieveSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get(
            self.tag_list,
            ModalityPerformedProcedureStepRetrieveSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0x0000
        assert ds.PatientName == 'Test'
        assoc.release()
        scp.shutdown()

    def test_scp_handler_return_dataset_multi(self):
        """Test handler returning a Dataset status with other elements"""
        def handle(event):
            status = Dataset()
            status.Status = 0x0001
            status.ErrorComment = 'Test'
            status.OffendingElement = 0x00080010
            status.ErrorID = 12
            return status, self.ds

        handlers = [(evt.EVT_N_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepRetrieveSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepRetrieveSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get(
            self.tag_list,
            ModalityPerformedProcedureStepRetrieveSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0x0001
        assert status.ErrorComment == 'Test'
        assert status.ErrorID == 12
        assert 'OffendingElement' not in status
        assert ds.PatientName == 'Test'
        assoc.release()
        scp.shutdown()

    def test_scp_handler_return_int(self):
        """Test handler returning an int status"""
        def handle(event):
            return 0x0000, self.ds

        handlers = [(evt.EVT_N_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepRetrieveSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepRetrieveSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get(
            self.tag_list,
            ModalityPerformedProcedureStepRetrieveSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0x0000
        assert not 'ErrorComment' in status
        assoc.release()
        scp.shutdown()

    def test_scp_handler_return_unknown(self):
        """Test handler returning a unknown status"""
        def handle(event):
            return 0xFFF0, self.ds

        handlers = [(evt.EVT_N_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepRetrieveSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepRetrieveSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get(
            self.tag_list,
            ModalityPerformedProcedureStepRetrieveSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0xFFF0
        assert ds is None
        assoc.release()
        scp.shutdown()

    def test_scp_handler_no_status(self):
        """Test handler not returning a status"""
        def handle(event):
            return None, self.ds

        handlers = [(evt.EVT_N_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepRetrieveSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepRetrieveSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get(
            self.tag_list,
            ModalityPerformedProcedureStepRetrieveSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0xC002
        assert ds is None
        assoc.release()
        scp.shutdown()

    def test_scp_handler_exception(self):
        """Test handler raising an exception"""
        def handle(event):
            raise ValueError
            return 0xFFF0, self.ds

        handlers = [(evt.EVT_N_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepRetrieveSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepRetrieveSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get(
            self.tag_list,
            ModalityPerformedProcedureStepRetrieveSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0x0110
        assert ds is None
        assoc.release()
        scp.shutdown()

    def test_scp_handler_context(self):
        """Test handler event's context parameter"""
        attrs = {}
        def handle(event):
            attrs['context'] = event.context
            attrs['assoc'] = event.assoc
            attrs['request'] = event.request
            return 0x0000, self.ds

        handlers = [(evt.EVT_N_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepRetrieveSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepRetrieveSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get(
            self.tag_list,
            ModalityPerformedProcedureStepRetrieveSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0x0000
        assert 'PatientName' in ds
        assoc.release()
        assert assoc.is_released

        cx = attrs['context']
        assert cx.context_id == 1
        assert cx.abstract_syntax == ModalityPerformedProcedureStepRetrieveSOPClass
        assert cx.transfer_syntax == '1.2.840.10008.1.2'

        scp.shutdown()

    def test_scp_handler_request(self):
        """Test handler event's request parameter"""
        attrs = {}
        def handle(event):
            attrs['context'] = event.context
            attrs['assoc'] = event.assoc
            attrs['request'] = event.request
            return 0x0000, self.ds

        handlers = [(evt.EVT_N_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepRetrieveSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepRetrieveSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get(
            self.tag_list,
            ModalityPerformedProcedureStepRetrieveSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0x0000
        assert 'PatientName' in ds
        assoc.release()
        assert assoc.is_released

        req = attrs['request']
        assert isinstance(req, N_GET)
        assert req.RequestedSOPInstanceUID == '1.2.3.4'

        scp.shutdown()

    def test_scp_handler_assoc(self):
        """Test handler context parameter"""
        attrs = {}
        def handle(event):
            attrs['context'] = event.context
            attrs['assoc'] = event.assoc
            attrs['request'] = event.request
            return 0x0000, self.ds

        handlers = [(evt.EVT_N_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepRetrieveSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepRetrieveSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get(
            self.tag_list,
            ModalityPerformedProcedureStepRetrieveSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0x0000
        assert 'PatientName' in ds

        scp_assoc = attrs['assoc']
        assert scp_assoc == scp.active_associations[0]

        assoc.release()
        assert assoc.is_released

        scp.shutdown()


class TestMPPSEventReport(object):
    """Test the MPPS N-EVENT-REPORT"""
    def setup(self):
        """Run prior to each test"""
        self.ae = None

        ds = Dataset()
        ds.PatientName = 'Test'
        ds.SOPClassUID = ModalityPerformedProcedureStepSOPClass
        ds.SOPInstanceUID = '1.2.3.4'
        self.ds = ds

    def teardown(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

    def test_scp_handler_return_dataset(self):
        """Test handler returning a Dataset status"""
        def handle(event):
            status = Dataset()
            status.Status = 0x0000
            return status, self.ds

        handlers = [(evt.EVT_N_EVENT_REPORT, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepNotificationSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepNotificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_event_report(
            self.ds,
            1,
            ModalityPerformedProcedureStepNotificationSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0x0000
        assert ds.PatientName == 'Test'
        assoc.release()
        scp.shutdown()

    def test_scp_handler_return_dataset_multi(self):
        """Test handler returning a Dataset status with other elements"""
        def handle(event):
            status = Dataset()
            status.Status = 0x0001
            status.ErrorComment = 'Test'
            status.OffendingElement = 0x00080010
            status.ErrorID = 12
            return status, self.ds

        handlers = [(evt.EVT_N_EVENT_REPORT, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepNotificationSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepNotificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_event_report(
            self.ds,
            1,
            ModalityPerformedProcedureStepNotificationSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0x0001
        assert status.ErrorComment == 'Test'
        assert status.ErrorID == 12
        assert 'OffendingElement' not in status
        assert ds.PatientName == 'Test'
        assoc.release()
        scp.shutdown()

    def test_scp_handler_return_int(self):
        """Test handler returning an int status"""
        def handle(event):
            return 0x0000, self.ds

        handlers = [(evt.EVT_N_EVENT_REPORT, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepNotificationSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepNotificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_event_report(
            self.ds,
            1,
            ModalityPerformedProcedureStepNotificationSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0x0000
        assert not 'ErrorComment' in status
        assoc.release()
        scp.shutdown()

    def test_scp_handler_return_unknown(self):
        """Test handler returning a unknown status"""
        def handle(event):
            return 0xFFF0, self.ds

        handlers = [(evt.EVT_N_EVENT_REPORT, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepNotificationSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepNotificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_event_report(
            self.ds,
            1,
            ModalityPerformedProcedureStepNotificationSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0xFFF0
        assert ds is None
        assoc.release()
        scp.shutdown()

    def test_scp_handler_no_status(self):
        """Test handler not returning a status"""
        def handle(event):
            return None, self.ds

        handlers = [(evt.EVT_N_EVENT_REPORT, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepNotificationSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepNotificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_event_report(
            self.ds,
            1,
            ModalityPerformedProcedureStepNotificationSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0xC002
        assert ds is None
        assoc.release()
        scp.shutdown()

    def test_scp_handler_exception(self):
        """Test handler raising an exception"""
        def handle(event):
            raise ValueError
            return 0xFFF0, self.ds

        handlers = [(evt.EVT_N_EVENT_REPORT, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepNotificationSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepNotificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_event_report(
            self.ds,
            1,
            ModalityPerformedProcedureStepNotificationSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0x0110
        assert ds is None
        assoc.release()
        scp.shutdown()

    def test_scp_handler_context(self):
        """Test handler event's context parameter"""
        attrs = {}
        def handle(event):
            attrs['context'] = event.context
            attrs['assoc'] = event.assoc
            attrs['request'] = event.request
            return 0x0000, self.ds

        handlers = [(evt.EVT_N_EVENT_REPORT, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepNotificationSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepNotificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_event_report(
            self.ds,
            1,
            ModalityPerformedProcedureStepNotificationSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0x0000
        assert 'PatientName' in ds
        assoc.release()
        assert assoc.is_released

        cx = attrs['context']
        assert cx.context_id == 1
        assert cx.abstract_syntax == ModalityPerformedProcedureStepNotificationSOPClass
        assert cx.transfer_syntax == '1.2.840.10008.1.2'

        scp.shutdown()

    def test_scp_handler_request(self):
        """Test handler event's request parameter"""
        attrs = {}
        def handle(event):
            attrs['context'] = event.context
            attrs['assoc'] = event.assoc
            attrs['request'] = event.request
            return 0x0000, self.ds

        handlers = [(evt.EVT_N_EVENT_REPORT, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepNotificationSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepNotificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_event_report(
            self.ds,
            1,
            ModalityPerformedProcedureStepNotificationSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0x0000
        assert 'PatientName' in ds
        assoc.release()
        assert assoc.is_released

        req = attrs['request']
        assert isinstance(req, N_EVENT_REPORT)
        assert req.AffectedSOPInstanceUID == '1.2.3.4'

        scp.shutdown()

    def test_scp_handler_assoc(self):
        """Test handler context parameter"""
        attrs = {}
        def handle(event):
            attrs['context'] = event.context
            attrs['assoc'] = event.assoc
            attrs['request'] = event.request
            return 0x0000, self.ds

        handlers = [(evt.EVT_N_EVENT_REPORT, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepNotificationSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepNotificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_event_report(
            self.ds,
            1,
            ModalityPerformedProcedureStepNotificationSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0x0000
        assert 'PatientName' in ds

        scp_assoc = attrs['assoc']
        assert scp_assoc == scp.active_associations[0]

        assoc.release()
        assert assoc.is_released

        scp.shutdown()


class TestMPPS(object):
    """Functional tests for MPPS"""
    def setup(self):
        """Run prior to each test"""
        self.ae = None

        self.tag_list = [0x00100010, 0x00100020]

        ds = Dataset()
        ds.PatientName = 'Test'
        ds.SOPClassUID = ModalityPerformedProcedureStepSOPClass
        ds.SOPInstanceUID = '1.2.3.4'
        self.ds = ds

    def teardown(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

    def test_unknown_msg(self):
        """Test exception raised if not valid DIMSE primitive."""
        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        scp = ae.start_server(('', 11112), block=False)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_action(
            self.ds,
            1,
            ModalityPerformedProcedureStepSOPClass,
            '1.2.3.4'
        )
        assert assoc.is_aborted

        scp.shutdown()

    def test_functional_create(self):
        """Test functionality with basic operation."""
        managed_instances = {}

        def handle_create(event):
            ds = event.attribute_list
            managed_instances[ds.SOPInstanceUID] = ds
            return 0x0000, ds

        def handle_set(event):
            ds = event.modification_list
            managed_instances[ds.SOPInstanceUID].update(ds)
            return 0x0000, ds

        handlers = [(evt.EVT_N_CREATE, handle_create),
                    (evt.EVT_N_SET, handle_set)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_create(
            self.ds,
            ModalityPerformedProcedureStepSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0x0000
        assert ds.PatientName == 'Test'
        assoc.release()

        assert '1.2.3.4' in managed_instances
        mpps = managed_instances['1.2.3.4']
        assert mpps.PatientName == 'Test'

        scp.shutdown()

    def test_functional_create_no_instance(self):
        """Test functionality without Instance UID."""
        managed_instances = {}

        def handle_create(event):
            ds = event.attribute_list
            ds.SOPInstanceUID = '1.2.3.4.5'
            managed_instances[ds.SOPInstanceUID] = ds
            return 0x0000, ds

        def handle_set(event):
            ds = event.modification_list
            managed_instances[ds.SOPInstanceUID].update(ds)
            return 0x0000, ds

        handlers = [(evt.EVT_N_CREATE, handle_create),
                    (evt.EVT_N_SET, handle_set)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        del self.ds.SOPInstanceUID
        status, ds = assoc.send_n_create(
            self.ds,
            ModalityPerformedProcedureStepSOPClass,
        )
        assert status.Status == 0x0000
        assert ds.PatientName == 'Test'
        assert ds.SOPInstanceUID == '1.2.3.4.5'
        assoc.release()

        assert '1.2.3.4.5' in managed_instances
        mpps = managed_instances['1.2.3.4.5']
        assert mpps.PatientName == 'Test'

        scp.shutdown()

    def test_functional_create_fail(self):
        """Test receiving a failed status from handler."""
        managed_instances = {}

        def handle_create(event):
            return 0x0110, None

        def handle_set(event):
            ds = event.modification_list
            managed_instances[ds.SOPInstanceUID].update(ds)
            return 0x0000, ds

        handlers = [(evt.EVT_N_CREATE, handle_create),
                    (evt.EVT_N_SET, handle_set)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        del self.ds.SOPInstanceUID
        status, ds = assoc.send_n_create(
            self.ds,
            ModalityPerformedProcedureStepSOPClass,
        )
        assert status.Status == 0x0110
        assert ds is None
        assoc.release()

        assert managed_instances == {}

        scp.shutdown()

    def test_functional_set_success(self):
        """Test setting."""
        managed_instances = {}

        def handle_create(event):
            ds = event.attribute_list
            ds.SOPInstanceUID = '1.2.3.4.5'
            managed_instances[ds.SOPInstanceUID] = ds
            return 0x0000, ds

        def handle_set(event):
            ds = event.modification_list
            instance_uid = event.request.RequestedSOPInstanceUID
            managed_instances[instance_uid].update(ds)
            return 0x0000, managed_instances[instance_uid]

        handlers = [(evt.EVT_N_CREATE, handle_create),
                    (evt.EVT_N_SET, handle_set)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        del self.ds.SOPInstanceUID
        status, ds = assoc.send_n_create(
            self.ds,
            ModalityPerformedProcedureStepSOPClass,
        )
        assert status.Status == 0x0000
        assert ds.PatientName == 'Test'
        assert ds.SOPInstanceUID == '1.2.3.4.5'
        assoc.release()

        assert '1.2.3.4.5' in managed_instances
        mpps = managed_instances['1.2.3.4.5']
        assert mpps.PatientName == 'Test'

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        set_ds = Dataset()
        set_ds.PatientName = 'Test^Test'
        status, ds = assoc.send_n_set(
            set_ds,
            ModalityPerformedProcedureStepSOPClass,
            '1.2.3.4.5'
        )

        assert status.Status == 0x0000
        assert ds.PatientName == 'Test^Test'
        assert ds.SOPInstanceUID == '1.2.3.4.5'
        assoc.release()

        assert '1.2.3.4.5' in managed_instances
        mpps = managed_instances['1.2.3.4.5']
        assert mpps.PatientName == 'Test^Test'

        scp.shutdown()

    def test_functional_set_fail(self):
        """Test trying to set with no matching instance."""
        managed_instances = {}

        def handle_create(event):
            ds = event.attribute_list
            ds.SOPInstanceUID = '1.2.3.4.5'
            managed_instances[ds.SOPInstanceUID] = ds
            return 0x0000, ds

        def handle_set(event):
            return 0x0110, None

        handlers = [(evt.EVT_N_CREATE, handle_create),
                    (evt.EVT_N_SET, handle_set)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        del self.ds.SOPInstanceUID
        status, ds = assoc.send_n_create(
            self.ds,
            ModalityPerformedProcedureStepSOPClass,
        )
        assert status.Status == 0x0000
        assert ds.PatientName == 'Test'
        assert ds.SOPInstanceUID == '1.2.3.4.5'
        assoc.release()

        assert '1.2.3.4.5' in managed_instances
        mpps = managed_instances['1.2.3.4.5']
        assert mpps.PatientName == 'Test'

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        set_ds = Dataset()
        set_ds.PatientName = 'Test^Test'
        status, ds = assoc.send_n_set(
            set_ds,
            ModalityPerformedProcedureStepSOPClass,
            '1.2.3.4.5'
        )

        assert status.Status == 0x0110
        assert ds is None
        assoc.release()

        assert '1.2.3.4.5' in managed_instances
        mpps = managed_instances['1.2.3.4.5']
        assert mpps.PatientName == 'Test'

        scp.shutdown()

    def test_functional_get_success(self):
        """Test getting."""
        managed_instances = {self.ds.SOPInstanceUID : self.ds}

        def handle_get(event):
            instance_uid = event.request.RequestedSOPInstanceUID
            return 0x0000, managed_instances[instance_uid]

        handlers = [(evt.EVT_N_GET, handle_get)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepRetrieveSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepRetrieveSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get(
            [0x00100010, 0x00100020],
            ModalityPerformedProcedureStepRetrieveSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0x0000
        assert ds.PatientName == 'Test'
        assert ds.SOPInstanceUID == '1.2.3.4'
        assoc.release()

        scp.shutdown()

    def test_functional_get_no_attr_list(self):
        """Test getting without attribute information list."""
        managed_instances = {self.ds.SOPInstanceUID : self.ds}

        def handle_get(event):
            instance_uid = event.request.RequestedSOPInstanceUID
            return 0x0000, managed_instances[instance_uid]

        handlers = [(evt.EVT_N_GET, handle_get)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepRetrieveSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepRetrieveSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get(
            [],
            ModalityPerformedProcedureStepRetrieveSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0x0000
        assert ds.PatientName == 'Test'
        assert ds.SOPInstanceUID == '1.2.3.4'
        assoc.release()

        scp.shutdown()

    def test_functional_get_fail(self):
        """Test failing to get."""
        managed_instances = {self.ds.SOPInstanceUID : self.ds}

        def handle_get(event):
            instance_uid = event.request.RequestedSOPInstanceUID
            return 0x0110, managed_instances[instance_uid]

        handlers = [(evt.EVT_N_GET, handle_get)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepRetrieveSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepRetrieveSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get(
            [],
            ModalityPerformedProcedureStepRetrieveSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0x0110
        assert ds is None
        assoc.release()

        scp.shutdown()

    def test_functional_report_success(self):
        """Test event report with Event Information."""
        managed_instances = {self.ds.SOPInstanceUID : self.ds}

        def handle_er(event):
            instance_uid = event.request.AffectedSOPInstanceUID
            return 0x0000, managed_instances[instance_uid]

        handlers = [(evt.EVT_N_EVENT_REPORT, handle_er)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepNotificationSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepNotificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_event_report(
            self.ds,
            1,
            ModalityPerformedProcedureStepNotificationSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0x0000
        assert ds.PatientName == 'Test'
        assert ds.SOPInstanceUID == '1.2.3.4'
        assoc.release()

        scp.shutdown()

    def test_functional_report_no_event_info(self):
        """Test event report without Event Information."""
        managed_instances = {self.ds.SOPInstanceUID : self.ds}

        def handle_er(event):
            instance_uid = event.request.AffectedSOPInstanceUID
            return 0x0000, managed_instances[instance_uid]

        handlers = [(evt.EVT_N_EVENT_REPORT, handle_er)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepNotificationSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepNotificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_event_report(
            None,
            1,
            ModalityPerformedProcedureStepNotificationSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0x0000
        assert ds.PatientName == 'Test'
        assert ds.SOPInstanceUID == '1.2.3.4'
        assoc.release()

        scp.shutdown()

    def test_functional_report_fail(self):
        """Test trying to set with no matching instance."""
        managed_instances = {self.ds.SOPInstanceUID : self.ds}

        def handle_er(event):
            instance_uid = event.request.AffectedSOPInstanceUID
            return 0x0110, managed_instances[instance_uid]

        handlers = [(evt.EVT_N_EVENT_REPORT, handle_er)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityPerformedProcedureStepNotificationSOPClass)
        ae.add_requested_context(ModalityPerformedProcedureStepNotificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_event_report(
            None,
            1,
            ModalityPerformedProcedureStepNotificationSOPClass,
            '1.2.3.4'
        )
        assert status.Status == 0x0110
        assert ds is None
        assoc.release()

        scp.shutdown()
