"""Unit tests for fsm.py"""

import logging
try:
    import queue
except ImportError:
    import Queue as queue  # Python 2 compatibility
import select
import socket
from struct import pack, unpack
import threading
import time

import pytest

from pynetdicom import AE, build_context
from pynetdicom.association import Association
from pynetdicom import fsm as FINITE_STATE
from pynetdicom.fsm import *
from pynetdicom.dimse_primitives import C_ECHO
from pynetdicom.pdu_primitives import (
    A_ASSOCIATE, A_ABORT, A_P_ABORT, P_DATA, A_RELEASE,
    MaximumLengthNotification, ImplementationClassUIDNotification
)
from pynetdicom.pdu import A_RELEASE_RQ
from pynetdicom.sop_class import VerificationSOPClass
from pynetdicom.utils import validate_ae_title
from .dummy_c_scp import DummyVerificationSCP, DummyBaseSCP
from .encoded_pdu_items import (
    a_associate_ac, a_associate_rq, a_associate_rj, p_data_tf, a_abort,
    a_release_rq, a_release_rp,
)


LOGGER = logging.getLogger("pynetdicom")
#LOGGER.setLevel(logging.CRITICAL)
LOGGER.setLevel(logging.DEBUG)


REFERENCE_BAD_EVENTS = [
    # Event, bad states
    ("Evt1", [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]),  # A-ASSOCIATE (rq) p
    ("Evt2", [1, 2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13]),  # Connection available
    ("Evt3", [1, 4]),  # A-ASSOCIATE-AC PDU recv
    ("Evt4", [1, 4]),  # A-ASSOCIATE-RJ PDU recv
    ("Evt5", [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]),  # Connection open
    ("Evt6", [1, 4]),  # A-ASSOCIATE-RQ PDU recv
    ("Evt7", [1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]),  # A-ASSOCIATE (ac) p
    ("Evt8", [1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]),  # A-ASSOCIATE (rj) p
    ("Evt9", [1, 2, 3, 4, 5, 7, 9, 10, 11, 12, 13]),  # P-DATA primitive
    ("Evt10", [1, 4]),  # P-DATA-TF PDU
    ("Evt11", [1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12, 13]),  # A-RELEASE (rq) p
    ("Evt12", [1, 4]),  # A-RELEASE-RQ PDU recv
    ("Evt13", [1, 4]),  # A-RELEASE-RP PDU recv
    ("Evt14", [1, 2, 3, 4, 5, 6, 7, 10, 11, 13]),  # A-RELEASE (rsp) primitive
    ("Evt15", [1, 2, 13]),  # A-ABORT (rq) primitive
    ("Evt16", [1, 4]),  # A-ABORT PDU recv
    ("Evt17", [1]),  # Connection closed
    ("Evt18", [1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]),  # ARTIM expired
    ("Evt19", [1, 4]),  # Unrecognised PDU rev
]
REFERENCE_GOOD_EVENTS = [
    # Event, good states
    ("Evt1", [1]),  # A-ASSOCIATE (rq) p
    ("Evt2", [4]),  # Connection available
    ("Evt3", [2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13]),  # A-ASSOCIATE-AC PDU recv
    ("Evt4", [2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13]),  # A-ASSOCIATE-RJ PDU recv
    ("Evt5", [1]),  # Connection open
    ("Evt6", [2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13]),  # A-ASSOCIATE-RQ PDU recv
    ("Evt7", [3]),  # A-ASSOCIATE (ac) p
    ("Evt8", [3]),  # A-ASSOCIATE (rj) p
    ("Evt9", [6, 8]),  # P-DATA primitive
    ("Evt10", [2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13]),  # P-DATA-TF PDU
    ("Evt11", [6]),  # A-RELEASE (rq) p
    ("Evt12", [2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13]),  # A-RELEASE-RQ PDU recv
    ("Evt13", [2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13]),  # A-RELEASE-RP PDU recv
    ("Evt14", [8, 9, 12]),  # A-RELEASE (rsp) primitive
    ("Evt15", [3, 4, 5, 6, 7, 8, 9, 10, 11, 12]),  # A-ABORT (rq) primitive
    ("Evt16", [2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13]),  # A-ABORT PDU recv
    ("Evt17", [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13]),  # Connection closed
    ("Evt18", [2, 13]),  # ARTIM expired
    ("Evt19", [2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13]),  # Unrecognised PDU rev
]


class BadDUL(object):
    """A DUL that always raises an exception during actions."""
    def __init__(self):
        self.is_killed = False

    def kill_dul(self):
        """Hook for testing whether DUL got killed."""
        self.is_killed = True

    @property
    def primitive(self):
        """Prevent StateMachine from setting primitive."""
        return None


class DummyAE(threading.Thread):
    def __init__(self, port=11112):
        self.queue = queue.Queue()
        self._kill = False
        self.socket = socket.socket
        self.address = ''
        self.local_port = port
        self.remote_port = None
        self.received = []
        self.mode = 'requestor'
        self.wait_after_connect = False
        self.disconnect_after_connect = False
        self._step = 0
        self._event = threading.Event()

        threading.Thread.__init__(self)
        self.daemon = True

    def bind_socket(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # SOL_SOCKET: the level, SO_REUSEADDR: allow reuse of a port
        #   stuck in TIME_WAIT, 1: set SO_REUSEADDR to 1
        # This must be called prior to socket.bind()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(
            socket.SOL_SOCKET, socket.SO_RCVTIMEO, pack('ll', 10, 0)
        )

        # Bind the socket to an address and port
        #   If self.bind_addr is '' then the socket is reachable by any
        #   address the machine may have, otherwise is visible only on that
        #   address
        sock.bind(('', self.local_port))

        # Listen for connections made to the socket
        # socket.listen() says to queue up to as many as N connect requests
        #   before refusing outside connections
        sock.listen(1)
        return sock

    def run(self):
        if self.mode == 'acceptor':
            self.run_as_acceptor()
        elif self.mode == 'requestor':
            self.run_as_requestor()

    def run_as_acceptor(self):
        """Run the Collider as an association requestor.

        1. Open a list socket on self.local_port
        2. Wait for a connection request, when connected GOTO 3
        3. Check self.queue for an item:
            a. If the item is None then GOTO 4
            b. If the item is singleton then send it to the peer and GOTO 4
            c. If the item is a list then send each item in the list to the
               peer, then GOTO 4. if one of the items is 'shutdown' then exit
            d. If the item is 'shutdown' then exit
        4. Block the connection until data appears, then append the data to
           self.received.
        """
        sock = self.bind_socket()
        self.sock = sock

        # Wait for a connection
        while not self._kill:
            ready, _, _ = select.select([sock], [], [], 0.5)

            if self.disconnect_after_connect:
                sock.shutdown(socket.SHUT_RDWR)
                sock.close()
                return

            if self.wait_after_connect:
                time.sleep(0.5)

            if ready:
                conn, _ = sock.accept()
                break

        # Send and receive data
        while not self._kill:
            to_send = self.queue.get()
            if to_send == 'shutdown':
                # 'shutdown'
                self.sock.shutdown(socket.SHUT_RDWR)
                self.sock.close()
                self._kill = True
                return
            elif to_send is not None:
                # item or [item, item]
                if isinstance(to_send, list):
                    if to_send[0] == 'wait':
                        time.sleep(to_send[1])
                        if len(to_send) == 3:
                            self.sock.shutdown(socket.SHUT_RDWR)
                            self.sock.close()
                            self._kill = True
                            return
                        continue
                    elif to_send[0] == 'skip':
                        conn.send(to_send[1])
                        continue
                    elif to_send[1] == 'shutdown':
                        conn.send(to_send[0])
                        self.sock.shutdown(socket.SHUT_RDWR)
                        self.sock.close()
                        self._kill = True
                        return
                    else:
                        for item in to_send:
                            conn.send(item)
                else:
                    conn.send(to_send)
            elif to_send == 'skip':
                continue
            else:
                # None
                pass

            # Block until ready to read
            ready, _, _ = select.select([conn], [], [])
            if ready:
                data_received = self.read_stream(conn)
                self.received.append(data_received)

    def run_as_requestor(self):
        """Run the Collider as an association requestor.

        1. Open a connection to the peer at (self.address, self.remote_port)
        2. Check self.queue for an item:
            a. If the item is None then GOTO 3
            b. If the item is singleton then send it to the peer and GOTO 3
            c. If the item is a list then send each item in the list to the
               peer, then GOTO 3
            d. If the item is 'shutdown' then exit
        3. Block the connection until data appears, then append the data to
           self.received.
        """
        # Make the connection
        while not self._kill:
            try:
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.connect((self.address, self.remote_port))
                break
            except:
                pass

        # Send and receive data
        while not self._kill:
            to_send = self.queue.get()
            if to_send == 'shutdown':
                # 'shutdown'
                self.sock.shutdown(socket.SHUT_RDWR)
                self.sock.close()
                self._kill = True
                return
            elif to_send is not None:
                # item or [item, item]
                if isinstance(to_send, list):
                    for item in to_send:
                        self.sock.send(item)
                else:
                    self.sock.send(to_send)
            else:
                # None
                pass

            # Block until ready
            # When the timeout argument is omitted the function blocks until
            #   at least one file descriptor is ready
            ready, _, _ = select.select([self.sock], [], [])
            if ready:
                data_received = self.read_stream(self.sock)
                self.received.append(data_received)

    def read_stream(self, sock):
        bytestream = bytes()

        # Try and read data from the socket
        try:
            # Get the data from the socket
            bytestream = sock.recv(1)
        except socket.error:
            self._kill = True
            sock.close()
            return

        pdu_type = unpack('B', bytestream)[0]

        # Byte 2 is Reserved
        result = self._recvn(sock, 1)
        bytestream += result

        # Bytes 3-6 is the PDU length
        result = unpack('B', result)
        length = self._recvn(sock, 4)

        bytestream += length
        length = unpack('>L', length)

        # Bytes 7-xxxx is the rest of the PDU
        result = self._recvn(sock, length[0])
        bytestream += result

        return bytestream

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

    def stop(self):
        self._kill = True

    def shutdown_sockets(self):
        """Close the sockets."""
        self.sock.shutdown(socket.SHUT_RDWR)
        self.sock.close()


class TestStateMachine(object):
    """Non-functional unit tests for fsm.StateMachine."""
    def test_init(self):
        """Test creation of new StateMachine."""
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        assoc = Association(ae, mode='requestor')

        fsm = assoc.dul.state_machine
        assert fsm.current_state == 'Sta1'
        assert fsm.dul == assoc.dul

    def test_invalid_transition_raises(self):
        """Test StateMachine.transition using invalid states raises."""
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        assoc = Association(ae, mode='requestor')

        fsm = assoc.dul.state_machine
        msg = r"Invalid state 'Sta0' for State Machine"
        with pytest.raises(ValueError, match=msg):
            fsm.transition('Sta0')

    def test_valid_transition(self):
        """Test StateMachine.transition using valid states."""
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        assoc = Association(ae, mode='requestor')
        fsm = assoc.dul.state_machine

        for ii in range(1, 14):
            assert 1 <= ii <= 13
            fsm.transition("Sta{}".format(ii))
            assert fsm.current_state == "Sta{}".format(ii)

    @pytest.mark.parametrize("event, states", REFERENCE_BAD_EVENTS)
    def test_invalid_action_raises(self, event, states):
        """Test StateMachine.do_action raises exception if action invalid."""
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        assoc = Association(ae, mode='requestor')
        fsm = assoc.dul.state_machine

        for state in states:
            state = "Sta{}".format(state)
            fsm.current_state = state

            msg = msg = (
                r"Invalid event '{}' for the current state '{}'"
                .format(event, state)
            )
            with pytest.raises(InvalidEventError, match=msg):
                fsm.do_action(event)

    @pytest.mark.parametrize("event, states", REFERENCE_GOOD_EVENTS)
    def test_exception_during_action(self, event, states):
        """Test an exception raised during an action kill the DUL."""
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        assoc = Association(ae, mode='requestor')
        fsm = assoc.dul.state_machine
        fsm.dul = BadDUL()

        for state in states:
            fsm.dul.is_killed = False
            state = "Sta{}".format(state)
            fsm.current_state = state
            with pytest.raises(AttributeError):
                fsm.do_action(event)
            assert fsm.dul.is_killed is True
            assert fsm.current_state == state


class TestStateBase(object):
    """Base class for State tests."""
    def setup(self):
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        assoc = Association(ae, mode='requestor')
        assoc.acse_timeout = ae.acse_timeout
        assoc.dimse_timeout = ae.dimse_timeout
        assoc.network_timeout = ae.network_timeout

        # Association Acceptor object -> remote AE
        assoc.acceptor.ae_title = validate_ae_title(b'ANY_SCU')
        assoc.acceptor.address = 'localhost'
        assoc.acceptor.port = 11112

        # Association Requestor object -> local AE
        assoc.requestor.address = ae.address
        assoc.requestor.port = ae.port
        assoc.requestor.ae_title = ae.ae_title
        assoc.requestor.maximum_length = 16382
        assoc.requestor.implementation_class_uid = (
            ae.implementation_class_uid
        )
        assoc.requestor.implementation_version_name = (
            ae.implementation_version_name
        )

        cx = build_context(VerificationSOPClass)
        cx.context_id = 1
        assoc.requestor.requested_contexts = [cx]

        self.assoc = assoc
        self.fsm = self.monkey_patch(assoc.dul.state_machine)

    def get_associate(self, assoc_type):
        primitive = A_ASSOCIATE()
        if assoc_type == 'request':
            primitive.application_context_name = '1.2.3.4.5.6'
            # Calling AE Title is the source DICOM AE title
            primitive.calling_ae_title = b'LOCAL_AE_TITLE  '
            # Called AE Title is the destination DICOM AE title
            primitive.called_ae_title = b'REMOTE_AE_TITLE '
            # The TCP/IP address of the source, pynetdicom includes port too
            primitive.calling_presentation_address = ('', 0)
            # The TCP/IP address of the destination, pynetdicom includes port too
            primitive.called_presentation_address = ('localhost', 11112)
            # Proposed presentation contexts
            cx = build_context(VerificationSOPClass)
            cx.context_id = 1
            primitive.presentation_context_definition_list = [cx]

            user_info = []

            item = MaximumLengthNotification()
            item.maximum_length_received = 16382
            user_info.append(item)

            item = ImplementationClassUIDNotification()
            item.implementation_class_uid = '1.2.3.4'
            user_info.append(item)
            primitive.user_information = user_info
        elif assoc_type == 'accept':
            primitive.application_context_name = '1.2.3.4.5.6'
            # Calling AE Title is the source DICOM AE title
            primitive.calling_ae_title = b'LOCAL_AE_TITLE  '
            # Called AE Title is the destination DICOM AE title
            primitive.called_ae_title = b'REMOTE_AE_TITLE '
            # The TCP/IP address of the source, pynetdicom includes port too
            primitive.result = 0x00
            primitive.result_source = 0x01
            # Proposed presentation contexts
            cx = build_context(VerificationSOPClass)
            cx.context_id = 1
            primitive.presentation_context_definition_results_list = [cx]

            user_info = []

            item = MaximumLengthNotification()
            item.maximum_length_received = 16383
            user_info.append(item)

            item = ImplementationClassUIDNotification()
            item.implementation_class_uid = '1.2.3.4.5'
            user_info.append(item)
            primitive.user_information = user_info
        elif assoc_type == 'reject':
            primitive.result = 0x01
            primitive.result_source = 0x01
            primitive.diagnostic = 0x01

        return primitive

    def get_release(self, is_response=False):
        primitive = A_RELEASE()
        if is_response:
            primitive.result = 'affirmative'

        return primitive

    def get_abort(self, is_ap=False):
        if is_ap:
            primitive = A_P_ABORT()
            primitive.provider_reason = 0x00
        else:
            primitive = A_ABORT()
            primitive.abort_source = 0x00

        return primitive

    def get_pdata(self):
        item = [1, p_data_tf[10:]]

        primitive = P_DATA()
        primitive.presentation_data_value_list.append(item)

        return primitive

    def monkey_patch(self, fsm):
        """Monkey patch the StateMachine to add testing hooks."""
        # Record all state transitions
        fsm._transitions = []
        fsm.original_transition = fsm.transition

        def transition(state):
            fsm._transitions.append(state)
            fsm.original_transition(state)

        fsm.transition = transition

        # Record all event/state/actions
        fsm._changes = []
        fsm._events = []
        fsm.original_action = fsm.do_action

        def do_action(event):
            fsm._events.append(event)
            if (event, fsm.current_state) in TRANSITION_TABLE:
                action_name = TRANSITION_TABLE[(event, fsm.current_state)]
                fsm._changes.append((fsm.current_state, event, action_name))

            fsm.original_action(event)

        fsm.do_action = do_action

        return fsm


class TestState01(TestStateBase):
    """Tests for State 01: Idle."""
    def test_evt01(self):
        """Test Sta1 + Evt1."""
        # Sta1 + Evt1 -> AE-1 -> Sta4
        # Sta1: Idle
        # Evt1: A-ASSOCIATE (rq) primitive from <local user>
        # AE-1: Issue TRANSPORT_CONNECT primitive to <transport service>
        # Sta4: Awaiting TRANSPORT_OPEN from <transport service>
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put([a_abort, 'shutdown'])

        scp.start()

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None
        self.assoc.start()

        time.sleep(0.1)

        assert self.assoc.is_aborted

        assert self.fsm._transitions[:2] == [
            'Sta4',  # Waiting for connection to complete
            'Sta5',  # Waiting for A-ASSOC-AC or -RJ PDU
        ]
        # We only need to test that Sta1 + Evt1 -> AE-1 -> Sta4
        assert self.fsm._changes[:2] == [
            ('Sta1', 'Evt1', 'AE-1'),  # recv A-ASSOC rq primitive
            ('Sta4', 'Evt2', 'AE-2'),  # connection confirmed
        ]

        assert self.fsm._events[0] == 'Evt1'

    @pytest.mark.skip()
    def test_evt02(self):
        """Test Sta1 + Evt2."""
        # Sta1 + Evt2 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt2: Receive TRANSPORT_OPEN from <transport service>
        # Sta1: Idle
        pass

    def test_evt03(self):
        """Test Sta1 + Evt3."""
        # Sta1 + Evt3 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt3: Receive A-ASSOCIATE-AC PDU from <remote>
        # Sta1: Idle
        scp = DummyAE()
        scp.remote_port = 11112
        scp.address = ''

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None

        self.assoc._mode = 'acceptor'
        listen_socket = scp.bind_socket()

        send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        send_socket.connect(('localhost', 11112))
        send_socket.send(a_associate_ac)

        ready, _, _ = select.select([listen_socket], [], [], 0.5)
        if ready:
            self.assoc.dul.scu_socket, _ = listen_socket.accept()

        self.assoc.start()

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt3'
        assert self.fsm.current_state == 'Sta1'

    def test_evt04(self):
        """Test Sta1 + Evt4."""
        # Sta1 + Evt4 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt4: Receive A-ASSOCIATE-RJ PDU from <remote>
        # Sta1: Idle
        scp = DummyAE()
        scp.remote_port = 11112
        scp.address = ''

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None

        self.assoc._mode = 'acceptor'
        listen_socket = scp.bind_socket()

        send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        send_socket.connect(('localhost', 11112))
        send_socket.send(a_associate_rj)

        ready, _, _ = select.select([listen_socket], [], [], 0.5)
        if ready:
            self.assoc.dul.scu_socket, _ = listen_socket.accept()

        self.assoc.start()

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt4'
        assert self.fsm.current_state == 'Sta1'

    @pytest.mark.skip()
    def test_evt05(self):
        """Test Sta1 + Evt5."""
        # Sta1 + Evt5 -> AE-5 -> Sta2
        # Sta1: Idle
        # Evt5: Receive TRANSPORT_INDICATION from <transport service>
        # AE-5: Issue TRANSPORT_RESPONSE to <transport service>
        #       Start ARTIM timer
        # Sta2: Connection open, awaiting A-ASSOCIATE-RQ from <remote>
        scp = DummyAE()
        scp.remote_port = 11112
        scp.address = ''

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None

        self.assoc._mode = 'acceptor'
        listen_socket = scp.bind_socket()

        send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        send_socket.connect(('localhost', 11112))
        #send_socket.send(a_associate_rj)

        ready, _, _ = select.select([listen_socket], [], [], 0.5)
        if ready:
            self.assoc.dul.scu_socket, _ = listen_socket.accept()

        self.assoc.start()

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt5'
        assert self.fsm.current_state == 'Sta1'

    def test_evt06(self):
        """Test Sta1 + Evt6."""
        # Sta1 + Evt6 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt6: Receive A-ASSOCIATE-RQ PDU from <remote>
        # Sta1: Idle
        scp = DummyAE()
        scp.remote_port = 11112
        scp.address = ''

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None

        self.assoc._mode = 'acceptor'
        listen_socket = scp.bind_socket()

        send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        send_socket.connect(('localhost', 11112))
        send_socket.send(a_associate_rq)

        ready, _, _ = select.select([listen_socket], [], [], 0.5)
        if ready:
            self.assoc.dul.scu_socket, _ = listen_socket.accept()

        self.assoc.start()

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt6'
        assert self.fsm.current_state == 'Sta1'

    def test_evt07(self):
        """Test Sta1 + Evt7."""
        # Sta1 + Evt7 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt7: Receive A-ASSOCIATE (accept) primitive from <local user>
        # Sta1: Idle
        self.assoc._mode = "acceptor"
        self.assoc.start()

        self.assoc.dul.send_pdu(self.get_associate('accept'))

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt7'
        assert self.fsm.current_state == 'Sta1'

    def test_evt08(self):
        """Test Sta1 + Evt8."""
        # Sta1 + Evt8 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt8: Receive A-ASSOCIATE (reject) primitive from <local user>
        # Sta1: Idle
        self.assoc._mode = "acceptor"
        self.assoc.start()

        self.assoc.dul.send_pdu(self.get_associate('reject'))

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt8'
        assert self.fsm.current_state == 'Sta1'

    def test_evt09(self):
        """Test Sta1 + Evt9."""
        # Sta1 + Evt9 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt9: Receive P-DATA primitive from <local user>
        # Sta1: Idle
        self.assoc._mode = "acceptor"
        self.assoc.start()

        self.assoc.dul.send_pdu(self.get_pdata())

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt9'
        assert self.fsm.current_state == 'Sta1'

    def test_evt10(self):
        """Test Sta1 + Evt10."""
        # Sta1 + Evt10 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt10: Receive P-DATA-TF PDU from <remote>
        # Sta1: Idle
        scp = DummyAE()
        scp.remote_port = 11112
        scp.address = ''

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None

        self.assoc._mode = 'acceptor'
        listen_socket = scp.bind_socket()

        send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        send_socket.connect(('localhost', 11112))
        send_socket.send(p_data_tf)

        ready, _, _ = select.select([listen_socket], [], [], 0.5)
        if ready:
            self.assoc.dul.scu_socket, _ = listen_socket.accept()

        self.assoc.start()

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt10'
        assert self.fsm.current_state == 'Sta1'

    def test_evt11(self):
        """Test Sta1 + Evt11."""
        # Sta1 + Evt11 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt11: Receive A-RELEASE (rq) primitive from <local user>
        # Sta1: Idle
        self.assoc._mode = "acceptor"
        self.assoc.start()

        self.assoc.dul.send_pdu(self.get_release(False))

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt11'
        assert self.fsm.current_state == 'Sta1'

    def test_evt12(self):
        """Test Sta1 + Evt12."""
        # Sta1 + Evt12 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt12: Receive A-RELEASE-RQ PDU from <remote>
        # Sta1: Idle
        scp = DummyAE()
        scp.remote_port = 11112
        scp.address = ''

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None

        self.assoc._mode = 'acceptor'
        listen_socket = scp.bind_socket()

        send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        send_socket.connect(('localhost', 11112))
        send_socket.send(a_release_rq)

        ready, _, _ = select.select([listen_socket], [], [], 0.5)
        if ready:
            self.assoc.dul.scu_socket, _ = listen_socket.accept()

        self.assoc.start()

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt12'
        assert self.fsm.current_state == 'Sta1'

    def test_evt13(self):
        """Test Sta1 + Evt13."""
        # Sta1 + Evt13 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt13: Receive A-RELEASE-RP PDU from <remote>
        # Sta1: Idle
        scp = DummyAE()
        scp.remote_port = 11112
        scp.address = ''

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None

        self.assoc._mode = 'acceptor'
        listen_socket = scp.bind_socket()

        send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        send_socket.connect(('localhost', 11112))
        send_socket.send(a_release_rp)

        ready, _, _ = select.select([listen_socket], [], [], 0.5)
        if ready:
            self.assoc.dul.scu_socket, _ = listen_socket.accept()

        self.assoc.start()

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt13'
        assert self.fsm.current_state == 'Sta1'

    def test_evt14(self):
        """Test Sta1 + Evt14."""
        # Sta1 + Evt14 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt14: Receive A-RELEASE (rsp) primitive from <local user>
        # Sta1: Idle
        self.assoc._mode = "acceptor"
        self.assoc.start()

        self.assoc.dul.send_pdu(self.get_release(True))

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt14'
        assert self.fsm.current_state == 'Sta1'

    def test_evt15(self):
        """Test Sta1 + Evt15."""
        # Sta1 + Evt15 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt15: Receive A-ABORT (rq) primitive from <local user>
        # Sta1: Idle
        self.assoc._mode = "acceptor"
        self.assoc.start()

        self.assoc.dul.send_pdu(self.get_abort(False))

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt15'
        assert self.fsm.current_state == 'Sta1'

    def test_evt16(self):
        """Test Sta1 + Evt16."""
        # Sta1 + Evt16 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt16: Receive A-ABORT PDU from <remote>
        # Sta1: Idle
        scp = DummyAE()
        scp.remote_port = 11112
        scp.address = ''

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None

        self.assoc._mode = 'acceptor'
        listen_socket = scp.bind_socket()

        send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        send_socket.connect(('localhost', 11112))
        send_socket.send(a_abort)

        ready, _, _ = select.select([listen_socket], [], [], 0.5)
        if ready:
            self.assoc.dul.scu_socket, _ = listen_socket.accept()

        self.assoc.start()

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt16'
        assert self.fsm.current_state == 'Sta1'

    def test_evt17(self):
        """Test Sta1 + Evt17."""
        # Sta1 + Evt17 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt17: Receive TRANSPORT_CLOSED from <transport service>
        # Sta1: Idle
        scp = DummyAE()

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None

        self.assoc._mode = 'acceptor'
        listen_socket = scp.bind_socket()

        send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        send_socket.connect(('localhost', 11112))
        send_socket.send(a_associate_ac)

        self.assoc.dul.scu_socket = listen_socket
        self.assoc.start()

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt17'
        assert self.fsm.current_state == 'Sta1'

    def test_evt18(self):
        """Test Sta1 + Evt18."""
        # Sta1 + Evt18 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt18: ARTIM timer expired from <local service>
        # Sta1: Idle
        self.assoc._mode = "acceptor"
        self.assoc.acse_timeout = 0.05
        self.assoc.dul.artim_timer.timeout_seconds = 0.05
        self.assoc.dul.artim_timer.start()
        self.assoc.start()

        time.sleep(0.2)

        self.assoc.kill()

        assert self.assoc.dul.artim_timer.is_expired

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt18'
        assert self.fsm.current_state == 'Sta1'

    def test_evt19(self):
        """Test Sta1 + Evt19."""
        # Sta1 + Evt19 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt19: Received unrecognised or invalid PDU from <remote>
        # Sta1: Idle
        scp = DummyAE()
        scp.remote_port = 11112
        scp.address = ''

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None

        self.assoc._mode = 'acceptor'
        listen_socket = scp.bind_socket()

        send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        send_socket.connect(('localhost', 11112))

        invalid_data = b'\x08\x00\x00\x00\x00'
        send_socket.send(invalid_data)

        ready, _, _ = select.select([listen_socket], [], [], 0.5)
        if ready:
            self.assoc.dul.scu_socket, _ = listen_socket.accept()

        self.assoc.start()

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt19'
        assert self.fsm.current_state == 'Sta1'


@pytest.mark.skip("Need a TRANSPORT_OPEN indication")
class TestState02(TestStateBase):
    """Tests for State 02: Connection open, waiting for A-ASSOCIATE-RQ."""
    def test_evt01(self):
        """Test Sta2 + Evt1."""
        # Sta2 + Evt1 -> <ignore> -> Sta2
        # Evt1: A-ASSOCIATE (rq) primitive from <local user>
        pass

    def test_evt02(self):
        """Test Sta2 + Evt2."""
        # Sta2 + Evt2 -> <ignore> -> Sta2
        # Evt2: Receive TRANSPORT_OPEN from <transport service>
        pass

    def test_evt03(self):
        """Test Sta2 + Evt3."""
        # Sta2 + Evt3 -> AA-1 -> Sta13
        # Evt3: Receive A-ASSOCIATE-AC PDU from <remote>
        pass

    def test_evt04(self):
        """Test Sta2 + Evt4."""
        # Sta2 + Evt4 -> AA-1 -> Sta13
        # Evt4: Receive A-ASSOCIATE-RJ PDU from <remote>
        pass

    def test_evt05(self):
        """Test Sta2 + Evt5."""
        # Sta2 + Evt5 -> <ignore> -> Sta2
        # Evt5: Receive TRANSPORT_INDICATION from <transport service>
        pass

    def test_evt06(self):
        """Test Sta2 + Evt6."""
        # Sta2 + Evt6 -> AE-6 -> Sta3 or Sta13
        # Evt6: Receive A-ASSOCIATE-RQ PDU from <remote>
        pass

    def test_evt07(self):
        """Test Sta2 + Evt7."""
        # Sta2 + Evt7 -> <ignore> -> Sta2
        # Evt7: Receive A-ASSOCIATE (accept) primitive from <local user>
        pass

    def test_evt08(self):
        """Test Sta2 + Evt8."""
        # Sta2 + Evt8 -> <ignore> -> Sta2
        # Evt8: Receive A-ASSOCIATE (reject) primitive from <local user>
        pass

    def test_evt09(self):
        """Test Sta2 + Evt9."""
        # Sta2 + Evt9 -> <ignore> -> Sta2
        # Evt9: Receive P-DATA primitive from <local user>
        pass

    def test_evt10(self):
        """Test Sta2 + Evt10."""
        # Sta2 + Evt10 -> AA-1 -> Sta13
        # Evt10: Receive P-DATA-TF PDU from <remote>
        pass

    def test_evt11(self):
        """Test Sta2 + Evt11."""
        # Sta2 + Evt11 -> <ignore> -> Sta2
        # Evt11: Receive A-RELEASE (rq) primitive from <local user>
        pass

    def test_evt12(self):
        """Test Sta2 + Evt12."""
        # Sta2 + Evt12 -> AA-1 -> Sta13
        # Evt12: Receive A-RELEASE-RQ PDU from <remote>
        pass

    def test_evt13(self):
        """Test Sta2 + Evt13."""
        # Sta2 + Evt13 -> AA-1 -> Sta13
        # Evt13: Receive A-RELEASE-RP PDU from <remote>
        pass

    def test_evt14(self):
        """Test Sta2 + Evt14."""
        # Sta2 + Evt14 -> <ignore> -> Sta2
        # Evt14: Receive A-RELEASE (rsp) primitive from <local user>
        pass

    def test_evt15(self):
        """Test Sta2 + Evt15."""
        # Sta2 + Evt15 -> <ignore> -> Sta2
        # Evt15: Receive A-ABORT (rq) primitive from <local user>
        pass

    def test_evt16(self):
        """Test Sta2 + Evt16."""
        # Sta2 + Evt16 -> AA-2 -> Sta1
        # Evt16: Receive A-ABORT PDU from <remote>
        pass

    def test_evt17(self):
        """Test Sta2 + Evt17."""
        # Sta2 + Evt17 -> AA-5 -> Sta1
        # Evt17: Receive TRANSPORT_CLOSED from <transport service>
        pass

    def test_evt18(self):
        """Test Sta2 + Evt18."""
        # Sta2 + Evt18 -> AA-2 -> Sta1
        # Evt18: ARTIM timer expired from <local service>
        pass

    def test_evt19(self):
        """Test Sta2 + Evt19."""
        # Sta2 + Evt19 -> AA-1 -> Sta13
        # Evt19: Received unrecognised or invalid PDU from <remote>
        pass


@pytest.mark.skip("Need a way to put the DUL in State 3")
class TestState03(TestStateBase):
    """Tests for State 03: Awaiting A-ASSOCIATE (rsp) primitive."""
    def test_evt01(self):
        """Test Sta3 + Evt1."""
        # Sta3 + Evt1 -> <ignore> -> Sta3
        # Sta3: Awaiting A-ASSOCIATE (rsp) primitive from <local user>
        # Evt1: A-ASSOCIATE (rq) primitive from <local user>
        # Sta3: Awaiting A-ASSOCIATE (rsp) primitive  <local user>
        pass

    @pytest.mark.skip()
    def test_evt02(self):
        """Test Sta1 + Evt2."""
        # Sta1 + Evt2 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt2: Receive TRANSPORT_OPEN from <transport service>
        # Sta1: Idle
        pass

    def test_evt03(self):
        """Test Sta1 + Evt3."""
        # Sta1 + Evt3 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt3: Receive A-ASSOCIATE-AC PDU from <remote>
        # Sta1: Idle
        scp = DummyAE()
        scp.remote_port = 11112
        scp.address = ''

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None

        self.assoc._mode = 'acceptor'
        listen_socket = scp.bind_socket()

        send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        send_socket.connect(('localhost', 11112))
        send_socket.send(a_associate_ac)

        ready, _, _ = select.select([listen_socket], [], [], 0.5)
        if ready:
            self.assoc.dul.scu_socket, _ = listen_socket.accept()

        self.assoc.start()

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt3'
        assert self.fsm.current_state == 'Sta1'

    def test_evt04(self):
        """Test Sta1 + Evt4."""
        # Sta1 + Evt4 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt4: Receive A-ASSOCIATE-RJ PDU from <remote>
        # Sta1: Idle
        scp = DummyAE()
        scp.remote_port = 11112
        scp.address = ''

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None

        self.assoc._mode = 'acceptor'
        listen_socket = scp.bind_socket()

        send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        send_socket.connect(('localhost', 11112))
        send_socket.send(a_associate_rj)

        ready, _, _ = select.select([listen_socket], [], [], 0.5)
        if ready:
            self.assoc.dul.scu_socket, _ = listen_socket.accept()

        self.assoc.start()

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt4'
        assert self.fsm.current_state == 'Sta1'

    @pytest.mark.skip()
    def test_evt05(self):
        """Test Sta1 + Evt5."""
        # Sta1 + Evt5 -> AE-5 -> Sta2
        # Sta1: Idle
        # Evt5: Receive TRANSPORT_INDICATION from <transport service>
        # AE-5: Issue TRANSPORT_RESPONSE to <transport service>
        #       Start ARTIM timer
        # Sta2: Connection open, awaiting A-ASSOCIATE-RQ from <remote>
        scp = DummyAE()
        scp.remote_port = 11112
        scp.address = ''

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None

        self.assoc._mode = 'acceptor'
        listen_socket = scp.bind_socket()

        send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        send_socket.connect(('localhost', 11112))
        #send_socket.send(a_associate_rj)

        ready, _, _ = select.select([listen_socket], [], [], 0.5)
        if ready:
            self.assoc.dul.scu_socket, _ = listen_socket.accept()

        self.assoc.start()

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt5'
        assert self.fsm.current_state == 'Sta1'

    def test_evt06(self):
        """Test Sta1 + Evt6."""
        # Sta1 + Evt6 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt6: Receive A-ASSOCIATE-RQ PDU from <remote>
        # Sta1: Idle
        scp = DummyAE()
        scp.remote_port = 11112
        scp.address = ''

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None

        self.assoc._mode = 'acceptor'
        listen_socket = scp.bind_socket()

        send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        send_socket.connect(('localhost', 11112))
        send_socket.send(a_associate_rq)

        ready, _, _ = select.select([listen_socket], [], [], 0.5)
        if ready:
            self.assoc.dul.scu_socket, _ = listen_socket.accept()

        self.assoc.start()

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt6'
        assert self.fsm.current_state == 'Sta1'

    def test_evt07(self):
        """Test Sta1 + Evt7."""
        # Sta1 + Evt7 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt7: Receive A-ASSOCIATE (accept) primitive from <local user>
        # Sta1: Idle
        self.assoc._mode = "acceptor"
        self.assoc.start()

        self.assoc.dul.send_pdu(self.get_associate('accept'))

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt7'
        assert self.fsm.current_state == 'Sta1'

    def test_evt08(self):
        """Test Sta1 + Evt8."""
        # Sta1 + Evt8 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt8: Receive A-ASSOCIATE (reject) primitive from <local user>
        # Sta1: Idle
        self.assoc._mode = "acceptor"
        self.assoc.start()

        self.assoc.dul.send_pdu(self.get_associate('reject'))

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt8'
        assert self.fsm.current_state == 'Sta1'

    def test_evt09(self):
        """Test Sta1 + Evt9."""
        # Sta1 + Evt9 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt9: Receive P-DATA primitive from <local user>
        # Sta1: Idle
        self.assoc._mode = "acceptor"
        self.assoc.start()

        self.assoc.dul.send_pdu(self.get_pdata())

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt9'
        assert self.fsm.current_state == 'Sta1'

    def test_evt10(self):
        """Test Sta1 + Evt10."""
        # Sta1 + Evt10 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt10: Receive P-DATA-TF PDU from <remote>
        # Sta1: Idle
        scp = DummyAE()
        scp.remote_port = 11112
        scp.address = ''

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None

        self.assoc._mode = 'acceptor'
        listen_socket = scp.bind_socket()

        send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        send_socket.connect(('localhost', 11112))
        send_socket.send(p_data_tf)

        ready, _, _ = select.select([listen_socket], [], [], 0.5)
        if ready:
            self.assoc.dul.scu_socket, _ = listen_socket.accept()

        self.assoc.start()

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt10'
        assert self.fsm.current_state == 'Sta1'

    def test_evt11(self):
        """Test Sta1 + Evt11."""
        # Sta1 + Evt11 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt11: Receive A-RELEASE (rq) primitive from <local user>
        # Sta1: Idle
        self.assoc._mode = "acceptor"
        self.assoc.start()

        self.assoc.dul.send_pdu(self.get_release(False))

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt11'
        assert self.fsm.current_state == 'Sta1'

    def test_evt12(self):
        """Test Sta1 + Evt12."""
        # Sta1 + Evt12 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt12: Receive A-RELEASE-RQ PDU from <remote>
        # Sta1: Idle
        scp = DummyAE()
        scp.remote_port = 11112
        scp.address = ''

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None

        self.assoc._mode = 'acceptor'
        listen_socket = scp.bind_socket()

        send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        send_socket.connect(('localhost', 11112))
        send_socket.send(a_release_rq)

        ready, _, _ = select.select([listen_socket], [], [], 0.5)
        if ready:
            self.assoc.dul.scu_socket, _ = listen_socket.accept()

        self.assoc.start()

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt12'
        assert self.fsm.current_state == 'Sta1'

    def test_evt13(self):
        """Test Sta1 + Evt13."""
        # Sta1 + Evt13 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt13: Receive A-RELEASE-RP PDU from <remote>
        # Sta1: Idle
        scp = DummyAE()
        scp.remote_port = 11112
        scp.address = ''

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None

        self.assoc._mode = 'acceptor'
        listen_socket = scp.bind_socket()

        send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        send_socket.connect(('localhost', 11112))
        send_socket.send(a_release_rp)

        ready, _, _ = select.select([listen_socket], [], [], 0.5)
        if ready:
            self.assoc.dul.scu_socket, _ = listen_socket.accept()

        self.assoc.start()

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt13'
        assert self.fsm.current_state == 'Sta1'

    def test_evt14(self):
        """Test Sta1 + Evt14."""
        # Sta1 + Evt14 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt14: Receive A-RELEASE (rsp) primitive from <local user>
        # Sta1: Idle
        self.assoc._mode = "acceptor"
        self.assoc.start()

        self.assoc.dul.send_pdu(self.get_release(True))

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt14'
        assert self.fsm.current_state == 'Sta1'

    def test_evt15(self):
        """Test Sta1 + Evt15."""
        # Sta1 + Evt15 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt15: Receive A-ABORT (rq) primitive from <local user>
        # Sta1: Idle
        self.assoc._mode = "acceptor"
        self.assoc.start()

        self.assoc.dul.send_pdu(self.get_abort(False))

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt15'
        assert self.fsm.current_state == 'Sta1'

    def test_evt16(self):
        """Test Sta1 + Evt16."""
        # Sta1 + Evt16 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt16: Receive A-ABORT PDU from <remote>
        # Sta1: Idle
        scp = DummyAE()
        scp.remote_port = 11112
        scp.address = ''

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None

        self.assoc._mode = 'acceptor'
        listen_socket = scp.bind_socket()

        send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        send_socket.connect(('localhost', 11112))
        send_socket.send(a_abort)

        ready, _, _ = select.select([listen_socket], [], [], 0.5)
        if ready:
            self.assoc.dul.scu_socket, _ = listen_socket.accept()

        self.assoc.start()

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt16'
        assert self.fsm.current_state == 'Sta1'

    def test_evt17(self):
        """Test Sta1 + Evt17."""
        # Sta1 + Evt17 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt17: Receive TRANSPORT_CLOSED from <transport service>
        # Sta1: Idle
        scp = DummyAE()

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None

        self.assoc._mode = 'acceptor'
        listen_socket = scp.bind_socket()

        send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        send_socket.connect(('localhost', 11112))
        send_socket.send(a_associate_ac)

        self.assoc.dul.scu_socket = listen_socket
        self.assoc.start()

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt17'
        assert self.fsm.current_state == 'Sta1'

    def test_evt18(self):
        """Test Sta1 + Evt18."""
        # Sta1 + Evt18 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt18: ARTIM timer expired from <local service>
        # Sta1: Idle
        self.assoc._mode = "acceptor"
        self.assoc.acse_timeout = 0.05
        self.assoc.dul.artim_timer.timeout_seconds = 0.05
        self.assoc.dul.artim_timer.start()
        self.assoc.start()

        time.sleep(0.2)

        self.assoc.kill()

        assert self.assoc.dul.artim_timer.is_expired

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt18'
        assert self.fsm.current_state == 'Sta1'

    def test_evt19(self):
        """Test Sta1 + Evt19."""
        # Sta1 + Evt19 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt19: Received unrecognised or invalid PDU from <remote>
        # Sta1: Idle
        scp = DummyAE()
        scp.remote_port = 11112
        scp.address = ''

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None

        self.assoc._mode = 'acceptor'
        listen_socket = scp.bind_socket()

        send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        send_socket.connect(('localhost', 11112))

        invalid_data = b'\x08\x00\x00\x00\x00'
        send_socket.send(invalid_data)

        ready, _, _ = select.select([listen_socket], [], [], 0.5)
        if ready:
            self.assoc.dul.scu_socket, _ = listen_socket.accept()

        self.assoc.start()

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt19'
        assert self.fsm.current_state == 'Sta1'


@pytest.mark.skip("Need a way to put the DUL in State 4")
class TestState04(TestStateBase):
    """Tests for State 04: Awaiting TRANSPORT_OPEN from <transport service>."""
    def test_evt01(self):
        """Test Sta1 + Evt1."""
        # Sta4 + Evt1 -> <ignore> -> Sta4
        # Sta4: Awaiting TRANSPORT_OPEN from <transport service>
        # Evt1: A-ASSOCIATE (rq) primitive from <local user>
        # Sta4: Awaiting TRANSPORT_OPEN from <transport service>
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put([None, 'shutdown'])

        scp.start()

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None
        self.assoc.dul.send_pdu(self.get_associate('request'))
        self.assoc.dul.send_pdu(self.get_associate('request'))
        print(self.assoc.dul.to_provider_queue.queue)
        self.assoc.start()

        time.sleep(0.1)

        #assert self.fsm._transitions == ['Sta4']
        # We only need to test that Sta1 + Evt1 -> AE-1 -> Sta4
        assert self.fsm._changes == [
            ('Sta1', 'Evt1', 'AE-1'),  # recv A-ASSOC rq primitive
        ]
        assert self.fsm._events == ['Evt1', 'Evt1']

    @pytest.mark.skip()
    def test_evt02(self):
        """Test Sta1 + Evt2."""
        # Sta1 + Evt2 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt2: Receive TRANSPORT_OPEN from <transport service>
        # Sta1: Idle
        pass

    def test_evt03(self):
        """Test Sta1 + Evt3."""
        # Sta1 + Evt3 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt3: Receive A-ASSOCIATE-AC PDU from <remote>
        # Sta1: Idle
        scp = DummyAE()
        scp.remote_port = 11112
        scp.address = ''

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None

        self.assoc._mode = 'acceptor'
        listen_socket = scp.bind_socket()

        send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        send_socket.connect(('localhost', 11112))
        send_socket.send(a_associate_ac)

        ready, _, _ = select.select([listen_socket], [], [], 0.5)
        if ready:
            self.assoc.dul.scu_socket, _ = listen_socket.accept()

        self.assoc.start()

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt3'
        assert self.fsm.current_state == 'Sta1'

    def test_evt04(self):
        """Test Sta1 + Evt4."""
        # Sta1 + Evt4 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt4: Receive A-ASSOCIATE-RJ PDU from <remote>
        # Sta1: Idle
        scp = DummyAE()
        scp.remote_port = 11112
        scp.address = ''

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None

        self.assoc._mode = 'acceptor'
        listen_socket = scp.bind_socket()

        send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        send_socket.connect(('localhost', 11112))
        send_socket.send(a_associate_rj)

        ready, _, _ = select.select([listen_socket], [], [], 0.5)
        if ready:
            self.assoc.dul.scu_socket, _ = listen_socket.accept()

        self.assoc.start()

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt4'
        assert self.fsm.current_state == 'Sta1'

    @pytest.mark.skip()
    def test_evt05(self):
        """Test Sta1 + Evt5."""
        # Sta1 + Evt5 -> AE-5 -> Sta2
        # Sta1: Idle
        # Evt5: Receive TRANSPORT_INDICATION from <transport service>
        # AE-5: Issue TRANSPORT_RESPONSE to <transport service>
        #       Start ARTIM timer
        # Sta2: Connection open, awaiting A-ASSOCIATE-RQ from <remote>
        scp = DummyAE()
        scp.remote_port = 11112
        scp.address = ''

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None

        self.assoc._mode = 'acceptor'
        listen_socket = scp.bind_socket()

        send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        send_socket.connect(('localhost', 11112))
        #send_socket.send(a_associate_rj)

        ready, _, _ = select.select([listen_socket], [], [], 0.5)
        if ready:
            self.assoc.dul.scu_socket, _ = listen_socket.accept()

        self.assoc.start()

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt5'
        assert self.fsm.current_state == 'Sta1'

    def test_evt06(self):
        """Test Sta1 + Evt6."""
        # Sta1 + Evt6 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt6: Receive A-ASSOCIATE-RQ PDU from <remote>
        # Sta1: Idle
        scp = DummyAE()
        scp.remote_port = 11112
        scp.address = ''

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None

        self.assoc._mode = 'acceptor'
        listen_socket = scp.bind_socket()

        send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        send_socket.connect(('localhost', 11112))
        send_socket.send(a_associate_rq)

        ready, _, _ = select.select([listen_socket], [], [], 0.5)
        if ready:
            self.assoc.dul.scu_socket, _ = listen_socket.accept()

        self.assoc.start()

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt6'
        assert self.fsm.current_state == 'Sta1'

    def test_evt07(self):
        """Test Sta1 + Evt7."""
        # Sta1 + Evt7 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt7: Receive A-ASSOCIATE (accept) primitive from <local user>
        # Sta1: Idle
        self.assoc._mode = "acceptor"
        self.assoc.start()

        self.assoc.dul.send_pdu(self.get_associate('accept'))

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt7'
        assert self.fsm.current_state == 'Sta1'

    def test_evt08(self):
        """Test Sta1 + Evt8."""
        # Sta1 + Evt8 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt8: Receive A-ASSOCIATE (reject) primitive from <local user>
        # Sta1: Idle
        self.assoc._mode = "acceptor"
        self.assoc.start()

        self.assoc.dul.send_pdu(self.get_associate('reject'))

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt8'
        assert self.fsm.current_state == 'Sta1'

    def test_evt09(self):
        """Test Sta1 + Evt9."""
        # Sta1 + Evt9 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt9: Receive P-DATA primitive from <local user>
        # Sta1: Idle
        self.assoc._mode = "acceptor"
        self.assoc.start()

        self.assoc.dul.send_pdu(self.get_pdata())

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt9'
        assert self.fsm.current_state == 'Sta1'

    def test_evt10(self):
        """Test Sta1 + Evt10."""
        # Sta1 + Evt10 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt10: Receive P-DATA-TF PDU from <remote>
        # Sta1: Idle
        scp = DummyAE()
        scp.remote_port = 11112
        scp.address = ''

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None

        self.assoc._mode = 'acceptor'
        listen_socket = scp.bind_socket()

        send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        send_socket.connect(('localhost', 11112))
        send_socket.send(p_data_tf)

        ready, _, _ = select.select([listen_socket], [], [], 0.5)
        if ready:
            self.assoc.dul.scu_socket, _ = listen_socket.accept()

        self.assoc.start()

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt10'
        assert self.fsm.current_state == 'Sta1'

    def test_evt11(self):
        """Test Sta1 + Evt11."""
        # Sta1 + Evt11 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt11: Receive A-RELEASE (rq) primitive from <local user>
        # Sta1: Idle
        self.assoc._mode = "acceptor"
        self.assoc.start()

        self.assoc.dul.send_pdu(self.get_release(False))

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt11'
        assert self.fsm.current_state == 'Sta1'

    def test_evt12(self):
        """Test Sta1 + Evt12."""
        # Sta1 + Evt12 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt12: Receive A-RELEASE-RQ PDU from <remote>
        # Sta1: Idle
        scp = DummyAE()
        scp.remote_port = 11112
        scp.address = ''

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None

        self.assoc._mode = 'acceptor'
        listen_socket = scp.bind_socket()

        send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        send_socket.connect(('localhost', 11112))
        send_socket.send(a_release_rq)

        ready, _, _ = select.select([listen_socket], [], [], 0.5)
        if ready:
            self.assoc.dul.scu_socket, _ = listen_socket.accept()

        self.assoc.start()

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt12'
        assert self.fsm.current_state == 'Sta1'

    def test_evt13(self):
        """Test Sta1 + Evt13."""
        # Sta1 + Evt13 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt13: Receive A-RELEASE-RP PDU from <remote>
        # Sta1: Idle
        scp = DummyAE()
        scp.remote_port = 11112
        scp.address = ''

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None

        self.assoc._mode = 'acceptor'
        listen_socket = scp.bind_socket()

        send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        send_socket.connect(('localhost', 11112))
        send_socket.send(a_release_rp)

        ready, _, _ = select.select([listen_socket], [], [], 0.5)
        if ready:
            self.assoc.dul.scu_socket, _ = listen_socket.accept()

        self.assoc.start()

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt13'
        assert self.fsm.current_state == 'Sta1'

    def test_evt14(self):
        """Test Sta1 + Evt14."""
        # Sta1 + Evt14 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt14: Receive A-RELEASE (rsp) primitive from <local user>
        # Sta1: Idle
        self.assoc._mode = "acceptor"
        self.assoc.start()

        self.assoc.dul.send_pdu(self.get_release(True))

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt14'
        assert self.fsm.current_state == 'Sta1'

    def test_evt15(self):
        """Test Sta1 + Evt15."""
        # Sta1 + Evt15 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt15: Receive A-ABORT (rq) primitive from <local user>
        # Sta1: Idle
        self.assoc._mode = "acceptor"
        self.assoc.start()

        self.assoc.dul.send_pdu(self.get_abort(False))

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt15'
        assert self.fsm.current_state == 'Sta1'

    def test_evt16(self):
        """Test Sta1 + Evt16."""
        # Sta1 + Evt16 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt16: Receive A-ABORT PDU from <remote>
        # Sta1: Idle
        scp = DummyAE()
        scp.remote_port = 11112
        scp.address = ''

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None

        self.assoc._mode = 'acceptor'
        listen_socket = scp.bind_socket()

        send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        send_socket.connect(('localhost', 11112))
        send_socket.send(a_abort)

        ready, _, _ = select.select([listen_socket], [], [], 0.5)
        if ready:
            self.assoc.dul.scu_socket, _ = listen_socket.accept()

        self.assoc.start()

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt16'
        assert self.fsm.current_state == 'Sta1'

    def test_evt17(self):
        """Test Sta1 + Evt17."""
        # Sta1 + Evt17 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt17: Receive TRANSPORT_CLOSED from <transport service>
        # Sta1: Idle
        scp = DummyAE()

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None

        self.assoc._mode = 'acceptor'
        listen_socket = scp.bind_socket()

        send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        send_socket.connect(('localhost', 11112))
        send_socket.send(a_associate_ac)

        self.assoc.dul.scu_socket = listen_socket
        self.assoc.start()

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt17'
        assert self.fsm.current_state == 'Sta1'

    def test_evt18(self):
        """Test Sta1 + Evt18."""
        # Sta1 + Evt18 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt18: ARTIM timer expired from <local service>
        # Sta1: Idle
        self.assoc._mode = "acceptor"
        self.assoc.acse_timeout = 0.05
        self.assoc.dul.artim_timer.timeout_seconds = 0.05
        self.assoc.dul.artim_timer.start()
        self.assoc.start()

        time.sleep(0.2)

        self.assoc.kill()

        assert self.assoc.dul.artim_timer.is_expired

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt18'
        assert self.fsm.current_state == 'Sta1'

    def test_evt19(self):
        """Test Sta1 + Evt19."""
        # Sta1 + Evt19 -> <ignore> -> Sta1
        # Sta1: Idle
        # Evt19: Received unrecognised or invalid PDU from <remote>
        # Sta1: Idle
        scp = DummyAE()
        scp.remote_port = 11112
        scp.address = ''

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None

        self.assoc._mode = 'acceptor'
        listen_socket = scp.bind_socket()

        send_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        send_socket.connect(('localhost', 11112))

        invalid_data = b'\x08\x00\x00\x00\x00'
        send_socket.send(invalid_data)

        ready, _, _ = select.select([listen_socket], [], [], 0.5)
        if ready:
            self.assoc.dul.scu_socket, _ = listen_socket.accept()

        self.assoc.start()

        time.sleep(0.1)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == 'Evt19'
        assert self.fsm.current_state == 'Sta1'


class TestState05(TestStateBase):
    """Tests for State 05: Awaiting A-ASSOCIATE-AC or A-ASSOCIATE-RJ PDU."""
    def test_evt01(self):
        """Test Sta5 + Evt1."""
        # Sta5 + Evt1 -> <ignore> -> Sta5
        # Evt1: A-ASSOCIATE (rq) primitive from <local user>
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(['wait', 0.4, 'shutdown'])

        scp.start()

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None
        self.assoc.start()

        time.sleep(0.3)

        #self.assoc.acse.send_abort(self.assoc, 0x00)
        self.assoc.dul.send_pdu(self.get_associate('request'))

        time.sleep(0.2)

        self.fsm.current_state = 'Sta13'

        assert self.fsm._changes[:2] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
        ]
        assert self.fsm._transitions[:2] == ['Sta4', 'Sta5']
        assert self.fsm._events[:3] == ['Evt1', 'Evt2', 'Evt1']

        scp.stop()

    @pytest.mark.skip()
    def test_evt02(self):
        """Test Sta5 + Evt2."""
        # Sta5 + Evt2 -> <ignore> -> Sta5
        # Evt2: Receive TRANSPORT_OPEN from <transport service>
        pass

    def test_evt03(self):
        """Test Sta5 + Evt3."""
        # Sta5 + Evt3 -> AE-3 -> Sta6
        # Evt3: Receive A-ASSOCIATE-AC PDU from <remote>
        # AE-3: Issue A-ASSOCIATE (ac) primitive
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put([a_associate_ac, 'shutdown'])

        scp.start()

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None
        self.assoc.start()

        time.sleep(0.1)

        assert self.fsm._changes[:3] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt3', 'AE-3'),
        ]
        assert self.fsm._events[:3] == ['Evt1', 'Evt2', 'Evt3']

    def test_evt04(self):
        """Test Sta5 + Evt4."""
        # Sta5 + Evt4 -> AE-4 -> Sta1
        # Evt4: Receive A-ASSOCIATE-RJ PDU from <remote>
        # AE-4: Issue A-ASSOCIATE (rj) primitive
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put([a_associate_rj, 'shutdown'])

        scp.start()

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None
        self.assoc.start()

        time.sleep(0.1)

        assert self.fsm._changes[:3] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt4', 'AE-4'),
        ]
        assert self.fsm._events[:3] == ['Evt1', 'Evt2', 'Evt4']

    @pytest.mark.skip()
    def test_evt05(self):
        """Test Sta1 + Evt5."""
        # Sta5 + Evt5 -> <ignore> -> Sta5
        # Evt5: Receive TRANSPORT_INDICATION from <transport service>
        # AE-5: Issue TRANSPORT_RESPONSE to <transport service>
        #       Start ARTIM timer
        pass

    def test_evt06(self):
        """Test Sta5 + Evt6."""
        # Sta5 + Evt6 -> AA-8 -> Sta13
        # Evt6: Receive A-ASSOCIATE-RQ PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(a_associate_rq)
        scp.queue.put('shutdown')

        scp.start()

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None
        self.assoc.start()

        time.sleep(0.1)

        assert self.fsm._changes[:3] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt6', 'AA-8'),
        ]
        assert self.fsm._events[:3] == ['Evt1', 'Evt2', 'Evt6']
        # Issue A-ABORT PDU
        assert scp.received[1] == b'\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00'

    def test_evt07(self):
        """Test Sta5 + Evt7."""
        # Sta5 + Evt7 -> <ignore> -> Sta5
        # Evt7: Receive A-ASSOCIATE (accept) primitive from <local user>
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(['wait', 0.4, 'shutdown'])

        scp.start()

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None
        self.assoc.acse_timeout = 1
        self.assoc.start()

        time.sleep(0.3)

        self.assoc.dul.send_pdu(self.get_associate('accept'))

        time.sleep(0.2)

        assert self.fsm._changes[:2] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
        ]
        assert self.fsm._transitions[:2] == ['Sta4', 'Sta5']
        assert self.fsm._events[:3] == ['Evt1', 'Evt2', 'Evt7']

    def test_evt08(self):
        """Test Sta5 + Evt8."""
        # Sta5 + Evt8 -> <ignore> -> Sta5
        # Evt8: Receive A-ASSOCIATE (reject) primitive from <local user>
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(['wait', 0.4, 'shutdown'])

        scp.start()

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None
        self.assoc.acse_timeout = 1
        self.assoc.start()

        time.sleep(0.3)

        #self.assoc.acse.send_abort(self.assoc, 0x00)
        self.assoc.dul.send_pdu(self.get_associate('reject'))

        time.sleep(0.2)

        assert self.fsm._changes[:2] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
        ]
        assert self.fsm._transitions[:2] == ['Sta4', 'Sta5']
        assert self.fsm._events[:3] == ['Evt1', 'Evt2', 'Evt8']

    def test_evt09(self):
        """Test Sta5 + Evt9."""
        # Sta5 + Evt9 -> <ignore> -> Sta5
        # Evt9: Receive P-DATA primitive from <local user>
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(['wait', 0.4, 'shutdown'])

        scp.start()

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None
        self.assoc.acse_timeout = 1
        self.assoc.start()

        time.sleep(0.3)

        #self.assoc.acse.send_abort(self.assoc, 0x00)
        self.assoc.dul.send_pdu(self.get_pdata())

        time.sleep(0.2)

        assert self.fsm._changes[:2] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
        ]
        assert self.fsm._transitions[:2] == ['Sta4', 'Sta5']
        assert self.fsm._events[:3] == ['Evt1', 'Evt2', 'Evt9']

    def test_evt10(self):
        """Test Sta5 + Evt10."""
        # Sta5 + Evt10 -> AA-8 -> Sta13
        # Evt10: Receive P-DATA-TF PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(p_data_tf)
        scp.queue.put('shutdown')

        scp.start()

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None
        self.assoc.start()

        time.sleep(0.1)

        assert self.fsm._changes[:3] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt10', 'AA-8'),
        ]
        assert self.fsm._transitions[:3] == ['Sta4', 'Sta5', 'Sta13']
        assert self.fsm._events[:3] == ['Evt1', 'Evt2', 'Evt10']
        # Issue A-ABORT PDU
        assert scp.received[1] == b'\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00'

    def test_evt11(self):
        """Test Sta5 + Evt11."""
        # Sta5 + Evt11 -> <ignore> -> Sta5
        # Evt11: Receive A-RELEASE (rq) primitive from <local user>
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(['wait', 0.4, 'shutdown'])

        scp.start()

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None
        self.assoc.acse_timeout = 1
        self.assoc.start()

        time.sleep(0.3)

        #self.assoc.acse.send_abort(self.assoc, 0x00)
        self.assoc.dul.send_pdu(self.get_release(False))

        time.sleep(0.2)

        assert self.fsm._changes[:2] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
        ]
        assert self.fsm._transitions[:2] == ['Sta4', 'Sta5']
        assert self.fsm._events[:3] == ['Evt1', 'Evt2', 'Evt11']

    def test_evt12(self):
        """Test Sta5 + Evt12."""
        # Sta5 + Evt12 -> AA-8 -> Sta13
        # Evt12: Receive A-RELEASE-RQ PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(a_release_rq)
        scp.queue.put('shutdown')

        scp.start()

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None
        self.assoc.start()

        time.sleep(0.1)

        assert self.fsm._changes[:3] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt12', 'AA-8'),
        ]
        assert self.fsm._transitions[:3] == ['Sta4', 'Sta5', 'Sta13']
        assert self.fsm._events[:3] == ['Evt1', 'Evt2', 'Evt12']
        # Issue A-ABORT PDU
        assert scp.received[1] == b'\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00'

    def test_evt13(self):
        """Test Sta5 + Evt13."""
        # Sta5 + Evt13 -> AA-8 -> Sta13
        # Evt13: Receive A-RELEASE-RP PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(a_release_rp)
        scp.queue.put('shutdown')

        scp.start()

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None
        self.assoc.start()

        time.sleep(0.1)

        assert self.fsm._changes[:3] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt13', 'AA-8'),
        ]
        assert self.fsm._transitions[:3] == ['Sta4', 'Sta5', 'Sta13']
        assert self.fsm._events[:3] == ['Evt1', 'Evt2', 'Evt13']
        # Issue A-ABORT PDU
        assert scp.received[1] == b'\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00'

    def test_evt14(self):
        """Test Sta5 + Evt14."""
        # Sta5 + Evt14 -> <ignore> -> Sta5
        # Evt14: Receive A-RELEASE (rsp) primitive from <local user>
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(['wait', 0.4, 'shutdown'])

        scp.start()

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None
        self.assoc.acse_timeout = 1
        self.assoc.start()

        time.sleep(0.3)

        #self.assoc.acse.send_abort(self.assoc, 0x00)
        self.assoc.dul.send_pdu(self.get_release(True))

        time.sleep(0.2)

        assert self.fsm._changes[:2] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
        ]
        assert self.fsm._transitions[:2] == ['Sta4', 'Sta5']
        assert self.fsm._events[:3] == ['Evt1', 'Evt2', 'Evt14']

    def test_evt15(self):
        """Test Sta5 + Evt15."""
        # Sta5 + Evt15 -> AA-1 -> Sta13
        # Evt15: Receive A-ABORT (rq) primitive from <local user>
        # AA-1: Send A-ABORT PDU and restart ARTIM
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(['wait', 0.4])
        scp.queue.put(None)
        scp.queue.put('shutdown')

        scp.start()

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None
        self.assoc.acse_timeout = 1
        self.assoc.start()

        time.sleep(0.3)

        #self.assoc.acse.send_abort(self.assoc, 0x00)
        self.assoc.dul.send_pdu(self.get_abort(False))

        time.sleep(0.2)

        assert self.fsm._changes[:4] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt15', 'AA-1'),
            ('Sta13', 'Evt17', 'AR-5'),
        ]
        assert self.fsm._transitions[:4] == ['Sta4', 'Sta5', 'Sta13', 'Sta1']
        assert self.fsm._events[:4] == ['Evt1', 'Evt2', 'Evt15', 'Evt17']

        # Issue A-ABORT PDU
        assert scp.received[1] == b'\x07\x00\x00\x00\x00\x04\x00\x00\x00\x00'

    def test_evt16(self):
        """Test Sta5 + Evt16."""
        # Sta5 + Evt16 -> AA-3 -> Sta1
        # Evt16: Receive A-ABORT PDU from <remote>
        # AA-3: If service user initiated:
        #           Issue A-ABORT primitve and close transport
        #       Otherwise
        #           Issue A-P-ABORT primitive and close transport
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(a_abort)
        scp.queue.put('shutdown')

        scp.start()

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None
        self.assoc.start()

        time.sleep(0.1)

        assert self.fsm._changes[:3] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt16', 'AA-3'),
        ]
        assert self.fsm._transitions[:3] == ['Sta4', 'Sta5', 'Sta1']
        assert self.fsm._events[:3] == ['Evt1', 'Evt2', 'Evt16']

    def test_evt17(self):
        """Test Sta5 + Evt17."""
        # Sta1 + Evt17 -> AA-4 -> Sta1
        # Evt17: Receive TRANSPORT_CLOSED from <transport service>
        # AA-4: Issue A-P-ABORT primitive
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(['wait', 0.2])
        scp.queue.put('shutdown')

        scp.start()

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None
        self.assoc.start()

        time.sleep(0.5)

        assert self.fsm._changes[:3] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt17', 'AA-4'),
        ]
        assert self.fsm._transitions[:3] == ['Sta4', 'Sta5', 'Sta1']
        assert self.fsm._events[:3] == ['Evt1', 'Evt2', 'Evt17']

    @pytest.mark.skip()
    def test_evt18(self):
        """Test Sta5 + Evt18."""
        # Sta5 + Evt18 -> <ignore> -> Sta5
        # Evt18: ARTIM timer expired from <local service>
        pass

    def test_evt19(self):
        """Test Sta5 + Evt19."""
        # Sta5 + Evt19 -> AA-8 -> Sta13
        # Evt19: Received unrecognised or invalid PDU from <remote>
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(b'\x08\x00\x00\x00\x00')
        scp.queue.put('shutdown')

        scp.start()

        assert self.fsm.current_state == 'Sta1'
        assert self.assoc.dul.scu_socket is None
        self.assoc.start()

        time.sleep(0.1)

        assert self.fsm._changes[:3] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt19', 'AA-8'),
        ]
        assert self.fsm._transitions[:3] == ['Sta4', 'Sta5', 'Sta13']
        assert self.fsm._events[:3] == ['Evt1', 'Evt2', 'Evt19']
        # Issue A-ABORT PDU
        assert scp.received[1] == b'\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00'


class TestState06(TestStateBase):
    """Tests for State 06: Association established and ready for data."""
    def test_evt01(self):
        """Test Sta6 + Evt1."""
        # Sta6 + Evt1 -> <ignore> -> Sta6
        # Evt1: A-ASSOCIATE (rq) primitive from <local user>
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(['skip', a_associate_ac])
        scp.queue.put(['wait', 0.4, 'shutdown'])
        scp.start()

        self.assoc.start()

        time.sleep(0.3)

        self.assoc.dul.send_pdu(self.get_associate('request'))

        time.sleep(0.2)

        assert self.fsm._changes[:3] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt3', 'AE-3'),
        ]
        assert self.fsm._transitions[:3] == ['Sta4', 'Sta5', 'Sta6']
        assert self.fsm._events[:4] == ['Evt1', 'Evt2', 'Evt3', 'Evt1']

    @pytest.mark.skip()
    def test_evt02(self):
        """Test Sta6 + Evt2."""
        # Sta6 + Evt2 -> <ignore> -> Sta6
        # Evt2: Receive TRANSPORT_OPEN from <transport service>
        pass

    def test_evt03(self):
        """Test Sta6 + Evt3."""
        # Sta6 + Evt3 -> AA-8 -> Sta13
        # Evt3: Receive A-ASSOCIATE-AC PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(['skip', a_associate_ac])
        scp.queue.put(a_associate_ac)
        scp.queue.put('shutdown')
        scp.start()

        self.assoc.start()

        time.sleep(0.2)

        assert self.fsm._changes[:4] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt3', 'AE-3'),
            ('Sta6', 'Evt3', 'AA-8'),
        ]
        assert self.fsm._transitions[:4] == ['Sta4', 'Sta5', 'Sta6', 'Sta13']
        assert self.fsm._events[:4] == ['Evt1', 'Evt2', 'Evt3', 'Evt3']

        # Issue A-ABORT PDU
        assert scp.received[1] == b'\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00'

    def test_evt04(self):
        """Test Sta6 + Evt4."""
        # Sta6 + Evt4 -> AA-8 -> Sta13
        # Evt4: Receive A-ASSOCIATE-RJ PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(['skip', a_associate_ac])
        scp.queue.put(a_associate_rj)
        scp.queue.put('shutdown')
        scp.start()

        self.assoc.start()

        time.sleep(0.2)

        assert self.fsm._changes[:4] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt3', 'AE-3'),
            ('Sta6', 'Evt4', 'AA-8'),
        ]
        assert self.fsm._transitions[:4] == ['Sta4', 'Sta5', 'Sta6', 'Sta13']
        assert self.fsm._events[:4] == ['Evt1', 'Evt2', 'Evt3', 'Evt4']

        # Issue A-ABORT PDU
        assert scp.received[1] == b'\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00'

    @pytest.mark.skip()
    def test_evt05(self):
        """Test Sta6 + Evt5."""
        # Sta6 + Evt5 -> <ignore> -> Sta6
        # Evt5: Receive TRANSPORT_INDICATION from <transport service>
        pass

    def test_evt06(self):
        """Test Sta6 + Evt6."""
        # Sta6 + Evt6 -> AA-8 -> Sta13
        # Evt6: Receive A-ASSOCIATE-RQ PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(['skip', a_associate_ac])
        scp.queue.put(a_associate_rq)
        scp.queue.put('shutdown')
        scp.start()

        self.assoc.start()

        time.sleep(0.2)

        assert self.fsm._changes[:4] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt3', 'AE-3'),
            ('Sta6', 'Evt6', 'AA-8'),
        ]
        assert self.fsm._transitions[:4] == ['Sta4', 'Sta5', 'Sta6', 'Sta13']
        assert self.fsm._events[:4] == ['Evt1', 'Evt2', 'Evt3', 'Evt6']

        # Issue A-ABORT PDU
        assert scp.received[1] == b'\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00'

    def test_evt07(self):
        """Test Sta6 + Evt7."""
        # Sta6 + Evt7 -> <ignore> -> Sta6
        # Evt7: Receive A-ASSOCIATE (accept) primitive from <local user>
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(['skip', a_associate_ac])
        scp.queue.put(['wait', 0.3])
        scp.queue.put(['skip', a_abort])
        scp.queue.put('shutdown')
        scp.start()

        self.assoc.start()

        time.sleep(0.2)

        self.assoc.dul.send_pdu(self.get_associate('accept'))

        time.sleep(0.2)

        assert self.fsm._changes[:3] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt3', 'AE-3'),
        ]
        assert self.fsm._transitions[:3] == ['Sta4', 'Sta5', 'Sta6']
        assert self.fsm._events[:4] == ['Evt1', 'Evt2', 'Evt3', 'Evt7']

    def test_evt08(self):
        """Test Sta6 + Evt8."""
        # Sta6 + Evt8 -> <ignore> -> Sta6
        # Evt8: Receive A-ASSOCIATE (reject) primitive from <local user>
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(['skip', a_associate_ac])
        scp.queue.put(['wait', 0.3])
        scp.queue.put(['skip', a_abort])
        scp.queue.put('shutdown')
        scp.start()

        self.assoc.start()

        time.sleep(0.2)

        self.assoc.dul.send_pdu(self.get_associate('reject'))

        time.sleep(0.2)

        assert self.fsm._changes[:3] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt3', 'AE-3'),
        ]
        assert self.fsm._transitions[:3] == ['Sta4', 'Sta5', 'Sta6']
        assert self.fsm._events[:4] == ['Evt1', 'Evt2', 'Evt3', 'Evt8']

    def test_evt09(self):
        """Test Sta6 + Evt9."""
        # Sta6 + Evt9 -> DT-1 -> Sta6
        # Evt9: Receive P-DATA primitive from <local user>
        # DT-1: Send P-DATA-TD PDU
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(['skip', a_associate_ac])
        scp.queue.put(None)
        scp.queue.put(['skip', a_abort])
        scp.queue.put('shutdown')
        scp.start()

        self.assoc.start()

        time.sleep(0.2)

        self.assoc.dul.send_pdu(self.get_pdata())

        time.sleep(0.2)

        assert self.fsm._changes[:4] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt3', 'AE-3'),
            ('Sta6', 'Evt9', 'DT-1'),
        ]
        assert self.fsm._transitions[:4] == ['Sta4', 'Sta5', 'Sta6', 'Sta6']
        assert self.fsm._events[:4] == ['Evt1', 'Evt2', 'Evt3', 'Evt9']

    def test_evt10(self):
        """Test Sta6 + Evt10."""
        # Sta6 + Evt10 -> DT-2 -> Sta6
        # Evt10: Receive P-DATA-TF PDU from <remote>
        # DT-2: Send P-DATA primitive
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(['skip', a_associate_ac])
        scp.queue.put(['skip', p_data_tf])
        scp.queue.put(['skip', a_abort])
        scp.queue.put('shutdown')
        scp.start()

        self.assoc.start()

        time.sleep(0.2)

        assert self.fsm._changes[:4] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt3', 'AE-3'),
            ('Sta6', 'Evt10', 'DT-2'),
        ]
        assert self.fsm._transitions[:4] == ['Sta4', 'Sta5', 'Sta6', 'Sta6']
        assert self.fsm._events[:4] == ['Evt1', 'Evt2', 'Evt3', 'Evt10']

    def test_evt11(self):
        """Test Sta6 + Evt11."""
        # Sta6 + Evt11 -> AR-1 -> Sta7
        # Evt11: Receive A-RELEASE (rq) primitive from <local user>
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(['skip', a_associate_ac])
        scp.queue.put(['wait', 0.3])
        scp.queue.put(['skip', a_abort])
        scp.queue.put('shutdown')
        scp.start()

        self.assoc.start()

        time.sleep(0.2)

        self.assoc.dul.send_pdu(self.get_release(False))

        time.sleep(0.2)

        assert self.fsm._changes[:3] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt3', 'AE-3'),
        ]
        assert self.fsm._transitions[:3] == ['Sta4', 'Sta5', 'Sta6']
        assert self.fsm._events[:4] == ['Evt1', 'Evt2', 'Evt3', 'Evt11']

    def test_evt12(self):
        """Test Sta6 + Evt12."""
        # Sta6 + Evt12 -> AR-2 -> Sta8
        # Evt12: Receive A-RELEASE-RQ PDU from <remote>
        # AR-2: Issue A-RELEASE (rq) primitive
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(['skip', a_associate_ac])
        scp.queue.put(a_release_rq)
        scp.queue.put('shutdown')
        scp.start()

        self.assoc.start()

        time.sleep(0.2)

        assert self.fsm._changes[:4] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt3', 'AE-3'),
            ('Sta6', 'Evt12', 'AR-2'),
        ]
        assert self.fsm._transitions[:4] == ['Sta4', 'Sta5', 'Sta6', 'Sta8']
        assert self.fsm._events[:4] == ['Evt1', 'Evt2', 'Evt3', 'Evt12']

    def test_evt13(self):
        """Test Sta6 + Evt13."""
        # Sta6 + Evt13 -> AA-8 -> Sta13
        # Evt13: Receive A-RELEASE-RP PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(['skip', a_associate_ac])
        scp.queue.put(a_release_rp)
        scp.queue.put('shutdown')
        scp.start()

        self.assoc.start()

        time.sleep(0.2)

        assert self.fsm._changes[:4] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt3', 'AE-3'),
            ('Sta6', 'Evt13', 'AA-8'),
        ]
        assert self.fsm._transitions[:4] == ['Sta4', 'Sta5', 'Sta6', 'Sta13']
        assert self.fsm._events[:4] == ['Evt1', 'Evt2', 'Evt3', 'Evt13']

        # Issue A-ABORT PDU
        assert scp.received[1] == b'\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00'

    def test_evt14(self):
        """Test Sta6 + Evt14."""
        # Sta6 + Evt14 -> <ignore> -> Sta6
        # Evt14: Receive A-RELEASE (rsp) primitive from <local user>
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(['skip', a_associate_ac])
        scp.queue.put(['wait', 0.3])
        scp.queue.put(['skip', a_abort])
        scp.queue.put('shutdown')
        scp.start()

        self.assoc.start()

        time.sleep(0.2)

        self.assoc.dul.send_pdu(self.get_release(True))

        time.sleep(0.2)

        assert self.fsm._changes[:3] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt3', 'AE-3'),
        ]
        assert self.fsm._transitions[:3] == ['Sta4', 'Sta5', 'Sta6']
        assert self.fsm._events[:4] == ['Evt1', 'Evt2', 'Evt3', 'Evt14']

    def test_evt15(self):
        """Test Sta6 + Evt15."""
        # Sta6 + Evt15 -> AA-1 -> Sta13
        # Evt15: Receive A-ABORT (rq) primitive from <local user>
        # AA-1: Send A-ABORT PDU and start ARTIM
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(['skip', a_associate_ac])
        scp.queue.put(None)
        scp.queue.put('shutdown')
        scp.start()

        self.assoc.start()

        time.sleep(0.2)

        self.assoc.abort()

        time.sleep(0.2)

        assert self.fsm._changes[:3] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt3', 'AE-3'),
        ]
        assert self.fsm._transitions[:3] == ['Sta4', 'Sta5', 'Sta6']
        assert self.fsm._events[:4] == ['Evt1', 'Evt2', 'Evt3', 'Evt15']

        # Issue A-ABORT PDU
        assert scp.received[1] == b'\x07\x00\x00\x00\x00\x04\x00\x00\x00\x00'

    def test_evt16(self):
        """Test Sta6 + Evt16."""
        # Sta6 + Evt16 -> AA-3 -> Sta1
        # Evt16: Receive A-ABORT PDU from <remote>
        # AA-3: Issue A-ABORT or A-P-ABORT, and close connection
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(['skip', a_associate_ac])
        scp.queue.put(['skip', a_abort])
        scp.queue.put('shutdown')
        scp.start()

        self.assoc.start()

        time.sleep(0.2)

        assert self.fsm._changes[:4] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt3', 'AE-3'),
            ('Sta6', 'Evt16', 'AA-3'),
        ]
        assert self.fsm._transitions[:4] == ['Sta4', 'Sta5', 'Sta6', 'Sta1']
        assert self.fsm._events[:4] == ['Evt1', 'Evt2', 'Evt3', 'Evt16']

    def test_evt17(self):
        """Test Sta6 + Evt17."""
        # Sta6 + Evt17 -> AA-4 -> Sta1
        # Evt17: Receive TRANSPORT_CLOSED from <transport service>
        # AA-4: Issue A-P-ABORT primitive
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(['skip', a_associate_ac])
        scp.queue.put('shutdown')
        scp.start()

        self.assoc.start()

        time.sleep(0.2)

        assert self.fsm._changes[:4] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt3', 'AE-3'),
            ('Sta6', 'Evt17', 'AA-4'),
        ]
        assert self.fsm._transitions[:4] == ['Sta4', 'Sta5', 'Sta6', 'Sta1']
        assert self.fsm._events[:4] == ['Evt1', 'Evt2', 'Evt3', 'Evt17']

    @pytest.mark.skip
    def test_evt18(self):
        """Test Sta6 + Evt18."""
        # Sta6 + Evt18 -> <ignore> -> Sta6
        # Evt18: ARTIM timer expired from <local service>
        pass

    def test_evt19(self):
        """Test Sta6 + Evt19."""
        # Sta6 + Evt19 -> AA-8 -> Sta13
        # Evt19: Received unrecognised or invalid PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(['skip', a_associate_ac])
        scp.queue.put(b'\x08\x00\x00\x00\x00')
        scp.queue.put('shutdown')
        scp.start()

        self.assoc.start()

        time.sleep(0.2)

        assert self.fsm._changes[:4] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt3', 'AE-3'),
            ('Sta6', 'Evt19', 'AA-8'),
        ]
        assert self.fsm._transitions[:4] == ['Sta4', 'Sta5', 'Sta6', 'Sta13']
        assert self.fsm._events[:4] == ['Evt1', 'Evt2', 'Evt3', 'Evt19']

        # Issue A-ABORT PDU
        assert scp.received[1] == b'\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00'


class TestState07(TestStateBase):
    """Tests for State 07: Awaiting A-RELEASE-RP PDU."""
    def test_evt01(self):
        """Test Sta7 + Evt1."""
        # Sta7 + Evt1 -> <ignore> -> Sta7
        # Evt1: A-ASSOCIATE (rq) primitive from <local user>
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(['skip', a_associate_ac])
        scp.queue.put(None)
        scp.queue.put(['wait', 0.2, 'shutdown'])
        scp.start()

        self.assoc.start()

        time.sleep(0.2)

        self.assoc.dul.send_pdu(self.get_release(False))

        time.sleep(0.1)

        self.assoc.dul.send_pdu(self.get_associate('request'))

        time.sleep(0.1)

        assert self.fsm._changes[:4] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt3', 'AE-3'),
            ('Sta6', 'Evt11', 'AR-1'),
        ]
        assert self.fsm._transitions[:4] == ['Sta4', 'Sta5', 'Sta6', 'Sta7']
        assert self.fsm._events[:5] == ['Evt1', 'Evt2', 'Evt3', 'Evt11', 'Evt1']

    @pytest.mark.skip()
    def test_evt02(self):
        """Test Sta7 + Evt2."""
        # Sta7 + Evt2 -> <ignore> -> Sta7
        # Evt2: Receive TRANSPORT_OPEN from <transport service>
        pass

    def test_evt03(self):
        """Test Sta7 + Evt3."""
        # Sta7 + Evt3 -> AA-8 -> Sta13
        # Evt3: Receive A-ASSOCIATE-AC PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(['skip', a_associate_ac])
        scp.queue.put(None)
        scp.queue.put(a_associate_ac)
        scp.queue.put(['wait', 0.2, 'shutdown'])
        scp.start()

        self.assoc.start()

        time.sleep(0.2)

        self.assoc.dul.send_pdu(self.get_release(False))

        time.sleep(0.3)

        assert self.fsm._changes[:5] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt3', 'AE-3'),
            ('Sta6', 'Evt11', 'AR-1'),
            ('Sta7', 'Evt3', 'AA-8'),
        ]
        assert self.fsm._transitions[:4] == ['Sta4', 'Sta5', 'Sta6', 'Sta7']
        assert self.fsm._events[:5] == ['Evt1', 'Evt2', 'Evt3', 'Evt11', 'Evt3']

        # Issue A-ASSOCIATE, A-RELEASE, A-ABORT PDU
        assert scp.received[2] == b'\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00'

    def test_evt04(self):
        """Test Sta7 + Evt4."""
        # Sta7 + Evt4 -> AA-8 -> Sta13
        # Evt4: Receive A-ASSOCIATE-RJ PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(['skip', a_associate_ac])
        scp.queue.put(None)
        scp.queue.put(a_associate_rj)
        scp.queue.put(['wait', 0.2, 'shutdown'])
        scp.start()

        self.assoc.start()

        time.sleep(0.2)

        self.assoc.dul.send_pdu(self.get_release(False))

        time.sleep(0.3)

        assert self.fsm._changes[:5] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt3', 'AE-3'),
            ('Sta6', 'Evt11', 'AR-1'),
            ('Sta7', 'Evt4', 'AA-8'),
        ]
        assert self.fsm._transitions[:4] == ['Sta4', 'Sta5', 'Sta6', 'Sta7']
        assert self.fsm._events[:5] == ['Evt1', 'Evt2', 'Evt3', 'Evt11', 'Evt4']

        # Issue A-ASSOCIATE, A-RELEASE, A-ABORT PDU
        assert scp.received[2] == b'\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00'

    @pytest.mark.skip()
    def test_evt05(self):
        """Test Sta7 + Evt5."""
        # Sta7 + Evt5 -> <ignore> -> Sta7
        # Evt5: Receive TRANSPORT_INDICATION from <transport service>
        pass

    def test_evt06(self):
        """Test Sta7 + Evt6."""
        # Sta7 + Evt6 -> AA-8 -> Sta13
        # Evt6: Receive A-ASSOCIATE-RQ PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(['skip', a_associate_ac])
        scp.queue.put(None)
        scp.queue.put(a_associate_rq)
        scp.queue.put(['wait', 0.2, 'shutdown'])
        scp.start()

        self.assoc.start()

        time.sleep(0.2)

        self.assoc.dul.send_pdu(self.get_release(False))

        time.sleep(0.3)

        assert self.fsm._changes[:5] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt3', 'AE-3'),
            ('Sta6', 'Evt11', 'AR-1'),
            ('Sta7', 'Evt6', 'AA-8'),
        ]
        assert self.fsm._transitions[:4] == ['Sta4', 'Sta5', 'Sta6', 'Sta7']
        assert self.fsm._events[:5] == ['Evt1', 'Evt2', 'Evt3', 'Evt11', 'Evt6']

        # Issue A-ASSOCIATE, A-RELEASE, A-ABORT PDU
        assert scp.received[2] == b'\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00'

    def test_evt07(self):
        """Test Sta7 + Evt7."""
        # Sta7 + Evt7 -> <ignore> -> Sta7
        # Evt7: Receive A-ASSOCIATE (accept) primitive from <local user>
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(['skip', a_associate_ac])
        scp.queue.put(None)
        scp.queue.put(['wait', 0.2, 'shutdown'])
        scp.start()

        self.assoc.start()

        time.sleep(0.2)

        self.assoc.dul.send_pdu(self.get_release(False))

        time.sleep(0.1)

        self.assoc.dul.send_pdu(self.get_associate('accept'))

        time.sleep(0.1)

        assert self.fsm._changes[:4] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt3', 'AE-3'),
            ('Sta6', 'Evt11', 'AR-1'),
        ]
        assert self.fsm._transitions[:4] == ['Sta4', 'Sta5', 'Sta6', 'Sta7']
        assert self.fsm._events[:5] == ['Evt1', 'Evt2', 'Evt3', 'Evt11', 'Evt7']

    def test_evt08(self):
        """Test Sta7 + Evt8."""
        # Sta7 + Evt8 -> <ignore> -> Sta7
        # Evt8: Receive A-ASSOCIATE (reject) primitive from <local user>
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(['skip', a_associate_ac])
        scp.queue.put(None)
        scp.queue.put(['wait', 0.2, 'shutdown'])
        scp.start()

        self.assoc.start()

        time.sleep(0.2)

        self.assoc.dul.send_pdu(self.get_release(False))

        time.sleep(0.1)

        self.assoc.dul.send_pdu(self.get_associate('reject'))

        time.sleep(0.1)

        assert self.fsm._changes[:4] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt3', 'AE-3'),
            ('Sta6', 'Evt11', 'AR-1'),
        ]
        assert self.fsm._transitions[:4] == ['Sta4', 'Sta5', 'Sta6', 'Sta7']
        assert self.fsm._events[:5] == ['Evt1', 'Evt2', 'Evt3', 'Evt11', 'Evt8']

    def test_evt09(self):
        """Test Sta7 + Evt9."""
        # Sta7 + Evt9 -> <ignore> -> Sta7
        # Evt9: Receive P-DATA primitive from <local user>
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(['skip', a_associate_ac])
        scp.queue.put(None)
        scp.queue.put(['wait', 0.2, 'shutdown'])
        scp.start()

        self.assoc.start()

        time.sleep(0.2)

        self.assoc.dul.send_pdu(self.get_release(False))

        time.sleep(0.1)

        self.assoc.dul.send_pdu(self.get_pdata())

        time.sleep(0.1)

        assert self.fsm._changes[:4] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt3', 'AE-3'),
            ('Sta6', 'Evt11', 'AR-1'),
        ]
        assert self.fsm._transitions[:4] == ['Sta4', 'Sta5', 'Sta6', 'Sta7']
        assert self.fsm._events[:5] == ['Evt1', 'Evt2', 'Evt3', 'Evt11', 'Evt9']

    def test_evt10(self):
        """Test Sta7 + Evt10."""
        # Sta7 + Evt10 -> AR-6 -> Sta7
        # Evt10: Receive P-DATA-TF PDU from <remote>
        # AR-6: Send P-DATA primitive
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(['skip', a_associate_ac])
        scp.queue.put(None)
        scp.queue.put(['skip', p_data_tf])
        scp.queue.put(['skip', a_abort])
        scp.queue.put(['wait', 0.2, 'shutdown'])
        scp.start()

        self.assoc.start()

        time.sleep(0.2)

        self.assoc.dul.send_pdu(self.get_release(False))

        time.sleep(0.2)

        primitive = self.assoc.dul.receive_pdu(wait=False)
        assert isinstance(primitive, P_DATA)
        assert self.fsm._changes[:5] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt3', 'AE-3'),
            ('Sta6', 'Evt11', 'AR-1'),
            ('Sta7', 'Evt10', 'AR-6'),
        ]
        assert self.fsm._transitions[:4] == ['Sta4', 'Sta5', 'Sta6', 'Sta7']
        assert self.fsm._events[:5] == ['Evt1', 'Evt2', 'Evt3', 'Evt11', 'Evt10']

    def test_evt11(self):
        """Test Sta7 + Evt11."""
        # Sta7 + Evt11 -> <ignore> -> Sta7
        # Evt11: Receive A-RELEASE (rq) primitive from <local user>
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(['skip', a_associate_ac])
        scp.queue.put(None)
        scp.queue.put(['wait', 0.2, 'shutdown'])
        scp.start()

        self.assoc.start()

        time.sleep(0.2)

        self.assoc.dul.send_pdu(self.get_release(False))

        time.sleep(0.1)

        self.assoc.dul.send_pdu(self.get_release(False))

        time.sleep(0.1)

        assert self.fsm._changes[:4] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt3', 'AE-3'),
            ('Sta6', 'Evt11', 'AR-1'),
        ]
        assert self.fsm._transitions[:4] == ['Sta4', 'Sta5', 'Sta6', 'Sta7']
        assert self.fsm._events[:5] == ['Evt1', 'Evt2', 'Evt3', 'Evt11', 'Evt11']

    def test_evt12(self):
        """Test Sta7 + Evt12."""
        # Sta7 + Evt12 -> AR-8 -> Sta9 or Sta10
        # Evt12: Receive A-RELEASE-RQ PDU from <remote>
        # AR-8: Issue A-RELEASE (rq) - release collision
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(['skip', a_associate_ac])
        scp.queue.put(None)
        scp.queue.put(a_release_rq)
        scp.queue.put(['wait', 0.2, 'shutdown'])
        scp.start()

        self.assoc.start()

        time.sleep(0.2)

        self.assoc.dul.send_pdu(self.get_release(False))

        time.sleep(0.3)

        assert self.fsm._changes[:5] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt3', 'AE-3'),
            ('Sta6', 'Evt11', 'AR-1'),
            ('Sta7', 'Evt12', 'AR-8'),
        ]
        assert self.fsm._transitions[:4] == ['Sta4', 'Sta5', 'Sta6', 'Sta7']
        assert self.fsm._events[:5] == ['Evt1', 'Evt2', 'Evt3', 'Evt11', 'Evt12']

    def test_evt13(self):
        """Test Sta7 + Evt13."""
        # Sta7 + Evt13 -> AR-3 -> Sta1
        # Evt13: Receive A-RELEASE-RP PDU from <remote>
        # AR-3: Issue A-RELEASE (rp) primitive and close connection
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(['skip', a_associate_ac])
        scp.queue.put(None)
        scp.queue.put([a_release_rp, 'shutdown'])
        scp.queue.put(['wait', 0.2, 'shutdown'])
        scp.start()

        self.assoc.start()

        time.sleep(0.2)

        self.assoc.dul.send_pdu(self.get_release(False))

        time.sleep(0.2)

        primitive = self.assoc.dul.receive_pdu(wait=False)
        assert isinstance(primitive, A_RELEASE)
        assert self.fsm._changes[:5] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt3', 'AE-3'),
            ('Sta6', 'Evt11', 'AR-1'),
            ('Sta7', 'Evt13', 'AR-3'),
        ]
        assert self.fsm._transitions[:4] == ['Sta4', 'Sta5', 'Sta6', 'Sta7']
        assert self.fsm._events[:5] == ['Evt1', 'Evt2', 'Evt3', 'Evt11', 'Evt13']

    def test_evt14(self):
        """Test Sta7 + Evt14."""
        # Sta7 + Evt14 -> <ignore> -> Sta7
        # Evt14: Receive A-RELEASE (rsp) primitive from <local user>
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(['skip', a_associate_ac])
        scp.queue.put(None)
        scp.queue.put(['wait', 0.2, 'shutdown'])
        scp.start()

        self.assoc.start()

        time.sleep(0.2)

        self.assoc.dul.send_pdu(self.get_release(False))

        time.sleep(0.1)

        self.assoc.dul.send_pdu(self.get_release(True))

        time.sleep(0.1)

        assert self.fsm._changes[:4] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt3', 'AE-3'),
            ('Sta6', 'Evt11', 'AR-1'),
        ]
        assert self.fsm._transitions[:4] == ['Sta4', 'Sta5', 'Sta6', 'Sta7']
        assert self.fsm._events[:5] == ['Evt1', 'Evt2', 'Evt3', 'Evt11', 'Evt14']

    def test_evt15(self):
        """Test Sta7 + Evt15."""
        # Sta7 + Evt15 -> AA-1 -> Sta13
        # Evt15: Receive A-ABORT (rq) primitive from <local user>
        # AA-1: Send A-ABORT PDU and start ARTIM
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(['skip', a_associate_ac])
        scp.queue.put(None) # release
        scp.queue.put(None) # abort
        scp.queue.put(['wait', 0.2,'shutdown'])
        scp.start()

        self.assoc.start()

        time.sleep(0.2)

        self.assoc.dul.send_pdu(self.get_release(False))

        time.sleep(0.1)

        self.assoc.dul.send_pdu(self.get_abort())

        time.sleep(0.2)

        assert self.fsm._changes[:4] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt3', 'AE-3'),
            ('Sta6', 'Evt11', 'AR-1'),
        ]
        assert self.fsm._transitions[:4] == ['Sta4', 'Sta5', 'Sta6', 'Sta7']
        assert self.fsm._events[:5] == ['Evt1', 'Evt2', 'Evt3', 'Evt11', 'Evt15']

    def test_evt16(self):
        """Test Sta7 + Evt16."""
        # Sta7 + Evt16 -> AA-3 -> Sta1
        # Evt16: Receive A-ABORT PDU from <remote>
        # AA-3: Issue A-ABORT or A-P-ABORT and close connection
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(['skip', a_associate_ac])
        scp.queue.put(None) # release
        scp.queue.put([a_abort, 'shutdown'])
        scp.queue.put(['wait', 0.2, 'shutdown'])
        scp.start()

        self.assoc.start()

        time.sleep(0.2)

        self.assoc.dul.send_pdu(self.get_release(False))

        time.sleep(0.1)

        assert self.fsm._changes[:5] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt3', 'AE-3'),
            ('Sta6', 'Evt11', 'AR-1'),
            ('Sta7', 'Evt16', 'AA-3'),
        ]
        assert self.fsm._transitions[:4] == ['Sta4', 'Sta5', 'Sta6', 'Sta7']
        assert self.fsm._events[:5] == ['Evt1', 'Evt2', 'Evt3', 'Evt11', 'Evt16']

    def test_evt17(self):
        """Test Sta7 + Evt17."""
        # Sta7 + Evt17 -> AA-4 -> Sta1
        # Evt17: Receive TRANSPORT_CLOSED from <transport service>
        # AA-4: Issue A-P-ABORT primitive
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(['skip', a_associate_ac])
        scp.queue.put(None)
        scp.queue.put('shutdown')
        scp.start()

        self.assoc.start()

        time.sleep(0.2)

        self.assoc.dul.send_pdu(self.get_release(False))

        time.sleep(0.1)

        assert self.fsm._changes[:5] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt3', 'AE-3'),
            ('Sta6', 'Evt11', 'AR-1'),
            ('Sta7', 'Evt17', 'AA-4'),
        ]
        assert self.fsm._transitions[:4] == ['Sta4', 'Sta5', 'Sta6', 'Sta7']
        assert self.fsm._events[:5] == ['Evt1', 'Evt2', 'Evt3', 'Evt11', 'Evt17']

    @pytest.mark.skip()
    def test_evt18(self):
        """Test Sta7 + Evt18."""
        # Sta7 + Evt18 -> <ignore> -> Sta7
        # Evt18: ARTIM timer expired from <local service>
        pass

    def test_evt19(self):
        """Test Sta7 + Evt19."""
        # Sta7 + Evt19 -> AA-8 -> Sta13
        # Evt19: Received unrecognised or invalid PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        scp = DummyAE()
        scp.mode = 'acceptor'
        scp.queue.put(None)
        scp.queue.put(['skip', a_associate_ac])
        scp.queue.put(None)
        scp.queue.put(b'\x08\x00\x00\x00')
        scp.queue.put(['wait', 0.2, 'shutdown'])
        scp.start()

        self.assoc.start()

        time.sleep(0.2)

        self.assoc.dul.send_pdu(self.get_release(False))

        time.sleep(0.1)

        assert self.fsm._changes[:5] == [
            ('Sta1', 'Evt1', 'AE-1'),
            ('Sta4', 'Evt2', 'AE-2'),
            ('Sta5', 'Evt3', 'AE-3'),
            ('Sta6', 'Evt11', 'AR-1'),
            ('Sta7', 'Evt19', 'AA-8'),
        ]
        assert self.fsm._transitions[:4] == ['Sta4', 'Sta5', 'Sta6', 'Sta7']
        assert self.fsm._events[:5] == ['Evt1', 'Evt2', 'Evt3', 'Evt11', 'Evt19']

        # Issue A-ASSOCIATE, A-RELEASE, A-ABORT PDU
        assert scp.received[2] == b'\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00'


@pytest.mark.skip()
class TestState08(TestStateBase):
    """Tests for State 08: """
    def test_evt01(self):
        """Test Sta2 + Evt1."""
        # Sta2 + Evt1 -> <ignore> -> Sta2
        # Evt1: A-ASSOCIATE (rq) primitive from <local user>
        pass

    def test_evt02(self):
        """Test Sta2 + Evt2."""
        # Sta2 + Evt2 -> <ignore> -> Sta2
        # Evt2: Receive TRANSPORT_OPEN from <transport service>
        pass

    def test_evt03(self):
        """Test Sta2 + Evt3."""
        # Sta2 + Evt3 -> AA-1 -> Sta13
        # Evt3: Receive A-ASSOCIATE-AC PDU from <remote>
        pass

    def test_evt04(self):
        """Test Sta2 + Evt4."""
        # Sta2 + Evt4 -> AA-1 -> Sta13
        # Evt4: Receive A-ASSOCIATE-RJ PDU from <remote>
        pass

    def test_evt05(self):
        """Test Sta2 + Evt5."""
        # Sta2 + Evt5 -> <ignore> -> Sta2
        # Evt5: Receive TRANSPORT_INDICATION from <transport service>
        pass

    def test_evt06(self):
        """Test Sta2 + Evt6."""
        # Sta2 + Evt6 -> AE-6 -> Sta3 or Sta13
        # Evt6: Receive A-ASSOCIATE-RQ PDU from <remote>
        pass

    def test_evt07(self):
        """Test Sta2 + Evt7."""
        # Sta2 + Evt7 -> <ignore> -> Sta2
        # Evt7: Receive A-ASSOCIATE (accept) primitive from <local user>
        pass

    def test_evt08(self):
        """Test Sta2 + Evt8."""
        # Sta2 + Evt8 -> <ignore> -> Sta2
        # Evt8: Receive A-ASSOCIATE (reject) primitive from <local user>
        pass

    def test_evt09(self):
        """Test Sta2 + Evt9."""
        # Sta2 + Evt9 -> <ignore> -> Sta2
        # Evt9: Receive P-DATA primitive from <local user>
        pass

    def test_evt10(self):
        """Test Sta2 + Evt10."""
        # Sta2 + Evt10 -> AA-1 -> Sta13
        # Evt10: Receive P-DATA-TF PDU from <remote>
        pass

    def test_evt11(self):
        """Test Sta2 + Evt11."""
        # Sta2 + Evt11 -> <ignore> -> Sta2
        # Evt11: Receive A-RELEASE (rq) primitive from <local user>
        pass

    def test_evt12(self):
        """Test Sta2 + Evt12."""
        # Sta2 + Evt12 -> AA-1 -> Sta13
        # Evt12: Receive A-RELEASE-RQ PDU from <remote>
        pass

    def test_evt13(self):
        """Test Sta2 + Evt13."""
        # Sta2 + Evt13 -> AA-1 -> Sta13
        # Evt13: Receive A-RELEASE-RP PDU from <remote>
        pass

    def test_evt14(self):
        """Test Sta2 + Evt14."""
        # Sta2 + Evt14 -> <ignore> -> Sta2
        # Evt14: Receive A-RELEASE (rsp) primitive from <local user>
        pass

    def test_evt15(self):
        """Test Sta2 + Evt15."""
        # Sta2 + Evt15 -> <ignore> -> Sta2
        # Evt15: Receive A-ABORT (rq) primitive from <local user>
        pass

    def test_evt16(self):
        """Test Sta2 + Evt16."""
        # Sta2 + Evt16 -> AA-2 -> Sta1
        # Evt16: Receive A-ABORT PDU from <remote>
        pass

    def test_evt17(self):
        """Test Sta2 + Evt17."""
        # Sta2 + Evt17 -> AA-5 -> Sta1
        # Evt17: Receive TRANSPORT_CLOSED from <transport service>
        pass

    def test_evt18(self):
        """Test Sta2 + Evt18."""
        # Sta2 + Evt18 -> AA-2 -> Sta1
        # Evt18: ARTIM timer expired from <local service>
        pass

    def test_evt19(self):
        """Test Sta2 + Evt19."""
        # Sta2 + Evt19 -> AA-1 -> Sta13
        # Evt19: Received unrecognised or invalid PDU from <remote>
        pass


@pytest.mark.skip()
class TestState09(TestStateBase):
    """Tests for State 09: """
    def test_evt01(self):
        """Test Sta2 + Evt1."""
        # Sta2 + Evt1 -> <ignore> -> Sta2
        # Evt1: A-ASSOCIATE (rq) primitive from <local user>
        pass

    def test_evt02(self):
        """Test Sta2 + Evt2."""
        # Sta2 + Evt2 -> <ignore> -> Sta2
        # Evt2: Receive TRANSPORT_OPEN from <transport service>
        pass

    def test_evt03(self):
        """Test Sta2 + Evt3."""
        # Sta2 + Evt3 -> AA-1 -> Sta13
        # Evt3: Receive A-ASSOCIATE-AC PDU from <remote>
        pass

    def test_evt04(self):
        """Test Sta2 + Evt4."""
        # Sta2 + Evt4 -> AA-1 -> Sta13
        # Evt4: Receive A-ASSOCIATE-RJ PDU from <remote>
        pass

    def test_evt05(self):
        """Test Sta2 + Evt5."""
        # Sta2 + Evt5 -> <ignore> -> Sta2
        # Evt5: Receive TRANSPORT_INDICATION from <transport service>
        pass

    def test_evt06(self):
        """Test Sta2 + Evt6."""
        # Sta2 + Evt6 -> AE-6 -> Sta3 or Sta13
        # Evt6: Receive A-ASSOCIATE-RQ PDU from <remote>
        pass

    def test_evt07(self):
        """Test Sta2 + Evt7."""
        # Sta2 + Evt7 -> <ignore> -> Sta2
        # Evt7: Receive A-ASSOCIATE (accept) primitive from <local user>
        pass

    def test_evt08(self):
        """Test Sta2 + Evt8."""
        # Sta2 + Evt8 -> <ignore> -> Sta2
        # Evt8: Receive A-ASSOCIATE (reject) primitive from <local user>
        pass

    def test_evt09(self):
        """Test Sta2 + Evt9."""
        # Sta2 + Evt9 -> <ignore> -> Sta2
        # Evt9: Receive P-DATA primitive from <local user>
        pass

    def test_evt10(self):
        """Test Sta2 + Evt10."""
        # Sta2 + Evt10 -> AA-1 -> Sta13
        # Evt10: Receive P-DATA-TF PDU from <remote>
        pass

    def test_evt11(self):
        """Test Sta2 + Evt11."""
        # Sta2 + Evt11 -> <ignore> -> Sta2
        # Evt11: Receive A-RELEASE (rq) primitive from <local user>
        pass

    def test_evt12(self):
        """Test Sta2 + Evt12."""
        # Sta2 + Evt12 -> AA-1 -> Sta13
        # Evt12: Receive A-RELEASE-RQ PDU from <remote>
        pass

    def test_evt13(self):
        """Test Sta2 + Evt13."""
        # Sta2 + Evt13 -> AA-1 -> Sta13
        # Evt13: Receive A-RELEASE-RP PDU from <remote>
        pass

    def test_evt14(self):
        """Test Sta2 + Evt14."""
        # Sta2 + Evt14 -> <ignore> -> Sta2
        # Evt14: Receive A-RELEASE (rsp) primitive from <local user>
        pass

    def test_evt15(self):
        """Test Sta2 + Evt15."""
        # Sta2 + Evt15 -> <ignore> -> Sta2
        # Evt15: Receive A-ABORT (rq) primitive from <local user>
        pass

    def test_evt16(self):
        """Test Sta2 + Evt16."""
        # Sta2 + Evt16 -> AA-2 -> Sta1
        # Evt16: Receive A-ABORT PDU from <remote>
        pass

    def test_evt17(self):
        """Test Sta2 + Evt17."""
        # Sta2 + Evt17 -> AA-5 -> Sta1
        # Evt17: Receive TRANSPORT_CLOSED from <transport service>
        pass

    def test_evt18(self):
        """Test Sta2 + Evt18."""
        # Sta2 + Evt18 -> AA-2 -> Sta1
        # Evt18: ARTIM timer expired from <local service>
        pass

    def test_evt19(self):
        """Test Sta2 + Evt19."""
        # Sta2 + Evt19 -> AA-1 -> Sta13
        # Evt19: Received unrecognised or invalid PDU from <remote>
        pass


@pytest.mark.skip()
class TestState10(TestStateBase):
    """Tests for State 10: ."""
    def test_evt01(self):
        """Test Sta2 + Evt1."""
        # Sta2 + Evt1 -> <ignore> -> Sta2
        # Evt1: A-ASSOCIATE (rq) primitive from <local user>
        pass

    def test_evt02(self):
        """Test Sta2 + Evt2."""
        # Sta2 + Evt2 -> <ignore> -> Sta2
        # Evt2: Receive TRANSPORT_OPEN from <transport service>
        pass

    def test_evt03(self):
        """Test Sta2 + Evt3."""
        # Sta2 + Evt3 -> AA-1 -> Sta13
        # Evt3: Receive A-ASSOCIATE-AC PDU from <remote>
        pass

    def test_evt04(self):
        """Test Sta2 + Evt4."""
        # Sta2 + Evt4 -> AA-1 -> Sta13
        # Evt4: Receive A-ASSOCIATE-RJ PDU from <remote>
        pass

    def test_evt05(self):
        """Test Sta2 + Evt5."""
        # Sta2 + Evt5 -> <ignore> -> Sta2
        # Evt5: Receive TRANSPORT_INDICATION from <transport service>
        pass

    def test_evt06(self):
        """Test Sta2 + Evt6."""
        # Sta2 + Evt6 -> AE-6 -> Sta3 or Sta13
        # Evt6: Receive A-ASSOCIATE-RQ PDU from <remote>
        pass

    def test_evt07(self):
        """Test Sta2 + Evt7."""
        # Sta2 + Evt7 -> <ignore> -> Sta2
        # Evt7: Receive A-ASSOCIATE (accept) primitive from <local user>
        pass

    def test_evt08(self):
        """Test Sta2 + Evt8."""
        # Sta2 + Evt8 -> <ignore> -> Sta2
        # Evt8: Receive A-ASSOCIATE (reject) primitive from <local user>
        pass

    def test_evt09(self):
        """Test Sta2 + Evt9."""
        # Sta2 + Evt9 -> <ignore> -> Sta2
        # Evt9: Receive P-DATA primitive from <local user>
        pass

    def test_evt10(self):
        """Test Sta2 + Evt10."""
        # Sta2 + Evt10 -> AA-1 -> Sta13
        # Evt10: Receive P-DATA-TF PDU from <remote>
        pass

    def test_evt11(self):
        """Test Sta2 + Evt11."""
        # Sta2 + Evt11 -> <ignore> -> Sta2
        # Evt11: Receive A-RELEASE (rq) primitive from <local user>
        pass

    def test_evt12(self):
        """Test Sta2 + Evt12."""
        # Sta2 + Evt12 -> AA-1 -> Sta13
        # Evt12: Receive A-RELEASE-RQ PDU from <remote>
        pass

    def test_evt13(self):
        """Test Sta2 + Evt13."""
        # Sta2 + Evt13 -> AA-1 -> Sta13
        # Evt13: Receive A-RELEASE-RP PDU from <remote>
        pass

    def test_evt14(self):
        """Test Sta2 + Evt14."""
        # Sta2 + Evt14 -> <ignore> -> Sta2
        # Evt14: Receive A-RELEASE (rsp) primitive from <local user>
        pass

    def test_evt15(self):
        """Test Sta2 + Evt15."""
        # Sta2 + Evt15 -> <ignore> -> Sta2
        # Evt15: Receive A-ABORT (rq) primitive from <local user>
        pass

    def test_evt16(self):
        """Test Sta2 + Evt16."""
        # Sta2 + Evt16 -> AA-2 -> Sta1
        # Evt16: Receive A-ABORT PDU from <remote>
        pass

    def test_evt17(self):
        """Test Sta2 + Evt17."""
        # Sta2 + Evt17 -> AA-5 -> Sta1
        # Evt17: Receive TRANSPORT_CLOSED from <transport service>
        pass

    def test_evt18(self):
        """Test Sta2 + Evt18."""
        # Sta2 + Evt18 -> AA-2 -> Sta1
        # Evt18: ARTIM timer expired from <local service>
        pass

    def test_evt19(self):
        """Test Sta2 + Evt19."""
        # Sta2 + Evt19 -> AA-1 -> Sta13
        # Evt19: Received unrecognised or invalid PDU from <remote>
        pass


@pytest.mark.skip()
class TestState11(TestStateBase):
    """Tests for State 11: ."""
    def test_evt01(self):
        """Test Sta2 + Evt1."""
        # Sta2 + Evt1 -> <ignore> -> Sta2
        # Evt1: A-ASSOCIATE (rq) primitive from <local user>
        pass

    def test_evt02(self):
        """Test Sta2 + Evt2."""
        # Sta2 + Evt2 -> <ignore> -> Sta2
        # Evt2: Receive TRANSPORT_OPEN from <transport service>
        pass

    def test_evt03(self):
        """Test Sta2 + Evt3."""
        # Sta2 + Evt3 -> AA-1 -> Sta13
        # Evt3: Receive A-ASSOCIATE-AC PDU from <remote>
        pass

    def test_evt04(self):
        """Test Sta2 + Evt4."""
        # Sta2 + Evt4 -> AA-1 -> Sta13
        # Evt4: Receive A-ASSOCIATE-RJ PDU from <remote>
        pass

    def test_evt05(self):
        """Test Sta2 + Evt5."""
        # Sta2 + Evt5 -> <ignore> -> Sta2
        # Evt5: Receive TRANSPORT_INDICATION from <transport service>
        pass

    def test_evt06(self):
        """Test Sta2 + Evt6."""
        # Sta2 + Evt6 -> AE-6 -> Sta3 or Sta13
        # Evt6: Receive A-ASSOCIATE-RQ PDU from <remote>
        pass

    def test_evt07(self):
        """Test Sta2 + Evt7."""
        # Sta2 + Evt7 -> <ignore> -> Sta2
        # Evt7: Receive A-ASSOCIATE (accept) primitive from <local user>
        pass

    def test_evt08(self):
        """Test Sta2 + Evt8."""
        # Sta2 + Evt8 -> <ignore> -> Sta2
        # Evt8: Receive A-ASSOCIATE (reject) primitive from <local user>
        pass

    def test_evt09(self):
        """Test Sta2 + Evt9."""
        # Sta2 + Evt9 -> <ignore> -> Sta2
        # Evt9: Receive P-DATA primitive from <local user>
        pass

    def test_evt10(self):
        """Test Sta2 + Evt10."""
        # Sta2 + Evt10 -> AA-1 -> Sta13
        # Evt10: Receive P-DATA-TF PDU from <remote>
        pass

    def test_evt11(self):
        """Test Sta2 + Evt11."""
        # Sta2 + Evt11 -> <ignore> -> Sta2
        # Evt11: Receive A-RELEASE (rq) primitive from <local user>
        pass

    def test_evt12(self):
        """Test Sta2 + Evt12."""
        # Sta2 + Evt12 -> AA-1 -> Sta13
        # Evt12: Receive A-RELEASE-RQ PDU from <remote>
        pass

    def test_evt13(self):
        """Test Sta2 + Evt13."""
        # Sta2 + Evt13 -> AA-1 -> Sta13
        # Evt13: Receive A-RELEASE-RP PDU from <remote>
        pass

    def test_evt14(self):
        """Test Sta2 + Evt14."""
        # Sta2 + Evt14 -> <ignore> -> Sta2
        # Evt14: Receive A-RELEASE (rsp) primitive from <local user>
        pass

    def test_evt15(self):
        """Test Sta2 + Evt15."""
        # Sta2 + Evt15 -> <ignore> -> Sta2
        # Evt15: Receive A-ABORT (rq) primitive from <local user>
        pass

    def test_evt16(self):
        """Test Sta2 + Evt16."""
        # Sta2 + Evt16 -> AA-2 -> Sta1
        # Evt16: Receive A-ABORT PDU from <remote>
        pass

    def test_evt17(self):
        """Test Sta2 + Evt17."""
        # Sta2 + Evt17 -> AA-5 -> Sta1
        # Evt17: Receive TRANSPORT_CLOSED from <transport service>
        pass

    def test_evt18(self):
        """Test Sta2 + Evt18."""
        # Sta2 + Evt18 -> AA-2 -> Sta1
        # Evt18: ARTIM timer expired from <local service>
        pass

    def test_evt19(self):
        """Test Sta2 + Evt19."""
        # Sta2 + Evt19 -> AA-1 -> Sta13
        # Evt19: Received unrecognised or invalid PDU from <remote>
        pass


@pytest.mark.skip()
class TestState12(TestStateBase):
    """Tests for State 12: """
    def test_evt01(self):
        """Test Sta2 + Evt1."""
        # Sta2 + Evt1 -> <ignore> -> Sta2
        # Evt1: A-ASSOCIATE (rq) primitive from <local user>
        pass

    def test_evt02(self):
        """Test Sta2 + Evt2."""
        # Sta2 + Evt2 -> <ignore> -> Sta2
        # Evt2: Receive TRANSPORT_OPEN from <transport service>
        pass

    def test_evt03(self):
        """Test Sta2 + Evt3."""
        # Sta2 + Evt3 -> AA-1 -> Sta13
        # Evt3: Receive A-ASSOCIATE-AC PDU from <remote>
        pass

    def test_evt04(self):
        """Test Sta2 + Evt4."""
        # Sta2 + Evt4 -> AA-1 -> Sta13
        # Evt4: Receive A-ASSOCIATE-RJ PDU from <remote>
        pass

    def test_evt05(self):
        """Test Sta2 + Evt5."""
        # Sta2 + Evt5 -> <ignore> -> Sta2
        # Evt5: Receive TRANSPORT_INDICATION from <transport service>
        pass

    def test_evt06(self):
        """Test Sta2 + Evt6."""
        # Sta2 + Evt6 -> AE-6 -> Sta3 or Sta13
        # Evt6: Receive A-ASSOCIATE-RQ PDU from <remote>
        pass

    def test_evt07(self):
        """Test Sta2 + Evt7."""
        # Sta2 + Evt7 -> <ignore> -> Sta2
        # Evt7: Receive A-ASSOCIATE (accept) primitive from <local user>
        pass

    def test_evt08(self):
        """Test Sta2 + Evt8."""
        # Sta2 + Evt8 -> <ignore> -> Sta2
        # Evt8: Receive A-ASSOCIATE (reject) primitive from <local user>
        pass

    def test_evt09(self):
        """Test Sta2 + Evt9."""
        # Sta2 + Evt9 -> <ignore> -> Sta2
        # Evt9: Receive P-DATA primitive from <local user>
        pass

    def test_evt10(self):
        """Test Sta2 + Evt10."""
        # Sta2 + Evt10 -> AA-1 -> Sta13
        # Evt10: Receive P-DATA-TF PDU from <remote>
        pass

    def test_evt11(self):
        """Test Sta2 + Evt11."""
        # Sta2 + Evt11 -> <ignore> -> Sta2
        # Evt11: Receive A-RELEASE (rq) primitive from <local user>
        pass

    def test_evt12(self):
        """Test Sta2 + Evt12."""
        # Sta2 + Evt12 -> AA-1 -> Sta13
        # Evt12: Receive A-RELEASE-RQ PDU from <remote>
        pass

    def test_evt13(self):
        """Test Sta2 + Evt13."""
        # Sta2 + Evt13 -> AA-1 -> Sta13
        # Evt13: Receive A-RELEASE-RP PDU from <remote>
        pass

    def test_evt14(self):
        """Test Sta2 + Evt14."""
        # Sta2 + Evt14 -> <ignore> -> Sta2
        # Evt14: Receive A-RELEASE (rsp) primitive from <local user>
        pass

    def test_evt15(self):
        """Test Sta2 + Evt15."""
        # Sta2 + Evt15 -> <ignore> -> Sta2
        # Evt15: Receive A-ABORT (rq) primitive from <local user>
        pass

    def test_evt16(self):
        """Test Sta2 + Evt16."""
        # Sta2 + Evt16 -> AA-2 -> Sta1
        # Evt16: Receive A-ABORT PDU from <remote>
        pass

    def test_evt17(self):
        """Test Sta2 + Evt17."""
        # Sta2 + Evt17 -> AA-5 -> Sta1
        # Evt17: Receive TRANSPORT_CLOSED from <transport service>
        pass

    def test_evt18(self):
        """Test Sta2 + Evt18."""
        # Sta2 + Evt18 -> AA-2 -> Sta1
        # Evt18: ARTIM timer expired from <local service>
        pass

    def test_evt19(self):
        """Test Sta2 + Evt19."""
        # Sta2 + Evt19 -> AA-1 -> Sta13
        # Evt19: Received unrecognised or invalid PDU from <remote>
        pass


@pytest.mark.skip()
class TestState13(TestStateBase):
    """Tests for State 13:"""
    def test_evt01(self):
        """Test Sta2 + Evt1."""
        # Sta2 + Evt1 -> <ignore> -> Sta2
        # Evt1: A-ASSOCIATE (rq) primitive from <local user>
        pass

    def test_evt02(self):
        """Test Sta2 + Evt2."""
        # Sta2 + Evt2 -> <ignore> -> Sta2
        # Evt2: Receive TRANSPORT_OPEN from <transport service>
        pass

    def test_evt03(self):
        """Test Sta2 + Evt3."""
        # Sta2 + Evt3 -> AA-1 -> Sta13
        # Evt3: Receive A-ASSOCIATE-AC PDU from <remote>
        pass

    def test_evt04(self):
        """Test Sta2 + Evt4."""
        # Sta2 + Evt4 -> AA-1 -> Sta13
        # Evt4: Receive A-ASSOCIATE-RJ PDU from <remote>
        pass

    def test_evt05(self):
        """Test Sta2 + Evt5."""
        # Sta2 + Evt5 -> <ignore> -> Sta2
        # Evt5: Receive TRANSPORT_INDICATION from <transport service>
        pass

    def test_evt06(self):
        """Test Sta2 + Evt6."""
        # Sta2 + Evt6 -> AE-6 -> Sta3 or Sta13
        # Evt6: Receive A-ASSOCIATE-RQ PDU from <remote>
        pass

    def test_evt07(self):
        """Test Sta2 + Evt7."""
        # Sta2 + Evt7 -> <ignore> -> Sta2
        # Evt7: Receive A-ASSOCIATE (accept) primitive from <local user>
        pass

    def test_evt08(self):
        """Test Sta2 + Evt8."""
        # Sta2 + Evt8 -> <ignore> -> Sta2
        # Evt8: Receive A-ASSOCIATE (reject) primitive from <local user>
        pass

    def test_evt09(self):
        """Test Sta2 + Evt9."""
        # Sta2 + Evt9 -> <ignore> -> Sta2
        # Evt9: Receive P-DATA primitive from <local user>
        pass

    def test_evt10(self):
        """Test Sta2 + Evt10."""
        # Sta2 + Evt10 -> AA-1 -> Sta13
        # Evt10: Receive P-DATA-TF PDU from <remote>
        pass

    def test_evt11(self):
        """Test Sta2 + Evt11."""
        # Sta2 + Evt11 -> <ignore> -> Sta2
        # Evt11: Receive A-RELEASE (rq) primitive from <local user>
        pass

    def test_evt12(self):
        """Test Sta2 + Evt12."""
        # Sta2 + Evt12 -> AA-1 -> Sta13
        # Evt12: Receive A-RELEASE-RQ PDU from <remote>
        pass

    def test_evt13(self):
        """Test Sta2 + Evt13."""
        # Sta2 + Evt13 -> AA-1 -> Sta13
        # Evt13: Receive A-RELEASE-RP PDU from <remote>
        pass

    def test_evt14(self):
        """Test Sta2 + Evt14."""
        # Sta2 + Evt14 -> <ignore> -> Sta2
        # Evt14: Receive A-RELEASE (rsp) primitive from <local user>
        pass

    def test_evt15(self):
        """Test Sta2 + Evt15."""
        # Sta2 + Evt15 -> <ignore> -> Sta2
        # Evt15: Receive A-ABORT (rq) primitive from <local user>
        pass

    def test_evt16(self):
        """Test Sta2 + Evt16."""
        # Sta2 + Evt16 -> AA-2 -> Sta1
        # Evt16: Receive A-ABORT PDU from <remote>
        pass

    def test_evt17(self):
        """Test Sta2 + Evt17."""
        # Sta2 + Evt17 -> AA-5 -> Sta1
        # Evt17: Receive TRANSPORT_CLOSED from <transport service>
        pass

    def test_evt18(self):
        """Test Sta2 + Evt18."""
        # Sta2 + Evt18 -> AA-2 -> Sta1
        # Evt18: ARTIM timer expired from <local service>
        pass

    def test_evt19(self):
        """Test Sta2 + Evt19."""
        # Sta2 + Evt19 -> AA-1 -> Sta13
        # Evt19: Received unrecognised or invalid PDU from <remote>
        pass


class TestStateMachineFunctionalRequestor(object):
    """Functional tests for StateMachine as association requestor."""
    def setup(self):
        """Run prior to each test"""
        self.scp = None

        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        assoc = Association(ae, mode='requestor')
        assoc.acse_timeout = ae.acse_timeout
        assoc.dimse_timeout = ae.dimse_timeout
        assoc.network_timeout = ae.network_timeout

        # Association Acceptor object -> remote AE
        assoc.acceptor.ae_title = validate_ae_title(b'ANY_SCU')
        assoc.acceptor.address = 'localhost'
        assoc.acceptor.port = 11112

        # Association Requestor object -> local AE
        assoc.requestor.address = ae.address
        assoc.requestor.port = ae.port
        assoc.requestor.ae_title = ae.ae_title
        assoc.requestor.maximum_length = 16382
        assoc.requestor.implementation_class_uid = (
            ae.implementation_class_uid
        )
        assoc.requestor.implementation_version_name = (
            ae.implementation_version_name
        )

        cx = build_context(VerificationSOPClass)
        cx.context_id = 1
        assoc.requestor.requested_contexts = [cx]

        self.assoc = assoc
        self.fsm = self.monkey_patch(assoc.dul.state_machine)

    def teardown(self):
        """Clear any active threads"""
        if self.scp:
            self.scp.abort()

        time.sleep(0.1)

        for thread in threading.enumerate():
            if isinstance(thread, DummyBaseSCP):
                thread.abort()
                thread.stop()

    def monkey_patch(self, fsm):
        """Monkey patch the StateMachine to add testing hooks."""
        # Record all state transitions
        fsm._transitions = []
        fsm.original_transition = fsm.transition

        def transition(state):
            fsm._transitions.append(state)
            fsm.original_transition(state)

        fsm.transition = transition

        # Record all event/state/actions
        fsm._changes = []
        fsm.original_action = fsm.do_action

        def do_action(event):
            if (event, fsm.current_state) in TRANSITION_TABLE:
                action_name = TRANSITION_TABLE[(event, fsm.current_state)]
                fsm._changes.append((fsm.current_state, event, action_name))

            fsm.original_action(event)

        fsm.do_action = do_action

        return fsm

    def test_monkey_patch(self):
        """Test monkey patching of StateMachine works as intended."""
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        assoc = Association(ae, mode='requestor')

        fsm = self.monkey_patch(assoc.dul.state_machine)
        assert fsm.current_state == 'Sta1'

        fsm.current_state = 'Sta13'
        fsm.do_action('Evt3')

        assert fsm._changes == [('Sta13', 'Evt3', 'AA-6')]
        assert fsm._transitions == ['Sta13']

    def test_associate_no_connection(self):
        """Test association with no connection to peer."""
        self.scp = DummyVerificationSCP()
        self.scp.send_a_abort = True
        self.scp.ae._handle_connection = self.scp.dev_handle_connection
        self.scp.start()

        assert self.fsm.current_state == 'Sta1'

        self.assoc.acceptor.port = 11113
        self.assoc.start()

        while (not self.assoc.is_established and not self.assoc.is_rejected and
               not self.assoc.is_aborted and not self.assoc.dul._kill_thread):
            time.sleep(0.05)

        assert not self.assoc.is_aborted

        #print(self.fsm._transitions)
        #print(self.fsm._changes)
        assert self.fsm._transitions == [
            'Sta1'  # Idle
        ]
        assert self.fsm._changes == [
            ('Sta1', 'Evt1', 'AE-1'),  # recv A-ASSOC rq primitive
        ]

        assert self.fsm.current_state == 'Sta1'

        self.scp.stop()

    def test_associate_accept_release(self):
        """Test normal association/release."""
        self.scp = DummyVerificationSCP()
        self.scp.start()

        assert self.fsm.current_state == 'Sta1'

        self.assoc.start()

        while (not self.assoc.is_established and not self.assoc.is_rejected and
               not self.assoc.is_aborted and not self.assoc.dul._kill_thread):
            time.sleep(0.05)

        if self.assoc.is_established:
            self.assoc.release()

            assert self.fsm._transitions == [
                'Sta4',  # Waiting for connection to complete
                'Sta5',  # Waiting for A-ASSOC-AC or -RJ PDU
                'Sta6',  # Assoc established
                'Sta7',  # Waiting for A-RELEASE-RP PDU
                'Sta1'  # Idle
            ]
            assert self.fsm._changes == [
                ('Sta1', 'Evt1', 'AE-1'),  # recv A-ASSOC rq primitive
                ('Sta4', 'Evt2', 'AE-2'),  # connection confirmed
                ('Sta5', 'Evt3', 'AE-3'),  # A-ASSOC-AC PDU recv
                ('Sta6', 'Evt11', 'AR-1'),  # A-RELEASE rq primitive
                ('Sta7', 'Evt13', 'AR-3'),  # A-RELEASE-RP PDU recv
            ]

        assert self.fsm.current_state == 'Sta1'

        self.scp.stop()

    def test_associate_reject(self):
        """Test normal association rejection."""
        self.scp = DummyVerificationSCP()
        self.scp.ae.require_called_aet = True
        self.scp.start()

        assert self.fsm.current_state == 'Sta1'

        self.assoc.start()

        while (not self.assoc.is_established and not self.assoc.is_rejected and
               not self.assoc.is_aborted and not self.assoc.dul._kill_thread):
            time.sleep(0.05)

        assert self.assoc.is_rejected

        assert self.fsm._transitions == [
            'Sta4',  # Waiting for connection to complete
            'Sta5',  # Waiting for A-ASSOC-AC or -RJ PDU
            'Sta1'  # Idle
        ]
        assert self.fsm._changes == [
            ('Sta1', 'Evt1', 'AE-1'),  # recv A-ASSOC rq primitive
            ('Sta4', 'Evt2', 'AE-2'),  # connection confirmed
            ('Sta5', 'Evt4', 'AE-4'),  # A-ASSOC-RJ PDU recv
        ]

        assert self.fsm.current_state == 'Sta1'

        self.scp.stop()

    def test_associate_peer_aborts(self):
        """Test association negotiation aborted by peer."""
        self.scp = DummyVerificationSCP()
        self.scp.send_a_abort = True
        self.scp.ae._handle_connection = self.scp.dev_handle_connection
        self.scp.start()

        assert self.fsm.current_state == 'Sta1'

        self.assoc.start()

        while (not self.assoc.is_established and not self.assoc.is_rejected and
               not self.assoc.is_aborted and not self.assoc.dul._kill_thread):
            time.sleep(0.05)

        assert self.assoc.is_aborted

        #print(self.fsm._transitions)
        assert self.fsm._transitions == [
            'Sta4',  # Waiting for connection to complete
            'Sta5',  # Waiting for A-ASSOC-AC or -RJ PDU
            'Sta1'  # Idle
        ]
        #print(self.fsm._changes)
        assert self.fsm._changes == [
            ('Sta1', 'Evt1', 'AE-1'),  # recv A-ASSOC rq primitive
            ('Sta4', 'Evt2', 'AE-2'),  # connection confirmed
            ('Sta5', 'Evt16', 'AA-3'),  # A-ABORT PDU recv
        ]

        assert self.fsm.current_state == 'Sta1'

        self.scp.stop()

    def test_associate_accept_abort(self):
        """Test association acceptance then local abort."""
        self.scp = DummyVerificationSCP()
        self.scp.start()

        assert self.fsm.current_state == 'Sta1'

        self.assoc.start()

        while (not self.assoc.is_established and not self.assoc.is_rejected and
               not self.assoc.is_aborted and not self.assoc.dul._kill_thread):
            time.sleep(0.05)

        if self.assoc.is_established:
            self.assoc.abort()

            #print(self.fsm._transitions)
            #print(self.fsm._changes)
            assert self.fsm._transitions == [
                'Sta4',  # Waiting for connection to complete
                'Sta5',  # Waiting for A-ASSOC-AC or -RJ PDU
                'Sta6',  # Assoc established
                'Sta13',  # Waiting for connection closed
                'Sta1'  # Idle
            ]
            assert self.fsm._changes == [
                ('Sta1', 'Evt1', 'AE-1'),  # recv A-ASSOC rq primitive
                ('Sta4', 'Evt2', 'AE-2'),  # connection confirmed
                ('Sta5', 'Evt3', 'AE-3'),  # A-ASSOC-AC PDU recv
                ('Sta6', 'Evt15', 'AA-1'),  # A-ABORT rq primitive
                ('Sta13', 'Evt17', 'AR-5'),  # connection closed
            ]

        assert self.fsm.current_state == 'Sta1'

        self.scp.stop()

    def test_associate_accept_local_abort(self):
        """Test association acceptance then local abort if no cx."""
        self.scp = DummyVerificationSCP()
        self.scp.start()

        assert self.fsm.current_state == 'Sta1'

        self.assoc.requestor.requested_contexts[0].abstract_syntax = '1.2.3'
        self.assoc.start()

        while (not self.assoc.is_established and not self.assoc.is_rejected and
               not self.assoc.is_aborted and not self.assoc.dul._kill_thread):
            time.sleep(0.05)

        time.sleep(0.1)

        assert self.fsm._transitions == [
            'Sta4',  # Waiting for connection to complete
            'Sta5',  # Waiting for A-ASSOC-AC or -RJ PDU
            'Sta6',  # Assoc established
            'Sta13',  # Waiting for connection close
            'Sta1'  # Idle
        ]
        assert self.fsm._changes == [
            ('Sta1', 'Evt1', 'AE-1'),  # A-ASSOC rq primitive
            ('Sta4', 'Evt2', 'AE-2'),  # connection confirmed
            ('Sta5', 'Evt3', 'AE-3'),  # A-ASSOC-AC PDU recv
            ('Sta6', 'Evt15', 'AA-1'),  # A-ABORT rq primitive
            ('Sta13', 'Evt17', 'AR-5'),  # Connection closed
        ]

        assert self.fsm.current_state == 'Sta1'

        self.scp.stop()

    def test_associate_accept_peer_abort(self):
        """Test association acceptance then peer abort."""
        self.scp = DummyVerificationSCP()
        self.scp.ae.network_timeout = 0.5
        self.scp.start()

        assert self.fsm.current_state == 'Sta1'

        self.assoc.start()

        while (not self.assoc.is_established and not self.assoc.is_rejected and
               not self.assoc.is_aborted and not self.assoc.dul._kill_thread):
            time.sleep(0.05)

        while not self.assoc.is_established:
            time.sleep(0.05)

        while not self.assoc.is_aborted:
            time.sleep(0.05)

        #print(self.fsm._transitions)
        #print(self.fsm._changes)
        assert self.fsm._transitions == [
            'Sta4',  # Waiting for connection to complete
            'Sta5',  # Waiting for A-ASSOC-AC or -RJ PDU
            'Sta6',  # Assoc established
            'Sta1'  # Idle
        ]
        assert self.fsm._changes == [
            ('Sta1', 'Evt1', 'AE-1'),  # A-ASSOC rq primitive
            ('Sta4', 'Evt2', 'AE-2'),  # connection confirmed
            ('Sta5', 'Evt3', 'AE-3'),  # A-ASSOC-AC PDU recv
            ('Sta6', 'Evt16', 'AA-3'),  # A-ABORT-RQ PDV recv
        ]

        assert self.fsm.current_state == 'Sta1'

        self.scp.stop()

    def test_associate_send_data(self):
        """Test association acceptance then send DIMSE message."""
        self.scp = DummyVerificationSCP()
        self.scp.start()

        assert self.fsm.current_state == 'Sta1'

        self.assoc.start()

        while (not self.assoc.is_established and not self.assoc.is_rejected and
               not self.assoc.is_aborted and not self.assoc.dul._kill_thread):
            time.sleep(0.05)

        self.assoc.send_c_echo()
        self.assoc.release()

        #while not self.assoc.is_released:
        #    time.sleep(0.05)

        #print(self.fsm._transitions)
        #print(self.fsm._changes)
        assert self.fsm._transitions == [
            'Sta4',  # Waiting for connection to complete
            'Sta5',  # Waiting for A-ASSOC-AC or -RJ PDU
            'Sta6',  # Assoc established
            'Sta6',
            'Sta6',
            'Sta7',  # Waitinf for A-RELEASE-RP PDU
            'Sta1'  # Idle
        ]
        assert self.fsm._changes == [
            ('Sta1', 'Evt1', 'AE-1'),  # A-ASSOC rq primitive
            ('Sta4', 'Evt2', 'AE-2'),  # connection confirmed
            ('Sta5', 'Evt3', 'AE-3'),  # A-ASSOC-AC PDU recv
            ('Sta6', 'Evt9', 'DT-1'),  # P-DATA rq primitive
            ('Sta6', 'Evt10', 'DT-2'),  # P-DATA-TF PDU recv
            ('Sta6', 'Evt11', 'AR-1'),  # A-RELEASE rq primitive
            ('Sta7', 'Evt13', 'AR-3'),  # A-RELEASE-RP PDU recv
        ]

        assert self.fsm.current_state == 'Sta1'

        self.scp.stop()

    @pytest.mark.skip()
    def test_release_AR6(self):
        """Test receive P-DATA-TF while waiting for A-RELEASE-RP."""
        # Requestor sends A-RELEASE-RQ, acceptor sends P-DATA-TF then
        #   A-RELEASE-RP
        # Patch AR-4 to also send a P-DATA-TF
        orig_entry = FINITE_STATE.ACTIONS['AR-4']

        def AR_4(dul):
            # Send C-ECHO-RQ
            dul.scu_socket.send(p_data_tf)

            # Normal release response
            dul.pdu = A_RELEASE_RP()
            dul.pdu.from_primitive(dul.primitive)
            # Callback
            dul.assoc.acse.debug_send_release_rp(dul.pdu)
            dul.scu_socket.send(dul.pdu.encode())
            dul.artim_timer.start()
            return 'Sta13'

        # In this case the association acceptor will hit AR_4
        FINITE_STATE.ACTIONS['AR-4'] = ('Bluh', AR_4, 'Sta13')

        self.scp = DummyVerificationSCP()
        self.scp.start()

        assert self.fsm.current_state == 'Sta1'

        self.assoc.start()

        while (not self.assoc.is_established and not self.assoc.is_rejected and
               not self.assoc.is_aborted and not self.assoc.dul._kill_thread):
            time.sleep(0.05)

        self.assoc.release()

        #print(self.fsm._transitions)
        #print(self.fsm._changes)
        assert self.fsm._transitions == [
            'Sta4',  # Waiting for connection to complete
            'Sta5',  # Waiting for A-ASSOC-AC or -RJ PDU
            'Sta6',  # Assoc established
            'Sta7',
            'Sta7',  # Waiting for A-RELEASE-RP PDU
            'Sta1'  # Idle
        ]
        assert self.fsm._changes == [
            ('Sta1', 'Evt1', 'AE-1'),  # A-ASSOC rq primitive
            ('Sta4', 'Evt2', 'AE-2'),  # connection confirmed
            ('Sta5', 'Evt3', 'AE-3'),  # A-ASSOC-AC PDU recv
            ('Sta6', 'Evt11', 'AR-1'),  # A-RELEASE rq primitive
            ('Sta7', 'Evt10', 'AR-6'),  # P-DATA-TF PDU recv
            ('Sta7', 'Evt13', 'AR-3'),  # A-RELEASE-RP PDU recv
        ]

        assert self.fsm.current_state == 'Sta1'

        self.scp.stop()

        FINITE_STATE.ACTIONS['AR-4']= orig_entry

    @pytest.mark.skip()
    def test_release_AR7(self):
        """Test receive P-DATA primitive after A-RELEASE-RQ PDU."""

        orig_entry = FINITE_STATE.ACTIONS['AR-2']

        def AR_2(dul):
            """AR-2 occurs when an A-RELEASE-RQ PDU is received."""
            # Add P-DATA primitive request
            primitive = C_ECHO()
            primitive.MessageID = 1
            primitive.AffectedSOPClassUID = VerificationSOPClass

            # Send C-ECHO request to the peer via DIMSE and wait for the response
            dul.assoc.dimse.send_msg(primitive, 1)

            # Normal AR2 response
            dul.to_user_queue.put(dul.primitive)
            return 'Sta8'

        # In this case the association acceptor will hit AR_2
        FINITE_STATE.ACTIONS['AR-2'] = ('Bluh', AR_2, 'Sta8')

        self.scp = DummyVerificationSCP()
        self.scp.start()

        assert self.fsm.current_state == 'Sta1'

        self.assoc.start()

        while (not self.assoc.is_established and not self.assoc.is_rejected and
               not self.assoc.is_aborted and not self.assoc.dul._kill_thread):
            time.sleep(0.05)

        self.assoc.release()

        #print(self.fsm._transitions)
        #print(self.fsm._changes)
        assert self.fsm._transitions == [
            'Sta4',  # Waiting for connection to complete
            'Sta5',  # Waiting for A-ASSOC-AC or -RJ PDU
            'Sta6',  # Assoc established
            'Sta7',
            'Sta7',  # Waiting for A-RELEASE-RP PDU
            'Sta1'  # Idle
        ]
        assert self.fsm._changes == [
            ('Sta1', 'Evt1', 'AE-1'),  # A-ASSOC rq primitive
            ('Sta4', 'Evt2', 'AE-2'),  # connection confirmed
            ('Sta5', 'Evt3', 'AE-3'),  # A-ASSOC-AC PDU recv
            ('Sta6', 'Evt11', 'AR-1'),  # A-RELEASE rq primitive
            ('Sta7', 'Evt10', 'AR-6'),  # P-DATA-TF PDU recv
            ('Sta7', 'Evt13', 'AR-3'),  # A-RELEASE-RP PDU recv
        ]

        assert self.fsm.current_state == 'Sta1'

        self.scp.stop()

        FINITE_STATE.ACTIONS['AR-2']= orig_entry

    @pytest.mark.skip()
    def test_release_AR8(self):
        """Test receive A-RELEASE-RQ after sending A-RELEASE-RQ PDU."""

        orig_entry = FINITE_STATE.ACTIONS['AR-2']

        def AR_2(dul):
            """AR-2 occurs when an A-RELEASE-RQ PDU is received."""
            # Send A-RELEASE-RQ
            pdu = A_RELEASE_RQ()
            pdu.from_primitive(A_RELEASE())

            bytestream = pdu.encode()
            dul.scu_socket.send(bytestream)
            #dul.assoc.acse.send_release(dul.assoc)

            # Normal AR2 response
            dul.to_user_queue.put(dul.primitive)
            return 'Sta8'

        # In this case the association acceptor will hit AR_2
        FINITE_STATE.ACTIONS['AR-2'] = ('Bluh', AR_2, 'Sta8')

        self.scp = DummyVerificationSCP()
        self.scp.acse_timeout = 0.5
        self.scp.start()

        assert self.fsm.current_state == 'Sta1'

        self.assoc.start()

        while (not self.assoc.is_established and not self.assoc.is_rejected and
               not self.assoc.is_aborted and not self.assoc.dul._kill_thread):
            time.sleep(0.05)

        self.assoc.release()

        #print(self.fsm._transitions)
        #print(self.fsm._changes)
        assert self.fsm._transitions == [
            'Sta4',  # Waiting for connection to complete
            'Sta5',  # Waiting for A-ASSOC-AC or -RJ PDU
            'Sta6',  # Assoc established
            'Sta7',  # Waiting for A-RELEASE-RP PDU
            'Sta9',  # Release collision requestor: wait for A-RELEASE primit
            'Sta11',  # Release collision requestor: wait for A-RELEASE-RP PDU
            'Sta1'  # Idle
        ]
        assert self.fsm._changes == [
            ('Sta1', 'Evt1', 'AE-1'),  # A-ASSOC rq primitive
            ('Sta4', 'Evt2', 'AE-2'),  # connection confirmed
            ('Sta5', 'Evt3', 'AE-3'),  # A-ASSOC-AC PDU recv
            ('Sta6', 'Evt11', 'AR-1'),  # A-RELEASE rq primitive
            ('Sta7', 'Evt12', 'AR-8'),  # A-RELEASE-RQ PDU recv
            ('Sta9', 'Evt14', 'AR-9'),  # A-RELEASE rsp primitive
            ('Sta11', 'Evt13', 'AR-3'),  # A-RELEASE-RP PDU recv
        ]

        assert self.fsm.current_state == 'Sta1'

        self.scp.stop()

        FINITE_STATE.ACTIONS['AR-2']= orig_entry


class TestStateMachineFunctionalAcceptor(object):
    """Functional tests for StateMachine as association acceptor."""
    def setup(self):
        """Run prior to each test"""
        self.scp = None

        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        assoc = Association(ae, mode='requestor')
        assoc.acse_timeout = ae.acse_timeout
        assoc.dimse_timeout = ae.dimse_timeout
        assoc.network_timeout = ae.network_timeout

        # Association Acceptor object -> remote AE
        assoc.acceptor.ae_title = validate_ae_title(b'ANY_SCU')
        assoc.acceptor.address = 'localhost'
        assoc.acceptor.port = 11112

        # Association Requestor object -> local AE
        assoc.requestor.address = ae.address
        assoc.requestor.port = ae.port
        assoc.requestor.ae_title = ae.ae_title
        assoc.requestor.maximum_length = 16382
        assoc.requestor.implementation_class_uid = (
            ae.implementation_class_uid
        )
        assoc.requestor.implementation_version_name = (
            ae.implementation_version_name
        )

        cx = build_context(VerificationSOPClass)
        cx.context_id = 1
        assoc.requestor.requested_contexts = [cx]

        self.assoc = assoc
        self.fsm = self.monkey_patch(assoc.dul.state_machine)

    def teardown(self):
        """Clear any active threads"""
        if self.scp:
            self.scp.abort()

        time.sleep(0.1)

        for thread in threading.enumerate():
            if isinstance(thread, DummyBaseSCP):
                thread.abort()
                thread.stop()

    def monkey_patch(self, fsm):
        """Monkey patch the StateMachine to add testing hooks."""
        # Record all state transitions
        fsm._transitions = []
        fsm.original_transition = fsm.transition

        def transition(state):
            fsm._transitions.append(state)
            fsm.original_transition(state)

        fsm.transition = transition

        # Record all event/state/actions
        fsm._changes = []
        fsm.original_action = fsm.do_action

        def do_action(event):
            if (event, fsm.current_state) in TRANSITION_TABLE:
                action_name = TRANSITION_TABLE[(event, fsm.current_state)]
                fsm._changes.append((fsm.current_state, event, action_name))

            fsm.original_action(event)

        fsm.do_action = do_action

        return fsm

    def test_invalid_protocol_version(self):
        """Test receiving an A-ASSOC-RQ with invalid protocol version."""
        self.scp = DummyVerificationSCP()
        self.scp.start()

        assert self.fsm.current_state == 'Sta1'

        # Patch AE_2
        orig_entry = FINITE_STATE.ACTIONS['AE-2']

        def AE_2(dul):
            dul.pdu = A_ASSOCIATE_RQ()
            dul.pdu.from_primitive(dul.primitive)
            dul.pdu.protocol_version = 0x0002
            # Callback
            dul.assoc.acse.debug_send_associate_rq(dul.pdu)
            bytestream = dul.pdu.encode()
            dul.scu_socket.send(bytestream)
            return 'Sta5'

        FINITE_STATE.ACTIONS['AE-2'] = ('Bluh', AE_2, 'Sta5')

        self.assoc.start()

        while (not self.assoc.is_established and not self.assoc.is_rejected and
               not self.assoc.is_aborted and not self.assoc.dul._kill_thread):
            time.sleep(0.05)

        assert self.assoc.is_rejected
        assert self.assoc.acceptor.primitive.result == 0x01
        assert self.assoc.acceptor.primitive.result_source == 0x02
        assert self.assoc.acceptor.primitive.diagnostic == 0x02

        assert self.fsm.current_state == 'Sta1'

        self.scp.stop()
        FINITE_STATE.ACTIONS['AE-2']= orig_entry

    @pytest.mark.skip()
    def test_release_collision(self):
        """Test receive A-RELEASE-RQ after sending A-RELEASE-RQ PDU."""

        orig_entry = FINITE_STATE.ACTIONS['AR-2']

        def AR_2(dul):
            """AR-2 occurs when an A-RELEASE-RQ PDU is received."""
            # Send A-RELEASE-RQ
            pdu = A_RELEASE_RQ()
            pdu.from_primitive(A_RELEASE())

            bytestream = pdu.encode()
            dul.scu_socket.send(bytestream)
            #dul.assoc.acse.send_release(dul.assoc)

            # Normal AR2 response
            dul.to_user_queue.put(dul.primitive)
            return 'Sta8'

        # In this case the association requestor will hit AR_2
        FINITE_STATE.ACTIONS['AR-2'] = ('Bluh', AR_2, 'Sta8')

        self.scp = DummyVerificationSCP()
        self.scp.acse_timeout = 0.5
        self.scp.start()

        assert self.fsm.current_state == 'Sta1'

        self.assoc.start()

        while (not self.assoc.is_established and not self.assoc.is_rejected and
               not self.assoc.is_aborted and not self.assoc.dul._kill_thread):
            time.sleep(0.05)

        self.scp.ae.active_associations[0].release()

        print(self.fsm._transitions)
        print(self.fsm._changes)
        assert self.fsm._transitions == [
            'Sta4',  # Waiting for connection to complete
            'Sta5',  # Waiting for A-ASSOC-AC or -RJ PDU
            'Sta6',  # Assoc established
            'Sta7',  # Waiting for A-RELEASE-RP PDU
            'Sta9',  # Release collision requestor: wait for A-RELEASE primit
            'Sta11',  # Release collision requestor: wait for A-RELEASE-RP PDU
            'Sta1'  # Idle
        ]
        assert self.fsm._changes == [
            ('Sta1', 'Evt1', 'AE-1'),  # A-ASSOC rq primitive
            ('Sta4', 'Evt2', 'AE-2'),  # connection confirmed
            ('Sta5', 'Evt3', 'AE-3'),  # A-ASSOC-AC PDU recv
            ('Sta6', 'Evt11', 'AR-1'),  # A-RELEASE rq primitive
            ('Sta7', 'Evt12', 'AR-8'),  # A-RELEASE-RQ PDU recv
            ('Sta9', 'Evt14', 'AR-9'),  # A-RELEASE rsp primitive
            ('Sta11', 'Evt13', 'AR-3'),  # A-RELEASE-RP PDU recv
        ]

        assert self.fsm.current_state == 'Sta1'

        self.scp.stop()

        FINITE_STATE.ACTIONS['AR-2']= orig_entry
