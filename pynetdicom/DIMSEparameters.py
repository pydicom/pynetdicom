

import logging

from pydicom.uid import UID
from pydicom.dataset import Dataset

from pynetdicom.utils import validate_ae_title


logger = logging.getLogger('pynetdicom.DIMSEparameters')


# DIMSE-C Services
class C_STORE_ServiceParameters:
    """
    Represents a C-STORE primitive
    
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
    PS3.7 9.1
    
    Attributes
    ----------
    MessageID : int
        [M, U] Identifies the operation and is used to distinguish this operation from
        other notifications or operations that may be in progress. No two
        identical values for the Message ID shall be used for outstanding 
        operations.
    MessageIDBeingRespondedTo : int
        [-, M] The Message ID of the operation request/indication to which this
        response/confirmation applies. 
    AffectedSOPClassUID : pydicom.uid.UID, bytes or str
        [M, U(=)] For the request/indication this specifies the SOP Class for
        storage. If included in the response/confirmation, it shall be equal
        to th value in the request/indication
    AffectedSOPInstanceUID : pydicom.uid.UID, bytes or str
        [M, U(=)] For the request/indication this specifies the SOP Instance for
        storage. If included in the response/confirmation, it shall be equal
        to th value in the request/indication
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
    DataSet : pydicom.dataset
        [M, -] The DICOM dataset containing the Attributes of the Composite SOP
        Instance to be stored
    Status : int
        [-, M] The error or success notification of the operation. It shall be
        one of the following values:
        * 0xA700: Failure (Refused: Out of resources)
        * 0xA900: Failure (Error: Data Set does not match SOP Class)
        * 0xC000: Failure (Error: Cannot understand)
        * 0xB000: Warning (Coercion of Data Elements)
        * 0xB007: Warning (Data Set does not match SOP Class)
        * 0xB006: Warning (Element Discarded)
        * 0x0000: Success
    """
    def __init__(self):
        self.MessageID = None
        self.MessageIDBeingRespondedTo = None
        self.AffectedSOPClassUID = None
        self.AffectedSOPInstanceUID = None
        self.Priority = 0x02
        self.MoveOriginatorApplicationEntityTitle = None
        self.MoveOriginatorMessageID = None
        self.DataSet = None
        self.Status = None
    
    @property
    def MessageID(self):
        return self._message_id
        
    @MessageID.setter
    def MessageID(self, value):
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
    def MessageIDBeingRespondedTo(self):
        return self._message_id_being_responded_to
        
    @MessageIDBeingRespondedTo.setter
    def MessageIDBeingRespondedTo(self, value):
        if isinstance(value, int):
            if 0 <= value < 2**16:
                self._message_id_being_responded_to = value
            else:
                raise ValueError("Message ID Being Responded To must be between 0 and 65535, inclusive")
        elif value is None:
            self._message_id_being_responded_to = value
        else:
            raise TypeError("Message ID Being Responded To must be an int")
    
    @property
    def AffectedSOPClassUID(self):
        return self._affected_sop_class_uid
        
    @AffectedSOPClassUID.setter
    def AffectedSOPClassUID(self, value):
        """
        Sets the Affected SOP Class UID parameter
        
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
        
        if value is not None:
            try:
                value.is_valid()
            except:
                logger.error("Affected SOP Class UID is an invalid UID")
                raise ValueError("Affected SOP Class UID is an invalid UID")
        
        self._affected_sop_class_uid = value
    
    @property
    def AffectedSOPInstanceUID(self):
        return self._affected_sop_instance_uid
        
    @AffectedSOPInstanceUID.setter
    def AffectedSOPInstanceUID(self, value):
        """
        Sets the Affected SOP Instance UID parameter
        
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
        
        if value is not None:
            try:
                value.is_valid()
            except:
                logger.error("Affected SOP Instance UID is an invalid UID")
                raise ValueError("Affected SOP Class UID is an invalid UID")
        
        self._affected_sop_instance_uid = value
    
    @property
    def Priority(self):
        return self._priority
        
    @Priority.setter
    def Priority(self, value):
        if value in [0, 1, 2]:
            self._priority = value
        else:
            logger.warning("Attempted to set C-STORE Priority parameter to an " \
                    "invalid value")
            raise ValueError("Priority must be 0, 1, or 2")

    @property
    def MoveOriginatorApplicationEntityTitle(self):
        return self._move_originator_application_entity_title
        
    @MoveOriginatorApplicationEntityTitle.setter
    def MoveOriginatorApplicationEntityTitle(self, value):
        """
        Set the Move Originator AE Title
        
        Parameters
        ----------
        value : str or bytes
            The Move Originator AE Title as a string or bytes object. Cannot be
            an empty string and will be truncated to 16 characters long
        """
        if isinstance(value, str):
            value = bytes(value, 'utf-8')
        
        if value is not None:
            self._move_originator_application_entity_title = validate_ae_title(value)
        else:
            self._move_originator_application_entity_title = None
    
    @property
    def MoveOriginatorMessageID(self):
        return self._move_originator_message_id
        
    @MoveOriginatorMessageID.setter
    def MoveOriginatorMessageID(self, value):
        if isinstance(value, int):
            if 0 <= value < 2**16:
                self._move_originator_message_id = value
            else:
                raise ValueError("Move Originator Message ID To must be between 0 and 65535, inclusive")
        elif value is None:
            self._move_originator_message_id = value
        else:
            raise TypeError("Move Originator Message ID To must be an int")
    
    @property
    def DataSet(self):
        return self._dataset
        
    @DataSet.setter
    def DataSet(self, value):
        if isinstance(value, Dataset):
            self._dataset = value
        elif value is None:
            self._dataset = value
        else:
            raise TypeError("DataSet must be a pydicom Dataset object")
    
    @property
    def Status(self):
        return self._status
        
    @Status.setter
    def Status(self, value):
        if isinstance(value, int):
            # Add value range checking
            #if 
            self._status = value
        elif value is None:
            self._status = value
        else:
            raise TypeError("Status must be an int")


class C_FIND_ServiceParameters:
    """
    PS3.4 Annex C.4.1.1
    
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
    """
    def __init__(self):
        self.MessageID = None
        self.MessageIDBeingRespondedTo = None
        self.AffectedSOPClassUID = None
        self.Priority = None
        self.Identifier = None
        self.Status = None

class C_GET_ServiceParameters:
    def __init__(self):
        self.MessageID = None
        self.MessageIDBeingRespondedTo = None
        self.AffectedSOPClassUID = None
        self.Priority = None
        self.Identifier = None
        self.Status = None
        self.NumberOfRemainingSuboperations = None
        self.NumberOfCompletedSuboperations = None
        self.NumberOfFailedSuboperations = None
        self.NumberOfWarningSuboperations = None

class C_MOVE_ServiceParameters:
    def __init__(self):
        self.MessageID = None
        self.MessageIDBeingRespondedTo = None
        self.AffectedSOPClassUID = None
        self.Priority = None
        self.MoveDestination = None
        self.Identifier = None
        self.Status = None
        self.NumberOfRemainingSuboperations = None
        self.NumberOfCompletedSuboperations = None
        self.NumberOfFailedSuboperations = None
        self.NumberOfWarningSuboperations = None

class C_ECHO_ServiceParameters:
    """
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
    
    """
    def __init__(self):
        self.MessageID = None
        self.MessageIDBeingRespondedTo = None
        self.AffectedSOPClassUID = None
        self.Status = None


# DIMSE-N services
class N_EVENT_REPORT_ServiceParameters:
    """ PS3.7 10.1.1.1 """
    def __init__(self):
        self.MessageID = None
        self.MessageIDBeingRespondedTo = None
        self.AffectedSOPClassUID = None
        self.AffectedSOPInstanceUID = None
        self.EventTypeID = None
        self.EventInformation = None
        self.EventReply = None
        self.Status = None

class N_GET_ServiceParameters:
    """ PS3.7 10.1.2.1 """
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

class N_SET_ServiceParameters:
    """ PS3.7 10.1.3.1 """
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

class N_ACTION_ServiceParameters:
    """ PS3.7 10.1.4.1 """
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

class N_CREATE_ServiceParameters:
    """ PS3.7 10.1.5.1 """
    def __init__(self):
        self.MessageID = None
        self.MessageIDBeingRespondedTo = None
        self.AffectedSOPClassUID = None
        self.AffectedSOPInstanceUID = None
        self.AttributeList = None
        self.Status = None

class N_DELETE_ServiceParameters:
    """ PS3.7 10.1.6.1 """
    def __init__(self):
        self.MessageID = None
        self.MessageIDBeingRespondedTo = None
        self.RequestedSOPClassUID = None
        self.RequestedSOPInstanceUID = None
        self.AffectedSOPClassUID = None
        self.AffectedSOPInstanceUID = None
        self.Status = None
