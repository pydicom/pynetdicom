"""Tests for the following Service Classes:

* QueryRetrieveServiceClass
* HangingProtocolQueryRetrieveServiceClass
* DefinedProcedureProtocolQueryRetrieveServiceClass
* ColorPaletteQueryRetrieveServiceClass
* ImplantTemplateQueryRetrieveServiceClass
* ProtocolApprovalQueryRetrieveServiceClass

"""

from io import BytesIO
import os
import time

import pytest

from pydicom import dcmread
from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.uid import ImplicitVRLittleEndian, ExplicitVRLittleEndian

from pynetdicom import (
    AE, build_context, StoragePresentationContexts, evt, build_role,
    debug_logger
)
from pynetdicom.dimse_primitives import C_FIND, C_GET, C_MOVE, C_STORE
from pynetdicom.presentation import PresentationContext
from pynetdicom.pdu_primitives import SCP_SCU_RoleSelectionNegotiation
from pynetdicom.service_class import (
    QueryRetrieveServiceClass,
    BasicWorklistManagementServiceClass,
)
from pynetdicom.sop_class import (
    CTImageStorage,
    ModalityWorklistInformationFind,
    PatientRootQueryRetrieveInformationModelFind,
    PatientRootQueryRetrieveInformationModelGet,
    PatientRootQueryRetrieveInformationModelMove,
    CompositeInstanceRetrieveWithoutBulkDataGet,
)


#debug_logger()


TEST_DS_DIR = os.path.join(os.path.dirname(__file__), 'dicom_files')
DATASET = dcmread(os.path.join(TEST_DS_DIR, 'CTImageStorage.dcm'))


def test_unknown_sop_class():
    """Test that starting the QR SCP with an unknown SOP Class raises"""
    service = QueryRetrieveServiceClass(None)
    context = PresentationContext()
    context.abstract_syntax = '1.2.3.4'
    context.add_transfer_syntax('1.2')
    with pytest.raises(ValueError):
        service.SCP(None, context)


class TestQRFindServiceClass:
    """Test the QueryRetrieveFindServiceClass"""
    def setup(self):
        """Run prior to each test"""
        self.query = Dataset()
        self.query.QueryRetrieveLevel = "PATIENT"
        self.query.PatientName = '*'

        self.ae = None

    def teardown(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

    def test_bad_req_identifier(self):
        """Test SCP handles a bad request identifier"""
        def handle(event):
            try:
                ds = event.identifier
                for elem in ds.iterall():
                    pass
            except:
                yield 0xC310, None
                return

            yield 0x0000, None

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)
        ae.add_requested_context(
            PatientRootQueryRetrieveInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        req = C_FIND()
        req.MessageID = 1
        req.AffectedSOPClassUID = PatientRootQueryRetrieveInformationModelFind
        req.Priority = 2
        req.Identifier = BytesIO(b'\x08\x00\x01\x00\x40\x40\x00\x00\x00\x00\x00\x08\x00\x49')
        assoc._reactor_checkpoint.clear()
        assoc.dimse.send_msg(req, 1)
        with pytest.warns(UserWarning):
            cx_id, rsp = assoc.dimse.get_msg(True)
        assoc._reactor_checkpoint.set()
        assert rsp.Status == 0xC310

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_handler_status_dataset(self):
        """Test handler yielding a Dataset status"""
        def handle(event):
            status = Dataset()
            status.Status = 0xFF00
            yield status, self.query
            yield 0x0000, None

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)
        ae.add_requested_context(
            PatientRootQueryRetrieveInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, PatientRootQueryRetrieveInformationModelFind)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        status, identifier = next(result)
        assert status.Status == 0x0000
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_handler_status_dataset_multi(self):
        """Test handler yielding a Dataset status with other elements"""
        def handle(event):
            status = Dataset()
            status.Status = 0xFF00
            status.ErrorComment = 'Test'
            status.OffendingElement = 0x00010001
            yield status, self.query

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)
        ae.add_requested_context(
            PatientRootQueryRetrieveInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, PatientRootQueryRetrieveInformationModelFind)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert status.ErrorComment == 'Test'
        assert status.OffendingElement == 0x00010001
        status, identifier = next(result)
        assert status.Status == 0x0000
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_handler_status_int(self):
        """Test handler yielding an int status"""
        def handle(event):
            yield 0xFF00, self.query

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)
        ae.add_requested_context(
            PatientRootQueryRetrieveInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, PatientRootQueryRetrieveInformationModelFind)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        status, identifier = next(result)
        assert status.Status == 0x0000
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_handler_status_unknown(self):
        """Test SCP handles handler yielding a unknown status"""
        def handle(event):
            yield 0xFFF0,  None

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)
        ae.add_requested_context(
            PatientRootQueryRetrieveInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, PatientRootQueryRetrieveInformationModelFind)
        status, identifier = next(result)
        assert status.Status == 0xFFF0
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_handler_status_invalid(self):
        """Test SCP handles handler yielding a invalid status"""
        def handle(event):
            yield 'Failure',  None

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)
        ae.add_requested_context(
            PatientRootQueryRetrieveInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, PatientRootQueryRetrieveInformationModelFind)
        status, identifier = next(result)
        assert status.Status == 0xC002
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_handler_status_none(self):
        """Test SCP handles handler not yielding a status"""
        def handle(event):
            yield None,  self.query

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)
        ae.add_requested_context(
            PatientRootQueryRetrieveInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, PatientRootQueryRetrieveInformationModelFind)
        status, identifier = next(result)
        assert status.Status == 0xC002
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_handler_exception_prior(self):
        """Test SCP handles handler yielding an exception before yielding"""
        def handle(event):
            raise ValueError
            yield 0xFF00, self.query

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)
        ae.add_requested_context(
            PatientRootQueryRetrieveInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, PatientRootQueryRetrieveInformationModelFind)
        status, identifier = next(result)
        assert status.Status == 0xC311
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_handler_exception_default(self):
        """Test default handler raises exception"""
        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)
        ae.add_requested_context(
            PatientRootQueryRetrieveInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, PatientRootQueryRetrieveInformationModelFind)
        status, identifier = next(result)
        assert status.Status == 0xC311
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_handler_exception_during(self):
        """Test SCP handles handler yielding an exception after first yield"""
        def handle(event):
            yield 0xFF00, self.query
            raise ValueError('some message')
            yield 0xFF00, self.query
            raise NotImplementedError('different message')

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)
        ae.add_requested_context(
            PatientRootQueryRetrieveInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(
            self.query, PatientRootQueryRetrieveInformationModelFind
        )
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier == self.query
        status, identifier = next(result)
        assert status.Status == 0xC311
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_handler_bad_identifier(self):
        """Test SCP handles a bad handler identifier"""
        def handle(event):
            yield 0xFF00, None
            yield 0xFE00, None

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)
        ae.add_requested_context(
            PatientRootQueryRetrieveInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, PatientRootQueryRetrieveInformationModelFind)
        status, identifier = next(result)
        assert status.Status == 0xC312
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_pending_cancel(self):
        """Test handler yielding pending then cancel status"""
        def handle(event):
            yield 0xFF00, self.query
            yield 0xFE00, None

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)
        ae.add_requested_context(
            PatientRootQueryRetrieveInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, PatientRootQueryRetrieveInformationModelFind)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier == self.query
        status, identifier = next(result)
        assert status.Status == 0xFE00
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_pending_success(self):
        """Test handler yielding pending then success status"""
        def handle(event):
            yield 0xFF01,  self.query
            yield 0x0000, None
            yield 0xA700, None

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)
        ae.add_requested_context(
            PatientRootQueryRetrieveInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, PatientRootQueryRetrieveInformationModelFind)
        status, identifier = next(result)
        assert status.Status == 0xFF01
        assert identifier == self.query
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_pending_failure(self):
        """Test handler yielding pending then failure status"""
        def handle(event):
            yield 0xFF00, self.query
            yield 0xA700, None
            yield 0x0000, None

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)
        ae.add_requested_context(
            PatientRootQueryRetrieveInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, PatientRootQueryRetrieveInformationModelFind)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier == self.query
        status, identifier = next(result)
        assert status.Status == 0xA700
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_multi_pending_cancel(self):
        """Test handler yielding multiple pending then cancel status"""
        def handle(event):
            yield 0xFF00, self.query
            yield 0xFF01,  self.query
            yield 0xFF00, self.query
            yield 0xFE00, None
            yield 0x0000, None

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)
        ae.add_requested_context(
            PatientRootQueryRetrieveInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, PatientRootQueryRetrieveInformationModelFind)
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
        assert assoc.is_released
        scp.shutdown()

    def test_multi_pending_success(self):
        """Test handler yielding multiple pending then success status"""
        def handle(event):
            yield 0xFF00, self.query
            yield 0xFF01, self.query
            yield 0xFF00, self.query
            yield 0x0000, self.query
            yield 0xA700, None

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)
        ae.add_requested_context(
            PatientRootQueryRetrieveInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(
            self.query, PatientRootQueryRetrieveInformationModelFind
        )
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
        assert assoc.is_released
        scp.shutdown()

    def test_multi_pending_failure(self):
        """Test handler yielding multiple pending then failure status"""
        def handle(event):
            yield 0xFF00, self.query
            yield 0xFF01,  self.query
            yield 0xFF00, self.query
            yield 0xA700, self.query
            yield 0x0000, None

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)
        ae.add_requested_context(
            PatientRootQueryRetrieveInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, PatientRootQueryRetrieveInformationModelFind)
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
        assert assoc.is_released
        scp.shutdown()

    def test_scp_handler_context(self):
        """Test handler event's context attribute"""
        attrs = {}
        def handle(event):
            attrs['context'] = event.context
            attrs['assoc'] = event.assoc
            attrs['request'] = event.request
            attrs['identifier'] = event.identifier
            yield 0xFF00, self.query

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, PatientRootQueryRetrieveInformationModelFind)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        status, identifier = next(result)
        assert status.Status == 0x0000
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released

        cx = attrs['context']
        assert cx.context_id == 1
        assert cx.abstract_syntax == PatientRootQueryRetrieveInformationModelFind
        assert cx.transfer_syntax == '1.2.840.10008.1.2'

        scp.shutdown()

    def test_scp_handler_assoc(self):
        """Test handler event's assoc attribute"""
        attrs = {}
        def handle(event):
            attrs['context'] = event.context
            attrs['assoc'] = event.assoc
            attrs['request'] = event.request
            attrs['identifier'] = event.identifier
            yield 0xFF00, self.query

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, PatientRootQueryRetrieveInformationModelFind)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        status, identifier = next(result)
        assert status.Status == 0x0000
        with pytest.raises(StopIteration):
            next(result)

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
            attrs['identifier'] = event.identifier
            yield 0xFF00, self.query

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, PatientRootQueryRetrieveInformationModelFind)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        status, identifier = next(result)
        assert status.Status == 0x0000
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released

        req = attrs['request']
        assert req.MessageID == 1
        assert isinstance(req, C_FIND)

        scp.shutdown()

    def test_scp_handler_identifier(self):
        """Test handler event's identifier property"""
        attrs = {}
        def handle(event):
            attrs['context'] = event.context
            attrs['assoc'] = event.assoc
            attrs['request'] = event.request
            attrs['identifier'] = event.identifier

            ds = event.identifier
            yield 0xFF00, self.query

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, PatientRootQueryRetrieveInformationModelFind)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        status, identifier = next(result)
        assert status.Status == 0x0000
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released

        ds = attrs['identifier']
        ds.QueryRetrieveLevel = "PATIENT"
        ds.PatientName = '*'

        scp.shutdown()

    def test_scp_cancelled(self):
        """Test is_cancelled works as expected."""
        cancel_results = []
        def handle(event):
            ds = Dataset()
            ds.PatientID = '123456'
            cancel_results.append(event.is_cancelled)
            yield 0xFF00, ds
            time.sleep(0.2)
            cancel_results.append(event.is_cancelled)
            yield 0xFE00, None
            yield 0xFF00, self.query

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        identifier = Dataset()
        identifier.PatientID = '*'
        results = assoc.send_c_find(
            identifier, PatientRootQueryRetrieveInformationModelFind, msg_id=11142
        )
        assoc.send_c_cancel(1, 3)
        assoc.send_c_cancel(11142, 1)

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

        assert True in cancel_results

        scp.shutdown()

    def test_handler_aborts_before(self):
        """Test handler aborts before any yields."""
        def handle(event):
            event.assoc.abort()
            yield 0xFF00, self.query

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)
        ae.add_requested_context(
            PatientRootQueryRetrieveInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(
            self.query, PatientRootQueryRetrieveInformationModelFind
        )
        status, identifier = next(result)
        assert status == Dataset()
        assert identifier == None
        with pytest.raises(StopIteration):
            next(result)

        time.sleep(0.1)
        assert assoc.is_aborted
        scp.shutdown()

    def test_handler_aborts_before_solo(self):
        """Test handler aborts before any yields."""
        def handle(event):
            event.assoc.abort()

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)
        ae.add_requested_context(
            PatientRootQueryRetrieveInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(
            self.query, PatientRootQueryRetrieveInformationModelFind
        )
        status, identifier = next(result)
        assert status == Dataset()
        assert identifier == None
        with pytest.raises(StopIteration):
            next(result)

        time.sleep(0.1)
        assert assoc.is_aborted
        scp.shutdown()

    def test_handler_aborts_during(self):
        """Test handler aborts during any yields."""
        def handle(event):
            yield 0xFF00, self.query
            event.assoc.abort()
            yield 0xFF01,  self.query

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)
        ae.add_requested_context(
            PatientRootQueryRetrieveInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(
            self.query, PatientRootQueryRetrieveInformationModelFind
        )
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier == self.query
        status, identifier = next(result)
        with pytest.raises(StopIteration):
            next(result)

        time.sleep(0.1)
        assert assoc.is_aborted
        scp.shutdown()

    def test_handler_aborts_after(self):
        """Test handler aborts after any yields."""
        def handle(event):
            yield 0xFF00, self.query
            yield 0xFF01,  self.query
            event.assoc.abort()

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)
        ae.add_requested_context(
            PatientRootQueryRetrieveInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(
            self.query, PatientRootQueryRetrieveInformationModelFind
        )
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier == self.query
        status, identifier = next(result)
        assert status.Status == 0xFF01
        assert identifier == self.query
        status, identifier = next(result)
        with pytest.raises(StopIteration):
            next(result)

        time.sleep(0.1)
        assert assoc.is_aborted
        scp.shutdown()

    def test_handler_no_yield(self):
        """Test handler doesn't yield anything."""
        def handle_find(event):
            raise ValueError

        handlers = [(evt.EVT_C_FIND, handle_find)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)
        ae.add_requested_context(
            PatientRootQueryRetrieveInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(
            self.query, PatientRootQueryRetrieveInformationModelFind
        )
        status, identifier = next(result)
        assert status.Status == 0xC311
        assert identifier == None
        pytest.raises(StopIteration, next, result)

        assoc.release()
        time.sleep(0.1)
        assert assoc.is_released
        scp.shutdown()

    def test_success_no_identifier(self):
        """Test success response has no identifier dataset"""
        # Regression test for #571
        def handle(event):
            status = Dataset()
            status.Status = 0xFF00
            yield status, self.query

        handlers = [(evt.EVT_C_FIND, handle)]

        has_dataset = []
        def handle_dimse_in(event):
            has_dataset.append(event.message.command_set.CommandDataSetType)

        scu_handlers = [(evt.EVT_DIMSE_RECV, handle_dimse_in)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)
        ae.add_requested_context(
            PatientRootQueryRetrieveInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112, evt_handlers=scu_handlers)
        assert assoc.is_established
        result = assoc.send_c_find(
            self.query, PatientRootQueryRetrieveInformationModelFind
        )
        status, identifier = next(result)
        assert status.Status == 0xFF00
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)

        # Only the pending response should have a dataset
        assert has_dataset[0] == 1
        assert has_dataset[1] != 1
        assert len(has_dataset) == 2

        assoc.release()
        assert assoc.is_released

        scp.shutdown()


class TestQRGetServiceClass:
    def setup(self):
        """Run prior to each test"""
        self.query = Dataset()
        self.query.PatientName = '*'
        self.query.QueryRetrieveLevel = "PATIENT"

        self.ds = Dataset()
        self.ds.file_meta = FileMetaDataset()
        self.ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
        self.ds.SOPClassUID = CTImageStorage
        self.ds.SOPInstanceUID = '1.1.1'
        self.ds.PatientName = 'Test'

        self.fail = Dataset()
        self.fail.FailedSOPInstanceUIDList = ['1.2.3']

        self.ae = None

    def teardown(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

    def test_bad_req_identifier(self):
        """Test SCP handles a bad request identifier"""
        def handle(event):
            yield 1
            try:
                ds = event.identifier
                for elem in ds.iterall():
                    pass
            except:
                yield 0xC410, None
                return

            yield 0xFF00, self.ds

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(
            PatientRootQueryRetrieveInformationModelGet,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        req = C_GET()
        req.MessageID = 1
        req.AffectedSOPClassUID = PatientRootQueryRetrieveInformationModelGet
        req.Priority = 2
        req.Identifier = BytesIO(b'\x08\x00\x01\x00\x40\x40\x00\x00\x00\x00\x00\x08\x00\x49')
        assoc._reactor_checkpoint.clear()
        assoc.dimse.send_msg(req, 1)
        with pytest.warns(UserWarning):
            cx_id, status = assoc.dimse.get_msg(True)
        assoc._reactor_checkpoint.set()
        assert status.Status == 0xC410

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_get_handler_bad_subops(self):
        """Test handler yielding a bad no subops"""
        def handle(event):
            yield 'no subops'
            status = Dataset()
            status.Status = 0xFF00
            yield status, self.ds
            yield 0x0000, None

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_GET, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
        assert assoc.is_established
        result = assoc.send_c_get(self.query, PatientRootQueryRetrieveInformationModelGet)
        status, identifier = next(result)
        assert status.Status == 0xC413
        pytest.raises(StopIteration, next, result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_get_handler_status_dataset(self):
        """Test handler yielding a Dataset status"""
        def handle(event):
            yield 1
            status = Dataset()
            status.Status = 0xFF00
            yield status, self.ds
            yield 0x0000, None

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role], evt_handlers=handlers)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, PatientRootQueryRetrieveInformationModelGet)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        pytest.raises(StopIteration, next, result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_get_handler_status_dataset_multi(self):
        """Test handler yielding a Dataset status with other elements"""
        def handle(event):
            yield 1
            status = Dataset()
            status.Status = 0xFF00
            status.ErrorComment = 'Test'
            status.OffendingElement = 0x00010001
            yield status, self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role], evt_handlers=handlers)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, PatientRootQueryRetrieveInformationModelGet)
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
        assert assoc.is_released
        scp.shutdown()

    def test_get_handler_status_int(self):
        """Test handler yielding an int status"""
        def handle(event):
            yield 1
            yield 0xFF00, self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role], evt_handlers=handlers)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, PatientRootQueryRetrieveInformationModelGet)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        pytest.raises(StopIteration, next, result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_get_handler_status_unknown(self):
        """Test SCP handles handler yielding a unknown status"""
        def handle(event):
            yield 1
            yield 0xFFF0, self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role], evt_handlers=handlers)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, PatientRootQueryRetrieveInformationModelGet)
        status, identifier = next(result)
        assert status.Status == 0xFFF0
        assert identifier is None
        pytest.raises(StopIteration, next, result)
        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_get_handler_status_invalid(self):
        """Test SCP handles handler yielding a invalid status"""
        def handle(event):
            yield 1
            yield 'Failure', self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role], evt_handlers=handlers)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, PatientRootQueryRetrieveInformationModelGet)
        status, identifier = next(result)
        assert status.Status == 0xC002
        assert identifier.FailedSOPInstanceUIDList == ''
        pytest.raises(StopIteration, next, result)
        assoc.release()
        scp.shutdown()

    def test_get_handler_status_none(self):
        """Test SCP handles handler not yielding a status"""
        def handle(event):
            yield 1
            yield None, self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role], evt_handlers=handlers)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, PatientRootQueryRetrieveInformationModelGet)
        status, identifier = next(result)
        assert status.Status == 0xC002
        assert identifier.FailedSOPInstanceUIDList == ''
        pytest.raises(StopIteration, next, result)
        assoc.release()
        scp.shutdown()

    def test_get_handler_exception_default(self):
        """Test default handler raises exception"""

        def handle_store(event):
            return 0x0000

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role], evt_handlers=handlers)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, PatientRootQueryRetrieveInformationModelGet)
        status, identifier = next(result)
        assert status.Status == 0xC411
        assert identifier == Dataset()
        pytest.raises(StopIteration, next, result)
        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_get_handler_exception_prior(self):
        """Test handler raises exception"""

        def handle_store(event):
            return 0x0000

        def handle_get(event):
            raise ValueError
            return 0xFF00, self.query


        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False,
                              evt_handlers=[(evt.EVT_C_GET, handle_get)])

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role], evt_handlers=handlers)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, PatientRootQueryRetrieveInformationModelGet)
        status, identifier = next(result)
        assert status.Status == 0xC411
        assert identifier == Dataset()
        pytest.raises(StopIteration, next, result)
        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_get_handler_exception_before(self):
        """Test SCP handles handler yielding an exception after no subops"""
        def handle(event):
            raise ValueError
            yield 1
            yield 0xFF00, self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role], evt_handlers=handlers)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, PatientRootQueryRetrieveInformationModelGet)
        status, identifier = next(result)
        assert status.Status == 0xC413
        assert identifier == Dataset()
        pytest.raises(StopIteration, next, result)
        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_get_handler_exception_after_subops(self):
        """Test SCP handles handler yielding an exception after no subops"""
        def handle(event):
            yield 1
            raise ValueError
            yield 0xFF00, self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role], evt_handlers=handlers)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, PatientRootQueryRetrieveInformationModelGet)
        status, identifier = next(result)
        assert status.Status == 0xC411
        assert identifier.FailedSOPInstanceUIDList == ''
        pytest.raises(StopIteration, next, result)
        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_get_handler_exception_during(self):
        """Test SCP handler yielding an exception after first pending"""
        def handle(event):
            yield 2
            yield 0xFF00, self.ds
            raise ValueError

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role], evt_handlers=handlers)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, PatientRootQueryRetrieveInformationModelGet)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xC411
        assert identifier.FailedSOPInstanceUIDList == ''
        pytest.raises(StopIteration, next, result)
        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_get_handler_bad_dataset(self):
        """Test SCP handles handler not yielding a valid dataset"""
        def handle(event):
            yield 1
            yield 0xFF00, self.fail

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate(
            'localhost', 11112, ext_neg=[role], evt_handlers=handlers
        )
        assert assoc.is_established
        result = assoc.send_c_get(
            self.query, PatientRootQueryRetrieveInformationModelGet
        )
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xA702
        assert identifier.FailedSOPInstanceUIDList == ''
        pytest.raises(StopIteration, next, result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_get_handler_invalid_dataset(self):
        """Test status returned correctly if not yielding a Dataset."""
        def handle(event):
            yield 3
            yield 0xFF00, self.ds
            yield 0xFF00, 'abcdef'
            yield 0xFF00, self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role], evt_handlers=handlers)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, PatientRootQueryRetrieveInformationModelGet)

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
        assert assoc.is_released
        scp.shutdown()

    def test_store_handler_exception(self):
        """Test SCP handles send_c_store raising an exception"""
        def handle(event):
            yield 1
            yield 0xFF00, self.query

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate(
            'localhost', 11112, ext_neg=[role], evt_handlers=handlers
        )
        assert assoc.is_established
        result = assoc.send_c_get(
            self.query, PatientRootQueryRetrieveInformationModelGet
        )
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xA702
        assert identifier.FailedSOPInstanceUIDList == ''
        pytest.raises(StopIteration, next, result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_scp_basic(self):
        """Test handler"""
        def handle(event):
            yield 2
            yield 0xFF00, self.ds
            yield 0xFF00, self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role], evt_handlers=handlers)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, PatientRootQueryRetrieveInformationModelGet)
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
        assert assoc.is_released
        scp.shutdown()

    def test_scp_store_failure(self):
        """Test when handler returns failure status"""
        def handle(event):
            yield 2
            yield 0xFF00, self.ds
            yield 0xFF00, self.ds

        def handle_store(event):
            return 0xC001

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role], evt_handlers=handlers)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, PatientRootQueryRetrieveInformationModelGet)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xA702
        assert status.NumberOfFailedSuboperations == 2
        assert status.NumberOfWarningSuboperations == 0
        assert status.NumberOfCompletedSuboperations == 0
        assert identifier.FailedSOPInstanceUIDList == ['1.1.1', '1.1.1']
        pytest.raises(StopIteration, next, result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_scp_store_warning(self):
        """Test when handler returns warning status"""
        def handle(event):
            yield 2
            yield 0xFF00, self.ds
            yield 0xFF00, self.ds

        def handle_store(event):
            return 0xB000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate(
            'localhost', 11112, ext_neg=[role], evt_handlers=handlers
        )
        assert assoc.is_established
        result = assoc.send_c_get(
            self.query, PatientRootQueryRetrieveInformationModelGet
        )
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
        assert identifier.FailedSOPInstanceUIDList == ''
        pytest.raises(StopIteration, next, result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_pending_success(self):
        """Test when handler returns success status"""
        def handle(event):
            yield 1
            yield 0xFF00, self.ds
            yield 0xB000, None

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role], evt_handlers=handlers)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, PatientRootQueryRetrieveInformationModelGet)
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
        assert assoc.is_released
        scp.shutdown()

    def test_pending_warning(self):
        """Test when handler returns warning status"""
        def handle(event):
            yield 1
            yield 0xFF00, self.ds
            yield 0x0000, None

        def handle_store(event):
            return 0xB000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role], evt_handlers=handlers)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, PatientRootQueryRetrieveInformationModelGet)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xB000
        assert status.NumberOfFailedSuboperations == 0
        assert status.NumberOfWarningSuboperations == 1
        assert status.NumberOfCompletedSuboperations == 0
        assert identifier.FailedSOPInstanceUIDList == ''
        pytest.raises(StopIteration, next, result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_pending_failure(self):
        """Test handler returns warning status after store failure"""
        def handle(event):
            yield 1
            yield 0xFF00, self.ds

        def handle_store(event):
            return 0xC000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role], evt_handlers=handlers)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, PatientRootQueryRetrieveInformationModelGet)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xA702
        assert status.NumberOfFailedSuboperations == 1
        assert status.NumberOfWarningSuboperations == 0
        assert status.NumberOfCompletedSuboperations == 0
        assert identifier.FailedSOPInstanceUIDList == '1.1.1'
        pytest.raises(StopIteration, next, result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_multi_pending_success(self):
        """Test handler returns success status after multi store success"""
        def handle(event):
            yield 3
            yield 0xFF00, self.ds
            yield 0xFF00, self.ds
            yield 0xFF00, self.ds
            yield 0xB000, None

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role], evt_handlers=handlers)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, PatientRootQueryRetrieveInformationModelGet)
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
        assert assoc.is_released
        scp.shutdown()

    def test_multi_pending_warning(self):
        """Test handler returns warning status after multi store warning"""
        def handle(event):
            yield 3
            yield 0xFF00, self.ds
            yield 0xFF00, self.ds
            yield 0xFF00, self.ds
            yield 0xB000, None

        def handle_store(event):
            return 0xB000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role], evt_handlers=handlers)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, PatientRootQueryRetrieveInformationModelGet)
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
        assert identifier.FailedSOPInstanceUIDList == ''
        pytest.raises(StopIteration, next, result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_multi_pending_failure(self):
        """Test handler returns warning status after multi store failure"""
        def handle(event):
            yield 3
            yield 0xFF00, self.ds
            yield 0xFF00, self.ds
            yield 0xFF00, self.ds
            yield 0xB000, None

        def handle_store(event):
            return 0xC000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role], evt_handlers=handlers)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, PatientRootQueryRetrieveInformationModelGet)
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
        assert status.Status == 0xA702
        assert status.NumberOfFailedSuboperations == 3
        assert status.NumberOfWarningSuboperations == 0
        assert status.NumberOfCompletedSuboperations == 0
        assert identifier.FailedSOPInstanceUIDList == ['1.1.1',
                                                       '1.1.1',
                                                       '1.1.1']
        pytest.raises(StopIteration, next, result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_get_failure(self):
        """Test when handler returns failure status"""
        def handle(event):
            yield 2
            yield 0xFF00, self.ds
            yield 0xC000, self.fail

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate(
            'localhost', 11112, ext_neg=[role], evt_handlers=handlers
        )
        assert assoc.is_established
        result = assoc.send_c_get(
            self.query, PatientRootQueryRetrieveInformationModelGet
        )
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
        assert assoc.is_released
        scp.shutdown()

    def test_get_success(self):
        """Test when handler returns success status"""
        def handle(event):
            yield 1
            yield 0xFF00, self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role], evt_handlers=handlers)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, PatientRootQueryRetrieveInformationModelGet)
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
        assert assoc.is_released
        scp.shutdown()

    def test_get_success_user(self):
        """Test when handler returns success status"""
        def handle(event):
            yield 2
            yield 0xFF00, self.ds
            yield 0x0000, None

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role], evt_handlers=handlers)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, PatientRootQueryRetrieveInformationModelGet)
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
        assert assoc.is_released
        scp.shutdown()

    def test_get_cancel(self):
        """Test handler returns cancel status"""
        def handle(event):
            yield 2
            yield 0xFF00, self.ds
            yield 0xFE00, self.fail
            yield 0x0000, None

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role], evt_handlers=handlers)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, PatientRootQueryRetrieveInformationModelGet)
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
        assert assoc.is_released
        scp.shutdown()

    def test_get_warning(self):
        """Test handler returns warning status"""
        def handle(event):
            yield 1
            yield 0xFF00, self.ds

        def handle_store(event):
            return 0xB000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role], evt_handlers=handlers)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, PatientRootQueryRetrieveInformationModelGet)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xB000
        assert status.NumberOfFailedSuboperations == 0
        assert status.NumberOfWarningSuboperations == 1
        assert status.NumberOfCompletedSuboperations == 0
        assert identifier.FailedSOPInstanceUIDList == ''
        pytest.raises(StopIteration, next, result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_get_handler_context(self):
        """Test C-STORE handler event's context attribute"""
        attrs = {}
        def handle(event):
            attrs['context'] = event.context
            attrs['request'] = event.request
            attrs['identifier'] = event.identifier
            attrs['assoc'] = event.assoc
            yield 1
            yield 0xFF00, self.ds

        def handle_store(event):

            return 0x0000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role], evt_handlers=handlers)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, PatientRootQueryRetrieveInformationModelGet)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        pytest.raises(StopIteration, next, result)
        assoc.release()
        assert assoc.is_released

        cx = attrs['context']
        assert cx.context_id == 1
        assert cx.abstract_syntax == PatientRootQueryRetrieveInformationModelGet
        assert cx.transfer_syntax == '1.2.840.10008.1.2'

        scp.shutdown()

    def test_get_handler_request(self):
        """Test C-STORE handler event's request attribute"""
        attrs = {}
        def handle(event):
            attrs['context'] = event.context
            attrs['request'] = event.request
            attrs['identifier'] = event.identifier
            attrs['assoc'] = event.assoc
            yield 1
            yield 0xFF00, self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role], evt_handlers=handlers)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, PatientRootQueryRetrieveInformationModelGet)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        pytest.raises(StopIteration, next, result)
        assoc.release()
        assert assoc.is_released

        request = attrs['request']
        assert isinstance(request, C_GET)

        scp.shutdown()

    def test_get_handler_assoc(self):
        """Test C-STORE handler event's assoc attribute"""
        attrs = {}
        def handle(event):
            attrs['context'] = event.context
            attrs['request'] = event.request
            attrs['identifier'] = event.identifier
            attrs['assoc'] = event.assoc
            yield 1
            yield 0xFF00, self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role], evt_handlers=handlers)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, PatientRootQueryRetrieveInformationModelGet)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        pytest.raises(StopIteration, next, result)

        scp_assoc = attrs['assoc']
        assert scp_assoc == scp.active_associations[0]

        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_get_handler_identifier(self):
        """Test C-STORE handler event's dataset property"""
        attrs = {}
        def handle(event):
            attrs['context'] = event.context
            attrs['request'] = event.request
            attrs['identifier'] = event.identifier
            attrs['assoc'] = event.assoc
            yield 1
            yield 0xFF00, self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role], evt_handlers=handlers)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, PatientRootQueryRetrieveInformationModelGet)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        pytest.raises(StopIteration, next, result)
        assoc.release()
        assert assoc.is_released

        ds = attrs['identifier']
        assert ds.PatientName == '*'

        scp.shutdown()

    def test_store_handler_context(self):
        """Test C-STORE handler event's context attribute"""
        attrs = {}
        def handle(event):
            yield 1
            yield 0xFF00, self.ds

        def handle_store(event):
            attrs['context'] = event.context
            attrs['request'] = event.request
            attrs['dataset'] = event.dataset
            attrs['assoc'] = event.assoc
            return 0x0000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role], evt_handlers=handlers)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, PatientRootQueryRetrieveInformationModelGet)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        pytest.raises(StopIteration, next, result)
        assoc.release()
        assert assoc.is_released

        cx = attrs['context']
        assert cx.context_id == 3
        assert cx.abstract_syntax == CTImageStorage
        assert cx.transfer_syntax == '1.2.840.10008.1.2'

        scp.shutdown()

    def test_store_handler_request(self):
        """Test C-STORE handler event's request attribute"""
        attrs = {}
        def handle(event):
            yield 1
            yield 0xFF00, self.ds

        def handle_store(event):
            attrs['context'] = event.context
            attrs['request'] = event.request
            attrs['dataset'] = event.dataset
            attrs['assoc'] = event.assoc
            return 0x0000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role], evt_handlers=handlers)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, PatientRootQueryRetrieveInformationModelGet)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        pytest.raises(StopIteration, next, result)
        assoc.release()
        assert assoc.is_released

        request = attrs['request']
        assert isinstance(request, C_STORE)

        scp.shutdown()

    def test_store_handler_assoc(self):
        """Test C-STORE handler event's assoc attribute"""
        attrs = {}
        def handle(event):
            yield 1
            yield 0xFF00, self.ds

        def handle_store(event):
            attrs['context'] = event.context
            attrs['request'] = event.request
            attrs['dataset'] = event.dataset
            attrs['assoc'] = event.assoc
            return 0x0000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role], evt_handlers=handlers)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, PatientRootQueryRetrieveInformationModelGet)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        pytest.raises(StopIteration, next, result)

        store_assoc = attrs['assoc']
        assert store_assoc == assoc

        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_store_handler_dataset(self):
        """Test C-STORE handler event's dataset property"""
        attrs = {}
        def handle(event):
            yield 1
            yield 0xFF00, self.ds

        def handle_store(event):
            attrs['context'] = event.context
            attrs['request'] = event.request
            attrs['dataset'] = event.dataset
            attrs['assoc'] = event.assoc
            return 0x0000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role], evt_handlers=handlers)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, PatientRootQueryRetrieveInformationModelGet)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        pytest.raises(StopIteration, next, result)
        assoc.release()
        assert assoc.is_released

        ds = attrs['dataset']
        assert ds.PatientName == 'Test'

        scp.shutdown()

    def test_store_handler_bad(self):
        """Test C-STORE handler event's assoc attribute"""
        attrs = {}
        def handle(event):
            yield 1
            yield 0xFF00, self.ds

        def handle_store(event):
            raise ValueError

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role], evt_handlers=handlers)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, PatientRootQueryRetrieveInformationModelGet)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xA702
        assert identifier.FailedSOPInstanceUIDList == '1.1.1'
        pytest.raises(StopIteration, next, result)

        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_contexts(self):
        """Test multiple presentation contexts work OK."""
        def handle(event):
            yield 1
            yield 0xFF00, self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.requested_contexts = StoragePresentationContexts[:120]
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)

        roles = []
        for cx in StoragePresentationContexts[:120]:
            roles.append(build_role(cx.abstract_syntax, scp_role=True))
            ae.add_supported_context(cx.abstract_syntax, scu_role=False, scp_role=True)

        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=roles, evt_handlers=handlers)

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
        for cx in scp.active_associations[0].accepted_contexts:
            if cx.abstract_syntax in storage_uids:
                # Acceptor is acting as SCU for storage contexts
                assert cx.as_scp is False
                assert cx.as_scu is True
            else:
                # Acceptor is acting as SCP for query contexts
                assert cx.as_scp is True
                assert cx.as_scu is False

        assert len(scp.active_associations[0].rejected_contexts) == 0

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_scp_cancelled(self):
        """Test is_cancelled works as expected."""
        cancel_results = []

        def handle(event):
            ds = Dataset()
            ds.SOPClassUID = CTImageStorage
            ds.SOPInstanceUID = '1.2.3.4'
            ds.file_meta = FileMetaDataset()
            ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
            yield 2
            cancel_results.append(event.is_cancelled)
            yield 0xFF00, ds
            time.sleep(0.2)
            cancel_results.append(event.is_cancelled)
            yield 0xFE00, None

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role], evt_handlers=handlers)
        assert assoc.is_established

        identifier = Dataset()
        identifier.PatientID = '*'
        results = assoc.send_c_get(
            identifier, PatientRootQueryRetrieveInformationModelGet, msg_id=11142
        )
        assoc.send_c_cancel(1, 3)
        assoc.send_c_cancel(11142, 1)

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

        assert True in cancel_results

        scp.shutdown()

    def test_subop_message_id(self):
        """The that the C-STORE sub-operation Message ID iterates."""
        def handle(event):
            yield 3
            yield 0xFF00, self.ds
            yield 0xFF00, self.ds
            yield 0xFF00, self.ds
            yield 0xB000, None

        msg_ids = []
        def handle_store(event):
            msg_ids.append(event.request.MessageID)
            return 0x0000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role], evt_handlers=handlers)
        assert assoc.is_established
        result = assoc.send_c_get(self.query, PatientRootQueryRetrieveInformationModelGet)
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
        assert assoc.is_released
        scp.shutdown()

        assert msg_ids == [2, 3, 4]

    def test_subop_message_id_rollover(self):
        """The that the C-STORE sub-operation Message ID iterates."""
        def handle(event):
            yield 3
            yield 0xFF00, self.ds
            yield 0xFF00, self.ds
            yield 0xFF00, self.ds
            yield 0xB000, None

        msg_ids = []
        def handle_store(event):
            msg_ids.append(event.request.MessageID)
            return 0x0000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role], evt_handlers=handlers)
        assert assoc.is_established
        result = assoc.send_c_get(
            self.query, PatientRootQueryRetrieveInformationModelGet, msg_id=65534
        )
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
        assert assoc.is_released
        scp.shutdown()

        assert msg_ids == [65535, 1, 2]

    def test_handler_aborts_before(self):
        """Test handler aborting the association before any yields"""
        def handle(event):
            event.assoc.abort()
            yield 1
            yield 0xFF00, self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate(
            'localhost', 11112, ext_neg=[role], evt_handlers=handlers
        )
        assert assoc.is_established
        result = assoc.send_c_get(
            self.query, PatientRootQueryRetrieveInformationModelGet
        )
        status, identifier = next(result)
        assert status == Dataset()
        assert identifier is None
        pytest.raises(StopIteration, next, result)

        time.sleep(0.1)
        assert assoc.is_aborted
        scp.shutdown()

    def test_handler_aborts_before_solo(self):
        """Test handler aborting the association before any yields"""
        def handle(event):
            event.assoc.abort()

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate(
            'localhost', 11112, ext_neg=[role], evt_handlers=handlers
        )
        assert assoc.is_established
        result = assoc.send_c_get(
            self.query, PatientRootQueryRetrieveInformationModelGet
        )
        status, identifier = next(result)
        assert status == Dataset()
        assert identifier is None
        pytest.raises(StopIteration, next, result)

        time.sleep(0.1)
        assert assoc.is_aborted
        scp.shutdown()

    def test_handler_aborts_during_noops(self):
        """Test handler aborting the association before any yields"""
        def handle(event):
            yield 1
            event.assoc.abort()
            yield 0xFF00, self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate(
            'localhost', 11112, ext_neg=[role], evt_handlers=handlers
        )
        assert assoc.is_established
        result = assoc.send_c_get(
            self.query, PatientRootQueryRetrieveInformationModelGet
        )
        status, identifier = next(result)
        assert status == Dataset()
        assert identifier is None
        pytest.raises(StopIteration, next, result)

        time.sleep(0.1)
        assert assoc.is_aborted
        scp.shutdown()

    def test_handler_aborts_during(self):
        """Test handler aborting the association before any yields"""
        def handle(event):
            yield 1
            yield 0xFF00, self.ds
            event.assoc.abort()
            yield 0xFF00, self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate(
            'localhost', 11112, ext_neg=[role], evt_handlers=handlers
        )
        assert assoc.is_established
        result = assoc.send_c_get(
            self.query, PatientRootQueryRetrieveInformationModelGet
        )
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status == Dataset()
        assert identifier is None
        pytest.raises(StopIteration, next, result)

        time.sleep(0.1)
        assert assoc.is_aborted
        scp.shutdown()

    def test_handler_aborts_after(self):
        """Test handler aborting the association before any yields"""
        def handle(event):
            yield 2
            yield 0xFF00, self.ds
            yield 0xFF00, self.ds
            event.assoc.abort()

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate(
            'localhost', 11112, ext_neg=[role], evt_handlers=handlers
        )
        assert assoc.is_established
        result = assoc.send_c_get(
            self.query, PatientRootQueryRetrieveInformationModelGet
        )
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status == Dataset()
        assert identifier is None
        pytest.raises(StopIteration, next, result)

        time.sleep(0.1)
        assert assoc.is_aborted
        scp.shutdown()

    def test_success_no_identifier(self):
        """Test pending and success responses have no identifier dataset"""
        # Regression test for #571
        def handle(event):
            yield 1
            status = Dataset()
            status.Status = 0xFF00
            yield status, self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        has_dataset = []
        def handle_dimse_in(event):
            has_dataset.append(event.message.command_set.CommandDataSetType)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [
            (evt.EVT_C_STORE, handle_store),
            (evt.EVT_DIMSE_RECV, handle_dimse_in)
        ]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate(
            'localhost', 11112, ext_neg=[role], evt_handlers=handlers
        )
        assert assoc.is_established
        result = assoc.send_c_get(
            self.query, PatientRootQueryRetrieveInformationModelGet
        )
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        pytest.raises(StopIteration, next, result)

        # The C-GET pending and success responses shouldn't have a dataset
        assert len(has_dataset) == 3
        assert has_dataset[0] == 1  # C-STORE rq
        assert has_dataset[1] != 1  # C-GET rsp pending
        assert has_dataset[2] != 1  # C-GET rsp success

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_scp_store_warning_failure(self):
        """Test when handler returns warning status if not all failed"""
        rsp = [0xC000, 0xB000]

        def handle(event):
            yield 2
            yield 0xFF00, self.ds
            yield 0xFF00, self.ds

        def handle_store(event):
            return rsp.pop()

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate(
            'localhost', 11112, ext_neg=[role], evt_handlers=handlers
        )
        assert assoc.is_established
        result = assoc.send_c_get(
            self.query, PatientRootQueryRetrieveInformationModelGet
        )
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xB000
        assert status.NumberOfFailedSuboperations == 1
        assert status.NumberOfWarningSuboperations == 1
        assert status.NumberOfCompletedSuboperations == 0
        assert identifier.FailedSOPInstanceUIDList == '1.1.1'
        pytest.raises(StopIteration, next, result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()


class TestQRMoveServiceClass:
    def setup(self):
        """Run prior to each test"""
        self.query = Dataset()
        self.query.PatientName = '*'
        self.query.QueryRetrieveLevel = "PATIENT"

        self.ds = Dataset()
        self.ds.file_meta = FileMetaDataset()
        self.ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
        self.ds.SOPClassUID = CTImageStorage
        self.ds.SOPInstanceUID = '1.1.1'
        self.ds.PatientName = 'Test'

        self.fail = Dataset()
        self.fail.FailedSOPInstanceUIDList = ['1.2.3']

        self.destination = ('localhost', 11112)

        self.ae = None

    def teardown(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

    def test_bad_req_identifier(self):
        """Test SCP handles a bad request identifier"""
        def handle(event):
            yield '127.0.0.1', 11112
            yield 1
            try:
                ds = event.identifier
                for elem in ds.iterall():
                    pass
            except:
                yield 0xC410, None
                return

            yield 1
            yield 0xFF00, self.ds

        handlers = [(evt.EVT_C_MOVE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(
            PatientRootQueryRetrieveInformationModelMove,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        req = C_MOVE()
        req.MessageID = 1
        req.MoveDestination = b'Test'
        req.AffectedSOPClassUID = PatientRootQueryRetrieveInformationModelMove
        req.Priority = 2
        # Encoded as Implicit VR Little
        req.Identifier = BytesIO(
            b'\x08\x00\x01\x00\x40\x40\x00\x00\x00\x00\x00\x08\x00\x49'
        )
        assoc._reactor_checkpoint.clear()
        assoc.dimse.send_msg(req, 1)
        with pytest.warns(UserWarning):
            cx_id, status = assoc.dimse.get_msg(True)
        assoc._reactor_checkpoint.set()
        assert status.Status == 0xC410

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_move_handler_bad_yield_destination(self):
        """Test correct status returned if handler doesn't yield dest."""
        # Testing what happens if the handler doesn't yield
        def handle(event):
            return

        handlers = [(evt.EVT_C_MOVE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        result = assoc.send_c_move(self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove)
        status, identifier = next(result)
        assert status.Status == 0xC514
        pytest.raises(StopIteration, next, result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_move_handler_bad_yield_subops(self):
        """Test correct status returned if handler doesn't yield subops."""
        def handle(event):
            yield self.destination
            return

        handlers = [(evt.EVT_C_MOVE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        result = assoc.send_c_move(self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove)
        status, identifier = next(result)
        assert status.Status == 0xC513
        pytest.raises(StopIteration, next, result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_move_bad_destination(self):
        """Test correct status returned if destination bad."""
        def handle(event):
            yield (None, 11112)
            yield 1
            yield 0xFF00, self.ds

        handlers = [(evt.EVT_C_MOVE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        result = assoc.send_c_move(self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove)
        status, identifier = next(result)
        assert status.Status == 0xA801
        pytest.raises(StopIteration, next, result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_move_handler_bad_subops(self):
        """Test handler yielding a bad no subops"""
        def handle(event):
            yield ('127.0.0.1', 11112)
            yield 'test'
            yield 0xFF00, self.ds

        handlers = [(evt.EVT_C_MOVE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove)
        status, identifier = next(result)
        assert status.Status == 0xC513
        pytest.raises(StopIteration, next, result)

        assoc.release()
        scp.shutdown()

    def test_move_handler_bad_aet(self):
        """Test handler yielding a bad move aet"""
        def handle(event):
            yield None
            yield 1
            yield 0xFF00, self.ds

        handlers = [(evt.EVT_C_MOVE, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove)
        status, identifier = next(result)
        assert status.Status == 0xC515
        pytest.raises(StopIteration, next, result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_move_handler_status_dataset(self):
        """Test handler yielding a Dataset status"""
        def handle(event):
            yield self.destination
            yield 1
            status = Dataset()
            status.Status = 0xFF00
            yield status, self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        pytest.raises(StopIteration, next, result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_move_handler_status_dataset_multi(self):
        """Test handler yielding a Dataset status with other elements"""
        def handle(event):
            yield self.destination
            yield 1
            status = Dataset()
            status.Status = 0xFF00
            status.ErrorComment = 'Test'
            status.OffendingElement = 0x00010001
            yield status, self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove)
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
        assert assoc.is_released
        scp.shutdown()

    def test_move_handler_status_int(self):
        """Test handler yielding an int status"""
        def handle(event):
            yield self.destination
            yield 1
            yield 0xFF00, self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        pytest.raises(StopIteration, next, result)

        assoc.release()
        scp.shutdown()

    def test_move_handler_status_unknown(self):
        """Test SCP handles handler yielding a unknown status"""
        def handle(event):
            yield self.destination
            yield 1
            yield 0xFFF0, self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove)
        status, identifier = next(result)
        assert status.Status == 0xFFF0
        assert identifier is None
        pytest.raises(StopIteration, next, result)
        assoc.release()
        scp.shutdown()

    def test_move_handler_status_invalid(self):
        """Test SCP handles handler yielding a invalid status"""
        def handle(event):
            yield self.destination
            yield 1
            yield 'Failure', self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove)
        status, identifier = next(result)
        assert status.Status == 0xC002
        assert identifier.FailedSOPInstanceUIDList == ''
        pytest.raises(StopIteration, next, result)
        assoc.release()
        scp.shutdown()

    def test_move_handler_status_none(self):
        """Test SCP handles handler not yielding a status"""
        def handle(event):
            yield self.destination
            yield 1
            yield None, self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove)
        status, identifier = next(result)
        assert status.Status == 0xC002
        assert identifier.FailedSOPInstanceUIDList == ''
        pytest.raises(StopIteration, next, result)
        assoc.release()
        scp.shutdown()

    def test_move_handler_exception_default(self):
        """Test SCP default handler"""
        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove)
        status, identifier = next(result)
        assert status.Status == 0xC511
        assert identifier == Dataset()
        pytest.raises(StopIteration, next, result)
        assoc.release()
        scp.shutdown()

    def test_move_handler_exception_prior(self):
        """Test SCP handles handler yielding an exception before destination"""
        def handle_store(event):
            return 0x0000

        def handle_move(event):
            raise ValueError
            return 0x0000, None

        handlers = [
            (evt.EVT_C_STORE, handle_store),
            (evt.EVT_C_MOVE, handle_move),
        ]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove)
        status, identifier = next(result)
        assert status.Status == 0xC511
        assert identifier == Dataset()
        pytest.raises(StopIteration, next, result)
        assoc.release()
        scp.shutdown()

    def test_move_handler_exception_destination(self):
        """Test SCP handles handler yielding an exception before destination"""
        def handle(event):
            raise ValueError
            yield self.destination
            yield 1
            yield 0xFF00, self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove)
        status, identifier = next(result)
        assert status.Status == 0xC514
        assert identifier == Dataset()
        pytest.raises(StopIteration, next, result)
        assoc.release()
        scp.shutdown()

    def test_move_handler_exception_subops(self):
        """Test SCP handles handler yielding an exception before subops"""
        def handle(event):
            yield self.destination
            raise ValueError
            yield 1
            yield 0xFF00, self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(
            self.query,
            b'TESTMOVE',
            PatientRootQueryRetrieveInformationModelMove
        )
        status, identifier = next(result)
        assert status.Status == 0xC513
        assert identifier == Dataset()
        pytest.raises(StopIteration, next, result)
        assoc.release()
        scp.shutdown()

    def test_move_handler_exception_ops(self):
        """Test SCP handles handler yielding an exception before ops"""
        def handle(event):
            yield self.destination
            yield 1
            raise ValueError
            yield 0xFF00, self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove)
        status, identifier = next(result)
        assert status.Status == 0xC511
        assert identifier.FailedSOPInstanceUIDList == ''
        pytest.raises(StopIteration, next, result)
        assoc.release()
        scp.shutdown()

    def test_move_handler_exception_during(self):
        """Test SCP handles handler yielding an exception during ops"""
        def handle(event):
            yield self.destination
            yield 2
            yield 0xFF00, self.ds
            raise ValueError

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xC511
        assert identifier.FailedSOPInstanceUIDList == ''
        pytest.raises(StopIteration, next, result)
        assoc.release()
        scp.shutdown()

    def test_move_handler_bad_dataset(self):
        """Test SCP handles handler not yielding a valid dataset"""
        def handle(event):
            yield self.destination
            yield 1
            yield 0xFF00, self.fail

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xA702
        assert identifier.FailedSOPInstanceUIDList == ''
        pytest.raises(StopIteration, next, result)

        assoc.release()
        scp.shutdown()

    def test_move_handler_invalid_dataset(self):
        """Test status returned correctly if not yielding a Dataset."""
        def handle(event):
            yield self.destination
            yield 2
            yield 0xFF00, self.ds
            yield 0xFF00, 'acdef'
            yield 0xFF00, self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove)
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
        scp.shutdown()

    def test_scp_basic(self):
        """Test handler"""
        def handle(event):
            yield self.destination
            yield 2
            yield 0xFF00, self.ds
            yield 0xFF00, self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove)
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
        scp.shutdown()

    def test_scp_store_failure(self):
        """Test when handler returns failure status"""
        def handle(event):
            yield self.destination
            yield 2
            yield 0xFF00, self.ds
            yield 0xFF00, self.ds
            yield 0x0000, None

        def handle_store(event):
            return 0xC000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xA702
        assert status.NumberOfFailedSuboperations == 2
        assert status.NumberOfWarningSuboperations == 0
        assert status.NumberOfCompletedSuboperations == 0
        assert identifier.FailedSOPInstanceUIDList == ['1.1.1', '1.1.1']
        pytest.raises(StopIteration, next, result)

        assoc.release()
        scp.shutdown()

    def test_move_handler_warning(self):
        """Test handler returns warning status"""
        def handle(event):
            yield self.destination
            yield 2
            yield 0xB000, self.ds
            yield 0xFF00, self.ds
            yield 0x0000, None

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove)
        status, identifier = next(result)
        assert status.Status == 0xB000
        assert status.NumberOfFailedSuboperations == 2
        assert status.NumberOfWarningSuboperations == 0
        assert status.NumberOfCompletedSuboperations == 0
        assert identifier.FailedSOPInstanceUIDList == ''
        pytest.raises(StopIteration, next, result)

        assoc.release()
        scp.shutdown()

    def test_scp_store_warning(self):
        """Test when handler returns warning status"""
        def handle(event):
            yield self.destination
            yield 2
            yield 0xFF00, self.ds
            yield 0xFF00, self.ds
            yield 0x0000, None

        def handle_store(event):
            return 0xB000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove)
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
        assert identifier.FailedSOPInstanceUIDList == ''
        pytest.raises(StopIteration, next, result)

        assoc.release()
        scp.shutdown()

    def test_pending_success(self):
        """Test when handler returns success status"""
        def handle(event):
            yield self.destination
            yield 1
            yield 0xFF00, self.ds
            yield 0x0000, None

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove)
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
        scp.shutdown()

    def test_pending_warning(self):
        """Test when handler returns warning status"""
        def handle(event):
            yield self.destination
            yield 1
            yield 0xFF00, self.ds
            yield 0x0000, None

        def handle_store(event):
            return 0xB000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xB000
        assert status.NumberOfFailedSuboperations == 0
        assert status.NumberOfWarningSuboperations == 1
        assert status.NumberOfCompletedSuboperations == 0
        assert identifier.FailedSOPInstanceUIDList == ''
        pytest.raises(StopIteration, next, result)

        assoc.release()
        scp.shutdown()

    def test_pending_failure(self):
        """Test handler returns warning status after store failure"""
        def handle(event):
            yield self.destination
            yield 1
            yield 0xFF00, self.ds
            yield 0x0000, None

        def handle_store(event):
            return 0xC000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xA702
        assert status.NumberOfFailedSuboperations == 1
        assert status.NumberOfWarningSuboperations == 0
        assert status.NumberOfCompletedSuboperations == 0
        assert identifier.FailedSOPInstanceUIDList == '1.1.1'
        pytest.raises(StopIteration, next, result)

        assoc.release()
        scp.shutdown()

    def test_multi_pending_success(self):
        """Test handler returns success status after multi store success"""
        def handle(event):
            yield self.destination
            yield 3
            yield 0xFF00, self.ds
            yield 0xFF00, self.ds
            yield 0xFF00, self.ds
            yield 0xB000, None

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove)
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
        scp.shutdown()

    def test_multi_pending_warning(self):
        """Test handler returns warning status after multi store warning"""
        def handle(event):
            yield self.destination
            yield 3
            yield 0xFF00, self.ds
            yield 0xFF00, self.ds
            yield 0xFF00, self.ds
            yield 0xB000, None

        def handle_store(event):
            return 0xB000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove)
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
        assert identifier.FailedSOPInstanceUIDList == ''
        pytest.raises(StopIteration, next, result)

        assoc.release()
        scp.shutdown()

    def test_multi_pending_failure(self):
        """Test handler returns warning status after multi store failure"""
        def handle(event):
            yield self.destination
            yield 3
            yield 0xFF00, self.ds
            yield 0xFF00, self.ds
            yield 0xFF00, self.ds
            yield 0xB000, None

        def handle_store(event):
            return 0xC000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove)
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
        assert status.Status == 0xA702
        assert status.NumberOfFailedSuboperations == 3
        assert status.NumberOfWarningSuboperations == 0
        assert status.NumberOfCompletedSuboperations == 0
        assert identifier.FailedSOPInstanceUIDList == [
            '1.1.1', '1.1.1', '1.1.1'
        ]
        pytest.raises(StopIteration, next, result)

        assoc.release()
        scp.shutdown()

    def test_move_failure(self):
        """Test when handler returns failure status"""
        def handle(event):
            yield self.destination
            yield 2
            yield 0xFF00, self.ds
            yield 0xC000, self.fail

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove)
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
        scp.shutdown()

    def test_move_success(self):
        """Test when handler returns success status"""
        def handle(event):
            yield self.destination
            yield 1
            yield 0xFF00, self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(
            self.query, b'TESTMOVE',
            PatientRootQueryRetrieveInformationModelMove
        )
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
        scp.shutdown()

    def test_move_cancel(self):
        """Test handler returns cancel status"""
        def handle(event):
            yield self.destination
            yield 2
            yield 0xFF00, self.ds
            yield 0xFE00, self.fail
            yield 0x0000, None

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove)
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
        scp.shutdown()

    def test_move_warning(self):
        """Test handler returns warning status"""
        def handle(event):
            yield self.destination
            yield 1
            yield 0xFF00, self.ds

        def handle_store(event):
            return 0xB000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xB000
        assert status.NumberOfFailedSuboperations == 0
        assert status.NumberOfWarningSuboperations == 1
        assert status.NumberOfCompletedSuboperations == 0
        assert identifier.FailedSOPInstanceUIDList == ''
        pytest.raises(StopIteration, next, result)

        assoc.release()
        scp.shutdown()

    def test_no_associate(self):
        """Test when handler returns failure status"""
        def handle(event):
            yield ('localhost', 11113)
            yield 1
            yield 0xFF00, self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove)
        status, identifier = next(result)
        assert status.Status == 0xA801
        assert identifier == Dataset()
        pytest.raises(StopIteration, next, result)

        assoc.release()
        scp.shutdown()

    def test_scp_handler_context(self):
        """Test hander event's context attribute"""
        attrs = {}
        def handle(event):
            attrs['request'] = event.request
            attrs['identifier'] = event.identifier
            attrs['assoc'] = event.assoc
            attrs['context'] = event.context

            yield self.destination
            yield 1
            yield 0xFF00, self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        pytest.raises(StopIteration, next, result)
        assoc.release()
        assert assoc.is_released

        cx = attrs['context']
        assert cx.abstract_syntax == PatientRootQueryRetrieveInformationModelMove
        assert cx.transfer_syntax == '1.2.840.10008.1.2'

        scp.shutdown()

    def test_scp_handler_assoc(self):
        """Test hander event's context attribute"""
        attrs = {}
        def handle(event):
            attrs['request'] = event.request
            attrs['identifier'] = event.identifier
            attrs['assoc'] = event.assoc
            attrs['context'] = event.context

            yield self.destination
            yield 1
            yield 0xFF00, self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        pytest.raises(StopIteration, next, result)

        scp_assoc = attrs['assoc']
        assert scp_assoc == scp.active_associations[0]

        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_scp_handler_request(self):
        """Test hander event's context attribute"""
        attrs = {}
        def handle(event):
            attrs['request'] = event.request
            attrs['identifier'] = event.identifier
            attrs['assoc'] = event.assoc
            attrs['context'] = event.context

            yield self.destination
            yield 1
            yield 0xFF00, self.ds

        def handle_store(event):
            attrs['originator_msg_id'] = event.request.MoveOriginatorMessageID
            attrs['originator_aet'] = (
                event.request.MoveOriginatorApplicationEntityTitle
            )
            return 0x0000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(
            self.query, b'TESTMOVE',
            PatientRootQueryRetrieveInformationModelMove,
            msg_id=1234
        )
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        pytest.raises(StopIteration, next, result)
        assoc.release()
        assert assoc.is_released

        req = attrs['request']
        assert isinstance(req, C_MOVE)
        assert req.MoveDestination == b'TESTMOVE'

        assert attrs['originator_msg_id'] == 1234
        assert attrs['originator_aet'] == b'PYNETDICOM'

        scp.shutdown()

    def test_scp_handler_identifier(self):
        """Test hander event's context attribute"""
        attrs = {}
        def handle(event):
            attrs['request'] = event.request
            attrs['identifier'] = event.identifier
            attrs['assoc'] = event.assoc
            attrs['context'] = event.context

            yield self.destination
            yield 1
            yield 0xFF00, self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        pytest.raises(StopIteration, next, result)
        assoc.release()
        assert assoc.is_released

        ds = attrs['identifier']
        assert ds.PatientName == '*'

        scp.shutdown()

    def test_scp_handler_move_dest(self):
        """Test hander event's context attribute"""
        attrs = {}
        def handle(event):
            attrs['request'] = event.request
            attrs['identifier'] = event.identifier
            attrs['assoc'] = event.assoc
            attrs['context'] = event.context
            attrs['destination'] = event.move_destination

            yield self.destination
            yield 1
            yield 0xFF00, self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(
            self.query, b'TESTMOVE',
            PatientRootQueryRetrieveInformationModelMove
        )
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        pytest.raises(StopIteration, next, result)
        assoc.release()
        assert assoc.is_released

        assert attrs['destination'] == b'TESTMOVE'

        scp.shutdown()

    def test_scp_cancelled(self):
        """Test is_cancelled works as expected."""
        cancel_results = []

        attrs = {}
        def handle(event):
            ds = Dataset()
            ds.SOPClassUID = CTImageStorage
            ds.SOPInstanceUID = '1.2.3.4'
            ds.file_meta = FileMetaDataset()
            ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
            yield self.destination
            yield 2
            cancel_results.append(event.is_cancelled)
            yield 0xFF00, ds
            time.sleep(0.2)
            cancel_results.append(event.is_cancelled)
            yield 0xFE00, None

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        identifier = Dataset()
        identifier.PatientID = '*'
        results = assoc.send_c_move(
            identifier, b'A', PatientRootQueryRetrieveInformationModelMove, msg_id=11142
        )
        assoc.send_c_cancel(1, 3)
        assoc.send_c_cancel(11142, 1)

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

        assert True in cancel_results

        scp.shutdown()

    def test_subop_message_id(self):
        """Test C-STORE sub-operations Message ID iterates."""
        def handle(event):
            yield self.destination
            yield 3
            yield 0xFF00, self.ds
            yield 0xFF00, self.ds
            yield 0xFF00, self.ds
            yield 0xB000, None

        msg_ids = []
        def handle_store(event):
            msg_ids.append(event.request.MessageID)
            return 0x0000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove)
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
        scp.shutdown()

        assert msg_ids == [2, 3, 4]

    def test_subop_message_id_rollover(self):
        """Test C-STORE sub-operations Message ID iterates."""
        def handle(event):
            yield self.destination
            yield 3
            yield 0xFF00, self.ds
            yield 0xFF00, self.ds
            yield 0xFF00, self.ds
            yield 0xB000, None

        msg_ids = []
        def handle_store(event):
            msg_ids.append(event.request.MessageID)
            return 0x0000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(
            self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove, msg_id=65534
        )
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
        scp.shutdown()

        assert msg_ids == [65535, 1, 2]

    def test_success_no_warn(self):
        """Test receiving final success status."""
        def handle(event):
            yield self.destination
            yield 2
            yield 0xFF00, self.ds
            yield 0x0000, None

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove)
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
        scp.shutdown()

    def test_success_warn(self):
        """Test receiving final success status after subop warns."""
        def handle(event):
            yield self.destination
            yield 2
            yield 0xFF00, self.ds
            yield 0x0000, None

        def handle_store(event):
            return 0xB000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xB000
        assert status.NumberOfFailedSuboperations == 0
        assert status.NumberOfWarningSuboperations == 1
        assert status.NumberOfCompletedSuboperations == 0
        assert identifier.FailedSOPInstanceUIDList == ''
        pytest.raises(StopIteration, next, result)

        assoc.release()
        scp.shutdown()

    def test_success_fail(self):
        """Test receiving final success status after subop failures."""
        def handle(event):
            yield self.destination
            yield 2
            yield 0xFF00, self.ds
            yield 0x0000, None

        def handle_store(event):
            return 0xC000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove)
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
        scp.shutdown()

    def test_handler_aborts_before(self):
        """Test handler aborting the association before any yields"""
        def handle(event):
            event.assoc.abort()
            yield self.destination
            yield 1
            yield 0xFF00, self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(
            self.query, b'TESTMOVE',
            PatientRootQueryRetrieveInformationModelMove
        )
        status, identifier = next(result)
        assert status == Dataset()
        assert identifier is None
        pytest.raises(StopIteration, next, result)

        time.sleep(0.1)
        assert assoc.is_aborted
        scp.shutdown()

    def test_handler_aborts_before_solo(self):
        """Test handler aborting the association before any yields"""
        def handle(event):
            event.assoc.abort()

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(
            self.query, b'TESTMOVE',
            PatientRootQueryRetrieveInformationModelMove
        )
        status, identifier = next(result)
        assert status == Dataset()
        assert identifier is None
        pytest.raises(StopIteration, next, result)

        time.sleep(0.1)
        assert assoc.is_aborted
        scp.shutdown()

    def test_handler_aborts_during_destination(self):
        """Test handler aborting the association during any yields"""
        def handle(event):
            yield self.destination
            event.assoc.abort()
            yield 1
            yield 0xFF00, self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(
            self.query, b'TESTMOVE',
            PatientRootQueryRetrieveInformationModelMove
        )
        status, identifier = next(result)
        assert status == Dataset()
        assert identifier is None
        pytest.raises(StopIteration, next, result)

        time.sleep(0.1)
        assert assoc.is_aborted
        scp.shutdown()

    def test_handler_aborts_during_noops(self):
        """Test handler aborting the association during any yields"""
        def handle(event):
            yield self.destination
            yield 1
            event.assoc.abort()
            yield 0xFF00, self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(
            self.query, b'TESTMOVE',
            PatientRootQueryRetrieveInformationModelMove
        )
        status, identifier = next(result)
        assert status == Dataset()
        assert identifier is None
        pytest.raises(StopIteration, next, result)

        time.sleep(0.1)
        assert assoc.is_aborted
        scp.shutdown()

    def test_handler_aborts_during(self):
        """Test handler aborting the association during any yields"""
        def handle(event):
            yield self.destination
            yield 2
            yield 0xFF00, self.ds
            event.assoc.abort()
            yield 0xFF00, self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(
            self.query, b'TESTMOVE',
            PatientRootQueryRetrieveInformationModelMove
        )
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status == Dataset()
        assert identifier is None
        pytest.raises(StopIteration, next, result)

        time.sleep(0.1)
        assert assoc.is_aborted
        scp.shutdown()

    def test_handler_aborts_after(self):
        """Test handler aborting the association after any yields"""
        def handle(event):
            yield self.destination
            yield 2
            yield 0xFF00, self.ds
            yield 0xFF00, self.ds
            event.assoc.abort()

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(
            self.query, b'TESTMOVE',
            PatientRootQueryRetrieveInformationModelMove
        )
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status == Dataset()
        assert identifier is None
        pytest.raises(StopIteration, next, result)

        time.sleep(0.1)
        assert assoc.is_aborted
        scp.shutdown()

    def test_no_subops_no_association(self):
        """Test that the Move SCP doesn't try and associate if not needed."""
        events = []
        def handle(event):
            yield ('localhost', 11113)
            yield 0
            yield 0x0000, None

        def handle_store(event):
            return 0x0000

        def handle_assoc(event):
            events.append(event)

        handlers = [
            (evt.EVT_REQUESTED, handle_assoc),
            (evt.EVT_C_STORE, handle_store),
        ]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage)
        store_scp = ae.start_server(
            ('', 11113), block=False, evt_handlers=handlers
        )
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_C_MOVE, handle)]
        )

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(
            self.query, b'TESTMOVE',
            PatientRootQueryRetrieveInformationModelMove
        )
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        assert status.NumberOfFailedSuboperations == 0
        assert status.NumberOfWarningSuboperations == 0
        assert status.NumberOfCompletedSuboperations == 0
        pytest.raises(StopIteration, next, result)

        assoc.release()
        scp.shutdown()

        assert len(events) == 0

    def test_handler_unknown_destination(self):
        """Test handler yielding unknown destination."""
        def handle(event):
            yield None, None

        handlers = [(evt.EVT_C_MOVE, handle)]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5

        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(
            self.query,
            b'TESTMOVE',
            PatientRootQueryRetrieveInformationModelMove
        )
        status, identifier = next(result)
        assert status.Status == 0xA801
        assert identifier == Dataset()
        pytest.raises(StopIteration, next, result)
        assoc.release()

        scp.shutdown()

    def test_handler_assoc_kwargs(self):
        """Test yielding the association kwargs."""
        """Test when handler returns success status"""
        def handle(event):
            kwargs = {
                'contexts': [build_context(CTImageStorage)],
                'ae_title': b'SOME_AE'
            }
            yield self.destination[0], self.destination[1], kwargs
            yield 1
            yield 0xFF00, self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(
            self.query,
            b'TESTMOVE',
            PatientRootQueryRetrieveInformationModelMove
        )
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
        scp.shutdown()

    def test_handler_assoc_kwargs_raises(self):
        """Test yielding bad association kwargs."""
        """Test when handler returns success status"""
        def handle(event):
            kwargs = {
                'contexts': [build_context(CTImageStorage)],
                'ae_title': b'SOME_AE',
                'badness': None
            }
            yield self.destination[0], self.destination[1], kwargs
            yield 1
            yield 0xFF00, self.ds

        handlers = [(evt.EVT_C_MOVE, handle)]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(
            self.query,
            b'TESTMOVE',
            PatientRootQueryRetrieveInformationModelMove
        )
        status, identifier = next(result)
        assert status.Status == 0xC515
        assert identifier == Dataset()
        pytest.raises(StopIteration, next, result)

        assoc.release()
        scp.shutdown()

    def test_success_no_identifier(self):
        """Test handler yielding a Dataset status"""
        def handle(event):
            yield self.destination
            yield 1
            status = Dataset()
            status.Status = 0xFF00
            yield status, self.ds

        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        has_dataset = []
        def handle_dimse_in(event):
            has_dataset.append(event.message.command_set.CommandDataSetType)

        scu_handlers = [(evt.EVT_DIMSE_RECV, handle_dimse_in)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, evt_handlers=scu_handlers)
        assert assoc.is_established
        result = assoc.send_c_move(
            self.query,
            b'TESTMOVE',
            PatientRootQueryRetrieveInformationModelMove
        )
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert identifier is None
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        pytest.raises(StopIteration, next, result)

        # The C-MOVE pending and success responses shouldn't have a dataset
        assert len(has_dataset) == 2
        assert has_dataset[0] != 1  # C-MOVE rsp pending
        assert has_dataset[1] != 1  # C-MOVE rsp success

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_scp_store_warning_failure(self):
        """Test when handler returns warning status if not all failed"""
        rsp = [0xC000, 0xB000, 0xB000]

        def handle(event):
            yield self.destination
            yield 3
            yield 0xFF00, self.ds
            yield 0xFF00, self.ds
            yield 0xFF00, self.ds
            yield 0xB000, None

        def handle_store(event):
            return rsp.pop()

        handlers = [(evt.EVT_C_MOVE, handle), (evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(
            self.query, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove
        )
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
        assert status.NumberOfWarningSuboperations == 2
        assert status.NumberOfCompletedSuboperations == 0
        assert identifier.FailedSOPInstanceUIDList == '1.1.1'
        pytest.raises(StopIteration, next, result)

        assoc.release()
        scp.shutdown()


class TestQRCompositeInstanceWithoutBulk:
    """Tests for QR + Composite Instance Without Bulk Data"""
    def setup(self):
        """Run prior to each test"""
        self.query = Dataset()
        self.query.PatientName = '*'
        self.query.QueryRetrieveLevel = "PATIENT"

        self.ds = Dataset()
        self.ds.file_meta = FileMetaDataset()
        self.ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
        self.ds.SOPClassUID = CTImageStorage
        self.ds.SOPInstanceUID = '1.1.1'
        self.ds.PatientName = 'Test'

        self.fail = Dataset()
        self.fail.FailedSOPInstanceUIDList = ['1.2.3']

        self.destination = ('localhost', 11112)

        self.ae = None

    def teardown(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

    def test_pixel_data(self):
        """Test pixel data is removed"""
        assert 'PixelData' in DATASET

        def handle(event):
            yield 1
            yield 0xFF00, DATASET
            yield 0x0000, None

        has_pixel_data = [True]
        def handle_store(event):
            if 'PixelData' not in event.dataset:
                has_pixel_data[0] = False
            return 0x0000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(CompositeInstanceRetrieveWithoutBulkDataGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(CompositeInstanceRetrieveWithoutBulkDataGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate(
            'localhost', 11112, ext_neg=[role], evt_handlers=handlers
        )

        assert assoc.is_established
        result = assoc.send_c_get(
            self.query, CompositeInstanceRetrieveWithoutBulkDataGet
        )
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

        assert has_pixel_data[0] is False

        assoc.release()
        scp.shutdown()

    def test_waveform_sequence(self):
        """Test when handler returns success status"""
        self.ds.SOPClassUID = CTImageStorage
        self.ds.WaveformSequence = [Dataset(), Dataset()]
        self.ds.WaveformSequence[0].WaveformData = b'\x00\x01'
        self.ds.WaveformSequence[0].WaveformBitsAllocated = 16
        self.ds.WaveformSequence[1].WaveformData = b'\x00\x02'
        self.ds.WaveformSequence[1].WaveformBitsAllocated = 8
        assert 'WaveformData' in self.ds.WaveformSequence[0]
        assert 'WaveformData' in self.ds.WaveformSequence[1]

        def handle(event):
            yield 1
            yield 0xFF00, self.ds

        has_waveform_data = [True, True]
        def handle_store(event):
            if 'WaveformData' not in event.dataset.WaveformSequence[0]:
                has_waveform_data[0] = False
            if 'WaveformData' not in event.dataset.WaveformSequence[1]:
                has_waveform_data[1] = False
            return 0x0000

        handlers = [(evt.EVT_C_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(CompositeInstanceRetrieveWithoutBulkDataGet)
        ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)
        ae.add_requested_context(CompositeInstanceRetrieveWithoutBulkDataGet)
        ae.add_requested_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        role = build_role(CTImageStorage, scp_role=True)
        handlers = [(evt.EVT_C_STORE, handle_store)]

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate(
            'localhost', 11112, ext_neg=[role], evt_handlers=handlers
        )

        assert assoc.is_established
        result = assoc.send_c_get(
            self.query, CompositeInstanceRetrieveWithoutBulkDataGet
        )
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

        assert has_waveform_data == [False, False]

        assoc.release()
        scp.shutdown()


class TestBasicWorklistServiceClass:
    """Tests for BasicWorklistManagementServiceClass."""
    def setup(self):
        """Run prior to each test"""
        self.query = Dataset()
        self.query.QueryRetrieveLevel = "PATIENT"
        self.query.PatientName = '*'

        self.ae = None

    def teardown(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

    def test_bad_abstract_syntax_raises(self):
        """Test calling the BWM SCP with an unknown UID raises exception."""
        msg = r'The supplied abstract syntax is not valid'
        with pytest.raises(ValueError, match=msg):
            bwm = BasicWorklistManagementServiceClass(None)
            context = build_context('1.2.3.4')
            bwm.SCP(None, context)

    def test_pending_success(self):
        """Test handler yielding pending then success status"""
        def handle(event):
            yield 0xFF01,  self.query
            yield 0x0000, None
            yield 0xA700, None

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ModalityWorklistInformationFind)
        ae.add_requested_context(ModalityWorklistInformationFind)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, ModalityWorklistInformationFind)
        status, identifier = next(result)
        assert status.Status == 0xFF01
        assert identifier == self.query
        status, identifier = next(result)
        assert status.Status == 0x0000
        assert identifier is None
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()
