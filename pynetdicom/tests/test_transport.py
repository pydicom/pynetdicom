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

from pydicom import dcmread

import pynetdicom
from pynetdicom import AE, evt, _config, debug_logger
from pynetdicom.association import Association
from pynetdicom.events import Event
from pynetdicom._globals import MODE_REQUESTOR, MODE_ACCEPTOR
from pynetdicom import transport
from pynetdicom.transport import (
    AssociationSocket, AssociationServer, ThreadedAssociationServer
)
from pynetdicom.sop_class import VerificationSOPClass, RTImageStorage
from .hide_modules import hide_modules


# This is the directory that contains test data
TEST_ROOT = os.path.abspath(os.path.dirname(__file__))
CERT_DIR = os.path.join(TEST_ROOT, 'cert_files')
DCM_DIR = os.path.join(TEST_ROOT, 'dicom_files')

# SSL Testing
SERVER_CERT, SERVER_KEY = (
    os.path.join(CERT_DIR, 'server.crt'),
    os.path.join(CERT_DIR, 'server.key')
)
CLIENT_CERT, CLIENT_KEY = (
    os.path.join(CERT_DIR, 'client.crt'),
    os.path.join(CERT_DIR, 'client.key')
)

DATASET = dcmread(os.path.join(DCM_DIR, 'RTImageStorage.dcm'))


#debug_logger()


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

    def test_close_socket_none(self):
        """Test trying to close a closed socket."""
        def handle_close(event):
            event.assoc.dul.socket.socket = None

        hh = [(evt.EVT_CONN_CLOSE, handle_close)]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(VerificationSOPClass)
        scp = ae.start_server(('', 11113), block=False, evt_handlers=hh)

        ae.add_requested_context(VerificationSOPClass)
        assoc = ae.associate('', 11113)
        assert assoc.is_established

        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_get_local_addr(self):
        """Test get_local_addr()."""
        # Normal use
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_requested_context(VerificationSOPClass)
        assoc = ae.associate('', 11113)
        assert not assoc.is_established
        assert isinstance(assoc.requestor.address, str)
        # Exceptional use
        assert not assoc.is_established
        addr = assoc.dul.socket.get_local_addr(('', 111111))
        assert '127.0.0.1' == addr


@pytest.fixture
def server_context(request):
    """Return a good server SSLContext."""
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_cert_chain(certfile=SERVER_CERT, keyfile=SERVER_KEY)
    context.load_verify_locations(cafile=CLIENT_CERT)

    # TLS v1.3 is not currently supported :(
    # The actual available attributes/protocols depend on OS, OpenSSL version
    #   and Python version, ugh
    if hasattr(ssl, 'TLSVersion'):
        # This is the current and future, but heavily depends on OpenSSL
        # Python 3.7+, w/ OpenSSL 1.1.0g+
        context.maximum_version = ssl.TLSVersion.TLSv1_2
    else:
        # Should work with older Python and OpenSSL versions
        # Python 2.7, 3.5, 3.6
        context = ssl.SSLContext(protocol=ssl.PROTOCOL_TLSv1_2)
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
    def setup(self):
        self.ae = None
        self.has_ssl = transport._HAS_SSL

    def teardown(self):
        if self.ae:
            self.ae.shutdown()

        # Ensure ssl module is available again
        import importlib
        try:
            importlib.reload(pynetdicom.transport)
        except AttributeError:
            # Python 2
            reload(pynetdicom.transport)

    def test_tls_not_server_not_client(self):
        """Test associating with no TLS on either end."""
        self.ae = ae = AE()
        ae.add_supported_context('1.2.840.10008.1.1')
        server = ae.start_server(('', 11112), block=False)

        ae.add_requested_context('1.2.840.10008.1.1')
        assoc = ae.associate('', 11112)
        assert assoc.is_established
        status = assoc.send_c_echo()
        assert status.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        server.shutdown()

        assert len(server.active_associations) == 0

    def test_tls_not_server_yes_client(self, client_context):
        """Test wrapping the requestor socket with TLS (but not server)."""
        self.ae = ae = AE()
        ae.acse_timeout = 0.5
        ae.dimse_timeout = 0.5
        ae.network_timeout = 0.5
        ae.add_supported_context('1.2.840.10008.1.1')

        server = ae.start_server(('', 11112), block=False)

        ae.add_requested_context('1.2.840.10008.1.1')
        assoc = ae.associate('', 11112, tls_args=(client_context, None))
        assert assoc.is_aborted

        server.shutdown()

        time.sleep(0.5)

        assert len(server.active_associations) == 0

    def test_tls_yes_server_not_client(self, server_context):
        """Test wrapping the acceptor socket with TLS (and not client)."""
        self.ae = ae = AE()
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

        assert len(server.active_associations) == 0

    def test_tls_yes_server_yes_client(self, server_context, client_context):
        """Test associating with TLS on both ends."""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
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

        assert len(server.active_associations) == 0

    def test_tls_transfer(self, server_context, client_context):
        """Test transferring data after associating with TLS."""
        ds = []
        def handle_store(event):
            ds.append(event.dataset)
            return 0x0000

        handlers = [(evt.EVT_C_STORE, handle_store)]

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context('1.2.840.10008.1.1')
        ae.add_supported_context(RTImageStorage)
        server = ae.start_server(
            ('', 11112),
            block=False,
            ssl_context=server_context,
            evt_handlers=handlers
        )

        ae.add_requested_context('1.2.840.10008.1.1')
        ae.add_requested_context(RTImageStorage)
        assoc = ae.associate('', 11112, tls_args=(client_context, None))
        assert assoc.is_established
        status = assoc.send_c_store(DATASET)
        assert status.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        server.shutdown()

        assert len(ds[0].PixelData) == 2097152

    @hide_modules(['ssl'])
    def test_no_ssl_scp(self):
        """Test exception raised if no SSL available to Python as SCP."""
        # Reload pynetdicom package
        import importlib
        try:
            importlib.reload(pynetdicom.transport)
        except AttributeError:
            # Python 2
            reload(pynetdicom.transport)

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context('1.2.840.10008.1.1')
        msg = r"Your Python installation lacks support for SSL"
        with pytest.raises(RuntimeError, match=msg):
            ae.start_server(
                ('', 11112),
                block=False,
                ssl_context=['random', 'object'],
            )

    @hide_modules(['ssl'])
    def test_no_ssl_scu(self):
        """Test exception raised if no SSL available to Python as SCU."""
        # Reload pynetdicom package
        import importlib
        try:
            importlib.reload(pynetdicom.transport)
        except AttributeError:
            # Python 2
            reload(pynetdicom.transport)

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_requested_context('1.2.840.10008.1.1')
        msg = r"Your Python installation lacks support for SSL"
        with pytest.raises(RuntimeError, match=msg):
            ae.associate('', 11112, tls_args=(['random', 'object'], None))


class TestAssociationServer(object):
    def setup(self):
        self.ae = None

    def teardown(self):
        if self.ae:
            self.ae.shutdown()

    @pytest.mark.skip()
    def test_multi_assoc_block(self):
        """Test that multiple requestors can associate when blocking."""
        self.ae = ae = AE()
        ae.maximum_associations = 10
        ae.add_supported_context('1.2.840.10008.1.1')
        ae.start_server(('', 11112))

    def test_multi_assoc_non(self):
        """Test that multiple requestors can association when non-blocking."""
        self.ae = ae = AE()
        ae.maximum_associations = 10
        ae.add_supported_context('1.2.840.10008.1.1')
        ae.add_requested_context('1.2.840.10008.1.1')
        scp = ae.start_server(('', 11112), block=False)

        assocs = []
        for ii in range(10):
            assoc = ae.associate('localhost', 11112)
            assert assoc.is_established
            assocs.append(assoc)

        for assoc in assocs:
            assoc.release()

        scp.shutdown()

    def test_init_handlers(self):
        """Test AssociationServer.__init__()."""
        def handle(event):
            pass

        def handle_echo(event):
            return 0x0000

        def handle_echo_b(event):
            return 0x0000

        self.ae = ae = AE()
        handlers = [
            (evt.EVT_DATA_RECV, handle),
            (evt.EVT_DATA_RECV, handle),
            (evt.EVT_C_ECHO, handle_echo),
            (evt.EVT_C_ECHO, handle_echo_b),
            (evt.EVT_DATA_SENT, handle_echo_b),
            (evt.EVT_DATA_SENT, handle_echo),
            (evt.EVT_DATA_SENT, handle),
        ]
        ae.add_supported_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assert evt.EVT_DATA_RECV in scp._handlers
        assert evt.EVT_C_ECHO in scp._handlers
        # Duplicates not added
        assert len(scp._handlers[evt.EVT_DATA_RECV]) == 1
        # Multiples allowed
        assert len(scp._handlers[evt.EVT_DATA_SENT]) == 3
        # Only a single handler allowed
        assert scp._handlers[evt.EVT_C_ECHO] == (handle_echo_b, None)

    def test_get_events(self):
        """Test AssociationServer.get_events()."""
        def handle(event):
            pass

        def handle_echo(event):
            return 0x0000

        def handle_echo_b(event):
            return 0x0000

        self.ae = ae = AE()
        handlers = [
            (evt.EVT_DATA_RECV, handle),
            (evt.EVT_DATA_RECV, handle),
            (evt.EVT_C_ECHO, handle_echo),
            (evt.EVT_C_ECHO, handle_echo_b),
            (evt.EVT_DATA_SENT, handle_echo_b),
            (evt.EVT_DATA_SENT, handle_echo),
            (evt.EVT_DATA_SENT, handle),
        ]
        ae.add_supported_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        bound_events = scp.get_events()
        assert evt.EVT_DATA_RECV in bound_events
        assert evt.EVT_DATA_SENT in bound_events
        assert evt.EVT_C_ECHO in bound_events

        scp.shutdown()

    def test_get_handlers(self):
        """Test AssociationServer.get_handlers()."""
        _config.LOG_HANDLER_LEVEL = 'none'

        def handle(event):
            pass

        def handle_echo(event):
            return 0x0000

        def handle_echo_b(event):
            return 0x0000

        self.ae = ae = AE()
        handlers = [
            (evt.EVT_DATA_RECV, handle),
            (evt.EVT_DATA_RECV, handle),
            (evt.EVT_C_ECHO, handle_echo),
            (evt.EVT_C_ECHO, handle_echo_b),
            (evt.EVT_DATA_SENT, handle_echo_b),
            (evt.EVT_DATA_SENT, handle_echo),
            (evt.EVT_DATA_SENT, handle),
        ]
        ae.add_supported_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assert scp.get_handlers(evt.EVT_DATA_RECV) == [(handle, None)]
        assert (handle, None) in scp.get_handlers(evt.EVT_DATA_SENT)
        assert (handle_echo, None) in scp.get_handlers(evt.EVT_DATA_SENT)
        assert (handle_echo_b, None) in scp.get_handlers(evt.EVT_DATA_SENT)
        assert scp.get_handlers(evt.EVT_C_ECHO) == (handle_echo_b, None)
        assert scp.get_handlers(evt.EVT_PDU_SENT) == []

        scp.shutdown()

    def test_shutdown(self):
        """test tring to shutdown a socket that's already closed."""
        self.ae = ae = AE()
        ae.add_supported_context('1.2.840.10008.1.1')
        server = ae.start_server(('', 11112), block=False)
        server.socket.close()
        server.shutdown()

    def test_exception_in_handler(self):
        """Test exc raised by the handler doesn't shut down the server."""
        class DummyAE(object):
            network_timeout = 5
            _servers = []

        dummy = DummyAE()
        server = ThreadedAssociationServer(dummy, ('', 11112), b'a', [])
        dummy._servers.append(server)
        thread = threading.Thread(target=server.serve_forever)
        thread.daemon = True
        thread.start()

        ae = AE()
        ae.add_requested_context('1.2.840.10008.1.1')
        assoc = ae.associate('', 11112)

        assert server.socket.fileno() != -1

        server.shutdown()

        if sys.version_info[0] == 2:
            with pytest.raises(socket.error):
                server.socket.fileno()
        else:
            assert server.socket.fileno() == -1


class TestEventHandlingAcceptor(object):
    """Test the transport events and handling as acceptor."""
    def setup(self):
        self.ae = None

    def teardown(self):
        if self.ae:
            self.ae.shutdown()

    def test_no_handlers(self):
        """Test with no transport event handlers bound."""
        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)
        assert scp.get_handlers(evt.EVT_CONN_OPEN) == []
        assert scp.get_handlers(evt.EVT_CONN_CLOSE) == []
        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established
        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_CONN_OPEN) == []
        assert scp.get_handlers(evt.EVT_CONN_CLOSE) == []
        assert assoc.get_handlers(evt.EVT_CONN_OPEN) == []
        assert assoc.get_handlers(evt.EVT_CONN_CLOSE) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_CONN_OPEN) == []
        assert child.get_handlers(evt.EVT_CONN_CLOSE) == []

        assoc.release()
        scp.shutdown()

    def test_bind_evt_conn_open(self):
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
        assert scp.get_handlers(evt.EVT_CONN_OPEN) == [(on_conn_open, None)]
        assert scp.get_handlers(evt.EVT_CONN_CLOSE) == []

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_CONN_OPEN) == [(on_conn_open, None)]
        assert scp.get_handlers(evt.EVT_CONN_CLOSE) == []
        assert assoc.get_handlers(evt.EVT_CONN_OPEN) == []
        assert assoc.get_handlers(evt.EVT_CONN_CLOSE) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_CONN_OPEN) == [(on_conn_open, None)]
        assert child.get_handlers(evt.EVT_CONN_CLOSE) == []

        assert len(triggered_events) == 1
        event = triggered_events[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert isinstance(event.address[0], str)
        assert isinstance(event.address[1], int)
        assert event.event.name == 'EVT_CONN_OPEN'

        assoc.release()
        scp.shutdown()

    def test_bind_evt_conn_open_running(self):
        """Test binding EVT_CONN_OPEN while running."""
        triggered_events = []
        def on_conn_open(event):
            triggered_events.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)
        assert scp.get_handlers(evt.EVT_CONN_OPEN) == []
        assert scp.get_handlers(evt.EVT_CONN_CLOSE) == []

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_CONN_OPEN) == []
        assert scp.get_handlers(evt.EVT_CONN_CLOSE) == []
        assert assoc.get_handlers(evt.EVT_CONN_OPEN) == []
        assert assoc.get_handlers(evt.EVT_CONN_CLOSE) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_CONN_OPEN) == []
        assert child.get_handlers(evt.EVT_CONN_CLOSE) == []

        assert len(scp.active_associations) == 1
        assert len(triggered_events) == 0

        # Bind
        scp.bind(evt.EVT_CONN_OPEN, on_conn_open)

        assert scp.get_handlers(evt.EVT_CONN_OPEN) == [(on_conn_open, None)]
        assert scp.get_handlers(evt.EVT_CONN_CLOSE) == []
        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_CONN_OPEN) == [(on_conn_open, None)]
        assert child.get_handlers(evt.EVT_CONN_CLOSE) == []

        assoc2 = ae.associate('localhost', 11112)
        assert assoc2.is_established
        assert len(scp.active_associations) == 2
        assert scp.get_handlers(evt.EVT_CONN_OPEN) == [(on_conn_open, None)]
        assert scp.get_handlers(evt.EVT_CONN_CLOSE) == []
        assert assoc2.get_handlers(evt.EVT_CONN_OPEN) == []
        assert assoc2.get_handlers(evt.EVT_CONN_CLOSE) == []

        child2 = scp.active_associations[1]
        assert child2.get_handlers(evt.EVT_CONN_OPEN) == [(on_conn_open, None)]
        assert child2.get_handlers(evt.EVT_CONN_CLOSE) == []

        assert len(triggered_events) == 1
        event = triggered_events[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert isinstance(event.address[0], str)
        assert isinstance(event.address[1], int)

        assoc.release()
        assoc2.release()

        scp.shutdown()

    def test_unbind_evt_conn_open(self):
        """Test unbinding an event while running."""
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
        assert scp.get_handlers(evt.EVT_CONN_OPEN) == [(on_conn_open, None)]
        assert scp.get_handlers(evt.EVT_CONN_CLOSE) == []

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_CONN_OPEN) == [(on_conn_open, None)]
        assert scp.get_handlers(evt.EVT_CONN_CLOSE) == []
        assert assoc.get_handlers(evt.EVT_CONN_OPEN) == []
        assert assoc.get_handlers(evt.EVT_CONN_CLOSE) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_CONN_OPEN) == [(on_conn_open, None)]
        assert child.get_handlers(evt.EVT_CONN_CLOSE) == []

        assert len(triggered_events) == 1
        event = triggered_events[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert isinstance(event.address[0], str)
        assert isinstance(event.address[1], int)

        # Unbind
        scp.unbind(evt.EVT_CONN_OPEN, on_conn_open)

        assert scp.get_handlers(evt.EVT_CONN_OPEN) == []
        assert scp.get_handlers(evt.EVT_CONN_CLOSE) == []
        assert child.get_handlers(evt.EVT_CONN_OPEN) == []
        assert child.get_handlers(evt.EVT_CONN_CLOSE) == []

        assoc2 = ae.associate('localhost', 11112)
        assert assoc2.is_established
        assert len(scp.active_associations) == 2
        assert scp.get_handlers(evt.EVT_CONN_OPEN) == []
        assert scp.get_handlers(evt.EVT_CONN_CLOSE) == []
        assert assoc2.get_handlers(evt.EVT_CONN_OPEN) == []
        assert assoc2.get_handlers(evt.EVT_CONN_CLOSE) == []

        child2 = scp.active_associations[1]
        assert child2.get_handlers(evt.EVT_CONN_OPEN) == []
        assert child2.get_handlers(evt.EVT_CONN_CLOSE) == []

        assert len(triggered_events) == 1

        assoc.release()
        assoc2.release()
        scp.shutdown()

    def test_unbind_no_event(self):
        """Test unbinding if no event bound."""
        def dummy(event):
            pass

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)
        assert scp.get_handlers(evt.EVT_CONN_CLOSE) == []

        scp.unbind(evt.EVT_CONN_CLOSE, dummy)
        assert scp.get_handlers(evt.EVT_CONN_CLOSE) == []

        scp.shutdown()

    def test_unbind_last_handler(self):
        """Test unbinding if no event bound."""
        def dummy(event):
            pass

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)
        scp.bind(evt.EVT_CONN_CLOSE, dummy)
        assert scp.get_handlers(evt.EVT_CONN_CLOSE) == [(dummy, None)]

        scp.unbind(evt.EVT_CONN_CLOSE, dummy)
        assert scp.get_handlers(evt.EVT_CONN_CLOSE) == []
        assert evt.EVT_CONN_CLOSE not in scp._handlers

        scp.shutdown()

    def test_conn_open_raises(self, caplog):
        """Test the handler for EVT_CONN_OPEN raising exception."""
        def handle(event):
            raise NotImplementedError("Exception description")

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_CONN_OPEN, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        with caplog.at_level(logging.ERROR, logger='pynetdicom'):
            assoc = ae.associate('localhost', 11112)
            assert assoc.is_established
            assoc.release()

            while scp.active_associations:
                time.sleep(0.05)

            scp.shutdown()

            msg = (
                "Exception raised in user's 'evt.EVT_CONN_OPEN' event handler"
                " 'handle'"
            )
            assert msg in caplog.text
            assert "Exception description" in caplog.text

    def test_bind_evt_conn_close(self):
        """Test associations as acceptor with EVT_CONN_CLOSE bound."""
        triggered_events = []
        def on_conn_close(event):
            with threading.Lock():
                triggered_events.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(
            ('', 11112),
            block=False,
            evt_handlers=[(evt.EVT_CONN_CLOSE, on_conn_close)]
        )
        assert scp.get_handlers(evt.EVT_CONN_OPEN) == []
        assert scp.get_handlers(evt.EVT_CONN_CLOSE) == [(on_conn_close, None)]

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_CONN_OPEN) == []
        assert scp.get_handlers(evt.EVT_CONN_CLOSE) == [(on_conn_close, None)]
        assert assoc.get_handlers(evt.EVT_CONN_OPEN) == []
        assert assoc.get_handlers(evt.EVT_CONN_CLOSE) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_CONN_OPEN) == []
        assert child.get_handlers(evt.EVT_CONN_CLOSE) == [(on_conn_close, None)]

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered_events) == 1
        event = triggered_events[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert isinstance(event.address[0], str)
        assert isinstance(event.address[1], int)
        assert event.event.name == 'EVT_CONN_CLOSE'

        scp.shutdown()

    def test_bind_evt_conn_close_running(self):
        """Test binding EVT_CONN_CLOSE while running."""
        triggered_events = []
        def on_conn_close(event):
            triggered_events.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False,)
        assert scp.get_handlers(evt.EVT_CONN_OPEN) == []
        assert scp.get_handlers(evt.EVT_CONN_CLOSE) == []

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_CONN_OPEN) == []
        assert scp.get_handlers(evt.EVT_CONN_CLOSE) == []
        assert assoc.get_handlers(evt.EVT_CONN_OPEN) == []
        assert assoc.get_handlers(evt.EVT_CONN_CLOSE) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_CONN_OPEN) == []
        assert child.get_handlers(evt.EVT_CONN_CLOSE) == []

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1

        scp.bind(evt.EVT_CONN_CLOSE, on_conn_close)

        assert scp.get_handlers(evt.EVT_CONN_OPEN) == []
        assert scp.get_handlers(evt.EVT_CONN_CLOSE) == [(on_conn_close, None)]
        assert assoc.get_handlers(evt.EVT_CONN_OPEN) == []
        assert assoc.get_handlers(evt.EVT_CONN_CLOSE) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_CONN_OPEN) == []
        assert child.get_handlers(evt.EVT_CONN_CLOSE) == [(on_conn_close, None)]

        assoc.release()
        assert assoc.is_released

        time.sleep(0.1)

        assert len(triggered_events) == 1
        event = triggered_events[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)

        scp.shutdown()

    def test_unbind_evt_conn_close(self):
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
        assert scp.get_handlers(evt.EVT_CONN_OPEN) == []
        assert scp.get_handlers(evt.EVT_CONN_CLOSE) == [(on_conn_close, None)]

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_CONN_OPEN) == []
        assert scp.get_handlers(evt.EVT_CONN_CLOSE) == [(on_conn_close, None)]
        assert assoc.get_handlers(evt.EVT_CONN_OPEN) == []
        assert assoc.get_handlers(evt.EVT_CONN_CLOSE) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_CONN_OPEN) == []
        assert child.get_handlers(evt.EVT_CONN_CLOSE) == [(on_conn_close, None)]

        scp.unbind(evt.EVT_CONN_CLOSE, on_conn_close)
        assert scp.get_handlers(evt.EVT_CONN_OPEN) == []
        assert scp.get_handlers(evt.EVT_CONN_CLOSE) == []
        assert child.get_handlers(evt.EVT_CONN_OPEN) == []
        assert child.get_handlers(evt.EVT_CONN_CLOSE) == []

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered_events) == 0

        scp.shutdown()

    def test_conn_close_raises(self, caplog):
        """Test the handler for EVT_CONN_CLOSE raising exception."""
        def handle(event):
            raise NotImplementedError("Exception description")

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_CONN_CLOSE, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        with caplog.at_level(logging.ERROR, logger='pynetdicom'):
            assoc = ae.associate('localhost', 11112)
            assert assoc.is_established
            assoc.release()

            while scp.active_associations:
                time.sleep(0.05)

            scp.shutdown()

            msg = (
                "Exception raised in user's 'evt.EVT_CONN_CLOSE' event handler"
                " 'handle'"
            )
            assert msg in caplog.text
            assert "Exception description" in caplog.text

    def test_data_sent(self):
        """Test binding to EVT_DATA_SENT."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_DATA_SENT, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)
        assert scp.get_handlers(evt.EVT_DATA_SENT) == [(handle, None)]

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_DATA_SENT) == [(handle, None)]
        assert assoc.get_handlers(evt.EVT_DATA_SENT) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_DATA_SENT) == [(handle, None)]

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 2
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert isinstance(event.data, bytes)
        assert event.event.name == 'EVT_DATA_SENT'

        assert triggered[0].data[0:1] == b'\x02'  # A-ASSOCIATE-AC
        assert triggered[1].data[0:1] == b'\x06'  # A-RELEASE-RP

        scp.shutdown()

    def test_data_sent_bind(self):
        """Test binding to EVT_DATA_SENT."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_DATA_SENT, handle)]
        scp = ae.start_server(('', 11112), block=False)
        assert scp.get_handlers(evt.EVT_DATA_SENT) == []

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        scp.bind(evt.EVT_DATA_SENT, handle)

        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_DATA_SENT) == [(handle, None)]
        assert assoc.get_handlers(evt.EVT_DATA_SENT) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_DATA_SENT) == [(handle, None)]

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert isinstance(event.data, bytes)
        assert event.event.name == 'EVT_DATA_SENT'

        assert event.data[0:1] == b'\x06'  # A-RELEASE-RP

        scp.shutdown()

    def test_data_sent_unbind(self):
        """Test unbinding EVT_DATA_SENT."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_DATA_SENT, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)
        assert scp.get_handlers(evt.EVT_DATA_SENT) == [(handle, None)]

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_DATA_SENT) == [(handle, None)]
        assert assoc.get_handlers(evt.EVT_DATA_SENT) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_DATA_SENT) == [(handle, None)]

        scp.unbind(evt.EVT_DATA_SENT, handle)

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        time.sleep(0.1)

        assert len(triggered) == 1
        assert triggered[0].data[0:1] == b'\x02'  # A-ASSOCIATE-AC

        scp.shutdown()

    def test_data_sent_raises(self, caplog):
        """Test the handler for EVT_DATA_SENT raising exception."""
        def handle(event):
            raise NotImplementedError("Exception description")

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_DATA_SENT, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        with caplog.at_level(logging.ERROR, logger='pynetdicom'):
            assoc = ae.associate('localhost', 11112)
            assert assoc.is_established
            assoc.release()

            while scp.active_associations:
                time.sleep(0.05)

            scp.shutdown()

            msg = (
                "Exception raised in user's 'evt.EVT_DATA_SENT' event handler"
                " 'handle'"
            )
            assert msg in caplog.text
            assert "Exception description" in caplog.text

    def test_data_recv(self):
        """Test starting bound to EVT_DATA_RECV."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_DATA_RECV, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)
        assert scp.get_handlers(evt.EVT_DATA_RECV) == [(handle, None)]

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_DATA_RECV) == [(handle, None)]
        assert assoc.get_handlers(evt.EVT_DATA_RECV) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_DATA_RECV) == [(handle, None)]

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 2
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert isinstance(event.data, bytes)
        assert triggered[0].data[0:1] == b'\x01'  # Should be A-ASSOCIATE-RQ PDU
        assert triggered[1].data[0:1] == b'\x05'  # Should be A-RELEASE-RQ PDU
        assert event.event.name == 'EVT_DATA_RECV'

        scp.shutdown()

    def test_data_recv_bind(self):
        """Test binding to EVT_DATA_RECV."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)
        assert scp.get_handlers(evt.EVT_DATA_RECV) == []

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1

        scp.bind(evt.EVT_DATA_RECV, handle)

        assert scp.get_handlers(evt.EVT_DATA_RECV) == [(handle, None)]
        assert assoc.get_handlers(evt.EVT_DATA_RECV) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_DATA_RECV) == [(handle, None)]

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert isinstance(event.data, bytes)
        assert event.data[0:1] == b'\x05'  # Should be A-RELEASE-RQ PDU
        assert event.event.name == 'EVT_DATA_RECV'

        scp.shutdown()

    def test_data_recv_unbind(self):
        """Test unbinding to EVT_DATA_RECV."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_DATA_RECV, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)
        assert scp.get_handlers(evt.EVT_DATA_RECV) == [(handle, None)]

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        scp.unbind(evt.EVT_DATA_RECV, handle)

        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_DATA_RECV) == []
        assert assoc.get_handlers(evt.EVT_DATA_RECV) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_DATA_RECV) == []

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert isinstance(event.data, bytes)
        assert triggered[0].data[0:1] == b'\x01'  # Should be A-ASSOCIATE-RQ PDU
        assert event.event.name == 'EVT_DATA_RECV'

        scp.shutdown()

    def test_data_recv_raises(self, caplog):
        """Test the handler for EVT_DATA_RECV raising exception."""
        def handle(event):
            raise NotImplementedError("Exception description")

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_DATA_RECV, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        with caplog.at_level(logging.ERROR, logger='pynetdicom'):
            assoc = ae.associate('localhost', 11112)
            assert assoc.is_established
            assoc.release()

            while scp.active_associations:
                time.sleep(0.05)

            scp.shutdown()

            msg = (
                "Exception raised in user's 'evt.EVT_DATA_RECV' event handler"
                " 'handle'"
            )
            assert msg in caplog.text
            assert "Exception description" in caplog.text


class TestEventHandlingRequestor(object):
    """Test the transport events and handling as requestor."""
    def setup(self):
        self.ae = None

    def teardown(self):
        if self.ae:
            self.ae.shutdown()

    def test_no_handlers(self):
        """Test associations as requestor with no handlers bound."""
        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)
        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established
        assert assoc.get_handlers(evt.EVT_CONN_OPEN) == []
        assert assoc.get_handlers(evt.EVT_CONN_CLOSE) == []

        assoc.release()
        scp.shutdown()

    def test_bind_evt_conn_open(self):
        """Test start with a bound EVT_CONN_OPEN"""
        triggered_events = []
        def on_conn_open(event):
            triggered_events.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)

        assoc = ae.associate(
            'localhost', 11112,
            evt_handlers=[(evt.EVT_CONN_OPEN, on_conn_open)]
        )
        assert assoc.is_established
        assert assoc.get_handlers(evt.EVT_CONN_OPEN) == [(on_conn_open, None)]
        assert assoc.get_handlers(evt.EVT_CONN_CLOSE) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_CONN_OPEN) == []
        assert child.get_handlers(evt.EVT_CONN_CLOSE) == []

        assert len(triggered_events) == 1
        event = triggered_events[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert isinstance(event.address[0], str)
        assert isinstance(event.address[1], int)

        assoc.release()
        scp.shutdown()

    def test_unbind_evt_conn_open(self):
        """Test unbinding EVT_CONN_OPEN"""
        triggered_events = []
        def on_conn_open(event):
            triggered_events.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)

        assoc = ae.associate(
            'localhost', 11112,
            evt_handlers=[(evt.EVT_CONN_OPEN, on_conn_open)]
        )
        assert assoc.is_established
        assert assoc.get_handlers(evt.EVT_CONN_OPEN) == [(on_conn_open, None)]
        assert assoc.get_handlers(evt.EVT_CONN_CLOSE) == []

        assoc.unbind(evt.EVT_CONN_OPEN, on_conn_open)
        assert assoc.get_handlers(evt.EVT_CONN_OPEN) == []
        assert assoc.get_handlers(evt.EVT_CONN_CLOSE) == []

        assert len(triggered_events) == 1
        event = triggered_events[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert isinstance(event.address[0], str)
        assert isinstance(event.address[1], int)

        assoc.release()
        scp.shutdown()

    def test_bind_evt_conn_close(self):
        """Test start with a bound EVT_CONN_CLOSED"""
        triggered_events = []
        def on_conn_close(event):
            triggered_events.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)

        assoc = ae.associate(
            'localhost', 11112,
            evt_handlers=[(evt.EVT_CONN_CLOSE, on_conn_close)]
        )
        assert assoc.is_established
        assert assoc.get_handlers(evt.EVT_CONN_OPEN) == []
        assert assoc.get_handlers(evt.EVT_CONN_CLOSE) == [(on_conn_close, None)]

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_CONN_OPEN) == []
        assert child.get_handlers(evt.EVT_CONN_CLOSE) == []

        assert len(triggered_events) == 0

        assoc.release()
        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered_events) == 1
        event = triggered_events[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)

        scp.shutdown()

    def test_bind_evt_conn_close_running(self):
        """Test binding EVT_CONN_CLOSED after assoc running."""
        triggered_events = []
        def on_conn_close(event):
            triggered_events.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert assoc.get_handlers(evt.EVT_CONN_OPEN) == []
        assert assoc.get_handlers(evt.EVT_CONN_CLOSE) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_CONN_OPEN) == []
        assert child.get_handlers(evt.EVT_CONN_CLOSE) == []

        assert len(triggered_events) == 0

        assoc.bind(evt.EVT_CONN_CLOSE, on_conn_close)
        assert assoc.get_handlers(evt.EVT_CONN_OPEN) == []
        assert assoc.get_handlers(evt.EVT_CONN_CLOSE) == [(on_conn_close, None)]

        assoc.release()
        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered_events) == 1
        event = triggered_events[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)

        scp.shutdown()

    def test_unbind_evt_conn_close(self):
        """Test unbinding EVT_CONN_CLOSED"""
        triggered_events = []
        def on_conn_close(event):
            triggered_events.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)

        assoc = ae.associate(
            'localhost', 11112,
            evt_handlers=[(evt.EVT_CONN_CLOSE, on_conn_close)]
        )
        assert assoc.is_established
        assert assoc.get_handlers(evt.EVT_CONN_OPEN) == []
        assert assoc.get_handlers(evt.EVT_CONN_CLOSE) == [(on_conn_close, None)]

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_CONN_OPEN) == []
        assert child.get_handlers(evt.EVT_CONN_CLOSE) == []

        assoc.unbind(evt.EVT_CONN_CLOSE, on_conn_close)

        assert assoc.get_handlers(evt.EVT_CONN_OPEN) == []
        assert assoc.get_handlers(evt.EVT_CONN_CLOSE) == []

        assoc.release()
        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered_events) == 0

        scp.shutdown()

    def test_connection_failure_log(self, caplog):
        """Test that a connection failure is logged."""
        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)
        with caplog.at_level(logging.ERROR, logger='pynetdicom'):
            assoc = ae.associate('unknown', 11112)
            assert assoc.is_aborted

            messages = [
                "Association request failed: unable to connect to remote",
                "TCP Initialisation Error: Connection refused"
            ]
            for msg in messages:
                assert msg in caplog.text

        scp.shutdown()

    def test_data_sent(self):
        """Test binding to EVT_DATA_SENT."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_DATA_SENT, handle)]
        scp = ae.start_server(('', 11112), block=False)
        assert scp.get_handlers(evt.EVT_DATA_SENT) == []

        assoc = ae.associate('localhost', 11112, evt_handlers=handlers)
        assert assoc.is_established
        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_DATA_SENT) == []
        assert assoc.get_handlers(evt.EVT_DATA_SENT) == [(handle, None)]

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_DATA_SENT) == []

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 2
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert isinstance(event.data, bytes)
        assert event.event.name == 'EVT_DATA_SENT'

        assert triggered[0].data[0:1] == b'\x01'  # A-ASSOCIATE-RQ
        assert triggered[1].data[0:1] == b'\x05'  # A-RELEASE-RQ

        scp.shutdown()

    def test_data_sent_bind(self):
        """Test binding to EVT_DATA_SENT."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_DATA_SENT, handle)]
        scp = ae.start_server(('', 11112), block=False)
        assert scp.get_handlers(evt.EVT_DATA_SENT) == []

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        assoc.bind(evt.EVT_DATA_SENT, handle)

        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_DATA_SENT) == []
        assert assoc.get_handlers(evt.EVT_DATA_SENT) == [(handle, None)]

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_DATA_SENT) == []

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert isinstance(event.data, bytes)
        assert event.event.name == 'EVT_DATA_SENT'

        assert event.data[0:1] == b'\x05'  # A-RELEASE-RQ

        scp.shutdown()

    def test_data_sent_unbind(self):
        """Test unbinding EVT_DATA_SENT."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_DATA_SENT, handle)]
        scp = ae.start_server(('', 11112), block=False)
        assert scp.get_handlers(evt.EVT_DATA_SENT) == []

        assoc = ae.associate('localhost', 11112, evt_handlers=handlers)
        assert assoc.is_established
        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_DATA_SENT) == []
        assert assoc.get_handlers(evt.EVT_DATA_SENT) == [(handle, None)]

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_DATA_SENT) == []

        assoc.unbind(evt.EVT_DATA_SENT, handle)

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        assert triggered[0].data[0:1] == b'\x01'  # A-ASSOCIATE-RQ

        scp.shutdown()

    def test_data_recv(self):
        """Test starting bound to EVT_DATA_RECV."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_DATA_RECV, handle)]
        scp = ae.start_server(('', 11112), block=False)
        assert scp.get_handlers(evt.EVT_DATA_RECV) == []

        assoc = ae.associate('localhost', 11112, evt_handlers=handlers)
        assert assoc.is_established
        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_DATA_RECV) == []
        assert assoc.get_handlers(evt.EVT_DATA_RECV) == [(handle, None)]

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_DATA_RECV) == []

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 2
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert isinstance(event.data, bytes)
        assert triggered[0].data[0:1] == b'\x02'  # Should be A-ASSOCIATE-AC PDU
        assert triggered[1].data[0:1] == b'\x06'  # Should be A-RELEASE-RP PDU
        assert event.event.name == 'EVT_DATA_RECV'

        scp.shutdown()

    def test_data_recv_bind(self):
        """Test binding to EVT_DATA_RECV."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)
        assert scp.get_handlers(evt.EVT_DATA_RECV) == []

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1

        assoc.bind(evt.EVT_DATA_RECV, handle)

        assert scp.get_handlers(evt.EVT_DATA_RECV) == []
        assert assoc.get_handlers(evt.EVT_DATA_RECV) == [(handle, None)]

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_DATA_RECV) == []

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert isinstance(event.data, bytes)
        assert event.data[0:1] == b'\x06'  # Should be A-RELEASE-RP PDU
        assert event.event.name == 'EVT_DATA_RECV'

        scp.shutdown()

    def test_data_recv_unbind(self):
        """Test unbinding to EVT_DATA_RECV."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_DATA_RECV, handle)]
        scp = ae.start_server(('', 11112), block=False)
        assert scp.get_handlers(evt.EVT_DATA_RECV) == []

        assoc = ae.associate('localhost', 11112, evt_handlers=handlers)
        assert assoc.is_established
        assert assoc.get_handlers(evt.EVT_DATA_RECV) == [(handle, None)]

        assoc.unbind(evt.EVT_DATA_RECV, handle)

        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_DATA_RECV) == []
        assert assoc.get_handlers(evt.EVT_DATA_RECV) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_DATA_RECV) == []

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert isinstance(event.data, bytes)
        assert triggered[0].data[0:1] == b'\x02'  # Should be A-ASSOCIATE-AC PDU
        assert event.event.name == 'EVT_DATA_RECV'

        scp.shutdown()
