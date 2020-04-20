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


LOGGER = logging.getLogger('pynetdicom.acse')


class ACSE(object):
    """The Association Control Service Element (ACSE) service provider.

    The ACSE protocol handles association negotiation and establishment, and
    normal and abnormal release of an association.
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
    def acceptor(self):
        """Return the *acceptor* :class:`~pynetdicom.association.ServiceUser`.
        """
        return self.assoc.acceptor

    @property
    def acse_timeout(self):
        """Return the ACSE timeout (in seconds)."""
        return self.assoc.acse_timeout

    @property
    def assoc(self):
        """Return the parent :class:`~pynetdicom.association.Association`.

        .. versionadded:: 1.3
        """
        return self._assoc

    def _check_async_ops(self):
        """Check the user's response to an Asynchronous Operations request.

        .. currentmodule:: pynetdicom.pdu_primitives

        Returns
        -------
        pdu_primitives.AsynchronousOperationsWindowNegotiation or None
            If the ``evt.EVT_ASYNC_OPS`` handler hasn't been implemented
            then returns ``None``, otherwise returns an
            :class:`AsynchronousOperationsWindowNegotiation` item with the
            default values for the number of operations invoked/performed
            (1, 1).
        """
        # pylint: disable=broad-except
        try:
            # Response is always ignored as async ops is not supported
            inv, perf = self.requestor.asynchronous_operations
            _ = evt.trigger(
                self.assoc,
                evt.EVT_ASYNC_OPS,
                {'nr_invoked' : inv, 'nr_performed' : perf}
            )
        except NotImplementedError:
            return None
        except Exception as exc:
            LOGGER.error(
                "Exception raised in handler bound to 'evt.EVT_ASYNC_OPS'"
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
            rsp = evt.trigger(
                self.assoc,
                evt.EVT_SOP_COMMON,
                {'items' : self.requestor.sop_class_common_extended}
            )
        except Exception as exc:
            LOGGER.error(
                "Exception raised in handler bound to 'evt.EVT_SOP_COMMON'"
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
                "Invalid type returned by handler bound to "
                "'evt.EVT_SOP_COMMON'"
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
            user_response = evt.trigger(
                self.assoc,
                evt.EVT_SOP_EXTENDED,
                {'app_info' : self.requestor.sop_class_extended}
            )
        except Exception as exc:
            user_response = {}
            LOGGER.error(
                "Exception raised in handler bound to 'evt.EVT_SOP_EXTENDED'"
            )
            LOGGER.exception(exc)

        if not isinstance(user_response, (type(None), dict)):
            LOGGER.error(
                "Invalid type returned by handler bount to "
                "'evt.EVT_SOP_EXTENDED'"
            )
            user_response = {}

        if not user_response:
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
        req = self.requestor.user_identity
        try:
            identity_verified, response = evt.trigger(
                self.assoc,
                evt.EVT_USER_ID,
                {
                    'user_id_type' : req.user_identity_type,
                    'primary_field' : req.primary_field,
                    'secondary_field' : req.secondary_field,
                }
            )
        except NotImplementedError:
            # If the user hasn't implemented identity negotiation then
            #   default to accepting the association
            return True, None
        except Exception as exc:
            # If the user has implemented identity negotiation but an exception
            #   occurred then reject the association
            LOGGER.error("Exception in handler bound to 'evt.EVT_USER_ID'")
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

    @property
    def dul(self):
        """Return the :class:`~pynetdicom.dul.DULServiceProvider`."""
        return self.assoc.dul

    def is_aborted(self, abort_type='both'):
        """Return ``True`` if an A-ABORT and/or A-P-ABORT request has been
        received.

        .. versionchanged:: 1.5

            Added `abort_type` keyword parameter.

        Parameters
        ----------
        abort_type : str, optional
            The type of abort to check for. If ``'both'`` then will return
            ``True`` if an A-ABORT or A-P-ABORT is received (default). If
            ``'a-abort'`` then will return ``True`` if an A-ABORT is received,
            if ``'a-p-abort'`` then will return ``True`` if an A-P-ABORT is
            received.

        Returns
        -------
        bool
            ``True`` if an abort is received, ``False`` otherwise.
        """
        # A-P-ABORT:
        #   Connection closed, FSM received invalid event or DUL sent A-ABORT
        abort_classes = {
            'both': (A_ABORT, A_P_ABORT),
            'a-abort': (A_ABORT, ),
            'a-p-abort': (A_P_ABORT, ),
        }

        primitive = self.dul.peek_next_pdu()
        if isinstance(primitive, abort_classes[abort_type]):
            return True

        return False

    def is_release_requested(self):
        """Return ``True`` if an A-RELEASE request has been received.

        .. versionadded:: 1.1
        """
        primitive = self.dul.peek_next_pdu()
        if isinstance(primitive, A_RELEASE) and primitive.result is None:
            _ = self.dul.receive_pdu(wait=False)
            return True

        return False

    def negotiate_association(self):
        """Perform an association negotiation as either the *requestor* or
        *acceptor*.
        """
        if self.assoc.is_requestor:
            self._negotiate_as_requestor()
        elif self.assoc.is_acceptor:
            self._negotiate_as_acceptor()

    def _negotiate_as_acceptor(self):
        """Perform an association negotiation as the association *acceptor*.
        """
        # For convenience
        assoc_rq = self.requestor.primitive
        # Set the Requestor's AE Title
        self.requestor.ae_title = assoc_rq.calling_ae_title

        # If we reject association -> [result, source, diagnostic]
        reject_assoc_rsd = []

        # Calling AE Title not recognised
        if (self.assoc.ae.require_calling_aet and assoc_rq.calling_ae_title
                not in self.assoc.ae.require_calling_aet):
            reject_assoc_rsd = [0x01, 0x01, 0x03]

        # Called AE Title not recognised
        if (self.assoc.ae.require_called_aet and assoc_rq.called_ae_title
                != self.acceptor.ae_title):
            reject_assoc_rsd = [0x01, 0x01, 0x07]

        ## Extended Negotiation items
        # User Identity Negotiation items
        if self.requestor.user_identity:
            is_valid, id_response = self._check_user_identity()

            if not is_valid:
                # Transient, ACSE related, no reason given
                LOGGER.info("User identity failed verification")
                reject_assoc_rsd = [0x02, 0x02, 0x01]

            if id_response:
                # Add the User Identity Negotiation (response) item
                self.acceptor.add_negotiation_item(id_response)

        # SOP Class Extended Negotiation items
        for item in self._check_sop_class_extended():
            self.acceptor.add_negotiation_item(item)

        # SOP Class Common Extended Negotiation items
        #   Note: No response items are allowed
        # pylint: disable=protected-access
        self.acceptor._common_ext = self._check_sop_class_common_extended()
        # pylint: enable=protected-access

        # Asynchronous Operations Window Negotiation items
        if self.requestor.asynchronous_operations != (1, 1):
            async_rsp = self._check_async_ops()

            # Add any Async Ops (response) item
            if async_rsp:
                self.acceptor.add_negotiation_item(async_rsp)

        ## DUL Presentation Related Rejections
        # Maximum number of associations reached (local-limit-exceeded)
        active_acceptors = [
            tt for tt in self.assoc.ae.active_associations if tt.is_acceptor
        ]
        if len(active_acceptors) > self.assoc.ae.maximum_associations:
            reject_assoc_rsd = [0x02, 0x03, 0x02]

        if reject_assoc_rsd:
            # pylint: disable=no-value-for-parameter
            LOGGER.info("Rejecting Association")
            self.send_reject(*reject_assoc_rsd)
            evt.trigger(self.assoc, evt.EVT_REJECTED, {})
            self.assoc.kill()
            return

        ## Negotiate Presentation Contexts
        # SCP/SCU Role Selection Negotiation request items
        # {SOP Class UID : (SCU role, SCP role)}
        rq_roles = {
            uid:(item.scu_role, item.scp_role)
            for uid, item in self.requestor.role_selection.items()
        }

        result, ac_roles = negotiate_as_acceptor(
            assoc_rq.presentation_context_definition_list,
            self.acceptor.supported_contexts,
            rq_roles
        )

        # pylint: disable=protected-access
        # Accepted contexts are stored as {context ID : context}
        self.assoc._accepted_cx = {
            cx.context_id:cx for cx in result if cx.result == 0x00
        }
        self.assoc._rejected_cx = [cx for cx in result if cx.result != 0x00]
        # pylint: enable=protected-access

        # Add any SCP/SCU Role Selection Negotiation response items
        for item in ac_roles:
            self.acceptor.add_negotiation_item(item)

        # Send the A-ASSOCIATE (accept) primitive
        LOGGER.info("Accepting Association")
        self.send_accept()

        # Callbacks/Logging
        evt.trigger(self.assoc, evt.EVT_ACCEPTED, {})

        # Assocation established OK
        self.assoc.is_established = True
        evt.trigger(self.assoc, evt.EVT_ESTABLISHED, {})

    def _negotiate_as_requestor(self):
        """Perform an association negotiation as the association *requestor*."""
        if not self.requestor.requested_contexts:
            LOGGER.error(
                "One or more requested presentation contexts must be set "
                "prior to association negotiation"
            )
            self.assoc.kill()
            return

        # Build and send an A-ASSOCIATE (request) PDU to the peer
        self.send_request()
        evt.trigger(self.assoc, evt.EVT_REQUESTED, {})

        # Wait for response
        rsp = self.dul.receive_pdu(wait=True, timeout=self.acse_timeout)

        # Association accepted or rejected
        if isinstance(rsp, A_ASSOCIATE):
            self.acceptor.primitive = rsp
            # Accepted
            if rsp.result == 0x00:
                ## Handle SCP/SCU Role Selection response
                # Apply requestor's proposed SCP/SCU role selection (if any)
                #   to the requested contexts
                rq_roles = {
                    uid:(ii.scu_role, ii.scp_role)
                    for uid, ii in self.requestor.role_selection.items()
                }
                if rq_roles:
                    for cx in self.requestor.requested_contexts:
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
                    for uid, ii in self.acceptor.role_selection.items()
                }

                # Check the negotiated presentation contexts results and
                #   determine their agreed upon SCP/SCU roles
                negotiated_contexts = negotiate_as_requestor(
                    self.requestor.requested_contexts,
                    rsp.presentation_context_definition_results_list,
                    ac_roles
                )

                # pylint: disable=protected-access
                # Accepted contexts are stored as {context ID : context}
                self.assoc._accepted_cx = {
                    cx.context_id:cx
                    for cx in negotiated_contexts if cx.result == 0x00
                }
                self.assoc._rejected_cx = [
                    cx for cx in negotiated_contexts if cx.result != 0x00
                ]
                # pylint: enable=protected-access

                evt.trigger(self.assoc, evt.EVT_ACCEPTED, {})

                # No acceptable presentation contexts
                if not self.assoc.accepted_contexts:
                    LOGGER.error("No accepted presentation contexts")
                    self.send_abort(0x02)
                    self.assoc.is_aborted = True
                    self.assoc.is_established = False
                    evt.trigger(self.assoc, evt.EVT_ABORTED, {})
                    self.assoc.kill()
                else:
                    LOGGER.info('Association Accepted')
                    self.assoc.is_established = True
                    evt.trigger(self.assoc, evt.EVT_ESTABLISHED, {})

            elif hasattr(rsp, 'result') and rsp.result in [0x01, 0x02]:
                # 0x01 is rejected (permanent)
                # 0x02 is rejected (transient)
                LOGGER.error('Association Rejected')
                LOGGER.error(
                    'Result: {}, Source: {}'
                    .format(rsp.result_str, rsp.source_str)
                )
                LOGGER.error('Reason: {}'.format(rsp.reason_str))
                self.assoc.is_rejected = True
                self.assoc.is_established = False
                evt.trigger(self.assoc, evt.EVT_REJECTED, {})
                self.dul.kill_dul()
            else:
                LOGGER.error(
                    "Received an invalid A-ASSOCIATE response from the peer"
                )
                LOGGER.error("Aborting Association")
                self.send_abort(0x02)
                self.assoc.is_aborted = True
                self.assoc.is_established = False
                # Event handler - association aborted
                evt.trigger(self.assoc, evt.EVT_ABORTED, {})
                self.assoc.kill()

        # Association aborted
        elif isinstance(rsp, (A_ABORT, A_P_ABORT)):
            LOGGER.error("Association Aborted")
            self.assoc.is_established = False
            self.assoc.is_aborted = True
            evt.trigger(self.assoc, evt.EVT_ABORTED, {})
            self.dul.kill_dul()
        elif rsp is None:
            # ACSE timeout
            LOGGER.error(
                "ACSE timeout reached while waiting for response to "
                "association request"
            )
            self.assoc.abort()
        else:
            # Received A-RELEASE or some weird object
            self.assoc.is_established = False
            self.dul.kill_dul()

    def negotiate_release(self):
        """Negotiate association release.

        .. versionadded:: 1.1

        Once an A-RELEASE request has been sent any received P-DATA PDUs will
        be ignored.
        """
        # Send A-RELEASE request
        # Only an A-ABORT request primitive is allowed after A-RELEASE starts
        # (Part 8, Section 7.2.2)
        self.send_release(is_response=False)

        # We need to wait for a reply and need to handle:
        #   P-DATA primitives
        #   A-ABORT request primitives
        #   A-RELEASE collisions
        is_collision = False
        while True:
            primitive = self.dul.receive_pdu(
                wait=True, timeout=self.acse_timeout
            )
            if primitive is None:
                # No response received within timeout window
                LOGGER.info("Aborting Association")
                self.send_abort(0x02)
                self.assoc.is_aborted = True
                self.assoc.is_established = False
                evt.trigger(self.assoc, evt.EVT_ABORTED, {})
                self.assoc.kill()
                return

            if isinstance(primitive, (A_ABORT, A_P_ABORT)):
                # Received A-ABORT/A-P-ABORT during association release
                LOGGER.info("Association Aborted")
                self.assoc.is_aborted = True
                self.assoc.is_established = False
                evt.trigger(self.assoc, evt.EVT_ABORTED, {})
                self.assoc.kill()
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
                if self.assoc.is_requestor:
                    # Send A-RELEASE response
                    self.send_release(is_response=True)
                    # Wait for A-RELEASE response
                    continue
                # Acceptor waits for A-RELEASE response before
                #   sending their own response
            else:
                # A-RELEASE (response) received
                # If collision and we are the acceptor then we need to send
                #   the A-RELEASE (response) to the requestor
                if self.assoc.is_acceptor and is_collision:
                    self.send_release(is_response=True)

                self.assoc.is_released = True
                self.assoc.is_established = False
                evt.trigger(self.assoc, evt.EVT_RELEASED, {})
                self.assoc.kill()
                return

    @property
    def requestor(self):
        """Return the *requestor* :class:`~pynetdicom.association.ServiceUser`.
        """
        return self.assoc.requestor

    def send_abort(self, source):
        """Send an A-ABORT request to the peer.

        Parameters
        ----------
        source : int
            The source of the abort request

            - ``0x00`` - the DUL service user
            - ``0x02`` - the DUL service provider

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

        self.dul.send_pdu(primitive)
        self.assoc.is_aborted = True
        self.assoc.is_established = False

    def send_accept(self):
        """Send an A-ASSOCIATE (accept) to the peer."""
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
        primitive.calling_ae_title = self.requestor.primitive.calling_ae_title
        primitive.called_ae_title = self.requestor.primitive.called_ae_title
        primitive.result = 0x00
        primitive.result_source = 0x01

        primitive.presentation_context_definition_results_list = (
            self.assoc.accepted_contexts + self.assoc.rejected_contexts
        )

        ## User Information - PS3.7 Annex D.3.3
        primitive.user_information = self.acceptor.user_information

        self.acceptor.primitive = primitive
        self.dul.send_pdu(primitive)

    def send_ap_abort(self, reason):
        """Send an A-P-ABORT to the peer.

        Parameters
        ----------
        reason : int
            The reason for aborting the association, one of the following:

            - ``0x00`` - reason not specified
            - ``0x01`` - unrecognised PDU
            - ``0x02`` - unexpected PDU
            - ``0x04`` - unrecognised PDU parameter
            - ``0x05`` - unexpected PDU parameter
            - ``0x06`` - invalid PDU parameter value

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

        self.dul.send_pdu(primitive)
        self.assoc.is_aborted = True
        self.assoc.is_established = False

    def send_reject(self, result, source, diagnostic):
        """Send an A-ASSOCIATE (reject) to the peer.

        Parameters
        ----------
        result : int
            The association rejection:

            - ``0x01`` - rejected permanent
            - ``0x02`` - rejected transient
        source : int
            The source of the rejection:

            - ``0x01`` - DUL service user
            - ``0x02`` - DUL service provider (ACSE related)
            - ``0x03`` - DUL service provider (presentation related)
        diagnostic : int
            The reason for the rejection, if the `source` is ``0x01``:

            - ``0x01`` - no reason given
            - ``0x02`` - application context name not supported
            - ``0x03`` - calling AE title not recognised
            - ``0x07`` - called AE title not recognised

            If the `source` is ``0x02``:

            - ``0x01`` - no reason given
            - ``0x02`` - protocol version not supported

            If the `source` is ``0x03``:

            - ``0x01`` - temporary congestion
            - ``0x02`` - local limit exceeded
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

        self.acceptor.primitive = primitive
        self.dul.send_pdu(primitive)
        self.assoc.is_rejected = True
        self.assoc.is_established = False

    def send_release(self, is_response=False):
        """Send an A-RELEASE (request or response) to the peer.

        Parameters
        ----------
        is_response : bool, optional
            ``True`` to send an A-RELEASE (response) to the peer, ``False``
            to send an A-RELEASE (request) to the peer (default).
        """
        primitive = A_RELEASE()

        if is_response:
            primitive.result = "affirmative"

        self.dul.send_pdu(primitive)

    def send_request(self):
        """Send an A-ASSOCIATE (request) to the peer."""
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
        primitive.calling_ae_title = self.requestor.ae_title
        # Called AE Title is the destination DICOM AE title
        primitive.called_ae_title = self.acceptor.ae_title
        # The TCP/IP address of the source, pynetdicom includes port too
        primitive.calling_presentation_address = (
            self.requestor.address, self.requestor.port
        )
        # The TCP/IP address of the destination, pynetdicom includes port too
        primitive.called_presentation_address = (
            self.acceptor.address, self.acceptor.port
        )
        # Proposed presentation contexts
        primitive.presentation_context_definition_list = (
            self.requestor.requested_contexts
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
        primitive.user_information = self.requestor.user_information

        # Save the request primitive
        self.requestor.primitive = primitive

        # Send the A-ASSOCIATE request primitive to the peer
        self.dul.send_pdu(primitive)
