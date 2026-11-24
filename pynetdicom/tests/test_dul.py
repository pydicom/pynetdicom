"""DUL service testing"""

import logging
import os
import socket
import struct
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
from .encoded_pdu_items import a_associate_ac, a_associate_rq, a_release_rq
from .parrot import start_server, ThreadedParrot, ParrotRequest
from .utils import sleep, get_port

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
            self.scp = scp = start_server(commands, port=get_port())

            def handle(event):
                scp.step()
                scp.step()

            hh = [(evt.EVT_REQUESTED, handle)]

            ae = AE()
            ae.acse_timeout = 5
            ae.dimse_timeout = 5
            ae.network_timeout = 0.2
            ae.add_requested_context("1.2.840.10008.1.1")
            assoc = ae.associate("localhost", get_port(), evt_handlers=hh)
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
            self.scp = scp = start_server(commands, port=get_port())

            def handle(event):
                scp.step()  # recv A-ASSOCIATE-RQ
                scp.step()  # send A-ASSOCIATE-AC

            hh = [(evt.EVT_REQUESTED, handle)]

            ae = AE()
            ae.acse_timeout = 5
            ae.dimse_timeout = 5
            ae.network_timeout = 0.5
            ae.add_requested_context("1.2.840.10008.1.1")
            assoc = ae.associate("localhost", get_port(), evt_handlers=hh)
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
            self.scp = scp = start_server(commands, port=get_port())

            def handle(event):
                scp.step()
                scp.step()

            hh = [(evt.EVT_REQUESTED, handle)]

            ae = AE()
            ae.acse_timeout = 5
            ae.dimse_timeout = 5
            # ae.network_timeout = 0.5
            ae.add_requested_context("1.2.840.10008.1.1")
            assoc = ae.associate("localhost", get_port(), evt_handlers=hh)
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
            self.scp = scp = start_server(commands, port=get_port())

            def handle(event):
                scp.step()
                scp.step()

            hh = [(evt.EVT_REQUESTED, handle)]

            ae = AE()
            ae.acse_timeout = 5
            ae.dimse_timeout = 5
            ae.network_timeout = 5
            ae.add_requested_context("1.2.840.10008.1.1")
            assoc = ae.associate("localhost", get_port(), evt_handlers=hh)
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
        self.scp = scp = start_server(commands, port=get_port())

        def handle(event):
            scp.step()
            scp.step()

        hh = [(evt.EVT_REQUESTED, handle)]

        ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_requested_context("1.2.840.10008.1.1")
        assoc = ae.associate("localhost", get_port(), evt_handlers=hh)
        assert assoc.is_established

        scp.step()  # send bad PDU

        time.sleep(0.1)

        scp.step()  # receive abort
        scp.step()
        scp.shutdown()

        assert assoc.is_aborted

    @staticmethod
    def _p_data_tf(length):
        """Return a well-formed, non-final P-DATA-TF PDU with a PDU-length field
        of `length` bytes (a single PDV item carrying zero-filled fragment data).
        """
        pdv_length = length - 4
        # The PDV length counts the context ID and message control header bytes
        pdv = struct.pack(">LBB", pdv_length, 1, 0x00) + bytes(pdv_length - 2)
        return struct.pack(">BBL", 0x04, 0x00, length) + pdv

    def test_recv_pdu_exceeding_max_length_aborts(self, caplog):
        """Test a P-DATA-TF longer than our Maximum Length Received aborts.

        PS3.8 Annex D.1: the maximum length "shall never be exceeded by the PDU
        length values used in the PDU-length field of the P-DATA-TF PDUs
        received", otherwise it is a protocol error. Only the 6 byte header is
        sent, so the test also shows the body is never waited for.
        """
        with caplog.at_level(logging.ERROR, logger="pynetdicom"):
            commands = [
                ("recv", None),  # recv a-associate-rq
                ("send", a_associate_ac),
                ("send", struct.pack(">BBL", 0x04, 0x00, 16383)),  # 1 over the limit
                ("recv", None),  # recv a-abort
                ("exit", None),
            ]
            self.scp = scp = start_server(commands, port=get_port())

            def handle(event):
                scp.step()
                scp.step()

            hh = [(evt.EVT_REQUESTED, handle)]

            ae = AE()
            ae.acse_timeout = 5
            ae.dimse_timeout = 5
            ae.network_timeout = 5
            ae.add_requested_context("1.2.840.10008.1.1")
            assoc = ae.associate("localhost", get_port(), evt_handlers=hh)
            assert assoc.is_established

            scp.step()  # send the oversized PDU header

            while assoc.dul.is_alive():
                time.sleep(0.001)

            scp.step()  # receive abort
            scp.step()
            scp.shutdown()

            assert assoc.is_aborted
            assert (
                "The received P-DATA-TF PDU length (16383) exceeds the negotiated "
                "Maximum Length Received (16382)"
            ) in caplog.text

    def test_recv_pdu_at_max_length_accepted(self, caplog):
        """Test a P-DATA-TF of exactly the Maximum Length Received is conformant."""
        with caplog.at_level(logging.ERROR, logger="pynetdicom"):
            commands = [
                ("recv", None),  # recv a-associate-rq
                ("send", a_associate_ac),
                ("send", self._p_data_tf(16382)),
                ("recv", None),  # recv a-abort
                ("exit", None),
            ]
            self.scp = scp = start_server(commands, port=get_port())

            def handle(event):
                scp.step()
                scp.step()

            hh = [(evt.EVT_REQUESTED, handle)]

            ae = AE()
            ae.acse_timeout = 5
            ae.dimse_timeout = 5
            ae.network_timeout = 5
            ae.add_requested_context("1.2.840.10008.1.1")
            assoc = ae.associate("localhost", get_port(), evt_handlers=hh)
            assert assoc.is_established

            scp.step()  # send the PDU
            time.sleep(0.2)
            assert assoc.is_established
            assert "exceeds the negotiated" not in caplog.text

            assoc.abort()
            scp.step()  # receive abort
            scp.step()
            scp.shutdown()

    def test_recv_pdu_unlimited_max_length(self, caplog):
        """Test a Maximum Length Received of 0 (no limit) is not enforced."""
        with caplog.at_level(logging.ERROR, logger="pynetdicom"):
            commands = [
                ("recv", None),  # recv a-associate-rq
                ("send", a_associate_ac),
                ("send", self._p_data_tf(40000)),
                ("recv", None),  # recv a-abort
                ("exit", None),
            ]
            self.scp = scp = start_server(commands, port=get_port())

            def handle(event):
                scp.step()
                scp.step()

            hh = [(evt.EVT_REQUESTED, handle)]

            ae = AE()
            ae.acse_timeout = 5
            ae.dimse_timeout = 5
            ae.network_timeout = 5
            ae.add_requested_context("1.2.840.10008.1.1")
            assoc = ae.associate("localhost", get_port(), max_pdu=0, evt_handlers=hh)
            assert assoc.is_established

            scp.step()  # send the PDU
            time.sleep(0.2)
            assert assoc.is_established
            assert "exceeds the negotiated" not in caplog.text

            assoc.abort()
            scp.step()  # receive abort
            scp.step()
            scp.shutdown()

    def test_acceptor_aborts_on_pdu_exceeding_max_length(self):
        """Test an SCP aborts when the requestor exceeds the SCP's maximum."""
        self.ae = ae = AE()
        ae.maximum_pdu_size = 16382
        ae.network_timeout = 5
        ae.add_supported_context(Verification)
        port = get_port()
        ae.start_server(("localhost", port), block=False)

        with socket.create_connection(("localhost", port), timeout=5) as sock:
            sock.sendall(a_associate_rq)
            assert sock.recv(4096)[0] == 0x02  # A-ASSOCIATE-AC

            # Declare a PDU close to 4 GiB but send none of it: the SCP must
            # refuse it from the header alone rather than wait for the body
            sock.sendall(struct.pack(">BBL", 0x04, 0x00, 0xFFFFFFF0))
            reply = sock.recv(4096)

        assert reply[0] == 0x07  # A-ABORT

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
        self.scp = scp = start_server(commands, port=get_port())

        def handle(event):
            scp.step()
            scp.step()

        hh = [(evt.EVT_REQUESTED, handle)]

        ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_requested_context("1.2.840.10008.1.1")
        assoc = ae.associate("localhost", get_port(), evt_handlers=hh)

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

        scp = ae.start_server(("localhost", get_port()), block=False)

        ae.add_requested_context(Verification)
        assoc = ae.associate("localhost", get_port())

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

            scp = ae.start_server(("localhost", get_port()), block=False)

            ae.add_requested_context(Verification)
            assoc = ae.associate("localhost", get_port())

            assoc._kill = True
            dul = assoc.dul
            dul.socket = None
            dul._send(None)
            dul._kill_thread = True

            scp.shutdown()
            assert "Attempted to send data over closed connection" in caplog.text
