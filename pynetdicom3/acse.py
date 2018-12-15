"""
ACSE service provider
"""
import logging
import socket

from pydicom.uid import UID

from pynetdicom3 import PYNETDICOM_IMPLEMENTATION_UID
from pynetdicom3 import PYNETDICOM_IMPLEMENTATION_VERSION
from pynetdicom3.pdu_primitives import (
    A_ASSOCIATE, A_RELEASE, A_ABORT, A_P_ABORT,
    MaximumLengthNotification,
    ImplementationClassUIDNotification,
    ImplementationVersionNameNotification,
    SCP_SCU_RoleSelectionNegotiation,
)
from pynetdicom3.presentation import (
    negotiate_as_requestor, negotiate_as_acceptor
)
from pynetdicom3.utils import pretty_bytes


LOGGER = logging.getLogger('pynetdicom3.acse')

# DICOM Application Context Name - see Part 7, Annex A.2.1
APPLICATION_CONTEXT_NAME = UID('1.2.840.10008.3.1.1.1')


class ACSE(object):
    """The Association Control Service Element (ACSE) service provider.

    The ACSE protocol handles association establishment, normal release of an
    association and the abnormal release of an association.

    Attributes
    ----------
    acse_timeout : int, optional
        The maximum time (in seconds) to wait for association related PDUs
        from the peer (default: 30)
    """
    def __init__(self, acse_timeout=30):
        """Create the ACSE provider.

        Parameters
        ----------
        acse_timeout : int, optional
            The maximum time (in seconds) to wait for A-ASSOCIATE related PDUs
            from the peer (default: 30)
        """
        # Maximum time for response from peer (in seconds)
        self.acse_timeout = acse_timeout

    @staticmethod
    def is_aborted(assoc):
        """Return True if an A-ABORT request has been received."""
        primitive = assoc.dul.peek_next_pdu()
        if primitive.__class__ in (A_ABORT, A_P_ABORT):
            return True

        return False

    @staticmethod
    def is_released(assoc):
        """Return True if an A-RELEASE request has been received."""
        primitive = assoc.dul.peek_next_pdu()
        if primitive.__class__ == A_RELEASE:
            # Make sure this is an A-RELEASE request primitive
            #   response primitives have the Result field as 'affirmative'
            if primitive.result == 'affirmative':
                return False

            return True

        return False


    def negotiate_association(self, assoc):
        if not assoc.mode:
            raise ValueError("No Association `mode` has been set")

        if assoc.mode == "requestor":
            self._negotiate_as_requestor(assoc)
        elif assoc.mode == "acceptor":
            self._negotiate_as_acceptor(assoc)

    def _negotiate_as_acceptor(self, assoc):
        pass

    # Replacement for request_association
    def _negotiate_as_requestor(self, assoc):
        """Send an A-ASSOCIATE (request) primitive to the peer AE and
        handle the response.

        Parameters
        ----------
        assoc
        """
        if not assoc.requested_contexts:
            LOGGER.error(
                "One or more requested presentation contexts must be set "
                "prior to requesting an association"
            )
            # Is it necessary to kill, negotiation should be fully synchronous
            assoc.kill()
            return

        # Build and send an A-ASSOCIATE (request) PDU to the peer
        self.send_request(assoc)

        # Wait for response
        rsp = assoc.dul.receive_pdu(wait=True, timeout=assoc.acse_timeout)

        # Association accepted or rejected
        if isinstance(rsp, A_ASSOCIATE):
            # Accepted
            if rsp.result == 0x00:
                # Get maximum pdu length from response
                assoc.remote['pdv_size'] = rsp.maximum_length_received

                ## Handle SCP/SCU Role Selection response
                # Apply requestor's proposed SCP/SCU role selection (if any)
                #   to the requested contexts
                rq_roles = {}
                for ii in assoc.ext_neg:
                    if isinstance(ii, SCP_SCU_RoleSelectionNegotiation):
                        roles[item.sop_class_uid] = (ii.scu_role, ii.scp_role)

                if rq_roles:
                    for cx in assoc.requested_contexts:
                        try:
                            (cx.scu_role, cx.scp_role) = rq_roles[
                                cx.abstract_syntax
                            ]
                        except KeyError:
                            pass

                # Collate the acceptor's SCP/SCU role selection responses
                ac_roles = {}
                for ii in rsp.user_information:
                    if isinstance(ii, SCP_SCU_RoleSelectionNegotiation):
                        ac_roles[ii.sop_class_uid] = (ii.scu_role, ii.scp_role)

                # Check the negotiated presentation contexts results and
                #   determine their agreed upon SCP/SCU roles
                negotiated_contexts = negotiate_as_requestor(
                    assoc.requested_contexts,
                    rsp.presentation_context_definition_results_list,
                    ac_roles
                )

                assoc.accepted_contexts = [
                    cx for cx in negotiated_contexts if cx.result == 0x00
                ]
                assoc.rejected_contexts = [
                    cx for cx in negotiated_contexts if cx.result != 0x00
                ]

                assoc.debug_association_accepted(rsp)
                assoc.ae.on_association_accepted(rsp)

                # No acceptable presentation contexts
                if not assoc.accepted_contexts:
                    LOGGER.error("No accepted presentation contexts")
                    assoc.is_aborted = True
                    assoc.is_established = False
                    self.send_abort(assoc, source=0x02, reason=0x00)
                    assoc.kill()
                else:
                    assoc.is_established = True

            elif rsp.result in [0x01, 0x02]:
                # 0x01 is rejected (permanent)
                # 0x02 is rejected (transient)
                assoc.ae.on_association_rejected(rsp)
                assoc.debug_association_rejected(rsp)
                assoc.is_rejected = True
                assoc.is_established = False
                assoc.dul.kill_dul()
            else:
                LOGGER.error(
                    "Received an invalid A-ASSOCIATE 'Result' value from "
                    "the peer: '0x{:02x}'".format(rsp.result)
                )
                assoc.is_aborted = True
                assoc.is_established = False
                self.send_abort(assoc, source=0x02, reason=0x06)
                assoc.kill()

        # Association aborted
        elif isinstance(rsp, (A_ABORT, A_P_ABORT)):
            assoc.ae.on_association_aborted(rsp)
            assoc.debug_association_aborted(rsp)
            assoc.is_established = False
            assoc.is_aborted = True
            assoc.dul.kill_dul()
        else:
            assoc.is_established = False
            assoc.dul.kill_dul()
            LOGGER.error(
                "Received an invalid response to the A-ASSOCIATE request"
            )


    @staticmethod
    def send_abort(assoc, source):
        """Send an A-ABORT to the peer.

        Parameters
        ----------
        assoc : pynetdicom3.association.Association
            The association that is sending the A-ABORT.
        source : int
            The source of the abort request

            - 0x00 - the DUL service user
            - 0x02 - the DUL service provider

        Raises
        ------
        ValueError
            If the `source` value is invalid.
        """
        if source not in [0x00, 0x02]:
            raise ValueError("Invalid 'source' parameter value")

        # The following parameters must be set for an A-ABORT primitive
        # (* sent in A-ABORT PDU):
        #    Abort Source*
        #    Provider Reason* (not significant with source 0x00)
        primitive = A_ABORT()
        primitive.abort_source = source

        assoc.dul.send_pdu(primitive)

    @staticmethod
    def send_ap_abort(assoc, reason):
        """Send an A-P-ABORT to the peer.

        Parameters
        ----------
        assoc : pynetdicom3.association.Association
            The association that is sending the A-P-ABORT.
        reason : int
            The reason for aborting the association, one of the following:

            - 0x00 - reason not specified
            - 0x01 - unrecognised PDU
            - 0x02 - unexpected PDU
            - 0x04 - unrecognised PDU parameter
            - 0x05 - unexpected PDU parameter
            - 0x06 - invalid PDU parameter value

        Raises
        ------
        ValueError
            If the `reason` value is invalid.
        """
        if reason not in [0x00, 0x01, 0x02, 0x04, 0x05, 0x06]:
            raise ValueError("Invalid 'reason' parameter value")

        # The following parameters must be set for an A-P-ABORT primitive
        # (* sent in A-ABORT PDU):
        #    Abort Source* (always 0x02)
        #    Provider Reason*
        primitive = A_P_ABORT()
        primitive.provider_reason = reason

        assoc.dul.send_pdu(primitive)

    @staticmethod
    def send_accept(assoc):
        """Send an A-ASSOCIATE (accept) to the peer.

        Parameters
        ----------
        assoc : pynetdicom3.association.Association
            The association that is sending the A-ASSOCIATE (accept).
        """
        # The following parameters must be set for an A-ASSOCIATE (accept)
        # primitive (* sent in A-ASSOCIATE-AC PDU):
        #   Application Context Name*
        #   Calling AE Title* (but not to be tested)
        #   Called AE Title* (but not to be tested)
        #   User Information
        #       Maximum PDV Length*
        #       Implementation Class UID*
        #   Result
        #   Result Source
        #   Presentation Context Definition List Result*
        primitive = A_ASSOCIATE()
        primitive.application_context_name = APPLICATION_CONTEXT_NAME
        primitive.calling_ae_title = assoc._assoc_req.calling_ae_title
        primitive.called_ae_title = assoc._assoc_req.called_ae_title
        primitive.result = 0x00
        primitive.result_source = 0x01

        primitive.presentation_context_definition_results_list = (
            assoc.accepted_contexts
        )

        ## User Information - PS3.7 Annex D.3.3
        # Maximum Length Notification
        # Allows the acceptor to limit the size of each P-DATA PDU
        item = MaximumLengthNotification()
        item.maximum_length_received = assoc.local['pdv_size']
        primitive.user_information = [item]

        # Implementation Identification Notification
        # Implementation Class UID
        # Uniquely identifies the implementation of the acceptor
        item = ImplementationClassUIDNotification()
        item.implementation_class_uid = assoc.ae.implementation_class_uid
        primitive.user_information.append(item)

        # Implementation Version Name (optional)
        # Used to distinguish between two versions of the same implementation
        item = ImplementationVersionNameNotification()
        item.implementation_version_name = assoc.ae.implementation_version_name
        primitive.user_information.append(item)

        # Extended Negotiation items (optional)
        primitive.user_information += assoc.extended_negotiation[1]

        assoc._assoc_rsp = primitive

        assoc.dul.send_pdu(primitive)

    @staticmethod
    def send_reject(assoc, result, source, diagnostic):
        """Send an A-ASSOCIATE (reject) to the peer.

        Parameters
        ----------
        assoc : pynetdicom3.association.Association
            The association that is sending the A-ASSOCIATE (reject).
        result : int
            The association rejection:

            - 0x01 - rejected permanent
            - 0x02 - rejected transient
        source : int
            The source of the rejection:

            - 0x01 - DUL service user
            - 0x02 - DUL service provider (ACSE related)
            - 0x03 - DUL service provider (presentation related)
        diagnostic : int
            The reason for the rejection, if the source is 0x01:

            - 0x01 - no reason given
            - 0x02 - application context name not supported
            - 0x03 - calling AE title not recognised
            - 0x07 - called AE title not recognised

            If the source is 0x02:

            - 0x01 - no reason given
            - 0x02 - protocol version not supported

            If the source is 0x03:

            - 0x01 - temporary congestion
            - 0x02 - local limit exceeded
        """
        if result not in [0x01, 0x02]:
            raise ValueError("Invalid 'result' parameter value")

        VALID_REASON_DIAGNOSTIC = {
            0x01 : [0x01, 0x02, 0x03, 0x07],
            0x02 : [0x01, 0x02],
            0x03 : [0x01, 0x02],
        }

        try:
            if diagnostic not in VALID_REASON_DIAGNOSTIC[source]:
                raise ValueError(
                    "Invalid 'diagnostic' parameter value"
                )
        except KeyError:
            raise ValueError("Invalid 'source' parameter value")

        # The following parameters must be set for an A-ASSOCIATE (reject)
        # primitive (* sent in A-ASSOCIATE-RJ PDU):
        #   Application Context Name
        #   Calling AE Title
        #   Called AE Title
        #   User Information
        #   Result*
        #   Result Source*
        #   Diagnostic*
        #   Presentation Context Definition List Result
        primitive = A_ASSOCIATE()
        primitive.result = result
        primitive.result_source = source
        primitive.diagnostic = diagnostic

        assoc._assoc_rsp = primitive
        assoc.dul.send_pdu(primitive)

    @staticmethod
    def send_release(assoc, is_response=False):
        """Send an A-RELEASE (request or response) to the peer.

        Parameters
        ----------
        assoc : pynetdicom3.association.Association
            The association that is sending the A-RELEASE.
        is_response : bool, optional
            True to send an A-RELEASE (response) to the peer, False
            to send an A-RELEASE (request) to the peer (default).
        """
        primitive = A_RELEASE()

        if is_response:
            primitive.result = "affirmative"

        assoc.dul.send_pdu(primitive)

    @staticmethod
    def send_request(assoc):
        """Send an A-ASSOCIATE (request) to the peer.

        Parameters
        ----------
        assoc : pynetdicom3.association.Association
            The association that is sending the A-ASSOCIATE (request).
        """
        # The following parameters must be set for a request primitive
        # (* sent in A-ASSOCIATE-RQ PDU)
        #   Application Context Name*
        #   Calling AE Title*
        #   Called AE Title*
        #   UserInformation*
        #       Maximum PDV Length*
        #       Implementation Class UID*
        #   Calling Presentation Address
        #   Called Presentation Address
        #   Presentation Context Definition List*
        primitive = A_ASSOCIATE()
        # DICOM Application Context Name, see PS3.7 Annex A.2.1
        primitive.application_context_name = APPLICATION_CONTEXT_NAME
        # Calling AE Title is the source DICOM AE title
        primitive.calling_ae_title = assoc.local['ae_title']
        # Called AE Title is the destination DICOM AE title
        primitive.called_ae_title = assoc.remote['ae_title']
        # The TCP/IP address of the source, pynetdicom includes port too
        primitive.calling_presentation_address = (
            assoc.local['address'], assoc.local['port']
        )
        # The TCP/IP address of the destination, pynetdicom includes port too
        primitive.called_presentation_address = (
            assoc.remote['address'], assoc.remote['port']
        )
        # Proposed presentation contexts
        primitive.presentation_context_definition_list = (
            assoc.requested_contexts
        )

        ## User Information - PS3.7 Annex D.3.3
        # Maximum Length Notification
        # Allows the requestor to limit the size of each P-DATA PDU
        item = MaximumLengthNotification()
        item.maximum_length_received = assoc.local['pdv_size']
        primitive.user_information = [item]

        # Implementation Identification Notification
        # Implementation Class UID
        # Uniquely identifies the implementation of the requestor
        item = ImplementationClassUIDNotification()
        item.implementation_class_uid = assoc.ae.implementation_class_uid
        primitive.user_information.append(item)

        # Implementation Version Name (optional)
        # Used to distinguish between two versions of the same implementation
        item = ImplementationVersionNameNotification()
        item.implementation_version_name = assoc.ae.implementation_version_name
        primitive.user_information.append(item)

        # Extended Negotiation items (optional)
        primitive.user_information += assoc.extended_negotiation[0]

        # Save the request primitive
        assoc._assoc_req = primitive

        # Send the A-ASSOCIATE request primitive to the peer
        LOGGER.info("Requesting Association")
        assoc.dul.send_pdu(primitive)


    # ACSE logging/debugging functions
    # Local AE sending PDU to peer AE
    @staticmethod
    def debug_send_associate_rq(a_associate_rq):
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
        s.append('Our Implementation Version Name:   '
                 '{0!s}'.format(
            user_info.implementation_version_name.decode('ascii'))
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
        if pdu.user_information.ext_neg is not None:
            s.append('Requested Extended Negotiation:')

            for item in pdu.user_information.ext_neg:
                s.append('  Abstract Syntax: ={0!s}'.format(item.uid))
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
        if pdu.user_information.common_ext_neg is not None:
            s.append('Requested Common Extended Negotiation:')

            for item in pdu.user_information.common_ext_neg:

                s.append('  Abstract Syntax: ={0!s}'.format(item.sop_class_uid))
                s.append('  Service Class:   ='
                         '{0!s}'.format(item.service_class_uid))

                if item.related_general_sop_class_identification != []:
                    s.append('  Related General SOP Class(es):')
                    for sub_field in \
                            item.related_general_sop_class_identification:
                        s.append('    ={0!s}'.format(sub_field))
                else:
                    s.append('  Related General SOP Classes: None')
        else:
            s.append('Requested Common Extended Negotiation: None')

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
                s.append('  Positive Response requested: Yes')
            else:
                s.append('  Positive Response requested: No')
        else:
            s.append('Requested User Identity Negotiation: None')

        s.append('======================= END A-ASSOCIATE-RQ =================='
                 '====')

        for line in s:
            LOGGER.debug(line)

    @staticmethod
    def debug_send_associate_ac(a_associate_ac):
        """
        Placeholder for a function callback. Function will be called
        immediately prior to encoding and sending an A-ASSOCIATE-AC to a peer AE

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

        responding_ae = 'resp. AE Title'

        s = ['Accept Parameters:']
        s.append('====================== BEGIN A-ASSOCIATE-AC ================'
                 '=====')

        s.append('Our Implementation Class UID:      '
                 '{0!s}'.format(user_info.implementation_class_uid))
        s.append('Our Implementation Version Name:   '
                 '{0!s}'.format(
            user_info.implementation_version_name.decode('ascii'))
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
                #    ac_scp_scu_role = '{0!s}/{1!s}'.format(item.scp_role, item.scu_role)
                #s.append('    Accepted SCP/SCU Role: {0!s}'
                #         .format(ac_scp_scu_role))
                s.append('    Accepted Transfer Syntax: ={0!s}'
                         .format(item.transfer_syntax.name))

        ## Extended Negotiation
        ext_nego = 'None'
        #if assoc_ac.UserInformation.ExtendedNegotiation is not None:
        #    ext_nego = 'Yes'
        s.append('Accepted Extended Negotiation: {0!s}'.format(ext_nego))

        ## User Identity Negotiation
        usr_id = 'Yes' if user_info.user_identity is not None else 'None'

        s.append('User Identity Negotiation Response:  {0!s}'.format(usr_id))
        s.append('======================= END A-ASSOCIATE-AC =================='
                 '====')

        for line in s:
            LOGGER.debug(line)

    @staticmethod
    def debug_send_associate_rj(a_associate_rj):
        """
        Placeholder for a function callback. Function will be called
        immediately prior to encoding and sending an A-ASSOCIATE-RJ to a peer AE

        Parameters
        ----------
        a_associate_rj : pdu.A_ASSOCIATE_RJ
            The A-ASSOCIATE-RJ PDU instance
        """
        LOGGER.info("Association Rejected")

    @staticmethod
    def debug_send_data_tf(p_data_tf):
        """
        Placeholder for a function callback. Function will be called
        immediately prior to encoding and sending an P-DATA-TF to a peer AE

        Parameters
        ----------
        a_release_rq : pdu.P_DATA_TF
            The P-DATA-TF PDU instance
        """
        pass

    @staticmethod
    def debug_send_release_rq(a_release_rq):
        """
        Placeholder for a function callback. Function will be called
        immediately prior to encoding and sending an A-RELEASE-RQ to a peer AE

        Parameters
        ----------
        a_release_rq : pdu.A_RELEASE_RQ
            The A-RELEASE-RQ PDU instance
        """
        pass

    @staticmethod
    def debug_send_release_rp(a_release_rp):
        """
        Placeholder for a function callback. Function will be called
        immediately prior to encoding and sending an A-RELEASE-RP to a peer AE

        Parameters
        ----------
        a_release_rp : pdu.A_RELEASE_RP
            The A-RELEASE-RP PDU instance
        """
        pass

    @staticmethod
    def debug_send_abort(a_abort_rq):
        """
        Placeholder for a function callback. Function will be called
        immediately prior to encoding and sending an A-ABORT to a peer AE

        Parameters
        ----------
        a_abort : pdu.A_ABORT_RQ
            The A-ABORT PDU instance
        """
        LOGGER.info('Aborting Association')


    # Local AE receiving PDU from peer AE
    @staticmethod
    def debug_receive_associate_rq(a_associate_rq):
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
        their_version = 'unknown'

        if user_info.implementation_class_uid:
            their_class_uid = user_info.implementation_class_uid
        if user_info.implementation_version_name:
            their_version = user_info.implementation_version_name

        s = ['Request Parameters:']
        s.append('====================== BEGIN A-ASSOCIATE-RQ ================'
                 '=====')
        s.append('Their Implementation Class UID:    {0!s}'
                 .format(their_class_uid))
        s.append('Their Implementation Version Name: {0!s}'
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
        s.append('Presentation Contexts:')
        for item in pres_contexts:
            s.append('  Context ID:        {0!s} (Proposed)'.format(
                item.context_id)
            )
            s.append('    Abstract Syntax: ={0!s}'.format(
                item.abstract_syntax.name)
            )

            # Add SCP/SCU Role Selection Negotiation
            # Roles are: SCU, SCP/SCU, SCP, Default
            if pdu.user_information.role_selection:
                try:
                    role = pdu.user_information.role_selection[
                        item.abstract_syntax
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
            s.append('    Proposed Transfer Syntax(es):')
            for ts in item.transfer_syntax:
                s.append('      ={0!s}'.format(ts.name))

        ## Extended Negotiation
        if pdu.user_information.ext_neg is not None:
            s.append('Requested Extended Negotiation:')

            for item in pdu.user_information.ext_neg:
                s.append('  Abstract Syntax: ={0!s}'.format(item.uid))
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
        if pdu.user_information.common_ext_neg is not None:
            s.append('Requested Common Extended Negotiation:')

            for item in pdu.user_information.common_ext_neg:

                s.append('  Abstract Syntax: ={0!s}'
                         .format(item.sop_class_uid))
                s.append('  Service Class:   ={0!s}'
                         .format(item.service_class_uid))

                if item.related_general_sop_class_identification != []:
                    s.append('  Related General SOP Class(es):')
                    for sub_field in \
                                item.related_general_sop_class_identification:
                        s.append('    ={0!s}'.format(sub_field))
                else:
                    s.append('  Related General SOP Classes: None')
        else:
            s.append('Requested Common Extended Negotiation: None')

        ## Asynchronous Operations Window Negotiation
        #async_neg = 'None'
        if pdu.user_information.async_ops_window is not None:
            s.append('Requested Asynchronous Operations Window Negotiation:')
            # FIXME
        else:
            s.append('Requested Asynchronous Operations Window ' \
                     'Negotiation: None')

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

        s.append('======================= END A-ASSOCIATE-RQ =================='
                 '====')

        for line in s:
            LOGGER.debug(line)

    @staticmethod
    def debug_receive_associate_ac(a_associate_ac):
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

        #roles = (ii.abstract_syntax:ii for ii in user_info.role_selection)

        their_class_uid = 'unknown'
        their_version = 'unknown'

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
                '''
                if item.SCP is None and item.SCU is None:
                    ac_scp_scu_role = 'Default'
                    rq_scp_scu_role = 'Default'
                else:
                    ac_scp_scu_role = '{0!s}/{1!s}'.format(item.SCP, item.SCU)
                s.append('    Proposed SCP/SCU Role: {0!s}'
                         .format(rq_scp_scu_role))
                s.append('    Accepted SCP/SCU Role: {0!s}'
                         .format(ac_scp_scu_role))
                '''
                s.append('    Accepted Transfer Syntax: ={0!s}'
                         .format(item.transfer_syntax.name))


        ## Extended Negotiation
        ext_neg = 'None'
        #if assoc_ac.UserInformation.ExtendedNegotiation is not None:
        #    ext_nego = 'Yes'
        s.append('Accepted Extended Negotiation: {0!s}'.format(ext_neg))

        ## Common Extended Negotiation
        common_ext_neg = 'None'
        s.append('Accepted Common Extended Negotiation: {0!s}'
                 .format(common_ext_neg))

        ## Asynchronous Operations Negotiation
        async_neg = 'None'
        s.append('Accepted Asynchronous Operations Window Negotiation: {0!s}'
                 .format(async_neg))

        ## User Identity
        usr_id = 'Yes' if user_info.user_identity is not None else 'None'

        s.append('User Identity Negotiation Response:  {0!s}'.format(usr_id))
        s.append('======================= END A-ASSOCIATE-AC =================='
                 '====')

        for line in s:
            LOGGER.debug(line)

        LOGGER.info('Association Accepted')

    @staticmethod
    def debug_receive_associate_rj(a_associate_rj):
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
        s.append('====================== BEGIN A-ASSOCIATE-RJ ================='
                 '=====')
        s.append('Result:    {0!s}'.format(assoc_rj.result_str))
        s.append('Source:    {0!s}'.format(assoc_rj.source_str))
        s.append('Reason:    {0!s}'.format(assoc_rj.reason_str))
        s.append('======================= END A-ASSOCIATE-RJ =================='
                 '====')
        for line in s:
            LOGGER.debug(line)

    @staticmethod
    def debug_receive_data_tf(p_data_tf):
        """
        Placeholder for a function callback. Function will be called
        immediately after receiving and decoding an P-DATA-TF

        Parameters
        ----------
        p_data_tf : pdu.P_DATA_TF
            The P-DATA-TF PDU instance
        """
        pass

    @staticmethod
    def debug_receive_release_rq(a_release_rq):
        """
        Placeholder for a function callback. Function will be called
        immediately after receiving and decoding an A-RELEASE-RQ

        Parameters
        ----------
        a_release_rq : pdu.A_RELEASE_RQ
            The A-RELEASE-RQ PDU instance
        """
        pass

    @staticmethod
    def debug_receive_release_rp(a_release_rp):
        """
        Placeholder for a function callback. Function will be called
        immediately after receiving and decoding an A-RELEASE-RP

        Parameters
        ----------
        a_release_rp : pdu.A_RELEASE_RP
            The A-RELEASE-RP PDU instance
        """
        pass

    @staticmethod
    def debug_receive_abort(a_abort):
        """
        Placeholder for a function callback. Function will be called
        immediately after receiving and decoding an A-ABORT

        Parameters
        ----------
        a_abort : pdu.A_ABORT_RQ
            The A-ABORT PDU instance
        """
        s = ['Abort Parameters:']
        s.append('========================== BEGIN A-ABORT ===================='
                 '====')
        s.append('Abort Source: {0!s}'.format(a_abort.source_str))
        s.append('Abort Reason: {0!s}'.format(a_abort.reason_str))
        s.append('=========================== END A-ABORT ====================='
                 '====')
        for line in s:
            LOGGER.debug(line)
