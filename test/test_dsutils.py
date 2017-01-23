"""Unit tests for the Dataset utilities."""
from copy import deepcopy
from io import BytesIO
import logging
import unittest

from pydicom.dataset import Dataset
from pydicom.dataelem import DataElement

from pynetdicom3.dsutils import correct_ambiguous_vr, decode, encode, \
                                encode_element

LOGGER = logging.getLogger('pynetdicom3')
handler = logging.StreamHandler()
LOGGER.setLevel(logging.CRITICAL)


class TestEncode(unittest.TestCase):
    """Test dsutils.encode(ds, is_implicit_vr, is_little_endian)."""
    def test_implicit_little(self):
        """Test encoding using implicit VR little endian."""
        ds = Dataset()
        ds.PatientName = 'CITIZEN^Snips'
        ds_enc = encode(ds, True, True)
        self.assertEqual(ds_enc, b'\x10\x00\x10\x00\x0e\x00\x00\x00\x43\x49' \
                                 b'\x54\x49\x5a\x45\x4e\x5e\x53\x6e\x69\x70' \
                                 b'\x73\x20')

        ds.PerimeterValue = 10
        ds_enc = encode(ds, True, True)
        self.assertEqual(ds_enc, None)

    def test_explicit_little(self):
        """Test encoding using explicit VR little endian."""
        ds = Dataset()
        ds.PatientName = 'CITIZEN^Snips'
        ds_enc = encode(ds, False, True)
        self.assertEqual(ds_enc, b'\x10\x00\x10\x00\x50\x4e\x0e\x00\x43\x49' \
                                 b'\x54\x49\x5a\x45\x4e\x5e\x53\x6e\x69\x70' \
                                 b'\x73\x20')

        ds.PerimeterValue = 10
        ds_enc = encode(ds, False, True)
        self.assertEqual(ds_enc, None)

    def test_explicit_big(self):
        """Test encoding using explicit VR big endian."""
        ds = Dataset()
        ds.PatientName = 'CITIZEN^Snips'
        ds_enc = encode(ds, False, False)
        self.assertEqual(ds_enc, b'\x00\x10\x00\x10\x50\x4e\x00\x0e\x43\x49' \
                                 b'\x54\x49\x5a\x45\x4e\x5e\x53\x6e\x69\x70' \
                                 b'\x73\x20')

        ds.PerimeterValue = 10
        ds_enc = encode(ds, False, False)
        self.assertEqual(ds_enc, None)


class TestDecode(unittest.TestCase):
    """Test dsutils.decode(bytes, is_implicit_vr, is_little_endian)."""
    def test_implicit_little(self):
        """Test decoding using implicit VR little endian."""
        bytestring = BytesIO()
        bytestring.write(b'\x10\x00\x10\x00\x0e\x00\x00\x00\x43\x49' \
                         b'\x54\x49\x5a\x45\x4e\x5e\x53\x6e\x69\x70' \
                         b'\x73\x20')
        ds = decode(bytestring, True, True)
        self.assertEqual(ds.PatientName, 'CITIZEN^Snips')

    def test_explicit_little(self):
        """Test decoding using explicit VR little endian."""
        bytestring = BytesIO()
        bytestring.write(b'\x10\x00\x10\x00\x50\x4e\x0e\x00\x43\x49' \
                         b'\x54\x49\x5a\x45\x4e\x5e\x53\x6e\x69\x70' \
                         b'\x73\x20')
        ds = decode(bytestring, False, True)
        self.assertEqual(ds.PatientName, 'CITIZEN^Snips')

    def test_explicit_big(self):
        """Test decoding using explicit VR big endian."""
        bytestring = BytesIO()
        bytestring.write(b'\x00\x10\x00\x10\x50\x4e\x00\x0e\x43\x49' \
                         b'\x54\x49\x5a\x45\x4e\x5e\x53\x6e\x69\x70' \
                         b'\x73\x20')
        ds = decode(bytestring, False, False)
        self.assertEqual(ds.PatientName, 'CITIZEN^Snips')


class TestElementEncode(unittest.TestCase):
    """Test dsutils.encode_element(elem, is_implicit_vr, is_little_endian)."""
    def test_implicit_little(self):
        """Test encoding using implicit VR little endian."""
        elem = DataElement(0x00100010, 'PN', 'CITIZEN^Snips')
        bytestring = encode_element(elem, True, True)
        self.assertEqual(bytestring, b'\x10\x00\x10\x00\x0e\x00\x00\x00\x43' \
                                     b'\x49\x54\x49\x5a\x45\x4e\x5e\x53\x6e' \
                                     b'\x69\x70\x73\x20')

    def test_explicit_little(self):
        """Test encoding using explicit VR little endian."""
        elem = DataElement(0x00100010, 'PN', 'CITIZEN^Snips')
        bytestring = encode_element(elem, False, True)
        self.assertEqual(bytestring, b'\x10\x00\x10\x00\x50\x4e\x0e\x00\x43' \
                                     b'\x49\x54\x49\x5a\x45\x4e\x5e\x53\x6e' \
                                     b'\x69\x70\x73\x20')

    def test_explicit_big(self):
        """Test encoding using explicit VR big endian."""
        elem = DataElement(0x00100010, 'PN', 'CITIZEN^Snips')
        bytestring = encode_element(elem, False, False)
        self.assertEqual(bytestring, b'\x00\x10\x00\x10\x50\x4e\x00\x0e\x43' \
                                     b'\x49\x54\x49\x5a\x45\x4e\x5e\x53\x6e' \
                                     b'\x69\x70\x73\x20')


class TestCorrectAmbiguousVR(unittest.TestCase):
    """Test correct_ambiguous_vr."""
    def test_pixel_representation_vm_one(self):
        """Test correcting VM 1 elements which require PixelRepresentation."""
        ref_ds = Dataset()

        # If PixelRepresentation is 0 then VR should be US
        ref_ds.PixelRepresentation = 0
        ref_ds.SmallestValidPixelValue = b'\x00\x01' # Little endian 256
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)
        self.assertEqual(ds.SmallestValidPixelValue, 256)
        self.assertEqual(ds[0x00280104].VR, 'US')

        # If PixelRepresentation is 1 then VR should be SS
        ref_ds.PixelRepresentation = 1
        ref_ds.SmallestValidPixelValue = b'\x00\x01' # Big endian 1
        ds = correct_ambiguous_vr(deepcopy(ref_ds), False)
        self.assertEqual(ds.SmallestValidPixelValue, 1)
        self.assertEqual(ds[0x00280104].VR, 'SS')

        # If no PixelRepresentation then raise ValueError
        ref_ds = Dataset()
        ref_ds.SmallestValidPixelValue = b'\x00\x01' # Big endian 1
        with self.assertRaises(ValueError):
            correct_ambiguous_vr(deepcopy(ref_ds), False)

    def test_pixel_representation_vm_three(self):
        """Test correcting VM 3 elements which require PixelRepresentation."""
        ref_ds = Dataset()

        # If PixelRepresentation is 0 then VR should be US - Little endian
        ref_ds.PixelRepresentation = 0
        ref_ds.LUTDescriptor = b'\x01\x00\x00\x01\x10\x00' # 1\256\16
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)
        self.assertEqual(ds.LUTDescriptor, [1, 256, 16])
        self.assertEqual(ds[0x00283002].VR, 'US')

        # If PixelRepresentation is 1 then VR should be SS
        ref_ds.PixelRepresentation = 1
        ref_ds.LUTDescriptor = b'\x01\x00\x00\x01\x00\x10'
        ds = correct_ambiguous_vr(deepcopy(ref_ds), False)
        self.assertEqual(ds.LUTDescriptor, [256, 1, 16])
        self.assertEqual(ds[0x00283002].VR, 'SS')

        # If no PixelRepresentation then raise ValueError
        ref_ds = Dataset()
        ref_ds.LUTDescriptor = b'\x01\x00\x00\x01\x00\x10'
        with self.assertRaises(ValueError):
            correct_ambiguous_vr(deepcopy(ref_ds), False)

    def test_pixel_data(self):
        """Test correcting PixelData."""
        ref_ds = Dataset()

        # If BitsAllocated  > 8 then VR must be OW
        ref_ds.BitsAllocated = 16
        ref_ds.PixelData = b'\x00\x01' # Little endian 256
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True) # Little endian
        self.assertEqual(ds.PixelData, b'\x00\x01')
        self.assertEqual(ds[0x7fe00010].VR, 'OW')
        ds = correct_ambiguous_vr(deepcopy(ref_ds), False) # Big endian
        self.assertEqual(ds.PixelData, b'\x00\x01')
        self.assertEqual(ds[0x7fe00010].VR, 'OW')

        # If BitsAllocated <= 8 then VR can be OB or OW: OW
        ref_ds = Dataset()
        ref_ds.BitsAllocated = 8
        ref_ds.Rows = 2
        ref_ds.Columns = 2
        ref_ds.PixelData = b'\x01\x00\x02\x00\x03\x00\x04\x00'
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)
        self.assertEqual(ds.PixelData, b'\x01\x00\x02\x00\x03\x00\x04\x00')
        self.assertEqual(ds[0x7fe00010].VR, 'OW')

        # If BitsAllocated <= 8 then VR can be OB or OW: OB
        ref_ds = Dataset()
        ref_ds.BitsAllocated = 8
        ref_ds.Rows = 2
        ref_ds.Columns = 2
        ref_ds.PixelData = b'\x01\x02\x03\x04'
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)
        self.assertEqual(ds.PixelData, b'\x01\x02\x03\x04')
        self.assertEqual(ds[0x7fe00010].VR, 'OB')

        # If no BitsAllocated then VR should raise ValueError
        ref_ds = Dataset()
        ref_ds.PixelData = b'\x00\x01' # Big endian 1
        with self.assertRaises(ValueError):
            correct_ambiguous_vr(deepcopy(ref_ds), False)

        # If required elements missing then VR should raise ValueError
        ref_ds = Dataset()
        ref_ds.BitsAllocated = 8
        ref_ds.Rows = 2
        ref_ds.PixelData = b'\x01\x02\x03\x04'
        with self.assertRaises(ValueError):
            correct_ambiguous_vr(deepcopy(ref_ds), False)

    def test_waveform_bits_allocated(self):
        """Test correcting elements which require WaveformBitsAllocated."""
        ref_ds = Dataset()

        # If WaveformBitsAllocated  > 8 then VR must be OW
        ref_ds.WaveformBitsAllocated = 16
        ref_ds.WaveformData = b'\x00\x01' # Little endian 256
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True) # Little endian
        self.assertEqual(ds.WaveformData, b'\x00\x01')
        self.assertEqual(ds[0x54001010].VR, 'OW')
        ds = correct_ambiguous_vr(deepcopy(ref_ds), False) # Big endian
        self.assertEqual(ds.WaveformData, b'\x00\x01')
        self.assertEqual(ds[0x54001010].VR, 'OW')

        # If WaveformBitsAllocated <= 8 then VR is OB or OW, but not sure which
        #   so raise ValueError
        ref_ds.WaveformBitsAllocated = 8
        ref_ds.WaveformData = b'\x01\x02'
        with self.assertRaises(ValueError):
            correct_ambiguous_vr(deepcopy(ref_ds), True)

        # If no WaveformBitsAllocated raise ValueError
        ref_ds = Dataset()
        ref_ds.WaveformData = b'\x00\x01' # Big endian 1
        with self.assertRaises(ValueError):
            correct_ambiguous_vr(deepcopy(ref_ds), True)

    def test_lut_descriptor(self):
        """Test correcting elements which require LUTDescriptor."""
        ref_ds = Dataset()
        ref_ds.PixelRepresentation = 0

        # If LUTDescriptor[0] is 1 then LUTData VR is 'US'
        ref_ds.LUTDescriptor = b'\x01\x00\x00\x01\x10\x00' # 1\256\16
        ref_ds.LUTData = b'\x00\x01' # Little endian 256
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True) # Little endian
        self.assertEqual(ds.LUTDescriptor[0], 1)
        self.assertEqual(ds[0x00283002].VR, 'US')
        self.assertEqual(ds.LUTData, 256)
        self.assertEqual(ds[0x00283006].VR, 'US')

        # If LUTDescriptor[0] is not 1 then LUTData VR is 'OW'
        ref_ds.LUTDescriptor = b'\x02\x00\x00\x01\x10\x00' # 2\256\16
        ref_ds.LUTData = b'\x00\x01\x00\x02'
        ds = correct_ambiguous_vr(deepcopy(ref_ds), True) # Little endian
        self.assertEqual(ds.LUTDescriptor[0], 2)
        self.assertEqual(ds[0x00283002].VR, 'US')
        self.assertEqual(ds.LUTData, b'\x00\x01\x00\x02')
        self.assertEqual(ds[0x00283006].VR, 'OW')

        # If no LUTDescriptor raise ValueError
        ref_ds = Dataset()
        ref_ds.LUTData = b'\x00\x01'
        with self.assertRaises(ValueError):
            correct_ambiguous_vr(deepcopy(ref_ds), True)

    def test_sequence(self):
        """Test correcting elements in a sequence."""
        ref_ds = Dataset()
        ref_ds.BeamSequence = [Dataset()]
        ref_ds.BeamSequence[0].PixelRepresentation = 0
        ref_ds.BeamSequence[0].SmallestValidPixelValue = b'\x00\x01'
        ref_ds.BeamSequence[0].BeamSequence = [Dataset()]
        ref_ds.BeamSequence[0].BeamSequence[0].PixelRepresentation = 0
        ref_ds.BeamSequence[0].BeamSequence[0].SmallestValidPixelValue = b'\x00\x01'

        ds = correct_ambiguous_vr(deepcopy(ref_ds), True)
        self.assertEqual(ds.BeamSequence[0].SmallestValidPixelValue, 256)
        self.assertEqual(ds.BeamSequence[0][0x00280104].VR, 'US')
        self.assertEqual(ds.BeamSequence[0].BeamSequence[0].SmallestValidPixelValue, 256)
        self.assertEqual(ds.BeamSequence[0].BeamSequence[0][0x00280104].VR, 'US')

    def test_write_explicit_vr_raises(self):
        """Test writing explicit vr raises exception if unsolved element."""
        ds = Dataset()
        ds.PerimeterValue = b'\x00\x01'
        with self.assertRaises(NotImplementedError):
            correct_ambiguous_vr(ds, True)


if __name__ == "__main__":
    unittest.main()
