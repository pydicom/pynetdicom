"""
Define the DIMSE-C and DIMSE-N service parameter primitives.

Notes:
  * The class member names must match their corresponding DICOM element keyword
    in order for the DIMSE messages/primitives to be created correctly.

TODO: Implement properties for DIMSE-N parameters
TODO: Implement status related parameters for DIMSE-N classes
TODO: Add string output for the DIMSE-C classes
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

from pynetdicom3.utils import validate_ae_title

LOGGER = logging.getLogger('pynetdicom3.dimse_primitives')

# pylint: disable=invalid-name
# pylint: disable=attribute-defined-outside-init
# pylint: disable=too-many-instance-attributes

# DIMSE-C Services
class C_STORE(object):
    """Represents a C-STORE primitive.

    The C-STORE service is used by a DIMSE user to store a composite SOP
    Instance on a peer DISMSE user. It is a confirmed service.

    **C-STORE Service Procedure**

    1. The invoking DIMSE user requests that the performing DIMSE user store a
       composite SOP Instance by issuing a C-STORE request primitive to the
       DIMSE provider
    2. The DIMSE provider issues a C-STORE indication primitive to the
       performing DIMSE user
    3. The performing DIMSE user reports acceptance or rejection of the C-STORE
       request primitive by issuing a C-STORE response primitive to the DIMSE
       provider
    4. The DIMSE provider issues a C-STORE confirmation primitive to the
       invoking DIMSE user, completing the C-STORE operation.

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

    | (=) - The value of the parameter is equal to the value of the parameter in
      the column to the left
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
        The pydicom Dataset containing the Attributes of the Composite
        SOP Instance to be stored, encoded as a BytesIO object
    Status : int
        The error or success notification of the operation.
    OffendingElement : list of int or None
        An optional status related field containing a list of the
        elements in which an error was detected.
    ErrorComment : str or None
        An optional status related field containing a text description
        of the error detected. 64 characters maximum.

    References
    ----------

    * DICOM Standard, Part 4, Annex B
    * DICOM Standard, Part 7, 9.1.1
    """
    STATUS_OPTIONAL_KEYWORDS = ('OffendingElement', 'ErrorComment', )

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
    def MessageID(self):
        """Return the DIMSE *Message ID*."""
        return self._message_id

    @MessageID.setter
    def MessageID(self, value):
        """Set the DIMSE *Message ID*."""
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
        """Return the *Message ID Being Responded To*."""
        return self._message_id_being_responded_to

    @MessageIDBeingRespondedTo.setter
    def MessageIDBeingRespondedTo(self, value):
        """Set the *Message ID Being Responded To*."""
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
    def AffectedSOPClassUID(self):
        """Return the *Affected SOP Class UID*."""
        return self._affected_sop_class_uid

    @AffectedSOPClassUID.setter
    def AffectedSOPClassUID(self, value):
        """Set the *Affected SOP Class UID*.

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
            raise TypeError("Affected SOP Class UID must be a "
                            "pydicom.uid.UID, str or bytes")

        if value is not None and not value.is_valid:
            LOGGER.error("Affected SOP Class UID is an invalid UID")
            raise ValueError("Affected SOP Class UID is an invalid UID")

        self._affected_sop_class_uid = value

    @property
    def AffectedSOPInstanceUID(self):
        """Return the *Affected SOP Instance UID*."""
        return self._affected_sop_instance_uid

    @AffectedSOPInstanceUID.setter
    def AffectedSOPInstanceUID(self, value):
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

        if value is not None and not value.is_valid:
            LOGGER.error("Affected SOP Instance UID is an invalid UID")
            raise ValueError("Affected SOP Instance UID is an invalid UID")

        self._affected_sop_instance_uid = value

    @property
    def Priority(self):
        """Return the *Priority*."""
        return self._priority

    @Priority.setter
    def Priority(self, value):
        """Set the *Priority*."""
        if value in [0, 1, 2]:
            self._priority = value
        else:
            LOGGER.warning("Attempted to set C-STORE Priority parameter to "
                           "an invalid value")
            raise ValueError("C-STORE Priority must be 0, 1, or 2")

    @property
    def MoveOriginatorApplicationEntityTitle(self):
        """Return the *Move Originator Application Entity Title*."""
        return self._move_originator_application_entity_title

    @MoveOriginatorApplicationEntityTitle.setter
    def MoveOriginatorApplicationEntityTitle(self, value):
        """Set the *Move Originator Application Entity Title*.

        Parameters
        ----------
        value : str or bytes
            The Move Originator AE Title as a string or bytes object. Cannot be
            an empty string and will be truncated to 16 characters long
        """
        if isinstance(value, str):
            value = codecs.encode(value, 'ascii')

        if value is not None:
            self._move_originator_application_entity_title = validate_ae_title(
                value
            )
        else:
            self._move_originator_application_entity_title = None

    @property
    def MoveOriginatorMessageID(self):
        """Return the *Move Originator Message ID*."""
        return self._move_originator_message_id

    @MoveOriginatorMessageID.setter
    def MoveOriginatorMessageID(self, value):
        """Set the *Move Originator Message ID*."""
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
    def DataSet(self):
        """Return the *Data Set*."""
        return self._dataset

    @DataSet.setter
    def DataSet(self, value):
        """Set the *Data Set*."""
        if value is None:
            self._dataset = value
        elif isinstance(value, BytesIO):
            self._dataset = value
        else:
            raise TypeError("DataSet must be a BytesIO object")

    @property
    def Status(self):
        """Return the *Status*."""
        return self._status

    @Status.setter
    def Status(self, value):
        """Set the *Status*."""
        if isinstance(value, int) or value is None:
            self._status = value
        else:
            raise TypeError("'C_STORE.Status' must be an int")

    @property
    def is_valid_request(self):
        """Return True if the C-STORE RQ is valid."""
        for keyword in ['MessageID', 'AffectedSOPClassUID', 'Priority',
                        'AffectedSOPInstanceUID', 'DataSet']:
            if getattr(self, keyword) is None:
                return False

        return True

    @property
    def is_valid_response(self):
        """Return True if the C-STORE RSP is valid."""
        for keyword in ['MessageIDBeingRespondedTo', 'Status']:
            if getattr(self, keyword) is None:
                return False

        return True


class C_FIND(object):
    """Represents a C-FIND primitive.

    **SOP Class UID**

    Identifies the QR Information Model against which the C-FIND is to be
    performed. Support for the SOP Class UID is implied by the Abstract Syntax
    UID of the Presentation Context used by this C-FIND operation.

    **Priority**

    The requested priority of the C-FIND operation with respect to other DIMSE
    operations being performed by the same SCP. Processing of priority requests
    is not required of SCPs. Whether or not an SCP supports priority processing
    and the meaning of different priority levels shall be stated in the
    Conformance Statement of the SCP.

    **Identifier**

    Encoded as a Data Set

    Request Identifier Structure

    * Key Attribute values to be matched against the values of storage SOP
      Instances managed by the SCP
    * QR Level (0008,0052) Query/Retrieve Level
    * Conditionally, (0008,0053) if enhanced multi frame image conversion
      accepted during Extended Negotiation
    * Conditionally, (0008,0005) if expanded or replacement character sets
      may be used in the request Identifier attributes
    * Conditionally, (0008,0201) if Key Attributes of time are to be
      interpreted explicitly in the designated local time zone

    Response Identifier Structure

    * Key Attribute with values corresponding to Key Attributes contained in
      the Identifier of the request
    * QR Level (0008, 0053)
    * Conditionally, (0008,0005) if expanded or replacement character sets
      may be used in the response Identifier attributes
    * Conditionally, (0008,0201) if Key Attributes of time are to be
      interpreted explicitly in the designated local time zone

    The C-FIND SCP is required to support either/both the 'Retrieve AE Title'
    (0008,0054) or the 'Storage Media File-Set ID'/'Storage Media File Set UID'
    (0088,0130)/(0088,0140) data elements.

    **Retrieve AE Title**

    A list of AE title(s) that identify the location from which the Instance
    may be retrieved on the network. Must be present if Storage Media File Set
    ID/UID not present. The named AE shall support either C-GET or C-MOVE
    SOP Class of the QR Service Class.

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

    | (=) - The value of the parameter is equal to the value of the parameter in
      the column to the left
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
        A list of Attributes (in the form of an encoded pydicom
        Dataset) to be matched against the values of the Attributes in the
        instances of the composite objects known to the performing DIMSE
        service-user.
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
    def MessageID(self):
        """Return the *Message ID*."""
        return self._message_id

    @MessageID.setter
    def MessageID(self, value):
        """Set the *Message ID*."""
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
        """Return the *Message ID Being Responded To*."""
        return self._message_id_being_responded_to

    @MessageIDBeingRespondedTo.setter
    def MessageIDBeingRespondedTo(self, value):
        """Set the *Message ID Being Responded To*."""
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
    def AffectedSOPClassUID(self):
        """Return the *Affected SOP Class UID*."""
        return self._affected_sop_class_uid

    @AffectedSOPClassUID.setter
    def AffectedSOPClassUID(self, value):
        """Set the *Affected SOP Class UID*.

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
            raise TypeError("Affected SOP Class UID must be a "
                            "pydicom.uid.UID, str or bytes")

        if value is not None and not value.is_valid:
            LOGGER.error("Affected SOP Class UID is an invalid UID")
            raise ValueError("Affected SOP Class UID is an invalid UID")

        self._affected_sop_class_uid = value

    @property
    def Priority(self):
        """Return the *Priority*."""
        return self._priority

    @Priority.setter
    def Priority(self, value):
        """Set the *Priority*."""
        if value in [0, 1, 2]:
            self._priority = value
        else:
            LOGGER.warning("Attempted to set C-FIND Priority parameter to an "
                           "invalid value")
            raise ValueError("Priority must be 0, 1, or 2")

    @property
    def Identifier(self):
        """Return the *Identifier*."""
        return self._identifier

    @Identifier.setter
    def Identifier(self, value):
        """Set the *Identifier*."""
        if value is None:
            self._identifier = value
        elif isinstance(value, BytesIO):
            self._identifier = value
        else:
            raise TypeError("Identifier must be a BytesIO object")

    @property
    def Status(self):
        """Return the *Status*."""
        return self._status

    @Status.setter
    def Status(self, value):
        """Set the *Status*."""
        if isinstance(value, int) or value is None:
            self._status = value
        else:
            raise TypeError("'C_FIND.Status' must be an int.")

    @property
    def is_valid_request(self):
        """Return True if the C-FIND RQ is valid."""
        for keyword in ['MessageID', 'AffectedSOPClassUID', 'Priority',
                        'Identifier']:
            if getattr(self, keyword) is None:
                return False

        return True

    @property
    def is_valid_response(self):
        """Return True if the C-FIND RSP is valid."""
        for keyword in ['MessageIDBeingRespondedTo', 'Status']:
            if getattr(self, keyword) is None:
                return False

        return True


class C_GET(object):
    """Represents a C-GET primitive.

    The C-GET service is used

    **C-GET Service Procedure**

    **Number of Remaining Sub-Operations**

    A C-GET response with a status of:

    * Pending shall contain the Number of Remaining Sub-operations Attribute
    * Canceled may contain the Number of Remaining Sub-operations Attribute
    * Warning, Failure or Success shall not contain the Number of Remaining
      Sub-operations Attribute

    **Number of Completed Sub-Operations**

    A C-GET response with a status of:

    * Pending shall contain the Number of Completed Sub-operations Attribute
    * Canceled, Warning, Failure or Success may contain the Number of Completed
      Sub-operations Attribute

    **Number of Failed Sub-Operations**

    A C-GET response with a status of:

    * Pending shall contain the Number of Failed Sub-operations Attribute
    * Canceled, Warning, Failure or Success may contain the Number of Failed
      Sub-operations Attribute

    **Number of Warning Sub-Operations**

    A C-GET response with a status of:

    * Pending shall contain the Number of Warning Sub-operations Attribute
    * Canceled, Warning, Failure or Success may contain the Number of Warning
      Sub-operations Attribute

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

    | (=) - The value of the parameter is equal to the value of the parameter in
      the column to the left
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
        The pydicom Dataset containing the list of Attributes to be
        matched against the values of Attributes of known composite SOP
        Instances of the performing DIMSE service-user, encoded as a BytesIO
        object. For the list of allowed Attributes and the rules defining their
        usage see the section corresponding to the service class in the DICOM
        Standard, Part 4.
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

    References
    ----------

    * DICOM Standard, Part 4, Annex C.4.3
    * DICOM Standard, Part 7, Section 9.1.3
    """
    STATUS_OPTIONAL_KEYWORDS = (
        'ErrorComment', 'OffendingElement', 'NumberOfRemainingSuboperations',
        'NumberOfCompletedSuboperations', 'NumberOfFailedSuboperations',
        'NumberOfWarningSuboperations'
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
    def MessageID(self):
        """Return the *Message ID*."""
        return self._message_id

    @MessageID.setter
    def MessageID(self, value):
        """Set the *Message ID*."""
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
        """Return the *Message ID Being Responded To*."""
        return self._message_id_being_responded_to

    @MessageIDBeingRespondedTo.setter
    def MessageIDBeingRespondedTo(self, value):
        """Set the *Message ID Being Responded To*."""
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
    def AffectedSOPClassUID(self):
        """Return the *Affected SOP Class UID*."""
        return self._affected_sop_class_uid

    @AffectedSOPClassUID.setter
    def AffectedSOPClassUID(self, value):
        """Set the *Affected SOP Class UID*.

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
            raise TypeError("Affected SOP Class UID must be a "
                            "pydicom.uid.UID, str or bytes")

        if value is not None and not value.is_valid:
            LOGGER.error("Affected SOP Class UID is an invalid UID")
            raise ValueError("Affected SOP Class UID is an invalid UID")

        self._affected_sop_class_uid = value

    @property
    def Priority(self):
        """Return the *Priority*."""
        return self._priority

    @Priority.setter
    def Priority(self, value):
        """Set the *Priority*."""
        if value in [0, 1, 2]:
            self._priority = value
        else:
            LOGGER.warning("Attempted to set C-FIND Priority parameter to an "
                           "invalid value")
            raise ValueError("Priority must be 0, 1, or 2")

    @property
    def Identifier(self):
        """Return the *Identifier*."""
        return self._identifier

    @Identifier.setter
    def Identifier(self, value):
        """Set the *Identifier*."""
        if value is None:
            self._identifier = value
        elif isinstance(value, BytesIO):
            self._identifier = value
        else:
            raise TypeError("Identifier must be a BytesIO object")

    @property
    def Status(self):
        """Return the *Status*."""
        return self._status

    @Status.setter
    def Status(self, value):
        """Set the *Status*."""
        if isinstance(value, int) or value is None:
            self._status = value
        else:
            raise TypeError("Status must be an int")

    @property
    def NumberOfRemainingSuboperations(self):
        """Return the *Number of Remaining Suboperations*."""
        return self._number_of_remaining_suboperations

    @NumberOfRemainingSuboperations.setter
    def NumberOfRemainingSuboperations(self, value):
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
    def NumberOfCompletedSuboperations(self):
        """Return the *Number of Completed Suboperations*."""
        return self._number_of_completed_suboperations

    @NumberOfCompletedSuboperations.setter
    def NumberOfCompletedSuboperations(self, value):
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
    def NumberOfFailedSuboperations(self):
        """Return the *Number of Failed Suboperations*."""
        return self._number_of_failed_suboperations

    @NumberOfFailedSuboperations.setter
    def NumberOfFailedSuboperations(self, value):
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
    def NumberOfWarningSuboperations(self):
        """Return the *Number of Warning Suboperations*."""
        return self._number_of_warning_suboperations

    @NumberOfWarningSuboperations.setter
    def NumberOfWarningSuboperations(self, value):
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
    def is_valid_request(self):
        """Return True if the C-GET RQ is valid."""
        for keyword in ['MessageID', 'AffectedSOPClassUID', 'Priority',
                        'Identifier']:
            if getattr(self, keyword) is None:
                return False

        return True

    @property
    def is_valid_response(self):
        """Return True if the C-GET RSP is valid."""
        for keyword in ['MessageIDBeingRespondedTo', 'Status']:
            if getattr(self, keyword) is None:
                return False

        return True


class C_MOVE(object):
    """Represents a C-MOVE primitive.

    The C-MOVE service is used

    **C-MOVE Service Procedure**

    **Number of Remaining Sub-Operations**

    A C-MOVE response with a status of:

    * Pending shall contain the Number of Remaining Sub-operations Attribute
    * Canceled may contain the Number of Remaining Sub-operations Attribute
    * Warning, Failure or Success shall not contain the Number of Remaining
      Sub-operations Attribute

    **Number of Completed Sub-Operations**

    A C-MOVE response with a status of:

    * Pending shall contain the Number of Completed Sub-operations Attribute
    * Canceled, Warning, Failure or Success may contain the Number of Completed
      Sub-operations Attribute

    **Number of Failed Sub-Operations**

    A C-MOVE response with a status of:

    * Pending shall contain the Number of Failed Sub-operations Attribute
    * Canceled, Warning, Failure or Success may contain the Number of Failed
      Sub-operations Attribute

    **Number of Warning Sub-Operations**

    A C-MOVE response with a status of:

    * Pending shall contain the Number of Warning Sub-operations Attribute
    * Canceled, Warning, Failure or Success may contain the Number of Warning
      Sub-operations Attribute

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

    | (=) - The value of the parameter is equal to the value of the parameter in
      the column to the left
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
        The pydicom Dataset containing the list of Attributes to be
        matched against the values of Attributes of known composite SOP
        Instances of the performing DIMSE service-user, encoded as a BytesIO
        object. For the list of allowed Attributes and the rules defining their
        usage see the section corresponding to the service class in the DICOM
        Standard, Part 4.
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

    References
    ----------

    * DICOM Standard, Part 4, Annex C.4.2
    * DICOM Standard, Part 7, Section 9.1.4
    """
    STATUS_OPTIONAL_KEYWORDS = (
        'ErrorComment', 'OffendingElement', 'NumberOfRemainingSuboperations',
        'NumberOfCompletedSuboperations', 'NumberOfFailedSuboperations',
        'NumberOfWarningSuboperations'
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
    def MessageID(self):
        """Return the *Message ID*."""
        return self._message_id

    @MessageID.setter
    def MessageID(self, value):
        """Set the *Message ID*."""
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
        """Return the *Message ID Being Responding To*."""
        return self._message_id_being_responded_to

    @MessageIDBeingRespondedTo.setter
    def MessageIDBeingRespondedTo(self, value):
        """Set the *Message ID Being Responding To*."""
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
    def AffectedSOPClassUID(self):
        """Return the *Affected SOP Class UID*."""
        return self._affected_sop_class_uid

    @AffectedSOPClassUID.setter
    def AffectedSOPClassUID(self, value):
        """Set the *Affected SOP Class UID*.

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
            raise TypeError("Affected SOP Class UID must be a "
                            "pydicom.uid.UID, str or bytes")

        if value is not None and not value.is_valid:
            LOGGER.error("Affected SOP Class UID is an invalid UID")
            raise ValueError("Affected SOP Class UID is an invalid UID")

        self._affected_sop_class_uid = value

    @property
    def Priority(self):
        """Return the *Priority*."""
        return self._priority

    @Priority.setter
    def Priority(self, value):
        """Set the *Priority*."""
        if value in [0, 1, 2]:
            self._priority = value
        else:
            LOGGER.warning("Attempted to set C-FIND Priority parameter to an "
                           "invalid value")
            raise ValueError("Priority must be 0, 1, or 2")

    @property
    def MoveDestination(self):
        """Return the *Move Destination*."""
        return self._move_destination

    @MoveDestination.setter
    def MoveDestination(self, value):
        """Set the *Move Destination*.

        Parameters
        ----------
        value : str or bytes
            The Move Destination AE Title as a string or bytes object. Cannot
            be an empty string and will be truncated to 16 characters long
        """
        if isinstance(value, str):
            value = codecs.encode(value, 'ascii')

        if value is not None:
            self._move_destination = validate_ae_title(value)
        else:
            self._move_destination = None

    @property
    def Identifier(self):
        """Return the *Identifier*."""
        return self._identifier

    @Identifier.setter
    def Identifier(self, value):
        """Set the *Identifier*."""
        if value is None:
            self._identifier = value
        elif isinstance(value, BytesIO):
            self._identifier = value
        else:
            raise TypeError("Identifier must be a BytesIO object")

    @property
    def Status(self):
        """Return the *Status*."""
        return self._status

    @Status.setter
    def Status(self, value):
        """Set the *Status*."""
        if isinstance(value, int) or value is None:
            self._status = value
        else:
            raise TypeError("Status must be an int")

    @property
    def NumberOfRemainingSuboperations(self):
        """Return the *Number of Remaining Suboperations*."""
        return self._number_of_remaining_suboperations

    @NumberOfRemainingSuboperations.setter
    def NumberOfRemainingSuboperations(self, value):
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
    def NumberOfCompletedSuboperations(self):
        """Return the *Number of Completed Suboperations*."""
        return self._number_of_completed_suboperations

    @NumberOfCompletedSuboperations.setter
    def NumberOfCompletedSuboperations(self, value):
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
    def NumberOfFailedSuboperations(self):
        """Return the *Number of Failed Suboperations*."""
        return self._number_of_failed_suboperations

    @NumberOfFailedSuboperations.setter
    def NumberOfFailedSuboperations(self, value):
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
    def NumberOfWarningSuboperations(self):
        """Return the *Number of Warning Suboperations*."""
        return self._number_of_warning_suboperations

    @NumberOfWarningSuboperations.setter
    def NumberOfWarningSuboperations(self, value):
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
    def is_valid_request(self):
        """Return True if the C-MOVE RQ is valid."""
        for keyword in ['MessageID', 'AffectedSOPClassUID', 'Priority',
                        'Identifier', 'MoveDestination']:
            if getattr(self, keyword) is None:
                return False

        return True

    @property
    def is_valid_response(self):
        """Return True if the C-MOVE RSP is valid."""
        for keyword in ['MessageIDBeingRespondedTo', 'Status']:
            if getattr(self, keyword) is None:
                return False

        return True


class C_ECHO(object):
    """Represents a C-ECHO primitive.

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

    | (=) - The value of the parameter is equal to the value of the parameter in
      the column to the left
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

    References
    ----------

    * DICOM Standard, Part 7, Section 9.1.5
    """
    STATUS_OPTIONAL_KEYWORDS = ('ErrorComment', )

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

    @property
    def MessageID(self):
        """Return the *Message ID*."""
        return self._message_id

    @MessageID.setter
    def MessageID(self, value):
        """Set the *Message ID*."""
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
        """Return the *Message ID Being Responded To*."""
        return self._message_id_being_responded_to

    @MessageIDBeingRespondedTo.setter
    def MessageIDBeingRespondedTo(self, value):
        """Set the *Message ID Being Responded To*."""
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
    def AffectedSOPClassUID(self):
        """Return the *Affected SOP Class UID*."""
        return self._affected_sop_class_uid

    @AffectedSOPClassUID.setter
    def AffectedSOPClassUID(self, value):
        """Set the *Affected SOP Class UID*.

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
            raise TypeError("Affected SOP Class UID must be a "
                            "pydicom.uid.UID, str or bytes")

        if value is not None and not value.is_valid:
            LOGGER.error("Affected SOP Class UID is an invalid UID")
            raise ValueError("Affected SOP Class UID is an invalid UID")

        self._affected_sop_class_uid = value

    @property
    def Status(self):
        """Return the *Status*."""
        return self._status

    @Status.setter
    def Status(self, value):
        """Set the *Status*."""
        if isinstance(value, int) or value is None:
            self._status = value
        else:
            raise TypeError("'C_ECHO.Status' must be an int.")

    @property
    def is_valid_request(self):
        """Return True if the C-ECHO RQ is valid."""
        for keyword in ['MessageID', 'AffectedSOPClassUID']:
            if getattr(self, keyword) is None:
                return False

        return True

    @property
    def is_valid_response(self):
        """Return True if the C-ECHO RSP is valid."""
        for keyword in ['MessageIDBeingRespondedTo', 'Status']:
            if getattr(self, keyword) is None:
                return False

        return True


class C_CANCEL(object):
    """Represents a C-CANCEL primitive.

    +-------------------------------+---------+
    | Parameter                     | Req/ind |
    +===============================+=========+
    | Message ID Being Responded To | M       |
    +-------------------------------+---------+

    | (=) - The value of the parameter is equal to the value of the parameter in
      the column to the left
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

    * DICOM Standard, Part 7, Section 9.3.2.3-4
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
        """Return the *Message ID Being Responded To*."""
        return self._message_id_being_responded_to

    @MessageIDBeingRespondedTo.setter
    def MessageIDBeingRespondedTo(self, value):
        """Set the *Message ID Being Responded To*."""
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


# DIMSE-N Services
class N_EVENT_REPORT(object):
    """Represents a N-EVENT-REPORT primitive.

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

    | (=) - The value of the parameter is equal to the value of the parameter in
      the column to the left
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
        the event. An encoded DICOM Dataset containing additional Service
        Class specific information related to the operation.
    EventReply : io.BytesIO
        Contains the optional reply to the event report. An encoded DICOM
        Dataset containing additional Service Class specific information.
    Status : int
        The error or success notification of the operation.
    """
    # Optional status element keywords other than 'Status'
    STATUS_OPTIONAL_KEYWORDS = (
        'AffectedSOPClassUID', 'AffectedSOPInstanceUID', 'EventTypeID',
        'EventInformation', 'ErrorComment', 'ErrorID'
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
    def AffectedSOPClassUID(self):
        """Return the *Affected SOP Class UID*."""
        return self._affected_sop_class_uid

    @AffectedSOPClassUID.setter
    def AffectedSOPClassUID(self, value):
        """Set the *Affected SOP Class UID*.

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
            raise TypeError("Affected SOP Class UID must be a "
                            "pydicom.uid.UID, str or bytes")

        if value is not None and not value.is_valid:
            LOGGER.error("Affected SOP Class UID is an invalid UID")
            raise ValueError("Affected SOP Class UID is an invalid UID")

        self._affected_sop_class_uid = value

    @property
    def AffectedSOPInstanceUID(self):
        """Return the *Affected SOP Instance UID*."""
        return self._affected_sop_instance_uid

    @AffectedSOPInstanceUID.setter
    def AffectedSOPInstanceUID(self, value):
        """Set the *Affected SOP Instance UID*.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The value for the Affected SOP Instance UID
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

        if value is not None and not value.is_valid:
            LOGGER.error("Affected SOP Instance UID is an invalid UID")
            raise ValueError("Affected SOP Instance UID is an invalid UID")

        self._affected_sop_instance_uid = value

    @property
    def EventInformation(self):
        """Return the *Event Information*."""
        return self._event_info

    @EventInformation.setter
    def EventInformation(self, value):
        """Set the *Event Information*."""
        if value is None:
            self._event_info = value
        elif isinstance(value, BytesIO):
            self._event_info = value
        else:
            raise TypeError("EventInformation must be a BytesIO object")

    @property
    def EventReply(self):
        """Return the *Event Reply*."""
        return self._event_reply

    @EventReply.setter
    def EventReply(self, value):
        """Set the *Event Reply*."""
        if value is None:
            self._event_reply = value
        elif isinstance(value, BytesIO):
            self._event_reply = value
        else:
            raise TypeError("EventReply must be a BytesIO object")

    @property
    def EventTypeID(self):
        """Return the *Event Type ID*."""
        return self._event_type_id

    @EventTypeID.setter
    def EventTypeID(self, value):
        """Set the *Event Type ID*."""
        if isinstance(value, int) or value is None:
            self._event_type_id = value
        else:
            raise TypeError("'N_EVENT_REPORT.EventTypeID' must be an int.")

    @property
    def is_valid_request(self):
        """Return True if the N-EVENT-REPORT RQ is valid."""
        for keyword in ['MessageID', 'AffectedSOPClassUID', 'EventTypeID',
                        'AffectedSOPInstanceUID']:
            if getattr(self, keyword) is None:
                return False

        return True

    @property
    def is_valid_response(self):
        """Return True if the N-EVENT-REPORT RSP is valid."""
        for keyword in ['MessageIDBeingRespondedTo', 'Status']:
            if getattr(self, keyword) is None:
                return False

        return True

    @property
    def MessageID(self):
        """Return the *Message ID*."""
        return self._message_id

    @MessageID.setter
    def MessageID(self, value):
        """Set the *Message ID*."""
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
        """Return the *Message ID Being Responded To*."""
        return self._message_id_being_responded_to

    @MessageIDBeingRespondedTo.setter
    def MessageIDBeingRespondedTo(self, value):
        """Set the *Message ID Being Responded To*."""
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
    def Status(self):
        """Return the *Status*."""
        return self._status

    @Status.setter
    def Status(self, value):
        """Set the *Status*."""
        if isinstance(value, int) or value is None:
            self._status = value
        else:
            raise TypeError("'N_EVENT_REPORT.Status' must be an int.")


class N_GET(object):
    """Represents an N-GET primitive.

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
        A dataset containing elements matching those supplied in
        AttributeIdentifierList.
    Status : int
        The error or success notification of the operation.

    References
    ----------

    DICOM Standard, Part 7, Section 10.1.2
    """
    STATUS_OPTIONAL_KEYWORDS = ('ErrorComment', 'ErrorID', )

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
    def AffectedSOPClassUID(self):
        """Return the *Affected SOP Class UID*."""
        return self._affected_sop_class_uid

    @AffectedSOPClassUID.setter
    def AffectedSOPClassUID(self, value):
        """Set the *Affected SOP Class UID*.

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
            raise TypeError("Affected SOP Class UID must be a "
                            "pydicom.uid.UID, str or bytes")

        if value is not None and not value.is_valid:
            LOGGER.error("Affected SOP Class UID is an invalid UID")
            raise ValueError("Affected SOP Class UID is an invalid UID")

        self._affected_sop_class_uid = value

    @property
    def AffectedSOPInstanceUID(self):
        """Return the *Affected SOP Instance UID*."""
        return self._affected_sop_instance_uid

    @AffectedSOPInstanceUID.setter
    def AffectedSOPInstanceUID(self, value):
        """Set the *Affected SOP Instance UID*.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The value for the Affected SOP Instance UID
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

        if value is not None and not value.is_valid:
            LOGGER.error("Affected SOP Instance UID is an invalid UID")
            raise ValueError("Affected SOP Instance UID is an invalid UID")

        self._affected_sop_instance_uid = value

    @property
    def AttributeIdentifierList(self):
        """Return the value of (0000,1005) *Attribute Identifier List*."""
        return self._attribute_identifier_list

    @AttributeIdentifierList.setter
    def AttributeIdentifierList(self, value):
        """Set the value of (0000,1005) *Attribute Identifier List*.

        Parameters
        ----------
        value : list of pydicom.tag.Tag
            A list of pydicom Tags or any values acceptable for creating a new
            pydicom Tag object.
        """
        if value:
            if not isinstance(value, (list, MutableSequence)):
                value = [value]
            try:
                self._attribute_identifier_list = [Tag(tag) for tag in value]
            except (TypeError, ValueError):
                raise ValueError(
                    "Attribute Identifier List must be a list of pydicom Tags"
                )
        elif value is None:
            self._attribute_identifier_list = None
        else:
            raise ValueError(
                "Attribute Identifier List must be a list of pydicom Tags"
            )

    @property
    def AttributeList(self):
        """Return the *Attribute List*."""
        return self._attribute_list

    @AttributeList.setter
    def AttributeList(self, value):
        """Set the *Attribute List*."""
        if value is None:
            self._attribute_list = value
        elif isinstance(value, BytesIO):
            self._attribute_list = value
        else:
            raise TypeError("AttributeList must be a BytesIO object")

    @property
    def is_valid_request(self):
        """Return True if the N-GET RQ is valid."""
        for keyword in ['MessageID', 'RequestedSOPClassUID',
                        'RequestedSOPInstanceUID']:
            if getattr(self, keyword) is None:
                return False

        return True

    @property
    def is_valid_response(self):
        """Return True if the N-GET RSP is valid."""
        for keyword in ['MessageIDBeingRespondedTo', 'Status']:
            if getattr(self, keyword) is None:
                return False

        return True

    @property
    def MessageID(self):
        """Return the *Message ID*."""
        return self._message_id

    @MessageID.setter
    def MessageID(self, value):
        """Set the *Message ID*."""
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
        """Return the *Message ID Being Responded To*."""
        return self._message_id_being_responded_to

    @MessageIDBeingRespondedTo.setter
    def MessageIDBeingRespondedTo(self, value):
        """Set the *Message ID Being Responded To*."""
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
    def RequestedSOPClassUID(self):
        """Return the *Requested SOP Class UID*."""
        return self._requested_sop_class_uid

    @RequestedSOPClassUID.setter
    def RequestedSOPClassUID(self, value):
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

        if value is not None and not value.is_valid:
            LOGGER.error("Requested SOP Class UID is an invalid UID")
            raise ValueError("Requested SOP Class UID is an invalid UID")

        self._requested_sop_class_uid = value

    @property
    def RequestedSOPInstanceUID(self):
        """Return the *Requested SOP Instance UID*."""
        return self._requested_sop_instance_uid

    @RequestedSOPInstanceUID.setter
    def RequestedSOPInstanceUID(self, value):
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

        if value is not None and not value.is_valid:
            LOGGER.error("Requested SOP Instance UID is an invalid UID")
            raise ValueError("Requested SOP Instance UID is an invalid UID")

        self._requested_sop_instance_uid = value

    @property
    def Status(self):
        """Return the *Status*."""
        return self._status

    @Status.setter
    def Status(self, value):
        """Set the *Status*."""
        if isinstance(value, int) or value is None:
            self._status = value
        else:
            raise TypeError("'N_GET.Status' must be an int.")


class N_SET(object):
    """Represents a N-SET primitive.

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

    | (=) - The value of the parameter is equal to the value of the parameter in
      the column to the left
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
    ModificationList : pydicom.dataset.Dataset
        A dataset containing the attributes and values that are to be used
        to modify the SOP Instance.
    AttributeList : pydicom.dataset.Dataset
        A dataset containing the attributes and values that were used to
        modify the SOP Instance.
    AffectedSOPClassUID : pydicom.uid.UID, bytes or str
        The SOP Class UID of the modified SOP Instance.
    AffectedSOPInstanceUID : pydicom.uid.UID, bytes or str
        The SOP Instance UID of the modified SOP Instance.
    Status : int
        The error or success notification of the operation.

    References
    ----------

    DICOM Standard, Part 7, Section 10.1.3
    """
    STATUS_OPTIONAL_KEYWORDS = (
        'ErrorComment', 'ErrorID', 'AttributeIdentifierList'
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
    def AffectedSOPClassUID(self):
        """Return the *Affected SOP Class UID*."""
        return self._affected_sop_class_uid

    @AffectedSOPClassUID.setter
    def AffectedSOPClassUID(self, value):
        """Set the *Affected SOP Class UID*.

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
            raise TypeError("Affected SOP Class UID must be a "
                            "pydicom.uid.UID, str or bytes")

        if value is not None and not value.is_valid:
            LOGGER.error("Affected SOP Class UID is an invalid UID")
            raise ValueError("Affected SOP Class UID is an invalid UID")

        self._affected_sop_class_uid = value

    @property
    def AffectedSOPInstanceUID(self):
        """Return the *Affected SOP Instance UID*."""
        return self._affected_sop_instance_uid

    @AffectedSOPInstanceUID.setter
    def AffectedSOPInstanceUID(self, value):
        """Set the *Affected SOP Instance UID*.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The value for the Affected SOP Instance UID
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

        if value is not None and not value.is_valid:
            LOGGER.error("Affected SOP Instance UID is an invalid UID")
            raise ValueError("Affected SOP Instance UID is an invalid UID")

        self._affected_sop_instance_uid = value

    @property
    def AttributeList(self):
        """Return the *Attribute List*."""
        return self._attribute_list

    @AttributeList.setter
    def AttributeList(self, value):
        """Set the *Attribute List*."""
        if value is None:
            self._attribute_list = value
        elif isinstance(value, BytesIO):
            self._attribute_list = value
        else:
            raise TypeError("AttributeList must be a BytesIO object")

    @property
    def is_valid_request(self):
        """Return True if the N-SET RQ is valid."""
        for keyword in ['MessageID', 'RequestedSOPClassUID',
                        'RequestedSOPInstanceUID', 'ModificationList']:
            if getattr(self, keyword) is None:
                return False

        return True

    @property
    def is_valid_response(self):
        """Return True if the N-SET RSP is valid."""
        for keyword in ['MessageIDBeingRespondedTo', 'Status']:
            if getattr(self, keyword) is None:
                return False

        return True

    @property
    def MessageID(self):
        """Return the *Message ID*."""
        return self._message_id

    @MessageID.setter
    def MessageID(self, value):
        """Set the *Message ID*."""
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
        """Return the *Message ID Being Responded To*."""
        return self._message_id_being_responded_to

    @MessageIDBeingRespondedTo.setter
    def MessageIDBeingRespondedTo(self, value):
        """Set the *Message ID Being Responded To*."""
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
    def ModificationList(self):
        """Return the *Modification List*."""
        return self._modification_list

    @ModificationList.setter
    def ModificationList(self, value):
        """Set the *Modification List*."""
        if value is None:
            self._modification_list = value
        elif isinstance(value, BytesIO):
            self._modification_list = value
        else:
            raise TypeError("ModificationList must be a BytesIO object")

    @property
    def RequestedSOPClassUID(self):
        """Return the *Requested SOP Class UID*."""
        return self._requested_sop_class_uid

    @RequestedSOPClassUID.setter
    def RequestedSOPClassUID(self, value):
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

        if value is not None and not value.is_valid:
            LOGGER.error("Requested SOP Class UID is an invalid UID")
            raise ValueError("Requested SOP Class UID is an invalid UID")

        self._requested_sop_class_uid = value

    @property
    def RequestedSOPInstanceUID(self):
        """Return the *Requested SOP Instance UID*."""
        return self._requested_sop_instance_uid

    @RequestedSOPInstanceUID.setter
    def RequestedSOPInstanceUID(self, value):
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

        if value is not None and not value.is_valid:
            LOGGER.error("Requested SOP Instance UID is an invalid UID")
            raise ValueError("Requested SOP Instance UID is an invalid UID")

        self._requested_sop_instance_uid = value

    @property
    def Status(self):
        """Return the *Status*."""
        return self._status

    @Status.setter
    def Status(self, value):
        """Set the *Status*."""
        if isinstance(value, int) or value is None:
            self._status = value
        else:
            raise TypeError("'N_SET.Status' must be an int.")


class N_ACTION(object):
    """Represents a N-ACTION primitive.

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

    | (=) - The value of the parameter is equal to the value of the parameter in
      the column to the left
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
    ActionInformation : pydicom.dataset.Dataset
        Extra information required to perform the action.
    AffectedSOPClassUID : pydicom.uid.UID, bytes or str
        For the request/indication this specifies the SOP Class for
        storage. If included in the response/confirmation, it shall be equal
        to the value in the request/indication
    AffectedSOPInstanceUID : pydicom.uid.UID, bytes or str
        For the request/indication this specifies the SOP Instance for
        storage. If included in the response/confirmation, it shall be equal
        to the value in the request/indication
    ActionReply : pydicom.dataset.Dataset
        The reply to the action.
    Status : int
        The error or success notification of the operation.
    """
    STATUS_OPTIONAL_KEYWORDS = (
        'ErrorComment', 'ErrorID', 'AttributeIdentifierList'
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
    def AffectedSOPClassUID(self):
        """Return the *Affected SOP Class UID*."""
        return self._affected_sop_class_uid

    @AffectedSOPClassUID.setter
    def AffectedSOPClassUID(self, value):
        """Set the *Affected SOP Class UID*.

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
            raise TypeError("Affected SOP Class UID must be a "
                            "pydicom.uid.UID, str or bytes")

        if value is not None and not value.is_valid:
            LOGGER.error("Affected SOP Class UID is an invalid UID")
            raise ValueError("Affected SOP Class UID is an invalid UID")

        self._affected_sop_class_uid = value

    @property
    def AffectedSOPInstanceUID(self):
        """Return the *Affected SOP Instance UID*."""
        return self._affected_sop_instance_uid

    @AffectedSOPInstanceUID.setter
    def AffectedSOPInstanceUID(self, value):
        """Set the *Affected SOP Instance UID*.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The value for the Affected SOP Instance UID
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

        if value is not None and not value.is_valid:
            LOGGER.error("Affected SOP Instance UID is an invalid UID")
            raise ValueError("Affected SOP Instance UID is an invalid UID")

        self._affected_sop_instance_uid = value

    @property
    def ActionInformation(self):
        """Return the *Action Information*."""
        return self._action_info

    @ActionInformation.setter
    def ActionInformation(self, value):
        """Set the *Action Information*."""
        if value is None:
            self._action_info = value
        elif isinstance(value, BytesIO):
            self._action_info = value
        else:
            raise TypeError("ActionInformation must be a BytesIO object")

    @property
    def is_valid_request(self):
        """Return True if the N-ACTION RQ is valid."""
        for keyword in ['MessageID', 'RequestedSOPClassUID',
                        'RequestedSOPInstanceUID', 'ActionTypeID']:
            if getattr(self, keyword) is None:
                return False

        return True

    @property
    def is_valid_response(self):
        """Return True if the N-ACTION RSP is valid."""
        for keyword in ['MessageIDBeingRespondedTo', 'Status']:
            if getattr(self, keyword) is None:
                return False

        return True

    @property
    def MessageID(self):
        """Return the *Message ID*."""
        return self._message_id

    @MessageID.setter
    def MessageID(self, value):
        """Set the *Message ID*."""
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
        """Return the *Message ID Being Responded To*."""
        return self._message_id_being_responded_to

    @MessageIDBeingRespondedTo.setter
    def MessageIDBeingRespondedTo(self, value):
        """Set the *Message ID Being Responded To*."""
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
    def ActionReply(self):
        """Return the *Action Reply*."""
        return self._action_reply

    @ActionReply.setter
    def ActionReply(self, value):
        """Set the *Action Reply List*."""
        if value is None:
            self._action_reply = value
        elif isinstance(value, BytesIO):
            self._action_reply = value
        else:
            raise TypeError("ActionReply must be a BytesIO object")

    @property
    def RequestedSOPClassUID(self):
        """Return the *Requested SOP Class UID*."""
        return self._requested_sop_class_uid

    @RequestedSOPClassUID.setter
    def RequestedSOPClassUID(self, value):
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

        if value is not None and not value.is_valid:
            LOGGER.error("Requested SOP Class UID is an invalid UID")
            raise ValueError("Requested SOP Class UID is an invalid UID")

        self._requested_sop_class_uid = value

    @property
    def RequestedSOPInstanceUID(self):
        """Return the *Requested SOP Instance UID*."""
        return self._requested_sop_instance_uid

    @RequestedSOPInstanceUID.setter
    def RequestedSOPInstanceUID(self, value):
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

        if value is not None and not value.is_valid:
            LOGGER.error("Requested SOP Instance UID is an invalid UID")
            raise ValueError("Requested SOP Instance UID is an invalid UID")

        self._requested_sop_instance_uid = value

    @property
    def Status(self):
        """Return the *Status*."""
        return self._status

    @Status.setter
    def Status(self, value):
        """Set the *Status*."""
        if isinstance(value, int) or value is None:
            self._status = value
        else:
            raise TypeError("'N_ACTION.Status' must be an int.")

    @property
    def ActionTypeID(self):
        """Return the *Action Type ID*."""
        return self._action_type_id

    @ActionTypeID.setter
    def ActionTypeID(self, value):
        """Set the *Action Type ID*."""
        if isinstance(value, int) or value is None:
            self._action_type_id = value
        else:
            raise TypeError("'N_ACTION.ActionTypeID' must be an int.")


class N_CREATE(object):
    """Represents a N-CREATE primitive.

    +------------------------------------------+---------+----------+
    | Parameter                                | Req/ind | Rsp/conf |
    +==========================================+=========+==========+
    | Message ID                               | M       | \-       |
    +------------------------------------------+---------+----------+
    +------------------------------------------+---------+----------+
    | Message ID Being Responded To            | \-      | M        |
    | Affected SOP Class UID                   | M       | U(=)     |
    +------------------------------------------+---------+----------+
    | Affected SOP Instance UID                | U       | C        |
    +------------------------------------------+---------+----------+
    | Affected SOP Instance UID                | U       | U        |
    +------------------------------------------+---------+----------+
    | Status                                   | \-      | M        |
    +------------------------------------------+---------+----------+

    | (=) - The value of the parameter is equal to the value of the parameter in
      the column to the left
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
    AttributeList : pydicom.dataset.Dataset
        A set of attributes and values that are to be assigned to the new
        SOP Instance.
    Status : int
        The error or success notification of the operation. It shall be
        one of the following values:
    """
    STATUS_OPTIONAL_KEYWORDS = ('ErrorComment', 'ErrorID', )

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
    def AffectedSOPClassUID(self):
        """Return the *Affected SOP Class UID*."""
        return self._affected_sop_class_uid

    @AffectedSOPClassUID.setter
    def AffectedSOPClassUID(self, value):
        """Set the *Affected SOP Class UID*.

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
            raise TypeError("Affected SOP Class UID must be a "
                            "pydicom.uid.UID, str or bytes")

        if value is not None and not value.is_valid:
            LOGGER.error("Affected SOP Class UID is an invalid UID")
            raise ValueError("Affected SOP Class UID is an invalid UID")

        self._affected_sop_class_uid = value

    @property
    def AffectedSOPInstanceUID(self):
        """Return the *Affected SOP Instance UID*."""
        return self._affected_sop_instance_uid

    @AffectedSOPInstanceUID.setter
    def AffectedSOPInstanceUID(self, value):
        """Set the *Affected SOP Instance UID*.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The value for the Affected SOP Instance UID
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

        if value is not None and not value.is_valid:
            LOGGER.error("Affected SOP Instance UID is an invalid UID")
            raise ValueError("Affected SOP Instance UID is an invalid UID")

        self._affected_sop_instance_uid = value

    @property
    def AttributeList(self):
        """Return the *Attribute List*."""
        return self._attribute_list

    @AttributeList.setter
    def AttributeList(self, value):
        """Set the *Attribute List*."""
        if value is None:
            self._attribute_list = value
        elif isinstance(value, BytesIO):
            self._attribute_list = value
        else:
            raise TypeError("AttributeList must be a BytesIO object")

    @property
    def is_valid_request(self):
        """Return True if the N-CREATE RQ is valid."""
        for keyword in ['MessageID', 'AffectedSOPClassUID']:
            if getattr(self, keyword) is None:
                return False

        return True

    @property
    def is_valid_response(self):
        """Return True if the N-CREATE RSP is valid."""
        for keyword in ['MessageIDBeingRespondedTo', 'Status']:
            if getattr(self, keyword) is None:
                return False

        return True

    @property
    def MessageID(self):
        """Return the *Message ID*."""
        return self._message_id

    @MessageID.setter
    def MessageID(self, value):
        """Set the *Message ID*."""
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
        """Return the *Message ID Being Responded To*."""
        return self._message_id_being_responded_to

    @MessageIDBeingRespondedTo.setter
    def MessageIDBeingRespondedTo(self, value):
        """Set the *Message ID Being Responded To*."""
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
    def Status(self):
        """Return the *Status*."""
        return self._status

    @Status.setter
    def Status(self, value):
        """Set the *Status*."""
        if isinstance(value, int) or value is None:
            self._status = value
        else:
            raise TypeError("'N_CREATE.Status' must be an int.")


class N_DELETE(object):
    """Represents a N-DELETE primitive.

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

    References
    ----------

    DICOM Standard Part 7, Sections 10.1.6 and 10.3.6.
    """
    STATUS_OPTIONAL_KEYWORDS = ('ErrorComment', 'ErrorID', )

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
    def AffectedSOPClassUID(self):
        """Return the *Affected SOP Class UID*."""
        return self._affected_sop_class_uid

    @AffectedSOPClassUID.setter
    def AffectedSOPClassUID(self, value):
        """Set the *Affected SOP Class UID*.

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
            raise TypeError("Affected SOP Class UID must be a "
                            "pydicom.uid.UID, str or bytes")

        if value is not None and not value.is_valid:
            LOGGER.error("Affected SOP Class UID is an invalid UID")
            raise ValueError("Affected SOP Class UID is an invalid UID")

        self._affected_sop_class_uid = value

    @property
    def AffectedSOPInstanceUID(self):
        """Return the *Affected SOP Instance UID*."""
        return self._affected_sop_instance_uid

    @AffectedSOPInstanceUID.setter
    def AffectedSOPInstanceUID(self, value):
        """Set the *Affected SOP Instance UID*.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The value for the Affected SOP Instance UID
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

        if value is not None and not value.is_valid:
            LOGGER.error("Affected SOP Instance UID is an invalid UID")
            raise ValueError("Affected SOP Instance UID is an invalid UID")

        self._affected_sop_instance_uid = value

    @property
    def is_valid_request(self):
        """Return True if the N-DELETE RQ is valid."""
        for keyword in ['MessageID', 'RequestedSOPClassUID',
                        'RequestedSOPInstanceUID']:
            if getattr(self, keyword) is None:
                return False

        return True

    @property
    def is_valid_response(self):
        """Return True if the N-DELETE RSP is valid."""
        for keyword in ['MessageIDBeingRespondedTo', 'Status']:
            if getattr(self, keyword) is None:
                return False

        return True

    @property
    def MessageID(self):
        """Return the *Message ID*."""
        return self._message_id

    @MessageID.setter
    def MessageID(self, value):
        """Set the *Message ID*."""
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
        """Return the *Message ID Being Responded To*."""
        return self._message_id_being_responded_to

    @MessageIDBeingRespondedTo.setter
    def MessageIDBeingRespondedTo(self, value):
        """Set the *Message ID Being Responded To*."""
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
    def RequestedSOPClassUID(self):
        """Return the *Requested SOP Class UID*."""
        return self._requested_sop_class_uid

    @RequestedSOPClassUID.setter
    def RequestedSOPClassUID(self, value):
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

        if value is not None and not value.is_valid:
            LOGGER.error("Requested SOP Class UID is an invalid UID")
            raise ValueError("Requested SOP Class UID is an invalid UID")

        self._requested_sop_class_uid = value

    @property
    def RequestedSOPInstanceUID(self):
        """Return the *Requested SOP Instance UID*."""
        return self._requested_sop_instance_uid

    @RequestedSOPInstanceUID.setter
    def RequestedSOPInstanceUID(self, value):
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

        if value is not None and not value.is_valid:
            LOGGER.error("Requested SOP Instance UID is an invalid UID")
            raise ValueError("Requested SOP Instance UID is an invalid UID")

        self._requested_sop_instance_uid = value

    @property
    def Status(self):
        """Return the *Status*."""
        return self._status

    @Status.setter
    def Status(self, value):
        """Set the *Status*."""
        if isinstance(value, int) or value is None:
            self._status = value
        else:
            raise TypeError("'N_DELETE.Status' must be an int.")
