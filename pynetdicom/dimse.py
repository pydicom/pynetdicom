"""
Implementation of the DIMSE service provider.
"""
from io import BytesIO
import logging
try:
    import queue
except ImportError:
    import Queue as queue  # Python 2 compatibility

from pynetdicom import evt
from pynetdicom.dimse_messages import *
from pynetdicom.dimse_primitives import *
from pynetdicom.pdu_primitives import P_DATA


LOGGER = logging.getLogger('pynetdicom.dimse')

_RQ_TO_MESSAGE = {
    C_ECHO : C_ECHO_RQ,
    C_STORE : C_STORE_RQ,
    C_FIND : C_FIND_RQ,
    C_MOVE : C_MOVE_RQ,
    C_GET : C_GET_RQ,
    N_EVENT_REPORT : N_EVENT_REPORT_RQ,
    N_GET : N_GET_RQ,
    N_SET : N_SET_RQ,
    N_ACTION : N_ACTION_RQ,
    N_CREATE : N_CREATE_RQ,
    N_DELETE : N_DELETE_RQ
}
_RSP_TO_MESSAGE = {
    C_ECHO : C_ECHO_RSP,
    C_STORE : C_STORE_RSP,
    C_FIND : C_FIND_RSP,
    C_MOVE : C_MOVE_RSP,
    C_GET : C_GET_RSP,
    C_CANCEL : C_CANCEL_RQ,
    N_EVENT_REPORT : N_EVENT_REPORT_RSP,
    N_GET : N_GET_RSP,
    N_SET : N_SET_RSP,
    N_ACTION : N_ACTION_RSP,
    N_CREATE : N_CREATE_RSP,
    N_DELETE : N_DELETE_RSP
}


class DIMSEServiceProvider(object):
    """The DIMSE service provider.

    A DICOM AE uses the services provided by the DICOM Message Service Element
    (DIMSE). DIMSE specifies two sets of services.

    - DIMSE-C supports operations associated with composite SOP Classes and
      provides effective compatibility with the previous versions of the DICOM
      standards.
    - DIMSE-N supports operations associated with normalised SOP Classes and
      provides an extended set of object-orientated operations and
      notifications

    **Service Overview**

    The DIMSE service provider supports communication between peer DIMSE
    service users. A service user acts in one of two roles:

    - invoking DIMSE user
    - performing DIMSE user

    Service users make use of service primitives provided by the DIMSE service
    provider. A service primitive shall be one of the following types:

    - request primitive
    - indication primitive
    - response primitive
    - confirmation primitive

    These primitives are used as follows:

    - The invoking service user issues a request primitive to the DIMSE
      provider
    - The DIMSE provider receives the request primitive and issues an
      indication primitive to the performing service user
    - The performing service user receives the indication primitive and
      performs the requested service
    - The performing service user issues a response primitive to the DIMSE
      provider
    - The DIMSE provider receives the response primitive and issues a
      confirmation primitive to the invoking service user
    - The invoking service user receives the confirmation primitive, completing
      the DIMSE service.

    **Service Primitive Classes**

    * DIMSE-C: C_ECHO, C_STORE, C_GET, C_FIND, C_MOVE
    * DIMSE-N: N_EVENT_REPORT, N_GET, N_GET, N_ACTION, N_CREATE, N_DELETE

    **Protocol Machine**

    PS3.7 8.1
    The DIMSE protocol machine defines the procedures and the encoding rules
    necessary to construct Messages used to exchange command requests and
    responses between peer DIMSE service users.

    The DIMSE protocol machine accepts service user requests and response
    service primitives and constructs Messages defined by the procedures in
    PS3.7 9.3 and 10.3. The DIMSE protocol machine accepts Messages and passes
    them to the DIMSE service user by the means of indication and confirmation
    service primitives.

    **Messages**

    +----------------+-----------------------+------------------------+
    | Primitive      | Type                  | Message Class          |
    +----------------+-----------------------+------------------------+
    | C-CANCEL       | Request/indication    | C_CANCEL_R             |
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
        A dict of {MessageIDBeingRespondedTo : C_CANCEL} messages received.
        The dict is cleared out at the start and end of Service Class
        operations and is limited to a maximum of 10 messages.
    message : dimse_messages.DIMSEMessage
        The DIMSE message.
    msg_queue: queue.queue of dimse_messages.DIMSEMessage
        A queue holding decoded DIMSE Message primitives received from the
        peer, except for C-CANCEL requests.

    References
    ----------

    * DICOM Standard, Part 7
    """
    def __init__(self, assoc):
        """Initialise the DIMSE service provider.

        Parameters
        ----------
        assoc : association.Association
            The Association to provide DIMSE services for.
        """
        self._assoc = assoc

        self.cancel_req = {}
        self.message = None
        self.msg_queue = queue.Queue()

    @property
    def assoc(self):
        """Return the ACSE's Association."""
        return self._assoc

    @property
    def dimse_timeout(self):
        """Return the DIMSE timeout as numeric or None."""
        return self.assoc.dimse_timeout

    @property
    def dul(self):
        """Return the Association's DUL service provider."""
        return self.assoc.dul

    def get_msg(self, block=False):
        """Get the next available DIMSE message.

        Parameters
        ----------
        block : bool
            If True then the function will block until either a message is
            available or `dimse_timeout` expires, otherwise non-blocking.

        Returns
        -------
        int, dimse_messages.DIMSEMessage or None, None
            The next available (context ID, DIMSE message), which is taken off
            the queue, or (None, None) if no messages are available within
            the `dimse_timeout` period.
        """
        try:
            return self.msg_queue.get(block=block, timeout=self.dimse_timeout)
        except queue.Empty:
            return None, None

    @property
    def maximum_pdu_size(self):
        """Return the peer's maximum PDU length."""
        if self.assoc.is_requestor:
            return self.assoc.acceptor.maximum_length
        elif self.assoc.is_acceptor:
            return self.assoc.requestor.maximum_length

    def peek_msg(self):
        """Return the first message in the message queue or None.

        Returns
        -------
        int, dimse_messages.DIMSEMessage or None, None
            The first (context ID, message) in the queue if one is available,
            otherwise (None, None). No messages are taken out of the queue.
        """
        try:
            return self.msg_queue.queue[0]
        except (queue.Empty, IndexError):
            return None, None

    def receive_primitive(self, primitive):
        """Process a P-DATA primitive received from the remote.

        A DIMSE message is split into one or more P-DATA primitives, which
        must be sent in sequential order. While waiting for all the P-DATA
        primitives associated with a message the encoded data is stored in
        self.message, which is decoded only when complete and converted
        into a DIMSE Message primitive which is added to the `msg_queue`.

        This makes it possible to process incoming P-DATA primitives into
        DIMSE messages while a service class implementation is running.

        Parameters
        ----------
        primitive : pdu_primitives.P_DATA
            A P-DATA primitive received from the peer to be processed.
        """
        if self.message is None:
            self.message = DIMSEMessage()

        if self.message.decode_msg(primitive):
            # Trigger event
            evt.trigger(
                self.assoc, evt.EVT_DIMSE_RECV, {'message' : self.message}
            )

            context_id = self.message.context_id
            try:
                primitive = self.message.message_to_primitive()
            except Exception as exc:
                LOGGER.error("Received an invalid DIMSE message")
                LOGGER.exception(exc)
                self.dul.event_queue.put('Evt19')
                return

            # Keep C-CANCEL requests separate from other messages
            # Only allow up to 10 C-CANCEL requests
            if isinstance(primitive, C_CANCEL) and len(self.cancel_req) < 10:
                msg_id = primitive.MessageIDBeingRespondedTo
                self.cancel_req[msg_id] = primitive
            elif (isinstance(primitive, N_EVENT_REPORT) and
                                                primitive.is_valid_request):
                # N-EVENT-REPORT service requests are handled immediately
                self.assoc._serve_request(primitive, context_id)
            else:
                self.msg_queue.put((context_id, primitive))

            # Fix for memory leak, Issue #41
            #   Reset the DIMSE message, ready for the next one
            self.message.encoded_command_set = BytesIO()
            self.message.data_set = BytesIO()
            self.message = None

    def send_msg(self, primitive, context_id):
        """Send a DIMSE-C or DIMSE-N message to the peer AE.

        Parameters
        ----------
        primitive : dimse_primitives DIMSE Primitive class
            The DIMSE message primitive to send to the peer.
        context_id : int
            The ID of the presentation context that the message is to be
            sent under.
        """
        if primitive.MessageIDBeingRespondedTo is None:
            dimse_msg = _RQ_TO_MESSAGE[primitive.__class__]()
        else:
            dimse_msg = _RSP_TO_MESSAGE[primitive.__class__]()

        # Convert DIMSE primitive to DIMSE Message
        dimse_msg.primitive_to_message(primitive)
        dimse_msg.context_id = context_id

        # Trigger event
        evt.trigger(
            self.assoc, evt.EVT_DIMSE_SENT, {'message' : dimse_msg}
        )

        # Split the full messages into P-DATA chunks,
        #   each below the max_pdu size
        for pdata in dimse_msg.encode_msg(context_id, self.maximum_pdu_size):
            self.dul.send_pdu(pdata)
