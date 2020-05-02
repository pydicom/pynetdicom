"""Unit tests for the dataset utilities."""

from copy import deepcopy
from io import BytesIO
import logging

import pytest

from pydicom import config
from pydicom.dataset import Dataset
from pydicom.dataelem import DataElement
from pydicom.valuerep import DA, DSfloat, DSdecimal, DT, IS, TM
from pydicom.uid import UID

from pynetdicom import debug_logger
from pynetdicom.dsutils import (
    decode, encode, encode_element, pretty_dataset, pretty_element
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


class TestPrettyElement(object):
    """Tests for pretty_element()."""
    def teardown(self):
        config.DS_decimal(False)
        config.datetime_conversion = False

    def test_bytes_empty(self):
        """Test empty byte VRs"""
        ds = Dataset()
        ds.PixelData = b''
        ds['PixelData'].VR = 'OB'
        assert (
            '(7FE0,0010) OB (no value available)                     # 0'
            ' PixelData'
        ) == pretty_element(ds['PixelData'])

    def test_bytes_short(self):
        """Test byte VRs containing small amounts of data"""
        ds = Dataset()
        ds.PixelData = (
            b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0A\x0B\x0C'
        )
        ds['PixelData'].VR = 'OB'
        assert (
            '(7FE0,0010) OB [00 01 02 03 04 05 06 07 08 09 0a 0b 0c] # 1'
            ' PixelData'
        ) == pretty_element(ds['PixelData'])

    def test_bytes_long(self):
        """Test byte VRs containing lots of data"""
        ds = Dataset()
        ds.PixelData = b'\x00' * 128
        ds['PixelData'].VR = 'OB'
        assert (
            '(7FE0,0010) OB (128 bytes of binary data)               # 1'
            ' PixelData'
        ) == pretty_element(ds['PixelData'])

    def test_bytes_vm_multi(self):
        """Test byte VRs with VM > 1"""
        ds = Dataset()
        ds.PixelData = [
            b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0A\x0B\x0C',
            b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0A\x0B\x0C',
        ]
        ds['PixelData'].VR = 'OB'
        assert (
            '(7FE0,0010) OB (26 bytes of binary data)                # 2'
            ' PixelData'
        ) == pretty_element(ds['PixelData'])

    def test_da_empty(self):
        """Test empty DA VR value"""
        ds = Dataset()
        ds.InstanceCreationDate = None
        assert (
            '(0008,0012) DA (no value available)                     # 0'
            ' InstanceCreationDate'
        ) == pretty_element(ds['InstanceCreationDate'])

    def test_da_vm_one(self):
        """Test single DA VR value"""
        config.datetime_conversion = True
        ds = Dataset()
        ds.InstanceCreationDate = '20200102'
        assert isinstance(ds.InstanceCreationDate, DA)
        assert (
            '(0008,0012) DA [20200102]                               # 1'
            ' InstanceCreationDate'
        ) == pretty_element(ds['InstanceCreationDate'])

    def test_da_vm_multi(self):
        """Test multi DA VR value"""
        config.datetime_conversion = True
        ds = Dataset()
        ds.InstanceCreationDate = ['20200102', '19851231']
        assert isinstance(ds.InstanceCreationDate[0], DA)
        assert (
            r'(0008,0012) DA [20200102\19851231]                      # 2'
            ' InstanceCreationDate'
        ) == pretty_element(ds['InstanceCreationDate'])

    def test_dsdecimal_empty(self):
        """Test empty DSdecimal VR value"""
        config.DS_decimal(True)
        ds = Dataset()
        ds.EventElapsedTimes = None
        assert (
            '(0008,2130) DS (no value available)                     # 0'
            ' EventElapsedTimes'
        ) == pretty_element(ds['EventElapsedTimes'])

    def test_dsdecimal_vm_one(self):
        """Test single DSdecimal VR value"""
        config.DS_decimal(True)
        ds = Dataset()
        ds.EventElapsedTimes = "1.23456"
        assert isinstance(ds.EventElapsedTimes, DSdecimal)
        assert (
            '(0008,2130) DS [1.23456]                                # 1'
            ' EventElapsedTimes'
        ) == pretty_element(ds['EventElapsedTimes'])

    def test_dsdecimal_vm_multi(self):
        """Test multi DSdecimal VR value"""
        config.DS_decimal(True)
        ds = Dataset()
        ds.EventElapsedTimes = ["1.23456", "2.23"]
        assert isinstance(ds.EventElapsedTimes[0], DSdecimal)
        assert (
            r'(0008,2130) DS [1.23456\2.23]                           # 2'
            ' EventElapsedTimes'
        ) == pretty_element(ds['EventElapsedTimes'])

    def test_dsfloat_empty(self):
        """Test empty DSfloat VR value"""
        ds = Dataset()
        ds.EventElapsedTimes = None
        assert (
            '(0008,2130) DS (no value available)                     # 0'
            ' EventElapsedTimes'
        ) == pretty_element(ds['EventElapsedTimes'])

    def test_dsfloat_vm_one(self):
        """Test single DSfloat VR value"""
        ds = Dataset()
        ds.EventElapsedTimes = "1.23456"
        assert isinstance(ds.EventElapsedTimes, DSfloat)
        assert (
            '(0008,2130) DS [1.23456]                                # 1'
            ' EventElapsedTimes'
        ) == pretty_element(ds['EventElapsedTimes'])

    def test_dsfloat_vm_multi(self):
        """Test multi DSfloat VR value"""
        ds = Dataset()
        ds.EventElapsedTimes = ["1.23456", "2.23"]
        assert isinstance(ds.EventElapsedTimes[0], DSfloat)
        assert (
            r'(0008,2130) DS [1.23456\2.23]                           # 2'
            ' EventElapsedTimes'
        ) == pretty_element(ds['EventElapsedTimes'])

    def test_dt_empty(self):
        """Test empty DT VR value"""
        ds = Dataset()
        ds.AcquisitionDateTime = None
        assert (
            '(0008,002A) DT (no value available)                     # 0'
            ' AcquisitionDateTime'
        ) == pretty_element(ds['AcquisitionDateTime'])

    def test_dt_vm_one(self):
        """Test single DT VR value"""
        config.datetime_conversion = True
        ds = Dataset()
        ds.AcquisitionDateTime = '20200102'
        assert isinstance(ds.AcquisitionDateTime, DT)
        assert (
            '(0008,002A) DT [20200102]                               # 1'
            ' AcquisitionDateTime'
        ) == pretty_element(ds['AcquisitionDateTime'])

    def test_dt_vm_multi(self):
        """Test multi DT VR value"""
        config.datetime_conversion = True
        ds = Dataset()
        ds.AcquisitionDateTime = ['20200102', '19851231']
        assert isinstance(ds.AcquisitionDateTime[0], DT)
        assert (
            r'(0008,002A) DT [20200102\19851231]                      # 2'
            ' AcquisitionDateTime'
        ) == pretty_element(ds['AcquisitionDateTime'])

    def test_float_empty(self):
        """Test empty float VR value"""
        ds = Dataset()
        ds.ExaminedBodyThickness = None
        assert (
            '(0010,9431) FL (no value available)                     # 0'
            ' ExaminedBodyThickness'
        ) == pretty_element(ds['ExaminedBodyThickness'])

    def test_float_vm_one(self):
        """Test single float VR value"""
        ds = Dataset()
        ds.ExaminedBodyThickness = 1.23456
        assert (
            '(0010,9431) FL [1.23456]                                # 1'
            ' ExaminedBodyThickness'
        ) == pretty_element(ds['ExaminedBodyThickness'])

    def test_float_vm_multi(self):
        """Test multi float VR value"""
        ds = Dataset()
        ds.ExaminedBodyThickness = [1.23456, 0.00001]
        assert (
            r'(0010,9431) FL [1.23456\1e-05]                          # 2'
            ' ExaminedBodyThickness'
        ) == pretty_element(ds['ExaminedBodyThickness'])

    def test_int_empty(self):
        """Test empty int VR value"""
        ds = Dataset()
        ds.BitsAllocated = None
        assert (
            '(0028,0100) US (no value available)                     # 0'
            ' BitsAllocated'
        ) == pretty_element(ds['BitsAllocated'])

    def test_int_vm_one(self):
        """Test single int VR value"""
        ds = Dataset()
        ds.BitsAllocated = 1234
        assert (
            '(0028,0100) US [1234]                                   # 1'
            ' BitsAllocated'
        ) == pretty_element(ds['BitsAllocated'])

    def test_int_vm_multi(self):
        """Test multi int VR value"""
        ds = Dataset()
        ds.BitsAllocated = [1234, 4]
        assert (
            r'(0028,0100) US [1234\4]                                 # 2'
            ' BitsAllocated'
        ) == pretty_element(ds['BitsAllocated'])

    def test_is_empty(self):
        """Test empty IS VR value"""
        ds = Dataset()
        ds.StageNumber = None
        assert (
            '(0008,2122) IS (no value available)                     # 0'
            ' StageNumber'
        ) == pretty_element(ds['StageNumber'])

    def test_is_vm_one(self):
        """Test single IS VR value"""
        config.datetime_conversion = True
        ds = Dataset()
        ds.StageNumber = '20200102'
        assert isinstance(ds.StageNumber, IS)
        assert (
            '(0008,2122) IS [20200102]                               # 1'
            ' StageNumber'
        ) == pretty_element(ds['StageNumber'])

    def test_is_vm_multi(self):
        """Test multi IS VR value"""
        config.datetime_conversion = True
        ds = Dataset()
        ds.StageNumber = ['20200102', '19851231']
        assert isinstance(ds.StageNumber[0], IS)
        assert (
            r'(0008,2122) IS [20200102\19851231]                      # 2'
            ' StageNumber'
        ) == pretty_element(ds['StageNumber'])

    def test_pn_empty(self):
        """Test empty PersonName VR value"""
        ds = Dataset()
        ds.PatientName = None
        assert (
            '(0010,0010) PN (no value available)                     # 0'
            ' PatientName'
        ) == pretty_element(ds['PatientName'])

    def test_pn_vm_one(self):
        """Test single PersonName VR value"""
        ds = Dataset()
        ds.PatientName = 'Citizen^Jan'
        assert (
            '(0010,0010) PN [Citizen^Jan]                            # 1'
            ' PatientName'
        ) == pretty_element(ds['PatientName'])

    def test_pn_vm_multi(self):
        """Test multi PersonName VR value"""
        ds = Dataset()
        ds.PatientName = ['Citizen^Jan', 'Citizen^Snips']
        assert (
            r'(0010,0010) PN [Citizen^Jan\Citizen^Snips]              # 2'
            ' PatientName'
        ) == pretty_element(ds['PatientName'])

    def test_seq_empty(self):
        """Test empty sequence"""
        ds = Dataset()
        ds.EventCodeSequence = []
        assert (
            '(0008,2135) SQ (Sequence with 0 items)                  # 0'
            ' EventCodeSequence'
        ) == pretty_element(ds['EventCodeSequence'])

    def test_seq_vm_one(self):
        """Test sequence with one item"""
        ds = Dataset()
        ds.EventCodeSequence = [Dataset()]
        assert (
            '(0008,2135) SQ (Sequence with 1 item)                   # 1'
            ' EventCodeSequence'
        ) == pretty_element(ds['EventCodeSequence'])

    def test_seq_vm_multi(self):
        """Test sequence with one item"""
        ds = Dataset()
        ds.EventCodeSequence = [Dataset(), Dataset()]
        assert (
            '(0008,2135) SQ (Sequence with 2 items)                  # 2'
            ' EventCodeSequence'
        ) == pretty_element(ds['EventCodeSequence'])

    def test_str_empty(self):
        """Test empty string VR value"""
        ds = Dataset()
        ds.PatientAge = None
        assert (
            '(0010,1010) AS (no value available)                     # 0'
            ' PatientAge'
        ) == pretty_element(ds['PatientAge'])

    def test_str_vm_one(self):
        """Test single string VR value"""
        ds = Dataset()
        ds.PatientAge = '10'
        assert (
            '(0010,1010) AS [10]                                     # 1'
            ' PatientAge'
        ) == pretty_element(ds['PatientAge'])

    def test_str_vm_multi(self):
        """Test multi string VR value"""
        ds = Dataset()
        ds.PatientAge = ['10', '11']
        assert (
            r'(0010,1010) AS [10\11]                                  # 2'
            ' PatientAge'
        ) == pretty_element(ds['PatientAge'])

    def test_tm_empty(self):
        """Test empty TM VR value"""
        ds = Dataset()
        ds.PatientBirthTime = None
        assert (
            '(0010,0032) TM (no value available)                     # 0'
            ' PatientBirthTime'
        ) == pretty_element(ds['PatientBirthTime'])

    def test_tm_vm_one(self):
        """Test single TM VR value"""
        config.datetime_conversion = True
        ds = Dataset()
        ds.PatientBirthTime = '120102'
        assert isinstance(ds.PatientBirthTime, TM)
        assert (
            '(0010,0032) TM [120102]                                 # 1'
            ' PatientBirthTime'
        ) == pretty_element(ds['PatientBirthTime'])

    def test_tm_vm_multi(self):
        """Test multi TM VR value"""
        config.datetime_conversion = True
        ds = Dataset()
        ds.PatientBirthTime = ['120102', '235959']
        assert isinstance(ds.PatientBirthTime[0], TM)
        assert (
            r'(0010,0032) TM [120102\235959]                          # 2'
            ' PatientBirthTime'
        ) == pretty_element(ds['PatientBirthTime'])

    def test_ui_empty(self):
        """Test empty UI VR value"""
        ds = Dataset()
        ds.SOPInstanceUID = None
        assert (
            '(0008,0018) UI (no value available)                     # 0'
            ' SOPInstanceUID'
        ) == pretty_element(ds['SOPInstanceUID'])

    def test_ui_vm_one(self):
        """Test single UI VR value"""
        ds = Dataset()
        ds.SOPInstanceUID = '1.2.3.4'
        assert (
            '(0008,0018) UI [1.2.3.4]                                # 1'
            ' SOPInstanceUID'
        ) == pretty_element(ds['SOPInstanceUID'])

    def test_ui_vm_multi(self):
        """Test multi UI VR value"""
        ds = Dataset()
        ds.SOPInstanceUID = ['1.2.3.4', '1.2.3.4.5']
        assert (
            r'(0008,0018) UI [1.2.3.4\1.2.3.4.5]                      # 2'
            ' SOPInstanceUID'
        ) == pretty_element(ds['SOPInstanceUID'])

    def test_pretty_failure(self):
        """Test failure to pretty up the element."""
        def some_func():
            pass

        ds = Dataset()
        ds.PixelData = some_func
        ds['PixelData'].VR = 'OB'
        assert (
            '(7FE0,0010) OB (pynetdicom failed to beautify value)    # 1 PixelData'
        ) == pretty_element(ds['PixelData'])


class TestPrettyDataset(object):
    """Tests for dsutils.pretty_dataset()."""
    def test_empty(self):
        """Test using an empty dataset."""
        assert [] == pretty_dataset(Dataset())

    def test_non_sequence(self):
        """Test using a dataset with no sequence items."""
        ds = Dataset()
        ds.PatientName = 'Citizen^Jan'
        ds.PatientID = None
        ds.PatientBirthDate = ['19840988', '20200527']
        out = pretty_dataset(ds)
        assert 3 == len(out)
        assert (
            '(0010,0010) PN [Citizen^Jan]                            # 1'
            ' PatientName'
        ) == out[0]
        assert (
            '(0010,0020) LO (no value available)                     # 0'
            ' PatientID'
        ) == out[1]
        assert (
            r'(0010,0030) DA [19840988\20200527]                      # 2'
            ' PatientBirthDate'
        ) == out[2]

    def test_sequence_empty(self):
        """Test using a dataset with an empty sequence."""
        ref = [
            '(0010,0010) PN [Citizen^Jan]                            # 1 PatientName',
            '(0014,2002) SQ (Sequence with 0 items)                  # 0 EvaluatorSequence',
            '(7FE0,0010) OB (no value available)                     # 0 PixelData',
        ]
        ds = Dataset()
        ds.PatientName = 'Citizen^Jan'
        ds.EvaluatorSequence = []
        ds.PixelData = None
        ds['PixelData'].VR = 'OB'
        assert ref == pretty_dataset(ds)

    def test_sequence_one(self):
        """Test using a dataset with a sequence of one item."""
        ref = [
            '(0010,0010) PN [Citizen^Jan]                            # 1 PatientName',
            '(0014,2002) SQ (Sequence with 1 item)                   # 1 EvaluatorSequence',
            '  (Sequence item #1)',
            '    (0010,0020) LO (no value available)                     # 0 PatientID',
            '    (0010,0030) DA [20011201]                               # 1 PatientBirthDate',
            '(7FE0,0010) OB (no value available)                     # 0 PixelData',
        ]
        ds = Dataset()
        ds.PatientName = 'Citizen^Jan'
        ds.EvaluatorSequence = [Dataset()]
        item = ds.EvaluatorSequence[0]
        item.PatientID = None
        item.PatientBirthDate = '20011201'
        ds.PixelData = None
        ds['PixelData'].VR = 'OB'
        out = pretty_dataset(ds)
        print()
        for line in out:
            print(line)
        assert ref == pretty_dataset(ds)

    def test_sequence_multi(self):
        """Test using a dataset with a sequence with multiple items."""
        ref = [
            '(0010,0010) PN [Citizen^Jan]                            # 1 PatientName',
            '(0014,2002) SQ (Sequence with 3 items)                  # 3 EvaluatorSequence',
            '  (Sequence item #1)',
            '    (0010,0020) LO (no value available)                     # 0 PatientID',
            '    (0010,0030) DA [20011201]                               # 1 PatientBirthDate',
            '  (Sequence item #2)',
            '  (Sequence item #3)',
            '    (0010,0020) LO [123456]                                 # 1 PatientID',
            '    (0010,0030) DA [20021201]                               # 1 PatientBirthDate',
            '(7FE0,0010) OB (no value available)                     # 0 PixelData',
        ]
        ds = Dataset()
        ds.PatientName = 'Citizen^Jan'
        ds.EvaluatorSequence = [Dataset(), Dataset(), Dataset()]
        item = ds.EvaluatorSequence[0]
        item.PatientID = None
        item.PatientBirthDate = '20011201'
        item = ds.EvaluatorSequence[2]
        item.PatientID = '123456'
        item.PatientBirthDate = '20021201'
        ds.PixelData = None
        ds['PixelData'].VR = 'OB'
        out = pretty_dataset(ds)
        print()
        for line in out:
            print(line)
        assert ref == pretty_dataset(ds)
