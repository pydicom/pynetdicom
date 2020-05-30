"""Standard logging event handlers."""

import logging

from pynetdicom.dimse_messages import *
from pynetdicom.pdu import (
    A_ASSOCIATE_RQ, A_ASSOCIATE_AC, A_ASSOCIATE_RJ, A_RELEASE_RQ,
    A_RELEASE_RP, A_ABORT_RQ, P_DATA_TF
)
from pynetdicom.sop_class import uid_to_service_class
from pynetdicom.utils import pretty_bytes


LOGGER = logging.getLogger('pynetdicom.events')


# Debugging handlers
def debug_fsm(event):
    """Debugging handler for the FSM."""
    LOGGER.debug(
        "{}: {} + {} -> {} -> {}"
        .format(
            event.assoc.mode[0].upper(),
            event.current_state,
            event.fsm_event,
            event.action,
            event.next_state
        )
    )


# Standard logging handlers
def standard_pdu_recv_handler(event):
    """Standard handler when a PDU is received and decoded.

    **Event**

    ``evt.EVT_PDU_RECV``

    Parameters
    ----------
    event : events.Event
        The ``evt.EVT_PDU_RECV`` event corresponding to receiving and decoding
        a PDU from the peer. :class:`~pynetdicom.events.Event` attributes are:

        * :attr:`~pynetdicom.events.Event.assoc`: the
          :class:`~pynetdicom.association.Association`
          that received the PDU.
        * ``pdu``: the PDU that was received, one of the ``pdu.PDU``
          subclasses.
        * :attr:`~pynetdicom.events.Event.timestamp`: the date and time that
          the PDU was received as :class:`datetime.datetime`.
    """
    pdu = event.pdu
    handlers = {
        A_ASSOCIATE_AC : _receive_associate_ac,
        A_ASSOCIATE_RJ : _receive_associate_rj,
        A_ASSOCIATE_RQ : _receive_associate_rq,
        A_RELEASE_RQ : _receive_release_rq,
        A_RELEASE_RP : _receive_release_rp,
        A_ABORT_RQ : _receive_abort_pdu,
        P_DATA_TF : _receive_data_tf,
    }
    with event.assoc.lock:
        handlers[type(pdu)](event)

def standard_pdu_sent_handler(event):
    """Standard handler when a PDU is encoded and sent.

    **Event**

    ``evt.EVT_PDU_SENT``

    Parameters
    ----------
    event : events.Event
        The ``evt.EVT_PDU_SENT`` event corresponding to encoding and sending
        a PDU to the peer. :class:`~pynetdicom.events.Event` attributes are:

        * :attr:`~pynetdicom.events.Event.assoc`: the
          :class:`~pynetdicom.association.Association`
          that sent the PDU.
        * ``pdu``: the PDU that was sent, one of the ``pdu.PDU`` subclasses.
        * :attr:`~pynetdicom.events.Event.timestamp`: the date and time that
          the PDU was sent as :class:`datetime.datetime`.
    """
    pdu = event.pdu
    handlers = {
        A_ASSOCIATE_AC : _send_associate_ac,
        A_ASSOCIATE_RJ : _send_associate_rj,
        A_ASSOCIATE_RQ : _send_associate_rq,
        A_RELEASE_RQ : _send_release_rq,
        A_RELEASE_RP : _send_release_rp,
        A_ABORT_RQ : _send_abort,
        P_DATA_TF : _send_data_tf,
    }
    with event.assoc.lock:
        handlers[type(pdu)](event)

def standard_dimse_recv_handler(event):
    """Standard handler for the ACSE receiving a primitive from the DUL.

    Parameters
    ----------
    event : events.Event
        The ``evt.EVT_DIMSE_RECV`` event corresponding to the DIMSE decoding
        a message received from the peer. :class:`~pynetdicom.events.Event`
        attributes are:

        * :attr:`~pynetdicom.events.Event.assoc`: the
          :class:`~pynetdicom.association.Association`
          that the DIMSE is providing services for.
        * ``message``: the DIMSE message that was received.
        * :attr:`~pynetdicom.events.Event.timestamp`: the date and time that
          the message was decoded as :class:`datetime.datetime`.
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

    with event.assoc.lock:
        handlers[type(event.message)](event)

def standard_dimse_sent_handler(event):
    """Standard handler for the ACSE receiving a primitive from the DUL.

    Parameters
    ----------
    event : events.Event
        The ``evt.EVT_DIMSE_SENT`` event corresponding to the DIMSE encoding
        a message to be sent to the peer. :class:`~pynetdicom.events.Event`
        attributes are:

        * :attr:`~pynetdicom.events.Event.assoc`: the
          :class:`~pynetdicom.association.Association`
          that the DIMSE is providing services for.
        * ``message``: the DIMSE message to be sent.
        * :attr:`~pynetdicom.events.Event.timestamp`: the date and time that
          the message was decode as :class:`datetime.datetime`.
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

    with event.assoc.lock:
        handlers[type(event.message)](event)


# PDU sub-handlers
def _receive_abort_pdu(event):
    """Standard logging handler for receiving an A-ABORT PDU."""
    s = ['Abort Parameters:']
    s.append('{:=^76}'.format(' INCOMING A-ABORT PDU '))
    s.append('Abort Source: {0!s}'.format(event.pdu.source_str))
    s.append('Abort Reason: {0!s}'.format(event.pdu.reason_str))
    s.append('{:=^76}'.format(' END A-ABORT PDU '))

    for line in s:
        LOGGER.debug(line)

def _receive_associate_ac(event):
    """Standard logging handler for receiving an A-ASSOCIATE-AC PDU."""
    assoc_ac = event.pdu

    app_context = assoc_ac.application_context_name.title()
    pres_contexts = sorted(
        assoc_ac.presentation_context, key=lambda x: x.context_id
    )
    user_info = assoc_ac.user_information
    async_ops = user_info.async_ops_window
    roles = user_info.role_selection

    req_contexts = event.assoc.requestor.requested_contexts
    req_contexts = {ii.context_id:ii for ii in req_contexts}

    their_class_uid = 'unknown'
    their_version = b'unknown'

    if user_info.implementation_class_uid:
        their_class_uid = user_info.implementation_class_uid
    if user_info.implementation_version_name:
        their_version = user_info.implementation_version_name

    s = ['Accept Parameters:']
    s.append('{:=^76}'.format(' INCOMING A-ASSOCIATE-AC PDU '))
    s.append('Their Implementation Class UID:    {0!s}'
             .format(their_class_uid))
    s.append('Their Implementation Version Name: {0!s}'
             .format(their_version.decode('ascii')))
    s.append('Application Context Name:    {0!s}'.format(app_context))
    s.append('Calling Application Name:    {0!s}'
             .format(assoc_ac.calling_ae_title.decode('ascii')))
    s.append('Called Application Name:     {0!s}'
             .format(assoc_ac.called_ae_title.decode('ascii')))
    s.append('Their Max PDU Receive Size:  {0!s}'
             .format(user_info.maximum_length))
    s.append('Presentation Contexts:')

    for cx in pres_contexts:
        s.append('  Context ID:        {0!s} ({1!s})'
                 .format(cx.context_id, cx.result_str))
        # Grab the abstract syntax from the requestor
        a_syntax = req_contexts[cx.context_id].abstract_syntax
        s.append('    Abstract Syntax: ={0!s}'.format(a_syntax.name))

        # Add SCP/SCU Role Selection Negotiation
        # Roles are: SCU, SCP/SCU, SCP, Default
        if cx.result == 0:
            try:
                role = roles[a_syntax]
                cx_roles = []
                if role.scp_role:
                    cx_roles.append('SCP')
                if role.scu_role:
                    cx_roles.append('SCU')
                scp_scu_role = '/'.join(cx_roles)
            except KeyError:
                scp_scu_role = 'Default'

            s.append('    Accepted SCP/SCU Role: {0!s}'.format(scp_scu_role))
            s.append(
                '    Accepted Transfer Syntax: ={0!s}'
                .format(cx.transfer_syntax.name)
            )

    ## Extended Negotiation
    if user_info.ext_neg:
        s.append('Accepted Extended Negotiation:')

        for item in user_info.ext_neg:
            s.append('  SOP Class: ={0!s}'.format(item.uid))
            app_info = pretty_bytes(item.app_info)
            for line in app_info:
                s.append('  {0!s}'.format(line))
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
    usr_id = 'Yes' if user_info.user_identity else 'None'

    s.append('User Identity Negotiation Response: {0!s}'.format(usr_id))
    s.append('{:=^76}'.format(' END A-ASSOCIATE-AC PDU '))

    for line in s:
        LOGGER.debug(line)

def _receive_associate_rj(event):
    """Standard logging handler for receiving an A-ASSOCIATE-RJ PDU."""
    s = ['Reject Parameters:']
    s.append('{:=^76}'.format(' INCOMING A-ASSOCIATE-RJ PDU '))
    s.append('Result:    {0!s}'.format(event.pdu.result_str))
    s.append('Source:    {0!s}'.format(event.pdu.source_str))
    s.append('Reason:    {0!s}'.format(event.pdu.reason_str))
    s.append('{:=^76}'.format(' END A-ASSOCIATE-RJ PDU '))

    for line in s:
        LOGGER.debug(line)

def _receive_associate_rq(event):
    """Standard logging handler for receiving an A-ASSOCIATE-RQ PDU."""
    pdu = event.pdu

    app_context = pdu.application_context_name.title()
    pres_contexts = sorted(
        pdu.presentation_context, key=lambda x: x.context_id
    )
    user_info = pdu.user_information

    #responding_ae = 'resp. AP Title'
    their_class_uid = 'unknown'
    their_version = b'unknown'

    if user_info.implementation_class_uid:
        their_class_uid = user_info.implementation_class_uid
    if user_info.implementation_version_name:
        their_version = user_info.implementation_version_name

    s = ['Request Parameters:']
    s.append('{:=^76}'.format(' INCOMING A-ASSOCIATE-RQ PDU '))
    s.append('Their Implementation Class UID:      {0!s}'
             .format(their_class_uid))
    s.append('Their Implementation Version Name:   {0!s}'
             .format(their_version.decode('ascii')))
    s.append('Application Context Name:    {0!s}'
             .format(app_context))
    s.append('Calling Application Name:    {0!s}'
             .format(pdu.calling_ae_title.decode('ascii')))
    s.append('Called Application Name:     {0!s}'
             .format(pdu.called_ae_title.decode('ascii')))
    s.append('Their Max PDU Receive Size:  {0!s}'
             .format(user_info.maximum_length))

    ## Presentation Contexts
    if len(pres_contexts) == 1:
        s.append('Presentation Context:')
    else:
        s.append('Presentation Contexts:')

    for context in pres_contexts:
        s.append('  Context ID:        {0!s} '
                 '(Proposed)'.format((context.context_id)))
        s.append('    Abstract Syntax: ='
                 '{0!s}'.format(context.abstract_syntax.name))

        # Add SCP/SCU Role Selection Negotiation
        # Roles are: SCU, SCP/SCU, SCP, Default
        if pdu.user_information.role_selection:
            try:
                role = pdu.user_information.role_selection[
                    context.abstract_syntax
                ]
                roles = []
                if role.scp_role:
                    roles.append('SCP')
                if role.scu_role:
                    roles.append('SCU')

                scp_scu_role = '/'.join(roles)
            except KeyError:
                scp_scu_role = 'Default'
        else:
            scp_scu_role = 'Default'

        s.append('    Proposed SCP/SCU Role: {0!s}'.format(scp_scu_role))

        # Transfer Syntaxes
        if len(context.transfer_syntax) == 1:
            s.append('    Proposed Transfer Syntax:')
        else:
            s.append('    Proposed Transfer Syntaxes:')

        for ts in context.transfer_syntax:
            s.append('      ={0!s}'.format(ts.name))

    ## Extended Negotiation
    if pdu.user_information.ext_neg:
        s.append('Requested Extended Negotiation:')

        for item in pdu.user_information.ext_neg:
            s.append('  SOP Class: ={0!s}'.format(item.uid))
            #s.append('    Application Information, length: %d bytes'
            #                                       %len(item.app_info))

            app_info = pretty_bytes(item.app_info)
            for line in app_info:
                s.append('  {0!s}'.format(line))
    else:
        s.append('Requested Extended Negotiation: None')

    ## Common Extended Negotiation
    if pdu.user_information.common_ext_neg:
        s.append('Requested Common Extended Negotiation:')

        for item in pdu.user_information.common_ext_neg:

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
    async_ops = pdu.user_information.async_ops_window
    if async_ops is not None:
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
    if user_info.user_identity is not None:
        usid = user_info.user_identity
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
            s.append('  Positive Response Requested: Yes')
        else:
            s.append('  Positive Response Requested: None')
    else:
        s.append('Requested User Identity Negotiation: None')

    s.append('{:=^76}'.format(' END A-ASSOCIATE-RQ PDU '))

    for line in s:
        LOGGER.debug(line)

def _receive_data_tf(event):
    """Standard logging handler for receiving a P-DATA-TF PDU."""
    pass

def _receive_release_rp(event):
    """Standard logging handler for receiving an A-RELEASE-RP PDU."""
    pass

def _receive_release_rq(event):
    """Standard logging handler for receiving an A-RELEASE-RQ PDU."""
    pass

def _send_abort(event):
    """Standard logging handler for sending an A-ABORT PDU."""
    s = ['Abort Parameters:']
    s.append('{:=^76}'.format(' OUTGOING A-ABORT PDU '))
    s.append('Abort Source: {0!s}'.format(event.pdu.source_str))
    s.append('Abort Reason: {0!s}'.format(event.pdu.reason_str))
    s.append('{:=^76}'.format(' END A-ABORT PDU '))

    for line in s:
        LOGGER.debug(line)

def _send_associate_ac(event):
    """Standard logging handler for sending an A-ASSOCIATE-AC PDU."""
    assoc_ac = event.pdu

    req_contexts = event.assoc.requestor.get_contexts('pcdl')
    req_contexts = {ii.context_id:ii for ii in req_contexts}

    # Needs some cleanup
    app_context = assoc_ac.application_context_name.title()
    pres_contexts = assoc_ac.presentation_context
    user_info = assoc_ac.user_information
    async_ops = user_info.async_ops_window
    roles = user_info.role_selection

    responding_ae = 'resp. AE Title'

    s = ['Accept Parameters:']
    s.append('{:=^76}'.format(' OUTGOING A-ASSOCIATE-AC PDU '))
    s.append('Our Implementation Class UID:      '
             '{0!s}'.format(user_info.implementation_class_uid))

    if user_info.implementation_version_name:
        s.append(
            "Our Implementation Version Name:   {0!s}"
            .format(user_info.implementation_version_name.decode('ascii'))
        )
    s.append('Application Context Name:    {0!s}'.format(app_context))
    s.append('Responding Application Name: {0!s}'.format(responding_ae))
    s.append('Our Max PDU Receive Size:    '
             '{0!s}'.format(user_info.maximum_length))
    s.append('Presentation Contexts:')

    if not pres_contexts:
        s.append('    (no valid presentation contexts)')

    # Sort by context ID
    for cx in sorted(pres_contexts, key=lambda x: x.context_id):
        s.append('  Context ID:        {0!s} ({1!s})'
                 .format(cx.context_id, cx.result_str))
        a_syntax = req_contexts[cx.context_id].abstract_syntax
        s.append('    Abstract Syntax: ={0!s}'.format(a_syntax.name))

        # If Presentation Context was accepted
        if cx.result == 0:
            try:
                role = roles[a_syntax]
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
                     .format(cx.transfer_syntax.name))

    ## Extended Negotiation
    if user_info.ext_neg:
        s.append('Accepted Extended Negotiation:')

        for item in user_info.ext_neg:
            s.append('  SOP Class: ={0!s}'.format(item.uid))
            app_info = pretty_bytes(item.app_info)
            for line in app_info:
                s.append('  {0!s}'.format(line))
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

    ## User Identity Negotiation
    usr_id = 'Yes' if user_info.user_identity is not None else 'None'


    s.append('User Identity Negotiation Response: {0!s}'.format(usr_id))
    s.append('{:=^76}'.format(' END A-ASSOCIATE-AC PDU '))

    for line in s:
        LOGGER.debug(line)

def _send_associate_rj(event):
    """Standard logging handler for sending an A-ASSOCIATE-RJ PDU."""
    s = ['Reject Parameters:']
    s.append('{:=^76}'.format(' OUTGOING A-ASSOCIATE-RJ PDU '))
    s.append('Result:    {0!s}'.format(event.pdu.result_str))
    s.append('Source:    {0!s}'.format(event.pdu.source_str))
    s.append('Reason:    {0!s}'.format(event.pdu.reason_str))
    s.append('{:=^76}'.format(' END A-ASSOCIATE-RJ PDU '))

    for line in s:
        LOGGER.debug(line)

def _send_associate_rq(event):
    """Standard logging handler for sending an A-ASSOCIATE-RQ PDU."""
    pdu = event.pdu

    app_context = pdu.application_context_name.title()
    pres_contexts = pdu.presentation_context
    user_info = pdu.user_information

    s = ['Request Parameters:']
    s.append('{:=^76}'.format(' OUTGOING A-ASSOCIATE-RQ PDU '))

    s.append('Our Implementation Class UID:      '
             '{0!s}'.format(user_info.implementation_class_uid))
    if user_info.implementation_version_name:
        s.append(
            'Our Implementation Version Name:   {0!s}'.format(
                user_info.implementation_version_name.decode('ascii')
            )
        )
    s.append('Application Context Name:    {0!s}'.format(app_context))
    s.append('Calling Application Name:    '
             '{0!s}'.format(pdu.calling_ae_title.decode('ascii')))
    s.append('Called Application Name:     '
             '{0!s}'.format(pdu.called_ae_title.decode('ascii')))
    s.append('Our Max PDU Receive Size:    '
             '{0!s}'.format(user_info.maximum_length))

    ## Presentation Contexts
    if len(pres_contexts) == 1:
        s.append('Presentation Context:')
    else:
        s.append('Presentation Contexts:')

    for context in pres_contexts:
        s.append('  Context ID:        {0!s} '
                 '(Proposed)'.format((context.context_id)))
        s.append('    Abstract Syntax: ='
                 '{0!s}'.format(context.abstract_syntax.name))

        # Add SCP/SCU Role Selection Negotiation
        # Roles are: SCU, SCP/SCU, SCP, Default
        if pdu.user_information.role_selection:
            try:
                role = pdu.user_information.role_selection[
                    context.abstract_syntax
                ]
                roles = []
                if role.scp_role:
                    roles.append('SCP')
                if role.scu_role:
                    roles.append('SCU')

                scp_scu_role = '/'.join(roles)
            except KeyError:
                scp_scu_role = 'Default'
        else:
            scp_scu_role = 'Default'

        s.append('    Proposed SCP/SCU Role: {0!s}'.format(scp_scu_role))

        # Transfer Syntaxes
        if len(context.transfer_syntax) == 1:
            s.append('    Proposed Transfer Syntax:')
        else:
            s.append('    Proposed Transfer Syntaxes:')

        for ts in context.transfer_syntax:
            s.append('      ={0!s}'.format(ts.name))

    ## Extended Negotiation
    if pdu.user_information.ext_neg:
        s.append('Requested Extended Negotiation:')

        for item in pdu.user_information.ext_neg:
            s.append('  SOP Class: ={0!s}'.format(item.uid))
            #s.append('    Application Information, length: %d bytes'
            #                                       %len(item.app_info))

            app_info = pretty_bytes(item.app_info)
            for line in app_info:
                s.append('   {0!s}'.format(line))
    else:
        s.append('Requested Extended Negotiation: None')

    ## Common Extended Negotiation
    if pdu.user_information.common_ext_neg:
        s.append('Requested Common Extended Negotiation:')

        for item in pdu.user_information.common_ext_neg:

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
    async_ops = pdu.user_information.async_ops_window
    if async_ops is not None:
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
    if user_info.user_identity is not None:
        usid = user_info.user_identity
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

    s.append('{:=^76}'.format(' END A-ASSOCIATE-RQ PDU '))

    for line in s:
        LOGGER.debug(line)

def _send_data_tf(event):
    """Standard logging handler for sending a P-DATA-TF PDU."""
    pass

def _send_release_rp(event):
    """Standard logging handler for sending an A-RELEASE-RP PDU."""
    pass

def _send_release_rq(event):
    """Standard logging handler for sending an A-RELEASE-RQ PDU."""
    pass


# DIMSE sub-handlers
def _send_c_echo_rq(event):
    """Logging handler for when a C-ECHO-RQ is sent.

    **C-ECHO Request Parameters**

    | (M) Message ID
    | (M) Affected SOP Class UID

    Parameters
    ----------
    event : events.Event
        The evt.EVT_DIMSE_SENT event that occurred.
    """
    pass

def _send_c_echo_rsp(event):
    """Logging handler for when a C-ECHO-RSP is sent.

    **C-ECHO Response Parameters**

    | (U) Message ID
    | (M) Message ID Being Responded To
    | (U) Affected SOP Class UID
    | (M) Status

    Parameters
    ----------
    event : events.Event
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
    event : events.Event
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
    s.append('{:=^76}'.format(' OUTGOING DIMSE MESSAGE '))
    s.append('Message Type                  : {0!s}'.format('C-STORE RQ'))
    s.append('Message ID                    : {0!s}'.format(cs.MessageID))
    s.append('Affected SOP Class UID        : {0!s}'
             .format(cs.AffectedSOPClassUID.name))
    s.append('Affected SOP Instance UID     : {0!s}'
             .format(cs.AffectedSOPInstanceUID))
    s.append('Data Set                      : {0!s}'.format(dataset))
    s.append('Priority                      : {0!s}'.format(priority))
    s.append('{:=^76}'.format(' END DIMSE MESSAGE '))
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
    event : events.Event
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
    event : events.Event
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

    s = []
    s.append('{:=^76}'.format(' OUTGOING DIMSE MESSAGE '))
    s.append('Message Type                  : {0!s}'.format('C-FIND RQ'))
    s.append('Presentation Context ID       : {0!s}'
             .format(msg.context_id))
    s.append('Message ID                    : {0!s}'.format(cs.MessageID))
    s.append('Affected SOP Class UID        : {0!s}'
             .format(cs.AffectedSOPClassUID.name))
    s.append('Identifier                    : {0!s}'.format(dataset))
    s.append('Priority                      : {0!s}'.format(priority))
    s.append('{:=^76}'.format(' END DIMSE MESSAGE '))

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
    event : events.Event
        The evt.EVT_DIMSE_SENT event that occurred.
    """
    msg = event.message
    cs = msg.command_set

    dataset = 'None'
    if msg.data_set and msg.data_set.getvalue() != b'':
        dataset = 'Present'

    s = []
    s.append('{:=^76}'.format(' OUTGOING DIMSE MESSAGE '))
    s.append('Message Type                  : {0!s}'.format('C-FIND RSP'))
    s.append('Message ID Being Responded To : {0!s}'
             .format(cs.MessageIDBeingRespondedTo))
    if 'AffectedSOPClassUID' in cs:
        s.append('Affected SOP Class UID        : {0!s}'
                 .format(cs.AffectedSOPClassUID.name))
    s.append('Identifier                    : {0!s}'.format(dataset))
    s.append('Status                        : 0x{0:04X}'.format(cs.Status))
    s.append('{:=^76}'.format(' END DIMSE MESSAGE '))

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
    event : events.Event
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

    s = []
    s.append('{:=^76}'.format(' OUTGOING DIMSE MESSAGE '))
    s.append('Message Type                  : {0!s}'.format('C-GET RQ'))
    s.append('Message ID                    : {0!s}'.format(cs.MessageID))
    s.append('Affected SOP Class UID        : {0!s}'
             .format(cs.AffectedSOPClassUID.name))
    s.append('Identifier                    : {0!s}'.format(dataset))
    s.append('Priority                      : {0!s}'.format(priority))
    s.append('{:=^76}'.format(' END DIMSE MESSAGE '))
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
    event : events.Event
        The evt.EVT_DIMSE_SENT event that occurred.
    """
    msg = event.message
    cs = msg.command_set

    dataset = 'None'
    if msg.data_set and msg.data_set.getvalue() != b'':
        dataset = 'Present'

    affected_sop = getattr(cs, 'AffectedSOPClassUID', 'None')

    s = []
    s.append('{:=^76}'.format(' OUTGOING DIMSE MESSAGE '))
    s.append('Message Type                  : {0!s}'.format('C-GET RSP'))
    s.append('Message ID Being Responded To : {0!s}'
             .format(cs.MessageIDBeingRespondedTo))
    if 'AffectedSOPClassUID' in cs:
        s.append('Affected SOP Class UID        : {0!s}'
                 .format(affected_sop))
    s.append('Identifier                    : {0!s}'.format(dataset))
    s.append('Status                        : 0x{0:04X}'.format(cs.Status))
    s.append('{:=^76}'.format(' END DIMSE MESSAGE '))

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
    event : events.Event
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

    s = []
    s.append('{:=^76}'.format(' OUTGOING DIMSE MESSAGE '))
    s.append('Message Type                  : {0!s}'.format('C-MOVE RQ'))
    s.append('Message ID                    : {0!s}'.format(cs.MessageID))
    s.append('Affected SOP Class UID        : {0!s}'
             .format(cs.AffectedSOPClassUID.name))
    s.append('Move Destination              : {0!s}'
             .format(cs.MoveDestination))
    s.append('Identifier                    : {0!s}'.format(identifier))
    s.append('Priority                      : {0!s}'.format(priority))
    s.append('{:=^76}'.format(' END DIMSE MESSAGE '))
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
    event : events.Event
        The evt.EVT_DIMSE_SENT event that occurred.
    """
    msg = event.message
    cs = msg.command_set

    identifier = 'None'
    if msg.data_set and msg.data_set.getvalue() != b'':
        identifier = 'Present'

    s = []
    s.append('{:=^76}'.format(' OUTGOING DIMSE MESSAGE '))
    s.append('Message Type                  : {0!s}'.format('C-MOVE RSP'))
    s.append('Message ID Being Responded To : {0!s}'
             .format(cs.MessageIDBeingRespondedTo))
    if 'AffectedSOPClassUID' in cs:
        s.append('Affected SOP Class UID        : {0!s}'
                 .format(cs.AffectedSOPClassUID.name))
    else:
        s.append('Affected SOP Class UID        : None')
    s.append('Identifier                    : {0!s}'.format(identifier))
    s.append('Status                        : 0x{0:04X}'.format(cs.Status))
    s.append('{:=^76}'.format(' END DIMSE MESSAGE '))

    for line in s:
        LOGGER.debug(line)

def _send_c_cancel_rq(event):
    """Logging handler when a C-CANCEL-RQ is sent.

    Covers C-CANCEL-FIND-RQ, C-CANCEL-GET-RQ and C-CANCEL-MOVE-RQ.

    Parameters
    ----------
    event : events.Event
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
    event : events.Event
        The evt.EVT_DIMSE_RECV event that occurred.
    """
    msg = event.message
    cs = msg.command_set

    LOGGER.info('Received Echo Request (MsgID %s)', cs.MessageID)

    s = []
    s.append('{:=^76}'.format(' INCOMING DIMSE MESSAGE '))
    s.append('Message Type                  : {0!s}'.format('C-ECHO RQ'))
    s.append('Presentation Context ID       : {0!s}'
             .format(msg.context_id))
    s.append('Message ID                    : {0!s}'.format(cs.MessageID))
    s.append('Data Set                      : None')
    s.append('{:=^76}'.format(' END DIMSE MESSAGE '))

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
    event : events.Event
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
        status_str = '0x{0:04X} - Unknown'.format(cs.Status)
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
    event : events.Event
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
    s.append('{:=^76}'.format(' INCOMING DIMSE MESSAGE '))
    s.append('Message Type                  : {0!s}'.format('C-STORE RQ'))
    s.append('Presentation Context ID       : {0!s}'
             .format(msg.context_id))
    s.append('Message ID                    : {0!s}'.format(cs.MessageID))
    s.append('Affected SOP Class UID        : {0!s}'
             .format(cs.AffectedSOPClassUID.name))
    s.append('Affected SOP Instance UID     : {0!s}'
             .format(cs.AffectedSOPInstanceUID))
    if 'MoveOriginatorApplicationEntityTitle' in cs:
        s.append('Move Originator               : {0!s}'
                 .format(cs.MoveOriginatorApplicationEntityTitle))
    s.append('Data Set                      : {0!s}'.format(dataset))
    s.append('Priority                      : {0!s}'.format(priority))
    s.append('{:=^76}'.format(' END DIMSE MESSAGE '))
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
    event : events.Event
        The evt.EVT_DIMSE_RECV event that occurred.
    """
    msg = event.message
    cs = msg.command_set

    # See PS3.4 Annex B.2.3 for Storage Service Class Statuses
    status_str = '0x{0:04X} - Unknown'.format(cs.Status)
    # Try and get the status from the affected SOP class UID
    if 'AffectedSOPClassUID' in cs:
        service_class = uid_to_service_class(cs.AffectedSOPClassUID)
        if cs.Status in service_class.statuses:
            status = service_class.statuses[cs.Status]
            status_str = '0x{0:04X} - {1}'.format(cs.Status, status[0])

    LOGGER.info('Received Store Response (Status: {})'.format(status_str))
    s = []
    s.append('{:=^76}'.format(' INCOMING DIMSE MESSAGE '))
    s.append('Message Type                  : {0!s}'.format('C-STORE RSP'))
    s.append('Presentation Context ID       : {0!s}'
             .format(msg.context_id))
    s.append('Message ID Being Responded To : {0!s}'
             .format(cs.MessageIDBeingRespondedTo))
    if 'AffectedSOPClassUID' in cs:
        s.append('Affected SOP Class UID        : {0!s}'
                 .format(cs.AffectedSOPClassUID.name))
    if 'AffectedSOPInstanceUID' in cs:
        s.append('Affected SOP Instance UID     : {0!s}'
                 .format(cs.AffectedSOPInstanceUID))
    s.append('Status                        : {0!s}'.format(status_str))
    s.append('{:=^76}'.format(' END DIMSE MESSAGE '))

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
    event : events.Event
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
    s.append('{:=^76}'.format(' INCOMING DIMSE MESSAGE '))
    s.append('Message Type                  : {0!s}'.format('C-FIND RQ'))
    s.append('Message ID                    : {0!s}'.format(cs.MessageID))
    s.append('Affected SOP Class UID        : {0!s}'
             .format(cs.AffectedSOPClassUID.name))
    s.append('Identifier                    : {0!s}'.format(dataset))
    s.append('Priority                      : {0!s}'.format(priority))
    s.append('{:=^76}'.format(' END DIMSE MESSAGE '))

    for line in s:
        LOGGER.debug(line)

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
    event : events.Event
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
    s.append('{:=^76}'.format(' INCOMING DIMSE MESSAGE '))
    s.append('Message Type                  : {0!s}'.format('C-FIND RSP'))
    s.append('Message ID Being Responded To : {0!s}'
             .format(cs.MessageIDBeingRespondedTo))
    if 'AffectedSOPClassUID' in cs:
        s.append('Affected SOP Class UID        : {0!s}'
                 .format(cs.AffectedSOPClassUID.name))
    s.append('Identifier                    : {0!s}'.format(dataset))
    s.append('Status                        : 0x{0:04X}'.format(cs.Status))
    s.append('{:=^76}'.format(' END DIMSE MESSAGE '))

    for line in s:
        LOGGER.debug(line)

def _recv_c_cancel_rq(event):
    """Logging handler when a C-CANCEL-RQ is received.

    Covers C-CANCEL-FIND-RQ, C-CANCEL-GET-RQ and C-CANCEL-MOVE-RQ

    Parameters
    ----------
    event : events.Event
        The evt.EVT_DIMSE_RECV event that occurred.
    """
    msg = event.message
    cs = msg.command_set

    s = []
    s.append('{:=^76}'.format(' INCOMING DIMSE MESSAGE '))
    s.append('Message Type                  : {0!s}'.format('C-CANCEL RQ'))
    s.append('Message ID Being Responded To : {0!s}'
             .format(cs.MessageIDBeingRespondedTo))
    s.append('{:=^76}'.format(' END DIMSE MESSAGE '))

    for line in s:
        LOGGER.debug(line)

def _recv_c_get_rq(event):
    """Logging handler when a C-GET-RQ is received.

    **C-GET Request Parameters**

    | (M) Message ID
    | (M) Affected SOP Class UID
    | (M) Priority
    | (M) Identifier

    Parameters
    ----------
    event : events.Event
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
    s.append('{:=^76}'.format(' INCOMING DIMSE MESSAGE '))
    s.append('Message Type                  : {0!s}'.format('C-GET RQ'))
    s.append('Message ID                    : {0!s}'.format(cs.MessageID))
    s.append('Affected SOP Class UID        : {0!s}'
             .format(cs.AffectedSOPClassUID.name))
    s.append('Identifier                    : {0!s}'.format(dataset))
    s.append('Priority                      : {0!s}'.format(priority))
    s.append('{:=^76}'.format(' END DIMSE MESSAGE '))

    for line in s:
        LOGGER.debug(line)

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
    event : events.Event
        The evt.EVT_DIMSE_RECV event that occurred.
    """
    msg = event.message
    cs = msg.command_set

    dataset = 'None'
    if msg.data_set and msg.data_set.getvalue() != b'':
        dataset = 'Present'

    s = []
    s.append('{:=^76}'.format(' INCOMING DIMSE MESSAGE '))
    s.append('Message Type                  : {0!s}'.format('C-GET RSP'))
    s.append('Presentation Context ID       : {0!s}'
             .format(msg.context_id))
    s.append('Message ID Being Responded To : {0!s}'
             .format(cs.MessageIDBeingRespondedTo))
    if 'AffectedSOPClassUID' in cs:
        s.append('Affected SOP Class UID        : {0!s}'
                 .format(cs.AffectedSOPClassUID.name))
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
    s.append('Identifier                    : {0!s}'.format(dataset))
    s.append('Status                        : 0x{0:04X}'.format(cs.Status))
    s.append('{:=^76}'.format(' END DIMSE MESSAGE '))

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
    event : events.Event
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
    event : events.Event
        The evt.EVT_DIMSE_RECV event that occurred.
    """
    msg = event.message
    cs = msg.command_set

    identifier = 'None'
    if msg.data_set and msg.data_set.getvalue() != b'':
        identifier = 'Present'

    s = []
    s.append('{:=^76}'.format(' INCOMING DIMSE MESSAGE '))
    s.append('Message Type                  : {0!s}'.format('C-MOVE RSP'))
    s.append('Message ID Being Responded To : {0!s}'
             .format(cs.MessageIDBeingRespondedTo))
    if 'AffectedSOPClassUID' in cs:
        s.append('Affected SOP Class UID        : {0!s}'
                 .format(cs.AffectedSOPClassUID.name))
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
    s.append('Status                        : 0x{0:04X}'.format(cs.Status))
    s.append('{:=^76}'.format(' END DIMSE MESSAGE '))

    for line in s:
        LOGGER.debug(line)

def _send_n_event_report_rq(event):
    """Logging handler when an N-EVENT-REPORT-RQ is sent.

    Parameters
    ----------
    event : events.Event
        The evt.EVT_DIMSE_SENT event that occurred.
    """
    msg = event.message
    cs = msg.command_set

    evt_info = 'None'
    if msg.data_set and msg.data_set.getvalue() != b'':
        evt_info = 'Present'

    s = []
    s.append('{:=^76}'.format(' OUTGOING DIMSE MESSAGE '))
    s.append('Message Type                  : {0!s}'
             .format('N-EVENT-REPORT RQ'))
    s.append('Message ID                    : {0!s}'.format(cs.MessageID))
    s.append('Affected SOP Class UID        : {0!s}'
             .format(cs.AffectedSOPClassUID.name))
    s.append('Affected SOP Instance UID     : {0!s}'
             .format(cs.AffectedSOPInstanceUID))
    s.append('Event Type ID                 : {0!s}'
             .format(cs.EventTypeID))
    s.append('Event Information             : {0!s}'.format(evt_info))
    s.append('{:=^76}'.format(' END DIMSE MESSAGE '))
    for line in s:
        LOGGER.debug(line)

def _send_n_event_report_rsp(event):
    """Logging handler when an N-EVENT-REPORT-RSP is sent.

    Parameters
    ----------
    event : events.Event
        The evt.EVT_DIMSE_SENT event that occurred.
    """
    msg = event.message
    cs = msg.command_set

    evt_reply = 'None'
    if msg.data_set and msg.data_set.getvalue() != b'':
        evt_reply = 'Present'

    s = []
    s.append('{:=^76}'.format(' OUTGOING DIMSE MESSAGE '))
    s.append('Message Type                  : {0!s}'
             .format('N-EVENT-REPORT RSP'))
    s.append('Message ID Being Responded To : {0!s}'
             .format(cs.MessageIDBeingRespondedTo))
    if 'AffectedSOPClassUID' in cs:
        s.append('Affected SOP Class UID        : {0!s}'
                 .format(cs.AffectedSOPClassUID.name))
    if 'AffectedSOPInstanceUID' in cs:
        s.append('Affected SOP Instance UID     : {0!s}'
                 .format(cs.AffectedSOPInstanceUID))
    if 'EventTypeID' in cs:
        s.append(
            'Event Type ID                 : {!s}'
            .format(cs.EventTypeID)
        )
    s.append('Event Reply                   : {0!s}'.format(evt_reply))
    s.append('Status                        : 0x{0:04X}'.format(cs.Status))
    s.append('{:=^76}'.format(' END DIMSE MESSAGE '))
    for line in s:
        LOGGER.debug(line)

def _send_n_get_rq(event):
    """Logging handler when an N-GET-RQ is sent.

    Parameters
    ----------
    event : events.Event
        The evt.EVT_DIMSE_SENT event that occurred.
    """
    msg = event.message
    cs = msg.command_set

    nr_attr = 'no identifiers'
    if 'AttributeIdentifierList' in cs:
        nr_attr = len(cs.AttributeIdentifierList)
        if nr_attr == 1:
            nr_attr = '{} Attribute Tag'.format(nr_attr)
        else:
            nr_attr = '{} Attribute Tags'.format(nr_attr)

    s = []
    s.append('{:=^76}'.format(' OUTGOING DIMSE MESSAGE '))
    s.append('Message Type                  : {0!s}'.format('N-GET RQ'))
    s.append('Message ID                    : {0!s}'.format(cs.MessageID))
    s.append('Requested SOP Class UID       : {0!s}'
             .format(cs.RequestedSOPClassUID))
    s.append('Requested SOP Instance UID    : {0!s}'
             .format(cs.RequestedSOPInstanceUID))
    s.append('Attribute Identifier List     : ({0!s})'.format(nr_attr))
    s.append('{:=^76}'.format(' END DIMSE MESSAGE '))
    for line in s:
        LOGGER.debug(line)

def _send_n_get_rsp(event):
    """Logging handler when an N-GET-RSP is sent.

    Parameters
    ----------
    event : events.Event
        The evt.EVT_DIMSE_SENT event that occurred.
    """
    msg = event.message
    cs = msg.command_set

    attr_list = 'None'
    if msg.data_set and msg.data_set.getvalue() != b'':
        attr_list = 'Present'

    s = []
    s.append('{:=^76}'.format(' OUTGOING DIMSE MESSAGE '))
    s.append('Message Type                  : {0!s}'.format('N-GET RSP'))
    s.append('Message ID Being Responded To : {0!s}'
             .format(cs.MessageIDBeingRespondedTo))
    if 'AffectedSOPClassUID' in cs:
        s.append('Affected SOP Class UID        : {0!s}'
                 .format(cs.AffectedSOPClassUID.name))
    if 'AffectedSOPInstanceUID' in cs:
        s.append('Affected SOP Instance UID     : {0!s}'
                 .format(cs.AffectedSOPInstanceUID))
    s.append('Attribute List                : {0!s}'.format(attr_list))
    s.append('Status                        : 0x{0:04X}'.format(cs.Status))
    s.append('{:=^76}'.format(' END DIMSE MESSAGE '))
    for line in s:
        LOGGER.debug(line)

def _send_n_set_rq(event):
    """Logging handler when an N-SET-RQ is sent.

    Parameters
    ----------
    event : events.Event
        The evt.EVT_DIMSE_SENT event that occurred.
    """
    msg = event.message
    cs = msg.command_set

    mod_list = 'None'
    if msg.data_set and msg.data_set.getvalue() != b'':
        mod_list = 'Present'

    s = []
    s.append('{:=^76}'.format(' OUTGOING DIMSE MESSAGE '))
    s.append('Message Type                  : {0!s}'.format('N-SET RQ'))
    s.append('Message ID                    : {0!s}'.format(cs.MessageID))
    s.append('Requested SOP Class UID       : {0!s}'
             .format(cs.RequestedSOPClassUID))
    s.append('Requested SOP Instance UID    : {0!s}'
             .format(cs.RequestedSOPInstanceUID))
    s.append('Modification List             : {0!s}'.format(mod_list))
    s.append('{:=^76}'.format(' END DIMSE MESSAGE '))
    for line in s:
        LOGGER.debug(line)

def _send_n_set_rsp(event):
    """Logging handler when an N-SET-RSP is sent.

    Parameters
    ----------
    event : events.Event
        The evt.EVT_DIMSE_SENT event that occurred.
    """
    msg = event.message
    cs = msg.command_set

    attr_list = 'None'
    if msg.data_set and msg.data_set.getvalue() != b'':
        attr_list = 'Present'

    s = []
    s.append('{:=^76}'.format(' OUTGOING DIMSE MESSAGE '))
    s.append('Message Type                  : {0!s}'.format('N-SET RSP'))
    s.append('Message ID Being Responded To : {0!s}'
             .format(cs.MessageIDBeingRespondedTo))
    if 'AffectedSOPClassUID' in cs:
        s.append('Affected SOP Class UID        : {0!s}'
                 .format(cs.AffectedSOPClassUID.name))
    if 'AffectedSOPInstanceUID' in cs:
        s.append('Affected SOP Instance UID     : {0!s}'
                 .format(cs.AffectedSOPInstanceUID))
    s.append('Attribute List                : {0!s}'.format(attr_list))
    s.append('Status                        : 0x{0:04X}'.format(cs.Status))
    s.append('{:=^76}'.format(' END DIMSE MESSAGE '))
    for line in s:
        LOGGER.debug(line)

def _send_n_action_rq(event):
    """Logging handler when an N-ACTION-RQ is sent.

    Parameters
    ----------
    event : events.Event
        The evt.EVT_DIMSE_SENT event that occurred.
    """
    pass

def _send_n_action_rsp(event):
    """Logging handler when an N-ACTION-RSP is sent.

    Parameters
    ----------
    event : events.Event
        The evt.EVT_DIMSE_SENT event that occurred.
    """
    pass

def _send_n_create_rq(event):
    """Logging handler when an N-CREATE-RQ is sent.

    Parameters
    ----------
    event : events.Event
        The evt.EVT_DIMSE_SENT event that occurred.
    """
    pass

def _send_n_create_rsp(event):
    """Logging handler when an N-CREATE-RSP is sent.

    Parameters
    ----------
    event : events.Event
        The evt.EVT_DIMSE_SENT event that occurred.
    """
    pass

def _send_n_delete_rq(event):
    """Logging handler when an N-DELETE-RQ is sent.

    Parameters
    ----------
    event : events.Event
        The evt.EVT_DIMSE_SENT event that occurred.
    """
    msg = event.message
    cs = msg.command_set

    s = []
    s.append('{:=^76}'.format(' OUTGOING DIMSE MESSAGE '))
    s.append('Message Type                  : {0!s}'.format('N-DELETE RQ'))
    s.append('Message ID                    : {0!s}'.format(cs.MessageID))
    s.append('Requested SOP Class UID       : {0!s}'
             .format(cs.RequestedSOPClassUID))
    s.append('Requested SOP Instance UID    : {0!s}'
             .format(cs.RequestedSOPInstanceUID))
    s.append('{:=^76}'.format(' END DIMSE MESSAGE '))
    for line in s:
        LOGGER.debug(line)

def _send_n_delete_rsp(event):
    """Logging handler when an N-DELETE-RSP is sent.

    Parameters
    ----------
    event : events.Event
        The evt.EVT_DIMSE_SENT event that occurred.
    """
    msg = event.message
    cs = msg.command_set

    s = []
    s.append('{:=^76}'.format(' OUTGOING DIMSE MESSAGE '))
    s.append('Message Type                  : {0!s}'.format('N-DELETE RSP'))
    s.append('Message ID Being Responded To : {0!s}'
             .format(cs.MessageIDBeingRespondedTo))
    if 'AffectedSOPClassUID' in cs:
        s.append('Affected SOP Class UID        : {0!s}'
                 .format(cs.AffectedSOPClassUID.name))
    if 'AffectedSOPInstanceUID' in cs:
        s.append('Affected SOP Instance UID     : {0!s}'
                 .format(cs.AffectedSOPInstanceUID))
    s.append('Status                        : 0x{0:04X}'.format(cs.Status))
    s.append('{:=^76}'.format(' END DIMSE MESSAGE '))
    for line in s:
        LOGGER.debug(line)

def _recv_n_event_report_rq(event):
    """Logging handler when an N-EVENT-REPORT-RQ is received.

    Parameters
    ----------
    event : events.Event
        The evt.EVT_DIMSE_RECV event that occurred.
    """
    pass

def _recv_n_event_report_rsp(event):
    """Logging handler when an N-EVENT-REPORT-RSP is received.

    Parameters
    ----------
    event : events.Event
        The evt.EVT_DIMSE_RECV event that occurred.
    """
    pass

def _recv_n_get_rq(event):
    """Logging handler when an N-GET-RQ is received.

    Parameters
    ----------
    event : events.Event
        The evt.EVT_DIMSE_RECV event that occurred.
    """
    pass

def _recv_n_get_rsp(event):
    """Logging handler when an N-GET-RSP is received.

    Parameters
    ----------
    event : events.Event
        The evt.EVT_DIMSE_RECV event that occurred.
    """
    msg = event.message
    cs = msg.command_set

    dataset = 'None'
    if msg.data_set and msg.data_set.getvalue() != b'':
        dataset = 'Present'

    LOGGER.info('Received Get Response')
    s = []
    s.append('{:=^76}'.format(' INCOMING DIMSE MESSAGE '))
    s.append('Message Type                  : {0!s}'.format('N-GET RSP'))
    s.append('Presentation Context ID       : {0!s}'
             .format(msg.context_id))
    s.append('Message ID Being Responded To : {0!s}'
             .format(cs.MessageIDBeingRespondedTo))
    if 'AffectedSOPClassUID' in cs:
        s.append('Affected SOP Class UID        : {0!s}'
                 .format(cs.AffectedSOPClassUID.name))
    if 'AffectedSOPInstanceUID' in cs:
        s.append('Affected SOP Instance UID     : {0!s}'
                 .format(cs.AffectedSOPInstanceUID))
    s.append('Attribute List                : {0!s}'.format(dataset))
    s.append('Status                        : 0x{0:04X}'.format(cs.Status))
    s.append('{:=^76}'.format(' END DIMSE MESSAGE '))

    for line in s:
        LOGGER.debug(line)

def _recv_n_set_rq(event):
    """Logging handler when an N-SET-RQ is received.

    Parameters
    ----------
    event : events.Event
        The evt.EVT_DIMSE_RECV event that occurred.
    """
    pass

def _recv_n_set_rsp(event):
    """Logging handler when an N-SET-RSP is received.

    Parameters
    ----------
    event : events.Event
        The evt.EVT_DIMSE_RECV event that occurred.
    """
    pass

def _recv_n_action_rq(event):
    """Logging handler when an N-ACTION-RQ is received.

    Parameters
    ----------
    event : events.Event
        The evt.EVT_DIMSE_RECV event that occurred.
    """
    pass

def _recv_n_action_rsp(event):
    """Logging handler when an N-ACTION-RSP is received.

    Parameters
    ----------
    event : events.Event
        The evt.EVT_DIMSE_RECV event that occurred.
    """
    pass

def _recv_n_create_rq(event):
    """Logging handler when an N-CREATE-RQ is received.

    Parameters
    ----------
    event : events.Event
        The evt.EVT_DIMSE_RECV event that occurred.
    """
    pass

def _recv_n_create_rsp(event):
    """Logging handler when an N-CREATE-RSP is received.

    Parameters
    ----------
    event : events.Event
        The evt.EVT_DIMSE_RECV event that occurred.
    """
    pass

def _recv_n_delete_rq(event):
    """Logging handler when an N-DELETE-RQ is received.

    Parameters
    ----------
    event : events.Event
        The evt.EVT_DIMSE_RECV event that occurred.
    """
    pass

def _recv_n_delete_rsp(event):
    """Logging handler when an N-DELETE-RSP is received.

    Parameters
    ----------
    event : events.Event
        The evt.EVT_DIMSE_RECV event that occurred.
    """
    pass


# Example handlers used for the documentation
# Intervention event handler documentation
def doc_handle_echo(event, *args):
    """Documentation for handlers bound to ``evt.EVT_C_ECHO``.

    User implementation of this event handler is optional. If a handler is
    not implemented and bound to ``evt.EVT_C_ECHO`` then the C-ECHO request
    will be responded to using a  *Status* value of ``0x0000`` - Success.

    **Event**

    ``evt.EVT_C_ECHO``

    **Supported Service Classes**

    * :dcm:`Verification Service Class<part04/chapter_A.html>`

    **Status**

    Success
      | ``0x0000`` - Success

    Failure
      | ``0x0122`` - SOP Class Not Supported
      | ``0x0210`` - Duplicate Invocation
      | ``0x0211`` - Unrecognised Operation
      | ``0x0212`` - Mistyped Argument

    Parameters
    ----------
    event : events.Event
        The event representing a service class receiving a C-ECHO
        request message. :class:`~pynetdicom.events.Event` attributes are:

        * :attr:`~pynetdicom.events.Event.assoc`: the
          :class:`~pynetdicom.association.Association`
          that is running the DICOM service that received the C-ECHO request.
        * :attr:`~pynetdicom.events.Event.context`: the presentation context
          the request was sent under as a
          :class:`~pynetdicom.presentation.PresentationContextTuple`.
        * :attr:`~pynetdicom.events.Event.event`: the event that occurred as an
          :class:`~pynetdicom.events.InterventionEvent`.
        * :attr:`~pynetdicom.events.Event.request`: the received
          :class:`C-ECHO request <pynetdicom.dimse_primitives.C_ECHO>`
        * :attr:`~pynetdicom.events.Event.timestamp`: the date and time
          that the C-ECHO request was processed by the service as
          :class:`datetime.datetime`.

        :class:`~pynetdicom.events.Event` properties are:

        * :attr:`~pynetdicom.events.Event.message_id`: the C-ECHO request's
          *Message ID* as :class:`int`.
    args
        If the handler was bound to the event using
        ``bind(event, handler, args)`` or by passing
        ``evt_handlers=[(event, handler, args), ...]``, where `args` is a
        :class:`list` then there will be one or more optional extra parameters
        matching the contents of `args`.

    Returns
    -------
    status : pydicom.dataset.Dataset or int
        The status returned to the peer AE in the C-ECHO response. Must be
        a valid C-ECHO status value for the applicable Service Class as
        either an :class:`int` or a :class:`~pydicom.dataset.Dataset` object
        containing (at a minimum) a (0000,0900) *Status* element. If returning
        a :class:`~pydicom.dataset.Dataset` object
        then it may also contain optional elements related to the *Status*
        (as in the DICOM Standard, Part 7,
        :dcm:`Annex C<part07/chapter_C.html>`).

    See Also
    --------
    :meth:`~pynetdicom.association.Association.send_c_echo`
    :class:`~pynetdicom.dimse_primitives.C_ECHO`
    :class:`~pynetdicom.service_class.VerificationServiceClass`

    References
    ----------

    * DICOM Standard, Part 4, :dcm:`Annex A<part04/chapter_A.html>`
    * DICOM Standard, Part 7, Sections
      :dcm:`9.1.5<part07/chapter_9.html#sect_9.1.5>`,
      :dcm:`9.3.5<part07/sect_9.3.5.html>`, and
      :dcm:`Annex C<part07/chapter_C.html>`
    """
    pass

def doc_handle_find(event, *args):
    """Documentation for handlers bound to ``evt.EVT_C_FIND``.

    User implementation of this event handler is required if one or more
    services that use C-FIND are to be supported. If a handler is
    not implemented and bound to ``evt.EVT_C_FIND`` then the C-FIND request
    will be responded to using a  *Status* value of ``0xC311`` - Failure.

    Yields ``(status, identifier)`` pairs, where *status* is either an
    :class:`int` or pydicom :class:`~pydicom.dataset.Dataset` containing a
    (0000,0900) *Status* element and *identifier* is a C-FIND *Identifier*
    :class:`~pydicom.dataset.Dataset`.

    **Event**

    ``evt.EVT_C_FIND``

    **Supported Service Classes**

    * :dcm:`Query/Retrieve Service Class<part04/chapter_C.html>`
    * :dcm:`Basic Worklist Management Service<part04/chapter_K.html>`
    * :dcm:`Relevant Patient Information Query Service<part04/chapter_Q.html>`
    * :dcm:`Hanging Protocol Query/Retrieve Service<part04/chapter_U.html>`
    * :dcm:`Substance Administration Query Service<part04/chapter_V.html>`
    * :dcm:`Color Palette Query/Retrieve Service<part04/chapter_X.html>`
    * :dcm:`Implant Template Query/Retrieve Service<part04/chapter_BB.html>`
    * :dcm:`Unified Procedure Step Service<part04/chapter_CC.html>`
    * :dcm:`Defined Procedure Protocol Query/Retrieve Service
      <part04/chapter_HH.html>`
    * :dcm:`Protocol Approval Query/Retrieve Service<part04/chapter_II.html>`

    **Status**

    Success
      | ``0x0000`` - Success

    Failure
      | ``0xA700`` - Out of resources
      | ``0xA900`` - Identifier does not match SOP class
      | ``0xC000`` to ``0xCFFF`` - Unable to process

    Cancel
      | ``0xFE00`` - Matching terminated due to Cancel request

    Pending
      | ``0xFF00`` - Matches are continuing: current match is supplied and
         any Optional Keys were supported in the same manner as Required
         Keys
      | ``0xFF01`` - Matches are continuing: warning that one or more Optional
        Keys were not supported for existence and/or matching for this
        Identifier

    Parameters
    ----------
    event : events.Event
        The event representing a service class receiving a C-FIND
        request message. :class:`~pynetdicom.events.Event` attributes are:

        * :attr:`~pynetdicom.events.Event.assoc`: the
          :class:`~pynetdicom.association.Association`
          that is running the service that received the C-FIND request.
        * :attr:`~pynetdicom.events.Event.context`: the presentation context
          the request was sent under
          as a :class:`~pynetdicom.presentation.PresentationContextTuple`.
        * :attr:`~pynetdicom.events.Event.event`: the event that occurred as
          :class:`~pynetdicom.events.InterventionEvent`.
        * :attr:`~pynetdicom.events.Event.request`: the received
          :class:`C-FIND request <pynetdicom.dimse_primitives.C_FIND>`
        * :attr:`~pynetdicom.events.Event.timestamp`: the date and time
          that the C-FIND request was processed by the service as
          :class:`datetime.datetime`.

        :class:`~pynetdicom.events.Event` properties are:

        * :attr:`~pynetdicom.events.Event.identifier`: the decoded
          :class:`~pydicom.dataset.Dataset` contained within the
          C-FIND request's *Identifier* parameter. Because *pydicom* uses
          a deferred read when decoding data, if the decode fails the returned
          :class:`~pydicom.dataset.Dataset` will only raise an exception at
          the time of use.
        * :attr:`~pynetdicom.events.Event.is_cancelled`: returns ``True`` if a
          C-CANCEL request has been received, ``False`` otherwise. If a
          C-CANCEL is received then the handler should ``yield (0xFE00, None)``
          and ``return``.
        * :attr:`~pynetdicom.events.Event.message_id`: the C-FIND request's
          *Message ID* as :class:`int`.
    args
        If the handler was bound to the event using
        ``bind(event, handler, args)`` or by passing
        ``evt_handlers=[(event, handler, args), ...]``, where `args` is a
        :class:`list` then there will be one or more optional extra parameters
        matching the contents of `args`.

    Yields
    ------
    status : pydicom.dataset.Dataset or int
        The status returned to the peer AE in the C-FIND response. Must be
        a valid C-FIND status vuale for the applicable Service Class as
        either an :class:`int` or a :class:`~pydicom.dataset.Dataset` object
        containing (at a minimum) a (0000,0900) *Status* element. If returning
        a :class:`~pydicom.dataset.Dataset` object then
        it may also contain optional elements related to the *Status* (as in
        DICOM Standard, Part 7, :dcm:`Annex C<part07/chapter_C.html>`).
    identifier : pydicom.dataset.Dataset or None
        If the status category is 'Pending' then the *Identifier*
        :class:`~pydicom.dataset.Dataset` for a matching SOP Instance. The
        exact requirements for the C-FIND response *Identifier* are Service
        Class specific (see the DICOM Standard, Part 4).

        If the status category is 'Failure' or 'Cancel' then yield ``None``.

        If the status category is 'Success' then yield ``None``, however
        yielding a final 'Success' status is not required and will be ignored
        if necessary.

    See Also
    --------

    :meth:`~pynetdicom.association.Association.send_c_find`
    :class:`~pynetdicom.dimse_primitives.C_FIND`
    :class:`~QueryRetrieveServiceClass`
    :class:`~pynetdicom.service_class.BasicWorklistManagementServiceClass`
    :class:`~pynetdicom.service_class.RelevantPatientInformationQueryServiceClass`
    :class:`~pynetdicom.service_class.SubstanceAdministrationQueryServiceClass`
    :class:`~pynetdicom.service_class.HangingProtocolQueryRetrieveServiceClass`
    :class:`~pynetdicom.service_class.DefinedProcedureProtocolQueryRetrieveServiceClass`
    :class:`~pynetdicom.service_class.ColorPaletteQueryRetrieveServiceClass`
    :class:`~pynetdicom.service_class.ImplantTemplateQueryRetrieveServiceClass`
    :class:`~pynetdicom.service_class_n.UnifiedProcedureStepServiceClass`
    :class:`~pynetdicom.service_class.ProtocolApprovalQueryRetrieveServiceClass`

    References
    ----------

    * DICOM Standard, Part 4, :dcm:`Annex C<part04/chapter_C.html>`
    * DICOM Standard, Part 4, :dcm:`Annex K<part04/chapter_K.html>`
    * DICOM Standard, Part 4, :dcm:`Annex Q<part04/chapter_Q.html>`
    * DICOM Standard, Part 4, :dcm:`Annex U<part04/chapter_U.html>`
    * DICOM Standard, Part 4, :dcm:`Annex V<part04/chapter_V.html>`
    * DICOM Standard, Part 4, :dcm:`Annex X<part04/chapter_X.html>`
    * DICOM Standard, Part 4, :dcm:`Annex BB<part04/chapter_BB.html>`
    * DICOM Standard, Part 4, :dcm:`Annex CC<part04/chapter_CC.html>`
    * DICOM Standard, Part 4, :dcm:`Annex HH<part04/chapter_HH.html>`
    * DICOM Standard, Part 4, :dcm:`Annex II<part04/chapter_II.html>`
    * DICOM Standard, Part 7, Sections
      :dcm:`9.1.2<part07/chapter_9.html#sect_9.1.2>`,
      :dcm:`9.3.2<part07/sect_9.3.2.html>` and
      :dcm:`Annex C<part07/chapter_C.html>`
    """
    pass

def doc_handle_c_get(event, *args):
    """Documentation for handlers bound to ``evt.EVT_C_GET``.

    User implementation of this event handler is required if one or more
    services that use C-GET are to be supported. If a handler is
    not implemented and bound to ``evt.EVT_C_GET`` then the C-GET request
    will be responded to using a  *Status* value of ``0xC411`` - Failure.

    Yields an :class:`int` containing the total number of C-STORE
    sub-operations, then yields ``(status, dataset)`` pairs.

    **Event**

    ``evt.EVT_C_GET``

    **Supported Service Classes**

    * :dcm:`Query/Retrieve Service Class<part04/chapter_C.html>`
    * :dcm:`Hanging Protocol Query/Retrieve Service<part04/chapter_U.html>`
    * :dcm:`Color Palette Query/Retrieve Service<part04/chapter_X.html>`
    * :dcm:`Implant Template Query/Retrieve Service<part04/chapter_BB.html>`
    * :dcm:`Defined Procedure Protocol Query/Retrieve Service
      <part04/chapter_HH.html>`
    * :dcm:`Protocol Approval Query/Retrieve Service<part04/chapter_II.html>`

    **Status**

    Success
      | ``0x0000`` - Sub-operations complete, no failures or warnings

    Failure
      | ``0xA701`` - Out of resources: unable to calculate the number of
        matches
      | ``0xA702`` - Out of resources: unable to perform sub-operations
      | ``0xA900`` - Identifier does not match SOP class
      | ``0xAA00`` - None of the frames requested were found in the SOP
        instance
      | ``0xAA01`` - Unable to create new object for this SOP class
      | ``0xAA02`` - Unable to extract frames
      | ``0xAA03`` - Time-based request received for a non-time-based
        original SOP Instance
      | ``0xAA04`` - Invalid request
      | ``0xC000`` to ``0xCFFF`` - Unable to process

    Cancel
      | ``0xFE00`` - Sub-operations terminated due to Cancel request

    Warning
      | ``0xB000`` - Sub-operations complete, one or more failures or
        warnings

    Pending
      | ``0xFF00`` - Matches are continuing - Current Match is supplied and
        any Optional Keys were supported in the same manner as Required
        Keys

    Parameters
    ----------
    event : events.Event
        The event representing a service class receiving a C-GET
        request message. :class:`~pynetdicom.events.Event` attributes are:

        * :attr:`~pynetdicom.events.Event.assoc`: the
          :class:`~pynetdicom.association.Association`
          that is running the service that received the C-GET request.
        * :attr:`~pynetdicom.events.Event.context`: the presentation context
          the request was sent under
          as a :class:`~pynetdicom.presentation.PresentationContextTuple`.
        * :attr:`~pynetdicom.events.Event.event`: the event that occurred as
          :class:`~pynetdicom.events.InterventionEvent`.
        * :attr:`~pynetdicom.events.Event.request`: the received
          :class:`C-GET request <pynetdicom.dimse_primitives.C_GET>`
        * :attr:`~pynetdicom.events.Event.timestamp`: the date and time
          that the C-GET request was processed by the service as
          :class:`datetime.datetime`.

        :class:`~pynetdicom.events.Event` properties are:

        * :attr:`~pynetdicom.events.Event.identifier`: the decoded
          :class:`~pydicom.dataset.Dataset` contained within the
          C-GET request's *Identifier* parameter. Because *pydicom* uses
          a deferred read when decoding data, if the decode fails the returned
          :class:`~pydicom.dataset.Dataset` will only raise an exception at the
          time of use.
        * :attr:`~pynetdicom.events.Event.is_cancelled`: returns ``True`` if a
          C-CANCEL request has been received, ``False`` otherwise. If a
          C-CANCEL is received then the handler should ``yield (0xFE00, None)``
          and ``return``.
        * :attr:`~pynetdicom.events.Event.message_id`: the C-GET request's
          *Message ID* as :class:`int`.
    args
        If the handler was bound to the event using
        ``bind(event, handler, args)`` or by passing
        ``evt_handlers=[(event, handler, args), ...]``, where `args` is a
        :class:`list` then there will be one or more optional extra parameters
        matching the contents of `args`.

    Yields
    ------
    int
        The first yielded value should be the total number of C-STORE
        sub-operations necessary to complete the C-GET operation. In other
        words, this is the number of matching SOP Instances to be sent to
        the peer.
    status : pydicom.dataset.Dataset or int
        The status returned to the peer AE in the C-GET response. Must be a
        valid C-GET status value for the applicable Service Class as either
        an :class:`int` or a :class:`~pydicom.dataset.Dataset` object
        containing (at a minimum) a (0000,0900) *Status* element. If returning
        a :class:`~pydicom.dataset.Dataset` object then
        it may also contain optional elements related to the *Status* (as in
        DICOM Standard, Part 7, :dcm:`Annex C<part07/chapter_C.html>`).
    dataset : pydicom.dataset.Dataset or None
        If the status category is 'Pending' then yield the
        :class:`~pydicom.dataset.Dataset` to send to the peer via a C-STORE
        sub-operation over the current association.

        If the status category is 'Failed', 'Warning' or 'Cancel' then yield a
        :class:`~pydicom.dataset.Dataset` with a (0008,0058) *Failed SOP
        Instance UID List* element containing a list of the C-STORE
        sub-operation SOP Instance UIDs for which the C-GET operation has
        failed.

        If the status category is 'Success' then yield ``None``, although
        yielding a final 'Success' status is not required and will be ignored
        if necessary.

    See Also
    --------

    :meth:`~pynetdicom.association.Association.send_c_get`
    :class:`~pynetdicom.dimse_primitives.C_GET`
    :class:`~pynetdicom.service_class.QueryRetrieveServiceClass`
    :class:`~pynetdicom.service_class.HangingProtocolQueryRetrieveServiceClass`
    :class:`~pynetdicom.service_class.DefinedProcedureProtocolQueryRetrieveServiceClass`
    :class:`~pynetdicom.service_class.ColorPaletteQueryRetrieveServiceClass`
    :class:`~pynetdicom.service_class.ImplantTemplateQueryRetrieveServiceClass`
    :class:`~pynetdicom.service_class.ProtocolApprovalQueryRetrieveServiceClass`

    References
    ----------

    * DICOM Standard, Part 4, :dcm:`Annex C<part04/chapter_C.html>`
    * DICOM Standard, Part 4, :dcm:`Annex U<part04/chapter_U.html>`
    * DICOM Standard, Part 4, :dcm:`Annex X<part04/chapter_X.html>`
    * DICOM Standard, Part 4, :dcm:`Annex Y<part04/chapter_Y.html>`
    * DICOM Standard, Part 4, :dcm:`Annex Z<part04/chapter_Z.html>`
    * DICOM Standard, Part 4, :dcm:`Annex BB<part04/chapter_BB.html>`
    * DICOM Standard, Part 4, :dcm:`Annex HH<part04/chapter_HH.html>`
    * DICOM Standard, Part 4, :dcm:`Annex II<part04/chapter_II.html>`
    * DICOM Standard, Part 7, Sections
      :dcm:`9.1.3<part07/chapter_9.html#sect_9.1.3>`,
      :dcm:`9.3.3<part07/sect_9.3.3.html>` and
      :dcm:`Annex C<part07/chapter_C.html>`
    """
    pass

def doc_handle_move(event, *args):
    """Documentation for handlers bound to ``evt.EVT_C_MOVE``.

    User implementation of this event handler is required if one or more
    services that use C-MOVE are to be supported. If a handler is
    not implemented and bound to ``evt.EVT_C_MOVE`` then the C-MOVE request
    will be responded to using a  *Status* value of ``0xC511`` - Failure.

    The first yield should be the ``(addr, port)`` of the move destination,
    however you may instead yield ``(addr, port, kwargs)``, where ``kwargs``
    is a :class:`dict` containing keyword parameters that will be passed
    to :meth:`AE.associate()<pynetdicom.ae.ApplicationEntity.associate>`. This
    allows you to customise the presentation contexts requested by the
    association with the Storage SCP via the `contexts` keyword parameter.

    The second yield should be the number of required C-STORE sub-operations
    as an :class:`int`, and the remaining yields the ``(status, dataset)``
    pairs.

    Matching SOP Instances will be sent to the move destination Storage SCP
    over a new association. If the move destination is unknown then the
    SCP will send a response with a 'Failure' status of ``0xA801`` 'Move
    Destination Unknown'.

    .. versionchanged:: 1.5

        Added the ability to yield either ``(addr, port)`` or
        ``(addr, port, kwargs)``

    **Event**

    ``evt.EVT_C_MOVE``

    **Supported Service Classes**

    * :dcm:`Query/Retrieve Service Class<part04/chapter_C.html>`
    * :dcm:`Hanging Protocol Query/Retrieve Service<part04/chapter_U.html>`
    * :dcm:`Color Palette Query/Retrieve Service<part04/chapter_X.html>`
    * :dcm:`Implant Template Query/Retrieve Service<part04/chapter_BB.html>`
    * :dcm:`Defined Procedure Protocol Query/Retrieve Service
      <part04/chapter_HH.html>`
    * :dcm:`Protocol Approval Query/Retrieve Service<part04/chapter_II.html>`

    **Status**

    Success
      | ``0x0000`` - Sub-operations complete, no failures

    Pending
      | ``0xFF00`` - Sub-operations are continuing

    Cancel
      | ``0xFE00`` - Sub-operations terminated due to Cancel indication

    Failure
      | ``0x0122`` - SOP class not supported
      | ``0x0124`` - Not authorised
      | ``0x0210`` - Duplicate invocation
      | ``0x0211`` - Unrecognised operation
      | ``0x0212`` - Mistyped argument
      | ``0xA701`` - Out of resources: unable to calculate number of matches
      | ``0xA702`` - Out of resources: unable to perform sub-operations
      | ``0xA801`` - Move destination unknown
      | ``0xA900`` - Identifier does not match SOP class
      | ``0xAA00`` - None of the frames requested were found in the SOP
        instance
      | ``0xAA01`` - Unable to create new object for this SOP class
      | ``0xAA02`` - Unable to extract frames
      | ``0xAA03`` - Time-based request received for a non-time-based
        original SOP Instance
      | ``0xAA04`` - Invalid request
      | ``0xC000`` to ``0xCFFF`` - Unable to process


    Parameters
    ----------
    event : events.Event
        The event representing a service class receiving a C-MOVE
        request message. :class:`~pynetdicom.events.Event` attributes are:

        * :attr:`~pynetdicom.events.Event.assoc`: the
          :class:`~pynetdicom.association.Association`
          that is running the service that received the C-MOVE request.
        * :attr:`~pynetdicom.events.Event.context`: the presentation context
          the request was sent under
          as a :class:`~pynetdicom.presentation.PresentationContextTuple`.
        * :attr:`~pynetdicom.events.Event.event`: the event that occurred as
          :class:`~pynetdicom.events.InterventionEvent`.
        * :attr:`~pynetdicom.events.Event.request`: the received
          :class:`C-MOVE request <pynetdicom.dimse_primitives.C_MOVE>`
        * :attr:`~pynetdicom.events.Event.timestamp`: the date and time
          that the C-MOVE request was processed by the service as
          :class:`datetime.datetime`.

        :class:`~pynetdicom.events.Event` properties are:

        * :attr:`~pynetdicom.events.Event.identifier`: the decoded
          :class:`~pydicom.dataset.Dataset` contained within the
          C-MOVE request's *Identifier* parameter. Because *pydicom* uses
          a deferred read when decoding data, if the decode fails the returned
          :class:`~pydicom.dataset.Dataset` will only raise an exception at the
          time of use.
        * :attr:`~pynetdicom.events.Event.is_cancelled`: returns ``True`` if a
          C-CANCEL request has been received, ``False`` otherwise. If a
          C-CANCEL is received then the handler should yield a
          ``(0xFE00, None)`` status/dataset pair and ``return``.
        * :attr:`~pynetdicom.events.Event.message_id`: the C-MOVE request's
          *Message ID* as :class:`int`.
        * :attr:`~pynetdicom.events.Event.move_destination`: the C-MOVE
          request's *Move Destination* value as :class:`bytes`.
    args
        If the handler was bound to the event using
        ``bind(event, handler, args)`` or by passing
        ``evt_handlers=[(event, handler, args), ...]``, where `args` is a
        :class:`list` then there will be one or more optional extra parameters
        matching the contents of `args`.

    Yields
    ------
    addr, port or addr, port, kwargs : str, int, (dict) or None, None, (None)
        The first yield should be the (TCP/IP address, port number) of the
        destination AE (if known) or ``(None, None)`` if unknown. If
        ``(None, None)`` is yielded then the SCP will send a C-MOVE
        response with a 'Failure' Status of ``0xA801`` (move destination
        unknown), in which case nothing more needs to be yielded. You may
        instead yield ``(addr, port, kwargs)``, where ``kwargs`` is
        a :class:`dict` containing keyword parameters to pass to
        :meth:`AE.associate()<pynetdicom.ae.ApplicationEntity.associate>`
        when the new association with the Storage SCP is initiated.
    int
        The second yield should be the number of C-STORE sub-operations
        required to complete the C-MOVE operation. In other words, this is
        the number of matching SOP Instances to be sent to the peer.
    status : pydicom.dataset.Dataset or int
        The status returned to the peer AE in the C-MOVE response. Must be
        a valid C-MOVE status value for the applicable Service Class as
        either an :class:`int` or a :class:`~pydicom.dataset.Dataset`
        containing (at a minimum) a (0000,0900) *Status* element. If returning
        a :class:`~pydicom.dataset.Dataset` then it may also contain optional
        elements related to the *Status* (as in
        DICOM Standard, Part 7, :dcm:`Annex C<part07/chapter_C.html>`).
    dataset : pydicom.dataset.Dataset or None
        If the status is 'Pending' then yield the
        :class:`~pydicom.dataset.Dataset` to send to the peer via a C-STORE
        sub-operation over a new association.

        If the status is 'Failed', 'Warning' or 'Cancel' then yield a
        :class:`~pydicom.dataset.Dataset` with a (0008,0058) *Failed SOP
        Instance UID List* element containing the list of the C-STORE
        sub-operation SOP Instance UIDs for which the C-MOVE operation has
        failed.

        If the status is 'Success' then yield ``None``, although yielding a
        final 'Success' status is not required and will be ignored if
        necessary.

    See Also
    --------

    :meth:`~pynetdicom.association.Association.send_c_move`
    :class:`~pynetdicom.dimse_primitives.C_MOVE`
    :class:`~pynetdicom.service_class.QueryRetrieveServiceClass`
    :class:`~pynetdicom.service_class.HangingProtocolQueryRetrieveServiceClass`
    :class:`~pynetdicom.service_class.DefinedProcedureProtocolQueryRetrieveServiceClass`
    :class:`~pynetdicom.service_class.ColorPaletteQueryRetrieveServiceClass`
    :class:`~pynetdicom.service_class.ImplantTemplateQueryRetrieveServiceClass`
    :class:`~pynetdicom.service_class.ProtocolApprovalQueryRetrieveServiceClass`

    References
    ----------

    * DICOM Standard, Part 4, :dcm:`Annex C<part04/chapter_C.html>`
    * DICOM Standard, Part 4, :dcm:`Annex U<part04/chapter_U.html>`
    * DICOM Standard, Part 4, :dcm:`Annex X<part04/chapter_X.html>`
    * DICOM Standard, Part 4, :dcm:`Annex Y<part04/chapter_Y.html>`
    * DICOM Standard, Part 4, :dcm:`Annex BB<part04/chapter_BB.html>`
    * DICOM Standard, Part 4, :dcm:`Annex HH<part04/chapter_HH.html>`
    * DICOM Standard, Part 4, :dcm:`Annex II<part04/chapter_II.html>`
    * DICOM Standard, Part 7, Sections
      :dcm:`9.1.4<part07/chapter_9.html#sect_9.1.4>`,
      :dcm:`9.3.4<part07/sect_9.3.4.html>` and
      :dcm:`Annex C<part07/chapter_C.html>`
    """
    pass

def doc_handle_store(event, *args):
    """Documentation for handlers bound to ``evt.EVT_C_STORE``.

    User implementation of this event handler is required if one or more
    services that use C-STORE are to be supported. If a handler is
    not implemented and bound to ``evt.EVT_C_STORE`` then the C-STORE request
    will be responded to using a  *Status* value of ``0xC211`` - Failure.

    If the user is storing the dataset in the
    :dcm:`DICOM File Format<part10/chapter_7.html>` then they are
    responsible for adding the
    :dcm:`File Meta Information<part10/chapter_7.html#sect_7.1>`.

    **Event**

    ``evt.EVT_C_STORE``

    **Supported Service Classes**

    * :dcm:`Storage Service Class<part04/chapter_B.html>`
    * :dcm:`Non-Patient Object Storage Service Class<part04/chapter_GG.html>`

    **Status**

    Success
      | ``0x0000`` - Success

    Warning
      | ``0xB000`` - Coercion of data elements
      | ``0xB006`` - Elements discarded
      | ``0xB007`` - Dataset does not match SOP class

    Failure
      | ``0x0117`` - Invalid SOP instance
      | ``0x0122`` - SOP class not supported
      | ``0x0124`` - Not authorised
      | ``0x0210`` - Duplicate invocation
      | ``0x0211`` - Unrecognised operation
      | ``0x0212`` - Mistyped argument
      | ``0xA700`` to ``0xA7FF`` - Out of resources
      | ``0xA900`` to ``0xA9FF`` - Dataset does not match SOP class
      | ``0xC000`` to ``0xCFFF`` - Cannot understand

    Parameters
    ----------
    event : events.Event
        The event representing a service class receiving a C-STORE
        request message. :class:`~pynetdicom.events.Event` attributes are:

        * :attr:`~pynetdicom.events.Event.assoc`: the
          :class:`~pynetdicom.association.Association`
          that is running the service that received the C-STORE request.
        * :attr:`~pynetdicom.events.Event.context`: the presentation context
          the request was sent under
          as a :class:`~pynetdicom.presentation.PresentationContextTuple`.
        * :attr:`~pynetdicom.events.Event.event`: the event that occurred as
          :class:`~pynetdicom.events.InterventionEvent`.
        * :attr:`~pynetdicom.events.Event.request`: the received
          :class:`C-STORE request <pynetdicom.dimse_primitives.C_STORE>`
        * :attr:`~pynetdicom.events.Event.timestamp`: the date and time
          that the C-STORE request was processed by the service as
          :class:`datetime.datetime`.

        :class:`~pynetdicom.events.Event` properties are:

        * :attr:`~pynetdicom.events.Event.dataset`: the decoded
          :class:`~pydicom.dataset.Dataset` contained within the
          C-STORE request's *Data Set* parameter. Because *pydicom* uses
          a deferred read when decoding data, if the decode fails the returned
          :class:`~pydicom.dataset.Dataset` will only raise an exception at the
          time of use.
        * :attr:`~pynetdicom.events.Event.file_meta`: a
          :class:`~pydicom.dataset.Dataset` containing DICOM
          conformant File Meta Information that can be used with the decoded
          dataset when saving to file: ``event.dataset.file_meta =
          event.file_meta``.
        * :attr:`~pynetdicom.events.Event.message_id`: the C-STORE request's
          *Message ID* as :class:`int`.
    args
        If the handler was bound to the event using
        ``bind(event, handler, args)`` or by passing
        ``evt_handlers=[(event, handler, args), ...]``, where `args` is a
        :class:`list` then there will be one or more optional extra parameters
        matching the contents of `args`.

    Returns
    -------
    status : pydicom.dataset.Dataset or int
        The status returned to the requesting AE in the C-STORE response. Must
        be a valid C-STORE status value for the applicable Service Class as
        either an :class:`int` or a :class:`~pydicom.dataset.Dataset` object
        containing (at a minimum) a (0000,0900) *Status* element. If returning
        a :class:`~pydicom.dataset.Dataset` object then it may also contain
        optional elements related to the *Status* (as in the DICOM Standard,
        Part 7, :dcm:`Annex C<part07/chapter_C.html>`).

    Raises
    ------
    NotImplementedError
        If the handler has not been implemented and bound to
        ``evt.EVT_C_STORE`` by the user.

    See Also
    --------

    :meth:`~pynetdicom.association.Association.send_c_store`
    :class:`~pynetdicom.dimse_primitives.C_STORE`
    :class:`~pynetdicom.service_class.StorageServiceClass`
    :class:`~pynetdicom.service_class.NonPatientObjectStorageServiceClass`

    References
    ----------

    * DICOM Standard, Part 4, :dcm:`Annex B<part04/chapter_B.html>`
    * DICOM Standard, Part 4, :dcm:`Annex GG<part04/chapter_GG.html>`
    * DICOM Standard, Part 7, Sections
      :dcm:`9.1.1<part07/chapter_9.html#sect_9.1.1>`,
      :dcm:`9.3.1<part07/sect_9.3.html#sect_9.3.1>` and
      :dcm:`Annex C<part07/chapter_C.html>`
    """
    pass

def doc_handle_action(event, *args):
    """Documentation for handlers bound to ``evt.EVT_N_ACTION``.

    User implementation of this event handler is required if one or more
    services that use N-ACTION are to be supported. If a handler is
    not implemented and bound to ``evt.EVT_N_ACTION`` then the N-ACTION request
    will be responded to using a  *Status* value of ``0x0110`` - Processing
    failure.

    **Event**

    ``evt.EVT_N_ACTION``

    **Supported Service Classes**

    * :dcm:`Print Management<part04/chapter_H.html>`
    * :dcm:`Storage Commitment<part04/chapter_J.html>`
    * :dcm:`Application Event Logging<part04/chapter_P.html>`
    * :dcm:`Media Creation Management<part04/chapter_S.html>`
    * :dcm:`Unified Procedure Step<part04/chapter_CC.html>`
    * :dcm:`RT Machine Verification<part04/chapter_DD.html>`

    **Status**

    Success
      | ``0x0000`` - Success

    Failure
      | ``0x0112`` - No such SOP Instance
      | ``0x0114`` - No such argument
      | ``0x0115`` - Invalid argument value
      | ``0x0117`` - Invalid object instance
      | ``0x0118`` - No such SOP Class
      | ``0x0119`` - Class-Instance conflict
      | ``0x0123`` - No such action
      | ``0x0124`` - Refused: not authorised
      | ``0x0210`` - Duplicate invocation
      | ``0x0211`` - Unrecognised operation
      | ``0x0212`` - Mistyped argument
      | ``0x0213`` - Resource limitation
      | ``0xC101`` - Procedural Logging not available for specified Study
        Instance UID
      | ``0xC102`` - Event Information does not match Template
      | ``0xC103`` - Cannot match event to a current study
      | ``0xC104`` - IDs inconsistent in matching a current study; Event not
        logged
      | ``0xC10E`` - Operator not authorised to add entry to Medication
        Administration Record
      | ``0xC110`` - Patient cannot be identified from Patient ID (0010,0020)
        or Admission ID (0038,0010)
      | ``0xC111`` - Update of Medication Administration Record failed
      | ``0xC112`` - Machine Verification requested instance not found
      | ``0xC300`` - The UPS may no longer be updated
      | ``0xC301`` - The correct Transaction UID was not provided
      | ``0xC302`` - The UPS is already IN PROGRESS
      | ``0xC303`` - The UPS may only become SCHEDULED via N-CREATE, not N-SET
        or N-ACTION
      | ``0xC304`` - The UPS has not met final state requirements for the
        requested state change
      | ``0xC307`` - Specified SOP Instance UID does not exist or is not a UPS
        Instance managed by this SCP
      | ``0xC308`` - Receiving AE-TITLE is Unknown to this SCP
      | ``0xC310`` - The UPS is not yet in the IN PROGRESS state
      | ``0xC311`` - The UPS is already COMPLETED
      | ``0xC312`` - The performer cannot be contacted
      | ``0xC313`` - Performer chooses not to cancel
      | ``0xC314`` - Specified action not appropriate for specified instance
      | ``0xC315`` - SCP does not support Event Reports
      | ``0xC600`` - Film Session SOP Instance hierarchy does not contain Film
        Box SOP Instances
      | ``0xC601`` - Unable to create Print Job SOP Instance; print queue is
        full
      | ``0xC602`` - Unable to create Print Job SOP Instance; print queue is
        full
      | ``0xC603`` - Image size is larger than image box size
      | ``0xC613`` - Combined Print Image size is larger than Image Box size

    Warning
      | ``0xB101`` - Specified Synchronisation Frame of Reference UID does not
        match SOP Synchronisation Frame of Reference
      | ``0xB102`` - Study Instance UID coercion; Event logged under a
        different Study Instance UID
      | ``0xB104`` - IDs inconsistent in matching a current study; Event logged
      | ``0xB301`` - Deletion Lock not granted
      | ``0xB304`` - The UPS is already in the requested state of CANCELED
      | ``0xB306`` - The UPS is already in the requested state of COMPLETED
      | ``0xB601`` - Film session printing (collation) is not supported
      | ``0xB602`` - Film Session SOP Instance hierarchy does not contain
        Image Box SOP Instances (empty page)
      | ``0xB603`` - Film Box SOP Instance hierarchy does not contain Image
        Box SOP Instances (empty page)
      | ``0xB604`` - Image size is larger than Image Box size, the image has
        been demagnified
      | ``0xB609`` - Image size is larger than Image Box size, the image has
        been cropped to fit.
      | ``0xB60A`` - Image size or Combined Print Image size is larger than the
        Image Box size. Image or Combined Print Image has been decimated to
        fit.

    Parameters
    ----------
    event : events.Event
        The event representing a service class receiving a N-ACTION
        request message. :class:`~pynetdicom.events.Event` attributes are:

        * :attr:`~pynetdicom.events.Event.assoc`: the
          :class:`~pynetdicom.association.Association`
          that is running the service that received the N-ACTION request.
        * :attr:`~pynetdicom.events.Event.context`: the presentation context
          the request was sent under
          as a :class:`~pynetdicom.presentation.PresentationContextTuple`.
        * :attr:`~pynetdicom.events.Event.event`: the event that occurred as
          :class:`~pynetdicom.events.InterventionEvent`.
        * :attr:`~pynetdicom.events.Event.request`: the received
          :class:`N-ACTION request <pynetdicom.dimse_primitives.N_ACTION>`
        * :attr:`~pynetdicom.events.Event.timestamp`: the date and time
          that the N-ACTION request was processed by the service as
          :class:`datetime.datetime`.

        :class:`~pynetdicom.events.Event` properties are:

        * :attr:`~pynetdicom.events.Event.action_information`: the decoded
          :class:`~pydicom.dataset.Dataset` contained within the
          N-ACTION request's *Action Information* parameter. Because *pydicom*
          uses a deferred read when decoding data, if the decode fails the
          returned :class:`~pydicom.dataset.Dataset` will only raise an
          exception at the time of use.
        * :attr:`~pynetdicom.events.Event.action_type`: the N-ACTION request's
          *Action Type ID* as :class:`int`.
        * :attr:`~pynetdicom.events.Event.message_id`: the N-ACTION request's
          *Message ID* as :class:`int`.
    args
        If the handler was bound to the event using
        ``bind(event, handler, args)`` or by passing
        ``evt_handlers=[(event, handler, args), ...]``, where `args` is a
        :class:`list` then there will be one or more optional extra parameters
        matching the contents of `args`.

    Returns
    -------
    status : pydicom.dataset.Dataset or int
        The status returned to the peer AE in the N-ACTION response. Must be a
        valid N-ACTION status value for the applicable Service Class as either
        an :class:`int` or a :class:`~pydicom.dataset.Dataset` object
        containing (at a minimum) a (0000,0900) *Status* element. If returning
        a :class:`~pydicom.dataset.Dataset` object then
        it may also contain optional elements related to the *Status* (as in
        DICOM Standard, Part 7, :dcm:`Annex C<part07/chapter_C.html>`).
    dataset : pydicom.dataset.Dataset or None
        If the status category is 'Success' or 'Warning' then a
        :class:`~pydicom.dataset.Dataset` containing elements for the
        response's *Action Reply* conformant to the specifications in the
        corresponding Service Class.

        If the status category is not 'Success' or 'Warning' then ``None``.

    Raises
    ------
    NotImplementedError
        If the handler has not been implemented and bound to
        ``evt.EVT_N_ACTION`` by the user.

    See Also
    --------

    :meth:`~pynetdicom.association.Association.send_n_action`
    :class:`~pynetdicom.dimse_primitives.N_ACTION`
    :class:`~pynetdicom.service_class_n.ApplicationEventLoggingServiceClass`
    :class:`~pynetdicom.service_class_n.MediaCreationManagementServiceClass`
    :class:`~pynetdicom.service_class_n.PrintManagementServiceClass`
    :class:`~pynetdicom.service_class_n.RTMachineVerificationServiceClass`
    :class:`~pynetdicom.service_class_n.StorageCommitmentServiceClass`
    :class:`~pynetdicom.service_class_n.UnifiedProcedureStepServiceClass`

    References
    ----------

    * DICOM Standard, Part 4, :dcm:`Annex H<part04/chapter_H.html>`
    * DICOM Standard, Part 4, :dcm:`Annex J<part04/chapter_J.html>`
    * DICOM Standard, Part 4, :dcm:`Annex P<part04/chapter_P.html>`
    * DICOM Standard, Part 4, :dcm:`Annex S<part04/chapter_S.html>`
    * DICOM Standard, Part 4, :dcm:`Annex CC<part04/chapter_CC.html>`
    * DICOM Standard, Part 4, :dcm:`Annex DD<part04/chapter_DD.html>`
    * DICOM Standard, Part 7, Sections
      :dcm:`10.1.4<part07/chapter_10.html#sect_10.1.4>`,
      :dcm:`10.3.4<part07/sect_10.3.4.html>` and
      :dcm:`Annex C<part07/chapter_C.html>`
    """
    pass

def doc_handle_create(event, *args):
    """Documentation for handlers bound to ``evt.EVT_N_CREATE``.

    User implementation of this event handler is required if one or more
    services that use N-CREATE are to be supported. If a handler is
    not implemented and bound to ``evt.EVT_N_CREATE`` then the N-CREATE request
    will be responded to using a  *Status* value of ``0x0110`` - Processing
    Failure.

    Management of the SOP Instances created in response to an N-CREATE request
    is the responsibility of the user.

    **Event**

    ``evt.EVT_N_CREATE``

    **Supported Service Classes**

    * :dcm:`Procedure Step<part04/chapter_F.html>`
    * :dcm:`Print Management<part04/chapter_H.html>`
    * :dcm:`Instance Availability Notification<part04/chapter_R.html>`
    * :dcm:`Media Creation Management<part04/chapter_S.html>`
    * :dcm:`Unified Procedure Step<part04/chapter_CC.html>`
    * :dcm:`RT Machine Verification<part04/chapter_DD.html>`

    **Status**

    Success
      | ``0x0000`` - Success

    Failure
      | ``0x0105`` - No such attribute
      | ``0x0106`` - Invalid attribute value
      | ``0x0107`` - Attribute list error
      | ``0x0110`` - Processing failure
      | ``0x0111`` - Duplicate SOP Instance
      | ``0x0116`` - Attribute value out of range
      | ``0x0117`` - Invalid object instance
      | ``0x0118`` - No such SOP Class
      | ``0x0120`` - Missing attribute
      | ``0x0121`` - Missing attribute value
      | ``0x0124`` - Refused: not authorised
      | ``0x0210`` - Duplicate invocation
      | ``0x0211`` - Unrecognised operation
      | ``0x0212`` - Mistyped argument
      | ``0x0213`` - Resource limitation
      | ``0xA510`` - Failed: an initiate media creation action has already been
        received for this SOP Instance
      | ``0xC221`` - The Referenced Fraction Group Number does not exist in the
        referenced plan
      | ``0xC222`` - No beams exist within the referenced fraction group
      | ``0xC223`` - SCU already verifying and cannot currently process this
        request
      | ``0xC227`` - No such object instance - Referenced RT Plan not found
      | ``0xC309`` - The provided value of UPS State was not 'SCHEDULED'
      | ``0xC616`` - There is an existing Film Box that has not been
        printed and N-ACTION at the Film Session level is not supported.
        A new Film Box will not be created when a previous Film Box has
        not been printed

    Warning
      | ``0xB300`` - THE UPS was created with modifications
      | ``0xB600`` - Memory allocation not supported
      | ``0xB605`` - Requested Min Density or Max Density outside of
        printer's operating range. The printer will use its respective
        minimum or maximum density value instead

    Parameters
    ----------
    event : events.Event
        The event representing a service class receiving a N-CREATE
        request message. :class:`~pynetdicom.events.Event` attributes are:

        * :attr:`~pynetdicom.events.Event.assoc`: the
          :class:`~pynetdicom.association.Association`
          that is running the service that received the N-CREATE request.
        * :attr:`~pynetdicom.events.Event.context`: the presentation context
          the request was sent under
          as a :class:`~pynetdicom.presentation.PresentationContextTuple`.
        * :attr:`~pynetdicom.events.Event.event`: the event that occurred as
          :class:`~pynetdicom.events.InterventionEvent`.
        * :attr:`~pynetdicom.events.Event.request`: the received
          :class:`N-CREATE request <pynetdicom.dimse_primitives.N_CREATE>`
        * :attr:`~pynetdicom.events.Event.timestamp`: the date and time
          that the N-CREATE request was processed by the service as
          :class:`datetime.datetime`.

        :class:`~pynetdicom.events.Event` properties are:

        * :attr:`~pynetdicom.events.Event.attribute_list`: the decoded
          :class:`~pydicom.dataset.Dataset` contained within the
          N-CREATE request's *Attribute List* parameter. Because *pydicom*
          uses a deferred read when decoding data, if the decode fails the
          returned :class:`~pydicom.dataset.Dataset` will only raise an
          exception at the time of use.
        * :attr:`~pynetdicom.events.Event.message_id`: the N-CREATE request's
          *Message ID* as :class:`int`.
    args
        If the handler was bound to the event using
        ``bind(event, handler, args)`` or by passing
        ``evt_handlers=[(event, handler, args), ...]``, where `args` is a
        :class:`list` then there will be one or more optional extra parameters
        matching the contents of `args`.

    Returns
    -------
    status : pydicom.dataset.Dataset or int
        The status returned to the peer AE in the N-CREATE response. Must be a
        valid N-CREATE status value for the applicable Service Class as either
        an :class:`int` or a :class:`~pydicom.dataset.Dataset` object
        containing (at a minimum) a (0000,0900) *Status* element. If returning
        a :class:`~pydicom.dataset.Dataset` object then
        it may also contain optional elements related to the *Status* (as in
        DICOM Standard, Part 7, :dcm:`Annex C<part07/chapter_C.html>`).
    dataset : pydicom.dataset.Dataset or None
        If the status category is 'Success' or 'Warning' then a
        :class:`~pydicom.dataset.Dataset` containing elements of the
        response's *Attribute List* conformant to the specifications in the
        corresponding Service Class.

        If the status category is not 'Success' or 'Warning' then ``None``.

    Raises
    ------
    NotImplementedError
        If the handler has not been implemented and bound to
        ``evt.EVT_N_CREATE`` by the user.

    See Also
    --------

    :meth:`~pynetdicom.association.Association.send_n_create`
    :class:`~pynetdicom.dimse_primitives.N_CREATE`
    :class:`~pynetdicom.service_class_n.InstanceAvailabilityNotificationServiceClass`
    :class:`~pynetdicom.service_class_n.MediaCreationManagementServiceClass`
    :class:`~pynetdicom.service_class_n.PrintManagementServiceClass`
    :class:`~pynetdicom.service_class_n.ProcedureStepServiceClass`
    :class:`~pynetdicom.service_class_n.RTMachineVerificationServiceClass`
    :class:`~pynetdicom.service_class_n.UnifiedProcedureStepServiceClass`

    References
    ----------

    * DICOM Standard, Part 4, :dcm:`Annex F<part04/chapter_F.html>`
    * DICOM Standard, Part 4, :dcm:`Annex H<part04/chapter_H.html>`
    * DICOM Standard, Part 4, :dcm:`Annex R<part04/chapter_R.html>`
    * DICOM Standard, Part 4, :dcm:`Annex S<part04/chapter_S.html>`
    * DICOM Standard, Part 4, :dcm:`Annex CC<part04/chapter_CC.html>`
    * DICOM Standard, Part 4, :dcm:`Annex DD<part04/chapter_DD.html>`
    * DICOM Standard, Part 7, Sections
      :dcm:`10.1.5<part07/chapter_10.html#sect_10.1.5>`,
      :dcm:`10.3.5<part07/sect_10.3.5.html>`
      and :dcm:`Annex C<part07/chapter_C.html>`
    """
    pass

def doc_handle_delete(event, *args):
    """Documentation for handlers bound to ``evt.EVT_N_DELETE``.

    User implementation of this event handler is required if one or more
    services that use N-DELETE are to be supported. If a handler is
    not implemented and bound to ``evt.EVT_N_DELETE`` then the N-DELETE request
    will be responded to using a  *Status* value of ``0x0110`` - Processing
    failure.

    **Event**

    ``evt.EVT_N_DELETE``

    **Supported Service Classes**

    * :dcm:`Print Management<part04/chapter_H.html>`
    * :dcm:`RT Machine Verification<part04/chapter_DD.html>`

    **Status**

    Success
      | ``0x0000`` - Success

    Failure
      | ``0x0110`` - Processing failure
      | ``0x0112`` - No such SOP Instance
      | ``0x0117`` - Invalid object Instance
      | ``0x0118`` - Not such SOP Class
      | ``0x0119`` - Class-Instance conflict
      | ``0x0124`` - Not authorised
      | ``0x0210`` - Duplicate invocation
      | ``0x0211`` - Unrecognised operation
      | ``0x0212`` - Mistyped argument
      | ``0x0213`` - Resource limitation

    Parameters
    ----------
    event : events.Event
        The event representing a service class receiving a N-DELETE
        request message. :class:`~pynetdicom.events.Event` attributes are:

        * :attr:`~pynetdicom.events.Event.assoc`: the
          :class:`~pynetdicom.association.Association`
          that is running the service that received the N-DELETE request.
        * :attr:`~pynetdicom.events.Event.context`: the presentation context
          the request was sent under
          as a :class:`~pynetdicom.presentation.PresentationContextTuple`.
        * :attr:`~pynetdicom.events.Event.event`: the event that occurred as
          :class:`~pynetdicom.events.InterventionEvent`.
        * :attr:`~pynetdicom.events.Event.request`: the received
          :class:`N-DELETE request <pynetdicom.dimse_primitives.N_DELETE>`
        * :attr:`~pynetdicom.events.Event.timestamp`: the date and time
          that the N-DELETE request was processed by the service as
          :class:`datetime.datetime`.

        :class:`~pynetdicom.events.Event` properties are:

        * :attr:`~pynetdicom.events.Event.message_id`: the N-DELETE request's
          *Message ID* as :class:`int`.
    args
        If the handler was bound to the event using
        ``bind(event, handler, args)`` or by passing
        ``evt_handlers=[(event, handler, args), ...]``, where `args` is a
        :class:`list` then there will be one or more optional extra parameters
        matching the contents of `args`.

    Returns
    -------
    status : pydicom.dataset.Dataset or int
        The status returned to the peer AE in the N-DELETE response. Must be a
        valid N-DELETE status value for the applicable Service Class as either
        an :class:`int` or a :class:`~pydicom.dataset.Dataset` object
        containing (at a minimum) a (0000,0900) *Status* element. If returning
        a :class:`~pydicom.dataset.Dataset` object then
        it may also contain optional elements related to the *Status* (as in
        DICOM Standard, Part 7, :dcm:`Annex C<part07/chapter_C.html>`).

    Raises
    ------
    NotImplementedError
        If the handler has not been implemented and bound to
        ``evt.EVT_N_DELETE`` by the user.

    See Also
    --------

    :meth:`~pynetdicom.association.Association.send_n_delete`
    :class:`~pynetdicom.dimse_primitives.N_DELETE`
    :class:`~pynetdicom.service_class_n.PrintManagementServiceClass`
    :class:`~pynetdicom.service_class_n.RTMachineVerificationServiceClass`

    References
    ----------

    * DICOM Standard, Part 4, :dcm:`Annex H <part04/chapter_H.html>`
    * DICOM Standard, Part 4, :dcm:`Annex DD <part04/chapter_DD.html>`
    * DICOM Standard, Part 7, Sections
      :dcm:`10.1.6<part07/chapter_10.html#sect_10.1.6>`,
      :dcm:`10.3.6<part07/sect_10.3.6.html>`
      and :dcm:`Annex C<part07/chapter_C.html>`
    """
    pass

def doc_handle_event_report(event, *args):
    """Documentation for handlers bound to ``evt.EVT_N_EVENT_REPORT``.

    User implementation of this event handler is required if one or more
    services that use N-EVENT-REPORT are to be supported. If a handler is
    not implemented and bound to ``evt.EVT_N_EVENT_REPORT`` then the
    N-EVENT-REPORT request will be responded to using a  *Status* value
    of ``0x0110`` - Processing Failure.

    **Event**

    ``evt.EVT_N_EVENT_REPORT``

    **Supported Service Classes**

    * :dcm:`Procedure Step<part04/chapter_F.html>`
    * :dcm:`Print Management<part04/chapter_H.html>`
    * :dcm:`Storage Commitment<part04/chapter_J.html>`
    * :dcm:`Instance Availability Notification<part04/chapter_R.html>`
    * :dcm:`Media Creation Management<part04/chapter_S.html>`
    * :dcm:`Unified Procedure Step<part04/chapter_CC.html>`
    * :dcm:`RT Machine Verification<part04/chapter_DD.html>`

    **Status**

    Success
      | ``0x0000`` - Success

    Failure
      | ``0x0110`` - Processing failure
      | ``0x0112`` - No such SOP Instance
      | ``0x0113`` - No such event type
      | ``0x0114`` - No such argument
      | ``0x0115`` - Invalid argument value
      | ``0x0117`` - Invalid object Instance
      | ``0x0118`` - No such SOP Class
      | ``0x0119`` - Class-Instance conflict
      | ``0x0210`` - Duplicate invocation
      | ``0x0211`` - Unrecognised operation
      | ``0x0212`` - Mistyped argument
      | ``0x0213`` - Resource limitation

    Parameters
    ----------
    event : events.Event
        The event representing a service class receiving a N-EVENT-REPORT
        request message. :class:`~pynetdicom.events.Event` attributes are:

        * :attr:`~pynetdicom.events.Event.assoc`: the
          :class:`~pynetdicom.association.Association`
          that is running the service that received the N-EVENT-REPORT request.
        * :attr:`~pynetdicom.events.Event.context`: the presentation context
          the request was sent under
          as a :class:`~pynetdicom.presentation.PresentationContextTuple`.
        * :attr:`~pynetdicom.events.Event.event`: the event that occurred as
          :class:`~pynetdicom.events.InterventionEvent`.
        * :attr:`~pynetdicom.events.Event.request`: the received
          :class:`N-EVENT-REPORT request
          <pynetdicom.dimse_primitives.N_EVENT_REPORT>`
        * :attr:`~pynetdicom.events.Event.timestamp`: the date and time
          that the N-EVENT-REPORT request was processed by the service as
          :class:`datetime.datetime`.

        :class:`~pynetdicom.events.Event` properties are:

        * :attr:`~pynetdicom.events.Event.event_information`: the decoded
          :class:`~pydicom.dataset.Dataset` contained within the
          N-EVENT-REPORT request's *Event Information* parameter. Because
          *pydicom* uses a deferred read when decoding data, if the decode
          fails the returned :class:`~pydicom.dataset.Dataset` will only raise
          an exception at the time of use.
        * :attr:`~pynetdicom.events.Event.event_type`: the N-EVENT-REPORT
          request's *Event Type ID* parameter value as :class:`int`.
        * :attr:`~pynetdicom.events.Event.message_id`: the N-EVENT-REPORT
          request's *Message ID* as :class:`int`.
    args
        If the handler was bound to the event using
        ``bind(event, handler, args)`` or by passing
        ``evt_handlers=[(event, handler, args), ...]``, where `args` is a
        :class:`list` then there will be one or more optional extra parameters
        matching the contents of `args`.

    Returns
    -------
    status : pydicom.dataset.Dataset or int
        The status returned to the peer AE in the N-EVENT-REPORT response.
        Must be a valid N-EVENT-REPORT status value for the applicable Service
        Class as either an :class:`int` or a :class:`~pydicom.dataset.Dataset`
        object containing (at a minimum) a (0000,0900) *Status* element. If
        returning a Dataset object then it may also contain optional elements
        related to the Status (as in DICOM Standard, Part 7,
        :dcm:`Annex C<part07/chapter_C.html>`).
    dataset : pydicom.dataset.Dataset or None
        If the status category is 'Success' or 'Warning' then a
        :class:`~pydicom.dataset.Dataset` containing elements of the
        response's *Event Reply* conformant to the specifications in the
        corresponding Service Class.

        If the status category is not 'Success' or 'Warning' then ``None``.

    Raises
    ------
    NotImplementedError
        If the handler has not been implemented and bound to
        ``evt.EVT_N_EVENT_REPORT`` by the user.

    See Also
    --------

    :meth:`~pynetdicom.association.Association.send_n_event_report`
    :class:`~pynetdicom.dimse_primitives.N_EVENT_REPORT`
    :class:`~pynetdicom.service_class_n.PrintManagementServiceClass`
    :class:`~pynetdicom.service_class_n.ProcedureStepServiceClass`
    :class:`~pynetdicom.service_class_n.RTMachineVerificationServiceClass`
    :class:`~pynetdicom.service_class_n.StorageCommitmentServiceClass`
    :class:`~pynetdicom.service_class_n.UnifiedProcedureStepServiceClass`

    References
    ----------

    * DICOM Standard, Part 4, :dcm:`Annex F <part04/chapter_F.html>`
    * DICOM Standard, Part 4, :dcm:`Annex H <part04/chapter_H.html>`
    * DICOM Standard, Part 4, :dcm:`Annex J <part04/chapter_J.html>`
    * DICOM Standard, Part 4, :dcm:`Annex CC <part04/chapter_CC.html>`
    * DICOM Standard, Part 4, :dcm:`Annex DD <part04/chapter_DD.html>`
    * DICOM Standard, Part 7, Sections
      :dcm:`10.1.1 <part07/chapter_10.html#sect_10.1.1>`,
      :dcm:`10.3.1 <part07/sect_10.3.html#sect_10.3.1>`
      and :dcm:`Annex C <part07/chapter_C.html>`
    """
    pass

def doc_handle_n_get(event, *args):
    """Documentation for handlers bound to ``evt.EVT_N_GET``.

    User implementation of this event handler is required if one or more
    services that use N-GET are to be supported. If a handler is
    not implemented and bound to ``evt.EVT_N_GET`` then the N_GET request
    will be responded to using a  *Status* value of ``0x0110`` - Processing
    Failure.

    **Event**

    ``evt.EVT_N_GET``

    **Supported Service Classes**

    * :dcm:`Procedure Step<part04/chapter_F.html>`
    * :dcm:`Print Management<part04/chapter_H.html>`
    * :dcm:`Media Creation Management<part04/chapter_S.html>`
    * :dcm:`Unified Procedure Step<part04/chapter_CC.html>`
    * :dcm:`RT Machine Verification<part04/chapter_DD.html>`
    * :dcm:`Dispaly System Management<part04/chapter_EE.html>`

    **Status**

    Success
      | ``0x0000`` - Success

    Failure
      | ``0x0107`` - Attribute list error
      | ``0x0110`` - Processing failure
      | ``0x0112`` - No such SOP Instance
      | ``0x0117`` - Invalid object Instance
      | ``0x0118`` - No such SOP Class
      | ``0x0119`` - Class-Instance conflict
      | ``0x0124`` - Not authorised
      | ``0x0210`` - Duplicate invocation
      | ``0x0211`` - Unrecognised operation
      | ``0x0212`` - Mistyped argument
      | ``0x0213`` - Resource limitation
      | ``0xC112`` - Applicable Machine Verification Instance not found
      | ``0xC307`` - Specified SOP Instance UID doesn't exist or is not
        a UPS Instance managed by this SCP

    Warning
      | ``0x0001`` - Requested optional Attributes are not supported
      | ``0x0107`` - Attribute list error

    Parameters
    ----------
    event : events.Event
        The event representing a service class receiving an N-GET
        request message. :class:`~pynetdicom.events.Event` attributes are:

        * :attr:`~pynetdicom.events.Event.assoc`: the
          :class:`~pynetdicom.association.Association`
          that is running the service that received the N-GET request.
        * :attr:`~pynetdicom.events.Event.context`: the presentation context
          the request was sent under
          as a :class:`~pynetdicom.presentation.PresentationContextTuple`.
        * :attr:`~pynetdicom.events.Event.event`: the event that occurred as
          :class:`~pynetdicom.events.InterventionEvent`.
        * :attr:`~pynetdicom.events.Event.request`: the received
          :class:`N-GET request <pynetdicom.dimse_primitives.N_GET>`
        * :attr:`~pynetdicom.events.Event.timestamp`: the date and time
          that the N-GET request was processed by the service as
          :class:`datetime.datetime`.

        :class:`~pynetdicom.events.Event` properties are:

        * :attr:`~pynetdicom.events.Event.attribute_identifiers`: a list of
          attribute :class:`BaseTag<pydicom.tag.BaseTag>` contained within the
          N-GET request's *Attribute Identifier List* parameter.
        * :attr:`~pynetdicom.events.Event.message_id`: the N-GET request's
          *Message ID* as :class:`int`.
    args
        If the handler was bound to the event using
        ``bind(event, handler, args)`` or by passing
        ``evt_handlers=[(event, handler, args), ...]``, where `args` is a
        :class:`list` then there will be one or more optional extra parameters
        matching the contents of `args`.

    Returns
    -------
    status : pydicom.dataset.Dataset or int
        The status returned to the peer AE in the N-GET response. Must be a
        valid N-GET status value for the applicable Service Class as either
        an :class:`int` or a :class:`~pydicom.dataset.Dataset` object
        containing (at a minimum) a (0000,0900) *Status* element. If returning
        a :class:`~pydicom.dataset.Dataset` object then it may also contain
        optional elements related to the *Status* (as in DICOM Standard, Part
        7, :dcm:`Annex C<part07/chapter_C.html>`).
    dataset : pydicom.dataset.Dataset or None
        If the status category is 'Success' or 'Warning' then a
        :class:`~pydicom.dataset.Dataset` containing elements matching the
        request's *Attribute List* conformant to the specifications in the
        corresponding Service Class.

        If the status category is not 'Success' or 'Warning' then ``None``.

    See Also
    --------

    :meth:`~pynetdicom.association.Association.send_n_get`
    :class:`~pynetdicom.dimse_primitives.N_GET`
    :class:`~pynetdicom.service_class_n.DisplaySystemManagementServiceClass`
    :class:`~pynetdicom.service_class_n.MediaCreationManagementServiceClass`
    :class:`~pynetdicom.service_class_n.PrintManagementServiceClass`
    :class:`~pynetdicom.service_class_n.ProcedureStepServiceClass`
    :class:`~pynetdicom.service_class_n.RTMachineVerificationServiceClass`
    :class:`~pynetdicom.service_class_n.UnifiedProcedureStepServiceClass`

    References
    ----------

    * DICOM Standard, Part 4, :dcm:`Annex F <part04/chapter_F.html>`
    * DICOM Standard, Part 4, :dcm:`Annex H <part04/chapter_H.html>`
    * DICOM Standard, Part 4, :dcm:`Annex S <part04/chapter_S.html>`
    * DICOM Standard, Part 4, :dcm:`Annex CC <part04/chapter_CC.html>`
    * DICOM Standard, Part 4, :dcm:`Annex DD <part04/chapter_DD.html>`
    * DICOM Standard, Part 4, :dcm:`Annex EE <part04/chapter_EE.html>`
    * DICOM Standard, Part 7, Sections
      :dcm:`10.1.2 <part07/chapter_10.html#sect_10.1.2>`,
      :dcm:`10.3.2 <part07/sect_10.3.2.html>`
      and :dcm:`Annex C <part07/chapter_C.html>`
    """
    pass

def doc_handle_set(event, *args):
    """Documentation for handlers bound to ``evt.EVT_N_SET``.

    User implementation of this event handler is required if one or more
    services that use N-SET are to be supported. If a handler is
    not implemented and bound to ``evt.EVT_N_SET`` then the N-SET request
    will be responded to using a  *Status* value of ``0x0110`` - Processing
    Failure.

    **Event**

    ``evt.EVT_N_SET``

    **Supported Service Classes**

    * :dcm:`Procedure Step<part04/chapter_F.html>`
    * :dcm:`Print Management<part04/chapter_H.html>`
    * :dcm:`Unified Procedure Step<part04/chapter_CC.html>`
    * :dcm:`RT Machine Verification<part04/chapter_DD.html>`

    **Status**

    Success
      | ``0x0000`` - Success

    Failure
      | ``0x0105`` - No such attribute
      | ``0x0106`` - Invalid attribute value
      | ``0x0110`` - Processing failure
      | ``0x0112`` - SOP Instance not recognised
      | ``0x0116`` - Attribute value out of range
      | ``0x0117`` - Invalid object instance
      | ``0x0118`` - No such SOP Class
      | ``0x0119`` - Class-Instance conflict
      | ``0x0121`` - Missing attribute value
      | ``0x0124`` - Refused: not authorised
      | ``0x0210`` - Duplicate invocation
      | ``0x0211`` - Unrecognised operation
      | ``0x0212`` - Mistyped argument
      | ``0x0213`` - Resource limitation
      | ``0xC112`` - Applicable Machine Verification Instance not found
      | ``0xC224`` - Reference Beam Number not found within the
        referenced Fraction Group
      | ``0xC225`` - Referenced device or accessory not supported
      | ``0xC226`` - Referenced device or accessory not found with the
        referenced beam
      | ``0xC300`` - The UPS may no longer be updated
      | ``0xC301`` - The correct Transaction UID was not provided
      | ``0xC307`` - Specified SOP Instance UID does not exist or is not a UPS
        Instance managed by this SCP
      | ``0xC310`` - The UPS is not in the 'IN PROGRESS' state
      | ``0xC603`` - Image size is larger than image box size
      | ``0xC605`` - Insufficient memory in printer to store the image
      | ``0xC613`` - Combined Print Image size is larger than the Image Box
        size
      | ``0xC616`` - There is an existing Film Box that has not been
        printed and N-ACTION at the Film Session level is not supported.
        A new Film Box will not be created when a previous Film Box has
        not been printed

    Warning
      | ``0x0001`` - Requested optional attributes are not supported
      | ``0xB305`` - Coerced invalid values to valid values
      | ``0xB600`` - Memory allocation not supported
      | ``0xB604`` - Image size larger than image box size, the image has been
        demagnified
      | ``0xB605`` - Requested Min Density or Max Density outside of
        printer's operating range. The printer will use its respective
        minimum or maximum density value instead
      | ``0xB609`` - Image size is larger than the Image Box. The Image has
        been cropped to fit
      | ``0xB60A`` - Image size or Combined Print Image size is larger than the
        Image Box size. The Image or Combined Print Image has been decimated
        to fit

    Parameters
    ----------
    event : events.Event
        The event representing a service class receiving a N-SET
        request message. :class:`~pynetdicom.events.Event` attributes are:

        * :attr:`~pynetdicom.events.Event.assoc`: the
          :class:`~pynetdicom.association.Association`
          that is running the service that received the N-SET request.
        * :attr:`~pynetdicom.events.Event.context`: the presentation context
          the request was sent under
          as a :class:`~pynetdicom.presentation.PresentationContextTuple`.
        * :attr:`~pynetdicom.events.Event.event`: the event that occurred as
          :class:`~pynetdicom.events.InterventionEvent`.
        * :attr:`~pynetdicom.events.Event.request`: the received
          :class:`N-SET request <pynetdicom.dimse_primitives.N_SET>`
        * :attr:`~pynetdicom.events.Event.timestamp`: the date and time
          that the N-SET request was processed by the service as
          :class:`datetime.datetime`.

        :class:`~pynetdicom.events.Event` properties are:

        * :attr:`~pynetdicom.events.Event.message_id`: the N-SET request's
          *Message ID* as :class:`int`.
        * :attr:`~pynetdicom.events.Event.modification_list`: the decoded
          :class:`~pydicom.dataset.Dataset` contained within the
          N-SET request's *Modification List* parameter. Because *pydicom*
          uses a deferred read when decoding data, if the decode fails the
          returned :class:`~pydicom.dataset.Dataset` will only raise an
          exception at the time of use.
    args
        If the handler was bound to the event using
        ``bind(event, handler, args)`` or by passing
        ``evt_handlers=[(event, handler, args), ...]``, where `args` is a
        :class:`list` then there will be one or more optional extra parameters
        matching the contents of `args`.

    Returns
    -------
    status : pydicom.dataset.Dataset or int
        The status returned to the peer AE in the N-SET response. Must be a
        valid N-SET status value for the applicable Service Class as either
        an :class:`int` or a :class:`~pydicom.dataset.Dataset` object
        containing (at a minimum) a (0000,0900) *Status* element. If returning
        a :class:`~pydicom.dataset.Dataset` object then it may also contain
        optional elements related to the *Status* (as in DICOM Standard, Part
        7, :dcm:`Annex C<part07/chapter_C.html>`).
    dataset : pydicom.dataset.Dataset or None
        If the status category is 'Success' or 'Warning' then a
        :class:`~pydicom.dataset.Dataset` containing elements of the response's
        *Attribute List* conformant to the specifications in the corresponding
        Service Class.

        If the status category is not 'Success' or 'Warning' then ``None``.

    Raises
    ------
    NotImplementedError
        If the handler has not been implemented and bound to
        ``evt.EVT_N_SET`` by the user.

    See Also
    --------

    :meth:`~pynetdicom.association.Association.send_n_set`
    :class:`~pynetdicom.dimse_primitives.N_SET`
    :class:`~pynetdicom.service_class_n.PrintManagementServiceClass`
    :class:`~pynetdicom.service_class_n.ProcedureStepServiceClass`
    :class:`~pynetdicom.service_class_n.RTMachineVerificationServiceClass`
    :class:`~pynetdicom.service_class_n.UnifiedProcedureStepServiceClass`

    References
    ----------

    * DICOM Standard, Part 4, :dcm:`Annex F <part04/chapter_F.html>`
    * DICOM Standard, Part 4, :dcm:`Annex H <part04/chapter_H.html>`
    * DICOM Standard, Part 4, :dcm:`Annex CC <part04/chapter_CC.html>`
    * DICOM Standard, Part 4, :dcm:`Annex DD <part04/chapter_DD.html>`
    * DICOM Standard, Part 7, Sections
      :dcm:`10.1.3 <part07/chapter_10.html#sect_10.1.3>`,
      :dcm:`10.3.3 <part07/sect_10.3.3.html>`
      and :dcm:`Annex C <part07/chapter_C.html>`
    """
    pass

def doc_handle_async(event, *args):
    """Documentation for handlers bound to ``evt.EVT_ASYNC_OPS``.

    User implementation of this event handler is optional. If a handler is
    not implemented and bound to ``evt.EVT_ASYNC_OPS`` then no response to the
    :dcm:`Asynchronous Operations Window Negotiation<part07/sect_D.3.3.3.html>`
    item will be sent in reply to the association requestor.

    Because *pynetdicom* doesn't support asynchronous operations if the
    handler is implemented then the response to the asynchronous
    operations window negotiation request will always return the default
    number of operations invoked/performed, (1, 1), regardless of what
    values are returned by the handler.

    **Event**

    ``evt.EVT_ASYNC_OPS``

    Parameters
    ----------
    event : events.Event
        The event representing an association request being received which
        contains an Asynchronous Operations Window Negotiation item. Event
        attributes are:

        * :attr:`~pynetdicom.events.Event.assoc`: the
          :class:`~pynetdicom.association.Association`
          that received the Asynchronous Operations Window Negotiation request.
        * :attr:`~pynetdicom.events.Event.event`: the event that occurred as
          :class:`~pynetdicom.events.InterventionEvent`.
        * ``invoked``: the *Maximum Number Operations Invoked* parameter
          value of the Asynchronous Operations Window Negotiation item as
          an :class:`int`. If the value is ``0`` then an unlimited number of
          invocations are requested.
        * ``performed``: the *Maximum Number Operations Performed*
          parameter value of the Asynchronous Operations Window Negotiation
          item as an :class:`int`. If the value is ``0`` then an unlimited
          number of performances are requested.
        * :attr:`~pynetdicom.events.Event.timestamp`: the date and time
          that the negotiation request was processed as
          :class:`datetime.datetime`.
    args
        If the handler was bound to the event using
        ``bind(event, handler, args)`` or by passing
        ``evt_handlers=[(event, handler, args), ...]``, where `args` is a
        :class:`list` then there will be one or more optional extra parameters
        matching the contents of `args`.

    Returns
    -------
    int, int
        The (maximum number operations invoked, maximum number operations
        performed). A value of ``0`` indicates that an unlimited number of
        operations is supported. As asynchronous operations are not
        supported the returned values will be ignored and (1, 1) sent in
        response.

    References
    ----------

    * DICOM Standard, Part 7, :dcm:`Annex D.3.3.3 <part07/sect_D.3.3.3.html>`
    """
    pass

def doc_handle_sop_common(event, *args):
    """Documentation for handlers bound to ``evt.EVT_SOP_COMMON``.

    User implementation of this event handler is required only if
    :dcm:`SOP Class Common Extended Negotiation<part07/sect_D.3.3.6.html>`
    is to be supported by the association.

    **Event**

    ``evt.EVT_SOP_COMMON``

    Parameters
    ----------
    event : events.Event
        The event representing an association request being received which
        contains one or more SOP Class Common Extended Negotiation items. Event
        attributes are:

        * :attr:`~pynetdicom.events.Event.assoc`: the
          :class:`~pynetdicom.association.Association`
          that received the SOP Class Common Extended Negotiation request.
        * :attr:`~pynetdicom.events.Event.event`: the event that occurred as
          :class:`~pynetdicom.events.InterventionEvent`.
        * ``items``: the {*SOP Class UID* :
          :class:`SOP Class Common Extended Negotiation
          <pynetdicom.pdu_primitives.SOPClassCommonExtendedNegotiation>`}
          items sent by the requestor.
        * :attr:`~pynetdicom.events.Event.timestamp`: the date and time
          that the negotiation request was processed as
          :class:`datetime.datetime`.
    args
        If the handler was bound to the event using
        ``bind(event, handler, args)`` or by passing
        ``evt_handlers=[(event, handler, args), ...]``, where `args` is a
        :class:`list` then there will be one or more optional extra parameters
        matching the contents of `args`.

    Returns
    -------
    dict
        The {*SOP Class UID* :
        :class:`SOP Class Common Extended Negotiation
        <pynetdicom.pdu_primitives.SOPClassCommonExtendedNegotiation>`} items
        accepted by the acceptor. When receiving DIMSE messages containing
        datasets corresponding to the *SOP Class UID* in an accepted item
        the corresponding Service Class will be used (if available).

    References
    ----------

    * DICOM Standard, Part 7, :dcm:`Annex D.3.3.6 <part07/sect_D.3.3.6.html>`
    """
    pass

def doc_handle_sop_extended(event, *args):
    """Documentation for handlers bound to ``evt.EVT_SOP_EXTENDED``.

    User implementation of this event handler is required only if
    :dcm:`SOP Class Extended Negotiation<part07/sect_D.3.3.5.html>`
    is to be supported by the association. If a handler
    is not implemented and bound to ``evt.EVT_SOP_EXTENDED`` then no response
    will be sent to the SOP Class Extended Negotiation request.

    **Event**

    ``evt.EVT_SOP_EXTENDED``

    Parameters
    ----------
    event : events.Event
        The event representing an association request being received which
        contains one or more SOP Class Extended Negotiation item. Event
        attributes are:

        * ``app_info``: the {*SOP Class UID* : *Service Class Application
          Information*} parameter values for the included items, with the
          service class application information being the raw encoded data sent
          by the requestor (as :class:`bytes`).
        * :attr:`~pynetdicom.events.Event.assoc`: the
          :class:`~pynetdicom.association.Association`
          that is running the service that received the user identity
          negotiation request.
        * :attr:`~pynetdicom.events.Event.event`: the event that occurred as
          :class:`~pynetdicom.events.InterventionEvent`.
        * :attr:`~pynetdicom.events.Event.timestamp`: the date and time
          that the negotiation request was processed as
          :class:`datetime.datetime`.
    args
        If the handler was bound to the event using
        ``bind(event, handler, args)`` or by passing
        ``evt_handlers=[(event, handler, args), ...]``, where `args` is a
        :class:`list` then there will be one or more optional extra parameters
        matching the contents of `args`.

    Returns
    -------
    dict of pydicom.uid.UID, bytes
        The {*SOP Class UID* : *Service Class Application Information*}
        parameter values to be sent in response to the request, with the
        service class application information being the encoded data that
        will be sent to the peer as-is. Return an empty :class:`dict` if no
        response is to be sent.

    References
    ----------

    * DICOM Standard, Part 7, :dcm:`Annex D.3.3.5 <part07/sect_D.3.3.5.html>`
    """
    pass

def doc_handle_userid(event, *args):
    """Documentation for handlers bound to ``evt.EVT_USER_ID``.

    User implementation of this handler is required if
    :dcm:`User Identity Negotiation<part07/sect_D.3.3.7.html>`
    is to be supported by the association. If no handler is
    implemented and bound to ``evt.EVT_USER_ID``
    then the association will be accepted (provided there's no other reason
    to reject it) and no User Identity Negotiation response will be sent in
    reply even if one is requested.

    **Event**

    ``evt.EVT_USER_ID``

    Parameters
    ----------
    event : events.Event
        The event representing an association request being received which
        contains a User Identity Negotiation item.
        :class:`~pynetdicom.events.Event` attributes are:

        * :attr:`~pynetdicom.events.Event.assoc`: the
          :class:`~pynetdicom.association.Association`
          that is running the service that received the user identity
          negotiation request.
        * :attr:`~pynetdicom.events.Event.event`: the event that occurred as
          :class:`~pynetdicom.events.InterventionEvent`.
        * ``primary_field``: the *Primary Field* value (as :class:`bytes`),
          contains the username, the encoded Kerberos ticket or the JSON web
          token, depending on the value of `user_id_type`.
        * ``secondary_field``: the *Secondary Field* value. Will be ``None``
          unless the `user_id_type` is ``2`` in which case it will be
          :class:`bytes`.
        * :attr:`~pynetdicom.events.Event.timestamp`: the date and time
          that the negotiation request was processed as
          :class:`datetime.datetime`.
        * ``user_id_type``: the *User Identity Type* value (as an
          :class:`int`), which indicates the form of user identity being
          provided:

          * ``1`` - Username as a UTF-8 string
          * ``2`` - Username as a UTF-8 string and passcode
          * ``3`` - Kerberos Service ticket
          * ``4`` - SAML Assertion
          * ``5`` - JSON Web Token
    args
        If the handler was bound to the event using
        ``bind(event, handler, args)`` or by passing
        ``evt_handlers=[(event, handler, args), ...]``, where `args` is a
        :class:`list` then there will be one or more optional extra parameters
        matching the contents of `args`.

    Returns
    -------
    is_verified : bool
        Return ``True`` if the user identity has been confirmed and you wish
        to proceed with association establishment, ``False`` otherwise.
    response : bytes or None
        If `user_id_type` is:

        * ``1`` or ``2``, then return ``None``
        * ``3`` then return the Kerberos Server ticket as :class:`bytes`
        * ``4`` then return the SAML response as :class:`bytes`
        * ``5`` then return the JSON web token as :class:`bytes`

    References
    ----------

    * DICOM Standard, Part 7, :dcm:`Annex D.3.3.7 <part07/sect_D.3.3.7.html>`
    """
    pass

# Notification event handler documentation
def doc_handle_acse(event, *args):
    """Documentation for handlers bound to ``evt.EVT_ACSE_RECV`` or
    ``evt.EVT_ACSE_SENT``.

    Parameters
    ----------
    event : events.Event
        Represents the ACSE service provider receiving or sending an
        association related primitive to/from the DUL service provider.
        :class:`~pynetdicom.events.Event` attributes are:

        * :attr:`~pynetdicom.events.Event.assoc`: the
          :class:`~pynetdicom.association.Association` that triggered the
          event.
        * :attr:`~pynetdicom.events.Event.event`: the event that occurred as
          :class:`~pynetdicom.events.NotificationEvent`.
        * ``primitive``: the ACSE primitive sent to or received from the
          DUL service provider. One of
          :class:`A_ASSOCIATE<pynetdicom.pdu_primitives.A_ASSOCIATE>`,
          :class:`A_RELEASE<pynetdicom.pdu_primitives.A_RELEASE>`,
          :class:`A_ABORT<pynetdicom.pdu_primitives.A_ABORT>` or
          :class:`A_P_ABORT<pynetdicom.pdu_primitives.A_P_ABORT>`.
        * :attr:`~pynetdicom.events.Event.timestamp`: the date and time
          that the negotiation item was processed as
          :class:`datetime.datetime`.
    args
        If the handler was bound to the event using
        ``bind(event, handler, args)`` or by passing
        ``evt_handlers=[(event, handler, args), ...]``, where `args` is a
        :class:`list` then there will be one or more optional extra parameters
        matching the contents of `args`.
    """
    pass

def doc_handle_assoc(event, *args):
    """Documentation for handlers bound to ``evt.EVT_ACCEPTED``,
    ``evt.EVT_ESTABLISHED``, ``evt.EVT_REJECTED``, ``evt.EVT_REQUESTED``,
    ``evt.EVT_RELEASED`` or ``evt.EVT_ABORTED``.

    Parameters
    ----------
    event : events.Event
        Represents moving to one of the main association states. Event
        attributes are:

        * :attr:`~pynetdicom.events.Event.assoc`: the
          :class:`~pynetdicom.association.Association` that triggered the
          event.
        * :attr:`~pynetdicom.events.Event.event`: the event that occurred as
          :class:`~pynetdicom.events.NotificationEvent`.
        * :attr:`~pynetdicom.events.Event.timestamp`: the date and time
          that the association status changed as :class:`datetime.datetime`.
    args
        If the handler was bound to the event using
        ``bind(event, handler, args)`` or by passing
        ``evt_handlers=[(event, handler, args), ...]``, where `args` is a
        :class:`list` then there will be one or more optional extra parameters
        matching the contents of `args`.
    """
    pass

def doc_handle_dimse(event, *args):
    """Documentation for handlers bound to ``evt.EVT_DIMSE_RECV`` or
    ``evt.EVT_DIMSE_SENT``.

    Parameters
    ----------
    event : events.Event
        Represents the DIMSE service provider decoding a DIMSE message after
        receiving the final P-DATA primitive that contained it, or encoding
        and converting a DIMSE message into P-DATA primitives. Event
        attributes are:

        * :attr:`~pynetdicom.events.Event.assoc`: the
          :class:`~pynetdicom.association.Association`
          that is running the service that received the user identity
          negotiation request.
        * :attr:`~pynetdicom.events.Event.event`: the event that occurred as
          :class:`~pynetdicom.events.NotificationEvent`.
        * ``message``: the DIMSE message encoding or decoded. One of
          :class:`~pynetdicom.dimse_messages.C_ECHO_RQ`,
          :class:`~pynetdicom.dimse_messages.C_ECHO_RSP`,
          :class:`~pynetdicom.dimse_messages.C_FIND_RQ`,
          :class:`~pynetdicom.dimse_messages.C_FIND_RSP`,
          :class:`~pynetdicom.dimse_messages.C_GET_RQ`,
          :class:`~pynetdicom.dimse_messages.C_GET_RSP`,
          :class:`~pynetdicom.dimse_messages.C_MOVE_RQ`,
          :class:`~pynetdicom.dimse_messages.C_MOVE_RSP`,
          :class:`~pynetdicom.dimse_messages.C_STORE_RQ`,
          :class:`~pynetdicom.dimse_messages.C_STORE_RSP`,
          :class:`~pynetdicom.dimse_messages.N_ACTION_RQ`,
          :class:`~pynetdicom.dimse_messages.N_ACTION_RSP`,
          :class:`~pynetdicom.dimse_messages.N_CREATE_RQ`,
          :class:`~pynetdicom.dimse_messages.N_CREATE_RSP`,
          :class:`~pynetdicom.dimse_messages.N_DELETE_RQ`,
          :class:`~pynetdicom.dimse_messages.N_DELETE_RSP`,
          :class:`~pynetdicom.dimse_messages.N_EVENT_REPORT_RQ`,
          :class:`~pynetdicom.dimse_messages.N_EVENT_REPORT_RSP`,
          :class:`~pynetdicom.dimse_messages.N_GET_RQ`,
          :class:`~pynetdicom.dimse_messages.N_GET_RSP`,
          :class:`~pynetdicom.dimse_messages.N_SET_RQ` or
          :class:`~pynetdicom.dimse_messages.N_SET_RSP`
        * :attr:`~pynetdicom.events.Event.timestamp`: the date and time
          that the message was processed as :class:`datetime.datetime`.
    args
        If the handler was bound to the event using
        ``bind(event, handler, args)`` or by passing
        ``evt_handlers=[(event, handler, args), ...]``, where `args` is a
        :class:`list` then there will be one or more optional extra parameters
        matching the contents of `args`.
    """
    pass

def doc_handle_data(event, *args):
    """Documentation for handlers bound to ``evt.EVT_DATA_RECV`` or
    ``evt.EVT_DATA_SENT``.

    Parameters
    ----------
    event : events.Event
        Represents data being sent to/received from the remote over the
        socket. :class:`~pynetdicom.events.Event` attributes are:

        * :attr:`~pynetdicom.events.Event.assoc`: the
          :class:`~pynetdicom.association.Association` that triggered the
          event.
        * ``data``: the data sent to/received from the remote, as
          :class:`bytes`.
        * :attr:`~pynetdicom.events.Event.event`: the event that occurred as
          :class:`~pynetdicom.events.NotificationEvent`.
        * :attr:`~pynetdicom.events.Event.timestamp`: the date and time
          that the data was sent/received as :class:`datetime.datetime`.
    args
        If the handler was bound to the event using
        ``bind(event, handler, args)`` or by passing
        ``evt_handlers=[(event, handler, args), ...]``, where `args` is a
        :class:`list` then there will be one or more optional extra parameters
        matching the contents of `args`.
    """
    pass

def doc_handle_fsm(event, *args):
    """Documentation for handlers bound to ``evt.EVT_FSM_TRANSITION``.

    Parameters
    ----------
    event : events.Event
        Represents the state machine receiving a triggering event and being
        about to perform the action that will take it to the next state.
        :class:`~pynetdicom.events.Event` attributes are:

        * ``action``: the name of the action that's to be performed as
          :class:`str`.
        * :attr:`~pynetdicom.events.Event.assoc`: the
          :class:`~pynetdicom.association.Association` that triggered the
          event.
        * ``current_state``: the current state of the state machine as
          :class:`str`.
        * :attr:`~pynetdicom.events.Event.event`: the event that occurred as
          :class:`~pynetdicom.events.NotificationEvent`.
        * ``fsm_event``: the name of the state machine event that occurred,
          triggering the transition as :class:`str`.
        * ``next_state``: the state the state machine will be in after the
          action has been performed as :class:`str`.
        * :attr:`~pynetdicom.events.Event.timestamp`: the date and time
          that the FSM transition occurred as :class:`datetime.datetime`.
    args
        If the handler was bound to the event using
        ``bind(event, handler, args)`` or by passing
        ``evt_handlers=[(event, handler, args), ...]``, where `args` is a
        :class:`list` then there will be one or more optional extra parameters
        matching the contents of `args`.
    """
    pass

def doc_handle_pdu(event, *args):
    """Documentation for handlers bound to ``evt.EVT_PDU_RECV`` or
    ``evt.EVT_PDU_SENT``.

    Parameters
    ----------
    event : events.Event
        Represents the DUL service provider sending or receiving a PDU.
        :class:`~pynetdicom.events.Event` attributes are:

        * :attr:`~pynetdicom.events.Event.assoc`: the
          :class:`~pynetdicom.association.Association` that triggered the
          event.
        * :attr:`~pynetdicom.events.Event.event`: the event that occurred as
          :class:`~pynetdicom.events.NotificationEvent`.
        * ``pdu``: the PDU sent to or received from the peer. One of:
          :class:`A_ASSOCIATE_RQ<pynetdicom.pdu.A_ASSOCIATE_RQ>`,
          :class:`A_ASSOCIATE_RJ<pynetdicom.pdu.A_ASSOCIATE_RJ>`,
          :class:`A_ASSOCIATE_AC<pynetdicom.pdu.A_ASSOCIATE_AC>`,
          :class:`A_RELEASE_RQ<pynetdicom.pdu.A_RELEASE_RQ>`,
          :class:`A_RELEASE_RP<pynetdicom.pdu.A_RELEASE_RP>`,
          :class:`A_ABORT_RQ<pynetdicom.pdu.A_ABORT_RQ>` or
          :class:`P_DATA_TF<pynetdicom.pdu.P_DATA_TF>`.
        * :attr:`~pynetdicom.events.Event.timestamp`: the date and time
          that the PDU was processed as :class:`datetime.datetime`.
    args
        If the handler was bound to the event using
        ``bind(event, handler, args)`` or by passing
        ``evt_handlers=[(event, handler, args), ...]``, where `args` is a
        :class:`list` then there will be one or more optional extra parameters
        matching the contents of `args`.
    """
    pass

def doc_handle_transport(event, *args):
    """Documentation for handlers bound to ``evt.EVT_CONN_OPEN`` or
    ``evt.EVT_CONN_CLOSE``.

    Parameters
    ----------
    event : events.Event
        Represents opening or closing a transport connection. Event
        attributes are:

        * ``address``: the (host, port) of the remote as (:class:`str`,
          :class:`int`).
        * :attr:`~pynetdicom.events.Event.assoc`: the
          :class:`~pynetdicom.association.Association` that triggered the
          event.
        * :attr:`~pynetdicom.events.Event.event`: the event that occurred as
          :class:`~pynetdicom.events.NotificationEvent`.
        * :attr:`~pynetdicom.events.Event.timestamp`: the date and time
          that the connection was opened/closed as
          :class:`datetime.datetime`.
    args
        If the handler was bound to the event using
        ``bind(event, handler, args)`` or by passing
        ``evt_handlers=[(event, handler, args), ...]``, where `args` is a
        :class:`list` then there will be one or more optional extra parameters
        matching the contents of `args`.
    """
    pass
