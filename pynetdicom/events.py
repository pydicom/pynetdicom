"""Module used to support events and event handling, not to be confused with
the state machine events.
"""

from collections import namedtuple
from datetime import datetime
import inspect
import logging
import sys

from pynetdicom.dsutils import decode


LOGGER = logging.getLogger('pynetdicom.events')


# Notification events
#   No returns/yields needed, can have multiple handlers per event
NotificationEvent = namedtuple('NotificationEvent', ['name', 'description'])
NotificationEvent.is_intervention = False
NotificationEvent.is_notification = True

EVT_ABORTED = NotificationEvent("EVT_ABORTED", "Association aborted")
EVT_ACCEPTED = NotificationEvent("EVT_ACCEPTED", "Association request accepted")
EVT_ACSE_RECV = NotificationEvent("EVT_ACSE_RECV", "ACSE primitive received from DUL")
EVT_ACSE_SENT = NotificationEvent("EVT_ACSE_SENT", "ACSE primitive sent to DUL")
EVT_CONN_CLOSE = NotificationEvent("EVT_CONN_CLOSE", "Connection closed")
EVT_CONN_OPEN = NotificationEvent("EVT_CONN_OPEN", "Connection opened")
EVT_DATA_RECV = NotificationEvent("EVT_DATA_RECV", "PDU data received from remote")
EVT_DATA_SENT = NotificationEvent("EVT_DATA_SENT", "PDU data sent to remote")
EVT_DIMSE_RECV = NotificationEvent("EVT_DIMSE_RECV", "Complete DIMSE message received and decoded")
EVT_DIMSE_SENT = NotificationEvent("EVT_DIMSE_SENT", "DIMSE message encoded and P-DATA primitives sent to DUL")
EVT_ESTABLISHED = NotificationEvent("EVT_ESTABLISHED", "Association established")
EVT_FSM_TRANSITION = NotificationEvent("EVT_FSM_TRANSITION", "State machine about to transition")
EVT_PDU_RECV = NotificationEvent("EVT_PDU_RECV", "PDU received and decoded")
EVT_PDU_SENT = NotificationEvent("EVT_PDU_SENT", "PDU encoded and sent")
EVT_REJECTED = NotificationEvent("EVT_REJECTED", "Association request rejected")
EVT_RELEASED = NotificationEvent("EVT_RELEASED", "Association released")
EVT_REQUESTED = NotificationEvent("EVT_REQUESTED", "Association requested")

# Intervention events
#   Returns/yields needed if bound, can only have one handler per event
InterventionEvent = namedtuple('InterventionEvent', ['name', 'description'])
InterventionEvent.is_intervention = True
InterventionEvent.is_notification = False

EVT_ASYNC_OPS = InterventionEvent("EVT_ASYNC_OPS", "Asynchronous operations negotiation requested")
EVT_SOP_COMMON = InterventionEvent("EVT_SOP_COMMON", "SOP class common extended negotiation requested")
EVT_SOP_EXTENDED = InterventionEvent("EVT_SOP_EXTENDED", "SOP class extended negotiation requested")
EVT_USER_ID = InterventionEvent("EVT_USER_ID", "User identity negotiation requested")
EVT_C_ECHO = InterventionEvent("EVT_C_ECHO", "C-ECHO request received")
EVT_C_FIND = InterventionEvent("EVT_C_FIND", "C-FIND request received")
EVT_C_GET = InterventionEvent("EVT_C_GET", "C-GET request received")
EVT_C_MOVE = InterventionEvent("EVT_C_MOVE", "C-MOVE request received")
EVT_C_STORE = InterventionEvent("EVT_C_STORE", "C-STORE request received")
EVT_N_ACTION = InterventionEvent("EVT_N_ACTION", "N-ACTION request received")
EVT_N_CREATE = InterventionEvent("EVT_N_CREATE", "N-CREATE request received")
EVT_N_DELETE = InterventionEvent("EVT_N_DELETE", "N-DELETE request received")
EVT_N_EVENT_REPORT = InterventionEvent("EVT_N_EVENT_REPORT", "N-EVENT-REPORT request received")
EVT_N_GET = InterventionEvent("EVT_N_GET", "N-GET request received")
EVT_N_SET = InterventionEvent("EVT_N_SET", "N-SET request received")


_INTERVENTION_EVENTS = [
    ii[1] for ii in inspect.getmembers(
        sys.modules[__name__], lambda x: isinstance(x, InterventionEvent)
    )
]
_NOTIFICATION_EVENTS = [
    ii[1] for ii in inspect.getmembers(
        sys.modules[__name__], lambda x: isinstance(x, NotificationEvent)
    )
]


def get_default_handler(event):
    """Get the default handler for an intervention `event`."""
    handlers = {
        EVT_ASYNC_OPS : default_async_ops_handler,
        EVT_SOP_COMMON : default_sop_common_handler,
        EVT_SOP_EXTENDED : default_sop_extended_handler,
        EVT_USER_ID : default_user_identity_handler,
        EVT_C_ECHO : default_c_echo_handler,
        EVT_C_FIND : default_c_find_handler,
        EVT_C_GET : default_c_get_handler,
        EVT_C_MOVE : default_c_move_handler,
        EVT_C_STORE : default_c_store_handler,
        EVT_N_ACTION : default_n_action_handler,
        EVT_N_CREATE : default_n_create_handler,
        EVT_N_DELETE : default_n_delete_handler,
        EVT_N_EVENT_REPORT : default_n_event_report_handler,
        EVT_N_GET : default_n_get_handler,
        EVT_N_SET : default_n_set_handler,
    }
    return handlers[event]


def trigger(assoc, event, attrs=None):
    """Trigger an `event` and call any bound handler(s).

    Notification events can be bound to multiple handlers, intervention events
    can only be bound to a single handler.

    **Intervention Events**

    * Service class requests: EVT_C_ECHO, EVT_C_FIND, EVT_C_GET, EVT_C_MOVE,
      EVT_C_STORE, EVT_N_ACTION, EVT_N_CREATE, EVT_N_DELETE,
      EVT_N_EVENT_REPORT, EVT_N_GET, EVT_N_SET
    * Association extended negotiation requests: EVT_ASYNC_OPS, EVT_SOP_COMMON,
      EVT_SOP_EXTENDED, EVT_USER_ID

    **Special Attributes**

    If `attrs` contains:

    * `_is_cancelled` key then ``Event.is_cancelled`` will be hooked into
      the value's callable function.
    * a C-STORE `request` key then ``Event.dataset`` will return the decoded
      *Data Set* parameter value.
    * a C-FIND, C-GET or C-MOVE `request` key then ``Event.identifier`` will
      return the decoded *Identifier* parameter value.

    Parameters
    ----------
    assoc : assoc.Association
        The association in which the event occurred.
    event : event.NotificationEvent or event.InterventionEvent
        The event to trigger.
    attrs : dict, optional
        The attributes to set in the Event instance that is passed to
        the event's corresponding handler functions as
        {attribute name : value}, default {}.

    Raises
    ------
    Exception
        If an exception occurs in an intervention event handler then the
        exception will be raised. If an exception occurs in a notification
        handler then the exception will be caught and logged instead.
    """
    # Get the handler(s) bound to the event
    #   notification events: returns a list of callable
    #   intervention events: returns a callable or None
    handlers = assoc.get_handlers(event)
    if not handlers:
        return

    evt = Event(assoc, event, attrs)

    try:
        # Intervention event - only singule handler allowed
        if event.is_intervention:
            return handlers(evt)

        # Notification event - multiple handlers are allowed
        for func in handlers:
            func(evt)
    except Exception as exc:
        # Intervention exceptions get raised
        if event.is_intervention:
            raise

        # Capture exceptions for notification events
        LOGGER.error(
            "Exception raised in user's 'evt.{}' event handler '{}'"
            .format(event.name, func.__name__)
        )
        LOGGER.exception(exc)


class Event(object):
    """Representation of an event.

    Attributes
    ----------
    assoc : association.Association
        The association in which the event occurred.
    event : tuple
        The event that occurred.
    timestamp : datetime.datetime
        The date/time the event was created. Will be slightly before or after
        the actual event that this object represents.
    """
    def __init__(self, assoc, event, attrs=None):
        """Create a new Event.

        Parameters
        ----------
        assoc : association.Association
            The association in which the event occurred.
        event : event.NotificationEvent or event.InterventionEvent
            The representation of the event.
        attrs : dict, optional
            The {attribute : value} to set for the Event.
        """
        self.assoc = assoc
        self._event = event
        self.timestamp = datetime.now()

        attrs = attrs or {}
        for kk, vv in attrs.items():
            if hasattr(self, kk):
                raise AttributeError(
                    "'Event' object already has an attribute '{}'"
                    .format(kk)
                )
            setattr(self, kk, vv)

        # Only decode a dataset when necessary
        self._hash = None
        self._decoded = None

    @property
    def dataset(self):
        """Return a C-STORE request's `Data Set` as a *pydicom* Dataset.

        Because *pydicom* defers data parsing during decoding until an element
        is actually required the returned ``Dataset`` may raise an exception
        when first used. It's therefore important that proper error handling
        be part of any handler bound to an event that includes a dataset.

        Returns
        -------
        pydicom.dataset.Dataset
            The decoded *Data Set* dataset.

        Raises
        ------
        AttributeError
            If the corresponding event is not a C-STORE request.
        """
        try:
            # If no change in encoded data then return stored decode
            if self._hash == hash(self.request.DataSet):
                return self._decoded

            t_syntax = self.context.transfer_syntax
            ds = decode(self.request.DataSet,
                        t_syntax.is_implicit_VR,
                        t_syntax.is_little_endian)

            # Store the decoded dataset in case its accessed again
            self._hash = hash(self.request.DataSet)
            self._decoded = ds

            return ds
        except AttributeError:
            pass

        raise AttributeError(
            "The corresponding event is not a C-STORE request and has no "
            "'Data Set' parameter"
        )

    @property
    def description(self):
        """Return a description of the event as a str."""
        return self._event.description

    @property
    def identifier(self):
        """Return a C-FIND, C-GET or C-MOVE request's `Identifier` as a
        *pydicom* Dataset.

        Because *pydicom* defers data parsing during decoding until an element
        is actually required the returned ``Dataset`` may raise an exception
        when first used. It's therefore important that proper error handling
        be part of any handler bound to an event that includes a Dataset.

        Returns
        -------
        pydicom.dataset.Dataset
            The decoded *Identifier* dataset.

        Raises
        ------
        AttributeError
            If the corresponding event is not a C-FIND, C-GET or C-MOVE
            request.
        """
        try:
            # If no change in encoded data then return stored decode
            if self._hash == hash(self.request.Identifier):
                return self._decoded

            t_syntax = self.context.transfer_syntax
            ds = decode(self.request.Identifier,
                        t_syntax.is_implicit_VR,
                        t_syntax.is_little_endian)

            # Store the decoded dataset in case its accessed again
            self._hash = hash(self.request.Identifier)
            self._decoded = ds

            return ds
        except AttributeError:
            pass

        raise AttributeError(
            "The corresponding event is not a C-FIND, C-GET or C-MOVE request "
            "and has no 'Identifier' parameter"
        )

    @property
    def is_cancelled(self):
        """Return True if a C-CANCEL request has been received.

        Returns
        -------
        bool
            If this event corresponds to a C-FIND, C-GET or C-MOVE request
            being received by a Service Class then returns True if a C-CANCEL
            request with a *MessageIDBeingRespondedTo* parameter value
            corresponding to the *MessageID* of the service request has been
            received. If no such C-CANCEL request has been received or if
            the event is not a C-FIND, C-GET or C-MOVE request then returns
            False.
        """
        try:
            return self._is_cancelled(self.request.MessageID)
        except AttributeError:
            pass

        return False

    @property
    def name(self):
        """Return the name of the event as a str."""
        return self._event.name


# Default extended negotiation item handlers
def default_async_ops_handler(event):
    """Default handler for when an Asynchronous Operations Window Negotiation
    item is include in the association request.

    Asynchronous operations are not supported by *pynetdicom* and any
    request will always return the default number of operations
    invoked/performed (1, 1), regardless of what values are returned by
    the handler.

    If the handler is not implemented then no response to the Asynchronous
    Operations Window Negotiation will be sent in reply to the association
    requestor.

    **Event**

    ``evt.EVT_ASYNC_OPS``

    Parameters
    ----------
    event : event.Event
        The event representing an association request being received which
        contains an Asynchronous Operations Window Negotiation item. Event
        attributes are:

        * ``assoc`` : the
          :py:class:`association <pynetdicom.association.Association>`
          that is running the service that received the asynchronous operations
          window negotiation request.
        * ``invoked`` : the *Maximum Number Operations Invoked* parameter
          value of the Asynchronous Operations Window request as an ``int``.
          If the value is 0 then an unlimited number of invocations are
          requested.
        * ``performed`` : the *Maximum Number Operations Performed*
          parameter value of the Asynchronous Operations Window request as an
          ``int``. If the value is 0 then an unlimited number of performances
          are requested.
        * ``timestamp`` : the
          `date and time <https://docs.python.org/3/library/datetime.html#datetime-objects>`_
          that the negotiation request was processed by the ACSE.

    Returns
    -------
    int, int
        The (maximum number operations invoked, maximum number operations
        performed). A value of 0 indicates that an unlimited number of
        operations is supported. As asynchronous operations are not
        supported the return value will be ignored and (1, 1) sent in response.
    """
    raise NotImplementedError(
        "No handler has been bound to 'evt.EVT_ASYNC_OPS', so no "
        "Asynchronous Operations Window Negotiation response will be "
        "sent"
    )

def default_sop_common_handler(event):
    """Default handler for when one or more SOP Class Common Extended
    Negotiation items are included in the association request.

    **Event**

    ``evt.EVT_SOP_COMMON``

    Parameters
    ----------
    event : event.Event
        The event representing an association request being received which
        contains an Asynchronous Operations Window Negotiation item. Event
        attributes are:

        * ``assoc`` : the
          :py:class:`association <pynetdicom.association.Association>`
          that is running the service that received the SOP class common
          extended negotiation request.
        * ``items`` : the {*SOP Class UID* : SOPClassCommonExtendedNegotiation}
          items sent by the requestor.
        * ``timestamp`` : the
          `date and time <https://docs.python.org/3/library/datetime.html#datetime-objects>`_
          that the negotiation request was processed by the ACSE.

    Returns
    -------
    dict
        The {*SOP Class UID* : SOPClassCommonExtendedNegotiation} items
        accepted by the acceptor. When receiving DIMSE messages containing
        datasets corresponding to the *SOP Class UID* in an accepted item
        the corresponding Service Class will be used.

    References
    ----------

    * DICOM Standard Part 7, `Annex D.3.3.6 <http://dicom.nema.org/medical/dicom/current/output/chtml/part07/sect_D.3.3.6.html>`_
    """
    return {}

def default_sop_extended_handler(event):
    """Default handler for when one or more SOP Class Extended Negotiation
    items are included in the association request.

    **Event**

    ``evt.EVT_SOP_EXTENDED``

    Parameters
    ----------
    event : event.Event
        The event representing an association request being received which
        contains an Asynchronous Operations Window Negotiation item. Event
        attributes are:

        * ``app_info`` : the {*SOP Class UID* : *Service Class Application
          Information*} parameter values for the included items, with the
          service class application information being the raw encoded data sent
          by the requestor (as ``bytes``).
        * ``assoc`` : the
          :py:class:`association <pynetdicom.association.Association>`
          that is running the service that received the user identity
          negotiation request.
        * ``timestamp`` : the
          `date and time <https://docs.python.org/3/library/datetime.html#datetime-objects>`_
          that the negotiation request was processed by the ACSE.

    Returns
    -------
    dict of pydicom.uid.UID, bytes
        The {*SOP Class UID* : *Service Class Application Information*}
        parameter values to be sent in response to the request, with the
        service class application information being the encoded data that
        will be sent to the peer as-is. Return an empty dict if no response is
        to be sent.

    References
    ----------

    * DICOM Standard Part 7, `Annex D.3.3.5 <http://dicom.nema.org/medical/dicom/current/output/chtml/part07/sect_D.3.3.5.html>`_
    """
    return {}

def default_user_identity_handler(event):
    """Default hander for when a user identity negotiation item is included
    with the association request.

    If not implemented by the user then the association will be accepted
    (provided there's no other reason to reject it) and no User Identity
    response will be sent in reply even if one is requested.

    **Event**

    ``evt.EVT_USER_ID``

    Parameters
    ----------
    event : event.Event
        The event representing an association request being received which
        contains a User Identity Negotiation item. Event attributes are:

        * ``assoc`` : the
          :py:class:`association <pynetdicom.association.Association>`
          that is running the service that received the user identity
          negotiation request.
        * ``primary_field`` : the *Primary Field* value (as ``bytes``),
          contains the username, the encoded Kerberos ticket or the JSON web
          token.
        * ``secondary_field`` : the *Secondary Field* value. Will be ``None``
          unless the ``user_id_type`` is ``2`` in which case it will be
          ``bytes``.
        * ``timestamp`` : the
          `date and time <https://docs.python.org/3/library/datetime.html#datetime-objects>`_
          that the negotiation request was processed by the ACSE.
        * ``user_id_type`` : the *User Identity Type* value (as an ``int``),
          which indicates the form of user identity being provided:

          * 1 - Username as a UTF-8 string
          * 2 - Username as a UTF-8 string and passcode
          * 3 - Kerberos Service ticket
          * 4 - SAML Assertion
          * 5 - JSON Web Token

    Returns
    -------
    is_verified : bool
        Return True if the user identity has been confirmed and you wish
        to proceed with association establishment, False otherwise.
    response : bytes or None
        If ``user_id_type`` is:

        * 1 or 2, then return None
        * 3 then return the Kerberos Server ticket as bytes
        * 4 then return the SAML response as bytes
        * 5 then return the JSON web token as bytes

    References
    ----------

    * DICOM Standard Part 7, `Annex D.3.3.7 <http://dicom.nema.org/medical/dicom/current/output/chtml/part07/sect_D.3.3.7.html>`_
    """
    raise NotImplementedError(
        "No handler has been bound to 'evt.EVT_USER_ID', so the User Identity "
        "Negotiation will be ignored and the association accepted (unless "
        "rejected for another reason)"
    )

# Default service class request handlers
def default_c_echo_handler(event):
    """Default handler for when a C-ECHO request is received.

    See _handlers.handle_echo for detailed documentation.
    """
    return 0x0000

def default_c_find_handler(event):
    """Default handler for when a C-FIND request is received."""
    raise NotImplementedError("No handler has been bound to 'evt.EVT_C_FIND'")

def default_c_get_handler(event):
    """Default handler for when a C-GET request is received."""
    raise NotImplementedError("No handler has been bound to 'evt.EVT_C_GET'")

def default_c_move_handler(event):
    """Default handler for when a C-MOVE request is received."""
    raise NotImplementedError("No handler has been bound to 'evt.EVT_C_MOVE'")

def default_c_store_handler(event):
    """Default handler for when a C-STORE request is received."""
    raise NotImplementedError("No handler has been bound to 'evt.EVT_C_STORE'")

def default_n_action_handler(event):
    """Default handler for when an N-ACTION request is received."""
    raise NotImplementedError(
        "No handler has been bound to 'evt.EVT_N_ACTION'"
    )

def default_n_create_handler(event):
    """Default handler for when an N-CREATE request is received."""
    raise NotImplementedError(
        "No handler has been bound to 'evt.EVT_N_CREATE'"
    )

def default_n_delete_handler(event):
    """Default handler for when an N-DELETE request is received."""
    raise NotImplementedError(
        "No handler has been bound to 'evt.EVT_N_DELETE'"
    )

def default_n_event_report_handler(event):
    """Default handler for when an N-EVENT-REPORT request is received."""
    raise NotImplementedError(
        "No handler has been bound to 'evt.EVT_N_EVENT_REPORT'"
    )

def default_n_get_handler(event):
    """Default handler for when an N-GET request is received."""
    raise NotImplementedError("No handler has been bound to 'evt.EVT_N_GET'")

def default_n_set_handler(event):
    """Default handler for when an N-SET request is received."""
    raise NotImplementedError("No handler has been bound to 'evt.EVT_N_SET'")
