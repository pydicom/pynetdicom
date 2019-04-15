"""Implements the supported Service Classes that make use of DIMSE-N."""

from io import BytesIO
import logging

from pynetdicom import evt
from pynetdicom.dsutils import encode
from pynetdicom.dimse_primitives import (
    N_ACTION, N_CREATE, N_DELETE, N_EVENT_REPORT, N_GET, N_SET
)
from pynetdicom.service_class import ServiceClass
from pynetdicom.status import (
    GENERAL_STATUS, code_to_category, _PROCEDURE_STEP_STATUS
)
from pynetdicom._globals import (
    STATUS_FAILURE,
    STATUS_SUCCESS,
    STATUS_WARNING,
    #STATUS_PENDING,
    #STATUS_CANCEL,
)


LOGGER = logging.getLogger('pynetdicom.service-n')


class DisplaySystemManagementServiceClass(ServiceClass):
    """Implementation of the Display System Management Service Class."""
    statuses = GENERAL_STATUS

    def SCP(self, req, context, info):
        """The implementation for the DIMSE N-GET service.

        Parameters
        ----------
        req : dimse_primitives.N_GET
            The N-GET request primitive sent by the peer.
        context : presentation.PresentationContext
            The presentation context that the service is operating under.
        info : dict
            A dict containing details about the association.

        See Also
        --------
        ae.ApplicationEntity.on_n_get
        association.Association.send_n_get

        Notes
        -----
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

        References
        ----------

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
            (rsp_status, ds) = evt.trigger(
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
            # Processing failure - Error in on_n_get callback
            rsp_status = 0x0110

        # Validate rsp_status and set rsp.Status accordingly
        rsp = self.validate_status(rsp_status, rsp)

        # Success or Warning, must return AttributeList dataset
        if code_to_category(rsp.Status) in [STATUS_SUCCESS, STATUS_WARNING]:
            # Encode the `dataset` using the agreed transfer syntax
            #   Will return None if failed to encode
            transfer_syntax = context.transfer_syntax[0]
            bytestream = encode(ds,
                                transfer_syntax.is_implicit_VR,
                                transfer_syntax.is_little_endian)

            if bytestream is not None:
                rsp.AttributeList = BytesIO(bytestream)
            else:
                LOGGER.error("Failed to encode the supplied Dataset")
                # Processing failure - Failed to encode dataset
                rsp.Status = 0x0110

        self.dimse.send_msg(rsp, context.context_id)


class ModalityPerformedProcedureStepServiceClass(ServiceClass):
    """Implementation of the Modality Performed Procedure Step Service Class"""
    statuses = _PROCEDURE_STEP_STATUS

    def SCP(self, req, context, info):
        """

        Parameters
        ----------
        req : dimse_primitives.N_CREATE or N_SET or N_GET or N_EVENT_REPORT
            The N-CREATE, N-SET, N-GET or N-EVENT-REPORT request primitive
            sent by the peer.
        context : presentation.PresentationContext
            The presentation context that the SCP is operating under.
        info : dict
            A dict containing details about the association.
        """
        if isinstance(req, N_CREATE):
            # Modality Performed Procedure Step
            self._create_scp(req, context)
        elif isinstance(req, N_EVENT_REPORT):
            # Modality Performed Procedure Step Notification
            self._event_report_scp(req, context)
        elif isinstance(req, N_GET):
            # Modality Performed Procedure Step Retrieve
            self._get_scp(req, context)
        elif isinstance(req, N_SET):
            # Modality Performed Procedure Step
            self._set_scp(req, context)
        else:
            raise ValueError(
                "Invalid DIMSE primitive '{}' used with Modality "
                "Performed Procedure Step"
                .format(req.__class__.__name__)
            )

    def _create_scp(self, req, context):
        """Implementation of the N-CREATE SCP.

        Parameters
        ----------
        req : dimse_primitives.N_CREATE
            The N-CREATE request primitive sent by the peer.
        context : presentation.PresentationContext
            The presentation context that the SCP is operating under.

        Notes
        -----
        **N-CREATE Request**

        *Parameters*

        | (M) Message ID
        | (M) Affected SOP Class UID
        | (U) Affected SOP Instance UID
        | (U) Attribute List

        As per the DICOM Standard, Annex F.7.2.1.2, the SCU shall specify the
        SOP Class UID and SOP Instance UID in the N-CREATE request.

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

        References
        ----------

        * DICOM Standard, Part 4, `Annex F <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_F>`_
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
            # If success or warning then there may be a dataset
            transfer_syntax = context.transfer_syntax[0]
            bytestream = encode(ds,
                                transfer_syntax.is_implicit_VR,
                                transfer_syntax.is_little_endian)
            bytestream = BytesIO(bytestream)

            if bytestream.getvalue() == b'':
                LOGGER.error(
                    "Failed to encode the N-CREATE response's 'Attribute "
                    "List' dataset"
                )
                # Processing failure
                rsp.Status = 0x0110
            else:
                rsp.AttributeList = bytestream

        # Send response primitive
        self.dimse.send_msg(rsp, context.context_id)

    def _event_report_scp(self, req, context):
        """Implementation of the N-EVENT-REPORT SCP.

        Parameters
        ----------
        req : dimse_primitives.N_EVENT_REPORT
            The N-EVENT-REPORT request primitive sent by the peer.
        context : presentation.PresentationContext
            The presentation context that the SCP is operating under.

        Notes
        -----
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
          | ``0x0000`` Success

        Failure
          | ``0x0110`` Processing failure
          | ``0x0112`` No such SOP Instance
          | ``0x0113`` No such event type
          | ``0x0114`` No such argument
          | ``0x0115`` Invalid argument value
          | ``0x0117`` Invalid object Instance
          | ``0x0118`` No such SOP Class
          | ``0x0119`` Class-Instance conflict
          | ``0x0210`` Duplicate invocation
          | ``0x0211`` Unrecognised operation
          | ``0x0212`` Mistyped argument
          | ``0x0213`` Resource limitation

        References
        ----------

        * DICOM Standard, Part 4, `Annex F <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_F>`_
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
            # If success or warning then there may be a dataset
            transfer_syntax = context.transfer_syntax[0]
            bytestream = encode(ds,
                                transfer_syntax.is_implicit_VR,
                                transfer_syntax.is_little_endian)
            bytestream = BytesIO(bytestream)

            if bytestream.getvalue() == b'':
                LOGGER.error(
                    "Failed to encode the N-EVENT-REPORT response's 'Event "
                    "Reply' dataset"
                )
                # Processing failure
                rsp.Status = 0x0110
            else:
                rsp.EventReply = bytestream

        # Send response primitive
        self.dimse.send_msg(rsp, context.context_id)

    def _get_scp(self, req, context):
        """

        Parameters
        ----------
        req : dimse_primitives.N_GET
            The N-GET request primitive sent by the peer.
        context : presentation.PresentationContext
            The presentation context that the service is operating under.
        info : dict
            A dict containing details about the association.

        See Also
        --------
        ae.ApplicationEntity.on_n_get
        association.Association.send_n_get

        Notes
        -----
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
          | ``0x0107`` - SOP Class not supported
          | ``0x0110`` - Processing failure
          | ``0x0112`` - No such SOP Instance
          | ``0x0117`` - Invalid object instance
          | ``0x0118`` - No such SOP Class
          | ``0x0119`` - Class-Instance conflict
          | ``0x0122`` - SOP Class not supported
          | ``0x0124`` - Refused: not authorised
          | ``0x0210`` - Duplicate invocation
          | ``0x0211`` - Unrecognised operation
          | ``0x0212`` - Mistyped argument
          | ``0x0213`` - Resource limitation

        References
        ----------

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
            # Processing failure - Error in on_n_get callback
            rsp.Status = 0x0110
            self.dimse.send_msg(rsp, context.context_id)
            return

        # Validate rsp_status and set rsp.Status accordingly
        rsp = self.validate_status(status, rsp)

        # Success or Warning, must return AttributeList dataset
        if code_to_category(rsp.Status) in [STATUS_SUCCESS, STATUS_WARNING]:
            # Encode the `dataset` using the agreed transfer syntax
            #   Will return None if failed to encode
            transfer_syntax = context.transfer_syntax[0]
            bytestream = encode(ds,
                                transfer_syntax.is_implicit_VR,
                                transfer_syntax.is_little_endian)

            if bytestream is not None:
                rsp.AttributeList = BytesIO(bytestream)
            else:
                LOGGER.error("Failed to encode the supplied Dataset")
                # Processing failure - Failed to encode dataset
                rsp.Status = 0x0110

        self.dimse.send_msg(rsp, context.context_id)

    def _set_scp(self, req, context):
        """Implementation of the N-SET SCP.

        Parameters
        ----------
        req : dimse_primitives.N_SET
            The N-SET request primitive sent by the peer.
        context : presentation.PresentationContext
            The presentation context that the SCP is operating under.

        Notes
        -----
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

        References
        ----------

        * DICOM Standard, Part 4, `Annex F <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_F>`_
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
            # If success or warning then there may be a dataset
            transfer_syntax = context.transfer_syntax[0]
            bytestream = encode(ds,
                                transfer_syntax.is_implicit_VR,
                                transfer_syntax.is_little_endian)
            bytestream = BytesIO(bytestream)

            if bytestream.getvalue() == b'':
                LOGGER.error(
                    "Failed to encode the N-SET response's 'Attribute "
                    "List' dataset"
                )
                # Processing failure
                rsp.Status = 0x0110
            else:
                rsp.AttributeList = bytestream

        # Send response primitive
        self.dimse.send_msg(rsp, context.context_id)
