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
from pynetdicom import fsm as FINITE_STATE
from pynetdicom.fsm import *
from pynetdicom.dimse_primitives import C_ECHO
from pynetdicom.pdu_primitives import A_RELEASE
from pynetdicom.pdu import A_RELEASE_RQ
from pynetdicom.sop_class import VerificationSOPClass
from pynetdicom.utils import validate_ae_title
from .dummy_c_scp import DummyVerificationSCP, DummyBaseSCP
from .encoded_pdu_items import p_data_tf


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

    @pytest.mark.xfail()
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

    @pytest.mark.xfail()
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

    @pytest.mark.xfail()
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
