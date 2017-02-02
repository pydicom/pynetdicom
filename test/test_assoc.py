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
from unittest.mock import patch

from pydicom import read_file
from pydicom.dataset import Dataset
from pydicom.uid import UID, ImplicitVRLittleEndian, ExplicitVRLittleEndian

from dummy_c_scp import DummyVerificationSCP, DummyStorageSCP, \
                        DummyFindSCP, DummyGetSCP, DummyMoveSCP
from pynetdicom3 import AE, VerificationSOPClass
from pynetdicom3.association import Association
from pynetdicom3.dimse_primitives import C_STORE, C_FIND, C_GET, C_MOVE
from pynetdicom3.dsutils import encode, decode
from pynetdicom3.pdu_primitives import UserIdentityNegotiation, \
                                   SOPClassExtendedNegotiation, \
                                   SOPClassCommonExtendedNegotiation
from pynetdicom3.sop_class import CTImageStorage, MRImageStorage, Status, \
                                 RTImageStorage, \
                                 PatientRootQueryRetrieveInformationModelFind, \
                                 StudyRootQueryRetrieveInformationModelFind, \
                                 ModalityWorklistInformationFind, \
                                 PatientStudyOnlyQueryRetrieveInformationModelFind, \
                                 PatientRootQueryRetrieveInformationModelGet, \
                                 PatientStudyOnlyQueryRetrieveInformationModelGet, \
                                 StudyRootQueryRetrieveInformationModelGet, \
                                 PatientRootQueryRetrieveInformationModelMove, \
                                 PatientStudyOnlyQueryRetrieveInformationModelMove, \
                                 StudyRootQueryRetrieveInformationModelMove

LOGGER = logging.getLogger('pynetdicom3')
LOGGER.setLevel(logging.CRITICAL)

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
    
    def test_require_called_aet(self):
        """SCP requires matching called AET"""
        scp = DummyVerificationSCP()
        scp.ae.require_calling_aet = b'TESTSCP'
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertFalse(assoc.is_established)
        self.assertTrue(assoc.is_rejected)
        scp.stop()

class TestAssociationSendCEcho(unittest.TestCase):
    """Run tests on Assocation send_c_echo."""
    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        self.assertFalse(assoc.is_established)
        with self.assertRaises(RuntimeError):
            assoc.send_c_echo()
        scp.stop()

    def test_no_abstract_syntax_match(self):
        """Test when no accepted abstract syntax"""
        scp = DummyStorageSCP()
        scp.start()
        ae = AE(scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_echo()
        self.assertTrue(result is None)
        assoc.release()
        scp.stop()

    def test_good_response(self):
        """Test successful c-echo"""
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_echo()
        self.assertEqual(int(result), 0x0000)
        assoc.release()
        scp.stop()

    def test_bad_user_on_c_echo(self):
        """Test no exception raised in on_c_echo"""
        scp = DummyVerificationSCP()
        def on_c_echo(): raise RuntimeError
        scp.ae.on_c_echo = on_c_echo
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        assoc.send_c_echo()
        assoc.release()
        scp.stop()


class TestAssociationSendCStore(unittest.TestCase):
    """Run tests on Assocation send_c_store."""
    def test_bad_dataset(self):
        """Test failure if unable to encode dataset"""
        scp = DummyStorageSCP()
        scp.start()
        ae = AE(scu_sop_class=[CTImageStorage],
                transfer_syntax=[ExplicitVRLittleEndian])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        DATASET.PerimeterValue = b'\x00\x01'
        result = assoc.send_c_store(DATASET)
        self.assertEqual(int(result), 0xC000)
        assoc.release()
        del DATASET.PerimeterValue # Fix up our changes
        scp.stop()

    @unittest.skip # Very difficult to test
    def test_bad_ds(self):
        """Test returns failure status if dataset cant be decoded by SCP"""
        scp = DummyStorageSCP()
        scp.start()

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
        rsp, _ = assoc.dimse.receive_msg(True, assoc.dimse_timeout)

        self.assertEqual(rsp.Status, 0xC000)
        assoc.release()
        scp.stop()

    def test_bad_priority(self):
        """Test bad priority gets reset"""
        scp = DummyStorageSCP()
        scp.start()
        ae = AE(scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_store(DATASET, priority=0x0003)
        self.assertEqual(int(result), 0x0000)
        assoc.release()
        scp.stop()

    def test_bad_user_on_c_store(self):
        """Test exception raised in on_c_store returns failure status"""
        scp = DummyStorageSCP()
        def on_c_store(ds): raise RuntimeError
        scp.ae.on_c_store = on_c_store
        scp.start()
        ae = AE(scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        response = assoc.send_c_store(DATASET)
        self.assertEqual(int(response), 0xc000)
        assoc.release()
        scp.stop()

    def test_bad_user_on_c_store_return(self):
        """Test exception raised by bad on_c_store return"""
        scp = DummyStorageSCP()
        scp.status = 'testing'
        scp.start()
        ae = AE(scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        status = assoc.send_c_store(DATASET)
        self.assertEqual(int(status), 0xC000)
        assoc.release()
        scp.stop()

    def test_bad_user_on_c_store_status(self):
        """Test exception raised by invalid on_c_store status"""
        scp = DummyStorageSCP()
        scp.status = scp.bad_status
        scp.start()
        ae = AE(scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        status = assoc.send_c_store(DATASET)
        self.assertEqual(int(status), 0xC000)
        scp.status = 0x0111
        status = assoc.send_c_store(DATASET)
        self.assertEqual(int(status), 0xC000)
        assoc.release()
        scp.stop()

    def test_compressed_ds(self):
        """Test when ds is compressed"""
        scp = DummyStorageSCP()
        scp.start()
        ae = AE(scu_sop_class=[MRImageStorage])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_store(COMP_DATASET)
        self.assertEqual(int(result), 0x0000)
        assoc.release()
        scp.stop()

    def test_ds_no_sop_class(self):
        """Test when the sent dataset has no sop class uid"""
        ds = Dataset()
        ds.PatientName = '*'
        ds.QueryRetrieveLevel = "PATIENT"

        scp = DummyStorageSCP()
        scp.start()
        ae = AE(scu_sop_class=[CTImageStorage, RTImageStorage])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_store(ds)
        self.assertEqual(int(result), 0xC000)
        assoc.release()
        scp.stop()

    def test_ds_not_match_agreed_sop(self):
        """Test returns failure status if dataset sop wasnt agreed on"""
        scp = DummyStorageSCP()
        scp.start()

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
        rsp, _ = assoc.dimse.receive_msg(True, assoc.dimse_timeout)

        self.assertEqual(rsp.Status, 0xA900)
        assoc.release()

        DATASET.SOPClassUID = orig
        scp.stop()

    def test_good_response(self):
        """Test successful c-store"""
        scp = DummyStorageSCP()
        scp.start()
        ae = AE(scu_sop_class=[CTImageStorage, RTImageStorage])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_store(DATASET)
        self.assertEqual(int(result), 0x0000)
        assoc.release()
        scp.stop()

    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        scp = DummyStorageSCP()
        scp.start()
        ae = AE(scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        self.assertFalse(assoc.is_established)
        with self.assertRaises(RuntimeError):
            assoc.send_c_store(DATASET)
        scp.stop()

    def test_no_abstract_syntax_match(self):
        """Test when no accepted abstract syntax"""
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_store(DATASET)
        self.assertEqual(int(result), 0xc000)
        assoc.release()
        scp.stop()


class TestAssociationSendCFind(unittest.TestCase):
    """Run tests on Assocation send_c_find."""
    def setUp(self):
        """Run prior to each test"""
        self.ds = Dataset()
        self.ds.PatientName = '*'
        self.ds.QueryRetrieveLevel = "PATIENT"

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
        for (status, ds) in assoc.send_c_find(self.ds):
            self.assertEqual(int(status), 0xa900)
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
            self.assertEqual(int(status), 0x0000)
        for (status, ds) in assoc.send_c_find(self.ds, query_model='S'):
            self.assertEqual(int(status), 0x0000)
        for (status, ds) in assoc.send_c_find(self.ds, query_model='O'):
            self.assertEqual(int(status), 0x0000)
        for (status, ds) in assoc.send_c_find(self.ds, query_model='W'):
            self.assertEqual(int(status), 0x0000)
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
            self.assertEqual(int(status), 0xA700)
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
        self.assertEqual(int(status), 0xFF00)
        self.assertTrue('PatientName' in ds)
        (status, ds) = next(result)
        self.assertEqual(int(status), 0x0000)
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
            self.assertEqual(int(status), 0x0000)
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
            self.assertEqual(int(status), 0xFE00)
        assoc.release()
        scp.stop()

    def test_bad_user_on_c_find(self):
        """Test exception raised by bad on_c_find"""
        scp = DummyFindSCP()
        def on_c_find(ds): raise RuntimeError
        scp.ae.on_c_find = on_c_find
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        for (status, ds) in assoc.send_c_find(self.ds, query_model='P'):
            self.assertEqual(int(status), 0xC000)
        assoc.release()
        scp.stop()

    def test_bad_user_on_c_find_status(self):
        """Test exception raised by bad on_c_find"""
        scp = DummyFindSCP()
        scp.status = scp.bad_status
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        for (status, ds) in assoc.send_c_find(self.ds, query_model='P'):
            self.assertEqual(int(status), 0xC000)
        assoc.release()
        scp.stop()

    def test_bad_user_on_c_find_return(self):
        """Test exception raised by bad on_c_find return"""
        scp = DummyFindSCP()
        scp.status = 'testing'
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        for (status, ds) in assoc.send_c_find(self.ds, query_model='P'):
            self.assertEqual(int(status), 0xC000)
        assoc.release()
        scp.stop()

    def test_bad_user_on_c_find_ds(self):
        """Test exception raised by bad on_c_find"""
        scp = DummyFindSCP()

        def on_c_find(ds):
            def test(): pass
            yield 0xFF00, test

        scp.ae.on_c_find = on_c_find
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind],
                transfer_syntax=[ExplicitVRLittleEndian])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        for (status, ds) in assoc.send_c_find(self.ds, query_model='P'):
            self.assertEqual(int(status), 0xC000)
        assoc.release()
        scp.stop()

    def test_ds_not_match_agreed_sop(self):
        """Test returns failure status if dataset sop wasnt agreed on"""
        scp = DummyFindSCP()
        scp.start()

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
        rsp, _ = assoc.dimse.receive_msg(True, assoc.dimse_timeout)

        self.assertEqual(rsp.Status, 0xA900)
        assoc.release()

        DATASET.SOPClassUID = orig
        scp.stop()

    def test_ds_corrupt(self):
        """Test returns failure status if dataset corrupt"""
        scp = DummyFindSCP()
        scp.start()

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
        rsp, _ = assoc.dimse.receive_msg(True, assoc.dimse_timeout)

        self.assertEqual(rsp.Status, 0xC000)
        assoc.release()
        scp.stop()


class TestAssociationSendCCancelFind(unittest.TestCase):
    """Run tests on Assocation send_c_cancel_find."""
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
            assoc.send_c_cancel_find(1)
        scp.stop()

    def test_good_send(self):
        """Test send_c_cancel_move"""
        scp = DummyFindSCP()
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        assoc.send_c_cancel_find(1)
        scp.stop()
        
    def test_bad_send(self):
        """Test send_c_cancel_move"""
        scp = DummyFindSCP()
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        with self.assertRaises(TypeError):
            assoc.send_c_cancel_find('a')
        assoc.release()
        scp.stop()
        


class TestAssociationSendCGet(unittest.TestCase):
    """Run tests on Assocation send_c_get."""
    def setUp(self):
        """Run prior to each test"""
        self.ds = Dataset()
        #self.ds.SOPClassUID = PatientRootQueryRetrieveInformationModelGet.UID
        self.ds.PatientName = '*'
        self.ds.QueryRetrieveLevel = "PATIENT"

    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        scp = DummyGetSCP()
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet])
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        self.assertFalse(assoc.is_established)
        with self.assertRaises(RuntimeError):
            next(assoc.send_c_get(self.ds))
        scp.stop()

    def test_no_abstract_syntax_match(self):
        """Test when no accepted abstract syntax"""
        scp = DummyStorageSCP()
        scp.start()
        ae = AE(scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        for (status, ds) in assoc.send_c_get(self.ds):
            self.assertEqual(int(status), 0xa900)
        assoc.release()
        scp.stop()

    def test_bad_query_model(self):
        """Test bad query model parameter"""
        scp = DummyGetSCP()
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        with self.assertRaises(ValueError):
            next(assoc.send_c_get(self.ds, query_model='X'))
        assoc.release()
        scp.stop()

    def test_good_query_model(self):
        """Test all the query models"""
        scp = DummyGetSCP()
        scp.start()
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
        scp.stop()

    def test_receive_failure(self):
        """Test receiving a failure response"""
        scp = DummyGetSCP()
        scp.status = scp.out_of_resources_match
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet])
        def on_c_store(ds): return 0x0000
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        for (status, ds) in assoc.send_c_get(self.ds, query_model='P'):
            self.assertEqual(int(status), 0xA701)
        assoc.release()
        scp.stop()

    def test_receive_pending_send_success(self):
        """Test receiving a pending response and sending success"""
        scp = DummyGetSCP()
        scp.status = scp.pending
        scp.start()
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
        scp.stop()

    def test_receive_success(self):
        """Test receiving a success response"""
        scp = DummyGetSCP()
        scp.status = scp.success
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        for (status, ds) in assoc.send_c_get(self.ds, query_model='P'):
            self.assertEqual(int(status), 0x0000)
            self.assertTrue(ds is None)
        assoc.release()
        scp.stop()

    def test_receive_pending_send_failure(self):
        """Test receiving a pending response and sending a failure"""
        scp = DummyGetSCP()
        scp.status = scp.pending
        scp.start()
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
        scp.stop()

    def test_receive_pending_send_warning(self):
        """Test receiving a pending response and sending a warning"""
        scp = DummyGetSCP()
        scp.status = scp.pending
        scp.start()
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
        scp.stop()

    def test_receive_cancel(self):
        """Test receiving a cancel response"""
        scp = DummyGetSCP()
        scp.status = scp.cancel_status
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        for (status, ds) in assoc.send_c_get(self.ds, query_model='P'):
            self.assertEqual(int(status), 0xFE00)
        assoc.release()
        scp.stop()

    def test_receive_warning(self):
        """Test receiving a warning response"""
        scp = DummyGetSCP()
        scp.status = scp.warning
        scp.start()
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
        scp.stop()

    def test_bad_user_on_c_get(self):
        """Test bad user on_c_get causes a failure response"""
        scp = DummyGetSCP()
        def on_c_get(ds): raise RuntimeError
        scp.ae.on_c_get = on_c_get
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        for (status, ds) in assoc.send_c_get(self.ds, query_model='P'):
            self.assertEqual(int(status), 0xC000)
        assoc.release()
        scp.stop()

    def test_bad_user_on_c_get_yield(self):
        """Test receiving a bad yield"""
        scp = DummyGetSCP()
        def on_c_get(ds): yield 'ats', None
        scp.ae.on_c_get = on_c_get
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        for (status, ds) in assoc.send_c_get(self.ds, query_model='P'):
            self.assertEqual(int(status), 0xC000)
        assoc.release()
        scp.stop()

    def test_bad_user_on_c_get_status_value(self):
        """Test receiving a bad yield status int"""
        scp = DummyGetSCP()
        def on_c_get(ds):
            yield 1
            yield 0x0111, None
        scp.ae.on_c_get = on_c_get
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        for (status, ds) in assoc.send_c_get(self.ds, query_model='P'):
            self.assertEqual(int(status), 0xC000)
        assoc.release()
        scp.stop()

    def test_bad_user_on_c_get_status_type(self):
        """Test receiving a bad yield status type"""
        scp = DummyGetSCP()
        def on_c_get(ds):
            yield 1
            yield 'test', None
        scp.ae.on_c_get = on_c_get
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        for (status, ds) in assoc.send_c_get(self.ds, query_model='P'):
            self.assertEqual(int(status), 0xC000)
        assoc.release()
        scp.stop()

    def test_bad_user_on_c_get_ds(self):
        """Test exception raised by bad on_c_get ds"""
        scp = DummyGetSCP()
        scp.status = scp.pending

        def on_c_store(ds):
            return 0x0000

        def on_c_get(ds):
            def test(): pass
            yield 1
            yield 0xFF00, test

        scp.ae.on_c_get = on_c_get
        scp.start()
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
        scp.stop()

    def test_good_send(self):
        """Test good send"""
        scp = DummyGetSCP()
        scp.status = scp.pending

        def on_c_store(ds):
            self.assertTrue('PatientID' in ds)
            return 0x0000

        scp.start()
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
        scp.stop()

    def test_ds_not_match_agreed_sop(self):
        """Test returns failure status if dataset sop wasnt agreed on"""
        scp = DummyGetSCP()
        scp.start()

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
            rsp, _ = assoc.dimse.receive_msg(False, assoc.dimse.dimse_timeout)

            if rsp.__class__ == C_GET:
                self.assertEqual(rsp.Status, 0xA900)
                assoc.release()
                break

        scp.stop()

    def test_ds_bad(self):
        """Test the user on_c_get raises when ds is bad"""
        scp = DummyGetSCP()
        scp.status = scp.pending
        scp.start()

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
            rsp, _ = assoc.dimse.receive_msg(False, assoc.dimse.dimse_timeout)

            if rsp.__class__ == C_GET:
                self.assertEqual(rsp.Status, 0xc000)
                assoc.release()
                break

        scp.stop()


class TestAssociationSendCCancelGet(unittest.TestCase):
    """Run tests on Assocation send_c_cancel_find."""
    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        scp = DummyGetSCP()
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet])
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        self.assertFalse(assoc.is_established)
        with self.assertRaises(RuntimeError):
            assoc.send_c_cancel_get(1)
        scp.stop()


class TestAssociationSendCMove(unittest.TestCase):
    """Run tests on Assocation send_c_move."""
    def setUp(self):
        """Run prior to each test"""
        self.ds = Dataset()
        self.ds.PatientName = '*'
        self.ds.QueryRetrieveLevel = "PATIENT"

    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        self.assertFalse(assoc.is_established)
        with self.assertRaises(RuntimeError):
            next(assoc.send_c_move(self.ds, b'TESTMOVE'))
        scp.stop()

    def test_no_abstract_syntax_match(self):
        """Test when no accepted abstract syntax"""
        scp = DummyStorageSCP()
        scp.start()
        ae = AE(scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        for (status, ds) in assoc.send_c_move(DATASET, b'TESTMOVE'):
            self.assertEqual(int(status), 0xa900)
        assoc.release()
        scp.stop()

    def test_bad_query_model(self):
        """Test bad query model parameter"""
        scp = DummyMoveSCP()
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        with self.assertRaises(ValueError):
            next(assoc.send_c_move(self.ds, b'TESTMOVE', query_model='X'))
        assoc.release()
        scp.stop()

    def test_good_query_model(self):
        """Test all the query models"""
        store_scp = DummyStorageSCP(11113)
        store_scp.start()

        scp = DummyMoveSCP()
        scp.start()
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
        scp.stop()

        store_scp.stop()

    def test_move_destination_no_assoc(self):
        """Test move destination failed to assoc"""
        scp = DummyMoveSCP()
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               StudyRootQueryRetrieveInformationModelMove,
                               PatientStudyOnlyQueryRetrieveInformationModelMove])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        for (status, ds) in assoc.send_c_move(self.ds, b'TESTMOVE', query_model='P'):
            self.assertEqual(int(status), 0xa702)
        assoc.release()
        scp.stop()

    def test_move_destination_unknown(self):
        """Test unknown move destination"""
        scp = DummyMoveSCP()
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               StudyRootQueryRetrieveInformationModelMove,
                               PatientStudyOnlyQueryRetrieveInformationModelMove])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        for (status, ds) in assoc.send_c_move(self.ds, b'UNKNOWN', query_model='P'):
            self.assertEqual(int(status), 0xa801)
        assoc.release()
        scp.stop()

    def test_move_destination_failed_store(self):
        """Test the destination AE returning failed status"""
        store_scp = DummyStorageSCP(11113)
        store_scp.status = store_scp.out_of_resources
        store_scp.start()

        scp = DummyMoveSCP()
        scp.start()
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
        scp.stop()

        store_scp.stop()

    def test_move_destination_warning_store(self):
        """Test the destination AE returning warning status"""
        store_scp = DummyStorageSCP(11113)
        store_scp.status = store_scp.coercion_of_elements
        store_scp.start()

        scp = DummyMoveSCP()
        scp.start()
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
        scp.stop()

        store_scp.stop()

    def test_user_failed(self):
        """Test the user on_c_move returning failure status"""
        store_scp = DummyStorageSCP(11113)
        store_scp.start()

        scp = DummyMoveSCP()
        scp.status = scp.unable_to_process
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               StudyRootQueryRetrieveInformationModelMove,
                               PatientStudyOnlyQueryRetrieveInformationModelMove])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_move(self.ds, b'TESTMOVE', query_model='P')
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xC000)

        assoc.release()
        scp.stop()

        store_scp.stop()

    def test_user_warning(self):
        """Test the user on_c_move returning warning status"""
        store_scp = DummyStorageSCP(11113)
        store_scp.start()

        scp = DummyMoveSCP()
        scp.status = scp.warning
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               StudyRootQueryRetrieveInformationModelMove,
                               PatientStudyOnlyQueryRetrieveInformationModelMove])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_move(self.ds, b'TESTMOVE', query_model='P')
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xB000)

        assoc.release()
        scp.stop()

        store_scp.stop()

    def test_user_cancel(self):
        """Test the user on_c_move returning cancel status"""
        store_scp = DummyStorageSCP(11113)
        store_scp.start()

        scp = DummyMoveSCP()
        scp.status = scp.cancel_status
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               StudyRootQueryRetrieveInformationModelMove,
                               PatientStudyOnlyQueryRetrieveInformationModelMove])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_move(self.ds, b'TESTMOVE', query_model='P')
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xFE00)

        assoc.release()
        scp.stop()

        store_scp.stop()

    def test_user_success(self):
        """Test the user on_c_move returning success status"""
        store_scp = DummyStorageSCP(11113)
        store_scp.start()

        scp = DummyMoveSCP()
        scp.status = scp.success
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               StudyRootQueryRetrieveInformationModelMove,
                               PatientStudyOnlyQueryRetrieveInformationModelMove])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_move(self.ds, b'TESTMOVE', query_model='P')
        (status, ds) = next(result)
        self.assertEqual(int(status), 0x0000)

        assoc.release()
        scp.stop()

        store_scp.stop()

    def test_bad_user_on_c_move(self):
        """Test bad user on_c_move causes a failure response"""
        store_scp = DummyStorageSCP(11113)
        store_scp.start()

        scp = DummyMoveSCP()
        def on_c_move(ds, aet): raise RuntimeError
        scp.ae.on_c_move = on_c_move
        scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_move(self.ds, b'TESTMOVE', query_model='P')
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xC000)

        assoc.release()
        scp.stop()
        store_scp.stop()

    def test_bad_user_on_c_move_first_yield(self):
        """Test exception raised by bad on_c_move first yield"""
        store_scp = DummyStorageSCP(11113)
        store_scp.start()

        scp = DummyMoveSCP()
        def on_c_move(ds, aet): yield None
        scp.ae.on_c_move = on_c_move
        scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_move(self.ds, b'TESTMOVE', query_model='P')
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xC000)

        assoc.release()
        scp.stop()
        store_scp.stop()

    def test_bad_user_on_c_move_second_yield_missing(self):
        """Test exception raised by bad on_c_move second yield missing"""
        store_scp = DummyStorageSCP(11113)
        store_scp.start()

        scp = DummyMoveSCP()
        def on_c_move(ds, aet): yield 1
        scp.ae.on_c_move = on_c_move
        scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_move(self.ds, b'TESTMOVE', query_model='P')
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xC000)

        assoc.release()
        scp.stop()
        store_scp.stop()

    def test_bad_user_on_c_move_second_yield(self):
        """Test exception raised by bad on_c_move second yield"""
        store_scp = DummyStorageSCP(11113)
        store_scp.start()

        scp = DummyMoveSCP()
        def on_c_move(ds, aet): yield 1; yield 1234, 'test'
        scp.ae.on_c_move = on_c_move
        scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_move(self.ds, b'TESTMOVE', query_model='P')
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xA801)

        assoc.release()
        scp.stop()
        store_scp.stop()

    def test_bad_user_on_c_move_nth_yield(self):
        """Test exception raised by bad on_c_move third+ yield"""
        store_scp = DummyStorageSCP(11113)
        store_scp.start()

        scp = DummyMoveSCP()
        def on_c_move(ds, aet):
            yield 1
            yield 'localhost', 11113
            yield 'test', DATASET
        scp.ae.on_c_move = on_c_move
        scp.start()

        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_move(self.ds, b'TESTMOVE', query_model='P')
        (status, ds) = next(result)
        self.assertEqual(int(status), 0xc000)

        assoc.release()
        scp.stop()
        store_scp.stop()

    def test_ds_not_match_agreed_sop(self):
        """Test returns failure status if dataset sop wasnt agreed on"""
        scp = DummyMoveSCP()
        scp.start()

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
            rsp, _ = assoc.dimse.receive_msg(False, assoc.dimse.dimse_timeout)

            if rsp.__class__ == C_MOVE:
                self.assertEqual(rsp.Status, 0xA900)
                assoc.release()
                break

        scp.stop()

    def test_ds_bad(self):
        """Test the user on_c_move raises when ds is bad"""
        store_scp = DummyStorageSCP(11113)
        store_scp.start()

        def test(): pass

        def on_c_move(ds, move_aet):
            yield 1
            yield 'localhost', 11113
            yield 0xff00, test

        scp = DummyMoveSCP()
        scp.ae.on_c_move = on_c_move
        scp.status = scp.pending
        scp.start()

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
            rsp, _ = assoc.dimse.receive_msg(False, assoc.dimse.dimse_timeout)

            if rsp.__class__ == C_MOVE:
                self.assertEqual(rsp.Status, 0xc000)
                assoc.release()
                break

        scp.stop()

        store_scp.stop()


class TestAssociationSendCCancelMove(unittest.TestCase):
    """Run tests on Assocation send_c_cancel_move."""
    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        scp = DummyMoveSCP()
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove])
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        self.assertFalse(assoc.is_established)
        with self.assertRaises(RuntimeError):
            assoc.send_c_cancel_move(1)
        scp.stop()


class TestAssociationSendNEventReport(unittest.TestCase):
    """Run tests on Assocation send_n_event_report."""
    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        self.assertFalse(assoc.is_established)
        with self.assertRaises(RuntimeError):
            assoc.send_n_event_report()
        scp.stop()

    def test_not_implemented(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        with self.assertRaises(NotImplementedError):
            assoc.send_n_event_report()
        assoc.release()
        scp.stop()


class TestAssociationSendNGet(unittest.TestCase):
    """Run tests on Assocation send_n_get."""
    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        self.assertFalse(assoc.is_established)
        with self.assertRaises(RuntimeError):
            assoc.send_n_get()
        scp.stop()

    def test_not_implemented(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        with self.assertRaises(NotImplementedError):
            assoc.send_n_get()
        assoc.release()
        scp.stop()


class TestAssociationSendNSet(unittest.TestCase):
    """Run tests on Assocation send_n_set."""
    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        self.assertFalse(assoc.is_established)
        with self.assertRaises(RuntimeError):
            assoc.send_n_set()
        scp.stop()

    def test_not_implemented(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        with self.assertRaises(NotImplementedError):
            assoc.send_n_set()
        assoc.release()
        scp.stop()


class TestAssociationSendNAction(unittest.TestCase):
    """Run tests on Assocation send_n_action."""
    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        self.assertFalse(assoc.is_established)
        with self.assertRaises(RuntimeError):
            assoc.send_n_action()
        scp.stop()

    def test_not_implemented(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        with self.assertRaises(NotImplementedError):
            assoc.send_n_action()
        assoc.release()
        scp.stop()


class TestAssociationSendNCreate(unittest.TestCase):
    """Run tests on Assocation send_n_create."""
    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        self.assertFalse(assoc.is_established)
        with self.assertRaises(RuntimeError):
            assoc.send_n_create()
        scp.stop()

    def test_not_implemented(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        with self.assertRaises(NotImplementedError):
            assoc.send_n_create()
        assoc.release()
        scp.stop()


class TestAssociationSendNDelete(unittest.TestCase):
    """Run tests on Assocation send_n_delete."""
    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        self.assertFalse(assoc.is_established)
        with self.assertRaises(RuntimeError):
            assoc.send_n_delete()
        scp.stop()

    def test_not_implemented(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        with self.assertRaises(NotImplementedError):
            assoc.send_n_delete()
        assoc.release()
        scp.stop()


class TestAssociationCallbacks(unittest.TestCase):
    """Run tests on Assocation callbacks."""
    pass


if __name__ == "__main__":
    unittest.main()
