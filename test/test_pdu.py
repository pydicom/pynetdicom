#!/usr/bin/env python

from io import BytesIO
import logging
import unittest

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
    PresentationContextItemAC, PresentationContextItemRQ, UserInformationItem
)
from pynetdicom3.pdu_primitives import (
    MaximumLengthNegotiation, ImplementationClassUIDNotification,
    ImplementationVersionNameNotification, A_P_ABORT, A_ABORT, A_ASSOCIATE,
    P_DATA
)
from .encoded_pdu_items import (
    a_associate_rq, a_associate_ac, a_associate_rj, a_release_rq, a_release_rq,
    a_release_rp, a_abort, a_p_abort, p_data_tf
)
#from pynetdicom3.utils import pretty_bytes

LOGGER = logging.getLogger('pynetdicom3')
LOGGER.setLevel(logging.CRITICAL)


class TestPDU(unittest.TestCase):
    def test_length_property(self):
        """ Check that the length property returns the correct value """
        pdu = A_ASSOCIATE_AC()
        pdu.Decode(a_associate_ac)

        self.assertEqual(pdu.length, pdu.get_length())

    def test_decode(self):
        """Check that encode raises not implemented"""
        pdu = A_ASSOCIATE_AC()
        with self.assertRaises(NotImplementedError):
            pdu.decode(a_associate_ac)


class TestPDU_NextItem(unittest.TestCase):
    def test_unknown_item_type(self):
        """ Check that an unknown item value raises ValueError """
        s = BytesIO(b'\x00\x02\x03\x04\x04')
        pdu = PDU()

        self.assertRaises(ValueError, pdu._next_item, s)

    def test_empty_stream(self):
        """ Check that an empty stream returns None """
        s = BytesIO(b'')
        pdu = PDU()

        item = pdu._next_item(s)

        self.assertTrue(item is None)

    def test_correct_item(self):
        """ Check that stream returns correct item type """
        pdu = PDU()

        item = pdu._next_item(BytesIO(b'\x01'))
        self.assertTrue(isinstance(item, A_ASSOCIATE_RQ))

        item = pdu._next_item(BytesIO(b'\x02'))
        self.assertTrue(isinstance(item, A_ASSOCIATE_AC))

        item = pdu._next_item(BytesIO(b'\x10'))
        self.assertTrue(isinstance(item, ApplicationContextItem))


class TestPDU_NextItemType(unittest.TestCase):
    def test_empty_stream(self):
        """ Check that an empty stream returns None """
        s = BytesIO(b'')
        pdu = PDU()

        item_type = pdu._next_item_type(s)
        self.assertTrue(item_type is None)

    def test_normal_stream(self):
        """ Check that a stream returns the value of the first byte  """
        s = BytesIO(b'\x01\x02\x03\x04\x04')
        pdu = PDU()

        item_type = pdu._next_item_type(s)
        self.assertTrue(item_type == 1)

    def test_return_type(self):
        """ Check stream returns the value of the first byte as an int """
        s = BytesIO(b'\x01\x02\x03\x04\x04')
        pdu = PDU()

        item_type = pdu._next_item_type(s)
        self.assertTrue(isinstance(item_type, int))


class TestPDU_Equality(unittest.TestCase):
    """Test the PDU equality/inequality operators."""
    def test_equality(self):
        """Test the equality operator"""
        self.assertTrue(PDU() == PDU())
        self.assertFalse(PDU() == 'TEST')
        pdu = PDU()
        pdu.formats = ['a']
        self.assertFalse(pdu == PDU())

    def test_inequality(self):
        """Test the inequality operator"""
        self.assertFalse(PDU() != PDU())
        self.assertTrue(PDU() != 'TEST')
        pdu = PDU()
        pdu.formats = ['a']
        self.assertTrue(pdu != PDU())


class TestPDU_A_ASSOC_RQ(unittest.TestCase):
    """Test the A_ASSOCIATE_RQ class."""
    def test_property_setters(self):
        """Check the property setters are working correctly."""
        # pdu.application_context_name
        pdu = A_ASSOCIATE_RQ()
        item = ApplicationContextItem()
        pdu.variable_items = [item]
        self.assertEqual(pdu.application_context_name, '')
        pdu.application_context_name = 'TEST'
        self.assertEqual(pdu.application_context_name, 'TEST')

        # pdu.presentation_context
        pdu = A_ASSOCIATE_RQ()
        pdu.Decode(a_associate_rq)
        role_selection = SCP_SCU_RoleSelectionSubItem()
        role_selection.sop_class_uid = '1.2.840.10008.1.1'
        role_selection.scu_role = 1
        role_selection.scp_role = 1
        pdu.user_information.user_data.append(role_selection)
        context = pdu.presentation_context[0]
        self.assertTrue(context.SCP == 1)
        self.assertTrue(context.SCU == 1)

    def test_string_output(self):
        """Check the string output works"""
        pdu = A_ASSOCIATE_RQ()
        pdu.Decode(a_associate_rq)
        self.assertTrue("Verification SOP Class" in pdu.__str__())
        self.assertTrue("Implicit VR Little Endian" in pdu.__str__())
        self.assertTrue("3680043.9.3811.0.9.0" in pdu.__str__())

    def test_stream_decode_values_types(self):
        """ Check decoding the assoc_rq stream produces the correct objects """
        pdu = A_ASSOCIATE_RQ()
        pdu.Decode(a_associate_rq)

        self.assertEqual(pdu.pdu_type, 0x01)
        self.assertEqual(pdu.pdu_length, 209)
        self.assertEqual(pdu.protocol_version, 0x0001)
        self.assertTrue(isinstance(pdu.pdu_type, int))
        self.assertTrue(isinstance(pdu.pdu_length, int))
        self.assertTrue(isinstance(pdu.protocol_version, int))

        # Check VariableItems
        #   The actual items will be tested separately
        self.assertTrue(isinstance(pdu.variable_items[0], ApplicationContextItem))
        self.assertTrue(isinstance(pdu.variable_items[1], PresentationContextItemRQ))
        self.assertTrue(isinstance(pdu.variable_items[2], UserInformationItem))

    def test_decode_properties(self):
        """ Check decoding the assoc_rq stream produces the correct properties """
        pdu = A_ASSOCIATE_RQ()
        pdu.Decode(a_associate_rq)

        # Check AE titles
        self.assertEqual(pdu.calling_ae_title.decode('utf-8'), 'ECHOSCU         ')
        self.assertEqual(pdu.called_ae_title.decode('utf-8'), 'ANY-SCP         ')
        self.assertTrue(isinstance(pdu.calling_ae_title, bytes))
        self.assertTrue(isinstance(pdu.called_ae_title, bytes))

        # Check application_context_name property
        app_name = pdu.application_context_name
        self.assertTrue(isinstance(app_name, UID))
        self.assertEqual(app_name, '1.2.840.10008.3.1.1.1')

        # Check presentation_context property
        contexts = pdu.presentation_context
        self.assertTrue(isinstance(contexts, list))
        for context in contexts:
            self.assertTrue(isinstance(context, PresentationContextItemRQ))

        # Check user_information property
        user_info = pdu.user_information
        self.assertTrue(isinstance(user_info, UserInformationItem))

    def test_new_encode(self):
        """ Check encoding using new generic method """
        pdu = A_ASSOCIATE_RQ()
        pdu.Decode(a_associate_rq)
        s = pdu.encode()

        self.assertEqual(s, a_associate_rq)

    def test_stream_encode(self):
        """ Check encoding an assoc_rq produces the correct output """
        pdu = A_ASSOCIATE_RQ()
        pdu.Decode(a_associate_rq)
        s = pdu.Encode()

        self.assertEqual(s, a_associate_rq)

    def test_to_primitive(self):
        """ Check converting PDU to primitive """
        pdu = A_ASSOCIATE_RQ()
        pdu.Decode(a_associate_rq)

        primitive = pdu.ToParams()

        self.assertEqual(primitive.application_context_name, UID('1.2.840.10008.3.1.1.1'))
        self.assertEqual(primitive.calling_ae_title, b'ECHOSCU         ')
        self.assertEqual(primitive.called_ae_title, b'ANY-SCP         ')

        # Test User Information
        for item in primitive.user_information:
            # Maximum PDU Length (required)
            if isinstance(item, MaximumLengthNegotiation):
                self.assertEqual(item.maximum_length_received, 16382)
                self.assertTrue(isinstance(item.maximum_length_received, int))

            # Implementation Class UID (required)
            elif isinstance(item, ImplementationClassUIDNotification):
                self.assertEqual(item.implementation_class_uid, UID('1.2.826.0.1.3680043.9.3811.0.9.0'))
                self.assertTrue(isinstance(item.implementation_class_uid, UID))

            # Implementation Version Name (optional)
            elif isinstance(item, ImplementationVersionNameNotification):
                self.assertEqual(item.implementation_version_name, b'PYNETDICOM_090')
                self.assertTrue(isinstance(item.implementation_version_name, bytes))

        # Test Presentation Contexts
        for context in primitive.presentation_context_definition_list:
            self.assertEqual(context.ID, 1)
            self.assertEqual(context.AbstractSyntax, UID('1.2.840.10008.1.1'))
            for syntax in context.TransferSyntax:
                self.assertEqual(syntax, UID('1.2.840.10008.1.2'))

        self.assertTrue(isinstance(primitive.application_context_name, UID))
        self.assertTrue(isinstance(primitive.calling_ae_title, bytes))
        self.assertTrue(isinstance(primitive.called_ae_title, bytes))
        self.assertTrue(isinstance(primitive.user_information, list))
        self.assertTrue(isinstance(primitive.presentation_context_definition_list, list))

        # Not used by A-ASSOCIATE-RQ or fixed value
        self.assertEqual(primitive.mode, "normal")
        self.assertEqual(primitive.responding_ae_title, primitive.called_ae_title)
        self.assertEqual(primitive.result, None)
        self.assertEqual(primitive.result_source, None)
        self.assertEqual(primitive.diagnostic, None)
        self.assertEqual(primitive.calling_presentation_address, None)
        self.assertEqual(primitive.called_presentation_address, None)
        self.assertEqual(primitive.responding_presentation_address, primitive.called_presentation_address)
        self.assertEqual(primitive.presentation_context_definition_results_list, [])
        self.assertEqual(primitive.presentation_requirements, "Presentation Kernel")
        self.assertEqual(primitive.session_requirements, "")

    def test_from_primitive(self):
        """ Check converting PDU to primitive """
        orig_pdu = A_ASSOCIATE_RQ()
        orig_pdu.Decode(a_associate_rq)

        primitive = orig_pdu.ToParams()

        new_pdu = A_ASSOCIATE_RQ()
        new_pdu.FromParams(primitive)

        self.assertEqual(new_pdu, orig_pdu)

    def test_update_data(self):
        """ Check that updating the PDU data works correctly """
        orig_pdu = A_ASSOCIATE_RQ()
        orig_pdu.Decode(a_associate_rq)
        orig_pdu.user_information.user_data = [orig_pdu.user_information.user_data[1]]
        orig_pdu.get_length()

        primitive = orig_pdu.ToParams()

        new_pdu = A_ASSOCIATE_RQ()
        new_pdu.FromParams(primitive)

        self.assertEqual(new_pdu, orig_pdu)

    def test_generic_encode(self):
        """ Check using the new pdu.encode produces the correct output """
        pdu = A_ASSOCIATE_RQ()
        pdu.Decode(a_associate_rq)
        s = pdu.Encode()
        t = pdu.encode()

        self.assertEqual(s, t)


class TestPDU_A_ASSOC_RQ_ApplicationContext(unittest.TestCase):
    def test_stream_decode_values_types(self):
        """ Check decoding an assoc_rq produces the correct application context """
        pdu = A_ASSOCIATE_RQ()
        pdu.Decode(a_associate_rq)

        app_context = pdu.variable_items[0]

        self.assertEqual(app_context.item_type, 0x10)
        self.assertEqual(app_context.item_length, 21)
        self.assertEqual(app_context.application_context_name, '1.2.840.10008.3.1.1.1')
        self.assertTrue(isinstance(app_context.item_type, int))
        self.assertTrue(isinstance(app_context.item_length, int))
        self.assertTrue(isinstance(app_context.application_context_name, UID))

        self.assertEqual(app_context.application_context_name, '1.2.840.10008.3.1.1.1')
        self.assertTrue(isinstance(app_context.application_context_name, UID))


class TestPDU_A_ASSOC_RQ_PresentationContext(unittest.TestCase):
    def test_stream_decode_values_types(self):
        """ Check decoding an assoc_rq produces the correct presentation context """
        pdu = A_ASSOCIATE_RQ()
        pdu.Decode(a_associate_rq)

        # Check PresentationContextItemRQ attributes
        presentation_context = pdu.variable_items[1]
        self.assertEqual(presentation_context.item_type, 0x20)
        self.assertEqual(presentation_context.presentation_context_id, 0x001)
        self.assertEqual(presentation_context.item_length, 46)
        self.assertTrue(isinstance(presentation_context.item_type, int))
        self.assertTrue(isinstance(presentation_context.presentation_context_id, int))
        self.assertTrue(isinstance(presentation_context.item_length, int))

    def test_decode_properties(self):
        """ Check decoding the stream produces the correct properties """
        pdu = A_ASSOCIATE_RQ()
        pdu.Decode(a_associate_rq)

        context = pdu.presentation_context[0]

        # Check ID property
        context_id = context.ID
        self.assertTrue(isinstance(context_id, int))
        self.assertEqual(context_id, 1)

        # Check Abstract Syntax property
        context = pdu.presentation_context[0]
        self.assertTrue(isinstance(context.abstract_syntax, UID))
        self.assertEqual(context.abstract_syntax, UID('1.2.840.10008.1.1'))

        # Check TransferSyntax property is a list
        self.assertTrue(isinstance(context.transfer_syntax, list))

        # Check TransferSyntax list contains transfer syntax type UIDs
        for syntax in pdu.presentation_context[0].transfer_syntax:
            self.assertTrue(isinstance(syntax, UID))
            self.assertTrue(syntax.is_transfer_syntax)

        # Check first transfer syntax is little endian implicit
        syntax = pdu.presentation_context[0].transfer_syntax[0]
        self.assertEqual(syntax, UID('1.2.840.10008.1.2'))


class TestPDU_A_ASSOC_RQ_PresentationContext_AbstractSyntax(unittest.TestCase):
    def test_decode_value_type(self):
        """ Check decoding an assoc_rq produces the correct abstract syntax """
        pdu = A_ASSOCIATE_RQ()
        pdu.Decode(a_associate_rq)

        context = pdu.presentation_context[0]

        abstract_syntax = context.abstract_transfer_syntax_sub_items[0]

        self.assertEqual(abstract_syntax.item_type, 0x30)
        self.assertEqual(abstract_syntax.item_length, 17)
        self.assertEqual(abstract_syntax.abstract_syntax_name, UID('1.2.840.10008.1.1'))
        self.assertTrue(isinstance(abstract_syntax.item_type, int))
        self.assertTrue(isinstance(abstract_syntax.item_length, int))
        self.assertTrue(isinstance(abstract_syntax.abstract_syntax_name, UID))


class TestPDU_A_ASSOC_RQ_PresentationContext_TransferSyntax(unittest.TestCase):
    def test_decode_value_type(self):
        """ Check decoding an assoc_rq produces the correct transfer syntax """
        pdu = A_ASSOCIATE_RQ()
        pdu.Decode(a_associate_rq)

        context = pdu.presentation_context[0]
        transfer_syntaxes = context.transfer_syntax

        # Check TransferSyntax property is a list
        self.assertTrue(isinstance(transfer_syntaxes, list))

        # Check TransferSyntax list contains transfer syntax type UIDs
        for syntax in transfer_syntaxes:
            self.assertTrue(isinstance(syntax, UID))
            self.assertTrue(syntax.is_transfer_syntax)

        # Check first transfer syntax is little endian implicit
        syntax = transfer_syntaxes[0]
        self.assertEqual(syntax, UID('1.2.840.10008.1.2'))


class TestPDU_A_ASSOC_RQ_UserInformation(unittest.TestCase):
    def test_decode_value_type(self):
        """ Check decoding an assoc_rq produces the correct user information """
        pdu = A_ASSOCIATE_RQ()
        pdu.Decode(a_associate_rq)

        user_info = pdu.variable_items[2]

        self.assertEqual(user_info.item_type, 0x50)
        self.assertEqual(user_info.item_length, 62)
        self.assertTrue(isinstance(user_info.item_type, int))
        self.assertTrue(isinstance(user_info.item_length, int))
        self.assertTrue(isinstance(user_info.user_data, list))

        # Test user items
        for item in user_info.user_data:
            # Maximum PDU Length (required)
            if isinstance(item, MaximumLengthSubItem):
                self.assertEqual(item.maximum_length_received, 16382)
                self.assertEqual(user_info.maximum_length, 16382)
                self.assertTrue(isinstance(item.maximum_length_received, int))
                self.assertTrue(isinstance(user_info.maximum_length, int))

            # Implementation Class UID (required)
            elif isinstance(item, ImplementationClassUIDSubItem):
                self.assertEqual(item.item_type, 0x52)
                self.assertEqual(item.item_length, 32)
                self.assertEqual(item.implementation_class_uid, UID('1.2.826.0.1.3680043.9.3811.0.9.0'))
                self.assertTrue(isinstance(item.item_type, int))
                self.assertTrue(isinstance(item.item_length, int))
                self.assertTrue(isinstance(item.implementation_class_uid, UID))

            # Implementation Version Name (optional)
            elif isinstance(item, ImplementationVersionNameSubItem):
                self.assertEqual(item.item_type, 0x55)
                self.assertEqual(item.item_length, 14)
                self.assertEqual(item.implementation_version_name, b'PYNETDICOM_090')
                self.assertTrue(isinstance(item.item_type, int))
                self.assertTrue(isinstance(item.item_length, int))
                self.assertTrue(isinstance(item.implementation_version_name, bytes))


class TestPDU_A_ASSOC_AC(unittest.TestCase):
    def test_property_setters(self):
        """Test the property setters"""
        # presentation_context
        pdu = A_ASSOCIATE_AC()
        pdu.Decode(a_associate_ac)
        role_selection = SCP_SCU_RoleSelectionSubItem()
        role_selection.sop_class_uid = '1.2.840.10008.1.1'
        role_selection.scu_role = 1
        role_selection.scp_role = 1
        pdu.user_information.user_data.append(role_selection)
        context = pdu.presentation_context[0]
        self.assertTrue(context.transfer_syntax == '1.2.840.10008.1.2')

    def test_property_getters(self):
        """Test the property getters"""
        # called_ae_title
        pdu = A_ASSOCIATE_AC()
        pdu.reserved_aet = b'TESTA'
        self.assertEqual(pdu.called_ae_title, b'TESTA')
        self.assertTrue(isinstance(pdu.called_ae_title, bytes))
        pdu.reserved_aet = 'TESTB'
        self.assertEqual(pdu.called_ae_title, b'TESTB')
        self.assertTrue(isinstance(pdu.called_ae_title, bytes))

        # calling_ae_title
        pdu = A_ASSOCIATE_AC()
        pdu.reserved_aec = b'TESTA'
        self.assertEqual(pdu.calling_ae_title, b'TESTA')
        self.assertTrue(isinstance(pdu.calling_ae_title, bytes))
        pdu.reserved_aec = 'TESTB'
        self.assertEqual(pdu.calling_ae_title, b'TESTB')
        self.assertTrue(isinstance(pdu.calling_ae_title, bytes))

    def test_string_output(self):
        """Test the string output"""
        pdu = A_ASSOCIATE_AC()
        pdu.Decode(a_associate_ac)
        self.assertTrue("Implicit VR Little Endian" in pdu.__str__())
        self.assertTrue("1.2.276.0.7230010" in pdu.__str__())


    def test_stream_decode_values_types(self):
        """ Check decoding the assoc_ac stream produces the correct objects """
        pdu = A_ASSOCIATE_AC()
        pdu.Decode(a_associate_ac)

        self.assertEqual(pdu.pdu_type, 0x02)
        self.assertEqual(pdu.pdu_length, 184)
        self.assertEqual(pdu.protocol_version, 0x0001)
        self.assertTrue(isinstance(pdu.pdu_type, int))
        self.assertTrue(isinstance(pdu.pdu_length, int))
        self.assertTrue(isinstance(pdu.protocol_version, int))

        # Check VariableItems
        #   The actual items will be tested separately
        self.assertTrue(isinstance(pdu.variable_items[0], ApplicationContextItem))
        self.assertTrue(isinstance(pdu.variable_items[1], PresentationContextItemAC))
        self.assertTrue(isinstance(pdu.variable_items[2], UserInformationItem))

    def test_decode_properties(self):
        """ Check decoding the assoc_ac stream produces the correct properties """
        pdu = A_ASSOCIATE_AC()
        pdu.Decode(a_associate_ac)

        # Check AE titles
        self.assertEqual(pdu.reserved_aec.decode('utf-8'), 'ECHOSCU         ')
        self.assertEqual(pdu.reserved_aet.decode('utf-8'), 'ANY-SCP         ')
        self.assertTrue(isinstance(pdu.reserved_aec, bytes))
        self.assertTrue(isinstance(pdu.reserved_aet, bytes))

        # Check application_context_name property
        app_name = pdu.application_context_name
        self.assertTrue(isinstance(app_name, UID))
        self.assertEqual(app_name, '1.2.840.10008.3.1.1.1')

        # Check presentation_context property
        contexts = pdu.presentation_context
        self.assertTrue(isinstance(contexts, list))
        for context in contexts:
            self.assertTrue(isinstance(context, PresentationContextItemAC))

        # Check user_information property
        user_info = pdu.user_information
        self.assertTrue(isinstance(user_info, UserInformationItem))

    def test_stream_encode(self):
        """ Check encoding an assoc_ac produces the correct output """
        pdu = A_ASSOCIATE_AC()
        pdu.Decode(a_associate_ac)
        s = pdu.Encode()

        self.assertEqual(s, a_associate_ac)

    def test_new_encode(self):
        """ Check encoding using new generic method """
        pdu = A_ASSOCIATE_AC()
        pdu.Decode(a_associate_ac)
        s = pdu.encode()

        self.assertEqual(s, a_associate_ac)

    def test_to_primitive(self):
        """ Check converting PDU to primitive """
        pdu = A_ASSOCIATE_AC()
        pdu.Decode(a_associate_ac)

        primitive = pdu.ToParams()

        self.assertEqual(primitive.application_context_name, UID('1.2.840.10008.3.1.1.1'))
        self.assertEqual(primitive.calling_ae_title, b'ECHOSCU         ')
        self.assertEqual(primitive.called_ae_title, b'ANY-SCP         ')

        # Test User Information
        for item in primitive.user_information:
            # Maximum PDU Length (required)
            if isinstance(item, MaximumLengthNegotiation):
                self.assertEqual(item.maximum_length_received, 16384)
                self.assertTrue(isinstance(item.maximum_length_received, int))

            # Implementation Class UID (required)
            elif isinstance(item, ImplementationClassUIDNotification):
                self.assertEqual(item.implementation_class_uid, UID('1.2.276.0.7230010.3.0.3.6.0'))
                self.assertTrue(isinstance(item.implementation_class_uid, UID))

            # Implementation Version Name (optional)
            elif isinstance(item, ImplementationVersionNameNotification):
                self.assertEqual(item.implementation_version_name, b'OFFIS_DCMTK_360')
                self.assertTrue(isinstance(item.implementation_version_name, bytes))

        # Test Presentation Contexts
        for context in primitive.presentation_context_definition_list:
            self.assertEqual(context.ID, 1)
            self.assertEqual(context.TransferSyntax[0], UID('1.2.840.10008.1.2'))

        self.assertTrue(isinstance(primitive.application_context_name, UID))
        self.assertTrue(isinstance(primitive.calling_ae_title, bytes))
        self.assertTrue(isinstance(primitive.called_ae_title, bytes))
        self.assertTrue(isinstance(primitive.user_information, list))

        self.assertEqual(primitive.result, 0)
        self.assertEqual(len(primitive.presentation_context_definition_results_list), 1)

        # Not used by A-ASSOCIATE-AC or fixed value
        self.assertEqual(primitive.mode, "normal")
        self.assertEqual(primitive.responding_ae_title, primitive.called_ae_title)
        self.assertEqual(primitive.result_source, None)
        self.assertEqual(primitive.diagnostic, None)
        self.assertEqual(primitive.calling_presentation_address, None)
        self.assertEqual(primitive.called_presentation_address, None)
        self.assertEqual(primitive.responding_presentation_address, primitive.called_presentation_address)
        self.assertEqual(primitive.presentation_context_definition_list, [])
        self.assertEqual(primitive.presentation_requirements, "Presentation Kernel")
        self.assertEqual(primitive.session_requirements, "")

    def test_from_primitive(self):
        """ Check converting PDU to primitive """
        orig = A_ASSOCIATE_AC()
        orig.Decode(a_associate_ac)

        primitive = orig.ToParams()

        new = A_ASSOCIATE_AC()
        new.FromParams(primitive)

        self.assertEqual(new, orig)

    def test_update_data(self):
        """ Check that updating the PDU data works correctly """
        original = A_ASSOCIATE_AC()
        original.Decode(a_associate_ac)
        original.user_information.user_data = [original.user_information.user_data[1]]
        original.get_length()

        primitive = original.ToParams()

        new = A_ASSOCIATE_AC()
        new.FromParams(primitive)

        self.assertEqual(original, new)

    def test_generic_encode(self):
        """ Check using the new pdu.encode produces the correct output """
        pdu = A_ASSOCIATE_AC()
        pdu.Decode(a_associate_ac)
        s = pdu.Encode()
        t = pdu.encode()

        self.assertEqual(s, t)


class TestPDU_A_ASSOC_AC_ApplicationContext(unittest.TestCase):
    def test_stream_decode_values_types(self):
        """ Check decoding an assoc_ac produces the correct application context """
        pdu = A_ASSOCIATE_AC()
        pdu.Decode(a_associate_ac)

        app_context = pdu.variable_items[0]

        self.assertEqual(app_context.item_type, 0x10)
        self.assertEqual(app_context.item_length, 21)
        self.assertEqual(app_context.application_context_name, '1.2.840.10008.3.1.1.1')
        self.assertTrue(isinstance(app_context.item_type, int))
        self.assertTrue(isinstance(app_context.item_length, int))
        self.assertTrue(isinstance(app_context.application_context_name, UID))

        self.assertEqual(app_context.application_context_name, '1.2.840.10008.3.1.1.1')
        self.assertTrue(isinstance(app_context.application_context_name, UID))


class TestPDU_A_ASSOC_AC_PresentationContext(unittest.TestCase):
    def test_stream_decode_values_types(self):
        """ Check decoding an assoc_ac produces the correct presentation context """
        pdu = A_ASSOCIATE_AC()
        pdu.Decode(a_associate_ac)

        # Check PresentationContextItemRQ attributes
        presentation_context = pdu.variable_items[1]
        self.assertEqual(presentation_context.item_type, 0x21)
        self.assertEqual(presentation_context.presentation_context_id, 0x0001)
        self.assertEqual(presentation_context.item_length, 25)
        self.assertEqual(presentation_context.result_reason, 0)
        self.assertTrue(isinstance(presentation_context.item_type, int))
        self.assertTrue(isinstance(presentation_context.presentation_context_id, int))
        self.assertTrue(isinstance(presentation_context.item_length, int))

    def test_decode_properties(self):
        """ Check decoding the stream produces the correct properties """
        pdu = A_ASSOCIATE_AC()
        pdu.Decode(a_associate_ac)

        context = pdu.presentation_context[0]

        # Check ID property
        context_id = context.ID
        self.assertTrue(isinstance(context_id, int))
        self.assertEqual(context_id, 1)

        # Check Result
        result = pdu.presentation_context[0].result_reason
        self.assertEqual(result, 0)
        self.assertTrue(isinstance(result, int))

        # Check transfer syntax
        syntax = pdu.presentation_context[0].transfer_syntax
        self.assertTrue(syntax.is_transfer_syntax)
        self.assertTrue(isinstance(syntax, UID))
        self.assertEqual(syntax, UID('1.2.840.10008.1.2'))


class TestPDU_A_ASSOC_AC_PresentationContext_TransferSyntax(unittest.TestCase):
    def test_decode_value_type(self):
        """ Check decoding an assoc_ac produces the correct transfer syntax """
        pdu = A_ASSOCIATE_AC()
        pdu.Decode(a_associate_ac)

        context = pdu.presentation_context[0]
        syntax = context.transfer_syntax

        self.assertTrue(isinstance(syntax, UID))
        self.assertTrue(syntax.is_transfer_syntax)
        self.assertEqual(syntax, UID('1.2.840.10008.1.2'))


class TestPDU_A_ASSOC_AC_UserInformation(unittest.TestCase):
    def test_decode_value_type(self):
        """ Check decoding an assoc_rq produces the correct user information """
        pdu = A_ASSOCIATE_AC()
        pdu.Decode(a_associate_ac)

        user_info = pdu.variable_items[2]

        self.assertEqual(user_info.item_type, 0x50)
        self.assertEqual(user_info.item_length, 58)
        self.assertTrue(isinstance(user_info.item_type, int))
        self.assertTrue(isinstance(user_info.item_length, int))
        self.assertTrue(isinstance(user_info.user_data, list))

        # Test user items
        for item in user_info.user_data:
            # Maximum PDU Length (required)
            if isinstance(item, MaximumLengthSubItem):
                self.assertEqual(item.maximum_length_received, 16384)
                self.assertEqual(user_info.maximum_length, 16384)
                self.assertTrue(isinstance(item.maximum_length_received, int))
                self.assertTrue(isinstance(user_info.maximum_length, int))

            # Implementation Class UID (required)
            elif isinstance(item, ImplementationClassUIDSubItem):
                self.assertEqual(item.item_type, 0x52)
                self.assertEqual(item.item_length, 27)
                self.assertEqual(item.implementation_class_uid, UID('1.2.276.0.7230010.3.0.3.6.0'))
                self.assertTrue(isinstance(item.item_type, int))
                self.assertTrue(isinstance(item.item_length, int))
                self.assertTrue(isinstance(item.implementation_class_uid, UID))

            # Implementation Version Name (optional)
            elif isinstance(item, ImplementationVersionNameSubItem):
                self.assertEqual(item.item_type, 0x55)
                self.assertEqual(item.item_length, 15)
                self.assertEqual(item.implementation_version_name, b'OFFIS_DCMTK_360')
                self.assertTrue(isinstance(item.item_type, int))
                self.assertTrue(isinstance(item.item_length, int))
                self.assertTrue(isinstance(item.implementation_version_name, bytes))


class TestPDU_A_ASSOC_RJ(unittest.TestCase):
    def test_string_output(self):
        """Test the string output"""
        pdu = A_ASSOCIATE_RJ()
        pdu.Decode(a_associate_rj)
        self.assertTrue("Rejected (Permanent)" in pdu.__str__())
        self.assertTrue("DUL service-user" in pdu.__str__())

    def test_stream_decode_values_types(self):
        """ Check decoding the assoc_rj stream produces the correct objects """
        pdu = A_ASSOCIATE_RJ()
        pdu.Decode(a_associate_rj)

        self.assertEqual(pdu.pdu_type, 0x03)
        self.assertEqual(pdu.pdu_length, 4)
        self.assertTrue(isinstance(pdu.pdu_type, int))
        self.assertTrue(isinstance(pdu.pdu_length, int))

    def test_decode_properties(self):
        """ Check decoding the assoc_rj stream produces the correct properties """
        pdu = A_ASSOCIATE_RJ()
        pdu.Decode(a_associate_rj)

        # Check reason/source/result
        self.assertEqual(pdu.result, 1)
        self.assertEqual(pdu.reason_diagnostic, 1)
        self.assertEqual(pdu.source, 1)
        self.assertTrue(isinstance(pdu.result, int))
        self.assertTrue(isinstance(pdu.reason_diagnostic, int))
        self.assertTrue(isinstance(pdu.source, int))

    def test_stream_encode(self):
        """ Check encoding an assoc_rj produces the correct output """
        pdu = A_ASSOCIATE_RJ()
        pdu.Decode(a_associate_rj)
        s = pdu.Encode()

        self.assertEqual(s, a_associate_rj)

    def test_new_encode(self):
        """ Check encoding using new generic method """
        pdu = A_ASSOCIATE_RJ()
        pdu.Decode(a_associate_rj)
        s = pdu.encode()

        self.assertEqual(s, a_associate_rj)

    def test_to_primitive(self):
        """ Check converting PDU to primitive """
        pdu = A_ASSOCIATE_RJ()
        pdu.Decode(a_associate_rj)

        primitive = pdu.ToParams()

        self.assertEqual(primitive.result, 1)
        self.assertEqual(primitive.result_source, 1)
        self.assertEqual(primitive.diagnostic, 1)
        self.assertTrue(isinstance(primitive.result, int))
        self.assertTrue(isinstance(primitive.result_source, int))
        self.assertTrue(isinstance(primitive.diagnostic, int))

        # Not used by A-ASSOCIATE-RJ or fixed value
        self.assertEqual(primitive.mode, "normal")
        self.assertEqual(primitive.application_context_name, None)
        self.assertEqual(primitive.calling_ae_title, None)
        self.assertEqual(primitive.called_ae_title, None)
        self.assertEqual(primitive.responding_ae_title, None)
        self.assertEqual(primitive.user_information, [])
        self.assertEqual(primitive.calling_presentation_address, None)
        self.assertEqual(primitive.called_presentation_address, None)
        self.assertEqual(primitive.responding_presentation_address, primitive.called_presentation_address)
        self.assertEqual(primitive.presentation_context_definition_list, [])
        self.assertEqual(primitive.presentation_context_definition_results_list, [])
        self.assertEqual(primitive.presentation_requirements, "Presentation Kernel")
        self.assertEqual(primitive.session_requirements, "")

    def test_from_primitive(self):
        """ Check converting PDU to primitive """
        orig_pdu = A_ASSOCIATE_RJ()
        orig_pdu.Decode(a_associate_rj)

        primitive = orig_pdu.ToParams()

        new_pdu = A_ASSOCIATE_RJ()
        new_pdu.FromParams(primitive)

        self.assertEqual(new_pdu, orig_pdu)

    def test_update_data(self):
        """ Check that updating the PDU data works correctly """
        orig_pdu = A_ASSOCIATE_RJ()
        orig_pdu.Decode(a_associate_rj)
        orig_pdu.source = 2
        orig_pdu.reason_diagnostic = 2
        orig_pdu.result = 2
        orig_pdu.get_length()

        primitive = orig_pdu.ToParams()

        new_pdu = A_ASSOCIATE_RJ()
        new_pdu.FromParams(primitive)

        self.assertEqual(new_pdu, orig_pdu)

    def test_result_str(self):
        """ Check the result str returns correct values """
        pdu = A_ASSOCIATE_RJ()
        pdu.Decode(a_associate_rj)

        pdu.result = 0
        with self.assertRaises(ValueError): pdu.result_str

        pdu.result = 1
        self.assertEqual(pdu.result_str, 'Rejected (Permanent)')

        pdu.result = 2
        self.assertEqual(pdu.result_str, 'Rejected (Transient)')

        pdu.result = 3
        with self.assertRaises(ValueError): pdu.result_str

    def test_source_str(self):
        """ Check the source str returns correct values """
        pdu = A_ASSOCIATE_RJ()
        pdu.Decode(a_associate_rj)

        pdu.source = 0
        with self.assertRaises(ValueError): pdu.source_str

        pdu.source = 1
        self.assertEqual(pdu.source_str, 'DUL service-user')

        pdu.source = 2
        self.assertEqual(pdu.source_str, 'DUL service-provider (ACSE related)')

        pdu.source = 3
        self.assertEqual(pdu.source_str, 'DUL service-provider (presentation related)')

        pdu.source = 4
        with self.assertRaises(ValueError): pdu.source_str

    def test_reason_str(self):
        """ Check the reason str returns correct values """
        pdu = A_ASSOCIATE_RJ()
        pdu.Decode(a_associate_rj)

        pdu.source = 0
        with self.assertRaises(ValueError): pdu.reason_str

        pdu.source = 1
        for ii in range(1, 11):
            pdu.reason_diagnostic = ii
            self.assertTrue(isinstance(pdu.reason_str, str))

        pdu.reason_diagnostic = 11
        with self.assertRaises(ValueError): pdu.reason_str

        pdu.source = 2
        for ii in range(1, 3):
            pdu.reason_diagnostic = ii
            self.assertTrue(isinstance(pdu.reason_str, str))

        pdu.reason_diagnostic = 3
        with self.assertRaises(ValueError): pdu.reason_str

        pdu.source = 3
        for ii in range(1, 8):
            pdu.reason_diagnostic = ii
            self.assertTrue(isinstance(pdu.reason_str, str))

        pdu.reason_diagnostic = 8
        with self.assertRaises(ValueError): pdu.reason_str

        pdu.source = 4
        with self.assertRaises(ValueError): pdu.reason_str

    def test_generic_encode(self):
        """ Check using the new pdu.encode produces the correct output """
        pdu = A_ASSOCIATE_RJ()
        pdu.Decode(a_associate_rj)
        s = pdu.Encode()
        t = pdu.encode()

        self.assertEqual(s, t)


class TestPDU_P_DATA_TF(unittest.TestCase):
    def test_string_output(self):
        """Test the string output"""
        pdu = P_DATA_TF()
        pdu.Decode(p_data_tf)
        self.assertTrue("80 bytes" in pdu.__str__())
        self.assertTrue("0x03 0x00" in pdu.__str__())

    def test_stream_decode_values_types(self):
        """ Check decoding the p_data stream produces the correct objects """
        pdu = P_DATA_TF()
        pdu.Decode(p_data_tf)

        self.assertEqual(pdu.pdu_type, 0x04)
        self.assertEqual(pdu.pdu_length, 84)
        self.assertTrue(isinstance(pdu.pdu_type, int))
        self.assertTrue(isinstance(pdu.pdu_length, int))

    def test_decode_properties(self):
        """ Check decoding the p_data stream produces the correct properties """
        pdu = P_DATA_TF()
        pdu.Decode(p_data_tf)

        # Check PDVs
        self.assertTrue(isinstance(pdu.PDVs, list))
        self.assertEqual(pdu.get_length(), 90)

    def test_stream_encode(self):
        """ Check encoding an p_data produces the correct output """
        pdu = P_DATA_TF()
        pdu.Decode(p_data_tf)
        s = pdu.Encode()

        self.assertEqual(s, p_data_tf)

    def test_new_encode(self):
        """ Check encoding using new generic method """
        pdu = P_DATA_TF()
        pdu.Decode(p_data_tf)
        s = pdu.encode()

        self.assertEqual(s, p_data_tf)

    def test_to_primitive(self):
        """ Check converting PDU to primitive """
        pdu = P_DATA_TF()
        pdu.Decode(p_data_tf)

        primitive = pdu.ToParams()

        self.assertEqual(primitive.presentation_data_value_list, [[1, p_data_tf[11:]]])
        self.assertTrue(isinstance(primitive.presentation_data_value_list, list))

    def test_from_primitive(self):
        """ Check converting PDU to primitive """
        orig_pdu = P_DATA_TF()
        orig_pdu.Decode(p_data_tf)

        primitive = orig_pdu.ToParams()

        new_pdu = P_DATA_TF()
        new_pdu.FromParams(primitive)

        self.assertEqual(new_pdu, orig_pdu)

    def test_generic_encode(self):
        """ Check using the new pdu.encode produces the correct output """
        pdu = P_DATA_TF()
        pdu.Decode(p_data_tf)
        s = pdu.Encode()
        t = pdu.encode()

        self.assertEqual(s, t)


class TestPDU_A_RELEASE_RQ(unittest.TestCase):
    def test_string_output(self):
        """Test the string output"""
        pdu = A_RELEASE_RQ()
        pdu.Decode(a_release_rq)
        self.assertTrue("0x05" in pdu.__str__())
        self.assertTrue("10 bytes" in pdu.__str__())

    def test_stream_decode_values_types(self):
        """ Check decoding the release_rq stream produces the correct objects """
        pdu = A_RELEASE_RQ()
        pdu.Decode(a_release_rq)

        self.assertEqual(pdu.pdu_type, 0x05)
        self.assertEqual(pdu.pdu_length, 4)
        self.assertEqual(pdu.get_length(), 10)
        self.assertTrue(isinstance(pdu.pdu_type, int))
        self.assertTrue(isinstance(pdu.pdu_length, int))

    def test_stream_encode(self):
        """ Check encoding an release_rq produces the correct output """
        pdu = A_RELEASE_RQ()
        pdu.Decode(a_release_rq)
        s = pdu.Encode()

        self.assertEqual(s, a_release_rq)

    def test_new_encode(self):
        """ Check encoding using new generic method """
        pdu = A_RELEASE_RQ()
        pdu.Decode(a_release_rq)
        s = pdu.encode()

        self.assertEqual(s, a_release_rq)

    def test_to_primitive(self):
        """ Check converting PDU to primitive """
        pdu = A_RELEASE_RQ()
        pdu.Decode(a_release_rq)

        primitive = pdu.ToParams()

        self.assertEqual(primitive.reason, "normal")
        self.assertEqual(primitive.result, None)

    def test_from_primitive(self):
        """ Check converting PDU to primitive """
        orig_pdu = A_RELEASE_RQ()
        orig_pdu.Decode(a_release_rq)

        primitive = orig_pdu.ToParams()

        new_pdu = A_RELEASE_RQ()
        new_pdu.FromParams(primitive)

        self.assertEqual(new_pdu, orig_pdu)

    def test_generic_encode(self):
        """ Check using the new pdu.encode produces the correct output """
        pdu = A_RELEASE_RQ()
        pdu.Decode(a_release_rq)
        s = pdu.Encode()
        t = pdu.encode()

        self.assertEqual(s, t)


class TestPDU_A_RELEASE_RP(unittest.TestCase):
    def test_string_output(self):
        """Test the string output"""
        pdu = A_RELEASE_RP()
        pdu.Decode(a_release_rp)
        self.assertTrue("0x06" in pdu.__str__())
        self.assertTrue("10 bytes" in pdu.__str__())

    def test_stream_decode_values_types(self):
        """ Check decoding the release_rp stream produces the correct objects """
        pdu = A_RELEASE_RP()
        pdu.Decode(a_release_rp)

        self.assertEqual(pdu.pdu_type, 0x06)
        self.assertEqual(pdu.pdu_length, 4)
        self.assertEqual(pdu.get_length(), 10)
        self.assertTrue(isinstance(pdu.pdu_type, int))
        self.assertTrue(isinstance(pdu.pdu_length, int))

    def test_stream_encode(self):
        """ Check encoding an release_rp produces the correct output """
        pdu = A_RELEASE_RP()
        pdu.Decode(a_release_rp)
        s = pdu.Encode()

        self.assertEqual(s, a_release_rp)

    def test_new_encode(self):
        """ Check encoding using new generic method """
        pdu = A_RELEASE_RP()
        pdu.Decode(a_release_rp)
        s = pdu.encode()

        self.assertEqual(s, a_release_rp)

    def test_to_primitive(self):
        """ Check converting PDU to primitive """
        pdu = A_RELEASE_RP()
        pdu.Decode(a_release_rp)

        primitive = pdu.ToParams()

        self.assertEqual(primitive.reason, "normal")
        self.assertEqual(primitive.result, "affirmative")

    def test_from_primitive(self):
        """ Check converting PDU to primitive """
        orig_pdu = A_RELEASE_RP()
        orig_pdu.Decode(a_release_rp)

        primitive = orig_pdu.ToParams()

        new_pdu = A_RELEASE_RP()
        new_pdu.FromParams(primitive)

        self.assertEqual(new_pdu, orig_pdu)

    def test_generic_encode(self):
        """ Check using the new pdu.encode produces the correct output """
        pdu = A_RELEASE_RP()
        pdu.Decode(a_release_rp)
        s = pdu.Encode()
        t = pdu.encode()

        self.assertEqual(s, t)


class TestPDU_A_ABORT(unittest.TestCase):
    def test_string_output(self):
        """Test the string output"""
        pdu = A_ABORT_RQ()
        pdu.Decode(a_abort)
        self.assertTrue("0x07" in pdu.__str__())
        self.assertTrue("4 bytes" in pdu.__str__())
        self.assertTrue("DUL service-user" in pdu.__str__())

    def test_a_abort_stream_decode_values_types(self):
        """ Check decoding the a_abort stream produces the correct objects """
        pdu = A_ABORT_RQ()
        pdu.Decode(a_abort)

        self.assertEqual(pdu.pdu_type, 0x07)
        self.assertEqual(pdu.pdu_length, 4)
        self.assertEqual(pdu.source, 0)
        self.assertEqual(pdu.reason_diagnostic, 0)
        self.assertEqual(pdu.get_length(), 10)
        self.assertTrue(isinstance(pdu.pdu_type, int))
        self.assertTrue(isinstance(pdu.pdu_length, int))
        self.assertTrue(isinstance(pdu.source, int))
        self.assertTrue(isinstance(pdu.reason_diagnostic, int))

    def test_a_p_abort_stream_decode_values_types(self):
        """ Check decoding the a_abort stream produces the correct objects """
        pdu = A_ABORT_RQ()
        pdu.Decode(a_p_abort)

        self.assertEqual(pdu.pdu_type, 0x07)
        self.assertEqual(pdu.pdu_length, 4)
        self.assertEqual(pdu.source, 2)
        self.assertEqual(pdu.reason_diagnostic, 4)
        self.assertTrue(isinstance(pdu.pdu_type, int))
        self.assertTrue(isinstance(pdu.pdu_length, int))
        self.assertTrue(isinstance(pdu.source, int))
        self.assertTrue(isinstance(pdu.reason_diagnostic, int))

    def test_a_abort_stream_encode(self):
        """ Check encoding an a_abort produces the correct output """
        pdu = A_ABORT_RQ()
        pdu.Decode(a_abort)
        s = pdu.Encode()

        self.assertEqual(s, a_abort)

    def test_new_encode_a_abort(self):
        """ Check encoding using new generic method """
        pdu = A_ABORT_RQ()
        pdu.Decode(a_abort)
        s = pdu.encode()

        self.assertEqual(s, a_abort)

    def test_a_p_abort_stream_encode(self):
        """ Check encoding an a_abort produces the correct output """
        pdu = A_ABORT_RQ()
        pdu.Decode(a_p_abort)
        s = pdu.Encode()

        self.assertEqual(s, a_p_abort)

    def test_new_encode_a_p_abort(self):
        """ Check encoding using new generic method """
        pdu = A_ABORT_RQ()
        pdu.Decode(a_p_abort)
        s = pdu.encode()

        self.assertEqual(s, a_p_abort)

    def test_to_a_abort_primitive(self):
        """ Check converting PDU to a_abort primitive """
        pdu = A_ABORT_RQ()
        pdu.Decode(a_abort)

        primitive = pdu.ToParams()

        self.assertTrue(isinstance(primitive, A_ABORT))
        self.assertEqual(primitive.abort_source, 0)

    def test_to_a_p_abort_primitive(self):
        """ Check converting PDU to a_p_abort primitive """
        pdu = A_ABORT_RQ()
        pdu.Decode(a_p_abort)

        primitive = pdu.ToParams()

        self.assertTrue(isinstance(primitive, A_P_ABORT))
        self.assertEqual(primitive.provider_reason, 4)

    def test_a_abort_from_primitive(self):
        """ Check converting PDU to primitive """
        orig_pdu = A_ABORT_RQ()
        orig_pdu.Decode(a_abort)

        primitive = orig_pdu.ToParams()

        new_pdu = A_ABORT_RQ()
        new_pdu.FromParams(primitive)

        self.assertEqual(new_pdu, orig_pdu)

    def test_a_p_abort_from_primitive(self):
        """ Check converting PDU to primitive """
        orig_pdu = A_ABORT_RQ()
        orig_pdu.Decode(a_p_abort)

        primitive = orig_pdu.ToParams()

        new_pdu = A_ABORT_RQ()
        new_pdu.FromParams(primitive)

        self.assertEqual(new_pdu, orig_pdu)

    def test_source_str(self):
        """ Check the source str returns correct values """
        pdu = A_ABORT_RQ()
        pdu.Decode(a_abort)

        pdu.source = 0
        self.assertEqual(pdu.source_str, 'DUL service-user')

        pdu.source = 2
        self.assertEqual(pdu.source_str, 'DUL service-provider')

    def test_reason_str(self):
        """ Check the reaspm str returns correct values """
        pdu = A_ABORT_RQ()
        pdu.Decode(a_abort)

        pdu.source = 2
        pdu.reason_diagnostic = 0
        self.assertEqual(pdu.reason_str, "No reason given")
        pdu.reason_diagnostic = 1
        self.assertEqual(pdu.reason_str, "Unrecognised PDU")
        pdu.reason_diagnostic = 2
        self.assertEqual(pdu.reason_str, "Unexpected PDU")
        pdu.reason_diagnostic = 3
        self.assertEqual(pdu.reason_str, "Reserved")
        pdu.reason_diagnostic = 4
        self.assertEqual(pdu.reason_str, "Unrecognised PDU parameter")
        pdu.reason_diagnostic = 5
        self.assertEqual(pdu.reason_str, "Unexpected PDU parameter")
        pdu.reason_diagnostic = 6
        self.assertEqual(pdu.reason_str, "Invalid PDU parameter value")

    def test_generic_encode(self):
        """ Check using the new pdu.encode produces the correct output """
        pdu = A_ABORT_RQ()
        pdu.Decode(a_abort)
        s = pdu.Encode()
        t = pdu.encode()

        self.assertEqual(s, t)

if __name__ == "__main__":
    unittest.main()
