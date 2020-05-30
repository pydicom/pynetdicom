"""Unit tests for qrscp.py storage service."""

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


def _send_datasets():
    pargs = [
        which('python'), '-m', 'pynetdicom', 'storescu', 'localhost', '11112',
        DATA_DIR, '-cx'
    ]
    subprocess.Popen(pargs)


class StoreSCPBase(object):
    """Tests for qrscp.py"""
    def setup(self):
        """Run prior to each test"""
        self.ae = None
        self.p = None
        self.func = None

        self.tfile = tempfile.NamedTemporaryFile()
        self.db_location = self.tfile.name
        self.instance_location = tempfile.TemporaryDirectory()

    def teardown(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

        if self.p:
            self.p.kill()
            self.p.wait(timeout=5)

    def test_basic(self):
        """Test basic operation of the storage service."""
        self.p = p = self.func([
            '--database-location', self.db_location,
            '--instance-location', self.instance_location.name,
            '-d'
        ])
        time.sleep(1)
        _send_datasets()
        time.sleep(1)

        assert 5 == len(os.listdir(self.instance_location.name))


class TestStoreSCP(StoreSCPBase):
    """Tests for qrscp.py"""
    def setup(self):
        """Run prior to each test"""
        super().setup()
        self.ae = None
        self.p = None
        self.func = start_qrscp


class TestStoreSCPCLI(StoreSCPBase):
    """Tests for qrscp using CLI"""
    def setup(self):
        """Run prior to each test"""
        super().setup()
        self.ae = None
        self.p = None
        self.func = start_qrscp_cli
