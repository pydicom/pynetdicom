"""Unit tests for the apps and pynetdicom.apps.common module."""

from collections import namedtuple
import logging
import os

import pytest
import pyfakefs

from pydicom.dataset import Dataset
from pydicom.tag import Tag

from pynetdicom.apps.common import ElementPath, create_dataset, get_files


class TestCreateDataset(object):
    """Tests for pynetdicom.apps.common.create_dataset()."""
    def test_element_new(self):
        """Test creating an element using keywords."""
        Args = namedtuple('args', ['keyword', 'file'])
        args = Args(['PatientName=*'], None)
        ds = create_dataset(args)

        ref = Dataset()
        ref.PatientName = '*'

        assert ds == ref

    def test_sequence_new(self):
        """Test creating a sequence using keywords."""
        Args = namedtuple('args', ['keyword', 'file'])
        args = Args(['BeamSequence[0].PatientName=*'], None)
        ds = create_dataset(args)

        ref = Dataset()
        ref.BeamSequence = [Dataset()]
        ref.BeamSequence[0].PatientName = '*'

        assert ds == ref

    def test_keyword_exception(self):
        """Test exception is raised by bad keyword."""
        Args = namedtuple('args', ['keyword', 'file'])
        args = Args(['BadPatientName=*'], None)

        msg = r"Unable to parse element path component"
        with pytest.raises(ValueError, match=msg):
            create_dataset(args)

    def test_file_read_exception(self):
        """Test exception is raised by bad file read."""
        Args = namedtuple('args', ['keyword', 'file'])
        args = Args([], 'no_such_file')

        # General exception
        msg = r"No such file or directory"
        with pytest.raises(Exception, match=msg):
            create_dataset(args)


class TestElementPath(object):
    """Tests for utils.ElementPath."""
    def test_child(self):
        """Tests for ElementPath.child."""
        elem = ElementPath('(0000,0000)')
        assert elem.child is None
        elem = ElementPath('CommandGroupLength')
        assert elem.child is None
        elem = ElementPath('(0000,0000).(0000,0002)')
        assert elem.child is not None
        assert elem.components == ['(0000,0000)', '(0000,0002)']
        child = elem.child
        assert child.child is None
        assert child.components == ['(0000,0002)']

    def test_parent(self):
        """Tests for ElementPath.parent."""
        elem = ElementPath('(0000,0000)')
        assert elem.parent is None
        elem = ElementPath('CommandGroupLength')
        assert elem.parent is None
        elem = ElementPath('(0000,0000).(0000,0002)')
        assert elem.child is not None
        assert elem.parent is None
        assert elem.components == ['(0000,0000)', '(0000,0002)']
        child = elem.child
        assert child.parent == elem
        assert child.child is None

    def test_item_nr(self):
        """Tests for ElementPath.item_nr."""
        elem = ElementPath('PatientName')
        assert elem.is_sequence is False
        assert elem.item_nr is None

        elem = ElementPath('PatientName[0]')
        assert elem.is_sequence
        assert elem.item_nr == 0

        elem = ElementPath('PatientName[12]')
        assert elem.is_sequence
        assert elem.item_nr == 12

    def test_is_sequence(self):
        """Tests for ElementPath.is_sequence."""
        elem = ElementPath('PatientName[0]')
        assert elem.is_sequence
        assert elem.item_nr == 0

        elem = ElementPath('PatientName[12]')
        assert elem.is_sequence
        assert elem.item_nr == 12

    def test_is_sequence_raises(self):
        """Tests for ElementPath.is_sequence with invalid values."""
        msg = r'Element path contains an invalid component:'
        with pytest.raises(ValueError, match=msg):
            ElementPath('PatientName[')

        with pytest.raises(ValueError, match=msg):
            ElementPath('PatientName]')

        with pytest.raises(ValueError, match=msg):
            ElementPath('PatientName][')

        with pytest.raises(ValueError, match=msg):
            ElementPath('PatientName[]')

        with pytest.raises(ValueError, match=msg):
            ElementPath('PatientName[-1]')

        with pytest.raises(ValueError, match=msg):
            ElementPath('PatientName[-10]')

        with pytest.raises(ValueError, match=msg):
            ElementPath('PatientName[as]')

    def test_keyword(self):
        """Tests for ElementPath.keyword."""
        elem = ElementPath('PatientName')
        assert elem.keyword == 'PatientName'
        elem = ElementPath('0020,0020')
        assert elem.keyword == 'PatientOrientation'
        elem = ElementPath('7ffe,0020')
        assert elem.keyword == 'VariableCoefficientsSDVN'
        elem = ElementPath('0009,0020')
        assert elem.keyword == 'Unknown'

    def test_non_sequence(self):
        """Test ElementPath using a non-sequence component."""
        elem = ElementPath('(0000,0000)')
        assert elem.tag == Tag(0x0000,0x0000)
        assert elem.keyword == 'CommandGroupLength'
        assert elem.VR == 'UL'
        assert elem.item_nr is None
        assert elem.is_sequence is False
        assert elem.child is None
        assert elem.parent is None
        assert elem.value == ''

        elem = ElementPath('0000,0000')
        assert elem.tag == Tag(0x0000,0x0000)
        assert elem.keyword == 'CommandGroupLength'
        assert elem.VR == 'UL'
        assert elem.item_nr is None
        assert elem.is_sequence is False
        assert elem.child is None
        assert elem.parent is None
        assert elem.value == ''

        elem = ElementPath('CommandGroupLength')
        assert elem.tag == Tag(0x0000,0x0000)
        assert elem.keyword == 'CommandGroupLength'
        assert elem.VR == 'UL'
        assert elem.item_nr is None
        assert elem.is_sequence is False
        assert elem.child is None
        assert elem.parent is None
        assert elem.value == ''

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
            assert elem.item_nr is None
            assert elem.is_sequence is False
            assert elem.child is None
            assert elem.parent is None
            assert elem.value == ''

        paths = [
            "(0000,0000)=120", "0000,0000=120", "CommandGroupLength=120"
        ]
        for path in paths:
            elem = ElementPath(path)
            assert elem.tag == Tag(0x0000,0x0000)
            assert elem.keyword == 'CommandGroupLength'
            assert elem.VR == 'UL'
            assert elem.item_nr is None
            assert elem.is_sequence is False
            assert elem.child is None
            assert elem.parent is None
            assert elem.value == 120

        paths = [
            "(300a,00b0)[0]=", "300a,00b0[0]=", "BeamSequence[0]="
        ]
        for path in paths:
            elem = ElementPath(path)
            assert elem.tag == Tag(0x300a,0x00b0)
            assert elem.keyword == 'BeamSequence'
            assert elem.VR == 'SQ'
            assert elem.item_nr == 0
            assert elem.is_sequence is True
            assert elem.child is None
            assert elem.parent is None
            assert elem.value == ''

        elem = ElementPath("BeamSequence[0].BeamName=")
        assert elem.tag == Tag(0x300a,0x00b0)
        assert elem.keyword == 'BeamSequence'
        assert elem.VR == 'SQ'
        assert elem.item_nr == 0
        assert elem.is_sequence is True
        assert elem.parent is None
        assert elem.value == ''

        child = elem.child
        assert child.tag == Tag(0x300a,0x00c2)
        assert child.keyword == 'BeamName'
        assert child.VR == 'LO'
        assert child.item_nr is None
        assert child.is_sequence is False
        assert child.parent is elem
        assert child.value == ''

        elem = ElementPath("BeamSequence[0].BeamName=Test")
        assert elem.tag == Tag(0x300a,0x00b0)
        assert elem.keyword == 'BeamSequence'
        assert elem.VR == 'SQ'
        assert elem.item_nr == 0
        assert elem.is_sequence is True
        assert elem.parent is None
        assert elem.value == 'Test'

        child = elem.child
        assert child.tag == Tag(0x300a,0x00c2)
        assert child.keyword == 'BeamName'
        assert child.VR == 'LO'
        assert child.item_nr is None
        assert child.is_sequence is False
        assert child.parent is elem
        assert child.value == 'Test'

        elem = ElementPath("BeamSequence[5].BeamSequence[13].BeamName=Test")
        assert elem.tag == Tag(0x300a,0x00b0)
        assert elem.keyword == 'BeamSequence'
        assert elem.VR == 'SQ'
        assert elem.item_nr == 5
        assert elem.is_sequence is True
        assert elem.parent is None
        assert elem.value == 'Test'

        child = elem.child
        assert child.tag == Tag(0x300a,0x00b0)
        assert child.keyword == 'BeamSequence'
        assert child.VR == 'SQ'
        assert child.item_nr == 13
        assert child.is_sequence is True
        assert child.parent is elem
        assert child.value == 'Test'

        subchild = child.child
        assert subchild.tag == Tag(0x300a,0x00c2)
        assert subchild.keyword == 'BeamName'
        assert subchild.VR == 'LO'
        assert subchild.item_nr is None
        assert subchild.is_sequence is False
        assert subchild.parent is child
        assert subchild.value == 'Test'

    def test_non_sequence_repeater(self):
        """Test ElementPath using a non-sequence component."""
        elem = ElementPath('(0020,3100)')
        assert elem.tag == Tag(0x0020,0x3100)
        assert elem.keyword == 'SourceImageIDs'
        assert elem.VR == 'CS'
        assert elem.item_nr is None
        assert elem.is_sequence is False

        elem = ElementPath('7Ffe,0040')
        assert elem.tag == Tag(0x7ffe,0x0040)
        assert elem.keyword == 'VariableCoefficientsSDDN'
        assert elem.VR == 'OW'
        assert elem.item_nr is None
        assert elem.is_sequence is False

    def test_private(self):
        """Test using private non-sequence component."""
        elem = ElementPath('(0029,0100)')
        assert elem.tag == Tag(0x0029,0x0100)
        assert elem.keyword == 'Unknown'
        assert elem.VR == 'UN'
        assert elem.item_nr is None
        assert elem.is_sequence is False

        msg = (
            r"Unable to parse element path component: 'UnknownPrivateElement'"
        )
        with pytest.raises(ValueError, match=msg):
            ElementPath('UnknownPrivateElement')

    def test_sequence(self):
        """Test ElementPath using a sequence component."""
        elem = ElementPath('(300a,00b0)[13]')
        assert elem.tag == Tag(0x300a,0x00b0)
        assert elem.keyword == 'BeamSequence'
        assert elem.VR == 'SQ'
        assert elem.item_nr == 13
        assert elem.is_sequence is True
        assert elem.child is None
        assert elem.parent is None
        assert elem.value == ''

        elem = ElementPath('300a,00b0[13]')
        assert elem.tag == Tag(0x300a,0x00b0)
        assert elem.keyword == 'BeamSequence'
        assert elem.VR == 'SQ'
        assert elem.item_nr == 13
        assert elem.is_sequence is True
        assert elem.child is None
        assert elem.parent is None
        assert elem.value == ''

        elem = ElementPath('BeamSequence[13]')
        assert elem.tag == Tag(0x300a,0x00b0)
        assert elem.keyword == 'BeamSequence'
        assert elem.VR == 'SQ'
        assert elem.item_nr == 13
        assert elem.is_sequence is True
        assert elem.child is None
        assert elem.parent is None
        assert elem.value == ''

    def test_sequence_raises(self):
        """Test ElementPath using bad sequence component raises."""
        msg = r'Element path contains an invalid component:'
        with pytest.raises(ValueError, match=msg):
            ElementPath('(300a,00b0)[')

        with pytest.raises(ValueError, match=msg):
            ElementPath('(300a,00b0)]')

        with pytest.raises(ValueError, match=msg):
            ElementPath('(300a,00b0)[]')

        with pytest.raises(ValueError, match=msg):
            ElementPath('300a,00b0[')

        with pytest.raises(ValueError, match=msg):
            ElementPath('300a,00b0]')

        with pytest.raises(ValueError, match=msg):
            ElementPath('300a,00b0[]')

        with pytest.raises(ValueError, match=msg):
            ElementPath('BeamSequence[')

        with pytest.raises(ValueError, match=msg):
            ElementPath('BeamSequence]')

        with pytest.raises(ValueError, match=msg):
            ElementPath('BeamSequence[]')

        with pytest.raises(ValueError, match=msg):
            ElementPath('BeamSequence[-1]')

    def test_tag(self):
        """Tests for ElementPath.tag."""
        elem = ElementPath('0000,0000')
        assert elem.tag == Tag(0x0000, 0x0000)
        elem = ElementPath('(0000,0000')
        assert elem.tag == Tag(0x0000, 0x0000)
        elem = ElementPath('0000,0000)')
        assert elem.tag == Tag(0x0000, 0x0000)
        elem = ElementPath('00(00,0000)')
        assert elem.tag == Tag(0x0000, 0x0000)
        elem = ElementPath('(00(00,00)00)')
        assert elem.tag == Tag(0x0000, 0x0000)

        # Private elements
        elem = ElementPath('(0009,0010)')
        assert elem.tag == Tag(0x0009, 0x0010)

        # Keywords
        elem = ElementPath('PatientName')
        assert elem.tag == Tag(0x0010, 0x0010)
        elem = ElementPath('CommandGroupLength')
        assert elem.tag == Tag(0x0000, 0x0000)

        # Repeater
        msg = (
            r'Repeating group elements must be specified using '
            r'\(gggg,eeee\)'
        )
        with pytest.raises(ValueError, match=msg):
            elem = ElementPath('SourceImageIDs')

        # Unknown
        msg = r'Unable to parse element path component:'
        with pytest.raises(ValueError, match=msg):
            elem = ElementPath('abcdefgh')

    def test_update_new(self):
        """Tests for parsing non-sequence strings."""
        ds = ElementPath('BeamSequence[0].PatientName=*').update(Dataset())

        assert ds.BeamSequence[0].PatientName == '*'

        paths = [
            'PatientName=Test^Name',
            'BeamSequence[0].BeamSequence[0].BeamNumber=1',
            'BeamSequence[0].BeamSequence[1].BeamNumber=2',
            'BeamSequence[0].BeamSequence[2].BeamNumber=3',
            'BeamSequence[1].BeamSequence[0].BeamNumber=4',
            'BeamSequence[1].BeamSequence[1].BeamNumber=5',
            'PatientName=Test^Name^2',
        ]
        ds = Dataset()
        for elem in [ElementPath(pp) for pp in paths]:
            elem.update(ds)

        ref = Dataset()
        ref.PatientName = "Test^Name^2"
        ref.BeamSequence = [Dataset(), Dataset()]
        ref.BeamSequence[0].BeamSequence = [Dataset(), Dataset(), Dataset()]
        ref.BeamSequence[0].BeamSequence[0].BeamNumber = 1
        ref.BeamSequence[0].BeamSequence[1].BeamNumber = 2
        ref.BeamSequence[0].BeamSequence[2].BeamNumber = 3
        ref.BeamSequence[1].BeamSequence = [Dataset(), Dataset()]
        ref.BeamSequence[1].BeamSequence[0].BeamNumber = 4
        ref.BeamSequence[1].BeamSequence[1].BeamNumber = 5

        assert ref == ds

    def test_update_repeater(self):
        """Test updating using repeater elements."""
        paths = [
            'PatientName=Test^Name',
            'BeamSequence[0].(0020,3100)=2',
        ]
        ds = Dataset()
        for elem in [ElementPath(pp) for pp in paths]:
            elem.update(ds)

        ref = Dataset()
        ref.PatientName = "Test^Name"
        ref.BeamSequence = [Dataset()]
        ref.BeamSequence[0].add_new(0x00203100, 'CS', '2')

        assert ref == ds

    def test_update_private(self):
        """Test updating using private elements."""
        paths = [
            'PatientName=Test^Name',
            'BeamSequence[0].(0029,0100)=2',
        ]
        ds = Dataset()
        for elem in [ElementPath(pp) for pp in paths]:
            elem.update(ds)

        ref = Dataset()
        ref.PatientName = "Test^Name"
        ref.BeamSequence = [Dataset()]
        ref.BeamSequence[0].add_new(0x00290100, 'UN', '2')

        assert ref == ds

    def test_update_non_sequential(self):
        """Test that updating new dataset with non-sequential items."""
        paths = [
            'BeamSequence[3]=',
            'BeamSequence[0].DACSequence[2]=',
            'BeamSequence[0].DACSequence[0].BeamSequence[1]=',
            'BeamSequence[0].DACSequence[1].BeamName=23',
        ]

        ds = Dataset()
        for elem in [ElementPath(pp) for pp in paths]:
            elem.update(ds)

        ref = Dataset()
        ref.BeamSequence = [Dataset(), Dataset(), Dataset(), Dataset()]
        ref.BeamSequence[0].DACSequence = [Dataset(), Dataset(), Dataset()]
        ref.BeamSequence[0].DACSequence[0].BeamSequence = [Dataset(), Dataset()]
        ref.BeamSequence[0].DACSequence[1].BeamName = '23'

        assert ref == ds

    def test_update_existing(self):
        """Tests for parsing non-sequence strings."""
        paths = [
            'PatientName=Test^Name',
            'BeamSequence[0].DACSequence[0].BeamNumber=1',
            'BeamSequence[0].DACSequence[1].BeamNumber=2',
            'BeamSequence[0].DACSequence[2].BeamNumber=3',
            'BeamSequence[1].DACSequence[0].BeamNumber=4',
            'BeamSequence[1].DACSequence[1].BeamNumber=5',
        ]
        ds = Dataset()
        ds.PatientName = 'Test^Name^2'
        ds.BeamSequence = [Dataset()]
        ds.BeamSequence[0].DACSequence = [Dataset()]
        ds.BeamSequence[0].DACSequence[0].BeamNumber = '100'

        for elem in [ElementPath(pp) for pp in paths]:
            elem.update(ds)

        ref = Dataset()
        ref.PatientName = "Test^Name"
        ref.BeamSequence = [Dataset(), Dataset()]
        ref.BeamSequence[0].DACSequence = [Dataset(), Dataset(), Dataset()]
        ref.BeamSequence[0].DACSequence[0].BeamNumber = 1
        ref.BeamSequence[0].DACSequence[1].BeamNumber = 2
        ref.BeamSequence[0].DACSequence[2].BeamNumber = 3
        ref.BeamSequence[1].DACSequence = [Dataset(), Dataset()]
        ref.BeamSequence[1].DACSequence[0].BeamNumber = 4
        ref.BeamSequence[1].DACSequence[1].BeamNumber = 5

        assert ref == ds

    def test_update_existing_non_sequential(self):
        """Test that updating existing dataset with non-sequential items."""
        paths = [
            'PatientName=Test^Name',
            'BeamSequence[1].DACSequence[3]=',
            'BeamSequence[0].DACSequence[2]=',
            'BeamSequence[0].DACSequence[0].BeamNumber=1',
            'BeamSequence[0].DACSequence[2].BeamNumber=3',
            'BeamSequence[1].DACSequence[3].BeamNumber=4',
        ]
        ds = Dataset()
        ds.PatientName = 'Test^Name^2'
        ds.BeamSequence = [Dataset(), Dataset()]
        ds.BeamSequence[0].DACSequence = [Dataset()]
        ds.BeamSequence[0].DACSequence[0].BeamNumber = '100'
        ds.BeamSequence[1].DACSequence = [Dataset(), Dataset()]
        ds.BeamSequence[1].DACSequence[1].BeamNumber = '101'
        ds.BeamSequence[1].DACSequence[0].BeamName = 'Beam'

        for elem in [ElementPath(pp) for pp in paths]:
            elem.update(ds)

        ref = Dataset()
        ref.PatientName = "Test^Name"
        ref.BeamSequence = [Dataset(), Dataset()]
        ref.BeamSequence[0].DACSequence = [Dataset(), Dataset(), Dataset()]
        ref.BeamSequence[0].DACSequence[0].BeamNumber = 1
        ref.BeamSequence[0].DACSequence[2].BeamNumber = 3
        ref.BeamSequence[1].DACSequence = [
            Dataset(), Dataset(), Dataset(), Dataset()
        ]
        ref.BeamSequence[1].DACSequence[3].BeamNumber = 4
        ref.BeamSequence[1].DACSequence[0].BeamName = 'Beam'
        ref.BeamSequence[1].DACSequence[1].BeamNumber = '101'

        assert ref == ds

    def test_str_types_empty(self):
        """Test that empty element values get converted correctly."""
        keywords = {
            'AE' : 'Receiver',
            'AS' : 'PatientAge',
            'AT' : 'OffendingElement',  # VM 1-n
            'CS' : 'QualityControlSubject',
            'DA' : 'PatientBirthDate',
            'DS' : 'PatientWeight',
            'DT' : 'AcquisitionDateTime',
            'IS' : 'BeamNumber',
            'LO' : 'DataSetSubtype',
            'LT' : 'ExtendedCodeMeaning',
            'PN' : 'PatientName',
            'SH' : 'CodeValue',
            'ST' : 'InstitutionAddress',
            'TM' : 'StudyTime',
            'UC' : 'LongCodeValue',
            'UI' : 'SOPClassUID',
            'UR' : 'CodingSchemeURL',
            'UT' : 'StrainAdditionalInformation',
        }
        for vr, kw in keywords.items():
            ds = ElementPath('{}='.format(kw)).update(Dataset())
            assert getattr(ds, kw) == ''

    def test_str_types(self):
        """Test that non-empty element values get converted correctly."""
        keywords = {
            'AE' : ('Receiver', 'SOME_AET'),
            'AS' : ('PatientAge', '14'),
            'AT' : ('OffendingElement', '00100020'),  # VM 1-n
            'CS' : ('QualityControlSubject', 'ASD123'),
            'DA' : ('PatientBirthDate', '20000101'),
            'DS' : ('PatientWeight', '14.7'),
            'DT' : ('AcquisitionDateTime', '20000101120000.123456'),
            'IS' : ('BeamNumber', '46'),
            'LO' : ('DataSetSubtype', 'Some long string thing for this one'),
            'LT' : ('ExtendedCodeMeaning', 'Another long string'),
            'PN' : ('PatientName', 'CITIZEN^Jan^X'),
            'SH' : ('CodeValue', '16 character str'),
            'ST' : ('InstitutionAddress', '1024 character string'),
            'TM' : ('StudyTime', '120000.123456'),
            'UC' : ('LongCodeValue', 'So many characters in this one'),
            'UI' : ('SOPClassUID', '1.2.3.4.5.6'),
            'UR' : ('CodingSchemeURL', 'http://github.com/pydicom/pynetdicom'),
            'UT' : ('StrainAdditionalInformation', 'Wheeeeeeeeee'),
        }
        for vr, (kw, val) in keywords.items():
            epath = '{}={}'.format(kw, val)
            ds = ElementPath(epath).update(Dataset())
            if vr in ['DS', 'IS']:
                assert getattr(ds, kw).original_string == val
            elif vr in ['AT']:
                assert getattr(ds, kw) == Tag(0x0010, 0x0020)
            else:
                assert getattr(ds, kw) == val

    def test_str_types_multi(self):
        """Test element values with VM > 1."""
        # AE
        epath = 'RetrieveAETitle=AET1\\AET2\\AET3'
        ds = ElementPath(epath).update(Dataset())
        assert len(ds.RetrieveAETitle) == 3
        assert ds.RetrieveAETitle[0] == 'AET1'
        assert ds.RetrieveAETitle[1] == 'AET2'
        assert ds.RetrieveAETitle[2] == 'AET3'
        # AT
        epath = 'OffendingElement=00100020\\00100021\\00200020'
        ds = ElementPath(epath).update(Dataset())
        elem = ds.OffendingElement
        assert elem[0] == Tag(0x0010, 0x0020)
        assert elem[1] == Tag(0x0010, 0x0021)
        assert elem[2] == Tag(0x0020, 0x0020)
        assert len(elem) == 3

    def test_int_types_empty(self):
        """Test that empty element values get converted correctly."""
        keywords = {
            'SL' : 'RationalNumeratorValue',
            'SS' : 'SelectorSSValue',
            'UL' : 'SimpleFrameList',
            'US' : 'SourceAcquisitionBeamNumber',
        }
        for vr, kw in keywords.items():
            ds = ElementPath('{}='.format(kw)).update(Dataset())
            assert getattr(ds, kw) == ''

    def test_int_types(self):
        """Test that non-empty element values get converted correctly."""
        keywords = {
            'SL' : ('RationalNumeratorValue', '-12'),
            'SS' : ('SelectorSSValue', '-13'),
            'UL' : ('SimpleFrameList', '14'),
            'US' : ('SourceAcquisitionBeamNumber', '15'),
        }
        for vr, (kw, val) in keywords.items():
            ds = ElementPath('{}={}'.format(kw, val)).update(Dataset())
            assert getattr(ds, kw) == int(val)

    def test_int_types_multi(self):
        """Test element values with VM > 1."""
        keywords = {
            'SL' : ('RationalNumeratorValue', '-12\\-13\\15'),
            'SS' : ('SelectorSSValue', '-13\\-14\\16'),
            'UL' : ('SimpleFrameList', '14\\15\\16'),
            'US' : ('SourceAcquisitionBeamNumber', '15\\16\\17'),
        }
        kw, val = keywords['SL']
        ds = ElementPath('{}={}'.format(kw, val)).update(Dataset())
        assert ds.RationalNumeratorValue == [-12, -13, 15]

        kw, val = keywords['SS']
        ds = ElementPath('{}={}'.format(kw, val)).update(Dataset())
        assert ds.SelectorSSValue == [-13, -14, 16]

        kw, val = keywords['UL']
        ds = ElementPath('{}={}'.format(kw, val)).update(Dataset())
        assert ds.SimpleFrameList == [14, 15, 16]

        kw, val = keywords['US']
        ds = ElementPath('{}={}'.format(kw, val)).update(Dataset())
        assert ds.SourceAcquisitionBeamNumber == [15, 16, 17]

    def test_float_types_empty(self):
        """Test that empty element values get converted correctly."""
        keywords = {
            'FD' : 'RealWorldValueLUTData',
            'FL' : 'VectorAccuracy',
        }
        for vr, kw in keywords.items():
            ds = ElementPath('{}='.format(kw)).update(Dataset())
            assert getattr(ds, kw) == ''

    def test_float_types(self):
        """Test that non-empty element values get converted correctly."""
        keywords = {
            'FD' : ('RealWorldValueLUTData', '-1.000005'),
            'FL' : ('VectorAccuracy', '12.111102'),
        }
        for vr, (kw, val) in keywords.items():
            ds = ElementPath('{}={}'.format(kw, val)).update(Dataset())
            assert getattr(ds, kw) == float(val)

    def test_float_types_multi(self):
        """Test element values with VM > 1."""
        keywords = {
            'FD' : ('RealWorldValueLUTData', '-1.000005\\91.992'),
            'FL' : ('VectorAccuracy', '12.111102\\-11129.22'),
        }
        kw, val = keywords['FD']
        ds = ElementPath('{}={}'.format(kw, val)).update(Dataset())
        assert ds.RealWorldValueLUTData == [-1.000005, 91.992]

        kw, val = keywords['FL']
        ds = ElementPath('{}={}'.format(kw, val)).update(Dataset())
        assert ds.VectorAccuracy == [12.111102, -11129.22]

    def test_byte_types_empty(self):
        """Test that empty element values get converted correctly."""
        keywords = {
            'OB' : 'FillPattern',
            'OD' : 'DoubleFloatPixelData',
            'OF' : 'UValueData',
            'OL' : 'TrackPointIndexList',
            'OW' : 'TrianglePointIndexList',
            #'OV' : '',
            'UN' : 'SelectorUNValue',
        }
        for vr, kw in keywords.items():
            ds = ElementPath('{}='.format(kw)).update(Dataset())
            assert getattr(ds, kw) == ''

    def test_byte_types(self):
        """Test that non-empty element values get converted correctly."""
        keywords = {
            'OB' : ('FillPattern','00fff0ec'),
            'OD' : ('DoubleFloatPixelData','00fff0ec'),
            'OF' : ('UValueData','00fff0ec'),
            'OL' : ('TrackPointIndexList','00fff0ec'),
            'OW' : ('TrianglePointIndexList','00fff0ec'),
            #'OV' : '',''),
            'UN' : ('SelectorUNValue', '00fff0ec'),
        }
        for vr, (kw, val) in keywords.items():
            ds = ElementPath('{}={}'.format(kw, val)).update(Dataset())
            assert getattr(ds, kw) == b'\x00\xff\xf0\xec'


REFERENCE_FS = [
    '/test.dcm',
    '/test.txt',
    '/A/test.dcm',
    '/A/test.txt',
    '/A/B/test.dcm',
    '/A/B/test.txt',
    '/A/B/C/test.dcm',
    '/A/B/C/test.txt',
    '/A/C/test.dcm',
    '/A/C/test.txt',
]
REFERENCE_OUTPUT = [
    (['/'], False, ['/test.dcm', '/test.txt']),
    (['/'], True, [
        '/test.dcm', '/test.txt',
        '/A/test.dcm', '/A/test.txt',
        '/A/B/test.dcm', '/A/B/test.txt',
        '/A/B/C/test.dcm', '/A/B/C/test.txt',
        '/A/C/test.dcm', '/A/C/test.txt',
    ]),
    (['/A'], False, ['/A/test.dcm', '/A/test.txt']),
    (['/A'], True, [
        '/A/test.dcm', '/A/test.txt',
        '/A/B/test.dcm', '/A/B/test.txt',
        '/A/B/C/test.dcm', '/A/B/C/test.txt',
        '/A/C/test.dcm', '/A/C/test.txt',
    ]),
    (['/A/B'], False, ['/A/B/test.dcm', '/A/B/test.txt']),
    (['/A/B'], True, [
        '/A/B/test.dcm', '/A/B/test.txt',
        '/A/B/C/test.dcm', '/A/B/C/test.txt',
    ]),
    (['/A/B/C'], False, ['/A/B/C/test.dcm', '/A/B/C/test.txt']),
    (['/A/B/C'], True, ['/A/B/C/test.dcm', '/A/B/C/test.txt',]),
    (['/A/B/C/test.dcm'], False, ['/A/B/C/test.dcm']),
    (['/A/B/C/test.dcm'], True, ['/A/B/C/test.dcm']),
    # Multiples
    (['/', '/A/test.dcm'], False, ['/test.dcm', '/test.txt', '/A/test.dcm']),
    (['/', '/A/test.dcm'], True, [
        '/test.dcm', '/test.txt',
        '/A/test.dcm', '/A/test.txt',
        '/A/B/test.dcm', '/A/B/test.txt',
        '/A/B/C/test.dcm', '/A/B/C/test.txt',
        '/A/C/test.dcm', '/A/C/test.txt',
    ]),
    (['/A/B', '/A/C'], False, [
        '/A/B/test.dcm', '/A/B/test.txt', '/A/C/test.dcm', '/A/C/test.txt'
    ]),
    (['/A/B', '/A/C'], True, [
        '/A/B/test.dcm', '/A/B/test.txt',
        '/A/C/test.dcm', '/A/C/test.txt',
        '/A/B/C/test.dcm', '/A/B/C/test.txt'
    ]),
    (['/A/B', '/A/C', 'test.txt'], False, [
        '/A/B/test.dcm', '/A/B/test.txt', '/A/C/test.dcm', '/A/C/test.txt',
        'test.txt'
    ]),
    (['/A/B', '/A/C'], True, [
        '/A/B/test.dcm', '/A/B/test.txt',
        '/A/C/test.dcm', '/A/C/test.txt',
        '/A/B/C/test.dcm', '/A/B/C/test.txt'
    ]),
    (['/A/B', '/A/C', 'test.txt'], True, [
        '/A/B/test.dcm', '/A/B/test.txt',
        '/A/C/test.dcm', '/A/C/test.txt',
        '/A/B/C/test.dcm', '/A/B/C/test.txt', 'test.txt'
    ]),
]


@pytest.mark.parametrize('fpaths, recurse, out', REFERENCE_OUTPUT)
def test_get_files(fpaths, recurse, out, fs):
    """Test finding files in a given path."""
    for fpath in REFERENCE_FS:
        fs.create_file(fpath)

    assert set(out) == set(get_files(fpaths, recurse)[0])
