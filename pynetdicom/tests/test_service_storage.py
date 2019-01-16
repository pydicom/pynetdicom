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

from pynetdicom import AE
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
#LOGGER.setLevel(logging.DEBUG)
LOGGER.setLevel(logging.CRITICAL)

TEST_DS_DIR = os.path.join(os.path.dirname(__file__), 'dicom_files')
DATASET = dcmread(os.path.join(TEST_DS_DIR, 'CTImageStorage.dcm'))


class TestStorageServiceClass(object):
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
        req.DataSet = BytesIO(b'\x08\x00\x01\x00\x04\x00\x00\x00\x00\x08\x00\x49')

        # Send C-STORE request to DIMSE and get response
        assoc.dimse.send_msg(req, 1)
        cx_id, rsp = assoc.dimse.get_msg(True)

        assert rsp.Status == 0xC210
        assert rsp.ErrorComment == 'Unable to decode the dataset'
        assoc.release()
        self.scp.stop()

    def test_scp_callback_return_dataset(self):
        """Test on_c_store returning a Dataset status"""
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

    def test_scp_callback_return_dataset_multi(self):
        """Test on_c_store returning a Dataset status with other elements"""
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

    def test_scp_callback_return_int(self):
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

    def test_scp_callback_return_invalid(self):
        """Test on_c_store returning a valid status"""
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

    def test_scp_callback_no_status(self):
        """Test on_c_store not returning a status"""
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

    def test_scp_callback_exception(self):
        """Test on_c_store raising an exception"""
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

    def test_scp_callback_context(self):
        """Test on_c_store caontext parameter"""
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

    def test_scp_callback_info(self):
        """Test on_c_store caontext parameter"""
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

    def test_scp_callback_info_move_origin(self):
        """Test on_c_store caontext parameter"""
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

    def test_scp_callback_sop_class_extended(self):
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
