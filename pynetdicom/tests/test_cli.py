"""Tests for the command-line interface."""

import subprocess

import pytest

from pynetdicom import __version__


def test_version():
    """Test --version."""
    command = ['python', '-m', 'pynetdicom', '--version']
    out = subprocess.check_output(command)
    assert __version__ == out.decode('utf-8').strip()


def test_echoscu():
    """Test echoscu."""
    command = ['python', '-m', 'pynetdicom', 'echoscu', 'localhost', '11112']
    p = subprocess.Popen(command, stderr=subprocess.PIPE)
    p.wait()
    assert p.returncode == 1
    out, err = p.communicate()
    assert "unable to connect to remote" in err.decode('utf-8')
