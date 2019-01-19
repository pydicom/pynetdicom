"""Unit tests for the transport module."""

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
from pynetdicom.transport import (
    AssociationSocket, AssociationServer, ThreadedAssociationServer
)
from pynetdicom._globals import MODE_REQUESTOR, MODE_ACCEPTOR


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

        scp.bind(evt.EVT_CONNECTION_OPEN, on_open)

        time.sleep(10)

        scp.shutdown()
