
# ACSE

# DUL
# Receive/sent PDUs
def send_abort(a_abort_rq):
    """
    Placeholder for a function callback. Function will be called
    immediately prior to encoding and sending an A-ABORT to a peer AE

    Parameters
    ----------
    a_abort : pdu.A_ABORT_RQ
        The A-ABORT PDU instance
    """
    LOGGER.info('Aborting Association')

def send_associate_ac(a_associate_ac):
    """
    Placeholder for a function callback. Function will be called
    immediately prior to encoding and sending an A-ASSOCIATE-AC to a peer
    AE

    Parameters
    ----------
    a_associate_ac : pdu.A_ASSOCIATE_AC
        The A-ASSOCIATE-AC PDU instance
    """
    LOGGER.info("Association Accepted")

    # Shorthand
    assoc_ac = a_associate_ac

    # Needs some cleanup
    app_context = assoc_ac.application_context_name.title()
    pres_contexts = assoc_ac.presentation_context
    user_info = assoc_ac.user_information
    async_ops = user_info.async_ops_window
    roles = user_info.role_selection

    responding_ae = 'resp. AE Title'

    s = ['Accept Parameters:']
    s.append('====================== BEGIN A-ASSOCIATE-AC ================'
             '=====')

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
    for item in sorted(pres_contexts, key=lambda x: x.context_id):
        s.append('  Context ID:        {0!s} ({1!s})'
                 .format(item.context_id, item.result_str))

        # If Presentation Context was accepted
        if item.result == 0:
            #if item.scu_role is None and item.scp_role is None:
            #    ac_scp_scu_role = 'Default'
            #else:
            #    ac_scp_scu_role = '{0!s}/{1!s}'.format(item.scp_role,
            #item.scu_role)
            #s.append('    Accepted SCP/SCU Role: {0!s}'
            #         .format(ac_scp_scu_role))
            s.append('    Accepted Transfer Syntax: ={0!s}'
                     .format(item.transfer_syntax.name))

    ## Role Selection
    if roles:
        s.append("Accepted Role Selection:")

        for uid in sorted(roles.keys()):
            s.append("  SOP Class: ={}".format(uid.name))
            str_roles = []
            if roles[uid].scp_role:
                str_roles.append('SCP')
            if roles[uid].scu_role:
                str_roles.append('SCU')

            str_roles = '/'.join(str_roles)
            s.append("    SCP/SCU Role: {}".format(str_roles))

    ## Extended Negotiation
    if user_info.ext_neg:
        s.append('Accepted Extended Negotiation:')

        for item in user_info.ext_neg:
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

    ## User Identity Negotiation
    usr_id = 'Yes' if user_info.user_identity is not None else 'None'


    s.append('User Identity Negotiation Response: {0!s}'.format(usr_id))
    s.append(
        '======================= END A-ASSOCIATE-AC ======================'
    )

    for line in s:
        LOGGER.debug(line)

def send_associate_rj(a_associate_rj):
    """
    Placeholder for a function callback. Function will be called
    immediately prior to encoding and sending an A-ASSOCIATE-RJ to a peer
    AE.

    Parameters
    ----------
    a_associate_rj : pdu.A_ASSOCIATE_RJ
        The A-ASSOCIATE-RJ PDU instance
    """
    LOGGER.info("Association Rejected")

def send_associate_rq(a_associate_rq):
    """
    Placeholder for a function callback. Function will be called
    immediately prior to encoding and sending an A-ASSOCIATE-RQ to
    a peer AE

    The default implementation is used for logging debugging information

    Parameters
    ----------
    a_associate_rq : pdu.A_ASSOCIATE_RQ
        The A-ASSOCIATE-RQ PDU instance to be encoded and sent
    """
    # Shorthand
    pdu = a_associate_rq

    app_context = pdu.application_context_name.title()
    pres_contexts = pdu.presentation_context
    user_info = pdu.user_information

    s = ['Request Parameters:']
    s.append('====================== BEGIN A-ASSOCIATE-RQ ================'
             '=====')

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
            app_info[0] = '[' + app_info[0][1:]
            app_info[-1] = app_info[-1] + ' ]'
            for line in app_info:
                s.append('    {0!s}'.format(line))
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

    s.append(
        '======================= END A-ASSOCIATE-RQ ======================'
    )

    for line in s:
        LOGGER.debug(line)

def send_data_tf(p_data_tf):
    """
    Placeholder for a function callback. Function will be called
    immediately prior to encoding and sending an P-DATA-TF to a peer AE

    Parameters
    ----------
    a_release_rq : pdu.P_DATA_TF
        The P-DATA-TF PDU instance
    """
    pass

def send_release_rp(a_release_rp):
    """
    Placeholder for a function callback. Function will be called
    immediately prior to encoding and sending an A-RELEASE-RP to a peer AE

    Parameters
    ----------
    a_release_rp : pdu.A_RELEASE_RP
        The A-RELEASE-RP PDU instance
    """
    pass

def send_release_rq(a_release_rq):
    """
    Placeholder for a function callback. Function will be called
    immediately prior to encoding and sending an A-RELEASE-RQ to a peer AE

    Parameters
    ----------
    a_release_rq : pdu.A_RELEASE_RQ
        The A-RELEASE-RQ PDU instance
    """
    pass

def recv_abort(a_abort):
    """
    Placeholder for a function callback. Function will be called
    immediately after receiving and decoding an A-ABORT

    Parameters
    ----------
    a_abort : pdu.A_ABORT_RQ
        The A-ABORT PDU instance
    """
    s = ['Abort Parameters:']
    s.append(
        '========================== BEGIN A-ABORT ========================'
    )
    s.append('Abort Source: {0!s}'.format(a_abort.source_str))
    s.append('Abort Reason: {0!s}'.format(a_abort.reason_str))
    s.append(
        '=========================== END A-ABORT ========================='
    )
    for line in s:
        LOGGER.debug(line)

def recv_associate_ac(a_associate_ac):
    """
    Placeholder for a function callback. Function will be called
    immediately after receiving and decoding an A-ASSOCIATE-AC

    The default implementation is used for logging debugging information

    Most of this should be moved to on_association_accepted()

    Parameters
    ----------
    a_associate_ac : pdu.A_ASSOCIATE_AC
        The A-ASSOCIATE-AC PDU instance
    """
    # Shorthand
    assoc_ac = a_associate_ac

    app_context = assoc_ac.application_context_name.title()
    pres_contexts = assoc_ac.presentation_context
    user_info = assoc_ac.user_information
    async_ops = user_info.async_ops_window
    roles = user_info.role_selection

    their_class_uid = 'unknown'
    their_version = b'unknown'

    if user_info.implementation_class_uid:
        their_class_uid = user_info.implementation_class_uid
    if user_info.implementation_version_name:
        their_version = user_info.implementation_version_name

    s = ['Accept Parameters:']
    s.append('====================== BEGIN A-ASSOCIATE-AC ================'
             '=====')

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

    for item in pres_contexts:
        s.append('  Context ID:        {0!s} ({1!s})'
                 .format(item.context_id, item.result_str))

        if item.result == 0:
            s.append('    Accepted Transfer Syntax: ={0!s}'
                     .format(item.transfer_syntax.name))

    ## Role Selection
    if roles:
        s.append("Accepted Role Selection:")

        for uid in sorted(roles.keys()):
            s.append("  SOP Class: ={}".format(uid.name))
            str_roles = []
            if roles[uid].scp_role:
                str_roles.append('SCP')
            if roles[uid].scu_role:
                str_roles.append('SCU')

            str_roles = '/'.join(str_roles)
            s.append("    SCP/SCU Role: {}".format(str_roles))

    ## Extended Negotiation
    if user_info.ext_neg:
        s.append('Accepted Extended Negotiation:')

        for item in user_info.ext_neg:
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
    usr_id = 'Yes' if user_info.user_identity is not None else 'None'

    s.append('User Identity Negotiation Response: {0!s}'.format(usr_id))
    s.append(
        '======================= END A-ASSOCIATE-AC ======================'
    )

    for line in s:
        LOGGER.debug(line)

    LOGGER.info('Association Accepted')

def recv_associate_rj(a_associate_rj):
    """
    Placeholder for a function callback. Function will be called
    immediately after receiving and decoding an A-ASSOCIATE-RJ

    Parameters
    ----------
    a_associate_rj : pdu.A_ASSOCIATE_RJ
        The A-ASSOCIATE-RJ PDU instance
    """
    # Shorthand
    assoc_rj = a_associate_rj

    s = ['Reject Parameters:']
    s.append(
        '====================== BEGIN A-ASSOCIATE-RJ ====================='
    )
    s.append('Result:    {0!s}'.format(assoc_rj.result_str))
    s.append('Source:    {0!s}'.format(assoc_rj.source_str))
    s.append('Reason:    {0!s}'.format(assoc_rj.reason_str))
    s.append(
        '======================= END A-ASSOCIATE-RJ ======================'
    )
    for line in s:
        LOGGER.debug(line)

def recv_associate_rq(a_associate_rq):
    """
    Placeholder for a function callback. Function will be called
    immediately after receiving and decoding an A-ASSOCIATE-RQ

    Parameters
    ----------
    a_associate_rq : pdu.A_ASSOCIATE_RQ
        The A-ASSOCIATE-RQ PDU instance
    """
    LOGGER.info("Association Received")

    # Shorthand
    pdu = a_associate_rq

    app_context = pdu.application_context_name.title()
    pres_contexts = pdu.presentation_context
    user_info = pdu.user_information

    #responding_ae = 'resp. AP Title'
    their_class_uid = 'unknown'
    their_version = b'unknown'

    if user_info.implementation_class_uid:
        their_class_uid = user_info.implementation_class_uid
    if user_info.implementation_version_name:
        their_version = user_info.implementation_version_name

    s = ['Request Parameters:']
    s.append('====================== BEGIN A-ASSOCIATE-RQ ================'
             '=====')
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
            app_info[0] = '[' + app_info[0][1:]
            app_info[-1] = app_info[-1] + ' ]'
            for line in app_info:
                s.append('    {0!s}'.format(line))
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

def recv_data_tf(p_data_tf):
    """
    Placeholder for a function callback. Function will be called
    immediately after receiving and decoding an P-DATA-TF

    Parameters
    ----------
    p_data_tf : pdu.P_DATA_TF
        The P-DATA-TF PDU instance
    """
    pass

def recv_release_rp(a_release_rp):
    """
    Placeholder for a function callback. Function will be called
    immediately after receiving and decoding an A-RELEASE-RP

    Parameters
    ----------
    a_release_rp : pdu.A_RELEASE_RP
        The A-RELEASE-RP PDU instance
    """
    pass

def recv_release_rq(a_release_rq):
    """
    Placeholder for a function callback. Function will be called
    immediately after receiving and decoding an A-RELEASE-RQ

    Parameters
    ----------
    a_release_rq : pdu.A_RELEASE_RQ
        The A-RELEASE-RQ PDU instance
    """
    pass

# DIMSE
# Receive/send messages
# DIMSE-C
def send_c_echo_rq(evt):
    """Debugging function when a C-ECHO-RQ is sent.

    **C-ECHO Request Parameters**

    | (M) Message ID
    | (M) Affected SOP Class UID

    Parameters
    ----------
    evt : dimse_messages.C_ECHO_RQ
        The C-ECHO-RQ message to be sent.
    """
    cs = evt.message.command_set
    LOGGER.info("Sending Echo Request: MsgID %s", cs.MessageID)

def send_c_echo_rsp(evt):
    """Debugging function when a C-ECHO-RSP is sent.

    **C-ECHO Response Parameters**

    | (U) Message ID
    | (M) Message ID Being Responded To
    | (U) Affected SOP Class UID
    | (M) Status

    Parameters
    ----------
    evt : dimse_messages.C_ECHO_RSP
        The C-ECHO-RSP message to be sent.
    """
    pass

def send_c_store_rq(evt):
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
    evt : dimse_messages.C_STORE_RQ
        The C-STORE-RQ message to be sent.
    """
    cs = evt.message.command_set

    priority_str = {2: 'Low',
                    0: 'Medium',
                    1: 'High'}
    priority = priority_str[cs.Priority]

    dataset = 'None'
    if evt.data_set and evt.data_set.getvalue() != b'':
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

def send_c_store_rsp(evt):
    """Debugging function when a C-STORE-RSP is sent.

    **C-STORE Response Elements**

    | (U) Message ID
    | (M) Message ID Being Responded To
    | (U) Affected SOP Class UID
    | (U) Affected SOP Instance UID
    | (M) Status

    Parameters
    ----------
    evt : dimse_messages.C_STORE_RSP
        The C-STORE-RSP message to be sent.
    """
    pass

def send_c_find_rq(evt):
    """Debugging function when a C-FIND-RQ is sent.

    **C-FIND Request Parameters**

    | (M) Message ID
    | (M) Affected SOP Class UID
    | (M) Priority
    | (M) Identifier

    Parameters
    ----------
    evt : dimse_messages.C_FIND_RQ
        The C-FIND-RQ message to be sent.
    """
    cs = evt.message.command_set

    priority_str = {2: 'Low',
                    0: 'Medium',
                    1: 'High'}
    priority = priority_str[cs.Priority]

    dataset = 'None'
    if evt.data_set and evt.data_set.getvalue() != b'':
        dataset = 'Present'

    LOGGER.info("Sending Find Request: MsgID %s", cs.MessageID)

    s = []
    s.append(
        '===================== OUTGOING DIMSE MESSAGE ===================='
    )
    s.append('Message Type                  : {0!s}'.format('C-FIND RQ'))
    s.append('Presentation Context ID       : {0!s}'
             .format(evt.context_id))
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

def send_c_find_rsp(evt):
    """Debugging function when a C-FIND-RSP is sent.

    **C-FIND Response Parameters**

    | (U) Message ID
    | (M) Message ID Being Responded To
    | (U) Affected SOP Class UID
    | (C) Identifier
    | (M) Status

    Parameters
    ----------
    evt : dimse_messages.C_FIND_RSP
        The C-FIND-RSP message to be sent.
    """
    cs = evt.message.command_set

    dataset = 'None'
    if evt.data_set and evt.data_set.getvalue() != b'':
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

def send_c_get_rq(evt):
    """Debugging function when a C-GET-RQ is sent.

    **C-GET Request Parameters**

    | (M) Message ID
    | (M) Affected SOP Class UID
    | (M) Priority
    | (M) Identifier

    Parameters
    ----------
    evt : dimse_messages.C_GET_RQ
        The C-GET-RQ message to be sent.
    """
    cs = evt.message.command_set

    priority_str = {2: 'Low',
                    0: 'Medium',
                    1: 'High'}
    priority = priority_str[cs.Priority]

    dataset = 'None'
    if evt.data_set and evt.data_set.getvalue() != b'':
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

def send_c_get_rsp(evt):
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
    evt : dimse_messages.C_GET_RSP
        The C-GET-RSP message to be sent.
    """
    cs = evt.message.command_set

    dataset = 'None'
    if evt.data_set and evt.data_set.getvalue() != b'':
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

def send_c_move_rq(evt):
    """Debugging function when a C-MOVE-RQ is sent.

    **C-MOVE Request Parameters**

    | (M) Message ID
    | (M) Affected SOP Class UID
    | (M) Priority
    | (M) Move Destination
    | (M) Identifier

    Parameters
    ----------
    evt : dimse_messages.C_MOVE_RQ
        The C-MOVE-RQ message to be sent.
    """
    cs = evt.message.command_set

    priority_str = {2: 'Low',
                    0: 'Medium',
                    1: 'High'}
    priority = priority_str[cs.Priority]

    identifier = 'None'
    if evt.data_set and evt.data_set.getvalue() != b'':
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

def send_c_move_rsp(evt):
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
    evt : dimse_messages.C_MOVE_RSP
        The C-MOVE-RSP message to be sent.
    """
    cs = evt.message.command_set

    identifier = 'None'
    if evt.data_set and evt.data_set.getvalue() != b'':
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

def send_c_cancel_rq(evt):
    """Debugging function when a C-CANCEL-RQ is sent.

    Covers C-CANCEL-FIND-RQ, C-CANCEL-GET-RQ and C-CANCEL-MOVE-RQ.

    Parameters
    ----------
    evt : dimse_messages.C_CANCEL_RQ
        The C-CANCEL-RQ message to be sent.
    """
    pass

def recv_c_echo_rq(evt):
    """Debugging function when a C-ECHO-RQ is received.

    **C-ECHO Request Parameters**

    | (M) Message ID
    | (M) Affected SOP Class UID

    Parameters
    ----------
    evt : dimse_messagesC_ECHO_RQ
        The received C-ECHO-RQ message.
    """
    cs = evt.message.command_set

    LOGGER.info('Received Echo Request (MsgID %s)', cs.MessageID)

    s = []
    s.append(
        '===================== INCOMING DIMSE MESSAGE ===================='
    )
    s.append('Message Type                  : {0!s}'.format('C-ECHO RQ'))
    s.append('Presentation Context ID       : {0!s}'
             .format(evt.context_id))
    s.append('Message ID                    : {0!s}'.format(cs.MessageID))
    s.append('Data Set                      : {0!s}'.format('none'))
    s.append(
        '======================= END DIMSE MESSAGE ======================='
    )

    for line in s:
        LOGGER.debug(line)

def recv_c_echo_rsp(evt):
    """Debugging function when a C-ECHO-RSP is received.

    **C-ECHO Response Parameters**

    | (U) Message ID
    | (M) Message ID Being Responded To
    | (U) Affected SOP Class UID
    | (M) Status

    Parameters
    ----------
    evt : dimse_messages.C_ECHO_RSP
        The received C-ECHO-RSP message.
    """
    cs = evt.message.command_set
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

def recv_c_store_rq(evt):
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
    evt : dimse_messagesC_STORE_RQ
        The received C-STORE-RQ message.
    """
    cs = evt.message.command_set

    priority_str = {2: 'Low',
                    0: 'Medium',
                    1: 'High'}
    priority = priority_str[cs.Priority]

    dataset = 'None'
    if evt.data_set and evt.data_set.getvalue() != b'':
        dataset = 'Present'

    LOGGER.info('Received Store Request')

    s = []
    s.append(
        '===================== INCOMING DIMSE MESSAGE ===================='
    )
    s.append('Message Type                  : {0!s}'.format('C-STORE RQ'))
    s.append('Presentation Context ID       : {0!s}'
             .format(evt.context_id))
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

def recv_c_store_rsp(evt):
    """Debugging function when a C-STORE-RSP is received.

    **C-STORE Response Elements**

    | (U) Message ID
    | (M) Message ID Being Responded To
    | (U) Affected SOP Class UID
    | (U) Affected SOP Instance UID
    | (M) Status

    Parameters
    ----------
    evt : dimse_messagesC_STORE_RSP
        The received C-STORE-RSP message.
    """
    cs = evt.message.command_set

    dataset = 'None'
    if evt.data_set and evt.data_set.getvalue() != b'':
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
             .format(evt.context_id))
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

def recv_c_find_rq(evt):
    """Debugging function when a C-FIND-RQ is received.

    **C-FIND Request Parameters**

    | (M) Message ID
    | (M) Affected SOP Class UID
    | (M) Priority
    | (M) Identifier

    Parameters
    ----------
    evt : dimse_messagesC_FIND_RQ
        The received C-FIND-RQ message.
    """
    cs = evt.message.command_set

    priority_str = {2: 'Low',
                    0: 'Medium',
                    1: 'High'}
    priority = priority_str[cs.Priority]

    dataset = 'None'
    if evt.data_set and evt.data_set.getvalue() != b'':
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

def recv_c_find_rsp(evt):
    """Debugging function when a C-FIND-RSP is received.

    **C-FIND Response Parameters**

    | (U) Message ID
    | (M) Message ID Being Responded To
    | (U) Affected SOP Class UID
    | (C) Identifier
    | (M) Status

    Parameters
    ----------
    evt : dimse_messages.C_FIND_RSP
        The received C-FIND-RSP message.
    """
    cs = evt.message.command_set
    if cs.Status != 0x0000:
        return

    dataset = 'None'
    if evt.data_set and evt.data_set.getvalue() != b'':
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

def recv_c_cancel_rq(evt):
    """Debugging function when a C-CANCEL-RQ is received.

    Covers C-CANCEL-FIND-RQ, C-CANCEL-GET-RQ and C-CANCEL-MOVE-RQ

    Parameters
    ----------
    evt : dimse_messagesC_CANCEL_RQ
        The received C-CANCEL-RQ message.
    """
    cs = evt.message.command_set

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

def recv_c_get_rq(evt):
    """Debugging function when a C-GET-RQ is received.

    **C-GET Request Parameters**

    | (M) Message ID
    | (M) Affected SOP Class UID
    | (M) Priority
    | (M) Identifier

    Parameters
    ----------
    evt : dimse_messagesC_GET_RQ
        The received C-GET-RQ message.
    """
    cs = evt.message.command_set

    priority_str = {2: 'Low',
                    0: 'Medium',
                    1: 'High'}
    priority = priority_str[cs.Priority]

    dataset = 'None'
    if evt.data_set and evt.data_set.getvalue() != b'':
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

def recv_c_get_rsp(evt):
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
    evt : dimse_messagesC_GET_RSP
        The received C-GET-RSP message.
    """
    cs = evt.message.command_set

    dataset = 'None'
    if evt.data_set and evt.data_set.getvalue() != b'':
        dataset = 'Present'

    s = []
    s.append(
        '===================== INCOMING DIMSE MESSAGE ===================='
    )
    s.append('Message Type                  : {0!s}'.format('C-GET RSP'))
    s.append('Presentation Context ID       : {0!s}'
             .format(evt.context_id))
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

def recv_c_move_rq(evt):
    """Debugging function when a C-MOVE-RQ is received.

    **C-MOVE Request Parameters**

    | (M) Message ID
    | (M) Affected SOP Class UID
    | (M) Priority
    | (M) Move Destination
    | (M) Identifier

    Parameters
    ----------
    evt : dimse_messagesC_MOVE_RQ
        The received C-MOVE-RQ message.
    """
    pass

def recv_c_move_rsp(evt):
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
    evt : dimse_messagesC_MOVE_RSP
        The received C-MOVE-RSP message.
    """
    cs = evt.message.command_set

    identifier = 'None'
    if evt.data_set and evt.data_set.getvalue() != b'':
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

# DIMSE-N
def send_n_event_report_rq(evt):
    """Debugging function when an N-EVENT-REPORT-RQ is sent.

    Parameters
    ----------
    evt : dimse_messages.N_EVENT_REPORT_RQ
        The N-EVENT-REPORT-RQ message to be sent.
    """
    cs = evt.message.command_set

    evt_info = 'None'
    if evt.data_set and evt.data_set.getvalue() != b'':
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

def send_n_event_report_rsp(evt):
    """Debugging function when an N-EVENT-REPORT-RSP is sent.

    Parameters
    ----------
    evt : dimse_messages.N_EVENT_REPORT_RSP
        The N-EVENT-REPORT-RSP message to be sent.
    """
    cs = evt.message.command_set

    evt_reply = 'None'
    if evt.data_set and evt.data_set.getvalue() != b'':
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

def send_n_get_rq(evt):
    """Debugging function when an N-GET-RQ is sent.

    Parameters
    ----------
    evt : dimse_messages.N_GET_RQ
        The N-GET-RQ message to be sent.
    """
    cs = evt.message.command_set

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

def send_n_get_rsp(evt):
    """Debugging function when an N-GET-RSP is sent.

    Parameters
    ----------
    evt : dimse_messages.N_GET_RSP
        The N-GET-RSP message to be sent.
    """
    cs = evt.message.command_set

    attr_list = 'None'
    if evt.data_set and evt.data_set.getvalue() != b'':
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

def send_n_set_rq(evt):
    """Debugging function when an N-SET-RQ is sent.

    Parameters
    ----------
    evt : dimse_messages.N_SET_RQ
        The N-SET-RQ message to be sent.
    """
    cs = evt.message.command_set

    mod_list = 'None'
    if evt.data_set and evt.data_set.getvalue() != b'':
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

def send_n_set_rsp(evt):
    """Debugging function when an N-SET-RSP is sent.

    Parameters
    ----------
    evt : dimse_messages.N_SET_RSP
        The N-SET-RSP message to be sent.
    """
    cs = evt.message.command_set

    attr_list = 'None'
    if evt.data_set and evt.data_set.getvalue() != b'':
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

def send_n_action_rq(evt):
    """Debugging function when an N-ACTION-RQ is sent.

    Parameters
    ----------
    evt : dimse_messages.N_ACTION_RQ
        The N-ACTION-RQ message to be sent.
    """
    pass

def send_n_action_rsp(evt):
    """Debugging function when an N-ACTION-RSP is sent.

    Parameters
    ----------
    evt : dimse_messages.N_ACTION_RSP
        The N-ACTION-RSP message to be sent.
    """
    pass

def send_n_create_rq(evt):
    """Debugging function when an N-CREATE-RQ is sent.

    Parameters
    ----------
    evt : dimse_messages.N_CREATE_RQ
        The N-CREATE-RQ message to be sent.
    """
    pass

def send_n_create_rsp(evt):
    """Debugging function when an N-CREATE-RSP is sent.

    Parameters
    ----------
    evt : dimse_messages.N_CREATE_RSP
        The N-CREATE-RSP message to be sent.
    """
    pass

def send_n_delete_rq(evt):
    """Debugging function when an N-DELETE-RQ is sent.

    Parameters
    ----------
    evt : dimse_messages.N_DELETE_RQ
        The N-DELETE-RQ message to be sent.
    """
    cs = evt.message.command_set

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

def send_n_delete_rsp(evt):
    """Debugging function when an N-DELETE-RSP is sent.

    Parameters
    ----------
    evt : dimse_messages.N_DELETE_RSP
        The N-DELETE-RSP message to be sent.
    """
    cs = evt.message.command_set

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

def recv_n_event_report_rq(evt):
    """Debugging function when an N-EVENT-REPORT-RQ is received.

    Parameters
    ----------
    evt : dimse_messages.N_EVENT_REPORT_RQ
        The received N-EVENT-REPORT-RQ message.
    """
    pass

def recv_n_event_report_rsp(evt):
    """Debugging function when an N-EVENT-REPORT-RSP is received.

    Parameters
    ----------
    evt : dimse_messages.N_EVENT_REPORT_RSP
        The received N-EVENT-REPORT-RSP message.
    """
    pass

def recv_n_get_rq(evt):
    """Debugging function when an N-GET-RQ is received.

    Parameters
    ----------
    evt : dimse_messages.N_GET_RQ
        The received N-GET-RQ message.
    """
    pass

def recv_n_get_rsp(evt):
    """Debugging function when an N-GET-RSP is received.

    Parameters
    ----------
    evt : dimse_messages.N_GET_RSP
        The received N-GET-RSP message.
    """
    cs = evt.message.command_set

    dataset = 'None'
    if evt.data_set and evt.data_set.getvalue() != b'':
        dataset = 'Present'

    LOGGER.info('Received Get Response')
    s = []
    s.append(
        '===================== INCOMING DIMSE MESSAGE ===================='
    )
    s.append('Message Type                  : {0!s}'.format('N-GET RSP'))
    s.append('Presentation Context ID       : {0!s}'
             .format(evt.context_id))
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

def recv_n_set_rq(evt):
    """Debugging function when an N-SET-RQ is received.

    Parameters
    ----------
    evt : dimse_messages.N_SET_RQ
        The received N-SET-RQ message.
    """
    pass

def recv_n_set_rsp(evt):
    """Debugging function when an N-SET-RSP is received.

    Parameters
    ----------
    evt : dimse_messages.N_SET_RSP
        The received N-SET-RSP message.
    """
    pass

def recv_n_action_rq(evt):
    """Debugging function when an N-ACTION-RQ is received.

    Parameters
    ----------
    evt : dimse_messages.N_ACTION_RQ
        The received N-ACTION-RQ message.
    """
    pass

def recv_n_action_rsp(evt):
    """Debugging function when an N-ACTION-RSP is received.

    Parameters
    ----------
    evt : dimse_messages.N_ACTION_RSP
        The received N-ACTION-RSP message.
    """
    pass

def recv_n_create_rq(evt):
    """Debugging function when an N-CREATE-RQ is received.

    Parameters
    ----------
    evt : dimse_messages.N_CREATE_RQ
        The received N-CREATE-RQ message.
    """
    pass

def recv_n_create_rsp(evt):
    """Debugging function when an N-CREATE-RSP is received.

    Parameters
    ----------
    evt : dimse_messages.N_CREATE_RSP
        The received N-CREATE-RSP message.
    """
    pass

def recv_n_delete_rq(evt):
    """Debugging function when an N-DELETE-RQ is received.

    Parameters
    ----------
    evt : dimse_messages.N_DELETE_RQ
        The received N-DELETE-RQ message.
    """
    pass

def recv_n_delete_rsp(evt):
    """Debugging function when an N-DELETE-RSP is received.

    Parameters
    ----------
    evt : dimse_messages.N_DELETE_RSP
        The received N-DELETE-RSP message.
    """
    pass
