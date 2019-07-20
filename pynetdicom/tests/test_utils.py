"""Unit tests for the utility functions.

validate_ae_title
pretty_bytes
"""

from io import BytesIO
import logging

import pytest

from pydicom.uid import UID
from pydicom.tag import Tag

from pynetdicom import _config
from pynetdicom.utils import (
    validate_ae_title, pretty_bytes, validate_uid, as_dataset, ElementPath
)
from .encoded_pdu_items import a_associate_rq

LOGGER = logging.getLogger('pynetdicom')
LOGGER.setLevel(logging.CRITICAL)


REFERENCE_GOOD_AE_STR = [
    ('a',                b'a               '),
    ('a              b', b'a              b'),
    ('a    b',           b'a    b          '),
    ('               b', b'b               '),
    ('        ab  c   ', b'ab  c           '),
    ('        ab  c      ', b'ab  c           '),
    ('ABCDEFGHIJKLMNOPQRSTUVWXYZ', b'ABCDEFGHIJKLMNOP')
]
REFERENCE_GOOD_AE_BYTES = [
    (b'a',                b'a               '),
    (b'a              b', b'a              b'),
    (b'a    b',           b'a    b          '),
    (b'               b', b'b               '),
    (b'        ab  c   ', b'ab  c           '),
    (b'        ab  c      ', b'ab  c           '),
    (b'ABCDEFGHIJKLMNOPQRSTUVWXYZ', b'ABCDEFGHIJKLMNOP')
]
REFERENCE_BAD_AE_STR = [
    '                ',  # empty, 16 chars 0x20
    '',  # empty
    'AE\\TITLE',  # backslash
    'AE\tTITLE',  # control char, tab
    'AE\rTITLE',  # control char, carriage return
    'AE\nTITLE',  # control char, new line
    u'\u0009'.encode('ascii'),  # \t
    u'\u000A'.encode('ascii'),  # \n
    u'\u000C'.encode('ascii'),  # \x0c
    u'\u000D'.encode('ascii'),  # \x0d
    u'\u001B'.encode('ascii'),  # \x1b
    u'\u005C'.encode('ascii'),  # \\
    u'\u0001'.encode('ascii'),  # \x01
    u'\u000e'.encode('ascii'),  # \x0e
    1234,
    45.1,
]
REFERENCE_BAD_AE_BYTES = [
    b'                ',  # empty, 16 chars 0x20
    b'',  # empty
    b'AE\\TITLE',  # backslash
    b'AE\tTITLE',  # control char, tab
    b'AE\rTITLE',  # control char, carriage return
    b'AE\nTITLE',  # control char, new line
    u'\u0009'.encode('ascii'),  # \t
    u'\u000A'.encode('ascii'),  # \n
    u'\u000C'.encode('ascii'),  # \x0c
    u'\u000D'.encode('ascii'),  # \x0d
    u'\u001B'.encode('ascii'),  # \x1b
    u'\u005C'.encode('ascii'),  # \\
    u'\u0001'.encode('ascii'),  # \x01
    u'\u000e'.encode('ascii'),  # \x0e
    1234,
    45.1,
]


class TestValidateAETitle(object):
    """Test validate_ae_title"""
    @pytest.mark.parametrize("aet, output", REFERENCE_GOOD_AE_STR)
    def test_good_ae_str(self, aet, output):
        """Test validate_ae_title using str input."""
        assert validate_ae_title(aet) == output
        assert isinstance(validate_ae_title(aet), bytes)

    @pytest.mark.parametrize("aet, output", REFERENCE_GOOD_AE_BYTES)
    def test_good_ae_bytes(self, aet, output):
        """Test validate_ae_title using bytes input."""
        assert validate_ae_title(aet) == output
        assert isinstance(validate_ae_title(aet), bytes)

    @pytest.mark.parametrize("aet", REFERENCE_BAD_AE_STR)
    def test_bad_ae_str(self, aet):
        """Test validate_ae_title using bad str input."""
        with pytest.raises((TypeError, ValueError)):
            validate_ae_title(aet)

    @pytest.mark.parametrize("aet", REFERENCE_BAD_AE_BYTES)
    def test_bad_ae_bytes(self, aet):
        """Test validate_ae_title using bad bytes input."""
        with pytest.raises((TypeError, ValueError)):
            validate_ae_title(aet)


REFERENCE_UID = [
    # UID, (enforced, non-enforced conformance)
    # Invalid, invalid
    ('', (False, False)),
    (' ' * 64, (False, False)),
    ('1' * 65, (False, False)),
    ('a' * 65, (False, False)),
    # Invalid, valid
    ('a' * 64, (False, True)),
    ('0.1.2.04', (False, True)),
    ('some random string', (False, True)),
    # Valid, valid
    ('1' * 64, (True, True)),
    ('0.1.2.4', (True, True)),
]


class TestValidateUID(object):
    """Test validate_uid."""
    def setup(self):
        self.default_conformance = _config.ENFORCE_UID_CONFORMANCE

    def teardown(self):
        _config.ENFORCE_UID_CONFORMANCE = self.default_conformance

    @pytest.mark.parametrize("uid,is_valid", REFERENCE_UID)
    def test_validate_uid_conformance_true(self, uid, is_valid):
        _config.ENFORCE_UID_CONFORMANCE = True
        assert validate_uid(UID(uid)) == is_valid[0]

    @pytest.mark.parametrize("uid,is_valid", REFERENCE_UID)
    def test_validate_uid_conformance_false(self, uid, is_valid):
        _config.ENFORCE_UID_CONFORMANCE = False
        assert validate_uid(UID(uid)) == is_valid[1]


class TestWrapList(object):
    """Test pretty_bytes() function"""
    def test_parameters(self):
        """Test parameters are correct."""
        # Default
        bytestream = a_associate_rq
        result = pretty_bytes(bytestream)
        assert len(result) == 14
        assert isinstance(result[0], str)

        # prefix
        result = pretty_bytes(bytestream, prefix='\\x')
        for line in result:
            assert line[:2] == '\\x'

        # delimiter
        result = pretty_bytes(bytestream, prefix='', delimiter=',')
        for line in result:
            assert line[2] == ','

        # items_per_line
        result = pretty_bytes(bytestream, prefix='', delimiter='',
                           items_per_line=10)
        assert len(result[0]) == 20

        # max_size
        result = pretty_bytes(bytestream, prefix='', delimiter='',
                           items_per_line=10, max_size=100)
        assert len(result) == 11  # 10 plus the cutoff line
        result = pretty_bytes(bytestream, max_size=None)

        # suffix
        result = pretty_bytes(bytestream, suffix='xxx')
        for line in result:
            assert line[-3:] == 'xxx'

    def test_bytesio(self):
        """Test wrap list using bytesio"""
        bytestream = BytesIO()
        bytestream.write(a_associate_rq)
        result = pretty_bytes(bytestream, prefix='', delimiter='',
                           items_per_line=10)
        assert isinstance(result[0], str)


REFERENCE_ELEM_STR_SINGLE = [
    # DICOM elements
    ("(0000,0000)=", 'CommandGroupLength'),
    ("CommandGroupLength=", 'CommandGroupLength'),
    ("(fffe,e0dd)=", 'SequenceDelimitationItem'),
    ("(FFFe,E0dD)=", 'SequenceDelimitationItem'),
    ("(FFFE,E0DD)=", 'SequenceDelimitationItem'),
    ('SequenceDelimitationItem=', 'SequenceDelimitationItem'),
    # DICOM repeater elements
    ("(0020,3100)=", 'SourceImageIDs'),
    ("(7fff,0040)=", 'VariableCoefficientsSDDN'),
    # Private elements
    ("(0001,0001)=",),
    ("UnknownPrivateElement=",),
]

REFERENCE_ELEM_STR_SEQ_BAD = [
    (["BeamName[0]="], ),  # Not a sequence element
    (["(300a,00b0)[1]="], ),
    (["(300a,00b0)[1]=", "(300a,00b0)[0]="], ),
    (["BeamSequence[1]="], ),
    (["BeamSequence[1]=", "BeamSequence[0]="], ),
    (["(300a,00b0)[1].BeamName="], ),
    (["(300a,00b0)[1].BeamName=", "(300a,00b0)[0].BeamName="], ),
    (["BeamSequence[1].BeamName="], ),
    (["BeamSequence[1].BeamName=", "BeamSequence[0].BeamName="], ),
    (["(300a,00b0)[0].(300a,00b0)[1]="], ),
    (["(300a,00b0)[0].BeamSequence[1]="], ),
    (["BeamSequence[0].(300a,00b0)[1]="], ),
    (["BeamSequence[0].BeamSequence[1]="], ),
    (["(300a,00b0)[0].(300a,00b0)[1].BeamName="], ),
    (["(300a,00b0)[0].BeamSequence[1].BeamName="], ),
    (["BeamSequence[0].(300a,00b0)[1].BeamName="], ),
    (["BeamSequence[0].BeamSequence[1].BeamName="], ),
]

REFERENCE_ELEM_STR_SEQ = [
    # Sequence with empty items
    (["(300a,00b0)[0]="], ),
    (["(300a,00b0)[0]=", "(300a,00b0)[1]="], ),
    (["BeamSequence[0]="], ),
    (["BeamSequence[0]=", "BeamSequence[1]="], ),
    # Sequence with keyword items
    (["(300a,00b0)[0].BeamName="], ),
    (["(300a,00b0)[0].BeamName=", "(300a,00b0)[0].BeamNumber="], ),
    (["(300a,00b0)[0].BeamName=", "(300a,00b0)[0].(300a,00c0)="], ),
    (["(300a,00b0)[0].BeamName=", "(300a,00b0)[1].BeamName="], ),
    (["BeamSequence[0].BeamName="], ),
    (["BeamSequence[0].BeamName=", "BeamSequence[1].BeamName="], ),
    # Sequence with tag items
    (["(300a,00b0)[0].(300a,00c2)="], ),
    (["(300a,00b0)[0].(300a,00c2)=", "(300a,00b0)[0].BeamNumber="], ),
    (["(300a,00b0)[0].(300a,00c2)=", "(300a,00b0)[0].(300a,00c0)="], ),
    (["(300a,00b0)[0].(300a,00c2)=", "(300a,00b0)[1].(300a,00c2)="], ),
    (["BeamSequence[0].(300a,00c2)="], ),
    (["BeamSequence[0].(300a,00c2)=", "BeamSequence[1].(300a,00c2)="], ),
    # Nested sequences
    (["(300a,00b0)[0].(300a,00b0)[0].(300a,00c2)="], ),
    (["(300a,00b0)[0].(300a,00b0)[0].(300a,00b0)[0].(300a,00c2)="], ),
    (["(300a,00b0)[0].(300a,00b0)[0].(300a,00c2)=", "(300a,00b0)[1].(300a,00b0)[0].(300a,00c2)="], ),
    (["(300a,00b0)[0].(300a,00b0)[0].(300a,00b0)[0].(300a,00c2)=", "(300a,00b0)[1].(300a,00b0)[0].(300a,00b0)[0].(300a,00c2)="], ),
    (["BeamSequence[0].(300a,00b0)[0].(300a,00c2)="], ),
    (["BeamSequence[0].(300a,00b0)[0].(300a,00b0)[0].(300a,00c2)="], ),
    (["BeamSequence[0].(300a,00b0)[0].(300a,00c2)=", "BeamSequence[1].(300a,00b0)[0].(300a,00c2)="], ),
    (["BeamSequence[0].(300a,00b0)[0].(300a,00b0)[0].(300a,00c2)=", "BeamSequence[1].(300a,00b0)[0].(300a,00b0)[0].(300a,00c2)="], ),
]


class TestElementPath(object):
    """Tests for utils.ElementPath."""
    def test_non_sequence(self):
        """Test ElementPath using a non-sequence component."""
        elem = ElementPath('(0000,0000)')
        assert elem.tag == Tag(0x0000,0x0000)
        assert elem.keyword == 'CommandGroupLength'
        assert elem.VR == 'UL'
        assert elem.VM == '1'
        assert elem.item_nr is None
        assert elem.is_sequence is False
        assert elem.child is None
        assert elem.parent is None
        assert elem.value is None

        elem = ElementPath('0000,0000')
        assert elem.tag == Tag(0x0000,0x0000)
        assert elem.keyword == 'CommandGroupLength'
        assert elem.VR == 'UL'
        assert elem.VM == '1'
        assert elem.item_nr is None
        assert elem.is_sequence is False
        assert elem.child is None
        assert elem.parent is None
        assert elem.value is None

        elem = ElementPath('CommandGroupLength')
        assert elem.tag == Tag(0x0000,0x0000)
        assert elem.keyword == 'CommandGroupLength'
        assert elem.VR == 'UL'
        assert elem.VM == '1'
        assert elem.item_nr is None
        assert elem.is_sequence is False
        assert elem.child is None
        assert elem.parent is None
        assert elem.value is None

    def test_pathing(self):
        """Test ElementPath using normal pathing."""
        paths = [
            "(0000,0000)=", "0000,0000=", "CommandGroupLength="
        ]
        for path in paths:
            elem = ElementPath(path)
            assert elem.tag == Tag(0x0000,0x0000)
            assert elem.keyword == 'CommandGroupLength'
            assert elem.VR == 'UL'
            assert elem.VM == '1'
            assert elem.item_nr is None
            assert elem.is_sequence is False
            assert elem.child is None
            assert elem.parent is None
            assert elem.value == ''

        paths = [
            "(0000,0000)=Test", "0000,0000=Test", "CommandGroupLength=Test"
        ]
        for path in paths:
            elem = ElementPath(path)
            assert elem.tag == Tag(0x0000,0x0000)
            assert elem.keyword == 'CommandGroupLength'
            assert elem.VR == 'UL'
            assert elem.VM == '1'
            assert elem.item_nr is None
            assert elem.is_sequence is False
            assert elem.child is None
            assert elem.parent is None
            assert elem.value == 'Test'

        paths = [
            "(300a,00b0)[0]=", "300a,00b0[0]=", "BeamSequence[0]="
        ]
        for path in paths:
            elem = ElementPath(path)
            assert elem.tag == Tag(0x300a,0x00b0)
            assert elem.keyword == 'BeamSequence'
            assert elem.VR == 'SQ'
            assert elem.VM == '1'
            assert elem.item_nr == 0
            assert elem.is_sequence is True
            assert elem.child is None
            assert elem.parent is None
            assert elem.value == ''

        elem = ElementPath("BeamSequence[0].BeamName=")
        assert elem.tag == Tag(0x300a,0x00b0)
        assert elem.keyword == 'BeamSequence'
        assert elem.VR == 'SQ'
        assert elem.VM == '1'
        assert elem.item_nr == 0
        assert elem.is_sequence is True
        assert elem.parent is None
        assert elem.value == ''

        child = elem.child
        assert child.tag == Tag(0x300a,0x00c2)
        assert child.keyword == 'BeamName'
        assert child.VR == 'LO'
        assert child.VM == '1'
        assert child.item_nr is None
        assert child.is_sequence is False
        assert child.parent is elem
        assert child.value == ''

        elem = ElementPath("BeamSequence[0].BeamName=Test")
        assert elem.tag == Tag(0x300a,0x00b0)
        assert elem.keyword == 'BeamSequence'
        assert elem.VR == 'SQ'
        assert elem.VM == '1'
        assert elem.item_nr == 0
        assert elem.is_sequence is True
        assert elem.parent is None
        assert elem.value == 'Test'

        child = elem.child
        assert child.tag == Tag(0x300a,0x00c2)
        assert child.keyword == 'BeamName'
        assert child.VR == 'LO'
        assert child.VM == '1'
        assert child.item_nr is None
        assert child.is_sequence is False
        assert child.parent is elem
        assert child.value == 'Test'

        elem = ElementPath("BeamSequence[5].BeamSequence[13].BeamName=Test")
        assert elem.tag == Tag(0x300a,0x00b0)
        assert elem.keyword == 'BeamSequence'
        assert elem.VR == 'SQ'
        assert elem.VM == '1'
        assert elem.item_nr == 5
        assert elem.is_sequence is True
        assert elem.parent is None
        assert elem.value == 'Test'

        child = elem.child
        assert child.tag == Tag(0x300a,0x00b0)
        assert child.keyword == 'BeamSequence'
        assert child.VR == 'SQ'
        assert child.VM == '1'
        assert child.item_nr == 13
        assert child.is_sequence is True
        assert child.parent is elem
        assert child.value == 'Test'

        subchild = child.child
        assert subchild.tag == Tag(0x300a,0x00c2)
        assert subchild.keyword == 'BeamName'
        assert subchild.VR == 'LO'
        assert subchild.VM == '1'
        assert subchild.item_nr is None
        assert subchild.is_sequence is False
        assert subchild.parent is child
        assert subchild.value == 'Test'

    @pytest.mark.skip()
    def test_non_sequence_repeater(self):
        """Test ElementPath using a non-sequence component."""
        elem = ElementPath('(0000,0000)')
        assert elem.tag == Tag(0x0000,0x0000)
        assert elem.keyword == 'CommandGroupLength'
        assert elem.VR == 'UL'
        assert elem.VM == '1'
        assert elem.item_nr is None
        assert elem.is_sequence is False

        elem = ElementPath('0000,0000')
        assert elem.tag == Tag(0x0000,0x0000)
        assert elem.keyword == 'CommandGroupLength'
        assert elem.VR == 'UL'
        assert elem.VM == '1'
        assert elem.item_nr is None
        assert elem.is_sequence is False

        elem = ElementPath('CommandGroupLength')
        assert elem.tag == Tag(0x0000,0x0000)
        assert elem.keyword == 'CommandGroupLength'
        assert elem.VR == 'UL'
        assert elem.VM == '1'
        assert elem.item_nr is None
        assert elem.is_sequence is False

    def test_private(self):
        """Test using a known private non-sequence component."""
        # '1.2.840.113663.1': {'0029xx00': ('US', '1', 'Unknown', ''),
        elem = ElementPath('(0029,0100)')
        assert elem.tag == Tag(0x0029,0x0100)
        assert elem.keyword == 'Unknown'
        assert elem.VR == 'UN'
        assert elem.VM == '1'
        assert elem.item_nr is None
        assert elem.is_sequence is False

        elem = ElementPath('0029,0100')
        assert elem.tag == Tag(0x0029,0x0100)
        assert elem.keyword == 'Unknown'
        assert elem.VR == 'UN'
        assert elem.VM == '1'
        assert elem.item_nr is None
        assert elem.is_sequence is False

        with pytest.raises(ValueError, match=r''):
            ElementPath('UnknownPrivateElement')

    def test_sequence(self):
        """Test ElementPath using a sequence component."""
        elem = ElementPath('(300a,00b0)[13]')
        assert elem.tag == Tag(0x300a,0x00b0)
        assert elem.keyword == 'BeamSequence'
        assert elem.VR == 'SQ'
        assert elem.VM == '1'
        assert elem.item_nr == 13
        assert elem.is_sequence is True
        assert elem.child is None
        assert elem.parent is None
        assert elem.value is None

        elem = ElementPath('300a,00b0[13]')
        assert elem.tag == Tag(0x300a,0x00b0)
        assert elem.keyword == 'BeamSequence'
        assert elem.VR == 'SQ'
        assert elem.VM == '1'
        assert elem.item_nr == 13
        assert elem.is_sequence is True
        assert elem.child is None
        assert elem.parent is None
        assert elem.value is None

        elem = ElementPath('BeamSequence[13]')
        assert elem.tag == Tag(0x300a,0x00b0)
        assert elem.keyword == 'BeamSequence'
        assert elem.VR == 'SQ'
        assert elem.VM == '1'
        assert elem.item_nr == 13
        assert elem.is_sequence is True
        assert elem.child is None
        assert elem.parent is None
        assert elem.value is None

    def test_sequence_raises(self):
        """Test ElementPath using bad sequence component raises."""
        with pytest.raises(ValueError, match=r''):
            ElementPath('(300a,00b0)[')

        with pytest.raises(ValueError, match=r''):
            ElementPath('(300a,00b0)]')

        with pytest.raises(ValueError, match=r''):
            ElementPath('(300a,00b0)[]')

        with pytest.raises(ValueError, match=r''):
            ElementPath('300a,00b0[')

        with pytest.raises(ValueError, match=r''):
            ElementPath('300a,00b0]')

        with pytest.raises(ValueError, match=r''):
            ElementPath('300a,00b0[]')

        with pytest.raises(ValueError, match=r''):
            ElementPath('BeamSequence[')

        with pytest.raises(ValueError, match=r''):
            ElementPath('BeamSequence]')

        with pytest.raises(ValueError, match=r''):
            ElementPath('BeamSequence[]')


class TestAsDataset(object):
    """Test for utils.parse_elem_str()."""
    def test_tag_non_sequence(self):
        """Tests for parsing non-sequence strings."""
        paths = [
            'PatientName=Test^Name',
            'BeamSequence[0].BeamSequence[0].BeamNumber=1',
            'BeamSequence[0].BeamSequence[1].BeamNumber=2',
            'BeamSequence[0].BeamSequence[2].BeamNumber=3',
            'BeamSequence[1].BeamSequence[0].BeamNumber=1',
            'BeamSequence[1].BeamSequence[1].BeamNumber=2',
            'BeamSequence[1].BeamSequence[2].BeamNumber=3',
        ]
        print(as_dataset(paths))

    def test_keyword_non_sequence(self):
        """Tests for parsing keyword non-sequence strings."""
        pass

    def test_sequence(self):
        """Tests for parsing sequence strings."""
        pass
