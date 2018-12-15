"""Tests for ACSE"""

#from io import BytesIO
import logging
#import os
try:
    import queue
except ImportError:
    import Queue as queue  # Python 2 compatibility
#import select
#import socket
#from struct import pack
import time
import threading

import pytest

from pynetdicom3 import (
    AE, VerificationPresentationContexts, PYNETDICOM_IMPLEMENTATION_UID,
    PYNETDICOM_IMPLEMENTATION_VERSION
)
from pynetdicom3.acse import ACSE
from pynetdicom3.association import Association
from pynetdicom3.pdu_primitives import (
    A_ASSOCIATE, A_RELEASE, A_ABORT, A_P_ABORT,
    MaximumLengthNotification,
    ImplementationClassUIDNotification,
    ImplementationVersionNameNotification,
    SCP_SCU_RoleSelectionNegotiation,
)

from .dummy_c_scp import (
    DummyVerificationSCP, DummyStorageSCP, DummyFindSCP, DummyGetSCP,
    DummyMoveSCP, DummyBaseSCP
)

LOGGER = logging.getLogger('pynetdicom3')
LOGGER.setLevel(logging.CRITICAL)
#LOGGER.setLevel(logging.DEBUG)


class DummyDUL(object):
    def __init__(self):
        self.received = queue.Queue()
        self.to_send = queue.Queue()

    def send_pdu(self, primitive):
        self.to_send.put(primitive)


class DummyAssociation(object):
    def __init__(self):
        self.ae = AE()
        self.dul = DummyDUL()
        self.local = {'pdv_size' : 31682, 'address' : '127.0.0.1',
                      'port' : 11112, 'ae_title' : b'TEST_LOCAL      '}
        self.remote = {'pdv_size' : 31683, 'address' : '127.0.0.2',
                      'port' : 11113, 'ae_title' : b'TEST_REMOTE     '}
        self.acse_timeout = 11
        self.dimse_timeout = 12
        self.network_timeout = 13
        self.extended_negotiation = [[], []]

        self._requested_contexts = []
        self._supported_contexts = []

    add_requested_context = AE.add_requested_context
    add_supported_context = AE.add_supported_context
    #self._validate_requested_contexts = AE._validate_requested_contexts

    @property
    def requested_contexts(self):
        contexts = []
        for ii, context in enumerate(self._requested_contexts):
            context.context_id = 2 * ii + 1
            contexts.append(context)

        return contexts

    @property
    def supported_contexts(self):
        return self._supported_contexts


class TestInit(object):
    """Tests for initialising the ACSE class"""
    def test_default(self):
        """Test default initialisation"""
        acse = ACSE()
        assert acse.acse_timeout == 30

    def test_args(self):
        """Test initialising the ACSE with arguments."""
        acse = ACSE(acse_timeout=20)
        assert acse.acse_timeout == 20


class TestPrimitiveConstruction(object):
    """Test the primitive builders"""
    def setup(self):
        self.assoc = DummyAssociation()
        self.assoc.add_requested_context('1.2.840.10008.1.1')

    def test_send_request(self):
        """Test A-ASSOCIATE (rq) construction and sending"""
        acse = ACSE()
        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = '1.2.840.10008.1.1'
        role.scu_role = True
        role.scp_role = False
        self.assoc.extended_negotiation[0].append(role)
        acse.send_request(self.assoc)

        primitive = self.assoc.dul.to_send.get()
        with pytest.raises(queue.Empty):
            self.assoc.dul.to_send.get(block=False)

        assert isinstance(primitive, A_ASSOCIATE)
        assert primitive.application_context_name == '1.2.840.10008.3.1.1.1'
        assert primitive.calling_ae_title == b'TEST_LOCAL      '
        assert primitive.called_ae_title == b'TEST_REMOTE     '
        assert primitive.calling_presentation_address == ('127.0.0.1', 11112)
        assert primitive.called_presentation_address == ('127.0.0.2', 11113)

        cx = primitive.presentation_context_definition_list
        assert len(cx) == 1
        assert cx[0].abstract_syntax == '1.2.840.10008.1.1'

        user_info = primitive.user_information
        assert len(user_info) == 4

        for item in user_info:
            if isinstance(item, MaximumLengthNotification):
                assert item.maximum_length_received == 31682
            elif isinstance(item, ImplementationClassUIDNotification):
                assert item.implementation_class_uid == (
                    PYNETDICOM_IMPLEMENTATION_UID
                )
            elif isinstance(item, ImplementationVersionNameNotification):
                assert item.implementation_version_name == (
                    PYNETDICOM_IMPLEMENTATION_VERSION.encode('ascii')
                )
            elif isinstance(item, SCP_SCU_RoleSelectionNegotiation):
                assert item.sop_class_uid == '1.2.840.10008.1.1'
                assert item.scu_role is True
                assert item.scp_role is False

    @pytest.mark.parametrize('source', (0x00, 0x02))
    def test_send_abort(self, source):
        """Test A-ABORT construction and sending"""
        acse = ACSE()
        acse.send_abort(self.assoc, source)

        primitive = self.assoc.dul.to_send.get()
        with pytest.raises(queue.Empty):
            self.assoc.dul.to_send.get(block=False)

        assert isinstance(primitive, A_ABORT)
        assert primitive.abort_source == source

    def test_send_abort_raises(self):
        """Test A-ABORT construction fails for invalid source"""
        acse = ACSE()
        msg = r"Invalid 'source' parameter value"
        with pytest.raises(ValueError, match=msg):
            acse.send_abort(self.assoc, 0x01)

    @pytest.mark.parametrize('reason', (0x00, 0x01, 0x02, 0x04, 0x05, 0x06))
    def test_send_ap_abort(self, reason):
        """Test A-P-ABORT construction and sending"""
        acse = ACSE()
        acse._send_ap_abort(self.assoc, reason)

        primitive = self.assoc.dul.to_send.get()
        with pytest.raises(queue.Empty):
            self.assoc.dul.to_send.get(block=False)

        assert isinstance(primitive, A_P_ABORT)
        assert primitive.provider_reason == reason

    def test_send_ap_abort_raises(self):
        """Test A-P-ABORT construction fails for invalid reason"""
        acse = ACSE()
        msg = r"Invalid 'reason' parameter value"
        with pytest.raises(ValueError, match=msg):
            acse._send_ap_abort(self.assoc, 0x03)


class Test(object):
    """Tests for ACSE"""
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
