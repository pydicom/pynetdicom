"""The Parrot testing server."""
try:
    import queue
except ImportError:
    import Queue as queue  # Python 2 compatibility
import select
import socket
try:
    from SocketServer import TCPServer, ThreadingMixIn, BaseRequestHandler
except ImportError:
    from socketserver import TCPServer, ThreadingMixIn, BaseRequestHandler
from struct import pack, unpack
import threading
import time

from pynetdicom.transport import AssociationServer


def start_server(commands):
    server = ThreadedParrot(('', 11112), commands)
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()

    return server


class ParrotRequest(BaseRequestHandler):
    @property
    def commands(self):
        """Return a list of command tuples."""
        return self.server.commands

    @property
    def socket(self):
        """Return the socket to the remote."""
        return self.request

    @property
    def ready(self):
        """Return True if there is data available to be read.

        Returns
        -------
        bool
            True if the socket has data ready to be read, False otherwise.
        """
        try:
            # Use a timeout of 0 so we get an "instant" result
            ready, _, _ = select.select([self.socket], [], [], 0.5)
        except (socket.error, socket.timeout, ValueError):
            return False

        return bool(ready)

    @property
    def read_data(self):
        bytestream = bytearray()

        # Try and read the PDU type and length from the socket
        try:
            bytestream.extend(self.recv(6))
        except (socket.error, socket.timeout):
            pass
        try:
            # Byte 1 is always the PDU type
            # Byte 2 is always reserved
            # Bytes 3-6 are always the PDU length
            pdu_type, _, pdu_length = unpack('>BBL', bytestream)
        except struct.error:
            pass

        # Try and read the rest of the PDU
        try:
            bytestream += self.recv(pdu_length)
        except (socket.error, socket.timeout):
            pass

        return bytestream

    def recv(self, nr_bytes):
        """Read `nr_bytes` from the socket.

        *Events Emitted*

        - None

        Parameters
        ----------
        nr_bytes : int
            The number of bytes to attempt to read from the socket.

        Returns
        -------
        bytearray
            The data read from the socket.
        """
        bytestream = bytearray()
        nr_read = 0
        # socket.recv() returns when the network buffer has been emptied
        #   not necessarily when the number of bytes requested have been
        #   read. Its up to us to keep calling recv() until we have all the
        #   data we want
        # **BLOCKING** until either all the data is read or an error occurs
        while nr_read < nr_bytes:
            # Python docs recommend reading a relatively small power of 2
            #   such as 4096
            bufsize = 4096
            if (nr_bytes - nr_read) < bufsize:
                bufsize = nr_bytes - nr_read

            bytes_read = self.socket.recv(bufsize)

            # If socket.recv() reads 0 bytes then the connection has been
            #   broken, so return what we have so far
            if not bytes_read:
                return bytestream

            bytestream.extend(bytes_read)
            nr_read += len(bytes_read)

        return bytestream

    def send(self, bytestream):
        """Try and send `bystream` to the remote.

        Parameters
        ----------
        bytestream : bytes
            The data to send to the remote.

        Returns
        -------
        bool
            True if the data was sent successfully, False otherwise.
        """
        total_sent = 0
        length_data = len(bytestream)
        try:
            while total_sent < length_data:
                # Returns the number of bytes sent
                nr_sent = self.socket.send(bytestream)
                total_sent += nr_sent
        except (socket.error, socket.timeout):
            # Evt17: Transport connection closed
            return False

        return True

    def handle(self):
        # self.server: ThreadedParrot
        # self.client_address: remote's (host, port)
        # self.request: socket
        self.received = []
        self.sent = []
        for (cmd, data) in self.commands:
            if cmd == 'recv':
                self.kill_read = False
                while not self.kill_read:
                    if self.ready:
                        self.received.append(bytes(self.read_data))
                        self.kill_read = True
            elif cmd == 'send':
                self.send(data)
                self.sent.append(data)
            elif cmd == 'wait':
                time.sleep(data)

        # Disconnects automatically when this method ends!


class Parrot(AssociationServer):
    def __init__(self, address, commands):
        """Create a new AssociationServer, bind a socket and start listening.

        Parameters
        ----------
        ae : ae.ApplicationEntity
            The parent AE that's running the server.
        address : 2-tuple
            The (host, port) that the server should run on.
        ssl_context : ssl.SSLContext, optional
            If TLS is to be used then this should be the ssl.SSLContext used
            to wrap the client sockets, otherwise if None then no TLS will be
            used (default).
        """
        self.commands = commands
        self.ssl_context = None
        self.allow_reuse_address = True

        TCPServer.__init__(
            self, address, ParrotRequest, bind_and_activate=True
        )

        self.timeout = 60
        self.handlers = []

    @property
    def received(self):
        return self.handlers[0].received

    def server_bind(self):
        """Bind the socket and set the socket options.

        - socket.SO_REUSEADDR is set to 1
        - socket.SO_RCVTIMEO is set to AE.network_timeout unless the value is
          None in which case it will be left unset.
        """
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.setsockopt(socket.SOL_SOCKET,
                               socket.SO_RCVTIMEO,
                               pack('ll', 2, 0))

        self.socket.bind(self.server_address)
        self.server_address = self.socket.getsockname()

    def finish_request(self, request, client_address):
        """Finish one request by instantiating RequestHandlerClass."""
        handler = self.RequestHandlerClass(request, client_address, self)
        self.handlers.append(handler)

    def shutdown(self):
        """Completely shutdown the server and close it's socket."""
        TCPServer.shutdown(self)
        self.server_close()

    process_request = TCPServer.process_request


class ThreadedParrot(ThreadingMixIn, Parrot):
    process_request_thread = ThreadingMixIn.process_request_thread
