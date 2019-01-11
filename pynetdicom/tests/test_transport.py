"""Unit tests for the transport module."""

import socket

import pytest

from pynetdicom import AE
from pynetdicom.association import Association
from pynetdicom.transport import AssociationSocket
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
