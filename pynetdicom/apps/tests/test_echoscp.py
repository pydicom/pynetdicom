"""Unit tests for echoscp.py"""

import logging
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

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


APP_DIR = Path(__file__).parent.parent
APP_FILE = APP_DIR / "echoscp" / "echoscp.py"
DATA_DIR = APP_DIR.parent / "tests" / "dicom_files"
DATASET_FILE = DATA_DIR / "CTImageStorage.dcm"


def start_echoscp(args):
    """Start the echoscp.py app and return the process."""
    pargs = [sys.executable, APP_FILE, "11112"] + [*args]
    return subprocess.Popen(pargs)


def start_echoscp_cli(args):
    """Start the echoscp app using CLI and return the process."""
    pargs = [sys.executable, "-m", "pynetdicom", "echoscp", "11112"] + [*args]
    return subprocess.Popen(pargs)


class EchoSCPBase:
    """Tests for echoscp.py"""

    def setup_method(self):
        """Run prior to each test"""
        self.ae = None
        self.p = None
        self.func = None

    def teardown_method(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

        if self.p:
            self.p.kill()
            self.p.wait(timeout=5)

    def test_default(self):
        """Test default settings."""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_requested_context(Verification)

        self.p = p = self.func([])
        time.sleep(0.5)

        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established
        assoc.release()

        p.terminate()
        p.wait()
        assert p.returncode != 0

        assert 16382 == assoc.acceptor.maximum_length
        cxs = assoc.accepted_contexts
        assert len(cxs) == 1
        cxs = {cx.abstract_syntax: cx for cx in cxs}
        assert Verification in cxs

    def test_flag_version(self, capfd):
        """Test --version flag."""
        self.p = p = self.func(["--version"])
        p.wait()
        assert p.returncode == 0

        out, err = capfd.readouterr()
        assert "echoscp.py v" in out

    def test_flag_quiet(self, capfd):
        """Test --quiet flag."""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_requested_context(Verification)

        self.p = p = self.func(["-q"])
        time.sleep(0.5)

        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established
        status = assoc.send_c_echo()
        assert status.Status == 0x0000
        assoc.release()

        p.terminate()
        p.wait()

        out, err = capfd.readouterr()
        assert out == err == ""

    def test_flag_verbose(self, capfd):
        """Test --verbose flag."""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_requested_context(Verification)

        out, err = [], []

        self.p = p = self.func(["-v"])
        time.sleep(0.5)

        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established
        status = assoc.send_c_echo()
        assert status.Status == 0x0000
        assoc.release()

        p.terminate()
        p.wait()

        out, err = capfd.readouterr()
        assert "Accepting Association" in err
        assert "Received Echo Request" in err
        assert "Association Released" in err

    def test_flag_debug(self, capfd):
        """Test --debug flag."""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_requested_context(Verification)

        self.p = p = self.func(["-d"])
        time.sleep(0.5)

        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established
        status = assoc.send_c_echo()
        assert status.Status == 0x0000
        assoc.release()

        p.terminate()
        p.wait()

        out, err = capfd.readouterr()
        assert "pydicom.read_dataset()" in err
        assert "Accept Parameters" in err

    def test_flag_log_collision(self):
        """Test error with -q -v and -d flag."""
        self.p = p = self.func(["-v", "-d"])
        p.wait()
        assert p.returncode != 0

    @pytest.mark.skip("No way to test comprehensively")
    def test_flag_log_level(self):
        """Test --log-level flag."""
        pass

    @pytest.mark.skip("Don't think this can be tested")
    def test_flag_ta(self, capfd):
        """Test --acse-timeout flag."""
        pass

    @pytest.mark.skip("Don't think this can be tested")
    def test_flag_td(self, capfd):
        """Test --dimse-timeout flag."""
        pass

    @pytest.mark.skip("Don't think this can be tested")
    def test_flag_tn(self, capfd):
        """Test --network-timeout flag."""
        pass

    def test_flag_max_pdu(self):
        """Test --max-pdu flag."""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_requested_context(Verification)

        self.p = p = self.func(["--max-pdu", "123456"])
        time.sleep(0.5)

        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established
        assoc.release()

        p.terminate()
        p.wait()

        assert 123456 == assoc.acceptor.maximum_length

    def test_flag_xequal(self):
        """Test --prefer-uncompr flag."""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_requested_context(Verification)

        self.p = p = self.func(["-x="])
        time.sleep(0.5)

        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established
        assoc.release()

        p.terminate()
        p.wait()

        cx = assoc.accepted_contexts[0]
        assert not cx.transfer_syntax[0].is_implicit_VR

    def test_flag_xe(self):
        """Test --prefer-little flag."""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_requested_context(Verification)

        self.p = p = self.func(["-xe"])
        time.sleep(0.5)

        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established
        assoc.release()

        p.terminate()
        p.wait()

        cx = assoc.accepted_contexts[0]
        assert cx.transfer_syntax[0] == ExplicitVRLittleEndian

    def test_flag_xb(self):
        """Test --prefer-big flag."""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_requested_context(Verification)

        self.p = p = self.func(["-xb"])
        time.sleep(0.5)

        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established
        assoc.release()

        p.terminate()
        p.wait()

        cx = assoc.accepted_contexts[0]
        assert cx.transfer_syntax[0] == ExplicitVRBigEndian

    def test_flag_xi(self):
        """Test --implicit flag."""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_requested_context(Verification)

        self.p = p = self.func(["-xi"])
        time.sleep(0.5)

        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established
        assoc.release()

        p.terminate()
        p.wait()

        cx = assoc.accepted_contexts[0]
        assert cx.transfer_syntax[0] == ImplicitVRLittleEndian


class TestEchoSCP(EchoSCPBase):
    """Tests for echoscp.py"""

    def setup_method(self):
        """Run prior to each test"""
        self.ae = None
        self.p = None
        self.func = start_echoscp


class TestEchoSCPCLI(EchoSCPBase):
    """Tests for echoscp using CLI"""

    def setup_method(self):
        """Run prior to each test"""
        self.ae = None
        self.p = None
        self.func = start_echoscp_cli
