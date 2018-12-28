"""Unit test coverage for the logging."""

import logging
import sys

import pytest

from pydicom.uid import (
    ImplicitVRLittleEndian, ExplicitVRLittleEndian, ExplicitVRBigEndian,
    DeflatedExplicitVRLittleEndian, JPEGBaseline, JPEGExtended,
    JPEGLosslessP14, JPEGLossless, JPEGLSLossless, JPEGLSLossy,
    JPEG2000Lossless, JPEG2000, JPEG2000MultiComponentLossless,
    JPEG2000MultiComponent, RLELossless,
    generate_uid,
)

from pynetdicom import build_context
from pynetdicom.acse import ACSE, APPLICATION_CONTEXT_NAME
from pynetdicom.pdu import (
    A_ASSOCIATE_RQ,
)
from pynetdicom.pdu_primitives import (
    A_ASSOCIATE,
    MaximumLengthNotification,
    ImplementationClassUIDNotification,
    ImplementationVersionNameNotification,
    SCP_SCU_RoleSelectionNegotiation,
    AsynchronousOperationsWindowNegotiation,
    SOPClassExtendedNegotiation,
    SOPClassCommonExtendedNegotiation,
    UserIdentityNegotiation,
)
from pynetdicom.sop_class import CTImageStorage


LOGGER = logging.getLogger('pynetdicom')
LOGGER.setLevel(logging.CRITICAL)
LOGGER.setLevel(logging.DEBUG)


@pytest.mark.skipif(sys.version_info[:2] == (3, 4), reason='no caplog')
class TestACSELogging(object):
    """Tests for ACSE logging."""
    def setup(self):
        """Setup each test."""
        self.acse = ACSE(5)

        primitive = A_ASSOCIATE()
        primitive.application_context_name = APPLICATION_CONTEXT_NAME
        # Calling AE Title is the source DICOM AE title
        primitive.calling_ae_title = b'ABCDEFGHIJKLMNOP'
        # Called AE Title is the destination DICOM AE title
        primitive.called_ae_title = b'1234567890123456'
        # The TCP/IP address of the source, pynetdicom includes port too
        primitive.calling_presentation_address = ('127.127.127.127', 111112)
        # The TCP/IP address of the destination, pynetdicom includes port too
        primitive.called_presentation_address = ('0.0.0.0', 0)
        # Proposed presentation contexts
        contexts = [
            build_context('1.2.3.4.5.6', JPEGBaseline),
            build_context('1.2.840.10008.1.1')
        ]
        for ii, cx in enumerate(contexts):
            cx.context_id = ii * 2 + 1

        primitive.presentation_context_definition_list = contexts

        item = MaximumLengthNotification()
        item.maximum_length_received = 0
        primitive.user_information.append(item)

        item = ImplementationClassUIDNotification()
        item.implementation_class_uid = generate_uid(entropy_srcs=['lorem'])
        primitive.user_information.append(item)

        self.associate_rq = primitive

    def add_impl_name(self, primitive, name=b'A               '):
        """Add an Implementation Version Name to the A-ASSOCIATE primitive."""
        assert len(name) == 16
        item = ImplementationVersionNameNotification()
        item.implementation_version_name = name
        primitive.user_information.append(item)

        return primitive

    def add_user_identity(self, primitive):
        """Add an Implementation Version Name to the A-ASSOCIATE primitive."""
        pass

    def add_async_ops(self, primitive):
        """Add Asynchronous Ops to the A-ASSOCIATE primitive."""
        item = AsynchronousOperationsWindowNegotiation()
        item.maximum_number_operations_invoked = 2
        item.maximum_number_operations_performed = 3
        primitive.user_information.append(item)

    def add_scp_scu_role(self, primitive):
        """Add SCP/SCU Role Selection to the A-ASSOCIATE primitive."""
        pass

    def add_sop_ext(self, primitive):
        """Add SOP Class Extended to the A-ASSOCIATE primitive."""
        req = {
            '1.2.3.4' : b'\x00\x01',
            '1.2.840.10008.1.1' : b'\x00\x01\x02\x03' * 10
        }

        for uid, data in req.items():
            item = SOPClassExtendedNegotiation()
            item.sop_class_uid = uid
            item.service_class_application_information = data
            primitive.user_information.append(item)

    def add_sop_common(self, primitive):
        """Add SOP Class Common Extended to the A-ASSOCIATE primitive."""
        req = {
            '1.2.3.4' : ('1.2.3', []),
            '1.2.3.4.5' : ('1.2.3', ['1.2.1', '1.4.3']),
            '1.2.840.10008.1.1' : ('1.2.840.10008.4.2', []),
            '1.2.840.10008.1.1.1' : ('1.2.840.10008.4.2',
                                     [CTImageStorage, '1.9.1']),
        }

        for uid, data in req.items():
            item = SOPClassCommonExtendedNegotiation()
            item.sop_class_uid = uid
            item.service_class_uid = data[0]
            item.related_general_sop_class_identification = data[1]
            primitive.user_information.append(item)

    def test_send_assoc_rq_minimal(self, caplog):
        """Test minimal ACSE.debug_send_associate_rq."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            pdu = A_ASSOCIATE_RQ()
            pdu.from_primitive(self.associate_rq)
            self.acse.debug_send_associate_rq(pdu)

            messages = [
                "Our Implementation Class UID:      1.2.826.0.1.3680043.8.498"
                ".10207287587329888519122978685894984263",
                "Calling Application Name:    ABCDEFGHIJKLMNOP",
                "Called Application Name:     1234567890123456",
                "Our Max PDU Receive Size:    0",
                "Presentation Contexts:",
                "Context ID:        1 (Proposed)",
                "Abstract Syntax: =1.2.3.4.5.6",
                "Proposed SCP/SCU Role: Default",
                "Proposed Transfer Syntax:",
                "=JPEG Baseline (Process 1)",
                "Context ID:        3 (Proposed)",
                "Abstract Syntax: =Verification SOP Class",
                "Proposed SCP/SCU Role: Default",
                "Proposed Transfer Syntaxes:",
                "=Implicit VR Little Endian",
                "=Explicit VR Little Endian",
                "=Explicit VR Big Endian",
                "Requested Extended Negotiation: None",
                "Requested Common Extended Negotiation: None",
                "Requested Asynchronous Operations Window Negotiation: None",
                "Requested User Identity Negotiation: None",
            ]

            for msg in messages:
                assert msg in caplog.text

    def test_send_assoc_rq_async(self, caplog):
        """Test minimal ACSE.debug_send_associate_rq."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.add_async_ops(self.associate_rq)
            pdu = A_ASSOCIATE_RQ()
            pdu.from_primitive(self.associate_rq)
            self.acse.debug_send_associate_rq(pdu)

            messages = [
                "Requested Extended Negotiation: None",
                "Requested Common Extended Negotiation: None",
                "Requested Asynchronous Operations Window Negotiation:",
                "Maximum invoked operations:     2",
                "Maximum performed operations:   3",
                "Requested User Identity Negotiation: None",
            ]

            for msg in messages:
                assert msg in caplog.text

    def test_send_assoc_rq_sop_ext(self, caplog):
        """Test minimal ACSE.debug_send_associate_rq."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.add_sop_ext(self.associate_rq)
            pdu = A_ASSOCIATE_RQ()
            pdu.from_primitive(self.associate_rq)
            self.acse.debug_send_associate_rq(pdu)

            messages = [
                "Requested Extended Negotiation:",
                "SOP Class: =1.2.3.4",
                "[ 00  01 ]",
                "SOP Class: =1.2.840.10008.1.1",
                "[ 00  01  02  03  00  01  02  03  00  01  02  03  00  01  02"
                "  03",
                "00  01  02  03  00  01  02  03  00  01  02  03  00  01  02  03",
                "00  01  02  03  00  01  02  03 ]",
                "Requested Common Extended Negotiation: None",
                "Requested Asynchronous Operations Window Negotiation: None",
                "Requested User Identity Negotiation: None",
            ]

            for msg in messages:
                assert msg in caplog.text

    def test_send_assoc_rq_sop_common(self, caplog):
        """Test minimal ACSE.debug_send_associate_rq."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.add_sop_common(self.associate_rq)
            pdu = A_ASSOCIATE_RQ()
            pdu.from_primitive(self.associate_rq)
            self.acse.debug_send_associate_rq(pdu)

            messages = [
                "Requested Extended Negotiation: None",
                "Requested Common Extended Negotiation:",
                "Requested Asynchronous Operations Window Negotiation: None",
                "Requested User Identity Negotiation: None",
            ]

            for msg in messages:
                assert msg in caplog.text
