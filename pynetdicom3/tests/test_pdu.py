"""Tests for the pynetdicom3.pdu module."""

from io import BytesIO
import logging

import pytest

from pydicom.uid import UID

from pynetdicom3 import (
    VerificationSOPClass, StorageSOPClassList, QueryRetrieveSOPClassList
)
from pynetdicom3.pdu import (
    A_ASSOCIATE_RQ, A_ASSOCIATE_AC, A_ASSOCIATE_RJ, P_DATA_TF, A_RELEASE_RQ,
    A_RELEASE_RP, A_ABORT_RQ, MaximumLengthSubItem,
    ImplementationClassUIDSubItem, ImplementationVersionNameSubItem,
    AsynchronousOperationsWindowSubItem, SCP_SCU_RoleSelectionSubItem,
    SOPClassExtendedNegotiationSubItem,
    SOPClassCommonExtendedNegotiationSubItem, UserIdentitySubItemRQ,
    UserIdentitySubItemAC, PDU, ApplicationContextItem,
    PresentationContextItemAC, PresentationContextItemRQ, UserInformationItem,
    PDU_ITEM_TYPES, PDU_TYPES,
)
from pynetdicom3.pdu_primitives import (
    MaximumLengthNegotiation, ImplementationClassUIDNotification,
    ImplementationVersionNameNotification, A_P_ABORT, A_ABORT, A_ASSOCIATE,
    P_DATA
)
from .encoded_pdu_items import (
    a_associate_rq, a_associate_ac, a_associate_rj, a_release_rq, a_release_rq,
    a_release_rp, a_abort, a_p_abort, p_data_tf,
    a_associate_rq_user_id_ext_neg
)
from pynetdicom3.utils import pretty_bytes

LOGGER = logging.getLogger('pynetdicom3')
LOGGER.setLevel(logging.CRITICAL)


class TestPDU_Equality(object):
    """Test the PDU equality/inequality operators."""
    def test_equality(self):
        """Test the equality operator"""
        assert PDU() == PDU()
        assert not PDU() == 'TEST'
        pdu = PDU()
        pdu.formats = ['a']
        assert not pdu == PDU()

    def test_inequality(self):
        """Test the inequality operator"""
        assert not PDU() != PDU()
        assert PDU() != 'TEST'
        pdu = PDU()
        pdu.formats = ['a']
        assert pdu != PDU()


class TestPDU_A_ASSOC_RQ(object):
    """Test the A_ASSOCIATE_RQ class."""
    def test_property_setters(self):
        """Check the property setters are working correctly."""
        # pdu.application_context_name
        pdu = A_ASSOCIATE_RQ()
        item = ApplicationContextItem()
        pdu.variable_items = [item]
        assert pdu.application_context_name == ''

    def test_string_output(self):
        """Check the string output works"""
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)
        assert "Verification SOP Class" in pdu.__str__()
        assert "Implicit VR Little Endian" in pdu.__str__()
        assert "3680043.9.3811.0.9.0" in pdu.__str__()

    def test_stream_decode_values_types(self):
        """ Check decoding the assoc_rq stream produces the correct objects """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)

        assert pdu.pdu_type == 0x01
        assert pdu.pdu_length == 209
        assert pdu.protocol_version == 0x0001
        assert isinstance(pdu.pdu_type, int)
        assert isinstance(pdu.pdu_length, int)
        assert isinstance(pdu.protocol_version, int)

        # Check VariableItems
        #   The actual items will be tested separately
        assert isinstance(pdu.variable_items[0], ApplicationContextItem)
        assert isinstance(pdu.variable_items[1], PresentationContextItemRQ)
        assert isinstance(pdu.variable_items[2], UserInformationItem)

    def test_decode_properties(self):
        """ Check decoding the assoc_rq stream produces the correct properties """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)

        # Check AE titles
        assert pdu.calling_ae_title.decode('utf-8') == 'ECHOSCU         '
        assert pdu.called_ae_title.decode('utf-8') == 'ANY-SCP         '
        assert isinstance(pdu.calling_ae_title, bytes)
        assert isinstance(pdu.called_ae_title, bytes)

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

    def test_stream_encode(self):
        """ Check encoding an assoc_rq produces the correct output """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)
        s = pdu.encode()

        assert s == a_associate_rq

    def test_to_primitive(self):
        """ Check converting PDU to primitive """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)

        primitive = pdu.ToParams()

        assert primitive.application_context_name == UID('1.2.840.10008.3.1.1.1')
        assert primitive.calling_ae_title == b'ECHOSCU         '
        assert primitive.called_ae_title == b'ANY-SCP         '

        # Test User Information
        for item in primitive.user_information:
            # Maximum PDU Length (required)
            if isinstance(item, MaximumLengthNegotiation):
                assert item.maximum_length_received == 16382
                assert isinstance(item.maximum_length_received, int)

            # Implementation Class UID (required)
            elif isinstance(item, ImplementationClassUIDNotification):
                assert item.implementation_class_uid == UID('1.2.826.0.1.3680043.9.3811.0.9.0')
                assert isinstance(item.implementation_class_uid, UID)

            # Implementation Version Name (optional)
            elif isinstance(item, ImplementationVersionNameNotification):
                assert item.implementation_version_name == b'PYNETDICOM_090'
                assert isinstance(item.implementation_version_name, bytes)

        # Test Presentation Contexts
        for context in primitive.presentation_context_definition_list:
            assert context.ID == 1
            assert context.AbstractSyntax == UID('1.2.840.10008.1.1')
            for syntax in context.TransferSyntax:
                assert syntax == UID('1.2.840.10008.1.2')

        assert isinstance(primitive.application_context_name, UID)
        assert isinstance(primitive.calling_ae_title, bytes)
        assert isinstance(primitive.called_ae_title, bytes)
        assert isinstance(primitive.user_information, list)
        assert isinstance(primitive.presentation_context_definition_list, list)

        # Not used by A-ASSOCIATE-RQ or fixed value
        assert primitive.mode == "normal"
        assert primitive.responding_ae_title == primitive.called_ae_title
        assert primitive.result is None
        assert primitive.result_source is None
        assert primitive.diagnostic is None
        assert primitive.calling_presentation_address is None
        assert primitive.called_presentation_address is None
        assert primitive.responding_presentation_address == primitive.called_presentation_address
        assert primitive.presentation_context_definition_results_list == []
        assert primitive.presentation_requirements == "Presentation Kernel"
        assert primitive.session_requirements == ""

    def test_from_primitive(self):
        """ Check converting PDU to primitive """
        orig_pdu = A_ASSOCIATE_RQ()
        orig_pdu.decode(a_associate_rq)

        primitive = orig_pdu.ToParams()

        new_pdu = A_ASSOCIATE_RQ()
        new_pdu.FromParams(primitive)

        assert new_pdu == orig_pdu

    def test_update_data(self):
        """ Check that updating the PDU data works correctly """
        orig_pdu = A_ASSOCIATE_RQ()
        orig_pdu.decode(a_associate_rq)
        orig_pdu.user_information.user_data = [orig_pdu.user_information.user_data[1]]

        primitive = orig_pdu.ToParams()

        new_pdu = A_ASSOCIATE_RQ()
        new_pdu.FromParams(primitive)

        assert new_pdu == orig_pdu


class TestPDU_A_ASSOC_RQ_ApplicationContext(object):
    def test_stream_decode_values_types(self):
        """ Check decoding an assoc_rq produces the correct application context """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)

        app_context = pdu.variable_items[0]

        assert app_context.item_type == 0x10
        assert app_context.item_length == 21
        assert app_context.application_context_name == '1.2.840.10008.3.1.1.1'
        assert isinstance(app_context.item_type, int)
        assert isinstance(app_context.item_length, int)
        assert isinstance(app_context.application_context_name, UID)

        assert app_context.application_context_name, '1.2.840.10008.3.1.1.1'
        assert isinstance(app_context.application_context_name, UID)


class TestPDU_A_ASSOC_RQ_PresentationContext(object):
    def test_stream_decode_values_types(self):
        """ Check decoding an assoc_rq produces the correct presentation context """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)

        # Check PresentationContextItemRQ attributes
        presentation_context = pdu.variable_items[1]
        assert presentation_context.item_type == 0x20
        assert presentation_context.presentation_context_id == 0x001
        assert presentation_context.item_length == 46
        assert isinstance(presentation_context.item_type, int)
        assert isinstance(presentation_context.presentation_context_id, int)
        assert isinstance(presentation_context.item_length, int)

    def test_decode_properties(self):
        """ Check decoding the stream produces the correct properties """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)

        context = pdu.presentation_context[0]

        # Check ID property
        context_id = context.context_id
        assert isinstance(context_id, int)
        assert context_id == 1

        # Check Abstract Syntax property
        context = pdu.presentation_context[0]
        assert isinstance(context.abstract_syntax, UID)
        assert context.abstract_syntax == UID('1.2.840.10008.1.1')

        # Check TransferSyntax property is a list
        assert isinstance(context.transfer_syntax, list)

        # Check TransferSyntax list contains transfer syntax type UIDs
        for syntax in pdu.presentation_context[0].transfer_syntax:
            assert isinstance(syntax, UID)
            assert syntax.is_transfer_syntax

        # Check first transfer syntax is little endian implicit
        syntax = pdu.presentation_context[0].transfer_syntax[0]
        assert syntax == UID('1.2.840.10008.1.2')


class TestPDU_A_ASSOC_RQ_PresentationContext_AbstractSyntax(object):
    def test_decode_value_type(self):
        """ Check decoding an assoc_rq produces the correct abstract syntax """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)

        context = pdu.presentation_context[0]

        abstract_syntax = context.abstract_transfer_syntax_sub_items[0]

        assert abstract_syntax.item_type == 0x30
        assert abstract_syntax.item_length == 17
        assert abstract_syntax.abstract_syntax_name == UID('1.2.840.10008.1.1')
        assert isinstance(abstract_syntax.item_type, int)
        assert isinstance(abstract_syntax.item_length, int)
        assert isinstance(abstract_syntax.abstract_syntax_name, UID)


class TestPDU_A_ASSOC_RQ_PresentationContext_TransferSyntax(object):
    def test_decode_value_type(self):
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
            assert syntax.is_transfer_syntax

        # Check first transfer syntax is little endian implicit
        syntax = transfer_syntaxes[0]
        assert syntax, UID('1.2.840.10008.1.2')


class TestPDU_A_ASSOC_RQ_UserInformation(object):
    def test_decode_value_type(self):
        """ Check decoding an assoc_rq produces the correct user information """
        pdu = A_ASSOCIATE_RQ()
        pdu.decode(a_associate_rq)

        user_info = pdu.variable_items[2]

        assert user_info.item_type == 0x50
        assert user_info.item_length == 62
        assert isinstance(user_info.item_type, int)
        assert isinstance(user_info.item_length, int)
        assert isinstance(user_info.user_data, list)

        # Test user items
        for item in user_info.user_data:
            # Maximum PDU Length (required)
            if isinstance(item, MaximumLengthSubItem):
                assert item.maximum_length_received == 16382
                assert user_info.maximum_length == 16382
                assert isinstance(item.maximum_length_received, int)
                assert isinstance(user_info.maximum_length, int)

            # Implementation Class UID (required)
            elif isinstance(item, ImplementationClassUIDSubItem):
                assert item.item_type == 0x52
                assert item.item_length == 32
                assert item.implementation_class_uid == UID('1.2.826.0.1.3680043.9.3811.0.9.0')
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


class TestPDU_A_ASSOC_AC(object):
    def test_property_setters(self):
        """Test the property setters"""
        # presentation_context
        pdu = A_ASSOCIATE_AC()
        pdu.decode(a_associate_ac)
        role_selection = SCP_SCU_RoleSelectionSubItem()
        role_selection.sop_class_uid = '1.2.840.10008.1.1'
        role_selection.scu_role = 1
        role_selection.scp_role = 1
        pdu.user_information.user_data.append(role_selection)
        context = pdu.presentation_context[0]
        assert context.transfer_syntax == '1.2.840.10008.1.2'

    def test_property_getters(self):
        """Test the property getters"""
        # called_ae_title
        pdu = A_ASSOCIATE_AC()
        pdu._reserved_aet = b'TESTA'
        assert pdu.called_ae_title == b'TESTA'
        assert isinstance(pdu.called_ae_title, bytes)
        pdu._reserved_aet = 'TESTB'
        assert pdu.called_ae_title == b'TESTB'
        assert isinstance(pdu.called_ae_title, bytes)

        # calling_ae_title
        pdu = A_ASSOCIATE_AC()
        pdu._reserved_aec = b'TESTA'
        assert pdu.calling_ae_title == b'TESTA'
        assert isinstance(pdu.calling_ae_title, bytes)
        pdu._reserved_aec = 'TESTB'
        assert pdu.calling_ae_title == b'TESTB'
        assert isinstance(pdu.calling_ae_title, bytes)

    def test_string_output(self):
        """Test the string output"""
        pdu = A_ASSOCIATE_AC()
        pdu.decode(a_associate_ac)
        assert "Implicit VR Little Endian" in pdu.__str__()
        assert "1.2.276.0.7230010" in pdu.__str__()

    def test_stream_decode_values_types(self):
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
        """ Check decoding the assoc_ac stream produces the correct properties """
        pdu = A_ASSOCIATE_AC()
        pdu.decode(a_associate_ac)

        # Check AE titles
        assert pdu._reserved_aec.decode('utf-8') == 'ECHOSCU         '
        assert pdu._reserved_aet.decode('utf-8') == 'ANY-SCP         '
        assert isinstance(pdu._reserved_aec, bytes)
        assert isinstance(pdu._reserved_aet, bytes)

        # Check application_context_name property
        app_name = pdu.application_context_name
        assert isinstance(app_name, UID)
        assert app_name == '1.2.840.10008.3.1.1.1'

        # Check presentation_context property
        contexts = pdu.presentation_context
        assert isinstance(contexts, list)
        for context in contexts:
            assert isinstance(context, PresentationContextItemAC)

        # Check user_information property
        user_info = pdu.user_information
        assert isinstance(user_info, UserInformationItem)

    def test_stream_encode(self):
        """ Check encoding an assoc_ac produces the correct output """
        pdu = A_ASSOCIATE_AC()
        pdu.decode(a_associate_ac)
        s = pdu.encode()

        assert s == a_associate_ac

    def test_to_primitive(self):
        """ Check converting PDU to primitive """
        pdu = A_ASSOCIATE_AC()
        pdu.decode(a_associate_ac)

        primitive = pdu.ToParams()

        assert primitive.application_context_name == UID('1.2.840.10008.3.1.1.1')
        assert primitive.calling_ae_title == b'ECHOSCU         '
        assert primitive.called_ae_title == b'ANY-SCP         '

        # Test User Information
        for item in primitive.user_information:
            # Maximum PDU Length (required)
            if isinstance(item, MaximumLengthNegotiation):
                assert item.maximum_length_received == 16384
                assert isinstance(item.maximum_length_received, int)

            # Implementation Class UID (required)
            elif isinstance(item, ImplementationClassUIDNotification):
                assert item.implementation_class_uid == UID('1.2.276.0.7230010.3.0.3.6.0')
                assert isinstance(item.implementation_class_uid, UID)

            # Implementation Version Name (optional)
            elif isinstance(item, ImplementationVersionNameNotification):
                assert item.implementation_version_name == b'OFFIS_DCMTK_360'
                assert isinstance(item.implementation_version_name, bytes)

        # Test Presentation Contexts
        for context in primitive.presentation_context_definition_list:
            assert context.ID == 1
            assert context.TransferSyntax[0] == UID('1.2.840.10008.1.2')

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
        assert primitive.responding_presentation_address == primitive.called_presentation_address
        assert primitive.presentation_context_definition_list == []
        assert primitive.presentation_requirements == "Presentation Kernel"
        assert primitive.session_requirements == ""

    def test_from_primitive(self):
        """ Check converting PDU to primitive """
        orig = A_ASSOCIATE_AC()
        orig.decode(a_associate_ac)

        primitive = orig.ToParams()

        new = A_ASSOCIATE_AC()
        new.FromParams(primitive)

        assert new == orig

    def test_update_data(self):
        """ Check that updating the PDU data works correctly """
        original = A_ASSOCIATE_AC()
        original.decode(a_associate_ac)
        original.user_information.user_data = [original.user_information.user_data[1]]

        primitive = original.ToParams()

        new = A_ASSOCIATE_AC()
        new.FromParams(primitive)

        assert original == new


class TestPDU_A_ASSOC_AC_ApplicationContext(object):
    def test_stream_decode_values_types(self):
        """ Check decoding an assoc_ac produces the correct application context """
        pdu = A_ASSOCIATE_AC()
        pdu.decode(a_associate_ac)

        app_context = pdu.variable_items[0]

        assert app_context.item_type == 0x10
        assert app_context.item_length == 21
        assert app_context.application_context_name == '1.2.840.10008.3.1.1.1'
        assert isinstance(app_context.item_type, int)
        assert isinstance(app_context.item_length, int)
        assert isinstance(app_context.application_context_name, UID)

        assert app_context.application_context_name == '1.2.840.10008.3.1.1.1'
        assert isinstance(app_context.application_context_name, UID)


class TestPDU_A_ASSOC_AC_PresentationContext(object):
    def test_stream_decode_values_types(self):
        """ Check decoding an assoc_ac produces the correct presentation context """
        pdu = A_ASSOCIATE_AC()
        pdu.decode(a_associate_ac)

        # Check PresentationContextItemRQ attributes
        presentation_context = pdu.variable_items[1]
        assert presentation_context.item_type == 0x21
        assert presentation_context.presentation_context_id == 0x0001
        assert presentation_context.item_length == 25
        assert presentation_context.result_reason == 0
        assert isinstance(presentation_context.item_type, int)
        assert isinstance(presentation_context.presentation_context_id, int)
        assert isinstance(presentation_context.item_length, int)

    def test_decode_properties(self):
        """ Check decoding the stream produces the correct properties """
        pdu = A_ASSOCIATE_AC()
        pdu.decode(a_associate_ac)

        context = pdu.presentation_context[0]

        # Check ID property
        context_id = context.context_id
        assert isinstance(context_id, int)
        assert context_id == 1

        # Check Result
        result = pdu.presentation_context[0].result_reason
        assert result == 0
        assert isinstance(result, int)

        # Check transfer syntax
        syntax = pdu.presentation_context[0].transfer_syntax
        assert syntax.is_transfer_syntax
        assert isinstance(syntax, UID)
        assert syntax == UID('1.2.840.10008.1.2')


class TestPDU_A_ASSOC_AC_PresentationContext_TransferSyntax(object):
    def test_decode_value_type(self):
        """ Check decoding an assoc_ac produces the correct transfer syntax """
        pdu = A_ASSOCIATE_AC()
        pdu.decode(a_associate_ac)

        context = pdu.presentation_context[0]
        syntax = context.transfer_syntax

        assert isinstance(syntax, UID)
        assert syntax.is_transfer_syntax
        assert syntax == UID('1.2.840.10008.1.2')


class TestPDU_A_ASSOC_AC_UserInformation(object):
    def test_decode_value_type(self):
        """ Check decoding an assoc_rq produces the correct user information """
        pdu = A_ASSOCIATE_AC()
        pdu.decode(a_associate_ac)

        user_info = pdu.variable_items[2]

        assert user_info.item_type == 0x50
        assert user_info.item_length == 58
        assert isinstance(user_info.item_type, int)
        assert isinstance(user_info.item_length, int)
        assert isinstance(user_info.user_data, list)

        # Test user items
        for item in user_info.user_data:
            # Maximum PDU Length (required)
            if isinstance(item, MaximumLengthSubItem):
                assert item.maximum_length_received == 16384
                assert user_info.maximum_length == 16384
                assert isinstance(item.maximum_length_received, int)
                assert isinstance(user_info.maximum_length, int)

            # Implementation Class UID (required)
            elif isinstance(item, ImplementationClassUIDSubItem):
                assert item.item_type == 0x52
                assert item.item_length == 27
                assert item.implementation_class_uid == UID('1.2.276.0.7230010.3.0.3.6.0')
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


class TestPDU_A_ASSOC_RJ(object):
    def test_string_output(self):
        """Test the string output"""
        pdu = A_ASSOCIATE_RJ()
        pdu.decode(a_associate_rj)
        assert "Rejected (Permanent)" in pdu.__str__()
        assert "DUL service-user" in pdu.__str__()

    def test_stream_decode_values_types(self):
        """ Check decoding the assoc_rj stream produces the correct objects """
        pdu = A_ASSOCIATE_RJ()
        pdu.decode(a_associate_rj)

        assert pdu.pdu_type == 0x03
        assert pdu.pdu_length == 4
        assert isinstance(pdu.pdu_type, int)
        assert isinstance(pdu.pdu_length, int)

    def test_decode_properties(self):
        """ Check decoding the assoc_rj stream produces the correct properties """
        pdu = A_ASSOCIATE_RJ()
        pdu.decode(a_associate_rj)

        # Check reason/source/result
        assert pdu.result ==1
        assert pdu.reason_diagnostic == 1
        assert pdu.source == 1
        assert isinstance(pdu.result, int)
        assert isinstance(pdu.reason_diagnostic, int)
        assert isinstance(pdu.source, int)

    def test_stream_encode(self):
        """ Check encoding an assoc_rj produces the correct output """
        pdu = A_ASSOCIATE_RJ()
        pdu.decode(a_associate_rj)
        s = pdu.encode()

        assert s == a_associate_rj

    def test_to_primitive(self):
        """ Check converting PDU to primitive """
        pdu = A_ASSOCIATE_RJ()
        pdu.decode(a_associate_rj)

        primitive = pdu.ToParams()

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
        assert primitive.responding_presentation_address == primitive.called_presentation_address
        assert primitive.presentation_context_definition_list == []
        assert primitive.presentation_context_definition_results_list == []
        assert primitive.presentation_requirements == "Presentation Kernel"
        assert primitive.session_requirements == ""

    def test_from_primitive(self):
        """ Check converting PDU to primitive """
        orig_pdu = A_ASSOCIATE_RJ()
        orig_pdu.decode(a_associate_rj)

        primitive = orig_pdu.ToParams()

        new_pdu = A_ASSOCIATE_RJ()
        new_pdu.FromParams(primitive)

        assert new_pdu == orig_pdu

    def test_update_data(self):
        """ Check that updating the PDU data works correctly """
        orig_pdu = A_ASSOCIATE_RJ()
        orig_pdu.decode(a_associate_rj)
        orig_pdu.source = 2
        orig_pdu.reason_diagnostic = 2
        orig_pdu.result = 2

        primitive = orig_pdu.ToParams()

        new_pdu = A_ASSOCIATE_RJ()
        new_pdu.FromParams(primitive)

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


class TestPDU_P_DATA_TF(object):
    def test_string_output(self):
        """Test the string output"""
        pdu = P_DATA_TF()
        pdu.decode(p_data_tf)
        assert "80 bytes" in pdu.__str__()
        assert "0x03 0x00" in pdu.__str__()

    def test_stream_decode_values_types(self):
        """ Check decoding the p_data stream produces the correct objects """
        pdu = P_DATA_TF()
        pdu.decode(p_data_tf)

        assert pdu.pdu_type == 0x04
        assert pdu.pdu_length == 84
        assert isinstance(pdu.pdu_type, int)
        assert isinstance(pdu.pdu_length, int)

    def test_decode_properties(self):
        """ Check decoding the p_data stream produces the correct properties """
        pdu = P_DATA_TF()
        pdu.decode(p_data_tf)

        # Check PDVs
        assert isinstance(pdu.presentation_data_value_items, list)
        assert len(pdu) == 90

    def test_stream_encode(self):
        """ Check encoding an p_data produces the correct output """
        pdu = P_DATA_TF()
        pdu.decode(p_data_tf)
        s = pdu.encode()

        assert s == p_data_tf

    def test_to_primitive(self):
        """ Check converting PDU to primitive """
        pdu = P_DATA_TF()
        pdu.decode(p_data_tf)

        primitive = pdu.ToParams()

        assert primitive.presentation_data_value_list == [[1, p_data_tf[11:]]]
        assert isinstance(primitive.presentation_data_value_list, list)

    def test_from_primitive(self):
        """ Check converting PDU to primitive """
        orig_pdu = P_DATA_TF()
        orig_pdu.decode(p_data_tf)
        primitive = orig_pdu.ToParams()

        new_pdu = P_DATA_TF()
        new_pdu.FromParams(primitive)
        pdv = new_pdu.presentation_data_value_items[0]

        assert new_pdu == orig_pdu


class TestPDU_A_RELEASE_RQ(object):
    def test_string_output(self):
        """Test the string output"""
        pdu = A_RELEASE_RQ()
        pdu.decode(a_release_rq)
        assert "0x05" in pdu.__str__()
        assert "4 bytes" in pdu.__str__()

    def test_stream_decode_values_types(self):
        """ Check decoding the release_rq stream produces the correct objects """
        pdu = A_RELEASE_RQ()
        pdu.decode(a_release_rq)

        assert pdu.pdu_type == 0x05
        assert pdu.pdu_length == 4
        assert len(pdu) == 10
        assert isinstance(pdu.pdu_type, int)
        assert isinstance(pdu.pdu_length, int)

    def test_stream_encode(self):
        """ Check encoding an release_rq produces the correct output """
        pdu = A_RELEASE_RQ()
        pdu.decode(a_release_rq)
        s = pdu.encode()

        assert s == a_release_rq

    def test_to_primitive(self):
        """ Check converting PDU to primitive """
        pdu = A_RELEASE_RQ()
        pdu.decode(a_release_rq)

        primitive = pdu.ToParams()

        assert primitive.reason == "normal"
        assert primitive.result is None

    def test_from_primitive(self):
        """ Check converting PDU to primitive """
        orig_pdu = A_RELEASE_RQ()
        orig_pdu.decode(a_release_rq)

        primitive = orig_pdu.ToParams()

        new_pdu = A_RELEASE_RQ()
        new_pdu.FromParams(primitive)

        assert new_pdu == orig_pdu


class TestPDU_A_RELEASE_RP(object):
    def test_string_output(self):
        """Test the string output"""
        pdu = A_RELEASE_RP()
        pdu.decode(a_release_rp)
        assert "0x06" in pdu.__str__()
        assert "4 bytes" in pdu.__str__()

    def test_stream_decode_values_types(self):
        """ Check decoding the release_rp stream produces the correct objects """
        pdu = A_RELEASE_RP()
        pdu.decode(a_release_rp)

        assert pdu.pdu_type == 0x06
        assert pdu.pdu_length == 4
        assert len(pdu) == 10
        assert isinstance(pdu.pdu_type, int)
        assert isinstance(pdu.pdu_length, int)

    def test_stream_encode(self):
        """ Check encoding an release_rp produces the correct output """
        pdu = A_RELEASE_RP()
        pdu.decode(a_release_rp)
        s = pdu.encode()

        assert s == a_release_rp

    def test_to_primitive(self):
        """ Check converting PDU to primitive """
        pdu = A_RELEASE_RP()
        pdu.decode(a_release_rp)

        primitive = pdu.ToParams()

        assert primitive.reason == "normal"
        assert primitive.result == "affirmative"

    def test_from_primitive(self):
        """ Check converting PDU to primitive """
        orig_pdu = A_RELEASE_RP()
        orig_pdu.decode(a_release_rp)

        primitive = orig_pdu.ToParams()

        new_pdu = A_RELEASE_RP()
        new_pdu.FromParams(primitive)

        assert new_pdu == orig_pdu


class TestPDU_A_ABORT(object):
    def test_string_output(self):
        """Test the string output"""
        pdu = A_ABORT_RQ()
        pdu.decode(a_abort)
        assert "0x07" in pdu.__str__()
        assert "4 bytes" in pdu.__str__()
        assert "DUL service-user" in pdu.__str__()

    def test_a_abort_stream_decode_values_types(self):
        """ Check decoding the a_abort stream produces the correct objects """
        pdu = A_ABORT_RQ()
        pdu.decode(a_abort)

        assert pdu.pdu_type == 0x07
        assert pdu.pdu_length == 4
        assert pdu.source == 0
        assert pdu.reason_diagnostic == 0
        assert len(pdu) == 10
        assert isinstance(pdu.pdu_type, int)
        assert isinstance(pdu.pdu_length, int)
        assert isinstance(pdu.source, int)
        assert isinstance(pdu.reason_diagnostic, int)

    def test_a_p_abort_stream_decode_values_types(self):
        """ Check decoding the a_abort stream produces the correct objects """
        pdu = A_ABORT_RQ()
        pdu.decode(a_p_abort)

        assert pdu.pdu_type == 0x07
        assert pdu.pdu_length == 4
        assert pdu.source == 2
        assert pdu.reason_diagnostic == 4
        assert isinstance(pdu.pdu_type, int)
        assert isinstance(pdu.pdu_length, int)
        assert isinstance(pdu.source, int)
        assert isinstance(pdu.reason_diagnostic, int)

    def test_a_abort_stream_encode(self):
        """ Check encoding an a_abort produces the correct output """
        pdu = A_ABORT_RQ()
        pdu.decode(a_abort)
        s = pdu.encode()

        assert s == a_abort

    def test_a_p_abort_stream_encode(self):
        """ Check encoding an a_abort produces the correct output """
        pdu = A_ABORT_RQ()
        pdu.decode(a_p_abort)
        s = pdu.encode()

        assert s == a_p_abort

    def test_to_a_abort_primitive(self):
        """ Check converting PDU to a_abort primitive """
        pdu = A_ABORT_RQ()
        pdu.decode(a_abort)

        primitive = pdu.ToParams()

        assert isinstance(primitive, A_ABORT)
        assert primitive.abort_source == 0

    def test_to_a_p_abort_primitive(self):
        """ Check converting PDU to a_p_abort primitive """
        pdu = A_ABORT_RQ()
        pdu.decode(a_p_abort)

        primitive = pdu.ToParams()

        assert isinstance(primitive, A_P_ABORT)
        assert primitive.provider_reason == 4

    def test_a_abort_from_primitive(self):
        """ Check converting PDU to primitive """
        orig_pdu = A_ABORT_RQ()
        orig_pdu.decode(a_abort)

        primitive = orig_pdu.ToParams()

        new_pdu = A_ABORT_RQ()
        new_pdu.FromParams(primitive)

        assert new_pdu == orig_pdu

    def test_a_p_abort_from_primitive(self):
        """ Check converting PDU to primitive """
        orig_pdu = A_ABORT_RQ()
        orig_pdu.decode(a_p_abort)

        primitive = orig_pdu.ToParams()

        new_pdu = A_ABORT_RQ()
        new_pdu.FromParams(primitive)

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
