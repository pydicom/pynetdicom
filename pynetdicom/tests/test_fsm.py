"""Unit tests for fsm.py"""

import queue
import socket
import threading
import time

import pytest

from pynetdicom import AE
from pynetdicom.association import Association
from pynetdicom.fsm import *
from pynetdicom.sop_class import VerificationSOPClass
from .dummy_c_scp import DummyVerificationSCP, DummyBaseSCP


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


class TestStateMachineFunctional(object):
    """Functional tests for StateMachine."""
    def setup(self):
        """Run prior to each test"""
        self.scp = None

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
        return fsm

    def test_init(self):
        """Test creation of new StateMachine."""
        #self.scp = DummyVerificationSCP()
        #self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        assoc = Association(ae, mode='requestor')

        fsm = self.monkey_patch(assoc.dul.state_machine)
        assert fsm.current_state == 'Sta1'
        assert fsm.dul == assoc.dul

        #self.scp.stop()
