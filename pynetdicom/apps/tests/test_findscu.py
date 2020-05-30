"""Unit tests for findscu.py"""

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

from pynetdicom import (
    AE, evt, debug_logger, DEFAULT_TRANSFER_SYNTAXES,
    QueryRetrievePresentationContexts,
    BasicWorklistManagementPresentationContexts,
)
from pynetdicom.sop_class import (
    VerificationSOPClass,
    PatientRootQueryRetrieveInformationModelFind,
    StudyRootQueryRetrieveInformationModelFind,
    PatientStudyOnlyQueryRetrieveInformationModelFind,
    ModalityWorklistInformationFind
)


#debug_logger()


APP_DIR = os.path.join(os.path.dirname(__file__), '../')
APP_FILE = os.path.join(APP_DIR, 'findscu', 'findscu.py')
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


def start_findscu(args):
    """Start the findscu.py app and return the process."""
    pargs = [which('python'), APP_FILE, 'localhost', '11112'] + [*args]
    return subprocess.Popen(pargs)


def start_findscu_scli(args):
    """Start the findscu app using CLI and return the process."""
    pargs = [
        which('python'), '-m', 'pynetdicom', 'findscu', 'localhost', '11112'
    ] + [*args]
    return subprocess.Popen(pargs)


class FindSCUBase(object):
    """Tests for findscu.py"""
    def setup(self):
        """Run prior to each test"""
        self.ae = None
        self.func = None

    def teardown(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

    def test_default(self):
        """Test default settings."""
        events = []

        def handle_find(event):
            events.append(event)
            yield 0x0000, None

        def handle_release(event):
            events.append(event)

        handlers = [
            (evt.EVT_C_FIND, handle_find),
            (evt.EVT_RELEASED, handle_release)
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.supported_contexts = (
            QueryRetrievePresentationContexts
            + BasicWorklistManagementPresentationContexts
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func(['-k', "PatientName="])
        p.wait()
        assert p.returncode == 0

        scp.shutdown()

        assert events[0].event == evt.EVT_C_FIND
        assert events[0].identifier.PatientName == ""
        assert events[1].event == evt.EVT_RELEASED
        requestor = events[1].assoc.requestor
        assert b'FINDSCU         ' == requestor.ae_title
        assert 16382 == requestor.maximum_length
        assert b'ANY-SCP         ' == requestor.primitive.called_ae_title
        assert [] == requestor.extended_negotiation
        assert (1, 1) == requestor.asynchronous_operations
        assert {} == requestor.sop_class_common_extended
        assert {} == requestor.sop_class_extended
        assert requestor.user_identity == None
        cxs = requestor.primitive.presentation_context_definition_list
        assert len(cxs) == 13
        cxs = {cx.abstract_syntax: cx for cx in cxs}
        assert PatientRootQueryRetrieveInformationModelFind in cxs
        cx = cxs[PatientRootQueryRetrieveInformationModelFind]
        assert cx.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES

    def test_no_peer(self, capfd):
        """Test trying to connect to non-existent host."""
        p = self.func(['-k', "PatientName="])
        p.wait()
        assert p.returncode == 1

        out, err = capfd.readouterr()
        assert "Association request failed: unable to connect to remote" in err
        assert "TCP Initialisation Error: Connection refused" in err
        assert "Association Aborted" in err

    def test_bad_input(self, capfd):
        """Test being unable to read the input file."""
        p = self.func(['-f', 'no-such-file.dcm'])
        p.wait()
        assert p.returncode == 1

        out, err = capfd.readouterr()
        assert 'Cannot read input file no-such-file.dcm' in err

    def test_flag_version(self, capfd):
        """Test --version flag."""
        p = self.func(['--version'])
        p.wait()
        assert p.returncode == 0

        out, err = capfd.readouterr()
        assert 'findscu.py v' in out

    def test_flag_quiet(self, capfd):
        """Test --quiet flag."""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)

        p = self.func(['-q', '-k', 'PatientName='])
        p.wait()
        assert p.returncode == 1

        out, err = capfd.readouterr()
        assert out == err == ''

        scp.shutdown()

    def test_flag_verbose(self, capfd):
        """Test --verbose flag."""
        def handle_find(event):
            yield 0x0000, None

        handlers = [
            (evt.EVT_C_FIND, handle_find),
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.supported_contexts = (
            QueryRetrievePresentationContexts
            + BasicWorklistManagementPresentationContexts
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func(['-v', '-k', 'PatientName='])
        p.wait()
        assert p.returncode == 0

        out, err = capfd.readouterr()
        assert "Requesting Association" in err
        assert "Association Accepted" in err
        assert "Sending Find Request" in err
        assert "Find SCP Result" in err
        assert "Releasing Association" in err
        assert "Accept Parameters" not in err

        scp.shutdown()

    def test_flag_debug(self, capfd):
        """Test --debug flag."""
        def handle_find(event):
            yield 0x0000, None

        handlers = [
            (evt.EVT_C_FIND, handle_find),
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.supported_contexts = (
            QueryRetrievePresentationContexts
            + BasicWorklistManagementPresentationContexts
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func(['-d', '-k', 'PatientName='])
        p.wait()
        assert p.returncode == 0

        out, err = capfd.readouterr()
        assert "Releasing Association" in err
        assert "Accept Parameters" in err

        scp.shutdown()

    def test_flag_log_collision(self):
        """Test error with -q -v and -d flag."""
        p = self.func(['-v', '-d'])
        p.wait()
        assert p.returncode != 0

    @pytest.mark.skip("No way to test comprehensively")
    def test_flag_log_level(self):
        """Test --log-level flag."""
        pass

    def test_flag_aet(self):
        """Test --calling-aet flag."""
        events = []
        def handle_find(event):
            events.append(event)
            yield 0x0000, None

        handlers = [
            (evt.EVT_C_FIND, handle_find),
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.supported_contexts = (
            QueryRetrievePresentationContexts
            + BasicWorklistManagementPresentationContexts
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func(['-aet', 'MYSCU', '-k', 'PatientName='])
        p.wait()
        assert p.returncode == 0

        scp.shutdown()

        assert events[0].event == evt.EVT_C_FIND
        requestor = events[0].assoc.requestor
        assert b'MYSCU           ' == requestor.ae_title

    def test_flag_aec(self):
        """Test --called-aet flag."""
        events = []
        def handle_find(event):
            events.append(event)
            yield 0x0000, None

        handlers = [
            (evt.EVT_C_FIND, handle_find),
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.supported_contexts = (
            QueryRetrievePresentationContexts
            + BasicWorklistManagementPresentationContexts
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)


        p = self.func(['-aec', 'YOURSCP', '-k', 'PatientName='])
        p.wait()
        assert p.returncode == 0

        scp.shutdown()

        assert events[0].event == evt.EVT_C_FIND
        requestor = events[0].assoc.requestor
        assert b'YOURSCP         ' == requestor.primitive.called_ae_title

    def test_flag_ta(self, capfd):
        """Test --acse-timeout flag."""
        events = []

        def handle_requested(event):
            events.append(event)
            time.sleep(0.1)

        def handle_find(event):
            events.append(event)
            yield 0x0000, None

        def handle_abort(event):
            events.append(event)

        handlers = [
            (evt.EVT_C_FIND, handle_find),
            (evt.EVT_ABORTED, handle_abort),
            (evt.EVT_REQUESTED, handle_requested),
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.supported_contexts = (
            QueryRetrievePresentationContexts
            + BasicWorklistManagementPresentationContexts
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func(['-ta', '0.05', '-d', '-k', 'PatientName='])
        p.wait()
        assert p.returncode == 1

        time.sleep(0.1)

        scp.shutdown()

        out, err = capfd.readouterr()
        assert "ACSE timeout reached while waiting for response" in err
        assert events[0].event == evt.EVT_REQUESTED
        assert events[1].event == evt.EVT_ABORTED

    def test_flag_td(self, capfd):
        """Test --dimse-timeout flag."""
        events = []

        def handle_find(event):
            events.append(event)
            time.sleep(0.1)
            yield 0x0000, None

        def handle_abort(event):
            events.append(event)

        handlers = [
            (evt.EVT_C_FIND, handle_find),
            (evt.EVT_ABORTED, handle_abort),
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.supported_contexts = (
            QueryRetrievePresentationContexts
            + BasicWorklistManagementPresentationContexts
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)


        p = self.func(['-td', '0.05', '-d', '-k', 'PatientName='])
        p.wait()
        assert p.returncode == 0

        time.sleep(0.1)

        scp.shutdown()

        out, err = capfd.readouterr()
        assert "DIMSE timeout reached while waiting for message" in err
        assert events[0].event == evt.EVT_C_FIND
        assert events[1].event == evt.EVT_ABORTED

    @pytest.mark.skip("Don't think this can be tested")
    def test_flag_tn(self, capfd):
        """Test --network-timeout flag."""
        pass

    def test_flag_max_pdu(self):
        """Test --max-pdu flag."""
        events = []

        def handle_find(event):
            events.append(event)
            yield 0x0000, None

        def handle_release(event):
            events.append(event)

        handlers = [
            (evt.EVT_C_FIND, handle_find),
            (evt.EVT_RELEASED, handle_release)
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.supported_contexts = (
            QueryRetrievePresentationContexts
            + BasicWorklistManagementPresentationContexts
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)


        p = self.func(['--max-pdu', '123456', '-k', 'PatientName='])
        p.wait()
        assert p.returncode == 0

        scp.shutdown()

        assert events[0].event == evt.EVT_C_FIND
        assert events[1].event == evt.EVT_RELEASED
        requestor = events[1].assoc.requestor
        assert 123456 == requestor.maximum_length

    def test_flag_patient(self):
        """Test the -P flag."""
        events = []
        def handle_find(event):
            events.append(event)
            yield 0x0000, None

        handlers = [
            (evt.EVT_C_FIND, handle_find),
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.supported_contexts = (
            QueryRetrievePresentationContexts
            + BasicWorklistManagementPresentationContexts
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func(['-P', '-k', 'PatientName='])
        p.wait()
        assert p.returncode == 0

        scp.shutdown()

        assert events[0].event == evt.EVT_C_FIND
        cx = events[0].context
        assert cx.abstract_syntax == (
            PatientRootQueryRetrieveInformationModelFind
        )

    def test_flag_study(self):
        """Test the -S flag."""
        events = []
        def handle_find(event):
            events.append(event)
            yield 0x0000, None

        handlers = [
            (evt.EVT_C_FIND, handle_find),
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.supported_contexts = (
            QueryRetrievePresentationContexts
            + BasicWorklistManagementPresentationContexts
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func(['-S', '-k', 'PatientName='])
        p.wait()
        assert p.returncode == 0

        scp.shutdown()

        assert events[0].event == evt.EVT_C_FIND
        cx = events[0].context
        assert cx.abstract_syntax == StudyRootQueryRetrieveInformationModelFind

    def test_flag_patient_study(self):
        """Test the -O flag."""
        events = []
        def handle_find(event):
            events.append(event)
            yield 0x0000, None

        handlers = [
            (evt.EVT_C_FIND, handle_find),
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.supported_contexts = (
            QueryRetrievePresentationContexts
            + BasicWorklistManagementPresentationContexts
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func(['-O', '-k', 'PatientName='])
        p.wait()
        assert p.returncode == 0

        scp.shutdown()

        assert events[0].event == evt.EVT_C_FIND
        cx = events[0].context
        assert cx.abstract_syntax == (
            PatientStudyOnlyQueryRetrieveInformationModelFind
        )

    def test_flag_worklist(self):
        """Test the -W flag."""
        events = []
        def handle_find(event):
            events.append(event)
            yield 0x0000, None

        handlers = [
            (evt.EVT_C_FIND, handle_find),
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.supported_contexts = (
            QueryRetrievePresentationContexts
            + BasicWorklistManagementPresentationContexts
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func(['-W', '-k', 'PatientName='])
        p.wait()
        assert p.returncode == 0

        scp.shutdown()

        assert events[0].event == evt.EVT_C_FIND
        cx = events[0].context
        assert cx.abstract_syntax == ModalityWorklistInformationFind

    def test_flag_write(self):
        """Test the -w flag."""
        def handle_find(event):
            yield 0xFF00, event.identifier

        handlers = [
            (evt.EVT_C_FIND, handle_find),
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.supported_contexts = (
            QueryRetrievePresentationContexts
            + BasicWorklistManagementPresentationContexts
        )
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func(['-w', '-k', 'PatientName='])
        p.wait()
        assert p.returncode == 0

        scp.shutdown()

        assert 'rsp000001.dcm' in os.listdir()
        ds = dcmread('rsp000001.dcm')
        assert ds.PatientName == ''
        os.remove('rsp000001.dcm')


class TestFindSCU(FindSCUBase):
    """Tests for findscu.py"""
    def setup(self):
        """Run prior to each test"""
        self.ae = None
        self.func = start_findscu


class TestFindSCUCLI(FindSCUBase):
    """Tests for findscu.py"""
    def setup(self):
        """Run prior to each test"""
        self.ae = None
        self.func = start_findscu_scli
