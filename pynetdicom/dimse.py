"""
Implementation of the DIMSE service provider.
"""
from io import BytesIO
import logging
try:
    import queue
except ImportError:
    import Queue as queue  # Python 2 compatibility
import time

# pylint: disable=no-name-in-module
# TODO: Consider switching to * import, check that _var aren't shown (__var?)
from pynetdicom.dimse_messages import (
    C_STORE_RQ, C_STORE_RSP, C_FIND_RQ, C_FIND_RSP, C_GET_RQ, C_GET_RSP,
    C_MOVE_RQ, C_MOVE_RSP, C_ECHO_RQ, C_ECHO_RSP, C_CANCEL_RQ,
    N_EVENT_REPORT_RQ, N_EVENT_REPORT_RSP, N_GET_RQ, N_GET_RSP, N_SET_RQ,
    N_SET_RSP, N_ACTION_RQ, N_ACTION_RSP, N_CREATE_RQ, N_CREATE_RSP,
    N_DELETE_RQ, N_DELETE_RSP, DIMSEMessage
)
# pylint: enable=no-name-in-module
from pynetdicom.dimse_primitives import (
    C_STORE, C_FIND, C_GET, C_MOVE, C_ECHO, N_EVENT_REPORT, N_GET, N_SET,
    N_ACTION, N_CREATE, N_DELETE, C_CANCEL
)
from pynetdicom.pdu_primitives import P_DATA
from pynetdicom.sop_class import uid_to_service_class
from pynetdicom.timer import Timer
from pynetdicom._globals import DEFAULT_MAX_LENGTH

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
    dimse_timeout : numeric or None
        The number of seconds before the DIMSE service timeout. A value of
        ``None`` indicates no timeout.
    dul : dul.DULServiceProvider
        The DICOM Upper Layer service provider.
    maximum_pdu_size : int
            The maximum PDU size when sending DIMSE messages.
    message : dimse_messages.DIMSEMessage
        The DIMSE message.
    msg_queue: queue.queue of dimse_messages.DIMSEMessage
        A queue holding decoded DIMSE Message primitives received from the
        peer, except for C-CANCEL requests.

    References
    ----------

    * DICOM Standard, Part 7
    """
    # pylint: disable=too-many-public-methods
    def __init__(self, dul, dimse_timeout=None,
                 maximum_pdu_size=DEFAULT_MAX_LENGTH):
        """Start the DIMSE service provider.

        Parameters
        ----------
        dul : dul.DULServiceProvider
            The DICOM Upper Layer service provider.
        dimse_timeout : int or float or None
            The number of seconds before the DIMSE service timeout. A value of
            None indicates no timeout.
        maximum_pdu_size : int
            The maximum PDU size when sending DIMSE messages, default 16382.
        """
        self.cancel_req = {}
        self.dimse_timeout = dimse_timeout
        self.dul = dul
        self.maximum_pdu_size = maximum_pdu_size
        self.message = None
        self.msg_queue = queue.Queue()

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
            # Callback
            # TODO: Make this a package level option to increase speed
            self.on_receive_dimse_message(self.message)

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

        # Callbacks
        self.on_send_dimse_message(dimse_msg)

        # Split the full messages into P-DATA chunks,
        #   each below the max_pdu size
        for pdata in dimse_msg.encode_msg(context_id, self.maximum_pdu_size):
            self.dul.send_pdu(pdata)

    # Debugging and AE callbacks
    def on_send_dimse_message(self, message):
        """Controls which debugging function is called when sending.

        Will be called immediately prior to encoding and sending a DIMSE
        message.

        Parameters
        ----------
        message : dimse_messages.DIMSEMessage
            The DIMSE message to be sent.
        """
        callback = {C_ECHO_RQ: self.debug_send_c_echo_rq,
                    C_ECHO_RSP: self.debug_send_c_echo_rsp,
                    C_FIND_RQ: self.debug_send_c_find_rq,
                    C_FIND_RSP: self.debug_send_c_find_rsp,
                    C_GET_RQ: self.debug_send_c_get_rq,
                    C_GET_RSP: self.debug_send_c_get_rsp,
                    C_MOVE_RQ: self.debug_send_c_move_rq,
                    C_MOVE_RSP: self.debug_send_c_move_rsp,
                    C_STORE_RQ: self.debug_send_c_store_rq,
                    C_STORE_RSP: self.debug_send_c_store_rsp,
                    C_CANCEL_RQ: self.debug_send_c_cancel_rq,
                    N_EVENT_REPORT_RQ: self.debug_send_n_event_report_rq,
                    N_EVENT_REPORT_RSP: self.debug_send_n_event_report_rsp,
                    N_SET_RQ: self.debug_send_n_set_rq,
                    N_SET_RSP: self.debug_send_n_set_rsp,
                    N_GET_RQ: self.debug_send_n_get_rq,
                    N_GET_RSP: self.debug_send_n_get_rsp,
                    N_ACTION_RQ: self.debug_send_n_action_rq,
                    N_ACTION_RSP: self.debug_send_n_action_rsp,
                    N_CREATE_RQ: self.debug_send_n_create_rq,
                    N_CREATE_RSP: self.debug_send_n_create_rsp,
                    N_DELETE_RQ: self.debug_send_n_delete_rq,
                    N_DELETE_RSP: self.debug_send_n_delete_rsp}

        callback[type(message)](message)

    def on_receive_dimse_message(self, message):
        """Controls which debugging function is called when receiving.

        Function will be called immediately after receiving and decoding a
        DIMSE message.

        Parameters
        ----------
        message : dimse_messages.DIMSEMessage
            The DIMSE message that was received.
        """
        callback = {C_ECHO_RQ: self.debug_receive_c_echo_rq,
                    C_ECHO_RSP: self.debug_receive_c_echo_rsp,
                    C_FIND_RQ: self.debug_receive_c_find_rq,
                    C_FIND_RSP: self.debug_receive_c_find_rsp,
                    C_CANCEL_RQ: self.debug_receive_c_cancel_rq,
                    C_GET_RQ: self.debug_receive_c_get_rq,
                    C_GET_RSP: self.debug_receive_c_get_rsp,
                    C_MOVE_RQ: self.debug_receive_c_move_rq,
                    C_MOVE_RSP: self.debug_receive_c_move_rsp,
                    C_STORE_RQ: self.debug_receive_c_store_rq,
                    C_STORE_RSP: self.debug_receive_c_store_rsp,
                    N_EVENT_REPORT_RQ: self.debug_receive_n_event_report_rq,
                    N_EVENT_REPORT_RSP: self.debug_receive_n_event_report_rsp,
                    N_SET_RQ: self.debug_receive_n_set_rq,
                    N_SET_RSP: self.debug_receive_n_set_rsp,
                    N_GET_RQ: self.debug_receive_n_get_rq,
                    N_GET_RSP: self.debug_receive_n_get_rsp,
                    N_ACTION_RQ: self.debug_receive_n_action_rq,
                    N_ACTION_RSP: self.debug_receive_n_action_rsp,
                    N_CREATE_RQ: self.debug_receive_n_create_rq,
                    N_CREATE_RSP: self.debug_receive_n_create_rsp,
                    N_DELETE_RQ: self.debug_receive_n_delete_rq,
                    N_DELETE_RSP: self.debug_receive_n_delete_rsp}

        callback[type(message)](message)

    # Mid-level DIMSE Message related logging/debugging
    # pylint: disable=unused-argument
    @staticmethod
    def debug_send_c_echo_rq(msg):
        """Debugging function when a C-ECHO-RQ is sent.

        **C-ECHO Request Parameters**

        | (M) Message ID
        | (M) Affected SOP Class UID

        Parameters
        ----------
        msg : dimse_messages.C_ECHO_RQ
            The C-ECHO-RQ message to be sent.
        """
        cs = msg.command_set
        LOGGER.info("Sending Echo Request: MsgID %s", cs.MessageID)

    @staticmethod
    def debug_send_c_echo_rsp(msg):
        """Debugging function when a C-ECHO-RSP is sent.

        **C-ECHO Response Parameters**

        | (U) Message ID
        | (M) Message ID Being Responded To
        | (U) Affected SOP Class UID
        | (M) Status

        Parameters
        ----------
        msg : dimse_messages.C_ECHO_RSP
            The C-ECHO-RSP message to be sent.
        """
        pass

    @staticmethod
    def debug_send_c_store_rq(msg):
        """Debugging function when a C-STORE-RQ is sent.

        **C-STORE Request Elements**

        | (M) Message ID
        | (M) Affected SOP Class UID
        | (M) Affected SOP Instance UID
        | (M) Priority
        | (U) Move Originator Application Entity Title
        | (U) Move Originator Message ID
        | (M) Data Set

        Parameters
        ----------
        msg : dimse_messages.C_STORE_RQ
            The C-STORE-RQ message to be sent.
        """
        cs = msg.command_set

        priority_str = {2: 'Low',
                        0: 'Medium',
                        1: 'High'}
        priority = priority_str[cs.Priority]

        dataset = 'None'
        if msg.data_set and msg.data_set.getvalue() != b'':
            dataset = 'Present'

        if cs.AffectedSOPClassUID.name == 'CT Image Storage':
            dataset_type = ', (CT)'
        elif cs.AffectedSOPClassUID.name == 'MR Image Storage':
            dataset_type = ', (MR)'
        else:
            dataset_type = ''

        LOGGER.info("Sending Store Request: MsgID %s%s",
                    cs.MessageID, dataset_type)

        s = []
        s.append(
            '===================== OUTGOING DIMSE MESSAGE ===================='
        )
        s.append('Message Type                  : {0!s}'.format('C-STORE RQ'))
        s.append('Message ID                    : {0!s}'.format(cs.MessageID))
        s.append('Affected SOP Class UID        : {0!s}'
                 .format(cs.AffectedSOPClassUID))
        s.append('Affected SOP Instance UID     : {0!s}'
                 .format(cs.AffectedSOPInstanceUID))
        s.append('Data Set                      : {0!s}'.format(dataset))
        s.append('Priority                      : {0!s}'.format(priority))
        s.append(
            '======================= END DIMSE MESSAGE ======================='
        )
        for line in s:
            LOGGER.debug(line)

    @staticmethod
    def debug_send_c_store_rsp(msg):
        """Debugging function when a C-STORE-RSP is sent.

        **C-STORE Response Elements**

        | (U) Message ID
        | (M) Message ID Being Responded To
        | (U) Affected SOP Class UID
        | (U) Affected SOP Instance UID
        | (M) Status

        Parameters
        ----------
        msg : dimse_messages.C_STORE_RSP
            The C-STORE-RSP message to be sent.
        """
        pass

    @staticmethod
    def debug_send_c_find_rq(msg):
        """Debugging function when a C-FIND-RQ is sent.

        **C-FIND Request Parameters**

        | (M) Message ID
        | (M) Affected SOP Class UID
        | (M) Priority
        | (M) Identifier

        Parameters
        ----------
        msg : dimse_messages.C_FIND_RQ
            The C-FIND-RQ message to be sent.
        """
        cs = msg.command_set

        priority_str = {2: 'Low',
                        0: 'Medium',
                        1: 'High'}
        priority = priority_str[cs.Priority]

        dataset = 'None'
        if msg.data_set and msg.data_set.getvalue() != b'':
            dataset = 'Present'

        LOGGER.info("Sending Find Request: MsgID %s", cs.MessageID)

        s = []
        s.append(
            '===================== OUTGOING DIMSE MESSAGE ===================='
        )
        s.append('Message Type                  : {0!s}'.format('C-FIND RQ'))
        s.append('Presentation Context ID       : {0!s}'
                 .format(msg.context_id))
        s.append('Message ID                    : {0!s}'.format(cs.MessageID))
        s.append('Affected SOP Class UID        : {0!s}'
                 .format(cs.AffectedSOPClassUID))
        s.append('Identifier                    : {0!s}'.format(dataset))
        s.append('Priority                      : {0!s}'.format(priority))
        s.append(
            '======================= END DIMSE MESSAGE ======================='
        )

        for line in s:
            LOGGER.debug(line)

    @staticmethod
    def debug_send_c_find_rsp(msg):
        """Debugging function when a C-FIND-RSP is sent.

        **C-FIND Response Parameters**

        | (U) Message ID
        | (M) Message ID Being Responded To
        | (U) Affected SOP Class UID
        | (C) Identifier
        | (M) Status

        Parameters
        ----------
        msg : dimse_messages.C_FIND_RSP
            The C-FIND-RSP message to be sent.
        """
        cs = msg.command_set

        dataset = 'None'
        if msg.data_set and msg.data_set.getvalue() != b'':
            dataset = 'Present'

        s = []
        s.append(
            '===================== OUTGOING DIMSE MESSAGE ===================='
        )
        s.append('Message Type                  : {0!s}'.format('C-FIND RSP'))
        s.append('Message ID Being Responded To : {0!s}'
                 .format(cs.MessageIDBeingRespondedTo))
        if 'AffectedSOPClassUID' in cs:
            s.append('Affected SOP Class UID        : {0!s}'
                     .format(cs.AffectedSOPClassUID))
        s.append('Data Set                      : {0!s}'.format(dataset))
        s.append('DIMSE Status                  : 0x{0:04x}'.format(cs.Status))

        s.append(
            '======================= END DIMSE MESSAGE ======================='
        )

        for line in s:
            LOGGER.debug(line)

    @staticmethod
    def debug_send_c_get_rq(msg):
        """Debugging function when a C-GET-RQ is sent.

        **C-GET Request Parameters**

        | (M) Message ID
        | (M) Affected SOP Class UID
        | (M) Priority
        | (M) Identifier

        Parameters
        ----------
        msg : dimse_messages.C_GET_RQ
            The C-GET-RQ message to be sent.
        """
        cs = msg.command_set

        priority_str = {2: 'Low',
                        0: 'Medium',
                        1: 'High'}
        priority = priority_str[cs.Priority]

        dataset = 'None'
        if msg.data_set and msg.data_set.getvalue() != b'':
            dataset = 'Present'

        LOGGER.info("Sending Get Request: MsgID %s", cs.MessageID)

        s = []
        s.append(
            '===================== OUTGOING DIMSE MESSAGE ===================='
        )
        s.append('Message Type                  : {0!s}'.format('C-GET RQ'))
        s.append('Message ID                    : {0!s}'.format(cs.MessageID))
        s.append('Affected SOP Class UID        : {0!s}'
                 .format(cs.AffectedSOPClassUID))
        s.append('Data Set                      : {0!s}'.format(dataset))
        s.append('Priority                      : {0!s}'.format(priority))
        s.append(
            '======================= END DIMSE MESSAGE ======================='
        )
        for line in s:
            LOGGER.debug(line)

    @staticmethod
    def debug_send_c_get_rsp(msg):
        """Debugging function when a C-GET-RSP is sent.

        **C-GET Response Parameters**

        | (U) Message ID
        | (M) Message ID Being Responded To
        | (U) Affected SOP Class UID
        | (U) Identifier
        | (M) Status
        | (C) Number of Remaining Sub-operations
        | (C) Number of Completed Sub-operations
        | (C) Number of Failed Sub-operations
        | (C) Number of Warning Sub-operations

        Parameters
        ----------
        msg : dimse_messages.C_GET_RSP
            The C-GET-RSP message to be sent.
        """
        cs = msg.command_set

        dataset = 'None'
        if msg.data_set and msg.data_set.getvalue() != b'':
            dataset = 'Present'

        affected_sop = getattr(cs, 'AffectedSOPClassUID', 'None')

        s = []
        s.append(
            '===================== OUTGOING DIMSE MESSAGE ===================='
        )
        s.append('Message Type                  : {0!s}'.format('C-GET RSP'))
        s.append('Message ID Being Responded To : {0!s}'
                 .format(cs.MessageIDBeingRespondedTo))
        if 'AffectedSOPClassUID' in cs:
            s.append('Affected SOP Class UID        : {0!s}'
                     .format(affected_sop))
        s.append('Data Set                      : {0!s}'.format(dataset))
        s.append('DIMSE Status                  : 0x{0:04x}'.format(cs.Status))

        s.append(
            '======================= END DIMSE MESSAGE ======================='
        )

        for line in s:
            LOGGER.debug(line)

    @staticmethod
    def debug_send_c_move_rq(msg):
        """Debugging function when a C-MOVE-RQ is sent.

        **C-MOVE Request Parameters**

        | (M) Message ID
        | (M) Affected SOP Class UID
        | (M) Priority
        | (M) Move Destination
        | (M) Identifier

        Parameters
        ----------
        msg : dimse_messages.C_MOVE_RQ
            The C-MOVE-RQ message to be sent.
        """
        cs = msg.command_set

        priority_str = {2: 'Low',
                        0: 'Medium',
                        1: 'High'}
        priority = priority_str[cs.Priority]

        identifier = 'None'
        if msg.data_set and msg.data_set.getvalue() != b'':
            identifier = 'Present'

        LOGGER.info("Sending Move Request: MsgID %s", cs.MessageID)

        s = []
        s.append(
            '===================== OUTGOING DIMSE MESSAGE ===================='
        )
        s.append('Message Type                  : {0!s}'.format('C-MOVE RQ'))
        s.append('Message ID                    : {0!s}'.format(cs.MessageID))
        s.append('Affected SOP Class UID        : {0!s}'
                 .format(cs.AffectedSOPClassUID))
        s.append('Move Destination              : {0!s}'
                 .format(cs.MoveDestination))
        s.append('Identifier                    : {0!s}'.format(identifier))
        s.append('Priority                      : {0!s}'.format(priority))
        s.append(
            '======================= END DIMSE MESSAGE ======================='
        )
        for line in s:
            LOGGER.debug(line)
        return None

    @staticmethod
    def debug_send_c_move_rsp(msg):
        """Debugging function when a C-MOVE-RSP is sent.

        **C-MOVE Response Parameters**

        | (U) Message ID
        | (M) Message ID Being Responded To
        | (U) Affected SOP Class UID
        | (U) Identifier
        | (M) Status
        | (C) Number of Remaining Sub-operations
        | (C) Number of Completed Sub-operations
        | (C) Number of Failed Sub-operations
        | (C) Number of Warning Sub-operations

        Parameters
        ----------
        msg : dimse_messages.C_MOVE_RSP
            The C-MOVE-RSP message to be sent.
        """
        cs = msg.command_set

        identifier = 'None'
        if msg.data_set and msg.data_set.getvalue() != b'':
            identifier = 'Present'

        s = []
        s.append(
            '===================== OUTGOING DIMSE MESSAGE ===================='
        )
        s.append('Message Type                  : {0!s}'.format('C-MOVE RSP'))
        s.append('Message ID Being Responded To : {0!s}'
                 .format(cs.MessageIDBeingRespondedTo))
        if 'AffectedSOPClassUID' in cs:
            s.append('Affected SOP Class UID        : {0!s}'
                     .format(cs.AffectedSOPClassUID))
        else:
            s.append('Affected SOP Class UID        : none')
        s.append('Identifier                    : {0!s}'.format(identifier))
        s.append('Status                        : 0x{0:04x}'.format(cs.Status))

        s.append(
            '======================= END DIMSE MESSAGE ======================='
        )

        for line in s:
            LOGGER.debug(line)

    @staticmethod
    def debug_send_c_cancel_rq(msg):
        """Debugging function when a C-CANCEL-RQ is sent.

        Covers C-CANCEL-FIND-RQ, C-CANCEL-GET-RQ and C-CANCEL-MOVE-RQ.

        Parameters
        ----------
        msg : dimse_messages.C_CANCEL_RQ
            The C-CANCEL-RQ message to be sent.
        """
        pass

    @staticmethod
    def debug_receive_c_echo_rq(msg):
        """Debugging function when a C-ECHO-RQ is received.

        **C-ECHO Request Parameters**

        | (M) Message ID
        | (M) Affected SOP Class UID

        Parameters
        ----------
        msg : dimse_messagesC_ECHO_RQ
            The received C-ECHO-RQ message.
        """
        cs = msg.command_set

        LOGGER.info('Received Echo Request (MsgID %s)', cs.MessageID)

        s = []
        s.append(
            '===================== INCOMING DIMSE MESSAGE ===================='
        )
        s.append('Message Type                  : {0!s}'.format('C-ECHO RQ'))
        s.append('Presentation Context ID       : {0!s}'
                 .format(msg.context_id))
        s.append('Message ID                    : {0!s}'.format(cs.MessageID))
        s.append('Data Set                      : {0!s}'.format('none'))
        s.append(
            '======================= END DIMSE MESSAGE ======================='
        )

        for line in s:
            LOGGER.debug(line)

    @staticmethod
    def debug_receive_c_echo_rsp(msg):
        """Debugging function when a C-ECHO-RSP is received.

        **C-ECHO Response Parameters**

        | (U) Message ID
        | (M) Message ID Being Responded To
        | (U) Affected SOP Class UID
        | (M) Status

        Parameters
        ----------
        msg : dimse_messages.C_ECHO_RSP
            The received C-ECHO-RSP message.
        """
        cs = msg.command_set
        # Status is one of the following:
        #   0x0000 Success
        #   0x0122 Refused: SOP Class Not Supported
        #   0x0210 Refused: Duplicate Invocation
        #   0x0212 Refused: Mistyped Argument
        #   0x0211 Refused: Unrecognised Operation
        if cs.Status == 0x0000:
            status_str = 'Success'
        else:
            status_str = '0x{0:04x} - Unknown'.format(cs.Status)
        LOGGER.info("Received Echo Response (Status: %s)", status_str)

    @staticmethod
    def debug_receive_c_store_rq(msg):
        """Debugging function when a C-STORE-RQ is received.

        **C-STORE Request Elements**

        | (M) Message ID
        | (M) Affected SOP Class UID
        | (M) Affected SOP Instance UID
        | (M) Priority
        | (U) Move Originator Application Entity Title
        | (U) Move Originator Message ID
        | (M) Data Set

        Parameters
        ----------
        msg : dimse_messagesC_STORE_RQ
            The received C-STORE-RQ message.
        """
        cs = msg.command_set

        priority_str = {2: 'Low',
                        0: 'Medium',
                        1: 'High'}
        priority = priority_str[cs.Priority]

        dataset = 'None'
        if msg.data_set and msg.data_set.getvalue() != b'':
            dataset = 'Present'

        LOGGER.info('Received Store Request')

        s = []
        s.append(
            '===================== INCOMING DIMSE MESSAGE ===================='
        )
        s.append('Message Type                  : {0!s}'.format('C-STORE RQ'))
        s.append('Presentation Context ID       : {0!s}'
                 .format(msg.context_id))
        s.append('Message ID                    : {0!s}'.format(cs.MessageID))
        s.append('Affected SOP Class UID        : {0!s}'
                 .format(cs.AffectedSOPClassUID))
        s.append('Affected SOP Instance UID     : {0!s}'
                 .format(cs.AffectedSOPInstanceUID))
        if 'MoveOriginatorApplicationEntityTitle' in cs:
            s.append('Move Originator               : {0!s}'
                     .format(cs.MoveOriginatorApplicationEntityTitle))
        s.append('Data Set                      : {0!s}'.format(dataset))
        s.append('Priority                      : {0!s}'.format(priority))
        s.append(
            '======================= END DIMSE MESSAGE ======================='
        )
        for line in s:
            LOGGER.debug(line)

    @staticmethod
    def debug_receive_c_store_rsp(msg):
        """Debugging function when a C-STORE-RSP is received.

        **C-STORE Response Elements**

        | (U) Message ID
        | (M) Message ID Being Responded To
        | (U) Affected SOP Class UID
        | (U) Affected SOP Instance UID
        | (M) Status

        Parameters
        ----------
        msg : dimse_messagesC_STORE_RSP
            The received C-STORE-RSP message.
        """
        cs = msg.command_set

        dataset = 'None'
        if msg.data_set and msg.data_set.getvalue() != b'':
            dataset = 'Present'

        # See PS3.4 Annex B.2.3 for Storage Service Class Statuses
        status_str = '0x{0:04x} - Unknown'.format(cs.Status)
        # Try and get the status from the affected SOP class UID
        if 'AffectedSOPClassUID' in cs:
            service_class = uid_to_service_class(cs.AffectedSOPClassUID)
            try:
                if cs.Status in service_class.statuses:
                    status = service_class.statuses[cs.Status]
                    status_str = '0x{0:04x} - {1}'.format(cs.Status, status[0])
            except AttributeError:
                status_str = '0x{0:04x}'.format(cs.Status)

        LOGGER.info('Received Store Response')
        s = []
        s.append(
            '===================== INCOMING DIMSE MESSAGE ===================='
        )
        s.append('Message Type                  : {0!s}'.format('C-STORE RSP'))
        s.append('Presentation Context ID       : {0!s}'
                 .format(msg.context_id))
        s.append('Message ID Being Responded To : {0!s}'
                 .format(cs.MessageIDBeingRespondedTo))
        if 'AffectedSOPClassUID' in cs:
            s.append('Affected SOP Class UID        : {0!s}'
                     .format(cs.AffectedSOPClassUID))
        if 'AffectedSOPInstanceUID' in cs:
            s.append('Affected SOP Instance UID     : {0!s}'
                     .format(cs.AffectedSOPInstanceUID))
        s.append('Data Set                      : {0!s}'.format(dataset))
        s.append('DIMSE Status                  : {0!s}'.format(status_str))

        s.append(
            '======================= END DIMSE MESSAGE ======================='
        )

        for line in s:
            LOGGER.debug(line)

    @staticmethod
    def debug_receive_c_find_rq(msg):
        """Debugging function when a C-FIND-RQ is received.

        **C-FIND Request Parameters**

        | (M) Message ID
        | (M) Affected SOP Class UID
        | (M) Priority
        | (M) Identifier

        Parameters
        ----------
        msg : dimse_messagesC_FIND_RQ
            The received C-FIND-RQ message.
        """
        cs = msg.command_set

        priority_str = {2: 'Low',
                        0: 'Medium',
                        1: 'High'}
        priority = priority_str[cs.Priority]

        dataset = 'None'
        if msg.data_set and msg.data_set.getvalue() != b'':
            dataset = 'Present'

        s = []
        s.append(
            '===================== INCOMING DIMSE MESSAGE ===================='
        )
        s.append('Message Type                  : {0!s}'.format('C-FIND RQ'))
        s.append('Message ID                    : {0!s}'.format(cs.MessageID))
        s.append('Affected SOP Class UID        : {0!s}'
                 .format(cs.AffectedSOPClassUID))
        s.append('Data Set                      : {0!s}'.format(dataset))
        s.append('Priority                      : {0!s}'.format(priority))

        s.append(
            '======================= END DIMSE MESSAGE ======================='
        )

        for line in s:
            LOGGER.info(line)

    @staticmethod
    def debug_receive_c_find_rsp(msg):
        """Debugging function when a C-FIND-RSP is received.

        **C-FIND Response Parameters**

        | (U) Message ID
        | (M) Message ID Being Responded To
        | (U) Affected SOP Class UID
        | (C) Identifier
        | (M) Status

        Parameters
        ----------
        msg : dimse_messages.C_FIND_RSP
            The received C-FIND-RSP message.
        """
        cs = msg.command_set
        if cs.Status != 0x0000:
            return

        dataset = 'None'
        if msg.data_set and msg.data_set.getvalue() != b'':
            dataset = 'Present'

        s = []
        s.append(
            '===================== INCOMING DIMSE MESSAGE ===================='
        )
        s.append('Message Type                  : {0!s}'.format('C-FIND RSP'))
        s.append('Message ID Being Responded To : {0!s}'
                 .format(cs.MessageIDBeingRespondedTo))
        if 'AffectedSOPClassUID' in cs:
            s.append('Affected SOP Class UID        : {0!s}'
                     .format(cs.AffectedSOPClassUID))
        s.append('Data Set                      : {0!s}'.format(dataset))
        s.append('DIMSE Status                  : 0x{0:04x}'.format(cs.Status))

        s.append(
            '======================= END DIMSE MESSAGE ======================='
        )

        for line in s:
            LOGGER.info(line)

    @staticmethod
    def debug_receive_c_cancel_rq(msg):
        """Debugging function when a C-CANCEL-RQ is received.

        Covers C-CANCEL-FIND-RQ, C-CANCEL-GET-RQ and C-CANCEL-MOVE-RQ

        Parameters
        ----------
        msg : dimse_messagesC_CANCEL_RQ
            The received C-CANCEL-RQ message.
        """
        cs = msg.command_set

        s = []
        s.append(
            '===================== INCOMING DIMSE MESSAGE ===================='
        )
        s.append('Message Type                  : {0!s}'.format('C-CANCEL RQ'))
        s.append('Message ID Being Responded To : {0!s}'
                 .format(cs.MessageIDBeingRespondedTo))

        s.append(
            '======================= END DIMSE MESSAGE ======================='
        )

        for line in s:
            LOGGER.info(line)

    @staticmethod
    def debug_receive_c_get_rq(msg):
        """Debugging function when a C-GET-RQ is received.

        **C-GET Request Parameters**

        | (M) Message ID
        | (M) Affected SOP Class UID
        | (M) Priority
        | (M) Identifier

        Parameters
        ----------
        msg : dimse_messagesC_GET_RQ
            The received C-GET-RQ message.
        """
        cs = msg.command_set

        priority_str = {2: 'Low',
                        0: 'Medium',
                        1: 'High'}
        priority = priority_str[cs.Priority]

        dataset = 'None'
        if msg.data_set and msg.data_set.getvalue() != b'':
            dataset = 'Present'

        s = []
        s.append(
            '===================== INCOMING DIMSE MESSAGE ===================='
        )
        s.append('Message Type                  : {0!s}'.format('C-GET RQ'))
        s.append('Message ID                    : {0!s}'.format(cs.MessageID))
        s.append('Affected SOP Class UID        : {0!s}'
                 .format(cs.AffectedSOPClassUID))
        s.append('Data Set                      : {0!s}'.format(dataset))
        s.append('Priority                      : {0!s}'.format(priority))

        s.append(
            '======================= END DIMSE MESSAGE ======================='
        )

        for line in s:
            LOGGER.info(line)

    @staticmethod
    def debug_receive_c_get_rsp(msg):
        """Debugging function when a C-GET-RSP is received.

        **C-GET Response Parameters**

        | (U) Message ID
        | (M) Message ID Being Responded To
        | (U) Affected SOP Class UID
        | (U) Identifier
        | (M) Status
        | (C) Number of Remaining Sub-operations
        | (C) Number of Completed Sub-operations
        | (C) Number of Failed Sub-operations
        | (C) Number of Warning Sub-operations

        Parameters
        ----------
        msg : dimse_messagesC_GET_RSP
            The received C-GET-RSP message.
        """
        cs = msg.command_set

        dataset = 'None'
        if msg.data_set and msg.data_set.getvalue() != b'':
            dataset = 'Present'

        s = []
        s.append(
            '===================== INCOMING DIMSE MESSAGE ===================='
        )
        s.append('Message Type                  : {0!s}'.format('C-GET RSP'))
        s.append('Presentation Context ID       : {0!s}'
                 .format(msg.context_id))
        s.append('Message ID Being Responded To : {0!s}'
                 .format(cs.MessageIDBeingRespondedTo))
        if 'AffectedSOPClassUID' in cs:
            s.append('Affected SOP Class UID        : {0!s}'
                     .format(cs.AffectedSOPClassUID))
        if 'NumberOfRemainingSuboperations' in cs:
            s.append('Remaining Sub-operations      : {0!s}'
                     .format(cs.NumberOfRemainingSuboperations))
        if 'NumberOfCompletedSuboperations' in cs:
            s.append('Completed Sub-operations      : {0!s}'
                     .format(cs.NumberOfCompletedSuboperations))
        if 'NumberOfFailedSuboperations' in cs:
            s.append('Failed Sub-operations         : {0!s}'
                     .format(cs.NumberOfFailedSuboperations))
        if 'NumberOfWarningSuboperations' in cs:
            s.append('Warning Sub-operations        : {0!s}'
                     .format(cs.NumberOfWarningSuboperations))
        s.append('Data Set                      : {0!s}'.format(dataset))
        s.append('DIMSE Status                  : 0x{0:04x}'.format(cs.Status))

        s.append(
            '======================= END DIMSE MESSAGE ======================='
        )

        for line in s:
            LOGGER.debug(line)

    @staticmethod
    def debug_receive_c_move_rq(msg):
        """Debugging function when a C-MOVE-RQ is received.

        **C-MOVE Request Parameters**

        | (M) Message ID
        | (M) Affected SOP Class UID
        | (M) Priority
        | (M) Move Destination
        | (M) Identifier

        Parameters
        ----------
        msg : dimse_messagesC_MOVE_RQ
            The received C-MOVE-RQ message.
        """
        pass

    @staticmethod
    def debug_receive_c_move_rsp(msg):
        """Debugging function when a C-MOVE-RSP is received.

        **C-MOVE Response Parameters**

        | (U) Message ID
        | (M) Message ID Being Responded To
        | (U) Affected SOP Class UID
        | (U) Identifier
        | (M) Status
        | (C) Number of Remaining Sub-operations
        | (C) Number of Completed Sub-operations
        | (C) Number of Failed Sub-operations
        | (C) Number of Warning Sub-operations

        Parameters
        ----------
        msg : dimse_messagesC_MOVE_RSP
            The received C-MOVE-RSP message.
        """
        cs = msg.command_set

        identifier = 'None'
        if msg.data_set and msg.data_set.getvalue() != b'':
            identifier = 'Present'

        s = []
        s.append(
            '===================== INCOMING DIMSE MESSAGE ===================='
        )
        s.append('Message Type                  : {0!s}'.format('C-MOVE RSP'))
        s.append('Message ID Being Responded To : {0!s}'
                 .format(cs.MessageIDBeingRespondedTo))
        if 'AffectedSOPClassUID' in cs:
            s.append('Affected SOP Class UID        : {0!s}'
                     .format(cs.AffectedSOPClassUID))
        if 'NumberOfRemainingSuboperations' in cs:
            s.append('Remaining Sub-operations      : {0!s}'
                     .format(cs.NumberOfRemainingSuboperations))
        if 'NumberOfCompletedSuboperations' in cs:
            s.append('Completed Sub-operations      : {0!s}'
                     .format(cs.NumberOfCompletedSuboperations))
        if 'NumberOfFailedSuboperations' in cs:
            s.append('Failed Sub-operations         : {0!s}'
                     .format(cs.NumberOfFailedSuboperations))
        if 'NumberOfWarningSuboperations' in cs:
            s.append('Warning Sub-operations        : {0!s}'
                     .format(cs.NumberOfWarningSuboperations))
        s.append('Identifier                    : {0!s}'.format(identifier))
        s.append('DIMSE Status                  : 0x{0:04x}'.format(cs.Status))

        s.append(
            '======================= END DIMSE MESSAGE ======================='
        )

        for line in s:
            LOGGER.debug(line)

    @staticmethod
    def debug_send_n_event_report_rq(msg):
        """Debugging function when an N-EVENT-REPORT-RQ is sent.

        Parameters
        ----------
        msg : dimse_messages.N_EVENT_REPORT_RQ
            The N-EVENT-REPORT-RQ message to be sent.
        """
        cs = msg.command_set

        evt_info = 'None'
        if msg.data_set and msg.data_set.getvalue() != b'':
            evt_info = 'Present'

        s = []
        s.append(
            '===================== OUTGOING DIMSE MESSAGE ===================='
        )
        s.append('Message Type                  : {0!s}'
                 .format('N-EVENT-REPORT RQ'))
        s.append('Message ID                    : {0!s}'.format(cs.MessageID))
        s.append('Affected SOP Class UID        : {0!s}'
                 .format(cs.AffectedSOPClassUID))
        s.append('Affected SOP Instance UID     : {0!s}'
                 .format(cs.AffectedSOPInstanceUID))
        s.append('Event Type ID                 : {0!s}'
                 .format(cs.EventTypeID))
        s.append('Event Information             : {0!s}'.format(evt_info))
        s.append(
            '======================= END DIMSE MESSAGE ======================='
        )
        for line in s:
            LOGGER.debug(line)

    @staticmethod
    def debug_send_n_event_report_rsp(msg):
        """Debugging function when an N-EVENT-REPORT-RSP is sent.

        Parameters
        ----------
        msg : dimse_messages.N_EVENT_REPORT_RSP
            The N-EVENT-REPORT-RSP message to be sent.
        """
        cs = msg.command_set

        evt_reply = 'None'
        if msg.data_set and msg.data_set.getvalue() != b'':
            evt_reply = 'Present'

        s = []
        s.append(
            '===================== OUTGOING DIMSE MESSAGE ===================='
        )
        s.append('Message Type                  : {0!s}'
                 .format('N-EVENT-REPORT RSP'))
        s.append('Message ID Being Responded To : {0!s}'
                 .format(cs.MessageIDBeingRespondedTo))
        if 'AffectedSOPClassUID' in cs:
            s.append('Affected SOP Class UID        : {0!s}'
                     .format(cs.AffectedSOPClassUID))
        if 'AffectedSOPInstanceUID' in cs:
            s.append('Affected SOP Instance UID     : {0!s}'
                     .format(cs.AffectedSOPInstanceUID))
        if 'EventTypeID' in cs:
            s.append(
                'Event Type ID                 : {!s}'
                .format(cs.EventTypeID)
            )
        s.append('Event Reply                       : {0!s}'.format(evt_reply))
        s.append('Status                        : 0x{0:04x}'.format(cs.Status))
        s.append(
            '======================= END DIMSE MESSAGE ======================='
        )
        for line in s:
            LOGGER.debug(line)

    @staticmethod
    def debug_send_n_get_rq(msg):
        """Debugging function when an N-GET-RQ is sent.

        Parameters
        ----------
        msg : dimse_messages.N_GET_RQ
            The N-GET-RQ message to be sent.
        """
        cs = msg.command_set

        nr_attr = 'no identifiers'
        if 'AttributeIdentifierList' in cs:
            nr_attr = len(cs.AttributeIdentifierList)
            if nr_attr == 1:
                nr_attr = '{} identifier'.format(nr_attr)
            else:
                nr_attr = '{} identifiers'.format(nr_attr)

        s = []
        s.append(
            '===================== OUTGOING DIMSE MESSAGE ===================='
        )
        s.append('Message Type                  : {0!s}'.format('N-GET RQ'))
        s.append('Message ID                    : {0!s}'.format(cs.MessageID))
        s.append('Requested SOP Class UID       : {0!s}'
                 .format(cs.RequestedSOPClassUID))
        s.append('Requested SOP Instance UID    : {0!s}'
                 .format(cs.RequestedSOPInstanceUID))
        s.append('Attribute Identifier List     : ({0!s})'.format(nr_attr))
        s.append(
            '======================= END DIMSE MESSAGE ======================='
        )
        for line in s:
            LOGGER.debug(line)

    @staticmethod
    def debug_send_n_get_rsp(msg):
        """Debugging function when an N-GET-RSP is sent.

        Parameters
        ----------
        msg : dimse_messages.N_GET_RSP
            The N-GET-RSP message to be sent.
        """
        cs = msg.command_set

        attr_list = 'None'
        if msg.data_set and msg.data_set.getvalue() != b'':
            attr_list = 'Present'

        s = []
        s.append(
            '===================== OUTGOING DIMSE MESSAGE ===================='
        )
        s.append('Message Type                  : {0!s}'.format('N-GET RSP'))
        s.append('Message ID Being Responded To : {0!s}'
                 .format(cs.MessageIDBeingRespondedTo))
        if 'AffectedSOPClassUID' in cs:
            s.append('Affected SOP Class UID        : {0!s}'
                     .format(cs.AffectedSOPClassUID))
        if 'AffectedSOPInstanceUID' in cs:
            s.append('Affected SOP Instance UID     : {0!s}'
                     .format(cs.AffectedSOPInstanceUID))
        s.append('Attribute List                : {0!s}'.format(attr_list))
        s.append('Status                        : 0x{0:04x}'.format(cs.Status))
        s.append(
            '======================= END DIMSE MESSAGE ======================='
        )
        for line in s:
            LOGGER.debug(line)

    @staticmethod
    def debug_send_n_set_rq(msg):
        """Debugging function when an N-SET-RQ is sent.

        Parameters
        ----------
        msg : dimse_messages.N_SET_RQ
            The N-SET-RQ message to be sent.
        """
        cs = msg.command_set

        mod_list = 'None'
        if msg.data_set and msg.data_set.getvalue() != b'':
            mod_list = 'Present'

        s = []
        s.append(
            '===================== OUTGOING DIMSE MESSAGE ===================='
        )
        s.append('Message Type                  : {0!s}'.format('N-SET RQ'))
        s.append('Message ID                    : {0!s}'.format(cs.MessageID))
        s.append('Requested SOP Class UID       : {0!s}'
                 .format(cs.RequestedSOPClassUID))
        s.append('Requested SOP Instance UID    : {0!s}'
                 .format(cs.RequestedSOPInstanceUID))
        s.append('Modification List             : {0!s}'.format(mod_list))
        s.append(
            '======================= END DIMSE MESSAGE ======================='
        )
        for line in s:
            LOGGER.debug(line)

    @staticmethod
    def debug_send_n_set_rsp(msg):
        """Debugging function when an N-SET-RSP is sent.

        Parameters
        ----------
        msg : dimse_messages.N_SET_RSP
            The N-SET-RSP message to be sent.
        """
        cs = msg.command_set

        attr_list = 'None'
        if msg.data_set and msg.data_set.getvalue() != b'':
            attr_list = 'Present'

        s = []
        s.append(
            '===================== OUTGOING DIMSE MESSAGE ===================='
        )
        s.append('Message Type                  : {0!s}'.format('N-SET RSP'))
        s.append('Message ID Being Responded To : {0!s}'
                 .format(cs.MessageIDBeingRespondedTo))
        if 'AffectedSOPClassUID' in cs:
            s.append('Affected SOP Class UID        : {0!s}'
                     .format(cs.AffectedSOPClassUID))
        if 'AffectedSOPInstanceUID' in cs:
            s.append('Affected SOP Instance UID     : {0!s}'
                     .format(cs.AffectedSOPInstanceUID))
        s.append('Attribute List                : {0!s}'.format(attr_list))
        s.append('Status                        : 0x{0:04x}'.format(cs.Status))
        s.append(
            '======================= END DIMSE MESSAGE ======================='
        )
        for line in s:
            LOGGER.debug(line)

    @staticmethod
    def debug_send_n_action_rq(msg):
        """Debugging function when an N-ACTION-RQ is sent.

        Parameters
        ----------
        msg : dimse_messages.N_ACTION_RQ
            The N-ACTION-RQ message to be sent.
        """
        pass

    @staticmethod
    def debug_send_n_action_rsp(msg):
        """Debugging function when an N-ACTION-RSP is sent.

        Parameters
        ----------
        msg : dimse_messages.N_ACTION_RSP
            The N-ACTION-RSP message to be sent.
        """
        pass

    @staticmethod
    def debug_send_n_create_rq(msg):
        """Debugging function when an N-CREATE-RQ is sent.

        Parameters
        ----------
        msg : dimse_messages.N_CREATE_RQ
            The N-CREATE-RQ message to be sent.
        """
        pass

    @staticmethod
    def debug_send_n_create_rsp(msg):
        """Debugging function when an N-CREATE-RSP is sent.

        Parameters
        ----------
        msg : dimse_messages.N_CREATE_RSP
            The N-CREATE-RSP message to be sent.
        """
        pass

    @staticmethod
    def debug_send_n_delete_rq(msg):
        """Debugging function when an N-DELETE-RQ is sent.

        Parameters
        ----------
        msg : dimse_messages.N_DELETE_RQ
            The N-DELETE-RQ message to be sent.
        """
        cs = msg.command_set

        s = []
        s.append(
            '===================== OUTGOING DIMSE MESSAGE ===================='
        )
        s.append('Message Type                  : {0!s}'.format('N-DELETE RQ'))
        s.append('Message ID                    : {0!s}'.format(cs.MessageID))
        s.append('Requested SOP Class UID       : {0!s}'
                 .format(cs.RequestedSOPClassUID))
        s.append('Requested SOP Instance UID    : {0!s}'
                 .format(cs.RequestedSOPInstanceUID))
        s.append(
            '======================= END DIMSE MESSAGE ======================='
        )
        for line in s:
            LOGGER.debug(line)

    @staticmethod
    def debug_send_n_delete_rsp(msg):
        """Debugging function when an N-DELETE-RSP is sent.

        Parameters
        ----------
        msg : dimse_messages.N_DELETE_RSP
            The N-DELETE-RSP message to be sent.
        """
        cs = msg.command_set

        s = []
        s.append(
            '===================== OUTGOING DIMSE MESSAGE ===================='
        )
        s.append('Message Type                  : {0!s}'.format('N-DELETE RQ'))
        s.append('Message ID Being Responded To : {0!s}'
                 .format(cs.MessageIDBeingRespondedTo))
        if 'AffectedSOPClassUID' in cs:
            s.append('Affected SOP Class UID        : {0!s}'
                     .format(cs.AffectedSOPClassUID))
        if 'AffectedSOPInstanceUID' in cs:
            s.append('Affected SOP Instance UID     : {0!s}'
                     .format(cs.AffectedSOPInstanceUID))
        s.append('Status                        : 0x{0:04x}'.format(cs.Status))
        s.append(
            '======================= END DIMSE MESSAGE ======================='
        )
        for line in s:
            LOGGER.debug(line)

    @staticmethod
    def debug_receive_n_event_report_rq(msg):
        """Debugging function when an N-EVENT-REPORT-RQ is received.

        Parameters
        ----------
        msg : dimse_messages.N_EVENT_REPORT_RQ
            The received N-EVENT-REPORT-RQ message.
        """
        pass

    @staticmethod
    def debug_receive_n_event_report_rsp(msg):
        """Debugging function when an N-EVENT-REPORT-RSP is received.

        Parameters
        ----------
        msg : dimse_messages.N_EVENT_REPORT_RSP
            The received N-EVENT-REPORT-RSP message.
        """
        pass

    @staticmethod
    def debug_receive_n_get_rq(msg):
        """Debugging function when an N-GET-RQ is received.

        Parameters
        ----------
        msg : dimse_messages.N_GET_RQ
            The received N-GET-RQ message.
        """
        pass

    @staticmethod
    def debug_receive_n_get_rsp(msg):
        """Debugging function when an N-GET-RSP is received.

        Parameters
        ----------
        msg : dimse_messages.N_GET_RSP
            The received N-GET-RSP message.
        """
        cs = msg.command_set

        dataset = 'None'
        if msg.data_set and msg.data_set.getvalue() != b'':
            dataset = 'Present'

        LOGGER.info('Received Get Response')
        s = []
        s.append(
            '===================== INCOMING DIMSE MESSAGE ===================='
        )
        s.append('Message Type                  : {0!s}'.format('N-GET RSP'))
        s.append('Presentation Context ID       : {0!s}'
                 .format(msg.context_id))
        s.append('Message ID Being Responded To : {0!s}'
                 .format(cs.MessageIDBeingRespondedTo))
        if 'AffectedSOPClassUID' in cs:
            s.append('Affected SOP Class UID        : {0!s}'
                     .format(cs.AffectedSOPClassUID))
        if 'AffectedSOPInstanceUID' in cs:
            s.append('Affected SOP Instance UID     : {0!s}'
                     .format(cs.AffectedSOPInstanceUID))
        s.append('Attribute List                : {0!s}'.format(dataset))
        s.append('Status                        : 0x{0:04x}'.format(cs.Status))
        s.append(
            '======================= END DIMSE MESSAGE ======================='
        )

        for line in s:
            LOGGER.debug(line)

    @staticmethod
    def debug_receive_n_set_rq(msg):
        """Debugging function when an N-SET-RQ is received.

        Parameters
        ----------
        msg : dimse_messages.N_SET_RQ
            The received N-SET-RQ message.
        """
        pass

    @staticmethod
    def debug_receive_n_set_rsp(msg):
        """Debugging function when an N-SET-RSP is received.

        Parameters
        ----------
        msg : dimse_messages.N_SET_RSP
            The received N-SET-RSP message.
        """
        pass

    @staticmethod
    def debug_receive_n_action_rq(msg):
        """Debugging function when an N-ACTION-RQ is received.

        Parameters
        ----------
        msg : dimse_messages.N_ACTION_RQ
            The received N-ACTION-RQ message.
        """
        pass

    @staticmethod
    def debug_receive_n_action_rsp(msg):
        """Debugging function when an N-ACTION-RSP is received.

        Parameters
        ----------
        msg : dimse_messages.N_ACTION_RSP
            The received N-ACTION-RSP message.
        """
        pass

    @staticmethod
    def debug_receive_n_create_rq(msg):
        """Debugging function when an N-CREATE-RQ is received.

        Parameters
        ----------
        msg : dimse_messages.N_CREATE_RQ
            The received N-CREATE-RQ message.
        """
        pass

    @staticmethod
    def debug_receive_n_create_rsp(msg):
        """Debugging function when an N-CREATE-RSP is received.

        Parameters
        ----------
        msg : dimse_messages.N_CREATE_RSP
            The received N-CREATE-RSP message.
        """
        pass

    @staticmethod
    def debug_receive_n_delete_rq(msg):
        """Debugging function when an N-DELETE-RQ is received.

        Parameters
        ----------
        msg : dimse_messages.N_DELETE_RQ
            The received N-DELETE-RQ message.
        """
        pass

    @staticmethod
    def debug_receive_n_delete_rsp(msg):
        """Debugging function when an N-DELETE-RSP is received.

        Parameters
        ----------
        msg : dimse_messages.N_DELETE_RSP
            The received N-DELETE-RSP message.
        """
        pass
