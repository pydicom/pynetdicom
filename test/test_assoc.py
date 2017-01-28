#!/usr/bin/env python

import logging
import os
import socket
import time
import threading
import unittest
from unittest.mock import patch

from pydicom.uid import UID, ImplicitVRLittleEndian, ExplicitVRLittleEndian
from pydicom import read_file

from dummy_c_scp import DummyVerificationSCP, DummyStorageSCP, \
                        DummyFindSCP, DummyGetSCP, DummyMoveSCP
from pynetdicom3 import AE, VerificationSOPClass
from pynetdicom3.association import Association
from pynetdicom3.SOPclass import CTImageStorage, MRImageStorage, Status, \
                                 RTImageStorage

LOGGER = logging.getLogger('pynetdicom3')
LOGGER.setLevel(logging.DEBUG)

TEST_DIR = os.path.dirname(__file__)
DATASET = read_file(os.path.join('dicom_files', 'RTImageStorage.dcm'))
COMP_DATASET = read_file(os.path.join('dicom_files', 'MRImageStorage_JPG2000_Lossless.dcm'))


class DummyVerificationSCU(threading.Thread):
    """A threaded dummy verification SCU used for testing"""
    def __init__(self):
        self.ae = AE(scu_sop_class=[VerificationSOPClass])
        threading.Thread.__init__(self)
        self.daemon = True

    def run(self):
        """The thread run method"""
        self.ae.start()

    def stop(self):
        """Stop the SCU thread"""
        self.ae.stop()


class TestAssociation(unittest.TestCase):
    """Run tests on Associtation."""
    # Association(local_ae, client_socket, peer_ae, acse_timeout,
    #             dimse_timout, max_pdu, ext_neg)
    def setUp(self):
        """This function runs prior to all test methods"""
        self.ae = AE(scu_sop_class=[VerificationSOPClass])
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
        self.ae.stop()

    def test_init_errors(self):
        """Test bad parameters on init raise errors"""
        with self.assertRaises(TypeError, msg="must have client_socket or peer_ae"):
            Association(self.ae)
        with self.assertRaises(TypeError, msg="must have client_socket or peer_ae"):
            Association(self.ae, client_socket=self.socket, peer_ae=self.peer)
        with self.assertRaises(TypeError, msg="wrong client_socket type"):
            Association(self.ae, client_socket=123)
        with self.assertRaises(TypeError, msg="wrong peer_ae type"):
            Association(self.ae, peer_ae=123)
        with self.assertRaises(KeyError, msg="missing keys in peer_ae"):
            Association(self.ae, peer_ae={})
        with self.assertRaises(TypeError, msg="wrong local_ae type"):
            Association(12345, peer_ae=self.peer)
        with self.assertRaises(TypeError, msg="wrong dimse_timeout type"):
            Association(self.ae, peer_ae=self.peer, dimse_timeout='a')
        with self.assertRaises(TypeError, msg="wrong acse_timeout type"):
            Association(self.ae, peer_ae=self.peer, acse_timeout='a')
        with self.assertRaises(TypeError, msg="wrong max_pdu type"):
            Association(self.ae, peer_ae=self.peer, max_pdu='a')
        with self.assertRaises(TypeError, msg="wrong ext_neg type"):
            Association(self.ae, peer_ae=self.peer, ext_neg='a')

    def test_run_acceptor(self):
        """Test running as an Association acceptor (SCP)"""
        pass

    def test_run_requestor(self):
        """Test running as an Association requestor (SCU)"""
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.presentation_contexts_scu = []
        assoc = ae.associate('localhost', 11113)
        self.assertFalse(assoc.is_established, msg="assoc.kill if no SCU presentation contexts")
        self.assertRaises(SystemExit, ae.quit)
        scp.stop()

        # Test good request and assoc accepted by peer
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11113)
        self.assertTrue(assoc.is_established)
        assoc.release()
        self.assertFalse(assoc.is_established)
        self.assertRaises(SystemExit, ae.quit)
        scp.stop()

        # Test rejection due to no acceptable presentation contexts
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11113)
        self.assertTrue(assoc.is_aborted)
        self.assertFalse(assoc.is_established)
        self.assertRaises(SystemExit, ae.quit)
        scp.stop()

        # Test peer releases assoc
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11113)
        self.assertTrue(assoc.is_established)
        scp.release()
        self.assertFalse(assoc.is_established)
        self.assertTrue(assoc.is_released)
        self.assertRaises(SystemExit, ae.quit)
        scp.stop() # Important!

        # Test peer aborts assoc
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11113)
        self.assertTrue(assoc.is_established)
        scp.abort()
        self.assertFalse(assoc.is_established)
        self.assertTrue(assoc.is_aborted)
        self.assertRaises(SystemExit, ae.quit)
        scp.stop() # Important!

        # Test peer rejects assoc
        scp = DummyVerificationSCP()
        scp.ae.require_calling_aet = b'HAHA NOPE'
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11113)
        self.assertTrue(assoc.is_rejected)
        self.assertFalse(assoc.is_established)
        self.assertRaises(SystemExit, ae.quit)
        scp.stop() # Important!

    def test_kill(self):
        """Test killing the association"""
        pass

    def test_assoc_release(self):
        """Test Association release"""
        pass

    def test_assoc_abort(self):
        """Test Association abort"""
        pass


class TestAssociationSendCEcho(unittest.TestCase):
    """Run tests on Assocation send_c_echo."""
    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11113)
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
        assoc = ae.associate('localhost', 11113)
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
        assoc = ae.associate('localhost', 11113)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_echo()
        self.assertEqual(int(result), 0x0000)
        assoc.release()
        scp.stop()

    @unittest.skip # dimse_timeout broken
    def test_no_response(self):
        """Test when no accepted abstract syntax"""
        scp = DummyVerificationSCP()
        scp.delay = 0.1
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.dimse_timeout = 0.01
        assoc = ae.associate('localhost', 11113)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_echo()
        self.assertTrue(result is None)
        assoc.release()
        scp.stop()


class TestAssociationSendCStore(unittest.TestCase):
    """Run tests on Assocation send_c_store."""
    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        scp = DummyStorageSCP()
        scp.start()
        ae = AE(scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11113)
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
        assoc = ae.associate('localhost', 11113)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_store(DATASET)
        self.assertEqual(int(result), 0xc000)
        assoc.release()
        scp.stop()

    def test_compressed_ds(self):
        """Test when ds is compressed"""
        scp = DummyStorageSCP()
        scp.start()
        ae = AE(scu_sop_class=[MRImageStorage])
        assoc = ae.associate('localhost', 11113)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_store(COMP_DATASET)
        self.assertEqual(int(result), 0x0000)
        assoc.release()
        scp.stop()

    def test_good_response(self):
        """Test successful c-store"""
        scp = DummyStorageSCP()
        scp.start()
        ae = AE(scu_sop_class=[CTImageStorage, RTImageStorage])
        assoc = ae.associate('localhost', 11113)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_store(DATASET)
        self.assertEqual(int(result), 0x0000)
        assoc.release()
        scp.stop()

    def test_bad_priority(self):
        """Test successful c-echo"""
        scp = DummyStorageSCP()
        scp.start()
        ae = AE(scu_sop_class=[RTImageStorage])
        assoc = ae.associate('localhost', 11113)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_store(DATASET, priority=0x0003)
        self.assertEqual(int(result), 0x0000)
        assoc.release()
        scp.stop()

    def test_bad_dataset(self):
        """Test failure if unable to encode dataset"""
        scp = DummyStorageSCP()
        scp.start()
        ae = AE(scu_sop_class=[RTImageStorage],
                transfer_syntax=[ExplicitVRLittleEndian])
        assoc = ae.associate('localhost', 11113)
        self.assertTrue(assoc.is_established)
        DATASET.PerimeterValue = b'\x00\x01'
        result = assoc.send_c_store(DATASET)
        self.assertEqual(int(result), 0xC000)
        assoc.release()
        del DATASET.PerimeterValue # Fix up our changes
        scp.stop()

    @unittest.skip # dimse_timeout broken
    def test_no_response(self):
        """Test when no accepted abstract syntax"""
        scp = DummyVerificationSCP()
        scp.delay = 0.1
        scp.start()
        ae = AE(scu_sop_class=[CTImageStorage, RTImageStorage])
        ae.dimse_timeout = 0.01
        assoc = ae.associate('localhost', 11113)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_store(DATASET)
        self.assertTrue(result is None)
        assoc.release()
        scp.stop()


class TestAssociationSendCFind(unittest.TestCase):
    """Run tests on Assocation send_c_find."""
    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11113)
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
        assoc = ae.associate('localhost', 11113)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_echo()
        self.assertTrue(result is None)
        assoc.release()
        scp.stop()


class TestAssociationSendCGet(unittest.TestCase):
    """Run tests on Assocation send_c_get."""
    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11113)
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
        assoc = ae.associate('localhost', 11113)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_echo()
        self.assertTrue(result is None)
        assoc.release()
        scp.stop()


class TestAssociationSendCMove(unittest.TestCase):
    """Run tests on Assocation send_c_move."""
    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11113)
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
        assoc = ae.associate('localhost', 11113)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_echo()
        self.assertTrue(result is None)
        assoc.release()
        scp.stop()


class TestAssociationSendDIMSEN(unittest.TestCase):
    """Run tests on Assocation send_n_* methods."""
    pass


class TestAssociationCallbacks(unittest.TestCase):
    """Run tests on Assocation callbacks."""
    pass


if __name__ == "__main__":
    unittest.main()
