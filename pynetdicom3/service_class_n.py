"""Implements the supported Service Classes that make use of DIMSE-N."""

from io import BytesIO
import logging
import sys

from pydicom.dataset import Dataset
from pydicom.uid import UID

from pynetdicom3.dsutils import decode, encode
from pynetdicom3.dimse_primitives import (
    N_GET, N_SET, N_EVENT_REPORT, N_ACTION, N_CREATE, N_DELETE
)
from pynetdicom3.service_class import ServiceClass
from pynetdicom3.status import (
    STATUS_FAILURE,
    STATUS_SUCCESS,
    STATUS_WARNING,
    STATUS_PENDING,
    STATUS_CANCEL,
    GENERAL_STATUS,
    code_to_category,
)


LOGGER = logging.getLogger('pynetdicom3.service-n')


class DisplaySystemManagementServiceClass(ServiceClass):
    """Implementation of the Display System Management Service Class."""
    statuses = GENERAL_STATUS

    def SCP(self, req, context, info):
        """The implementation for the DIMSE N-GET service.

        Parameters
        ----------
        req : dimse_primitives.C_ECHO
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
          `10.3.2 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_10.3.2>`_ and
          `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_
        """
        # Build N-GET response primitive
        rsp = N_GET()
        rsp.MessageIDBeingRespondedTo = req.MessageID
        rsp.AffectedSOPClassUID = req.RequestedSOPClassUID
        rsp.AffectedSOPInstanceUID = req.RequestedSOPInstanceUID

        info['parameters'] = {
             'message_id' : req.MessageID,
             'requested_sop_class_uid' : req.RequestedSOPClassUID,
             'requested_sop_instance_uid' : req.RequestedSOPInstanceUID,
        }

        # Attempt to run the ApplicationEntity's on_n_get callback
        try:
            # Send the value rather than the element
            (rsp_status, ds) = self.AE.on_n_get(req.AttributeIdentifierList,
                                                context.as_tuple, info)
        except Exception as exc:
            LOGGER.error(
                "Exception in the ApplicationEntity.on_n_get() callback"
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

        self.DIMSE.send_msg(rsp, context.context_id)
