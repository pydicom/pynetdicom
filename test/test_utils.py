"""Unit tests for the utility functions.

validate_ae_title
wrap_list
"""

from io import BytesIO
import logging
import unittest

from pydicom.uid import UID

from pynetdicom3.utils import validate_ae_title, wrap_list, \
                              PresentationContext, PresentationContextManager

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


class TestPresentationContext(unittest.TestCase):
    """Test the PresentationContext class"""
    def test_good_init(self):
        """Test the presentation context class init"""
        pc = PresentationContext(1)
        self.assertEqual(pc.ID, 1)
        self.assertEqual(pc.AbstractSyntax, None)
        self.assertEqual(pc.TransferSyntax, [])

        pc = PresentationContext(1, '1.1.1', ['1.2.840.10008.1.2'])
        self.assertEqual(pc.ID, 1)
        self.assertEqual(pc.AbstractSyntax, '1.1.1')
        self.assertTrue(isinstance(pc.AbstractSyntax, UID))
        self.assertEqual(pc.TransferSyntax, ['1.2.840.10008.1.2'])
        self.assertTrue(isinstance(pc.TransferSyntax[0], UID))

        pc = PresentationContext(1, transfer_syntaxes=['1.2.840.10008.1.2'])
        self.assertEqual(pc.ID, 1)
        self.assertEqual(pc.AbstractSyntax, None)
        self.assertEqual(pc.TransferSyntax, ['1.2.840.10008.1.2'])
        self.assertTrue(isinstance(pc.TransferSyntax[0], UID))

        pc = PresentationContext(1, abstract_syntax='1.1.1')
        self.assertEqual(pc.ID, 1)
        self.assertEqual(pc.AbstractSyntax, '1.1.1')
        self.assertTrue(isinstance(pc.AbstractSyntax, UID))
        self.assertEqual(pc.TransferSyntax, [])

    def test_bad_init(self):
        """Test the presentation context class init"""
        with self.assertRaises(ValueError):
            PresentationContext(0)
        with self.assertRaises(ValueError):
            PresentationContext(256)
        with self.assertRaises(TypeError):
            PresentationContext(1, transfer_syntaxes='1.1.1')
        with self.assertRaises(ValueError):
            PresentationContext(1, transfer_syntaxes=[1234])
        with self.assertRaises(TypeError):
            PresentationContext(1, abstract_syntax=['1.1.1.'])
        with self.assertRaises(TypeError):
            PresentationContext(1, abstract_syntax=1234)


if __name__ == "__main__":
    unittest.main()
