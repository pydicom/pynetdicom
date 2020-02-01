"""Tests for the pynetdicom.pdu module."""

from datetime import datetime
from io import BytesIO
import logging
import sys
import time

import pytest

from pydicom.uid import UID

from pynetdicom import AE, evt, Association, _config
from pynetdicom.events import Event
from pynetdicom.pdu import (
    A_ASSOCIATE_RQ, A_ASSOCIATE_AC, A_ASSOCIATE_RJ, P_DATA_TF, A_RELEASE_RQ,
    A_RELEASE_RP, A_ABORT_RQ, PDU, ApplicationContextItem,
    PresentationContextItemAC, PresentationContextItemRQ, UserInformationItem,
    PDU_ITEM_TYPES, PDU_TYPES,
    PACK_UCHAR, UNPACK_UCHAR
)
from pynetdicom.pdu_items import (
    PresentationDataValueItem,
    TransferSyntaxSubItem,
    MaximumLengthSubItem,
    ImplementationClassUIDSubItem, ImplementationVersionNameSubItem,
    AsynchronousOperationsWindowSubItem, SCP_SCU_RoleSelectionSubItem,
    SOPClassExtendedNegotiationSubItem,
    SOPClassCommonExtendedNegotiationSubItem, UserIdentitySubItemRQ,
    UserIdentitySubItemAC,
)
from pynetdicom.pdu_primitives import (
    MaximumLengthNotification, ImplementationClassUIDNotification,
    ImplementationVersionNameNotification, A_P_ABORT, A_ABORT, A_ASSOCIATE,
    P_DATA
)
from .encoded_pdu_items import (
    a_associate_rq, a_associate_ac, a_associate_rj, a_release_rq, a_release_rq,
    a_release_rp, a_abort, a_p_abort, p_data_tf,
    a_associate_rq_user_id_ext_neg, a_associate_ac_no_ts
)
from pynetdicom.sop_class import VerificationSOPClass
from pynetdicom.utils import pretty_bytes

LOGGER = logging.getLogger('pynetdicom')
LOGGER.setLevel(logging.CRITICAL)


class TestPDU(object):
    """Test the PDU equality/inequality operators."""
    def test_decode_raises(self):
        """Test the PDU.decode method raises NotImplementedError."""
        pdu = PDU()
        with pytest.raises(NotImplementedError):
            pdu.decode(a_release_rq)

    def test_decoders_raises(self):
        """Test the PDU._decoders property raises NotImplementedError."""
        pdu = PDU()
        with pytest.raises(NotImplementedError):
            pdu._decoders

    def test_equality(self):
        """Test the equality operator"""
        aa = A_ASSOCIATE_RQ()
        bb = A_ASSOCIATE_RQ()
        assert aa == bb
        assert not aa == 'TEST'

        aa.decode(a_associate_rq)
        assert not aa == bb

        bb.decode(a_associate_rq)
        assert aa == bb

        aa.calling_ae_title = b'TEST_AE_TITLE_00'
        assert not aa == bb

        assert aa == aa

    def test_encode_raises(self):
        """Test the PDU.encode method raises NotImplementedError."""
        pdu = PDU()
        with pytest.raises(NotImplementedError):
            pdu.encode()

    def test_encoders_raises(self):
        """Test the PDU._encoders property raises NotImplementedError."""
        pdu = PDU()
        with pytest.raises(NotImplementedError):
            pdu._encoders

    def test_generate_items(self):
        """Test the PDU._generate_items method."""
        pdu = PDU()
        gen = pdu._generate_items(b'')
        with pytest.raises(StopIteration):
            next(gen)

        data = b'\x10\x00\x00\x02\x01\x02'
        gen = pdu._generate_items(data)
        assert next(gen) == (0x10, data)
        with pytest.raises(StopIteration):
            next(gen)

        data += b'\x20\x00\x00\x03\x01\x02\x03'
        gen = pdu._generate_items(data)
        assert next(gen) == (0x10, b'\x10\x00\x00\x02\x01\x02')
        assert next(gen) == (0x20, b'\x20\x00\x00\x03\x01\x02\x03')
        with pytest.raises(StopIteration):
            next(gen)

    def test_generate_items_raises(self):
        """Test failure modes of PDU._generate_items method."""
        pdu = PDU()

        # Short data
        data = b'\x10\x00\x00\x02\x01'
        gen = pdu._generate_items(data)
        with pytest.raises(AssertionError):
            next(gen)

    def test_hash_raises(self):
        """Test hash(PDU) raises exception."""
        pdu = PDU()
        with pytest.raises(TypeError):
            hash(pdu)

    def test_inequality(self):
        """Test the inequality operator"""
        aa = A_ASSOCIATE_RQ()
        bb = A_ASSOCIATE_RQ()
        assert not aa != bb
        assert aa != 'TEST'

        aa.decode(a_associate_rq)
        assert aa != bb

        assert not aa != aa

    def test_pdu_length_raises(self):
        """Test PDU.pdu_length raises NotImplementedError."""
        pdu = PDU()
        with pytest.raises(NotImplementedError):
            pdu.pdu_length

    def test_pdu_type_raises(self):
        """Test PDU.pdu_type raises ValueError."""
        pdu = PDU()
        with pytest.raises(KeyError):
            pdu.pdu_type

    def test_wrap_bytes(self):
        """Test PDU._wrap_bytes()."""
        pdu = PDU()
        assert pdu._wrap_bytes(b'') == b''
        assert pdu._wrap_bytes(b'\x00\x01') == b'\x00\x01'

    def test_wrap_encode_items(self):
        """Test PDU._wrap_encode_items()."""
        release_a = A_RELEASE_RQ()
        release_b = A_RELEASE_RQ()
        pdu = PDU()
        out = pdu._wrap_encode_items([release_a])
        assert out == b'\x05\x00\x00\x00\x00\x04\x00\x00\x00\x00'

        out = pdu._wrap_encode_items([release_a, release_a])
        assert out == b'\x05\x00\x00\x00\x00\x04\x00\x00\x00\x00' * 2

    def test_wrap_encode_uid(self):
        """Test PDU._wrap_encode_uid()."""
        pdu = PDU()
        uid = UID('1.2.840.10008.1.1')
        out = pdu._wrap_encode_uid(uid)
        assert out == b'1.2.840.10008.1.1'

    def test_wrap_generate_items(self):
        """Test PDU._wrap_generate_items()."""
        pdu = PDU()
        out = pdu._wrap_generate_items(b'')
        assert out == []

        data = b'\x10\x00\x00\x03\x31\x2e\x32'
        out = pdu._wrap_generate_items(data)
        assert out[0].application_context_name == '1.2'

        data += b'\x10\x00\x00\x04\x31\x2e\x32\x33'
        out = pdu._wrap_generate_items(data)
        assert out[0].application_context_name == '1.2'
        assert out[1].application_context_name == '1.23'

    def test_wrap_pack(self):
        """Test PDU._wrap_pack()."""
        pdu = PDU()
        out = pdu._wrap_pack(1, PACK_UCHAR)
        assert out == b'\x01'

    def test_wrap_unpack(self):
        """Test PDU._wrap_unpack()."""
        pdu = PDU()
        out = pdu._wrap_unpack(b'\x01', UNPACK_UCHAR)
        assert out == 1


class TestASSOC_RQ(object):
    """Test the A_ASSOCIATE_RQ class."""
    def test_init(self):
        pdu = A_ASSOCIATE_RQ()
        assert pdu.protocol_version == 0x01
        assert pdu.calling_ae_title == b'Default         '
        assert pdu.called_ae_title == b'Default         '
        assert pdu.variable_items == []
        assert pdu.pdu_type == 0x01
        assert pdu.pdu_length == 68
        assert len(pdu) == 74

        assert pdu.application_context_name is None
        assert pdu.presentation_context == []
        assert pdu.user_information is None

    def test_property_setters(self):
        """Check the property setters are working correctly."""
        pdu = A_ASSOCIATE_RQ()

        # pdu.called_ae_title
        assert pdu.called_ae_title == b'Default         '
        pdu.called_ae_title = 'TEST_SCP'
        assert pdu.called_ae_title == b'TEST_SCP        '

        # pdu.calling_ae_title
        assert pdu.calling_ae_title == b'Default         '
        pdu.calling_ae_title = 'TEST_SCP2'
        assert pdu.calling_ae_title == b'TEST_SCP2       '

    def test_string_output(self):
        """Check the string output works"""
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)
        assert "Verification SOP Class" in pdu.__str__()
        assert "Implicit VR Little Endian" in pdu.__str__()
        assert "3680043.9.3811.0.9.0" in pdu.__str__()

    def test_decode(self):
        """Check decoding assoc_rq produces the correct attribute values."""
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)

        assert pdu.protocol_version == 0x01
        assert pdu.calling_ae_title == b'ECHOSCU         '
        assert pdu.called_ae_title == b'ANY-SCP         '
        assert pdu.pdu_type == 0x01
        assert pdu.pdu_length == 209
        assert len(pdu) == 215

        assert len(pdu.presentation_context) == 1
        assert len(pdu.user_information.user_data) == 3

        # Check VariableItems
        #   The actual items will be tested separately
        assert len(pdu.variable_items) == 3
        assert isinstance(pdu.variable_items[0], ApplicationContextItem)
        assert isinstance(pdu.variable_items[1], PresentationContextItemRQ)
        assert isinstance(pdu.variable_items[2], UserInformationItem)

    def test_decode_properties(self):
        """Check decoding produces the correct property values."""
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)

        # Check application_context_name property
        app_name = pdu.application_context_name
        assert isinstance(app_name, UID)
        assert app_name == '1.2.840.10008.3.1.1.1'

        # Check presentation_context property
        contexts = pdu.presentation_context
        assert isinstance(contexts, list)
        for context in contexts:
            assert isinstance(context, PresentationContextItemRQ)

        # Check user_information property
        user_info = pdu.user_information
        assert isinstance(user_info, UserInformationItem)

    def test_encode(self):
        """Check encoding produces the correct output."""
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)
        out = pdu.encode()

        assert out == a_associate_rq

    def test_to_primitive(self):
        """Check converting PDU to primitive"""
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)

        pr = pdu.to_primitive()

        assert pr.application_context_name == UID('1.2.840.10008.3.1.1.1')
        assert pr.calling_ae_title == b'ECHOSCU         '
        assert pr.called_ae_title == b'ANY-SCP         '

        # Test User Information
        for item in pr.user_information:
            # Maximum PDU Length (required)
            if isinstance(item, MaximumLengthNotification):
                assert item.maximum_length_received == 16382
                assert isinstance(item.maximum_length_received, int)

            # Implementation Class UID (required)
            elif isinstance(item, ImplementationClassUIDNotification):
                assert item.implementation_class_uid == UID(
                    '1.2.826.0.1.3680043.9.3811.0.9.0'
                )
                assert isinstance(item.implementation_class_uid, UID)

            # Implementation Version Name (optional)
            elif isinstance(item, ImplementationVersionNameNotification):
                assert item.implementation_version_name == b'PYNETDICOM_090'
                assert isinstance(item.implementation_version_name, bytes)

        # Test Presentation Contexts
        for context in pr.presentation_context_definition_list:
            assert context.context_id == 1
            assert context.abstract_syntax == UID('1.2.840.10008.1.1')
            for syntax in context.transfer_syntax:
                assert syntax == UID('1.2.840.10008.1.2')

        assert isinstance(pr.application_context_name, UID)
        assert isinstance(pr.calling_ae_title, bytes)
        assert isinstance(pr.called_ae_title, bytes)
        assert isinstance(pr.user_information, list)
        assert isinstance(pr.presentation_context_definition_list, list)

        # Not used by A-ASSOCIATE-RQ or fixed value
        assert pr.mode == "normal"
        assert pr.responding_ae_title == pr.called_ae_title
        assert pr.result is None
        assert pr.result_source is None
        assert pr.diagnostic is None
        assert pr.calling_presentation_address is None
        assert pr.called_presentation_address is None
        assert pr.responding_presentation_address == (
            pr.called_presentation_address
        )
        assert pr.presentation_context_definition_results_list == []
        assert pr.presentation_requirements == "Presentation Kernel"
        assert pr.session_requirements == ""

    def test_from_primitive(self):
        """Check converting primitive to PDU."""
        orig_pdu = A_ASSOCIATE_RQ()
        orig_pdu.decode(a_associate_rq)
        primitive = orig_pdu.to_primitive()

        new_pdu = A_ASSOCIATE_RQ()
        new_pdu.from_primitive(primitive)

        assert new_pdu == orig_pdu
        assert new_pdu.encode() == a_associate_rq


class TestASSOC_RQ_ApplicationContext(object):
    def test_decode(self):
        """Check decoding assoc_rq produces the correct application context."""
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)

        app_context = pdu.variable_items[0]

        assert app_context.item_type == 0x10
        assert app_context.item_length == 21
        assert len(app_context) == 25
        assert app_context.application_context_name == '1.2.840.10008.3.1.1.1'
        assert isinstance(app_context.application_context_name, UID)


class TestASSOC_RQ_PresentationContext(object):
    def test_decode(self):
        """Check decoding assoc_rq produces the correct presentation context."""
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)

        # Check PresentationContextItemRQ attributes
        context = pdu.variable_items[1]
        assert context.item_type == 0x20
        assert context.item_length == 46
        assert len(context) == 50
        assert context.presentation_context_id == 0x001

        assert len(context.abstract_transfer_syntax_sub_items) == 2

    def test_decode_properties(self):
        """Check decoding produces the correct property values."""
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)

        context = pdu.presentation_context[0]

        # Check context_id property
        assert context.context_id == 1

        # Check abstract_syntax property
        assert isinstance(context.abstract_syntax, UID)
        assert context.abstract_syntax == UID('1.2.840.10008.1.1')

        # Check transfer_syntax property
        assert isinstance(context.transfer_syntax, list)
        assert len(context.transfer_syntax) == 1

        for syntax in pdu.presentation_context[0].transfer_syntax:
            assert isinstance(syntax, UID)

        # Check first transfer syntax is little endian implicit
        syntax = pdu.presentation_context[0].transfer_syntax[0]
        assert syntax == UID('1.2.840.10008.1.2')


class TestASSOC_RQ_PresentationContext_AbstractSyntax(object):
    def test_decode(self):
        """Check decoding assoc_rq produces the correct abstract syntax."""
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)

        context = pdu.presentation_context[0]

        abstract_syntax = context.abstract_transfer_syntax_sub_items[0]

        assert abstract_syntax.item_type == 0x30
        assert abstract_syntax.item_length == 17
        assert len(abstract_syntax) == 21
        assert abstract_syntax.abstract_syntax_name == UID('1.2.840.10008.1.1')
        assert isinstance(abstract_syntax.abstract_syntax_name, UID)


class TestASSOC_RQ_PresentationContext_TransferSyntax(object):
    def test_decode(self):
        """ Check decoding an assoc_rq produces the correct transfer syntax """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)

        context = pdu.presentation_context[0]
        transfer_syntaxes = context.transfer_syntax

        # Check TransferSyntax property is a list
        assert isinstance(transfer_syntaxes, list)

        # Check TransferSyntax list contains transfer syntax type UIDs
        for syntax in transfer_syntaxes:
            assert isinstance(syntax, UID)

        # Check first transfer syntax is little endian implicit
        syntax = transfer_syntaxes[0]
        assert syntax, UID('1.2.840.10008.1.2')


class TestASSOC_RQ_UserInformation(object):
    def test_decode(self):
        """Check decoding an assoc_rq produces the correct user information."""
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)

        user_info = pdu.variable_items[2]

        assert user_info.item_type == 0x50
        assert user_info.item_length == 62
        assert len(user_info) == 66
        assert isinstance(user_info.user_data, list)

        # Test user items
        for item in user_info.user_data:
            # Maximum PDU Length (required)
            if isinstance(item, MaximumLengthSubItem):
                assert item.maximum_length_received == 16382
                assert user_info.maximum_length == 16382

            # Implementation Class UID (required)
            elif isinstance(item, ImplementationClassUIDSubItem):
                assert item.item_type == 0x52
                assert item.item_length == 32
                assert item.implementation_class_uid == UID(
                    '1.2.826.0.1.3680043.9.3811.0.9.0'
                )
                assert isinstance(item.item_type, int)
                assert isinstance(item.item_length, int)
                assert isinstance(item.implementation_class_uid, UID)

            # Implementation Version Name (optional)
            elif isinstance(item, ImplementationVersionNameSubItem):
                assert item.item_type == 0x55
                assert item.item_length == 14
                assert item.implementation_version_name == b'PYNETDICOM_090'
                assert isinstance(item.item_type, int)
                assert isinstance(item.item_length, int)
                assert isinstance(item.implementation_version_name, bytes)

    def test_decode_properties(self):
        """Check decoding produces the correct property values."""
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)

        user_info = pdu.variable_items[2]
        assert user_info.async_ops_window is None
        assert user_info.common_ext_neg == []
        assert user_info.ext_neg == []
        assert user_info.implementation_class_uid == (
            '1.2.826.0.1.3680043.9.3811.0.9.0'
        )
        assert user_info.implementation_version_name == b'PYNETDICOM_090'
        assert user_info.maximum_length == 16382
        assert user_info.role_selection == {}
        assert user_info.user_identity is None


class TestASSOC_AC(object):
    def test_init(self):
        """Test a new A_ASSOCIATE_AC PDU."""
        pdu = A_ASSOCIATE_AC()
        assert pdu.protocol_version == 0x01
        assert pdu._reserved_aet is None
        assert pdu._reserved_aec is None
        assert pdu.variable_items == []
        assert pdu.pdu_type == 0x02
        assert pdu.pdu_length == 68
        assert len(pdu) ==  74

        assert pdu.application_context_name is None
        assert pdu.called_ae_title is None
        assert pdu.calling_ae_title is None
        assert pdu.presentation_context == []
        assert pdu.user_information is None

    def test_string_output(self):
        """Test the string output"""
        pdu = A_ASSOCIATE_AC()
        pdu.decode(a_associate_ac)
        assert "Implicit VR Little Endian" in pdu.__str__()
        assert "1.2.276.0.7230010" in pdu.__str__()

    def test_decode(self):
        """ Check decoding the assoc_ac stream produces the correct objects """
        pdu = A_ASSOCIATE_AC()
        pdu.decode(a_associate_ac)

        assert pdu.pdu_type == 0x02
        assert pdu.pdu_length == 184
        assert pdu.protocol_version == 0x0001
        assert isinstance(pdu.pdu_type, int)
        assert isinstance(pdu.pdu_length, int)
        assert isinstance(pdu.protocol_version, int)

        # Check VariableItems
        #   The actual items will be tested separately
        assert isinstance(pdu.variable_items[0], ApplicationContextItem)
        assert isinstance(pdu.variable_items[1], PresentationContextItemAC)
        assert isinstance(pdu.variable_items[2], UserInformationItem)

    def test_decode_properties(self):
        """Check decoding produces the correct property values."""
        pdu = A_ASSOCIATE_AC()
        pdu.decode(a_associate_ac)

        # Check AE titles
        assert pdu._reserved_aec == b'ECHOSCU         '
        assert pdu._reserved_aet == b'ANY-SCP         '
        assert pdu.calling_ae_title == b'ECHOSCU         '
        assert pdu.called_ae_title == b'ANY-SCP         '

        # Check application_context_name property
        assert isinstance(pdu.application_context_name, UID)
        assert pdu.application_context_name == '1.2.840.10008.3.1.1.1'

        # Check presentation_context property
        contexts = pdu.presentation_context
        assert isinstance(contexts, list)
        assert len(contexts) == 1
        for context in contexts:
            assert isinstance(context, PresentationContextItemAC)

        # Check user_information property
        user_info = pdu.user_information
        assert isinstance(user_info, UserInformationItem)

    def test_stream_encode(self):
        """ Check encoding an assoc_ac produces the correct output """
        pdu = A_ASSOCIATE_AC()
        pdu.decode(a_associate_ac)

        assert pdu.encode() == a_associate_ac

    def test_to_primitive(self):
        """ Check converting PDU to primitive """
        pdu = A_ASSOCIATE_AC()
        pdu.decode(a_associate_ac)

        primitive = pdu.to_primitive()

        assert primitive.application_context_name == UID(
            '1.2.840.10008.3.1.1.1'
        )
        assert primitive.calling_ae_title == b'ECHOSCU         '
        assert primitive.called_ae_title == b'ANY-SCP         '

        # Test User Information
        for item in primitive.user_information:
            # Maximum PDU Length (required)
            if isinstance(item, MaximumLengthNotification):
                assert item.maximum_length_received == 16384
                assert isinstance(item.maximum_length_received, int)

            # Implementation Class UID (required)
            elif isinstance(item, ImplementationClassUIDNotification):
                assert item.implementation_class_uid == UID(
                    '1.2.276.0.7230010.3.0.3.6.0'
                )
                assert isinstance(item.implementation_class_uid, UID)

            # Implementation Version Name (optional)
            elif isinstance(item, ImplementationVersionNameNotification):
                assert item.implementation_version_name == b'OFFIS_DCMTK_360'
                assert isinstance(item.implementation_version_name, bytes)

        # Test Presentation Contexts
        for context in primitive.presentation_context_definition_list:
            assert context.context_id == 1
            assert context.transfer_syntax[0] == UID('1.2.840.10008.1.2')

        assert isinstance(primitive.application_context_name, UID)
        assert isinstance(primitive.calling_ae_title, bytes)
        assert isinstance(primitive.called_ae_title, bytes)
        assert isinstance(primitive.user_information, list)

        assert primitive.result == 0
        assert len(primitive.presentation_context_definition_results_list) == 1

        # Not used by A-ASSOCIATE-AC or fixed value
        assert primitive.mode == "normal"
        assert primitive.responding_ae_title == primitive.called_ae_title
        assert primitive.result_source is None
        assert primitive.diagnostic is None
        assert primitive.calling_presentation_address is None
        assert primitive.called_presentation_address is None
        assert primitive.responding_presentation_address == (
            primitive.called_presentation_address
        )
        assert primitive.presentation_context_definition_list == []
        assert primitive.presentation_requirements == "Presentation Kernel"
        assert primitive.session_requirements == ""

    def test_from_primitive(self):
        """ Check converting PDU to primitive """
        orig = A_ASSOCIATE_AC()
        orig.decode(a_associate_ac)

        primitive = orig.to_primitive()

        new = A_ASSOCIATE_AC()
        new.from_primitive(primitive)

        assert new == orig

    def test_no_transfer_syntax(self):
        """Regression test for #361 - ASSOC-AC has no transfer syntax"""
        pdu = A_ASSOCIATE_AC()
        pdu.decode(a_associate_ac_no_ts)

        assert pdu.pdu_type == 0x02
        assert pdu.pdu_length == 167
        assert pdu.protocol_version == 0x0001
        assert isinstance(pdu.pdu_type, int)
        assert isinstance(pdu.pdu_length, int)
        assert isinstance(pdu.protocol_version, int)

        item = pdu.variable_items[1]
        cx = item.to_primitive()
        assert cx.transfer_syntax == []
        assert cx.result == 3
        assert cx.context_id == 1


class TestASSOC_AC_ApplicationContext(object):
    def test_decode(self):
        """Check decoding produces the correct application context."""
        pdu = A_ASSOCIATE_AC()
        pdu.decode(a_associate_ac)

        app_context = pdu.variable_items[0]

        assert app_context.item_type == 0x10
        assert app_context.item_length == 21
        assert app_context.application_context_name == '1.2.840.10008.3.1.1.1'
        assert isinstance(app_context.application_context_name, UID)


class TestASSOC_AC_PresentationContext(object):
    def test_decode(self):
        """Check decoding produces the correct presentation context."""
        pdu = A_ASSOCIATE_AC()
        pdu.decode(a_associate_ac)

        # Check PresentationContextItemRQ attributes
        context = pdu.variable_items[1]
        assert context.item_type == 0x21
        assert context.item_length == 25
        assert len(context) == 29
        assert context.presentation_context_id == 0x01
        assert context.result_reason == 0
        assert len(context.transfer_syntax_sub_item) == 1
        syntax = context.transfer_syntax_sub_item[0]
        assert isinstance(syntax, TransferSyntaxSubItem)
        assert isinstance(syntax.transfer_syntax_name, UID)
        assert syntax.transfer_syntax_name == UID('1.2.840.10008.1.2')

    def test_decode_properties(self):
        """ Check decoding the produces the correct properties """
        pdu = A_ASSOCIATE_AC()
        pdu.decode(a_associate_ac)

        context = pdu.presentation_context[0]

        # Check context_id property
        assert context.context_id == 1

        # Check result
        assert context.result == 0
        assert context.result == context.result_reason

        # Check transfer syntax
        assert isinstance(context.transfer_syntax, UID)
        assert context.transfer_syntax == UID('1.2.840.10008.1.2')

        # result_str
        assert context.result_str == 'Accepted'


class TestASSOC_AC_PresentationContext_TransferSyntax(object):
    def test_decode(self):
        """ Check decoding an assoc_ac produces the correct transfer syntax """
        pdu = A_ASSOCIATE_AC()
        pdu.decode(a_associate_ac)

        syntax = pdu.presentation_context[0].transfer_syntax

        assert isinstance(syntax, UID)
        assert syntax == UID('1.2.840.10008.1.2')


class TestASSOC_AC_UserInformation(object):
    def test_decode(self):
        """ Check decoding an assoc_rq produces the correct user information """
        pdu = A_ASSOCIATE_AC()
        pdu.decode(a_associate_ac)

        user_info = pdu.variable_items[2]

        assert user_info.item_type == 0x50
        assert user_info.item_length == 58
        assert len(user_info) == 62
        assert isinstance(user_info.user_data, list)

        # Test user items
        for item in user_info.user_data:
            # Maximum PDU Length (required)
            if isinstance(item, MaximumLengthSubItem):
                assert item.maximum_length_received == 16384
                assert user_info.maximum_length == 16384

            # Implementation Class UID (required)
            elif isinstance(item, ImplementationClassUIDSubItem):
                assert item.item_type == 0x52
                assert item.item_length == 27
                assert item.implementation_class_uid == UID(
                    '1.2.276.0.7230010.3.0.3.6.0'
                )
                assert isinstance(item.item_type, int)
                assert isinstance(item.item_length, int)
                assert isinstance(item.implementation_class_uid, UID)

            # Implementation Version Name (optional)
            elif isinstance(item, ImplementationVersionNameSubItem):
                assert item.item_type == 0x55
                assert item.item_length == 15
                assert item.implementation_version_name == b'OFFIS_DCMTK_360'
                assert isinstance(item.item_type, int)
                assert isinstance(item.item_length, int)
                assert isinstance(item.implementation_version_name, bytes)

    def test_decode_properties(self):
        """Check decoding produces the correct property values."""
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_ac)

        user_info = pdu.variable_items[2]
        assert user_info.async_ops_window is None
        assert user_info.common_ext_neg == []
        assert user_info.ext_neg == []
        assert user_info.implementation_class_uid == (
            '1.2.276.0.7230010.3.0.3.6.0'
        )
        assert user_info.implementation_version_name == b'OFFIS_DCMTK_360'
        assert user_info.maximum_length == 16384
        assert user_info.role_selection == {}
        assert user_info.user_identity is None


class TestASSOC_RJ(object):
    def test_init(self):
        """Test a new A_ASSOCIATE_RJ PDU."""
        pdu = A_ASSOCIATE_RJ()
        assert pdu.result is None
        assert pdu.source is None
        assert pdu.reason_diagnostic is None
        assert pdu.pdu_type == 0x03
        assert pdu.pdu_length == 4
        assert len(pdu) == 10

        with pytest.raises(ValueError):
            pdu.reason_str

        with pytest.raises(ValueError):
            pdu.result_str

        with pytest.raises(ValueError):
            pdu.source_str

    def test_string_output(self):
        """Test the string output"""
        pdu = A_ASSOCIATE_RJ()
        pdu.decode(a_associate_rj)
        assert "Rejected (Permanent)" in pdu.__str__()
        assert "DUL service-user" in pdu.__str__()

    def test_decod(self):
        """ Check decoding produces the correct objects """
        pdu = A_ASSOCIATE_RJ()
        pdu.decode(a_associate_rj)

        assert pdu.pdu_type == 0x03
        assert pdu.pdu_length == 4
        assert len(pdu) == 10
        assert pdu.result == 1
        assert pdu.source == 1
        assert pdu.reason_diagnostic == 1

    def test_decode_properties(self):
        """ Check decoding produces the correct properties """
        pdu = A_ASSOCIATE_RJ()
        pdu.decode(a_associate_rj)

        # Check reason/source/result
        assert pdu.result_str == 'Rejected (Permanent)'
        assert pdu.reason_str == 'No reason given'
        assert pdu.source_str == 'DUL service-user'

    def test_encode(self):
        """ Check encoding an assoc_rj produces the correct output """
        pdu = A_ASSOCIATE_RJ()
        pdu.decode(a_associate_rj)

        assert pdu.encode() == a_associate_rj

    def test_to_primitive(self):
        """ Check converting PDU to primitive """
        pdu = A_ASSOCIATE_RJ()
        pdu.decode(a_associate_rj)

        primitive = pdu.to_primitive()

        assert primitive.result == 1
        assert primitive.result_source == 1
        assert primitive.diagnostic == 1
        assert isinstance(primitive.result, int)
        assert isinstance(primitive.result_source, int)
        assert isinstance(primitive.diagnostic, int)

        # Not used by A-ASSOCIATE-RJ or fixed value
        assert primitive.mode == "normal"
        assert primitive.application_context_name is None
        assert primitive.calling_ae_title is None
        assert primitive.called_ae_title is None
        assert primitive.responding_ae_title is None
        assert primitive.user_information == []
        assert primitive.calling_presentation_address is None
        assert primitive.called_presentation_address is None
        assert primitive.responding_presentation_address == (
            primitive.called_presentation_address
        )
        assert primitive.presentation_context_definition_list == []
        assert primitive.presentation_context_definition_results_list == []
        assert primitive.presentation_requirements == "Presentation Kernel"
        assert primitive.session_requirements == ""

    def test_from_primitive(self):
        """ Check converting PDU to primitive """
        orig_pdu = A_ASSOCIATE_RJ()
        orig_pdu.decode(a_associate_rj)

        primitive = orig_pdu.to_primitive()

        new_pdu = A_ASSOCIATE_RJ()
        new_pdu.from_primitive(primitive)

        assert new_pdu == orig_pdu

    def test_result_str(self):
        """ Check the result str returns correct values """
        pdu = A_ASSOCIATE_RJ()
        pdu.decode(a_associate_rj)

        pdu.result = 0
        with pytest.raises(ValueError):
            pdu.result_str

        pdu.result = 1
        assert pdu.result_str == 'Rejected (Permanent)'

        pdu.result = 2
        assert pdu.result_str == 'Rejected (Transient)'

        pdu.result = 3
        with pytest.raises(ValueError):
            pdu.result_str

    def test_source_str(self):
        """ Check the source str returns correct values """
        pdu = A_ASSOCIATE_RJ()
        pdu.decode(a_associate_rj)

        pdu.source = 0
        with pytest.raises(ValueError):
            pdu.source_str

        pdu.source = 1
        assert pdu.source_str == 'DUL service-user'

        pdu.source = 2
        assert pdu.source_str == 'DUL service-provider (ACSE related)'

        pdu.source = 3
        assert pdu.source_str == 'DUL service-provider (presentation related)'

        pdu.source = 4
        with pytest.raises(ValueError):
            pdu.source_str

    def test_reason_str(self):
        """ Check the reason str returns correct values """
        pdu = A_ASSOCIATE_RJ()
        pdu.decode(a_associate_rj)

        pdu.source = 0
        with pytest.raises(ValueError):
            pdu.reason_str

        pdu.source = 1
        for ii in range(1, 11):
            pdu.reason_diagnostic = ii
            assert isinstance(pdu.reason_str, str)

        pdu.reason_diagnostic = 11
        with pytest.raises(ValueError):
            pdu.reason_str

        pdu.source = 2
        for ii in range(1, 3):
            pdu.reason_diagnostic = ii
            assert isinstance(pdu.reason_str, str)

        pdu.reason_diagnostic = 3
        with pytest.raises(ValueError):
            pdu.reason_str

        pdu.source = 3
        for ii in range(1, 8):
            pdu.reason_diagnostic = ii
            assert isinstance(pdu.reason_str, str)

        pdu.reason_diagnostic = 8
        with pytest.raises(ValueError):
            pdu.reason_str

        pdu.source = 4
        with pytest.raises(ValueError):
            pdu.reason_str


class TestP_DATA_TF(object):
    def test_init(self):
        """Test a new P_DATA_TF"""
        pdu = P_DATA_TF()
        assert pdu.presentation_data_value_items == []
        assert pdu.pdu_type == 0x04
        assert pdu.pdu_length == 0
        assert len(pdu) == 6

    def test_string_output(self):
        """Test the string output"""
        pdu = P_DATA_TF()
        pdu.decode(p_data_tf)
        assert "80 bytes" in pdu.__str__()
        assert "0x03 0x00" in pdu.__str__()

    def test_decode(self):
        """ Check decoding the p_data stream produces the correct objects """
        pdu = P_DATA_TF()
        pdu.decode(p_data_tf)

        assert pdu.pdu_type == 0x04
        assert pdu.pdu_length == 84
        assert len(pdu) == 90

        assert len(pdu.presentation_data_value_items) == 1
        assert isinstance(pdu.presentation_data_value_items[0],
                          PresentationDataValueItem)
        pdv = pdu.presentation_data_value_items[0]
        assert pdv.presentation_context_id == 1
        assert pdv.presentation_data_value == (
            b'\x03\x00\x00\x00\x00\x04\x00\x00\x00\x42\x00\x00\x00\x00\x00\x02\x00'
            b'\x12\x00\x00\x00\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38'
            b'\x2e\x31\x2e\x31\x00\x00\x00\x00\x01\x02\x00\x00\x00\x30\x80\x00\x00'
            b'\x20\x01\x02\x00\x00\x00\x01\x00\x00\x00\x00\x08\x02\x00\x00\x00\x01'
            b'\x01\x00\x00\x00\x09\x02\x00\x00\x00\x00\x00'
        )

    def test_encode(self):
        """ Check encoding an p_data produces the correct output """
        pdu = P_DATA_TF()
        pdu.decode(p_data_tf)

        assert pdu.encode() == p_data_tf

    def test_to_primitive(self):
        """ Check converting PDU to primitive """
        pdu = P_DATA_TF()
        pdu.decode(p_data_tf)

        primitive = pdu.to_primitive()

        assert primitive.presentation_data_value_list == [[1, p_data_tf[11:]]]
        assert isinstance(primitive.presentation_data_value_list, list)

    def test_from_primitive(self):
        """ Check converting PDU to primitive """
        orig_pdu = P_DATA_TF()
        orig_pdu.decode(p_data_tf)
        primitive = orig_pdu.to_primitive()

        new_pdu = P_DATA_TF()
        new_pdu.from_primitive(primitive)
        pdv = new_pdu.presentation_data_value_items[0]

        assert new_pdu == orig_pdu

    def test_generate_items(self):
        """Test ._generate_items"""
        pdu = P_DATA_TF()
        gen = pdu._generate_items(b'')
        with pytest.raises(StopIteration):
            next(gen)

        data = b'\x00\x00\x00\x04\x01\x01\x02\x03'
        gen = pdu._generate_items(data)
        assert next(gen) == (1, b'\x01\x02\x03')
        with pytest.raises(StopIteration):
            next(gen)

        data += b'\x00\x00\x00\x05\x02\x03\x01\x02\x03'
        gen = pdu._generate_items(data)
        assert next(gen) == (1, b'\x01\x02\x03')
        assert next(gen) == (2, b'\x03\x01\x02\x03')
        with pytest.raises(StopIteration):
            next(gen)

    def test_generate_items_raises(self):
        """Test failure modes of ._generate_items method."""
        pdu = P_DATA_TF()

        # Short data
        data = b'\x00\x00\x00\x04\x01\x01\x02'
        gen = pdu._generate_items(data)
        with pytest.raises(AssertionError):
            next(gen)

    def test_wrap_generate_items(self):
        """Test ._wrap_generate_items"""
        pdu = P_DATA_TF()
        out = pdu._wrap_generate_items(b'')
        assert out == []

        data = b'\x00\x00\x00\x04\x01\x01\x02\x03'
        out = pdu._wrap_generate_items(data)
        assert len(out) == 1
        assert isinstance(out[0], PresentationDataValueItem)
        assert out[0].context_id == 1
        assert out[0].presentation_data_value == b'\x01\x02\x03'

        data += b'\x00\x00\x00\x05\x02\x03\x01\x02\x03'
        out = pdu._wrap_generate_items(data)
        assert len(out) == 2
        assert isinstance(out[0], PresentationDataValueItem)
        assert isinstance(out[1], PresentationDataValueItem)
        assert out[0].context_id == 1
        assert out[1].context_id == 2
        assert out[0].presentation_data_value == b'\x01\x02\x03'
        assert out[1].presentation_data_value == b'\x03\x01\x02\x03'


class TestRELEASE_RQ(object):
    def test_init(self):
        """Test a new A_RELEASE_RQ PDU"""
        pdu = A_RELEASE_RQ()
        assert pdu.pdu_type == 0x05
        assert pdu.pdu_length == 4
        assert len(pdu) == 10

    def test_string_output(self):
        """Test the string output"""
        pdu = A_RELEASE_RQ()
        pdu.decode(a_release_rq)
        assert "0x05" in pdu.__str__()
        assert "4 bytes" in pdu.__str__()

    def test_decode(self):
        """ Check decoding the release_rq stream produces the correct objects """
        pdu = A_RELEASE_RQ()
        pdu.decode(a_release_rq)

        assert pdu.pdu_type == 0x05
        assert pdu.pdu_length == 4
        assert len(pdu) == 10

    def test_encode(self):
        """ Check encoding an release_rq produces the correct output """
        pdu = A_RELEASE_RQ()
        pdu.decode(a_release_rq)

        assert pdu.encode() == a_release_rq

    def test_to_primitive(self):
        """ Check converting PDU to primitive """
        pdu = A_RELEASE_RQ()
        pdu.decode(a_release_rq)

        primitive = pdu.to_primitive()

        assert primitive.reason == "normal"
        assert primitive.result is None

    def test_from_primitive(self):
        """ Check converting PDU to primitive """
        orig_pdu = A_RELEASE_RQ()
        orig_pdu.decode(a_release_rq)

        primitive = orig_pdu.to_primitive()

        new_pdu = A_RELEASE_RQ()
        new_pdu.from_primitive(primitive)

        assert new_pdu == orig_pdu


class TestRELEASE_RP(object):
    def test_init(self):
        """Test a new A_RELEASE_RQ PDU"""
        pdu = A_RELEASE_RP()
        assert pdu.pdu_type == 0x06
        assert pdu.pdu_length == 4
        assert len(pdu) == 10

    def test_string_output(self):
        """Test the string output"""
        pdu = A_RELEASE_RP()
        pdu.decode(a_release_rp)
        assert "0x06" in pdu.__str__()
        assert "4 bytes" in pdu.__str__()

    def test_decode(self):
        """ Check decoding the release_rp stream produces the correct objects """
        pdu = A_RELEASE_RP()
        pdu.decode(a_release_rp)

        assert pdu.pdu_type == 0x06
        assert pdu.pdu_length == 4
        assert len(pdu) == 10

    def test_encode(self):
        """ Check encoding an release_rp produces the correct output """
        pdu = A_RELEASE_RP()
        pdu.decode(a_release_rp)

        assert pdu.encode() == a_release_rp

    def test_to_primitive(self):
        """ Check converting PDU to primitive """
        pdu = A_RELEASE_RP()
        pdu.decode(a_release_rp)

        primitive = pdu.to_primitive()

        assert primitive.reason == "normal"
        assert primitive.result == "affirmative"

    def test_from_primitive(self):
        """ Check converting PDU to primitive """
        orig_pdu = A_RELEASE_RP()
        orig_pdu.decode(a_release_rp)

        primitive = orig_pdu.to_primitive()

        new_pdu = A_RELEASE_RP()
        new_pdu.from_primitive(primitive)

        assert new_pdu == orig_pdu


class TestABORT(object):
    def test_init(self):
        """Test a new A_ABORT_RQ PDU"""
        pdu = A_ABORT_RQ()
        assert pdu.pdu_type == 0x07
        assert pdu.pdu_length == 4
        assert len(pdu) == 10
        assert pdu.source is None
        assert pdu.reason_diagnostic is None

        with pytest.raises(KeyError):
            pdu.source_str

        pdu.reason_str == 'No reason given'

    def test_string_output(self):
        """Test the string output"""
        pdu = A_ABORT_RQ()
        pdu.decode(a_abort)
        assert "0x07" in pdu.__str__()
        assert "4 bytes" in pdu.__str__()
        assert "DUL service-user" in pdu.__str__()

    def test_a_abort_decode(self):
        """ Check decoding the a_abort stream produces the correct objects """
        pdu = A_ABORT_RQ()
        pdu.decode(a_abort)

        assert pdu.pdu_type == 0x07
        assert pdu.pdu_length == 4
        assert pdu.source == 0
        assert pdu.reason_diagnostic == 0
        assert len(pdu) == 10

    def test_a_p_abort_decode(self):
        """ Check decoding the a_abort stream produces the correct objects """
        pdu = A_ABORT_RQ()
        pdu.decode(a_p_abort)

        assert pdu.pdu_type == 0x07
        assert pdu.pdu_length == 4
        assert pdu.source == 2
        assert pdu.reason_diagnostic == 4

    def test_a_abort_encode(self):
        """ Check encoding an a_abort produces the correct output """
        pdu = A_ABORT_RQ()
        pdu.decode(a_abort)

        assert pdu.encode() == a_abort

    def test_a_p_abort_encode(self):
        """ Check encoding an a_abort produces the correct output """
        pdu = A_ABORT_RQ()
        pdu.decode(a_p_abort)

        assert pdu.encode() == a_p_abort

    def test_to_a_abort_primitive(self):
        """ Check converting PDU to a_abort primitive """
        pdu = A_ABORT_RQ()
        pdu.decode(a_abort)

        primitive = pdu.to_primitive()

        assert isinstance(primitive, A_ABORT)
        assert primitive.abort_source == 0

    def test_to_a_p_abort_primitive(self):
        """ Check converting PDU to a_p_abort primitive """
        pdu = A_ABORT_RQ()
        pdu.decode(a_p_abort)

        primitive = pdu.to_primitive()

        assert isinstance(primitive, A_P_ABORT)
        assert primitive.provider_reason == 4

    def test_a_abort_from_primitive(self):
        """ Check converting PDU to primitive """
        orig_pdu = A_ABORT_RQ()
        orig_pdu.decode(a_abort)

        primitive = orig_pdu.to_primitive()

        new_pdu = A_ABORT_RQ()
        new_pdu.from_primitive(primitive)

        assert new_pdu == orig_pdu

    def test_a_p_abort_from_primitive(self):
        """ Check converting PDU to primitive """
        orig_pdu = A_ABORT_RQ()
        orig_pdu.decode(a_p_abort)

        primitive = orig_pdu.to_primitive()

        new_pdu = A_ABORT_RQ()
        new_pdu.from_primitive(primitive)

        assert new_pdu == orig_pdu

    def test_source_str(self):
        """ Check the source str returns correct values """
        pdu = A_ABORT_RQ()
        pdu.decode(a_abort)

        pdu.source = 0
        assert pdu.source_str == 'DUL service-user'

        pdu.source = 2
        assert pdu.source_str == 'DUL service-provider'

    def test_reason_str(self):
        """ Check the reaspm str returns correct values """
        pdu = A_ABORT_RQ()
        pdu.decode(a_abort)

        pdu.source = 2
        pdu.reason_diagnostic = 0
        assert pdu.reason_str == "No reason given"
        pdu.reason_diagnostic = 1
        assert pdu.reason_str == "Unrecognised PDU"
        pdu.reason_diagnostic = 2
        assert pdu.reason_str == "Unexpected PDU"
        pdu.reason_diagnostic = 3
        assert pdu.reason_str == "Reserved"
        pdu.reason_diagnostic = 4
        assert pdu.reason_str == "Unrecognised PDU parameter"
        pdu.reason_diagnostic = 5
        assert pdu.reason_str == "Unexpected PDU parameter"
        pdu.reason_diagnostic = 6
        assert pdu.reason_str == "Invalid PDU parameter value"


class TestEventHandlingAcceptor(object):
    """Test the transport events and handling as acceptor."""
    def setup(self):
        self.ae = None
        _config.LOG_HANDLER_LEVEL = 'none'

    def teardown(self):
        if self.ae:
            self.ae.shutdown()

        _config.LOG_HANDLER_LEVEL = 'standard'

    def test_no_handlers(self):
        """Test with no transport event handlers bound."""
        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)
        assert scp.get_handlers(evt.EVT_PDU_RECV) == []
        assert scp.get_handlers(evt.EVT_PDU_SENT) == []
        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established
        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_PDU_RECV) == []
        assert scp.get_handlers(evt.EVT_PDU_SENT) == []
        assert assoc.get_handlers(evt.EVT_PDU_RECV) == []
        assert assoc.get_handlers(evt.EVT_PDU_SENT) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_PDU_RECV) == []
        assert child.get_handlers(evt.EVT_PDU_SENT) == []

        assoc.release()
        scp.shutdown()

    def test_pdu_sent(self):
        """Test binding to EVT_PDU_SENT."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_PDU_SENT, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)
        assert scp.get_handlers(evt.EVT_PDU_SENT) == [(handle, None)]

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_PDU_SENT) == [(handle, None)]
        assert assoc.get_handlers(evt.EVT_PDU_SENT) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_PDU_SENT) == [(handle, None)]

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 2
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert event.event.name == 'EVT_PDU_SENT'

        assert isinstance(triggered[0].pdu, A_ASSOCIATE_AC)
        assert isinstance(triggered[1].pdu, A_RELEASE_RP)

        scp.shutdown()

    def test_pdu_sent_bind(self):
        """Test binding to EVT_PDU_SENT."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_PDU_SENT, handle)]
        scp = ae.start_server(('', 11112), block=False)
        assert scp.get_handlers(evt.EVT_PDU_SENT) == []

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        scp.bind(evt.EVT_PDU_SENT, handle)

        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_PDU_SENT) == [(handle, None)]
        assert assoc.get_handlers(evt.EVT_PDU_SENT) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_PDU_SENT) == [(handle, None)]

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert event.event.name == 'EVT_PDU_SENT'

        assert isinstance(triggered[0].pdu, A_RELEASE_RP)

        scp.shutdown()

    def test_pdu_sent_unbind(self):
        """Test unbinding EVT_PDU_SENT."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_PDU_SENT, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)
        assert scp.get_handlers(evt.EVT_PDU_SENT) == [(handle, None)]

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_PDU_SENT) == [(handle, None)]
        assert assoc.get_handlers(evt.EVT_PDU_SENT) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_PDU_SENT) == [(handle, None)]

        scp.unbind(evt.EVT_PDU_SENT, handle)

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        assert isinstance(triggered[0].pdu, A_ASSOCIATE_AC)

        scp.shutdown()

    def test_pdu_sent_raises(self, caplog):
        """Test the handler for EVT_PDU_SENT raising exception."""
        def handle(event):
            raise NotImplementedError("Exception description")

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_PDU_SENT, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        with caplog.at_level(logging.ERROR, logger='pynetdicom'):
            assoc = ae.associate('localhost', 11112)
            assert assoc.is_established
            assoc.release()

            while scp.active_associations:
                time.sleep(0.05)

            scp.shutdown()

            msg = (
                "Exception raised in user's 'evt.EVT_PDU_SENT' event handler"
                " 'handle'"
            )
            assert msg in caplog.text
            assert "Exception description" in caplog.text

    def test_pdu_recv(self):
        """Test starting bound to EVT_PDU_RECV."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_PDU_RECV, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)
        assert scp.get_handlers(evt.EVT_PDU_RECV) == [(handle, None)]

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_PDU_RECV) == [(handle, None)]
        assert assoc.get_handlers(evt.EVT_PDU_RECV) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_PDU_RECV) == [(handle, None)]

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 2
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert isinstance(triggered[0].pdu, A_ASSOCIATE_RQ)
        assert isinstance(triggered[1].pdu, A_RELEASE_RQ)
        assert event.event.name == 'EVT_PDU_RECV'

        scp.shutdown()

    def test_pdu_recv_bind(self):
        """Test binding to EVT_PDU_RECV."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)
        assert scp.get_handlers(evt.EVT_PDU_RECV) == []

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1

        scp.bind(evt.EVT_PDU_RECV, handle)

        assert scp.get_handlers(evt.EVT_PDU_RECV) == [(handle, None)]
        assert assoc.get_handlers(evt.EVT_PDU_RECV) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_PDU_RECV) == [(handle, None)]

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert isinstance(triggered[0].pdu, A_RELEASE_RQ)
        assert event.event.name == 'EVT_PDU_RECV'

        scp.shutdown()

    def test_pdu_recv_unbind(self):
        """Test unbinding to EVT_PDU_RECV."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_PDU_RECV, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)
        assert scp.get_handlers(evt.EVT_PDU_RECV) == [(handle, None)]

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        scp.unbind(evt.EVT_PDU_RECV, handle)

        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_PDU_RECV) == []
        assert assoc.get_handlers(evt.EVT_PDU_RECV) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_PDU_RECV) == []

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert isinstance(triggered[0].pdu, A_ASSOCIATE_RQ)
        assert event.event.name == 'EVT_PDU_RECV'

        scp.shutdown()

    def test_pdu_recv_raises(self, caplog):
        """Test the handler for EVT_PDU_RECV raising exception."""
        def handle(event):
            raise NotImplementedError("Exception description")

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_PDU_RECV, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        with caplog.at_level(logging.ERROR, logger='pynetdicom'):
            assoc = ae.associate('localhost', 11112)
            assert assoc.is_established
            assoc.release()

            while scp.active_associations:
                time.sleep(0.05)

            scp.shutdown()

            msg = (
                "Exception raised in user's 'evt.EVT_PDU_RECV' event handler"
                " 'handle'"
            )
            assert msg in caplog.text
            assert "Exception description" in caplog.text


class TestEventHandlingRequestor(object):
    """Test the transport events and handling as requestor."""
    def setup(self):
        self.ae = None
        _config.LOG_HANDLER_LEVEL = 'none'

    def teardown(self):
        if self.ae:
            self.ae.shutdown()

        _config.LOG_HANDLER_LEVEL = 'standard'

    def test_no_handlers(self):
        """Test with no transport event handlers bound."""
        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)
        assert scp.get_handlers(evt.EVT_PDU_RECV) == []
        assert scp.get_handlers(evt.EVT_PDU_SENT) == []
        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established
        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_PDU_RECV) == []
        assert scp.get_handlers(evt.EVT_PDU_SENT) == []
        assert assoc.get_handlers(evt.EVT_PDU_RECV) == []
        assert assoc.get_handlers(evt.EVT_PDU_SENT) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_PDU_RECV) == []
        assert child.get_handlers(evt.EVT_PDU_SENT) == []

        assoc.release()
        scp.shutdown()

    def test_pdu_sent(self):
        """Test binding to EVT_PDU_SENT."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_PDU_SENT, handle)]
        scp = ae.start_server(('', 11112), block=False)
        assert scp.get_handlers(evt.EVT_PDU_SENT) == []

        assoc = ae.associate('localhost', 11112, evt_handlers=handlers)
        assert assoc.is_established
        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_PDU_SENT) == []
        assert assoc.get_handlers(evt.EVT_PDU_SENT) == [(handle, None)]

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_PDU_SENT) == []

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 2
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert event.event.name == 'EVT_PDU_SENT'

        assert isinstance(triggered[0].pdu, A_ASSOCIATE_RQ)
        assert isinstance(triggered[1].pdu, A_RELEASE_RQ)

        scp.shutdown()

    def test_pdu_sent_abort_pdata(self):
        """Test A-ABORT and P-DATA PDUs with EVT_PDU_SENT."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_PDU_SENT, handle)]
        scp = ae.start_server(('', 11112), block=False)

        assoc = ae.associate('localhost', 11112, evt_handlers=handlers)
        assert assoc.is_established

        assoc.send_c_echo()

        assoc.abort()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 3

        assert isinstance(triggered[0].pdu, A_ASSOCIATE_RQ)
        assert isinstance(triggered[1].pdu, P_DATA_TF)
        assert isinstance(triggered[2].pdu, A_ABORT_RQ)

        scp.shutdown()

    def test_pdu_sent_bind(self):
        """Test binding to EVT_PDU_SENT."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_PDU_SENT, handle)]
        scp = ae.start_server(('', 11112), block=False)
        assert scp.get_handlers(evt.EVT_PDU_SENT) == []

        assoc = ae.associate('localhost', 11112)
        assert assoc.get_handlers(evt.EVT_PDU_SENT) == []
        assert assoc.is_established

        assoc.bind(evt.EVT_PDU_SENT, handle)

        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_PDU_SENT) == []
        assert assoc.get_handlers(evt.EVT_PDU_SENT) == [(handle, None)]

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_PDU_SENT) == []

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert event.event.name == 'EVT_PDU_SENT'

        assert isinstance(triggered[0].pdu, A_RELEASE_RQ)

        scp.shutdown()

    def test_pdu_sent_unbind(self):
        """Test unbinding EVT_PDU_SENT."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_PDU_SENT, handle)]
        scp = ae.start_server(('', 11112), block=False)
        assert scp.get_handlers(evt.EVT_PDU_SENT) == []

        assoc = ae.associate('localhost', 11112, evt_handlers=handlers)
        assert assoc.is_established
        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_PDU_SENT) == []
        assert assoc.get_handlers(evt.EVT_PDU_SENT) == [(handle, None)]

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_PDU_SENT) == []

        assoc.unbind(evt.EVT_PDU_SENT, handle)

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        assert isinstance(triggered[0].pdu, A_ASSOCIATE_RQ)

        scp.shutdown()

    def test_pdu_sent_raises(self, caplog):
        """Test the handler for EVT_PDU_SENT raising exception."""
        def handle(event):
            raise NotImplementedError("Exception description")

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_PDU_SENT, handle)]
        scp = ae.start_server(('', 11112), block=False)

        with caplog.at_level(logging.ERROR, logger='pynetdicom'):
            assoc = ae.associate('localhost', 11112, evt_handlers=handlers)
            assert assoc.is_established
            assoc.release()

            while scp.active_associations:
                time.sleep(0.05)

            scp.shutdown()

            msg = (
                "Exception raised in user's 'evt.EVT_PDU_SENT' event handler"
                " 'handle'"
            )
            assert msg in caplog.text
            assert "Exception description" in caplog.text

    def test_pdu_recv(self):
        """Test starting bound to EVT_PDU_RECV."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_PDU_RECV, handle)]
        scp = ae.start_server(('', 11112), block=False)
        assert scp.get_handlers(evt.EVT_PDU_RECV) == []

        assoc = ae.associate('localhost', 11112, evt_handlers=handlers)
        assert assoc.is_established
        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_PDU_RECV) == []
        assert assoc.get_handlers(evt.EVT_PDU_RECV) == [(handle, None)]

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_PDU_RECV) == []

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 2
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert isinstance(triggered[0].pdu, A_ASSOCIATE_AC)
        assert isinstance(triggered[1].pdu, A_RELEASE_RP)
        assert event.event.name == 'EVT_PDU_RECV'

        scp.shutdown()

    def test_pdu_recv_abort_pdata(self):
        """Test A-ABORT and P-DATA PDUs with EVT_PDU_RECV."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_PDU_RECV, handle)]
        scp = ae.start_server(('', 11112), block=False)

        assoc = ae.associate('localhost', 11112, evt_handlers=handlers)
        assert assoc.is_established

        assoc.send_c_echo()

        assoc.abort()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 2

        assert isinstance(triggered[0].pdu, A_ASSOCIATE_AC)
        assert isinstance(triggered[1].pdu, P_DATA_TF)

        scp.shutdown()

    def test_pdu_recv_bind(self):
        """Test binding to EVT_PDU_RECV."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)
        assert scp.get_handlers(evt.EVT_PDU_RECV) == []

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1
        assert assoc.get_handlers(evt.EVT_PDU_RECV) == []

        assoc.bind(evt.EVT_PDU_RECV, handle)

        assert scp.get_handlers(evt.EVT_PDU_RECV) == []
        assert assoc.get_handlers(evt.EVT_PDU_RECV) == [(handle, None)]

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_PDU_RECV) == []

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert isinstance(triggered[0].pdu, A_RELEASE_RP)
        assert event.event.name == 'EVT_PDU_RECV'

        scp.shutdown()

    def test_pdu_recv_unbind(self):
        """Test unbinding to EVT_PDU_RECV."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_PDU_RECV, handle)]
        scp = ae.start_server(('', 11112), block=False)
        assert scp.get_handlers(evt.EVT_PDU_RECV) == []

        assoc = ae.associate('localhost', 11112, evt_handlers=handlers)
        assert assoc.is_established
        assert assoc.get_handlers(evt.EVT_PDU_RECV) == [(handle, None)]

        assoc.unbind(evt.EVT_PDU_RECV, handle)

        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_PDU_RECV) == []
        assert assoc.get_handlers(evt.EVT_PDU_RECV) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_PDU_RECV) == []

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert isinstance(triggered[0].pdu, A_ASSOCIATE_AC)
        assert event.event.name == 'EVT_PDU_RECV'

        scp.shutdown()

    def test_pdu_recv_raises(self, caplog):
        """Test the handler for EVT_PDU_RECV raising exception."""
        def handle(event):
            raise NotImplementedError("Exception description")

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_PDU_RECV, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        with caplog.at_level(logging.ERROR, logger='pynetdicom'):
            assoc = ae.associate('localhost', 11112)
            assert assoc.is_established
            assoc.release()

            while scp.active_associations:
                time.sleep(0.05)

            scp.shutdown()

            msg = (
                "Exception raised in user's 'evt.EVT_PDU_RECV' event handler"
                " 'handle'"
            )
            assert msg in caplog.text
            assert "Exception description" in caplog.text
