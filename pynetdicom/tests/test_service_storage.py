"""Tests for the StorageServiceClass."""

from copy import deepcopy
from io import BytesIO
import os
from pathlib import Path
import time

import pytest

from pydicom import dcmread
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, ImplicitVRLittleEndian

from pynetdicom import AE, _config, evt, debug_logger, register_uid, sop_class
from pynetdicom.dimse_primitives import C_STORE
from pynetdicom.pdu_primitives import SOPClassExtendedNegotiation
from pynetdicom.sop_class import (
    Verification,
    CTImageStorage,
    _STORAGE_CLASSES,
)
from pynetdicom.service_class import StorageServiceClass

try:
    from pynetdicom.status import Status

    HAS_STATUS = True
except ImportError:
    HAS_STATUS = False


# debug_logger()


TEST_DS_DIR = os.path.join(os.path.dirname(__file__), "dicom_files")
DATASET = dcmread(os.path.join(TEST_DS_DIR, "CTImageStorage.dcm"))


@pytest.fixture()
def enable_unrestricted():
    _config.UNRESTRICTED_STORAGE_SERVICE = True
    yield
    _config.UNRESTRICTED_STORAGE_SERVICE = False


@pytest.fixture()
def register_new_uid():
    register_uid(
        "1.2.3.4",
        "NewStorage",
        StorageServiceClass,
    )
    yield
    del _STORAGE_CLASSES["NewStorage"]
    delattr(sop_class, "NewStorage")


class TestStorageServiceClass:
    """Test the StorageServiceClass"""

    def setup_method(self):
        """Run prior to each test"""
        self.ae = None

        self.ds = Dataset()
        self.ds.file_meta = FileMetaDataset()
        self.ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
        self.ds.SOPClassUID = CTImageStorage
        self.ds.SOPInstanceUID = "1.1.1"
        self.ds.PatientName = "Test"

    def teardown_method(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

        _config.STORE_RECV_CHUNKED_DATASET = False

    @pytest.mark.skipif(not HAS_STATUS, reason="No Status class available")
    def test_status_enum(self):
        """Test failure to decode the dataset"""
        # Hard to test directly as decode errors won't show up until the
        #   dataset is actually used
        Status.add("UNABLE_TO_DECODE", 0xC210)

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
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established

        req = C_STORE()
        req.MessageID = 1
        req.AffectedSOPClassUID = DATASET.SOPClassUID
        req.AffectedSOPInstanceUID = DATASET.SOPInstanceUID
        req.Priority = 0x0002
        req.DataSet = BytesIO(
            b"\x08\x00\x01\x00\x40\x40\x00\x00\x00\x00\x00\x08\x00\x49"
        )

        # Send C-STORE request to DIMSE and get response
        assoc._reactor_checkpoint.clear()
        assoc.dimse.send_msg(req, 1)
        with pytest.warns(UserWarning):
            cx_id, rsp = assoc.dimse.get_msg(True)
        assoc._reactor_checkpoint.set()

        assert rsp.Status == 0xC210
        assert rsp.ErrorComment == "Unable to decode the dataset"
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
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established

        req = C_STORE()
        req.MessageID = 1
        req.AffectedSOPClassUID = DATASET.SOPClassUID
        req.AffectedSOPInstanceUID = DATASET.SOPInstanceUID
        req.Priority = 0x0002
        req.DataSet = BytesIO(
            b"\x08\x00\x01\x00\x40\x40\x00\x00\x00\x00\x00\x08\x00\x49"
        )

        # Send C-STORE request to DIMSE and get response
        assoc._reactor_checkpoint.clear()
        assoc.dimse.send_msg(req, 1)
        with pytest.warns(UserWarning):
            cx_id, rsp = assoc.dimse.get_msg(True)
        assoc._reactor_checkpoint.set()

        assert rsp.Status == 0xC210
        assert rsp.ErrorComment == "Unable to decode the dataset"
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
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate("localhost", 11112)
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
            status.ErrorComment = "Test"
            status.OffendingElement = 0x00080010
            return status

        handlers = [(evt.EVT_C_STORE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(CTImageStorage)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established
        rsp = assoc.send_c_store(DATASET)
        assert rsp.Status == 0x0001
        assert rsp.ErrorComment == "Test"
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
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established
        rsp = assoc.send_c_store(DATASET)
        assert rsp.Status == 0x0000
        assert "ErrorComment" not in rsp
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
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate("localhost", 11112)
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
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate("localhost", 11112)
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
        scp = ae.start_server(("localhost", 11112), block=False)

        assoc = ae.associate("localhost", 11112)
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
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate("localhost", 11112)
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
            attrs["context"] = event.context
            attrs["assoc"] = event.assoc
            attrs["request"] = event.request
            attrs["dataset"] = event.dataset
            return 0x0000

        handlers = [(evt.EVT_C_STORE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(CTImageStorage)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established
        status = assoc.send_c_store(DATASET)
        assert status.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        cx = attrs["context"]
        assert cx.context_id == 1
        assert cx.abstract_syntax == CTImageStorage
        assert cx.transfer_syntax == "1.2.840.10008.1.2"

        scp.shutdown()

    def test_scp_handler_assoc(self):
        """Test handler event's assoc attribute"""
        attrs = {}

        def handle(event):
            attrs["context"] = event.context
            attrs["assoc"] = event.assoc
            attrs["request"] = event.request
            attrs["dataset"] = event.dataset
            return 0x0000

        handlers = [(evt.EVT_C_STORE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(CTImageStorage)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established
        status = assoc.send_c_store(DATASET)
        assert status.Status == 0x0000

        scp_assoc = attrs["assoc"]
        assert scp_assoc == scp.active_associations[0]

        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_scp_handler_request(self):
        """Test handler event's request attribute"""
        attrs = {}

        def handle(event):
            attrs["context"] = event.context
            attrs["assoc"] = event.assoc
            attrs["request"] = event.request
            attrs["dataset"] = event.dataset
            return 0x0000

        handlers = [(evt.EVT_C_STORE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(CTImageStorage)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established
        status = assoc.send_c_store(DATASET)
        assert status.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        req = attrs["request"]
        assert req.MessageID == 1
        assert isinstance(req, C_STORE)

        scp.shutdown()

    def test_scp_handler_dataset(self):
        """Test handler event's dataset property"""
        attrs = {}

        def handle(event):
            attrs["context"] = event.context
            attrs["assoc"] = event.assoc
            attrs["request"] = event.request
            attrs["dataset"] = event.dataset
            return 0x0000

        handlers = [(evt.EVT_C_STORE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(CTImageStorage)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established
        status = assoc.send_c_store(DATASET)
        assert status.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        ds = attrs["dataset"]
        assert isinstance(ds, Dataset)
        assert ds.PatientName == DATASET.PatientName

        scp.shutdown()

    def test_scp_handler_dataset_path(self):
        """Test handler event's dataset_path property"""
        attrs = {}

        def handle(event):
            dataset_path = event.dataset_path

            # File at `dataset_path` valid and complete
            ds = dcmread(dataset_path)
            assert isinstance(ds, Dataset)
            assert isinstance(ds.file_meta, FileMetaDataset)
            assert ds.PatientName == DATASET.PatientName
            assert (
                ds.file_meta.MediaStorageSOPInstanceUID
                == DATASET.file_meta.MediaStorageSOPInstanceUID
            )

            attrs["dataset"] = event.dataset
            attrs["dataset_path"] = dataset_path
            return 0x0000

        _config.STORE_RECV_CHUNKED_DATASET = True

        handlers = [(evt.EVT_C_STORE, handle)]

        self.ae = ae = AE()
        ae.maximum_pdu_size = 256
        ae.add_supported_context(CTImageStorage)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established
        status = assoc.send_c_store(DATASET)
        assert status.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        dataset_path = attrs["dataset_path"]
        assert isinstance(dataset_path, Path)

        # `dataset_path` not available outside of event handler
        with pytest.raises(FileNotFoundError):
            dataset_path.open("rb")

        ds = attrs["dataset"]
        assert "CompressedSamples^CT1" == ds.PatientName
        assert "DataSetTrailingPadding" in ds
        assert len(ds.DataSetTrailingPadding) == 126

        scp.shutdown()

    def test_scp_handler_dataset_path_windows_unlink(self, monkeypatch):
        """Test handler event's dataset_path property:
        user has file open on Windows"""

        def unlink(*args, **kwargs):
            raise OSError()

        import os

        monkeypatch.setattr(os, "unlink", unlink)

        def handle(event):
            return 0x0000

        _config.STORE_RECV_CHUNKED_DATASET = True

        handlers = [(evt.EVT_C_STORE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(CTImageStorage)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established
        status = assoc.send_c_store(DATASET)
        assert status.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_scp_handler_move_origin(self):
        """Test handler event's request property with MoveOriginator"""
        attrs = {}

        def handle(event):
            attrs["context"] = event.context
            attrs["assoc"] = event.assoc
            attrs["request"] = event.request
            attrs["dataset"] = event.dataset
            return 0x0000

        handlers = [(evt.EVT_C_STORE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(CTImageStorage)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established
        status = assoc.send_c_store(DATASET, originator_aet="ORIGIN", originator_id=888)
        assert status.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        req = attrs["request"]
        assert req.MoveOriginatorApplicationEntityTitle == "ORIGIN"
        assert req.MoveOriginatorMessageID == 888

        scp.shutdown()

    def test_scp_handler_sop_extended(self):
        """Test handler event's assoc attribute with SOP Class Extended"""
        attrs = {}

        def handle_sop(event):
            return event.app_info

        def handle(event):
            attrs["context"] = event.context
            attrs["assoc"] = event.assoc
            attrs["request"] = event.request
            attrs["dataset"] = event.dataset
            return 0x0000

        handlers = [(evt.EVT_C_STORE, handle), (evt.EVT_SOP_EXTENDED, handle_sop)]

        self.ae = ae = AE()
        ae.add_supported_context(CTImageStorage)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)

        ext_neg = []
        item = SOPClassExtendedNegotiation()
        item.sop_class_uid = "1.2.3"
        item.service_class_application_information = b"\x00\x01"
        ext_neg.append(item)

        item = SOPClassExtendedNegotiation()
        item.sop_class_uid = "1.2.4"
        item.service_class_application_information = b"\x00\x02"
        ext_neg.append(item)

        assoc = ae.associate("localhost", 11112, ext_neg=ext_neg)
        assert assoc.is_established
        status = assoc.send_c_store(DATASET)
        assert status.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        ext = attrs["assoc"].acceptor.sop_class_extended
        assert ext["1.2.3"] == b"\x00\x01"
        assert ext["1.2.4"] == b"\x00\x02"

        scp.shutdown()

    def test_event_ds_modify(self):
        """Test modifying event.dataset in-place."""
        event_out = []

        def handle(event):
            meta = FileMetaDataset()
            meta.TransferSyntaxUID = event.context.transfer_syntax
            event.dataset.file_meta = meta

            event_out.append(event.dataset)

            return 0x0000

        handlers = [(evt.EVT_C_STORE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(CTImageStorage)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established
        rsp = assoc.send_c_store(DATASET)
        assert rsp.Status == 0x0000
        assert not "ErrorComment" in rsp
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

        assert "TransferSyntaxUID" in event_out[0].file_meta

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
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established
        rsp = assoc.send_c_store(DATASET)
        assert rsp.Status == 0x0000
        assert not "ErrorComment" in rsp
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
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established
        rsp = assoc.send_c_store(DATASET)
        assert rsp.Status == 0x0000
        assert not "ErrorComment" in rsp
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
        ae.add_supported_context(Verification)
        ae.add_requested_context(Verification)
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate("localhost", 11112)
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
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established
        rsp = assoc.send_c_store(DATASET)
        assert rsp == Dataset()

        time.sleep(0.1)
        assert assoc.is_aborted
        scp.shutdown()

    def test_unrestricted(self, enable_unrestricted):
        """Test an unrestricted storage service."""
        recv = []

        def handle(event):
            recv.append(event.dataset.PatientName)
            return 0x0000

        handlers = [(evt.EVT_C_STORE, handle)]

        self.ae = ae = AE()
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)

        ae.add_requested_context(CTImageStorage)
        ae.add_requested_context("1.2.3")
        ae.add_requested_context("1.2.840.10008.1.1.1.1.1.1.1.1")
        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established
        rsp = assoc.send_c_store(DATASET)
        assert rsp.Status == 0x0000

        self.ds.SOPClassUID = "1.2.3"
        self.ds.PatientName = "Private"

        rsp = assoc.send_c_store(self.ds)
        assert rsp.Status == 0x0000

        self.ds.SOPClassUID = "1.2.840.10008.1.1.1.1.1.1.1.1"
        self.ds.PatientName = "Unknown^Public"

        rsp = assoc.send_c_store(self.ds)
        assert rsp.Status == 0x0000

        assoc.release()
        assert assoc.is_released

        assert recv == ["CompressedSamples^CT1", "Private", "Unknown^Public"]

        scp.shutdown()

    def test_register(self, register_new_uid):
        """Test registering a new UID."""
        from pynetdicom.sop_class import NewStorage

        attrs = {}

        def handle(event):
            attrs["uid"] = event.dataset.SOPClassUID
            return 0x0000

        ds = deepcopy(DATASET)
        ds.SOPClassUID = NewStorage

        handlers = [(evt.EVT_C_STORE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(NewStorage)
        ae.add_requested_context(NewStorage)
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established
        rsp = assoc.send_c_store(ds)
        assert rsp.Status == 0x0000
        assert "ErrorComment" not in rsp
        assoc.release()
        assert assoc.is_released

        assert attrs["uid"] == NewStorage

        scp.shutdown()
