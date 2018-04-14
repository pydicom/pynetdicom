"""Tests for the pyndx.presentation module."""

import pytest

from pydicom._uid_dict import UID_dictionary
from pydicom.uid import UID

from pynetdicom3 import StorageSOPClassList
from pynetdicom3.presentation import PresentationContext, PresentationService


@pytest.fixture(params=[
    (1, None, []),
    (1, '1.1.1', ['1.2.840.10008.1.2']),
    (1, '1.1.1', ['1.2.840.10008.1.2', '1.2.840.10008.1.2.1']),
    (1, '1.1.1', ['1.2.840.10008.1.2', '1.2.840.10008.1.2.1', '1.2.3']),
    (1, None, ['1.2.840.10008.1.2']),
    (1, None, ['1.2.840.10008.1.2', '1.2.3']),
    (1, '1.1.1', []),
    (1, None, ['1.2.3']),
    (1, None, ['1.2.3', '1.2.840.10008.1.2']),
    (1, '1.2.840.10008.1.2.1.1.3', ['1.2.3']),
    (1, '1.2.840.10008.1.2.1.1.3', ['1.2.3', '1.2.840.10008.1.2'])
])
def good_init(request):
    """Good init values."""
    return request.param

@pytest.fixture(params=[
    (1, None, [], []),
    (1, '1.1.1', ['1.2.840.10008.1.1'], []),
    (1, '1.1.1', ['1.2.840.10008.1.1'], ['1.2.840.10008.1.2.1']),
    (1, '1.1.1', ['1.2.840.10008.1.1'], ['1.2.840.10008.1.2.1', '1.2.3']),
    (1, None, ['1.2.840.10008.1.1'], []),
    (1, None, ['1.2.840.10008.1.1'], ['1.2.3']),
    (1, '1.2.840.10008.1.2.1.1.3', ['1.2.840.10008.1.1'], ['1.2.3'])
])
def mixed_init(request):
    """Good init values with a mix of good and bad transfer syntaxes."""
    return request.param


class TestPresentationContext(object):
    """Test the PresentationContext class"""
    def test_good_init(self, good_init):
        """Test the presentation context class init"""
        (ID, abs_syn, tran_syn) = good_init
        pc = PresentationContext(ID, abs_syn, tran_syn)
        assert pc.ID == ID
        assert pc.AbstractSyntax == abs_syn
        assert pc.TransferSyntax == tran_syn
        assert pc.SCU is None
        assert pc.SCP is None
        assert pc.Result is None

    def test_mixed_init(self, mixed_init):
        """Test the presentation context class init with some bad transfer"""
        (ID, abs_syn, bad_tran, good_tran) = mixed_init
        bad_tran.extend(good_tran)
        pc = PresentationContext(ID, abs_syn, bad_tran)
        assert pc.ID == ID
        assert pc.AbstractSyntax == abs_syn
        assert pc.TransferSyntax == good_tran
        assert pc.SCU is None
        assert pc.SCP is None
        assert pc.Result is None

    def test_bad_init(self):
        """Test the presentation context class init"""
        with pytest.raises(ValueError):
            PresentationContext(0)
        with pytest.raises(ValueError):
            PresentationContext(256)
        with pytest.raises(TypeError):
            PresentationContext(1, transfer_syntaxes='1.1.1')
        with pytest.raises(ValueError):
            PresentationContext(1, transfer_syntaxes=[1234])
        with pytest.raises(TypeError):
            PresentationContext(1, abstract_syntax=['1.1.1.'])
        with pytest.raises(TypeError):
            PresentationContext(1, abstract_syntax=1234)

    def test_add_transfer_syntax(self):
        """Test adding transfer syntaxes"""
        pc = PresentationContext(1)
        pc.add_transfer_syntax('1.2.840.10008.1.2')
        pc.add_transfer_syntax(b'1.2.840.10008.1.2.1')
        pc.add_transfer_syntax(UID('1.2.840.10008.1.2.2'))
        pc.add_transfer_syntax(UID(''))

        with pytest.raises(TypeError):
            pc.add_transfer_syntax([])

        with pytest.raises(ValueError):
            pc.add_transfer_syntax('1.2.3.')

        with pytest.raises(ValueError):
            pc.add_transfer_syntax('1.2.840.10008.1.1')

    def test_add_private_transfer_syntax(self):
        """Test adding private transfer syntaxes"""
        pc = PresentationContext(1)
        pc.add_transfer_syntax('2.16.840.1.113709.1.2.2')
        assert '2.16.840.1.113709.1.2.2' in pc._transfer_syntax

        pc.TransferSyntax = ['2.16.840.1.113709.1.2.1']
        assert '2.16.840.1.113709.1.2.1' in pc._transfer_syntax

    def test_equality(self):
        """Test presentation context equality"""
        pc_a = PresentationContext(1, '1.1.1', ['1.2.840.10008.1.2'])
        pc_b = PresentationContext(1, '1.1.1', ['1.2.840.10008.1.2'])
        assert pc_a == pc_a
        assert pc_a == pc_b
        assert not pc_a != pc_b
        assert not pc_a != pc_a
        pc_a.SCP = True
        assert not pc_a == pc_b
        pc_b.SCP = True
        assert pc_a == pc_b
        pc_a.SCU = True
        assert not pc_a == pc_b
        pc_b.SCU = True
        assert pc_a == pc_b
        assert not 'a' == pc_b

    def test_string_output(self):
        """Test string output"""
        pc = PresentationContext(1, '1.1.1', ['1.2.840.10008.1.2'])
        pc.SCP = True
        pc.SCU = False
        pc.Result = 0x0002
        assert '1.1.1' in pc.__str__()
        assert 'Implicit' in pc.__str__()
        assert 'Provider Rejected' in pc.__str__()

    def test_abstract_syntax(self):
        """Test abstract syntax setter"""
        pc = PresentationContext(1)
        pc.AbstractSyntax = '1.1.1'
        assert pc.AbstractSyntax == UID('1.1.1')
        assert isinstance(pc.AbstractSyntax, UID)
        pc.AbstractSyntax = b'1.2.1'
        assert pc.AbstractSyntax == UID('1.2.1')
        assert isinstance(pc.AbstractSyntax, UID)
        pc.AbstractSyntax = UID('1.3.1')
        assert pc.AbstractSyntax == UID('1.3.1')
        assert isinstance(pc.AbstractSyntax, UID)

        pc.AbstractSyntax = UID('1.4.1.')
        assert pc.AbstractSyntax == UID('1.3.1')
        assert isinstance(pc.AbstractSyntax, UID)

    def test_transfer_syntax(self):
        """Test transfer syntax setter"""
        pc = PresentationContext(1)
        pc.TransferSyntax = ['1.2.840.10008.1.2']

        assert pc.TransferSyntax[0] == UID('1.2.840.10008.1.2')
        assert isinstance(pc.TransferSyntax[0], UID)
        pc.TransferSyntax = [b'1.2.840.10008.1.2.1']
        assert pc.TransferSyntax[0] == UID('1.2.840.10008.1.2.1')
        assert isinstance(pc.TransferSyntax[0], UID)
        pc.TransferSyntax = [UID('1.2.840.10008.1.2.2')]
        assert pc.TransferSyntax[0] == UID('1.2.840.10008.1.2.2')
        assert isinstance(pc.TransferSyntax[0], UID)

        with pytest.raises(TypeError):
            pc.TransferSyntax = UID('1.4.1')

        pc.TransferSyntax = ['1.4.1.', '1.2.840.10008.1.2']
        assert pc.TransferSyntax[0] == UID('1.2.840.10008.1.2')

    def test_status(self):
        """Test presentation context status"""
        pc = PresentationContext(1)
        statuses = [None, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05]
        results = ['Pending', 'Accepted', 'User Rejected', 'Provider Rejected',
                   'Abstract Syntax Not Supported',
                   'Transfer Syntax(es) Not Supported', 'Unknown']

        for status, result in zip(statuses, results):
            pc.Result = status
            assert pc.status == result


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
        context = PresentationContext(1,
                                      '1.2.840.10008.5.1.4.1.1.2',
                                      ['1.2.840.10008.1.2'])
        result = self.test_func([context], [])

        assert len(result) == 1
        context = result[0]
        assert context.ID == 1
        assert context.AbstractSyntax == '1.2.840.10008.5.1.4.1.1.2'
        assert context.TransferSyntax[0] == '1.2.840.10008.1.2'
        assert len(context.TransferSyntax) == 1
        assert context.Result == 0x03

    def test_no_req_one_acc(self):
        """Test negotiation with no requestor, one acceptor contexts."""
        context = PresentationContext(1,
                                      '1.2.840.10008.5.1.4.1.1.2',
                                      ['1.2.840.10008.1.2'])
        result = self.test_func([], [context])
        assert result == []

    def test_dupe_abs_req_no_acc(self):
        """Test negotiation with duplicate requestor, no acceptor contexts."""
        context_a = PresentationContext(1,
                                      '1.2.840.10008.5.1.4.1.1.2',
                                      ['1.2.840.10008.1.2'])
        context_b = PresentationContext(3,
                                      '1.2.840.10008.5.1.4.1.1.2',
                                      ['1.2.840.10008.1.2.1'])
        context_c = PresentationContext(5,
                                      '1.2.840.10008.5.1.4.1.1.2',
                                      ['1.2.840.10008.1.2.2'])
        context_list = [context_a, context_b, context_c]
        result = self.test_func(context_list, [])
        assert len(result) == 3
        for context in result:
            assert context.ID in [1, 3, 5]
            assert context.AbstractSyntax == '1.2.840.10008.5.1.4.1.1.2'
            assert context.Result == 0x03

    def test_dupe_abs_req(self):
        """Test negotiation with duplicate requestor, no acceptor contexts."""
        context_a = PresentationContext(1,
                                      '1.2.840.10008.5.1.4.1.1.2',
                                      ['1.2.840.10008.1.2'])
        context_b = PresentationContext(3,
                                      '1.2.840.10008.5.1.4.1.1.2',
                                      ['1.2.840.10008.1.2.1'])
        context_c = PresentationContext(5,
                                      '1.2.840.10008.5.1.4.1.1.2',
                                      ['1.2.840.10008.1.2.2'])
        t_syntax = ['1.2.840.10008.1.2',
                    '1.2.840.10008.1.2.1',
                    '1.2.840.10008.1.2.2']
        context_d = PresentationContext(None,
                                        '1.2.840.10008.5.1.4.1.1.2',
                                        t_syntax)
        context_list = [context_a, context_b, context_c]
        result = self.test_func(context_list, [context_d])
        assert len(result) == 3
        for ii, context in enumerate(result):
            assert context.ID in [1, 3, 5]
            assert context.AbstractSyntax == '1.2.840.10008.5.1.4.1.1.2'
            assert context.Result == 0x00
            assert context.TransferSyntax == [t_syntax[ii]]

    def test_one_req_one_acc_match(self):
        """Test negotiation one req/acc, matching accepted."""
        context = PresentationContext(1,
                                      '1.2.840.10008.5.1.4.1.1.2',
                                      ['1.2.840.10008.1.2'])
        result = self.test_func([context], [context])
        assert len(result) == 1
        context = result[0]
        assert context.ID == 1
        assert context.AbstractSyntax == '1.2.840.10008.5.1.4.1.1.2'
        assert context.Result == 0x00
        assert context.TransferSyntax == ['1.2.840.10008.1.2']

    def test_one_req_one_acc_accept_trans(self):
        """Test negotiation one req/acc, matching accepted, multi trans."""
        context = PresentationContext(1,
                                      '1.2.840.10008.5.1.4.1.1.2',
                                      ['1.2.840.10008.1.2',
                                       '1.2.840.10008.1.2.1',
                                       '1.2.840.10008.1.2.2'])
        result = self.test_func([context], [context])
        assert len(result) == 1
        context = result[0]
        assert context.ID == 1
        assert context.AbstractSyntax == '1.2.840.10008.5.1.4.1.1.2'
        assert context.Result == 0x00
        assert context.TransferSyntax == ['1.2.840.10008.1.2']

    def test_one_req_one_acc_accept_trans_diff(self):
        """Test negotiation one req/acc, matching accepted, multi trans."""
        context_a = PresentationContext(1,
                                        '1.2.840.10008.5.1.4.1.1.2',
                                        ['1.2.840.10008.1.2',
                                         '1.2.840.10008.1.2.1',
                                         '1.2.840.10008.1.2.2'])
        context_b = PresentationContext(None,
                                        '1.2.840.10008.5.1.4.1.1.2',
                                        ['1.2.840.10008.1.2.2'])
        result = self.test_func([context_a], [context_b])
        assert len(result) == 1
        context = result[0]
        assert context.ID == 1
        assert context.AbstractSyntax == '1.2.840.10008.5.1.4.1.1.2'
        assert context.Result == 0x00
        assert context.TransferSyntax == ['1.2.840.10008.1.2.2']

    def test_one_req_one_acc_reject_trans(self):
        """Test negotiation one req/acc, matching rejected trans"""
        context_a = PresentationContext(1,
                                        '1.2.840.10008.5.1.4.1.1.2',
                                        ['1.2.840.10008.1.2',
                                         '1.2.840.10008.1.2.1'])
        context_b = PresentationContext(None,
                                        '1.2.840.10008.5.1.4.1.1.2',
                                        ['1.2.840.10008.1.2.2'])
        result = self.test_func([context_a], [context_b])
        assert len(result) == 1
        context = result[0]
        assert context.ID == 1
        assert context.AbstractSyntax == '1.2.840.10008.5.1.4.1.1.2'
        assert context.Result == 0x04

    def test_one_req_one_acc_mismatch(self):
        """Test negotiation one req/acc, mismatched rejected"""
        context_a = PresentationContext(1,
                                        '1.2.840.10008.5.1.4.1.1.2',
                                        ['1.2.840.10008.1.2',
                                         '1.2.840.10008.1.2.1'])
        context_b = PresentationContext(None,
                                        '1.2.840.10008.5.1.4.1.1.4',
                                        ['1.2.840.10008.1.2.1'])
        result = self.test_func([context_a], [context_b])
        assert len(result) == 1
        context = result[0]
        assert context.ID == 1
        assert context.AbstractSyntax == '1.2.840.10008.5.1.4.1.1.2'
        assert context.Result == 0x03

    def test_private_transfer_syntax(self):
        """Test negotiation with private transfer syntax"""
        context_a = PresentationContext(1,
                                        '1.2.840.10008.5.1.4.1.1.2',
                                        ['1.2.3.4'])
        context_b = PresentationContext(None,
                                        '1.2.840.10008.5.1.4.1.1.2',
                                        ['1.2.840.10008.1.2.1',
                                         '1.2.3.4'])
        result = self.test_func([context_a], [context_b])
        assert len(result) == 1
        context = result[0]
        assert context.ID == 1
        assert context.AbstractSyntax == '1.2.840.10008.5.1.4.1.1.2'
        assert context.Result == 0x00
        assert context.TransferSyntax == ['1.2.3.4']

    def test_private_abstract_syntax(self):
        """Test negotiation with private abstract syntax"""
        context_a = PresentationContext(1,
                                        '1.2.3.4',
                                        ['1.2.840.10008.1.2.1'])
        context_b = PresentationContext(None,
                                        '1.2.3.4',
                                        ['1.2.840.10008.1.2.1'])
        result = self.test_func([context_a], [context_b])
        assert len(result) == 1
        context = result[0]
        assert context.ID == 1
        assert context.AbstractSyntax == '1.2.3.4'
        assert context.Result == 0x00
        assert context.TransferSyntax == ['1.2.840.10008.1.2.1']

    def test_typical(self):
        """Test a typical set of presentation context negotiations."""
        req_contexts = []
        for ii, sop in enumerate(StorageSOPClassList):
            req_contexts.append(
                PresentationContext(ii * 2 + 1,
                                    sop.UID,
                                    ['1.2.840.10008.1.2',
                                     '1.2.840.10008.1.2.1',
                                     '1.2.840.10008.1.2.2'])
            )

        acc_contexts = []
        for uid in UID_dictionary:
            acc_contexts.append(
                PresentationContext(1,
                                    uid,
                                    ['1.2.840.10008.1.2',
                                     '1.2.840.10008.1.2.1',
                                     '1.2.840.10008.1.2.2'])
            )

        results = self.test_func(req_contexts, acc_contexts)
        assert len(results) == len(req_contexts)
        for ii, context in enumerate(req_contexts):
            assert results[ii].ID == context.ID
            assert results[ii].AbstractSyntax == context.AbstractSyntax
            if results[ii].AbstractSyntax == '1.2.840.10008.5.1.4.1.1.1.1.1.1':
                assert results[ii].Result == 0x03
            elif results[ii].AbstractSyntax == '1.2.840.10008.5.1.1.4.1.1.3.1':
                assert results[ii].Result == 0x03
            else:
                assert results[ii].Result == 0x00
                assert results[ii].TransferSyntax == ['1.2.840.10008.1.2']


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

        assert result[0].AbstractSyntax == '1.2.3.4'
        assert result[0].TransferSyntax[0] == '1.2.840.10008.1.2'
        assert result[0].SCP == out[0]
        assert result[0].SCU == out[1]
        assert result[0].Result == 0x00


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
        context = PresentationContext(1,
                                      '1.2.840.10008.5.1.4.1.1.2',
                                      ['1.2.840.10008.1.2'])
        result = self.test_func([context], [])

        assert len(result) == 1
        context = result[0]
        assert context.ID == 1
        assert context.AbstractSyntax == '1.2.840.10008.5.1.4.1.1.2'
        assert context.TransferSyntax[0] == '1.2.840.10008.1.2'
        assert len(context.TransferSyntax) == 1
        assert context.Result == 0x02

    def test_no_req_one_acc_raise(self):
        """Test negotiation with no requestor, one acceptor contexts."""
        context = PresentationContext(1,
                                      '1.2.840.10008.5.1.4.1.1.2',
                                      ['1.2.840.10008.1.2'])
        with pytest.raises(ValueError):
            result = self.test_func([], [context])

    def test_dupe_abs_req_no_acc(self):
        """Test negotiation with duplicate requestor, no acceptor contexts."""
        context_a = PresentationContext(1,
                                      '1.2.840.10008.5.1.4.1.1.2',
                                      ['1.2.840.10008.1.2'])
        context_b = PresentationContext(3,
                                      '1.2.840.10008.5.1.4.1.1.2',
                                      ['1.2.840.10008.1.2.1'])
        context_c = PresentationContext(5,
                                      '1.2.840.10008.5.1.4.1.1.2',
                                      ['1.2.840.10008.1.2.2'])
        rq_contexts = [context_a, context_b, context_c]
        acc_contexts = self.test_acc(rq_contexts, [])

        for context in acc_contexts:
            context.AbstractSyntax = None

        result = self.test_func(rq_contexts, acc_contexts)

        assert len(result) == 3
        for context in result:
            assert context.ID in [1, 3, 5]
            assert context.AbstractSyntax == '1.2.840.10008.5.1.4.1.1.2'
            assert context.Result == 0x03

    def test_dupe_abs_req(self):
        """Test negotiation with duplicate requestor, no acceptor contexts."""
        context_a = PresentationContext(1,
                                      '1.2.840.10008.5.1.4.1.1.2',
                                      ['1.2.840.10008.1.2'])
        context_b = PresentationContext(3,
                                      '1.2.840.10008.5.1.4.1.1.2',
                                      ['1.2.840.10008.1.2.1'])
        context_c = PresentationContext(5,
                                      '1.2.840.10008.5.1.4.1.1.2',
                                      ['1.2.840.10008.1.2.2'])
        t_syntax = ['1.2.840.10008.1.2',
                    '1.2.840.10008.1.2.1',
                    '1.2.840.10008.1.2.2']
        context_d = PresentationContext(None,
                                        '1.2.840.10008.5.1.4.1.1.2',
                                        t_syntax)

        rq_contexts = [context_a, context_b, context_c]
        acc_contexts = self.test_acc(rq_contexts, [context_d])

        for context in acc_contexts:
            context.AbstractSyntax = None

        result = self.test_func(rq_contexts, acc_contexts)

        assert len(result) == 3
        for ii, context in enumerate(result):
            assert context.ID in [1, 3, 5]
            assert context.AbstractSyntax == '1.2.840.10008.5.1.4.1.1.2'
            assert context.Result == 0x00
            assert context.TransferSyntax == [t_syntax[ii]]

    def test_one_req_one_acc_match(self):
        """Test negotiation one req/acc, matching accepted."""
        context = PresentationContext(1,
                                      '1.2.840.10008.5.1.4.1.1.2',
                                      ['1.2.840.10008.1.2'])
        rq_contexts = [context]
        acc_contexts = self.test_acc([context], [context])

        for context in acc_contexts:
            context.AbstractSyntax = None

        result = self.test_func(rq_contexts, acc_contexts)

        assert len(result) == 1
        context = result[0]
        assert context.ID == 1
        assert context.AbstractSyntax == '1.2.840.10008.5.1.4.1.1.2'
        assert context.Result == 0x00
        assert context.TransferSyntax == ['1.2.840.10008.1.2']

    def test_one_req_one_acc_accept_trans(self):
        """Test negotiation one req/acc, matching accepted, multi trans."""
        context = PresentationContext(1,
                                      '1.2.840.10008.5.1.4.1.1.2',
                                      ['1.2.840.10008.1.2',
                                       '1.2.840.10008.1.2.1',
                                       '1.2.840.10008.1.2.2'])
        rq_contexts = [context]
        acc_contexts = self.test_acc([context], [context])

        for context in acc_contexts:
            context.AbstractSyntax = None

        result = self.test_func(rq_contexts, acc_contexts)
        assert len(result) == 1
        context = result[0]
        assert context.ID == 1
        assert context.AbstractSyntax == '1.2.840.10008.5.1.4.1.1.2'
        assert context.Result == 0x00
        assert context.TransferSyntax == ['1.2.840.10008.1.2']

    def test_one_req_one_acc_accept_trans_diff(self):
        """Test negotiation one req/acc, matching accepted, multi trans."""
        context_a = PresentationContext(1,
                                        '1.2.840.10008.5.1.4.1.1.2',
                                        ['1.2.840.10008.1.2',
                                         '1.2.840.10008.1.2.1',
                                         '1.2.840.10008.1.2.2'])
        context_b = PresentationContext(None,
                                        '1.2.840.10008.5.1.4.1.1.2',
                                        ['1.2.840.10008.1.2.2'])
        rq_contexts = [context_a]
        acc_contexts = self.test_acc(rq_contexts, [context_b])

        for context in acc_contexts:
            context.AbstractSyntax = None

        result = self.test_func(rq_contexts, acc_contexts)

        assert len(result) == 1
        context = result[0]
        assert context.ID == 1
        assert context.AbstractSyntax == '1.2.840.10008.5.1.4.1.1.2'
        assert context.Result == 0x00
        assert context.TransferSyntax == ['1.2.840.10008.1.2.2']

    def test_one_req_one_acc_reject_trans(self):
        """Test negotiation one req/acc, matching rejected trans"""
        context_a = PresentationContext(1,
                                        '1.2.840.10008.5.1.4.1.1.2',
                                        ['1.2.840.10008.1.2',
                                         '1.2.840.10008.1.2.1'])
        context_b = PresentationContext(None,
                                        '1.2.840.10008.5.1.4.1.1.2',
                                        ['1.2.840.10008.1.2.2'])
        rq_contexts = [context_a]
        acc_contexts = self.test_acc(rq_contexts, [context_b])

        for context in acc_contexts:
            context.AbstractSyntax = None

        result = self.test_func(rq_contexts, acc_contexts)

        assert len(result) == 1
        context = result[0]
        assert context.ID == 1
        assert context.AbstractSyntax == '1.2.840.10008.5.1.4.1.1.2'
        assert context.Result == 0x04

    def test_one_req_one_acc_mismatch(self):
        """Test negotiation one req/acc, mismatched rejected"""
        context_a = PresentationContext(1,
                                        '1.2.840.10008.5.1.4.1.1.2',
                                        ['1.2.840.10008.1.2',
                                         '1.2.840.10008.1.2.1'])
        context_b = PresentationContext(None,
                                        '1.2.840.10008.5.1.4.1.1.4',
                                        ['1.2.840.10008.1.2.1'])
        rq_contexts = [context_a]
        acc_contexts = self.test_acc(rq_contexts, [context_b])

        for context in acc_contexts:
            context.AbstractSyntax = None

        result = self.test_func(rq_contexts, acc_contexts)

        assert len(result) == 1
        context = result[0]
        assert context.ID == 1
        assert context.AbstractSyntax == '1.2.840.10008.5.1.4.1.1.2'
        assert context.Result == 0x03

    def test_private_transfer_syntax(self):
        """Test negotiation with private transfer syntax"""
        context_a = PresentationContext(1,
                                        '1.2.840.10008.5.1.4.1.1.2',
                                        ['1.2.3.4'])
        context_b = PresentationContext(None,
                                        '1.2.840.10008.5.1.4.1.1.2',
                                        ['1.2.840.10008.1.2.1',
                                         '1.2.3.4'])
        rq_contexts = [context_a]
        acc_contexts = self.test_acc(rq_contexts, [context_b])

        for context in acc_contexts:
            context.AbstractSyntax = None

        result = self.test_func(rq_contexts, acc_contexts)

        assert len(result) == 1
        context = result[0]
        assert context.ID == 1
        assert context.AbstractSyntax == '1.2.840.10008.5.1.4.1.1.2'
        assert context.Result == 0x00
        assert context.TransferSyntax == ['1.2.3.4']

    def test_private_abstract_syntax(self):
        """Test negotiation with private abstract syntax"""
        context_a = PresentationContext(1,
                                        '1.2.3.4',
                                        ['1.2.840.10008.1.2.1'])
        context_b = PresentationContext(None,
                                        '1.2.3.4',
                                        ['1.2.840.10008.1.2.1'])
        rq_contexts = [context_a]
        acc_contexts = self.test_acc(rq_contexts, [context_b])

        for context in acc_contexts:
            context.AbstractSyntax = None

        result = self.test_func(rq_contexts, acc_contexts)

        assert len(result) == 1
        context = result[0]
        assert context.ID == 1
        assert context.AbstractSyntax == '1.2.3.4'
        assert context.Result == 0x00
        assert context.TransferSyntax == ['1.2.840.10008.1.2.1']

    def test_typical(self):
        """Test a typical set of presentation context negotiations."""
        req_contexts = []
        for ii, sop in enumerate(StorageSOPClassList):
            req_contexts.append(
                PresentationContext(ii * 2 + 1,
                                    sop.UID,
                                    ['1.2.840.10008.1.2',
                                     '1.2.840.10008.1.2.1',
                                     '1.2.840.10008.1.2.2'])
            )

        acc_contexts = []
        for uid in UID_dictionary:
            acc_contexts.append(
                PresentationContext(1,
                                    uid,
                                    ['1.2.840.10008.1.2',
                                     '1.2.840.10008.1.2.1',
                                     '1.2.840.10008.1.2.2'])
            )

        acc_contexts = self.test_acc(req_contexts, acc_contexts)

        for context in acc_contexts:
            context.AbstractSyntax = None

        results = self.test_func(req_contexts, acc_contexts)

        assert len(results) == len(req_contexts)
        for ii, context in enumerate(req_contexts):
            assert results[ii].ID == context.ID
            assert results[ii].AbstractSyntax == context.AbstractSyntax
            if results[ii].AbstractSyntax == '1.2.840.10008.5.1.4.1.1.1.1.1.1':
                assert results[ii].Result == 0x03
            elif results[ii].AbstractSyntax == '1.2.840.10008.5.1.1.4.1.1.3.1':
                assert results[ii].Result == 0x03
            else:
                assert results[ii].Result == 0x00
                assert results[ii].TransferSyntax == ['1.2.840.10008.1.2']
