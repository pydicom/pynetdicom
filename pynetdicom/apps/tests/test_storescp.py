"""Unit tests for storescp.py"""

import logging
import os
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
LOG_CONFIG = os.path.join(APP_DIR, 'echoscu', 'logging.cfg')
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


class TestStoreSCP(object):
    """Tests for storescp.py"""
    def setup(self):
        """Run prior to each test"""
        self.ae = None
        self.p = None

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

        self.p = p = start_storescp([])
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
        self.p = p = start_storescp(['--version'])
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

        self.p = p = start_storescp(['-q'])
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

        self.p = p = start_storescp(['-v'])
        time.sleep(0.5)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status = assoc.send_c_echo()
        assert status.Status == 0x0000
        assoc.release()

        p.terminate()
        p.wait()

        #print(capsys.readouterr())
        #print('out', p.stdout.read())
        #print('err', p.stderr.read())
        out, err = capfd.readouterr()
        print('out', out)
        print('err', err)

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

        self.p = p = start_storescp(['-d'])
        time.sleep(0.5)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status = assoc.send_c_echo()
        assert status.Status == 0x0000
        assoc.release()

        p.terminate()
        p.wait()

        out, err = capfd.readouterr()
        assert "Releasing Association" in err
        assert "Accept Parameters" in err

    def test_flag_log_collision(self):
        """Test error with -q -v and -d flag."""
        self.p = p = start_storescu(['-v', '-d'])
        p.wait()
        assert p.returncode != 0

    @pytest.mark.skip("No way to test comprehensively")
    def test_flag_log_level(self):
        """Test --log-level flag."""
        pass

    def test_flag_log_config(self, capfd):
        """Test --log-config flag."""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)

        self.p = p = start_storescp(['--log-config', LOG_CONFIG])
        time.sleep(0.5)

        out, err = capfd.readouterr()
        assert "pynetdicom.acse - ERROR - No accepted presentation" in out
        assert "No accepted presentation contexts" in err

        scp.shutdown()
