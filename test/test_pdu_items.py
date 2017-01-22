#!/usr/bin/env python

import logging
import unittest

from pydicom.uid import UID

from pynetdicom3 import StorageSOPClassList, QueryRetrieveSOPClassList
from pynetdicom3.PDU import A_ASSOCIATE_RQ_PDU, A_ASSOCIATE_AC_PDU, \
                            P_DATA_TF_PDU, \
                            MaximumLengthSubItem, \
                            ImplementationClassUIDSubItem, \
                            ImplementationVersionNameSubItem, \
                            AsynchronousOperationsWindowSubItem, \
                            SCP_SCU_RoleSelectionSubItem, \
                            SOPClassExtendedNegotiationSubItem, \
                            SOPClassCommonExtendedNegotiationSubItem, \
                            UserIdentitySubItemRQ, \
                            ApplicationContextItem, \
                            PresentationContextItemAC, \
                            PresentationContextItemRQ, \
                            UserInformationItem, \
                            TransferSyntaxSubItem, \
                            PresentationDataValueItem, \
                            AbstractSyntaxSubItem
from pynetdicom3.primitives import SOPClassExtendedNegotiation, \
                                   SOPClassCommonExtendedNegotiation, \
                                   MaximumLengthNegotiation, \
                                   ImplementationClassUIDNotification, \
                                   ImplementationVersionNameNotification, \
                                   SCP_SCU_RoleSelectionNegotiation, \
                                   AsynchronousOperationsWindowNegotiation, \
                                   UserIdentityNegotiation
from pynetdicom3.utils import wrap_list, PresentationContext

## A-ASSOCIATE-RQ PDU
# Called AET: ANY-SCP
# Callign AET: ECHOSCU
# Application Context Name: 1.2.840.10008.3.1.1.1
# 1.2.840.10008.1.1
# Presentation Context Items:
#   Presentation Context ID: 1
#   Abstract Syntax: 1.2.840.10008.1.1
#   Transfer Syntax: 1.2.840.10008.1.2
# User Information
#   Max Length Received: 16382
#   Implementation Class UID: 1.2.826.0.1.3680043.9.3811.0.9.0
#   Implementation Version Name: PYNETDICOM_090
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

a_associate_rq_user_async = b'\x01\x00\x00\x00\x00\xed\x00\x01\x00\x00\x41\x4e\x59\x2d\x53\x43' \
                            b'\x50\x20\x20\x20\x20\x20\x20\x20\x20\x20\x45\x43\x48\x4f\x53\x43' \
                            b'\x55\x20\x20\x20\x20\x20\x20\x20\x20\x20\x00\x00\x00\x00\x00\x00' \
                            b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' \
                            b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x10\x00\x00\x15\x31\x2e' \
                            b'\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x33\x2e\x31\x2e' \
                            b'\x31\x2e\x31\x20\x00\x00\x2e\x01\x00\x00\x00\x30\x00\x00\x11\x31' \
                            b'\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x31\x2e\x31' \
                            b'\x40\x00\x00\x11\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30' \
                            b'\x38\x2e\x31\x2e\x32\x50\x00\x00\x5a\x51\x00\x00\x04\x00\x00\x3f' \
                            b'\xfe\x52\x00\x00\x20\x31\x2e\x32\x2e\x38\x32\x36\x2e\x30\x2e\x31' \
                            b'\x2e\x33\x36\x38\x30\x30\x34\x33\x2e\x39\x2e\x33\x38\x31\x31\x2e' \
                            b'\x30\x2e\x39\x2e\x30\x55\x00\x00\x0e\x50\x59\x4e\x45\x54\x44\x49' \
                            b'\x43\x4f\x4d\x5f\x30\x39\x30\x58\x00\x00\x10\x01\x01\x00\x0a\x70' \
                            b'\x79\x6e\x65\x74\x64\x69\x63\x6f\x6d\x00\x00\x53\x00\x00\x04\x00' \
                            b'\x05\x00\x05'

asynchronous_window_ops = b'\x53\x00\x00\x04\x00\x05\x00\x05'

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

# CTImageStorage and MRImageStorage
a_associate_rq_user_id_ext_neg = b'\x01\x00\x00\x00\x01\xab\x00\x01\x00\x00\x41\x4e\x59\x2d\x53\x43' \
                                 b'\x50\x20\x20\x20\x20\x20\x20\x20\x20\x20\x45\x43\x48\x4f\x53\x43' \
                                 b'\x55\x20\x20\x20\x20\x20\x20\x20\x20\x20\x00\x00\x00\x00\x00\x00' \
                                 b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' \
                                 b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x10\x00\x00\x15\x31\x2e' \
                                 b'\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x33\x2e\x31\x2e' \
                                 b'\x31\x2e\x31\x20\x00\x00\x2e\x01\x00\x00\x00\x30\x00\x00\x11\x31' \
                                 b'\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x31\x2e\x31' \
                                 b'\x40\x00\x00\x11\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30' \
                                 b'\x38\x2e\x31\x2e\x32\x20\x00\x00\x36\x03\x00\x00\x00\x30\x00\x00' \
                                 b'\x19\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x35' \
                                 b'\x2e\x31\x2e\x34\x2e\x31\x2e\x31\x2e\x32\x40\x00\x00\x11\x31\x2e' \
                                 b'\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x31\x2e\x32\x20' \
                                 b'\x00\x00\x36\x05\x00\x00\x00\x30\x00\x00\x19\x31\x2e\x32\x2e\x38' \
                                 b'\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x35\x2e\x31\x2e\x34\x2e\x31' \
                                 b'\x2e\x31\x2e\x34\x40\x00\x00\x11\x31\x2e\x32\x2e\x38\x34\x30\x2e' \
                                 b'\x31\x30\x30\x30\x38\x2e\x31\x2e\x32\x50\x00\x00\xa4\x51\x00\x00' \
                                 b'\x04\x00\x00\x3f\xfe\x52\x00\x00\x20\x31\x2e\x32\x2e\x38\x32\x36' \
                                 b'\x2e\x30\x2e\x31\x2e\x33\x36\x38\x30\x30\x34\x33\x2e\x39\x2e\x33' \
                                 b'\x38\x31\x31\x2e\x30\x2e\x39\x2e\x30\x55\x00\x00\x0e\x50\x59\x4e' \
                                 b'\x45\x54\x44\x49\x43\x4f\x4d\x5f\x30\x39\x30\x58\x00\x00\x10\x01' \
                                 b'\x01\x00\x0a\x70\x79\x6e\x65\x74\x64\x69\x63\x6f\x6d\x00\x00\x53' \
                                 b'\x00\x00\x04\x00\x05\x00\x05\x56\x00\x00\x21\x00\x19\x31\x2e\x32' \
                                 b'\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x35\x2e\x31\x2e\x34' \
                                 b'\x2e\x31\x2e\x31\x2e\x32\x02\x00\x03\x00\x01\x00\x56\x00\x00\x21' \
                                 b'\x00\x19\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e' \
                                 b'\x35\x2e\x31\x2e\x34\x2e\x31\x2e\x31\x2e\x34\x02\x00\x03\x00\x01' \
                                 b'\x00'

a_associate_ac_user_id_user_pass = b'\x02\x00\x00\x00\x00\xbe\x00\x01\x00\x00\x41\x4e\x59\x2d\x53\x43' \
                                   b'\x50\x20\x20\x20\x20\x20\x20\x20\x20\x20\x53\x54\x4f\x52\x45\x53' \
                                   b'\x43\x55\x20\x20\x20\x20\x20\x20\x20\x20\x00\x00\x00\x00\x00\x00' \
                                   b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' \
                                   b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x10\x00\x00\x15\x31\x2e' \
                                   b'\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x33\x2e\x31\x2e' \
                                   b'\x31\x2e\x31\x21\x00\x00\x19\x01\x00\x00\x00\x40\x00\x00\x11\x31' \
                                   b'\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x31\x2e\x32' \
                                   b'\x50\x00\x00\x40\x51\x00\x00\x04\x00\x00\x40\x00\x52\x00\x00\x1b' \
                                   b'\x31\x2e\x32\x2e\x32\x37\x36\x2e\x30\x2e\x37\x32\x33\x30\x30\x31' \
                                   b'\x30\x2e\x33\x2e\x30\x2e\x33\x2e\x36\x2e\x30\x55\x00\x00\x0f\x4f' \
                                   b'\x46\x46\x49\x53\x5f\x44\x43\x4d\x54\x4b\x5f\x33\x36\x30\x58\x00' \
                                   b'\x00\x02\x00\x00'

a_associate_rq_com_ext_neg = b'\x02\x00\x00\x00\x01\x49\x00\x01\x00\x00\x41\x4e\x59\x2d\x53\x43' \
                             b'\x50\x20\x20\x20\x20\x20\x20\x20\x20\x20\x45\x43\x48\x4f\x53\x43' \
                             b'\x55\x20\x20\x20\x20\x20\x20\x20\x20\x20\x00\x00\x00\x00\x00\x00' \
                             b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' \
                             b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x10\x00\x00\x15\x31\x2e' \
                             b'\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x33\x2e\x31\x2e' \
                             b'\x31\x2e\x31\x21\x00\x00\x19\x01\x00\x00\x00\x40\x00\x00\x11\x31' \
                             b'\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x31\x2e\x32' \
                             b'\x21\x00\x00\x19\x03\x00\x00\x00\x40\x00\x00\x11\x31\x2e\x32\x2e' \
                             b'\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x31\x2e\x32\x21\x00\x00' \
                             b'\x19\x05\x00\x00\x00\x40\x00\x00\x11\x31\x2e\x32\x2e\x38\x34\x30' \
                             b'\x2e\x31\x30\x30\x30\x38\x2e\x31\x2e\x32\x50\x00\x00\x91\x51\x00' \
                             b'\x00\x04\x00\x00\x40\x00\x52\x00\x00\x20\x31\x2e\x32\x2e\x38\x32' \
                             b'\x36\x2e\x30\x2e\x31\x2e\x33\x36\x38\x30\x30\x34\x33\x2e\x39\x2e' \
                             b'\x33\x38\x31\x31\x2e\x30\x2e\x39\x2e\x30\x55\x00\x00\x0e\x50\x59' \
                             b'\x4e\x45\x54\x44\x49\x43\x4f\x4d\x5f\x30\x39\x30\x57\x00\x00\x4d' \
                             b'\x00\x19\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e' \
                             b'\x35\x2e\x31\x2e\x34\x2e\x31\x2e\x31\x2e\x34\x00\x11\x31\x2e\x32' \
                             b'\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x34\x2e\x32\x00\x1d' \
                             b'\x00\x1d\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e' \
                             b'\x35\x2e\x31\x2e\x34\x2e\x31\x2e\x31\x2e\x38\x38\x2e\x32\x32'

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

user_information = b'\x50\x00\x00\x3e\x51\x00\x00\x04\x00\x00\x3f\xfe\x52\x00\x00\x20' \
            b'\x31\x2e\x32\x2e\x38\x32\x36\x2e\x30\x2e\x31\x2e\x33\x36\x38\x30' \
            b'\x30\x34\x33\x2e\x39\x2e\x33\x38\x31\x31\x2e\x30\x2e\x39\x2e\x30' \
            b'\x55\x00\x00\x0e\x50\x59\x4e\x45\x54\x44\x49\x43\x4f\x4d\x5f\x30' \
            b'\x39\x30'

extended_negotiation = b'\x56\x00\x00\x21\x00\x19\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30' \
                       b'\x30\x30\x38\x2e\x35\x2e\x31\x2e\x34\x2e\x31\x2e\x31\x2e\x32\x02' \
                       b'\x00\x03\x00\x01\x00'

common_extended_negotiation = b'\x57\x00\x00\x4d\x00\x19\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30' \
                              b'\x30\x30\x38\x2e\x35\x2e\x31\x2e\x34\x2e\x31\x2e\x31\x2e\x34\x00' \
                              b'\x11\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x34' \
                              b'\x2e\x32\x00\x1d\x00\x1d\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30' \
                              b'\x30\x30\x38\x2e\x35\x2e\x31\x2e\x34\x2e\x31\x2e\x31\x2e\x38\x38' \
                              b'\x2e\x32\x32'

logger = logging.getLogger('pynetdicom3')
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

    def test_encode(self):
        """ Check encoding produces the correct output """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)

        user_info = pdu.user_information

        s = user_info.encode()

        #for ii in wrap_list(s):
        #        print(ii)

        self.assertEqual(s, user_information)

    def test_to_primitive(self):
        """ Check converting to primitive """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq)

        ui = pdu.user_information

        result = ui.ToParams()

        check = []
        max_pdu = MaximumLengthNegotiation()
        max_pdu.maximum_length_received = 16382
        check.append(max_pdu)
        class_uid = ImplementationClassUIDNotification()
        class_uid.implementation_class_uid = UID('1.2.826.0.1.3680043.9.3811.0.9.0')
        check.append(class_uid)
        v_name = ImplementationVersionNameNotification()
        v_name.implementation_version_name = b'PYNETDICOM_090'
        check.append(v_name)

        self.assertEqual(result, check)

    def test_from_primitive(self):
        """ Check converting from primitive """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq_user_async)

        orig = pdu.user_information
        params = orig.ToParams()

        new = UserInformationItem()
        new.FromParams(params)

        self.assertEqual(orig, new)

    def test_properties_usr_id(self):
        """ Check user id properties are OK """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq_user_async)

        ui = pdu.user_information

        self.assertTrue(isinstance(ui.user_identity, UserIdentitySubItemRQ))

    def test_properties_ext_neg(self):
        """ Check extended neg properties are OK """
        '''
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq_user_async)

        ui = pdu.user_information

        self.assertTrue(isinstance(ui.user_identity, UserIdentitySubItemRQ))
        '''
        pass

    def test_properties_role(self):
        """ Check user id properties are OK """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq_role)

        ui = pdu.user_information

        for role in ui.role_selection:
            self.assertTrue(isinstance(role, SCP_SCU_RoleSelectionSubItem))

    def test_properties_async(self):
        """ Check async window ops properties are OK """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq_user_async)

        ui = pdu.user_information

        self.assertEqual(ui.max_operations_invoked, 5)
        self.assertEqual(ui.max_operations_performed, 5)

        self.assertTrue(isinstance(ui.async_ops_window, AsynchronousOperationsWindowSubItem))

    def test_properties_max_pdu(self):
        """ Check max receive properties are OK """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq_role)

        ui = pdu.user_information

        self.assertEqual(ui.maximum_length, 16382)

    def test_properties_implementation(self):
        """ Check async window ops properties are OK """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq_role)

        ui = pdu.user_information

        self.assertEqual(ui.implementation_class_uid, UID('1.2.826.0.1.3680043.9.3811.0.9.0'))
        self.assertEqual(ui.implementation_version_name, 'PYNETDICOM_090')

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

        check = MaximumLengthNegotiation()
        check.maximum_length_received = 16382

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

        check = ImplementationClassUIDNotification()
        check.implementation_class_uid = UID('1.2.826.0.1.3680043.9.3811.0.9.0')
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

        check = ImplementationVersionNameNotification()
        check.implementation_version_name = b'PYNETDICOM_090'
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
        pdu.Decode(a_associate_rq_user_async)

        for item in pdu.user_information.user_data:
            if isinstance(item, AsynchronousOperationsWindowSubItem):
                async = item

                self.assertEqual(async.item_length, 4)
                self.assertEqual(async.maximum_number_operations_invoked, 5)
                self.assertEqual(async.maximum_number_operations_performed, 5)

    def test_encode(self):
        """ Check encoding produces the correct output """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq_user_async)
        for item in pdu.user_information.user_data:
            if isinstance(item, AsynchronousOperationsWindowSubItem):
                async = item

                s = async.encode()

                #for ii in wrap_list(s):
                #    print(ii)

                self.assertEqual(s, asynchronous_window_ops)

    def test_to_primitive(self):
        """ Check converting to primitive """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq_user_async)
        for item in pdu.user_information.user_data:
            if isinstance(item, AsynchronousOperationsWindowSubItem):
                async = item

                result = async.ToParams()

                check = AsynchronousOperationsWindowNegotiation()
                check.maximum_number_operations_invoked = 5
                check.maximum_number_operations_performed = 5
                self.assertEqual(result, check)

    def test_from_primitive(self):
        """ Check converting from primitive """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq_user_async)

        for item in pdu.user_information.user_data:
            if isinstance(item, AsynchronousOperationsWindowSubItem):
                orig = item
                params = orig.ToParams()

                new = AsynchronousOperationsWindowSubItem()
                new.FromParams(params)

                self.assertEqual(orig, new)

    def test_properies(self):
        """ Check property setters and getters """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq_user_async)

        for item in pdu.user_information.user_data:
            if isinstance(item, AsynchronousOperationsWindowSubItem):
                async = item

        self.assertEqual(item.max_operations_invoked, 5)
        self.assertEqual(item.max_operations_performed, 5)

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

        check = SCP_SCU_RoleSelectionNegotiation()
        check.sop_class_uid = UID('1.2.840.10008.5.1.4.1.1.2')
        check.scu_role = False
        check.scp_role = True

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

        check = UserIdentityNegotiation()
        check.user_identity_type = 1
        check.positive_response_requested = True
        check.primary_field = b'pynetdicom'
        check.secondary_field = None

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
        self.assertEqual(ui.id_type_str, 'Username')
        self.assertEqual(ui.primary, b'pynetdicom')
        self.assertEqual(ui.response_requested, True)
        self.assertEqual(ui.secondary, None)

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

        check = UserIdentityNegotiation()
        check.user_identity_type = 2
        check.positive_response_requested = False
        check.primary_field = b'pynetdicom'
        check.secondary_field = b'p4ssw0rd'

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
        self.assertEqual(ui.id_type_str, 'Username/Password')
        self.assertEqual(ui.primary, b'pynetdicom')
        self.assertEqual(ui.response_requested, False)
        self.assertEqual(ui.secondary, b'p4ssw0rd')

# FIXME: Add tests for UserIdentityRQ SAML
class TestPDUItem_UserInformation_UserIdentityRQ_SAML(unittest.TestCase):
    pass

# FIXME: Add tests for UserIdentityRQ Kerberos
class TestPDUItem_UserInformation_UserIdentityRQ_Kerberos(unittest.TestCase):
    pass


# FIXME: Add tests for UserIdentityAC User no pass
class TestPDUItem_UserInformation_UserIdentityAC_UserNoPassNoResponse(unittest.TestCase):
    pass

class TestPDUItem_UserInformation_UserIdentityAC_UserNoPassResponse(unittest.TestCase):
    pass

# FIXME: Add tests for UserIdentityAC User pass
class TestPDUItem_UserInformation_UserIdentityAC_UserPassNoResponse(unittest.TestCase):
    pass

class TestPDUItem_UserInformation_UserIdentityAC_UserPassResponse(unittest.TestCase):
    pass

# FIXME: Add tests for UserIdentityAC SAML
class TestPDUItem_UserInformation_UserIdentityAC_SAMLNoResponse(unittest.TestCase):
    pass

class TestPDUItem_UserInformation_UserIdentityAC_SAMLResponse(unittest.TestCase):
    pass

# FIXME: Add tests for UserIdentityAC Kerberos
class TestPDUItem_UserInformation_UserIdentityAC_KerberosNoResponse(unittest.TestCase):
    pass

class TestPDUItem_UserInformation_UserIdentityAC_KerberosResponse(unittest.TestCase):
    pass


class TestPDUItem_UserInformation_ExtendedNegotiation(unittest.TestCase):
    def test_decode(self):
        """ Check decoding produces the correct values """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq_user_id_ext_neg)

        item = pdu.user_information.ext_neg[0]

        self.assertEqual(item.item_type, 0x56)
        self.assertEqual(item.item_length, 33)
        self.assertEqual(item.sop_class_uid_length, 25)
        self.assertEqual(item.sop_class_uid, UID('1.2.840.10008.5.1.4.1.1.2'))
        self.assertEqual(item.service_class_application_information, b'\x02\x00\x03\x00\x01\x00')

    def test_encode(self):
        """ Check encoding produces the correct output """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq_user_id_ext_neg)

        item = pdu.user_information.ext_neg[0]

        s = item.encode()

        self.assertEqual(s, extended_negotiation)

    def test_to_primitive(self):
        """ Check converting to primitive """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq_user_id_ext_neg)

        item = pdu.user_information.ext_neg[0]

        result = item.ToParams()

        check = SOPClassExtendedNegotiation()

        check.sop_class_uid = UID('1.2.840.10008.5.1.4.1.1.2')
        check.service_class_application_information = b'\x02\x00\x03\x00\x01\x00'

        self.assertEqual(result, check)

    def test_from_primitive(self):
        """ Check converting from primitive """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq_user_id_ext_neg)

        orig = pdu.user_information.ext_neg[0]
        params = orig.ToParams()

        new = SOPClassExtendedNegotiationSubItem()
        new.FromParams(params)

        self.assertEqual(orig, new)

    def test_properties(self):
        """ Check property setters and getters """
        item = SOPClassExtendedNegotiationSubItem()

        # SOP Class UID
        item.sop_class_uid = '1.2'
        self.assertEqual(item.sop_class_uid, UID('1.2'))
        self.assertEqual(item.sop_class_uid_length, 3)
        item.sop_class_uid = b'1.2.3'
        self.assertEqual(item.sop_class_uid, UID('1.2.3'))
        self.assertEqual(item.sop_class_uid_length, 5)
        item.sop_class_uid = UID('1.2.3.4')
        self.assertEqual(item.sop_class_uid, UID('1.2.3.4'))
        self.assertEqual(item.sop_class_uid_length, 7)

        self.assertEqual(item.UID, item.sop_class_uid)

        with self.assertRaises(TypeError):
            item.sop_class_uid = 10002

        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq_user_id_ext_neg)

        item = pdu.user_information.ext_neg[0]

        self.assertEqual(item.app_info, b'\x02\x00\x03\x00\x01\x00')


class TestPDUItem_UserInformation_CommonExtendedNegotiation(unittest.TestCase):
    def test_decode(self):
        """ Check decoding produces the correct values """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq_com_ext_neg)

        item = pdu.user_information.common_ext_neg[0]

        self.assertEqual(item.item_type, 0x57)
        self.assertEqual(item.item_length, 77)
        self.assertEqual(item.sop_class_uid_length, 25)
        self.assertEqual(item.sop_class_uid, UID('1.2.840.10008.5.1.4.1.1.4'))
        self.assertEqual(item.service_class_uid, UID('1.2.840.10008.4.2'))
        self.assertEqual(item.related_general_sop_class_identification, [UID('1.2.840.10008.5.1.4.1.1.88.22')])

    def test_encode(self):
        """ Check encoding produces the correct output """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq_com_ext_neg)

        item = pdu.user_information.common_ext_neg[0]

        s = item.encode()

        self.assertEqual(s, common_extended_negotiation)

    def test_to_primitive(self):
        """ Check converting to primitive """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq_com_ext_neg)

        item = pdu.user_information.common_ext_neg[0]

        result = item.ToParams()

        check = SOPClassCommonExtendedNegotiation()

        check.sop_class_uid = UID('1.2.840.10008.5.1.4.1.1.4')
        check.service_class_uid = UID('1.2.840.10008.4.2')
        check.related_general_sop_class_identification = [UID('1.2.840.10008.5.1.4.1.1.88.22')]

        self.assertEqual(result, check)

    def test_from_primitive(self):
        """ Check converting from primitive """
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(a_associate_rq_com_ext_neg)

        orig = pdu.user_information.common_ext_neg[0]
        params = orig.ToParams()

        new = SOPClassCommonExtendedNegotiationSubItem()
        new.FromParams(params)

        self.assertEqual(orig, new)

    def test_properies(self):
        """ Check property setters and getters """
        item = SOPClassCommonExtendedNegotiationSubItem()

        # SOP Class UID
        item.sop_class_uid = '1.1'
        self.assertEqual(item.sop_class_uid, UID('1.1'))
        self.assertEqual(item.sop_class_uid_length, 3)

        with self.assertRaises(TypeError):
            item.sop_class_uid = 10002

        # Service Class UID
        item.service_class_uid = '1.2'
        self.assertEqual(item.service_class_uid, UID('1.2'))
        self.assertEqual(item.service_class_uid_length, 3)
        item.service_class_uid = b'1.2.3'
        self.assertEqual(item.service_class_uid, UID('1.2.3'))
        self.assertEqual(item.service_class_uid_length, 5)
        item.service_class_uid = UID('1.2.3.4')
        self.assertEqual(item.service_class_uid, UID('1.2.3.4'))
        self.assertEqual(item.service_class_uid_length, 7)

        with self.assertRaises(TypeError):
            item.service_class_uid = 10002

        # Related General SOP Class UID
        item.related_general_sop_class_identification = ['1.2']
        self.assertEqual(item.related_general_sop_class_identification, [UID('1.2')])
        self.assertEqual(item.related_general_sop_class_identification_length, 3)
        item.related_general_sop_class_identification = [b'1.2.3']
        self.assertEqual(item.related_general_sop_class_identification, [UID('1.2.3')])
        self.assertEqual(item.related_general_sop_class_identification_length, 5)
        item.related_general_sop_class_identification = [UID('1.2.3.4')]
        self.assertEqual(item.related_general_sop_class_identification, [UID('1.2.3.4')])
        self.assertEqual(item.related_general_sop_class_identification_length, 7)

        with self.assertRaises(TypeError):
            item.related_general_sop_class_identification = 10002


if __name__ == "__main__":
    unittest.main()
