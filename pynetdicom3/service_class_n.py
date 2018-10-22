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
)


LOGGER = logging.getLogger('pynetdicom3.service-n')


# Lets try something a little different

def _n_get_scp(req, context, info, statuses):
    """The implementation for the DIMSE N-GET service.

    Parameters
    ----------
    req : dimse_primitives.C_ECHO
        The N-GET request primitive sent by the peer.
    context : presentation.PresentationContext
        The presentation context that the service is operating under.
    info : dict
        A dict containing details about the association.
    statuses : dict
        A dict containing possible statuses that may be used when responding
        to the service user.

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

    """
    # Build N-GET response primitive
    rsp = N_GET()
    rsp.MessageIDBeingRespondedTo = req.MessageID
    rsp.AffectedSOPClassUID = req.RequestedSOPClassUID
    rsp.AffectedSOPInstanceUID = req.RequestedSOPInstanceUID

    info['parameters'] = {
         'message_id' : req.MessageID,
         'requested_sop_class' : req.RequestedSOPClassUID,
         'requested_sop_instance' : req.RequestedSOPInstanceUID,
    }

    # Attempt to run the ApplicationEntity's on_n_get callback
    try:
        (rsp_status, ds) = self.AE.on_n_get(req.AttributeIdentifierList,
                                            context.as_tuple, info)
    except Exception as exc:
        LOGGER.error(
            "Exception in the ApplicationEntity.on_n_get() callback"
        )
        LOGGER.exception(exc)
        # Failure: Cannot Understand - Error in on_n_get callback
        # FIXME: assign custom status value
        rsp_status = 0x0110

    # Validate rsp_status and set rsp.Status accordingly
    rsp = self.validate_status(rsp_status, rsp)

    # Encode the `dataset` using the agreed transfer syntax
    #   Will return None if failed to encode
    transfer_syntax = context.transfer_syntax[0]
    bytestream = encode(ds,
                        transfer_syntax.is_implicit_VR,
                        transfer_syntax.is_little_endian)

    if bytestream is not None:
        req.AttributeList = BytesIO(bytestream)
    else:
        LOGGER.error("Failed to encode the supplied Dataset")
        rsp.Status = 0x0117
        req.AttributeList = b''

    self.DIMSE.send_msg(rsp, context.context_id)


class DisplaySystemManagementServiceClass(ServiceClass):
    """"""
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
        statuses : dict
            A dict containing possible statuses that may be used when responding
            to the service user.

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

        """
        # Build N-GET response primitive
        rsp = N_GET()
        rsp.MessageIDBeingRespondedTo = req.MessageID
        rsp.AffectedSOPClassUID = req.RequestedSOPClassUID
        rsp.AffectedSOPInstanceUID = req.RequestedSOPInstanceUID

        info['parameters'] = {
             'message_id' : req.MessageID,
             'requested_sop_class' : req.RequestedSOPClassUID,
             'requested_sop_instance' : req.RequestedSOPInstanceUID,
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
            # FIXME
            # Failure: Cannot Understand - Error in on_n_get callback
            rsp_status = 0x0110

        # Validate rsp_status and set rsp.Status accordingly
        rsp = self.validate_status(rsp_status, rsp)

        # Success, must return AttributeList dataset
        if rsp.Status == 0x0000:
            # Encode the `dataset` using the agreed transfer syntax
            #   Will return None if failed to encode
            transfer_syntax = context.transfer_syntax[0]
            bytestream = encode(ds,
                                transfer_syntax.is_implicit_VR,
                                transfer_syntax.is_little_endian)

            if bytestream is not None:
                req.AttributeList = BytesIO(bytestream)
            else:
                LOGGER.error("Failed to encode the supplied Dataset")
                rsp.Status = 0x0117

        self.DIMSE.send_msg(rsp, context.context_id)
