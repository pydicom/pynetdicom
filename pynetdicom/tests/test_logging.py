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
    A_ASSOCIATE_RQ, A_ASSOCIATE_AC,
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


REFERENCE_USER_ID = [
    (
        (1, b'username', None, False),
        [
            "Authentication Mode: 1 - Username",
            "Username: [username]",
            "Positive Response Requested: No",
        ],
    ),
    (
        (1, b'username', None, True),
        [
            "Authentication Mode: 1 - Username",
            "Username: [username]",
            "Positive Response Requested: Yes",
        ],
    ),
    (
        (2, b'username', b'pass', False),
        [
            "Authentication Mode: 2 - Username/Password",
            "Username: [username]",
            "Password: [pass]",
            "Positive Response Requested: No",
        ],
    ),
    (
        (2, b'username', b'pass', True),
        [
            "Authentication Mode: 2 - Username/Password",
            "Username: [username]",
            "Password: [pass]",
            "Positive Response Requested: Yes",
        ],
    ),
    (
        (3, b'KERBEROS', None, False),
        [
            "Authentication Mode: 3 - Kerberos",
            "Kerberos Service Ticket (not dumped) length: 8",
            "Positive Response Requested: No",
        ],
    ),
    (
        (3, b'KERBEROS', None, True),
        [
            "Authentication Mode: 3 - Kerberos",
            "Kerberos Service Ticket (not dumped) length: 8",
            "Positive Response Requested: Yes",
        ],
    ),
    (
        (4, b'SAML', None, False),
        [
            "Authentication Mode: 4 - SAML",
            "SAML Assertion (not dumped) length: 4",
            "Positive Response Requested: No",
        ],
    ),
    (
        (4, b'SAML', None, True),
        [
            "Authentication Mode: 4 - SAML",
            "SAML Assertion (not dumped) length: 4",
            "Positive Response Requested: Yes",
        ],
    ),
    (
        (5, b'JSON', None, False),
        [
            "Authentication Mode: 5 - JSON Web Token",
            "JSON Web Token (not dumped) length: 4",
            "Positive Response Requested: No",
        ],
    ),
    (
        (5, b'JSON', None, True),
        [
            "Authentication Mode: 5 - JSON Web Token",
            "JSON Web Token (not dumped) length: 4",
            "Positive Response Requested: Yes",
        ],
    )
]


@pytest.mark.skipif(sys.version_info[:2] == (3, 4), reason='no caplog')
class TestACSELogging(object):
    """Tests for ACSE logging."""
    def setup(self):
        """Setup each test."""
        self.acse = ACSE()

        # A-ASSOCIATE (request)
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

        # A-ASSOCIATE (accept)
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
            build_context('1.2.840.10008.1.1'),
            build_context('1.2.840.10008.1.1'),
            build_context('1.2.840.10008.1.1'),
            build_context('1.2.840.10008.1.1'),
        ]
        for ii, cx in enumerate(contexts):
            cx.context_id = ii * 2 + 1
            cx.result = ii

        primitive.presentation_context_definition_results_list = contexts
        primitive.result = 0x00

        item = MaximumLengthNotification()
        item.maximum_length_received = 0
        primitive.user_information.append(item)

        item = ImplementationClassUIDNotification()
        item.implementation_class_uid = generate_uid(entropy_srcs=['lorem'])
        primitive.user_information.append(item)

        self.associate_ac = primitive

    def add_impl_name(self, primitive, name=b'A               '):
        """Add an Implementation Version Name to the A-ASSOCIATE primitive."""
        assert len(name) == 16
        item = ImplementationVersionNameNotification()
        item.implementation_version_name = name
        primitive.user_information.append(item)

        return primitive

    def add_user_identity(self, primitive, id_type, primary, secondary, response):
        """Add User Identity to the A-ASSOCIATE primitive."""
        item = UserIdentityNegotiation()
        item.user_identity_type = id_type
        item.primary_field = primary
        item.secondary_field = secondary
        item.positive_response_requested = response
        primitive.user_information.append(item)

    def add_user_identity_rsp(self, primitive):
        """Add User Identity (rsp) to the A-ASSOCIATE primitive."""
        item = UserIdentityNegotiation()
        item.server_response = b'this is the response'
        primitive.user_information.append(item)

    def add_async_ops(self, primitive):
        """Add Asynchronous Ops to the A-ASSOCIATE primitive."""
        item = AsynchronousOperationsWindowNegotiation()
        item.maximum_number_operations_invoked = 2
        item.maximum_number_operations_performed = 3
        primitive.user_information.append(item)

    def add_scp_scu_role(self, primitive):
        """Add SCP/SCU Role Selection to the A-ASSOCIATE primitive."""
        contexts = [
            build_context('1.2.840.10008.1.1'),
            build_context('1.2.840.10008.1.2'),
            build_context('1.2.840.10008.1.3'),
            build_context('1.2.840.10008.1.4'),
        ]

        for ii, cx in enumerate(contexts):
            cx.context_id = ii * 2 + 1

        primitive.presentation_context_definition_list = contexts

        item = SCP_SCU_RoleSelectionNegotiation()
        item.sop_class_uid = '1.2.840.10008.1.2'
        item.scu_role = True
        item.scp_role = False
        primitive.user_information.append(item)

        item = SCP_SCU_RoleSelectionNegotiation()
        item.sop_class_uid = '1.2.840.10008.1.3'
        item.scu_role = False
        item.scp_role = True
        primitive.user_information.append(item)

        item = SCP_SCU_RoleSelectionNegotiation()
        item.sop_class_uid = '1.2.840.10008.1.4'
        item.scu_role = True
        item.scp_role = True
        primitive.user_information.append(item)

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

    # debug_send_associate_rq
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

    def test_send_assoc_rq_role(self, caplog):
        """Test ACSE.debug_send_associate_rq with role selection."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.add_scp_scu_role(self.associate_rq)
            pdu = A_ASSOCIATE_RQ()
            pdu.from_primitive(self.associate_rq)
            self.acse.debug_send_associate_rq(pdu)

            messages = [
                "Proposed SCP/SCU Role: Default",
                "Proposed SCP/SCU Role: SCU",
                "Proposed SCP/SCU Role: SCP",
                "Proposed SCP/SCU Role: SCP/SCU",
                "Requested Extended Negotiation: None",
                "Requested Common Extended Negotiation: None",
                "Requested Asynchronous Operations Window Negotiation: None",
                "Requested User Identity Negotiation: None",
            ]

            for msg in messages:
                assert msg in caplog.text

    def test_send_assoc_rq_async(self, caplog):
        """Test ACSE.debug_send_associate_rq with async ops."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.add_async_ops(self.associate_rq)
            pdu = A_ASSOCIATE_RQ()
            pdu.from_primitive(self.associate_rq)
            self.acse.debug_send_associate_rq(pdu)

            messages = [
                "Requested Extended Negotiation: None",
                "Requested Common Extended Negotiation: None",
                "Requested Asynchronous Operations Window Negotiation:",
                "Maximum Invoked Operations:     2",
                "Maximum Performed Operations:   3",
                "Requested User Identity Negotiation: None",
            ]

            for msg in messages:
                assert msg in caplog.text

    def test_send_assoc_rq_sop_ext(self, caplog):
        """Test ACSE.debug_send_associate_rq with SOP Class Extended."""
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
        """Test ACSE.debug_send_associate_rq with SOP Class Common."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.add_sop_common(self.associate_rq)
            pdu = A_ASSOCIATE_RQ()
            pdu.from_primitive(self.associate_rq)
            self.acse.debug_send_associate_rq(pdu)

            messages = [
                "Requested Extended Negotiation: None",
                "Requested Common Extended Negotiation:",
                "SOP Class: =1.2.3.4",
                "Service Class: =1.2.3",
                "Related General SOP Classes: None",
                "SOP Class: =Verification SOP Class",
                "Service Class: =Storage Service Class",
                "Related General SOP Class(es):",
                "=CT Image Storage",
                "=1.9.1",
                "Requested Asynchronous Operations Window Negotiation: None",
                "Requested User Identity Negotiation: None",
            ]

            for msg in messages:
                assert msg in caplog.text

    @pytest.mark.parametrize("info, output", REFERENCE_USER_ID)
    def test_send_assoc_rq_user_id(self, caplog, info, output):
        """Test ACSE.debug_send_associate_rq with SOP User Identity."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.add_user_identity(self.associate_rq, *info)
            pdu = A_ASSOCIATE_RQ()
            pdu.from_primitive(self.associate_rq)
            self.acse.debug_send_associate_rq(pdu)

            messages = [
                "Requested Extended Negotiation: None",
                "Requested Common Extended Negotiation: None",
                "Requested Asynchronous Operations Window Negotiation: None",
                "Requested User Identity Negotiation:",
            ]
            messages += output

            for msg in messages:
                assert msg in caplog.text

    # debug_receive_associate_rq
    def test_recv_assoc_rq_minimal(self, caplog):
        """Test minimal ACSE.debug_receive_associate_rq."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            pdu = A_ASSOCIATE_RQ()
            pdu.from_primitive(self.associate_rq)
            self.acse.debug_receive_associate_rq(pdu)

            messages = [
                "Their Implementation Class UID:      1.2.826.0.1.3680043.8."
                "498.10207287587329888519122978685894984263",
                "Their Implementation Version Name:   unknown",
                "Calling Application Name:    ABCDEFGHIJKLMNOP",
                "Called Application Name:     1234567890123456",
                "Their Max PDU Receive Size:  0",
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

    def test_recv_assoc_rq_role(self, caplog):
        """Test ACSE.debug_receive_associate_rq with role selection."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.add_scp_scu_role(self.associate_rq)
            pdu = A_ASSOCIATE_RQ()
            pdu.from_primitive(self.associate_rq)
            self.acse.debug_receive_associate_rq(pdu)

            messages = [
                "Proposed SCP/SCU Role: Default",
                "Proposed SCP/SCU Role: SCU",
                "Proposed SCP/SCU Role: SCP",
                "Proposed SCP/SCU Role: SCP/SCU",
                "Requested Extended Negotiation: None",
                "Requested Common Extended Negotiation: None",
                "Requested Asynchronous Operations Window Negotiation: None",
                "Requested User Identity Negotiation: None",
            ]

            for msg in messages:
                assert msg in caplog.text

    def test_recv_assoc_rq_async(self, caplog):
        """Test ACSE.debug_receive_associate_rq with async ops."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.add_async_ops(self.associate_rq)
            pdu = A_ASSOCIATE_RQ()
            pdu.from_primitive(self.associate_rq)
            self.acse.debug_receive_associate_rq(pdu)

            messages = [
                "Requested Extended Negotiation: None",
                "Requested Common Extended Negotiation: None",
                "Requested Asynchronous Operations Window Negotiation:",
                "Maximum Invoked Operations:     2",
                "Maximum Performed Operations:   3",
                "Requested User Identity Negotiation: None",
            ]

            for msg in messages:
                assert msg in caplog.text

    def test_recv_assoc_rq_sop_ext(self, caplog):
        """Test ACSE.debug_receive_associate_rq with SOP Class Extended."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.add_sop_ext(self.associate_rq)
            pdu = A_ASSOCIATE_RQ()
            pdu.from_primitive(self.associate_rq)
            self.acse.debug_receive_associate_rq(pdu)

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

    def test_recv_assoc_rq_sop_common(self, caplog):
        """Test ACSE.debug_receive_associate_rq with SOP Class Common."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.add_sop_common(self.associate_rq)
            pdu = A_ASSOCIATE_RQ()
            pdu.from_primitive(self.associate_rq)
            self.acse.debug_receive_associate_rq(pdu)

            messages = [
                "Requested Extended Negotiation: None",
                "Requested Common Extended Negotiation:",
                "SOP Class: =1.2.3.4",
                "Service Class: =1.2.3",
                "Related General SOP Classes: None",
                "SOP Class: =Verification SOP Class",
                "Service Class: =Storage Service Class",
                "Related General SOP Class(es):",
                "=CT Image Storage",
                "=1.9.1",
                "Requested Asynchronous Operations Window Negotiation: None",
                "Requested User Identity Negotiation: None",
            ]

            for msg in messages:
                assert msg in caplog.text

    @pytest.mark.parametrize("info, output", REFERENCE_USER_ID)
    def test_recv_assoc_rq_user_id(self, caplog, info, output):
        """Test ACSE.debug_receive_associate_rq with User Identity."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.add_user_identity(self.associate_rq, *info)
            pdu = A_ASSOCIATE_RQ()
            pdu.from_primitive(self.associate_rq)
            self.acse.debug_send_associate_rq(pdu)

            messages = [
                "Requested Extended Negotiation: None",
                "Requested Common Extended Negotiation: None",
                "Requested Asynchronous Operations Window Negotiation: None",
                "Requested User Identity Negotiation:",
            ]
            messages += output

            for msg in messages:
                assert msg in caplog.text

    # debug_send_associate_ac
    def test_send_assoc_ac_minimal(self, caplog):
        """Test minimal ACSE.debug_send_associate_ac."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            pdu = A_ASSOCIATE_AC()
            pdu.from_primitive(self.associate_ac)
            self.acse.debug_send_associate_ac(pdu)

            messages = [
                "Our Implementation Class UID:      1.2.826.0.1.3680043.8.498"
                ".10207287587329888519122978685894984263",
                "Application Context Name:    1.2.840.10008.3.1.1.1",
                "Responding Application Name: resp. AE Title",
                "Our Max PDU Receive Size:    0",
                "Presentation Contexts:",
                "Context ID:        1 (Accepted)",
                "Accepted Transfer Syntax: =JPEG Baseline (Process 1)",
                "Context ID:        3 (User Rejection)",
                "Context ID:        5 (Provider Rejection)",
                "Context ID:        7 (Abstract Syntax Not Supported)",
                "Context ID:        9 (Transfer Syntax Not Supported)",
                "Accepted Extended Negotiation: None",
                "Accepted Asynchronous Operations Window Negotiation: None",
                "User Identity Negotiation Response: None",
            ]

            for msg in messages:
                assert msg in caplog.text

    def test_send_assoc_ac_role(self, caplog):
        """Test ACSE.debug_send_associate_ac with role selection."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.add_scp_scu_role(self.associate_ac)
            pdu = A_ASSOCIATE_AC()
            pdu.from_primitive(self.associate_ac)
            self.acse.debug_send_associate_ac(pdu)

            messages = [
                "Accepted Role Selection:",
                "SOP Class: =Implicit VR Little Endian",
                "SCP/SCU Role: SCU",
                "SOP Class: =1.2.840.10008.1.3",
                "SCP/SCU Role: SCP",
                "SOP Class: =1.2.840.10008.1.4",
                "SCP/SCU Role: SCP/SCU",
                "Accepted Extended Negotiation: None",
                "Accepted Asynchronous Operations Window Negotiation: None",
                "User Identity Negotiation Response: None",
            ]

            for msg in messages:
                assert msg in caplog.text

    def test_send_assoc_ac_async(self, caplog):
        """Test ACSE.debug_send_associate_ac with async ops."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.add_async_ops(self.associate_ac)
            pdu = A_ASSOCIATE_AC()
            pdu.from_primitive(self.associate_ac)
            self.acse.debug_send_associate_ac(pdu)

            messages = [
                "Accepted Extended Negotiation: None",
                "Accepted Asynchronous Operations Window Negotiation:",
                "Maximum Invoked Operations:     2",
                "Maximum Performed Operations:   3",
                "User Identity Negotiation Response: None",
            ]

            for msg in messages:
                assert msg in caplog.text

    def test_send_assoc_ac_sop_ext(self, caplog):
        """Test ACSE.debug_send_associate_ac with SOP Class Extended."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.add_sop_ext(self.associate_ac)
            pdu = A_ASSOCIATE_AC()
            pdu.from_primitive(self.associate_ac)
            self.acse.debug_send_associate_ac(pdu)

            messages = [
                "Accepted Extended Negotiation:",
                "SOP Class: =1.2.3.4",
                "[ 00  01 ]",
                "SOP Class: =1.2.840.10008.1.1",
                "[ 00  01  02  03  00  01  02  03  00  01  02  03  00  01  02"
                "  03",
                "00  01  02  03  00  01  02  03  00  01  02  03  00  01  02  03",
                "00  01  02  03  00  01  02  03 ]",
                "Accepted Asynchronous Operations Window Negotiation: None",
                "User Identity Negotiation Response: None",
            ]

            for msg in messages:
                assert msg in caplog.text

    def test_send_assoc_ac_user_id(self, caplog):
        """Test ACSE.debug_send_associate_ac with User Identity."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.add_user_identity_rsp(self.associate_ac)
            pdu = A_ASSOCIATE_AC()
            pdu.from_primitive(self.associate_ac)
            self.acse.debug_send_associate_ac(pdu)

            messages = [
                "Accepted Extended Negotiation: None",
                "Accepted Asynchronous Operations Window Negotiation: None",
                "User Identity Negotiation Response: Yes",
            ]

            for msg in messages:
                assert msg in caplog.text

    # debug_receive_associate_ac
    def test_recv_assoc_ac_minimal(self, caplog):
        """Test minimal ACSE.debug_receive_associate_ac."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            pdu = A_ASSOCIATE_AC()
            pdu.from_primitive(self.associate_ac)
            self.acse.debug_receive_associate_ac(pdu)

            messages = [
                "Their Implementation Class UID:    1.2.826.0.1.3680043.8.498"
                ".10207287587329888519122978685894984263",
                "Their Implementation Version Name: unknown",
                "Application Context Name:    1.2.840.10008.3.1.1.1",
                "Calling Application Name:    ABCDEFGHIJKLMNOP",
                "Called Application Name:     1234567890123456",
                "Their Max PDU Receive Size:  0",
                "Presentation Contexts:",
                "Context ID:        1 (Accepted)",
                "Accepted Transfer Syntax: =JPEG Baseline (Process 1)",
                "Context ID:        3 (User Rejection)",
                "Context ID:        5 (Provider Rejection)",
                "Context ID:        7 (Abstract Syntax Not Supported)",
                "Context ID:        9 (Transfer Syntax Not Supported)",
                "Accepted Extended Negotiation: None",
                "Accepted Asynchronous Operations Window Negotiation: None",
                "User Identity Negotiation Response: None",
            ]

            for msg in messages:
                assert msg in caplog.text

    def test_recv_assoc_ac_role(self, caplog):
        """Test ACSE.debug_receive_associate_ac with role selection."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.add_scp_scu_role(self.associate_ac)
            pdu = A_ASSOCIATE_AC()
            pdu.from_primitive(self.associate_ac)
            self.acse.debug_receive_associate_ac(pdu)

            messages = [
                "Accepted Role Selection:",
                "SOP Class: =Implicit VR Little Endian",
                "SCP/SCU Role: SCU",
                "SOP Class: =1.2.840.10008.1.3",
                "SCP/SCU Role: SCP",
                "SOP Class: =1.2.840.10008.1.4",
                "SCP/SCU Role: SCP/SCU",
                "Accepted Extended Negotiation: None",
                "Accepted Asynchronous Operations Window Negotiation: None",
                "User Identity Negotiation Response: None",
            ]

            for msg in messages:
                assert msg in caplog.text

    def test_recv_assoc_ac_async(self, caplog):
        """Test ACSE.debug_receive_associate_ac with async ops."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.add_async_ops(self.associate_ac)
            pdu = A_ASSOCIATE_AC()
            pdu.from_primitive(self.associate_ac)
            self.acse.debug_receive_associate_ac(pdu)

            messages = [
                "Accepted Extended Negotiation: None",
                "Accepted Asynchronous Operations Window Negotiation:",
                "Maximum Invoked Operations:     2",
                "Maximum Performed Operations:   3",
                "User Identity Negotiation Response: None",
            ]

            for msg in messages:
                assert msg in caplog.text

    def test_recv_assoc_ac_sop_ext(self, caplog):
        """Test ACSE.debug_receive_associate_ac with SOP Class Extended."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.add_sop_ext(self.associate_ac)
            pdu = A_ASSOCIATE_AC()
            pdu.from_primitive(self.associate_ac)
            self.acse.debug_receive_associate_ac(pdu)

            messages = [
                "Accepted Extended Negotiation:",
                "SOP Class: =1.2.3.4",
                "[ 00  01 ]",
                "SOP Class: =1.2.840.10008.1.1",
                "[ 00  01  02  03  00  01  02  03  00  01  02  03  00  01  02"
                "  03",
                "00  01  02  03  00  01  02  03  00  01  02  03  00  01  02  03",
                "00  01  02  03  00  01  02  03 ]",
                "Accepted Asynchronous Operations Window Negotiation: None",
                "User Identity Negotiation Response: None",
            ]

            for msg in messages:
                assert msg in caplog.text

    def test_recv_assoc_ac_user_id(self, caplog):
        """Test ACSE.debug_receive_associate_ac with User Identity."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.add_user_identity_rsp(self.associate_ac)
            pdu = A_ASSOCIATE_AC()
            pdu.from_primitive(self.associate_ac)
            self.acse.debug_receive_associate_ac(pdu)

            messages = [
                "Accepted Extended Negotiation: None",
                "Accepted Asynchronous Operations Window Negotiation: None",
                "User Identity Negotiation Response: Yes",
            ]

            for msg in messages:
                assert msg in caplog.text
