"""Implementation of the Transport Service."""

import select
import ssl
import socket
from struct import unpack

from pynetdicom.association import Association
from pynetdicom._globals import MODE_ACCEPTOR

# Transport service events
# Connection requested
EVT_TRANSPORT_INDICATION = (
    'TRANSPORT', 'INDICATION', 'Transport connection indication'
)
# Connection confirmed
EVT_TRANSPORT_OPEN = ('TRANSPORT', 'OPEN', 'Transport connection open')
# Connection closed
EVT_TRANSPORT_CLOSED = ('TRANSPORT', 'CLOSED', 'Transport connection closed')

# Socket modes
_SOCKET_MODE_CLIENT = "client"
_SOCKET_MODE_SERVER = "server"
SOCKET_MAXIMUM_QUEUE = 5


# Transport primitives
CONNECTION_INDICATION = None
CONNECTION_CONFIRMATION = None
CONNECTION_OPEN = None
CONNECTION_CLOSED = None


class TransportService(object):
    """

    Attributes
    ----------
    select_timeout : float or None
        The timeout (in seconds) that the select.select() call will block
        for (default 0.5). A value of 0 specifies a poll and never blocks.
        A value of None blocks until a connection is ready.
    """
    def __init__(self, ae):
        self._ae = ae
        self._callbacks = {
            EVT_TRANSPORT_INDICATION : [],
            EVT_TRANSPORT_OPEN : [],
            EVNT_TRANSPORT_CLOSED : [],
        }
        self.select_timeout = 0.5

    def bind(self, event, callback):
        """Bind a `callback` to a transport service `event`.

        Parameters
        ----------
        event : pynetdicom.events
            An event tuple, one of EVT_TRANSPORT_OPEN, EVT_TRANSPORT_CLOSED,
            EVT_TRANSPORT_INDICATION.
        callback : callable
            The function to call when the event occurs.

        Raises
        ------
        ValueError
            If `event` is not a valid transport event.
        """
        if event not in self._callbacks:
            raise ValueError(
                "Invalid event for the transport service"
            )

        if callback not in self._callbacks[event]:
            self._callbacks[event].append(callback)

    def unbind(self, event, callback):
        """Unbind a `callback` from a transport service `event`.

        Parameters
        ----------
        event : pynetdicom.events
            An event tuple, one of EVT_TRANSPORT_OPEN, EVT_TRANSPORT_CLOSED,
            EVT_TRANSPORT_INDICATION.
        callback : callable
            The function to stop calling when the event occurs.

        Raises
        ------
        ValueError
            If `event` is not a valid transport event.
        """
        if event not in self._callbacks:
            raise ValueError(
                "Invalid event for the transport service"
            )

        if callback in self._callbacks[event]:
            self._callbacks[event].remove(callback)

    def process_primitive(self, primitive):
        """Process a received transport service primitive.

        Parameters
        ----------
        primitive

            - TRANSPORT_CONNECT
                Open a new connection and send emit either a confirmation
                event (Evt2) or negation event (Evt17).
            - TRANSPORT_INDICATION
                A remote has attempted to connect.
            - TRANSPORT_CLOSE
                Close an existing connection and emit event Evt17 when done.
        """
        # Received TRANSPORT_CONNECT
        # Request to open new connection
        #   -> Sends TRANSPORT_CONFIRMATION
        #      Confirmation that connection is open
        return self.open_connection()

        # Received TRANSPORT_INDICATION
        # Server received connection request

        # Received TRANSPORT_CLOSE
        # Request to close connection

        pass

    def open_connection(self, assoc, tls_args=None):
        """TRANSPORT_CONNECT received by transport service.

        Open connection to remote.

        returns a client socket
        """
        sock = TransportSocket()
        sock.callbacks = self._callbacks[:]
        sock._assoc = assoc

        return sock.connect((addr, port), self.tls_args)

    def get_server_socket(self, (addr, port), tls_args=None):
        """Return a server socket.

        Parameters
        ----------
        addr : str
            The address to bind the server socket to.
        port : int
            The port to bind the server socket to.
        tls_args : dict
            A dict containing keyword arguments to ssl.wrap_socket.

        Return
        ------
        transport.TransportSocket
            A socket operating in server mode.
        """
        sock = TransportSocket()
        sock.callbacks = self._callbacks[:]

        return sock.listen((addr, port), tls_args or {})

    # Not a good spot, needs to be non-blocking
    def monitor_connection(self):
        while not assoc._kill:
            try:
                ready, _, _ = select.select([assoc._socket], [], [], 0.5)
            except (socket.error, socket.timeout, ValueError):
                # Evt17: closed connection indication
                assoc._event_queue.put('Evt17')
                break

            if ready:
                self.read_data(assoc._socket)


class BaseSocket(object):
    def __init__(self, ae):
        self._ae = ae
        self.select_timeout = 0.5
        self.socket = None
        self._local = (None, None)
        self._mode = None

    @property
    def ae(self):
        return self._ae

    @property
    def is_client(self):
        """Return True if the socket is in client mode, False otherwise."""
        return self._mode == _SOCKET_MODE_CLIENT

    @property
    def is_server(self):
        """Return True if the socket is in server mode, False otherwise."""
        return self._mode == _SOCKET_MODE_SERVER



class ServerSocket(BaseServer):
    def __init__(self, ae, (addr, port), tls_args=None):
        super(self).__init__(ae)

        self._local = (addr, port)
        self._stop_server = False
        self._mode = _SOCKET_MODE_SERVER

        self.socket = None
        self.select_timeout = 0.5

        self._create_socket((addr, port), tls_args or {})

    def _create_socket(self, (addr, port), tls_args):
        # AF_INET: IPv4, SOCK_STREAM: TCP socket
        socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # SO_REUSEADDR: reuse the socket in TIME_WAIT state without
        #   waiting for its natural timeout to expire
        #   Allows local address reuse
        socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # If no timeout is set then recv() will block forever if
        #   the connection is kept alive with no data sent
        # SO_RCVTIMEO: the timeout on receive calls in seconds
        #   set using a packed binary string containing two uint32s as
        #   (seconds, microseconds)
        timeout_seconds = floor(self.ae.network_timeout)
        timeout_microsec = int(self.ae.network_timeout % 1 * 1000)
        socket.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_RCVTIMEO,
            pack('ll', timeout_seconds, timeout_microsec)
        )

        try:
            # Bind the socket to an (address, port)
            #   If address is '' then the socket is reachable by any
            #   address the machine may have, otherwise is visible only on that
            #   address
            if tls_args:
                socket = ssl.wrap_socket(socket, server_side=True, **tls_args)
            socket.bind((addr, port))
            # Listen for connections made to the socket
            # socket.listen() says to queue up to as many as N connect requests
            #   before refusing outside connections
            socket.listen(SOCKET_MAXIMUM_QUEUE)

        except (socket.error, socket.timeout):
            if socket is not None:
                socket.close()

            return

        self.socket = socket

    def serve_forever(self):
        while not self._stop_server:
            try:
                ready, _, _ = select.select(
                    [self.socket], [], [], self.select_timeout
                )
                if self.ready and not self._stop_server:
                    try:
                        # Wrap the client socket and start a new
                        #   Association acceptor thread
                        client = ClientSocket(self.ae)
                        client.socket = self.socket.accept()
                        client.start_as_acceptor()
                    except (socket.error, socket.timeout):
                        if client.socket is not None:
                            client.close()


            except (socket.error, socket.timeout, ValueError):
                return


class ClientSocket(BaseServer):
    def __init__(self, ae):
        self._ae = ae
        self.socket = socket
        self._assoc = None
        self._mode = _SOCKET_MODE_CLIENT

    @property
    def assoc(self):
        """Return the socket's parent Association instance."""
        return self._assoc

    def close(self):
        if self._socket is None:
            return

        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except (socket.error):
            pass

        self.socket.close()
        self.event_queue.put('Evt17')

    def send(self, bytestream):
        """Try and send `bystream` to the remote.

        **Events Emitted**

        - None
        - Evt17: Transport connected closed.

        Parameters
        ----------
        bytestream : bytes
            The data to send to the remote.

        Returns
        -------
        bool
            True if the data was sent successfully (no event emitted),
            False otherwise (Evt17 emitted).
        """
        if self._socket is None:
            raise RuntimeError("The socket is not open")

        total_sent = 0
        length_data = len(bytestream)
        while nr_sent < length_data:
            try:
                # Returns the number of bytes sent
                nr_sent = self._socket.send(bytestream)
                total_sent += nr_sent
            except socket.error:
                # Evt17: Transport connection closed
                self.event_queue.put('Evt17')

    def start_as_requestor(self):
        pass
        # bluh

    def start_as_acceptor(self):
        assoc = Association(self.ae, MODE_ACCEPTOR, self)
        assoc.acse_timeout = self.ae.acse_timeout
        assoc.dimse_timeout = self.ae.dimse_timeout
        assoc.network_timeout = self.ae.network_timeout

        # Association Acceptor object -> local AE
        assoc.acceptor.maximum_length = self.ae.maximum_pdu_size
        assoc.acceptor.ae_title = self.ae_title
        assoc.acceptor.address = self.address
        assoc.acceptor.port = self.port
        assoc.acceptor.implementation_class_uid = (
            self.ae.implementation_class_uid
        )
        assoc.acceptor.implementation_version_name = (
            self.ae.implementation_version_name
        )
        assoc.acceptor.supported_contexts = deepcopy(
            self.ae.supported_contexts
        )

        # Association Requestor object -> remote AE
        assoc.requestor.address = client_socket.getpeername()[0]
        assoc.requestor.port = client_socket.getpeername()[1]

        assoc.start()
        self.ae.active_associations.append(assoc)


class TransportSocket(object):
    def __init__(self, socket=None):
        self._mode = None
        self._socket = socket
        self._local = None
        self._remote = None
        self._assoc = None

        self.select_timeout = 0.5

        if self.socket:
            self._handle_connection()

    def connect(self, (addr, port), tls_args):
        """Try and connect to a remote.

        **Events Emitted**

        - Evt2: Transport connection confirmed
        - Evt17: Transport connection closed

        Parameters
        ----------
        addr : str
            The IPv4 address to connect to.
        port : int
            The port number to connect to.

        Returns
        -------
        bool
            True if the connection attempt succeeded, False otherwise.
        """
        if not self.is_neutral:
            raise RuntimeError("The socket not in a neutral mode")

        try:
            if tls_args:
                self.socket = ssl.wrap_socket(self.socket,
                                              server_side=False,
                                              **tls_args)
            # Try and connect to remote at (address, port)
            #   raises socket.error if connection refused
            self.socket.connect((addr, port))
            self._mode = _SOCKET_MODE_CLIENT
            self._remote = (addr, port)
            # Evt2: Transport connection confirmation
            self.event_queue.put('Evt2')
        except (socket.error, socket.timeout):
            if self.socket is not None:
                self.socket.close()
            # Evt17: Transport connection closed
            self.event_queue.put('Evt17')
            self._socket = None
            self._mode = None
            self._remote = None

            return False

        return True

    def _create_socket(self):
        """Create a new IPv4 TCP socket and set it up for use.

        *Socket Options*

        - SO_REUSEADDR is 1
        - SO_RCVTIMEO is set to the Association's network_timeout value.

        Returns
        -------
        socket.socket
            An unbound and unconnected socket instance.
        """
        # AF_INET: IPv4, SOCK_STREAM: TCP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # SO_REUSEADDR: reuse the socket in TIME_WAIT state without
        #   waiting for its natural timeout to expire
        #   Allows local address reuse
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # If no timeout is set then recv() will block forever if
        #   the connection is kept alive with no data sent
        # SO_RCVTIMEO: the timeout on receive calls in seconds
        #   set using a packed binary string containing two uint32s as
        #   (seconds, microseconds)
        timeout_seconds = floor(self.assoc.network_timeout)
        timeout_microsec = int(self.assoc.network_timeout % 1 * 1000)
        sock.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_RCVTIMEO,
            pack('ll', timeout_seconds, timeout_microsec)
        )
        # Set mode to neutral
        self._mode = None

        return sock

    @property
    def event_queue(self):
        """Return the Association's event queue."""
        return self.assoc.dul.event_queue

    def _handle_connection(self):
        assoc = Association(mode=MODE_ACCEPTOR)

    def listen(self, (addr, port), tls_args):
        """Try to bind the socket and listen for connections.

        **Events Emitted**

        - None
        - Evt17: Transport connection closed

        Parameters
        ----------
        addr : str
            The IPv4 address to connect to.
        port : int
            The port number to connect to.

        Returns
        -------
        bool
            True if the connection is bound and listening, False otherwise.
        """
        if not self.is_neutral:
            raise RuntimeError("The socket not in a neutral mode")

        try:
            # Bind the socket to an (address, port)
            #   If address is '' then the socket is reachable by any
            #   address the machine may have, otherwise is visible only on that
            #   address
            if tls_args:
                self.socket = ssl.wrap_socket(self.socket,
                                              server_side=True,
                                              **tls_args)
            self.socket.bind((addr, port))
            # Listen for connections made to the socket
            # socket.listen() says to queue up to as many as N connect requests
            #   before refusing outside connections
            self.socket.listen(SOCKET_MAXIMUM_QUEUE)
            self._mode = _SOCKET_MODE_SERVER
            self._local = (addr, port)
        except (socket.error, socket.timeout):
            if self.socket is not None:
                self.socket.close()
            # Evt17: Transport connection closed
            self.event_queue.put('Evt17')
            self._socket = None
            self._mode = None
            self._local = None

            return False

        return True

    @property
    def local(self):
        """Return a 2-tuple of the local's (address, port)."""
        return self._local

    # Maybe doesn't belong here
    def read_pdu(self):
        """Try and read a PDU sent by the remote.

        PDUs are always encoded using big endian.

        **Events Emitted**

        - Evt3: A-ASSOCIATE-AC PDU received from remote
        - Evt3: A-ASSOCIATE-RJ PDU received from remote
        - Evt6: A-ASSOCIATE-RQ PDU received from remote
        - Evt10: P-DATA-TF PDU received from remote
        - Evt12: A-RELEASE-RQ PDU received from remote
        - Evt13: A-RELEASE-RP PDU received from remote
        - Evt16: A-ABORT PDU received from remote
        - Evt17: Transport connection closed indication
        - Evt19: Unrecognised or invalid PDU

        """
        bytestream = bytearray()

        # Try and read the PDU type and length from the socket
        try:
            bytestream.extend(self.recv(6))
        except (socket.error, socket.timeout):
            # Evt17: Transport connection closed
            self.event_queue.put('Evt17')
            return None

        try:
            # Byte 1 is always the PDU type
            # Byte 2 is always reserved
            # Bytes 3-6 are always the PDU length
            pdu_type, _, pdu_length = unpack('>BBL', bytestream)
        except struct.error:
            # Raised if there's not enough data
            # Evt17: Transport connection closed
            self.event_queue.put('Evt17')
            return None

        # If the `pdu_type` is unrecognised
        if pdu_type not in PDU_TYPES:
            # Evt19: Unrecognised or invalid PDU received
            self.event_queue.put('Evt19')
            return None

        # Try and read the rest of the PDU
        try:
            bytestream += sock.recv(pdu_length)
        except socket.error:
            # Evt17: Transport connection closed
            self.event_queue.put('Evt17')
            return None

        # Check that the PDU data was completely read
        if len(bytestream) != 6 + pdu_length:
            # Evt17: Transport connection closed
            self.event_queue.put('Evt17')
            return None

        # Convert the bytestream to the corresponding PDU class
        (pdu, event) = PDU_TYPES[pdu_type]
        try:
            # Decode the PDU data
            pdu.decode(bytestream)
            self.event_queue.put(event)
        except Exception as exc:
            LOGGER.error('Unable to decode the received PDU data')
            LOGGER.exception(exc)
            # Evt19: Unrecognised or invalid PDU received
            self.event_queue.put('Evt19')
            return None

        return pdu

    @property
    def ready(self):
        """Return True if there is data available to be read.

        **Events Emitted**

        - Evt17: Transport connection closed

        Returns
        -------
        bool
            True if the socket has data ready to be read, False otherwise.
        """
        try:
            ready, _, _ = select.select(
                [self._socket], [], [], self.select_timeout
            )
        except (socket.error, socket.timeout, ValueError):
            # Evt17: transport connection closed indication
            self.event_queue.put('Evt17')
            return False

        return ready

    def recv(self, nr_bytes):
        """Read `nr_bytes` from the socket.

        Parameters
        ----------
        nr_bytes : int
            The number of bytes to attempt to read from the socket.

        Returns
        -------
        bytearray
            The data read from the socket.
        """
        if self._socket is None:
            raise RuntimeError("The socket is not open")

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

            bytes_read = self._socket.recv(bufsize)

            # If socket.recv() reads 0 bytes then the connection has been
            #   broken, so return what we have so far
            # Note: anything calling recv
            if not bytes_read:
                return bytestream

            bytestream.extend(bytes_read)
            nr_read += len(bytes_read)

        return bytestream

    @property
    def remote(self):
        """Return a 2-tuple of the remote's (address, port)."""
        return self._remote

    def serve_forever(self):
        while not self._stop_server:
            try:
                ready, _, _ = select.select(
                    [self._socket], [], [], self.select_timeout
                )
                if self.ready and not self._stop_server:
                    try:
                        # Wrap the client socket and start a new
                        #   Association acceptor thread
                        client = TransportSocket(self.socket.accept())
                    except (socket.error, socket.timeout):
                        if client._socket is not None:
                            client.close()
                        client.event_queue.put('Evt17')

            except (socket.error, socket.timeout, ValueError):
                return

    @property
    def socket(self):
        """Return the underlying socket.socket instance.

        **Events Emitted**

        - None
        - Evt17: Transport connection closed

        Parameters
        ----------
        network_timeout : float
            The timeout (in seconds) for socket.recv() calls. Doesn't affect
            socket.accept() calls.

        Returns
        -------
        socket.socket
            The underlying socket, may be either neutral, client or server.
        """
        if self._socket is None:
            self._socket = self._create_socket()

        return self._socket

    def trigger(self, event):
        """Trigger the callbacks bound to `event`.

        Parameters
        ----------
        event : pynetdicom.events
            A transport service event.
        """
        for callback in self._callbacks[event[1]]:
            try:
                callback()
            except Exception as exc:
                LOGGER.error(
                    "Exception in callback for 'TRANSPORT {}' event"
                    .format(event[1])
                )
                LOGGER.exception(exc)


# {PDU's first byte : (PDU class, PDU received on transport connection event)}
PDU_TYPES = {
    0x01 : (A_ASSOCIATE_RQ, 'Evt6'),
    0x02 : (A_ASSOCIATE_AC, 'Evt3'),
    0x03 : (A_ASSOCIATE_RJ, 'Evt4'),
    0x04 : (P_DATA_TF, 'Evt10'),
    0x05 : (A_RELEASE_RQ, 'Evt12'),
    0x06 : (A_RELEASE_RP, 'Evt13'),
    0x07 : (A_ABORT_RQ, 'Evt16'),
}
