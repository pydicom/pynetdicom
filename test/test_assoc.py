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
import unittest

from pydicom import read_file
from pydicom.dataset import Dataset
from pydicom.uid import UID, ImplicitVRLittleEndian, ExplicitVRLittleEndian

from dummy_c_scp import (DummyVerificationSCP, DummyStorageSCP, DummyFindSCP,
                         DummyGetSCP, DummyMoveSCP, DummyBaseSCP)
from pynetdicom3 import AE, VerificationSOPClass
from pynetdicom3.association import Association
from pynetdicom3.dimse_primitives import C_STORE, C_FIND, C_GET, C_MOVE
from pynetdicom3.dsutils import encode, decode
from pynetdicom3.pdu_primitives import (UserIdentityNegotiation,
                                        SOPClassExtendedNegotiation,
                                        SOPClassCommonExtendedNegotiation)
from pynetdicom3.sop_class import (CTImageStorage, MRImageStorage,
                                   RTImageStorage,
                                   PatientRootQueryRetrieveInformationModelFind,
                                   StudyRootQueryRetrieveInformationModelFind,
                                   ModalityWorklistInformationFind,
                                   PatientStudyOnlyQueryRetrieveInformationModelFind,
                                   PatientRootQueryRetrieveInformationModelGet,
                                   PatientStudyOnlyQueryRetrieveInformationModelGet,
                                   StudyRootQueryRetrieveInformationModelGet,
                                   PatientRootQueryRetrieveInformationModelMove,
                                   PatientStudyOnlyQueryRetrieveInformationModelMove,
                                   StudyRootQueryRetrieveInformationModelMove)

LOGGER = logging.getLogger('pynetdicom3')
LOGGER.setLevel(logging.CRITICAL)
#LOGGER.setLevel(logging.DEBUG)

TEST_DS_DIR = os.path.join(os.path.dirname(__file__), 'dicom_files')
BIG_DATASET = read_file(os.path.join(TEST_DS_DIR, 'RTImageStorage.dcm')) # 2.1 M
DATASET = read_file(os.path.join(TEST_DS_DIR, 'CTImageStorage.dcm'))
COMP_DATASET = read_file(os.path.join(TEST_DS_DIR, 'MRImageStorage_JPG2000_Lossless.dcm'))


class TestAssociation(unittest.TestCase):
    """Run tests on Associtation."""
    # Association(local_ae, client_socket, peer_ae, acse_timeout,
    #             dimse_timout, max_pdu, ext_neg)
    def setUp(self):
        """This function runs prior to all test methods"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(('', 0))
        self.socket.listen(1)
        self.peer = {'AET' : 'PEER_AET',
                     'Port' : 11112,
                     'Address' : 'localhost'}
        self.ext_neg = []

    def tearDown(self):
        """This function runs after all test methods"""
        self.socket.close()

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
        assoc = ae.associate('localhost', 11112)
        self.assertFalse(assoc.is_established)

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
        assoc = ae.associate('localhost', 11112)
        self.assertFalse(assoc.is_established)

        scp.stop()

    @staticmethod
    def test_bad_connection():
        """Test connect to non-AE"""
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 22)

    @staticmethod
    def test_connection_refused():
        """Test connection refused"""
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11120)

    def test_init_errors(self):
        """Test bad parameters on init raise errors"""
        ae = AE(scu_sop_class=[VerificationSOPClass])
        with self.assertRaises(TypeError, msg="must have client_socket or peer_ae"):
            Association(ae)
        with self.assertRaises(TypeError, msg="must have client_socket or peer_ae"):
            Association(ae, client_socket=self.socket, peer_ae=self.peer)
        with self.assertRaises(TypeError, msg="wrong client_socket type"):
            Association(ae, client_socket=123)
        with self.assertRaises(TypeError, msg="wrong peer_ae type"):
            Association(ae, peer_ae=123)
        with self.assertRaises(KeyError, msg="missing keys in peer_ae"):
            Association(ae, peer_ae={})
        with self.assertRaises(TypeError, msg="wrong local_ae type"):
            Association(12345, peer_ae=self.peer)
        with self.assertRaises(TypeError, msg="wrong dimse_timeout type"):
            Association(ae, peer_ae=self.peer, dimse_timeout='a')
        with self.assertRaises(TypeError, msg="wrong acse_timeout type"):
            Association(ae, peer_ae=self.peer, acse_timeout='a')
        with self.assertRaises(TypeError, msg="wrong max_pdu type"):
            Association(ae, peer_ae=self.peer, max_pdu='a')
        with self.assertRaises(TypeError, msg="wrong ext_neg type"):
            Association(ae, peer_ae=self.peer, ext_neg='a')

    def test_run_acceptor(self):
        """Test running as an Association acceptor (SCP)"""
        pass

    def test_run_requestor(self):
        """Test running as an Association requestor (SCU)"""
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.presentation_contexts_scu = []
        assoc = ae.associate('localhost', 11112)
        self.assertFalse(assoc.is_established)
        self.assertRaises(SystemExit, ae.quit)
        scp.stop()

        # Test good request and assoc accepted by peer
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        assoc.release()
        self.assertFalse(assoc.is_established)
        self.assertRaises(SystemExit, ae.quit)
        scp.stop()

    def test_req_no_presentation_context(self):
        """Test rejection due to no acceptable presentation contexts"""
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_aborted)
        self.assertFalse(assoc.is_established)
        self.assertRaises(SystemExit, ae.quit)
        scp.stop()

    def test_peer_releases_assoc(self):
        """Test peer releases assoc"""
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        scp.release()
        self.assertFalse(assoc.is_established)
        self.assertTrue(assoc.is_released)
        self.assertRaises(SystemExit, ae.quit)
        scp.stop() # Important!

    def test_peer_aborts_assoc(self):
        """Test peer aborts assoc"""
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        scp.abort()
        self.assertFalse(assoc.is_established)
        self.assertTrue(assoc.is_aborted)
        scp.stop() # Important!

    def test_peer_rejects_assoc(self):
        """Test peer rejects assoc"""
        scp = DummyVerificationSCP()
        scp.ae.require_calling_aet = b'HAHA NOPE'
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_rejected)
        self.assertFalse(assoc.is_established)
        self.assertRaises(SystemExit, ae.quit)
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
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        assoc.release()
        self.assertFalse(assoc.is_established)
        scp.stop()

        # Simple release, then release again
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        assoc.release()
        self.assertFalse(assoc.is_established)
        self.assertTrue(assoc.is_released)
        assoc.release()
        scp.stop()

        # Simple release, then abort
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        assoc.release()
        self.assertTrue(assoc.is_released)
        self.assertFalse(assoc.is_established)
        assoc.abort()
        self.assertFalse(assoc.is_aborted)
        scp.stop()

    def test_assoc_abort(self):
        """Test Association abort"""
        # Simple abort
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        assoc.abort()
        self.assertFalse(assoc.is_established)
        self.assertTrue(assoc.is_aborted)
        scp.stop()

        # Simple abort, then release
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        assoc.abort()
        self.assertFalse(assoc.is_established)
        self.assertTrue(assoc.is_aborted)
        assoc.release()
        self.assertFalse(assoc.is_released)
        scp.stop()

        # Simple abort, then abort again
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        assoc.abort()
        self.assertTrue(assoc.is_aborted)
        self.assertFalse(assoc.is_established)
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
        assoc = ae.associate('localhost', 11112, ext_neg=[ui])
        self.assertTrue(assoc.is_established)
        assoc.release()
        scp.stop()

    def test_scp_removed_ext_neg(self):
        """Test SCP removes ex negotiation"""
        scp = DummyVerificationSCP()
        scp.start()
        ext = SOPClassExtendedNegotiation()
        ext.sop_class_uid = '1.1.1.1'
        ext.service_class_application_information = b'\x01\x02'

        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112, ext_neg=[ext])
        self.assertTrue(assoc.is_established)
        assoc.release()
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
        assoc = ae.associate('localhost', 11112, ext_neg=[ext])
        self.assertTrue(assoc.is_established)
        assoc.release()
        scp.stop()

    def test_scp_assoc_limit(self):
        """Test SCP limits associations"""
        scp = DummyVerificationSCP()
        scp.ae.maximum_associations = 1
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        assoc_2 = ae.associate('localhost', 11112)
        self.assertFalse(assoc_2.is_established)
        assoc.release()
        scp.stop()

    def test_require_called_aet(self):
        """SCP requires matching called AET"""
        scp = DummyVerificationSCP()
        scp.ae.require_called_aet = b'TESTSCU'
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertFalse(assoc.is_established)
        self.assertTrue(assoc.is_rejected)
        scp.stop()

    def test_require_calling_aet(self):
        """SCP requires matching called AET"""
        scp = DummyVerificationSCP()
        scp.ae.require_calling_aet = b'TESTSCP'
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertFalse(assoc.is_established)
        self.assertTrue(assoc.is_rejected)
        scp.stop()

    def test_acse_timeout(self):
        """Test that the ACSE timeout works"""
        pass

    def test_dimse_timeout(self):
        """Test that the DIMSE timeout works"""
        scp = DummyVerificationSCP()
        scp.delay = 0.2
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.dimse_timeout = 0.1
        assoc = ae.associate('localhost', 11112)
        self.assertEqual(assoc.dimse_timeout, 0.1)
        self.assertEqual(assoc.dimse.dimse_timeout, 0.1)
        self.assertTrue(assoc.is_established)
        assoc.send_c_echo()
        assoc.release()
        self.assertTrue(assoc.is_aborted)
        scp.stop()

    def test_dul_timeout(self):
        """Test that the DUL timeout (ARTIM) works"""
        pass


class TestAssociationSendCEcho(unittest.TestCase):
    """Run tests on Assocation send_c_echo."""
    def setUp(self):
        """Run prior to each test"""
        self.scp = None

    def tearDown(self):
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
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        self.assertFalse(assoc.is_established)
        with self.assertRaises(RuntimeError):
            assoc.send_c_echo()
        self.scp.stop()

    def test_no_response(self):
        """Test no response from peer"""
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        class DummyDIMSE():
            def send_msg(*args, **kwargs): return
            def receive_msg(*args, **kwargs): return None, None

        assoc.dimse = DummyDIMSE()
        if assoc.is_established:
            assoc.send_c_echo()

        self.assertTrue(assoc.is_aborted)
        
        self.scp.stop()

    def test_invalid_response(self):
        """Test invalid response received from peer"""
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)

        class DummyResponse():
            is_valid_response = False
        
        class DummyDIMSE():
            def send_msg(*args, **kwargs): return
            def receive_msg(*args, **kwargs): return DummyResponse(), None

        assoc.dimse = DummyDIMSE()
        if assoc.is_established:
            assoc.send_c_echo()

        self.assertTrue(assoc.is_aborted)
        
        self.scp.stop()

    def test_good_response(self):
        """Test successful c-echo"""
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_echo()
        self.assertEqual(result.Status, 0x0000)
        assoc.release()
        self.scp.stop()

    def test_bad_user_on_c_echo(self):
        """Test no exception raised in on_c_echo"""
        self.scp = DummyVerificationSCP()
        def on_c_echo(): raise RuntimeError
        self.scp.ae.on_c_echo = on_c_echo
        self.scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        assoc.send_c_echo()
        assoc.release()
        self.scp.stop()

    def test_abort_during_c_echo(self):
        """Test aborting the association during c-echo"""
        self.scp = DummyVerificationSCP()
        self.scp.send_abort = True
        self.scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_echo()
        self.assertEqual(result, Dataset())
        self.assertTrue(assoc.is_aborted)
        self.scp.stop()

    def test_no_abstract_syntax_match(self):
        """Test SCU when no accepted abstract syntax"""
        self.scp = DummyStorageSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        self.assertRaises(ValueError, assoc.send_c_echo)
        assoc.release()
        self.scp.stop()

    def test_status_ds_multi(self):
        """Test successful c-echo"""
        def on_c_echo():
            ds = Dataset()
            ds.Status = 0x0122
            ds.ErrorComment = 'Some comment'
            return ds
        
        self.scp = DummyVerificationSCP()
        self.scp.ae.on_c_echo = on_c_echo
        self.scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_echo()
        self.assertEqual(result.Status, 0x0122)
        self.assertEqual(result.ErrorComment, 'Some comment')
        assoc.release()
        self.scp.stop()


class TestAssociationSendCStore(unittest.TestCase):
    """Run tests on Assocation send_c_store."""
    def setUp(self):
        """Run prior to each test"""
        self.scp = None

    def tearDown(self):
        """Clear any active threads"""
        if self.scp:
            self.scp.abort()

        time.sleep(0.1)

        for thread in threading.enumerate():
            if isinstance(thread, DummyBaseSCP):
                thread.abort()
                thread.stop()

    def test_dataset_encode_failure(self):
        """Test failure if unable to encode dataset"""
        self.scp = DummyStorageSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[CTImageStorage],
                transfer_syntax=[ExplicitVRLittleEndian])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        DATASET.PerimeterValue = b'\x00\x01'
        self.assertRaises(ValueError, assoc.send_c_store, DATASET)
        assoc.release()
        del DATASET.PerimeterValue # Fix up our changes
        self.scp.stop()

    def test_no_peer_response(self):
        """Test no response from peer"""
        self.scp = DummyStorageSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11112)
        class DummyDIMSE():
            def send_msg(*args, **kwargs): return
            def receive_msg(*args, **kwargs): return None, None

        assoc.dimse = DummyDIMSE()
        if assoc.is_established:
            assoc.send_c_store(DATASET)

        self.assertTrue(assoc.is_aborted)
        
        self.scp.stop()

    def test_invalid_peer_response(self):
        """Test invalid response received from peer"""
        self.scp = DummyStorageSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11112)

        class DummyResponse():
            is_valid_response = False
        
        class DummyDIMSE():
            def send_msg(*args, **kwargs): return
            def receive_msg(*args, **kwargs): return DummyResponse(), None

        assoc.dimse = DummyDIMSE()
        if assoc.is_established:
            assoc.send_c_store(DATASET)

        self.assertTrue(assoc.is_aborted)
        
        self.scp.stop()

    @unittest.skip('Too difficult to test')
    def test_bad_ds(self):
        """Test returns failure status if dataset cant be decoded by SCP"""
        self.scp = DummyStorageSCP()
        self.scp.start()

        ## Need to bypass the standard send_c_store checks
        # Build C-STORE request primitive
        primitive = C_STORE()
        primitive.MessageID = 1
        primitive.AffectedSOPClassUID = DATASET.SOPClassUID
        primitive.AffectedSOPInstanceUID = DATASET.SOPInstanceUID
        primitive.Priorty = 0x0002
        primitive.DataSet = BytesIO(b'\x08\x00\x05\x00\x43\x53\x08\x00\x49\x53\x4f\x54\x45\x53\x54\x00')

        ae = AE(scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)

        # Send C-STORE request primitive to DIMSE and get response
        assoc.dimse.send_msg(primitive, 1)
        rsp, _ = assoc.dimse.receive_msg(True)

        self.assertEqual(rsp.Status, 0xC000)
        assoc.release()
        self.scp.stop()

    def test_bad_priority(self):
        """Test bad priority raises exception"""
        self.scp = DummyStorageSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        self.assertRaises(ValueError, assoc.send_c_store, DATASET, priority=0x0003)
        assoc.release()
        self.scp.stop()

    def test_bad_user_on_c_store(self):
        """Test exception raised in on_c_store returns failure status"""
        self.scp = DummyStorageSCP()
        def on_c_store(ds): raise RuntimeError
        self.scp.ae.on_c_store = on_c_store
        self.scp.start()
        ae = AE(scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_store(DATASET)
        self.assertEqual(result.Status, 0xC101)
        assoc.release()
        self.scp.stop()

    def test_bad_user_on_c_store_return(self):
        """Test SCP exception raised by bad on_c_store return"""
        self.scp = DummyStorageSCP()
        self.scp.status = 'testing'
        self.scp.start()
        ae = AE(scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_store(DATASET)
        self.assertEqual(result.Status, 0xC103)
        assoc.release()
        self.scp.stop()

    def test_bad_user_on_c_store_status(self):
        """Test SCP exception raised by invalid on_c_store status"""
        self.scp = DummyStorageSCP()
        # on_c_store must return Status object with valid value
        self.scp.status = self.scp.bad_status
        self.scp.start()
        ae = AE(scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_store(DATASET)
        self.assertEqual(result.Status, 0xFFFF)
        # on_c_store must return Status object, not int
        self.scp.status = 0xCCCC
        result = assoc.send_c_store(DATASET)
        self.assertEqual(result.Status, 0xCCCC)
        assoc.release()
        self.scp.stop()

    def test_compressed_ds(self):
        """Test SCU when ds is compressed"""
        self.scp = DummyStorageSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[MRImageStorage])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_store(COMP_DATASET)
        self.assertEqual(result.Status, 0x0000)
        assoc.release()
        self.scp.stop()

    def test_ds_no_sop_class(self):
        """Test SCU when the sent dataset has no sop class uid"""
        ds = Dataset()
        ds.PatientName = '*'
        ds.QueryRetrieveLevel = "PATIENT"

        self.scp = DummyStorageSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[CTImageStorage, RTImageStorage])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        self.assertRaises(AttributeError, assoc.send_c_store, ds)
        assoc.release()
        self.scp.stop()

    def test_ds_not_match_agreed_sop(self):
        """Test SCP returns failure status if dataset sop wasnt agreed on"""
        self.scp = DummyStorageSCP()
        self.scp.start()

        ## Need to bypass the standard send_c_store checks
        # Modify the DATASET SOPClassUID
        orig = DATASET.SOPClassUID
        DATASET.SOPClassUID = '1.2.840.10008.5.1.4.1.1.1'

        # Build C-STORE request primitive
        primitive = C_STORE()
        primitive.MessageID = 1
        primitive.AffectedSOPClassUID = DATASET.SOPClassUID
        primitive.AffectedSOPInstanceUID = DATASET.SOPInstanceUID
        primitive.Priorty = 0x0002
        ds = encode(DATASET, True, True)
        primitive.DataSet = BytesIO(ds)

        ae = AE(scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)

        # Send C-STORE request primitive to DIMSE and get response
        assoc.dimse.send_msg(primitive, 1)
        rsp, _ = assoc.dimse.receive_msg(True)

        self.assertEqual(rsp.Status, 0xA900)
        assoc.release()

        DATASET.SOPClassUID = orig
        self.scp.stop()

    def test_good_response(self):
        """Test SCU/SCP successful c-store"""
        self.scp = DummyStorageSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[CTImageStorage, RTImageStorage])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_store(DATASET)
        self.assertEqual(result.Status, 0x0000)
        assoc.release()
        self.scp.stop()

    def test_must_be_associated(self):
        """Test SCU can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyStorageSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        self.assertFalse(assoc.is_established)
        with self.assertRaises(RuntimeError):
            assoc.send_c_store(DATASET)
        self.scp.stop()

    def test_no_abstract_syntax_match(self):
        """Test SCU when no accepted abstract syntax"""
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        self.assertRaises(ValueError, assoc.send_c_store, DATASET)
        assoc.release()
        self.scp.stop()


class TestAssociationSendCFind(unittest.TestCase):
    """Run tests on Assocation send_c_find."""
    def setUp(self):
        """Run prior to each test"""
        self.ds = Dataset()
        self.ds.PatientName = '*'
        self.ds.QueryRetrieveLevel = "PATIENT"

        self.scp = None

    def tearDown(self):
        """Clear any active threads"""
        if self.scp:
            self.scp.abort()

        time.sleep(0.1)

        for thread in threading.enumerate():
            if isinstance(thread, DummyBaseSCP):
                thread.abort()
                thread.stop()

    def test_invalid_response(self):
        """Test invalid response received from peer"""
        self.scp = DummyFindSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)

        class DummyResponse():
            is_valid_response = False
        
        class DummyDIMSE():
            def send_msg(*args, **kwargs): return
            def receive_msg(*args, **kwargs): return DummyResponse(), None

        assoc.dimse = DummyDIMSE()
        self.assertTrue(assoc.is_established)
        for (_, _) in assoc.send_c_find(self.ds, query_model='P'):
            pass

        self.assertTrue(assoc.is_aborted)
        
        self.scp.stop()

    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        scp = DummyFindSCP()
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        self.assertFalse(assoc.is_established)
        with self.assertRaises(RuntimeError):
            next(assoc.send_c_find(self.ds))
        scp.stop()

    def test_no_abstract_syntax_match(self):
        """Test when no accepted abstract syntax"""
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)

        def test():
            next(assoc.send_c_find(self.ds))

        self.assertRaises(ValueError, test)
        assoc.release()
        scp.stop()

    def test_bad_query_model(self):
        """Test when no accepted abstract syntax"""
        scp = DummyFindSCP()
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        with self.assertRaises(ValueError):
            next(assoc.send_c_find(self.ds, query_model='X'))
        assoc.release()
        scp.stop()

    def test_good_query_model(self):
        """Test when no accepted abstract syntax"""
        scp = DummyFindSCP()
        scp.status = scp.success
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind,
                               StudyRootQueryRetrieveInformationModelFind,
                               PatientStudyOnlyQueryRetrieveInformationModelFind,
                               ModalityWorklistInformationFind])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        for (status, ds) in assoc.send_c_find(self.ds, query_model='P'):
            self.assertEqual(status.Status, 0x0000)
        for (status, ds) in assoc.send_c_find(self.ds, query_model='S'):
            self.assertEqual(status.Status, 0x0000)
        for (status, ds) in assoc.send_c_find(self.ds, query_model='O'):
            self.assertEqual(status.Status, 0x0000)
        for (status, ds) in assoc.send_c_find(self.ds, query_model='W'):
            self.assertEqual(status.Status, 0x0000)
        assoc.release()
        scp.stop()

    def test_receive_failure(self):
        """Test receiving a failure response"""
        scp = DummyFindSCP()
        scp.status = scp.out_of_resources
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        for (status, ds) in assoc.send_c_find(self.ds, query_model='P'):
            self.assertEqual(status.Status, 0xA700)
        assoc.release()
        scp.stop()

    def test_receive_pending(self):
        """Test receiving a failure response"""
        scp = DummyFindSCP()
        scp.status = scp.pending
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_find(self.ds, query_model='P')
        (status, ds) = next(result)
        self.assertEqual(status.Status, 0xFF00)
        self.assertTrue('PatientName' in ds)
        (status, ds) = next(result)
        self.assertEqual(status.Status, 0x0000)
        self.assertTrue(ds is None)
        assoc.release()
        scp.stop()

    def test_receive_success(self):
        """Test receiving a failure response"""
        scp = DummyFindSCP()
        scp.status = scp.success
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        for (status, ds) in assoc.send_c_find(self.ds, query_model='P'):
            self.assertEqual(status.Status, 0x0000)
        assoc.release()
        scp.stop()

    def test_receive_cancel(self):
        """Test receiving a failure response"""
        scp = DummyFindSCP()
        scp.status = scp.matching_terminated_cancel
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        for (status, ds) in assoc.send_c_find(self.ds, query_model='P'):
            self.assertEqual(status.Status, 0xFE00)
        assoc.release()
        scp.stop()

    def test_bad_user_on_c_find(self):
        """Test exception raised by bad on_c_find"""
        self.scp = DummyFindSCP()
        def on_c_find(ds): raise RuntimeError
        self.scp.ae.on_c_find = on_c_find
        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        for (status, ds) in assoc.send_c_find(self.ds, query_model='P'):
            self.assertEqual(status.Status, 0xC001)
        assoc.release()
        self.scp.stop()

    def test_bad_user_on_c_find_status(self):
        """Test exception raised by bad on_c_find"""
        self.scp = DummyFindSCP()
        self.scp.status = 0xFFF0
        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        for (status, ds) in assoc.send_c_find(self.ds, query_model='P'):
            self.assertEqual(status.Status, 0xFFF0)
        assoc.release()
        self.scp.stop()

    def test_bad_user_on_c_find_return(self):
        """Test exception raised by bad on_c_find return"""
        self.scp = DummyFindSCP()
        self.scp.status = 'testing'
        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        for (status, ds) in assoc.send_c_find(self.ds, query_model='P'):
            self.assertTrue(status.Status in range(0xC000, 0xD000))
        assoc.release()
        self.scp.stop()

    def test_bad_user_on_c_find_ds(self):
        """Test exception raised by bad on_c_find"""
        self.scp = DummyFindSCP()

        def on_c_find(ds):
            def test(): pass
            yield 0xFF00, test

        self.scp.ae.on_c_find = on_c_find
        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind],
                transfer_syntax=[ExplicitVRLittleEndian])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        for (status, ds) in assoc.send_c_find(self.ds, query_model='P'):
            self.assertTrue(status.Status in range(0xC000, 0xD000))
        assoc.release()
        self.scp.stop()

    def test_ds_not_match_agreed_sop(self):
        """Test returns failure status if dataset sop wasnt agreed on"""
        self.scp = DummyFindSCP()
        self.scp.start()

        ## Need to bypass the standard send_c_find checks
        # Modify the DATASET SOPClassUID
        orig = DATASET.SOPClassUID
        DATASET.SOPClassUID = StudyRootQueryRetrieveInformationModelFind.UID

        # Build C-STORE request primitive
        primitive = C_FIND()
        primitive.MessageID = 1
        primitive.AffectedSOPClassUID = DATASET.SOPClassUID
        primitive.Priorty = 0x0002
        ds = encode(DATASET, True, True)
        primitive.Identifier = BytesIO(ds)

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)

        # Send C-STORE request primitive to DIMSE and get response
        assoc.dimse.send_msg(primitive, 1)
        rsp, _ = assoc.dimse.receive_msg(True)

        self.assertEqual(rsp.Status, 0xA900)
        assoc.release()

        DATASET.SOPClassUID = orig
        self.scp.stop()

    def test_ds_corrupt(self):
        """Test returns failure status if dataset corrupt"""
        self.scp = DummyFindSCP()
        self.scp.start()

        ## Need to bypass the standard send_c_find checks
        # Build C-STORE request primitive
        primitive = C_FIND()
        primitive.MessageID = 1
        primitive.AffectedSOPClassUID = PatientRootQueryRetrieveInformationModelFind.UID
        primitive.Priorty = 0x0002
        primitive.Identifier = BytesIO(b'\x00\x05\x00\x08\x22\x11\x02\x00\x00\x00')

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)

        # Send C-STORE request primitive to DIMSE and get response
        assoc.dimse.send_msg(primitive, 1)
        rsp, _ = assoc.dimse.receive_msg(wait=True)

        self.assertEqual(rsp.Status, 0xC000)
        assoc.release()
        self.scp.stop()


class TestAssociationSendCCancelFind(unittest.TestCase):
    """Run tests on Assocation send_c_cancel_find."""
    def setUp(self):
        """Run prior to each test"""
        self.scp = None

    def tearDown(self):
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
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        self.assertFalse(assoc.is_established)
        with self.assertRaises(RuntimeError):
            assoc.send_c_cancel_find(1)
        self.scp.stop()

    def test_good_send(self):
        """Test send_c_cancel_move"""
        self.scp = DummyFindSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        assoc.send_c_cancel_find(1)
        self.scp.stop()

    def test_bad_send(self):
        """Test send_c_cancel_move"""
        self.scp = DummyFindSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        with self.assertRaises(TypeError):
            assoc.send_c_cancel_find('a')
        assoc.release()
        self.scp.stop()


class TestAssociationSendCGet(unittest.TestCase):
    """Run tests on Assocation send_c_get."""
    def setUp(self):
        """Run prior to each test"""
        self.ds = Dataset()
        #self.ds.SOPClassUID = PatientRootQueryRetrieveInformationModelGet.UID
        self.ds.PatientName = '*'
        self.ds.QueryRetrieveLevel = "PATIENT"

        self.scp = None

    def tearDown(self):
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
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        self.assertFalse(assoc.is_established)
        with self.assertRaises(RuntimeError):
            next(assoc.send_c_get(self.ds))
        self.scp.stop()

    def test_no_abstract_syntax_match(self):
        """Test when no accepted abstract syntax"""
        self.scp = DummyStorageSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        for (status, ds) in assoc.send_c_get(self.ds):
            self.assertEqual(int(status), 0xa900)
        assoc.release()
        self.scp.stop()

    def test_bad_query_model(self):
        """Test bad query model parameter"""
        self.scp = DummyGetSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        with self.assertRaises(ValueError):
            next(assoc.send_c_get(self.ds, query_model='X'))
        assoc.release()
        self.scp.stop()

    def test_good_query_model(self):
        """Test all the query models"""
        self.scp = DummyGetSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               StudyRootQueryRetrieveInformationModelGet,
                               PatientStudyOnlyQueryRetrieveInformationModelGet])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        for (status, ds) in assoc.send_c_get(self.ds, query_model='P'):
            self.assertEqual(int(status), 0x0000)
        for (status, ds) in assoc.send_c_get(self.ds, query_model='S'):
            self.assertEqual(int(status), 0x0000)
        for (status, ds) in assoc.send_c_get(self.ds, query_model='O'):
            self.assertEqual(int(status), 0x0000)
        assoc.release()
        self.scp.stop()

    def test_receive_failure(self):
        """Test receiving a failure response"""
        self.scp = DummyGetSCP()
        self.scp.status = self.scp.out_of_resources_match
        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet])
        def on_c_store(ds): return 0x0000
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        for (status, ds) in assoc.send_c_get(self.ds, query_model='P'):
            self.assertEqual(int(status), 0xA701)
        assoc.release()
        self.scp.stop()

    def test_receive_pending_send_success(self):
        """Test receiving a pending response and sending success"""
        self.scp = DummyGetSCP()
        self.scp.status = self.scp.pending
        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage],
                scp_sop_class=[CTImageStorage])
        def on_c_store(ds): return 0x0000
        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_get(self.ds, query_model='P')
        # We have 2 status, ds and 1 success
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xFF00)
        self.assertTrue('PatientName' in ds)
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xFF00)
        self.assertTrue('PatientName' in ds)
        (status, ds) = next(result)
        self.assertEqual(int(status), 0x0000)
        self.assertTrue(ds is None)
        assoc.release()
        self.scp.stop()

    def test_receive_success(self):
        """Test receiving a success response"""
        self.scp = DummyGetSCP()
        self.scp.status = self.scp.success
        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        for (status, ds) in assoc.send_c_get(self.ds, query_model='P'):
            self.assertEqual(int(status), 0x0000)
            self.assertTrue(ds is None)
        assoc.release()
        self.scp.stop()

    def test_receive_pending_send_failure(self):
        """Test receiving a pending response and sending a failure"""
        self.scp = DummyGetSCP()
        self.scp.status = self.scp.pending
        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage],
                scp_sop_class=[CTImageStorage])
        def on_c_store(ds): return 0xA700
        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_get(self.ds, query_model='P')
        # We have 2 status, ds and 1 success
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xFF00)
        self.assertTrue('PatientName' in ds)
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xFF00)
        self.assertTrue('PatientName' in ds)
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xB000)
        self.assertTrue(ds is None)
        assoc.release()
        self.scp.stop()

    def test_receive_pending_send_warning(self):
        """Test receiving a pending response and sending a warning"""
        self.scp = DummyGetSCP()
        self.scp.status = self.scp.pending
        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage],
                scp_sop_class=[CTImageStorage])
        def on_c_store(ds): return 0xB007
        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_get(self.ds, query_model='P')
        # We have 2 status, ds and 1 success
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xFF00)
        self.assertTrue('PatientName' in ds)
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xFF00)
        self.assertTrue('PatientName' in ds)
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xB000)
        self.assertTrue(ds is None)
        assoc.release()
        self.scp.stop()

    def test_receive_cancel(self):
        """Test receiving a cancel response"""
        self.scp = DummyGetSCP()
        self.scp.status = self.scp.cancel_status
        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        for (status, ds) in assoc.send_c_get(self.ds, query_model='P'):
            self.assertEqual(int(status), 0xFE00)
        assoc.release()
        self.scp.stop()

    def test_receive_warning(self):
        """Test receiving a warning response"""
        self.scp = DummyGetSCP()
        self.scp.status = self.scp.warning
        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage],
                scp_sop_class=[CTImageStorage])
        def on_c_store(ds): return 0xB007
        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        # We have 2 status, ds and 1 success
        result = assoc.send_c_get(self.ds, query_model='P')
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xff00)
        self.assertTrue('PatientName' in ds)
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xff00)
        self.assertTrue('PatientName' in ds)
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xb000)
        self.assertTrue(ds is None)
        assoc.release()
        self.scp.stop()

    def test_bad_user_on_c_get(self):
        """Test bad user on_c_get causes a failure response"""
        self.scp = DummyGetSCP()
        def on_c_get(ds): raise RuntimeError
        self.scp.ae.on_c_get = on_c_get
        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        for (status, ds) in assoc.send_c_get(self.ds, query_model='P'):
            self.assertEqual(int(status), 0xC000)
        assoc.release()
        self.scp.stop()

    def test_bad_user_on_c_get_yield(self):
        """Test receiving a bad yield"""
        self.scp = DummyGetSCP()
        def on_c_get(ds): yield 'ats', None
        self.scp.ae.on_c_get = on_c_get
        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        for (status, ds) in assoc.send_c_get(self.ds, query_model='P'):
            self.assertEqual(int(status), 0xC000)
        assoc.release()
        self.scp.stop()

    def test_bad_user_on_c_get_status_value(self):
        """Test receiving a bad yield status int"""
        self.scp = DummyGetSCP()
        def on_c_get(ds):
            yield 1
            yield 0x0111, None
        self.scp.ae.on_c_get = on_c_get
        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        for (status, ds) in assoc.send_c_get(self.ds, query_model='P'):
            self.assertEqual(int(status), 0xC000)
        assoc.release()
        self.scp.stop()

    def test_bad_user_on_c_get_status_type(self):
        """Test receiving a bad yield status type"""
        self.scp = DummyGetSCP()
        def on_c_get(ds):
            yield 1
            yield 'test', None
        self.scp.ae.on_c_get = on_c_get
        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        for (status, ds) in assoc.send_c_get(self.ds, query_model='P'):
            self.assertEqual(int(status), 0xC000)
        assoc.release()
        self.scp.stop()

    def test_bad_user_on_c_get_ds(self):
        """Test exception raised by bad on_c_get ds"""
        self.scp = DummyGetSCP()
        self.scp.status = self.scp.pending

        def on_c_store(ds):
            return 0x0000

        def on_c_get(ds):
            def test(): pass
            yield 1
            yield 0xFF00, test

        self.scp.ae.on_c_get = on_c_get
        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage],
                scp_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage],
                transfer_syntax=[ExplicitVRLittleEndian])
        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_get(self.ds, query_model='P')
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xff00)
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xb000)
        assoc.release()
        self.scp.stop()

    def test_good_send(self):
        """Test good send"""
        self.scp = DummyGetSCP()
        self.scp.status = self.scp.pending

        def on_c_store(ds):
            self.assertTrue('PatientID' in ds)
            return 0x0000

        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage],
                scp_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               CTImageStorage],
                transfer_syntax=[ExplicitVRLittleEndian])
        ae.on_c_store = on_c_store
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_get(self.ds, query_model='P')
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xff00)
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xff00)
        (status, ds) = next(result)
        self.assertEqual(int(status), 0x0000)
        assoc.release()
        self.scp.stop()

    def test_ds_not_match_agreed_sop(self):
        """Test returns failure status if dataset sop wasnt agreed on"""
        self.scp = DummyGetSCP()
        self.scp.start()

        ## Need to bypass the standard send_c_find checks
        primitive = C_GET()
        primitive.MessageID = 1
        primitive.AffectedSOPClassUID = StudyRootQueryRetrieveInformationModelGet.UID
        primitive.Priorty = 0x0002
        primitive.Identifier = BytesIO(encode(self.ds, True, True))

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet],
                transfer_syntax=[ImplicitVRLittleEndian])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)

        # Send C-STORE request primitive to DIMSE and get response
        assoc.dimse.send_msg(primitive, 1)
        while True:
            time.sleep(0.001)
            rsp, _ = assoc.dimse.receive_msg(False)

            if rsp.__class__ == C_GET:
                self.assertEqual(rsp.Status, 0xA900)
                assoc.release()
                break

        self.scp.stop()

    def test_ds_bad(self):
        """Test the user on_c_get raises when ds is bad"""
        self.scp = DummyGetSCP()
        self.scp.status = self.scp.pending
        self.scp.start()

        ## Need to bypass the standard send_c_find checks
        primitive = C_GET()
        primitive.MessageID = 1
        primitive.AffectedSOPClassUID = PatientRootQueryRetrieveInformationModelGet.UID
        primitive.Priorty = 0x0002
        primitive.Identifier = BytesIO(b'\x00\x05\x00\x08\x22\x11\x02\x00\x00\x00')

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet],
                transfer_syntax=[ImplicitVRLittleEndian])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)

        # Send C-GET request primitive to DIMSE and get response
        assoc.dimse.send_msg(primitive, 1)
        while True:
            time.sleep(0.001)
            rsp, _ = assoc.dimse.receive_msg(False)

            if rsp.__class__ == C_GET:
                self.assertEqual(rsp.Status, 0xc000)
                assoc.release()
                break

        self.scp.stop()


class TestAssociationSendCCancelGet(unittest.TestCase):
    """Run tests on Assocation send_c_cancel_find."""
    def setUp(self):
        """Run prior to each test"""
        self.scp = None

    def tearDown(self):
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
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        self.assertFalse(assoc.is_established)
        with self.assertRaises(RuntimeError):
            assoc.send_c_cancel_get(1)
        self.scp.stop()


class TestAssociationSendCMove(unittest.TestCase):
    """Run tests on Assocation send_c_move."""
    def setUp(self):
        """Run prior to each test"""
        self.ds = Dataset()
        self.ds.PatientName = '*'
        self.ds.QueryRetrieveLevel = "PATIENT"

        self.scp = None
        self.scp2 = None

    def tearDown(self):
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
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        self.assertFalse(assoc.is_established)
        with self.assertRaises(RuntimeError):
            next(assoc.send_c_move(self.ds, b'TESTMOVE'))
        self.scp.stop()

    def test_no_abstract_syntax_match(self):
        """Test when no accepted abstract syntax"""
        self.scp = DummyStorageSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        for (status, ds) in assoc.send_c_move(DATASET, b'TESTMOVE'):
            self.assertEqual(int(status), 0xa900)
        assoc.release()
        self.scp.stop()

    def test_bad_query_model(self):
        """Test bad query model parameter"""
        self.scp = DummyMoveSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        with self.assertRaises(ValueError):
            next(assoc.send_c_move(self.ds, b'TESTMOVE', query_model='X'))
        assoc.release()
        self.scp.stop()

    def test_good_query_model(self):
        """Test all the query models"""
        self.scp2 = DummyStorageSCP(11113)
        self.scp2.start()

        self.scp = DummyMoveSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               StudyRootQueryRetrieveInformationModelMove,
                               PatientStudyOnlyQueryRetrieveInformationModelMove])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_move(self.ds, b'TESTMOVE', query_model='P')
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xFF00)
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xFF00)
        (status, ds) = next(result)
        self.assertEqual(int(status), 0x0000)

        result = assoc.send_c_move(self.ds, b'TESTMOVE', query_model='S')
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xFF00)
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xFF00)
        (status, ds) = next(result)
        self.assertEqual(int(status), 0x0000)

        result = assoc.send_c_move(self.ds, b'TESTMOVE', query_model='O')
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xFF00)
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xFF00)
        (status, ds) = next(result)
        self.assertEqual(int(status), 0x0000)
        assoc.release()
        self.scp.stop()

        self.scp2.stop()

    def test_move_destination_no_assoc(self):
        """Test move destination failed to assoc"""
        self.scp = DummyMoveSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               StudyRootQueryRetrieveInformationModelMove,
                               PatientStudyOnlyQueryRetrieveInformationModelMove])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        for (status, ds) in assoc.send_c_move(self.ds, b'TESTMOVE', query_model='P'):
            self.assertEqual(int(status), 0xa702)
        assoc.release()
        self.scp.stop()

    def test_move_destination_unknown(self):
        """Test unknown move destination"""
        self.scp = DummyMoveSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               StudyRootQueryRetrieveInformationModelMove,
                               PatientStudyOnlyQueryRetrieveInformationModelMove])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        for (status, ds) in assoc.send_c_move(self.ds, b'UNKNOWN', query_model='P'):
            self.assertEqual(int(status), 0xa801)
        assoc.release()
        self.scp.stop()

    def test_move_destination_failed_store(self):
        """Test the destination AE returning failed status"""
        self.scp2 = DummyStorageSCP(11113)
        self.scp2.status = self.scp2.out_of_resources
        self.scp2.start()

        self.scp = DummyMoveSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               StudyRootQueryRetrieveInformationModelMove,
                               PatientStudyOnlyQueryRetrieveInformationModelMove])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_move(self.ds, b'TESTMOVE', query_model='P')
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xFF00)
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xFF00)
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xB000)

        assoc.release()
        self.scp.stop()

        self.scp2.stop()

    def test_move_destination_warning_store(self):
        """Test the destination AE returning warning status"""
        self.scp2 = DummyStorageSCP(11113)
        self.scp2.status = self.scp2.coercion_of_elements
        self.scp2.start()

        self.scp = DummyMoveSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               StudyRootQueryRetrieveInformationModelMove,
                               PatientStudyOnlyQueryRetrieveInformationModelMove])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_move(self.ds, b'TESTMOVE', query_model='P')
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xFF00)
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xFF00)
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xB000)

        assoc.release()
        self.scp.stop()

        self.scp2.stop()

    def test_user_failed(self):
        """Test the user on_c_move returning failure status"""
        self.scp2 = DummyStorageSCP(11113)
        self.scp.start()

        self.scp = DummyMoveSCP()
        self.scp.status = self.scp.unable_to_process
        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               StudyRootQueryRetrieveInformationModelMove,
                               PatientStudyOnlyQueryRetrieveInformationModelMove])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_move(self.ds, b'TESTMOVE', query_model='P')
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xC000)

        assoc.release()
        self.scp.stop()

        self.scp.stop()

    def test_user_warning(self):
        """Test the user on_c_move returning warning status"""
        self.scp2 = DummyStorageSCP(11113)
        self.scp2.start()

        self.scp = DummyMoveSCP()
        self.scp.status = self.scp.warning
        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               StudyRootQueryRetrieveInformationModelMove,
                               PatientStudyOnlyQueryRetrieveInformationModelMove])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_move(self.ds, b'TESTMOVE', query_model='P')
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xB000)

        assoc.release()
        self.scp.stop()

        self.scp2.stop()

    def test_user_cancel(self):
        """Test the user on_c_move returning cancel status"""
        self.scp2 = DummyStorageSCP(11113)
        self.scp2.start()

        self.scp = DummyMoveSCP()
        self.scp.status = self.scp.cancel_status
        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               StudyRootQueryRetrieveInformationModelMove,
                               PatientStudyOnlyQueryRetrieveInformationModelMove])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_move(self.ds, b'TESTMOVE', query_model='P')
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xFE00)

        assoc.release()
        self.scp.stop()

        self.scp2.stop()

    def test_user_success(self):
        """Test the user on_c_move returning success status"""
        self.scp2 = DummyStorageSCP(11113)
        self.scp2.start()

        self.scp = DummyMoveSCP()
        self.scp.status = scp.success
        self.scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               StudyRootQueryRetrieveInformationModelMove,
                               PatientStudyOnlyQueryRetrieveInformationModelMove])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_move(self.ds, b'TESTMOVE', query_model='P')
        (status, ds) = next(result)
        self.assertEqual(int(status), 0x0000)

        assoc.release()
        self.scp.stop()

        self.scp2.stop()

    def test_bad_user_on_c_move(self):
        """Test bad user on_c_move causes a failure response"""
        self.scp2 = DummyStorageSCP(11113)
        self.scp2.start()

        self.scp = DummyMoveSCP()
        def on_c_move(ds, aet): raise RuntimeError
        self.scp.ae.on_c_move = on_c_move
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_move(self.ds, b'TESTMOVE', query_model='P')
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xC000)

        assoc.release()
        self.scp.stop()
        self.scp2.stop()

    def test_bad_user_on_c_move_first_yield(self):
        """Test exception raised by bad on_c_move first yield"""
        self.scp2 = DummyStorageSCP(11113)
        self.scp2.start()

        self.scp = DummyMoveSCP()
        def on_c_move(ds, aet): yield None
        self.scp.ae.on_c_move = on_c_move
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_move(self.ds, b'TESTMOVE', query_model='P')
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xC000)

        assoc.release()
        self.scp.stop()
        self.scp2.stop()

    def test_bad_user_on_c_move_second_yield_missing(self):
        """Test exception raised by bad on_c_move second yield missing"""
        self.scp2 = DummyStorageSCP(11113)
        self.scp2.start()

        self.scp = DummyMoveSCP()
        def on_c_move(ds, aet): yield 1
        self.scp.ae.on_c_move = on_c_move
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_move(self.ds, b'TESTMOVE', query_model='P')
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xC000)

        assoc.release()
        self.scp.stop()
        self.scp2.stop()

    def test_bad_user_on_c_move_second_yield(self):
        """Test exception raised by bad on_c_move second yield"""
        self.scp2 = DummyStorageSCP(11113)
        self.scp2.start()

        self.scp = DummyMoveSCP()
        def on_c_move(ds, aet): yield 1; yield 1234, 'test'
        self.scp.ae.on_c_move = on_c_move
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_move(self.ds, b'TESTMOVE', query_model='P')
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xA801)

        assoc.release()
        self.scp.stop()
        self.scp2.stop()

    def test_bad_user_on_c_move_nth_yield(self):
        """Test exception raised by bad on_c_move third+ yield"""
        self.scp2 = DummyStorageSCP(11113)
        self.scp2.start()

        self.scp = DummyMoveSCP()
        def on_c_move(ds, aet):
            yield 1
            yield 'localhost', 11113
            yield 'test', DATASET
        self.scp.ae.on_c_move = on_c_move
        self.scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_move(self.ds, b'TESTMOVE', query_model='P')
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xc000)

        assoc.release()
        self.scp.stop()
        self.scp2.stop()

    def test_ds_not_match_agreed_sop(self):
        """Test returns failure status if dataset sop wasnt agreed on"""
        self.scp = DummyMoveSCP()
        self.scp.start()

        ## Need to bypass the standard send_c_find checks
        primitive = C_MOVE()
        primitive.MessageID = 1
        primitive.AffectedSOPClassUID = StudyRootQueryRetrieveInformationModelMove.UID
        primitive.MoveDestination = b'TESTMOVE'
        primitive.Priorty = 0x0002
        primitive.Identifier = BytesIO(encode(self.ds, True, True))

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove],
                transfer_syntax=[ImplicitVRLittleEndian])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)

        # Send C-STORE request primitive to DIMSE and get response
        assoc.dimse.send_msg(primitive, 1)
        while True:
            time.sleep(0.001)
            rsp, _ = assoc.dimse.receive_msg(False)

            if rsp.__class__ == C_MOVE:
                self.assertEqual(rsp.Status, 0xA900)
                assoc.release()
                break

        self.scp.stop()

    def test_ds_bad(self):
        """Test the user on_c_move raises when ds is bad"""
        self.scp2 = DummyStorageSCP(11113)
        self.scp2.start()

        def test(): pass

        def on_c_move(ds, move_aet):
            yield 1
            yield 'localhost', 11113
            yield 0xff00, test

        self.scp = DummyMoveSCP()
        self.scp.ae.on_c_move = on_c_move
        self.scp.status = self.scp.pending
        self.scp.start()

        ## Need to bypass the standard send_c_find checks
        primitive = C_MOVE()
        primitive.MessageID = 1
        primitive.AffectedSOPClassUID = PatientRootQueryRetrieveInformationModelMove.UID
        primitive.MoveDestination = b'TESTMOVE'
        primitive.Priorty = 0x0002
        primitive.Identifier = BytesIO(b'\x00\x05\x00\x08\x22\x11\x02\x00\x00\x00')

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove],
                transfer_syntax=[ImplicitVRLittleEndian])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)

        # Send C-STORE request primitive to DIMSE and get response
        assoc.dimse.send_msg(primitive, 1)
        while True:
            time.sleep(0.001)
            rsp, _ = assoc.dimse.receive_msg(False)

            if rsp.__class__ == C_MOVE:
                self.assertEqual(rsp.Status, 0xc000)
                assoc.release()
                break

        self.scp.stop()

        self.scp2.stop()


class TestAssociationSendCCancelMove(unittest.TestCase):
    """Run tests on Assocation send_c_cancel_move."""
    def setUp(self):
        self.scp = None

    def tearDown(self):
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
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        self.assertFalse(assoc.is_established)
        with self.assertRaises(RuntimeError):
            assoc.send_c_cancel_move(1)
        self.scp.stop()


class TestAssociationSendNEventReport(unittest.TestCase):
    """Run tests on Assocation send_n_event_report."""
    def setUp(self):
        self.scp = None

    def tearDown(self):
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
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        self.assertFalse(assoc.is_established)
        with self.assertRaises(RuntimeError):
            assoc.send_n_event_report()
        self.scp.stop()

    def test_not_implemented(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        with self.assertRaises(NotImplementedError):
            assoc.send_n_event_report()
        assoc.release()
        self.scp.stop()


class TestAssociationSendNGet(unittest.TestCase):
    """Run tests on Assocation send_n_get."""
    def setUp(self):
        self.scp = None

    def tearDown(self):
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
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        self.assertFalse(assoc.is_established)
        with self.assertRaises(RuntimeError):
            assoc.send_n_get()
        self.scp.stop()

    def test_not_implemented(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        with self.assertRaises(NotImplementedError):
            assoc.send_n_get()
        assoc.release()
        self.scp.stop()


class TestAssociationSendNSet(unittest.TestCase):
    """Run tests on Assocation send_n_set."""
    def setUp(self):
        self.scp = None

    def tearDown(self):
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
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        self.assertFalse(assoc.is_established)
        with self.assertRaises(RuntimeError):
            assoc.send_n_set()
        self.scp.stop()

    def test_not_implemented(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        with self.assertRaises(NotImplementedError):
            assoc.send_n_set()
        assoc.release()
        self.scp.stop()


class TestAssociationSendNAction(unittest.TestCase):
    """Run tests on Assocation send_n_action."""
    def setUp(self):
        self.scp = None

    def tearDown(self):
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
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        self.assertFalse(assoc.is_established)
        with self.assertRaises(RuntimeError):
            assoc.send_n_action()
        self.scp.stop()

    def test_not_implemented(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        with self.assertRaises(NotImplementedError):
            assoc.send_n_action()
        assoc.release()
        self.scp.stop()


class TestAssociationSendNCreate(unittest.TestCase):
    """Run tests on Assocation send_n_create."""
    def setUp(self):
        self.scp = None

    def tearDown(self):
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
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        self.assertFalse(assoc.is_established)
        with self.assertRaises(RuntimeError):
            assoc.send_n_create()
        self.scp.stop()

    def test_not_implemented(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        with self.assertRaises(NotImplementedError):
            assoc.send_n_create()
        assoc.release()
        self.scp.stop()


class TestAssociationSendNDelete(unittest.TestCase):
    """Run tests on Assocation send_n_delete."""
    def setUp(self):
        self.scp = None

    def tearDown(self):
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
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        self.assertFalse(assoc.is_established)
        with self.assertRaises(RuntimeError):
            assoc.send_n_delete()
        self.scp.stop()

    def test_not_implemented(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        with self.assertRaises(NotImplementedError):
            assoc.send_n_delete()
        assoc.release()
        self.scp.stop()


class TestAssociationCallbacks(unittest.TestCase):
    """Run tests on Assocation callbacks."""
    def setUp(self):
        self.scp = None

    def tearDown(self):
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
        assoc = ae.associate('localhost', 11112)
        assoc.debug_association_requested(None)
        assoc.release()
        self.scp.stop()


if __name__ == "__main__":
    unittest.main()
