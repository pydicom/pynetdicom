"""Module used to support events and event handling, not to be confused with
the state machine events.
"""

from datetime import datetime
import inspect
import logging
from pathlib import Path
import sys
from typing import (
    Union,
    Callable,
    Any,
    Tuple,
    List,
    NamedTuple,
    Optional,
    TYPE_CHECKING,
    Dict,
    cast,
    Iterator,
)

from pydicom.dataset import Dataset, FileMetaDataset
from pydicom.filereader import dcmread
from pydicom.tag import BaseTag
from pydicom.uid import UID

from pynetdicom.dsutils import decode, create_file_meta

if TYPE_CHECKING:  # pragma: no cover
    from pynetdicom.association import Association
    from pynetdicom.dimse_messages import DIMSEMessage
    from pynetdicom.dimse_primitives import (
        C_ECHO,
        C_FIND,
        C_GET,
        C_MOVE,
        C_STORE,
        N_ACTION,
        N_CREATE,
        N_DELETE,
        N_EVENT_REPORT,
        N_GET,
        N_SET,
    )
    from pynetdicom.pdu import _PDUType
    from pynetdicom.pdu_primitives import SOPClassCommonExtendedNegotiation
    from pynetdicom.presentation import PresentationContextTuple

    _RequestType = Union[
        C_ECHO,
        C_FIND,
        C_GET,
        C_MOVE,
        C_STORE,
        N_ACTION,
        N_CREATE,
        N_DELETE,
        N_EVENT_REPORT,
        N_GET,
        N_SET,
    ]


LOGGER = logging.getLogger("pynetdicom.events")


EventType = Union["NotificationEvent", "InterventionEvent"]
EventHandlerType = Union[
    Tuple[EventType, Callable], Tuple[EventType, Callable, List[Any]]
]
_BasicReturnType = Union[Dataset, int]
_DatasetReturnType = Tuple[_BasicReturnType, Optional[Dataset]]
_IteratorType = Iterator[Tuple[_BasicReturnType, Optional[Dataset]]]


# Notification events
#   No returns/yields needed, can have multiple handlers per event
class NotificationEvent(NamedTuple):
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

    name: str
    description: str
    is_intervention: bool = False
    is_notification: bool = True

    def __str__(self) -> str:
        """String representation of the class."""
        return self.name


# pylint: disable=line-too-long
EVT_ABORTED = NotificationEvent("EVT_ABORTED", "Association aborted")
EVT_ACCEPTED = NotificationEvent("EVT_ACCEPTED", "Association request accepted")  # noqa
EVT_ACSE_RECV = NotificationEvent(
    "EVT_ACSE_RECV", "ACSE primitive received from DUL"
)  # noqa
EVT_ACSE_SENT = NotificationEvent("EVT_ACSE_SENT", "ACSE primitive sent to DUL")  # noqa
EVT_CONN_CLOSE = NotificationEvent("EVT_CONN_CLOSE", "Connection closed")
EVT_CONN_OPEN = NotificationEvent("EVT_CONN_OPEN", "Connection opened")
EVT_DATA_RECV = NotificationEvent(
    "EVT_DATA_RECV", "PDU data received from remote"
)  # noqa
EVT_DATA_SENT = NotificationEvent("EVT_DATA_SENT", "PDU data sent to remote")
EVT_DIMSE_RECV = NotificationEvent(
    "EVT_DIMSE_RECV", "Complete DIMSE message received and decoded"
)  # noqa
EVT_DIMSE_SENT = NotificationEvent(
    "EVT_DIMSE_SENT", "DIMSE message encoded and P-DATA primitives sent to DUL"
)  # noqa
EVT_ESTABLISHED = NotificationEvent(
    "EVT_ESTABLISHED", "Association established"
)  # noqa
EVT_FSM_TRANSITION = NotificationEvent(
    "EVT_FSM_TRANSITION", "State machine about to transition"
)  # noqa
EVT_PDU_RECV = NotificationEvent("EVT_PDU_RECV", "PDU received and decoded")
EVT_PDU_SENT = NotificationEvent("EVT_PDU_SENT", "PDU encoded and sent")
EVT_REJECTED = NotificationEvent("EVT_REJECTED", "Association request rejected")  # noqa
EVT_RELEASED = NotificationEvent("EVT_RELEASED", "Association released")
EVT_REQUESTED = NotificationEvent("EVT_REQUESTED", "Association requested")


# Intervention events
#   Returns/yields needed if bound, can only have one handler per event
class InterventionEvent(NamedTuple):
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

    name: str
    description: str
    is_intervention: bool = True
    is_notification: bool = False

    def __str__(self) -> str:
        """String representation of the class."""
        return self.name


EVT_ASYNC_OPS = InterventionEvent(
    "EVT_ASYNC_OPS", "Asynchronous operations negotiation requested"
)  # noqa
EVT_SOP_COMMON = InterventionEvent(
    "EVT_SOP_COMMON", "SOP class common extended negotiation requested"
)  # noqa
EVT_SOP_EXTENDED = InterventionEvent(
    "EVT_SOP_EXTENDED", "SOP class extended negotiation requested"
)  # noqa
EVT_USER_ID = InterventionEvent(
    "EVT_USER_ID", "User identity negotiation requested"
)  # noqa
EVT_C_ECHO = InterventionEvent("EVT_C_ECHO", "C-ECHO request received")
EVT_C_FIND = InterventionEvent("EVT_C_FIND", "C-FIND request received")
EVT_C_GET = InterventionEvent("EVT_C_GET", "C-GET request received")
EVT_C_MOVE = InterventionEvent("EVT_C_MOVE", "C-MOVE request received")
EVT_C_STORE = InterventionEvent("EVT_C_STORE", "C-STORE request received")
EVT_N_ACTION = InterventionEvent("EVT_N_ACTION", "N-ACTION request received")
EVT_N_CREATE = InterventionEvent("EVT_N_CREATE", "N-CREATE request received")
EVT_N_DELETE = InterventionEvent("EVT_N_DELETE", "N-DELETE request received")
EVT_N_EVENT_REPORT = InterventionEvent(
    "EVT_N_EVENT_REPORT", "N-EVENT-REPORT request received"
)  # noqa
EVT_N_GET = InterventionEvent("EVT_N_GET", "N-GET request received")
EVT_N_SET = InterventionEvent("EVT_N_SET", "N-SET request received")
# pylint: enable=line-too-long

_INTERVENTION_EVENTS = [
    ii[1]
    for ii in inspect.getmembers(
        sys.modules[__name__], lambda x: isinstance(x, InterventionEvent)
    )
]
_NOTIFICATION_EVENTS = [
    ii[1]
    for ii in inspect.getmembers(
        sys.modules[__name__], lambda x: isinstance(x, NotificationEvent)
    )
]


_HandlerBase = Tuple[Callable, Optional[List[Any]]]
_NotificationHandlerAttr = List[_HandlerBase]
_InterventionHandlerAttr = _HandlerBase
HandlerArgType = Union[_NotificationHandlerAttr, _InterventionHandlerAttr]
_HandlerAttr = Dict[EventType, HandlerArgType]


def _add_handler(
    event: EventType, handlers_attr: _HandlerAttr, handler_arg: _HandlerBase
) -> None:
    """Add a handler to an object's handler recording attribute.

    Parameters
    ----------
    event : NotificationEvent or InterventionEvent
        The event the handler should be bound to.
    handlers_attr : dict
        The object attribute of {event: Union[
            [(handler, Optional[args])],
            (handler, Optional[args])
        ]} used to record bindings.
    handler_arg : Tuple[Callable, Optional[List[Any]]]
        The handler and optional arguments to be bound.
    """
    if isinstance(event, NotificationEvent):
        if event not in handlers_attr:
            handlers_attr[event] = []

        if handler_arg not in handlers_attr[event]:
            h = cast(_NotificationHandlerAttr, handlers_attr[event])
            h.append(handler_arg)

    elif isinstance(event, InterventionEvent):
        # Intervention events - only one handler allowed
        handlers_attr[event] = handler_arg


def _remove_handler(
    event: EventType, handlers_attr: _HandlerAttr, handler: Callable
) -> None:
    """Remove a handler from an object's handler recording attribute.

    Parameters
    ----------
    event : NotificationEvent or InterventionEvent
        The event the handler should be unbound from.
    handlers_attr : dict
        The object attribute of
        {
            event: Union[
                List[(handler, Optional[args])],
                (handler, Optional[args])
            ]
        } used to record bindings.
    handler_arg : Callable
        The handler to be unbound.
    """
    if event not in handlers_attr:
        return

    if isinstance(event, NotificationEvent):
        handlers_list = cast(_NotificationHandlerAttr, handlers_attr[event])
        handlers_attr[event] = [h for h in handlers_list if h[0] != handler]
        if not handlers_attr[event]:
            del handlers_attr[event]

    elif isinstance(event, InterventionEvent):
        # Unbind and replace with default
        if handler in handlers_attr[event]:
            handlers_attr[event] = (get_default_handler(event), None)


def get_default_handler(event: InterventionEvent) -> Callable[["Event"], Any]:
    """Return the default handler for an intervention `event`.

    .. versionadded:: 1.3
    """
    handlers = {
        EVT_ASYNC_OPS: _async_ops_handler,
        EVT_SOP_COMMON: _sop_common_handler,
        EVT_SOP_EXTENDED: _sop_extended_handler,
        EVT_USER_ID: _user_identity_handler,
        EVT_C_ECHO: _c_echo_handler,
        EVT_C_FIND: _c_find_handler,
        EVT_C_GET: _c_get_handler,
        EVT_C_MOVE: _c_move_handler,
        EVT_C_STORE: _c_store_handler,
        EVT_N_ACTION: _n_action_handler,
        EVT_N_CREATE: _n_create_handler,
        EVT_N_DELETE: _n_delete_handler,
        EVT_N_EVENT_REPORT: _n_event_report_handler,
        EVT_N_GET: _n_get_handler,
        EVT_N_SET: _n_set_handler,
    }
    return handlers[event]


def trigger(
    assoc: "Association", event: EventType, attrs: Optional[Dict[str, Any]] = None
) -> Optional[Any]:
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
        return None

    evt = Event(assoc, event, attrs or {})

    try:
        # Intervention event - only single handler allowed
        if isinstance(event, InterventionEvent):
            handlers = cast(_InterventionHandlerAttr, handlers)
            if handlers[1] is not None:
                return handlers[0](evt, *handlers[1])

            return handlers[0](evt)

        # Notification event - multiple handlers are allowed
        handlers = cast(_NotificationHandlerAttr, handlers)
        for func, args in handlers:
            if args:
                func(evt, *args)
            else:
                func(evt)
    except Exception as exc:
        # Intervention exceptions get raised
        if isinstance(event, InterventionEvent):
            raise

        # Capture exceptions for notification events
        LOGGER.error(
            f"Exception raised in user's 'evt.{event.name}' "
            f"event handler '{func.__name__}'"
        )
        LOGGER.exception(exc)

    return None


class Event:
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
    timestamp : datetime.datetime
        The date/time the event was created. Will be slightly before or after
        the actual event that this object represents.
    """

    def __init__(
        self,
        assoc: "Association",
        event: EventType,
        attrs: Optional[Dict[str, Any]] = None,
    ) -> None:
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
        self._hash: Optional[int] = None
        self._decoded: Optional[Dataset] = None

        # Define type hints for dynamic attributes
        self.request: "_RequestType"
        self._is_cancelled: Callable[[int], bool]
        self.context: "PresentationContextTuple"
        self.current_state: str
        self.fsm_event: str
        self.next_state: str
        self.action: str
        self.data: bytes
        self.message: DIMSEMessage
        self.pdu: _PDUType

        attrs = attrs or {}
        for kk, vv in attrs.items():
            if hasattr(self, kk):
                raise AttributeError(f"'Event' object already has an attribute '{kk}'")
            setattr(self, kk, vv)

    @property
    def action_information(self) -> Dataset:
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
    def action_type(self) -> Optional[int]:
        """Return an N-ACTION request's `Action Type ID` as an :class:`int`.

        .. versionadded:: 1.4

        Returns
        -------
        int or None
            The request's (0000,1008) *Action Type ID* value, may be ``None``
            if the peer's N-ACTION request is non-conformant.

        Raises
        ------
        AttributeError
            If the corresponding event is not an N-ACTION request.
        """
        try:
            return cast("N_ACTION", self.request).ActionTypeID
        except AttributeError:
            raise AttributeError(
                "The corresponding event is not an N-ACTION request and has "
                "no 'Action Type ID' parameter"
            )

    @property
    def attribute_identifiers(self) -> List[BaseTag]:
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
            attr_list = cast("N_GET", self.request).AttributeIdentifierList
            if attr_list is None:
                return []

            if not isinstance(attr_list, list):
                return [attr_list]

            return attr_list
        except AttributeError:
            pass

        raise AttributeError(
            "The corresponding event is not an N-GET request and has no "
            "'Attribute Identifier List' parameter"
        )

    @property
    def attribute_list(self) -> Dataset:
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
    def dataset(self) -> Dataset:
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
        try:
            return dcmread(self.dataset_path)
        except (TypeError, AttributeError):
            pass

        return self._get_dataset("DataSet", msg)

    @property
    def dataset_path(self) -> Path:
        """Return the path to the dataset when
        :attr:`~pynetdicom._config.STORE_RECV_CHUNKED_DATASET` is ``True``.

        .. versionadded:: 2.0

        Returns
        -------
        pathlib.Path
            The path to the dataset.
        """
        try:
            req = cast("C_STORE", self.request)
            path = req._dataset_path
        except AttributeError:
            msg = (
                "The corresponding event is either not a C-STORE request or "
                "'STORE_RECV_CHUNKED_DATASET' is not True."
            )
            raise AttributeError(msg)

        return cast(Path, path)

    @property
    def event(self) -> EventType:
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
    def event_information(self) -> Dataset:
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
    def event_type(self) -> Optional[int]:
        """Return an N-EVENT-REPORT request's `Event Type ID` as an
        :class:`int`.

        .. versionadded:: 1.4

        Returns
        -------
        int or None
            The request's (0000,1002) *Event Type ID* value, may be ``None``
            if the peer's N-EVENT-REPORT request is non-conformant.

        Raises
        ------
        AttributeError
            If the corresponding event is not an N-EVENT-REPORT request.
        """
        try:
            return cast("N_EVENT_REPORT", self.request).EventTypeID
        except AttributeError:
            raise AttributeError(
                "The corresponding event is not an N-EVENT-REPORT request "
                "and has no 'Event Type ID' parameter"
            )

    @property
    def file_meta(self) -> FileMetaDataset:
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
        if not hasattr(self.request, "DataSet"):
            raise AttributeError("The corresponding event is not a C-STORE request")

        # A C-STORE request must have AffectedSOPClassUID and
        #   AffectedSOPInstanceUID
        self.request = cast("C_STORE", self.request)
        sop_class = cast(UID, self.request.AffectedSOPClassUID)
        sop_instance = cast(UID, self.request.AffectedSOPInstanceUID)
        return create_file_meta(
            sop_class_uid=sop_class,
            sop_instance_uid=sop_instance,
            transfer_syntax=self.context.transfer_syntax,
        )

    def _get_dataset(self, attr: str, exc_msg: str) -> Dataset:
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
                return cast(Dataset, self._decoded)

            # Some dataset-like parameters are optional
            if bytestream and bytestream.getvalue() != b"":
                # Dataset-like parameter has been used
                t_syntax = self.context.transfer_syntax
                ds = decode(
                    bytestream,
                    t_syntax.is_implicit_VR,
                    t_syntax.is_little_endian,
                    t_syntax.is_deflated,
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
    def identifier(self) -> Dataset:
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
    def is_cancelled(self) -> bool:
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
            return self._is_cancelled(cast(int, self.request.MessageID))
        except AttributeError:
            pass

        return False

    @property
    def message_id(self) -> int:
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
            return cast(int, self.request.MessageID)
        except AttributeError:
            raise AttributeError(
                "The corresponding event is not a DIMSE service request and "
                "has no 'Message ID' parameter"
            )

    @property
    def modification_list(self) -> Dataset:
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
    def move_destination(self) -> Optional[str]:
        """Return a C-MOVE request's `Move Destination` as :class:`str`.

        .. versionadded:: 1.4

        .. versionchanged:: 2.0

            Changed to return :class:`str` and trailing spaces removed.

        Returns
        -------
        str or None
            The request's (0000,0600) *Move Destination* value, without any
            trailing padding spaces. May be ``None`` if the peer's C-MOVE
            request is non-conformant.

        Raises
        ------
        AttributeError
            If the corresponding event is not a C-MOVE request.
        """
        try:
            return cast("C_MOVE", self.request).MoveDestination
        except AttributeError:
            raise AttributeError(
                "The corresponding event is not a C-MOVE request and has no "
                "'Move Destination' parameter"
            )


# Default extended negotiation event handlers
def _async_ops_handler(event: Event) -> Tuple[int, int]:
    """Default handler for when an Asynchronous Operations Window Negotiation
    item is include in the association request.

    See _handlers.doc_handle_async for detailed documentation.
    """
    raise NotImplementedError(
        "No handler has been bound to 'evt.EVT_ASYNC_OPS', so no "
        "Asynchronous Operations Window Negotiation response will be "
        "sent"
    )


def _sop_common_handler(event: Event) -> Dict[UID, "SOPClassCommonExtendedNegotiation"]:
    """Default handler for when one or more SOP Class Common Extended
    Negotiation items are included in the association request.

    See _handlers.doc_handle_sop_common for detailed documentation.
    """
    return {}


def _sop_extended_handler(event: Event) -> Dict[UID, bytes]:
    """Default handler for when one or more SOP Class Extended Negotiation
    items are included in the association request.

    See _handlers.doc_handler_sop_extended for detailed documentation.
    """
    return {}


def _user_identity_handler(event: Event) -> Tuple[bool, Optional[bytes]]:
    """Default handler for when a user identity negotiation item is included
    with the association request.

    See _handlers.doc_handler_userid for detailed documentation.
    """
    raise NotImplementedError(
        "No handler has been bound to 'evt.EVT_USER_ID', so the User Identity "
        "Negotiation will be ignored and the association accepted (unless "
        "rejected for another reason)"
    )


# Default service class request handlers
def _c_echo_handler(event: Event) -> _BasicReturnType:
    """Default handler for when a C-ECHO request is received.

    See _handlers.doc_handle_echo for detailed documentation.
    """
    return 0x0000


def _c_find_handler(event: Event) -> _IteratorType:
    """Default handler for when a C-FIND request is received.

    See _handlers.doc_handle_find for detailed documentation.
    """
    raise NotImplementedError("No handler has been bound to 'evt.EVT_C_FIND'")


def _c_get_handler(event: Event) -> _IteratorType:
    """Default handler for when a C-GET request is received.

    See _handlers.doc_handle_c_get for detailed documentation.
    """
    raise NotImplementedError("No handler has been bound to 'evt.EVT_C_GET'")


def _c_move_handler(event: Event) -> _IteratorType:
    """Default handler for when a C-MOVE request is received.

    See _handlers.doc_handle_move for detailed documentation.
    """
    raise NotImplementedError("No handler has been bound to 'evt.EVT_C_MOVE'")


def _c_store_handler(event: Event) -> _BasicReturnType:
    """Default handler for when a C-STORE request is received.

    See _handlers.doc_handle_store for detailed documentation.
    """
    raise NotImplementedError("No handler has been bound to 'evt.EVT_C_STORE'")


def _n_action_handler(event: Event) -> _DatasetReturnType:
    """Default handler for when an N-ACTION request is received.

    See _handlers.doc_handle_action for detailed documentation.
    """
    raise NotImplementedError("No handler has been bound to 'evt.EVT_N_ACTION'")


def _n_create_handler(event: Event) -> _DatasetReturnType:
    """Default handler for when an N-CREATE request is received.

    See _handlers.doc_handle_create for detailed documentation.
    """
    raise NotImplementedError("No handler has been bound to 'evt.EVT_N_CREATE'")


def _n_delete_handler(event: Event) -> _BasicReturnType:
    """Default handler for when an N-DELETE request is received.

    See _handlers.doc_handle_delete for detailed documentation.
    """
    raise NotImplementedError("No handler has been bound to 'evt.EVT_N_DELETE'")


def _n_event_report_handler(event: Event) -> _DatasetReturnType:
    """Default handler for when an N-EVENT-REPORT request is received.

    See _handlers.doc_handle_event_report for detailed documentation.
    """
    raise NotImplementedError("No handler has been bound to 'evt.EVT_N_EVENT_REPORT'")


def _n_get_handler(event: Event) -> _DatasetReturnType:
    """Default handler for when an N-GET request is received.

    See _handlers.doc_handle_n_get for detailed documentation.
    """
    raise NotImplementedError("No handler has been bound to 'evt.EVT_N_GET'")


def _n_set_handler(event: Event) -> _DatasetReturnType:
    """Default handler for when an N-SET request is received.

    See _handlers.doc_handle_set for detailed documentation.
    """
    raise NotImplementedError("No handler has been bound to 'evt.EVT_N_SET'")
