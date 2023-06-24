"""DUL service testing"""

import logging
import socket
import threading
import time

import pytest

from pynetdicom import AE, debug_logger, evt
from pynetdicom.dul import DULServiceProvider
from pynetdicom.pdu import (
    A_ASSOCIATE_RQ,
    A_ASSOCIATE_AC,
    A_ASSOCIATE_RJ,
    A_RELEASE_RQ,
    A_RELEASE_RP,
    P_DATA_TF,
    A_ABORT_RQ,
)
from pynetdicom.pdu_primitives import A_ASSOCIATE, A_RELEASE, A_ABORT, P_DATA
from pynetdicom.sop_class import Verification
from .encoded_pdu_items import a_associate_ac, a_release_rq
from .parrot import start_server, ThreadedParrot, ParrotRequest
from .utils import sleep


# debug_logger()


class DummyACSE:
    """Dummy ACSE class"""

    @staticmethod
    def debug_receive_associate_rq():
        pass

    @staticmethod
    def debug_receive_associate_ac():
        pass

    @staticmethod
    def debug_receive_associate_rj():
        pass

    @staticmethod
    def debug_receive_data_tf():
        pass

    @staticmethod
    def debug_receive_release_rq():
        pass

    @staticmethod
    def debug_receive_release_rp():
        pass

    @staticmethod
    def debug_receive_abort():
        pass


class DummyAssociation:
    """Dummy Association class"""

    acse = DummyACSE()


class TestDUL:
    """Run tests on DUL service provider.

    DULServiceProvider._read_pdu_data() tests
    READ_PDU_EXC_A - test_transport.py::TestTLS::test_tls_yes_server_not_client
    READ_PDU_EXC_B - test_assoc.py::TestAssociation::test_unknown_abort_source
    READ_PDU_EXC_C - test_assoc.py::TestAssociation::test_bad_connection
    READ_PDU_EXC_D - test_dul.py::TestDUL::test_recv_short_aborts
    READ_PDU_EXC_E - test_dul.py::TestDUL::test_recv_missing_data
    READ_PDU_EXC_F - test_dul.py::TestDUL::test_recv_bad_pdu_aborts
    """

    def setup_method(self):
        self.scp = None
        self.ae = None

    def teardown_method(self):
        if self.scp:
            self.scp.commands = [("exit", None)]
            self.scp.step
            self.scp.commands = []
            self.scp.shutdown()

        if self.ae:
            self.ae.shutdown()

        for thread in threading.enumerate():
            if isinstance(thread, ThreadedParrot):
                thread.shutdown()

    def test_recv_primitive(self):
        """Test processing received primitives"""
        dul = DULServiceProvider(DummyAssociation())

        primitive = A_ASSOCIATE()
        primitive.result = None
        dul.to_provider_queue.put(primitive)
        dul._process_recv_primitive()
        assert dul.event_queue.get(False) == "Evt1"
        primitive.result = 0
        dul._process_recv_primitive()
        assert dul.event_queue.get(False) == "Evt7"
        primitive.result = 1
        dul._process_recv_primitive()
        assert dul.event_queue.get(False) == "Evt8"

        dul.to_provider_queue.get(False)

        primitive = A_RELEASE()
        primitive.result = None
        dul.to_provider_queue.put(primitive)
        dul._process_recv_primitive()
        assert dul.event_queue.get(False) == "Evt11"
        primitive.result = "affirmative"
        dul._process_recv_primitive()
        assert dul.event_queue.get(False) == "Evt14"

        dul.to_provider_queue.get(False)

        primitive = A_ABORT()
        dul.to_provider_queue.put(primitive)
        dul._process_recv_primitive()
        assert dul.event_queue.get(False) == "Evt15"

        dul.to_provider_queue.get(False)

        primitive = P_DATA()
        dul.to_provider_queue.put(primitive)
        dul._process_recv_primitive()
        assert dul.event_queue.get(False) == "Evt9"

        dul.to_provider_queue.get(False)

        msg = "Unknown primitive type 'str' received"
        with pytest.raises(ValueError, match=msg):
            dul.to_provider_queue.put("TEST")
            dul._process_recv_primitive()

    def test_recv_failure_aborts(self, caplog):
        """Test connection close during PDU recv causes abort."""
        with caplog.at_level(logging.ERROR, logger="pynetdicom"):
            commands = [
                ("recv", None),  # recv a-associate-rq
                ("send", a_associate_ac),
                ("send", b"\x07\x00\x00\x00\x00\x04"),
                ("exit", None),
            ]
            self.scp = scp = start_server(commands)

            def handle(event):
                scp.step()
                scp.step()

            hh = [(evt.EVT_REQUESTED, handle)]

            ae = AE()
            ae.acse_timeout = 5
            ae.dimse_timeout = 5
            ae.network_timeout = 0.2
            ae.add_requested_context("1.2.840.10008.1.1")
            assoc = ae.associate("localhost", 11112, evt_handlers=hh)
            assert assoc.is_established

            scp.step()  # send short pdu
            scp.step()  # close connection
            scp.shutdown()

            # Need to wait for network timeout to expire
            timeout = 0
            while not assoc.is_aborted and timeout < 1:
                time.sleep(0.05)
                timeout += 0.05
            assert assoc.is_aborted
            assert (
                "The received PDU is shorter than expected (6 of 10 bytes received)"
            ) in caplog.text

    def test_recv_short_aborts(self, caplog):
        """Test receiving short PDU causes abort."""
        with caplog.at_level(logging.ERROR, logger="pynetdicom"):
            commands = [
                ("recv", None),  # recv a-associate-rq
                ("send", a_associate_ac),
                ("send", b"\x07\x00\x00\x00\x00\x04"),  # Send first 6
                ("send", b"\x00\x00"),  # Send short remainder
                ("exit", None),
            ]
            self.scp = scp = start_server(commands)

            def handle(event):
                scp.step()  # recv A-ASSOCIATE-RQ
                scp.step()  # send A-ASSOCIATE-AC

            hh = [(evt.EVT_REQUESTED, handle)]

            ae = AE()
            ae.acse_timeout = 5
            ae.dimse_timeout = 5
            ae.network_timeout = 0.5
            ae.add_requested_context("1.2.840.10008.1.1")
            assoc = ae.associate("localhost", 11112, evt_handlers=hh)
            assert assoc.is_established

            scp.step()  # send short pdu
            time.sleep(0.1)
            assoc.dul.socket.socket.close()
            # Need to wait for network timeout to expire
            timeout = 0
            while not assoc.is_aborted and timeout < 1:
                time.sleep(0.05)
                timeout += 0.05
            scp.step()
            scp.step()  # exit
            assert assoc.is_aborted
            scp.shutdown()

            assert "Connection closed before the entire PDU was received" in caplog.text

    def test_recv_missing_data(self, caplog):
        """Test missing data when receiving."""
        with caplog.at_level(logging.ERROR, logger="pynetdicom"):
            commands = [
                ("recv", None),  # recv a-associate-rq
                ("send", a_associate_ac),
                ("send", b"\x07\x00\x00\x00\x00\x02\x00"),  # Send short PDU
                ("exit", None),
            ]
            self.scp = scp = start_server(commands)

            def handle(event):
                scp.step()
                scp.step()

            hh = [(evt.EVT_REQUESTED, handle)]

            ae = AE()
            ae.acse_timeout = 5
            ae.dimse_timeout = 5
            # ae.network_timeout = 0.5
            ae.add_requested_context("1.2.840.10008.1.1")
            assoc = ae.associate("localhost", 11112, evt_handlers=hh)
            assert assoc.is_established

            scp.step()  # send short pdu

            scp.step()
            scp.shutdown()
            assert assoc.is_aborted
            assert (
                "The received PDU is shorter than expected (7 of 8 bytes received)"
            ) in caplog.text

    def test_recv_bad_pdu_aborts(self, caplog):
        """Test receiving undecodable PDU causes abort."""
        with caplog.at_level(logging.ERROR, logger="pynetdicom"):
            commands = [
                ("recv", None),  # recv a-associate-rq
                ("send", a_associate_ac),
                ("send", b"\x07\x00\x00\x00\x00\x02\x00\x00"),
                ("recv", None),
                ("exit", None),
            ]
            self.scp = scp = start_server(commands)

            def handle(event):
                scp.step()
                scp.step()

            hh = [(evt.EVT_REQUESTED, handle)]

            ae = AE()
            ae.acse_timeout = 5
            ae.dimse_timeout = 5
            ae.network_timeout = 5
            ae.add_requested_context("1.2.840.10008.1.1")
            assoc = ae.associate("localhost", 11112, evt_handlers=hh)
            assert assoc.is_established

            scp.step()  # send bad PDU

            while assoc.dul.is_alive():
                time.sleep(0.001)

            scp.step()  # receive abort
            scp.step()
            scp.shutdown()

            assert assoc.is_aborted
            assert "Unable to decode the received PDU data" in caplog.text

    def test_unknown_pdu_aborts(self):
        commands = [
            ("recv", None),  # recv a-associate-rq
            ("send", a_associate_ac),
            ("send", b"\x53\x00\x00\x00\x00\x02"),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = start_server(commands)

        def handle(event):
            scp.step()
            scp.step()

        hh = [(evt.EVT_REQUESTED, handle)]

        ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_requested_context("1.2.840.10008.1.1")
        assoc = ae.associate("localhost", 11112, evt_handlers=hh)
        assert assoc.is_established

        scp.step()  # send bad PDU

        time.sleep(0.1)

        scp.step()  # receive abort
        scp.step()
        scp.shutdown()

        assert assoc.is_aborted

    def test_exception_in_reactor(self):
        """Test that an exception being raised in the DUL reactor kills the
        DUL and aborts the association.
        """
        commands = [
            ("recv", None),  # recv a-associate-rq
            ("send", a_associate_ac),
            ("send", a_release_rq),  # Trigger the exception
            ("recv", None),  # recv a-abort
            ("exit", None),
        ]
        self.scp = scp = start_server(commands)

        def handle(event):
            scp.step()
            scp.step()

        hh = [(evt.EVT_REQUESTED, handle)]

        ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_requested_context("1.2.840.10008.1.1")
        assoc = ae.associate("localhost", 11112, evt_handlers=hh)

        assert assoc.is_established

        def patch_read_pdu():
            raise NotImplementedError

        assoc.dul._read_pdu_data = patch_read_pdu

        scp.step()

        while assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()

        assert assoc.is_aborted

        scp.step()
        scp.shutdown()

    def test_stop_dul_sta1(self):
        """Test that stop_dul() returns True when in Sta1"""
        dul = DULServiceProvider(DummyAssociation())
        assert dul.state_machine.current_state == "Sta1"
        assert dul.stop_dul()

    def test_stop_dul(self):
        self.ae = ae = AE()
        ae.network_timeout = 5
        ae.dimse_timeout = 5
        ae.acse_timeout = 5
        ae.add_supported_context(Verification)

        scp = ae.start_server(("localhost", 11112), block=False)

        ae.add_requested_context(Verification)
        assoc = ae.associate("localhost", 11112)

        dul = assoc.dul

        dul.state_machine.current_state = "Sta1"
        dul.stop_dul()

        assoc.release()

        scp.shutdown()

    def test_send_over_closed(self, caplog):
        """Test attempting to send data over closed socket logs warning."""
        with caplog.at_level(logging.WARNING, logger="pynetdicom"):
            self.ae = ae = AE()
            ae.network_timeout = 5
            ae.dimse_timeout = 5
            ae.acse_timeout = 5
            ae.add_supported_context(Verification)

            scp = ae.start_server(("localhost", 11112), block=False)

            ae.add_requested_context(Verification)
            assoc = ae.associate("localhost", 11112)

            assoc._kill = True
            dul = assoc.dul
            dul.socket = None
            dul._send(None)
            dul._kill_thread = True

            scp.shutdown()
            assert "Attempted to send data over closed connection" in caplog.text
