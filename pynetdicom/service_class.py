"""Implements the supported Service Classes."""

from io import BytesIO
import logging
import sys
import traceback

from pydicom.dataset import Dataset

from pynetdicom import _config, evt
from pynetdicom.dsutils import decode, encode
from pynetdicom.dimse_primitives import (
    C_STORE, C_ECHO, C_MOVE, C_GET, C_FIND, C_CANCEL,
    N_ACTION, N_CREATE, N_DELETE, N_EVENT_REPORT, N_GET, N_SET
)
from pynetdicom._globals import (
    STATUS_FAILURE, STATUS_SUCCESS, STATUS_WARNING, STATUS_PENDING,
    STATUS_CANCEL,
)
from pynetdicom.status import (
    GENERAL_STATUS,
    QR_FIND_SERVICE_CLASS_STATUS,
    QR_GET_SERVICE_CLASS_STATUS,
    QR_MOVE_SERVICE_CLASS_STATUS,
    MODALITY_WORKLIST_SERVICE_CLASS_STATUS,
    NON_PATIENT_SERVICE_CLASS_STATUS,
    RELEVANT_PATIENT_SERVICE_CLASS_STATUS,
    SUBSTANCE_ADMINISTRATION_SERVICE_CLASS_STATUS,
    STORAGE_SERVICE_CLASS_STATUS,
    VERIFICATION_SERVICE_CLASS_STATUS,
)


LOGGER = logging.getLogger('pynetdicom.service-c')


class ServiceClass(object):
    """The base class for all the service classes.

    Attributes
    ----------
    assoc : association.Association
        The association instance offering the service.
    """
    statuses = GENERAL_STATUS

    def __init__(self, assoc):
        """Create a new ServiceClass."""
        self.assoc = assoc

    @property
    def ae(self):
        """Return the AE."""
        return self.assoc.ae

    def _c_find_scp(self, req, context):
        """Implementation of the DIMSE C-FIND service.

        Parameters
        ----------
        req : dimse_primitives.C_FIND
            The C-FIND request primitive received from the peer.
        context : presentation.PresentationContext
            The presentation context that the SCP is operating under.

        See Also
        --------
        association.Association.send_c_find

        Notes
        -----
        **C-FIND Request**

        *Parameters*

        | (M) Message ID
        | (M) Affected SOP Class UID
        | (M) Priority
        | (M) Identifier

        **C-FIND Response**

        *Parameters*

        | (U) Message ID
        | (M) Message ID Being Responded To
        | (U) Affected SOP Class UID
        | (C) Identifier
        | (M) Status

        *Status*

        Success
          | ``0x0000`` Success

        Pending
          | ``0xFF00`` Matches are continuing, current match supplied
          | ``0xFF01`` Matches are continuing, warning

        Cancel
          | ``0xFE00`` Cancel

        Failure
          | ``0x0122`` SOP class not supported
          | ``0xA700`` Out of resources
          | ``0xA900`` Identifier does not match SOP class
          | ``0xC000`` to ``0xCFFF`` Unable to process

        References
        ----------
        .. [1] DICOM Standard, Part 4, `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_C>`_.
        .. [1] DICOM Standard, Part 4, `Annex CC <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_CC>`_.
        .. [2] DICOM Standard, Part 7, Sections
           `9.1.2 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.1.2>`_,
           `9.3.2 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.2>`_
           and `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_.
        """
        # Build C-FIND response primitive
        rsp = C_FIND()
        rsp.MessageID = req.MessageID
        rsp.MessageIDBeingRespondedTo = req.MessageID
        rsp.AffectedSOPClassUID = req.AffectedSOPClassUID

        # Decode and log Identifier
        transfer_syntax = context.transfer_syntax[0]
        try:
            identifier = decode(req.Identifier,
                                transfer_syntax.is_implicit_VR,
                                transfer_syntax.is_little_endian)
            LOGGER.info('Find SCP Request Identifiers:')
            LOGGER.info('')
            LOGGER.debug('# DICOM Dataset')
            for elem in identifier.iterall():
                LOGGER.info(elem)
            LOGGER.info('')
        except Exception as ex:
            LOGGER.error("Failed to decode the request's Identifier dataset.")
            LOGGER.exception(ex)
            # Failure - Unable to Process - Failed to decode Identifier
            rsp.Status = 0xC310
            rsp.ErrorComment = 'Unable to decode the dataset'
            self.dimse.send_msg(rsp, context.context_id)
            return

        # Pass the C-FIND request to the user to handle
        try:
            handler = evt.trigger(
                self.assoc,
                evt.EVT_C_FIND,
                {
                    'request' : req,
                    'context' : context.as_tuple,
                    '_is_cancelled' : self.is_cancelled
                }
            )
        except Exception as exc:
            LOGGER.error("Exception in handler bound to 'evt.EVT_C_FIND'")
            LOGGER.exception(exc)
            rsp.Status = 0xC311
            self.dimse.send_msg(rsp, context.context_id)
            return

        # No matches and no yields
        if handler is None:
            handler = iter([(0x0000, None)])

        ii = -1  # So if there are no results, log below doesn't break
        # Iterate through the results
        for ii, (rsp_status, rsp_identifier) in enumerate(self._wrap_handler(handler)):
            # Exception raised by user's generator
            if isinstance(rsp_status, Exception):
                LOGGER.error(
                    "Exception raised by user's C-FIND request handler",
                    exc_info=rsp_identifier)
                rsp_status = 0xC311

            # Validate rsp_status and set rsp.Status accordingly
            rsp = self.validate_status(rsp_status, rsp)

            if rsp.Status in self.statuses:
                status = self.statuses[rsp.Status]
            else:
                # Unknown status
                self.dimse.send_msg(rsp, context.context_id)
                return

            if status[0] == STATUS_CANCEL:
                # If cancel, then rsp_identifier is None
                LOGGER.info('Received C-CANCEL-FIND RQ from peer')
                LOGGER.info('Find SCP Response: (Cancel)')
                self.dimse.send_msg(rsp, context.context_id)
                return
            elif status[0] == STATUS_FAILURE:
                # If failed, then rsp_identifier is None
                LOGGER.info('Find SCP Response: (Failure - %s)', status[1])
                self.dimse.send_msg(rsp, context.context_id)
                return
            elif status[0] == STATUS_SUCCESS:
                # User isn't supposed to send these, but handle anyway
                # If success, then rsp_identifier is None
                LOGGER.info('Find SCP Response: %s (Success)', ii + 1)
                self.dimse.send_msg(rsp, context.context_id)
                return
            elif status[0] == STATUS_PENDING:
                # If pending, the rsp_identifier is the Identifier dataset
                bytestream = encode(rsp_identifier,
                                    transfer_syntax.is_implicit_VR,
                                    transfer_syntax.is_little_endian)
                bytestream = BytesIO(bytestream)

                if bytestream.getvalue() == b'':
                    LOGGER.error("Failed to encode the received Identifier "
                                 "dataset")
                    # Failure: Unable to Process - Can't decode dataset
                    #   returned by handler
                    rsp.Status = 0xC312
                    self.dimse.send_msg(rsp, context.context_id)
                    return

                rsp.Identifier = bytestream

                LOGGER.info('Find SCP Response: %s (Pending)', ii + 1)
                LOGGER.debug('Find SCP Response Identifier:')
                LOGGER.debug('')
                LOGGER.debug('# DICOM Dataset')
                for elem in rsp_identifier.iterall():
                    LOGGER.debug(elem)
                LOGGER.debug('')

                self.dimse.send_msg(rsp, context.context_id)

            # Reset the response Identifier
            rsp.Identifier = None

        # Send final success response
        rsp.Status = 0x0000
        LOGGER.info('Find SCP Response: %s (Success)', ii + 2)
        self.dimse.send_msg(rsp, context.context_id)

    @property
    def dimse(self):
        """Return the DIMSE service provider."""
        return self.assoc.dimse

    def is_cancelled(self, msg_id):
        """Return True if a C-CANCEL message with `msg_id` has been received.

        Parameters
        ----------
        msg_id : int
            The (0000,0120) *Message ID Being Responded To* value to use to
            match against.

        Returns
        -------
        bool
            True if a C-CANCEL message has been received with a *Message ID
            Being Responded To* corresponding to `msg_id`, False otherwise.
        """
        if msg_id in self.dimse.cancel_req.keys():
            del self.dimse.cancel_req[msg_id]
            return True

        return False

    def is_valid_status(self, status):
        """Return True if `status` is valid for the service class.

        Parameters
        ----------
        status : int
            The Status value to check for validity.

        Returns
        -------
        bool
            True if the status is valid, False otherwise.
        """
        if status in self.statuses:
            return True

        return False

    def _n_action_scp(self, req, context):
        """Implementation of the DIMSE N-ACTION service.

        Parameters
        ----------
        req : dimse_primitives.N_ACTION
            The N-ACTION request primitive sent by the peer.
        context : presentation.PresentationContext
            The presentation context that the SCP is operating under.

        Notes
        -----

        **Service Classes**

        * *Print Management*
        * *Storage Commitment*
        * *Application Event Logging*
        * *Media Creation Management*
        * *Unified Procedure Step*
        * *RT Machine Verification*

        **N-ACTION Request**

        *Parameters*

        | (M) Message ID
        | (M) Requested SOP Class UID
        | (M) Requested SOP Instance UID
        | (M) Action Type ID
        | (U) Action Information

        **N-ACTION Response**

        *Parameters*

        | (M) Message ID Being Responded To
        | (C=) Action Type ID
        | (U) Affected SOP Class UID
        | (U) Affected SOP Instance UID
        | (C) Action Reply
        | (M) Status

        *Status*

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

        References
        ----------

        * DICOM Standard, Part 4, `Annex H <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_H>`_
        * DICOM Standard, Part 4, `Annex J <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_J>`_
        * DICOM Standard, Part 4, `Annex P <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_P>`_
        * DICOM Standard, Part 4, `Annex S <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_S>`_
        * DICOM Standard, Part 4, `Annex CC <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_CC>`_
        * DICOM Standard, Part 4, `Annex DD <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_DD>`_
        * DICOM Standard, Part 7, Sections
          `10.1.5 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_10.1.5>`_,
          `10.3.5 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_10.3.5>`_
          and `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_
        """
        # Build N-CREATE response primitive
        rsp = N_ACTION()
        rsp.MessageIDBeingRespondedTo = req.MessageID
        rsp.AffectedSOPClassUID = req.RequestedSOPClassUID
        rsp.AffectedSOPInstanceUID = req.RequestedSOPInstanceUID
        rsp.ActionTypeID = req.ActionTypeID

        try:
            status, ds = evt.trigger(
                self.assoc,
                evt.EVT_N_ACTION,
                {'request' : req, 'context' : context.as_tuple}
            )
        except Exception as exc:
            LOGGER.error(
                "Exception in the handler bound to 'evt.EVT_N_ACTION"
            )
            LOGGER.exception(exc)
            rsp.Status = 0x0110
            self.dimse.send_msg(rsp, context.context_id)
            return

        # Check Status validity
        # Validate rsp_status and set rsp.Status accordingly
        rsp = self.validate_status(status, rsp)

        if rsp.Status in self.statuses:
            status = self.statuses[rsp.Status]
        else:
            # Unknown status
            self.dimse.send_msg(rsp, context.context_id)
            return

        if status[0] in (STATUS_SUCCESS, STATUS_WARNING) and ds:
            # If Success or Warning then there **may** be a dataset
            transfer_syntax = context.transfer_syntax[0]
            # If encode() fails then returns `None`
            bytestream = encode(ds,
                                transfer_syntax.is_implicit_VR,
                                transfer_syntax.is_little_endian)

            if bytestream is None:
                LOGGER.error(
                    "Failed to encode the N-ACTION response's 'Action Reply' "
                    "dataset"
                )
                # Processing failure
                rsp.Status = 0x0110
            else:
                rsp.ActionReply = BytesIO(bytestream)

        # Send response primitive
        self.dimse.send_msg(rsp, context.context_id)

    def _n_create_scp(self, req, context):
        """Implementation of the DIMSE N-CREATE service.

        Parameters
        ----------
        req : dimse_primitives.N_CREATE
            The N-CREATE request primitive sent by the peer.
        context : presentation.PresentationContext
            The presentation context that the SCP is operating under.

        Notes
        -----

        **Service Classes**

        * *Procedure Step*
        * *Print Management*
        * *Instance Availability Notification*
        * *Media Creation Management*
        * *Unified Procedure Step*
        * *RT Machine Verification*

        **N-CREATE Request**

        *Parameters*

        | (M) Message ID
        | (M) Affected SOP Class UID
        | (U) Affected SOP Instance UID
        | (U) Attribute List

        **N-CREATE Response**

        *Parameters*

        | (M) Message ID Being Responded To
        | (U=) Affected SOP Class UID
        | (C) Affected SOP Instance UID
        | (U) Attribute List
        | (M) Status

        *Status*

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
          | ``0xA510`` - Failed: an initiate media creation action has already
            been received for this SOP Instance
          | ``0xC221`` - The Referenced Fraction Group Number does not exist in
            the referenced plan
          | ``0xC222`` - No beams exist within the referenced fraction group
          | ``0xC223`` - SCU already verifying and cannot currently process
            this request
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

        References
        ----------

        * DICOM Standard, Part 4, `Annex F <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_F>`_
        * DICOM Standard, Part 4, `Annex H <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_H>`_
        * DICOM Standard, Part 4, `Annex R <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_R>`_
        * DICOM Standard, Part 4, `Annex S <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_S>`_
        * DICOM Standard, Part 4, `Annex CC <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_CC>`_
        * DICOM Standard, Part 4, `Annex DD <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_DD>`_
        * DICOM Standard, Part 7, Sections
          `10.1.5 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_10.1.5>`_,
          `10.3.5 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_10.3.5>`_
          and `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_
        """
        # Build N-CREATE response primitive
        rsp = N_CREATE()
        rsp.MessageIDBeingRespondedTo = req.MessageID
        rsp.AffectedSOPClassUID = req.AffectedSOPClassUID
        rsp.AffectedSOPInstanceUID = req.AffectedSOPInstanceUID

        try:
            status, ds = evt.trigger(
                self.assoc,
                evt.EVT_N_CREATE,
                {'request' : req, 'context' : context.as_tuple}
            )
        except Exception as exc:
            LOGGER.error(
                "Exception in the handler bound to 'evt.EVT_N_CREATE"
            )
            LOGGER.exception(exc)
            rsp.Status = 0x0110
            self.dimse.send_msg(rsp, context.context_id)
            return

        # Check Status validity
        # Validate rsp_status and set rsp.Status accordingly
        rsp = self.validate_status(status, rsp)

        if rsp.Status in self.statuses:
            status = self.statuses[rsp.Status]
        else:
            # Unknown status
            self.dimse.send_msg(rsp, context.context_id)
            return

        if status[0] in (STATUS_SUCCESS, STATUS_WARNING) and ds:
            # If Success or Warning then there **may** be a dataset
            transfer_syntax = context.transfer_syntax[0]
            # If encode() fails then returns `None`
            bytestream = encode(ds,
                                transfer_syntax.is_implicit_VR,
                                transfer_syntax.is_little_endian)

            if bytestream is None:
                LOGGER.error(
                    "Failed to encode the N-CREATE response's 'Attribute "
                    "List' dataset"
                )
                # Processing failure
                rsp.Status = 0x0110
            else:
                rsp.AttributeList = BytesIO(bytestream)

        # Send response primitive
        self.dimse.send_msg(rsp, context.context_id)

    def _n_delete_scp(self, req, context):
        """Implementation of the DIMSE N-DELETE service.

        Parameters
        ----------
        req : dimse_primitives.N_DELETE
            The N-DELETE request primitive sent by the peer.
        context : presentation.PresentationContext
            The presentation context that the SCP is operating under.

        Notes
        -----

        **Service Classes**

        * *Print Management*
        * *RT Machine Verification*

        **N-DELETE Request**

        *Parameters*

        | (M) Message ID
        | (M) Requested SOP Class UID
        | (M) Requested SOP Instance UID

        **N-DELETE Response**

        *Parameters*

        | (M) Message ID Being Responded To
        | (U) Affected SOP Class UID
        | (U) Affected SOP Instance UID
        | (M) Status

        *Status*

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

        References
        ----------

        * DICOM Standard, Part 4, `Annex H <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_H>`_
        * DICOM Standard, Part 4, `Annex DD <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_DD>`_
        * DICOM Standard, Part 7, Sections
          `10.1.6 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_10.1.6>`_,
          `10.3.6 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_10.3.6>`_
          and `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_
        """
        # Build N-DELETE response primitive
        rsp = N_DELETE()
        rsp.MessageIDBeingRespondedTo = req.MessageID
        rsp.AffectedSOPClassUID = req.RequestedSOPClassUID
        rsp.AffectedSOPInstanceUID = req.RequestedSOPInstanceUID

        try:
            status = evt.trigger(
                self.assoc,
                evt.EVT_N_DELETE,
                {'request' : req, 'context' : context.as_tuple}
            )
        except Exception as exc:
            LOGGER.error(
                "Exception in the handler bound to 'evt.EVT_N_DELETE"
            )
            LOGGER.exception(exc)
            rsp.Status = 0x0110
            self.dimse.send_msg(rsp, context.context_id)
            return

        # Check Status validity
        # Validate 'status' and set 'rsp.Status' accordingly
        rsp = self.validate_status(status, rsp)

        # Send response primitive
        self.dimse.send_msg(rsp, context.context_id)

    def _n_event_report_scp(self, req, context):
        """Implementation of the DIMSE N-EVENT-REPORT service.

        Parameters
        ----------
        req : dimse_primitives.N_EVENT_REPORT
            The N-EVENT-REPORT request primitive sent by the peer.
        context : presentation.PresentationContext
            The presentation context that the SCP is operating under.

        Notes
        -----

        **Service Classes**

        * *Procedure Step*
        * *Print Management*
        * *Storage Commitment*
        * *Unified Procedure Step*
        * *RT Machine Verification*

        **N-EVENT-REPORT Request**

        *Parameters*

        | (M) Message ID
        | (M) Affected SOP Class UID
        | (M) Affected SOP Instance UID
        | (M) Event Type ID
        | (U) Event Information

        **N-EVENT-REPORT Response**

        *Parameters*

        | (M) Message ID Being Responded To
        | (U=) Affected SOP Class UID
        | (U=) Affected SOP Instance UID
        | (C=) Event Type ID
        | (C) Event Reply
        | (M) Status

        *Status*

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

        References
        ----------

        * DICOM Standard, Part 4, `Annex F <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_F>`_
        * DICOM Standard, Part 4, `Annex H <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_H>`_
        * DICOM Standard, Part 4, `Annex J <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_J>`_
        * DICOM Standard, Part 4, `Annex CC <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_CC>`_
        * DICOM Standard, Part 4, `Annex DD <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_DD>`_
        * DICOM Standard, Part 7, Sections
          `10.1.1 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_10.1.1>`_,
          `10.3.1 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_10.3.1>`_
          and `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_
        """
        # Build N-EVENT-REPLY response primitive
        rsp = N_EVENT_REPORT()
        rsp.MessageIDBeingRespondedTo = req.MessageID
        rsp.AffectedSOPClassUID = req.AffectedSOPClassUID
        rsp.AffectedSOPInstanceUID = req.AffectedSOPInstanceUID
        rsp.EventTypeID = req.EventTypeID

        try:
            status, ds = evt.trigger(
                self.assoc,
                evt.EVT_N_EVENT_REPORT,
                {'request' : req, 'context' : context.as_tuple}
            )
        except Exception as exc:
            LOGGER.error(
                "Exception in the handler bound to 'evt.EVT_N_EVENT_REPORT"
            )
            LOGGER.exception(exc)
            rsp.Status = 0x0110
            self.dimse.send_msg(rsp, context.context_id)
            return

        # Check Status validity
        # Validate rsp_status and set rsp.Status accordingly
        rsp = self.validate_status(status, rsp)

        if rsp.Status in self.statuses:
            status = self.statuses[rsp.Status]
        else:
            # Unknown status
            self.dimse.send_msg(rsp, context.context_id)
            return

        if status[0] in (STATUS_SUCCESS, STATUS_WARNING) and ds:
            # If Success or Warning then there **may** be a dataset
            transfer_syntax = context.transfer_syntax[0]
            # If encode() fails then returns `None`
            bytestream = encode(ds,
                                transfer_syntax.is_implicit_VR,
                                transfer_syntax.is_little_endian)

            if bytestream is None:
                LOGGER.error(
                    "Failed to encode the N-EVENT-REPORT response's 'Event "
                    "Reply' dataset"
                )
                # Processing failure
                rsp.Status = 0x0110
            else:
                rsp.EventReply = BytesIO(bytestream)

        # Send response primitive
        self.dimse.send_msg(rsp, context.context_id)

    def _n_get_scp(self, req, context):
        """Implementation of the DIMSE N-GET service.

        Parameters
        ----------
        req : dimse_primitives.N_GET
            The N-GET request primitive sent by the peer.
        context : presentation.PresentationContext
            The presentation context that the service is operating under.

        See Also
        --------
        association.Association.send_n_get

        Notes
        -----

        **Service Classes**

        * *Display System Management*
        * *Procedure Step*
        * *Print Management*
        * *Media Creation Management*
        * *Unified Procedure Step*
        * *RT Machine Verification*

        **N-GET Request**

        *Parameters*

        | (M) Message ID
        | (M) Requested SOP Class UID
        | (M) Requested SOP Instance UID
        | (U) Attribute Identifier List

        *Attribute Identifier List*

        An element with VR AT, VM 1-n, containing an attribute tag for each
        of the attributes applicable to the N-GET operation.

        **N-GET Response**

        *Parameters*

        | (M) Message ID Being Responded To
        | (U) Affected SOP Class UID
        | (U) Affected SOP Instance UID
        | (C) Attribute List
        | (M) Status

        *Attribute List*

        A dataset containing the values of the requested attributes.

        *Status*

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

        References
        ----------

        * DICOM Standard, Part 4, `Annex F <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_F>`_
        * DICOM Standard, Part 4, `Annex H <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_H>`_
        * DICOM Standard, Part 4, `Annex S <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_S>`_
        * DICOM Standard, Part 4, `Annex CC <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_CC>`_
        * DICOM Standard, Part 4, `Annex DD <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_DD>`_
        * DICOM Standard, Part 4, `Annex EE <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_EE>`_
        * DICOM Standard, Part 7, Sections
          `10.1.2 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_10.1.2>`_,
          `10.3.2 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_10.3.2>`_
          and `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_
        """
        # Build N-GET response primitive
        rsp = N_GET()
        rsp.MessageIDBeingRespondedTo = req.MessageID
        rsp.AffectedSOPClassUID = req.RequestedSOPClassUID
        rsp.AffectedSOPInstanceUID = req.RequestedSOPInstanceUID

        try:
            status, ds = evt.trigger(
                self.assoc,
                evt.EVT_N_GET,
                {
                    'request' : req,
                    'context' : context.as_tuple,
                }
            )
        except Exception as exc:
            LOGGER.error(
                "Exception in the handler bound to 'evt.EVT_N_GET'"
            )
            LOGGER.exception(exc)
            # Processing failure - Error in handler
            rsp.Status = 0x0110
            self.dimse.send_msg(rsp, context.context_id)
            return

        # Validate rsp_status and set rsp.Status accordingly
        rsp = self.validate_status(status, rsp)

        if rsp.Status in self.statuses:
            status = self.statuses[rsp.Status]
        else:
            # Unknown status
            self.dimse.send_msg(rsp, context.context_id)
            return

        if status[0] in [STATUS_SUCCESS, STATUS_WARNING] and ds:
            # If Success or Warning then there **may** be a dataset
            transfer_syntax = context.transfer_syntax[0]
            # If encode() fails then returns `None`
            bytestream = encode(ds,
                                transfer_syntax.is_implicit_VR,
                                transfer_syntax.is_little_endian)

            if bytestream is None:
                LOGGER.error(
                    "Failed to encode the N-GET response's 'Attribute "
                    "List' dataset"
                )
                # Processing failure - Failed to encode dataset
                rsp.Status = 0x0110
            else:
                rsp.AttributeList = BytesIO(bytestream)

        self.dimse.send_msg(rsp, context.context_id)

    def _n_set_scp(self, req, context):
        """Implementation of the DIMSE N-SET service.

        Parameters
        ----------
        req : dimse_primitives.N_SET
            The N-SET request primitive sent by the peer.
        context : presentation.PresentationContext
            The presentation context that the SCP is operating under.

        Notes
        -----

        **Service Classes**

        * *Procedure Step*
        * *Print Management*
        * *Unified Procedure Step*
        * *RT Machine Verification*

        **N-SET Request**

        *Parameters*

        | (M) Message ID
        | (M) Requested SOP Class UID
        | (M) Requested SOP Instance UID
        | (M) Modification List

        **N-SET Response**

        *Parameters*

        | (M) Message ID Being Responded To
        | (U) Attribute List
        | (U) Affected SOP Class UID
        | (U) Affected SOP Instance UID
        | (M) Status

        *Status*

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
          | ``0xC307`` - Specified SOP Instance UID does not exist or is not a
            UPS Instance managed by this SCP
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
          | ``0xB604`` - Image size larger than image box size, the image has
            been demagnified
          | ``0xB605`` - Requested Min Density or Max Density outside of
            printer's operating range. The printer will use its respective
            minimum or maximum density value instead
          | ``0xB609`` - Image size is larger than the Image Box. The Image has
            been cropped to fit
          | ``0xB60A`` - Image size or Combined Print Image size is larger than
            the Image Box size. The Image or Combined Print Image has been
            decimated to fit

        References
        ----------

        * DICOM Standard, Part 4, `Annex F <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_F>`_
        * DICOM Standard, Part 4, `Annex H <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_H>`_
        * DICOM Standard, Part 4, `Annex CC <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_CC>`_
        * DICOM Standard, Part 4, `Annex DD <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_DD>`_
        * DICOM Standard, Part 7, Sections
          `10.1.3 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_10.1.3>`_,
          `10.3.3 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_10.3.3>`_
          and `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_
        """
        # Build N-CREATE response primitive
        rsp = N_SET()
        rsp.MessageIDBeingRespondedTo = req.MessageID
        rsp.AffectedSOPClassUID = req.RequestedSOPClassUID
        rsp.AffectedSOPInstanceUID = req.RequestedSOPInstanceUID

        try:
            status, ds = evt.trigger(
                self.assoc,
                evt.EVT_N_SET,
                {'request' : req, 'context' : context.as_tuple}
            )
        except Exception as exc:
            LOGGER.error(
                "Exception in the handler bound to 'evt.EVT_N_SET"
            )
            LOGGER.exception(exc)
            rsp.Status = 0x0110
            self.dimse.send_msg(rsp, context.context_id)
            return

        # Validate rsp_status and set rsp.Status accordingly
        rsp = self.validate_status(status, rsp)

        if rsp.Status in self.statuses:
            status = self.statuses[rsp.Status]
        else:
            # Unknown status
            self.dimse.send_msg(rsp, context.context_id)
            return

        if status[0] in (STATUS_SUCCESS, STATUS_WARNING) and ds:
            # If Success or Warning then there **may** be a dataset
            transfer_syntax = context.transfer_syntax[0]
            # If encode() fails then returns `None`
            bytestream = encode(ds,
                                transfer_syntax.is_implicit_VR,
                                transfer_syntax.is_little_endian)

            if bytestream is None:
                LOGGER.error(
                    "Failed to encode the N-SET response's 'Attribute "
                    "List' dataset"
                )
                # Processing failure
                rsp.Status = 0x0110
            else:
                rsp.AttributeList = BytesIO(bytestream)

        # Send response primitive
        self.dimse.send_msg(rsp, context.context_id)

    def SCP(self, req, context):
        """The implementation of the corresponding service class.

        Parameters
        ----------
        req : A DIMSE message primitive
            The message request primitive sent by the peer.
        context : presentation.PresentationContext
            The presentation context that the SCP is operating under.
        """
        msg = (
            "No service class has been implemented for the SOP Class UID '{}'"
            .format(context.abstract_syntax)
        )
        raise NotImplementedError(msg)

    def validate_status(self, status, rsp):
        """Validate `status` and set `rsp.Status` accordingly.

        Parameters
        ----------
        status : pydicom.dataset.Dataset or int
            A Dataset containing a Status element or an int.
        rsp : dimse_primitive
            The response primitive to be sent to the peer.

        Returns
        -------
        rsp : dimse_primitive
            The response primitie to be sent to the peer (containing a valid
            Status parameter).
        """
        # Check the callback's returned Status dataset
        if isinstance(status, Dataset):
            # Check that the returned status dataset contains a Status element
            if 'Status' in status:
                # For the elements in the status dataset, try and set the
                #   corresponding response primitive attribute
                for elem in status:
                    if hasattr(rsp, elem.keyword):
                        setattr(rsp, elem.keyword, elem.value)
                    else:
                        LOGGER.warning("Status dataset returned by callback "
                                       "contained an unsupported Element "
                                       "'%s'.", elem.keyword)
            else:
                LOGGER.error("User callback returned a `Dataset` without a "
                             "Status element.")
                # Failure: Cannot Understand - callback returned
                #   a pydicom.dataset.Dataset without a Status element
                rsp.Status = 0xC001
        elif isinstance(status, int):
            rsp.Status = status
        else:
            LOGGER.error("Invalid status returned by callback")
            # Failure: Cannot Understand - callback didn't return
            #   a valid status type
            rsp.Status = 0xC002

        if not self.is_valid_status(rsp.Status):
            # Failure: Cannot Understand - Unknown status returned by the
            #   callback
            LOGGER.warning("Unknown status value returned by "
                           "callback - 0x{0:04x}".format(rsp.Status))

        return rsp

    def _wrap_handler(self, handler):
        """Wrap a generator handler to catch exceptions.

        Parameters
        ----------
        handler : generator
            A generator returned by a user's handler.

        Yields
        ------
        object or Exception, str
            The normal yields of the generator, unless an exception occurs
            within the generator in which case the exception and traceback
            are yielded instead.
        """
        try:
            for result in handler:
                yield result
        except Exception as exc:
            yield exc, traceback.print_exc()


# Service Class implementations
class VerificationServiceClass(ServiceClass):
    """Implementation of the Verification Service Class."""
    statuses = VERIFICATION_SERVICE_CLASS_STATUS

    def SCP(self, req, context):
        """The SCP implementation for the Verification Service Class.

        Will always return 0x0000 (Success) unless the user returns a different
        (valid) status value from the handler bound to `evt.EVT_C_ECHO`.

        Parameters
        ----------
        req : dimse_primitives.C_ECHO
            The C-ECHO request primitive sent by the peer.
        context : presentation.PresentationContext
            The presentation context that the SCP is operating under.

        See Also
        --------
        association.Association.send_c_echo

        Notes
        -----
        **C-ECHO Request**

        *Parameters*

        | (M) Message ID
        | (M) Affected SOP Class UID

        **C-ECHO Response**

        *Parameters*

        | (U) Message ID
        | (M) Message ID Being Responded To
        | (U) Affected SOP Class UID
        | (M) Status

        *Status*

        The DICOM Standard, Part 7 (Table 9.3-13) indicates that the Status
        value of a C-ECHO response "shall have a value of Success". However
        Section 9.1.5.1.4 indicates it may have any of the following values:

        Success
          | ``0x0000`` Success

        Failure
          | ``0x0122`` Refused: SOP Class Not Supported
          | ``0x0210`` Refused: Duplicate Invocation
          | ``0x0211`` Refused: Unrecognised Operation
          | ``0x0212`` Refused: Mistyped Argument

        References
        ----------

        * DICOM Standard, Part 4, `Annex A <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_A>`_
        * DICOM Standard, Part 7, Sections
          `9.1.5 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.1.5>`_,
          `9.3.5 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.5>`_
          and `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_
        """
        # Build C-ECHO response primitive
        rsp = C_ECHO()
        rsp.MessageID = req.MessageID
        rsp.MessageIDBeingRespondedTo = req.MessageID
        rsp.AffectedSOPClassUID = req.AffectedSOPClassUID

        try:
            status = evt.trigger(
                self.assoc,
                evt.EVT_C_ECHO,
                {'request' : req, 'context' : context.as_tuple}
            )
            if isinstance(status, Dataset):
                if 'Status' not in status:
                    raise AttributeError(
                        "The 'status' dataset returned by the handler "
                        "bound to 'evt.EVT_C_ECHO' must contain"
                        "a (0000,0900) Status element"
                    )
                for elem in status:
                    if hasattr(rsp, elem.keyword):
                        setattr(rsp, elem.keyword, elem.value)
                    else:
                        LOGGER.warning(
                            "The 'status' dataset returned by the handler "
                            "bound to 'evt.EVT_C_ECHO' contained an "
                            "unsupported Element '%s'.", elem.keyword)
            elif isinstance(status, int):
                rsp.Status = status
            else:
                raise TypeError(
                    "Invalid 'status' returned by the handler bound to "
                    "'evt.EVT_C_ECHO'"
                )

        except Exception as ex:
            LOGGER.error(
                "Exception in the handler bound to 'evt.EVT_C_ECHO', "
                "responding with a default 'Status' value of 0x0000 "
                "(Success)"
            )
            LOGGER.exception(ex)
            rsp.Status = 0x0000

        # Check Status validity
        if not self.is_valid_status(rsp.Status):
            LOGGER.warning(
                "Unknown 'status' value returned by the handler bound to "
                "'evt.EVT_C_ECHO' - 0x{0:04x}".format(rsp.Status)
            )

        # Send primitive
        self.dimse.send_msg(rsp, context.context_id)


class StorageServiceClass(ServiceClass):
    """Implementation of the Storage Service Class."""
    uid = '1.2.840.10008.4.2'
    statuses = STORAGE_SERVICE_CLASS_STATUS

    def SCP(self, req, context):
        """The SCP implementation for the Storage Service Class.

        Parameters
        ----------
        req : dimse_primitives.C_STORE
            The C-STORE request primitive sent by the peer.
        context : presentation.PresentationContext
            The presentation context that the SCP is operating under.

        See Also
        --------
        association.Association.send_c_store

        Notes
        -----

        **C-STORE Request**

        *Parameters*

        | (M) Message ID
        | (M) Affected SOP Class UID
        | (M) Affected SOP Instance UID
        | (M) Priority
        | (U) Move Originator Application Entity Title
        | (U) Move Originator Message ID
        | (M) Data Set

        **C-STORE Response**

        *Parameters*

        | (U) Message ID
        | (M) Message ID Being Responded To
        | (U) Affected SOP Class UID
        | (U) Affected SOP Instance UID
        | (M) Status

        *Status*

        Success
          | ``0x0000`` Success

        Warning
          | ``0xB000`` Warning: Coercion of Data Elements
          | ``0xB006`` Warning: Elements Discarded
          | ``0xB007`` Warning: Data Set Does Not Match SOP Class

        Failure
          | ``0x0117`` Refused: Invalid SOP Instance
          | ``0x0122`` Refused: SOP Class Not Supported
          | ``0x0124`` Refused: Not Authorised
          | ``0x0210`` Refused: Duplicate Invocation
          | ``0x0211`` Refused: Unrecognised Operation
          | ``0x0212`` Refused: Mistyped Argument
          | ``0xA700`` to ``0xA7FF`` Refused: Out of Resources
          | ``0xA900`` to ``0xA9FF`` Error: Data Set Does Not Match SOP Class
          | ``0xC000`` to ``0xCFFF`` Error: Cannot Understand

        References
        ----------

        * DICOM Standard, Part 4, `Annex B <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_B>`_.
        * DICOM Standard, Part 4, `Annex GG <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_GG>`_.
        * DICOM Standard, Part 7, Sections
          `9.1.1 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.1.1>`_,
          `9.3.1 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.1>`_
          and `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_.
        """
        # Build C-STORE response primitive
        rsp = C_STORE()
        rsp.MessageID = req.MessageID
        rsp.MessageIDBeingRespondedTo = req.MessageID
        rsp.AffectedSOPInstanceUID = req.AffectedSOPInstanceUID
        rsp.AffectedSOPClassUID = req.AffectedSOPClassUID

        try:
            rsp_status = evt.trigger(
                self.assoc,
                evt.EVT_C_STORE,
                {'request' : req, 'context' : context.as_tuple}
            )
        except Exception as exc:
            LOGGER.error(
                "Exception in the handler bound to 'evt.EVT_C_STORE'"
            )
            LOGGER.exception(exc)
            rsp.Status = 0xC211
            self.dimse.send_msg(rsp, context.context_id)
            return

        # Validate rsp_status and set rsp.Status accordingly
        rsp = self.validate_status(rsp_status, rsp)
        self.dimse.send_msg(rsp, context.context_id)


class QueryRetrieveServiceClass(ServiceClass):
    """Implementation of the Query/Retrieve Service Class."""
    statuses = None
    # Used with Composite Instance Retrieve Without Bulk Data
    BULK_DATA_KEYWORDS = [
        'PixelData', 'FloatPixelData', 'DoubleFloatPixelData',
        'PixelDataProviderURL', 'SpectroscopyData', 'OverlayData',
        'CurveData', 'AudioSampleData', 'EncapsulatedDocument'
    ]

    def SCP(self, req, context):
        """The SCP implementation for the Query/Retrieve Service Class.

        Parameters
        ----------
        req : dimse_primitives.C_FIND or C_GET or C_MOVE
            The request primitive received from the peer.
        context : presentation.PresentationContext
            The presentation context that the SCP is operating under.
        """
        if context.abstract_syntax in ['1.2.840.10008.5.1.4.1.2.1.1',
                                       '1.2.840.10008.5.1.4.1.2.2.1',
                                       '1.2.840.10008.5.1.4.1.2.3.1',
                                       '1.2.840.10008.5.1.4.20.1',
                                       '1.2.840.10008.5.1.4.38.2',
                                       '1.2.840.10008.5.1.4.39.2',
                                       '1.2.840.10008.5.1.4.43.2',
                                       '1.2.840.10008.5.1.4.44.2',
                                       '1.2.840.10008.5.1.4.45.2',
                                       '1.2.840.10008.5.1.4.1.1.200.4']:
            self.statuses = QR_FIND_SERVICE_CLASS_STATUS
            self._find_scp(req, context)
        elif context.abstract_syntax in ['1.2.840.10008.5.1.4.1.2.1.3',
                                         '1.2.840.10008.5.1.4.1.2.2.3',
                                         '1.2.840.10008.5.1.4.1.2.3.3',
                                         '1.2.840.10008.5.1.4.1.2.4.3',
                                         '1.2.840.10008.5.1.4.1.2.5.3',
                                         '1.2.840.10008.5.1.4.20.3',
                                         '1.2.840.10008.5.1.4.38.4',
                                         '1.2.840.10008.5.1.4.39.4',
                                         '1.2.840.10008.5.1.4.43.4',
                                         '1.2.840.10008.5.1.4.44.4',
                                         '1.2.840.10008.5.1.4.45.4',
                                         '1.2.840.10008.5.1.4.1.1.200.6']:
            self.statuses = QR_GET_SERVICE_CLASS_STATUS
            self._get_scp(req, context)
        elif context.abstract_syntax in ['1.2.840.10008.5.1.4.1.2.1.2',
                                         '1.2.840.10008.5.1.4.1.2.2.2',
                                         '1.2.840.10008.5.1.4.1.2.3.2',
                                         '1.2.840.10008.5.1.4.1.2.4.2',
                                         '1.2.840.10008.5.1.4.20.2',
                                         '1.2.840.10008.5.1.4.38.3',
                                         '1.2.840.10008.5.1.4.39.3',
                                         '1.2.840.10008.5.1.4.43.3',
                                         '1.2.840.10008.5.1.4.44.3',
                                         '1.2.840.10008.5.1.4.45.3',
                                         '1.2.840.10008.5.1.4.1.1.200.5']:
            self.statuses = QR_MOVE_SERVICE_CLASS_STATUS
            self._move_scp(req, context)
        else:
            raise ValueError(
                'The supplied abstract syntax is not valid for use with the '
                'Query/Retrieve Service Class'
            )

    def _find_scp(self, req, context):
        """The SCP implementation for Query/Retrieve - Find.

        Parameters
        ----------
        req : dimse_primitives.C_FIND
            The C-FIND request primitive received from the peer.
        context : presentation.PresentationContext
            The presentation context that the SCP is operating under.

        See Also
        --------
        association.Association.send_c_find

        Notes
        -----
        **C-FIND Request**

        *Parameters*

        | (M) Message ID
        | (M) Affected SOP Class UID
        | (M) Priority
        | (M) Identifier

        *Identifier*

        The C-FIND request Identifier shall contain:

        * Key Attributes values to be matched against the values of storage
          SOP Instances managed by the SCP.
        * (0008,0052) Query/Retrieve Level.
        * (0008,0053) Query/Retrieve View, if Enhanced Multi-Frame Image
          Conversion has been accepted during Extended Negotiation. It shall
          not be present otherwise.
        * (0008,0005) Specific Character Set, if expanded or replacement
          character sets may be used in any of the Attributes in the request
          Identifier. It shall not be present otherwise.
        * (0008,0201) Timezone Offset From UTC, if any Attributes of time in
          the request Identifier are to be interpreted explicitly in the
          designated local time zone. It shall not be present otherwise.

        **C-FIND Response**

        *Parameters*

        | (U) Message ID
        | (M) Message ID Being Responded To
        | (U) Affected SOP Class UID
        | (C) Identifier
        | (M) Status

        *Identifier*

        The C-FIND response shall only include an Identifier when the Status is
        'Pending'. When sent, the Identifier shall contain:

        * Key Attributes with values corresponding to Key Attributes contained
          in the Identifier of the req.
        * (0008,0052) Query/Retrieve Level.
        * (0008,0005) Specific Character Set, if expanded or replacement
          character sets may be used in any of the Attributes in the response
          Identifier. It shall not be present otherwise.
        * (0008,0201) Timezone Offset From UTC, if any Attributes of time in
          the response Identifier are to be interpreted explicitly in the
          designated local time zone. It shall not be present otherwise.

        The C-FIND response Identifier shall also contain either or both of:

        * (0008,0130) Storage Media File-Set ID and (0088,0140) Storage Media
          File-Set UID.
        * (0008,0054) Retrieve AE Title.

        The C-FIND response Identifier may also (but is not required to)
        include the (0008,0056) Instance Availability element.

        *Status*

        Success
          | ``0x0000`` Success

        Pending
          | ``0xFF00`` Matches are continuing, current match supplied
          | ``0xFF01`` Matches are continuing, warning

        Cancel
          | ``0xFE00`` Cancel

        Failure
          | ``0x0122`` SOP class not supported
          | ``0xA700`` Out of resources
          | ``0xA900`` Identifier does not match SOP class
          | ``0xC000`` to ``0xCFFF`` Unable to process

        References
        ----------
        .. [1] DICOM Standard, Part 4, `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_C>`_.
        .. [2] DICOM Standard, Part 7, Sections
           `9.1.2 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.1.2>`_,
           `9.3.2 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.2>`_
           and `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_.
        """
        # Build C-FIND response primitive
        rsp = C_FIND()
        rsp.MessageID = req.MessageID
        rsp.MessageIDBeingRespondedTo = req.MessageID
        rsp.AffectedSOPClassUID = req.AffectedSOPClassUID

        # Decode and log Identifier
        transfer_syntax = context.transfer_syntax[0]
        try:
            identifier = decode(req.Identifier,
                                transfer_syntax.is_implicit_VR,
                                transfer_syntax.is_little_endian)
            LOGGER.info('Find SCP Request Identifiers:')
            LOGGER.info('')
            LOGGER.debug('# DICOM Dataset')
            for elem in identifier.iterall():
                LOGGER.info(elem)
            LOGGER.info('')
        except Exception as ex:
            LOGGER.error("Failed to decode the request's Identifier dataset.")
            LOGGER.exception(ex)
            # Failure - Unable to Process - Failed to decode Identifier
            rsp.Status = 0xC310
            rsp.ErrorComment = 'Unable to decode the dataset'
            self.dimse.send_msg(rsp, context.context_id)
            return

        # Pass the C-FIND request to the user to handle
        try:
            handler = evt.trigger(
                self.assoc,
                evt.EVT_C_FIND,
                {
                    'request' : req,
                    'context' : context.as_tuple,
                    '_is_cancelled' : self.is_cancelled
                }
            )
        except Exception as exc:
            LOGGER.error("Exception in handler bound to 'evt.EVT_C_FIND'")
            LOGGER.exception(exc)
            rsp.Status = 0xC311
            self.dimse.send_msg(rsp, context.context_id)
            return

        # No matches and no yields
        if handler is None:
            handler = iter([(0x0000, None)])

        ii = -1  # So if there are no results, log below doesn't break
        # Iterate through the results
        for ii, (rsp_status, rsp_identifier) in enumerate(self._wrap_handler(handler)):
            # Exception raised by user's generator
            if isinstance(rsp_status, Exception):
                LOGGER.error(
                    "Exception raised by user's C-FIND request handler",
                    exc_info=rsp_identifier)
                rsp_status = 0xC311

            # Validate rsp_status and set rsp.Status accordingly
            rsp = self.validate_status(rsp_status, rsp)

            if rsp.Status in self.statuses:
                status = self.statuses[rsp.Status]
            else:
                # Unknown status
                self.dimse.send_msg(rsp, context.context_id)
                return

            if status[0] == STATUS_CANCEL:
                # If cancel, then rsp_identifier is None
                LOGGER.info('Received C-CANCEL-FIND RQ from peer')
                LOGGER.info('Find SCP Response: (Cancel)')
                self.dimse.send_msg(rsp, context.context_id)
                return
            elif status[0] == STATUS_FAILURE:
                # If failed, then rsp_identifier is None
                LOGGER.info('Find SCP Response: (Failure - %s)', status[1])
                self.dimse.send_msg(rsp, context.context_id)
                return
            elif status[0] == STATUS_SUCCESS:
                # User isn't supposed to send these, but handle anyway
                # If success, then rsp_identifier is None
                LOGGER.info('Find SCP Response: %s (Success)', ii + 1)
                self.dimse.send_msg(rsp, context.context_id)
                return
            elif status[0] == STATUS_PENDING:
                # If pending, the rsp_identifier is the Identifier dataset
                bytestream = encode(rsp_identifier,
                                    transfer_syntax.is_implicit_VR,
                                    transfer_syntax.is_little_endian)
                bytestream = BytesIO(bytestream)

                if bytestream.getvalue() == b'':
                    LOGGER.error("Failed to encode the received Identifier "
                                 "dataset")
                    # Failure: Unable to Process - Can't decode dataset
                    #   returned by handler
                    rsp.Status = 0xC312
                    self.dimse.send_msg(rsp, context.context_id)
                    return

                rsp.Identifier = bytestream

                LOGGER.info('Find SCP Response: %s (Pending)', ii + 1)
                LOGGER.debug('Find SCP Response Identifier:')
                LOGGER.debug('')
                LOGGER.debug('# DICOM Dataset')
                for elem in rsp_identifier.iterall():
                    LOGGER.debug(elem)
                LOGGER.debug('')

                self.dimse.send_msg(rsp, context.context_id)

            # Reset the response Identifier
            rsp.Identifier = None

        # Send final success response
        rsp.Status = 0x0000
        LOGGER.info('Find SCP Response: %s (Success)', ii + 2)
        self.dimse.send_msg(rsp, context.context_id)

    def _get_scp(self, req, context):
        """The SCP implementation for Query/Retrieve - Get.

        Parameters
        ----------
        req : dimse_primitives.C_GET
            The C-GET request primitive sent by the peer.
        context : presentation.PresentationContext
            The presentation context that the SCP is operating under.

        See Also
        --------
        association.Association.send_c_get

        Notes
        -----
        **C-GET Request**

        *Parameters*

        | (M) Message ID
        | (M) Affected SOP Class UID
        | (M) Priority
        | (M) Identifier

        *Identifier*

        The C-GET request Identifier shall contain:

        * (0008,0052) Query/Retrieve Level.
        * Unique Key Attributes, which may include:

          - (0010,0020) Patient ID
          - (0020,000D) Study Instance UIDs
          - (0020,000E) Series Instance UIDs
          - (0008,0018) SOP Instance UIDs

        * (0008,0053) Query/Retrieve View, if Enhanced Multi-Frame Image
          Conversion has been accepted during Extended Negotiation. It shall
          not be present otherwise.
        * (0008,0005) Specific Character Set, if (0010,0020) Patient ID is
          using a character set other than the default character repertoire.

        **C-GET Response**

        *Parameters*

        | (U) Message ID
        | (M) Message ID Being Responded To
        | (U) Affected SOP Class UID
        | (U) Identifier
        | (M) Status
        | (C) Number of Remaining Sub-operations
        | (C) Number of Completed Sub-operations
        | (C) Number of Failed Sub-operations
        | (C) Number of Warning Sub-operations

        *Identifier*

        If the C-GET response Status is 'Cancelled', 'Failure', 'Refused' or
        'Warning' then the Identifier shall contain:

        * (0008,0058) Failed SOP Instance UID List

        If the C-GET response Status is 'Pending' then there is no Identifier.

        *Status*

        Success
          | ``0x0000`` Sub-operations complete: no failures or warnings

        Pending
          | ``0xFF00`` Sub-operations are continuing

        Cancel
          | ``0xFE00`` Sub-operations terminated due to Cancel indication

        Failure
          | ``0x0122`` SOP class not supported
          | ``0x0124`` Not authorised
          | ``0x0210`` Duplicate invocation
          | ``0x0211`` Unrecognised operation
          | ``0x0212`` Mistyped argument
          | ``0xA701`` Out of resources: unable to calculate number of matches
          | ``0xA702`` Out of resources: unable to perform sub-operations
          | ``0xA900`` Identifier does not match SOP class
          | ``0xC000`` to ``0xCFFF`` Unable to process

        Warning
          | ``0xB000`` Sub-operations complete: one or more failures or
            warnings

        *Number of X Sub-operations*

        Inclusion of the 'Number of X Sub-operations' parameters is conditional
        on the value of the response Status. For a given Status category, the
        table below states whether or not the response shall contain, shall not
        contain or may contain the 'Number of X Sub-operations' parameter.

        +-----------+------------------------------------------+
        |           | Number of "X" Sub-operations             |
        +-----------+-----------+-----------+--------+---------+
        | Status    | Remaining | Completed | Failed | Warning |
        +===========+===========+===========+========+=========+
        | Pending   | shall     | shall     | shall  | shall   |
        +-----------+-----------+-----------+--------+---------+
        | Cancelled | may       | may       | may    | may     |
        +-----------+-----------+-----------+--------+---------+
        | Warning   | shall not | may       | may    | may     |
        +-----------+-----------+-----------+--------+---------+
        | Failure   | shall not | may       | may    | may     |
        +-----------+-----------+-----------+--------+---------+
        | Success   | shall not | may       | may    | may     |
        +-----------+-----------+-----------+--------+---------+

        References
        ----------
        .. [1] DICOM Standard, Part 4, `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_C>`_.
        .. [2] DICOM Standard, Part 7, Sections
           `9.1.3 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.1.3>`_,
           `9.3.3 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.3>`_
           and `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_.
        """
        # Build C-GET response primitive
        rsp = C_GET()
        rsp.MessageID = req.MessageID
        rsp.MessageIDBeingRespondedTo = req.MessageID
        rsp.AffectedSOPClassUID = req.AffectedSOPClassUID

        # Attempt to decode the request's Identifier dataset
        transfer_syntax = context.transfer_syntax[0]

        try:
            result = evt.trigger(
                self.assoc,
                evt.EVT_C_GET,
                {
                    'request' : req,
                    'context' : context.as_tuple,
                    '_is_cancelled' : self.is_cancelled
                }
            )
        except Exception as exc:
            LOGGER.error("Exception in handler bound to 'evt.EVT_C_GET'")
            LOGGER.exception(exc)
            rsp.Status = 0xC411
            self.dimse.send_msg(rsp, context.context_id)
            return

        # Number of C-STORE sub-operations
        try:
            no_suboperations = int(next(result))
        except Exception as exc:
            LOGGER.error("User's C-GET' generator yielded an invalid number "
                         "of sub-operations value")
            LOGGER.exception(exc)
            rsp.Status = 0xC413
            self.dimse.send_msg(rsp, context.context_id)
            return

        # Track the sub operation results
        #   [remaining, failed, warning, complete]
        store_results = [no_suboperations, 0, 0, 0]

        # Store the SOP Instance UIDs from any failed C-STORE sub-operations
        failed_instances = []
        def _add_failed_instance(ds):
            if hasattr(ds, 'SOPInstanceUID'):
                failed_instances.append(ds.SOPInstanceUID)

        # Iterate through the results
        # C-GET Pending responses are optional!
        for ii, (rsp_status, dataset) in enumerate(self._wrap_handler(result)):
            # Exception raised by user's generator
            if isinstance(rsp_status, Exception):
                LOGGER.error(
                    "Exception raised by user's C-GET request handler",
                    exc_info=dataset)
                rsp_status = 0xC411

            # All sub-operations are complete
            if store_results[0] <= 0:
                LOGGER.warning(
                    "User's C-GET generator yielded further (status, dataset) "
                    "results but these will be ignored as the sub-operations "
                    "are complete"
                )
                break

            # Validate rsp_status and set rsp.Status accordingly
            rsp = self.validate_status(rsp_status, rsp)
            if rsp.Status in self.statuses:
                status = self.statuses[rsp.Status]
            else:
                # Unknown status
                self.dimse.send_msg(rsp, context.context_id)
                return

            if status[0] == STATUS_CANCEL:
                # If cancel, dataset is a Dataset with a
                # 'FailedSOPInstanceUIDList' element
                LOGGER.info('Get SCP Received C-CANCEL-GET RQ from peer')
                rsp.NumberOfRemainingSuboperations = store_results[0]
                rsp.NumberOfFailedSuboperations = store_results[1]
                rsp.NumberOfWarningSuboperations = store_results[2]
                rsp.NumberOfCompletedSuboperations = store_results[3]

                # In case user didn't include it
                if (not isinstance(dataset, Dataset) or
                        'FailedSOPInstanceUIDList' not in dataset):
                    dataset = Dataset()
                    dataset.FailedSOPInstanceUIDList = failed_instances

                bytestream = encode(dataset,
                                    transfer_syntax.is_implicit_VR,
                                    transfer_syntax.is_little_endian)
                rsp.Identifier = BytesIO(bytestream)
                self.dimse.send_msg(rsp, context.context_id)
                return
            elif status[0] in [STATUS_FAILURE, STATUS_WARNING]:
                # If failure or warning, dataset is a Dataset with a
                # 'FailedSOPInstanceUIDList' element
                LOGGER.info('Get SCP Result (%s - %s)', status[0], status[1])
                rsp.NumberOfRemainingSuboperations = None
                rsp.NumberOfFailedSuboperations = (
                    store_results[1] + store_results[0]
                )
                rsp.NumberOfWarningSuboperations = store_results[2]
                rsp.NumberOfCompletedSuboperations = store_results[3]

                # In case user didn't include it
                if (not isinstance(dataset, Dataset) or
                        'FailedSOPInstanceUIDList' not in dataset):
                    dataset = Dataset()
                    dataset.FailedSOPInstanceUIDList = failed_instances

                bytestream = encode(dataset,
                                    transfer_syntax.is_implicit_VR,
                                    transfer_syntax.is_little_endian)
                rsp.Identifier = BytesIO(bytestream)
                self.dimse.send_msg(rsp, context.context_id)
                return
            elif status[0] == STATUS_SUCCESS:
                # If user yields Success, check it
                # dataset is None
                if store_results[1] or store_results[2]:
                    LOGGER.info('Get SCP Response: (Warning)')
                    rsp.Status = 0xB000
                    ds = Dataset()
                    ds.FailedSOPInstanceUIDList = failed_instances
                    bytestream = encode(ds,
                                        transfer_syntax.is_implicit_VR,
                                        transfer_syntax.is_little_endian)
                    rsp.Identifier = BytesIO(bytestream)
                else:
                    LOGGER.info('Get SCP Response: (Success)')
                    rsp.Identifier = None

                rsp.NumberOfRemainingSuboperations = None
                rsp.NumberOfFailedSuboperations = store_results[1]
                rsp.NumberOfWarningSuboperations = store_results[2]
                rsp.NumberOfCompletedSuboperations = store_results[3]

                self.dimse.send_msg(rsp, context.context_id)
                return
            elif status[0] == STATUS_PENDING and dataset:
                # If pending, dataset is the Dataset to send
                if not isinstance(dataset, Dataset):
                    LOGGER.error('Received invalid dataset from callback')
                    # Count as a sub-operation failure
                    store_results[1] += 1
                    failed_instances.append('')
                    rsp.Identifier = None
                    rsp.NumberOfRemainingSuboperations = store_results[0]
                    rsp.NumberOfFailedSuboperations = store_results[1]
                    rsp.NumberOfWarningSuboperations = store_results[2]
                    rsp.NumberOfCompletedSuboperations = store_results[3]
                    self.dimse.send_msg(rsp, context.context_id)
                    continue

                LOGGER.info('Get SCP Response: %s (Pending)', ii + 1)

                # If the Composite Instance Retrieve Without Bulk Data Service
                #   is being used then we must remove the bulk data elements
                #   (if present)
                if context.abstract_syntax == '1.2.840.10008.5.1.4.1.2.5.3':
                    # Doesn't include WaveformData
                    _bulk_data = [
                        kw for kw in self.BULK_DATA_KEYWORDS if kw in dataset
                    ]
                    for keyword in _bulk_data:
                        delattr(dataset, keyword)

                    # Needs to be handled separately
                    if 'WaveformSequence' in dataset:
                        for item in dataset.WaveformSequence:
                            if 'WaveformData' in item:
                                del item.WaveformData
                                if 'WaveformData' not in _bulk_data:
                                    _bulk_data.append('WaveformData')

                    if _bulk_data:
                        LOGGER.warning(
                            "The Query/Retrieve - Composite Instance Retrieve "
                            "Without Bulk Data service is requested but a "
                            "yielded dataset contains the following (to be "
                            "removed) bulk data elements: {}"
                            .format(','.join(_bulk_data))
                        )

                # Send `dataset` via C-STORE sub-operations over the existing
                #   association and check that the response's Status exists and
                #   is a known value
                try:
                    # Message ID is VR 'US' and has range 0 <= n < 2**16
                    msg_id = req.MessageID + ii + 1
                    if msg_id > 65535:
                        msg_id -= 65535

                    store_status = self.assoc.send_c_store(
                        dataset, msg_id=msg_id
                    )
                    store_status = (
                        STORAGE_SERVICE_CLASS_STATUS[store_status.Status]
                    )
                except Exception as ex:
                    # An exception implies a C-STORE failure
                    LOGGER.warning("C-STORE sub-operation failed.")
                    LOGGER.exception(ex)
                    store_status = [STATUS_FAILURE, 'Unknown']

                LOGGER.info('Get SCP: Received Store SCU response (%s)',
                            store_status[0])

                # Update the C-STORE sub-operation result tracker
                if store_status[0] == STATUS_FAILURE:
                    store_results[1] += 1
                    _add_failed_instance(dataset)
                elif store_status[0] == STATUS_WARNING:
                    store_results[2] += 1
                    _add_failed_instance(dataset)
                elif store_status[0] == STATUS_SUCCESS:
                    store_results[3] += 1

                store_results[0] -= 1

                rsp.Identifier = None
                rsp.NumberOfRemainingSuboperations = store_results[0]
                rsp.NumberOfFailedSuboperations = store_results[1]
                rsp.NumberOfWarningSuboperations = store_results[2]
                rsp.NumberOfCompletedSuboperations = store_results[3]
                self.dimse.send_msg(rsp, context.context_id)

        # If not already done, send the final 'Success' or 'Warning' response
        if not store_results[1] and not store_results[2]:
            # Success response - no failures or warnings
            LOGGER.info('Get SCP Result: (Success)')
            rsp.Status = 0x0000
        else:
            # Warning response - one or more failures or warnings
            LOGGER.info('Get SCP Result: (Warning)')
            rsp.Status = 0xB000
            # If Warning response, need to return an Identifier with
            #   (0008,0058) Failed SOP Instance UID List element
            ds = Dataset()
            ds.FailedSOPInstanceUIDList = failed_instances
            bytestream = encode(ds,
                                transfer_syntax.is_implicit_VR,
                                transfer_syntax.is_little_endian)
            rsp.Identifier = BytesIO(bytestream)

        rsp.NumberOfRemainingSuboperations = None
        rsp.NumberOfFailedSuboperations = store_results[1]
        rsp.NumberOfWarningSuboperations = store_results[2]
        rsp.NumberOfCompletedSuboperations = store_results[3]

        self.dimse.send_msg(rsp, context.context_id)

    def _move_scp(self, req, context):
        """The SCP implementation for Query/Retrieve - Move.

        Parameters
        ----------
        req : dimse_primitives.C_MOVE
            The C-MOVE request primitive sent by the peer.
        context : presentation.PresentationContext
            The presentation context that the SCP is operating under.

        See Also
        --------
        association.Association.send_c_move

        Notes
        -----
        **C-MOVE Request**

        *Parameters*

        | (M) Message ID
        | (M) Affected SOP Class UID
        | (M) Priority
        | (M) Move Destination
        | (M) Identifier

        *Identifier*

        The C-MOVE request Identifier shall contain:

        * (0008,0052) Query/Retrieve Level.
        * Unique Key Attributes, which may include:

          - (0010,0020) Patient ID
          - (0020,000D) Study Instance UIDs
          - (0020,000E) Series Instance UIDs
          - (0008,0018) SOP Instance UIDs

        * (0008,0053) Query/Retrieve View, if Enhanced Multi-Frame Image
          Conversion has been accepted during Extended Negotiation. It shall
          not be present otherwise.
        * (0008,0005) Specific Character Set, if (0010,0020) Patient ID is
          using a character set other than the default character repertoire.

        **C-MOVE Response**

        *Parameters*

        | (U) Message ID
        | (M) Message ID Being Responded To
        | (U) Affected SOP Class UID
        | (U) Identifier
        | (M) Status
        | (C) Number of Remaining Sub-operations
        | (C) Number of Completed Sub-operations
        | (C) Number of Failed Sub-operations
        | (C) Number of Warning Sub-operations

        *Identifier*

        If the C-MOVE response Status is 'Cancelled', 'Failure', 'Refused' or
        'Warning' then the Identifier shall contain:

        * (0008,0058) Failed SOP Instance UID List

        If the C-MOVE response Status is 'Pending' then there is no Identifier.

        *Status*

        Success
          | ``0x0000`` Sub-operations complete: no failures

        Pending
          | ``0xFF00`` Sub-operations are continuing

        Cancel
          | ``0xFE00`` Sub-operations terminated due to Cancel indication

        Failure
          | ``0x0122`` SOP class not supported
          | ``0x0124`` Not authorised
          | ``0x0210`` Duplicate invocation
          | ``0x0211`` Unrecognised operation
          | ``0x0212`` Mistyped argument
          | ``0xA701`` Out of resources: unable to calculate number of matches
          | ``0xA702`` Out of resources, unable to perform sub-operations
          | ``0xA801`` Move destination unknown
          | ``0xA900`` Identifier does not match SOP class
          | ``0xC000`` to ``0xCFFF`` Unable to process

        Warning
          | ``0xB000`` Sub-operations complete: one or more failures

        *Number of X Sub-operations*

        Inclusion of the 'Number of X Sub-operations' parameters is conditional
        on the value of the response Status. For a given Status category, the
        table below states whether or not the response shall contain, shall not
        contain or may contain the 'Number of X Sub-operations' parameter.

        +-----------+------------------------------------------+
        |           | Number of "X" Sub-operations             |
        +-----------+-----------+-----------+--------+---------+
        | Status    | Remaining | Completed | Failed | Warning |
        +===========+===========+===========+========+=========+
        | Pending   | shall     | shall     | shall  | shall   |
        +-----------+-----------+-----------+--------+---------+
        | Cancelled | may       | may       | may    | may     |
        +-----------+-----------+-----------+--------+---------+
        | Warning   | shall not | may       | may    | may     |
        +-----------+-----------+-----------+--------+---------+
        | Failure   | shall not | may       | may    | may     |
        +-----------+-----------+-----------+--------+---------+
        | Success   | shall not | may       | may    | may     |
        +-----------+-----------+-----------+--------+---------+

        References
        ----------
        .. [1] DICOM Standard, Part 4, `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_C>`_.
        .. [2] DICOM Standard, Part 7, Sections
           `9.1.4 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.1.4>`_,
           `9.3.4 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.4>`_
           and `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_.
        """
        # Build C-MOVE response primitive
        rsp = C_MOVE()
        rsp.MessageID = req.MessageID
        rsp.MessageIDBeingRespondedTo = req.MessageID
        rsp.AffectedSOPClassUID = req.AffectedSOPClassUID

        # Attempt to decode the request's Identifier dataset
        transfer_syntax = context.transfer_syntax[0]
        try:
            identifier = decode(req.Identifier,
                                transfer_syntax.is_implicit_VR,
                                transfer_syntax.is_little_endian)
            LOGGER.info('Move SCP Request Identifier:')
            LOGGER.info('')
            LOGGER.debug('# DICOM Data Set')
            for elem in identifier.iterall():
                LOGGER.info(elem)
            LOGGER.info('')
        except Exception as exc:
            LOGGER.error("Failed to decode the request's Identifier dataset")
            LOGGER.exception(exc)
            # Failure: Cannot Understand - Dataset decoding error
            rsp.Status = 0xC510
            rsp.ErrorComment = 'Unable to decode the dataset'
            self.dimse.send_msg(rsp, context.context_id)
            return

        try:
            result = evt.trigger(
                self.assoc,
                evt.EVT_C_MOVE,
                {
                    'request' : req,
                    'context' : context.as_tuple,
                    '_is_cancelled' : self.is_cancelled
                }
            )
        except Exception as exc:
            LOGGER.error("Exception in handler bound to 'evt.EVT_C_MOVE'")
            LOGGER.exception(exc)
            # Failure - Unable to process - Error in handler
            rsp.Status = 0xC511
            self.dimse.send_msg(rsp, context.context_id)
            return

        try:
            destination = next(result)
            no_suboperations = next(result)
        except Exception as exc:
            LOGGER.exception(
                "The C-MOVE request handler must yield the (address, port) "
                "of the destination AE, then yield the number of "
                "sub-operations, then yield (status dataset) pairs."
            )
            # Failure - Unable to process - Error in handler
            rsp.Status = 0xC514
            self.dimse.send_msg(rsp, context.context_id)
            return

        # Check number of C-STORE sub-operations
        try:
            no_suboperations = int(no_suboperations)
        except Exception as ex:
            LOGGER.error(
                "The C-MOVE request handler yielded an invalid number of "
                "sub-operations value"
            )
            LOGGER.exception(ex)
            rsp.Status = 0xC513
            self.dimse.send_msg(rsp, context.context_id)
            return

        # Request new association with Move Destination
        try:
            # Unknown Move Destination
            if None in destination:
                LOGGER.error('Unknown Move Destination: %s',
                             req.MoveDestination.decode('ascii'))
                # Failure - Move destination unknown
                rsp.Status = 0xA801
                self.dimse.send_msg(rsp, context.context_id)
                return

            store_assoc = self.ae.associate(destination[0],
                                            destination[1],
                                            ae_title=req.MoveDestination)
        except Exception as ex:
            LOGGER.error(
                "The handler bound to 'evt.EVT_C_MOVE' yielded an invalid "
                "destination AE (addr, port) value"
            )
            LOGGER.exception(ex)
            # Failure - Unable to process - Bad handler AE destination
            rsp.Status = 0xC515
            self.dimse.send_msg(rsp, context.context_id)
            return

        # Track the sub operation results
        #   [remaining, failed, warning, complete]
        store_results = [no_suboperations, 0, 0, 0]

        # Store the SOP Instance UIDs from any failed C-STORE sub-operations
        failed_instances = []
        def _add_failed_instance(ds):
            if hasattr(ds, 'SOPInstanceUID'):
                failed_instances.append(ds.SOPInstanceUID)

        if store_assoc.is_established:
            # Iterate through the remaining callback (status, dataset) yields
            for ii, (rsp_status, dataset) in enumerate(self._wrap_handler(result)):
                # Exception raised by handler
                if isinstance(rsp_status, Exception):
                    LOGGER.error(
                        "Exception raised by handler bound to 'evt.EVT_C_MOVE'",
                        exc_info=dataset
                    )
                    rsp_status = 0xC511

                # All sub-operations are complete
                if store_results[0] <= 0:
                    LOGGER.warning(
                        "Handler bound to 'evt.EVT_C_MOVE' yielded further "
                        "(status, dataset) results but these will be "
                        "ignored as the sub-operations are complete"
                    )
                    break

                # Validate rsp_status and set rsp.Status accordingly
                rsp = self.validate_status(rsp_status, rsp)
                if rsp.Status in self.statuses:
                    status = self.statuses[rsp.Status]
                else:
                    # Unknown status
                    store_assoc.release()
                    self.dimse.send_msg(rsp, context.context_id)
                    return

                # If usr_status is Cancel, Failure, Warning or Success then
                #   generate a final response, if Pending then do C-STORE
                #   sub-operation
                if status[0] == STATUS_CANCEL:
                    # If cancel, then dataset is a Dataset with a
                    #   'FailedSOPInstanceUIDList' element
                    LOGGER.info(
                        'Move SCP Received C-CANCEL-MOVE RQ from peer'
                    )
                    store_assoc.release()

                    # In case user didn't include it
                    if (not isinstance(dataset, Dataset) or
                            'FailedSOPInstanceUIDList' not in dataset):
                        dataset = Dataset()
                        dataset.FailedSOPInstanceUIDList = failed_instances

                    bytestream = encode(dataset,
                                        transfer_syntax.is_implicit_VR,
                                        transfer_syntax.is_little_endian)

                    rsp.Identifier = BytesIO(bytestream)
                    rsp.NumberOfRemainingSuboperations = store_results[0]
                    rsp.NumberOfFailedSuboperations = store_results[1]
                    rsp.NumberOfWarningSuboperations = store_results[2]
                    rsp.NumberOfCompletedSuboperations = store_results[3]

                    self.dimse.send_msg(rsp, context.context_id)
                    return
                elif status[0] in [STATUS_FAILURE, STATUS_WARNING]:
                    # If failed or warning, then dataset is a Dataset with a
                    #   'FailedSOPInstanceUIDList' element
                    LOGGER.info(
                        'Move SCP Result (%s - %s)', status[0], status[1]
                    )
                    store_assoc.release()

                    # In case user didn't include it
                    if (not isinstance(dataset, Dataset) or
                            'FailedSOPInstanceUIDList' not in dataset):
                        dataset = Dataset()
                        dataset.FailedSOPInstanceUIDList = failed_instances

                    bytestream = encode(dataset,
                                        transfer_syntax.is_implicit_VR,
                                        transfer_syntax.is_little_endian)

                    rsp.Identifier = BytesIO(bytestream)
                    rsp.NumberOfRemainingSuboperations = None
                    rsp.NumberOfFailedSuboperations = (
                        store_results[1] + store_results[0]
                    )
                    rsp.NumberOfWarningSuboperations = store_results[2]
                    rsp.NumberOfCompletedSuboperations = store_results[3]

                    self.dimse.send_msg(rsp, context.context_id)
                    return
                elif status[0] == STATUS_SUCCESS:
                    # If Success, then dataset is None
                    store_assoc.release()

                    # If the user yields Success, check it
                    if store_results[1] or store_results[2]:
                        # Sub-operations contained failures/warnings
                        LOGGER.info('Move SCP Response: (Warning)')

                        ds = Dataset()
                        ds.FailedSOPInstanceUIDList = failed_instances
                        bytestream = encode(ds,
                                            transfer_syntax.is_implicit_VR,
                                            transfer_syntax.is_little_endian)

                        rsp.Identifier = BytesIO(bytestream)
                        rsp.Status = 0xB000
                    else:
                        # No failures or warnings
                        LOGGER.info('Move SCP Response: (Success)')
                        rsp.Identifier = None

                    rsp.NumberOfRemainingSuboperations = None
                    rsp.NumberOfFailedSuboperations = store_results[1]
                    rsp.NumberOfWarningSuboperations = store_results[2]
                    rsp.NumberOfCompletedSuboperations = store_results[3]

                    self.dimse.send_msg(rsp, context.context_id)
                    return
                elif status[0] == STATUS_PENDING and dataset:
                    # If pending, then dataset is the Dataset to send
                    if not isinstance(dataset, Dataset):
                        LOGGER.error('Received invalid dataset from callback')
                        # Count as a sub-operation failure
                        store_results[1] += 1
                        failed_instances.append('')
                        rsp.Identifier = None
                        rsp.NumberOfRemainingSuboperations = store_results[0]
                        rsp.NumberOfFailedSuboperations = store_results[1]
                        rsp.NumberOfWarningSuboperations = store_results[2]
                        rsp.NumberOfCompletedSuboperations = store_results[3]
                        self.dimse.send_msg(rsp, context.context_id)
                        continue

                    LOGGER.info('Move SCP Response %s (Pending)', ii + 1)

                    # Send `dataset` via C-STORE sub-operations over the
                    #   association and check that the response's Status exists
                    #   and is a known value
                    try:
                        # Message ID is VR 'US' and has range 0 <= n < 2**16
                        msg_id = req.MessageID + ii + 1
                        if msg_id > 65535:
                            msg_id -= 65535

                        store_status = store_assoc.send_c_store(
                            dataset,
                            msg_id=msg_id,
                            originator_aet=self.ae.ae_title,
                            originator_id=1
                        )
                        # FIXME: Should probably split status check?
                        store_status = STORAGE_SERVICE_CLASS_STATUS[
                            store_status.Status
                        ]
                    except Exception as ex:
                        # An exception implies a C-STORE failure
                        LOGGER.warning("C-STORE sub-operation failed.")
                        store_status = [STATUS_FAILURE, 'Unknown']

                    LOGGER.info('Move SCP: Received Store SCU response (%s)',
                                store_status[0])

                    # Update the C-STORE sub-operation result tracker
                    if store_status[0] == STATUS_FAILURE:
                        store_results[1] += 1
                        _add_failed_instance(dataset)
                    elif store_status[0] == STATUS_WARNING:
                        store_results[2] += 1
                        _add_failed_instance(dataset)
                    elif store_status[0] == STATUS_SUCCESS:
                        store_results[3] += 1

                    store_results[0] -= 1

                    rsp.Identifier = None
                    rsp.NumberOfRemainingSuboperations = store_results[0]
                    rsp.NumberOfFailedSuboperations = store_results[1]
                    rsp.NumberOfWarningSuboperations = store_results[2]
                    rsp.NumberOfCompletedSuboperations = store_results[3]

                    self.dimse.send_msg(rsp, context.context_id)

            store_assoc.release()

        else:
            # Failed to associate with Move Destination AE
            LOGGER.error('Move SCP: Unable to associate with destination AE')
            rsp.Status = 0xA801
            self.dimse.send_msg(rsp, context.context_id)

            # FIXME - shouldn't have to manually close the socket like this
            store_assoc.dul.socket.close()
            return

        # If not already done, send the final 'Success' or 'Warning' response
        if not store_results[1] and not store_results[2]:
            # Success response - no failures or warnings
            LOGGER.info('Move SCP Result: (Success)')
            rsp.Status = 0x0000
        else:
            # Warning response - one or more failures or warnings
            LOGGER.info('Move SCP Result: (Warning)')
            rsp.Status = 0xB000
            # If Warning response, need to return an Identifier with
            #   (0008, 0058) Failed SOP Instance UID List element
            ds = Dataset()
            ds.FailedSOPInstanceUIDList = failed_instances
            bytestream = encode(ds,
                                transfer_syntax.is_implicit_VR,
                                transfer_syntax.is_little_endian)
            rsp.Identifier = BytesIO(bytestream)

        rsp.NumberOfRemainingSuboperations = None
        rsp.NumberOfFailedSuboperations = store_results[1]
        rsp.NumberOfWarningSuboperations = store_results[2]
        rsp.NumberOfCompletedSuboperations = store_results[3]

        self.dimse.send_msg(rsp, context.context_id)


class BasicWorklistManagementServiceClass(QueryRetrieveServiceClass):
    """Implementation of the Basic Worklist Management Service Class."""
    statuses = QR_FIND_SERVICE_CLASS_STATUS

    def __init__(self, assoc):
        super(BasicWorklistManagementServiceClass, self).__init__(assoc)

    def SCP(self, req, context):
        """The SCP implementation for Basic Worklist Management.

        Parameters
        ----------
        req : dimse_primitives.C_FIND
            The C-FIND request primitive received from the peer.
        context : presentation.PresentationContext
            The presentation context that the SCP is operating under.

        See Also
        --------
        association.Association.send_c_find

        Notes
        -----
        **C-FIND Request**

        *Parameters*

        | (M) Message ID
        | (M) Affected SOP Class UID
        | (M) Priority
        | (M) Identifier

        *Identifier*

        The C-FIND request Identifier shall contain:

        * Key Attributes values to be matched against the values of attributes
          specified in that SOP Class.
        * (0008,0005) Specific Character Set, if expanded or replacement
          character sets may be used in any of the Attributes in the request
          Identifier. It shall not be present otherwise.
        * (0008,0201) Timezone Offset From UTC, if any Attributes of time in
          the request Identifier are to be interpreted explicitly in the
          designated local time zone. It shall not be present otherwise.

        **C-FIND Response**

        *Parameters*

        | (U) Message ID
        | (M) Message ID Being Responded To
        | (U) Affected SOP Class UID
        | (C) Identifier
        | (M) Status

        *Identifier*

        The C-FIND response shall only include an Identifier when the Status is
        'Pending'. When sent, the Identifier shall contain:

        * Key Attributes with values corresponding to Key Attributes contained
          in the Identifier of the requeset.
        * (0008,0005) Specific Character Set, if expanded or replacement
          character sets may be used in any of the Attributes in the response
          Identifier. It shall not be present otherwise.
        * (0008,0201) Timezone Offset From UTC, if any Attributes of time in
          the response Identifier are to be interpreted explicitly in the
          designated local time zone. It shall not be present otherwise.

        *Status*

        Success
          | ``0x0000`` Success

        Pending
          | ``0xFF00`` Matches are continuing, current match supplied
          | ``0xFF01`` Matches are continuing, warning

        Cancel
          | ``0xFE00`` Cancel

        Failure
          | ``0x0122`` SOP class not supported
          | ``0xA700`` Out of resources
          | ``0xA900`` Dataset does not match SOP class
          | ``0xC000`` to ``0xCFFF`` Unable to process

        References
        ----------

        * DICOM Standard, Part 4, `Annex K <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_K>`_.
        * [2] DICOM Standard, Part 7, Sections
          `9.1.2 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.1.2>`_,
          `9.3.2 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.2>`_
          and `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_.
        """
        if context.abstract_syntax == '1.2.840.10008.5.1.4.31':
            self._find_scp(req, context)
        else:
            raise ValueError(
                'The supplied abstract syntax is not valid for use with the '
                'Basic Worklist Management Service Class'
            )


class ColorPaletteQueryRetrieveServiceClass(QueryRetrieveServiceClass):
    """Implementation of the Color Palette QR Service."""
    pass


class DefinedProcedureProtocolQueryRetrieveServiceClass(QueryRetrieveServiceClass):
    """Implementation of the Defined Procedure Protocol QR Service."""
    pass


class HangingProtocolQueryRetrieveServiceClass(QueryRetrieveServiceClass):
    """Implementation of the Hanging Protocol QR Service."""
    pass


class ImplantTemplateQueryRetrieveServiceClass(QueryRetrieveServiceClass):
    """Implementation of the Implant Template QR Service."""
    pass


class NonPatientObjectStorageServiceClass(StorageServiceClass):
    """Implementation of the Non-Patient Object Storage Service"""
    statuses = NON_PATIENT_SERVICE_CLASS_STATUS


class ProtocolApprovalQueryRetrieveServiceClass(QueryRetrieveServiceClass):
    """Implementation of the Protocol Approval QR Service."""
    pass


class RelevantPatientInformationQueryServiceClass(ServiceClass):
    """Implementation of the Relevant Patient Information Query"""
    statuses = RELEVANT_PATIENT_SERVICE_CLASS_STATUS

    def SCP(self, req, context):
        """The SCP implementation for the Relevant Patient Information Query
        Service Class.

        Parameters
        ----------
        req : dimse_primitives.C_FIND
            The C-FIND request primitive sent by the peer.
        context : presentation.PresentationContext
            The presentation context that the SCP is operating under.

        See Also
        --------
        association.Association.send_c_find

        Notes
        -----
        **C-FIND Request**

        *Parameters*

        | (M) Message ID
        | (M) Affected SOP Class UID
        | (M) Priority
        | (M) Identifier

        *Identifier*

        The C-FIND request Identifier shall contain:

        * Key Attributes with values corresponding to Key Attributes contained
          in the Identifier of the request.
        * (0040,A504) Content Template Sequence, which shall include a single
          sequence item containing (0040,DB00) Template Identifier and
          (0008,0105) Mapping Resource attributes, to identify the template
          structure used in the C-FIND responses.
        * (0008,0005) Specific Character Set, if expanded or replacement
          character sets may be used in any of the Attributes in the request
          Identifier. It shall not be present otherwise.

        **C-FIND Response**

        *Parameters*

        | (U) Message ID
        | (M) Message ID Being Responded To
        | (U) Affected SOP Class UID
        | (C) Identifier
        | (M) Status

        *Status*

        Success
          | ``0x0000`` Success

        Pending
          | ``0xFF00`` Matches are continuing, current match supplied
          | ``0xFF01`` Matches are continuing, warning

        Cancel
          | ``0xFE00`` Matching terminated due to cancel request

        Failure
          | ``0x0122`` SOP class not supported
          | ``0xA700`` Out of resources
          | ``0xA900`` Identifier does not match SOP class
          | ``0xC100`` More than one match found
          | ``0xC200`` Unable to support requested template

        References
        ----------

        * DICOM Standard, Part 4, `Annex Q <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_Q>`_.
        * DICOM Standard, Part 7, Sections
           `9.1.2 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.1.2>`_,
           `9.3.2 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.2>`_
           and `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_.
        """
        # Build C-FIND response primitive
        rsp = C_FIND()
        rsp.MessageID = req.MessageID
        rsp.MessageIDBeingRespondedTo = req.MessageID
        rsp.AffectedSOPClassUID = req.AffectedSOPClassUID

        # Decode and log Identifier
        transfer_syntax = context.transfer_syntax[0]
        try:
            identifier = decode(req.Identifier,
                                transfer_syntax.is_implicit_VR,
                                transfer_syntax.is_little_endian)
            LOGGER.info('Find SCP Request Identifier:')
            LOGGER.info('')
            LOGGER.debug('# DICOM Dataset')
            for elem in identifier.iterall():
                LOGGER.info(elem)
            LOGGER.info('')
        except Exception as ex:
            LOGGER.error("Failed to decode the request's Identifier dataset.")
            LOGGER.exception(ex)
            # Failure - Unable to Process - Failed to decode Identifier
            rsp.Status = 0xC310
            rsp.ErrorComment = 'Unable to decode the dataset'
            self.dimse.send_msg(rsp, context.context_id)
            return

        try:
            responses = evt.trigger(
                self.assoc,
                evt.EVT_C_FIND,
                {
                    'request' : req,
                    'context' : context.as_tuple,
                    '_is_cancelled' : self.is_cancelled
                }
            )
            (rsp_status, rsp_identifier) = next(responses)
        except (StopIteration, TypeError):
            # There were no matches, so return Success
            # If success, then rsp_identifier is None
            rsp.Status = 0x0000
            LOGGER.info('Find SCP Response: (Success)')
            self.dimse.send_msg(rsp, context.context_id)
            return
        except Exception as ex:
            LOGGER.error("Exception in handler bound to 'evt.EVT_C_FIND'")
            LOGGER.exception(ex)
            rsp.Status = 0xC311
            self.dimse.send_msg(rsp, context.context_id)
            return

        rsp = self.validate_status(rsp_status, rsp)

        if rsp.Status in self.statuses:
            status = self.statuses[rsp.Status]
        else:
            # Unknown status
            self.dimse.send_msg(rsp, context.context_id)
            return

        if status[0] == STATUS_CANCEL:
            # If cancel, then rsp_identifier is None
            LOGGER.info('Received C-CANCEL-FIND RQ from peer')
            LOGGER.info('Find SCP Response: (Cancel)')
            self.dimse.send_msg(rsp, context.context_id)
            return
        elif status[0] == STATUS_FAILURE:
            # If failed, then rsp_identifier is None
            LOGGER.info('Find SCP Response: (Failure)')
            self.dimse.send_msg(rsp, context.context_id)
            return
        elif status[0] == STATUS_SUCCESS:
            # User isn't supposed to send these, but handle anyway
            # If success, then rsp_identifier is None
            LOGGER.info('Find SCP Response: (Success)')
            self.dimse.send_msg(rsp, context.context_id)
            return
        elif status[0] == STATUS_PENDING:
            # If pending, the rsp_identifier is the Identifier dataset
            bytestream = encode(rsp_identifier,
                                transfer_syntax.is_implicit_VR,
                                transfer_syntax.is_little_endian)
            bytestream = BytesIO(bytestream)

            if bytestream.getvalue() == b'':
                LOGGER.error("Failed to encode the received Identifier "
                             "dataset")
                # Failure: Unable to Process - Can't encode dataset
                #   returned by handler
                rsp.Status = 0xC312
                self.dimse.send_msg(rsp, context.context_id)
                return

            rsp.Identifier = bytestream

            LOGGER.info('Find SCP Response: (Pending)')
            LOGGER.debug('Find SCP Response Identifier:')
            LOGGER.debug('')
            LOGGER.debug('# DICOM Dataset')
            for elem in rsp_identifier.iterall():
                LOGGER.debug(elem)
            LOGGER.debug('')

            # Send pending response
            self.dimse.send_msg(rsp, context.context_id)

            # Send final success response
            rsp.Status = 0x0000
            LOGGER.info('Find SCP Response: (Success)')
            self.dimse.send_msg(rsp, context.context_id)


class SubstanceAdministrationQueryServiceClass(QueryRetrieveServiceClass):
    """Implementation of the Substance Administration Query Service"""
    statuses = SUBSTANCE_ADMINISTRATION_SERVICE_CLASS_STATUS

    def __init__(self, assoc):
        super(SubstanceAdministrationQueryServiceClass, self).__init__(assoc)

    def SCP(self, req, context):
        """The SCP implementation for the Relevant Patient Information Query
        Service Class.

        Parameters
        ----------
        req : dimse_primitives.C_FIND
            The C-FIND request primitive sent by the peer.
        context : presentation.PresentationContext
            The presentation context that the SCP is operating under.

        See Also
        --------
        association.Association.send_c_find

        Notes
        -----
        **C-FIND Request**

        *Parameters*

        | (M) Message ID
        | (M) Affected SOP Class UID
        | (M) Priority
        | (M) Identifier

        *Identifier*

        The C-FIND request Identifier shall contain:

        * Key Attributes with values corresponding to Key Attributes contained
          in the Identifier of the request.
        * (0008,0005) Specific Character Set, if expanded or replacement
          character sets may be used in any of the Attributes in the request
          Identifier. It shall not be present otherwise.

        **C-FIND Response**

        *Parameters*

        | (U) Message ID
        | (M) Message ID Being Responded To
        | (U) Affected SOP Class UID
        | (C) Identifier
        | (M) Status

        *Status*

        Success
          | ``0x0000`` Success

        Pending
          | ``0xFF00`` Matches are continuing, current match supplied
          | ``0xFF01`` Matches are continuing, warning

        Cancel
          | ``0xFE00`` Matching terminated due to cancel request

        Failure
          | ``0x0122`` SOP class not supported
          | ``0xA700`` Out of resources
          | ``0xA900`` Identifier does not match SOP class
          | ``0xC000`` to ``0xCFFF`` Unable to process

        References
        ----------

        * DICOM Standard, Part 4, `Annex V <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_V>`_.
        * DICOM Standard, Part 7, Sections
           `9.1.2 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.1.2>`_,
           `9.3.2 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.2>`_
           and `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_.
        """
        self._find_scp(req, context)
