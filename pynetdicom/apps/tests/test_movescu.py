"""Unit tests for movescu.py"""

import logging
import os
import shutil
import subprocess
import sys
import time

import pytest

from pydicom import dcmread
from pydicom.dataset import Dataset
from pydicom.uid import (
    ExplicitVRLittleEndian, ImplicitVRLittleEndian,
    DeflatedExplicitVRLittleEndian, ExplicitVRBigEndian
)

from pynetdicom import (
    AE, evt, debug_logger, DEFAULT_TRANSFER_SYNTAXES,
    QueryRetrievePresentationContexts,
    StoragePresentationContexts
)
from pynetdicom.sop_class import (
    VerificationSOPClass, CTImageStorage,
    PatientRootQueryRetrieveInformationModelMove,
    StudyRootQueryRetrieveInformationModelMove,
    PatientStudyOnlyQueryRetrieveInformationModelMove,
)


#debug_logger()


APP_DIR = os.path.join(os.path.dirname(__file__), '../')
APP_FILE = os.path.join(APP_DIR, 'movescu', 'movescu.py')
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


def start_movescu(args):
    """Start the movescu.py app and return the process."""
    pargs = [which('python'), APP_FILE, 'localhost', '11112'] + [*args]
    return subprocess.Popen(pargs)


def start_movescu_cli(args):
    """Start the movescu.py app using CLI and return the process."""
    pargs = [
        which('python'), '-m', 'pynetdicom', 'movescu', 'localhost', '11112'
    ] + [*args]
    return subprocess.Popen(pargs)


class MoveSCUBase(object):
    """Tests for movescu.py"""
    def setup(self):
        """Run prior to each test"""
        self.ae = None
        self.func = None

        self.response = ds = Dataset()
        ds.file_meta = Dataset()
        ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
        ds.SOPClassUID = CTImageStorage
        ds.SOPInstanceUID = '1.2.3.4'
        ds.PatientName = 'Citizen^Jan'

    def teardown(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

    def test_default(self):
        """Test default settings."""
        events = []

        def handle_move(event):
            events.append(event)
            yield 'localhost', 11113
            yield 0
            yield 0x0000, None

        def handle_release(event):
            events.append(event)

        def handle_store(event):
            return 0x0000

        handlers = [
            (evt.EVT_C_MOVE, handle_move),
            (evt.EVT_RELEASED, handle_release)
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.supported_contexts = QueryRetrievePresentationContexts
        ae.requested_contexts = StoragePresentationContexts
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)
        store_scp = ae.start_server(
            ('', 11113), block=False,
            evt_handlers=[(evt.EVT_C_STORE, handle_store)]
        )

        p = self.func(['-k', "PatientName="])
        p.wait()
        assert p.returncode == 0

        store_scp.shutdown()
        scp.shutdown()

        assert events[0].event == evt.EVT_C_MOVE
        assert events[0].identifier.PatientName == ""
        assert events[1].event == evt.EVT_RELEASED
        requestor = events[1].assoc.requestor
        assert b'MOVESCU         ' == requestor.ae_title
        assert 16382 == requestor.maximum_length
        assert b'ANY-SCP         ' == requestor.primitive.called_ae_title
        assert 0 == len(requestor.extended_negotiation)
        assert (1, 1) == requestor.asynchronous_operations
        assert {} == requestor.sop_class_common_extended
        assert {} == requestor.sop_class_extended
        assert requestor.role_selection == {}
        assert requestor.user_identity == None
        cxs = requestor.primitive.presentation_context_definition_list
        assert len(cxs) == 12
        cxs = {cx.abstract_syntax: cx for cx in cxs}
        assert PatientRootQueryRetrieveInformationModelMove in cxs
        cx = cxs[PatientRootQueryRetrieveInformationModelMove]
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
        assert 'movescu.py v' in out

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
        def handle_store(event):
            return 0x0000

        def handle_move(event):
            yield 'localhost', 11113
            yield 0
            yield 0x0000, None

        handlers = [
            (evt.EVT_C_MOVE, handle_move),
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.requested_contexts = StoragePresentationContexts
        ae.supported_contexts = QueryRetrievePresentationContexts
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)
        ae.supported_contexts = StoragePresentationContexts
        store_scp = ae.start_server(
            ('', 11113), block=False,
            evt_handlers=[(evt.EVT_C_STORE, handle_store)]
        )

        p = self.func(['-v', '-k', 'PatientName='])
        p.wait()
        assert p.returncode == 0

        out, err = capfd.readouterr()
        assert "Requesting Association" in err
        assert "Association Accepted" in err
        assert "Sending Move Request" in err
        assert "Move SCP Result" in err
        assert "Releasing Association" in err
        assert "Accept Parameters" not in err

        store_scp.shutdown()
        scp.shutdown()

    def test_flag_debug(self, capfd):
        """Test --debug flag."""
        def handle_store(event):
            return 0x0000

        def handle_move(event):
            yield 'localhost', 11113
            yield 0
            yield 0x0000, None

        handlers = [
            (evt.EVT_C_MOVE, handle_move),
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.requested_contexts = StoragePresentationContexts
        ae.supported_contexts = QueryRetrievePresentationContexts
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)
        ae.supported_contexts = StoragePresentationContexts
        store_scp = ae.start_server(
            ('', 11113), block=False,
            evt_handlers=[(evt.EVT_C_STORE, handle_store)]
        )

        p = self.func(['-d', '-k', 'PatientName='])
        p.wait()
        assert p.returncode == 0

        out, err = capfd.readouterr()
        assert "Releasing Association" in err
        assert "Accept Parameters" in err

        store_scp.shutdown()
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
        def handle_move(event):
            events.append(event)
            yield 'localhost', 11113
            yield 0
            yield 0x0000, None

        handlers = [
            (evt.EVT_C_MOVE, handle_move),
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.requested_contexts = StoragePresentationContexts
        ae.supported_contexts = QueryRetrievePresentationContexts
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)
        ae.supported_contexts = StoragePresentationContexts

        p = self.func(['-aet', 'MYSCU', '-k', 'PatientName='])
        p.wait()
        assert p.returncode == 0

        scp.shutdown()

        assert events[0].event == evt.EVT_C_MOVE
        requestor = events[0].assoc.requestor
        assert b'MYSCU           ' == requestor.ae_title

    def test_flag_aec(self):
        """Test --called-aet flag."""
        events = []
        def handle_move(event):
            events.append(event)
            yield 'localhost', 11113
            yield 0
            yield 0x0000, None

        handlers = [
            (evt.EVT_C_MOVE, handle_move),
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.requested_contexts = StoragePresentationContexts
        ae.supported_contexts = QueryRetrievePresentationContexts
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func(['-aec', 'YOURSCP', '-k', 'PatientName='])
        p.wait()
        assert p.returncode == 0

        scp.shutdown()

        assert events[0].event == evt.EVT_C_MOVE
        requestor = events[0].assoc.requestor
        assert b'YOURSCP         ' == requestor.primitive.called_ae_title

    def test_flag_aem(self):
        """Test --called-aem flag."""
        events = []
        def handle_move(event):
            events.append(event)
            yield 'localhost', 11113
            yield 0
            yield 0x0000, None

        handlers = [
            (evt.EVT_C_MOVE, handle_move),
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.requested_contexts = StoragePresentationContexts
        ae.supported_contexts = QueryRetrievePresentationContexts
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)
        ae.supported_contexts = StoragePresentationContexts

        p = self.func(['-aem', 'SOMESCP', '-k', 'PatientName='])
        p.wait()
        assert p.returncode == 0

        scp.shutdown()

        assert events[0].event == evt.EVT_C_MOVE
        assert b'SOMESCP' == events[0].move_destination.strip()

    def test_flag_ta(self, capfd):
        """Test --acse-timeout flag."""
        events = []
        def handle_requested(event):
            events.append(event)
            time.sleep(0.1)

        def handle_move(event):
            events.append(event)
            yield 'localhost', 11113
            yield 0
            yield 0x0000, None

        def handle_abort(event):
            events.append(event)

        handlers = [
            (evt.EVT_C_MOVE, handle_move),
            (evt.EVT_ABORTED, handle_abort),
            (evt.EVT_REQUESTED, handle_requested),
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.requested_contexts = StoragePresentationContexts
        ae.supported_contexts = QueryRetrievePresentationContexts
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
        def handle_move(event):
            events.append(event)
            time.sleep(0.1)
            yield 'localhost', 11113
            yield 0
            yield 0x0000, None

        def handle_abort(event):
            events.append(event)

        handlers = [
            (evt.EVT_C_MOVE, handle_move),
            (evt.EVT_ABORTED, handle_abort),
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.requested_contexts = StoragePresentationContexts
        ae.supported_contexts = QueryRetrievePresentationContexts
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func(['-td', '0.05', '-d', '-k', 'PatientName='])
        p.wait()
        assert p.returncode == 0

        time.sleep(0.1)
        scp.shutdown()

        out, err = capfd.readouterr()
        assert "DIMSE timeout reached while waiting for message" in err
        assert events[0].event == evt.EVT_C_MOVE
        assert events[1].event == evt.EVT_ABORTED

    @pytest.mark.skip("Don't think this can be tested")
    def test_flag_tn(self, capfd):
        """Test --network-timeout flag."""
        pass

    def test_flag_max_pdu(self):
        """Test --max-pdu flag."""
        events = []
        def handle_move(event):
            events.append(event)
            yield 'localhost', 11113
            yield 0
            yield 0x0000, None

        def handle_release(event):
            events.append(event)

        handlers = [
            (evt.EVT_C_MOVE, handle_move),
            (evt.EVT_RELEASED, handle_release)
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.requested_contexts = StoragePresentationContexts
        ae.supported_contexts = QueryRetrievePresentationContexts
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func(['--max-pdu', '123456', '-k', 'PatientName='])
        p.wait()
        assert p.returncode == 0

        scp.shutdown()

        assert events[0].event == evt.EVT_C_MOVE
        assert events[1].event == evt.EVT_RELEASED
        requestor = events[1].assoc.requestor
        assert 123456 == requestor.maximum_length

    def test_flag_patient(self):
        """Test the -P flag."""
        events = []
        def handle_move(event):
            events.append(event)
            yield 'localhost', 11113
            yield 0
            yield 0x0000, None

        handlers = [
            (evt.EVT_C_MOVE, handle_move),
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.requested_contexts = StoragePresentationContexts
        ae.supported_contexts = QueryRetrievePresentationContexts
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func(['-P', '-k', 'PatientName='])
        p.wait()
        assert p.returncode == 0

        scp.shutdown()

        assert events[0].event == evt.EVT_C_MOVE
        cx = events[0].context
        assert cx.abstract_syntax == (
            PatientRootQueryRetrieveInformationModelMove
        )

    def test_flag_study(self):
        """Test the -S flag."""
        events = []
        def handle_move(event):
            events.append(event)
            yield 'localhost', 11113
            yield 0
            yield 0x0000, None

        handlers = [
            (evt.EVT_C_MOVE, handle_move),
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.requested_contexts = StoragePresentationContexts
        ae.supported_contexts = QueryRetrievePresentationContexts
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func(['-S', '-k', 'PatientName='])
        p.wait()
        assert p.returncode == 0

        scp.shutdown()

        assert events[0].event == evt.EVT_C_MOVE
        cx = events[0].context
        assert cx.abstract_syntax == StudyRootQueryRetrieveInformationModelMove

    def test_flag_patient_study(self):
        """Test the -O flag."""
        events = []
        def handle_move(event):
            events.append(event)
            yield 'localhost', 11113
            yield 0
            yield 0x0000, None

        handlers = [
            (evt.EVT_C_MOVE, handle_move),
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.requested_contexts = StoragePresentationContexts
        ae.supported_contexts = QueryRetrievePresentationContexts
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func(['-O', '-k', 'PatientName='])
        p.wait()
        assert p.returncode == 0

        scp.shutdown()

        assert events[0].event == evt.EVT_C_MOVE
        cx = events[0].context
        assert cx.abstract_syntax == (
            PatientStudyOnlyQueryRetrieveInformationModelMove
        )

    def test_flag_store(self):
        """Test the --store flag."""
        events = []
        def handle_move(event):
            events.append(event)
            yield 'localhost', 11113
            yield 1
            yield 0xFF00, self.response

        handlers = [
            (evt.EVT_C_MOVE, handle_move),
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.requested_contexts = StoragePresentationContexts
        ae.supported_contexts = QueryRetrievePresentationContexts
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func(['--store', '-k', 'PatientName='])
        p.wait()
        assert p.returncode == 0

        scp.shutdown()

        assert 'CT.1.2.3.4' in os.listdir()
        os.remove('CT.1.2.3.4')
        assert 'CT.1.2.3.4' not in os.listdir()

    def test_flag_store_port(self):
        """Test the --store-port flag."""
        events = []
        def handle_move(event):
            events.append(event)
            yield 'localhost', 11114
            yield 1
            yield 0xFF00, self.response

        handlers = [
            (evt.EVT_C_MOVE, handle_move),
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.requested_contexts = StoragePresentationContexts
        ae.supported_contexts = QueryRetrievePresentationContexts
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func(
            ['--store', '--store-port', '11114', '-k', 'PatientName=']
        )
        p.wait()
        assert p.returncode == 0

        scp.shutdown()

        assert 'CT.1.2.3.4' in os.listdir()
        os.remove('CT.1.2.3.4')
        assert 'CT.1.2.3.4' not in os.listdir()

    def test_flag_store_aet(self):
        """Test the --store-aet flag."""
        # Value not actually checked
        events = []
        def handle_move(event):
            events.append(event)
            yield 'localhost', 11113
            yield 1
            yield 0xFF00, self.response

        def handle_accepted(event):
            events.append(event)

        handlers = [
            (evt.EVT_ACCEPTED, handle_accepted),
            (evt.EVT_C_MOVE, handle_move),
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.requested_contexts = StoragePresentationContexts
        ae.supported_contexts = QueryRetrievePresentationContexts
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func(
            ['--store', '--store-aet', 'SOMESCP', '-k', 'PatientName=']
        )
        p.wait()
        assert p.returncode == 0

        scp.shutdown()

        assert 'CT.1.2.3.4' in os.listdir()
        os.remove('CT.1.2.3.4')
        assert 'CT.1.2.3.4' not in os.listdir()

    def test_flag_output(self):
        """Test the -od --output-directory flag."""
        def handle_move(event):
            yield 'localhost', 11113
            yield 1
            yield 0xFF00, self.response

        handlers = [
            (evt.EVT_C_MOVE, handle_move),
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.requested_contexts = StoragePresentationContexts
        ae.supported_contexts = QueryRetrievePresentationContexts
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assert 'test_dir' not in os.listdir()

        p = self.func(['--store', '-od', 'test_dir', '-k', 'PatientName='])
        p.wait()
        assert p.returncode == 0

        scp.shutdown()

        assert 'CT.1.2.3.4' in os.listdir('test_dir')
        shutil.rmtree('test_dir')
        assert 'test_dir' not in os.listdir()

    def test_flag_ignore(self):
        """Test the --ignore flag."""
        def handle_move(event):
            yield 'localhost', 11113
            yield 1
            yield 0xFF00, self.response

        handlers = [
            (evt.EVT_C_MOVE, handle_move),
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.requested_contexts = StoragePresentationContexts
        ae.supported_contexts = QueryRetrievePresentationContexts
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func(['--store', '--ignore', '-k', 'PatientName='])
        p.wait()
        assert p.returncode == 0

        scp.shutdown()

        assert 'CT.1.2.3.4' not in os.listdir()


class TestMoveSCU(MoveSCUBase):
    """Tests for movescu.py"""
    def setup(self):
        """Run prior to each test"""
        self.ae = None
        self.func = start_movescu

        self.response = ds = Dataset()
        ds.file_meta = Dataset()
        ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
        ds.SOPClassUID = CTImageStorage
        ds.SOPInstanceUID = '1.2.3.4'
        ds.PatientName = 'Citizen^Jan'


class TestMoveSCUCLI(MoveSCUBase):
    """Tests for movescu.py"""
    def setup(self):
        """Run prior to each test"""
        self.ae = None
        self.func = start_movescu_cli

        self.response = ds = Dataset()
        ds.file_meta = Dataset()
        ds.file_meta.TransferSyntaxUID = ImplicitVRLittleEndian
        ds.SOPClassUID = CTImageStorage
        ds.SOPInstanceUID = '1.2.3.4'
        ds.PatientName = 'Citizen^Jan'
