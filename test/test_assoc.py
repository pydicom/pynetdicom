#!/usr/bin/env python

import logging
import os
import socket
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
LOGGER.setLevel(logging.DEBUG)

TEST_DS_DIR = os.path.join(os.path.dirname(__file__), 'dicom_files')
DATASET = read_file(os.path.join(TEST_DS_DIR, 'RTImageStorage.dcm'))
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

        # Test rejection due to no acceptable presentation contexts
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_aborted)
        self.assertFalse(assoc.is_established)
        self.assertRaises(SystemExit, ae.quit)
        scp.stop()

        # Test peer releases assoc
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

        # Test peer aborts assoc
        scp = DummyVerificationSCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11112)
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
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_rejected)
        self.assertFalse(assoc.is_established)
        self.assertRaises(SystemExit, ae.quit)
        scp.stop() # Important!

        # Test peer rejects assoc
        scp = DummyVerificationSCP()
        scp.ae.require_called_aet = b'HAHA NOPE'
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


class TestAssociationSendCStore(unittest.TestCase):
    """Run tests on Assocation send_c_store."""
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

    def test_bad_priority(self):
        """Test successful c-echo"""
        scp = DummyStorageSCP()
        scp.start()
        ae = AE(scu_sop_class=[RTImageStorage])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        result = assoc.send_c_store(DATASET, priority=0x0003)
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

    def test_bad_dataset(self):
        """Test failure if unable to encode dataset"""
        scp = DummyStorageSCP()
        scp.start()
        ae = AE(scu_sop_class=[RTImageStorage],
                transfer_syntax=[ExplicitVRLittleEndian])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        DATASET.PerimeterValue = b'\x00\x01'
        result = assoc.send_c_store(DATASET)
        self.assertEqual(int(result), 0xC000)
        assoc.release()
        del DATASET.PerimeterValue # Fix up our changes
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
        """Test receiving a failure response"""
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
            assoc.send_c_cancel_find(1, 'P')
        scp.stop()

    def test_bad_query_model(self):
        """Test when no accepted abstract syntax"""
        scp = DummyFindSCP()
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        with self.assertRaises(ValueError):
            next(assoc.send_c_cancel_find(1, 'X'))
        assoc.release()
        scp.stop()

    @unittest.skip # Depends on issue #40
    def test_cancel(self):
        """Test sending C-CANCEL-RQ"""
        scp = DummyFindSCP()
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelFind,
                               StudyRootQueryRetrieveInformationModelFind,
                               PatientStudyOnlyQueryRetrieveInformationModelFind,
                               ModalityWorklistInformationFind])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        assoc.send_c_cancel_find(1, query_model='P')
        assoc.send_c_cancel_find(1, query_model='S')
        assoc.send_c_cancel_find(1, query_model='O')
        assoc.send_c_cancel_find(1, query_model='W')
        assoc.release()
        scp.stop()


class TestAssociationSendCGet(unittest.TestCase):
    """Run tests on Assocation send_c_get."""
    def setUp(self):
        """Run prior to each test"""
        self.ds = Dataset()
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
                               RTImageStorage],
                scp_sop_class=[RTImageStorage])
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
                               RTImageStorage],
                scp_sop_class=[RTImageStorage])
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
                               RTImageStorage],
                scp_sop_class=[RTImageStorage])
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
                               RTImageStorage],
                scp_sop_class=[RTImageStorage])
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
        """Test receiving a failure response"""
        scp = DummyGetSCP()
        def on_c_get(ds): yield 0x0000, None
        scp.ae.on_c_get = on_c_get
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        for (status, ds) in assoc.send_c_get(self.ds, query_model='P'):
            self.assertEqual(int(status), 0xC000)
        assoc.release()
        scp.stop()

    # test bad user second yield

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
            assoc.send_c_cancel_get(1, 'P')
        scp.stop()

    def test_bad_query_model(self):
        """Test when no accepted abstract syntax"""
        scp = DummyGetSCP()
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        with self.assertRaises(ValueError):
            next(assoc.send_c_cancel_get(1, 'X'))
        assoc.release()
        scp.stop()

    @unittest.skip # Depends on issue #40
    def test_cancel(self):
        """Test sending C-CANCEL-RQ"""
        scp = DummyGetSCP()
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelGet,
                               StudyRootQueryRetrieveInformationModelGet,
                               PatientStudyOnlyQueryRetrieveInformationModelGet])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        assoc.send_c_cancel_get(1, query_model='P')
        assoc.send_c_cancel_get(1, query_model='S')
        assoc.send_c_cancel_get(1, query_model='O')
        assoc.release()
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

    # test receive failure
    # test receive pending send failure
    # test receive pending send warning
    # test receive pending send success
    # test receive warning
    # test receive cancel
    # test receive success
    # test error user on_c_move
    # test error bad first yield
    # test error bad second yield
    # test error bad third yield




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
            assoc.send_c_cancel_move(1, 'P')
        scp.stop()

    def test_bad_query_model(self):
        """Test when no accepted abstract syntax"""
        scp = DummyMoveSCP()
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        with self.assertRaises(ValueError):
            next(assoc.send_c_cancel_move(1, 'X'))
        assoc.release()
        scp.stop()

    @unittest.skip # Depends on issue #40
    def test_cancel(self):
        """Test sending C-CANCEL-RQ"""
        scp = DummyMoveSCP()
        scp.start()
        ae = AE(scu_sop_class=[PatientRootQueryRetrieveInformationModelMove,
                               StudyRootQueryRetrieveInformationModelMove,
                               PatientStudyOnlyQueryRetrieveInformationModelMove,
                               ModalityWorklistInformationMove])
        assoc = ae.associate('localhost', 11112)
        self.assertTrue(assoc.is_established)
        assoc.send_c_cancel_move(1, query_model='P')
        assoc.send_c_cancel_move(1, query_model='S')
        assoc.send_c_cancel_move(1, query_model='O')
        assoc.send_c_cancel_move(1, query_model='W')
        assoc.release()
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
