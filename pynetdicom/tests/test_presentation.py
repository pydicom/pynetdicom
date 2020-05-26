"""Tests for the presentation module."""
import logging
import sys

import pytest

from pydicom._uid_dict import UID_dictionary
from pydicom.uid import UID

from pynetdicom import AE, _config
from pynetdicom.pdu_primitives import SCP_SCU_RoleSelectionNegotiation
from pynetdicom.presentation import (
    build_context,
    build_role,
    PresentationContext,
    negotiate_as_acceptor,
    negotiate_as_requestor,
    DEFAULT_TRANSFER_SYNTAXES,
    ApplicationEventLoggingPresentationContexts,
    BasicWorklistManagementPresentationContexts,
    ColorPalettePresentationContexts,
    DefinedProcedureProtocolPresentationContexts,
    DisplaySystemPresentationContexts,
    HangingProtocolPresentationContexts,
    ImplantTemplatePresentationContexts,
    InstanceAvailabilityPresentationContexts,
    MediaCreationManagementPresentationContexts,
    MediaStoragePresentationContexts,
    NonPatientObjectPresentationContexts,
    PrintManagementPresentationContexts,
    ProcedureStepPresentationContexts,
    ProtocolApprovalPresentationContexts,
    QueryRetrievePresentationContexts,
    RelevantPatientInformationPresentationContexts,
    RTMachineVerificationPresentationContexts,
    StoragePresentationContexts,
    StorageCommitmentPresentationContexts,
    SubstanceAdministrationPresentationContexts,
    UnifiedProcedurePresentationContexts,
    VerificationPresentationContexts,
)
from pynetdicom.sop_class import (
    VerificationSOPClass,
    CompositeInstanceRetrieveWithoutBulkDataGet,
    CTImageStorage,
)


@pytest.fixture(params=[
    (1, '1.1.1', ['1.2.840.10008.1.2']),
    (1, '1.1.1', ['1.2.840.10008.1.2', '1.2.840.10008.1.2.1']),
    (1, '1.1.1', ['1.2.840.10008.1.2', '1.2.840.10008.1.2.1', '1.2.3']),
    (1, '1.1.1', []),
    (1, '1.2.840.10008.1.2.1.1.3', ['1.2.3']),
    (1, '1.2.840.10008.1.2.1.1.3', ['1.2.3', '1.2.840.10008.1.2'])
])
def good_init(request):
    """Good init values."""
    return request.param


class TestPresentationContext(object):
    """Test the PresentationContext class"""
    def setup(self):
        self.default_conformance = _config.ENFORCE_UID_CONFORMANCE

    def teardown(self):
        _config.ENFORCE_UID_CONFORMANCE = self.default_conformance

    def test_setter(self, good_init):
        """Test the presentation context class init"""
        (context_id, abs_syn, tran_syn) = good_init
        pc = PresentationContext()
        pc.context_id = context_id
        pc.abstract_syntax = abs_syn
        pc.transfer_syntax = tran_syn
        assert pc.context_id == context_id
        assert pc.abstract_syntax == abs_syn
        assert pc.transfer_syntax == tran_syn
        assert pc._scu_role is None
        assert pc._scp_role is None
        assert pc._as_scu is None
        assert pc._as_scp is None
        assert pc.result is None

    def test_add_transfer_syntax(self):
        """Test adding transfer syntaxes"""
        pc = PresentationContext()
        pc.context_id = 1
        pc.add_transfer_syntax('1.2.840.10008.1.2')
        pc.add_transfer_syntax(b'1.2.840.10008.1.2.1')
        pc.add_transfer_syntax(UID('1.2.840.10008.1.2.2'))

        # Test adding an invalid value
        pc.add_transfer_syntax(1234)
        assert 1234 not in pc.transfer_syntax

    def test_add_transfer_syntax_nonconformant(self, caplog):
        """Test adding non-conformant transfer syntaxes"""
        _config.ENFORCE_UID_CONFORMANCE = True

        caplog.set_level(logging.DEBUG, logger='pynetdicom.presentation')
        pc = PresentationContext()
        pc.context_id = 1

        msg = r"'transfer_syntax' contains an invalid UID"
        with pytest.raises(ValueError, match=msg):
            pc.add_transfer_syntax('1.2.3.')

        assert msg in caplog.text

        pc.add_transfer_syntax('1.2.840.10008.1.1')
        assert ("A UID has been added to 'transfer_syntax' that is not a "
               "transfer syntax" in caplog.text)

        _config.ENFORCE_UID_CONFORMANCE = False
        pc.add_transfer_syntax('1.2.3.')
        assert '1.2.3.' in pc.transfer_syntax

    def test_add_private_transfer_syntax(self):
        """Test adding private transfer syntaxes"""
        _config.ENFORCE_UID_CONFORMANCE = False
        pc = PresentationContext()
        pc.context_id = 1
        pc.add_transfer_syntax('2.16.840.1.113709.1.2.2')
        assert '2.16.840.1.113709.1.2.2' in pc._transfer_syntax

        pc.transfer_syntax = ['2.16.840.1.113709.1.2.1']
        assert '2.16.840.1.113709.1.2.1' in pc._transfer_syntax

        _config.ENFORCE_UID_CONFORMANCE = True
        pc = PresentationContext()
        pc.context_id = 1
        pc.add_transfer_syntax('2.16.840.1.113709.1.2.2')
        assert '2.16.840.1.113709.1.2.2' in pc._transfer_syntax

        pc.transfer_syntax = ['2.16.840.1.113709.1.2.1']
        assert '2.16.840.1.113709.1.2.1' in pc._transfer_syntax

    def test_add_transfer_syntax_duplicate(self):
        """Test add_transfer_syntax with a duplicate UID"""
        pc = PresentationContext()
        pc.add_transfer_syntax('1.3')
        pc.add_transfer_syntax('1.3')

        assert pc.transfer_syntax == ['1.3']

    def test_equality(self):
        """Test presentation context equality"""
        pc_a = PresentationContext()
        pc_a.context_id = 1
        pc_a.abstract_syntax = '1.1.1'
        pc_a.transfer_syntax = ['1.2.840.10008.1.2']
        pc_b = PresentationContext()
        pc_b.context_id = 1
        pc_b.abstract_syntax = '1.1.1'
        pc_b.transfer_syntax = ['1.2.840.10008.1.2']
        assert pc_a == pc_a
        assert pc_a == pc_b
        assert not pc_a != pc_b
        assert not pc_a != pc_a
        # scp/scu role start off as None
        pc_a._scp_role = False
        assert not pc_a == pc_b
        pc_a._scp_role = True
        assert not pc_a == pc_b
        pc_b._scu_role = False
        assert not pc_a == pc_b
        pc_b._scu_role = True
        pc_a._scu_role = True
        pc_b._scp_role = True
        assert pc_a == pc_b
        assert not 'a' == pc_b

    def test_hash(self):
        """Test hashing the context"""
        cx_a = build_context('1.2.3', '1.2.3.4')
        cx_b = build_context('1.2.3', '1.2.3.4')
        assert hash(cx_a) == hash(cx_b)
        cx_a.transfer_syntax = ['1.2.3.4']
        assert hash(cx_a) == hash(cx_b)
        cx_a.transfer_syntax[0] = '1.2.3.4'
        assert hash(cx_a) == hash(cx_b)
        cx_a.transfer_syntax[0] = '1.2.3.5'
        assert hash(cx_a) != hash(cx_b)
        cx_a.transfer_syntax = ['1.2.3.5']
        assert hash(cx_a) != hash(cx_b)
        cx_c = build_context('1.2.3', ['1.1', '1.2'])
        assert hash(cx_c) != hash(cx_b)
        cx_d = build_context('1.2.3', ['1.1', '1.2'])
        assert hash(cx_c) == hash(cx_d)
        cx_c.transfer_syntax[1] = '1.2.3.5'
        cx_d.transfer_syntax[1] = '1.2.3.5'
        assert hash(cx_c) == hash(cx_d)

    def test_string_output(self):
        """Test string output"""
        pc = PresentationContext()
        pc.context_id = 1
        pc.abstract_syntax = '1.1.1'
        pc.transfer_syntax = ['1.2.840.10008.1.2', '1.2.3']
        pc._scp_role = True
        pc._scu_role = False
        pc.result = 0x02
        assert '1.1.1' in pc.__str__()
        assert 'Implicit' in pc.__str__()
        assert 'Provider Rejected' in pc.__str__()

        pc._as_scu = True
        pc._as_scp = False
        assert 'Role: SCU only' in pc.__str__()
        pc._as_scp = True
        assert 'Role: SCU and SCP' in pc.__str__()
        pc._as_scu = False
        assert 'Role: SCP only' in pc.__str__()
        pc._as_scp = False
        assert 'Role: (none)' in pc.__str__()

        pc._transfer_syntax = []
        print(pc)
        assert '    (none)' in pc.__str__()

    def test_context_id(self):
        """Test setting context_id."""
        pc = PresentationContext()
        pc.context_id = 1
        assert pc.context_id == 1
        pc.context_id = 255
        assert pc.context_id == 255

        with pytest.raises(ValueError):
            pc.context_id = 0
        with pytest.raises(ValueError):
            pc.context_id = 256
        with pytest.raises(ValueError):
            pc.context_id = 12

    def test_abstract_syntax(self):
        """Test abstract syntax setter"""
        pc = PresentationContext()
        pc.context_id = 1
        pc.abstract_syntax = '1.1.1'
        assert pc.abstract_syntax == UID('1.1.1')
        assert isinstance(pc.abstract_syntax, UID)
        pc.abstract_syntax = b'1.2.1'
        assert pc.abstract_syntax == UID('1.2.1')
        assert isinstance(pc.abstract_syntax, UID)
        pc.abstract_syntax = UID('1.3.1')
        assert pc.abstract_syntax == UID('1.3.1')
        assert isinstance(pc.abstract_syntax, UID)

    def test_abstract_syntax_raises(self):
        """Test exception raised if invalid abstract syntax"""
        pc = PresentationContext()
        with pytest.raises(TypeError):
            pc.abstract_syntax = 1234

    def test_abstract_syntax_nonconformant(self, caplog):
        """Test adding non-conformant abstract syntaxes"""
        _config.ENFORCE_UID_CONFORMANCE = True
        caplog.set_level(logging.DEBUG, logger='pynetdicom.presentation')
        pc = PresentationContext()
        pc.context_id = 1

        msg = r"'abstract_syntax' is an invalid UID"
        with pytest.raises(ValueError, match=msg):
            pc.abstract_syntax = UID('1.4.1.')
        assert pc.abstract_syntax is None

        _config.ENFORCE_UID_CONFORMANCE = False
        pc.abstract_syntax = UID('1.4.1.')
        assert pc.abstract_syntax == UID('1.4.1.')
        assert isinstance(pc.abstract_syntax, UID)

        assert ("'abstract_syntax' is an invalid UID" in caplog.text)

    def test_transfer_syntax(self):
        """Test transfer syntax setter"""
        pc = PresentationContext()
        pc.context_id = 1
        pc.transfer_syntax = ['1.2.840.10008.1.2']

        assert pc.transfer_syntax[0] == UID('1.2.840.10008.1.2')
        assert isinstance(pc.transfer_syntax[0], UID)
        pc.transfer_syntax = [b'1.2.840.10008.1.2.1']
        assert pc.transfer_syntax[0] == UID('1.2.840.10008.1.2.1')
        assert isinstance(pc.transfer_syntax[0], UID)
        pc.transfer_syntax = [UID('1.2.840.10008.1.2.2')]
        assert pc.transfer_syntax[0] == UID('1.2.840.10008.1.2.2')
        assert isinstance(pc.transfer_syntax[0], UID)

        with pytest.raises(TypeError):
            pc.transfer_syntax = UID('1.4.1')

        pc.transfer_syntax = [1234, UID('1.4.1')]
        assert pc.transfer_syntax == [UID('1.4.1')]

    def test_transfer_syntax_duplicate(self):
        """Test the transfer_syntax setter with duplicate UIDs."""
        pc = PresentationContext()
        pc.transfer_syntax = ['1.3', '1.3']
        assert pc.transfer_syntax == ['1.3']

    def test_transfer_syntax_nonconformant(self, caplog):
        """Test setting non-conformant transfer syntaxes"""
        caplog.set_level(logging.DEBUG, logger='pynetdicom.presentation')
        pc = PresentationContext()
        pc.context_id = 1
        pc.transfer_syntax = ['1.4.1.', '1.2.840.10008.1.2']
        assert pc.transfer_syntax == ['1.4.1.', '1.2.840.10008.1.2']
        assert ("A non-conformant UID has been added to 'transfer_syntax'" in
            caplog.text)

    def test_status(self):
        """Test presentation context status"""
        pc = PresentationContext()
        pc.context_id = 1
        statuses = [None, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05]
        results = ['Pending', 'Accepted', 'User Rejected', 'Provider Rejected',
                   'Abstract Syntax Not Supported',
                   'Transfer Syntax(es) Not Supported', 'Unknown']

        for status, result in zip(statuses, results):
            pc.result = status
            assert pc.status == result

    def test_tuple(self):
        """Test the .as_tuple"""
        context = PresentationContext()
        context.context_id = 3
        context.abstract_syntax = '1.2.840.10008.1.1'
        context.transfer_syntax = ['1.2.840.10008.1.2']
        out = context.as_tuple

        assert out.context_id == 3
        assert out.abstract_syntax == '1.2.840.10008.1.1'
        assert out.transfer_syntax == '1.2.840.10008.1.2'

    def test_as_scp(self):
        """Test the Presentation.as_scp property."""
        context = build_context('1.2.3')
        assert context.as_scp is None

        with pytest.raises(AttributeError, match=r"can't set attribute"):
            context.as_scp = True

        context._as_scp = True
        assert context.as_scp
        context._as_scp = False
        assert not context.as_scp

    def test_as_scu(self):
        """Test the Presentation.as_scu property."""
        context = build_context('1.2.3')
        assert context.as_scu is None

        with pytest.raises(AttributeError, match=r"can't set attribute"):
            context.as_scu = True

        context._as_scu = True
        assert context.as_scu
        context._as_scu = False
        assert not context.as_scu

    def test_scu_role(self):
        """Test Presentation.scu_role setter/getter."""
        context = build_context('1.2.3')
        assert context.scu_role is None
        context.scu_role = True
        assert context.scu_role
        context.scu_role = False
        assert not context.scu_role
        context.scu_role = None
        assert context.scu_role is None
        with pytest.raises(TypeError, match=r"`scu_role` must be a bool"):
            context.scu_role = 1

    def test_scp_role(self):
        """Test Presentation.scp_role setter/getter."""
        context = build_context('1.2.3')
        assert context.scp_role is None
        context.scp_role = True
        assert context.scp_role
        context.scp_role = False
        assert not context.scp_role
        context.scp_role = None
        assert context.scp_role is None

        with pytest.raises(TypeError, match=r"`scp_role` must be a bool"):
            context.scp_role = 1

    def test_repr(self):
        """Test PresentationContext.__repr__"""
        cx = build_context('1.2.3')
        assert '1.2.3' == repr(cx)
        cx = build_context('1.2.840.10008.1.1')
        assert 'Verification SOP Class' == repr(cx)


class TestNegotiateAsAcceptor(object):
    """Tests negotiation_as_acceptor."""
    def setup(self):
        self.test_func = negotiate_as_acceptor

    def test_no_req_no_acc(self):
        """Test negotiation with no contexts."""
        result = self.test_func([], [], [])
        assert result == ([], [])

    def test_one_req_no_acc(self):
        """Test negotiation with one requestor, no acceptor contexts."""
        context = PresentationContext()
        context.context_id = 1
        context.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
        context.transfer_syntax = ['1.2.840.10008.1.2']
        result, roles = self.test_func([context], [])

        assert len(result) == 1
        assert roles == []
        context = result[0]
        assert context.context_id == 1
        assert context.abstract_syntax == '1.2.840.10008.5.1.4.1.1.2'
        assert context.transfer_syntax == ['1.2.840.10008.1.2']
        assert context.result == 0x03

    def test_no_req_one_acc(self):
        """Test negotiation with no requestor, one acceptor contexts."""
        context = PresentationContext()
        context.context_id = 1
        context.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
        context.transfer_syntax = ['1.2.840.10008.1.2']
        result, roles = self.test_func([], [context])
        assert result == []
        assert roles == []

    def test_dupe_abs_req_no_acc(self):
        """Test negotiation with duplicate requestor, no acceptor contexts."""
        context_a = PresentationContext()
        context_a.context_id = 1
        context_a.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
        context_a.transfer_syntax = ['1.2.840.10008.1.2']

        context_b = PresentationContext()
        context_b.context_id = 3
        context_b.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
        context_b.transfer_syntax = ['1.2.840.10008.1.2.1']

        context_c = PresentationContext()
        context_c.context_id = 5
        context_c.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
        context_c.transfer_syntax = ['1.2.840.10008.1.2.2']

        context_list = [context_a, context_b, context_c]
        result, roles = self.test_func(context_list, [])
        assert len(result) == 3
        assert roles == []
        for context in result:
            assert context.context_id in [1, 3, 5]
            assert context.abstract_syntax == '1.2.840.10008.5.1.4.1.1.2'
            assert context.result == 0x03

    def test_dupe_abs_req(self):
        """Test negotiation with duplicate requestor, no acceptor contexts."""
        context_a = PresentationContext()
        context_a.context_id = 1
        context_a.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
        context_a.transfer_syntax = ['1.2.840.10008.1.2']

        context_b = PresentationContext()
        context_b.context_id = 3
        context_b.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
        context_b.transfer_syntax = ['1.2.840.10008.1.2.1']

        context_c = PresentationContext()
        context_c.context_id = 5
        context_c.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
        context_c.transfer_syntax = ['1.2.840.10008.1.2.2']

        t_syntax = ['1.2.840.10008.1.2',
                    '1.2.840.10008.1.2.1',
                    '1.2.840.10008.1.2.2']
        context_d = PresentationContext()
        context_d.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
        context_d.transfer_syntax = t_syntax
        context_list = [context_a, context_b, context_c]
        result, roles = self.test_func(context_list, [context_d])
        assert len(result) == 3
        assert roles == []
        for ii, context in enumerate(result):
            assert context.context_id in [1, 3, 5]
            assert context.abstract_syntax == '1.2.840.10008.5.1.4.1.1.2'
            assert context.result == 0x00
            assert context.transfer_syntax == [t_syntax[ii]]

    def test_one_req_one_acc_match(self):
        """Test negotiation one req/acc, matching accepted."""
        context = PresentationContext()
        context.context_id = 1
        context.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
        context.transfer_syntax = ['1.2.840.10008.1.2']
        result, roles = self.test_func([context], [context])
        assert len(result) == 1
        assert roles == []
        context = result[0]
        assert context.context_id == 1
        assert context.abstract_syntax == '1.2.840.10008.5.1.4.1.1.2'
        assert context.result == 0x00
        assert context.transfer_syntax == ['1.2.840.10008.1.2']

    def test_one_req_one_acc_accept_trans(self):
        """Test negotiation one req/acc, matching accepted, multi trans."""
        context = PresentationContext()
        context.context_id = 1
        context.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
        context.transfer_syntax = ['1.2.840.10008.1.2',
                                   '1.2.840.10008.1.2.1',
                                   '1.2.840.10008.1.2.2']
        result, roles = self.test_func([context], [context])
        assert len(result) == 1
        assert roles == []
        context = result[0]
        assert context.context_id == 1
        assert context.abstract_syntax == '1.2.840.10008.5.1.4.1.1.2'
        assert context.result == 0x00
        assert context.transfer_syntax == ['1.2.840.10008.1.2']

    def test_one_req_one_acc_accept_trans_diff(self):
        """Test negotiation one req/acc, matching accepted, multi trans."""
        context_a = PresentationContext()
        context_a.context_id = 1
        context_a.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
        context_a.transfer_syntax = ['1.2.840.10008.1.2',
                                   '1.2.840.10008.1.2.1',
                                   '1.2.840.10008.1.2.2']
        context_b = PresentationContext()
        context_b.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
        context_b.transfer_syntax = ['1.2.840.10008.1.2.2']

        result, roles = self.test_func([context_a], [context_b])
        assert len(result) == 1
        assert roles == []
        context = result[0]
        assert context.context_id == 1
        assert context.abstract_syntax == '1.2.840.10008.5.1.4.1.1.2'
        assert context.result == 0x00
        assert context.transfer_syntax == ['1.2.840.10008.1.2.2']

    def test_one_req_one_acc_reject_trans(self):
        """Test negotiation one req/acc, matching rejected trans"""
        context_a = PresentationContext()
        context_a.context_id = 1
        context_a.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
        context_a.transfer_syntax = ['1.2.840.10008.1.2',
                                   '1.2.840.10008.1.2.1']
        context_b = PresentationContext()
        context_b.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
        context_b.transfer_syntax = ['1.2.840.10008.1.2.2']
        result, roles = self.test_func([context_a], [context_b])
        assert len(result) == 1
        assert roles == []
        context = result[0]
        assert context.context_id == 1
        assert context.abstract_syntax == '1.2.840.10008.5.1.4.1.1.2'
        assert context.result == 0x04

    def test_one_req_one_acc_mismatch(self):
        """Test negotiation one req/acc, mismatched rejected"""
        context_a = PresentationContext()
        context_a.context_id = 1
        context_a.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
        context_a.transfer_syntax = ['1.2.840.10008.1.2',
                                   '1.2.840.10008.1.2.1']
        context_b = PresentationContext()
        context_b.abstract_syntax = '1.2.840.10008.5.1.4.1.1.4'
        context_b.transfer_syntax = ['1.2.840.10008.1.2.2']
        result, roles = self.test_func([context_a], [context_b])
        assert len(result) == 1
        assert roles == []
        context = result[0]
        assert context.context_id == 1
        assert context.abstract_syntax == '1.2.840.10008.5.1.4.1.1.2'
        assert context.result == 0x03

    def test_private_transfer_syntax(self):
        """Test negotiation with private transfer syntax"""
        context_a = PresentationContext()
        context_a.context_id = 1
        context_a.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
        context_a.transfer_syntax = ['1.2.3.4']
        context_b = PresentationContext()
        context_b.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
        context_b.transfer_syntax = ['1.2.840.10008.1.2.1',
                                     '1.2.3.4']
        result, roles = self.test_func([context_a], [context_b])
        assert len(result) == 1
        assert roles == []
        context = result[0]
        assert context.context_id == 1
        assert context.abstract_syntax == '1.2.840.10008.5.1.4.1.1.2'
        assert context.result == 0x00
        assert context.transfer_syntax == ['1.2.3.4']

    def test_private_abstract_syntax(self):
        """Test negotiation with private abstract syntax"""
        context_a = PresentationContext()
        context_a.context_id = 1
        context_a.abstract_syntax = '1.2.3.4'
        context_a.transfer_syntax = ['1.2.840.10008.1.2.1']
        context_b = PresentationContext()
        context_b.abstract_syntax = '1.2.3.4'
        context_b.transfer_syntax = ['1.2.840.10008.1.2.1']

        result, roles = self.test_func([context_a], [context_b])
        assert len(result) == 1
        assert roles == []
        context = result[0]
        assert context.context_id == 1
        assert context.abstract_syntax == '1.2.3.4'
        assert context.result == 0x00
        assert context.transfer_syntax == ['1.2.840.10008.1.2.1']

    def test_typical(self):
        """Test a typical set of presentation context negotiations."""
        req_contexts = []
        for ii, context in enumerate(StoragePresentationContexts):
            pc = PresentationContext()
            pc.context_id = ii * 2 + 1
            pc.abstract_syntax = context.abstract_syntax
            pc.transfer_syntax = ['1.2.840.10008.1.2',
                                 '1.2.840.10008.1.2.1',
                                 '1.2.840.10008.1.2.2']
            req_contexts.append(pc)

        acc_contexts = []
        for uid in UID_dictionary:
            pc = PresentationContext()
            pc.abstract_syntax = uid
            pc.transfer_syntax = ['1.2.840.10008.1.2',
                                  '1.2.840.10008.1.2.1',
                                  '1.2.840.10008.1.2.2']
            acc_contexts.append(pc)

        results, roles = self.test_func(req_contexts, acc_contexts)
        assert len(results) == len(req_contexts)
        assert roles == []
        for ii, context in enumerate(req_contexts):
            assert results[ii].context_id == context.context_id
            assert results[ii].abstract_syntax == context.abstract_syntax
            if results[ii].abstract_syntax == '1.2.840.10008.5.1.4.1.1.1.1.1.1':
                assert results[ii].result == 0x03
            elif results[ii].abstract_syntax == '1.2.840.10008.5.1.1.4.1.1.3.1':
                assert results[ii].result == 0x03
            else:
                assert results[ii].result == 0x00
                assert results[ii].transfer_syntax == ['1.2.840.10008.1.2']

    def test_first_supported_match(self):
        """Test that the acceptor uses the first matching supported tsyntax."""
        req_contexts = []
        pc = PresentationContext()
        pc.context_id = 1
        pc.abstract_syntax = CTImageStorage
        pc.transfer_syntax = [
            '1.2.840.10008.1.2', '1.2.840.10008.1.2.1', '1.2.840.10008.1.2.2'
        ]
        req_contexts.append(pc)

        acc_contexts = []
        pc = PresentationContext()
        pc.abstract_syntax = CTImageStorage
        pc.transfer_syntax = [
            '1.2.840.10008.1.2.1', '1.2.840.10008.1.2.2', '1.2.840.10008.1.2'
        ]
        acc_contexts.append(pc)

        results, roles = self.test_func(req_contexts, acc_contexts)
        assert results[0].transfer_syntax[0] == '1.2.840.10008.1.2.1'


# (req.as_scu, req.as_scp, ac.as_scu, ac.as_scp)
DEFAULT_ROLE = (True, False, False, True)
BOTH_SCU_SCP_ROLE = (True, True, True, True)
CONTEXT_REJECTED = (False, False, False, False)
INVERTED_ROLE = (False, True, True, False)

REFERENCE_ROLES = [
    # Req role (SCU, SCP), ac role (SCU, SCP), Outcome
    # No SCP/SCU Role Selection proposed
    ((None, None), (None, None), DEFAULT_ROLE),
    ((None, None), (None, True), DEFAULT_ROLE),
    ((None, None), (None, False), DEFAULT_ROLE),
    ((None, None), (True, None), DEFAULT_ROLE),
    ((None, None), (False, None), DEFAULT_ROLE),
    ((None, None), (True, True), DEFAULT_ROLE),
    ((None, None), (True, False), DEFAULT_ROLE),
    ((None, None), (False, False), DEFAULT_ROLE),
    ((None, None), (False, True), DEFAULT_ROLE),
    # True, True proposed
    ((True, True), (None, None), DEFAULT_ROLE),
    ((True, True), (None, True), DEFAULT_ROLE),
    ((True, True), (None, False), DEFAULT_ROLE),
    ((True, True), (True, None), DEFAULT_ROLE),
    ((True, True), (False, None), DEFAULT_ROLE),
    ((True, True), (True, True), BOTH_SCU_SCP_ROLE),
    ((True, True), (True, False), DEFAULT_ROLE),
    ((True, True), (False, False), CONTEXT_REJECTED),
    ((True, True), (False, True), INVERTED_ROLE),
    # True, False proposed
    ((True, False), (None, None), DEFAULT_ROLE),
    ((True, False), (None, True), DEFAULT_ROLE),
    ((True, False), (None, False), DEFAULT_ROLE),
    ((True, False), (True, None), DEFAULT_ROLE),
    ((True, False), (False, None), DEFAULT_ROLE),
    ((True, False), (True, True), DEFAULT_ROLE),  # Invalid
    ((True, False), (True, False), DEFAULT_ROLE),
    ((True, False), (False, False), CONTEXT_REJECTED),
    ((True, False), (False, True), CONTEXT_REJECTED),  # Invalid
    # False, True proposed
    ((False, True), (None, None), DEFAULT_ROLE),
    ((False, True), (None, True), DEFAULT_ROLE),
    ((False, True), (None, False), DEFAULT_ROLE),
    ((False, True), (True, None), DEFAULT_ROLE),
    ((False, True), (False, None), DEFAULT_ROLE),
    ((False, True), (True, True), INVERTED_ROLE),  # Invalid
    ((False, True), (True, False), CONTEXT_REJECTED),  # Invalid
    ((False, True), (False, False), CONTEXT_REJECTED),
    ((False, True), (False, True), INVERTED_ROLE),
    # False, False proposed
    ((False, False), (None, None), DEFAULT_ROLE),
    ((False, False), (None, True), DEFAULT_ROLE),
    ((False, False), (None, False), DEFAULT_ROLE),
    ((False, False), (True, None), DEFAULT_ROLE),
    ((False, False), (False, None), DEFAULT_ROLE),
    ((False, False), (True, True), CONTEXT_REJECTED),  # Invalid
    ((False, False), (True, False), CONTEXT_REJECTED),  # Invalid
    ((False, False), (False, False), CONTEXT_REJECTED),
    ((False, False), (False, True), CONTEXT_REJECTED),  # Invalid
]


class TestNegotiateAsAcceptorWithRoleSelection(object):
    """Tests negotiate_as_acceptor with role selection."""
    @pytest.mark.parametrize("req, acc, out", REFERENCE_ROLES)
    def test_scp_scu_role_negotiation(self, req, acc, out):
        """Test presentation service negotiation with role selection."""
        rq = build_context('1.2.3.4')
        rq_roles = {'1.2.3.4' : (req[0], req[1])}

        ac = build_context('1.2.3.4')
        ac.scu_role = acc[0]
        ac.scp_role = acc[1]

        result, roles = negotiate_as_acceptor([rq], [ac], rq_roles)

        assert result[0].abstract_syntax == '1.2.3.4'
        assert result[0].transfer_syntax[0] == '1.2.840.10008.1.2'
        assert result[0].as_scu == out[2]
        assert result[0].as_scp == out[3]
        if out == CONTEXT_REJECTED:
            assert result[0].result == 0x01
        else:
            assert result[0].result == 0x00

        if None not in acc and out != CONTEXT_REJECTED:
            assert roles[0].sop_class_uid == '1.2.3.4'
            if req[0] is False:
                assert roles[0].scu_role is False
            else:
                assert roles[0].scu_role == acc[0]

            if req[1] is False:
                assert roles[0].scp_role is False
            else:
                assert roles[0].scp_role == acc[1]

    def test_multiple_contexts_same_abstract(self):
        """Test that SCP/SCU role neg works with multiple contexts."""
        rq_contexts = [build_context('1.2.3.4'), build_context('1.2.3.4')]
        rq_roles = {}
        for ii, context in enumerate(rq_contexts):
            context.context_id = ii * 2 + 1
            rq_roles[context.abstract_syntax] = (False, True)
        rq_contexts.append(build_context('1.2.3.4.5'))
        rq_contexts[2].context_id = 5

        ac = build_context('1.2.3.4')
        ac.scu_role = False
        ac.scp_role = True

        ac2 = build_context('1.2.3.4.5')

        result, roles = negotiate_as_acceptor(rq_contexts, [ac, ac2], rq_roles)
        assert len(result) == 3
        for context in result[:2]:
            assert context.abstract_syntax == '1.2.3.4'
            assert context.transfer_syntax[0] == '1.2.840.10008.1.2'
            assert context.as_scu == True
            assert context.as_scp == False
            assert context.result == 0x0000

        assert result[2].abstract_syntax == '1.2.3.4.5'
        assert result[2].transfer_syntax[0] == '1.2.840.10008.1.2'
        assert result[2].as_scu == False
        assert result[2].as_scp == True
        assert result[2].result == 0x0000

        assert len(roles) == 1
        for role in roles:
            assert role.sop_class_uid == '1.2.3.4'
            assert role.scu_role == False
            assert role.scp_role == True

    def test_no_invalid_return_scp(self):
        """Test that invalid role selection values aren't returned."""
        # If the SCU proposes 0x00 we can't return 0x01
        rq = build_context('1.2.3.4')
        rq_roles = {'1.2.3.4' : (True, False)}

        ac = build_context('1.2.3.4')
        ac.scu_role = True
        ac.scp_role = True

        result, roles = negotiate_as_acceptor([rq], [ac], rq_roles)

        assert roles[0].sop_class_uid == '1.2.3.4'
        assert roles[0].scu_role == True
        assert roles[0].scp_role == False

    def test_no_invalid_return_scu(self):
        """Test that invalid role selection values aren't returned."""
        # If the SCU proposes 0x00 we can't return 0x01
        rq = build_context('1.2.3.4')
        rq_roles = {'1.2.3.4' : (False, True)}

        ac = build_context('1.2.3.4')
        ac.scu_role = True
        ac.scp_role = True

        result, roles = negotiate_as_acceptor([rq], [ac], rq_roles)

        assert roles[0].sop_class_uid == '1.2.3.4'
        assert roles[0].scu_role == False
        assert roles[0].scp_role == True

    @pytest.mark.parametrize("req, acc, out", REFERENCE_ROLES)
    def test_combination_role(self, req, acc, out):
        """Test that a combination of results works correctly."""
        # No role selection
        rq_contexts = []
        ac_contexts = []

        # 0x00 - accepted
        rq_contexts.append(build_context('1.1.1'))
        rq_contexts.append(build_context('1.1.2'))
        rq_contexts.append(build_context('1.1.2'))
        rq_contexts.append(build_context('1.1.3'))
        ac_contexts.append(build_context('1.1.1'))
        ac_contexts.append(build_context('1.1.2'))
        ac_contexts.append(build_context('1.1.3'))

        # 0x01 - user rejected - only achievable with role selection

        # 0x02 - provider rejected - not achievable as acceptor

        # 0x03 - abstract syyntax not supported
        rq_contexts.append(build_context('1.4.1'))
        rq_contexts.append(build_context('1.4.2'))
        rq_contexts.append(build_context('1.4.2'))
        rq_contexts.append(build_context('1.4.3'))

        # 0x04 - transfer syntax not supported
        rq_contexts.append(build_context('1.5.1', '1.2'))
        rq_contexts.append(build_context('1.5.2', '1.2'))
        rq_contexts.append(build_context('1.5.2', '1.2'))
        rq_contexts.append(build_context('1.5.3', '1.2'))
        ac_contexts.append(build_context('1.5.1'))
        ac_contexts.append(build_context('1.5.2'))
        ac_contexts.append(build_context('1.5.3'))

        # Role selection
        rq_roles = {}
        # 0x00 - accepted and 0x01 - user rejected
        for uid in ['2.1.1', '2.1.2', '2.1.2', '2.1.3']:
            rq_contexts.append(build_context(uid))
            rq_roles[uid] = (req[0], req[1])
            cx = build_context(uid)
            cx.scu_role = acc[0]
            cx.scp_role = acc[1]
            ac_contexts.append(cx)

        # 0x03 - abstract syntax not supported
        for uid in ['2.4.1', '2.4.2', '2.4.2', '2.4.3']:
            rq_contexts.append(build_context(uid))
            rq_roles[uid] = (req[0], req[1])

        # 0x04 - transfer syntax not supported
        for uid in ['2.5.1', '2.5.2', '2.5.2', '2.5.3']:
            rq_contexts.append(build_context(uid, '1.2'))
            rq_roles[uid] = (req[0], req[1])
            cx = build_context(uid)
            cx.scu_role = acc[0]
            cx.scp_role = acc[1]
            ac_contexts.append(cx)

        for ii, cx in enumerate(rq_contexts):
            cx.context_id = (ii + 1) * 2 - 1

        results, roles = negotiate_as_acceptor(rq_contexts, ac_contexts, rq_roles)

        out_00 = [cx for cx in results if cx.result == 0x00]
        out_01 = [cx for cx in results if cx.result == 0x01]
        out_02 = [cx for cx in results if cx.result == 0x02]
        out_03 = [cx for cx in results if cx.result == 0x03]
        out_04 = [cx for cx in results if cx.result == 0x04]
        out_na = [cx for cx in results if cx.result is None]

        out_00_role = [cx for cx in out_00 if cx.abstract_syntax[0] == '2']
        # Unique UIDs with role selection
        out_00_uids = set([cx.abstract_syntax for cx in out_00_role])

        # If acceptor has None as role then no SCP/SCU role response
        if None not in acc:
            assert len(out_00_uids) == len(roles)

        # Raw results
        if out == CONTEXT_REJECTED:
            assert len(out_01) == 4
            assert len(out_00) == 4
        else:
            assert len(out_00) == 8
            assert len(out_01) == 0

        # Always
        assert len(out_02) == 0
        assert len(out_03) == 8
        assert len(out_04) == 8
        assert len(out_na) == 0

        # Test individual results
        assert out_00[0].abstract_syntax == '1.1.1'
        assert out_00[1].abstract_syntax == '1.1.2'
        assert out_00[2].abstract_syntax == '1.1.2'
        assert out_00[3].abstract_syntax == '1.1.3'

        for cx in out_00:
            if cx.abstract_syntax[0] == '2':
                assert cx.as_scu == out[2]
                assert cx.as_scp == out[3]
            else:
                assert cx.as_scu is False
                assert cx.as_scp is True

        if out == CONTEXT_REJECTED:
            assert out_01[0].abstract_syntax == '2.1.1'
            assert out_01[1].abstract_syntax == '2.1.2'
            assert out_01[2].abstract_syntax == '2.1.2'
            assert out_01[3].abstract_syntax == '2.1.3'

            for cx in out_01:
                assert cx.as_scu is False
                assert cx.as_scp is False

        for cx in out_02:
            assert cx.as_scu is False
            assert cx.as_scp is False

        for cx in out_03:
            assert cx.as_scu is False
            assert cx.as_scp is False

        for cx in out_04:
            assert cx.as_scu is False
            assert cx.as_scp is False


class TestNegotiateAsRequestorWithRoleSelection(object):
    """Tests negotiate_as_requestor with role selection."""
    @pytest.mark.parametrize("req, acc, out", REFERENCE_ROLES)
    def test_scp_scu_role_negotiation(self, req, acc, out):
        """Test presentation service negotiation with role selection."""
        rq = build_context('1.2.3.4')
        rq.context_id = 1
        rq.scu_role = req[0]
        rq.scp_role = req[1]

        ac = build_context('1.2.3.4')
        ac.context_id = 1
        ac.result = 0x0000
        ac_roles = {'1.2.3.4' : (acc[0], acc[1])}

        result = negotiate_as_requestor([rq], [ac], ac_roles)

        assert result[0].abstract_syntax == '1.2.3.4'
        assert result[0].transfer_syntax[0] == '1.2.840.10008.1.2'
        assert result[0].as_scu == out[0]
        assert result[0].as_scp == out[1]

    def test_multiple_contexts_same_abstract(self):
        """Test that SCP/SCU role neg works with multiple contexts."""
        rq_contexts = [build_context('1.2.3.4'), build_context('1.2.3.4')]
        for ii, context in enumerate(rq_contexts):
            context.context_id = ii * 2 + 1
            context.scu_role = False
            context.scp_role = True
        rq_contexts.append(build_context('1.2.3.4.5'))
        rq_contexts[2].context_id = 5

        ac_roles = {}
        ac = build_context('1.2.3.4')
        ac.context_id = 1
        ac.result = 0x0000
        ac_roles['1.2.3.4'] = (False, True)

        ac2 = build_context('1.2.3.4.1')
        ac2.context_id = 3
        ac2.result = 0x0000
        ac_roles['1.2.3.4.1'] = (False, True)

        ac3 = build_context('1.2.3.4.5')
        ac3.context_id = 5
        ac3.result = 0x0000

        result = negotiate_as_requestor(rq_contexts, [ac, ac2, ac3], ac_roles)
        assert len(result) == 3
        for context in result[:2]:
            assert context.abstract_syntax == '1.2.3.4'
            assert context.transfer_syntax[0] == '1.2.840.10008.1.2'
            assert context.as_scu == False
            assert context.as_scp == True

        assert result[2].abstract_syntax == '1.2.3.4.5'
        assert result[2].transfer_syntax[0] == '1.2.840.10008.1.2'
        assert result[2].as_scu == True
        assert result[2].as_scp == False

    def test_functional(self):
        """Functional test of role negotiation."""
        # Requestor
        context_a = build_context(CompositeInstanceRetrieveWithoutBulkDataGet)
        context_a.context_id = 1
        context_b = build_context(CTImageStorage)
        context_b.context_id = 3
        rq_roles = {CTImageStorage : (False, True)}
        rq_contexts = [context_a, context_b]

        # Acceptor
        context_a = build_context(CompositeInstanceRetrieveWithoutBulkDataGet)
        context_b = build_context(CTImageStorage)
        context_b.scu_role = False
        context_b.scp_role = True
        ac_contexts = [context_a, context_b]

        # Requestor -> Acceptor
        result, roles = negotiate_as_acceptor(rq_contexts, ac_contexts, rq_roles)

        # Acceptor -> Requestor
        ac_roles = {}
        for role in roles:
            ac_roles[role.sop_class_uid] = (role.scu_role, role.scp_role)

        rq_contexts[1].scu_role = False
        rq_contexts[1].scp_role = True
        result = negotiate_as_requestor(rq_contexts, result, ac_roles)

        assert result[0].abstract_syntax == CompositeInstanceRetrieveWithoutBulkDataGet
        assert result[0].as_scu
        assert not result[0].as_scp

        assert result[1].abstract_syntax == CTImageStorage
        assert not result[1].as_scu
        assert result[1].as_scp

    def test_acc_invalid_return_scp(self):
        """Test that the role negotiation is OK if given invalid SCP value."""
        # Requestor
        context_a = build_context(CTImageStorage)
        context_a.context_id = 3
        rq_roles = {CTImageStorage : (True, False)}
        rq_contexts = [context_a]

        # Acceptor
        context_a = build_context(CompositeInstanceRetrieveWithoutBulkDataGet)
        context_b = build_context(CTImageStorage)
        context_b.scu_role = True
        context_b.scp_role = True
        ac_contexts = [context_a, context_b]

        # Requestor -> Acceptor
        result, roles = negotiate_as_acceptor(rq_contexts, ac_contexts, rq_roles)
        # Force invalid SCP role response
        roles[0].scp_role = True

        # Acceptor -> Requestor
        ac_roles = {}
        for role in roles:
            ac_roles[role.sop_class_uid] = (role.scu_role, role.scp_role)

        rq_contexts[0].scu_role = True
        rq_contexts[0].scp_role = False
        result = negotiate_as_requestor(rq_contexts, result, ac_roles)

        assert result[0].as_scu is True
        assert result[0].as_scp is False

    def test_acc_invalid_return_scu(self):
        """Test that the role negotiation is OK if given invalid SCU value."""
        # Requestor
        context_a = build_context(CTImageStorage)
        context_a.context_id = 3
        rq_roles = {CTImageStorage : (False, True)}
        rq_contexts = [context_a]

        # Acceptor
        context_a = build_context(CompositeInstanceRetrieveWithoutBulkDataGet)
        context_b = build_context(CTImageStorage)
        context_b.scu_role = True
        context_b.scp_role = True
        ac_contexts = [context_a, context_b]

        # Requestor -> Acceptor
        result, roles = negotiate_as_acceptor(rq_contexts, ac_contexts, rq_roles)
        # Force invalid SCU role response
        roles[0].scu_role = True

        # Acceptor -> Requestor
        ac_roles = {}
        for role in roles:
            ac_roles[role.sop_class_uid] = (role.scu_role, role.scp_role)

        rq_contexts[0].scu_role = False
        rq_contexts[0].scp_role = True
        result = negotiate_as_requestor(rq_contexts, result, ac_roles)

        assert result[0].as_scu is False
        assert result[0].as_scp is True

    @pytest.mark.parametrize("req, acc, out", REFERENCE_ROLES)
    def test_combination(self, req, acc, out):
        """Test that returned combinations work OK."""
        ## GENERATE ACCEPTOR RESPONSE
        # No role selection
        rq_contexts = []
        ac_contexts = []

        # 0x00 - accepted
        rq_contexts.append(build_context('1.1.1'))
        rq_contexts.append(build_context('1.1.2'))
        rq_contexts.append(build_context('1.1.2'))
        rq_contexts.append(build_context('1.1.3'))
        ac_contexts.append(build_context('1.1.1'))
        ac_contexts.append(build_context('1.1.2'))
        ac_contexts.append(build_context('1.1.3'))

        # 0x01 - user rejected - only achievable with role selection

        # 0x02 - provider rejected - not achievable as acceptor

        # 0x03 - abstract syyntax not supported
        rq_contexts.append(build_context('1.4.1'))
        rq_contexts.append(build_context('1.4.2'))
        rq_contexts.append(build_context('1.4.2'))
        rq_contexts.append(build_context('1.4.3'))

        # 0x04 - transfer syntax not supported
        rq_contexts.append(build_context('1.5.1', '1.2'))
        rq_contexts.append(build_context('1.5.2', '1.2'))
        rq_contexts.append(build_context('1.5.2', '1.2'))
        rq_contexts.append(build_context('1.5.3', '1.2'))
        ac_contexts.append(build_context('1.5.1'))
        ac_contexts.append(build_context('1.5.2'))
        ac_contexts.append(build_context('1.5.3'))

        # Role selection
        rq_roles = {}
        # 0x00 - accepted and 0x01 - user rejected
        for uid in ['2.1.1', '2.1.2', '2.1.2', '2.1.3']:
            rq_contexts.append(build_context(uid))
            rq_roles[uid] = (req[0], req[1])
            cx = build_context(uid)
            cx.scu_role = acc[0]
            cx.scp_role = acc[1]
            ac_contexts.append(cx)

        # 0x03 - abstract syntax not supported
        for uid in ['2.4.1', '2.4.2', '2.4.2', '2.4.3']:
            rq_contexts.append(build_context(uid))
            rq_roles[uid] = (req[0], req[1])

        # 0x04 - transfer syntax not supported
        for uid in ['2.5.1', '2.5.2', '2.5.2', '2.5.3']:
            rq_contexts.append(build_context(uid, '1.2'))
            rq_roles[uid] = (req[0], req[1])
            cx = build_context(uid)
            cx.scu_role = acc[0]
            cx.scp_role = acc[1]
            ac_contexts.append(cx)

        for ii, cx in enumerate(rq_contexts):
            cx.context_id = (ii + 1) * 2 - 1

        results, roles = negotiate_as_acceptor(rq_contexts, ac_contexts, rq_roles)

        ## TEST REQUESTOR NEGOTIATION
        for cx in rq_contexts:
            if '2' == cx.abstract_syntax[0]:
                cx.scu_role = req[0]
                cx.scp_role = req[1]

        roles = {rr.sop_class_uid : (rr.scu_role, rr.scp_role) for rr in roles}
        results = negotiate_as_requestor(rq_contexts, results, roles)

        out_00 = [cx for cx in results if cx.result == 0x00]
        out_01 = [cx for cx in results if cx.result == 0x01]
        out_02 = [cx for cx in results if cx.result == 0x02]
        out_03 = [cx for cx in results if cx.result == 0x03]
        out_04 = [cx for cx in results if cx.result == 0x04]
        out_na = [cx for cx in results if cx.result is None]

        if out != CONTEXT_REJECTED:
            assert len(out_00) == 8
            assert len(out_01) == 0

            for cx in out_00:
                if cx.abstract_syntax[0] == '2':
                    assert cx.as_scu == out[0]
                    assert cx.as_scp == out[1]
                else:
                    assert cx.as_scu is True
                    assert cx.as_scp is False
        else:
            assert len(out_00) == 4
            assert len(out_01) == 4

        # Always
        assert len(out_02) == 0
        assert len(out_03) == 8
        assert len(out_04) == 8
        assert len(out_na) == 0

    def test_one_role_only_scu(self):
        """Test only specifying scu_role in the role selection."""
        ae = AE()
        ae.add_supported_context('1.2.840.10008.1.1', scu_role=True, scp_role=True)
        ae.add_requested_context('1.2.840.10008.1.1')
        scp = ae.start_server(('', 11112), block=False)

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = '1.2.840.10008.1.1'
        role.scu_role = True

        assoc = ae.associate('localhost', 11112, ext_neg=[role])
        assert assoc.is_established
        cx = assoc.accepted_contexts[0]
        assert cx.as_scu is True
        assert cx.as_scp is False
        assoc.release()

        scp.shutdown()

    def test_one_role_only_scp(self):
        """Test only specifying scp_role in the role selection."""
        ae = AE()
        ae.add_supported_context('1.2.840.10008.1.1', scu_role=True, scp_role=True)
        ae.add_requested_context('1.2.840.10008.1.1')
        scp = ae.start_server(('', 11112), block=False)

        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = '1.2.840.10008.1.1'
        role.scp_role = True

        assoc = ae.associate('localhost', 11112, ext_neg=[role])
        assert assoc.is_established
        cx = assoc.accepted_contexts[0]
        assert cx.as_scu is False
        assert cx.as_scp is True
        assoc.release()

        scp.shutdown()


class TestNegotiateAsRequestor(object):
    """Tests negotiate_as_requestor."""
    def setup(self):
        self.test_acc = negotiate_as_acceptor
        self.test_func = negotiate_as_requestor

    def test_no_req_no_acc_raise(self):
        """Test negotiation with no contexts."""
        with pytest.raises(ValueError):
            result = self.test_func([], [])

    def test_one_req_no_acc(self):
        """Test negotiation with one requestor, no acceptor contexts."""
        context = PresentationContext()
        context.context_id = 1
        context.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
        context.transfer_syntax = ['1.2.840.10008.1.2']
        result = self.test_func([context], [])

        assert len(result) == 1
        context = result[0]
        assert context.context_id == 1
        assert context.abstract_syntax == '1.2.840.10008.5.1.4.1.1.2'
        assert context.transfer_syntax[0] == '1.2.840.10008.1.2'
        assert len(context.transfer_syntax) == 1
        assert context.result == 0x02

    def test_no_req_one_acc_raise(self):
        """Test negotiation with no requestor, one acceptor contexts."""
        context = PresentationContext()
        context.context_id = 1
        context.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
        context.transfer_syntax = ['1.2.840.10008.1.2']
        with pytest.raises(ValueError):
            result = self.test_func([], [context])

    def test_dupe_abs_req_no_acc(self):
        """Test negotiation with duplicate requestor, no acceptor contexts."""
        context_a = PresentationContext()
        context_a.context_id = 1
        context_a.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
        context_a.transfer_syntax = ['1.2.840.10008.1.2']

        context_b = PresentationContext()
        context_b.context_id = 3
        context_b.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
        context_b.transfer_syntax = ['1.2.840.10008.1.2.1']

        context_c = PresentationContext()
        context_c.context_id = 5
        context_c.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
        context_c.transfer_syntax = ['1.2.840.10008.1.2.2']

        rq_contexts = [context_a, context_b, context_c]
        acc_contexts, roles = self.test_acc(rq_contexts, [])

        for context in acc_contexts:
            context._abstract_syntax = None

        result = self.test_func(rq_contexts, acc_contexts)

        assert len(result) == 3
        for context in result:
            assert context.context_id in [1, 3, 5]
            assert context.abstract_syntax == '1.2.840.10008.5.1.4.1.1.2'
            assert context.result == 0x03

    def test_dupe_abs_req(self):
        """Test negotiation with duplicate requestor, no acceptor contexts."""
        context_a = PresentationContext()
        context_a.context_id = 1
        context_a.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
        context_a.transfer_syntax = ['1.2.840.10008.1.2']

        context_b = PresentationContext()
        context_b.context_id = 3
        context_b.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
        context_b.transfer_syntax = ['1.2.840.10008.1.2.1']

        context_c = PresentationContext()
        context_c.context_id = 5
        context_c.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
        context_c.transfer_syntax = ['1.2.840.10008.1.2.2']
        t_syntax = ['1.2.840.10008.1.2',
                    '1.2.840.10008.1.2.1',
                    '1.2.840.10008.1.2.2']
        context_d = PresentationContext()
        context_d.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
        context_d.transfer_syntax = t_syntax

        rq_contexts = [context_a, context_b, context_c]
        acc_contexts, roles = self.test_acc(rq_contexts, [context_d])

        for context in acc_contexts:
            context._abstract_syntax = None

        result = self.test_func(rq_contexts, acc_contexts)

        assert len(result) == 3
        for ii, context in enumerate(result):
            assert context.context_id in [1, 3, 5]
            assert context.abstract_syntax == '1.2.840.10008.5.1.4.1.1.2'
            assert context.result == 0x00
            assert context.transfer_syntax == [t_syntax[ii]]

    def test_one_req_one_acc_match(self):
        """Test negotiation one req/acc, matching accepted."""
        context = PresentationContext()
        context.context_id = 1
        context.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
        context.transfer_syntax = ['1.2.840.10008.1.2']

        rq_contexts = [context]
        acc_contexts, roles = self.test_acc([context], [context])

        for context in acc_contexts:
            context._abstract_syntax = None

        result = self.test_func(rq_contexts, acc_contexts)

        assert len(result) == 1
        context = result[0]
        assert context.context_id == 1
        assert context.abstract_syntax == '1.2.840.10008.5.1.4.1.1.2'
        assert context.result == 0x00
        assert context.transfer_syntax == ['1.2.840.10008.1.2']

    def test_one_req_one_acc_accept_trans(self):
        """Test negotiation one req/acc, matching accepted, multi trans."""
        context = PresentationContext()
        context.context_id = 1
        context.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
        context.transfer_syntax = ['1.2.840.10008.1.2',
                                   '1.2.840.10008.1.2.1',
                                   '1.2.840.10008.1.2.2']
        rq_contexts = [context]
        acc_contexts, roles = self.test_acc([context], [context])

        for context in acc_contexts:
            context._abstract_syntax = None

        result = self.test_func(rq_contexts, acc_contexts)
        assert len(result) == 1
        context = result[0]
        assert context.context_id == 1
        assert context.abstract_syntax == '1.2.840.10008.5.1.4.1.1.2'
        assert context.result == 0x00
        assert context.transfer_syntax == ['1.2.840.10008.1.2']

    def test_one_req_one_acc_accept_trans_diff(self):
        """Test negotiation one req/acc, matching accepted, multi trans."""
        context_a = PresentationContext()
        context_a.context_id = 1
        context_a.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
        context_a.transfer_syntax = ['1.2.840.10008.1.2',
                                   '1.2.840.10008.1.2.1',
                                   '1.2.840.10008.1.2.2']
        context_b = PresentationContext()
        context_b.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
        context_b.transfer_syntax = ['1.2.840.10008.1.2.2']
        rq_contexts = [context_a]
        acc_contexts, roles = self.test_acc(rq_contexts, [context_b])

        for context in acc_contexts:
            context._abstract_syntax = None

        result = self.test_func(rq_contexts, acc_contexts)

        assert len(result) == 1
        context = result[0]
        assert context.context_id == 1
        assert context.abstract_syntax == '1.2.840.10008.5.1.4.1.1.2'
        assert context.result == 0x00
        assert context.transfer_syntax == ['1.2.840.10008.1.2.2']

    def test_one_req_one_acc_reject_trans(self):
        """Test negotiation one req/acc, matching rejected trans"""
        context_a = PresentationContext()
        context_a.context_id = 1
        context_a.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
        context_a.transfer_syntax = ['1.2.840.10008.1.2',
                                     '1.2.840.10008.1.2.1']
        context_b = PresentationContext()
        context_b.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
        context_b.transfer_syntax = ['1.2.840.10008.1.2.2']
        rq_contexts = [context_a]
        acc_contexts, roles = self.test_acc(rq_contexts, [context_b])

        for context in acc_contexts:
            context._abstract_syntax = None

        result = self.test_func(rq_contexts, acc_contexts)

        assert len(result) == 1
        context = result[0]
        assert context.context_id == 1
        assert context.abstract_syntax == '1.2.840.10008.5.1.4.1.1.2'
        assert context.result == 0x04

    def test_one_req_one_acc_mismatch(self):
        """Test negotiation one req/acc, mismatched rejected"""
        context_a = PresentationContext()
        context_a.context_id = 1
        context_a.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
        context_a.transfer_syntax = ['1.2.840.10008.1.2',
                                     '1.2.840.10008.1.2.1']
        context_b = PresentationContext()
        context_b.abstract_syntax = '1.2.840.10008.5.1.4.1.1.4'
        context_b.transfer_syntax = ['1.2.840.10008.1.2.1']
        rq_contexts = [context_a]
        acc_contexts, roles = self.test_acc(rq_contexts, [context_b])

        for context in acc_contexts:
            context._abstract_syntax = None

        result = self.test_func(rq_contexts, acc_contexts)

        assert len(result) == 1
        context = result[0]
        assert context.context_id == 1
        assert context.abstract_syntax == '1.2.840.10008.5.1.4.1.1.2'
        assert context.result == 0x03

    def test_private_transfer_syntax(self):
        """Test negotiation with private transfer syntax"""
        context_a = PresentationContext()
        context_a.context_id = 1
        context_a.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
        context_a.transfer_syntax = ['1.2.3.4']
        context_b = PresentationContext()
        context_b.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
        context_b.transfer_syntax = ['1.2.840.10008.1.2.1',
                                     '1.2.3.4']

        acc_contexts, roles = self.test_acc([context_a], [context_b])

        for context in acc_contexts:
            context._abstract_syntax = None

        result = self.test_func([context_a], acc_contexts)

        assert len(result) == 1
        context = result[0]
        assert context.context_id == 1
        assert context.abstract_syntax == '1.2.840.10008.5.1.4.1.1.2'
        assert context.result == 0x00
        assert context.transfer_syntax == ['1.2.3.4']

    def test_private_abstract_syntax(self):
        """Test negotiation with private abstract syntax"""
        context_a = PresentationContext()
        context_a.context_id = 1
        context_a.abstract_syntax = '1.2.3.4'
        context_a.transfer_syntax = ['1.2.840.10008.1.2.1']
        context_b = PresentationContext()
        context_b.abstract_syntax = '1.2.3.4'
        context_b.transfer_syntax = ['1.2.840.10008.1.2.1']
        rq_contexts = [context_a]
        acc_contexts, roles = self.test_acc(rq_contexts, [context_b])

        for context in acc_contexts:
            context._abstract_syntax = None

        result = self.test_func(rq_contexts, acc_contexts)

        assert len(result) == 1
        context = result[0]
        assert context.context_id == 1
        assert context.abstract_syntax == '1.2.3.4'
        assert context.result == 0x00
        assert context.transfer_syntax == ['1.2.840.10008.1.2.1']

    def test_typical(self):
        """Test a typical set of presentation context negotiations."""
        req_contexts = []
        for ii, context in enumerate(StoragePresentationContexts):
            pc = PresentationContext()
            pc.context_id = ii * 2 + 1
            pc.abstract_syntax = context.abstract_syntax
            pc.transfer_syntax = ['1.2.840.10008.1.2',
                                  '1.2.840.10008.1.2.1',
                                  '1.2.840.10008.1.2.2']
            req_contexts.append(pc)

        acc_contexts = []
        for uid in UID_dictionary:
            pc = PresentationContext()
            pc.abstract_syntax = uid
            pc.transfer_syntax = ['1.2.840.10008.1.2',
                                  '1.2.840.10008.1.2.1',
                                  '1.2.840.10008.1.2.2']
            acc_contexts.append(pc)

        acc_contexts, roles = self.test_acc(req_contexts, acc_contexts)

        for context in acc_contexts:
            context._abstract_syntax = None

        results = self.test_func(req_contexts, acc_contexts)

        assert len(results) == len(req_contexts)
        for ii, context in enumerate(req_contexts):
            assert results[ii].context_id == context.context_id
            assert results[ii].abstract_syntax == context.abstract_syntax
            if results[ii].abstract_syntax == '1.2.840.10008.5.1.4.1.1.1.1.1.1':
                assert results[ii].result == 0x03
            elif results[ii].abstract_syntax == '1.2.840.10008.5.1.1.4.1.1.3.1':
                assert results[ii].result == 0x03
            else:
                assert results[ii].result == 0x00
                assert results[ii].transfer_syntax == ['1.2.840.10008.1.2']

    def test_acceptor_empty_context(self):
        """Test negotiation when the acceptor cx has no transfer syntax."""
        # Requestor contexts
        context_a = PresentationContext()
        context_a.context_id = 1
        context_a.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
        context_a.transfer_syntax = ['1.2.840.10008.1.2',
                                     '1.2.840.10008.1.2.1']
        context_b = PresentationContext()
        context_b.context_id = 3
        context_b.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2.1'
        context_b.transfer_syntax = ['1.2.840.10008.1.2',
                                     '1.2.840.10008.1.2.1']
        rq_contexts = [context_a, context_b]

        # Acceptor contexts
        context_c = PresentationContext()
        context_c.context_id = 1
        context_c.transfer_syntax = ['1.2.840.10008.1.2']
        context_c.result = 0x00

        context_d = PresentationContext()
        context_d.context_id = 3
        context_d.result = 0x01
        acc_contexts = [context_c, context_d]

        #acc_contexts, roles = self.test_acc(rq_contexts, [context_b])

        result = self.test_func(rq_contexts, acc_contexts)
        for ii in result:
            print(ii)

        assert len(result) == 2
        context = result[0]
        assert context.context_id == 1
        assert context.abstract_syntax == '1.2.840.10008.5.1.4.1.1.2'
        assert context.result == 0x00
        context = result[1]
        assert context.context_id == 3
        assert context.abstract_syntax == '1.2.840.10008.5.1.4.1.1.2.1'
        assert context.result == 0x01


def test_default_transfer_syntaxes():
    """Test that the default transfer syntaxes are correct."""
    assert len(DEFAULT_TRANSFER_SYNTAXES) == 4
    assert '1.2.840.10008.1.2' in DEFAULT_TRANSFER_SYNTAXES
    assert '1.2.840.10008.1.2.1' in DEFAULT_TRANSFER_SYNTAXES
    assert '1.2.840.10008.1.2.1.99' in DEFAULT_TRANSFER_SYNTAXES
    assert '1.2.840.10008.1.2.2' in DEFAULT_TRANSFER_SYNTAXES


def test_build_context():
    """Test build_context()"""
    context = build_context('1.2.840.10008.1.1')
    assert context.abstract_syntax == '1.2.840.10008.1.1'
    assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
    assert context.context_id is None

    context = build_context('1.2.840.10008.1.1', ['1.2.3', '4.5.6'])
    assert context.abstract_syntax == '1.2.840.10008.1.1'
    assert context.transfer_syntax == ['1.2.3', '4.5.6']
    assert context.context_id is None

    context = build_context('1.2.840.10008.1.1', '12.3')
    assert context.abstract_syntax == '1.2.840.10008.1.1'
    assert context.transfer_syntax == ['12.3']
    assert context.context_id is None

    context = build_context(VerificationSOPClass)
    assert context.abstract_syntax == '1.2.840.10008.1.1'
    assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
    assert context.context_id is None


class TestServiceContexts(object):
    def test_application_event(self):
        """Tests with application event logging presentation contexts"""
        contexts = ApplicationEventLoggingPresentationContexts
        assert len(contexts) == 2

        for context in contexts:
            assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
            assert context.context_id is None

        assert contexts[0].abstract_syntax == '1.2.840.10008.1.40'
        assert contexts[1].abstract_syntax == '1.2.840.10008.1.42'

    def test_basic_worklist(self):
        """Test the basic worklist service presentation contexts."""
        contexts = BasicWorklistManagementPresentationContexts
        assert len(contexts) == 1

        assert contexts[0].transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
        assert contexts[0].context_id is None
        assert contexts[0].abstract_syntax == '1.2.840.10008.5.1.4.31'

    def test_color_palette(self):
        """Tests with color palette presentation contexts"""
        contexts = ColorPalettePresentationContexts
        assert len(contexts) == 3

        for context in contexts:
            assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
            assert context.context_id is None

        assert contexts[0].abstract_syntax == '1.2.840.10008.5.1.4.39.2'
        assert contexts[1].abstract_syntax == '1.2.840.10008.5.1.4.39.3'
        assert contexts[2].abstract_syntax == '1.2.840.10008.5.1.4.39.4'

    def test_defined_procedure(self):
        """Tests with defined procedure protocol presentation contexts"""
        contexts = DefinedProcedureProtocolPresentationContexts
        assert len(contexts) == 3

        for context in contexts:
            assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
            assert context.context_id is None

        assert contexts[0].abstract_syntax == '1.2.840.10008.5.1.4.20.1'
        assert contexts[1].abstract_syntax == '1.2.840.10008.5.1.4.20.2'
        assert contexts[2].abstract_syntax == '1.2.840.10008.5.1.4.20.3'

    def test_display_system(self):
        """Tests with display system presentation contexts"""
        contexts = DisplaySystemPresentationContexts
        assert len(contexts) == 1

        for context in contexts:
            assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
            assert context.context_id is None

        assert contexts[0].abstract_syntax == '1.2.840.10008.5.1.1.40'

    def test_hanging_protocol(self):
        """Tests with hanging protocol presentation contexts"""
        contexts = HangingProtocolPresentationContexts
        assert len(contexts) == 3

        for context in contexts:
            assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
            assert context.context_id is None

        assert contexts[0].abstract_syntax == '1.2.840.10008.5.1.4.38.2'
        assert contexts[1].abstract_syntax == '1.2.840.10008.5.1.4.38.3'
        assert contexts[2].abstract_syntax == '1.2.840.10008.5.1.4.38.4'

    def test_implant_template(self):
        """Tests with implant template presentation contexts"""
        contexts = ImplantTemplatePresentationContexts
        assert len(contexts) == 9

        for context in contexts:
            assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
            assert context.context_id is None

        assert contexts[0].abstract_syntax == '1.2.840.10008.5.1.4.43.2'
        assert contexts[1].abstract_syntax == '1.2.840.10008.5.1.4.43.3'
        assert contexts[2].abstract_syntax == '1.2.840.10008.5.1.4.43.4'
        assert contexts[3].abstract_syntax == '1.2.840.10008.5.1.4.44.2'
        assert contexts[4].abstract_syntax == '1.2.840.10008.5.1.4.44.3'
        assert contexts[5].abstract_syntax == '1.2.840.10008.5.1.4.44.4'
        assert contexts[6].abstract_syntax == '1.2.840.10008.5.1.4.45.2'
        assert contexts[7].abstract_syntax == '1.2.840.10008.5.1.4.45.3'
        assert contexts[8].abstract_syntax == '1.2.840.10008.5.1.4.45.4'

    def test_instance_availability(self):
        """Tests with instance availability presentation contexts"""
        contexts = InstanceAvailabilityPresentationContexts
        assert len(contexts) == 1

        for context in contexts:
            assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
            assert context.context_id is None

        assert contexts[0].abstract_syntax == '1.2.840.10008.5.1.4.33'

    def test_media_creation(self):
        """Tests with media creation presentation contexts"""
        contexts = MediaCreationManagementPresentationContexts
        assert len(contexts) == 1

        for context in contexts:
            assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
            assert context.context_id is None

        assert contexts[0].abstract_syntax == '1.2.840.10008.5.1.1.33'

    def test_media_storage(self):
        """Tests with media storage presentation contexts"""
        contexts = MediaStoragePresentationContexts
        assert len(contexts) == 1

        for context in contexts:
            assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
            assert context.context_id is None

        assert contexts[0].abstract_syntax == '1.2.840.10008.1.3.10'

    def test_non_patient(self):
        """Tests with non patient object presentation contexts"""
        contexts = NonPatientObjectPresentationContexts
        assert len(contexts) == 7

        for context in contexts:
            assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
            assert context.context_id is None

        assert contexts[0].abstract_syntax == '1.2.840.10008.5.1.4.1.1.200.1'
        assert contexts[1].abstract_syntax == '1.2.840.10008.5.1.4.1.1.200.3'
        assert contexts[2].abstract_syntax == '1.2.840.10008.5.1.4.38.1'
        assert contexts[3].abstract_syntax == '1.2.840.10008.5.1.4.39.1'
        assert contexts[4].abstract_syntax == '1.2.840.10008.5.1.4.43.1'
        assert contexts[5].abstract_syntax == '1.2.840.10008.5.1.4.44.1'
        assert contexts[6].abstract_syntax == '1.2.840.10008.5.1.4.45.1'

    def test_print_management(self):
        """Tests with print management presentation contexts"""
        contexts = PrintManagementPresentationContexts
        assert len(contexts) == 11

        for context in contexts:
            assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
            assert context.context_id is None

        assert contexts[0].abstract_syntax == '1.2.840.10008.5.1.1.1'
        assert contexts[1].abstract_syntax == '1.2.840.10008.5.1.1.14'
        assert contexts[2].abstract_syntax == '1.2.840.10008.5.1.1.15'
        assert contexts[3].abstract_syntax == '1.2.840.10008.5.1.1.16'
        assert contexts[4].abstract_syntax == '1.2.840.10008.5.1.1.16.376'
        assert contexts[5].abstract_syntax == '1.2.840.10008.5.1.1.18'
        assert contexts[6].abstract_syntax == '1.2.840.10008.5.1.1.2'
        assert contexts[7].abstract_syntax == '1.2.840.10008.5.1.1.23'
        assert contexts[8].abstract_syntax == '1.2.840.10008.5.1.1.4'
        assert contexts[9].abstract_syntax == '1.2.840.10008.5.1.1.4.1'
        assert contexts[10].abstract_syntax == '1.2.840.10008.5.1.1.9'

    def test_procedure_step(self):
        """Tests with procedure step presentation contexts"""
        contexts = ProcedureStepPresentationContexts
        assert len(contexts) == 3

        for context in contexts:
            assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
            assert context.context_id is None

        assert contexts[0].abstract_syntax == '1.2.840.10008.3.1.2.3.3'
        assert contexts[1].abstract_syntax == '1.2.840.10008.3.1.2.3.4'
        assert contexts[2].abstract_syntax == '1.2.840.10008.3.1.2.3.5'

    def test_protocol_approval(self):
        """Tests with protocol approval presentation contexts"""
        contexts = ProtocolApprovalPresentationContexts
        assert len(contexts) == 3

        for context in contexts:
            assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
            assert context.context_id is None

        assert contexts[0].abstract_syntax == '1.2.840.10008.5.1.4.1.1.200.4'
        assert contexts[1].abstract_syntax == '1.2.840.10008.5.1.4.1.1.200.5'
        assert contexts[2].abstract_syntax == '1.2.840.10008.5.1.4.1.1.200.6'

    def test_qr(self):
        """Test the query/retrieve service presentation contexts."""
        contexts = QueryRetrievePresentationContexts
        assert len(contexts) == 12

        for context in contexts:
            assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
            assert context.context_id is None

        assert contexts[0].abstract_syntax == '1.2.840.10008.5.1.4.1.2.1.1'
        assert contexts[4].abstract_syntax == '1.2.840.10008.5.1.4.1.2.2.2'
        assert contexts[-1].abstract_syntax == '1.2.840.10008.5.1.4.1.2.5.3'

    def test_relevant_patient(self):
        """Tests with relevant patient info presentation contexts"""
        contexts = RelevantPatientInformationPresentationContexts
        assert len(contexts) == 3

        for context in contexts:
            assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
            assert context.context_id is None

        assert contexts[0].abstract_syntax == '1.2.840.10008.5.1.4.37.1'
        assert contexts[1].abstract_syntax == '1.2.840.10008.5.1.4.37.2'
        assert contexts[2].abstract_syntax == '1.2.840.10008.5.1.4.37.3'

    def test_rt_machine(self):
        """Tests with RT machine verification presentation contexts"""
        contexts = RTMachineVerificationPresentationContexts
        assert len(contexts) == 2

        for context in contexts:
            assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
            assert context.context_id is None

        assert contexts[0].abstract_syntax == '1.2.840.10008.5.1.4.34.8'
        assert contexts[1].abstract_syntax == '1.2.840.10008.5.1.4.34.9'

    def test_storage(self):
        """Test the storage service presentation contexts"""
        contexts = StoragePresentationContexts
        assert len(contexts) == 128

        for context in contexts:
            assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
            assert context.context_id is None

        assert contexts[0].abstract_syntax == '1.2.840.10008.5.1.4.1.1.1'
        assert contexts[80].abstract_syntax == '1.2.840.10008.5.1.4.1.1.77.1.2'
        assert contexts[-1].abstract_syntax == '1.2.840.10008.5.1.4.1.1.9.2.1'

    def test_storage_commitement(self):
        """Tests with storage commitment presentation contexts"""
        contexts = StorageCommitmentPresentationContexts
        assert len(contexts) == 1

        for context in contexts:
            assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
            assert context.context_id is None

        assert contexts[0].abstract_syntax == '1.2.840.10008.1.20.1'

    def test_substance_admin(self):
        """Tests with substance administration presentation contexts"""
        contexts = SubstanceAdministrationPresentationContexts
        assert len(contexts) == 2

        for context in contexts:
            assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
            assert context.context_id is None

        assert contexts[0].abstract_syntax == '1.2.840.10008.5.1.4.41'
        assert contexts[1].abstract_syntax == '1.2.840.10008.5.1.4.42'

    def test_unified_procedure(self):
        """Tests with unified procedure presentation contexts"""
        contexts = UnifiedProcedurePresentationContexts
        assert len(contexts) == 5

        for context in contexts:
            assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
            assert context.context_id is None

        assert contexts[0].abstract_syntax == '1.2.840.10008.5.1.4.34.6.1'
        assert contexts[1].abstract_syntax == '1.2.840.10008.5.1.4.34.6.2'
        assert contexts[2].abstract_syntax == '1.2.840.10008.5.1.4.34.6.3'
        assert contexts[3].abstract_syntax == '1.2.840.10008.5.1.4.34.6.4'
        assert contexts[4].abstract_syntax == '1.2.840.10008.5.1.4.34.6.5'

    def test_verification(self):
        """Test the verification service presentation contexts."""
        contexts = VerificationPresentationContexts
        assert len(contexts) == 1
        assert contexts[0].abstract_syntax == '1.2.840.10008.1.1'
        assert contexts[0].transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
        assert contexts[0].context_id is None


class TestBuildRole(object):
    """Tests for presentation.build_role."""
    def test_default(self):
        """Test the default role."""
        role = build_role('1.2.3')

        assert role.sop_class_uid == '1.2.3'
        assert role.scu_role is False
        assert role.scp_role is False

    def test_various(self):
        """Test various combinations of role."""
        role = build_role('1.2.3', scu_role=True)
        assert role.sop_class_uid == '1.2.3'
        assert role.scu_role is True
        assert role.scp_role is False

        role = build_role('1.2.3', scp_role=True)
        assert role.sop_class_uid == '1.2.3'
        assert role.scu_role is False
        assert role.scp_role is True

        role = build_role('1.2.3', scu_role=True, scp_role=True)
        assert role.sop_class_uid == '1.2.3'
        assert role.scu_role is True
        assert role.scp_role is True
