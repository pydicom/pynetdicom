"""Tests for association.AcceptorRequestor."""

import pytest

from pynetdicom import (
    AE,
    PYNETDICOM_IMPLEMENTATION_UID,
    build_context,
    debug_logger,
)
from pynetdicom.association import ServiceUser, Association
from pynetdicom.pdu_primitives import (
    A_ASSOCIATE,
    MaximumLengthNotification,
    ImplementationClassUIDNotification,
    ImplementationVersionNameNotification,
    SCP_SCU_RoleSelectionNegotiation,
    UserIdentityNegotiation,
    SOPClassExtendedNegotiation,
    SOPClassCommonExtendedNegotiation,
    AsynchronousOperationsWindowNegotiation,
)
from pynetdicom.sop_class import Verification
from pynetdicom.transport import AddressInformation


# debug_logger()


class TestServiceUserAcceptor:
    """Tests for ServiceUser as acceptor."""

    def setup_method(self):
        self.assoc = Association(AE(), mode="requestor")

        primitive = A_ASSOCIATE()
        primitive.application_context_name = "1.2.840.10008.3.1.1.1"
        primitive.calling_ae_title = "LOCAL_AE_TITLE  "
        primitive.called_ae_title = "REMOTE_AE_TITLE "
        primitive.result = 0x00
        primitive.result_source = 0x01

        # Presentation Contexts
        cx = build_context("1.2.840.10008.1.1")
        cx.context_id = 1
        primitive.presentation_context_definition_results_list = [cx]

        # User Information items
        item = MaximumLengthNotification()
        item.maximum_length_received = 16383
        primitive.user_information = [item]

        item = ImplementationClassUIDNotification()
        item.implementation_class_uid = "1.2.3"
        primitive.user_information.append(item)

        self.primitive_ac = primitive

        primitive = A_ASSOCIATE()
        primitive.result = 0x01
        primitive.result_source = 0x01
        primitive.diagnostic = 0x01
        self.primitive_rj = primitive

        primitive = A_ASSOCIATE()
        primitive.application_context_name = "1.2.840.10008.3.1.1.1"
        primitive.calling_ae_title = "LOCAL_AE_TITLE  "
        primitive.called_ae_title = "REMOTE_AE_TITLE "
        primitive.calling_presentation_address = AddressInformation("127.0.0.1", 11112)
        primitive.called_presentation_address = AddressInformation("127.0.0.2", 11113)

        # Presentation Contexts
        cx = build_context("1.2.840.10008.1.1")
        cx.context_id = 1
        primitive.presentation_context_definition_list = [cx]

        # User Information items
        item = MaximumLengthNotification()
        item.maximum_length_received = 16382
        primitive.user_information = [item]

        item = ImplementationClassUIDNotification()
        item.implementation_class_uid = "1.2.3"
        primitive.user_information.append(item)

        self.primitive_rq = primitive

    def test_init(self):
        """Test new ServiceUser as acceptor."""
        user = ServiceUser(self.assoc, mode="acceptor")

        assert user.primitive is None
        assert user.ae_title == ""
        with pytest.raises(ValueError, match="No address info"):
            user.port

        with pytest.raises(ValueError, match="No address info"):
            user.address

        assert user.address_info is None
        assert user._contexts == []
        assert user.mode == "acceptor"
        assert user.maximum_length == 16382
        assert user.extended_negotiation == []
        assert user.implementation_class_uid == PYNETDICOM_IMPLEMENTATION_UID

        assert len(user.user_information) == 2

    def test_bad_mode(self):
        """Test bad mode raises exception."""
        with pytest.raises(ValueError, match=r"The 'mode' must be either"):
            ServiceUser(None, "something")

    def test_no_implementation_class_uid(self):
        """Test correct return if no class UID."""
        user = ServiceUser(self.assoc, mode="acceptor")
        user._user_info = []
        assert user.implementation_class_uid is None

    def test_no_maximum_len(self):
        """Test correct return if no maximum length."""
        user = ServiceUser(self.assoc, mode="acceptor")
        user._user_info = []
        assert user.maximum_length is None

    def test_accepted_common(self):
        """Test accepted_common_extended works correctly."""
        user = ServiceUser(self.assoc, "acceptor")

        item = SOPClassCommonExtendedNegotiation()
        item.sop_class_uid = "1.2.3"
        item.service_class_uid = "2.3.4"
        item.related_general_sop_class_identification = ["1.3.4"]

        user._common_ext = {item.sop_class_uid: item}

        out = user.accepted_common_extended
        assert out[item.sop_class_uid] == (
            item.service_class_uid,
            item.related_general_sop_class_identification,
        )

    def test_assignment(self):
        """Test that assignment works OK,"""
        user = ServiceUser(self.assoc, mode="acceptor")

        assert user.primitive is None
        assert user.ae_title == ""
        with pytest.raises(ValueError, match="No address info"):
            user.port

        with pytest.raises(ValueError, match="No address info"):
            user.address

        assert user.address_info is None
        assert user._contexts == []
        assert user.mode == "acceptor"
        assert user.maximum_length == 16382
        assert user.extended_negotiation == []
        assert user.implementation_class_uid == PYNETDICOM_IMPLEMENTATION_UID

        user.ae_title = "TEST_AE_TITLE"
        user.address_info = AddressInformation("127.9.9.1", 11112)
        user._contexts = [1]
        user.maximum_length = 16383

        assert user.ae_title == "TEST_AE_TITLE"
        assert user.port == 11112
        assert user.address == "127.9.9.1"
        assert user.address_info.as_tuple == ("127.9.9.1", 11112)
        assert user._contexts == [1]
        assert user.maximum_length == 16383

    def test_mode_assignment_raises(self):
        """Test that assigning mode after init raises exception."""
        user = ServiceUser(self.assoc, mode="acceptor")
        assert user.mode == "acceptor"
        with pytest.raises(AttributeError, match=r"can't set attribute|has no setter"):
            user.mode = "requestor"

        assert user.mode == "acceptor"

    def test_minimal_ac(self):
        """Test access with a minimal allowed A-ASSOCIATE (ac) primitive."""
        user = ServiceUser(self.assoc, mode="acceptor")
        user.primitive = self.primitive_ac

        assert user.writeable is False
        assert user.primitive == self.primitive_ac
        assert user.mode == "acceptor"
        assert user.maximum_length == 16383
        assert user.implementation_class_uid == "1.2.3"
        assert user.implementation_version_name is None
        assert user.asynchronous_operations == (1, 1)
        assert user.role_selection == {}
        assert user.sop_class_common_extended == {}
        assert user.sop_class_extended == {}
        assert user.user_identity is None

    def test_minimal_rj(self):
        """Test access with a minimal allowed A-ASSOCIATE (rj) primitive."""
        user = ServiceUser(self.assoc, mode="acceptor")
        user.primitive = self.primitive_rj

        assert user.writeable is False
        assert user.primitive == self.primitive_rj
        assert user.mode == "acceptor"
        assert user.maximum_length is None
        assert user.implementation_class_uid is None
        assert user.implementation_version_name is None
        assert user.asynchronous_operations == (1, 1)
        assert user.role_selection == {}
        assert user.sop_class_common_extended == {}
        assert user.sop_class_extended == {}
        assert user.user_identity is None

    def test_full(self):
        """Test access with a maximum allowed A-ASSOCIATE primitive."""
        user = ServiceUser(self.assoc, mode="acceptor")

        item = ImplementationVersionNameNotification()
        item.implementation_version_name = "VERSION_1"
        self.primitive_ac.user_information.append(item)

        for uid in ["1.2", "3.4"]:
            item = SCP_SCU_RoleSelectionNegotiation()
            item.sop_class_uid = uid
            item.scu_role = False
            item.scp_role = True
            self.primitive_ac.user_information.append(item)

        item = AsynchronousOperationsWindowNegotiation()
        item.maximum_number_operations_invoked = 2
        item.maximum_number_operations_performed = 3
        self.primitive_ac.user_information.append(item)

        item = UserIdentityNegotiation()
        item.user_identity_type = 0x01
        item.positive_response_requested = True
        item.primary_field = b"username"
        self.primitive_ac.user_information.append(item)

        item = SOPClassExtendedNegotiation()
        item.sop_class_uid = "1.2.3"
        item.service_class_application_information = b"SOME DATA"
        self.primitive_ac.user_information.append(item)

        user.primitive = self.primitive_ac

        assert user.maximum_length == 16383
        assert user.implementation_class_uid == "1.2.3"
        assert user.implementation_version_name == "VERSION_1"
        assert user.asynchronous_operations == (2, 3)

        roles = user.role_selection
        assert len(roles) == 2
        role = roles["1.2"]
        assert role.scu_role is False
        assert role.scp_role is True

        classes = user.sop_class_extended
        assert len(classes) == 1
        assert classes["1.2.3"] == b"SOME DATA"

        assert user.sop_class_common_extended == {}

        item = user.user_identity
        assert item.user_identity_type == 0x01
        assert item.primary_field == b"username"

    def test_info(self):
        """Test the .info property"""
        user = ServiceUser(self.assoc, mode="acceptor")
        info = user.info

        assert info["port"] is None
        assert info["mode"] == "acceptor"
        assert info["address"] is None
        assert info["ae_title"] == ""
        with pytest.raises(KeyError):
            info["pdv_size"]

        user.primitive = self.primitive_ac
        assert user.info["pdv_size"] == 16383

    def test_primitive_assignment_raises(self):
        """Test trying to set primitive parameters raises exception."""
        user = ServiceUser(self.assoc, mode="acceptor")
        user.primitive = self.primitive_ac

        assert user.primitive == self.primitive_ac
        assert user.mode == "acceptor"

        msg = r"Can't set the Maximum Length after negotiation has started"
        with pytest.raises(RuntimeError, match=msg):
            user.maximum_length = 16382

        msg = (
            r"Can't set the Implementation Class UID after negotiation " r"has started"
        )
        with pytest.raises(RuntimeError, match=msg):
            user.implementation_class_uid = "1.2.3"

        msg = (
            r"Can't set the Implementation Version Name after negotiation "
            r"has started"
        )
        with pytest.raises(RuntimeError, match=msg):
            user.implementation_version_name = "1.2.3"

        with pytest.raises(AttributeError, match=r"can't set attribute|has no setter"):
            user.asynchronous_operations = (1, 1)

        with pytest.raises(AttributeError, match=r"can't set attribute|has no setter"):
            user.role_selection = {}

        with pytest.raises(AttributeError, match=r"can't set attribute|has no setter"):
            user.sop_class_common_extended = {}

        with pytest.raises(AttributeError, match=r"can't set attribute|has no setter"):
            user.sop_class_extended = {}

        with pytest.raises(AttributeError, match=r"can't set attribute|has no setter"):
            user.user_identity = "test"

        with pytest.raises(AttributeError, match=r"can't set attribute|has no setter"):
            user.extended_negotiation = []

    def test_add_neg_pre(self):
        """Test adding negotiation items."""
        user = ServiceUser(self.assoc, mode="acceptor")
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2

        item = AsynchronousOperationsWindowNegotiation()
        item.maximum_number_operations_invoked = 2
        item.maximum_number_operations_performed = 3
        user.add_negotiation_item(item)
        assert item in user.extended_negotiation
        assert item in user._ext_neg[AsynchronousOperationsWindowNegotiation]
        assert len(user.extended_negotiation) == 1
        assert len(user.user_information) == 3

        item = UserIdentityNegotiation()
        item.user_identity_type = 0x01
        item.positive_response_requested = True
        item.primary_field = b"username"
        user.add_negotiation_item(item)
        assert item in user.extended_negotiation
        assert item in user._ext_neg[UserIdentityNegotiation]
        assert len(user.extended_negotiation) == 2
        assert len(user.user_information) == 4

        item = SCP_SCU_RoleSelectionNegotiation()
        item.sop_class_uid = "1.2.3"
        item.scu_role = True
        item.scp_role = True
        user.add_negotiation_item(item)
        assert item in user.extended_negotiation
        assert item in user._ext_neg[SCP_SCU_RoleSelectionNegotiation]
        assert len(user.extended_negotiation) == 3
        assert len(user.user_information) == 5

        item = SOPClassExtendedNegotiation()
        item.sop_class_uid = "1.2.3"
        item.service_class_application_information = b"SOME DATA"
        user.add_negotiation_item(item)
        assert item in user.extended_negotiation
        assert item in user._ext_neg[SOPClassExtendedNegotiation]
        assert len(user.extended_negotiation) == 4
        assert len(user.user_information) == 6

    def test_add_neg_pre_raises(self):
        """Test that exception is raised if bad item added."""
        user = ServiceUser(self.assoc, mode="acceptor")

        item = AsynchronousOperationsWindowNegotiation()
        item.maximum_number_operations_invoked = 2
        item.maximum_number_operations_performed = 3
        user.add_negotiation_item(item)
        assert item in user.extended_negotiation
        assert item in user._ext_neg[AsynchronousOperationsWindowNegotiation]
        assert len(user.extended_negotiation) == 1
        assert len(user.user_information) == 3

        bad = MaximumLengthNotification()
        bad.maximum_length_received = 12
        msg = r"'item' is not a valid extended negotiation item"
        with pytest.raises(TypeError, match=msg):
            user.add_negotiation_item(bad)

        assert item in user.extended_negotiation
        assert item in user._ext_neg[AsynchronousOperationsWindowNegotiation]
        assert len(user.extended_negotiation) == 1
        assert len(user.user_information) == 3

    def test_add_neg_post_raises(self):
        """Test adding items after negotiation."""
        user = ServiceUser(self.assoc, mode="acceptor")
        user.primitive = self.primitive_ac
        assert user.writeable is False

        item = AsynchronousOperationsWindowNegotiation()
        item.maximum_number_operations_invoked = 2
        item.maximum_number_operations_performed = 3

        msg = r"Can't add extended negotiation items after negotiation "
        with pytest.raises(RuntimeError, match=msg):
            user.add_negotiation_item(item)

        assert item not in user.extended_negotiation
        assert item not in user._ext_neg[AsynchronousOperationsWindowNegotiation]
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2

    def test_async_ops_pre(self):
        """Test getting async ops item prior to negotiation."""
        user = ServiceUser(self.assoc, mode="acceptor")
        assert user.writeable is True
        assert user.asynchronous_operations == (1, 1)  # default
        assert user.extended_negotiation == []

        item = AsynchronousOperationsWindowNegotiation()
        item.maximum_number_operations_invoked = 2
        item.maximum_number_operations_performed = 3
        user.add_negotiation_item(item)

        assert user.asynchronous_operations == (2, 3)
        assert item in user.extended_negotiation
        assert item in user._ext_neg[AsynchronousOperationsWindowNegotiation]
        assert len(user.extended_negotiation) == 1
        assert len(user.user_information) == 3

    def test_async_ops_post(self):
        """Test getting async ops item after negotiation."""
        user = ServiceUser(self.assoc, mode="acceptor")
        user.primitive = self.primitive_ac
        assert user.writeable is False
        assert user.asynchronous_operations == (1, 1)  # default
        assert user.extended_negotiation == []

        item = AsynchronousOperationsWindowNegotiation()
        item.maximum_number_operations_invoked = 2
        item.maximum_number_operations_performed = 3
        user.primitive.user_information.append(item)
        assert user.asynchronous_operations == (2, 3)
        assert user.extended_negotiation == [item]
        assert item in user.extended_negotiation
        assert item not in user._ext_neg[AsynchronousOperationsWindowNegotiation]
        assert len(user.extended_negotiation) == 1
        assert len(user.user_information) == 3

        msg = r"Can't add extended negotiation items after negotiation"
        with pytest.raises(RuntimeError, match=msg):
            user.add_negotiation_item(item)

    def test_ext_neg_pre(self):
        """Test extended_negotiation only returns negotiation items."""
        user = ServiceUser(self.assoc, mode="acceptor")
        assert user.writeable is True
        assert user.extended_negotiation == []
        assert len(user.user_information) == 2

        item = AsynchronousOperationsWindowNegotiation()
        item.maximum_number_operations_invoked = 2
        item.maximum_number_operations_performed = 3
        user.add_negotiation_item(item)

        assert item in user.extended_negotiation
        assert len(user.extended_negotiation) == 1
        assert len(user.user_information) == 3

    def test_ext_neg_post(self):
        """Test extended_negotiation only returns negotiation items."""
        user = ServiceUser(self.assoc, mode="acceptor")
        user.primitive = self.primitive_ac
        assert user.writeable is False
        assert user.extended_negotiation == []
        assert len(user.user_information) == 2

        item = AsynchronousOperationsWindowNegotiation()
        item.maximum_number_operations_invoked = 2
        item.maximum_number_operations_performed = 3
        user.primitive.user_information.append(item)

        assert item in user.extended_negotiation
        assert len(user.extended_negotiation) == 1
        assert len(user.user_information) == 3

    def test_req_get_contexts_pre(self):
        """Test get_contexts prior to association raises if bad type."""
        user = ServiceUser(self.assoc, mode="acceptor")
        assert user.is_acceptor
        assert user.assoc.is_requestor
        assert user.writeable is True

        for cx_type in ("requested", "supported", "pcdl", "pcdrl"):
            msg = (
                f"No '{cx_type}' presentation contexts are available for the "
                r"acceptor service user"
            )
            with pytest.raises(ValueError, match=msg):
                user.get_contexts(cx_type)

    def test_req_get_contexts_post(self):
        """Test get_contexts after association."""
        # requested, pcdl, supported unavailable
        user = ServiceUser(self.assoc, mode="acceptor")
        assert user.is_acceptor
        assert user.assoc.is_requestor

        user.primitive = self.primitive_ac
        assert user.writeable is False

        for cx_type in ("requested", "supported", "pcdl"):
            msg = (
                f"No '{cx_type}' presentation contexts are available for the "
                r"acceptor service user"
            )
            with pytest.raises(ValueError, match=msg):
                user.get_contexts(cx_type)

        cxs = user.get_contexts("pcdrl")
        assert len(cxs) == 1
        assert cxs[0].abstract_syntax == "1.2.840.10008.1.1"

    def test_acc_get_contexts_pre(self):
        """Test get_contexts prior to association."""
        # requested, pcdl, pcdrl unavailable
        self.assoc.mode = "acceptor"
        user = ServiceUser(self.assoc, mode="acceptor")
        assert user.is_acceptor
        assert user.assoc.is_acceptor
        assert user.writeable is True

        user.get_contexts("supported") == []

    def test_acc_get_contexts_pre_raises(self):
        """Test get_contexts prior to association raises if bad type."""
        # requested, pcdl, pcdrl unavailable
        self.assoc.mode = "acceptor"
        user = ServiceUser(self.assoc, mode="acceptor")
        assert user.is_acceptor
        assert user.assoc.is_acceptor
        assert user.writeable is True

        for cx_type in ("requested", "pcdl", "pcdrl"):
            msg = (
                f"No '{cx_type}' presentation contexts are available for the "
                r"acceptor service user"
            )
            with pytest.raises(ValueError, match=msg):
                user.get_contexts(cx_type)

    def test_acc_get_contexts_post(self):
        """Test get_contexts after association."""
        self.assoc.mode = "acceptor"
        user = ServiceUser(self.assoc, mode="acceptor")
        user.primitive = self.primitive_ac
        assert user.writeable is False
        assert user.is_acceptor
        assert user.assoc.is_acceptor

        assert user.get_contexts("supported") == []
        cxs = user.get_contexts("pcdrl")
        assert len(cxs) == 1
        assert cxs[0].abstract_syntax == "1.2.840.10008.1.1"

    def test_acc_get_contexts_post_raises(self):
        """Test get_contexts after association raises if bad type."""
        # requested, pcdl unavailable
        self.assoc.mode = "acceptor"
        user = ServiceUser(self.assoc, mode="acceptor")
        assert user.is_acceptor
        assert user.assoc.is_acceptor

        user.primitive = self.primitive_ac
        assert user.writeable is False

        for cx_type in ("requested", "pcdl"):
            msg = (
                f"No '{cx_type}' presentation contexts are available for the "
                r"acceptor service user"
            )
            with pytest.raises(ValueError, match=msg):
                user.get_contexts(cx_type)

    def test_impl_class_pre(self):
        """Test implementation_class_uid prior to association."""
        user = ServiceUser(self.assoc, mode="acceptor")
        assert user.writeable is True
        assert user.implementation_class_uid == PYNETDICOM_IMPLEMENTATION_UID
        class_items = []
        for item in user.user_information:
            if isinstance(item, ImplementationClassUIDNotification):
                assert item.implementation_class_uid == (PYNETDICOM_IMPLEMENTATION_UID)
                class_items.append(item)

        assert len(class_items) == 1

        user.implementation_class_uid = "1.2.3"
        assert user.implementation_class_uid == "1.2.3"
        class_items = []
        for item in user.user_information:
            if isinstance(item, ImplementationClassUIDNotification):
                assert item.implementation_class_uid == ("1.2.3")
                class_items.append(item)

        assert len(class_items) == 1

    def test_impl_class_post(self):
        """Test implementation_class_uid after association."""
        user = ServiceUser(self.assoc, mode="acceptor")
        user.primitive = self.primitive_ac
        assert user.writeable is False
        assert user.implementation_class_uid == "1.2.3"

        msg = r"Can't set the Implementation Class UID after negotiation"
        with pytest.raises(RuntimeError, match=msg):
            user.implementation_class_uid = "1.2.3.4"

        class_items = []
        for item in user.user_information:
            if isinstance(item, ImplementationClassUIDNotification):
                assert item.implementation_class_uid == "1.2.3"
                class_items.append(item)

        assert len(class_items) == 1

    def test_impl_version_pre(self):
        """Test implementation_version_name prior to association."""
        user = ServiceUser(self.assoc, mode="acceptor")
        assert user.writeable is True
        assert user.implementation_version_name is None

        class_items = []
        for item in user.user_information:
            if isinstance(item, ImplementationVersionNameNotification):
                class_items.append(item)

        assert len(class_items) == 0

        ref = "12345ABCDE123456"
        user.implementation_version_name = ref
        assert user.implementation_version_name == ref

        class_items = []
        user.implementation_version_name = ref
        for item in user.user_information:
            if isinstance(item, ImplementationVersionNameNotification):
                class_items.append(item)
                assert user.implementation_version_name == ref

        assert len(class_items) == 1

        user.implementation_version_name = None
        assert user.implementation_version_name is None

        class_items = []
        for item in user.user_information:
            if isinstance(item, ImplementationVersionNameNotification):
                class_items.append(item)
                assert user.implementation_version_name == ref

        assert len(class_items) == 0

        msg = "Invalid 'implementation_version_name' value - must not be an empty str"
        with pytest.raises(ValueError, match=msg):
            user.implementation_version_name = ""

    def test_impl_version_post(self):
        """Test implementation_version_name after association."""
        user = ServiceUser(self.assoc, mode="acceptor")
        user.primitive = self.primitive_ac
        assert user.writeable is False
        assert user.implementation_version_name is None

        ref = "12345ABCDE123456"
        msg = r"Can't set the Implementation Version Name after negotiation"
        with pytest.raises(RuntimeError, match=msg):
            user.implementation_version_name = ref

        item = ImplementationVersionNameNotification()
        item.implementation_version_name = ref
        user.primitive.user_information.append(item)

        class_items = []
        for item in user.user_information:
            if isinstance(item, ImplementationVersionNameNotification):
                assert item.implementation_version_name == ref
                class_items.append(item)

        assert len(class_items) == 1

    def test_is_acceptor(self):
        """Test is_acceptor"""
        user = ServiceUser(self.assoc, mode="acceptor")
        assert user.is_acceptor is True

    def test_is_requestor(self):
        """Test is_requestor"""
        user = ServiceUser(self.assoc, mode="acceptor")
        assert user.is_requestor is False

    def test_max_length_pre(self):
        """Test maximum_length prior to association."""
        user = ServiceUser(self.assoc, mode="acceptor")
        assert user.writeable is True

        assert user.maximum_length == 16382
        class_items = []
        for item in user.user_information:
            if isinstance(item, MaximumLengthNotification):
                assert item.maximum_length_received == 16382
                class_items.append(item)

        assert len(class_items) == 1

        user.maximum_length = 45
        assert user.maximum_length == 45
        class_items = []
        for item in user.user_information:
            if isinstance(item, MaximumLengthNotification):
                assert item.maximum_length_received == 45
                class_items.append(item)

        assert len(class_items) == 1

    def test_max_length_post(self):
        """Test maximum_length after association."""
        user = ServiceUser(self.assoc, mode="acceptor")
        user.primitive = self.primitive_ac
        assert user.writeable is False
        assert user.maximum_length == 16383

        msg = r"Can't set the Maximum Length after negotiation"
        with pytest.raises(RuntimeError, match=msg):
            user.maximum_length = 45

        class_items = []
        for item in user.user_information:
            if isinstance(item, MaximumLengthNotification):
                assert item.maximum_length_received == 16383
                class_items.append(item)

        assert len(class_items) == 1

    def test_req_requested_cx_pre(self):
        """Test requested_contexts prior to association for requestor."""
        user = ServiceUser(self.assoc, mode="acceptor")
        assert user.is_acceptor
        assert user.assoc.is_requestor
        assert user.writeable is True

        msg = (
            r"No 'requested' presentation contexts are available for the "
            r"acceptor service user"
        )
        with pytest.raises(ValueError, match=msg):
            user.requested_contexts

        msg = r"'requested_contexts' can only be set for the association " r"requestor"
        with pytest.raises(AttributeError, match=msg):
            user.requested_contexts = [build_context("1.2.3")]

    def test_req_requested_cx_post(self):
        """Test requested_contexts after association for requestor."""
        user = ServiceUser(self.assoc, mode="acceptor")
        assert user.is_acceptor
        assert user.assoc.is_requestor
        user.primitive = self.primitive_rq
        assert not user.writeable

        msg = (
            r"No 'requested' presentation contexts are available for the "
            r"acceptor service user"
        )
        with pytest.raises(ValueError, match=msg):
            user.requested_contexts

        msg = r"Can't set the requested presentation contexts after"
        with pytest.raises(RuntimeError, match=msg):
            user.requested_contexts = [build_context("1.2.3")]

    def test_acc_requested_cx_pre(self):
        """Test requested_contexts prior to association."""
        self.assoc.mode = "acceptor"
        user = ServiceUser(self.assoc, mode="acceptor")
        assert user.is_acceptor
        assert user.assoc.is_acceptor
        assert user.writeable is True

        msg = (
            r"No 'requested' presentation contexts are available for the "
            r"acceptor service user"
        )
        with pytest.raises(ValueError, match=msg):
            user.requested_contexts

        msg = r"'requested_contexts' can only be set for the association " r"requestor"
        with pytest.raises(AttributeError, match=msg):
            user.requested_contexts = [build_context("1.2.3")]

    def test_acc_requested_cx_post(self):
        """Test requested_contexts after association."""
        self.assoc.mode = "acceptor"
        user = ServiceUser(self.assoc, mode="acceptor")
        assert user.is_acceptor
        assert user.assoc.is_acceptor
        user.primitive = self.primitive_ac
        assert not user.writeable

        msg = (
            r"No 'pcdl' presentation contexts are available for the "
            r"acceptor service user"
        )
        with pytest.raises(ValueError, match=msg):
            user.requested_contexts

        msg = r"Can't set the requested presentation contexts after"
        with pytest.raises(RuntimeError, match=msg):
            user.requested_contexts = [build_context("1.2.3")]

    def test_rm_neg_pre(self):
        """Test removing negotiation items."""
        user = ServiceUser(self.assoc, mode="acceptor")
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2

        item = AsynchronousOperationsWindowNegotiation()
        item.maximum_number_operations_invoked = 2
        item.maximum_number_operations_performed = 3

        # Test removing non-existent item
        user.remove_negotiation_item(item)
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2

        # Test removing existent item
        user.add_negotiation_item(item)
        assert item in user.extended_negotiation
        assert item in user._ext_neg[AsynchronousOperationsWindowNegotiation]
        assert len(user.extended_negotiation) == 1
        assert len(user.user_information) == 3

        user.remove_negotiation_item(item)
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2

        # Repeat for UserIdentity
        item = UserIdentityNegotiation()
        item.user_identity_type = 0x01
        item.positive_response_requested = True
        item.primary_field = b"username"
        user.add_negotiation_item(item)
        assert item in user.extended_negotiation
        assert item in user._ext_neg[UserIdentityNegotiation]
        assert len(user.extended_negotiation) == 1
        assert len(user.user_information) == 3

        user.remove_negotiation_item(item)
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2

        # Repeat for Role Selection
        item = SCP_SCU_RoleSelectionNegotiation()
        item.sop_class_uid = "1.2.3"
        item.scu_role = True
        item.scp_role = True
        user.add_negotiation_item(item)
        assert item in user.extended_negotiation
        assert item in user._ext_neg[SCP_SCU_RoleSelectionNegotiation]
        assert len(user.extended_negotiation) == 1
        assert len(user.user_information) == 3

        user.remove_negotiation_item(item)
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2

        # Repeat for SOP Class Extended
        item = SOPClassExtendedNegotiation()
        item.sop_class_uid = "1.2.3"
        item.service_class_application_information = b"SOME DATA"
        user.add_negotiation_item(item)
        assert item in user.extended_negotiation
        assert item in user._ext_neg[SOPClassExtendedNegotiation]
        assert len(user.extended_negotiation) == 1
        assert len(user.user_information) == 3

        user.remove_negotiation_item(item)
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2

        # Try removing unknown type
        msg = r"'item' is not a valid extended negotiation item"
        with pytest.raises(TypeError, match=msg):
            user.remove_negotiation_item(1234)

    def test_rm_neg_post_raises(self):
        """Test adding items after negotiation."""
        user = ServiceUser(self.assoc, mode="acceptor")
        user.primitive = self.primitive_ac
        assert user.writeable is False

        item = AsynchronousOperationsWindowNegotiation()
        item.maximum_number_operations_invoked = 2
        item.maximum_number_operations_performed = 3
        user.primitive.user_information.append(item)

        msg = r"Can't remove extended negotiation items after negotiation "
        with pytest.raises(RuntimeError, match=msg):
            user.remove_negotiation_item(item)

        assert item in user.extended_negotiation
        assert len(user.extended_negotiation) == 1
        assert len(user.user_information) == 3

    def test_reset_neg_pre(self):
        """Test reset_negotiation_items prior to association."""
        user = ServiceUser(self.assoc, mode="acceptor")
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2

        # Test with no items
        user.reset_negotiation_items()
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2

        item = AsynchronousOperationsWindowNegotiation()
        item.maximum_number_operations_invoked = 2
        item.maximum_number_operations_performed = 3
        user.add_negotiation_item(item)

        item = SCP_SCU_RoleSelectionNegotiation()
        item.sop_class_uid = "1.2.3"
        item.scu_role = True
        item.scp_role = True
        user.add_negotiation_item(item)

        item = UserIdentityNegotiation()
        item.user_identity_type = 0x01
        item.positive_response_requested = True
        item.primary_field = b"username"
        user.add_negotiation_item(item)

        item = SOPClassExtendedNegotiation()
        item.sop_class_uid = "1.2.3"
        item.service_class_application_information = b"SOME DATA"
        user.add_negotiation_item(item)

        assert len(user.extended_negotiation) == 4
        assert len(user.user_information) == 6

        user.reset_negotiation_items()
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2
        assert len(user._ext_neg.keys()) == 4

    def test_reset_neg_post_raises(self):
        """Test reset_negotiation_items after association raises."""
        user = ServiceUser(self.assoc, mode="acceptor")
        user.primitive = self.primitive_ac
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2

        item = AsynchronousOperationsWindowNegotiation()
        item.maximum_number_operations_invoked = 2
        item.maximum_number_operations_performed = 3
        user.primitive.user_information.append(item)

        item = SCP_SCU_RoleSelectionNegotiation()
        item.sop_class_uid = "1.2.3"
        item.scu_role = True
        item.scp_role = True
        user.primitive.user_information.append(item)

        item = UserIdentityNegotiation()
        item.user_identity_type = 0x01
        item.positive_response_requested = True
        item.primary_field = b"username"
        user.primitive.user_information.append(item)

        item = SOPClassExtendedNegotiation()
        item.sop_class_uid = "1.2.3"
        item.service_class_application_information = b"SOME DATA"
        user.primitive.user_information.append(item)

        item = SOPClassCommonExtendedNegotiation()
        item.sop_class_uid = "1.2.3"
        item.service_class_uid = "2.3.4"
        item.related_general_sop_class_identification = ["1.3.4"]
        user.primitive.user_information.append(item)

        assert len(user.extended_negotiation) == 4
        assert len(user.user_information) == 7

        msg = r"Can't reset the extended negotiation items after negotiation"
        with pytest.raises(RuntimeError, match=msg):
            user.reset_negotiation_items()

        assert len(user.extended_negotiation) == 4
        assert len(user.user_information) == 7

    def test_role_pre(self):
        """Test role_selection prior to association."""
        user = ServiceUser(self.assoc, mode="acceptor")
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2
        assert user.role_selection == {}

        item = SCP_SCU_RoleSelectionNegotiation()
        item.sop_class_uid = "1.2.3"
        item.scu_role = True
        item.scp_role = True
        user.add_negotiation_item(item)
        assert item in user.extended_negotiation
        assert item in user._ext_neg[SCP_SCU_RoleSelectionNegotiation]
        assert len(user.extended_negotiation) == 1
        assert len(user.user_information) == 3

        assert user.role_selection["1.2.3"] == item

    def test_role_post(self):
        """Test role_selection prior to association."""
        user = ServiceUser(self.assoc, mode="acceptor")
        user.primitive = self.primitive_ac
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2
        assert user.role_selection == {}

        item = SCP_SCU_RoleSelectionNegotiation()
        item.sop_class_uid = "1.2.3"
        item.scu_role = True
        item.scp_role = True
        user.primitive.user_information.append(item)
        assert item in user.extended_negotiation
        assert item not in user._ext_neg[SCP_SCU_RoleSelectionNegotiation]
        assert len(user.extended_negotiation) == 1
        assert len(user.user_information) == 3

        assert user.role_selection["1.2.3"] == item

        msg = r"Can't add extended negotiation items after negotiation"
        with pytest.raises(RuntimeError, match=msg):
            user.add_negotiation_item(item)

    def test_sop_ext_pre(self):
        """Test sop_class_extended prior to association."""
        user = ServiceUser(self.assoc, mode="acceptor")
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2
        assert user.sop_class_extended == {}

        item = SOPClassExtendedNegotiation()
        item.sop_class_uid = "1.2.3"
        item.service_class_application_information = b"SOME DATA"
        user.add_negotiation_item(item)
        assert item in user.extended_negotiation
        assert item in user._ext_neg[SOPClassExtendedNegotiation]
        assert len(user.extended_negotiation) == 1
        assert len(user.user_information) == 3

        assert user.sop_class_extended["1.2.3"] == (
            item.service_class_application_information
        )

    def test_sop_ext_post(self):
        """Test sop_class_extended prior to association."""
        user = ServiceUser(self.assoc, mode="acceptor")
        user.primitive = self.primitive_ac
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2
        assert user.sop_class_extended == {}

        item = SOPClassExtendedNegotiation()
        item.sop_class_uid = "1.2.3"
        item.service_class_application_information = b"SOME DATA"
        user.primitive.user_information.append(item)
        assert item in user.extended_negotiation
        assert item not in user._ext_neg[SOPClassExtendedNegotiation]
        assert len(user.extended_negotiation) == 1
        assert len(user.user_information) == 3

        assert user.sop_class_extended["1.2.3"] == (
            item.service_class_application_information
        )

        msg = r"Can't add extended negotiation items after negotiation"
        with pytest.raises(RuntimeError, match=msg):
            user.add_negotiation_item(item)

    def test_sop_common_pre(self):
        """Test sop_class_common_extended prior to association."""
        user = ServiceUser(self.assoc, mode="acceptor")
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2
        assert user.sop_class_common_extended == {}

        item = SOPClassCommonExtendedNegotiation()
        item.sop_class_uid = "1.2.3"
        item.service_class_uid = "2.3.4"
        item.related_general_sop_class_identification = ["1.3.4"]

        msg = r"'item' is not a valid extended negotiation item"
        with pytest.raises(TypeError, match=msg):
            user.add_negotiation_item(item)

        assert item not in user.extended_negotiation
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2

        assert user.sop_class_common_extended == {}

    def test_sop_common_post(self):
        """Test sop_class_common_extended prior to association."""
        user = ServiceUser(self.assoc, mode="acceptor")
        user.primitive = self.primitive_ac
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2
        assert user.sop_class_common_extended == {}

        item = SOPClassCommonExtendedNegotiation()
        item.sop_class_uid = "1.2.3"
        item.service_class_uid = "2.3.4"
        item.related_general_sop_class_identification = ["1.3.4"]
        user.primitive.user_information.append(item)
        assert item not in user.extended_negotiation
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 3

        assert user.sop_class_common_extended == {}

        msg = r"Can't add extended negotiation items after negotiation"
        with pytest.raises(RuntimeError, match=msg):
            user.add_negotiation_item(item)

    def test_req_supported_cx_pre(self):
        """Test supported_contexts prior to association."""
        user = ServiceUser(self.assoc, mode="acceptor")
        assert user.is_acceptor
        assert not user.assoc.is_acceptor

        assert user.writeable is True

        msg = (
            r"No 'supported' presentation contexts are available for the "
            r"acceptor service user"
        )
        with pytest.raises(ValueError, match=msg):
            user.supported_contexts

    def test_req_supported_cx_post(self):
        """Test supported_contexts after association."""
        user = ServiceUser(self.assoc, mode="acceptor")
        assert user.is_acceptor
        assert not user.assoc.is_acceptor

        cx_a = build_context("1.2.3")
        cx_b = build_context("1.2.3.4")
        user.supported_contexts = [cx_a, cx_b]

        user.primitive = self.primitive_ac
        assert user.writeable is False
        assert user.supported_contexts[0].abstract_syntax == Verification

        cx_a = build_context("1.2.3")
        msg = r"Can't set the supported presentation contexts after"
        with pytest.raises(RuntimeError, match=msg):
            user.supported_contexts = [build_context("1.2.3")]

        assert user.supported_contexts[0].abstract_syntax == Verification

    def test_acc_supported_cx_pre(self):
        """Test supported_contexts prior to association."""
        self.assoc.mode = "acceptor"
        user = ServiceUser(self.assoc, mode="acceptor")
        assert user.is_acceptor
        assert user.assoc.is_acceptor

        assert user.writeable
        assert user.supported_contexts == []

        cx_a = build_context("1.2.3")
        cx_b = build_context("1.2.3.4")
        user.supported_contexts = [cx_a, cx_b]

        assert user.supported_contexts == [cx_a, cx_b]

    def test_acc_supported_cx_post(self):
        """Test supported_contexts after association."""
        self.assoc.mode = "acceptor"
        user = ServiceUser(self.assoc, mode="acceptor")
        assert user.is_acceptor
        assert user.assoc.is_acceptor

        cx_a = build_context("1.2.3")
        cx_b = build_context("1.2.3.4")
        user.supported_contexts = [cx_a, cx_b]

        user.primitive = self.primitive_ac
        assert user.writeable is False
        assert user.supported_contexts == [cx_a, cx_b]

        msg = r"Can't set the supported presentation contexts after"
        with pytest.raises(RuntimeError, match=msg):
            user.supported_contexts = [build_context("1.2.3.4.5")]

        assert user.supported_contexts == [cx_a, cx_b]

    def test_user_id_pre(self):
        """Test user_identity prior to association."""
        user = ServiceUser(self.assoc, mode="acceptor")
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2
        assert user.user_identity is None

        item = UserIdentityNegotiation()
        item.user_identity_type = 0x01
        item.positive_response_requested = True
        item.primary_field = b"username"
        user.add_negotiation_item(item)
        assert item in user.extended_negotiation
        assert item in user._ext_neg[UserIdentityNegotiation]
        assert len(user.extended_negotiation) == 1
        assert len(user.user_information) == 3

        assert user.user_identity == item

    def test_user_id_post(self):
        """Test user_identity prior to association."""
        user = ServiceUser(self.assoc, mode="acceptor")
        user.primitive = self.primitive_ac
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2
        assert user.user_identity is None

        item = UserIdentityNegotiation()
        item.user_identity_type = 0x01
        item.positive_response_requested = True
        item.primary_field = b"username"
        user.primitive.user_information.append(item)
        assert item in user.extended_negotiation
        assert item not in user._ext_neg[UserIdentityNegotiation]
        assert len(user.extended_negotiation) == 1
        assert len(user.user_information) == 3

        assert user.user_identity == item

        msg = r"Can't add extended negotiation items after negotiation"
        with pytest.raises(RuntimeError, match=msg):
            user.add_negotiation_item(item)

    def test_user_info_pre(self):
        """Test user_information prior to association."""
        user = ServiceUser(self.assoc, mode="acceptor")
        assert len(user.user_information) == 2

        user.implementation_version_name = "VERSION_1"
        item = user.user_information[2]
        assert isinstance(item, ImplementationVersionNameNotification)
        assert item.implementation_version_name == "VERSION_1"
        assert len(user.user_information) == 3

        for uid in ["1.2", "3.4"]:
            item = SCP_SCU_RoleSelectionNegotiation()
            item.sop_class_uid = uid
            item.scu_role = False
            item.scp_role = True
            user.add_negotiation_item(item)
            assert item in user.user_information

        assert len(user.user_information) == 5

        item = AsynchronousOperationsWindowNegotiation()
        item.maximum_number_operations_invoked = 2
        item.maximum_number_operations_performed = 3
        user.add_negotiation_item(item)
        assert item in user.user_information
        assert len(user.user_information) == 6

        item = UserIdentityNegotiation()
        item.user_identity_type = 0x01
        item.positive_response_requested = True
        item.primary_field = b"username"
        user.add_negotiation_item(item)
        assert item in user.user_information
        assert len(user.user_information) == 7

        item = SOPClassExtendedNegotiation()
        item.sop_class_uid = "1.2.3"
        item.service_class_application_information = b"SOME DATA"
        user.add_negotiation_item(item)
        assert item in user.user_information
        assert len(user.user_information) == 8

        item = SOPClassCommonExtendedNegotiation()
        item.sop_class_uid = "1.2.3"
        item.service_class_uid = "2.3.4"
        item.related_general_sop_class_identification = ["1.3.4"]

        msg = r"'item' is not a valid extended negotiation item"
        with pytest.raises(TypeError, match=msg):
            user.add_negotiation_item(item)

        assert item not in user.user_information
        assert len(user.user_information) == 8

    def test_user_info_post(self):
        """Test user_information prior to association."""
        user = ServiceUser(self.assoc, mode="acceptor")
        user.primitive = self.primitive_ac
        assert len(user.user_information) == 2

        item = ImplementationVersionNameNotification()
        item.implementation_version_name = "VERSION_1"
        user.primitive.user_information.append(item)
        assert item in user.user_information
        assert len(user.user_information) == 3

        for uid in ["1.2", "3.4"]:
            item = SCP_SCU_RoleSelectionNegotiation()
            item.sop_class_uid = uid
            item.scu_role = False
            item.scp_role = True
            user.primitive.user_information.append(item)
            assert item in user.user_information

        assert len(user.user_information) == 5

        item = AsynchronousOperationsWindowNegotiation()
        item.maximum_number_operations_invoked = 2
        item.maximum_number_operations_performed = 3
        user.primitive.user_information.append(item)
        assert item in user.user_information
        assert len(user.user_information) == 6

        item = UserIdentityNegotiation()
        item.user_identity_type = 0x01
        item.positive_response_requested = True
        item.primary_field = b"username"
        user.primitive.user_information.append(item)
        assert item in user.user_information
        assert len(user.user_information) == 7

        item = SOPClassExtendedNegotiation()
        item.sop_class_uid = "1.2.3"
        item.service_class_application_information = b"SOME DATA"
        user.primitive.user_information.append(item)
        assert item in user.user_information
        assert len(user.user_information) == 8

        item = SOPClassCommonExtendedNegotiation()
        item.sop_class_uid = "1.2.3"
        item.service_class_uid = "2.3.4"
        item.related_general_sop_class_identification = ["1.3.4"]
        user.primitive.user_information.append(item)
        assert item in user.user_information
        assert len(user.user_information) == 9

    def test_writeable(self):
        """Test writeable."""
        user = ServiceUser(self.assoc, mode="acceptor")
        assert user.writeable is True
        user.primitive = self.primitive_ac
        assert user.writeable is False

    def test_ae_title(self):
        """Test setting the ae_title"""
        user = ServiceUser(self.assoc, mode="acceptor")
        user.ae_title = "  TEST A   "
        assert user.ae_title == "  TEST A   "

        msg = "Invalid 'ae_title' value - must not be an empty str"
        with pytest.raises(ValueError, match=msg):
            user.ae_title = ""

        msg = "'ae_title' must be str, not 'int'"
        with pytest.raises(TypeError, match=msg):
            user.ae_title = 12345

    def test_aet_bytes_deprecation(self):
        """Test deprecation warning for bytes"""
        user = ServiceUser(self.assoc, mode="acceptor")
        msg = (
            r"The use of bytes with 'ae_title' is deprecated, use an ASCII "
            r"str instead"
        )
        with pytest.warns(DeprecationWarning, match=msg):
            user.ae_title = b"BADAE2"
            assert user.ae_title == "BADAE2"


class TestServiceUserRequestor:
    """Tests for ServiceUser as requestor."""

    def setup_method(self):
        self.assoc = Association(AE(), mode="requestor")

        primitive = A_ASSOCIATE()
        primitive.application_context_name = "1.2.840.10008.3.1.1.1"
        primitive.calling_ae_title = "LOCAL_AE_TITLE  "
        primitive.called_ae_title = "REMOTE_AE_TITLE "
        primitive.calling_presentation_address = AddressInformation("127.0.0.1", 11112)
        primitive.called_presentation_address = AddressInformation("127.0.0.2", 11113)

        # Presentation Contexts
        cx = build_context("1.2.840.10008.1.1")
        cx.context_id = 1
        primitive.presentation_context_definition_list = [cx]

        # User Information items
        item = MaximumLengthNotification()
        item.maximum_length_received = 16382
        primitive.user_information = [item]

        item = ImplementationClassUIDNotification()
        item.implementation_class_uid = "1.2.3"
        primitive.user_information.append(item)

        self.primitive = primitive

        primitive = A_ASSOCIATE()
        primitive.application_context_name = "1.2.840.10008.3.1.1.1"
        primitive.calling_ae_title = "LOCAL_AE_TITLE  "
        primitive.called_ae_title = "REMOTE_AE_TITLE "
        primitive.result = 0x00
        primitive.result_source = 0x01

        # Presentation Contexts
        cx = build_context("1.2.840.10008.1.1")
        cx.context_id = 1
        primitive.presentation_context_definition_results_list = [cx]

        # User Information items
        item = MaximumLengthNotification()
        item.maximum_length_received = 16383
        primitive.user_information = [item]

        item = ImplementationClassUIDNotification()
        item.implementation_class_uid = "1.2.3"
        primitive.user_information.append(item)

        self.primitive_ac = primitive

    def test_init(self):
        """Test new ServiceUser as requestor."""
        user = ServiceUser(self.assoc, mode="requestor")

        assert user.primitive is None
        assert user.ae_title == ""
        with pytest.raises(ValueError, match="No address info"):
            user.port

        with pytest.raises(ValueError, match="No address info"):
            user.address

        assert user.address_info is None
        assert user._contexts == []
        assert user.mode == "requestor"
        assert user.maximum_length == 16382
        assert user.implementation_class_uid == PYNETDICOM_IMPLEMENTATION_UID
        assert user.extended_negotiation == []

        assert len(user.user_information) == 2

    def test_assignment(self):
        """Test that assignment works OK,"""
        user = ServiceUser(self.assoc, mode="requestor")

        assert user.primitive is None
        assert user.ae_title == ""
        with pytest.raises(ValueError, match="No address info"):
            user.port

        with pytest.raises(ValueError, match="No address info"):
            user.address

        assert user.address_info is None
        assert user._contexts == []
        assert user.mode == "requestor"
        assert user.maximum_length == 16382
        assert user.extended_negotiation == []
        assert user.implementation_class_uid == PYNETDICOM_IMPLEMENTATION_UID

        user.ae_title = "TEST_AE_TITLE"
        user.address_info = AddressInformation("127.9.9.1", 11112)
        user._contexts = [1]
        user.maximum_length = 16383

        assert user.ae_title == "TEST_AE_TITLE"
        assert user.port == 11112
        assert user.address == "127.9.9.1"
        assert user.address_info.as_tuple == ("127.9.9.1", 11112)
        assert user._contexts == [1]
        assert user.maximum_length == 16383

    def test_mode_assignment_raises(self):
        """Test that assigning mode after init raises exception."""
        user = ServiceUser(self.assoc, mode="requestor")
        assert user.mode == "requestor"
        with pytest.raises(AttributeError, match=r"can't set attribute|has no setter"):
            user.mode = "acceptor"

        assert user.mode == "requestor"

    def test_minimal(self):
        """Test access with a minimal allowed A-ASSOCIATE primitive."""
        user = ServiceUser(self.assoc, mode="requestor")
        user.primitive = self.primitive

        assert user.primitive == self.primitive
        assert user.mode == "requestor"
        assert user.maximum_length == 16382
        assert user.implementation_class_uid == "1.2.3"
        assert user.implementation_version_name is None
        assert user.asynchronous_operations == (1, 1)
        assert user.role_selection == {}
        assert user.sop_class_common_extended == {}
        assert user.sop_class_extended == {}
        assert user.user_identity is None

    def test_full(self):
        """Test access with a maximum allowed A-ASSOCIATE primitive."""
        user = ServiceUser(self.assoc, mode="requestor")

        item = ImplementationVersionNameNotification()
        item.implementation_version_name = "VERSION_1"
        self.primitive.user_information.append(item)

        for uid in ["1.2", "3.4"]:
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
        item.primary_field = b"username"
        self.primitive.user_information.append(item)

        item = SOPClassExtendedNegotiation()
        item.sop_class_uid = "1.2.3"
        item.service_class_application_information = b"SOME DATA"
        self.primitive.user_information.append(item)

        item = SOPClassCommonExtendedNegotiation()
        item.sop_class_uid = "1.2.3"
        item.service_class_uid = "2.3.4"
        item.related_general_sop_class_identification = ["1.3.4"]
        self.primitive.user_information.append(item)

        user.primitive = self.primitive

        assert user.maximum_length == 16382
        assert user.implementation_class_uid == "1.2.3"
        assert user.implementation_version_name == "VERSION_1"
        assert user.asynchronous_operations == (2, 3)

        roles = user.role_selection
        assert len(roles) == 2
        role = roles["1.2"]
        assert role.scu_role is False
        assert role.scp_role is True

        classes = user.sop_class_extended
        assert len(classes) == 1
        assert classes["1.2.3"] == b"SOME DATA"

        classes = user.sop_class_common_extended
        assert len(classes) == 1
        assert classes["1.2.3"].service_class_uid == "2.3.4"
        assert classes["1.2.3"].related_general_sop_class_identification == ["1.3.4"]

        item = user.user_identity
        assert item.user_identity_type == 0x01
        assert item.primary_field == b"username"

    def test_info(self):
        """Test the .info property"""
        user = ServiceUser(self.assoc, mode="requestor")
        info = user.info

        assert info["port"] is None
        assert info["mode"] == "requestor"
        assert info["address"] is None
        assert info["ae_title"] == ""
        with pytest.raises(KeyError):
            info["pdv_size"]

        user.primitive = self.primitive
        assert user.info["pdv_size"] == 16382

    def test_primitive_assignment_raises(self):
        """Test trying to set primitive parameters raises exception."""
        user = ServiceUser(self.assoc, mode="requestor")
        user.primitive = self.primitive

        assert user.primitive == self.primitive
        assert user.mode == "requestor"

        msg = r"Can't set the Maximum Length after negotiation has started"
        with pytest.raises(RuntimeError, match=msg):
            user.maximum_length = 16382

        msg = (
            r"Can't set the Implementation Class UID after negotiation " r"has started"
        )
        with pytest.raises(RuntimeError, match=msg):
            user.implementation_class_uid = "1.2.3"

        msg = (
            r"Can't set the Implementation Version Name after negotiation "
            r"has started"
        )
        with pytest.raises(RuntimeError, match=msg):
            user.implementation_version_name = "1.2.3"

        with pytest.raises(AttributeError, match=r"can't set attribute|has no setter"):
            user.asynchronous_operations = (1, 1)

        with pytest.raises(AttributeError, match=r"can't set attribute|has no setter"):
            user.role_selection = {}

        with pytest.raises(AttributeError, match=r"can't set attribute|has no setter"):
            user.sop_class_common_extended = {}

        with pytest.raises(AttributeError, match=r"can't set attribute|has no setter"):
            user.sop_class_extended = {}

        with pytest.raises(AttributeError, match=r"can't set attribute|has no setter"):
            user.user_identity = "test"

        with pytest.raises(AttributeError, match=r"can't set attribute|has no setter"):
            user.extended_negotiation = []

    def test_accepted_common_raises(self):
        """Test trying to get the accepted common ext items raises."""
        user = ServiceUser(self.assoc, mode="requestor")

        msg = r"'accepted_common_extended' is only available for the " r"'acceptor'"
        with pytest.raises(RuntimeError, match=msg):
            user.accepted_common_extended()

    def test_add_neg_pre(self):
        """Test adding negotiation items."""
        user = ServiceUser(self.assoc, mode="requestor")
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2

        item = AsynchronousOperationsWindowNegotiation()
        item.maximum_number_operations_invoked = 2
        item.maximum_number_operations_performed = 3
        user.add_negotiation_item(item)
        assert item in user.extended_negotiation
        assert item in user._ext_neg[AsynchronousOperationsWindowNegotiation]
        assert len(user.extended_negotiation) == 1
        assert len(user.user_information) == 3

        item = UserIdentityNegotiation()
        item.user_identity_type = 0x01
        item.positive_response_requested = True
        item.primary_field = b"username"
        user.add_negotiation_item(item)
        assert item in user.extended_negotiation
        assert item in user._ext_neg[UserIdentityNegotiation]
        assert len(user.extended_negotiation) == 2
        assert len(user.user_information) == 4

        item = SCP_SCU_RoleSelectionNegotiation()
        item.sop_class_uid = "1.2.3"
        item.scu_role = True
        item.scp_role = True
        user.add_negotiation_item(item)
        assert item in user.extended_negotiation
        assert item in user._ext_neg[SCP_SCU_RoleSelectionNegotiation]
        assert len(user.extended_negotiation) == 3
        assert len(user.user_information) == 5

        item = SOPClassExtendedNegotiation()
        item.sop_class_uid = "1.2.3"
        item.service_class_application_information = b"SOME DATA"
        user.add_negotiation_item(item)
        assert item in user.extended_negotiation
        assert item in user._ext_neg[SOPClassExtendedNegotiation]
        assert len(user.extended_negotiation) == 4
        assert len(user.user_information) == 6

        item = SOPClassCommonExtendedNegotiation()
        item.sop_class_uid = "1.2.3"
        item.service_class_uid = "2.3.4"
        item.related_general_sop_class_identification = ["1.3.4"]
        user.add_negotiation_item(item)
        assert item in user.extended_negotiation
        assert item in user._ext_neg[SOPClassCommonExtendedNegotiation]
        assert len(user.extended_negotiation) == 5
        assert len(user.user_information) == 7

    def test_add_neg_pre_raises(self):
        """Test that exception is raised if bad item added."""
        user = ServiceUser(self.assoc, mode="requestor")

        item = AsynchronousOperationsWindowNegotiation()
        item.maximum_number_operations_invoked = 2
        item.maximum_number_operations_performed = 3
        user.add_negotiation_item(item)
        assert item in user.extended_negotiation
        assert item in user._ext_neg[AsynchronousOperationsWindowNegotiation]
        assert len(user.extended_negotiation) == 1
        assert len(user.user_information) == 3

        bad = MaximumLengthNotification()
        bad.maximum_length_received = 12
        msg = r"'item' is not a valid extended negotiation item"
        with pytest.raises(TypeError, match=msg):
            user.add_negotiation_item(bad)

        assert item in user.extended_negotiation
        assert item in user._ext_neg[AsynchronousOperationsWindowNegotiation]
        assert len(user.extended_negotiation) == 1
        assert len(user.user_information) == 3

    def test_add_neg_post_raises(self):
        """Test adding items after negotiation."""
        user = ServiceUser(self.assoc, mode="requestor")
        user.primitive = self.primitive
        assert user.writeable is False

        item = AsynchronousOperationsWindowNegotiation()
        item.maximum_number_operations_invoked = 2
        item.maximum_number_operations_performed = 3

        msg = r"Can't add extended negotiation items after negotiation "
        with pytest.raises(RuntimeError, match=msg):
            user.add_negotiation_item(item)

        assert item not in user.extended_negotiation
        assert item not in user._ext_neg[AsynchronousOperationsWindowNegotiation]
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2

    def test_async_ops_pre(self):
        """Test getting async ops item prior to negotiation."""
        user = ServiceUser(self.assoc, mode="requestor")
        assert user.writeable is True
        assert user.asynchronous_operations == (1, 1)  # default
        assert user.extended_negotiation == []

        item = AsynchronousOperationsWindowNegotiation()
        item.maximum_number_operations_invoked = 2
        item.maximum_number_operations_performed = 3
        user.add_negotiation_item(item)

        assert user.asynchronous_operations == (2, 3)
        assert item in user.extended_negotiation
        assert item in user._ext_neg[AsynchronousOperationsWindowNegotiation]
        assert len(user.extended_negotiation) == 1
        assert len(user.user_information) == 3

    def test_async_ops_post(self):
        """Test getting async ops item after negotiation."""
        user = ServiceUser(self.assoc, mode="requestor")
        user.primitive = self.primitive
        assert user.writeable is False
        assert user.asynchronous_operations == (1, 1)  # default
        assert user.extended_negotiation == []

        item = AsynchronousOperationsWindowNegotiation()
        item.maximum_number_operations_invoked = 2
        item.maximum_number_operations_performed = 3
        self.primitive.user_information.append(item)
        assert user.asynchronous_operations == (2, 3)
        assert user.extended_negotiation == [item]
        assert item in user.extended_negotiation
        assert item not in user._ext_neg[AsynchronousOperationsWindowNegotiation]
        assert len(user.extended_negotiation) == 1
        assert len(user.user_information) == 3

        msg = r"Can't add extended negotiation items after negotiation"
        with pytest.raises(RuntimeError, match=msg):
            user.add_negotiation_item(item)

    def test_ext_neg_pre(self):
        """Test extended_negotiation only returns negotiation items."""
        user = ServiceUser(self.assoc, mode="requestor")
        assert user.writeable is True
        assert user.extended_negotiation == []
        assert len(user.user_information) == 2

        item = AsynchronousOperationsWindowNegotiation()
        item.maximum_number_operations_invoked = 2
        item.maximum_number_operations_performed = 3
        user.add_negotiation_item(item)

        assert item in user.extended_negotiation
        assert len(user.extended_negotiation) == 1
        assert len(user.user_information) == 3

    def test_ext_neg_post(self):
        """Test extended_negotiation only returns negotiation items."""
        user = ServiceUser(self.assoc, mode="requestor")
        user.primitive = self.primitive
        assert user.writeable is False
        assert user.extended_negotiation == []
        assert len(user.user_information) == 2

        item = AsynchronousOperationsWindowNegotiation()
        item.maximum_number_operations_invoked = 2
        item.maximum_number_operations_performed = 3
        self.primitive.user_information.append(item)

        assert item in user.extended_negotiation
        assert len(user.extended_negotiation) == 1
        assert len(user.user_information) == 3

    def test_req_get_contexts_pre(self):
        """Test get_contexts prior to association."""
        user = ServiceUser(self.assoc, mode="requestor")
        assert user.assoc.is_requestor
        assert user.is_requestor

        assert user.writeable is True

        cxs = user.get_contexts("requested")
        assert len(cxs) == 0

        user.requested_contexts = [build_context("1.2.840.10008.1.1")]
        cxs = user.get_contexts("requested")
        assert len(cxs) == 1
        assert cxs[0].abstract_syntax == "1.2.840.10008.1.1"

    def test_req_get_contexts_pre_raises(self):
        """Test get_contexts prior to association raises if bad type."""
        # pcdl, supported, pcdrl unavailable
        user = ServiceUser(self.assoc, mode="requestor")
        assert user.assoc.is_requestor
        assert user.is_requestor
        assert user.writeable is True

        for cx_type in ("supported", "pcdl", "pcdrl"):
            msg = (
                f"No '{cx_type}' presentation contexts are available for the "
                r"requestor service user"
            )
            with pytest.raises(ValueError, match=msg):
                user.get_contexts(cx_type)

    def test_req_get_contexts_post(self):
        """Test get_contexts after association."""
        user = ServiceUser(self.assoc, mode="requestor")
        assert user.assoc.is_requestor
        assert user.is_requestor

        user.primitive = self.primitive
        assert user.writeable is False

        cxs = user.get_contexts("requested")
        assert len(cxs) == 0

        cxs = user.get_contexts("pcdl")
        assert len(cxs) == 1
        assert cxs[0].abstract_syntax == "1.2.840.10008.1.1"

    def test_req_get_contexts_post_raises(self):
        """Test get_contexts after association raises if bad type."""
        # supported, pcdrl unavailable
        user = ServiceUser(self.assoc, mode="requestor")
        assert user.assoc.is_requestor
        assert user.is_requestor

        user.primitive = self.primitive
        assert user.writeable is False

        for cx_type in ("supported", "pcdrl"):
            msg = (
                f"No '{cx_type}' presentation contexts are available for the "
                r"requestor service user"
            )
            with pytest.raises(ValueError, match=msg):
                user.get_contexts(cx_type)

    def test_acc_get_contexts_pre(self):
        """Test get_contexts prior to association."""
        # requested, pcdl, supported, pcdrl unavailable
        self.assoc.mode = "acceptor"
        user = ServiceUser(self.assoc, mode="requestor")
        assert user.assoc.is_acceptor
        assert user.is_requestor

        assert user.writeable is True

        for cx_type in ("requested", "supported", "pcdl", "pcdrl"):
            msg = (
                f"No '{cx_type}' presentation contexts are available for the "
                r"requestor service user"
            )
            with pytest.raises(ValueError, match=msg):
                user.get_contexts(cx_type)

    def test_acc_get_contexts_post(self):
        """Test get_contexts prior to association."""
        self.assoc.mode = "acceptor"
        user = ServiceUser(self.assoc, mode="requestor")
        assert user.assoc.is_acceptor
        assert user.is_requestor

        user.primitive = self.primitive
        assert user.writeable is False

        assert user.get_contexts("pcdl")[0].abstract_syntax == Verification

    def test_acc_get_contexts_post_raises(self):
        """Test get_contexts prior to association."""
        # requested, pcdrl, supported unavailable
        self.assoc.mode = "acceptor"
        user = ServiceUser(self.assoc, mode="requestor")
        assert user.assoc.is_acceptor
        assert user.is_requestor

        user.primitive = self.primitive
        assert user.writeable is False

        for cx_type in ("requested", "supported", "pcdrl"):
            msg = (
                f"No '{cx_type}' presentation contexts are available for the "
                r"requestor service user"
            )
            with pytest.raises(ValueError, match=msg):
                user.get_contexts(cx_type)

    def test_impl_class_pre(self):
        """Test implementation_class_uid prior to association."""
        user = ServiceUser(self.assoc, mode="requestor")
        assert user.writeable is True
        assert user.implementation_class_uid == PYNETDICOM_IMPLEMENTATION_UID
        class_items = []
        for item in user.user_information:
            if isinstance(item, ImplementationClassUIDNotification):
                assert item.implementation_class_uid == (PYNETDICOM_IMPLEMENTATION_UID)
                class_items.append(item)

        assert len(class_items) == 1

        user.implementation_class_uid = "1.2.3"
        assert user.implementation_class_uid == "1.2.3"
        class_items = []
        for item in user.user_information:
            if isinstance(item, ImplementationClassUIDNotification):
                assert item.implementation_class_uid == ("1.2.3")
                class_items.append(item)

        assert len(class_items) == 1

    def test_impl_class_post(self):
        """Test implementation_class_uid after association."""
        user = ServiceUser(self.assoc, mode="requestor")
        user.primitive = self.primitive
        assert user.writeable is False
        assert user.implementation_class_uid == "1.2.3"

        msg = r"Can't set the Implementation Class UID after negotiation"
        with pytest.raises(RuntimeError, match=msg):
            user.implementation_class_uid = "1.2.3.4"

        class_items = []
        for item in user.user_information:
            if isinstance(item, ImplementationClassUIDNotification):
                assert item.implementation_class_uid == "1.2.3"
                class_items.append(item)

        assert len(class_items) == 1

    def test_impl_version_pre(self):
        """Test implementation_version_name prior to association."""
        user = ServiceUser(self.assoc, mode="requestor")
        assert user.writeable is True
        assert user.implementation_version_name is None

        class_items = []
        for item in user.user_information:
            if isinstance(item, ImplementationVersionNameNotification):
                class_items.append(item)

        assert len(class_items) == 0

        ref = "12345ABCDE123456"
        user.implementation_version_name = ref
        assert user.implementation_version_name == ref

        class_items = []
        user.implementation_version_name = ref
        for item in user.user_information:
            if isinstance(item, ImplementationVersionNameNotification):
                class_items.append(item)
                assert user.implementation_version_name == ref

        assert len(class_items) == 1

    def test_impl_version_post(self):
        """Test implementation_version_name after association."""
        user = ServiceUser(self.assoc, mode="requestor")
        user.primitive = self.primitive
        assert user.writeable is False
        assert user.implementation_version_name is None

        ref = "12345ABCDE123456"
        msg = r"Can't set the Implementation Version Name after negotiation"
        with pytest.raises(RuntimeError, match=msg):
            user.implementation_version_name = ref

        item = ImplementationVersionNameNotification()
        item.implementation_version_name = ref
        self.primitive.user_information.append(item)

        class_items = []
        for item in user.user_information:
            if isinstance(item, ImplementationVersionNameNotification):
                assert item.implementation_version_name == ref
                class_items.append(item)

        assert len(class_items) == 1

    def test_is_acceptor(self):
        """Test is_acceptor"""
        user = ServiceUser(self.assoc, mode="requestor")
        assert user.is_acceptor is False

    def test_is_requestor(self):
        """Test is_requestor"""
        user = ServiceUser(self.assoc, mode="requestor")
        assert user.is_requestor is True

    def test_max_length_pre(self):
        """Test maximum_length prior to association."""
        user = ServiceUser(self.assoc, mode="requestor")
        assert user.writeable is True

        assert user.maximum_length == 16382
        class_items = []
        for item in user.user_information:
            if isinstance(item, MaximumLengthNotification):
                assert item.maximum_length_received == 16382
                class_items.append(item)

        assert len(class_items) == 1

        user.maximum_length = 45
        assert user.maximum_length == 45
        class_items = []
        for item in user.user_information:
            if isinstance(item, MaximumLengthNotification):
                assert item.maximum_length_received == 45
                class_items.append(item)

        assert len(class_items) == 1

    def test_max_length_post(self):
        """Test maximum_length after association."""
        user = ServiceUser(self.assoc, mode="requestor")
        user.primitive = self.primitive
        assert user.writeable is False
        assert user.maximum_length == 16382

        msg = r"Can't set the Maximum Length after negotiation"
        with pytest.raises(RuntimeError, match=msg):
            user.maximum_length = 45

        class_items = []
        for item in user.user_information:
            if isinstance(item, MaximumLengthNotification):
                assert item.maximum_length_received == 16382
                class_items.append(item)

        assert len(class_items) == 1

    def test_req_requested_cx_pre(self):
        """Test requested_contexts prior to association."""
        user = ServiceUser(self.assoc, mode="requestor")
        assert user.assoc.is_requestor
        assert user.is_requestor

        assert user.writeable is True
        assert user.requested_contexts == []

        cx_a = build_context("1.2.3")
        cx_b = build_context("1.2.3.4")
        user.requested_contexts = [cx_a, cx_b]

        assert len(user.requested_contexts) == 2
        assert cx_a in user.requested_contexts
        assert cx_b in user.requested_contexts

    def test_req_requested_cx_post(self):
        """Test requested_contexts after association."""
        user = ServiceUser(self.assoc, mode="requestor")
        assert user.assoc.is_requestor
        assert user.is_requestor

        cx_a = build_context("1.2.3")
        cx_b = build_context("1.2.3.4")
        user.requested_contexts = [cx_a, cx_b]

        user.primitive = self.primitive
        assert user.writeable is False
        assert user.requested_contexts == [cx_a, cx_b]

        msg = r"Can't set the requested presentation contexts after"
        with pytest.raises(RuntimeError, match=msg):
            user.requested_contexts = [build_context("1.2.3.4.5")]

        assert user.requested_contexts == [cx_a, cx_b]

    def test_acc_requested_cx_pre(self):
        """Test requested_contexts prior to association."""
        self.assoc.mode = "acceptor"
        user = ServiceUser(self.assoc, mode="requestor")
        assert user.assoc.is_acceptor
        assert user.is_requestor

        assert user.writeable is True

        msg = (
            r"No 'requested' presentation contexts are available for the "
            r"requestor service user"
        )
        with pytest.raises(ValueError, match=msg):
            user.requested_contexts

    def test_acc_requested_cx_post(self):
        """Test requested_contexts after association."""
        self.assoc.mode = "acceptor"
        user = ServiceUser(self.assoc, mode="requestor")
        assert user.assoc.is_acceptor
        assert user.is_requestor

        user.primitive = self.primitive
        assert user.writeable is False
        assert user.requested_contexts[0].abstract_syntax == Verification

        msg = r"Can't set the requested presentation contexts after"
        with pytest.raises(RuntimeError, match=msg):
            user.requested_contexts = [build_context("1.2.3.4.5")]

    def test_rm_neg_pre(self):
        """Test removing negotiation items."""
        user = ServiceUser(self.assoc, mode="requestor")
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2

        item = AsynchronousOperationsWindowNegotiation()
        item.maximum_number_operations_invoked = 2
        item.maximum_number_operations_performed = 3

        # Test removing non-existent item
        user.remove_negotiation_item(item)
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2

        # Test removing existent item
        user.add_negotiation_item(item)
        assert item in user.extended_negotiation
        assert item in user._ext_neg[AsynchronousOperationsWindowNegotiation]
        assert len(user.extended_negotiation) == 1
        assert len(user.user_information) == 3

        user.remove_negotiation_item(item)
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2

        # Repeat for UserIdentity
        item = UserIdentityNegotiation()
        item.user_identity_type = 0x01
        item.positive_response_requested = True
        item.primary_field = b"username"
        user.add_negotiation_item(item)
        assert item in user.extended_negotiation
        assert item in user._ext_neg[UserIdentityNegotiation]
        assert len(user.extended_negotiation) == 1
        assert len(user.user_information) == 3

        user.remove_negotiation_item(item)
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2

        # Repeat for Role Selection
        item = SCP_SCU_RoleSelectionNegotiation()
        item.sop_class_uid = "1.2.3"
        item.scu_role = True
        item.scp_role = True
        user.add_negotiation_item(item)
        assert item in user.extended_negotiation
        assert item in user._ext_neg[SCP_SCU_RoleSelectionNegotiation]
        assert len(user.extended_negotiation) == 1
        assert len(user.user_information) == 3

        user.remove_negotiation_item(item)
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2

        # Repeat for SOP Class Extended
        item = SOPClassExtendedNegotiation()
        item.sop_class_uid = "1.2.3"
        item.service_class_application_information = b"SOME DATA"
        user.add_negotiation_item(item)
        assert item in user.extended_negotiation
        assert item in user._ext_neg[SOPClassExtendedNegotiation]
        assert len(user.extended_negotiation) == 1
        assert len(user.user_information) == 3

        user.remove_negotiation_item(item)
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2

        # Repeat for SOP Class Common
        item = SOPClassCommonExtendedNegotiation()
        item.sop_class_uid = "1.2.3"
        item.service_class_uid = "2.3.4"
        item.related_general_sop_class_identification = ["1.3.4"]
        user.add_negotiation_item(item)
        assert item in user.extended_negotiation
        assert item in user._ext_neg[SOPClassCommonExtendedNegotiation]
        assert len(user.extended_negotiation) == 1
        assert len(user.user_information) == 3

        user.remove_negotiation_item(item)
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2

        # Try removing unknown type
        msg = r"'item' is not a valid extended negotiation item"
        with pytest.raises(TypeError, match=msg):
            user.remove_negotiation_item(1234)

    def test_rm_neg_post_raises(self):
        """Test adding items after negotiation."""
        user = ServiceUser(self.assoc, mode="requestor")
        user.primitive = self.primitive
        assert user.writeable is False

        item = AsynchronousOperationsWindowNegotiation()
        item.maximum_number_operations_invoked = 2
        item.maximum_number_operations_performed = 3
        self.primitive.user_information.append(item)

        msg = r"Can't remove extended negotiation items after negotiation "
        with pytest.raises(RuntimeError, match=msg):
            user.remove_negotiation_item(item)

        assert item in user.extended_negotiation
        assert len(user.extended_negotiation) == 1
        assert len(user.user_information) == 3

    def test_reset_neg_pre(self):
        """Test reset_negotiation_items prior to association."""
        user = ServiceUser(self.assoc, mode="requestor")
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2

        # Test with no items
        user.reset_negotiation_items()
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2

        item = AsynchronousOperationsWindowNegotiation()
        item.maximum_number_operations_invoked = 2
        item.maximum_number_operations_performed = 3
        user.add_negotiation_item(item)

        item = SCP_SCU_RoleSelectionNegotiation()
        item.sop_class_uid = "1.2.3"
        item.scu_role = True
        item.scp_role = True
        user.add_negotiation_item(item)

        item = UserIdentityNegotiation()
        item.user_identity_type = 0x01
        item.positive_response_requested = True
        item.primary_field = b"username"
        user.add_negotiation_item(item)

        item = SOPClassExtendedNegotiation()
        item.sop_class_uid = "1.2.3"
        item.service_class_application_information = b"SOME DATA"
        user.add_negotiation_item(item)

        item = SOPClassCommonExtendedNegotiation()
        item.sop_class_uid = "1.2.3"
        item.service_class_uid = "2.3.4"
        item.related_general_sop_class_identification = ["1.3.4"]
        user.add_negotiation_item(item)

        assert len(user.extended_negotiation) == 5
        assert len(user.user_information) == 7

        user.reset_negotiation_items()
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2
        assert len(user._ext_neg.keys()) == 5

    def test_reset_neg_post_raises(self):
        """Test reset_negotiation_items after association raises."""
        user = ServiceUser(self.assoc, mode="requestor")
        user.primitive = self.primitive
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2

        item = AsynchronousOperationsWindowNegotiation()
        item.maximum_number_operations_invoked = 2
        item.maximum_number_operations_performed = 3
        user.primitive.user_information.append(item)

        item = SCP_SCU_RoleSelectionNegotiation()
        item.sop_class_uid = "1.2.3"
        item.scu_role = True
        item.scp_role = True
        user.primitive.user_information.append(item)

        item = UserIdentityNegotiation()
        item.user_identity_type = 0x01
        item.positive_response_requested = True
        item.primary_field = b"username"
        user.primitive.user_information.append(item)

        item = SOPClassExtendedNegotiation()
        item.sop_class_uid = "1.2.3"
        item.service_class_application_information = b"SOME DATA"
        user.primitive.user_information.append(item)

        item = SOPClassCommonExtendedNegotiation()
        item.sop_class_uid = "1.2.3"
        item.service_class_uid = "2.3.4"
        item.related_general_sop_class_identification = ["1.3.4"]
        user.primitive.user_information.append(item)

        assert len(user.extended_negotiation) == 5
        assert len(user.user_information) == 7

        msg = r"Can't reset the extended negotiation items after negotiation"
        with pytest.raises(RuntimeError, match=msg):
            user.reset_negotiation_items()

        assert len(user.extended_negotiation) == 5
        assert len(user.user_information) == 7

    def test_role_pre(self):
        """Test role_selection prior to association."""
        user = ServiceUser(self.assoc, mode="requestor")
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2
        assert user.role_selection == {}

        item = SCP_SCU_RoleSelectionNegotiation()
        item.sop_class_uid = "1.2.3"
        item.scu_role = True
        item.scp_role = True
        user.add_negotiation_item(item)
        assert item in user.extended_negotiation
        assert item in user._ext_neg[SCP_SCU_RoleSelectionNegotiation]
        assert len(user.extended_negotiation) == 1
        assert len(user.user_information) == 3

        assert user.role_selection["1.2.3"] == item

    def test_role_post(self):
        """Test role_selection prior to association."""
        user = ServiceUser(self.assoc, mode="requestor")
        user.primitive = self.primitive
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2
        assert user.role_selection == {}

        item = SCP_SCU_RoleSelectionNegotiation()
        item.sop_class_uid = "1.2.3"
        item.scu_role = True
        item.scp_role = True
        user.primitive.user_information.append(item)
        assert item in user.extended_negotiation
        assert item not in user._ext_neg[SCP_SCU_RoleSelectionNegotiation]
        assert len(user.extended_negotiation) == 1
        assert len(user.user_information) == 3

        assert user.role_selection["1.2.3"] == item

        msg = r"Can't add extended negotiation items after negotiation"
        with pytest.raises(RuntimeError, match=msg):
            user.add_negotiation_item(item)

    def test_sop_ext_pre(self):
        """Test sop_class_extended prior to association."""
        user = ServiceUser(self.assoc, mode="requestor")
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2
        assert user.sop_class_extended == {}

        item = SOPClassExtendedNegotiation()
        item.sop_class_uid = "1.2.3"
        item.service_class_application_information = b"SOME DATA"
        user.add_negotiation_item(item)
        assert item in user.extended_negotiation
        assert item in user._ext_neg[SOPClassExtendedNegotiation]
        assert len(user.extended_negotiation) == 1
        assert len(user.user_information) == 3

        assert user.sop_class_extended["1.2.3"] == (
            item.service_class_application_information
        )

    def test_sop_ext_post(self):
        """Test sop_class_extended prior to association."""
        user = ServiceUser(self.assoc, mode="requestor")
        user.primitive = self.primitive
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2
        assert user.sop_class_extended == {}

        item = SOPClassExtendedNegotiation()
        item.sop_class_uid = "1.2.3"
        item.service_class_application_information = b"SOME DATA"
        user.primitive.user_information.append(item)
        assert item in user.extended_negotiation
        assert item not in user._ext_neg[SOPClassExtendedNegotiation]
        assert len(user.extended_negotiation) == 1
        assert len(user.user_information) == 3

        assert user.sop_class_extended["1.2.3"] == (
            item.service_class_application_information
        )

        msg = r"Can't add extended negotiation items after negotiation"
        with pytest.raises(RuntimeError, match=msg):
            user.add_negotiation_item(item)

    def test_sop_common_pre(self):
        """Test sop_class_common_extended prior to association."""
        user = ServiceUser(self.assoc, mode="requestor")
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2
        assert user.sop_class_common_extended == {}

        item = SOPClassCommonExtendedNegotiation()
        item.sop_class_uid = "1.2.3"
        item.service_class_uid = "2.3.4"
        item.related_general_sop_class_identification = ["1.3.4"]
        user.add_negotiation_item(item)
        assert item in user.extended_negotiation
        assert item in user._ext_neg[SOPClassCommonExtendedNegotiation]
        assert len(user.extended_negotiation) == 1
        assert len(user.user_information) == 3

        assert user.sop_class_common_extended["1.2.3"] == item

    def test_sop_common_post(self):
        """Test sop_class_common_extended prior to association."""
        user = ServiceUser(self.assoc, mode="requestor")
        user.primitive = self.primitive
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2
        assert user.sop_class_common_extended == {}

        item = SOPClassCommonExtendedNegotiation()
        item.sop_class_uid = "1.2.3"
        item.service_class_uid = "2.3.4"
        item.related_general_sop_class_identification = ["1.3.4"]
        user.primitive.user_information.append(item)
        assert item in user.extended_negotiation
        assert item not in user._ext_neg[SOPClassCommonExtendedNegotiation]
        assert len(user.extended_negotiation) == 1
        assert len(user.user_information) == 3

        assert user.sop_class_common_extended["1.2.3"] == item

        msg = r"Can't add extended negotiation items after negotiation"
        with pytest.raises(RuntimeError, match=msg):
            user.add_negotiation_item(item)

    def test_req_supported_cx_pre(self):
        """Test supported_contexts prior to association."""
        user = ServiceUser(self.assoc, mode="requestor")
        assert user.assoc.is_requestor
        assert user.is_requestor
        assert user.writeable is True

        msg = (
            r"No 'supported' presentation contexts are available for the "
            r"requestor service user"
        )
        with pytest.raises(ValueError, match=msg):
            user.supported_contexts

        msg = r"'supported_contexts' can only be set for the association " r"acceptor"
        with pytest.raises(AttributeError, match=msg):
            user.supported_contexts = "bluh"

    def test_req_supported_cx_post(self):
        """Test supported_contexts after association."""
        user = ServiceUser(self.assoc, mode="requestor")
        assert user.assoc.is_requestor
        assert user.is_requestor

        user.primitive = self.primitive
        assert user.writeable is False

        msg = (
            r"No 'pcdrl' presentation contexts are available for the "
            r"requestor service user"
        )
        with pytest.raises(ValueError, match=msg):
            user.supported_contexts

    def test_acc_supported_cx_pre(self):
        """Test supported_contexts prior to association."""
        self.assoc.mode = "acceptor"
        user = ServiceUser(self.assoc, mode="requestor")
        assert user.assoc.is_acceptor
        assert user.is_requestor
        assert user.writeable is True

        msg = (
            r"No 'supported' presentation contexts are available for the "
            r"requestor service user"
        )
        with pytest.raises(ValueError, match=msg):
            user.supported_contexts

        msg = r"'supported_contexts' can only be set for the association " r"acceptor"
        with pytest.raises(AttributeError, match=msg):
            user.supported_contexts = "bluh"

    def test_acc_supported_cx_post(self):
        """Test supported_contexts after association."""
        self.assoc.mode = "acceptor"
        user = ServiceUser(self.assoc, mode="requestor")
        assert user.assoc.is_acceptor
        assert user.is_requestor

        user.primitive = self.primitive
        assert user.writeable is False

        msg = (
            r"No 'supported' presentation contexts are available for the "
            r"requestor service user"
        )
        with pytest.raises(ValueError, match=msg):
            user.supported_contexts

    def test_user_id_pre(self):
        """Test user_identity prior to association."""
        user = ServiceUser(self.assoc, mode="requestor")
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2
        assert user.user_identity is None

        item = UserIdentityNegotiation()
        item.user_identity_type = 0x01
        item.positive_response_requested = True
        item.primary_field = b"username"
        user.add_negotiation_item(item)
        assert item in user.extended_negotiation
        assert item in user._ext_neg[UserIdentityNegotiation]
        assert len(user.extended_negotiation) == 1
        assert len(user.user_information) == 3

        assert user.user_identity == item

    def test_user_id_post(self):
        """Test user_identity prior to association."""
        user = ServiceUser(self.assoc, mode="requestor")
        user.primitive = self.primitive
        assert len(user.extended_negotiation) == 0
        assert len(user.user_information) == 2
        assert user.user_identity is None

        item = UserIdentityNegotiation()
        item.user_identity_type = 0x01
        item.positive_response_requested = True
        item.primary_field = b"username"
        user.primitive.user_information.append(item)
        assert item in user.extended_negotiation
        assert item not in user._ext_neg[UserIdentityNegotiation]
        assert len(user.extended_negotiation) == 1
        assert len(user.user_information) == 3

        assert user.user_identity == item

        msg = r"Can't add extended negotiation items after negotiation"
        with pytest.raises(RuntimeError, match=msg):
            user.add_negotiation_item(item)

    def test_user_info_pre(self):
        """Test user_information prior to association."""
        user = ServiceUser(self.assoc, mode="requestor")
        assert len(user.user_information) == 2

        user.implementation_version_name = "VERSION_1"
        item = user.user_information[2]
        assert isinstance(item, ImplementationVersionNameNotification)
        assert item.implementation_version_name == "VERSION_1"
        assert len(user.user_information) == 3

        for uid in ["1.2", "3.4"]:
            item = SCP_SCU_RoleSelectionNegotiation()
            item.sop_class_uid = uid
            item.scu_role = False
            item.scp_role = True
            user.add_negotiation_item(item)
            assert item in user.user_information

        assert len(user.user_information) == 5

        item = AsynchronousOperationsWindowNegotiation()
        item.maximum_number_operations_invoked = 2
        item.maximum_number_operations_performed = 3
        user.add_negotiation_item(item)
        assert item in user.user_information
        assert len(user.user_information) == 6

        item = UserIdentityNegotiation()
        item.user_identity_type = 0x01
        item.positive_response_requested = True
        item.primary_field = b"username"
        user.add_negotiation_item(item)
        assert item in user.user_information
        assert len(user.user_information) == 7

        item = SOPClassExtendedNegotiation()
        item.sop_class_uid = "1.2.3"
        item.service_class_application_information = b"SOME DATA"
        user.add_negotiation_item(item)
        assert item in user.user_information
        assert len(user.user_information) == 8

        item = SOPClassCommonExtendedNegotiation()
        item.sop_class_uid = "1.2.3"
        item.service_class_uid = "2.3.4"
        item.related_general_sop_class_identification = ["1.3.4"]
        user.add_negotiation_item(item)
        assert item in user.user_information
        assert len(user.user_information) == 9

    def test_user_info_post(self):
        """Test user_information prior to association."""
        user = ServiceUser(self.assoc, mode="requestor")
        user.primitive = self.primitive
        assert len(user.user_information) == 2

        item = ImplementationVersionNameNotification()
        item.implementation_version_name = "VERSION_1"
        user.primitive.user_information.append(item)
        assert item in user.user_information
        assert len(user.user_information) == 3

        for uid in ["1.2", "3.4"]:
            item = SCP_SCU_RoleSelectionNegotiation()
            item.sop_class_uid = uid
            item.scu_role = False
            item.scp_role = True
            user.primitive.user_information.append(item)
            assert item in user.user_information

        assert len(user.user_information) == 5

        item = AsynchronousOperationsWindowNegotiation()
        item.maximum_number_operations_invoked = 2
        item.maximum_number_operations_performed = 3
        user.primitive.user_information.append(item)
        assert item in user.user_information
        assert len(user.user_information) == 6

        item = UserIdentityNegotiation()
        item.user_identity_type = 0x01
        item.positive_response_requested = True
        item.primary_field = b"username"
        user.primitive.user_information.append(item)
        assert item in user.user_information
        assert len(user.user_information) == 7

        item = SOPClassExtendedNegotiation()
        item.sop_class_uid = "1.2.3"
        item.service_class_application_information = b"SOME DATA"
        user.primitive.user_information.append(item)
        assert item in user.user_information
        assert len(user.user_information) == 8

        item = SOPClassCommonExtendedNegotiation()
        item.sop_class_uid = "1.2.3"
        item.service_class_uid = "2.3.4"
        item.related_general_sop_class_identification = ["1.3.4"]
        user.primitive.user_information.append(item)
        assert item in user.user_information
        assert len(user.user_information) == 9

    def test_writeable(self):
        """Test writeable."""
        user = ServiceUser(self.assoc, mode="requestor")
        assert user.writeable is True
        user.primitive = self.primitive
        assert user.writeable is False
