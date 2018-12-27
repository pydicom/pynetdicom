"""Unit tests for the utility functions.

validate_ae_title
pretty_bytes
"""

from io import BytesIO
import logging

import pytest

from pydicom.uid import UID

from pynetdicom.utils import validate_ae_title, pretty_bytes
from .encoded_pdu_items import a_associate_rq

LOGGER = logging.getLogger('pynetdicom')
LOGGER.setLevel(logging.CRITICAL)


class TestValidateAETitle(object):
    """Test validate_ae_title() function"""
    def test_bad_parameters(self):
        "Test exception raised if ae is not str or bytes."
        with pytest.raises(TypeError):
            validate_ae_title(1234)
        with pytest.raises(TypeError):
            validate_ae_title(['aetitle'])

    def test_bad_ae_title(self):
        """Test bad AE titles raise exceptions."""
        # Bad str AE
        bad_ae = ['                ', # empty, 16 chars 0x20
                  '', # empty
                  'AE\\TITLE', # backslash
                  'AE\tTITLE', # control char, tab
                  'AE\rTITLE', # control char, line feed
                  'AE\nTITLE'] # control char, newline

        for ae in bad_ae:
            with pytest.raises(ValueError):
                validate_ae_title(ae)

        # Bad bytes AE
        bad_ae = [b'                ', # empty, 16 chars 0x20
                  b'', # empty
                  b'AE\\TITLE', # backslash
                  b'AE\tTITLE', # control char, tab
                  b'AE\rTITLE', # control char, line feed
                  b'AE\nTITLE'] # control char, newline

        for ae in bad_ae:
            with pytest.raises(ValueError):
                validate_ae_title(ae)

    def test_good_ae_title(self):
        """Test good ae titles are set correctly."""
        # Check str AE
        good_ae = ['a',
                   'a              b',
                   'a    b',
                   '               b']
        ref = ['a               ',
               'a              b',
               'a    b          ',
               'b               ']

        for ae, ref_ae in zip(good_ae, ref):
            new_ae = validate_ae_title(ae)
            assert new_ae == ref_ae
            assert isinstance(new_ae, str)

        # Check bytes AE
        good_ae = [b'a',
                   b'a              b',
                   b'a    b',
                   b'               b']
        ref = [b'a               ',
               b'a              b',
               b'a    b          ',
               b'b               ']

        for ae, ref_ae in zip(good_ae, ref):
            new_ae = validate_ae_title(ae)
            assert new_ae == ref_ae
            assert isinstance(new_ae, bytes)

    def test_invalid_ae_title_raises(self):
        """Test invalid AE title value raises exception."""
        with pytest.raises(TypeError, match=r"Invalid value for an AE"):
            validate_ae_title(1234)


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
