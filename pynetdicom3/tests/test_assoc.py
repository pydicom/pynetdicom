#!/usr/bin/env python
"""Association testing

TODO: Add tests to check raise NotImplemented if no user implementation
of the DIMSE-C service callbacks
"""

from io import BytesIO
import logging
import os
import select
import socket
from struct import pack
import time
import threading

import pytest

from pydicom import read_file
from pydicom.dataset import Dataset
from pydicom.uid import UID, ImplicitVRLittleEndian, ExplicitVRLittleEndian

from pynetdicom3 import AE, VerificationSOPClass
from pynetdicom3.association import Association
from pynetdicom3.dimse_primitives import C_STORE, C_FIND, C_GET, C_MOVE
from pynetdicom3.dsutils import encode, decode
from pynetdicom3.pdu_primitives import (
    UserIdentityNegotiation, SOPClassExtendedNegotiation,
    SOPClassCommonExtendedNegotiation
)
from pynetdicom3.sop_class import (
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
    StudyRootQueryRetrieveInformationModelMove
)
from .dummy_c_scp import (
    DummyVerificationSCP, DummyStorageSCP, DummyFindSCP, DummyGetSCP,
    DummyMoveSCP, DummyBaseSCP
)

LOGGER = logging.getLogger('pynetdicom3')
LOGGER.setLevel(logging.CRITICAL)
#LOGGER.setLevel(logging.DEBUG)

TEST_DS_DIR = os.path.join(os.path.dirname(__file__), 'dicom_files')
BIG_DATASET = read_file(os.path.join(TEST_DS_DIR, 'RTImageStorage.dcm')) # 2.1 M
DATASET = read_file(os.path.join(TEST_DS_DIR, 'CTImageStorage.dcm'))
COMP_DATASET = read_file(os.path.join(TEST_DS_DIR, 'MRImageStorage_JPG2000_Lossless.dcm'))


class DummyDIMSE(object):
    def __init__(self):
        self.status = None

    def send_msg(self, rsp, context_id):
        self.status = rsp.Status


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

        ae = AE(scu_sop_class=[RTImageStorage])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.on_c_store = self.scp.on_c_store

        assoc = ae.associate('localhost', 11112)
        assoc.dimse = DummyDIMSE()
        assert assoc.is_established

        req = C_STORE()
        req.MessageID = 1
        req.AffectedSOPClassUID = DATASET.SOPClassUID
        req.AffectedSOPInstanceUID = DATASET.SOPInstanceUID
        req.Priority = 1

        bytestream = encode(DATASET, True, True)
        req.DataSet = BytesIO(bytestream)

        assoc._c_store_scp(req)
        assert assoc.dimse.status == 0x0122
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_dataset_decode_failure(self):
        """Test correct status returned if unable to decode dataset."""
        # Not sure how to test this
        pass

    def test_on_c_store_callback_exception(self):
        """Test correct status returned if exception raised in callback."""
        self.scp = DummyStorageSCP()
        self.scp.raise_exception = True
        self.scp.start()

        ae = AE(scu_sop_class=[CTImageStorage, RTImageStorage])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.on_c_store = self.scp.on_c_store

        assoc = ae.associate('localhost', 11112)
        assoc.dimse = DummyDIMSE()
        assert assoc.is_established

        req = C_STORE()
        req.MessageID = 1
        req.AffectedSOPClassUID = DATASET.SOPClassUID
        req.AffectedSOPInstanceUID = DATASET.SOPInstanceUID
        req.Priority = 1

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

        ae = AE(scu_sop_class=[CTImageStorage, RTImageStorage])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.on_c_store = self.scp.on_c_store

        assoc = ae.associate('localhost', 11112)
        assoc.dimse = DummyDIMSE()
        assert assoc.is_established

        req = C_STORE()
        req.MessageID = 1
        req.AffectedSOPClassUID = DATASET.SOPClassUID
        req.AffectedSOPInstanceUID = DATASET.SOPInstanceUID
        req.Priority = 1

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

        ae = AE(scu_sop_class=[CTImageStorage, RTImageStorage])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.on_c_store = self.scp.on_c_store

        assoc = ae.associate('localhost', 11112)
        assoc.dimse = DummyDIMSE()
        assert assoc.is_established

        req = C_STORE()
        req.MessageID = 1
        req.AffectedSOPClassUID = DATASET.SOPClassUID
        req.AffectedSOPInstanceUID = DATASET.SOPInstanceUID
        req.Priority = 1

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

        ae = AE(scu_sop_class=[CTImageStorage, RTImageStorage])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.on_c_store = self.scp.on_c_store

        assoc = ae.associate('localhost', 11112)
        assoc.dimse = DummyDIMSE()
        assert assoc.is_established

        req = C_STORE()
        req.MessageID = 1
        req.AffectedSOPClassUID = DATASET.SOPClassUID
        req.AffectedSOPInstanceUID = DATASET.SOPInstanceUID
        req.Priority = 1

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

        ae = AE(scu_sop_class=[CTImageStorage, RTImageStorage])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.on_c_store = self.scp.on_c_store

        assoc = ae.associate('localhost', 11112)
        assoc.dimse = DummyDIMSE()
        assert assoc.is_established

        req = C_STORE()
        req.MessageID = 1
        req.AffectedSOPClassUID = DATASET.SOPClassUID
        req.AffectedSOPInstanceUID = DATASET.SOPInstanceUID
        req.Priority = 1

        bytestream = encode(DATASET, True, True)
        req.DataSet = BytesIO(bytestream)

        assoc._c_store_scp(req)
        assert assoc.dimse.status == 0xDEFA
        assoc.release()
        assert assoc.is_released
        self.scp.stop()


class TestAssociation(object):
    """Run tests on Associtation."""
    # Association(local_ae, client_socket, peer_ae, acse_timeout,
    #             dimse_timout, max_pdu, ext_neg)
    def setup(self):
        """This function runs prior to all test methods"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(('', 0))
        self.socket.listen(1)
        self.peer = {'AET' : 'PEER_AET',
                     'Port' : 11112,
                     'Address' : 'localhost'}
        self.ext_neg = []

        self.scp = None

    def teardown(self):
        """This function runs after all test methods"""
        self.socket.close()

        if self.scp:
            self.scp.abort()

        time.sleep(0.1)

        for thread in threading.enumerate():
            if isinstance(thread, DummyBaseSCP):
                thread.abort()
                thread.stop()

    def test_scp_assoc_a_abort_reply(self):
        """Test the SCP sending an A-ABORT instead of an A-ASSOCIATE response"""
        class DummyAE(threading.Thread, AE):
            """Dummy AE used for testing"""
            def __init__(self, scp_sop_class, port):
                """Initialise the class"""
                AE.__init__(self, scp_sop_class=scp_sop_class, port=port)
                threading.Thread.__init__(self)
                self.daemon = True

            def run(self):
                """The thread run method"""
                self.start_scp()

            def start_scp(self):
                """new runner"""
                self._bind_socket()
                while True:
                    try:
                        if self._quit:
                            break
                        self._monitor_socket()
                        self.cleanup_associations()

                    except KeyboardInterrupt:
                        self.stop()

            def _monitor_socket(self):
                """Override the normal method"""
                try:
                    read_list, _, _ = select.select([self.local_socket], [], [], 0)
                except (socket.error, ValueError):
                    return

                # If theres a connection
                if read_list:
                    client_socket, _ = self.local_socket.accept()
                    client_socket.setsockopt(socket.SOL_SOCKET,
                                             socket.SO_RCVTIMEO,
                                             pack('ll', 10, 0))

                    # Create a new Association
                    # Association(local_ae, local_socket=None, max_pdu=16382)
                    assoc = Association(self,
                                        client_socket,
                                        max_pdu=self.maximum_pdu_size,
                                        acse_timeout=self.acse_timeout,
                                        dimse_timeout=self.dimse_timeout)
                    # Set the ACSE to abort association requests
                    assoc._a_abort_assoc_rq = True
                    assoc.start()
                    self.active_associations.append(assoc)

        scp = DummyAE(scp_sop_class=[VerificationSOPClass], port=11112)
        scp.start()

        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert not assoc.is_established

        scp.stop()

    def test_scp_assoc_ap_abort_reply(self):
        """Test the SCP sending an A-ABORT instead of an A-ASSOCIATE response"""
        class DummyAE(threading.Thread, AE):
            """Dummy AE used for testing"""
            def __init__(self, scp_sop_class, port):
                """Initialise the class"""
                AE.__init__(self, scp_sop_class=scp_sop_class, port=port)
                threading.Thread.__init__(self)
                self.daemon = True

            def run(self):
                """The thread run method"""
                self.start_scp()

            def start_scp(self):
                """new runner"""
                self._bind_socket()
                while True:
                    try:
                        if self._quit:
                            break
                        self._monitor_socket()
                        self.cleanup_associations()

                    except KeyboardInterrupt:
                        self.stop()

            def _monitor_socket(self):
                """Override the normal method"""
                try:
                    read_list, _, _ = select.select([self.local_socket], [], [], 0)
                except ValueError:
                    return

                # If theres a connection
                if read_list:
                    client_socket, _ = self.local_socket.accept()
                    client_socket.setsockopt(socket.SOL_SOCKET,
                                             socket.SO_RCVTIMEO,
                                             pack('ll', 10, 0))

                    # Create a new Association
                    # Association(local_ae, local_socket=None, max_pdu=16382)
                    assoc = Association(self,
                                        client_socket,
                                        max_pdu=self.maximum_pdu_size,
                                        acse_timeout=self.acse_timeout,
                                        dimse_timeout=self.dimse_timeout)
                    # Set the ACSE to abort association requests
                    assoc._a_p_abort_assoc_rq = True
                    assoc.start()
                    self.active_associations.append(assoc)

        scp = DummyAE(scp_sop_class=[VerificationSOPClass], port=11112)
        scp.start()

        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert not assoc.is_established

        scp.stop()

    @staticmethod
    def test_bad_connection():
        """Test connect to non-AE"""
        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 22)

    @staticmethod
    def test_connection_refused():
        """Test connection refused"""
        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11120)

    def test_init_errors(self):
        """Test bad parameters on init raise errors"""
        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        with pytest.raises(TypeError, match="with either the client_socket or peer_ae"):
            Association(ae)
        with pytest.raises(TypeError, match="with either client_socket or peer_ae"):
            Association(ae, client_socket=self.socket, peer_ae=self.peer)
        with pytest.raises(TypeError, match="client_socket must be"):
            Association(ae, client_socket=123)
        with pytest.raises(TypeError, match="peer_ae must be a dict"):
            Association(ae, peer_ae=123)
        with pytest.raises(KeyError, match="peer_ae must contain 'AET'"):
            Association(ae, peer_ae={})
        with pytest.raises(TypeError, match="local_ae must be a pynetdicom"):
            Association(12345, peer_ae=self.peer)
        with pytest.raises(TypeError, match="dimse_timeout must be numeric"):
            Association(ae, peer_ae=self.peer, dimse_timeout='a')
        with pytest.raises(TypeError, match="acse_timeout must be numeric"):
            Association(ae, peer_ae=self.peer, acse_timeout='a')
        with pytest.raises(TypeError, match="max_pdu must be an int"):
            Association(ae, peer_ae=self.peer, max_pdu='a')
        with pytest.raises(TypeError, match="ext_neg must be a list"):
            Association(ae, peer_ae=self.peer, ext_neg='a')

    def test_run_acceptor(self):
        """Test running as an Association acceptor (SCP)"""
        pass

    def test_run_requestor(self):
        """Test running as an Association requestor (SCU)"""
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.dimse_timeout = 5
        ae.presentation_contexts_scu = []
        assoc = ae.associate('localhost', 11112)
        assert not assoc.is_established
        #self.assertRaises(SystemExit, ae.quit)
        scp.stop()

        # Test good request and assoc accepted by peer
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established
        assert assoc.is_released
        #self.assertRaises(SystemExit, ae.quit)
        scp.stop()

    def test_req_no_presentation_context(self):
        """Test rejection due to no acceptable presentation contexts"""
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[CTImageStorage])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert not assoc.is_established
        assert assoc.is_aborted
        scp.stop()

    def test_peer_releases_assoc(self):
        """Test peer releases assoc"""
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        scp.release()
        assert not assoc.is_established
        assert assoc.is_released
        #self.assertRaises(SystemExit, ae.quit)
        scp.stop() # Important!

    def test_peer_aborts_assoc(self):
        """Test peer aborts assoc"""
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        self.scp.abort()
        time.sleep(0.1)
        assert not assoc.is_established
        assert assoc.is_aborted
        self.scp.stop()

    def test_peer_rejects_assoc(self):
        """Test peer rejects assoc"""
        scp = DummyVerificationSCP()
        scp.ae.require_calling_aet = b'HAHA NOPE'
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_rejected
        assert not assoc.is_established
        #self.assertRaises(SystemExit, ae.quit)
        scp.stop() # Important!

    def test_kill(self):
        """Test killing the association"""
        pass

    def test_assoc_release(self):
        """Test Association release"""
        # Simple release
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established
        scp.stop()

        # Simple release, then release again
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
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
        scp.stop()

        # Simple release, then abort
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
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
        scp.stop()

    def test_assoc_abort(self):
        """Test Association abort"""
        # Simple abort
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assoc.abort()
        assert not assoc.is_established
        assert assoc.is_aborted
        scp.stop()

        # Simple abort, then release
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
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
        scp.stop()

        # Simple abort, then abort again
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assoc.abort()
        assert assoc.is_aborted
        assert not assoc.is_established
        assoc.abort()
        scp.stop()

    def test_scp_removed_ui(self):
        """Test SCP removes UI negotiation"""
        scp = DummyVerificationSCP()
        scp.start()
        ui = UserIdentityNegotiation()
        ui.user_identity_type = 0x01
        ui.primary_field = b'pynetdicom'

        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[ui])
        assert assoc.is_established
        assoc.release()
        assert assoc.is_released
        scp.stop()

    def test_scp_removed_ext_neg(self):
        """Test SCP removes ex negotiation"""
        scp = DummyVerificationSCP()
        scp.start()
        ext = SOPClassExtendedNegotiation()
        ext.sop_class_uid = '1.1.1.1'
        ext.service_class_application_information = b'\x01\x02'

        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[ext])
        assert assoc.is_established
        assoc.release()
        assert assoc.is_released
        scp.stop()

    def test_scp_removed_com_ext_neg(self):
        """Test SCP removes common ext negotiation"""
        scp = DummyVerificationSCP()
        scp.start()
        ext = SOPClassCommonExtendedNegotiation()
        self.related_general_sop_class_identification = ['1.2.1']
        ext.sop_class_uid = '1.1.1.1'
        ext.service_class_uid = '1.1.3'

        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, ext_neg=[ext])
        assert assoc.is_established
        assoc.release()
        assert assoc.is_released
        scp.stop()

    def test_scp_assoc_limit(self):
        """Test SCP limits associations"""
        scp = DummyVerificationSCP()
        scp.ae.maximum_associations = 1
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assoc_2 = ae.associate('localhost', 11112)
        assert not assoc_2.is_established
        assoc.release()
        assert assoc.is_released
        scp.stop()

    def test_require_called_aet(self):
        """SCP requires matching called AET"""
        scp = DummyVerificationSCP()
        scp.ae.require_called_aet = b'TESTSCU'
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert not assoc.is_established
        assert assoc.is_rejected
        scp.stop()

    def test_require_calling_aet(self):
        """SCP requires matching called AET"""
        scp = DummyVerificationSCP()
        scp.ae.require_calling_aet = b'TESTSCP'
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert not assoc.is_established
        assert assoc.is_rejected
        scp.stop()

    def test_acse_timeout(self):
        """Test that the ACSE timeout works"""
        pass

    def test_acse_timeout_release_no_reply(self):
        """Test that the ACSE timeout works when waiting for an A-RELEASE reply"""
        pass

    def test_dimse_timeout(self):
        """Test that the DIMSE timeout works"""
        scp = DummyVerificationSCP()
        scp.delay = 0.2
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
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
        scp.stop()

    def test_dul_timeout(self):
        """Test that the DUL timeout (ARTIM) works"""
        pass

    def test_multiple_association_release_cycles(self):
        """Test repeatedly associating and releasing"""
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
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

        scp.stop()


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
        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
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
        ae = AE(scu_sop_class=[CTImageStorage])
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
        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        class DummyDIMSE():
            def send_msg(*args, **kwargs): return
            def receive_msg(*args, **kwargs): return None, None

        assoc.dimse = DummyDIMSE()
        if assoc.is_established:
            assoc.send_c_echo()

        assert assoc.is_aborted

        self.scp.stop()

    def test_rsp_invalid(self):
        """Test invalid response received from peer"""
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        class DummyResponse():
            is_valid_response = False

        class DummyDIMSE():
            def send_msg(*args, **kwargs): return
            def receive_msg(*args, **kwargs): return DummyResponse(), None

        assoc.dimse = DummyDIMSE()
        if assoc.is_established:
            assoc.send_c_echo()

        assert assoc.is_aborted

        self.scp.stop()

    def test_rsp_success(self):
        """Test receiving a success response from the peer"""
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_echo()
        assert result.Status == 0x0000
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rsp_failure(self):
        """Test receiving a failure response from the peer"""
        self.scp = DummyVerificationSCP()
        self.scp.status = 0x0210
        self.scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_echo()
        assert result.Status == 0x0210
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rsp_unknown_status(self):
        """Test unknown status value returned by peer"""
        self.scp = DummyVerificationSCP()
        self.scp.status = 0xFFF0
        self.scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
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
        def on_c_echo():
            ds = Dataset()
            ds.Status = 0x0122
            ds.ErrorComment = 'Some comment'
            return ds

        self.scp = DummyVerificationSCP()
        self.scp.ae.on_c_echo = on_c_echo
        self.scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
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
        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_echo()
        assert result == Dataset()
        assert assoc.is_aborted
        self.scp.stop()


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
        ae = AE(scu_sop_class=[CTImageStorage])
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
        ae = AE(scu_sop_class=[VerificationSOPClass])
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
        ae = AE(scu_sop_class=[CTImageStorage])
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
        ae = AE(scu_sop_class=[CTImageStorage],
                transfer_syntax=[ExplicitVRLittleEndian])
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
        ae = AE(scu_sop_class=[MRImageStorage])
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
        ae = AE(scu_sop_class=[CTImageStorage])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        class DummyDIMSE():
            def send_msg(*args, **kwargs): return
            def receive_msg(*args, **kwargs): return None, None

        assoc.dimse = DummyDIMSE()
        assert assoc.is_established
        assoc.send_c_store(DATASET)

        assert assoc.is_aborted

        self.scp.stop()

    def test_rsp_invalid(self):
        """Test invalid DIMSE message received from peer"""
        self.scp = DummyStorageSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[CTImageStorage])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        class DummyResponse():
            is_valid_response = False

        class DummyDIMSE():
            def send_msg(*args, **kwargs): return
            def receive_msg(*args, **kwargs): return DummyResponse(), None

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
        ae = AE(scu_sop_class=[CTImageStorage, RTImageStorage])
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
        ae = AE(scu_sop_class=[CTImageStorage, RTImageStorage])
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
        ae = AE(scu_sop_class=[CTImageStorage, RTImageStorage])
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
        ae = AE(scu_sop_class=[CTImageStorage])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        result = assoc.send_c_store(DATASET)
        assert result.Status == 0xFFF0
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
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
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
        ae = AE(scu_sop_class=[VerificationSOPClass])
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
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        with pytest.raises(ValueError):
            next(assoc.send_c_find(self.ds, query_model='X'))
        assoc.release()
        assert assoc.is_released
        scp.stop()

    def test_good_query_model(self):
        """Test good query_model values"""
        scp = DummyFindSCP()
        scp.statuses = [0x0000]
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind,
                               StudyRootQueryRetrieveInformationModelFind,
                               PatientStudyOnlyQueryRetrieveInformationModelFind,
                               ModalityWorklistInformationFind])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        for (status, ds) in assoc.send_c_find(self.ds, query_model='P'):
            assert status.Status == 0x0000
        for (status, ds) in assoc.send_c_find(self.ds, query_model='S'):
            assert status.Status == 0x0000
        for (status, ds) in assoc.send_c_find(self.ds, query_model='O'):
            assert status.Status == 0x0000
        for (status, ds) in assoc.send_c_find(self.ds, query_model='W'):
            assert status.Status == 0x0000
        assoc.release()
        assert assoc.is_released
        scp.stop()

    def test_fail_encode_identifier(self):
        """Test a failure in encoding the Identifier dataset"""
        self.scp = DummyFindSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind],
                transfer_syntax=[ExplicitVRLittleEndian])
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
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
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
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
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
        scp = DummyFindSCP()
        scp.statuses = [0x0000]
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
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

    def test_rsp_empty(self):
        """Test receiving a success response from the peer"""
        scp = DummyFindSCP()
        scp.statuses = []
        scp.identifiers = []
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
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
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
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
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        class DummyResponse():
            is_valid_response = False

        class DummyDIMSE():
            def send_msg(*args, **kwargs): return
            def receive_msg(*args, **kwargs): return DummyResponse(), None

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
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
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

        def on_c_find(ds):
            def test(): pass
            yield 0xFF00, test

        self.scp.ae.on_c_find = on_c_find
        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind],
                transfer_syntax=[ExplicitVRLittleEndian])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        for (status, ds) in assoc.send_c_find(self.ds, query_model='P'):
            assert status.Status in range(0xC000, 0xD000)
        assoc.release()
        assert assoc.is_released
        self.scp.stop()


class TestAssociationSendCCancelFind(object):
    """Run tests on Assocation send_c_cancel_find."""
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
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established
        with pytest.raises(RuntimeError):
            assoc.send_c_cancel_find(1)
        self.scp.stop()

    def test_good_send(self):
        """Test send_c_cancel_move"""
        self.scp = DummyFindSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assoc.send_c_cancel_find(1)
        self.scp.stop()

    def test_bad_send(self):
        """Test send_c_cancel_move"""
        self.scp = DummyFindSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        with pytest.raises(TypeError):
            assoc.send_c_cancel_find('a')
        assoc.release()
        assert assoc.is_released
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
        self.good.SOPClassUID = CTImageStorage().UID
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
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established
        with pytest.raises(RuntimeError):
            next(assoc.send_c_get(self.ds))
        self.scp.stop()

    def test_no_abstract_syntax_match(self):
        """Test when no accepted abstract syntax"""
        self.scp = DummyStorageSCP()
        self.scp.datasets = [self.good]
        self.scp.start()
        ae = AE(scu_sop_class=[CTImageStorage])
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
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet])
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
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               StudyRootQueryRetrieveInformationModelGet,
                               PatientStudyOnlyQueryRetrieveInformationModelGet])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        for (status, ds) in assoc.send_c_get(self.ds, query_model='P'):
            assert status.Status == 0x0000
        for (status, ds) in assoc.send_c_get(self.ds, query_model='S'):
            assert status.Status == 0x0000
        for (status, ds) in assoc.send_c_get(self.ds, query_model='O'):
            assert status.Status == 0x0000
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_fail_encode_identifier(self):
        """Test a failure in encoding the Identifier dataset"""
        self.scp = DummyGetSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet],
                transfer_syntax=[ExplicitVRLittleEndian])
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
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        def on_c_store(ds): return 0x0000
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

        def on_c_store(ds):
            assert 'PatientName' in ds
            return 0x0000

        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage],
                scp_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage],
                transfer_syntax=[ExplicitVRLittleEndian])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112)
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
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage],
                scp_sop_class=[CTImageStorage])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        def on_c_store(ds): return 0x0000
        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112)
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
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage],
                scp_sop_class=[CTImageStorage])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        def on_c_store(ds): return 0xA700
        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112)
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
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage],
                scp_sop_class=[CTImageStorage])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        def on_c_store(ds): return 0xB007
        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112)
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
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet])
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

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage],
                scp_sop_class=[CTImageStorage])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        def on_c_store(ds): return 0xB007
        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112)
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
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage],
                scp_sop_class=[CTImageStorage])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        for (status, ds) in assoc.send_c_get(self.ds, query_model='P'):
            assert status.Status == 0xFFF0
        assoc.release()
        assert assoc.is_released
        self.scp.stop()


class TestAssociationSendCCancelGet(object):
    """Run tests on Assocation send_c_cancel_find."""
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
        self.scp = DummyGetSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established
        with pytest.raises(RuntimeError):
            assoc.send_c_cancel_get(1)
        self.scp.stop()


class TestAssociationSendCMove(object):
    """Run tests on Assocation send_c_move."""
    def setup(self):
        """Run prior to each test"""
        self.ds = Dataset()
        self.ds.PatientName = '*'
        self.ds.QueryRetrieveLevel = "PATIENT"

        self.good = Dataset()
        self.good.SOPClassUID = CTImageStorage().UID
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
        ae = AE(scu_sop_class=[VerificationSOPClass])
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
        ae = AE(scu_sop_class=[CTImageStorage])
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
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove])
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

        self.scp = DummyMoveSCP()
        self.scp.no_suboperations = 2
        self.scp.statuses = [0xFF00, 0xFF00]
        self.scp.datasets = [self.good, self.good]
        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               StudyRootQueryRetrieveInformationModelMove,
                               PatientStudyOnlyQueryRetrieveInformationModelMove])
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
        assert status.Status == 0x0000
        with pytest.raises(StopIteration):
            next(result)

        result = assoc.send_c_move(self.ds, b'TESTMOVE', query_model='S')
        (status, ds) = next(result)
        assert status.Status == 0xFF00
        (status, ds) = next(result)
        assert status.Status == 0xFF00
        (status, ds) = next(result)
        assert status.Status == 0x0000
        with pytest.raises(StopIteration):
            next(result)

        result = assoc.send_c_move(self.ds, b'TESTMOVE', query_model='O')
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
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove],
                transfer_syntax=[ExplicitVRLittleEndian])
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
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               StudyRootQueryRetrieveInformationModelMove,
                               PatientStudyOnlyQueryRetrieveInformationModelMove])
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
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               StudyRootQueryRetrieveInformationModelMove,
                               PatientStudyOnlyQueryRetrieveInformationModelMove])
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
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               StudyRootQueryRetrieveInformationModelMove,
                               PatientStudyOnlyQueryRetrieveInformationModelMove])
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
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               StudyRootQueryRetrieveInformationModelMove,
                               PatientStudyOnlyQueryRetrieveInformationModelMove])
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
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               StudyRootQueryRetrieveInformationModelMove,
                               PatientStudyOnlyQueryRetrieveInformationModelMove])
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
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               StudyRootQueryRetrieveInformationModelMove,
                               PatientStudyOnlyQueryRetrieveInformationModelMove])
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
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               StudyRootQueryRetrieveInformationModelMove,
                               PatientStudyOnlyQueryRetrieveInformationModelMove])
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
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               StudyRootQueryRetrieveInformationModelMove,
                               PatientStudyOnlyQueryRetrieveInformationModelMove])
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
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               CTImageStorage],
                scp_sop_class=[CTImageStorage])
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
        self.scp.start()
        ae = AE(
            scu_sop_class=[
                PatientRootQueryRetrieveInformationModelMove,
                StudyRootQueryRetrieveInformationModelMove,
                PatientStudyOnlyQueryRetrieveInformationModelMove
            ]
        )
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


class TestAssociationSendCCancelMove(object):
    """Run tests on Assocation send_c_cancel_move."""
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

    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyMoveSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established
        with pytest.raises(RuntimeError):
            assoc.send_c_cancel_move(1)
        self.scp.stop()


class TestAssociationSendNEventReport(object):
    """Run tests on Assocation send_n_event_report."""
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

    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established
        with pytest.raises(RuntimeError):
            assoc.send_n_event_report()
        self.scp.stop()

    def test_not_implemented(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        with pytest.raises(NotImplementedError):
            assoc.send_n_event_report()
        assoc.release()
        assert assoc.is_released
        self.scp.stop()


class TestAssociationSendNGet(object):
    """Run tests on Assocation send_n_get."""
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

    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established
        with pytest.raises(RuntimeError):
            assoc.send_n_get()
        self.scp.stop()

    def test_not_implemented(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        with pytest.raises(NotImplementedError):
            assoc.send_n_get()
        assoc.release()
        assert assoc.is_released
        self.scp.stop()


class TestAssociationSendNSet(object):
    """Run tests on Assocation send_n_set."""
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

    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established
        with pytest.raises(RuntimeError):
            assoc.send_n_set()
        self.scp.stop()

    def test_not_implemented(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        with pytest.raises(NotImplementedError):
            assoc.send_n_set()
        assoc.release()
        assert assoc.is_released
        self.scp.stop()


class TestAssociationSendNAction(object):
    """Run tests on Assocation send_n_action."""
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

    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established
        with pytest.raises(RuntimeError):
            assoc.send_n_action()
        self.scp.stop()

    def test_not_implemented(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        with pytest.raises(NotImplementedError):
            assoc.send_n_action()
        assoc.release()
        assert assoc.is_released
        self.scp.stop()


class TestAssociationSendNCreate(object):
    """Run tests on Assocation send_n_create."""
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

    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established
        with pytest.raises(RuntimeError):
            assoc.send_n_create()
        self.scp.stop()

    def test_not_implemented(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        with pytest.raises(NotImplementedError):
            assoc.send_n_create()
        assoc.release()
        assert assoc.is_released
        self.scp.stop()


class TestAssociationSendNDelete(object):
    """Run tests on Assocation send_n_delete."""
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

    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established
        with pytest.raises(RuntimeError):
            assoc.send_n_delete()
        self.scp.stop()

    def test_not_implemented(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        with pytest.raises(NotImplementedError):
            assoc.send_n_delete()
        assoc.release()
        assert assoc.is_released
        self.scp.stop()


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
        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assoc.debug_association_requested(None)
        assoc.release()
        assert assoc.is_released
        self.scp.stop()


if __name__ == "__main__":
    unittest.main()
