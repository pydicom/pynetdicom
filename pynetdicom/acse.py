"""ACSE service provider"""

import logging

from pynetdicom import evt
from pynetdicom._globals import APPLICATION_CONTEXT_NAME
from pynetdicom.pdu_primitives import (
    A_ASSOCIATE, A_RELEASE, A_ABORT, A_P_ABORT,
    AsynchronousOperationsWindowNegotiation,
    SOPClassCommonExtendedNegotiation,
    SOPClassExtendedNegotiation,
    UserIdentityNegotiation,
)
from pynetdicom.presentation import (
    negotiate_as_requestor, negotiate_as_acceptor
)
from pynetdicom.utils import pretty_bytes


LOGGER = logging.getLogger('pynetdicom.acse')


class ACSE(object):
    """The Association Control Service Element (ACSE) service provider.

    The ACSE protocol handles association establishment, normal release of an
    association and the abnormal release of an association.
    """
    def __init__(self, assoc):
        """Create the ACSE service provider.

        Parameters
        ----------
        assoc : association.Association
            The Association to provide ACSE services for.
        """
        self._assoc = assoc

    @property
    def assoc(self):
        """Return the Association to provide ACSE services for."""
        return self._assoc

    def _check_async_ops(self):
        """Check the user's response to an Asynchronous Operations request.

        Returns
        -------
        pdu_primitives.AsynchronousOperationsWindowNegotiation or None
            If the `AE.on_async_ops_window` callback hasn't been implemented
            then returns None, otherwise returns an
            AsynchronousOperationsWindowNegotiation item with the default
            values for the number of operations invoked/performed (1, 1).
        """
        # pylint: disable=broad-except
        try:
            # TODO: refactor in v1.4
            # Response is always ignored as async ops is not supported
            default = evt.get_default_handler(evt.EVT_ASYNC_OPS)
            if self.assoc.get_handlers(evt.EVT_ASYNC_OPS) != default:
                inv, perf = self.assoc.requestor.asynchronous_operations
                _ = evt.trigger(
                    self.assoc,
                    evt.EVT_ASYNC_OPS,
                    {'nr_invoked' : inv, 'nr_performed' : perf}
                )
            else:
                _ = self.assoc.ae.on_async_ops_window(
                    *self.assoc.requestor.asynchronous_operations
                )
        except NotImplementedError:
            return None
        except Exception as exc:
            LOGGER.error(
                "Exception raised in user's 'on_async_ops_window' "
                "implementation"
            )
            LOGGER.exception(exc)

        item = AsynchronousOperationsWindowNegotiation()
        item.maximum_number_operations_invoked = 1
        item.maximum_number_operations_performed = 1

        return item

    def _check_sop_class_common_extended(self):
        """Check the user's response to a SOP Class Common Extended request.

        Returns
        -------
        dict
            The {SOP Class UID : SOPClassCommonExtendedNegotiation} items for
            the accepted SOP Class Common Extended negotiation items.
        """
        # pylint: disable=broad-except
        try:
            default = evt.get_default_handler(evt.EVT_SOP_COMMON)
            if self.assoc.get_handlers(evt.EVT_SOP_COMMON) != default:
                rsp = evt.trigger(
                    self.assoc,
                    evt.EVT_SOP_COMMON,
                    {'items' : self.assoc.requestor.sop_class_common_extended}
                )
            else:
                rsp = self.assoc.ae.on_sop_class_common_extended(
                    self.assoc.requestor.sop_class_common_extended
                )
        except Exception as exc:
            LOGGER.error(
                "Exception raised in user's 'on_sop_class_common_extended' "
                "implementation"
            )
            LOGGER.exception(exc)
            return {}

        try:
            rsp = {
                uid:ii for uid, ii in rsp.items()
                if isinstance(ii, SOPClassCommonExtendedNegotiation)
            }
        except Exception as exc:
            LOGGER.error(
                "Invalid type returned by user's 'evt.EVT_SOP_COMMON' handler"
            )
            LOGGER.exception(exc)
            return {}

        return rsp

    def _check_sop_class_extended(self):
        """Check the user's response to a SOP Class Extended request.

        Returns
        -------
        list of pdu_primitives.SOPClassExtendedNegotiation
            The SOP Class Extended Negotiation items to be sent in response
        """
        # pylint: disable=broad-except
        try:
            default = evt.get_default_handler(evt.EVT_SOP_EXTENDED)
            if self.assoc.get_handlers(evt.EVT_SOP_EXTENDED) != default:
                user_response = evt.trigger(
                    self.assoc,
                    evt.EVT_SOP_EXTENDED,
                    {'app_info' : self.assoc.requestor.sop_class_extended}
                )
            else:
                user_response = self.assoc.ae.on_sop_class_extended(
                    self.assoc.requestor.sop_class_extended
                )
        except Exception as exc:
            user_response = None
            LOGGER.error(
                "Exception raised in user's 'on_sop_class_extended' "
                "implementation"
            )
            LOGGER.exception(exc)

        if not isinstance(user_response, (type(None), dict)):
            LOGGER.error(
                "Invalid type returned by user's 'on_sop_class_extended' "
                "implementation"
            )
            user_response = None

        if user_response is None:
            return []

        items = []
        for sop_class, app_info in user_response.items():
            try:
                item = SOPClassExtendedNegotiation()
                item.sop_class_uid = sop_class
                item.service_class_application_information = app_info
                items.append(item)
            except Exception as exc:
                LOGGER.error(
                    "Unable to set the SOP Class Extended Negotiation "
                    "response values for the SOP Class UID {}"
                    .format(sop_class)
                )
                LOGGER.exception(exc)

        return items

    def _check_user_identity(self):
        """Check the user's response to a User Identity request.

        Returns
        -------
        bool
            True if the user identity has been confirmed, False otherwise.
        pdu_primitives.UserIdentityNegotiation or None
            The negotiation response, if a positive response is requested,
            otherwise None.
        """
        # pylint: disable=broad-except
        # The UserIdentityNegotiation (request) item
        req = self.assoc.requestor.user_identity
        try:
            default = evt.get_default_handler(evt.EVT_USER_ID)
            if self.assoc.get_handlers(evt.EVT_USER_ID) != default:
                identity_verified, response = evt.trigger(
                    self.assoc,
                    evt.EVT_USER_ID,
                    {
                        'user_id_type' : req.user_identity_type,
                        'primary_field' : req.primary_field,
                        'secondary_field' : req.secondary_field,
                    }
                )
            else:
                identity_verified, response = self.assoc.ae.on_user_identity(
                    req.user_identity_type,
                    req.primary_field,
                    req.secondary_field,
                    {
                        'requestor' : self.assoc.requestor.info,
                    }
                )
        except NotImplementedError:
            # If the user hasn't implemented identity negotiation then
            #   default to accepting the association
            return True, None
        except Exception as exc:
            # If the user has implemented identity negotiation but an exception
            #   occurred then reject the association
            LOGGER.error("Exception in handling user identity negotiation")
            LOGGER.exception(exc)
            return False, None

        if not identity_verified:
            # Reject association as the user isn't authorised
            return False, None

        if req.user_identity_type in [3, 4, 5]:
            if req.positive_response_requested and response is not None:
                try:
                    rsp = UserIdentityNegotiation()
                    rsp.server_response = response
                    return True, rsp
                except Exception as exc:
                    # > If the acceptor doesn't support user identification it
                    # > will accept the association without making a positive
                    # > response
                    LOGGER.error(
                        "Unable to set the User Identity Negotiation's "
                        "'server_response'"
                    )
                    LOGGER.exception(exc)
                    return True, None

        return True, None

    @staticmethod
    def is_aborted(assoc):
        """Return True if an A-ABORT or A-P-ABORT request has been received."""
        primitive = assoc.dul.peek_next_pdu()
        if primitive.__class__ in (A_ABORT, A_P_ABORT):
            return True

        return False

    @staticmethod
    def is_release_requested(assoc):
        """Return True if an A-RELEASE request has been received.

        Parameters
        ----------
        assoc : association.Association
            The Association instance that wants to know if an A-RELEASE
            request has been received.
        """
        primitive = assoc.dul.peek_next_pdu()
        if isinstance(primitive, A_RELEASE) and primitive.result is None:
            _ = assoc.dul.receive_pdu(wait=False)
            return True

        return False

    def negotiate_association(self, assoc):
        """Perform an association negotiation as either the requestor or
        acceptor.

        Parameters
        ----------
        assoc : association.Association
            The Association instance to perform the negotiation for.
        """
        if assoc.is_requestor:
            self._negotiate_as_requestor(assoc)
        elif assoc.is_acceptor:
            self._negotiate_as_acceptor(assoc)

    def _negotiate_as_acceptor(self, assoc):
        """Perform an association negotiation as the association acceptor.

        Parameters
        ----------
        assoc : association.Association
            The Association instance to perform the negotiation for.
        """
        # For convenience
        assoc_rq = assoc.requestor.primitive
        # Set the Requestor's AE Title
        assoc.requestor.ae_title = assoc_rq.calling_ae_title

        # If we reject association -> [result, source, diagnostic]
        reject_assoc_rsd = []

        # Calling AE Title not recognised
        if (assoc.ae.require_calling_aet and assoc_rq.calling_ae_title
                not in assoc.ae.require_calling_aet):
            reject_assoc_rsd = [0x01, 0x01, 0x03]

        # Called AE Title not recognised
        if (assoc.ae.require_called_aet and assoc_rq.called_ae_title
                != assoc.ae.ae_title):
            reject_assoc_rsd = [0x01, 0x01, 0x07]

        ## Extended Negotiation items
        # User Identity Negotiation items
        if assoc.requestor.user_identity:
            is_valid, id_response = self._check_user_identity()

            if not is_valid:
                # Transient, ACSE related, no reason given
                LOGGER.info("User identity failed verification")
                reject_assoc_rsd = [0x02, 0x02, 0x01]

            if id_response:
                # Add the User Identity Negotiation (response) item
                assoc.acceptor.add_negotiation_item(id_response)

        # SOP Class Extended Negotiation items
        for item in self._check_sop_class_extended():
            assoc.acceptor.add_negotiation_item(item)

        # SOP Class Common Extended Negotiation items
        #   Note: No response items are allowed
        # pylint: disable=protected-access
        assoc.acceptor._common_ext = (
            self._check_sop_class_common_extended()
        )
        # pylint: enable=protected-access

        # Asynchronous Operations Window Negotiation items
        if assoc.requestor.asynchronous_operations != (1, 1):
            async_rsp = self._check_async_ops()

            # Add any Async Ops (response) item
            if async_rsp:
                assoc.acceptor.add_negotiation_item(async_rsp)

        ## DUL Presentation Related Rejections
        # Maximum number of associations reached (local-limit-exceeded)
        active_acceptors = [
            tt for tt in assoc.ae.active_associations if tt.is_acceptor
        ]
        if len(active_acceptors) > assoc.ae.maximum_associations:
            reject_assoc_rsd = [0x02, 0x03, 0x02]

        if reject_assoc_rsd:
            # pylint: disable=no-value-for-parameter
            self.send_reject(assoc, *reject_assoc_rsd)
            evt.trigger(self.assoc, evt.EVT_REJECTED, {})
            assoc.ae.on_association_rejected(assoc.acceptor.primitive)
            assoc.kill()
            return

        ## Negotiate Presentation Contexts
        # SCP/SCU Role Selection Negotiation request items
        # {SOP Class UID : (SCU role, SCP role)}
        rq_roles = {
            uid:(item.scu_role, item.scp_role)
            for uid, item in assoc.requestor.role_selection.items()
        }

        result, ac_roles = negotiate_as_acceptor(
            assoc_rq.presentation_context_definition_list,
            assoc.acceptor.supported_contexts,
            rq_roles
        )

        # pylint: disable=protected-access
        # Accepted contexts are stored as {context ID : context}
        assoc._accepted_cx = {
            cx.context_id:cx for cx in result if cx.result == 0x00
        }
        assoc._rejected_cx = [cx for cx in result if cx.result != 0x00]
        # pylint: enable=protected-access

        # Add any SCP/SCU Role Selection Negotiation response items
        for item in ac_roles:
            assoc.acceptor.add_negotiation_item(item)

        # Send the A-ASSOCIATE (accept) primitive
        self.send_accept(assoc)

        # Callbacks/Logging
        assoc.ae.on_association_accepted(assoc.acceptor.primitive)
        evt.trigger(self.assoc, evt.EVT_ACCEPTED, {})

        # Assocation established OK
        assoc.is_established = True
        evt.trigger(self.assoc, evt.EVT_ESTABLISHED, {})

    def _negotiate_as_requestor(self, assoc):
        """Perform an association negotiation as the association requestor.

        Parameters
        ----------
        assoc : association.Association
            The Association instance to perform the negotiation for.
        """
        if not assoc.requestor.requested_contexts:
            LOGGER.error(
                "One or more requested presentation contexts must be set "
                "prior to association negotiation"
            )
            assoc.kill()
            return

        # Build and send an A-ASSOCIATE (request) PDU to the peer
        self.send_request(assoc)
        evt.trigger(self.assoc, evt.EVT_REQUESTED, {})

        # Wait for response
        rsp = assoc.dul.receive_pdu(wait=True, timeout=assoc.acse_timeout)

        # Association accepted or rejected
        if isinstance(rsp, A_ASSOCIATE):
            assoc.acceptor.primitive = rsp
            # Accepted
            if rsp.result == 0x00:
                ## Handle SCP/SCU Role Selection response
                # Apply requestor's proposed SCP/SCU role selection (if any)
                #   to the requested contexts
                rq_roles = {
                    uid:(ii.scu_role, ii.scp_role)
                    for uid, ii in assoc.requestor.role_selection.items()
                }
                if rq_roles:
                    for cx in assoc.requestor.requested_contexts:
                        try:
                            (cx.scu_role, cx.scp_role) = rq_roles[
                                cx.abstract_syntax
                            ]
                            # If no role was specified then use False
                            #   see SCP_SCU_RoleSelectionSubItem.from_primitive
                            cx.scu_role = cx.scu_role or False
                            cx.scp_role = cx.scp_role or False
                        except KeyError:
                            pass

                # Collate the acceptor's SCP/SCU role selection responses
                ac_roles = {
                    uid:(ii.scu_role, ii.scp_role)
                    for uid, ii in assoc.acceptor.role_selection.items()
                }

                # Check the negotiated presentation contexts results and
                #   determine their agreed upon SCP/SCU roles
                negotiated_contexts = negotiate_as_requestor(
                    assoc.requestor.requested_contexts,
                    rsp.presentation_context_definition_results_list,
                    ac_roles
                )

                # pylint: disable=protected-access
                # Accepted contexts are stored as {context ID : context}
                assoc._accepted_cx = {
                    cx.context_id:cx
                    for cx in negotiated_contexts if cx.result == 0x00
                }
                assoc._rejected_cx = [
                    cx for cx in negotiated_contexts if cx.result != 0x00
                ]
                # pylint: enable=protected-access

                assoc.ae.on_association_accepted(rsp)
                evt.trigger(self.assoc, evt.EVT_ACCEPTED, {})

                # No acceptable presentation contexts
                if not assoc.accepted_contexts:
                    LOGGER.error("No accepted presentation contexts")
                    self.send_abort(assoc, 0x02)
                    assoc.is_aborted = True
                    assoc.is_established = False
                    evt.trigger(self.assoc, evt.EVT_ABORTED, {})
                    assoc.kill()
                else:
                    assoc.is_established = True
                    evt.trigger(self.assoc, evt.EVT_ESTABLISHED, {})

            elif hasattr(rsp, 'result') and rsp.result in [0x01, 0x02]:
                # 0x01 is rejected (permanent)
                # 0x02 is rejected (transient)
                assoc.ae.on_association_rejected(rsp)
                assoc.is_rejected = True
                assoc.is_established = False
                evt.trigger(self.assoc, evt.EVT_REJECTED, {})
                assoc.dul.kill_dul()
            else:
                LOGGER.warning(
                    "Received an invalid A-ASSOCIATE response from the peer"
                )
                self.send_abort(assoc, 0x02)
                assoc.is_aborted = True
                assoc.is_established = False
                # Event handler - association aborted
                evt.trigger(self.assoc, evt.EVT_ABORTED, {})
                assoc.kill()

        # Association aborted
        elif isinstance(rsp, (A_ABORT, A_P_ABORT)):
            assoc.ae.on_association_aborted(rsp)
            assoc.is_established = False
            assoc.is_aborted = True
            evt.trigger(self.assoc, evt.EVT_ABORTED, {})
            assoc.dul.kill_dul()
        else:
            assoc.is_established = False
            assoc.dul.kill_dul()

    def negotiate_release(self, assoc):
        """Negotiate association release.

        Once an A-RELEASE request has been sent any received P-DATA PDUs will
        be ignored.

        Parameters
        ----------
        assoc : association.Association
            The association instance that wants to initiate association
            release.
        """
        # Send A-RELEASE request
        # Only an A-ABORT request primitive is allowed after A-RELEASE starts
        # (Part 8, Section 7.2.2)
        self.send_release(assoc, is_response=False)

        # We need to wait for a reply and need to handle:
        #   P-DATA primitives
        #   A-ABORT request primitives
        #   A-RELEASE collisions
        is_collision = False
        while True:
            primitive = assoc.dul.receive_pdu(wait=True,
                                              timeout=assoc.acse_timeout)
            if primitive is None:
                # No response received within timeout window
                self.send_abort(assoc, 0x02)
                assoc.is_aborted = True
                assoc.is_established = False
                evt.trigger(self.assoc, evt.EVT_ABORTED, {})
                assoc.kill()
                return

            if isinstance(primitive, (A_ABORT, A_P_ABORT)):
                # Received A-ABORT/A-P-ABORT during association release
                assoc.is_aborted = True
                assoc.is_established = False
                evt.trigger(self.assoc, evt.EVT_ABORTED, {})
                assoc.kill()
                return

            # Any other primitive besides A_RELEASE gets trashed
            elif not isinstance(primitive, A_RELEASE):
                # Should only be P-DATA
                LOGGER.warning(
                    "P-DATA received after Association release, data has "
                    "been lost"
                )
                continue

            # Must be A-RELEASE, but may be either request or release
            if primitive.result is None:
                # A-RELEASE (request) received, therefore an
                # A-RELEASE collision has occurred (Part 8, Section 7.2.2.7)
                LOGGER.debug("An A-RELEASE collision has occurred")
                is_collision = True
                if assoc.is_requestor:
                    # Send A-RELEASE response
                    self.send_release(assoc, is_response=True)
                    # Wait for A-RELEASE response
                    continue
                # Acceptor waits for A-RELEASE response before
                #   sending their own response
            else:
                # A-RELEASE (response) received
                # If collision and we are the acceptor then we need to send
                #   the A-RELEASE (response) to the requestor
                if assoc.is_acceptor and is_collision:
                    self.send_release(assoc, is_response=True)

                assoc.is_released = True
                assoc.is_established = False
                evt.trigger(self.assoc, evt.EVT_RELEASED, {})
                assoc.kill()
                return

    @staticmethod
    def send_abort(assoc, source):
        """Send an A-ABORT request to the peer.

        Parameters
        ----------
        assoc : pynetdicom.association.Association
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
        assoc.is_aborted = True
        assoc.is_established = False

    @staticmethod
    def send_accept(assoc):
        """Send an A-ASSOCIATE (accept) to the peer.

        Parameters
        ----------
        assoc : pynetdicom.association.Association
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
        primitive.calling_ae_title = assoc.requestor.primitive.calling_ae_title
        primitive.called_ae_title = assoc.requestor.primitive.called_ae_title
        primitive.result = 0x00
        primitive.result_source = 0x01

        primitive.presentation_context_definition_results_list = (
            assoc.accepted_contexts
        )

        ## User Information - PS3.7 Annex D.3.3
        primitive.user_information = assoc.acceptor.user_information

        assoc.acceptor.primitive = primitive
        assoc.dul.send_pdu(primitive)

    @staticmethod
    def send_ap_abort(assoc, reason):
        """Send an A-P-ABORT to the peer.

        Parameters
        ----------
        assoc : pynetdicom.association.Association
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
        assoc.is_aborted = True
        assoc.is_established = False

    @staticmethod
    def send_reject(assoc, result, source, diagnostic):
        """Send an A-ASSOCIATE (reject) to the peer.

        Parameters
        ----------
        assoc : pynetdicom.association.Association
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

        _valid_reason_diagnostic = {
            0x01 : [0x01, 0x02, 0x03, 0x07],
            0x02 : [0x01, 0x02],
            0x03 : [0x01, 0x02],
        }

        try:
            if diagnostic not in _valid_reason_diagnostic[source]:
                raise ValueError(
                    "Invalid 'diagnostic' parameter value"
                )
        except KeyError:
            raise ValueError("Invalid 'source' parameter value")

        # The following parameters must be set for an A-ASSOCIATE (reject)
        # primitive (* sent in A-ASSOCIATE-RJ PDU):
        #   Result*
        #   Result Source*
        #   Diagnostic*
        primitive = A_ASSOCIATE()
        primitive.result = result
        primitive.result_source = source
        primitive.diagnostic = diagnostic

        assoc.acceptor.primitive = primitive
        assoc.dul.send_pdu(primitive)
        assoc.is_rejected = True
        assoc.is_established = False

    @staticmethod
    def send_release(assoc, is_response=False):
        """Send an A-RELEASE (request or response) to the peer.

        Parameters
        ----------
        assoc : pynetdicom.association.Association
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
        assoc : pynetdicom.association.Association
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
        primitive.calling_ae_title = assoc.requestor.ae_title
        # Called AE Title is the destination DICOM AE title
        primitive.called_ae_title = assoc.acceptor.ae_title
        # The TCP/IP address of the source, pynetdicom includes port too
        primitive.calling_presentation_address = (
            assoc.requestor.address, assoc.requestor.port
        )
        # The TCP/IP address of the destination, pynetdicom includes port too
        primitive.called_presentation_address = (
            assoc.acceptor.address, assoc.acceptor.port
        )
        # Proposed presentation contexts
        primitive.presentation_context_definition_list = (
            assoc.requestor.requested_contexts
        )

        ## User Information - PS3.7 Annex D.3.3
        # Mandatory items:
        #   Maximum Length Notification (1)
        #   Implementation Class UID Notification (1)
        # Optional notification items:
        #   Implementation Version Name Notification (0 or 1)
        # Optional negotiation items:
        #   SCP/SCU Role Selection Negotiation (0 or N)
        #   Asynchronous Operations Window Negotiation (0 or 1)
        #   SOP Class Extended Negotiation (0 or N)
        #   SOP Class Common Extended Negotiation (0 or N)
        #   User Identity Negotiation (0 or 1)
        primitive.user_information = assoc.requestor.user_information

        # Save the request primitive
        assoc.requestor.primitive = primitive

        # Send the A-ASSOCIATE request primitive to the peer
        LOGGER.info("Requesting Association")
        assoc.dul.send_pdu(primitive)
