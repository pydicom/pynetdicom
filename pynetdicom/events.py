"""Module used to support events and event handling, not to be confused with
the state machine events.
"""

from collections import namedtuple
from datetime import datetime
import inspect
import logging
import sys

from pydicom.dataset import Dataset

from pynetdicom.dsutils import decode


LOGGER = logging.getLogger('pynetdicom.events')


# Notification events
#   No returns/yields needed, can have multiple handlers per event
NotificationEvent = namedtuple('NotificationEvent', ['name', 'description'])
"""Representation of a notification event.

.. versionadded:: 1.3

Possible notification events are:

* :class:`EVT_ABORTED`
* :class:`EVT_ACCEPTED`
* :class:`EVT_ACSE_RECV`
* :class:`EVT_ACSE_SENT`
* :class:`EVT_CONN_CLOSE`
* :class:`EVT_CONN_OPEN`
* :class:`EVT_DATA_RECV`
* :class:`EVT_DATA_SENT`
* :class:`EVT_DIMSE_RECV`
* :class:`EVT_DIMSE_SENT`
* :class:`EVT_ESTABLISHED`
* :class:`EVT_FSM_TRANSITION`
* :class:`EVT_PDU_RECV`
* :class:`EVT_PDU_SENT`
* :class:`EVT_REJECTED`
* :class:`EVT_RELEASED`
* :class:`EVT_REQUESTED`
"""
NotificationEvent.is_intervention = False
NotificationEvent.is_notification = True

# pylint: disable=line-too-long
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
"""Representation of an intervention event.

.. versionadded:: 1.3

Possible intervention events are:

* :class:`EVT_ASYNC_OPS`
* :class:`EVT_SOP_COMMON`
* :class:`EVT_SOP_EXTENDED`
* :class:`EVT_USER_ID`
* :class:`EVT_C_ECHO`
* :class:`EVT_C_FIND`
* :class:`EVT_C_GET`
* :class:`EVT_C_MOVE`
* :class:`EVT_C_STORE`
* :class:`EVT_N_ACTION`
* :class:`EVT_N_CREATE`
* :class:`EVT_N_DELETE`
* :class:`EVT_N_EVENT_REPORT`
* :class:`EVT_N_GET`
* :class:`EVT_N_SET`
"""
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
# pylint: enable=line-too-long

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
    """Return the default handler for an intervention `event`.

    .. versionadded:: 1.3
    """
    handlers = {
        EVT_ASYNC_OPS : _async_ops_handler,
        EVT_SOP_COMMON : _sop_common_handler,
        EVT_SOP_EXTENDED : _sop_extended_handler,
        EVT_USER_ID : _user_identity_handler,
        EVT_C_ECHO : _c_echo_handler,
        EVT_C_FIND : _c_find_handler,
        EVT_C_GET : _c_get_handler,
        EVT_C_MOVE : _c_move_handler,
        EVT_C_STORE : _c_store_handler,
        EVT_N_ACTION : _n_action_handler,
        EVT_N_CREATE : _n_create_handler,
        EVT_N_DELETE : _n_delete_handler,
        EVT_N_EVENT_REPORT : _n_event_report_handler,
        EVT_N_GET : _n_get_handler,
        EVT_N_SET : _n_set_handler,
    }
    return handlers[event]


def trigger(assoc, event, attrs=None):
    """Trigger an `event` and call any bound handler(s).

    .. versionadded:: 1.3

    Notification events can be bound to multiple handlers, intervention events
    can only be bound to a single handler.

    **Special Attributes**

    If `attrs` contains:

    * `_is_cancelled` key then :attr:`Event.is_cancelled` will be hooked into
      the value's callable function.
    * a C-FIND, C-GET or C-MOVE `request` key then :attr:`Event.identifier`
      will return the decoded *Identifier* parameter value.
    * a C-STORE `request` key then :attr:`Event.dataset` will return the
      decoded *Data Set* parameter value.
    * an N-ACTION `request` key then :attr:`Event.action_information` will
      return the decoded *Action Information* parameter value.
    * an N-CREATE `request` key then :attr:`Event.attribute_list` will return
      the decoded *Attribute List* parameter value.
    * an N-EVENT-REPORT `request` key then :attr:`Event.event_information` will
      return the decoded *Event Information* parameter value.
    * an N-SET `request` key then :attr:`Event.modification_list` will return
      the decoded *Modification List* parameter value.

    Parameters
    ----------
    assoc : assoc.Association
        The association in which the event occurred.
    event : events.NotificationEvent or events.InterventionEvent
        The event to trigger.
    attrs : dict, optional
        The attributes to set in the :class:`Event` instance that is passed to
        the event's corresponding handler functions as
        ``{attribute name : value}``, default ``{}``.

    Raises
    ------
    Exception
        If an exception occurs in an intervention event handler then the
        exception will be raised. If an exception occurs in a notification
        handler then the exception will be caught and logged instead.
    """
    # Get the handler(s) bound to the event
    #   notification events: returns a list of 2-tuple (callable, args)
    #   intervention events: returns a 2-tuple of (callable, args)
    #       or (None, None)
    handlers = assoc.get_handlers(event)
    # Empty list or (None, None)
    if not handlers or handlers[0] is None:
        return

    evt = Event(assoc, event, attrs or {})

    try:
        # Intervention event - only single handler allowed
        if event.is_intervention:
            if handlers[1] is not None:
                return handlers[0](evt, *handlers[1])

            return handlers[0](evt)

        # Notification event - multiple handlers are allowed
        for func, args in handlers:
            if args:
                func(evt, *args)
            else:
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

    .. versionadded:: 1.3

    .. warning::

       Some of :class:`Event`'s attributes are set dynamically when an event is
       triggered and are available only for a specific event. For example, the
       ``Event.context`` attribute is only available for events such as
       ``evt.EVT_C_ECHO``, ``evt.EVT_C_STORE``, etc. See the
       :ref:`handler documentation<api_events>` for a list of what attributes
       are available for a given event.

    Attributes
    ----------
    assoc : association.Association
        The association in which the event occurred.
    event : events.InterventionEvent or events.NotificationEvent
        A :func:`namedtuple<collections.namedtuple>` instance representing the
        event that occurred.
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
        event : events.NotificationEvent or events.InterventionEvent
            The representation of the event that occurred.
        attrs : dict, optional
            The ``{attribute : value}`` pairs to use to set the
            :class:`Event`'s  attributes.
        """
        self.assoc = assoc
        self._event = event
        self.timestamp = datetime.now()

        # Only decode a dataset when necessary
        self._hash = None
        self._decoded = None

        attrs = attrs or {}
        for kk, vv in attrs.items():
            if hasattr(self, kk):
                raise AttributeError(
                    "'Event' object already has an attribute '{}'"
                    .format(kk)
                )
            setattr(self, kk, vv)

    @property
    def action_information(self):
        """Return an N-ACTION request's `Action Information` as a *pydicom*
        :class:`~pydicom.dataset.Dataset`.

        Because *pydicom* defers data parsing during decoding until an element
        is actually required the returned :class:`~pydicom.dataset.Dataset`
        may raise an exception when any element is first accessed. It's
        therefore important that proper error handling be part of any handler
        that uses the returned :class:`~pydicom.dataset.Dataset`.

        Returns
        -------
        pydicom.dataset.Dataset
            The decoded *Action Information* dataset.

        Raises
        ------
        AttributeError
            If the corresponding event is not an N-ACTION request.
        """
        msg = (
            "The corresponding event is not an N-ACTION request and has no "
            "'Action Information' parameter"
        )
        return self._get_dataset("ActionInformation", msg)

    @property
    def action_type(self):
        """Return an N-ACTION request's `Action Type ID` as an :class:`int`.

        .. versionadded:: 1.4

        Returns
        -------
        int
            The request's (0000,1008) *Action Type ID* value.

        Raises
        ------
        AttributeError
            If the corresponding event is not an N-ACTION request.
        """
        try:
            return self.request.ActionTypeID
        except AttributeError:
            raise AttributeError(
                "The corresponding event is not an N-ACTION request and has "
                "no 'Action Type ID' parameter"
            )

    @property
    def attribute_identifiers(self):
        """Return an N-GET request's `Attribute Identifier List` as a
        :class:`list` of *pydicom* :class:`~pydicom.tag.BaseTag`.

        Returns
        -------
        list of pydicom.tag.BaseTag
            The (0000,1005) *Attribute Identifier List* tags, may be an empty
            list if no *Attribute Identifier List* was included in the C-GET
            request.

        Raises
        ------
        AttributeError
            If the corresponding event is not an N-GET request.
        """
        try:
            attr_list = self.request.AttributeIdentifierList
            if attr_list is None:
                return []

            return attr_list
        except AttributeError:
            pass

        raise AttributeError(
            "The corresponding event is not an N-GET request and has no "
            "'Attribute Identifier List' parameter"
        )

    @property
    def attribute_list(self):
        """Return an N-CREATE request's `Attribute List` as a *pydicom*
        :class:`~pydicom.dataset.Dataset`.

        Because *pydicom* defers data parsing during decoding until an element
        is actually required the returned :class:`~pydicom.dataset.Dataset`
        may raise an exception when any element is first accessed. It's
        therefore important that proper error handling be part of any handler
        that uses the returned :class:`~pydicom.dataset.Dataset`.

        Returns
        -------
        pydicom.dataset.Dataset
            The decoded *Attribute List* dataset.

        Raises
        ------
        AttributeError
            If the corresponding event is not an N-CREATE request.
        """
        msg = (
            "The corresponding event is not an N-CREATE request and has no "
            "'Attribute List' parameter"
        )
        return self._get_dataset("AttributeList", msg)

    @property
    def dataset(self):
        """Return a C-STORE request's `Data Set` as a *pydicom*
        :class:`~pydicom.dataset.Dataset`.

        Because *pydicom* defers data parsing during decoding until an element
        is actually required the returned :class:`~pydicom.dataset.Dataset`
        may raise an exception when any element is first accessed. It's
        therefore important that proper error handling be part of any handler
        that uses the returned :class:`~pydicom.dataset.Dataset`.

        Returns
        -------
        pydicom.dataset.Dataset
            The decoded *Data Set* dataset.

        Raises
        ------
        AttributeError
            If the corresponding event is not a C-STORE request.
        """
        msg = (
            "The corresponding event is not a C-STORE request and has no "
            "'Data Set' parameter"
        )
        return self._get_dataset("DataSet", msg)

    @property
    def event(self):
        """Return the corresponding event.

        .. versionadded:: 1.4

        Returns
        -------
        events.InterventionEvent or events.NotificationEvent
            The corresponding event as a
            :func:`namedtuple<collections.namedtuple>`.
        """
        return self._event

    @property
    def event_information(self):
        """Return an N-EVENT-REPORT request's `Event Information` as a
        *pydicom* :class:`~pydicom.dataset.Dataset`.

        Because *pydicom* defers data parsing during decoding until an element
        is actually required the returned :class:`~pydicom.dataset.Dataset`
        may raise an exception when any element is first accessed. It's
        therefore important that proper error handling be part of any handler
        that uses the returned :class:`~pydicom.dataset.Dataset`.

        Returns
        -------
        pydicom.dataset.Dataset
            The decoded *Event Information* dataset.

        Raises
        ------
        AttributeError
            If the corresponding event is not an N-EVENT-REPORT request.
        """
        msg = (
            "The corresponding event is not an N-EVENT-REPORT request and has "
            "no 'Event Information' parameter"
        )
        return self._get_dataset("EventInformation", msg)

    @property
    def event_type(self):
        """Return an N-EVENT-REPORT request's `Event Type ID` as an
        :class:`int`.

        .. versionadded:: 1.4

        Returns
        -------
        int
            The request's (0000,1002) *Event Type ID* value.

        Raises
        ------
        AttributeError
            If the corresponding event is not an N-EVENT-REPORT request.
        """
        try:
            return self.request.EventTypeID
        except AttributeError:
            raise AttributeError(
                "The corresponding event is not an N-EVENT-REPORT request "
                "and has no 'Event Type ID' parameter"
            )

    @property
    def file_meta(self):
        r"""Return a *pydicom* :class:`~pydicom.dataset.Dataset` with the
        :dcm:`File Meta Information<part10/chapter_7.html#sect_7.1>` for a
        C-STORE request's `Data Set`.

        Contains the following File Meta Information elements:

        * (0002,0000) *File Meta Information Group Length* - set as ``0``, will
          be updated with the correct value during write
        * (0002,0001) *File Meta Information Version* - set as ``0x0001``
        * (0002,0002) *Media Storage SOP Class UID* - set from the request's
          *Affected SOP Class UID*
        * (0002,0003) *Media Storage SOP Instance UID* - set from the request's
          *Affected SOP Instance UID*
        * (0002,0010) *Transfer Syntax UID* - set from the presentation context
          used to transfer the *Data Set*
        * (0002,0012) *Implementation Class UID* - set using
          :attr:`~pynetdicom.PYNETDICOM_IMPLEMENTATION_UID`
        * (0002,0013) *Implementation Version Name* - set using
          :attr:`~pynetdicom.PYNETDICOM_IMPLEMENTATION_VERSION`

        Examples
        --------

        Add the File Meta Information to the decoded *Data Set* and save it to
        the :dcm:`DICOM File Format<part10/chapter_7.html>`.

        .. code-block:: python

            >>> ds = event.dataset
            >>> ds.file_meta = event.file_meta
            >>> ds.save_as('example.dcm', write_like_original=False)

        Encode the File Meta Information in a new file and append the encoded
        *Data Set* to it. This skips having to decode/re-encode the *Data Set*
        as in the previous example.

        .. code-block:: python

           >>> from pydicom.filewriter import write_file_meta_info
           >>> with open('example.dcm', 'wb') as f:
           ...     f.write(b'\x00' * 128)
           ...     f.write(b'DICM')
           ...     write_file_meta_info(f, event.file_meta)
           ...     f.write(event.request.DataSet.getvalue())

        Returns
        -------
        pydicom.dataset.Dataset
            The File Meta Information suitable for use with the decoded C-STORE
            request's *Data Set*.

        Raises
        ------
        AttributeError
            If the corresponding event is not a C-STORE request.
        """
        if not hasattr(self.request, 'DataSet'):
            raise AttributeError(
                "The corresponding event is not a C-STORE request"
            )

        from pynetdicom import PYNETDICOM_IMPLEMENTATION_UID
        from pynetdicom import PYNETDICOM_IMPLEMENTATION_VERSION

        # A C-STORE request must have AffectedSOPClassUID and
        #   AffectedSOPInstanceUID
        meta = Dataset()
        meta.FileMetaInformationGroupLength = 0
        meta.FileMetaInformationVersion = b'\x00\x01'
        meta.MediaStorageSOPClassUID = self.request.AffectedSOPClassUID
        meta.MediaStorageSOPInstanceUID = self.request.AffectedSOPInstanceUID
        meta.TransferSyntaxUID = self.context.transfer_syntax
        meta.ImplementationClassUID = PYNETDICOM_IMPLEMENTATION_UID
        meta.ImplementationVersionName = PYNETDICOM_IMPLEMENTATION_VERSION

        # File Meta Information is always encoded as Explicit VR Little Endian
        meta.is_little_endian = True
        meta.is_implicit_VR = False

        return meta

    def _get_dataset(self, attr, exc_msg):
        """Return DIMSE dataset-like parameter as a *pydicom* Dataset.

        Parameters
        ----------
        attr : str
            The name of the DIMSE primitive's dataset-like parameter, one of
            'DataSet', 'Identifier', 'AttributeList', 'ModificationList',
            'EventInformation', 'ActionInformation'.
        exc_msg : str
            The exception message to use if the request primitive has no
            dataset-like parameter.

        Returns
        -------
        pydicom.dataset.Dataset
            The decoded dataset-like parameter.

        Raises
        ------
        AttributeError
            If the corresponding event is not due to one of the DIMSE requests
            with a dataset-like parameter.
        """
        try:
            bytestream = getattr(self.request, attr)
            # If no change in encoded data then return stored decode
            if self._hash == hash(bytestream):
                return self._decoded

            # Some dataset-like parameters are optional
            if bytestream and bytestream.getvalue() != b'':
                # Dataset-like parameter has been used
                t_syntax = self.context.transfer_syntax
                ds = decode(
                    bytestream,
                    t_syntax.is_implicit_VR,
                    t_syntax.is_little_endian,
                    t_syntax.is_deflated
                )

                ds.is_little_endian = t_syntax.is_little_endian
                ds.is_implicit_VR = t_syntax.is_implicit_VR

                # Store the decoded dataset in case its accessed again
                self._decoded = ds
            else:
                # Dataset-like parameter hasn't been used
                self._decoded = Dataset()

            self._hash = hash(bytestream)
            return self._decoded

        except AttributeError as exc:
            pass

        raise AttributeError(exc_msg)

    @property
    def identifier(self):
        """Return a C-FIND, C-GET or C-MOVE request's `Identifier` as a
        *pydicom* :class:`~pydicom.dataset.Dataset`.

        Because *pydicom* defers data parsing during decoding until an element
        is actually required the returned :class:`~pydicom.dataset.Dataset`
        may raise an exception when any element is first accessed. It's
        therefore important that proper error handling be part of any handler
        that uses the returned :class:`~pydicom.dataset.Dataset`.

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
        msg = (
            "The corresponding event is not a C-FIND, C-GET or C-MOVE request "
            "and has no 'Identifier' parameter"
        )
        return self._get_dataset("Identifier", msg)

    @property
    def is_cancelled(self):
        """Return ``True`` if a C-CANCEL request has been received.

        Returns
        -------
        bool
            If this event corresponds to a C-FIND, C-GET or C-MOVE request
            being received by a Service Class then returns ``True`` if a
            C-CANCEL request with a *Message ID Being Responded To* parameter
            value corresponding to the *Message ID* of the service request has
            been received. If no such C-CANCEL request has been received or if
            the event is not a C-FIND, C-GET or C-MOVE request then returns
            ``False``.
        """
        try:
            return self._is_cancelled(self.request.MessageID)
        except AttributeError:
            pass

        return False

    @property
    def message_id(self):
        """Return a DIMSE service request's `Message ID` as :class:`int`.

        .. versionadded:: 1.5

        Returns
        -------
        int
            The request's (0000,0110) *Message ID* value.

        Raises
        ------
        AttributeError
            If the corresponding event is not one of the DIMSE service
            requests.
        """
        try:
            return self.request.MessageID
        except AttributeError:
            raise AttributeError(
                "The corresponding event is not a DIMSE service request and "
                "has no 'Message ID' parameter"
            )

    @property
    def modification_list(self):
        """Return an N-SET request's `Modification List` as a *pydicom*
        :class:`~pydicom.dataset.Dataset`.

        Because *pydicom* defers data parsing during decoding until an element
        is actually required the returned :class:`~pydicom.dataset.Dataset`
        may raise an exception when any element is first accessed. It's
        therefore important that proper error handling be part of any handler
        that uses the returned :class:`~pydicom.dataset.Dataset`.

        Returns
        -------
        pydicom.dataset.Dataset
            The decoded *Modification List* dataset.

        Raises
        ------
        AttributeError
            If the corresponding event is not an N-SET request.
        """
        msg = (
            "The corresponding event is not an N-SET request and has no "
            "'Modification List' parameter"
        )
        return self._get_dataset("ModificationList", msg)

    @property
    def move_destination(self):
        """Return a C-MOVE request's `Move Destination` as :class:`bytes`.

        .. versionadded:: 1.4

        Returns
        -------
        bytes
            The request's (0000,0600) *Move Destination* value as length 16
            bytes (including trailing spaces as padding if required).

        Raises
        ------
        AttributeError
            If the corresponding event is not a C-MOVE request.
        """
        try:
            return self.request.MoveDestination
        except AttributeError:
            raise AttributeError(
                "The corresponding event is not a C-MOVE request and has no "
                "'Move Destination' parameter"
            )


# Default extended negotiation event handlers
def _async_ops_handler(event):
    """Default handler for when an Asynchronous Operations Window Negotiation
    item is include in the association request.

    See _handlers.doc_handle_async for detailed documentation.
    """
    raise NotImplementedError(
        "No handler has been bound to 'evt.EVT_ASYNC_OPS', so no "
        "Asynchronous Operations Window Negotiation response will be "
        "sent"
    )

def _sop_common_handler(event):
    """Default handler for when one or more SOP Class Common Extended
    Negotiation items are included in the association request.

    See _handlers.doc_handle_sop_common for detailed documentation.
    """
    return {}

def _sop_extended_handler(event):
    """Default handler for when one or more SOP Class Extended Negotiation
    items are included in the association request.

    See _handlers.doc_handler_sop_extended for detailed documentation.
    """
    return {}

def _user_identity_handler(event):
    """Default hander for when a user identity negotiation item is included
    with the association request.

    See _handlers.doc_handler_userid for detailed documentation.
    """
    raise NotImplementedError(
        "No handler has been bound to 'evt.EVT_USER_ID', so the User Identity "
        "Negotiation will be ignored and the association accepted (unless "
        "rejected for another reason)"
    )

# Default service class request handlers
def _c_echo_handler(event):
    """Default handler for when a C-ECHO request is received.

    See _handlers.doc_handle_echo for detailed documentation.
    """
    return 0x0000

def _c_find_handler(event):
    """Default handler for when a C-FIND request is received.

    See _handlers.doc_handle_find for detailed documentation.
    """
    raise NotImplementedError("No handler has been bound to 'evt.EVT_C_FIND'")

def _c_get_handler(event):
    """Default handler for when a C-GET request is received.

    See _handlers.doc_handle_c_get for detailed documentation.
    """
    raise NotImplementedError("No handler has been bound to 'evt.EVT_C_GET'")

def _c_move_handler(event):
    """Default handler for when a C-MOVE request is received.

    See _handlers.doc_handle_move for detailed documentation.
    """
    raise NotImplementedError("No handler has been bound to 'evt.EVT_C_MOVE'")

def _c_store_handler(event):
    """Default handler for when a C-STORE request is received.

    See _handlers.doc_handle_store for detailed documentation.
    """
    raise NotImplementedError("No handler has been bound to 'evt.EVT_C_STORE'")

def _n_action_handler(event):
    """Default handler for when an N-ACTION request is received.

    See _handlers.doc_handle_action for detailed documentation.
    """
    raise NotImplementedError(
        "No handler has been bound to 'evt.EVT_N_ACTION'"
    )

def _n_create_handler(event):
    """Default handler for when an N-CREATE request is received.

    See _handlers.doc_handle_create for detailed documentation.
    """
    raise NotImplementedError(
        "No handler has been bound to 'evt.EVT_N_CREATE'"
    )

def _n_delete_handler(event):
    """Default handler for when an N-DELETE request is received.

    See _handlers.doc_handle_delete for detailed documentation.
    """
    raise NotImplementedError(
        "No handler has been bound to 'evt.EVT_N_DELETE'"
    )

def _n_event_report_handler(event):
    """Default handler for when an N-EVENT-REPORT request is received.

    See _handlers.doc_handle_event_report for detailed documentation.
    """
    raise NotImplementedError(
        "No handler has been bound to 'evt.EVT_N_EVENT_REPORT'"
    )

def _n_get_handler(event):
    """Default handler for when an N-GET request is received.

    See _handlers.doc_handle_n_get for detailed documentation.
    """
    raise NotImplementedError("No handler has been bound to 'evt.EVT_N_GET'")

def _n_set_handler(event):
    """Default handler for when an N-SET request is received.

    See _handlers.doc_handle_set for detailed documentation.
    """
    raise NotImplementedError("No handler has been bound to 'evt.EVT_N_SET'")
