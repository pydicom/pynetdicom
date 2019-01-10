"""Implementation of the Transport Service."""

import select
import socket
from struct import unpack


# Transport events
# No enum in python 2.7 so lets use tuples instead
EVT_TRANSPORT_OPEN = ('TRANSPORT', 'OPEN')
EVT_TRANSPORT_CLOSED = ('TRANSPORT', 'CLOSED')

# Socket modes
SOCKET_MODE_CLIENT = "client"
SOCKET_MODE_SERVER = "server"
SOCKET_MAXIMUM_QUEUE = 1


# Transport primitives
CONNECTION_INDICATION = None
CONNECTION_CONFIRMATION = None
CONNECTION_OPEN = None
CONNECTION_CLOSED = None


class TransportService(object):
    def __init__(self):
        pass

    def register_callback(self, event, callback):
        pass

    def unregister_callback(self, event, callback):
        pass

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

    def open_connection(self, assoc):
        """TRANSPORT_CONNECT received by transport service.

        Open connection to remote.

        returns a client socket
        """
        sock = TransportSocket(assoc)

        return sock.connect((addr, port))

    def close_connection(self, assoc):
        pass

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
    def __init__(self, assoc):
        self._mode = None
        self._socket = None
        self._local = None
        self._remote = None
        self._assoc = assoc

        self.select_timeout = 0.5
        self.network_timeout = 60

    @property
    def assoc(self):
        return self._assoc

    @property
    def local(self):
        return self._local

    @property
    def remote(self):
        return self._remote

    @property
    def is_client(self):
        return self._mode == SOCKET_MODE_CLIENT

    @property
    def is_server(self):
        return self._mode == SOCKET_MODE_SERVER

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

    @property
    def socket(self):
        """Return the socket, something something.

        **Events Emitted**

        - None
        - Evt17: Transport connection closed

        Parameters
        ----------
        network_timeout : float
            The timeout (in seconds) for socket.recv() calls. Doesn't affect
            socket.accept() calls.
        """
        if self._socket is None:
            self._socket = self._create_socket()

        return self._socket

    def _create_socket(self):
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
        timeout_seconds = floor(self.network_timeout)
        timeout_microsec = int(self.network_timeout % 1 * 1000)
        sock.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_RCVTIMEO,
            pack('ll', timeout_seconds, timeout_microsec)
        )

        return sock

    def connect(self, (addr, port)):
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
        if self.is_server:
            raise RuntimeError("The socket is in server mode")

        try:
            # Try and connect to remote at (address, port)
            #   raises socket.error if connection refused
            self.socket.connect((addr, port))
            self._mode = SOCKET_MODE_CLIENT
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

    def bind(self, (addr, port)):
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
            True if the connection is listening, False otherwise.
        """
        if self.is_client:
            raise RuntimeError("The socket is in client mode")

        try:
            # Bind the socket to an (address, port)
            #   If address is '' then the socket is reachable by any
            #   address the machine may have, otherwise is visible only on that
            #   address
            self.socket.bind((addr, port))
            # Listen for connections made to the socket
            # socket.listen() says to queue up to as many as N connect requests
            #   before refusing outside connections
            self.socket.listen(SOCKET_MAXIMUM_QUEUE)
            self._mode = SOCKET_MODE_SERVER
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

    def close(self):
        if self._socket is None:
            return

        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except (socket.error):
            pass

        self._socket.close()
        self._socket = None

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

    @property
    def event_queue(self):
        return self.assoc.dul.event_queue



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
