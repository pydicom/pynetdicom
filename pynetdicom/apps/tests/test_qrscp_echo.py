"""Unit tests for qrscp.py verification service."""

import logging
import os
import subprocess
import sys
import tempfile
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
APP_FILE = os.path.join(APP_DIR, 'qrscp', 'qrscp.py')
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


def start_qrscp(args):
    """Start the qrscp.py app and return the process."""
    pargs = [which('python'), APP_FILE] + [*args]
    return subprocess.Popen(pargs)


def start_qrscp_cli(args):
    """Start the qrscp app using CLI and return the process."""
    pargs = [which('python'), '-m', 'pynetdicom', 'qrscp'] + [*args]
    return subprocess.Popen(pargs)


class EchoSCPBase(object):
    """Tests for echoscp.py"""
    def setup(self):
        """Run prior to each test"""
        self.ae = None
        self.p = None
        self.func = None

        self.tfile = tempfile.NamedTemporaryFile()
        self.db_location = 'sqlite:///{}'.format(self.tfile.name)
        self.instance_location = tempfile.TemporaryDirectory()

    def teardown(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

        if self.p:
            self.p.kill()
            self.p.wait(timeout=5)

    def test_default(self):
        """Test default settings."""
        print(self.ae)
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_requested_context(VerificationSOPClass)

        self.p = p = self.func([
            '--database-location', self.db_location,
            '--instance-location', self.instance_location.name
        ])
        time.sleep(1)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assoc.release()

        p.terminate()
        p.wait()
        assert p.returncode != 0

        assert 16382 == assoc.acceptor.maximum_length
        cxs = assoc.accepted_contexts
        assert len(cxs) == 1
        cxs = {cx.abstract_syntax: cx for cx in cxs}
        assert VerificationSOPClass in cxs

    def test_flag_version(self, capfd):
        """Test --version flag."""
        self.p = p = self.func([
            '--database-location', self.db_location,
            '--instance-location', self.instance_location.name,
            '--version'
        ])
        p.wait()
        assert p.returncode == 0

        out, err = capfd.readouterr()
        assert 'qrscp.py v' in out

    def test_flag_quiet(self, capfd):
        """Test --quiet flag."""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_requested_context(VerificationSOPClass)

        self.p = p = self.func([
            '--database-location', self.db_location,
            '--instance-location', self.instance_location.name,
            '-q'
        ])
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

        out, err = [], []

        self.p = p = self.func([
            '--database-location', self.db_location,
            '--instance-location', self.instance_location.name,
            '-v'
        ])
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

        self.p = p = self.func([
            '--database-location', self.db_location,
            '--instance-location', self.instance_location.name,
            '-d'
        ])
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
        assert 'Received C-ECHO request from' in err

    def test_flag_log_collision(self):
        """Test error with -q -v and -d flag."""
        self.p = p = self.func([
            '--database-location', self.db_location,
            '--instance-location', self.instance_location.name,
            '-v', '-d'
        ])
        p.wait()
        assert p.returncode != 0


class TestEchoSCP(EchoSCPBase):
    """Tests for echoscp.py"""
    def setup(self):
        """Run prior to each test"""
        super().setup()

        self.func = start_qrscp


class TestEchoSCPCLI(EchoSCPBase):
    """Tests for echoscp using CLI"""
    def setup(self):
        """Run prior to each test"""
        super().setup()

        self.func = start_qrscp_cli
