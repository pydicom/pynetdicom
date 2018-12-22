"""Tests for association.AcceptorRequestor."""

import logging
import time
import threading

import pytest

from pynetdicom3 import (
    AE, VerificationPresentationContexts, PYNETDICOM_IMPLEMENTATION_UID,
    PYNETDICOM_IMPLEMENTATION_VERSION, build_context
)
from pynetdicom3.association import ServiceUser
from pynetdicom3.pdu_primitives import (
    A_ASSOCIATE, MaximumLengthNotification, ImplementationClassUIDNotification,
    ImplementationVersionNameNotification, SCP_SCU_RoleSelectionNegotiation,
    UserIdentityNegotiation, SOPClassExtendedNegotiation,
    SOPClassCommonExtendedNegotiation, AsynchronousOperationsWindowNegotiation
)
from pynetdicom3.sop_class import VerificationSOPClass

from .dummy_c_scp import DummyVerificationSCP, DummyBaseSCP


LOGGER = logging.getLogger('pynetdicom3')
LOGGER.setLevel(logging.CRITICAL)
#LOGGER.setLevel(logging.DEBUG)


class TestAcceptor(object):
    """Tests for ServiceUser as acceptor."""
    def test_init(self):
        """Test new ServiceUser as acceptor."""
        assoc_role = ServiceUser(mode='acceptor')

        assert assoc_role.primitive is None
        assert assoc_role.ae_title == b''
        assert assoc_role.port is None
        assert assoc_role.address == ''
        assert assoc_role._contexts == []
        assert assoc_role.mode == 'acceptor'
        assert assoc_role.maximum_length == 16382
        assert assoc_role._max_length == 16382
        assert assoc_role._ext_neg == []
        assert assoc_role.extended_negotiation == []


class TestRequestor(object):
    """Tests for ServiceUser as requestor."""
    def setup(self):
        primitive = A_ASSOCIATE()
        primitive.application_context_name = '1.2.840.10008.3.1.1.1'
        primitive.calling_ae_title = b'LOCAL_AE_TITLE  '
        primitive.called_ae_title = b'REMOTE_AE_TITLE '
        primitive.calling_presentation_address = ('127.0.0.1', 11112)
        primitive.called_presentation_address = ('127.0.0.2', 11113)

        # Presentation Contexts
        cx = build_context('1.2.840.10008.1.1')
        cx.context_id = 1
        primitive.presentation_context_definition_list = [cx]

        # User Information items
        item = MaximumLengthNotification()
        item.maximum_length_received = 16382
        primitive.user_information = [item]

        item = ImplementationClassUIDNotification()
        item.implementation_class_uid = '1.2.3'
        primitive.user_information.append(item)

        self.primitive = primitive

    def test_init(self):
        """Test new ServiceUser as requestor."""
        assoc_role = ServiceUser(mode='requestor')

        assert assoc_role.primitive is None
        assert assoc_role.ae_title == b''
        assert assoc_role.port is None
        assert assoc_role.address == ''
        assert assoc_role._contexts == []
        assert assoc_role.mode == 'requestor'
        assert assoc_role.maximum_length == 16382
        assert assoc_role._max_length == 16382
        assert assoc_role.extended_negotiation == []
        assert assoc_role._ext_neg == []

    def test_assignment(self):
        """Test that assignment works OK,"""
        assoc_role = ServiceUser(mode='requestor')

        assert assoc_role.primitive is None
        assert assoc_role.ae_title == b''
        assert assoc_role.port is None
        assert assoc_role.address == ''
        assert assoc_role._contexts == []
        assert assoc_role.mode == 'requestor'
        assert assoc_role.maximum_length == 16382
        assert assoc_role.extended_negotiation == []

        assoc_role.ae_title = b'TEST_AE_TITLE'
        assoc_role.port = 11112
        assoc_role.address = '127.9.9.1'
        assoc_role._contexts = [1]
        assoc_role.maximum_length = 16383
        assoc_role.extended_negotiation = [1234]

        assert assoc_role.ae_title == b'TEST_AE_TITLE'
        assert assoc_role.port == 11112
        assert assoc_role.address == '127.9.9.1'
        assert assoc_role._contexts == [1]
        assert assoc_role.maximum_length == 16383
        assert assoc_role.extended_negotiation == [1234]

    def test_mode_assignment_raises(self):
        """Test that assigning mode after init raises exception."""
        assocer = ServiceUser(mode='requestor')
        assert assocer.mode == 'requestor'
        with pytest.raises(AttributeError, match=r"can't set attribute"):
            assocer.mode = 'acceptor'

        assert assocer.mode == 'requestor'

    def test_minimal(self):
        """Test access with a miminal allowed A-ASSOCIATE primitive."""
        assocer = ServiceUser(mode='requestor')
        assocer.primitive = self.primitive

        assert assocer.primitive == self.primitive
        assert assocer.mode == 'requestor'
        assert assocer.maximum_length == 16382
        assert assocer.implementation_class_uid == '1.2.3'
        assert assocer.implementation_version_name is None
        assert assocer.asynchronous_operations == (1, 1)
        assert assocer.role_selection == {}
        assert assocer.sop_class_common_extended == {}
        assert assocer.sop_class_extended == {}
        assert assocer.user_identity is None

    def test_full(self):
        """Test access with a maximum allowed A-ASSOCIATE primitive."""
        assocer = ServiceUser(mode='requestor')

        item = ImplementationVersionNameNotification()
        item.implementation_version_name = 'VERSION_1'
        self.primitive.user_information.append(item)

        for uid in ['1.2', '3.4']:
            item = SCP_SCU_RoleSelectionNegotiation()
            item.sop_class_uid = uid
            item.scu_role = False
            item.scp_role = True
            self.primitive.user_information.append(item)

        item = AsynchronousOperationsWindowNegotiation()
        item.maximum_number_operations_invoked = 2
        item.maximum_number_operations_performed = 3
        self.primitive.user_information.append(item)

        item = UserIdentityNegotiation()
        item.user_identity_type = 0x01
        item.positive_response_requested = True
        item.primary_field = b'username'
        self.primitive.user_information.append(item)

        item = SOPClassExtendedNegotiation()
        item.sop_class_uid = '1.2.3'
        item.service_class_application_information = b'SOME DATA'
        self.primitive.user_information.append(item)

        item = SOPClassCommonExtendedNegotiation()
        item.sop_class_uid = '1.2.3'
        item.service_class_uid = '2.3.4'
        item.related_general_sop_class_identification = ['1.3.4']
        self.primitive.user_information.append(item)

        assocer.primitive = self.primitive

        assert assocer.maximum_length == 16382
        assert assocer.implementation_class_uid == '1.2.3'
        assert assocer.implementation_version_name == 'VERSION_1'
        assert assocer.asynchronous_operations == (2, 3)

        roles = assocer.role_selection
        assert len(roles) == 2
        role = roles['1.2']
        assert role.scu_role is False
        assert role.scp_role is True

        classes = assocer.sop_class_extended
        assert len(classes) == 1
        assert classes['1.2.3'].service_class_application_information == (
            b'SOME DATA'
        )

        classes = assocer.sop_class_common_extended
        assert len(classes) == 1
        assert classes['1.2.3'].service_class_uid == '2.3.4'
        assert classes['1.2.3'].related_general_sop_class_identification == [
            '1.3.4'
        ]

        item = assocer.user_identity
        assert item.user_identity_type == 0x01
        assert item.primary_field == b'username'

    def test_info(self):
        """Test the .info propoerty"""
        assocer = ServiceUser(mode='requestor')
        info = assocer.info

        assert info['port'] is None
        assert info['mode'] == 'requestor'
        assert info['address'] == ''
        assert info['ae_title'] == b''
        with pytest.raises(KeyError):
            info['pdv_size']

        assocer.primitive = self.primitive
        assert assocer.info['pdv_size'] == 16382

    def test_primitive_assignment_raises(self):
        """Test trying to set primitive parameters raises exception."""
        assocer = ServiceUser(mode='requestor')
        assocer.primitive = self.primitive

        assert assocer.primitive == self.primitive
        assert assocer.mode == 'requestor'

        msg = r"Can't set the Maximum Length after negotiation has started"
        with pytest.raises(RuntimeError, match=msg):
            assocer.maximum_length = 16382

        with pytest.raises(AttributeError, match=r"can't set attribute"):
            assocer.implementation_class_uid = '1.2.3'

        with pytest.raises(AttributeError, match=r"can't set attribute"):
            assocer.implementation_version_name = '1.2.3'

        with pytest.raises(AttributeError, match=r"can't set attribute"):
            assocer.asynchronous_operations = (1, 1)

        with pytest.raises(AttributeError, match=r"can't set attribute"):
            assocer.role_selection = {}

        with pytest.raises(AttributeError, match=r"can't set attribute"):
            assocer.sop_class_common_extended = {}

        with pytest.raises(AttributeError, match=r"can't set attribute"):
            assocer.sop_class_extended = {}

        with pytest.raises(AttributeError, match=r"can't set attribute"):
            assocer.user_identity = 'test'

        msg = (
            r"Can't set the Extended Negotiation items after negotiation "
            "has started"
        )
        with pytest.raises(RuntimeError, match=msg):
            assocer.extended_negotiation = []
