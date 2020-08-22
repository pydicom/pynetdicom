"""Implementation of the Transport Service."""

from copy import deepcopy
from datetime import datetime
import logging
import select
import socket
try:
    from SocketServer import TCPServer, ThreadingMixIn, BaseRequestHandler
except ImportError:
    from socketserver import TCPServer, ThreadingMixIn, BaseRequestHandler
try:
    import ssl
    _HAS_SSL = True
except ImportError:
    _HAS_SSL = False
from struct import pack
import threading

from pynetdicom import evt, _config
from pynetdicom._globals import MODE_ACCEPTOR
from pynetdicom._handlers import (
    standard_dimse_recv_handler, standard_dimse_sent_handler,
    standard_pdu_recv_handler, standard_pdu_sent_handler,
)


LOGGER = logging.getLogger('pynetdicom.transport')


class AssociationSocket(object):
    """A wrapper for a :pyd:`socket<3/library/socket.html#socket-objects>`
    object.

    .. versionadded:: 1.2

    Provides an interface for :pyd:`socket
    <3/library/socket.html#socket-objects>` that is integrated nicely
    with an :class:`~pynetdicom.association.Association` instance and the
    state machine.

    Attributes
    ----------
    select_timeout : float or None
        The timeout (in seconds) that :func:`select.select` calls in
        :meth:`ready` will block for (default ``0.5``). A value of ``0``
        specifies a poll and never blocks. A value of ``None`` blocks until a
        connection is ready.
    socket : socket.socket or None
        The wrapped socket, will be ``None`` if :meth:`close` is called.
    tls_args : 2-tuple or None
        If the socket should be wrapped by TLS then this is
        ``(context, hostname)``, where *context* is a :class:`ssl.SSLContext`
        that will be used to wrap the socket and *hostname* is the value to
        use for the *server_hostname* keyword argument for
        :meth:`SSLContext.wrap_socket()<ssl.SSLContext.wrap_socket>`. If TLS
        is not to be used then ``None`` (default).
    """
    def __init__(self, assoc, client_socket=None, address=('', 0)):
        """Create a new :class:`AssociationSocket`.

        Parameters
        ----------
        assoc : association.Association
            The :class:`~pynetdicom.association.Association` instance that will
            be using the socket to communicate.
        client_socket : socket.socket, optional
            The :pyd:`socket<3/library/socket.html#socket-objects>` to wrap,
            if not supplied then a new socket will be created instead.
        address : 2-tuple, optional
            If *client_socket* is ``None`` then this is the ``(host, port)`` to
            bind the newly created socket to, which by default will be
            ``('', 0)``.
        """
        self._assoc = assoc

        if client_socket is not None and address != ('', 0):
            LOGGER.warning(
                "AssociationSocket instantiated with both a 'client_socket' "
                "and bind 'address'. The original socket will not be rebound"
            )

        if client_socket is None:
            self.socket = self._create_socket(address)
            self._is_connected = False
        else:
            self.socket = client_socket
            self._is_connected = True
            # Evt5: Transport connection indication
            self.event_queue.put('Evt5')

        self._tls_args = None
        self.select_timeout = 0.5

    @property
    def assoc(self):
        """Return the parent :class:`~pynetdicom.association.Association`
        instance.
        """
        return self._assoc

    def close(self):
        """Close the connection to the peer and shutdown the socket.

        Sets :attr:`AssociationSocket.socket` to ``None`` once complete.

        **Events Emitted**

        - Evt17: Transport connection closed
        """
        if self.socket is None or self._is_connected is False:
            return

        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except socket.error:
            pass

        self.socket.close()
        self.socket = None
        self._is_connected = False
        # Evt17: Transport connection closed
        self.event_queue.put('Evt17')

    def connect(self, address):
        """Try and connect to a remote at `address`.

        **Events Emitted**

        - Evt2: Transport connection confirmed
        - Evt17: Transport connection closed

        Parameters
        ----------
        address : 2-tuple
            The ``(host, port)`` IPv4 address to connect to.
        """
        if self.socket is None:
            self.socket = self._create_socket()

        try:
            if self.tls_args:
                context, server_hostname = self.tls_args
                self.socket = context.wrap_socket(
                    self.socket,
                    server_side=False,
                    server_hostname=server_hostname,
                )
            # Try and connect to remote at (address, port)
            #   raises socket.error if connection refused
            self.socket.connect(address)
            # Trigger event - connection open
            evt.trigger(self.assoc, evt.EVT_CONN_OPEN, {'address' : address})
            self._is_connected = True
            # Evt2: Transport connection confirmation
            self.event_queue.put('Evt2')
        except (socket.error, socket.timeout) as exc:
            # Log connection failure
            LOGGER.error(
                "Association request failed: unable to connect to remote"
            )
            LOGGER.error("TCP Initialisation Error: Connection refused")
            # Log exception if TLS issue to help with troubleshooting
            if isinstance(exc, ssl.SSLError):
                LOGGER.exception(exc)

            # Don't be tempted to replace this with a self.close() call -
            #   it doesn't work because `_is_connected` is False
            if self.socket:
                try:
                    self.socket.shutdown(socket.SHUT_RDWR)
                except:
                    pass
                self.socket.close()
                self.socket = None
            self.event_queue.put('Evt17')

    def _create_socket(self, address=('', 0)):
        """Create a new IPv4 TCP socket and set it up for use.

        *Socket Options*

        - ``SO_REUSEADDR`` is 1
        - ``SO_RCVTIMEO`` is set to the Association's ``network_timeout``
          value.

        Parameters
        ----------
        address : 2-tuple, optional
            The ``(host, port)`` to bind the socket to. By default the socket
            is bound to ``('', 0)``, i.e. the first available port.

        Returns
        -------
        socket.socket
            A bound and unconnected socket instance.
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
        if self.assoc.network_timeout is not None:
            timeout_seconds = int(self.assoc.network_timeout)
            timeout_microsec = int(self.assoc.network_timeout % 1 * 1000)
            sock.setsockopt(
                socket.SOL_SOCKET,
                socket.SO_RCVTIMEO,
                pack('ll', timeout_seconds, timeout_microsec)
            )

        sock.bind(address)

        self._is_connected = False

        return sock

    @property
    def event_queue(self):
        """Return the :class:`~pynetdicom.association.Association`'s event
        queue.
        """
        return self.assoc.dul.event_queue

    def get_local_addr(self, host=('10.255.255.255', 1)):
        """Return an address for the local computer as :class:`str`.

        Parameters
        ----------
        host : tuple
            The host's (*addr*, *port*) when trying to determine the local
            address.
        """
        # Solution from https://stackoverflow.com/a/28950776
        temp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # We use `host` to allow unit testing
            temp.connect(host)
            addr = temp.getsockname()[0]
        except:
            addr = '127.0.0.1'
        finally:
            temp.close()

        return addr

    @property
    def ready(self):
        """Return ``True`` if there is data available to be read.

        *Events Emitted*

        - None
        - Evt17: Transport connection closed

        Returns
        -------
        bool
            ``True`` if the socket has data ready to be read, ``False``
            otherwise.
        """
        if self.socket is None or self._is_connected is False:
            return False

        try:
            # Use a timeout of 0 so we get an "instant" result
            ready, _, _ = select.select([self.socket], [], [], 0)
        except (socket.error, socket.timeout, ValueError):
            # Evt17: Transport connection closed
            self.event_queue.put('Evt17')
            return False

        # An SSLSocket may have buffered data available that `select`
        # is unaware of - see #528
        if _HAS_SSL and isinstance(self.socket, ssl.SSLSocket):
            return bool(ready) or bool(self.socket.pending())

        return bool(ready)

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
        """Try and send the data in `bytestream` to the remote.

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
                nr_sent = self.socket.send(bytestream[total_sent:])
                total_sent += nr_sent

            evt.trigger(self.assoc, evt.EVT_DATA_SENT, {'data' : bytestream})
        except (socket.error, socket.timeout):
            # Evt17: Transport connection closed
            self.event_queue.put('Evt17')

    def __str__(self):
        """Return the string output for ``socket``."""
        return self.socket.__str__()

    @property
    def tls_args(self):
        """Return the TLS context and hostname (if set) or ``None``."""
        return self._tls_args

    @tls_args.setter
    def tls_args(self, tls_args):
        """Set the TLS arguments for the socket.

        Parameters
        ----------
        tls_args : 2-tuple
            If the socket should be wrapped by TLS then this is
            ``(context, hostname)``, where *context* is a
            :class:`ssl.SSLContext` that will be used to wrap the socket and
            *hostname* is the value to use for the *server_hostname* keyword
            argument for :meth:`SSLContext.wrap_socket()
            <ssl.SSLContext.wrap_socket>`.
        """
        if not _HAS_SSL:
            raise RuntimeError(
                "Your Python installation lacks support for SSL"
            )

        self._tls_args = tls_args


class RequestHandler(BaseRequestHandler):
    """Connection request handler for the ``AssociationServer``.

    .. versionadded:: 1.2

    Attributes
    ----------
    client_address : 2-tuple
        The ``(host, port)`` of the remote.
    request : socket.socket
        The (unaccepted) client socket.
    server : transport.AssociationServer or transport.ThreadedAssociationServer
        The server that received the connection request.
    """
    @property
    def ae(self):
        """Return the server's parent AE."""
        return self.server.ae

    def handle(self):
        """Handle an association request.

        * Creates a new Association acceptor instance and configures it.
        * Sets the Association's socket to the request's socket.
        * Starts the Association reactor.
        """
        assoc = self._create_association()

        # Trigger must be after binding the events
        evt.trigger(
            assoc, evt.EVT_CONN_OPEN, {'address' : self.client_address}
        )

        assoc.start()

    @property
    def local(self):
        """Return a 2-tuple of the local server's ``(host, port)`` address."""
        return self.server.server_address

    @property
    def remote(self):
        """Return a 2-tuple of the remote client's ``(host, port)`` address."""
        return self.client_address

    def _create_association(self):
        """Create an :class:`Association` object for the current request.

        .. versionadded:: 1.5
        """
        from pynetdicom.association import Association

        assoc = Association(self.ae, MODE_ACCEPTOR)
        assoc._server = self.server

        # Set the thread name
        timestamp = datetime.strftime(datetime.now(), "%Y%m%d%H%M%S")
        assoc.name = "AcceptorThread@{}".format(timestamp)

        sock = AssociationSocket(assoc, client_socket=self.request)
        assoc.set_socket(sock)

        # Association Acceptor object -> local AE
        assoc.acceptor.maximum_length = self.ae.maximum_pdu_size
        assoc.acceptor.ae_title = self.server.ae_title
        assoc.acceptor.address = self.local[0]
        assoc.acceptor.port = self.local[1]
        assoc.acceptor.implementation_class_uid = (
            self.ae.implementation_class_uid
        )
        assoc.acceptor.implementation_version_name = (
            self.ae.implementation_version_name
        )
        assoc.acceptor.supported_contexts = deepcopy(self.server.contexts)

        # Association Requestor object -> remote AE
        assoc.requestor.address = self.remote[0]
        assoc.requestor.port = self.remote[1]

        # Bind events to handlers
        for event in self.server._handlers:
            # Intervention events
            if event.is_intervention and self.server._handlers[event]:
                assoc.bind(event, *self.server._handlers[event])
            elif event.is_notification:
                for handler in self.server._handlers[event]:
                    assoc.bind(event, *handler)
        return assoc


class AssociationServer(TCPServer):
    """An Association server implementation.

    .. versionadded:: 1.2

    .. versionchanged:: 1.5

        Added `request_handler` keyword parameter.

    Any attempts to connect will be assumed to be from association requestors.

    The server should be started with
    :meth:`serve_forever(poll_interval)<AssociationServer.serve_forever>`,
    where *poll_interval* is the timeout (in seconds) that the
    :func:`select.select` call will block for (default ``0.5``). A value of
    ``0`` specifies a poll and never blocks. A value of ``None`` blocks until
    a connection is ready.

    Attributes
    ----------
    ae : ae.ApplicationEntity
        The parent AE that is running the server.
    request_queue_size : int
        Default ``5``.
    server_address : 2-tuple
        The ``(host, port)`` that the server is running on.
    ssl_context : ssl.SSLContext or None
        The :class:`ssl.SSLContext` used to wrap client sockets, or ``None`` if
        no TLS is required (default).
    """
    def __init__(self, ae, address, ae_title, contexts, ssl_context=None,
                 evt_handlers=None, request_handler=None):
        """Create a new :class:`AssociationServer`, bind a socket and start
        listening.

        Parameters
        ----------
        ae : ae.ApplicationEntity
            The parent AE that's running the server.
        address : 2-tuple
            The ``(host, port)`` that the server should run on.
        ae_title : bytes
            The AE title of the SCP.
        contexts : list of presentation.PresentationContext
            The SCPs supported presentation contexts.
        ssl_context : ssl.SSLContext, optional
            If TLS is to be used then this should be the
            :class:`ssl.SSLContext` used to wrap the client sockets, otherwise
            if ``None`` then no TLS will be used (default).
        evt_handlers : list of 2- or 3-tuple, optional
            A list of ``(event, callable)`` or ``(event, callable, args)``,
            the *callable* function to run when *event* occurs and the
            optional extra *args* to pass to the callable.
        request_handler : type
            The request handler class; an instance of this class
            is created for each request. Should be a subclass of
            :class:`~socketserver.BaseRequestHandler`.
        """
        self.ae = ae
        self.ae_title = ae_title
        self.contexts = contexts
        # Cover Python 2: old style class
        if ssl_context and not _HAS_SSL:
            raise RuntimeError(
                "Your Python installation lacks support for SSL"
            )
        self.ssl_context = ssl_context
        self.allow_reuse_address = True

        request_handler = request_handler or RequestHandler
        TCPServer.__init__(
            self, address, request_handler, bind_and_activate=True
        )

        self.timeout = 60

        # Stores all currently bound event handlers so future
        #   Associations can be bound
        self._handlers = {}
        self._bind_defaults()

        # Bind the functions to their events
        for evt_hh_args in (evt_handlers or {}):
            self.bind(*evt_hh_args)

    def bind(self, event, handler, args=None):
        """Bind a callable `handler` to an `event`.

        .. versionadded:: 1.3

        .. versionchanged:: 1.5

            Added `args` keyword parameter.

        Parameters
        ----------
        event : namedtuple
            The event to bind the function to.
        handler : callable
            The function that will be called if the event occurs.
        args : list, optional
            Optional extra arguments to be passed to the handler (default:
            no extra arguments passed to the handler).
        """
        # Notification events - multiple handlers allowed
        if event.is_notification:
            if event not in self._handlers:
                self._handlers[event] = []

            if (handler, args) not in self._handlers[event]:
                self._handlers[event].append((handler, args))

        # Intervention events - only one handler allowed
        if event.is_intervention:
            self._handlers[event] = (handler, args)

        # Bind our child Association events
        for assoc in self.active_associations:
            assoc.bind(event, handler, args)

    def _bind_defaults(self):
        """Bind the default event handlers."""
        # Intervention event handlers
        for event in evt._INTERVENTION_EVENTS:
            handler = evt.get_default_handler(event)
            self.bind(event, handler)

        # Notification event handlers
        if _config.LOG_HANDLER_LEVEL == 'standard':
            self.bind(evt.EVT_DIMSE_RECV, standard_dimse_recv_handler)
            self.bind(evt.EVT_DIMSE_SENT, standard_dimse_sent_handler)
            self.bind(evt.EVT_PDU_RECV, standard_pdu_recv_handler)
            self.bind(evt.EVT_PDU_SENT, standard_pdu_sent_handler)

    @property
    def active_associations(self):
        """Return the server's running
        :class:`~pynetdicom.association.Association` acceptor instances
        """
        # Find all AcceptorThreads with `_server` as self
        threads = [
            tt for tt in threading.enumerate() if 'AcceptorThread' in tt.name
        ]
        return [tt for tt in threads if tt._server is self]

    def get_events(self):
        """Return a list of currently bound events.

        .. versionadded:: 1.3
        """
        return sorted(self._handlers.keys(), key=lambda x: x.name)

    def get_handlers(self, event):
        """Return handlers bound to a specific `event`.

        .. versionadded:: 1.3

        .. versionchanged:: 1.5

            Returns a 2-tuple of (callable, args) or list of 2-tuple.

        Parameters
        ----------
        event : namedtuple
            The event bound to the handlers.

        Returns
        -------
        2-tuple of (callable, args), list of 2-tuple
            If the event is a notification event then returns a list of
            2-tuples containing the callable functions bound to `event` and
            the arguments passed to the callable as ``(callable, args)``. If
            the event is an intervention event then returns either a 2-tuple of
            (callable, args) if a handler is bound to the event or
            ``(None, None)`` if no handler has been bound.
        """
        if event not in self._handlers:
            return []

        return self._handlers[event]

    def get_request(self):
        """Handle a connection request.

        If :attr:`~AssociationServer.ssl_context` is set then the client socket
        will be wrapped using
        :meth:`SSLContext.wrap_socket()<ssl.SSLContext.wrap_socket>`.

        Returns
        -------
        client_socket : socket.socket
            The connection request.
        address : 2-tuple
            The client's address as ``(host, port)``.
        """
        client_socket, address = self.socket.accept()
        if self.ssl_context:
            client_socket = self.ssl_context.wrap_socket(client_socket,
                                                         server_side=True)

        return client_socket, address

    def process_request(self, request, client_address):
        """Process a connection request."""
        self.finish_request(request, client_address)

    def server_bind(self):
        """Bind the socket and set the socket options.

        - ``socket.SO_REUSEADDR`` is set to ``1``
        - ``socket.SO_RCVTIMEO`` is set to
          :attr:`AE.network_timeout
          <pynetdicom.ae.ApplicationEntity.network_timeout>` unless the
          value is ``None`` in which case it will be left unset.
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
        if self.ae.network_timeout is not None:
            timeout_seconds = int(self.ae.network_timeout)
            timeout_microsec = int(self.ae.network_timeout % 1 * 1000)
            self.socket.setsockopt(
                socket.SOL_SOCKET,
                socket.SO_RCVTIMEO,
                pack('ll', timeout_seconds, timeout_microsec)
            )

        # Bind the socket to an (address, port)
        #   If address is '' then the socket is reachable by any
        #   address the machine may have, otherwise is visible only on that
        #   address
        self.socket.bind(self.server_address)
        self.server_address = self.socket.getsockname()

    def server_close(self):
        """Close the server."""
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except socket.error:
            pass

        self.socket.close()

    def shutdown(self):
        """Completely shutdown the server and close it's socket."""
        # Can't use super() due to Python 2.7 compatibility
        TCPServer.shutdown(self)
        self.server_close()
        self.ae._servers.remove(self)

    @property
    def ssl_context(self):
        """Return the :class:`ssl.SSLContext` (if available)."""
        return self._ssl_context

    @ssl_context.setter
    def ssl_context(self, context):
        """Set the SSL context for the socket.

        Parameters
        ----------
        context : ssl.SSLContext or None
            If TLS is to be used then this should be the
            :class:`ssl.SSLContext` used to wrap the client sockets, otherwise
            if ``None`` then no TLS will be used (default).
        """
        # TODO: Uncomment when no longer supporting Python 2
        #if not _HAS_SSL:
        #    raise RuntimeError(
        #        "Your Python installation lacks support for SSL"
        #    )

        self._ssl_context = context

    def unbind(self, event, handler):
        """Unbind a callable `handler` from an `event`.

        .. versionadded:: 1.3

        Parameters
        ----------
        event : 3-tuple
            The event to unbind the function from.
        handler : callable
            The function that will no longer be called if the event occurs.
        """
        if event not in self._handlers:
            return

        # Notification events
        if event.is_notification:
            handlers = [hh[0] for hh in self._handlers[event]]
            try:
                ii = handlers.index(handler)
                del self._handlers[event][ii]
            except ValueError:
                pass

            if not self._handlers[event]:
                del self._handlers[event]

        # Intervention events - unbind and replace with default
        if event.is_intervention and handler in self._handlers[event]:
            self._handlers[event] = (evt.get_default_handler(event), None)

        # Unbind from our child Association events
        for assoc in self.active_associations:
            assoc.unbind(event, handler)


class ThreadedAssociationServer(ThreadingMixIn, AssociationServer):
    """An :class:`AssociationServer` suitable for threading.

    .. versionadded:: 1.2
    """
    def process_request_thread(self, request, client_address):
        """Process a connection request."""
        # pylint: disable=broad-except
        try:
            self.finish_request(request, client_address)
        except Exception:
            self.handle_error(request, client_address)
            self.shutdown_request(request)
