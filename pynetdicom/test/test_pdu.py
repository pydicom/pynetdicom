#!/usr/bin/env python

a_associate_rq = b"\x01\x00\x00\x00\x00\xcd\x00\x01\x00\x00\x41\x4e\x59\x2d\x53\x43" \
                 b"\x50\x20\x20\x20\x20\x20\x20\x20\x20\x20\x45\x43\x48\x4f\x53\x43" \
                 b"\x55\x20\x20\x20\x20\x20\x20\x20\x20\x20\x00\x00\x00\x00\x00\x00" \
                 b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00" \
                 b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x10\x00\x00\x15\x31\x2e" \
                 b"\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x33\x2e\x31\x2e" \
                 b"\x31\x2e\x31\x20\x00\x00\x2e\x01\x00\x00\x00\x30\x00\x00\x11\x31" \
                 b"\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x31\x2e\x31" \
                 b"\x40\x00\x00\x11\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30" \
                 b"\x38\x2e\x31\x2e\x32\x50\x00\x00\x3a\x51\x00\x00\x04\x00\x00\x40" \
                 b"\x00\x52\x00\x00\x1b\x31\x2e\x32\x2e\x32\x37\x36\x2e\x30\x2e\x37" \
                 b"\x32\x33\x30\x30\x31\x30\x2e\x33\x2e\x30\x2e\x33\x2e\x36\x2e\x30" \
                 b"\x55\x00\x00\x0f\x4f\x46\x46\x49\x53\x5f\x44\x43\x4d\x54\x4b\x5f" \
                 b"\x33\x36\x30"

a_associate_ac = b"\x02\x00\x00\x00\x00\xb8\x00\x01\x00\x00\x41\x4e\x59\x2d\x53\x43" \
                 b"\x50\x20\x20\x20\x20\x20\x20\x20\x20\x20\x45\x43\x48\x4f\x53\x43" \
                 b"\x55\x20\x20\x20\x20\x20\x20\x20\x20\x20\x00\x00\x00\x00\x00\x00" \
                 b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00" \
                 b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x10\x00\x00\x15\x31\x2e" \
                 b"\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x33\x2e\x31\x2e" \
                 b"\x31\x2e\x31\x21\x00\x00\x19\x01\x00\x00\x00\x40\x00\x00\x11\x31" \
                 b"\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x31\x2e\x32" \
                 b"\x50\x00\x00\x3a\x51\x00\x00\x04\x00\x00\x40\x00\x52\x00\x00\x1b" \
                 b"\x31\x2e\x32\x2e\x32\x37\x36\x2e\x30\x2e\x37\x32\x33\x30\x30\x31" \
                 b"\x30\x2e\x33\x2e\x30\x2e\x33\x2e\x36\x2e\x30\x55\x00\x00\x0f\x4f" \
                 b"\x46\x46\x49\x53\x5f\x44\x43\x4d\x54\x4b\x5f\x33\x36\x30"

from io import BytesIO
import logging
import threading
import unittest
from unittest.mock import patch

from pydicom.uid import UID, ImplicitVRLittleEndian

from pynetdicom import AE
from pynetdicom import VerificationSOPClass, StorageSOPClassList, \
    QueryRetrieveSOPClassList
from pynetdicom.PDU import *
from pynetdicom.utils import wrap_list

logger = logging.getLogger('pynetdicom')
handler = logging.StreamHandler()
logger.setLevel(logging.ERROR)


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
        self.assertTrue(isinstance(item, A_ASSOCIATE_RQ_PDU))
        
        item = pdu._next_item(BytesIO(b'\x02'))
        self.assertTrue(isinstance(item, A_ASSOCIATE_AC_PDU))
        
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


class TestPDU_A_ASSOC_RQ(unittest.TestCase):
    def test_stream_decode_values_types(self):
        """ Check decoding the assoc_rq stream produces the correct objects """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        
        self.assertEqual(pdu.pdu_type, 0x01)
        self.assertEqual(pdu.pdu_length, 205)
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
        pdu = A_ASSOCIATE_RQ_PDU()
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

    def test_stream_encode(self):
        """ Check encoding an assoc_rq produces the correct output """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        s = pdu.Encode()
        
        self.assertEqual(s, a_associate_rq)

    def test_to_primitive(self):
        """ Check converting PDU to primitive """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        
        primitive = pdu.ToParams()
        
        self.assertEqual(primitive.ApplicationContextName, UID('1.2.840.10008.3.1.1.1'))
        self.assertEqual(primitive.CallingAETitle, b'ECHOSCU         ')
        self.assertEqual(primitive.CalledAETitle, b'ANY-SCP         ')
        
        # Test User Information
        for item in primitive.UserInformationItem:
            # Maximum PDU Length (required)
            if isinstance(item, MaximumLengthSubItem):
                self.assertEqual(item.MaximumLengthReceived, 16384)
                self.assertEqual(user_info.maximum_length, 16384)
                self.assertTrue(isinstance(item.MaximumLengthReceived, int))
                self.assertTrue(isinstance(user_info.maximum_length, int))
            
            # Implementation Class UID (required)
            elif isinstance(item, ImplementationClassUIDSubItem):
                self.assertEqual(item.ItemType, 0x52)
                self.assertEqual(item.ItemLength, 27)
                self.assertEqual(item.implementation_class_uid, UID('1.2.276.0.7230010.3.0.3.6.0'))
                self.assertTrue(isinstance(item.ItemType, int))
                self.assertTrue(isinstance(item.ItemLength, int))
                self.assertTrue(isinstance(item.implementation_class_uid, UID))
                
            # Implementation Version Name (optional)
            elif isinstance(item, ImplementationVersionNameSubItem):
                self.assertEqual(item.ItemType, 0x55)
                self.assertEqual(item.ItemLength, 15)
                self.assertEqual(item.implementation_version_name, b'OFFIS_DCMTK_360')
                self.assertTrue(isinstance(item.ItemType, int))
                self.assertTrue(isinstance(item.ItemLength, int))
                self.assertTrue(isinstance(item.implementation_version_name, bytes))
        
        # Test Presentation Contexts
        for context in primitive.PresentationContextDefinitionList:
            self.assertEqual(context.ID, 1)
            self.assertEqual(context.AbstractSyntax, UID('1.2.840.10008.1.1'))
            for syntax in context.TransferSyntax:
                self.assertEqual(syntax, UID('1.2.840.10008.1.2'))
            
        self.assertTrue(isinstance(primitive.ApplicationContextName, UID))
        self.assertTrue(isinstance(primitive.CallingAETitle, bytes))
        self.assertTrue(isinstance(primitive.CalledAETitle, bytes))
        self.assertTrue(isinstance(primitive.UserInformationItem, list))
        self.assertTrue(isinstance(primitive.PresentationContextDefinitionList, list))
        
        # Not used by A-ASSOCIATE-RQ or fixed value
        self.assertEqual(primitive.Mode, "normal")
        self.assertEqual(primitive.RespondingAETitle, None)
        self.assertEqual(primitive.Result, None)
        self.assertEqual(primitive.ResultSource, None)
        self.assertEqual(primitive.Diagnostic, None)
        self.assertEqual(primitive.CallingPresentationAddress, None)
        self.assertEqual(primitive.CalledPresentationAddress, None)
        self.assertEqual(primitive.RespondingPresentationAddress, primitive.CalledPresentationAddress)
        self.assertEqual(primitive.PresentationContextDefinitionResultList, [])
        self.assertEqual(primitive.PresentationRequirements, "Presentation Kernel")
        self.assertEqual(primitive.SessionRequirements, "")

    def test_from_primitive(self):
        """ Check converting PDU to primitive """
        orig_pdu = A_ASSOCIATE_RQ_PDU()
        orig_pdu.Decode(a_associate_rq)
        
        primitive = orig_pdu.ToParams()
        
        new_pdu = A_ASSOCIATE_RQ_PDU()
        new_pdu.FromParams(primitive)
        
        self.assertEqual(new_pdu, orig_pdu)
        
    def test_update_data(self):
        """ Check that updating the PDU data works correctly """
        orig_pdu = A_ASSOCIATE_RQ_PDU()
        orig_pdu.Decode(a_associate_rq)
        orig_pdu.user_information.UserData = [orig_pdu.user_information.UserData[1]]
        orig_pdu.get_length()
        
        primitive = orig_pdu.ToParams()
        
        new_pdu = A_ASSOCIATE_RQ_PDU()
        new_pdu.FromParams(primitive)
        
        self.assertEqual(new_pdu, orig_pdu)

class TestPDU_A_ASSOC_RQ_ApplicationContext(unittest.TestCase):
    def test_stream_decode_values_types(self):
        """ Check decoding an assoc_rq produces the correct application context """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        
        app_context = pdu.variable_items[0]
        
        self.assertEqual(app_context.ItemType, 0x10)
        self.assertEqual(app_context.ItemLength, 21)
        self.assertEqual(app_context.application_context_name, '1.2.840.10008.3.1.1.1')
        self.assertTrue(isinstance(app_context.ItemType, int))
        self.assertTrue(isinstance(app_context.ItemLength, int))
        self.assertTrue(isinstance(app_context.application_context_name, UID))
        
        self.assertEqual(app_context.application_context_name, '1.2.840.10008.3.1.1.1')
        self.assertTrue(isinstance(app_context.application_context_name, UID))

class TestPDU_A_ASSOC_RQ_PresentationContext(unittest.TestCase):
    def test_stream_decode_values_types(self):
        """ Check decoding an assoc_rq produces the correct presentation context """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        
        # Check PresentationContextItemRQ attributes
        presentation_context = pdu.variable_items[1]
        self.assertEqual(presentation_context.ItemType, 0x20)
        self.assertEqual(presentation_context.PresentationContextID, 0x001)
        self.assertEqual(presentation_context.ItemLength, 46)
        self.assertTrue(isinstance(presentation_context.ItemType, int))
        self.assertTrue(isinstance(presentation_context.PresentationContextID, int))
        self.assertTrue(isinstance(presentation_context.ItemLength, int))
        
    def test_decode_properties(self):
        """ Check decoding the stream produces the correct properties """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        
        context = pdu.presentation_context[0]
        
        # Check ID property
        context_id = context.ID
        self.assertTrue(isinstance(context_id, int))
        self.assertEqual(context_id, 1)
        
        # Check Abstract Syntax property        
        context = pdu.presentation_context[0]
        self.assertTrue(isinstance(context.AbstractSyntax, UID))
        self.assertEqual(context.AbstractSyntax, UID('1.2.840.10008.1.1'))
        
        # Check TransferSyntax property is a list
        self.assertTrue(isinstance(context.TransferSyntax, list))
        
        # Check TransferSyntax list contains transfer syntax type UIDs
        for syntax in pdu.presentation_context[0].TransferSyntax:
            self.assertTrue(isinstance(syntax, UID))
            self.assertTrue(syntax.is_transfer_syntax)
        
        # Check first transfer syntax is little endian implicit
        syntax = pdu.presentation_context[0].TransferSyntax[0]
        self.assertEqual(syntax, UID('1.2.840.10008.1.2'))

class TestPDU_A_ASSOC_RQ_PresentationContext_AbstractSyntax(unittest.TestCase):
    def test_decode_value_type(self):
        """ Check decoding an assoc_rq produces the correct abstract syntax """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        
        context = pdu.presentation_context[0]
        
        abstract_syntax = context.AbstractTransferSyntaxSubItems[0]
        
        self.assertEqual(abstract_syntax.ItemType, 0x30)
        self.assertEqual(abstract_syntax.ItemLength, 17)
        self.assertEqual(abstract_syntax.abstract_syntax_name, UID('1.2.840.10008.1.1'))
        self.assertTrue(isinstance(abstract_syntax.ItemType, int))
        self.assertTrue(isinstance(abstract_syntax.ItemLength, int))
        self.assertTrue(isinstance(abstract_syntax.abstract_syntax_name, UID))
        
class TestPDU_A_ASSOC_RQ_PresentationContext_TransferSyntax(unittest.TestCase):
    def test_decode_value_type(self):
        """ Check decoding an assoc_rq produces the correct transfer syntax """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        
        context = pdu.presentation_context[0]
        transfer_syntaxes = context.TransferSyntax
        
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
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)

        user_info = pdu.variable_items[2]
        
        self.assertEqual(user_info.ItemType, 0x50)
        self.assertEqual(user_info.ItemLength, 58)
        self.assertTrue(isinstance(user_info.ItemType, int))
        self.assertTrue(isinstance(user_info.ItemLength, int))
        self.assertTrue(isinstance(user_info.UserData, list))
        
        # Test user items
        for item in user_info.UserData:
            # Maximum PDU Length (required)
            if isinstance(item, MaximumLengthSubItem):
                self.assertEqual(item.MaximumLengthReceived, 16384)
                self.assertEqual(user_info.maximum_length, 16384)
                self.assertTrue(isinstance(item.MaximumLengthReceived, int))
                self.assertTrue(isinstance(user_info.maximum_length, int))
            
            # Implementation Class UID (required)
            elif isinstance(item, ImplementationClassUIDSubItem):
                self.assertEqual(item.ItemType, 0x52)
                self.assertEqual(item.ItemLength, 27)
                self.assertEqual(item.implementation_class_uid, UID('1.2.276.0.7230010.3.0.3.6.0'))
                self.assertTrue(isinstance(item.ItemType, int))
                self.assertTrue(isinstance(item.ItemLength, int))
                self.assertTrue(isinstance(item.implementation_class_uid, UID))
                
            # Implementation Version Name (optional)
            elif isinstance(item, ImplementationVersionNameSubItem):
                self.assertEqual(item.ItemType, 0x55)
                self.assertEqual(item.ItemLength, 15)
                self.assertEqual(item.implementation_version_name, b'OFFIS_DCMTK_360')
                self.assertTrue(isinstance(item.ItemType, int))
                self.assertTrue(isinstance(item.ItemLength, int))
                self.assertTrue(isinstance(item.implementation_version_name, bytes))



if __name__ == "__main__":
    unittest.main()
