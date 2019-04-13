"""Tests for the StorageServiceClass."""

from io import BytesIO
import logging
import os
import threading
import time

import pytest

from pydicom import dcmread
from pydicom.dataset import Dataset
from pydicom.uid import ExplicitVRLittleEndian

from pynetdicom import AE, evt
from pynetdicom.dimse_primitives import C_STORE
from pynetdicom.pdu_primitives import SOPClassExtendedNegotiation
from pynetdicom.sop_class import (
    VerificationServiceClass,
    VerificationSOPClass,
    StorageServiceClass,
    CTImageStorage,
)
from .dummy_c_scp import (
    DummyBaseSCP,
    DummyVerificationSCP,
    DummyStorageSCP
)

LOGGER = logging.getLogger('pynetdicom')
LOGGER.setLevel(logging.CRITICAL)
#LOGGER.setLevel(logging.DEBUG)

TEST_DS_DIR = os.path.join(os.path.dirname(__file__), 'dicom_files')
DATASET = dcmread(os.path.join(TEST_DS_DIR, 'CTImageStorage.dcm'))


class TestStorageServiceClass_Deprecated(object):
    """Test the StorageServiceClass"""
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

    def test_scp_failed_ds_decode(self):
        """Test failure to decode the dataset"""
        # Hard to test directly as decode errors won't show up until the
        #   dataset is actually used
        self.scp = DummyStorageSCP()
        self.scp.status = 0x0000
        self.scp.start()

        ae = AE()
        ae.add_requested_context(CTImageStorage, ExplicitVRLittleEndian)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        req = C_STORE()
        req.MessageID = 1
        req.AffectedSOPClassUID = DATASET.SOPClassUID
        req.AffectedSOPInstanceUID = DATASET.SOPInstanceUID
        req.Priorty = 0x0002
        req.DataSet = BytesIO(b'\x08\x00\x01\x00\x40\x40\x00\x00\x00\x00\x00\x08\x00\x49')

        # Send C-STORE request to DIMSE and get response
        assoc.dimse.send_msg(req, 1)
        cx_id, rsp = assoc.dimse.get_msg(True)

        assert rsp.Status == 0xC210
        assert rsp.ErrorComment == 'Unable to decode the dataset'
        assoc.release()
        self.scp.stop()

    def test_scp_handler_return_dataset(self):
        """Test handler returning a Dataset status"""
        self.scp = DummyStorageSCP()
        self.scp.status = Dataset()
        self.scp.status.Status = 0x0001
        self.scp.start()

        ae = AE()
        ae.add_requested_context(CTImageStorage)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_store(DATASET)
        assert rsp.Status == 0x0001
        assoc.release()
        self.scp.stop()

    def test_scp_handler_return_dataset_multi(self):
        """Test handler returning a Dataset status with other elements"""
        self.scp = DummyStorageSCP()
        self.scp.status = Dataset()
        self.scp.status.Status = 0x0001
        self.scp.status.ErrorComment = 'Test'
        self.scp.status.OffendingElement = 0x00080010
        self.scp.start()

        ae = AE()
        ae.add_requested_context(CTImageStorage)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_store(DATASET)
        assert rsp.Status == 0x0001
        assert rsp.ErrorComment == 'Test'
        assert rsp.OffendingElement == 0x00080010
        assoc.release()
        self.scp.stop()

    def test_scp_handler_return_int(self):
        """Test on_c_echo returning an int status"""
        self.scp = DummyStorageSCP()
        self.scp.status = 0x0000
        self.scp.start()

        ae = AE()
        ae.add_requested_context(CTImageStorage)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_store(DATASET)
        assert rsp.Status == 0x0000
        assert not 'ErrorComment' in rsp
        assoc.release()
        self.scp.stop()

    def test_scp_handler_return_invalid(self):
        """Test handler returning a valid status"""
        self.scp = DummyStorageSCP()
        self.scp.status = 0xFFF0
        self.scp.start()

        ae = AE()
        ae.add_requested_context(CTImageStorage)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_store(DATASET)
        assert rsp.Status == 0xFFF0
        assoc.release()
        self.scp.stop()

    def test_scp_handler_no_status(self):
        """Test handler not returning a status"""
        self.scp = DummyStorageSCP()
        self.scp.status = None
        self.scp.start()

        ae = AE()
        ae.add_requested_context(CTImageStorage)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_store(DATASET)
        assert rsp.Status == 0xC002
        assoc.release()
        self.scp.stop()

    def test_scp_handler_exception(self):
        """Test handler raising an exception"""
        self.scp = DummyStorageSCP()
        def on_c_store(ds, context, assoc_info):
            raise ValueError
        self.scp.ae.on_c_store = on_c_store
        self.scp.start()

        ae = AE()
        ae.add_requested_context(CTImageStorage)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_store(DATASET)
        assert rsp.Status == 0xC211
        assoc.release()
        self.scp.stop()

    def test_scp_handler_context(self):
        """Test handler caontext parameter"""
        self.scp = DummyStorageSCP()
        self.scp.start()

        ae = AE()
        ae.add_requested_context(CTImageStorage, '1.2.840.10008.1.2.1')
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status = assoc.send_c_store(DATASET)
        assert status.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        assert self.scp.context.context_id == 1
        assert self.scp.context.abstract_syntax == CTImageStorage
        assert self.scp.context.transfer_syntax == '1.2.840.10008.1.2.1'

        self.scp.stop()

    def test_scp_handler_info(self):
        """Test handler caontext parameter"""
        self.scp = DummyStorageSCP()
        self.scp.start()

        ae = AE()
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status = assoc.send_c_store(DATASET)
        assert status.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        assert 'address' in self.scp.info['requestor']
        assert self.scp.info['requestor']['ae_title'] == b'PYNETDICOM      '
        #assert self.scp.info['requestor']['called_aet'] == b'ANY-SCP         '
        assert isinstance(self.scp.info['requestor']['port'], int)
        assert self.scp.info['acceptor']['port'] == 11112
        assert 'address' in self.scp.info['acceptor']
        assert self.scp.info['acceptor']['ae_title'] == b'PYNETDICOM      '
        assert self.scp.info['parameters']['message_id'] == 1
        assert self.scp.info['parameters']['priority'] == 2
        assert self.scp.info['parameters']['originator_aet'] is None
        assert self.scp.info['parameters']['originator_message_id'] is None
        assert self.scp.info['sop_class_extended'] == {}

        self.scp.stop()

    def test_scp_handler_info_move_origin(self):
        """Test handler caontext parameter"""
        self.scp = DummyStorageSCP()
        self.scp.start()

        ae = AE()
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status = assoc.send_c_store(DATASET,
                                    originator_aet=b'ORIGIN',
                                    originator_id=888)
        assert status.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        assert 'address' in self.scp.info['requestor']
        assert self.scp.info['requestor']['ae_title'] == b'PYNETDICOM      '
        #assert self.scp.info['requestor']['called_aet'] == b'ANY-SCP         '
        assert isinstance(self.scp.info['requestor']['port'], int)
        assert self.scp.info['acceptor']['port'] == 11112
        assert 'address' in self.scp.info['acceptor']
        assert self.scp.info['acceptor']['ae_title'] == b'PYNETDICOM      '
        assert self.scp.info['parameters']['message_id'] == 1
        assert self.scp.info['parameters']['priority'] == 2
        assert self.scp.info['parameters']['originator_aet'] == b'ORIGIN          '
        assert self.scp.info['parameters']['originator_message_id'] == 888

        self.scp.stop()

    def test_scp_handler_sop_class_extended(self):
        """Test that the SOP Class Extended info is available."""
        def on_ext(req):
            return req

        self.scp = DummyStorageSCP()
        self.scp.ae.on_sop_class_extended = on_ext
        self.scp.start()

        ae = AE()
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        ext_neg = []
        item = SOPClassExtendedNegotiation()
        item.sop_class_uid = '1.2.3'
        item.service_class_application_information = b'\x00\x01'
        ext_neg.append(item)

        item = SOPClassExtendedNegotiation()
        item.sop_class_uid = '1.2.4'
        item.service_class_application_information = b'\x00\x02'
        ext_neg.append(item)

        assoc = ae.associate('localhost', 11112, ext_neg=ext_neg)
        assert assoc.is_established
        status = assoc.send_c_store(DATASET)
        assert status.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        info = self.scp.info['sop_class_extended']
        assert len(info) == 2
        assert info['1.2.3'] == b'\x00\x01'
        assert info['1.2.4'] == b'\x00\x02'

        self.scp.stop()

    def test_config_return_dataset(self):
        """Test the _config option DECODE_STORE_DATASETS = True."""
        from pynetdicom import _config

        orig_value = _config.DECODE_STORE_DATASETS
        _config.DECODE_STORE_DATASETS = True

        self.scp = DummyStorageSCP()
        self.scp.status = Dataset()
        self.scp.status.Status = 0x0001
        self.scp.start()

        ae = AE()
        ae.add_requested_context(CTImageStorage)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_store(DATASET)
        assert rsp.Status == 0x0001
        assoc.release()
        assert isinstance(self.scp.dataset, Dataset)

        _config.DECODE_STORE_DATASETS = orig_value

        self.scp.stop()

    def test_config_return_bytes(self):
        """Test the _config option DECODE_STORE_DATASETS = False."""
        from pynetdicom import _config

        orig_value = _config.DECODE_STORE_DATASETS
        _config.DECODE_STORE_DATASETS = False

        self.scp = DummyStorageSCP()
        self.scp.status = Dataset()
        self.scp.status.Status = 0x0001
        self.scp.start()

        ae = AE()
        ae.add_requested_context(CTImageStorage)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_store(DATASET)
        assert rsp.Status == 0x0001
        assoc.release()
        assert isinstance(self.scp.dataset, bytes)

        _config.DECODE_STORE_DATASETS = orig_value

        self.scp.stop()


class TestStorageServiceClass(object):
    """Test the StorageServiceClass"""
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
        ae.add_supported_context(CTImageStorage)
        ae.add_requested_context(CTImageStorage, ExplicitVRLittleEndian)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        req = C_STORE()
        req.MessageID = 1
        req.AffectedSOPClassUID = DATASET.SOPClassUID
        req.AffectedSOPInstanceUID = DATASET.SOPInstanceUID
        req.Priorty = 0x0002
        req.DataSet = BytesIO(b'\x08\x00\x01\x00\x40\x40\x00\x00\x00\x00\x00\x08\x00\x49')

        # Send C-STORE request to DIMSE and get response
        assoc.dimse.send_msg(req, 1)
        cx_id, rsp = assoc.dimse.get_msg(True)

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
        ae.add_supported_context(CTImageStorage)
        ae.add_requested_context(CTImageStorage)
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
        ae.add_supported_context(CTImageStorage)
        ae.add_requested_context(CTImageStorage)
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
        """Test on_c_echo returning an int status"""
        def handle(event):
            return 0x0000

        handlers = [(evt.EVT_C_STORE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(CTImageStorage)
        ae.add_requested_context(CTImageStorage)
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
        ae.add_supported_context(CTImageStorage)
        ae.add_requested_context(CTImageStorage)
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
        ae.add_supported_context(CTImageStorage)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_store(DATASET)
        assert rsp.Status == 0xC002
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_scp_handler_exception_default(self):
        """Test default handler raises an exception"""
        self.ae = ae = AE()
        ae.add_supported_context(CTImageStorage)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_store(DATASET)
        assert rsp.Status == 0xC211
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_scp_handler_exception(self):
        """Test handler raising an exception"""
        def handle(event):
            raise ValueError

        handlers = [(evt.EVT_C_STORE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(CTImageStorage)
        ae.add_requested_context(CTImageStorage)
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
        ae.add_supported_context(CTImageStorage)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status = assoc.send_c_store(DATASET)
        assert status.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        cx = attrs['context']
        assert cx.context_id == 1
        assert cx.abstract_syntax == CTImageStorage
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
        ae.add_supported_context(CTImageStorage)
        ae.add_requested_context(CTImageStorage)
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
        ae.add_supported_context(CTImageStorage)
        ae.add_requested_context(CTImageStorage)
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
        ae.add_supported_context(CTImageStorage)
        ae.add_requested_context(CTImageStorage)
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
        ae.add_supported_context(CTImageStorage)
        ae.add_requested_context(CTImageStorage)
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
        assert req.MoveOriginatorApplicationEntityTitle == b'ORIGIN          '
        assert req.MoveOriginatorMessageID == 888

        scp.shutdown()

    def test_scp_handler_sop_extended(self):
        """Test handler event's assoc attribute with SOP Class Extended"""
        attrs = {}
        def handle_sop(event):
            return event.app_info

        def handle(event):
            attrs['context'] = event.context
            attrs['assoc'] = event.assoc
            attrs['request'] = event.request
            attrs['dataset'] = event.dataset
            return 0x0000

        handlers = [(evt.EVT_C_STORE, handle),
                    (evt.EVT_SOP_EXTENDED, handle_sop)]

        self.ae = ae = AE()
        ae.add_supported_context(CTImageStorage)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)


        ext_neg = []
        item = SOPClassExtendedNegotiation()
        item.sop_class_uid = '1.2.3'
        item.service_class_application_information = b'\x00\x01'
        ext_neg.append(item)

        item = SOPClassExtendedNegotiation()
        item.sop_class_uid = '1.2.4'
        item.service_class_application_information = b'\x00\x02'
        ext_neg.append(item)

        assoc = ae.associate('localhost', 11112, ext_neg=ext_neg)
        assert assoc.is_established
        status = assoc.send_c_store(DATASET)
        assert status.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        ext = attrs['assoc'].acceptor.sop_class_extended
        assert ext['1.2.3'] == b'\x00\x01'
        assert ext['1.2.4'] == b'\x00\x02'

        scp.shutdown()

    def test_event_ds_modify(self):
        """Test modifying event.dataset in-place."""
        event_out = []
        def handle(event):
            meta = Dataset()
            meta.TransferSyntaxUID = event.context.transfer_syntax
            event.dataset.file_meta = meta

            event_out.append(event.dataset)

            return 0x0000

        handlers = [(evt.EVT_C_STORE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(CTImageStorage)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_store(DATASET)
        assert rsp.Status == 0x0000
        assert not 'ErrorComment' in rsp
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

        assert 'TransferSyntaxUID' in event_out[0].file_meta

    def test_event_ds_change(self):
        """Test that event.dataset is redecoded if request.DataSet changes."""

        def handle(event):
            assert event._hash is None
            assert event._decoded is None
            ds = event.dataset
            assert event._decoded == ds
            assert event._hash == hash(event.request.DataSet)
            event._hash = None
            ds = event.dataset
            assert event._hash == hash(event.request.DataSet)
            assert event._decoded == ds

            return 0x0000

        handlers = [(evt.EVT_C_STORE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(CTImageStorage)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_store(DATASET)
        assert rsp.Status == 0x0000
        assert not 'ErrorComment' in rsp
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_event_file_meta(self):
        """Test basic functioning of event.file_meta"""
        event_out = []
        def handle(event):
            ds = event.dataset
            ds.file_meta = event.file_meta

            event_out.append(ds)

            return 0x0000

        handlers = [(evt.EVT_C_STORE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(CTImageStorage)
        ts = ae.supported_contexts[0].transfer_syntax[0]
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_store(DATASET)
        assert rsp.Status == 0x0000
        assert not 'ErrorComment' in rsp
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

        ds = event_out[0]
        meta = event_out[0].file_meta
        assert meta.MediaStorageSOPClassUID == CTImageStorage
        assert meta.MediaStorageSOPInstanceUID == ds.SOPInstanceUID
        assert meta.TransferSyntaxUID == ts

    def test_event_file_meta_bad(self):
        """Test event.file_meta when not a C-STORE request."""
        event_exc = []
        def handle(event):
            try:
                event.file_meta
            except Exception as exc:
                event_exc.append(exc)

            return 0x0000

        handlers = [(evt.EVT_C_ECHO, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_echo()
        assert rsp.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

        exc = event_exc[0]
        assert isinstance(exc, AttributeError)
