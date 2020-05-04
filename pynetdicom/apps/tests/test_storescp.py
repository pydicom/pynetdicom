"""Unit tests for storescp.py"""

import logging
import os
import shutil
import subprocess
import sys
import time

import pytest

from pydicom import dcmread
from pydicom.uid import (
    ExplicitVRLittleEndian, ImplicitVRLittleEndian,
    DeflatedExplicitVRLittleEndian, ExplicitVRBigEndian
)

from pynetdicom import AE, evt, debug_logger, DEFAULT_TRANSFER_SYNTAXES
from pynetdicom.sop_class import VerificationSOPClass, CTImageStorage


#debug_logger()


APP_DIR = os.path.join(os.path.dirname(__file__), '../')
APP_FILE = os.path.join(APP_DIR, 'storescp', 'storescp.py')
DATA_DIR = os.path.join(APP_DIR, '../', 'tests', 'dicom_files')
DATASET_FILE = os.path.join(DATA_DIR, 'CTImageStorage.dcm')


def which(program):
    # Determine if a given program is installed on PATH
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file


def start_storescp(args):
    """Start the storescp.py app and return the process."""
    pargs = [which('python'), APP_FILE, '11112'] + [*args]
    return subprocess.Popen(pargs)


def start_storescp_cli(args):
    """Start the storescp app using CLI and return the process."""
    pargs = [
        which('python'), '-m', 'pynetdicom', 'storescp', '11112'
    ] + [*args]
    return subprocess.Popen(pargs)


class StoreSCPBase(object):
    """Tests for storescp.py"""
    def setup(self):
        """Run prior to each test"""
        self.ae = None
        self.p = None
        self.func = None

    def teardown(self):
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
        ae.add_requested_context(VerificationSOPClass)
        ae.add_requested_context(CTImageStorage)

        self.p = p = self.func([])
        time.sleep(0.5)

        assoc = ae.associate('localhost', 11112)
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
        assert VerificationSOPClass in cxs

    def test_flag_version(self, capfd):
        """Test --version flag."""
        self.p = p = self.func(['--version'])
        p.wait()
        assert p.returncode == 0

        out, err = capfd.readouterr()
        assert 'storescp.py v' in out

    def test_flag_quiet(self, capfd):
        """Test --quiet flag."""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_requested_context(VerificationSOPClass)
        ae.add_requested_context(CTImageStorage)

        self.p = p = self.func(['-q'])
        time.sleep(0.5)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status = assoc.send_c_echo()
        assert status.Status == 0x0000
        assoc.release()

        p.terminate()
        p.wait()

        out, err = capfd.readouterr()
        assert out == err == ''

    def test_flag_verbose(self, capfd):
        """Test --verbose flag."""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_requested_context(VerificationSOPClass)
        ae.add_requested_context(CTImageStorage)

        self.p = p = self.func(['-v'])
        time.sleep(0.5)

        assoc = ae.associate('localhost', 11112)
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
        ae.add_requested_context(VerificationSOPClass)
        ae.add_requested_context(CTImageStorage)

        self.p = p = self.func(['-d'])
        time.sleep(0.5)

        assoc = ae.associate('localhost', 11112)
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
        self.p = p = self.func(['-v', '-d'])
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
        ae.add_requested_context(VerificationSOPClass)

        self.p = p = self.func(['--max-pdu', '123456'])
        time.sleep(0.5)

        assoc = ae.associate('localhost', 11112)
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
        ae.add_requested_context(VerificationSOPClass)

        self.p = p = self.func(['-x='])
        time.sleep(0.5)

        assoc = ae.associate('localhost', 11112)
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
        ae.add_requested_context(VerificationSOPClass)

        self.p = p = self.func(['-xe'])
        time.sleep(0.5)

        assoc = ae.associate('localhost', 11112)
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
        ae.add_requested_context(VerificationSOPClass)

        self.p = p = self.func(['-xb'])
        time.sleep(0.5)

        assoc = ae.associate('localhost', 11112)
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
        ae.add_requested_context(VerificationSOPClass)

        self.p = p = self.func(['-xi'])
        time.sleep(0.5)

        assoc = ae.associate('localhost', 11112)
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
        ae.add_requested_context(VerificationSOPClass)
        ae.add_requested_context(CTImageStorage)

        assert 'test_dir' not in os.listdir()

        self.p = p = self.func(['-od', 'test_dir'])
        time.sleep(0.5)

        ds = dcmread(DATASET_FILE)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status = assoc.send_c_store(ds)
        assert status.Status == 0x0000
        assoc.release()

        assert 'CT.{}'.format(ds.SOPInstanceUID) in os.listdir('test_dir')
        shutil.rmtree('test_dir')
        assert 'test_dir' not in os.listdir()

    def test_flag_ignore(self):
        """Test the --ignore flag."""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_requested_context(VerificationSOPClass)
        ae.add_requested_context(CTImageStorage)

        self.p = p = self.func(['--ignore'])
        time.sleep(0.5)

        ds = dcmread(DATASET_FILE)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status = assoc.send_c_store(ds)
        assert status.Status == 0x0000
        assoc.release()

        assert 'CT.{}'.format(ds.SOPInstanceUID) not in os.listdir()


class TestStoreSCP(StoreSCPBase):
    """Tests for storescp.py"""
    def setup(self):
        """Run prior to each test"""
        self.ae = None
        self.p = None
        self.func = start_storescp


class TestStoreSCPCLI(StoreSCPBase):
    """Tests for storescp using CLI"""
    def setup(self):
        """Run prior to each test"""
        self.ae = None
        self.p = None
        self.func = start_storescp_cli
