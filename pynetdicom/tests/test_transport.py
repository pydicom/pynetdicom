"""Unit tests for the transport module."""

from datetime import datetime
import logging
import queue
import os
import platform
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
from pynetdicom._globals import MODE_REQUESTOR
from pynetdicom.pdu_primitives import A_ASSOCIATE
from pynetdicom import transport
from pynetdicom.transport import (
    AssociationSocket,
    AssociationServer,
    ThreadedAssociationServer,
    T_CONNECT,
    AddressInformation,
)
from pynetdicom.sop_class import Verification, RTImageStorage
from .encoded_pdu_items import p_data_tf_rq, a_associate_rq
from .hide_modules import hide_modules
from .utils import wait_for_server_socket


# This is the directory that contains test data
TEST_ROOT = os.path.abspath(os.path.dirname(__file__))
CERT_DIR = os.path.join(TEST_ROOT, "cert_files")
DCM_DIR = os.path.join(TEST_ROOT, "dicom_files")

# SSL Testing
SERVER_CERT, SERVER_KEY = (
    os.path.join(CERT_DIR, "server.crt"),
    os.path.join(CERT_DIR, "server.key"),
)
CLIENT_CERT, CLIENT_KEY = (
    os.path.join(CERT_DIR, "client.crt"),
    os.path.join(CERT_DIR, "client.key"),
)

DATASET = dcmread(os.path.join(DCM_DIR, "RTImageStorage.dcm"))


# debug_logger()


class TestAddressInformation:
    """Tests for AssociationInformation."""

    def test_ipv4_init(self):
        addr = AddressInformation("", 0)
        assert addr.address == "0.0.0.0"
        assert addr.port == 0
        assert addr.is_ipv4 is True
        assert addr.is_ipv6 is False
        assert addr.address_family == socket.AF_INET
        assert addr.flowinfo == 0
        assert addr.scope_id == 0
        assert addr.as_tuple == ("0.0.0.0", 0)

    def test_ipv6_init_minimal(self):
        addr = AddressInformation("::1", 0)
        assert addr.address == "::1"
        assert addr.port == 0
        assert addr.is_ipv4 is False
        assert addr.is_ipv6 is True
        assert addr.address_family == socket.AF_INET6
        assert addr.flowinfo == 0
        assert addr.scope_id == 0
        assert addr.as_tuple == ("::1", 0, 0, 0)

    def test_ipv6_init_maximal(self):
        addr = AddressInformation("::1", 0, 10, 11)
        assert addr.address == "::1"
        assert addr.port == 0
        assert addr.is_ipv4 is False
        assert addr.is_ipv6 is True
        assert addr.address_family == socket.AF_INET6
        assert addr.flowinfo == 10
        assert addr.scope_id == 11
        assert addr.as_tuple == ("::1", 0, 10, 11)

    def test_from_tuple(self):
        addr = AddressInformation.from_tuple(("localhost", 11112))
        assert isinstance(addr, AddressInformation)
        assert addr.address == "127.0.0.1"
        assert addr.port == 11112

        addr = AddressInformation.from_tuple(("<broadcast>", 104))
        assert isinstance(addr, AddressInformation)
        assert addr.address == "255.255.255.255"
        assert addr.port == 104

        addr = AddressInformation.from_tuple(("::0", 11113))
        assert isinstance(addr, AddressInformation)
        assert addr.address == "::0"
        assert addr.port == 11113

    def test_from_add_port(self):
        addr = AddressInformation.from_addr_port("localhost", 11112)
        assert isinstance(addr, AddressInformation)
        assert addr.address == "127.0.0.1"
        assert addr.port == 11112

        addr = AddressInformation.from_addr_port("::0", 11113)
        assert isinstance(addr, AddressInformation)
        assert addr.address == "::0"
        assert addr.port == 11113
        assert addr.flowinfo == 0
        assert addr.scope_id == 0

        addr = AddressInformation.from_addr_port(("::0", 12, 13), 11113)
        assert isinstance(addr, AddressInformation)
        assert addr.address == "::0"
        assert addr.port == 11113
        assert addr.flowinfo == 12
        assert addr.scope_id == 13

    def test_address(self):
        addr = AddressInformation("", 0)
        assert addr.address == "0.0.0.0"
        assert addr.address_family == socket.AF_INET
        addr.address = "<broadcast>"
        assert addr.address == "255.255.255.255"
        assert addr.address_family == socket.AF_INET
        addr.address = "localhost"
        assert addr.address == "127.0.0.1"
        assert addr.address_family == socket.AF_INET
        addr.address = "192.168.0.1"
        assert addr.address == "192.168.0.1"
        assert addr.address_family == socket.AF_INET
        addr.address = "::0"
        assert addr.address == "::0"
        assert addr.address_family == socket.AF_INET6
        addr.address = "192.168.0.1"
        assert addr.address == "192.168.0.1"
        assert addr.address_family == socket.AF_INET


class TestTConnect:
    """Tests for T_CONNECT."""

    def test_bad_addr_raises(self):
        """Test a bad init parameter raises exception"""
        msg = (
            r"'request' must be 'pynetdicom.pdu_primitives.A_ASSOCIATE', not 'NoneType'"
        )
        with pytest.raises(TypeError, match=msg):
            T_CONNECT(None)

    def test_address_request(self):
        """Test init with an A-ASSOCIATE primitive"""
        request = A_ASSOCIATE()
        request.called_presentation_address = AddressInformation("123.4", 12)
        conn = T_CONNECT(request)
        assert conn.address == ("123.4", 12)
        assert conn.request is request

        msg = r"A connection attempt has not yet been made"
        with pytest.raises(ValueError, match=msg):
            conn.result

    def test_result_setter(self):
        """Test setting the result value."""
        request = A_ASSOCIATE()
        request.called_presentation_address = AddressInformation("123.4", 12)
        conn = T_CONNECT(request)

        msg = r"Invalid connection result 'foo'"
        with pytest.raises(ValueError, match=msg):
            conn.result = "foo"

        assert conn._result == ""

        for result in ("Evt2", "Evt17"):
            conn.result = result
            assert conn.result == result

    def test_address_inf(self):
        request = A_ASSOCIATE()
        request.called_presentation_address = AddressInformation("123.4", 12)
        conn = T_CONNECT(request)
        assert conn.address_info is request.called_presentation_address


class TestAssociationSocket:
    """Tests for the transport.AssociationSocket class."""

    def setup_method(self):
        ae = AE()
        self.assoc = Association(ae, MODE_REQUESTOR)

    def test_init_new(self):
        """Test creating a new AssociationSocket instance."""
        sock = AssociationSocket(self.assoc, address=AddressInformation("", 11112))

        assert sock.tls_args is None
        assert sock.select_timeout == 0.5
        assert sock._assoc == self.assoc
        assert isinstance(sock.socket, socket.socket)
        assert sock.socket.getsockname()[0] == "0.0.0.0"
        assert sock.socket.getsockname()[1] == 11112
        assert sock._is_connected is False

        with pytest.raises(queue.Empty):
            sock.event_queue.get(block=False)

        sock.close()

        sock = AssociationSocket(self.assoc, address=AddressInformation("::1", 11112))

        assert sock.tls_args is None
        assert sock.select_timeout == 0.5
        assert sock._assoc == self.assoc
        assert isinstance(sock.socket, socket.socket)
        assert sock.socket.getsockname()[0] == "::1"
        assert sock.socket.getsockname()[1] == 11112
        assert sock._is_connected is False

        with pytest.raises(queue.Empty):
            sock.event_queue.get(block=False)

        sock.close()

    def test_init_existing(self):
        """Test creating a new AssociationSocket around existing socket."""
        sock = AssociationSocket(self.assoc, client_socket="abc")

        assert sock.tls_args is None
        assert sock.select_timeout == 0.5
        assert sock._assoc == self.assoc
        assert sock.socket == "abc"
        assert sock._is_connected is True

        assert sock.event_queue.get(block=False) == "Evt5"

    def test_init_warns(self, caplog):
        """Test warning is logged if init with client_socket and address."""
        msg = (
            r"AssociationSocket instantiated with both a 'client_socket' "
            r"and bind 'address'. The original socket will not be rebound"
        )
        with caplog.at_level(logging.WARNING, logger="pynetdicom"):
            AssociationSocket(
                self.assoc, client_socket="abc", address=("localhost", 11112)
            )

            assert msg in caplog.text

    def test_init_raises(self):
        """Test warning is logged if init with client_socket and address."""
        msg = (
            "Either 'client_socket' or 'address' must be used when creating a new "
            "AssociationSocket instance"
        )
        with pytest.raises(ValueError, match=msg):
            AssociationSocket(self.assoc)

    def test_close_connect(self):
        """Test closing and connecting."""
        sock = AssociationSocket(self.assoc, address=AddressInformation("", 0))
        sock._is_connected = True
        assert sock.socket is not None
        sock.close()
        assert sock.socket is None
        # Tries to connect, sets to None if fails
        # Ensure we fail if *something* is listening
        self.assoc.connection_timeout = 1
        request = A_ASSOCIATE()
        request.called_presentation_address = AddressInformation("", 11112)
        sock.socket = sock._create_socket(AddressInformation("", 0))
        sock.connect(T_CONNECT(request))
        assert sock.event_queue.get() == "Evt17"
        assert sock.socket is None

    def test_ready_error(self):
        """Test AssociationSocket.ready."""
        sock = AssociationSocket(self.assoc, address=AddressInformation("localhost", 0))
        assert sock.ready is False
        sock._is_connected = True
        if platform.system() in ["Windows", "Darwin"]:
            assert sock.ready is False
        else:
            assert sock.ready is True
        sock.socket.close()
        assert sock.ready is False
        assert sock.event_queue.get() == "Evt17"

    def test_print(self):
        """Test str(AssociationSocket)."""
        sock = AssociationSocket(self.assoc, address=AddressInformation("", 0))
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
        ae.add_supported_context(Verification)
        scp = ae.start_server(("localhost", 11113), block=False, evt_handlers=hh)

        ae.add_requested_context(Verification)
        assoc = ae.associate("localhost", 11113)
        assert assoc.is_established

        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_get_local_addr(self):
        """Test get_local_addr()."""
        sock = AssociationSocket(self.assoc, address=AddressInformation("", 11112))

        # Normal use
        with pytest.warns(DeprecationWarning, match="get_local_addr"):
            addr = sock.get_local_addr(("", 11113))

        # Exception
        with pytest.warns(DeprecationWarning, match="get_local_addr"):
            addr = sock.get_local_addr(("", 111111))

        assert addr == "127.0.0.1"

    def test_multiple_pdu_req(self):
        """Test what happens if two PDUs are sent before the select call."""
        events = []

        def handle_echo(event):
            events.append(event)
            return 0x0000

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context("1.2.840.10008.1.1")
        ae.add_requested_context("1.2.840.10008.1.1")

        server = ae.start_server(("localhost", 11112), block=False)

        assoc = ae.associate(
            "localhost", 11112, evt_handlers=[(evt.EVT_C_ECHO, handle_echo)]
        )
        assert assoc.is_established

        # Send data directly to the requestor
        socket = server.active_associations[0].dul.socket
        socket.send(2 * p_data_tf_rq)

        time.sleep(1)

        assoc.release()
        assert assoc.is_released

        server.shutdown()

        assert 2 == len(events)

    def test_multiple_pdu_acc(self):
        """Test what happens if two PDUs are sent before the select call."""
        events = []

        def handle_echo(event):
            events.append(event)
            return 0x0000

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context("1.2.840.10008.1.1")
        ae.add_requested_context("1.2.840.10008.1.1")

        server = ae.start_server(
            ("localhost", 11112),
            block=False,
            evt_handlers=[(evt.EVT_C_ECHO, handle_echo)],
        )

        assoc = ae.associate(
            "localhost",
            11112,
        )
        assert assoc.is_established

        # Send data directly to the requestor
        socket = assoc.dul.socket
        socket.send(2 * p_data_tf_rq)

        time.sleep(1)

        assoc.release()
        assert assoc.is_released

        server.shutdown()

        assert 2 == len(events)

    def test_no_socket_connect_raises(self):
        sock = AssociationSocket(self.assoc, address=AddressInformation("", 0))
        sock._is_connected = True
        sock.close()
        assert sock.socket is None

        msg = r"A socket must be created before calling AssociationSocket.connect\(\)"
        with pytest.raises(ValueError, match=msg):
            sock.connect(None)


def server_context_v1_2():
    """Return a good TLs v1.2 server SSLContext."""
    # Python 3.10 and PEP 644, the ssl module requires OpenSSL 1.1.1 or newer
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_cert_chain(certfile=SERVER_CERT, keyfile=SERVER_KEY)
    context.load_verify_locations(cafile=CLIENT_CERT)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.maximum_version = ssl.TLSVersion.TLSv1_2

    return context


def server_context_v1_3():
    """Return a good TLS v1.3 server SSLContext."""
    # Python 3.10 and PEP 644, the ssl module requires OpenSSL 1.1.1 or newer
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_cert_chain(certfile=SERVER_CERT, keyfile=SERVER_KEY)
    context.load_verify_locations(cafile=CLIENT_CERT)
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    context.maximum_version = ssl.TLSVersion.TLSv1_3

    return context


@pytest.fixture
def client_context(request):
    """Return a good client SSLContext."""
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=SERVER_CERT)
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_cert_chain(certfile=CLIENT_CERT, keyfile=CLIENT_KEY)
    context.check_hostname = False

    return context


TLS_SERVER_CONTEXTS = [(server_context_v1_2, "TLSv1.2")]
if ssl.OPENSSL_VERSION_INFO >= (1, 1, 1):
    TLS_SERVER_CONTEXTS = [
        (server_context_v1_2, "TLSv1.2"),
        (server_context_v1_3, "TLSv1.3"),
    ]


class TestTLS:
    """Test using TLS to wrap the association."""

    def setup_method(self):
        self.ae = None
        self.has_ssl = transport._HAS_SSL

    def teardown_method(self):
        if self.ae:
            self.ae.shutdown()

        # Ensure ssl module is available again
        import importlib

        importlib.reload(pynetdicom.transport)
        importlib.reload(pynetdicom.ae)

    def test_tls_not_server_not_client(self):
        """Test associating with no TLS on either end."""

        self.ae = ae = AE()
        ae.add_supported_context("1.2.840.10008.1.1")
        server = ae.start_server(("localhost", 11112), block=False)

        ae.add_requested_context("1.2.840.10008.1.1")
        assoc = ae.associate("localhost", 11112)
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
        ae.add_supported_context("1.2.840.10008.1.1")

        server = ae.start_server(("localhost", 11112), block=False)

        ae.add_requested_context("1.2.840.10008.1.1")
        assoc = ae.associate("localhost", 11112, tls_args=(client_context, None))
        assert assoc.is_aborted

        server.shutdown()

        time.sleep(0.5)

        assert len(server.active_associations) == 0

    @pytest.mark.parametrize("server_context, tls_version", TLS_SERVER_CONTEXTS)
    def test_tls_yes_server_not_client(self, server_context, tls_version, caplog):
        """Test wrapping the acceptor socket with TLS (and not client)."""
        with caplog.at_level(logging.ERROR, logger="pynetdicom"):
            self.ae = ae = AE()
            ae.add_supported_context("1.2.840.10008.1.1")
            server = ae.start_server(
                ("localhost", 11112),
                block=False,
                ssl_context=server_context(),
            )

            ae.add_requested_context("1.2.840.10008.1.1")
            assoc = ae.associate("localhost", 11112)
            assert assoc.is_aborted

            server.shutdown()

            assert len(server.active_associations) == 0
            assert "Connection closed before the entire PDU was received" in caplog.text

    @pytest.mark.parametrize("server_context, tls_version", TLS_SERVER_CONTEXTS)
    def test_tls_yes_server_yes_client(
        self, server_context, tls_version, client_context
    ):
        """Test associating with TLS on both ends."""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context("1.2.840.10008.1.1")
        server = ae.start_server(
            ("localhost", 11112),
            block=False,
            ssl_context=server_context(),
        )

        wait_for_server_socket(server, 1)

        ae.add_requested_context("1.2.840.10008.1.1")
        assoc = ae.associate("localhost", 11112, tls_args=(client_context, None))
        assert assoc.dul.socket.socket.version() == tls_version
        assert assoc.is_established
        assoc.release()
        assert assoc.is_released

        server.shutdown()

        assert len(server.active_associations) == 0

    @pytest.mark.parametrize("server_context, tls_version", TLS_SERVER_CONTEXTS)
    def test_tls_transfer(self, server_context, tls_version, client_context):
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
        ae.add_supported_context("1.2.840.10008.1.1")
        ae.add_supported_context(RTImageStorage)
        server = ae.start_server(
            ("localhost", 11112),
            block=False,
            ssl_context=server_context(),
            evt_handlers=handlers,
        )

        ae.add_requested_context("1.2.840.10008.1.1")
        ae.add_requested_context(RTImageStorage)
        assoc = ae.associate("localhost", 11112, tls_args=(client_context, None))
        assert assoc.is_established
        status = assoc.send_c_store(DATASET)
        assert status.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        server.shutdown()

        assert len(ds[0].PixelData) == 2097152

    @hide_modules(["ssl"])
    def test_no_ssl_scp(self):
        """Test exception raised if no SSL available to Python as SCP."""
        # Reload pynetdicom package
        import importlib

        importlib.reload(pynetdicom.transport)

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context("1.2.840.10008.1.1")
        msg = r"Your Python installation lacks support for SSL"
        with pytest.raises(RuntimeError, match=msg):
            ae.start_server(
                ("localhost", 11112),
                block=False,
                ssl_context=["random", "object"],
            )

    @hide_modules(["ssl"])
    def test_no_ssl_scu(self):
        """Test exception raised if no SSL available to Python as SCU."""
        # Reload pynetdicom package
        import importlib

        importlib.reload(pynetdicom.transport)

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_requested_context("1.2.840.10008.1.1")
        msg = r"Your Python installation lacks support for SSL"
        with pytest.raises(RuntimeError, match=msg):
            ae.associate("localhost", 11112, tls_args=(["random", "object"], None))

    @pytest.mark.parametrize("server_context, tls_version", TLS_SERVER_CONTEXTS)
    def test_multiple_pdu_req(self, server_context, tls_version, client_context):
        """Test what happens if two PDUs are sent before the select call."""
        events = []

        def handle_echo(event):
            events.append(event)
            return 0x0000

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context("1.2.840.10008.1.1")
        ae.add_requested_context("1.2.840.10008.1.1")

        server = ae.start_server(
            ("localhost", 11112),
            block=False,
            ssl_context=server_context(),
        )

        assoc = ae.associate(
            "localhost",
            11112,
            tls_args=(client_context, None),
            evt_handlers=[(evt.EVT_C_ECHO, handle_echo)],
        )
        assert assoc.is_established

        # Send data directly to the requestor
        socket = server.active_associations[0].dul.socket
        socket.send(2 * p_data_tf_rq)

        time.sleep(1)

        assoc.release()
        timeout = 0
        while not assoc.is_released and timeout < 5:
            time.sleep(0.05)
            timeout += 0.05

        assert assoc.is_released

    @pytest.mark.parametrize("server_context, tls_version", TLS_SERVER_CONTEXTS)
    def test_multiple_pdu_acc(self, server_context, tls_version, client_context):
        """Test what happens if two PDUs are sent before the select call."""
        events = []

        def handle_echo(event):
            events.append(event)
            return 0x0000

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context("1.2.840.10008.1.1")
        ae.add_requested_context("1.2.840.10008.1.1")

        server = ae.start_server(
            ("localhost", 11112),
            block=False,
            ssl_context=server_context(),
            evt_handlers=[(evt.EVT_C_ECHO, handle_echo)],
        )

        assoc = ae.associate("localhost", 11112, tls_args=(client_context, None))
        assert assoc.is_established

        # Send data directly to the requestor
        socket = assoc.dul.socket
        socket.send(2 * p_data_tf_rq)

        time.sleep(1)

        assoc.release()
        timeout = 0
        while not assoc.is_released and timeout < 5:
            time.sleep(0.05)
            timeout += 0.05

        assert assoc.is_released

        server.shutdown()

        assert 2 == len(events)


class TestAssociationServer:
    def setup_method(self):
        self.ae = None

    def teardown_method(self):
        if self.ae:
            self.ae.shutdown()

    @pytest.mark.skip()
    def test_multi_assoc_block(self):
        """Test that multiple requestors can associate when blocking."""
        self.ae = ae = AE()
        ae.maximum_associations = 10
        ae.add_supported_context("1.2.840.10008.1.1")
        ae.start_server(("localhost", 11112))

    def test_multi_assoc_non(self):
        """Test that multiple requestors can association when non-blocking."""
        self.ae = ae = AE()
        ae.maximum_associations = 10
        ae.add_supported_context("1.2.840.10008.1.1")
        ae.add_requested_context("1.2.840.10008.1.1")
        scp = ae.start_server(("localhost", 11112), block=False)

        assocs = []
        for ii in range(10):
            assoc = ae.associate("localhost", 11112)
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
        ae.add_supported_context(Verification)
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)

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
        ae.add_supported_context(Verification)
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)

        bound_events = scp.get_events()
        assert evt.EVT_DATA_RECV in bound_events
        assert evt.EVT_DATA_SENT in bound_events
        assert evt.EVT_C_ECHO in bound_events

        scp.shutdown()

    def test_get_handlers(self):
        """Test AssociationServer.get_handlers()."""
        _config.LOG_HANDLER_LEVEL = "none"

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
        ae.add_supported_context(Verification)
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)

        assert scp.get_handlers(evt.EVT_DATA_RECV) == [(handle, None)]
        assert (handle, None) in scp.get_handlers(evt.EVT_DATA_SENT)
        assert (handle_echo, None) in scp.get_handlers(evt.EVT_DATA_SENT)
        assert (handle_echo_b, None) in scp.get_handlers(evt.EVT_DATA_SENT)
        assert scp.get_handlers(evt.EVT_C_ECHO) == (handle_echo_b, None)
        assert scp.get_handlers(evt.EVT_PDU_SENT) == []

        scp.shutdown()

    def test_shutdown(self):
        """test trying to shutdown a socket that's already closed."""
        self.ae = ae = AE()
        ae.add_supported_context(Verification)
        server = ae.start_server(("localhost", 11112), block=False)
        server.socket.close()
        server.shutdown()

    def test_exception_in_handler(self):
        """Test exc raised by the handler doesn't shut down the server."""

        class DummyAE:
            network_timeout = 5
            _servers = []

        dummy = DummyAE()
        server = ThreadedAssociationServer(dummy, ("localhost", 11112), b"a", [])
        dummy._servers.append(server)
        thread = threading.Thread(target=server.serve_forever)
        thread.daemon = True
        thread.start()

        ae = AE()
        ae.add_requested_context("1.2.840.10008.1.1")
        ae.associate("localhost", 11112)

        assert server.socket.fileno() != -1

        server.shutdown()

        if sys.version_info[0] == 2:
            with pytest.raises(OSError):
                server.socket.fileno()
        else:
            assert server.socket.fileno() == -1

    def test_blocking_process_request(self):
        """Test AssociationServer.process_request."""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(Verification)

        t = threading.Thread(
            target=ae.start_server, args=(("localhost", 11112),), kwargs={"block": True}
        )
        t.start()

        ae.add_requested_context(Verification)
        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established
        assoc.release()
        ae.shutdown()

    def test_split_pdu_windows(self):
        """Regression test for #653"""

        events = []

        def handle_echo(event):
            events.append(event)
            return 0x0000

        req_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        req_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        req_sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVTIMEO, pack("ll", 6000, 0))

        req_sock.bind(("localhost", 0))

        self.ae = ae = AE()
        ae.network_timeout = 1
        ae.add_supported_context("1.2.840.10008.1.1")
        ae.add_requested_context("1.2.840.10008.1.1")

        server = ae.start_server(
            ("localhost", 11112),
            block=False,
            evt_handlers=[(evt.EVT_C_ECHO, handle_echo)],
        )

        # Set AE requestor connection timeout
        req_sock.settimeout(30)
        req_sock.connect(("localhost", 11112))
        req_sock.settimeout(None)

        # Send data directly to the acceptor
        req_sock.send(a_associate_rq)

        # Give the acceptor time to send the A-ASSOCIATE-AC
        while not server.active_associations:
            time.sleep(0.0001)

        assoc = server.active_associations[0]
        while not assoc.is_established:
            time.sleep(0.0001)

        # Forcibly split the P-DATA PDU into two TCP segments
        req_sock.send(p_data_tf_rq[:12])
        time.sleep(0.5)
        req_sock.send(p_data_tf_rq[12:])

        # Give the acceptor time to process the C-ECHO-RQ
        while assoc.is_established and not events:
            time.sleep(0.0001)

        server.shutdown()
        req_sock.close()

        assert 1 == len(events)

    def test_gc(self):
        """Test garbage collection."""
        self.ae = ae = AE()
        ae.add_supported_context(Verification)
        server = ae.start_server(("localhost", 11112), block=False)
        server._gc[0] = 59

        # Default poll interval is 0.5 s
        while server._gc[0] == server._gc[1]:
            time.sleep(0.1)

        assert server._gc[0] < server._gc[1]

        server.shutdown()


class TestEventHandlingAcceptor:
    """Test the transport events and handling as acceptor."""

    def setup_method(self):
        self.ae = None

    def teardown_method(self):
        if self.ae:
            self.ae.shutdown()

    def test_no_handlers(self):
        """Test with no transport event handlers bound."""
        self.ae = ae = AE()
        ae.add_supported_context(Verification)
        ae.add_requested_context(Verification)
        scp = ae.start_server(("localhost", 11112), block=False)
        assert scp.get_handlers(evt.EVT_CONN_OPEN) == []
        assert scp.get_handlers(evt.EVT_CONN_CLOSE) == []
        assoc = ae.associate("localhost", 11112)

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
        ae.add_supported_context(Verification)
        ae.add_requested_context(Verification)
        scp = ae.start_server(
            ("localhost", 11112),
            block=False,
            evt_handlers=[(evt.EVT_CONN_OPEN, on_conn_open)],
        )
        assert scp.get_handlers(evt.EVT_CONN_OPEN) == [(on_conn_open, None)]
        assert scp.get_handlers(evt.EVT_CONN_CLOSE) == []

        assoc = ae.associate("localhost", 11112)
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
        assert event.event.name == "EVT_CONN_OPEN"

        assoc.release()
        scp.shutdown()

    def test_bind_evt_conn_open_running(self):
        """Test binding EVT_CONN_OPEN while running."""
        triggered_events = []

        def on_conn_open(event):
            triggered_events.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(Verification)
        ae.add_requested_context(Verification)
        scp = ae.start_server(("localhost", 11112), block=False)
        assert scp.get_handlers(evt.EVT_CONN_OPEN) == []
        assert scp.get_handlers(evt.EVT_CONN_CLOSE) == []

        assoc = ae.associate("localhost", 11112)
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

        assoc2 = ae.associate("localhost", 11112)
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
        ae.add_supported_context(Verification)
        ae.add_requested_context(Verification)
        scp = ae.start_server(
            ("localhost", 11112),
            block=False,
            evt_handlers=[(evt.EVT_CONN_OPEN, on_conn_open)],
        )
        assert scp.get_handlers(evt.EVT_CONN_OPEN) == [(on_conn_open, None)]
        assert scp.get_handlers(evt.EVT_CONN_CLOSE) == []

        assoc = ae.associate("localhost", 11112)
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

        assoc2 = ae.associate("localhost", 11112)
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
        ae.add_supported_context(Verification)
        ae.add_requested_context(Verification)
        scp = ae.start_server(("localhost", 11112), block=False)
        assert scp.get_handlers(evt.EVT_CONN_CLOSE) == []

        scp.unbind(evt.EVT_CONN_CLOSE, dummy)
        assert scp.get_handlers(evt.EVT_CONN_CLOSE) == []

        scp.shutdown()

    def test_unbind_last_handler(self):
        """Test unbinding if no event bound."""

        def dummy(event):
            pass

        self.ae = ae = AE()
        ae.add_supported_context(Verification)
        ae.add_requested_context(Verification)
        scp = ae.start_server(("localhost", 11112), block=False)
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
        ae.add_supported_context(Verification)
        ae.add_requested_context(Verification)
        handlers = [(evt.EVT_CONN_OPEN, handle)]
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)

        with caplog.at_level(logging.ERROR, logger="pynetdicom"):
            assoc = ae.associate("localhost", 11112)
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
        ae.add_supported_context(Verification)
        ae.add_requested_context(Verification)
        scp = ae.start_server(
            ("localhost", 11112),
            block=False,
            evt_handlers=[(evt.EVT_CONN_CLOSE, on_conn_close)],
        )
        assert scp.get_handlers(evt.EVT_CONN_OPEN) == []
        assert scp.get_handlers(evt.EVT_CONN_CLOSE) == [(on_conn_close, None)]

        assoc = ae.associate("localhost", 11112)
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
        assert event.event.name == "EVT_CONN_CLOSE"

        scp.shutdown()

    def test_bind_evt_conn_close_running(self):
        """Test binding EVT_CONN_CLOSE while running."""
        triggered_events = []

        def on_conn_close(event):
            triggered_events.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(Verification)
        ae.add_requested_context(Verification)
        scp = ae.start_server(
            ("localhost", 11112),
            block=False,
        )
        assert scp.get_handlers(evt.EVT_CONN_OPEN) == []
        assert scp.get_handlers(evt.EVT_CONN_CLOSE) == []

        assoc = ae.associate("localhost", 11112)
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

        assoc = ae.associate("localhost", 11112)
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
        ae.add_supported_context(Verification)
        ae.add_requested_context(Verification)
        scp = ae.start_server(
            ("localhost", 11112),
            block=False,
            evt_handlers=[(evt.EVT_CONN_CLOSE, on_conn_close)],
        )
        assert scp.get_handlers(evt.EVT_CONN_OPEN) == []
        assert scp.get_handlers(evt.EVT_CONN_CLOSE) == [(on_conn_close, None)]

        assoc = ae.associate("localhost", 11112)
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
        ae.add_supported_context(Verification)
        ae.add_requested_context(Verification)
        handlers = [(evt.EVT_CONN_CLOSE, handle)]
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)

        with caplog.at_level(logging.ERROR, logger="pynetdicom"):
            assoc = ae.associate("localhost", 11112)
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
        ae.add_supported_context(Verification)
        ae.add_requested_context(Verification)
        handlers = [(evt.EVT_DATA_SENT, handle)]
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)
        assert scp.get_handlers(evt.EVT_DATA_SENT) == [(handle, None)]

        assoc = ae.associate("localhost", 11112)
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
        assert event.event.name == "EVT_DATA_SENT"

        assert triggered[0].data[0:1] == b"\x02"  # A-ASSOCIATE-AC
        assert triggered[1].data[0:1] == b"\x06"  # A-RELEASE-RP

        scp.shutdown()

    def test_data_sent_bind(self):
        """Test binding to EVT_DATA_SENT."""
        triggered = []

        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(Verification)
        ae.add_requested_context(Verification)
        scp = ae.start_server(("localhost", 11112), block=False)
        assert scp.get_handlers(evt.EVT_DATA_SENT) == []

        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established
        time.sleep(0.5)

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
        assert event.event.name == "EVT_DATA_SENT"

        assert event.data[0:1] == b"\x06"  # A-RELEASE-RP

        scp.shutdown()

    def test_data_sent_unbind(self):
        """Test unbinding EVT_DATA_SENT."""
        triggered = []

        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(Verification)
        ae.add_requested_context(Verification)
        handlers = [(evt.EVT_DATA_SENT, handle)]
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)
        assert scp.get_handlers(evt.EVT_DATA_SENT) == [(handle, None)]

        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established
        time.sleep(0.5)
        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_DATA_SENT) == [(handle, None)]
        assert assoc.get_handlers(evt.EVT_DATA_SENT) == []

        child = scp.active_associations[0]
        assert child.dul.state_machine.current_state == "Sta6"
        assert child.get_handlers(evt.EVT_DATA_SENT) == [(handle, None)]

        scp.unbind(evt.EVT_DATA_SENT, handle)

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        time.sleep(0.1)

        assert len(triggered) == 1
        assert triggered[0].data[0:1] == b"\x02"  # A-ASSOCIATE-AC

        scp.shutdown()

    def test_data_sent_raises(self, caplog):
        """Test the handler for EVT_DATA_SENT raising exception."""

        def handle(event):
            raise NotImplementedError("Exception description")

        self.ae = ae = AE()
        ae.add_supported_context(Verification)
        ae.add_requested_context(Verification)
        handlers = [(evt.EVT_DATA_SENT, handle)]
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)

        with caplog.at_level(logging.ERROR, logger="pynetdicom"):
            assoc = ae.associate("localhost", 11112)
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
        ae.add_supported_context(Verification)
        ae.add_requested_context(Verification)
        handlers = [(evt.EVT_DATA_RECV, handle)]
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)
        assert scp.get_handlers(evt.EVT_DATA_RECV) == [(handle, None)]

        assoc = ae.associate("localhost", 11112)
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
        assert triggered[0].data[0:1] == b"\x01"  # Should be A-ASSOCIATE-RQ PDU
        assert triggered[1].data[0:1] == b"\x05"  # Should be A-RELEASE-RQ PDU
        assert event.event.name == "EVT_DATA_RECV"

        scp.shutdown()

    def test_data_recv_bind(self):
        """Test binding to EVT_DATA_RECV."""
        triggered = []

        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(Verification)
        ae.add_requested_context(Verification)
        scp = ae.start_server(("localhost", 11112), block=False)
        assert scp.get_handlers(evt.EVT_DATA_RECV) == []

        assoc = ae.associate("localhost", 11112)
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
        assert event.data[0:1] == b"\x05"  # Should be A-RELEASE-RQ PDU
        assert event.event.name == "EVT_DATA_RECV"

        scp.shutdown()

    def test_data_recv_unbind(self):
        """Test unbinding to EVT_DATA_RECV."""
        triggered = []

        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(Verification)
        ae.add_requested_context(Verification)
        handlers = [(evt.EVT_DATA_RECV, handle)]
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)
        assert scp.get_handlers(evt.EVT_DATA_RECV) == [(handle, None)]

        assoc = ae.associate("localhost", 11112)
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
        assert triggered[0].data[0:1] == b"\x01"  # Should be A-ASSOCIATE-RQ PDU
        assert event.event.name == "EVT_DATA_RECV"

        scp.shutdown()

    def test_data_recv_raises(self, caplog):
        """Test the handler for EVT_DATA_RECV raising exception."""

        def handle(event):
            raise NotImplementedError("Exception description")

        self.ae = ae = AE()
        ae.add_supported_context(Verification)
        ae.add_requested_context(Verification)
        handlers = [(evt.EVT_DATA_RECV, handle)]
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)

        with caplog.at_level(logging.ERROR, logger="pynetdicom"):
            assoc = ae.associate("localhost", 11112)
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


class TestEventHandlingRequestor:
    """Test the transport events and handling as requestor."""

    def setup_method(self):
        self.ae = None

    def teardown_method(self):
        if self.ae:
            self.ae.shutdown()

    def test_no_handlers(self):
        """Test associations as requestor with no handlers bound."""
        self.ae = ae = AE()
        ae.add_supported_context(Verification)
        ae.add_requested_context(Verification)
        scp = ae.start_server(("localhost", 11112), block=False)
        assoc = ae.associate("localhost", 11112)

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
        ae.add_supported_context(Verification)
        ae.add_requested_context(Verification)
        scp = ae.start_server(("localhost", 11112), block=False)

        assoc = ae.associate(
            "localhost", 11112, evt_handlers=[(evt.EVT_CONN_OPEN, on_conn_open)]
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
        ae.add_supported_context(Verification)
        ae.add_requested_context(Verification)
        scp = ae.start_server(("localhost", 11112), block=False)

        assoc = ae.associate(
            "localhost", 11112, evt_handlers=[(evt.EVT_CONN_OPEN, on_conn_open)]
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
        ae.add_supported_context(Verification)
        ae.add_requested_context(Verification)
        scp = ae.start_server(("localhost", 11112), block=False)

        assoc = ae.associate(
            "localhost", 11112, evt_handlers=[(evt.EVT_CONN_CLOSE, on_conn_close)]
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
        ae.add_supported_context(Verification)
        ae.add_requested_context(Verification)
        scp = ae.start_server(("localhost", 11112), block=False)

        assoc = ae.associate("localhost", 11112)
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
        ae.add_supported_context(Verification)
        ae.add_requested_context(Verification)
        scp = ae.start_server(("localhost", 11112), block=False)

        assoc = ae.associate(
            "localhost", 11112, evt_handlers=[(evt.EVT_CONN_CLOSE, on_conn_close)]
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
        ae.add_supported_context(Verification)
        ae.add_requested_context(Verification)
        scp = ae.start_server(("localhost", 11112), block=False)
        with caplog.at_level(logging.ERROR, logger="pynetdicom"):
            assoc = ae.associate("localhost", 11113)
            assert assoc.is_aborted

            messages = [
                "Association request failed: unable to connect to remote",
                "TCP Initialisation Error",
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
        ae.add_supported_context(Verification)
        ae.add_requested_context(Verification)
        handlers = [(evt.EVT_DATA_SENT, handle)]
        scp = ae.start_server(("localhost", 11112), block=False)
        assert scp.get_handlers(evt.EVT_DATA_SENT) == []

        assoc = ae.associate("localhost", 11112, evt_handlers=handlers)
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
        assert event.event.name == "EVT_DATA_SENT"

        assert triggered[0].data[0:1] == b"\x01"  # A-ASSOCIATE-RQ
        assert triggered[1].data[0:1] == b"\x05"  # A-RELEASE-RQ

        scp.shutdown()

    def test_data_sent_bind(self):
        """Test binding to EVT_DATA_SENT."""
        triggered = []

        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(Verification)
        ae.add_requested_context(Verification)
        scp = ae.start_server(("localhost", 11112), block=False)
        assert scp.get_handlers(evt.EVT_DATA_SENT) == []

        assoc = ae.associate("localhost", 11112)
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
        assert event.event.name == "EVT_DATA_SENT"

        assert event.data[0:1] == b"\x05"  # A-RELEASE-RQ

        scp.shutdown()

    def test_data_sent_unbind(self):
        """Test unbinding EVT_DATA_SENT."""
        triggered = []

        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(Verification)
        ae.add_requested_context(Verification)
        handlers = [(evt.EVT_DATA_SENT, handle)]
        scp = ae.start_server(("localhost", 11112), block=False)
        assert scp.get_handlers(evt.EVT_DATA_SENT) == []

        assoc = ae.associate("localhost", 11112, evt_handlers=handlers)
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
        assert triggered[0].data[0:1] == b"\x01"  # A-ASSOCIATE-RQ

        scp.shutdown()

    def test_data_recv(self):
        """Test starting bound to EVT_DATA_RECV."""
        triggered = []

        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(Verification)
        ae.add_requested_context(Verification)
        handlers = [(evt.EVT_DATA_RECV, handle)]
        scp = ae.start_server(("localhost", 11112), block=False)
        assert scp.get_handlers(evt.EVT_DATA_RECV) == []

        assoc = ae.associate("localhost", 11112, evt_handlers=handlers)
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
        assert triggered[0].data[0:1] == b"\x02"  # Should be A-ASSOCIATE-AC PDU
        assert triggered[1].data[0:1] == b"\x06"  # Should be A-RELEASE-RP PDU
        assert event.event.name == "EVT_DATA_RECV"

        scp.shutdown()

    def test_data_recv_bind(self):
        """Test binding to EVT_DATA_RECV."""
        triggered = []

        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(Verification)
        ae.add_requested_context(Verification)
        scp = ae.start_server(("localhost", 11112), block=False)
        assert scp.get_handlers(evt.EVT_DATA_RECV) == []

        assoc = ae.associate("localhost", 11112)
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
        assert event.data[0:1] == b"\x06"  # Should be A-RELEASE-RP PDU
        assert event.event.name == "EVT_DATA_RECV"

        scp.shutdown()

    def test_data_recv_unbind(self):
        """Test unbinding to EVT_DATA_RECV."""
        triggered = []

        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(Verification)
        ae.add_requested_context(Verification)
        handlers = [(evt.EVT_DATA_RECV, handle)]
        scp = ae.start_server(("localhost", 11112), block=False)
        assert scp.get_handlers(evt.EVT_DATA_RECV) == []

        assoc = ae.associate("localhost", 11112, evt_handlers=handlers)
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
        assert triggered[0].data[0:1] == b"\x02"  # Should be A-ASSOCIATE-AC PDU
        assert event.event.name == "EVT_DATA_RECV"

        scp.shutdown()
