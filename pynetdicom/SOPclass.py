#
# Copyright (c) 2012 Patrice Munger
# This file is part of pynetdicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pynetdicom.googlecode.com
#

import logging
import time

from pynetdicom.dsutils import *
from pynetdicom.DIMSEparameters import *
import pynetdicom.DIMSEprovider
import pynetdicom.ACSEprovider


logger = logging.getLogger('pynetdicom.SOPclass')


class Status(object):
    def __init__(self, Type, Description, CodeRange):
        self.Type = Type
        self.Description = Description
        self.CodeRange = CodeRange

    def __int__(self):
        return self.CodeRange[0]

    def __repr__(self):
        return self.Type + ' ' + self.Description


class ServiceClass(object):
    def __init__(self):
        pass

    def Code2Status(self, code):
        for dd in dir(self):
            getattr(self, dd).__class__
            obj = getattr(self, dd)
            if obj.__class__ == Status:
                if code in obj.CodeRange:
                    return obj
        # unknown status ...
        return None


# VERIFICATION SOP CLASSES
class VerificationServiceClass(ServiceClass):
    Success = Status('Success', '', range(0x0000, 0x0000 + 1))

    def __init__(self):
        ServiceClass.__init__(self)

    def SCU(self, msg_id):
        cecho = C_ECHO_ServiceParameters()
        cecho.MessageID = msg_id
        cecho.AffectedSOPClassUID = self.UID

        self.DIMSE.Send(cecho, self.pcid, self.maxpdulength)

        msg, _ = self.DIMSE.Receive(Wait=True)
        
        return self.Code2Status(msg.Status)

    def SCP(self, msg):
        """
        When the local AE is acting as an SCP for the VerificationSOPClass
        and a C-ECHO-RQ is received then create a C-ECHO-RSP and send it
        to the peer AE via the DIMSE provider
        
        Parameters
        ----------
        msg - pydicom.Dataset
            The dataset containing the C-ECHO-RQ
        """
        rsp = C_ECHO_ServiceParameters()
        self.message_id = msg.MessageID.value
        rsp.MessageIDBeingRespondedTo = msg.MessageID.value
        rsp.Status = int(self.Success)

        try:
            self.AE.on_c_echo(self)
        except:
            #logger.error("There was an exception on OnReceiveEcho callback")
            pass
        
        # Send response via DIMSE provider
        self.DIMSE.Send(rsp, self.pcid, self.ACSE.MaxPDULength)

class VerificationSOPClass(VerificationServiceClass):
    UID = '1.2.840.10008.1.1'


# STORAGE SOP CLASSES
class StorageServiceClass(ServiceClass):
    OutOfResources = Status('Failure',
                            'Refused: Out of resources',
                            range(0xA700, 0xA7FF + 1)) 
    DataSetDoesNotMatchSOPClassFailure = Status(
                            'Failure',
                            'Error: Data Set does not match SOP Class',
                            range(0xA900, 0xA9FF + 1))
    CannotUnderstand = Status(
                            'Failure',
                            'Error: Cannot understand',
                            range(0xC000, 0xCFFF + 1))
    CoercionOfDataElements = Status(
                            'Warning',
                            'Coercion of Data Elements',
                            range(0xB000, 0xB000 + 1))
    DataSetDoesNotMatchSOPClassWarning = Status(
                            'Warning',
                            'Data Set does not match SOP Class',
                            range(0xB007, 0xB007 + 1))
    ElementDisgarded = Status(
                            'Warning',
                            'Element Discarted',
                            range(0xB006, 0xB006 + 1))
    Success = Status('Success', '', range(0x0000, 0x0000 + 1))
    
    def __init__(self):
        ServiceClass.__init__(self)

    def SCU(self, dataset, msg_id, priority=2):
        """
        
        """
        # build C-STORE primitive
        csto = C_STORE_ServiceParameters()
        csto.MessageID = msg_id
        csto.AffectedSOPClassUID = dataset.SOPClassUID
        csto.AffectedSOPInstanceUID = dataset.SOPInstanceUID
        csto.Priority = 0x0002
        csto.DataSet = encode(dataset,
                              self.transfersyntax.is_implicit_VR,
                              self.transfersyntax.is_little_endian)
        csto.DataSet = BytesIO(csto.DataSet)
        
        # If we failed to encode our dataset, abort the association and return
        if csto.DataSet is None:
            return None

        # send cstore request
        self.DIMSE.Send(csto, self.pcid, self.maxpdulength)

        # wait for c-store response
        ans, _ = self.DIMSE.Receive(Wait=True)
        return self.Code2Status(ans.Status.value)

    def SCP(self, msg):
        status = None
        
        try:
            DS = decode(msg.DataSet,
                        self.transfersyntax.is_implicit_VR,
                        self.transfersyntax.is_little_endian)
        except:
            logger.error("StorageServiceClass failed to decode the dataset")
            status = self.CannotUnderstand
            
        
        # make response
        rsp = C_STORE_ServiceParameters()
        rsp.MessageIDBeingRespondedTo = msg.MessageID
        rsp.AffectedSOPInstanceUID = msg.AffectedSOPInstanceUID
        rsp.AffectedSOPClassUID = msg.AffectedSOPClassUID
        
        # Callback
        #   We expect a valid Status from on_store to send back to the peer AE
        if status is None:
            try:
                status = self.AE.on_c_store(self, DS)
            except Exception as e:
                logger.exception("Failed to implement the "
                    "ApplicationEntity::on_store() callback function correctly")
                status = self.CannotUnderstand
                
        rsp.Status = int(status)
        self.DIMSE.Send(rsp, self.pcid, self.ACSE.MaxPDULength)

class StorageSOPClass(StorageServiceClass): pass

class MRImageStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.4'

class EnhancedMRImageStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.4.1'

class MRSpectroscopyStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.4.2'

class CTImageStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.2'

class PositronEmissionTomographyImageStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.128'

class CRImageStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.1'

class DigitalXRayImagePresentationStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.1.1'

class DigitalXRayImageProcessingStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.1.1.1'

class DigitalMammographyXRayImagePresentationStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.1.2'

class DigitalMammographyXRayImageProcessingStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.1.2.1'

class DigitalIntraOralXRayImagePresentationStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.1.3'

class DigitalIntraOralXRayImageProcessingStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.1.3.1'

class EncapsulatedPDFStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.104.1'
    
class GrayscaleSoftcopyPresentationStateStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.11.1'
    
class ColorSoftcopyPresentationStateStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.11.2'

class PseudocolorSoftcopyPresentationStageStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.11.3'

class BlendingSoftcopyPresentationStateStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.11.4'

class XRayAngiographicImageStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.12.1'

class EnhancedXAImageStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.12.1.1'

class XRayRadiofluoroscopicImageStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.12.2'

class EnhancedXRFImageStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.12.2.1'

class EnhancedCTImageStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.2.1'

class NMImageStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.20'

class UltrasoundMultiframeImageStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.3.1'

class SCImageStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.7'

class MultiframeSingleBitSecondaryCaptureImageStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.7.1'

class MultiframeGrayscaleByteSecondaryCaptureImageStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.7.2'

class MultiframeGrayscaleWordSecondaryCaptureImageStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.7.3'

class MultiframeTrueColorSecondaryCaptureImageStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.7.4'

class RTImageStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.481.1'

class RTDoseStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.481.2'

class RTStructureSetStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.481.3'

class RTPlanStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.481.5'

class VLEndoscopicImageStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.77.1.1'

class VideoEndoscopicImageStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.77.1.1.1'

class VLMicroscopicImageStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.77.1.2'

class VideoMicroscopicImageStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.77.1.2.1'

class VLSlideCoordinatesMicroscopicImageStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.77.1.3'

class VLPhotographicImageStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.77.1.4'

class VideoPhotographicImageStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.77.1.4.1'

class OphthalmicPhotography8BitImageStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.77.1.5.1'

class OphthalmicPhotography16BitImageStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.77.1.5.2'

class StereometricRelationshipStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.77.1.5.3'

class UltrasoundImageStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.6.1'

class RawDataStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.66'

class SpatialRegistrationStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.66.1'

class SpatialFiducialsStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.66.2'

class DeformableSpatialRegistrationStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.66.3'

class SegmentationStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.66.4'

class RealWorldValueMappingStorageSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.67'

class XRayRadiationDoseStructuredReportSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.88.67'

class EnhancedStructuredReportSOPClass(StorageSOPClass):
    UID = '1.2.840.10008.5.1.4.1.1.88.22'


# QUERY RETRIEVE SOP Classes
class QueryRetrieveServiceClass(ServiceClass): pass

class QueryRetrieveSOPClass(QueryRetrieveServiceClass): pass

class BasicWorklistServiceClass (ServiceClass): pass

class ModalityWorklistServiceSOPClass (BasicWorklistServiceClass):
    OutOfResources = Status(
        'Failure',
        'Refused: Out of resources',
        range(0xA700, 0xA700 + 1)
    )
    IdentifierDoesNotMatchSOPClass = Status(
        'Failure',
        'Identifier does not match SOP Class',
        range(0xA900, 0xA900 + 1)
    )
    UnableToProcess = Status(
        'Failure',
        'Unable to process',
        range(0xC000, 0xCFFF + 1)
    )
    MatchingTerminatedDueToCancelRequest = Status(
        'Cancel',
        'Matching terminated due to Cancel request',
        range(0xFE00, 0xFE00 + 1)
    )
    Success = Status(
        'Success',
        'Matching is complete - No final Identifier is supplied',
        range(0x0000, 0x0000 + 1)
    )
    Pending = Status(
        'Pending',
        'Matches are continuing - Current Match is supplied'
        'and any Optional Keys were supported in the same manner as'
        'Required Keys',
        range(0xFF00, 0xFF00 + 1)
    )
    PendingWarning = Status(
        'Pending',
        'Matches are continuing - Warning that one or more Optional'
        'Keys were not supported for existence and/or matching for'
        'this identifier',
        range(0xFF01, 0xFF01 + 1)
    )

    def SCU(self, msgid):
        # build C-FIND primitive
        cfind = C_FIND_ServiceParameters()
        cfind.MessageID = msgid
        cfind.AffectedSOPClassUID = self.UID
        cfind.Priority = 0x0002
        cfind.Identifier = encode(ds,
                                          self.transfersyntax.is_implicit_VR,
                                          self.transfersyntax.is_little_endian)
        cfind.Identifier = BytesIO(cfind.Identifier)
        
        # send c-find request
        self.DIMSE.Send(cfind, self.pcid, self.maxpdulength)
        while 1:
            time.sleep(0.001)
            # wait for c-find responses
            ans, id = self.DIMSE.Receive(Wait=False)
            if not ans:
                continue
            d = decode(
                ans.Identifier, self.transfersyntax.is_implicit_VR,
                self.transfersyntax.is_little_endian)
            try:
                status = self.Code2Status(ans.Status.value).Type
            except:
                status = None
            if status != 'Pending':
                break
            yield status, d
        yield status, d

    def SCP(self, msg):
        ds = decode(msg.Identifier, self.transfersyntax.is_implicit_VR,
                            self.transfersyntax.is_little_endian)

        # make response
        rsp = C_FIND_ServiceParameters()
        rsp.MessageIDBeingRespondedTo = msg.MessageID
        rsp.AffectedSOPClassUID = msg.AffectedSOPClassUID

        gen = self.AE.OnReceiveFind(self, ds)
        try:
            while 1:
                time.sleep(0.001)
                IdentifierDS, status = gen.next()
                rsp.Status = int(status)
                rsp.Identifier = encode(
                    IdentifierDS,
                    self.transfersyntax.is_implicit_VR,
                    self.transfersyntax.is_little_endian)
                # send response
                self.DIMSE.Send(rsp, self.pcid, self.ACSE.MaxPDULength)
        except StopIteration:
            # send final response
            rsp = C_FIND_ServiceParameters()
            rsp.MessageIDBeingRespondedTo = msg.MessageID
            rsp.AffectedSOPClassUID = msg.AffectedSOPClassUID
            rsp.Status = int(self.Success)
            self.DIMSE.Send(rsp, self.pcid, self.ACSE.MaxPDULength)


# QR Information Models
class PatientRootQueryRetrieveSOPClass(QueryRetrieveSOPClass): pass

class StudyRootQueryRetrieveSOPClass(QueryRetrieveSOPClass): pass

class PatientStudyOnlyQueryRetrieveSOPClass(QueryRetrieveSOPClass): pass


# C-FIND SOP Classes for QR
class QueryRetrieveFindSOPClass(QueryRetrieveServiceClass):
    OutOfResources = Status('Failure',
                            'Refused: Out of resources',
                            range(0xA700, 0xA700 + 1))
    IdentifierDoesNotMatchSOPClass = Status(
                            'Failure',
                            'Identifier does not match SOP Class',
                            range(0xA900, 0xA900 + 1))
    UnableToProcess = Status('Failure',
                             'Unable to process',
                             range(0xC000, 0xCFFF + 1))
    MatchingTerminatedDueToCancelRequest = Status(
                            'Cancel',
                            'Matching terminated due to Cancel request',
                            range(0xFE00, 0xFE00 + 1))
    Success = Status(
                    'Success',
                    'Matching is complete - No final Identifier is supplied',
                    range(0x0000, 0x0000 + 1))
    Pending = Status(
                'Pending',
                'Matches are continuing - Current Match is supplied \
                and any Optional Keys were supported in the same manner as '
                'Required Keys',
                range(0xFF00, 0xFF00 + 1))
    PendingWarning = Status(
                "Pending",
                "Matches are continuing - Warning that one or more Optional "
                "Keys were not supported for existence and/or matching for "
                "this identifier",
                range(0xFF01, 0xFF01 + 1))
    
    def SCU(self, ds, msg_id, msg_priority=2):
        """
        Parameters
        ----------
        ds - pydicom.dataset.Dataset
            The query
        msg_id - int
            The message ID
        msg_priority - int
            The message priority level (2: Normal)
        """
        # build C-FIND primitive
        cfind = C_FIND_ServiceParameters()
        cfind.MessageID = msg_id
        cfind.AffectedSOPClassUID = self.UID
        cfind.Priority = 0x0002
        cfind.Identifier = encode(ds,
                                  self.transfersyntax.is_implicit_VR,
                                  self.transfersyntax.is_little_endian)
        cfind.Identifier = BytesIO(cfind.Identifier)

        # send c-find request
        self.DIMSE.Send(cfind, self.pcid, self.maxpdulength)
        
        logger.info('Find SCU Request Identifiers:')
        logger.info('')
        logger.info('# DICOM Dataset')
        for elem in ds:
            logger.info(elem)
        logger.info('')
        
        while 1:
            time.sleep(0.001)
            
            # wait for c-find responses
            ans, _ = self.DIMSE.Receive(Wait=False)
            if not ans:
                continue
            
            d = decode(ans.Identifier, 
                       self.transfersyntax.is_implicit_VR,
                       self.transfersyntax.is_little_endian)

            try:
                status = self.Code2Status(ans.Status.value).Type
            except:
                status = None
            
            if status != 'Pending':
                break
            
            logger.warn("Find Response: (Pending)")
            logger.warn('')
            
            yield status, d

        yield status, d

    def SCP(self, msg):
        ds = decode(msg.Identifier, self.transfersyntax.is_implicit_VR,
                            self.transfersyntax.is_little_endian)

        # make response
        rsp = C_FIND_ServiceParameters()
        rsp.MessageIDBeingRespondedTo = msg.MessageID
        rsp.AffectedSOPClassUID = msg.AffectedSOPClassUID

        gen = self.AE.OnReceiveFind(self, ds)
        try:
            while 1:
                time.sleep(0.001)
                IdentifierDS, status = gen.next()
                rsp.Status = int(status)
                rsp.Identifier = encode(
                    IdentifierDS,
                    self.transfersyntax.is_implicit_VR,
                    self.transfersyntax.is_little_endian)
                # send response
                self.DIMSE.Send(rsp, self.pcid, self.ACSE.MaxPDULength)
        except StopIteration:
            # send final response
            rsp = C_FIND_ServiceParameters()
            rsp.MessageIDBeingRespondedTo = msg.MessageID
            rsp.AffectedSOPClassUID = msg.AffectedSOPClassUID
            rsp.Status = int(self.Success)
            self.DIMSE.Send(rsp, self.pcid, self.ACSE.MaxPDULength)

class PatientRootFindSOPClass(PatientRootQueryRetrieveSOPClass,
                                  QueryRetrieveFindSOPClass):
    UID = '1.2.840.10008.5.1.4.1.2.1.1'

class StudyRootFindSOPClass(StudyRootQueryRetrieveSOPClass,
                            QueryRetrieveFindSOPClass):
    UID = '1.2.840.10008.5.1.4.1.2.2.1'

class PatientStudyOnlyFindSOPClass(PatientStudyOnlyQueryRetrieveSOPClass,
                                   QueryRetrieveFindSOPClass):
    UID = '1.2.840.10008.5.1.4.1.2.3.1'


# C-MOVE SOP Classes for QR
class QueryRetrieveMoveSOPClass(QueryRetrieveServiceClass):
    OutOfResourcesNumberOfMatches = Status(
        'Failure',
        'Refused: Out of resources - Unable to calcultate number of matches',
        range(0xA701, 0xA701 + 1)
    )
    OutOfResourcesUnableToPerform = Status(
        'Failure',
        'Refused: Out of resources - Unable to perform sub-operations',
        range(0xA702, 0xA702 + 1)
    )
    MoveDestinationUnknown = Status(
        'Failure',
        'Refused: Move destination unknown',
        range(0xA801, 0xA801 + 1)
    )
    IdentifierDoesNotMatchSOPClass = Status(
        'Failure',
        'Identifier does not match SOP Class',
        range(0xA900, 0xA900 + 1)
    )
    UnableToProcess = Status(
        'Failure',
        'Unable to process',
        range(0xC000, 0xCFFF + 1)
    )
    Cancel = Status(
        'Cancel',
        'Sub-operations terminated due to Cancel indication',
        range(0xFE00, 0xFE00 + 1)
    )
    Warning = Status(
        'Warning',
        'Sub-operations Complete - One or more Failures or Warnings',
        range(0xB000, 0xB000 + 1)
    )
    Success = Status(
        'Success',
        'Sub-operations Complete - No Failure or Warnings',
        range(0x0000, 0x0000 + 1)
    )
    Pending = Status(
        'Pending',
        'Sub-operations are continuing',
        range(0xFF00, 0xFF00 + 1)
    )

    def SCU(self, ds, destaet, msgid):
        # build C-FIND primitive
        cmove = C_MOVE_ServiceParameters()
        cmove.MessageID = msgid
        cmove.AffectedSOPClassUID = self.UID
        cmove.MoveDestination = destaet
        cmove.Priority = 0x0002
        cmove.Identifier = encode(
            ds, self.transfersyntax.is_implicit_VR,
            self.transfersyntax.is_little_endian)
        cmove.Identifier = BytesIO(cmove.Identifier)

        # send c-find request
        self.DIMSE.Send(cmove, self.pcid, self.maxpdulength)

        while 1:
            # wait for c-move responses
            time.sleep(0.001)
            ans, id = self.DIMSE.Receive(Wait=False)
            if not ans:
                continue
            status = self.Code2Status(ans.Status.value).Type
            if status != 'Pending':
                break
            yield status

    def SCP(self, msg):
        ds = decode(msg.Identifier, self.transfersyntax.is_implicit_VR,
                            self.transfersyntax.is_little_endian)

        # make response
        rsp = C_MOVE_ServiceParameters()
        rsp.MessageIDBeingRespondedTo = msg.MessageID.value
        rsp.AffectedSOPClassUID = msg.AffectedSOPClassUID.value
        gen = self.AE.OnReceiveMove(self, ds, msg.MoveDestination.value)

        # first value returned by callback must be the complete remote AE specs
        remoteAE = gen.next()

        # request association to move destination
        ass = self.AE.RequestAssociation(remoteAE)
        nop = gen.next()
        try:
            ncomp = 0
            nfailed = 0
            nwarning = 0
            ncompleted = 0
            while 1:
                DataSet = gen.next()
                # request an association with destination
                # send C-STORE
                s = str(UID2SOPClass(DataSet.SOPClassUID))
                ind = len(s) - s[::-1].find('.')
                obj = getattr(ass, s[ind:-2])
                status = obj.SCU(DataSet, ncompleted)
                if status.Type == 'Failed':
                    nfailed += 1
                if status.Type == 'Warning':
                    nwarning += 1
                rsp.Status = int(self.Pending)
                rsp.NumberOfRemainingSubOperations = nop - ncompleted
                rsp.NumberOfCompletedSubOperations = ncompleted
                rsp.NumberOfFailedSubOperations = nfailed
                rsp.NumberOfWarningSubOperations = nwarning
                ncompleted += 1

                # send response
                self.DIMSE.Send(rsp, self.pcid, self.ACSE.MaxPDULength)

        except StopIteration:
            # send final response
            rsp = C_MOVE_ServiceParameters()
            rsp.MessageIDBeingRespondedTo = msg.MessageID.value
            rsp.AffectedSOPClassUID = msg.AffectedSOPClassUID.value
            rsp.NumberOfRemainingSubOperations = nop - ncompleted
            rsp.NumberOfCompletedSubOperations = ncompleted
            rsp.NumberOfFailedSubOperations = nfailed
            rsp.NumberOfWarningSubOperations = nwarning
            rsp.Status = int(self.Success)
            self.DIMSE.Send(rsp, self.pcid, self.ACSE.MaxPDULength)
            ass.Release(0)

class PatientRootMoveSOPClass(PatientRootQueryRetrieveSOPClass,
                              QueryRetrieveMoveSOPClass):
    UID = '1.2.840.10008.5.1.4.1.2.1.2'

class StudyRootMoveSOPClass(StudyRootQueryRetrieveSOPClass,
                            QueryRetrieveMoveSOPClass):
    UID = '1.2.840.10008.5.1.4.1.2.2.2'

class PatientStudyOnlyMoveSOPClass(PatientStudyOnlyQueryRetrieveSOPClass,
                                   QueryRetrieveMoveSOPClass):
    UID = '1.2.840.10008.5.1.4.1.2.3.2'


# C-GET SOP Classes for QR
class QueryRetrieveGetSOPClass(QueryRetrieveServiceClass):
    OutOfResourcesNumberOfMatches = Status(
        'Failure',
        'Refused: Out of resources - Unable to calcultate number of matches',
        range(0xA701, 0xA701 + 1)
    )

    OutOfResourcesUnableToPerform = Status(
        'Failure',
        'Refused: Out of resources - Unable to perform sub-operations',
        range(0xA702, 0xA702 + 1)
    )

    IdentifierDoesNotMatchSOPClass = Status(
        'Failure',
        'Identifier does not match SOP Class',
        range(0xA900, 0xA900 + 1)
    )
    UnableToProcess = Status(
        'Failure',
        'Unable to process',
        range(0xC000, 0xCFFF + 1)
    )
    Cancel = Status(
        'Cancel',
        'Sub-operations terminated due to Cancel indication',
        range(0xFE00, 0xFE00 + 1)
    )
    Warning = Status(
        'Warning',
        'Sub-operations Complete - One or more Failures or Warnings',
        range(0xB000, 0xB000 + 1)
    )
    Success = Status(
        'Success',
        'Sub-operations Complete - No Failure or Warnings',
        range(0x0000, 0x0000 + 1)
    )
    Pending = Status(
        'Pending',
        'Sub-operations are continuing',
        range(0xFF00, 0xFF00 + 1)
    )

    def SCU(self, ds, msgid):
        # build C-GET primitive
        cget = C_GET_ServiceParameters()
        cget.MessageID = msgid
        cget.AffectedSOPClassUID = self.UID
        cget.Priority = 0x0002
        cget.Identifier = encode(ds,
                                         self.transfersyntax.is_implicit_VR,
                                         self.transfersyntax.is_little_endian)
        cget.Identifier = BytesIO(cget.Identifier)
        # send c-get primitive
        self.DIMSE.Send(cget, self.pcid, self.maxpdulength)

        while 1:
            # receive c-store
            msg, id = self.DIMSE.Receive(Wait=True)
            if msg.__class__ == C_GET_ServiceParameters:
                if self.Code2Status(msg.Status.value).Type == 'Pending':
                    # pending. intermediate C-GET response
                    pass
                else:
                    # last answer
                    break
            elif msg.__class__ == C_STORE_ServiceParameters:
                # send c-store response
                rsp = C_STORE_ServiceParameters()
                rsp.MessageIDBeingRespondedTo = msg.MessageID
                rsp.AffectedSOPInstanceUID = msg.AffectedSOPInstanceUID
                rsp.AffectedSOPClassUID = msg.AffectedSOPClassUID
                status = None
                try:
                    d = decode(
                        msg.DataSet, self.transfersyntax.is_implicit_VR,
                        self.transfersyntax.is_little_endian)
                except:
                    # cannot understand
                    status = CannotUnderstand

                SOPClass = UID2SOPClass(d.SOPClassUID)
                status = self.AE.OnReceiveStore(SOPClass, d)
                rsp.Status = int(status)

                self.DIMSE.Send(rsp, id, self.maxpdulength)

class PatientRootGetSOPClass(PatientRootQueryRetrieveSOPClass,
                             QueryRetrieveGetSOPClass):
    UID = '1.2.840.10008.5.1.4.1.2.1.3'

class StudyRootGetSOPClass(StudyRootQueryRetrieveSOPClass,
                           QueryRetrieveGetSOPClass):
    UID = '1.2.840.10008.5.1.4.1.2.2.3'

class PatientStudyOnlyGetSOPClass(PatientStudyOnlyQueryRetrieveSOPClass,
                                  QueryRetrieveGetSOPClass):
    UID = '1.2.840.10008.5.1.4.1.2.3.3'


# BASIC WORKLIST SOP Classes
class BasicWorklistSOPClass(BasicWorklistServiceClass):
    pass

class ModalityWorklistInformationFindSOPClass(BasicWorklistSOPClass,
                                              ModalityWorklistServiceSOPClass):
    UID = '1.2.840.10008.5.1.4.31'


d = dir()

def UID2SOPClass(UID):
    """
    Parameters
    ----------
    UID - str
        The class UID as a string
    
    Returns
    -------
    SOPClass object corresponding to the given UID
    """
    for ss in d:
        if hasattr(eval(ss), 'UID'):
            tmpuid = getattr(eval(ss), 'UID')
            if tmpuid == UID:
                return eval(ss)
    return None
