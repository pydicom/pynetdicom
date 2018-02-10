"""Unit tests for the Dataset utilities."""
from copy import deepcopy
from io import BytesIO
import logging
import unittest

from pydicom.dataset import Dataset
from pydicom.dataelem import DataElement

from pynetdicom3.dsutils import decode, encode, encode_element

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


if __name__ == "__main__":
    unittest.main()
