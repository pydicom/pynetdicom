"""Unit tests for qrscp.py storage service."""

import logging
import os
import subprocess
import sys
import tempfile
import time

import pytest

try:
    import sqlalchemy

    HAVE_SQLALCHEMY = True
except ImportError:
    HAVE_SQLALCHEMY = False

from pydicom import dcmread
from pydicom.uid import (
    ExplicitVRLittleEndian,
    ImplicitVRLittleEndian,
    DeflatedExplicitVRLittleEndian,
    ExplicitVRBigEndian,
)

from pynetdicom import AE, evt, debug_logger, DEFAULT_TRANSFER_SYNTAXES
from pynetdicom.sop_class import Verification, CTImageStorage


# debug_logger()


APP_DIR = os.path.join(os.path.dirname(__file__), "../")
APP_FILE = os.path.join(APP_DIR, "qrscp", "qrscp.py")
DATA_DIR = os.path.join(APP_DIR, "../", "tests", "dicom_files")


def start_qrscp(args):
    """Start the qrscp.py app and return the process."""
    pargs = [sys.executable, APP_FILE] + [*args]
    return subprocess.Popen(pargs)


def start_qrscp_cli(args):
    """Start the qrscp app using CLI and return the process."""
    pargs = [sys.executable, "-m", "pynetdicom", "qrscp"] + [*args]
    return subprocess.Popen(pargs)


def _send_datasets():
    pargs = [
        sys.executable,
        "-m",
        "pynetdicom",
        "storescu",
        "localhost",
        "11112",
        DATA_DIR,
        "-cx",
    ]
    subprocess.Popen(pargs)


class StoreSCPBase:
    """Tests for qrscp.py"""

    def setup_method(self):
        """Run prior to each test"""
        self.ae = None
        self.p = None
        self.func = None

        self.tfile = tempfile.NamedTemporaryFile()
        self.db_location = self.tfile.name
        self.instance_location = tempfile.TemporaryDirectory()

        self.startup = 1.0

    def teardown_method(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

        if self.p:
            self.p.kill()
            self.p.wait(timeout=5)

    def test_basic(self):
        """Test basic operation of the storage service."""
        self.p = p = self.func(
            [
                "--database-location",
                self.db_location,
                "--instance-location",
                self.instance_location.name,
                "-d",
            ]
        )
        time.sleep(self.startup)
        _send_datasets()
        time.sleep(self.startup)

        assert 5 == len(os.listdir(self.instance_location.name))


@pytest.mark.skipif(not HAVE_SQLALCHEMY, reason="Requires sqlalchemy")
class TestStoreSCP(StoreSCPBase):
    """Tests for qrscp.py"""

    def setup_method(self):
        """Run prior to each test"""
        super().setup_method()
        self.ae = None
        self.p = None
        self.func = start_qrscp


@pytest.mark.skipif(not HAVE_SQLALCHEMY, reason="Requires sqlalchemy")
class TestStoreSCPCLI(StoreSCPBase):
    """Tests for qrscp using CLI"""

    def setup_method(self):
        """Run prior to each test"""
        super().setup_method()
        self.ae = None
        self.p = None
        self.func = start_qrscp_cli
