"""Tests for the following Service Classes:

* QueryRetrieveServiceClass
* HangingProtocolQueryRetrieveServiceClass
* DefinedProcedureProtocolQueryRetrieveServiceClass
* ColorPaletteQueryRetrieveServiceClass
* ImplantTemplateQueryRetrieveServiceClass

"""

from io import BytesIO
import logging
import os
import threading
import time

import pytest

from pydicom import dcmread
from pydicom.dataset import Dataset
from pydicom.uid import ImplicitVRLittleEndian, ExplicitVRLittleEndian

from pynetdicom import AE, build_context, StoragePresentationContexts
from pynetdicom.dimse_primitives import C_FIND, C_GET
from pynetdicom.presentation import PresentationContext
from pynetdicom.pdu_primitives import SCP_SCU_RoleSelectionNegotiation
from pynetdicom.service_class import (
    QueryRetrieveServiceClass,
    BasicWorklistManagementServiceClass,
)
from pynetdicom.sop_class import (
    uid_to_sop_class,
    ModalityWorklistInformationFind,
    VerificationSOPClass,
    CTImageStorage,
    PatientRootQueryRetrieveInformationModelFind,
    PatientRootQueryRetrieveInformationModelGet,
    PatientRootQueryRetrieveInformationModelMove,
    CompositeInstanceRetrieveWithoutBulkDataGet,
)
from .dummy_c_scp import (
    DummyVerificationSCP,
    DummyStorageSCP,
    DummyFindSCP,
    DummyBaseSCP,
    DummyGetSCP,
    DummyMoveSCP
)

LOGGER = logging.getLogger('pynetdicom')
LOGGER.setLevel(logging.CRITICAL)
#LOGGER.setLevel(logging.DEBUG)

TEST_DS_DIR = os.path.join(os.path.dirname(__file__), 'dicom_files')
DATASET = dcmread(os.path.join(TEST_DS_DIR, 'CTImageStorage.dcm'))


def test_unknown_sop_class():
    """Test that starting the QR SCP with an unknown SOP Class raises"""
    service = QueryRetrieveServiceClass(None)
    context = PresentationContext()
    context.abstract_syntax = '1.2.3.4'
    context.add_transfer_syntax('1.2')
    with pytest.raises(ValueError):
        service.SCP(None, context, None)


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
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind,
                                 ExplicitVRLittleEndian)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        req = C_FIND()
        req.MessageID = 1
        req.AffectedSOPClassUID = PatientRootQueryRetrieveInformationModelFind
        req.Priority = 2
        req.Identifier = BytesIO(b'\x08\x00\x01\x00\x04\x00\x00\x00\x00\x08\x00\x49')
        assoc.dimse.send_msg(req, 1)
        cx_id, rsp = assoc.dimse.get_msg(True)
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
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
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

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
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

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
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

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='P')
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
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='P')
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
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='P')
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
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='P')
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
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='P')
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
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='P')
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
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='P')
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
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='P')
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
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
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
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
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
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
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
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind,
                                 '1.2.840.10008.1.2.1')
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        status, identifier = next(result)
        assert status.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        assert self.scp.context.context_id == 1
        assert self.scp.context.abstract_syntax == PatientRootQueryRetrieveInformationModelFind
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
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        status, identifier = next(result)
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

        self.scp.stop()

    def test_scp_cancelled(self):
        """Test is_cancelled works as expected."""
        cancel_results = []

        def on_c_find(ds, cx, info):
            ds = Dataset()
            ds.PatientID = '123456'
            msg_id = info['parameters']['message_id']
            cancel_results.append(info['cancelled'](msg_id))
            yield 0xFF00, ds
            time.sleep(0.5)
            cancel_results.append(info['cancelled'](1))
            cancel_results.append(info['cancelled'](msg_id))
            cancel_results.append(info['cancelled'](12))
            yield 0xFE00, None

        ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        ae.on_c_find = on_c_find
        scp = ae.start_server(('', 11112), block=False)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        identifier = Dataset()
        identifier.PatientID = '*'
        results = assoc.send_c_find(identifier, msg_id=11142, query_model='P')
        time.sleep(0.2)
        assoc.send_c_cancel(11142, 1)
        assoc.send_c_cancel(1, 3)

        status, ds = next(results)
        assert status.Status == 0xFF00
        assert ds.PatientID == '123456'
        status, ds = next(results)
        assert status.Status == 0xFE00  # Cancelled
        assert ds is None

        with pytest.raises(StopIteration):
            next(results)

        assoc.release()
        assert assoc.is_released

        assert cancel_results == [False, True, True, False]

        scp.shutdown()


class TestQRGetServiceClass(object):
    def setup(self):
        """Run prior to each test"""
        self.query = Dataset()
        self.query.PatientName = '*'
        self.query.QueryRetrieveLevel = "PATIENT"

        self.ds = Dataset()
        self.ds.file_meta = Dataset()
        self.ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
        self.ds.SOPClassUID = CTImageStorage
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

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet,
                                 ExplicitVRLittleEndian)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        req = C_GET()
        req.MessageID = 1
        req.AffectedSOPClassUID = PatientRootQueryRetrieveInformationModelGet
        req.Priority = 2
        req.Identifier = BytesIO(b'\x08\x00\x01\x00\x04\x00\x00\x00\x00\x08\x00\x49')
        assoc.dimse.send_msg(req, 1)
        cx_id, status = assoc.dimse.get_msg(True)
        assert status.Status == 0xC410

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

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = False
        role.scp_role = True

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        def on_c_store(ds, context, assoc_info):
            return 0x0000
        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
        assert assoc.is_established
        result = assoc.send_c_get(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xC413
        pytest.raises(StopIteration, next, result)

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

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = False
        role.scp_role = True

        def on_c_store(ds, context, assoc_info):
            return 0x0000
        ae.on_c_store = on_c_store
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
        assert assoc.is_established
        result = assoc.send_c_get(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        pytest.raises(StopIteration, next, result)

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

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = False
        role.scp_role = True

        def on_c_store(ds, context, assoc_info):
            return 0x0000

        ae.on_c_store = on_c_store
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
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
        pytest.raises(StopIteration, next, result)

        assoc.release()
        self.scp.stop()

    def test_get_callback_status_int(self):
        """Test on_c_get yielding an int status"""
        self.scp = DummyGetSCP()
        self.scp.statuses = [0xFF00]
        self.scp.start()

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = False
        role.scp_role = True

        def on_c_store(ds, context, assoc_info):
            return 0x0000
        ae.on_c_store = on_c_store
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
        assert assoc.is_established
        result = assoc.send_c_get(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        pytest.raises(StopIteration, next, result)

        assoc.release()
        self.scp.stop()

    def test_get_callback_status_unknown(self):
        """Test SCP handles on_c_get yielding a unknown status"""
        self.scp = DummyGetSCP()
        self.scp.statuses = [0xFFF0]
        self.scp.start()

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = False
        role.scp_role = True

        def on_c_store(ds, context, assoc_info):
            return 0x0000
        ae.on_c_store = on_c_store
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
        assert assoc.is_established
        result = assoc.send_c_get(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFFF0
        assert identifier is None
        pytest.raises(StopIteration, next, result)
        assoc.release()
        self.scp.stop()

    def test_get_callback_status_invalid(self):
        """Test SCP handles on_c_get yielding a invalid status"""
        self.scp = DummyGetSCP()
        self.scp.statuses = ['Failure']
        self.scp.start()

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = False
        role.scp_role = True

        def on_c_store(ds, context, assoc_info):
            return 0x0000
        ae.on_c_store = on_c_store
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
        assert assoc.is_established
        result = assoc.send_c_get(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xC002
        assert identifier.FailedSOPInstanceUIDList == ''
        pytest.raises(StopIteration, next, result)
        assoc.release()
        self.scp.stop()

    def test_get_callback_status_none(self):
        """Test SCP handles on_c_get not yielding a status"""
        self.scp = DummyGetSCP()
        self.scp.statuses = [None]
        self.scp.start()

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = False
        role.scp_role = True

        def on_c_store(ds, context, assoc_info):
            return 0x0000
        ae.on_c_store = on_c_store
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
        assert assoc.is_established
        result = assoc.send_c_get(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xC002
        assert identifier.FailedSOPInstanceUIDList == ''
        pytest.raises(StopIteration, next, result)
        assoc.release()
        self.scp.stop()

    def test_get_callback_exception(self):
        """Test SCP handles on_c_get yielding an exception"""
        self.scp = DummyGetSCP()
        def on_c_get(ds, context, info): raise ValueError
        self.scp.ae.on_c_get = on_c_get
        self.scp.start()

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = False
        role.scp_role = True

        def on_c_store(ds, context, assoc_info):
            return 0x0000
        ae.on_c_store = on_c_store
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
        assert assoc.is_established
        result = assoc.send_c_get(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xC411
        assert identifier == Dataset()
        pytest.raises(StopIteration, next, result)
        assoc.release()
        self.scp.stop()

    def test_get_callback_bad_dataset(self):
        """Test SCP handles on_c_get not yielding a valid dataset"""
        self.scp = DummyGetSCP()
        self.scp.statuses = [0xFF00, 0x0000]
        self.scp.datasets = [self.fail, None]
        self.scp.start()

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = False
        role.scp_role = True

        def on_c_store(ds, context, assoc_info):
            return 0x0000
        ae.on_c_store = on_c_store
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
        assert assoc.is_established
        result = assoc.send_c_get(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xB000
        assert identifier.FailedSOPInstanceUIDList == ''
        pytest.raises(StopIteration, next, result)

        assoc.release()
        self.scp.stop()

    def test_get_callback_invalid_dataset(self):
        """Test status returned correctly if not yielding a Dataset."""
        self.scp = DummyGetSCP()
        def on_c_store(ds, context, assoc_info):
            return 0x0000
        self.scp.no_suboperations = 3
        self.scp.statuses = [Dataset(), Dataset(), Dataset(), 0x0000]
        self.scp.statuses[0].Status = 0xFF00
        self.scp.statuses[1].Status = 0xFF00
        self.scp.statuses[2].Status = 0xFF00
        self.scp.datasets = [self.ds, 'acbdef', self.ds]
        self.scp.start()

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = False
        role.scp_role = True

        ae.on_c_store = on_c_store
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        assoc = ae.associate('localhost', 11112, ext_neg=[role])
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
        pytest.raises(StopIteration, next, result)
        assoc.release()
        self.scp.stop()

    def test_store_callback_exception(self):
        """Test SCP handles send_c_store raising an exception"""
        self.scp = DummyGetSCP()
        self.scp.statuses = [0xFF00, 0x0000]
        self.scp.datasets = [self.query, None]
        self.scp.start()

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = False
        role.scp_role = True

        def on_c_store(ds, context, assoc_info):
            return 0x0000
        ae.on_c_store = on_c_store
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
        assert assoc.is_established
        result = assoc.send_c_get(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xB000
        assert identifier.FailedSOPInstanceUIDList == ''
        pytest.raises(StopIteration, next, result)

        assoc.release()
        self.scp.stop()

    def test_scp_basic(self):
        """Test on_c_get"""
        self.scp = DummyGetSCP()
        def on_c_store(ds, context, assoc_info):
            return 0x0000
        self.scp.statuses = [0xFF00, 0xFF00]
        self.scp.datasets = [self.ds, self.ds]
        self.scp.no_suboperations = 2
        self.scp.start()

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = False
        role.scp_role = True

        ae.on_c_store = on_c_store
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
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
        pytest.raises(StopIteration, next, result)

        assoc.release()
        self.scp.stop()

    def test_scp_store_failure(self):
        """Test when on_c_store returns failure status"""
        self.scp = DummyGetSCP()
        def on_c_store(ds, context, assoc_info):
            return 0xC001
        # SCP should override final success status
        self.scp.statuses = [0xFF00, 0xFF00, 0x0000]
        self.scp.datasets = [self.ds, self.ds, None]
        self.scp.no_suboperations = 2
        self.scp.start()

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = False
        role.scp_role = True

        ae.on_c_store = on_c_store
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
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
        pytest.raises(StopIteration, next, result)

        assoc.release()
        self.scp.stop()

    def test_scp_store_warning(self):
        """Test when on_c_store returns warning status"""
        self.scp = DummyGetSCP()
        def on_c_store(ds, context, assoc_info):
            return 0xB000
        # SCP should override final success status
        self.scp.statuses = [0xFF00, 0xFF00, 0x0000]
        self.scp.datasets = [self.ds, self.ds, None]
        self.scp.no_suboperations = 3
        self.scp.start()

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = False
        role.scp_role = True

        ae.on_c_store = on_c_store
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
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
        pytest.raises(StopIteration, next, result)

        assoc.release()
        self.scp.stop()

    def test_pending_success(self):
        """Test when on_c_get returns success status"""
        self.scp = DummyGetSCP()
        def on_c_store(ds, context, assoc_info):
            return 0x0000
        # SCP should override final warning status
        self.scp.statuses = [0xFF00, 0xB000]
        self.scp.datasets = [self.ds, None]
        self.scp.no_suboperations = 1
        self.scp.start()

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = False
        role.scp_role = True

        ae.on_c_store = on_c_store
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
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
        pytest.raises(StopIteration, next, result)

        assoc.release()
        self.scp.stop()

    def test_pending_warning(self):
        """Test when on_c_get returns warning status"""
        self.scp = DummyGetSCP()
        def on_c_store(ds, context, assoc_info):
            return 0xB000
        # SCP should override final success status
        self.scp.statuses = [0xFF00, 0x0000]
        self.scp.datasets = [self.ds, None]
        self.scp.no_suboperations = 1
        self.scp.start()

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = False
        role.scp_role = True

        ae.on_c_store = on_c_store
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
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
        pytest.raises(StopIteration, next, result)

        assoc.release()
        self.scp.stop()

    def test_pending_failure(self):
        """Test on_c_get returns warning status after store failure"""
        self.scp = DummyGetSCP()
        def on_c_store(ds, context, assoc_info):
            return 0xC000
        # SCP should override final warning status
        self.scp.statuses = [0xFF00]
        self.scp.datasets = [self.ds]
        self.scp.no_suboperations = 1
        self.scp.start()

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = False
        role.scp_role = True

        ae.on_c_store = on_c_store
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
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
        pytest.raises(StopIteration, next, result)

        assoc.release()
        self.scp.stop()

    def test_multi_pending_success(self):
        """Test on_c_get returns success status after multi store success"""
        self.scp = DummyGetSCP()
        def on_c_store(ds, context, assoc_info):
            return 0x0000
        # SCP should override final warning status
        self.scp.statuses = [0xFF00, 0xFF00, 0xFF00, 0xB000]
        self.scp.datasets = [self.ds, self.ds, self.ds, None]
        self.scp.no_suboperations = 3
        self.scp.start()

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = False
        role.scp_role = True

        ae.on_c_store = on_c_store
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
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
        pytest.raises(StopIteration, next, result)

        assoc.release()
        self.scp.stop()

    def test_multi_pending_warning(self):
        """Test on_c_get returns warning status after multi store warning"""
        self.scp = DummyGetSCP()
        def on_c_store(ds, context, assoc_info):
            return 0xB000
        # SCP should override final warning status
        self.scp.statuses = [0xFF00, 0xFF00, 0xFF00, 0xB000]
        self.scp.datasets = [self.ds, self.ds, self.ds, None]
        self.scp.no_suboperations = 3
        self.scp.start()

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = False
        role.scp_role = True

        ae.on_c_store = on_c_store
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
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
        pytest.raises(StopIteration, next, result)

        assoc.release()
        self.scp.stop()

    def test_multi_pending_failure(self):
        """Test on_c_get returns warning status after multi store failure"""
        self.scp = DummyGetSCP()
        def on_c_store(ds, context, assoc_info):
            return 0xC000
        # SCP should override final warning status
        self.scp.statuses = [0xFF00, 0xFF00, 0xFF00, 0xB000]
        self.scp.datasets = [self.ds, self.ds, self.ds, None]
        self.scp.no_suboperations = 3
        self.scp.start()

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = False
        role.scp_role = True

        ae.on_c_store = on_c_store
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
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
        pytest.raises(StopIteration, next, result)

        assoc.release()
        self.scp.stop()

    def test_get_failure(self):
        """Test when on_c_get returns failure status"""
        self.scp = DummyGetSCP()
        def on_c_store(ds, context, assoc_info):
            return 0x0000
        # SCP should override final success status
        self.scp.statuses = [0xFF00, 0xC000]
        self.scp.datasets = [self.ds, self.fail]
        self.scp.no_suboperations = 2
        self.scp.start()

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = False
        role.scp_role = True

        ae.on_c_store = on_c_store
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
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
        pytest.raises(StopIteration, next, result)

        assoc.release()
        self.scp.stop()

    def test_get_success(self):
        """Test when on_c_get returns success status"""
        self.scp = DummyGetSCP()
        def on_c_store(ds, context, assoc_info):
            return 0x0000
        # SCP should override final success status
        self.scp.statuses = [0xFF00]
        self.scp.datasets = [self.ds]
        self.scp.no_suboperations = 1
        self.scp.start()

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = False
        role.scp_role = True

        ae.on_c_store = on_c_store
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
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
        pytest.raises(StopIteration, next, result)

        assoc.release()
        self.scp.stop()

    def test_get_cancel(self):
        """Test on_c_get returns cancel status"""
        self.scp = DummyGetSCP()
        def on_c_store(ds, context, assoc_info):
            return 0x0000
        # SCP should override final success status
        self.scp.statuses = [0xFF00, 0xFE00, 0x0000]
        self.scp.datasets = [self.ds, self.fail, None]
        self.scp.no_suboperations = 2
        self.scp.start()

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = False
        role.scp_role = True

        ae.on_c_store = on_c_store
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
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
        pytest.raises(StopIteration, next, result)

        assoc.release()
        self.scp.stop()

    def test_get_warning(self):
        """Test on_c_get returns warning status"""
        self.scp = DummyGetSCP()
        def on_c_store(ds, context, assoc_info):
            return 0xB000
        # SCP should override final success status
        self.scp.statuses = [0xFF00]
        self.scp.datasets = [self.ds]
        self.scp.no_suboperations = 1
        self.scp.start()

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = False
        role.scp_role = True

        ae.on_c_store = on_c_store
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
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
        pytest.raises(StopIteration, next, result)

        assoc.release()
        self.scp.stop()

    def test_scp_callback_context(self):
        """Test on_c_store caontext parameter"""
        self.scp = DummyGetSCP()
        self.scp.no_suboperations = 1
        self.scp.statuses = [Dataset(), 0x0000]
        self.scp.statuses[0].Status = 0xFF00
        self.identifiers = [self.ds, None]
        self.scp.start()

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet,
                                 '1.2.840.10008.1.2.1')
        ae.add_requested_context(CTImageStorage, '1.2.840.10008.1.2.1')

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = False
        role.scp_role = True

        def on_c_store(ds, context, assoc_info):
            assert context.context_id == 3
            assert context.abstract_syntax == CTImageStorage
            assert context.transfer_syntax == '1.2.840.10008.1.2.1'
            return 0x0000

        ae.on_c_store = on_c_store
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
        assert assoc.is_established
        result = assoc.send_c_get(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        pytest.raises(StopIteration, next, result)
        assoc.release()
        assert assoc.is_released

        assert self.scp.context.context_id == 1
        assert self.scp.context.abstract_syntax == PatientRootQueryRetrieveInformationModelGet
        assert self.scp.context.transfer_syntax == '1.2.840.10008.1.2.1'

        self.scp.stop()

    def test_scp_callback_info(self):
        """Test on_c_store caontext parameter"""
        self.scp = DummyGetSCP()
        self.scp.no_suboperations = 1
        self.scp.statuses = [Dataset(), 0x0000]
        self.scp.statuses[0].Status = 0xFF00
        self.identifiers = [self.ds, None]
        self.scp.start()

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet,
                                 '1.2.840.10008.1.2.1')
        ae.add_requested_context(CTImageStorage, '1.2.840.10008.1.2.1')

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = False
        role.scp_role = True

        def on_c_store(ds, context, assoc_info):
            assert context.abstract_syntax == CTImageStorage
            assert context.transfer_syntax == '1.2.840.10008.1.2.1'
            return 0x0000

        ae.on_c_store = on_c_store
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
        assert assoc.is_established
        result = assoc.send_c_get(self.query, query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        pytest.raises(StopIteration, next, result)
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

        self.scp.stop()

    def test_contexts(self):
        """Test multiple presentation contexts work OK."""
        self.scp = DummyGetSCP()
        def on_c_store(ds, context, assoc_info):
            return 0x0000
        # SCP should override final success status
        self.scp.statuses = [0xFF00]
        self.scp.datasets = [self.ds]
        self.scp.no_suboperations = 1
        self.scp.start()

        ae = AE()
        ae.requested_contexts = StoragePresentationContexts[:120]
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)

        role_selection = []
        for context in StoragePresentationContexts:
            role = SCP_SCU_RoleSelectionNegotiation()
            role.sop_class_uid = context.abstract_syntax
            role.scu_role = False
            role.scp_role = True
            role_selection.append(role)

        ae.on_c_store = on_c_store
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=role_selection)
        assert assoc.is_established

        # Check requestor's negotiated contexts
        storage_uids = [cx.abstract_syntax for cx in StoragePresentationContexts]
        for cx in assoc.accepted_contexts:
            if cx.abstract_syntax in storage_uids:
                # Requestor is acting as SCP for storage contexts
                assert cx.as_scp is True
                assert cx.as_scu is False
            else:
                # Requestor is acting as SCU for query contexts
                assert cx.as_scp is False
                assert cx.as_scu is True

        # Check acceptor's negotiated contexts
        acc_assoc = self.scp.ae.active_associations[0]
        for cx in acc_assoc.accepted_contexts:
            if cx.abstract_syntax in storage_uids:
                # Acceptor is acting as SCU for storage contexts
                assert cx.as_scp is False
                assert cx.as_scu is True
            else:
                # Acceptor is acting as SCP for query contexts
                assert cx.as_scp is True
                assert cx.as_scu is False

        assert len(acc_assoc.rejected_contexts) == 0

        assoc.release()
        self.scp.stop()

    def test_scp_cancelled(self):
        """Test is_cancelled works as expected."""
        cancel_results = []

        def on_c_get(ds, cx, info):
            ds = Dataset()
            ds.SOPClassUID = CTImageStorage
            ds.SOPInstanceUID = '1.2.3.4'
            ds.file_meta = Dataset()
            ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
            yield 2
            msg_id = info['parameters']['message_id']
            cancel_results.append(info['cancelled'](msg_id))
            yield 0xFF00, ds
            time.sleep(0.5)
            cancel_results.append(info['cancelled'](1))
            cancel_results.append(info['cancelled'](msg_id))
            cancel_results.append(info['cancelled'](12))
            yield 0xFE00, None

        def on_c_store(ds, cx, info):
            return 0x0000

        ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=True, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        ae.on_c_get = on_c_get
        ae.on_c_store = on_c_store
        scp = ae.start_server(('', 11112), block=False)

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = True
        role.scp_role = True
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
        assert assoc.is_established

        identifier = Dataset()
        identifier.PatientID = '*'
        results = assoc.send_c_get(identifier, msg_id=11142, query_model='P')
        time.sleep(0.2)
        assoc.send_c_cancel(11142, 1)
        assoc.send_c_cancel(1, 3)

        status, ds = next(results)
        assert status.Status == 0xFF00
        assert ds is None
        status, ds = next(results)
        assert status.Status == 0xFE00  # Cancelled
        assert status.NumberOfFailedSuboperations == 0
        assert status.NumberOfCompletedSuboperations == 1
        assert status.NumberOfRemainingSuboperations == 1
        assert status.NumberOfWarningSuboperations == 0
        assert ds.FailedSOPInstanceUIDList == ''

        with pytest.raises(StopIteration):
            next(results)

        assoc.release()
        assert assoc.is_released

        assert cancel_results == [False, True, True, False]

        scp.shutdown()


class TestQRMoveServiceClass(object):
    def setup(self):
        """Run prior to each test"""
        self.query = Dataset()
        self.query.PatientName = '*'
        self.query.QueryRetrieveLevel = "PATIENT"

        self.ds = Dataset()
        self.ds.file_meta = Dataset()
        self.ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
        self.ds.SOPClassUID = CTImageStorage
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

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove,
                                 ExplicitVRLittleEndian)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        req = C_GET()
        req.MessageID = 1
        req.AffectedSOPClassUID = PatientRootQueryRetrieveInformationModelMove
        req.Priority = 2
        # Encoded as Implicit VR Little
        req.Identifier = BytesIO(b'\x08\x00\x01\x00\x04\x00\x00\x00\x00\x08\x00\x49')
        assoc.dimse.send_msg(req, 1)
        cx_id, status = assoc.dimse.get_msg(True)
        assert status.Status == 0xC510

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

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5


        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xC514
        pytest.raises(StopIteration, next, result)

        assoc.release()
        self.scp.stop()

    def test_move_callback_bad_yield_subops(self):
        """Test correct status returned if callback doesn't yield subops."""
        self.scp = DummyMoveSCP()
        self.scp.statuses = [0xFF00]
        self.scp.datasets = [self.ds]
        self.scp.test_no_subops = True
        self.scp.start()

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xC514
        pytest.raises(StopIteration, next, result)

        assoc.release()
        self.scp.stop()

    def test_move_bad_destination(self):
        """Test correct status returned if destination bad."""
        self.scp = DummyMoveSCP()
        self.scp.statuses = [0xFF00]
        self.scp.datasets = [self.ds]
        self.scp.destination_ae = (None, 11112)
        self.scp.start()

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xA801
        pytest.raises(StopIteration, next, result)

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

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xC513
        pytest.raises(StopIteration, next, result)

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

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xC515
        pytest.raises(StopIteration, next, result)

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

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        pytest.raises(StopIteration, next, result)

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

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
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
        pytest.raises(StopIteration, next, result)

        assoc.release()
        self.scp.stop()

    def test_move_callback_status_int(self):
        """Test on_c_move yielding an int status"""
        self.scp = DummyMoveSCP()
        self.scp.statuses = [0xFF00]
        self.scp.start()

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        pytest.raises(StopIteration, next, result)

        assoc.release()
        self.scp.stop()

    def test_move_callback_status_unknown(self):
        """Test SCP handles on_c_move yielding a unknown status"""
        self.scp = DummyMoveSCP()
        self.scp.statuses = [0xFFF0]
        self.scp.start()

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFFF0
        assert identifier is None
        pytest.raises(StopIteration, next, result)
        assoc.release()
        self.scp.stop()

    def test_move_callback_status_invalid(self):
        """Test SCP handles on_c_move yielding a invalid status"""
        self.scp = DummyMoveSCP()
        self.scp.statuses = ['Failure']
        self.scp.start()

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xC002
        assert identifier.FailedSOPInstanceUIDList == ''
        pytest.raises(StopIteration, next, result)
        assoc.release()
        self.scp.stop()

    def test_move_callback_status_none(self):
        """Test SCP handles on_c_move not yielding a status"""
        self.scp = DummyMoveSCP()
        self.scp.statuses = [None]
        self.scp.start()

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xC002
        assert identifier.FailedSOPInstanceUIDList == ''
        pytest.raises(StopIteration, next, result)
        assoc.release()
        self.scp.stop()

    def test_move_callback_exception(self):
        """Test SCP handles on_c_move yielding an exception"""
        self.scp = DummyMoveSCP()
        def on_c_move(ds, dest, context, info): raise ValueError
        self.scp.ae.on_c_move = on_c_move
        self.scp.start()

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xC511
        assert identifier == Dataset()
        pytest.raises(StopIteration, next, result)
        assoc.release()
        self.scp.stop()

    def test_move_callback_bad_dataset(self):
        """Test SCP handles on_c_move not yielding a valid dataset"""
        self.scp = DummyMoveSCP()
        self.scp.statuses = [0xFF00, 0x0000]
        self.scp.datasets = [self.fail, None]
        self.scp.start()

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xB000
        assert identifier.FailedSOPInstanceUIDList == ''
        pytest.raises(StopIteration, next, result)

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

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
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
        pytest.raises(StopIteration, next, result)
        assoc.release()
        self.scp.stop()

    def test_scp_basic(self):
        """Test on_c_move"""
        self.scp = DummyMoveSCP()
        self.scp.statuses = [0xFF00, 0xFF00]
        self.scp.datasets = [self.ds, self.ds]
        self.scp.no_suboperations = 2
        self.scp.start()

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
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
        pytest.raises(StopIteration, next, result)

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

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
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
        pytest.raises(StopIteration, next, result)

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

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xB000
        assert status.NumberOfFailedSuboperations == 2
        assert status.NumberOfWarningSuboperations == 0
        assert status.NumberOfCompletedSuboperations == 0
        assert identifier.FailedSOPInstanceUIDList == ''
        pytest.raises(StopIteration, next, result)

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

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
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
        pytest.raises(StopIteration, next, result)

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

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
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
        pytest.raises(StopIteration, next, result)

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

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
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
        pytest.raises(StopIteration, next, result)

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

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
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
        pytest.raises(StopIteration, next, result)

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

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
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
        pytest.raises(StopIteration, next, result)

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

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
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
        pytest.raises(StopIteration, next, result)

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

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
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
        assert identifier.FailedSOPInstanceUIDList == [
            '1.1.1', '1.1.1', '1.1.1'
        ]
        pytest.raises(StopIteration, next, result)

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

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
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
        pytest.raises(StopIteration, next, result)

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

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
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
        pytest.raises(StopIteration, next, result)

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

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
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
        pytest.raises(StopIteration, next, result)

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

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
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
        pytest.raises(StopIteration, next, result)

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

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xA801
        assert identifier == Dataset()
        pytest.raises(StopIteration, next, result)

        assoc.release()
        self.scp.stop()

    def test_scp_callback_context(self):
        """Test on_c_store caontext parameter"""
        self.scp = DummyMoveSCP()
        self.scp.no_suboperations = 1
        self.scp.statuses = [Dataset(), 0x0000]
        self.scp.statuses[0].Status = 0xFF00
        self.identifiers = [self.ds, None]
        self.scp.start()

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove,
                                 '1.2.840.10008.1.2.1')
        ae.add_requested_context(CTImageStorage)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        pytest.raises(StopIteration, next, result)
        assoc.release()
        assert assoc.is_released

        assert self.scp.context.abstract_syntax == PatientRootQueryRetrieveInformationModelMove
        assert self.scp.context.transfer_syntax == '1.2.840.10008.1.2.1'

        self.scp.stop()

    def test_scp_callback_info(self):
        """Test on_c_store caontext parameter"""
        self.scp = DummyMoveSCP()
        self.scp.no_suboperations = 1
        self.scp.statuses = [Dataset(), 0x0000]
        self.scp.statuses[0].Status = 0xFF00
        self.identifiers = [self.ds, None]
        self.scp.start()

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        pytest.raises(StopIteration, next, result)
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

        assert self.scp.store_info['parameters']['originator_aet'] == b'PYNETDICOM      '
        assert self.scp.store_info['parameters']['originator_message_id'] == 1

        self.scp.stop()

    def test_scp_callback_move_aet(self):
        """Test on_c_move move_aet parameter"""
        self.scp = DummyMoveSCP()
        self.scp.no_suboperations = 1
        self.scp.statuses = [Dataset(), 0x0000]
        self.scp.statuses[0].Status = 0xFF00
        self.identifiers = [self.ds, None]
        self.scp.start()

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', query_model='P')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        pytest.raises(StopIteration, next, result)
        assoc.release()
        assert assoc.is_released

        assert self.scp.move_aet == b'TESTMOVE        '

        self.scp.stop()

    def test_scp_cancelled(self):
        """Test is_cancelled works as expected."""
        cancel_results = []

        def on_c_move(ds, move_aet, cx, info):
            ds = Dataset()
            ds.SOPClassUID = CTImageStorage
            ds.SOPInstanceUID = '1.2.3.4'
            ds.file_meta = Dataset()
            ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
            yield ('localhost', 11113)
            yield 2
            msg_id = info['parameters']['message_id']
            cancel_results.append(info['cancelled'](msg_id))
            yield 0xFF00, ds
            time.sleep(0.5)
            cancel_results.append(info['cancelled'](1))
            cancel_results.append(info['cancelled'](msg_id))
            cancel_results.append(info['cancelled'](12))
            yield 0xFE00, None

        def on_c_store(ds, cx, info):
            return 0x0000

        ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=True, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        ae.on_c_move = on_c_move
        ae.on_c_store = on_c_store
        move_scp = ae.start_server(('', 11112), block=False)
        store_scp = ae.start_server(('', 11113), block=False)

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = True
        role.scp_role = True
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
        assert assoc.is_established

        identifier = Dataset()
        identifier.PatientID = '*'
        results = assoc.send_c_move(identifier, move_aet=b'A',
                                    msg_id=11142, query_model='P')
        time.sleep(0.2)
        assoc.send_c_cancel(11142, 1)
        assoc.send_c_cancel(1, 3)

        status, ds = next(results)
        assert status.Status == 0xFF00
        assert ds is None
        status, ds = next(results)
        assert status.Status == 0xFE00  # Cancelled
        assert status.NumberOfFailedSuboperations == 0
        assert status.NumberOfCompletedSuboperations == 1
        assert status.NumberOfRemainingSuboperations == 1
        assert status.NumberOfWarningSuboperations == 0
        assert ds.FailedSOPInstanceUIDList == ''

        with pytest.raises(StopIteration):
            next(results)

        assoc.release()
        assert assoc.is_released

        assert cancel_results == [False, True, True, False]

        move_scp.shutdown()
        store_scp.shutdown()



class TestQRCompositeInstanceWithoutBulk(object):
    """Tests for QR + Composite Instance Without Bulk Data"""
    def setup(self):
        """Run prior to each test"""
        self.query = Dataset()
        self.query.PatientName = '*'
        self.query.QueryRetrieveLevel = "PATIENT"

        self.ds = Dataset()
        self.ds.file_meta = Dataset()
        self.ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
        self.ds.SOPClassUID = CTImageStorage
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

    def test_pixel_data(self):
        """Test pixel data is removed"""
        self.scp = DummyGetSCP()
        assert 'PixelData' in DATASET
        self.scp.datasets = [DATASET, None]
        self.scp.statuses = [0xFF00, 0x0000]
        self.scp.no_suboperations = 1

        def on_c_store(ds, context, assoc_info):
            assert 'PixelData' not in ds
            return 0x0000

        # SCP should override final success status
        self.scp.start()

        ae = AE()
        ae.add_requested_context(CompositeInstanceRetrieveWithoutBulkDataGet)
        ae.add_requested_context(CTImageStorage)

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scp_role = True
        role.scu_role = False

        ae.on_c_store = on_c_store
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
        assert assoc.is_established
        result = assoc.send_c_get(self.query, query_model='CB')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert status.NumberOfFailedSuboperations == 0
        assert status.NumberOfWarningSuboperations == 0
        assert status.NumberOfCompletedSuboperations == 1
        assert identifier is None
        pytest.raises(StopIteration, next, result)

        assoc.release()
        self.scp.stop()

    def test_waveform_sequence(self):
        """Test when on_c_get returns success status"""
        self.scp = DummyGetSCP()
        self.ds.SOPClassUID = CTImageStorage
        self.ds.WaveformSequence = [Dataset(), Dataset()]
        self.ds.WaveformSequence[0].WaveformData = b'\x00\x01'
        self.ds.WaveformSequence[0].WaveformBitsAllocated = 16
        self.ds.WaveformSequence[1].WaveformData = b'\x00\x02'
        self.ds.WaveformSequence[1].WaveformBitsAllocated = 8
        self.scp.datasets = [self.ds]
        self.scp.statuses = [0xFF00]
        self.scp.no_suboperations = 1

        assert 'WaveformData' in self.ds.WaveformSequence[0]
        assert 'WaveformData' in self.ds.WaveformSequence[1]

        def on_c_store(ds, context, assoc_info):
            assert 'WaveformData' not in self.ds.WaveformSequence[0]
            assert 'WaveformData' not in self.ds.WaveformSequence[1]
            return 0x0000

        # SCP should override final success status
        self.scp.start()

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scp_role = True
        role.scu_role = False

        ae = AE()
        ae.add_requested_context(CompositeInstanceRetrieveWithoutBulkDataGet)
        ae.add_requested_context(CTImageStorage)
        ae.on_c_store = on_c_store
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
        assert assoc.is_established
        result = assoc.send_c_get(self.query, query_model='CB')
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert status.NumberOfFailedSuboperations == 0
        assert status.NumberOfWarningSuboperations == 0
        assert status.NumberOfCompletedSuboperations == 1
        assert identifier is None
        pytest.raises(StopIteration, next, result)

        assoc.release()
        self.scp.stop()


class TestBasicWorklistServiceClass(object):
    """Tests for BasicWorklistManagementServiceClass."""
    def setup(self):
        """Run prior to each test"""
        self.query = Dataset()
        self.query.PatientName = '*'
        self.query.QueryRetrieveLevel = "PATIENT"

        self.ds = Dataset()
        self.ds.SOPClassUID = CTImageStorage
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

    def test_bad_abstract_syntax_raises(self):
        """Test calling the BWM SCP with an unknown UID raises exception."""
        msg = r'The supplied abstract syntax is not valid'
        with pytest.raises(ValueError, match=msg):
            bwm = BasicWorklistManagementServiceClass(None)
            context = build_context('1.2.3.4')
            bwm.SCP(None, context, None)
