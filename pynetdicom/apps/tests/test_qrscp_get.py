"""Unit tests for qrscp.py QR get service."""

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

from pydicom import dcmread, Dataset
from pydicom.uid import (
    ExplicitVRLittleEndian,
    ImplicitVRLittleEndian,
    DeflatedExplicitVRLittleEndian,
    ExplicitVRBigEndian,
)

from pynetdicom import AE, evt, debug_logger, DEFAULT_TRANSFER_SYNTAXES, build_role
from pynetdicom.sop_class import (
    CTImageStorage,
    PatientRootQueryRetrieveInformationModelGet,
)


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


class GetSCPBase:
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
        """Test basic operation of the QR get service."""
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

        query = Dataset()
        query.QueryRetrieveLevel = "PATIENT"
        query.PatientID = "1CT1"

        datasets = []

        def handle_store(event):
            datasets.append(event.dataset)
            return 0x0000

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        model = PatientRootQueryRetrieveInformationModelGet
        ae.add_requested_context(model)
        ae.add_requested_context(CTImageStorage)
        role = build_role(CTImageStorage, scp_role=True)
        assoc = ae.associate(
            "localhost",
            11112,
            ext_neg=[role],
            evt_handlers=[(evt.EVT_C_STORE, handle_store)],
        )
        assert assoc.is_established
        responses = assoc.send_c_get(query, model)

        status, ds = next(responses)
        assert status.Status == 0xFF00
        assert ds is None

        status, ds = next(responses)
        assert status.Status == 0x0000
        assert ds is None
        pytest.raises(StopIteration, next, responses)

        assoc.release()

        p.terminate()
        p.wait()

        assert 1 == len(datasets)
        assert "CompressedSamples^CT1" == datasets[0].PatientName


@pytest.mark.skipif(not HAVE_SQLALCHEMY, reason="Requires sqlalchemy")
class TestGetSCP(GetSCPBase):
    """Tests for qrscp.py"""

    def setup_method(self):
        """Run prior to each test"""
        super().setup_method()
        self.ae = None
        self.p = None
        self.func = start_qrscp


@pytest.mark.skipif(not HAVE_SQLALCHEMY, reason="Requires sqlalchemy")
class TestGetSCPCLI(GetSCPBase):
    """Tests for qrscp using CLI"""

    def setup_method(self):
        """Run prior to each test"""
        super().setup_method()
        self.ae = None
        self.p = None
        self.func = start_qrscp_cli
