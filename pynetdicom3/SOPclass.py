
import logging
import time

from pynetdicom3.dsutils import *
from pynetdicom3.DIMSEparameters import *

logger = logging.getLogger('pynetdicom3.SOPclass')

def class_factory(name, uid, BaseClass):
    """
    Generates a SOP Class subclass of `BaseClass` called `name`

    Parameters
    ----------
    name : str
        The name of the SOP class
    uid : str
        The UID of the SOP class
    BaseClass : pynetdicom3.SOPclass.ServiceClass subclass
        One of the following Service classes:
            VerificationServiceClass
            StorageServiceClass
            QueryRetrieveFindServiceClass
            QueryRetrieveGetServiceClass
            QueryRetrieveMoveServiceClass

    Returns
    -------
    subclass of BaseClass
        The new class
    """
    def __init__(self):
        BaseClass.__init__(self)

    new_class = type(name, (BaseClass,), {"__init__": __init__})
    new_class.UID = uid

    return new_class

def _generate_service_sop_classes(class_list, service_class):
    for name in class_list.keys():
        cls = class_factory(name, class_list[name], service_class)
        globals()[cls.__name__] = cls


class Status(object):
    def __init__(self, Type, Description, CodeRange):
        self.Type = Type
        self.Description = Description
        self.CodeRange = CodeRange

    def __int__(self):
        return self.CodeRange[0]

    def __repr__(self):
        return self.Type

    def __str__(self):
        return self.Type + ' ' + self.Description


# DICOM SERVICE CLASS BASE
class ServiceClass(object):
    """

    """
    def Code2Status(self, code):
        """
        Parameters
        ----------
        code : int
            The status code value from the (0000,0900) dataset element

        Returns
        -------
        obj : pynetdicom3.SOPclass.Status
            The Status object for the `code`
        """
        for dd in dir(self):
            getattr(self, dd).__class__
            obj = getattr(self, dd)

            if obj.__class__ == Status:
                if code in obj.CodeRange:
                    return obj

        # Unknown status
        return None


class VerificationServiceClass(ServiceClass):
    Success = Status('Success', '', range(0x0000, 0x0000 + 1))

    def SCP(self, msg):
        """
        When the local AE is acting as an SCP for the VerificationSOPClass
        and a C-ECHO request is received then create a C-ECHO response
        primitive and send it to the peer AE via the DIMSE provider

        Parameters
        ----------
        msg : pynetdicom3.DIMSEparameters.C_ECHO_ServiceParameters
            The C-ECHO request primitive sent by the peer
        """
        # Create C-ECHO response primitive
        rsp = C_ECHO_ServiceParameters()
        rsp.AffectedSOPClassUID = '1.2.840.10008.1.1'
        rsp.MessageIDBeingRespondedTo = msg.MessageID
        rsp.Status = int(self.Success)

        # Try and run the user on_c_echo callback
        try:
            self.AE.on_c_echo()
        except:
            logger.exception("Exception in the AE.on_c_echo() callback")

        # Send primitive
        self.DIMSE.Send(rsp, self.pcid, self.maxpdulength)


class StorageServiceClass(ServiceClass):
    # Storage Service specific status code values - PS3.4 Annex B.2.3
    # General status code values - PS3.7 9.1.1.1.9 - not used?
    #
    # Note that the response/confirmation primitives do NOT contain a dataset
    #   and hence only the Status parameter of the primitive is of interest
    OutOfResources = Status('Failure',
                            'Refused: Out of resources',
                            range(0xA700, 0xA7FF + 1))
    DataSetDoesNotMatchSOPClassFailure = Status('Failure',
                                    'Error: Data Set does not match SOP Class',
                                    range(0xA900, 0xA9FF + 1))
    CannotUnderstand = Status('Failure',
                              'Error: Cannot understand',
                              range(0xC000, 0xCFFF + 1))
    CoercionOfDataElements = Status('Warning',
                                    'Coercion of Data Elements',
                                    range(0xB000, 0xB000 + 1))
    DataSetDoesNotMatchSOPClassWarning = Status('Warning',
                                            'Data Set does not match SOP Class',
                                            range(0xB007, 0xB007 + 1))
    ElementDisgarded = Status('Warning',
                              'Element Discarded',
                              range(0xB006, 0xB006 + 1))
    Success = Status('Success', '', range(0x0000, 0x0000 + 1))

    def SCP(self, msg):
        try:
            dataset = decode(msg.DataSet,
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
            status = self.AE.on_c_store(dataset)
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


class QueryRetrieveFindServiceClass(ServiceClass):
    """
    PS3.4 C.1.4 C-FIND Service Definition
    -------------------------------------
    - The SCU requests that the SCP perform a match of all the keys
      specified in the Identifier  of the request, against the information
      that it possesses, to the level (Patient, Study, Series or Composite
      Object Instance) specified in the request. Identifier refers to the
      Identifier service parameter of the C-FIND

    - The SCP generates a C-FIND response for each match with an Identifier
      containing the values of all key fields and all known Attributes
      requested. All such responses will contain a status of Pending.
      A status of Pending indicates that the process of matching is not
      complete

    - When the process of matching is complete a C-FIND response is sent
      with a status of Success and no Identifier.

    - A Refused or Failed response to a C-FIND request indicates that the
      SCP is unable to process the request.

    - The SCU may cancel the C-FIND service by issuing a C-FIND-CANCEL
      request at any time during the processing of the C-FIND service.
      The SCP will interrupt all matching and return a status of Canceled.

    Patient Root QR Information Model
    =================================
    PS3.4 Table C.6-1, C.6-2

    Patient Level
    -------------
    Required Key
    - Patient's Name (0010,0010)
    Unique Key
    - Patient ID (0010,0020)

    Study Level
    -----------
    Required Keys
    - Study Date (0008,0020)
    - Study Time (0008,0030)
    - Accession Number (0008,0050)
    - Study ID (0020,0010)
    Unique Key
    - Study Instance UID (0020,000D)

    Series Level
    ------------
    Required Keys
    - Modality (0008,0060)
    - Series Number (0020,0011)
    Unique Key
    - Series Instance UID (0020,000E)

    Composite Object Instance Level
    -------------------------------
    Required Key
    - Instance Number (0020,0013)
    Unique Key
    - SOP Instance UID (0008,0018)


    Study Root QR Information Model
    ===============================
    PS3.4 C.6.2.1

    Study Level
    -----------
    Required Keys
    - Study Date (0008,0020)
    - Study Time (0008,0030)
    - Accession Number (0008,0050)
    - Patient's Name (0010,0010)
    - Patient ID (0010,0020)
    - Study ID (0020,0010)
    Unique Key
    - Study Instance UID (0020,000D)

    Series Level/Composite Object Instance Level
    --------------------------------------------
    As for Patient Root QR Information Model


    """
    # PS3.4 Annex C.4.1.1.4
    OutOfResources = Status('Failure',
                            'Refused: Out of resources',
                            range(0xA700, 0xA700 + 1))
    IdentifierDoesNotMatchSOPClass = Status('Failure',
                                            "Identifier does not match SOP "
                                            "Class",
                                            range(0xA900, 0xA900 + 1))
    UnableToProcess = Status('Failure',
                             'Unable to process',
                             range(0xC000, 0xCFFF + 1))
    MatchingTerminatedDueToCancelRequest = Status('Cancel',
                                                  "Matching terminated due to "
                                                  "Cancel request",
                                                  range(0xFE00, 0xFE00 + 1))
    Success = Status('Success',
                     'Matching is complete - No final Identifier is supplied',
                     range(0x0000, 0x0000 + 1))
    Pending = Status('Pending',
                     "Matches are continuing - Current Match is supplied "
                     "and any Optional Keys were supported in the same manner "
                     "as 'Required Keys'",
                     range(0xFF00, 0xFF00 + 1))
    PendingWarning = Status("Pending",
                            "Matches are continuing - Warning that one or more "
                            "Optional Keys were not supported for existence "
                            "and/or matching for this identifier",
                            range(0xFF01, 0xFF01 + 1))

    def SCP(self, msg):
        """
        PS3.4 Annex C.1.3
        In order to serve as an QR SCP, a DICOM AE possesses information about
        the Attributes of a number of stored Composite Object Instances. This
        information is organised into a well defined QR Information Model.
        This QR Information Model shall be a standard QR Information Model.

        A specific SOP Class of the QR Service Class consists of an Information
        Model Definition and a DIMSE-C Service Group.

        PS3.4 Annex C.2
        A QR Information Model contains:
        - an Entity-Relationship Model Definition: a hierarchy of entities, with
          Attributes defined for each level in the hierarchy (eg Patient, Study,
          Series, Composite Object Instance)
        - a Key Attributes Definition: Attributes should be defined at each
          level in the Entity-Relationship Model. An Identifier shall contain
          values to be matched against the Attributes of the Entities in a
          QR Information Model. For any query, the set of entities for which
          Attributes are returned shall be determined by the set of Key
          Attributes specified in the Identifier that have corresponding
          matches on entities managed by the SCP associated with the query.

        All Attributes shall be either a Unique, Required or Optional Key. 'Key
        Attributes' refers to these three types.

        Unique Keys
        -----------
        At each level in the Entity-Relationship Model (ERM), one Attribute
        shall be defined as a Unique Key. A single value in a Unique Key
        Attribute shall uniquely identify a single entity at a given level (ie
        two entities at the same level may not have the same Unique Key value).

        All entities managed by C-FIND SCPs shall have a specific non-zero
        length Unique Key value.

        Unique Keys may be contained in the Identifier of a C-FIND request.

        Required Keys
        -------------
        At each level in the ERM, a set of Attributes shall be defined as
        Required Keys. Required Keys imply the SCP of a C-FIND shall support
        matching based on a value contained in a Required Key of the C-FIND
        required. Multiple entities may have the same value for Required Keys.

        C-FIND SCPs shall support existence and matching of all Required Keys
        defined by a QR Information Model. If a C-FIND SCP manages an entity
        with a Required Key of zero length, the value is considered unknown
        and all matching against the zero length Required Key shall be
        considered a successful match.

        Required Keys may be contained in the Identifier of a C-FIND request.

        Optional Keys
        -------------
        At each level in the ERM, a set of Attributes shall be defined as
        Optional Keys. Optional Keys may have three different types of
        behaviour depending on support for existence and/or matching by the
        C-FIND SCP.
        1. If the SCP doesnt support the existence of the Optional Key, then
           the Attribute shall not be returned in C-FIND responses
        2. If the SCP supports existence of the Optional Key but does not
           support matching on the Optional Key, then the Optional Key shall be
           processed in the same manner as a zero length Required Key.
        3. If the SCP supports both the existence and matching of the Optional
           Key, then the Key shall be processed in the same manner as a Required
           Key.

        Optional Keys may be contained in the Identifier of a C-FIND request.

        Attribute Matching
        ==================
        The following types of matching may be performed on Key Attributes:
        * Single Value
        * List of UID
        * Universal
        * Wild Card
        * Range
        * Sequence

        Matching requires special characters (*, ?, -, =, \) which need not be
        part of the character repertoire for the VR of the Key Attribute

        The total length of the Key Attribute may exceed the length as specified
        in the VR in PS3.5. The VM may be larger than that specified in PS3.6.

        Single Value Matching
        ---------------------
        single value matching shall be performed if the value specified for a
        Key Attribute in a request is non-zero length and it is:
        a. Not a date or time or datetime and contains not wild card characters
        b. A date or time or datetime and contains a single date or time or
           datetime with no '-'.

        Except for Attributes with a PN VR, only entites with values that
        exactly match are included. Matching is case-sensitive.

        For PN VRs, an application may perform literal matching that is either
        case-sensitive or that is insensitive to some or all aspects of case,
        position, accent or other character encoding variants

        Blah blah, this is user implementation stuff

        ...

        Three standard QR Information Models are defined:
        * Patient Root
        * Study Root
        * Patient/Study Only

        Patient Root QR Information Model
        ---------------------------------
        The Patient Root is based on a four level hierarchy: Patient, Study,
        Series, Composite Object Instance.

        The Patient level is the top level and contains Attributes associated
        with the Patietn Information Entity of the Composite IODs (PS3.3).
        Patient IEs are modality independent.

        The Study level contains Attributes associated with the Series, Frame of
        Reference and Equipment IEs of the Composite IODs. A series belongs
        to a single study, which may have multiple series. Series IEs are
        modality dependant.

        The Composite Object Instance level contains Attributes associated with
        the Composite object IE of the Composite IODs. A Composite Object
        Instance belongs to a single series, which may have multiple Composite
        Object Instances.

        Study Root
        ----------
        The Study Root is identical to the Patient Root except the top level is
        the Study level. Attributes of patients are considered to be Attributes
        of studies

        Patient/Study Root
        ------------------
        Retired (PS3.4-2004)

        Parameters
        ----------
        msg : pynetdicom3.DIMSEmessage.C_FIND_RQ
            The C_FIND request primitive received from the peer
        """
        dataset = decode(msg.Identifier,
                         self.transfersyntax.is_implicit_VR,
                         self.transfersyntax.is_little_endian)

        # Build C-FIND response primitive
        c_find_rsp = C_FIND_ServiceParameters()
        c_find_rsp.MessageIDBeingRespondedTo = msg.MessageID
        c_find_rsp.AffectedSOPClassUID = msg.AffectedSOPClassUID

        logger.info('Find SCP Request Identifiers:')
        logger.info('')
        logger.debug('# DICOM Data Set')
        for elem in dataset:
            logger.info(elem)
        logger.info('')

        # Callback
        try:
            matches = self.AE.on_c_find(dataset)
        except:
            logger.exception('Exception in on_c_find()')
            matches = []

        for ii, instance in enumerate(matches):
            c_find_rsp.Identifier = BytesIO(encode(instance,
                                            self.transfersyntax.is_implicit_VR,
                                            self.transfersyntax.is_little_endian))

            # Send response
            c_find_rsp.Status = int(self.Pending)

            logger.info('Find SCP Response: %s (Pending)' %(ii + 1))

            self.DIMSE.Send(c_find_rsp, self.pcid, self.ACSE.MaxPDULength)

            logger.debug('Find SCP Response Identifiers:')
            logger.debug('')
            logger.debug('# DICOM Dataset')
            for elem in instance:
                logger.debug(elem)
            logger.debug('')

        # Send final response
        c_find_rsp.Status = int(self.Success)

        logger.info('Find SCP Response: %s (Success)' %(ii + 2))

        self.DIMSE.Send(c_find_rsp, self.pcid, self.ACSE.MaxPDULength)

class QueryRetrieveMoveServiceClass(ServiceClass):
    OutOfResourcesNumberOfMatches = Status('Failure',
        'Refused: Out of resources - Unable to calcultate number of matches',
        range(0xA701, 0xA701 + 1)    )
    OutOfResourcesUnableToPerform = Status('Failure',
        'Refused: Out of resources - Unable to perform sub-operations',
        range(0xA702, 0xA702 + 1)    )
    MoveDestinationUnknown = Status('Failure',
                                    'Refused: Move destination unknown',
                                    range(0xA801, 0xA801 + 1)    )
    IdentifierDoesNotMatchSOPClass = Status('Failure',
        'Identifier does not match SOP Class',
        range(0xA900, 0xA900 + 1)    )
    UnableToProcess = Status('Failure',
        'Unable to process',
        range(0xC000, 0xCFFF + 1)    )
    Cancel = Status('Cancel',
        'Sub-operations terminated due to Cancel indication',
        range(0xFE00, 0xFE00 + 1)    )
    Warning = Status('Warning',
        'Sub-operations Complete - One or more Failures or Warnings',
        range(0xB000, 0xB000 + 1)    )
    Success = Status('Success',
        'Sub-operations Complete - No Failure or Warnings',
        range(0x0000, 0x0000 + 1)    )
    Pending = Status('Pending',
        'Sub-operations are continuing',
        range(0xFF00, 0xFF00 + 1)    )

    def SCP(self, msg):
        attributes = decode(msg.Identifier,
                            self.transfersyntax.is_implicit_VR,
                            self.transfersyntax.is_little_endian)

        # Build C-MOVE response primitive
        c_move_rsp = C_MOVE_ServiceParameters()
        c_move_rsp.MessageIDBeingRespondedTo = msg.MessageID
        c_move_rsp.AffectedSOPClassUID = msg.AffectedSOPClassUID
        c_move_rsp.Identifier = msg.Identifier

        logger.info('Move SCP Request Identifiers:')
        logger.info('')
        logger.info('# DICOM Data Set')
        for elem in attributes:
            logger.info(elem)
        logger.info('')

        # The user is responsible for returning the matching Instances
        try:
            matches = self.AE.on_c_move(attributes, msg.MoveDestination)
        except:
            logger.error('Exception in on_c_move')
            c_get_rsp.Status = int(self.UnableToProcess)
            logger.info('Move SCP Response %s (Failure)' %ii)
            self.DIMSE.Send(c_move_rsp, self.pcid, self.maxpdulength)
            return

        # First value is the number of matches
        c_move_rsp.NumberOfRemainingSuboperations = next(matches)
        c_move_rsp.NumberOfCompletedSuboperations = 0
        c_move_rsp.NumberOfFailedSuboperations = 0
        c_move_rsp.NumberOfWarningSuboperations = 0

        # Second value is the addr and port for the move destination if known
        #   None, None if not known
        addr, port = next(matches)

        if None in [addr, port]:
            logger.error('Unknown Move Destination: %s' %msg.MoveDestination.decode('utf-8'))
            c_move_rsp.Status = int(self.MoveDestinationUnknown)
            logger.info('Move SCP Response (Failure)')
            self.DIMSE.Send(c_move_rsp, self.pcid, self.maxpdulength)
            return

        # Request new association with move destination
        #   need (addr, port, aet)
        assoc = self.AE.associate(addr, port, msg.MoveDestination)

        ii = 1
        if assoc.is_established:
            for dataset in matches:
                # Send dataset via C-STORE over new association
                status = assoc.send_c_store(dataset)
                store_status = status.Type

                logger.info('Move SCU: Received Store SCU RSP (%s)' %store_status)

                if store_status == 'Failure':
                    c_move_rsp.NumberOfFailedSuboperations += 1
                elif store_status == 'Warning':
                    c_move_rsp.NumberOfWarningSuboperations += 1
                elif store_status == 'Success':
                    c_move_rsp.NumberOfCompletedSuboperations += 1

                c_move_rsp.NumberOfRemainingSuboperations -= 1

                c_move_rsp.Status = int(self.Pending)

                logger.info('Move SCP Response %s (Pending)' %ii)

                self.DIMSE.Send(c_move_rsp, self.pcid, self.maxpdulength)

                ii += 1

            assoc.release()

        # Send Success C-GET-RSP to peer
        c_move_rsp.Status = int(self.Success)
        logger.info('Move SCP Response %s (Success)' %ii)
        self.DIMSE.Send(c_move_rsp, self.pcid, self.maxpdulength)

class QueryRetrieveGetServiceClass(ServiceClass):
    OutOfResourcesNumberOfMatches = Status('Failure',
                                           'Refused: Out of resources - Unable '
                                           'to calcultate number of matches',
                                           range(0xA701, 0xA701 + 1)    )
    OutOfResourcesUnableToPerform = Status('Failure',
                                           'Refused: Out of resources - Unable '
                                           'to perform sub-operations',
                                           range(0xA702, 0xA702 + 1)    )
    IdentifierDoesNotMatchSOPClass = Status('Failure',
                                            'Identifier does not match SOP '
                                            'Class',
                                            range(0xA900, 0xA900 + 1))
    UnableToProcess = Status('Failure',
                             'Unable to process',
                             range(0xC000, 0xCFFF + 1))
    Cancel = Status('Cancel',
                    'Sub-operations terminated due to Cancel indication',
                    range(0xFE00, 0xFE00 + 1))
    Warning = Status('Warning',
                      'Sub-operations Complete - One or more Failures or '
                      'Warnings',
                      range(0xB000, 0xB000 + 1))
    Success = Status('Success',
                     'Sub-operations Complete - No Failure or Warnings',
                     range(0x0000, 0x0000 + 1))
    Pending = Status('Pending',
                     'Sub-operations are continuing',
                     range(0xFF00, 0xFF00 + 1))

    def SCP(self, msg, priority=2):
        """
        PS3.7 9.1.3.2

        Service Procedure
        -----------------
        Performing DIMSE User
        ~~~~~~~~~~~~~~~~~~~~~
        - When the performer receives a C-GET indication it matches the
          Identifier against the Attributes of known composite SOP Instances
          and generates a C-STORE sub-operation for each match
        - For each match, the performing user initiates a C-STORE sub-operation
          on the same Association as the C-GET.
        - During the processing of the C-GET operation, the performing user may
          issue C-GET response primitives with a status of Pending
        - When the C-GET operation completes (either in success or failure) the
          performing DIMSE user issues a C-GET response with status set to
          either refused, failed or success
        """
        attributes = decode(msg.Identifier,
                            self.transfersyntax.is_implicit_VR,
                            self.transfersyntax.is_little_endian)

        # Build C-GET response primitive
        c_get_rsp = C_GET_ServiceParameters()
        c_get_rsp.MessageIDBeingRespondedTo = msg.MessageID
        c_get_rsp.AffectedSOPClassUID = msg.AffectedSOPClassUID
        c_get_rsp.Identifier = msg.Identifier

        logger.info('Get SCP Request Identifiers:')
        logger.info('')
        logger.debug('# DICOM Data Set')
        for elem in attributes:
            logger.info(elem)
        logger.info('')

        # The user is responsible for returning the matching Instances
        try:
            matches = self.AE.on_c_get(attributes)
        except:
            logger.error('Exception in on_c_get')
            c_get_rsp.Status = int(self.UnableToProcess)
            logger.info('Get SCP Response %s (Failure)' %ii)
            self.DIMSE.Send(c_get_rsp, self.pcid, self.maxpdulength)
            return

        c_get_rsp.NumberOfRemainingSuboperations = next(matches)
        c_get_rsp.NumberOfCompletedSuboperations = 0
        c_get_rsp.NumberOfFailedSuboperations = 0
        c_get_rsp.NumberOfWarningSuboperations = 0

        ii = 1
        for dataset in matches:
            # Send C-STORE-RQ and Pending C-GET-RSP to peer
            # Send each matching dataset via C-STORE
            logger.info('Store SCU RQ: MsgID %s' %ii)

            store_status = self.ACSE.parent.send_c_store(dataset,
                                                         msg.MessageID,
                                                         priority)
            store_status = store_status.Type

            logger.info('Get SCU: Received Store SCU RSP (%s)' %store_status)

            if store_status == 'Failure':
                c_get_rsp.NumberOfFailedSuboperations += 1
            elif store_status == 'Warning':
                c_get_rsp.NumberOfWarningSuboperations += 1
            elif store_status == 'Success':
                c_get_rsp.NumberOfCompletedSuboperations += 1

            c_get_rsp.NumberOfRemainingSuboperations -= 1

            c_get_rsp.Status = int(self.Pending)

            logger.info('Get SCP Response %s (Pending)' %ii)

            self.DIMSE.Send(c_get_rsp, self.pcid, self.maxpdulength)

            ii += 1

        # Send Success C-GET-RSP to peer
        c_get_rsp.Status = int(self.Success)
        logger.info('Get SCP Response %s (Success)' %ii)
        self.DIMSE.Send(c_get_rsp, self.pcid, self.maxpdulength)


# WORKLIST SOP Classes
class BasicWorklistServiceClass (ServiceClass): pass

class ModalityWorklistServiceSOPClass (BasicWorklistServiceClass):
    OutOfResources = Status('Failure',
                            'Refused: Out of resources',
                            range(0xA700, 0xA700 + 1))
    IdentifierDoesNotMatchSOPClass = Status('Failure',
                                            'Identifier does not match SOP '
                                            'Class',
                                            range(0xA900, 0xA900 + 1))
    UnableToProcess = Status('Failure',
                             'Unable to process',
                             range(0xC000, 0xCFFF + 1))
    MatchingTerminatedDueToCancelRequest = Status('Cancel',
                                                  'Matching terminated due to '
                                                  'Cancel request',
                                                  range(0xFE00, 0xFE00 + 1))
    Success = Status('Success',
                     'Matching is complete - No final Identifier is supplied',
                     range(0x0000, 0x0000 + 1))
    Pending = Status('Pending',
                     'Matches are continuing - Current Match is supplied'
                     'and any Optional Keys were supported in the same manner '
                     'as Required Keys',
                     range(0xFF00, 0xFF00 + 1))
    PendingWarning = Status('Pending',
                            'Matches are continuing - Warning that one or more '
                            'Optional Keys were not supported for existence '
                            'and/or matching for this identifier',
                            range(0xFF01, 0xFF01 + 1))

    # FIXME
    def SCP(self, msg):
        ds = decode(msg.Identifier,
                    self.transfersyntax.is_implicit_VR,
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
                rsp.Identifier = encode(IdentifierDS,
                                        self.transfersyntax.is_implicit_VR,
                                        self.transfersyntax.is_little_endian)
                # send response
                self.DIMSE.Send(rsp, self.pcid, self.ACSE.MaxPDULength)
        except StopIteration:
            # send final response
            rsp = C_FIND_ServiceParameters()
            rsp.MessageIDBeingRespondedTo = msg.MessageID.value
            rsp.AffectedSOPClassUID = msg.AffectedSOPClassUID.value
            rsp.Status = int(self.Success)
            self.DIMSE.Send(rsp, self.pcid, self.ACSE.MaxPDULength)


class RTMachineVerificationServiceClass(ServiceClass):
    # PS3.4 DD.3.2.1.2 RT Ion Machine Verification N-CREATE/N-SET/N-GET/N-ACTION
    #   Slight differences in description text
    Success = Status('Success',
                     'Machine Verification successfully created',
                     range(0x0000, 0x0000 + 1))

    # PS3.4 DD.3.2.1.2 RT Ion Machine Verification N-CREATE
    fail_C227 = Status('Failure', '', range(0xC227, 0xC227 + 1))
    fail_c221 = Status('Failure', '', range(0xC221, 0xC221 + 1))
    fail_C222 = Status('Failure', '', range(0xC222, 0xC222 + 1))
    fail_C223 = Status('Failure', '', range(0xC223, 0xC223 + 1))

    # N-SET
    fail_C224 = Status('Failure', '', range(0xC224, 0xC224 + 1))
    fail_C225 = Status('Failure', '', range(0xC225, 0xC225 + 1))
    fail_C226 = Status('Failure', '', range(0xC226, 0xC226 + 1))

    # N-GET
    fail_C112 = Status('Failure', '', range(0xC112, 0xC112 + 1))

    # N-ACTION
    fail_C112 = Status('Failure', '', range(0xC112, 0xC112 + 1)) # oh noooooooo

    def SCP(self, msg):
        print('RTMachineVerification SCP', msg)

        if msg.__class__ == N_CREATE_ServiceParameters:
            pass
        elif msg.__class__ == N_SET_ServiceParameters:
            pass
        elif msg.__class__ == N_ACTION_ServiceParameters:
            pass
        elif msg.__class__ == N_DELETE_ServiceParameters:
            pass
        elif msg.__class__ == N_EVENT_REPORT_ServiceParameters:
            pass
        else:
            pass



# Generate the various SOP classes
_VERIFICATION_CLASSES = {'VerificationSOPClass' : '1.2.840.10008.1.1'}

_STORAGE_CLASSES = {'ComputedRadiographyImageStorage' : '1.2.840.10008.5.1.4.1.1.1',
                    'DigitalXRayImagePresentationStorage' : '1.2.840.10008.5.1.4.1.1.1.1',
                    'DigitalXRayImageProcessingStorage' : '1.2.840.10008.5.1.4.1.1.1.1.1.1',
                    'DigitalMammographyXRayImagePresentationStorage' : '1.2.840.10008.5.1.4.1.1.1.2',
                    'DigitalMammographyXRayImageProcessingStorage' : '1.2.840.10008.5.1.4.1.1.1.2.1',
                    'DigitalIntraOralXRayImagePresentationStorage' : '1.2.840.10008.5.1.4.1.1.1.3',
                    'DigitalIntraOralXRayImageProcessingStorage' : '1.2.840.10008.5.1.1.4.1.1.3.1',
                    'CTImageStorage' : '1.2.840.10008.5.1.4.1.1.2',
                    'EnhancedCTImageStorage' : '1.2.840.10008.5.1.4.1.1.2.1',
                    'LegacyConvertedEnhancedCTImageStorage' : '1.2.840.10008.5.1.4.1.1.2.2',
                    'UltrasoundMultiframeImageStorage' : '1.2.840.10008.5.1.4.1.1.3.1',
                    'MRImageStorage' : '1.2.840.10008.5.1.4.1.1.4',
                    'EnhancedMRImageStorage' : '1.2.840.10008.5.1.4.1.1.4.1',
                    'MRSpectroscopyStorage' : '1.2.840.10008.5.1.4.1.1.4.2',
                    'EnhancedMRColorImageStorage' : '1.2.840.10008.5.1.4.1.1.4.3',
                    'LegacyConvertedEnhancedMRImageStorage' : '1.2.840.10008.5.1.4.1.1.4.4',
                    'UltrasoundImageStorage' : '1.2.840.10008.5.1.4.1.1.6.1',
                    'EnhancedUSVolumeStorage' : '1.2.840.10008.5.1.4.1.1.6.2',
                    'SecondaryCaptureImageStorage' : '1.2.840.10008.5.1.4.1.1.7',
                    'MultiframeSingleBitSecondaryCaptureImageStorage' : '1.2.840.10008.5.1.4.1.1.7.1',
                    'MultiframeGrayscaleByteSecondaryCaptureImageStorage' : '1.2.840.10008.5.1.4.1.1.7.2',
                    'MultiframeGrayscaleWordSecondaryCaptureImageStorage' : '1.2.840.10008.5.1.4.1.1.7.3',
                    'MultiframeTrueColorSecondaryCaptureImageStorage' : '1.2.840.10008.5.1.4.1.1.7.4',
                    'TwelveLeadECGWaveformStorage' : '1.2.840.10008.5.1.4.1.1.9.1.1',
                    'GeneralECGWaveformStorage' : '1.2.840.10008.5.1.4.1.1.9.1.2',
                    'AmbulatoryECGWaveformStorage' : '1.2.840.10008.5.1.4.1.1.9.1.3',
                    'HemodynamicWaveformStorage' : '1.2.840.10008.5.1.4.1.1.9.2.1',
                    'CardiacElectrophysiologyWaveformStorage' : '1.2.840.10008.5.1.4.1.1.9.3.1',
                    'BasicVoiceAudioWaveformStorage' : '1.2.840.10008.5.1.4.1.1.9.4.1',
                    'GeneralAudioWaveformStorage' : '1.2.840.10008.5.1.4.1.1.9.4.2',
                    'ArterialPulseWaveformStorage' : '1.2.840.10008.5.1.4.1.1.9.5.1',
                    'RespiratoryWaveformStorage' : '1.2.840.10008.5.1.4.1.1.9.6.1',
                    'GrayscaleSoftcopyPresentationStateStorage' : '1.2.840.10008.5.1.4.1.1.11.1',
                    'ColorSoftcopyPresentationStateStorage' : '1.2.840.10008.5.1.4.1.1.11.2',
                    'PseudocolorSoftcopyPresentationStageStorage' : '1.2.840.10008.5.1.4.1.1.11.3',
                    'BlendingSoftcopyPresentationStateStorage' : '1.2.840.10008.5.1.4.1.1.11.4',
                    'XAXRFGrayscaleSoftcopyPresentationStateStorage' : '1.2.840.10008.5.1.4.1.1.11.5',
                    'XRayAngiographicImageStorage' : '1.2.840.10008.5.1.4.1.1.12.1',
                    'EnhancedXAImageStorage' : '1.2.840.10008.5.1.4.1.1.12.1.1',
                    'XRayRadiofluoroscopicImageStorage' : '1.2.840.10008.5.1.4.1.1.12.2',
                    'EnhancedXRFImageStorage' : '1.2.840.10008.5.1.4.1.1.12.2.1',
                    'XRay3DAngiographicImageStorage' : '1.2.840.10008.5.1.4.1.1.13.1.1',
                    'XRay3DCraniofacialImageStorage' : '1.2.840.10008.5.1.4.1.1.13.1.2',
                    'BreastTomosynthesisImageStorage' : '1.2.840.10008.5.1.4.1.1.13.1.3',
                    'BreastProjectionXRayImagePresentationStorage' : '1.2.840.10008.5.1.4.1.1.13.1.4',
                    'BreastProjectionXRayImageProcessingStorage' : '1.2.840.10008.5.1.4.1.1.13.1.5',
                    'IntravascularOpticalCoherenceTomographyImagePresentationStorage' : '1.2.840.10008.5.1.4.1.1.14.1',
                    'IntravascularOpticalCoherenceTomographyImageProcessingStorage' : '1.2.840.10008.5.1.4.1.1.14.2',
                    'NuclearMedicineImageStorage' : '1.2.840.10008.5.1.4.1.1.20',
                    'ParametricMapStorage' : '1.2.840.10008.5.1.4.1.1.30',
                    'RawDataStorage' : '1.2.840.10008.5.1.4.1.1.66',
                    'SpatialRegistrationStorage' : '1.2.840.10008.5.1.4.1.1.66.1',
                    'SpatialFiducialsStorage' : '1.2.840.10008.5.1.4.1.1.66.2',
                    'DeformableSpatialRegistrationStorage' : '1.2.840.10008.5.1.4.1.1.66.3',
                    'SegmentationStorage' : '1.2.840.10008.5.1.4.1.1.66.4',
                    'SurfaceSegmentationStorage' : '1.2.840.10008.5.1.4.1.1.66.5',
                    'RealWorldValueMappingStorage' : '1.2.840.10008.5.1.4.1.1.67',
                    'SurfaceScanMeshStorage' : '1.2.840.10008.5.1.4.1.1.68.1',
                    'SurfaceScanPointCloudStorage' : '1.2.840.10008.5.1.4.1.1.68.2',
                    'VLEndoscopicImageStorage' : '1.2.840.10008.5.1.4.1.1.77.1.1',
                    'VideoEndoscopicImageStorage' : '1.2.840.10008.5.1.4.1.1.77.1.1.1',
                    'VLMicroscopicImageStorage' : '1.2.840.10008.5.1.4.1.1.77.1.2',
                    'VideoMicroscopicImageStorage' : '1.2.840.10008.5.1.4.1.1.77.1.2.1',
                    'VLSlideCoordinatesMicroscopicImageStorage' : '1.2.840.10008.5.1.4.1.1.77.1.3',
                    'VLPhotographicImageStorage' : '1.2.840.10008.5.1.4.1.1.77.1.4',
                    'VideoPhotographicImageStorage' : '1.2.840.10008.5.1.4.1.1.77.1.4.1',
                    'OphthalmicPhotography8BitImageStorage' : '1.2.840.10008.5.1.4.1.1.77.1.5.1',
                    'OphthalmicPhotography16BitImageStorage' : '1.2.840.10008.5.1.4.1.1.77.1.5.2',
                    'StereometricRelationshipStorage' : '1.2.840.10008.5.1.4.1.1.77.1.5.3',
                    'OpthalmicTomographyImageStorage' : '1.2.840.10008.5.1.4.1.1.77.1.5.4',
                    'WideFieldOpthalmicPhotographyStereographicProjectionImageStorage' : '1.2.840.10008.5.1.4.1.1.77.1.5.5',
                    'WideFieldOpthalmicPhotography3DCoordinatesImageStorage' : '1.2.840.10008.5.1.4.1.1.77.1.5.6',
                    'VLWholeSlideMicroscopyImageStorage' : '1.2.840.10008.5.1.4.1.1.77.1.6',
                    'LensometryMeasurementsStorage' : '1.2.840.10008.5.1.4.1.1.78.1',
                    'AutorefractionMeasurementsStorage' : '1.2.840.10008.5.1.4.1.1.78.2',
                    'KeratometryMeasurementsStorage' : '1.2.840.10008.5.1.4.1.1.78.3',
                    'SubjectiveRefractionMeasurementsStorage' : '1.2.840.10008.5.1.4.1.1.78.4',
                    'VisualAcuityMeasurementsStorage' : '1.2.840.10008.5.1.4.1.1.78.5',
                    'SpectaclePrescriptionReportStorage' : '1.2.840.10008.5.1.4.1.1.78.6',
                    'OpthalmicAxialMeasurementsStorage' : '1.2.840.10008.5.1.4.1.1.78.7',
                    'IntraocularLensCalculationsStorage' : '1.2.840.10008.5.1.4.1.1.78.8',
                    'MacularGridThicknessAndVolumeReport' : '1.2.840.10008.5.1.4.1.1.79.1',
                    'OpthalmicVisualFieldStaticPerimetryMeasurementsStorag' : '1.2.840.10008.5.1.4.1.1.80.1',
                    'OpthalmicThicknessMapStorage' : '1.2.840.10008.5.1.4.1.1.81.1',
                    'CornealTopographyMapStorage' : '1.2.840.10008.5.1.4.1.1.82.1',
                    'BasicTextSRStorage' : '1.2.840.10008.5.1.4.1.1.88.11',
                    'EnhancedSRStorage' : '1.2.840.10008.5.1.4.1.1.88.22',
                    'ComprehensiveSRStorage' : '1.2.840.10008.5.1.4.1.1.88.33',
                    'Comprehenseice3DSRStorage' : '1.2.840.10008.5.1.4.1.1.88.34',
                    'ExtensibleSRStorage' : '1.2.840.10008.5.1.4.1.1.88.35',
                    'ProcedureSRStorage' : '1.2.840.10008.5.1.4.1.1.88.40',
                    'MammographyCADSRStorage' : '1.2.840.10008.5.1.4.1.1.88.50',
                    'KeyObjectSelectionStorage' : '1.2.840.10008.5.1.4.1.1.88.59',
                    'ChestCADSRStorage' : '1.2.840.10008.5.1.4.1.1.88.65',
                    'XRayRadiationDoseSRStorage' : '1.2.840.10008.5.1.4.1.1.88.67',
                    'RadiopharmaceuticalRadiationDoseSRStorage' : '1.2.840.10008.5.1.4.1.1.88.68',
                    'ColonCADSRStorage' : '1.2.840.10008.5.1.4.1.1.88.69',
                    'ImplantationPlanSRDocumentStorage' : '1.2.840.10008.5.1.4.1.1.88.70',
                    'EncapsulatedPDFStorage' : '1.2.840.10008.5.1.4.1.1.104.1',
                    'EncapsulatedCDAStorage' : '1.2.840.10008.5.1.4.1.1.104.2',
                    'PositronEmissionTomographyImageStorage' : '1.2.840.10008.5.1.4.1.1.128',
                    'EnhancedPETImageStorage' : '1.2.840.10008.5.1.4.1.1.130',
                    'LegacyConvertedEnhancedPETImageStorage' : '1.2.840.10008.5.1.4.1.1.128.1',
                    'BasicStructuredDisplayStorage' : '1.2.840.10008.5.1.4.1.1.131',
                    'RTImageStorage' : '1.2.840.10008.5.1.4.1.1.481.1',
                    'RTDoseStorage' : '1.2.840.10008.5.1.4.1.1.481.2',
                    'RTStructureSetStorage' : '1.2.840.10008.5.1.4.1.1.481.3',
                    'RTBeamsTreatmentRecordStorage' : '1.2.840.10008.5.1.4.1.1.481.4',
                    'RTPlanStorage' : '1.2.840.10008.5.1.4.1.1.481.5',
                    'RTBrachyTreatmentRecordStorage' : '1.2.840.10008.5.1.4.1.1.481.6',
                    'RTTreatmentSummaryRecordStorage' : '1.2.840.10008.5.1.4.1.1.481.7',
                    'RTIonPlanStorage' : '1.2.840.10008.5.1.4.1.1.481.8',
                    'RTIonBeamsTreatmentRecordStorage' : '1.2.840.10008.5.1.4.1.1.481.9',
                    'RTBeamsDeliveryInstructionStorage' : '1.2.840.10008.5.1.4.34.7',
                    'GenericImplantTemplateStorage' : '1.2.840.10008.5.1.4.43.1',
                    'ImplantAssemblyTemplateStorage' : '1.2.840.10008.5.1.4.44.1',
                    'ImplantTemplateGroupStorage' : '1.2.840.10008.5.1.4.45.1'}

_QR_FIND_CLASSES = {'PatientRootQueryRetrieveInformationModelFind'      : '1.2.840.10008.5.1.4.1.2.1.1',
                    'StudyRootQueryRetrieveInformationModelFind'        : '1.2.840.10008.5.1.4.1.2.2.1',
                    'PatientStudyOnlyQueryRetrieveInformationModelFind' : '1.2.840.10008.5.1.4.1.2.3.1',
                    'ModalityWorklistInformationFind'                   : '1.2.840.10008.5.1.4.31'}

_QR_MOVE_CLASSES = {'PatientRootQueryRetrieveInformationModelMove'      : '1.2.840.10008.5.1.4.1.2.1.2',
                    'StudyRootQueryRetrieveInformationModelMove'        : '1.2.840.10008.5.1.4.1.2.2.2',
                    'PatientStudyOnlyQueryRetrieveInformationModelMove' : '1.2.840.10008.5.1.4.1.2.3.2'}

_QR_GET_CLASSES = {'PatientRootQueryRetrieveInformationModelGet'      : '1.2.840.10008.5.1.4.1.2.1.3',
                   'StudyRootQueryRetrieveInformationModelGet'        : '1.2.840.10008.5.1.4.1.2.2.3',
                   'PatientStudyOnlyQueryRetrieveInformationModelGet' : '1.2.840.10008.5.1.4.1.2.3.3'}

_MACHINE_VERIFICATION_CLASSES = {'RTConventionalMachineVerification' : '1.2.840.10008.5.1.4.34.8'}

_generate_service_sop_classes(_VERIFICATION_CLASSES, VerificationServiceClass)
_generate_service_sop_classes(_STORAGE_CLASSES, StorageServiceClass)
_generate_service_sop_classes(_QR_FIND_CLASSES, QueryRetrieveFindServiceClass)
_generate_service_sop_classes(_QR_MOVE_CLASSES, QueryRetrieveMoveServiceClass)
_generate_service_sop_classes(_QR_GET_CLASSES, QueryRetrieveGetServiceClass)
_generate_service_sop_classes(_MACHINE_VERIFICATION_CLASSES, RTMachineVerificationServiceClass)

STORAGE_CLASS_LIST = StorageServiceClass.__subclasses__()
QR_FIND_CLASS_LIST = QueryRetrieveFindServiceClass.__subclasses__()
QR_MOVE_CLASS_LIST = QueryRetrieveMoveServiceClass.__subclasses__()
QR_GET_CLASS_LIST = QueryRetrieveGetServiceClass.__subclasses__()

QR_CLASS_LIST = []
for class_list in [QR_FIND_CLASS_LIST, QR_MOVE_CLASS_LIST, QR_GET_CLASS_LIST]:
    QR_CLASS_LIST.extend(class_list)

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
