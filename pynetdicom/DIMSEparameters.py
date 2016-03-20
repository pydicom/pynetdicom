#
# Copyright (c) 2012 Patrice Munger
# This file is part of pynetdicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pynetdicom.googlecode.com
#

import struct


def classprinter(klass):
    tmp = ''
    for ii in klass.__dict__.keys():
        tmp += ii + ": " + str(klass.__dict__[ii]) + '\n'

    return tmp


# DIMSE-C Services
class C_STORE_ServiceParameters:

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
    * QR Level (0008,0052)
    * Conditionally, (0008,0053)
    * Conditionally, (0008,0005)
    * Conditionally, (0008,0201)
    
    Response Identifier Structure
    * Key Attribute with values corresponding to Key Attributes contained in the
    Identifier of the request
    * QR Level (0008, 0053)
    * Conditionally, (0008,0005)
    * Conditionally, (0008,0201)
    
    """
    def __init__(self):
        self.MessageID = None
        self.MessageIDBeingRespondedTo = None
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
    C-ECHO Service Procedures
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

# Why are these here?
#class C_STORE_RQ_Message:
#    def __init__(self):
#        pass

#class C_STORE_Service:
#    def __init__(self):
#        self.Parameters = C_STORE_ServiceParameters()
