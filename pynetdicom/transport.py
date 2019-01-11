"""Implementation of the Transport Service."""

from copy import deepcopy
from math import floor
import select
import socket
from socketserver import TCPServer, ThreadingMixIn, BaseRequestHandler
import ssl
from struct import pack, unpack
import time

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


# Transport primitives
CONNECT_REQUEST = None
CONNECT_RESPONSE = None


##### NEW HOTNESS


class AssociationSocket(object):
    """A wrapper for the socket.socket object.

    Provides an interface for socket.socket that is integrated nicely with a
    pynetdicom Association instance and the state machine.

    Attributes
    ----------
    socket : socket.socket or None
        The wrapped socket, will be None if AssociationSocket.close() is called.
    tls_kwargs : dict
        If the socket should be wrapped by TLS then this is the keyword
        arguments for ssl.wrap_socket, excluding `server_side`. By default
        TLS is not used.
    """
    def __init__(self, assoc, socket=None):
        """Create a new AssociationSocket.

        Parameters
        ----------
        assoc : association.Association
            The Association instance that will be using the socket to
            communicate.
        """
        self._assoc = assoc

        if socket is None:
            self.socket = self._create_socket()
        else:
            self.socket = socket
            # Evt5: Transport connection indication
            self.event_queue.put('Evt5')

        #print('init', self.socket)
        self.tls_kwargs = self.assoc._tls_kwargs or {}
        self.select_timeout = 0.5

    @property
    def assoc(self):
        """Return the socket's parent Association instance."""
        return self._assoc

    def close(self):
        """Close the connection to the peer and shutdown the socket.

        Sets ``AssociationSocket.socket`` to ``None`` once complete.

        *Events Emitted*

        - Evt17: Transport connection closed
        """
        if self.socket is None:
            return

        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except (socket.error):
            pass

        self.socket.close()
        self.socket = None
        self.event_queue.put('Evt17')

    def connect(self, address):
        """Try and connect to a remote.

        **Events Emitted**

        - Evt2: Transport connection confirmed
        - Evt17: Transport connection closed

        Parameters
        ----------
        address : 2-tuple
            The (host, port) IPv4 address to connect to.
        """
        if self.socket is None and self.is_requestor:
            self.socket = self._create_socket()

        try:
            if self.tls_kwargs:
                self.socket = ssl.wrap_socket(self.socket,
                                              server_side=False,
                                              **self.tls_kwargs)
            # Try and connect to remote at (address, port)
            #   raises socket.error if connection refused
            self.socket.connect(address)
            # Evt2: Transport connection confirmation
            self.event_queue.put('Evt2')
        except (socket.error, socket.timeout):
            if self.socket is not None:
                self.socket.close()
            # Evt17: Transport connection closed
            self.event_queue.put('Evt17')

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

        return sock

    @property
    def event_queue(self):
        """Return the Association's event queue."""
        return self.assoc.dul.event_queue

    @property
    def is_acceptor(self):
        return self.assoc.is_acceptor

    @property
    def is_requestor(self):
        return self.assoc.is_requestor

    @property
    def ready(self):
        """Return True if there is data available to be read.

        *Events Emitted*

        - None
        - Evt17: Transport connection closed

        Returns
        -------
        bool
            True if the socket has data ready to be read, False otherwise.
        """
        try:
            ready, _, _ = select.select([self.socket], [], [], 0.5)
        except (socket.error, socket.timeout, ValueError):
            #    # Evt17: transport connection closed indication
            #    print('socket.ready failed')
            #    self.event_queue.put('Evt17')
            return False

        return ready

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
            # Note: anything calling recv
            if not bytes_read:
                return bytestream

            bytestream.extend(bytes_read)
            nr_read += len(bytes_read)

        return bytestream

    def send(self, bytestream):
        """Try and send `bystream` to the remote.

        *Events Emitted*

        - None
        - Evt17: Transport connected closed.

        Parameters
        ----------
        bytestream : bytes
            The data to send to the remote.
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
            self.event_queue.put('Evt17')


class RequestHandler(BaseRequestHandler):
    def handle(self):
        """Handle an association request."""
        # self.request = request
        # self.client_address = client_address
        # self server = instance
        from pynetdicom.association import Association

        ae = self.server.ae

        assoc = Association(ae, MODE_ACCEPTOR)
        assoc.acse_timeout = ae.acse_timeout
        assoc.dimse_timeout = ae.dimse_timeout
        assoc.network_timeout = ae.network_timeout
        assoc.dul.socket = AssociationSocket(assoc, self.request)

        # Association Acceptor object -> local AE
        assoc.acceptor.maximum_length = ae.maximum_pdu_size
        assoc.acceptor.ae_title = ae.ae_title
        assoc.acceptor.address = self.server.server_address[0]
        assoc.acceptor.port = self.server.server_address[1]
        assoc.acceptor.implementation_class_uid = (
            ae.implementation_class_uid
        )
        assoc.acceptor.implementation_version_name = (
            ae.implementation_version_name
        )
        assoc.acceptor.supported_contexts = deepcopy(ae.supported_contexts)

        # Association Requestor object -> remote AE
        assoc.requestor.address = self.client_address[0]
        assoc.requestor.port = self.client_address[1]

        assoc.start()

        ae.active_associations.append(assoc)


class AssociationServer(TCPServer):
    """An Association server implementation.

    Any attempts to connect will be assumed to be from association requestors.

    The server should be started with ``serve_forever(poll_interval)``, where
    ``poll_interval`` is the timeout (in seconds) that the ``select.select()``
    call will block for (default 0.5). A value of 0 specifies a poll and never
    blocks. A value of None blocks until a connection is ready.

    Attributes
    ----------
    ae : ae.ApplicationEntity
        The parent AE that is running the server.
    server_address : 2-tuple
        The (host, port) that the server is running on.
    tls_kwargs : dict
        A dict containing keyword arguments used with ssl.wrap_socket().
    request_queue_size : int
        Default 5.
    """
    def __init__(self, ae, tls_kwargs=None):
        """Create a new AssociationServer, bind a socket and start listening.

        Parameters
        ----------
        ae : ae.ApplicationEntity
            The parent AE that's running the server.
        address : 2-tuple
            The (host, port) that the server should run on.
        tls_kwargs : dict, optional
            If TLS is to be used then this should be a dict containing the
            keyword arguments to be used with ssl.wrap_socket().
        """
        self.ae = ae
        self.tls_kwargs = tls_kwargs or {}
        self.allow_reuse_address = True

        super(AssociationServer, self).__init__(
            (ae.bind_addr, ae.port),
            RequestHandler,
            bind_and_activate=True
        )

        self.timeout = 60

    def server_bind(self):
        """Bind the socket and set the socket options.

        socket.SO_REUSEADDR is set to 1
        socket.SO_RCVTIMEO is set to AE.network_timeout
        """
        # SO_REUSEADDR: reuse the socket in TIME_WAIT state without
        #   waiting for its natural timeout to expire
        #   Allows local address reuse
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # If no timeout is set then recv() will block forever if
        #   the connection is kept alive with no data sent
        # SO_RCVTIMEO: the timeout on receive calls in seconds
        #   set using a packed binary string containing two uint32s as
        #   (seconds, microseconds)
        #timeout_seconds = floor(self.ae.network_timeout)
        #timeout_microsec = int(self.ae.network_timeout % 1 * 1000)
        timeout_seconds = 60
        timeout_microsec = 0
        self.socket.setsockopt(socket.SOL_SOCKET,
                               socket.SO_RCVTIMEO,
                               pack('ll', timeout_seconds, timeout_microsec))

        # Bind the socket to an (address, port)
        #   If address is '' then the socket is reachable by any
        #   address the machine may have, otherwise is visible only on that
        #   address
        self.socket.bind(self.server_address)
        self.server_address = self.socket.getsockname()

    def get_request(self):
        """Handle a connection request.

        If ``tls_kwargs`` is set then the client socket will be wrapped using
        ``ssl.wrap_socket()``.

        Returns
        -------
        client_socket : socket._socket
            The connection request.
        address : 2-tuple
            The client's address as (host, port).
        """
        client_socket, address = self.socket.accept()
        if self.tls_kwargs:
            if 'server_side' in self.tls_kwargs:
                del self.tls_kwargs['server_side']
            client_socket = ssl.wrap_socket(client_socket,
                                            server_side=True,
                                            **self.tls_kwargs)

        return client_socket, address

    def process_request(self, request, client_address):
        self.finish_request(request, client_address)

    def server_close(self):
        """Close the server."""
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except socket.error:
            pass

        self.socket.close()


class ThreadedAssociationServer(ThreadingMixIn, AssociationServer):
    """An AssociationServer suitable for threading."""
    pass


##### OLD AND BUSTED

class ServerSocket(object):
    def __init__(self, ae, address, tls_kwargs=None):

        self._local = address
        self._stop_server = False
        self._mode = _SOCKET_MODE_SERVER

        self.socket = None
        self.select_timeout = 0.5

        self._create_socket((addr, port), tls_kwargs or {})

    def _create_socket(self, address, tls_kwargs=None):
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
            if tls_kwargs:
                socket = ssl.wrap_socket(socket, server_side=True, **tls_kwargs)
            socket.bind(address)
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
                        client = AssociationSocket(self.ae)
                        client.socket = self.socket.accept()
                        client.start_as_acceptor()
                    except (socket.error, socket.timeout):
                        if client.socket is not None:
                            client.close()


            except (socket.error, socket.timeout, ValueError):
                return


class StreamServer(object):
    """AE's Association server."""
    def __init__(self, ae):
        self._ae = ae
        self._socket = ServerSocket(ae)


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

    def get_server_socket(self, address, tls_args=None):
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

    def connect(self, address, tls_args):
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

    def _handle_connection(self):
        assoc = Association(mode=MODE_ACCEPTOR)

    def listen(self, address, tls_args):
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
