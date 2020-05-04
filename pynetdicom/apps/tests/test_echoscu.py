"""Unit tests for echoscu.py"""

import logging
import os
import subprocess
import sys
import time

import pytest

from pydicom.uid import (
    ExplicitVRLittleEndian, ImplicitVRLittleEndian,
    DeflatedExplicitVRLittleEndian, ExplicitVRBigEndian
)

from pynetdicom import AE, evt, debug_logger, DEFAULT_TRANSFER_SYNTAXES
from pynetdicom.sop_class import VerificationSOPClass, CTImageStorage


#debug_logger()


APP_DIR = os.path.join(os.path.dirname(__file__), '../')
APP_FILE = os.path.join(APP_DIR, 'echoscu', 'echoscu.py')


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


def start_echoscu(args):
    """Start the echoscu.py app and return the process."""
    pargs = [which('python'), APP_FILE, 'localhost', '11112'] + [*args]
    return subprocess.Popen(pargs)


def start_echoscu_cli(args):
    """Start the echoscu app using CLI and return the process."""
    pargs = [
        which('python'), '-m', 'pynetdicom', 'echoscu', 'localhost', '11112'
    ] + [*args]
    return subprocess.Popen(pargs)


class EchoSCUBase(object):
    """Tests for echoscu.py"""
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

        def handle_echo(event):
            events.append(event)
            return 0x0000

        def handle_release(event):
            events.append(event)

        handlers = [
            (evt.EVT_C_ECHO, handle_echo),
            (evt.EVT_RELEASED, handle_release)
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func([])
        p.wait()
        assert p.returncode == 0

        scp.shutdown()

        assert events[0].event == evt.EVT_C_ECHO
        assert events[1].event == evt.EVT_RELEASED
        requestor = events[1].assoc.requestor
        assert b'ECHOSCU         ' == requestor.ae_title
        assert 16382 == requestor.maximum_length
        assert b'ANY-SCP         ' == requestor.primitive.called_ae_title
        assert [] == requestor.extended_negotiation
        assert (1, 1) == requestor.asynchronous_operations
        assert {} == requestor.sop_class_common_extended
        assert {} == requestor.sop_class_extended
        assert requestor.user_identity == None
        cxs = requestor.primitive.presentation_context_definition_list
        assert len(cxs) == 1
        assert cxs[0].abstract_syntax == VerificationSOPClass
        assert cxs[0].transfer_syntax == [
            ExplicitVRLittleEndian,
            ImplicitVRLittleEndian,
            DeflatedExplicitVRLittleEndian,
            ExplicitVRBigEndian
        ]

    def test_no_peer(self, capfd):
        """Test trying to connect to non-existent host."""
        p = self.func([])
        p.wait()
        assert p.returncode == 1

        out, err = capfd.readouterr()
        assert "Association request failed: unable to connect to remote" in err
        assert "TCP Initialisation Error: Connection refused" in err
        assert "Association Aborted" in err

    def test_flag_version(self, capfd):
        """Test --version flag."""
        p = self.func(['--version'])
        p.wait()
        assert p.returncode == 0

        out, err = capfd.readouterr()
        assert 'echoscu.py v' in out

    def test_flag_quiet(self, capfd):
        """Test --quiet flag."""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(CTImageStorage)
        scp = ae.start_server(('', 11112), block=False)

        p = self.func(['-q'])
        p.wait()
        assert p.returncode == 1

        out, err = capfd.readouterr()
        assert out == err == ''

        scp.shutdown()

    def test_flag_verbose(self, capfd):
        """Test --verbose flag."""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)

        p = self.func(['-v'])
        p.wait()
        assert p.returncode == 0

        out, err = capfd.readouterr()
        assert "Requesting Association" in err
        assert "Association Accepted" in err
        assert "Sending Echo Request" in err
        assert "Received Echo Response" in err
        assert "Releasing Association" in err
        assert "Accept Parameters" not in err

        scp.shutdown()

    def test_flag_debug(self, capfd):
        """Test --debug flag."""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)

        p = self.func(['-d'])
        p.wait()
        assert p.returncode == 0

        out, err = capfd.readouterr()
        assert "Releasing Association" in err
        assert "Accept Parameters" in err

        scp.shutdown()

    def test_flag_log_collision(self):
        """Test error with -q -v and -d flag."""
        p = self.func(['-q', '-v'])
        p.wait()
        assert p.returncode != 0

    @pytest.mark.skip("No way to test comprehensively")
    def test_flag_log_level(self):
        """Test --log-level flag."""
        pass

    def test_flag_aet(self):
        """Test --calling-aet flag."""
        events = []

        def handle_echo(event):
            events.append(event)
            return 0x0000

        def handle_release(event):
            events.append(event)

        handlers = [
            (evt.EVT_C_ECHO, handle_echo),
            (evt.EVT_RELEASED, handle_release)
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func(['-aet', 'MYSCU'])
        p.wait()
        assert p.returncode == 0

        scp.shutdown()

        assert events[0].event == evt.EVT_C_ECHO
        assert events[1].event == evt.EVT_RELEASED
        requestor = events[1].assoc.requestor
        assert b'MYSCU           ' == requestor.ae_title

    def test_flag_aec(self):
        """Test --called-aet flag."""
        events = []

        def handle_echo(event):
            events.append(event)
            return 0x0000

        def handle_release(event):
            events.append(event)

        handlers = [
            (evt.EVT_C_ECHO, handle_echo),
            (evt.EVT_RELEASED, handle_release)
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func(['-aec', 'YOURSCP'])
        p.wait()
        assert p.returncode == 0

        scp.shutdown()

        assert events[0].event == evt.EVT_C_ECHO
        assert events[1].event == evt.EVT_RELEASED
        requestor = events[1].assoc.requestor
        assert b'YOURSCP         ' == requestor.primitive.called_ae_title

    def test_flag_ta(self, capfd):
        """Test --acse-timeout flag."""
        events = []

        def handle_requested(event):
            events.append(event)
            time.sleep(0.1)

        def handle_echo(event):
            events.append(event)
            return 0x0000

        def handle_abort(event):
            events.append(event)

        handlers = [
            (evt.EVT_C_ECHO, handle_echo),
            (evt.EVT_ABORTED, handle_abort),
            (evt.EVT_REQUESTED, handle_requested),
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func(['-ta', '0.05', '-d'])
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

        def handle_echo(event):
            events.append(event)
            time.sleep(0.1)
            return 0x0000

        def handle_abort(event):
            events.append(event)

        handlers = [
            (evt.EVT_C_ECHO, handle_echo),
            (evt.EVT_ABORTED, handle_abort),
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func(['-td', '0.05', '-d'])
        p.wait()
        assert p.returncode == 0

        time.sleep(0.1)

        scp.shutdown()

        out, err = capfd.readouterr()
        assert "DIMSE timeout reached while waiting for message" in err
        assert events[0].event == evt.EVT_C_ECHO
        assert events[1].event == evt.EVT_ABORTED

    @pytest.mark.skip("Don't think this can be tested")
    def test_flag_tn(self, capfd):
        """Test --network-timeout flag."""
        pass

    def test_flag_max_pdu(self):
        """Test --max-pdu flag."""
        events = []

        def handle_echo(event):
            events.append(event)
            return 0x0000

        def handle_release(event):
            events.append(event)

        handlers = [
            (evt.EVT_C_ECHO, handle_echo),
            (evt.EVT_RELEASED, handle_release)
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func(['--max-pdu', '123456'])
        p.wait()
        assert p.returncode == 0

        scp.shutdown()

        assert events[0].event == evt.EVT_C_ECHO
        assert events[1].event == evt.EVT_RELEASED
        requestor = events[1].assoc.requestor
        assert 123456 == requestor.maximum_length

    def test_flag_xe(self):
        """Test --request-little flag."""
        events = []

        def handle_echo(event):
            events.append(event)
            return 0x0000

        def handle_release(event):
            events.append(event)

        handlers = [
            (evt.EVT_C_ECHO, handle_echo),
            (evt.EVT_RELEASED, handle_release)
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func(['-xe'])
        p.wait()
        assert p.returncode == 0

        scp.shutdown()

        assert events[0].event == evt.EVT_C_ECHO
        assert events[1].event == evt.EVT_RELEASED
        requestor = events[1].assoc.requestor
        cxs = requestor.primitive.presentation_context_definition_list
        assert len(cxs) == 1
        assert cxs[0].abstract_syntax == VerificationSOPClass
        assert cxs[0].transfer_syntax == [ExplicitVRLittleEndian]

    def test_flag_xb(self):
        """Test --request-big flag."""
        events = []

        def handle_echo(event):
            events.append(event)
            return 0x0000

        def handle_release(event):
            events.append(event)

        handlers = [
            (evt.EVT_C_ECHO, handle_echo),
            (evt.EVT_RELEASED, handle_release)
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func(['-xb'])
        p.wait()
        assert p.returncode == 0

        scp.shutdown()

        assert events[0].event == evt.EVT_C_ECHO
        assert events[1].event == evt.EVT_RELEASED
        requestor = events[1].assoc.requestor
        cxs = requestor.primitive.presentation_context_definition_list
        assert len(cxs) == 1
        assert cxs[0].abstract_syntax == VerificationSOPClass
        assert cxs[0].transfer_syntax == [ExplicitVRBigEndian]

    def test_flag_xi(self):
        """Test --request-implicit flag."""
        events = []

        def handle_echo(event):
            events.append(event)
            return 0x0000

        def handle_release(event):
            events.append(event)

        handlers = [
            (evt.EVT_C_ECHO, handle_echo),
            (evt.EVT_RELEASED, handle_release)
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func(['-xi'])
        p.wait()
        assert p.returncode == 0

        scp.shutdown()

        assert events[0].event == evt.EVT_C_ECHO
        assert events[1].event == evt.EVT_RELEASED
        requestor = events[1].assoc.requestor
        cxs = requestor.primitive.presentation_context_definition_list
        assert len(cxs) == 1
        assert cxs[0].abstract_syntax == VerificationSOPClass
        assert cxs[0].transfer_syntax == [ImplicitVRLittleEndian]

    def test_flag_repeat(self):
        """Test --repeat flag."""
        events = []

        def handle_echo(event):
            events.append(event)
            return 0x0000

        def handle_release(event):
            events.append(event)

        handlers = [
            (evt.EVT_C_ECHO, handle_echo),
            (evt.EVT_RELEASED, handle_release)
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func(['--repeat', '3'])
        p.wait()
        assert p.returncode == 0

        scp.shutdown()

        assert events[0].event == evt.EVT_C_ECHO
        assert events[1].event == evt.EVT_C_ECHO
        assert events[2].event == evt.EVT_C_ECHO
        assert events[3].event == evt.EVT_RELEASED

    def test_flag_abort(self):
        """Test --abort flag."""
        events = []

        def handle_echo(event):
            events.append(event)
            return 0x0000

        def handle_release(event):
            events.append(event)

        def handle_abort(event):
            events.append(event)

        handlers = [
            (evt.EVT_C_ECHO, handle_echo),
            (evt.EVT_RELEASED, handle_release),
            (evt.EVT_ABORTED, handle_abort),
        ]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        p = self.func(['--abort'])
        p.wait()
        assert p.returncode == 0

        scp.shutdown()

        assert events[0].event == evt.EVT_C_ECHO
        assert events[1].event == evt.EVT_ABORTED


class TestEchoSCU(EchoSCUBase):
    """Tests for echoscu.py"""
    def setup(self):
        """Run prior to each test"""
        self.ae = None
        self.func = start_echoscu


class TestEchoSCUCLI(EchoSCUBase):
    """Tests for echoscu using CLI"""
    def setup(self):
        """Run prior to each test"""
        self.ae = None
        self.func = start_echoscu_cli
