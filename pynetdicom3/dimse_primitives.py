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
from io import BytesIO
import logging

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

    PS3.4 Annex B
    PS3.7 9.1.1

    Attributes
    ----------
    MessageID : int
        [M, U] Identifies the operation and is used to distinguish this
        operation from other notifications or operations that may be in
        progress. No two identical values for the Message ID shall be used for
        outstanding operations.
    MessageIDBeingRespondedTo : int
        [-, M] The Message ID of the operation request/indication to which this
        response/confirmation applies.
    AffectedSOPClassUID : pydicom.uid.UID, bytes or str
        [M, U(=)] For the request/indication this specifies the SOP Class for
        storage. If included in the response/confirmation, it shall be equal
        to the value in the request/indication
    AffectedSOPInstanceUID : pydicom.uid.UID, bytes or str
        [M, U(=)] For the request/indication this specifies the SOP Instance
        for storage. If included in the response/confirmation, it shall be
        equal to the value in the request/indication
    Priority : int
        [M, -] The priority of the C-STORE operation. It shall be one of the
        following:
        * 0: Medium
        * 1: High
        * 2: Low (Default)
    MoveOriginatorApplicationEntityTitle : bytes or str
        [U, -] The DICOM AE Title of the AE that invoked the C-MOVE operation
        from which this C-STORE sub-operation is being performed
    MoveOriginatorMessageID : int
        [U, -] The Message ID of the C-MOVE request/indication primitive from
        which this C-STORE sub-operation is being performed
    DataSet : io.BytesIO
        [M, -] The pydicom Dataset containing the Attributes of the Composite
        SOP Instance to be stored, encoded as a BytesIO object
    Status : int
        [-, M] The error or success notification of the operation.
    OffendingElement : list of int or None
        [-, C] An optional status related field containing a list of the
        elements in which an error was detected.
    ErrorComment : str or None
        [-, C] An optional status related field containing a text description
        of the error detected. 64 characters maximum.
    """

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
        """Return the DIMSE message ID parameter."""
        return self._message_id

    @MessageID.setter
    def MessageID(self, value):
        """Set the DIMSE message ID parameter."""
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
        """Return the Message ID Being Responded To parameter."""
        return self._message_id_being_responded_to

    @MessageIDBeingRespondedTo.setter
    def MessageIDBeingRespondedTo(self, value):
        """Set the Message ID Being Responded To parameter."""
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
        """Return the AffectedSOPClassUID parameter."""
        return self._affected_sop_class_uid

    @AffectedSOPClassUID.setter
    def AffectedSOPClassUID(self, value):
        """Set the Affected SOP Class UID parameter.

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
            value = UID(value.decode('utf-8'))
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
        """Return the Affected SOP Instance UID parameter."""
        return self._affected_sop_instance_uid

    @AffectedSOPInstanceUID.setter
    def AffectedSOPInstanceUID(self, value):
        """Set the Affected SOP Instance UID parameter.

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
            value = UID(value.decode('utf-8'))
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
        """Return the Priority parameter."""
        return self._priority

    @Priority.setter
    def Priority(self, value):
        """Set the Priority parameter."""
        if value in [0, 1, 2]:
            self._priority = value
        else:
            LOGGER.warning("Attempted to set C-STORE Priority parameter to "
                           "an invalid value")
            raise ValueError("C-STORE Priority must be 0, 1, or 2")

    @property
    def MoveOriginatorApplicationEntityTitle(self):
        """Return the Move Originator AE Title parameter."""
        return self._move_originator_application_entity_title

    @MoveOriginatorApplicationEntityTitle.setter
    def MoveOriginatorApplicationEntityTitle(self, value):
        """Set the Move Originator AE Title parameter.

        Parameters
        ----------
        value : str or bytes
            The Move Originator AE Title as a string or bytes object. Cannot be
            an empty string and will be truncated to 16 characters long
        """
        if isinstance(value, str):
            value = codecs.encode(value, 'utf-8')

        if value is not None:
            self._move_originator_application_entity_title = \
                validate_ae_title(value)
        else:
            self._move_originator_application_entity_title = None

    @property
    def MoveOriginatorMessageID(self):
        """Return the Move Originator Message ID parameter."""
        return self._move_originator_message_id

    @MoveOriginatorMessageID.setter
    def MoveOriginatorMessageID(self, value):
        """Set the Move Originator Message ID parameter."""
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
        """Return the Data Set parameter."""
        return self._dataset

    @DataSet.setter
    def DataSet(self, value):
        """Set the Data Set parameter."""
        if value is None:
            self._dataset = value
        elif isinstance(value, BytesIO):
            self._dataset = value
        else:
            raise TypeError("DataSet must be a BytesIO object")

    @property
    def Status(self):
        """Return the Status parameter."""
        return self._status

    @Status.setter
    def Status(self, value):
        """Set the Status parameter."""
        if isinstance(value, int) or value is None:
            self._status = value
        else:
            raise TypeError("'C_STORE.Status' must be an int")

    @property
    def is_valid_request(self):
        """Return True if the required parameters for a C-ECHO RQ are set."""
        for keyword in ['MessageID', 'AffectedSOPClassUID', 'Priority',
                        'AffectedSOPInstanceUID', 'DataSet']:
            if getattr(self, keyword) is None:
                return False

        return True

    @property
    def is_valid_response(self):
        """Return True if the required parameters for a C-ECHO RSP are set."""
        for keyword in ['MessageIDBeingRespondedTo', 'Status']:
            if getattr(self, keyword) is None:
                return False

        return True


class C_FIND(object):
    """Represents a C-FIND primitive.

    PS3.4 Annex C.4.1.1
    PS3.4 9.1.2

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

    Attributes
    ----------
    MessageID : int
        [M, U, -] Identifies the operation and is used to distinguish this
        operation from other notifications or operations that may be in
        progress. No two identical values for the Message ID shall be used for
        outstanding operations.
    MessageIDBeingRespondedTo : int
        [-, M, M] The Message ID of the operation request/indication to which
        this response/confirmation applies.
    AffectedSOPClassUID : pydicom.uid.UID, bytes or str
        [M, U(=), -] For the request/indication this specifies the SOP Class
        for storage. If included in the response/confirmation, it shall be
        equal to the value in the request/indication
    Priority : int
        [M, -, -] The priority of the C-STORE operation. It shall be one of the
        following:
        * 0: Medium
        * 1: High
        * 2: Low (Default)
    Identifier : io.BytesIO
        [M, C, -] A list of Attributes (in the form of an encoded pydicom
        Dataset) to be matched against the values of the Attributes in the
        instances of the composite objects known to the performing DIMSE
        service-user
    Status : int
        [-, M, -] The error or success notification of the operation.
    OffendingElement : list of int or None
        [-, C, -] An optional status related field containing a list of the
        elements in which an error was detected.
    ErrorComment : str or None
        [-, C, -] An optional status related field containing a text
        description of the error detected. 64 characters maximum.
    """

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
        """Return the Message ID parameter."""
        return self._message_id

    @MessageID.setter
    def MessageID(self, value):
        """Set the Message ID parameter."""
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
        """Return the Message ID Being Responded To parameter."""
        return self._message_id_being_responded_to

    @MessageIDBeingRespondedTo.setter
    def MessageIDBeingRespondedTo(self, value):
        """Set the Message ID Being Responded To parameter."""
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
        """Return the Affected SOP Class UID parameter."""
        return self._affected_sop_class_uid

    @AffectedSOPClassUID.setter
    def AffectedSOPClassUID(self, value):
        """Set the Affected SOP Class UID parameter.

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
            value = UID(value.decode('utf-8'))
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
        """Return the Priority parameter."""
        return self._priority

    @Priority.setter
    def Priority(self, value):
        """Set the Priority parameter."""
        if value in [0, 1, 2]:
            self._priority = value
        else:
            LOGGER.warning("Attempted to set C-FIND Priority parameter to an "
                           "invalid value")
            raise ValueError("Priority must be 0, 1, or 2")

    @property
    def Identifier(self):
        """Return the Identifier parameter."""
        return self._identifier

    @Identifier.setter
    def Identifier(self, value):
        """Set the Identifier parameter."""
        if value is None:
            self._identifier = value
        elif isinstance(value, BytesIO):
            self._identifier = value
        else:
            raise TypeError("Identifier must be a BytesIO object")

    @property
    def Status(self):
        """Return the Status parameter."""
        return self._status

    @Status.setter
    def Status(self, value):
        """Set the Status parameter."""
        if isinstance(value, int) or value is None:
            self._status = value
        else:
            raise TypeError("'C_FIND.Status' must be an int.")

    @property
    def is_valid_request(self):
        """Return True if the required parameters for a C-ECHO RQ are set."""
        for keyword in ['MessageID', 'AffectedSOPClassUID', 'Priority',
                        'Identifier']:
            if getattr(self, keyword) is None:
                return False

        return True

    @property
    def is_valid_response(self):
        """Return True if the required parameters for a C-ECHO RSP are set."""
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

    PS3.4 Annex C.4.3
    PS3.7 9.1.3

    Attributes
    ----------
    MessageID : int
        [M, U, -] Identifies the operation and is used to distinguish this
        operation from other notifications or operations that may be in
        progress. No two identical values for the Message ID shall be used for
        outstanding operations.
    MessageIDBeingRespondedTo : int
        [-, M, M] The Message ID of the operation request/indication to which
        this response/confirmation applies.
    AffectedSOPClassUID : pydicom.uid.UID, bytes or str
        [M, U(=), -] For the request/indication this specifies the SOP Class
        for storage. If included in the response/confirmation, it shall be
        equal to the value in the request/indication
    Priority : int
        [M, -, -] The priority of the C-STORE operation. It shall be one of the
        following:
        * 0: Medium
        * 1: High
        * 2: Low (Default)
    Identifier : io.BytesIO
        [M, U, -] The pydicom Dataset containing the list of Attributes to be
        matched against the values of Attributes of known composite SOP
        Instances of the performing DIMSE service-user, encoded as a BytesIO
        object. For the list of allowed Attributes and the rules defining their
        usage see PS3.4 Annex C.4.3.1.3
    Status : int
        [-, M, -] The error or success notification of the operation.
    NumberOfRemainingSuboperations : int
        [-, C, -] The number of remaining C-STORE sub-operations to be invoked
        by this C-GET operation. It may be included in any response and shall
        be included if the status is Pending
    NumberOfCompletedSuboperations : int
        [-, C, -] The number of C-STORE sub-operations that have completed
        successfully. It may be included in any response and shall be included
        if the status is Pending
    NumberOfFailedSuboperations : int
        [-, C, -] The number of C-STORE sub-operations that have failed. It may
        be included in any response and shall be included if the status is
        Pending
    NumberOfWarningSuboperations : int
        [-, C, -] The number of C-STORE operations that generated Warning
        responses. It may be included in any response and shall be included if
        the status is Pending
    OffendingElement : list of int or None
        [-, C, -] An optional status related field containing a list of the
        elements in which an error was detected.
    ErrorComment : str or None
        [-, C, -] An optional status related field containing a text
        description of the error detected. 64 characters maximum.
    """

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
        """Return the Message ID parameter."""
        return self._message_id

    @MessageID.setter
    def MessageID(self, value):
        """Set the Message ID parameter."""
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
        """Return the Message ID Being Responded To parameter."""
        return self._message_id_being_responded_to

    @MessageIDBeingRespondedTo.setter
    def MessageIDBeingRespondedTo(self, value):
        """Set the Message ID Being Responded To parameter."""
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
        """Return the Affected SOP Class UID parameter."""
        return self._affected_sop_class_uid

    @AffectedSOPClassUID.setter
    def AffectedSOPClassUID(self, value):
        """Set the Affected SOP Class UID parameter.

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
            value = UID(value.decode('utf-8'))
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
        """Return the Priority parameter."""
        return self._priority

    @Priority.setter
    def Priority(self, value):
        """Set the Priority parameter."""
        if value in [0, 1, 2]:
            self._priority = value
        else:
            LOGGER.warning("Attempted to set C-FIND Priority parameter to an "
                           "invalid value")
            raise ValueError("Priority must be 0, 1, or 2")

    @property
    def Identifier(self):
        """Return the Identifier parameter."""
        return self._identifier

    @Identifier.setter
    def Identifier(self, value):
        """Set the Identifier parameter."""
        if value is None:
            self._identifier = value
        elif isinstance(value, BytesIO):
            self._identifier = value
        else:
            raise TypeError("Identifier must be a BytesIO object")

    @property
    def Status(self):
        """Return the Status parameter."""
        return self._status

    @Status.setter
    def Status(self, value):
        """Set the Status parameter."""
        if isinstance(value, int) or value is None:
            self._status = value
        else:
            raise TypeError("Status must be an int")

    @property
    def NumberOfRemainingSuboperations(self):
        """Return the Number of Remaining Suboperations parameter."""
        return self._number_of_remaining_suboperations

    @NumberOfRemainingSuboperations.setter
    def NumberOfRemainingSuboperations(self, value):
        """Set the Number of Remaining Suboperations parameter."""
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
        """Return the Number of Completed Suboperations parameter."""
        return self._number_of_completed_suboperations

    @NumberOfCompletedSuboperations.setter
    def NumberOfCompletedSuboperations(self, value):
        """Set the Number of Completed Suboperations parameter."""
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
        """Return the Number of Failed Suboperations parameter."""
        return self._number_of_failed_suboperations

    @NumberOfFailedSuboperations.setter
    def NumberOfFailedSuboperations(self, value):
        """Set the Number of Failed Suboperations parameter."""
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
        """Return the Number of Warning Suboperations parameter."""
        return self._number_of_warning_suboperations

    @NumberOfWarningSuboperations.setter
    def NumberOfWarningSuboperations(self, value):
        """Set the Number of Warning Suboperations parameter."""
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
        """Return True if the required parameters for a C-ECHO RQ are set."""
        for keyword in ['MessageID', 'AffectedSOPClassUID', 'Priority',
                        'Identifier']:
            if getattr(self, keyword) is None:
                return False

        return True

    @property
    def is_valid_response(self):
        """Return True if the required parameters for a C-ECHO RSP are set."""
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

    PS3.4 Annex C.4.2
    PS3.7 9.1.4

    Attributes
    ----------
    MessageID : int
        [M, U, -] Identifies the operation and is used to distinguish this
        operation from other notifications or operations that may be in
        progress. No two identical values for the Message ID shall be used for
        outstanding operations.
    MessageIDBeingRespondedTo : int
        [-, M, M] The Message ID of the operation request/indication to which
        this response/confirmation applies.
    AffectedSOPClassUID : pydicom.uid.UID, bytes or str
        [M, U(=), -] For the request/indication this specifies the SOP Class
        for storage. If included in the response/confirmation, it shall be
        equal to the value in the request/indication
    Priority : int
        [M, -, -] The priority of the C-STORE operation. It shall be one of the
        following:
        * 0: Medium
        * 1: High
        * 2: Low (Default)
    MoveDestination : bytes or str
        [M, -, -] Specifies the DICOM AE Title of the destination DICOM AE to
        which the C-STORE sub-operations are being performed.
    Identifier : io.BytesIO
        [M, U, -] The pydicom Dataset containing the list of Attributes to be
        matched against the values of Attributes of known composite SOP
        Instances of the performing DIMSE service-user, encoded as a BytesIO
        object. For the list of allowed Attributes and the rules defining their
        usage see PS3.4 Annex C.4.2.1.4
    Status : int
        [-, M, -] The error or success notification of the operation.
    NumberOfRemainingSuboperations : int
        [-, C, -] The number of remaining C-STORE sub-operations to be invoked
        by this C-MOVE operation. It may be included in any response and shall
        be included if the status is Pending
    NumberOfCompletedSuboperations : int
        [-, C, -] The number of C-STORE sub-operations that have completed
        successfully. It may be included in any response and shall be included
        if the status is Pending
    NumberOfFailedSuboperations : int
        [-, C, -] The number of C-STORE sub-operations that have failed. It may
        be included in any response and shall be included if the status is
        Pending
    NumberOfWarningSuboperations : int
        [-, C, -] The number of C-STORE operations that generated Warning
        responses. It may be included in any response and shall be included if
        the status is Pending
    OffendingElement : list of int or None
        [-, C, -] An optional status related field containing a list of the
        elements in which an error was detected.
    ErrorComment : str or None
        [-, C, -] An optional status related field containing a text
        description of the error detected. 64 characters maximum.
    """

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
        """Return the Message ID parameter."""
        return self._message_id

    @MessageID.setter
    def MessageID(self, value):
        """Set the Message ID parameter."""
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
        """Return the Message ID Being Responding To parameter."""
        return self._message_id_being_responded_to

    @MessageIDBeingRespondedTo.setter
    def MessageIDBeingRespondedTo(self, value):
        """Set the Message ID Being Responding To parameter."""
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
        """Return the Affected SOP Class UID parameter."""
        return self._affected_sop_class_uid

    @AffectedSOPClassUID.setter
    def AffectedSOPClassUID(self, value):
        """Set the Affected SOP Class UID parameter.

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
            value = UID(value.decode('utf-8'))
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
        """Return the Priority parameter."""
        return self._priority

    @Priority.setter
    def Priority(self, value):
        """Set the Priority parameter."""
        if value in [0, 1, 2]:
            self._priority = value
        else:
            LOGGER.warning("Attempted to set C-FIND Priority parameter to an "
                           "invalid value")
            raise ValueError("Priority must be 0, 1, or 2")

    @property
    def MoveDestination(self):
        """Return the Move Destination parameter."""
        return self._move_destination

    @MoveDestination.setter
    def MoveDestination(self, value):
        """Set the Move Destination parameter

        Parameters
        ----------
        value : str or bytes
            The Move Destination AE Title as a string or bytes object. Cannot
            be an empty string and will be truncated to 16 characters long
        """
        if isinstance(value, str):
            value = codecs.encode(value, 'utf-8')

        if value is not None:
            self._move_destination = validate_ae_title(value)
        else:
            self._move_destination = None

    @property
    def Identifier(self):
        """Return the Identifier parameter."""
        return self._identifier

    @Identifier.setter
    def Identifier(self, value):
        """Set the Identifier parameter."""
        if value is None:
            self._identifier = value
        elif isinstance(value, BytesIO):
            self._identifier = value
        else:
            raise TypeError("Identifier must be a BytesIO object")

    @property
    def Status(self):
        """Return the Status parameter."""
        return self._status

    @Status.setter
    def Status(self, value):
        """Set the Status parameter."""
        if isinstance(value, int) or value is None:
            self._status = value
        else:
            raise TypeError("Status must be an int")

    @property
    def NumberOfRemainingSuboperations(self):
        """Return the Number of Remaining Suboperations parameter."""
        return self._number_of_remaining_suboperations

    @NumberOfRemainingSuboperations.setter
    def NumberOfRemainingSuboperations(self, value):
        """Set the Number of Remaining Suboperations parameter."""
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
        """Return the Number of Completed Suboperations parameter."""
        return self._number_of_completed_suboperations

    @NumberOfCompletedSuboperations.setter
    def NumberOfCompletedSuboperations(self, value):
        """Set the Number of Completed Suboperations parameter."""
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
        """Return the Number of Failed Suboperations parameter."""
        return self._number_of_failed_suboperations

    @NumberOfFailedSuboperations.setter
    def NumberOfFailedSuboperations(self, value):
        """Set the Number of Failed Suboperations parameter."""
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
        """Return the Number of Warning Suboperations parameter."""
        return self._number_of_warning_suboperations

    @NumberOfWarningSuboperations.setter
    def NumberOfWarningSuboperations(self, value):
        """Set the Number of Warning Suboperations parameter."""
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
        """Return True if the required parameters for a C-ECHO RQ are set."""
        for keyword in ['MessageID', 'AffectedSOPClassUID', 'Priority',
                        'Identifier', 'MoveDestination']:
            if getattr(self, keyword) is None:
                return False

        return True

    @property
    def is_valid_response(self):
        """Return True if the required parameters for a C-ECHO RSP are set."""
        for keyword in ['MessageIDBeingRespondedTo', 'Status']:
            if getattr(self, keyword) is None:
                return False

        return True


class C_ECHO(object):
    """Represents a C-ECHO primitive.

    **C-ECHO Service Procedure**


    1. The invoking DIMSE user requests verification of communication to the
        performing DIMSE user by issuing a C-ECHO request primitive to the
        DIMSE provider.
    2. The DIMSE provider issues a C-ECHO indication primitive to the
        performing DIMSE user
    3. The performing DIMSE user verifies communication by issuing a C-ECHO
        response primitive to the DISME provider
    4. The DIMSE provider issues a C-ECHO confirmation primitive to the
        invoking DIMSE user, completing the C-ECHO operations

    So, local AE sends C-ECHO-RQ to peer, peer sends C-ECHO-RP to local.

    PS3.7 Section 9.1.5

    Attributes
    ----------
    MessageID : int or None
        [M, U] Identifies the operation and is used to distinguish this
        operation from other notifications or operations that may be in
        progress. No two identical values for the Message ID shall be used for
        outstanding operations.
    MessageIDBeingRespondedTo : int or None
        [-, M] The Message ID of the operation request/indication to which this
        response/confirmation applies.
    AffectedSOPClassUID : pydicom.uid.UID, bytes or str or None
        [M, U(=)] For the request/indication this specifies the SOP Class for
        storage. If included in the response/confirmation, it shall be equal
        to the value in the request/indication
    Status : int or None
        [-, M] The error or success notification of the operation.
    ErrorComment : str or None
        [-, C] An optional status related field containing a text description
        of the error detected. 64 characters maximum.
    """

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
        """Return the Message ID parameter."""
        return self._message_id

    @MessageID.setter
    def MessageID(self, value):
        """Set the Message ID parameter."""
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
        """Return the Message ID Being Responded To parameter."""
        return self._message_id_being_responded_to

    @MessageIDBeingRespondedTo.setter
    def MessageIDBeingRespondedTo(self, value):
        """Set the Message ID Being Responded To parameter."""
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
        """Return the Afffected SOP Class UID parameter."""
        return self._affected_sop_class_uid

    @AffectedSOPClassUID.setter
    def AffectedSOPClassUID(self, value):
        """Set the Affected SOP Class UID parameter.

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
            value = UID(value.decode('utf-8'))
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
        """Return the Status parameter."""
        return self._status

    @Status.setter
    def Status(self, value):
        """Set the Status parameter."""
        if isinstance(value, int) or value is None:
            self._status = value
        else:
            raise TypeError("'C_ECHO.Status' must be an int.")

    @property
    def is_valid_request(self):
        """Return True if the required parameters for a C-ECHO RQ are set."""
        for keyword in ['MessageID', 'AffectedSOPClassUID']:
            if getattr(self, keyword) is None:
                return False

        return True

    @property
    def is_valid_response(self):
        """Return True if the required parameters for a C-ECHO RSP are set."""
        for keyword in ['MessageIDBeingRespondedTo', 'Status']:
            if getattr(self, keyword) is None:
                return False

        return True


class C_CANCEL(object):
    """Represents a C-CANCEL primitive.

    PS3.7 Section 9.3.2.3-4 (C-CANCEL-FIND-RQ)
    PS3.7 Section 9.3.3.3-4 (C-CANCEL-GET-RQ)
    PS3.7 Section 9.3.4.3-4 (C-CANCEL-MOVE-RQ)

    Attributes
    ----------
    MessageIDBeingRespondedTo : int
        [-, M] The Message ID of the operation request/indication to which this
        response/confirmation applies.
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
        """Return the Message ID Being Responded To parameter."""
        return self._message_id_being_responded_to

    @MessageIDBeingRespondedTo.setter
    def MessageIDBeingRespondedTo(self, value):
        """Set the Message ID Being Responded To parameter."""
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

    PS3.7 10.1.1.1

    Attributes
    ----------
    MessageID : int
        [M, -] Identifies the operation and is used to distinguish this
        operation from other notifications or operations that may be in
        progress. No two identical values for the Message ID shall be used for
        outstanding operations.
    MessageIDBeingRespondedTo : int
        [-, M] The Message ID of the operation request/indication to which this
        response/confirmation applies.
    AffectedSOPClassUID : pydicom.uid.UID, bytes or str
        [M, U(=)] For the request/indication this specifies the SOP Class for
        storage. If included in the response/confirmation, it shall be equal
        to the value in the request/indication
    AffectedSOPInstanceUID : pydicom.uid.UID, bytes or str
        [M, U(=)] For the request/indication this specifies the SOP Instance
        for storage. If included in the response/confirmation, it shall be
        equal to the value in the request/indication
    EventTypeID :
        [M, C(=)] FIXME, PS3.4 Service Class Specifications
    EventInformation :
        [U, -] FIXME, PS3.4 Service Class Specifications
    EventReply :
        [-, C] FIXME, PS3.4 Service Class Specifications
    Status : int
        [-, M] The error or success notification of the operation. It shall be
        one of the following values:
        FIXME: Add the status values

    **10.1.1.1.8 Status**

    Failure

    0x0119 - class-instance conflict PS3.7 Annex C.5.7
    0x0210 - duplicate invocation PS3.7 Annex C.5.9
    0x0115 - invalid argument value PS3.7 Annex C.5.10
    0x0117 - invalid SOP instance PS3.7 Annex C.5.12
    0x0212 - mistyped argument PS3.7 Annex C.5.15
    0x0114 - no such argument  PS3.7 Annex C.5.16
    0x0113 - no such event type PS3.7 Annex C.5.18
    0x0118 - no such SOP class PS3.7 Annex C.5.20
    0x0112 - no such SOP instance PS3.7 Annex C.5.19
    0x0110 - processing failure PS3.7 Annex C.5.21
    0x0213 - resource limitation PS3.7 Annex C.5.22
    0x0211 - unrecognised operation PS3.7 Annex C.5.23

    Success

    0x0000 - success 0x0000

    """

    def __init__(self):
        self.MessageID = None
        self.MessageIDBeingRespondedTo = None
        self.AffectedSOPClassUID = None
        self.AffectedSOPInstanceUID = None
        self.EventTypeID = None
        self.EventInformation = None
        self.EventReply = None
        self.Status = None

        # (0000,1008) 0x0115
        self.ActionTypeID = None
        self.ActionInformation = None

    @property
    def is_valid_request(self):
        """Return True if the required parameters for a C-ECHO RQ are set."""
        for keyword in ['MessageID', 'AffectedSOPClassUID', 'EventTypeID',
                        'AffectedSOPInstanceUID']:
            if getattr(self, keyword) is None:
                return False

        return True

    @property
    def is_valid_response(self):
        """Return True if the required parameters for a C-ECHO RSP are set."""
        for keyword in ['MessageIDBeingRespondedTo', 'Status']:
            if getattr(self, keyword) is None:
                return False

        return True


class N_GET(object):
    """Represents a N-GET primitive.

    PS3.7 10.1.2.1


    Attributes
    ----------
    MessageID : int
        [M, -] Identifies the operation and is used to distinguish this
        operation from other notifications or operations that may be in
        progress. No two identical values for the Message ID shall be used for
        outstanding operations.
    MessageIDBeingRespondedTo : int
        [-, M] The Message ID of the operation request/indication to which this
        response/confirmation applies.
    RequestedSOPClassUID : pydicom.uid.UID, bytes or str
        [M, -] FIXME
    RequestedSOPInstanceUID : pydicom.uid.UID, bytes or str
        [M, -] FIXME
    AttributeIdentifierList :
        [U, -] FIXME
    AffectedSOPClassUID : pydicom.uid.UID, bytes or str
        [-, U] For the request/indication this specifies the SOP Class for
        storage. If included in the response/confirmation, it shall be equal
        to the value in the request/indication
    AffectedSOPInstanceUID : pydicom.uid.UID, bytes or str
        [-, U] For the request/indication this specifies the SOP Instance for
        storage. If included in the response/confirmation, it shall be equal
        to the value in the request/indication
    AttributeList :
        [-, C] FIXME
    Status : int
        [-, M] The error or success notification of the operation. It shall be
        one of the following values:
        FIXME: Add the status values

    **10.1.2.1.9 Status**

    Warning
        attribute list error 0x0107 PS3.5 Annex C.4.2
    Failure
        class-instance conflict 0x0119 PS3.7 Annex C.5.7
        duplicate invocation 0x0210 PS3.7 Annex C.5.9
        invalid SOP instance 0x0117 PS3.7 Annex C.5.12
        mistyped argument 0x0212 PS3.7 Annex C.5.15
        no such SOP class 0x0118 PS3.7 Annex C.5.20
        no such SOP instance 0x0112 PS3.7 Annex C.5.19
        processing failure 0x0110 PS3.7 Annex C.5.21
        resource limitation 0x213 PS3.7 Annex C.5.22
        unrecognised operation 0x0211 PS3.7 Annex C.5.23
        not authorised 0x0124 PS3.5 Annex C.5.25
    Success
        success 0x0000
    """

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

    @property
    def is_valid_request(self):
        """Return True if the required parameters for a C-ECHO RQ are set."""
        for keyword in ['MessageID', 'RequestedSOPClassUID',
                        'RequestedSOPInstanceUID']:
            if getattr(self, keyword) is None:
                return False

        return True

    @property
    def is_valid_response(self):
        """Return True if the required parameters for a C-ECHO RSP are set."""
        for keyword in ['MessageIDBeingRespondedTo', 'Status']:
            if getattr(self, keyword) is None:
                return False

        return True


class N_SET(object):
    """Represents a N-SET primitive.

    PS3.7 10.1.3.1

    Attributes
    ----------
    MessageID : int
        [M, -] Identifies the operation and is used to distinguish this
        operation from other notifications or operations that may be in
        progress. No two identical values for the Message ID shall be used for
        outstanding operations.
    MessageIDBeingRespondedTo : int
        [-, M] The Message ID of the operation request/indication to which this
        response/confirmation applies.
    RequestedSOPClassUID : pydicom.uid.UID, bytes or str
        [M, -] FIXME
    RequestedSOPInstanceUID : pydicom.uid.UID, bytes or str
        [M, -] FIXME
    ModificationList :
        [M, -] FIXME
    AttributeList :
        [-, U] FIXME
    AffectedSOPClassUID : pydicom.uid.UID, bytes or str
        [-, U] For the request/indication this specifies the SOP Class for
        storage. If included in the response/confirmation, it shall be equal
        to the value in the request/indication
    AffectedSOPInstanceUID : pydicom.uid.UID, bytes or str
        [-, U] For the request/indication this specifies the SOP Instance for
        storage. If included in the response/confirmation, it shall be equal
        to the value in the request/indication
    Status : int
        [-, M] The error or success notification of the operation. It shall be
        one of the following values:
        FIXME: Add the status values

    **10.1.3.1.9 Status**

    Failure
        class-instance conflict 0x0119 PS3.7 Annex C.5.7
        duplicate invocation 0x0210 PS3.7 Annex C.5.9
        invalid attribute value 0x0106 PS3.7 Annex C.5.11
        invalid SOP instance 0x0117 PS3.7 Annex C.5.12
        no such attribute 0x0120 PS3.7 Annex C.5.13
        missing attribute value 0x0121 PS3.7 Annex C.5.14
        mistyped argument 0x0212 PS3.7 Annex C.5.15
        no such SOP instance 0x0112 PS3.7 Annex C.5.19
        no such SOP class 0x0118 PS3.7 Annex C.5.20
        processing failure 0x0110 PS3.7 Annex C.5.21
        resource limitation 0x213 PS3.7 Annex C.5.22
        unrecognised operation 0x0211 PS3.7 Annex C.5.23
        not authorised 0x0124 PS3.5 Annex C.5.25
    Warning
        attribute list error 0x0107 PS3.5 Annex C.4.2
    Success
        success 0x0000
    """

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

    @property
    def is_valid_request(self):
        """Return True if the required parameters for a C-ECHO RQ are set."""
        for keyword in ['MessageID', 'RequestedSOPClassUID',
                        'RequestedSOPInstanceUID']:
            if getattr(self, keyword) is None:
                return False

        return True

    @property
    def is_valid_response(self):
        """Return True if the required parameters for a C-ECHO RSP are set."""
        for keyword in ['MessageIDBeingRespondedTo', 'Status']:
            if getattr(self, keyword) is None:
                return False

        return True


class N_ACTION(object):
    """Represents a N-ACTION primitive.

    PS3.7 10.1.4.1

    Attributes
    ----------
    MessageID : int
        [M, -] Identifies the operation and is used to distinguish this
        operation from other notifications or operations that may be in
        progress. No two identical values for the Message ID shall be used for
        outstanding operations.
    MessageIDBeingRespondedTo : int
        [-, M] The Message ID of the operation request/indication to which this
        response/confirmation applies.
    RequestedSOPClassUID : pydicom.uid.UID, bytes or str
        [M, -] FIXME
    RequestedSOPInstanceUID : pydicom.uid.UID, bytes or str
        [M, -] FIXME
    ActionTypeID :
        [M, C(=)] FIXME
    ActionInformation :
        [U, -] FIXME
    AffectedSOPClassUID : pydicom.uid.UID, bytes or str
        [-, U] For the request/indication this specifies the SOP Class for
        storage. If included in the response/confirmation, it shall be equal
        to the value in the request/indication
    AffectedSOPInstanceUID : pydicom.uid.UID, bytes or str
        [-, U] For the request/indication this specifies the SOP Instance for
        storage. If included in the response/confirmation, it shall be equal
        to the value in the request/indication
    ActionReply :
        [-, C] FIXME
    Status : int
        [-, M] The error or success notification of the operation. It shall be
        one of the following values:
        FIXME: Add the status values

    **10.1.4.1.10 Status**

    Failure
        class-instance conflict 0x0119 PS3.7 Annex C.5.7
        duplicate invocation 0x0210 PS3.7 Annex C.5.9
        invalid argument value 0x0115 PS3.7 Annex C.5.10
        invalid SOP instance 0x0117 PS3.7 Annex C.5.12
        mistyped argument 0x0212 PS3.7 Annex C.5.15
        no such action type 0x0123 PS3.7 Annex C.5.24
        no such argument 0x0114 PS3.7 Annex C.5.16
        no such SOP instance 0x0112 PS3.7 Annex C.5.19
        no such SOP class 0x0118 PS3.7 Annex C.5.20
        processing failure 0x0110 PS3.7 Annex C.5.21
        resource limitation 0x213 PS3.7 Annex C.5.22
        unrecognised operation 0x0211 PS3.7 Annex C.5.23
        not authorised 0x0124 PS3.5 Annex C.5.25
    Success
        success 0x0000 PS3.7 Annex C.1.1
    """

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

    @property
    def is_valid_request(self):
        """Return True if the required parameters for a C-ECHO RQ are set."""
        for keyword in ['MessageID', 'RequestedSOPClassUID',
                        'RequestedSOPInstanceUID']:
            if getattr(self, keyword) is None:
                return False

        return True

    @property
    def is_valid_response(self):
        """Return True if the required parameters for a C-ECHO RSP are set."""
        for keyword in ['MessageIDBeingRespondedTo', 'Status']:
            if getattr(self, keyword) is None:
                return False

        return True


class N_CREATE(object):
    """Represents a N-CREATE primitive.

    PS3.7 10.1.5.1

    Attributes
    ----------
    MessageID : int
        [M, -] Identifies the operation and is used to distinguish this
        operation from other notifications or operations that may be in
        progress. No two identical values for the Message ID shall be used for
        outstanding operations.
    MessageIDBeingRespondedTo : int
        [-, M] The Message ID of the operation request/indication to which this
        response/confirmation applies.
    AffectedSOPClassUID : pydicom.uid.UID, bytes or str
        [M, U(=)] For the request/indication this specifies the SOP Class for
        storage. If included in the response/confirmation, it shall be equal
        to the value in the request/indication
    AffectedSOPInstanceUID : pydicom.uid.UID, bytes or str
        [U, C] For the request/indication this specifies the SOP Instance for
        storage. If included in the response/confirmation, it shall be equal
        to the value in the request/indication
    AttributeList :
        [U, U] FIXME
    Status : int
        [-, M] The error or success notification of the operation. It shall be
        one of the following values:
        FIXME: Add the status values

    **10.1.5.1.6 Status**

    Failure
        duplicate SOP instance 0x0111 PS3.7 Annex C.5.8
        duplicate invocation 0x0210 PS3.7 Annex C.5.9
        invalid attribute value 0x0106 PS3.7 Annex C.5.11
        invalid SOP instance 0x0117 PS3.7 Annex C.5.12
        missing attribute 0x0120 PS3.7 Annex C.5.13
        missing attribute value 0x0121 PS3.7 Annex C.5.14
        mistyped argument 0x0212 PS3.7 Annex C.5.15
        no such attribute 0x0105 PS3.6 Annex C.5.17
        no such SOP class 0x0118 PS3.7 Annex C.5.20
        processing failure 0x0110 PS3.7 Annex C.5.21
        resource limitation 0x213 PS3.7 Annex C.5.22
        unrecognised operation 0x0211 PS3.7 Annex C.5.23
        not authorised 0x0124 PS3.5 Annex C.5.25
    Warning
        attribute list error 0x0107 PS3.7 Annex C.4.2
        attribute value out of range 0x0116 PS3.7 Annex C.4.3
    Success
        success 0x0000 PS3.7 Annex C.1.1
    """

    def __init__(self):
        self.MessageID = None
        self.MessageIDBeingRespondedTo = None
        self.AffectedSOPClassUID = None
        self.AffectedSOPInstanceUID = None
        self.AttributeList = None
        self.Status = None

    @property
    def is_valid_request(self):
        """Return True if the required parameters for a C-ECHO RQ are set."""
        for keyword in ['MessageID', 'AffectedSOPClassUID']:
            if getattr(self, keyword) is None:
                return False

        return True

    @property
    def is_valid_response(self):
        """Return True if the required parameters for a C-ECHO RSP are set."""
        for keyword in ['MessageIDBeingRespondedTo', 'Status']:
            if getattr(self, keyword) is None:
                return False

        return True


class N_DELETE(object):
    """Represents a N-DELETE primitive.

    PS3.7 10.1.6.1

    Attributes
    ----------
    MessageID : int
        [M, -] Identifies the operation and is used to distinguish this
        operation from other notifications or operations that may be in
        progress. No two identical values for the Message ID shall be used for
        outstanding operations.
    MessageIDBeingRespondedTo : int
        [-, M] The Message ID of the operation request/indication to which this
        response/confirmation applies.
    RequestedSOPClassUID : pydicom.uid.UID, bytes or str
        [M, -] FIXME
    RequestedSOPInstanceUID : pydicom.uid.UID, bytes or str
        [M, -] FIXME
    AffectedSOPClassUID : pydicom.uid.UID, bytes or str
        [-, U] For the request/indication this specifies the SOP Class for
        storage. If included in the response/confirmation, it shall be equal
        to the value in the request/indication
    AffectedSOPInstanceUID : pydicom.uid.UID, bytes or str
        [-, U] For the request/indication this specifies the SOP Instance for
        storage. If included in the response/confirmation, it shall be equal
        to the value in the request/indication
    Status : int
        [-, M] The error or success notification of the operation. It shall be
        one of the following values:
        FIXME: Add the status values

    **10.1.6.1.7 Status**

    Failure
        class-instance conflict 0x0119 PS3.7 Annex C.5.7
        duplicate invocation 0x0210 PS3.7 Annex C.5.9
        invalid SOP instance 0x0117 PS3.7 Annex C.5.12
        mistyped argument 0x0212 PS3.7 Annex C.5.15
        no such SOP class 0x0118 PS3.7 Annex C.5.20
        no such SOP instance 0x0112 PS3.7 Annex C.5.19
        processing failure 0x0110 PS3.7 Annex C.5.21
        resource limitation 0x213 PS3.7 Annex C.5.22
        unrecognised operation 0x0211 PS3.7 Annex C.5.23
        not authorised 0x0124 PS3.5 Annex C.5.25
    Success
        success 0x0000 PS3.7 Annex C.1.1
    """

    def __init__(self):
        self.MessageID = None
        self.MessageIDBeingRespondedTo = None
        self.RequestedSOPClassUID = None
        self.RequestedSOPInstanceUID = None
        self.AffectedSOPClassUID = None
        self.AffectedSOPInstanceUID = None
        self.Status = None

    @property
    def is_valid_request(self):
        """Return True if the required parameters for a C-ECHO RQ are set."""
        for keyword in ['MessageID', 'RequestedSOPClassUID',
                        'RequestedSOPInstanceUID']:
            if getattr(self, keyword) is None:
                return False

        return True

    @property
    def is_valid_response(self):
        """Return True if the required parameters for a C-ECHO RSP are set."""
        for keyword in ['MessageIDBeingRespondedTo', 'Status']:
            if getattr(self, keyword) is None:
                return False

        return True
