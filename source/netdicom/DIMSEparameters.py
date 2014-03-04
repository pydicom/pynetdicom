#
# Copyright (c) 2012 Patrice Munger
# This file is part of pynetdicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pynetdicom.googlecode.com
#


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


class C_STORE_RQ_Message:

    def __init__(self):
        pass


class C_STORE_Service:

    def __init__(self):
        self.Parameters = C_STORE_ServiceParameters()


#
#
# Extented association stuff: Defined in part 3.7
#
#
#
#
#
class ImplementationClassUIDParameters:

    def __init__(self):
        self.ImplementationClassUID = None

    def ToParams(self):
        tmp = ImplementationClassUIDSubItem()
        tmp.FromParams(self)
        return tmp


class ImplementationClassUIDSubItem:

    def __init__(self):
        self.ItemType = 0x52                                # Unsigned byte
        # Unsigned byte 0x00
        self.Reserved = 0x00
        self.ItemLength = None                          # Unsigned short
        self.ImplementationClassUID = None          # String

    def FromParams(self, Params):
        self.ImplementationClassUID = Params.ImplementationClassUID
        self.ItemLength = len(self.ImplementationClassUID)

    def ToParams(self):
        tmp = ImplementationClassUIDParameters()
        tmp.ImplementationClassUID = self.ImplementationClassUID
        return tmp

    def Encode(self):
        tmp = ''
        tmp = tmp + struct.pack('B', self.ItemType)
        tmp = tmp + struct.pack('B', self.Reserved)
        tmp = tmp + struct.pack('>H', self.ItemLength)
        tmp = tmp + self.ImplementationClassUID
        return tmp

    def Decode(self, Stream):
        (self.ItemType, self.Reserved,
         self.ItemLength) = struct.unpack('> B B H', Stream.read(4))
        self.ImplementationClassUID = Stream.read(self.ItemLength)

    def TotalLength(self):
        return 4 + self.ItemLength

    def __repr__(self):
        tmp = "  Implementation class IUD sub item\n"
        tmp = tmp + "   Item type: 0x%02x\n" % self.ItemType
        tmp = tmp + "   Item length: %d\n" % self.ItemLength
        tmp = tmp + \
            "   SOP class UID length: %s\n" % self.ImplementationClassUID
        return tmp

#
#
#


class ImplementationVersionNameParameters:

    def __init__(self):
        self.ImplementationVersionName = None

    def ToParams(self):
        tmp = ImplementationVersionNameSubItem()
        tmp.FromParams(self)
        return tmp


class ImplementationVersionNameSubItem:

    def __init__(self):
        self.ItemType = 0x55                                # Unsigned byte
        # Unsigned byte 0x00
        self.Reserved = 0x00
        self.ItemLength = None                          # Unsigned short
        self.ImplementationVersionName = None       # String

    def FromParams(self, Params):
        self.ImplementationVersionName = Params.ImplementationVersionName
        self.ItemLength = len(self.ImplementationVersionName)

    def ToParams(self):
        tmp = ImplementationVersionNameParameters()
        tmp.ImplementationVersionName = self.ImplementationVersionName
        return tmp

    def Encode(self):
        tmp = ''
        tmp = tmp + struct.pack('B', self.ItemType)
        tmp = tmp + struct.pack('B', self.Reserved)
        tmp = tmp + struct.pack('>H', self.ItemLength)
        tmp = tmp + self.ImplementationVersionName
        return tmp

    def Decode(self, Stream):
        (self.ItemType, self.Reserved,
         self.ItemLength) = struct.unpack('> B B H', Stream.read(4))
        self.ImplementationVersionName = Stream.read(self.ItemLength)

    def TotalLength(self):
        return 4 + self.ItemLength

    def __repr__(self):
        tmp = "  Implementation version name sub item\n"
        tmp = tmp + "   Item type: 0x%02x\n" % self.ItemType
        tmp = tmp + "   Item length: %d\n" % self.ItemLength
        tmp = tmp + \
            "   SOP class UID length: %s\n" % self.ImplementationVersionName
        return tmp


class AsynchronousOperationsWindowSubItem:

    def __init__(self):
        # Unsigned byte
        self.ItemType = 0x53
        # Unsigned byte
        self.Reserved = 0x00
        # Unsigned short
        self.ItemLength = 0x0004
        self.MaximumNumberOperationsInvoked = None          # Unsigned short
        # Unsigned short
        self.MaximumNumberOperationsPerformed = None

    def FromParams(self, Params):
        self.MaximumNumberOperationsInvoked = \
            Params.MaximumNumberOperationsInvoked
        self.MaximumNumberOperationsPerformed = \
            Params.MaximumNumberOperationsPerformed

    def ToParams(self):
        tmp = AsynchronousOperationsWindowSubItem()
        tmp.MaximumNumberOperationsInvoked = \
            self.MaximumNumberOperationsInvoked
        tmp.MaximumNumberOperationsPerformed = \
            self.MaximumNumberOperationsPerformed
        return tmp

    def Encode(self):
        tmp = ''
        tmp = tmp + struct.pack('B', self.ItemType)
        tmp = tmp + struct.pack('B', self.Reserved)
        tmp = tmp + struct.pack('>H', self.ItemLength)
        tmp = tmp + struct.pack('>H', self.MaximumNumberOperationsInvoked)
        tmp = tmp + struct.pack('>H', self.MaximumNumberOperationsPerformed)
        return tmp

    def Decode(self, Stream):
        (self.ItemType, self.Reserved, self.ItemLength,
         self.MaximumNumberOperationsInvoked,
         self.MaximumNumberOperationsPerformed) = struct.unpack('> B B H H H',
                                                                Stream.read(8))

    def TotalLength(self):
        return 4 + self.ItemLength

    def __repr__(self):
        tmp = "  Asynchoneous operation window sub item\n"
        tmp = tmp + "   Item type: 0x%02x\n" % self.ItemType
        tmp = tmp + "   Item length: %d\n" % self.ItemLength
        tmp = tmp + \
            "   Maximum number of operations invoked: %d\n" % \
            self.MaximumNumberOperationsInvoked
        tmp = tmp + \
            "   Maximum number of operations performed: %d\n" % \
            self.MaximumNumberOperationsPerformed
        return tmp


import struct


class SCP_SCU_RoleSelectionParameters:

    def __init__(self):
        self.SOPClassUID = None
        self.SCURole = None
        self.SCPRole = None

    def ToParams(self):
        tmp = SCP_SCU_RoleSelectionSubItem()
        tmp.FromParams(self)
        return tmp


class SCP_SCU_RoleSelectionSubItem:

    def __init__(self):
        self.ItemType = 0x54            # Unsigned byte
        self.Reserved = 0x00            # Unsigned byte 0x00
        self.ItemLength = None          # Unsigned short
        self.UIDLength = None           # Unsigned short
        self.SOPClassUID = None         # String
        self.SCURole = None         # Unsigned byte
        self.SCPRole = None         # Unsigned byte

    def FromParams(self, Params):
        self.SOPClassUID = Params.SOPClassUID
        self.SCURole = Params.SCURole
        self.SCPRole = Params.SCPRole
        self.ItemLength = 4 + len(self.SOPClassUID)
        self.UIDLength = len(self.SOPClassUID)

    def ToParams(self):
        tmp = SCP_SCU_RoleSelectionParameters()
        tmp.SOPClassUID = self.SOPClassUID
        tmp.SCURole = self.SCURole
        tmp.SCPRole = self.SCPRole
        return tmp

    def Encode(self):
        tmp = ''
        tmp += struct.pack('B', self.ItemType)
        tmp += struct.pack('B', self.Reserved)
        tmp += struct.pack('>H', self.ItemLength)
        tmp += struct.pack('>H', self.UIDLength)
        tmp += self.SOPClassUID
        tmp += struct.pack('B B', self.SCURole, self.SCPRole)
        return tmp

    def Decode(self, Stream):
        (self.ItemType, self.Reserved,
         self.ItemLength, self.UIDLength) = struct.unpack('> B B H H',
                                                          Stream.read(6))
        self.SOPClassUID = Stream.read(self.UIDLength)
        (self.SCURole, self.SCPRole) = struct.unpack('B B', Stream.read(2))

    def TotalLength(self):
        return 4 + self.ItemLength

    def __repr__(self):
        tmp = "  SCU/SCP role selection sub item\n"
        tmp = tmp + "   Item type: 0x%02x\n" % self.ItemType
        tmp = tmp + "   Item length: %d\n" % self.ItemLength
        tmp = tmp + "   SOP class UID length: %d\n" % self.UIDLength
        tmp = tmp + "   SOP class UID: %s\n" % self.SOPClassUID
        tmp = tmp + "   SCU Role: %d\n" % self.SCURole
        tmp = tmp + "   SCP Role: %d" % self.SCPRole
        return tmp



# needs to be re-worked
# class SOPClassExtentedNegociationSubItem:
#    def __init__(self):
# self.ItemType = 0x56                                   # Unsigned byte
# self.Reserved = 0x00                                   # Unsigned byte - 0x00
# self.ItemLength = None                                 # Unsigned short
# self.SOPClassUIDLength = None                          # Unsigned short
# self.SOPClassUID = None                                # String
# self.ServiceClassApplicationInformation = None         # Class
#
#    def FromParams(self, Params):
#        self.SOPClassUID = Params.SOPClassUID
#        self.ServiceClassApplicationInformation = \
#            Params.ServiceClassApplicationInformation()
#        self.SOPClassUIDLength = len(self.SOPClassUID)
#        self.ItemLength = 2 + self.SOPClassUIDLength + \
#        self.ServiceClassApplicationInformation.TotalLength()
#
#    def ToParams(self):
#        tmp = SOPClassExtentedNegociationSubItem()
#        tmp.SOPClassUID = self.SOPClassUID
#        tmp.ServiceClassApplicationInformation = \
#            self.ServiceClassApplicationInformation
#        return  (self.SOPClassUID, \
#                  self.ServiceClassApplicationInformation.Decompose())
#
#    def Encode(self):
#        tmp = ''
#        tmp = tmp + struct.pack('B', self.ItemType)
#        tmp = tmp + struct.pack('B', self.Reserved)
#        tmp = tmp + struct.pack('>H', self.ItemLength)
#        tmp = tmp + struct.pack('>H', self.SOPClassUIDLength)
#        tmp = tmp + self.SOPClassUID
#        tmp = tmp + self.ServiceClassApplicationInformation.Encode()
#        return tmp
#
#    def Decode(self,Stream):
#        (self.ItemType, self.Reserved,
#         self.ItemLength, self.SOPClassUIDLength) = \
#              struct.unpack('> B B H H', Stream.read(6))
#        self.SOPClassUID = Stream.read(self.UIDLength)
#        self.ServiceClassApplicationInformation.Decode(Stream)
#
#    def TotalLength(self):
#        return 4 + self.ItemLength
#
#
#
#    def __repr__(self):
#        tmp = "  SOP class extended negociation sub item\n"
#        tmp = tmp + "   Item type: 0x%02x\n" % self.ItemType
#        tmp = tmp + "   Item length: %d\n" % self.ItemLength
#        tmp = tmp + "   SOP class UID length: %d\n" % self.SOPClassUIDLength
#        tmp = tmp + "   SOP class UID: %s" % self.SOPClassUID
#        return tmp
#
