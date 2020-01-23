"""
Define the DIMSE-C and DIMSE-N service parameter primitives.

Notes:
  * The class member names must match their corresponding DICOM element keyword
    in order for the DIMSE messages/primitives to be created correctly.
"""

import codecs
try:
    from collections.abc import MutableSequence
except ImportError:
    from collections import MutableSequence
from io import BytesIO
import logging

from pydicom.tag import Tag
from pydicom.uid import UID

from pynetdicom import _config
from pynetdicom.utils import validate_ae_title, validate_uid


LOGGER = logging.getLogger('pynetdicom.dimse_primitives')


# pylint: disable=invalid-name
# pylint: disable=attribute-defined-outside-init
# pylint: disable=too-many-instance-attributes
# pylint: disable=anomalous-backslash-in-string
class DIMSEPrimitive(object):
    """Base class for the DIMSE primitives."""
    STATUS_OPTIONAL_KEYWORDS = ()
    REQUEST_KEYWORDS = ()
    RESPONSE_KEYWORDS = ('MessageIDBeingRespondedTo', 'Status')

    @property
    def AffectedSOPClassUID(self):
        """Return the *Affected SOP Class UID* as :class:`~pydicom.uid.UID`."""
        return self._affected_sop_class_uid

    @AffectedSOPClassUID.setter
    def AffectedSOPClassUID(self, value):
        """Set the *Affected SOP Class UID*.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The value to use for the *Affected SOP Class UID* parameter.
        """
        if isinstance(value, UID):
            pass
        elif isinstance(value, str):
            value = UID(value)
        elif isinstance(value, bytes):
            value = UID(value.decode('ascii'))
        elif value is None:
            pass
        else:
            raise TypeError("Affected SOP Class UID must be a "
                            "pydicom.uid.UID, str or bytes")

        if value and not validate_uid(value):
            LOGGER.error("Affected SOP Class UID is an invalid UID")
            raise ValueError("Affected SOP Class UID is an invalid UID")

        if value and not value.is_valid:
            LOGGER.warning(
                "The Affected SOP Class UID '{}' is non-conformant"
                .format(value)
            )

        if value:
            self._affected_sop_class_uid = value
        else:
            self._affected_sop_class_uid = None

    @property
    def _AffectedSOPInstanceUID(self):
        """Return the *Affected SOP Instance UID* as :class:`~pydicom.uid.UID`.
        """
        return self._affected_sop_instance_uid

    @_AffectedSOPInstanceUID.setter
    def _AffectedSOPInstanceUID(self, value):
        """Set the *Affected SOP Instance UID*.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The value for the Affected SOP Class UID
        """
        if isinstance(value, UID):
            pass
        elif isinstance(value, str):
            value = UID(value)
        elif isinstance(value, bytes):
            value = UID(value.decode('ascii'))
        elif value is None:
            pass
        else:
            raise TypeError("Affected SOP Instance UID must be a "
                            "pydicom.uid.UID, str or bytes")

        if value and not validate_uid(value):
            LOGGER.error("Affected SOP Instance UID is an invalid UID")
            raise ValueError("Affected SOP Instance UID is an invalid UID")

        if value and not value.is_valid:
            LOGGER.warning(
                "The Affected SOP Instance UID '{}' is non-conformant"
                .format(value)
            )

        if value:
            self._affected_sop_instance_uid = value
        else:
            self._affected_sop_instance_uid = None

    @property
    def _dataset_variant(self):
        """Return the Dataset-like parameter value.

        Used for EventInformation, EventReply, AttributeList,
        ActionInformation, ActionReply, DataSet, Identifier and
        ModificationList dataset-like parameter values.

        Returns
        -------
        BytesIO or None
        """
        return self._dataset

    @_dataset_variant.setter
    def _dataset_variant(self, value):
        """Set the Dataset-like parameter.

        Used for EventInformation, EventReply, AttributeList,
        ActionInformation, ActionReply, DataSet, Identifier and
        ModificationList dataset-like parameter values.

        Parameters
        ----------
        value : tuple
            The (dataset, variant name) to set, where dataset is either None
            or BytesIO and variant name is str.
        """
        if value[0] is None:
            self._dataset = value[0]
        elif isinstance(value[0], BytesIO):
            self._dataset = value[0]
        else:
            raise TypeError(
                "'{}' parameter must be a BytesIO object".format(value[1])
            )

    @property
    def is_valid_request(self):
        """Return ``True`` if the request is valid, ``False`` otherwise."""
        for keyword in self.REQUEST_KEYWORDS:
            if getattr(self, keyword) is None:
                return False

        return True

    @property
    def is_valid_response(self):
        """Return ``True`` if the response is valid, ``False`` otherwise."""
        for keyword in self.RESPONSE_KEYWORDS:
            if getattr(self, keyword) is None:
                return False

        return True

    @property
    def MessageID(self):
        """Return the *Message ID* value as :class:`int`."""
        return self._message_id

    @MessageID.setter
    def MessageID(self, value):
        """Set the *Message ID*.

        Parameters
        ----------
        int
            The value to use for the *Message ID* parameter.
        """
        if isinstance(value, int):
            if 0 <= value < 2**16:
                self._message_id = value
            else:
                raise ValueError("Message ID must be between 0 and 65535, "
                                 "inclusive")
        elif value is None:
            self._message_id = value
        else:
            raise TypeError("Message ID must be an int")

    @property
    def MessageIDBeingRespondedTo(self):
        """Return the *Message ID Being Responded To* as :class:`int`."""
        return self._message_id_being_responded_to

    @MessageIDBeingRespondedTo.setter
    def MessageIDBeingRespondedTo(self, value):
        """Set the *Message ID Being Responded To*.

        Parameters
        ----------
        int
            The value to use for the *Message ID Being Responded To* parameter.
        """
        if isinstance(value, int):
            if 0 <= value < 2**16:
                self._message_id_being_responded_to = value
            else:
                raise ValueError("Message ID Being Responded To must be "
                                 "between 0 and 65535, inclusive")
        elif value is None:
            self._message_id_being_responded_to = value
        else:
            raise TypeError("Message ID Being Responded To must be an int")

    @property
    def _NumberOfCompletedSuboperations(self):
        """Return the *Number of Completed Suboperations*."""
        return self._number_of_completed_suboperations

    @_NumberOfCompletedSuboperations.setter
    def _NumberOfCompletedSuboperations(self, value):
        """Set the *Number of Completed Suboperations*."""
        if isinstance(value, int):
            if value >= 0:
                self._number_of_completed_suboperations = value
            else:
                raise ValueError("Number of Completed Suboperations must be "
                                 "greater than or equal to 0")
        elif value is None:
            self._number_of_completed_suboperations = value
        else:
            raise TypeError("Number of Completed Suboperations must be an int")

    @property
    def _NumberOfFailedSuboperations(self):
        """Return the *Number of Failed Suboperations*."""
        return self._number_of_failed_suboperations

    @_NumberOfFailedSuboperations.setter
    def _NumberOfFailedSuboperations(self, value):
        """Set the *Number of Failed Suboperations*."""
        if isinstance(value, int):
            if value >= 0:
                self._number_of_failed_suboperations = value
            else:
                raise ValueError("Number of Failed Suboperations must be "
                                 "greater than or equal to 0")
        elif value is None:
            self._number_of_failed_suboperations = value
        else:
            raise TypeError("Number of Failed Suboperations must be an int")

    @property
    def _NumberOfRemainingSuboperations(self):
        """Return the *Number of Remaining Suboperations*."""
        return self._number_of_remaining_suboperations

    @_NumberOfRemainingSuboperations.setter
    def _NumberOfRemainingSuboperations(self, value):
        """Set the *Number of Remaining Suboperations*."""
        if isinstance(value, int):
            if value >= 0:
                self._number_of_remaining_suboperations = value
            else:
                raise ValueError("Number of Remaining Suboperations must be "
                                 "greater than or equal to 0")
        elif value is None:
            self._number_of_remaining_suboperations = value
        else:
            raise TypeError("Number of Remaining Suboperations must be an int")

    @property
    def _NumberOfWarningSuboperations(self):
        """Return the *Number of Warning Suboperations*."""
        return self._number_of_warning_suboperations

    @_NumberOfWarningSuboperations.setter
    def _NumberOfWarningSuboperations(self, value):
        """Set the *Number of Warning Suboperations*."""
        if isinstance(value, int):
            if value >= 0:
                self._number_of_warning_suboperations = value
            else:
                raise ValueError("Number of Warning Suboperations must be "
                                 "greater than or equal to 0")
        elif value is None:
            self._number_of_warning_suboperations = value
        else:
            raise TypeError("Number of Warning Suboperations must be an int")

    @property
    def _Priority(self):
        """Return the *Priority*."""
        return self._priority

    @_Priority.setter
    def _Priority(self, value):
        """Set the *Priority*."""
        if value in [0, 1, 2]:
            self._priority = value
        else:
            LOGGER.warning("Attempted to set Priority parameter to "
                           "an invalid value")
            raise ValueError("Priority must be 0, 1, or 2")

    @property
    def _RequestedSOPClassUID(self):
        """Return the *Requested SOP Class UID*."""
        return self._requested_sop_class_uid

    @_RequestedSOPClassUID.setter
    def _RequestedSOPClassUID(self, value):
        """Set the *Requested SOP Class UID*.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The value for the Requested SOP Class UID
        """
        if isinstance(value, UID):
            pass
        elif isinstance(value, str):
            value = UID(value)
        elif isinstance(value, bytes):
            value = UID(value.decode('ascii'))
        elif value is None:
            pass
        else:
            raise TypeError("Requested SOP Class UID must be a "
                            "pydicom.uid.UID, str or bytes")

        if value and not validate_uid(value):
            LOGGER.error("Requested SOP Class UID is an invalid UID")
            raise ValueError("Requested SOP Class UID is an invalid UID")

        if value and not value.is_valid:
            LOGGER.warning(
                "The Requested SOP Class UID '{}' is non-conformant"
                .format(value)
            )

        if value:
            self._requested_sop_class_uid = value
        else:
            self._requested_sop_class_uid = None

    @property
    def _RequestedSOPInstanceUID(self):
        """Return the *Requested SOP Instance UID*."""
        return self._requested_sop_instance_uid

    @_RequestedSOPInstanceUID.setter
    def _RequestedSOPInstanceUID(self, value):
        """Set the *Requested SOP Instance UID*.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The value for the Requested SOP Instance UID
        """
        if isinstance(value, UID):
            pass
        elif isinstance(value, str):
            value = UID(value)
        elif isinstance(value, bytes):
            value = UID(value.decode('ascii'))
        elif value is None:
            pass
        else:
            raise TypeError("Requested SOP Instance UID must be a "
                            "pydicom.uid.UID, str or bytes")

        if value and not validate_uid(value):
            LOGGER.error("Requested SOP Instance UID is an invalid UID")
            raise ValueError("Requested SOP Instance UID is an invalid UID")

        if value and not value.is_valid:
            LOGGER.warning(
                "The Requested SOP Instance UID '{}' is non-conformant"
                .format(value)
            )

        if value:
            self._requested_sop_instance_uid = value
        else:
            self._requested_sop_instance_uid = None

    @property
    def Status(self):
        """Return the *Status* as :class:`int`."""
        return self._status

    @Status.setter
    def Status(self, value):
        """Set the *Status*

        Parameters
        ----------
        int
            The value to use for the *Status* parameter.
        """
        if isinstance(value, int) or value is None:
            self._status = value
        else:
            raise TypeError("DIMSE primitive's 'Status' must be an int")

    @property
    def msg_type(self):
        """Return the DIMSE message type as :class:`str`."""
        return self.__class__.__name__.replace('_', '-')


# DIMSE-C Service Primitives
class C_STORE(DIMSEPrimitive):
    r"""Represents a C-STORE primitive.

    +------------------------------------------+---------+----------+
    | Parameter                                | Req/ind | Rsp/conf |
    +==========================================+=========+==========+
    | Message ID                               | M       | U        |
    +------------------------------------------+---------+----------+
    | Message ID Being Responded To            | \-      | M        |
    +------------------------------------------+---------+----------+
    | Affected SOP Class UID                   | M       | U(=)     |
    +------------------------------------------+---------+----------+
    | Affected SOP Instance UID                | M       | U(=)     |
    +------------------------------------------+---------+----------+
    | Priority                                 | M       | \-       |
    +------------------------------------------+---------+----------+
    | Move Originator Application Entity Title | U       | \-       |
    +------------------------------------------+---------+----------+
    | Move Originator Message ID               | U       | \-       |
    +------------------------------------------+---------+----------+
    | Data Set                                 | M       | \-       |
    +------------------------------------------+---------+----------+
    | Status                                   | \-      | M        |
    +------------------------------------------+---------+----------+
    | Offending Element                        | \-      | C        |
    +------------------------------------------+---------+----------+
    | Error Comment                            | \-      | C        |
    +------------------------------------------+---------+----------+

    | (=) - The value of the parameter is equal to the value of the parameter
      in the column to the left
    | C - The parameter is conditional.
    | M - Mandatory
    | MF - Mandatory with a fixed value
    | U - The use of this parameter is a DIMSE service user option
    | UF - User option with a fixed value

    Attributes
    ----------
    MessageID : int
        Identifies the operation and is used to distinguish this
        operation from other notifications or operations that may be in
        progress. No two identical values for the Message ID shall be used for
        outstanding operations.
    MessageIDBeingRespondedTo : int
        The Message ID of the operation request/indication to which this
        response/confirmation applies.
    AffectedSOPClassUID : pydicom.uid.UID, bytes or str
        For the request/indication this specifies the SOP Class for
        storage. If included in the response/confirmation, it shall be equal
        to the value in the request/indication
    AffectedSOPInstanceUID : pydicom.uid.UID, bytes or str
        For the request/indication this specifies the SOP Instance
        for storage. If included in the response/confirmation, it shall be
        equal to the value in the request/indication
    Priority : int
        The priority of the C-STORE operation. It shall be one of the
        following:

        * 0: Medium
        * 1: High
        * 2: Low (Default)
    MoveOriginatorApplicationEntityTitle : bytes
        The DICOM AE Title of the AE that invoked the C-MOVE operation
        from which this C-STORE sub-operation is being performed
    MoveOriginatorMessageID : int
        The Message ID of the C-MOVE request/indication primitive from
        which this C-STORE sub-operation is being performed
    DataSet : io.BytesIO
        A DICOM dataset containing the attributes of the Composite
        SOP Instance to be stored.
    Status : int
        The error or success notification of the operation.
    OffendingElement : list of int or None
        An optional status related field containing a list of the
        elements in which an error was detected.
    ErrorComment : str or None
        An optional status related field containing a text description
        of the error detected. 64 characters maximum.
    """
    STATUS_OPTIONAL_KEYWORDS = ('OffendingElement', 'ErrorComment', )
    REQUEST_KEYWORDS = (
        'MessageID', 'AffectedSOPClassUID', 'AffectedSOPInstanceUID',
        'Priority', 'DataSet'
    )

    def __init__(self):
        # Variable names need to match the corresponding DICOM Element keywords
        #   in order for the DIMSE Message classes to be built correctly.
        # Changes to the variable names can be made provided the DIMSEMessage()
        #   class' message_to_primitive() and primitive_to_message() methods
        #   are also changed
        self.MessageID = None
        self.MessageIDBeingRespondedTo = None
        self.AffectedSOPClassUID = None
        self.AffectedSOPInstanceUID = None
        self.Priority = 0x02
        self.MoveOriginatorApplicationEntityTitle = None
        self.MoveOriginatorMessageID = None
        self.DataSet = None
        self.Status = None

        # Optional Command Set elements used with specific Status values
        # For Warning statuses 0xB000, 0xB006, 0xB007
        # For Failure statuses 0xCxxx, 0xA9xx,
        self.OffendingElement = None
        # For Warning statuses 0xB000, 0xB006, 0xB007
        # For Failure statuses 0xCxxx, 0xA9xx, 0xA7xx, 0x0122, 0x0124
        self.ErrorComment = None
        # For Failure statuses 0x0117
        # self.AffectedSOPInstanceUID

    @property
    def AffectedSOPInstanceUID(self):
        """Return the *Affected SOP Instance UID* as :class:`~pydicom.uid.UID`.
        """
        return self._AffectedSOPInstanceUID

    @AffectedSOPInstanceUID.setter
    def AffectedSOPInstanceUID(self, value):
        """Set the *Affected SOP Instance UID*.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The value to use for the *Affected SOP Class UID* parameter.
        """
        self._AffectedSOPInstanceUID = value

    @property
    def DataSet(self):
        """Return the *Data Set* as :class:`io.BytesIO`."""
        return self._dataset_variant

    @DataSet.setter
    def DataSet(self, value):
        """Set the *Data Set*.

        Parameters
        ----------
        io.BytesIO
            The value to use for the *Data Set* parameter.
        """
        self._dataset_variant = (value, 'DataSet')

    @property
    def MoveOriginatorApplicationEntityTitle(self):
        """Return the *Move Originator Application Entity Title* as
        :class:`bytes`.
        """
        return self._move_originator_application_entity_title

    @MoveOriginatorApplicationEntityTitle.setter
    def MoveOriginatorApplicationEntityTitle(self, value):
        """Set the *Move Originator Application Entity Title*.

        Parameters
        ----------
        bytes or str
            The value to use for the *Move Originator AE Title* parameter.
            The parameter value will be truncated to 16 bytes and invalid
            values ignored.
        """
        if isinstance(value, str):
            value = codecs.encode(value, 'ascii')

        if value:
            try:
                self._move_originator_application_entity_title = (
                    validate_ae_title(value, _config.USE_SHORT_DIMSE_AET)
                )
            except ValueError:
                LOGGER.error(
                    "C-STORE request primitive contains an invalid "
                    "'Move Originator AE Title'"
                )
                self._move_originator_application_entity_title = None
        else:
            self._move_originator_application_entity_title = None

    @property
    def MoveOriginatorMessageID(self):
        """Return the *Move Originator Message ID* as :class:`int`."""
        return self._move_originator_message_id

    @MoveOriginatorMessageID.setter
    def MoveOriginatorMessageID(self, value):
        """Set the *Move Originator Message ID*.

        Parameters
        ----------
        int
            The value to use for the *Move Originator Message ID* parameter.
        """
        # Fix for peers sending a value consisting of nulls
        if isinstance(value, int):
            if 0 <= value < 2**16:
                self._move_originator_message_id = value
            else:
                raise ValueError("Move Originator Message ID To must be "
                                 "between 0 and 65535, inclusive")
        elif value is None:
            self._move_originator_message_id = value
        else:
            raise TypeError("Move Originator Message ID To must be an int")

    @property
    def Priority(self):
        """Return the *Priority* as :class:`int`."""
        return self._Priority

    @Priority.setter
    def Priority(self, value):
        """Set the *Priority*.

        Parameters
        ----------
        int
            The value to use for the *Priority* parameter.
        """
        self._Priority = value


class C_FIND(DIMSEPrimitive):
    r"""Represents a C-FIND primitive.

    +-------------------------------+---------+----------+
    | Parameter                     | Req/ind | Rsp/conf |
    +===============================+=========+==========+
    | Message ID                    | M       | U        |
    +-------------------------------+---------+----------+
    | Message ID Being Responded To | \-      | M        |
    +-------------------------------+---------+----------+
    | Affected SOP Class UID        | M       | U(=)     |
    +-------------------------------+---------+----------+
    | Priority                      | M       | \-       |
    +-------------------------------+---------+----------+
    | Identifier                    | M       | C        |
    +-------------------------------+---------+----------+
    | Status                        | \-      | M        |
    +-------------------------------+---------+----------+
    | Offending Element             | \-      | C        |
    +-------------------------------+---------+----------+
    | Error Comment                 | \-      | C        |
    +-------------------------------+---------+----------+

    | (=) - The value of the parameter is equal to the value of the parameter
      in the column to the left
    | C - The parameter is conditional.
    | M - Mandatory
    | MF - Mandatory with a fixed value
    | U - The use of this parameter is a DIMSE service user option
    | UF - User option with a fixed value

    Attributes
    ----------
    MessageID : int
        Identifies the operation and is used to distinguish this
        operation from other notifications or operations that may be in
        progress. No two identical values for the Message ID shall be used for
        outstanding operations.
    MessageIDBeingRespondedTo : int
        The Message ID of the operation request/indication to which
        this response/confirmation applies.
    AffectedSOPClassUID : pydicom.uid.UID, bytes or str
        For the request/indication this specifies the SOP Class
        for storage. If included in the response/confirmation, it shall be
        equal to the value in the request/indication
    Priority : int
        The priority of the C-STORE operation. It shall be one of the
        following:

        * 0: Medium
        * 1: High
        * 2: Low (Default)
    Identifier : io.BytesIO
        A DICOM dataset of attributes to be matched against the values of the
        attributes in the instances of the composite objects known to the
        performing DIMSE service-user.
    Status : int
        The error or success notification of the operation.
    OffendingElement : list of int or None
        An optional status related field containing a list of the
        elements in which an error was detected.
    ErrorComment : str or None
        An optional status related field containing a text
        description of the error detected. 64 characters maximum.
    """
    STATUS_OPTIONAL_KEYWORDS = ('OffendingElement', 'ErrorComment', )
    REQUEST_KEYWORDS = (
        'MessageID', 'AffectedSOPClassUID', 'Priority', 'Identifier'
    )

    def __init__(self):
        # Variable names need to match the corresponding DICOM Element keywords
        #   in order for the DIMSE Message classes to be built correctly.
        # Changes to the variable names can be made provided the DIMSEMessage()
        #   class' message_to_primitive() and primitive_to_message() methods
        #   are also changed
        self.MessageID = None
        self.MessageIDBeingRespondedTo = None
        self.AffectedSOPClassUID = None
        self.Priority = 0x02
        self.Identifier = None
        self.Status = None

        # Optional Command Set elements used in with specific Status values
        # For Failure statuses 0xA900, 0xCxxx
        self.OffendingElement = None
        # For Failure statuses 0xA900, 0xA700, 0x0122, 0xCxxx
        self.ErrorComment = None

    @property
    def Identifier(self):
        """Return the *Identifier* as :class:`io.BytesIO`."""
        return self._dataset_variant

    @Identifier.setter
    def Identifier(self, value):
        """Set the *Identifier*.

        Parameters
        ----------
        io.BytesIO
            The value to use for the *Identifier* parameter.
        """
        self._dataset_variant = (value, 'Identifier')

    @property
    def Priority(self):
        """Return the *Priority* as :class:`int`."""
        return self._Priority

    @Priority.setter
    def Priority(self, value):
        """Set the *Priority*.

        Parameters
        ----------
        int
            The value to use for the *Priority* parameter.
        """
        self._Priority = value


class C_GET(DIMSEPrimitive):
    r"""Represents a C-GET primitive.

    +-------------------------------+---------+----------+
    | Parameter                     | Req/ind | Rsp/conf |
    +===============================+=========+==========+
    | Message ID                    | M       | U        |
    +-------------------------------+---------+----------+
    | Message ID Being Responded To | \-      | M        |
    +-------------------------------+---------+----------+
    | Affected SOP Class UID        | M       | U(=)     |
    +-------------------------------+---------+----------+
    | Priority                      | M       | \-       |
    +-------------------------------+---------+----------+
    | Identifier                    | M       | U        |
    +-------------------------------+---------+----------+
    | Status                        | \-      | M        |
    +-------------------------------+---------+----------+
    | Number of Remaining Sub-ops   | \-      | C        |
    +-------------------------------+---------+----------+
    | Number of Completed Sub-ops   | \-      | C        |
    +-------------------------------+---------+----------+
    | Number of Failed Sub-ops      | \-      | C        |
    +-------------------------------+---------+----------+
    | Number of Warning Sub-ops     | \-      | C        |
    +-------------------------------+---------+----------+
    | Offending Element             | \-      | C        |
    +-------------------------------+---------+----------+
    | Error Comment                 | \-      | C        |
    +-------------------------------+---------+----------+

    | (=) - The value of the parameter is equal to the value of the parameter
      in the column to the left
    | C - The parameter is conditional.
    | M - Mandatory
    | MF - Mandatory with a fixed value
    | U - The use of this parameter is a DIMSE service user option
    | UF - User option with a fixed value

    Attributes
    ----------
    MessageID : int
        Identifies the operation and is used to distinguish this
        operation from other notifications or operations that may be in
        progress. No two identical values for the Message ID shall be used for
        outstanding operations.
    MessageIDBeingRespondedTo : int
        The Message ID of the operation request/indication to which
        this response/confirmation applies.
    AffectedSOPClassUID : pydicom.uid.UID, bytes or str
        For the request/indication this specifies the SOP Class
        for storage. If included in the response/confirmation, it shall be
        equal to the value in the request/indication
    Priority : int
        The priority of the C-STORE operation. It shall be one of the
        following:

        * 0: Medium
        * 1: High
        * 2: Low (Default)
    Identifier : io.BytesIO
        A DICOM dataset of attributes to be matched against the values of the
        attributes in the instances of the composite objects known to the
        performing DIMSE service-user.
    Status : int
        The error or success notification of the operation.
    NumberOfRemainingSuboperations : int
        The number of remaining C-STORE sub-operations to be invoked
        by this C-GET operation. It may be included in any response and shall
        be included if the status is Pending
    NumberOfCompletedSuboperations : int
        The number of C-STORE sub-operations that have completed
        successfully. It may be included in any response and shall be included
        if the status is Pending
    NumberOfFailedSuboperations : int
        The number of C-STORE sub-operations that have failed. It may
        be included in any response and shall be included if the status is
        Pending
    NumberOfWarningSuboperations : int
        The number of C-STORE operations that generated Warning
        responses. It may be included in any response and shall be included if
        the status is Pending
    OffendingElement : list of int or None
        An optional status related field containing a list of the
        elements in which an error was detected.
    ErrorComment : str or None
        An optional status related field containing a text
        description of the error detected. 64 characters maximum.
    """
    STATUS_OPTIONAL_KEYWORDS = (
        'ErrorComment', 'OffendingElement', 'NumberOfRemainingSuboperations',
        'NumberOfCompletedSuboperations', 'NumberOfFailedSuboperations',
        'NumberOfWarningSuboperations'
    )
    REQUEST_KEYWORDS = (
        'MessageID', 'AffectedSOPClassUID', 'Priority', 'Identifier'
    )

    def __init__(self):
        # Variable names need to match the corresponding DICOM Element keywords
        #   in order for the DIMSE Message classes to be built correctly.
        # Changes to the variable names can be made provided the DIMSEMessage()
        #   class' message_to_primitive() and primitive_to_message() methods
        #   are also changed
        self.MessageID = None
        self.MessageIDBeingRespondedTo = None
        self.AffectedSOPClassUID = None
        self.Priority = 0x02
        self.Identifier = None
        self.Status = None
        self.NumberOfRemainingSuboperations = None
        self.NumberOfCompletedSuboperations = None
        self.NumberOfFailedSuboperations = None
        self.NumberOfWarningSuboperations = None

        # For Failure statuses 0xA701, 0xA900
        self.ErrorComment = None
        self.OffendingElement = None
        # For 0xA702, 0xFE00, 0xB000, 0x0000
        # self.NumberOfRemainingSuboperations
        # self.NumberOfCompletedSuboperations
        # self.NumberOfFailedSuboperations
        # self.NumberOfWarningSuboperations

    @property
    def Identifier(self):
        """Return the *Identifier* as :class:`io.BytesIO`."""
        return self._dataset_variant

    @Identifier.setter
    def Identifier(self, value):
        """Set the *Identifier*.

        Parameters
        ----------
        io.BytesIO
            The value to use for the *Identifier* parameter.
        """
        self._dataset_variant = (value, 'Identifier')

    @property
    def NumberOfCompletedSuboperations(self):
        """Return the *Number of Completed Suboperations* as :class:`int`."""
        return self._NumberOfCompletedSuboperations

    @NumberOfCompletedSuboperations.setter
    def NumberOfCompletedSuboperations(self, value):
        """Set the *Number of Completed Suboperations*.

        Parameters
        ----------
        int
            The value to use for the *Number of Completed Suboperations*
            parameter.
        """
        self._NumberOfCompletedSuboperations = value

    @property
    def NumberOfFailedSuboperations(self):
        """Return the *Number of Failed Suboperations* as :class:`int`."""
        return self._NumberOfFailedSuboperations

    @NumberOfFailedSuboperations.setter
    def NumberOfFailedSuboperations(self, value):
        """Set the *Number of Failed Suboperations*.

        Parameters
        ----------
        int
            The value to use for the *Number of Failed Suboperations*
            parameter.
        """
        self._NumberOfFailedSuboperations = value

    @property
    def NumberOfRemainingSuboperations(self):
        """Return the *Number of Remaining Suboperations* as :class:`int`."""
        return self._NumberOfRemainingSuboperations

    @NumberOfRemainingSuboperations.setter
    def NumberOfRemainingSuboperations(self, value):
        """Set the *Number of Remaining Suboperations*.

        Parameters
        ----------
        int
            The value to use for the *Number of Remaining Suboperations*
            parameter.
        """
        self._NumberOfRemainingSuboperations = value

    @property
    def NumberOfWarningSuboperations(self):
        """Return the *Number of Warning Suboperations* as :class:`int`."""
        return self._NumberOfWarningSuboperations

    @NumberOfWarningSuboperations.setter
    def NumberOfWarningSuboperations(self, value):
        """Set the *Number of Warning Suboperations*.

        Parameters
        ----------
        int
            The value to use for the *Number of Warning Suboperations*
            parameter.
        """
        self._NumberOfWarningSuboperations = value

    @property
    def Priority(self):
        """Return the *Priority* as :class:`int`."""
        return self._Priority

    @Priority.setter
    def Priority(self, value):
        """Set the *Priority*.

        Parameters
        ----------
        int
            The value to use for the *Priority* parameter.
        """
        self._Priority = value


class C_MOVE(DIMSEPrimitive):
    r"""Represents a C-MOVE primitive.

    +-------------------------------+---------+----------+
    | Parameter                     | Req/ind | Rsp/conf |
    +===============================+=========+==========+
    | Message ID                    | M       | U        |
    +-------------------------------+---------+----------+
    | Message ID Being Responded To | \-      | M        |
    +-------------------------------+---------+----------+
    | Affected SOP Class UID        | M       | U(=)     |
    +-------------------------------+---------+----------+
    | Priority                      | M       | \-       |
    +-------------------------------+---------+----------+
    | Move Destination              | M       | \-       |
    +-------------------------------+---------+----------+
    | Identifier                    | M       | U        |
    +-------------------------------+---------+----------+
    | Status                        | \-      | M        |
    +-------------------------------+---------+----------+
    | Number of Remaining Sub-ops   | \-      | C        |
    +-------------------------------+---------+----------+
    | Number of Completed Sub-ops   | \-      | C        |
    +-------------------------------+---------+----------+
    | Number of Failed Sub-ops      | \-      | C        |
    +-------------------------------+---------+----------+
    | Number of Warning Sub-ops     | \-      | C        |
    +-------------------------------+---------+----------+
    | Offending Element             | \-      | C        |
    +-------------------------------+---------+----------+
    | Error Comment                 | \-      | C        |
    +-------------------------------+---------+----------+

    | (=) - The value of the parameter is equal to the value of the parameter
      in the column to the left
    | C - The parameter is conditional.
    | M - Mandatory
    | MF - Mandatory with a fixed value
    | U - The use of this parameter is a DIMSE service user option
    | UF - User option with a fixed value

    Attributes
    ----------
    MessageID : int
        Identifies the operation and is used to distinguish this
        operation from other notifications or operations that may be in
        progress. No two identical values for the Message ID shall be used for
        outstanding operations.
    MessageIDBeingRespondedTo : int
        The Message ID of the operation request/indication to which
        this response/confirmation applies.
    AffectedSOPClassUID : pydicom.uid.UID, bytes or str
        For the request/indication this specifies the SOP Class
        for storage. If included in the response/confirmation, it shall be
        equal to the value in the request/indication
    Priority : int
        The priority of the C-STORE operation. It shall be one of the
        following:

        * 0: Medium
        * 1: High
        * 2: Low (Default)
    MoveDestination : bytes or str
        Specifies the DICOM AE Title of the destination DICOM AE to
        which the C-STORE sub-operations are being performed.
    Identifier : io.BytesIO
        A DICOM dataset of attributes to be matched against the values of the
        attributes in the instances of the composite objects known to the
        performing DIMSE service-user.
    Status : int
        The error or success notification of the operation.
    NumberOfRemainingSuboperations : int
        The number of remaining C-STORE sub-operations to be invoked
        by this C-MOVE operation. It may be included in any response and shall
        be included if the status is Pending
    NumberOfCompletedSuboperations : int
        The number of C-STORE sub-operations that have completed
        successfully. It may be included in any response and shall be included
        if the status is Pending
    NumberOfFailedSuboperations : int
        The number of C-STORE sub-operations that have failed. It may
        be included in any response and shall be included if the status is
        Pending
    NumberOfWarningSuboperations : int
        The number of C-STORE operations that generated Warning
        responses. It may be included in any response and shall be included if
        the status is Pending
    OffendingElement : list of int or None
        An optional status related field containing a list of the
        elements in which an error was detected.
    ErrorComment : str or None
        An optional status related field containing a text
        description of the error detected. 64 characters maximum.
    """
    STATUS_OPTIONAL_KEYWORDS = (
        'ErrorComment', 'OffendingElement', 'NumberOfRemainingSuboperations',
        'NumberOfCompletedSuboperations', 'NumberOfFailedSuboperations',
        'NumberOfWarningSuboperations'
    )
    REQUEST_KEYWORDS = (
        'MessageID', 'AffectedSOPClassUID', 'Priority', 'Identifier',
        'MoveDestination'
    )

    def __init__(self):
        # Variable names need to match the corresponding DICOM Element keywords
        #   in order for the DIMSE Message classes to be built correctly.
        # Changes to the variable names can be made provided the DIMSEMessage()
        #   class' message_to_primitive() and primitive_to_message() methods
        #   are also changed
        self.MessageID = None
        self.MessageIDBeingRespondedTo = None
        self.AffectedSOPClassUID = None
        self.Priority = 0x02
        self.MoveDestination = None
        self.Identifier = None
        self.Status = None
        self.NumberOfRemainingSuboperations = None
        self.NumberOfCompletedSuboperations = None
        self.NumberOfFailedSuboperations = None
        self.NumberOfWarningSuboperations = None

        # Optional Command Set elements used in with specific Status values
        # For Failure statuses 0xA900
        self.OffendingElement = None
        # For Failure statuses 0xA801, 0xA701, 0xA702, 0x0122, 0xA900, 0xCxxx
        #   0x0124
        self.ErrorComment = None

    @property
    def Identifier(self):
        """Return the *Identifier* as :class:`io.BytesIO`."""
        return self._dataset_variant

    @Identifier.setter
    def Identifier(self, value):
        """Set the *Identifier*.

        Parameters
        ----------
        io.BytesIO
            The value to use for the *Identifier* parameter.
        """
        self._dataset_variant = (value, 'Identifier')

    @property
    def MoveDestination(self):
        """Return the *Move Destination* as bytes."""
        return self._move_destination

    @MoveDestination.setter
    def MoveDestination(self, value):
        """Set the *Move Destination*.

        Parameters
        ----------
        bytes or str
            The value to use for the *Move Destination* parameter. Cannot
            be an empty string and will be truncated to 16 characters long
        """
        if isinstance(value, str):
            value = codecs.encode(value, 'ascii')

        if value is not None:
            self._move_destination = validate_ae_title(
                value, _config.USE_SHORT_DIMSE_AET
            )
        else:
            self._move_destination = None

    @property
    def NumberOfCompletedSuboperations(self):
        """Return the *Number of Completed Suboperations* as :class:`int`."""
        return self._NumberOfCompletedSuboperations

    @NumberOfCompletedSuboperations.setter
    def NumberOfCompletedSuboperations(self, value):
        """Set the *Number of Completed Suboperations*.

        Parameters
        ----------
        int
            The value to use for the *Number of Completed Suboperations*
            parameter.
        """
        self._NumberOfCompletedSuboperations = value

    @property
    def NumberOfFailedSuboperations(self):
        """Return the *Number of Failed Suboperations* as :class:`int`."""
        return self._NumberOfFailedSuboperations

    @NumberOfFailedSuboperations.setter
    def NumberOfFailedSuboperations(self, value):
        """Set the *Number of Failed Suboperations*.

        Parameters
        ----------
        int
            The value to use for the *Number of Failed Suboperations*
            parameter.
        """
        self._NumberOfFailedSuboperations = value

    @property
    def NumberOfRemainingSuboperations(self):
        """Return the *Number of Remaining Suboperations* as :class:`int`."""
        return self._NumberOfRemainingSuboperations

    @NumberOfRemainingSuboperations.setter
    def NumberOfRemainingSuboperations(self, value):
        """Set the *Number of Remaining Suboperations*.

        Parameters
        ----------
        int
            The value to use for the *Number of Remaining Suboperations*
            parameter.
        """
        self._NumberOfRemainingSuboperations = value

    @property
    def NumberOfWarningSuboperations(self):
        """Return the *Number of Warning Suboperations* as :class:`int`."""
        return self._NumberOfWarningSuboperations

    @NumberOfWarningSuboperations.setter
    def NumberOfWarningSuboperations(self, value):
        """Set the *Number of Warning Suboperations*.

        Parameters
        ----------
        int
            The value to use for the *Number of Warning Suboperations*
            parameter.
        """
        self._NumberOfWarningSuboperations = value

    @property
    def Priority(self):
        """Return the *Priority* as :class:`int`."""
        return self._Priority

    @Priority.setter
    def Priority(self, value):
        """Set the *Priority*.

        Parameters
        ----------
        int
            The value to use for the *Priority* parameter.
        """
        self._Priority = value


class C_ECHO(DIMSEPrimitive):
    r"""Represents a C-ECHO primitive.

    +-------------------------------+---------+----------+
    | Parameter                     | Req/ind | Rsp/conf |
    +===============================+=========+==========+
    | Message ID                    | M       | U        |
    +-------------------------------+---------+----------+
    | Message ID Being Responded To | \-      | M        |
    +-------------------------------+---------+----------+
    | Affected SOP Class UID        | M       | U(=)     |
    +-------------------------------+---------+----------+
    | Status                        | \-      | M        |
    +-------------------------------+---------+----------+
    | Error Comment                 | \-      | C        |
    +-------------------------------+---------+----------+

    | (=) - The value of the parameter is equal to the value of the parameter
      in the column to the left
    | C - The parameter is conditional.
    | M - Mandatory
    | MF - Mandatory with a fixed value
    | U - The use of this parameter is a DIMSE service user option
    | UF - User option with a fixed value

    Attributes
    ----------
    MessageID : int or None
        Identifies the operation and is used to distinguish this
        operation from other notifications or operations that may be in
        progress. No two identical values for the Message ID shall be used for
        outstanding operations.
    MessageIDBeingRespondedTo : int or None
        The Message ID of the operation request/indication to which this
        response/confirmation applies.
    AffectedSOPClassUID : pydicom.uid.UID, bytes or str or None
        For the request/indication this specifies the SOP Class for
        storage. If included in the response/confirmation, it shall be equal
        to the value in the request/indication
    Status : int or None
        The error or success notification of the operation.
    ErrorComment : str or None
        An optional status related field containing a text description
        of the error detected. 64 characters maximum.
    """
    STATUS_OPTIONAL_KEYWORDS = ('ErrorComment', )
    REQUEST_KEYWORDS = ('MessageID', 'AffectedSOPClassUID')

    def __init__(self):
        # Variable names need to match the corresponding DICOM Element keywords
        #   in order for the DIMSE Message classes to be built correctly.
        # Changes to the variable names can be made provided the DIMSEMessage()
        #   class' message_to_primitive() and primitive_to_message() methods
        #   are also changed
        self.MessageID = None
        self.MessageIDBeingRespondedTo = None
        self.AffectedSOPClassUID = None
        self.Status = None

        # (Optional) for Failure status 0x0122
        self.ErrorComment = None


class C_CANCEL(object):
    """Represents a C-CANCEL primitive.

    +-------------------------------+---------+
    | Parameter                     | Req/ind |
    +===============================+=========+
    | Message ID Being Responded To | M       |
    +-------------------------------+---------+

    | (=) - The value of the parameter is equal to the value of the parameter
      in the column to the left
    | C - The parameter is conditional.
    | M - Mandatory
    | MF - Mandatory with a fixed value
    | U - The use of this parameter is a DIMSE service user option
    | UF - User option with a fixed value

    Attributes
    ----------
    MessageIDBeingRespondedTo : int
        The Message ID of the operation request/indication to which this
        response/confirmation applies.

    References
    ----------

    * DICOM Standard, Part 7, :dcm:`Section 9.3.2.3<part07/sect_9.3.2.3.html>`
    """
    def __init__(self):
        """Initialise the C_CANCEL"""
        # Variable names need to match the corresponding DICOM Element keywords
        #   in order for the DIMSE Message classes to be built correctly.
        # Changes to the variable names can be made provided the DIMSEMessage()
        #   class' message_to_primitive() and primitive_to_message() methods
        #   are also changed
        self.MessageIDBeingRespondedTo = None

    @property
    def MessageIDBeingRespondedTo(self):
        """Return the *Message ID Being Responded To* as an :class:`int`."""
        return self._message_id_being_responded_to

    @MessageIDBeingRespondedTo.setter
    def MessageIDBeingRespondedTo(self, value):
        """Set the *Message ID Being Responded To*.

        Parameters
        ----------
        int
            The value to use for the *Message ID Being Responded To* parameter.
        """
        if isinstance(value, int):
            if 0 <= value < 2**16:
                self._message_id_being_responded_to = value
            else:
                raise ValueError("Message ID Being Responded To must be "
                                 "between 0 and 65535, inclusive")
        elif value is None:
            self._message_id_being_responded_to = value
        else:
            raise TypeError("Message ID Being Responded To must be an int")


# DIMSE-N Service Primitives
class N_EVENT_REPORT(DIMSEPrimitive):
    r"""Represents a N-EVENT-REPORT primitive.

    +------------------------------------------+---------+----------+
    | Parameter                                | Req/ind | Rsp/conf |
    +==========================================+=========+==========+
    | Message ID                               | M       | \-       |
    +------------------------------------------+---------+----------+
    | Message ID Being Responded To            | \-      | M        |
    +------------------------------------------+---------+----------+
    | Affected SOP Class UID                   | M       | U(=)     |
    +------------------------------------------+---------+----------+
    | Affected SOP Instance UID                | M       | U(=)     |
    +------------------------------------------+---------+----------+
    | Event Type ID                            | M       | C(=)     |
    +------------------------------------------+---------+----------+
    | Event Information                        | U       | \-       |
    +------------------------------------------+---------+----------+
    | Event Reply                              | \-      | C        |
    +------------------------------------------+---------+----------+
    | Status                                   | \-      | M        |
    +------------------------------------------+---------+----------+

    | (=) - The value of the parameter is equal to the value of the parameter
      in the column to the left
    | C - The parameter is conditional.
    | M - Mandatory
    | MF - Mandatory with a fixed value
    | U - The use of this parameter is a DIMSE service user option
    | UF - User option with a fixed value

    Attributes
    ----------
    MessageID : int
        Identifies the operation and is used to distinguish this
        operation from other notifications or operations that may be in
        progress. No two identical values for the Message ID shall be used for
        outstanding operations.
    MessageIDBeingRespondedTo : int
        The Message ID of the operation request/indication to which this
        response/confirmation applies.
    AffectedSOPClassUID : pydicom.uid.UID, bytes or str
        For the request/indication this specifies the SOP Class for
        storage. If included in the response/confirmation, it shall be equal
        to the value in the request/indication
    AffectedSOPInstanceUID : pydicom.uid.UID, bytes or str
        For the request/indication this specifies the SOP Instance
        for storage. If included in the response/confirmation, it shall be
        equal to the value in the request/indication
    EventTypeID : int
        The type of event being reported, depends on the Service Class
        specification. Shall be included if Event Reply is included.
    EventInformation : io.BytesIO
        Contains information the invoking DIMSE user is able to supply about
        the event. An encoded DICOM dataset containing additional Service
        Class specific information related to the operation.
    EventReply : io.BytesIO
        Contains the optional reply to the event report. An encoded DICOM
        dataset containing additional Service Class specific information.
    Status : int
        The error or success notification of the operation.
    """
    # Optional status element keywords other than 'Status'
    STATUS_OPTIONAL_KEYWORDS = (
        'AffectedSOPClassUID', 'AffectedSOPInstanceUID', 'EventTypeID',
        'ErrorComment', 'ErrorID' # EventInformation
    )
    REQUEST_KEYWORDS = (
        'MessageID', 'AffectedSOPClassUID', 'EventTypeID',
        'AffectedSOPInstanceUID'
    )

    def __init__(self):
        self.MessageID = None
        self.MessageIDBeingRespondedTo = None
        self.AffectedSOPClassUID = None
        self.AffectedSOPInstanceUID = None
        self.EventTypeID = None
        self.EventInformation = None
        self.EventReply = None
        self.Status = None

        # Optional status elements
        self.ErrorComment = None
        self.ErrorID = None

    @property
    def AffectedSOPInstanceUID(self):
        """Return the *Affected SOP Instance UID* as :class:`~pydicom.uid.UID`.
        """
        return self._AffectedSOPInstanceUID

    @AffectedSOPInstanceUID.setter
    def AffectedSOPInstanceUID(self, value):
        """Set the *Affected SOP Instance UID*.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The value to use for the *Affected SOP Class UID* parameter.
        """
        self._AffectedSOPInstanceUID = value

    @property
    def EventInformation(self):
        """Return the *Event Information* as :class:`io.BytesIO`."""
        return self._dataset_variant

    @EventInformation.setter
    def EventInformation(self, value):
        """Set the *Event Information*.

        Parameters
        ----------
        io.BytesIO
            The value to use for the *Event Information* parameter.
        """
        self._dataset_variant = (value, 'EventInformation')

    @property
    def EventReply(self):
        """Return the *Event Reply* as :class:`io.BytesIO`."""
        return self._dataset_variant

    @EventReply.setter
    def EventReply(self, value):
        """Set the *Event Reply*.

        Parameters
        ----------
        io.BytesIO
            The value to use for the *Event Reply* parameter.
        """
        self._dataset_variant = (value, 'EventReply')

    @property
    def EventTypeID(self):
        """Return the *Event Type ID* as :class:`int`."""
        return self._event_type_id

    @EventTypeID.setter
    def EventTypeID(self, value):
        """Set the *Event Type ID*.

        Parameters
        ----------
        int
            The value to use for the *Event Type ID* parameter.
        """
        if isinstance(value, int) or value is None:
            self._event_type_id = value
        else:
            raise TypeError("'N_EVENT_REPORT.EventTypeID' must be an int.")


class N_GET(DIMSEPrimitive):
    r"""Represents an N-GET primitive.

    +------------------------------------------+---------+----------+
    | Parameter                                | Req/ind | Rsp/conf |
    +==========================================+=========+==========+
    | Message ID                               | M       | \-       |
    +------------------------------------------+---------+----------+
    | Message ID Being Responded To            | \-      | M        |
    +------------------------------------------+---------+----------+
    | Requested SOP Class UID                  | M       | \-       |
    +------------------------------------------+---------+----------+
    | Requested SOP Instance UID               | M       | \-       |
    +------------------------------------------+---------+----------+
    | Attribute Identifier List                | U       | \-       |
    +------------------------------------------+---------+----------+
    | Affected SOP Class UID                   | \-      | U        |
    +------------------------------------------+---------+----------+
    | Affected SOP Instance UID                | \-      | U        |
    +------------------------------------------+---------+----------+
    | Attribute List                           | \-      | C        |
    +------------------------------------------+---------+----------+
    | Status                                   | \-      | M        |
    +------------------------------------------+---------+----------+

    | (=) - The value of the parameter is equal to the value of the parameter
      in the column to the left
    | C - The parameter is conditional.
    | M - Mandatory
    | MF - Mandatory with a fixed value
    | U - The use of this parameter is a DIMSE service user option
    | UF - User option with a fixed value

    Attributes
    ----------
    MessageID : int
        Identifies the operation and is used to distinguish this
        operation from other notifications or operations that may be in
        progress. No two identical values for the Message ID shall be used for
        outstanding operations.
    MessageIDBeingRespondedTo : int
        The Message ID of the operation request/indication to which this
        response/confirmation applies.
    RequestedSOPClassUID : pydicom.uid.UID, bytes or str
        The UID of the SOP Class for which attribute values are to be
        retrieved.
    RequestedSOPInstanceUID : pydicom.uid.UID, bytes or str
        The SOP Instance for which attribute values are to be retrieved.
    AttributeIdentifierList : list of pydicom.tag.Tag
        A list of attribute tags to be sent to the peer.
    AffectedSOPClassUID : pydicom.uid.UID, bytes or str
        The SOP Class UID of the SOP Instance for which the attributes were
        retrieved.
    AffectedSOPInstanceUID : pydicom.uid.UID, bytes or str
        The SOP Instance UID of the SOP Instance for which the attributes were
        retrieved.
    AttributeList : pydicom.dataset.Dataset
        A DICOM dataset containing elements matching those supplied in
        Attribute Identifier List.
    Status : int
        The error or success notification of the operation.
    """
    STATUS_OPTIONAL_KEYWORDS = (
        'AttributeIdentifierList', 'ErrorComment', 'ErrorID',
    )
    REQUEST_KEYWORDS = (
        'MessageID', 'RequestedSOPClassUID', 'RequestedSOPInstanceUID'
    )

    def __init__(self):
        self.MessageID = None
        self.MessageIDBeingRespondedTo = None
        self.RequestedSOPClassUID = None
        self.RequestedSOPInstanceUID = None
        self.AttributeIdentifierList = None
        self.AffectedSOPClassUID = None
        self.AffectedSOPInstanceUID = None
        self.AttributeList = None
        self.Status = None

        # (Optional) elements for specific status values
        self.ErrorComment = None
        self.ErrorID = None

    @property
    def AffectedSOPInstanceUID(self):
        """Return the *Affected SOP Instance UID* as :class:`~pydicom.uid.UID`.
        """
        return self._AffectedSOPInstanceUID

    @AffectedSOPInstanceUID.setter
    def AffectedSOPInstanceUID(self, value):
        """Set the *Affected SOP Instance UID*.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The value to use for the *Affected SOP Class UID* parameter.
        """
        self._AffectedSOPInstanceUID = value

    @property
    def AttributeIdentifierList(self):
        """Return the *Attribute Identifier List* as a :class:`list` of
        :class:`~pydicom.tag.BaseTag`.

        """
        return self._attribute_identifier_list

    @AttributeIdentifierList.setter
    def AttributeIdentifierList(self, value):
        """Set the *Attribute Identifier List*.

        Parameters
        ----------
        list of pydicom.tag.BaseTag
            The value to use for the *Attribute Identifier List* parameter.
            A list of pydicom :class:`pydicom.tag.BaseTag` instances or any
            values acceptable for creating them.
        """
        if value is None:
            self._attribute_identifier_list = None
            return

        # Singleton tags get put in a list
        if not isinstance(value, (list, MutableSequence)):
            value = [value]

        # Empty list -> None
        if not value:
            self._attribute_identifier_list = None
            return

        try:
            # Convert each item in list to pydicom Tag
            self._attribute_identifier_list = [Tag(tag) for tag in value]
        except (TypeError, ValueError):
            raise ValueError(
                "Attribute Identifier List must be a list of pydicom Tags"
            )

    @property
    def AttributeList(self):
        """Return the *Attribute List* as :class:`io.BytesIO`."""
        return self._dataset_variant

    @AttributeList.setter
    def AttributeList(self, value):
        """Set the *Attribute List*.

        Parameters
        ----------
        io.BytesIO
            The value to use for the *Attribute List* parameter.
        """
        self._dataset_variant = (value, 'AttributeList')

    @property
    def RequestedSOPClassUID(self):
        """Return the *Requested SOP Class UID* as :class:`~pydicom.uid.UID`.
        """
        return self._RequestedSOPClassUID

    @RequestedSOPClassUID.setter
    def RequestedSOPClassUID(self, value):
        """Set the *Requested SOP Class UID*.

        Parameters
        ----------
        pydicom.uid.UID, bytes or str
            The value to use for the *Requested SOP Class UID* parameter.
        """
        self._RequestedSOPClassUID = value

    @property
    def RequestedSOPInstanceUID(self):
        """Return the *Requested SOP Instance UID* as
        :class:`~pydicom.uid.UID`.
        """
        return self._RequestedSOPInstanceUID

    @RequestedSOPInstanceUID.setter
    def RequestedSOPInstanceUID(self, value):
        """Set the *Requested SOP Instance UID*.

        Parameters
        ----------
        pydicom.uid.UID, bytes or str
            The value to use for the *Requested SOP Instance UID* parameter.
        """
        self._RequestedSOPInstanceUID = value


class N_SET(DIMSEPrimitive):
    r"""Represents a N-SET primitive.

    +------------------------------------------+---------+----------+
    | Parameter                                | Req/ind | Rsp/conf |
    +==========================================+=========+==========+
    | Message ID                               | M       | \-       |
    +------------------------------------------+---------+----------+
    | Message ID Being Responded To            | \-      | M        |
    +------------------------------------------+---------+----------+
    | Requested SOP Class UID                  | M       | \-       |
    +------------------------------------------+---------+----------+
    | Requested SOP Instance UID               | M       | \-       |
    +------------------------------------------+---------+----------+
    | Modification List                        | M       | \-       |
    +------------------------------------------+---------+----------+
    | Attribute List                           | \-      | U        |
    +------------------------------------------+---------+----------+
    | Affected SOP Class UID                   | \-      | U        |
    +------------------------------------------+---------+----------+
    | Affected SOP Instance UID                | \-      | U        |
    +------------------------------------------+---------+----------+
    | Status                                   | \-      | M        |
    +------------------------------------------+---------+----------+

    | (=) - The value of the parameter is equal to the value of the parameter
      in the column to the left
    | C - The parameter is conditional.
    | M - Mandatory
    | MF - Mandatory with a fixed value
    | U - The use of this parameter is a DIMSE service user option
    | UF - User option with a fixed value

    Attributes
    ----------
    MessageID : int
        Identifies the operation and is used to distinguish this
        operation from other notifications or operations that may be in
        progress. No two identical values for the Message ID shall be used for
        outstanding operations.
    MessageIDBeingRespondedTo : int
        The Message ID of the operation request/indication to which this
        response/confirmation applies.
    RequestedSOPClassUID : pydicom.uid.UID, bytes or str
        The UID of the SOP Class for which attribute values are to be
        modified.
    RequestedSOPInstanceUID : pydicom.uid.UID, bytes or str
        The SOP Instance for which attribute values are to be modified.
    ModificationList : io.BytesIO
        A DICOM dataset containing the attributes and values that are to be
        used to modify the SOP Instance.
    AttributeList : io.BytesIO
        A DICOM dataset containing the attributes and values that were used to
        modify the SOP Instance.
    AffectedSOPClassUID : pydicom.uid.UID, bytes or str
        The SOP Class UID of the modified SOP Instance.
    AffectedSOPInstanceUID : pydicom.uid.UID, bytes or str
        The SOP Instance UID of the modified SOP Instance.
    Status : int
        The error or success notification of the operation.
    """
    STATUS_OPTIONAL_KEYWORDS = (
        'ErrorComment', 'ErrorID', 'AttributeIdentifierList'
    )
    REQUEST_KEYWORDS = (
        'MessageID', 'RequestedSOPClassUID', 'RequestedSOPInstanceUID',
        'ModificationList'
    )

    def __init__(self):
        self.MessageID = None
        self.MessageIDBeingRespondedTo = None
        self.RequestedSOPClassUID = None
        self.RequestedSOPInstanceUID = None
        self.ModificationList = None
        self.AttributeList = None
        self.AffectedSOPClassUID = None
        self.AffectedSOPInstanceUID = None
        self.Status = None

        # Optional
        self.ErrorComment = None
        self.ErrorID = None
        self.AttributeIdentifierList = None

    @property
    def AffectedSOPInstanceUID(self):
        """Return the *Affected SOP Instance UID* as :class:`~pydicom.uid.UID`.
        """
        return self._AffectedSOPInstanceUID

    @AffectedSOPInstanceUID.setter
    def AffectedSOPInstanceUID(self, value):
        """Set the *Affected SOP Instance UID*.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The value to use for the *Affected SOP Class UID* parameter.
        """
        self._AffectedSOPInstanceUID = value

    @property
    def AttributeList(self):
        """Return the *Attribute List* as :class:`io.BytesIO`."""
        return self._dataset_variant

    @AttributeList.setter
    def AttributeList(self, value):
        """Set the *Attribute List*.

        Parameters
        ----------
        io.BytesIO
            The value to use for the *Attribute List* parameter.
        """
        self._dataset_variant = (value, 'AttributeList')

    @property
    def ModificationList(self):
        """Return the *Modification List* as :class:`io.BytesIO`."""
        return self._dataset_variant

    @ModificationList.setter
    def ModificationList(self, value):
        """Set the *Modification List*.

        Parameters
        ----------
        io.BytesIO
            The value to use for the *Modification List* parameter.
        """
        self._dataset_variant = (value, 'ModificationList')

    @property
    def RequestedSOPClassUID(self):
        """Return the *Requested SOP Class UID* as :class:`~pydicom.uid.UID`.
        """
        return self._RequestedSOPClassUID

    @RequestedSOPClassUID.setter
    def RequestedSOPClassUID(self, value):
        """Set the *Requested SOP Class UID*.

        Parameters
        ----------
        pydicom.uid.UID, bytes or str
            The value to use for the *Requested SOP Class UID* parameter.
        """
        self._RequestedSOPClassUID = value

    @property
    def RequestedSOPInstanceUID(self):
        """Return the *Requested SOP Instance UID* as
        :class:`~pydicom.uid.UID`.
        """
        return self._RequestedSOPInstanceUID

    @RequestedSOPInstanceUID.setter
    def RequestedSOPInstanceUID(self, value):
        """Set the *Requested SOP Instance UID*.

        Parameters
        ----------
        pydicom.uid.UID, bytes or str
            The value to use for the *Requested SOP Instance UID* parameter.
        """
        self._RequestedSOPInstanceUID = value


class N_ACTION(DIMSEPrimitive):
    r"""Represents a N-ACTION primitive.

    +------------------------------------------+---------+----------+
    | Parameter                                | Req/ind | Rsp/conf |
    +==========================================+=========+==========+
    | Message ID                               | M       | \-       |
    +------------------------------------------+---------+----------+
    | Message ID Being Responded To            | \-      | M        |
    +------------------------------------------+---------+----------+
    | Requested SOP Class UID                  | M       | \-       |
    +------------------------------------------+---------+----------+
    | Requested SOP Instance UID               | M       | \-       |
    +------------------------------------------+---------+----------+
    | Action Type ID                           | M       | C(=)     |
    +------------------------------------------+---------+----------+
    | Action Information                       | U       | \-       |
    +------------------------------------------+---------+----------+
    | Affected SOP Class UID                   | \-      | U        |
    +------------------------------------------+---------+----------+
    | Affected SOP Instance UID                | \-      | U        |
    +------------------------------------------+---------+----------+
    | Action Reply                             | \-      | C        |
    +------------------------------------------+---------+----------+
    | Status                                   | \-      | M        |
    +------------------------------------------+---------+----------+

    | (=) - The value of the parameter is equal to the value of the parameter
      in the column to the left
    | C - The parameter is conditional.
    | M - Mandatory
    | MF - Mandatory with a fixed value
    | U - The use of this parameter is a DIMSE service user option
    | UF - User option with a fixed value

    Attributes
    ----------
    MessageID : int
        Identifies the operation and is used to distinguish this
        operation from other notifications or operations that may be in
        progress. No two identical values for the Message ID shall be used for
        outstanding operations.
    MessageIDBeingRespondedTo : int
        The Message ID of the operation request/indication to which this
        response/confirmation applies.
    RequestedSOPClassUID : pydicom.uid.UID, bytes or str
        The SOP Class for which the action is to be performed.
    RequestedSOPInstanceUID : pydicom.uid.UID, bytes or str
        The SOP Instance for which the action is to be performed.
    ActionTypeID : int
        The type of action that is to be performed.
    ActionInformation : io.BytesIO
        Extra information required to perform the action.
    AffectedSOPClassUID : pydicom.uid.UID, bytes or str
        For the request/indication this specifies the SOP Class for
        storage. If included in the response/confirmation, it shall be equal
        to the value in the request/indication
    AffectedSOPInstanceUID : pydicom.uid.UID, bytes or str
        For the request/indication this specifies the SOP Instance for
        storage. If included in the response/confirmation, it shall be equal
        to the value in the request/indication
    ActionReply : io.BytesIO
        The reply to the action.
    Status : int
        The error or success notification of the operation.
    """
    STATUS_OPTIONAL_KEYWORDS = (
        'ErrorComment', 'ErrorID', 'AttributeIdentifierList'
    )
    REQUEST_KEYWORDS = (
        'MessageID', 'RequestedSOPClassUID', 'RequestedSOPInstanceUID',
        'ActionTypeID'
    )

    def __init__(self):
        self.MessageID = None
        self.MessageIDBeingRespondedTo = None
        self.RequestedSOPClassUID = None
        self.RequestedSOPInstanceUID = None
        self.ActionTypeID = None
        self.ActionInformation = None
        self.AffectedSOPClassUID = None
        self.AffectedSOPInstanceUID = None
        self.ActionReply = None
        self.Status = None

        # Optional status elements
        self.ErrorComment = None
        self.ErrorID = None

    @property
    def ActionInformation(self):
        """Return the *Action Information* as :class:`io.BytesIO`."""
        return self._dataset_variant

    @ActionInformation.setter
    def ActionInformation(self, value):
        """Set the *Action Information*.

        Parameters
        ----------
        io.BytesIO
            The value to use for the *Action Information* parameter.
        """
        self._dataset_variant = (value, 'ActionInformation')

    @property
    def ActionReply(self):
        """Return the *Action Reply* as :class:`io.BytesIO`."""
        return self._dataset_variant

    @ActionReply.setter
    def ActionReply(self, value):
        """Set the *Action Reply*.

        Parameters
        ----------
        io.BytesIO
            The value to use for the *Action Reply* parameter.
        """
        self._dataset_variant = (value, 'ActionReply')

    @property
    def ActionTypeID(self):
        """Return the *Action Type ID* as :class:`int`."""
        return self._action_type_id

    @ActionTypeID.setter
    def ActionTypeID(self, value):
        """Set the *Action Type ID*.

        Parameters
        ----------
        int
            The value to use for the *Action Type ID* parameter.
        """
        if isinstance(value, int) or value is None:
            self._action_type_id = value
        else:
            raise TypeError("'N_ACTION.ActionTypeID' must be an int.")

    @property
    def AffectedSOPInstanceUID(self):
        """Return the *Affected SOP Instance UID* as :class:`~pydicom.uid.UID`.
        """
        return self._AffectedSOPInstanceUID

    @AffectedSOPInstanceUID.setter
    def AffectedSOPInstanceUID(self, value):
        """Set the *Affected SOP Instance UID*.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The value to use for the *Affected SOP Class UID* parameter.
        """
        self._AffectedSOPInstanceUID = value

    @property
    def RequestedSOPClassUID(self):
        """Return the *Requested SOP Class UID* as :class:`~pydicom.uid.UID`.
        """
        return self._RequestedSOPClassUID

    @RequestedSOPClassUID.setter
    def RequestedSOPClassUID(self, value):
        """Set the *Requested SOP Class UID*.

        Parameters
        ----------
        pydicom.uid.UID, bytes or str
            The value to use for the *Requested SOP Class UID* parameter.
        """
        self._RequestedSOPClassUID = value

    @property
    def RequestedSOPInstanceUID(self):
        """Return the *Requested SOP Instance UID* as
        :class:`~pydicom.uid.UID`.
        """
        return self._RequestedSOPInstanceUID

    @RequestedSOPInstanceUID.setter
    def RequestedSOPInstanceUID(self, value):
        """Set the *Requested SOP Instance UID*.

        Parameters
        ----------
        pydicom.uid.UID, bytes or str
            The value to use for the *Requested SOP Instance UID* parameter.
        """
        self._RequestedSOPInstanceUID = value


class N_CREATE(DIMSEPrimitive):
    r"""Represents a N-CREATE primitive.

    +------------------------------------------+---------+----------+
    | Parameter                                | Req/ind | Rsp/conf |
    +==========================================+=========+==========+
    | Message ID                               | M       | \-       |
    +------------------------------------------+---------+----------+
    | Message ID Being Responded To            | \-      | M        |
    +------------------------------------------+---------+----------+
    | Affected SOP Class UID                   | M       | U(=)     |
    +------------------------------------------+---------+----------+
    | Affected SOP Instance UID                | U       | C        |
    +------------------------------------------+---------+----------+
    | Attribute List                           | U       | U        |
    +------------------------------------------+---------+----------+
    | Status                                   | \-      | M        |
    +------------------------------------------+---------+----------+

    | (=) - The value of the parameter is equal to the value of the parameter
      in the column to the left
    | C - The parameter is conditional.
    | M - Mandatory
    | MF - Mandatory with a fixed value
    | U - The use of this parameter is a DIMSE service user option
    | UF - User option with a fixed value

    Attributes
    ----------
    MessageID : int
        Identifies the operation and is used to distinguish this
        operation from other notifications or operations that may be in
        progress. No two identical values for the Message ID shall be used for
        outstanding operations.
    MessageIDBeingRespondedTo : int
        The Message ID of the operation request/indication to which this
        response/confirmation applies.
    AffectedSOPClassUID : pydicom.uid.UID, bytes or str
        For the request/indication this specifies the SOP Class for
        storage. If included in the response/confirmation, it shall be equal
        to the value in the request/indication
    AffectedSOPInstanceUID : pydicom.uid.UID, bytes or str
        For the request/indication this specifies the SOP Instance for
        storage. If included in the response/confirmation, it shall be equal
        to the value in the request/indication
    AttributeList : io.BytesIO
        A set of attributes and values that are to be assigned to the new
        SOP Instance.
    Status : int
        The error or success notification of the operation. It shall be
        one of the following values:
    """
    STATUS_OPTIONAL_KEYWORDS = ('ErrorComment', 'ErrorID', )
    REQUEST_KEYWORDS = ('MessageID', 'AffectedSOPClassUID')

    def __init__(self):
        self.MessageID = None
        self.MessageIDBeingRespondedTo = None
        self.AffectedSOPClassUID = None
        self.AffectedSOPInstanceUID = None
        self.AttributeList = None
        self.Status = None

        # Optional elements
        self.ErrorComment = None
        self.ErrorID = None

    @property
    def AffectedSOPInstanceUID(self):
        """Return the *Affected SOP Instance UID* as :class:`~pydicom.uid.UID`.
        """
        return self._AffectedSOPInstanceUID

    @AffectedSOPInstanceUID.setter
    def AffectedSOPInstanceUID(self, value):
        """Set the *Affected SOP Instance UID*.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The value to use for the *Affected SOP Class UID* parameter.
        """
        self._AffectedSOPInstanceUID = value

    @property
    def AttributeList(self):
        """Return the *Attribute List* as :class:`io.BytesIO`."""
        return self._dataset_variant

    @AttributeList.setter
    def AttributeList(self, value):
        """Set the *Attribute List*.

        Parameters
        ----------
        io.BytesIO
            The value to use for the *Attribute List* parameter.
        """
        self._dataset_variant = (value, 'AttributeList')


class N_DELETE(DIMSEPrimitive):
    r"""Represents a N-DELETE primitive.

    +------------------------------------------+---------+----------+
    | Parameter                                | Req/ind | Rsp/conf |
    +==========================================+=========+==========+
    | Message ID                               | M       | \-       |
    +------------------------------------------+---------+----------+
    | Message ID Being Responded To            | \-      | M        |
    +------------------------------------------+---------+----------+
    | Requested SOP Class UID                  | M       | \-       |
    +------------------------------------------+---------+----------+
    | Requested SOP Instance UID               | M       | \-       |
    +------------------------------------------+---------+----------+
    | Affected SOP Class UID                   | \-      | U        |
    +------------------------------------------+---------+----------+
    | Affected SOP Instance UID                | \-      | U        |
    +------------------------------------------+---------+----------+
    | Status                                   | \-      | M        |
    +------------------------------------------+---------+----------+

    | (=) - The value of the parameter is equal to the value of the parameter
      in the column to the left
    | C - The parameter is conditional.
    | M - Mandatory
    | MF - Mandatory with a fixed value
    | U - The use of this parameter is a DIMSE service user option
    | UF - User option with a fixed value

    Attributes
    ----------
    MessageID : int
        Identifies the operation and is used to distinguish this
        operation from other notifications or operations that may be in
        progress. No two identical values for the Message ID shall be used for
        outstanding operations.
    MessageIDBeingRespondedTo : int
        The Message ID of the operation request/indication to which this
        response/confirmation applies.
    RequestedSOPClassUID : pydicom.uid.UID, bytes or str
        The UID of the SOP Class to be deleted.
    RequestedSOPInstanceUID : pydicom.uid.UID, bytes or str
        The SOP Instance to be deleted.
    AffectedSOPClassUID : pydicom.uid.UID, bytes or str
        For the request/indication this specifies the SOP Class for
        storage. If included in the response/confirmation, it shall be equal
        to the value in the request/indication
    AffectedSOPInstanceUID : pydicom.uid.UID, bytes or str
        For the request/indication this specifies the SOP Instance for
        storage. If included in the response/confirmation, it shall be equal
        to the value in the request/indication
    Status : int
        The error or success notification of the operation.
    """
    STATUS_OPTIONAL_KEYWORDS = ('ErrorComment', 'ErrorID', )
    REQUEST_KEYWORDS = (
        'MessageID', 'RequestedSOPClassUID', 'RequestedSOPInstanceUID'
    )

    def __init__(self):
        self.MessageID = None
        self.MessageIDBeingRespondedTo = None
        self.RequestedSOPClassUID = None
        self.RequestedSOPInstanceUID = None
        self.AffectedSOPClassUID = None
        self.AffectedSOPInstanceUID = None
        self.Status = None

        # Optional
        self.ErrorComment = None
        self.ErrorID = None

    @property
    def AffectedSOPInstanceUID(self):
        """Return the *Affected SOP Instance UID* as :class:`~pydicom.uid.UID`.
        """
        return self._AffectedSOPInstanceUID

    @AffectedSOPInstanceUID.setter
    def AffectedSOPInstanceUID(self, value):
        """Set the *Affected SOP Instance UID*.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The value to use for the *Affected SOP Class UID* parameter.
        """
        self._AffectedSOPInstanceUID = value

    @property
    def RequestedSOPClassUID(self):
        """Return the *Requested SOP Class UID* as :class:`~pydicom.uid.UID`.
        """
        return self._RequestedSOPClassUID

    @RequestedSOPClassUID.setter
    def RequestedSOPClassUID(self, value):
        """Set the *Requested SOP Class UID*.

        Parameters
        ----------
        pydicom.uid.UID, bytes or str
            The value to use for the *Requested SOP Class UID* parameter.
        """
        self._RequestedSOPClassUID = value

    @property
    def RequestedSOPInstanceUID(self):
        """Return the *Requested SOP Instance UID* as
        :class:`~pydicom.uid.UID`.
        """
        return self._RequestedSOPInstanceUID

    @RequestedSOPInstanceUID.setter
    def RequestedSOPInstanceUID(self, value):
        """Set the *Requested SOP Instance UID*.

        Parameters
        ----------
        pydicom.uid.UID, bytes or str
            The value to use for the *Requested SOP Instance UID* parameter.
        """
        self._RequestedSOPInstanceUID = value
