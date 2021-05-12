"""DUL service testing"""

import logging
import socket
import threading
import time

import pytest

from pynetdicom import AE, debug_logger, evt
from pynetdicom.dul import DULServiceProvider
from pynetdicom.pdu import (
    A_ASSOCIATE_RQ, A_ASSOCIATE_AC, A_ASSOCIATE_RJ,
    A_RELEASE_RQ, A_RELEASE_RP, P_DATA_TF, A_ABORT_RQ
)
from pynetdicom.pdu_primitives import A_ASSOCIATE, A_RELEASE, A_ABORT, P_DATA
from .encoded_pdu_items import a_associate_ac, a_release_rq
from .parrot import start_server, ThreadedParrot, ParrotRequest
from .utils import sleep


#debug_logger()


class DummyACSE:
    """Dummy ACSE class"""
    @staticmethod
    def debug_receive_associate_rq(): pass
    @staticmethod
    def debug_receive_associate_ac(): pass
    @staticmethod
    def debug_receive_associate_rj(): pass
    @staticmethod
    def debug_receive_data_tf(): pass
    @staticmethod
    def debug_receive_release_rq(): pass
    @staticmethod
    def debug_receive_release_rp(): pass
    @staticmethod
    def debug_receive_abort(): pass


class DummyAssociation:
    """Dummy Association class"""
    acse = DummyACSE()


class TestDUL:
    """Run tests on DUL service provider."""
    def setup(self):
        self.scp = None

    def teardown(self):
        if self.scp:
            self.scp.commands = [('exit', None)]
            self.scp.step
            self.scp.commands = []
            self.scp.shutdown()

        for thread in threading.enumerate():
            if isinstance(thread, ThreadedParrot):
                thread.shutdown()

    def test_primitive_to_event(self):
        """Test that parameter returns expected results"""
        dul = DULServiceProvider(DummyAssociation())
        p2e = dul._primitive_to_event

        primitive = A_ASSOCIATE()
        primitive.result = None
        assert p2e(primitive) == 'Evt1'
        primitive.result = 0
        assert p2e(primitive) == 'Evt7'
        primitive.result = 1
        assert p2e(primitive) == 'Evt8'

        primitive = A_RELEASE()
        primitive.result = None
        assert p2e(primitive) == 'Evt11'
        primitive.result = 'affirmative'
        assert p2e(primitive) == 'Evt14'

        primitive = A_ABORT()
        assert p2e(primitive) == 'Evt15'

        primitive = P_DATA()
        assert p2e(primitive) == 'Evt9'

        with pytest.raises(ValueError):
            p2e('TEST')

    def test_recv_failure_aborts(self):
        """Test connection close during PDU recv causes abort."""
        commands = [
            ('recv', None),  # recv a-associate-rq
            ('send', a_associate_ac),
            ('send', b"\x07\x00\x00\x00\x00\x04"),
            ('exit', None)
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
        ae.add_requested_context('1.2.840.10008.1.1')
        assoc = ae.associate('localhost', 11112, evt_handlers=hh)
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

    def test_recv_short_aborts(self):
        """Test receiving short PDU causes abort."""
        commands = [
            ('recv', None),  # recv a-associate-rq
            ('send', a_associate_ac),
            ('send', b"\x07\x00\x00\x00\x00\x04\x00\x00"),  # Send short PDU
            ('exit', None)
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
        ae.add_requested_context('1.2.840.10008.1.1')
        assoc = ae.associate('localhost', 11112, evt_handlers=hh)
        assert assoc.is_established

        scp.step()  # send short pdu
        # Need to wait for network timeout to expire
        timeout = 0
        while not assoc.is_aborted and timeout < 1:
            time.sleep(0.05)
            timeout += 0.05
        assert assoc.is_aborted

        scp.step()
        scp.shutdown()

    def test_recv_missing_data(self):
        """Test missing data when receiving."""
        commands = [
            ('recv', None),  # recv a-associate-rq
            ('send', a_associate_ac),
            ('send', b"\x07\x00\x00\x00\x00\x02\x00"),  # Send short PDU
            ('exit', None)
        ]
        self.scp = scp = start_server(commands)

        def handle(event):
            scp.step()
            scp.step()

        hh = [(evt.EVT_REQUESTED, handle)]

        def recv(nr_bytes):
            return assoc.dul.socket.socket.recv(6)

        ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 0.5
        ae.add_requested_context('1.2.840.10008.1.1')
        assoc = ae.associate('localhost', 11112, evt_handlers=hh)
        assert assoc.is_established
        assoc.dul.socket.recv = recv

        scp.step()  # send short pdu
        # Need to wait for network timeout to expire
        timeout = 0
        while not assoc.is_aborted and timeout < 1:
            time.sleep(0.05)
            timeout += 0.05
        assert assoc.is_aborted

        scp.step()
        scp.shutdown()

    def test_recv_bad_pdu_aborts(self):
        """Test receiving undecodable PDU causes abort."""
        commands = [
            ('recv', None),  # recv a-associate-rq
            ('send', a_associate_ac),
            ('send', b"\x07\x00\x00\x00\x00\x02\x00\x00"),
            ('recv', None),
            ('exit', None)
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
        ae.add_requested_context('1.2.840.10008.1.1')
        assoc = ae.associate('localhost', 11112, evt_handlers=hh)
        assert assoc.is_established

        scp.step()  # send bad PDU
        scp.step()  # receive abort
        assert assoc.is_aborted

        scp.step()
        scp.shutdown()

    def test_exception_in_reactor(self):
        """Test that an exception being raised in the DUL reactor kills the
        DUL and aborts the association.
        """
        commands = [
            ('recv', None),  # recv a-associate-rq
            ('send', a_associate_ac),
            ('send', a_release_rq),  # Trigger the exception
            ('recv', None),  # recv a-abort
            ('exit', None),
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
        ae.add_requested_context('1.2.840.10008.1.1')
        assoc = ae.associate('localhost', 11112, evt_handlers=hh)

        assert assoc.is_established

        def patch_read_pdu():
            raise NotImplementedError

        assoc.dul._read_pdu_data = patch_read_pdu

        scp.step()
        scp.step()
        assert assoc.is_aborted

        scp.step()
        scp.shutdown()
