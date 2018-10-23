"""Tests for the presentation module."""
import logging
import sys

import pytest

from pydicom._uid_dict import UID_dictionary
from pydicom.uid import UID

from pynetdicom3 import StoragePresentationContexts
from pynetdicom3.presentation import (
    PresentationContext,
    PresentationService,
    DEFAULT_TRANSFER_SYNTAXES,
    VerificationPresentationContexts,
    StoragePresentationContexts,
    QueryRetrievePresentationContexts,
    BasicWorklistManagementPresentationContexts,
    RelevantPatientInformationPresentationContexts,
    SubstanceAdministrationPresentationContexts,
    NonPatientObjectPresentationContexts,
    HangingProtocolPresentationContexts,
    DefinedProcedureProtocolPresentationContexts,
    ColorPalettePresentationContexts,
    ImplantTemplatePresentationContexts,
    DisplaySystemPresentationContexts,
    build_context,
)
from pynetdicom3.sop_class import VerificationSOPClass


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
        assert pc.result is None

    def test_add_transfer_syntax(self):
        """Test adding transfer syntaxes"""
        pc = PresentationContext()
        pc.context_id = 1
        pc.add_transfer_syntax('1.2.840.10008.1.2')
        pc.add_transfer_syntax(b'1.2.840.10008.1.2.1')
        pc.add_transfer_syntax(UID('1.2.840.10008.1.2.2'))
        pc.add_transfer_syntax(UID(''))

        # Test adding an invalid value
        pc.add_transfer_syntax(1234)
        assert 1234 not in pc.transfer_syntax

    @pytest.mark.skipif(sys.version_info[:2] == (3, 4), reason='pytest missing caplog')
    def test_add_transfer_syntax_nonconformant(self, caplog):
        """Test adding non-conformant transfer syntaxes"""
        caplog.set_level(logging.DEBUG, logger='pynetdicom3.presentation')
        pc = PresentationContext()
        pc.context_id = 1
        pc.add_transfer_syntax('1.2.3.')
        assert ("A non-conformant UID has been added to 'transfer_syntax'"
            in caplog.text)

        pc.add_transfer_syntax('1.2.840.10008.1.1')
        assert ("A UID has been added to 'transfer_syntax' that is not a "
               "transfer syntax" in caplog.text)

    def test_add_private_transfer_syntax(self):
        """Test adding private transfer syntaxes"""
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
        pc_a._scp_role = True
        assert not pc_a == pc_b
        pc_b._scp_role = True
        assert pc_a == pc_b
        pc_a._scu_role = True
        assert not pc_a == pc_b
        pc_b._scu_role = True
        assert pc_a == pc_b
        assert not 'a' == pc_b

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

    @pytest.mark.skipif(sys.version_info[:2] == (3, 4), reason='pytest missing caplog')
    def test_abstract_syntax_nonconformant(self, caplog):
        """Test adding non-conformant abstract syntaxes"""
        caplog.set_level(logging.DEBUG, logger='pynetdicom3.presentation')
        pc = PresentationContext()
        pc.context_id = 1
        pc.abstract_syntax = UID('1.4.1.')
        assert pc.abstract_syntax == UID('1.4.1.')
        assert isinstance(pc.abstract_syntax, UID)

        assert ("'abstract_syntax' set to a non-conformant UID" in caplog.text)

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

    @pytest.mark.skipif(sys.version_info[:2] == (3, 4), reason='pytest missing caplog')
    def test_transfer_syntax_nonconformant(self, caplog):
        """Test setting non-conformant transfer syntaxes"""
        caplog.set_level(logging.DEBUG, logger='pynetdicom3.presentation')
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


class TestPresentationServiceAcceptor(object):
    """Tests for the PresentationService class when running as acceptor."""
    def setup(self):
        ps = PresentationService()
        self.test_func = ps.negotiate_as_acceptor

    def test_no_req_no_acc(self):
        """Test negotiation with no contexts."""
        result = self.test_func([], [])
        assert result == []

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
        assert context.result == 0x03

    def test_no_req_one_acc(self):
        """Test negotiation with no requestor, one acceptor contexts."""
        context = PresentationContext()
        context.context_id = 1
        context.abstract_syntax = '1.2.840.10008.5.1.4.1.1.2'
        context.transfer_syntax = ['1.2.840.10008.1.2']
        result = self.test_func([], [context])
        assert result == []

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
        result = self.test_func(context_list, [])
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
        context_list = [context_a, context_b, context_c]
        result = self.test_func(context_list, [context_d])
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
        result = self.test_func([context], [context])
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
        result = self.test_func([context], [context])
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

        result = self.test_func([context_a], [context_b])
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
        result = self.test_func([context_a], [context_b])
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
        context_b.transfer_syntax = ['1.2.840.10008.1.2.2']
        result = self.test_func([context_a], [context_b])
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
        result = self.test_func([context_a], [context_b])
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

        result = self.test_func([context_a], [context_b])
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


@pytest.mark.skip()
class TestPresentationServiceAcceptorWithRoleSelection(object):
    """Tests for the PresentationService as acceptor with role selection."""
    @pytest.mark.parametrize("req, acc, out", [
        ((None, None), (None, None), (False, True)),
        ((None, None), (True, True), (False, True)),
        ((None, None), (True, False), (False, True)),
        ((None, None), (False, False), (False, True)),
        ((None, None), (False, True), (False, True)),
        ((True, True), (None, None), (False, True)),
        ((True, True), (True, True), (True, True)),
        ((True, True), (True, False), (True, True)),
        ((True, True), (False, False), (False, True)),
        ((True, True), (False, True), (False, True)),
        ((False, True), (None, None), (False, True)),
        ((False, True), (True, True), (False, True)),
        ((False, True), (True, False), (False, True)),
        ((False, True), (False, False), (False, True)),
        ((False, True), (False, True), (False, True)),
        ((False, False), (None, None), (False, True)),
        ((False, False), (True, True), (False, True)),
        ((False, False), (True, False), (False, False)),
        ((False, False), (False, False), (False, False)),
        ((False, False), (False, True), (False, True)),
        ((True, False), (None, None), (False, True)),
        ((True, False), (True, True), (True, True)),
        ((True, False), (True, False), (True, False)),
        ((True, False), (False, False), (False, False)),
        ((True, False), (False, True), (False, True)),
    ])
    def test_scp_scu_role_negotiation(self, req, acc, out):
        """Test presentation service negotiation with role selection."""
        # Rules!
        # - If the requestor doesn't ask, then there is no reply
        # - If the requestor is False then the reply is False
        # - If the requestor is True then the reply is either True or False
        #   - If the acceptor is True then the reply is True
        #   - If the acceptor is False then the reply is False
        # Note: if the requestor and acceptor can't agree then the default
        # roles should be used, which as we are acceptor is SCP True, SCU False
        rq = PresentationContext(1,
                                 '1.2.3.4',
                                 ['1.2.840.10008.1.2'])
        rq.SCP = req[0]
        rq.SCU = req[1]

        ac = PresentationContext(1,
                                 '1.2.3.4',
                                 ['1.2.840.10008.1.2'])
        ac.SCP = acc[0]
        ac.SCU = acc[0]
        result = self.test_func([rq], [ac])

        assert result[0].abstract_syntax == '1.2.3.4'
        assert result[0].transfer_syntax[0] == '1.2.840.10008.1.2'
        assert result[0].SCP == out[0]
        assert result[0].SCU == out[1]
        assert result[0].result == 0x00


class TestPresentationServiceRequestor(object):
    """Tests for the PresentationService class when running as requestor."""
    def setup(self):
        ps = PresentationService()
        self.test_acc = ps.negotiate_as_acceptor
        self.test_func = ps.negotiate_as_requestor

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
        acc_contexts = self.test_acc(rq_contexts, [])

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
        acc_contexts = self.test_acc(rq_contexts, [context_d])

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
        acc_contexts = self.test_acc([context], [context])

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
        acc_contexts = self.test_acc([context], [context])

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
        acc_contexts = self.test_acc(rq_contexts, [context_b])

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
        acc_contexts = self.test_acc(rq_contexts, [context_b])

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
        acc_contexts = self.test_acc(rq_contexts, [context_b])

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

        acc_contexts = self.test_acc([context_a], [context_b])

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
        acc_contexts = self.test_acc(rq_contexts, [context_b])

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

        acc_contexts = self.test_acc(req_contexts, acc_contexts)

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


def test_default_transfer_syntaxes():
    """Test that the default transfer syntaxes are correct."""
    assert len(DEFAULT_TRANSFER_SYNTAXES) == 3
    assert '1.2.840.10008.1.2' in DEFAULT_TRANSFER_SYNTAXES
    assert '1.2.840.10008.1.2.1' in DEFAULT_TRANSFER_SYNTAXES
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
    def test_verification(self):
        """Test the verification service presentation contexts."""
        contexts = VerificationPresentationContexts
        assert len(contexts) == 1
        assert contexts[0].abstract_syntax == '1.2.840.10008.1.1'
        assert contexts[0].transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
        assert contexts[0].context_id is None

    def test_storage(self):
        """Test the storage service presentation contexts"""
        contexts = StoragePresentationContexts
        assert len(contexts) == 115

        for context in contexts:
            assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
            assert context.context_id is None

        assert contexts[0].abstract_syntax == '1.2.840.10008.5.1.4.1.1.1'
        assert contexts[80].abstract_syntax == '1.2.840.10008.5.1.4.1.1.78.8'
        assert contexts[-1].abstract_syntax == '1.2.840.10008.5.1.4.34.10'

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

    def test_worklist(self):
        """Test the basic worklist service presentation contexts."""
        contexts = BasicWorklistManagementPresentationContexts
        assert len(contexts) == 1

        assert contexts[0].transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
        assert contexts[0].context_id is None
        assert contexts[0].abstract_syntax == '1.2.840.10008.5.1.4.31'

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

    def test_substance_admin(self):
        """Tests with substance administration presentation contexts"""
        contexts = SubstanceAdministrationPresentationContexts
        assert len(contexts) == 2

        for context in contexts:
            assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
            assert context.context_id is None

        assert contexts[0].abstract_syntax == '1.2.840.10008.5.1.4.41'
        assert contexts[1].abstract_syntax == '1.2.840.10008.5.1.4.42'

    def test_non_patient(self):
        """Tests with non patient object presentation contexts"""
        contexts = NonPatientObjectPresentationContexts
        assert len(contexts) == 7

        for context in contexts:
            assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
            assert context.context_id is None

        assert contexts[0].abstract_syntax == '1.2.840.10008.5.1.4.38.1'
        assert contexts[1].abstract_syntax == '1.2.840.10008.5.1.4.39.1'
        assert contexts[2].abstract_syntax == '1.2.840.10008.5.1.4.43.1'
        assert contexts[3].abstract_syntax == '1.2.840.10008.5.1.4.44.1'
        assert contexts[4].abstract_syntax == '1.2.840.10008.5.1.4.45.1'
        assert contexts[5].abstract_syntax == '1.2.840.10008.5.1.4.1.1.200.1'
        assert contexts[6].abstract_syntax == '1.2.840.10008.5.1.4.1.1.200.3'

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

    def test_display_system(self):
        """Tests with display system presentation contexts"""
        contexts = DisplaySystemPresentationContexts
        assert len(contexts) == 1

        for context in contexts:
            assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
            assert context.context_id is None

        assert contexts[0].abstract_syntax == '1.2.840.10008.5.1.1.40'
