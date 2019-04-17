"""Unit tests for the Dataset utilities."""
from copy import deepcopy
from io import BytesIO
import logging

import pytest

from pydicom.dataset import Dataset
from pydicom.dataelem import DataElement

from pynetdicom.dsutils import decode, encode, encode_element

LOGGER = logging.getLogger('pynetdicom')
handler = logging.StreamHandler()
LOGGER.setLevel(logging.CRITICAL)


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
