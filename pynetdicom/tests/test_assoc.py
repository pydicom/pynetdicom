"""Association testing"""

from datetime import datetime
from io import BytesIO
import logging
import os
try:
    import queue
except ImportError:
    import Queue as queue  # Python 2 compatibility
import socket
import sys
import time
import threading

import pytest

from pydicom import dcmread
from pydicom.dataset import Dataset
from pydicom.uid import (
    UID,
    ImplicitVRLittleEndian,
    ExplicitVRLittleEndian,
    JPEGBaseline,
    JPEG2000,
    JPEG2000Lossless,
    DeflatedExplicitVRLittleEndian,
    ExplicitVRBigEndian
)

from pynetdicom import (
    AE, VerificationPresentationContexts, build_context, evt, _config,
    debug_logger, build_role
)
from pynetdicom.association import Association
from pynetdicom.dimse_primitives import C_STORE, C_FIND, C_GET, C_MOVE
from pynetdicom.dsutils import encode, decode
from pynetdicom.events import Event
from pynetdicom._globals import MODE_REQUESTOR, MODE_ACCEPTOR
from pynetdicom.pdu_primitives import (
    UserIdentityNegotiation, SOPClassExtendedNegotiation,
    SOPClassCommonExtendedNegotiation, SCP_SCU_RoleSelectionNegotiation,
    AsynchronousOperationsWindowNegotiation, A_ASSOCIATE
)
from pynetdicom.sop_class import (
    VerificationSOPClass,
    CTImageStorage, MRImageStorage, RTImageStorage,
    PatientRootQueryRetrieveInformationModelFind,
    PatientRootQueryRetrieveInformationModelGet,
    PatientRootQueryRetrieveInformationModelMove,
    PatientStudyOnlyQueryRetrieveInformationModelMove,
    StudyRootQueryRetrieveInformationModelMove,
    SecondaryCaptureImageStorage,
    UnifiedProcedureStepPullSOPClass,
    UnifiedProcedureStepPushSOPClass,
    UnifiedProcedureStepWatchSOPClass
)
from .dummy_c_scp import (
    DummyVerificationSCP, DummyStorageSCP, DummyFindSCP, DummyGetSCP,
    DummyMoveSCP, DummyBaseSCP
)
from .encoded_pdu_items import a_associate_ac
from .parrot import start_server, ThreadedParrot


#debug_logger()


TEST_DS_DIR = os.path.join(os.path.dirname(__file__), 'dicom_files')
BIG_DATASET = dcmread(os.path.join(TEST_DS_DIR, 'RTImageStorage.dcm')) # 2.1 M
DATASET = dcmread(os.path.join(TEST_DS_DIR, 'CTImageStorage.dcm'))
# JPEG2000Lossless
COMP_DATASET = dcmread(
    os.path.join(TEST_DS_DIR, 'MRImageStorage_JPG2000_Lossless.dcm')
)
# DeflatedExplicitVRLittleEndian
DEFL_DATASET = dcmread(
    os.path.join(TEST_DS_DIR, 'SCImageStorage_Deflated.dcm')
)


class DummyDIMSE(object):
    def __init__(self):
        self.status = None
        self.msg_queue = queue.Queue()

    def send_msg(self, rsp, context_id):
        self.status = rsp.Status
        self.rsp = rsp

    def get_msg(self, block=False):
        return None, None


class TestAssociation(object):
    """Run tests on Associtation."""
    # Association(local_ae, client_socket, peer_ae, acse_timeout,
    #             dimse_timeout, max_pdu, ext_neg)
    def setup(self):
        """This function runs prior to all test methods"""
        self.scp = None
        self.ae = None

    def teardown(self):
        """This function runs after all test methods"""
        if self.scp:
            self.scp.abort()

        if self.ae:
            self.ae.shutdown()

        for thread in threading.enumerate():
            if isinstance(thread, DummyBaseSCP):
                thread.abort()
                thread.stop()

    def test_bad_connection(self):
        """Test connect to non-AE"""
        # sometimes causes hangs in Travis
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        assoc = ae.associate('localhost', 22)
        assert not assoc.is_established

    def test_connection_refused(self):
        """Test connection refused"""
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        assoc = ae.associate('localhost', 11120)
        assert not assoc.is_established

    def test_req_no_presentation_context(self):
        """Test rejection due to no acceptable presentation contexts"""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)

        ae.add_requested_context(CTImageStorage)
        assoc = ae.associate('localhost', 11112)
        assert not assoc.is_established
        assert assoc.is_aborted

        scp.shutdown()

    def test_peer_releases_assoc(self):
        """Test peer releases association"""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)

        ae.add_requested_context(VerificationSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        scp.active_associations[0].release()

        time.sleep(0.1)

        assert assoc.is_released
        assert not assoc.is_established

        scp.shutdown()

    def test_peer_aborts_assoc(self):
        """Test peer aborts association."""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)

        ae.add_requested_context(VerificationSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        scp.active_associations[0].abort()

        time.sleep(0.1)

        assert assoc.is_aborted
        assert not assoc.is_established

        scp.shutdown()

    def test_peer_rejects_assoc(self):
        """Test peer rejects assoc"""
        self.scp = DummyVerificationSCP()
        self.scp.ae.require_calling_aet = [b'HAHA NOPE']
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        time.sleep(0.1)
        assert assoc.is_rejected
        assert not assoc.is_established
        self.scp.stop() # Important!

    def test_assoc_release(self):
        """Test Association release"""
        # Simple release
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established
        self.scp.stop()

        # Simple release, then release again
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established
        assert assoc.is_released
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

        # Simple release, then abort
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assoc.release()
        assert assoc.is_released
        assert assoc.is_released
        assert not assoc.is_established
        assoc.abort()
        assert not assoc.is_aborted
        self.scp.stop()

    def test_assoc_abort(self):
        """Test Association abort"""
        # Simple abort
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assoc.abort()
        assert not assoc.is_established
        assert assoc.is_aborted
        self.scp.stop()

        # Simple abort, then release
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assoc.abort()
        assert not assoc.is_established
        assert assoc.is_aborted
        assoc.release()
        assert assoc.is_aborted
        assert not assoc.is_released
        self.scp.stop()

        # Simple abort, then abort again
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assoc.abort()
        assert assoc.is_aborted
        assert not assoc.is_established
        assoc.abort()
        self.scp.stop()

    def test_scp_removed_ui(self):
        """Test SCP removes UI negotiation"""
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ui = UserIdentityNegotiation()
        ui.user_identity_type = 0x01
        ui.primary_field = b'pynetdicom'

        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[ui])
        assert assoc.is_established
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_scp_removed_ext_neg(self):
        """Test SCP removes ex negotiation"""
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ext = SOPClassExtendedNegotiation()
        ext.sop_class_uid = '1.1.1.1'
        ext.service_class_application_information = b'\x01\x02'

        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[ext])
        assert assoc.is_established
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_scp_removed_com_ext_neg(self):
        """Test SCP removes common ext negotiation"""
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ext = SOPClassCommonExtendedNegotiation()
        ext.related_general_sop_class_identification = ['1.2.1']
        ext.sop_class_uid = '1.1.1.1'
        ext.service_class_uid = '1.1.3'

        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[ext])
        assert assoc.is_established
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_scp_assoc_limit(self):
        """Test SCP limits associations"""
        self.scp = DummyVerificationSCP()
        self.scp.ae.maximum_associations = 1
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assoc_2 = ae.associate('localhost', 11112)
        assert not assoc_2.is_established
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_require_called_aet(self):
        """SCP requires matching called AET"""
        self.scp = DummyVerificationSCP()
        self.scp.ae.require_called_aet = True
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert not assoc.is_established
        assert assoc.is_rejected
        self.scp.stop()

    def test_require_calling_aet(self):
        """SCP requires matching called AET"""
        self.scp = DummyVerificationSCP()
        self.scp.ae.require_calling_aet = [b'TESTSCP']
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert not assoc.is_established
        assert assoc.is_rejected
        self.scp.stop()

    def test_dimse_timeout(self):
        """Test that the DIMSE timeout works"""
        def handle(event):
            time.sleep(0.2)
            return 0x0000

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.dimse_timeout = 0.1
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_C_ECHO, handle)]
        )

        ae.add_requested_context(VerificationSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.dimse_timeout == 0.1
        assert assoc.dimse.dimse_timeout == 0.1
        assert assoc.is_established
        assoc.send_c_echo()
        assoc.release()
        assert not assoc.is_released
        assert assoc.is_aborted

        scp.shutdown()

    def test_multiple_association_release_cycles(self):
        """Test repeatedly associating and releasing"""
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        for ii in range(10):
            assoc = ae.associate('localhost', 11112)
            assert assoc.is_established
            assert not assoc.is_released
            assoc.send_c_echo()
            assoc.release()
            assert assoc.is_released
            assert not assoc.is_established

        self.scp.stop()

    def test_local(self):
        """Test Association.local."""
        ae = AE()
        assoc = Association(ae, 'requestor')
        assoc.requestor.ae_title = ae.ae_title
        assert assoc.local['ae_title'] == b'PYNETDICOM      '

        assoc = Association(ae, 'acceptor')
        assoc.acceptor.ae_title = ae.ae_title
        assert assoc.local['ae_title'] == b'PYNETDICOM      '

    def test_remote(self):
        """Test Association.local."""
        ae = AE()
        assoc = Association(ae, 'requestor')
        assert assoc.remote['ae_title'] == b''

        assoc = Association(ae, 'acceptor')
        assert assoc.remote['ae_title'] == b''

    def test_mode_raises(self):
        """Test exception is raised if invalid mode."""
        msg = (
            r"Invalid association `mode` value, must be either 'requestor' or "
            "'acceptor'"
        )
        with pytest.raises(ValueError, match=msg):
            assoc = Association(None, 'nope')

    def test_setting_socket_override_raises(self):
        """Test that set_socket raises exception if socket set."""
        ae = AE()
        assoc = Association(ae, MODE_REQUESTOR)
        assoc.dul.socket = 'abc'
        msg = r"The Association already has a socket set."
        with pytest.raises(RuntimeError, match=msg):
            assoc.set_socket('cba')

        assert assoc.dul.socket == 'abc'

    def test_invalid_context(self, caplog):
        """Test receiving an message with invalid context ID"""
        with caplog.at_level(logging.INFO, logger='pynetdicom'):
            ae = AE()
            ae.add_requested_context(VerificationSOPClass)
            ae.add_requested_context(CTImageStorage)
            ae.add_supported_context(VerificationSOPClass)
            scp = ae.start_server(('', 11112), block=False)

            assoc = ae.associate('localhost', 11112)
            assoc.dimse_timeout = 0.1
            assert assoc.is_established
            assoc._accepted_cx[3] = assoc._rejected_cx[0]
            assoc._accepted_cx[3].result = 0x00
            assoc._accepted_cx[3]._as_scu = True
            assoc._accepted_cx[3]._as_scp = True
            ds = Dataset()
            ds.SOPClassUID = CTImageStorage
            ds.SOPInstanceUID = '1.2.3.4'
            ds.file_meta = Dataset()
            ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
            result = assoc.send_c_store(ds)
            time.sleep(0.1)
            assert assoc.is_aborted
            assert (
                'Received DIMSE message with invalid or rejected context ID'
            ) in caplog.text

            scp.shutdown()

    def test_get_events(self):
        """Test Association.get_events()."""
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert evt.EVT_C_STORE in assoc.get_events()
        assert evt.EVT_USER_ID in assoc.get_events()

    def test_requested_handler_abort(self):
        """Test the EVT_REQUESTED handler sending abort."""
        def handle_req(event):
            event.assoc.acse.send_abort(0x00)
            time.sleep(0.1)

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(VerificationSOPClass)

        hh = [(evt.EVT_REQUESTED, handle_req)]

        scp = ae.start_server(('', 11112), block=False, evt_handlers=hh)

        ae.add_requested_context(VerificationSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert not assoc.is_established
        assert assoc.is_aborted

        scp.shutdown()

    def test_requested_handler_reject(self):
        """Test the EVT_REQUESTED handler sending reject."""
        def handle_req(event):
            event.assoc.acse.send_reject(0x02, 0x01, 0x01)
            # Give the requestor time to process the message before killing
            #   the connection
            time.sleep(0.1)

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(VerificationSOPClass)

        hh = [(evt.EVT_REQUESTED, handle_req)]

        scp = ae.start_server(('', 11112), block=False, evt_handlers=hh)

        ae.add_requested_context(VerificationSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert not assoc.is_established
        assert assoc.is_rejected

        scp.shutdown()

    def test_unknown_abort_source(self):
        """Test an unknown abort source handled correctly #561"""
        def handle_req(event):
            pdu = b"\x07\x00\x00\x00\x00\x04\x00\x00\x01\x00"
            event.assoc.dul.socket.send(pdu)
            # Give the requestor time to process the message before killing
            #   the connection
            time.sleep(0.1)

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(VerificationSOPClass)

        hh = [(evt.EVT_REQUESTED, handle_req)]

        scp = ae.start_server(('', 11112), block=False, evt_handlers=hh)

        ae.add_requested_context(VerificationSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert not assoc.is_established
        assert assoc.is_aborted

        scp.shutdown()


class TestCStoreSCP(object):
    """Tests for Association._c_store_scp()."""
    # Used with C-GET (always) and C-MOVE (over the same association)
    def setup(self):
        self.ae = None

    def teardown(self):
        if self.ae:
            self.ae.shutdown()

    def test_no_context(self):
        """Test correct response if no valid presentation context."""
        def handle(event):
            return 0x0000

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(CTImageStorage)
        ae.add_supported_context(RTImageStorage)
        # Storage SCP
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_C_STORE, handle)]
        )

        ae.add_requested_context(RTImageStorage)
        role = build_role(CTImageStorage, scu_role=False, scp_role=True)
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
        assert assoc.is_established

        req = C_STORE()
        req.MessageID = 1
        req.AffectedSOPClassUID = DATASET.SOPClassUID
        req.AffectedSOPInstanceUID = DATASET.SOPInstanceUID
        req.Priority = 1
        req._context_id = 1

        bytestream = encode(DATASET, True, True)
        req.DataSet = BytesIO(bytestream)

        assoc.dimse = DummyDIMSE()
        assoc._c_store_scp(req)
        assert assoc.dimse.status == 0x0122
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_handler_exception(self):
        """Test correct response if exception raised by handler."""
        def handle(event):
            raise ValueError()
            return 0x0000

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(CTImageStorage, scp_role=True, scu_role=True)
        # Storage SCP
        scp = ae.start_server(('', 11112), block=False)

        ae.add_requested_context(CTImageStorage)
        role = build_role(CTImageStorage, scu_role=False, scp_role=True)
        assoc = ae.associate(
            'localhost', 11112, ext_neg=[role],
            evt_handlers=[(evt.EVT_C_STORE, handle)]
        )
        assert assoc.is_established

        req = C_STORE()
        req.MessageID = 1
        req.AffectedSOPClassUID = DATASET.SOPClassUID
        req.AffectedSOPInstanceUID = DATASET.SOPInstanceUID
        req.Priority = 1
        req._context_id = 1

        bytestream = encode(DATASET, True, True)
        req.DataSet = BytesIO(bytestream)

        assoc.dimse = DummyDIMSE()
        assoc._c_store_scp(req)
        assert assoc.dimse.status == 0xC211
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_handler_status_ds_no_status(self):
        """Test handler with status dataset with no Status element."""
        def handle(event):
            return Dataset()

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(CTImageStorage, scp_role=True, scu_role=True)
        # Storage SCP
        scp = ae.start_server(('', 11112), block=False)

        ae.add_requested_context(CTImageStorage)
        role = build_role(CTImageStorage, scu_role=False, scp_role=True)
        assoc = ae.associate(
            'localhost', 11112, ext_neg=[role],
            evt_handlers=[(evt.EVT_C_STORE, handle)]
        )
        assert assoc.is_established

        req = C_STORE()
        req.MessageID = 1
        req.AffectedSOPClassUID = DATASET.SOPClassUID
        req.AffectedSOPInstanceUID = DATASET.SOPInstanceUID
        req.Priority = 1
        req._context_id = 1

        bytestream = encode(DATASET, True, True)
        req.DataSet = BytesIO(bytestream)

        assoc.dimse = DummyDIMSE()
        assoc._c_store_scp(req)
        assert assoc.dimse.status == 0xC001
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_handler_status_ds_unknown_elems(self):
        """Test handler with status dataset with an unknown element."""
        def handle(event):
            ds = Dataset()
            ds.Status = 0x0000
            ds.PatientName = 'ABCD'
            return ds

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(CTImageStorage, scp_role=True, scu_role=True)
        # Storage SCP
        scp = ae.start_server(('', 11112), block=False)

        ae.add_requested_context(CTImageStorage)
        role = build_role(CTImageStorage, scu_role=False, scp_role=True)
        assoc = ae.associate(
            'localhost', 11112, ext_neg=[role],
            evt_handlers=[(evt.EVT_C_STORE, handle)]
        )
        assert assoc.is_established

        req = C_STORE()
        req.MessageID = 1
        req.AffectedSOPClassUID = DATASET.SOPClassUID
        req.AffectedSOPInstanceUID = DATASET.SOPInstanceUID
        req.Priority = 1
        req._context_id = 1

        bytestream = encode(DATASET, True, True)
        req.DataSet = BytesIO(bytestream)

        assoc.dimse = DummyDIMSE()
        assoc._c_store_scp(req)
        rsp = assoc.dimse.rsp
        assert rsp.Status == 0x0000
        assert not hasattr(rsp, 'PatientName')
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_handler_invalid_status(self):
        """Test handler with invalid status."""
        def handle(event):
            return 'abcd'

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(CTImageStorage, scp_role=True, scu_role=True)
        # Storage SCP
        scp = ae.start_server(('', 11112), block=False)

        ae.add_requested_context(CTImageStorage)
        role = build_role(CTImageStorage, scu_role=False, scp_role=True)
        assoc = ae.associate(
            'localhost', 11112, ext_neg=[role],
            evt_handlers=[(evt.EVT_C_STORE, handle)]
        )
        assert assoc.is_established

        req = C_STORE()
        req.MessageID = 1
        req.AffectedSOPClassUID = DATASET.SOPClassUID
        req.AffectedSOPInstanceUID = DATASET.SOPInstanceUID
        req.Priority = 1
        req._context_id = 1

        bytestream = encode(DATASET, True, True)
        req.DataSet = BytesIO(bytestream)

        assoc.dimse = DummyDIMSE()
        assoc._c_store_scp(req)
        assert assoc.dimse.status == 0xC002
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_handler_unknown_status(self):
        """Test handler with invalid status."""
        def handle(event):
            return 0xDEFA

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(CTImageStorage, scp_role=True, scu_role=True)
        # Storage SCP
        scp = ae.start_server(('', 11112), block=False)

        ae.add_requested_context(CTImageStorage)
        role = build_role(CTImageStorage, scu_role=False, scp_role=True)
        assoc = ae.associate(
            'localhost', 11112, ext_neg=[role],
            evt_handlers=[(evt.EVT_C_STORE, handle)]
        )
        assert assoc.is_established

        req = C_STORE()
        req.MessageID = 1
        req.AffectedSOPClassUID = DATASET.SOPClassUID
        req.AffectedSOPInstanceUID = DATASET.SOPInstanceUID
        req.Priority = 1
        req._context_id = 1

        bytestream = encode(DATASET, True, True)
        req.DataSet = BytesIO(bytestream)

        assoc.dimse = DummyDIMSE()
        assoc._c_store_scp(req)
        assert assoc.dimse.status == 0xDEFA
        assoc.release()
        assert assoc.is_released

        scp.shutdown()


class TestAssociationSendCEcho(object):
    """Run tests on Assocation evt.EVT_C_ECHO handler."""
    def setup(self):
        """Run prior to each test"""
        self.scp = None
        self.ae = None

    def teardown(self):
        """Clear any active threads"""
        if self.scp:
            self.scp.abort()

        if self.ae:
            self.ae.shutdown()

        time.sleep(0.1)

        for thread in threading.enumerate():
            if isinstance(thread, DummyBaseSCP):
                thread.abort()
                thread.stop()

    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established
        with pytest.raises(RuntimeError):
            assoc.send_c_echo()
        self.scp.stop()

    def test_no_abstract_syntax_match(self):
        """Test SCU when no accepted abstract syntax"""
        self.scp = DummyStorageSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        with pytest.raises(ValueError):
            assoc.send_c_echo()
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rsp_none(self):
        """Test no response from peer"""
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        class DummyDIMSE():
            msg_queue = queue.Queue()
            def send_msg(*args, **kwargs): return
            def get_msg(*args, **kwargs): return None, None

        assoc._reactor_checkpoint.clear()
        while not assoc._is_paused:
            time.sleep(0.01)
        assoc.dimse = DummyDIMSE()
        if assoc.is_established:
            assoc.send_c_echo()

        assert assoc.is_aborted

        self.scp.stop()

    def test_rsp_invalid(self):
        """Test invalid response received from peer"""
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        class DummyResponse():
            is_valid_response = False

        class DummyDIMSE():
            msg_queue = queue.Queue()
            def send_msg(*args, **kwargs): return
            def get_msg(*args, **kwargs): return None, DummyResponse()

        assoc._reactor_checkpoint.clear()
        while not assoc._is_paused:
            time.sleep(0.01)
        assoc.dimse = DummyDIMSE()
        if assoc.is_established:
            assoc.send_c_echo()

        assert assoc.is_aborted

        self.scp.stop()

    def test_rsp_success(self):
        """Test receiving a success response from the peer"""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)

        ae.add_requested_context(VerificationSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_echo()
        assert result.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_failure(self):
        """Test receiving a failure response from the peer"""
        def handler(event):
            return 0x0210

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        handlers = [(evt.EVT_C_ECHO, handler)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_echo()
        assert result.Status == 0x0210
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_unknown_status(self):
        """Test unknown status value returned by peer"""
        def handler(event):
            return 0xFFF0

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        handlers = [(evt.EVT_C_ECHO, handler)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_echo()
        assert result.Status == 0xFFF0
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_multi_status(self):
        """Test receiving a status with extra elements"""
        def handler(event):
            ds = Dataset()
            ds.Status = 0x0122
            ds.ErrorComment = 'Some comment'
            return ds

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        handlers = [(evt.EVT_C_ECHO, handler)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_echo()
        assert result.Status == 0x0122
        assert result.ErrorComment == 'Some comment'
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_abort_during(self):
        """Test aborting the association during message exchange"""
        def handle(event):
            event.assoc.abort()
            return 0x0000

        self.ae = ae = AE()
        ae.acse_timeout = 1
        ae.dimse_timeout = 1
        ae.network_timeout = 1
        ae.add_supported_context(VerificationSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_C_ECHO, handle)]
        )

        ae.add_requested_context(VerificationSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_echo()
        assert result == Dataset()

        time.sleep(0.1)
        assert assoc.is_aborted

        scp.shutdown()

    def test_run_accept_scp_not_implemented(self):
        """Test association is aborted if non-implemented SCP requested."""
        self.scp = DummyVerificationSCP()
        self.scp.send_abort = True
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.add_requested_context('1.2.3.4')
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status = assoc.send_n_delete('1.2.3.4', '1.2.3')
        assert status == Dataset()

        time.sleep(0.1)
        assert assoc.is_aborted
        self.scp.stop()

    def test_rejected_contexts(self):
        """Test receiving a success response from the peer"""
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(assoc.rejected_contexts) == 1
        cx = assoc.rejected_contexts[0]
        assert cx.abstract_syntax == CTImageStorage
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_common_ext_neg_no_general_sop(self):
        """Test sending SOP Class Common Extended Negotiation."""
        # With no Related General SOP Classes
        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        item = SOPClassCommonExtendedNegotiation()
        item.sop_class_uid = '1.2.3'
        item.service_class_uid = '2.3.4'

        assoc = ae.associate('localhost', 11112, ext_neg=[item])
        assert assoc.is_established
        result = assoc.send_c_echo()
        assert result.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_changing_network_timeout(self):
        """Test changing timeout after associated."""
        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        ae.network_timeout = 1

        assert assoc.dul.network_timeout == 1
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_network_times_out_requestor(self):
        """Regression test for #286."""
        self.ae = ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.add_supported_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert assoc.network_timeout == 60
        assoc.network_timeout = 0.5
        assert assoc.network_timeout == 0.5

        time.sleep(1.0)
        assert assoc.is_aborted

        scp.shutdown()

    def test_network_times_out_acceptor(self):
        """Regression test for #286."""
        self.ae = ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.add_supported_context(VerificationSOPClass)
        scp = ae.start_server(('', 11113), block=False)

        assoc = ae.associate('localhost', 11113)
        ae.network_timeout = 0.5
        assoc.network_timeout = 60
        assert assoc.network_timeout == 60
        assert assoc.is_established
        time.sleep(1.0)
        assert assoc.is_aborted

        scp.shutdown()


class TestAssociationSendCStore(object):
    """Run tests on Assocation send_c_store."""
    def setup(self):
        """Run prior to each test"""
        self.ae = None

    def teardown(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

    def test_must_be_associated(self):
        """Test SCU can't send without association."""
        # Test raise if assoc not established
        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.add_requested_context(CTImageStorage)
        assoc = ae.associate('localhost', 11112)
        assoc.release()

        assert assoc.is_released
        assert not assoc.is_established
        with pytest.raises(RuntimeError):
            assoc.send_c_store(DATASET)

        scp.shutdown()

    def test_no_abstract_syntax_match(self):
        """Test SCU when no accepted abstract syntax"""
        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.add_requested_context(VerificationSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        with pytest.raises(ValueError):
            assoc.send_c_store(DATASET)
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_bad_priority(self):
        """Test bad priority raises exception"""
        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.add_requested_context(CTImageStorage)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        with pytest.raises(ValueError):
            assoc.send_c_store(DATASET, priority=0x0003)
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_fail_encode_dataset(self):
        """Test failure if unable to encode dataset"""
        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.add_requested_context(CTImageStorage, ExplicitVRLittleEndian)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        ds = Dataset()
        ds.SOPClassUID = CTImageStorage
        ds.SOPInstanceUID = '1.2.3'
        ds.PerimeterValue = b'\x00\x01'
        ds.file_meta = Dataset()
        ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
        with pytest.raises(ValueError):
            assoc.send_c_store(ds)
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_encode_compressed_dataset(self):
        """Test sending a dataset with a compressed transfer syntax """
        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(MRImageStorage, JPEG2000Lossless)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.add_requested_context(MRImageStorage, JPEG2000Lossless)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_store(COMP_DATASET)
        assert result.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_none(self):
        """Test no response from peer"""
        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.add_requested_context(CTImageStorage)
        assoc = ae.associate('localhost', 11112)

        class DummyDIMSE():
            msg_queue = queue.Queue()
            def send_msg(*args, **kwargs): return
            def get_msg(*args, **kwargs): return None, None

        assoc._reactor_checkpoint.clear()
        while not assoc._is_paused:
            time.sleep(0.01)
        assoc.dimse = DummyDIMSE()
        assert assoc.is_established
        status = assoc.send_c_store(DATASET)
        assert status == Dataset()

        assert assoc.is_aborted

        scp.shutdown()

    def test_rsp_invalid(self):
        """Test invalid DIMSE message received from peer"""
        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.add_requested_context(CTImageStorage)
        assoc = ae.associate('localhost', 11112)

        class DummyResponse():
            is_valid_response = False

        class DummyDIMSE():
            msg_queue = queue.Queue()
            def send_msg(*args, **kwargs): return
            def get_msg(*args, **kwargs): return DummyResponse(), None

        assoc._reactor_checkpoint.clear()
        while not assoc._is_paused:
            time.sleep(0.01)
        assoc.dimse = DummyDIMSE()
        assert assoc.is_established
        status = assoc.send_c_store(DATASET)
        assert assoc.is_aborted
        assert status == Dataset()

        scp.shutdown()

    def test_rsp_failure(self):
        """Test receiving a failure response from the peer"""
        def handle_store(event):
            return 0xC000

        handlers = [(evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.add_requested_context(CTImageStorage)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status = assoc.send_c_store(DATASET)
        assert status.Status == 0xC000
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_warning(self):
        """Test receiving a warning response from the peer"""
        def handle_store(event):
            return 0xB000

        handlers = [(evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.add_requested_context(CTImageStorage)
        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established
        status = assoc.send_c_store(DATASET)
        assert status.Status == 0xB000
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_success(self):
        """Test receiving a success response from the peer"""
        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.add_requested_context(CTImageStorage)
        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established
        status = assoc.send_c_store(DATASET)
        assert status.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_unknown_status(self):
        """Test unknown status value returned by peer"""
        def handle_store(event):
            return 0xFFF0

        handlers = [(evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.add_requested_context(CTImageStorage)
        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established
        status = assoc.send_c_store(DATASET)
        assert status.Status == 0xFFF0
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_dataset_no_sop_class_raises(self):
        """Test sending a dataset without SOPClassUID raises."""
        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.add_requested_context(CTImageStorage)
        assoc = ae.associate('localhost', 11112)

        ds = Dataset()
        ds.SOPInstanceUID = '1.2.3.4'
        ds.file_meta = Dataset()
        ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian

        assert assoc.is_established
        assert 'SOPClassUID' not in ds
        msg = (
            r"Unable to determine the presentation context to use with "
            r"`dataset` as it contains no '\(0008,0016\) SOP Class UID' "
            r"element"
        )
        with pytest.raises(AttributeError, match=msg):
            assoc.send_c_store(ds)

        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_dataset_no_transfer_syntax_raises(self):
        """Test sending a dataset without TransferSyntaxUID raises."""
        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.add_requested_context(CTImageStorage)
        assoc = ae.associate('localhost', 11112)

        ds = Dataset()
        ds.SOPInstanceUID = '1.2.3.4'
        ds.SOPClassUID = CTImageStorage

        assert 'file_meta' not in ds
        msg = (
            r"Unable to determine the presentation context to use with "
            r"`dataset` as it contains no '\(0002,0010\) Transfer Syntax "
            r"UID' file meta information element"
        )
        with pytest.raises(AttributeError, match=msg):
            assoc.send_c_store(ds)

        ds.file_meta = Dataset()
        assert 'TransferSyntaxUID' not in ds.file_meta
        msg = (
            r"Unable to determine the presentation context to use with "
            r"`dataset` as it contains no '\(0002,0010\) Transfer Syntax "
            r"UID' file meta information element"
        )
        with pytest.raises(AttributeError, match=msg):
            assoc.send_c_store(ds)

        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_functional_common_ext_neg(self):
        """Test functioning of the SOP Class Common Extended negotiation."""
        def handle_ext(event):
            return event.items

        def handle_store(event):
            return 0x0000

        handlers = [
            (evt.EVT_C_STORE, handle_store),
            (evt.EVT_SOP_COMMON, handle_ext)
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(CTImageStorage)
        ae.add_supported_context('1.2.3')
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.add_requested_context(CTImageStorage)
        ae.add_requested_context('1.2.3')

        req = {
            '1.2.3' : ('1.2.840.10008.4.2', []),
            '1.2.3.1' : ('1.2.840.10008.4.2', ['1.1.1', '1.4.2']),
            '1.2.3.4' : ('1.2.111111', []),
            '1.2.3.5' : ('1.2.111111', ['1.2.4', '1.2.840.10008.1.1']),
        }

        ext_neg = []
        for kk, vv in req.items():
            item = SOPClassCommonExtendedNegotiation()
            item.sop_class_uid = kk
            item.service_class_uid = vv[0]
            item.related_general_sop_class_identification = vv[1]
            ext_neg.append(item)

        assoc = ae.associate('localhost', 11112, ext_neg=ext_neg)
        assert assoc.is_established

        ds = Dataset()
        ds.SOPClassUID = '1.2.3'
        ds.SOPInstanceUID = '1.2.3.4'
        ds.file_meta = Dataset()
        ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
        status = assoc.send_c_store(ds)
        assert status.Status == 0x0000

        assoc.release()

        scp.shutdown()

    # Regression tests
    def test_no_send_mismatch(self):
        """Test sending a dataset with mismatched transfer syntax (206)."""
        def handle_store(event):
            return 0x0000

        handlers = [(evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.add_requested_context(CTImageStorage, ImplicitVRLittleEndian)
        assoc = ae.associate('localhost', 11112)

        ds = Dataset()
        ds.SOPClassUID = CTImageStorage
        ds.SOPInstanceUID = '1.2.3.4'
        ds.file_meta = Dataset()
        ds.file_meta.TransferSyntaxUID = JPEGBaseline

        assert assoc.is_established

        msg = (
            r"No presentation context for 'CT Image Storage' has been "
            r"accepted by the peer with 'JPEG Baseline \(Process 1\)' "
            r"transfer syntax for the SCU role"
        )
        with pytest.raises(ValueError, match=msg):
            assoc.send_c_store(ds)

        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_send_deflated(self):
        """Test sending a deflated encoded dataset (482)."""
        recv_ds = []
        def handle_store(event):
            recv_ds.append(event.dataset)
            return 0x0000

        handlers = [(evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(
            SecondaryCaptureImageStorage, DeflatedExplicitVRLittleEndian
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.add_requested_context(
            SecondaryCaptureImageStorage, DeflatedExplicitVRLittleEndian
        )
        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established

        status = assoc.send_c_store(DEFL_DATASET)

        assoc.release()
        assert assoc.is_released

        scp.shutdown()

        assert '^^^^' == recv_ds[0].PatientName


class TestAssociationSendCFind(object):
    """Run tests on Assocation send_c_find."""
    def setup(self):
        """Run prior to each test"""
        self.ds = Dataset()
        self.ds.PatientName = '*'
        self.ds.QueryRetrieveLevel = "PATIENT"

        self.scp = None
        self.ae = None

    def teardown(self):
        """Clear any active threads"""
        if self.scp:
            self.scp.abort()

        if self.ae:
            self.ae.shutdown()

        time.sleep(0.1)

        for thread in threading.enumerate():
            if isinstance(thread, DummyBaseSCP):
                thread.abort()
                thread.stop()

    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        scp = DummyFindSCP()
        scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established
        with pytest.raises(RuntimeError):
            next(assoc.send_c_find(self.ds, PatientRootQueryRetrieveInformationModelFind))
        scp.stop()

    def test_no_abstract_syntax_match(self):
        """Test when no accepted abstract syntax"""
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        def test():
            next(assoc.send_c_find(
                self.ds,
                PatientRootQueryRetrieveInformationModelFind)
            )

        with pytest.raises(ValueError):
            test()
        assoc.release()
        assert assoc.is_released
        scp.stop()

    def test_bad_query_model(self):
        """Test invalid query_model value"""
        scp = DummyFindSCP()
        scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        with pytest.raises(ValueError):
            next(assoc.send_c_find(self.ds, query_model='XXX'))
        assoc.release()
        assert assoc.is_released
        scp.stop()

    def test_fail_encode_identifier(self):
        """Test a failure in encoding the Identifier dataset"""
        self.scp = DummyFindSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind,
                                 ExplicitVRLittleEndian)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        DATASET.PerimeterValue = b'\x00\x01'

        def test():
            next(assoc.send_c_find(DATASET, PatientRootQueryRetrieveInformationModelFind))
        with pytest.raises(ValueError):
            test()
        assoc.release()
        assert assoc.is_released
        del DATASET.PerimeterValue # Fix up our changes
        self.scp.stop()

    def test_rsp_failure(self):
        """Test receiving a failure response from the peer"""
        def handle(event):
            yield 0xA700, None

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_C_FIND, handle)]
        )

        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        for (status, ds) in assoc.send_c_find(
                self.ds, PatientRootQueryRetrieveInformationModelFind):
            assert status.Status == 0xA700
            assert ds is None
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_pending(self):
        """Test receiving a pending response from the peer"""
        def handle(event):
            yield 0xFF00, self.ds

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_C_FIND, handle)]
        )

        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        result = assoc.send_c_find(self.ds, PatientRootQueryRetrieveInformationModelFind)
        (status, ds) = next(result)
        assert status.Status == 0xFF00
        assert 'PatientName' in ds
        (status, ds) = next(result)
        assert status.Status == 0x0000
        assert ds is None
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_success(self):
        """Test receiving a success response from the peer"""
        def handle(event):
            yield 0x0000, None

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_C_FIND, handle)]
        )

        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        for (status, ds) in assoc.send_c_find(self.ds, PatientRootQueryRetrieveInformationModelFind):
            assert status.Status == 0x0000
            assert ds is None
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_empty(self):
        """Test receiving a success response from the peer"""
        # No matches
        def handle(event):
            pass

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_C_FIND, handle)]
        )

        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        for (status, ds) in assoc.send_c_find(self.ds, PatientRootQueryRetrieveInformationModelFind):
            assert status.Status == 0x0000
            assert ds is None
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_cancel(self):
        """Test receiving a cancel response from the peer"""
        def handle(event):
            yield 0xFE00, None

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_C_FIND, handle)]
        )

        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        for (status, ds) in assoc.send_c_find(self.ds, PatientRootQueryRetrieveInformationModelFind):
            assert status.Status == 0xFE00
            assert ds is None
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_invalid(self):
        """Test invalid DIMSE message response received from peer"""
        self.scp = DummyFindSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        class DummyResponse():
            is_valid_response = False

        class DummyDIMSE():
            def send_msg(*args, **kwargs): return
            def get_msg(*args, **kwargs): return DummyResponse(), None

        assoc._reactor_checkpoint.clear()
        while not assoc._is_paused:
            time.sleep(0.01)
        assoc.dimse = DummyDIMSE()
        assert assoc.is_established
        for (_, _) in assoc.send_c_find(self.ds, PatientRootQueryRetrieveInformationModelFind):
            pass

        assert assoc.is_aborted

        self.scp.stop()

    def test_rsp_unknown_status(self):
        """Test unknown status value returned by peer"""
        def handle(event):
            yield 0xFFF0, None

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_C_FIND, handle)]
        )

        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        for (status, ds) in assoc.send_c_find(self.ds, PatientRootQueryRetrieveInformationModelFind):
            assert status.Status == 0xFFF0
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_bad_dataset(self):
        """Test bad dataset returned by evt.EVT_C_FIND handler"""
        def handle(event):
            def test(): pass
            yield 0xFF00, test

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(
            PatientRootQueryRetrieveInformationModelFind,
            ExplicitVRLittleEndian
        )
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_C_FIND, handle)]
        )

        model = PatientRootQueryRetrieveInformationModelFind
        ae.add_requested_context(model, ExplicitVRLittleEndian)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        for (status, ds) in assoc.send_c_find(self.ds, model):
            assert status.Status in range(0xC000, 0xD000)

        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_connection_timeout(self):
        """Test the connection timing out"""
        self.scp = DummyFindSCP()
        self.scp.statuses = [0x0000]
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        class DummyMessage():
            is_valid_response = True
            Identifier = None
            Status = 0x0000
            STATUS_OPTIONAL_KEYWORDS = []

        class DummyDIMSE():
            def send_msg(*args, **kwargs):
                return

            def get_msg(*args, **kwargs):
                return None, None

        assoc._reactor_checkpoint.clear()
        while not assoc._is_paused:
            time.sleep(0.01)
        assoc.dimse = DummyDIMSE()
        assert assoc.is_established

        results = assoc.send_c_find(self.ds, PatientRootQueryRetrieveInformationModelFind)
        assert next(results) == (Dataset(), None)
        with pytest.raises(StopIteration):
            next(results)

        assert assoc.is_aborted

        self.scp.stop()

    def test_decode_failure(self):
        """Test the connection timing out"""
        self.scp = DummyFindSCP()
        self.scp.statuses = [0x0000]
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind,
                                 ExplicitVRLittleEndian)
        ae.add_requested_context(CTImageStorage)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        class DummyDIMSE():
            msg_queue = queue.Queue()
            def send_msg(*args, **kwargs):
                return

            def get_msg(*args, **kwargs):
                def dummy():
                    pass

                rsp = C_FIND()
                rsp.Status = 0xFF00
                rsp.MessageIDBeingRespondedTo = 1
                rsp._dataset = dummy
                return 1, rsp

        assoc._reactor_checkpoint.clear()
        while not assoc._is_paused:
            time.sleep(0.01)
        assoc.dimse = DummyDIMSE()
        assert assoc.is_established

        results = assoc.send_c_find(self.ds, PatientRootQueryRetrieveInformationModelFind)
        status, ds = next(results)

        assert status.Status == 0xFF00
        assert ds is None

        self.scp.stop()

    def test_rsp_not_find(self, caplog):
        """Test receiving a non C-FIND message in response."""
        with caplog.at_level(logging.ERROR, logger='pynetdicom'):
            ae = AE()
            assoc = Association(ae, 'requestor')
            assoc._is_paused = True
            dimse = assoc.dimse
            dimse.msg_queue.put((3, C_STORE()))
            cx = build_context(PatientRootQueryRetrieveInformationModelFind)
            cx._as_scu = True
            cx._as_scp = False
            cx.context_id = 1
            assoc._accepted_cx = {1 : cx}
            identifier = Dataset()
            identifier.PatientID = '*'
            assoc.is_established = True
            results = assoc.send_c_find(
                identifier, PatientRootQueryRetrieveInformationModelFind
            )
            status, ds = next(results)
            assert status == Dataset()
            assert ds is None
            with pytest.raises(StopIteration):
                next(results)
            assert (
                'Received an unexpected C-STORE message from the peer'
            ) in caplog.text
            assert assoc.is_aborted

    def test_rsp_invalid_find(self, caplog):
        """Test receiving an invalid C-FIND message in response."""
        with caplog.at_level(logging.ERROR, logger='pynetdicom'):
            ae = AE()
            assoc = Association(ae, 'requestor')
            assoc._is_paused = True
            dimse = assoc.dimse
            dimse.msg_queue.put((3, C_FIND()))
            cx = build_context(PatientRootQueryRetrieveInformationModelFind)
            cx._as_scu = True
            cx._as_scp = False
            cx.context_id = 1
            assoc._accepted_cx = {1 : cx}
            identifier = Dataset()
            identifier.PatientID = '*'
            assoc.is_established = True
            results = assoc.send_c_find(identifier, PatientRootQueryRetrieveInformationModelFind)
            status, ds = next(results)
            assert status == Dataset()
            assert ds is None
            with pytest.raises(StopIteration):
                next(results)
            assert (
                'Received an invalid C-FIND response from the peer'
            ) in caplog.text
            assert assoc.is_aborted

    def test_query_uid_public(self):
        """Test using a public UID for the query model"""
        def handle(event):
            yield 0x0000, None

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelFind)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_C_FIND, handle)]
        )

        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        responses = assoc.send_c_find(
            self.ds, PatientRootQueryRetrieveInformationModelFind
        )
        for (status, ds) in responses:
            assert status.Status == 0x0000
            assert ds is None
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_query_uid_private(self, caplog):
        """Test using a private UID for the query model"""
        def handle(event):
            yield 0x0000, None

        with caplog.at_level(logging.ERROR, logger='pynetdicom'):
            self.ae = ae = AE()
            ae.acse_timeout = 5
            ae.dimse_timeout = 5
            ae.network_timeout = 5
            ae.add_supported_context('1.2.3.4')
            scp = ae.start_server(
                ('', 11112), block=False, evt_handlers=[(evt.EVT_C_FIND, handle)]
            )

            ae.add_requested_context('1.2.3.4')
            assoc = ae.associate('localhost', 11112)
            assert assoc.is_established

            responses = assoc.send_c_find(self.ds, '1.2.3.4')

            scp.shutdown()

            msg = (
                "No supported service class available for the SOP Class "
                "UID '1.2.3.4'"
            )
            assert msg in caplog.text


class TestAssociationSendCCancel(object):
    """Run tests on Assocation send_c_cancel."""
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

    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyFindSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established
        with pytest.raises(RuntimeError):
            assoc.send_c_cancel(1, 1)
        self.scp.stop()

    def test_good_send(self):
        """Test send_c_cancel_move"""
        self.scp = DummyFindSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assoc.send_c_cancel(1, 1)
        self.scp.stop()


class TestAssociationSendCGet(object):
    """Run tests on Assocation send_c_get."""
    def setup(self):
        """Run prior to each test"""
        self.ds = Dataset()
        #self.ds.SOPClassUID = PatientRootQueryRetrieveInformationModelGet.UID
        self.ds.PatientName = '*'
        self.ds.QueryRetrieveLevel = "PATIENT"

        self.good = Dataset()
        self.good.file_meta = Dataset()
        self.good.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
        self.good.SOPClassUID = CTImageStorage
        self.good.SOPInstanceUID = '1.1.1'
        self.good.PatientName = 'Test'

        self.scp = None

        self.ae = None

    def teardown(self):
        """Clear any active threads"""
        if self.scp:
            self.scp.abort()

        if self.ae:
            self.ae.shutdown()

        time.sleep(0.1)

        for thread in threading.enumerate():
            if isinstance(thread, DummyBaseSCP):
                thread.abort()
                thread.stop()

    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyGetSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established
        with pytest.raises(RuntimeError):
            next(assoc.send_c_get(self.ds, PatientRootQueryRetrieveInformationModelGet))
        self.scp.stop()

    def test_must_be_scp(self):
        """Test failure if not SCP for storage context."""

        store_pname = []

        def handle_store(event):
            store_pname.append(event.dataset.PatientName)
            return 0x0000

        def handle_get(event):
            yield 2
            yield 0xFF00, self.good
            yield 0xFF00, self.good

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=True, scp_role=True)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_C_GET, handle_get)]
        )

        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        #ae.add_requested_context(CTImageStorage)

        role = build_role(CTImageStorage, scu_role=True, scp_role=True)
        assoc = ae.associate(
            'localhost', 11112, ext_neg=[role],
            evt_handlers=[(evt.EVT_C_STORE, handle_store)]
        )
        assert assoc.is_established

        result = assoc.send_c_get(self.ds, PatientRootQueryRetrieveInformationModelGet)
        (status, ds) = next(result)
        assert status.Status == 0xff00
        assert ds is None
        (status, ds) = next(result)
        assert status.Status == 0xff00
        assert ds is None
        (status, ds) = next(result)
        assert status.Status == 0xA702
        assert ds.FailedSOPInstanceUIDList == ['1.1.1', '1.1.1']
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_no_abstract_syntax_match(self):
        """Test when no accepted abstract syntax"""
        self.scp = DummyStorageSCP()
        self.scp.datasets = [self.good]
        self.scp.start()
        ae = AE()
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        def test():
            next(assoc.send_c_get(self.ds, PatientRootQueryRetrieveInformationModelGet))

        with pytest.raises(ValueError):
            test()
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_bad_query_model(self):
        """Test bad query model parameter"""
        self.scp = DummyGetSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        with pytest.raises(ValueError):
            next(assoc.send_c_get(self.ds, query_model='X'))
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_fail_encode_identifier(self):
        """Test a failure in encoding the Identifier dataset"""
        self.scp = DummyGetSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet,
                                 ExplicitVRLittleEndian)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        DATASET.PerimeterValue = b'\x00\x01'

        def test():
            next(assoc.send_c_get(DATASET, PatientRootQueryRetrieveInformationModelGet))
        with pytest.raises(ValueError):
            test()
        assoc.release()
        assert assoc.is_released
        del DATASET.PerimeterValue # Fix up our changes
        self.scp.stop()

    def test_rsp_failure(self):
        """Test receiving a failure response"""
        store_pname = []

        def handle_store(event):
            store_pname.append(event.dataset.PatientName)
            return 0x0000

        def handle_get(event):
            yield 1
            yield 0xA701, None

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=True, scp_role=True)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_C_GET, handle_get)]
        )

        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)

        role = build_role(CTImageStorage, scu_role=True, scp_role=True)
        assoc = ae.associate(
            'localhost', 11112, ext_neg=[role],
            evt_handlers=[(evt.EVT_C_STORE, handle_store)]
        )
        assert assoc.is_established

        for (status, ds) in assoc.send_c_get(self.ds, PatientRootQueryRetrieveInformationModelGet):
            assert status.Status == 0xA701
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_success(self):
        """Test good send"""
        store_pname = []

        def handle_get(event):
            yield 2
            yield 0xFF00, self.good
            yield 0xFF00, self.good

        def handle_store(event):
            store_pname.append(event.dataset.PatientName)
            return 0x0000

        scu_handler = [(evt.EVT_C_STORE, handle_store)]
        scp_handler = [(evt.EVT_C_GET, handle_get)]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=True, scp_role=True)

        scp = ae.start_server(('', 11112), block=False, evt_handlers=scp_handler)

        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)

        role = build_role(CTImageStorage, scp_role=True, scu_role=True)

        assoc = ae.associate(
            'localhost', 11112, evt_handlers=scu_handler, ext_neg=[role]
        )

        assert assoc.is_established

        result = assoc.send_c_get(
            self.ds, PatientRootQueryRetrieveInformationModelGet
        )
        (status, ds) = next(result)
        assert status.Status == 0xff00
        assert ds is None
        (status, ds) = next(result)
        assert status.Status == 0xff00
        assert ds is None
        (status, ds) = next(result)
        assert status.Status == 0x0000
        assert ds is None
        assoc.release()
        assert assoc.is_released

        assert store_pname == ['Test', 'Test']

        scp.shutdown()

    def test_rsp_pending_send_success(self):
        """Test receiving a pending response and sending success"""
        store_pname = []

        def handle_get(event):
            yield 3
            yield 0xFF00, self.good
            yield 0xFF00, self.good

        def handle_store(event):
            store_pname.append(event.dataset.PatientName)
            return 0x0000

        scu_handler = [(evt.EVT_C_STORE, handle_store)]
        scp_handler = [(evt.EVT_C_GET, handle_get)]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=True, scp_role=True)

        scp = ae.start_server(('', 11112), block=False, evt_handlers=scp_handler)

        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)

        role = build_role(CTImageStorage, scp_role=True, scu_role=True)

        assoc = ae.associate(
            'localhost', 11112, evt_handlers=scu_handler, ext_neg=[role]
        )

        assert assoc.is_established

        result = assoc.send_c_get(self.ds, PatientRootQueryRetrieveInformationModelGet)
        (status, ds) = next(result)
        assert status.Status == 0xff00
        assert ds is None
        (status, ds) = next(result)
        assert status.Status == 0xff00
        assert ds is None
        (status, ds) = next(result)
        assert status.Status == 0x0000
        assert ds is None
        assoc.release()
        assert assoc.is_released

        assert store_pname == ['Test', 'Test']

        scp.shutdown()

    def test_rsp_pending_send_failure(self):
        """Test receiving a pending response and sending a failure"""
        store_pname = []

        def handle_store(event):
            store_pname.append(event.dataset.PatientName)
            return 0xA700

        def handle_get(event):
            yield 3
            yield 0xFF00, self.good
            yield 0xFF00, self.good
            yield 0x0000, None

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=True, scp_role=True)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_C_GET, handle_get)]
        )

        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)

        role = build_role(CTImageStorage, scu_role=True, scp_role=True)
        assoc = ae.associate(
            'localhost', 11112, ext_neg=[role],
            evt_handlers=[(evt.EVT_C_STORE, handle_store)]
        )
        assert assoc.is_established

        result = assoc.send_c_get(self.ds, PatientRootQueryRetrieveInformationModelGet)
        # We have 2 status, ds and 1 success
        (status, ds) = next(result)
        assert status.Status == 0xFF00
        assert ds is None
        (status, ds) = next(result)
        assert status.Status == 0xFF00
        assert ds is None
        (status, ds) = next(result)
        assert status.Status == 0xB000
        assert 'FailedSOPInstanceUIDList' in ds
        with pytest.raises(StopIteration):
            next(result)
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_pending_send_warning(self):
        """Test receiving a pending response and sending a warning"""
        store_pname = []

        def handle_store(event):
            store_pname.append(event.dataset.PatientName)
            return 0xB007

        def handle_get(event):
            yield 3
            yield 0xFF00, self.good
            yield 0xFF00, self.good
            yield 0xB000, None

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=True, scp_role=True)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_C_GET, handle_get)]
        )

        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)

        role = build_role(CTImageStorage, scu_role=True, scp_role=True)
        assoc = ae.associate(
            'localhost', 11112, ext_neg=[role],
            evt_handlers=[(evt.EVT_C_STORE, handle_store)]
        )
        assert assoc.is_established

        result = assoc.send_c_get(self.ds, PatientRootQueryRetrieveInformationModelGet)
        # We have 2 status, ds and 1 success
        (status, ds) = next(result)
        assert status.Status == 0xFF00
        assert ds is None
        (status, ds) = next(result)
        assert status.Status == 0xFF00
        assert ds is None
        (status, ds) = next(result)
        assert status.Status == 0xB000
        assert 'FailedSOPInstanceUIDList' in ds
        with pytest.raises(StopIteration):
            next(result)
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_cancel(self):
        """Test receiving a cancel response"""
        store_pname = []

        def handle_store(event):
            store_pname.append(event.dataset.PatientName)
            return 0x0000

        def handle_get(event):
            yield 1
            yield 0xFE00, None

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=True, scp_role=True)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_C_GET, handle_get)]
        )

        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)

        role = build_role(CTImageStorage, scu_role=True, scp_role=True)
        assoc = ae.associate(
            'localhost', 11112, ext_neg=[role],
            evt_handlers=[(evt.EVT_C_STORE, handle_store)]
        )
        assert assoc.is_established

        for (status, ds) in assoc.send_c_get(self.ds, PatientRootQueryRetrieveInformationModelGet):
            assert status.Status == 0xFE00
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_warning(self):
        """Test receiving a warning response"""
        store_pname = []

        def handle_store(event):
            store_pname.append(event.dataset.PatientName)
            return 0xB007

        def handle_get(event):
            yield 3
            yield 0xFF00, self.good
            yield 0xFF00, self.good
            yield 0xB000, None

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=True, scp_role=True)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_C_GET, handle_get)]
        )

        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)

        role = build_role(CTImageStorage, scu_role=True, scp_role=True)
        assoc = ae.associate(
            'localhost', 11112, ext_neg=[role],
            evt_handlers=[(evt.EVT_C_STORE, handle_store)]
        )
        assert assoc.is_established

        result = assoc.send_c_get(self.ds, PatientRootQueryRetrieveInformationModelGet)
        (status, ds) = next(result)
        assert status.Status == 0xff00
        assert ds is None
        (status, ds) = next(result)
        assert status.Status == 0xff00
        assert ds is None
        (status, ds) = next(result)
        assert status.Status == 0xb000
        assert 'FailedSOPInstanceUIDList' in ds
        with pytest.raises(StopIteration):
            next(result)
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_unknown_status(self):
        """Test unknown status value returned by peer"""
        store_pname = []

        def handle_store(event):
            store_pname.append(event.dataset.PatientName)
            return 0x0000

        def handle_get(event):
            yield 1
            yield 0xFFF0, None

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_supported_context(CTImageStorage, scu_role=True, scp_role=True)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_C_GET, handle_get)]
        )

        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)

        role = build_role(CTImageStorage, scu_role=True, scp_role=True)
        assoc = ae.associate(
            'localhost', 11112, ext_neg=[role],
            evt_handlers=[(evt.EVT_C_STORE, handle_store)]
        )
        assert assoc.is_established

        for (status, ds) in assoc.send_c_get(self.ds, PatientRootQueryRetrieveInformationModelGet):
            assert status.Status == 0xFFF0
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_connection_timeout(self):
        """Test the connection timing out"""
        self.scp = DummyGetSCP()
        self.scp.no_suboperations = 2
        self.scp.statuses = [0xFF00, 0xFF00]
        self.scp.datasets = [self.good, self.good]

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
        assoc = ae.associate('localhost', 11112, ext_neg=[role])

        class DummyMessage():
            is_valid_response = True
            DataSet = None
            Status = 0x0000
            STATUS_OPTIONAL_KEYWORDS = []

        class DummyDIMSE():
            def send_msg(*args, **kwargs):
                return

            def get_msg(*args, **kwargs):
                return None, None

        assoc._reactor_checkpoint.clear()
        while not assoc._is_paused:
            time.sleep(0.01)
        assoc.dimse = DummyDIMSE()
        assert assoc.is_established

        results = assoc.send_c_get(self.ds, PatientRootQueryRetrieveInformationModelGet)
        assert next(results) == (Dataset(), None)
        with pytest.raises(StopIteration):
            next(results)

        assert assoc.is_aborted

        self.scp.stop()

    def test_decode_failure(self):
        """Test the connection timing out"""
        self.scp = DummyGetSCP()
        self.scp.no_suboperations = 2
        self.scp.ae.remove_supported_context(CTImageStorage, ImplicitVRLittleEndian)
        self.scp.statuses = [0xFF00, 0xFF00]
        self.scp.datasets = [self.good, self.good]

        self.scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet,
                                 ExplicitVRLittleEndian)
        ae.add_requested_context(CTImageStorage)

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = False
        role.scp_role = True

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role])

        class DummyMessage():
            is_valid_response = True
            DataSet = None
            Status = 0x0000
            STATUS_OPTIONAL_KEYWORDS = []

        class DummyDIMSE():
            def send_msg(*args, **kwargs):
                return

            def get_msg(*args, **kwargs):
                def dummy(): pass
                rsp = C_GET()
                rsp.Status = 0xC000
                rsp.MessageIDBeingRespondedTo = 1
                rsp._dataset = dummy
                return 1, rsp

        assoc._reactor_checkpoint.clear()
        while not assoc._is_paused:
            time.sleep(0.01)
        assoc.dimse = DummyDIMSE()
        assert assoc.is_established

        results = assoc.send_c_get(self.ds, PatientRootQueryRetrieveInformationModelGet)
        status, ds = next(results)

        assert status.Status == 0xC000
        assert ds is None

        self.scp.stop()

    def test_rsp_not_get(self, caplog):
        """Test receiving a non C-GET/C-STORE message in response."""
        with caplog.at_level(logging.ERROR, logger='pynetdicom'):
            ae = AE()
            assoc = Association(ae, 'requestor')
            assoc._is_paused = True
            dimse = assoc.dimse
            dimse.msg_queue.put((3, C_FIND()))
            cx = build_context(PatientRootQueryRetrieveInformationModelGet)
            cx._as_scu = True
            cx._as_scp = False
            cx.context_id = 1
            assoc._accepted_cx = {1 : cx}
            identifier = Dataset()
            identifier.PatientID = '*'
            assoc.is_established = True
            results = assoc.send_c_get(identifier, PatientRootQueryRetrieveInformationModelGet)
            status, ds = next(results)
            assert status == Dataset()
            assert ds is None
            with pytest.raises(StopIteration):
                next(results)
            assert (
                'Received an unexpected C-FIND message from the peer'
            ) in caplog.text
            assert assoc.is_aborted

    def test_rsp_invalid_get(self, caplog):
        """Test receiving an invalid C-GET message in response."""
        with caplog.at_level(logging.ERROR, logger='pynetdicom'):
            ae = AE()
            assoc = Association(ae, 'requestor')
            assoc._is_paused = True
            dimse = assoc.dimse
            dimse.msg_queue.put((3, C_GET()))
            cx = build_context(PatientRootQueryRetrieveInformationModelGet)
            cx._as_scu = True
            cx._as_scp = False
            cx.context_id = 1
            assoc._accepted_cx = {1 : cx}
            identifier = Dataset()
            identifier.PatientID = '*'
            assoc.is_established = True
            results = assoc.send_c_get(identifier, PatientRootQueryRetrieveInformationModelGet)
            status, ds = next(results)
            assert status == Dataset()
            assert ds is None
            with pytest.raises(StopIteration):
                next(results)
            assert (
                'Received an invalid C-GET response from the peer'
            ) in caplog.text
            assert assoc.is_aborted

    def test_query_uid_public(self):
        """Test using a public UID for the query model"""
        def handle(event):
            yield 0
            yield 0x0000, None

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelGet)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_C_GET, handle)]
        )

        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        responses = assoc.send_c_get(
            self.ds, PatientRootQueryRetrieveInformationModelGet
        )
        for (status, ds) in responses:
            assert status.Status == 0x0000
            assert ds is None
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_query_uid_private(self, caplog):
        """Test using a private UID for the query model"""
        def handle(event):
            yield 0
            yield 0x0000, None

        with caplog.at_level(logging.ERROR, logger='pynetdicom'):
            self.ae = ae = AE()
            ae.acse_timeout = 5
            ae.dimse_timeout = 5
            ae.network_timeout = 5
            ae.add_supported_context('1.2.3.4')
            scp = ae.start_server(
                ('', 11112), block=False, evt_handlers=[(evt.EVT_C_GET, handle)]
            )

            ae.add_requested_context('1.2.3.4')
            assoc = ae.associate('localhost', 11112)
            assert assoc.is_established

            responses = assoc.send_c_get(self.ds, '1.2.3.4')

            scp.shutdown()

            msg = (
                "No supported service class available for the SOP Class "
                "UID '1.2.3.4'"
            )
            assert msg in caplog.text


class TestAssociationSendCMove(object):
    """Run tests on Assocation send_c_move."""
    def setup(self):
        """Run prior to each test"""
        self.ds = Dataset()
        self.ds.PatientName = '*'
        self.ds.QueryRetrieveLevel = "PATIENT"

        self.good = Dataset()
        self.good.file_meta = Dataset()
        self.good.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
        self.good.SOPClassUID = CTImageStorage
        self.good.SOPInstanceUID = '1.1.1'
        self.good.PatientName = 'Test'

        self.scp = None
        self.scp2 = None

        self.ae = None

    def teardown(self):
        """Clear any active threads"""
        if self.scp:
            self.scp.abort()

        if self.ae:
            self.ae.shutdown()

        if self.scp2:
            self.scp2.abort()

        time.sleep(0.1)

        for thread in threading.enumerate():
            if isinstance(thread, DummyBaseSCP):
                thread.abort()
                thread.stop()

    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyMoveSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established
        with pytest.raises(RuntimeError):
            next(assoc.send_c_move(self.ds, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove))
        self.scp.stop()

    def test_no_abstract_syntax_match(self):
        """Test when no accepted abstract syntax"""
        self.scp = DummyStorageSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        def test():
            next(assoc.send_c_move(self.ds, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove))

        with pytest.raises(ValueError):
            test()
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_bad_query_model(self):
        """Test bad query model parameter"""
        self.scp = DummyMoveSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        with pytest.raises(ValueError):
            next(assoc.send_c_move(self.ds, b'TESTMOVE', query_model='X'))
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_fail_encode_identifier(self):
        """Test a failure in encoding the Identifier dataset"""
        self.scp = DummyMoveSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove,
                                 ExplicitVRLittleEndian)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        DATASET.PerimeterValue = b'\x00\x01'

        def test():
            next(assoc.send_c_move(
                DATASET, b'SOMEPLACE',
                PatientRootQueryRetrieveInformationModelMove)
            )
        with pytest.raises(ValueError):
            test()
        assoc.release()
        assert assoc.is_released
        del DATASET.PerimeterValue # Fix up our changes
        self.scp.stop()

    def test_move_destination_no_assoc(self):
        """Test move destination failed to assoc"""
        # Move SCP
        def handle_move(event):
            yield 'localhost', 11113
            yield 2
            yield 0xFF00, self.good

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        move_scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_C_MOVE, handle_move)]
        )

        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        for (status, ds) in assoc.send_c_move(
                    self.ds, b'TESTMOVE',
                    PatientRootQueryRetrieveInformationModelMove):
            assert status.Status == 0xa801
        assoc.release()
        assert assoc.is_released

        move_scp.shutdown()

    def test_move_destination_unknown(self):
        """Test unknown move destination"""
        def handle_move(event):
            yield None, None
            yield 1
            yield 0xFF00, self.good

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        move_scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_C_MOVE, handle_move)]
        )

        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        for (status, ds) in assoc.send_c_move(
                    self.ds, b'UNKNOWN',
                    PatientRootQueryRetrieveInformationModelMove):
            assert status.Status == 0xa801
        assoc.release()
        assert assoc.is_released

        move_scp.shutdown()

    def test_move_destination_failed_store(self):
        """Test the destination AE returning failed status"""
        def handle_store(event):
            return 0xA700

        def handle_move(event):
            yield 'localhost', 11113
            yield 2
            yield 0xFF00, self.good
            yield 0xFF00, self.good

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        move_scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_C_MOVE, handle_move)]
        )

        ae.add_supported_context(CTImageStorage)
        store_scp = ae.start_server(
            ('', 11113), block=False, evt_handlers=[(evt.EVT_C_STORE, handle_store)]
        )

        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        result = assoc.send_c_move(
            self.ds, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove
        )
        (status, ds) = next(result)
        assert status.Status == 0xFF00
        (status, ds) = next(result)
        assert status.Status == 0xFF00
        (status, ds) = next(result)
        assert status.Status == 0xA702
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released

        store_scp.shutdown()
        move_scp.shutdown()

    def test_move_destination_warning_store(self):
        """Test the destination AE returning warning status"""
        def handle_store(event):
            return 0xB000

        def handle_move(event):
            yield 'localhost', 11113
            yield 2
            yield 0xFF00, self.good
            yield 0xFF00, self.good

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        move_scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_C_MOVE, handle_move)]
        )

        ae.add_supported_context(CTImageStorage)
        store_scp = ae.start_server(
            ('', 11113), block=False, evt_handlers=[(evt.EVT_C_STORE, handle_store)]
        )

        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        result = assoc.send_c_move(
            self.ds, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove
        )
        (status, ds) = next(result)
        assert status.Status == 0xFF00
        (status, ds) = next(result)
        assert status.Status == 0xFF00
        (status, ds) = next(result)
        assert status.Status == 0xB000

        assoc.release()
        assert assoc.is_released

        store_scp.shutdown()
        move_scp.shutdown()

    def test_rsp_failure(self):
        """Test the handler returning failure status"""
        def handle_store(event):
            return 0x0000

        def handle_move(event):
            yield 'localhost', 11113
            yield 2
            yield 0xC000, None
            yield 0xFF00, self.good

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        move_scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_C_MOVE, handle_move)]
        )

        ae.add_supported_context(CTImageStorage)
        store_scp = ae.start_server(
            ('', 11113), block=False, evt_handlers=[(evt.EVT_C_STORE, handle_store)]
        )

        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        result = assoc.send_c_move(
            self.ds, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove
        )
        (status, ds) = next(result)
        assert status.Status == 0xC000
        assert 'FailedSOPInstanceUIDList' in ds
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released

        store_scp.shutdown()
        move_scp.shutdown()

    def test_rsp_warning(self):
        """Test receiving a warning response from the peer"""
        def handle_store(event):
            return 0xB007

        def handle_move(event):
            yield 'localhost', 11113
            yield 2
            yield 0xFF00, self.good
            yield 0xFF00, self.good

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        move_scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_C_MOVE, handle_move)]
        )

        ae.add_supported_context(CTImageStorage)
        store_scp = ae.start_server(
            ('', 11113), block=False, evt_handlers=[(evt.EVT_C_STORE, handle_store)]
        )

        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        result = assoc.send_c_move(
            self.ds, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove
        )
        (status, ds) = next(result)
        assert status.Status == 0xFF00
        assert ds is None
        (status, ds) = next(result)
        assert status.Status == 0xFF00
        assert ds is None
        (status, ds) = next(result)
        assert status.Status == 0xB000
        assert 'FailedSOPInstanceUIDList' in ds
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released

        store_scp.shutdown()
        move_scp.shutdown()

    def test_rsp_cancel(self):
        """Test the handler returning cancel status"""
        def handle_store(event):
            return 0x0000

        def handle_move(event):
            yield 'localhost', 11113
            yield 2
            yield 0xFE00, self.good
            yield 0xFF00, self.good

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        move_scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_C_MOVE, handle_move)]
        )

        ae.add_supported_context(CTImageStorage)
        store_scp = ae.start_server(
            ('', 11113), block=False, evt_handlers=[(evt.EVT_C_STORE, handle_store)]
        )

        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        result = assoc.send_c_move(
            self.ds, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove
        )
        (status, ds) = next(result)
        assert status.Status == 0xFE00

        assoc.release()
        assert assoc.is_released

        store_scp.shutdown()
        move_scp.shutdown()

    def test_rsp_success(self):
        """Test the handler returning success status"""

        def handle_store(event):
            return 0x0000

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5

        # Storage SCP
        ae.add_supported_context(CTImageStorage)
        store_scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_C_STORE, handle_store)]
        )

        # Move SCP
        def handle_move(event):
            yield 'localhost', 11112
            yield 2
            yield 0xff00, self.good

        ae.add_requested_context(CTImageStorage)
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(StudyRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(PatientStudyOnlyQueryRetrieveInformationModelMove)
        move_scp = ae.start_server(
            ('', 11113), block=False, evt_handlers=[(evt.EVT_C_MOVE, handle_move)]
        )

        # Move SCU
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(StudyRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(PatientStudyOnlyQueryRetrieveInformationModelMove)

        assoc = ae.associate('localhost', 11113)
        assert assoc.is_established

        result = assoc.send_c_move(
            self.ds, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove
        )
        (status, ds) = next(result)
        assert status.Status == 0xFF00
        assert ds is None
        (status, ds) = next(result)
        assert status.Status == 0x0000
        assert ds is None
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released

        store_scp.shutdown()
        move_scp.shutdown()

    def test_rsp_unknown_status(self):
        """Test unknown status value returned by peer"""
        def handle_store(event):
            return 0xA700

        def handle_move(event):
            yield 'localhost', 11113
            yield 2
            yield 0xFFF0, self.good
            yield 0xFF00, self.good

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        move_scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_C_MOVE, handle_move)]
        )

        ae.add_supported_context(CTImageStorage)
        store_scp = ae.start_server(
            ('', 11113), block=False, evt_handlers=[(evt.EVT_C_STORE, handle_store)]
        )

        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        for (status, ds) in assoc.send_c_move(
                    self.ds, b'TESTMOVE',
                    PatientRootQueryRetrieveInformationModelMove):
            assert status.Status == 0xFFF0
        assoc.release()
        assert assoc.is_released

        store_scp.shutdown()
        move_scp.shutdown()

    def test_multiple_c_move(self):
        """Test multiple C-MOVE operation requests"""
        def handle_store(event):
            return 0x0000

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5

        # Storage SCP
        ae.add_supported_context(CTImageStorage)
        store_scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_C_STORE, handle_store)]
        )

        # Move SCP
        def handle_move(event):
            yield 'localhost', 11112
            yield 2
            yield 0xff00, self.good
            yield 0xff00, self.good

        ae.add_requested_context(CTImageStorage)
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(StudyRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(PatientStudyOnlyQueryRetrieveInformationModelMove)
        move_scp = ae.start_server(
            ('', 11113), block=False, evt_handlers=[(evt.EVT_C_MOVE, handle_move)]
        )

        # Move SCU
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(StudyRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(PatientStudyOnlyQueryRetrieveInformationModelMove)

        for ii in range(20):
            assoc = ae.associate('localhost', 11113)
            assert assoc.is_established
            assert not assoc.is_released
            result = assoc.send_c_move(
                self.ds,
                b'TESTMOVE',
                PatientRootQueryRetrieveInformationModelMove
            )
            (status, ds) = next(result)
            assert status.Status == 0xFF00
            (status, ds) = next(result)
            assert status.Status == 0xFF00
            (status, ds) = next(result)
            assert status.Status == 0x0000
            with pytest.raises(StopIteration):
                next(result)
            assoc.release()
            assert assoc.is_released
            assert not assoc.is_established

        store_scp.shutdown()
        move_scp.shutdown()

    def test_connection_timeout(self):
        """Test the connection timing out"""
        self.scp = DummyMoveSCP()
        self.scp.no_suboperations = 2
        self.scp.statuses = [0xFF00, 0xFF00]
        self.scp.datasets = [self.good, self.good]

        self.scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        class DummyMessage():
            is_valid_response = True
            Identifier = None
            Status = 0x0000
            STATUS_OPTIONAL_KEYWORDS = []

        class DummyDIMSE():
            def send_msg(*args, **kwargs):
                return

            def get_msg(*args, **kwargs):
                return None, None

        assoc._reactor_checkpoint.clear()
        while not assoc._is_paused:
            time.sleep(0.01)
        assoc.dimse = DummyDIMSE()
        assert assoc.is_established

        results = assoc.send_c_move(
            self.ds, b'TEST', PatientRootQueryRetrieveInformationModelMove
        )
        assert next(results) == (Dataset(), None)
        with pytest.raises(StopIteration):
            next(results)

        assert assoc.is_aborted

        self.scp.stop()

    def test_decode_failure(self):
        """Test the connection timing out"""
        self.scp = DummyMoveSCP()
        self.scp.no_suboperations = 2
        self.scp.statuses = [0xFF00, 0xFF00]
        self.scp.datasets = [self.good, self.good]

        self.scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove,
                                 ExplicitVRLittleEndian)
        ae.add_requested_context(CTImageStorage)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        class DummyMessage():
            is_valid_response = True
            DataSet = None
            Status = 0x0000
            STATUS_OPTIONAL_KEYWORDS = []

        class DummyDIMSE():
            def send_msg(*args, **kwargs):
                return

            def get_msg(*args, **kwargs):
                def dummy(): pass

                rsp = C_MOVE()
                rsp.MessageIDBeingRespondedTo = 1
                rsp.Status = 0xC000
                rsp._dataset = dummy
                return 1, rsp

        assoc._reactor_checkpoint.clear()
        while not assoc._is_paused:
            time.sleep(0.01)
        assoc.dimse = DummyDIMSE()
        assert assoc.is_established

        results = assoc.send_c_move(
            self.ds, b'TEST', PatientRootQueryRetrieveInformationModelMove
        )
        status, ds = next(results)

        assert status.Status == 0xC000
        assert ds is None

        self.scp.stop()

    def test_rsp_not_move(self, caplog):
        """Test receiving a non C-MOVE/C-STORE message in response."""
        with caplog.at_level(logging.ERROR, logger='pynetdicom'):
            ae = AE()
            assoc = Association(ae, 'requestor')
            assoc._is_paused = True
            dimse = assoc.dimse
            dimse.msg_queue.put((3, C_FIND()))
            cx = build_context(PatientRootQueryRetrieveInformationModelMove)
            cx._as_scu = True
            cx._as_scp = False
            cx.context_id = 1
            assoc._accepted_cx = {1 : cx}
            identifier = Dataset()
            identifier.PatientID = '*'
            assoc.is_established = True
            results = assoc.send_c_move(
                identifier, b'A', PatientRootQueryRetrieveInformationModelMove
            )
            status, ds = next(results)
            assert status == Dataset()
            assert ds is None
            with pytest.raises(StopIteration):
                next(results)
            assert (
                'Received an unexpected C-FIND message from the peer'
            ) in caplog.text
            assert assoc.is_aborted

    def test_rsp_invalid_move(self, caplog):
        """Test receiving an invalid C-MOVE message in response."""
        with caplog.at_level(logging.ERROR, logger='pynetdicom'):
            ae = AE()
            assoc = Association(ae, 'requestor')
            assoc._is_paused = True
            dimse = assoc.dimse
            dimse.msg_queue.put((3, C_MOVE()))
            cx = build_context(PatientRootQueryRetrieveInformationModelMove)
            cx._as_scu = True
            cx._as_scp = False
            cx.context_id = 1
            assoc._accepted_cx = {1 : cx}
            identifier = Dataset()
            identifier.PatientID = '*'
            assoc.is_established = True
            results = assoc.send_c_move(
                identifier, b'A', PatientRootQueryRetrieveInformationModelMove
            )
            status, ds = next(results)
            assert status == Dataset()
            assert ds is None
            with pytest.raises(StopIteration):
                next(results)
            assert (
                'Received an invalid C-MOVE response from the peer'
            ) in caplog.text
            assert assoc.is_aborted

    def test_query_uid_public(self):
        """Test using a public UID for the query model"""

        def handle_store(event):
            return 0x0000

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5

        # Storage SCP
        ae.add_supported_context(CTImageStorage)
        store_scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_C_STORE, handle_store)]
        )

        # Move SCP
        def handle_move(event):
            yield 'localhost', 11112
            yield 2
            yield 0xff00, self.good

        ae.add_requested_context(CTImageStorage)
        ae.add_supported_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(StudyRootQueryRetrieveInformationModelMove)
        ae.add_supported_context(PatientStudyOnlyQueryRetrieveInformationModelMove)
        move_scp = ae.start_server(
            ('', 11113), block=False, evt_handlers=[(evt.EVT_C_MOVE, handle_move)]
        )

        # Move SCU
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(StudyRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(PatientStudyOnlyQueryRetrieveInformationModelMove)

        assoc = ae.associate('localhost', 11113)
        assert assoc.is_established

        result = assoc.send_c_move(
            self.ds, b'TESTMOVE', PatientRootQueryRetrieveInformationModelMove
        )
        (status, ds) = next(result)
        assert status.Status == 0xFF00
        assert ds is None
        (status, ds) = next(result)
        assert status.Status == 0x0000
        assert ds is None
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released

        store_scp.shutdown()
        move_scp.shutdown()

    def test_query_uid_private(self, caplog):
        """Test using a private UID for the query model"""
        def handle_store(event):
            return 0x0000

        def handle_move(event):
            yield 'localhost', 11112
            yield 2
            yield 0xff00, self.good

        with caplog.at_level(logging.ERROR, logger='pynetdicom'):
            self.ae = ae = AE()
            ae.acse_timeout = 5
            ae.dimse_timeout = 5
            ae.network_timeout = 5

            # Storage SCP
            ae.add_supported_context(CTImageStorage)
            store_scp = ae.start_server(
                ('', 11112), block=False, evt_handlers=[(evt.EVT_C_STORE, handle_store)]
            )

            ae.add_requested_context(CTImageStorage)
            ae.add_supported_context('1.2.3.4')
            move_scp = ae.start_server(
                ('', 11113), block=False, evt_handlers=[(evt.EVT_C_MOVE, handle_move)]
            )

            # Move SCU
            ae.add_requested_context('1.2.3.4')

            assoc = ae.associate('localhost', 11113)
            assert assoc.is_established

            result = assoc.send_c_move(self.ds, b'TESTMOVE', '1.2.3.4')

            store_scp.shutdown()
            move_scp.shutdown()

            msg = (
                "No supported service class available for the SOP Class "
                "UID '1.2.3.4'"
            )
            assert msg in caplog.text


class TestGetValidContext(object):
    """Tests for Association._get_valid_context."""
    def setup(self):
        """Run prior to each test"""
        self.scp = None
        self.ae = None

    def teardown(self):
        """Clear any active threads"""
        if self.scp:
            self.scp.abort()

        if self.ae:
            self.ae.shutdown()

        time.sleep(0.1)

        for thread in threading.enumerate():
            if isinstance(thread, DummyBaseSCP):
                thread.abort()
                thread.stop()

    def test_id_no_abstract_syntax_match(self):
        """Test exception raised if with ID no abstract syntax match"""
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        msg = (
            r"No presentation context for 'CT Image Storage' has been "
            r"accepted by the peer for the SCU role"
        )
        with pytest.raises(ValueError, match=msg):
            assoc._get_valid_context(CTImageStorage, '', 'scu', context_id=1)

        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_id_transfer_syntax(self):
        """Test match with context ID."""
        self.scp = DummyVerificationSCP()
        self.scp.ae.add_supported_context(CTImageStorage)
        self.scp.ae.add_supported_context(
            CTImageStorage,
            [ExplicitVRLittleEndian, JPEGBaseline]
        )
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.add_requested_context(CTImageStorage)
        ae.add_requested_context(CTImageStorage, JPEGBaseline)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        # Uncompressed accepted, different uncompressed sent
        cx = assoc._get_valid_context(CTImageStorage,
                                      '',
                                      'scu',
                                      context_id=3)
        assert cx.context_id == 3
        assert cx.abstract_syntax == CTImageStorage
        assert cx.transfer_syntax[0] == ImplicitVRLittleEndian
        assert cx.as_scu is True

        cx = assoc._get_valid_context(CTImageStorage,
                                      '',
                                      'scu',
                                      context_id=5)
        assert cx.context_id == 5
        assert cx.abstract_syntax == CTImageStorage
        assert cx.transfer_syntax[0] == JPEGBaseline
        assert cx.as_scu is True

    def test_id_no_transfer_syntax(self):
        """Test exception raised if with ID no transfer syntax match."""
        self.scp = DummyVerificationSCP()
        self.scp.ae.add_supported_context(CTImageStorage, JPEGBaseline)
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.add_requested_context(CTImageStorage, JPEGBaseline)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        # Confirm otherwise OK
        cx = assoc._get_valid_context('1.2.840.10008.1.1',
                                      '',
                                      'scu',
                                      context_id=1)
        assert cx.context_id == 1
        assert cx.transfer_syntax[0] == ImplicitVRLittleEndian

        # Uncompressed accepted, compressed sent
        msg = (
            r"No presentation context for 'Verification SOP Class' has been "
            r"accepted by the peer with 'JPEG Baseline \(Process 1\)' "
            r"transfer syntax for the SCU role"
        )
        with pytest.raises(ValueError, match=msg):
            assoc._get_valid_context('1.2.840.10008.1.1',
                                     JPEGBaseline,
                                     'scu',
                                     context_id=1)

        # Compressed (JPEGBaseline) accepted, uncompressed sent
        # Confirm otherwise OK
        cx = assoc._get_valid_context(CTImageStorage,
                                      JPEGBaseline,
                                      'scu',
                                      context_id=3)
        assert cx.context_id == 3
        assert cx.transfer_syntax[0] == JPEGBaseline

        msg = (
            r"No presentation context for 'CT Image Storage' has been "
            r"accepted by the peer with 'Implicit VR Little Endian' "
            r"transfer syntax for the SCU role"
        )
        with pytest.raises(ValueError, match=msg):
            assoc._get_valid_context(CTImageStorage,
                                     ImplicitVRLittleEndian,
                                     'scu',
                                     context_id=3)

        # Compressed (JPEGBaseline) accepted, compressed (JPEG2000) sent
        msg = (
            r"No presentation context for 'CT Image Storage' has been "
            r"accepted by the peer with 'JPEG 2000 Image Compression' "
            r"transfer syntax for the SCU role"
        )
        with pytest.raises(ValueError, match=msg):
            assoc._get_valid_context(CTImageStorage,
                                     JPEG2000,
                                     'scu',
                                     context_id=3)

        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_id_no_role_scp(self):
        """Test exception raised if with ID no role match."""
        self.scp = DummyVerificationSCP()
        self.scp.ae.add_supported_context(CTImageStorage, JPEGBaseline)
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.add_requested_context(CTImageStorage, JPEGBaseline)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        # Confirm matching otherwise OK
        cx = assoc._get_valid_context('1.2.840.10008.1.1',
                                      '',
                                      'scu',
                                      context_id=1)
        assert cx.context_id == 1
        assert cx.as_scu is True

        # Any transfer syntax
        msg = (
            r"No presentation context for 'Verification SOP Class' has been "
            r"accepted by the peer "
            r"for the SCP role"
        )
        with pytest.raises(ValueError, match=msg):
            assoc._get_valid_context('1.2.840.10008.1.1',
                                     '',
                                     'scp',
                                     context_id=1)

        # Transfer syntax used
        msg = (
            r"No presentation context for 'Verification SOP Class' has been "
            r"accepted by the peer "
            r"with 'Implicit VR Little Endian' transfer syntax "
            r"for the SCP role"
        )
        with pytest.raises(ValueError, match=msg):
            assoc._get_valid_context('1.2.840.10008.1.1',
                                     ImplicitVRLittleEndian,
                                     'scp',
                                     context_id=1)

    def test_id_no_role_scu(self):
        """Test exception raised if with ID no role match."""
        self.scp = DummyGetSCP()
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
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
        assert assoc.is_established

        # Confirm matching otherwise OK
        cx = assoc._get_valid_context(CTImageStorage,
                                      '',
                                      'scp',
                                      context_id=3)
        assert cx.context_id == 3
        assert cx.as_scp is True

        # Any transfer syntax
        msg = (
            r"No presentation context for 'CT Image Storage' has been "
            r"accepted by the peer "
            r"for the SCU role"
        )
        with pytest.raises(ValueError, match=msg):
            assoc._get_valid_context(CTImageStorage,
                                     '',
                                     'scu',
                                     context_id=3)

        # Transfer syntax used
        msg = (
            r"No presentation context for 'CT Image Storage' has been "
            r"accepted by the peer "
            r"with 'Implicit VR Little Endian' transfer syntax "
            r"for the SCU role"
        )
        with pytest.raises(ValueError, match=msg):
            assoc._get_valid_context(CTImageStorage,
                                     ImplicitVRLittleEndian,
                                     'scu',
                                     context_id=3)

    def test_no_id_no_abstract_syntax_match(self):
        """Test exception raised if no abstract syntax match"""
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        # Test otherwise OK
        assoc._get_valid_context(VerificationSOPClass, '', 'scu')

        msg = (
            r"No presentation context for 'CT Image Storage' has been "
            r"accepted by the peer "
            r"for the SCU role"
        )
        with pytest.raises(ValueError, match=msg):
            assoc._get_valid_context(CTImageStorage, '', 'scu')

        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_no_id_transfer_syntax(self):
        """Test match."""
        self.scp = DummyVerificationSCP()
        self.scp.ae.add_supported_context(CTImageStorage, JPEGBaseline)
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.add_requested_context(CTImageStorage, JPEGBaseline)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        # Uncompressed accepted, different uncompressed sent
        cx = assoc._get_valid_context('1.2.840.10008.1.1',
                                      ExplicitVRLittleEndian,
                                      'scu')
        assert cx.context_id == 1
        assert cx.abstract_syntax == VerificationSOPClass
        assert cx.transfer_syntax[0] == ImplicitVRLittleEndian
        assert cx.as_scu is True

    def test_no_id_no_transfer_syntax(self):
        """Test exception raised if no transfer syntax match."""
        self.scp = DummyVerificationSCP()
        self.scp.ae.add_supported_context(CTImageStorage, JPEGBaseline)
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.add_requested_context(CTImageStorage, JPEGBaseline)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        # Confirm otherwise OK
        cx = assoc._get_valid_context('1.2.840.10008.1.1', '', 'scu')
        assert cx.context_id == 1
        assert cx.transfer_syntax[0] == ImplicitVRLittleEndian

        # Uncompressed accepted, compressed sent
        msg = (
            r"No presentation context for 'Verification SOP Class' has been "
            r"accepted by the peer "
            r"with 'JPEG Baseline \(Process 1\)' transfer syntax "
            r"for the SCU role"
        )
        with pytest.raises(ValueError, match=msg):
            assoc._get_valid_context('1.2.840.10008.1.1', JPEGBaseline, 'scu')

        # Compressed (JPEGBaseline) accepted, uncompressed sent
        # Confirm otherwise OK
        cx = assoc._get_valid_context(CTImageStorage, JPEGBaseline, 'scu')
        assert cx.context_id == 3
        assert cx.transfer_syntax[0] == JPEGBaseline

        msg = (
            r"No presentation context for 'CT Image Storage' has been "
            r"accepted by the peer "
            r"with 'Implicit VR Little Endian' transfer syntax "
            r"for the SCU role"
        )
        with pytest.raises(ValueError, match=msg):
            assoc._get_valid_context(CTImageStorage,
                                     ImplicitVRLittleEndian,
                                     'scu')

        # Compressed (JPEGBaseline) accepted, compressed (JPEG2000) sent
        msg = (
            r"No presentation context for 'CT Image Storage' has been "
            r"accepted by the peer "
            r"with 'JPEG 2000 Image Compression' transfer syntax "
            r"for the SCU role"
        )
        with pytest.raises(ValueError, match=msg):
            assoc._get_valid_context(CTImageStorage, JPEG2000, 'scu')

        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_no_id_no_role_scp(self):
        """Test exception raised if no role match."""
        self.scp = DummyVerificationSCP()
        self.scp.ae.add_supported_context(CTImageStorage, JPEGBaseline)
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.add_requested_context(CTImageStorage, JPEGBaseline)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        # Confirm matching otherwise OK
        cx = assoc._get_valid_context('1.2.840.10008.1.1', '', 'scu')
        assert cx.context_id == 1
        assert cx.as_scu is True

        # Any transfer syntax
        msg = (
            r"No presentation context for 'Verification SOP Class' has been "
            r"accepted by the peer "
            r"for the SCP role"
        )
        with pytest.raises(ValueError, match=msg):
            assoc._get_valid_context('1.2.840.10008.1.1', '', 'scp')

        # Transfer syntax used
        msg = (
            r"No presentation context for 'Verification SOP Class' has been "
            r"accepted by the peer "
            r"with 'Implicit VR Little Endian' transfer syntax "
            r"for the SCP role"
        )
        with pytest.raises(ValueError, match=msg):
            assoc._get_valid_context('1.2.840.10008.1.1',
                                     ImplicitVRLittleEndian,
                                     'scp')

    def test_no_id_no_role_scu(self):
        """Test exception raised if no role match."""
        self.scp = DummyGetSCP()
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
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
        assert assoc.is_established

        # Confirm matching otherwise OK
        cx = assoc._get_valid_context(CTImageStorage, '', 'scp')
        assert cx.context_id == 3
        assert cx.as_scp is True

        # Any transfer syntax
        msg = (
            r"No presentation context for 'CT Image Storage' has been "
            r"accepted by the peer "
            r"for the SCU role"
        )
        with pytest.raises(ValueError, match=msg):
            assoc._get_valid_context(CTImageStorage,
                                     '',
                                     'scu')

        # Transfer syntax used
        msg = (
            r"No presentation context for 'CT Image Storage' has been "
            r"accepted by the peer "
            r"with 'Implicit VR Little Endian' transfer syntax "
            r"for the SCU role"
        )
        with pytest.raises(ValueError, match=msg):
            assoc._get_valid_context(CTImageStorage,
                                     ImplicitVRLittleEndian,
                                     'scu')

    def test_implicit_explicit(self):
        """Test matching when both implicit and explicit are available."""
        self.scp = DummyVerificationSCP()
        self.scp.ae.add_supported_context(CTImageStorage, ImplicitVRLittleEndian)
        self.scp.ae.add_supported_context(CTImageStorage, ExplicitVRLittleEndian)
        self.scp.start()
        ae = AE()
        ae.add_requested_context(CTImageStorage, ImplicitVRLittleEndian)
        ae.add_requested_context(CTImageStorage, ExplicitVRLittleEndian)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        cx = assoc._get_valid_context(
            CTImageStorage, ExplicitVRLittleEndian, 'scu'
        )
        assert cx.context_id == 3
        assert cx.abstract_syntax == CTImageStorage
        assert cx.transfer_syntax[0] == ExplicitVRLittleEndian
        assert cx.as_scu is True

        cx = assoc._get_valid_context(
            CTImageStorage, ImplicitVRLittleEndian, 'scu'
        )
        assert cx.context_id == 1
        assert cx.abstract_syntax == CTImageStorage
        assert cx.transfer_syntax[0] == ImplicitVRLittleEndian
        assert cx.as_scu is True

        self.scp.abort()

    def test_explicit_implicit(self):
        """Test matching when both implicit and explicit are available."""
        self.scp = DummyVerificationSCP()
        self.scp.ae.add_supported_context(CTImageStorage, ExplicitVRLittleEndian)
        self.scp.ae.add_supported_context(CTImageStorage, ImplicitVRLittleEndian)
        self.scp.start()
        ae = AE()
        ae.add_requested_context(CTImageStorage, ExplicitVRLittleEndian)
        ae.add_requested_context(CTImageStorage, ImplicitVRLittleEndian)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        cx = assoc._get_valid_context(
            CTImageStorage, ExplicitVRLittleEndian, 'scu'
        )
        assert cx.context_id == 1
        assert cx.abstract_syntax == CTImageStorage
        assert cx.transfer_syntax[0] == ExplicitVRLittleEndian
        assert cx.as_scu is True

        cx = assoc._get_valid_context(
            CTImageStorage, ImplicitVRLittleEndian, 'scu'
        )
        assert cx.context_id == 3
        assert cx.abstract_syntax == CTImageStorage
        assert cx.transfer_syntax[0] == ImplicitVRLittleEndian
        assert cx.as_scu is True

        self.scp.abort()

    def test_little_big(self):
        """Test no match from little to big endian."""
        self.scp = DummyVerificationSCP()
        self.scp.ae.add_supported_context(MRImageStorage, ExplicitVRLittleEndian)
        self.scp.ae.add_supported_context(CTImageStorage, ImplicitVRLittleEndian)
        self.scp.start()

        ae = AE()
        ae.add_requested_context(MRImageStorage, ExplicitVRBigEndian)
        ae.add_requested_context(MRImageStorage, ExplicitVRLittleEndian)
        ae.add_requested_context(CTImageStorage, ImplicitVRLittleEndian)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        msg = (
            r"No presentation context for 'MR Image Storage' has been "
            r"accepted by the peer with 'Explicit VR Big Endian' transfer "
            r"syntax for the SCU role"
        )
        with pytest.raises(ValueError, match=msg):
            assoc._get_valid_context(
                MRImageStorage, ExplicitVRBigEndian, 'scu'
            )

        self.scp.abort()

    def test_ups_push_action(self, caplog):
        """Test matching UPS Push to other UPS contexts."""
        def handle(event, cx):
            cx.append(event.context)
            return 0x0000, None

        self.ae = ae = AE()
        ae.network_timeout = 5
        ae.dimse_timeout = 5
        ae.acse_timeout = 5
        ae.add_supported_context(UnifiedProcedureStepPullSOPClass)

        contexts = []
        handlers = [(evt.EVT_N_ACTION, handle, [contexts])]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.add_requested_context(UnifiedProcedureStepPullSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        msg = (
            r"No exact matching context found for 'Unified Procedure Step "
            r"- Push SOP Class', checking accepted contexts for other UPS "
            r"SOP classes"
        )
        ds = Dataset()
        ds.TransactionUID = '1.2.3.4'
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            status, rsp = assoc.send_n_action(
                ds, 1, UnifiedProcedureStepPushSOPClass, '1.2.3'
            )
            assert msg in caplog.text

        assoc.release()
        assert contexts[0].abstract_syntax == UnifiedProcedureStepPullSOPClass
        scp.shutdown()

    def test_ups_push_get(self, caplog):
        """Test matching UPS Push to other UPS contexts."""
        self.ae = ae = AE()
        ae.network_timeout = 5
        ae.dimse_timeout = 5
        ae.acse_timeout = 5
        ae.add_supported_context(UnifiedProcedureStepPullSOPClass)

        scp = ae.start_server(('', 11112), block=False)

        ae.add_requested_context(UnifiedProcedureStepPullSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        msg = (
            r"No exact matching context found for 'Unified Procedure Step "
            r"- Push SOP Class', checking accepted contexts for other UPS "
            r"SOP classes"
        )
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            status, rsp = assoc.send_n_get(
                [0x00100010], UnifiedProcedureStepPushSOPClass, '1.2.3'
            )
            assert msg in caplog.text

        assoc.release()
        scp.shutdown()

    def test_ups_push_set(self, caplog):
        """Test matching UPS Push to other UPS contexts."""
        self.ae = ae = AE()
        ae.network_timeout = 5
        ae.dimse_timeout = 5
        ae.acse_timeout = 5
        ae.add_supported_context(UnifiedProcedureStepPullSOPClass)

        scp = ae.start_server(('', 11112), block=False)

        ae.add_requested_context(UnifiedProcedureStepPullSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        msg = (
            r"No exact matching context found for 'Unified Procedure Step "
            r"- Push SOP Class', checking accepted contexts for other UPS "
            r"SOP classes"
        )
        ds = Dataset()
        ds.TransactionUID = '1.2.3.4'
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            status, rsp = assoc.send_n_set(
                ds, UnifiedProcedureStepPushSOPClass, '1.2.3'
            )
            assert msg in caplog.text

        assoc.release()
        scp.shutdown()

    def test_ups_push_er(self, caplog):
        """Test matching UPS Push to other UPS contexts."""
        self.ae = ae = AE()
        ae.network_timeout = 5
        ae.dimse_timeout = 5
        ae.acse_timeout = 5
        ae.add_supported_context(UnifiedProcedureStepPullSOPClass)

        scp = ae.start_server(('', 11112), block=False)

        ae.add_requested_context(UnifiedProcedureStepPullSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        msg = (
            r"No exact matching context found for 'Unified Procedure Step "
            r"- Push SOP Class', checking accepted contexts for other UPS "
            r"SOP classes"
        )
        ds = Dataset()
        ds.TransactionUID = '1.2.3.4'
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            status, rsp = assoc.send_n_event_report(
                ds, 1, UnifiedProcedureStepPushSOPClass, '1.2.3'
            )
            assert msg in caplog.text

        assoc.release()
        scp.shutdown()

    def test_ups_push_find(self, caplog):
        """Test matching UPS Push to other UPS contexts."""
        self.ae = ae = AE()
        ae.network_timeout = 5
        ae.dimse_timeout = 5
        ae.acse_timeout = 5
        ae.add_supported_context(UnifiedProcedureStepPullSOPClass)

        scp = ae.start_server(('', 11112), block=False)

        ae.add_requested_context(UnifiedProcedureStepPullSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        msg = (
            r"No exact matching context found for 'Unified Procedure Step "
            r"- Push SOP Class', checking accepted contexts for other UPS "
            r"SOP classes"
        )
        ds = Dataset()
        ds.TransactionUID = '1.2.3.4'
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            responses = assoc.send_c_find(ds, UnifiedProcedureStepPushSOPClass)
            assert msg in caplog.text

        assoc.release()
        scp.shutdown()


class TestEventHandlingAcceptor(object):
    """Test the transport events and handling as acceptor."""
    def setup(self):
        self.ae = None
        _config.LOG_HANDLER_LEVEL = 'none'

    def teardown(self):
        if self.ae:
            self.ae.shutdown()

        _config.LOG_HANDLER_LEVEL = 'standard'

    def test_no_handlers(self):
        """Test with no association event handlers bound."""
        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)
        assert scp.get_handlers(evt.EVT_ABORTED) == []
        assert scp.get_handlers(evt.EVT_ACCEPTED) == []
        assert scp.get_handlers(evt.EVT_ESTABLISHED) == []
        assert scp.get_handlers(evt.EVT_REJECTED) == []
        assert scp.get_handlers(evt.EVT_RELEASED) == []
        assert scp.get_handlers(evt.EVT_REQUESTED) == []
        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established
        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_ABORTED) == []
        assert scp.get_handlers(evt.EVT_ACCEPTED) == []
        assert scp.get_handlers(evt.EVT_ESTABLISHED) == []
        assert scp.get_handlers(evt.EVT_REJECTED) == []
        assert scp.get_handlers(evt.EVT_RELEASED) == []
        assert scp.get_handlers(evt.EVT_REQUESTED) == []

        assert assoc.get_handlers(evt.EVT_ABORTED) == []
        assert assoc.get_handlers(evt.EVT_ACCEPTED) == []
        assert assoc.get_handlers(evt.EVT_ESTABLISHED) == []
        assert assoc.get_handlers(evt.EVT_REJECTED) == []
        assert assoc.get_handlers(evt.EVT_RELEASED) == []
        assert assoc.get_handlers(evt.EVT_REQUESTED) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_ABORTED) == []
        assert child.get_handlers(evt.EVT_ACCEPTED) == []
        assert child.get_handlers(evt.EVT_ESTABLISHED) == []
        assert child.get_handlers(evt.EVT_REJECTED) == []
        assert child.get_handlers(evt.EVT_RELEASED) == []
        assert child.get_handlers(evt.EVT_REQUESTED) == []

        assoc.release()
        scp.shutdown()

    def test_no_handlers_unbind(self):
        """Test unbinding a handler that's not bound."""
        _config.LOG_HANDLER_LEVEL = 'standard'

        def dummy(event):
            pass

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)

        assert dummy not in scp._handlers[evt.EVT_DIMSE_SENT]
        scp.unbind(evt.EVT_DIMSE_SENT, dummy)
        assert dummy not in scp._handlers[evt.EVT_DIMSE_SENT]

        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established
        assert len(scp.active_associations) == 1

        assert dummy not in assoc._handlers[evt.EVT_DIMSE_SENT]
        assoc.unbind(evt.EVT_DIMSE_SENT, dummy)
        assert dummy not in assoc._handlers[evt.EVT_DIMSE_SENT]


        child = scp.active_associations[0]
        assert dummy not in child._handlers[evt.EVT_DIMSE_SENT]
        child.unbind(evt.EVT_DIMSE_SENT, dummy)
        assert dummy not in child._handlers[evt.EVT_DIMSE_SENT]

        assoc.release()
        scp.shutdown()

    def test_unbind_intervention(self):
        """Test unbinding a user intervention handler."""
        def dummy(event):
            pass

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)
        scp.bind(evt.EVT_C_ECHO, dummy)
        assert scp.get_handlers(evt.EVT_C_ECHO) == (dummy, None)
        scp.unbind(evt.EVT_C_ECHO, dummy)
        assert scp.get_handlers(evt.EVT_C_ECHO) != (dummy, None)
        assert scp.get_handlers(evt.EVT_C_ECHO) == (evt._c_echo_handler, None)

        scp.shutdown()

    def test_unbind_intervention_assoc(self):
        """Test unbinding a user intervention handler."""
        def dummy(event):
            pass

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)
        scp.bind(evt.EVT_C_ECHO, dummy)
        assert scp.get_handlers(evt.EVT_C_ECHO) == (dummy, None)

        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established
        assert len(scp.active_associations) == 1

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_C_ECHO) == (dummy, None)

        scp.unbind(evt.EVT_C_ECHO, dummy)
        assert scp.get_handlers(evt.EVT_C_ECHO) != (dummy, None)
        assert scp.get_handlers(evt.EVT_C_ECHO) == (evt._c_echo_handler, None)
        assert child.get_handlers(evt.EVT_C_ECHO) != (dummy, None)
        assert child.get_handlers(evt.EVT_C_ECHO) == (
            evt._c_echo_handler, None
        )

        assoc.release()

        scp.shutdown()

    def test_abort(self):
        """Test starting with handler bound to EVT_ABORTED."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_ABORTED, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)
        assert scp.get_handlers(evt.EVT_ABORTED) == [(handle, None)]
        assert scp.get_handlers(evt.EVT_ACCEPTED) == []
        assert scp.get_handlers(evt.EVT_ESTABLISHED) == []
        assert scp.get_handlers(evt.EVT_REJECTED) == []
        assert scp.get_handlers(evt.EVT_RELEASED) == []
        assert scp.get_handlers(evt.EVT_REQUESTED) == []

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1

        assert scp.get_handlers(evt.EVT_ABORTED) == [(handle, None)]
        assert scp.get_handlers(evt.EVT_ACCEPTED) == []
        assert scp.get_handlers(evt.EVT_ESTABLISHED) == []
        assert scp.get_handlers(evt.EVT_REJECTED) == []
        assert scp.get_handlers(evt.EVT_RELEASED) == []
        assert scp.get_handlers(evt.EVT_REQUESTED) == []

        assert assoc.get_handlers(evt.EVT_ABORTED) == []
        assert assoc.get_handlers(evt.EVT_ACCEPTED) == []
        assert assoc.get_handlers(evt.EVT_ESTABLISHED) == []
        assert assoc.get_handlers(evt.EVT_REJECTED) == []
        assert assoc.get_handlers(evt.EVT_RELEASED) == []
        assert assoc.get_handlers(evt.EVT_REQUESTED) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_ABORTED) == [(handle, None)]
        assert child.get_handlers(evt.EVT_ACCEPTED) == []
        assert child.get_handlers(evt.EVT_ESTABLISHED) == []
        assert child.get_handlers(evt.EVT_REJECTED) == []
        assert child.get_handlers(evt.EVT_RELEASED) == []
        assert child.get_handlers(evt.EVT_REQUESTED) == []

        assoc.abort()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert event.event.name == 'EVT_ABORTED'

        scp.shutdown()

    def test_abort_bind(self):
        """Test binding a handler to EVT_ABORTED."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_ABORTED, handle)]
        scp = ae.start_server(('', 11112), block=False)
        assert scp.get_handlers(evt.EVT_ABORTED) == []
        assert scp.get_handlers(evt.EVT_ACCEPTED) == []
        assert scp.get_handlers(evt.EVT_ESTABLISHED) == []
        assert scp.get_handlers(evt.EVT_REJECTED) == []
        assert scp.get_handlers(evt.EVT_RELEASED) == []
        assert scp.get_handlers(evt.EVT_REQUESTED) == []

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1

        assert scp.get_handlers(evt.EVT_ABORTED) == []
        assert scp.get_handlers(evt.EVT_ACCEPTED) == []
        assert scp.get_handlers(evt.EVT_ESTABLISHED) == []
        assert scp.get_handlers(evt.EVT_REJECTED) == []
        assert scp.get_handlers(evt.EVT_RELEASED) == []
        assert scp.get_handlers(evt.EVT_REQUESTED) == []

        assert assoc.get_handlers(evt.EVT_ABORTED) == []
        assert assoc.get_handlers(evt.EVT_ACCEPTED) == []
        assert assoc.get_handlers(evt.EVT_ESTABLISHED) == []
        assert assoc.get_handlers(evt.EVT_REJECTED) == []
        assert assoc.get_handlers(evt.EVT_RELEASED) == []
        assert assoc.get_handlers(evt.EVT_REQUESTED) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_ABORTED) == []
        assert child.get_handlers(evt.EVT_ACCEPTED) == []
        assert child.get_handlers(evt.EVT_ESTABLISHED) == []
        assert child.get_handlers(evt.EVT_REJECTED) == []
        assert child.get_handlers(evt.EVT_RELEASED) == []
        assert child.get_handlers(evt.EVT_REQUESTED) == []

        scp.bind(evt.EVT_ABORTED, handle)

        assert scp.get_handlers(evt.EVT_ABORTED) == [(handle, None)]
        assert scp.get_handlers(evt.EVT_ACCEPTED) == []
        assert scp.get_handlers(evt.EVT_ESTABLISHED) == []
        assert scp.get_handlers(evt.EVT_REJECTED) == []
        assert scp.get_handlers(evt.EVT_RELEASED) == []
        assert scp.get_handlers(evt.EVT_REQUESTED) == []

        assert assoc.get_handlers(evt.EVT_ABORTED) == []
        assert assoc.get_handlers(evt.EVT_ACCEPTED) == []
        assert assoc.get_handlers(evt.EVT_ESTABLISHED) == []
        assert assoc.get_handlers(evt.EVT_REJECTED) == []
        assert assoc.get_handlers(evt.EVT_RELEASED) == []
        assert assoc.get_handlers(evt.EVT_REQUESTED) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_ABORTED) == [(handle, None)]
        assert child.get_handlers(evt.EVT_ACCEPTED) == []
        assert child.get_handlers(evt.EVT_ESTABLISHED) == []
        assert child.get_handlers(evt.EVT_REJECTED) == []
        assert child.get_handlers(evt.EVT_RELEASED) == []
        assert child.get_handlers(evt.EVT_REQUESTED) == []

        assoc.abort()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert event.event.name == 'EVT_ABORTED'

        scp.shutdown()

    def test_abort_unbind(self):
        """Test starting with handler bound to EVT_ABORTED."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_ABORTED, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)
        assert scp.get_handlers(evt.EVT_ABORTED) == [(handle, None)]
        assert scp.get_handlers(evt.EVT_ACCEPTED) == []
        assert scp.get_handlers(evt.EVT_ESTABLISHED) == []
        assert scp.get_handlers(evt.EVT_REJECTED) == []
        assert scp.get_handlers(evt.EVT_RELEASED) == []
        assert scp.get_handlers(evt.EVT_RELEASED) == []

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1

        assert scp.get_handlers(evt.EVT_ABORTED) == [(handle, None)]
        assert scp.get_handlers(evt.EVT_ACCEPTED) == []
        assert scp.get_handlers(evt.EVT_ESTABLISHED) == []
        assert scp.get_handlers(evt.EVT_REJECTED) == []
        assert scp.get_handlers(evt.EVT_RELEASED) == []
        assert scp.get_handlers(evt.EVT_REQUESTED) == []

        assert assoc.get_handlers(evt.EVT_ABORTED) == []
        assert assoc.get_handlers(evt.EVT_ACCEPTED) == []
        assert assoc.get_handlers(evt.EVT_ESTABLISHED) == []
        assert assoc.get_handlers(evt.EVT_REJECTED) == []
        assert assoc.get_handlers(evt.EVT_RELEASED) == []
        assert assoc.get_handlers(evt.EVT_REQUESTED) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_ABORTED) == [(handle, None)]
        assert child.get_handlers(evt.EVT_ACCEPTED) == []
        assert child.get_handlers(evt.EVT_ESTABLISHED) == []
        assert child.get_handlers(evt.EVT_REJECTED) == []
        assert child.get_handlers(evt.EVT_RELEASED) == []
        assert child.get_handlers(evt.EVT_REQUESTED) == []

        scp.unbind(evt.EVT_ABORTED, handle)

        assert scp.get_handlers(evt.EVT_ABORTED) == []
        assert scp.get_handlers(evt.EVT_ACCEPTED) == []
        assert scp.get_handlers(evt.EVT_ESTABLISHED) == []
        assert scp.get_handlers(evt.EVT_REJECTED) == []
        assert scp.get_handlers(evt.EVT_RELEASED) == []
        assert scp.get_handlers(evt.EVT_REQUESTED) == []

        assert assoc.get_handlers(evt.EVT_ABORTED) == []
        assert assoc.get_handlers(evt.EVT_ACCEPTED) == []
        assert assoc.get_handlers(evt.EVT_ESTABLISHED) == []
        assert assoc.get_handlers(evt.EVT_REJECTED) == []
        assert assoc.get_handlers(evt.EVT_RELEASED) == []
        assert assoc.get_handlers(evt.EVT_REQUESTED) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_ABORTED) == []
        assert child.get_handlers(evt.EVT_ACCEPTED) == []
        assert child.get_handlers(evt.EVT_ESTABLISHED) == []
        assert child.get_handlers(evt.EVT_REJECTED) == []
        assert child.get_handlers(evt.EVT_RELEASED) == []
        assert child.get_handlers(evt.EVT_REQUESTED) == []

        assoc.abort()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 0

        scp.shutdown()

    def test_abort_local(self):
        """Test the handler bound to EVT_ABORTED with local requested abort."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_ABORTED, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1


        scp.active_associations[0].abort()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert event.event.name == 'EVT_ABORTED'

        scp.shutdown()

    def test_abort_raises(self, caplog):
        """Test the handler for EVT_ACCEPTED raising exception."""
        def handle(event):
            raise NotImplementedError("Exception description")

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_ABORTED, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        with caplog.at_level(logging.ERROR, logger='pynetdicom'):
            assoc = ae.associate('localhost', 11112)
            assert assoc.is_established
            assoc.abort()

            while scp.active_associations:
                time.sleep(0.05)

            scp.shutdown()

            msg = (
                "Exception raised in user's 'evt.EVT_ABORTED' event handler"
                " 'handle'"
            )
            assert msg in caplog.text
            assert "Exception description" in caplog.text

    def test_accept(self):
        """Test starting with handler bound to EVT_ACCEPTED."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_ACCEPTED, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)
        assert scp.get_handlers(evt.EVT_ABORTED) == []
        assert scp.get_handlers(evt.EVT_ACCEPTED) == [(handle, None)]
        assert scp.get_handlers(evt.EVT_ESTABLISHED) == []
        assert scp.get_handlers(evt.EVT_REJECTED) == []
        assert scp.get_handlers(evt.EVT_RELEASED) == []
        assert scp.get_handlers(evt.EVT_REQUESTED) == []

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1

        assert scp.get_handlers(evt.EVT_ABORTED) == []
        assert scp.get_handlers(evt.EVT_ACCEPTED) == [(handle, None)]
        assert scp.get_handlers(evt.EVT_ESTABLISHED) == []
        assert scp.get_handlers(evt.EVT_REJECTED) == []
        assert scp.get_handlers(evt.EVT_RELEASED) == []
        assert scp.get_handlers(evt.EVT_REQUESTED) == []

        assert assoc.get_handlers(evt.EVT_ABORTED) == []
        assert assoc.get_handlers(evt.EVT_ACCEPTED) == []
        assert assoc.get_handlers(evt.EVT_ESTABLISHED) == []
        assert assoc.get_handlers(evt.EVT_REJECTED) == []
        assert assoc.get_handlers(evt.EVT_RELEASED) == []
        assert assoc.get_handlers(evt.EVT_REQUESTED) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_ABORTED) == []
        assert child.get_handlers(evt.EVT_ACCEPTED) == [(handle, None)]
        assert child.get_handlers(evt.EVT_ESTABLISHED) == []
        assert child.get_handlers(evt.EVT_REJECTED) == []
        assert child.get_handlers(evt.EVT_RELEASED) == []
        assert child.get_handlers(evt.EVT_REQUESTED) == []

        assoc.abort()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert event.event.name == 'EVT_ACCEPTED'

        scp.shutdown()

    def test_accept_bind(self):
        """Test binding a handler to EVT_ACCEPTED."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_ACCEPTED, handle)]
        scp = ae.start_server(('', 11112), block=False)
        assert scp.get_handlers(evt.EVT_ACCEPTED) == []

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_ACCEPTED) == []
        assert assoc.get_handlers(evt.EVT_ACCEPTED) == []
        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_ACCEPTED) == []

        assert len(triggered) == 0

        scp.bind(evt.EVT_ACCEPTED, handle)

        assert scp.get_handlers(evt.EVT_ACCEPTED) == [(handle, None)]
        assert assoc.get_handlers(evt.EVT_ACCEPTED) == []
        assert child.get_handlers(evt.EVT_ACCEPTED) == [(handle, None)]

        assoc2 = ae.associate('localhost', 11112)

        assoc.release()
        assoc2.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        assert triggered[0].event.name == 'EVT_ACCEPTED'

        scp.shutdown()

    def test_accept_unbind(self):
        """Test starting with handler bound to EVT_ACCEPTED."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_ACCEPTED, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)
        assert scp.get_handlers(evt.EVT_ACCEPTED) == [(handle, None)]

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1

        assert scp.get_handlers(evt.EVT_ACCEPTED) == [(handle, None)]
        assert assoc.get_handlers(evt.EVT_ACCEPTED) == []
        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_ACCEPTED) == [(handle, None)]

        assert len(triggered) == 1
        assert triggered[0].event.name == "EVT_ACCEPTED"

        scp.unbind(evt.EVT_ACCEPTED, handle)

        assert scp.get_handlers(evt.EVT_ACCEPTED) == []
        assert assoc.get_handlers(evt.EVT_ACCEPTED) == []
        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_ACCEPTED) == []

        assoc2 = ae.associate('localhost', 11112)

        assoc.release()
        assoc2.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1

        scp.shutdown()

    def test_accept_raises(self, caplog):
        """Test the handler for EVT_ACCEPTED raising exception."""
        def handle(event):
            raise NotImplementedError("Exception description")

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_ACCEPTED, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        with caplog.at_level(logging.ERROR, logger='pynetdicom'):
            assoc = ae.associate('localhost', 11112)
            assert assoc.is_established
            assoc.abort()

            while scp.active_associations:
                time.sleep(0.05)

            scp.shutdown()

            msg = (
                "Exception raised in user's 'evt.EVT_ACCEPTED' event handler"
                " 'handle'"
            )
            assert msg in caplog.text
            assert "Exception description" in caplog.text

    def test_release(self):
        """Test starting with handler bound to EVT_RELEASED."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_RELEASED, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)
        assert scp.get_handlers(evt.EVT_ABORTED) == []
        assert scp.get_handlers(evt.EVT_ACCEPTED) == []
        assert scp.get_handlers(evt.EVT_ESTABLISHED) == []
        assert scp.get_handlers(evt.EVT_REJECTED) == []
        assert scp.get_handlers(evt.EVT_RELEASED) == [(handle, None)]
        assert scp.get_handlers(evt.EVT_REQUESTED) == []

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1

        assert scp.get_handlers(evt.EVT_ABORTED) == []
        assert scp.get_handlers(evt.EVT_ACCEPTED) == []
        assert scp.get_handlers(evt.EVT_ESTABLISHED) == []
        assert scp.get_handlers(evt.EVT_REJECTED) == []
        assert scp.get_handlers(evt.EVT_RELEASED) == [(handle, None)]
        assert scp.get_handlers(evt.EVT_REQUESTED) == []

        assert assoc.get_handlers(evt.EVT_ABORTED) == []
        assert assoc.get_handlers(evt.EVT_ACCEPTED) == []
        assert assoc.get_handlers(evt.EVT_ESTABLISHED) == []
        assert assoc.get_handlers(evt.EVT_REJECTED) == []
        assert assoc.get_handlers(evt.EVT_RELEASED) == []
        assert assoc.get_handlers(evt.EVT_REQUESTED) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_ABORTED) == []
        assert child.get_handlers(evt.EVT_ACCEPTED) == []
        assert child.get_handlers(evt.EVT_ESTABLISHED) == []
        assert child.get_handlers(evt.EVT_REJECTED) == []
        assert child.get_handlers(evt.EVT_RELEASED) == [(handle, None)]
        assert child.get_handlers(evt.EVT_REQUESTED) == []

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert event.event.name == 'EVT_RELEASED'

        scp.shutdown()

    def test_release_bind(self):
        """Test binding a handler to EVT_RELEASED."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_RELEASED, handle)]
        scp = ae.start_server(('', 11112), block=False)
        assert scp.get_handlers(evt.EVT_RELEASED) == []

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1

        assert scp.get_handlers(evt.EVT_RELEASED) == []
        assert assoc.get_handlers(evt.EVT_RELEASED) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_RELEASED) == []

        scp.bind(evt.EVT_RELEASED, handle)

        assert scp.get_handlers(evt.EVT_RELEASED) == [(handle, None)]
        assert assoc.get_handlers(evt.EVT_RELEASED) == []
        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_RELEASED) == [(handle, None)]

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert event.event.name == 'EVT_RELEASED'

        scp.shutdown()

    def test_release_unbind(self):
        """Test starting with handler bound to EVT_ABORTED."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_RELEASED, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1

        scp.unbind(evt.EVT_RELEASED, handle)

        assert scp.get_handlers(evt.EVT_RELEASED) == []
        assert assoc.get_handlers(evt.EVT_RELEASED) == []
        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_RELEASED) == []

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 0

        scp.shutdown()

    def test_release_local(self):
        """Test the handler bound to EVT_RELEASED with local requested abort."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_RELEASED, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1


        scp.active_associations[0].release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert event.event.name == 'EVT_RELEASED'

        scp.shutdown()

    def test_release_raises(self, caplog):
        """Test the handler for EVT_RELEASED raising exception."""
        def handle(event):
            raise NotImplementedError("Exception description")

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_RELEASED, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        with caplog.at_level(logging.ERROR, logger='pynetdicom'):
            assoc = ae.associate('localhost', 11112)
            assert assoc.is_established
            assoc.release()

            while scp.active_associations:
                time.sleep(0.05)

            scp.shutdown()

            msg = (
                "Exception raised in user's 'evt.EVT_RELEASED' event handler"
                " 'handle'"
            )
            assert msg in caplog.text
            assert "Exception description" in caplog.text

    def test_established(self):
        """Test starting with handler bound to EVT_ESTABLISHED."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_ESTABLISHED, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)
        assert scp.get_handlers(evt.EVT_ABORTED) == []
        assert scp.get_handlers(evt.EVT_ACCEPTED) == []
        assert scp.get_handlers(evt.EVT_ESTABLISHED) == [(handle, None)]
        assert scp.get_handlers(evt.EVT_REJECTED) == []
        assert scp.get_handlers(evt.EVT_RELEASED) == []
        assert scp.get_handlers(evt.EVT_REQUESTED) == []

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1

        assert scp.get_handlers(evt.EVT_ABORTED) == []
        assert scp.get_handlers(evt.EVT_ACCEPTED) == []
        assert scp.get_handlers(evt.EVT_ESTABLISHED) == [(handle, None)]
        assert scp.get_handlers(evt.EVT_REJECTED) == []
        assert scp.get_handlers(evt.EVT_RELEASED) == []
        assert scp.get_handlers(evt.EVT_REQUESTED) == []

        assert assoc.get_handlers(evt.EVT_ABORTED) == []
        assert assoc.get_handlers(evt.EVT_ACCEPTED) == []
        assert assoc.get_handlers(evt.EVT_ESTABLISHED) == []
        assert assoc.get_handlers(evt.EVT_REJECTED) == []
        assert assoc.get_handlers(evt.EVT_ESTABLISHED) == []
        assert assoc.get_handlers(evt.EVT_REQUESTED) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_ABORTED) == []
        assert child.get_handlers(evt.EVT_ACCEPTED) == []
        assert child.get_handlers(evt.EVT_ESTABLISHED) == [(handle, None)]
        assert child.get_handlers(evt.EVT_REJECTED) == []
        assert child.get_handlers(evt.EVT_RELEASED) == []
        assert child.get_handlers(evt.EVT_REQUESTED) == []

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert event.event.name == 'EVT_ESTABLISHED'

        scp.shutdown()

    def test_established_bind(self):
        """Test binding a handler to EVT_ESTABLISHED."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_ESTABLISHED, handle)]
        scp = ae.start_server(('', 11112), block=False)
        assert scp.get_handlers(evt.EVT_ESTABLISHED) == []

        scp.bind(evt.EVT_ESTABLISHED, handle)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1

        assert scp.get_handlers(evt.EVT_ESTABLISHED) == [(handle, None)]
        assert assoc.get_handlers(evt.EVT_ESTABLISHED) == []
        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_ESTABLISHED) == [(handle, None)]

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert event.event.name == 'EVT_ESTABLISHED'

        scp.shutdown()

    def test_established_unbind(self):
        """Test starting with handler bound to EVT_ABORTED."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_ESTABLISHED, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        scp.unbind(evt.EVT_ESTABLISHED, handle)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1

        assert scp.get_handlers(evt.EVT_ESTABLISHED) == []
        assert assoc.get_handlers(evt.EVT_ESTABLISHED) == []
        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_ESTABLISHED) == []

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 0

        scp.shutdown()

    def test_established_raises(self, caplog):
        """Test the handler for EVT_ESTABLISHED raising exception."""
        def handle(event):
            raise NotImplementedError("Exception description")

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_ESTABLISHED, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        with caplog.at_level(logging.ERROR, logger='pynetdicom'):
            assoc = ae.associate('localhost', 11112)
            assert assoc.is_established
            assoc.release()

            while scp.active_associations:
                time.sleep(0.05)

            scp.shutdown()

            msg = (
                "Exception raised in user's 'evt.EVT_ESTABLISHED' event handler"
                " 'handle'"
            )
            assert msg in caplog.text
            assert "Exception description" in caplog.text

    def test_requested(self):
        """Test starting with handler bound to EVT_REQUESTED."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_REQUESTED, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)
        assert scp.get_handlers(evt.EVT_ABORTED) == []
        assert scp.get_handlers(evt.EVT_ACCEPTED) == []
        assert scp.get_handlers(evt.EVT_ESTABLISHED) == []
        assert scp.get_handlers(evt.EVT_REJECTED) == []
        assert scp.get_handlers(evt.EVT_RELEASED) == []
        assert scp.get_handlers(evt.EVT_REQUESTED) == [(handle, None)]

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1

        assert scp.get_handlers(evt.EVT_ABORTED) == []
        assert scp.get_handlers(evt.EVT_ACCEPTED) == []
        assert scp.get_handlers(evt.EVT_ESTABLISHED) == []
        assert scp.get_handlers(evt.EVT_REJECTED) == []
        assert scp.get_handlers(evt.EVT_RELEASED) == []
        assert scp.get_handlers(evt.EVT_REQUESTED) == [(handle, None)]

        assert assoc.get_handlers(evt.EVT_ABORTED) == []
        assert assoc.get_handlers(evt.EVT_ACCEPTED) == []
        assert assoc.get_handlers(evt.EVT_REQUESTED) == []
        assert assoc.get_handlers(evt.EVT_REJECTED) == []
        assert assoc.get_handlers(evt.EVT_REQUESTED) == []
        assert assoc.get_handlers(evt.EVT_REQUESTED) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_ABORTED) == []
        assert child.get_handlers(evt.EVT_ACCEPTED) == []
        assert child.get_handlers(evt.EVT_ESTABLISHED) == []
        assert child.get_handlers(evt.EVT_REJECTED) == []
        assert child.get_handlers(evt.EVT_RELEASED) == []
        assert child.get_handlers(evt.EVT_REQUESTED) == [(handle, None)]

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert event.event.name == 'EVT_REQUESTED'

        scp.shutdown()

    def test_requested_bind(self):
        """Test binding a handler to EVT_REQUESTED."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_REQUESTED, handle)]
        scp = ae.start_server(('', 11112), block=False)
        assert scp.get_handlers(evt.EVT_REQUESTED) == []

        scp.bind(evt.EVT_REQUESTED, handle)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1

        assert scp.get_handlers(evt.EVT_REQUESTED) == [(handle, None)]
        assert assoc.get_handlers(evt.EVT_REQUESTED) == []
        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_REQUESTED) == [(handle, None)]

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert event.event.name == 'EVT_REQUESTED'

        scp.shutdown()

    def test_requested_unbind(self):
        """Test starting with handler bound to EVT_ABORTED."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_REQUESTED, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        scp.unbind(evt.EVT_REQUESTED, handle)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1

        assert scp.get_handlers(evt.EVT_REQUESTED) == []
        assert assoc.get_handlers(evt.EVT_REQUESTED) == []
        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_REQUESTED) == []

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 0

        scp.shutdown()

    def test_requested_raises(self, caplog):
        """Test the handler for EVT_REQUESTED raising exception."""
        def handle(event):
            raise NotImplementedError("Exception description")

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_REQUESTED, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        with caplog.at_level(logging.ERROR, logger='pynetdicom'):
            assoc = ae.associate('localhost', 11112)
            assert assoc.is_established
            assoc.release()

            while scp.active_associations:
                time.sleep(0.05)

            scp.shutdown()

            msg = (
                "Exception raised in user's 'evt.EVT_REQUESTED' event handler"
                " 'handle'"
            )
            assert msg in caplog.text
            assert "Exception description" in caplog.text

    def test_rejected(self):
        """Test starting with handler bound to EVT_REJECTED."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.require_called_aet = True
        ae.add_supported_context(CTImageStorage)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_REJECTED, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)
        assert scp.get_handlers(evt.EVT_ABORTED) == []
        assert scp.get_handlers(evt.EVT_ACCEPTED) == []
        assert scp.get_handlers(evt.EVT_ESTABLISHED) == []
        assert scp.get_handlers(evt.EVT_REJECTED) == [(handle, None)]
        assert scp.get_handlers(evt.EVT_RELEASED) == []
        assert scp.get_handlers(evt.EVT_REQUESTED) == []

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_rejected

        assert scp.get_handlers(evt.EVT_ABORTED) == []
        assert scp.get_handlers(evt.EVT_ACCEPTED) == []
        assert scp.get_handlers(evt.EVT_ESTABLISHED) == []
        assert scp.get_handlers(evt.EVT_REJECTED) == [(handle, None)]
        assert scp.get_handlers(evt.EVT_RELEASED) == []
        assert scp.get_handlers(evt.EVT_REQUESTED) == []

        assert assoc.get_handlers(evt.EVT_ABORTED) == []
        assert assoc.get_handlers(evt.EVT_ACCEPTED) == []
        assert assoc.get_handlers(evt.EVT_REJECTED) == []
        assert assoc.get_handlers(evt.EVT_REJECTED) == []
        assert assoc.get_handlers(evt.EVT_REJECTED) == []
        assert assoc.get_handlers(evt.EVT_REQUESTED) == []

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert event.event.name == 'EVT_REJECTED'

        scp.shutdown()

    def test_rejected_bind(self):
        """Test binding a handler to EVT_REJECTED."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.require_called_aet = True
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_REJECTED, handle)]
        scp = ae.start_server(('', 11112), block=False)
        assert scp.get_handlers(evt.EVT_REJECTED) == []

        scp.bind(evt.EVT_REJECTED, handle)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_rejected

        assert scp.get_handlers(evt.EVT_REJECTED) == [(handle, None)]
        assert assoc.get_handlers(evt.EVT_REJECTED) == []

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert event.event.name == 'EVT_REJECTED'

        scp.shutdown()

    def test_rejected_unbind(self):
        """Test starting with handler bound to EVT_ABORTED."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.require_called_aet = True
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_REJECTED, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        scp.unbind(evt.EVT_REJECTED, handle)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_rejected

        assert scp.get_handlers(evt.EVT_REJECTED) == []
        assert assoc.get_handlers(evt.EVT_REJECTED) == []

        assoc.release()

        assert len(triggered) == 0

        scp.shutdown()

    def test_rejected_raises(self, caplog):
        """Test the handler for EVT_REJECTED raising exception."""
        def handle(event):
            raise NotImplementedError("Exception description")

        self.ae = ae = AE()
        ae.require_called_aet = True
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_REJECTED, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        with caplog.at_level(logging.ERROR, logger='pynetdicom'):
            assoc = ae.associate('localhost', 11112)
            assert assoc.is_rejected
            scp.shutdown()

            msg = (
                "Exception raised in user's 'evt.EVT_REJECTED' event handler"
                " 'handle'"
            )
            assert msg in caplog.text
            assert "Exception description" in caplog.text

    def test_optional_args(self):
        """Test passing optional arguments to the handler."""
        arguments = []
        def handle(event, *args):
            arguments.append(args)

        args = ['a', 1, {'test': 1}]

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_ACCEPTED, handle, args)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_ACCEPTED) == [(handle, args)]
        assert assoc.get_handlers(evt.EVT_ESTABLISHED) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_ACCEPTED) == [(handle, args)]

        assoc.abort()

        while scp.active_associations:
            time.sleep(0.05)

        scp.shutdown()

        assert len(arguments) == 1
        assert args == list(arguments[0])

    def test_optional_args_intervention(self):
        """Test passing optional arguments to the handler."""
        arguments = []
        def handle_echo(event, *args):
            arguments.append(args)
            return 0x0000

        args = ['a', 1, {'test': 1}]

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_C_ECHO, handle_echo, args)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_C_ECHO) == (handle_echo, args)

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_C_ECHO) == (handle_echo, args)

        status = assoc.send_c_echo()
        assert status.Status == 0x0000

        assoc.abort()

        while scp.active_associations:
            time.sleep(0.05)

        scp.shutdown()

        assert len(arguments) == 1
        assert args == list(arguments[0])


class TestEventHandlingRequestor(object):
    """Test the transport events and handling as acceptor."""
    def setup(self):
        self.ae = None
        _config.LOG_HANDLER_LEVEL = 'none'

    def teardown(self):
        if self.ae:
            self.ae.shutdown()

        _config.LOG_HANDLER_LEVEL = 'standard'

    def test_no_handlers(self):
        """Test with no association event handlers bound."""
        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)
        assert scp.get_handlers(evt.EVT_ABORTED) == []
        assert scp.get_handlers(evt.EVT_ACCEPTED) == []
        assert scp.get_handlers(evt.EVT_ESTABLISHED) == []
        assert scp.get_handlers(evt.EVT_REJECTED) == []
        assert scp.get_handlers(evt.EVT_RELEASED) == []
        assert scp.get_handlers(evt.EVT_REQUESTED) == []
        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established
        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_ABORTED) == []
        assert scp.get_handlers(evt.EVT_ACCEPTED) == []
        assert scp.get_handlers(evt.EVT_ESTABLISHED) == []
        assert scp.get_handlers(evt.EVT_REJECTED) == []
        assert scp.get_handlers(evt.EVT_RELEASED) == []
        assert scp.get_handlers(evt.EVT_REQUESTED) == []

        assert assoc.get_handlers(evt.EVT_ABORTED) == []
        assert assoc.get_handlers(evt.EVT_ACCEPTED) == []
        assert assoc.get_handlers(evt.EVT_ESTABLISHED) == []
        assert assoc.get_handlers(evt.EVT_REJECTED) == []
        assert assoc.get_handlers(evt.EVT_RELEASED) == []
        assert assoc.get_handlers(evt.EVT_REQUESTED) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_ABORTED) == []
        assert child.get_handlers(evt.EVT_ACCEPTED) == []
        assert child.get_handlers(evt.EVT_ESTABLISHED) == []
        assert child.get_handlers(evt.EVT_REJECTED) == []
        assert child.get_handlers(evt.EVT_RELEASED) == []
        assert child.get_handlers(evt.EVT_REQUESTED) == []

        assoc.release()
        scp.shutdown()

    def test_unbind_not_event(self):
        """Test unbind a handler if no events bound."""
        def dummy(event):
            pass

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)

        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established
        assert len(scp.active_associations) == 1

        assert assoc.get_handlers(evt.EVT_DIMSE_SENT) == []
        assoc.unbind(evt.EVT_DIMSE_SENT, dummy)
        assert assoc.get_handlers(evt.EVT_DIMSE_SENT) == []

        assoc.release()

        scp.shutdown()

    def test_unbind_notification_none(self):
        """Test unbinding a handler thats not bound."""
        def dummy(event):
            pass

        def dummy2(event):
            pass

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)

        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established
        assert len(scp.active_associations) == 1

        assoc.bind(evt.EVT_DIMSE_SENT, dummy)

        assert assoc.get_handlers(evt.EVT_DIMSE_SENT) == [(dummy, None)]
        assoc.unbind(evt.EVT_DIMSE_SENT, dummy2)
        assert assoc.get_handlers(evt.EVT_DIMSE_SENT) == [(dummy, None)]

        assoc.release()

        scp.shutdown()

    def test_unbind_intervention(self):
        """Test unbinding a user intervention handler."""
        def dummy(event):
            pass

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)

        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established
        assert len(scp.active_associations) == 1

        assoc.bind(evt.EVT_C_ECHO, dummy)
        assert assoc.get_handlers(evt.EVT_C_ECHO) == (dummy, None)
        assoc.unbind(evt.EVT_C_ECHO, dummy)
        assert assoc.get_handlers(evt.EVT_C_ECHO) != (dummy, None)
        assert assoc.get_handlers(evt.EVT_C_ECHO) == (
            evt._c_echo_handler, None
        )

        assoc.release()

        scp.shutdown()

    def test_abort(self):
        """Test starting with handler bound to EVT_ABORTED."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_ABORTED, handle)]
        scp = ae.start_server(('', 11112), block=False)
        assoc = ae.associate('localhost', 11112, evt_handlers=handlers)
        assert assoc.is_established
        assert len(scp.active_associations) == 1

        assert assoc.get_handlers(evt.EVT_ABORTED) == [(handle, None)]
        assert assoc.get_handlers(evt.EVT_ACCEPTED) == []
        assert assoc.get_handlers(evt.EVT_ESTABLISHED) == []
        assert assoc.get_handlers(evt.EVT_REJECTED) == []
        assert assoc.get_handlers(evt.EVT_RELEASED) == []
        assert assoc.get_handlers(evt.EVT_REQUESTED) == []

        assoc.abort()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert event.event.name == 'EVT_ABORTED'

        scp.shutdown()

    def test_abort_bind(self):
        """Test binding a handler to EVT_ABORTED."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_ABORTED, handle)]
        scp = ae.start_server(('', 11112), block=False)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1

        assert assoc.get_handlers(evt.EVT_ABORTED) == []
        assert assoc.get_handlers(evt.EVT_ACCEPTED) == []
        assert assoc.get_handlers(evt.EVT_ESTABLISHED) == []
        assert assoc.get_handlers(evt.EVT_REJECTED) == []
        assert assoc.get_handlers(evt.EVT_RELEASED) == []
        assert assoc.get_handlers(evt.EVT_REQUESTED) == []

        assoc.bind(evt.EVT_ABORTED, handle)

        assert assoc.get_handlers(evt.EVT_ABORTED) == [(handle, None)]
        assert assoc.get_handlers(evt.EVT_ACCEPTED) == []
        assert assoc.get_handlers(evt.EVT_ESTABLISHED) == []
        assert assoc.get_handlers(evt.EVT_REJECTED) == []
        assert assoc.get_handlers(evt.EVT_RELEASED) == []
        assert assoc.get_handlers(evt.EVT_REQUESTED) == []

        assoc.abort()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert event.event.name == 'EVT_ABORTED'

        scp.shutdown()

    def test_abort_unbind(self):
        """Test starting with handler bound to EVT_ABORTED."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_ABORTED, handle)]
        scp = ae.start_server(('', 11112), block=False)

        assoc = ae.associate('localhost', 11112, evt_handlers=handlers)
        assert assoc.is_established
        assert len(scp.active_associations) == 1

        assert assoc.get_handlers(evt.EVT_ABORTED) == [(handle, None)]
        assert assoc.get_handlers(evt.EVT_ACCEPTED) == []
        assert assoc.get_handlers(evt.EVT_ESTABLISHED) == []
        assert assoc.get_handlers(evt.EVT_REJECTED) == []
        assert assoc.get_handlers(evt.EVT_RELEASED) == []
        assert assoc.get_handlers(evt.EVT_REQUESTED) == []

        assoc.unbind(evt.EVT_ABORTED, handle)

        assert assoc.get_handlers(evt.EVT_ABORTED) == []
        assert assoc.get_handlers(evt.EVT_ACCEPTED) == []
        assert assoc.get_handlers(evt.EVT_ESTABLISHED) == []
        assert assoc.get_handlers(evt.EVT_REJECTED) == []
        assert assoc.get_handlers(evt.EVT_RELEASED) == []
        assert assoc.get_handlers(evt.EVT_REQUESTED) == []

        assoc.abort()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 0

        scp.shutdown()

    def test_abort_remote(self):
        """Test the handler bound to EVT_ABORTED with local requested abort."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_ABORTED, handle)]
        scp = ae.start_server(('', 11112), block=False)

        assoc = ae.associate('localhost', 11112, evt_handlers=handlers)
        assert assoc.is_established
        assert len(scp.active_associations) == 1

        scp.active_associations[0].abort()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert event.event.name == 'EVT_ABORTED'

        scp.shutdown()

    def test_abort_raises(self, caplog):
        """Test the handler for EVT_ACCEPTED raising exception."""
        def handle(event):
            raise NotImplementedError("Exception description")

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_ABORTED, handle)]
        scp = ae.start_server(('', 11112), block=False)

        with caplog.at_level(logging.ERROR, logger='pynetdicom'):
            assoc = ae.associate('localhost', 11112, evt_handlers=handlers)
            assert assoc.is_established
            assoc.abort()

            while scp.active_associations:
                time.sleep(0.05)

            scp.shutdown()

            msg = (
                "Exception raised in user's 'evt.EVT_ABORTED' event handler"
                " 'handle'"
            )
            assert msg in caplog.text
            assert "Exception description" in caplog.text

    def test_accept(self):
        """Test starting with handler bound to EVT_ACCEPTED."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_ACCEPTED, handle)]
        scp = ae.start_server(('', 11112), block=False)

        assoc = ae.associate('localhost', 11112, evt_handlers=handlers)
        assert assoc.is_established
        assert len(scp.active_associations) == 1

        assert assoc.get_handlers(evt.EVT_ABORTED) == []
        assert assoc.get_handlers(evt.EVT_ACCEPTED) == [(handle, None)]
        assert assoc.get_handlers(evt.EVT_ESTABLISHED) == []
        assert assoc.get_handlers(evt.EVT_REJECTED) == []
        assert assoc.get_handlers(evt.EVT_RELEASED) == []
        assert assoc.get_handlers(evt.EVT_REQUESTED) == []

        assoc.abort()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert event.event.name == 'EVT_ACCEPTED'

        scp.shutdown()

    def test_accept_raises(self, caplog):
        """Test the handler for EVT_ACCEPTED raising exception."""
        def handle(event):
            raise NotImplementedError("Exception description")

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_ACCEPTED, handle)]
        scp = ae.start_server(('', 11112), block=False)

        with caplog.at_level(logging.ERROR, logger='pynetdicom'):
            assoc = ae.associate('localhost', 11112, evt_handlers=handlers)
            assert assoc.is_established
            assoc.abort()

            while scp.active_associations:
                time.sleep(0.05)

            scp.shutdown()

            msg = (
                "Exception raised in user's 'evt.EVT_ACCEPTED' event handler"
                " 'handle'"
            )
            assert msg in caplog.text
            assert "Exception description" in caplog.text

    def test_release(self):
        """Test starting with handler bound to EVT_RELEASED."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_RELEASED, handle)]
        scp = ae.start_server(('', 11112), block=False)

        assoc = ae.associate('localhost', 11112, evt_handlers=handlers)
        assert assoc.is_established
        assert len(scp.active_associations) == 1

        assert assoc.get_handlers(evt.EVT_ABORTED) == []
        assert assoc.get_handlers(evt.EVT_ACCEPTED) == []
        assert assoc.get_handlers(evt.EVT_ESTABLISHED) == []
        assert assoc.get_handlers(evt.EVT_REJECTED) == []
        assert assoc.get_handlers(evt.EVT_RELEASED) == [(handle, None)]
        assert assoc.get_handlers(evt.EVT_REQUESTED) == []

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert event.event.name == 'EVT_RELEASED'

        scp.shutdown()

    def test_release_bind(self):
        """Test binding a handler to EVT_RELEASED."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_RELEASED, handle)]
        scp = ae.start_server(('', 11112), block=False)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1
        assert assoc.get_handlers(evt.EVT_RELEASED) == []

        assoc.bind(evt.EVT_RELEASED, handle)
        assert assoc.get_handlers(evt.EVT_RELEASED) == [(handle, None)]

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert event.event.name == 'EVT_RELEASED'

        scp.shutdown()

    def test_release_unbind(self):
        """Test starting with handler bound to EVT_ABORTED."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_RELEASED, handle)]
        scp = ae.start_server(('', 11112), block=False)

        assoc = ae.associate('localhost', 11112, evt_handlers=handlers)
        assert assoc.is_established
        assert len(scp.active_associations) == 1

        assert assoc.get_handlers(evt.EVT_RELEASED) == [(handle, None)]

        assoc.unbind(evt.EVT_RELEASED, handle)

        assert assoc.get_handlers(evt.EVT_RELEASED) == []

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 0

        scp.shutdown()

    def test_release_remote(self):
        """Test the handler bound to EVT_RELEASED with local requested abort."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_RELEASED, handle)]
        scp = ae.start_server(('', 11112), block=False)

        assoc = ae.associate('localhost', 11112, evt_handlers=handlers)
        assert assoc.is_established
        assert len(scp.active_associations) == 1

        scp.active_associations[0].release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert event.event.name == 'EVT_RELEASED'

        scp.shutdown()

    def test_release_raises(self, caplog):
        """Test the handler for EVT_RELEASED raising exception."""
        def handle(event):
            raise NotImplementedError("Exception description")

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_RELEASED, handle)]
        scp = ae.start_server(('', 11112), block=False)

        with caplog.at_level(logging.ERROR, logger='pynetdicom'):
            assoc = ae.associate('localhost', 11112, evt_handlers=handlers)
            assert assoc.is_established
            assoc.release()

            while scp.active_associations:
                time.sleep(0.05)

            scp.shutdown()

            msg = (
                "Exception raised in user's 'evt.EVT_RELEASED' event handler"
                " 'handle'"
            )
            assert msg in caplog.text
            assert "Exception description" in caplog.text

    def test_established(self):
        """Test starting with handler bound to EVT_ESTABLISHED."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_ESTABLISHED, handle)]
        scp = ae.start_server(('', 11112), block=False)

        assoc = ae.associate('localhost', 11112, evt_handlers=handlers)
        assert assoc.is_established
        assert len(scp.active_associations) == 1

        assert assoc.get_handlers(evt.EVT_ABORTED) == []
        assert assoc.get_handlers(evt.EVT_ACCEPTED) == []
        assert assoc.get_handlers(evt.EVT_ESTABLISHED) == [(handle, None)]
        assert assoc.get_handlers(evt.EVT_REJECTED) == []
        assert assoc.get_handlers(evt.EVT_RELEASED) == []
        assert assoc.get_handlers(evt.EVT_REQUESTED) == []

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert event.event.name == 'EVT_ESTABLISHED'

        scp.shutdown()

    def test_established_raises(self, caplog):
        """Test the handler for EVT_ESTABLISHED raising exception."""
        def handle(event):
            raise NotImplementedError("Exception description")

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_ESTABLISHED, handle)]
        scp = ae.start_server(('', 11112), block=False)

        with caplog.at_level(logging.ERROR, logger='pynetdicom'):
            assoc = ae.associate('localhost', 11112, evt_handlers=handlers)
            assert assoc.is_established
            assoc.release()

            while scp.active_associations:
                time.sleep(0.05)

            scp.shutdown()

            msg = (
                "Exception raised in user's 'evt.EVT_ESTABLISHED' event handler"
                " 'handle'"
            )
            assert msg in caplog.text
            assert "Exception description" in caplog.text

    def test_requested(self):
        """Test starting with handler bound to EVT_REQUESTED."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_REQUESTED, handle)]
        scp = ae.start_server(('', 11112), block=False)

        assoc = ae.associate('localhost', 11112, evt_handlers=handlers)
        assert assoc.is_established
        assert len(scp.active_associations) == 1
        assert assoc.get_handlers(evt.EVT_ABORTED) == []
        assert assoc.get_handlers(evt.EVT_ACCEPTED) == []
        assert assoc.get_handlers(evt.EVT_ESTABLISHED) == []
        assert assoc.get_handlers(evt.EVT_REJECTED) == []
        assert assoc.get_handlers(evt.EVT_RELEASED) == []
        assert assoc.get_handlers(evt.EVT_REQUESTED) == [(handle, None)]

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert event.event.name == 'EVT_REQUESTED'

        scp.shutdown()

    def test_requested_raises(self, caplog):
        """Test the handler for EVT_REQUESTED raising exception."""
        def handle(event):
            raise NotImplementedError("Exception description")

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_REQUESTED, handle)]
        scp = ae.start_server(('', 11112), block=False)

        with caplog.at_level(logging.ERROR, logger='pynetdicom'):
            assoc = ae.associate('localhost', 11112, evt_handlers=handlers)
            assert assoc.is_established
            assoc.release()

            while scp.active_associations:
                time.sleep(0.05)

            scp.shutdown()

            msg = (
                "Exception raised in user's 'evt.EVT_REQUESTED' event handler"
                " 'handle'"
            )
            assert msg in caplog.text
            assert "Exception description" in caplog.text

    def test_rejected(self):
        """Test starting with handler bound to EVT_REJECTED."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.require_called_aet = True
        ae.add_supported_context(CTImageStorage)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_REJECTED, handle)]
        scp = ae.start_server(('', 11112), block=False)

        assoc = ae.associate('localhost', 11112, evt_handlers=handlers)
        assert assoc.is_rejected

        assert assoc.get_handlers(evt.EVT_ABORTED) == []
        assert assoc.get_handlers(evt.EVT_ACCEPTED) == []
        assert assoc.get_handlers(evt.EVT_ESTABLISHED) == []
        assert assoc.get_handlers(evt.EVT_REJECTED) == [(handle, None)]
        assert assoc.get_handlers(evt.EVT_RELEASED) == []
        assert assoc.get_handlers(evt.EVT_REQUESTED) == []

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert event.event.name == 'EVT_REJECTED'

        scp.shutdown()

    def test_rejected_raises(self, caplog):
        """Test the handler for EVT_REJECTED raising exception."""
        def handle(event):
            raise NotImplementedError("Exception description")

        self.ae = ae = AE()
        ae.require_called_aet = True
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_REJECTED, handle)]
        scp = ae.start_server(('', 11112), block=False)

        with caplog.at_level(logging.ERROR, logger='pynetdicom'):
            assoc = ae.associate('localhost', 11112, evt_handlers=handlers)
            assert assoc.is_rejected
            scp.shutdown()

            msg = (
                "Exception raised in user's 'evt.EVT_REJECTED' event handler"
                " 'handle'"
            )
            assert msg in caplog.text
            assert "Exception description" in caplog.text

    def test_optional_args(self):
        """Test passing optional arguments to the handler."""
        arguments = []
        def handle(event, *args):
            arguments.append(args)

        args = ['a', 1, {'test': 1}]

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_ACCEPTED, handle, args)]
        scp = ae.start_server(('', 11112), block=False)

        assoc = ae.associate('localhost', 11112, evt_handlers=handlers)
        assert assoc.is_established
        assert len(scp.active_associations) == 1
        assert assoc.get_handlers(evt.EVT_ACCEPTED) == [(handle, args)]

        assoc.abort()

        while scp.active_associations:
            time.sleep(0.05)

        scp.shutdown()

        assert len(arguments) == 1
        assert args == list(arguments[0])
