"""Implementation of the Transport Service."""
import asyncio

from copy import deepcopy
from datetime import datetime
import logging
import socket

import pynetdicom

try:
    import ssl
    _HAS_SSL = True
except ImportError:
    _HAS_SSL = False

from pynetdicom import evt, _config
from pynetdicom._globals import MODE_ACCEPTOR
from pynetdicom._handlers import (
    standard_dimse_recv_handler, standard_dimse_sent_handler,
    standard_pdu_recv_handler, standard_pdu_sent_handler,
)


LOGGER = logging.getLogger('pynetdicom.transport')


class AssociationStream:
    """A wrapper for a StreamReader and StreamWriter objects.

    .. versionadded:: 1.2

    Provides an interface for transport that is integrated
    nicely with an :class:`~pynetdicom.association.Association` instance
    and the state machine.

    Attributes
    ----------
    select_timeout : float or None
        The timeout (in seconds) that :func:`select.select` calls in
        :meth:`ready` will block for (default ``0.5``). A value of ``0``
        specifies a poll and never blocks. A value of ``None`` blocks until a
        connection is ready.
    transport : asyncio.transport or None
        The wrapped transport, will be ``None`` if :meth:`close` is called.
    """
    def __init__(self, assoc, reader, writer):
        """Create a new :class:`AssociationStream`.

        Parameters
        ----------
        assoc : association.Association
            The :class:`~pynetdicom.association.Association` instance that will
            be using the socket to communicate.
        transport : asyncio.transport, optional
            The ``asyncio.transport`` to wrap
        """
        self._assoc = assoc

        self._is_connected = True

        self._reader = reader
        self._writer = writer

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

        Sets :attr:`AssociationStream.socket` to ``None`` once complete.

        **Events Emitted**

        - Evt17: Transport connection closed
        """
        if self._writer is None or self._is_connected is False:
            return

        self._writer.close()
        self._writer = None
        self._reader = None
        self._is_connected = False
        # Evt17: Transport connection closed
        self.event_queue.put('Evt17')

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
        if self._writer is None or self._is_connected is False:
            return False

        # TODO: not sure if this is a good idea
        return self._writer._transport.is_reading()

    async def recv(self, nr_bytes):
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
        await self._reader.read(nr_bytes)

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
        self._writer.write(bytestream)
        evt.trigger(self.assoc, evt.EVT_DATA_SENT, {'data' : bytestream})

    # TODO: make tls work
    @property
    def tls_args(self):
        """Return the TLS context and hostname (if set) or ``None``.

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
        return self._tls_args

    @tls_args.setter
    def tls_args(self, tls_args):
        """Set the TLS arguments for the socket."""
        if not _HAS_SSL:
            raise RuntimeError(
                "Your Python installation lacks support for SSL"
            )

        self._tls_args = tls_args


class AssociationProtocol(asyncio.streams.StreamReaderProtocol):
    def __init__(self, server):
        self._assoc = None
        self._stream = None
        self._server = server

        super().__init__(
            stream_reader=asyncio.StreamReader(),
            client_connected_cb=self._handle_connection
        )

    async def _handle_connection(self, reader, writer):
        """Handle an association request.

        * Creates a new Association acceptor instance and configures it.
        * Sets the Association's socket to the request's socket.
        * Starts the Association reactor.
        """
        self._create_association(reader=reader, writer=writer)
        # Trigger must be after binding the events
        evt.trigger(
            self._assoc, evt.EVT_CONN_OPEN, {'address' : self.remote}
        )
        self._server._active_connections.append(self)
        await self._assoc.start()

    @property
    def ae(self):
        """Return the server's parent AE."""
        return self._server.ae

    @property
    def local(self):
        """Return a 2-tuple of the local server's ``(host, port)`` address."""
        return self._server.address

    @property
    def remote(self):
        """Return a 2-tuple of the remote client's ``(host, port)`` address."""
        return self._stream._writer.get_extra_info('peername')

    def _create_association(self, reader, writer):
        """Create an :class:`Association` object for the current request.

        .. versionadded:: 1.5
        """
        from pynetdicom.association import Association

        self._assoc = assoc = Association(self.ae, MODE_ACCEPTOR)
        assoc._server = self._server

        # Set the thread name
        timestamp = datetime.strftime(datetime.now(), "%Y%m%d%H%M%S")
        assoc.name = f"AcceptorThread@{timestamp}"

        self._stream = stream = AssociationStream(assoc, reader, writer)
        # TODO: create stream
        # assoc.set_stream(stream)

        # Association Acceptor object -> local AE
        assoc.acceptor.maximum_length = self.ae.maximum_pdu_size
        assoc.acceptor.ae_title = self._server.ae_title
        assoc.acceptor.address = self.local[0]
        assoc.acceptor.port = self.local[1]
        assoc.acceptor.implementation_class_uid = (
            self.ae.implementation_class_uid
        )
        assoc.acceptor.implementation_version_name = (
            self.ae.implementation_version_name
        )
        assoc.acceptor.supported_contexts = deepcopy(self._server.contexts)

        # Association Requestor object -> remote AE
        assoc.requestor.address = self.remote[0]
        assoc.requestor.port = self.remote[1]

        # Bind events to handlers
        for event in self._server._handlers:
            # Intervention events
            if event.is_intervention and self._server._handlers[event]:
                assoc.bind(event, *self._server._handlers[event])
            elif event.is_notification:
                for handler in self._server._handlers[event]:
                    assoc.bind(event, *handler)
        return assoc, stream


    def connection_lost(self, exc):
        super().connection_lost(exc)
        self._stream.close()
        self._server._active_connections.remove(self)


class AssociationServer:
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
        self.ssl_context = ssl_context
        self.address = address

        # active connections (aka protocols) are stored here
        self._active_connections = []

        self.timeout = 60

        # Stores all currently bound event handlers so future
        #   Associations can be bound
        self._handlers = {}
        self._bind_defaults()

        # Bind the functions to their events
        for evt_hh_args in (evt_handlers or {}):
            self.bind(*evt_hh_args)


    def __call__(self):
        return AssociationProtocol(server=self)

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
        return [x._assoc for x in self._active_connections if x._is_connected]

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

    @property
    def ssl_context(self):
        """Return the :class:`ssl.SSLContext` (if available).

        Parameters
        ----------
        context : ssl.SSLContext or None
            If TLS is to be used then this should be the
            :class:`ssl.SSLContext` used to wrap the client sockets, otherwise
            if ``None`` then no TLS will be used (default).
        """
        return self._ssl_context

    @ssl_context.setter
    def ssl_context(self, context):
        """Set the SSL context for the socket."""
        if not _HAS_SSL:
            raise RuntimeError(
                "Your Python installation lacks support for SSL"
            )

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

    async def serve_forever(self):
        loop = asyncio.get_event_loop()
        server = await loop.create_server(
            self, '127.0.0.1', 4242
        )
        async with server:
            await server.serve_forever()
