#!/usr/bin/env python

import logging
import socket
import threading
import unittest
from unittest.mock import patch

from pydicom.uid import UID, ImplicitVRLittleEndian

from pynetdicom3 import AE, VerificationSOPClass
from pynetdicom3.association import Association
from pynetdicom3.SOPclass import CTImageStorage

LOGGER = logging.getLogger('pynetdicom3')
LOGGER.setLevel(logging.CRITICAL)


class DummySCP(threading.Thread):
    """A threaded dummy verification SCP used for testing"""
    def __init__(self):
        self.ae = AE(scp_sop_class=[VerificationSOPClass], port=11113)
        threading.Thread.__init__(self)
        self.daemon = True

    def run(self):
        """The thread run method"""
        self.ae.start()

    def stop(self):
        """Stop the SCP thread"""
        self.ae.stop()

    def abort(self):
        """Abort any associations"""
        for assoc in self.ae.active_associations:
            assoc.abort()

    def release(self):
        """Release any associations"""
        for assoc in self.ae.active_associations:
            assoc.release()


class DummySCU(threading.Thread):
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
            Association(self.ae, client_socket=self.socket, peer_ae={})
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
        scp = DummySCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        ae.presentation_contexts_scu = []
        assoc = ae.associate('localhost', 11113)
        self.assertFalse(assoc.is_established, msg="assoc.kill if no SCU presentation contexts")
        self.assertRaises(SystemExit, ae.quit)
        scp.stop()

        # Test good request and assoc accepted by peer
        scp = DummySCP()
        scp.start()
        ae = AE(scu_sop_class=[VerificationSOPClass])
        assoc = ae.associate('localhost', 11113)
        self.assertTrue(assoc.is_established)
        assoc.release()
        self.assertFalse(assoc.is_established)
        self.assertRaises(SystemExit, ae.quit)
        scp.stop()

        # Test rejection due to no acceptable presentation contexts
        scp = DummySCP()
        scp.start()
        ae = AE(scu_sop_class=[CTImageStorage])
        assoc = ae.associate('localhost', 11113)
        self.assertTrue(assoc.is_aborted)
        self.assertFalse(assoc.is_established)
        self.assertRaises(SystemExit, ae.quit)
        scp.stop()

        # Test peer releases assoc
        scp = DummySCP()
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
        scp = DummySCP()
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
        scp = DummySCP()
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


class TestAssociationSendDIMSEC(unittest.TestCase):
    """Run tests on Assocation send_c_* methods."""
    pass


class TestAssociationSendDIMSEN(unittest.TestCase):
    """Run tests on Assocation send_n_* methods."""
    pass


class TestAssociationCallbacks(unittest.TestCase):
    """Run tests on Assocation callbacks."""
    pass


if __name__ == "__main__":
    unittest.main()
