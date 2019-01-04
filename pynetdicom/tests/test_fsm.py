"""Unit tests for fsm.py"""

import logging
try:
    import queue
except ImportError:
    import Queue as queue  # Python 2 compatibility
import socket
import threading
import time

import pytest

from pynetdicom import AE, build_context
from pynetdicom.association import Association
from pynetdicom.fsm import *
from pynetdicom.sop_class import VerificationSOPClass
from pynetdicom.utils import validate_ae_title
from .dummy_c_scp import DummyVerificationSCP, DummyBaseSCP


LOGGER = logging.getLogger("pynetdicom")
LOGGER.setLevel(logging.CRITICAL)
#LOGGER.setLevel(logging.DEBUG)


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
                r"DUL State Machine received an invalid event '{}' for the "
                r"current state '{}'".format(event, state)
            )
            with pytest.raises(KeyError, match=msg):
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

        while self.assoc.is_established:
            time.sleep(0.05)

        while not self.assoc.is_aborted:
            time.sleep(0.05)

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
