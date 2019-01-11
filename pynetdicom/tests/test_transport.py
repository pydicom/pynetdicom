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




class TestAssociationServer(object):
    def test_init(self):
        ae = AE()
        server = ThreadedAssociationServer(ae, ('', 11112), {})
        thread = threading.Thread(target=server.serve_forever)
        thread.daemon = True
        thread.start()

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(('localhost', 11112))

        server.shutdown()
        server.server_close()

    def test_server(self):
        ae = AE(port=11113)
        ae.add_supported_context('1.2.840.10008.1.1')
        server = AssociationServer(ae)
        server.serve_forever()
