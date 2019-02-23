"""Unit tests for the events module."""

from collections import namedtuple
from datetime import datetime
import logging
import os
import sys
import time

import pytest

from pynetdicom import AE, evt, _config, Association
from pynetdicom.events import (
    Event, trigger, _async_ops_handler, _sop_common_handler,
    _sop_extended_handler, _user_identity_handler, _c_echo_handler,
    _c_get_handler, _c_find_handler, _c_move_handler, _c_store_handler,
    _n_action_handler, _n_create_handler, _n_delete_handler,
    _n_event_report_handler, _n_get_handler, _n_set_handler
)
from pynetdicom.sop_class import VerificationSOPClass

LOGGER = logging.getLogger('pynetdicom')
LOGGER.setLevel(logging.CRITICAL)
LOGGER.setLevel(logging.DEBUG)


def test_intervention_namedtuple():
    """Test the InterventionEvent namedtuple."""
    event = evt.InterventionEvent('some name', 'some description')
    assert event.name == 'some name'
    assert event.description == 'some description'
    assert event.is_intervention is True
    assert event.is_notification is False

def test_notification_namedtuple():
    """Test the NotificationEvent namedtuple."""
    event = evt.NotificationEvent('some name', 'some description')
    assert event.name == 'some name'
    assert event.description == 'some description'
    assert event.is_intervention is False
    assert event.is_notification is True

def test_intervention_global():
    """Test the _INTERVENTION_EVENTS global."""
    assert evt.EVT_C_ECHO in evt._INTERVENTION_EVENTS
    assert evt.EVT_DATA_RECV not in evt._INTERVENTION_EVENTS

def test_notification_global():
    """Test the _NOTIFICATION_EVENTS global."""
    assert evt.EVT_C_ECHO not in evt._NOTIFICATION_EVENTS
    assert evt.EVT_DATA_RECV in evt._NOTIFICATION_EVENTS


class TestEvent(object):
    """Tests for event.Event."""
    def setup(self):
        self.ae = None
        _config.LOG_HANDLER_LEVEL = 'none'

    def teardown(self):
        if self.ae:
            self.ae.shutdown()

        _config.LOG_HANDLER_LEVEL = 'standard'

    def test_init(self):
        """Test initialisation of event.Event."""
        event = evt.Event(None, evt.EVT_C_STORE)
        assert event.assoc is None
        assert event._event == evt.EVT_C_STORE
        assert isinstance(event.timestamp, datetime)
        assert event.name == 'EVT_C_STORE'
        assert isinstance(event.description, str)

        def callable():
            return 'some value'

        event = evt.Event(
            None, evt.EVT_C_STORE, {'aa' : True, 'bb' : False, 'cc' : callable}
        )
        assert event.assoc is None
        assert event._event == evt.EVT_C_STORE
        assert isinstance(event.timestamp, datetime)
        assert event.name == 'EVT_C_STORE'
        assert isinstance(event.description, str)
        assert event.cc() == 'some value'
        assert event.aa is True
        assert event.bb is False

    def test_raises(self):
        """Test property getters raise if not correct event type."""
        event = evt.Event(None, evt.EVT_DATA_RECV)
        msg = (
            r"The corresponding event is not a C-STORE "
            r"request and has no 'Data Set' parameter"
        )
        with pytest.raises(AttributeError, match=msg):
            event.dataset

        msg = (
            r"The corresponding event is not a C-FIND, C-GET or C-MOVE request "
            r"and has no 'Identifier' parameter"
        )
        with pytest.raises(AttributeError, match=msg):
            event.identifier

    def test_is_cancelled_non(self):
        """Test Event.is_cancelled with wrong event type."""
        event = evt.Event(None, evt.EVT_DATA_RECV)
        assert event.is_cancelled is False

        def is_cancelled(msg_id):
            if msg_id in [1, 2, 3]:
                return True

            return False

        # No Message ID
        event = evt.Event(
            None, evt.EVT_DATA_RECV, {'_is_cancelled' : is_cancelled}
        )
        assert event.is_cancelled is False

    def test_is_cancelled(self):
        """Test Event.is_cancelled with correct event type."""
        def is_cancelled(msg_id):
            if msg_id in [1, 2, 3]:
                return True

            return False

        message = namedtuple('Message', ['MessageID'])
        msg = message(1)
        msg2 = message(7)

        event = evt.Event(
            None,
            evt.EVT_DATA_RECV,
            {'_is_cancelled' : is_cancelled, 'request' : msg}
        )
        assert event.is_cancelled is True

        event = evt.Event(
            None,
            evt.EVT_DATA_RECV,
            {'_is_cancelled' : is_cancelled, 'request' : msg2}
        )
        assert event.is_cancelled is False

    def test_assign_existing(self):
        """Test adding an attribute that already exists."""
        msg = r"'Event' object already has an attribute 'assoc'"
        with pytest.raises(AttributeError, match=msg):
            event = evt.Event(None, evt.EVT_C_STORE, {'assoc' : None})


# TODO: Should be able to remove in v1.4
INTERVENTION_HANDLERS = [
    _async_ops_handler, _sop_common_handler,
    _sop_extended_handler, _user_identity_handler, _c_echo_handler,
    _c_get_handler, _c_find_handler, _c_move_handler, _c_store_handler,
    _n_action_handler, _n_create_handler, _n_delete_handler,
    _n_event_report_handler, _n_get_handler, _n_set_handler
]

@pytest.mark.parametrize('handler', INTERVENTION_HANDLERS)
def test_default_handlers(handler):
    if handler not in [_sop_common_handler, _sop_extended_handler,
                       _c_echo_handler]:
        with pytest.raises(NotImplementedError):
            handler(None)
    else:
        handler(None)
