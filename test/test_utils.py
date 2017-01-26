"""Unit tests for the utility functions.

validate_ae_title
wrap_list
"""

from io import BytesIO
import logging
import unittest

from pynetdicom3.utils import validate_ae_title, wrap_list

LOGGER = logging.getLogger('pynetdicom3')
LOGGER.setLevel(logging.CRITICAL)


class TestValidateAETitle(unittest.TestCase):
    """Test validate_ae_title() function"""
    def test_bad_parameters(self):
        "Test exception raised if ae is not str or bytes."
        with self.assertRaises(TypeError):
            validate_ae_title(1234)
        with self.assertRaises(TypeError):
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
            with self.assertRaises(ValueError):
                validate_ae_title(ae)

        # Bad bytes AE
        bad_ae = [b'                ', # empty, 16 chars 0x20
                  b'', # empty
                  b'AE\\TITLE', # backslash
                  b'AE\tTITLE', # control char, tab
                  b'AE\rTITLE', # control char, line feed
                  b'AE\nTITLE'] # control char, newline

        for ae in bad_ae:
            with self.assertRaises(ValueError):
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
            self.assertEqual(new_ae, ref_ae)
            self.assertTrue(isinstance(new_ae, str))

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
            self.assertEqual(new_ae, ref_ae)
            self.assertTrue(isinstance(new_ae, bytes))


class TestWrapList(unittest.TestCase):
    """Test wrap_list() function"""
    def test_parameters(self):
        """Test parameters are correct."""
        pass


if __name__ == "__main__":
    unittest.main()
