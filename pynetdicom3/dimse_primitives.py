"""
Define the DIMSE-C and DIMSE-N service parameter primitives.

Notes:
* The class member names must match their corresponding DICOM element keyword
    in order for the DIMSE messages/primitives to be created correctly.

TODO: Implement properties for DIMSE-N parameters
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

    C-STORE Service Procedure
    =========================
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
        [M, U(=)] For the request/indication this specifies the SOP Instance for
        storage. If included in the response/confirmation, it shall be equal
        to the value in the request/indication
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
        [-, M] The error or success notification of the operation. It shall be
        one of the following values:
        Storage Service Class Specific (PS3.4 Annex B.2.3):
            * 0xA700 to 0xA7FF: Failure (Refused: Out of resources)
            * 0xA900 to 0xA9FF: Failure (Error: Data Set does not match SOP
                                Class)
            * 0xC000 to 0xCFFF: Failure (Error: Cannot understand)
            * 0xB000: Warning (Coercion of Data Elements)
            * 0xB007: Warning (Data Set does not match SOP Class)
            * 0xB006: Warning (Element Discarded)
            * 0x0000: Success
        General C-STORE (PS3.7 9.1.1.1.9 and Annex C):
            * 0x0122: Failure (Refused: SOP class not supported)
            * 0x0210: Failure (Refused: Duplicate invocation)
            * 0x0117: Failure (Refused: Invalid SOP instance)
            * 0x0212: Failure (Refused: Mistyped argument)
            * 0x0211: Failure (Refused: Unrecognised operation)
            * 0x0124: Failure (Refused: Not authorised)
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

        # Optional Command Set elements used in with specific Status values
        # For Warning statuses 0xB000, 0xB006, 0xB007
        # For Failure statuses 0xCxxx, 0xA9xx,
        self.OffendingElement = None
        # For Warning statuses 0xB000, 0xB006, 0xB007
        # For Failure statuses 0xCxxx, 0xA9xx, 0xA7xx, 0x0122, 0x0124
        self.ErrorComment = None
        # For Failure statuses 0x0117, 0x0122
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
                raise ValueError("Message ID must be between 0 and 65535, " \
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
                raise ValueError("Message ID Being Responded To must be " \
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
            raise TypeError("Affected SOP Class UID must be a " \
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
            raise TypeError("Affected SOP Instance UID must be a " \
                            "pydicom.uid.UID, str or bytes")

        if value is not None and not value.is_valid:
            LOGGER.error("Affected SOP Instance UID is an invalid UID")
            raise ValueError("Affected SOP Class UID is an invalid UID")

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
            LOGGER.warning("Attempted to set C-STORE Priority parameter to " \
                           "an invalid value")
            raise ValueError("Priority must be 0, 1, or 2")

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
                raise ValueError("Move Originator Message ID To must be " \
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
        if isinstance(value, int):
            # Add value range checking
            # Additional statuses needed
            # Refused: Out of Resources
            # Refused: SOP Class Not Supported 0x0122
            # 0x0111 Duplicate SOP Instance
            # Error: Cannot Understand
            # Error: Dataset does not match SOP Class
            # Warning
            # Success
            # Refused: Duplicate Invocation 0x0210
            # Refused: Invalid SOP Instance 0x0117
            # Refused: Mistyped Argument 0x0212
            # Refused: Unrecognised Operation 0x0211
            # Refused: Not Authorised 0x0124
            valid_values = [range(0xA700, 0xA7FF + 1),
                            range(0xA900, 0xA9FF + 1),
                            range(0xC000, 0xCFFF + 1),
                            [0xB000, 0xB007, 0xB006, 0x0000, 0x0122, 0x0111,
                             0x0210, 0x0212, 0x0211, 0x0124, 0x0117]]
            found_valid = False
            for ii in valid_values:
                if value in ii:
                    found_valid = True
            if not found_valid:
                LOGGER.debug("Unknown Status value 0x{0:04x}".format(value))

            self._status = value

        elif value is None:
            self._status = value
        else:
            raise TypeError("Status must be an int")


class C_FIND(object):
    """Represents a C-FIND primitive.

    PS3.4 Annex C.4.1.1
    PS3.4 9.1.2

    SOP Class UID
    ~~~~~~~~~~~~~
    Identifies the QR Information Model against which the C-FIND is to be
    performed. Support for the SOP Class UID is implied by the Abstract Syntax
    UID of the Presentation Context used by this C-FIND operation.

    Priority
    ~~~~~~~~
    The requested priority of the C-FIND operation with respect to other DIMSE
    operations being performed by the same SCP. Processing of priority requests
    is not required of SCPs. Whether or not an SCP supports priority processing
    and the meaning of different priority levels shall be stated in the
    Conformance Statement of the SCP.

    Identifier
    ~~~~~~~~~~
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
    * Key Attribute with values corresponding to Key Attributes contained in the
    Identifier of the request
    * QR Level (0008, 0053)
    * Conditionally, (0008,0005) if expanded or replacement character sets
        may be used in the response Identifier attributes
    * Conditionally, (0008,0201) if Key Attributes of time are to be
        interpreted explicitly in the designated local time zone

    The C-FIND SCP is required to support either/both the 'Retrieve AE Title'
    (0008,0054) or the 'Storage Media File-Set ID'/'Storage Media File Set UID'
    (0088,0130)/(0088,0140) data elements.

    Retrieve AE Title
    ~~~~~~~~~~~~~~~~~
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
        [M, U(=), -] For the request/indication this specifies the SOP Class for
        storage. If included in the response/confirmation, it shall be equal
        to the value in the request/indication
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
        [-, M, -] The error or success notification of the operation. It shall
        be one of the following values:
        Query/Retrieve Service Class Specific (PS3.4 Annex C.4.1):
            * 0xA700: Failure (Refused: Out of resources)
            * 0xA900: Failure (Identifier does not match SOP Class)
            * 0xC000 to 0xCFFF: Failure (Unable to process)
            * 0xFE00: Cancel (Matching terminated due to Cancel request)
            * 0x0000: Success (Matching is complete - no final Identifier is
                      supplied)
            * 0xFF00: Pending (Matches are continuing - Current match is
                      supplied and any Optional Keys were supported in the same
                      manner as Required Keys)
            * 0xFF01: Pending (Matches are continuing - Warning that one or more
                      Optional Keys were not supported for existence and/or
                      matching for this Identifier)
        General C-FIND PS3.7 9.1.2.1.5 and Annex C
            * 0x0122: Failure (Refused: SOP class not supported)
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
        # For Failure statuses 0xA900
        self.OffendingElement = None
        # For Failure statuses 0xA900, 0xA700, 0x0122, 0xC000
        self.ErrorComment = None
        # For Failure statuses 0xC000
        self.AffectedSOPInstanceUID = None
        self.ErrorID = None

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
                raise ValueError("Message ID must be between 0 and 65535, " \
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
                raise ValueError("Message ID Being Responded To must be " \
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
            raise TypeError("Affected SOP Class UID must be a " \
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
            LOGGER.warning("Attempted to set C-FIND Priority parameter to an " \
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
        if isinstance(value, int):
            # Add value range checking
            valid_values = [range(0xC000, 0xCFFF + 1),
                            [0xA700, 0xA900, 0xFE00, 0xFF00, 0xFF01, 0x0000]]
            found_valid = False
            for ii in valid_values:
                if value in ii:
                    found_valid = True
                    self._status = value
            if not found_valid:
                raise ValueError("Invalid Status value")

        elif value is None:
            self._status = value
        else:
            raise TypeError("Status must be an int")


class C_GET(object):
    """Represents a C-GET primitive.

    The C-GET service is used

    C-GET Service Procedure
    =======================

    Number of Remaining Sub-Operations
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    A C-GET response with a status of:
    * Pending shall contain the Number of Remaining Sub-operations Attribute
    * Canceled may contain the Number of Remaining Sub-operations Attribute
    * Warning, Failure or Success shall not contain the Number of Remaining
        Sub-operations Attribute

    Number of Completed Sub-Operations
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    A C-GET response with a status of:
    * Pending shall contain the Number of Completed Sub-operations Attribute
    * Canceled, Warning, Failure or Success may contain the Number of Completed
        Sub-operations Attribute

    Number of Failed Sub-Operations
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    A C-GET response with a status of:
    * Pending shall contain the Number of Failed Sub-operations Attribute
    * Canceled, Warning, Failure or Success may contain the Number of Failed
        Sub-operations Attribute

    Number of Warning Sub-Operations
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
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
        [M, U(=), -] For the request/indication this specifies the SOP Class for
        storage. If included in the response/confirmation, it shall be equal
        to the value in the request/indication
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
        [-, M, -] The error or success notification of the operation. It shall
        be one of the following values:
        * 0xA701: Failure (Refused: out of resources - unable to calculate
            number of matches)
        * 0xA702: Failure (Refused: out of resources - unable to perform
            sub-operations)
        * 0xA900: Failure (Identifier does not match SOP Class)
        * 0xC000 to 0xCFFF: Failure (Unable to process)
        * 0xFE00: Cancel (Sub-operations terminated due to Cancel indication)
        * 0xB000: Warning (Sub-operations complete - one or more Failures or
            Warnings)
        * 0x0000: Success (Sub-operations complete - no Failures or Warnings)
        * 0xFF00: Pending (Sub-operations are continuing)
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
                raise ValueError("Message ID must be between 0 and 65535, " \
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
                raise ValueError("Message ID Being Responded To must be " \
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
            raise TypeError("Affected SOP Class UID must be a " \
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
            LOGGER.warning("Attempted to set C-FIND Priority parameter to an " \
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
        if isinstance(value, int):
            # Add value range checking
            valid_values = [range(0xC000, 0xCFFF + 1),
                            [0xA701, 0xA702, 0xA900, 0xFE00,
                             0xB000, 0x0000, 0xFF00]]
            found_valid = False
            for ii in valid_values:
                if value in ii:
                    found_valid = True
                    self._status = value
            if not found_valid:
                raise ValueError("Invalid Status value")

        elif value is None:
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
                raise ValueError("Number of Remaining Suboperations must be " \
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
                raise ValueError("Number of Completed Suboperations must be " \
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
                raise ValueError("Number of Failed Suboperations must be " \
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
                raise ValueError("Number of Warning Suboperations must be " \
                                 "greater than or equal to 0")
        elif value is None:
            self._number_of_warning_suboperations = value
        else:
            raise TypeError("Number of Warning Suboperations must be an int")


class C_MOVE(object):
    """Represents a C-MOVE primitive.

    The C-MOVE service is used

    C-MOVE Service Procedure
    =======================

    Number of Remaining Sub-Operations
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    A C-MOVE response with a status of:
    * Pending shall contain the Number of Remaining Sub-operations Attribute
    * Canceled may contain the Number of Remaining Sub-operations Attribute
    * Warning, Failure or Success shall not contain the Number of Remaining
        Sub-operations Attribute

    Number of Completed Sub-Operations
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    A C-MOVE response with a status of:
    * Pending shall contain the Number of Completed Sub-operations Attribute
    * Canceled, Warning, Failure or Success may contain the Number of Completed
        Sub-operations Attribute

    Number of Failed Sub-Operations
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    A C-MOVE response with a status of:
    * Pending shall contain the Number of Failed Sub-operations Attribute
    * Canceled, Warning, Failure or Success may contain the Number of Failed
        Sub-operations Attribute

    Number of Warning Sub-Operations
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
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
        [M, U(=), -] For the request/indication this specifies the SOP Class for
        storage. If included in the response/confirmation, it shall be equal
        to the value in the request/indication
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
        [-, M, -] The error or success notification of the operation. It shall
        be one of the following values:
        Query/Retrieve Service Class Specific (PS3.4 Annex C.4.2.1.5):
            * 0xA701: Failure (Refused: Out of resources - unable to calculate
                      number of matches)
            * 0xA702: Failure (Refused: Out of resources - unable to perform
                      sub-operations)
            * 0xA801: Failure (Refused: Move destination unknown)
            * 0xA900: Failure (Identifier does not match SOP Class)
            * 0xC000 to 0xCFFF: Failure (Unable to process)
            * 0xFE00: Cancel (Sub-operations terminated due to Cancel
                      indication)
            * 0xB000: Warning (Sub-operations complete - one or more failures)
            * 0x0000: Success (Sub-operations complete - no failures)
            * 0xFF00: Pending (Sub-operations are continuing)
        General C-MOVE PS3.7 9.1.4.1.7 and Annex C:
            * 0x0122: Failure (Refused: SOP class not supported)
            * 0x0111: Failure (Refused: Duplicate invocation)
            * 0x0212: Failure (Refused: Mistyped argument)
            * 0x0211: Failure (Refused: Unrecognised operation)
            * 0x0124: Failure (Refused: Not authorised)

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
        # For Failure statuses 0xCxxx
        self.AffectedSOPInstanceUID = None
        self.ErrorID = None

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
                raise ValueError("Message ID must be between 0 and 65535, " \
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
                raise ValueError("Message ID Being Responded To must be " \
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
            raise TypeError("Affected SOP Class UID must be a " \
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
            LOGGER.warning("Attempted to set C-FIND Priority parameter to an " \
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
            The Move Destination AE Title as a string or bytes object. Cannot be
            an empty string and will be truncated to 16 characters long
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
        if isinstance(value, int):
            # Add value range checking
            valid_values = [range(0xC000, 0xCFFF + 1),
                            [0xA701, 0xA702, 0xA801, 0xA900,
                             0xFE00, 0xFF00, 0xB000, 0x0000]]
            found_valid = False
            for ii in valid_values:
                if value in ii:
                    found_valid = True
                    self._status = value
            if not found_valid:
                raise ValueError("Invalid Status value")

        elif value is None:
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
                raise ValueError("Number of Remaining Suboperations must be " \
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
                raise ValueError("Number of Completed Suboperations must be " \
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
                raise ValueError("Number of Failed Suboperations must be " \
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
                raise ValueError("Number of Warning Suboperations must be " \
                                 "greater than or equal to 0")
        elif value is None:
            self._number_of_warning_suboperations = value
        else:
            raise TypeError("Number of Warning Suboperations must be an int")


class C_ECHO(object):
    """Represents a C-ECHO primitive.

    C-ECHO Service Procedure
    ========================
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
    Status : int
        [-, M] The error or success notification of the operation. It shall be
        one of the following values:
        * 0x0000: Success
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
                raise ValueError("Message ID must be between 0 and 65535, " \
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
                raise ValueError("Message ID Being Responded To must be " \
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
            raise TypeError("Affected SOP Class UID must be a " \
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
        if value == 0x0000 or value is None:
            self._status = value
        else:
            raise ValueError("Status must be 0x0000")


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
                raise ValueError("Message ID Being Responded To must be " \
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
        [M, U(=)] For the request/indication this specifies the SOP Instance for
        storage. If included in the response/confirmation, it shall be equal
        to the value in the request/indication
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

    10.1.1.1.8 Status

    Failure
        class-instance conflict 0x0119 PS3.7 Annex C.5.7
        duplicate invocation 0x0210 PS3.7 Annex C.5.9
        invalid argument value 0x0115 PS3.7 Annex C.5.10
        invalid SOP instance 0x0117 PS3.7 Annex C.5.12
        mistyped argument 0x0212 PS3.7 Annex C.5.15
        no such argument 0x0114 PS3.7 Annex C.5.16
        no such event type 0x0113 PS3.7 Annex C.5.18
        no such SOP class 0x0118 PS3.7 Annex C.5.20
        no such SOP instance 0x0112 PS3.7 Annex C.5.19
        processing failure 0x0110 PS3.7 Annex C.5.21
        resource limitation 0x213 PS3.7 Annex C.5.22
        unrecognised operation 0x0211 PS3.7 Annex C.5.23
    Success
        success 0x0000
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

    10.1.2.1.9 Status

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

    10.1.3.1.9 Status

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

    10.1.4.1.10 Status

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

    10.1.5.1.6 Status

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

    10.1.6.1.7 Status
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
