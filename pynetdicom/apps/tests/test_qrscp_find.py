"""Unit tests for qrscp.py QR find service."""

import logging
import os
import subprocess
import sys
import tempfile
import time

import pytest

from pydicom import dcmread, Dataset
from pydicom.uid import (
    ExplicitVRLittleEndian, ImplicitVRLittleEndian,
    DeflatedExplicitVRLittleEndian, ExplicitVRBigEndian
)

from pynetdicom import AE, evt, debug_logger, DEFAULT_TRANSFER_SYNTAXES
from pynetdicom.sop_class import (
    PatientRootQueryRetrieveInformationModelFind,
    StudyRootQueryRetrieveInformationModelFind
)


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


class FindSCPBase(object):
    """Tests for qrscp.py"""
    def setup(self):
        """Run prior to each test"""
        self.ae = None
        self.p = None
        self.func = None

        self.tfile = tempfile.NamedTemporaryFile()
        self.db_location = self.tfile.name
        self.instance_location = tempfile.TemporaryDirectory()

        self.q_patient = ds = Dataset()
        ds.QueryRetrieveLevel = 'PATIENT'
        ds.PatientID = None

        self.q_study = ds = Dataset()
        ds.QueryRetrieveLevel = 'STUDY'
        ds.PatientID = None
        ds.StudyInstanceUID = None

        self.q_series = ds = Dataset()
        ds.QueryRetrieveLevel = 'SERIES'
        ds.PatientID = None
        ds.StudyInstanceUID = None
        ds.SeriesInstanceUID = None

        self.q_image = ds = Dataset()
        ds.QueryRetrieveLevel = 'IMAGE'
        ds.PatientID = None
        ds.StudyInstanceUID = None
        ds.SeriesInstanceUID = None
        ds.SOPInstanceUID = None

    def teardown(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

        if self.p:
            self.p.kill()
            self.p.wait(timeout=5)

    def test_pr_level_patient(self):
        """Test PATIENT query level."""
        self.p = p = self.func([
            '--database-location', self.db_location,
            '--instance-location', self.instance_location.name,
            '-d'
        ])
        time.sleep(1)
        _send_datasets()
        time.sleep(1)

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        model = PatientRootQueryRetrieveInformationModelFind
        ae.add_requested_context(model)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        responses = assoc.send_c_find(self.q_patient, model)
        for ii in range(5):
            status, ds = next(responses)
            assert status.Status == 0xFF00
            assert 'PatientID' in ds
            assert ds.RetrieveAETitle == 'QRSCP'
            assert ds.QueryRetrieveLevel == 'PATIENT'
            assert 3 == len(ds)

        status, ds = next(responses)
        assert status.Status == 0x0000
        assert ds is None
        pytest.raises(StopIteration, next, responses)

        assoc.release()

        p.terminate()
        p.wait()

    def test_pr_level_patient_invalid(self, caplog):
        """Test PATIENT query level."""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        model = PatientRootQueryRetrieveInformationModelFind
        ae.add_requested_context(model)

        self.p = p = self.func(['-d'])
        time.sleep(0.5)
        _send_datasets()
        time.sleep(1)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        self.q_patient.StudyInstanceUID = None
        responses = assoc.send_c_find(self.q_patient, model)
        status, ds = next(responses)
        assert status.Status == 0xA900
        assert ds is None
        pytest.raises(StopIteration, next, responses)

        assoc.release()

        p.terminate()
        p.wait()

    def test_pr_level_patient_req(self):
        """Test PATIENT query level."""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        model = PatientRootQueryRetrieveInformationModelFind
        ae.add_requested_context(model)

        self.p = p = self.func(['-d'])
        time.sleep(0.5)
        _send_datasets()
        time.sleep(1)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        self.q_patient.PatientName = None
        responses = assoc.send_c_find(self.q_patient, model)
        for ii in range(5):
            status, ds = next(responses)
            assert status.Status == 0xFF00
            assert 'PatientID' in ds
            assert 'PatientName' in ds
            assert ds.RetrieveAETitle == 'QRSCP'
            assert ds.QueryRetrieveLevel == 'PATIENT'
            assert 4 == len(ds)

        status, ds = next(responses)
        assert status.Status == 0x0000
        assert ds is None
        pytest.raises(StopIteration, next, responses)

        assoc.release()

        p.terminate()
        p.wait()

    def test_pr_level_study(self):
        """Test STUDY query level."""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        model = PatientRootQueryRetrieveInformationModelFind
        ae.add_requested_context(model)

        self.p = p = self.func(['-d'])
        time.sleep(0.5)
        _send_datasets()
        time.sleep(1)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        responses = assoc.send_c_find(self.q_study, model)
        for ii in range(5):
            status, ds = next(responses)
            assert status.Status == 0xFF00
            assert 'PatientID' in ds
            assert 'StudyInstanceUID' in ds
            assert ds.RetrieveAETitle == 'QRSCP'
            assert ds.QueryRetrieveLevel == 'STUDY'
            assert 4 == len(ds)

        status, ds = next(responses)
        assert status.Status == 0x0000
        assert ds is None
        pytest.raises(StopIteration, next, responses)

        assoc.release()

        p.terminate()
        p.wait()

    def test_pr_level_study_req(self):
        """Test STUDY query level."""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        model = PatientRootQueryRetrieveInformationModelFind
        ae.add_requested_context(model)

        self.p = p = self.func(['-d'])
        time.sleep(0.5)
        _send_datasets()
        time.sleep(1)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        self.q_study.StudyDate = None
        responses = assoc.send_c_find(self.q_study, model)
        for ii in range(5):
            status, ds = next(responses)
            assert status.Status == 0xFF00
            assert 'PatientID' in ds
            assert 'StudyInstanceUID' in ds
            assert 'StudyDate' in ds
            assert ds.RetrieveAETitle == 'QRSCP'
            assert ds.QueryRetrieveLevel == 'STUDY'
            assert 5 == len(ds)

        status, ds = next(responses)
        assert status.Status == 0x0000
        assert ds is None
        pytest.raises(StopIteration, next, responses)

        assoc.release()

        p.terminate()
        p.wait()

    def test_pr_level_series(self):
        """Test SERIES query level."""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        model = PatientRootQueryRetrieveInformationModelFind
        ae.add_requested_context(model)

        self.p = p = self.func(['-d'])
        time.sleep(0.5)
        _send_datasets()
        time.sleep(1)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        responses = assoc.send_c_find(self.q_series, model)
        for ii in range(5):
            status, ds = next(responses)
            assert status.Status == 0xFF00
            assert 'PatientID' in ds
            assert 'StudyInstanceUID' in ds
            assert 'SeriesInstanceUID' in ds
            assert ds.RetrieveAETitle == 'QRSCP'
            assert ds.QueryRetrieveLevel == 'SERIES'
            assert 5 == len(ds)

        status, ds = next(responses)
        assert status.Status == 0x0000
        assert ds is None
        pytest.raises(StopIteration, next, responses)

        assoc.release()

        p.terminate()
        p.wait()

    def test_pr_level_series_req(self):
        """Test SERIES query level."""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        model = PatientRootQueryRetrieveInformationModelFind
        ae.add_requested_context(model)

        self.p = p = self.func(['-d'])
        time.sleep(0.5)
        _send_datasets()
        time.sleep(1)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        self.q_series.Modality = None
        responses = assoc.send_c_find(self.q_series, model)
        for ii in range(5):
            status, ds = next(responses)
            assert status.Status == 0xFF00
            assert 'PatientID' in ds
            assert 'StudyInstanceUID' in ds
            assert 'SeriesInstanceUID' in ds
            assert 'Modality' in ds
            assert ds.RetrieveAETitle == 'QRSCP'
            assert ds.QueryRetrieveLevel == 'SERIES'
            assert 6 == len(ds)

        status, ds = next(responses)
        assert status.Status == 0x0000
        assert ds is None
        pytest.raises(StopIteration, next, responses)

        assoc.release()

        p.terminate()
        p.wait()

    def test_pr_level_image(self):
        """Test IMAGE query level."""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        model = PatientRootQueryRetrieveInformationModelFind
        ae.add_requested_context(model)

        self.p = p = self.func(['-d'])
        time.sleep(0.5)
        _send_datasets()
        time.sleep(1)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        responses = assoc.send_c_find(self.q_image, model)
        for ii in range(5):
            status, ds = next(responses)
            assert status.Status == 0xFF00
            assert 'PatientID' in ds
            assert 'StudyInstanceUID' in ds
            assert 'SeriesInstanceUID' in ds
            assert 'SOPInstanceUID' in ds
            assert ds.RetrieveAETitle == 'QRSCP'
            assert ds.QueryRetrieveLevel == 'IMAGE'
            assert 6 == len(ds)

        status, ds = next(responses)
        assert status.Status == 0x0000
        assert ds is None
        pytest.raises(StopIteration, next, responses)

        assoc.release()

        p.terminate()
        p.wait()

    def test_pr_level_image_req(self):
        """Test IMAGE query level."""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        model = PatientRootQueryRetrieveInformationModelFind
        ae.add_requested_context(model)

        self.p = p = self.func(['-d'])
        time.sleep(0.5)
        _send_datasets()
        time.sleep(1)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        self.q_image.InstanceNumber = None
        responses = assoc.send_c_find(self.q_image, model)
        for ii in range(5):
            status, ds = next(responses)
            assert status.Status == 0xFF00
            assert 'PatientID' in ds
            assert 'StudyInstanceUID' in ds
            assert 'SeriesInstanceUID' in ds
            assert 'SOPInstanceUID' in ds
            assert 'InstanceNumber' in ds
            assert ds.RetrieveAETitle == 'QRSCP'
            assert ds.QueryRetrieveLevel == 'IMAGE'
            assert 7 == len(ds)

        status, ds = next(responses)
        assert status.Status == 0x0000
        assert ds is None
        pytest.raises(StopIteration, next, responses)

        assoc.release()

        p.terminate()
        p.wait()

    def test_pr_query(self):
        """Test expected response from PatientRoot query."""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        model = PatientRootQueryRetrieveInformationModelFind
        ae.add_requested_context(model)

        self.p = p = self.func(['-d'])
        time.sleep(0.5)
        _send_datasets()
        time.sleep(1)

        ds = Dataset()
        ds.QueryRetrieveLevel = 'PATIENT'
        ds.PatientID = '4MR1'

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        responses = assoc.send_c_find(ds, model)
        for ii in range(2):
            status, ds = next(responses)
            assert status.Status == 0xFF00
            assert '4MR1' == ds.PatientID
            assert ds.RetrieveAETitle == 'QRSCP'
            assert ds.QueryRetrieveLevel == 'PATIENT'
            assert 3 == len(ds)

        status, ds = next(responses)
        assert status.Status == 0x0000
        assert ds is None
        pytest.raises(StopIteration, next, responses)

        assoc.release()

        p.terminate()
        p.wait()

    def test_sr_query(self):
        """Test expected response from StudyRoot query."""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        model = StudyRootQueryRetrieveInformationModelFind
        ae.add_requested_context(model)

        self.p = p = self.func(['-d'])
        time.sleep(0.5)
        _send_datasets()
        time.sleep(1)

        ds = Dataset()
        ds.QueryRetrieveLevel = 'STUDY'
        ds.PatientID = '4MR1'

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        responses = assoc.send_c_find(ds, model)
        for ii in range(2):
            status, ds = next(responses)
            assert status.Status == 0xFF00
            assert '4MR1' == ds.PatientID
            assert ds.RetrieveAETitle == 'QRSCP'
            assert ds.QueryRetrieveLevel == 'STUDY'
            assert 3 == len(ds)

        status, ds = next(responses)
        assert status.Status == 0x0000
        assert ds is None
        pytest.raises(StopIteration, next, responses)

        assoc.release()

        p.terminate()
        p.wait()


class TestFindSCP(FindSCPBase):
    """Tests for qrscp.py"""
    def setup(self):
        """Run prior to each test"""
        super().setup()
        self.ae = None
        self.p = None
        self.func = start_qrscp


class TestFindSCPCLI(FindSCPBase):
    """Tests for qrscp using CLI"""
    def setup(self):
        """Run prior to each test"""
        super().setup()
        self.ae = None
        self.p = None
        self.func = start_qrscp_cli
