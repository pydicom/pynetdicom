"""Unit tests for ACSE"""

import logging
try:
    import queue
except ImportError:
    import Queue as queue  # Python 2 compatibility
import select
import socket
from struct import pack, unpack
import sys
import time
import threading

import pytest

from pynetdicom import (
    AE, VerificationPresentationContexts, PYNETDICOM_IMPLEMENTATION_UID,
    PYNETDICOM_IMPLEMENTATION_VERSION, build_context
)
from pynetdicom.acse import ACSE
from pynetdicom.association import Association, ServiceUser
from pynetdicom.dimse_messages import DIMSEMessage, C_ECHO_RQ, C_ECHO_RSP
from pynetdicom.pdu_primitives import (
    A_ASSOCIATE, A_RELEASE, A_ABORT, A_P_ABORT,
    MaximumLengthNotification,
    ImplementationClassUIDNotification,
    ImplementationVersionNameNotification,
    UserIdentityNegotiation,
    SOPClassExtendedNegotiation,
    SOPClassCommonExtendedNegotiation,
    AsynchronousOperationsWindowNegotiation,
    SCP_SCU_RoleSelectionNegotiation,
)
from pynetdicom.pdu import P_DATA_TF
from pynetdicom.sop_class import VerificationSOPClass

from .dummy_c_scp import DummyVerificationSCP, DummyBaseSCP
from .encoded_pdu_items import (
    a_associate_rq, a_associate_ac, a_release_rq, a_release_rp, p_data_tf,
    a_abort, a_p_abort,
)


LOGGER = logging.getLogger('pynetdicom')
LOGGER.setLevel(logging.CRITICAL)
#LOGGER.setLevel(logging.DEBUG)


class DummyDUL(object):
    def __init__(self):
        self.queue = queue.Queue()
        self.received = queue.Queue()
        self.is_killed = False

    def send_pdu(self, primitive):
        self.queue.put(primitive)

    def peek_next_pdu(self):
        """Check the next PDU to be processed."""
        try:
            # Looks at next item without retrieving it
            return self.queue.queue[0]
        except (queue.Empty, IndexError):
            return None

    def receive_pdu(self, wait=False, timeout=None):
        # Takes item off the queue
        return self.queue.get(wait, timeout)

    def kill_dul(self):
        self.is_killed = True


class DummyAssociation(object):
    def __init__(self):
        self.ae = AE()
        self.mode = None
        self.dul = DummyDUL()
        self.requestor = ServiceUser(self, 'requestor')
        self.requestor.port = 11112
        self.requestor.ae_title = b'TEST_LOCAL      '
        self.requestor.address = '127.0.0.1'
        self.requestor.maximum_length = 31682
        self.acceptor = ServiceUser(self, 'acceptor')
        self.acceptor.ae_title = b'TEST_REMOTE     '
        self.acceptor.port = 11113
        self.acceptor.address = '127.0.0.2'
        self.acse_timeout = 11
        self.dimse_timeout = 12
        self.network_timeout = 13
        self.is_killed = False
        self.is_aborted = False
        self.is_established = False
        self.is_rejected = False
        self.is_released = False
        self.is_acceptor = False
        self.is_requestor = True

    def abort(self):
        self.is_aborted = True
        self.kill()

    def kill(self):
        self.is_killed = True

    @property
    def requested_contexts(self):
        return self.requestor.get_contexts('requested')

    @property
    def supported_contexts(self):
        return self.requestor.get_contexts('supported')

    def debug_association_rejected(self, primitive):
        pass

    debug_association_aborted = debug_association_rejected


class TestACSE(object):
    """Tests for initialising the ACSE class"""
    def setup(self):
        self.assoc = DummyAssociation()
        self.assoc.requestor.requested_contexts = [
            build_context('1.2.840.10008.1.1')
        ]

    def test_default(self):
        """Test default initialisation"""
        acse = ACSE()
        assert hasattr(acse, 'acse_timeout') is False

    def test_is_aborted(self):
        """Test ACSE.is_aborted"""
        acse = ACSE()
        assert acse.is_aborted(self.assoc) is False
        # "Received" A-ABORT
        acse.send_abort(self.assoc, 0x02)
        assert acse.is_aborted(self.assoc) is True
        self.assoc.dul.queue.get()
        with pytest.raises(queue.Empty):
            self.assoc.dul.queue.get(block=False)
        assert acse.is_aborted(self.assoc) is False

        # "Received" A-P-ABORT
        acse.send_ap_abort(self.assoc, 0x02)
        assert acse.is_aborted(self.assoc) is True

    def test_is_release_requested(self):
        """Test ACSE.is_release_requested"""
        acse = ACSE()
        assert acse.is_release_requested(self.assoc) is False

        acse.send_release(self.assoc)
        assert acse.is_release_requested(self.assoc) is True
        with pytest.raises(queue.Empty):
            self.assoc.dul.queue.get(block=False)
        assert acse.is_release_requested(self.assoc) is False

        acse.send_release(self.assoc, is_response=True)
        assert acse.is_release_requested(self.assoc) is False
        self.assoc.dul.queue.get()
        with pytest.raises(queue.Empty):
            self.assoc.dul.queue.get(block=False)
        assert acse.is_release_requested(self.assoc) is False


class TestNegotiationRequestor(object):
    """Test ACSE negotiation as requestor."""
    def setup(self):
        """Run prior to each test"""
        self.scp = None

        self.assoc = DummyAssociation()
        self.assoc.requestor.requested_contexts = [
            build_context('1.2.840.10008.1.1')
        ]

    def teardown(self):
        """Clear any active threads"""
        if self.scp:
            self.scp.abort()

        time.sleep(0.1)

        for thread in threading.enumerate():
            if isinstance(thread, DummyBaseSCP):
                thread.abort()
                thread.stop()

    @pytest.mark.skipif(sys.version_info[:2] == (3, 4), reason='no caplog')
    def test_no_requested_cx(self, caplog):
        """Test error logged if no requested contexts."""
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        assoc = Association(ae, mode='requestor')
        assert assoc.requestor.requested_contexts == []

        with caplog.at_level(logging.WARNING, logger='pynetdicom'):
            assoc.acse._negotiate_as_requestor(assoc)

            msg = (
                "One or more requested presentation contexts must be set "
                "prior to association negotiation"
            )
            assert msg in caplog.text

    def test_receive_abort(self):
        """Test if A-ABORT received during association negotiation."""
        primitive = A_ABORT()

        self.assoc.dul.queue.put(primitive)
        assert self.assoc.is_aborted is False
        assert self.assoc.is_killed is False

        acse = ACSE()
        acse._negotiate_as_requestor(self.assoc)
        #assert isinstance(self.assoc.dul.queue.get(), A_ASSOCIATE)
        #with pytest.raises(queue.Empty):
        #    self.assoc.dul.queue.get(block=False)
        assert self.assoc.is_aborted is True
        assert self.assoc.dul.is_killed is True

        primitive = self.assoc.dul.queue.get(block=False)
        assert isinstance(primitive, A_ASSOCIATE)
        with pytest.raises(queue.Empty):
            self.assoc.dul.queue.get(block=False)

    def test_receive_ap_abort(self):
        """Test if A-P-ABORT received during association negotiation."""
        primitive = A_P_ABORT()

        self.assoc.dul.queue.put(primitive)
        assert self.assoc.is_aborted is False
        assert self.assoc.is_killed is False

        acse = ACSE()
        acse._negotiate_as_requestor(self.assoc)
        assert self.assoc.is_aborted is True
        assert self.assoc.dul.is_killed is True

        primitive = self.assoc.dul.queue.get(block=False)
        assert isinstance(primitive, A_ASSOCIATE)
        with pytest.raises(queue.Empty):
            self.assoc.dul.queue.get(block=False)

    def test_receive_other(self):
        """Test if invalid received during association negotiation."""
        primitive = A_RELEASE()

        self.assoc.dul.queue.put(primitive)
        assert self.assoc.is_aborted is False
        assert self.assoc.is_killed is False

        acse = ACSE()
        acse._negotiate_as_requestor(self.assoc)
        assert self.assoc.is_aborted is False
        assert self.assoc.dul.is_killed is True

        primitive = self.assoc.dul.queue.get(block=False)
        assert isinstance(primitive, A_ASSOCIATE)
        with pytest.raises(queue.Empty):
            self.assoc.dul.queue.get(block=False)

    def test_receive_unknown_result(self):
        """Test abort if A-ASSOCIATE result is unknown."""
        primitive = A_ASSOCIATE()
        primitive._result = 0xFF

        self.assoc.dul.queue.put(primitive)
        assert self.assoc.is_aborted is False
        assert self.assoc.is_killed is False

        acse = ACSE()
        acse._negotiate_as_requestor(self.assoc)
        primitive = self.assoc.dul.queue.get(block=False)
        assert isinstance(primitive, A_ASSOCIATE)
        assert self.assoc.is_aborted is True
        assert self.assoc.is_killed is True

        primitive = self.assoc.dul.queue.get(block=False)
        assert isinstance(primitive, A_ABORT)
        assert primitive.abort_source == 0x02
        with pytest.raises(queue.Empty):
            self.assoc.dul.queue.get(block=False)

    def test_receive_reject(self):
        """Test kill if A-ASSOCIATE result is rejection."""
        primitive = A_ASSOCIATE()
        primitive._result = 0x01

        self.assoc.dul.queue.put(primitive)
        assert self.assoc.is_aborted is False
        assert self.assoc.is_killed is False
        assert self.assoc.is_rejected is False

        acse = ACSE()
        acse._negotiate_as_requestor(self.assoc)
        primitive = self.assoc.dul.queue.get(block=False)
        assert isinstance(primitive, A_ASSOCIATE)
        assert self.assoc.is_aborted is False
        assert self.assoc.is_rejected is True
        assert self.assoc.is_established is False
        assert self.assoc.dul.is_killed is True

        with pytest.raises(queue.Empty):
            self.assoc.dul.queue.get(block=False)

    def test_receive_accept(self):
        """Test establishment if A-ASSOCIATE result is acceptance."""
        self.scp = DummyVerificationSCP()
        self.scp.start()

        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established is True
        assoc.release()

        self.scp.stop()


class TestNegotiationAcceptor(object):
    """Test ACSE negotiation as acceptor."""
    def setup(self):
        pass


REFERENCE_REJECT_GOOD = [
    (0x01, 0x01, (0x01, 0x02, 0x03, 0x07)),
    (0x02, 0x01, (0x01, 0x02, 0x03, 0x07)),
    (0x01, 0x02, (0x01, 0x02)),
    (0x02, 0x02, (0x01, 0x02)),
    (0x01, 0x03, (0x01, 0x02)),
    (0x02, 0x03, (0x01, 0x02)),
]


class TestPrimitiveConstruction(object):
    """Test the primitive builders"""
    def setup(self):
        self.assoc = DummyAssociation()
        self.assoc.requestor.requested_contexts = [
            build_context('1.2.840.10008.1.1')
        ]

    def test_send_request(self):
        """Test A-ASSOCIATE (rq) construction and sending"""
        acse = ACSE()
        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = '1.2.840.10008.1.1'
        role.scu_role = True
        role.scp_role = False
        self.assoc.requestor.add_negotiation_item(role)
        acse.send_request(self.assoc)

        primitive = self.assoc.dul.queue.get()
        with pytest.raises(queue.Empty):
            self.assoc.dul.queue.get(block=False)

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
        assert len(user_info) == 3

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

        primitive = self.assoc.dul.queue.get()
        with pytest.raises(queue.Empty):
            self.assoc.dul.queue.get(block=False)

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
        acse.send_ap_abort(self.assoc, reason)

        primitive = self.assoc.dul.queue.get()
        with pytest.raises(queue.Empty):
            self.assoc.dul.queue.get(block=False)

        assert isinstance(primitive, A_P_ABORT)
        assert primitive.provider_reason == reason

    def test_send_ap_abort_raises(self):
        """Test A-P-ABORT construction fails for invalid reason"""
        acse = ACSE()
        msg = r"Invalid 'reason' parameter value"
        with pytest.raises(ValueError, match=msg):
            acse.send_ap_abort(self.assoc, 0x03)

    @pytest.mark.parametrize('result, source, reasons', REFERENCE_REJECT_GOOD)
    def test_send_reject(self, result, source, reasons):
        """Test A-ASSOCIATE (rj) construction and sending"""
        acse = ACSE()
        for reason in reasons:
            acse.send_reject(self.assoc, result, source, reason)

            primitive = self.assoc.dul.queue.get()
            with pytest.raises(queue.Empty):
                self.assoc.dul.queue.get(block=False)

            assert isinstance(primitive, A_ASSOCIATE)
            assert primitive.result == result
            assert primitive.result_source == source
            assert primitive.diagnostic == reason

    def test_send_reject_raises(self):
        """Test A-ASSOCIATE (rj) construction invalid values raise exception"""
        acse = ACSE()
        msg = r"Invalid 'result' parameter value"
        with pytest.raises(ValueError, match=msg):
            acse.send_reject(self.assoc, 0x00, 0x00, 0x00)

        msg = r"Invalid 'source' parameter value"
        with pytest.raises(ValueError, match=msg):
            acse.send_reject(self.assoc, 0x01, 0x00, 0x00)

        msg = r"Invalid 'diagnostic' parameter value"
        with pytest.raises(ValueError, match=msg):
            acse.send_reject(self.assoc, 0x01, 0x01, 0x00)

    def test_send_release(self):
        """Test A-RELEASE construction and sending"""
        acse = ACSE()
        acse.send_release(self.assoc, is_response=False)

        primitive = self.assoc.dul.queue.get()
        with pytest.raises(queue.Empty):
            self.assoc.dul.queue.get(block=False)

        assert isinstance(primitive, A_RELEASE)
        assert primitive.result is None

        acse.send_release(self.assoc, is_response=True)

        primitive = self.assoc.dul.queue.get()
        with pytest.raises(queue.Empty):
            self.assoc.dul.queue.get(block=False)

        assert isinstance(primitive, A_RELEASE)
        assert primitive.result == 'affirmative'

    def test_send_accept(self):
        """Test A-ASSOCIATE (ac) construction and sending"""
        acse = ACSE()
        # So we have the request available
        acse.send_request(self.assoc)
        self.assoc.accepted_contexts = [build_context('1.2.840.10008.1.1')]
        acse.send_accept(self.assoc)

        self.assoc.dul.queue.get()  # The request
        primitive = self.assoc.dul.queue.get()
        with pytest.raises(queue.Empty):
            self.assoc.dul.queue.get(block=False)

        assert isinstance(primitive, A_ASSOCIATE)
        assert primitive.application_context_name == '1.2.840.10008.3.1.1.1'
        assert primitive.calling_ae_title == b'TEST_LOCAL      '
        assert primitive.called_ae_title == b'TEST_REMOTE     '
        assert primitive.result == 0x00
        assert primitive.result_source == 0x01

        cx = primitive.presentation_context_definition_results_list
        assert len(cx) == 1
        assert cx[0].abstract_syntax == '1.2.840.10008.1.1'


REFERENCE_USER_IDENTITY_REQUEST = [
    # (Request, response)
    # Request: (ID type, primary field, secondary field, req_response)
    # Response: (is_valid, server response)
    # Username
    # (User ID Type, Primary Field, Secondary Field, Response Requested)
    # (Is valid, positive response value)
    ((1, b'username', b'', False), (True, b'\x01\x01')),
    ((1, b'username', b'', True), (True, b'\x01\x01')),
    ((1, b'username', b'invalid', False), (True, b'\x01\x01')),
    ((1, b'username', b'invalid', True), (True, b'\x01\x01')),
    # Username and password
    ((2, b'username', b'', False), (True, b'\x01\x02')),
    ((2, b'username', b'', True), (True, b'\x01\x02')),
    ((2, b'username', b'password', False), (True, b'\x01\x02')),
    ((2, b'username', b'password', True), (True, b'\x01\x02')),
    # Kerberos service ticket
    ((3, b'\x00\x03', b'', False), (True, b'\x01\x03')),
    ((3, b'\x00\x03', b'', True), (True, b'\x01\x03')),
    ((3, b'\x00\x03', b'invalid', False), (True, b'\x01\x03')),
    ((3, b'\x00\x03', b'invalid', True), (True, b'\x01\x03')),
    # SAML assertion
    ((4, b'\x00\x04', b'', False), (True, b'\x01\x04')),
    ((4, b'\x00\x04', b'', True), (True, b'\x01\x04')),
    ((4, b'\x00\x04', b'invalid', False), (True, b'\x01\x04')),
    ((4, b'\x00\x04', b'invalid', True), (True, b'\x01\x04')),
    # JSON web token
    ((5, b'\x00\x05', b'', False), (True, b'\x01\x05')),
    ((5, b'\x00\x05', b'', True), (True, b'\x01\x05')),
    ((5, b'\x00\x05', b'invalid', False), (True, b'\x01\x05')),
    ((5, b'\x00\x05', b'invalid', True), (True, b'\x01\x05')),
]


class TestUserIdentityNegotiation(object):
    """Tests for User Identity Negotiation."""
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
                thread.close()

    @pytest.mark.parametrize("req, rsp", REFERENCE_USER_IDENTITY_REQUEST)
    def test_check_usrid_not_implemented(self, req, rsp):
        """Check _check_user_identity if user hasn't implemented."""
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        assoc = Association(ae, mode='requestor')

        item = UserIdentityNegotiation()
        item.user_identity_type = req[0]
        item.primary_field = req[1]
        item.secondary_field = req[2]
        item.positive_response_requested = req[3]

        assoc.requestor.add_negotiation_item(item)
        is_valid, response = assoc.acse._check_user_identity(assoc)

        assert is_valid is True
        assert response is None

    @pytest.mark.parametrize("req, rsp", REFERENCE_USER_IDENTITY_REQUEST)
    def test_check_usrid_not_authorised(self, req, rsp):
        """Check _check_user_identity if requestor not authorised"""

        def on_user_identity(usr_type, primary, secondary, info):
            return False, rsp[1]

        scp = AE()
        scp.add_supported_context(VerificationSOPClass)
        scp.on_user_identity = on_user_identity
        server = scp.start_server(('', 11112), block=False)

        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 2
        ae.dimse_timeout = 2
        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established

        item = UserIdentityNegotiation()
        item.user_identity_type = req[0]
        item.primary_field = req[1]
        item.secondary_field = req[2]
        item.positive_response_requested = req[3]

        scp_assoc = scp.active_associations[0]
        scp_assoc.requestor.primitive.user_information.append(item)
        is_valid, response = scp_assoc.acse._check_user_identity(scp_assoc)

        assert is_valid is False
        assert response is None

        assoc.release()

        scp.shutdown()

    @pytest.mark.parametrize("req, rsp", REFERENCE_USER_IDENTITY_REQUEST)
    def test_check_usrid_authorised(self, req, rsp):
        """Check _check_user_identity if requestor authorised"""

        def on_user_identity(usr_type, primary, secondary, info):
            return True, rsp[1]

        scp = AE()
        scp.add_supported_context(VerificationSOPClass)
        scp.on_user_identity = on_user_identity
        server = scp.start_server(('', 11112), block=False)

        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established

        item = UserIdentityNegotiation()
        item.user_identity_type = req[0]
        item.primary_field = req[1]
        item.secondary_field = req[2]
        item.positive_response_requested = req[3]

        scp_assoc = scp.active_associations[0]
        scp_assoc.requestor.primitive.user_information.append(item)
        is_valid, response = scp_assoc.acse._check_user_identity(scp_assoc)

        assert is_valid is True
        if req[3] is True and req[0] in [3, 4, 5]:
            assert isinstance(response, UserIdentityNegotiation)
            assert response.server_response == rsp[1]
        else:
            assert response is None

        assoc.release()

        scp.shutdown()

    def test_check_usrid_callback_exception(self):
        """Check _check_user_identity if exception in callback"""

        def on_user_identity(usr_type, primary, secondary, info):
            raise ValueError()
            return True, rsp[1]

        self.scp = DummyVerificationSCP()
        self.scp.ae.on_user_identity = on_user_identity
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established

        item = UserIdentityNegotiation()
        item.user_identity_type = 1
        item.primary_field = b'test'
        item.secondary_field = b'test'
        item.positive_response_requested = True

        scp_assoc = self.scp.ae.active_associations[0]
        scp_assoc.requestor.primitive.user_information.append(item)
        is_valid, response = scp_assoc.acse._check_user_identity(scp_assoc)

        assert is_valid is False
        assert response is None

        assoc.release()

        self.scp.stop()

    def test_check_usrid_server_response_exception(self):
        """Check _check_user_identity exception in setting server response"""

        def on_user_identity(usr_type, primary, secondary, info):
            return True, 123

        self.scp = DummyVerificationSCP()
        self.scp.ae.on_user_identity = on_user_identity
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established

        item = UserIdentityNegotiation()
        item.user_identity_type = 3
        item.primary_field = b'test'
        item.secondary_field = b'test'
        item.positive_response_requested = True

        scp_assoc = self.scp.ae.active_associations[0]
        scp_assoc.requestor.primitive.user_information.append(item)
        is_valid, response = scp_assoc.acse._check_user_identity(scp_assoc)

        assert is_valid is True
        assert response is None

        assoc.release()

        self.scp.stop()

    @pytest.mark.parametrize("req, rsp", REFERENCE_USER_IDENTITY_REQUEST)
    def test_callback(self, req, rsp):
        """Test the AE.on_user_identity callback"""
        def on_user_identity(usr_type, primary, secondary, info):
            assert usr_type == req[0]
            assert primary == req[1]
            assert secondary == req[2]
            assert 'requestor' in info
            assert 'ae_title' in info['requestor']
            assert 'port' in info['requestor']
            assert 'address' in info['requestor']

            return True, rsp[1]

        self.scp = DummyVerificationSCP()
        self.scp.ae.on_user_identity = on_user_identity
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established

        item = UserIdentityNegotiation()
        item.user_identity_type = req[0]
        item.primary_field = req[1]
        item.secondary_field = req[2]
        item.positive_response_requested = req[3]

        scp_assoc = self.scp.ae.active_associations[0]
        scp_assoc.requestor.primitive.user_information.append(item)
        is_valid, response = scp_assoc.acse._check_user_identity(scp_assoc)
        assert is_valid is True
        if req[3] is True and req[0] in [3, 4, 5]:
            assert isinstance(response, UserIdentityNegotiation)
            assert response.server_response == rsp[1]
        else:
            assert response is None

        assoc.release()

        self.scp.stop()

    def test_functional_authorised_response(self):
        """Test a functional workflow where the user is authorised."""
        def on_user_identity(usr_type, primary, secondary, info):
            return True, b'\x00\x01'

        self.scp = DummyVerificationSCP()
        self.scp.ae.on_user_identity = on_user_identity
        self.scp.start()
        ae = AE()
        ae.on_user_identity = on_user_identity
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        item = UserIdentityNegotiation()
        item.user_identity_type = 3
        item.primary_field = b'test'
        item.secondary_field = b'test'
        item.positive_response_requested = True

        assoc = ae.associate('localhost', 11112, ext_neg=[item])

        assert assoc.is_established

        assoc.release()

        self.scp.stop()

    def test_functional_authorised_no_response(self):
        """Test a functional workflow where the user is authorised."""
        def on_user_identity(usr_type, primary, secondary, info):
            return True, None

        self.scp = DummyVerificationSCP()
        self.scp.ae.acse_timeout = 5
        self.scp.ae.dimse_timeout = 5
        self.scp.ae.network_timeout = 5
        self.scp.ae.on_user_identity = on_user_identity
        self.scp.start()
        ae = AE()
        ae.on_user_identity = on_user_identity
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        item = UserIdentityNegotiation()
        item.user_identity_type = 3
        item.primary_field = b'test'
        item.secondary_field = b'test'
        item.positive_response_requested = True

        assoc = ae.associate('localhost', 11112, ext_neg=[item])

        assert assoc.is_established

        assoc.release()

        self.scp.stop()

    def test_functional_not_authorised(self):
        """Test a functional workflow where the user isn't authorised."""
        def on_user_identity(usr_type, primary, secondary, info):
            return False, None

        self.scp = DummyVerificationSCP()
        self.scp.ae.acse_timeout = 5
        self.scp.ae.dimse_timeout = 5
        self.scp.ae.network_timeout = 5
        self.scp.ae.on_user_identity = on_user_identity
        self.scp.start()
        ae = AE()
        ae.on_user_identity = on_user_identity
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        item = UserIdentityNegotiation()
        item.user_identity_type = 1
        item.primary_field = b'test'
        item.secondary_field = b'test'
        item.positive_response_requested = True

        assoc = ae.associate('localhost', 11112, ext_neg=[item])

        assert assoc.is_rejected

        self.scp.stop()

    def test_req_response_reject(self):
        """Test requestor response if assoc rejected."""
        def on_user_identity(usr_type, primary, secondary, info):
            return True, b'\x00\x01'

        self.scp = DummyVerificationSCP()
        self.scp.ae.require_calling_aet = [b'HAHA NOPE']
        self.scp.ae.on_user_identity = on_user_identity
        self.scp.start()
        ae = AE()
        ae.on_user_identity = on_user_identity
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        item = UserIdentityNegotiation()
        item.user_identity_type = 3
        item.primary_field = b'test'
        item.secondary_field = b'test'
        item.positive_response_requested = True

        assoc = ae.associate('localhost', 11112, ext_neg=[item])

        assert assoc.is_rejected
        assert assoc.acceptor.user_identity is None

        assoc.release()

        self.scp.stop()

    def test_req_response_no_user_identity(self):
        """Test requestor response if no response from acceptor."""
        def on_user_identity(usr_type, primary, secondary, info):
            return True, None

        self.scp = DummyVerificationSCP()
        self.scp.ae.on_user_identity = on_user_identity
        self.scp.start()
        ae = AE()
        ae.on_user_identity = on_user_identity
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        item = UserIdentityNegotiation()
        item.user_identity_type = 3
        item.primary_field = b'test'
        item.secondary_field = b'test'
        item.positive_response_requested = True

        assoc = ae.associate('localhost', 11112, ext_neg=[item])

        assert assoc.is_established
        assert assoc.acceptor.user_identity is None

        assoc.release()

        self.scp.stop()

    def test_req_response_user_identity(self):
        """Test requestor response if assoc rejected."""
        def on_user_identity(usr_type, primary, secondary, info):
            return True, b'\x00\x01'

        self.scp = DummyVerificationSCP()
        self.scp.ae.on_user_identity = on_user_identity
        self.scp.start()
        ae = AE()
        ae.on_user_identity = on_user_identity
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        item = UserIdentityNegotiation()
        item.user_identity_type = 3
        item.primary_field = b'test'
        item.secondary_field = b'test'
        item.positive_response_requested = True

        assoc = ae.associate('localhost', 11112, ext_neg=[item])

        assert assoc.is_established
        assert assoc.acceptor.user_identity.server_response == b'\x00\x01'

        assoc.release()

        self.scp.stop()

    @pytest.mark.parametrize("req, rsp", REFERENCE_USER_IDENTITY_REQUEST)
    def test_logging(self, req, rsp):
        """Test the logging output works with user identity"""
        def on_user_identity(usr_type, primary, secondary, info):
            return True, rsp[1]

        self.scp = DummyVerificationSCP()
        self.scp.ae.acse_timeout = 5
        self.scp.ae.dimse_timeout = 5
        self.scp.ae.network_timeout = 5
        self.scp.ae.on_user_identity = on_user_identity
        self.scp.start()
        ae = AE()
        ae.on_user_identity = on_user_identity
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        item = UserIdentityNegotiation()
        item.user_identity_type = req[0]
        item.primary_field = req[1]
        if req[0] == 2:
            item.secondary_field = req[2] or b'someval'
        else:
            item.secondary_field = req[2]
        item.positive_response_requested = req[3]

        assoc = ae.associate('localhost', 11112, ext_neg=[item])
        if assoc.is_established:
            assoc.release()
        self.scp.stop()


class TestSOPClassExtendedNegotiation(object):
    """Tests for SOP Class Extended Negotiation."""
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

    def test_check_ext_no_req(self):
        """Test the default implementation of on_sop_class_extended"""
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established

        req = {}

        scp_assoc = self.scp.ae.active_associations[0]
        rsp = scp_assoc.acse._check_sop_class_extended(scp_assoc)

        assert rsp == []

    def test_check_ext_default(self):
        """Test the default implementation of on_sop_class_extended"""
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established

        req = {
            '1.2.3' : b'\x00\x01',
            '1.2.4' : b'\x00\x02',
        }

        scp_assoc = self.scp.ae.active_associations[0]
        for kk, vv in req.items():
            item = SOPClassExtendedNegotiation()
            item.sop_class_uid = kk
            item.service_class_application_information = vv
            scp_assoc.requestor.user_information.append(item)

        rsp = scp_assoc.acse._check_sop_class_extended(scp_assoc)

        assert rsp == []

        self.scp.stop()

    def test_check_ext_user_implemented_none(self):
        """Test the default implementation of on_sop_class_extended"""
        def on_ext(req):
            return req

        self.scp = DummyVerificationSCP()
        self.scp.ae.on_sop_class_extended = on_ext
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established

        req = {
            '1.2.3' : b'\x00\x01',
            '1.2.4' : b'\x00\x02',
        }

        scp_assoc = self.scp.ae.active_associations[0]
        for kk, vv in req.items():
            item = SOPClassExtendedNegotiation()
            item.sop_class_uid = kk
            item.service_class_application_information = vv
            scp_assoc.requestor.user_information.append(item)

        rsp = scp_assoc.acse._check_sop_class_extended(scp_assoc)

        assert len(rsp) == 2
        # Can't guarantee order
        for item in rsp:
            if item.sop_class_uid == '1.2.3':
                assert item.service_class_application_information == b'\x00\x01'
            else:
                assert item.sop_class_uid == '1.2.4'
                assert item.service_class_application_information == b'\x00\x02'

        self.scp.stop()

    def test_check_ext_bad_implemented_raises(self):
        """Test the default implementation of on_sop_class_extended"""
        def on_ext(req):
            raise ValueError()

        self.scp = DummyVerificationSCP()
        self.scp.ae.on_sop_class_extended = on_ext
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established

        req = {
            '1.2.3' : b'\x00\x01',
            '1.2.4' : b'\x00\x02',
        }

        scp_assoc = self.scp.ae.active_associations[0]
        for kk, vv in req.items():
            item = SOPClassExtendedNegotiation()
            item.sop_class_uid = kk
            item.service_class_application_information = vv
            scp_assoc.requestor.user_information.append(item)

        rsp = scp_assoc.acse._check_sop_class_extended(scp_assoc)

        assert rsp == []

        self.scp.stop()

    def test_check_ext_bad_implemented_type(self):
        """Test the default implementation of on_sop_class_extended"""
        def on_ext(req):
            return b'\x00\x00'

        self.scp = DummyVerificationSCP()
        self.scp.ae.on_sop_class_extended = on_ext
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established

        req = {
            '1.2.3' : b'\x00\x01',
            '1.2.4' : b'\x00\x02',
        }

        scp_assoc = self.scp.ae.active_associations[0]
        for kk, vv in req.items():
            item = SOPClassExtendedNegotiation()
            item.sop_class_uid = kk
            item.service_class_application_information = vv
            scp_assoc.requestor.user_information.append(item)

        rsp = scp_assoc.acse._check_sop_class_extended(scp_assoc)

        assert rsp == []

        self.scp.stop()

    def test_check_ext_bad_implemented_item_value(self):
        """Test the default implementation of on_sop_class_extended"""
        def on_ext(request):
            out = {}
            for k, v in request.items():
                if k == '1.2.3':
                    out[k] = 1234
                else:
                    out[k] = v

            return out

        self.scp = DummyVerificationSCP()
        self.scp.ae.on_sop_class_extended = on_ext
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established

        req = {
            '1.2.3' : b'\x00\x01',
            '1.2.4' : b'\x00\x02',
        }

        scp_assoc = self.scp.ae.active_associations[0]
        for kk, vv in req.items():
            item = SOPClassExtendedNegotiation()
            item.sop_class_uid = kk
            item.service_class_application_information = vv
            scp_assoc.requestor.user_information.append(item)

        rsp = scp_assoc.acse._check_sop_class_extended(scp_assoc)

        assert len(rsp) == 1
        assert rsp[0].sop_class_uid == '1.2.4'
        assert rsp[0].service_class_application_information == b'\x00\x02'

        self.scp.stop()

    def test_functional_no_response(self):
        """Test a functional workflow with no response."""
        def on_ext(req):
            assert isinstance(req, dict)
            for k, v in req.items():
                if k == '1.2.3':
                    assert v == b'\x00\x01'
                else:
                    assert k == '1.2.4'
                    assert v == b'\x00\x02'

            return None

        self.scp = DummyVerificationSCP()
        self.scp.ae.on_sop_class_extended = on_ext
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        ext_neg = []
        item = SOPClassExtendedNegotiation()
        item.sop_class_uid = '1.2.3'
        item.service_class_application_information = b'\x00\x01'
        ext_neg.append(item)

        item = SOPClassExtendedNegotiation()
        item.sop_class_uid = '1.2.4'
        item.service_class_application_information = b'\x00\x02'
        ext_neg.append(item)

        assoc = ae.associate('localhost', 11112, ext_neg=ext_neg)

        assert assoc.is_established
        assoc.release()

        self.scp.stop()

    def test_functional_response(self):
        """Test a functional workflow with response."""
        def on_ext(req):
            return req

        self.scp = DummyVerificationSCP()
        self.scp.ae.on_sop_class_extended = on_ext
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        ext_neg = []
        item = SOPClassExtendedNegotiation()
        item.sop_class_uid = '1.2.3'
        item.service_class_application_information = b'\x00\x01'
        ext_neg.append(item)

        item = SOPClassExtendedNegotiation()
        item.sop_class_uid = '1.2.4'
        item.service_class_application_information = b'\x00\x02'
        ext_neg.append(item)

        assoc = ae.associate('localhost', 11112, ext_neg=ext_neg)

        assert assoc.is_established
        assoc.release()

        self.scp.stop()

    def test_req_response_reject(self):
        """Test requestor response if assoc rejected."""
        def on_ext(req):
            return req

        self.scp = DummyVerificationSCP()
        self.scp.ae.on_sop_class_extended = on_ext
        self.scp.ae.require_calling_aet = [b'HAHA NOPE']
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        ext_neg = []
        item = SOPClassExtendedNegotiation()
        item.sop_class_uid = '1.2.3'
        item.service_class_application_information = b'\x00\x01'
        ext_neg.append(item)

        item = SOPClassExtendedNegotiation()
        item.sop_class_uid = '1.2.4'
        item.service_class_application_information = b'\x00\x02'
        ext_neg.append(item)

        assoc = ae.associate('localhost', 11112, ext_neg=ext_neg)

        assert assoc.is_rejected
        assert assoc.acceptor.sop_class_extended == {}

        assoc.release()

        self.scp.stop()

    def test_req_response_no_response(self):
        """Test requestor response if no response from acceptor."""
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        ext_neg = []
        item = SOPClassExtendedNegotiation()
        item.sop_class_uid = '1.2.3'
        item.service_class_application_information = b'\x00\x01'
        ext_neg.append(item)

        item = SOPClassExtendedNegotiation()
        item.sop_class_uid = '1.2.4'
        item.service_class_application_information = b'\x00\x02'
        ext_neg.append(item)

        assoc = ae.associate('localhost', 11112, ext_neg=ext_neg)

        assert assoc.is_established
        assert assoc.acceptor.sop_class_extended == {}

        assoc.release()

        self.scp.stop()

    def test_req_response_sop_class_ext(self):
        """Test requestor response if response received."""
        def on_ext(req):
            return req

        self.scp = DummyVerificationSCP()
        self.scp.ae.on_sop_class_extended = on_ext
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        ext_neg = []
        item = SOPClassExtendedNegotiation()
        item.sop_class_uid = '1.2.3'
        item.service_class_application_information = b'\x00\x01'
        ext_neg.append(item)

        item = SOPClassExtendedNegotiation()
        item.sop_class_uid = '1.2.4'
        item.service_class_application_information = b'\x00\x02'
        ext_neg.append(item)

        assoc = ae.associate('localhost', 11112, ext_neg=ext_neg)

        assert assoc.is_established
        rsp = assoc.acceptor.sop_class_extended
        assert '1.2.3' in rsp
        assert '1.2.4' in rsp
        assert len(rsp) == 2
        assert rsp['1.2.3'] == b'\x00\x01'
        assert rsp['1.2.4'] == b'\x00\x02'

        assoc.release()

        self.scp.stop()


class TestSOPClassCommonExtendedNegotiation(object):
    """Tests for SOP Class Extended Negotiation."""
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

    def test_check_ext_no_req(self):
        """Test the default implementation of on_sop_class_common_extended"""
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established

        req = {}

        scp_assoc = self.scp.ae.active_associations[0]
        rsp = scp_assoc.acse._check_sop_class_common_extended(scp_assoc)

        assert rsp == {}

    def test_check_ext_default(self):
        """Test the default implementation of on_sop_class_extended"""
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established

        req = {
            '1.2.3' : ('1.2.840.10008.4.2', []),
            '1.2.3.1' : ('1.2.840.10008.4.2', ['1.1.1', '1.4.2']),
            '1.2.3.4' : ('1.2.111111', []),
            '1.2.3.5' : ('1.2.111111', ['1.2.4', '1.2.840.10008.1.1']),
        }

        scp_assoc = self.scp.ae.active_associations[0]
        items = {}
        for kk, vv in req.items():
            item = SOPClassCommonExtendedNegotiation()
            item.sop_class_uid = kk
            item.service_class_uid = vv[0]
            item.related_general_sop_class_identification = vv[1]
            items[kk] = item

        rsp = scp_assoc.acse._check_sop_class_common_extended(scp_assoc)

        assert rsp == {}

        self.scp.stop()

    def test_check_ext_user_implemented_none(self):
        """Test the default implementation of on_sop_class_common_extended"""
        def on_ext(req):
            return req

        self.scp = DummyVerificationSCP()
        self.scp.ae.on_sop_class_common_extended = on_ext
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established

        req = {
            '1.2.3' : ('1.2.840.10008.4.2', []),
            '1.2.3.1' : ('1.2.840.10008.4.2', ['1.1.1', '1.4.2']),
            '1.2.3.4' : ('1.2.111111', []),
            '1.2.3.5' : ('1.2.111111', ['1.2.4', '1.2.840.10008.1.1']),
        }

        scp_assoc = self.scp.ae.active_associations[0]
        items = {}
        for kk, vv in req.items():
            item = SOPClassCommonExtendedNegotiation()
            item.sop_class_uid = kk
            item.service_class_uid = vv[0]
            item.related_general_sop_class_identification = vv[1]
            items[kk] = item

        scp_assoc.requestor.user_information.extend(items.values())
        rsp = scp_assoc.acse._check_sop_class_common_extended(scp_assoc)
        assert rsp == items

        self.scp.stop()

    def test_check_ext_bad_implemented_raises(self):
        """Test the default implementation of on_sop_class_extended"""
        def on_ext(req):
            raise ValueError()

        self.scp = DummyVerificationSCP()
        self.scp.ae.on_sop_class_common_extended = on_ext
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established

        req = {
            '1.2.3' : ('1.2.840.10008.4.2', []),
            '1.2.3.1' : ('1.2.840.10008.4.2', ['1.1.1', '1.4.2']),
            '1.2.3.4' : ('1.2.111111', []),
            '1.2.3.5' : ('1.2.111111', ['1.2.4', '1.2.840.10008.1.1']),
        }

        scp_assoc = self.scp.ae.active_associations[0]
        items = {}
        for kk, vv in req.items():
            item = SOPClassCommonExtendedNegotiation()
            item.sop_class_uid = kk
            item.service_class_uid = vv[0]
            item.related_general_sop_class_identification = vv[1]
            items[kk] = item

        scp_assoc.requestor.user_information.extend(items.values())
        rsp = scp_assoc.acse._check_sop_class_common_extended(scp_assoc)

        assert rsp == {}

        self.scp.stop()

    def test_check_ext_bad_implemented_type(self):
        """Test the default implementation of on_sop_class_extended"""
        def on_ext(req):
            return b'\x00\x00'

        self.scp = DummyVerificationSCP()
        self.scp.ae.on_sop_class_extended = on_ext
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established

        req = {
            '1.2.3' : ('1.2.840.10008.4.2', []),
            '1.2.3.1' : ('1.2.840.10008.4.2', ['1.1.1', '1.4.2']),
            '1.2.3.4' : ('1.2.111111', []),
            '1.2.3.5' : ('1.2.111111', ['1.2.4', '1.2.840.10008.1.1']),
        }

        scp_assoc = self.scp.ae.active_associations[0]
        items = {}
        for kk, vv in req.items():
            item = SOPClassCommonExtendedNegotiation()
            item.sop_class_uid = kk
            item.service_class_uid = vv[0]
            item.related_general_sop_class_identification = vv[1]
            items[kk] = item

        scp_assoc.requestor.user_information.extend(items.values())
        rsp = scp_assoc.acse._check_sop_class_common_extended(scp_assoc)

        assert rsp == {}

        self.scp.stop()

    def test_functional_no_response(self):
        """Test a functional workflow with no response."""
        def on_ext(req):
            return {}

        self.scp = DummyVerificationSCP()
        self.scp.ae.on_sop_class_common_extended = on_ext
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
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
        assert assoc.acceptor.accepted_common_extended == {}
        scp_assoc = self.scp.ae.active_associations[0]
        assert scp_assoc.acceptor.accepted_common_extended == {}
        assoc.release()

        self.scp.stop()

    def test_functional_response(self):
        """Test a functional workflow with response."""
        def on_ext(req):
            del req['1.2.3.1']
            return req

        self.scp = DummyVerificationSCP()
        self.scp.ae.on_sop_class_common_extended = on_ext
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
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

        scp_assoc = self.scp.ae.active_associations[0]
        acc = scp_assoc.acceptor.accepted_common_extended
        assert len(acc) == 3
        assert acc['1.2.3'] == req['1.2.3']
        assert acc['1.2.3.4'] == req['1.2.3.4']
        assert acc['1.2.3.5'] == req['1.2.3.5']

        assoc.release()

        self.scp.stop()


class TestAsyncOpsNegotiation(object):
    """Tests for Asynchronous Operations Window Negotiation."""
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

    def test_check_async_no_req(self):
        """Test the default implementation of on_async_ops_window"""
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established

        scp_assoc = self.scp.ae.active_associations[0]
        rsp = scp_assoc.acse._check_async_ops(scp_assoc)

        assert rsp is None

    def test_check_user_implemented_none(self):
        """Test the response when user callback returns values."""
        def on_async(invoked, performed):
            return 1, 2

        self.scp = DummyVerificationSCP()
        self.scp.ae.on_async_ops_window = on_async
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established

        scp_assoc = self.scp.ae.active_associations[0]
        rsp = scp_assoc.acse._check_async_ops(scp_assoc)

        assert isinstance(rsp, AsynchronousOperationsWindowNegotiation)
        assert rsp.maximum_number_operations_invoked == 1
        assert rsp.maximum_number_operations_performed == 1

        self.scp.stop()

    def test_check_ext_user_implemented_raises(self):
        """Test the response when the user callback raises exception."""
        def on_async(invoked, performed):
            raise ValueError

        self.scp = DummyVerificationSCP()
        self.scp.ae.on_async_ops_window = on_async
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established

        scp_assoc = self.scp.ae.active_associations[0]
        rsp = scp_assoc.acse._check_async_ops(scp_assoc)

        assert isinstance(rsp, AsynchronousOperationsWindowNegotiation)
        assert rsp.maximum_number_operations_invoked == 1
        assert rsp.maximum_number_operations_performed == 1

        self.scp.stop()

    def test_req_response_reject(self):
        """Test requestor response if assoc rejected."""
        def on_async(inv, perf):
            return inv, perf

        self.scp = DummyVerificationSCP()
        self.scp.ae.on_async_ops_window = on_async
        self.scp.ae.require_calling_aet = [b'HAHA NOPE']
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        ext_neg = []
        item = AsynchronousOperationsWindowNegotiation()
        item.maximum_number_operations_invoked = 0
        item.maximum_number_operations_performed = 1
        ext_neg.append(item)

        assoc = ae.associate('localhost', 11112, ext_neg=ext_neg)

        assert assoc.is_rejected
        assert assoc.acceptor.asynchronous_operations == (1, 1)

        assoc.release()

        self.scp.stop()

    def test_req_response_no_response(self):
        """Test requestor response if no response from acceptor."""
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        ext_neg = []
        item = AsynchronousOperationsWindowNegotiation()
        item.maximum_number_operations_invoked = 0
        item.maximum_number_operations_performed = 1
        ext_neg.append(item)

        assoc = ae.associate('localhost', 11112, ext_neg=ext_neg)

        assert assoc.is_established
        assert assoc.acceptor.asynchronous_operations == (1, 1)

        assoc.release()

        self.scp.stop()

    def test_req_response_async(self):
        """Test requestor response if response received"""
        def on_async(inv, perf):
            return inv, perf

        self.scp = DummyVerificationSCP()
        self.scp.ae.on_async_ops_window = on_async
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        ext_neg = []
        item = AsynchronousOperationsWindowNegotiation()
        item.maximum_number_operations_invoked = 0
        item.maximum_number_operations_performed = 2
        ext_neg.append(item)

        assoc = ae.associate('localhost', 11112, ext_neg=ext_neg)

        assert assoc.is_established
        # Because pynetdicom doesn't support async ops this is always 1, 1
        assert assoc.acceptor.asynchronous_operations == (1, 1)

        assoc.release()

        self.scp.stop()


class SmallReleaseCollider(threading.Thread):
    def __init__(self, port=11112):
        self.queue = queue.Queue()
        self._kill = False
        self.socket = socket.socket
        self.address = ''
        self.local_port = port
        self.remote_port = None
        self.received = []
        self.mode = 'requestor'
        self._step = 0
        self._event = threading.Event()

        threading.Thread.__init__(self)
        self.daemon = True

    def bind_socket(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # SOL_SOCKET: the level, SO_REUSEADDR: allow reuse of a port
        #   stuck in TIME_WAIT, 1: set SO_REUSEADDR to 1
        # This must be called prior to socket.bind()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(
            socket.SOL_SOCKET, socket.SO_RCVTIMEO, pack('ll', 10, 0)
        )

        # Bind the socket to an address and port
        #   If self.bind_addr is '' then the socket is reachable by any
        #   address the machine may have, otherwise is visible only on that
        #   address
        sock.bind(('', self.local_port))

        # Listen for connections made to the socket
        # socket.listen() says to queue up to as many as N connect requests
        #   before refusing outside connections
        sock.listen(1)
        return sock

    def run(self):
        if self.mode == 'acceptor':
            self.run_as_acceptor()
        elif self.mode == 'requestor':
            self.run_as_requestor()

    def run_as_acceptor(self):
        """Run the Collider as an association requestor.

        1. Open a list socket on self.local_port
        2. Wait for a connection request, when connected GOTO 3
        3. Check self.queue for an item:
            a. If the item is None then GOTO 4
            b. If the item is singleton then send it to the peer and GOTO 4
            c. If the item is a list then send each item in the list to the
               peer, then GOTO 4. if one of the items is 'shutdown' then exit
            d. If the item is 'shutdown' then exit
        4. Block the connection until data appears, then append the data to
           self.received.
        """
        sock = self.bind_socket()
        self.sock = sock

        # Wait for a connection
        while not self._kill:
            ready, _, _ = select.select([sock], [], [], 0.5)
            if ready:
                conn, _ = sock.accept()
                break

        # Send and receive data
        while not self._kill:
            to_send = self.queue.get()
            if to_send == 'shutdown':
                # 'shutdown'
                self.sock.shutdown(socket.SHUT_RDWR)
                self.sock.close()
                self._kill = True
                return
            elif to_send is not None:
                # item or [item, item]
                if isinstance(to_send, list):
                    for item in to_send:
                        if item == 'shutdown':
                            self.sock.shutdown(socket.SHUT_RDWR)
                            self.sock.close()
                            self._kill = True
                            return
                        elif item == None:
                            continue
                        else:
                            conn.send(item)
                else:
                    conn.send(to_send)
            elif to_send == 'skip':
                continue
            else:
                # None
                pass

            # Block until ready to read
            ready, _, _ = select.select([conn], [], [])
            if ready:
                data_received = self.read_stream(conn)
                self.received.append(data_received)

    def run_as_requestor(self):
        """Run the Collider as an association requestor.

        1. Open a connection to the peer at (self.address, self.remote_port)
        2. Check self.queue for an item:
            a. If the item is None then GOTO 3
            b. If the item is singleton then send it to the peer and GOTO 3
            c. If the item is a list then send each item in the list to the
               peer, then GOTO 3
            d. If the item is 'shutdown' then exit
        3. Block the connection until data appears, then append the data to
           self.received.
        """
        # Make the connection
        while not self._kill:
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.connect((self.address, self.remote_port))
                break
            except:
                pass

        # Send and receive data
        while not self._kill:
            to_send = self.queue.get()
            if to_send == 'shutdown':
                # 'shutdown'
                self.sock.shutdown(socket.SHUT_RDWR)
                self.sock.close()
                self._kill = True
                return
            elif to_send is not None:
                # item or [item, item]
                if isinstance(to_send, list):
                    for item in to_send:
                        self.sock.send(item)
                else:
                    self.sock.send(to_send)
            else:
                # None
                pass

            # Block until ready
            # When the timeout argument is omitted the function blocks until
            #   at least one file descriptor is ready
            ready, _, _ = select.select([self.sock], [], [])
            if ready:
                data_received = self.read_stream(self.sock)
                self.received.append(data_received)

    def read_stream(self, sock):
        bytestream = bytes()

        # Try and read data from the socket
        try:
            # Get the data from the socket
            bytestream = sock.recv(1)
        except socket.error:
            self._kill = True
            sock.close()
            return

        pdu_type = unpack('B', bytestream)[0]

        # Byte 2 is Reserved
        result = self._recvn(sock, 1)
        bytestream += result

        # Bytes 3-6 is the PDU length
        result = unpack('B', result)
        length = self._recvn(sock, 4)

        bytestream += length
        length = unpack('>L', length)

        # Bytes 7-xxxx is the rest of the PDU
        result = self._recvn(sock, length[0])
        bytestream += result

        return bytestream

    @staticmethod
    def _recvn(sock, n_bytes):
        """Read `n_bytes` from a socket.

        Parameters
        ----------
        sock : socket.socket
            The socket to read from
        n_bytes : int
            The number of bytes to read
        """
        ret = b''
        read_length = 0
        while read_length < n_bytes:
            tmp = sock.recv(n_bytes - read_length)

            if not tmp:
                return ret

            ret += tmp
            read_length += len(tmp)

        if read_length != n_bytes:
            raise RuntimeError("_recvn(socket, {}) - Error reading data from "
                               "socket.".format(n_bytes))

        return ret

    def stop(self):
        self._kill = True

    def shutdown_sockets(self):
        """Close the sockets."""
        self.sock.shutdown(socket.SHUT_RDWR)
        self.sock.close()


class TestNegotiateRelease(object):
    """Tests for ACSE.negotiate_release."""
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

    @pytest.mark.skipif(sys.version_info[:2] == (3, 4), reason='no caplog')
    def test_collision_requestor(self, caplog):
        """Test a simulated A-RELEASE collision on the requestor side."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            scp = SmallReleaseCollider()
            scp.mode = 'acceptor'
            scp_messages = [
                None, a_associate_ac, a_release_rq, [a_release_rp, 'shutdown']
            ]
            for item in scp_messages:
                scp.queue.put(item)
            scp.start()

            ae = AE()
            ae.add_requested_context(VerificationSOPClass)
            assoc = ae.associate('localhost', 11112)
            assert assoc.is_established
            assoc.release()
            assert assoc.is_released
            assert not assoc.is_established

            scp.stop()

            assert scp.received[1] == a_release_rq
            assert scp.received[2] == a_release_rp

            assert "An A-RELEASE collision has occurred" in caplog.text

    def test_release_no_response(self):
        """Test a simulated A-RELEASE collision on the requestor side."""
        scp = SmallReleaseCollider()
        scp.mode = 'acceptor'
        scp_messages = [None, a_associate_ac, None, 'shutdown']
        for item in scp_messages:
            scp.queue.put(item)
        scp.start()

        ae = AE()
        ae.acse_timeout = 1
        ae.add_requested_context(VerificationSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assoc.release()
        assert assoc.is_aborted
        assert not assoc.is_established

        time.sleep(0.5)

        assert scp.received[1] == a_release_rq
        assert scp.received[2] == a_p_abort[:-1] + b'\x00'

        scp.stop()

    @pytest.mark.skipif(sys.version_info[:2] == (3, 4), reason='no caplog')
    def test_release_p_data(self, caplog):
        """Test a receiving P-DATA-TF after release."""
        with caplog.at_level(logging.WARNING, logger='pynetdicom'):
            scp = SmallReleaseCollider()
            scp.mode = 'acceptor'
            scp_messages = [
                None, a_associate_ac, [p_data_tf, a_release_rp , 'shutdown'],
            ]
            for item in scp_messages:
                scp.queue.put(item)
            scp.start()

            ae = AE()
            ae.acse_timeout = 2
            ae.add_requested_context(VerificationSOPClass)
            assoc = ae.associate('localhost', 11112)
            assert assoc.is_established
            assoc.release()
            assert assoc.is_released
            assert not assoc.is_established

            assert scp.received[1] == a_release_rq

            scp._kill = True
            scp.queue.put(None)
            scp.stop()

            assert (
                "P-DATA received after Association release, data has been lost"
            ) in caplog.text

    @pytest.mark.skipif(sys.version_info[:2] == (3, 4), reason='no caplog')
    def test_collision_acceptor(self, caplog):
        """Test a simulated A-RELEASE collision on the acceptor side."""
        # Listening on port 11112
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            def on_c_echo(cx, info):
                assoc = self.scp.ae.active_associations[0]
                assoc.release()
                return 0x0000

            self.scp = DummyVerificationSCP()
            self.scp.ae.acse_timeout = 1
            self.scp.ae.dimse_timeout = 5
            self.scp.ae.network_timeout = 5
            self.scp.ae.on_c_echo = on_c_echo
            self.scp.start()

            # C-ECHO-RQ
            # 80 total length
            p_data_tf = (
                b"\x04\x00\x00\x00\x00\x4a" # P-DATA-TF 74
                b"\x00\x00\x00\x46\x01" # PDV Item 70
                b"\x03"  # PDV: 2 -> 69
                b"\x00\x00\x00\x00\x04\x00\x00\x00\x42\x00\x00\x00"  # 12 Command Group Length
                b"\x00\x00\x02\x00\x12\x00\x00\x00\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x31\x2e\x31\x00"  # 26
                b"\x00\x00\x00\x01\x02\x00\x00\x00\x30\x00"  # 10 Command Field
                b"\x00\x00\x10\x01\x02\x00\x00\x00\x01\x00"  # 10 Message ID
                b"\x00\x00\x00\x08\x02\x00\x00\x00\x01\x01"  # 10 Command Data Set Type
            )

            scu = SmallReleaseCollider()
            scu.mode = 'requestor'
            scu.address = 'localhost'
            scu.local_port = 0
            scu.remote_port = 11112
            msgs = [
                a_associate_rq,
                p_data_tf,
                [a_release_rq, a_release_rp],
                'shutdown'
            ]
            for msg in msgs:
                scu.queue.put(msg)

            # Blocking
            scu.run_as_requestor()

            self.scp.stop()

            assert "An A-RELEASE collision has occurred" in caplog.text

            # A-ASSOCIATE-RQ
            assert scu.received[1] == (
                b'\x05\x00\x00\x00\x00\x04\x00\x00\x00\x00'
            )
            # A-ASSOCIATE-RP
            assert scu.received[2] == (
                b'\x06\x00\x00\x00\x00\x04\x00\x00\x00\x00'
            )

    @pytest.mark.skipif(sys.version_info[:2] == (3, 4), reason='no caplog')
    def test_collision_requestor_abort(self, caplog):
        """Test a simulated A-RELEASE collision on the requestor side."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            scp = SmallReleaseCollider()
            scp.mode = 'acceptor'
            scp_messages = [
                None, a_associate_ac, a_release_rq, a_abort, 'shutdown'
            ]
            for item in scp_messages:
                scp.queue.put(item)
            scp.start()

            ae = AE()
            ae.add_requested_context(VerificationSOPClass)
            assoc = ae.associate('localhost', 11112)
            assert assoc.is_established
            assoc.release()
            assert assoc.is_aborted
            assert not assoc.is_established

            scp.stop()

            assert scp.received[1] == a_release_rq
            assert scp.received[2] == a_release_rp

            assert "An A-RELEASE collision has occurred" in caplog.text

    @pytest.mark.skipif(sys.version_info[:2] == (3, 4), reason='no caplog')
    def test_collision_requestor_ap_abort(self, caplog):
        """Test a simulated A-RELEASE collision on the requestor side."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            scp = SmallReleaseCollider()
            scp.mode = 'acceptor'
            scp_messages = [
                None, a_associate_ac, a_release_rq, a_p_abort, 'shutdown'
            ]
            for item in scp_messages:
                scp.queue.put(item)
            scp.start()

            ae = AE()
            ae.add_requested_context(VerificationSOPClass)
            assoc = ae.associate('localhost', 11112)
            assert assoc.is_established
            assoc.release()
            assert assoc.is_aborted
            assert not assoc.is_established

            scp.stop()

            assert scp.received[1] == a_release_rq
            assert scp.received[2] == a_release_rp

            assert "An A-RELEASE collision has occurred" in caplog.text
