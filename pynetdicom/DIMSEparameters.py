#
# Copyright (c) 2012 Patrice Munger
# This file is part of pynetdicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pynetdicom.googlecode.com
#

import struct

# DIMSE-C Services
class C_STORE_ServiceParameters:
    """
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
    """
    def __init__(self):
        self.MessageID = None
        self.MessageIDBeingRespondedTo = None
        self.AffectedSOPClassUID = None
        self.AffectedSOPInstanceUID = None
        self.Priority = None
        self.MoveOriginatorApplicationEntityTitle = None
        self.MoveOriginatorMessageID = None
        self.DataSet = None
        self.Status = None

    def __repr__(self):
        return classprinter(self)

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
        # The SOP Class of the Information Model for the query
        self.AffectedSOPClassUID = None
        self.Priority = None
        self.Identifier = None
        self.Status = None

    def __repr__(self):
        return classprinter(self)

class C_GET_ServiceParameters:

    def __init__(self):
        self.MessageID = None
        self.MessageIDBeingRespondedTo = None
        self.AffectedSOPClassUID = None
        self.Priority = None
        self.Identifier = None
        self.Status = None
        self.NumberOfRemainingSubOperations = None
        self.NumberOfCompleteSubOperations = None
        self.NumberOfFailedSubOperations = None
        self.NumberOfWarningSubOperations = None

    def __repr__(self):
        return classprinter(self)

class C_MOVE_ServiceParameters:

    def __init__(self):
        self.MessageID = None
        self.MessageIDBeingRespondedTo = None
        self.AffectedSOPClassUID = None
        self.Priority = None
        self.MoveDestination = None
        self.Identifier = None
        self.Status = None
        self.NumberOfRemainingSubOperations = None
        self.NumberOfCompleteSubOperations = None
        self.NumberOfFailedSubOperations = None
        self.NumberOfWarningSubOperations = None

    def __repr__(self):
        return classprinter(self)

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

    def __repr__(self):
        return classprinter(self)


# DIMSE-N services
class N_EVENT_REPORT_ServiceParamters:

    def __init__(self):
        self.MessageID = None
        self.MessageIDBeingRespondedTo = None
        self.AffectedSOPClassUID = None
        self.AffectedSOPInstanceUID = None
        self.EventTypeID = None
        self.EventInformation = None
        self.EventReply = None
        self.Status = None

class N_GET_ServiceParamters:

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

class N_SET_ServiceParamters:

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

class N_ACTION_ServiceParamters:
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

class N_CREATE_ServiceParamters:
    def __init__(self):
        self.MessageID = None
        self.MessageIDBeingRespondedTo = None
        self.AffectedSOPClassUID = None
        self.AffectedSOPInstanceUID = None
        self.AttributeList = None
        self.Status = None

class N_DELETE_ServiceParamters:
    def __init__(self):
        self.MessageID = None
        self.MessageIDBeingRespondedTo = None
        self.RequestedSOPClassUID = None
        self.RequestedSOPInstanceUID = None
        self.AffectedSOPClassUID = None
        self.AffectedSOPInstanceUID = None
        self.Status = None
