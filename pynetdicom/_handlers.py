"""Default logging handlers."""

import logging

from pynetdicom.dimse_messages import *
from pynetdicom.pdu_primitives import (
    A_ASSOCIATE, A_RELEASE, A_ABORT, A_P_ABORT,
    SOPClassExtendedNegotiation,
    SOPClassCommonExtendedNegotiation,
    SCP_SCU_RoleSelectionNegotiation,
    AsynchronousOperationsWindowNegotiation,
    UserIdentityNegotiation,
    ImplementationVersionNameNotification
)
from pynetdicom.sop_class import uid_to_service_class


LOGGER = logging.getLogger('pynetdicom.events')


# Standard logging handlers
def standard_acse_recv_handler(event):
    """Standard handler for the ACSE receiving a primitive from the DUL.

    Parameters
    ----------
    event : event.Event
        The ``evt.EVT_ACSE_RECV`` event corresponding to the ACSE receiving
        a primitive from the DUL service provider. Event attributes are:

        * ``assoc`` : the
          :py:class:`association <pynetdicom.association.Association>`
          that the ACSE is providing services for.
        * ``message`` : the ACSE primitive that was received, either
        ``A_ASSOCIATE``, ``A_RELEASE``, ``A_ABORT`` or ``A_P_ABORT``.
        * ``timestamp`` : the
          `date and time <https://docs.python.org/3/library/datetime.html#datetime-objects>`_
          that the primitive was received.
    """
    primitive = event.message
    handlers = {
        A_ASSOCIATE : _recv_a_associate,
        A_RELEASE : _recv_a_release,
        A_ABORT : _recv_a_abort,
        A_P_ABORT : _recv_ap_abort,
    }

    handlers[type(primitive)](event)

def standard_acse_sent_handler(event):
    """Standard handler for the ACSE sending a primitive to the DUL.

    Parameters
    ----------
    event : event.Event
        The ``evt.EVT_ACSE_SENT`` event corresponding to the ACSE receiving
        a primitive from the DUL service provider. Event attributes are:

        * ``assoc`` : the
          :py:class:`association <pynetdicom.association.Association>`
          that the ACSE is providing services for.
        * ``message`` : the ACSE primitive that was sent, either
        ``A_ASSOCIATE``, ``A_RELEASE``, ``A_ABORT`` or ``A_P_ABORT``.
        * ``timestamp`` : the
          `date and time <https://docs.python.org/3/library/datetime.html#datetime-objects>`_
          that the primitive was sent.
    """
    primitive = event.message
    handlers = {
        A_ASSOCIATE : _send_a_associate,
        A_RELEASE : _send_a_release,
        A_ABORT : _send_a_abort,
        A_P_ABORT : _send_ap_abort,
    }
    handlers[type(primitive)](event)

def standard_dimse_recv_handler(event):
    """Standard handler for the ACSE receiving a primitive from the DUL.

    Parameters
    ----------
    event : event.Event
        The ``evt.EVT_DIMSE_RECV`` event corresponding to the DIMSE decoding
        a message received from the peer. Event attributes are:

        * ``assoc`` : the
          :py:class:`association <pynetdicom.association.Association>`
          that the DIMSE is providing services for.
        * ``message`` : the DIMSE message that was received.
        * ``timestamp`` : the
          `date and time <https://docs.python.org/3/library/datetime.html#datetime-objects>`_
          that the message was decoded.
    """
    handlers = {
        C_ECHO_RQ: _recv_c_echo_rq,
        C_ECHO_RSP: _recv_c_echo_rsp,
        C_FIND_RQ: _recv_c_find_rq,
        C_FIND_RSP: _recv_c_find_rsp,
        C_CANCEL_RQ: _recv_c_cancel_rq,
        C_GET_RQ: _recv_c_get_rq,
        C_GET_RSP: _recv_c_get_rsp,
        C_MOVE_RQ: _recv_c_move_rq,
        C_MOVE_RSP: _recv_c_move_rsp,
        C_STORE_RQ: _recv_c_store_rq,
        C_STORE_RSP: _recv_c_store_rsp,
        N_EVENT_REPORT_RQ: _recv_n_event_report_rq,
        N_EVENT_REPORT_RSP: _recv_n_event_report_rsp,
        N_SET_RQ: _recv_n_set_rq,
        N_SET_RSP: _recv_n_set_rsp,
        N_GET_RQ: _recv_n_get_rq,
        N_GET_RSP: _recv_n_get_rsp,
        N_ACTION_RQ: _recv_n_action_rq,
        N_ACTION_RSP: _recv_n_action_rsp,
        N_CREATE_RQ: _recv_n_create_rq,
        N_CREATE_RSP: _recv_n_create_rsp,
        N_DELETE_RQ: _recv_n_delete_rq,
        N_DELETE_RSP: _recv_n_delete_rsp
    }

    handlers[type(event.message)](event)

def standard_dimse_send_handler(event):
    """Standard handler for the ACSE receiving a primitive from the DUL.

    Parameters
    ----------
    event : event.Event
        The ``evt.EVT_DIMSE_SENT`` event corresponding to the DIMSE encoding
        a message to be sent to the peer. Event attributes are:

        * ``assoc`` : the
          :py:class:`association <pynetdicom.association.Association>`
          that the DIMSE is providing services for.
        * ``message`` : the DIMSE message to be sent.
        * ``timestamp`` : the
          `date and time <https://docs.python.org/3/library/datetime.html#datetime-objects>`_
          that the message was decoded.
    """
    handlers = {
        C_ECHO_RQ: _send_c_echo_rq,
        C_ECHO_RSP: _send_c_echo_rsp,
        C_FIND_RQ: _send_c_find_rq,
        C_FIND_RSP: _send_c_find_rsp,
        C_GET_RQ: _send_c_get_rq,
        C_GET_RSP: _send_c_get_rsp,
        C_MOVE_RQ: _send_c_move_rq,
        C_MOVE_RSP: _send_c_move_rsp,
        C_STORE_RQ: _send_c_store_rq,
        C_STORE_RSP: _send_c_store_rsp,
        C_CANCEL_RQ: _send_c_cancel_rq,
        N_EVENT_REPORT_RQ: _send_n_event_report_rq,
        N_EVENT_REPORT_RSP: _send_n_event_report_rsp,
        N_SET_RQ: _send_n_set_rq,
        N_SET_RSP: _send_n_set_rsp,
        N_GET_RQ: _send_n_get_rq,
        N_GET_RSP: _send_n_get_rsp,
        N_ACTION_RQ: _send_n_action_rq,
        N_ACTION_RSP: _send_n_action_rsp,
        N_CREATE_RQ: _send_n_create_rq,
        N_CREATE_RSP: _send_n_create_rsp,
        N_DELETE_RQ: _send_n_delete_rq,
        N_DELETE_RSP: _send_n_delete_rsp
    }

    handlers[type(event.message)](event)

def logging_aborted_handler(event):
    LOGGER.error('Association Aborted')

def logging_accepted_handler(event):
    pass

def logging_rejected_handler(event):
    primitive = event.message
    source = primitive.result_source
    result = primitive.result
    reason = primitive.diagnostic

    source_str = {1 : 'Service User',
                  2 : 'Service Provider (ACSE)',
                  3 : 'Service Provider (Presentation)'}

    reason_str = [{1 : 'No reason given',
                   2 : 'Application context name not supported',
                   3 : 'Calling AE title not recognised',
                   4 : 'Reserved',
                   5 : 'Reserved',
                   6 : 'Reserved',
                   7 : 'Called AE title not recognised',
                   8 : 'Reserved',
                   9 : 'Reserved',
                   10 : 'Reserved'},
                  {1 : 'No reason given',
                   2 : 'Protocol version not supported'},
                  {0 : 'Reserved',
                   1 : 'Temporary congestion',
                   2 : 'Local limit exceeded',
                   3 : 'Reserved',
                   4 : 'Reserved',
                   5 : 'Reserved',
                   6 : 'Reserved',
                   7 : 'Reserved'}]

    result_str = {1 : 'Rejected Permanent',
                  2 : 'Rejected Transient'}

    LOGGER.error('Association Rejected:')
    LOGGER.error('Result: %s, Source: %s', result_str[result],
                 source_str[source])
    LOGGER.error('Reason: %s', reason_str[source - 1][reason])

def logging_requested_handler(event):
    pass

def logging_established_handler(event):
    pass

def logging_released_handler(event):
    LOGGER.info('Association Released')


# ACSE sub-handlers
# OK
def _recv_a_abort(event):
    """Handler for the ACSE receiving an A-ABORT from the DUL service."""
    source = event.message.abort_source
    sources = {
        0 : 'DUL service-user',
        1 : 'Reserved',
        2 : 'DUL service-provider'
    }
    s = ['Abort Parameters:']
    s.append(
        '========================== BEGIN A-ABORT ========================'
    )
    s.append('Abort Source: {0!s}'.format(sources[source]))
    s.append(
        '=========================== END A-ABORT ========================='
    )
    for line in s:
        LOGGER.debug(line)

# OK
def _recv_ap_abort(event):
    """Handler for the ACSE receiving an A-P-ABORT from the DUL service."""
    reason = event.message.provider_reason
    reasons = {
        0 : "No reason given",
        1 : "Unrecognised PDU",
        2 : "Unexpected PDU",
        3 : "Reserved",
        4 : "Unrecognised PDU parameter",
        5 : "Unexpected PDU parameter",
        6 : "Invalid PDU parameter value"
    }
    s = ['Abort Parameters:']
    s.append(
        '========================= BEGIN A-P-ABORT ======================='
    )
    s.append('Abort Reason: {0!s}'.format(reasons[reason]))
    s.append(
        '========================== END A-P-ABORT ========================'
    )
    for line in s:
        LOGGER.debug(line)

# OK
def _recv_a_associate(event):
    """Handler for the ACSE receiving an A-ASSOCIATE from the DUL service."""
    if event.message.result is None:
        # A-ASSOCIATE Request
        _recv_a_associate_rq(event)
    elif event.message.result == 0x00:
        # A-ASSOCIATE Response (accept)
        _recv_a_associate_ac(event)
    else:
        # A-ASSOCIATE Response (reject)
        _recv_a_associate_rj(event)

# OK
def _recv_a_associate_rq(event):
    """Handler for the ACSE receiving an A-ASSOCIATE (request) from the DUL."""
    LOGGER.info("Association Received")

    req = event.message

    app_context = req.application_context_name.title()
    pres_contexts = req.presentation_context_definition_list
    user_info = req.user_information
    ext_neg = {
        ii.sop_class_uid:ii for ii in req.user_information
        if isinstance(ii, SOPClassExtendedNegotiation)
    }
    com_neg = {
        ii.sop_class_uid:ii for ii in req.user_information
        if isinstance(ii, SOPClassCommonExtendedNegotiation)
    }
    role_items = {
        ii.sop_class_uid:ii for ii in req.user_information
        if isinstance(ii, SCP_SCU_RoleSelectionNegotiation)
    }
    user_id = [
        ii for ii in req.user_information
        if isinstance(ii, UserIdentityNegotiation)
    ]
    async_ops = [
        ii for ii in req.user_information
        if isinstance(ii, AsynchronousOperationsWindowNegotiation)
    ]
    version_name = [
        ii for ii in req.user_information
        if isinstance(ii, ImplementationVersionNameNotification)
    ]
    if version_name:
        version_name = version_name[0].implementation_version_name.decode('ascii')
    else:
        version_name = 'unknown'

    #responding_ae = 'resp. AP Title'
    their_class_uid = 'unknown'
    if req.implementation_class_uid:
        their_class_uid = req.implementation_class_uid

    s = ['Request Parameters:']
    s.append('====================== BEGIN A-ASSOCIATE-RQ ================'
             '=====')
    s.append('Their Implementation Class UID:      {0!s}'
             .format(their_class_uid))
    s.append('Their Implementation Version Name:   {0!s}'.format(version_name))
    s.append('Application Context Name:    {0!s}'
             .format(app_context))
    s.append('Calling Application Name:    {0!s}'
             .format(req.calling_ae_title.decode('ascii')))
    s.append('Called Application Name:     {0!s}'
             .format(req.called_ae_title.decode('ascii')))
    s.append('Their Max PDU Receive Size:  {0!s}'
             .format(req.maximum_length_received))

    ## Presentation Contexts
    s.append('Presentation Contexts:')

    for cx in pres_contexts:
        s.append('  Context ID:        {0!s} '
                 '(Proposed)'.format((cx.context_id)))
        s.append('    Abstract Syntax: ='
                 '{0!s}'.format(cx.abstract_syntax.name))

        # Add SCP/SCU Role Selection Negotiation
        # Roles are: SCU, SCP/SCU, SCP, Default
        try:
            role = role_items[cx.abstract_syntax]
            roles = []
            if role.scp_role:
                roles.append('SCP')
            if role.scu_role:
                roles.append('SCU')

            scp_scu_role = '/'.join(roles)
        except KeyError:
            scp_scu_role = 'Default'

        s.append('    Proposed SCP/SCU Role: {0!s}'.format(scp_scu_role))

        # Transfer Syntaxes
        if len(cx.transfer_syntax) == 1:
            s.append('    Proposed Transfer Syntax:')
        else:
            s.append('    Proposed Transfer Syntaxes:')

        for ts in cx.transfer_syntax:
            s.append('      ={0!s}'.format(ts.name))

    ## Extended Negotiation
    if ext_neg:
        s.append('Requested Extended Negotiation:')

        for item in ext_neg:
            s.append('  SOP Class: ={0!s}'.format(item.uid))
            app_info = pretty_bytes(item.app_info)
            app_info[0] = '[' + app_info[0][1:]
            app_info[-1] = app_info[-1] + ' ]'
            for line in app_info:
                s.append('    {0!s}'.format(line))
    else:
        s.append('Requested Extended Negotiation: None')

    ## Common Extended Negotiation
    if com_neg:
        s.append('Requested Common Extended Negotiation:')

        for item in com_neg:

            s.append('  SOP Class: ={0!s}'.format(item.sop_class_uid.name))
            s.append(
                "    Service Class: ={0!s}"
                .format(item.service_class_uid.name)
            )

            related_uids = item.related_general_sop_class_identification
            if related_uids:
                s.append('    Related General SOP Class(es):')
                for sub_field in related_uids:
                    s.append('      ={0!s}'.format(sub_field.name))
            else:
                s.append('    Related General SOP Classes: None')
    else:
        s.append('Requested Common Extended Negotiation: None')

    ## Asynchronous Operations Window Negotiation
    if async_ops:
        async_ops = async_ops[0]
        s.append('Requested Asynchronous Operations Window Negotiation:')
        s.append(
            "  Maximum Invoked Operations:     {}"
            .format(async_ops.maximum_number_operations_invoked)
        )
        s.append(
            "  Maximum Performed Operations:   {}"
            .format(async_ops.maximum_number_operations_performed)
        )
    else:
        s.append(
            "Requested Asynchronous Operations Window Negotiation: None"
        )

    ## User Identity
    if user_id:
        usid = user_id[0]
        s.append('Requested User Identity Negotiation:')
        s.append('  Authentication Mode: {0:d} - {1!s}'
                 .format(usid.id_type, usid.id_type_str))
        if usid.id_type == 1:
            s.append('  Username: [{0!s}]'
                     .format(usid.primary.decode('utf-8')))
        elif usid.id_type == 2:
            s.append('  Username: [{0!s}]'
                     .format(usid.primary.decode('utf-8')))
            s.append('  Password: [{0!s}]'
                     .format(usid.secondary.decode('utf-8')))
        elif usid.id_type == 3:
            s.append('  Kerberos Service Ticket (not dumped) length: '
                     '{0:d}'.format(len(usid.primary)))
        elif usid.id_type == 4:
            s.append('  SAML Assertion (not dumped) length: '
                     '{0:d}'.format(len(usid.primary)))
        elif usid.id_type == 5:
            s.append('  JSON Web Token (not dumped) length: '
                     '{0:d}'.format(len(usid.primary)))

        if usid.response_requested:
            s.append('  Positive Response requested: Yes')
        else:
            s.append('  Positive Response requested: None')
    else:
        s.append('Requested User Identity Negotiation: None')

    s.append(
        '======================= END A-ASSOCIATE-RQ ======================'
    )

    for line in s:
        LOGGER.debug(line)

# OK
def _recv_a_associate_ac(event):
    """Handler for the ACSE receiving an A-ASSOCIATE (accept) from the DUL."""
    # To receive an A-ASSOCIATE (accept) we should be the requestor
    rsp = event.message
    assoc = event.assoc

    # Returns list, index as {ID : cx}
    req_contexts = assoc.requestor.requested_contexts
    req_contexts = {ii.context_id:ii for ii in req_contexts}

    app_context = rsp.application_context_name.title()
    pres_contexts = rsp.presentation_context_definition_results_list
    pres_contexts = sorted(pres_contexts, key=lambda x: x.context_id)
    user_info = rsp.user_information

    ext_neg = {
        ii.sop_class_uid:ii for ii in rsp.user_information
        if isinstance(ii, SOPClassExtendedNegotiation)
    }
    com_neg = {
        ii.sop_class_uid:ii for ii in rsp.user_information
        if isinstance(ii, SOPClassCommonExtendedNegotiation)
    }
    role_items = {
        ii.sop_class_uid:ii for ii in rsp.user_information
        if isinstance(ii, SCP_SCU_RoleSelectionNegotiation)
    }
    user_id = [
        ii for ii in rsp.user_information
        if isinstance(ii, UserIdentityNegotiation)
    ]
    async_ops = [
        ii for ii in rsp.user_information
        if isinstance(ii, AsynchronousOperationsWindowNegotiation)
    ]
    version_name = [
        ii for ii in rsp.user_information
        if isinstance(ii, ImplementationVersionNameNotification)
    ]
    if version_name:
        version_name = version_name[0].implementation_version_name.decode('ascii')
    else:
        version_name = 'unknown'

    their_class_uid = 'unknown'

    cx_results = {
        0 : 'Accepted',
        1 : 'User Rejection',
        2 : 'Provider Rejection',
        3 : 'Abstract Syntax Not Supported',
        4 : 'Transfer Syntax Not Supported'
    }

    if rsp.implementation_class_uid:
        their_class_uid = rsp.implementation_class_uid

    s = ['Accept Parameters:']
    s.append('====================== BEGIN A-ASSOCIATE-AC ================'
             '=====')

    s.append('Their Implementation Class UID:    {0!s}'
             .format(their_class_uid))
    s.append('Their Implementation Version Name: {0!s}'.format(version_name))
    s.append('Application Context Name:    {0!s}'.format(app_context))
    s.append('Calling Application Name:    {0!s}'
             .format(rsp.calling_ae_title.decode('ascii')))
    s.append('Called Application Name:     {0!s}'
             .format(rsp.called_ae_title.decode('ascii')))
    s.append('Their Max PDU Receive Size:  {0!s}'
             .format(rsp.maximum_length_received))
    s.append('Presentation Contexts:')

    for cx in pres_contexts:
        s.append('  Context ID:        {0!s} ({1!s})'
                 .format(cx.context_id, cx_results[cx.result]))
        # Grab the abstract syntax
        a_syntax = req_contexts[cx.context_id].abstract_syntax
        s.append('    Abstract Syntax: ={0!s}'.format(a_syntax.name))

        # Add SCP/SCU Role Selection Negotiation
        # Roles are: SCU, SCP/SCU, SCP, Default
        if cx.result == 0:
            try:
                role = role_items[a_syntax]
                cx_roles = []
                if role.scp_role:
                    cx_roles.append('SCP')
                if role.scu_role:
                    cx_roles.append('SCU')

                scp_scu_role = '/'.join(cx_roles)
            except KeyError:
                scp_scu_role = 'Default'

            s.append('    Accepted SCP/SCU Role: {0!s}'.format(scp_scu_role))
            s.append('    Accepted Transfer Syntax: ={0!s}'
                     .format(cx.transfer_syntax[0].name))

    ## Extended Negotiation
    if ext_neg:
        s.append('Accepted Extended Negotiation:')

        for item in ext_neg:
            s.append('  SOP Class: ={0!s}'.format(item.uid))
            app_info = pretty_bytes(item.app_info)
            app_info[0] = '[' + app_info[0][1:]
            app_info[-1] = app_info[-1] + ' ]'
            for line in app_info:
                s.append('    {0!s}'.format(line))
    else:
        s.append('Accepted Extended Negotiation: None')

    ## Asynchronous Operations
    if async_ops:
        s.append(
            "Accepted Asynchronous Operations Window Negotiation:"
        )
        s.append(
            "  Maximum Invoked Operations:     {}"
            .format(async_ops.maximum_number_operations_invoked)
        )
        s.append(
            "  Maximum Performed Operations:   {}"
            .format(async_ops.maximum_number_operations_performed)
        )
    else:
        s.append(
            "Accepted Asynchronous Operations Window Negotiation: None"
        )

    ## User Identity
    usr_id = 'Yes' if user_id else 'None'

    s.append('User Identity Negotiation Response: {0!s}'.format(usr_id))
    s.append(
        '======================= END A-ASSOCIATE-AC ======================'
    )

    for line in s:
        LOGGER.debug(line)

    LOGGER.info('Association Accepted')

# Test
def _recv_a_associate_rj(event):
    """
    """
    rej = event.message
    reasons = {
        1 : {
            1 : "No reason given",
            2 : "Application context name not supported",
            3 : "Calling AE title not recognised",
            4 : "Reserved",
            5 : "Reserved",
            6 : "Reserved",
            7 : "Called AE title not recognised",
            8 : "Reserved",
            9 : "Reserved",
            10 : "Reserved"
        },
        2 : {
            1 : "No reason given",
            2 : "Protocol version not supported"
        },
        3 : {
            0 : "Reserved",
            1 : "Temporary congestion",
            2 : "Local limit exceeded",
            3 : "Reserved",
            4 : "Reserved",
            5: "Reserved",
            6 : "Reserved",
            7 : "Reserved"
        }
    }
    reasons = reasons[rej.result_source]
    sources = {
        1 : 'DUL service-user',
        2 : 'DUL service-provider (ACSE related)',
        3 : 'DUL service-provider (presentation related)'
    }
    results = {
        1 : 'Rejected (Permanent)',
        2 : 'Rejected (Transient)'
    }

    s = ['Reject Parameters:']
    s.append(
        '====================== BEGIN A-ASSOCIATE-RJ ====================='
    )
    s.append('Result:    {0!s}'.format(results[rej.result]))
    s.append('Source:    {0!s}'.format(sources[rej.result_source]))
    s.append('Reason:    {0!s}'.format(reasons[rej.diagnostic]))
    s.append(
        '======================= END A-ASSOCIATE-RJ ======================'
    )
    for line in s:
        LOGGER.debug(line)

# Test
def _recv_a_release(event):
    """
    """
    if event.message.result:
        _recv_a_release_rp(event)
    else:
        _recv_a_release_rq(event)

# OK
def _recv_a_release_rp(event):
    """
    """
    pass

# OK
def _recv_a_release_rq(event):
    """
    """
    pass

# OK
def _send_a_abort(event):
    """Handler for the ACSE sending an A-ABORT to the DUL service."""
    LOGGER.info('Aborting Association')

# OK
def _send_ap_abort(event):
    """Handler for the ACSE sending an A-ABORT to the DUL service."""
    LOGGER.info('Aborting Association')

# OK
def _send_a_associate(event):
    """Handler for the ACSE sending an A-ASSOCIATE to the DUL service."""
    if event.message.result is None:
        # A-ASSOCIATE Request
        _send_a_associate_rq(event)
    elif event.message.result == 0x00:
        # A-ASSOCIATE Response (accept)
        _send_a_associate_ac(event)
    else:
        # A-ASSOCIATE Response (reject)
        _send_a_associate_rj(event)

# OK
def _send_a_associate_ac(event):
    """
    """
    LOGGER.info("Association Accepted")
    # To send an A-ASSOCIATE (accept) we should be the acceptor
    rsp = event.message
    assoc = event.assoc

    app_context = rsp.application_context_name.title()
    pres_contexts = rsp.presentation_context_definition_results_list
    pres_contexts = sorted(pres_contexts, key=lambda x: x.context_id)
    user_info = rsp.user_information

    ext_neg = {
        ii.sop_class_uid:ii for ii in rsp.user_information
        if isinstance(ii, SOPClassExtendedNegotiation)
    }
    com_neg = {
        ii.sop_class_uid:ii for ii in rsp.user_information
        if isinstance(ii, SOPClassCommonExtendedNegotiation)
    }
    role_items = {
        ii.sop_class_uid:ii for ii in rsp.user_information
        if isinstance(ii, SCP_SCU_RoleSelectionNegotiation)
    }
    user_id = [
        ii for ii in rsp.user_information
        if isinstance(ii, UserIdentityNegotiation)
    ]
    async_ops = [
        ii for ii in rsp.user_information
        if isinstance(ii, AsynchronousOperationsWindowNegotiation)
    ]
    version_name = [
        ii for ii in rsp.user_information
        if isinstance(ii, ImplementationVersionNameNotification)
    ]
    if version_name:
        version_name = version_name[0].implementation_version_name.decode('ascii')
    else:
        version_name = '(none)'

    cx_results = {
        0 : 'Accepted',
        1 : 'User Rejection',
        2 : 'Provider Rejection',
        3 : 'Abstract Syntax Not Supported',
        4 : 'Transfer Syntax Not Supported'
    }

    their_class_uid = 'unknown'
    if rsp.implementation_class_uid:
        their_class_uid = rsp.implementation_class_uid

    responding_ae = 'resp. AE Title'

    s = ['Accept Parameters:']
    s.append('====================== BEGIN A-ASSOCIATE-AC ================'
             '=====')

    s.append('Our Implementation Class UID:      '
             '{0!s}'.format(their_class_uid))

    s.append("Our Implementation Version Name:   {0!s}".format(version_name))
    s.append('Application Context Name:    {0!s}'.format(app_context))
    s.append('Responding Application Name: {0!s}'.format(responding_ae))
    s.append('Our Max PDU Receive Size:    '
             '{0!s}'.format(rsp.maximum_length_received))
    s.append('Presentation Contexts:')

    if not pres_contexts:
        s.append('    (no valid presentation contexts)')

    # Sort by context ID
    for cx in sorted(pres_contexts, key=lambda x: x.context_id):
        s.append('  Context ID:        {0!s} ({1!s})'
                 .format(cx.context_id, cx_results[cx.result]))
        s.append('    Abstract Syntax: ={0!s}'.format(cx.abstract_syntax.name))

        # If Presentation Context was accepted
        if cx.result == 0:

            try:
                role = role_items[cx.abstract_syntax]
                cx_roles = []
                if role.scp_role:
                    cx_roles.append('SCP')
                if role.scu_role:
                    cx_roles.append('SCU')

                scp_scu_role = '/'.join(cx_roles)
            except KeyError:
                scp_scu_role = 'Default'

            s.append('    Accepted SCP/SCU Role: {0!s}'.format(scp_scu_role))

            s.append('    Accepted Transfer Syntax: ={0!s}'
                     .format(cx.transfer_syntax[0].name))

    ## Extended Negotiation
    if ext_neg:
        s.append('Accepted Extended Negotiation:')

        for item in ext_neg:
            s.append('  SOP Class: ={0!s}'.format(item.uid))
            app_info = pretty_bytes(item.app_info)
            app_info[0] = '[' + app_info[0][1:]
            app_info[-1] = app_info[-1] + ' ]'
            for line in app_info:
                s.append('    {0!s}'.format(line))
    else:
        s.append('Accepted Extended Negotiation: None')

    ## Asynchronous Operations
    if async_ops:
        async_ops = async_ops[0]
        s.append(
            "Accepted Asynchronous Operations Window Negotiation:"
        )
        s.append(
            "  Maximum Invoked Operations:     {}"
            .format(async_ops.maximum_number_operations_invoked)
        )
        s.append(
            "  Maximum Performed Operations:   {}"
            .format(async_ops.maximum_number_operations_performed)
        )
    else:
        s.append(
            "Accepted Asynchronous Operations Window Negotiation: None"
        )

    ## User Identity Negotiation
    usr_id = 'Yes' if user_id else 'None'


    s.append('User Identity Negotiation Response: {0!s}'.format(usr_id))
    s.append(
        '======================= END A-ASSOCIATE-AC ======================'
    )

    for line in s:
        LOGGER.debug(line)

# OK
def _send_a_associate_rj(event):
    """
    """
    LOGGER.info("Association Rejected")

# OK
def _send_a_associate_rq(event):
    """"""
    req = event.message

    app_context = req.application_context_name.title()
    pres_contexts = req.presentation_context_definition_list
    user_info = req.user_information
    ext_neg = {
        ii.sop_class_uid:ii for ii in req.user_information
        if isinstance(ii, SOPClassExtendedNegotiation)
    }
    com_neg = {
        ii.sop_class_uid:ii for ii in req.user_information
        if isinstance(ii, SOPClassCommonExtendedNegotiation)
    }
    role_items = {
        ii.sop_class_uid:ii for ii in req.user_information
        if isinstance(ii, SCP_SCU_RoleSelectionNegotiation)
    }
    user_id = [
        ii for ii in req.user_information
        if isinstance(ii, UserIdentityNegotiation)
    ]
    async_ops = [
        ii for ii in req.user_information
        if isinstance(ii, AsynchronousOperationsWindowNegotiation)
    ]
    version_name = [
        ii for ii in req.user_information
        if isinstance(ii, ImplementationVersionNameNotification)
    ]
    if version_name:
        version_name = version_name[0].implementation_version_name.decode('ascii')
    else:
        version_name = '(none)'

    s = ['Request Parameters:']
    s.append(
        '====================== BEGIN A-ASSOCIATE-RQ ====================='
    )

    s.append('Our Implementation Class UID:      '
             '{0!s}'.format(req.implementation_class_uid))
    s.append('Our Implementation Version Name:   {0!s}'.format(version_name))
    s.append('Application Context Name:    {0!s}'.format(app_context))
    s.append('Calling Application Name:    '
             '{0!s}'.format(req.calling_ae_title.decode('ascii')))
    s.append('Called Application Name:     '
             '{0!s}'.format(req.called_ae_title.decode('ascii')))
    s.append('Our Max PDU Receive Size:    '
             '{0!s}'.format(req.maximum_length_received))

    ## Presentation Contexts
    s.append('Presentation Contexts:')
    for cx in pres_contexts:
        s.append('  Context ID:        {0!s} '
                 '(Proposed)'.format((cx.context_id)))
        s.append('    Abstract Syntax: ={0!s}'.format(cx.abstract_syntax.name))

        # Add SCP/SCU Role Selection Negotiation
        # Roles are: SCU, SCP/SCU, SCP, Default
        if role_items:
            try:
                role = role_items[cx.abstract_syntax]
                cx_roles = []
                if role.scp_role:
                    cx_roles.append('SCP')
                if role.scu_role:
                    cx_roles.append('SCU')

                scp_scu_role = '/'.join(cx_roles)
            except KeyError:
                scp_scu_role = 'Default'
        else:
            scp_scu_role = 'Default'

        s.append('    Proposed SCP/SCU Role: {0!s}'.format(scp_scu_role))

        # Transfer Syntaxes
        if len(cx.transfer_syntax) == 1:
            s.append('    Proposed Transfer Syntax:')
        else:
            s.append('    Proposed Transfer Syntaxes:')

        for ts in cx.transfer_syntax:
            s.append('      ={0!s}'.format(ts.name))

    ## Extended Negotiation
    if ext_neg:
        s.append('Requested Extended Negotiation:')

        for item in ext_neg:
            s.append('  SOP Class: ={0!s}'.format(item.uid))

            app_info = pretty_bytes(item.app_info)
            app_info[0] = '[' + app_info[0][1:]
            app_info[-1] = app_info[-1] + ' ]'
            for line in app_info:
                s.append('    {0!s}'.format(line))
    else:
        s.append('Requested Extended Negotiation: None')

    ## Common Extended Negotiation
    if com_neg:
        s.append('Requested Common Extended Negotiation:')

        for item in com_neg:

            s.append('  SOP Class: ={0!s}'.format(item.sop_class_uid.name))
            s.append(
                "    Service Class: ={0!s}"
                .format(item.service_class_uid.name)
            )

            related_uids = item.related_general_sop_class_identification
            if related_uids:
                s.append('    Related General SOP Class(es):')
                for sub_field in related_uids:
                    s.append('      ={0!s}'.format(sub_field.name))
            else:
                s.append('    Related General SOP Classes: None')
    else:
        s.append('Requested Common Extended Negotiation: None')

    ## Asynchronous Operations Window Negotiation
    if async_ops:
        async_ops = async_ops[0]
        s.append('Requested Asynchronous Operations Window Negotiation:')
        s.append(
            "  Maximum Invoked Operations:     {}"
            .format(async_ops.maximum_number_operations_invoked)
        )
        s.append(
            "  Maximum Performed Operations:   {}"
            .format(async_ops.maximum_number_operations_performed)
        )
    else:
        s.append(
            "Requested Asynchronous Operations Window Negotiation: None"
        )

    ## User Identity
    if user_id:
        usid = user_id[0]
        s.append('Requested User Identity Negotiation:')
        s.append('  Authentication Mode: {0:d} - '
                 '{1!s}'.format(usid.id_type, usid.id_type_str))
        if usid.id_type == 1:
            s.append('  Username: '
                     '[{0!s}]'.format(usid.primary.decode('utf-8')))
        elif usid.id_type == 2:
            s.append('  Username: '
                     '[{0!s}]'.format(usid.primary.decode('utf-8')))
            s.append('  Password: '
                     '[{0!s}]'.format(usid.secondary.decode('utf-8')))
        elif usid.id_type == 3:
            s.append('  Kerberos Service Ticket (not dumped) length: '
                     '{0:d}'.format(len(usid.primary)))
        elif usid.id_type == 4:
            s.append('  SAML Assertion (not dumped) length: '
                     '{0:d}'.format(len(usid.primary)))
        elif usid.id_type == 5:
            s.append('  JSON Web Token (not dumped) length: '
                     '{0:d}'.format(len(usid.primary)))

        if usid.response_requested:
            s.append('  Positive Response Requested: Yes')
        else:
            s.append('  Positive Response Requested: No')
    else:
        s.append('Requested User Identity Negotiation: None')

    s.append(
        '======================= END A-ASSOCIATE-RQ ======================'
    )

    for line in s:
        LOGGER.debug(line)

# Test
def _send_a_release(event):
    """
    """
    if event.message.result:
        _send_a_release_rp(event)
    else:
        _send_a_release_rq(event)

# OK
def _send_a_release_rp(event):
    """
    """
    pass

# OK
def _send_a_release_rq(event):
    """
    """
    pass



# DIMSE sub-handlers
def _send_c_echo_rq(event):
    """Logging handler for when a C-ECHO-RQ is sent.

    **C-ECHO Request Parameters**

    | (M) Message ID
    | (M) Affected SOP Class UID

    Parameters
    ----------
    event : event.Event
        The evt.EVT_DIMSE_SENT event that occurred.
    """
    msg = event.message
    cs = msg.command_set
    LOGGER.info("Sending Echo Request: MsgID %s", cs.MessageID)

def _send_c_echo_rsp(event):
    """Logging handler for when a C-ECHO-RSP is sent.

    **C-ECHO Response Parameters**

    | (U) Message ID
    | (M) Message ID Being Responded To
    | (U) Affected SOP Class UID
    | (M) Status

    Parameters
    ----------
    event : event.Event
        The evt.EVT_DIMSE_SENT event that occurred.
    """
    pass

def _send_c_store_rq(event):
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
        The evt.EVT_DIMSE_SENT event that occurred.
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

def _send_c_store_rsp(event):
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
        The evt.EVT_DIMSE_SENT event that occurred.
    """
    pass

def _send_c_find_rq(event):
    """Logging handler when a C-FIND-RQ is sent.

    **C-FIND Request Parameters**

    | (M) Message ID
    | (M) Affected SOP Class UID
    | (M) Priority
    | (M) Identifier

    Parameters
    ----------
    event : event.Event
        The evt.EVT_DIMSE_SENT event that occurred.
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

def _send_c_find_rsp(event):
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
        The evt.EVT_DIMSE_SENT event that occurred.
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

def _send_c_get_rq(event):
    """Logging handler when a C-GET-RQ is sent.

    **C-GET Request Parameters**

    | (M) Message ID
    | (M) Affected SOP Class UID
    | (M) Priority
    | (M) Identifier

    Parameters
    ----------
    event : event.Event
        The evt.EVT_DIMSE_SENT event that occurred.
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

def _send_c_get_rsp(event):
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
        The evt.EVT_DIMSE_SENT event that occurred.
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

def _send_c_move_rq(event):
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
        The evt.EVT_DIMSE_SENT event that occurred.
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

def _send_c_move_rsp(event):
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
        The evt.EVT_DIMSE_SENT event that occurred.
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

def _send_c_cancel_rq(event):
    """Logging handler when a C-CANCEL-RQ is sent.

    Covers C-CANCEL-FIND-RQ, C-CANCEL-GET-RQ and C-CANCEL-MOVE-RQ.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_DIMSE_SENT event that occurred.
    """
    pass

def _recv_c_echo_rq(event):
    """Logging handler when a C-ECHO-RQ is received.

    **C-ECHO Request Parameters**

    | (M) Message ID
    | (M) Affected SOP Class UID

    Parameters
    ----------
    event : event.Event
        The evt.EVT_DIMSE_RECV event that occurred.
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

def _recv_c_echo_rsp(event):
    """Logging handler when a C-ECHO-RSP is received.

    **C-ECHO Response Parameters**

    | (U) Message ID
    | (M) Message ID Being Responded To
    | (U) Affected SOP Class UID
    | (M) Status

    Parameters
    ----------
    event : event.Event
        The evt.EVT_DIMSE_RECV event that occurred.
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

def _recv_c_store_rq(event):
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
        The evt.EVT_DIMSE_RECV event that occurred.
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

def _recv_c_store_rsp(event):
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
        The evt.EVT_DIMSE_RECV event that occurred.
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

def _recv_c_find_rq(event):
    """Logging handler when a C-FIND-RQ is received.

    **C-FIND Request Parameters**

    | (M) Message ID
    | (M) Affected SOP Class UID
    | (M) Priority
    | (M) Identifier

    Parameters
    ----------
    event : event.Event
        The evt.EVT_DIMSE_RECV event that occurred.
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

def _recv_c_find_rsp(event):
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
        The evt.EVT_DIMSE_RECV event that occurred.
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

def _recv_c_cancel_rq(event):
    """Logging handler when a C-CANCEL-RQ is received.

    Covers C-CANCEL-FIND-RQ, C-CANCEL-GET-RQ and C-CANCEL-MOVE-RQ

    Parameters
    ----------
    event : event.Event
        The evt.EVT_DIMSE_RECV event that occurred.
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

def _recv_c_get_rq(event):
    """Logging handler when a C-GET-RQ is received.

    **C-GET Request Parameters**

    | (M) Message ID
    | (M) Affected SOP Class UID
    | (M) Priority
    | (M) Identifier

    Parameters
    ----------
    event : event.Event
        The evt.EVT_DIMSE_RECV event that occurred.
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

def _recv_c_get_rsp(event):
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
        The evt.EVT_DIMSE_RECV event that occurred.
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

def _recv_c_move_rq(event):
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
        The evt.EVT_DIMSE_RECV event that occurred.
    """
    pass

def _recv_c_move_rsp(event):
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
        The evt.EVT_DIMSE_RECV event that occurred.
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

def _send_n_event_report_rq(event):
    """Logging handler when an N-EVENT-REPORT-RQ is sent.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_DIMSE_SENT event that occurred.
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

def _send_n_event_report_rsp(event):
    """Logging handler when an N-EVENT-REPORT-RSP is sent.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_DIMSE_SENT event that occurred.
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

def _send_n_get_rq(event):
    """Logging handler when an N-GET-RQ is sent.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_DIMSE_SENT event that occurred.
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

def _send_n_get_rsp(event):
    """Logging handler when an N-GET-RSP is sent.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_DIMSE_SENT event that occurred.
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

def _send_n_set_rq(event):
    """Logging handler when an N-SET-RQ is sent.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_DIMSE_SENT event that occurred.
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

def _send_n_set_rsp(event):
    """Logging handler when an N-SET-RSP is sent.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_DIMSE_SENT event that occurred.
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

def _send_n_action_rq(event):
    """Logging handler when an N-ACTION-RQ is sent.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_DIMSE_SENT event that occurred.
    """
    pass

def _send_n_action_rsp(event):
    """Logging handler when an N-ACTION-RSP is sent.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_DIMSE_SENT event that occurred.
    """
    pass

def _send_n_create_rq(event):
    """Logging handler when an N-CREATE-RQ is sent.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_DIMSE_SENT event that occurred.
    """
    pass

def _send_n_create_rsp(event):
    """Logging handler when an N-CREATE-RSP is sent.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_DIMSE_SENT event that occurred.
    """
    pass

def _send_n_delete_rq(event):
    """Logging handler when an N-DELETE-RQ is sent.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_DIMSE_SENT event that occurred.
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

def _send_n_delete_rsp(event):
    """Logging handler when an N-DELETE-RSP is sent.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_DIMSE_SENT event that occurred.
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

def _recv_n_event_report_rq(event):
    """Logging handler when an N-EVENT-REPORT-RQ is received.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_DIMSE_RECV event that occurred.
    """
    pass

def _recv_n_event_report_rsp(event):
    """Logging handler when an N-EVENT-REPORT-RSP is received.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_DIMSE_RECV event that occurred.
    """
    pass

def _recv_n_get_rq(event):
    """Logging handler when an N-GET-RQ is received.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_DIMSE_RECV event that occurred.
    """
    pass

def _recv_n_get_rsp(event):
    """Logging handler when an N-GET-RSP is received.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_DIMSE_RECV event that occurred.
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

def _recv_n_set_rq(event):
    """Logging handler when an N-SET-RQ is received.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_DIMSE_RECV event that occurred.
    """
    pass

def _recv_n_set_rsp(event):
    """Logging handler when an N-SET-RSP is received.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_DIMSE_RECV event that occurred.
    """
    pass

def _recv_n_action_rq(event):
    """Logging handler when an N-ACTION-RQ is received.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_DIMSE_RECV event that occurred.
    """
    pass

def _recv_n_action_rsp(event):
    """Logging handler when an N-ACTION-RSP is received.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_DIMSE_RECV event that occurred.
    """
    pass

def _recv_n_create_rq(event):
    """Logging handler when an N-CREATE-RQ is received.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_DIMSE_RECV event that occurred.
    """
    pass

def _recv_n_create_rsp(event):
    """Logging handler when an N-CREATE-RSP is received.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_DIMSE_RECV event that occurred.
    """
    pass

def _recv_n_delete_rq(event):
    """Logging handler when an N-DELETE-RQ is received.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_DIMSE_RECV event that occurred.
    """
    pass

def _recv_n_delete_rsp(event):
    """Logging handler when an N-DELETE-RSP is received.

    Parameters
    ----------
    event : event.Event
        The evt.EVT_DIMSE_RECV event that occurred.
    """
    pass
