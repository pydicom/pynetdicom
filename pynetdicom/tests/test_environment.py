"""Tests that confirm the environment is as expected."""

import pytest


from pynetdicom._version import __version__, is_canonical, extract_components


def test_is_canonical():
    """Test is_canonical"""
    assert is_canonical('1.0')
    assert is_canonical('1.0.0a0')
    assert is_canonical('1.0.0.post0')
    assert is_canonical('1.0.0.dev0')
    assert not is_canonical('1.0+abc.5')


REFERENCE_VERSIONS = [
    "1.0.dev456", "1.0a1", "1.0a2.dev456", "1.0a12.dev456", "1.0a12",
    "1.0b1.dev456", "1.0b2", "1.0b2.post345.dev456", "1.0b2.post345",
    "1.0rc1.dev456", "1.0rc1", "1.0", "1.0.post456.dev34", "1.0.post456",
    "1.1.dev1",
]


class TestExtractComponents(object):
    @pytest.mark.parametrize("version", REFERENCE_VERSIONS)
    def test_extract_components(self, version):
        """Test various forms of the version components"""
        extract_components(version)

    def test_bad_version_raises(self):
        """Test bad version components raise exception"""
        msg = r"The supplied `version` is not conformant with PEP440"
        with pytest.raises(ValueError, match=msg):
            extract_components("m.12.a.b.devA")
