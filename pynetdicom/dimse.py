"""
Implementation of the DIMSE service provider.
"""

from io import BytesIO
import logging
import queue
import threading
from typing import TYPE_CHECKING, cast

from pynetdicom import evt

# pylint: disable=no-name-in-module
from pynetdicom.dimse_messages import (
    C_STORE_RQ,
    C_STORE_RSP,
    C_FIND_RQ,
    C_FIND_RSP,
    C_GET_RQ,
    C_GET_RSP,
    C_MOVE_RQ,
    C_MOVE_RSP,
    C_ECHO_RQ,
    C_ECHO_RSP,
    C_CANCEL_RQ,
    N_EVENT_REPORT_RQ,
    N_GET_RQ,
    N_SET_RQ,
    N_ACTION_RQ,
    N_CREATE_RQ,
    N_DELETE_RQ,
    N_EVENT_REPORT_RSP,
    N_GET_RSP,
    N_SET_RSP,
    N_ACTION_RSP,
    N_CREATE_RSP,
    N_DELETE_RSP,
    DIMSEMessage,
)

# pylint: enable=no-name-in-module
from pynetdicom.dimse_primitives import (
    C_STORE,
    C_FIND,
    C_GET,
    C_MOVE,
    C_ECHO,
    C_CANCEL,
    N_EVENT_REPORT,
    N_GET,
    N_SET,
    N_ACTION,
    N_CREATE,
    N_DELETE,
    DimsePrimitiveType,
    DimseServiceType,
)
from pynetdicom.utils import make_target

if TYPE_CHECKING:  # pragma: no cover
    from pynetdicom.association import Association
    from pynetdicom.dul import DULServiceProvider
    from pynetdicom.pdu_primitives import P_DATA


LOGGER = logging.getLogger(__name__)

_RQ_TO_MESSAGE = {
    C_ECHO: C_ECHO_RQ,
    C_STORE: C_STORE_RQ,
    C_FIND: C_FIND_RQ,
    C_MOVE: C_MOVE_RQ,
    C_GET: C_GET_RQ,
    N_EVENT_REPORT: N_EVENT_REPORT_RQ,
    N_GET: N_GET_RQ,
    N_SET: N_SET_RQ,
    N_ACTION: N_ACTION_RQ,
    N_CREATE: N_CREATE_RQ,
    N_DELETE: N_DELETE_RQ,
}
_RSP_TO_MESSAGE = {
    C_ECHO: C_ECHO_RSP,
    C_STORE: C_STORE_RSP,
    C_FIND: C_FIND_RSP,
    C_MOVE: C_MOVE_RSP,
    C_GET: C_GET_RSP,
    C_CANCEL: C_CANCEL_RQ,
    N_EVENT_REPORT: N_EVENT_REPORT_RSP,
    N_GET: N_GET_RSP,
    N_SET: N_SET_RSP,
    N_ACTION: N_ACTION_RSP,
    N_CREATE: N_CREATE_RSP,
    N_DELETE: N_DELETE_RSP,
}

_QueueItem = tuple[None, None] | tuple[int, DimseServiceType]


class DIMSEServiceProvider:
    """The DIMSE service provider.

    **Messages**

    +----------------+-----------------------+------------------------+
    | Primitive      | Type                  | Message Class          |
    +================+=======================+========================+
    | C-CANCEL       | Request/indication    | C_CANCEL_RQ            |
    +----------------+-----------------------+------------------------+
    | C-ECHO         | Request/indication    | C_ECHO_RQ              |
    |                +-----------------------+------------------------+
    |                | Response/confirmation | C_ECHO_RSP             |
    +----------------+-----------------------+------------------------+
    | C-FIND         | Request/indication    | C_FIND_RQ              |
    |                +-----------------------+------------------------+
    |                | Response/confirmation | C_FIND_RSP             |
    +----------------+-----------------------+------------------------+
    | C-GET          | Request/indication    | C_GET_RQ               |
    |                +-----------------------+------------------------+
    |                | Response/confirmation | C_GET_RSP              |
    +----------------+-----------------------+------------------------+
    | C-MOVE         | Request/indication    | C_MOVE_RQ              |
    |                +-----------------------+------------------------+
    |                | Response/confirmation | C_MOVE_RSP             |
    +----------------+-----------------------+------------------------+
    | C-STORE        | Request/indication    | C_STORE_RQ             |
    |                +-----------------------+------------------------+
    |                | Response/confirmation | C_STORE_RSP            |
    +----------------+-----------------------+------------------------+
    | N-ACTION       | Request/indication    | N_ACTION_RQ            |
    |                +-----------------------+------------------------+
    |                | Response/confirmation | N_ACTION_RSP           |
    +----------------+-----------------------+------------------------+
    | N-CREATE       | Request/indication    | N_CREATE_RQ            |
    |                +-----------------------+------------------------+
    |                | Response/confirmation | N_CREATE_RSP           |
    +----------------+-----------------------+------------------------+
    | N-DELETE       | Request/indication    | N_DELETE_RQ            |
    |                +-----------------------+------------------------+
    |                | Response/confirmation | N_DELETE_RSP           |
    +----------------+-----------------------+------------------------+
    | N-EVENT-REPORT | Request/indication    | N_EVENT_REPORT_RQ      |
    |                +-----------------------+------------------------+
    |                | Response/confirmation | N_EVENT_REPORT_RSP     |
    +----------------+-----------------------+------------------------+
    | N-GET          | Request/indication    | N_GET_RQ               |
    |                +-----------------------+------------------------+
    |                | Response/confirmation | N_GET_RSP              |
    +----------------+-----------------------+------------------------+
    | N-SET          | Request/indication    | N_SET_RQ               |
    |                +-----------------------+------------------------+
    |                | Response/confirmation | N_SET_RSP              |
    +----------------+-----------------------+------------------------+

    Attributes
    ----------
    cancel_rq : dict
        A dict of ``{MessageIDBeingRespondedTo : C_CANCEL}`` messages received.
        The dict is cleared out at the start and end of Service Class
        operations and is limited to a maximum of 10 messages.
    message : dimse_messages.DIMSEMessage or None
        The DIMSE message currently being received.
    msg_queue: queue.queue of dimse_messages.DIMSEMessage
        A queue holding decoded DIMSE Message primitives received from the
        peer, except for C-CANCEL requests.

    References
    ----------

    * DICOM Standard, :dcm:`Part 7<part07/PS3.7.html>`
    """

    def __init__(self, assoc: "Association") -> None:
        """Initialise the DIMSE service provider.

        Parameters
        ----------
        assoc : association.Association
            The association to provide DIMSE services for.
        """
        self._assoc = assoc

        self.cancel_req: dict[int, C_CANCEL] = {}
        self.message: DIMSEMessage | None = None
        self.msg_queue: "queue.Queue[_QueueItem]" = queue.Queue()

    @property
    def assoc(self) -> "Association":
        """Return the parent :class:`~pynetdicom.association.Association`."""
        return self._assoc

    @property
    def dimse_timeout(self) -> float | None:
        """Return the DIMSE timeout as numeric or ``None``."""
        return self.assoc.dimse_timeout

    @property
    def dul(self) -> "DULServiceProvider":
        """Return the :class:`~pynetdicom.dul.DULServiceProvider`."""
        return self.assoc.dul

    def get_msg(self, block: bool = False) -> _QueueItem:
        """Get the next available DIMSE message.

        Parameters
        ----------
        block : bool
            If ``True`` then the function will block until either a message is
            available or :attr:`~DIMSEServiceProvider.dimse_timeout` expires,
            otherwise non-blocking.

        Returns
        -------
        (int, dimse_messages.DIMSEMessage) or (None, None)
            The next available (*Context ID*, *DIMSE Message*), which is taken
            off the queue, or ``(None, None)`` if the peer has aborted the
            association, the connection is closed or if no messages are
            available within the :attr:`~DIMSEServiceProvider.dimse_timeout`
            period.
        """
        try:
            return self.msg_queue.get(block=block, timeout=self.dimse_timeout)
        except queue.Empty:
            return None, None

    @property
    def maximum_pdu_size(self) -> int:
        """Return the peer's maximum PDU length as :class:`int`."""
        if self.assoc.is_requestor:
            return cast(int, self.assoc.acceptor.maximum_length)

        return cast(int, self.assoc.requestor.maximum_length)

    def peek_msg(self) -> _QueueItem:
        """Return the first message in the message queue or ``None``.

        Returns
        -------
        (int, dimse_messages.DIMSEMessage) or (None, None)
            The first (*Context ID*, *Message*) in the queue if one is
            available, otherwise ``(None, None)``. No messages are taken out
            of the queue.
        """
        try:
            return cast(_QueueItem, self.msg_queue.queue[0])
        except (queue.Empty, IndexError):
            return None, None

    def receive_primitive(self, primitive: "P_DATA") -> None:
        """Process a P-DATA primitive received from the remote.

        A DIMSE message is split into one or more P-DATA primitives, which
        must be sent in sequential order. While waiting for all the P-DATA
        primitives associated with a message the encoded data is stored in
        :attr:`~DIMSEServiceProvider.message`, which is decoded only when
        complete and converted into a DIMSE Message primitive which is added
        to the :attr:`~DIMSEServiceProvider.msg_queue`.

        This makes it possible to process incoming P-DATA primitives into
        DIMSE messages while a service class implementation is running.

        Parameters
        ----------
        primitive : pdu_primitives.P_DATA
            A P-DATA primitive received from the peer to be processed.
        """
        if self.message is None:
            self.message = DIMSEMessage()

        if self.message.decode_msg(primitive, self.assoc):
            # Trigger event
            evt.trigger(self.assoc, evt.EVT_DIMSE_RECV, {"message": self.message})

            context_id = cast(int, self.message.context_id)
            try:
                d_primitive = self.message.message_to_primitive()
            except Exception as exc:
                LOGGER.error("Received an invalid DIMSE message")
                LOGGER.exception(exc)
                self.dul.event_queue.put("Evt19")
                # Shouldn't need to reset `self.message` as Evt19 will end
                #   the association
                return

            # Keep C-CANCEL requests separate from other messages
            # Only allow up to 10 C-CANCEL requests
            if isinstance(d_primitive, C_CANCEL) and len(self.cancel_req) < 10:
                msg_id = cast(int, d_primitive.MessageIDBeingRespondedTo)
                self.cancel_req[msg_id] = d_primitive
            elif (
                isinstance(d_primitive, N_EVENT_REPORT) and d_primitive.is_valid_request
            ):
                # N-EVENT-REPORT service requests are handled immediately
                # Ugly hack, but would block the DUL otherwise
                t = threading.Thread(
                    target=make_target(self.assoc._serve_request),
                    args=(d_primitive, context_id),
                )
                t.start()
            else:
                self.msg_queue.put((context_id, cast(DimseServiceType, d_primitive)))

            # Fix for memory leak, Issue #41
            #   Reset the DIMSE message, ready for the next one
            self.message.encoded_command_set = BytesIO()
            self.message.data_set = BytesIO()
            self.message._data_set_file = None
            self.message._data_set_path = None
            self.message = None

    def send_msg(self, primitive: DimsePrimitiveType, context_id: int) -> None:
        """Encode and send a DIMSE-C or DIMSE-N message to the peer AE.

        Parameters
        ----------
        primitive : dimse_primitives DIMSE Primitive class
            The DIMSE message primitive to send to the peer.
        context_id : int
            The ID of the presentation context that the message is to be
            sent under.
        """
        if primitive.MessageIDBeingRespondedTo is None:
            dimse_msg = _RQ_TO_MESSAGE[primitive.__class__]()  # type: ignore
        else:
            dimse_msg = _RSP_TO_MESSAGE[primitive.__class__]()

        # Convert DIMSE primitive to DIMSE Message
        dimse_msg.primitive_to_message(primitive)
        dimse_msg.context_id = context_id

        # Trigger event
        evt.trigger(self.assoc, evt.EVT_DIMSE_SENT, {"message": dimse_msg})

        # Split the full messages into P-DATA chunks,
        #   each below the max_pdu size
        for pdata in dimse_msg.encode_msg(context_id, self.maximum_pdu_size):
            self.dul.send_pdu(pdata)
