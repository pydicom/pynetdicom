"""Tests for the StorageServiceClass."""

from io import BytesIO
import os
import time

import pytest

from pydicom import dcmread
from pydicom.dataset import Dataset
from pydicom.uid import ExplicitVRLittleEndian

from pynetdicom import AE, evt, build_role, debug_logger
from pynetdicom.dimse_primitives import C_STORE
from pynetdicom.pdu_primitives import SOPClassExtendedNegotiation
from pynetdicom.service_class import StorageServiceClass
from pynetdicom.sop_class import (
    VerificationSOPClass, CTImageStorage, RTImageStorage,
)
try:
    from pynetdicom.status import Status
    HAS_STATUS = True
except ImportError:
    HAS_STATUS = False


#debug_logger()


TEST_DS_DIR = os.path.join(os.path.dirname(__file__), 'dicom_files')
DATASET = dcmread(os.path.join(TEST_DS_DIR, 'CTImageStorage.dcm'))


class TestStorageServiceClass(object):
    """Test the StorageServiceClass"""
    def setup(self):
        """Run prior to each test"""
        self.ae = None

    def teardown(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

    @pytest.mark.skipif(not HAS_STATUS, reason="No Status class available")
    def test_status_enum(self):
        """Test failure to decode the dataset"""
        # Hard to test directly as decode errors won't show up until the
        #   dataset is actually used
        Status.add('UNABLE_TO_DECODE', 0xC210)

        def handle(event):
            try:
                for elem in event.dataset.iterall():
                    pass
            except:
                status = Dataset()
                status.Status = Status.UNABLE_TO_DECODE
                status.ErrorComment = "Unable to decode the dataset"
                return status

            return Status.SUCCESS

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
        assoc._reactor_checkpoint.clear()
        assoc.dimse.send_msg(req, 1)
        cx_id, rsp = assoc.dimse.get_msg(True)
        assoc._reactor_checkpoint.set()

        assert rsp.Status == 0xC210
        assert rsp.ErrorComment == 'Unable to decode the dataset'
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

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
        """Test handler returning an int status"""
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
        assert req.MoveOriginatorApplicationEntityTitle == b'ORIGIN'
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

    def test_scp_handler_aborts(self):
        """Test handler aborting the association"""
        def handle(event):
            event.assoc.abort()

        handlers = [(evt.EVT_C_STORE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(CTImageStorage)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_store(DATASET)
        assert rsp == Dataset()

        time.sleep(0.1)
        assert assoc.is_aborted
        scp.shutdown()
