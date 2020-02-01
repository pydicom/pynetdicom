#!/usr/bin/env python
"""Test DIMSE service provider operations.

TODO: Add testing of maximum pdu length flow from assoc negotiation
"""
from datetime import datetime
try:
    import queue
except ImportError:
    import Queue as queue
from io import BytesIO
import logging
import sys
import threading
import time

import pytest

from pydicom.dataset import Dataset

from pynetdicom import evt, AE, Association, _config, debug_logger
from pynetdicom.association import ServiceUser
from pynetdicom.dimse import DIMSEServiceProvider
from pynetdicom.dimse_messages import (
    C_STORE_RQ, C_STORE_RSP, C_FIND_RQ, C_FIND_RSP, C_GET_RQ, C_GET_RSP,
    C_MOVE_RQ, C_MOVE_RSP, C_ECHO_RQ,C_ECHO_RSP, C_CANCEL_RQ,
    N_EVENT_REPORT_RQ, N_EVENT_REPORT_RSP, N_GET_RQ, N_GET_RSP, N_SET_RQ,
    N_SET_RSP, N_ACTION_RQ, N_ACTION_RSP, N_CREATE_RQ, N_CREATE_RSP,
    N_DELETE_RQ, N_DELETE_RSP
)
from pynetdicom.dimse_primitives import (
    C_STORE, C_ECHO, C_GET, C_MOVE, C_FIND, N_EVENT_REPORT, N_SET, N_GET,
    N_ACTION, N_CREATE, N_DELETE, C_CANCEL
)
from pynetdicom.dsutils import encode
from pynetdicom.events import Event
from pynetdicom.pdu_primitives import P_DATA
from pynetdicom.pdu import P_DATA_TF
from .encoded_dimse_msg import c_store_ds
from .encoded_dimse_n_msg import (
    n_er_rq_ds, n_er_rsp_ds, n_get_rsp_ds, n_set_rq_ds, n_set_rsp_ds,
    n_action_rq_ds, n_action_rsp_ds, n_create_rq_ds, n_create_rsp_ds
)
from .encoded_pdu_items import p_data_tf
from pynetdicom.sop_class import (
    VerificationSOPClass, BasicGrayscalePrintManagementMetaSOPClass,
    PrinterSOPClass
)


#debug_logger()


class DummyAssociation(object):
    def __init__(self):
        self.ae = AE()
        self.mode = None
        self.dul = DummyDUL()
        self.requestor = ServiceUser(self, 'requestor')
        self.requestor.port = 11112
        self.requestor.ae_title = b'TEST_LOCAL      '
        self.requestor.address = '127.0.0.1'
        self.requestor.maximum_length = 31682
        self.acceptor = ServiceUser(self, 'acceptor')
        self.acceptor.ae_title = b'TEST_REMOTE     '
        self.acceptor.port = 11113
        self.acceptor.address = '127.0.0.2'
        self.acse_timeout = 11
        self.dimse_timeout = 1
        self.network_timeout = 13
        self.is_killed = False
        self.is_aborted = False
        self.is_established = False
        self.is_rejected = False
        self.is_released = False
        self.is_acceptor = False
        self.is_requestor = True
        self._handlers = {}

    def abort(self):
        self.is_aborted = True
        self.kill()

    def kill(self):
        self.is_killed = True

    @property
    def requested_contexts(self):
        return self.requestor.get_contexts('requested')

    @property
    def supported_contexts(self):
        return self.requestor.get_contexts('supported')

    def get_handlers(self, event):
        if event not in self._handlers:
            return []

        return self._handlers[event]


class DummyDUL(object):
    """Dummy DUL class for testing DIMSE provider"""
    def __init__(self):
        self.event_queue = queue.Queue()

    @staticmethod
    def is_alive(): return True

    @staticmethod
    def send_pdu(pdv):
        """Dummy Send method to test DIMSEServiceProvider.Send"""
        pass

    @staticmethod
    def receive_pdu():
        """Dummy Receive method to test DIMSEServiceProvider.Receive"""
        pass

    @staticmethod
    def peek_next_pdu():
        return 0x01


REFERENCE_MSG = [
    (C_ECHO(), ('C_ECHO_RQ', 'C_ECHO_RSP')),
    (C_STORE(), ('C_STORE_RQ', 'C_STORE_RSP')),
    (C_FIND(), ('C_FIND_RQ', 'C_FIND_RSP')),
    (C_GET(), ('C_GET_RQ', 'C_GET_RSP')),
    (C_MOVE(), ('C_MOVE_RQ', 'C_MOVE_RSP')),
    (C_CANCEL(), (None, 'C_CANCEL_RQ')),
    (N_EVENT_REPORT(), ('N_EVENT_REPORT_RQ', 'N_EVENT_REPORT_RSP')),
    (N_GET(), ('N_GET_RQ', 'N_GET_RSP')),
    (N_SET(), ('N_SET_RQ', 'N_SET_RSP')),
    (N_ACTION(), ('N_ACTION_RQ', 'N_ACTION_RSP')),
    (N_CREATE(), ('N_CREATE_RQ', 'N_CREATE_RSP')),
    (N_DELETE(), ('N_DELETE_RQ', 'N_DELETE_RSP')),
]


class TestDIMSEProvider(object):
    """Test DIMSE service provider operations."""
    def setup(self):
        """Set up"""
        self.dimse = DIMSEServiceProvider(DummyAssociation())

    def test_receive_not_pdata(self):
        """Test we get back None if not a P_DATA"""
        assert self.dimse.get_msg(True) == (None, None)

    def test_peek_empty(self):
        """Test peek_msg with nothing on the queue."""
        dimse = DIMSEServiceProvider(DummyAssociation())
        assert dimse.peek_msg() == (None, None)

    def test_peek_item(self):
        """Test peek_msg with nothing on the queue."""
        dimse = DIMSEServiceProvider(DummyAssociation())
        primitive = C_STORE()
        dimse.msg_queue.put((14, primitive))
        assert dimse.peek_msg() == (14, primitive)

    def test_invalid_message(self):
        """Test that an invalid message kills the association."""
        class DummyDUL(object):
            def __init__(self):
                self.event_queue = queue.Queue()

        dimse = DIMSEServiceProvider(DummyAssociation())

        p_data_tf = (
            #     |   | length
            b"\x04\x00\x00\x00\x00\x4E" # P-DATA-TF 78
            b"\x00\x00\x00\x4a\x01" # PDV Item 70
            b"\x03"  # PDV: 2 -> 69
            # C-ECHO-RQ
            # CommandGroupLen | len 4         | value 64
            b"\x00\x00\x00\x00\x04\x00\x00\x00\x40\x00\x00\x00"  # 12
            #  AffSOPClass    | len 18        | value
            b"\x00\x00\x02\x00\x12\x00\x00\x00"
            b"\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x31\x2e"
            b"\x31\x00"  # 26
            # CommandField    | len 2         | 0x0030 -> C-ECHO-RQ
            b"\x00\x00\x00\x01\x02\x00\x00\x00\x30\x00"  # 10
            # Message ID      | len 6         | -> should be invalid
            b"\x00\x00\x10\x01\x06\x00\x00\x00\xff\xff\xff\xff\xff\xff"  # 14
            # CommandDSType   | len 2         | no DS
            b"\x00\x00\x00\x08\x02\x00\x00\x00\x01\x01"  # 10
        )
        pdata = P_DATA_TF()
        pdata.decode(p_data_tf)
        pdata = pdata.to_primitive()
        # Should send Evt19 due to invalid message
        dimse.receive_primitive(pdata)
        assert dimse.assoc.dul.event_queue.get() == 'Evt19'


class TestEventHandlingAcceptor(object):
    """Test the transport events and handling as acceptor."""
    def setup(self):
        self.ae = None
        _config.LOG_HANDLER_LEVEL = 'none'

    def teardown(self):
        if self.ae:
            self.ae.shutdown()

        _config.LOG_HANDLER_LEVEL = 'standard'

    def test_no_handlers(self):
        """Test with no transport event handlers bound."""
        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)
        assert scp.get_handlers(evt.EVT_DIMSE_RECV) == []
        assert scp.get_handlers(evt.EVT_DIMSE_SENT) == []
        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established
        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_DIMSE_RECV) == []
        assert scp.get_handlers(evt.EVT_DIMSE_SENT) == []
        assert assoc.get_handlers(evt.EVT_DIMSE_RECV) == []
        assert assoc.get_handlers(evt.EVT_DIMSE_SENT) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_DIMSE_RECV) == []
        assert child.get_handlers(evt.EVT_DIMSE_SENT) == []

        assoc.release()
        scp.shutdown()

    def test_dimse_sent(self):
        """Test binding to EVT_DIMSE_SENT."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_DIMSE_SENT, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)
        assert scp.get_handlers(evt.EVT_DIMSE_SENT) == [(handle, None)]

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_DIMSE_SENT) == [(handle, None)]
        assert assoc.get_handlers(evt.EVT_DIMSE_SENT) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_DIMSE_SENT) == [(handle, None)]

        assoc.send_c_echo()

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert event.event.name == 'EVT_DIMSE_SENT'

        assert isinstance(triggered[0].message, C_ECHO_RSP)

        scp.shutdown()

    def test_dimse_sent_bind(self):
        """Test binding to EVT_DIMSE_SENT."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_DIMSE_SENT, handle)]
        scp = ae.start_server(('', 11112), block=False)
        assert scp.get_handlers(evt.EVT_DIMSE_SENT) == []

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        assoc.send_c_echo(msg_id=12)

        scp.bind(evt.EVT_DIMSE_SENT, handle)

        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_DIMSE_SENT) == [(handle, None)]
        assert assoc.get_handlers(evt.EVT_DIMSE_SENT) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_DIMSE_SENT) == [(handle, None)]

        assoc.send_c_echo(msg_id=21)

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert event.event.name == 'EVT_DIMSE_SENT'

        assert isinstance(triggered[0].message, C_ECHO_RSP)
        assert triggered[0].message.command_set.MessageIDBeingRespondedTo == 21

        scp.shutdown()

    def test_dimse_sent_unbind(self):
        """Test unbinding EVT_DIMSE_SENT."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_DIMSE_SENT, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)
        assert scp.get_handlers(evt.EVT_DIMSE_SENT) == [(handle, None)]

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_DIMSE_SENT) == [(handle, None)]

        assert assoc.get_handlers(evt.EVT_DIMSE_SENT) == []

        assoc.send_c_echo(msg_id=12)

        scp.unbind(evt.EVT_DIMSE_SENT, handle)

        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_DIMSE_SENT) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_DIMSE_SENT) == []

        assoc.send_c_echo(msg_id=21)

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert event.event.name == 'EVT_DIMSE_SENT'

        assert isinstance(triggered[0].message, C_ECHO_RSP)
        assert triggered[0].message.command_set.MessageIDBeingRespondedTo == 12

        scp.shutdown()

    def test_dimse_sent_raises(self, caplog):
        """Test the handler for EVT_DIMSE_SENT raising exception."""
        def handle(event):
            raise NotImplementedError("Exception description")

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_DIMSE_SENT, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        with caplog.at_level(logging.ERROR, logger='pynetdicom'):
            assoc = ae.associate('localhost', 11112)
            assert assoc.is_established
            assoc.send_c_echo()
            assoc.release()

            while scp.active_associations:
                time.sleep(0.05)

            scp.shutdown()

            msg = (
                "Exception raised in user's 'evt.EVT_DIMSE_SENT' event handler"
                " 'handle'"
            )
            assert msg in caplog.text
            assert "Exception description" in caplog.text

    def test_dimse_recv(self):
        """Test starting bound to EVT_DIMSE_RECV."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_DIMSE_RECV, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)
        assert scp.get_handlers(evt.EVT_DIMSE_RECV) == [(handle, None)]

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_DIMSE_RECV) == [(handle, None)]
        assert assoc.get_handlers(evt.EVT_DIMSE_RECV) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_DIMSE_RECV) == [(handle, None)]

        assoc.send_c_echo()

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert isinstance(triggered[0].message, C_ECHO_RQ)
        assert event.event.name == 'EVT_DIMSE_RECV'

        scp.shutdown()

    def test_dimse_recv_bind(self):
        """Test binding to EVT_DIMSE_RECV."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)
        assert scp.get_handlers(evt.EVT_DIMSE_RECV) == []

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1

        assoc.send_c_echo(msg_id=12)

        scp.bind(evt.EVT_DIMSE_RECV, handle)

        assert scp.get_handlers(evt.EVT_DIMSE_RECV) == [(handle, None)]
        assert assoc.get_handlers(evt.EVT_DIMSE_RECV) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_DIMSE_RECV) == [(handle, None)]

        assoc.send_c_echo(msg_id=21)

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert isinstance(triggered[0].message, C_ECHO_RQ)
        assert event.event.name == 'EVT_DIMSE_RECV'
        assert triggered[0].message.command_set.MessageID == 21

        scp.shutdown()

    def test_dimse_recv_unbind(self):
        """Test unbinding to EVT_DIMSE_RECV."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_DIMSE_RECV, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)
        assert scp.get_handlers(evt.EVT_DIMSE_RECV) == [(handle, None)]

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_DIMSE_RECV) == [(handle, None)]

        assoc.send_c_echo(msg_id=12)

        scp.unbind(evt.EVT_DIMSE_RECV, handle)

        assert scp.get_handlers(evt.EVT_DIMSE_RECV) == []
        assert assoc.get_handlers(evt.EVT_DIMSE_RECV) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_DIMSE_RECV) == []

        assoc.send_c_echo(msg_id=21)

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert isinstance(triggered[0].message, C_ECHO_RQ)
        assert event.event.name == 'EVT_DIMSE_RECV'
        assert triggered[0].message.command_set.MessageID == 12

        scp.shutdown()

    def test_dimse_recv_raises(self, caplog):
        """Test the handler for EVT_DIMSE_RECV raising exception."""
        def handle(event):
            raise NotImplementedError("Exception description")

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_DIMSE_RECV, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        with caplog.at_level(logging.ERROR, logger='pynetdicom'):
            assoc = ae.associate('localhost', 11112)
            assert assoc.is_established
            assoc.send_c_echo()
            assoc.release()

            while scp.active_associations:
                time.sleep(0.05)

            scp.shutdown()

            msg = (
                "Exception raised in user's 'evt.EVT_DIMSE_RECV' event handler"
                " 'handle'"
            )
            assert msg in caplog.text
            assert "Exception description" in caplog.text


class TestEventHandlingRequestor(object):
    """Test the transport events and handling as requestor."""
    def setup(self):
        self.ae = None
        _config.LOG_HANDLER_LEVEL = 'none'

    def teardown(self):
        if self.ae:
            self.ae.shutdown()

        _config.LOG_HANDLER_LEVEL = 'standard'

    def test_no_handlers(self):
        """Test with no transport event handlers bound."""
        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)
        assert scp.get_handlers(evt.EVT_DIMSE_RECV) == []
        assert scp.get_handlers(evt.EVT_DIMSE_SENT) == []
        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established
        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_DIMSE_RECV) == []
        assert scp.get_handlers(evt.EVT_DIMSE_SENT) == []
        assert assoc.get_handlers(evt.EVT_DIMSE_RECV) == []
        assert assoc.get_handlers(evt.EVT_DIMSE_SENT) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_DIMSE_RECV) == []
        assert child.get_handlers(evt.EVT_DIMSE_SENT) == []

        assoc.release()
        scp.shutdown()

    def test_dimse_sent(self):
        """Test binding to EVT_DIMSE_SENT."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_DIMSE_SENT, handle)]
        scp = ae.start_server(('', 11112), block=False)
        assert scp.get_handlers(evt.EVT_DIMSE_SENT) == []

        assoc = ae.associate('localhost', 11112, evt_handlers=handlers)
        assert assoc.is_established
        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_DIMSE_SENT) == []
        assert assoc.get_handlers(evt.EVT_DIMSE_SENT) == [(handle, None)]

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_DIMSE_SENT) == []

        assoc.send_c_echo()
        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert event.event.name == 'EVT_DIMSE_SENT'

        assert isinstance(triggered[0].message, C_ECHO_RQ)

        scp.shutdown()

    def test_dimse_sent_bind(self):
        """Test binding to EVT_DIMSE_SENT."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_DIMSE_SENT, handle)]
        scp = ae.start_server(('', 11112), block=False)
        assert scp.get_handlers(evt.EVT_DIMSE_SENT) == []

        assoc = ae.associate('localhost', 11112)
        assert assoc.get_handlers(evt.EVT_DIMSE_SENT) == []
        assert assoc.is_established
        assoc.send_c_echo(msg_id=12)

        assoc.bind(evt.EVT_DIMSE_SENT, handle)

        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_DIMSE_SENT) == []
        assert assoc.get_handlers(evt.EVT_DIMSE_SENT) == [(handle, None)]

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_DIMSE_SENT) == []

        assoc.send_c_echo(msg_id=21)

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert event.event.name == 'EVT_DIMSE_SENT'

        assert isinstance(triggered[0].message, C_ECHO_RQ)
        assert triggered[0].message.command_set.MessageID == 21

        scp.shutdown()

    def test_dimse_sent_unbind(self):
        """Test unbinding EVT_DIMSE_SENT."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_DIMSE_SENT, handle)]
        scp = ae.start_server(('', 11112), block=False)
        assert scp.get_handlers(evt.EVT_DIMSE_SENT) == []

        assoc = ae.associate('localhost', 11112, evt_handlers=handlers)
        assert assoc.is_established
        assoc.send_c_echo(msg_id=12)
        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_DIMSE_SENT) == []
        assert assoc.get_handlers(evt.EVT_DIMSE_SENT) == [(handle, None)]

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_DIMSE_SENT) == []

        assoc.unbind(evt.EVT_DIMSE_SENT, handle)

        assert assoc.get_handlers(evt.EVT_DIMSE_SENT) == []

        assoc.send_c_echo(msg_id=21)

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        assert triggered[0].message.command_set.MessageID == 12

        scp.shutdown()

    def test_dimse_sent_raises(self, caplog):
        """Test the handler for EVT_DIMSE_SENT raising exception."""
        def handle(event):
            raise NotImplementedError("Exception description")

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_DIMSE_SENT, handle)]
        scp = ae.start_server(('', 11112), block=False)

        with caplog.at_level(logging.ERROR, logger='pynetdicom'):
            assoc = ae.associate('localhost', 11112, evt_handlers=handlers)
            assert assoc.is_established
            assoc.send_c_echo()
            assoc.release()

            while scp.active_associations:
                time.sleep(0.05)

            scp.shutdown()

            msg = (
                "Exception raised in user's 'evt.EVT_DIMSE_SENT' event handler"
                " 'handle'"
            )
            assert msg in caplog.text
            assert "Exception description" in caplog.text

    def test_dimse_recv(self):
        """Test starting bound to EVT_DIMSE_RECV."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_DIMSE_RECV, handle)]
        scp = ae.start_server(('', 11112), block=False)
        assert scp.get_handlers(evt.EVT_DIMSE_RECV) == []

        assoc = ae.associate('localhost', 11112, evt_handlers=handlers)
        assert assoc.is_established
        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_DIMSE_RECV) == []
        assert assoc.get_handlers(evt.EVT_DIMSE_RECV) == [(handle, None)]

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_DIMSE_RECV) == []

        assoc.send_c_echo()

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert isinstance(triggered[0].message, C_ECHO_RSP)
        assert event.event.name == 'EVT_DIMSE_RECV'

        scp.shutdown()

    def test_dimse_recv_bind(self):
        """Test binding to EVT_DIMSE_RECV."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)
        assert scp.get_handlers(evt.EVT_DIMSE_RECV) == []

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert len(scp.active_associations) == 1
        assert assoc.get_handlers(evt.EVT_DIMSE_RECV) == []
        assoc.send_c_echo(msg_id=12)

        assoc.bind(evt.EVT_DIMSE_RECV, handle)

        assert scp.get_handlers(evt.EVT_DIMSE_RECV) == []
        assert assoc.get_handlers(evt.EVT_DIMSE_RECV) == [(handle, None)]

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_DIMSE_RECV) == []

        assoc.send_c_echo(msg_id=21)

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert isinstance(triggered[0].message, C_ECHO_RSP)
        assert event.event.name == 'EVT_DIMSE_RECV'
        assert triggered[0].message.command_set.MessageIDBeingRespondedTo == 21

        scp.shutdown()

    def test_dimse_recv_unbind(self):
        """Test unbinding to EVT_DIMSE_RECV."""
        triggered = []
        def handle(event):
            triggered.append(event)

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_DIMSE_RECV, handle)]
        scp = ae.start_server(('', 11112), block=False)
        assert scp.get_handlers(evt.EVT_DIMSE_RECV) == []

        assoc = ae.associate('localhost', 11112, evt_handlers=handlers)
        assert assoc.is_established
        assert assoc.get_handlers(evt.EVT_DIMSE_RECV) == [(handle, None)]
        assoc.send_c_echo(msg_id=12)

        assoc.unbind(evt.EVT_DIMSE_RECV, handle)

        assert len(scp.active_associations) == 1
        assert scp.get_handlers(evt.EVT_DIMSE_RECV) == []
        assert assoc.get_handlers(evt.EVT_DIMSE_RECV) == []

        child = scp.active_associations[0]
        assert child.get_handlers(evt.EVT_DIMSE_RECV) == []

        assoc.send_c_echo(msg_id=21)

        assoc.release()

        while scp.active_associations:
            time.sleep(0.05)

        assert len(triggered) == 1
        event = triggered[0]
        assert isinstance(event, Event)
        assert isinstance(event.assoc, Association)
        assert isinstance(event.timestamp, datetime)
        assert isinstance(triggered[0].message, C_ECHO_RSP)
        assert event.event.name == 'EVT_DIMSE_RECV'
        assert triggered[0].message.command_set.MessageIDBeingRespondedTo == 12

        scp.shutdown()

    def test_dimse_recv_raises(self, caplog):
        """Test the handler for EVT_DIMSE_RECV raising exception."""
        def handle(event):
            raise NotImplementedError("Exception description")

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        handlers = [(evt.EVT_DIMSE_RECV, handle)]
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        with caplog.at_level(logging.ERROR, logger='pynetdicom'):
            assoc = ae.associate('localhost', 11112)
            assert assoc.is_established
            assoc.send_c_echo()
            assoc.release()

            while scp.active_associations:
                time.sleep(0.05)

            scp.shutdown()

            msg = (
                "Exception raised in user's 'evt.EVT_DIMSE_RECV' event handler"
                " 'handle'"
            )
            assert msg in caplog.text
            assert "Exception description" in caplog.text
