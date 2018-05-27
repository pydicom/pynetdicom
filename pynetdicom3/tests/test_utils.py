"""Unit tests for the utility functions.

validate_ae_title
pretty_bytes
"""

from io import BytesIO
import logging
import unittest

from pydicom.uid import UID

from pynetdicom3.utils import validate_ae_title, pretty_bytes, \
                              PresentationContext, PresentationContextManager
from .encoded_pdu_items import a_associate_rq

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
    """Test pretty_bytes() function"""
    def test_parameters(self):
        """Test parameters are correct."""
        # Default
        bytestream = a_associate_rq
        result = pretty_bytes(bytestream)
        self.assertEqual(len(result), 14)
        self.assertTrue(isinstance(result[0], str))

        # prefix
        result = pretty_bytes(bytestream, prefix='\\x')
        for line in result:
            self.assertTrue(line[:2] == '\\x')

        # delimiter
        result = pretty_bytes(bytestream, prefix='', delimiter=',')
        for line in result:
            self.assertTrue(line[2] == ',')

        # items_per_line
        result = pretty_bytes(bytestream, prefix='', delimiter='',
                           items_per_line=10)
        self.assertEqual(len(result[0]), 20)

        # max_size
        result = pretty_bytes(bytestream, prefix='', delimiter='',
                           items_per_line=10, max_size=100)
        self.assertEqual(len(result), 11) # 10 plus the cutoff line
        result = pretty_bytes(bytestream, max_size=None)

        # suffix
        result = pretty_bytes(bytestream, suffix='xxx')
        for line in result:
            self.assertTrue(line[-3:] == 'xxx')

    def test_bytesio(self):
        """Test wrap list using bytesio"""
        bytestream = BytesIO()
        bytestream.write(a_associate_rq)
        result = pretty_bytes(bytestream, prefix='', delimiter='',
                           items_per_line=10)
        self.assertTrue(isinstance(result[0], str))


class TestPresentationContextManager(unittest.TestCase):
    """Test the PresentationContextManager class"""
    def test_good_init(self):
        """Test the presentation context manager init"""
        req = PresentationContext()
        req.context_id = 1
        req.abstract_syntax = '1.1.1'
        req.transfer_syntax = ['1.2.840.10008.1.2']
        acc = PresentationContext()
        acc.context_id = 1
        acc.abstract_syntax = '1.1.1'
        acc.transfer_syntax = ['1.2.840.10008.1.2']

        pcm = PresentationContextManager()
        self.assertEqual(pcm.requestor_contexts, [])
        self.assertEqual(pcm.acceptor_contexts, [])

        pcm = PresentationContextManager([req], [acc])
        self.assertEqual(pcm.requestor_contexts, [req])
        self.assertEqual(pcm.acceptor_contexts, [acc])

    def test_bad_init(self):
        """Test breaking the presentation context manager init"""
        req = PresentationContext()
        req.context_id = 1
        req.abstract_syntax = '1.1.1'
        req.transfer_syntax = ['1.2.840.10008.1.2']
        acc = PresentationContext()
        acc.context_id = 1
        acc.abstract_syntax = '1.1.1'
        acc.transfer_syntax = ['1.2.840.10008.1.2']

        pcm = PresentationContextManager()
        self.assertEqual(pcm.requestor_contexts, [])
        self.assertEqual(pcm.acceptor_contexts, [])

        with self.assertRaises(TypeError):
            pcm = PresentationContextManager(req, [acc])
        #with self.assertRaises(TypeError):
        #    pcm = PresentationContextManager([req], acc)

    @unittest.skip('Skip this until we update PCM')
    def test_property_setters(self):
        """Test the property setters"""
        # Requestor
        req = PresentationContext(1, '1.1.1', ['1.2.840.10008.1.2'])
        acc = PresentationContext(1, '1.1.1', ['1.2.840.10008.1.2.1'])

        # No matching abstract syntax
        pcm = PresentationContextManager([req])
        acc = PresentationContext(1, '1.1.2', ['1.2.840.10008.1.2'])
        pcm.acceptor_contexts = [acc]
        self.assertEqual(pcm.accepted, [])
        acc.Result = 0x03
        #print(acc, pcm.rejected)
        self.assertEqual(pcm.rejected, [acc])

        pcm = PresentationContextManager()
        with self.assertRaises(RuntimeError):
            pcm.acceptor_contexts = [acc]
        pcm.requestor_contexts = [req]
        self.assertEqual(pcm.requestor_contexts, [req])
        with self.assertRaises(TypeError):
            pcm.requestor_contexts = req

        # Acceptor
        # No matching transfer syntax
        pcm.requestor_contexts = [req]
        pcm.acceptor_contexts = [acc]
        self.assertEqual(pcm.accepted, [])
        acc.Result = 0x04
        self.assertEqual(pcm.rejected, [acc])



        # Accepted
        pcm = PresentationContextManager()
        pcm.requestor_contexts = [req]
        acc = PresentationContext(1, '1.1.1', ['1.2.840.10008.1.2'])
        pcm.acceptor_contexts = [acc]
        self.assertEqual(pcm.rejected, [])
        acc.Result = 0x01
        self.assertEqual(pcm.accepted, [acc])
