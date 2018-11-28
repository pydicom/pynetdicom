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


class ACSE(object):
    """The Association Control Service Element (ACSE) service provider.

    The ACSE protocol handles association establishment, normal release of an
    association and the abnormal release of an association.

    Attributes
    ----------
    acse_timeout : int, optional
        The maximum time (in seconds) to wait for A-ASSOCIATE related PDUs
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

    def abort_assoc(self, source=0x02, reason=0x00):
        """Abort the Association with the peer Application Entity.

        ACSE issued A-ABORT request primitive to the DICOM UL service provider.
        The source may be either the DUL service user or provider.

        See PS3.8 7.3-4 and 9.3.8

        Parameters
        ----------
        source : int, optional
            The source of the abort request (default: 0x02 DUL provider)

            - 0x00 - the DUL service user
            - 0x02 - the DUL service provider
        reason : int, optional
            The reason for aborting the association (default: 0x00 reason not
            specified).

            If source 0x00 (DUL user):

            - 0x00 - reason field not significant

            If source 0x02 (DUL provider):

            - 0x00 - reason not specified
            - 0x01 - unrecognised PDU
            - 0x02 - unexpected PDU
            - 0x04 - unrecognised PDU parameter
            - 0x05 - unexpected PDU parameter
            - 0x06 - invalid PDU parameter value
        """
        primitive = A_ABORT()

        if source in [0x00, 0x02]:
            primitive.abort_source = source
            if source == 0x00:
                primitive.reason = 0x00
            elif reason in [0x00, 0x01, 0x02, 0x04, 0x05, 0x06]:
                primitive.reason = reason
            else:
                raise ValueError("acse.abort_assoc() invalid reason "
                                 "'{0!s}'".format(reason))

        else:
            raise ValueError("acse.abort_assoc() invalid source "
                             "'{0!s}'".format(source))

        self.dul.send_pdu(primitive)

    def accept_assoc(self, primitive):
        """Accept an Association with a peer Application Entity SCU,

        Issues an A-ASSOCIATE response primitive to the DICOM UL service
        provider. The response will be that the association request is
        accepted

        When an AE gets a connection on its listen socket it creates an
        Association instance which creates an ACSE instance and forwards
        the socket onwards (`client_socket`).

        Waits for an association request from a remote AE. Upon reception
        of the request sends association response based on
        AcceptablePresentationContexts

        The acceptability of the proposed Transfer Syntax is checked in the
        order of appearance in the local AE's SupportedTransferSyntax list

        Parameters
        ----------
        primitive : pdu_primitives.A_ASSOCIATE
            The A_ASSOCIATE (AC) primitive to convert and send to the peer
        """
        # FIXME: This is weird, refactor
        self.local_max_pdu = primitive.maximum_length_received
        self.parent.local_max_pdu = primitive.maximum_length_received

        # Send response
        primitive.presentation_context_definition_list = []
        primitive.presentation_context_definition_results_list = (
            self.accepted_contexts + self.rejected_contexts
        )
        primitive.result = 0

        self.dul.send_pdu(primitive)
        return primitive

    @property
    def application_context_name(self):
        """Return the application context name UID"""
        # DICOM Application Context Name, see PS3.7 Annex A.2.1
        #   UID for the DICOM Application Context Name
        return UID('1.2.840.10008.3.1.1.1')

    @property
    def dul(self):
        """Return the DUL Service Provider."""
        return self.parent.dul

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

    def reject_assoc(self, primitive, result, source, diagnostic):
        """Reject an Association with a peer Application Entity SCU.

        Issues an A-ASSOCIATE response primitive to the DICOM UL service
        provider. The response will be that the association request is
        rejected

        Parameters
        ----------
        assoc_primtive : pdu_primitives.A_ASSOCIATE
            The Association request primitive to be rejected
        result : int
            The association rejection: 0x01 or 0x02
        source : int
            The source of the rejection: 0x01, 0x02, 0x03
        diagnostic : int
            The reason for the rejection: 0x01 to 0x10
        """
        # Check valid Result and Source values
        if result not in [0x01, 0x02]:
            raise ValueError("ACSE rejection: invalid Result value " \
                             "'{0!s}'".format(result))

        if source not in [0x01, 0x02, 0x03]:
            raise ValueError("ACSE rejection: invalid Source value "
                             "'{0!s}'".format(source))

        # Send an A-ASSOCIATE primitive, rejecting the association
        primitive.presentation_context_definition_list = []
        primitive.presentation_context_definition_results_list = []
        primitive.result = result
        primitive.result_source = source
        primitive.diagnostic = diagnostic
        primitive.user_information = []

        self.dul.send_pdu(primitive)

        return primitive

    def release_assoc(self):
        """Release the Association with the peer Application Entity.

        Issues an A-RELEASE request primitive to the DICOM UL service provider

        The graceful release of an association between two AEs shall be
        performed through ACSE A-RELEASE request, indication, response and
        confirmation primitives.

        Requests the release of the associations and waits for confirmation.
        A-RELEASE always gives a reason of 'normal' and a result of
        'affirmative'.

        Returns
        -------
        pdu_primitives.A_RELEASE
            The A-RELEASE response primitive
        """
        LOGGER.info("Releasing Association")
        primitive = A_RELEASE()
        self.dul.send_pdu(primitive)

        return self.dul.receive_pdu(wait=True, timeout=self.acse_timeout)

    def request_assoc(self, local_ae, peer_ae, max_pdu_size, pcdl,
                      userspdu=None):
        """Request an Association with a peer Application Entity SCP.

        Issues an A-ASSOCIATE request primitive to the DICOM UL service
        provider

        Requests an association with a remote AE and waits for association
        response (local AE is acting as an SCU)

        Parameters
        ----------
        local_ae : dict
            Contains information about the local AE, keys 'ae_title', 'port',
            'address', 'pdv_size'.
        peer_ae : dict
            Contains information about the peer AE, keys 'ae_title', 'port',
            'address'.
        max_pdu_size : int
            Maximum PDU size in bytes
        pcdl : list of presentation.PresentationContext
            A list of the proposed Presentation Contexts for the association
            If local_ae is ApplicationEntity then this is doubled up
            unnecessarily
        userpdu : list of UserInformation objects
            List of items to be added to the requests user information for use
            in extended negotiation. See PS3.7 Annex D.3.3

        Returns
        -------
        bool
            True if the Association was accepted, False if rejected or aborted
        """
        self.local_ae = local_ae
        self.local_ae['pdv_size'] = max_pdu_size
        self.remote_ae = peer_ae

        self.local_max_pdu = max_pdu_size

        ## Build an A-ASSOCIATE request primitive
        #
        # The following parameters must be set for a request primitive
        #   ApplicationContextName
        #   CallingAETitle
        #   CalledAETitle
        #   UserInformation
        #       Maximum PDV Length (required)
        #       Implementation Identification - Class UID (required)
        #   CallingPresentationAddress
        #   CalledPresentationAddress
        #   PresentationContextDefinitionList
        assoc_rq = A_ASSOCIATE()
        assoc_rq.application_context_name = self.application_context_name
        assoc_rq.calling_ae_title = self.local_ae['ae_title']
        assoc_rq.called_ae_title = self.remote_ae['ae_title']

        # Build User Information - PS3.7 Annex D.3.3
        #
        # Maximum Length Negotiation (required)
        max_length = MaximumLengthNotification()
        max_length.maximum_length_received = self.local_ae['pdv_size']
        assoc_rq.user_information = [max_length]

        # Implementation Identification Notification (required)
        # Class UID (required)
        implementation_class_uid = ImplementationClassUIDNotification()
        implementation_class_uid.implementation_class_uid = UID(
            PYNETDICOM_IMPLEMENTATION_UID
        )
        assoc_rq.user_information.append(implementation_class_uid)

        # Version Name (optional)
        implementation_version_name = ImplementationVersionNameNotification()
        implementation_version_name.implementation_version_name = (
            PYNETDICOM_IMPLEMENTATION_VERSION
        )
        assoc_rq.user_information.append(implementation_version_name)

        # Add the extended negotiation information (optional)
        if userspdu is not None:
            assoc_rq.user_information += userspdu

        assoc_rq.calling_presentation_address = (self.local_ae['address'],
                                                 self.local_ae['port'])
        assoc_rq.called_presentation_address = (self.remote_ae['address'],
                                                self.remote_ae['port'])
        assoc_rq.presentation_context_definition_list = pcdl
        ## A-ASSOCIATE request primitive is now complete

        # Send the A-ASSOCIATE request primitive to the peer via the
        #   DICOM UL service
        LOGGER.info("Requesting Association")
        self.dul.send_pdu(assoc_rq)

        ## Receive the response from the peer
        #   This may be an A-ASSOCIATE confirmation primitive or an
        #   A-ABORT or A-P-ABORT request primitive
        #
        assoc_rsp = self.dul.receive_pdu(wait=True, timeout=self.acse_timeout)

        # Association accepted or rejected
        if isinstance(assoc_rsp, A_ASSOCIATE):
            # Accepted
            if assoc_rsp.result == 0x00:
                # Get maximum pdu length from answer
                self.peer_max_pdu = assoc_rsp.maximum_length_received
                self.parent.peer_ae['pdv_size'] = (
                    assoc_rsp.maximum_length_received
                )
                # FIXME
                self.parent.peer_max_pdu = assoc_rsp.maximum_length_received

                ac_roles = {}
                for ii in assoc_rsp.user_information:
                    if isinstance(ii, SCP_SCU_RoleSelectionNegotiation):
                        ac_roles[ii.sop_class_uid] = (ii.scu_role, ii.scp_role)

                # Check the negotiated Presentation Contexts
                results = negotiate_as_requestor(
                    pcdl,
                    assoc_rsp.presentation_context_definition_results_list,
                    ac_roles
                )

                self.accepted_contexts = [
                    cx for cx in results if cx.result == 0x00
                ]
                self.rejected_contexts = [
                    cx for cx in results if cx.result != 0x00
                ]

                return True, assoc_rsp

            # Rejected
            elif assoc_rsp.result in [0x01, 0x02]:
                # 0x01 is rejected (permanent)
                # 0x02 is rejected (transient)
                return False, assoc_rsp
            # Invalid Result value
            elif assoc_rsp.result is None:
                return False, assoc_rsp
            else:
                LOGGER.error("ACSE received an invalid result value from "
                             "the peer AE: '%s'", assoc_rsp.result)
                raise ValueError("ACSE received an invalid result value from "
                                 "the peer AE: '{}'".format(assoc_rsp.result))

        # Association aborted
        elif isinstance(assoc_rsp, (A_ABORT, A_P_ABORT)):
            return False, assoc_rsp

        elif assoc_rsp is None:
            return False, assoc_rsp

        else:
            raise ValueError("Unexpected response by the peer AE to the "
                             "ACSE association request")


    # Deprecated
    def CheckRelease(self):
        """Checks for release request from the remote AE. Upon reception of
        the request a confirmation is sent"""
        rel = self.dul.peek_next_pdu()
        if rel.__class__ == A_RELEASE:
            # Make sure this is a A-RELEASE request primitive
            if rel.result == 'affirmative':
                return False

            self.dul.receive_pdu(wait=False)
            release_rsp = A_RELEASE()
            release_rsp.result = "affirmative"
            self.dul.send_pdu(release_rsp)

            return True

        return False

    def CheckAbort(self):
        """Checks for abort indication from the remote AE. """
        # Abort is a non-confirmed service so no need to worry if its a request
        #   primitive
        primitive = self.dul.peek_next_pdu()
        if primitive.__class__ in (A_ABORT, A_P_ABORT):
            self.dul.receive_pdu(wait=False)
            return True

        return False


    # New hotness
    def negotiate_association(self, assoc):
        if not assoc.mode:
            raise ValueError("No Association `mode` has been set")

        if assoc.mode == "requestor":
            self._negotiate_as_requestor(assoc)
        elif assoc.mode == "acceptor":
            self._negotiate_as_acceptor(assoc)

    def _negotiate_as_acceptor(self, assoc):
        pass

    def _negotiate_as_requestor(self, assoc):
        """
        Parameters
        ----------

        """
        if not assoc.requested_contexts:
            LOGGER.error(
                "One or more requested presentation contexts must be set "
                "prior to requesting an association"
            )
            assoc.kill()
            return

        # Send A-ASSOCIATE (request) PDU to the peer
        self.send_request(assoc)

        # Wait for response
        assoc_rsp = assoc.dul.receive_pdu(wait=True, timeout=self.acse_timeout)

        # Association accepted or rejected
        if isinstance(assoc_rsp, A_ASSOCIATE):
            # Accepted
            if assoc_rsp.result == 0x00:
                # Get maximum pdu length from answer
                assoc.remote['pdv_size'] = assoc_rsp.maximum_length_received

                ## Handle SCP/SCU Role Selection response
                # Apply requestor's SCP/SCU role selection (if any)
                rq_roles = {}
                for ii in assoc.ext_neg:
                    if isinstance(ii, SCP_SCU_RoleSelectionNegotiation):
                        roles[item.sop_class_uid] = (ii.scu_role, ii.scp_role)

                if rq_roles:
                    for cx in assoc.requested_contexts:
                        try:
                            (cx.scu_role, cx.scp_role) = rq_roles[cx.abstract_syntax]
                        except KeyError:
                            pass

                ac_roles = {}
                for ii in assoc_rsp.user_information:
                    if isinstance(ii, SCP_SCU_RoleSelectionNegotiation):
                        ac_roles[ii.sop_class_uid] = (ii.scu_role, ii.scp_role)

                # Check the negotiated Presentation Contexts
                results = negotiate_as_requestor(
                    assoc.requested_contexts,
                    assoc_rsp.presentation_context_definition_results_list,
                    ac_roles
                )

                assoc.accepted_contexts = [
                    cx for cx in results if cx.result == 0x00
                ]
                assoc.rejected_contexts = [
                    cx for cx in results if cx.result != 0x00
                ]

                is_accepted = True
                assoc.debug_association_accepted(assoc_rsp)
                assoc.ae.on_association_accepted(assoc_rsp)

                # No acceptable presentation contexts
                if assoc.accepted_contexts == []:
                    LOGGER.error("No Acceptable Presentation Contexts")
                    assoc.is_aborted = True
                    assoc.is_established = False
                    assoc.acse.abort_assoc(0x02, 0x00)
                    assoc.kill()

                    return

                # Assocation established OK
                assoc.is_established = True
            elif assoc_rsp.result in [0x01, 0x02]:
                # 0x01 is rejected (permanent)
                # 0x02 is rejected (transient)
                assoc.ae.on_association_rejected(assoc_rsp)
                assoc.debug_association_rejected(assoc_rsp)
                assoc.is_rejected = True
                assoc.is_established = False
                assoc.dul.kill_dul()

                is_accepted = False
            else:
                msg = (
                    "Received an invalid A-ASSOCIATE 'result' value from "
                    "the peer: '{}'".format(assoc_rsp.result)
                )
                LOGGER.error(msg)
                assoc.dul.kill_dul()

        # Association aborted or no response
        elif isinstance(assoc_rsp, A_ABORT):
            assoc.ae.on_association_aborted(assoc_rsp)
            assoc.debug_association_aborted(assoc_rsp)
            assoc.is_established = False
            assoc.is_aborted = True
            assoc.dul.kill_dul()
        elif isinstance(assoc_rsp, A_P_ABORT):
            assoc.is_aborted = True
            assoc.is_established = False
            assoc.dul.kill_dul()
        else:
            assoc.is_established = False
            assoc.dul.kill_dul()
            LOGGER.error(
                "Received an invalid response to the A-ASSOCIATE (request)"
            )


    @staticmethod
    def send_abort(assoc, source, reason):
        """Send an A-ABORT to the peer.

        Parameters
        ----------
        assoc : pynetdicom3.association.Association
            The association that is sending the A-ABORT.
        source : int
            The source of the abort request

            - 0x00 - the DUL service user
            - 0x02 - the DUL service provider
        reason : int
            The reason for aborting the association. If `source` is 0x00
            (DUL user):

            - 0x00 - reason field not significant

            If `source` is 0x02 (DUL provider):

            - 0x00 - reason not specified
            - 0x01 - unrecognised PDU
            - 0x02 - unexpected PDU
            - 0x04 - unrecognised PDU parameter
            - 0x05 - unexpected PDU parameter
            - 0x06 - invalid PDU parameter value

        Raises
        ------
        ValueError
            If the `source` or `reason` values are invalid.
        """
        if source not in [0x00, 0x02]:
            raise ValueError()

        primitive = A_ABORT()
        primitive.abort_source = source

        if source == 0x00:
            primitive.reason = 0x00
        elif reason in [0x00, 0x01, 0x02, 0x04, 0x05, 0x06]:
            primitive.reason = reason
        else:
            raise ValueError()

        assoc.dul.send_pdu(primitive)

    @staticmethod
    def send_accept(assoc):
        """Send an A-ASSOCIATE (accept) to the peer.

        Parameters
        ----------
        assoc : pynetdicom3.association.Association
            The association that is sending the A-ASSOCIATE (accept).
        """
        primitive = None
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
            The association rejection: 0x01 or 0x02
        source : int
            The source of the rejection: 0x01, 0x02, 0x03
        diagnostic : int
            The reason for the rejection: 0x01 to 0x10
        """
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
        #   ApplicationContextName
        #   CallingAETitle
        #   CalledAETitle
        #   UserInformation
        #       Maximum PDV Length (required)
        #       Implementation Identification - Class UID (required)
        #   CallingPresentationAddress
        #   CalledPresentationAddress
        #   PresentationContextDefinitionList
        primitive = A_ASSOCIATE()
        # DICOM Application Context Name, see PS3.7 Annex A.2.1
        primitive.application_context_name = UID('1.2.840.10008.3.1.1.1')
        # Source DICOM AE title
        primitive.calling_ae_title = assoc.local['ae_title']
        # Destination DICOM AE title
        primitive.called_ae_title = assoc.remote['ae_title']
        # The TCP/IP address of the source
        primitive.calling_presentation_address = (
            assoc.local['address'], assoc.local['port']
        )
        # The TCP/IP address of the destination
        primitive.called_presentation_address = (
            assoc.remote['address'], assoc.remote['port']
        )
        # Proposed presentation contexts
        primitive.presentation_context_definition_list = (
            assoc.requested_contexts
        )

        ## User Information - PS3.7 Annex D.3.3
        # Notification items
        # Maximum Length Notification (required)
        item = MaximumLengthNotification()
        item.maximum_length_received = assoc.local['pdv_size']
        primitive.user_information = [item]

        # Implementation Identification Notification (required)
        # Class UID (required)
        item = ImplementationClassUIDNotification()
        item.implementation_class_uid = assoc.ae.implementation_class_uid
        primitive.user_information.append(item)

        # Version Name (optional)
        item = ImplementationVersionNameNotification()
        item.implementation_version_name = assoc.ae.implementation_version_name
        primitive.user_information.append(item)

        # Extended Negotiation items (optional)
        primitive.user_information += assoc.extended_negotiation[0]

        # Send the A-ASSOCIATE request primitive to the peer
        assoc._assoc_req = primitive
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
