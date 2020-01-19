"""Unit test coverage for the logging."""

from io import BytesIO
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

from pynetdicom import build_context, evt, AE, build_role, debug_logger
from pynetdicom.acse import ACSE, APPLICATION_CONTEXT_NAME
from pynetdicom.dimse_primitives import C_MOVE, N_EVENT_REPORT, N_GET, N_DELETE
from pynetdicom._handlers import (
    doc_handle_echo, doc_handle_find, doc_handle_c_get, doc_handle_move,
    doc_handle_store, doc_handle_action, doc_handle_create, doc_handle_delete,
    doc_handle_event_report, doc_handle_n_get, doc_handle_set,
    doc_handle_async, doc_handle_sop_common, doc_handle_sop_extended,
    doc_handle_userid, doc_handle_acse, doc_handle_dimse, doc_handle_data,
    doc_handle_pdu, doc_handle_transport, doc_handle_assoc, doc_handle_fsm,
    debug_fsm
)
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
from pynetdicom.sop_class import CTImageStorage, VerificationSOPClass


#debug_logger()


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


DOC_HANDLERS = [
    doc_handle_echo, doc_handle_find, doc_handle_c_get, doc_handle_move,
    doc_handle_store, doc_handle_action, doc_handle_create, doc_handle_delete,
    doc_handle_event_report, doc_handle_n_get, doc_handle_set,
    doc_handle_async, doc_handle_sop_common, doc_handle_sop_extended,
    doc_handle_userid, doc_handle_acse, doc_handle_dimse, doc_handle_data,
    doc_handle_pdu, doc_handle_transport, doc_handle_assoc, doc_handle_fsm
]


def test_debug_logger():
    """Test __init__.debug_logger()."""
    logger = logging.getLogger('pynetdicom')
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0], logging.NullHandler)

    debug_logger()

    handlers = logger.handlers
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0], logging.StreamHandler)

    debug_logger()

    handlers = logger.handlers
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0], logging.StreamHandler)


class TestDocHandlers(object):
    """Dummy tests to coverage for handler documentation functions."""
    @pytest.mark.parametrize('handler', DOC_HANDLERS)
    def test_doc_handlers(self, handler):
        handler(None)


class TestStandardDIMSE(object):
    def setup(self):
        """Setup each test."""
        self.ae = None

    def teardown(self):
        """Cleanup after each test"""
        if self.ae:
            self.ae.shutdown()

    def test_send_n_delete_rsp(self):
        """Test the handler for N-DELETE rsp"""
        self.ae = ae = AE()
        ae.add_supported_context('1.2.840.10008.1.1')
        ae.add_requested_context('1.2.840.10008.1.1')
        scp = ae.start_server(('', 11112), block=False)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        msg = N_DELETE()
        msg.MessageIDBeingRespondedTo = 1
        msg.AffectedSOPClassUID = '1.2.3'
        msg.AffectedSOPInstanceUID = '1.2.3.4'
        msg.Status = 0x0000

        assoc.dimse.send_msg(msg, 1)

        assoc.release()
        scp.shutdown()

    def test_send_n_get_rq_multiple_attr(self):
        """Test the handler for N-GET rq with multiple Attribute Identifiers"""
        self.ae = ae = AE()
        ae.add_supported_context('1.2.840.10008.1.1')
        ae.add_requested_context('1.2.840.10008.1.1')
        scp = ae.start_server(('', 11112), block=False)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        msg = N_GET()
        msg.MessageID = 1
        msg.RequestedSOPClassUID = '1.2.3'
        msg.RequestedSOPInstanceUID = '1.2.3.4'
        msg.AttributeIdentifierList = [(0x0000,0x0010), (0x00080010)]

        assoc.dimse.send_msg(msg, 1)

        assoc.release()
        scp.shutdown()

    def test_send_n_event_report_rsp(self):
        """Test the handler for N-EVENT-REPORT rsp with Event Type ID."""
        self.ae = ae = AE()
        ae.add_supported_context('1.2.840.10008.1.1')
        ae.add_requested_context('1.2.840.10008.1.1')
        scp = ae.start_server(('', 11112), block=False)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        msg = N_EVENT_REPORT()
        msg.MessageIDBeingRespondedTo = 1
        msg.AffectedSOPClassUID = '1.2.3'
        msg.AffectedSOPInstanceUID = '1.2.3.4'
        msg.EventTypeID = 1  # US
        msg.EventReply = BytesIO(b'\x00\x01')  # Dataset
        msg.Status = 0x0000

        assoc.dimse.send_msg(msg, 1)

        assoc.release()
        scp.shutdown()

    def test_send_c_move_rsp_no_affected_sop(self):
        """Test the handler for C-MOVE rsp with no Affected SOP Class UID."""
        self.ae = ae = AE()
        ae.add_supported_context('1.2.840.10008.1.1')
        ae.add_requested_context('1.2.840.10008.1.1')
        scp = ae.start_server(('', 11112), block=False)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        msg = C_MOVE()
        msg.MessageIDBeingRespondedTo = 1
        msg.Status = 0x0000
        msg.NumberOfRemainingSuboperations = 0
        msg.NumberOfCompletedSuboperations = 0
        msg.NumberOfFailedSuboperations = 0
        msg.NumberOfWarningSuboperations = 0

        assoc.dimse.send_msg(msg, 1)

        assoc.release()
        scp.shutdown()


class TestStandardLogging(object):
    """Tests for standard logging handlers."""
    def setup(self):
        """Setup each test."""
        self.ae = None

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

    def teardown(self):
        """Cleanup after each test"""
        if self.ae:
            self.ae.shutdown()

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
        """Test standard PDU logging handler with minimal A-ASSOCIATE-RQ."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.ae = ae = AE()
            ae.add_supported_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            scp = ae.start_server(('', 11112), block=False)
            assoc = ae.associate('localhost', 11112)

            pdu = A_ASSOCIATE_RQ()
            pdu.from_primitive(self.associate_rq)
            evt.trigger(
                assoc, evt.EVT_PDU_SENT, {'pdu' : pdu}
            )

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

            assoc.release()
            scp.shutdown

    def test_send_assoc_rq_role(self, caplog):
        """Test A-ASSOCIATE-RQ with role selection."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.ae = ae = AE()
            ae.add_supported_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            scp = ae.start_server(('', 11112), block=False)
            assoc = ae.associate('localhost', 11112)

            self.add_scp_scu_role(self.associate_rq)
            pdu = A_ASSOCIATE_RQ()
            pdu.from_primitive(self.associate_rq)
            evt.trigger(
                assoc, evt.EVT_PDU_SENT, {'pdu' : pdu}
            )

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

            assoc.release()
            scp.shutdown()

    def test_send_assoc_rq_async(self, caplog):
        """Test A-ASSOCIATE-RQ with async ops."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.ae = ae = AE()
            ae.add_supported_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            scp = ae.start_server(('', 11112), block=False)
            assoc = ae.associate('localhost', 11112)

            self.add_async_ops(self.associate_rq)
            pdu = A_ASSOCIATE_RQ()
            pdu.from_primitive(self.associate_rq)
            evt.trigger(
                assoc, evt.EVT_PDU_SENT, {'pdu' : pdu}
            )

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

            assoc.release()
            scp.shutdown()

    def test_send_assoc_rq_sop_ext(self, caplog):
        """Test ACSE.debug_send_associate_rq with SOP Class Extended."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.ae = ae = AE()
            ae.add_supported_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            scp = ae.start_server(('', 11112), block=False)
            assoc = ae.associate('localhost', 11112)

            self.add_sop_ext(self.associate_rq)
            pdu = A_ASSOCIATE_RQ()
            pdu.from_primitive(self.associate_rq)
            evt.trigger(
                assoc, evt.EVT_PDU_SENT, {'pdu' : pdu}
            )

            messages = [
                "Requested Extended Negotiation:",
                "SOP Class: =1.2.3.4",
                "00  01",
                "SOP Class: =1.2.840.10008.1.1",
                "00  01  02  03  00  01  02  03  00  01  02  03  00  01  02"
                "  03",
                "00  01  02  03  00  01  02  03  00  01  02  03  00  01  02"
                "  03",
                "00  01  02  03  00  01  02  03",
                "Requested Common Extended Negotiation: None",
                "Requested Asynchronous Operations Window Negotiation: None",
                "Requested User Identity Negotiation: None",
            ]

            for msg in messages:
                assert msg in caplog.text

            assoc.release()
            scp.shutdown()

    def test_send_assoc_rq_sop_common(self, caplog):
        """Test ACSE.debug_send_associate_rq with SOP Class Common."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.ae = ae = AE()
            ae.add_supported_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            scp = ae.start_server(('', 11112), block=False)
            assoc = ae.associate('localhost', 11112)

            self.add_sop_common(self.associate_rq)
            pdu = A_ASSOCIATE_RQ()
            pdu.from_primitive(self.associate_rq)
            evt.trigger(
                assoc, evt.EVT_PDU_SENT, {'pdu' : pdu}
            )

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

            assoc.release()
            scp.shutdown()

    @pytest.mark.parametrize("info, output", REFERENCE_USER_ID)
    def test_send_assoc_rq_user_id(self, caplog, info, output):
        """Test ACSE.debug_send_associate_rq with SOP User Identity."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.ae = ae = AE()
            ae.add_supported_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            scp = ae.start_server(('', 11112), block=False)
            assoc = ae.associate('localhost', 11112)

            self.add_user_identity(self.associate_rq, *info)
            pdu = A_ASSOCIATE_RQ()
            pdu.from_primitive(self.associate_rq)
            evt.trigger(
                assoc, evt.EVT_PDU_SENT, {'pdu' : pdu}
            )

            messages = [
                "Requested Extended Negotiation: None",
                "Requested Common Extended Negotiation: None",
                "Requested Asynchronous Operations Window Negotiation: None",
                "Requested User Identity Negotiation:",
            ]
            messages += output

            for msg in messages:
                assert msg in caplog.text

            assoc.release()
            scp.shutdown()

    # debug_receive_associate_rq
    def test_recv_assoc_rq_minimal(self, caplog):
        """Test minimal ACSE.debug_receive_associate_rq."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.ae = ae = AE()
            ae.add_supported_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            scp = ae.start_server(('', 11112), block=False)
            assoc = ae.associate('localhost', 11112)

            pdu = A_ASSOCIATE_RQ()
            pdu.from_primitive(self.associate_rq)
            evt.trigger(
                assoc, evt.EVT_PDU_RECV, {'pdu' : pdu}
            )

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

            assoc.release()
            scp.shutdown()

    def test_recv_assoc_rq_role(self, caplog):
        """Test ACSE.debug_receive_associate_rq with role selection."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.ae = ae = AE()
            ae.add_supported_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            scp = ae.start_server(('', 11112), block=False)
            assoc = ae.associate('localhost', 11112)

            self.add_scp_scu_role(self.associate_rq)
            pdu = A_ASSOCIATE_RQ()
            pdu.from_primitive(self.associate_rq)
            evt.trigger(
                assoc, evt.EVT_PDU_RECV, {'pdu' : pdu}
            )

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

            assoc.release()
            scp.shutdown()

    def test_recv_assoc_rq_async(self, caplog):
        """Test ACSE.debug_receive_associate_rq with async ops."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.ae = ae = AE()
            ae.add_supported_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            scp = ae.start_server(('', 11112), block=False)
            assoc = ae.associate('localhost', 11112)

            self.add_async_ops(self.associate_rq)
            pdu = A_ASSOCIATE_RQ()
            pdu.from_primitive(self.associate_rq)
            evt.trigger(
                assoc, evt.EVT_PDU_RECV, {'pdu' : pdu}
            )

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

            assoc.release()
            scp.shutdown()

    def test_recv_assoc_rq_sop_ext(self, caplog):
        """Test ACSE.debug_receive_associate_rq with SOP Class Extended."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.ae = ae = AE()
            ae.add_supported_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            scp = ae.start_server(('', 11112), block=False)
            assoc = ae.associate('localhost', 11112)

            self.add_sop_ext(self.associate_rq)
            pdu = A_ASSOCIATE_RQ()
            pdu.from_primitive(self.associate_rq)
            evt.trigger(
                assoc, evt.EVT_PDU_RECV, {'pdu' : pdu}
            )

            messages = [
                "Requested Extended Negotiation:",
                "SOP Class: =1.2.3.4",
                "00  01",
                "SOP Class: =1.2.840.10008.1.1",
                "00  01  02  03  00  01  02  03  00  01  02  03  00  01  02"
                "  03",
                "00  01  02  03  00  01  02  03  00  01  02  03  00  01  02"
                "  03",
                "00  01  02  03  00  01  02  03",
                "Requested Common Extended Negotiation: None",
                "Requested Asynchronous Operations Window Negotiation: None",
                "Requested User Identity Negotiation: None",
            ]

            for msg in messages:
                assert msg in caplog.text

            assoc.release()
            scp.shutdown()

    def test_recv_assoc_rq_sop_common(self, caplog):
        """Test ACSE.debug_receive_associate_rq with SOP Class Common."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.ae = ae = AE()
            ae.add_supported_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            scp = ae.start_server(('', 11112), block=False)
            assoc = ae.associate('localhost', 11112)

            self.add_sop_common(self.associate_rq)
            pdu = A_ASSOCIATE_RQ()
            pdu.from_primitive(self.associate_rq)
            evt.trigger(
                assoc, evt.EVT_PDU_RECV, {'pdu' : pdu}
            )

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

            assoc.release()
            scp.shutdown()

    @pytest.mark.parametrize("info, output", REFERENCE_USER_ID)
    def test_recv_assoc_rq_user_id(self, caplog, info, output):
        """Test ACSE.debug_receive_associate_rq with User Identity."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.ae = ae = AE()
            ae.add_supported_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            scp = ae.start_server(('', 11112), block=False)
            assoc = ae.associate('localhost', 11112)

            self.add_user_identity(self.associate_rq, *info)
            pdu = A_ASSOCIATE_RQ()
            pdu.from_primitive(self.associate_rq)
            evt.trigger(
                assoc, evt.EVT_PDU_RECV, {'pdu' : pdu}
            )

            messages = [
                "Requested Extended Negotiation: None",
                "Requested Common Extended Negotiation: None",
                "Requested Asynchronous Operations Window Negotiation: None",
                "Requested User Identity Negotiation:",
            ]
            messages += output

            for msg in messages:
                assert msg in caplog.text

            assoc.release()
            scp.shutdown()

    # debug_send_associate_ac
    def test_send_assoc_ac_minimal(self, caplog):
        """Test minimal ACSE.debug_send_associate_ac."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.ae = ae = AE()
            ae.add_supported_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            scp = ae.start_server(('', 11112), block=False)
            assoc = ae.associate('localhost', 11112)

            pdu = A_ASSOCIATE_AC()
            pdu.from_primitive(self.associate_ac)
            evt.trigger(
                assoc, evt.EVT_PDU_SENT, {'pdu' : pdu}
            )

            messages = [
                "Our Implementation Class UID:      1.2.826.0.1.3680043.8.498"
                ".10207287587329888519122978685894984263",
                "Application Context Name:    1.2.840.10008.3.1.1.1",
                "Responding Application Name: resp. AE Title",
                "Our Max PDU Receive Size:    0",
                "Presentation Contexts:",
                "Context ID:        1 (Accepted)",
                "Abstract Syntax: =Verification SOP Class",
                "Accepted SCP/SCU Role: Default",
                "Accepted Transfer Syntax: =JPEG Baseline (Process 1)",
                "Context ID:        3 (User Rejection)",
                "Context ID:        5 (Provider Rejection)",
                "Context ID:        7 (Rejected - Abstract Syntax Not Supported)",
                "Context ID:        9 (Rejected - Transfer Syntax Not Supported)",
                "Accepted Extended Negotiation: None",
                "Accepted Asynchronous Operations Window Negotiation: None",
                "User Identity Negotiation Response: None",
            ]

            for msg in messages:
                assert msg in caplog.text

            assoc.release()
            scp.shutdown()

    def test_send_assoc_ac_role(self, caplog):
        """Test ACSE.debug_send_associate_ac with role selection."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.ae = ae = AE()
            ae.add_supported_context(
                '1.2.840.10008.1.2', scu_role=True, scp_role=True)
            ae.add_supported_context(
                '1.2.840.10008.1.3', scu_role=True, scp_role=True)
            ae.add_supported_context(
                '1.2.840.10008.1.4', scu_role=True, scp_role=True)
            ae.add_requested_context('1.2.840.10008.1.2')
            ae.add_requested_context('1.2.840.10008.1.3')
            ae.add_requested_context('1.2.840.10008.1.4')
            ae.add_requested_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            scp = ae.start_server(('', 11112), block=False)

            ext_neg = []
            ext_neg.append(build_role('1.2.840.10008.1.2', scu_role=True))
            ext_neg.append(build_role('1.2.840.10008.1.3', scp_role=True))
            ext_neg.append(build_role(
                '1.2.840.10008.1.4', scu_role=True, scp_role=True))
            assoc = ae.associate('localhost', 11112, ext_neg=ext_neg)

            self.add_scp_scu_role(self.associate_ac)
            contexts = self.associate_ac.presentation_context_definition_results_list
            for ii, cx in enumerate(contexts):
                cx.context_id = ii * 2 + 1
                cx.result = 0
            pdu = A_ASSOCIATE_AC()
            pdu.from_primitive(self.associate_ac)
            evt.trigger(
                assoc, evt.EVT_PDU_SENT, {'pdu' : pdu}
            )

            messages = [
                "Abstract Syntax: =Implicit VR Little Endian",
                "SCP/SCU Role: SCU",
                "Abstract Syntax: =1.2.840.10008.1.3",
                "SCP/SCU Role: SCP",
                "Abstract Syntax: =1.2.840.10008.1.4",
                "SCP/SCU Role: SCP/SCU",
                "Accepted Extended Negotiation: None",
                "Accepted Asynchronous Operations Window Negotiation: None",
                "User Identity Negotiation Response: None",
            ]

            for msg in messages:
                assert msg in caplog.text

            assoc.release()
            scp.shutdown()

    def test_send_assoc_ac_async(self, caplog):
        """Test ACSE.debug_send_associate_ac with async ops."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.ae = ae = AE()
            ae.add_supported_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            scp = ae.start_server(('', 11112), block=False)
            assoc = ae.associate('localhost', 11112)

            self.add_async_ops(self.associate_ac)
            pdu = A_ASSOCIATE_AC()
            pdu.from_primitive(self.associate_ac)
            evt.trigger(
                assoc, evt.EVT_PDU_SENT, {'pdu' : pdu}
            )

            messages = [
                "Accepted Extended Negotiation: None",
                "Accepted Asynchronous Operations Window Negotiation:",
                "Maximum Invoked Operations:     2",
                "Maximum Performed Operations:   3",
                "User Identity Negotiation Response: None",
            ]

            for msg in messages:
                assert msg in caplog.text

            assoc.release()
            scp.shutdown()

    def test_send_assoc_ac_sop_ext(self, caplog):
        """Test ACSE.debug_send_associate_ac with SOP Class Extended."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.ae = ae = AE()
            ae.add_supported_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            scp = ae.start_server(('', 11112), block=False)
            assoc = ae.associate('localhost', 11112)

            self.add_sop_ext(self.associate_ac)
            pdu = A_ASSOCIATE_AC()
            pdu.from_primitive(self.associate_ac)
            evt.trigger(
                assoc, evt.EVT_PDU_SENT, {'pdu' : pdu}
            )

            messages = [
                "Accepted Extended Negotiation:",
                "SOP Class: =1.2.3.4",
                "00  01",
                "SOP Class: =1.2.840.10008.1.1",
                "00  01  02  03  00  01  02  03  00  01  02  03  00  01  02"
                "  03",
                "00  01  02  03  00  01  02  03  00  01  02  03  00  01  02"
                "  03",
                "00  01  02  03  00  01  02  03",
                "Accepted Asynchronous Operations Window Negotiation: None",
                "User Identity Negotiation Response: None",
            ]

            for msg in messages:
                assert msg in caplog.text

            assoc.release()
            scp.shutdown()

    def test_send_assoc_ac_user_id(self, caplog):
        """Test ACSE.debug_send_associate_ac with User Identity."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.ae = ae = AE()
            ae.add_supported_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            scp = ae.start_server(('', 11112), block=False)
            assoc = ae.associate('localhost', 11112)

            self.add_user_identity_rsp(self.associate_ac)
            pdu = A_ASSOCIATE_AC()
            pdu.from_primitive(self.associate_ac)
            evt.trigger(
                assoc, evt.EVT_PDU_SENT, {'pdu' : pdu}
            )

            messages = [
                "Accepted Extended Negotiation: None",
                "Accepted Asynchronous Operations Window Negotiation: None",
                "User Identity Negotiation Response: Yes",
            ]

            for msg in messages:
                assert msg in caplog.text

            assoc.release()
            scp.shutdown()

    def test_send_assoc_ac_no_cx(self, caplog):
        """Test _send_associate_ac logger with no presentations contexts"""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.ae = ae = AE()
            ae.add_supported_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            scp = ae.start_server(('', 11112), block=False)
            assoc = ae.associate('localhost', 11112)

            primitive = self.associate_ac
            primitive.presentation_context_definition_results_list = []
            pdu = A_ASSOCIATE_AC()
            pdu.from_primitive(primitive)
            evt.trigger(
                assoc, evt.EVT_PDU_SENT, {'pdu' : pdu}
            )

            messages = [
                "Our Implementation Class UID:      1.2.826.0.1.3680043.8.498"
                ".10207287587329888519122978685894984263",
                "Application Context Name:    1.2.840.10008.3.1.1.1",
                "Responding Application Name: resp. AE Title",
                "Our Max PDU Receive Size:    0",
                "Presentation Contexts:",
                "(no valid presentation contexts)",
                "Accepted Extended Negotiation: None",
                "Accepted Asynchronous Operations Window Negotiation: None",
                "User Identity Negotiation Response: None",
            ]

            for msg in messages:
                assert msg in caplog.text

            assoc.release()
            scp.shutdown()

    # debug_receive_associate_ac
    def test_recv_assoc_ac_minimal(self, caplog):
        """Test minimal ACSE.debug_receive_associate_ac."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.ae = ae = AE()
            ae.add_supported_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            scp = ae.start_server(('', 11112), block=False)
            assoc = ae.associate('localhost', 11112)

            pdu = A_ASSOCIATE_AC()
            pdu.from_primitive(self.associate_ac)
            evt.trigger(
                assoc, evt.EVT_PDU_RECV, {'pdu' : pdu}
            )

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
                "Context ID:        7 (Rejected - Abstract Syntax Not Supported)",
                "Context ID:        9 (Rejected - Transfer Syntax Not Supported)",
                "Accepted Extended Negotiation: None",
                "Accepted Asynchronous Operations Window Negotiation: None",
                "User Identity Negotiation Response: None",
            ]

            for msg in messages:
                assert msg in caplog.text

            assoc.release()
            scp.shutdown()

    def test_recv_assoc_ac_role(self, caplog):
        """Test ACSE.debug_receive_associate_ac with role selection."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.ae = ae = AE()
            ae.add_supported_context(
                '1.2.840.10008.1.2', scu_role=True, scp_role=True)
            ae.add_supported_context(
                '1.2.840.10008.1.3', scu_role=True, scp_role=True)
            ae.add_supported_context(
                '1.2.840.10008.1.4', scu_role=True, scp_role=True)
            ae.add_requested_context('1.2.840.10008.1.2')
            ae.add_requested_context('1.2.840.10008.1.3')
            ae.add_requested_context('1.2.840.10008.1.4')
            ae.add_requested_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            scp = ae.start_server(('', 11112), block=False)

            ext_neg = []
            ext_neg.append(build_role('1.2.840.10008.1.2', scu_role=True))
            ext_neg.append(build_role('1.2.840.10008.1.3', scp_role=True))
            ext_neg.append(build_role(
                '1.2.840.10008.1.4', scu_role=True, scp_role=True))
            assoc = ae.associate('localhost', 11112, ext_neg=ext_neg)

            self.add_scp_scu_role(self.associate_ac)
            pdu = A_ASSOCIATE_AC()
            pdu.from_primitive(self.associate_ac)
            evt.trigger(
                assoc, evt.EVT_PDU_RECV, {'pdu' : pdu}
            )

            messages = [
                "Abstract Syntax: =Implicit VR Little Endian",
                "SCP/SCU Role: SCU",
                "Abstract Syntax: =1.2.840.10008.1.3",
                "SCP/SCU Role: SCP",
                "Abstract Syntax: =1.2.840.10008.1.4",
                "SCP/SCU Role: SCP/SCU",
                "Accepted Extended Negotiation: None",
                "Accepted Asynchronous Operations Window Negotiation: None",
                "User Identity Negotiation Response: None",
            ]

            for msg in messages:
                assert msg in caplog.text

            assoc.release()
            scp.shutdown()

    def test_recv_assoc_ac_async(self, caplog):
        """Test ACSE.debug_receive_associate_ac with async ops."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.ae = ae = AE()
            ae.add_supported_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            scp = ae.start_server(('', 11112), block=False)
            assoc = ae.associate('localhost', 11112)

            self.add_async_ops(self.associate_ac)
            pdu = A_ASSOCIATE_AC()
            pdu.from_primitive(self.associate_ac)
            evt.trigger(
                assoc, evt.EVT_PDU_RECV, {'pdu' : pdu}
            )

            messages = [
                "Accepted Extended Negotiation: None",
                "Accepted Asynchronous Operations Window Negotiation:",
                "Maximum Invoked Operations:     2",
                "Maximum Performed Operations:   3",
                "User Identity Negotiation Response: None",
            ]

            for msg in messages:
                assert msg in caplog.text

            assoc.release()
            scp.shutdown()

    def test_recv_assoc_ac_sop_ext(self, caplog):
        """Test ACSE.debug_receive_associate_ac with SOP Class Extended."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.ae = ae = AE()
            ae.add_supported_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            scp = ae.start_server(('', 11112), block=False)
            assoc = ae.associate('localhost', 11112)

            self.add_sop_ext(self.associate_ac)
            pdu = A_ASSOCIATE_AC()
            pdu.from_primitive(self.associate_ac)
            evt.trigger(
                assoc, evt.EVT_PDU_RECV, {'pdu' : pdu}
            )

            messages = [
                "Accepted Extended Negotiation:",
                "SOP Class: =1.2.3.4",
                "00  01",
                "SOP Class: =1.2.840.10008.1.1",
                "00  01  02  03  00  01  02  03  00  01  02  03  00  01  02"
                "  03",
                "00  01  02  03  00  01  02  03  00  01  02  03  00  01  02"
                "  03",
                "00  01  02  03  00  01  02  03",
                "Accepted Asynchronous Operations Window Negotiation: None",
                "User Identity Negotiation Response: None",
            ]

            for msg in messages:
                assert msg in caplog.text

            assoc.release()
            scp.shutdown()

    def test_recv_assoc_ac_user_id(self, caplog):
        """Test ACSE.debug_receive_associate_ac with User Identity."""
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            self.ae = ae = AE()
            ae.add_supported_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            ae.add_requested_context(VerificationSOPClass)
            scp = ae.start_server(('', 11112), block=False)
            assoc = ae.associate('localhost', 11112)

            self.add_user_identity_rsp(self.associate_ac)
            pdu = A_ASSOCIATE_AC()
            pdu.from_primitive(self.associate_ac)
            evt.trigger(
                assoc, evt.EVT_PDU_RECV, {'pdu' : pdu}
            )

            messages = [
                "Accepted Extended Negotiation: None",
                "Accepted Asynchronous Operations Window Negotiation: None",
                "User Identity Negotiation Response: Yes",
            ]

            for msg in messages:
                assert msg in caplog.text

            assoc.release()
            scp.shutdown()


class TestDebuggingLogging(object):
    """Tests for debugging handlers."""
    def setup(self):
        """Setup each test."""
        self.ae = None

    def teardown(self):
        """Cleanup after each test"""
        if self.ae:
            self.ae.shutdown()

    def test_debug_fsm(self, caplog):
        """Test debug_fsm."""
        self.ae = ae = AE()
        ae.add_supported_context('1.2.840.10008.1.1')
        ae.add_requested_context('1.2.840.10008.1.1')
        scp = ae.start_server(('', 11112), block=False)

        hh = [(evt.EVT_FSM_TRANSITION, debug_fsm)]
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            assoc = ae.associate('localhost', 11112, evt_handlers=hh)
            assert assoc.is_established
            assoc.send_c_echo()
            assoc.release()

        scp.shutdown()

        assert "R: Sta1 + Evt1 -> AE-1 -> Sta4" in caplog.text
