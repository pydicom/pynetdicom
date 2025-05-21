"""Unit tests for fsm.py"""

import datetime
import logging
import socket
from struct import pack
import threading
import time

import pytest

from pynetdicom import AE, build_context, evt, debug_logger
from pynetdicom.association import Association
from pynetdicom import fsm as FINITE_STATE
from pynetdicom.fsm import *
from pynetdicom.dimse_primitives import C_ECHO
from pynetdicom.pdu_primitives import (
    A_ASSOCIATE,
    A_ABORT,
    A_P_ABORT,
    P_DATA,
    A_RELEASE,
    MaximumLengthNotification,
    ImplementationClassUIDNotification,
)
from pynetdicom.sop_class import Verification
from pynetdicom.transport import AssociationSocket, T_CONNECT, AddressInformation
from .encoded_pdu_items import (
    a_associate_ac,
    a_associate_rq,
    a_associate_rj,
    p_data_tf,
    a_abort,
    a_release_rq,
    a_release_rp,
)
from .parrot import ThreadedParrot


# debug_logger()


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


class BadDUL:
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


class TestStateMachine:
    """Non-functional unit tests for fsm.StateMachine."""

    def test_init(self):
        """Test creation of new StateMachine."""
        ae = AE()
        ae.add_requested_context(Verification)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        assoc = Association(ae, mode="requestor")

        fsm = assoc.dul.state_machine
        assert fsm.current_state == "Sta1"
        assert fsm.dul == assoc.dul

    def test_invalid_transition_raises(self):
        """Test StateMachine.transition using invalid states raises."""
        ae = AE()
        ae.add_requested_context(Verification)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        assoc = Association(ae, mode="requestor")

        fsm = assoc.dul.state_machine
        msg = r"Invalid state 'Sta0' for State Machine"
        with pytest.raises(ValueError, match=msg):
            fsm.transition("Sta0")

    def test_valid_transition(self):
        """Test StateMachine.transition using valid states."""
        ae = AE()
        ae.add_requested_context(Verification)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        assoc = Association(ae, mode="requestor")
        fsm = assoc.dul.state_machine

        for ii in range(1, 14):
            assert 1 <= ii <= 13
            fsm.transition("Sta{}".format(ii))
            assert fsm.current_state == "Sta{}".format(ii)

    @pytest.mark.parametrize("event, states", REFERENCE_BAD_EVENTS)
    def test_invalid_action_raises(self, event, states):
        """Test StateMachine.do_action raises exception if action invalid."""
        ae = AE()
        ae.add_requested_context(Verification)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        assoc = Association(ae, mode="requestor")
        fsm = assoc.dul.state_machine

        for state in states:
            state = "Sta{}".format(state)
            fsm.current_state = state

            msg = msg = r"Invalid event '{}' for the current state '{}'".format(
                event, state
            )
            with pytest.raises(InvalidEventError, match=msg):
                fsm.do_action(event)

    @pytest.mark.parametrize("event, states", REFERENCE_GOOD_EVENTS)
    def test_exception_during_action(self, event, states):
        """Test an exception raised during an action kill the DUL."""
        ae = AE()
        ae.add_requested_context(Verification)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        assoc = Association(ae, mode="requestor")
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


class TestStateBase:
    """Base class for State tests."""

    def setup_method(self):
        ae = AE()
        ae.add_requested_context(Verification)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        assoc = Association(ae, mode="requestor")

        assoc.set_socket(AssociationSocket(assoc, address=AddressInformation("", 0)))

        # Association Acceptor object -> remote AE
        assoc.acceptor.ae_title = "ANY_SCU"
        assoc.acceptor.address_info = AddressInformation("localhost", 11112)

        # Association Requestor object -> local AE
        assoc.requestor.address_info = AddressInformation("", 11113)
        assoc.requestor.ae_title = ae.ae_title
        assoc.requestor.maximum_length = 16382
        assoc.requestor.implementation_class_uid = ae.implementation_class_uid
        assoc.requestor.implementation_version_name = ae.implementation_version_name

        cx = build_context(Verification)
        cx.context_id = 1
        assoc.requestor.requested_contexts = [cx]

        self.assoc = assoc
        self.fsm = self.monkey_patch(assoc.dul.state_machine)
        self.scp = None

    def teardown_method(self):
        if self.scp:
            for commands in self.scp.commands:
                self.scp.step()
            # self.scp.commands = [('exit', None)]
            # self.scp.step()
            self.scp.shutdown()

    def get_associate(self, assoc_type):
        primitive = A_ASSOCIATE()
        if assoc_type == "request":
            primitive.application_context_name = "1.2.3.4.5.6"
            # Calling AE Title is the source DICOM AE title
            primitive.calling_ae_title = "LOCAL_AE_TITLE  "
            # Called AE Title is the destination DICOM AE title
            primitive.called_ae_title = "REMOTE_AE_TITLE "
            # The TCP/IP address of the source, pynetdicom includes port too
            primitive.calling_presentation_address = AddressInformation("localhost", 0)
            # The TCP/IP address of the destination, pynetdicom includes port too
            primitive.called_presentation_address = AddressInformation(
                "localhost", 11112
            )
            # Proposed presentation contexts
            cx = build_context(Verification)
            cx.context_id = 1
            primitive.presentation_context_definition_list = [cx]

            user_info = []

            item = MaximumLengthNotification()
            item.maximum_length_received = 16382
            user_info.append(item)

            item = ImplementationClassUIDNotification()
            item.implementation_class_uid = "1.2.3.4"
            user_info.append(item)
            primitive.user_information = user_info
        elif assoc_type == "accept":
            primitive.application_context_name = "1.2.3.4.5.6"
            # Calling AE Title is the source DICOM AE title
            primitive.calling_ae_title = "LOCAL_AE_TITLE  "
            # Called AE Title is the destination DICOM AE title
            primitive.called_ae_title = "REMOTE_AE_TITLE "
            # The TCP/IP address of the source, pynetdicom includes port too
            primitive.result = 0x00
            primitive.result_source = 0x01
            # Proposed presentation contexts
            cx = build_context(Verification)
            cx.context_id = 1
            primitive.presentation_context_definition_results_list = [cx]

            user_info = []

            item = MaximumLengthNotification()
            item.maximum_length_received = 16383
            user_info.append(item)

            item = ImplementationClassUIDNotification()
            item.implementation_class_uid = "1.2.3.4.5"
            user_info.append(item)
            primitive.user_information = user_info
        elif assoc_type == "reject":
            primitive.result = 0x01
            primitive.result_source = 0x01
            primitive.diagnostic = 0x01

        return primitive

    def get_release(self, is_response=False):
        primitive = A_RELEASE()
        if is_response:
            primitive.result = "affirmative"

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

    def start_server(self, commands):
        """Start the receiving server."""
        server = ThreadedParrot(("localhost", 11112), commands)
        thread = threading.Thread(target=server.serve_forever)
        thread.daemon = True
        thread.start()

        return server

    def print_fsm_scp(self, fsm, scp=None):
        """Print out some of the quantities we're interested in."""
        print("Transitions", fsm._transitions)
        print("Changes")
        for change in fsm._changes:
            print("\t{}".format(change))
        print("Events", fsm._events)

        if scp and scp.handlers:
            print("Received", scp.handlers[0].received)
            print("Sent", scp.handlers[0].sent)

    def get_acceptor_assoc(self):
        # AF_INET: IPv4, SOCK_STREAM: TCP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVTIMEO, pack("ll", 1, 0))
        sock.connect(("localhost", 11112))

        ae = AE()
        ae.add_supported_context(Verification)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        assoc = Association(ae, mode="acceptor")

        assoc.set_socket(AssociationSocket(assoc, client_socket=sock))

        # Association Acceptor object -> remote AE
        assoc.acceptor.ae_title = "ANY_SCU"
        assoc.acceptor.address_info = AddressInformation("localhost", 11112)

        # Association Requestor object -> local AE
        assoc.requestor.address_info = AddressInformation("", 11113)
        assoc.requestor.ae_title = ae.ae_title
        assoc.requestor.maximum_length = 16382
        assoc.requestor.implementation_class_uid = ae.implementation_class_uid
        assoc.requestor.implementation_version_name = ae.implementation_version_name

        cx = build_context(Verification)
        cx.context_id = 1
        assoc.acceptor.supported_contexts = [cx]

        fsm = self.monkey_patch(assoc.dul.state_machine)
        return assoc, fsm

    def wait_on_state(self, fsm, state, timeout=5):
        start = 0
        while (
            fsm.current_state != state
            and fsm.current_state not in state
            and start < timeout
        ):
            time.sleep(0.0001)
            start += 0.0001

        # if start >= timeout:
        #     print(f"'wait_on_state' timed out for state {state}")


IGNORE_FILTER = "ignore:.*:pytest.PytestUnhandledThreadExceptionWarning"


class TestState01(TestStateBase):
    """Tests for State 01: Idle."""

    def move_to_state(self, assoc, scp):
        assoc.start()
        self.wait_on_state(assoc.dul.state_machine, "Sta1")

    def test_evt01(self):
        """Test Sta1 + Evt1."""
        # Sta1 + Evt1 -> AE-1 -> Sta4
        # Evt1: A-ASSOCIATE (rq) primitive from <local user>
        # AE-1: Issue TRANSPORT_CONNECT primitive to <transport service>
        commands = [("recv", None), ("send", a_abort), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._transitions[:1] == ["Sta4"]
        assert self.fsm._changes[:1] == [
            ("Sta1", "Evt1", "AE-1"),
        ]
        assert self.fsm._events[:1] == ["Evt1"]

    @pytest.mark.skip()
    def test_evt02(self):
        """Test Sta1 + Evt2."""
        # Sta1 + Evt2 -> <ignore> -> Sta1
        # Evt2: Receive TRANSPORT_OPEN from <transport service>
        pass

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt03(self):
        """Test Sta1 + Evt3."""
        # Sta1 + Evt3 -> <ignore> -> Sta1
        # Evt3: Receive A-ASSOCIATE-AC PDU from <remote>
        commands = [("send", a_associate_ac), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.assoc._mode = "acceptor"
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.socket.socket.connect(("localhost", 11112))
        self.assoc.dul.socket._is_connected = True

        scp.step()

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[:1] == ["Evt3"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt04(self):
        """Test Sta1 + Evt4."""
        # Sta1 + Evt4 -> <ignore> -> Sta1
        # Evt4: Receive A-ASSOCIATE-RJ PDU from <remote>
        commands = [("send", a_associate_rj), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.assoc._mode = "acceptor"
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.socket.socket.connect(("localhost", 11112))
        self.assoc.dul.socket._is_connected = True

        scp.step()

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[:1] == ["Evt4"]

    @pytest.mark.skip()
    def test_evt05(self):
        """Test Sta1 + Evt5."""
        # Sta1 + Evt5 -> AE-5 -> Sta2
        # Evt5: Receive TRANSPORT_INDICATION from <transport service>
        # AE-5: Issue TRANSPORT_RESPONSE to <transport service>
        #       Start ARTIM timer
        pass

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt06(self):
        """Test Sta1 + Evt6."""
        # Sta1 + Evt6 -> <ignore> -> Sta1
        # Evt6: Receive A-ASSOCIATE-RQ PDU from <remote>
        commands = [("send", a_associate_rq), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.assoc._mode = "acceptor"
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.socket.socket.connect(("localhost", 11112))
        self.assoc.dul.socket._is_connected = True

        scp.step()

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[:1] == ["Evt6"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt07(self):
        """Test Sta1 + Evt7."""
        # Sta1 + Evt7 -> <ignore> -> Sta1
        # Evt7: Receive A-ASSOCIATE (accept) primitive from <local user>
        self.assoc._mode = "acceptor"
        self.assoc.start()

        time.sleep(0.1)

        self.assoc.dul.send_pdu(self.get_associate("accept"))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == "Evt7"

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt08(self):
        """Test Sta1 + Evt8."""
        # Sta1 + Evt8 -> <ignore> -> Sta1
        # Evt8: Receive A-ASSOCIATE (reject) primitive from <local user>
        self.assoc._mode = "acceptor"
        self.assoc.start()

        time.sleep(0.1)

        self.assoc.dul.send_pdu(self.get_associate("reject"))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == "Evt8"
        assert self.fsm.current_state == "Sta1"

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt09(self):
        """Test Sta1 + Evt9."""
        # Sta1 + Evt9 -> <ignore> -> Sta1
        # Evt9: Receive P-DATA primitive from <local user>
        self.assoc._mode = "acceptor"
        self.assoc.start()

        time.sleep(0.1)

        self.assoc.dul.send_pdu(self.get_pdata())

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == "Evt9"
        assert self.fsm.current_state == "Sta1"

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt10(self):
        """Test Sta1 + Evt10."""
        # Sta1 + Evt10 -> <ignore> -> Sta1
        # Evt10: Receive P-DATA-TF PDU from <remote>
        commands = [("send", p_data_tf), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.assoc._mode = "acceptor"
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.socket.socket.connect(("localhost", 11112))
        self.assoc.dul.socket._is_connected = True

        scp.step()

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[:1] == ["Evt10"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt11(self):
        """Test Sta1 + Evt11."""
        # Sta1 + Evt11 -> <ignore> -> Sta1
        # Evt11: Receive A-RELEASE (rq) primitive from <local user>
        self.assoc._mode = "acceptor"
        self.assoc.start()

        time.sleep(0.1)

        self.assoc.dul.send_pdu(self.get_release(False))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == "Evt11"
        assert self.fsm.current_state == "Sta1"

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt12(self):
        """Test Sta1 + Evt12."""
        # Sta1 + Evt12 -> <ignore> -> Sta1
        # Evt12: Receive A-RELEASE-RQ PDU from <remote>
        commands = [("send", a_release_rq), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.assoc._mode = "acceptor"
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.socket.socket.connect(("localhost", 11112))
        self.assoc.dul.socket._is_connected = True

        scp.step()

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[:1] == ["Evt12"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt13(self):
        """Test Sta1 + Evt13."""
        # Sta1 + Evt13 -> <ignore> -> Sta1
        # Evt13: Receive A-RELEASE-RP PDU from <remote>
        commands = [("send", a_release_rp), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.assoc._mode = "acceptor"
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.socket.socket.connect(("localhost", 11112))
        self.assoc.dul.socket._is_connected = True

        scp.step()

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[:1] == ["Evt13"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt14(self):
        """Test Sta1 + Evt14."""
        # Sta1 + Evt14 -> <ignore> -> Sta1
        # Evt14: Receive A-RELEASE (rsp) primitive from <local user>
        self.assoc._mode = "acceptor"
        self.assoc.start()

        time.sleep(0.1)

        self.assoc.dul.send_pdu(self.get_release(True))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == "Evt14"
        assert self.fsm.current_state == "Sta1"

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt15(self):
        """Test Sta1 + Evt15."""
        # Sta1 + Evt15 -> <ignore> -> Sta1
        # Evt15: Receive A-ABORT (rq) primitive from <local user>
        self.assoc._mode = "acceptor"
        self.assoc.start()

        time.sleep(0.1)

        self.assoc.dul.send_pdu(self.get_abort(False))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        self.assoc.kill()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == "Evt15"
        assert self.fsm.current_state == "Sta1"

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt16(self):
        """Test Sta1 + Evt16."""
        # Sta1 + Evt16 -> <ignore> -> Sta1
        # Evt16: Receive A-ABORT PDU from <remote>
        commands = [("send", a_abort), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.assoc._mode = "acceptor"
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.socket.socket.connect(("localhost", 11112))
        self.assoc.dul.socket._is_connected = True

        scp.step()

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[:1] == ["Evt16"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt17(self):
        """Test Sta1 + Evt17."""
        # Sta1 + Evt17 -> <ignore> -> Sta1
        # Evt17: Receive TRANSPORT_CLOSED from <transport service>
        commands = [("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.assoc._mode = "acceptor"
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.socket.socket.connect(("localhost", 11112))
        self.assoc.dul.socket._is_connected = True

        scp.step()
        scp.shutdown()

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[:1] == ["Evt17"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt18(self):
        """Test Sta1 + Evt18."""
        # Sta1 + Evt18 -> <ignore> -> Sta1
        # Evt18: ARTIM timer expired from <local service>
        self.assoc._mode = "acceptor"
        self.assoc.start()

        time.sleep(0.1)

        self.assoc.dul.artim_timer.timeout = 0.05
        self.assoc.dul.artim_timer.start()

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        self.assoc.kill()

        assert self.assoc.dul.artim_timer.expired

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[0] == "Evt18"
        assert self.fsm.current_state == "Sta1"

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt19(self):
        """Test Sta1 + Evt19."""
        # Sta1 + Evt19 -> <ignore> -> Sta1
        # Evt19: Received unrecognised or invalid PDU from <remote>
        commands = [("send", b"\x08\x00\x00\x00\x00\x00\x00"), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.assoc._mode = "acceptor"
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.socket.socket.connect(("localhost", 11112))
        self.assoc.dul.socket._is_connected = True

        scp.step()

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._transitions == []
        assert self.fsm._changes == []
        assert self.fsm._events[:1] == ["Evt19"]


class TestState02(TestStateBase):
    """Tests for State 02: Connection open, waiting for A-ASSOCIATE-RQ."""

    def move_to_state(self, assoc, scp):
        assoc.start()
        self.wait_on_state(assoc.dul.state_machine, "Sta2")

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt01(self):
        """Test Sta2 + Evt1."""
        # Sta2 + Evt1 -> <ignore> -> Sta2
        # Evt1: A-ASSOCIATE (rq) primitive from <local user>
        commands = [("exit", None)]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        assoc.dul.send_pdu(self.get_associate("request"))

        while assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert fsm._transitions[:1] == ["Sta2"]
        assert fsm._changes[:1] == [
            ("Sta1", "Evt5", "AE-5"),
        ]
        assert fsm._events[:2] == ["Evt5", "Evt1"]

    @pytest.mark.skip()
    def test_evt02(self):
        """Test Sta2 + Evt2."""
        # Sta2 + Evt2 -> <ignore> -> Sta2
        # Evt2: Receive TRANSPORT_OPEN from <transport service>
        pass

    def test_evt03(self):
        """Test Sta2 + Evt3."""
        # Sta2 + Evt3 -> AA-1 -> Sta13
        # Evt3: Receive A-ASSOCIATE-AC PDU from <remote>
        # AA-1: Send A-ABORT PDU, start ARTIM
        commands = [("send", a_associate_ac), ("recv", None), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert fsm._transitions[:2] == ["Sta2", "Sta13"]
        assert fsm._changes[:2] == [("Sta1", "Evt5", "AE-5"), ("Sta2", "Evt3", "AA-1")]
        assert fsm._events[:2] == ["Evt5", "Evt3"]

    def test_evt04(self):
        """Test Sta2 + Evt4."""
        # Sta2 + Evt4 -> AA-1 -> Sta13
        # Evt4: Receive A-ASSOCIATE-RJ PDU from <remote>
        # AA-1: Send A-ABORT PDU, start ARTIM
        commands = [("send", a_associate_rj), ("recv", None), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert fsm._transitions[:2] == ["Sta2", "Sta13"]
        assert fsm._changes[:2] == [("Sta1", "Evt5", "AE-5"), ("Sta2", "Evt4", "AA-1")]
        assert fsm._events[:2] == ["Evt5", "Evt4"]

    @pytest.mark.skip()
    def test_evt05(self):
        """Test Sta2 + Evt5."""
        # Sta2 + Evt5 -> <ignore> -> Sta2
        # Evt5: Receive TRANSPORT_INDICATION from <transport service>
        pass

    def test_evt06a(self):
        """Test Sta2 + Evt6."""
        # Sta2 + Evt6 -> AE-6 -> **Sta3** or Sta13
        # Evt6: Receive A-ASSOCIATE-RQ PDU from <remote>
        # AE-6: Stop ARTIM, issue A-ASSOCIATE or A-ASSOCIATE-RJ PDU
        commands = [("send", a_associate_rq), ("recv", None), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert fsm._transitions[:2] == ["Sta2", "Sta3"]
        assert fsm._changes[:2] == [("Sta1", "Evt5", "AE-5"), ("Sta2", "Evt6", "AE-6")]
        assert fsm._events[:2] == ["Evt5", "Evt6"]

    def test_evt06b(self):
        """Test Sta2 + Evt6."""
        # Sta2 + Evt6 -> AE-6 -> Sta3 or **Sta13**
        # Evt6: Receive A-ASSOCIATE-RQ PDU from <remote>
        # AE-6: Stop ARTIM, issue A-ASSOCIATE or A-ASSOCIATE-RJ PDU
        bad_request = a_associate_rq[:6] + b"\x00\x02" + a_associate_rq[8:]
        assert len(bad_request) == len(a_associate_rq)
        commands = [("send", bad_request), ("recv", None), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert fsm._transitions[:2] == ["Sta2", "Sta13"]
        assert fsm._changes[:2] == [("Sta1", "Evt5", "AE-5"), ("Sta2", "Evt6", "AE-6")]
        assert fsm._events[:2] == ["Evt5", "Evt6"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt07(self):
        """Test Sta2 + Evt7."""
        # Sta2 + Evt7 -> <ignore> -> Sta2
        # Evt7: Receive A-ASSOCIATE (accept) primitive from <local user>
        commands = [("exit", None)]
        self.scp = scp = self.start_server(commands)

        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)
        assoc.dul.send_pdu(self.get_associate("accept"))

        while assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert fsm._transitions[:1] == ["Sta2"]
        assert fsm._changes[:1] == [
            ("Sta1", "Evt5", "AE-5"),
        ]
        assert fsm._events[:2] == ["Evt5", "Evt7"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt08(self):
        """Test Sta2 + Evt8."""
        # Sta2 + Evt8 -> <ignore> -> Sta2
        # Evt8: Receive A-ASSOCIATE (reject) primitive from <local user>
        commands = [("exit", None)]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        assoc.dul.send_pdu(self.get_associate("reject"))

        while assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert fsm._transitions[:1] == ["Sta2"]
        assert fsm._changes[:1] == [
            ("Sta1", "Evt5", "AE-5"),
        ]
        assert fsm._events[:2] == ["Evt5", "Evt8"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt09(self):
        """Test Sta2 + Evt9."""
        # Sta2 + Evt9 -> <ignore> -> Sta2
        # Evt9: Receive P-DATA primitive from <local user>
        commands = [("exit", None)]
        self.scp = scp = self.start_server(commands)

        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        assoc.dul.send_pdu(self.get_pdata())

        while assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert fsm._transitions[:1] == ["Sta2"]
        assert fsm._changes[:1] == [
            ("Sta1", "Evt5", "AE-5"),
        ]
        assert fsm._events[:2] == ["Evt5", "Evt9"]

    def test_evt10(self):
        """Test Sta2 + Evt10."""
        # Sta2 + Evt10 -> AA-1 -> Sta13
        # Evt10: Receive P-DATA-TF PDU from <remote>
        # AA-1: Send A-ABORT PDU, start ARTIM
        commands = [("send", p_data_tf), ("recv", None), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert fsm._transitions[:2] == ["Sta2", "Sta13"]
        assert fsm._changes[:2] == [("Sta1", "Evt5", "AE-5"), ("Sta2", "Evt10", "AA-1")]
        assert fsm._events[:2] == ["Evt5", "Evt10"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt11(self):
        """Test Sta2 + Evt11."""
        # Sta2 + Evt11 -> <ignore> -> Sta2
        # Evt11: Receive A-RELEASE (rq) primitive from <local user>
        commands = [("exit", None)]
        self.scp = scp = self.start_server(commands)

        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        assoc.dul.send_pdu(self.get_release(False))

        while assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert fsm._transitions[:1] == ["Sta2"]
        assert fsm._changes[:1] == [
            ("Sta1", "Evt5", "AE-5"),
        ]
        assert fsm._events[:2] == ["Evt5", "Evt11"]

    def test_evt12(self):
        """Test Sta2 + Evt12."""
        # Sta2 + Evt12 -> AA-1 -> Sta13
        # Evt12: Receive A-RELEASE-RQ PDU from <remote>
        # AA-1: Send A-ABORT PDU, start ARTIM
        commands = [("send", a_release_rq), ("recv", None), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert fsm._transitions[:2] == ["Sta2", "Sta13"]
        assert fsm._changes[:2] == [("Sta1", "Evt5", "AE-5"), ("Sta2", "Evt12", "AA-1")]
        assert fsm._events[:2] == ["Evt5", "Evt12"]

    def test_evt13(self):
        """Test Sta2 + Evt13."""
        # Sta2 + Evt13 -> AA-1 -> Sta13
        # Evt13: Receive A-RELEASE-RP PDU from <remote>
        # AA-1: Send A-ABORT PDU, start ARTIM
        commands = [("send", a_release_rp), ("recv", None), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert fsm._transitions[:2] == ["Sta2", "Sta13"]
        assert fsm._changes[:2] == [("Sta1", "Evt5", "AE-5"), ("Sta2", "Evt13", "AA-1")]
        assert fsm._events[:2] == ["Evt5", "Evt13"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt14(self):
        """Test Sta2 + Evt14."""
        # Sta2 + Evt14 -> <ignore> -> Sta2
        # Evt14: Receive A-RELEASE (rsp) primitive from <local user>
        commands = [("exit", None)]
        self.scp = scp = self.start_server(commands)

        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        assoc.dul.send_pdu(self.get_release(True))

        while assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert fsm._transitions[:1] == ["Sta2"]
        assert fsm._changes[:1] == [
            ("Sta1", "Evt5", "AE-5"),
        ]
        assert fsm._events[:2] == ["Evt5", "Evt14"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt15(self):
        """Test Sta2 + Evt15."""
        # Sta2 + Evt15 -> <ignore> -> Sta2
        # Evt15: Receive A-ABORT (rq) primitive from <local user>
        commands = [("exit", None)]
        self.scp = scp = self.start_server(commands)

        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        assoc.dul.send_pdu(self.get_abort())

        while assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert fsm._transitions[:1] == ["Sta2"]
        assert fsm._changes[:1] == [
            ("Sta1", "Evt5", "AE-5"),
        ]
        assert fsm._events[:2] == ["Evt5", "Evt15"]

    def test_evt16(self):
        """Test Sta2 + Evt16."""
        # Sta2 + Evt16 -> AA-2 -> Sta1
        # Evt16: Receive A-ABORT PDU from <remote>
        # AA-2: Stop ARTIM, close connection
        commands = [("send", a_abort), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        scp.step()
        scp.step()
        scp.shutdown()

        assert fsm._transitions[:2] == ["Sta2", "Sta1"]
        assert fsm._changes[:2] == [("Sta1", "Evt5", "AE-5"), ("Sta2", "Evt16", "AA-2")]
        assert fsm._events[:2] == ["Evt5", "Evt16"]

    def test_evt17(self):
        """Test Sta2 + Evt17."""
        # Sta2 + Evt17 -> AA-5 -> Sta1
        # Evt17: Receive TRANSPORT_CLOSED from <transport service>
        # AA-5: Stop ARTIM timer
        commands = [("exit", None)]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        scp.step()
        scp.shutdown()

        time.sleep(0.5)

        assert fsm._transitions[:2] == ["Sta2", "Sta1"]
        assert fsm._changes[:2] == [("Sta1", "Evt5", "AE-5"), ("Sta2", "Evt17", "AA-5")]
        assert fsm._events[:2] == ["Evt5", "Evt17"]

    def test_evt18(self):
        """Test Sta2 + Evt18."""
        # Sta2 + Evt18 -> AA-2 -> Sta1
        # Evt18: ARTIM timer expired from <local service>
        commands = [("exit", None)]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        assoc.dul.artim_timer.timeout = 0.05
        assoc.dul.artim_timer.start()
        time.sleep(0.5)

        scp.step()
        scp.shutdown()

        assert fsm._transitions[:1] == ["Sta2"]
        assert fsm._changes[:1] == [
            ("Sta1", "Evt5", "AE-5"),
        ]
        assert fsm._events[:2] == ["Evt5", "Evt18"]

    def test_evt19(self):
        """Test Sta2 + Evt19."""
        # Sta2 + Evt19 -> AA-1 -> Sta13
        # Evt19: Received unrecognised or invalid PDU from <remote>
        # AA-1: Send A-ABORT PDU, start ARTIM
        commands = [("send", b"\x08\x00\x00\x00\x00\x00\x00\x00"), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        scp.step()
        scp.step()
        scp.shutdown()

        assert fsm._transitions[:2] == ["Sta2", "Sta13"]
        assert fsm._changes[:2] == [("Sta1", "Evt5", "AE-5"), ("Sta2", "Evt19", "AA-1")]
        assert fsm._events[:2] == ["Evt5", "Evt19"]


class TestState03(TestStateBase):
    """Tests for State 03: Awaiting A-ASSOCIATE (rsp) primitive."""

    def move_to_state(self, assoc, scp):
        assoc.start()
        scp.step()
        self.wait_on_state(assoc.dul.state_machine, "Sta3")

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt01(self):
        """Test Sta3 + Evt1."""
        # Sta3 + Evt1 -> <ignore> -> Sta3
        # Evt1: A-ASSOCIATE (rq) primitive from <local user>
        commands = [("send", a_associate_rq), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()

        def _neg_as_acc():
            """Override ACSE._negotiate_as_acceptor so no A-ASSOCIATE (rsp)."""
            pass

        assoc.acse._negotiate_as_acceptor = _neg_as_acc

        self.move_to_state(assoc, scp)

        assoc.dul.send_pdu(self.get_associate("request"))

        while assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert fsm._transitions[:2] == ["Sta2", "Sta3"]
        assert fsm._changes[:2] == [("Sta1", "Evt5", "AE-5"), ("Sta2", "Evt6", "AE-6")]
        assert fsm._events[:3] == ["Evt5", "Evt6", "Evt1"]

    @pytest.mark.skip()
    def test_evt02(self):
        """Test Sta3 + Evt2."""
        # Sta3 + Evt2 -> <ignore> -> Sta3
        # Evt2: Receive TRANSPORT_OPEN from <transport service>
        pass

    def test_evt03(self):
        """Test Sta3 + Evt3."""
        # Sta3 + Evt3 -> AA-8 -> Sta13
        # Evt3: Receive A-ASSOCIATE-AC PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("send", a_associate_rq),
            ("send", a_associate_ac),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()

        def _neg_as_acc():
            """Override ACSE._negotiate_as_acceptor so no A-ASSOCIATE (rsp)."""
            pass

        assoc.acse._negotiate_as_acceptor = _neg_as_acc
        self.move_to_state(assoc, scp)

        scp.step()

        self.wait_on_state(assoc.dul.state_machine, "Sta13")

        scp.step()
        scp.step()
        scp.shutdown()

        # Check A-ABORT-RQ sent
        pdu = A_ABORT_RQ()
        pdu.decode(scp.received[0])
        assert pdu.source == 2
        assert pdu.reason_diagnostic == 0

        # Check local got A-P-ABORT
        assert assoc.acse.is_aborted("a-p-abort")

        assert fsm._transitions[:2] == ["Sta2", "Sta3"]
        assert fsm._changes[:3] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt3", "AA-8"),
        ]
        assert fsm._events[:3] == ["Evt5", "Evt6", "Evt3"]

    def test_evt04(self):
        """Test Sta3 + Evt4."""
        # Sta3 + Evt4 -> AA-8 -> Sta13
        # Evt4: Receive A-ASSOCIATE-RJ PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [("send", a_associate_rq), ("send", a_associate_rj), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()

        def _neg_as_acc():
            """Override ACSE._negotiate_as_acceptor so no A-ASSOCIATE (rsp)."""
            pass

        assoc.acse._negotiate_as_acceptor = _neg_as_acc

        self.move_to_state(assoc, scp)

        scp.step()

        self.wait_on_state(assoc.dul.state_machine, "Sta13")

        scp.step()
        scp.shutdown()

        assert fsm._transitions[:2] == ["Sta2", "Sta3"]
        assert fsm._changes[:3] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt4", "AA-8"),
        ]
        assert fsm._events[:3] == ["Evt5", "Evt6", "Evt4"]

    @pytest.mark.skip()
    def test_evt05(self):
        """Test Sta3 + Evt5."""
        # Sta3 + Evt5 -> <ignore> -> Sta3
        # Evt5: Receive TRANSPORT_INDICATION from <transport service>
        pass

    def test_evt06(self):
        """Test Sta3 + Evt6."""
        # Sta3 + Evt6 -> AA-8 -> Sta13
        # Evt6: Receive A-ASSOCIATE-RQ PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [("send", a_associate_rq), ("send", a_associate_rq), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()

        def _neg_as_acc():
            """Override ACSE._negotiate_as_acceptor so no A-ASSOCIATE (rsp)."""
            pass

        assoc.acse._negotiate_as_acceptor = _neg_as_acc
        self.move_to_state(assoc, scp)

        scp.step()

        self.wait_on_state(assoc.dul.state_machine, "Sta13")

        scp.step()
        scp.shutdown()

        assert fsm._transitions[:2] == ["Sta2", "Sta3"]
        assert fsm._changes[:3] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt6", "AA-8"),
        ]
        assert fsm._events[:3] == ["Evt5", "Evt6", "Evt6"]

    def test_evt07(self):
        """Test Sta3 + Evt7."""
        # Sta3 + Evt7 -> AE-7 -> Sta6
        # Evt7: Receive A-ASSOCIATE (accept) primitive from <local user>
        # AE-7: Send A-ASSOCIATE-AC PDU
        commands = [("send", a_associate_rq), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)
        self.wait_on_state(assoc.dul.state_machine, "Sta6")

        scp.step()
        scp.shutdown()

        assert fsm._transitions[:3] == ["Sta2", "Sta3", "Sta6"]
        assert fsm._changes[:3] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt7", "AE-7"),
        ]
        assert fsm._events[:3] == ["Evt5", "Evt6", "Evt7"]

    def test_evt08(self):
        """Test Sta3 + Evt8."""
        # Sta3 + Evt8 -> AE-8 -> Sta13
        # Evt8: Receive A-ASSOCIATE (reject) primitive from <local user>
        # AE-8: Send A-ASSOCIATE-RJ PDU and start ARTIM
        commands = [("send", a_associate_rq), ("exit", None)]
        self.scp = scp = self.start_server(commands)

        assoc, fsm = self.get_acceptor_assoc()

        assoc.acse._negotiate_as_acceptor

        def _neg_as_acc():
            """Override ACSE._negotiate_as_acceptor so no A-ASSOCIATE (rsp)."""
            assoc.dul.send_pdu(self.get_associate("reject"))

        assoc.acse._negotiate_as_acceptor = _neg_as_acc
        self.move_to_state(assoc, scp)
        self.wait_on_state(assoc.dul.state_machine, ["Sta13", "Sta1"])

        scp.step()
        scp.shutdown()

        assert fsm._transitions[:2] == ["Sta2", "Sta3"]
        assert fsm._changes[:3] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt8", "AE-8"),
        ]
        assert fsm._events[:3] == ["Evt5", "Evt6", "Evt8"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt09(self):
        """Test Sta3 + Evt9."""
        # Sta3 + Evt9 -> <ignore> -> Sta3
        # Evt9: Receive P-DATA primitive from <local user>
        commands = [("send", a_associate_rq), ("exit", None)]
        self.scp = scp = self.start_server(commands)

        assoc, fsm = self.get_acceptor_assoc()

        assoc.acse._negotiate_as_acceptor

        def _neg_as_acc():
            """Override ACSE._negotiate_as_acceptor so no A-ASSOCIATE (rsp)."""
            assoc.dul.send_pdu(self.get_pdata())

        assoc.acse._negotiate_as_acceptor = _neg_as_acc
        self.move_to_state(assoc, scp)

        while assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert fsm._transitions[:2] == ["Sta2", "Sta3"]
        assert fsm._changes[:2] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
        ]
        assert fsm._events[:3] == ["Evt5", "Evt6", "Evt9"]

    def test_evt10(self):
        """Test Sta3 + Evt10."""
        # Sta3 + Evt10 -> AA-8 -> Sta13
        # Evt10: Receive P-DATA-TF PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [("send", a_associate_rq), ("send", p_data_tf), ("exit", None)]
        self.scp = scp = self.start_server(commands)

        assoc, fsm = self.get_acceptor_assoc()

        orig = assoc.acse._negotiate_as_acceptor

        def _neg_as_acc():
            """Override ACSE._negotiate_as_acceptor so no A-ASSOCIATE (rsp)."""
            # Keep the state machine in Sta3 for 0.5 s
            scp.step()
            time.sleep(0.5)
            orig()

        assoc.acse._negotiate_as_acceptor = _neg_as_acc
        self.move_to_state(assoc, scp)
        self.wait_on_state(assoc.dul.state_machine, "Sta13")

        scp.step()
        scp.shutdown()

        assert fsm._transitions[:2] == ["Sta2", "Sta3"]
        assert fsm._changes[:3] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt10", "AA-8"),
        ]
        assert fsm._events[:3] == ["Evt5", "Evt6", "Evt10"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt11(self):
        """Test Sta3 + Evt11."""
        # Sta3 + Evt11 -> <ignore> -> Sta3
        # Evt11: Receive A-RELEASE (rq) primitive from <local user>
        commands = [("send", a_associate_rq), ("exit", None)]
        self.scp = scp = self.start_server(commands)

        assoc, fsm = self.get_acceptor_assoc()

        assoc.acse._negotiate_as_acceptor

        def _neg_as_acc():
            """Override ACSE._negotiate_as_acceptor so no A-ASSOCIATE (rsp)."""
            assoc.dul.send_pdu(self.get_release(False))

        assoc.acse._negotiate_as_acceptor = _neg_as_acc
        self.move_to_state(assoc, scp)

        while assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert fsm._transitions[:2] == ["Sta2", "Sta3"]
        assert fsm._changes[:2] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
        ]
        assert fsm._events[:3] == ["Evt5", "Evt6", "Evt11"]

    def test_evt12(self):
        """Test Sta3 + Evt12."""
        # Sta3 + Evt12 -> AA-8 -> Sta13
        # Evt12: Receive A-RELEASE-RQ PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [("send", a_associate_rq), ("send", a_release_rq), ("exit", None)]
        self.scp = scp = self.start_server(commands)

        assoc, fsm = self.get_acceptor_assoc()

        orig = assoc.acse._negotiate_as_acceptor

        def _neg_as_acc():
            """Override ACSE._negotiate_as_acceptor so no A-ASSOCIATE (rsp)."""
            # Keep the state machine in Sta3 for 0.5 s
            scp.step()
            time.sleep(0.5)
            orig()

        assoc.acse._negotiate_as_acceptor = _neg_as_acc
        self.move_to_state(assoc, scp)
        self.wait_on_state(assoc.dul.state_machine, "Sta13")

        scp.step()
        scp.shutdown()

        assert fsm._transitions[:2] == ["Sta2", "Sta3"]
        assert fsm._changes[:3] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt12", "AA-8"),
        ]
        assert fsm._events[:3] == ["Evt5", "Evt6", "Evt12"]

    def test_evt13(self):
        """Test Sta3 + Evt13."""
        # Sta3 + Evt13 -> AA-8 -> Sta13
        # Evt13: Receive A-RELEASE-RP PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [("send", a_associate_rq), ("send", a_release_rp), ("exit", None)]
        self.scp = scp = self.start_server(commands)

        assoc, fsm = self.get_acceptor_assoc()

        orig = assoc.acse._negotiate_as_acceptor

        def _neg_as_acc():
            """Override ACSE._negotiate_as_acceptor so no A-ASSOCIATE (rsp)."""
            # Keep the state machine in Sta3 for 0.5 s
            scp.step()
            time.sleep(0.5)
            orig()

        assoc.acse._negotiate_as_acceptor = _neg_as_acc
        self.move_to_state(assoc, scp)
        self.wait_on_state(assoc.dul.state_machine, "Sta13")

        scp.step()
        scp.shutdown()

        assert fsm._transitions[:2] == ["Sta2", "Sta3"]
        assert fsm._changes[:3] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt13", "AA-8"),
        ]
        assert fsm._events[:3] == ["Evt5", "Evt6", "Evt13"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt14(self):
        """Test Sta3 + Evt14."""
        # Sta3 + Evt14 -> <ignore> -> Sta3
        # Evt14: Receive A-RELEASE (rsp) primitive from <local user>
        commands = [("send", a_associate_rq), ("exit", None)]
        self.scp = scp = self.start_server(commands)

        assoc, fsm = self.get_acceptor_assoc()

        assoc.acse._negotiate_as_acceptor

        def _neg_as_acc():
            """Override ACSE._negotiate_as_acceptor so no A-ASSOCIATE (rsp)."""
            assoc.dul.send_pdu(self.get_release(True))

        assoc.acse._negotiate_as_acceptor = _neg_as_acc
        self.move_to_state(assoc, scp)

        while assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert fsm._transitions[:2] == ["Sta2", "Sta3"]
        assert fsm._changes[:2] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
        ]
        assert fsm._events[:3] == ["Evt5", "Evt6", "Evt14"]

    def test_evt15(self):
        """Test Sta3 + Evt15."""
        # Sta3 + Evt15 -> AA-1 -> Sta13
        # Evt15: Receive A-ABORT (rq) primitive from <local user>
        # AA-1: Send A-ABORT PDU, start ARTIM
        commands = [("send", a_associate_rq), ("exit", None)]
        self.scp = scp = self.start_server(commands)

        assoc, fsm = self.get_acceptor_assoc()

        assoc.acse._negotiate_as_acceptor

        def _neg_as_acc():
            """Override ACSE._negotiate_as_acceptor so no A-ASSOCIATE (rsp)."""
            assoc.dul.send_pdu(self.get_abort())

        assoc.acse._negotiate_as_acceptor = _neg_as_acc
        self.move_to_state(assoc, scp)

        self.wait_on_state(assoc.dul.state_machine, "Sta13")

        scp.step()
        scp.shutdown()

        assert fsm._transitions[:2] == ["Sta2", "Sta3"]
        assert fsm._changes[:3] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt15", "AA-1"),
        ]
        assert fsm._events[:3] == ["Evt5", "Evt6", "Evt15"]

    def test_evt16(self):
        """Test Sta3 + Evt16."""
        # Sta3 + Evt16 -> AA-3 -> Sta1
        # Evt16: Receive A-ABORT PDU from <remote>
        # AA-3: Issue A-ABORT or A-P-ABORT primitive, close connection
        commands = [("send", a_associate_rq), ("send", a_abort), ("exit", None)]
        self.scp = scp = self.start_server(commands)

        assoc, fsm = self.get_acceptor_assoc()

        orig = assoc.acse._negotiate_as_acceptor

        def _neg_as_acc():
            """Override ACSE._negotiate_as_acceptor so no A-ASSOCIATE (rsp)."""
            # Keep the state machine in Sta3 for 0.5 s
            scp.step()
            time.sleep(0.5)
            orig()

        assoc.acse._negotiate_as_acceptor = _neg_as_acc
        self.move_to_state(assoc, scp)
        self.wait_on_state(assoc.dul.state_machine, "Sta1")

        scp.step()
        scp.shutdown()

        assert fsm._transitions[:2] == ["Sta2", "Sta3"]
        assert fsm._changes[:3] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt16", "AA-3"),
        ]
        assert fsm._events[:3] == ["Evt5", "Evt6", "Evt16"]

    def test_evt17(self):
        """Test Sta3 + Evt17."""
        # Sta3 + Evt17 -> AA-4 -> Sta1
        # Evt17: Receive TRANSPORT_CLOSED from <transport service>
        # AA-4: Issue A-P-ABORT primitive
        commands = [("send", a_associate_rq), ("exit", None)]
        self.scp = scp = self.start_server(commands)

        assoc, fsm = self.get_acceptor_assoc()

        orig = assoc.acse._negotiate_as_acceptor

        def _neg_as_acc():
            """Override ACSE._negotiate_as_acceptor so no A-ASSOCIATE (rsp)."""
            # Keep the state machine in Sta3 for 0.5 s
            time.sleep(0.5)
            orig()

        assoc.acse._negotiate_as_acceptor = _neg_as_acc
        self.move_to_state(assoc, scp)

        scp.step()
        scp.shutdown()

        self.wait_on_state(assoc.dul.state_machine, "Sta1")

        assert fsm._transitions[:2] == ["Sta2", "Sta3"]
        assert fsm._changes[:3] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt17", "AA-4"),
        ]
        assert fsm._events[:3] == ["Evt5", "Evt6", "Evt17"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt18(self):
        """Test Sta3 + Evt18."""
        # Sta3 + Evt18 -> <ignore> -> Sta3
        # Evt18: ARTIM timer expired from <local service>
        commands = [("send", a_associate_rq), ("exit", None)]
        self.scp = scp = self.start_server(commands)

        assoc, fsm = self.get_acceptor_assoc()

        orig = assoc.acse._negotiate_as_acceptor

        def _neg_as_acc():
            """Override ACSE._negotiate_as_acceptor so no A-ASSOCIATE (rsp)."""
            # Keep the state machine in Sta3 for 0.5 s
            assoc.dul.artim_timer.timeout = 0.05
            assoc.dul.artim_timer.start()
            time.sleep(0.5)
            scp.step()
            orig()

        assoc.acse._negotiate_as_acceptor = _neg_as_acc
        self.move_to_state(assoc, scp)

        while assoc.dul.is_alive():
            time.sleep(0.001)

        scp.shutdown()

        assert fsm._transitions[:2] == ["Sta2", "Sta3"]
        assert fsm._changes[:2] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
        ]
        assert fsm._events[:3] == ["Evt5", "Evt6", "Evt18"]

    def test_evt19(self):
        """Test Sta3 + Evt19."""
        # Sta3 + Evt19 -> AA-8 -> Sta13
        # Evt19: Received unrecognised or invalid PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("send", a_associate_rq),
            ("send", b"\x08\x00\x00\x00\x00\x00\x00\x00"),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)

        assoc, fsm = self.get_acceptor_assoc()

        orig = assoc.acse._negotiate_as_acceptor

        def _neg_as_acc():
            """Override ACSE._negotiate_as_acceptor so no A-ASSOCIATE (rsp)."""
            # Keep the state machine in Sta3 for 0.5 s
            scp.step()
            time.sleep(0.5)
            orig()

        assoc.acse._negotiate_as_acceptor = _neg_as_acc
        self.move_to_state(assoc, scp)
        self.wait_on_state(assoc.dul.state_machine, "Sta13")

        scp.step()
        scp.shutdown()

        assert fsm._transitions[:2] == ["Sta2", "Sta3"]
        assert fsm._changes[:3] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt19", "AA-8"),
        ]
        assert fsm._events[:3] == ["Evt5", "Evt6", "Evt19"]


class TestState04(TestStateBase):
    """Tests for State 04: Awaiting TRANSPORT_OPEN from <transport service>."""

    def move_to_state(self, assoc, scp):
        def connect(primitive):
            """Override the socket's connect so no event gets added."""
            if assoc.dul.socket.socket is None:
                assoc.dul.socket.socket = assoc.dul.socket._create_socket()

            try:
                assoc.dul.socket.socket.connect(primitive.address_info.as_tuple)
                assoc.dul.socket._is_connected = True
            except (OSError, TimeoutError) as exc:
                assoc.dul.socket.close()

        assoc.dul.socket.connect = connect

        assoc.start()
        self.wait_on_state(assoc.dul.state_machine, "Sta4")

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt01(self):
        """Test Sta4 + Evt1."""
        # Sta4 + Evt1 -> <ignore> -> Sta4
        # Evt1: A-ASSOCIATE (rq) primitive from <local user>
        commands = [("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_associate("request"))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._transitions[:1] == ["Sta4"]
        assert self.fsm._changes[:1] == [
            ("Sta1", "Evt1", "AE-1"),
        ]
        assert self.fsm._events[:2] == ["Evt1", "Evt1"]

    @pytest.mark.skip()
    def test_evt02(self):
        """Test Sta4 + Evt2."""
        # Sta4 + Evt2 -> <ignore> -> Sta4
        # Evt2: Receive TRANSPORT_OPEN from <transport service>
        pass

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt03(self):
        """Test Sta4 + Evt3."""
        # Sta4 + Evt3 -> <ignore> -> Sta4
        # Evt3: Receive A-ASSOCIATE-AC PDU from <remote>
        commands = [("send", a_associate_ac), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._transitions[:1] == ["Sta4"]
        assert self.fsm._changes[:1] == [
            ("Sta1", "Evt1", "AE-1"),
        ]
        assert self.fsm._events[:2] == ["Evt1", "Evt3"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt04(self):
        """Test Sta4 + Evt4."""
        # Sta4 + Evt4 -> <ignore> -> Sta4
        # Evt4: Receive A-ASSOCIATE-RJ PDU from <remote>
        commands = [("send", a_associate_rj), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._transitions[:1] == ["Sta4"]
        assert self.fsm._changes[:1] == [
            ("Sta1", "Evt1", "AE-1"),
        ]
        assert self.fsm._events[:2] == ["Evt1", "Evt4"]

    @pytest.mark.skip()
    def test_evt05(self):
        """Test Sta4 + Evt5."""
        # Sta4 + Evt5 -> AE-5 -> Sta2
        # Evt5: Receive TRANSPORT_INDICATION from <transport service>
        # AE-5: Issue TRANSPORT_RESPONSE to <transport service>
        #       Start ARTIM timer
        pass

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt06(self):
        """Test Sta4 + Evt6."""
        # Sta4 + Evt6 -> <ignore> -> Sta4
        # Evt6: Receive A-ASSOCIATE-RQ PDU from <remote>
        commands = [("send", a_associate_rq), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._transitions[:1] == ["Sta4"]
        assert self.fsm._changes[:1] == [
            ("Sta1", "Evt1", "AE-1"),
        ]
        assert self.fsm._events[:2] == ["Evt1", "Evt6"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt07(self):
        """Test Sta4 + Evt7."""
        # Sta4 + Evt7 -> <ignore> -> Sta4
        # Evt7: Receive A-ASSOCIATE (accept) primitive from <local user>
        commands = [("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_associate("accept"))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._transitions[:1] == ["Sta4"]
        assert self.fsm._changes[:1] == [
            ("Sta1", "Evt1", "AE-1"),
        ]
        assert self.fsm._events[:2] == ["Evt1", "Evt7"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt08(self):
        """Test Sta4 + Evt8."""
        # Sta4 + Evt8 -> <ignore> -> Sta4
        # Evt8: Receive A-ASSOCIATE (reject) primitive from <local user>
        commands = [("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_associate("reject"))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._transitions[:1] == ["Sta4"]
        assert self.fsm._changes[:1] == [
            ("Sta1", "Evt1", "AE-1"),
        ]
        assert self.fsm._events[:2] == ["Evt1", "Evt8"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt09(self):
        """Test Sta4 + Evt9."""
        # Sta4 + Evt9 -> <ignore> -> Sta4
        # Evt9: Receive P-DATA primitive from <local user>
        commands = [("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_pdata())

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._transitions[:1] == ["Sta4"]
        assert self.fsm._changes[:1] == [
            ("Sta1", "Evt1", "AE-1"),
        ]
        assert self.fsm._events[:2] == ["Evt1", "Evt9"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt10(self):
        """Test Sta4 + Evt10."""
        # Sta4 + Evt10 -> <ignore> -> Sta4
        # Evt10: Receive P-DATA-TF PDU from <remote>
        commands = [("send", p_data_tf), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._transitions[:1] == ["Sta4"]
        assert self.fsm._changes[:1] == [
            ("Sta1", "Evt1", "AE-1"),
        ]
        assert self.fsm._events[:2] == ["Evt1", "Evt10"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt11(self):
        """Test Sta4 + Evt11."""
        # Sta4 + Evt11 -> <ignore> -> Sta4
        # Evt11: Receive A-RELEASE (rq) primitive from <local user>
        commands = [("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_release(False))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._transitions[:1] == ["Sta4"]
        assert self.fsm._changes[:1] == [
            ("Sta1", "Evt1", "AE-1"),
        ]
        assert self.fsm._events[:2] == ["Evt1", "Evt11"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt12(self):
        """Test Sta4 + Evt12."""
        # Sta4 + Evt12 -> <ignore> -> Sta4
        # Evt12: Receive A-RELEASE-RQ PDU from <remote>
        commands = [("send", a_release_rq), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._transitions[:1] == ["Sta4"]
        assert self.fsm._changes[:1] == [
            ("Sta1", "Evt1", "AE-1"),
        ]
        assert self.fsm._events[:2] == ["Evt1", "Evt12"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt13(self):
        """Test Sta4 + Evt13."""
        # Sta4 + Evt13 -> <ignore> -> Sta4
        # Evt13: Receive A-RELEASE-RP PDU from <remote>
        commands = [("send", a_release_rp), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._transitions[:1] == ["Sta4"]
        assert self.fsm._changes[:1] == [
            ("Sta1", "Evt1", "AE-1"),
        ]
        assert self.fsm._events[:2] == ["Evt1", "Evt13"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt14(self):
        """Test Sta4 + Evt14."""
        # Sta4 + Evt14 -> <ignore> -> Sta4
        # Evt14: Receive A-RELEASE (rsp) primitive from <local user>
        commands = [("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_release(True))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._transitions[:1] == ["Sta4"]
        assert self.fsm._changes[:1] == [
            ("Sta1", "Evt1", "AE-1"),
        ]
        assert self.fsm._events[:2] == ["Evt1", "Evt14"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt15(self):
        """Test Sta4 + Evt15."""
        # Sta4 + Evt15 -> <ignore> -> Sta4
        # Evt15: Receive A-ABORT (rq) primitive from <local user>
        commands = [("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_abort())

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._transitions[:1] == ["Sta4"]
        assert self.fsm._changes[:1] == [
            ("Sta1", "Evt1", "AE-1"),
        ]
        assert self.fsm._events[:2] == ["Evt1", "Evt15"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt16(self):
        """Test Sta4 + Evt16."""
        # Sta4 + Evt16 -> <ignore> -> Sta4
        # Evt16: Receive A-ABORT PDU from <remote>
        commands = [("send", a_abort), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._transitions[:1] == ["Sta4"]
        assert self.fsm._changes[:1] == [
            ("Sta1", "Evt1", "AE-1"),
        ]
        assert self.fsm._events[:2] == ["Evt1", "Evt16"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt17(self):
        """Test Sta4 + Evt17."""
        # Sta4 + Evt17 -> <ignore> -> Sta4
        # Evt17: Receive TRANSPORT_CLOSED from <transport service>
        commands = [("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.shutdown()

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        assert self.fsm._transitions[:1] == ["Sta4"]
        assert self.fsm._changes[:1] == [
            ("Sta1", "Evt1", "AE-1"),
        ]
        assert self.fsm._events[:2] == ["Evt1", "Evt17"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt18(self):
        """Test Sta4 + Evt18."""
        # Sta4 + Evt18 -> <ignore> -> Sta4
        # Evt18: ARTIM timer expired from <local service>
        commands = [("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.artim_timer.timeout = 0.05
        self.assoc.dul.artim_timer.start()

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._transitions[:1] == ["Sta4"]
        assert self.fsm._changes[:1] == [
            ("Sta1", "Evt1", "AE-1"),
        ]
        assert self.fsm._events[:2] == ["Evt1", "Evt18"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt19(self):
        """Test Sta4 + Evt19."""
        # Sta4 + Evt19 -> <ignore> -> Sta4
        # Evt19: Received unrecognised or invalid PDU from <remote>
        commands = [("send", b"\x08\x00\x00\x00\x00\x00\x00\x00\x00"), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._transitions[:1] == ["Sta4"]
        assert self.fsm._changes[:1] == [
            ("Sta1", "Evt1", "AE-1"),
        ]
        assert self.fsm._events[:2] == ["Evt1", "Evt19"]


class TestState05(TestStateBase):
    """Tests for State 05: Awaiting A-ASSOCIATE-AC or A-ASSOCIATE-RJ PDU."""

    def move_to_state(self, assoc, scp):
        assoc.start()
        scp.step()
        self.wait_on_state(assoc.dul.state_machine, "Sta5")

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt01(self):
        """Test Sta5 + Evt1."""
        # Sta5 + Evt1 -> <ignore> -> Sta5
        # Evt1: A-ASSOCIATE (rq) primitive from <local user>
        commands = [("recv", None), ("exit", None)]  # recv a-associate-rq
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_associate("request"))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:2] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
        ]
        assert self.fsm._transitions[:2] == ["Sta4", "Sta5"]
        assert self.fsm._events[:3] == ["Evt1", "Evt2", "Evt1"]

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
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:3] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),  # Sometimes not making it to Sta5...
        ]
        assert self.fsm._transitions[:3] == ["Sta4", "Sta5", "Sta6"]
        assert self.fsm._events[:3] == ["Evt1", "Evt2", "Evt3"]

    def test_evt04(self):
        """Test Sta5 + Evt4."""
        # Sta5 + Evt4 -> AE-4 -> Sta1
        # Evt4: Receive A-ASSOCIATE-RJ PDU from <remote>
        # AE-4: Issue A-ASSOCIATE (rj) primitive
        commands = [("recv", None), ("send", a_associate_rj), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:3] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt4", "AE-4"),
        ]
        assert self.fsm._transitions[:3] == ["Sta4", "Sta5", "Sta1"]
        assert self.fsm._events[:3] == ["Evt1", "Evt2", "Evt4"]

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
        commands = [
            ("recv", None),
            ("send", a_associate_rq),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:3] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt6", "AA-8"),
        ]
        assert self.fsm._transitions[:3] == ["Sta4", "Sta5", "Sta13"]
        assert self.fsm._events[:3] == ["Evt1", "Evt2", "Evt6"]
        assert scp.handlers[0].received[1] == (
            b"\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00"
        )

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt07(self):
        """Test Sta5 + Evt7."""
        # Sta5 + Evt7 -> <ignore> -> Sta5
        # Evt7: Receive A-ASSOCIATE (accept) primitive from <local user>
        commands = [("recv", None), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_associate("accept"))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:2] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
        ]
        assert self.fsm._transitions[:2] == ["Sta4", "Sta5"]
        assert self.fsm._events[:3] == ["Evt1", "Evt2", "Evt7"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt08(self):
        """Test Sta5 + Evt8."""
        # Sta5 + Evt8 -> <ignore> -> Sta5
        # Evt8: Receive A-ASSOCIATE (reject) primitive from <local user>
        commands = [("recv", None), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_associate("reject"))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:2] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
        ]
        assert self.fsm._transitions[:2] == ["Sta4", "Sta5"]
        assert self.fsm._events[:3] == ["Evt1", "Evt2", "Evt8"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt09(self):
        """Test Sta5 + Evt9."""
        # Sta5 + Evt9 -> <ignore> -> Sta5
        # Evt9: Receive P-DATA primitive from <local user>
        commands = [("recv", None), ("exit", None)]  # recv a-associate-rq
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_pdata())

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:2] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
        ]
        assert self.fsm._transitions[:2] == ["Sta4", "Sta5"]
        assert self.fsm._events[:3] == ["Evt1", "Evt2", "Evt9"]

    def test_evt10(self):
        """Test Sta5 + Evt10."""
        # Sta5 + Evt10 -> AA-8 -> Sta13
        # Evt10: Receive P-DATA-TF PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [("recv", None), ("send", p_data_tf), ("recv", None), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:3] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt10", "AA-8"),
        ]
        assert self.fsm._transitions[:3] == ["Sta4", "Sta5", "Sta13"]
        assert self.fsm._events[:3] == ["Evt1", "Evt2", "Evt10"]

        # Issue A-ABORT PDU
        assert scp.handlers[0].received[1] == (
            b"\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00"
        )

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt11(self):
        """Test Sta5 + Evt11."""
        # Sta5 + Evt11 -> <ignore> -> Sta5
        # Evt11: Receive A-RELEASE (rq) primitive from <local user>
        commands = [("recv", None), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_release(False))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:2] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
        ]
        assert self.fsm._transitions[:2] == ["Sta4", "Sta5"]
        assert self.fsm._events[:3] == ["Evt1", "Evt2", "Evt11"]

    def test_evt12(self):
        """Test Sta5 + Evt12."""
        # Sta5 + Evt12 -> AA-8 -> Sta13
        # Evt12: Receive A-RELEASE-RQ PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("recv", None),
            ("send", a_release_rq),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:3] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt12", "AA-8"),
        ]
        assert self.fsm._transitions[:3] == ["Sta4", "Sta5", "Sta13"]
        assert self.fsm._events[:3] == ["Evt1", "Evt2", "Evt12"]
        # Issue A-ABORT PDU
        assert scp.handlers[0].received[1] == (
            b"\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00"
        )

    def test_evt13(self):
        """Test Sta5 + Evt13."""
        # Sta5 + Evt13 -> AA-8 -> Sta13
        # Evt13: Receive A-RELEASE-RP PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("recv", None),
            ("send", a_release_rp),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:3] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt13", "AA-8"),
        ]
        assert self.fsm._transitions[:3] == ["Sta4", "Sta5", "Sta13"]
        assert self.fsm._events[:3] == ["Evt1", "Evt2", "Evt13"]
        # Issue A-ABORT PDU
        assert scp.handlers[0].received[1] == (
            b"\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00"
        )

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt14(self):
        """Test Sta5 + Evt14."""
        # Sta5 + Evt14 -> <ignore> -> Sta5
        # Evt14: Receive A-RELEASE (rsp) primitive from <local user>
        commands = [("recv", None), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_release(True))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:2] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
        ]
        assert self.fsm._transitions[:2] == ["Sta4", "Sta5"]
        assert self.fsm._events[:3] == ["Evt1", "Evt2", "Evt14"]

    def test_evt15(self):
        """Test Sta5 + Evt15."""
        # Sta5 + Evt15 -> AA-1 -> Sta13
        # Evt15: Receive A-ABORT (rq) primitive from <local user>
        # AA-1: Send A-ABORT PDU and restart ARTIM
        commands = [("recv", None), ("recv", None), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_abort())

        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:3] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt15", "AA-1"),
        ]
        assert self.fsm._transitions[:3] == ["Sta4", "Sta5", "Sta13"]
        assert self.fsm._events[:3] == ["Evt1", "Evt2", "Evt15"]

        # Issue A-ABORT PDU
        assert scp.handlers[0].received[1] == (
            b"\x07\x00\x00\x00\x00\x04\x00\x00\x00\x00"
        )

    def test_evt16(self):
        """Test Sta5 + Evt16."""
        # Sta5 + Evt16 -> AA-3 -> Sta1
        # Evt16: Receive A-ABORT PDU from <remote>
        # AA-3: If service user initiated:
        #           Issue A-ABORT primitive and close transport
        #       Otherwise
        #           Issue A-P-ABORT primitive and close transport
        commands = [("recv", None), ("send", a_abort), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:3] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt16", "AA-3"),
        ]
        assert self.fsm._transitions[:3] == ["Sta4", "Sta5", "Sta1"]
        assert self.fsm._events[:3] == ["Evt1", "Evt2", "Evt16"]

    def test_evt17(self):
        """Test Sta5 + Evt17."""
        # Sta1 + Evt17 -> AA-4 -> Sta1
        # Evt17: Receive TRANSPORT_CLOSED from <transport service>
        # AA-4: Issue A-P-ABORT primitive
        commands = [("recv", None), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.shutdown()

        time.sleep(0.5)

        assert self.fsm._changes[:3] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt17", "AA-4"),
        ]
        assert self.fsm._transitions[:3] == ["Sta4", "Sta5", "Sta1"]
        assert self.fsm._events[:3] == ["Evt1", "Evt2", "Evt17"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt18(self):
        """Test Sta5 + Evt18."""
        # Sta5 + Evt18 -> <ignore> -> Sta5
        # Evt18: ARTIM timer expired from <local service>
        commands = [("recv", None), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.artim_timer.timeout = 0.05
        self.assoc.dul.artim_timer.start()

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:3] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
        ]
        assert self.fsm._transitions[:3] == ["Sta4", "Sta5"]
        assert self.fsm._events[:3] == ["Evt1", "Evt2", "Evt18"]

    def test_evt19(self):
        """Test Sta5 + Evt19."""
        # Sta5 + Evt19 -> AA-8 -> Sta13
        # Evt19: Received unrecognised or invalid PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("recv", None),
            ("send", b"\x08\x00\x00\x00\x00\x00"),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:3] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt19", "AA-8"),
        ]
        assert self.fsm._transitions[:3] == ["Sta4", "Sta5", "Sta13"]
        assert self.fsm._events[:3] == ["Evt1", "Evt2", "Evt19"]
        # Issue A-ABORT PDU
        assert scp.handlers[0].received[1] == (
            b"\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00"
        )


class TestState06(TestStateBase):
    """Tests for State 06: Association established and ready for data."""

    def move_to_state(self, assoc, scp):
        assoc.start()
        scp.step()
        scp.step()
        self.wait_on_state(assoc.dul.state_machine, "Sta6")

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt01(self):
        """Test Sta6 + Evt1."""
        # Sta6 + Evt1 -> <ignore> -> Sta6
        # Evt1: A-ASSOCIATE (rq) primitive from <local user>
        commands = [("recv", None), ("send", a_associate_ac), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_associate("request"))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:3] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
        ]
        assert self.fsm._transitions[:3] == ["Sta4", "Sta5", "Sta6"]
        assert self.fsm._events[:4] == ["Evt1", "Evt2", "Evt3", "Evt1"]

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
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("send", a_associate_ac),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:4] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt3", "AA-8"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta13"]
        assert self.fsm._events[:4] == ["Evt1", "Evt2", "Evt3", "Evt3"]

        # Issue A-ABORT PDU
        assert scp.handlers[0].received[1] == (
            b"\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00"
        )

    def test_evt04(self):
        """Test Sta6 + Evt4."""
        # Sta6 + Evt4 -> AA-8 -> Sta13
        # Evt4: Receive A-ASSOCIATE-RJ PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("send", a_associate_rj),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:4] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt4", "AA-8"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta13"]
        assert self.fsm._events[:4] == ["Evt1", "Evt2", "Evt3", "Evt4"]

        # Issue A-ABORT PDU
        assert scp.handlers[0].received[1] == (
            b"\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00"
        )

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
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("send", a_associate_rq),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:4] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt6", "AA-8"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta13"]
        assert self.fsm._events[:4] == ["Evt1", "Evt2", "Evt3", "Evt6"]

        # Issue A-ABORT PDU
        assert scp.handlers[0].received[1] == (
            b"\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00"
        )

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt07(self):
        """Test Sta6 + Evt7."""
        # Sta6 + Evt7 -> <ignore> -> Sta6
        # Evt7: Receive A-ASSOCIATE (accept) primitive from <local user>
        commands = [("recv", None), ("send", a_associate_ac), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_associate("accept"))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:3] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
        ]
        assert self.fsm._transitions[:3] == ["Sta4", "Sta5", "Sta6"]
        assert self.fsm._events[:4] == ["Evt1", "Evt2", "Evt3", "Evt7"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt08(self):
        """Test Sta6 + Evt8."""
        # Sta6 + Evt8 -> <ignore> -> Sta6
        # Evt8: Receive A-ASSOCIATE (reject) primitive from <local user>
        commands = [("recv", None), ("send", a_associate_ac), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_associate("reject"))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:3] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
        ]
        assert self.fsm._transitions[:3] == ["Sta4", "Sta5", "Sta6"]
        assert self.fsm._events[:4] == ["Evt1", "Evt2", "Evt3", "Evt8"]

    def test_evt09(self):
        """Test Sta6 + Evt9."""
        # Sta6 + Evt9 -> DT-1 -> Sta6
        # Evt9: Receive P-DATA primitive from <local user>
        # DT-1: Send P-DATA-TD PDU
        commands = [("recv", None), ("send", a_associate_ac), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_pdata())

        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:4] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt9", "DT-1"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta6"]
        assert self.fsm._events[:4] == ["Evt1", "Evt2", "Evt3", "Evt9"]

    def test_evt10(self):
        """Test Sta6 + Evt10."""
        # Sta6 + Evt10 -> DT-2 -> Sta6
        # Evt10: Receive P-DATA-TF PDU from <remote>
        # DT-2: Send P-DATA primitive
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("send", p_data_tf),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:4] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt10", "DT-2"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta6"]
        assert self.fsm._events[:4] == ["Evt1", "Evt2", "Evt3", "Evt10"]

    def test_evt11(self):
        """Test Sta6 + Evt11."""
        # Sta6 + Evt11 -> AR-1 -> Sta7
        # Evt11: Receive A-RELEASE (rq) primitive from <local user>
        commands = [("recv", None), ("send", a_associate_ac), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_release(False))

        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:3] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
        ]
        assert self.fsm._transitions[:3] == ["Sta4", "Sta5", "Sta6"]
        assert self.fsm._events[:4] == ["Evt1", "Evt2", "Evt3", "Evt11"]

    def test_evt12(self):
        """Test Sta6 + Evt12."""
        # Sta6 + Evt12 -> AR-2 -> Sta8
        # Evt12: Receive A-RELEASE-RQ PDU from <remote>
        # AR-2: Issue A-RELEASE (rq) primitive
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("send", a_release_rq),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:4] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt12", "AR-2"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta8"]
        assert self.fsm._events[:4] == ["Evt1", "Evt2", "Evt3", "Evt12"]

    def test_evt13(self):
        """Test Sta6 + Evt13."""
        # Sta6 + Evt13 -> AA-8 -> Sta13
        # Evt13: Receive A-RELEASE-RP PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("send", a_release_rp),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:4] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt13", "AA-8"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta13"]
        assert self.fsm._events[:4] == ["Evt1", "Evt2", "Evt3", "Evt13"]

        # Issue A-ABORT PDU
        assert scp.handlers[0].received[1] == (
            b"\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00"
        )

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt14(self):
        """Test Sta6 + Evt14."""
        # Sta6 + Evt14 -> <ignore> -> Sta6
        # Evt14: Receive A-RELEASE (rsp) primitive from <local user>
        commands = [("recv", None), ("send", a_associate_ac), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_release(True))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:3] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
        ]
        assert self.fsm._transitions[:3] == ["Sta4", "Sta5", "Sta6"]
        assert self.fsm._events[:4] == ["Evt1", "Evt2", "Evt3", "Evt14"]

    def test_evt15(self):
        """Test Sta6 + Evt15."""
        # Sta6 + Evt15 -> AA-1 -> Sta13
        # Evt15: Receive A-ABORT (rq) primitive from <local user>
        # AA-1: Send A-ABORT PDU and start ARTIM
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.abort()

        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:4] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt15", "AA-1"),
        ]
        assert self.fsm._transitions[:3] == ["Sta4", "Sta5", "Sta6"]
        assert self.fsm._events[:4] == ["Evt1", "Evt2", "Evt3", "Evt15"]

        # Issue A-ABORT PDU
        assert scp.handlers[0].received[1] == (
            b"\x07\x00\x00\x00\x00\x04\x00\x00\x00\x00"
        )

    def test_evt16(self):
        """Test Sta6 + Evt16."""
        # Sta6 + Evt16 -> AA-3 -> Sta1
        # Evt16: Receive A-ABORT PDU from <remote>
        # AA-3: Issue A-ABORT or A-P-ABORT, and close connection
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("send", a_abort),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:4] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt16", "AA-3"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta1"]
        assert self.fsm._events[:4] == ["Evt1", "Evt2", "Evt3", "Evt16"]

    def test_evt17(self):
        """Test Sta6 + Evt17."""
        # Sta6 + Evt17 -> AA-4 -> Sta1
        # Evt17: Receive TRANSPORT_CLOSED from <transport service>
        # AA-4: Issue A-P-ABORT primitive
        commands = [("recv", None), ("send", a_associate_ac), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.shutdown()

        time.sleep(0.5)

        assert self.fsm._changes[:4] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt17", "AA-4"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta1"]
        assert self.fsm._events[:4] == ["Evt1", "Evt2", "Evt3", "Evt17"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt18(self):
        """Test Sta6 + Evt18."""
        # Sta6 + Evt18 -> <ignore> -> Sta6
        # Evt18: ARTIM timer expired from <local service>
        commands = [("recv", None), ("send", a_associate_ac), ("exit", None)]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.artim_timer.timeout = 0.05
        self.assoc.dul.artim_timer.start()

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:3] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
        ]
        assert self.fsm._transitions[:3] == ["Sta4", "Sta5", "Sta6"]
        assert self.fsm._events[:4] == ["Evt1", "Evt2", "Evt3", "Evt18"]

    def test_evt19(self):
        """Test Sta6 + Evt19."""
        # Sta6 + Evt19 -> AA-8 -> Sta13
        # Evt19: Received unrecognised or invalid PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("send", b"\x08\x00\x00\x00\x00\x00"),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:4] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt19", "AA-8"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta13"]
        assert self.fsm._events[:4] == ["Evt1", "Evt2", "Evt3", "Evt19"]

        # Issue A-ABORT PDU
        assert scp.handlers[0].received[1] == (
            b"\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00"
        )


class TestState07(TestStateBase):
    """Tests for State 07: Awaiting A-RELEASE-RP PDU."""

    def move_to_state(self, assoc, scp):
        assoc.start()
        scp.step()
        scp.step()
        self.wait_on_state(assoc.dul.state_machine, "Sta6")
        self.assoc.dul.send_pdu(self.get_release(False))
        scp.step()
        self.wait_on_state(assoc.dul.state_machine, "Sta7")

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt01(self):
        """Test Sta7 + Evt1."""
        # Sta7 + Evt1 -> <ignore> -> Sta7
        # Evt1: A-ASSOCIATE (rq) primitive from <local user>
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_associate("request"))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:4] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta7"]
        assert self.fsm._events[:5] == ["Evt1", "Evt2", "Evt3", "Evt11", "Evt1"]

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
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:5] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt3", "AA-8"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta7"]
        assert self.fsm._events[:5] == ["Evt1", "Evt2", "Evt3", "Evt11", "Evt3"]

        # Issue A-ASSOCIATE, A-RELEASE, A-ABORT PDU
        assert scp.handlers[0].received[2] == (
            b"\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00"
        )

    def test_evt04(self):
        """Test Sta7 + Evt4."""
        # Sta7 + Evt4 -> AA-8 -> Sta13
        # Evt4: Receive A-ASSOCIATE-RJ PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("send", a_associate_rj),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:5] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt4", "AA-8"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta7"]
        assert self.fsm._events[:5] == ["Evt1", "Evt2", "Evt3", "Evt11", "Evt4"]

        # Issue A-ASSOCIATE, A-RELEASE, A-ABORT PDU
        assert scp.handlers[0].received[2] == (
            b"\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00"
        )

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
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("send", a_associate_rq),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:5] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt6", "AA-8"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta7"]
        assert self.fsm._events[:5] == ["Evt1", "Evt2", "Evt3", "Evt11", "Evt6"]

        # Issue A-ASSOCIATE, A-RELEASE, A-ABORT PDU
        assert scp.handlers[0].received[2] == (
            b"\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00"
        )

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt07(self):
        """Test Sta7 + Evt7."""
        # Sta7 + Evt7 -> <ignore> -> Sta7
        # Evt7: Receive A-ASSOCIATE (accept) primitive from <local user>
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_associate("accept"))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:4] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta7"]
        assert self.fsm._events[:5] == ["Evt1", "Evt2", "Evt3", "Evt11", "Evt7"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt08(self):
        """Test Sta7 + Evt8."""
        # Sta7 + Evt8 -> <ignore> -> Sta7
        # Evt8: Receive A-ASSOCIATE (reject) primitive from <local user>
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_associate("reject"))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:4] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta7"]
        assert self.fsm._events[:5] == ["Evt1", "Evt2", "Evt3", "Evt11", "Evt8"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt09(self):
        """Test Sta7 + Evt9."""
        # Sta7 + Evt9 -> <ignore> -> Sta7
        # Evt9: Receive P-DATA primitive from <local user>
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_pdata())

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:4] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta7"]
        assert self.fsm._events[:5] == ["Evt1", "Evt2", "Evt3", "Evt11", "Evt9"]

    def test_evt10(self):
        """Test Sta7 + Evt10."""
        # Sta7 + Evt10 -> AR-6 -> Sta7
        # Evt10: Receive P-DATA-TF PDU from <remote>
        # AR-6: Send P-DATA primitive
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("send", p_data_tf),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.shutdown()

        # primitive = self.assoc.dul.receive_pdu(wait=False)
        # assert isinstance(primitive, P_DATA)
        assert self.fsm._changes[:5] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt10", "AR-6"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta7"]
        assert self.fsm._events[:5] == ["Evt1", "Evt2", "Evt3", "Evt11", "Evt10"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt11(self):
        """Test Sta7 + Evt11."""
        # Sta7 + Evt11 -> <ignore> -> Sta7
        # Evt11: Receive A-RELEASE (rq) primitive from <local user>
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_release(False))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:4] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta7"]
        assert self.fsm._events[:5] == ["Evt1", "Evt2", "Evt3", "Evt11", "Evt11"]

    def test_evt12(self):
        """Test Sta7 + Evt12."""
        # Sta7 + Evt12 -> AR-8 -> Sta9 or Sta10
        # Evt12: Receive A-RELEASE-RQ PDU from <remote>
        # AR-8: Issue A-RELEASE (rq) - release collision
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("send", a_release_rq),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:5] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta7"]
        assert self.fsm._events[:5] == ["Evt1", "Evt2", "Evt3", "Evt11", "Evt12"]

    def test_evt13(self):
        """Test Sta7 + Evt13."""
        # Sta7 + Evt13 -> AR-3 -> Sta1
        # Evt13: Receive A-RELEASE-RP PDU from <remote>
        # AR-3: Issue A-RELEASE (rp) primitive and close connection
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("send", a_release_rp),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.shutdown()

        primitive = self.assoc.dul.receive_pdu(wait=False)
        assert isinstance(primitive, A_RELEASE)
        assert self.fsm._changes[:5] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt13", "AR-3"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta7"]
        assert self.fsm._events[:5] == ["Evt1", "Evt2", "Evt3", "Evt11", "Evt13"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt14(self):
        """Test Sta7 + Evt14."""
        # Sta7 + Evt14 -> <ignore> -> Sta7
        # Evt14: Receive A-RELEASE (rsp) primitive from <local user>
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_release(True))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:4] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta7"]
        assert self.fsm._events[:5] == ["Evt1", "Evt2", "Evt3", "Evt11", "Evt14"]

    def test_evt15(self):
        """Test Sta7 + Evt15."""
        # Sta7 + Evt15 -> AA-1 -> Sta13
        # Evt15: Receive A-ABORT (rq) primitive from <local user>
        # AA-1: Send A-ABORT PDU and start ARTIM
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_abort())

        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:5] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt15", "AA-1"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta7"]
        assert self.fsm._events[:5] == ["Evt1", "Evt2", "Evt3", "Evt11", "Evt15"]

    def test_evt16(self):
        """Test Sta7 + Evt16."""
        # Sta7 + Evt16 -> AA-3 -> Sta1
        # Evt16: Receive A-ABORT PDU from <remote>
        # AA-3: Issue A-ABORT or A-P-ABORT and close connection
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("send", a_abort),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:5] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt16", "AA-3"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta7"]
        assert self.fsm._events[:5] == ["Evt1", "Evt2", "Evt3", "Evt11", "Evt16"]

    def test_evt17(self):
        """Test Sta7 + Evt17."""
        # Sta7 + Evt17 -> AA-4 -> Sta1
        # Evt17: Receive TRANSPORT_CLOSED from <transport service>
        # AA-4: Issue A-P-ABORT primitive
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.shutdown()

        time.sleep(0.5)

        assert self.fsm._changes[:5] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt17", "AA-4"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta7"]
        assert self.fsm._events[:5] == ["Evt1", "Evt2", "Evt3", "Evt11", "Evt17"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt18(self):
        """Test Sta7 + Evt18."""
        # Sta7 + Evt18 -> <ignore> -> Sta7
        # Evt18: ARTIM timer expired from <local service>
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.artim_timer.timeout = 0.05
        self.assoc.dul.artim_timer.start()

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:4] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
        ]
        assert self.fsm._transitions[:3] == ["Sta4", "Sta5", "Sta6"]
        assert self.fsm._events[:5] == ["Evt1", "Evt2", "Evt3", "Evt11", "Evt18"]

    def test_evt19(self):
        """Test Sta7 + Evt19."""
        # Sta7 + Evt19 -> AA-8 -> Sta13
        # Evt19: Received unrecognised or invalid PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("send", b"\x08\x00\x00\x00\x00\x00"),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:5] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt19", "AA-8"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta7"]
        assert self.fsm._events[:5] == ["Evt1", "Evt2", "Evt3", "Evt11", "Evt19"]

        # Issue A-ASSOCIATE, A-RELEASE, A-ABORT PDU
        assert scp.handlers[0].received[2] == (
            b"\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00"
        )


class TestState08(TestStateBase):
    """Tests for State 08: Awaiting A-RELEASE (rp) primitive."""

    def move_to_state(self, assoc, scp):
        def is_release_requested():
            """Override ACSE.is_release_requested."""
            return False

        assoc.acse.is_release_requested = is_release_requested

        assoc.start()
        scp.step()
        scp.step()
        self.wait_on_state(assoc.dul.state_machine, "Sta6")
        scp.step()
        self.wait_on_state(assoc.dul.state_machine, "Sta8")

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt01(self):
        """Test Sta8 + Evt1."""
        # Sta8 + Evt1 -> <ignore> -> Sta8
        # Evt1: A-ASSOCIATE (rq) primitive from <local user>
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("send", a_release_rq),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_associate("request"))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:4] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt12", "AR-2"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta8"]
        assert self.fsm._events[:5] == ["Evt1", "Evt2", "Evt3", "Evt12", "Evt1"]

    @pytest.mark.skip()
    def test_evt02(self):
        """Test Sta8 + Evt2."""
        # Sta8 + Evt2 -> <ignore> -> Sta8
        # Evt2: Receive TRANSPORT_OPEN from <transport service>
        pass

    def test_evt03(self):
        """Test Sta8 + Evt3."""
        # Sta8 + Evt3 -> AA-8 -> Sta13
        # Evt3: Receive A-ASSOCIATE-AC PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("send", a_release_rq),
            ("send", a_associate_ac),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:5] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt12", "AR-2"),
            ("Sta8", "Evt3", "AA-8"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta8"]
        assert self.fsm._events[:5] == ["Evt1", "Evt2", "Evt3", "Evt12", "Evt3"]

    def test_evt04(self):
        """Test Sta8 + Evt4."""
        # Sta8 + Evt4 -> AA-8 -> Sta13
        # Evt4: Receive A-ASSOCIATE-RJ PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("send", a_release_rq),
            ("send", a_associate_rj),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:5] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt12", "AR-2"),
            ("Sta8", "Evt4", "AA-8"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta8"]
        assert self.fsm._events[:5] == ["Evt1", "Evt2", "Evt3", "Evt12", "Evt4"]

    @pytest.mark.skip()
    def test_evt05(self):
        """Test Sta8 + Evt5."""
        # Sta8 + Evt5 -> <ignore> -> Sta8
        # Evt5: Receive TRANSPORT_INDICATION from <transport service>
        pass

    def test_evt06(self):
        """Test Sta8 + Evt6."""
        # Sta8 + Evt6 -> AA-8 -> Sta13
        # Evt6: Receive A-ASSOCIATE-RQ PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("send", a_release_rq),
            ("send", a_associate_rq),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:5] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt12", "AR-2"),
            ("Sta8", "Evt6", "AA-8"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta8"]
        assert self.fsm._events[:5] == ["Evt1", "Evt2", "Evt3", "Evt12", "Evt6"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt07(self):
        """Test Sta8 + Evt7."""
        # Sta8 + Evt7 -> <ignore> -> Sta8
        # Evt7: Receive A-ASSOCIATE (accept) primitive from <local user>
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("send", a_release_rq),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_associate("accept"))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:4] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt12", "AR-2"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta8"]
        assert self.fsm._events[:5] == ["Evt1", "Evt2", "Evt3", "Evt12", "Evt7"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt08(self):
        """Test Sta8 + Evt8."""
        # Sta8 + Evt8 -> <ignore> -> Sta8
        # Evt8: Receive A-ASSOCIATE (reject) primitive from <local user>
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("send", a_release_rq),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_associate("reject"))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:4] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt12", "AR-2"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta8"]
        assert self.fsm._events[:5] == ["Evt1", "Evt2", "Evt3", "Evt12", "Evt8"]

    def test_evt09(self):
        """Test Sta8 + Evt9."""
        # Sta8 + Evt9 -> AR-7 -> Sta8
        # Evt9: Receive P-DATA primitive from <local user>
        # AR-7: Send P-DATA-TF PDU to <remote>
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("send", a_release_rq),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_pdata())

        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:4] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt12", "AR-2"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta8"]
        assert self.fsm._events[:5] == ["Evt1", "Evt2", "Evt3", "Evt12", "Evt9"]

    def test_evt10(self):
        """Test Sta8 + Evt10."""
        # Sta8 + Evt10 -> AA-8 -> Sta13
        # Evt10: Receive P-DATA-TF PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("send", a_release_rq),
            ("send", p_data_tf),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:5] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt12", "AR-2"),
            ("Sta8", "Evt10", "AA-8"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta8"]
        assert self.fsm._events[:5] == ["Evt1", "Evt2", "Evt3", "Evt12", "Evt10"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt11(self):
        """Test Sta8 + Evt11."""
        # Sta8 + Evt11 -> <ignore> -> Sta8
        # Evt11: Receive A-RELEASE (rq) primitive from <local user>
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("send", a_release_rq),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_release(False))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:4] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt12", "AR-2"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta8"]
        assert self.fsm._events[:5] == ["Evt1", "Evt2", "Evt3", "Evt12", "Evt11"]

    def test_evt12(self):
        """Test Sta8 + Evt12."""
        # Sta8 + Evt12 -> AA-8 -> Sta13
        # Evt12: Receive A-RELEASE-RQ PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("recv", None),  # get a_assoc_rq
            ("send", a_associate_ac),
            ("send", a_release_rq),
            ("send", a_release_rq),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:5] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt12", "AR-2"),
            ("Sta8", "Evt12", "AA-8"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta8"]
        assert self.fsm._events[:5] == ["Evt1", "Evt2", "Evt3", "Evt12", "Evt12"]

    def test_evt13(self):
        """Test Sta8 + Evt13."""
        # Sta8 + Evt13 -> AA-8 -> Sta13
        # Evt13: Receive A-RELEASE-RP PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("send", a_release_rq),
            ("send", a_release_rp),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:5] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt12", "AR-2"),
            ("Sta8", "Evt13", "AA-8"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta8"]
        assert self.fsm._events[:5] == ["Evt1", "Evt2", "Evt3", "Evt12", "Evt13"]

    def test_evt14(self):
        """Test Sta8 + Evt14."""
        # Sta8 + Evt14 -> AR-4 -> Sta13
        # Evt14: Receive A-RELEASE (rsp) primitive from <local user>
        # AR-4: Send A-RELEASE-RP PDU and start ARTIM
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("send", a_release_rq),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_release(True))

        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:4] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt12", "AR-2"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta8"]
        assert self.fsm._events[:5] == ["Evt1", "Evt2", "Evt3", "Evt12", "Evt14"]

    def test_evt15(self):
        """Test Sta8 + Evt15."""
        # Sta8 + Evt15 -> AA-1 -> Sta13
        # Evt15: Receive A-ABORT (rq) primitive from <local user>
        # AA-1: Send A-ABORT PDU and start ARTIM
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("send", a_release_rq),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_abort())

        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:5] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt12", "AR-2"),
            ("Sta8", "Evt15", "AA-1"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta8"]
        assert self.fsm._events[:5] == ["Evt1", "Evt2", "Evt3", "Evt12", "Evt15"]

    def test_evt16(self):
        """Test Sta8 + Evt16."""
        # Sta8 + Evt16 -> AA-3 -> Sta13
        # Evt16: Receive A-ABORT PDU from <remote>
        # AA-3: Issue A-ABORT or A-P-ABORT and close connection
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("send", a_release_rq),
            ("send", a_abort),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:5] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt12", "AR-2"),
            ("Sta8", "Evt16", "AA-3"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta8"]
        assert self.fsm._events[:5] == ["Evt1", "Evt2", "Evt3", "Evt12", "Evt16"]

    def test_evt17(self):
        """Test Sta8 + Evt17."""
        # Sta8 + Evt17 -> AA-4 -> Sta1
        # Evt17: Receive TRANSPORT_CLOSED from <transport service>
        # AA-4: Issue A-P-ABORT
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("send", a_release_rq),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.shutdown()

        time.sleep(0.5)

        assert self.fsm._changes[:5] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt12", "AR-2"),
            ("Sta8", "Evt17", "AA-4"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta8"]
        assert self.fsm._events[:5] == ["Evt1", "Evt2", "Evt3", "Evt12", "Evt17"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt18(self):
        """Test Sta8 + Evt18."""
        # Sta8 + Evt18 -> <ignore> -> Sta1
        # Evt18: ARTIM timer expired from <local service>
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("send", a_release_rq),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.artim_timer.timeout = 0.05
        self.assoc.dul.artim_timer.start()

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:4] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt12", "AR-2"),
        ]
        assert self.fsm._transitions[:3] == ["Sta4", "Sta5", "Sta6"]
        assert self.fsm._events[:5] == ["Evt1", "Evt2", "Evt3", "Evt12", "Evt18"]

    def test_evt19(self):
        """Test Sta8 + Evt19."""
        # Sta8 + Evt19 -> AA-8 -> Sta13
        # Evt19: Received unrecognised or invalid PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("send", a_release_rq),
            ("send", b"\x08\x00\x00\x00\x00\x00"),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:5] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt12", "AR-2"),
            ("Sta8", "Evt19", "AA-8"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta8"]
        assert self.fsm._events[:5] == ["Evt1", "Evt2", "Evt3", "Evt12", "Evt19"]


class TestState09(TestStateBase):
    """Tests for State 09: Release collision req - awaiting A-RELEASE (rp)."""

    def move_to_state(self, assoc, scp):
        def is_release_requested():
            """Override ACSE.is_release_requested."""
            return False

        assoc.acse.is_release_requested = is_release_requested

        assoc.start()
        scp.step()
        scp.step()
        self.wait_on_state(assoc.dul.state_machine, "Sta6")
        assoc.dul.send_pdu(self.get_release(False))
        scp.step()
        scp.step()
        self.wait_on_state(assoc.dul.state_machine, "Sta9")

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt01(self):
        """Test Sta9 + Evt1."""
        # Sta9 + Evt1 -> <ignore> -> Sta9
        # Evt1: A-ASSOCIATE (rq) primitive from <local user>
        commands = [
            ("recv", None),  # recv a-associate-rq
            ("send", a_associate_ac),
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_associate("request"))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:5] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
        ]
        assert self.fsm._transitions[:5] == ["Sta4", "Sta5", "Sta6", "Sta7", "Sta9"]
        assert self.fsm._events[:6] == [
            "Evt1",
            "Evt2",
            "Evt3",
            "Evt11",
            "Evt12",
            "Evt1",
        ]

    @pytest.mark.skip()
    def test_evt02(self):
        """Test Sta9 + Evt2."""
        # Sta9 + Evt2 -> <ignore> -> Sta9
        # Evt2: Receive TRANSPORT_OPEN from <transport service>
        pass

    def test_evt03(self):
        """Test Sta9 + Evt3."""
        # Sta9 + Evt3 -> AA-8 -> Sta13
        # Evt3: Receive A-ASSOCIATE-AC PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("recv", None),  # recv a-associate-rq
            ("send", a_associate_ac),
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("send", a_associate_ac),  # trigger event
            ("recv", None),  # recv a-abort
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:6] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta9", "Evt3", "AA-8"),
        ]
        assert self.fsm._transitions[:5] == ["Sta4", "Sta5", "Sta6", "Sta7", "Sta9"]
        assert self.fsm._events[:6] == [
            "Evt1",
            "Evt2",
            "Evt3",
            "Evt11",
            "Evt12",
            "Evt3",
        ]
        assert scp.handlers[0].received[2] == (
            b"\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00"
        )

    def test_evt04(self):
        """Test Sta9 + Evt4."""
        # Sta9 + Evt4 -> AA-8 -> Sta13
        # Evt4: Receive A-ASSOCIATE-RJ PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("recv", None),  # recv a-associate-rq
            ("send", a_associate_ac),
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),
            ("send", a_associate_rj),
            ("recv", None),  # recv a-abort
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:6] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta9", "Evt4", "AA-8"),
        ]
        assert self.fsm._transitions[:5] == ["Sta4", "Sta5", "Sta6", "Sta7", "Sta9"]
        assert self.fsm._events[:6] == [
            "Evt1",
            "Evt2",
            "Evt3",
            "Evt11",
            "Evt12",
            "Evt4",
        ]
        assert scp.handlers[0].received[2] == (
            b"\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00"
        )

    @pytest.mark.skip()
    def test_evt05(self):
        """Test Sta9 + Evt5."""
        # Sta9 + Evt5 -> <ignore> -> Sta9
        # Evt5: Receive TRANSPORT_INDICATION from <transport service>
        pass

    def test_evt06(self):
        """Test Sta9 + Evt6."""
        # Sta9 + Evt6 -> AA-8 -> Sta13
        # Evt6: Receive A-ASSOCIATE-RQ PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("recv", None),  # recv a-associate-rq
            ("send", a_associate_ac),
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("send", a_associate_rq),  # trigger event
            ("recv", None),  # recv a-abort
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:6] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta9", "Evt6", "AA-8"),
        ]
        assert self.fsm._transitions[:5] == ["Sta4", "Sta5", "Sta6", "Sta7", "Sta9"]
        assert self.fsm._events[:6] == [
            "Evt1",
            "Evt2",
            "Evt3",
            "Evt11",
            "Evt12",
            "Evt6",
        ]
        assert scp.handlers[0].received[2] == (
            b"\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00"
        )

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt07(self):
        """Test Sta9 + Evt7."""
        # Sta9 + Evt7 -> <ignore> -> Sta9
        # Evt7: Receive A-ASSOCIATE (accept) primitive from <local user>
        commands = [
            ("recv", None),  # recv a-associate-rq
            ("send", a_associate_ac),
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_associate("accept"))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:5] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
        ]
        assert self.fsm._transitions[:5] == ["Sta4", "Sta5", "Sta6", "Sta7", "Sta9"]
        assert self.fsm._events[:6] == [
            "Evt1",
            "Evt2",
            "Evt3",
            "Evt11",
            "Evt12",
            "Evt7",
        ]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt08(self):
        """Test Sta9 + Evt8."""
        # Sta9 + Evt8 -> <ignore> -> Sta9
        # Evt8: Receive A-ASSOCIATE (reject) primitive from <local user>
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("send", a_release_rq),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_associate("reject"))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:5] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
        ]
        assert self.fsm._transitions[:5] == ["Sta4", "Sta5", "Sta6", "Sta7", "Sta9"]
        assert self.fsm._events[:6] == [
            "Evt1",
            "Evt2",
            "Evt3",
            "Evt11",
            "Evt12",
            "Evt8",
        ]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt09(self):
        """Test Sta9 + Evt9."""
        # Sta9 + Evt9 -> <ignore> -> Sta9
        # Evt9: Receive P-DATA primitive from <local user>
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("send", a_release_rq),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_pdata())

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:5] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
        ]
        assert self.fsm._transitions[:5] == ["Sta4", "Sta5", "Sta6", "Sta7", "Sta9"]
        assert self.fsm._events[:6] == [
            "Evt1",
            "Evt2",
            "Evt3",
            "Evt11",
            "Evt12",
            "Evt9",
        ]

    def test_evt10(self):
        """Test Sta9 + Evt10."""
        # Sta9 + Evt10 -> AA-8 -> Sta13
        # Evt10: Receive P-DATA-TF PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("recv", None),  # recv a-associate-rq
            ("send", a_associate_ac),
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("send", p_data_tf),  # trigger event
            ("recv", None),  # recv a-abort
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:6] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta9", "Evt10", "AA-8"),
        ]
        assert self.fsm._transitions[:5] == ["Sta4", "Sta5", "Sta6", "Sta7", "Sta9"]
        assert self.fsm._events[:6] == [
            "Evt1",
            "Evt2",
            "Evt3",
            "Evt11",
            "Evt12",
            "Evt10",
        ]
        assert scp.handlers[0].received[2] == (
            b"\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00"
        )

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt11(self):
        """Test Sta9 + Evt11."""
        # Sta9 + Evt11 -> <ignore> -> Sta9
        # Evt11: Receive A-RELEASE (rq) primitive from <local user>
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("send", a_release_rq),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_release(False))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:5] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
        ]
        assert self.fsm._transitions[:5] == ["Sta4", "Sta5", "Sta6", "Sta7", "Sta9"]
        assert self.fsm._events[:6] == [
            "Evt1",
            "Evt2",
            "Evt3",
            "Evt11",
            "Evt12",
            "Evt11",
        ]

    def test_evt12(self):
        """Test Sta9 + Evt12."""
        # Sta9 + Evt12 -> AA-8 -> Sta13
        # Evt12: Receive A-RELEASE-RQ PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("recv", None),  # recv a-associate-rq
            ("send", a_associate_ac),
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("send", a_release_rq),  # trigger event
            ("recv", None),  # recv a-abort
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:6] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta9", "Evt12", "AA-8"),
        ]
        assert self.fsm._transitions[:5] == ["Sta4", "Sta5", "Sta6", "Sta7", "Sta9"]
        assert self.fsm._events[:6] == [
            "Evt1",
            "Evt2",
            "Evt3",
            "Evt11",
            "Evt12",
            "Evt12",
        ]
        assert scp.handlers[0].received[2] == (
            b"\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00"
        )

    def test_evt13(self):
        """Test Sta9 + Evt13."""
        # Sta9 + Evt13 -> AA-8 -> Sta13
        # Evt13: Receive A-RELEASE-RP PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("recv", None),  # recv a-associate-rq
            ("send", a_associate_ac),
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("send", a_release_rp),  # trigger event
            ("recv", None),  # recv a-abort
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:6] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta9", "Evt13", "AA-8"),
        ]
        assert self.fsm._transitions[:5] == ["Sta4", "Sta5", "Sta6", "Sta7", "Sta9"]
        assert self.fsm._events[:6] == [
            "Evt1",
            "Evt2",
            "Evt3",
            "Evt11",
            "Evt12",
            "Evt13",
        ]
        assert scp.handlers[0].received[2] == (
            b"\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00"
        )

    def test_evt14(self):
        """Test Sta9 + Evt14."""
        # Sta9 + Evt14 -> AR-9 -> Sta11
        # Evt14: Receive A-RELEASE (rsp) primitive from <local user>
        # AR-9: Send A-RELEASE-RP PDU to <remote>
        commands = [
            ("recv", None),  # recv a-associate-rq
            ("send", a_associate_ac),
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),
            ("recv", None),  # recv a-release-rp
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_release(True))

        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:5] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
        ]
        assert self.fsm._transitions[:5] == ["Sta4", "Sta5", "Sta6", "Sta7", "Sta9"]
        assert self.fsm._events[:6] == [
            "Evt1",
            "Evt2",
            "Evt3",
            "Evt11",
            "Evt12",
            "Evt14",
        ]
        assert scp.handlers[0].received[2] == (
            b"\x06\x00\x00\x00\x00\x04\x00\x00\x00\x00"
        )

    def test_evt15(self):
        """Test Sta9 + Evt15."""
        # Sta9 + Evt15 -> AA-1 -> Sta13
        # Evt15: Receive A-ABORT (rq) primitive from <local user>
        # AA-1: Send A-ABORT PDU to <remote>, start ARTIM
        commands = [
            ("recv", None),  # recv a-associate-rq
            ("send", a_associate_ac),
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("recv", None),  # recv a-abort
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_abort())

        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:6] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta9", "Evt15", "AA-1"),
        ]
        assert self.fsm._transitions[:5] == ["Sta4", "Sta5", "Sta6", "Sta7", "Sta9"]
        assert self.fsm._events[:6] == [
            "Evt1",
            "Evt2",
            "Evt3",
            "Evt11",
            "Evt12",
            "Evt15",
        ]
        assert scp.handlers[0].received[2] == (
            b"\x07\x00\x00\x00\x00\x04\x00\x00\x00\x00"
        )

    def test_evt16(self):
        """Test Sta9 + Evt16."""
        # Sta9 + Evt16 -> AA-3 -> Sta1
        # Evt16: Receive A-ABORT PDU from <remote>
        # AA-3: Issue A-ABORT or A-P-ABORT primitive, close connection
        commands = [
            ("recv", None),  # recv a-associate-rq
            ("send", a_associate_ac),
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("send", a_abort),  # trigger event
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:6] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta9", "Evt16", "AA-3"),
        ]
        assert self.fsm._transitions[:5] == ["Sta4", "Sta5", "Sta6", "Sta7", "Sta9"]
        assert self.fsm._events[:6] == [
            "Evt1",
            "Evt2",
            "Evt3",
            "Evt11",
            "Evt12",
            "Evt16",
        ]

    def test_evt17(self):
        """Test Sta9 + Evt17."""
        # Sta9 + Evt17 -> AA-4 -> Sta1
        # Evt17: Receive TRANSPORT_CLOSED from <transport service>
        # AA-4: Issue A-P-ABORT primitive
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("send", a_release_rq),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.shutdown()

        time.sleep(0.5)

        assert self.fsm._changes[:6] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta9", "Evt17", "AA-4"),
        ]
        assert self.fsm._transitions[:5] == ["Sta4", "Sta5", "Sta6", "Sta7", "Sta9"]
        assert self.fsm._events[:6] == [
            "Evt1",
            "Evt2",
            "Evt3",
            "Evt11",
            "Evt12",
            "Evt17",
        ]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt18(self):
        """Test Sta9 + Evt18."""
        # Sta9 + Evt18 -> <ignore> -> Sta9
        # Evt18: ARTIM timer expired from <local service>
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("send", a_release_rq),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.artim_timer.timeout = 0.05
        self.assoc.dul.artim_timer.start()

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:5] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
        ]
        assert self.fsm._transitions[:4] == ["Sta4", "Sta5", "Sta6", "Sta7"]
        assert self.fsm._events[:6] == [
            "Evt1",
            "Evt2",
            "Evt3",
            "Evt11",
            "Evt12",
            "Evt18",
        ]

    def test_evt19(self):
        """Test Sta9 + Evt19."""
        # Sta9 + Evt19 -> AA-8 -> Sta13
        # Evt19: Received unrecognised or invalid PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("recv", None),  # recv a-associate-rq
            ("send", a_associate_ac),
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("send", b"\x08\x00\x00\x00\x00\x00"),  # trigger event
            ("recv", None),  # recv a-abort
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:6] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta9", "Evt19", "AA-8"),
        ]
        assert self.fsm._transitions[:5] == ["Sta4", "Sta5", "Sta6", "Sta7", "Sta9"]
        assert self.fsm._events[:6] == [
            "Evt1",
            "Evt2",
            "Evt3",
            "Evt11",
            "Evt12",
            "Evt19",
        ]
        assert scp.handlers[0].received[2] == (
            b"\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00"
        )


class TestState10(TestStateBase):
    """Tests for State 10: Release collision acc - awaiting A-RELEASE-RP ."""

    def move_to_state(self, assoc, scp):
        def is_release_requested():
            """Override ACSE.is_release_requested."""
            return False

        assoc.acse.is_release_requested = is_release_requested

        assoc.start()
        scp.step()
        scp.step()
        self.wait_on_state(assoc.dul.state_machine, "Sta6")
        assoc.dul.send_pdu(self.get_release(False))
        scp.step()
        scp.step()
        self.wait_on_state(assoc.dul.state_machine, "Sta10")

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt01(self):
        """Test Sta10 + Evt1."""
        # Sta10 + Evt1 -> <ignore> -> Sta10
        # Evt1: A-ASSOCIATE (rq) primitive from <local user>
        commands = [
            ("send", a_associate_rq),
            ("recv", None),  # recv a-associate-ac
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        assoc.dul.send_pdu(self.get_associate("request"))

        while assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert fsm._transitions[:5] == ["Sta2", "Sta3", "Sta6", "Sta7", "Sta10"]
        assert fsm._changes[:5] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt7", "AE-7"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
        ]
        assert fsm._events[:6] == ["Evt5", "Evt6", "Evt7", "Evt11", "Evt12", "Evt1"]

    @pytest.mark.skip()
    def test_evt02(self):
        """Test Sta10 + Evt2."""
        # Sta10 + Evt2 -> <ignore> -> Sta10
        # Evt2: Receive TRANSPORT_OPEN from <transport service>
        pass

    def test_evt03(self):
        """Test Sta10 + Evt3."""
        # Sta10 + Evt3 -> AA-8 -> Sta13
        # Evt3: Receive A-ASSOCIATE-AC PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("send", a_associate_rq),
            ("recv", None),  # recv a-associate-rq
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("send", a_associate_ac),  # trigger event
            ("recv", None),  # recv a-abort
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert fsm._transitions[:5] == ["Sta2", "Sta3", "Sta6", "Sta7", "Sta10"]
        assert fsm._changes[:6] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt7", "AE-7"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta10", "Evt3", "AA-8"),
        ]
        assert fsm._events[:6] == ["Evt5", "Evt6", "Evt7", "Evt11", "Evt12", "Evt3"]
        assert scp.handlers[0].received[2] == (
            b"\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00"
        )

    def test_evt04(self):
        """Test Sta10 + Evt4."""
        # Sta10 + Evt4 -> AA-8 -> Sta13
        # Evt4: Receive A-ASSOCIATE-RJ PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("send", a_associate_rq),
            ("recv", None),  # recv a-associate-rq
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("send", a_associate_rj),  # trigger event
            ("recv", None),  # recv a-abort
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert fsm._transitions[:5] == ["Sta2", "Sta3", "Sta6", "Sta7", "Sta10"]
        assert fsm._changes[:6] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt7", "AE-7"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta10", "Evt4", "AA-8"),
        ]
        assert fsm._events[:6] == ["Evt5", "Evt6", "Evt7", "Evt11", "Evt12", "Evt4"]
        assert scp.handlers[0].received[2] == (
            b"\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00"
        )

    @pytest.mark.skip()
    def test_evt05(self):
        """Test Sta10 + Evt5."""
        # Sta10 + Evt5 -> <ignore> -> Sta10
        # Evt5: Receive TRANSPORT_INDICATION from <transport service>
        pass

    def test_evt06(self):
        """Test Sta10 + Evt6."""
        # Sta10 + Evt6 -> AA-8 -> Sta13
        # Evt6: Receive A-ASSOCIATE-RQ PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("send", a_associate_rq),
            ("recv", None),  # recv a-associate-rq
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("send", a_associate_rq),  # trigger event
            ("recv", None),  # recv a-abort
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert fsm._transitions[:5] == ["Sta2", "Sta3", "Sta6", "Sta7", "Sta10"]
        assert fsm._changes[:6] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt7", "AE-7"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta10", "Evt6", "AA-8"),
        ]
        assert fsm._events[:6] == ["Evt5", "Evt6", "Evt7", "Evt11", "Evt12", "Evt6"]
        assert scp.handlers[0].received[2] == (
            b"\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00"
        )

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt07(self):
        """Test Sta10 + Evt7."""
        # Sta10 + Evt7 -> <ignore> -> Sta10
        # Evt7: Receive A-ASSOCIATE (accept) primitive from <local user>
        commands = [
            ("send", a_associate_rq),
            ("recv", None),  # recv a-associate-rq
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        assoc.dul.send_pdu(self.get_associate("accept"))

        while assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert fsm._transitions[:5] == ["Sta2", "Sta3", "Sta6", "Sta7", "Sta10"]
        assert fsm._changes[:5] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt7", "AE-7"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
        ]
        assert fsm._events[:6] == ["Evt5", "Evt6", "Evt7", "Evt11", "Evt12", "Evt7"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt08(self):
        """Test Sta10 + Evt8."""
        # Sta10 + Evt8 -> <ignore> -> Sta10
        # Evt8: Receive A-ASSOCIATE (reject) primitive from <local user>
        commands = [
            ("send", a_associate_rq),
            ("recv", None),  # recv a-associate-rq
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        assoc.dul.send_pdu(self.get_associate("reject"))
        while assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert fsm._transitions[:5] == ["Sta2", "Sta3", "Sta6", "Sta7", "Sta10"]
        assert fsm._changes[:5] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt7", "AE-7"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
        ]
        assert fsm._events[:6] == ["Evt5", "Evt6", "Evt7", "Evt11", "Evt12", "Evt8"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt09(self):
        """Test Sta10 + Evt9."""
        # Sta10 + Evt9 -> <ignore> -> Sta10
        # Evt9: Receive P-DATA primitive from <local user>
        commands = [
            ("send", a_associate_rq),
            ("recv", None),  # recv a-associate-rq
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        assoc.dul.send_pdu(self.get_pdata())

        while assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert fsm._transitions[:5] == ["Sta2", "Sta3", "Sta6", "Sta7", "Sta10"]
        assert fsm._changes[:5] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt7", "AE-7"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
        ]
        assert fsm._events[:6] == ["Evt5", "Evt6", "Evt7", "Evt11", "Evt12", "Evt9"]

    def test_evt10(self):
        """Test Sta10 + Evt10."""
        # Sta10 + Evt10 -> AA-8 -> Sta13
        # Evt10: Receive P-DATA-TF PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("send", a_associate_rq),
            ("recv", None),  # recv a-associate-rq
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("send", p_data_tf),  # trigger event
            ("recv", None),  # recv a-abort
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert fsm._transitions[:5] == ["Sta2", "Sta3", "Sta6", "Sta7", "Sta10"]
        assert fsm._changes[:6] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt7", "AE-7"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta10", "Evt10", "AA-8"),
        ]
        assert fsm._events[:6] == ["Evt5", "Evt6", "Evt7", "Evt11", "Evt12", "Evt10"]
        assert scp.handlers[0].received[2] == (
            b"\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00"
        )

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt11(self):
        """Test Sta10 + Evt11."""
        # Sta10 + Evt11 -> <ignore> -> Sta10
        # Evt11: Receive A-RELEASE (rq) primitive from <local user>
        commands = [
            ("send", a_associate_rq),
            ("recv", None),  # recv a-associate-rq
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        assoc.dul.send_pdu(self.get_release(False))

        while assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert fsm._transitions[:5] == ["Sta2", "Sta3", "Sta6", "Sta7", "Sta10"]
        assert fsm._changes[:5] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt7", "AE-7"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
        ]
        assert fsm._events[:6] == ["Evt5", "Evt6", "Evt7", "Evt11", "Evt12", "Evt11"]

    def test_evt12(self):
        """Test Sta10 + Evt12."""
        # Sta10 + Evt12 -> AA-8 -> Sta13
        # Evt12: Receive A-RELEASE-RQ PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("send", a_associate_rq),
            ("recv", None),  # recv a-associate-rq
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("send", a_release_rq),  # trigger event
            ("recv", None),  # recv a-abort
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert fsm._transitions[:5] == ["Sta2", "Sta3", "Sta6", "Sta7", "Sta10"]
        assert fsm._changes[:6] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt7", "AE-7"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta10", "Evt12", "AA-8"),
        ]
        assert fsm._events[:6] == ["Evt5", "Evt6", "Evt7", "Evt11", "Evt12", "Evt12"]
        assert scp.handlers[0].received[2] == (
            b"\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00"
        )

    def test_evt13(self):
        """Test Sta10 + Evt13."""
        # Sta10 + Evt13 -> AR-10 -> Sta13
        # Evt13: Receive A-RELEASE-RP PDU from <remote>
        # AR-10: Issue A-RELEASE (rp) primitive
        commands = [
            ("send", a_associate_rq),
            ("recv", None),  # recv a-associate-rq
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("send", a_release_rp),  # trigger event
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        scp.step()
        scp.step()
        scp.shutdown()

        assert fsm._transitions[:5] == ["Sta2", "Sta3", "Sta6", "Sta7", "Sta10"]
        assert fsm._changes[:6] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt7", "AE-7"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta10", "Evt13", "AR-10"),
        ]
        assert fsm._events[:6] == ["Evt5", "Evt6", "Evt7", "Evt11", "Evt12", "Evt13"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt14(self):
        """Test Sta10 + Evt14."""
        # Sta10 + Evt14 -> <ignore> -> Sta10
        # Evt14: Receive A-RELEASE (rsp) primitive from <local user>
        commands = [
            ("send", a_associate_rq),
            ("recv", None),  # recv a-associate-rq
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        assoc.dul.send_pdu(self.get_release(True))

        while assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert fsm._transitions[:5] == ["Sta2", "Sta3", "Sta6", "Sta7", "Sta10"]
        assert fsm._changes[:5] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt7", "AE-7"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
        ]
        assert fsm._events[:6] == ["Evt5", "Evt6", "Evt7", "Evt11", "Evt12", "Evt14"]

    def test_evt15(self):
        """Test Sta10 + Evt15."""
        # Sta10 + Evt15 -> AA-1 -> Sta13
        # Evt15: Receive A-ABORT (rq) primitive from <local user>
        # AA-1: Send A-ABORT PDU to <remote>, start ARTIM
        commands = [
            ("send", a_associate_rq),
            ("recv", None),  # recv a-associate-rq
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("recv", None),  # recv a-abort
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        assoc.dul.send_pdu(self.get_abort())

        scp.step()
        scp.step()
        scp.shutdown()

        assert fsm._transitions[:5] == ["Sta2", "Sta3", "Sta6", "Sta7", "Sta10"]
        assert fsm._changes[:6] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt7", "AE-7"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta10", "Evt15", "AA-1"),
        ]
        assert fsm._events[:6] == ["Evt5", "Evt6", "Evt7", "Evt11", "Evt12", "Evt15"]
        assert scp.handlers[0].received[2] == (
            b"\x07\x00\x00\x00\x00\x04\x00\x00\x00\x00"
        )

    def test_evt16(self):
        """Test Sta10 + Evt16."""
        # Sta10 + Evt16 -> AA-3 -> Sta1
        # Evt16: Receive A-ABORT PDU from <remote>
        # AA-3: Issue A-ABORT or A-P-ABORT primitive, close connection
        commands = [
            ("send", a_associate_rq),
            ("recv", None),  # recv a-associate-rq
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("send", a_abort),  # trigger event
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        scp.step()
        scp.step()
        scp.shutdown()

        assert fsm._transitions[:5] == ["Sta2", "Sta3", "Sta6", "Sta7", "Sta10"]
        assert fsm._changes[:6] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt7", "AE-7"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta10", "Evt16", "AA-3"),
        ]
        assert fsm._events[:6] == ["Evt5", "Evt6", "Evt7", "Evt11", "Evt12", "Evt16"]

    def test_evt17(self):
        """Test Sta10 + Evt17."""
        # Sta10 + Evt17 -> AA-4 -> Sta1
        # Evt17: Receive TRANSPORT_CLOSED from <transport service>
        # AA-4: Issue A-P-ABORT primitive
        commands = [
            ("send", a_associate_rq),
            ("recv", None),  # recv a-associate-rq
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        scp.step()
        scp.shutdown()

        time.sleep(0.5)

        assert fsm._transitions[:5] == ["Sta2", "Sta3", "Sta6", "Sta7", "Sta10"]
        assert fsm._changes[:6] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt7", "AE-7"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta10", "Evt17", "AA-4"),
        ]
        assert fsm._events[:6] == ["Evt5", "Evt6", "Evt7", "Evt11", "Evt12", "Evt17"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt18(self):
        """Test Sta10 + Evt18."""
        # Sta10 + Evt18 -> <ignore> -> Sta10
        # Evt18: ARTIM timer expired from <local service>
        commands = [
            ("send", a_associate_rq),
            ("recv", None),  # recv a-associate-rq
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        assoc.dul.artim_timer.timeout = 0.05
        assoc.dul.artim_timer.start()

        while assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert fsm._transitions[:5] == ["Sta2", "Sta3", "Sta6", "Sta7", "Sta10"]
        assert fsm._changes[:5] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt7", "AE-7"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
        ]
        assert fsm._events[:6] == ["Evt5", "Evt6", "Evt7", "Evt11", "Evt12", "Evt18"]

    def test_evt19(self):
        """Test Sta10 + Evt19."""
        # Sta10 + Evt19 -> AA-8 -> Sta13
        # Evt19: Received unrecognised or invalid PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("send", a_associate_rq),
            ("recv", None),  # recv a-associate-rq
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("send", b"\x08\x00\x00\x00\x00\x00\x00\x00"),  # trigger event
            ("recv", a_abort),  # recv a-abort
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert fsm._transitions[:5] == ["Sta2", "Sta3", "Sta6", "Sta7", "Sta10"]
        assert fsm._changes[:6] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt7", "AE-7"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta10", "Evt19", "AA-8"),
        ]
        assert fsm._events[:6] == ["Evt5", "Evt6", "Evt7", "Evt11", "Evt12", "Evt19"]
        assert scp.handlers[0].received[2] == (
            b"\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00"
        )


class TestState11(TestStateBase):
    """Tests for State 11: Release collision req - awaiting A-RELEASE-RP PDU"""

    def move_to_state(self, assoc, scp):
        def is_release_requested():
            """Override ACSE.is_release_requested."""
            return False

        assoc.acse.is_release_requested = is_release_requested

        assoc.start()
        scp.step()
        scp.step()
        self.wait_on_state(assoc.dul.state_machine, "Sta6")
        assoc.dul.send_pdu(self.get_release(False))
        scp.step()
        scp.step()
        self.wait_on_state(assoc.dul.state_machine, "Sta9")
        assoc.dul.send_pdu(self.get_release(True))
        self.wait_on_state(assoc.dul.state_machine, "Sta11")

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt01(self):
        """Test Sta11 + Evt1."""
        # Sta11 + Evt1 -> <ignore> -> Sta11
        # Evt1: A-ASSOCIATE (rq) primitive from <local user>
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("send", a_release_rq),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)
        self.assoc.dul.send_pdu(self.get_associate("request"))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:6] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta9", "Evt14", "AR-9"),
        ]
        assert self.fsm._transitions[:6] == [
            "Sta4",
            "Sta5",
            "Sta6",
            "Sta7",
            "Sta9",
            "Sta11",
        ]
        assert self.fsm._events[:7] == [
            "Evt1",
            "Evt2",
            "Evt3",
            "Evt11",
            "Evt12",
            "Evt14",
            "Evt1",
        ]

    @pytest.mark.skip()
    def test_evt02(self):
        """Test Sta11 + Evt2."""
        # Sta11 + Evt2 -> <ignore> -> Sta11
        # Evt2: Receive TRANSPORT_OPEN from <transport service>
        pass

    def test_evt03(self):
        """Test Sta11 + Evt3."""
        # Sta11 + Evt3 -> AA-8 -> Sta13
        # Evt3: Receive A-ASSOCIATE-AC PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("send", a_release_rq),
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:7] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta9", "Evt14", "AR-9"),
            ("Sta11", "Evt3", "AA-8"),
        ]
        assert self.fsm._transitions[:6] == [
            "Sta4",
            "Sta5",
            "Sta6",
            "Sta7",
            "Sta9",
            "Sta11",
        ]
        assert self.fsm._events[:7] == [
            "Evt1",
            "Evt2",
            "Evt3",
            "Evt11",
            "Evt12",
            "Evt14",
            "Evt3",
        ]

    def test_evt04(self):
        """Test Sta11 + Evt4."""
        # Sta11 + Evt4 -> AA-8 -> Sta13
        # Evt4: Receive A-ASSOCIATE-RJ PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("send", a_release_rq),
            ("recv", None),
            ("send", a_associate_rj),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:7] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta9", "Evt14", "AR-9"),
            ("Sta11", "Evt4", "AA-8"),
        ]
        assert self.fsm._transitions[:6] == [
            "Sta4",
            "Sta5",
            "Sta6",
            "Sta7",
            "Sta9",
            "Sta11",
        ]
        assert self.fsm._events[:7] == [
            "Evt1",
            "Evt2",
            "Evt3",
            "Evt11",
            "Evt12",
            "Evt14",
            "Evt4",
        ]

    @pytest.mark.skip()
    def test_evt05(self):
        """Test Sta11 + Evt5."""
        # Sta11 + Evt5 -> <ignore> -> Sta11
        # Evt5: Receive TRANSPORT_INDICATION from <transport service>
        pass

    def test_evt06(self):
        """Test Sta11 + Evt6."""
        # Sta11 + Evt6 -> AA-8 -> Sta13
        # Evt6: Receive A-ASSOCIATE-RQ PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("send", a_release_rq),
            ("recv", None),
            ("send", a_associate_rq),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:7] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta9", "Evt14", "AR-9"),
            ("Sta11", "Evt6", "AA-8"),
        ]
        assert self.fsm._transitions[:6] == [
            "Sta4",
            "Sta5",
            "Sta6",
            "Sta7",
            "Sta9",
            "Sta11",
        ]
        assert self.fsm._events[:7] == [
            "Evt1",
            "Evt2",
            "Evt3",
            "Evt11",
            "Evt12",
            "Evt14",
            "Evt6",
        ]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt07(self):
        """Test Sta11 + Evt7."""
        # Sta11 + Evt7 -> <ignore> -> Sta11
        # Evt7: Receive A-ASSOCIATE (accept) primitive from <local user>
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("send", a_release_rq),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_associate("accept"))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:6] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta9", "Evt14", "AR-9"),
        ]
        assert self.fsm._transitions[:6] == [
            "Sta4",
            "Sta5",
            "Sta6",
            "Sta7",
            "Sta9",
            "Sta11",
        ]
        assert self.fsm._events[:7] == [
            "Evt1",
            "Evt2",
            "Evt3",
            "Evt11",
            "Evt12",
            "Evt14",
            "Evt7",
        ]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt08(self):
        """Test Sta11 + Evt8."""
        # Sta11 + Evt8 -> <ignore> -> Sta11
        # Evt8: Receive A-ASSOCIATE (reject) primitive from <local user>
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("send", a_release_rq),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_associate("reject"))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:6] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta9", "Evt14", "AR-9"),
        ]
        assert self.fsm._transitions[:6] == [
            "Sta4",
            "Sta5",
            "Sta6",
            "Sta7",
            "Sta9",
            "Sta11",
        ]
        assert self.fsm._events[:7] == [
            "Evt1",
            "Evt2",
            "Evt3",
            "Evt11",
            "Evt12",
            "Evt14",
            "Evt8",
        ]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt09(self):
        """Test Sta11 + Evt9."""
        # Sta11 + Evt9 -> <ignore> -> Sta11
        # Evt9: Receive P-DATA primitive from <local user>
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("send", a_release_rq),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_pdata())

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:6] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta9", "Evt14", "AR-9"),
        ]
        assert self.fsm._transitions[:6] == [
            "Sta4",
            "Sta5",
            "Sta6",
            "Sta7",
            "Sta9",
            "Sta11",
        ]
        assert self.fsm._events[:7] == [
            "Evt1",
            "Evt2",
            "Evt3",
            "Evt11",
            "Evt12",
            "Evt14",
            "Evt9",
        ]

    def test_evt10(self):
        """Test Sta11 + Evt10."""
        # Sta11 + Evt10 -> AA-8 -> Sta13
        # Evt10: Receive P-DATA-TF PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("send", a_release_rq),
            ("recv", None),
            ("send", p_data_tf),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:7] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta9", "Evt14", "AR-9"),
            ("Sta11", "Evt10", "AA-8"),
        ]
        assert self.fsm._transitions[:6] == [
            "Sta4",
            "Sta5",
            "Sta6",
            "Sta7",
            "Sta9",
            "Sta11",
        ]
        assert self.fsm._events[:7] == [
            "Evt1",
            "Evt2",
            "Evt3",
            "Evt11",
            "Evt12",
            "Evt14",
            "Evt10",
        ]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt11(self):
        """Test Sta11 + Evt11."""
        # Sta11 + Evt11 -> <ignore> -> Sta11
        # Evt11: Receive A-RELEASE (rq) primitive from <local user>
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("send", a_release_rq),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_release(False))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:6] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta9", "Evt14", "AR-9"),
        ]
        assert self.fsm._transitions[:6] == [
            "Sta4",
            "Sta5",
            "Sta6",
            "Sta7",
            "Sta9",
            "Sta11",
        ]
        assert self.fsm._events[:7] == [
            "Evt1",
            "Evt2",
            "Evt3",
            "Evt11",
            "Evt12",
            "Evt14",
            "Evt11",
        ]

    def test_evt12(self):
        """Test Sta11 + Evt12."""
        # Sta11 + Evt12 -> AA-8 -> Sta13
        # Evt12: Receive A-RELEASE-RQ PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("send", a_release_rq),
            ("recv", None),
            ("send", a_release_rq),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:7] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta9", "Evt14", "AR-9"),
            ("Sta11", "Evt12", "AA-8"),
        ]
        assert self.fsm._transitions[:6] == [
            "Sta4",
            "Sta5",
            "Sta6",
            "Sta7",
            "Sta9",
            "Sta11",
        ]
        assert self.fsm._events[:7] == [
            "Evt1",
            "Evt2",
            "Evt3",
            "Evt11",
            "Evt12",
            "Evt14",
            "Evt12",
        ]

    def test_evt13(self):
        """Test Sta11 + Evt13."""
        # Sta11 + Evt13 -> AR-3 -> Sta1
        # Evt13: Receive A-RELEASE-RP PDU from <remote>
        # AR-3: Issue A-RELEASE (rp) primitive and close connection
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("send", a_release_rq),
            ("recv", None),
            ("send", a_release_rp),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:7] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta9", "Evt14", "AR-9"),
            ("Sta11", "Evt13", "AR-3"),
        ]
        assert self.fsm._transitions[:6] == [
            "Sta4",
            "Sta5",
            "Sta6",
            "Sta7",
            "Sta9",
            "Sta11",
        ]
        assert self.fsm._events[:7] == [
            "Evt1",
            "Evt2",
            "Evt3",
            "Evt11",
            "Evt12",
            "Evt14",
            "Evt13",
        ]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt14(self):
        """Test Sta11 + Evt14."""
        # Sta11 + Evt14 -> <ignore> -> Sta11
        # Evt14: Receive A-RELEASE (rsp) primitive from <local user>
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("send", a_release_rq),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_release(True))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:6] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta9", "Evt14", "AR-9"),
        ]
        assert self.fsm._transitions[:6] == [
            "Sta4",
            "Sta5",
            "Sta6",
            "Sta7",
            "Sta9",
            "Sta11",
        ]
        assert self.fsm._events[:7] == [
            "Evt1",
            "Evt2",
            "Evt3",
            "Evt11",
            "Evt12",
            "Evt14",
            "Evt14",
        ]

    def test_evt15(self):
        """Test Sta11 + Evt15."""
        # Sta11 + Evt15 -> AA-1 -> Sta13
        # Evt15: Receive A-ABORT (rq) primitive from <local user>
        # AA-1: Send A-ABORT PDU to <remote>, start ARTIM
        commands = [
            ("recv", None),  # recv a-associate-rq
            ("send", a_associate_ac),
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("recv", None),  # recv a-release-rp
            ("recv", None),  # recv a-abort
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_abort())

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:7] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta9", "Evt14", "AR-9"),
            ("Sta11", "Evt15", "AA-1"),
        ]
        assert self.fsm._transitions[:6] == [
            "Sta4",
            "Sta5",
            "Sta6",
            "Sta7",
            "Sta9",
            "Sta11",
        ]
        assert self.fsm._events[:7] == [
            "Evt1",
            "Evt2",
            "Evt3",
            "Evt11",
            "Evt12",
            "Evt14",
            "Evt15",
        ]

    def test_evt16(self):
        """Test Sta11 + Evt16."""
        # Sta11 + Evt16 -> AA-3 -> Sta1
        # Evt16: Receive A-ABORT PDU from <remote>
        # AA-3: Issue A-ABORT or A-P-ABORT primitive, close connection
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("send", a_release_rq),
            ("recv", None),
            ("send", a_abort),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:7] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta9", "Evt14", "AR-9"),
            ("Sta11", "Evt16", "AA-3"),
        ]
        assert self.fsm._transitions[:6] == [
            "Sta4",
            "Sta5",
            "Sta6",
            "Sta7",
            "Sta9",
            "Sta11",
        ]
        assert self.fsm._events[:7] == [
            "Evt1",
            "Evt2",
            "Evt3",
            "Evt11",
            "Evt12",
            "Evt14",
            "Evt16",
        ]

    def test_evt17(self):
        """Test Sta11 + Evt17."""
        # Sta11 + Evt17 -> AA-4 -> Sta1
        # Evt17: Receive TRANSPORT_CLOSED from <transport service>
        # AA-4: Issue A-P-ABORT primitive
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("send", a_release_rq),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.shutdown()

        time.sleep(0.5)

        assert self.fsm._changes[:7] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta9", "Evt14", "AR-9"),
            ("Sta11", "Evt17", "AA-4"),
        ]
        assert self.fsm._transitions[:6] == [
            "Sta4",
            "Sta5",
            "Sta6",
            "Sta7",
            "Sta9",
            "Sta11",
        ]
        assert self.fsm._events[:7] == [
            "Evt1",
            "Evt2",
            "Evt3",
            "Evt11",
            "Evt12",
            "Evt14",
            "Evt17",
        ]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt18(self):
        """Test Sta11 + Evt18."""
        # Sta11 + Evt18 -> <ignore> -> Sta11
        # Evt18: ARTIM timer expired from <local service>
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("send", a_release_rq),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.artim_timer.timeout = 0.05
        self.assoc.dul.artim_timer.start()

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:6] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta9", "Evt14", "AR-9"),
        ]
        assert self.fsm._transitions[:5] == ["Sta4", "Sta5", "Sta6", "Sta7", "Sta9"]
        assert self.fsm._events[:7] == [
            "Evt1",
            "Evt2",
            "Evt3",
            "Evt11",
            "Evt12",
            "Evt14",
            "Evt18",
        ]

    def test_evt19(self):
        """Test Sta11 + Evt19."""
        # Sta11 + Evt19 -> AA-8 -> Sta13
        # Evt19: Received unrecognised or invalid PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("recv", None),
            ("send", a_release_rq),
            ("recv", None),
            ("send", b"\x08\x00\x00\x00\x00\x00"),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:7] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta9", "Evt14", "AR-9"),
            ("Sta11", "Evt19", "AA-8"),
        ]
        assert self.fsm._transitions[:6] == [
            "Sta4",
            "Sta5",
            "Sta6",
            "Sta7",
            "Sta9",
            "Sta11",
        ]
        assert self.fsm._events[:7] == [
            "Evt1",
            "Evt2",
            "Evt3",
            "Evt11",
            "Evt12",
            "Evt14",
            "Evt19",
        ]


class TestState12(TestStateBase):
    """Tests for State 12: Release collision acc - awaiting A-RELEASE (rp)"""

    def move_to_state(self, assoc, scp):
        def is_release_requested():
            """Override ACSE.is_release_requested."""
            return False

        assoc.acse.is_release_requested = is_release_requested

        assoc.start()
        scp.step()
        scp.step()
        self.wait_on_state(assoc.dul.state_machine, "Sta6")
        assoc.dul.send_pdu(self.get_release(False))
        scp.step()
        scp.step()
        self.wait_on_state(assoc.dul.state_machine, "Sta10")
        scp.step()
        self.wait_on_state(assoc.dul.state_machine, "Sta12")

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt01(self):
        """Test Sta12 + Evt1."""
        # Sta12 + Evt1 -> <ignore> -> Sta12
        # Evt1: A-ASSOCIATE (rq) primitive from <local user>
        commands = [
            ("send", a_associate_rq),
            ("recv", None),  # recv a-associate-rq
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("send", a_release_rp),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)
        assoc.dul.send_pdu(self.get_associate("request"))

        while assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert fsm._transitions[:6] == [
            "Sta2",
            "Sta3",
            "Sta6",
            "Sta7",
            "Sta10",
            "Sta12",
        ]
        assert fsm._changes[:6] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt7", "AE-7"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta10", "Evt13", "AR-10"),
        ]
        assert fsm._events[:7] == [
            "Evt5",
            "Evt6",
            "Evt7",
            "Evt11",
            "Evt12",
            "Evt13",
            "Evt1",
        ]

    @pytest.mark.skip()
    def test_evt02(self):
        """Test Sta12 + Evt2."""
        # Sta12 + Evt2 -> <ignore> -> Sta12
        # Evt2: Receive TRANSPORT_OPEN from <transport service>
        pass

    def test_evt03(self):
        """Test Sta12 + Evt3."""
        # Sta12 + Evt3 -> AA-8 -> Sta13
        # Evt3: Receive A-ASSOCIATE-AC PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("send", a_associate_rq),
            ("recv", None),  # recv a-associate-rq
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("send", a_release_rp),
            ("send", a_associate_ac),  # trigger event
            ("recv", None),  # recv a-abort
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert fsm._transitions[:6] == [
            "Sta2",
            "Sta3",
            "Sta6",
            "Sta7",
            "Sta10",
            "Sta12",
        ]
        assert fsm._changes[:7] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt7", "AE-7"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta10", "Evt13", "AR-10"),
            ("Sta12", "Evt3", "AA-8"),
        ]
        assert fsm._events[:7] == [
            "Evt5",
            "Evt6",
            "Evt7",
            "Evt11",
            "Evt12",
            "Evt13",
            "Evt3",
        ]
        assert scp.handlers[0].received[2] == (
            b"\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00"
        )

    def test_evt04(self):
        """Test Sta12 + Evt4."""
        # Sta12 + Evt4 -> AA-8 -> Sta13
        # Evt4: Receive A-ASSOCIATE-RJ PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("send", a_associate_rq),
            ("recv", None),  # recv a-associate-rq
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("send", a_release_rp),
            ("send", a_associate_rj),  # trigger event
            ("recv", None),  # recv a-abort
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert fsm._transitions[:6] == [
            "Sta2",
            "Sta3",
            "Sta6",
            "Sta7",
            "Sta10",
            "Sta12",
        ]
        assert fsm._changes[:7] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt7", "AE-7"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta10", "Evt13", "AR-10"),
            ("Sta12", "Evt4", "AA-8"),
        ]
        assert fsm._events[:7] == [
            "Evt5",
            "Evt6",
            "Evt7",
            "Evt11",
            "Evt12",
            "Evt13",
            "Evt4",
        ]
        assert scp.handlers[0].received[2] == (
            b"\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00"
        )

    @pytest.mark.skip()
    def test_evt05(self):
        """Test Sta12 + Evt5."""
        # Sta12 + Evt5 -> <ignore> -> Sta12
        # Evt5: Receive TRANSPORT_INDICATION from <transport service>
        pass

    def test_evt06(self):
        """Test Sta12 + Evt6."""
        # Sta12 + Evt6 -> AA-8 -> Sta13
        # Evt6: Receive A-ASSOCIATE-RQ PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("send", a_associate_rq),
            ("recv", None),  # recv a-associate-rq
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("send", a_release_rp),
            ("send", a_associate_rq),  # trigger event
            ("recv", None),  # recv a-abort
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert fsm._transitions[:6] == [
            "Sta2",
            "Sta3",
            "Sta6",
            "Sta7",
            "Sta10",
            "Sta12",
        ]
        assert fsm._changes[:7] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt7", "AE-7"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta10", "Evt13", "AR-10"),
            ("Sta12", "Evt6", "AA-8"),
        ]
        assert fsm._events[:7] == [
            "Evt5",
            "Evt6",
            "Evt7",
            "Evt11",
            "Evt12",
            "Evt13",
            "Evt6",
        ]
        assert scp.handlers[0].received[2] == (
            b"\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00"
        )

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt07(self):
        """Test Sta12 + Evt7."""
        # Sta12 + Evt7 -> <ignore> -> Sta12
        # Evt7: Receive A-ASSOCIATE (accept) primitive from <local user>
        commands = [
            ("send", a_associate_rq),
            ("recv", None),  # recv a-associate-ac
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("send", a_release_rp),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        assoc.dul.send_pdu(self.get_associate("accept"))

        while assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert fsm._transitions[:6] == [
            "Sta2",
            "Sta3",
            "Sta6",
            "Sta7",
            "Sta10",
            "Sta12",
        ]
        assert fsm._changes[:6] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt7", "AE-7"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta10", "Evt13", "AR-10"),
        ]
        assert fsm._events[:7] == [
            "Evt5",
            "Evt6",
            "Evt7",
            "Evt11",
            "Evt12",
            "Evt13",
            "Evt7",
        ]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt08(self):
        """Test Sta12 + Evt8."""
        # Sta12 + Evt8 -> <ignore> -> Sta12
        # Evt8: Receive A-ASSOCIATE (reject) primitive from <local user>
        commands = [
            ("send", a_associate_rq),
            ("recv", None),  # recv a-associate-rq
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("send", a_release_rp),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        assoc.dul.send_pdu(self.get_associate("reject"))

        while assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert fsm._transitions[:6] == [
            "Sta2",
            "Sta3",
            "Sta6",
            "Sta7",
            "Sta10",
            "Sta12",
        ]
        assert fsm._changes[:6] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt7", "AE-7"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta10", "Evt13", "AR-10"),
        ]
        assert fsm._events[:7] == [
            "Evt5",
            "Evt6",
            "Evt7",
            "Evt11",
            "Evt12",
            "Evt13",
            "Evt8",
        ]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt09(self):
        """Test Sta12 + Evt9."""
        # Sta12 + Evt9 -> <ignore> -> Sta12
        # Evt9: Receive P-DATA primitive from <local user>
        commands = [
            ("send", a_associate_rq),
            ("recv", None),  # recv a-associate-rq
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("send", a_release_rp),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        assoc.dul.send_pdu(self.get_pdata())

        while assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert fsm._transitions[:6] == [
            "Sta2",
            "Sta3",
            "Sta6",
            "Sta7",
            "Sta10",
            "Sta12",
        ]
        assert fsm._changes[:6] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt7", "AE-7"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta10", "Evt13", "AR-10"),
        ]
        assert fsm._events[:7] == [
            "Evt5",
            "Evt6",
            "Evt7",
            "Evt11",
            "Evt12",
            "Evt13",
            "Evt9",
        ]

    def test_evt10(self):
        """Test Sta12 + Evt10."""
        # Sta12 + Evt10 -> AA-8 -> Sta13
        # Evt10: Receive P-DATA-TF PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("send", a_associate_rq),
            ("recv", None),  # recv a-associate-rq
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("send", a_release_rp),
            ("send", p_data_tf),  # trigger event
            ("recv", None),  # recv a-abort
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert fsm._transitions[:6] == [
            "Sta2",
            "Sta3",
            "Sta6",
            "Sta7",
            "Sta10",
            "Sta12",
        ]
        assert fsm._changes[:7] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt7", "AE-7"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta10", "Evt13", "AR-10"),
            ("Sta12", "Evt10", "AA-8"),
        ]
        assert fsm._events[:7] == [
            "Evt5",
            "Evt6",
            "Evt7",
            "Evt11",
            "Evt12",
            "Evt13",
            "Evt10",
        ]
        assert scp.handlers[0].received[2] == (
            b"\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00"
        )

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt11(self):
        """Test Sta12 + Evt11."""
        # Sta12 + Evt11 -> <ignore> -> Sta12
        # Evt11: Receive A-RELEASE (rq) primitive from <local user>
        commands = [
            ("send", a_associate_rq),
            ("recv", None),  # recv a-associate-rq
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("send", a_release_rp),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        assoc.dul.send_pdu(self.get_release(False))

        while assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert fsm._transitions[:6] == [
            "Sta2",
            "Sta3",
            "Sta6",
            "Sta7",
            "Sta10",
            "Sta12",
        ]
        assert fsm._changes[:6] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt7", "AE-7"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta10", "Evt13", "AR-10"),
        ]
        assert fsm._events[:7] == [
            "Evt5",
            "Evt6",
            "Evt7",
            "Evt11",
            "Evt12",
            "Evt13",
            "Evt11",
        ]

    def test_evt12(self):
        """Test Sta12 + Evt12."""
        # Sta12 + Evt12 -> AA-8 -> Sta13
        # Evt12: Receive A-RELEASE-RQ PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("send", a_associate_rq),
            ("recv", None),  # recv a-associate-rq
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("send", a_release_rp),
            ("send", a_release_rq),  # trigger event
            ("recv", None),  # recv a-abort
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert fsm._transitions[:6] == [
            "Sta2",
            "Sta3",
            "Sta6",
            "Sta7",
            "Sta10",
            "Sta12",
        ]
        assert fsm._changes[:7] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt7", "AE-7"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta10", "Evt13", "AR-10"),
            ("Sta12", "Evt12", "AA-8"),
        ]
        assert fsm._events[:7] == [
            "Evt5",
            "Evt6",
            "Evt7",
            "Evt11",
            "Evt12",
            "Evt13",
            "Evt12",
        ]
        assert scp.handlers[0].received[2] == (
            b"\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00"
        )

    def test_evt13(self):
        """Test Sta12 + Evt13."""
        # Sta12 + Evt13 -> AA-8 -> Sta1
        # Evt13: Receive A-RELEASE-RP PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("send", a_associate_rq),
            ("recv", None),  # recv a-associate-rq
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("send", a_release_rp),
            ("send", a_release_rp),  # trigger event
            ("recv", None),  # recv a-abort
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert fsm._transitions[:6] == [
            "Sta2",
            "Sta3",
            "Sta6",
            "Sta7",
            "Sta10",
            "Sta12",
        ]
        assert fsm._changes[:7] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt7", "AE-7"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta10", "Evt13", "AR-10"),
            ("Sta12", "Evt13", "AA-8"),
        ]
        assert fsm._events[:7] == [
            "Evt5",
            "Evt6",
            "Evt7",
            "Evt11",
            "Evt12",
            "Evt13",
            "Evt13",
        ]
        assert scp.handlers[0].received[2] == (
            b"\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00"
        )

    def test_evt14(self):
        """Test Sta12 + Evt14."""
        # Sta12 + Evt14 -> AR-4 -> Sta12
        # Evt14: Receive A-RELEASE (rsp) primitive from <local user>
        # AR-4: Issue A-RELEASE-RP PDU and start ARTIM
        commands = [
            ("send", a_associate_rq),
            ("recv", None),  # recv a-associate-rq
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("send", a_release_rp),
            ("recv", None),  # recv a-release-rp
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)
        assoc.dul.send_pdu(self.get_release(True))

        scp.step()
        scp.step()
        scp.shutdown()

        assert fsm._transitions[:6] == [
            "Sta2",
            "Sta3",
            "Sta6",
            "Sta7",
            "Sta10",
            "Sta12",
        ]
        assert fsm._changes[:7] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt7", "AE-7"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta10", "Evt13", "AR-10"),
            ("Sta12", "Evt14", "AR-4"),
        ]
        assert fsm._events[:7] == [
            "Evt5",
            "Evt6",
            "Evt7",
            "Evt11",
            "Evt12",
            "Evt13",
            "Evt14",
        ]
        assert scp.handlers[0].received[2] == (
            b"\x06\x00\x00\x00\x00\x04\x00\x00\x00\x00"
        )

    def test_evt15(self):
        """Test Sta12 + Evt15."""
        # Sta12 + Evt15 -> AA-1 -> Sta13
        # Evt15: Receive A-ABORT (rq) primitive from <local user>
        # AA-1: Send A-ABORT PDU to <remote>, start ARTIM
        commands = [
            ("send", a_associate_rq),
            ("recv", None),  # recv a-associate-rq
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("send", a_release_rp),
            ("recv", None),  # recv a-abort
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)
        assoc.dul.send_pdu(self.get_abort())

        scp.step()
        scp.step()
        scp.shutdown()

        assert fsm._transitions[:6] == [
            "Sta2",
            "Sta3",
            "Sta6",
            "Sta7",
            "Sta10",
            "Sta12",
        ]
        assert fsm._changes[:7] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt7", "AE-7"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta10", "Evt13", "AR-10"),
            ("Sta12", "Evt15", "AA-1"),
        ]
        assert fsm._events[:7] == [
            "Evt5",
            "Evt6",
            "Evt7",
            "Evt11",
            "Evt12",
            "Evt13",
            "Evt15",
        ]
        assert scp.handlers[0].received[2] == (
            b"\x07\x00\x00\x00\x00\x04\x00\x00\x00\x00"
        )

    def test_evt16(self):
        """Test Sta12 + Evt16."""
        # Sta12 + Evt16 -> AA-3 -> Sta1
        # Evt16: Receive A-ABORT PDU from <remote>
        # AA-3: Issue A-ABORT or A-P-ABORT primitive, close connection
        commands = [
            ("send", a_associate_rq),
            ("recv", None),  # recv a-associate-rq
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("send", a_release_rp),
            ("send", a_abort),  # trigger event
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        scp.step()
        scp.step()
        scp.shutdown()

        assert fsm._transitions[:6] == [
            "Sta2",
            "Sta3",
            "Sta6",
            "Sta7",
            "Sta10",
            "Sta12",
        ]
        assert fsm._changes[:7] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt7", "AE-7"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta10", "Evt13", "AR-10"),
            ("Sta12", "Evt16", "AA-3"),
        ]
        assert fsm._events[:7] == [
            "Evt5",
            "Evt6",
            "Evt7",
            "Evt11",
            "Evt12",
            "Evt13",
            "Evt16",
        ]

    def test_evt17(self):
        """Test Sta12 + Evt17."""
        # Sta12 + Evt17 -> AA-4 -> Sta1
        # Evt17: Receive TRANSPORT_CLOSED from <transport service>
        # AA-4: Issue A-P-ABORT primitive
        commands = [
            ("send", a_associate_rq),
            ("recv", None),  # recv a-associate-rq
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("send", a_release_rp),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        scp.step()
        scp.shutdown()

        time.sleep(0.5)

        assert fsm._transitions[:6] == [
            "Sta2",
            "Sta3",
            "Sta6",
            "Sta7",
            "Sta10",
            "Sta12",
        ]
        assert fsm._changes[:7] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt7", "AE-7"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta10", "Evt13", "AR-10"),
            ("Sta12", "Evt17", "AA-4"),
        ]
        assert fsm._events[:7] == [
            "Evt5",
            "Evt6",
            "Evt7",
            "Evt11",
            "Evt12",
            "Evt13",
            "Evt17",
        ]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt18(self):
        """Test Sta12 + Evt18."""
        # Sta12 + Evt18 -> <ignore> -> Sta12
        # Evt18: ARTIM timer expired from <local service>
        commands = [
            ("send", a_associate_rq),
            ("recv", None),  # recv a-associate-rq
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("send", a_release_rp),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        assoc.dul.artim_timer.timeout = 0.05
        assoc.dul.artim_timer.start()

        while assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert fsm._transitions[:6] == [
            "Sta2",
            "Sta3",
            "Sta6",
            "Sta7",
            "Sta10",
            "Sta12",
        ]
        assert fsm._changes[:7] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt7", "AE-7"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta10", "Evt13", "AR-10"),
        ]
        assert fsm._events[:7] == [
            "Evt5",
            "Evt6",
            "Evt7",
            "Evt11",
            "Evt12",
            "Evt13",
            "Evt18",
        ]

    def test_evt19(self):
        """Test Sta12 + Evt19."""
        # Sta12 + Evt19 -> AA-8 -> Sta13
        # Evt19: Received unrecognised or invalid PDU from <remote>
        # AA-8: Send A-ABORT PDU, issue A-P-ABORT primitive, start ARTIM
        commands = [
            ("send", a_associate_rq),
            ("recv", None),  # recv a-associate-rq
            ("recv", None),  # recv a-release-rq
            ("send", a_release_rq),  # collide
            ("send", a_release_rp),
            ("send", b"\x08\x00\x00\x00\x00\x00\x00\x00"),  # trigger event
            ("recv", None),  # recv a-abort
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        assoc, fsm = self.get_acceptor_assoc()
        self.move_to_state(assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.shutdown()

        assert fsm._transitions[:6] == [
            "Sta2",
            "Sta3",
            "Sta6",
            "Sta7",
            "Sta10",
            "Sta12",
        ]
        assert fsm._changes[:7] == [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt7", "AE-7"),
            ("Sta6", "Evt11", "AR-1"),
            ("Sta7", "Evt12", "AR-8"),
            ("Sta10", "Evt13", "AR-10"),
            ("Sta12", "Evt19", "AA-8"),
        ]
        assert fsm._events[:7] == [
            "Evt5",
            "Evt6",
            "Evt7",
            "Evt11",
            "Evt12",
            "Evt13",
            "Evt19",
        ]
        assert scp.handlers[0].received[2] == (
            b"\x07\x00\x00\x00\x00\x04\x00\x00\x02\x00"
        )


class TestState13(TestStateBase):
    """Tests for State 13: Waiting for connection closed."""

    def move_to_state(self, assoc, scp):
        def patch_neg_rq():
            """Override ACSE._negotiate_as_requestor"""
            assoc.acse.send_request()

        assoc.acse._negotiate_as_requestor = patch_neg_rq

        orig_method = assoc.dul._is_transport_event

        def patch_xport_event():
            """Override DUL._is_transport_event to not close in Sta13."""
            if self.fsm.current_state == "Sta13":
                if assoc.dul.socket and assoc.dul.socket.ready:
                    assoc.dul._read_pdu_data()
                    return True

                return False

            return orig_method()

        assoc.dul._is_transport_event = patch_xport_event
        assoc.start()
        scp.step()
        scp.step()
        self.wait_on_state(assoc.dul.state_machine, "Sta13")

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt01(self):
        """Test Sta13 + Evt1."""
        # Sta13 + Evt1 -> <ignore> -> Sta13
        # Evt1: A-ASSOCIATE (rq) primitive from <local user>
        commands = [
            ("recv", None),
            ("send", a_associate_rq),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_associate("request"))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        self.assoc.dul.socket.close()

        assert self.fsm._changes[:3] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt6", "AA-8"),
        ]
        assert self.fsm._transitions[:3] == ["Sta4", "Sta5", "Sta13"]
        assert self.fsm._events[:4] == ["Evt1", "Evt2", "Evt6", "Evt1"]

    @pytest.mark.skip()
    def test_evt02(self):
        """Test Sta13 + Evt2."""
        # Sta13 + Evt2 -> <ignore> -> Sta13
        # Evt2: Receive TRANSPORT_OPEN from <transport service>
        pass

    def test_evt03(self):
        """Test Sta13 + Evt3."""
        # Sta13 + Evt3 -> AA-6 -> Sta13
        # Evt3: Receive A-ASSOCIATE-AC PDU from <remote>
        # AA-6: Ignore PDU
        commands = [
            ("recv", None),
            ("send", a_associate_rq),
            ("send", a_associate_ac),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.shutdown()

        self.assoc.dul.socket.close()

        assert self.fsm._changes[:4] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt6", "AA-8"),
            ("Sta13", "Evt3", "AA-6"),
        ]
        assert self.fsm._transitions[:3] == ["Sta4", "Sta5", "Sta13"]
        assert self.fsm._events[:4] == ["Evt1", "Evt2", "Evt6", "Evt3"]

    def test_evt04(self):
        """Test Sta13 + Evt4."""
        # Sta13 + Evt4 -> AA-6 -> Sta13
        # Evt4: Receive A-ASSOCIATE-RJ PDU from <remote>
        # AA-6: Ignore PDU
        commands = [
            ("recv", None),
            ("send", a_associate_rq),
            ("send", a_associate_rj),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:4] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt6", "AA-8"),
            ("Sta13", "Evt4", "AA-6"),
        ]
        assert self.fsm._transitions[:3] == ["Sta4", "Sta5", "Sta13"]
        assert self.fsm._events[:4] == ["Evt1", "Evt2", "Evt6", "Evt4"]

    @pytest.mark.skip()
    def test_evt05(self):
        """Test Sta13 + Evt5."""
        # Sta13 + Evt5 -> <ignore> -> Sta13
        # Evt5: Receive TRANSPORT_INDICATION from <transport service>
        pass

    def test_evt06(self):
        """Test Sta13 + Evt6."""
        # Sta13 + Evt6 -> AA-7 -> Sta13
        # Evt6: Receive A-ASSOCIATE-RQ PDU from <remote>
        # AA-7: Send A-ABORT PDU to <remote>
        commands = [
            ("recv", None),
            ("send", a_associate_rq),
            ("send", a_associate_rq),
            ("recv", None),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.step()

        scp.shutdown()

        pdu = A_ABORT_RQ()
        pdu.decode(scp.received[2])
        assert pdu.source == 2
        assert pdu.reason_diagnostic == 2

        assert self.fsm._changes[:4] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt6", "AA-8"),
            ("Sta13", "Evt6", "AA-7"),
        ]
        assert self.fsm._transitions[:3] == ["Sta4", "Sta5", "Sta13"]
        assert self.fsm._events[:4] == ["Evt1", "Evt2", "Evt6", "Evt6"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt07(self):
        """Test Sta13 + Evt7."""
        # Sta13 + Evt7 -> <ignore> -> Sta13
        # Evt7: Receive A-ASSOCIATE (accept) primitive from <local user>
        commands = [
            ("recv", None),
            ("send", a_associate_rq),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_associate("accept"))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:3] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt6", "AA-8"),
        ]
        assert self.fsm._transitions[:3] == ["Sta4", "Sta5", "Sta13"]
        assert self.fsm._events[:4] == ["Evt1", "Evt2", "Evt6", "Evt7"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt08(self):
        """Test Sta13 + Evt8."""
        # Sta13 + Evt8 -> <ignore> -> Sta13
        # Evt8: Receive A-ASSOCIATE (reject) primitive from <local user>
        commands = [
            ("recv", None),
            ("send", a_associate_rq),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_associate("reject"))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:3] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt6", "AA-8"),
        ]
        assert self.fsm._transitions[:3] == ["Sta4", "Sta5", "Sta13"]
        assert self.fsm._events[:4] == ["Evt1", "Evt2", "Evt6", "Evt8"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt09(self):
        """Test Sta13 + Evt9."""
        # Sta13 + Evt9 -> <ignore> -> Sta13
        # Evt9: Receive P-DATA primitive from <local user>
        commands = [
            ("recv", None),
            ("send", a_associate_rq),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_pdata())

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:3] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt6", "AA-8"),
        ]
        assert self.fsm._transitions[:3] == ["Sta4", "Sta5", "Sta13"]
        assert self.fsm._events[:4] == ["Evt1", "Evt2", "Evt6", "Evt9"]

    def test_evt10(self):
        """Test Sta13 + Evt10."""
        # Sta13 + Evt10 -> AA-6 -> Sta13
        # Evt10: Receive P-DATA-TF PDU from <remote>
        # AA-6: Ignore PDU
        commands = [
            ("recv", None),
            ("send", a_associate_rq),
            ("send", p_data_tf),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:4] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt6", "AA-8"),
            ("Sta13", "Evt10", "AA-6"),
        ]
        assert self.fsm._transitions[:3] == ["Sta4", "Sta5", "Sta13"]
        assert self.fsm._events[:4] == ["Evt1", "Evt2", "Evt6", "Evt10"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt11(self):
        """Test Sta13 + Evt11."""
        # Sta13 + Evt11 -> <ignore> -> Sta13
        # Evt11: Receive A-RELEASE (rq) primitive from <local user>
        commands = [
            ("recv", None),
            ("send", a_associate_rq),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_release(False))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:3] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt6", "AA-8"),
        ]
        assert self.fsm._transitions[:3] == ["Sta4", "Sta5", "Sta13"]
        assert self.fsm._events[:4] == ["Evt1", "Evt2", "Evt6", "Evt11"]

    def test_evt12(self):
        """Test Sta13 + Evt12."""
        # Sta13 + Evt12 -> AA-6 -> Sta13
        # Evt12: Receive A-RELEASE-RQ PDU from <remote>
        # AA-6: Ignore PDU
        commands = [
            ("recv", None),
            ("send", a_associate_rq),
            ("send", a_release_rq),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:4] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt6", "AA-8"),
            ("Sta13", "Evt12", "AA-6"),
        ]
        assert self.fsm._transitions[:3] == ["Sta4", "Sta5", "Sta13"]
        assert self.fsm._events[:4] == ["Evt1", "Evt2", "Evt6", "Evt12"]

    def test_evt13(self):
        """Test Sta13 + Evt13."""
        # Sta13 + Evt13 -> AA-6 -> Sta1
        # Evt13: Receive A-RELEASE-RP PDU from <remote>
        # AA-6: Ignore PDU
        commands = [
            ("recv", None),
            ("send", a_associate_rq),
            ("send", a_release_rp),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:4] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt6", "AA-8"),
            ("Sta13", "Evt13", "AA-6"),
        ]
        assert self.fsm._transitions[:3] == ["Sta4", "Sta5", "Sta13"]
        assert self.fsm._events[:4] == ["Evt1", "Evt2", "Evt6", "Evt13"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt14(self):
        """Test Sta13 + Evt14."""
        # Sta13 + Evt14 -> <ignore> -> Sta13
        # Evt14: Receive A-RELEASE (rsp) primitive from <local user>
        commands = [
            ("recv", None),
            ("send", a_associate_rq),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_release(True))

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:3] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt6", "AA-8"),
        ]
        assert self.fsm._transitions[:3] == ["Sta4", "Sta5", "Sta13"]
        assert self.fsm._events[:4] == ["Evt1", "Evt2", "Evt6", "Evt14"]

    @pytest.mark.filterwarnings(IGNORE_FILTER)
    def test_evt15(self):
        """Test Sta13 + Evt15."""
        # Sta13 + Evt15 -> <ignore> -> Sta13
        # Evt15: Receive A-ABORT (rq) primitive from <local user>
        commands = [
            ("recv", None),
            ("send", a_associate_rq),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.send_pdu(self.get_abort())

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:3] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt6", "AA-8"),
        ]
        assert self.fsm._transitions[:3] == ["Sta4", "Sta5", "Sta13"]
        assert self.fsm._events[:4] == ["Evt1", "Evt2", "Evt6", "Evt15"]

    def test_evt16(self):
        """Test Sta13 + Evt16."""
        # Sta13 + Evt16 -> AA-2 -> Sta1
        # Evt16: Receive A-ABORT PDU from <remote>
        # AA-2: Stop ARTIM, close connection
        commands = [
            ("recv", None),
            ("send", a_associate_rq),
            ("send", a_abort),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:4] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt6", "AA-8"),
            ("Sta13", "Evt16", "AA-2"),
        ]
        assert self.fsm._transitions[:3] == ["Sta4", "Sta5", "Sta13"]
        assert self.fsm._events[:4] == ["Evt1", "Evt2", "Evt6", "Evt16"]

    def test_evt17(self):
        """Test Sta13 + Evt17."""
        # Sta13 + Evt17 -> AR-5 -> Sta1
        # Evt17: Receive TRANSPORT_CLOSED from <transport service>
        # AR-5: Stop ARTIM
        commands = [
            ("recv", None),
            ("send", a_associate_rq),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.shutdown()

        time.sleep(0.5)

        assert self.fsm._changes[:4] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt6", "AA-8"),
            ("Sta13", "Evt17", "AR-5"),
        ]
        assert self.fsm._transitions[:3] == ["Sta4", "Sta5", "Sta13"]
        assert self.fsm._events[:4] == ["Evt1", "Evt2", "Evt6", "Evt17"]

    def test_evt18(self):
        """Test Sta13 + Evt18."""
        # Sta13 + Evt18 -> AA-2 -> Sta1
        # Evt18: ARTIM timer expired from <local service>
        # AA-2: Stop ARTIM, close connection
        commands = [
            ("recv", None),
            ("send", a_associate_rq),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        self.assoc.dul.artim_timer.timeout = 0.05
        self.assoc.dul.artim_timer.start()
        time.sleep(0.5)

        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:4] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt6", "AA-8"),
            ("Sta13", "Evt18", "AA-2"),
        ]
        assert self.fsm._transitions[:3] == ["Sta4", "Sta5", "Sta13"]
        assert self.fsm._events[:4] == ["Evt1", "Evt2", "Evt6", "Evt18"]

    def test_evt19(self):
        """Test Sta13 + Evt19."""
        # Sta13 + Evt19 -> AA-7 -> Sta13
        # Evt19: Received unrecognised or invalid PDU from <remote>
        # AA-7: Send A-ABORT PDU to <remote>
        commands = [
            ("recv", None),
            ("send", a_associate_rq),
            ("send", b"\x08\x00\x00\x00\x00\x00\x00\x00"),
            ("recv", None),
            ("recv", None),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.move_to_state(self.assoc, scp)

        scp.step()
        scp.step()
        scp.step()
        scp.step()

        scp.shutdown()

        pdu = A_ABORT_RQ()
        pdu.decode(scp.received[2])
        assert pdu.source == 2
        assert pdu.reason_diagnostic == 2

        assert self.fsm._changes[:4] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt6", "AA-8"),
            ("Sta13", "Evt19", "AA-7"),
        ]
        assert self.fsm._transitions[:3] == ["Sta4", "Sta5", "Sta13"]
        assert self.fsm._events[:4] == ["Evt1", "Evt2", "Evt6", "Evt19"]


class TestParrotAttack(TestStateBase):
    """Test a parrot attack on the association."""

    def test_requestor(self):
        commands = [
            ("recv", None),
            ("send", a_associate_ac),
            ("send", p_data_tf),
            ("send", p_data_tf),
            ("send", p_data_tf),
            ("send", p_data_tf),
            ("send", p_data_tf),
            ("send", p_data_tf),
            ("send", p_data_tf),
            ("send", p_data_tf),
            ("send", a_release_rq),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)
        self.assoc.start()

        for ii in range(len(commands) - 1):
            scp.step()

        while self.assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert self.fsm._changes[:14] == [
            ("Sta1", "Evt1", "AE-1"),
            ("Sta4", "Evt2", "AE-2"),
            ("Sta5", "Evt3", "AE-3"),
            ("Sta6", "Evt10", "DT-2"),
            ("Sta6", "Evt10", "DT-2"),
            ("Sta6", "Evt10", "DT-2"),
            ("Sta6", "Evt10", "DT-2"),
            ("Sta6", "Evt10", "DT-2"),
            ("Sta6", "Evt10", "DT-2"),
            ("Sta6", "Evt10", "DT-2"),
            ("Sta6", "Evt10", "DT-2"),
            ("Sta6", "Evt12", "AR-2"),
            ("Sta8", "Evt14", "AR-4"),
            ("Sta13", "Evt17", "AR-5"),
        ]

    def test_acceptor(self):
        """Test hitting the acceptor with PDUs."""
        # Also a regression test for #120
        # C-ECHO-RQ
        # 80 total length
        echo_rq = (
            b"\x04\x00\x00\x00\x00\x4a"  # P-DATA-TF 74
            b"\x00\x00\x00\x46\x01"  # PDV Item 70
            b"\x03"  # PDV: 2 -> 69
            b"\x00\x00\x00\x00\x04\x00\x00\x00\x42\x00\x00\x00"  # 12 Command Group Length
            b"\x00\x00\x02\x00\x12\x00\x00\x00\x31\x2e\x32\x2e\x38"
            b"\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x31\x2e\x31\x00"  # 26
            b"\x00\x00\x00\x01\x02\x00\x00\x00\x30\x00"  # 10 Command Field
            b"\x00\x00\x10\x01\x02\x00\x00\x00\x01\x00"  # 10 Message ID
            b"\x00\x00\x00\x08\x02\x00\x00\x00\x01\x01"  # 10 Command Data Set Type
        )

        # Send associate request then c-echo requests then release request
        commands = [
            ("send", a_associate_rq),
            ("recv", None),
            ("send", echo_rq),
            ("recv", None),
            ("send", echo_rq),
            ("recv", None),
            ("send", echo_rq),
            ("recv", None),
            ("send", echo_rq),
            ("recv", None),
            ("send", echo_rq),
            ("recv", None),
            ("send", echo_rq),
            ("recv", None),
            ("send", echo_rq),
            ("recv", None),
            ("send", echo_rq),
            ("recv", None),
            ("send", echo_rq),
            ("recv", None),
            ("send", echo_rq),
            ("recv", None),
            ("send", echo_rq),
            ("recv", None),
            ("send", echo_rq),
            ("recv", None),
            ("send", a_release_rq),
            ("exit", None),
        ]
        self.scp = scp = self.start_server(commands)

        assoc, fsm = self.get_acceptor_assoc()
        assoc.start()

        for ii in range(len(commands) - 1):
            scp.step()

        while assoc.dul.is_alive():
            time.sleep(0.001)

        scp.step()
        scp.shutdown()

        assert [
            ("Sta1", "Evt5", "AE-5"),
            ("Sta2", "Evt6", "AE-6"),
            ("Sta3", "Evt7", "AE-7"),
            ("Sta6", "Evt10", "DT-2"),
            ("Sta6", "Evt9", "DT-1"),
            ("Sta6", "Evt10", "DT-2"),
            ("Sta6", "Evt9", "DT-1"),
            ("Sta6", "Evt10", "DT-2"),
            ("Sta6", "Evt9", "DT-1"),
            ("Sta6", "Evt10", "DT-2"),
            ("Sta6", "Evt9", "DT-1"),
            ("Sta6", "Evt10", "DT-2"),
            ("Sta6", "Evt9", "DT-1"),
            ("Sta6", "Evt10", "DT-2"),
            ("Sta6", "Evt9", "DT-1"),
            ("Sta6", "Evt10", "DT-2"),
            ("Sta6", "Evt9", "DT-1"),
            ("Sta6", "Evt10", "DT-2"),
            ("Sta6", "Evt9", "DT-1"),
            ("Sta6", "Evt10", "DT-2"),
            ("Sta6", "Evt9", "DT-1"),
            ("Sta6", "Evt10", "DT-2"),
            ("Sta6", "Evt9", "DT-1"),
            ("Sta6", "Evt10", "DT-2"),
            ("Sta6", "Evt9", "DT-1"),
            ("Sta6", "Evt10", "DT-2"),
            ("Sta6", "Evt9", "DT-1"),
            ("Sta6", "Evt12", "AR-2"),
            ("Sta8", "Evt14", "AR-4"),
            ("Sta13", "Evt17", "AR-5"),
        ] == fsm._changes[:30]


class TestStateMachineFunctionalRequestor:
    """Functional tests for StateMachine as association requestor."""

    def setup_method(self):
        """Run prior to each test"""
        self.ae = None

        ae = AE()
        ae.add_requested_context(Verification)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        assoc = Association(ae, mode="requestor")
        assoc.set_socket(AssociationSocket(assoc, address=AddressInformation("", 0)))

        # Association Acceptor object -> remote AE
        assoc.acceptor.ae_title = "ANY_SCU"
        assoc.acceptor.address_info = AddressInformation("localhost", 11112)

        # Association Requestor object -> local AE
        assoc.requestor.address_info = AddressInformation("localhost", 11113)
        assoc.requestor.ae_title = ae.ae_title
        assoc.requestor.maximum_length = 16382
        assoc.requestor.implementation_class_uid = ae.implementation_class_uid
        assoc.requestor.implementation_version_name = ae.implementation_version_name

        cx = build_context(Verification)
        cx.context_id = 1
        assoc.requestor.requested_contexts = [cx]

        self.assoc = assoc
        self.fsm = self.monkey_patch(assoc.dul.state_machine)

        self.orig_ar2 = FINITE_STATE.ACTIONS["AR-2"]
        self.orig_ar4 = FINITE_STATE.ACTIONS["AR-4"]

    def teardown_method(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

        FINITE_STATE.ACTIONS["AR-4"] = self.orig_ar4
        FINITE_STATE.ACTIONS["AR-2"] = self.orig_ar2

        time.sleep(0.1)

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
        ae.add_requested_context(Verification)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        assoc = Association(ae, mode="requestor")

        fsm = self.monkey_patch(assoc.dul.state_machine)
        assert fsm.current_state == "Sta1"

        fsm.current_state = "Sta13"
        fsm.do_action("Evt3")

        assert fsm._changes == [("Sta13", "Evt3", "AA-6")]
        assert fsm._transitions == ["Sta13"]

    def test_associate_accept_release(self):
        """Test normal association/release."""
        self.ae = ae = AE()
        ae.add_supported_context(Verification)
        scp = ae.start_server(("localhost", 11112), block=False)

        assert self.fsm.current_state == "Sta1"

        self.assoc.start()

        timeout = 0
        while (
            not self.assoc.is_established
            and not self.assoc.is_rejected
            and not self.assoc.is_aborted
            and not self.assoc.dul._kill_thread
            and timeout < 10
        ):
            time.sleep(0.05)
            timeout += 0.05

        if self.assoc.is_established:
            self.assoc.release()

            timeout = 0
            while self.fsm.current_state != "Sta1" and timeout < 10:
                time.sleep(0.05)
                timeout += 0.05

            assert self.fsm._transitions == [
                "Sta4",  # Waiting for connection to complete
                "Sta5",  # Waiting for A-ASSOC-AC or -RJ PDU
                "Sta6",  # Assoc established
                "Sta7",  # Waiting for A-RELEASE-RP PDU
                "Sta1",  # Idle
            ]
            assert self.fsm._changes == [
                ("Sta1", "Evt1", "AE-1"),  # recv A-ASSOC rq primitive
                ("Sta4", "Evt2", "AE-2"),  # connection confirmed
                ("Sta5", "Evt3", "AE-3"),  # A-ASSOC-AC PDU recv
                ("Sta6", "Evt11", "AR-1"),  # A-RELEASE rq primitive
                ("Sta7", "Evt13", "AR-3"),  # A-RELEASE-RP PDU recv
            ]

        assert self.fsm.current_state == "Sta1"

        scp.shutdown()

    def test_associate_reject(self):
        """Test normal association rejection."""
        self.ae = ae = AE()
        ae.require_called_aet = True
        ae.add_supported_context(Verification)
        scp = ae.start_server(("localhost", 11112), block=False)

        assert self.fsm.current_state == "Sta1"

        self.assoc.start()

        timeout = 0
        while (
            not self.assoc.is_established
            and not self.assoc.is_rejected
            and not self.assoc.is_aborted
            and not self.assoc.dul._kill_thread
            and timeout < 10
        ):
            time.sleep(0.05)
            timeout += 0.05

        timeout = 0
        while self.fsm.current_state != "Sta1" and timeout < 10:
            time.sleep(0.05)
            timeout += 0.05

        assert self.assoc.is_rejected

        assert self.fsm._transitions == [
            "Sta4",  # Waiting for connection to complete
            "Sta5",  # Waiting for A-ASSOC-AC or -RJ PDU
            "Sta1",  # Idle
        ]
        assert self.fsm._changes == [
            ("Sta1", "Evt1", "AE-1"),  # recv A-ASSOC rq primitive
            ("Sta4", "Evt2", "AE-2"),  # connection confirmed
            ("Sta5", "Evt4", "AE-4"),  # A-ASSOC-RJ PDU recv
        ]

        assert self.fsm.current_state == "Sta1"

        scp.shutdown()

    def test_associate_accept_abort(self):
        """Test association acceptance then local abort."""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.add_supported_context(Verification)
        scp = ae.start_server(("localhost", 11112), block=False)

        assert self.fsm.current_state == "Sta1"

        self.assoc.start()

        timeout = 0
        while (
            not self.assoc.is_established
            and not self.assoc.is_rejected
            and not self.assoc.is_aborted
            and not self.assoc.dul._kill_thread
            and timeout < 10
        ):
            time.sleep(0.05)
            timeout += 0.05

        if self.assoc.is_established:
            self.assoc.abort()

            timeout = 0
            while self.fsm.current_state != "Sta1" and timeout < 10:
                time.sleep(0.05)
                timeout += 0.05

            assert self.fsm._transitions == [
                "Sta4",  # Waiting for connection to complete
                "Sta5",  # Waiting for A-ASSOC-AC or -RJ PDU
                "Sta6",  # Assoc established
                "Sta13",  # Waiting for connection closed
                "Sta1",  # Idle
            ]
            assert self.fsm._changes == [
                ("Sta1", "Evt1", "AE-1"),  # recv A-ASSOC rq primitive
                ("Sta4", "Evt2", "AE-2"),  # connection confirmed
                ("Sta5", "Evt3", "AE-3"),  # A-ASSOC-AC PDU recv
                ("Sta6", "Evt15", "AA-1"),  # A-ABORT rq primitive
                ("Sta13", "Evt17", "AR-5"),  # connection closed
            ]

        assert self.fsm.current_state == "Sta1"

        scp.shutdown()

    def test_associate_accept_local_abort(self):
        """Test association acceptance then local abort if no cx."""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.add_supported_context(Verification)
        scp = ae.start_server(("localhost", 11112), block=False)

        assert self.fsm.current_state == "Sta1"

        self.assoc.requestor.requested_contexts[0].abstract_syntax = "1.2.3"
        self.assoc.start()

        timeout = 0
        while (
            not self.assoc.is_established
            and not self.assoc.is_rejected
            and not self.assoc.is_aborted
            and not self.assoc.dul._kill_thread
            and timeout < 10
        ):
            time.sleep(0.05)
            timeout += 0.05

        timeout = 0
        while self.fsm.current_state != "Sta1" and timeout < 10:
            time.sleep(0.05)
            timeout += 0.05

        assert self.fsm._transitions == [
            "Sta4",  # Waiting for connection to complete
            "Sta5",  # Waiting for A-ASSOC-AC or -RJ PDU
            "Sta6",  # Assoc established
            "Sta13",  # Waiting for connection close
            "Sta1",  # Idle
        ]
        assert self.fsm._changes == [
            ("Sta1", "Evt1", "AE-1"),  # A-ASSOC rq primitive
            ("Sta4", "Evt2", "AE-2"),  # connection confirmed
            ("Sta5", "Evt3", "AE-3"),  # A-ASSOC-AC PDU recv
            ("Sta6", "Evt15", "AA-1"),  # A-ABORT rq primitive
            ("Sta13", "Evt17", "AR-5"),  # Connection closed
        ]

        assert self.fsm.current_state == "Sta1"

        scp.shutdown()

    def test_associate_accept_peer_abort(self):
        """Test association acceptance then peer abort."""
        self.ae = ae = AE()
        ae.network_timeout = 0.5
        ae.acse_timeout = 5
        ae.add_supported_context(Verification)
        scp = ae.start_server(("localhost", 11112), block=False)

        assert self.fsm.current_state == "Sta1"

        self.assoc.start()

        timeout = 0
        while (
            not self.assoc.is_established
            and not self.assoc.is_rejected
            and not self.assoc.is_aborted
            and not self.assoc.dul._kill_thread
            and timeout < 1
        ):
            time.sleep(0.05)
            timeout += 0.05

        timeout = 0
        while not self.assoc.is_established and timeout < 1:
            time.sleep(0.05)
            timeout += 0.05

        timeout = 0
        while not self.assoc.is_aborted and timeout < 1:
            time.sleep(0.05)
            timeout += 0.05

        timeout = 0
        while self.fsm.current_state != "Sta1" and timeout < 10:
            time.sleep(0.05)
            timeout += 0.05

        assert self.fsm._transitions == [
            "Sta4",  # Waiting for connection to complete
            "Sta5",  # Waiting for A-ASSOC-AC or -RJ PDU
            "Sta6",  # Assoc established
            "Sta1",  # Idle
        ]
        assert self.fsm._changes == [
            ("Sta1", "Evt1", "AE-1"),  # A-ASSOC rq primitive
            ("Sta4", "Evt2", "AE-2"),  # connection confirmed
            ("Sta5", "Evt3", "AE-3"),  # A-ASSOC-AC PDU recv
            ("Sta6", "Evt16", "AA-3"),  # A-ABORT-RQ PDV recv
        ]

        scp.shutdown()

    def test_associate_send_data(self):
        """Test association acceptance then send DIMSE message."""
        self.ae = ae = AE()
        ae.add_supported_context(Verification)
        scp = ae.start_server(("localhost", 11112), block=False)

        assert self.fsm.current_state == "Sta1"

        self.assoc.start()

        timeout = 0
        while (
            not self.assoc.is_established
            and not self.assoc.is_rejected
            and not self.assoc.is_aborted
            and not self.assoc.dul._kill_thread
            and timeout < 10
        ):
            time.sleep(0.05)
            timeout += 0.05

        self.assoc.send_c_echo()
        self.assoc.release()

        timeout = 0
        while self.fsm.current_state != "Sta1" and timeout < 10:
            time.sleep(0.05)
            timeout += 0.05

        assert self.fsm._transitions == [
            "Sta4",  # Waiting for connection to complete
            "Sta5",  # Waiting for A-ASSOC-AC or -RJ PDU
            "Sta6",  # Assoc established
            "Sta6",
            "Sta6",
            "Sta7",  # Waitinf for A-RELEASE-RP PDU
            "Sta1",  # Idle
        ]
        assert self.fsm._changes == [
            ("Sta1", "Evt1", "AE-1"),  # A-ASSOC rq primitive
            ("Sta4", "Evt2", "AE-2"),  # connection confirmed
            ("Sta5", "Evt3", "AE-3"),  # A-ASSOC-AC PDU recv
            ("Sta6", "Evt9", "DT-1"),  # P-DATA rq primitive
            ("Sta6", "Evt10", "DT-2"),  # P-DATA-TF PDU recv
            ("Sta6", "Evt11", "AR-1"),  # A-RELEASE rq primitive
            ("Sta7", "Evt13", "AR-3"),  # A-RELEASE-RP PDU recv
        ]

        assert self.fsm.current_state == "Sta1"

        scp.shutdown()

    def test_release_AR6(self):
        """Test receive P-DATA-TF while waiting for A-RELEASE-RP."""

        # Requestor sends A-RELEASE-RQ, acceptor sends P-DATA-TF then
        #   A-RELEASE-RP
        # Patch AR-4 to also send a P-DATA-TF
        def AR_4(dul):
            # Send C-ECHO-RQ
            dul.socket.send(p_data_tf)

            # Normal release response
            primitive = dul.to_provider_queue.get(False)
            pdu = A_RELEASE_RP()
            pdu.from_primitive(primitive)
            # Callback
            dul.socket.send(pdu.encode())
            dul.artim_timer.start()
            return "Sta13"

        # In this case the association acceptor will hit AR_4
        FINITE_STATE.ACTIONS["AR-4"] = ("Bluh", AR_4, "Sta13")

        self.ae = ae = AE()
        ae.add_supported_context(Verification)
        scp = ae.start_server(("localhost", 11112), block=False)

        assert self.fsm.current_state == "Sta1"

        self.assoc.start()

        timeout = 0
        while (
            not self.assoc.is_established
            and not self.assoc.is_rejected
            and not self.assoc.is_aborted
            and not self.assoc.dul._kill_thread
            and timeout < 10
        ):
            time.sleep(0.05)
            timeout += 0.05

        self.assoc.release()

        timeout = 0
        while self.fsm.current_state != "Sta1" and timeout < 10:
            time.sleep(0.05)
            timeout += 0.05

        assert self.fsm._transitions == [
            "Sta4",  # Waiting for connection to complete
            "Sta5",  # Waiting for A-ASSOC-AC or -RJ PDU
            "Sta6",  # Assoc established
            "Sta7",
            "Sta7",  # Waiting for A-RELEASE-RP PDU
            "Sta1",  # Idle
        ]
        assert self.fsm._changes == [
            ("Sta1", "Evt1", "AE-1"),  # A-ASSOC rq primitive
            ("Sta4", "Evt2", "AE-2"),  # connection confirmed
            ("Sta5", "Evt3", "AE-3"),  # A-ASSOC-AC PDU recv
            ("Sta6", "Evt11", "AR-1"),  # A-RELEASE rq primitive
            ("Sta7", "Evt10", "AR-6"),  # P-DATA-TF PDU recv
            ("Sta7", "Evt13", "AR-3"),  # A-RELEASE-RP PDU recv
        ]

        assert self.fsm.current_state == "Sta1"

        scp.shutdown()

    def test_release_AR7(self):
        """Test receive P-DATA primitive after A-RELEASE-RQ PDU."""

        def AR_2(dul):
            """AR-2 occurs when an A-RELEASE-RQ PDU is received."""
            # Add P-DATA primitive request
            primitive = C_ECHO()
            primitive.MessageID = 1
            primitive.AffectedSOPClassUID = Verification

            # Send C-ECHO request to the peer via DIMSE and wait for the response
            dul.assoc.dimse.send_msg(primitive, 1)

            pdu = dul._recv_pdu.get(False)
            primitive = pdu.to_primitive()

            # Normal AR2 response
            dul.to_user_queue.put(primitive)
            return "Sta8"

        # In this case the association acceptor will hit AR_2
        FINITE_STATE.ACTIONS["AR-2"] = ("Bluh", AR_2, "Sta8")

        self.ae = ae = AE()
        ae.add_supported_context(Verification)
        scp = ae.start_server(("localhost", 11112), block=False)

        assert self.fsm.current_state == "Sta1"

        self.assoc.start()

        timeout = 0
        while (
            not self.assoc.is_established
            and not self.assoc.is_rejected
            and not self.assoc.is_aborted
            and not self.assoc.dul._kill_thread
            and timeout < 10
        ):
            time.sleep(0.05)
            timeout += 0.05

        self.assoc.release()

        timeout = 0
        while self.fsm.current_state != "Sta1" and timeout < 10:
            time.sleep(0.05)
            timeout += 0.05

        assert self.fsm._transitions == [
            "Sta4",  # Waiting for connection to complete
            "Sta5",  # Waiting for A-ASSOC-AC or -RJ PDU
            "Sta6",  # Assoc established
            "Sta7",
            "Sta7",  # Waiting for A-RELEASE-RP PDU
            "Sta1",  # Idle
        ]
        assert self.fsm._changes == [
            ("Sta1", "Evt1", "AE-1"),  # A-ASSOC rq primitive
            ("Sta4", "Evt2", "AE-2"),  # connection confirmed
            ("Sta5", "Evt3", "AE-3"),  # A-ASSOC-AC PDU recv
            ("Sta6", "Evt11", "AR-1"),  # A-RELEASE rq primitive
            ("Sta7", "Evt10", "AR-6"),  # P-DATA-TF PDU recv
            ("Sta7", "Evt13", "AR-3"),  # A-RELEASE-RP PDU recv
        ]

        assert self.fsm.current_state == "Sta1"

        scp.shutdown()


class TestStateMachineFunctionalAcceptor:
    """Functional tests for StateMachine as association acceptor."""

    def setup_method(self):
        """Run prior to each test"""
        self.ae = None

        ae = AE()
        ae.add_requested_context(Verification)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        assoc = Association(ae, mode="requestor")
        assoc.set_socket(AssociationSocket(assoc, address=AddressInformation("", 0)))

        # Association Acceptor object -> remote AE
        assoc.acceptor.ae_title = "ANY_SCU"
        assoc.acceptor.address_info = AddressInformation("localhost", 11112)

        # Association Requestor object -> local AE
        assoc.requestor.address_info = AddressInformation("localhost", 11113)
        assoc.requestor.ae_title = ae.ae_title
        assoc.requestor.maximum_length = 16382
        assoc.requestor.implementation_class_uid = ae.implementation_class_uid
        assoc.requestor.implementation_version_name = ae.implementation_version_name

        cx = build_context(Verification)
        cx.context_id = 1
        assoc.requestor.requested_contexts = [cx]

        self.assoc = assoc
        self.fsm = self.monkey_patch(assoc.dul.state_machine)

        self.orig_entry = FINITE_STATE.ACTIONS["AE-2"]

    def teardown_method(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

        FINITE_STATE.ACTIONS["AE-2"] = self.orig_entry

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
        self.ae = ae = AE()
        ae.add_supported_context(Verification)
        scp = ae.start_server(("localhost", 11112), block=False)

        assert self.fsm.current_state == "Sta1"

        def AE_2(dul):
            conn = dul.to_provider_queue.get(False)
            pdu = A_ASSOCIATE_RQ()
            pdu.from_primitive(conn.request)
            pdu.protocol_version = 0x0002
            bytestream = pdu.encode()
            dul.socket.send(bytestream)
            return "Sta5"

        FINITE_STATE.ACTIONS["AE-2"] = ("Bluh", AE_2, "Sta5")

        self.assoc.start()

        timeout = 0
        while (
            not self.assoc.is_established
            and not self.assoc.is_rejected
            and not self.assoc.is_aborted
            and not self.assoc.dul._kill_thread
            and timeout < 10
        ):
            time.sleep(0.05)
            timeout += 0.05

        assert self.assoc.is_rejected
        assert self.assoc.acceptor.primitive.result == 0x01
        assert self.assoc.acceptor.primitive.result_source == 0x02
        assert self.assoc.acceptor.primitive.diagnostic == 0x02

        timeout = 0
        while self.fsm.current_state != "Sta1" and timeout < 10:
            time.sleep(0.05)
            timeout += 0.05

        assert self.fsm.current_state == "Sta1"

        scp.shutdown()


class TestEventHandling:
    """Test the FSM event handlers."""

    def setup_method(self):
        self.ae = None

    def teardown_method(self):
        if self.ae:
            self.ae.shutdown()

    def test_no_handlers(self):
        """Test with no handlers bound."""
        self.ae = ae = AE()
        ae.add_supported_context("1.2.840.10008.1.1")
        ae.add_requested_context("1.2.840.10008.1.1")
        scp = ae.start_server(("localhost", 11112), block=False)
        assert scp.get_handlers(evt.EVT_FSM_TRANSITION) == []

        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established
        assert assoc.get_handlers(evt.EVT_FSM_TRANSITION) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_FSM_TRANSITION) == []

        assoc.release()

        scp.shutdown()

    def test_transition_acceptor(self):
        """Test EVT_FSM_TRANSITION as acceptor."""
        triggered = []

        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context("1.2.840.10008.1.1")
        ae.add_requested_context("1.2.840.10008.1.1")
        handlers = [(evt.EVT_FSM_TRANSITION, handle)]
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)
        assert scp.get_handlers(evt.EVT_FSM_TRANSITION) == [(handle, None)]

        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established
        assert assoc.get_handlers(evt.EVT_FSM_TRANSITION) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_FSM_TRANSITION) == [(handle, None)]

        assoc.release()
        timeout = 0
        while scp.active_associations and timeout < 10:
            time.sleep(0.05)
            timeout += 0.05

        for event in triggered:
            assert hasattr(event, "current_state")
            assert hasattr(event, "fsm_event")
            assert hasattr(event, "action")
            assert hasattr(event, "next_state")
            assert isinstance(event.assoc, Association)
            assert isinstance(event.timestamp, datetime.datetime)
            assert event.event.name == "EVT_FSM_TRANSITION"
            assert event.event.description == "State machine about to transition"

        states = [ee.current_state for ee in triggered]
        assert states[:6] == ["Sta1", "Sta2", "Sta3", "Sta6", "Sta8", "Sta13"]

        scp.shutdown()

    def test_transition_acceptor_bind(self):
        """Test EVT_FSM_TRANSITION as acceptor."""
        triggered = []

        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context("1.2.840.10008.1.1")
        ae.add_requested_context("1.2.840.10008.1.1")
        scp = ae.start_server(("localhost", 11112), block=False)
        assert scp.get_handlers(evt.EVT_FSM_TRANSITION) == []

        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established

        time.sleep(0.5)

        child = scp.active_associations[0]
        assert child.dul.state_machine.current_state == "Sta6"
        assert assoc.get_handlers(evt.EVT_FSM_TRANSITION) == []
        assert child.get_handlers(evt.EVT_FSM_TRANSITION) == []

        scp.bind(evt.EVT_FSM_TRANSITION, handle)
        assert scp.get_handlers(evt.EVT_FSM_TRANSITION) == [(handle, None)]
        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_FSM_TRANSITION) == [(handle, None)]

        assoc.release()
        timeout = 0
        while scp.active_associations and timeout < 10:
            time.sleep(0.05)
            timeout += 0.05

        for event in triggered:
            assert hasattr(event, "current_state")
            assert hasattr(event, "fsm_event")
            assert hasattr(event, "action")
            assert hasattr(event, "next_state")
            assert isinstance(event.assoc, Association)
            assert isinstance(event.timestamp, datetime.datetime)

        states = [ee.current_state for ee in triggered]
        assert states[:3] == ["Sta6", "Sta8", "Sta13"]

    def test_transition_acceptor_unbind(self):
        """Test EVT_FSM_TRANSITION as acceptor."""
        triggered = []

        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context("1.2.840.10008.1.1")
        ae.add_requested_context("1.2.840.10008.1.1")
        handlers = [(evt.EVT_FSM_TRANSITION, handle)]
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)

        # Confirm that the handler is bound
        assert scp.get_handlers(evt.EVT_FSM_TRANSITION) == [(handle, None)]

        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established

        time.sleep(0.5)

        # Acceptor association
        child = scp.active_associations[0]
        # At this point we *must* have gone Sta1 -> Sta2 -> Sta3 -> Sta6
        assert child.dul.state_machine.current_state == "Sta6"
        assert child.get_handlers(evt.EVT_FSM_TRANSITION) == [(handle, None)]

        # Unbind the handler and confirm that its unbound
        scp.unbind(evt.EVT_FSM_TRANSITION, handle)
        assert scp.get_handlers(evt.EVT_FSM_TRANSITION) == []
        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_FSM_TRANSITION) == []

        # Should go Sta6 -> Sta8 -> Sta13
        assoc.release()
        timeout = 0
        while scp.active_associations and timeout < 10:
            time.sleep(0.05)
            timeout += 0.05

        time.sleep(0.5)

        for event in triggered:
            assert hasattr(event, "current_state")
            assert hasattr(event, "fsm_event")
            assert hasattr(event, "action")
            assert hasattr(event, "next_state")
            assert isinstance(event.assoc, Association)
            assert isinstance(event.timestamp, datetime.datetime)

        states = [ee.current_state for ee in triggered]
        print(states)
        assert states[:3] == ["Sta1", "Sta2", "Sta3"]

        scp.shutdown()

    def test_transition_requestor(self):
        """Test EVT_FSM_TRANSITION as requestor."""
        triggered = []

        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context("1.2.840.10008.1.1")
        ae.add_requested_context("1.2.840.10008.1.1")
        handlers = [(evt.EVT_FSM_TRANSITION, handle)]
        scp = ae.start_server(("localhost", 11112), block=False)

        assoc = ae.associate("localhost", 11112, evt_handlers=handlers)
        assert assoc.get_handlers(evt.EVT_FSM_TRANSITION) == [(handle, None)]
        assert assoc.is_established
        assert scp.get_handlers(evt.EVT_FSM_TRANSITION) == []
        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_FSM_TRANSITION) == []
        assoc.release()
        timeout = 0
        while not assoc.is_released and timeout < 10:
            time.sleep(0.05)
            timeout += 0.05

        for event in triggered:
            assert hasattr(event, "current_state")
            assert hasattr(event, "fsm_event")
            assert hasattr(event, "action")
            assert hasattr(event, "next_state")
            assert isinstance(event.assoc, Association)
            assert isinstance(event.timestamp, datetime.datetime)

        states = [ee.current_state for ee in triggered]
        assert states[:5] == ["Sta1", "Sta4", "Sta5", "Sta6", "Sta7"]

        scp.shutdown()

    def test_transition_requestor_bind(self):
        """Test EVT_FSM_TRANSITION as requestor."""
        triggered = []

        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context("1.2.840.10008.1.1")
        ae.add_requested_context("1.2.840.10008.1.1")
        scp = ae.start_server(("localhost", 11112), block=False)

        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established
        assert assoc.get_handlers(evt.EVT_FSM_TRANSITION) == []

        assoc.bind(evt.EVT_FSM_TRANSITION, handle)
        assert assoc.get_handlers(evt.EVT_FSM_TRANSITION) == [(handle, None)]

        assert scp.get_handlers(evt.EVT_FSM_TRANSITION) == []
        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_FSM_TRANSITION) == []

        assoc.release()
        timeout = 0
        while not assoc.is_released and timeout < 10:
            time.sleep(0.05)
            timeout += 0.05

        for event in triggered:
            assert hasattr(event, "current_state")
            assert hasattr(event, "fsm_event")
            assert hasattr(event, "action")
            assert hasattr(event, "next_state")
            assert isinstance(event.assoc, Association)
            assert isinstance(event.timestamp, datetime.datetime)

        states = [ee.current_state for ee in triggered]
        assert states[:2] == ["Sta6", "Sta7"]

        scp.shutdown()

    def test_transition_requestor_unbind(self):
        """Test EVT_FSM_TRANSITION as requestor."""
        triggered = []

        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context("1.2.840.10008.1.1")
        ae.add_requested_context("1.2.840.10008.1.1")
        handlers = [(evt.EVT_FSM_TRANSITION, handle)]
        scp = ae.start_server(("localhost", 11112), block=False)

        assoc = ae.associate("localhost", 11112, evt_handlers=handlers)
        assert assoc.is_established
        assert assoc.get_handlers(evt.EVT_FSM_TRANSITION) == [(handle, None)]

        assoc.unbind(evt.EVT_FSM_TRANSITION, handle)
        assert assoc.get_handlers(evt.EVT_FSM_TRANSITION) == []

        assert scp.get_handlers(evt.EVT_FSM_TRANSITION) == []
        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_FSM_TRANSITION) == []

        assoc.release()
        timeout = 0
        while not assoc.is_released and timeout < 10:
            time.sleep(0.05)
            timeout += 0.05

        for event in triggered:
            assert hasattr(event, "current_state")
            assert hasattr(event, "fsm_event")
            assert hasattr(event, "action")
            assert hasattr(event, "next_state")
            assert isinstance(event.assoc, Association)
            assert isinstance(event.timestamp, datetime.datetime)

        states = [ee.current_state for ee in triggered]
        assert states[:3] == ["Sta1", "Sta4", "Sta5"]

        scp.shutdown()

    def test_transition_raises(self, caplog):
        """Test the handler for EVT_FSM_TRANSITION raising exception."""

        def handle(event):
            raise NotImplementedError("Exception description")

        self.ae = ae = AE()
        ae.add_supported_context(Verification)
        ae.add_requested_context(Verification)
        handlers = [(evt.EVT_FSM_TRANSITION, handle)]
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)

        with caplog.at_level(logging.ERROR, logger="pynetdicom"):
            assoc = ae.associate("localhost", 11112)
            assert assoc.is_established
            assoc.release()

            timeout = 0
            while scp.active_associations and timeout < 10:
                time.sleep(0.05)
                timeout += 0.05

            scp.shutdown()

            msg = (
                "Exception raised in user's 'evt.EVT_FSM_TRANSITION' event "
                "handler 'handle'"
            )
            assert msg in caplog.text
            assert "Exception description" in caplog.text
