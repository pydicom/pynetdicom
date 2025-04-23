"""Unit tests for the pynetdicom.utils module."""

from codecs import BOM_UTF32_LE
from io import BytesIO
from threading import Thread
import logging
import sys

import pytest

from pydicom.uid import UID

from pynetdicom import _config, debug_logger
from pynetdicom.utils import (
    pretty_bytes,
    validate_uid,
    make_target,
    set_uid,
    decode_bytes,
)
from .encoded_pdu_items import a_associate_rq


# debug_logger()


REFERENCE_GOOD_AE_STR = [
    ("a", b"a               "),
    ("a              b", b"a              b"),
    ("a    b", b"a    b          "),
    ("               b", b"b               "),
    ("        ab  c   ", b"ab  c           "),
    ("        ab  c      ", b"ab  c           "),
    ("ABCDEFGHIJKLMNOPQRSTUVWXYZ", b"ABCDEFGHIJKLMNOP"),
]
REFERENCE_GOOD_AE_BYTES = [
    (b"a", b"a               "),
    (b"a              b", b"a              b"),
    (b"a    b", b"a    b          "),
    (b"               b", b"b               "),
    (b"        ab  c   ", b"ab  c           "),
    (b"        ab  c      ", b"ab  c           "),
    (b"ABCDEFGHIJKLMNOPQRSTUVWXYZ", b"ABCDEFGHIJKLMNOP"),
]
REFERENCE_BAD_AE_STR = [
    "                ",  # empty, 16 chars 0x20
    "",  # empty
    "AE\\TITLE",  # backslash
    "AE\tTITLE",  # control char, tab
    "AE\rTITLE",  # control char, carriage return
    "AE\nTITLE",  # control char, new line
    "\u0009".encode("ascii"),  # \t
    "\u000a".encode("ascii"),  # \n
    "\u000c".encode("ascii"),  # \x0c
    "\u000d".encode("ascii"),  # \x0d
    "\u001b".encode("ascii"),  # \x1b
    "\u005c".encode("ascii"),  # \\
    "\u0001".encode("ascii"),  # \x01
    "\u000e".encode("ascii"),  # \x0e
    1234,
    45.1,
]
REFERENCE_BAD_AE_BYTES = [
    b"                ",  # empty, 16 chars 0x20
    b"",  # empty
    b"AE\\TITLE",  # backslash
    b"AE\tTITLE",  # control char, tab
    b"AE\rTITLE",  # control char, carriage return
    b"AE\nTITLE",  # control char, new line
    "\u0009".encode("ascii"),  # \t
    "\u000a".encode("ascii"),  # \n
    "\u000c".encode("ascii"),  # \x0c
    "\u000d".encode("ascii"),  # \x0d
    "\u001b".encode("ascii"),  # \x1b
    "\u005c".encode("ascii"),  # \\
    "\u0001".encode("ascii"),  # \x01
    "\u000e".encode("ascii"),  # \x0e
    1234,
    45.1,
]


REFERENCE_UID = [
    # UID, (enforced, non-enforced conformance)
    # Invalid, invalid
    ("", (False, False)),
    (" " * 64, (False, False)),
    ("1" * 65, (False, False)),
    ("a" * 65, (False, False)),
    # Invalid, valid
    ("a" * 64, (False, True)),
    ("0.1.2.04", (False, True)),
    ("some random string", (False, True)),
    # Valid, valid
    ("1" * 64, (True, True)),
    ("0.1.2.4", (True, True)),
]


class TestValidateUID:
    """Tests for utils.validate_uid()."""

    def setup_method(self):
        self.default_conformance = _config.ENFORCE_UID_CONFORMANCE

    def teardown_method(self):
        _config.ENFORCE_UID_CONFORMANCE = self.default_conformance

    @pytest.mark.parametrize("uid,is_valid", REFERENCE_UID)
    def test_validate_uid_conformance_true(self, uid, is_valid):
        _config.ENFORCE_UID_CONFORMANCE = True
        assert validate_uid(UID(uid)) == is_valid[0]

    @pytest.mark.parametrize("uid,is_valid", REFERENCE_UID)
    def test_validate_uid_conformance_false(self, uid, is_valid):
        _config.ENFORCE_UID_CONFORMANCE = False
        assert validate_uid(UID(uid)) == is_valid[1]


class TestPrettyBytes:
    """Tests for utils.pretty_bytes()."""

    def test_parameters(self):
        """Test parameters are correct."""
        # Default
        bytestream = a_associate_rq
        result = pretty_bytes(bytestream)
        assert len(result) == 14
        assert isinstance(result[0], str)

        # prefix
        result = pretty_bytes(bytestream, prefix="\\x")
        for line in result:
            assert line[:2] == "\\x"

        # delimiter
        result = pretty_bytes(bytestream, prefix="", delimiter=",")
        for line in result:
            assert line[2] == ","

        # items_per_line
        result = pretty_bytes(bytestream, prefix="", delimiter="", items_per_line=10)
        assert len(result[0]) == 20

        # max_size
        result = pretty_bytes(
            bytestream, prefix="", delimiter="", items_per_line=10, max_size=100
        )
        assert len(result) == 11  # 10 plus the cutoff line
        assert "Only dumping 100 bytes." == result[0]
        assert "382e332e312e312e3120" == result[-1]

        result = pretty_bytes(bytestream, max_size=None)
        assert "Only dumping 100 bytes." != result[0]
        assert "  43  4f  4d  5f  30  39  30" == result[-1]

        # suffix
        result = pretty_bytes(bytestream, suffix="xxx")
        for line in result:
            assert line[-3:] == "xxx"

    def test_bytesio(self):
        """Test wrap list using bytesio"""
        bytestream = BytesIO()
        bytestream.write(a_associate_rq)
        result = pretty_bytes(bytestream, prefix="", delimiter="", items_per_line=10)
        assert isinstance(result[0], str)


class TestMakeTarget:
    """Tests for utils.make_target()."""

    def test_make_target(self):
        """Context Setup"""
        from contextvars import ContextVar

        foo = ContextVar("foo")
        token = foo.set("foo")

        """Test for ``_config.PASS_CONTEXTVARS = False`` (the default)."""
        assert _config.PASS_CONTEXTVARS is False

        def target_without_context():
            with pytest.raises(LookupError):
                foo.get()

        thread_without_context = Thread(target=make_target(target_without_context))
        thread_without_context.start()
        thread_without_context.join()

        """Test for ``_config.PASS_CONTEXTVARS = True``."""
        _config.PASS_CONTEXTVARS = True

        def target_with_context():
            assert foo.get() == "foo"

        thread_with_context = Thread(target=make_target(target_with_context))
        thread_with_context.start()
        thread_with_context.join()

        _config.PASS_CONTEXTVARS = False

        """Context Teardown"""
        foo.reset(token)


@pytest.fixture
def utf8():
    """Add UTF-8 as a fallback codec"""
    _config.CODECS = ("ascii", "utf8")
    yield
    _config.CODECS = ("ascii",)


class TestSetUID:
    """Tests for utils.set_uid()"""

    def test_str(self):
        """Test str -> UID"""
        uid = set_uid("1.2.3", "foo")
        assert isinstance(uid, UID)
        assert uid == "1.2.3"

    def test_bytes(self):
        """Test bytes -> UID"""
        b = "1.2.3".encode("ascii")
        assert isinstance(b, bytes)
        uid = set_uid(b, "foo")
        assert isinstance(uid, UID)
        assert uid == "1.2.3"

    def test_bytes_decoding_error(self, caplog):
        """Test invalid bytes raises exception"""
        b = BOM_UTF32_LE + "1.2.3".encode("utf_32_le")
        assert isinstance(b, bytes)
        msg = (
            r"Unable to decode 'FF FE 00 00 31 00 00 00 2E 00 00 00 32 00 00 "
            r"00 2E 00 00 00 33 00 00 00' using the ascii codec\(s\)"
        )
        with caplog.at_level(logging.ERROR, logger="pynetdicom"):
            with pytest.raises(ValueError, match=msg):
                set_uid(b, "foo")

            assert ("'ascii' codec can't decode byte 0xff in position 0") in caplog.text

    def test_uid(self):
        """Test UID -> UID"""
        uid = set_uid(UID("1.2.3"), "foo")
        assert isinstance(uid, UID)
        assert uid == "1.2.3"

    def test_invalid_raises(self, caplog):
        """Test invalid UID raises exception"""
        with caplog.at_level(logging.ERROR, logger="pynetdicom"):
            bad = "abc" * 22
            msg = f"Invalid 'foo' value '{bad}' - must not exceed 64 characters"
            with pytest.raises(ValueError, match=msg):
                uid = set_uid(bad, "foo")
                assert isinstance(uid, UID)
                assert uid == bad

            assert msg in caplog.text

    def test_no_validation(self, caplog):
        """Test skipping validation"""
        with caplog.at_level(logging.WARNING, logger="pynetdicom"):
            uid = set_uid("abc" * 22, "foo", validate=False)
            assert isinstance(uid, UID)
            assert uid == "abc" * 22

            assert not caplog.text

    def test_valid_non_conformant_warns(self, caplog):
        """Test a valid but non-conformant UID warns"""
        with caplog.at_level(logging.WARNING, logger="pynetdicom"):
            uid = set_uid("1.2.03", "foo")
            assert isinstance(uid, UID)
            assert uid == "1.2.03"

            assert "Non-conformant 'foo' value '1.2.03'" in caplog.text

    def test_none_allowed(self):
        """Test None -> None"""
        uid = set_uid(None, "foo", allow_none=True)
        assert uid is None

    def test_none_disallowed(self):
        """Test None raises exception"""
        msg = "'foo' must be str, bytes or UID, not 'NoneType'"
        with pytest.raises(TypeError, match=msg):
            set_uid(None, "foo", allow_none=False)

    def test_empty_passthrough(self):
        """Test an empty value passes through validation"""
        uid = set_uid("", "foo")
        assert uid == UID("")

        uid = set_uid(b"", "foo")
        assert uid == UID("")

        uid = set_uid(UID(""), "foo")
        assert uid == UID("")

    def test_empty_raises(self):
        """Test empty raises exception"""
        msg = r"Invalid 'foo' value - must not be an empty str"
        with pytest.raises(ValueError, match=msg):
            set_uid("", "foo", allow_empty=False)


class TestDecodeBytes:
    """Tests for utils.decode_bytes"""

    def test_decoding_error(self, caplog):
        """Test decoding error raises and logs"""
        b = BOM_UTF32_LE + "1.2.3".encode("utf_32_le")
        with caplog.at_level(logging.ERROR, logger="pynetdicom"):
            msg = (
                r"Unable to decode 'FF FE 00 00 31 00 00 00 2E 00 00 00 32 "
                r"00 00 00 2E 00 00 00 33 00 00 00' using the ascii codec\(s\)"
            )
            with pytest.raises(ValueError, match=msg):
                decode_bytes(b)

            assert ("'ascii' codec can't decode byte 0xff in position 0") in caplog.text

    def test_decoding_error_fallback(self, caplog, utf8):
        """Test decoding error raises and logs"""
        b = BOM_UTF32_LE + "1.2.3".encode("utf_32_le")
        with caplog.at_level(logging.ERROR, logger="pynetdicom"):
            msg = (
                r"Unable to decode 'FF FE 00 00 31 00 00 00 2E 00 00 00 32 "
                r"00 00 00 2E 00 00 00 33 00 00 00' using the ascii, "
                r"utf8 codec\(s\)"
            )
            with pytest.raises(ValueError, match=msg):
                decode_bytes(b)

            assert ("'ascii' codec can't decode byte 0xff in position 0") in caplog.text
            assert ("'utf-8' codec can't decode byte 0xff in position 0") in caplog.text
