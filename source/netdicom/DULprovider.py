#
# Copyright (c) 2012 Patrice Munger
# This file is part of pynetdicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pynetdicom.googlecode.com
#

#
# This module implements the DUL service provider, allowing a
# DUL service user to send and receive DUL messages. The User and Provider
# talk to each other using a TCP socket. The DULServer runs in a thread,
# so that and implements an event loop whose events will drive the
# state machine.
#
#
from threading import Thread
import socket
import time
import os
import select
import timer
import fsm
from struct import unpack
from PDU import *
import DULparameters
import Queue
import logging
logger = logging.getLogger('netdicom.DUL')


class InvalidPrimitive(Exception):
    pass


def recvn(sock, n):
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

    def __init__(self, Socket=None, Port=None, Name=''):
        """Three ways to call DULServiceProvider. If a port number is given,
        the DUL will wait for incoming connections on this port. If a socket
        is given, the DUL will use this socket as the client socket. If none
        is given, the DUL will not be able to accept connections (but will
        be able to initiate them.)"""

        if Socket and Port:
            raise "Cannot have both socket and port"

        Thread.__init__(self, name=Name)

        # current primitive and pdu
        self.primitive = None
        self.pdu = None
        self.event = Queue.Queue()
        # These variables provide communication between the DUL service
        # user and the DUL service provider. An event occurs when the DUL
        # service user writes the variable self.FromServiceUser.
        # A primitive is sent to the service user when the DUL service provider
        # writes the variable self.ToServiceUser.
        # The "None" value means that nothing happens.
        self.ToServiceUser = Queue.Queue()
        self.FromServiceUser = Queue.Queue()

        # Setup the timer and finite state machines
        self.Timer = timer.Timer(10)
        self.SM = fsm.StateMachine(self)

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
        """Interrupts the thread if state is "Sta1" """
        if self.SM.CurrentState == 'Sta1':
            self.kill = True
            return True
        else:
            return False

    def Send(self, params):
        self.FromServiceUser.put(params)

    def Receive(self, Wait=False, Timeout=None):
        # if not self.RemoteClientSocket: return None
        try:
            tmp = self.ToServiceUser.get(Wait, Timeout)
            return tmp
        except Queue.Empty:
            return None

    def Peek(self):
        """Look at next item to be returned by get"""
        try:
            return self.ToServiceUser.queue[0]
        except:
            return None

    def CheckIncomingPDU(self):
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
        #logger.debug('%s: checking timer' % (self.name))
        if self.Timer.Check() is False:
            logger.debug('%s: timer expired' % (self.name))
            # Timer expired
            self.event.put('Evt18')
            return True
        else:
            return False

    def CheckIncomingPrimitive(self):
        #logger.debug('%s: checking incoming primitive' % (self.name))
        # look at self.ReceivePrimitive for incoming primitives
        try:
            self.primitive = self.FromServiceUser.get(False, None)
            self.event.put(primitive2event(self.primitive))
            return True
        except Queue.Empty:
            return False

    def CheckNetwork(self):
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
        logger.debug('%s: DUL loop started' % self.name)
        while 1:
            time.sleep(0.001)
            # time.sleep(1)
            #logger.debug('%s: starting DUL loop' % self.name)
            if self.kill:
                break
            # catch an event
            if self.CheckNetwork():
                pass
            elif self.CheckIncomingPrimitive():
                pass
            elif self.CheckTimer():
                pass
            try:
                evt = self.event.get(False)
            except Queue.Empty:
                #logger.debug('%s: no event' % (self.name))
                continue
            self.SM.Action(evt, self)
        logger.debug('%s: DUL loop ended' % self.name)


def primitive2event(primitive):
    if primitive.__class__ == DULparameters.A_ASSOCIATE_ServiceParameters:
        if primitive.Result is None:
            # A-ASSOCIATE Request
            return 'Evt1'
        elif primitive.Result == 0:
            # A-ASSOCIATE Response (accept)
            return 'Evt7'
        else:
            # A-ASSOCIATE Response (reject)
            return 'Evt8'
    elif primitive.__class__ == DULparameters.A_RELEASE_ServiceParameters:
        if primitive.Result is None:
            # A-Release Request
            return 'Evt11'
        else:
            # A-Release Response
            return 'Evt14'
    elif primitive.__class__ == DULparameters.A_ABORT_ServiceParameters:
        return 'Evt15'
    elif primitive.__class__ == DULparameters.P_DATA_ServiceParameters:
        return 'Evt9'
    else:
        raise InvalidPrimitive


def Socket2PDU(data):
    # Returns the PDU object associated with an incoming data stream
    pdutype = unpack('B', data[0])[0]
    if pdutype == 0x01:
        pdu = A_ASSOCIATE_RQ_PDU()
        pdu.Decode(data)
    elif pdutype == 0x02:
        pdu = A_ASSOCIATE_AC_PDU()
        pdu.Decode(data)
    elif pdutype == 0x03:
        pdu = A_ASSOCIATE_RJ_PDU()
        pdu.Decode(data)
    elif pdutype == 0x04:
        pdu = P_DATA_TF_PDU()
        pdu.Decode(data)
    elif pdutype == 0x05:
        pdu = A_RELEASE_RQ_PDU()
        pdu.Decode(data)
    elif pdutype == 0x06:
        pdu = A_RELEASE_RP_PDU()
        pdu.Decode(data)
    elif pdutype == 0x07:
        pdu = A_ABORT_PDU()
        pdu.Decode(data)
    else:
        "Unrecognized or invalid PDU"
        pdu = None
    return pdu


def PDU2Event(pdu):
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
        "Unrecognized or invalid PDU"
        return 'Evt19'
