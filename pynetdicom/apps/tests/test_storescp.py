"""Unit tests for storescp.py"""

import logging
import os
from pathlib import Path
import shutil
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
from pynetdicom.sop_class import (
    Verification,
    CTImageStorage,
    SecondaryCaptureImageStorage,
)


# debug_logger()


APP_DIR = Path(__file__).parent.parent
APP_FILE = APP_DIR / "storescp" / "storescp.py"
DATA_DIR = APP_DIR.parent / "tests" / "dicom_files"
DATASET_FILE = DATA_DIR / "CTImageStorage.dcm"
DEFLATED_FILE = DATA_DIR / "SCImageStorage_Deflated.dcm"
TEST_DIR = Path(__file__).parent / "test_dir"


def start_storescp(args):
    """Start the storescp.py app and return the process."""
    pargs = [sys.executable, APP_FILE, "11112"] + [*args]
    return subprocess.Popen(pargs)


def start_storescp_cli(args):
    """Start the storescp app using CLI and return the process."""
    pargs = [sys.executable, "-m", "pynetdicom", "storescp", "11112"] + [*args]
    return subprocess.Popen(pargs)


class StoreSCPBase:
    """Tests for storescp.py"""

    def setup_method(self):
        """Run prior to each test"""
        self.ae = None
        self.p = None
        self.func = None

    def teardown_method(self):
        """Clear any active threads"""
        if TEST_DIR.exists():
            shutil.rmtree(os.fspath(TEST_DIR))

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
        ae.add_requested_context(CTImageStorage)

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
        assert len(cxs) == 2
        cxs = {cx.abstract_syntax: cx for cx in cxs}
        assert CTImageStorage in cxs
        assert Verification in cxs

    def test_flag_version(self, capfd):
        """Test --version flag."""
        self.p = p = self.func(["--version"])
        p.wait()
        assert p.returncode == 0

        out, err = capfd.readouterr()
        assert "storescp.py v" in out

    def test_flag_quiet(self, capfd):
        """Test --quiet flag."""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_requested_context(Verification)
        ae.add_requested_context(CTImageStorage)

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
        ae.add_requested_context(CTImageStorage)

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
        ae.add_requested_context(CTImageStorage)

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

    def test_flag_output(self):
        """Test the -od --output-directory flag."""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_requested_context(Verification)
        ae.add_requested_context(CTImageStorage)

        assert not TEST_DIR.exists()

        self.p = p = self.func(["-od", os.fspath(TEST_DIR)])
        time.sleep(0.5)

        ds = dcmread(DATASET_FILE)

        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established
        status = assoc.send_c_store(ds)
        assert status.Status == 0x0000
        assoc.release()

        assert (TEST_DIR / f"CT.{ds.SOPInstanceUID}").exists()
        shutil.rmtree(os.fspath(TEST_DIR))
        assert not TEST_DIR.exists()

    def test_flag_ignore(self):
        """Test the --ignore flag."""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_requested_context(Verification)
        ae.add_requested_context(CTImageStorage)

        self.p = p = self.func(["--ignore"])
        time.sleep(0.5)

        ds = dcmread(DATASET_FILE)

        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established
        status = assoc.send_c_store(ds)
        assert status.Status == 0x0000
        assoc.release()

        assert not (TEST_DIR / f"CT.{ds.SOPInstanceUID}").exists()

    def test_store_deflated(self):
        """Test storing deflated dataset"""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_requested_context(
            SecondaryCaptureImageStorage,
            DeflatedExplicitVRLittleEndian,
        )

        assert not TEST_DIR.exists()

        self.p = p = self.func(["-od", os.fspath(TEST_DIR)])
        time.sleep(0.5)

        ds = dcmread(DEFLATED_FILE)

        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established
        status = assoc.send_c_store(ds)
        assert status.Status == 0x0000
        assoc.release()

        p = TEST_DIR / f"SC.{ds.SOPInstanceUID}"
        assert p.exists()
        ds = dcmread(p)
        assert ds.file_meta.TransferSyntaxUID == DeflatedExplicitVRLittleEndian
        shutil.rmtree(os.fspath(TEST_DIR))
        assert not TEST_DIR.exists()


class TestStoreSCP(StoreSCPBase):
    """Tests for storescp.py"""

    def setup_method(self):
        """Run prior to each test"""
        self.ae = None
        self.p = None
        self.func = start_storescp


class TestStoreSCPCLI(StoreSCPBase):
    """Tests for storescp using CLI"""

    def setup_method(self):
        """Run prior to each test"""
        self.ae = None
        self.p = None
        self.func = start_storescp_cli
