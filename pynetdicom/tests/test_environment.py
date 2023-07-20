"""Tests that confirm the environment is as expected."""

import os
import sys

import pytest

from pynetdicom._version import __version__, is_canonical


def get_envar(envar):
    """Return the value of the environmental variable `envar`.

    Parameters
    ----------
    envar : str
        The environmental variable to check for.

    Returns
    -------
    str or None
        If the envar is present then return its value otherwise returns None.
    """
    if envar in os.environ:
        return os.environ.get(envar)

    return None


IN_GITHUB = get_envar("GITHUB_ACTIONS") == "true"


@pytest.mark.skipif(not IN_GITHUB, reason="Tests not running in Github")
class TestBuilds:
    """Tests for the testing builds in Github Actions."""

    def test_python_version(self):
        """Test that the python version is correct."""
        version = get_envar("PYTHON_VERSION")
        if not version:
            raise RuntimeError("No 'PYTHON_VERSION' envar has been set")

        # remove any pre-release suffix
        version = version.split("-")[0]
        version = tuple([int(vv) for vv in version.split(".")])
        assert version[:2] == sys.version_info[:2]


# Tests for the pynetdicom version
def test_is_canonical():
    """Test is_canonical"""
    assert is_canonical("1.0")
    assert is_canonical("1.0.0a0")
    assert is_canonical("1.0.0.post0")
    assert is_canonical("1.0.0.dev0")
    assert not is_canonical("1.0+abc.5")
