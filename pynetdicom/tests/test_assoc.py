"""Association testing"""

from copy import deepcopy
from io import BytesIO
import logging
import os
import select
import socket
from struct import pack
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
)

from pynetdicom import AE, VerificationPresentationContexts, build_context
from pynetdicom.association import Association
from pynetdicom.dimse_primitives import C_STORE, C_FIND, C_GET, C_MOVE
from pynetdicom.dsutils import encode, decode
from pynetdicom._globals import MODE_REQUESTOR, MODE_ACCEPTOR
from pynetdicom.pdu_primitives import (
    UserIdentityNegotiation, SOPClassExtendedNegotiation,
    SOPClassCommonExtendedNegotiation, SCP_SCU_RoleSelectionNegotiation,
    AsynchronousOperationsWindowNegotiation, A_ASSOCIATE,
)
from pynetdicom.sop_class import (
    VerificationSOPClass,
    CTImageStorage, MRImageStorage, RTImageStorage,
    PatientRootQueryRetrieveInformationModelFind,
    StudyRootQueryRetrieveInformationModelFind,
    ModalityWorklistInformationFind,
    PatientStudyOnlyQueryRetrieveInformationModelFind,
    PatientRootQueryRetrieveInformationModelGet,
    PatientStudyOnlyQueryRetrieveInformationModelGet,
    StudyRootQueryRetrieveInformationModelGet,
    PatientRootQueryRetrieveInformationModelMove,
    PatientStudyOnlyQueryRetrieveInformationModelMove,
    StudyRootQueryRetrieveInformationModelMove,
    GeneralRelevantPatientInformationQuery,
    BreastImagingRelevantPatientInformationQuery,
    CardiacRelevantPatientInformationQuery,
    ProductCharacteristicsQueryInformationModelFind,
    SubstanceApprovalQueryInformationModelFind,
    CompositeInstanceRootRetrieveGet,
    CompositeInstanceRootRetrieveMove,
    CompositeInstanceRetrieveWithoutBulkDataGet,
    HangingProtocolInformationModelGet,
    HangingProtocolInformationModelFind,
    HangingProtocolInformationModelMove,
    DefinedProcedureProtocolInformationModelGet,
    DefinedProcedureProtocolInformationModelFind,
    DefinedProcedureProtocolInformationModelMove,
    ColorPaletteInformationModelGet,
    ColorPaletteInformationModelFind,
    ColorPaletteInformationModelMove,
    GenericImplantTemplateInformationModelGet,
    GenericImplantTemplateInformationModelFind,
    GenericImplantTemplateInformationModelMove,
    ImplantAssemblyTemplateInformationModelGet,
    ImplantAssemblyTemplateInformationModelFind,
    ImplantAssemblyTemplateInformationModelMove,
    ImplantTemplateGroupInformationModelFind,
    ImplantTemplateGroupInformationModelGet,
    ImplantTemplateGroupInformationModelMove,
)
from .dummy_c_scp import (
    DummyVerificationSCP, DummyStorageSCP, DummyFindSCP, DummyGetSCP,
    DummyMoveSCP, DummyBaseSCP
)
from .encoded_pdu_items import a_associate_ac
from .parrot import start_server, ThreadedParrot


LOGGER = logging.getLogger('pynetdicom')
LOGGER.setLevel(logging.CRITICAL)
LOGGER.setLevel(logging.DEBUG)

TEST_DS_DIR = os.path.join(os.path.dirname(__file__), 'dicom_files')
BIG_DATASET = dcmread(os.path.join(TEST_DS_DIR, 'RTImageStorage.dcm')) # 2.1 M
DATASET = dcmread(os.path.join(TEST_DS_DIR, 'CTImageStorage.dcm'))
# JPEG2000Lossless UID
COMP_DATASET = dcmread(os.path.join(TEST_DS_DIR, 'MRImageStorage_JPG2000_Lossless.dcm'))


class DummyDIMSE(object):
    def __init__(self):
        self.status = None

    def send_msg(self, rsp, context_id):
        self.status = rsp.Status

    def get_msg(self, block=False):
        return None, None


class TestCStoreSCP(object):
    """Tests for Association._c_store_scp"""
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

    def test_no_presentation_context(self):
        """Test correct status is returned if no valid presentation context."""
        self.scp = DummyStorageSCP()
        self.scp.raise_exception = True
        self.scp.start()

        ae = AE()
        ae.add_requested_context(RTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.on_c_store = self.scp.on_c_store

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = False
        role.scp_role = True

        assoc = ae.associate('localhost', 11112, ext_neg=[role])
        assoc.dimse = DummyDIMSE()
        assert assoc.is_established

        req = C_STORE()
        req.MessageID = 1
        req.AffectedSOPClassUID = DATASET.SOPClassUID
        req.AffectedSOPInstanceUID = DATASET.SOPInstanceUID
        req.Priority = 1
        req._context_id = 1

        bytestream = encode(DATASET, True, True)
        req.DataSet = BytesIO(bytestream)

        assoc._c_store_scp(req)
        assert assoc.dimse.status == 0x0122
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_on_c_store_callback_exception(self):
        """Test correct status returned if exception raised in callback."""
        self.scp = DummyStorageSCP()
        self.scp.raise_exception = True
        self.scp.start()

        ae = AE()
        ae.add_requested_context(CTImageStorage)
        ae.add_requested_context(RTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.on_c_store = self.scp.on_c_store

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = False
        role.scp_role = True

        assoc = ae.associate('localhost', 11112, ext_neg=[role])
        assoc.dimse = DummyDIMSE()
        assert assoc.is_established

        req = C_STORE()
        req.MessageID = 1
        req.AffectedSOPClassUID = DATASET.SOPClassUID
        req.AffectedSOPInstanceUID = DATASET.SOPInstanceUID
        req.Priority = 1
        req._context_id = 1

        bytestream = encode(DATASET, True, True)
        req.DataSet = BytesIO(bytestream)

        assoc._c_store_scp(req)
        assert assoc.dimse.status == 0xC211
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_callback_status_ds_no_status(self):
        """Test correct status returned if status Dataset has no status."""
        self.scp = DummyStorageSCP()
        self.scp.status = Dataset()
        self.scp.status.PatientName = 'ABCD'
        self.scp.start()

        ae = AE()
        ae.add_requested_context(CTImageStorage)
        ae.add_requested_context(RTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.on_c_store = self.scp.on_c_store

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = False
        role.scp_role = True

        assoc = ae.associate('localhost', 11112, ext_neg=[role])
        assoc.dimse = DummyDIMSE()
        assert assoc.is_established

        req = C_STORE()
        req.MessageID = 1
        req.AffectedSOPClassUID = DATASET.SOPClassUID
        req.AffectedSOPInstanceUID = DATASET.SOPInstanceUID
        req.Priority = 1
        req._context_id = 1

        bytestream = encode(DATASET, True, True)
        req.DataSet = BytesIO(bytestream)

        assoc._c_store_scp(req)
        assert assoc.dimse.status == 0xC001
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_callback_status_ds_unknown_elem(self):
        """Test returning a status Dataset with an unknown element."""
        self.scp = DummyStorageSCP()
        self.scp.status = Dataset()
        self.scp.status.Status = 0x0000
        self.scp.status.PatientName = 'ABCD'
        self.scp.start()

        ae = AE()
        ae.add_requested_context(CTImageStorage)
        ae.add_requested_context(RTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.on_c_store = self.scp.on_c_store

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = False
        role.scp_role = True

        assoc = ae.associate('localhost', 11112, ext_neg=[role])
        assoc.dimse = DummyDIMSE()
        assert assoc.is_established

        req = C_STORE()
        req.MessageID = 1
        req.AffectedSOPClassUID = DATASET.SOPClassUID
        req.AffectedSOPInstanceUID = DATASET.SOPInstanceUID
        req.Priority = 1
        req._context_id = 1

        bytestream = encode(DATASET, True, True)
        req.DataSet = BytesIO(bytestream)

        assoc._c_store_scp(req)
        assert assoc.dimse.status == 0x0000
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_callback_invalid_status(self):
        """Test returning a status Dataset with an invalid status type."""
        self.scp = DummyStorageSCP()
        self.scp.status = 'abcd'
        self.scp.start()

        ae = AE()
        ae.add_requested_context(CTImageStorage)
        ae.add_requested_context(RTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.on_c_store = self.scp.on_c_store

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = False
        role.scp_role = True

        assoc = ae.associate('localhost', 11112, ext_neg=[role])
        assoc.dimse = DummyDIMSE()
        assert assoc.is_established

        req = C_STORE()
        req.MessageID = 1
        req.AffectedSOPClassUID = DATASET.SOPClassUID
        req.AffectedSOPInstanceUID = DATASET.SOPInstanceUID
        req.Priority = 1
        req._context_id = 1

        bytestream = encode(DATASET, True, True)
        req.DataSet = BytesIO(bytestream)

        assoc._c_store_scp(req)
        assert assoc.dimse.status == 0xC002
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_callback_unknown_status(self):
        """Test returning a status Dataset with an unknown status value."""
        self.scp = DummyStorageSCP()
        self.scp.status = 0xDEFA
        self.scp.start()

        ae = AE()
        ae.add_requested_context(CTImageStorage)
        ae.add_requested_context(RTImageStorage)

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = False
        role.scp_role = True

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.on_c_store = self.scp.on_c_store

        assoc = ae.associate('localhost', 11112, ext_neg=[role])
        assoc.dimse = DummyDIMSE()
        assert assoc.is_established

        req = C_STORE()
        req.MessageID = 1
        req.AffectedSOPClassUID = DATASET.SOPClassUID
        req.AffectedSOPInstanceUID = DATASET.SOPInstanceUID
        req.Priority = 1
        req._context_id = 1

        bytestream = encode(DATASET, True, True)
        req.DataSet = BytesIO(bytestream)

        assoc._c_store_scp(req)
        assert assoc.dimse.status == 0xDEFA
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_decode_failure(self):
        """Test decoding failure."""
        self.scp = DummyStorageSCP()
        self.scp.start()

        ae = AE()
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = False
        role.scp_role = True

        assoc = ae.associate('localhost', 11112, ext_neg=[role])

        class DummyMessage():
            is_valid_response = True
            DataSet = None
            Status = 0x0000
            STATUS_OPTIONAL_KEYWORDS = []

        class DummyDIMSE():
            def send_msg(*args, **kwargs):
                assert args[1].Status == 0xC210
                assert args[1].ErrorComment == "Unable to decode the dataset"
                return

            def get_msg(*args, **kwargs):
                status = Dataset()
                status.Status = 0x0000

                rsp = DummyMessage()

                return None, rsp

        req = C_STORE()
        req.MessageID = 1
        req.AffectedSOPClassUID = DATASET.SOPClassUID
        req.AffectedSOPInstanceUID = DATASET.SOPInstanceUID
        req.Priority = 1
        req._context_id = 1
        req.DataSet = None

        assoc.dimse = DummyDIMSE()
        assert assoc.is_established
        assoc._c_store_scp(req)

        self.scp.stop()


class TestAssociation(object):
    """Run tests on Associtation."""
    # Association(local_ae, client_socket, peer_ae, acse_timeout,
    #             dimse_timout, max_pdu, ext_neg)
    def setup(self):
        """This function runs prior to all test methods"""
        self.scp = None

    def teardown(self):
        """This function runs after all test methods"""
        if self.scp:
            self.scp.abort()

        for thread in threading.enumerate():
            if isinstance(thread, DummyBaseSCP):
                thread.abort()
                thread.stop()

    def test_scp_assoc_a_abort_reply(self):
        """Test SCP sending an A-ABORT instead of an A-ASSOCIATE response"""
        self.scp = DummyVerificationSCP()
        self.scp.send_a_abort = True
        self.scp.ae._handle_connection = self.scp.dev_handle_connection
        self.scp.use_old_start = True
        self.scp.start()

        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert not assoc.is_established
        assert assoc.is_aborted

        self.scp.stop()

    def test_scp_assoc_ap_abort_reply(self):
        """Test SCP sending an A-P-ABORT instead of an A-ASSOCIATE response"""
        self.scp = DummyVerificationSCP()
        self.scp.send_ap_abort = True
        self.scp.use_old_start = True
        self.scp.ae._handle_connection = self.scp.dev_handle_connection
        self.scp.start()

        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert not assoc.is_established
        assert assoc.is_aborted

        self.scp.stop()

    @staticmethod
    def test_bad_connection():
        """Test connect to non-AE"""
        # sometimes causes hangs in Travis
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        assoc = ae.associate('localhost', 22)

    @staticmethod
    def test_connection_refused():
        """Test connection refused"""
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        assoc = ae.associate('localhost', 11120)

    def test_req_no_presentation_context(self):
        """Test rejection due to no acceptable presentation contexts"""
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        assoc = ae.associate('localhost', 11112)
        time.sleep(0.1)
        assert not assoc.is_established
        assert assoc.is_aborted
        self.scp.stop()

    def test_peer_releases_assoc(self):
        """Test peer releases assoc"""
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        self.scp.release()
        time.sleep(0.1)
        assert not assoc.is_established
        assert assoc.is_released
        #self.assertRaises(SystemExit, ae.quit)
        self.scp.stop() # Important!

    def test_peer_aborts_assoc(self):
        """Test peer aborts assoc"""
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        self.scp.abort()

        time.sleep(0.5)
        assert not assoc.is_established
        assert assoc.is_aborted

        self.scp.stop()

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
        self.scp = DummyVerificationSCP()
        self.scp.delay = 0.2
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.dimse_timeout = 0.1
        assoc = ae.associate('localhost', 11112)
        assert assoc.dimse_timeout == 0.1
        assert assoc.dimse.dimse_timeout == 0.1
        assert assoc.is_established
        assoc.send_c_echo()
        assoc.release()
        assert not assoc.is_released
        assert assoc.is_aborted
        self.scp.stop()

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

    @pytest.mark.skipif(sys.version_info[:2] == (3, 4), reason='no caplog')
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


class TestAssociationSendCEcho(object):
    """Run tests on Assocation send_c_echo."""
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
            def send_msg(*args, **kwargs): return
            def get_msg(*args, **kwargs): return None, None

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
            def send_msg(*args, **kwargs): return
            def get_msg(*args, **kwargs): return None, DummyResponse()

        assoc.dimse = DummyDIMSE()
        if assoc.is_established:
            assoc.send_c_echo()

        assert assoc.is_aborted

        self.scp.stop()

    def test_rsp_success(self):
        """Test receiving a success response from the peer"""
        scp = AE()
        scp.add_supported_context(VerificationSOPClass)
        scp.start_server(('', 11112), block=False)

        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_echo()
        assert result.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_rsp_failure(self):
        """Test receiving a failure response from the peer"""
        #self.scp = DummyVerificationSCP()
        #self.scp.status = 0x0210
        #self.scp.start()
        def on_c_echo(cx, info):
            return 0x0210

        scp = AE()
        scp.add_supported_context(VerificationSOPClass)
        scp.on_c_echo = on_c_echo
        scp.start_server(('', 11112), block=False)

        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_echo()
        assert result.Status == 0x0210
        assoc.release()
        assert assoc.is_released
        #self.scp.stop()

        scp.shutdown()

    def test_rsp_unknown_status(self):
        """Test unknown status value returned by peer"""
        self.scp = DummyVerificationSCP()
        self.scp.status = 0xFFF0
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_echo()
        assert result.Status == 0xFFF0
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rsp_multi_status(self):
        """Test receiving a status with extra elements"""
        def on_c_echo(context, assoc_info):
            ds = Dataset()
            ds.Status = 0x0122
            ds.ErrorComment = 'Some comment'
            return ds

        self.scp = DummyVerificationSCP()
        self.scp.ae.on_c_echo = on_c_echo
        self.scp.start()
        ae = AE()
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
        self.scp.stop()

    def test_abort_during(self):
        """Test aborting the association during message exchange"""
        self.scp = DummyVerificationSCP()
        self.scp.send_abort = True
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_echo()
        assert result == Dataset()
        assert assoc.is_aborted
        self.scp.stop()

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
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
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
        self.scp.stop()

    def test_changing_network_timeout(self):
        """Test changing timeout after associated."""
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        ae.network_timeout = 1

        assert assoc.dul.network_timeout == 1
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_network_times_out_requestor(self):
        """Regression test for #286."""
        ae = AE()
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
        ae = AE()
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
        """Test SCU can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyStorageSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established
        with pytest.raises(RuntimeError):
            assoc.send_c_store(DATASET)
        self.scp.stop()

    def test_no_abstract_syntax_match(self):
        """Test SCU when no accepted abstract syntax"""
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        with pytest.raises(ValueError):
            assoc.send_c_store(DATASET)
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_bad_priority(self):
        """Test bad priority raises exception"""
        self.scp = DummyStorageSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        with pytest.raises(ValueError):
            assoc.send_c_store(DATASET, priority=0x0003)
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_fail_encode_dataset(self):
        """Test failure if unable to encode dataset"""
        self.scp = DummyStorageSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(CTImageStorage, ExplicitVRLittleEndian)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        DATASET.PerimeterValue = b'\x00\x01'
        with pytest.raises(ValueError):
            assoc.send_c_store(DATASET)
        assoc.release()
        assert assoc.is_released
        del DATASET.PerimeterValue # Fix up our changes
        self.scp.stop()

    def test_encode_compressed_dataset(self):
        """Test sending a dataset with a compressed transfer syntax"""
        self.scp = DummyStorageSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(MRImageStorage, JPEG2000Lossless)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_store(COMP_DATASET)
        assert result.Status == 0x0000
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rsp_none(self):
        """Test no response from peer"""
        self.scp = DummyStorageSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        class DummyDIMSE():
            def send_msg(*args, **kwargs): return
            def get_msg(*args, **kwargs): return None, None

        assoc.dimse = DummyDIMSE()
        assert assoc.is_established
        assoc.send_c_store(DATASET)

        assert assoc.is_aborted

        self.scp.stop()

    def test_rsp_invalid(self):
        """Test invalid DIMSE message received from peer"""
        self.scp = DummyStorageSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        class DummyResponse():
            is_valid_response = False

        class DummyDIMSE():
            def send_msg(*args, **kwargs): return
            def get_msg(*args, **kwargs): return DummyResponse(), None

        assoc.dimse = DummyDIMSE()
        assert assoc.is_established
        assoc.send_c_store(DATASET)
        assert assoc.is_aborted

        self.scp.stop()

    def test_rsp_failure(self):
        """Test receiving a failure response from the peer"""
        self.scp = DummyStorageSCP()
        self.scp.status = 0xC000
        self.scp.start()
        ae = AE()
        ae.add_requested_context(CTImageStorage)
        ae.add_requested_context(RTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_store(DATASET)
        assert result.Status == 0xC000
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rsp_warning(self):
        """Test receiving a warning response from the peer"""
        self.scp = DummyStorageSCP()
        self.scp.status = 0xB000
        self.scp.start()
        ae = AE()
        ae.add_requested_context(CTImageStorage)
        ae.add_requested_context(RTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_store(DATASET)
        assert result.Status == 0xB000
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rsp_success(self):
        """Test receiving a success response from the peer"""
        self.scp = DummyStorageSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(CTImageStorage)
        ae.add_requested_context(RTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_store(DATASET)
        assert result.Status == 0x0000
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rsp_unknown_status(self):
        """Test unknown status value returned by peer"""
        self.scp = DummyStorageSCP()
        self.scp.status = 0xFFF0
        self.scp.start()
        ae = AE()
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_store(DATASET)
        assert result.Status == 0xFFF0
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_dataset_no_sop_class_raises(self):
        """Test sending a dataset without SOPClassUID raises."""
        self.scp = DummyStorageSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        ds = DATASET[:]
        del ds.SOPClassUID
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
        self.scp.stop()

    def test_dataset_no_transfer_syntax_raises(self):
        """Test sending a dataset without TransferSyntaxUID raises."""
        self.scp = DummyStorageSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        ds = DATASET[:]
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
        self.scp.stop()

    def test_functional_common_ext_neg(self):
        """Test functioning of the SOP Class Common Extended negotiation."""
        def on_ext(req):
            return req

        self.scp = DummyStorageSCP()
        self.scp.ae.add_supported_context('1.2.3')
        self.scp.ae.on_sop_class_common_extended = on_ext
        self.scp.start()
        ae = AE()
        ae.add_requested_context('1.2.3')
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

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

        ds = deepcopy(DATASET)
        ds.SOPClassUID = '1.2.3'
        status = assoc.send_c_store(ds)
        assert status.Status == 0x0000

        assoc.release()

        self.scp.stop()

    # Regression tests
    def test_no_send_mismatch(self):
        """Test sending a dataset with mismatched transfer syntax (206)."""
        self.scp = DummyStorageSCP()
        self.scp.start()

        ds = dcmread(os.path.join(TEST_DS_DIR, 'CTImageStorage.dcm'))
        ds.file_meta.TransferSyntaxUID = JPEGBaseline

        ae = AE()
        ae.add_requested_context(CTImageStorage, ImplicitVRLittleEndian)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        msg = r""
        with pytest.raises(ValueError, match=msg):
            assoc.send_c_store(ds)

        assoc.release()
        assert assoc.is_released

        self.scp.stop()


class TestAssociationSendCFind(object):
    """Run tests on Assocation send_c_find."""
    def setup(self):
        """Run prior to each test"""
        self.ds = Dataset()
        self.ds.PatientName = '*'
        self.ds.QueryRetrieveLevel = "PATIENT"

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
            next(assoc.send_c_find(self.ds))
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
            next(assoc.send_c_find(self.ds))

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

    def test_good_query_model(self):
        """Test good query_model values"""
        scp = DummyFindSCP()
        scp.statuses = [0x0000]
        scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        ae.add_requested_context(StudyRootQueryRetrieveInformationModelFind)
        ae.add_requested_context(PatientStudyOnlyQueryRetrieveInformationModelFind)
        ae.add_requested_context(ModalityWorklistInformationFind)
        ae.add_requested_context(GeneralRelevantPatientInformationQuery)
        ae.add_requested_context(BreastImagingRelevantPatientInformationQuery)
        ae.add_requested_context(CardiacRelevantPatientInformationQuery)
        ae.add_requested_context(ProductCharacteristicsQueryInformationModelFind)
        ae.add_requested_context(SubstanceApprovalQueryInformationModelFind)
        ae.add_requested_context(HangingProtocolInformationModelFind)
        ae.add_requested_context(DefinedProcedureProtocolInformationModelFind)
        ae.add_requested_context(ColorPaletteInformationModelFind)
        ae.add_requested_context(GenericImplantTemplateInformationModelFind)
        ae.add_requested_context(ImplantAssemblyTemplateInformationModelFind)
        ae.add_requested_context(ImplantTemplateGroupInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        for qm in ['P', 'S', 'O', 'W', 'G', 'B', 'C', 'PC', 'SA', 'H',
                   'D', 'CP', 'IG', 'IA', 'IT']:
            for (status, ds) in assoc.send_c_find(self.ds, query_model=qm):
                assert status.Status == 0x0000

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
            next(assoc.send_c_find(DATASET, query_model='P'))
        with pytest.raises(ValueError):
            test()
        assoc.release()
        assert assoc.is_released
        del DATASET.PerimeterValue # Fix up our changes
        self.scp.stop()

    def test_rsp_failure(self):
        """Test receiving a failure response from the peer"""
        scp = DummyFindSCP()
        scp.statuses = [0xA700]
        scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        for (status, ds) in assoc.send_c_find(self.ds, query_model='P'):
            assert status.Status == 0xA700
            assert ds is None
        assoc.release()
        assert assoc.is_released
        scp.stop()

    def test_rsp_pending(self):
        """Test receiving a pending response from the peer"""
        scp = DummyFindSCP()
        scp.statuses = [0xFF00]
        scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.ds, query_model='P')
        (status, ds) = next(result)
        assert status.Status == 0xFF00
        assert 'PatientName' in ds
        (status, ds) = next(result)
        assert status.Status == 0x0000
        assert ds is None
        assoc.release()
        assert assoc.is_released
        scp.stop()

    def test_rsp_success(self):
        """Test receiving a success response from the peer"""
        self.scp = DummyFindSCP()
        self.scp.statuses = [0x0000]
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        for (status, ds) in assoc.send_c_find(self.ds, query_model='P'):
            assert status.Status == 0x0000
            assert ds is None
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rsp_empty(self):
        """Test receiving a success response from the peer"""
        scp = DummyFindSCP()
        scp.statuses = []
        scp.identifiers = []
        scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        for (status, ds) in assoc.send_c_find(self.ds, query_model='P'):
            assert status.Status == 0x0000
            assert ds is None
        assoc.release()
        assert assoc.is_released
        scp.stop()

    def test_rsp_cancel(self):
        """Test receiving a cancel response from the peer"""
        scp = DummyFindSCP()
        scp.statuses = [0xFE00]
        scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        for (status, ds) in assoc.send_c_find(self.ds, query_model='P'):
            assert status.Status == 0xFE00
            assert ds is None
        assoc.release()
        assert assoc.is_released
        scp.stop()

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

        assoc.dimse = DummyDIMSE()
        assert assoc.is_established
        for (_, _) in assoc.send_c_find(self.ds, query_model='P'):
            pass

        assert assoc.is_aborted

        self.scp.stop()

    def test_rsp_unknown_status(self):
        """Test unknown status value returned by peer"""
        self.scp = DummyFindSCP()
        self.scp.statuses = [0xFFF0]
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        for (status, ds) in assoc.send_c_find(self.ds, query_model='P'):
            assert status.Status == 0xFFF0
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rsp_bad_dataset(self):
        """Test bad dataset returned by on_c_find"""
        self.scp = DummyFindSCP()

        def on_c_find(ds, context, assoc_info):
            def test(): pass
            yield 0xFF00, test

        self.scp.ae.on_c_find = on_c_find
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind,
                                 ExplicitVRLittleEndian)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        for (status, ds) in assoc.send_c_find(self.ds, query_model='P'):
            assert status.Status in range(0xC000, 0xD000)
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

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

        assoc.dimse = DummyDIMSE()
        assert assoc.is_established

        results = assoc.send_c_find(self.ds, query_model='P')
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

        class DummyMessage():
            is_valid_response = True
            DataSet = None
            Status = 0x0000
            STATUS_OPTIONAL_KEYWORDS = []

        class DummyDIMSE():
            def send_msg(*args, **kwargs):
                return

            def get_msg(*args, **kwargs):
                rsp = C_FIND()
                rsp.Status = 0xFF00
                rsp.MessageIDBeingRespondedTo = 1
                rsp.Identifier = BytesIO(b'\x08\x00\x01\x00\x04\x00\x00\x00\x00\x08\x00\x49')
                return 1, rsp

        assoc.dimse = DummyDIMSE()
        assert assoc.is_established

        results = assoc.send_c_find(self.ds, query_model='P')
        status, ds = next(results)

        assert status.Status == 0xFF00
        assert ds is None

        self.scp.stop()

    @pytest.mark.skipif(sys.version_info[:2] == (3, 4), reason='no caplog')
    def test_rsp_not_find(self, caplog):
        """Test receiving a non C-FIND message in response."""
        with caplog.at_level(logging.ERROR, logger='pynetdicom'):
            ae = AE()
            assoc = Association(ae, 'requestor')
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
            results = assoc.send_c_find(identifier, query_model='P')
            status, ds = next(results)
            assert status == Dataset()
            assert ds is None
            with pytest.raises(StopIteration):
                next(results)
            assert (
                'Received an unexpected C-STORE message from the peer'
            ) in caplog.text
            assert assoc.is_aborted

    @pytest.mark.skipif(sys.version_info[:2] == (3, 4), reason='no caplog')
    def test_rsp_invalid_find(self, caplog):
        """Test receiving an invalid C-FIND message in response."""
        with caplog.at_level(logging.ERROR, logger='pynetdicom'):
            ae = AE()
            assoc = Association(ae, 'requestor')
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
            results = assoc.send_c_find(identifier, query_model='P')
            status, ds = next(results)
            assert status == Dataset()
            assert ds is None
            with pytest.raises(StopIteration):
                next(results)
            assert (
                'Received an invalid C-FIND response from the peer'
            ) in caplog.text
            assert assoc.is_aborted


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
            next(assoc.send_c_get(self.ds))
        self.scp.stop()

    def test_must_be_scp(self):
        """Test failure if not SCP for storage context."""
        self.scp = DummyGetSCP()
        self.scp.no_suboperations = 2
        self.scp.statuses = [0xFF00, 0xFF00]
        self.scp.datasets = [self.good, self.good]

        def on_c_store(ds, context, assoc_info):
            assert 'PatientName' in ds
            return 0x0000

        self.scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = True
        role.scp_role = False

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
        assert assoc.is_established
        result = assoc.send_c_get(self.ds, query_model='P')
        time.sleep(0.2)
        (status, ds) = next(result)
        assert status.Status == 0xff00
        assert ds is None
        (status, ds) = next(result)
        assert status.Status == 0xff00
        assert ds is None
        (status, ds) = next(result)
        assert status.Status == 0xb000
        assert ds.FailedSOPInstanceUIDList == ['1.1.1', '1.1.1']
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

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
            next(assoc.send_c_get(self.ds))

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

    def test_good_query_model(self):
        """Test all the query models"""
        self.scp = DummyGetSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(StudyRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(PatientStudyOnlyQueryRetrieveInformationModelGet)
        ae.add_requested_context(CompositeInstanceRootRetrieveGet)
        ae.add_requested_context(CompositeInstanceRetrieveWithoutBulkDataGet)
        ae.add_requested_context(HangingProtocolInformationModelGet)
        ae.add_requested_context(DefinedProcedureProtocolInformationModelGet)
        ae.add_requested_context(ColorPaletteInformationModelGet)
        ae.add_requested_context(GenericImplantTemplateInformationModelGet)
        ae.add_requested_context(ImplantAssemblyTemplateInformationModelGet)
        ae.add_requested_context(ImplantTemplateGroupInformationModelGet)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        for qm in ['P', 'S', 'O', 'C', 'CB', 'H', 'D', 'CP', 'IG', 'IA', 'IT']:
            for (status, ds) in assoc.send_c_get(self.ds, query_model=qm):
                assert status.Status == 0x0000

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
            next(assoc.send_c_get(DATASET, query_model='P'))
        with pytest.raises(ValueError):
            test()
        assoc.release()
        assert assoc.is_released
        del DATASET.PerimeterValue # Fix up our changes
        self.scp.stop()

    def test_rsp_failure(self):
        """Test receiving a failure response"""
        self.scp = DummyGetSCP()
        self.scp.statuses = [0xA701]
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        def on_c_store(ds, context, assoc_info):
            return 0x0000
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        for (status, ds) in assoc.send_c_get(self.ds, query_model='P'):
            assert status.Status == 0xA701
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rsp_success(self):
        """Test good send"""
        self.scp = DummyGetSCP()
        self.scp.no_suboperations = 2
        self.scp.statuses = [0xFF00, 0xFF00]
        self.scp.datasets = [self.good, self.good]

        def on_c_store(ds, context, assoc_info):
            assert 'PatientName' in ds
            return 0x0000

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
        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
        assert assoc.is_established
        result = assoc.send_c_get(self.ds, query_model='P')
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
        self.scp.stop()

    def test_rsp_pending_send_success(self):
        """Test receiving a pending response and sending success"""
        self.scp = DummyGetSCP()
        self.scp.no_suboperations = 3
        self.scp.statuses = [0xFF00, 0xFF00, 0xB000]
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
        def on_c_store(ds, context, assoc_info):
            return 0x0000
        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
        assert assoc.is_established
        result = assoc.send_c_get(self.ds, query_model='P')
        # We have 2 status, ds and 1 success
        (status, ds) = next(result)
        assert status.Status == 0xFF00
        assert ds is None
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
        self.scp.stop()

    def test_rsp_pending_send_failure(self):
        """Test receiving a pending response and sending a failure"""
        self.scp = DummyGetSCP()
        self.scp.no_suboperations = 3
        self.scp.statuses = [0xFF00, 0xFF00, 0x0000]
        self.scp.datasets = [self.good, self.good, None]
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = True
        role.scp_role = False

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        def on_c_store(ds, context, assoc_info):
            return 0xA700
        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
        assert assoc.is_established
        result = assoc.send_c_get(self.ds, query_model='P')
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
        self.scp.stop()

    def test_rsp_pending_send_warning(self):
        """Test receiving a pending response and sending a warning"""
        self.scp = DummyGetSCP()
        self.scp.no_suboperations = 3
        self.scp.statuses = [0xFF00, 0xFF00, 0xB000]
        self.scp.datasets = [self.good, self.good, None]
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = True
        role.scp_role = False

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        def on_c_store(ds, context, assoc_info):
            return 0xB007
        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
        assert assoc.is_established
        result = assoc.send_c_get(self.ds, query_model='P')
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
        self.scp.stop()

    def test_rsp_cancel(self):
        """Test receiving a cancel response"""
        self.scp = DummyGetSCP()
        self.scp.statuses = [0xFE00]
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        for (status, ds) in assoc.send_c_get(self.ds, query_model='P'):
            assert status.Status == 0xFE00
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rsp_warning(self):
        """Test receiving a warning response"""
        self.scp = DummyGetSCP()
        self.scp.no_suboperations = 3
        self.scp.statuses = [0xFF00, 0xFF00, 0xB000]
        self.scp.datasets = [self.good, self.good, None]
        self.scp.start()

        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = True
        role.scp_role = False

        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        def on_c_store(ds, context, assoc_info):
            return 0xB007
        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
        assert assoc.is_established
        result = assoc.send_c_get(self.ds, query_model='P')
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
        self.scp.stop()

    def test_rsp_unknown_status(self):
        """Test unknown status value returned by peer"""
        self.scp = DummyGetSCP()
        self.scp.statuses = [0xFFF0]
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.add_requested_context(CTImageStorage)

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = CTImageStorage
        role.scu_role = True
        role.scp_role = False

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
        assert assoc.is_established
        for (status, ds) in assoc.send_c_get(self.ds, query_model='P'):
            assert status.Status == 0xFFF0
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_connection_timeout(self):
        """Test the connection timing out"""
        self.scp = DummyGetSCP()
        self.scp.no_suboperations = 2
        self.scp.statuses = [0xFF00, 0xFF00]
        self.scp.datasets = [self.good, self.good]

        def on_c_store(ds, context, assoc_info):
            assert 'PatientName' in ds
            return 0x0000

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
        ae.on_c_store = on_c_store
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

        assoc.dimse = DummyDIMSE()
        assert assoc.is_established

        results = assoc.send_c_get(self.ds, query_model='P')
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

        def on_c_store(ds, context, assoc_info):
            assert 'PatientName' in ds
            return 0x0000

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
        ae.on_c_store = on_c_store
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
                rsp = C_GET()
                rsp.Status = 0xC000
                rsp.MessageIDBeingRespondedTo = 1
                rsp.Identifier = BytesIO(b'\x08\x00\x01\x00\x04\x00\x00\x00\x00\x08\x00\x49')
                return 1, rsp

        assoc.dimse = DummyDIMSE()
        assert assoc.is_established

        results = assoc.send_c_get(self.ds, query_model='P')
        status, ds = next(results)

        assert status.Status == 0xC000
        assert ds is None

        self.scp.stop()

    def test_config_return_dataset(self):
        """Test the _config option DECODE_STORE_DATASETS = True."""
        from pynetdicom import _config

        orig_value = _config.DECODE_STORE_DATASETS
        _config.DECODE_STORE_DATASETS = True

        self.scp = DummyGetSCP()
        self.scp.no_suboperations = 1
        self.scp.statuses = [0xFF00]
        self.scp.datasets = [self.good]

        def on_c_store(ds, context, assoc_info):
            assert isinstance(ds, Dataset)
            return 0x0000

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
        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
        assert assoc.is_established
        result = assoc.send_c_get(self.ds, query_model='P')
        (status, ds) = next(result)
        assert status.Status == 0xff00
        assert ds is None
        (status, ds) = next(result)
        assert status.Status == 0x0000
        assert ds is None
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

        _config.DECODE_STORE_DATASETS = orig_value

        self.scp.stop()

    def test_config_return_bytes(self):
        """Test the _config option DECODE_STORE_DATASETS = False."""
        from pynetdicom import _config

        orig_value = _config.DECODE_STORE_DATASETS
        _config.DECODE_STORE_DATASETS = False

        self.scp = DummyGetSCP()
        self.scp.no_suboperations = 1
        self.scp.statuses = [0xFF00]
        self.scp.datasets = [self.good]

        def on_c_store(ds, context, assoc_info):
            assert isinstance(ds, bytes)
            return 0x0000

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
        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112, ext_neg=[role])
        assert assoc.is_established
        result = assoc.send_c_get(self.ds, query_model='P')
        (status, ds) = next(result)
        assert status.Status == 0xff00
        assert ds is None
        (status, ds) = next(result)
        assert status.Status == 0x0000
        assert ds is None
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

        _config.DECODE_STORE_DATASETS = orig_value

    @pytest.mark.skipif(sys.version_info[:2] == (3, 4), reason='no caplog')
    def test_rsp_not_get(self, caplog):
        """Test receiving a non C-GET/C-STORE message in response."""
        with caplog.at_level(logging.ERROR, logger='pynetdicom'):
            ae = AE()
            assoc = Association(ae, 'requestor')
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
            results = assoc.send_c_get(identifier, query_model='P')
            status, ds = next(results)
            assert status == Dataset()
            assert ds is None
            with pytest.raises(StopIteration):
                next(results)
            assert (
                'Received an unexpected C-FIND message from the peer'
            ) in caplog.text
            assert assoc.is_aborted

    @pytest.mark.skipif(sys.version_info[:2] == (3, 4), reason='no caplog')
    def test_rsp_invalid_get(self, caplog):
        """Test receiving an invalid C-GET message in response."""
        with caplog.at_level(logging.ERROR, logger='pynetdicom'):
            ae = AE()
            assoc = Association(ae, 'requestor')
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
            results = assoc.send_c_get(identifier, query_model='P')
            status, ds = next(results)
            assert status == Dataset()
            assert ds is None
            with pytest.raises(StopIteration):
                next(results)
            assert (
                'Received an invalid C-GET response from the peer'
            ) in caplog.text
            assert assoc.is_aborted


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

    def teardown(self):
        """Clear any active threads"""
        if self.scp:
            self.scp.abort()

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
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established
        with pytest.raises(RuntimeError):
            next(assoc.send_c_move(self.ds, b'TESTMOVE'))
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
            next(assoc.send_c_move(self.ds, b'TESTMOVE'))

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

    def test_good_query_model(self):
        """Test all the query models"""
        self.scp2 = DummyStorageSCP(11113)
        self.scp2.start()

        self.scp = DummyMoveSCP()  # port 11112
        self.scp.no_suboperations = 2
        self.scp.destination_ae = ('localhost', 11113)
        self.scp.statuses = [0xFF00, 0xFF00]
        self.scp.datasets = [self.good, self.good]
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(StudyRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(PatientStudyOnlyQueryRetrieveInformationModelMove)
        ae.add_requested_context(CompositeInstanceRootRetrieveMove)
        ae.add_requested_context(HangingProtocolInformationModelMove)
        ae.add_requested_context(DefinedProcedureProtocolInformationModelMove)
        ae.add_requested_context(ColorPaletteInformationModelMove)
        ae.add_requested_context(GenericImplantTemplateInformationModelMove)
        ae.add_requested_context(ImplantAssemblyTemplateInformationModelMove)
        ae.add_requested_context(ImplantTemplateGroupInformationModelMove)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        for qm in ['P', 'S', 'O', 'C', 'H', 'D', 'CP', 'IG', 'IA', 'IT']:
            result = assoc.send_c_move(self.ds, b'TESTMOVE', query_model=qm)
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
        self.scp.stop()

        self.scp2.stop()

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
            next(assoc.send_c_move(DATASET, b'SOMEPLACE', query_model='P'))
        with pytest.raises(ValueError):
            test()
        assoc.release()
        assert assoc.is_released
        del DATASET.PerimeterValue # Fix up our changes
        self.scp.stop()

    def test_move_destination_no_assoc(self):
        """Test move destination failed to assoc"""
        self.scp = DummyMoveSCP()
        self.scp.destination_ae = ('localhost', 11113)
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(StudyRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(PatientStudyOnlyQueryRetrieveInformationModelMove)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        for (status, ds) in assoc.send_c_move(self.ds, b'TESTMOVE', query_model='P'):
            assert status.Status == 0xa801
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_move_destination_unknown(self):
        """Test unknown move destination"""
        self.scp = DummyMoveSCP()
        self.scp.destination_ae = ('localhost', 11113)
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(StudyRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(PatientStudyOnlyQueryRetrieveInformationModelMove)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        for (status, ds) in assoc.send_c_move(self.ds, b'UNKNOWN', query_model='P'):
            assert status.Status == 0xa801
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_move_destination_failed_store(self):
        """Test the destination AE returning failed status"""
        self.scp2 = DummyStorageSCP(11113)
        self.scp2.status = 0xA700
        self.scp2.start()

        self.scp = DummyMoveSCP()
        self.scp.destination_ae = ('localhost', 11113)
        self.scp.no_suboperations = 2
        self.scp.statuses = [0xFF00, 0xFF00]
        self.scp.datasets = [self.good, self.good]
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(StudyRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(PatientStudyOnlyQueryRetrieveInformationModelMove)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.ds, b'TESTMOVE', query_model='P')
        (status, ds) = next(result)
        assert status.Status == 0xFF00
        (status, ds) = next(result)
        assert status.Status == 0xFF00
        (status, ds) = next(result)
        assert status.Status == 0xB000
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released
        self.scp.stop()

        self.scp2.stop()

    def test_move_destination_warning_store(self):
        """Test the destination AE returning warning status"""
        self.scp2 = DummyStorageSCP(11113)
        self.scp2.status = 0xB000
        self.scp2.start()

        self.scp = DummyMoveSCP()
        self.scp.destination_ae = ('localhost', 11113)
        self.scp.no_suboperations = 2
        self.scp.statuses = [0xFF00, 0xFF00]
        self.scp.datasets = [self.good, self.good]
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(StudyRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(PatientStudyOnlyQueryRetrieveInformationModelMove)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.ds, b'TESTMOVE', query_model='P')
        (status, ds) = next(result)
        assert status.Status == 0xFF00
        (status, ds) = next(result)
        assert status.Status == 0xFF00
        (status, ds) = next(result)
        assert status.Status == 0xB000

        assoc.release()
        assert assoc.is_released
        self.scp.stop()

        self.scp2.stop()

    def test_rsp_failure(self):
        """Test the user on_c_move returning failure status"""
        self.scp2 = DummyStorageSCP(11113)
        self.scp2.start()

        self.scp = DummyMoveSCP()
        self.scp.no_suboperations = 1
        self.scp.destination_ae = ('localhost', 11113)
        self.scp.statuses = [0xC000]
        self.scp.datasets = [None]
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(StudyRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(PatientStudyOnlyQueryRetrieveInformationModelMove)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.ds, b'TESTMOVE', query_model='P')
        (status, ds) = next(result)
        assert status.Status == 0xC000
        assert 'FailedSOPInstanceUIDList' in ds
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released
        self.scp.stop()
        self.scp2.stop()

    def test_rsp_warning(self):
        """Test receiving a warning response from the peer"""
        self.scp2 = DummyStorageSCP(11113)
        self.scp2.status = 0xB007
        self.scp2.start()

        self.scp = DummyMoveSCP()
        self.scp.destination_ae = ('localhost', 11113)
        self.scp.no_suboperations = 2
        self.scp.statuses = [0xFF00, 0xFF00]
        self.scp.datasets = [self.good, self.good]
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(StudyRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(PatientStudyOnlyQueryRetrieveInformationModelMove)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.ds, b'TESTMOVE', query_model='P')
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
        self.scp.stop()

        self.scp2.stop()

    def test_rsp_cancel(self):
        """Test the user on_c_move returning cancel status"""
        self.scp2 = DummyStorageSCP(11113)
        self.scp2.start()

        self.scp = DummyMoveSCP()
        self.scp.destination_ae = ('localhost', 11113)
        self.scp.no_suboperations = 2
        self.scp.statuses = [0xFE00, 0xFF00]
        self.scp.datasets = [None, self.good]
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(StudyRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(PatientStudyOnlyQueryRetrieveInformationModelMove)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.ds, b'TESTMOVE', query_model='P')
        (status, ds) = next(result)
        assert status.Status == 0xFE00

        assoc.release()
        assert assoc.is_released
        self.scp.stop()

        self.scp2.stop()

    def test_rsp_success(self):
        """Test the user on_c_move returning success status"""
        self.scp2 = DummyStorageSCP(11113)
        self.scp2.start()

        self.scp = DummyMoveSCP()
        self.scp.destination_ae = ('localhost', 11113)
        self.scp.no_suboperations = 2
        self.scp.statuses = [0xFF00, 0x0000]
        self.scp.datasets = [self.good, None]
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(StudyRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(PatientStudyOnlyQueryRetrieveInformationModelMove)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_move(self.ds, b'TESTMOVE', query_model='P')
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
        self.scp.stop()

        self.scp2.stop()

    def test_rsp_unknown_status(self):
        """Test unknown status value returned by peer"""
        self.scp2 = DummyStorageSCP(11113)
        self.scp2.start()

        self.scp = DummyMoveSCP()
        self.scp.destination_ae = ('localhost', 11113)
        self.scp.statuses = [0xFFF0]
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(CTImageStorage)
        ae.add_supported_context(CTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        for (status, ds) in assoc.send_c_move(self.ds, b'TESTMOVE', query_model='P'):
            assert status.Status == 0xFFF0
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

        self.scp2.stop()

    def test_multiple_c_move(self):
        """Test multiple C-MOVE operation requests"""
        self.scp2 = DummyStorageSCP(11113)
        self.scp2.start()

        self.scp = DummyMoveSCP()
        self.scp.no_suboperations = 2
        self.scp.statuses = [0xFF00, 0xFF00]
        self.scp.datasets = [self.good, self.good]
        self.scp.destination_ae = ('localhost', 11113)
        self.scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(StudyRootQueryRetrieveInformationModelMove)
        ae.add_requested_context(PatientStudyOnlyQueryRetrieveInformationModelMove)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        for ii in range(20):
            assoc = ae.associate('localhost', 11112)
            assert assoc.is_established
            assert not assoc.is_released
            result = assoc.send_c_move(self.ds, b'TESTMOVE', query_model='P')
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

        self.scp.stop()
        self.scp2.stop()

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

        assoc.dimse = DummyDIMSE()
        assert assoc.is_established

        results = assoc.send_c_move(self.ds, b'TEST', query_model='P')
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

        def on_c_store(ds, context, assoc_info):
            assert 'PatientName' in ds
            return 0x0000

        self.scp.start()
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove,
                                 ExplicitVRLittleEndian)
        ae.add_requested_context(CTImageStorage)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.on_c_store = on_c_store
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
                rsp = C_MOVE()
                rsp.MessageIDBeingRespondedTo = 1
                rsp.Status = 0xC000
                rsp.Identifier = BytesIO(b'\x08\x00\x01\x00\x04\x00\x00\x00\x00\x08\x00\x49')
                return 1, rsp

        assoc.dimse = DummyDIMSE()
        assert assoc.is_established

        results = assoc.send_c_move(self.ds, b'TEST', query_model='P')
        status, ds = next(results)

        assert status.Status == 0xC000
        assert ds is None

        self.scp.stop()

    @pytest.mark.skipif(sys.version_info[:2] == (3, 4), reason='no caplog')
    def test_rsp_not_move(self, caplog):
        """Test receiving a non C-MOVE/C-STORE message in response."""
        with caplog.at_level(logging.ERROR, logger='pynetdicom'):
            ae = AE()
            assoc = Association(ae, 'requestor')
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
            results = assoc.send_c_move(identifier, move_aet=b'A', query_model='P')
            status, ds = next(results)
            assert status == Dataset()
            assert ds is None
            with pytest.raises(StopIteration):
                next(results)
            assert (
                'Received an unexpected C-FIND message from the peer'
            ) in caplog.text
            assert assoc.is_aborted

    @pytest.mark.skipif(sys.version_info[:2] == (3, 4), reason='no caplog')
    def test_rsp_invalid_move(self, caplog):
        """Test receiving an invalid C-MOVE message in response."""
        with caplog.at_level(logging.ERROR, logger='pynetdicom'):
            ae = AE()
            assoc = Association(ae, 'requestor')
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
            results = assoc.send_c_move(identifier, move_aet=b'A', query_model='P')
            status, ds = next(results)
            assert status == Dataset()
            assert ds is None
            with pytest.raises(StopIteration):
                next(results)
            assert (
                'Received an invalid C-MOVE response from the peer'
            ) in caplog.text
            assert assoc.is_aborted


class TestAssociationCallbacks(object):
    """Run tests on Assocation callbacks."""
    def setup(self):
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

    def test_debug_assoc_rq(self):
        """Test the callback"""
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assoc.debug_association_requested(None)
        assoc.release()
        assert assoc.is_released
        self.scp.stop()


class TestGetValidContext(object):
    """Tests for Association._get_valid_context."""
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
            r"No suitable presentation context for the SCU role has been "
            r"accepted by the peer for the SOP Class 'CT Image Storage'"
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
            r"No suitable presentation context for the SCU role has been "
            r"accepted by the peer for the SOP Class 'Verification SOP Class' "
            r"with a transfer syntax of 'JPEG Baseline \(Process 1\)'"
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
            r"No suitable presentation context for the SCU role has been "
            r"accepted by the peer for the SOP Class 'CT Image Storage' "
            r"with a transfer syntax of 'Implicit VR Little Endian'"
        )
        with pytest.raises(ValueError, match=msg):
            assoc._get_valid_context(CTImageStorage,
                                     ImplicitVRLittleEndian,
                                     'scu',
                                     context_id=3)

        # Compressed (JPEGBaseline) accepted, compressed (JPEG2000) sent
        msg = (
            r"No suitable presentation context for the SCU role has been "
            r"accepted by the peer for the SOP Class 'CT Image Storage' "
            r"with a transfer syntax of 'JPEG 2000 Image Compression'"
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
            r"No suitable presentation context for the SCP role has been "
            r"accepted by the peer for the SOP Class 'Verification SOP Class'"
        )
        with pytest.raises(ValueError, match=msg):
            assoc._get_valid_context('1.2.840.10008.1.1',
                                     '',
                                     'scp',
                                     context_id=1)

        # Transfer syntax used
        msg = (
            r"No suitable presentation context for the SCP role has been "
            r"accepted by the peer for the SOP Class 'Verification SOP Class' "
            r"with a transfer syntax of 'Implicit VR Little Endian'"
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
            r"No suitable presentation context for the SCU role has been "
            r"accepted by the peer for the SOP Class 'CT Image Storage'"
        )
        with pytest.raises(ValueError, match=msg):
            assoc._get_valid_context(CTImageStorage,
                                     '',
                                     'scu',
                                     context_id=3)

        # Transfer syntax used
        msg = (
            r"No suitable presentation context for the SCU role has been "
            r"accepted by the peer for the SOP Class 'CT Image Storage' "
            r"with a transfer syntax of 'Implicit VR Little Endian'"
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
            r"No suitable presentation context for the SCU role has been "
            r"accepted by the peer for the SOP Class 'CT Image Storage'"
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
            r"No suitable presentation context for the SCU role has been "
            r"accepted by the peer for the SOP Class 'Verification SOP Class' "
            r"with a transfer syntax of 'JPEG Baseline \(Process 1\)'"
        )
        with pytest.raises(ValueError, match=msg):
            assoc._get_valid_context('1.2.840.10008.1.1', JPEGBaseline, 'scu')

        # Compressed (JPEGBaseline) accepted, uncompressed sent
        # Confirm otherwise OK
        cx = assoc._get_valid_context(CTImageStorage, JPEGBaseline, 'scu')
        assert cx.context_id == 3
        assert cx.transfer_syntax[0] == JPEGBaseline

        msg = (
            r"No suitable presentation context for the SCU role has been "
            r"accepted by the peer for the SOP Class 'CT Image Storage' "
            r"with a transfer syntax of 'Implicit VR Little Endian'"
        )
        with pytest.raises(ValueError, match=msg):
            assoc._get_valid_context(CTImageStorage,
                                     ImplicitVRLittleEndian,
                                     'scu')

        # Compressed (JPEGBaseline) accepted, compressed (JPEG2000) sent
        msg = (
            r"No suitable presentation context for the SCU role has been "
            r"accepted by the peer for the SOP Class 'CT Image Storage' "
            r"with a transfer syntax of 'JPEG 2000 Image Compression'"
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
            r"No suitable presentation context for the SCP role has been "
            r"accepted by the peer for the SOP Class 'Verification SOP Class'"
        )
        with pytest.raises(ValueError, match=msg):
            assoc._get_valid_context('1.2.840.10008.1.1', '', 'scp')

        # Transfer syntax used
        msg = (
            r"No suitable presentation context for the SCP role has been "
            r"accepted by the peer for the SOP Class 'Verification SOP Class' "
            r"with a transfer syntax of 'Implicit VR Little Endian'"
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
            r"No suitable presentation context for the SCU role has been "
            r"accepted by the peer for the SOP Class 'CT Image Storage'"
        )
        with pytest.raises(ValueError, match=msg):
            assoc._get_valid_context(CTImageStorage,
                                     '',
                                     'scu')

        # Transfer syntax used
        msg = (
            r"No suitable presentation context for the SCU role has been "
            r"accepted by the peer for the SOP Class 'CT Image Storage' "
            r"with a transfer syntax of 'Implicit VR Little Endian'"
        )
        with pytest.raises(ValueError, match=msg):
            assoc._get_valid_context(CTImageStorage,
                                     ImplicitVRLittleEndian,
                                     'scu')
