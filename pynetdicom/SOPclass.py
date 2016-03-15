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

        # If Association is Aborted before we receive the response
        #   then we hang here
        msg, _ = self.DIMSE.Receive(Wait=True, 
                                    dimse_timeout=self.DIMSE.dimse_timeout)
        
        if msg is None:
            return None
        
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
        except NotImplementedError:
            pass
        except:
            logger.exception("Exception raised by the AE.on_c_echo() callback")
        
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

    def SCU(self, dataset, msg_id, priority=0x0000):
        """
        I think perhaps we should rewrite the .SCU and .SCP methods so
        they return the DIMSE message that should be sent to the peer
        
        Parameters
        ----------
        dataset - pydicom.dataset
            The DICOM dataset to send
        msg_id - int
            The DIMSE message ID value to use
        priority - int, optional
            The message priority, must be one of the following:
                0x0002 Low
                0x0001 High
                0x0000 Medium
                
        Returns
        -------
        """
        # Build C-STORE request primitive
        c_store_primitive = C_STORE_ServiceParameters()
        c_store_primitive.MessageID = msg_id
        c_store_primitive.AffectedSOPClassUID = dataset.SOPClassUID
        c_store_primitive.AffectedSOPInstanceUID = dataset.SOPInstanceUID
        
        # Message priority
        if priority in [0x0000, 0x0001, 0x0002]:
            c_store_primitive.Priority = priority
        else:
            logger.warning("StorageServiceClass.SCU(): Invalid priority value "
                                                            "'%s'" %priority)
            c_store_primitive.Priorty = 0x0000
        
        # Encode the dataset using the agreed transfer syntax
        transfer_syntax = self.presentation_context.TransferSyntax[0]
        c_store_primitive.DataSet = encode(dataset,
                                           transfer_syntax.is_implicit_VR,
                                           transfer_syntax.is_little_endian)

        c_store_primitive.DataSet = BytesIO(c_store_primitive.DataSet)
        
        # If we failed to encode our dataset, abort the association and return
        if c_store_primitive.DataSet is None:
            return None

        # Send C-STORE request primitive to DIMSE
        self.DIMSE.Send(c_store_primitive, 
                        self.MessageID, 
                        self.maxpdulength)

        # Wait for C-STORE response primitive
        ans, _ = self.DIMSE.Receive(Wait=True, 
                                    dimse_timeout=self.DIMSE.dimse_timeout)

        return self.Code2Status(ans.Status.value)

    def SCP(self, msg):
        try:
            DS = decode(msg.DataSet,
                        self.transfersyntax.is_implicit_VR,
                        self.transfersyntax.is_little_endian)
        except:
            status = self.CannotUnderstand
            logger.error("StorageServiceClass failed to decode the dataset")

        # Create C-STORE response primitive
        rsp = C_STORE_ServiceParameters()
        rsp.MessageIDBeingRespondedTo = msg.MessageID
        rsp.AffectedSOPInstanceUID = msg.AffectedSOPInstanceUID
        rsp.AffectedSOPClassUID = msg.AffectedSOPClassUID
        
        # ApplicationEntity's on_c_store callback 
        try:
            self.AE.on_c_store(self, DS)
            status = self.Success
        except Exception as e:
            logger.exception("Exception in the ApplicationEntity.on_c_store() "
                                                                "callback")
            status = self.CannotUnderstand

        # Check that the supplied dataset UID matches the presentation context
        #   ID
        if self.UID != self.sopclass:
            status = self.DataSetDoesNotMatchSOPClassFailure
            logger.info("Store request's dataset UID does not match the "
                                                        "presentation context")

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
            ans, id = self.DIMSE.Receive(Wait=False, 
                                    dimse_timeout=self.DIMSE.dimse_timeout)
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
            ans, _ = self.DIMSE.Receive(Wait=False, 
                                    dimse_timeout=self.DIMSE.dimse_timeout)
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
            
            logger.info("Find Response: (Pending)")
            logger.info('')
            
            logger.info('# DICOM Dataset')
            for elem in d:
                logger.info(elem)
            logger.info('')
            
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
        range(0xA701, 0xA701 + 1)    )
    OutOfResourcesUnableToPerform = Status(
        'Failure',
        'Refused: Out of resources - Unable to perform sub-operations',
        range(0xA702, 0xA702 + 1)    )
    MoveDestinationUnknown = Status(
        'Failure',
        'Refused: Move destination unknown',
        range(0xA801, 0xA801 + 1)    )
    IdentifierDoesNotMatchSOPClass = Status(
        'Failure',
        'Identifier does not match SOP Class',
        range(0xA900, 0xA900 + 1)    )
    UnableToProcess = Status(
        'Failure',
        'Unable to process',
        range(0xC000, 0xCFFF + 1)    )
    Cancel = Status(
        'Cancel',
        'Sub-operations terminated due to Cancel indication',
        range(0xFE00, 0xFE00 + 1)    )
    Warning = Status(
        'Warning',
        'Sub-operations Complete - One or more Failures or Warnings',
        range(0xB000, 0xB000 + 1)    )
    Success = Status(
        'Success',
        'Sub-operations Complete - No Failure or Warnings',
        range(0x0000, 0x0000 + 1)    )
    Pending = Status(
        'Pending',
        'Sub-operations are continuing',
        range(0xFF00, 0xFF00 + 1)    )

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
            ans, id = self.DIMSE.Receive(Wait=False, 
                                    dimse_timeout=self.DIMSE.dimse_timeout)
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
        range(0xA701, 0xA701 + 1)    )
    OutOfResourcesUnableToPerform = Status(
        'Failure',
        'Refused: Out of resources - Unable to perform sub-operations',
        range(0xA702, 0xA702 + 1)    )
    IdentifierDoesNotMatchSOPClass = Status(
        'Failure',
        'Identifier does not match SOP Class',
        range(0xA900, 0xA900 + 1)    )
    UnableToProcess = Status(
        'Failure',
        'Unable to process',
        range(0xC000, 0xCFFF + 1)    )
    Cancel = Status(
        'Cancel',
        'Sub-operations terminated due to Cancel indication',
        range(0xFE00, 0xFE00 + 1)    )
    Warning = Status(
        'Warning',
        'Sub-operations Complete - One or more Failures or Warnings',
        range(0xB000, 0xB000 + 1)    )
    Success = Status(
        'Success',
        'Sub-operations Complete - No Failure or Warnings',
        range(0x0000, 0x0000 + 1)    )
    Pending = Status(
        'Pending',
        'Sub-operations are continuing',
        range(0xFF00, 0xFF00 + 1)    )

    def SCU(self, ds, msg_id, priority=2):
        # build C-GET primitive
        cget = C_GET_ServiceParameters()
        cget.MessageID = msg_id
        cget.AffectedSOPClassUID = self.UID
        cget.Priority = 0x0002
        cget.Identifier = encode(ds,
                                 self.transfersyntax.is_implicit_VR,
                                 self.transfersyntax.is_little_endian)
        cget.Identifier = BytesIO(cget.Identifier)
        # send c-get primitive
        self.DIMSE.Send(cget, self.pcid, self.maxpdulength)

        logger.info('Get SCU Request Identifiers:')
        logger.info('')
        logger.info('# DICOM Dataset')
        for elem in ds:
            logger.info(elem)
        logger.info('')

        while 1:
            
            msg, id = self.DIMSE.Receive(Wait=True, 
                                    dimse_timeout=self.DIMSE.dimse_timeout)
            
            # Received a C-GET response
            if msg.__class__ == C_GET_ServiceParameters:
                
                status = self.Code2Status(msg.Status.value).Type
                
                # If the Status is "Pending" then the processing of 
                #   matches and suboperations is initiated or continuing
                if status == 'Pending':
                    pass
                    
                # If the Status is "Success" then processing is complete
                elif status == "Success":
                    pass
                
                # All other possible responses
                else:
                    
                    break
            
            # Received a C-STORE response
            elif msg.__class__ == C_STORE_ServiceParameters:
                
                rsp = C_STORE_ServiceParameters()
                rsp.MessageIDBeingRespondedTo = msg.MessageID
                rsp.AffectedSOPInstanceUID = msg.AffectedSOPInstanceUID
                rsp.AffectedSOPClassUID = msg.AffectedSOPClassUID
                status = None
                #try:
                d = decode(msg.DataSet, 
                               self.transfersyntax.is_implicit_VR,
                               self.transfersyntax.is_little_endian)
                #logger.debug('SCU', d)
                #except:
                #    # cannot understand
                #    status = CannotUnderstand

                SOPClass = UID2SOPClass(d.SOPClassUID)
                
                # Callback
                status = self.AE.on_c_store(SOPClass, d)
                
                # Send Store confirmation
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

from pydicom._uid_dict import UID_dictionary
from pydicom.uid import UID

def sop_class_factory(class_uid, parent_class, sop_name='Unknown SOP Class'):
    """
    SOP Class class Factory
    Modifies the pydicom _uid_dict.UID_dictionary to add a ServiceClass
    something something
    
    A list of the supported Standard SOP Classes for each service class is
    available in PS3.4. * indicates those Service Classes supported by pynetdicom
        A. *Verification Service Class
        B. *Storage Service Class
        C. *Query/Retrieve Service Class
        F. Procedure Strep SOP Classes
        H. Print Management Service Class
        I. Media Storage Service Class
        J. Storage Commitment Service Class
        K. Basic Worklist Management Service
        N. Softcopy Presentation State Storage SOP Classes
        O. Structured Reporting Storage SOP Classes
        P. Application Event Logging Service Class
        Q. Relevant Patient Information Query Service Class
        R. Instance Availability Notification Service Class
        S. Media Creation Management Service Class
        T. Hanging Protocol Storage Service Class
        U. Ganging Protocol Query/Retrieve Service Class
        V. Substance Administration Query Service Class
        W. Color Palette Storage Service Class
        X. Color Palette Query/Retrieve Service Class
        Y. Instance and Frame Level Retrieve SOP Classes
        Z. Composite Instance Retrieve Without Bulk Data SOP Classes
        AA. Opthalmic Refractive Measurements Storage SOP Classes
        BB. Implant Template Query/Retrieve Service Classes
        CC. Unified Procedure Step Service and SOP Classes
        DD. RT Machine Verification Service Classes
        EE. Display System Management Service Class
    
    # Example usage - UID present in pydicom's UID dictionary
    class = class_factory('1.2.840.10008.5.1.4.1.1.2', StorageServiceClass)
    
    # Should return these values...
    class.UID  # '1.2.840.10008.5.1.4.1.1.2' pydicom.uid.UID
    class.Name # 'CT Image Storage' str
    class.Type # 'Storage SOP Class' str
    class.Info # '' str
    class.is_retired # '' str
    
    # Example Usage - UID not present in pydicom's UID dictionary
    class = class_factory(1.2.840.10008.5.1.4.1.1.2.2', StorageServiceClass, name='Unknown SOP Class')
    # Should return these values...
    class.UID  # '1.2.840.10008.5.1.4.1.1.2.2'
    class.Name # 'Unknown SOP Class'
    class.Type # 'Storage SOP Class'
    class.Info # ''
    class.is_retired # ''
    
    #status = class.SCU('ct_dataset.dcm')
    
    # The Presentation Context the SOP Class is operating under
    class.presentation_context = context 

    # This should really be a DIMSE attribute rather than a primitive attribute
    #sop_class.maxpdulength = self.acse.MaxPDULength
    
    # Used by SCU/SCP to Send/Receive self but seems inelegant
    sop_class.DIMSE = self.dimse
    
    # Not sure why we need the ACSE -> presentation context checking?
    #sop_class.ACSE = self.acse
    
    # Better
    class.scu_callback = None
    class.scp_callback = self.ae.on_c_store
    
    # Run SOPClass in SCP mode
    class.SCP(dimse_msg)
    
    # Run SOPClass in SCU mode
    class.SCU(*args)
    
    Example usage - UID not present in pydicom's UID_dictionary:
    
    
    Parameters
    ----------
    class_name - str
        The variable name for the class
    parent_class - pynetdicom.SOPclass.ServiceClass subclass
        One of the implemented Service Classes:
            VerificationServiceClass - Only 1.2.840.10008.1.1
            StorageServiceClass - Tables B.5-1 and B.6-1 in PS3.4
            QueryRetrieveFindSOPClass - Annex C.4.1 in PS3.4
            QueryRetrieveMoveSOPClass - Annex C.4.2 in PS3.4
            QueryRetrieveGetSOPClass - Annex C.4.3 in PS3.4
            ModalityWorklistServiceSOPClass - Annex K in PS3.4
    """
    if parent_class in [VerificationServiceClass, 
                         StorageServiceClass,
                         QueryRetrieveFindSOPClass,
                         QueryRetrieveMoveSOPClass,
                         QueryRetrieveGetSOPClass,
                         ModalityWorklistServiceSOPClass]:

        cls = parent_class()
        cls.UID = UID(class_uid)
        
        try:
            cls.UID.is_valid()
        except:
            pass
            
        if cls.UID.is_transfer_syntax:
            raise ValueError("Supplied UID belongs to a Transfer Syntax")
        
        # Check with pydicom to see if its a known SOP Class
        if cls.UID in UID_dictionary.keys():
            cls.name = UID.name
            cls.type = UID.type
            cls.info = UID.info
            cls.is_retired = UID.is_retired
            cls.presentation_context = None
            
        else:
            cls.name = sop_name
            cls.type = None
            cls.info = None
            cls.is_retired = None
            cls.presentation_context = None

"""
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

    def SCU(self, dataset, msg_id, priority=0x0000):
        # Build C-STORE request primitive
        c_store_primitive = C_STORE_ServiceParameters()
        c_store_primitive.MessageID = msg_id
        c_store_primitive.AffectedSOPClassUID = dataset.SOPClassUID
        c_store_primitive.AffectedSOPInstanceUID = dataset.SOPInstanceUID
        
        # Message priority
        if priority in [0x0000, 0x0001, 0x0002]:
            c_store_primitive.Priority = priority
        else:
            logger.warning("StorageServiceClass.SCU(): Invalid priority value "
                                                            "'%s'" %priority)
            c_store_primitive.Priorty = 0x0000
        
        # Encode the dataset using the agreed transfer syntax
        transfer_syntax = self.presentation_context.TransferSyntax[0]
        c_store_primitive.DataSet = encode(dataset,
                                           transfer_syntax.is_implicit_VR,
                                           transfer_syntax.is_little_endian)

        c_store_primitive.DataSet = BytesIO(c_store_primitive.DataSet)
        
        # If we failed to encode our dataset, abort the association and return
        if c_store_primitive.DataSet is None:
            return None

        # Send C-STORE request primitive to DIMSE
        self.DIMSE.Send(c_store_primitive, 
                        self.MessageID, 
                        self.maxpdulength)

        # Wait for C-STORE response primitive
        ans, _ = self.DIMSE.Receive(Wait=True, 
                                    dimse_timeout=self.DIMSE.dimse_timeout)

        return self.Code2Status(ans.Status.value)

    def SCP(self, msg):
        try:
            DS = decode(msg.DataSet,
                        self.transfersyntax.is_implicit_VR,
                        self.transfersyntax.is_little_endian)
        except:
            status = self.CannotUnderstand
            logger.error("StorageServiceClass failed to decode the dataset")

        # Create C-STORE response primitive
        rsp = C_STORE_ServiceParameters()
        rsp.MessageIDBeingRespondedTo = msg.MessageID
        rsp.AffectedSOPInstanceUID = msg.AffectedSOPInstanceUID
        rsp.AffectedSOPClassUID = msg.AffectedSOPClassUID
        
        # ApplicationEntity's on_c_store callback 
        try:
            self.AE.on_c_store(self, DS)
            status = self.Success
        except Exception as e:
            logger.exception("Exception in the ApplicationEntity.on_c_store() "
                                                                "callback")
            status = self.CannotUnderstand

        # Check that the supplied dataset UID matches the presentation context
        #   ID
        if self.UID != self.sopclass:
            status = self.DataSetDoesNotMatchSOPClassFailure
            logger.info("Store request's dataset UID does not match the "
                                                        "presentation context")

        rsp.Status = int(status)
        self.DIMSE.Send(rsp, self.pcid, self.ACSE.MaxPDULength)
"""

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
