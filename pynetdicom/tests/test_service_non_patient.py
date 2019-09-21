"""Tests for the NonPatientObjectStorageServiceClass."""

from io import BytesIO
import logging
import os
import threading
import time

import pytest

from pydicom import dcmread
from pydicom.dataset import Dataset
from pydicom.uid import ExplicitVRLittleEndian

from pynetdicom import AE, evt, debug_logger
from pynetdicom.dimse_primitives import C_STORE
from pynetdicom.sop_class import (
    NonPatientObjectStorageServiceClass,
    HangingProtocolStorage,
)
from .dummy_c_scp import (
    DummyBaseSCP,
    DummyStorageSCP
)

#debug_logger()

TEST_DS_DIR = os.path.join(os.path.dirname(__file__), 'dicom_files')
DATASET = dcmread(os.path.join(TEST_DS_DIR, 'CTImageStorage.dcm'))
DATASET.SOPClassUID = HangingProtocolStorage


class TestNonPatientObjectStorageServiceClass(object):
    """Test the NonPatientObjectStorageServiceClass.

    Subclass of StorageServiceClass with its own set of statuses.
    """
    def setup(self):
        """Run prior to each test"""
        self.ae = None

    def teardown(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

    def test_scp_failed_ds_decode(self):
        """Test failure to decode the dataset"""
        # Hard to test directly as decode errors won't show up until the
        #   dataset is actually used
        def handle(event):
            try:
                for elem in event.dataset.iterall():
                    pass
            except:
                status = Dataset()
                status.Status = 0xC210
                status.ErrorComment = "Unable to decode the dataset"
                return status

            return 0x0000

        handlers = [(evt.EVT_C_STORE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(HangingProtocolStorage)
        ae.add_requested_context(HangingProtocolStorage, ExplicitVRLittleEndian)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        req = C_STORE()
        req.MessageID = 1
        req.AffectedSOPClassUID = DATASET.SOPClassUID
        req.AffectedSOPInstanceUID = DATASET.SOPInstanceUID
        req.Priorty = 0x0002
        # Bad VR? AA
        req.DataSet = BytesIO(b'\x08\x00\x01\x00\x40\x40\x00\x00\x00\x00\x00\x08\x00\x49')

        # Send C-STORE request to DIMSE and get response
        # Need to manually hit the checkpoint
        assoc._reactor_checkpoint.clear()
        assoc.dimse.send_msg(req, 1)
        cx_id, rsp = assoc.dimse.get_msg(True)
        assoc._reactor_checkpoint.set()

        assert rsp.Status == 0xC210
        assert rsp.ErrorComment == 'Unable to decode the dataset'
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_scp_handler_return_dataset(self):
        """Test handler returning a Dataset status"""
        def handle(event):
            status = Dataset()
            status.Status = 0x0001
            return status

        handlers = [(evt.EVT_C_STORE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(HangingProtocolStorage)
        ae.add_requested_context(HangingProtocolStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_store(DATASET)
        assert rsp.Status == 0x0001
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_scp_handler_return_dataset_multi(self):
        """Test handler returning a Dataset status with other elements"""
        def handle(event):
            status = Dataset()
            status.Status = 0x0001
            status.ErrorComment = 'Test'
            status.OffendingElement = 0x00080010
            return status

        handlers = [(evt.EVT_C_STORE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(HangingProtocolStorage)
        ae.add_requested_context(HangingProtocolStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_store(DATASET)
        assert rsp.Status == 0x0001
        assert rsp.ErrorComment == 'Test'
        assert rsp.OffendingElement == 0x00080010
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_scp_handler_return_int(self):
        """Test handler returning an int status"""
        def handle(event):
            return 0x0000

        handlers = [(evt.EVT_C_STORE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(HangingProtocolStorage)
        ae.add_requested_context(HangingProtocolStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_store(DATASET)
        assert rsp.Status == 0x0000
        assert not 'ErrorComment' in rsp
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_scp_handler_return_invalid(self):
        """Test handler returning an invalid status"""
        def handle(event):
            return 0xFFF0

        handlers = [(evt.EVT_C_STORE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(HangingProtocolStorage)
        ae.add_requested_context(HangingProtocolStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_store(DATASET)
        assert rsp.Status == 0xFFF0
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_scp_handler_no_status(self):
        """Test handler not returning a status"""
        def handle(event):
            return None

        handlers = [(evt.EVT_C_STORE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(HangingProtocolStorage)
        ae.add_requested_context(HangingProtocolStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_store(DATASET)
        assert rsp.Status == 0xC002
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_scp_handler_exception(self):
        """Test handler raising an exception"""
        def handle(event):
            raise ValueError

        handlers = [(evt.EVT_C_STORE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(HangingProtocolStorage)
        ae.add_requested_context(HangingProtocolStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_store(DATASET)
        assert rsp.Status == 0xC211
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
            attrs['dataset'] = event.dataset
            return 0x0000

        handlers = [(evt.EVT_C_STORE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(HangingProtocolStorage)
        ae.add_requested_context(HangingProtocolStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status = assoc.send_c_store(DATASET)
        assert status.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        cx = attrs['context']
        assert cx.context_id == 1
        assert cx.abstract_syntax == HangingProtocolStorage
        assert cx.transfer_syntax == '1.2.840.10008.1.2'

        scp.shutdown()

    def test_scp_handler_assoc(self):
        """Test handler event's assoc attribute"""
        attrs = {}
        def handle(event):
            attrs['context'] = event.context
            attrs['assoc'] = event.assoc
            attrs['request'] = event.request
            attrs['dataset'] = event.dataset
            return 0x0000

        handlers = [(evt.EVT_C_STORE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(HangingProtocolStorage)
        ae.add_requested_context(HangingProtocolStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status = assoc.send_c_store(DATASET)
        assert status.Status == 0x0000

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
            attrs['dataset'] = event.dataset
            return 0x0000

        handlers = [(evt.EVT_C_STORE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(HangingProtocolStorage)
        ae.add_requested_context(HangingProtocolStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status = assoc.send_c_store(DATASET)
        assert status.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        req = attrs['request']
        assert req.MessageID == 1
        assert isinstance(req, C_STORE)

        scp.shutdown()

    def test_scp_handler_dataset(self):
        """Test handler event's dataset property"""
        attrs = {}
        def handle(event):
            attrs['context'] = event.context
            attrs['assoc'] = event.assoc
            attrs['request'] = event.request
            attrs['dataset'] = event.dataset
            return 0x0000

        handlers = [(evt.EVT_C_STORE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(HangingProtocolStorage)
        ae.add_requested_context(HangingProtocolStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status = assoc.send_c_store(DATASET)
        assert status.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        ds = attrs['dataset']
        assert isinstance(ds, Dataset)
        assert ds.PatientName == DATASET.PatientName

        scp.shutdown()

    def test_scp_handler_move_origin(self):
        """Test handler event's request property with MoveOriginator"""
        attrs = {}
        def handle(event):
            attrs['context'] = event.context
            attrs['assoc'] = event.assoc
            attrs['request'] = event.request
            attrs['dataset'] = event.dataset
            return 0x0000

        handlers = [(evt.EVT_C_STORE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(HangingProtocolStorage)
        ae.add_requested_context(HangingProtocolStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status = assoc.send_c_store(
            DATASET, originator_aet=b'ORIGIN', originator_id=888
        )
        assert status.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        req = attrs['request']
        assert req.MoveOriginatorApplicationEntityTitle == b'ORIGIN'
        assert req.MoveOriginatorMessageID == 888

        scp.shutdown()
