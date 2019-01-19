"""Module used to support Event handling."""

from datetime import datetime
import logging


LOGGER = logging.getLogger('pynetdicom.events')


# Possible events
# (source, name, description, multiple handers)
# Transport Service
EVT_CONNECTION_OPEN = ('TRANSPORT', 'CONNECTION OPEN', 'Connection with remote opened', True)
EVT_CONNECTION_CLOSE = ('TRANSPORT', 'CONNECTION CLOSE', 'Connection with remote closed', True)

# DIMSE Service
EVT_MESSAGE_RECV = ('DIMSE', 'MESSAGE RECV', 'DIMSE message received', True)
EVT_MESSAGE_SENT = ('DIMSE', 'MESSAGE SENT', 'DIMSE message sent', True)


# Association
EVT_ESTABLISHED = ('ASSOCIATION', 'ESTABLISHED', 'Association established', True)
EVT_RELEASED = ('ASSOCIATION', 'RELEASED', 'Association release completed', True)
EVT_ABORTED = ('ASSOCIATION', 'ABORTED', 'Association aborted', True)
EVT_REJECTED = ('ASSOCIATION', 'REJECTED', 'Association rejected', True)

# ACSE Service
EVT_USER_IDENTITY = ('ACSE', 'USER IDENTITY', 'User Identity request sent/received', False)
EVT_ASYNC_OPS = ('ACSE', 'ASYNC OPERATIONS', 'Asynchronous Operations request sent/received', False)
EVT_SOP_EXTENDED = ('ACSE', 'SOP EXTENDED', 'SOP Class Extended request sent/received', False)
EVT_SOP_COMMON = ('ACSE', 'SOP COMMON', 'SOP Class Common Extended request sent/received', False)

EVT_REQUEST = ('ACSE', 'ASSOCIATION REQUEST', 'Association request sent/received')
EVT_ACCEPT = ('ACSE', 'ASSOCIATION ACCEPT', 'Association accept sent/received')
EVT_REJECT = ('ACSE', 'ASSOCIATION REJECT', 'Association reject sent/received')
EVT_ABORT = ('ACSE', 'ASSOCIATION ABORT', 'Association abort sent/received')
EVT_RELEASE = ('ACSE', 'ASSOCIATION RELEASE', 'Association release sent/received')

# Verificiation Service
EVT_ECHO = ('VERIFICATION', 'ECHO ACTION', 'C-ECHO request received by service', False)
# Storage Service
EVT_STORE = ('STORAGE', 'STORE ACTION', 'C-STORE request received by service', False)
# Query/Retrieve Service
EVT_FIND = ('QR', 'FIND ACTION', 'C-FIND request received by service', False)
EVT_GET = ('QR', 'GET ACTION', 'C-GET request received by service', False)
EVT_MOVE = ('QR', 'MOVE ACTION', 'C-MOVE request received by service', False)


def trigger(cls, event, attrs=None):
    """Trigger an `event`.

    Parameters
    ----------
    cls : object
        The object triggering the event.
    event : 3-tuple of str
        The event to trigger ('source', 'event', 'description').
    attrs : dict, optional
        The attributes to set in the Event instance that is passed to
        the event's corresponding handler functions as
        {attribute name : value}, default {}.
    is_singleton : bool, optional
        True if only one callable function is allowed, False otherwise
        (default).
    """
    if event not in cls._handlers:
        return

    attrs = attrs or {}

    evt = Event(event)
    evt.source = cls
    for kk, vv in attrs.items():
        setattr(evt, kk, vv)

    try:
        for func in cls._handlers[event]:
            func(evt)
    except Exception as exc:
        print(
            "Exception raised in user's '{}' event handler '{}'"
            .format(event[1], func.__name__)
        )
        print(exc)
        LOGGER.error(
            "Exception raised in user's '{}' event handler '{}'"
            .format(event[1], func.__name__)
        )
        LOGGER.exception(exc)


class Event(object):
    """Representation of an event.

    Attributes
    ----------
    event : 3-tuple
        The event that occurred.
    timestamp : datetime.datetime
        The date/time the event was created. Will be slightly before or after
        the actual event that this object represents.
    """
    def __init__(self, event):
        self.event = event
        self.source = None
        self.timestamp = datetime.now()
