"""Unit tests for the Dataset utilities."""
from copy import deepcopy
from io import BytesIO
import logging

import pytest

from pydicom.dataset import Dataset
from pydicom.dataelem import DataElement
from pydicom.tag import Tag

from pynetdicom import debug_logger
from pynetdicom.dsutils import (
    decode, encode, encode_element, as_dataset, ElementPath
)


#debug_logger()


class TestEncode(object):
    """Test dsutils.encode(ds, is_implicit_vr, is_little_endian)."""
    def test_implicit_little(self):
        """Test encoding using implicit VR little endian."""
        ds = Dataset()
        ds.PatientName = 'CITIZEN^Snips'
        ds_enc = encode(ds, True, True)
        assert ds_enc == (
            b'\x10\x00\x10\x00\x0e\x00\x00\x00\x43\x49'
            b'\x54\x49\x5a\x45\x4e\x5e\x53\x6e\x69\x70'
            b'\x73\x20'
        )

        ds.PerimeterValue = 10
        ds_enc = encode(ds, True, True)
        assert ds_enc is None

    def test_explicit_little(self):
        """Test encoding using explicit VR little endian."""
        ds = Dataset()
        ds.PatientName = 'CITIZEN^Snips'
        ds_enc = encode(ds, False, True)
        assert ds_enc == (
            b'\x10\x00\x10\x00\x50\x4e\x0e\x00\x43\x49'
            b'\x54\x49\x5a\x45\x4e\x5e\x53\x6e\x69\x70'
            b'\x73\x20'
        )

        ds.PerimeterValue = 10
        ds_enc = encode(ds, False, True)
        assert ds_enc is None

    def test_explicit_big(self):
        """Test encoding using explicit VR big endian."""
        ds = Dataset()
        ds.PatientName = 'CITIZEN^Snips'
        ds_enc = encode(ds, False, False)
        assert ds_enc == (
            b'\x00\x10\x00\x10\x50\x4e\x00\x0e\x43\x49'
            b'\x54\x49\x5a\x45\x4e\x5e\x53\x6e\x69\x70'
            b'\x73\x20'
        )

        ds.PerimeterValue = 10
        ds_enc = encode(ds, False, False)
        assert ds_enc is None

    def test_encode_none(self):
        """Test encoding None."""
        out = encode(None, True, True)
        assert out is None

    def test_encode_empty(self):
        """Test encoding an empty dataset."""
        out = encode(Dataset(), True, True)
        assert out == b''


class TestDecode(object):
    """Test dsutils.decode(bytes, is_implicit_vr, is_little_endian)."""
    def test_implicit_little(self):
        """Test decoding using implicit VR little endian."""
        bytestring = BytesIO()
        bytestring.write(b'\x10\x00\x10\x00\x0e\x00\x00\x00\x43\x49' \
                         b'\x54\x49\x5a\x45\x4e\x5e\x53\x6e\x69\x70' \
                         b'\x73\x20')
        ds = decode(bytestring, True, True)
        assert ds.PatientName == 'CITIZEN^Snips'

    def test_explicit_little(self):
        """Test decoding using explicit VR little endian."""
        bytestring = BytesIO()
        bytestring.write(b'\x10\x00\x10\x00\x50\x4e\x0e\x00\x43\x49' \
                         b'\x54\x49\x5a\x45\x4e\x5e\x53\x6e\x69\x70' \
                         b'\x73\x20')
        ds = decode(bytestring, False, True)
        assert ds.PatientName == 'CITIZEN^Snips'

    def test_explicit_big(self):
        """Test decoding using explicit VR big endian."""
        bytestring = BytesIO()
        bytestring.write(b'\x00\x10\x00\x10\x50\x4e\x00\x0e\x43\x49' \
                         b'\x54\x49\x5a\x45\x4e\x5e\x53\x6e\x69\x70' \
                         b'\x73\x20')
        ds = decode(bytestring, False, False)
        assert ds.PatientName == 'CITIZEN^Snips'


class TestElementEncode(object):
    """Test dsutils.encode_element(elem, is_implicit_vr, is_little_endian)."""
    def test_implicit_little(self):
        """Test encoding using implicit VR little endian."""
        elem = DataElement(0x00100010, 'PN', 'CITIZEN^Snips')
        bytestring = encode_element(elem, True, True)
        assert bytestring == (
            b'\x10\x00\x10\x00\x0e\x00\x00\x00\x43'
            b'\x49\x54\x49\x5a\x45\x4e\x5e\x53\x6e'
            b'\x69\x70\x73\x20'
        )

    def test_explicit_little(self):
        """Test encoding using explicit VR little endian."""
        elem = DataElement(0x00100010, 'PN', 'CITIZEN^Snips')
        bytestring = encode_element(elem, False, True)
        assert bytestring == (
            b'\x10\x00\x10\x00\x50\x4e\x0e\x00\x43'
            b'\x49\x54\x49\x5a\x45\x4e\x5e\x53\x6e'
            b'\x69\x70\x73\x20'
        )

    def test_explicit_big(self):
        """Test encoding using explicit VR big endian."""
        elem = DataElement(0x00100010, 'PN', 'CITIZEN^Snips')
        bytestring = encode_element(elem, False, False)
        assert bytestring == (
            b'\x00\x10\x00\x10\x50\x4e\x00\x0e\x43'
            b'\x49\x54\x49\x5a\x45\x4e\x5e\x53\x6e'
            b'\x69\x70\x73\x20'
        )


class TestDecodeFailure(object):
    """Tests that ensure dataset decoding fails as expected"""
    def test_failure(self):
        def dummy(): pass
        with pytest.raises(AttributeError):
            print(decode(dummy, False, True))


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
            'PatientName=Test^Name^2',
        ]
        for ds in as_dataset(paths):
            print(ds)

        #paths.append('BeamSequence[0].BeamSequence[4]=')
        #print('\n' + str(as_dataset(paths)))
