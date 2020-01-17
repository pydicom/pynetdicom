#!/usr/bin/env python

import codecs
import logging
import sys

import pytest

from pydicom.uid import UID

from pynetdicom import _config
from pynetdicom.pdu import (
    A_ASSOCIATE_RQ, A_ASSOCIATE_AC, P_DATA_TF
)
from pynetdicom.pdu_items import (
    MaximumLengthSubItem,
    ImplementationClassUIDSubItem, ImplementationVersionNameSubItem,
    AsynchronousOperationsWindowSubItem,
    SOPClassExtendedNegotiationSubItem,
    SOPClassCommonExtendedNegotiationSubItem, UserIdentitySubItemRQ,
    UserIdentitySubItemAC, ApplicationContextItem, PresentationContextItemAC,
    PresentationContextItemRQ, UserInformationItem, TransferSyntaxSubItem,
    PresentationDataValueItem, AbstractSyntaxSubItem,
    SCP_SCU_RoleSelectionSubItem,
    PDUItem,
    PACK_UCHAR, UNPACK_UCHAR
)
from pynetdicom.pdu_primitives import (
    SOPClassExtendedNegotiation, SOPClassCommonExtendedNegotiation,
    MaximumLengthNotification, ImplementationClassUIDNotification,
    ImplementationVersionNameNotification, SCP_SCU_RoleSelectionNegotiation,
    AsynchronousOperationsWindowNegotiation, UserIdentityNegotiation
)
from pynetdicom.presentation import PresentationContext
from pynetdicom.utils import pretty_bytes
from .encoded_pdu_items import (
    a_associate_rq, a_associate_ac, a_associate_rq_user_async,
    asynchronous_window_ops, a_associate_rq_role, user_identity_rq_user_nopw,
    user_identity_ac, a_associate_rq_user_id_user_pass,
    a_associate_rq_user_id_ext_neg, a_associate_ac_user,
    a_associate_rq_com_ext_neg, user_identity_rq_user_pass, a_associate_rj,
    a_release_rq, a_release_rp, a_abort, a_p_abort, application_context,
    presentation_context_rq, presentation_context_ac, abstract_syntax,
    transfer_syntax, presentation_data, presentation_data_value,
    maximum_length_received, implementation_class_uid,
    implementation_version_name, role_selection, role_selection_odd,
    user_information, extended_negotiation, common_extended_negotiation,
    p_data_tf, a_associate_ac_zero_ts
)

LOGGER = logging.getLogger('pynetdicom')
LOGGER.setLevel(logging.CRITICAL)


def print_nice_bytes(bytestream):
    """Nice output for bytestream."""
    str_list = pretty_bytes(bytestream, prefix="b'\\x", delimiter='\\x',
                        items_per_line=10)
    for string in str_list:
        print(string)

def bytes_to_bytesio(bytestream):
    """Convert a bytestring to a BytesIO ready to be decoded."""
    from io import BytesIO
    fp = BytesIO()
    fp.write(bytestream)
    fp.seek(0)
    return fp

def create_encoded_pdu():
    """Function to create a PDU for testing"""
    pdu = A_ASSOCIATE_AC()
    pdu.decode(a_associate_ac)
    ui = pdu.user_information
    data = ui.user_data

    usr_id = UserIdentitySubItemAC()
    usr_id.server_response = b'Accepted'
    usr_id.server_response_length = 8
    usr_id.get_length()
    data.append(usr_id)
    print_nice_bytes(pdu.encode())


class TestPDU(object):
    """Test the PDU equality/inequality operators."""
    def test_decode_raises(self):
        """Test the PDU.decode method raises NotImplementedError."""
        item = PDUItem()
        with pytest.raises(NotImplementedError):
            item.decode(abstract_syntax)

    def test_decoders_raises(self):
        """Test the PDU._decoders property raises NotImplementedError."""
        item = PDUItem()
        with pytest.raises(NotImplementedError):
            item._decoders

    def test_equality(self):
        """Test the equality operator"""
        aa = ApplicationContextItem()
        bb = ApplicationContextItem()
        assert aa == bb
        assert not aa == 'TEST'

        aa.application_context_name = UID('1.2.3')
        assert not aa == bb

        bb.application_context_name = UID('1.2.3')
        assert aa == bb

        assert aa == aa

    def test_encode_raises(self):
        """Test the PDU.encode method raises NotImplementedError."""
        item = PDUItem()
        with pytest.raises(NotImplementedError):
            item.encode()

    def test_encoders_raises(self):
        """Test the PDU._encoders property raises NotImplementedError."""
        item = PDUItem()
        with pytest.raises(NotImplementedError):
            item._encoders

    def test_generate_items(self):
        """Test the PDU._generate_items method."""
        item = PDUItem()
        gen = item._generate_items(b'')
        with pytest.raises(StopIteration):
            next(gen)

        data = b'\x10\x00\x00\x02\x01\x02'
        gen = item._generate_items(data)
        assert next(gen) == (0x10, data)
        with pytest.raises(StopIteration):
            next(gen)

        data += b'\x20\x00\x00\x03\x01\x02\x03'
        gen = item._generate_items(data)
        assert next(gen) == (0x10, b'\x10\x00\x00\x02\x01\x02')
        assert next(gen) == (0x20, b'\x20\x00\x00\x03\x01\x02\x03')
        with pytest.raises(StopIteration):
            next(gen)

    def test_generate_items_raises(self):
        """Test failure modes of PDU._generate_items method."""
        item = PDUItem()

        # Short data
        data = b'\x10\x00\x00\x02\x01'
        gen = item._generate_items(data)
        with pytest.raises(AssertionError):
            next(gen)

    def test_hash_raises(self):
        """Test hash(PDU) raises exception."""
        item = PDUItem()
        with pytest.raises(TypeError):
            hash(item)

    def test_inequality(self):
        """Test the inequality operator"""
        aa = ApplicationContextItem()
        bb = ApplicationContextItem()
        assert not aa != bb
        assert aa != 'TEST'

        aa.application_context_name = UID('1.2.3')
        assert aa != bb

        assert not aa != aa

    def test_item_length_raises(self):
        """Test PDU.pdu_length raises NotImplementedError."""
        item = PDUItem()
        with pytest.raises(NotImplementedError):
            item.item_length

    def test_item_type_raises(self):
        """Test PDUItem.item_type raises ValueError."""
        item = PDUItem()
        with pytest.raises(KeyError):
            item.item_type

    def test_wrap_bytes(self):
        """Test PDU._wrap_bytes()."""
        item = PDUItem()
        assert item._wrap_bytes(b'') == b''
        assert item._wrap_bytes(b'\x00\x01') == b'\x00\x01'

    def test_wrap_encode_items(self):
        """Test PDU._wrap_encode_items()."""
        context_a = ApplicationContextItem()
        context_b = ApplicationContextItem()
        item = PDUItem()
        out = item._wrap_encode_items([context_a])
        assert out == (
            b"\x10\x00\x00\x15\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31" +
            b"\x30\x30\x30\x38\x2e\x33\x2e\x31\x2e\x31\x2e\x31"
        )

        out = item._wrap_encode_items([context_a, context_b])
        assert out == (
            (b"\x10\x00\x00\x15\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31" +
             b"\x30\x30\x30\x38\x2e\x33\x2e\x31\x2e\x31\x2e\x31") * 2
        )

    def test_wrap_generate_items(self):
        """Test PDU._wrap_generate_items()."""
        item = PDUItem()
        out = item._wrap_generate_items(b'')
        assert out == []

        data = b'\x10\x00\x00\x03\x31\x2e\x32'
        out = item._wrap_generate_items(data)
        assert out[0].application_context_name == '1.2'

        data += b'\x10\x00\x00\x04\x31\x2e\x32\x33'
        out = item._wrap_generate_items(data)
        assert out[0].application_context_name == '1.2'
        assert out[1].application_context_name == '1.23'

    def test_wrap_pack(self):
        """Test PDU._wrap_pack()."""
        item = PDUItem()
        out = item._wrap_pack(1, PACK_UCHAR)
        assert out == b'\x01'

    def test_wrap_uid_bytes(self):
        """Tets PDU._wrap_uid_bytes()."""
        item = PDUItem()
        assert b'1.2.3' == item._wrap_uid_bytes(b'1.2.3')
        assert b'1.2.31' == item._wrap_uid_bytes(b'1.2.31')
        # Removes trailing padding
        assert b'1.2.3' == item._wrap_uid_bytes(b'1.2.3\x00')
        # But only last padding byte
        assert b'1.2.3\x00' == item._wrap_uid_bytes(b'1.2.3\x00\x00')
        assert b'\x001.2.3' == item._wrap_uid_bytes(b'\x001.2.3')

    def test_wrap_unpack(self):
        """Test PDU._wrap_unpack()."""
        item = PDUItem()
        out = item._wrap_unpack(b'\x01', UNPACK_UCHAR)
        assert out == 1

    def test_wrap_encode_uid(self):
        """Test PDU._wrap_encode_uid()."""
        item = PDUItem()
        # Odd length
        uid = UID('1.2.840.10008.1.1')
        assert len(uid) % 2 > 0
        out = item._wrap_encode_uid(uid)
        assert out == b'1.2.840.10008.1.1'

        # Even length
        uid = UID('1.2.840.10008.1.10')
        assert len(uid) % 2 == 0
        out = item._wrap_encode_uid(uid)
        assert out == b'1.2.840.10008.1.10'


class TestApplicationContext(object):
    def setup(self):
        self.default_conformance = _config.ENFORCE_UID_CONFORMANCE

    def teardown(self):
        _config.ENFORCE_UID_CONFORMANCE = self.default_conformance

    def test_init(self):
        """Test a new ApplicationContextItem"""
        item = ApplicationContextItem()
        assert item.item_type == 0x10
        assert item.item_length == 21
        assert len(item) == 25
        assert item.application_context_name == UID('1.2.840.10008.3.1.1.1')

    def test_uid_conformance(self):
        """Test the UID conformance with ENFORCE_UID_CONFORMANCE."""
        _config.ENFORCE_UID_CONFORMANCE = False

        item = ApplicationContextItem()
        item.application_context_name = 'abc'
        assert item.application_context_name == 'abc'

        msg = r"Invalid 'Application Context Name'"
        with pytest.raises(ValueError, match=msg):
            item.application_context_name = 'abc' * 22

        _config.ENFORCE_UID_CONFORMANCE = True
        with pytest.raises(ValueError, match=msg):
            item.application_context_name = 'abc'

    def test_string_output(self):
        """Test the string output"""
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)
        for item in pdu.variable_items:
            if isinstance(item, ApplicationContextItem):
                assert '1.2.840.10008.3.1.1.1' in item.__str__()

    def test_rq_decode(self):
        """Check decoding an assoc_rq produces the correct application context """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)

        item = pdu.variable_items[0]

        assert item.item_type == 0x10
        assert item.item_length == 21
        assert len(item) == 25
        assert item.application_context_name == '1.2.840.10008.3.1.1.1'
        assert isinstance(item.application_context_name, UID)

    def test_ac_decode(self):
        """Check decoding an assoc_ac produces the correct application context """
        pdu = A_ASSOCIATE_AC()
        pdu.decode(a_associate_ac)

        item = pdu.variable_items[0]

        assert item.item_type == 0x10
        assert item.item_length == 21
        assert len(item) == 25
        assert item.application_context_name == '1.2.840.10008.3.1.1.1'
        assert isinstance(item.application_context_name, UID)

    def test_encode_cycle(self):
        """Check encoding produces the correct output"""
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)

        for item in pdu.variable_items:
            if isinstance(item, ApplicationContextItem):
                s = item.encode()

        assert s == application_context

    def test_update(self):
        """Test that changing the item's parameters correctly updates the length """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)

        for item in pdu.variable_items:
            if isinstance(item, ApplicationContextItem):
                assert len(item) == 25
                item.application_context_name = '1.2.840'
                assert item.item_length == 7
                assert len(item) == 11

    def test_properties(self):
        """Test the item's property setters and getters """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)

        for item in pdu.variable_items:
            if isinstance(item, ApplicationContextItem):
                break

        uid = '1.2.840.10008.3.1.1.1'
        for s in [codecs.encode(uid, 'ascii'), uid, UID(uid)]:
            item.application_context_name = s
            assert item.application_context_name == UID(uid)
            assert isinstance(item.application_context_name, UID)

        # Test bad value
        with pytest.raises(TypeError):
            item.application_context_name = 2

    def test_encode_odd(self):
        """Test encoding odd-length context name"""
        item = ApplicationContextItem()
        item.application_context_name = '1.2.3'
        assert len(item.application_context_name) % 2 > 0
        assert item.item_length == 5
        assert len(item) == 9
        enc = item.encode()
        assert enc == b'\x10\x00\x00\x05\x31\x2e\x32\x2e\x33'

    def test_encode_even(self):
        """Test encoding even-length context name"""
        item = ApplicationContextItem()
        item.application_context_name = '1.2.31'
        assert len(item.application_context_name) % 2 == 0
        assert item.item_length == 6
        assert len(item) == 10
        enc = item.encode()
        assert enc == b'\x10\x00\x00\x06\x31\x2e\x32\x2e\x33\x31'

    def test_decode_odd(self):
        """Test decoding odd-length context name"""
        bytestream = b'\x10\x00\x00\x05\x31\x2e\x32\x2e\x33'
        item = ApplicationContextItem()
        item.decode(bytestream)
        assert item.item_length == 5
        assert item.application_context_name == '1.2.3'
        assert len(item.application_context_name) % 2 > 0
        assert len(item) == 9
        assert item.encode() == bytestream

    def test_decode_even(self):
        """Test decoding even-length context name"""
        bytestream = b'\x10\x00\x00\x06\x31\x2e\x32\x2e\x33\x31'
        item = ApplicationContextItem()
        item.decode(bytestream)
        assert item.item_length == 6
        assert item.application_context_name == '1.2.31'
        assert len(item.application_context_name) % 2 == 0
        assert len(item) == 10
        assert item.encode() == bytestream

    def test_decode_padded_odd(self):
        """Test decoding a padded odd-length context name"""
        # Non-conformant but handle anyway
        bytestream = b'\x10\x00\x00\x06\x31\x2e\x32\x2e\x33\x00'
        item = ApplicationContextItem()
        item.decode(bytestream)
        assert item.item_length == 5
        assert item.application_context_name == '1.2.3'
        assert len(item.application_context_name) % 2 > 0
        assert len(item) == 9
        assert item.encode() == b'\x10\x00\x00\x05\x31\x2e\x32\x2e\x33'


class TestPresentationContextRQ(object):
    def test_init(self):
        """Test a new PresentationContextRQ Item."""
        item = PresentationContextItemRQ()
        assert item.item_type == 0x20
        assert item.item_length == 4
        assert len(item) == 8
        assert item.presentation_context_id is None
        assert item.abstract_transfer_syntax_sub_items == []

        assert item.abstract_syntax is None
        assert item.context_id is None
        assert item.transfer_syntax == []

    def test_string_output(self):
        """Test the string output"""
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_role)
        pdu.presentation_context
        for item in pdu.variable_items:
            if isinstance(item, PresentationContextItemRQ):
                assert 'CT Image Storage' in item.__str__()
                assert 'Explicit VR Little Endian' in item.__str__()

    def test_decode(self):
        """Check decoding produces the correct presentation context """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)
        item = pdu.variable_items[1]

        assert item.item_type == 0x20
        assert item.item_length == 46
        assert len(item) == 50
        assert item.presentation_context_id == 1
        assert isinstance(item.abstract_transfer_syntax_sub_items, list)
        assert item.abstract_syntax == UID('1.2.840.10008.1.1')
        assert len(item.transfer_syntax) == 1
        assert item.transfer_syntax[0] == UID('1.2.840.10008.1.2')

    def test_encode(self):
        """Check encoding produces the correct output """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)

        for item in pdu.variable_items:
            if isinstance(item, PresentationContextItemRQ):
                s = item.encode()

        assert s == presentation_context_rq

    def test_to_primitive(self):
        """Check converting to primitive """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)

        for item in pdu.variable_items:
            if isinstance(item, PresentationContextItemRQ):
                result = item.to_primitive()

        context = PresentationContext()
        context.context_id = 1
        context.abstract_syntax = '1.2.840.10008.1.1'
        context.add_transfer_syntax('1.2.840.10008.1.2')
        assert result == context

    def test_from_primitive(self):
        """Check converting from primitive """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)

        for ii in pdu.variable_items:
            if isinstance(ii, PresentationContextItemRQ):
                orig_item = ii
                break

        context = PresentationContext()
        context.context_id = 1
        context.abstract_syntax = '1.2.840.10008.1.1'
        context.add_transfer_syntax('1.2.840.10008.1.2')

        new_item = PresentationContextItemRQ()
        new_item.from_primitive(context)
        assert orig_item == new_item


class TestPresentationContextAC(object):
    def test_init(self):
        """Test a new PresentationContextAC Item."""
        item = PresentationContextItemAC()
        assert item.item_type == 0x21
        assert item.item_length == 4
        assert len(item) == 8
        assert item.presentation_context_id is None
        assert item.result_reason is None
        assert item.transfer_syntax_sub_item == []

        assert item.context_id is None
        assert item.transfer_syntax is None
        assert item.result is None

        with pytest.raises(KeyError):
            item.result_str

    def test_string_output(self):
        """Test the string output"""
        pdu = A_ASSOCIATE_AC()
        pdu.decode(a_associate_ac)
        for item in pdu.variable_items:
            if isinstance(item, PresentationContextItemAC):
                assert 'Accepted' in item.__str__()
                assert 'Implicit VR Little Endian' in item.__str__()

    def test_decode(self):
        """Check decoding produces the correct presentation context """
        pdu = A_ASSOCIATE_AC()
        pdu.decode(a_associate_ac)

        item = pdu.variable_items[1]

        assert item.item_type == 0x21
        assert item.item_length == 25
        assert len(item) == 29
        assert item.presentation_context_id == 1
        assert item.result_reason == 0
        assert item.result == item.result_reason
        assert item.result_str == 'Accepted'
        assert isinstance(item.transfer_syntax_sub_item[0],
                          TransferSyntaxSubItem)
        assert item.transfer_syntax == UID('1.2.840.10008.1.2')

    def test_encode(self):
        """Check encoding produces the correct output """
        pdu = A_ASSOCIATE_AC()
        pdu.decode(a_associate_ac)

        for item in pdu.variable_items:
            if isinstance(item, PresentationContextItemAC):
                s = item.encode()

        assert s == presentation_context_ac

    def test_to_primitive(self):
        """Check converting to primitive """
        pdu = A_ASSOCIATE_AC()
        pdu.decode(a_associate_ac)

        for item in pdu.variable_items:
            if isinstance(item, PresentationContextItemAC):
                result = item.to_primitive()

        context = PresentationContext()
        context.context_id = 1
        context.add_transfer_syntax('1.2.840.10008.1.2')
        context.result = 0
        assert result == context

    def test_from_primitive(self):
        """Check converting from primitive """
        pdu = A_ASSOCIATE_AC()
        pdu.decode(a_associate_ac)

        for ii in pdu.variable_items:
            if isinstance(ii, PresentationContextItemAC):
                orig_item = ii
                break

        context = PresentationContext()
        context.context_id = 1
        context.add_transfer_syntax('1.2.840.10008.1.2')
        context.result = 0

        new_item = PresentationContextItemAC()
        new_item.from_primitive(context)

        assert orig_item == new_item

    def test_result_str(self):
        item = PresentationContextItemAC()
        _result = {
            0 : 'Accepted',
            1 : 'User Rejection',
            2 : 'Provider Rejection',
            3 : 'Rejected - Abstract Syntax Not Supported',
            4 : 'Rejected - Transfer Syntax Not Supported'
        }

        for result in [0, 1, 2, 3, 4]:
            item.result_reason = result
            assert item.result_str == _result[result]

    def test_decode_empty(self):
        """Regression test for #342 (decoding an empty Transfer Syntax Item."""
        # When result is not accepted, transfer syntax value must not be tested
        item = PresentationContextItemAC()
        item.decode(
            b'\x21\x00\x00\x08\x01\x00\x01\x00'
            b'\x40\x00\x00\x00'
        )

        assert item.item_type == 0x21
        assert item.item_length == 8
        assert item.result == 1
        assert len(item) == 12
        assert item.transfer_syntax is None

        # Confirm we can still convert the PDU into a PresentationContext
        primitive = item.to_primitive()
        assert primitive.context_id == 1
        assert primitive.transfer_syntax == []
        assert primitive.result == 1

        assert "Item length: 8 bytes" in item.__str__()

        item = item.transfer_syntax_sub_item[0]
        assert item.item_length == 0
        assert item._skip_validation is True
        assert item.transfer_syntax_name is None


class TestAbstractSyntax(object):
    def setup(self):
        self.default_conformance = _config.ENFORCE_UID_CONFORMANCE

    def teardown(self):
        _config.ENFORCE_UID_CONFORMANCE = self.default_conformance

    def test_init(self):
        """Test a new AbstractSyntaxSubItem."""
        item = AbstractSyntaxSubItem()
        assert item.item_type == 0x30
        assert item.item_length == 0
        assert len(item) == 4
        assert item.abstract_syntax_name is None
        assert item.abstract_syntax is None

    def test_uid_conformance(self):
        """Test the UID conformance with ENFORCE_UID_CONFORMANCE."""
        _config.ENFORCE_UID_CONFORMANCE = False

        item = AbstractSyntaxSubItem()
        item.abstract_syntax_name = 'abc'
        assert item.abstract_syntax_name == 'abc'

        msg = r"Abstract Syntax Name is an invalid UID"
        with pytest.raises(ValueError, match=msg):
            item.abstract_syntax_name = 'abc' * 22

        _config.ENFORCE_UID_CONFORMANCE = True
        with pytest.raises(ValueError, match=msg):
            item.abstract_syntax_name = 'abc'

    def test_string_output(self):
        """Test the string output"""
        item = AbstractSyntaxSubItem()
        item.abstract_syntax_name = '1.2.840.10008.1.1'
        assert '17 bytes' in item.__str__()
        assert 'Verification SOP Class' in item.__str__()

    def test_decode(self):
        """Check decoding produces the correct presentation context """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)

        contexts = pdu.presentation_context
        item = contexts[0].abstract_transfer_syntax_sub_items[0]

        assert item.item_type == 0x30
        assert item.item_length == 17
        assert len(item) == 21
        assert item.abstract_syntax_name == UID('1.2.840.10008.1.1')
        assert item.abstract_syntax == UID('1.2.840.10008.1.1')

    def test_encode_cycle(self):
        """Check encoding produces the correct output """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)

        contexts = pdu.presentation_context
        ab_syntax = contexts[0].abstract_transfer_syntax_sub_items[0]

        assert ab_syntax.encode() == abstract_syntax

    def test_properies(self):
        """Check property setters and getters """
        item = AbstractSyntaxSubItem()
        item.abstract_syntax_name = '1.2.840.10008.1.1'

        assert item.abstract_syntax == UID('1.2.840.10008.1.1')

        item.abstract_syntax_name = b'1.2.840.10008.1.1'
        assert item.abstract_syntax == UID('1.2.840.10008.1.1')

        item.abstract_syntax_name = UID('1.2.840.10008.1.1')
        assert item.abstract_syntax == UID('1.2.840.10008.1.1')

        with pytest.raises(TypeError):
            item.abstract_syntax_name = 10002

    def test_encode_odd(self):
        """Test encoding odd-length abstract syntax"""
        item = AbstractSyntaxSubItem()
        item.abstract_syntax_name = '1.2.3'
        assert len(item.abstract_syntax_name) % 2 > 0
        assert item.item_length == 5
        assert len(item) == 9
        enc = item.encode()
        assert enc == b'\x30\x00\x00\x05\x31\x2e\x32\x2e\x33'

    def test_encode_even(self):
        """Test encoding even-length abstract syntax"""
        item = AbstractSyntaxSubItem()
        item.abstract_syntax_name = '1.2.31'
        assert len(item.abstract_syntax_name) % 2 == 0
        assert item.item_length == 6
        assert len(item) == 10
        enc = item.encode()
        assert enc == b'\x30\x00\x00\x06\x31\x2e\x32\x2e\x33\x31'

    def test_decode_odd(self):
        """Test decoding odd-length abstract syntax"""
        bytestream = b'\x30\x00\x00\x05\x31\x2e\x32\x2e\x33'
        item = AbstractSyntaxSubItem()
        item.decode(bytestream)
        assert item.item_length == 5
        assert item.abstract_syntax_name == '1.2.3'
        assert len(item.abstract_syntax_name) % 2 > 0
        assert len(item) == 9
        assert item.encode() == bytestream

    def test_decode_even(self):
        """Test decoding even-length abstract syntax"""
        bytestream = b'\x30\x00\x00\x06\x31\x2e\x32\x2e\x33\x31'
        item = AbstractSyntaxSubItem()
        item.decode(bytestream)
        assert item.item_length == 6
        assert item.abstract_syntax_name == '1.2.31'
        assert len(item.abstract_syntax_name) % 2 == 0
        assert len(item) == 10
        assert item.encode() == bytestream

    def test_decode_padded_odd(self):
        """Test decoding a padded odd-length abstract syntax"""
        # Non-conformant but handle anyway
        bytestream = b'\x30\x00\x00\x06\x31\x2e\x32\x2e\x33\x00'
        item = AbstractSyntaxSubItem()
        item.decode(bytestream)
        assert item.item_length == 5
        assert item.abstract_syntax_name == '1.2.3'
        assert len(item.abstract_syntax_name) % 2 > 0
        assert len(item) == 9
        assert item.encode() == b'\x30\x00\x00\x05\x31\x2e\x32\x2e\x33'


class TestTransferSyntax(object):
    def setup(self):
        self.default_conformance = _config.ENFORCE_UID_CONFORMANCE

    def teardown(self):
        _config.ENFORCE_UID_CONFORMANCE = self.default_conformance

    def test_init(self):
        """Test a new AbstractSyntaxSubItem."""
        item = TransferSyntaxSubItem()
        assert item.item_type == 0x40
        assert item.item_length == 0
        assert len(item) == 4
        assert item.transfer_syntax_name is None
        assert item.transfer_syntax is None

    def test_uid_conformance(self):
        """Test the UID conformance with ENFORCE_UID_CONFORMANCE."""
        _config.ENFORCE_UID_CONFORMANCE = False

        item = TransferSyntaxSubItem()
        item.transfer_syntax_name = 'abc'
        assert item.transfer_syntax_name == 'abc'

        msg = r"Transfer Syntax Name is an invalid UID"
        with pytest.raises(ValueError, match=msg):
            item.transfer_syntax_name = 'abc' * 22

        _config.ENFORCE_UID_CONFORMANCE = True
        with pytest.raises(ValueError, match=msg):
            item.transfer_syntax_name = 'abc'

    def test_string_output(self):
        """Test the string output"""
        item = TransferSyntaxSubItem()
        item.transfer_syntax_name = '1.2.840.10008.1.2'
        assert '17 bytes' in item.__str__()
        assert 'Implicit VR Little Endian' in item.__str__()

    def test_decode(self):
        """Check decoding produces the correct presentation context """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)

        contexts = pdu.presentation_context
        item = contexts[0].abstract_transfer_syntax_sub_items[1]

        assert item.item_type == 0x40
        assert item.item_length == 17
        assert len(item) == 21
        assert item.transfer_syntax_name == UID('1.2.840.10008.1.2')
        assert item.transfer_syntax == UID('1.2.840.10008.1.2')

    def test_encode_cycle(self):
        """Check encoding produces the correct output """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)

        contexts = pdu.presentation_context
        tran_syntax = contexts[0].abstract_transfer_syntax_sub_items[1]

        assert tran_syntax.encode() == transfer_syntax

    def test_properies(self):
        """Check property setters and getters """
        tran_syntax = TransferSyntaxSubItem()
        tran_syntax.transfer_syntax_name = '1.2.840.10008.1.2'

        assert tran_syntax.transfer_syntax == UID('1.2.840.10008.1.2')

        tran_syntax.transfer_syntax_name = b'1.2.840.10008.1.2'
        assert tran_syntax.transfer_syntax == UID('1.2.840.10008.1.2')

        tran_syntax.transfer_syntax_name = UID('1.2.840.10008.1.2')
        assert tran_syntax.transfer_syntax == UID('1.2.840.10008.1.2')

        with pytest.raises(TypeError):
            tran_syntax.transfer_syntax_name = 10002

    def test_encode_odd(self):
        """Test encoding odd-length transfer syntax"""
        item = TransferSyntaxSubItem()
        item.transfer_syntax_name = '1.2.3'
        assert len(item.transfer_syntax_name) % 2 > 0
        assert item.item_length == 5
        assert len(item) == 9
        enc = item.encode()
        assert enc == b'\x40\x00\x00\x05\x31\x2e\x32\x2e\x33'

    def test_encode_even(self):
        """Test encoding even-length transfer syntax"""
        item = TransferSyntaxSubItem()
        item.transfer_syntax_name = '1.2.31'
        assert len(item.transfer_syntax_name) % 2 == 0
        assert item.item_length == 6
        assert len(item) == 10
        enc = item.encode()
        assert enc == b'\x40\x00\x00\x06\x31\x2e\x32\x2e\x33\x31'

    def test_decode_odd(self):
        """Test decoding odd-length transfer syntax"""
        bytestream = b'\x40\x00\x00\x05\x31\x2e\x32\x2e\x33'
        item = TransferSyntaxSubItem()
        item.decode(bytestream)
        assert item.item_length == 5
        assert item.transfer_syntax_name == '1.2.3'
        assert len(item.transfer_syntax_name) % 2 > 0
        assert len(item) == 9
        assert item.encode() == bytestream

    def test_decode_even(self):
        """Test decoding even-length transfer syntax"""
        bytestream = b'\x40\x00\x00\x06\x31\x2e\x32\x2e\x33\x31'
        item = TransferSyntaxSubItem()
        item.decode(bytestream)
        assert item.item_length == 6
        assert item.transfer_syntax_name == '1.2.31'
        assert len(item.transfer_syntax_name) % 2 == 0
        assert len(item) == 10
        assert item.encode() == bytestream

    def test_decode_padded_odd(self):
        """Test decoding a padded odd-length transfer syntax"""
        # Non-conformant but handle anyway
        bytestream = b'\x40\x00\x00\x06\x31\x2e\x32\x2e\x33\x00'
        item = TransferSyntaxSubItem()
        item.decode(bytestream)
        assert item.item_length == 5
        assert item.transfer_syntax_name == '1.2.3'
        assert len(item.transfer_syntax_name) % 2 > 0
        assert len(item) == 9
        assert item.encode() == b'\x40\x00\x00\x05\x31\x2e\x32\x2e\x33'

    def test_decode_empty(self):
        """Regression test for #342 (decoding an empty Transfer Syntax Item."""
        pdu = A_ASSOCIATE_AC()
        pdu.decode(a_associate_ac_zero_ts)

        item = pdu.presentation_context[0]
        assert item.item_type == 0x21
        assert item.item_length == 27
        assert item.result == 0
        assert len(item) == 31
        assert item.transfer_syntax == UID('1.2.840.10008.1.2.1')

        item = pdu.presentation_context[1]
        assert item.item_type == 0x21
        assert item.item_length == 8
        assert item.result == 3
        assert len(item) == 12
        assert item.transfer_syntax is None

        item = TransferSyntaxSubItem()
        item._skip_validation = True
        item.decode(b'\x40\x00\x00\x00')
        assert item.item_type == 0x40
        assert item.item_length == 0
        assert len(item) == 4
        assert item.transfer_syntax is None
        assert 'Item length: 0 bytes' in item.__str__()
        assert 'Transfer syntax name' not in item.__str__()


class TestPresentationDataValue(object):
    def test_init(self):
        """Test a new PresentationDataValueItem"""
        item = PresentationDataValueItem()
        assert item.item_length == 1
        assert len(item) == 5
        assert item.presentation_context_id is None
        assert item.presentation_data_value is None

        with pytest.raises(ValueError):
            item.message_control_header_byte

        with pytest.raises(NotImplementedError):
            item.item_type

    def test_string_output(self):
        """Test the string output"""
        pdu = P_DATA_TF()
        pdu.decode(p_data_tf)
        pdvs = pdu.presentation_data_value_items
        item = pdvs[0]
        assert '80 bytes' in item.__str__()
        assert '0x03 0x00' in item.__str__()

    def test_decode(self):
        """Check decoding produces the correct presentation data value """
        item = PresentationDataValueItem()
        item.decode(presentation_data_value)

        assert item.item_length == 80
        assert len(item) == 84
        assert item.presentation_data_value == presentation_data
        assert item.message_control_header_byte == "00000011"

    def test_encode(self):
        """Check encoding produces the correct output """
        pdu = P_DATA_TF()
        pdu.decode(p_data_tf)
        pdvs = pdu.presentation_data_value_items

        assert pdvs[0].encode() == presentation_data_value

    def test_properies(self):
        """Check property setters and getters """
        pdu = P_DATA_TF()
        pdu.decode(p_data_tf)

        pdvs = pdu.presentation_data_value_items

        pdv = pdvs[0]

        assert pdv.context_id == 1
        assert pdv.data == presentation_data
        assert pdv.message_control_header_byte == '00000011'

    def test_message_control_header_byte(self):
        item = PresentationDataValueItem()
        ref = {
            b'\x00' : '00000000',
            b'\x01' : '00000001',
            b'\x02' : '00000010',
            b'\x03' : '00000011',
        }
        for value in [b'\x00\x99', b'\x01\x99', b'\x02\x99', b'\x03\x99']:
            item.presentation_data_value = value
            assert item.message_control_header_byte == ref[value[0:1]]


class TestUserInformation(object):
    def test_init(self):
        """Test a new UserInformationItem."""
        item = UserInformationItem()
        assert item.item_type == 0x50
        assert item.item_length == 0
        assert len(item) == 4
        assert item.user_data == []

        assert item.async_ops_window is None
        assert item.common_ext_neg == []
        assert item.ext_neg == []
        assert item.implementation_class_uid is None
        assert item.implementation_version_name is None
        assert item.role_selection == {}
        assert item.user_identity is None

    def test_string_output(self):
        """Test the string output"""
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_role)
        item = pdu.user_information
        assert 'Implementation Class UID Sub-item' in item.__str__()
        assert 'Implementation Version Name Sub-item' in item.__str__()
        assert 'SCP/SCU Role Selection Sub-item' in item.__str__()

    def test_decode(self):
        """Check decoding produces the correct values """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_role)
        item = pdu.user_information

        assert item.item_type == 0x50
        assert item.item_length == 95
        assert len(item) == 99
        assert len(item.user_data) == 4

    def test_encode(self):
        """Check encoding produces the correct output """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)
        user_info = pdu.user_information

        assert user_info.encode(), user_information

    def test_to_primitive(self):
        """Check converting to primitive """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)

        ui = pdu.user_information

        result = ui.to_primitive()

        check = []
        max_pdu = MaximumLengthNotification()
        max_pdu.maximum_length_received = 16382
        check.append(max_pdu)
        class_uid = ImplementationClassUIDNotification()
        class_uid.implementation_class_uid = UID(
            '1.2.826.0.1.3680043.9.3811.0.9.0'
        )
        check.append(class_uid)
        v_name = ImplementationVersionNameNotification()
        v_name.implementation_version_name = b'PYNETDICOM_090'
        check.append(v_name)

        assert result == check

    def test_from_primitive(self):
        """Check converting from primitive """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_user_async)

        orig = pdu.user_information
        params = orig.to_primitive()

        new = UserInformationItem()
        new.from_primitive(params)

        assert orig == new

    def test_properties_usr_id(self):
        """Check user id properties are OK """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_user_async)
        ui = pdu.user_information
        assert isinstance(ui.user_identity, UserIdentitySubItemRQ)

        pdu = A_ASSOCIATE_AC()
        pdu.decode(a_associate_ac)
        ui = pdu.user_information
        ui.user_data.append(UserIdentitySubItemAC())
        assert isinstance(ui.user_identity, UserIdentitySubItemAC)

    def test_properties_ext_neg(self):
        """Check extended neg properties are OK """
        '''
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_user_async)

        ui = pdu.user_information

        self.assertTrue(isinstance(ui.user_identity, UserIdentitySubItemRQ))
        '''
        pass

    def test_properties_role(self):
        """Check user id properties are OK """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_role)

        ui = pdu.user_information

        for uid in ui.role_selection:
            assert isinstance(ui.role_selection[uid],
                              SCP_SCU_RoleSelectionSubItem)

    def test_properties_async(self):
        """Check async window ops properties are OK """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_user_async)

        ui = pdu.user_information

        assert isinstance(ui.async_ops_window,
                          AsynchronousOperationsWindowSubItem)

    def test_properties_max_pdu(self):
        """Check max receive properties are OK """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_role)

        ui = pdu.user_information

        assert ui.maximum_length == 16382

        for item in ui.user_data:
            if isinstance(item, MaximumLengthSubItem):
                ui.user_data.remove(item)
        assert ui.maximum_length is None

    def test_properties_implementation(self):
        """Check async window ops properties are OK """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_role)
        ui = pdu.user_information

        assert ui.implementation_class_uid == UID(
            '1.2.826.0.1.3680043.9.3811.0.9.0'
        )
        assert ui.implementation_version_name == b'PYNETDICOM_090'

        for item in ui.user_data:
            if isinstance(item, ImplementationVersionNameSubItem):
                ui.user_data.remove(item)
        assert ui.implementation_version_name is None


class TestUserInformation_MaximumLength(object):
    def test_init(self):
        """Test a new MaximumLengthSubItem."""
        item = MaximumLengthSubItem()
        assert item.item_type == 0x51
        assert item.item_length == 4
        assert len(item) == 8
        assert item.maximum_length_received is None

    def test_string_output(self):
        """Test the string output"""
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)
        item = pdu.user_information.user_data[0]
        assert '16382' in item.__str__()

    def test_decode(self):
        """Check decoding produces the correct values """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)

        max_length = pdu.user_information.user_data[0]

        assert max_length.item_length == 4
        assert len(max_length) == 8
        assert max_length.maximum_length_received == 16382

    def test_encode(self):
        """Check encoding produces the correct output """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)

        max_length = pdu.user_information.user_data[0]

        assert max_length.encode(), maximum_length_received

    def test_to_primitive(self):
        """Check converting to primitive """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)
        max_length = pdu.user_information.user_data[0]
        result = max_length.to_primitive()
        check = MaximumLengthNotification()
        check.maximum_length_received = 16382
        assert result == check

    def test_from_primitive(self):
        """Check converting from primitive """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)
        orig_max_length = pdu.user_information.user_data[0]
        params = orig_max_length.to_primitive()
        new_max_length = MaximumLengthSubItem()
        new_max_length.from_primitive(params)
        assert orig_max_length == new_max_length


class TestUserInformation_ImplementationUID(object):
    def setup(self):
        self.default_conformance = _config.ENFORCE_UID_CONFORMANCE

    def teardown(self):
        _config.ENFORCE_UID_CONFORMANCE = self.default_conformance

    def test_uid_conformance(self):
        """Test the UID conformance with ENFORCE_UID_CONFORMANCE."""
        _config.ENFORCE_UID_CONFORMANCE = False

        item = ImplementationClassUIDSubItem()
        item.implementation_class_uid = 'abc'
        assert item.implementation_class_uid == 'abc'

        msg = r"Implementation Class UID is an invalid UID"
        with pytest.raises(ValueError, match=msg):
            item.implementation_class_uid = 'abc' * 22

        _config.ENFORCE_UID_CONFORMANCE = True
        with pytest.raises(ValueError, match=msg):
            item.implementation_class_uid = 'abc'

    def test_init(self):
        """Test a new ImplementationClassUIDSubItem."""
        item = ImplementationClassUIDSubItem()
        assert item.item_type == 0x52
        assert item.item_length == 0
        assert len(item) == 4
        assert item.implementation_class_uid is None

        item.decode(
            b'\x52\x00\x00\x14\x31\x2e\x32\x2e\x31\x32\x34\x2e\x31\x31\x33\x35\x33\x32\x2e\x33\x33\x32\x30\x00'
        )
        primitive = item.to_primitive()

    def test_string_output(self):
        """Test the string output"""
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)
        item = pdu.user_information.user_data[1]
        assert '1.2.826.0.1.3680043' in item.__str__()

    def test_decode(self):
        """Check decoding produces the correct values """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)

        uid = pdu.user_information.user_data[1]

        assert uid.item_length == 32
        assert len(uid) == 36
        assert uid.implementation_class_uid == UID(
            '1.2.826.0.1.3680043.9.3811.0.9.0'
        )

    def test_encode(self):
        """Check encoding produces the correct output """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)

        uid = pdu.user_information.user_data[1]

        assert uid.encode() == implementation_class_uid

    def test_to_primitive(self):
        """Check converting to primitive """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)

        uid = pdu.user_information.user_data[1]

        result = uid.to_primitive()

        check = ImplementationClassUIDNotification()
        check.implementation_class_uid = UID(
            '1.2.826.0.1.3680043.9.3811.0.9.0'
        )
        assert result == check

    def test_from_primitive(self):
        """Check converting from primitive """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)

        orig_uid = pdu.user_information.user_data[1]
        params = orig_uid.to_primitive()

        new_uid = ImplementationClassUIDSubItem()
        new_uid.from_primitive(params)

        assert orig_uid == new_uid

    def test_properies(self):
        """Check property setters and getters """
        uid = ImplementationClassUIDSubItem()
        uid.implementation_class_uid = '1.2.826.0.1.3680043.9.3811.0.9.1'

        assert uid.implementation_class_uid == UID(
            '1.2.826.0.1.3680043.9.3811.0.9.1'
        )

        uid.implementation_class_uid = b'1.2.826.0.1.3680043.9.3811.0.9.2'
        assert uid.implementation_class_uid == UID(
            '1.2.826.0.1.3680043.9.3811.0.9.2'
        )

        uid.implementation_class_uid = UID('1.2.826.0.1.3680043.9.3811.0.9.3')
        assert uid.implementation_class_uid == UID(
            '1.2.826.0.1.3680043.9.3811.0.9.3'
        )

        with pytest.raises(TypeError):
            uid.implementation_class_uid = 10002

    def test_encode_odd(self):
        """Test encoding odd-length UID"""
        item = ImplementationClassUIDSubItem()
        item.implementation_class_uid = '1.2.3'
        assert len(item.implementation_class_uid) % 2 > 0
        assert item.item_length == 5
        assert len(item) == 9
        enc = item.encode()
        assert enc == b'\x52\x00\x00\x05\x31\x2e\x32\x2e\x33'

    def test_encode_even(self):
        """Test encoding even-length UID"""
        item = ImplementationClassUIDSubItem()
        item.implementation_class_uid = '1.2.31'
        assert len(item.implementation_class_uid) % 2 == 0
        assert item.item_length == 6
        assert len(item) == 10
        enc = item.encode()
        assert enc == b'\x52\x00\x00\x06\x31\x2e\x32\x2e\x33\x31'

    def test_decode_odd(self):
        """Test decoding odd-length UID"""
        bytestream = b'\x52\x00\x00\x05\x31\x2e\x32\x2e\x33'
        item = ImplementationClassUIDSubItem()
        item.decode(bytestream)
        assert item.item_length == 5
        assert item.implementation_class_uid == '1.2.3'
        assert len(item.implementation_class_uid) % 2 > 0
        assert len(item) == 9
        assert item.encode() == bytestream

    def test_decode_even(self):
        """Test decoding even-length UID"""
        bytestream = b'\x52\x00\x00\x06\x31\x2e\x32\x2e\x33\x31'
        item = ImplementationClassUIDSubItem()
        item.decode(bytestream)
        assert item.item_length == 6
        assert item.implementation_class_uid == '1.2.31'
        assert len(item.implementation_class_uid) % 2 == 0
        assert len(item) == 10
        assert item.encode() == bytestream

    def test_decode_padded_odd(self):
        """Test decoding a padded odd-length UID"""
        # Non-conformant but handle anyway
        bytestream = b'\x52\x00\x00\x06\x31\x2e\x32\x2e\x33\x00'
        item = ImplementationClassUIDSubItem()
        item.decode(bytestream)
        assert item.item_length == 5
        assert item.implementation_class_uid == '1.2.3'
        assert len(item.implementation_class_uid) % 2 > 0
        assert len(item) == 9
        assert item.encode() == b'\x52\x00\x00\x05\x31\x2e\x32\x2e\x33'

    def test_no_log_padded(self, caplog):
        """Regression test for #240."""
        _config.ENFORCE_UID_CONFORMANCE = True
        caplog.set_level(logging.DEBUG, logger='pynetdicom.pdu_primitives')
        # Confirm that no longer logs invalid UID
        item = ImplementationClassUIDSubItem()
        # Valid UID (with non-conformant padding)
        item.decode(
            b'\x52\x00\x00\x14'
            b'\x31\x2e\x32\x2e\x31\x32\x34\x2e\x31\x31\x33\x35\x33\x32\x2e'
            b'\x33\x33\x32\x30\x00'
        )
        primitive = item.to_primitive()
        assert caplog.text == ''

        # Invalid UID (with no padding)
        msg = r"Implementation Class UID is an invalid UID"
        with pytest.raises(ValueError, match=msg):
            item.decode(
                b'\x52\x00\x00\x08'
                b'\x30\x30\x2e\x31\x2e\x32\x2e\x33'
            )

        # Invalid UID (with non-conformant padding)
        with pytest.raises(ValueError, match=msg):
            item.decode(
                b'\x52\x00\x00\x09'
                b'\x30\x30\x2e\x31\x2e\x32\x2e\x33\x00'
            )

        item._implementation_class_uid = '00.1.2.3'
        msg = (
            r"The Implementation Class UID Notification's 'Implementation "
            r"Class UID' parameter value '00.1.2.3' is not a valid UID"
        )
        with pytest.raises(ValueError, match=msg):
            primitive = item.to_primitive()

        assert msg in caplog.text


class TestUserInformation_ImplementationVersion(object):
    def test_init(self):
        """Test a new ImplementationVersionNameSubItem."""
        item = ImplementationVersionNameSubItem()
        assert item.item_type == 0x55
        assert item.item_length == 0
        assert len(item) == 4
        assert item.implementation_version_name is None

    def test_string_output(self):
        """Test the string output"""
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)
        item = pdu.user_information.user_data[2]
        assert 'PYNETDICOM_090' in item.__str__()

    def test_decode(self):
        """Check decoding produces the correct values """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)

        version = pdu.user_information.user_data[2]

        assert version.item_length == 14
        assert len(version) == 18
        assert version.implementation_version_name == b'PYNETDICOM_090'

    def test_encode(self):
        """Check encoding produces the correct output """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)

        version = pdu.user_information.user_data[2]
        version.implementation_version_name = b'PYNETDICOM_090'

        assert version.encode() == implementation_version_name

    def test_to_primitive(self):
        """Check converting to primitive """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)

        version = pdu.user_information.user_data[2]

        result = version.to_primitive()

        check = ImplementationVersionNameNotification()
        check.implementation_version_name = b'PYNETDICOM_090'
        assert result == check

    def test_from_primitive(self):
        """Check converting from primitive """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)

        orig_version = pdu.user_information.user_data[2]
        params = orig_version.to_primitive()

        new_version = ImplementationVersionNameSubItem()
        new_version.from_primitive(params)

        assert orig_version == new_version

    def test_properies(self):
        """Check property setters and getters """
        version = ImplementationVersionNameSubItem()

        version.implementation_version_name = 'PYNETDICOM'
        assert version.implementation_version_name == b'PYNETDICOM'

        version.implementation_version_name = b'PYNETDICOM_090'
        assert version.implementation_version_name == b'PYNETDICOM_090'


class TestUserInformation_Asynchronous(object):
    def test_init(self):
        """Test a new AsynchronousOperationsWindowSubItem."""
        item = AsynchronousOperationsWindowSubItem()
        assert item.item_type == 0x53
        assert item.item_length == 4
        assert len(item) == 8
        assert item.maximum_number_operations_invoked is None
        assert item.maximum_number_operations_performed is None

        assert item.max_operations_invoked is None
        assert item.max_operations_performed is None

    def test_string_output(self):
        """Test the string output"""
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_user_async)
        for item in pdu.user_information.user_data:
            if isinstance(item, AsynchronousOperationsWindowSubItem):
                assert 'invoked: 5' in item.__str__()
                assert 'performed: 5' in item.__str__()

    def test_decode(self):
        """Check decoding produces the correct values """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_user_async)

        for item in pdu.user_information.user_data:
            if isinstance(item, AsynchronousOperationsWindowSubItem):
                break

        assert item.item_length == 4
        assert len(item) == 8
        assert item.maximum_number_operations_invoked == 5
        assert item.maximum_number_operations_performed == 5

        assert item.max_operations_invoked == 5
        assert item.max_operations_performed == 5

    def test_encode(self):
        """Check encoding produces the correct output """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_user_async)
        for item in pdu.user_information.user_data:
            if isinstance(item, AsynchronousOperationsWindowSubItem):
                break

        assert item.encode() == asynchronous_window_ops

    def test_to_primitive(self):
        """Check converting to primitive """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_user_async)
        for item in pdu.user_information.user_data:
            if isinstance(item, AsynchronousOperationsWindowSubItem):
                break

        check = AsynchronousOperationsWindowNegotiation()
        check.maximum_number_operations_invoked = 5
        check.maximum_number_operations_performed = 5
        assert item.to_primitive() == check

    def test_from_primitive(self):
        """Check converting from primitive """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_user_async)

        for item in pdu.user_information.user_data:
            if isinstance(item, AsynchronousOperationsWindowSubItem):
                break

        new = AsynchronousOperationsWindowSubItem()
        new.from_primitive(item.to_primitive())

        assert item == new

    def test_properies(self):
        """Check property setters and getters """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_user_async)

        for item in pdu.user_information.user_data:
            if isinstance(item, AsynchronousOperationsWindowSubItem):
                break

        assert item.max_operations_invoked == 5
        assert item.max_operations_performed == 5


class TestUserInformation_RoleSelection(object):
    def setup(self):
        self.default_conformance = _config.ENFORCE_UID_CONFORMANCE

    def teardown(self):
        _config.ENFORCE_UID_CONFORMANCE = self.default_conformance

    def test_uid_conformance(self):
        """Test the UID conformance with ENFORCE_UID_CONFORMANCE."""
        _config.ENFORCE_UID_CONFORMANCE = False

        item = SCP_SCU_RoleSelectionSubItem()
        item.sop_class_uid = 'abc'
        assert item.sop_class_uid == 'abc'

        msg = r"SOP Class UID is an invalid UID"
        with pytest.raises(ValueError, match=msg):
            item.sop_class_uid = 'abc' * 22

        _config.ENFORCE_UID_CONFORMANCE = True
        with pytest.raises(ValueError, match=msg):
            item.sop_class_uid = 'abc'

    def test_init(self):
        """Test a new SCP_SCU_RoleSelectionSubItem."""
        item = SCP_SCU_RoleSelectionSubItem()
        assert item.item_type == 0x54
        assert item.item_length == 4
        assert len(item) == 8
        assert item.uid_length == 0
        assert item.sop_class_uid is None
        assert item.scu_role is None
        assert item.scp_role is None

        assert item.scu is None
        assert item.scp is None
        assert item.uid is None

    def test_string_output(self):
        """Test the string output"""
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_role)
        item = pdu.user_information.role_selection['1.2.840.10008.5.1.4.1.1.2']
        assert 'CT Image Storage' in item.__str__()
        assert 'SCU Role: 0' in item.__str__()

    def test_decode(self):
        """Check decoding produces the correct values """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_role)

        item = pdu.user_information.role_selection['1.2.840.10008.5.1.4.1.1.2']

        assert item.item_type == 0x54
        assert item.item_length == 29
        assert len(item) == 33
        assert item.uid_length == 25
        assert item.sop_class_uid == UID('1.2.840.10008.5.1.4.1.1.2')
        assert item.scu_role == 0
        assert item.scp_role == 1

    def test_encode(self):
        """Check encoding produces the correct output """
        # Encoding follows the rules of UIDs (trailing padding null if odd)
        item = SCP_SCU_RoleSelectionSubItem()
        item.scu_role = False
        item.scp_role = True
        # Odd length
        uid = '1.2.840.10008.5.1.4.1.1.2'
        assert len(uid) % 2 > 0
        item.sop_class_uid = uid

        assert item.encode() == role_selection_odd

        # Even length
        uid = '1.2.840.10008.5.1.4.1.1.21'
        assert len(uid) % 2 == 0
        item.sop_class_uid = uid

        assert item.encode() == role_selection

    def test_to_primitive(self):
        """Check converting to primitive """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_role)

        item = pdu.user_information.role_selection['1.2.840.10008.5.1.4.1.1.2']

        check = SCP_SCU_RoleSelectionNegotiation()
        check.sop_class_uid = UID('1.2.840.10008.5.1.4.1.1.2')
        check.scu_role = False
        check.scp_role = True

        assert item.to_primitive() == check

    def test_from_primitive(self):
        """Check converting from primitive"""
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_role)

        orig = pdu.user_information.role_selection['1.2.840.10008.5.1.4.1.1.2']
        params = orig.to_primitive()

        new = SCP_SCU_RoleSelectionSubItem()
        new.from_primitive(params)

        assert orig == new

    def test_from_primitive_no_scu(self):
        """Check converting from primitive with scu_role undefined"""
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_role)

        orig = pdu.user_information.role_selection['1.2.840.10008.5.1.4.1.1.2']
        params = orig.to_primitive()

        assert not params.scu_role
        # None should become False
        params.scu_role = None
        assert params.scu_role is None

        new = SCP_SCU_RoleSelectionSubItem()
        new.from_primitive(params)

        assert orig == new

    def test_properties(self):
        """Check property setters and getters """
        item = SCP_SCU_RoleSelectionSubItem()

        # SOP Class UID
        item.sop_class_uid = '1.1'
        assert item.sop_class_uid == UID('1.1')
        assert isinstance(item.sop_class_uid, UID)
        assert item.uid_length == 3
        item.sop_class_uid = b'1.1.2'
        assert item.sop_class_uid == UID('1.1.2')
        assert isinstance(item.sop_class_uid, UID)
        assert item.uid_length == 5
        item.sop_class_uid = UID('1.1.3.1')
        assert item.sop_class_uid == UID('1.1.3.1')
        assert isinstance(item.sop_class_uid, UID)
        assert item.uid_length == 7
        item.sop_class_uid = UID('1.1.3.12')
        assert item.sop_class_uid == UID('1.1.3.12')
        assert isinstance(item.sop_class_uid, UID)
        assert item.uid_length == 8

        assert item.uid == item.sop_class_uid

        with pytest.raises(TypeError):
            item.sop_class_uid = 10002

        # SCU Role
        item.scu_role = 0
        assert item.scu == 0
        item.scu_role = 1
        assert item.scu, 1
        assert item.scu, item.scu_role

        with pytest.raises(ValueError):
            item.scu_role = 2

        # SCP Role
        item.scp_role = 0
        assert item.scp == 0
        item.scp_role = 1
        assert item.scp == 1
        assert item.scp == item.scp_role

        with pytest.raises(ValueError):
            item.scp_role = 2

    def test_encode_odd(self):
        """Test encoding odd-length UID"""
        item = SCP_SCU_RoleSelectionSubItem()
        item.scu_role = False
        item.scp_role = True
        item.sop_class_uid = '1.2.3'
        assert len(item.sop_class_uid) % 2 > 0
        assert item.uid_length == 5
        assert item.item_length == 9
        assert len(item) == 13
        enc = item.encode()
        assert enc == (
            b'\x54\x00\x00\x09\x00\x05\x31\x2e\x32\x2e\x33\x00\x01'
        )

    def test_encode_even(self):
        """Test encoding even-length UID"""
        item = SCP_SCU_RoleSelectionSubItem()
        item.scu_role = 0
        item.scp_role = 1
        item.sop_class_uid = '1.2.31'
        assert len(item.sop_class_uid) % 2 == 0
        assert item.uid_length == 6
        assert item.item_length == 10
        assert len(item) == 14
        enc = item.encode()
        assert enc == (
            b'\x54\x00\x00\x0a\x00\x06\x31\x2e\x32\x2e\x33\x31\x00\x01'
        )

    def test_decode_odd(self):
        """Test decoding odd-length UID"""
        bytestream = (
            b'\x54\x00\x00\x09\x00\x05\x31\x2e\x32\x2e\x33\x00\x01'
        )
        item = SCP_SCU_RoleSelectionSubItem()
        item.decode(bytestream)
        assert item.item_length == 9
        assert item.sop_class_uid == '1.2.3'
        assert item.uid_length == 5
        assert len(item.sop_class_uid) % 2 > 0
        assert len(item) == 13
        assert item.scu_role == 0
        assert item.scp_role == 1
        assert item.encode() == bytestream

    def test_decode_even(self):
        """Test decoding even-length UID"""
        bytestream = (
            b'\x54\x00\x00\x0a\x00\x06\x31\x2e\x32\x2e\x33\x31\x00\x01'
        )
        item = SCP_SCU_RoleSelectionSubItem()
        item.decode(bytestream)
        assert item.item_length == 10
        assert item.uid_length == 6
        assert item.sop_class_uid == '1.2.31'
        assert len(item.sop_class_uid) % 2 == 0
        assert len(item) == 14
        assert item.scu_role == 0
        assert item.scp_role == 1
        assert item.encode() == bytestream

    def test_decode_padded_odd(self):
        """Test decoding padded odd-length UID"""
        # Non-conformant but handle anyway
        bytestream = (
            b'\x54\x00\x00\x0a\x00\x06\x31\x2e\x32\x2e\x33\x00\x00\x01'
        )
        item = SCP_SCU_RoleSelectionSubItem()
        item.decode(bytestream)
        assert item.item_length == 9
        assert item.sop_class_uid == '1.2.3'
        assert item.uid_length == 5
        assert len(item.sop_class_uid) % 2 > 0
        assert len(item) == 13
        assert item.scu_role == 0
        assert item.scp_role == 1
        assert item.encode() == (
            b'\x54\x00\x00\x09\x00\x05\x31\x2e\x32\x2e\x33\x00\x01'
        )


class TestUserIdentityRQ_UserNoPass(object):
    def test_init(self):
        """Test a new UserIdentitySubItemRQ."""
        item = UserIdentitySubItemRQ()
        assert item.item_type == 0x58
        assert item.item_length == 6
        assert len(item) == 10
        assert item.user_identity_type is None
        assert item.positive_response_requested is None
        assert item.primary_field_length == 0
        assert item.primary_field is None
        assert item.secondary_field_length == 0
        assert item.secondary_field == b''

        assert item.id_type is None
        with pytest.raises(KeyError):
            item.id_type_str
        assert item.primary is None
        assert item.response_requested is None
        assert item.secondary == b''

    def test_string_output(self):
        """Test the string output"""
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_user_async)
        item = pdu.user_information.user_identity
        assert 'type: 1' in item.__str__()
        assert 'requested: 1' in item.__str__()
        assert ("Primary field: b'pynetdicom'" in item.__str__() or
                "Primary field: pynetdicom" in item.__str__())

    def test_decode(self):
        """Check decoding produces the correct values """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_user_async)

        item = pdu.user_information.user_identity

        assert item.item_type == 0x58
        assert item.item_length == 16
        assert len(item) == 20
        assert item.user_identity_type == 1
        assert item.positive_response_requested == 1
        assert item.primary_field_length == 10
        assert item.primary_field == b'pynetdicom'
        assert item.secondary_field_length == 0
        assert item.secondary_field == b''

    def test_encode(self):
        """Check encoding produces the correct output """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_user_async)
        item = pdu.user_information.user_identity
        assert item.encode() == user_identity_rq_user_nopw

    def test_to_primitive(self):
        """Check converting to primitive """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_user_async)
        item = pdu.user_information.user_identity

        check = UserIdentityNegotiation()
        check.user_identity_type = 1
        check.positive_response_requested = True
        check.primary_field = b'pynetdicom'
        check.secondary_field = b''
        assert item.to_primitive() == check

    def test_from_primitive(self):
        """Check converting from primitive """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_user_async)

        orig = pdu.user_information.user_identity
        params = orig.to_primitive()

        new = UserIdentitySubItemRQ()
        new.from_primitive(params)

        assert orig == new

    def test_properies(self):
        """Check property setters and getters """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_user_async)

        item = pdu.user_information.user_identity

        assert item.id_type == 1
        assert item.id_type_str == 'Username'
        assert item.primary == b'pynetdicom'
        assert item.response_requested == True
        assert item.secondary == b''

        item.user_identity_type = 2
        assert item.id_type == 2
        assert item.id_type_str == 'Username/Password'

        item.user_identity_type = 3
        assert item.id_type == 3
        assert item.id_type_str == 'Kerberos'

        item.user_identity_type = 4
        assert item.id_type == 4
        assert item.id_type_str == 'SAML'


class TestUserIdentityRQ_UserPass(object):
    def test_string_output(self):
        """Test the string output"""
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_user_id_user_pass)
        item = pdu.user_information.user_identity
        assert 'type: 2' in item.__str__()
        assert 'requested: 0' in item.__str__()
        assert ("Primary field: b'pynetdicom'" in item.__str__() or
                "Primary field: pynetdicom" in item.__str__())
        assert ("Secondary field: b'p4ssw0rd'" in item.__str__() or
                "Secondary field: p4ssw0rd" in item.__str__())

    def test_decode(self):
        """Check decoding produces the correct values """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_user_id_user_pass)

        item = pdu.user_information.user_identity

        assert item.item_type == 0x58
        assert item.item_length == 24
        assert len(item) == 28
        assert item.user_identity_type == 2
        assert item.positive_response_requested == 0
        assert item.primary_field_length == 10
        assert item.primary_field == b'pynetdicom'
        assert item.secondary_field_length == 8
        assert item.secondary_field == b'p4ssw0rd'

    def test_encode(self):
        """Check encoding produces the correct output """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_user_id_user_pass)

        item = pdu.user_information.user_identity
        assert item.encode() == user_identity_rq_user_pass

    def test_to_primitive(self):
        """Check converting to primitive """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_user_id_user_pass)

        item = pdu.user_information.user_identity

        check = UserIdentityNegotiation()
        check.user_identity_type = 2
        check.positive_response_requested = False
        check.primary_field = b'pynetdicom'
        check.secondary_field = b'p4ssw0rd'

        assert item.to_primitive() == check

    def test_from_primitive(self):
        """Check converting from primitive """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_user_id_user_pass)

        orig = pdu.user_information.user_identity
        params = orig.to_primitive()

        new = UserIdentitySubItemRQ()
        new.from_primitive(params)

        assert orig == new

    def test_properties(self):
        """Check property setters and getters """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_user_id_user_pass)

        item = pdu.user_information.user_identity

        assert item.id_type == 2
        assert item.id_type_str == 'Username/Password'
        assert item.primary == b'pynetdicom'
        assert item.response_requested == False
        assert item.secondary == b'p4ssw0rd'


class TestUserIdentityAC_UserResponse(object):
    def test_init(self):
        """Test a new UserIdentitySubItemAC."""
        item = UserIdentitySubItemAC()
        assert item.item_type == 0x59
        assert item.item_length == 2
        assert len(item) == 6
        assert item.server_response is None
        assert item.server_response_length == 0

        assert item.response is None

    def test_string_output(self):
        """Test the string output"""
        pdu = A_ASSOCIATE_AC()
        pdu.decode(a_associate_ac_user)
        item = pdu.user_information.user_identity
        assert ("Server response: b'Accepted'" in item.__str__() or
                "Server response: Accepted" in item.__str__())

    def test_decode(self):
        """Check decoding produces the correct values """
        pdu = A_ASSOCIATE_AC()
        pdu.decode(a_associate_ac_user)

        item = pdu.user_information.user_identity

        assert item.item_type == 0x59
        assert item.item_length == 10
        assert len(item) == 14
        assert item.server_response_length == 8
        assert item.server_response == b'Accepted'

        assert item.response == b'Accepted'

    def test_encode(self):
        """Check encoding produces the correct output """
        pdu = A_ASSOCIATE_AC()
        pdu.decode(a_associate_ac_user)

        item = pdu.user_information.user_identity
        assert item.encode() == user_identity_ac

    def test_to_primitive(self):
        """Check converting to primitive """
        pdu = A_ASSOCIATE_AC()
        pdu.decode(a_associate_ac_user)

        item = pdu.user_information.user_identity
        check = UserIdentityNegotiation()
        check.server_response = b'Accepted'
        assert item.to_primitive() == check

    def test_from_primitive(self):
        """Check converting from primitive """
        pdu = A_ASSOCIATE_AC()
        pdu.decode(a_associate_ac_user)
        orig = pdu.user_information.user_identity
        params = orig.to_primitive()

        new = UserIdentitySubItemAC()
        new.from_primitive(params)

        assert orig == new

    def test_properies(self):
        """Check property setters and getters """
        pdu = A_ASSOCIATE_AC()
        pdu.decode(a_associate_ac_user)
        item = pdu.user_information.user_identity
        assert item.response == b'Accepted'


class TestUserInformation_ExtendedNegotiation(object):
    def setup(self):
        self.default_conformance = _config.ENFORCE_UID_CONFORMANCE

    def teardown(self):
        _config.ENFORCE_UID_CONFORMANCE = self.default_conformance

    def test_uid_conformance(self):
        """Test the UID conformance with ENFORCE_UID_CONFORMANCE."""
        _config.ENFORCE_UID_CONFORMANCE = False

        item = SOPClassExtendedNegotiationSubItem()
        item.sop_class_uid = 'abc'
        assert item.sop_class_uid == 'abc'

        msg = r"SOP Class UID is an invalid UID"
        with pytest.raises(ValueError, match=msg):
            item.sop_class_uid = 'abc' * 22

        _config.ENFORCE_UID_CONFORMANCE = True
        with pytest.raises(ValueError, match=msg):
            item.sop_class_uid = 'abc'

    def test_init(self):
        """Test a new SOPClassExtendedNegotiationSubItem."""
        item = SOPClassExtendedNegotiationSubItem()
        assert item.item_type == 0x56
        assert item.item_length == 2
        assert len(item) == 6
        assert item.sop_class_uid_length == 0
        assert item.sop_class_uid is None
        assert item.service_class_application_information is None

        assert item.app_info is None
        assert item.uid is None

    def test_string_output(self):
        """Test the string output"""
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_user_id_ext_neg)
        item = pdu.user_information.ext_neg[0]
        assert 'CT Image Storage' in item.__str__()
        assert ("information: b'\\x02\\x00" in item.__str__() or
                "information: \\x02\\x00" in item.__str__())

    def test_decode(self):
        """Check decoding produces the correct values """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_user_id_ext_neg)

        item = pdu.user_information.ext_neg[0]

        assert item.item_type == 0x56
        assert item.item_length == 33
        assert len(item) == 37
        assert item.sop_class_uid_length == 25
        assert item.sop_class_uid == UID('1.2.840.10008.5.1.4.1.1.2')
        assert item.service_class_application_information == (
            b'\x02\x00\x03\x00\x01\x00'
        )

        assert item.uid == UID('1.2.840.10008.5.1.4.1.1.2')
        assert item.app_info == b'\x02\x00\x03\x00\x01\x00'

    def test_encode(self):
        """Check encoding produces the correct output """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_user_id_ext_neg)

        item = pdu.user_information.ext_neg[0]

        assert item.encode() == (
            b'\x56\x00\x00\x21\x00\x19\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30'
            b'\x30\x30\x38\x2e\x35\x2e\x31\x2e\x34\x2e\x31\x2e\x31\x2e\x32'
            b'\x02\x00\x03\x00\x01\x00'
        )

    def test_to_primitive(self):
        """Check converting to primitive """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_user_id_ext_neg)

        item = pdu.user_information.ext_neg[0]

        result = item.to_primitive()

        check = SOPClassExtendedNegotiation()
        check.sop_class_uid = UID('1.2.840.10008.5.1.4.1.1.2')
        check.service_class_application_information = (
            b'\x02\x00\x03\x00\x01\x00'
        )

        assert result == check

    def test_from_primitive(self):
        """Check converting from primitive """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_user_id_ext_neg)

        orig = pdu.user_information.ext_neg[0]
        params = orig.to_primitive()

        new = SOPClassExtendedNegotiationSubItem()
        new.from_primitive(params)

        assert orig == new

    def test_properties(self):
        """Check property setters and getters """
        item = SOPClassExtendedNegotiationSubItem()

        # SOP Class UID
        item.sop_class_uid = '1.1.1'
        assert item.sop_class_uid == UID('1.1.1')
        assert item.sop_class_uid_length == 5
        assert isinstance(item.sop_class_uid, UID)
        item.sop_class_uid = b'1.1.2.1'
        assert item.sop_class_uid == UID('1.1.2.1')
        assert item.sop_class_uid_length == 7
        assert isinstance(item.sop_class_uid, UID)
        item.sop_class_uid = UID('1.1.3.1.1')
        assert item.sop_class_uid == UID('1.1.3.1.1')
        assert item.sop_class_uid_length == 9
        assert isinstance(item.sop_class_uid, UID)
        item.sop_class_uid = UID('1.1.3.1.11')
        assert item.sop_class_uid == UID('1.1.3.1.11')
        assert item.sop_class_uid_length == 10
        assert isinstance(item.sop_class_uid, UID)

        assert item.uid == item.sop_class_uid

        with pytest.raises(TypeError):
            item.sop_class_uid = 10002

        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_user_id_ext_neg)

        item = pdu.user_information.ext_neg[0]

        assert item.app_info == b'\x02\x00\x03\x00\x01\x00'

    def test_encode_odd(self):
        """Test encoding odd-length UID"""
        item = SOPClassExtendedNegotiationSubItem()
        item.sop_class_uid = '1.2.3'
        item.service_class_application_information = b'\xFF'
        assert len(item.sop_class_uid) % 2 > 0
        assert item.sop_class_uid_length == 5
        assert item.item_length == 8
        assert len(item) == 12
        enc = item.encode()
        assert enc == b'\x56\x00\x00\x08\x00\x05\x31\x2e\x32\x2e\x33\xFF'

    def test_encode_even(self):
        """Test encoding even-length UID"""
        item = SOPClassExtendedNegotiationSubItem()
        item.service_class_application_information = b'\xFF'
        item.sop_class_uid = '1.2.31'
        assert len(item.sop_class_uid) % 2 == 0
        assert item.sop_class_uid_length == 6
        assert item.item_length == 9
        assert len(item) == 13
        enc = item.encode()
        assert enc == (
            b'\x56\x00\x00\x09\x00\x06\x31\x2e\x32\x2e\x33\x31\xFF'
        )

    def test_decode_odd(self):
        """Test decoding odd-length UID"""
        bytestream = (
            b'\x56\x00\x00\x08\x00\x05\x31\x2e\x32\x2e\x33\xFF'
        )
        item = SOPClassExtendedNegotiationSubItem()
        item.decode(bytestream)
        assert item.item_length == 8
        assert item.sop_class_uid == '1.2.3'
        assert item.sop_class_uid_length == 5
        assert len(item.sop_class_uid) % 2 > 0
        assert len(item) == 12
        assert item.service_class_application_information == b'\xFF'
        assert item.encode() == bytestream

    def test_decode_even(self):
        """Test decoding even-length UID"""
        bytestream = (
            b'\x56\x00\x00\x09\x00\x06\x31\x2e\x32\x2e\x33\x31\xFF'
        )
        item = SOPClassExtendedNegotiationSubItem()
        item.decode(bytestream)
        assert item.item_length == 9
        assert item.sop_class_uid_length == 6
        assert item.sop_class_uid == '1.2.31'
        assert len(item.sop_class_uid) % 2 == 0
        assert len(item) == 13
        assert item.service_class_application_information == b'\xFF'
        assert item.encode() == bytestream

    def test_decode_padded_odd(self):
        """Test decoding padded odd-length UID"""
        # Non-conformant but handle anyway
        bytestream = (
            b'\x56\x00\x00\x09\x00\x06\x31\x2e\x32\x2e\x33\x00\xFF'
        )
        item = SOPClassExtendedNegotiationSubItem()
        item.decode(bytestream)
        assert item.item_length == 8
        assert item.sop_class_uid == '1.2.3'
        assert item.sop_class_uid_length == 5
        assert len(item.sop_class_uid) % 2 > 0
        assert len(item) == 12
        assert item.service_class_application_information == b'\xFF'
        assert item.encode() == (
            b'\x56\x00\x00\x08\x00\x05\x31\x2e\x32\x2e\x33\xFF'
        )


class TestUserInformation_CommonExtendedNegotiation(object):
    def setup(self):
        self.default_conformance = _config.ENFORCE_UID_CONFORMANCE

    def teardown(self):
        _config.ENFORCE_UID_CONFORMANCE = self.default_conformance

    def test_uid_conformance(self):
        """Test the UID conformance with ENFORCE_UID_CONFORMANCE."""
        _config.ENFORCE_UID_CONFORMANCE = False

        item = SOPClassCommonExtendedNegotiationSubItem()
        item.sop_class_uid = 'abc'
        assert item.sop_class_uid == 'abc'
        item.service_class_uid = 'abc'
        assert item.service_class_uid == 'abc'
        item.related_general_sop_class_identification = ['abc']
        assert item.related_general_sop_class_identification == ['abc']

        msg = r"SOP Class UID is an invalid UID"
        with pytest.raises(ValueError, match=msg):
            item.sop_class_uid = 'abc' * 22

        msg = r"Service Class UID is an invalid UID"
        with pytest.raises(ValueError, match=msg):
            item.service_class_uid = 'abc' * 22

        msg = (
            r"Related General SOP Class Identification contains "
            r"an invalid UID"
        )
        with pytest.raises(ValueError, match=msg):
            item.related_general_sop_class_identification = ['abc' * 22]

        _config.ENFORCE_UID_CONFORMANCE = True
        msg = r"SOP Class UID is an invalid UID"
        with pytest.raises(ValueError, match=msg):
            item.sop_class_uid = 'abc'

        msg = r"Service Class UID is an invalid UID"
        with pytest.raises(ValueError, match=msg):
            item.service_class_uid = 'abc'

        msg = (
            r"Related General SOP Class Identification contains "
            r"an invalid UID"
        )
        with pytest.raises(ValueError, match=msg):
            item.related_general_sop_class_identification = ['abc']

    def test_init(self):
        """Test a new SOPClassCommonExtendedNegotiationSubItem."""
        item = SOPClassCommonExtendedNegotiationSubItem()
        assert item.item_type == 0x57
        assert item.item_length == 6
        assert len(item) == 10
        assert item.sub_item_version == 0x00
        assert item.sop_class_uid_length == 0
        assert item.sop_class_uid is None
        assert item.service_class_uid_length == 0
        assert item.service_class_uid is None
        assert item.related_general_sop_class_identification_length == 0
        assert item.related_general_sop_class_identification == []

    def test_string_output(self):
        """Test the string output"""
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_com_ext_neg)
        item = pdu.user_information.common_ext_neg[0]
        assert 'MR Image Storage' in item.__str__()
        assert 'Enhanced SR Storage' in item.__str__()

    def test_decode(self):
        """Check decoding produces the correct values """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_com_ext_neg)

        item = pdu.user_information.common_ext_neg[0]

        assert item.item_type == 0x57
        assert item.item_length == 79
        assert len(item) == 83
        assert item.sop_class_uid_length == 25
        assert item.sop_class_uid == UID('1.2.840.10008.5.1.4.1.1.4')
        assert item.service_class_uid_length == 17
        assert item.service_class_uid == UID('1.2.840.10008.4.2')
        assert item.related_general_sop_class_identification_length == 31
        assert item.related_general_sop_class_identification == [
            UID('1.2.840.10008.5.1.4.1.1.88.22')
        ]

    def test_encode(self):
        """Check encoding produces the correct output """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_com_ext_neg)
        item = pdu.user_information.common_ext_neg[0]
        assert item.encode() == (
            # Item type, item length
            b'\x57\x00\x00\x4f'
            # SOP Class UID length, SOP Class UID
            b'\x00\x19\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e'
            b'\x35\x2e\x31\x2e\x34\x2e\x31\x2e\x31\x2e\x34'
            # Service Class UID length, Service Class UID
            b'\x00\x11\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e'
            b'\x34\x2e\x32'
            # Related general ID length
            b'\x00\x1f'
            # Related general ID list
            b'\x00\x1d\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30'
            b'\x30\x30\x38\x2e\x35\x2e\x31\x2e\x34\x2e\x31\x2e\x31\x2e\x38\x38'
            b'\x2e\x32\x32'
        )

    def test_to_primitive(self):
        """Check converting to primitive """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_com_ext_neg)

        item = pdu.user_information.common_ext_neg[0]

        check = SOPClassCommonExtendedNegotiation()
        check.sop_class_uid = UID('1.2.840.10008.5.1.4.1.1.4')
        check.service_class_uid = UID('1.2.840.10008.4.2')
        check.related_general_sop_class_identification = [
            UID('1.2.840.10008.5.1.4.1.1.88.22')
        ]

        assert item.to_primitive() == check

    def test_from_primitive(self):
        """Check converting from primitive """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq_com_ext_neg)

        orig = pdu.user_information.common_ext_neg[0]
        params = orig.to_primitive()

        new = SOPClassCommonExtendedNegotiationSubItem()
        new.from_primitive(params)

        assert orig == new

    def test_properties(self):
        """Check property setters and getters """
        item = SOPClassCommonExtendedNegotiationSubItem()

        # SOP Class UID
        item.sop_class_uid = '1.1'
        assert item.sop_class_uid == UID('1.1')
        assert item.sop_class_uid_length == 3

        with pytest.raises(TypeError):
            item.sop_class_uid = 10002

        # Service Class UID
        item.service_class_uid = '1.2'
        assert item.service_class_uid == UID('1.2')
        assert item.service_class_uid_length == 3
        item.service_class_uid = b'1.2.3'
        assert item.service_class_uid == UID('1.2.3')
        assert item.service_class_uid_length == 5
        item.service_class_uid = UID('1.2.3.4')
        assert item.service_class_uid == UID('1.2.3.4')
        assert item.service_class_uid_length == 7
        item.service_class_uid = UID('1.2.3.41')
        assert item.service_class_uid == UID('1.2.3.41')
        assert item.service_class_uid_length == 8

        with pytest.raises(TypeError):
            item.service_class_uid = 10002

        # Related General SOP Class UID
        item.related_general_sop_class_identification = ['1.2']
        assert item.related_general_sop_class_identification == [UID('1.2')]
        assert item.related_general_sop_class_identification_length == 5
        item.related_general_sop_class_identification = [b'1.2.3']
        assert item.related_general_sop_class_identification == [UID('1.2.3')]
        assert item.related_general_sop_class_identification_length ==  7
        item.related_general_sop_class_identification = [UID('1.2.3.4')]
        assert item.related_general_sop_class_identification == [UID('1.2.3.4')]
        assert item.related_general_sop_class_identification_length == 9
        item.related_general_sop_class_identification = [UID('1.2.3.41')]
        assert item.related_general_sop_class_identification == [UID('1.2.3.41')]
        assert item.related_general_sop_class_identification_length == 10

        with pytest.raises(TypeError):
            item.related_general_sop_class_identification = 10002
        with pytest.raises(TypeError):
            item.related_general_sop_class_identification = [10002]

    def test_generate_items(self):
        """Test ._generate_items"""
        item = SOPClassCommonExtendedNegotiationSubItem()
        gen = item._generate_items(b'')
        with pytest.raises(StopIteration):
            next(gen)

        # Unpadded odd length UID
        data = b'\x00\x07\x31\x2e\x38\x38\x2e\x32\x32'
        gen = item._generate_items(data)
        assert next(gen) == UID('1.88.22')
        with pytest.raises(StopIteration):
            next(gen)

        # Even length UID
        data += b'\x00\x08\x31\x2e\x38\x31\x38\x2e\x32\x32'
        gen = item._generate_items(data)
        assert next(gen) == UID('1.88.22')
        assert next(gen) == UID('1.818.22')
        with pytest.raises(StopIteration):
            next(gen)

        # Padded odd length UID
        data += b'\x00\x08\x31\x2e\x38\x38\x2e\x32\x32\x00'
        gen = item._generate_items(data)
        assert next(gen) == UID('1.88.22')
        assert next(gen) == UID('1.818.22')
        assert next(gen) == UID('1.88.22')
        with pytest.raises(StopIteration):
            next(gen)

        # Even length UID
        data += b'\x00\x08\x31\x2e\x38\x38\x2e\x32\x32\x31'
        gen = item._generate_items(data)
        assert next(gen) == UID('1.88.22')
        assert next(gen) == UID('1.818.22')
        assert next(gen) == UID('1.88.22')
        assert next(gen) == UID('1.88.221')
        with pytest.raises(StopIteration):
            next(gen)

    def test_generate_items_raises(self):
        """Test failure modes of ._generate_items"""
        item = SOPClassCommonExtendedNegotiationSubItem()

        data = b'\x00\x08\x31\x2e\x38\x38\x2e\x32\x32'
        gen = item._generate_items(data)
        with pytest.raises(AssertionError):
            next(gen)

    def test_wrap_generate_items(self):
        """Test ._wrap_generate_items"""
        item = SOPClassCommonExtendedNegotiationSubItem()
        out = item._wrap_generate_items(b'')
        assert out == []

        data = b'\x00\x07\x31\x2e\x38\x38\x2e\x32\x32'
        out = item._wrap_generate_items(data)
        assert out == [UID('1.88.22')]

        data += b'\x00\x08\x31\x2e\x38\x31\x38\x2e\x32\x32'
        out = item._wrap_generate_items(data)
        assert out == [UID('1.88.22'), UID('1.818.22')]

    def test_wrap_list(self):
        """test ._wrap_list."""
        item = SOPClassCommonExtendedNegotiationSubItem()
        data = [UID('1.88.22'), UID('1.818.22')]
        assert item._wrap_list(data) == (
            b'\x00\x07\x31\x2e\x38\x38\x2e\x32\x32'
            b'\x00\x08\x31\x2e\x38\x31\x38\x2e\x32\x32'
        )
