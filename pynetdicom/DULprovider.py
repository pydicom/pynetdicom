#
# Copyright (c) 2012 Patrice Munger
# This file is part of pynetdicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pynetdicom.googlecode.com


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

from pynetdicom.DULparameters import *
from pynetdicom.exceptions import InvalidPrimitive
from pynetdicom.fsm import StateMachine
from pynetdicom.PDU import *
from pynetdicom.timer import Timer


logger = logging.getLogger('netdicom.DUL')


def recvn(sock, n):
    """
    
    """
    ret = ''
    read_length = 0
    while read_length < n:
        tmp = sock.recv(n - read_length)
        if len(tmp)==0:
            return ret
        ret += tmp
        read_length += len(tmp)
    if read_length != n:
        raise "Low level Network ERROR: "
    return ret


class DULServiceProvider(Thread):
    """
    Three ways to call DULServiceProvider. If a port number is given,
    the DUL will wait for incoming connections on this port. If a socket
    is given, the DUL will use this socket as the client socket. If none
    is given, the DUL will not be able to accept connections (but will
    be able to initiate them.)
    
    Parameters
    ---------
    Socket - socket.socket, optional
        The socket to be used as the client socket
    Port - int, optional
        The port number on which to wait for incoming connections
    Name - str, optional
        Used help identify the DUL service provider
    MaxIdleSeconds - float, optional
        The maximum amount of time to wait for connection responses
        
    Attributes
    ----------
    Timer - timer
        The ARTIM timer
    SM - StateMachine
        The DICOM Upper Layer's State Machine
    event - queue.Queue
        List of queued events to be processed
    """
    def __init__(self, Socket=None, Port=None, Name='', MaxIdleSeconds=None):
        if Socket and Port:
            raise "Cannot have both socket and port"

        Thread.__init__(self, name=Name)

        # current primitive and pdu
        self.primitive = None
        self.pdu = None
        self.event = queue.Queue()
        # These variables provide communication between the DUL service
        # user and the DUL service provider. An event occurs when the DUL
        # service user writes the variable self.FromServiceUser.
        # A primitive is sent to the service user when the DUL service provider
        # writes the variable self.ToServiceUser.
        # The "None" value means that nothing happens.
        self.ToServiceUser = queue.Queue()
        self.FromServiceUser = queue.Queue()

        # Setup the timer and finite state machines
        self._idle_timer = None
        if MaxIdleSeconds is not None and MaxIdleSeconds > 0:
            self._idle_timer = Timer(MaxIdleSeconds)
        self.Timer = Timer(10)
        self.SM = StateMachine(self)

        if Socket:
            # A client socket has been given
            # generate an event 5
            self.event.put('Evt5')
            self.RemoteClientSocket = Socket
            self.RemoteConnectionAddress = None
            self.LocalServerSocket = None
        elif Port:
            # Setup the remote server socket
            # This is the socket that will accept connections
            # from the remote DUL provider
            # start this instance of DULServiceProvider in a thread.
            self.LocalServerSocket = socket.socket(socket.AF_INET,
                                                   socket.SOCK_STREAM)
            self.LocalServerSocket.setsockopt(socket.SOL_SOCKET,
                                              socket.SO_REUSEADDR, 1)

            self.LocalServerPort = Port
            if self.LocalServerPort:
                try:
                    self.LocalServerSocket.bind(
                        (os.popen('hostname').read()[:-1],
                         self.LocalServerPort))
                except:
                    logger.error("Already bound")
                self.LocalServerSocket.listen(1)
            else:
                self.LocalServerSocket = None
            self.RemoteClientSocket = None
            self.RemoteConnectionAddress = None
        else:
            # No port nor socket
            self.LocalServerSocket = None
            self.RemoteClientSocket = None
            self.RemoteConnectionAddress = None

        self.kill = False
        self.daemon = True
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
        if self.SM.CurrentState == 'Sta1':
            self.kill = True
            return True

        return False

    def Send(self, params):
        """
        
        Parameters
        ----------
        params - 
            The parameters to put on FromServiceUser [FIXME]
        """
        self.FromServiceUser.put(params)

    def Receive(self, Wait=False, Timeout=None):
        """
        
        Parameters
        ----------
        Wait - bool, optional
        Timeout - ?, optional
        
        Returns
        -------
        ???
            The get from the ToServiceUser [FIXME]
        None 
            If the [FIXME] queue is empty
        """
        # if not self.RemoteClientSocket: return None
        try:
            tmp = self.ToServiceUser.get(Wait, Timeout)
            return tmp
        except queue.Empty:
            return None

    def Peek(self):
        """Look at next item to be returned by get"""
        try:
            return self.ToServiceUser.queue[0]
        except:
            return None

    def CheckIncomingPDU(self):
        """
    
        """
        rawpdu = ''
        # There is something to read
        # read type
        try:
            rawpdu = self.RemoteClientSocket.recv(1)
        except socket.error:
            self.event.put('Evt17')
            self.RemoteClientSocket.close()
            self.RemoteClientSocket = None
            return

        if rawpdu == '':
            # Remote port has been closed
            self.event.put('Evt17')
            self.RemoteClientSocket.close()
            self.RemoteClientSocket = None
            return
        else:
            type = unpack('B', rawpdu)
            res = recvn(self.RemoteClientSocket, 1)
            rawpdu += res
            res = unpack('B', res)
            length = recvn(self.RemoteClientSocket, 4)
            rawpdu += length
            length = unpack('>L', length)
            tmp = recvn(self.RemoteClientSocket, length[0])
            rawpdu += tmp
            # Determine the type of PDU coming on remote port
            # and set the event accordingly
            self.pdu = Socket2PDU(rawpdu)
            self.event.put(PDU2Event(self.pdu))

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
        if self.Timer.is_expired():
            logger.debug('%s: timer expired' % (self.name))
            self.event.put('Evt18')
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
            self.primitive = self.FromServiceUser.get(False, None)
            self.event.put(primitive2event(self.primitive))
            return True
        except queue.Empty:
            return False

    def CheckNetwork(self):
        """
    
        """
        #logger.debug('%s: checking network' % (self.name))
        if self.SM.CurrentState == 'Sta13':
            # wainting for connection to close
            if self.RemoteClientSocket is None:
                return False
            # wait for remote connection to close
            try:
                while self.RemoteClientSocket.recv(1) != '':
                    continue
            except socket.error:
                return False
            # self.event.Flush() # flush event queue
            self.RemoteClientSocket.close()
            self.RemoteClientSocket = None
            self.event.put('Evt17')
            return True
        
        if self.LocalServerSocket and not self.RemoteClientSocket:
            # local server is listening
            [a, b, c] = select.select([self.LocalServerSocket], [], [], 0)
            if a:
                # got an incoming connection
                self.RemoteClientSocket, address = \
                    self.LocalServerSocket.accept()
                self.event.put('Evt5')
                return True
        elif self.RemoteClientSocket:
            if self.SM.CurrentState == 'Sta4':
                self.event.put('Evt2')
                return True
            # check if something comes in the client socket
            [a, b, c] = select.select([self.RemoteClientSocket], [], [], 0)
            if a:
                self.CheckIncomingPDU()
                return True
        else:
            return False

    def run(self):
        """
        The main threading.Thread run loop
        
        """
        logger.debug('%s: DUL loop started' % self.name)
        
        # Main DUL loop
        while True:
            if self._idle_timer is not None:
                self._idle_timer.start()

            time.sleep(0.001)
            # time.sleep(1)
            #logger.debug('%s: starting DUL loop' % self.name)
            
            if self.kill:
                break
            
            # catch an event
            try:
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
            
            try:
                evt = self.event.get(False)
            except queue.Empty:
                #logger.debug('%s: no event' % (self.name))
                continue
            
            try:
                self.SM.Action(evt, self)
            except:
                self.kill = True
        logger.debug('%s: DUL loop ended' % self.name)


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
    if primitive.__class__ == A_ASSOCIATE_ServiceParameters:
        if primitive.Result is None:
            # A-ASSOCIATE Request
            return 'Evt1'
        elif primitive.Result == 0:
            # A-ASSOCIATE Response (accept)
            return 'Evt7'
        else:
            # A-ASSOCIATE Response (reject)
            return 'Evt8'
    elif primitive.__class__ == A_RELEASE_ServiceParameters:
        if primitive.Result is None:
            # A-Release Request
            return 'Evt11'
        else:
            # A-Release Response
            return 'Evt14'
    elif primitive.__class__ == A_ABORT_ServiceParameters:
        return 'Evt15'
    elif primitive.__class__ == P_DATA_ServiceParameters:
        return 'Evt9'
    else:
        raise InvalidPrimitive

def Socket2PDU(data):
    """
    Returns the PDU object associated with an incoming data stream
    
    Parameters
    ----------
    data - 
        The incoming data stream
    
    Returns
    -------
    pdu
        The PDU object
    """
    pdutype = unpack('B', data[0])[0]
    if pdutype == 0x01:
        pdu = A_ASSOCIATE_RQ_PDU()
    elif pdutype == 0x02:
        pdu = A_ASSOCIATE_AC_PDU()
    elif pdutype == 0x03:
        pdu = A_ASSOCIATE_RJ_PDU()
    elif pdutype == 0x04:
        pdu = P_DATA_TF_PDU()
    elif pdutype == 0x05:
        pdu = A_RELEASE_RQ_PDU()
    elif pdutype == 0x06:
        pdu = A_RELEASE_RP_PDU()
    elif pdutype == 0x07:
        pdu = A_ABORT_PDU()
    else:
        #"Unrecognized or invalid PDU"
        return None

    pdu.Decode(data)

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
