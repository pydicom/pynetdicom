"""Unit tests for storescu.py"""

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
    AllStoragePresentationContexts, ALL_TRANSFER_SYNTAXES
)
from pynetdicom.sop_class import (
    VerificationSOPClass, CTImageStorage, MRImageStorage
)


#debug_logger()


APP_DIR = os.path.join(os.path.dirname(__file__), '../')
APP_FILE = os.path.join(APP_DIR, 'storescu', 'storescu.py')
DATA_DIR = os.path.join(APP_DIR, '../', 'tests', 'dicom_files')
DATASET_FILE = os.path.join(DATA_DIR, 'CTImageStorage.dcm')
BE_DATASET_FILE = os.path.join(
    DATA_DIR, 'MRImageStorage_ExplicitVRBigEndian.dcm'
)
LIB_DIR = os.path.join(APP_DIR, '../')


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


def start_storescu(args):
    """Start the storescu.py app and return the process."""
    pargs = [which('python'), APP_FILE, 'localhost', '11112'] + [*args]
    return subprocess.Popen(pargs)


def start_storescu_cli(args):
    """Start the storescu app using CLI and return the process."""
    pargs = [
        which('python'), '-m', 'pynetdicom', 'storescu', 'localhost', '11112'
    ] + [*args]
    return subprocess.Popen(pargs)


class StoreSCUBase(object):
    """Tests for storescu.py"""
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

        def handle_store(event):
            events.append(event)
            return 0x0000

        def handle_release(event):
            events.append(event)

        handlers = [
            (evt.EVT_C_STORE, handle_store),
            (evt.EVT_RELEASED, handle_release)
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func([DATASET_FILE])
        p.wait()
        assert p.returncode == 0

        scp.shutdown()

        assert events[0].event == evt.EVT_C_STORE
        assert events[0].dataset.PatientName == "CompressedSamples^CT1"
        assert events[1].event == evt.EVT_RELEASED
        requestor = events[1].assoc.requestor
        assert b'STORESCU        ' == requestor.ae_title
        assert 16382 == requestor.maximum_length
        assert b'ANY-SCP         ' == requestor.primitive.called_ae_title
        assert [] == requestor.extended_negotiation
        assert (1, 1) == requestor.asynchronous_operations
        assert {} == requestor.sop_class_common_extended
        assert {} == requestor.sop_class_extended
        assert requestor.user_identity == None
        cxs = requestor.primitive.presentation_context_definition_list
        assert len(cxs) == 128
        cxs = {cx.abstract_syntax: cx for cx in cxs}
        assert CTImageStorage in cxs
        assert cxs[CTImageStorage].transfer_syntax == [
            ExplicitVRLittleEndian,
            ImplicitVRLittleEndian,
            DeflatedExplicitVRLittleEndian,
            ExplicitVRBigEndian
        ]

    def test_no_peer(self, capfd):
        """Test trying to connect to non-existent host."""
        p = self.func([DATASET_FILE])
        p.wait()
        assert p.returncode == 1

        out, err = capfd.readouterr()
        assert "Association request failed: unable to connect to remote" in err
        assert "TCP Initialisation Error: Connection refused" in err
        assert "Association Aborted" in err

    def test_flag_version(self, capfd):
        """Test --version flag."""
        p = self.func([DATASET_FILE, '--version'])
        p.wait()
        assert p.returncode == 0

        out, err = capfd.readouterr()
        assert 'storescu.py v' in out

    def test_flag_quiet(self, capfd):
        """Test --quiet flag."""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)

        p = self.func([DATASET_FILE, '-q'])
        p.wait()
        assert p.returncode == 1

        out, err = capfd.readouterr()
        assert out == err == ''

        scp.shutdown()

    def test_flag_verbose(self, capfd):
        """Test --verbose flag."""
        def handle_store(event):
            return 0x0000

        handlers = [
            (evt.EVT_C_STORE, handle_store),
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func([DATASET_FILE, '-v'])
        p.wait()
        assert p.returncode == 0

        out, err = capfd.readouterr()
        assert "Requesting Association" in err
        assert "Association Accepted" in err
        assert "Sending Store Request" in err
        assert "Received Store Response" in err
        assert "Releasing Association" in err
        assert "Accept Parameters" not in err

        scp.shutdown()

    def test_flag_debug(self, capfd):
        """Test --debug flag."""
        def handle_store(event):
            return 0x0000

        handlers = [
            (evt.EVT_C_STORE, handle_store),
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func([DATASET_FILE, '-d'])
        p.wait()
        assert p.returncode == 0

        out, err = capfd.readouterr()
        assert "Releasing Association" in err
        assert "Accept Parameters" in err

        scp.shutdown()

    def test_flag_log_collision(self):
        """Test error with -q -v and -d flag."""
        p = self.func([DATASET_FILE, '-v', '-d'])
        p.wait()
        assert p.returncode != 0

    @pytest.mark.skip("No way to test comprehensively")
    def test_flag_log_level(self):
        """Test --log-level flag."""
        pass

    def test_flag_aet(self):
        """Test --calling-aet flag."""
        events = []
        def handle_store(event):
            events.append(event)
            return 0x0000

        handlers = [
            (evt.EVT_C_STORE, handle_store),
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func([DATASET_FILE, '-aet', 'MYSCU'])
        p.wait()
        assert p.returncode == 0

        scp.shutdown()

        assert events[0].event == evt.EVT_C_STORE
        requestor = events[0].assoc.requestor
        assert b'MYSCU           ' == requestor.ae_title

    def test_flag_aec(self):
        """Test --called-aet flag."""
        events = []
        def handle_store(event):
            events.append(event)
            return 0x0000

        handlers = [
            (evt.EVT_C_STORE, handle_store),
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func([DATASET_FILE, '-aec', 'YOURSCP'])
        p.wait()
        assert p.returncode == 0

        scp.shutdown()

        assert events[0].event == evt.EVT_C_STORE
        requestor = events[0].assoc.requestor
        assert b'YOURSCP         ' == requestor.primitive.called_ae_title

    def test_flag_ta(self, capfd):
        """Test --acse-timeout flag."""
        events = []

        def handle_requested(event):
            events.append(event)
            time.sleep(0.1)

        def handle_store(event):
            events.append(event)
            return 0x0000

        def handle_abort(event):
            events.append(event)

        handlers = [
            (evt.EVT_C_STORE, handle_store),
            (evt.EVT_ABORTED, handle_abort),
            (evt.EVT_REQUESTED, handle_requested),
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func([DATASET_FILE, '-ta', '0.05', '-d'])
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

        def handle_store(event):
            events.append(event)
            time.sleep(0.1)
            return 0x0000

        def handle_abort(event):
            events.append(event)

        handlers = [
            (evt.EVT_C_STORE, handle_store),
            (evt.EVT_ABORTED, handle_abort),
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func([DATASET_FILE, '-td', '0.05', '-d'])
        p.wait()
        assert p.returncode == 0

        time.sleep(0.1)

        scp.shutdown()

        out, err = capfd.readouterr()
        assert "DIMSE timeout reached while waiting for message" in err
        assert events[0].event == evt.EVT_C_STORE
        assert events[1].event == evt.EVT_ABORTED

    @pytest.mark.skip("Don't think this can be tested")
    def test_flag_tn(self, capfd):
        """Test --network-timeout flag."""
        pass

    def test_flag_max_pdu(self):
        """Test --max-pdu flag."""
        events = []

        def handle_store(event):
            events.append(event)
            return 0x0000

        def handle_release(event):
            events.append(event)

        handlers = [
            (evt.EVT_C_STORE, handle_store),
            (evt.EVT_RELEASED, handle_release)
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func([DATASET_FILE, '--max-pdu', '123456'])
        p.wait()
        assert p.returncode == 0

        scp.shutdown()

        assert events[0].event == evt.EVT_C_STORE
        assert events[1].event == evt.EVT_RELEASED
        requestor = events[1].assoc.requestor
        assert 123456 == requestor.maximum_length

    def test_flag_xe(self):
        """Test --request-little flag."""
        events = []

        def handle_store(event):
            events.append(event)
            return 0x0000

        def handle_release(event):
            events.append(event)

        handlers = [
            (evt.EVT_C_STORE, handle_store),
            (evt.EVT_RELEASED, handle_release)
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func([DATASET_FILE, '-xe'])
        p.wait()
        assert p.returncode == 0

        scp.shutdown()

        assert events[0].event == evt.EVT_C_STORE
        assert events[0].dataset.PatientName == 'CompressedSamples^CT1'
        assert events[1].event == evt.EVT_RELEASED
        requestor = events[1].assoc.requestor
        cxs = requestor.primitive.presentation_context_definition_list
        assert len(cxs) == 128
        cxs = {cx.abstract_syntax: cx for cx in cxs}
        assert CTImageStorage in cxs
        assert cxs[CTImageStorage].transfer_syntax == [ExplicitVRLittleEndian]

    def test_flag_xb(self):
        """Test --request-big flag."""
        events = []

        def handle_store(event):
            events.append(event)
            return 0x0000

        def handle_release(event):
            events.append(event)

        handlers = [
            (evt.EVT_C_STORE, handle_store),
            (evt.EVT_RELEASED, handle_release)
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(MRImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func([BE_DATASET_FILE, '-xb'])
        p.wait()
        assert p.returncode == 0

        scp.shutdown()

        assert events[0].event == evt.EVT_C_STORE
        assert events[0].dataset.PatientName == 'CompressedSamples^MR1'
        assert events[1].event == evt.EVT_RELEASED
        requestor = events[1].assoc.requestor
        cxs = requestor.primitive.presentation_context_definition_list
        cxs = requestor.primitive.presentation_context_definition_list
        assert len(cxs) == 128
        cxs = {cx.abstract_syntax: cx for cx in cxs}
        assert CTImageStorage in cxs
        assert cxs[CTImageStorage].transfer_syntax == [ExplicitVRBigEndian]

    def test_flag_xi(self):
        """Test --request-implicit flag."""
        events = []

        def handle_store(event):
            events.append(event)
            return 0x0000

        def handle_release(event):
            events.append(event)

        handlers = [
            (evt.EVT_C_STORE, handle_store),
            (evt.EVT_RELEASED, handle_release)
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func([DATASET_FILE, '-xi'])
        p.wait()
        assert p.returncode == 0

        scp.shutdown()

        assert events[0].event == evt.EVT_C_STORE
        assert events[0].dataset.PatientName == 'CompressedSamples^CT1'
        assert events[1].event == evt.EVT_RELEASED
        requestor = events[1].assoc.requestor
        cxs = requestor.primitive.presentation_context_definition_list
        cxs = requestor.primitive.presentation_context_definition_list
        assert len(cxs) == 128
        cxs = {cx.abstract_syntax: cx for cx in cxs}
        assert CTImageStorage in cxs
        assert cxs[CTImageStorage].transfer_syntax == [ImplicitVRLittleEndian]

    def test_flag_required_cx(self):
        """Test --required-contexts flag."""
        events = []

        def handle_store(event):
            events.append(event)
            return 0x0000

        def handle_release(event):
            events.append(event)

        handlers = [
            (evt.EVT_C_STORE, handle_store),
            (evt.EVT_RELEASED, handle_release)
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func([DATASET_FILE, '-cx'])
        p.wait()
        assert p.returncode == 0

        scp.shutdown()

        ds = dcmread(DATASET_FILE)
        tsyntax = ds.file_meta.TransferSyntaxUID
        requestor = events[0].assoc.requestor
        cxs = requestor.primitive.presentation_context_definition_list
        assert len(cxs) == 1
        assert cxs[0].abstract_syntax == CTImageStorage
        assert cxs[0].transfer_syntax == [tsyntax]

    def test_bad_input(self, capfd):
        """Test being unable to read the input file."""
        p = self.func(['no-such-file.dcm', '-d'])
        p.wait()
        assert p.returncode == 0

        out, err = capfd.readouterr()
        assert 'No suitable DICOM files found' in err
        assert 'Cannot access path: no-such-file.dcm' in err

    def test_recurse(self, capfd):
        """Test the --recurse flag."""
        events = []
        def handle_store(event):
            events.append(event)
            return 0x0000

        handlers = [
            (evt.EVT_C_STORE, handle_store),
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        for cx in AllStoragePresentationContexts:
            ae.add_supported_context(cx.abstract_syntax, ALL_TRANSFER_SYNTAXES)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func([LIB_DIR, '--recurse', '-cx'])
        p.wait()
        assert p.returncode == 0

        scp.shutdown()

        assert len(events) == 5


class TestStoreSCU(StoreSCUBase):
    """Tests for storescu.py"""
    def setup(self):
        """Run prior to each test"""
        self.ae = None
        self.func = start_storescu


class TestStoreSCUCLI(StoreSCUBase):
    """Tests for storescu using CLI"""
    def setup(self):
        """Run prior to each test"""
        self.ae = None
        self.func = start_storescu_cli
