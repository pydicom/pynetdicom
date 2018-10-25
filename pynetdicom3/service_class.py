"""Implements the supported Service Classes."""

from io import BytesIO
import logging
import sys

from pydicom.dataset import Dataset
from pydicom.uid import UID

from pynetdicom3.dsutils import decode, encode
from pynetdicom3.dimse_primitives import C_STORE, C_ECHO, C_MOVE, C_GET, C_FIND
from pynetdicom3.status import (
    VERIFICATION_SERVICE_CLASS_STATUS,
    STORAGE_SERVICE_CLASS_STATUS,
    QR_FIND_SERVICE_CLASS_STATUS,
    QR_MOVE_SERVICE_CLASS_STATUS,
    QR_GET_SERVICE_CLASS_STATUS,
    MODALITY_WORKLIST_SERVICE_CLASS_STATUS,
    RELEVANT_PATIENT_SERVICE_CLASS_STATUS,
    SUBSTANCE_ADMINISTRATION_SERVICE_CLASS_STATUS,
    NON_PATIENT_SERVICE_CLASS_STATUS,
    STATUS_FAILURE,
    STATUS_SUCCESS,
    STATUS_WARNING,
    STATUS_PENDING,
    STATUS_CANCEL,
)


LOGGER = logging.getLogger('pynetdicom3.service')


class ServiceClass(object):
    """The base class for all the service classes.

    TODO: Perhaps define some class attributes such as self.AE = None
        self.UID = None,
        then call ServiceClass.__init__() in the subclasses?

    Attributes
    ----------
    AE : ae.ApplicationEntity
        The local AE (needed for the callbacks).
    DIMSE : dimse.DIMSEServiceProvider
        The DIMSE service provider (needed to send/receive messages)
    """
    def __init__(self):
        self.AE = None
        self.DIMSE = None
        self.ACSE = None
        self.maxpdulength = None

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

    def SCP(self, req, context, info):
        """The implementation of the corresponding service class.

        Parameters
        ----------
        req : A DIMSE message primitive
            The message request primitive sent by the peer.
        context : presentation.PresentationContext
            The presentation context that the SCP is operating under.
        info : dict
            A dict containing details about the association.
        """
        msg = (
            "No service has been implemented for the SOP Class UID '{}'"
            .format(context.abstract_syntax)
        )
        LOGGER.error(msg)
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




# Service Class implementations
class VerificationServiceClass(ServiceClass):
    """Implementation of the Verification Service Class."""
    statuses = VERIFICATION_SERVICE_CLASS_STATUS

    def SCP(self, req, context, info):
        """The SCP implementation for the Verification Service Class.

        Will always return 0x0000 (Success) unless the user returns a different
        (valid) status value from the `AE.on_c_echo` callback.

        Parameters
        ----------
        req : dimse_primitives.C_ECHO
            The C-ECHO request primitive sent by the peer.
        context : presentation.PresentationContext
            The presentation context that the SCP is operating under.
        info : dict
            A dict containing details about the association.

        See Also
        --------
        ae.ApplicationEntity.on_c_echo
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

        The DICOM Standard, Part 7 (Table 9.3-13) indicates that the Status value
        of a C-ECHO response "shall have a value of Success". However Section
        9.1.5.1.4 indicates it may have any of the following values:

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
          `9.3.5 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.5>`_ and
          `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_
        """
        # Build C-ECHO response primitive
        rsp = C_ECHO()
        rsp.MessageID = req.MessageID
        rsp.MessageIDBeingRespondedTo = req.MessageID
        rsp.AffectedSOPClassUID = req.AffectedSOPClassUID

        info['parameters'] = {
             'message_id' : req.MessageID
        }

        # Try and run the user's on_c_echo callback. The callback should return
        #   the Status as either an int or Dataset, and any failures in the
        #   callback results in 0x0000 'Success'
        try:
            status = self.AE.on_c_echo(context.as_tuple, info)
            if isinstance(status, Dataset):
                if 'Status' not in status:
                    raise AttributeError("The 'status' dataset returned by "
                                         "'on_c_echo' must contain"
                                         "a (0000,0900) Status element")
                for elem in status:
                    if hasattr(rsp, elem.keyword):
                        setattr(rsp, elem.keyword, elem.value)
                    else:
                        LOGGER.warning("The 'status' dataset returned by "
                                       "'on_c_echo' contained an unsupported "
                                       "Element '%s'.", elem.keyword)
            elif isinstance(status, int):
                rsp.Status = status
            else:
                raise TypeError("Invalid 'status' returned by 'on_c_echo'")

            # Check Status validity
            if not self.is_valid_status(rsp.Status):
                LOGGER.warning("Unknown 'status' value returned by 'on_c_echo' "
                               "callback - 0x{0:04x}".format(rsp.Status))
        except Exception as ex:
            LOGGER.exception(ex)
            LOGGER.error("Exception in the 'on_c_echo' callback, responding "
                         "with default 'status' value of 0x0000 (Success).")
            rsp.Status = 0x0000

        # Send primitive
        self.DIMSE.send_msg(rsp, context.context_id)


class StorageServiceClass(ServiceClass):
    """Implementation of the Storage Service Class."""
    uid = '1.2.840.10008.4.2'
    statuses = STORAGE_SERVICE_CLASS_STATUS

    def SCP(self, req, context, info):
        """The SCP implementation for the Storage Service Class.

        Parameters
        ----------
        req : dimse_primitives.C_STORE
            The C-STORE request primitive sent by the peer.
        context : presentation.PresentationContext
            The presentation context that the SCP is operating under.
        info : dict
            A dict containing details about the association.

        See Also
        --------
        ae.ApplicationEntity.on_c_store
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
          `9.3.1 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.1>`_ and
          `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_.
        """
        # Build C-STORE response primitive
        rsp = C_STORE()
        rsp.MessageID = req.MessageID
        rsp.MessageIDBeingRespondedTo = req.MessageID
        rsp.AffectedSOPInstanceUID = req.AffectedSOPInstanceUID
        rsp.AffectedSOPClassUID = req.AffectedSOPClassUID

        # Attempt to decode the request's dataset
        transfer_syntax = context.transfer_syntax[0]
        try:
            ds = decode(req.DataSet,
                        transfer_syntax.is_implicit_VR,
                        transfer_syntax.is_little_endian)
            # Trigger exception if bad dataset
            for elem in ds:
                pass
        except Exception as ex:
            LOGGER.error("Failed to decode the received dataset")
            LOGGER.exception(ex)
            # Failure: Cannot Understand - Dataset decoding error
            rsp.Status = 0xC210
            rsp.ErrorComment = 'Unable to decode the dataset'
            self.DIMSE.send_msg(rsp, context.context_id)
            return

        info['parameters'] = {
             'message_id' : req.MessageID,
             'priority' : req.Priority,
             'originator_aet' : req.MoveOriginatorApplicationEntityTitle,
             'originator_message_id' : req.MoveOriginatorMessageID
        }

        # Attempt to run the ApplicationEntity's on_c_store callback
        try:
            rsp_status = self.AE.on_c_store(ds, context.as_tuple, info)
        except Exception as ex:
            LOGGER.error("Exception in the ApplicationEntity.on_c_store() "
                         "callback")
            LOGGER.exception(ex)
            # Failure: Cannot Understand - Error in on_c_store callback
            rsp_status = 0xC211

        # Validate rsp_status and set rsp.Status accordingly
        rsp = self.validate_status(rsp_status, rsp)
        self.DIMSE.send_msg(rsp, context.context_id)


class QueryRetrieveServiceClass(ServiceClass):
    """Implementation of the Query/Retrieve Service Class."""
    statuses = None
    # Used with Composite Instance Retrieve Without Bulk Data
    BULK_DATA_KEYWORDS = [
        'PixelData', 'FloatPixelData', 'DoubleFloatPixelData',
        'PixelDataProviderURL', 'SpectroscopyData', 'OverlayData',
        'CurveData', 'AudioSampleData', 'EncapsulatedDocument'
    ]

    def SCP(self, req, context, info):
        """The SCP implementation for the Query/Retrieve Service Class.

        Parameters
        ----------
        req : dimse_primitives.C_FIND or C_GET or C_MOVE
            The request primitive received from the peer.
        context : presentation.PresentationContext
            The presentation context that the SCP is operating under.
        info : dict
            A dict containing details about the association.
        """
        if context.abstract_syntax in ['1.2.840.10008.5.1.4.1.2.1.1',
                                       '1.2.840.10008.5.1.4.1.2.2.1',
                                       '1.2.840.10008.5.1.4.1.2.3.1',
                                       '1.2.840.10008.5.1.4.20.1',
                                       '1.2.840.10008.5.1.4.38.2',
                                       '1.2.840.10008.5.1.4.39.2',
                                       '1.2.840.10008.5.1.4.43.2',
                                       '1.2.840.10008.5.1.4.44.2',
                                       '1.2.840.10008.5.1.4.45.2']:
            self.statuses = QR_FIND_SERVICE_CLASS_STATUS
            self._find_scp(req, context, info)
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
                                         '1.2.840.10008.5.1.4.45.4']:
            self.statuses = QR_GET_SERVICE_CLASS_STATUS
            self._get_scp(req, context, info)
        elif context.abstract_syntax in ['1.2.840.10008.5.1.4.1.2.1.2',
                                         '1.2.840.10008.5.1.4.1.2.2.2',
                                         '1.2.840.10008.5.1.4.1.2.3.2',
                                         '1.2.840.10008.5.1.4.1.2.4.2',
                                         '1.2.840.10008.5.1.4.20.2',
                                         '1.2.840.10008.5.1.4.38.3',
                                         '1.2.840.10008.5.1.4.39.3',
                                         '1.2.840.10008.5.1.4.43.3',
                                         '1.2.840.10008.5.1.4.44.3',
                                         '1.2.840.10008.5.1.4.45.3']:
            self.statuses = QR_MOVE_SERVICE_CLASS_STATUS
            self._move_scp(req, context, info)
        else:
            raise ValueError(
                'The supplied abstract syntax is not valid for use with the '
                'Query/Retrieve Service Class'
            )

    def _find_scp(self, req, context, info):
        """The SCP implementation for Query/Retrieve - Find.

        Parameters
        ----------
        req : dimse_primitives.C_FIND
            The C-FIND request primitive received from the peer.
        context : presentation.PresentationContext
            The presentation context that the SCP is operating under.
        info : dict
            A dict containing details about the association.

        See Also
        --------
        ae.ApplicationEntity.on_c_find
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
          Conversion has been accepted during Extended Negotiation. It shall not
          be present otherwise.
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
           `9.3.2 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.2>`_ and
           `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_.
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
            self.DIMSE.send_msg(rsp, context.context_id)
            return

        info['parameters'] = {
             'message_id' : req.MessageID,
             'priority' : req.Priority
        }

        stopper = object()
        # This will wrap exceptions during iteration and return a good value.
        def wrap_on_c_find():
            try:
                # We unpack here so that the error is still caught
                for val1, val2 in self.AE.on_c_find(identifier,
                                                    context.as_tuple,
                                                    info):
                    yield val1, val2
            except Exception:
                # TODO: special (singleton) value
                yield stopper, sys.exc_info()

        ii = -1  # So if there are no results, log below doesn't break
        # Iterate through the results
        for ii, (rsp_status, rsp_identifier) in enumerate(wrap_on_c_find()):
            # We only want to catch exceptions in the user code, not in ours.
            if rsp_status is stopper:
                exc_info = rsp_identifier
                LOGGER.exception("Exception in user's on_c_find implementation.", exc_info=exc_info)
                # Failure - Unable to Process - Error in on_c_find callback
                rsp.Status = 0xC311
                self.DIMSE.send_msg(rsp, context.context_id)
                return
            # Validate rsp_status and set rsp.Status accordingly
            rsp = self.validate_status(rsp_status, rsp)

            if rsp.Status in self.statuses:
                status = self.statuses[rsp.Status]
            else:
                # Unknown status
                self.DIMSE.send_msg(rsp, context.context_id)
                return

            if status[0] == STATUS_CANCEL:
                # If cancel, then rsp_identifier is None
                LOGGER.info('Received C-CANCEL-FIND RQ from peer')
                LOGGER.info('Find SCP Response: (Cancel)')
                self.DIMSE.send_msg(rsp, context.context_id)
                return
            elif status[0] == STATUS_FAILURE:
                # If failed, then rsp_identifier is None
                LOGGER.info('Find SCP Response: (Failure - %s)', status[1])
                self.DIMSE.send_msg(rsp, context.context_id)
                return
            elif status[0] == STATUS_SUCCESS:
                # User isn't supposed to send these, but handle anyway
                # If success, then rsp_identifier is None
                LOGGER.info('Find SCP Response: %s (Success)', ii + 1)
                self.DIMSE.send_msg(rsp, context.context_id)
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
                    #   returned by on_c_find callback
                    rsp.Status = 0xC312
                    self.DIMSE.send_msg(rsp, context.context_id)
                    return

                rsp.Identifier = bytestream

                LOGGER.info('Find SCP Response: %s (Pending)', ii + 1)
                LOGGER.debug('Find SCP Response Identifier:')
                LOGGER.debug('')
                LOGGER.debug('# DICOM Dataset')
                for elem in rsp_identifier.iterall():
                    LOGGER.debug(elem)
                LOGGER.debug('')

                self.DIMSE.send_msg(rsp, context.context_id)

            # Reset the response Identifier
            rsp.Identifier = None

        # Send final success response
        rsp.Status = 0x0000
        LOGGER.info('Find SCP Response: %s (Success)', ii + 2)
        self.DIMSE.send_msg(rsp, context.context_id)

    def _get_scp(self, req, context, info):
        """The SCP implementation for Query/Retrieve - Get.

        Parameters
        ----------
        req : dimse_primitives.C_GET
            The C-GET request primitive sent by the peer.
        context : presentation.PresentationContext
            The presentation context that the SCP is operating under.
        info : dict
            A dict containing details about the association.

        See Also
        --------
        ae.ApplicationEntity.on_c_get
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
          | ``0xB000`` Sub-operations complete: one or more failures or warnings

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
           `9.3.3 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.3>`_ and
           `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_.
        """
        # Build C-GET response primitive
        rsp = C_GET()
        rsp.MessageID = req.MessageID
        rsp.MessageIDBeingRespondedTo = req.MessageID
        rsp.AffectedSOPClassUID = req.AffectedSOPClassUID

        # Attempt to decode the request's Identifier dataset
        transfer_syntax = context.transfer_syntax[0]
        try:
            identifier = decode(req.Identifier,
                                transfer_syntax.is_implicit_VR,
                                transfer_syntax.is_little_endian)
            LOGGER.info('Get SCP Request Identifier:')
            LOGGER.info('')
            LOGGER.debug('# DICOM Data Set')
            for elem in identifier.iterall():
                LOGGER.info(elem)
            LOGGER.info('')
        except Exception as ex:
            LOGGER.error("Failed to decode the request's Identifier dataset")
            LOGGER.exception(ex)
            # Failure: Cannot Understand - Dataset decoding error
            rsp.Status = 0xC410
            rsp.ErrorComment = 'Unable to decode the dataset'
            self.DIMSE.send_msg(rsp, context.context_id)
            return

        info['parameters'] = {
             'message_id' : req.MessageID,
             'priority' : req.Priority
        }

        # Callback - C-GET
        try:
            # yields int, (status, dataset), ...
            result = self.AE.on_c_get(identifier, context.as_tuple, info)
        except Exception as ex:
            LOGGER.error("Exception in user's on_c_get implementation.")
            LOGGER.exception(ex)
            rsp.Status = 0xC411
            self.DIMSE.send_msg(rsp, context.context_id)
            return

        # Number of C-STORE sub-operations
        try:
            no_suboperations = int(next(result))
        except Exception as ex:
            LOGGER.error("'on_c_get' yielded an invalid number of "
                         "sub-operations value")
            LOGGER.exception(ex)
            rsp.Status = 0xC413
            self.DIMSE.send_msg(rsp, context.context_id)
            return

        # Track the sub operation results [remaining, failed, warning, complete]
        store_results = [no_suboperations, 0, 0, 0]

        # Store the SOP Instance UIDs from any failed C-STORE sub-operations
        failed_instances = []
        def _add_failed_instance(ds):
            if hasattr(ds, 'SOPInstanceUID'):
                failed_instances.append(ds.SOPInstanceUID)

        # Iterate through the results
        # C-GET Pending responses are optional!
        for ii, (rsp_status, dataset) in enumerate(result):
            # All sub-operations are complete
            if store_results[0] <= 0:
                LOGGER.warning("'on_c_get' yielded further (status, dataset) "
                               "results but these will be ignored as the "
                               "sub-operations are complete")
                break

            # Validate rsp_status and set rsp.Status accordingly
            rsp = self.validate_status(rsp_status, rsp)
            if rsp.Status in self.statuses:
                status = self.statuses[rsp.Status]
            else:
                # Unknown status
                self.DIMSE.send_msg(rsp, context.context_id)
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
                self.DIMSE.send_msg(rsp, context.context_id)
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
                self.DIMSE.send_msg(rsp, context.context_id)
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

                self.DIMSE.send_msg(rsp, context.context_id)
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
                    self.DIMSE.send_msg(rsp, context.context_id)
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
                    store_status = self.ACSE.parent.send_c_store(dataset)
                    store_status = \
                        STORAGE_SERVICE_CLASS_STATUS[store_status.Status]
                except Exception as ex:
                    # An exception implies a C-STORE failure
                    LOGGER.warning("C-STORE sub-operation failed.")
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
                self.DIMSE.send_msg(rsp, context.context_id)

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

        self.DIMSE.send_msg(rsp, context.context_id)

    def _move_scp(self, req, context, info):
        """The SCP implementation for Query/Retrieve - Move.

        Parameters
        ----------
        req : dimse_primitives.C_MOVE
            The C-MOVE request primitive sent by the peer.
        context : presentation.PresentationContext
            The presentation context that the SCP is operating under.
        info : dict
            A dict containing details about the association.

        See Also
        --------
        ae.ApplicationEntity.on_c_move
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
           `9.3.4 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.4>`_ and
           `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_.
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
        except Exception as ex:
            LOGGER.error("Failed to decode the request's Identifier dataset")
            LOGGER.exception(ex)
            # Failure: Cannot Understand - Dataset decoding error
            rsp.Status = 0xC510
            rsp.ErrorComment = 'Unable to decode the dataset'
            self.DIMSE.send_msg(rsp, context.context_id)
            return

        info['parameters'] = {
             'message_id' : req.MessageID,
             'priority' : req.Priority
        }

        # Callback - C-MOVE
        try:
            # yields (addr, port), int, (status, dataset), ...
            result = self.AE.on_c_move(identifier,
                                       req.MoveDestination,
                                       context.as_tuple,
                                       info)
        except Exception as ex:
            LOGGER.error("Exception in user's on_c_move implementation.")
            LOGGER.exception(ex)
            # Failure - Unable to process - Error in on_c_move callback
            rsp.Status = 0xC511
            self.DIMSE.send_msg(rsp, context.context_id)
            return

        try:
            destination = next(result)
            no_suboperations = next(result)
        except StopIteration:
            LOGGER.exception("The on_c_move callback must yield the (address, "
                             "port) of the destination AE, then yield the "
                             "number of sub-operations, then yield (status "
                             "dataset) pairs.")
            # Failure - Unable to process - Error in on_c_move yield
            rsp.Status = 0xC514
            self.DIMSE.send_msg(rsp, context.context_id)
            return

        # Check number of C-STORE sub-operations
        try:
            no_suboperations = int(no_suboperations)
        except Exception as ex:
            LOGGER.error("'on_c_move' yielded an invalid number of "
                         "sub-operations value")
            LOGGER.exception(ex)
            rsp.Status = 0xC513
            self.DIMSE.send_msg(rsp, context.context_id)
            return

        # Request new association with Move Destination
        try:
            # Unknown Move Destination
            if None in destination:
                LOGGER.error('Unknown Move Destination: %s',
                             req.MoveDestination.decode('ascii'))
                # Failure - Move destination unknown
                rsp.Status = 0xA801
                self.DIMSE.send_msg(rsp, context.context_id)
                return

            store_assoc = self.AE.associate(destination[0],
                                            destination[1],
                                            ae_title=req.MoveDestination)
        except Exception as ex:
            LOGGER.error("'on_c_move' yielded an invalid destination AE (addr, "
                         "port) value")
            LOGGER.exception(ex)
            # Failure - Unable to process - Bad on_c_move destination
            rsp.Status = 0xC515
            self.DIMSE.send_msg(rsp, context.context_id)
            return

        # Track the sub operation results [remaining, failed, warning, complete]
        store_results = [no_suboperations, 0, 0, 0]

        # Store the SOP Instance UIDs from any failed C-STORE sub-operations
        failed_instances = []
        def _add_failed_instance(ds):
            if hasattr(ds, 'SOPInstanceUID'):
                failed_instances.append(ds.SOPInstanceUID)

        if store_assoc.is_established:
            # Iterate through the remaining callback (status, dataset) yields
            for ii, (rsp_status, dataset) in enumerate(result):
                # All sub-operations are complete
                if store_results[0] <= 0:
                    LOGGER.warning("'on_c_move' yielded further (status, "
                                   "dataset) results but these will be "
                                   "ignored as the sub-operations are "
                                   "complete")
                    break

                # Validate rsp_status and set rsp.Status accordingly
                rsp = self.validate_status(rsp_status, rsp)
                if rsp.Status in self.statuses:
                    status = self.statuses[rsp.Status]
                else:
                    # Unknown status
                    store_assoc.release()
                    self.DIMSE.send_msg(rsp, context.context_id)
                    return

                # If usr_status is Cancel, Failure, Warning or Success then
                #   generate a final response, if Pending then do C-STORE
                #   sub-operation
                if status[0] == STATUS_CANCEL:
                    # If cancel, then dataset is a Dataset with a
                    #   'FailedSOPInstanceUIDList' element
                    LOGGER.info('Move SCP Received C-CANCEL-MOVE RQ from peer')
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

                    self.DIMSE.send_msg(rsp, context.context_id)
                    return
                elif status[0] in [STATUS_FAILURE, STATUS_WARNING]:
                    # If failed or warning, then dataset is a Dataset with a
                    #   'FailedSOPInstanceUIDList' element
                    LOGGER.info('Move SCP Result (%s - %s)',
                                status[0],
                                status[1])
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

                    self.DIMSE.send_msg(rsp, context.context_id)
                    return
                elif status[0] == STATUS_SUCCESS:
                    # If success, then dataset is None
                    store_assoc.release()

                    # If the user yields Success, check it
                    if store_results[1] or store_results[2]:
                        LOGGER.info('Move SCP Response: (Warning)')

                        ds = Dataset()
                        ds.FailedSOPInstanceUIDList = failed_instances
                        bytestream = encode(ds,
                                            transfer_syntax.is_implicit_VR,
                                            transfer_syntax.is_little_endian)

                        rsp.Identifier = BytesIO(bytestream)
                        rsp.Status = 0xB000
                    else:
                        LOGGER.info('Move SCP Response: (Warning)')
                        rsp.Identifier = None

                    rsp.NumberOfRemainingSuboperations = None
                    rsp.NumberOfFailedSuboperations = store_results[1]
                    rsp.NumberOfWarningSuboperations = store_results[2]
                    rsp.NumberOfCompletedSuboperations = store_results[3]

                    self.DIMSE.send_msg(rsp, context.context_id)
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
                        self.DIMSE.send_msg(rsp, context.context_id)
                        continue

                    LOGGER.info('Move SCP Response %s (Pending)', ii)

                    # Send `dataset` via C-STORE sub-operations over the
                    #   association and check that the response's Status exists
                    #   and is a known value
                    try:
                        store_status = store_assoc.send_c_store(
                            dataset,
                            originator_aet=self.AE.ae_title,
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

                    self.DIMSE.send_msg(rsp, context.context_id)

            store_assoc.release()

        else:
            # Failed to associate with Move Destination AE
            LOGGER.error('Move SCP: Unable to associate with destination AE')
            rsp.Status = 0xA801
            self.DIMSE.send_msg(rsp, context.context_id)

            # FIXME - shouldn't have to manually close the socket like this
            store_assoc.dul.scu_socket.close()
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

        self.DIMSE.send_msg(rsp, context.context_id)


class BasicWorklistManagementServiceClass(QueryRetrieveServiceClass):
    """Implementation of the Basic Worklist Management Service Class."""
    statuses = QR_FIND_SERVICE_CLASS_STATUS

    def __init__(self):
        super(BasicWorklistManagementServiceClass, self).__init__()

    def SCP(self, req, context, info):
        """The SCP implementation for Basic Worklist Management.

        Parameters
        ----------
        req : dimse_primitives.C_FIND
            The C-FIND request primitive received from the peer.
        context : presentation.PresentationContext
            The presentation context that the SCP is operating under.
        info : dict
            A dict containing details about the association.

        See Also
        --------
        ae.ApplicationEntity.on_c_find
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
          `9.3.2 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.2>`_ and
          `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_.
        """
        if context.abstract_syntax == '1.2.840.10008.5.1.4.31':
            self._find_scp(req, context, info)
        else:
            raise ValueError(
                'The supplied abstract syntax is not valid for use with the '
                'Basic Worklist Management Service Class'
            )


class RelevantPatientInformationQueryServiceClass(ServiceClass):
    """Implementation of the Relevant Patient Information Query"""
    statuses = RELEVANT_PATIENT_SERVICE_CLASS_STATUS

    def SCP(self, req, context, info):
        """The SCP implementation for the Relevant Patient Information Query
        Service Class.

        Parameters
        ----------
        req : dimse_primitives.C_FIND
            The C-FIND request primitive sent by the peer.
        context : presentation.PresentationContext
            The presentation context that the SCP is operating under.
        info : dict
            A dict containing details about the association.

        See Also
        --------
        ae.ApplicationEntity.on_c_find
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
           `9.3.2 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.2>`_ and
           `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_.
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
            self.DIMSE.send_msg(rsp, context.context_id)
            return

        info['parameters'] = {
             'message_id' : req.MessageID,
             'priority' : req.Priority
        }

        # Relevant Patient Query only allows the following responses:
        #   pending + match; success
        #   cancel or failure
        #   success (no match)
        # In other words there can only be 1 or 2 responses
        try:
            # If we get a valid yield then send the corresponding message
            #   if the yield is pending, send message then success and return
            #   if the yield is cancel or failure, send message and return
            #   if StopIteration send success and return
            responses = self.AE.on_c_find(identifier, context.as_tuple, info)
            (rsp_status, rsp_identifier) = next(responses)
        except StopIteration:
            # There were no matches, so return Success
            # If success, then rsp_identifier is None
            rsp.Status = 0x0000
            LOGGER.info('Find SCP Response: (Success)')
            self.DIMSE.send_msg(rsp, context.context_id)
            return
        except Exception as ex:
            LOGGER.error("Exception in user's on_c_find implementation.")
            LOGGER.exception(ex)
            rsp.Status = 0xC311
            self.DIMSE.send_msg(rsp, context.context_id)
            return

        rsp = self.validate_status(rsp_status, rsp)

        if rsp.Status in self.statuses:
            status = self.statuses[rsp.Status]
        else:
            # Unknown status
            self.DIMSE.send_msg(rsp, context.context_id)
            return

        if status[0] == STATUS_CANCEL:
            # If cancel, then rsp_identifier is None
            LOGGER.info('Received C-CANCEL-FIND RQ from peer')
            LOGGER.info('Find SCP Response: (Cancel)')
            self.DIMSE.send_msg(rsp, context.context_id)
            return
        elif status[0] == STATUS_FAILURE:
            # If failed, then rsp_identifier is None
            LOGGER.info('Find SCP Response: (Failure)')
            self.DIMSE.send_msg(rsp, context.context_id)
            return
        elif status[0] == STATUS_SUCCESS:
            # User isn't supposed to send these, but handle anyway
            # If success, then rsp_identifier is None
            LOGGER.info('Find SCP Response: (Success)')
            self.DIMSE.send_msg(rsp, context.context_id)
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
                #   returned by on_c_find callback
                rsp.Status = 0xC312
                self.DIMSE.send_msg(rsp, context.context_id)
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
            self.DIMSE.send_msg(rsp, context.context_id)

            # Send final success response
            rsp.Status = 0x0000
            LOGGER.info('Find SCP Response: (Success)')
            self.DIMSE.send_msg(rsp, context.context_id)


class SubstanceAdministrationQueryServiceClass(QueryRetrieveServiceClass):
    """Implementation of the Substance Administration Query Service"""
    statuses = SUBSTANCE_ADMINISTRATION_SERVICE_CLASS_STATUS

    def __init__(self):
        super(SubstanceAdministrationQueryServiceClass, self).__init__()

    def SCP(self, req, context, info):
        """The SCP implementation for the Relevant Patient Information Query
        Service Class.

        Parameters
        ----------
        req : dimse_primitives.C_FIND
            The C-FIND request primitive sent by the peer.
        context : presentation.PresentationContext
            The presentation context that the SCP is operating under.
        info : dict
            A dict containing details about the association.

        See Also
        --------
        ae.ApplicationEntity.on_c_find
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
           `9.3.2 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.2>`_ and
           `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_.
        """
        self._find_scp(req, context, info)


class NonPatientObjectStorageServiceClass(StorageServiceClass):
    """Implementation of the Non-Patient Object Storage Service"""
    statuses = NON_PATIENT_SERVICE_CLASS_STATUS


class HangingProtocolQueryRetrieveServiceClass(QueryRetrieveServiceClass):
    """Implementation of the Hanging Protocol QR Service."""
    pass


class DefinedProcedureProtocolQueryRetrieveServiceClass(QueryRetrieveServiceClass):
    """Implementation of the Defined Procedure Protocol QR Service."""
    pass


class ColorPaletteQueryRetrieveServiceClass(QueryRetrieveServiceClass):
    """Implementation of the Color Palette QR Service."""
    pass


class ImplantTemplateQueryRetrieveServiceClass(QueryRetrieveServiceClass):
    """Implementation of the Implant Template QR Service."""
    pass
