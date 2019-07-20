"""Unit tests for the pynetdicom.utils module."""

from io import BytesIO
import logging

import pytest

from pydicom.uid import UID

from pynetdicom import _config, debug_logger
from pynetdicom.utils import validate_ae_title, pretty_bytes, validate_uid
from .encoded_pdu_items import a_associate_rq


#debug_logger()


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
    """Tests for utils.validate_ae_title()."""
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
    """Tests for utils.validate_uid()."""
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


class TestPrettyBytes(object):
    """Tests for utils.pretty_bytes()."""
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
