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

a_associate_rj = b"\x03\x00\x00\x00\x00\x04\x00\x01\x01\x01"

a_release_rq = b"\x05\x00\x00\x00\x00\x04\x00\x00\x00\x00"

a_release_rp = b"\x06\x00\x00\x00\x00\x04\x00\x00\x00\x00"

a_abort = b"\x07\x00\x00\x00\x00\x04\x00\x00\x00\x00"

a_p_abort = b"\x07\x00\x00\x00\x00\x04\x00\x00\x02\x04"

# This is a C-ECHO
p_data_tf = b"\x04\x00\x00\x00\x00\x54\x00\x00\x00\x50\x01\x03\x00\x00\x00\x00" \
            b"\x04\x00\x00\x00\x42\x00\x00\x00\x00\x00\x02\x00\x12\x00\x00\x00" \
            b"\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x31\x2e" \
            b"\x31\x00\x00\x00\x00\x01\x02\x00\x00\x00\x30\x80\x00\x00\x20\x01" \
            b"\x02\x00\x00\x00\x01\x00\x00\x00\x00\x08\x02\x00\x00\x00\x01\x01" \
            b"\x00\x00\x00\x09\x02\x00\x00\x00\x00\x00"

application_context = b'\x10\x00\x00\x151.2.840.10008.3.1.1.1'

presentation_context_rq = b'\x20\x00\x00\x2e\x01\x00\x00\x00\x30\x00\x00\x11\x31\x2e\x32\x2e' \
                          b'\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x31\x2e\x31\x40\x00\x00' \
                          b'\x11\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x31' \
                          b'\x2e\x32'

presentation_context_ac = b'\x21\x00\x00\x19\x01\x00\x00\x00\x40\x00\x00\x11\x31\x2e\x32\x2e' \
                          b'\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x31\x2e\x32'

abstract_syntax = b'\x30\x00\x00\x11\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30' \
                  b'\x38\x2e\x31\x2e\x31'

transfer_syntax = b'\x40\x00\x00\x11\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30' \
                  b'\x38\x2e\x31\x2e\x32'

presentation_data = b'\x03\x00\x00\x00\x00\x04\x00\x00\x00\x42\x00\x00\x00\x00\x00\x02' \
                    b'\x00\x12\x00\x00\x00\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30' \
                    b'\x30\x38\x2e\x31\x2e\x31\x00\x00\x00\x00\x01\x02\x00\x00\x00\x30' \
                    b'\x80\x00\x00\x20\x01\x02\x00\x00\x00\x01\x00\x00\x00\x00\x08\x02' \
                    b'\x00\x00\x00\x01\x01\x00\x00\x00\x09\x02\x00\x00\x00\x00\x00'

presentation_data_value = b'\x00\x00\x00\x50\x01' + presentation_data


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
from pynetdicom.utils import wrap_list, PresentationContext

logger = logging.getLogger('pynetdicom')
#handler = logging.StreamHandler()
handler = logging.NullHandler()
for h in logger.handlers:
    logger.removeHandler(h)
logger.addHandler(handler)
logger.setLevel(logging.ERROR)


class TestPDUItem_ApplicationContext(unittest.TestCase):
    def test_stream_decode_assoc_rq(self):
        """ Check decoding an assoc_rq produces the correct application context """
        pdu = A_ASSOCIATE_RQ_PDU()
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

    def test_stream_decode_assoc_ac(self):
        """ Check decoding an assoc_ac produces the correct application context """
        pdu = A_ASSOCIATE_AC_PDU()
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

    def test_encode(self):
        """ Check encoding produces the correct output """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        
        for item in pdu.variable_items:
            if isinstance(item, ApplicationContextItem):
                s = item.encode()

        self.assertEqual(s, application_context)
        
    def test_to_primitive(self):
        """ Check converting to primitive """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        
        for item in pdu.variable_items:
            if isinstance(item, ApplicationContextItem):
                result = item.ToParams()
        
        self.assertEqual(result, '1.2.840.10008.3.1.1.1')
        self.assertTrue(isinstance(result, str))
        
    def test_from_primitive(self):
        """ Check converting from primitive """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        
        for item in pdu.variable_items:
            if isinstance(item, ApplicationContextItem):
                item.FromParams('1.2.840.10008.3.1.1.1.1')
                self.assertEqual(item.application_context_name, '1.2.840.10008.3.1.1.1.1')

    def test_update(self):
        """ Test that changing the item's parameters correctly updates the length """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        
        for item in pdu.variable_items:
            if isinstance(item, ApplicationContextItem):
                self.assertEqual(item.length, 25)
                item.application_context_name = '1.2.840.10008.3.1.1.1.1'
                self.assertEqual(item.length, 27)

    def test_properties(self):
        """ Test the item's property setters and getters """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        
        for item in pdu.variable_items:
            if isinstance(item, ApplicationContextItem):
                uid = '1.2.840.10008.3.1.1.1'
                for s in [bytes(uid, 'utf-8'), uid, UID(uid)]:
                    item.application_context_name = s
                    self.assertEqual(item.application_context_name, UID(uid))
                    self.assertTrue(isinstance(item.application_context_name, UID))


class TestPDUItem_PresentationContextRQ(unittest.TestCase):
    def test_stream_decode(self):
        """ Check decoding produces the correct presentation context """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        
        pres_context = pdu.variable_items[1]
        
        self.assertEqual(pres_context.item_type, 0x20)
        self.assertEqual(pres_context.item_length, 46)
        self.assertEqual(pres_context.presentation_context_id, 1)
        self.assertEqual(pres_context.SCP, None)
        self.assertEqual(pres_context.SCU, None)
        self.assertTrue(isinstance(pres_context.abstract_transfer_syntax_sub_items, list))

    def test_encode(self):
        """ Check encoding produces the correct output """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        
        for item in pdu.variable_items:
            if isinstance(item, PresentationContextItemRQ):
                s = item.encode()

        self.assertEqual(s, presentation_context_rq)

    def test_to_primitive(self):
        """ Check converting to primitive """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        
        for item in pdu.variable_items:
            if isinstance(item, PresentationContextItemRQ):
                result = item.ToParams()
        
        context = PresentationContext(1)
        context.AbstractSyntax = '1.2.840.10008.1.1'
        context.add_transfer_syntax('1.2.840.10008.1.2')
        self.assertEqual(result, context)
        
    def test_from_primitive(self):
        """ Check converting from primitive """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        
        for ii in pdu.variable_items:
            if isinstance(ii, PresentationContextItemRQ):
                orig_item = ii
                break
        
        context = PresentationContext(1)
        context.AbstractSyntax = '1.2.840.10008.1.1'
        context.add_transfer_syntax('1.2.840.10008.1.2')

        new_item = PresentationContextItemRQ()
        new_item.FromParams(context)
        
        self.assertEqual(orig_item, new_item)

class TestPDUItem_PresentationContextAC(unittest.TestCase):
    def test_stream_decode(self):
        """ Check decoding produces the correct presentation context """
        pdu = A_ASSOCIATE_AC_PDU()
        pdu.Decode(a_associate_ac)
        
        pres_context = pdu.variable_items[1]
        
        self.assertEqual(pres_context.item_type, 0x21)
        self.assertEqual(pres_context.item_length, 25)
        self.assertEqual(pres_context.presentation_context_id, 1)
        self.assertEqual(pres_context.SCP, None)
        self.assertEqual(pres_context.SCU, None)
        self.assertTrue(isinstance(pres_context.transfer_syntax_sub_item, TransferSyntaxSubItem))

    def test_encode(self):
        """ Check encoding produces the correct output """
        pdu = A_ASSOCIATE_AC_PDU()
        pdu.Decode(a_associate_ac)
        
        for item in pdu.variable_items:
            if isinstance(item, PresentationContextItemAC):
                s = item.encode()

        self.assertEqual(s, presentation_context_ac)

    def test_to_primitive(self):
        """ Check converting to primitive """
        pdu = A_ASSOCIATE_AC_PDU()
        pdu.Decode(a_associate_ac)
        
        for item in pdu.variable_items:
            if isinstance(item, PresentationContextItemAC):
                result = item.ToParams()
        
        context = PresentationContext(1)
        context.add_transfer_syntax('1.2.840.10008.1.2')
        context.Result = 0
        self.assertEqual(result, context)
        
    def test_from_primitive(self):
        """ Check converting from primitive """
        pdu = A_ASSOCIATE_AC_PDU()
        pdu.Decode(a_associate_ac)
        
        for ii in pdu.variable_items:
            if isinstance(ii, PresentationContextItemAC):
                orig_item = ii
                break
        
        context = PresentationContext(1)
        context.add_transfer_syntax('1.2.840.10008.1.2')
        context.Result = 0

        new_item = PresentationContextItemAC()
        new_item.FromParams(context)
        
        self.assertEqual(orig_item, new_item)


class TestPDUItem_AbstractSyntax(unittest.TestCase):
    def test_stream_decode(self):
        """ Check decoding produces the correct presentation context """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        
        contexts = pdu.presentation_context
        ab_syntax = contexts[0].abstract_transfer_syntax_sub_items[0]
        
        self.assertEqual(ab_syntax.item_type, 0x30)
        self.assertEqual(ab_syntax.item_length, 17)
        self.assertEqual(ab_syntax.abstract_syntax_name, UID('1.2.840.10008.1.1'))

    def test_encode(self):
        """ Check encoding produces the correct output """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        
        contexts = pdu.presentation_context
        ab_syntax = contexts[0].abstract_transfer_syntax_sub_items[0]
        
        s = ab_syntax.encode()

        self.assertEqual(s, abstract_syntax)

    def test_to_primitive(self):
        """ Check converting to primitive """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        
        contexts = pdu.presentation_context
        ab_syntax = contexts[0].abstract_transfer_syntax_sub_items[0]
        
        result = ab_syntax.ToParams()
        
        self.assertEqual(result, UID('1.2.840.10008.1.1'))
        
    def test_from_primitive(self):
        """ Check converting from primitive """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        
        contexts = pdu.presentation_context
        orig_ab_syntax = contexts[0].abstract_transfer_syntax_sub_items[0]
        
        new_ab_syntax = AbstractSyntaxSubItem()
        new_ab_syntax.FromParams('1.2.840.10008.1.1')
        
        self.assertEqual(orig_ab_syntax, new_ab_syntax)

    def test_properies(self):
        """ Check property setters and getters """
        ab_syntax = AbstractSyntaxSubItem()
        ab_syntax.abstract_syntax_name = '1.2.840.10008.1.1'
        
        self.assertEqual(ab_syntax.abstract_syntax, UID('1.2.840.10008.1.1'))
        
        ab_syntax.abstract_syntax_name = b'1.2.840.10008.1.1'
        self.assertEqual(ab_syntax.abstract_syntax, UID('1.2.840.10008.1.1'))
        
        ab_syntax.abstract_syntax_name = UID('1.2.840.10008.1.1')
        self.assertEqual(ab_syntax.abstract_syntax, UID('1.2.840.10008.1.1'))
        
        with self.assertRaises(TypeError):
            ab_syntax.abstract_syntax_name = 10002

class TestPDUItem_TransferSyntax(unittest.TestCase):
    def test_stream_decode(self):
        """ Check decoding produces the correct presentation context """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        
        contexts = pdu.presentation_context
        tran_syntax = contexts[0].abstract_transfer_syntax_sub_items[1]
        
        self.assertEqual(tran_syntax.item_type, 0x40)
        self.assertEqual(tran_syntax.item_length, 17)
        self.assertEqual(tran_syntax.transfer_syntax_name, UID('1.2.840.10008.1.2'))

    def test_encode(self):
        """ Check encoding produces the correct output """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        
        contexts = pdu.presentation_context
        tran_syntax = contexts[0].abstract_transfer_syntax_sub_items[1]
        
        s = tran_syntax.encode()

        self.assertEqual(s, transfer_syntax)

    def test_to_primitive(self):
        """ Check converting to primitive """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        
        contexts = pdu.presentation_context
        tran_syntax = contexts[0].abstract_transfer_syntax_sub_items[1]
        
        result = tran_syntax.ToParams()
        
        self.assertEqual(result, UID('1.2.840.10008.1.2'))
        
    def test_from_primitive(self):
        """ Check converting from primitive """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        
        contexts = pdu.presentation_context
        orig_tran_syntax = contexts[0].abstract_transfer_syntax_sub_items[1]
        
        new_tran_syntax = TransferSyntaxSubItem()
        new_tran_syntax.FromParams('1.2.840.10008.1.2')
        
        self.assertEqual(orig_tran_syntax, new_tran_syntax)

    def test_properies(self):
        """ Check property setters and getters """
        tran_syntax = TransferSyntaxSubItem()
        tran_syntax.transfer_syntax_name = '1.2.840.10008.1.2'
        
        self.assertEqual(tran_syntax.transfer_syntax, UID('1.2.840.10008.1.2'))
        
        tran_syntax.transfer_syntax_name = b'1.2.840.10008.1.2'
        self.assertEqual(tran_syntax.transfer_syntax, UID('1.2.840.10008.1.2'))
        
        tran_syntax.transfer_syntax_name = UID('1.2.840.10008.1.2')
        self.assertEqual(tran_syntax.transfer_syntax, UID('1.2.840.10008.1.2'))
        
        with self.assertRaises(TypeError):
            tran_syntax.transfer_syntax_name = 10002


class TestPDUItem_PresentationDataValue(unittest.TestCase):
    def test_stream_decode(self):
        """ Check decoding produces the correct presentation data value """
        pdu = P_DATA_TF_PDU()
        pdu.Decode(p_data_tf)
        
        pdvs = pdu.PDVs
        
        self.assertEqual(pdvs[0].item_length, 80)
        self.assertEqual(pdvs[0].presentation_data_value, presentation_data)

    def test_encode(self):
        """ Check encoding produces the correct output """
        pdu = P_DATA_TF_PDU()
        pdu.Decode(p_data_tf)
        
        pdvs = pdu.PDVs
        
        s = pdvs[0].encode()

        self.assertEqual(s, presentation_data_value)

    def test_to_primitive(self):
        """ Check converting to primitive """
        pdu = P_DATA_TF_PDU()
        pdu.Decode(p_data_tf)
        
        pdvs = pdu.PDVs
        
        result = pdvs[0].ToParams()
        
        self.assertEqual(result, [1, presentation_data])
        
    def test_from_primitive(self):
        """ Check converting from primitive """
        pdu = P_DATA_TF_PDU()
        pdu.Decode(p_data_tf)
        
        pdvs = pdu.PDVs
        orig_pdv = pdvs[0]
        
        new_pdv = PresentationDataValueItem()
        new_pdv.FromParams([1, presentation_data])
        
        self.assertEqual(orig_pdv, new_pdv)

    def test_properies(self):
        """ Check property setters and getters """
        pdu = P_DATA_TF_PDU()
        pdu.Decode(p_data_tf)
        
        pdvs = pdu.PDVs
        
        pdv = pdvs[0]
        
        self.assertEqual(pdv.ID, 1)
        self.assertEqual(pdv.data, presentation_data)
        self.assertEqual(pdv.message_control_header_byte, '00000011')



if __name__ == "__main__":
    unittest.main()
