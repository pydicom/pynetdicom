"""Default logging handlers."""

import logging

from pynetdicom.dimse_messages import *


LOGGER = logging.getLogger('pynetdicom.events')


# DIMSE
def send_message_handler(event):
    """Standard logging handler for when a DIMSE message is sent.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_SENT event that occurred.
    """
    msg_handlers = {
        C_ECHO_RQ: send_c_echo_rq,
        C_ECHO_RSP: send_c_echo_rsp,
        C_FIND_RQ: send_c_find_rq,
        C_FIND_RSP: send_c_find_rsp,
        C_GET_RQ: send_c_get_rq,
        C_GET_RSP: send_c_get_rsp,
        C_MOVE_RQ: send_c_move_rq,
        C_MOVE_RSP: send_c_move_rsp,
        C_STORE_RQ: send_c_store_rq,
        C_STORE_RSP: send_c_store_rsp,
        C_CANCEL_RQ: send_c_cancel_rq,
        N_EVENT_REPORT_RQ: send_n_event_report_rq,
        N_EVENT_REPORT_RSP: send_n_event_report_rsp,
        N_SET_RQ: send_n_set_rq,
        N_SET_RSP: send_n_set_rsp,
        N_GET_RQ: send_n_get_rq,
        N_GET_RSP: send_n_get_rsp,
        N_ACTION_RQ: send_n_action_rq,
        N_ACTION_RSP: send_n_action_rsp,
        N_CREATE_RQ: send_n_create_rq,
        N_CREATE_RSP: send_n_create_rsp,
        N_DELETE_RQ: send_n_delete_rq,
        N_DELETE_RSP: send_n_delete_rsp
    }

    msg_handlers[type(event.message)](event)

def recv_message_handler(event):
    """Standard logging handler for when a DIMSE message is received.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_RECV event that occurred.
    """
    msg_handlers = {
        C_ECHO_RQ: recv_c_echo_rq,
        C_ECHO_RSP: recv_c_echo_rsp,
        C_FIND_RQ: recv_c_find_rq,
        C_FIND_RSP: recv_c_find_rsp,
        C_CANCEL_RQ: recv_c_cancel_rq,
        C_GET_RQ: recv_c_get_rq,
        C_GET_RSP: recv_c_get_rsp,
        C_MOVE_RQ: recv_c_move_rq,
        C_MOVE_RSP: recv_c_move_rsp,
        C_STORE_RQ: recv_c_store_rq,
        C_STORE_RSP: recv_c_store_rsp,
        N_EVENT_REPORT_RQ: recv_n_event_report_rq,
        N_EVENT_REPORT_RSP: recv_n_event_report_rsp,
        N_SET_RQ: recv_n_set_rq,
        N_SET_RSP: recv_n_set_rsp,
        N_GET_RQ: recv_n_get_rq,
        N_GET_RSP: recv_n_get_rsp,
        N_ACTION_RQ: recv_n_action_rq,
        N_ACTION_RSP: recv_n_action_rsp,
        N_CREATE_RQ: recv_n_create_rq,
        N_CREATE_RSP: recv_n_create_rsp,
        N_DELETE_RQ: recv_n_delete_rq,
        N_DELETE_RSP: recv_n_delete_rsp
    }

    msg_handlers[type(event.message)](event)

# DIMSE message sub-handlers
def send_c_echo_rq(event):
    """Logging handler for when a C-ECHO-RQ is sent.

    **C-ECHO Request Parameters**

    | (M) Message ID
    | (M) Affected SOP Class UID

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_SENT event that occurred.
    """
    msg = event.message
    cs = msg.command_set
    LOGGER.info("Sending Echo Request: MsgID %s", cs.MessageID)

def send_c_echo_rsp(event):
    """Logging handler for when a C-ECHO-RSP is sent.

    **C-ECHO Response Parameters**

    | (U) Message ID
    | (M) Message ID Being Responded To
    | (U) Affected SOP Class UID
    | (M) Status

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_SENT event that occurred.
    """
    pass

def send_c_store_rq(event):
    """Logging handler when a C-STORE-RQ is sent.

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
    event : event.Event
        The evt.EVT_MESSAGE_SENT event that occurred.
    """
    msg = event.message
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

def send_c_store_rsp(event):
    """Logging handler when a C-STORE-RSP is sent.

    **C-STORE Response Elements**

    | (U) Message ID
    | (M) Message ID Being Responded To
    | (U) Affected SOP Class UID
    | (U) Affected SOP Instance UID
    | (M) Status

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_SENT event that occurred.
    """
    pass

def send_c_find_rq(event):
    """Logging handler when a C-FIND-RQ is sent.

    **C-FIND Request Parameters**

    | (M) Message ID
    | (M) Affected SOP Class UID
    | (M) Priority
    | (M) Identifier

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_SENT event that occurred.
    """
    msg = event.message
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

def send_c_find_rsp(event):
    """Logging handler when a C-FIND-RSP is sent.

    **C-FIND Response Parameters**

    | (U) Message ID
    | (M) Message ID Being Responded To
    | (U) Affected SOP Class UID
    | (C) Identifier
    | (M) Status

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_SENT event that occurred.
    """
    msg = event.message
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

def send_c_get_rq(event):
    """Logging handler when a C-GET-RQ is sent.

    **C-GET Request Parameters**

    | (M) Message ID
    | (M) Affected SOP Class UID
    | (M) Priority
    | (M) Identifier

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_SENT event that occurred.
    """
    msg = event.message
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

def send_c_get_rsp(event):
    """Logging handler when a C-GET-RSP is sent.

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
    event : event.Event
        The evt.EVT_MESSAGE_SENT event that occurred.
    """
    msg = event.message
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

def send_c_move_rq(event):
    """Logging handler when a C-MOVE-RQ is sent.

    **C-MOVE Request Parameters**

    | (M) Message ID
    | (M) Affected SOP Class UID
    | (M) Priority
    | (M) Move Destination
    | (M) Identifier

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_SENT event that occurred.
    """
    msg = event.message
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

def send_c_move_rsp(event):
    """Logging handler when a C-MOVE-RSP is sent.

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
    event : event.Event
        The evt.EVT_MESSAGE_SENT event that occurred.
    """
    msg = event.message
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

def send_c_cancel_rq(event):
    """Logging handler when a C-CANCEL-RQ is sent.

    Covers C-CANCEL-FIND-RQ, C-CANCEL-GET-RQ and C-CANCEL-MOVE-RQ.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_SENT event that occurred.
    """
    pass

def recv_c_echo_rq(event):
    """Logging handler when a C-ECHO-RQ is received.

    **C-ECHO Request Parameters**

    | (M) Message ID
    | (M) Affected SOP Class UID

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_RECV event that occurred.
    """
    msg = event.message
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

def recv_c_echo_rsp(event):
    """Logging handler when a C-ECHO-RSP is received.

    **C-ECHO Response Parameters**

    | (U) Message ID
    | (M) Message ID Being Responded To
    | (U) Affected SOP Class UID
    | (M) Status

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_RECV event that occurred.
    """
    msg = event.message
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

def recv_c_store_rq(event):
    """Logging handler when a C-STORE-RQ is received.

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
    event : event.Event
        The evt.EVT_MESSAGE_RECV event that occurred.
    """
    msg = event.message
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

def recv_c_store_rsp(event):
    """Logging handler when a C-STORE-RSP is received.

    **C-STORE Response Elements**

    | (U) Message ID
    | (M) Message ID Being Responded To
    | (U) Affected SOP Class UID
    | (U) Affected SOP Instance UID
    | (M) Status

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_RECV event that occurred.
    """
    msg = event.message
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

def recv_c_find_rq(event):
    """Logging handler when a C-FIND-RQ is received.

    **C-FIND Request Parameters**

    | (M) Message ID
    | (M) Affected SOP Class UID
    | (M) Priority
    | (M) Identifier

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_RECV event that occurred.
    """
    msg = event.message
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

def recv_c_find_rsp(event):
    """Logging handler when a C-FIND-RSP is received.

    **C-FIND Response Parameters**

    | (U) Message ID
    | (M) Message ID Being Responded To
    | (U) Affected SOP Class UID
    | (C) Identifier
    | (M) Status

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_RECV event that occurred.
    """
    msg = event.message
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

def recv_c_cancel_rq(event):
    """Logging handler when a C-CANCEL-RQ is received.

    Covers C-CANCEL-FIND-RQ, C-CANCEL-GET-RQ and C-CANCEL-MOVE-RQ

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_RECV event that occurred.
    """
    msg = event.message
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

def recv_c_get_rq(event):
    """Logging handler when a C-GET-RQ is received.

    **C-GET Request Parameters**

    | (M) Message ID
    | (M) Affected SOP Class UID
    | (M) Priority
    | (M) Identifier

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_RECV event that occurred.
    """
    msg = event.message
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

def recv_c_get_rsp(event):
    """Logging handler when a C-GET-RSP is received.

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
    event : event.Event
        The evt.EVT_MESSAGE_RECV event that occurred.
    """
    msg = event.message
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

def recv_c_move_rq(event):
    """Logging handler when a C-MOVE-RQ is received.

    **C-MOVE Request Parameters**

    | (M) Message ID
    | (M) Affected SOP Class UID
    | (M) Priority
    | (M) Move Destination
    | (M) Identifier

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_RECV event that occurred.
    """
    pass

def recv_c_move_rsp(event):
    """Logging handler when a C-MOVE-RSP is received.

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
    event : event.Event
        The evt.EVT_MESSAGE_RECV event that occurred.
    """
    msg = event.message
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

def send_n_event_report_rq(event):
    """Logging handler when an N-EVENT-REPORT-RQ is sent.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_SENT event that occurred.
    """
    msg = event.message
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

def send_n_event_report_rsp(event):
    """Logging handler when an N-EVENT-REPORT-RSP is sent.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_SENT event that occurred.
    """
    msg = event.message
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

def send_n_get_rq(event):
    """Logging handler when an N-GET-RQ is sent.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_SENT event that occurred.
    """
    msg = event.message
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

def send_n_get_rsp(event):
    """Logging handler when an N-GET-RSP is sent.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_SENT event that occurred.
    """
    msg = event.message
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

def send_n_set_rq(event):
    """Logging handler when an N-SET-RQ is sent.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_SENT event that occurred.
    """
    msg = event.message
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

def send_n_set_rsp(event):
    """Logging handler when an N-SET-RSP is sent.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_SENT event that occurred.
    """
    msg = event.message
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

def send_n_action_rq(event):
    """Logging handler when an N-ACTION-RQ is sent.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_SENT event that occurred.
    """
    pass

def send_n_action_rsp(event):
    """Logging handler when an N-ACTION-RSP is sent.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_SENT event that occurred.
    """
    pass

def send_n_create_rq(event):
    """Logging handler when an N-CREATE-RQ is sent.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_SENT event that occurred.
    """
    pass

def send_n_create_rsp(event):
    """Logging handler when an N-CREATE-RSP is sent.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_SENT event that occurred.
    """
    pass

def send_n_delete_rq(event):
    """Logging handler when an N-DELETE-RQ is sent.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_SENT event that occurred.
    """
    msg = event.message
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

def send_n_delete_rsp(event):
    """Logging handler when an N-DELETE-RSP is sent.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_SENT event that occurred.
    """
    msg = event.message
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

def recv_n_event_report_rq(event):
    """Logging handler when an N-EVENT-REPORT-RQ is received.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_RECV event that occurred.
    """
    pass

def recv_n_event_report_rsp(event):
    """Logging handler when an N-EVENT-REPORT-RSP is received.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_RECV event that occurred.
    """
    pass

def recv_n_get_rq(event):
    """Logging handler when an N-GET-RQ is received.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_RECV event that occurred.
    """
    pass

def recv_n_get_rsp(event):
    """Logging handler when an N-GET-RSP is received.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_RECV event that occurred.
    """
    msg = event.message
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

def recv_n_set_rq(event):
    """Logging handler when an N-SET-RQ is received.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_RECV event that occurred.
    """
    pass

def recv_n_set_rsp(event):
    """Logging handler when an N-SET-RSP is received.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_RECV event that occurred.
    """
    pass

def recv_n_action_rq(event):
    """Logging handler when an N-ACTION-RQ is received.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_RECV event that occurred.
    """
    pass

def recv_n_action_rsp(event):
    """Logging handler when an N-ACTION-RSP is received.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_RECV event that occurred.
    """
    pass

def recv_n_create_rq(event):
    """Logging handler when an N-CREATE-RQ is received.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_RECV event that occurred.
    """
    pass

def recv_n_create_rsp(event):
    """Logging handler when an N-CREATE-RSP is received.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_RECV event that occurred.
    """
    pass

def recv_n_delete_rq(event):
    """Logging handler when an N-DELETE-RQ is received.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_RECV event that occurred.
    """
    pass

def recv_n_delete_rsp(event):
    """Logging handler when an N-DELETE-RSP is received.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_MESSAGE_RECV event that occurred.
    """
    pass
