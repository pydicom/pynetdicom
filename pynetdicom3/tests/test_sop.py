"""Tests for the sop_class module."""

import logging
from io import BytesIO
import os
import threading
import time

import pytest

from pydicom import read_file
from pydicom.dataset import Dataset

from pynetdicom3 import AE
from pynetdicom3.dimse_primitives import C_ECHO, C_STORE, C_FIND, C_GET, C_MOVE
from pynetdicom3.dsutils import decode
from pynetdicom3.sop_class import (
    uid_to_sop_class,
    VerificationServiceClass,
    StorageServiceClass,
    QueryRetrieveGetServiceClass,
    QueryRetrieveFindServiceClass,
    QueryRetrieveMoveServiceClass,
    ModalityWorklistServiceSOPClass,
    VerificationSOPClass,
    CTImageStorage,
    PatientRootQueryRetrieveInformationModelFind,
    PatientRootQueryRetrieveInformationModelGet,
    PatientRootQueryRetrieveInformationModelMove
)
from .dummy_c_scp import (DummyVerificationSCP, DummyStorageSCP, DummyFindSCP,
                         DummyBaseSCP, DummyGetSCP, DummyMoveSCP)

LOGGER = logging.getLogger('pynetdicom3')
#LOGGER.setLevel(logging.DEBUG)
LOGGER.setLevel(logging.CRITICAL)

TEST_DS_DIR = os.path.join(os.path.dirname(__file__), 'dicom_files')
DATASET = read_file(os.path.join(TEST_DS_DIR, 'CTImageStorage.dcm'))


class DummyAE(object):
    """Dummy class for testing callback errors"""
    @staticmethod
    def on_c_echo(context):
        """Dummy method to test callback errors"""
        raise ValueError

    @staticmethod
    def on_c_store(ds, context, peer_ae):
        """Dummy method to test callback errors"""
        raise ValueError

    @staticmethod
    def on_c_find(ds, context, peer_ae):
        """Dummy method to test callback errors"""
        raise ValueError

    @staticmethod
    def on_c_cancel_find():
        """Dummy method to test callback errors"""
        raise ValueError

    @staticmethod
    def on_c_get(ds, context, peer_ae):
        """Dummy method to test callback errors"""
        raise ValueError

    @staticmethod
    def on_c_cancel_get():
        """Dummy method to test callback errors"""
        raise ValueError

    @staticmethod
    def on_c_move(ds, move_aet, context, peer_ae):
        """Dummy method to test callback errors"""
        raise ValueError

    @staticmethod
    def on_c_cancel_move():
        """Dummy method to test callback errors"""
        raise ValueError


class DummyDIMSE(object):
    """Dummy DIMSE provider"""
    def send_msg(self, msg, context_id, length):
        """Dummy Send method"""
        pass


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

    def test_validate_status_ds_no_status(self):
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
        assert not hasattr(rsp, 'PatientName')

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


class TestVerificationServiceClass(object):
    """Test the VerifictionSOPClass"""
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

    def test_scp_callback_return_dataset(self):
        """Test on_c_echo returning a Dataset status"""
        self.scp = DummyVerificationSCP()
        self.scp.status = Dataset()
        self.scp.status.Status = 0x0001
        self.scp.start()

        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_echo()
        assert rsp.Status == 0x0001
        assoc.release()
        self.scp.stop()

    def test_scp_callback_return_dataset_no_status(self):
        """Test on_c_echo returning a Dataset with no Status elem"""
        self.scp = DummyVerificationSCP()
        self.scp.status = Dataset()
        self.scp.start()

        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_echo()
        assert rsp.Status == 0x0000
        assoc.release()
        self.scp.stop()

    def test_scp_callback_return_dataset_multi(self):
        """Test on_c_echo returning a Dataset status with other elements"""
        self.scp = DummyVerificationSCP()
        self.scp.status = Dataset()
        self.scp.status.Status = 0x0001
        self.scp.status.ErrorComment = 'Test'
        self.scp.start()

        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_echo()
        assert rsp.Status == 0x0001
        assert rsp.ErrorComment == 'Test'
        assoc.release()
        self.scp.stop()

    def test_scp_callback_return_dataset_unknown(self):
        """Test a status ds with an unknown element."""
        self.scp = DummyVerificationSCP()
        self.scp.status = Dataset()
        self.scp.status.Status = 0x0001
        self.scp.status.PatientName = 'test name'
        self.scp.start()

        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_echo()
        assert rsp.Status == 0x0001
        assoc.release()
        self.scp.stop()

    def test_scp_callback_return_int(self):
        """Test on_c_echo returning an int status"""
        self.scp = DummyVerificationSCP()
        self.scp.status = 0x0002
        self.scp.start()

        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_echo()
        assert rsp.Status == 0x0002
        assert not 'ErrorComment' in rsp
        assoc.release()
        self.scp.stop()

    def test_scp_callback_return_valid(self):
        """Test on_c_echo returning a valid status"""
        self.scp = DummyVerificationSCP()
        self.scp.status = 0x0000
        self.scp.start()

        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_echo()
        assert rsp.Status == 0x0000
        assoc.release()
        self.scp.stop()

    def test_scp_callback_no_status(self):
        """Test on_c_echo not returning a status"""
        self.scp = DummyVerificationSCP()
        self.scp.status = None
        self.scp.start()

        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_echo()
        assert rsp.Status == 0x0000
        assoc.release()
        self.scp.stop()

    def test_scp_callback_exception(self):
        """Test on_c_echo raising an exception"""
        self.scp = DummyVerificationSCP()
        def on_c_echo(context): raise ValueError

        self.scp.ae.on_c_echo = on_c_echo
        self.scp.start()

        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_echo()
        assert rsp.Status == 0x0000
        assoc.release()
        self.scp.stop()

    def test_scp_callback_context(self):
        """Test on_c_echo context parameter."""
        self.scp = DummyVerificationSCP()
        self.scp.start()

        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_echo()
        assert rsp.Status == 0x0000
        assoc.release()

        assert self.scp.context.AbstractSyntax == '1.2.840.10008.1.1'
        assert self.scp.context.TransferSyntax[0] == '1.2.840.10008.1.2.1'

        self.scp.stop()

    def test_scp_callback_peer(self):
        """Test on_c_echo peer_ae parameter."""
        self.scp = DummyVerificationSCP()
        self.scp.start()

        ae = AE(ae_title='ECHOSCU', scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112, max_pdu=16380)
        assert assoc.is_established
        rsp = assoc.send_c_echo()
        assert rsp.Status == 0x0000
        assoc.release()

        assert self.scp.peer_ae['address'] == '127.0.0.1'
        assert self.scp.peer_ae['pdv_size'] == 16380
        assert self.scp.peer_ae['ae_title'] == b'ECHOSCU         '

        self.scp.stop()


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

    @pytest.mark.skip('Difficult to test correctly')
    def test_scp_failed_ds_decode(self):
        """Test failure to decode the dataset"""
        # Although we managed to get a failure with issue #632 in pydicom
        self.scp = DummyStorageSCP()
        self.scp.status = 0x0000
        self.scp.start()

        ae = AE(scu_sop_class=[CTImageStorage])
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
        rsp, _ = assoc.dimse.receive_msg(True)

        assert rsp.Status == 0xC100
        assert rsp.ErrorComment == 'Unable to decode the dataset'
        assoc.release()
        self.scp.stop()

    def test_scp_callback_return_dataset(self):
        """Test on_c_store returning a Dataset status"""
        self.scp = DummyStorageSCP()
        self.scp.status = Dataset()
        self.scp.status.Status = 0x0001
        self.scp.start()

        ae = AE(scu_sop_class=[CTImageStorage])
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

        ae = AE(scu_sop_class=[CTImageStorage])
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

        ae = AE(scu_sop_class=[CTImageStorage])
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

        ae = AE(scu_sop_class=[CTImageStorage])
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

        ae = AE(scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_store(DATASET)
        assert rsp.Status == 0xC002
        assoc.release()
        self.scp.stop()

    def test_scp_callback_exception(self):
        """Test on_c_store raising an exception"""
        self.scp = DummyStorageSCP()
        def on_c_store(ds, context, peer_ae): raise ValueError
        self.scp.ae.on_c_store = on_c_store
        self.scp.start()

        ae = AE(scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_store(DATASET)
        assert rsp.Status == 0xC211
        assoc.release()
        self.scp.stop()

    def test_scp_callback_context(self):
        """Test on_c_store context parameter."""
        self.scp = DummyStorageSCP()
        self.scp.start()

        ae = AE(scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_store(DATASET)
        assert rsp.Status == 0x0000
        assoc.release()

        assert self.scp.context.AbstractSyntax == CTImageStorage.UID
        assert self.scp.context.TransferSyntax[0] == '1.2.840.10008.1.2.1'

        self.scp.stop()

    def test_scp_callback_peer(self):
        """Test on_c_store peer_ae parameter."""
        self.scp = DummyStorageSCP()
        self.scp.start()

        ae = AE(ae_title='STORESCU', scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11112, max_pdu=16380)
        assert assoc.is_established
        rsp = assoc.send_c_store(DATASET)
        assert rsp.Status == 0x0000
        assoc.release()

        # Note: can't guarantee the port number
        assert self.scp.peer_ae['address'] == '127.0.0.1'
        assert self.scp.peer_ae['pdv_size'] == 16380
        assert self.scp.peer_ae['ae_title'] == b'STORESCU        '

        self.scp.stop()


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

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        req = C_FIND()
        req.MessageID = 1
        req.AffectedSOPClassUID = PatientRootQueryRetrieveInformationModelFind.UID
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

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='P')
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

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='P')
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

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='P')
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

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFFF0
        with pytest.raises(StopIteration):
            next(result)
        assoc.release()
        self.scp.stop()

    def test_callback_status_invalid(self):
        """Test SCP handles on_c_find yielding a invalid status"""
        self.scp = DummyFindSCP()
        self.scp.statuses = ['Failure']
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xC002
        with pytest.raises(StopIteration):
            next(result)
        assoc.release()
        self.scp.stop()

    def test_callback_status_none(self):
        """Test SCP handles on_c_find not yielding a status"""
        self.scp = DummyFindSCP()
        self.scp.statuses = [None]
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xC002
        with pytest.raises(StopIteration):
            next(result)
        assoc.release()
        self.scp.stop()

    def test_callback_exception(self):
        """Test SCP handles on_c_find yielding an exception"""
        self.scp = DummyFindSCP()
        def on_c_find(ds): raise ValueError
        self.scp.ae.on_c_find = on_c_find
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xC311
        with pytest.raises(StopIteration):
            next(result)
        assoc.release()
        self.scp.stop()

    def test_callback_bad_identifier(self):
        """Test SCP handles a bad callback identifier"""
        self.scp = DummyFindSCP()
        self.scp.statuses = [0xFF00, 0xFE00]
        self.scp.identifiers = [None, None]
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xC312
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_callback_context(self):
        """Test on_c_find context parameter."""
        self.scp = DummyFindSCP()
        self.scp.statuses = [Dataset(), 0x0000]
        self.scp.statuses[0].Status = 0xFF00
        self.scp.identifers = [self.query, None]
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        status, identifier = next(result)
        assert status.Status == 0x0000

        assert self.scp.context.AbstractSyntax == PatientRootQueryRetrieveInformationModelFind.UID
        assert self.scp.context.TransferSyntax[0] == '1.2.840.10008.1.2.1'

        self.scp.stop()

    def test_callback_peer(self):
        """Test on_c_find peer_ae parameter."""
        self.scp = DummyFindSCP()
        self.scp.statuses = [Dataset(), 0x0000]
        self.scp.statuses[0].Status = 0xFF00
        self.scp.identifers = [self.query, None]
        self.scp.start()

        ae = AE(ae_title='FINDSCU',
                scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112, max_pdu=12345)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        status, identifier = next(result)
        assert status.Status == 0x0000

        # Note: can't guarantee the port number
        assert self.scp.peer_ae['address'] == '127.0.0.1'
        assert self.scp.peer_ae['pdv_size'] == 12345
        assert self.scp.peer_ae['ae_title'] == b'FINDSCU         '

        self.scp.stop()

    def test_pending_cancel(self):
        """Test on_c_find yielding pending then cancel status"""
        self.scp = DummyFindSCP()
        self.scp.statuses = [0xFF00, 0xFE00]
        self.scp.identifiers = [self.query, None]
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier == self.query
        status, identifier = next(result)
        assert status.Status == 0xFE00
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_pending_success(self):
        """Test on_c_find yielding pending then success status"""
        self.scp = DummyFindSCP()
        self.scp.statuses = [0xFF01, 0x0000, 0xA700]
        self.scp.identifiers = [self.query, None]
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF01
        assert identifier == self.query
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_pending_failure(self):
        """Test on_c_find yielding pending then failure status"""
        self.scp = DummyFindSCP()
        self.scp.statuses = [0xFF00, 0xA700, 0x0000]
        self.scp.identifiers = [self.query, None, None]
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier == self.query
        status, identifier = next(result)
        assert status.Status == 0xA700
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_multi_pending_cancel(self):
        """Test on_c_find yielding multiple pending then cancel status"""
        self.scp = DummyFindSCP()
        self.scp.statuses = [0xFF00, 0xFF01, 0xFF00, 0xFE00, 0x0000]
        self.scp.identifiers = [self.query, self.query, self.query, None]
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='P')
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
        self.scp.stop()

    def test_multi_pending_success(self):
        """Test on_c_find yielding multiple pending then success status"""
        self.scp = DummyFindSCP()
        self.scp.statuses = [0xFF00, 0xFF01, 0xFF00, 0x0000, 0xA700]
        self.scp.identifiers = [self.query, self.query, self.query, None]
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='P')
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
        self.scp.stop()

    def test_multi_pending_failure(self):
        """Test on_c_find yielding multiple pending then failure status"""
        self.scp = DummyFindSCP()
        self.scp.statuses = [0xFF00, 0xFF01, 0xFF00, 0xA700, 0x0000]
        self.scp.identifiers = [self.query, self.query, self.query, None]
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='P')
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
        self.scp.stop()


class TestQRGetServiceClass(object):
    def setup(self):
        """Run prior to each test"""
        self.query = Dataset()
        self.query.PatientName = '*'
        self.query.QueryRetrieveLevel = "PATIENT"

        self.ds = Dataset()
        self.ds.SOPClassUID = CTImageStorage().UID
        self.ds.SOPInstanceUID = '1.1.1'
        self.ds.PatientName = 'Test'

        self.fail = Dataset()
        self.fail.FailedSOPInstanceUIDList = ['1.2.3']

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
        self.scp = DummyGetSCP()
        self.scp.statuses = [0xFF00]
        self.scp.datasets = [self.ds]
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet])
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        req = C_GET()
        req.MessageID = 1
        req.AffectedSOPClassUID = PatientRootQueryRetrieveInformationModelGet.UID
        req.Priority = 2
        req.Identifier = BytesIO(b'\x08\x00\x01\x00\x04\x00\x00\x00\x00\x08\x00\x49')
        assoc.dimse.send_msg(req, 1)
        rsp, _ = assoc.dimse.receive_msg(True)
        assert rsp.Status == 0xC410

        assoc.release()
        self.scp.stop()

    def test_get_callback_bad_subops(self):
        """Test on_c_get yielding a bad no subops"""
        self.scp = DummyGetSCP()
        self.scp.no_suboperations = 'test'
        self.scp.statuses = [Dataset(), 0x0000]
        self.scp.statuses[0].Status = 0xFF00
        self.scp.datasets = [self.ds, None]
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage])
        def on_c_store(ds, context, peer_ae):
            return 0x0000

        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xC413
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_get_callback_status_dataset(self):
        """Test on_c_get yielding a Dataset status"""
        self.scp = DummyGetSCP()
        self.scp.no_suboperations = 1
        self.scp.statuses = [Dataset(), 0x0000]
        self.scp.statuses[0].Status = 0xFF00
        self.scp.datasets = [self.ds, None]
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage])
        def on_c_store(ds, context, peer_ae):
            return 0x0000

        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_get_callback_status_dataset_multi(self):
        """Test on_c_get yielding a Dataset status with other elements"""
        self.scp = DummyGetSCP()
        self.scp.statuses = [Dataset()]
        self.scp.statuses[0].Status = 0xFF00
        self.scp.statuses[0].ErrorComment = 'Test'
        self.scp.statuses[0].OffendingElement = 0x00010001
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage])
        def on_c_store(ds, context, peer_ae):
            return 0x0000
        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert status.ErrorComment == 'Test'
        assert status.OffendingElement == 0x00010001
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_get_callback_status_int(self):
        """Test on_c_get yielding an int status"""
        self.scp = DummyGetSCP()
        self.scp.statuses = [0xFF00]
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage])
        def on_c_store(ds, context, peer_ae):
            return 0x0000

        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_get_callback_status_unknown(self):
        """Test SCP handles on_c_get yielding a unknown status"""
        self.scp = DummyGetSCP()
        self.scp.statuses = [0xFFF0]
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage])
        def on_c_store(ds, context, peer_ae):
            return 0x0000

        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFFF0
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)
        assoc.release()
        self.scp.stop()

    def test_get_callback_status_invalid(self):
        """Test SCP handles on_c_get yielding a invalid status"""
        self.scp = DummyGetSCP()
        self.scp.statuses = ['Failure']
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage])
        def on_c_store(ds, context, peer_ae):
            return 0x0000

        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xC002
        assert identifier.FailedSOPInstanceUIDList == ''
        with pytest.raises(StopIteration):
            next(result)
        assoc.release()
        self.scp.stop()

    def test_get_callback_status_none(self):
        """Test SCP handles on_c_get not yielding a status"""
        self.scp = DummyGetSCP()
        self.scp.statuses = [None]
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage])
        def on_c_store(ds, context, peer_ae):
            return 0x0000

        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xC002
        assert identifier.FailedSOPInstanceUIDList == ''
        with pytest.raises(StopIteration):
            next(result)
        assoc.release()
        self.scp.stop()

    def test_get_callback_exception(self):
        """Test SCP handles on_c_get yielding an exception"""
        self.scp = DummyGetSCP()
        def on_c_get(ds): raise ValueError
        self.scp.ae.on_c_get = on_c_get
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage])
        def on_c_store(ds, context, peer_ae):
            return 0x0000

        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xC411
        assert identifier == Dataset()
        with pytest.raises(StopIteration):
            next(result)
        assoc.release()
        self.scp.stop()

    def test_get_callback_bad_dataset(self):
        """Test SCP handles on_c_get not yielding a valid dataset"""
        self.scp = DummyGetSCP()
        self.scp.statuses = [0xFF00, 0x0000]
        self.scp.datasets = [self.fail, None]
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage])
        def on_c_store(ds, context, peer_ae):
            return 0x0000

        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xB000
        assert identifier.FailedSOPInstanceUIDList == ''
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_get_callback_invalid_dataset(self):
        """Test status returned correctly if not yielding a Dataset."""
        self.scp = DummyGetSCP()
        def on_c_store(ds, context, peer_ae):
            return 0x0000

        self.scp.no_suboperations = 3
        self.scp.statuses = [Dataset(), Dataset(), Dataset(), 0x0000]
        self.scp.statuses[0].Status = 0xFF00
        self.scp.statuses[1].Status = 0xFF00
        self.scp.statuses[2].Status = 0xFF00
        self.scp.datasets = [self.ds, 'acbdef', self.ds]
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage])
        ae.on_c_store = on_c_store

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, query_model='P')

        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xB000
        assert status.NumberOfFailedSuboperations == 1
        assert status.NumberOfWarningSuboperations == 0
        assert status.NumberOfCompletedSuboperations == 2
        assert identifier.FailedSOPInstanceUIDList == ''
        with pytest.raises(StopIteration):
            next(result)
        assoc.release()
        self.scp.stop()

    def test_get_callback_context(self):
        """Test on_c_get context parameter."""
        self.scp = DummyGetSCP()
        self.scp.no_suboperations = 1
        self.scp.statuses = [Dataset(), 0x0000]
        self.scp.statuses[0].Status = 0xFF00
        self.scp.datasets = [self.ds, None]
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage])

        def on_c_store(ds, context, peer_ae):
            assert context.AbstractSyntax == CTImageStorage.UID
            assert context.TransferSyntax[0] == '1.2.840.10008.1.2.1'
            return 0x0000

        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)

        assert self.scp.context.AbstractSyntax == PatientRootQueryRetrieveInformationModelGet.UID
        assert self.scp.context.TransferSyntax[0] == '1.2.840.10008.1.2.1'

        self.scp.stop()

    def test_get_callback_peer(self):
        """Test on_c_get peer_ae parameter."""
        self.scp = DummyGetSCP()
        self.scp.no_suboperations = 1
        self.scp.statuses = [Dataset(), 0x0000]
        self.scp.statuses[0].Status = 0xFF00
        self.scp.datasets = [self.ds, None]
        self.scp.start()

        ae = AE(ae_title='TEST_TITLE',
                scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage])

        def on_c_store(ds, context, peer_ae):
            assert peer_ae['ae_title'] == 'ANY-SCP         '
            assert peer_ae['port'] == 11112
            assert peer_ae['pdv_size'] == 16382
            assert peer_ae['address'] == 'localhost'
            return 0x0000

        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112, max_pdu=16380)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)

        # Note: can't guarantee the port number
        assert self.scp.peer_ae['address'] == '127.0.0.1'
        assert self.scp.peer_ae['pdv_size'] == 16380
        assert self.scp.peer_ae['ae_title'] == b'TEST_TITLE      '

        self.scp.stop()

    def test_store_callback_exception(self):
        """Test SCP handles send_c_store raising an exception"""
        self.scp = DummyGetSCP()
        self.scp.statuses = [0xFF00, 0x0000]
        self.scp.datasets = [self.query, None]
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage])
        def on_c_store(ds, context, peer_ae):
            return 0x0000
        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xB000
        assert identifier.FailedSOPInstanceUIDList == ''
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_scp_basic(self):
        """Test on_c_get"""
        self.scp = DummyGetSCP()
        def on_c_store(ds, context, peer_ae):
            return 0x0000
        self.scp.statuses = [0xFF00, 0xFF00]
        self.scp.datasets = [self.ds, self.ds]
        self.scp.no_suboperations = 2
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage])
        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_scp_store_failure(self):
        """Test when on_c_store returns failure status"""
        self.scp = DummyGetSCP()
        def on_c_store(ds, context, peer_ae):
            return 0xC001
        # SCP should override final success status
        self.scp.statuses = [0xFF00, 0xFF00, 0x0000]
        self.scp.datasets = [self.ds, self.ds, None]
        self.scp.no_suboperations = 2
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage])
        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xB000
        assert status.NumberOfFailedSuboperations == 2
        assert status.NumberOfWarningSuboperations == 0
        assert status.NumberOfCompletedSuboperations == 0
        assert identifier.FailedSOPInstanceUIDList == ['1.1.1', '1.1.1']
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_scp_store_warning(self):
        """Test when on_c_store returns warning status"""
        self.scp = DummyGetSCP()
        def on_c_store(ds, context, peer_ae):
            return 0xB000
        # SCP should override final success status
        self.scp.statuses = [0xFF00, 0xFF00, 0x0000]
        self.scp.datasets = [self.ds, self.ds, None]
        self.scp.no_suboperations = 3
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage])
        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xB000
        assert status.NumberOfFailedSuboperations == 0
        assert status.NumberOfWarningSuboperations == 2
        assert status.NumberOfCompletedSuboperations == 0
        assert identifier.FailedSOPInstanceUIDList == ['1.1.1', '1.1.1']
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_pending_success(self):
        """Test when on_c_get returns success status"""
        self.scp = DummyGetSCP()
        def on_c_store(ds, context, peer_ae):
            return 0x0000
        # SCP should override final warning status
        self.scp.statuses = [0xFF00, 0xB000]
        self.scp.datasets = [self.ds, None]
        self.scp.no_suboperations = 1
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage])
        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert status.NumberOfFailedSuboperations == 0
        assert status.NumberOfWarningSuboperations == 0
        assert status.NumberOfCompletedSuboperations == 1
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_pending_warning(self):
        """Test when on_c_get returns warning status"""
        self.scp = DummyGetSCP()
        def on_c_store(ds, context, peer_ae):
            return 0xB000
        # SCP should override final success status
        self.scp.statuses = [0xFF00, 0x0000]
        self.scp.datasets = [self.ds, None]
        self.scp.no_suboperations = 1
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage])
        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xB000
        assert status.NumberOfFailedSuboperations == 0
        assert status.NumberOfWarningSuboperations == 1
        assert status.NumberOfCompletedSuboperations == 0
        assert identifier.FailedSOPInstanceUIDList == '1.1.1'
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_pending_failure(self):
        """Test on_c_get returns warning status after store failure"""
        self.scp = DummyGetSCP()
        def on_c_store(ds, context, peer_ae):
            return 0xC000
        # SCP should override final warning status
        self.scp.statuses = [0xFF00]
        self.scp.datasets = [self.ds]
        self.scp.no_suboperations = 1
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage])
        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xB000
        assert status.NumberOfFailedSuboperations == 1
        assert status.NumberOfWarningSuboperations == 0
        assert status.NumberOfCompletedSuboperations == 0
        assert identifier.FailedSOPInstanceUIDList == '1.1.1'
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_multi_pending_success(self):
        """Test on_c_get returns success status after multi store success"""
        self.scp = DummyGetSCP()
        def on_c_store(ds, context, peer_ae):
            return 0x0000
        # SCP should override final warning status
        self.scp.statuses = [0xFF00, 0xFF00, 0xFF00, 0xB000]
        self.scp.datasets = [self.ds, self.ds, self.ds, None]
        self.scp.no_suboperations = 3
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage])
        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert status.NumberOfFailedSuboperations == 0
        assert status.NumberOfWarningSuboperations == 0
        assert status.NumberOfCompletedSuboperations == 3
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_multi_pending_warning(self):
        """Test on_c_get returns warning status after multi store warning"""
        self.scp = DummyGetSCP()
        def on_c_store(ds, context, peer_ae):
            return 0xB000
        # SCP should override final warning status
        self.scp.statuses = [0xFF00, 0xFF00, 0xFF00, 0xB000]
        self.scp.datasets = [self.ds, self.ds, self.ds, None]
        self.scp.no_suboperations = 3
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage])
        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xB000
        assert status.NumberOfFailedSuboperations == 0
        assert status.NumberOfWarningSuboperations == 3
        assert status.NumberOfCompletedSuboperations == 0
        assert identifier.FailedSOPInstanceUIDList == ['1.1.1',
                                                       '1.1.1',
                                                       '1.1.1']
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_multi_pending_failure(self):
        """Test on_c_get returns warning status after multi store failure"""
        self.scp = DummyGetSCP()
        def on_c_store(ds, context, peer_ae):
            return 0xC000
        # SCP should override final warning status
        self.scp.statuses = [0xFF00, 0xFF00, 0xFF00, 0xB000]
        self.scp.datasets = [self.ds, self.ds, self.ds, None]
        self.scp.no_suboperations = 3
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage])
        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xB000
        assert status.NumberOfFailedSuboperations == 3
        assert status.NumberOfWarningSuboperations == 0
        assert status.NumberOfCompletedSuboperations == 0
        assert identifier.FailedSOPInstanceUIDList == ['1.1.1',
                                                       '1.1.1',
                                                       '1.1.1']
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_get_failure(self):
        """Test when on_c_get returns failure status"""
        self.scp = DummyGetSCP()
        def on_c_store(ds, context, peer_ae):
            return 0x0000
        # SCP should override final success status
        self.scp.statuses = [0xFF00, 0xC000]
        self.scp.datasets = [self.ds, self.fail]
        self.scp.no_suboperations = 2
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage])
        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xC000
        assert status.NumberOfFailedSuboperations == 1
        assert status.NumberOfWarningSuboperations == 0
        assert status.NumberOfCompletedSuboperations == 1
        assert identifier.FailedSOPInstanceUIDList == '1.2.3'
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_get_success(self):
        """Test when on_c_get returns failure status"""
        self.scp = DummyGetSCP()
        def on_c_store(ds, context, peer_ae):
            return 0x0000
        # SCP should override final success status
        self.scp.statuses = [0xFF00]
        self.scp.datasets = [self.ds]
        self.scp.no_suboperations = 1
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage])
        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert status.NumberOfFailedSuboperations == 0
        assert status.NumberOfWarningSuboperations == 0
        assert status.NumberOfCompletedSuboperations == 1
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_get_cancel(self):
        """Test on_c_get returns cancel status"""
        self.scp = DummyGetSCP()
        def on_c_store(ds, context, peer_ae):
            return 0x0000
        # SCP should override final success status
        self.scp.statuses = [0xFF00, 0xFE00, 0x0000]
        self.scp.datasets = [self.ds, self.fail, None]
        self.scp.no_suboperations = 2
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage])
        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xFE00
        assert status.NumberOfFailedSuboperations == 0
        assert status.NumberOfWarningSuboperations == 0
        assert status.NumberOfCompletedSuboperations == 1
        assert identifier.FailedSOPInstanceUIDList == '1.2.3'
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_get_warning(self):
        """Test on_c_get returns warning status"""
        self.scp = DummyGetSCP()
        def on_c_store(ds, context, peer_ae):
            return 0xB000
        # SCP should override final success status
        self.scp.statuses = [0xFF00]
        self.scp.datasets = [self.ds]
        self.scp.no_suboperations = 1
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage])
        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xB000
        assert status.NumberOfFailedSuboperations == 0
        assert status.NumberOfWarningSuboperations == 1
        assert status.NumberOfCompletedSuboperations == 0
        assert identifier.FailedSOPInstanceUIDList =='1.1.1'
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()


class TestQRMoveServiceClass(object):
    def setup(self):
        """Run prior to each test"""
        self.query = Dataset()
        self.query.PatientName = '*'
        self.query.QueryRetrieveLevel = "PATIENT"

        self.ds = Dataset()
        self.ds.SOPClassUID = CTImageStorage().UID
        self.ds.SOPInstanceUID = '1.1.1'
        self.ds.PatientName = 'Test'

        self.fail = Dataset()
        self.fail.FailedSOPInstanceUIDList = ['1.2.3']

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
        self.scp = DummyMoveSCP()
        self.scp.statuses = [0xFF00]
        self.scp.datasets = [self.ds]
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove])
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        req = C_GET()
        req.MessageID = 1
        req.AffectedSOPClassUID = PatientRootQueryRetrieveInformationModelMove.UID
        req.Priority = 2
        req.Identifier = BytesIO(b'\x08\x00\x01\x00\x04\x00\x00\x00\x00\x08\x00\x49')
        assoc.dimse.send_msg(req, 1)
        rsp, _ = assoc.dimse.receive_msg(True)
        assert rsp.Status == 0xC510

        assoc.release()
        self.scp.stop()

    def test_move_callback_bad_yield_destination(self):
        """Test correct status returned if callback doesn't yield dest."""
        # Testing what happens if  the on_c_move callback doesn't yield
        self.scp = DummyMoveSCP()
        self.scp.statuses = [0xFF00]
        self.scp.datasets = [self.ds]
        self.scp.test_no_yield = True
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               CTImageStorage])


        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xC514
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_move_callback_bad_yield_subops(self):
        """Test correct status returned if callback doesn't yield subops."""
        self.scp = DummyMoveSCP()
        self.scp.statuses = [0xFF00]
        self.scp.datasets = [self.ds]
        self.scp.test_no_subops = True
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               CTImageStorage])


        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xC514
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_move_bad_destination(self):
        """Test correct status returned if destination bad."""
        self.scp = DummyMoveSCP()
        self.scp.statuses = [0xFF00]
        self.scp.datasets = [self.ds]
        self.scp.destination_ae = (None, 11112)
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               CTImageStorage])


        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xA801
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_move_callback_bad_subops(self):
        """Test on_c_move yielding a bad no subops"""
        self.scp = DummyMoveSCP()
        self.scp.no_suboperations = 'test'
        self.scp.statuses = [Dataset(), 0x0000]
        self.scp.statuses[0].Status = 0xFF00
        self.scp.datasets = [self.ds, None]
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               CTImageStorage])

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xC513
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_move_callback_bad_aet(self):
        """Test on_c_move yielding a bad move aet"""
        self.scp = DummyMoveSCP()
        self.scp.no_suboperations = 1
        self.scp.statuses = [Dataset(), 0x0000]
        self.scp.statuses[0].Status = 0xFF00
        self.scp.datasets = [self.ds, None]
        self.scp.destination_ae = None
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               CTImageStorage])

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xC515
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_move_callback_status_dataset(self):
        """Test on_c_move yielding a Dataset status"""
        self.scp = DummyMoveSCP()
        self.scp.no_suboperations = 1
        self.scp.statuses = [Dataset(), 0x0000]
        self.scp.statuses[0].Status = 0xFF00
        self.scp.datasets = [self.ds, None]
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               CTImageStorage])

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_move_callback_status_dataset_multi(self):
        """Test on_c_move yielding a Dataset status with other elements"""
        self.scp = DummyMoveSCP()
        self.scp.statuses = [Dataset()]
        self.scp.statuses[0].Status = 0xFF00
        self.scp.statuses[0].ErrorComment = 'Test'
        self.scp.statuses[0].OffendingElement = 0x00010001
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               CTImageStorage])

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert status.ErrorComment == 'Test'
        assert status.OffendingElement == 0x00010001
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_move_callback_status_int(self):
        """Test on_c_move yielding an int status"""
        self.scp = DummyMoveSCP()
        self.scp.statuses = [0xFF00]
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               CTImageStorage])

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_move_callback_status_unknown(self):
        """Test SCP handles on_c_move yielding a unknown status"""
        self.scp = DummyMoveSCP()
        self.scp.statuses = [0xFFF0]
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               CTImageStorage])

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFFF0
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)
        assoc.release()
        self.scp.stop()

    def test_move_callback_status_invalid(self):
        """Test SCP handles on_c_move yielding a invalid status"""
        self.scp = DummyMoveSCP()
        self.scp.statuses = ['Failure']
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               CTImageStorage])

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xC002
        assert identifier.FailedSOPInstanceUIDList == ''
        with pytest.raises(StopIteration):
            next(result)
        assoc.release()
        self.scp.stop()

    def test_move_callback_status_none(self):
        """Test SCP handles on_c_move not yielding a status"""
        self.scp = DummyMoveSCP()
        self.scp.statuses = [None]
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               CTImageStorage])

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xC002
        assert identifier.FailedSOPInstanceUIDList == ''
        with pytest.raises(StopIteration):
            next(result)
        assoc.release()
        self.scp.stop()

    def test_move_callback_exception(self):
        """Test SCP handles on_c_move yielding an exception"""
        self.scp = DummyMoveSCP()
        def on_c_move(ds, dest): raise ValueError
        self.scp.ae.on_c_move = on_c_move
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               CTImageStorage])

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xC511
        assert identifier == Dataset()
        with pytest.raises(StopIteration):
            next(result)
        assoc.release()
        self.scp.stop()

    def test_move_callback_bad_dataset(self):
        """Test SCP handles on_c_move not yielding a valid dataset"""
        self.scp = DummyMoveSCP()
        self.scp.statuses = [0xFF00, 0x0000]
        self.scp.datasets = [self.fail, None]
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               CTImageStorage])

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xB000
        assert identifier.FailedSOPInstanceUIDList == ''
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_move_callback_invalid_dataset(self):
        """Test status returned correctly if not yielding a Dataset."""
        self.scp = DummyMoveSCP()
        self.scp.no_suboperations = 2
        self.scp.statuses = [Dataset(), Dataset(), Dataset(), 0x0000]
        self.scp.statuses[0].Status = 0xFF00
        self.scp.statuses[1].Status = 0xFF00
        self.scp.statuses[2].Status = 0xFF00
        self.scp.datasets = [self.ds, 'acbdef', self.ds]
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               CTImageStorage])

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xB000
        assert status.NumberOfFailedSuboperations == 1
        assert status.NumberOfWarningSuboperations == 0
        assert status.NumberOfCompletedSuboperations == 2
        assert identifier.FailedSOPInstanceUIDList == ''
        with pytest.raises(StopIteration):
            next(result)
        assoc.release()
        self.scp.stop()

    def test_move_callback_context(self):
        """Test on_c_move context parameter."""
        self.scp = DummyMoveSCP()
        self.scp.no_suboperations = 1
        self.scp.statuses = [Dataset(), 0x0000]
        self.scp.statuses[0].Status = 0xFF00
        self.scp.datasets = [self.ds, None]
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               CTImageStorage])

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)

        assert self.scp.context.AbstractSyntax == PatientRootQueryRetrieveInformationModelMove.UID
        assert self.scp.context.TransferSyntax[0] == '1.2.840.10008.1.2.1'

        self.scp.stop()

    def test_move_callback_peer(self):
        """Test on_c_move peer_ae parameter."""
        self.scp = DummyMoveSCP()
        self.scp.no_suboperations = 1
        self.scp.statuses = [Dataset(), 0x0000]
        self.scp.statuses[0].Status = 0xFF00
        self.scp.datasets = [self.ds, None]
        self.scp.start()

        ae = AE(ae_title='MOVESCU',
                scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               CTImageStorage])

        assoc = ae.associate('localhost', 11112, max_pdu=54321)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)

        # Note: can't guarantee the port number
        assert self.scp.peer_ae['address'] == '127.0.0.1'
        assert self.scp.peer_ae['pdv_size'] == 54321
        assert self.scp.peer_ae['ae_title'] == b'MOVESCU         '

        self.scp.stop()

    def test_scp_basic(self):
        """Test on_c_move"""
        self.scp = DummyMoveSCP()
        self.scp.statuses = [0xFF00, 0xFF00]
        self.scp.datasets = [self.ds, self.ds]
        self.scp.no_suboperations = 2
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               CTImageStorage])

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_scp_store_failure(self):
        """Test when on_c_store returns failure status"""
        self.scp = DummyMoveSCP()
        # SCP should override final success status
        self.scp.statuses = [0xFF00, 0xFF00, 0x0000]
        self.scp.datasets = [self.ds, self.ds, None]
        self.scp.no_suboperations = 2
        self.scp.store_status = 0xC000
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               CTImageStorage])

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xB000
        assert status.NumberOfFailedSuboperations == 2
        assert status.NumberOfWarningSuboperations == 0
        assert status.NumberOfCompletedSuboperations == 0
        assert identifier.FailedSOPInstanceUIDList == ['1.1.1', '1.1.1']
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_move_callback_warning(self):
        """Test on_c_move returns warning status"""
        self.scp = DummyMoveSCP()
        # SCP should override final success status
        self.scp.statuses = [0xB000, 0xFF00]
        self.scp.datasets = [self.ds, self.ds]
        self.scp.no_suboperations = 2
        self.scp.store_status = 0x0000
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               CTImageStorage])

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xB000
        assert status.NumberOfFailedSuboperations == 2
        assert status.NumberOfWarningSuboperations == 0
        assert status.NumberOfCompletedSuboperations == 0
        assert identifier.FailedSOPInstanceUIDList == ''
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_scp_store_warning(self):
        """Test when on_c_store returns warning status"""
        self.scp = DummyMoveSCP()
        # SCP should override final success status
        self.scp.statuses = [0xFF00, 0xFF00, 0x0000]
        self.scp.datasets = [self.ds, self.ds, None]
        self.scp.no_suboperations = 3
        self.scp.store_status = 0xB000
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               CTImageStorage])

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xB000
        assert status.NumberOfFailedSuboperations == 0
        assert status.NumberOfWarningSuboperations == 2
        assert status.NumberOfCompletedSuboperations == 0
        assert identifier.FailedSOPInstanceUIDList == ['1.1.1', '1.1.1']
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_pending_success(self):
        """Test when on_c_move returns success status"""
        self.scp = DummyMoveSCP()
        # SCP should override final warning status
        self.scp.statuses = [0xFF00, 0xB000]
        self.scp.datasets = [self.ds, None]
        self.scp.no_suboperations = 1
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               CTImageStorage])

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert status.NumberOfFailedSuboperations == 0
        assert status.NumberOfWarningSuboperations == 0
        assert status.NumberOfCompletedSuboperations == 1
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_pending_warning(self):
        """Test when on_c_move returns warning status"""
        self.scp = DummyMoveSCP()
        # SCP should override final success status
        self.scp.statuses = [0xFF00, 0x0000]
        self.scp.datasets = [self.ds, None]
        self.scp.no_suboperations = 1
        self.scp.store_status = 0xB000
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               CTImageStorage])

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xB000
        assert status.NumberOfFailedSuboperations == 0
        assert status.NumberOfWarningSuboperations == 1
        assert status.NumberOfCompletedSuboperations == 0
        assert identifier.FailedSOPInstanceUIDList == '1.1.1'
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_pending_failure(self):
        """Test on_c_move returns warning status after store failure"""
        self.scp = DummyMoveSCP()
        # SCP should override final warning status
        self.scp.statuses = [0xFF00]
        self.scp.datasets = [self.ds]
        self.scp.no_suboperations = 1
        self.scp.store_status = 0xC000
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               CTImageStorage])

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xB000
        assert status.NumberOfFailedSuboperations == 1
        assert status.NumberOfWarningSuboperations == 0
        assert status.NumberOfCompletedSuboperations == 0
        assert identifier.FailedSOPInstanceUIDList == '1.1.1'
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_multi_pending_success(self):
        """Test on_c_move returns success status after multi store success"""
        self.scp = DummyMoveSCP()
        # SCP should override final warning status
        self.scp.statuses = [0xFF00, 0xFF00, 0xFF00, 0xB000]
        self.scp.datasets = [self.ds, self.ds, self.ds, None]
        self.scp.no_suboperations = 3
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               CTImageStorage])

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert status.NumberOfFailedSuboperations == 0
        assert status.NumberOfWarningSuboperations == 0
        assert status.NumberOfCompletedSuboperations == 3
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_multi_pending_warning(self):
        """Test on_c_move returns warning status after multi store warning"""
        self.scp = DummyMoveSCP()
        # SCP should override final warning status
        self.scp.statuses = [0xFF00, 0xFF00, 0xFF00, 0xB000]
        self.scp.datasets = [self.ds, self.ds, self.ds, None]
        self.scp.no_suboperations = 3
        self.scp.store_status = 0xB000
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               CTImageStorage])

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xB000
        assert status.NumberOfFailedSuboperations == 0
        assert status.NumberOfWarningSuboperations == 3
        assert status.NumberOfCompletedSuboperations == 0
        assert identifier.FailedSOPInstanceUIDList == ['1.1.1',
                                                       '1.1.1',
                                                       '1.1.1']
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_multi_pending_failure(self):
        """Test on_c_move returns warning status after multi store failure"""
        self.scp = DummyMoveSCP()
        # SCP should override final warning status
        self.scp.statuses = [0xFF00, 0xFF00, 0xFF00, 0xB000]
        self.scp.datasets = [self.ds, self.ds, self.ds, None]
        self.scp.no_suboperations = 3
        self.scp.store_status = 0xC000
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               CTImageStorage])

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xB000
        assert status.NumberOfFailedSuboperations == 3
        assert status.NumberOfWarningSuboperations == 0
        assert status.NumberOfCompletedSuboperations == 0
        assert identifier.FailedSOPInstanceUIDList == ['1.1.1',
                                                       '1.1.1',
                                                       '1.1.1']
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_move_failure(self):
        """Test when on_c_move returns failure status"""
        self.scp = DummyMoveSCP()
        # SCP should override final success status
        self.scp.statuses = [0xFF00, 0xC000]
        self.scp.datasets = [self.ds, self.fail]
        self.scp.no_suboperations = 2
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               CTImageStorage])

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xC000
        assert status.NumberOfFailedSuboperations == 1
        assert status.NumberOfWarningSuboperations == 0
        assert status.NumberOfCompletedSuboperations == 1
        assert identifier.FailedSOPInstanceUIDList == '1.2.3'
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_move_success(self):
        """Test when on_c_move returns failure status"""
        self.scp = DummyMoveSCP()
        # SCP should override final success status
        self.scp.statuses = [0xFF00]
        self.scp.datasets = [self.ds]
        self.scp.no_suboperations = 1
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               CTImageStorage])

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert status.NumberOfFailedSuboperations == 0
        assert status.NumberOfWarningSuboperations == 0
        assert status.NumberOfCompletedSuboperations == 1
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_move_cancel(self):
        """Test on_c_move returns cancel status"""
        self.scp = DummyMoveSCP()
        # SCP should override final success status
        self.scp.statuses = [0xFF00, 0xFE00, 0x0000]
        self.scp.datasets = [self.ds, self.fail, None]
        self.scp.no_suboperations = 2
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               CTImageStorage])

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xFE00
        assert status.NumberOfFailedSuboperations == 0
        assert status.NumberOfWarningSuboperations == 0
        assert status.NumberOfCompletedSuboperations == 1
        assert identifier.FailedSOPInstanceUIDList == '1.2.3'
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_move_warning(self):
        """Test on_c_move returns warning status"""
        self.scp = DummyMoveSCP()
        # SCP should override final success status
        self.scp.statuses = [0xFF00]
        self.scp.datasets = [self.ds]
        self.scp.no_suboperations = 1
        self.scp.store_status = 0xB000
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               CTImageStorage])

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xB000
        assert status.NumberOfFailedSuboperations == 0
        assert status.NumberOfWarningSuboperations == 1
        assert status.NumberOfCompletedSuboperations == 0
        assert identifier.FailedSOPInstanceUIDList == '1.1.1'
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()

    def test_no_associate(self):
        """Test when on_c_move returns failure status"""
        self.scp = DummyMoveSCP()
        # SCP should override final success status
        self.scp.statuses = [0xFF00]
        self.scp.datasets = [self.ds]
        self.scp.no_suboperations = 1
        self.scp.destination_ae = ('localhost', 11113)
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               CTImageStorage])

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xA801
        assert identifier == Dataset()
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        self.scp.stop()


class TestUIDtoSOPlass(object):
    def test_missing_sop(self):
        """Test raise if SOP Class not found."""
        with pytest.raises(NotImplementedError):
            uid_to_sop_class('1.2.3.4')
