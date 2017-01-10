# This module implements the DUL service provider, allowing a
# DUL service user to send and receive DUL messages. The User and Provider
# talk to each other using a TCP socket. The DULServer runs in a thread,
# so that and implements an event loop whose events will drive the
# state machine.

import logging
import os
import queue
import select
import socket
from struct import unpack
from threading import Thread
import time

from pynetdicom3.exceptions import InvalidPrimitive
from pynetdicom3.fsm import StateMachine
from pynetdicom3.PDU import *
from pynetdicom3.timer import Timer
from pynetdicom3.primitives import A_ASSOCIATE, A_RELEASE, A_ABORT, P_DATA


logger = logging.getLogger('pynetdicom3.dul')


def recvn(sock, n):
    """
    Read n bytes from a socket

    Parameters
    ----------
    sock - socket.socket
        The socket to read from
    n - int
        The number of bytes to read
    """
    ret = b''
    read_length = 0
    while read_length < n:
        tmp = sock.recv(n - read_length)

        if len(tmp)==0:
            return ret

        ret += tmp
        read_length += len(tmp)

    if read_length != n:
        raise #"Low level Network ERROR: "

    return ret


class DULServiceProvider(Thread):
    """
    Three ways to call DULServiceProvider:
    - If a port number is given, the DUL will wait for incoming connections on
      this port.
    - If a socket is given, the DUL will use this socket as the client socket.
    - If neither is given, the DUL will not be able to accept connections (but
      will be able to initiate them.)

    Parameters
    ----------
    Socket : socket.socket, optional
        The local AE's listen socket
    Port : int, optional
        The port number on which to wait for incoming connections
    Name : str, optional
        Used help identify the DUL service provider
    dul_timeout : float, optional
        The maximum amount of time to wait for connection responses (in seconds)
    local_ae : pynetdicom3.applicationentity.ApplicationEntity
        The local AE instance
    assoc : pynetdicom3.association.Association
        The DUL's current Association

    Attributes
    ----------
    artim_timer : pynetdicom3.timer.Timer
        The ARTIM timer
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
    def __init__(self, Socket=None, Port=None, Name='', dul_timeout=None,
                        acse_timeout=30, local_ae=None, assoc=None):

        if Socket and Port:
            raise ValueError("DULServiceProvider can't be instantiated with "
                                        "both Socket and Port parameters")

        # The local AE
        self.local_ae = local_ae
        self.association = assoc

        Thread.__init__(self, name=Name)

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
        self._idle_timer = None
        if dul_timeout is not None and dul_timeout > 0:
            self._idle_timer = Timer(dul_timeout)

        # ARTIM timer
        self.artim_timer = Timer(acse_timeout)

        # State machine - PS3.8 Section 9.2
        self.state_machine = StateMachine(self)

        if Socket:
            # A client socket has been given, so the local AE is acting as
            #   an SCP
            # generate an event 5
            self.event_queue.put('Evt5')
            self.scu_socket = Socket
            self.peer_address = None
            self.scp_socket = None
        elif Port:
            # A port number has been given, so the local AE is acting as an
            #   SCU. Create a new socket using the given port number
            self.scp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.scp_socket.setsockopt(socket.SOL_SOCKET,
                                       socket.SO_REUSEADDR,
                                       1)

            # The port number for the local AE to listen on
            self.local_port = Port
            if self.local_port:
                try:
                    local_address = os.popen('hostname').read()[:-1]
                    self.scp_socket.bind((local_address, self.local_port))
                except:
                    #logger.error("Already bound")
                    # FIXME: If already bound then warn?
                    #   Why would it already be bound?
                    # A: Another process may be using it
                    pass
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

        self.kill = False
        self.daemon = False
        self.start()

    def Kill(self):
        """Immediately interrupts the thread"""
        self.kill = True

    def Stop(self):
        """
        Interrupts the thread if state is "Sta1"

        Returns
        -------
        bool
            True if Sta1, False otherwise
        """
        if self.state_machine.current_state == 'Sta1':
            self.kill = True
            # Fix for Issue 39
            # Give the DUL thread time to exit
            while self.is_alive():
                time.sleep(0.001)

            return True

        return False

    def Send(self, params):
        """

        Parameters
        ----------
        params -
            The parameters to put on FromServiceUser [FIXME]
        """
        self.to_provider_queue.put(params)

    def Receive(self, Wait=False, Timeout=None):
        """
        Get the next item to be processed out of the queue of items sent
        from the DUL service provider to the service user

        Parameters
        ----------
        Wait - bool, optional
            If `Wait` is True and `Timeout` is None, blocks until an item
            is available. If `Timeout` is a positive number, blocks at most
            `Timeout` seconds. Otherwise returns an item if one is immediately
            available.
        Timeout - int, optional
            See the definition of `Wait`

        Returns
        -------
        queue_item
            The next object in the to_user_queue [FIXME]
        None
            If the queue is empty
        """
        try:
            queue_item = self.to_user_queue.get(block=Wait, timeout=Timeout)
            return queue_item
        except queue.Empty:
            return None

    def Peek(self):
        """Look at next item to be returned by get"""
        try:
            return self.to_user_queue.queue[0]
        except:
            return None

    def CheckIncomingPDU(self):
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
            logger.error('DUL: Error reading data from the socket')
            return

        # Remote port has been closed
        if bytestream == bytes():
            self.event_queue.put('Evt17')
            self.scu_socket.close()
            self.scu_socket = None
            logger.error('Peer has closed transport connection')
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
            pdu_type = unpack('B', bytestream)

            # Unrecognised PDU type - Evt19 in the State Machine
            if pdu_type[0] not in [0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07]:
                logger.error("Unrecognised PDU type: 0x%s" %pdu_type)
                self.event_queue.put('Evt19')
                return

            # Byte 2 is Reserved
            result = recvn(self.scu_socket, 1)
            bytestream += result

            # Bytes 3-6 is the PDU length
            result = unpack('B', result)
            length = recvn(self.scu_socket, 4)

            bytestream += length
            length = unpack('>L', length)

            # Bytes 7-xxxx is the rest of the PDU
            result = recvn(self.scu_socket, length[0])
            bytestream += result

            # Determine the type of PDU coming on remote port, then decode
            # the raw bytestream to the corresponding PDU class
            self.pdu = Socket2PDU(bytestream, self)

            # Put the event corresponding to the incoming PDU on the queue
            self.event_queue.put(PDU2Event(self.pdu))

            # Convert the incoming PDU to a corresponding ServiceParameters
            #   object
            self.primitive = self.pdu.ToParams()

    def CheckTimer(self):
        """
        Check if the state machine's ARTIM timer has expired. If it has then
        Evt18 is added to the event queue.

        Returns
        -------
        bool
            True if the ARTIM timer has expired, False otherwise
        """
        if self.artim_timer.is_expired():
            #logger.debug('%s: timer expired' % (self.name))
            self.event_queue.put('Evt18')
            return True

        return False

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

        if self._idle_timer.is_expired() == True:
            return True

        return False

    def CheckIncomingPrimitive(self):
        """

        """
        #logger.debug('%s: checking incoming primitive' % (self.name))
        # look at self.ReceivePrimitive for incoming primitives
        try:
            # Check the queue and see if there are any primitives
            # If so then put the corresponding event on the event queue
            self.primitive = self.to_provider_queue.get(False, None)
            self.event_queue.put(primitive2event(self.primitive))
            return True
        except queue.Empty:
            return False

    def CheckNetwork(self):
        return self.is_transport_connection_event()

    def is_transport_connection_event(self):
        """
        Check to see if the transport connection has incoming data

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
                self.scu_socket, address = self.scp_socket.accept()

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

            # By this point the connection is established
            #   If theres incoming data on the connection then check the PDU
            #   type
            #
            # FIXME: bug related to socket closing, see socket_bug.note
            #
            #try:
            #print(self.scu_socket)

            read_list, _, _ = select.select([self.scu_socket], [], [], 0)

            if read_list:
                self.CheckIncomingPDU()
                return True
            #except ValueError:
            #    self.event_queue.put('Evt17')
            #    return False

        else:
            return False

    def run(self):
        """
        The main threading.Thread run loop. Runs constantly, checking the
        connection for incoming data. When incoming data is received it
        categorises it and add its to the `to_user_queue`.
        """
        #logger.debug('Starting DICOM UL service "%s"' %self.name)

        # Main DUL loop
        while True:
            if self._idle_timer is not None:
                self._idle_timer.start()

            # Required for some reason
            time.sleep(0.001)

            if self.kill:
                break

            # Check the connection for incoming data
            try:
                # If local AE is SCU also calls CheckIncomingPDU()
                if self.CheckNetwork():
                    if self._idle_timer is not None:
                        self._idle_timer.restart()
                elif self.CheckIncomingPrimitive():
                    pass

                elif self.CheckTimer():
                    self.kill = True

            except:
                self.kill = True
                raise

            # Check the event queue to see if there is anything to do
            try:
                event = self.event_queue.get(False)
            # If the queue is empty, return to the start of the loop
            except queue.Empty:
                continue

            self.state_machine.do_action(event)

        #logger.debug('DICOM UL service "%s" stopped' %self.name)

    def on_receive_pdu(self):
        """
        Callback function that is called after the first byte of an incoming
        PDU is read
        """
        pass


def primitive2event(primitive):
    """
    Returns the event associated with the primitive

    Parameters
    ----------
    primitive -


    Returns
    -------
    str
        The event associated with the primitive

    Raises
    ------
    InvalidPrimitive
        If the primitive is not valid
    """
    if primitive.__class__ == A_ASSOCIATE:
        if primitive.result is None:
            # A-ASSOCIATE Request
            return 'Evt1'
        elif primitive.result == 0:
            # A-ASSOCIATE Response (accept)
            return 'Evt7'
        else:
            # A-ASSOCIATE Response (reject)
            return 'Evt8'
    elif primitive.__class__ == A_RELEASE:
        if primitive.result is None:
            # A-Release Request
            return 'Evt11'
        else:
            # A-Release Response
            return 'Evt14'
    elif primitive.__class__ == A_ABORT:
        return 'Evt15'
    elif primitive.__class__ == P_DATA:
        return 'Evt9'
    else:
        raise InvalidPrimitive

def Socket2PDU(data, dul):
    """
    Returns the PDU object associated with an incoming data stream

    Parameters
    ----------
    data -
        The incoming data stream
    dul - pynetdicom3.DULprovider.DUL
        The DUL instance

    Returns
    -------
    pdu
        The decoded data as a PDU object
    """
    pdutype = unpack('B', data[0:1])[0]
    acse = dul.association.acse

    if pdutype == 0x01:
        pdu = A_ASSOCIATE_RQ_PDU()
        acse_callback = acse.debug_receive_associate_rq
    elif pdutype == 0x02:
        pdu = A_ASSOCIATE_AC_PDU()
        acse_callback = acse.debug_receive_associate_ac
    elif pdutype == 0x03:
        pdu = A_ASSOCIATE_RJ_PDU()
        acse_callback = acse.debug_receive_associate_rj
    elif pdutype == 0x04:
        pdu = P_DATA_TF_PDU()
        acse_callback = acse.debug_receive_data_tf
    elif pdutype == 0x05:
        pdu = A_RELEASE_RQ_PDU()
        acse_callback = acse.debug_receive_release_rq
    elif pdutype == 0x06:
        pdu = A_RELEASE_RP_PDU()
        acse_callback = acse.debug_receive_release_rp
    elif pdutype == 0x07:
        pdu = A_ABORT_PDU()
        acse_callback = acse.debug_receive_abort
    else:
        #"Unrecognized or invalid PDU"
        return None

    pdu.Decode(data)

    # Callback - AE must always be first
    acse_callback(pdu)

    return pdu

def PDU2Event(pdu):
    """
    Returns the event associated with the PDU

    Parameters
    ----------
    pdu -
        The PDU

    Returns
    -------
    str
        The event str associated with the PDU
    """
    if pdu.__class__ == A_ASSOCIATE_RQ_PDU:
        return 'Evt6'
    elif pdu.__class__ == A_ASSOCIATE_AC_PDU:
        return 'Evt3'
    elif pdu.__class__ == A_ASSOCIATE_RJ_PDU:
        return 'Evt4'
    elif pdu.__class__ == P_DATA_TF_PDU:
        return 'Evt10'
    elif pdu.__class__ == A_RELEASE_RQ_PDU:
        return 'Evt12'
    elif pdu.__class__ == A_RELEASE_RP_PDU:
        return 'Evt13'
    elif pdu.__class__ == A_ABORT_PDU:
        return 'Evt16'
    else:
        #"Unrecognized or invalid PDU"
        return 'Evt19'
