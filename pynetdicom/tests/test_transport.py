"""Unit tests for the transport module."""

from datetime import datetime
import logging
try:
    import queue
except ImportError:
    import Queue as queue
import os
import select
import socket
import ssl
from struct import pack
import sys
import threading
import time

import pytest

from pynetdicom import AE, evt
from pynetdicom.association import Association
from pynetdicom.events import Event
from pynetdicom._globals import MODE_REQUESTOR, MODE_ACCEPTOR
from pynetdicom.transport import (
    AssociationSocket, AssociationServer, ThreadedAssociationServer
)
from pynetdicom.sop_class import VerificationSOPClass


# This is the directory that contains test data
TEST_ROOT = os.path.abspath(os.path.dirname(__file__))
CERT_DIR = os.path.join(TEST_ROOT, 'cert_files')

# SSL Testing
SERVER_CERT, SERVER_KEY = (
    os.path.join(CERT_DIR, 'server.crt'),
    os.path.join(CERT_DIR, 'server.key')
)
CLIENT_CERT, CLIENT_KEY = (
    os.path.join(CERT_DIR, 'client.crt'),
    os.path.join(CERT_DIR, 'client.key')
)


LOGGER = logging.getLogger('pynetdicom')
LOGGER.setLevel(logging.CRITICAL)
#LOGGER.setLevel(logging.DEBUG)


class TestAssociationSocket(object):
    """Tests for the transport.AssociationSocket class."""
    def setup(self):
        ae = AE()
        self.assoc = Association(ae, MODE_REQUESTOR)

    def get_listen_socket(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_RCVTIMEO,
            pack('ll', 1, 0)
        )
        sock.bind(('', 11112))
        sock.listen(5)
        return sock

    def test_init_new(self):
        """Test creating a new AssociationSocket instance."""
        sock = AssociationSocket(self.assoc)

        assert sock.tls_args is None
        assert sock.select_timeout == 0.5
        assert sock._assoc == self.assoc
        assert isinstance(sock.socket, socket.socket)
        assert sock._is_connected is False

        with pytest.raises(queue.Empty):
            sock.event_queue.get(block=False)

    def test_init_address(self):
        """Test creating a new bound AssociationSocket instance."""
        sock = AssociationSocket(self.assoc, address=('', 11112))

        assert sock.tls_args is None
        assert sock.select_timeout == 0.5
        assert sock._assoc == self.assoc
        assert isinstance(sock.socket, socket.socket)
        assert sock.socket.getsockname()[0] == '0.0.0.0'
        assert sock.socket.getsockname()[1] == 11112
        assert sock._is_connected is False

        with pytest.raises(queue.Empty):
            sock.event_queue.get(block=False)

    def test_init_existing(self):
        """Test creating a new AssociationSocket around existing socket."""
        sock = AssociationSocket(self.assoc, client_socket='abc')

        assert sock.tls_args is None
        assert sock.select_timeout == 0.5
        assert sock._assoc == self.assoc
        assert sock.socket == 'abc'
        assert sock._is_connected is True

        assert sock.event_queue.get(block=False) == "Evt5"

    @pytest.mark.skipif(sys.version_info[:2] == (3, 4), reason='no caplog')
    def test_init_raises(self, caplog):
        """Test exception is raised if init with client_socket and address."""
        msg = (
            r"AssociationSocket instantiated with both a 'client_socket' "
            r"and bind 'address'. The original socket will not be rebound"
        )
        with caplog.at_level(logging.WARNING, logger='pynetdicom'):
            sock = AssociationSocket(self.assoc,
                                     client_socket='abc',
                                     address=('', 11112))

            assert msg in caplog.text

    def test_close_connect(self):
        """Test closing and connecting."""
        sock = AssociationSocket(self.assoc)
        sock._is_connected = True
        assert sock.socket is not None
        sock.close()
        assert sock.socket is None
        # Tries to connect, sets to None if fails
        sock.connect(('', 11112))
        assert sock.event_queue.get() == 'Evt17'
        assert sock.socket is None

    def test_ready_error(self):
        """Test AssociationSocket.ready."""
        sock = AssociationSocket(self.assoc)
        assert sock.ready is False
        sock._is_connected = True
        assert sock.ready is True
        sock.socket.close()
        assert sock.ready is False
        assert sock.event_queue.get() == 'Evt17'

    def test_print(self):
        """Test str(AssociationSocket)."""
        sock = AssociationSocket(self.assoc)
        assert sock.__str__() == sock.socket.__str__()


@pytest.fixture
def server_context(request):
    """Return a good server SSLContext."""
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_cert_chain(certfile=SERVER_CERT, keyfile=SERVER_KEY)
    context.load_verify_locations(cafile=CLIENT_CERT)
    return context


@pytest.fixture
def client_context(request):
    """Return a good client SSLContext."""
    context = ssl.create_default_context(
        ssl.Purpose.CLIENT_AUTH, cafile=SERVER_CERT)
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_cert_chain(certfile=CLIENT_CERT, keyfile=CLIENT_KEY)
    return context


class TestTLS(object):
    """Test using TLS to wrap the association."""
    def test_tls_not_server_not_client(self):
        """Test associating with no TLS on either end."""
        ae = AE()
        ae.add_supported_context('1.2.840.10008.1.1')
        server = ae.start_server(('', 11112), block=False)

        ae.add_requested_context('1.2.840.10008.1.1')
        assoc = ae.associate('', 11112)
        assert assoc.is_established
        assoc.release()
        assert assoc.is_released

        server.shutdown()

    def test_tls_not_server_yes_client(self, client_context):
        """Test wrapping the requestor socket with TLS (but not server)."""
        ae = AE()
        ae.add_supported_context('1.2.840.10008.1.1')
        server = ae.start_server(('', 11112), block=False)

        ae.add_requested_context('1.2.840.10008.1.1')
        assoc = ae.associate('', 11112, tls_args=(client_context, None))
        assert assoc.is_aborted

        server.shutdown()

    def test_tls_yes_server_not_client(self, server_context):
        """Test wrapping the requestor socket with TLS (and server)."""
        ae = AE()
        ae.add_supported_context('1.2.840.10008.1.1')
        server = ae.start_server(
            ('', 11112),
            block=False,
            ssl_context=server_context,
        )

        ae.add_requested_context('1.2.840.10008.1.1')
        assoc = ae.associate('', 11112)
        assert assoc.is_aborted

        server.shutdown()

    def test_tls_yes_server_yes_client(self, server_context, client_context):
        """Test associating with no TLS on either end."""
        ae = AE()
        ae.add_supported_context('1.2.840.10008.1.1')
        server = ae.start_server(
            ('', 11112),
            block=False,
            ssl_context=server_context,
        )

        ae.add_requested_context('1.2.840.10008.1.1')
        assoc = ae.associate('', 11112, tls_args=(client_context, None))
        assert assoc.is_established
        assoc.release()
        assert assoc.is_released

        server.shutdown()


class TestAssociationServer(object):
    @pytest.mark.skip()
    def test_multi_assoc(self):
        """Test that multiple requestors can association when blocking."""
        ae = AE()
        ae.maximum_associations = 10
        ae.add_supported_context('1.2.840.10008.1.1')
        ae.start_server(('', 11112))

    def test_multi_assoc_non(self):
        """Test that multiple requestors can association when non-blocking."""
        ae = AE()
        ae.maximum_associations = 10
        ae.add_supported_context('1.2.840.10008.1.1')
        scp = ae.start_server(('', 11112), block=False)

        def on_open(evt):
            print(evt.address)
            print(evt.event)
            print(evt.timestamp)

        scp.bind(evt.EVT_CONN_OPEN, on_open)

        time.sleep(10)

        scp.shutdown()


class TestTransportEventsAcceptor(object):
    """Test the transport events and handling as acceptor."""
    def setup(self):
        self.ae = None

    def teardown(self):
        if self.ae:
            self.ae.shutdown()

    def test_no_handlers(self):
        """Test associations as acceptor with no handlers bound."""
        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)
        assert scp._handlers[evt.EVT_CONN_OPEN] == []
        assoc = ae.associate('localhost', 11112)

        assert scp._handlers[evt.EVT_CONN_OPEN] == []
        assert assoc.is_established
        assert assoc.dul.socket._handlers[evt.EVT_CONN_OPEN] == []
        assert assoc.dul.socket._handlers[evt.EVT_CONN_CLOSE] == []

        assert len(scp.active_associations) == 1
        scp_assoc = scp.active_associations[0]
        assert scp_assoc.dul.socket._handlers[evt.EVT_CONN_OPEN] == []
        assert scp_assoc.dul.socket._handlers[evt.EVT_CONN_CLOSE] == []

        assoc.release()
        scp.shutdown()

    def test_bind_evt_connection_open(self):
        """Test associations as acceptor with EVT_CONN_OPEN bound."""
        triggered_events = []
        def on_conn_open(event):
            triggered_events.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(
            ('', 11112),
            block=False,
            evt_handlers=[(evt.EVT_CONN_OPEN, on_conn_open)]
        )
        assert scp._handlers[evt.EVT_CONN_OPEN] == [on_conn_open]

        # Start association
        assoc = ae.associate('localhost', 11112)
        # Make sure requestor didn't bind anything
        assert assoc.dul.socket._handlers[evt.EVT_CONN_OPEN] == []

        assert scp._handlers[evt.EVT_CONN_OPEN] == [on_conn_open]
        assert assoc.is_established

        sock = scp.active_associations[0].dul.socket
        assert sock._handlers[evt.EVT_CONN_OPEN] == [on_conn_open]
        assert sock._handlers[evt.EVT_CONN_CLOSE] == []

        # Only the acceptor server's connection open event should trigger
        #   not the acceptor association's client socket
        assert len(triggered_events) == 1
        event = triggered_events[0]
        assert isinstance(event, Event)
        assert isinstance(event.timestamp, datetime)
        assert isinstance(event.address[0], str)
        assert isinstance(event.address[1], int)

        assoc.release()
        scp.shutdown()

    def test_bind_evt_connection_open_running(self):
        """Test binding EVT_CONN_OPEN while running with no assocs."""
        triggered_events = []
        def on_conn_open(event):
            triggered_events.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)
        assert scp._handlers[evt.EVT_CONN_OPEN] == []

        scp.bind(evt.EVT_CONN_OPEN, on_conn_open)
        assert scp._handlers[evt.EVT_CONN_OPEN] == [on_conn_open]

        assoc = ae.associate('localhost', 11112)
        assert assoc.dul.socket._handlers[evt.EVT_CONN_OPEN] == []
        assert assoc.is_established

        sock = scp.active_associations[0].dul.socket
        assert sock._handlers[evt.EVT_CONN_OPEN] == [on_conn_open]
        assert sock._handlers[evt.EVT_CONN_CLOSE] == []

        assert len(scp.active_associations) == 1

        assert len(triggered_events) == 1
        event = triggered_events[0]
        assert isinstance(event, Event)
        assert isinstance(event.timestamp, datetime)
        assert isinstance(event.address[0], str)
        assert isinstance(event.address[1], int)

        assoc.release()

        time.sleep(0.1)

        assert len(scp.active_associations) == 0

        scp.shutdown()

    def test_bind_evt_connection_open_during(self):
        """Test binding EVT_CONN_OPEN while assocs are running."""
        triggered_events = []
        def on_conn_open(event):
            triggered_events.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)
        assert scp._handlers[evt.EVT_CONN_OPEN] == []

        assoc = ae.associate('localhost', 11112)
        assert assoc.dul.socket._handlers[evt.EVT_CONN_OPEN] == []

        assert scp._handlers[evt.EVT_CONN_OPEN] == []
        assert assoc.is_established

        sock = scp.active_associations[0].dul.socket
        assert sock._handlers[evt.EVT_CONN_OPEN] == []
        assert sock._handlers[evt.EVT_CONN_CLOSE] == []
        assert len(triggered_events) == 0

        scp.bind(evt.EVT_CONN_OPEN, on_conn_open)

        assoc2 = ae.associate('localhost', 11112)
        assert assoc2.is_established

        assert len(scp.active_associations) == 2
        sock = scp.active_associations[0].dul.socket
        assert sock._handlers[evt.EVT_CONN_OPEN] == [on_conn_open]
        sock = scp.active_associations[1].dul.socket
        assert sock._handlers[evt.EVT_CONN_OPEN] == [on_conn_open]

        assert len(triggered_events) == 1
        event = triggered_events[0]
        assert isinstance(event, Event)
        assert isinstance(event.timestamp, datetime)
        assert isinstance(event.address[0], str)
        assert isinstance(event.address[1], int)

        assoc.release()

        time.sleep(0.1)

        assert len(scp.active_associations) == 1

        assoc2.release()

        time.sleep(0.1)

        assert len(scp.active_associations) == 0

        scp.shutdown()

    def test_unbind_evt_connection_open_running(self):
        """Test unbinding an event while running with no assocs."""
        triggered_events = []
        def on_conn_open(event):
            triggered_events.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(
            ('', 11112),
            block=False,
            evt_handlers=[(evt.EVT_CONN_OPEN, on_conn_open)]
        )
        assert scp._handlers[evt.EVT_CONN_OPEN] == [on_conn_open]

        scp.unbind(evt.EVT_CONN_OPEN, on_conn_open)
        assert scp._handlers[evt.EVT_CONN_OPEN] == []

        # Start association
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        sock = scp.active_associations[0].dul.socket
        assert sock._handlers[evt.EVT_CONN_OPEN] == []
        assert sock._handlers[evt.EVT_CONN_CLOSE] == []

        assert len(triggered_events) == 0

        assoc.release()
        scp.shutdown()

    def test_unbind_evt_connection_open_during(self):
        """Test unbinding EVT_CONN_OPEN while assoc is established."""
        triggered_events = []
        def on_conn_open(event):
            triggered_events.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(
            ('', 11112),
            block=False,
            evt_handlers=[(evt.EVT_CONN_OPEN, on_conn_open)]
        )
        assert scp._handlers[evt.EVT_CONN_OPEN] == [on_conn_open]

        assoc = ae.associate('localhost', 11112)
        assert assoc.dul.socket._handlers[evt.EVT_CONN_OPEN] == []

        assert scp._handlers[evt.EVT_CONN_OPEN] == [on_conn_open]
        assert assoc.is_established

        sock = scp.active_associations[0].dul.socket
        assert sock._handlers[evt.EVT_CONN_OPEN] == [on_conn_open]
        assert sock._handlers[evt.EVT_CONN_CLOSE] == []

        # Only the acceptor server's connection open event should trigger
        #   not the acceptor association's client socket
        assert len(triggered_events) == 1
        event = triggered_events[0]
        assert isinstance(event, Event)
        assert isinstance(event.timestamp, datetime)
        assert isinstance(event.address[0], str)
        assert isinstance(event.address[1], int)

        assoc.release()

        time.sleep(0.1)
        
        assert len(scp.active_associations) == 0

        scp.unbind(evt.EVT_CONN_OPEN, on_conn_open)
        assert scp._handlers[evt.EVT_CONN_OPEN] == []
        assoc = ae.associate('localhost', 11112)
        assert scp._handlers[evt.EVT_CONN_OPEN] == []
        assert assoc.is_established

        assert len(triggered_events) == 1

        assoc.release()
        scp.shutdown()

    def test_bind_evt_connection_close(self):
        """Test associations as acceptor with EVT_CONN_CLOSE bound."""
        triggered_events = []
        def on_conn_close(event):
            triggered_events.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(
            ('', 11112),
            block=False,
            evt_handlers=[(evt.EVT_CONN_CLOSE, on_conn_close)]
        )
        # Start association
        assoc = ae.associate('localhost', 11112)
        # Make sure requestor didn't bind anything
        assert assoc.dul.socket._handlers[evt.EVT_CONN_CLOSE] == []

        assert evt.EVT_CONN_CLOSE not in scp._handlers
        assert assoc.is_established

        sock = scp.active_associations[0].dul.socket
        assert sock._handlers[evt.EVT_CONN_CLOSE] == [on_conn_close]
        assert sock._handlers[evt.EVT_CONN_OPEN] == []

        assert len(triggered_events) == 0

        assoc.release()

        time.sleep(0.1)

        assert len(triggered_events) == 1
        event = triggered_events[0]
        assert isinstance(event, Event)
        assert isinstance(event.timestamp, datetime)
        assert not hasattr(event, 'address')

        scp.shutdown()

    def test_bind_evt_connection_close_running(self):
        """Test binding EVT_CONN_CLOSE while running with no assocs."""
        triggered_events = []
        def on_conn_close(event):
            triggered_events.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)

        scp.bind(evt.EVT_CONN_CLOSE, on_conn_close)

        # Start association
        assoc = ae.associate('localhost', 11112)
        # Make sure requestor didn't bind anything
        assert assoc.dul.socket._handlers[evt.EVT_CONN_CLOSE] == []

        assert evt.EVT_CONN_CLOSE not in scp._handlers
        assert assoc.is_established

        sock = scp.active_associations[0].dul.socket
        assert sock._handlers[evt.EVT_CONN_CLOSE] == [on_conn_close]
        assert sock._handlers[evt.EVT_CONN_OPEN] == []

        assert len(triggered_events) == 0

        assoc.release()

        time.sleep(0.1)

        assert len(triggered_events) == 1
        event = triggered_events[0]
        assert isinstance(event, Event)
        assert isinstance(event.timestamp, datetime)
        assert not hasattr(event, 'address')

        scp.shutdown()

    def test_bind_evt_connection_close_during(self):
        """Test binding EVT_CONN_CLOSE while associated."""
        triggered_events = []
        def on_conn_close(event):
            triggered_events.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)

        # Start association
        assoc = ae.associate('localhost', 11112)
        # Make sure requestor didn't bind anything
        assert assoc.dul.socket._handlers[evt.EVT_CONN_CLOSE] == []

        assert evt.EVT_CONN_CLOSE not in scp._handlers
        assert assoc.is_established

        sock = scp.active_associations[0].dul.socket
        assert sock._handlers[evt.EVT_CONN_CLOSE] == []
        assert sock._handlers[evt.EVT_CONN_OPEN] == []

        scp.bind(evt.EVT_CONN_CLOSE, on_conn_close)

        assert assoc.dul.socket._handlers[evt.EVT_CONN_CLOSE] == []
        assert sock._handlers[evt.EVT_CONN_CLOSE] == [on_conn_close]
        assert sock._handlers[evt.EVT_CONN_OPEN] == []

        assert len(triggered_events) == 0

        assoc.release()

        time.sleep(0.1)

        assert len(triggered_events) == 1
        event = triggered_events[0]
        assert isinstance(event, Event)
        assert isinstance(event.timestamp, datetime)
        assert not hasattr(event, 'address')

        scp.shutdown()

    def test_unbind_evt_connection_close_running(self):
        """Test unbinding EVT_CONN_CLOSE."""
        triggered_events = []
        def on_conn_close(event):
            triggered_events.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(
            ('', 11112),
            block=False,
            evt_handlers=[(evt.EVT_CONN_CLOSE, on_conn_close)]
        )
        scp.unbind(evt.EVT_CONN_CLOSE, on_conn_close)
        # Start association
        assoc = ae.associate('localhost', 11112)
        # Make sure requestor didn't bind anything
        assert assoc.dul.socket._handlers[evt.EVT_CONN_CLOSE] == []

        assert evt.EVT_CONN_CLOSE not in scp._handlers
        assert assoc.is_established

        sock = scp.active_associations[0].dul.socket
        assert sock._handlers[evt.EVT_CONN_CLOSE] == []
        assert sock._handlers[evt.EVT_CONN_OPEN] == []

        assoc.release()

        time.sleep(0.1)

        assert len(triggered_events) == 0

        scp.shutdown()

    def test_unbind_evt_connection_close_during(self):
        """Test unbinding EVT_CONN_CLOSE while associated."""
        triggered_events = []
        def on_conn_close(event):
            triggered_events.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        evts = [(evt.EVT_CONN_CLOSE, on_conn_close)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=evts)

        # Start association
        assoc = ae.associate('localhost', 11112)
        # Make sure requestor didn't bind anything
        assert assoc.dul.socket._handlers[evt.EVT_CONN_CLOSE] == []

        assert evt.EVT_CONN_CLOSE not in scp._handlers
        assert assoc.is_established

        sock = scp.active_associations[0].dul.socket
        assert sock._handlers[evt.EVT_CONN_CLOSE] == [on_conn_close]
        assert sock._handlers[evt.EVT_CONN_OPEN] == []

        scp.unbind(evt.EVT_CONN_CLOSE, on_conn_close)

        assert sock._handlers[evt.EVT_CONN_CLOSE] == []
        assert sock._handlers[evt.EVT_CONN_OPEN] == []

        assoc.release()

        time.sleep(0.1)

        assert len(triggered_events) == 0

        scp.shutdown()


class TestTransportEventsRequestor(object):
    """Test the transport events and handling as requestor."""
    def test_no_handlers(self):
        """Test associations as requestor with no handlers bound."""
        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)
        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established
        assert assoc.dul.socket._handlers[evt.EVT_CONN_OPEN] == []
        assert assoc.dul.socket._handlers[evt.EVT_CONN_CLOSE] == []

        assoc.release()
        scp.shutdown()

    def test_bind_evt_connection_open(self):
        pass

    def test_unbind_evt_connection_open(self):
        pass

    def test_bind_evt_connection_close(self):
        pass

    def test_unbind_evt_connection_close(self):
        pass
