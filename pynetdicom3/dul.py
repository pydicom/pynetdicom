"""
Implements the DICOM Upper Layer service provider.
"""

import logging
import os
try:
    import queue
except ImportError:
    import Queue as queue  # Python 2 compatibility
import select
import socket
from struct import unpack
from threading import Thread
import time

from pynetdicom3.fsm import StateMachine
from pynetdicom3.pdu import (A_ASSOCIATE_RQ, A_ASSOCIATE_AC, A_ASSOCIATE_RJ,
                             P_DATA_TF, A_RELEASE_RQ, A_RELEASE_RP, A_ABORT_RQ)
from pynetdicom3.pdu_primitives import A_ASSOCIATE, A_RELEASE, A_ABORT, P_DATA
from pynetdicom3.timer import Timer

LOGGER = logging.getLogger('pynetdicom3.dul')


class DULServiceProvider(Thread):
    """
    Three ways to call DULServiceProvider:

    - If a port number is given, the DUL will wait for incoming connections on
      this port.
    - If a socket is given, the DUL will use this socket as the client socket.
    - If neither is given, the DUL will not be able to accept connections (but
      will be able to initiate them.)

    Attributes
    ----------
    artim_timer : pynetdicom3.timer.Timer
        The ARTIM timer
    association : pynetdicom3.association.Association
        The DUL's current Association
    dul_from_user_queue : queue.Queue
        Queue of PDUs from the DUL service user to be processed by the DUL
        provider
    dul_to_user_queue : queue.Queue
        Queue of primitives from the DUL service to be processed by the DUL user
    event_queue : queue.Queue
        List of queued events to be processed by the state machine
    scp_socket : socket.socket()
        If the local AE is acting as an SCP, this is the connection from the
        peer AE to the SCP
    scu_socket : socket.socket()
        If the local AE is acting as an SCU, this is the connection from the
        local AE to the peer AE SCP
    state_machine : pynetdicom3.fsm.StateMachine
        The DICOM Upper Layer's State Machine
    """

    def __init__(self, socket=None, port=None, dul_timeout=None, assoc=None):
        """
        Parameters
        ----------
        socket : socket.socket, optional
            The local AE's listen socket
        port : int, optional
            The port number on which to wait for incoming connections
        dul_timeout : float, optional
            The maximum amount of time to wait for connection responses
            (in seconds)
        assoc : pynetdicom3.association.Association
            The DUL's current Association
        """
        if socket and port:
            raise ValueError("DULServiceProvider can't be instantiated with "
                             "both socket and port parameters")

        # The association thread
        self.assoc = assoc

        Thread.__init__(self)

        # Current primitive and PDU
        self.primitive = None
        self.pdu = None

        # The event_queue tracks the events the DUL state machine needs to
        #   process
        self.event_queue = queue.Queue()

        # These queues provide communication between the DUL service
        #   user and the DUL service provider.
        # An event occurs when the DUL service user adds to
        #   the to_provider_queue
        self.to_provider_queue = queue.Queue()

        # A primitive is sent to the service user when the DUL service provider
        # adds to the to_user_queue.
        self.to_user_queue = queue.Queue()

        # Setup the idle timer, ARTIM timer and finite state machine
        # FIXME: Why do we have an idle timer?
        self._idle_timer = Timer(dul_timeout)

        # ARTIM timer
        self.artim_timer = Timer(dul_timeout)

        # State machine - PS3.8 Section 9.2
        self.state_machine = StateMachine(self)

        if socket:
            # A client socket has been given, so the local AE is acting as
            #   an SCP
            # generate an event 5
            self.event_queue.put('Evt5')
            self.scu_socket = socket
            self.peer_address = None
            self.scp_socket = None
        elif port:
            # A port number has been given, so the local AE is acting as an
            #   SCU. Create a new socket using the given port number
            self.scp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.scp_socket.setsockopt(socket.SOL_SOCKET,
                                       socket.SO_REUSEADDR,
                                       1)

            # The port number for the local AE to listen on
            self.local_port = port
            if self.local_port:
                try:
                    local_address = os.popen('hostname').read()[:-1]
                    self.scp_socket.bind((local_address, self.local_port))
                except Exception as ex:
                    LOGGER.exception(ex)

                self.scp_socket.listen(1)

            else:
                self.scp_socket = None

            self.scu_socket = None
            self.peer_address = None
        else:
            # No port nor socket
            self.scp_socket = None
            self.scu_socket = None
            self.peer_address = None

        self._kill_thread = False
        self.daemon = False

        # Controls the minimum delay between loops in run()
        self._run_loop_delay = 0.001

    def idle_timer_expired(self):
        """
        Checks if the idle timer has expired

        Returns
        -------
        bool
            True if the idle timer has expired, False otherwise
        """
        if self._idle_timer is None:
            return False

        if self._idle_timer.is_expired:
            return True

        return False

    def kill_dul(self):
        """Immediately interrupts the thread"""
        self._kill_thread = True

    def on_receive_pdu(self):
        """Called after the first byte of an incoming PDU is read.
        """
        pass

    def peek_next_pdu(self):
        """Check the next PDU to be processed."""
        try:
            return self.to_user_queue.queue[0]
        except (queue.Empty, IndexError):
            return None

    def receive_pdu(self, wait=False, timeout=None):
        """
        Get the next item to be processed out of the queue of items sent
        from the DUL service provider to the service user

        Parameters
        ----------
        wait : bool, optional
            If `wait` is True and `timeout` is None, blocks until an item
            is available. If `timeout` is a positive number, blocks at most
            `timeout` seconds. Otherwise returns an item if one is immediately
            available.
        timeout : int or None
            See the definition of `Wait`

        Returns
        -------
        queue_item
            The next object in the to_user_queue [FIXME]
        None
            If the queue is empty
        """
        try:
            # Remove and return an item from the queue
            #   If block is True and timeout is None then block until an item
            #       is available.
            #   If timeout is a positive number, blocks timeout seconds and
            #       raises queue.Empty if no item was available in that time.
            #   If block is False, return an item if one is immediately
            #       available, otherwise raise queue.Empty
            queue_item = self.to_user_queue.get(block=wait, timeout=timeout)
            return queue_item
        except queue.Empty:
            return None

    def run(self):
        """
        The main threading.Thread run loop. Runs constantly, checking the
        connection for incoming data. When incoming data is received it
        categorises it and add its to the `to_user_queue`.

        Ripping out this loop and replacing it with event-driven reactor would
            be nice.
        """
        # Main DUL loop
        if self._idle_timer is not None:
            self._idle_timer.start()
        while True:

            # This effectively controls how often the DUL checks the network
            time.sleep(self._run_loop_delay)

            if self._kill_thread:
                break

            # Check the connection for incoming data
            try:
                # If local AE is SCU also calls _check_incoming_pdu()
                if self._is_transport_event() and self._idle_timer is not None:
                    self._idle_timer.restart()
                elif self._check_incoming_primitive():
                    pass

                elif self._is_artim_expired():
                    self._kill_thread = True

            except:
                # FIXME: This catch all should be removed
                self._kill_thread = True
                raise

            # Check the event queue to see if there is anything to do
            try:
                event = self.event_queue.get(block=False)
            # If the queue is empty, return to the start of the loop
            except queue.Empty:
                continue

            self.state_machine.do_action(event)

    def send_pdu(self, params):
        """

        Parameters
        ----------
        params -
            The parameters to put on FromServiceUser [FIXME]
        """
        self.to_provider_queue.put(params)

    def stop_dul(self):
        """
        Interrupts the thread if state is "Sta1"

        Returns
        -------
        bool
            True if Sta1, False otherwise
        """
        if self.state_machine.current_state == 'Sta1':
            self._kill_thread = True
            # Fix for Issue 39
            # Give the DUL thread time to exit
            while self.is_alive():
                time.sleep(0.001)

            return True

        return False

    def _check_incoming_pdu(self):
        """
        Converts an incoming PDU from the peer AE back into a primitive (ie one
        of the following: A-ASSOCIATE, A-RELEASE, A-ABORT, P-DATA, A-P-ABORT)
        """
        bytestream = bytes()

        # Try and read data from the socket
        try:
            # Get the data from the socket
            bytestream = self.scu_socket.recv(1)
        except socket.error:
            self.event_queue.put('Evt17')
            self.scu_socket.close()
            self.scu_socket = None
            LOGGER.error('DUL: Error reading data from the socket')
            return

        # Remote port has been closed
        if bytestream == bytes():
            self.event_queue.put('Evt17')
            self.scu_socket.close()
            self.scu_socket = None
            LOGGER.error('Peer has closed transport connection')
            return

        # Incoming data is OK
        else:
            # First byte is always PDU type
            #   0x01 - A-ASSOCIATE-RQ   1, 2, 3-6
            #   0x02 - A-ASSOCIATE-AC   1, 2, 3-6
            #   0x03 - A-ASSOCIATE-RJ   1, 2, 3-6
            #   0x04 - P-DATA-TF        1, 2, 3-6
            #   0x05 - A-RELEASE-RQ     1, 2, 3-6
            #   0x06 - A-RELEASE-RP     1, 2, 3-6
            #   0x07 - A-ABORT          1, 2, 3-6

            # We do all this just to get the length of the PDU
            # Byte 1 is PDU type
            #   (value, )
            pdu_type = unpack('B', bytestream)[0]

            # Unrecognised PDU type - Evt19 in the State Machine
            if pdu_type not in [0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07]:
                LOGGER.error("Unrecognised PDU type: 0x%02x", pdu_type)
                self.event_queue.put('Evt19')
                return

            # Byte 2 is Reserved
            result = self._recvn(self.scu_socket, 1)
            bytestream += result

            # Bytes 3-6 is the PDU length
            result = unpack('B', result)
            length = self._recvn(self.scu_socket, 4)

            bytestream += length
            length = unpack('>L', length)

            # Bytes 7-xxxx is the rest of the PDU
            result = self._recvn(self.scu_socket, length[0])
            bytestream += result

            # Determine the type of PDU coming on remote port, then decode
            # the raw bytestream to the corresponding PDU class
            self.pdu = self._socket_to_pdu(bytestream)

            # Put the event corresponding to the incoming PDU on the queue
            self.event_queue.put(self._pdu_to_event(self.pdu))

            # Convert the incoming PDU to a corresponding ServiceParameters
            #   object
            self.primitive = self.pdu.ToParams()

    def _check_incoming_primitive(self):
        """Check the incoming primitive."""
        try:
            # Check the queue and see if there are any primitives
            # If so then put the corresponding event on the event queue
            self.primitive = self.to_provider_queue.get(False)
            self.event_queue.put(self._primitive_to_event(self.primitive))
            return True
        except queue.Empty:
            return False

    def _is_artim_expired(self):
        """Return if the state machine's ARTIM timer has expired.

        If it has then 'Evt18' is added to the event queue.

        Returns
        -------
        bool
            True if the ARTIM timer has expired, False otherwise
        """
        if self.artim_timer.is_expired:
            #LOGGER.debug('%s: timer expired' % (self.name))
            self.event_queue.put('Evt18')
            return True

        return False

    def _is_transport_event(self):
        """Check to see if the transport connection has incoming data

        Returns
        -------
        bool
            True if an event has been added, False otherwise
        """
        # Sta13 is waiting for the transport connection to close
        if self.state_machine.current_state == 'Sta13':
            # If we have no connection to the SCU
            if self.scu_socket is None:
                return False

            # If we are still connected to the SCU
            try:
                # socket.Socket().recv(bufsize)
                # If we are still receiving data from the socket
                #   wait until its done
                while self.scu_socket.recv(1) != b'':
                    continue
            except socket.error:
                return False

            # Once we have no more incoming data close the socket and
            #   add the corresponding event to the queue
            self.scu_socket.close()
            self.scu_socket = None

            # Issue the Transport connection closed indication (AR-5 -> Sta1)
            self.event_queue.put('Evt17')
            return True

        # If the local AE is an SCP, listen for incoming data
        # The local AE is in Sta1, i.e. listening for Transport Connection
        #   Indications
        if self.scp_socket and not self.scu_socket:
            read_list, _, _ = select.select([self.scp_socket], [], [], 0)

            # If theres incoming connection request, accept it
            if read_list:
                self.scu_socket, _ = self.scp_socket.accept()

                # Add to event queue (Sta1 + Evt5 -> AE-5 -> Sta2
                self.event_queue.put('Evt5')
                return True

        # If a local AE is an SCU, listen for incoming data
        elif self.scu_socket:
            # If we are awaiting transport connection opening to complete
            #   (from local transport service) then issue the corresponding
            #   indication (Sta4 + Evt2 -> AE-2 -> Sta5)
            if self.state_machine.current_state == 'Sta4':
                self.event_queue.put('Evt2')
                return True

            # By this point the connection should be established
            #   If theres incoming data on the connection then check the PDU
            #   type
            # Fix for #28 - caused by peer disconnecting before run loop is
            #   stopped by assoc.release()
            try:
                read_list, _, _ = select.select([self.scu_socket], [], [], 0)
            except (socket.error, ValueError):
                return False

            if read_list:
                self._check_incoming_pdu()
                return True

        else:
            return False

    @staticmethod
    def _pdu_to_event(pdu):
        """Returns the event associated with the PDU.

        Parameters
        ----------
        pdu : pynetdicom3.pdu.PDU
            The PDU

        Returns
        -------
        str
            The event str associated with the PDU
        """
        if pdu.__class__ == A_ASSOCIATE_RQ:
            event_str = 'Evt6'
        elif pdu.__class__ == A_ASSOCIATE_AC:
            event_str = 'Evt3'
        elif pdu.__class__ == A_ASSOCIATE_RJ:
            event_str = 'Evt4'
        elif pdu.__class__ == P_DATA_TF:
            event_str = 'Evt10'
        elif pdu.__class__ == A_RELEASE_RQ:
            event_str = 'Evt12'
        elif pdu.__class__ == A_RELEASE_RP:
            event_str = 'Evt13'
        elif pdu.__class__ == A_ABORT_RQ:
            event_str = 'Evt16'
        else:
            #"Unrecognized or invalid PDU"
            event_str = 'Evt19'

        return event_str

    @staticmethod
    def _primitive_to_event(primitive):
        """Returns the state machine event associated with sending a primitive.

        Parameters
        ----------
        primitive : pynetdicom3.pdu_primitives.ServiceParameter
            The Association primitive

        Returns
        -------
        str
            The event associated with the primitive
        """
        if primitive.__class__ == A_ASSOCIATE:
            if primitive.result is None:
                # A-ASSOCIATE Request
                event_str = 'Evt1'
            elif primitive.result == 0x00:
                # A-ASSOCIATE Response (accept)
                event_str = 'Evt7'
            else:
                # A-ASSOCIATE Response (reject)
                event_str = 'Evt8'
        elif primitive.__class__ == A_RELEASE:
            if primitive.result is None:
                # A-Release Request
                event_str = 'Evt11'
            else:
                # A-Release Response
                # result is 'affirmative'
                event_str = 'Evt14'
        elif primitive.__class__ == A_ABORT:
            event_str = 'Evt15'
        elif primitive.__class__ == P_DATA:
            event_str = 'Evt9'
        else:
            raise ValueError("_primitive_to_event(): invalid primitive")

        return event_str

    @staticmethod
    def _recvn(sock, n_bytes):
        """Read `n_bytes` from a socket.

        Parameters
        ----------
        sock : socket.socket
            The socket to read from
        n_bytes : int
            The number of bytes to read
        """
        ret = b''
        read_length = 0
        while read_length < n_bytes:
            tmp = sock.recv(n_bytes - read_length)

            if not tmp:
                return ret

            ret += tmp
            read_length += len(tmp)

        if read_length != n_bytes:
            raise RuntimeError("_recvn(socket, {}) - Error reading data from "
                               "socket.".format(n_bytes))

        return ret

    def _socket_to_pdu(self, data):
        """Returns the PDU object associated with an incoming data stream.

        Parameters
        ----------
        data : bytes
            The incoming data stream

        Returns
        -------
        pdu : pynetdicom3.pdu.PDU
            The decoded data as a PDU object
        """
        pdutype = unpack('B', data[0:1])[0]
        acse = self.assoc.acse

        pdu_types = {0x01: (A_ASSOCIATE_RQ(), acse.debug_receive_associate_rq),
                     0x02: (A_ASSOCIATE_AC(), acse.debug_receive_associate_ac),
                     0x03: (A_ASSOCIATE_RJ(), acse.debug_receive_associate_rj),
                     0x04: (P_DATA_TF(), acse.debug_receive_data_tf),
                     0x05: (A_RELEASE_RQ(), acse.debug_receive_release_rq),
                     0x06: (A_RELEASE_RP(), acse.debug_receive_release_rp),
                     0x07: (A_ABORT_RQ(), acse.debug_receive_abort)}

        if pdutype in pdu_types:
            pdu = pdu_types[pdutype][0]
            pdu.Decode(data)

            # ACSE callbacks
            pdu_types[pdutype][1](pdu)

            return pdu

        return None
