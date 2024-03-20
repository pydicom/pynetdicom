"""
Define the DIMSE-C and DIMSE-N service parameter primitives.

Notes:
  * The class member names must match their corresponding DICOM element keyword
    in order for the DIMSE messages/primitives to be created correctly.
"""

from collections.abc import Sequence
from io import BytesIO
import logging
from pathlib import Path
from typing import Optional, List, Tuple, Union, TYPE_CHECKING
import warnings

from pydicom.tag import Tag, BaseTag
from pydicom.uid import UID

from pynetdicom._globals import OptionalUIDType
from pynetdicom.utils import set_ae, decode_bytes, set_uid


if TYPE_CHECKING:  # pragma: no cover
    from io import BufferedWriter
    from typing import Protocol  # Python 3.8+

    class NTF(Protocol):
        # Protocol for a NamedTemporaryFile
        name: str
        file: BufferedWriter

        def write(self, data: bytes) -> bytes: ...

        def close(self) -> None: ...


LOGGER = logging.getLogger(__name__)


DimseServiceType = Union[
    "C_ECHO",
    "C_FIND",
    "C_GET",
    "C_MOVE",
    "C_STORE",
    "N_ACTION",
    "N_CREATE",
    "N_DELETE",
    "N_EVENT_REPORT",
    "N_GET",
    "N_SET",
]
DimsePrimitiveType = Union["C_CANCEL", DimseServiceType]


# pylint: disable=invalid-name
# pylint: disable=attribute-defined-outside-init
# pylint: disable=too-many-instance-attributes
# pylint: disable=anomalous-backslash-in-string
class DIMSEPrimitive:
    """Base class for the DIMSE primitives."""

    STATUS_OPTIONAL_KEYWORDS: Tuple[str, ...] = ()
    REQUEST_KEYWORDS: Tuple[str, ...] = ()
    RESPONSE_KEYWORDS: Tuple[str, ...] = ("MessageIDBeingRespondedTo", "Status")

    _action_type_id: Optional[int] = None
    _affected_sop_class_uid: Optional[UID] = None
    _affected_sop_instance_uid: Optional[UID] = None
    _attribute_identifier_list: Union[None, BaseTag, List[BaseTag]] = None
    _dataset: Optional[BytesIO] = None
    _event_type_id: Optional[int] = None
    _message_id: Optional[int] = None
    _message_id_being_responded_to: Optional[int] = None
    _move_destination: Optional[str] = None
    _move_originator_application_entity_title: Optional[str] = None
    _move_originator_message_id: Optional[int] = None
    _number_of_completed_suboperations: Optional[int] = None
    _number_of_failed_suboperations: Optional[int] = None
    _number_of_remaining_suboperations: Optional[int] = None
    _number_of_warning_suboperations: Optional[int] = None
    _priority: int = 0x02
    _requested_sop_class_uid: Optional[UID] = None
    _requested_sop_instance_uid: Optional[UID] = None
    _status: Optional[int] = None

    _context_id: Optional[int] = None

    # If we are sending a C-STORE service primitive:
    #   If None then the dataset is encoded as BytesIO
    #   If not None then the dataset is stored at (path, offset)
    # If we are receiving a C-STORE service primitive:
    #   If None then the dataset is encoded as BytesIO
    #   If not None then the dataset is stored at _dataset_path
    # self._dataset_path = None
    # If we are sending a C-STORE service primitive:
    #   Always None
    # If we are receiving a C-STORE service primitive:
    #   If None then the dataset is encoded as BytesIO
    #   If not None then _dataset_file backs the dataset stored
    #   at _dataset_path
    # self._dataset_file = None
    _dataset_path: Optional[Union[Path, Tuple[Path, int]]] = None
    _dataset_file: Optional["NTF"] = None

    @property
    def AffectedSOPClassUID(self) -> Optional[UID]:
        """Get or set the *Affected SOP Class UID* as
        :class:`~pydicom.uid.UID`.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The value to use for the *Affected SOP Class UID* parameter.
        """
        return self._affected_sop_class_uid

    @AffectedSOPClassUID.setter
    def AffectedSOPClassUID(self, value: OptionalUIDType) -> None:
        """Set the *Affected SOP Class UID*."""
        self._affected_sop_class_uid = set_uid(value, "Affected SOP Class UID") or None

    @property
    def _AffectedSOPInstanceUID(self) -> Optional[UID]:
        """Return the *Affected SOP Instance UID* as :class:`~pydicom.uid.UID`."""
        return self._affected_sop_instance_uid

    @_AffectedSOPInstanceUID.setter
    def _AffectedSOPInstanceUID(self, value: OptionalUIDType) -> None:
        """Set the *Affected SOP Instance UID*.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The value for the Affected SOP Class UID
        """
        self._affected_sop_instance_uid = (
            set_uid(value, "Affected SOP Instance UID") or None
        )

    @property
    def _dataset_variant(self) -> Optional[BytesIO]:
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
    def _dataset_variant(self, value: Tuple[Optional[BytesIO], str]) -> None:
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
            raise TypeError(f"'{value[1]}' parameter must be a BytesIO object")

    @property
    def is_valid_request(self) -> bool:
        """Return ``True`` if the request is valid, ``False`` otherwise."""
        for keyword in self.REQUEST_KEYWORDS:
            if getattr(self, keyword) is None:
                return False

        return True

    @property
    def is_valid_response(self) -> bool:
        """Return ``True`` if the response is valid, ``False`` otherwise."""
        for keyword in self.RESPONSE_KEYWORDS:
            if getattr(self, keyword) is None:
                return False

        return True

    @property
    def MessageID(self) -> Optional[int]:
        """Get or set the *Message ID* value as :class:`int`.

        Parameters
        ----------
        int
            The value to use for the *Message ID* parameter.
        """
        return self._message_id

    @MessageID.setter
    def MessageID(self, value: Optional[int]) -> None:
        """Set the *Message ID*."""
        if isinstance(value, int):
            if 0 <= value < 2**16:
                self._message_id = value
            else:
                raise ValueError("Message ID must be between 0 and 65535, inclusive")
        elif value is None:
            self._message_id = value
        else:
            raise TypeError("Message ID must be an int")

    @property
    def MessageIDBeingRespondedTo(self) -> Optional[int]:
        """Get or set the *Message ID Being Responded To* as :class:`int`.

        Parameters
        ----------
        int
            The value to use for the *Message ID Being Responded To* parameter.
        """
        return self._message_id_being_responded_to

    @MessageIDBeingRespondedTo.setter
    def MessageIDBeingRespondedTo(self, value: Optional[int]) -> None:
        """Set the *Message ID Being Responded To*."""
        if isinstance(value, int):
            if 0 <= value < 2**16:
                self._message_id_being_responded_to = value
            else:
                raise ValueError(
                    "Message ID Being Responded To must be "
                    "between 0 and 65535, inclusive"
                )
        elif value is None:
            self._message_id_being_responded_to = value
        else:
            raise TypeError("Message ID Being Responded To must be an int")

    @property
    def _NumberOfCompletedSuboperations(self) -> Optional[int]:
        """Return the *Number of Completed Suboperations*."""
        return self._number_of_completed_suboperations

    @_NumberOfCompletedSuboperations.setter
    def _NumberOfCompletedSuboperations(self, value: Optional[int]) -> None:
        """Set the *Number of Completed Suboperations*."""
        if isinstance(value, int):
            if value >= 0:
                self._number_of_completed_suboperations = value
            else:
                raise ValueError(
                    "Number of Completed Suboperations must be "
                    "greater than or equal to 0"
                )
        elif value is None:
            self._number_of_completed_suboperations = value
        else:
            raise TypeError("Number of Completed Suboperations must be an int")

    @property
    def _NumberOfFailedSuboperations(self) -> Optional[int]:
        """Return the *Number of Failed Suboperations*."""
        return self._number_of_failed_suboperations

    @_NumberOfFailedSuboperations.setter
    def _NumberOfFailedSuboperations(self, value: Optional[int]) -> None:
        """Set the *Number of Failed Suboperations*."""
        if isinstance(value, int):
            if value >= 0:
                self._number_of_failed_suboperations = value
            else:
                raise ValueError(
                    "Number of Failed Suboperations must be "
                    "greater than or equal to 0"
                )
        elif value is None:
            self._number_of_failed_suboperations = value
        else:
            raise TypeError("Number of Failed Suboperations must be an int")

    @property
    def _NumberOfRemainingSuboperations(self) -> Optional[int]:
        """Return the *Number of Remaining Suboperations*."""
        return self._number_of_remaining_suboperations

    @_NumberOfRemainingSuboperations.setter
    def _NumberOfRemainingSuboperations(self, value: Optional[int]) -> None:
        """Set the *Number of Remaining Suboperations*."""
        if isinstance(value, int):
            if value >= 0:
                self._number_of_remaining_suboperations = value
            else:
                raise ValueError(
                    "Number of Remaining Suboperations must be "
                    "greater than or equal to 0"
                )
        elif value is None:
            self._number_of_remaining_suboperations = value
        else:
            raise TypeError("Number of Remaining Suboperations must be an int")

    @property
    def _NumberOfWarningSuboperations(self) -> Optional[int]:
        """Return the *Number of Warning Suboperations*."""
        return self._number_of_warning_suboperations

    @_NumberOfWarningSuboperations.setter
    def _NumberOfWarningSuboperations(self, value: Optional[int]) -> None:
        """Set the *Number of Warning Suboperations*."""
        if isinstance(value, int):
            if value >= 0:
                self._number_of_warning_suboperations = value
            else:
                raise ValueError(
                    "Number of Warning Suboperations must be "
                    "greater than or equal to 0"
                )
        elif value is None:
            self._number_of_warning_suboperations = value
        else:
            raise TypeError("Number of Warning Suboperations must be an int")

    @property
    def _Priority(self) -> int:
        """Return the *Priority* as :class:`int`.

        Parameters
        ----------
        int
            The value to use for the *Priority* parameter. It shall be one
            of the following:

            * 0: Medium
            * 1: High
            * 2: Low (Default)
        """
        return self._priority

    @_Priority.setter
    def _Priority(self, value: int) -> None:
        """Set the *Priority*."""
        if value in [0, 1, 2]:
            self._priority = value
        else:
            LOGGER.warning("Attempted to set Priority parameter to an invalid value")
            raise ValueError("Priority must be 0, 1, or 2")

    @property
    def _RequestedSOPClassUID(self) -> Optional[UID]:
        """Return the *Requested SOP Class UID*."""
        return self._requested_sop_class_uid

    @_RequestedSOPClassUID.setter
    def _RequestedSOPClassUID(self, value: OptionalUIDType) -> None:
        """Set the *Requested SOP Class UID*.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The value for the Requested SOP Class UID
        """
        self._requested_sop_class_uid = (
            set_uid(value, "Requested SOP Instance UID") or None
        )

    @property
    def _RequestedSOPInstanceUID(self) -> Optional[UID]:
        """Return the *Requested SOP Instance UID*."""
        return self._requested_sop_instance_uid

    @_RequestedSOPInstanceUID.setter
    def _RequestedSOPInstanceUID(self, value: OptionalUIDType) -> None:
        """Set the *Requested SOP Instance UID*.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The value for the Requested SOP Instance UID
        """
        self._requested_sop_instance_uid = (
            set_uid(value, "Requested SOP Instance UID") or None
        )

    @property
    def Status(self) -> Optional[int]:
        """Get or set the *Status* as :class:`int`.

        Parameters
        ----------
        int
            The value to use for the *Status* parameter.
        """
        return self._status

    @Status.setter
    def Status(self, value: Optional[int]) -> None:
        """Set the *Status*"""
        if isinstance(value, int) or value is None:
            self._status = value
        else:
            raise TypeError("DIMSE primitive's 'Status' must be an int")

    @property
    def msg_type(self) -> str:
        """Return the DIMSE message type as :class:`str`."""
        return self.__class__.__name__.replace("_", "-")


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
    Status : int
        The error or success notification of the operation.
    OffendingElement : list of int or None
        An optional status related field containing a list of the
        elements in which an error was detected.
    ErrorComment : str or None
        An optional status related field containing a text description
        of the error detected. 64 characters maximum.
    """

    STATUS_OPTIONAL_KEYWORDS = (
        "OffendingElement",
        "ErrorComment",
    )
    REQUEST_KEYWORDS = (
        "MessageID",
        "AffectedSOPClassUID",
        "AffectedSOPInstanceUID",
        "Priority",
        "DataSet",
    )

    def __init__(self) -> None:
        # Variable names need to match the corresponding DICOM Element keywords
        #   in order for the DIMSE Message classes to be built correctly.
        # Changes to the variable names can be made provided the DIMSEMessage()
        #   class' message_to_primitive() and primitive_to_message() methods
        #   are also changed
        # self.MessageID: Optional[int] = None
        # self.MessageIDBeingRespondedTo: Optional[int] = None
        # self.AffectedSOPClassUID: Optional[UID] = None
        # self.AffectedSOPInstanceUID: Optional[UID] = None
        # self.Priority = 0x02
        self.MoveOriginatorApplicationEntityTitle: Optional[str] = None
        self.MoveOriginatorMessageID: Optional[int] = None
        self.DataSet: Optional[BytesIO] = None
        # self.Status: Optional[int] = None

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
    def AffectedSOPInstanceUID(self) -> Optional[UID]:
        """Get or set the *Affected SOP Instance UID* as
        :class:`~pydicom.uid.UID`.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The value to use for the *Affected SOP Class UID* parameter.
        """
        return self._AffectedSOPInstanceUID

    @AffectedSOPInstanceUID.setter
    def AffectedSOPInstanceUID(self, value: OptionalUIDType) -> None:
        """Set the *Affected SOP Instance UID*."""
        self._AffectedSOPInstanceUID = value  # type: ignore

    @property
    def DataSet(self) -> Optional[BytesIO]:
        """Get or set the *Data Set* as :class:`io.BytesIO`."""
        return self._dataset_variant

    @DataSet.setter
    def DataSet(self, value: Optional[BytesIO]) -> None:
        """Set the *Data Set*."""
        self._dataset_variant = (value, "DataSet")  # type: ignore

    @property
    def MoveOriginatorApplicationEntityTitle(self) -> Optional[str]:
        """Get or set the *Move Originator Application Entity Title* as
        :class:`str`.

        Parameters
        ----------
        value : str
            The value to use for the *Move Originator AE Title* parameter.

        Returns
        -------
        str or None
            Th *Move Originator AE Title* value. May be ``None`` if the
            value was invalid.
        """
        return self._move_originator_application_entity_title

    @MoveOriginatorApplicationEntityTitle.setter
    def MoveOriginatorApplicationEntityTitle(self, value: Optional[str]) -> None:
        """Set the *Move Originator Application Entity Title*."""
        if isinstance(value, bytes):
            warnings.warn(
                "The use of bytes with 'Move Originator AE "
                "Title' is deprecated, use an ASCII str instead",
                DeprecationWarning,
            )
            value = decode_bytes(value).strip()

        try:
            value = set_ae(value, "Move Originator AE Title")
        except ValueError:
            LOGGER.error("Invalid 'Move Originator AE Title' in C-STORE request")
            value = None

        self._move_originator_application_entity_title = value

    @property
    def MoveOriginatorMessageID(self) -> Optional[int]:
        """Get or set the *Move Originator Message ID* as :class:`int`."""
        return self._move_originator_message_id

    @MoveOriginatorMessageID.setter
    def MoveOriginatorMessageID(self, value: Optional[int]) -> None:
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
                raise ValueError(
                    "Move Originator Message ID To must be "
                    "between 0 and 65535, inclusive"
                )
        elif value is None:
            self._move_originator_message_id = value
        else:
            raise TypeError("Move Originator Message ID To must be an int")

    @property
    def Priority(self) -> int:
        """Get or set the *Priority* as :class:`int`.

        Parameters
        ----------
        int
            The value to use for the *Priority* parameter. It shall be one
            of the following:

            * 0: Medium
            * 1: High
            * 2: Low (Default)
        """
        return self._Priority

    @Priority.setter
    def Priority(self, value: int) -> None:
        """Set the *Priority*."""
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
    Status : int
        The error or success notification of the operation.
    OffendingElement : list of int or None
        An optional status related field containing a list of the
        elements in which an error was detected.
    ErrorComment : str or None
        An optional status related field containing a text
        description of the error detected. 64 characters maximum.
    """

    STATUS_OPTIONAL_KEYWORDS = (
        "OffendingElement",
        "ErrorComment",
    )
    REQUEST_KEYWORDS = ("MessageID", "AffectedSOPClassUID", "Priority", "Identifier")

    def __init__(self) -> None:
        # Variable names need to match the corresponding DICOM Element keywords
        #   in order for the DIMSE Message classes to be built correctly.
        # Changes to the variable names can be made provided the DIMSEMessage()
        #   class' message_to_primitive() and primitive_to_message() methods
        #   are also changed
        # self.MessageID = None
        # self.MessageIDBeingRespondedTo = None
        # self.AffectedSOPClassUID = None
        # self.Priority = 0x02
        self.Identifier = None
        # self.Status = None

        # Optional Command Set elements used in with specific Status values
        # For Failure statuses 0xA900, 0xCxxx
        self.OffendingElement = None
        # For Failure statuses 0xA900, 0xA700, 0x0122, 0xCxxx
        self.ErrorComment = None

    @property
    def Identifier(self) -> Optional[BytesIO]:
        """Get or set the *Identifier* as :class:`io.BytesIO`.

        Parameters
        ----------
        io.BytesIO
            The value to use for the *Identifier* parameter.
        """
        return self._dataset_variant

    @Identifier.setter
    def Identifier(self, value: Optional[BytesIO]) -> None:
        """Set the *Identifier*."""
        self._dataset_variant = (value, "Identifier")  # type: ignore

    @property
    def Priority(self) -> int:
        """Get or set the *Priority* as :class:`int`.

        Parameters
        ----------
        int
            The value to use for the *Priority* parameter. It shall be one
            of the following:

            * 0: Medium
            * 1: High
            * 2: Low (Default)
        """
        return self._Priority

    @Priority.setter
    def Priority(self, value: int) -> None:
        """Set the *Priority*."""
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
    Status : int
        The error or success notification of the operation.
    OffendingElement : list of int or None
        An optional status related field containing a list of the
        elements in which an error was detected.
    ErrorComment : str or None
        An optional status related field containing a text
        description of the error detected. 64 characters maximum.
    """

    STATUS_OPTIONAL_KEYWORDS = (
        "ErrorComment",
        "OffendingElement",
        "NumberOfRemainingSuboperations",
        "NumberOfCompletedSuboperations",
        "NumberOfFailedSuboperations",
        "NumberOfWarningSuboperations",
    )
    REQUEST_KEYWORDS = ("MessageID", "AffectedSOPClassUID", "Priority", "Identifier")

    def __init__(self) -> None:
        # Variable names need to match the corresponding DICOM Element keywords
        #   in order for the DIMSE Message classes to be built correctly.
        # Changes to the variable names can be made provided the DIMSEMessage()
        #   class' message_to_primitive() and primitive_to_message() methods
        #   are also changed
        # self.MessageID = None
        # self.MessageIDBeingRespondedTo = None
        # self.AffectedSOPClassUID = None
        # self.Priority = 0x02
        self.Identifier = None
        # self.Status = None
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
    def Identifier(self) -> Optional[BytesIO]:
        """Get or set the *Identifier* as :class:`io.BytesIO`.

        Parameters
        ----------
        io.BytesIO
            The value to use for the *Identifier* parameter.
        """
        return self._dataset_variant

    @Identifier.setter
    def Identifier(self, value: Optional[BytesIO]) -> None:
        """Set the *Identifier*."""
        self._dataset_variant = (value, "Identifier")  # type: ignore

    @property
    def NumberOfCompletedSuboperations(self) -> Optional[int]:
        """Get or set the *Number of Completed Suboperations* as :class:`int`."""
        return self._NumberOfCompletedSuboperations

    @NumberOfCompletedSuboperations.setter
    def NumberOfCompletedSuboperations(self, value: Optional[int]) -> None:
        """Set the *Number of Completed Suboperations*."""
        self._NumberOfCompletedSuboperations = value

    @property
    def NumberOfFailedSuboperations(self) -> Optional[int]:
        """Get or set the *Number of Failed Suboperations* as :class:`int`."""
        return self._NumberOfFailedSuboperations

    @NumberOfFailedSuboperations.setter
    def NumberOfFailedSuboperations(self, value: Optional[int]) -> None:
        """Set the *Number of Failed Suboperations*."""
        self._NumberOfFailedSuboperations = value

    @property
    def NumberOfRemainingSuboperations(self) -> Optional[int]:
        """Get or set the *Number of Remaining Suboperations* as :class:`int`."""
        return self._NumberOfRemainingSuboperations

    @NumberOfRemainingSuboperations.setter
    def NumberOfRemainingSuboperations(self, value: Optional[int]) -> None:
        """Set the *Number of Remaining Suboperations*."""
        self._NumberOfRemainingSuboperations = value

    @property
    def NumberOfWarningSuboperations(self) -> Optional[int]:
        """Get or set the *Number of Warning Suboperations* as :class:`int`."""
        return self._NumberOfWarningSuboperations

    @NumberOfWarningSuboperations.setter
    def NumberOfWarningSuboperations(self, value: Optional[int]) -> None:
        """Set the *Number of Warning Suboperations*.

        Parameters
        ----------
        int
            The value to use for the *Number of Warning Suboperations*
            parameter.
        """
        self._NumberOfWarningSuboperations = value

    @property
    def Priority(self) -> int:
        """Get or set the *Priority* as :class:`int`.

        Parameters
        ----------
        int
            The value to use for the *Priority* parameter. It shall be one
            of the following:

            * 0: Medium
            * 1: High
            * 2: Low (Default)
        """
        return self._Priority

    @Priority.setter
    def Priority(self, value: int) -> None:
        """Set the *Priority*."""
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
    Status : int
        The error or success notification of the operation.
    OffendingElement : list of int or None
        An optional status related field containing a list of the
        elements in which an error was detected.
    ErrorComment : str or None
        An optional status related field containing a text
        description of the error detected. 64 characters maximum.
    """

    STATUS_OPTIONAL_KEYWORDS = (
        "ErrorComment",
        "OffendingElement",
        "NumberOfRemainingSuboperations",
        "NumberOfCompletedSuboperations",
        "NumberOfFailedSuboperations",
        "NumberOfWarningSuboperations",
    )
    REQUEST_KEYWORDS = (
        "MessageID",
        "AffectedSOPClassUID",
        "Priority",
        "Identifier",
        "MoveDestination",
    )

    def __init__(self) -> None:
        # Variable names need to match the corresponding DICOM Element keywords
        #   in order for the DIMSE Message classes to be built correctly.
        # Changes to the variable names can be made provided the DIMSEMessage()
        #   class' message_to_primitive() and primitive_to_message() methods
        #   are also changed
        # self.MessageID = None
        # self.MessageIDBeingRespondedTo = None
        # self.AffectedSOPClassUID = None
        # self.Priority = 0x02
        self.MoveDestination = None
        self.Identifier = None
        # self.Status = None
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
    def Identifier(self) -> Optional[BytesIO]:
        """Get or set the *Identifier* as :class:`io.BytesIO`.

        Parameters
        ----------
        io.BytesIO
            The value to use for the *Identifier* parameter.
        """
        return self._dataset_variant

    @Identifier.setter
    def Identifier(self, value: Optional[BytesIO]) -> None:
        """Set the *Identifier*."""
        self._dataset_variant = (value, "Identifier")  # type: ignore

    @property
    def MoveDestination(self) -> Optional[str]:
        """Get or set the *Move Destination* as :class:`str`.

        Parameters
        ----------
        value : str
            The value to use for the *Move Destination* parameter. Cannot
            be an empty string.

        Returns
        -------
        str
            The *Move Destination* value.
        """
        return self._move_destination

    @MoveDestination.setter
    def MoveDestination(self, value: Optional[Union[str, bytes]]) -> None:
        """Set the *Move Destination*."""
        if isinstance(value, bytes):
            warnings.warn(
                "The use of bytes with 'Move Destination' is deprecated, "
                "use an ASCII str instead",
                DeprecationWarning,
            )
            value = decode_bytes(value).strip()

        self._move_destination = set_ae(value, "Move Destination", allow_empty=False)

    @property
    def NumberOfCompletedSuboperations(self) -> Optional[int]:
        """Get or set the *Number of Completed Suboperations* as :class:`int`."""
        return self._NumberOfCompletedSuboperations

    @NumberOfCompletedSuboperations.setter
    def NumberOfCompletedSuboperations(self, value: Optional[int]) -> None:
        """Set the *Number of Completed Suboperations*."""
        self._NumberOfCompletedSuboperations = value

    @property
    def NumberOfFailedSuboperations(self) -> Optional[int]:
        """Get or set the *Number of Failed Suboperations* as :class:`int`."""
        return self._NumberOfFailedSuboperations

    @NumberOfFailedSuboperations.setter
    def NumberOfFailedSuboperations(self, value: Optional[int]) -> None:
        """Set the *Number of Failed Suboperations*."""
        self._NumberOfFailedSuboperations = value

    @property
    def NumberOfRemainingSuboperations(self) -> Optional[int]:
        """Get or set the *Number of Remaining Suboperations* as :class:`int`."""
        return self._NumberOfRemainingSuboperations

    @NumberOfRemainingSuboperations.setter
    def NumberOfRemainingSuboperations(self, value: Optional[int]) -> None:
        """Set the *Number of Remaining Suboperations*."""
        self._NumberOfRemainingSuboperations = value

    @property
    def NumberOfWarningSuboperations(self) -> Optional[int]:
        """Get or set the *Number of Warning Suboperations* as :class:`int`."""
        return self._NumberOfWarningSuboperations

    @NumberOfWarningSuboperations.setter
    def NumberOfWarningSuboperations(self, value: Optional[int]) -> None:
        """Set the *Number of Warning Suboperations*."""
        self._NumberOfWarningSuboperations = value

    @property
    def Priority(self) -> int:
        """Get or set the *Priority* as :class:`int`.

        Parameters
        ----------
        int
            The value to use for the *Priority* parameter. It shall be one
            of the following:

            * 0: Medium
            * 1: High
            * 2: Low (Default)
        """
        return self._Priority

    @Priority.setter
    def Priority(self, value: int) -> None:
        """Set the *Priority*."""
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

    STATUS_OPTIONAL_KEYWORDS = ("ErrorComment",)
    REQUEST_KEYWORDS = ("MessageID", "AffectedSOPClassUID")

    def __init__(self) -> None:
        # Variable names need to match the corresponding DICOM Element keywords
        #   in order for the DIMSE Message classes to be built correctly.
        # Changes to the variable names can be made provided the DIMSEMessage()
        #   class' message_to_primitive() and primitive_to_message() methods
        #   are also changed
        # self.MessageID = None
        # self.MessageIDBeingRespondedTo = None
        # self.AffectedSOPClassUID = None
        # self.Status = None

        # (Optional) for Failure status 0x0122
        self.ErrorComment = None


class C_CANCEL:
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

    References
    ----------

    * DICOM Standard, Part 7, :dcm:`Section 9.3.2.3<part07/sect_9.3.2.3.html>`
    """

    def __init__(self) -> None:
        """Initialise the C_CANCEL"""
        # Variable names need to match the corresponding DICOM Element keywords
        #   in order for the DIMSE Message classes to be built correctly.
        # Changes to the variable names can be made provided the DIMSEMessage()
        #   class' message_to_primitive() and primitive_to_message() methods
        #   are also changed
        self._message_id_being_responded_to: Optional[int] = None
        self._context_id: Optional[int] = None
        self._dataset_path: Optional[Union[Path, Tuple[Path, int]]] = None
        self._dataset_file: Optional["NTF"] = None

    @property
    def MessageIDBeingRespondedTo(self) -> Optional[int]:
        """Get or set the *Message ID Being Responded To* as an :class:`int`.

        Parameters
        ----------
        int
            The value to use for the *Message ID Being Responded To* parameter.
        """
        return self._message_id_being_responded_to

    @MessageIDBeingRespondedTo.setter
    def MessageIDBeingRespondedTo(self, value: Optional[int]) -> None:
        """Set the *Message ID Being Responded To*."""
        if isinstance(value, int):
            if 0 <= value < 2**16:
                self._message_id_being_responded_to = value
            else:
                raise ValueError(
                    "Message ID Being Responded To must be "
                    "between 0 and 65535, inclusive"
                )
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
    Status : int
        The error or success notification of the operation.
    """

    # Optional status element keywords other than 'Status'
    STATUS_OPTIONAL_KEYWORDS = (
        "AffectedSOPClassUID",
        "AffectedSOPInstanceUID",
        "EventTypeID",
        "ErrorComment",
        "ErrorID",  # EventInformation
    )
    REQUEST_KEYWORDS = (
        "MessageID",
        "AffectedSOPClassUID",
        "EventTypeID",
        "AffectedSOPInstanceUID",
    )

    def __init__(self) -> None:
        # self.MessageID = None
        # self.MessageIDBeingRespondedTo = None
        # self.AffectedSOPClassUID = None
        # self.AffectedSOPInstanceUID = None
        self.EventTypeID = None
        self.EventInformation = None
        self.EventReply = None
        # self.Status = None

        # Optional status elements
        self.ErrorComment = None
        self.ErrorID = None

    @property
    def AffectedSOPInstanceUID(self) -> Optional[UID]:
        """Get or set the *Affected SOP Instance UID* as
        :class:`~pydicom.uid.UID`.
        """
        return self._AffectedSOPInstanceUID

    @AffectedSOPInstanceUID.setter
    def AffectedSOPInstanceUID(self, value: OptionalUIDType) -> None:
        """Set the *Affected SOP Instance UID*.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The value to use for the *Affected SOP Class UID* parameter.
        """
        self._AffectedSOPInstanceUID = value  # type: ignore

    @property
    def EventInformation(self) -> Optional[BytesIO]:
        """Get or set the *Event Information* as :class:`io.BytesIO`."""
        return self._dataset_variant

    @EventInformation.setter
    def EventInformation(self, value: Optional[BytesIO]) -> None:
        """Set the *Event Information*.

        Parameters
        ----------
        io.BytesIO
            The value to use for the *Event Information* parameter.
        """
        self._dataset_variant = (value, "EventInformation")  # type: ignore

    @property
    def EventReply(self) -> Optional[BytesIO]:
        """Get or set the *Event Reply* as :class:`io.BytesIO`."""
        return self._dataset_variant

    @EventReply.setter
    def EventReply(self, value: Optional[BytesIO]) -> None:
        """Set the *Event Reply*.

        Parameters
        ----------
        io.BytesIO
            The value to use for the *Event Reply* parameter.
        """
        self._dataset_variant = (value, "EventReply")  # type: ignore

    @property
    def EventTypeID(self) -> Optional[int]:
        """Get or set the *Event Type ID* as :class:`int`."""
        return self._event_type_id

    @EventTypeID.setter
    def EventTypeID(self, value: Optional[int]) -> None:
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
    AffectedSOPClassUID : pydicom.uid.UID, bytes or str
        The SOP Class UID of the SOP Instance for which the attributes were
        retrieved.
    Status : int
        The error or success notification of the operation.
    """

    STATUS_OPTIONAL_KEYWORDS = (
        "AttributeIdentifierList",
        "ErrorComment",
        "ErrorID",
    )
    REQUEST_KEYWORDS = ("MessageID", "RequestedSOPClassUID", "RequestedSOPInstanceUID")

    def __init__(self) -> None:
        # self.MessageID = None
        # self.MessageIDBeingRespondedTo = None
        # self.RequestedSOPClassUID = None
        # self.RequestedSOPInstanceUID = None
        self.AttributeIdentifierList = None
        # self.AffectedSOPClassUID = None
        # self.AffectedSOPInstanceUID = None
        self.AttributeList = None
        # self.Status = None

        # (Optional) elements for specific status values
        self.ErrorComment = None
        self.ErrorID = None

    @property
    def AffectedSOPInstanceUID(self) -> Optional[UID]:
        """Get or set the *Affected SOP Instance UID* as
        :class:`~pydicom.uid.UID`.
        """
        return self._AffectedSOPInstanceUID

    @AffectedSOPInstanceUID.setter
    def AffectedSOPInstanceUID(self, value: OptionalUIDType) -> None:
        """Set the *Affected SOP Instance UID*.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The value to use for the *Affected SOP Class UID* parameter.
        """
        self._AffectedSOPInstanceUID = value  # type: ignore

    @property
    def AttributeIdentifierList(self) -> Optional[Union[BaseTag, List[BaseTag]]]:
        """Get or set the *Attribute Identifier List* as a :class:`list` of
        :class:`~pydicom.tag.BaseTag`.

        Parameters
        ----------
        pydicom.tag.BaseTag or list of pydicom.tag.BaseTag
            The value to use for the *Attribute Identifier List* parameter.
            A pydicom :class:`pydicom.tag.BaseTag` or list of
            :class:`pydicom.tag.BaseTag` or any values acceptable for creating
            them.
        """
        return self._attribute_identifier_list

    @AttributeIdentifierList.setter
    def AttributeIdentifierList(
        self, value: Optional[Union[BaseTag, List[BaseTag]]]
    ) -> None:
        """Set the *Attribute Identifier List*."""
        # Be careful as a tag value of 0x00000000 is possible (though unlikely)
        if value is None:
            self._attribute_identifier_list = None
            return

        try:
            if isinstance(value, Sequence):
                if not value:
                    self._attribute_identifier_list = None

                if len(value) == 1:
                    # Force to a single value - workaround for pydicom #757
                    self._attribute_identifier_list = Tag(value[0])
                else:
                    self._attribute_identifier_list = [Tag(tag) for tag in value]
            else:
                self._attribute_identifier_list = Tag(value)
        except (TypeError, ValueError):
            raise ValueError(
                "Attribute Identifier List must be convertible to a pydicom "
                "BaseTag or list of BaseTag"
            )

    @property
    def AttributeList(self) -> Optional[BytesIO]:
        """Get or set the *Attribute List* as :class:`io.BytesIO`.

        Parameters
        ----------
        io.BytesIO
            The value to use for the *Attribute List* parameter.
        """
        return self._dataset_variant

    @AttributeList.setter
    def AttributeList(self, value: Optional[BytesIO]) -> None:
        """Set the *Attribute List*."""
        self._dataset_variant = (value, "AttributeList")  # type: ignore

    @property
    def RequestedSOPClassUID(self) -> Optional[UID]:
        """Get or set the *Requested SOP Class UID* as
        :class:`~pydicom.uid.UID`.

        Parameters
        ----------
        pydicom.uid.UID, bytes or str
            The value to use for the *Requested SOP Class UID* parameter.
        """
        return self._RequestedSOPClassUID

    @RequestedSOPClassUID.setter
    def RequestedSOPClassUID(self, value: OptionalUIDType) -> None:
        """Set the *Requested SOP Class UID*."""
        self._RequestedSOPClassUID = value  # type: ignore

    @property
    def RequestedSOPInstanceUID(self) -> Optional[UID]:
        """Get or set the *Requested SOP Instance UID* as
        :class:`~pydicom.uid.UID`.

        Parameters
        ----------
        pydicom.uid.UID, bytes or str
            The value to use for the *Requested SOP Instance UID* parameter.
        """
        return self._RequestedSOPInstanceUID

    @RequestedSOPInstanceUID.setter
    def RequestedSOPInstanceUID(self, value: OptionalUIDType) -> None:
        """Set the *Requested SOP Instance UID*."""
        self._RequestedSOPInstanceUID = value  # type: ignore


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
    AffectedSOPClassUID : pydicom.uid.UID, bytes or str
        The SOP Class UID of the modified SOP Instance.
    Status : int
        The error or success notification of the operation.
    """

    STATUS_OPTIONAL_KEYWORDS = ("ErrorComment", "ErrorID", "AttributeIdentifierList")
    REQUEST_KEYWORDS = (
        "MessageID",
        "RequestedSOPClassUID",
        "RequestedSOPInstanceUID",
        "ModificationList",
    )

    def __init__(self) -> None:
        # self.MessageID = None
        # self.MessageIDBeingRespondedTo = None
        # self.RequestedSOPClassUID = None
        # self.RequestedSOPInstanceUID = None
        self.ModificationList = None
        self.AttributeList = None
        # self.AffectedSOPClassUID = None
        # self.AffectedSOPInstanceUID = None
        # self.Status = None

        # Optional
        self.ErrorComment = None
        self.ErrorID = None
        self.AttributeIdentifierList = None

    @property
    def AffectedSOPInstanceUID(self) -> Optional[UID]:
        """Get or set the *Affected SOP Instance UID* as
        :class:`~pydicom.uid.UID`.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The value to use for the *Affected SOP Class UID* parameter.
        """
        return self._AffectedSOPInstanceUID

    @AffectedSOPInstanceUID.setter
    def AffectedSOPInstanceUID(self, value: OptionalUIDType) -> None:
        """Set the *Affected SOP Instance UID*."""
        self._AffectedSOPInstanceUID = value  # type: ignore

    @property
    def AttributeList(self) -> Optional[BytesIO]:
        """Return the *Attribute List* as :class:`io.BytesIO`.

        Parameters
        ----------
        io.BytesIO
            The value to use for the *Attribute List* parameter.
        """
        return self._dataset_variant

    @AttributeList.setter
    def AttributeList(self, value: Optional[BytesIO]) -> None:
        """Set the *Attribute List*."""
        self._dataset_variant = (value, "AttributeList")  # type: ignore

    @property
    def ModificationList(self) -> Optional[BytesIO]:
        """Return the *Modification List* as :class:`io.BytesIO`.

        Parameters
        ----------
        io.BytesIO
            The value to use for the *Modification List* parameter.
        """
        return self._dataset_variant

    @ModificationList.setter
    def ModificationList(self, value: Optional[BytesIO]) -> None:
        """Set the *Modification List*."""
        self._dataset_variant = (value, "ModificationList")  # type: ignore

    @property
    def RequestedSOPClassUID(self) -> Optional[UID]:
        """Return the *Requested SOP Class UID* as :class:`~pydicom.uid.UID`.

        Parameters
        ----------
        pydicom.uid.UID, bytes or str
            The value to use for the *Requested SOP Class UID* parameter.
        """
        return self._RequestedSOPClassUID

    @RequestedSOPClassUID.setter
    def RequestedSOPClassUID(self, value: OptionalUIDType) -> None:
        """Set the *Requested SOP Class UID*."""
        self._RequestedSOPClassUID = value  # type: ignore

    @property
    def RequestedSOPInstanceUID(self) -> Optional[UID]:
        """Return the *Requested SOP Instance UID* as
        :class:`~pydicom.uid.UID`.

        Parameters
        ----------
        pydicom.uid.UID, bytes or str
            The value to use for the *Requested SOP Instance UID* parameter.
        """
        return self._RequestedSOPInstanceUID

    @RequestedSOPInstanceUID.setter
    def RequestedSOPInstanceUID(self, value: OptionalUIDType) -> None:
        """Set the *Requested SOP Instance UID*."""
        self._RequestedSOPInstanceUID = value  # type: ignore


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
    AffectedSOPClassUID : pydicom.uid.UID, bytes or str
        For the request/indication this specifies the SOP Class for
        storage. If included in the response/confirmation, it shall be equal
        to the value in the request/indication
    Status : int
        The error or success notification of the operation.
    """

    STATUS_OPTIONAL_KEYWORDS = ("ErrorComment", "ErrorID", "AttributeIdentifierList")
    REQUEST_KEYWORDS = (
        "MessageID",
        "RequestedSOPClassUID",
        "RequestedSOPInstanceUID",
        "ActionTypeID",
    )

    def __init__(self) -> None:
        # self.MessageID = None
        # self.MessageIDBeingRespondedTo = None
        # self.RequestedSOPClassUID = None
        # self.RequestedSOPInstanceUID = None
        self.ActionTypeID = None
        self.ActionInformation = None
        # self.AffectedSOPClassUID = None
        # self.AffectedSOPInstanceUID = None
        self.ActionReply = None
        # self.Status = None

        # Optional status elements
        self.ErrorComment = None
        self.ErrorID = None

    @property
    def ActionInformation(self) -> Optional[BytesIO]:
        """Return the *Action Information* as :class:`io.BytesIO`.

        Parameters
        ----------
        io.BytesIO
            The value to use for the *Action Information* parameter.
        """
        return self._dataset_variant

    @ActionInformation.setter
    def ActionInformation(self, value: Optional[BytesIO]) -> None:
        """Set the *Action Information*."""
        self._dataset_variant = (value, "ActionInformation")  # type: ignore

    @property
    def ActionReply(self) -> Optional[BytesIO]:
        """Return the *Action Reply* as :class:`io.BytesIO`.

        Parameters
        ----------
        io.BytesIO
            The value to use for the *Action Reply* parameter.
        """
        return self._dataset_variant

    @ActionReply.setter
    def ActionReply(self, value: Optional[BytesIO]) -> None:
        """Set the *Action Reply*."""
        self._dataset_variant = (value, "ActionReply")  # type: ignore

    @property
    def ActionTypeID(self) -> Optional[int]:
        """Return the *Action Type ID* as :class:`int`.

        Parameters
        ----------
        int
            The value to use for the *Action Type ID* parameter.
        """
        return self._action_type_id

    @ActionTypeID.setter
    def ActionTypeID(self, value: Optional[int]) -> None:
        """Set the *Action Type ID*."""
        if isinstance(value, int) or value is None:
            self._action_type_id = value
        else:
            raise TypeError("'N_ACTION.ActionTypeID' must be an int.")

    @property
    def AffectedSOPInstanceUID(self) -> Optional[UID]:
        """Return the *Affected SOP Instance UID* as :class:`~pydicom.uid.UID`.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The value to use for the *Affected SOP Class UID* parameter.
        """
        return self._AffectedSOPInstanceUID

    @AffectedSOPInstanceUID.setter
    def AffectedSOPInstanceUID(self, value: OptionalUIDType) -> None:
        """Set the *Affected SOP Instance UID*."""
        self._AffectedSOPInstanceUID = value  # type: ignore

    @property
    def RequestedSOPClassUID(self) -> Optional[UID]:
        """Return the *Requested SOP Class UID* as :class:`~pydicom.uid.UID`.

        Parameters
        ----------
        pydicom.uid.UID, bytes or str
            The value to use for the *Requested SOP Class UID* parameter.
        """
        return self._RequestedSOPClassUID

    @RequestedSOPClassUID.setter
    def RequestedSOPClassUID(self, value: OptionalUIDType) -> None:
        """Set the *Requested SOP Class UID*."""
        self._RequestedSOPClassUID = value  # type: ignore

    @property
    def RequestedSOPInstanceUID(self) -> Optional[UID]:
        """Return the *Requested SOP Instance UID* as
        :class:`~pydicom.uid.UID`.

        Parameters
        ----------
        pydicom.uid.UID, bytes or str
            The value to use for the *Requested SOP Instance UID* parameter.
        """
        return self._RequestedSOPInstanceUID

    @RequestedSOPInstanceUID.setter
    def RequestedSOPInstanceUID(self, value: OptionalUIDType) -> None:
        """Set the *Requested SOP Instance UID*."""
        self._RequestedSOPInstanceUID = value  # type: ignore


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
    Status : int
        The error or success notification of the operation. It shall be
        one of the following values:
    """

    STATUS_OPTIONAL_KEYWORDS = (
        "ErrorComment",
        "ErrorID",
    )
    REQUEST_KEYWORDS = ("MessageID", "AffectedSOPClassUID")

    def __init__(self) -> None:
        # self.MessageID = None
        # self.MessageIDBeingRespondedTo = None
        # self.AffectedSOPClassUID = None
        # self.AffectedSOPInstanceUID = None
        self.AttributeList = None
        # self.Status = None

        # Optional elements
        self.ErrorComment = None
        self.ErrorID = None

    @property
    def AffectedSOPInstanceUID(self) -> Optional[UID]:
        """Return the *Affected SOP Instance UID* as :class:`~pydicom.uid.UID`.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The value to use for the *Affected SOP Class UID* parameter.
        """
        return self._AffectedSOPInstanceUID

    @AffectedSOPInstanceUID.setter
    def AffectedSOPInstanceUID(self, value: OptionalUIDType) -> None:
        """Set the *Affected SOP Instance UID*."""
        self._AffectedSOPInstanceUID = value  # type: ignore

    @property
    def AttributeList(self) -> Optional[BytesIO]:
        """Return the *Attribute List* as :class:`io.BytesIO`.

        Parameters
        ----------
        io.BytesIO
            The value to use for the *Attribute List* parameter.
        """
        return self._dataset_variant

    @AttributeList.setter
    def AttributeList(self, value: Optional[BytesIO]) -> None:
        """Set the *Attribute List*."""
        self._dataset_variant = (value, "AttributeList")  # type: ignore


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
    AffectedSOPClassUID : pydicom.uid.UID, bytes or str
        For the request/indication this specifies the SOP Class for
        storage. If included in the response/confirmation, it shall be equal
        to the value in the request/indication
    Status : int
        The error or success notification of the operation.
    """

    STATUS_OPTIONAL_KEYWORDS = (
        "ErrorComment",
        "ErrorID",
    )
    REQUEST_KEYWORDS = ("MessageID", "RequestedSOPClassUID", "RequestedSOPInstanceUID")

    def __init__(self) -> None:
        # self.MessageID = None
        # self.MessageIDBeingRespondedTo = None
        # self.RequestedSOPClassUID = None
        # self.RequestedSOPInstanceUID = None
        # self.AffectedSOPClassUID = None
        # self.AffectedSOPInstanceUID = None
        # self.Status = None

        # Optional
        self.ErrorComment = None
        self.ErrorID = None

    @property
    def AffectedSOPInstanceUID(self) -> Optional[UID]:
        """Return the *Affected SOP Instance UID* as :class:`~pydicom.uid.UID`.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The value to use for the *Affected SOP Class UID* parameter.
        """
        return self._AffectedSOPInstanceUID

    @AffectedSOPInstanceUID.setter
    def AffectedSOPInstanceUID(self, value: OptionalUIDType) -> None:
        """Set the *Affected SOP Instance UID*."""
        self._AffectedSOPInstanceUID = value  # type: ignore

    @property
    def RequestedSOPClassUID(self) -> Optional[UID]:
        """Return the *Requested SOP Class UID* as :class:`~pydicom.uid.UID`.

        Parameters
        ----------
        pydicom.uid.UID, bytes or str
            The value to use for the *Requested SOP Class UID* parameter.
        """
        return self._RequestedSOPClassUID

    @RequestedSOPClassUID.setter
    def RequestedSOPClassUID(self, value: OptionalUIDType) -> None:
        """Set the *Requested SOP Class UID*."""
        self._RequestedSOPClassUID = value  # type: ignore

    @property
    def RequestedSOPInstanceUID(self) -> Optional[UID]:
        """Return the *Requested SOP Instance UID* as
        :class:`~pydicom.uid.UID`.

        Parameters
        ----------
        pydicom.uid.UID, bytes or str
            The value to use for the *Requested SOP Instance UID* parameter.
        """
        return self._RequestedSOPInstanceUID

    @RequestedSOPInstanceUID.setter
    def RequestedSOPInstanceUID(self, value: OptionalUIDType) -> None:
        """Set the *Requested SOP Instance UID*."""
        self._RequestedSOPInstanceUID = value  # type: ignore
