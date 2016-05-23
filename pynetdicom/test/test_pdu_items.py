#!/usr/bin/env python

a_associate_rq = b"\x01\x00\x00\x00\x00\xd1\x00\x01\x00\x00\x41\x4e\x59\x2d\x53\x43" \
                 b"\x50\x20\x20\x20\x20\x20\x20\x20\x20\x20\x45\x43\x48\x4f\x53\x43" \
                 b"\x55\x20\x20\x20\x20\x20\x20\x20\x20\x20\x00\x00\x00\x00\x00\x00" \
                 b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00" \
                 b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x10\x00\x00\x15\x31\x2e" \
                 b"\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x33\x2e\x31\x2e" \
                 b"\x31\x2e\x31\x20\x00\x00\x2e\x01\x00\x00\x00\x30\x00\x00\x11\x31" \
                 b"\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x31\x2e\x31" \
                 b"\x40\x00\x00\x11\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30" \
                 b"\x38\x2e\x31\x2e\x32\x50\x00\x00\x3e\x51\x00\x00\x04\x00\x00\x3f" \
                 b"\xfe\x52\x00\x00\x20\x31\x2e\x32\x2e\x38\x32\x36\x2e\x30\x2e\x31" \
                 b"\x2e\x33\x36\x38\x30\x30\x34\x33\x2e\x39\x2e\x33\x38\x31\x31\x2e" \
                 b"\x30\x2e\x39\x2e\x30\x55\x00\x00\x0e\x50\x59\x4e\x45\x54\x44\x49" \
                 b"\x43\x4f\x4d\x5f\x30\x39\x30"

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

a_associate_rq_role = b'\x01\x00\x00\x00\x00\xfc\x00\x01\x00\x00\x41\x4e\x59\x2d\x53\x43' \
                      b'\x50\x20\x20\x20\x20\x20\x20\x20\x20\x20\x47\x45\x54\x53\x43\x55' \
                      b'\x20\x20\x20\x20\x20\x20\x20\x20\x20\x20\x00\x00\x00\x00\x00\x00' \
                      b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' \
                      b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x10\x00\x00\x15\x31\x2e' \
                      b'\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x33\x2e\x31\x2e' \
                      b'\x31\x2e\x31\x20\x00\x00\x38\x01\x00\x00\x00\x30\x00\x00\x19\x31' \
                      b'\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x35\x2e\x31' \
                      b'\x2e\x34\x2e\x31\x2e\x31\x2e\x32\x40\x00\x00\x13\x31\x2e\x32\x2e' \
                      b'\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x31\x2e\x32\x2e\x31\x50' \
                      b'\x00\x00\x5f\x51\x00\x00\x04\x00\x00\x3f\xfe\x52\x00\x00\x20\x31' \
                      b'\x2e\x32\x2e\x38\x32\x36\x2e\x30\x2e\x31\x2e\x33\x36\x38\x30\x30' \
                      b'\x34\x33\x2e\x39\x2e\x33\x38\x31\x31\x2e\x30\x2e\x39\x2e\x30\x55' \
                      b'\x00\x00\x0e\x50\x59\x4e\x45\x54\x44\x49\x43\x4f\x4d\x5f\x30\x39' \
                      b'\x30\x54\x00\x00\x1d\x00\x19\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31' \
                      b'\x30\x30\x30\x38\x2e\x35\x2e\x31\x2e\x34\x2e\x31\x2e\x31\x2e\x32' \
                      b'\x00\x01'

#a_associate_rq_user_id_kerberos
#a_associate_rq_user_id_saml

# username: pynetdicom
a_associate_rq_user_id_user_nopw = b'\x01\x00\x00\x00\x01\x17\x00\x01\x00\x00\x41\x4e\x59\x2d\x53\x43' \
                                   b'\x50\x20\x20\x20\x20\x20\x20\x20\x20\x20\x53\x54\x4f\x52\x45\x53' \
                                   b'\x43\x55\x20\x20\x20\x20\x20\x20\x20\x20\x00\x00\x00\x00\x00\x00' \
                                   b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' \
                                   b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x10\x00\x00\x15\x31\x2e' \
                                   b'\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x33\x2e\x31\x2e' \
                                   b'\x31\x2e\x31\x20\x00\x00\x64\x01\x00\xff\x00\x30\x00\x00\x19\x31' \
                                   b'\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x35\x2e\x31' \
                                   b'\x2e\x34\x2e\x31\x2e\x31\x2e\x32\x40\x00\x00\x13\x31\x2e\x32\x2e' \
                                   b'\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x31\x2e\x32\x2e\x31\x40' \
                                   b'\x00\x00\x13\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38' \
                                   b'\x2e\x31\x2e\x32\x2e\x32\x40\x00\x00\x11\x31\x2e\x32\x2e\x38\x34' \
                                   b'\x30\x2e\x31\x30\x30\x30\x38\x2e\x31\x2e\x32\x50\x00\x00\x4e\x51' \
                                   b'\x00\x00\x04\x00\x00\x40\x00\x52\x00\x00\x1b\x31\x2e\x32\x2e\x32' \
                                   b'\x37\x36\x2e\x30\x2e\x37\x32\x33\x30\x30\x31\x30\x2e\x33\x2e\x30' \
                                   b'\x2e\x33\x2e\x36\x2e\x30\x55\x00\x00\x0f\x4f\x46\x46\x49\x53\x5f' \
                                   b'\x44\x43\x4d\x54\x4b\x5f\x33\x36\x30\x58\x00\x00\x10\x01\x01\x00' \
                                   b'\x0a\x70\x79\x6e\x65\x74\x64\x69\x63\x6f\x6d\x00\x00'

user_identity_rq_user_nopw = b'\x58\x00\x00\x10\x01\x01\x00\x0a\x70\x79\x6e\x65\x74\x64\x69\x63' \
                             b'\x6f\x6d\x00\x00'

# username: pynetdicom, password: p4ssw0rd
a_associate_rq_user_id_user_pass = b'\x01\x00\x00\x00\x01\x1f\x00\x01\x00\x00\x41\x4e\x59\x2d\x53\x43' \
                                   b'\x50\x20\x20\x20\x20\x20\x20\x20\x20\x20\x53\x54\x4f\x52\x45\x53' \
                                   b'\x43\x55\x20\x20\x20\x20\x20\x20\x20\x20\x00\x00\x00\x00\x00\x00' \
                                   b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' \
                                   b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x10\x00\x00\x15\x31\x2e' \
                                   b'\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x33\x2e\x31\x2e' \
                                   b'\x31\x2e\x31\x20\x00\x00\x64\x01\x00\xff\x00\x30\x00\x00\x19\x31' \
                                   b'\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x35\x2e\x31' \
                                   b'\x2e\x34\x2e\x31\x2e\x31\x2e\x32\x40\x00\x00\x13\x31\x2e\x32\x2e' \
                                   b'\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x31\x2e\x32\x2e\x31\x40' \
                                   b'\x00\x00\x13\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38' \
                                   b'\x2e\x31\x2e\x32\x2e\x32\x40\x00\x00\x11\x31\x2e\x32\x2e\x38\x34' \
                                   b'\x30\x2e\x31\x30\x30\x30\x38\x2e\x31\x2e\x32\x50\x00\x00\x56\x51' \
                                   b'\x00\x00\x04\x00\x00\x40\x00\x52\x00\x00\x1b\x31\x2e\x32\x2e\x32' \
                                   b'\x37\x36\x2e\x30\x2e\x37\x32\x33\x30\x30\x31\x30\x2e\x33\x2e\x30' \
                                   b'\x2e\x33\x2e\x36\x2e\x30\x55\x00\x00\x0f\x4f\x46\x46\x49\x53\x5f' \
                                   b'\x44\x43\x4d\x54\x4b\x5f\x33\x36\x30\x58\x00\x00\x18\x02\x00\x00' \
                                   b'\x0a\x70\x79\x6e\x65\x74\x64\x69\x63\x6f\x6d\x00\x08\x70\x34\x73' \
                                   b'\x73\x77\x30\x72\x64'

user_identity_rq_user_pass = b'\x58\x00\x00\x18\x02\x00\x00\x0a\x70\x79\x6e\x65\x74\x64\x69\x63' \
                             b'\x6f\x6d\x00\x08\x70\x34\x73\x73\x77\x30\x72\x64'

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

maximum_length_received = b'\x51\x00\x00\x04\x00\x00\x3f\xfe'

implementation_class_uid = b'\x52\x00\x00\x20\x31\x2e\x32\x2e\x38\x32\x36\x2e\x30\x2e\x31\x2e' \
                           b'\x33\x36\x38\x30\x30\x34\x33\x2e\x39\x2e\x33\x38\x31\x31\x2e\x30' \
                           b'\x2e\x39\x2e\x30'

implementation_version_name = b'\x55\x00\x00\x0e\x50\x59\x4e\x45\x54\x44\x49\x43\x4f\x4d\x5f' \
                              b'\x30\x39\x30'

role_selection = b'\x54\x00\x00\x1d\x00\x19\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30' \
                 b'\x30\x30\x38\x2e\x35\x2e\x31\x2e\x34\x2e\x31\x2e\x31\x2e\x32\x00' \
                 b'\x01'

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


class TestPDUItem_UserInformation(unittest.TestCase):
    def test_stream_decode(self):
        """ Check decoding produces the correct values """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq_role)

        user_info = pdu.user_information
        
        self.assertEqual(user_info.item_type, 0x50)
        self.assertEqual(user_info.item_length, 95)
        
    
class TestPDUItem_UserInformation_MaximumLength(unittest.TestCase):
    def test_stream_decode(self):
        """ Check decoding produces the correct values """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        
        max_length = pdu.user_information.user_data[0]
        
        self.assertEqual(max_length.item_length, 4)
        self.assertEqual(max_length.maximum_length_received, 16382)

    def test_encode(self):
        """ Check encoding produces the correct output """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        
        max_length = pdu.user_information.user_data[0]
        
        s = max_length.encode()

        self.assertEqual(s, maximum_length_received)

    def test_to_primitive(self):
        """ Check converting to primitive """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        
        max_length = pdu.user_information.user_data[0]
        
        result = max_length.ToParams()
        
        check = MaximumLengthParameters()
        check.MaximumLengthReceived = 16382
        
        self.assertEqual(result, check)
        
    def test_from_primitive(self):
        """ Check converting from primitive """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        
        orig_max_length = pdu.user_information.user_data[0]
        params = orig_max_length.ToParams()
        
        new_max_length = MaximumLengthSubItem()
        new_max_length.FromParams(params)
        
        self.assertEqual(orig_max_length, new_max_length)

class TestPDUItem_UserInformation_ImplementationUID(unittest.TestCase):
    def test_stream_decode(self):
        """ Check decoding produces the correct values """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        
        uid = pdu.user_information.user_data[1]
        
        self.assertEqual(uid.item_length, 32)
        self.assertEqual(uid.implementation_class_uid, UID('1.2.826.0.1.3680043.9.3811.0.9.0'))

    def test_encode(self):
        """ Check encoding produces the correct output """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        
        uid = pdu.user_information.user_data[1]
        
        s = uid.encode()
        
        self.assertEqual(s, implementation_class_uid)

    def test_to_primitive(self):
        """ Check converting to primitive """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        
        uid = pdu.user_information.user_data[1]
        
        result = uid.ToParams()
        
        check = ImplementationClassUIDParameters()
        check.ImplementationClassUID = UID('1.2.826.0.1.3680043.9.3811.0.9.0')
        self.assertEqual(result, check)
        
    def test_from_primitive(self):
        """ Check converting from primitive """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        
        orig_uid = pdu.user_information.user_data[1]
        params = orig_uid.ToParams()
        
        new_uid = ImplementationClassUIDSubItem()
        new_uid.FromParams(params)
        
        self.assertEqual(orig_uid, new_uid)

    def test_properies(self):
        """ Check property setters and getters """
        uid = ImplementationClassUIDSubItem()
        uid.implementation_class_uid = '1.2.826.0.1.3680043.9.3811.0.9.1'
        
        self.assertEqual(uid.implementation_class_uid, UID('1.2.826.0.1.3680043.9.3811.0.9.1'))
        
        uid.implementation_class_uid = b'1.2.826.0.1.3680043.9.3811.0.9.2'
        self.assertEqual(uid.implementation_class_uid, UID('1.2.826.0.1.3680043.9.3811.0.9.2'))
        
        uid.implementation_class_uid = UID('1.2.826.0.1.3680043.9.3811.0.9.3')
        self.assertEqual(uid.implementation_class_uid, UID('1.2.826.0.1.3680043.9.3811.0.9.3'))
        
        with self.assertRaises(TypeError):
            uid.implementation_class_uid = 10002

class TestPDUItem_UserInformation_ImplementationVersion(unittest.TestCase):
    def test_stream_decode(self):
        """ Check decoding produces the correct values """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        
        version = pdu.user_information.user_data[2]
        
        self.assertEqual(version.item_length, 14)
        self.assertEqual(version.implementation_version_name, b'PYNETDICOM_090')

    def test_encode(self):
        """ Check encoding produces the correct output """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        
        version = pdu.user_information.user_data[2]
        version.implementation_version_name = b'PYNETDICOM_090'
        
        s = version.encode()

        self.assertEqual(s, implementation_version_name)

    def test_to_primitive(self):
        """ Check converting to primitive """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        
        version = pdu.user_information.user_data[2]
        
        result = version.ToParams()
        
        check = ImplementationVersionNameParameters()
        check.ImplementationVersionName = b'PYNETDICOM_090'
        self.assertEqual(result, check)
        
    def test_from_primitive(self):
        """ Check converting from primitive """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        
        orig_version = pdu.user_information.user_data[2]
        params = orig_version.ToParams()
        
        new_version = ImplementationVersionNameSubItem()
        new_version.FromParams(params)
        
        self.assertEqual(orig_version, new_version)

    def test_properies(self):
        """ Check property setters and getters """
        version = ImplementationVersionNameSubItem()
        
        version.implementation_version_name = 'PYNETDICOM'
        self.assertEqual(version.implementation_version_name, b'PYNETDICOM')
        
        version.implementation_version_name = b'PYNETDICOM_090'
        self.assertEqual(version.implementation_version_name, b'PYNETDICOM_090')
        
        with self.assertRaises(TypeError):
            version.implementation_version_name = 10002

class TestPDUItem_UserInformation_Asynchronous(unittest.TestCase):
    def test_stream_decode(self):
        """ Check decoding produces the correct values """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        return
        uid = pdu.user_information.user_data[1]
        
        self.assertEqual(uid.item_length, 27)
        self.assertEqual(uid.implementation_class_uid, UID('1.2.276.0.7230010.3.0.3.6.0'))

    def test_encode(self):
        """ Check encoding produces the correct output """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        return
        uid = pdu.user_information.user_data[1]
        
        s = uid.encode()
        
        #for ii in wrap_list(s):
        #    print(ii)

        self.assertEqual(s, implementation_class_uid)

    def test_to_primitive(self):
        """ Check converting to primitive """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        return
        uid = pdu.user_information.user_data[1]
        
        result = uid.ToParams()
        
        check = ImplementationClassUIDParameters()
        check.ImplementationClassUID = UID('1.2.276.0.7230010.3.0.3.6.0')
        self.assertEqual(result, check)
        
    def test_from_primitive(self):
        """ Check converting from primitive """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)
        return
        orig_uid = pdu.user_information.user_data[1]
        params = orig_uid.ToParams()
        
        new_uid = ImplementationClassUIDSubItem()
        new_uid.FromParams(params)
        
        self.assertEqual(orig_uid, new_uid)

    def test_properies(self):
        """ Check property setters and getters """
        return
        uid = ImplementationClassUIDSubItem()
        uid.implementation_class_uid = '1.2.276.0.7230010.3.0.3.6.0'
        
        self.assertEqual(uid.implementation_class_uid, UID('1.2.276.0.7230010.3.0.3.6.0'))
        
        uid.implementation_class_uid = b'1.2.276.0.7230010.3.0.3.6.0'
        self.assertEqual(uid.implementation_class_uid, UID('1.2.276.0.7230010.3.0.3.6.0'))
        
        uid.implementation_class_uid = UID('1.2.276.0.7230010.3.0.3.6.0')
        self.assertEqual(uid.implementation_class_uid, UID('1.2.276.0.7230010.3.0.3.6.0'))
        
        with self.assertRaises(TypeError):
            uid.implementation_class_uid = 10002

class TestPDUItem_UserInformation_RoleSelection(unittest.TestCase):
    def test_stream_decode(self):
        """ Check decoding produces the correct values """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq_role)

        rs = pdu.user_information.role_selection

        self.assertEqual(rs[0].item_type, 0x54)
        self.assertEqual(rs[0].item_length, 29)
        self.assertEqual(rs[0].uid_length, 25)
        self.assertEqual(rs[0].sop_class_uid, UID('1.2.840.10008.5.1.4.1.1.2'))
        self.assertEqual(rs[0].scu_role, 0)
        self.assertEqual(rs[0].scp_role, 1)

    def test_encode(self):
        """ Check encoding produces the correct output """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq_role)

        rs = pdu.user_information.role_selection
        
        s = rs[0].encode()

        self.assertEqual(s, role_selection)

    def test_to_primitive(self):
        """ Check converting to primitive """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq_role)

        rs = pdu.user_information.role_selection
        
        result = rs[0].ToParams()
        
        check = SCP_SCU_RoleSelectionParameters()
        check.SOPClassUID = UID('1.2.840.10008.5.1.4.1.1.2')
        check.SCURole = 0
        check.SCPRole = 1

        self.assertEqual(result, check)
        
    def test_from_primitive(self):
        """ Check converting from primitive """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq_role)

        rs = pdu.user_information.role_selection
        orig = rs[0]
        params = orig.ToParams()
        
        new = SCP_SCU_RoleSelectionSubItem()
        new.FromParams(params)
        
        self.assertEqual(orig, new)

    def test_properies(self):
        """ Check property setters and getters """
        item = SCP_SCU_RoleSelectionSubItem()
        
        # SOP Class UID
        item.sop_class_uid = '1.2.276.0.7230010.3.0.3.6.0'
        self.assertEqual(item.sop_class_uid, UID('1.2.276.0.7230010.3.0.3.6.0'))
        item.implementation_class_uid = b'1.2.276.0.7230010.3.0.3.6.0'
        self.assertEqual(item.sop_class_uid, UID('1.2.276.0.7230010.3.0.3.6.0'))
        item.implementation_class_uid = UID('1.2.276.0.7230010.3.0.3.6.0')
        self.assertEqual(item.sop_class_uid, UID('1.2.276.0.7230010.3.0.3.6.0'))
        
        self.assertEqual(item.UID, item.sop_class_uid)
        
        with self.assertRaises(TypeError):
            item.sop_class_uid = 10002

        # SCU Role
        item.scu_role = 0
        self.assertEqual(item.SCU, 0)
        item.scu_role = 1
        self.assertEqual(item.SCU, 1)
        self.assertEqual(item.SCU, item.scu_role)
        
        with self.assertRaises(ValueError):
            item.scu_role = 2
        
        # SCP Role
        item.scp_role = 0
        self.assertEqual(item.SCP, 0)
        item.scp_role = 1
        self.assertEqual(item.SCP, 1)
        self.assertEqual(item.SCP, item.scp_role)
        
        with self.assertRaises(ValueError):
            item.scp_role = 2

class TestPDUItem_UserInformation_UserIdentityRQ_UserNoPass(unittest.TestCase):
    def test_decode(self):
        """ Check decoding produces the correct values """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq_user_id_user_nopw)

        ui = pdu.user_information.user_identity
        
        self.assertEqual(ui.item_type, 0x58)
        self.assertEqual(ui.item_length, 16)
        self.assertEqual(ui.user_identity_type, 1)
        self.assertEqual(ui.positive_response_requested, 1)
        self.assertEqual(ui.primary_field_length, 10)
        self.assertEqual(ui.primary_field, b'pynetdicom')
        self.assertEqual(ui.secondary_field_length, 0)
        self.assertEqual(ui.secondary_field, None)

    def test_encode(self):
        """ Check encoding produces the correct output """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq_user_id_user_nopw)

        ui = pdu.user_information.user_identity
        
        s = ui.encode()

        self.assertEqual(s, user_identity_rq_user_nopw)

    def test_to_primitive(self):
        """ Check converting to primitive """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq_user_id_user_nopw)

        ui = pdu.user_information.user_identity
        
        result = ui.ToParams()
        
        check = UserIdentityParameters()
        check.UserIdentityType = 1
        check.PositiveResponseRequested = 1
        check.PrimaryField = b'pynetdicom'
        check.SecondaryField = None

        self.assertEqual(result, check)
    
    def test_from_primitive(self):
        """ Check converting from primitive """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq_user_id_user_nopw)

        orig = pdu.user_information.user_identity
        params = orig.ToParams()
        
        new = UserIdentitySubItemRQ()
        new.FromParams(params)
        
        self.assertEqual(orig, new)
    
    def test_properies(self):
        """ Check property setters and getters """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq_user_id_user_nopw)

        ui = pdu.user_information.user_identity
        
        self.assertEqual(ui.id_type, 1)
        self.assertEqual(ui.id_type_str, 'username')
        self.assertEqual(ui.response_requested, 1)

class TestPDUItem_UserInformation_UserIdentityRQ_UserPass(unittest.TestCase):
    def test_decode(self):
        """ Check decoding produces the correct values """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq_user_id_user_pass)

        ui = pdu.user_information.user_identity
        
        self.assertEqual(ui.item_type, 0x58)
        self.assertEqual(ui.item_length, 24)
        self.assertEqual(ui.user_identity_type, 2)
        self.assertEqual(ui.positive_response_requested, 0)
        self.assertEqual(ui.primary_field_length, 10)
        self.assertEqual(ui.primary_field, b'pynetdicom')
        self.assertEqual(ui.secondary_field_length, 8)
        self.assertEqual(ui.secondary_field, b'p4ssw0rd')

    def test_encode(self):
        """ Check encoding produces the correct output """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq_user_id_user_pass)

        ui = pdu.user_information.user_identity
        
        s = ui.encode()
        
        self.assertEqual(s, user_identity_rq_user_pass)

    def test_to_primitive(self):
        """ Check converting to primitive """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq_user_id_user_pass)

        ui = pdu.user_information.user_identity
        
        result = ui.ToParams()
        
        check = UserIdentityParameters()
        check.UserIdentityType = 2
        check.PositiveResponseRequested = 0
        check.PrimaryField = b'pynetdicom'
        check.SecondaryField = b'p4ssw0rd'

        self.assertEqual(result, check)
    
    def test_from_primitive(self):
        """ Check converting from primitive """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq_user_id_user_pass)

        orig = pdu.user_information.user_identity
        params = orig.ToParams()
        
        new = UserIdentitySubItemRQ()
        new.FromParams(params)
        
        self.assertEqual(orig, new)
    
    def test_properies(self):
        """ Check property setters and getters """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq_user_id_user_pass)

        ui = pdu.user_information.user_identity
        
        self.assertEqual(ui.id_type, 2)
        self.assertEqual(ui.id_type_str, 'username/password')
        self.assertEqual(ui.response_requested, 0)


    
if __name__ == "__main__":
    unittest.main()
