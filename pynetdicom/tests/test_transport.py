"""Unit tests for the transport module."""

import socket
import threading
import time

import pytest

from pynetdicom import AE
from pynetdicom.association import Association
from pynetdicom.transport import (
    AssociationSocket, AssociationServer, ThreadedAssociationServer
)
from pynetdicom._globals import MODE_REQUESTOR, MODE_ACCEPTOR


class TestAssociationSocket(object):
    """Tests for the transport.AssociationSocket class."""
    def setup(self):
        ae = AE()
        self.assoc = Association(ae, MODE_REQUESTOR)

    def test_init(self):
        """Test creating a new AssociationSocket instance."""
        sock = AssociationSocket(self.assoc)

        assert sock.tls_kwargs == {}
        assert sock._assoc == self.assoc
        assert isinstance(sock.socket, socket.socket)

    def test_ae_associate(self):
        ae = AE()
        ae.add_requested_context('1.2.840.10008.1.1')
        assoc = ae.associate('localhost', 11112)
        if assoc.is_established:
            assoc.send_c_echo()
            assoc.release()
            

class TestAssociationServer(object):
    def test_init(self):
        ae = AE()
        ae.add_supported_context('1.2.840.10008.1.1')
        server = ae.start_server(11112, block=False)

        time.sleep(10)

        server.shutdown()

    def test_threaded_server_shutdown(self):
        ae = AE()
        ae.add_supported_context('1.2.840.10008.1.1')
        server = ae.start_server(11112, block=False)

        time.sleep(10)

        server.shutdown()

    def test_ae_server_shutdown(self):
        ae = AE()
        ae.add_supported_context('1.2.840.10008.1.1')
        server = ae.start_server(11112, block=False)

        time.sleep(10)

        ae.shutdown()

    def test_server(self):
        ae = AE(port=11113)
        ae.add_supported_context('1.2.840.10008.1.1')
        server = ae.start_server(11112)
        assert server is None
