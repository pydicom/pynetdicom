"""
Defines Status and the supported Service Classes, generates the SOP Classes.
"""
import inspect
from io import BytesIO
import logging
import sys
import time

from pydicom.dataset import Dataset
from pydicom.uid import UID

from pynetdicom3.dsutils import decode, encode
from pynetdicom3.dimse_primitives import (C_STORE, C_ECHO, C_MOVE, C_GET,
                                          C_FIND, N_EVENT_REPORT, N_GET,
                                          N_SET, N_CREATE, N_ACTION, N_DELETE)
from pynetdicom3.status import (Status, VERIFICATION_SERVICE_CLASS_STATUS,
                                STORAGE_SERVICE_CLASS_STATUS,
                                QR_FIND_SERVICE_CLASS_STATUS,
                                QR_MOVE_SERVICE_CLASS_STATUS,
                                QR_GET_SERVICE_CLASS_STATUS,
                                MODALITY_WORKLIST_SERVICE_CLASS_STATUS)

LOGGER = logging.getLogger('pynetdicom3.sop')

def _class_factory(name, uid, base_cls):
    """
    Generates a SOP Class subclass of `base_cls` called `name`

    Parameters
    ----------
    name : str
        The name of the SOP class
    uid : pydicom.uid.UID
        The UID of the SOP class
    base_cls : pynetdicom3.sop_class.ServiceClass subclass
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
        base_cls.__init__(self)

    new_class = type(name, (base_cls,), {"__init__": __init__})
    new_class.UID = uid

    return new_class

def _generate_service_sop_classes(sop_class_list, service_class):
    """Generate the SOP Classes."""
    for name in sop_class_list:
        cls = _class_factory(name, UID(sop_class_list[name]), service_class)
        globals()[cls.__name__] = cls


# DICOM SERVICE CLASS BASE
class ServiceClass(object):
    """The base class for all the service class types.

    FIXME: Determine a better method for the statuses
    FIXME: SOP class status values shouldn't overwrite Warning (which is a
    non-pythonic attribute name anyway)
    FIXME: Perhaps define some class attributes such as self.AE = None
        self.UID = None,
        then call ServiceClass.__init__() in the subclasses?

    Attributes
    ----------
    AE : pynetdicom3.applicationentity.ApplicationEntity
        The local AE (needed for the callbacks).
    DIMSE : pynetdicom3.dimse.DIMSEServiceProvider
        The DIMSE service provider (needed to send/receive messages)
    """
    def __init__(self):
        self.AE = None
        self.DIMSE = None
        self.pcid = None
        self.ACSE = None
        self.sopclass = None
        self.maxpdulength = None
        self.transfersyntax = None

        # Assigned by class builder, this will override
        #self.UID = None

        # New method?
        self.presentation_context = None

    def is_valid_status(self, status):
        """Check if a status is valid for the service class.

        Parameters
        ----------
        status : pynetdicom3.sop_class.Status
            The Status object to check for validity.

        Returns
        -------
        bool
            Whether or not the status is valid
        """
        if int(status) in self.statuses:
            return True

        return False


# Service Class types
class VerificationServiceClass(ServiceClass):
    """Represents the Verification Service Class.

    Status
    ------
    Based on PS3.7 Section 9.1.5.1.4.

    Success
        0x000 - Success
    Failure
        0x0122 - Refused: SOP Class Not Supported
        0x0210 - Refused: Duplicate Invocation
        0x0212 - Refused: Mistyped Argument
        0x0211 - Refused: Unrecognised Operation
    """
    statuses = VERIFICATION_SERVICE_CLASS_STATUS

    def SCP(self, msg):
        """
        When the local AE is acting as an SCP for the VerificationSOPClass
        and a C-ECHO request is received then create a C-ECHO response
        primitive and send it to the peer AE via the DIMSE provider

        Parameters
        ----------
        msg : pynetdicom3.dimse_primitives.C_ECHO
            The C-ECHO request primitive sent by the peer
        """
        # Create C-ECHO response primitive
        rsp = C_ECHO()
        rsp.AffectedSOPClassUID = '1.2.840.10008.1.1'
        rsp.MessageIDBeingRespondedTo = msg.MessageID
        rsp.Status = 0x0000 # Success

        # Try and run the user on_c_echo callback
        try:
            self.AE.on_c_echo()
        except:
            LOGGER.exception("Exception in the AE.on_c_echo() callback.")

        # Send primitive
        self.DIMSE.send_msg(rsp, self.pcid)


class StorageServiceClass(ServiceClass):
    """Represents the Storage Service Class.

    Status
    ------
    Based on PS3.7 Section 9.1.1.1.9 and PS3.4 Annex B.2.3.

    pynetdicom3 specific status codes
        Failure: Cannot Understand
            0xC100 - Failed to decode the received dataset.
            0xC101 - Exception in the on_c_store callback.
            0xC102 - Unknown status returned by the on_c_store callback.
            0xC103 - Dataset with no Status element returned by the on_c_store
                     callback.
            0xC104 - on_c_store callback failed to return a pydicom Dataset.

    * Indicates service class specific status codes

    Success
        0x0000 - Success
    Warning
        0xB000 * - Warning: Coercion of Data Elements
        0xB006 * - Warning: Elements Discarded
        0xB007 * - Warning: Data Set Does Not Match SOP Class
    Failure
        0x0117 - Refused: Invalid SOP Instance
        0x0122 - Refused: SOP Class Not Supported
        0x0124 - Refused: Not Authorised
        0x0210 - Refused: Duplicate Invocation
        0x0211 - Refused: Unrecognised Operation
        0x0212 - Refused: Mistyped Argument
        0xA7xx * - Refused: Out of Resources
        0xA9xx * - Error: Data Set Does Not Match SOP Class
        0xCxxx * - Error: Cannot Understand
    """
    statuses = STORAGE_SERVICE_CLASS_STATUS

    def SCP(self, msg):
        """Called when running as an SCP and receive a C-STORE request."""
        # Create C-STORE response primitive
        rsp = C_STORE()
        rsp.MessageIDBeingRespondedTo = msg.MessageID
        rsp.AffectedSOPInstanceUID = msg.AffectedSOPInstanceUID
        rsp.AffectedSOPClassUID = msg.AffectedSOPClassUID

        # Check the dataset SOP Class UID matches the one agreed to
        if self.UID != self.sopclass:
            LOGGER.error("Store request's dataset UID does not match the "
                         "presentation context")
             # Failure: Data Set Does Not Match SOP Class
            rsp.Status = 0xA900
            self.DIMSE.send_msg(rsp, self.pcid)
            return

        # Attempt to decode the dataset
        try:
            ds = decode(msg.DataSet,
                        self.transfersyntax.is_implicit_VR,
                        self.transfersyntax.is_little_endian)
        except:
            LOGGER.error("Failed to decode the received dataset")
             # Failure: Cannot Understand - Dataset decoding error
            rsp.Status = 0xC100
            self.DIMSE.send_msg(rsp, self.pcid)
            return

        # Attempt to run the ApplicationEntity's on_c_store callback
        try:
            status_ds = self.AE.on_c_store(ds)
        except Exception:
            LOGGER.exception("Exception in the ApplicationEntity.on_c_store() "
                             "callback")
             # Failure: Cannot Understand - Error in on_c_store callback
            rsp.Status = 0xC101
            self.DIMSE.send_msg(rsp, self.pcid)
            return

        # Check the callback's returned Status dataset
        if isinstance(status_ds, Dataset):
            # Check that the returned status dataset contains a Status element
            if 'Status' in status_ds:
                # Check returned dataset Status element value is OK
                if status_ds.Status not in self.statuses:
                    LOGGER.error("ApplicationEntity.on_c_store() returned an "
                                 "invalid status value.")
                    # Failure: Cannot Understand - Invalid Status returned
                    #   by on_c_store callback
                    rsp.Status = 0xC102
                else:
                    # For the elements in the status dataset, try and set the
                    #   corresponding response primitive attribute
                    for elem in status_ds:
                        if hasattr(rsp, elem.keyword):
                            setattr(rsp, elem.keyword, elem.value)
                        else:
                            LOGGER.warning("Status dataset returned by on_c_store "
                                           "contained an unsupported Element "
                                           "'{}'.".format(elem.keyword))
            else:
                LOGGER.error("ApplicationEntity.on_c_store() returned a "
                             "dataset without a Status element.")
                # Failure: Cannot Understand - on_c_store callback returned
                #   a pydicom.dataset.Dataset without a Status element
                rsp.Status = 0xC103
        else:
            LOGGER.error("ApplicationEntity.on_c_store() returned an invalid "
                         "status type (should be a pydicom Dataset).")
            # Failure: Cannot Understand - on_c_store callback didn't return
            #   a pydicom.dataset.Dataset
            rsp.Status = 0xC104

        self.DIMSE.send_msg(rsp, self.pcid)


class QueryRetrieveFindServiceClass(ServiceClass):
    """Implements the QR Find Service Class.
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

    Status
    ------
    Based on PS3.7 Section 9.1.2.1.5 and PS3.4 Annex C.4.1.1.4

    * Indicates service class specific status codes

    Success
        Success - 0x0000
    Pending
        *Pending: Matches are continuing, current match supplied - 0xFF00
        *Pending: Matches are continuing, warning - 0xFF01
    Cancel
        Cancel - 0xFE00
    Failure
        *Refused: Out of Resources - 0xA700
        Refused: SOP Class Not Supported - 0x0122
        *Identifier Does Not Match SOP Class - 0xA900
        *Unable to Process - 0xCxxx

    A QR C-FIND SCP may also support Instance Availability (0008,0056) element
    in the Identifier (PS3.4 C.4.1.1.3)
    """
    statuses = QR_FIND_SERVICE_CLASS_STATUS

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
        # Build C-FIND response primitive
        rsp = C_FIND()
        rsp.MessageIDBeingRespondedTo = msg.MessageID
        rsp.AffectedSOPClassUID = msg.AffectedSOPClassUID

        # Check the identifier SOP Class UID matches the one agreed to
        if self.UID != self.sopclass:
            LOGGER.error("Find request's Identifier UID does not match the "
                         "presentation context")
            # Failure - Identifier Does Not Match SOP Class
            rsp.Status = 0xA900
            self.DIMSE.send_msg(rsp, self.pcid)
            return

        try:
            dataset = decode(msg.Identifier,
                             self.transfersyntax.is_implicit_VR,
                             self.transfersyntax.is_little_endian)
        except:
            LOGGER.error("Failed to decode the received Identifier dataset")
            # Failure - Unable to Process - Failed to decode Identifier
            rsp.Status = 0xC000
            self.DIMSE.send_msg(rsp, self.pcid)
            return

        # Log Identifier
        try:
            LOGGER.info('Find SCP Request Identifiers:')
            LOGGER.info('')
            LOGGER.debug('# DICOM Data Set')
            for elem in dataset:
                LOGGER.info(elem)
            LOGGER.info('')
        except (AttributeError, NotImplementedError, TypeError):
            LOGGER.error("Failed to decode the received Identifier dataset")
            # Failure - Unable to Process - Failed to decode Identifier
            rsp.Status = 0xC000
            self.DIMSE.send_msg(rsp, self.pcid)
            return

        # Callback - C-FIND
        try:
            result = self.AE.on_c_find(dataset)
        except:
            LOGGER.exception('Exception in user\'s on_c_find implementation.')
            # Failure - Unable to Process - Error in on_c_find callback
            rsp.Status = 0xC001
            self.DIMSE.send_msg(rsp, self.pcid)
            return

        # Iterate through the results
        for ii, (status_ds, matching_ds) in enumerate(result):

            # Check the callback's returned Status dataset
            if isinstance(status_ds, Dataset):
                # Check that the returned status dataset contains
                #   a Status element
                if 'Status' in status_ds:
                    # Check returned dataset Status element value is OK
                    if status_ds.Status not in self.statuses:
                        LOGGER.error("ApplicationEntity.on_c_find returned "
                                     "an invalid status value.")
                        # Failure: Unable to Process - Invalid Status returned
                        #   by on_c_find callback
                        rsp.Status = 0xC002
                    else:
                        # For the elements in the status dataset, try and set the
                        #   corresponding response primitive attribute
                        for elem in status_ds:
                            if hasattr(rsp, elem.keyword):
                                setattr(rsp, elem.keyword, elem.value)
                            else:
                                LOGGER.warning("Status dataset returned by "
                                               "on_c_find contained an unsupported "
                                               "Element '{}'.".format(elem.keyword))
                else:
                    LOGGER.error("ApplicationEntity.on_c_find returned a "
                                 "dataset without a Status element.")
                    # Failure: Unable to Process - on_c_store callback returned
                    #   a pydicom.dataset.Dataset without a Status element
                    rsp.Status = 0xC003
            else:
                LOGGER.error("ApplicationEntity.on_c_find returned an invalid "
                             "status type (should be a pydicom Dataset).")
                # Failure: Unable to Process - on_c_store callback didn't return
                #   a pydicom.dataset.Dataset
                rsp.Status = 0xC004

            status = Status(rsp.Status, *self.statuses[rsp.Status])
            if status.category == 'Cancel':
                LOGGER.info('Received C-CANCEL-FIND RQ from peer')
                LOGGER.info('Find SCP Response: (Cancel)')
                self.DIMSE.send_msg(rsp, self.pcid)
                return
            elif status.category == 'Failure':
                LOGGER.info('Find SCP Response: (Failure - %s)', status.description)
                self.DIMSE.send_msg(rsp, self.pcid)
                return
            elif status.category == 'Success':
                # User isn't supposed to send these, but handle anyway
                LOGGER.info('Find SCP Response: (Success)')
                self.DIMSE.send_msg(rsp, self.pcid)
                return
            else:
                # Pending
                ds = BytesIO(encode(matching_ds,
                                    self.transfersyntax.is_implicit_VR,
                                    self.transfersyntax.is_little_endian))

                if ds.getvalue() == b'':
                    LOGGER.error("Failed to decode the received Identifier "
                                 "dataset")
                    # Failure: Unable to Process - Can't decode dataset
                    #   returned by on_c_find callback
                    rsp.Status = 0xC005
                    self.DIMSE.send_msg(rsp, self.pcid)
                    return

                rsp.Identifier = ds

                # Send Pending response
                rsp.Status = 0xFF00

                LOGGER.info('Find SCP Response: %s (Pending)', ii + 1)

                self.DIMSE.send_msg(rsp, self.pcid)

                LOGGER.debug('Find SCP Response Identifiers:')
                LOGGER.debug('')
                LOGGER.debug('# DICOM Dataset')
                for elem in matching_ds:
                    LOGGER.debug(elem)
                LOGGER.debug('')

        # Send final success response
        rsp.Status = 0x0000
        LOGGER.info('Find SCP Response: %s (Success)', ii + 2)
        self.DIMSE.send_msg(rsp, self.pcid)


class QueryRetrieveMoveServiceClass(ServiceClass):
    """Implements the QR Move Service Class.

    PS3.4 Section C.4.2.2

    Status
    ------
    Based on PS3.7 Section 9.1.4.1.7 and PS3.4 Annex C.4.2.1.5.

    * Indicates service class specific status codes

    Success
        Success: Sub-operations complete, no failures - 0x0000
    Pending
        *Pending: Sub-operations are continuing - 0xFF00
    Cancel
        Cancel: Sub-operations terminated due to Cancel indication - 0xFE00
    Failure
        *Refused: Out of Resources, unable to calculate number of matches
            - 0xA701
        *Refused: Out of Resources, unable to perform sub-operations - 0xA702
        Refused: SOP Class Not Supported - 0x0122
        *Refused: Move Destination Unknown - 0xA801
        *Identifier Does Not Match SOP Class - 0xA900
        *Unable to Process - 0xCxxx
        Refused: Duplicate Invocation
        Refused: Mistyped Argument
        Refused: Unrecognised Operation
        Refused: Not Authorised
    Warning
        Warning: Sub-operations completed, one or more failures - 0xB000
    """
    statuses = QR_MOVE_SERVICE_CLASS_STATUS

    def SCP(self, msg):
        """SCP

        SCP Behaviour
        -------------
        The SCP shall identify a set of Entities at the level of the transfer
        based on the values in the Unique Keys in the Identifier of the C-MOVE
        request.

        The SCP shall initiate C-STORE sub-operations for all stored SOP
        Instances related to the Patient ID, List of Study Instance UIDs, List
        of Series Instance UIDs or List of SOP Instance UIDs depending on the
        QR level specified in the C-MOVE request.

        A sub-operation is considered Failed if the SCP is unable to negotiate
        an appropriate presentation context for a given stored SOP instance.

        Optionally, the SCP may generate responses to the C-MOVE with status
        equal to Pending during the processing of the C-STORE sub-operations.
        These responses shall indicate the Remaining, Completed, Failed and
        Warning C-STORE sub-operations.

        When the number of Remaining sub-operations reaches zero, the SCP shall
        generate a final response with a status equal to Success, Warning,
        Failure or Refused.

        The SCP may receive a C-MOVE-CANCEL request at any time during the
        processing of the C-MOVE. The SCP shall interrupt all C-STORE
        sub-operation processing and return a status of Canceled in the C-MOVE
        response.

        Pending: shall contain NoRemainingSubops, NoCompletedSubops,
            NoFailedSubops, NoWarningSubops
        Canceled: may contain NoRemainingSubops, NoCompletedSubops,
            NoFailedSubops, NoWarningSubops
        Failed: shall NOT contain NoRemainingSubops, may contain
            NoCompletedSubops, NoFailedSubops, NoWarningSubops
        Warning: shall NOT contain NoRemainingSubops, may contain
            NoCompletedSubops, NoFailedSubops, NoWarningSubops
        Success: shall NOT contain NoRemainingSubops, may contain
            NoCompletedSubops, NoFailedSubops, NoWarningSubops

        Identifier
        -----------
        Based on PS3.7 Annex C.4.2.1.4.2

        The FailedSOPInstanceUIDList (0008,0058) specifies a list of UIDs of the
        C-STORE sub-operation SOP Instances for which this C-MOVE operation has
        failed.

        The Identifier in a C-MOVE response with a status of Canceled, Failure,
        Refused or Warning shall contain the FailedSOPInstanceUIDList attribute.
        Pending shall not contain the FailedSOPInstanceUIDList attribute.

        Parameters
        ----------
        msg : pynetdicom3.dimse_messages.DIMSEMessage
            The DIMSE C-MOVE request (C_MOVE_RQ) message
        """
        # Build C-MOVE response primitive
        rsp = C_MOVE()
        rsp.MessageIDBeingRespondedTo = msg.MessageID
        rsp.AffectedSOPClassUID = msg.AffectedSOPClassUID
        rsp.Identifier = msg.Identifier

        # Number of suboperation trackers
        no_remaining = 0
        no_completed = 0
        no_failed = 0
        no_warning = 0
        failed_sop_instances = []

        # Check that the Identifier's SOP Class matches the presentation context
        if not self._is_identifier_sop_class_valid(rsp):
            return

        # Decode the Identifier dataset
        ds = self._decode_identifier(msg, rsp)
        if ds is None:
            return

        ## GET USER ON_C_MOVE GENERATOR
        result = self._user_callback(ds, msg.MoveDestination, rsp)
        if result is None:
            return

        # USER YIELD NUMBER OF OPERATIONS
        no_remaining = self._get_number_suboperations(result, rsp)
        if no_remaining is None:
            return

        ## USER YIELD MOVE DESTINATION ADDR, PORT
        addr, port = self._get_destination(result, rsp)
        if addr is None:
            return

        # Request new association with move destination
        #   need (addr, port, aet)
        assoc = self.AE.associate(addr, port, msg.MoveDestination)
        if assoc.is_established:

            ## USER YIELD STATUS, DATASET
            for ii, (status_ds, dataset) in enumerate(result):
                # Check validity of status_ds and set rsp.Status
                rsp = self._get_status(status_ds, rsp)
                status = Status(rsp.Status, *self.statuses[rsp.Status])

                # If usr_status is Cancel, Failure or Success then generate a
                #   final response
                if status.category == 'Cancel':
                    LOGGER.info('Move SCP Received C-CANCEL-MOVE RQ from peer')
                    assoc.release()

                    # A Cancel response may include the number remaining, etc
                    rsp.NumberOfRemainingSuboperations = no_remaining
                    rsp.NumberOfFailedSuboperations = no_failed
                    rsp.NumberOfWarningSuboperations = no_warning
                    rsp.NumberOfCompletedSuboperations = no_completed
                    rsp.Identifier = self._add_failed_sop_instances(rsp,
                                                        failed_sop_instances)
                    self.DIMSE.send_msg(rsp, self.pcid)
                    return
                elif status.category == 'Failure':
                    LOGGER.info('Move SCP Response: (Failure - %s)',
                                usr_status.description)
                    assoc.release()
                    rsp.Identifier = self._add_failed_sop_instances(rsp,
                                                        failed_sop_instances)
                    self.DIMSE.send_msg(rsp, self.pcid)
                    return
                elif status.category == 'Success':
                    LOGGER.info('Move SCP Response: (Success)')
                    assoc.release()
                    self.DIMSE.send_msg(rsp, self.pcid)
                    return
                elif status.category == 'Warning':
                    LOGGER.info('Move SCP Response: (Warning)')
                    assoc.release()
                    rsp.Identifier = self._add_failed_sop_instances(rsp,
                                                        failed_sop_instances)
                    self.DIMSE.send_msg(rsp, self.pcid)
                    return
                else:
                    ## USER RESPONSE IS PENDING
                    # Send dataset(s) via C-STORE sub-operations over new
                    #   association. While the sub-operations are being
                    #   performed send Pending statuses back to the peer
                    store_status = assoc.send_c_store(dataset)
                    store_status = self._get_store_status(store_status)
                    service_class = StorageServiceClass()
                    store_status = Status(store_status,
                                          *service.statuses[store_status])
                    LOGGER.info('Move SCU: Received Store SCU RSP (%s)',
                                store_status.category)

                    # Update the suboperation trackers
                    if store_status.status_type == 'Failure':
                        no_failed += 1
                        failed_sop_instances.append(dataset.SOPInstanceUID)
                    elif store_status.status_type == 'Warning':
                        no_warning += 1
                        failed_sop_instances.append(dataset.SOPInstanceUID)
                    elif store_status.status_type == 'Success':
                        no_completed += 1
                    no_remaining -= 1

                    rsp.NumberOfRemainingSuboperations = no_remaining
                    rsp.NumberOfFailedSuboperations = no_failed
                    rsp.NumberOfWarningSuboperations = no_warning
                    rsp.NumberOfCompletedSuboperations = no_completed

                    rsp.Status = 0xFF00 # Pending
                    LOGGER.info('Move SCP Response %s (Pending)', ii)
                    self.DIMSE.send_msg(rsp, self.pcid)

            assoc.release()

        else:
            # Failed to associate
            # Close socket
            assoc.dul.scu_socket.close()

            LOGGER.info('Move SCP Response: (Failure - Peer refused '
                        'association)')
            # Failure - Out of resources, unable to perform sub-operations
            rsp.Status = 0xA702
            self.DIMSE.send_msg(rsp, self.pcid)
            return

        # Send final C-MOVE-RSP to peer
        if no_warning == 0 and no_failed == 0:
            rsp.Status = 0x0000 # Success
            LOGGER.info('Move SCP Response: (Success)')
        else:
            rsp.Status = 0xB000 # Warning
            rsp.Identifier = self._add_failed_sop_instances(rsp,
                                                        failed_sop_instances)
            LOGGER.info('Move SCP Response: (Warning)')
        self.DIMSE.send_msg(rsp, self.pcid)

    def _is_identifier_sop_class_valid(self, rsp):
        """Check the Identifier's SOP Class UID matches the one agreed to."""
        if self.UID != self.sopclass:
            LOGGER.error("C-MOVE request's Identifier SOP Class UID does not "
                         "match the agreed presentation context.")
            # Failure - Identifier doesn't match SOP class
            rsp.Status = 0xA900
            self.DIMSE.send_msg(rsp, self.pcid)
            return False

        return True

    def _decode_identifier(self, rsp):
        """Decode the Identifier dataset."""
        try:
            ds = decode(rsp.Identifier,
                        self.transfersyntax.is_implicit_VR,
                        self.transfersyntax.is_little_endian)

            LOGGER.info('Move SCP Request Identifiers:')
            LOGGER.info('')
            LOGGER.debug('# DICOM Data Set')
            for elem in ds:
                LOGGER.info(elem)
            LOGGER.info('')
        except (AttributeError, NotImplementedError, TypeError, KeyError):
            LOGGER.error("Failed to decode the Identifier dataset received "
                         "from the peer.")
            # Failure - Unable to process - Failed to decode Identifier
            rsp.Status = 0xC000
            self.DIMSE.send_msg(rsp, self.pcid)
            return None

        return ds

    def _user_callback(self, ds, move_destination, rsp):
        """Call the user's on_c_move callback."""
        try:
            result = self.AE.on_c_move(ds, move_destination)
        except:
            LOGGER.exception("Exception in user's on_c_move implementation.")
            # Failure - Unable to process - Error in on_c_move callback
            rsp.Status = 0xC001
            self.DIMSE.send_msg(rsp, self.pcid)
            return None

        return result

    def _get_number_suboperations(self, generator, rsp):
        """Get the number of suboperations."""
        try:
            no_remaining = int(next(generator))
        except TypeError:
            LOGGER.exception('You must yield the number of sub-operations in '
                             'ae.on_c_move before yielding the (address, port) '
                             'of the destination AE and then yield (status, '
                             'dataset) pairs.')
            # Failure - Unable to process - Error in on_c_move yield
            rsp.Status = 0xC002
            self.DIMSE.send_msg(rsp, self.pcid)
            return None

        return no_remaining

    def _get_destination(self, generator, rsp):
        """Get the IP address and port for the move destination."""
        # Second yield is the addr and port for the move destination if known
        #   None, None if not known
        try:
            addr, port = next(generator)
        except StopIteration:
            LOGGER.exception('You must yield the number of sub-operations in '
                             'ae.on_c_move before yielding the (address, port) '
                             'of the destination AE and then yield (status, '
                             'dataset) pairs.')
            # Failure - Unable to process - Error in on_c_move yield
            rsp.Status = 0xC002
            self.DIMSE.send_msg(rsp, self.pcid)
            return None, None

        if None in [addr, port]:
            LOGGER.error('Unknown Move Destination: %s',
                         msg.MoveDestination.decode('utf-8'))
            # Failure - Move destination unknown
            rsp.Status = 0xA801
            self.DIMSE.send_msg(rsp, self.pcid)
            return None, None

        if not isinstance(addr, str) or not isinstance(port, int):
            LOGGER.exception('You must yield the (address, port) '
                             'of the destination AE and then yield (status, '
                             'dataset) pairs.')
            # Failure - Unable to process - Bad yielded value
            rsp.Status = 0xC002
            self.DIMSE.send_msg(rsp, self.pcid)
            return None, None

        return addr, port

    def _get_status(self, ds, rsp):
        """Check the callback's returned status dataset and set rsp.Status."""
        # Check the callback's returned Status dataset
        if isinstance(ds, Status) and 'Status' in ds:
            # Check returned dataset Status element value is OK
            if ds.Status not in self.statuses:
                LOGGER.error("Status dataset yielded by on_c_move callback "
                             "contains a Status element with an unknown value: "
                             "0x{0:04x}.".format(ds.Status))
                # Failure: Unable to Process - Invalid Status returned
                rsp.Status = 0xC002
                return rsp

            # For the elements in the status dataset, try and set the
            #   corresponding response primitive attribute
            for elem in ds:
                if hasattr(rsp, elem.keyword):
                    setattr(rsp, elem.keyword, elem.value)
                else:
                    LOGGER.warning("Status dataset yielded by on_c_move "
                                   "callback contained an unsupported "
                                   "Element '{}'.".format(elem.keyword))
            
        else:
            LOGGER.error("Callback yielded an invalid status "
                         "(should be a pydicom Dataset with a Status "
                         "element).")
            # Failure: Unable to Process - callback didn't yield/return
            #   a pydicom.dataset.Dataset with a Status element.
            rsp.Status = 0xC003

        return rsp

    def _get_store_status(self, ds):
        """Check the on_c_store's returned status dataset and set rsp.Status."""
        # Check the callback's returned Status dataset
        if isinstance(ds, Status) and 'Status' in ds:
            # Check returned dataset Status element value is OK
            if ds.Status not in self.statuses:
                LOGGER.error("Status dataset yielded by on_c_store callback "
                             "contains a Status element with an unknown value: "
                             "0x{0:04x}.".format(ds.Status))
                # Failure: Unable to Process - Invalid Status returned
                status = 0xC002
            # User's status is OK
            status = ds.Status
        else:
            LOGGER.error("Callback yielded an invalid status "
                         "(should be a pydicom Dataset with a Status "
                         "element).")
            # Failure: Unable to Process - callback didn't yield/return
            #   a pydicom.dataset.Dataset with a Status element.
            status = 0xC003

        return status

    def _add_failed_sop_instances(self, rsp, failed_instances):
        """Add FailedSOPInstanceUIDList to the Identifier."""
        # Decode Identifier
        ds = decode(msg.Identifier,
                    self.transfersyntax.is_implicit_VR,
                    self.transfersyntax.is_little_endian)
        ds.FailedSOPInstanceUIDList = failed_instances
        return ds.encode(self.transfersyntax.is_implicit_VR,
                         self.transfersyntax.is_little_endian)


class QueryRetrieveGetServiceClass(ServiceClass):
    """Implements the QR Get Service Class.

    Status
    ------
    Based on PS3.7 Section 9.1.3.1.6 and PS3.4 Annex C.4.3.1.4.

    * Indicates service class specific status codes

    Success
        Success: Sub-operations complete, no failures - 0x0000
    Pending
        *Pending: Sub-operations are continuing - 0xFF00
    Cancel
        Cancel: Sub-operations terminated due to Cancel indication - 0xFE00
    Failure
        *Refused: Out of Resources, unable to calculate number of matches
            - 0xA701
        *Refused: Out of Resources, unable to perform sub-operations - 0xA702
        Refused: SOP Class Not Supported - 0x0122
        *Identifier Does Not Match SOP Class - 0xA900
        *Unable to Process - 0xCxxx
        Refused: Duplicate Invocation
        Refused: Mistyped Argument
        Refused: Unrecognised Operation
        Refused: Not Authorised
    Warning
        Warning: Sub-operations completed, one or more failures/warnings - 0xB000
    """
    statuses = QR_GET_SERVICE_CLASS_STATUS

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
        # Build C-GET response primitive
        rsp = C_GET()
        rsp.MessageIDBeingRespondedTo = msg.MessageID
        rsp.AffectedSOPClassUID = msg.AffectedSOPClassUID
        rsp.Identifier = msg.Identifier

        # Number of suboperation trackers
        no_remaining = 0
        no_completed = 0
        no_failed = 0
        no_warning = 0
        failed_sop_instances = []

        # Check the identifier SOP Class UID matches the one agreed to
        if not self._is_identifier_sop_class_valid(rsp):
            return

        # Decode the Identifier dataset
        ds = self._decode_identifier(rsp)
        if ds is None:
            return

        # Get user's on_c_find generator
        result = self._user_callback(ds, rsp)
        if result is None:
            return

        # Get user's yielded number of sub-operations
        no_remaining = self._get_number_suboperations(result, rsp)
        if no_remaining is None:
            return

        # Iterate through the results
        for ii, (status_ds, dataset) in enumerate(result):
            # Check validity of status_ds and set rsp.Status
            rsp = self._get_status(status_ds, rsp)
            try:
                status = Status(rsp.Status, *self.statuses[rsp.Status])
            except (ValueError, TypeError):
                LOGGER.error("ApplicationEntity.on_c_move() returned an "
                             "invalid status value.")
                rsp.Status = 0xC000 # Unable to process
                self.DIMSE.send_msg(rsp, self.pcid)
                return

            if status.category == 'Cancel':
                LOGGER.info('Received C-CANCEL-GET RQ from peer')
                rsp.Status = 0xFE00 # Cancel
                rsp.NumberOfRemainingSuboperations = no_remaining
                rsp.NumberOfFailedSuboperations = no_failed
                rsp.NumberOfWarningSuboperations = no_warning
                rsp.NumberOfCompletedSuboperations = no_completed
                # Send C-CANCEL confirmation
                self.DIMSE.send_msg(rsp, self.pcid)
                return
            elif status.category == 'Failure':
                # Pass along the status from the user
                rsp.Status = int(usr_status)
                LOGGER.info('Get SCP Response: (Failure - %s)',
                            usr_status.description)
                self.DIMSE.send_msg(rsp, self.pcid)
                return
            elif status.category == 'Success':
                # User isn't supposed to send these, but handle anyway
                rsp.Status = 0x0000 # Success
                LOGGER.info('Get SCP Response: (Success)')
                self.DIMSE.send_msg(rsp, self.pcid)
                return
            else:
                # Send C-STORE-RQ and Pending C-GET-RSP to peer
                # Send each matching dataset via C-STORE
                LOGGER.info('Store SCU RQ: MsgID %s', ii + 1)

                store_status = self.ACSE.parent.send_c_store(dataset,
                                                             msg.MessageID,
                                                             priority)

                store_status = assoc.send_c_store(dataset)
                store_status = self._get_store_status(store_status)
                service_class = StorageServiceClass()
                store_status = Status(store_status,
                                      *service.statuses[store_status])
                LOGGER.info('Get SCU: Received Store SCU RSP (%s)',
                            store_status.category)

                # Update the suboperation trackers
                if store_status.category == 'Failure':
                    no_failed += 1
                elif store_status.category == 'Warning':
                    no_warning += 1
                elif store_status.category == 'Success':
                    no_completed += 1
                no_remaining -= 1

                rsp.NumberOfRemainingSuboperations = no_remaining
                rsp.NumberOfFailedSuboperations = no_failed
                rsp.NumberOfWarningSuboperations = no_warning
                rsp.NumberOfCompletedSuboperations = no_completed

                LOGGER.info('Get SCP Response %s (Pending)', ii + 1)
                rsp.Status = 0xFF00 # Pending
                self.DIMSE.send_msg(rsp, self.pcid)

        # Send final C-GET-RSP to peer
        if no_warning == 0 and no_failed == 0:
            rsp.Status = 0x0000
            LOGGER.info('Get SCP Final Response (Success)')
        else:
            rsp.Status = 0xB000 # Warning
            LOGGER.info('Get SCP Final Response (Warning)')

        self.DIMSE.send_msg(rsp, self.pcid)

    def _is_identifier_sop_class_valid(self, rsp):
        """Check the Identifier's SOP Class UID matches the one agreed to."""
        if self.UID != self.sopclass:
            LOGGER.error("C-GET request's Identifier SOP Class UID does not "
                         "match the agreed presentation context.")
            # Failure - Identifier doesn't match SOP class
            rsp.Status = 0xA900
            self.DIMSE.send_msg(rsp, self.pcid)
            return False

        return True

    def _decode_identifier(self, rsp):
        """Decode the Identifier dataset."""
        try:
            ds = decode(rsp.Identifier,
                        self.transfersyntax.is_implicit_VR,
                        self.transfersyntax.is_little_endian)

            LOGGER.info('Get SCP Request Identifiers:')
            LOGGER.info('')
            LOGGER.debug('# DICOM Data Set')
            for elem in ds:
                LOGGER.info(elem)
            LOGGER.info('')
        except (AttributeError, NotImplementedError, TypeError, KeyError):
            LOGGER.error("Failed to decode the Identifier dataset received "
                         "from the peer.")
            # Failure - Unable to process - Failed to decode Identifier
            rsp.Status = 0xC000
            self.DIMSE.send_msg(rsp, self.pcid)
            return None

        return ds

    def _user_callback(self, ds, rsp):
        """Call the user's on_c_get callback."""
        try:
            result = self.AE.on_c_get(ds)
        except:
            LOGGER.exception("Exception in user's on_c_get implementation.")
            # Failure - Unable to process - Error in on_c_get callback
            rsp.Status = 0xC001
            self.DIMSE.send_msg(rsp, self.pcid)
            return None

        return result

    def _get_number_suboperations(self, generator, rsp):
        """Get the number of suboperations."""
        try:
            no_remaining = int(next(generator))
        except TypeError:
            LOGGER.exception('You must yield the number of sub-operations in '
                             'ae.on_c_get before yielding the (status, '
                             'dataset) pairs.')
            # Failure - Unable to process - Error in on_c_get yield
            rsp.Status = 0xC002
            self.DIMSE.send_msg(rsp, self.pcid)
            return None

        return no_remaining

    def _get_status(self, ds, rsp):
        """Check the callback's returned status dataset and set rsp.Status."""
        # Check the callback's returned Status dataset
        if isinstance(ds, Dataset) and 'Status' in ds:
            # Check returned dataset Status element value is OK
            if int(ds.Status) not in self.statuses:
                LOGGER.error("Status dataset yielded by on_c_get callback "
                             "contains a Status element with an unknown value: "
                             "0x{0:04x}.".format(ds.Status))
                # Failure: Unable to Process - Invalid Status returned
                rsp.Status = 0xC002
                return rsp

            # For the elements in the status dataset, try and set the
            #   corresponding response primitive attribute
            for elem in ds:
                if hasattr(rsp, elem.keyword):
                    setattr(rsp, elem.keyword, elem.value)
                else:
                    LOGGER.warning("Status dataset yielded by on_c_get "
                                   "callback contained an unsupported "
                                   "Element '{}'.".format(elem.keyword))
        else:
            LOGGER.error("Callback yielded an invalid status "
                         "(should be a pydicom Dataset with a Status "
                         "element).")
            # Failure: Unable to Process - callback didn't yield/return
            #   a pydicom.dataset.Dataset with a Status element.
            rsp.Status = 0xC003

        return rsp

    def _get_store_status(self, ds):
        """Check the on_c_store's returned status dataset and set rsp.Status."""
        # Check the callback's returned Status dataset
        if isinstance(ds, Status) and 'Status' in ds:
            # Check returned dataset Status element value is OK
            if ds.Status not in self.statuses:
                LOGGER.error("Status dataset yielded by on_c_store callback "
                             "contains a Status element with an unknown value: "
                             "0x{0:04x}.".format(ds.Status))
                # Failure: Unable to Process - Invalid Status returned
                status = 0xC002
            # User's status is OK
            status = ds.Status
        else:
            LOGGER.error("Callback yielded an invalid status "
                         "(should be a pydicom Dataset with a Status "
                         "element).")
            # Failure: Unable to Process - callback didn't yield/return
            #   a pydicom.dataset.Dataset with a Status element.
            status = 0xC003

        return status



# WORKLIST SOP Classes
class BasicWorklistServiceClass(ServiceClass): pass


class ModalityWorklistServiceSOPClass(BasicWorklistServiceClass):
    """Implements the Modality Worklist Service Class.

    Status
    ------
    Based on PS3.4 Annex K.4.1.1.4 (FIXME)

    * Indicates service class specific status codes

    Success
        Success: Sub-operations complete, no failures - 0x0000
    Pending
        *Pending: Matches are continuing - warning that one or more Optional
            Keys were not supported for existence for this Identifier - 0xFF01
        *Pending: Matches are continuing - current match is supplied and any
            Optional Keys were supported in the same manner as Required Keys
            - 0xFF00
    Cancel
        Cancel: Sub-operations terminated due to Cancel indication - 0xFE00
    Failure
        *Refused: Out of Resources - 0xA700
        *Identifier Does Not Match SOP Class - 0xA900
        *Unable to Process - 0xCxxx
    """
    statuses = MODALITY_WORKLIST_SERVICE_CLASS_STATUS

    # FIXME
    def SCP(self, msg):
        """SCP"""
        ds = decode(msg.Identifier,
                    self.transfersyntax.is_implicit_VR,
                    self.transfersyntax.is_little_endian)

        # make response
        rsp = C_FIND()
        rsp.MessageIDBeingRespondedTo = msg.MessageID
        rsp.AffectedSOPClassUID = msg.AffectedSOPClassUID

        gen = self.AE.OnReceiveFind(self, ds)
        try:
            while 1:
                time.sleep(0.001)
                dataset, status = gen.next()
                rsp.Status = int(status)
                rsp.Identifier = encode(dataset,
                                        self.transfersyntax.is_implicit_VR,
                                        self.transfersyntax.is_little_endian)
                # send response
                self.DIMSE.send_msg(rsp, self.pcid)
        except StopIteration:
            # send final response
            rsp = C_FIND()
            rsp.MessageIDBeingRespondedTo = msg.MessageID.value
            rsp.AffectedSOPClassUID = msg.AffectedSOPClassUID.value
            rsp.Status = int(self.Success)
            self.DIMSE.send_msg(rsp, self.pcid)


# Generate the various SOP classes
_VERIFICATION_CLASSES = {'VerificationSOPClass' : '1.2.840.10008.1.1'}

# pylint: disable=line-too-long
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

# pylint: enable=line-too-long
_generate_service_sop_classes(_VERIFICATION_CLASSES, VerificationServiceClass)
_generate_service_sop_classes(_STORAGE_CLASSES, StorageServiceClass)
_generate_service_sop_classes(_QR_FIND_CLASSES, QueryRetrieveFindServiceClass)
_generate_service_sop_classes(_QR_MOVE_CLASSES, QueryRetrieveMoveServiceClass)
_generate_service_sop_classes(_QR_GET_CLASSES, QueryRetrieveGetServiceClass)

# pylint: disable=no-member
STORAGE_CLASS_LIST = StorageServiceClass.__subclasses__()
QR_FIND_CLASS_LIST = QueryRetrieveFindServiceClass.__subclasses__()
QR_MOVE_CLASS_LIST = QueryRetrieveMoveServiceClass.__subclasses__()
QR_GET_CLASS_LIST = QueryRetrieveGetServiceClass.__subclasses__()
# pylint: enable=no-member

QR_CLASS_LIST = []
for class_list in [QR_FIND_CLASS_LIST, QR_MOVE_CLASS_LIST, QR_GET_CLASS_LIST]:
    QR_CLASS_LIST.extend(class_list)

def uid_to_sop_class(uid):
    """Given a `uid` return the corresponding SOP Class.

    Parameters
    ----------
    uid : pydicom.uid.UID

    Returns
    -------
    subclass of pynetdicom3.sopclass.ServiceClass
        The SOP class corresponding to `uid`

    Raises
    ------
    NotImplementedError
        The the SOP class for the given UID has not been implemented.
    """
    # Get a list of all the class members of the current module
    members = inspect.getmembers(sys.modules[__name__],
                                 lambda member: inspect.isclass(member) and \
                                                member.__module__ == __name__)

    for obj in members:
        if hasattr(obj[1], 'UID') and obj[1].UID == uid:
            return obj[1]

    raise NotImplementedError("The SOP Class for UID '{}' has not been " \
                              "implemented".format(uid))
