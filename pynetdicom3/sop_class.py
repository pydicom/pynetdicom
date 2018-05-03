"""
Defines the supported Service Classes and generates their SOP Classes.
"""
import inspect
from io import BytesIO
import logging
import sys
import time

from pydicom.dataset import Dataset
from pydicom.uid import UID

from pynetdicom3.dsutils import decode, encode
from pynetdicom3.dimse_primitives import C_STORE, C_ECHO, C_MOVE, C_GET, C_FIND
from pynetdicom3.status import (
    VERIFICATION_SERVICE_CLASS_STATUS, STORAGE_SERVICE_CLASS_STATUS,
    QR_FIND_SERVICE_CLASS_STATUS, QR_MOVE_SERVICE_CLASS_STATUS,
    QR_GET_SERVICE_CLASS_STATUS, MODALITY_WORKLIST_SERVICE_CLASS_STATUS
)

LOGGER = logging.getLogger('pynetdicom3.sop')


def _class_factory(name, uid, base_cls):
    """Generates a SOP Class subclass of `base_cls` called `name`.

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
    """The base class for all the service classes.

    TODO: Perhaps define some class attributes such as self.AE = None
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
        """Return True if `status` is valid for the service class.

        Parameters
        ----------
        status : int
            The Status value to check for validity.

        Returns
        -------
        bool
            True if the status is valid, False otherwise.
        """
        if status in self.statuses:
            return True

        return False

    def validate_status(self, status, rsp):
        """Validate `status` and set `rsp.Status` accordingly.

        Parameters
        ----------
        status : pydicom.dataset.Dataset or int
            A Dataset containing a Status element or an int.
        rsp : pynetdicom3.dimse_primitive
            The response primitive to be sent to the peer.

        Returns
        -------
        rsp : pynetdicom3.dimse_primitive
            The response primitie to be sent to the peer (containing a valid
            Status parameter).
        """
        # Check the callback's returned Status dataset
        if isinstance(status, Dataset):
            # Check that the returned status dataset contains a Status element
            if 'Status' in status:
                # For the elements in the status dataset, try and set the
                #   corresponding response primitive attribute
                for elem in status:
                    if hasattr(rsp, elem.keyword):
                        setattr(rsp, elem.keyword, elem.value)
                    else:
                        LOGGER.warning("Status dataset returned by callback "
                                       "contained an unsupported Element "
                                       "'%s'.", elem.keyword)
            else:
                LOGGER.error("User callback returned a `Dataset` without a "
                             "Status element.")
                # Failure: Cannot Understand - callback returned
                #   a pydicom.dataset.Dataset without a Status element
                rsp.Status = 0xC001
        elif isinstance(status, int):
            rsp.Status = status
        else:
            LOGGER.error("Invalid status returned by callback")
            # Failure: Cannot Understand - callback didn't return
            #   a valid status type
            rsp.Status = 0xC002

        if not self.is_valid_status(rsp.Status):
            # Failure: Cannot Understand - Unknown status returned by the
            #   callback
            LOGGER.warning("Unknown status value returned by "
                           "callback - 0x{0:04x}".format(rsp.Status))

        return rsp


# Service Class implementations
class VerificationServiceClass(ServiceClass):
    """Implementation of the Verification Service Class."""
    statuses = VERIFICATION_SERVICE_CLASS_STATUS

    def SCP(self, request):
        """
        The SCP implementation for the Verification Service Class.

        Will always return 0x0000 (Success) unless the user returns a different
        (valid) status value from the `AE.on_c_echo` callback.

        Parameters
        ----------
        request : pynetdicom3.dimse_primitives.C_ECHO
            The C-ECHO request primitive sent by the peer.

        See Also
        --------
        applicationentity.ApplicationEntity.on_c_echo
        association.Association.send_c_echo

        Notes
        -----
        **C-ECHO Request**

        *Parameters*

        | (M) Message ID
        | (M) Affected SOP Class UID

        **C-ECHO Response**

        *Parameters*

        | (U) Message ID
        | (M) Message ID Being Responded To
        | (U) Affected SOP Class UID
        | (M) Status

        *Status*

        The DICOM Standard [2]_ (Table 9.3-13) indicates that the Status value
        of a C-ECHO response "shall have a value of Success". However Section
        9.1.5.1.4 indicates it may have any of the following values:

        Success
          | ``0x0000`` Success

        Failure
          | ``0x0122`` Refused: SOP Class Not Supported
          | ``0x0210`` Refused: Duplicate Invocation
          | ``0x0211`` Refused: Unrecognised Operation
          | ``0x0212`` Refused: Mistyped Argument

        References
        ----------
        .. [1] DICOM Standard, Part 4, `Annex A <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_A>`_
        .. [2] DICOM Standard, Part 7, Sections
           `9.1.5 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.1.5>`_,
           `9.3.5 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.5>`_ and
           `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_
        """
        # Build C-ECHO response primitive
        rsp = C_ECHO()
        rsp.MessageID = request.MessageID
        rsp.MessageIDBeingRespondedTo = request.MessageID
        rsp.AffectedSOPClassUID = request.AffectedSOPClassUID

        # Try and run the user's on_c_echo callback. The callback should return
        #   the Status as either an int or Dataset, and any failures in the
        #   callback results in 0x0000 'Success'
        try:
            status = self.AE.on_c_echo()
            if isinstance(status, Dataset):
                if 'Status' not in status:
                    raise AttributeError("The 'status' dataset returned by "
                                         "'on_c_echo' must contain"
                                         "a (0000,0900) Status element")
                for elem in status:
                    if hasattr(rsp, elem.keyword):
                        setattr(rsp, elem.keyword, elem.value)
                    else:
                        LOGGER.warning("The 'status' dataset returned by "
                                       "'on_c_echo' contained an unsupported "
                                       "Element '%s'.", elem.keyword)
            elif isinstance(status, int):
                rsp.Status = status
            else:
                raise TypeError("Invalid 'status' returned by 'on_c_echo'")

            # Check Status validity
            if not self.is_valid_status(rsp.Status):
                LOGGER.warning("Unknown 'status' value returned by 'on_c_echo' "
                               "callback - 0x{0:04x}".format(rsp.Status))
        except Exception as ex:
            LOGGER.error("Exception in the 'on_c_echo' callback, responding "
                         "with default 'status' value of 0x0000 (Success).")
            LOGGER.exception(ex)
            rsp.Status = 0x0000

        # Send primitive
        self.DIMSE.send_msg(rsp, self.pcid)


class StorageServiceClass(ServiceClass):
    """Implementation of the Storage Service Class."""
    statuses = STORAGE_SERVICE_CLASS_STATUS

    def SCP(self, request):
        """The SCP implementation for the Storage Service Class.

        Parameters
        ----------
        request : pynetdicom3.dimse_primitives.C_STORE
            The C-STORE request primitive sent by the peer.

        See Also
        --------
        applicationentity.ApplicationEntity.on_c_store
        association.Association.send_c_store

        Notes
        -----

        **C-STORE Request**

        *Parameters*

        | (M) Message ID
        | (M) Affected SOP Class UID
        | (M) Affected SOP Instance UID
        | (M) Priority
        | (U) Move Originator Application Entity Title
        | (U) Move Originator Message ID
        | (M) Data Set

        **C-STORE Response**

        *Parameters*

        | (U) Message ID
        | (M) Message ID Being Responded To
        | (U) Affected SOP Class UID
        | (U) Affected SOP Instance UID
        | (M) Status

        *Status*

        Success
          | ``0x0000`` Success

        Warning
          | ``0xB000`` Warning: Coercion of Data Elements
          | ``0xB006`` Warning: Elements Discarded
          | ``0xB007`` Warning: Data Set Does Not Match SOP Class

        Failure
          | ``0x0117`` Refused: Invalid SOP Instance
          | ``0x0122`` Refused: SOP Class Not Supported
          | ``0x0124`` Refused: Not Authorised
          | ``0x0210`` Refused: Duplicate Invocation
          | ``0x0211`` Refused: Unrecognised Operation
          | ``0x0212`` Refused: Mistyped Argument
          | ``0xA700`` to ``0xA7FF`` Refused: Out of Resources
          | ``0xA900`` to ``0xA9FF`` Error: Data Set Does Not Match SOP Class
          | ``0xC000`` to ``0xCFFF`` Error: Cannot Understand

        References
        ----------
        .. [1] DICOM Standard, Part 4, `Annex B <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_B>`_.
        .. [2] DICOM Standard, Part 7, Sections
           `9.1.1 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.1.1>`_,
           `9.3.1 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.1>`_ and
           `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_.
        """
        # Build C-STORE response primitive
        rsp = C_STORE()
        rsp.MessageID = request.MessageID
        rsp.MessageIDBeingRespondedTo = request.MessageID
        rsp.AffectedSOPInstanceUID = request.AffectedSOPInstanceUID
        rsp.AffectedSOPClassUID = request.AffectedSOPClassUID

        # Attempt to decode the request's dataset
        try:
            ds = decode(request.DataSet,
                        self.transfersyntax.is_implicit_VR,
                        self.transfersyntax.is_little_endian)
        except Exception as ex:
            LOGGER.error("Failed to decode the received dataset")
            LOGGER.exception(ex)
            # Failure: Cannot Understand - Dataset decoding error
            rsp.Status = 0xC210
            rsp.ErrorComment = 'Unable to decode the dataset'
            self.DIMSE.send_msg(rsp, self.pcid)
            return

        # Attempt to run the ApplicationEntity's on_c_store callback
        try:
            rsp_status = self.AE.on_c_store(ds)
        except Exception as ex:
            LOGGER.error("Exception in the ApplicationEntity.on_c_store() "
                         "callback")
            LOGGER.exception(ex)
            # Failure: Cannot Understand - Error in on_c_store callback
            rsp_status = 0xC211

        # Validate rsp_status and set rsp.Status accordingly
        rsp = self.validate_status(rsp_status, rsp)
        self.DIMSE.send_msg(rsp, self.pcid)


class QueryRetrieveFindServiceClass(ServiceClass):
    """Implementation of the Query/Retrieve Find Service Class."""
    statuses = QR_FIND_SERVICE_CLASS_STATUS

    def SCP(self, request):
        """The SCP implementation for the Query/Retrieve Find Service Class.

        Parameters
        ----------
        request : pynetdicom3.dimse_primitives.C_FIND
            The C-FIND request primitive received from the peer.

        See Also
        --------
        applicationentity.ApplicationEntity.on_c_find
        association.Association.send_c_find

        Notes
        -----
        **C-FIND Request**

        *Parameters*

        | (M) Message ID
        | (M) Affected SOP Class UID
        | (M) Priority
        | (M) Identifier

        *Identifier*

        The C-FIND request Identifier shall contain:

        * Key Attributes values to be matched against the values of storage
          SOP Instances managed by the SCP.
        * (0008,0052) Query/Retrieve Level.
        * (0008,0053) Query/Retrieve View, if Enhanced Multi-Frame Image
          Conversion has been accepted during Extended Negotiation. It shall not
          be present otherwise.
        * (0008,0005) Specific Character Set, if expanded or replacement
          character sets may be used in any of the Attributes in the request
          Identifier. It shall not be present otherwise.
        * (0008,0201) Timezone Offset From UTC, if any Attributes of time in
          the request Identifier are to be interpreted explicitly in the
          designated local time zone. It shall not be present otherwise.

        **C-FIND Response**

        *Parameters*

        | (U) Message ID
        | (M) Message ID Being Responded To
        | (U) Affected SOP Class UID
        | (C) Identifier
        | (M) Status

        *Identifier*

        The C-FIND response shall only include an Identifier when the Status is
        'Pending'. When sent, the Identifier shall contain:

        * Key Attributes with values corresponding to Key Attributes contained
          in the Identifier of the request.
        * (0008,0052) Query/Retrieve Level.
        * (0008,0005) Specific Character Set, if expanded or replacement
          character sets may be used in any of the Attributes in the response
          Identifier. It shall not be present otherwise.
        * (0008,0201) Timezone Offset From UTC, if any Attributes of time in
          the response Identifier are to be interpreted explicitly in the
          designated local time zone. It shall not be present otherwise.

        The C-FIND response Identifier shall also contain either or both of:

        * (0008,0130) Storage Media File-Set ID and (0088,0140) Storage Media
          File-Set UID.
        * (0008,0054) Retrieve AE Title.

        The C-FIND response Identifier may also (but is not required to)
        include the (0008,0056) Instance Availability element.

        *Status*

        Success
          | ``0x0000`` Success

        Pending
          | ``0xFF00`` Matches are continuing, current match supplied
          | ``0xFF01`` Matches are continuing, warning

        Cancel
          | ``0xFE00`` Cancel

        Failure
          | ``0x0122`` SOP class not supported
          | ``0xA700`` Out of resources
          | ``0xA900`` Identifier does not match SOP class
          | ``0xC000`` to ``0xCFFF`` Unable to process

        References
        ----------
        .. [1] DICOM Standard, Part 4, `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_C>`_.
        .. [2] DICOM Standard, Part 7, Sections
           `9.1.2 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.1.2>`_,
           `9.3.2 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.2>`_ and
           `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_.
        """
        # Build C-FIND response primitive
        rsp = C_FIND()
        rsp.MessageID = request.MessageID
        rsp.MessageIDBeingRespondedTo = request.MessageID
        rsp.AffectedSOPClassUID = request.AffectedSOPClassUID

        # Decode and log Identifier
        try:
            identifier = decode(request.Identifier,
                                self.transfersyntax.is_implicit_VR,
                                self.transfersyntax.is_little_endian)
            LOGGER.info('Find SCP Request Identifiers:')
            LOGGER.info('')
            LOGGER.debug('# DICOM Dataset')
            for elem in identifier.iterall():
                LOGGER.info(elem)
            LOGGER.info('')
        except Exception as ex:
            LOGGER.error("Failed to decode the request's Identifier dataset.")
            LOGGER.exception(ex)
            # Failure - Unable to Process - Failed to decode Identifier
            rsp.Status = 0xC310
            rsp.ErrorComment = 'Unable to decode the dataset'
            self.DIMSE.send_msg(rsp, self.pcid)
            return

        stopper = object()
        # This will wrap exceptions during iteration and return a good value.
        def wrap_on_c_find():
            try:
                # We unpack here so that the error is still caught
                for val1, val2 in self.AE.on_c_find(identifier):
                    yield val1, val2
            except Exception:
                # TODO: special (singleton) value
                yield stopper, sys.exc_info()

        ii = -1  # So if there are no results, log below doesn't break
        # Iterate through the results
        for ii, (rsp_status, rsp_identifier) in enumerate(wrap_on_c_find()):
            # We only want to catch exceptions in the user code, not in ours.
            if rsp_status is stopper:
                exc_info = rsp_identifier
                LOGGER.exception("Exception in user's on_c_find implementation.", exc_info=exc_info)
                # Failure - Unable to Process - Error in on_c_find callback
                rsp.Status = 0xC311
                self.DIMSE.send_msg(rsp, self.pcid)
                return
            # Validate rsp_status and set rsp.Status accordingly
            rsp = self.validate_status(rsp_status, rsp)

            if rsp.Status in self.statuses:
                status = self.statuses[rsp.Status]
            else:
                # Unknown status
                self.DIMSE.send_msg(rsp, self.pcid)
                return

            if status[0] == 'Cancel':
                # If cancel, then rsp_identifier is None
                LOGGER.info('Received C-CANCEL-FIND RQ from peer')
                LOGGER.info('Find SCP Response: (Cancel)')
                self.DIMSE.send_msg(rsp, self.pcid)
                return
            elif status[0] == 'Failure':
                # If failed, then rsp_identifier is None
                LOGGER.info('Find SCP Response: (Failure - %s)', status[1])
                self.DIMSE.send_msg(rsp, self.pcid)
                return
            elif status[0] == 'Success':
                # User isn't supposed to send these, but handle anyway
                # If success, then rsp_identifier is None
                LOGGER.info('Find SCP Response: %s (Success)', ii + 1)
                self.DIMSE.send_msg(rsp, self.pcid)
                return
            elif status[0] == 'Pending':
                # If pending, the rsp_identifier is the Identifier dataset
                bytestream = encode(rsp_identifier,
                                    self.transfersyntax.is_implicit_VR,
                                    self.transfersyntax.is_little_endian)
                bytestream = BytesIO(bytestream)

                if bytestream.getvalue() == b'':
                    LOGGER.error("Failed to encode the received Identifier "
                                 "dataset")
                    # Failure: Unable to Process - Can't decode dataset
                    #   returned by on_c_find callback
                    rsp.Status = 0xC312
                    self.DIMSE.send_msg(rsp, self.pcid)
                    return

                rsp.Identifier = bytestream

                LOGGER.info('Find SCP Response: %s (Pending)', ii + 1)
                LOGGER.debug('Find SCP Response Identifier:')
                LOGGER.debug('')
                LOGGER.debug('# DICOM Dataset')
                for elem in rsp_identifier.iterall():
                    LOGGER.debug(elem)
                LOGGER.debug('')

                self.DIMSE.send_msg(rsp, self.pcid)

            # Reset the response Identifier
            rsp.Identifier = None

        # Send final success response
        rsp.Status = 0x0000
        LOGGER.info('Find SCP Response: %s (Success)', ii + 2)
        self.DIMSE.send_msg(rsp, self.pcid)


class QueryRetrieveMoveServiceClass(ServiceClass):
    """Implements the Query/Retrieve Move Service Class."""
    statuses = QR_MOVE_SERVICE_CLASS_STATUS

    def SCP(self, request):
        """The SCP implementation for the Query/Retrieve Move Service Class.

        Parameters
        ----------
        request : pynetdicom3.dimse_primitives.C_MOVE
            The C-MOVE request primitive sent by the peer.

        See Also
        --------
        applicationentity.ApplicationEntity.on_c_move
        association.Association.send_c_move

        Notes
        -----
        **C-MOVE Request**

        *Parameters*

        | (M) Message ID
        | (M) Affected SOP Class UID
        | (M) Priority
        | (M) Move Destination
        | (M) Identifier

        *Identifier*

        The C-MOVE request Identifier shall contain:

        * (0008,0052) Query/Retrieve Level.
        * Unique Key Attributes, which may include:

          - (0010,0020) Patient ID
          - (0020,000D) Study Instance UIDs
          - (0020,000E) Series Instance UIDs
          - (0008,0018) SOP Instance UIDs

        * (0008,0053) Query/Retrieve View, if Enhanced Multi-Frame Image
          Conversion has been accepted during Extended Negotiation. It shall
          not be present otherwise.
        * (0008,0005) Specific Character Set, if (0010,0020) Patient ID is
          using a character set other than the default character repertoire.

        **C-MOVE Response**

        *Parameters*

        | (U) Message ID
        | (M) Message ID Being Responded To
        | (U) Affected SOP Class UID
        | (U) Identifier
        | (M) Status
        | (C) Number of Remaining Sub-operations
        | (C) Number of Completed Sub-operations
        | (C) Number of Failed Sub-operations
        | (C) Number of Warning Sub-operations

        *Identifier*

        If the C-MOVE response Status is 'Cancelled', 'Failure', 'Refused' or
        'Warning' then the Identifier shall contain:

        * (0008,0058) Failed SOP Instance UID List

        If the C-MOVE response Status is 'Pending' then there is no Identifier.

        *Status*

        Success
          | ``0x0000`` Sub-operations complete: no failures

        Pending
          | ``0xFF00`` Sub-operations are continuing

        Cancel
          | ``0xFE00`` Sub-operations terminated due to Cancel indication

        Failure
          | ``0x0122`` SOP class not supported
          | ``0x0124`` Not authorised
          | ``0x0210`` Duplicate invocation
          | ``0x0211`` Unrecognised operation
          | ``0x0212`` Mistyped argument
          | ``0xA701`` Out of resources: unable to calculate number of matches
          | ``0xA702`` Out of resources, unable to perform sub-operations
          | ``0xA801`` Move destination unknown
          | ``0xA900`` Identifier does not match SOP class
          | ``0xC000`` to ``0xCFFF`` Unable to process

        Warning
          | ``0xB000`` Sub-operations complete: one or more failures

        *Number of X Sub-operations*

        Inclusion of the 'Number of X Sub-operations' parameters is conditional
        on the value of the response Status. For a given Status category, the
        table below states whether or not the response shall contain, shall not
        contain or may contain the 'Number of X Sub-operations' parameter.

        +-----------+------------------------------------------+
        |           | Number of "X" Sub-operations             |
        +-----------+-----------+-----------+--------+---------+
        | Status    | Remaining | Completed | Failed | Warning |
        +===========+===========+===========+========+=========+
        | Pending   | shall     | shall     | shall  | shall   |
        +-----------+-----------+-----------+--------+---------+
        | Cancelled | may       | may       | may    | may     |
        +-----------+-----------+-----------+--------+---------+
        | Warning   | shall not | may       | may    | may     |
        +-----------+-----------+-----------+--------+---------+
        | Failure   | shall not | may       | may    | may     |
        +-----------+-----------+-----------+--------+---------+
        | Success   | shall not | may       | may    | may     |
        +-----------+-----------+-----------+--------+---------+

        References
        ----------
        .. [1] DICOM Standard, Part 4, `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_C>`_.
        .. [2] DICOM Standard, Part 7, Sections
           `9.1.4 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.1.4>`_,
           `9.3.4 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.4>`_ and
           `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_.
        """
        # Build C-MOVE response primitive
        rsp = C_MOVE()
        rsp.MessageID = request.MessageID
        rsp.MessageIDBeingRespondedTo = request.MessageID
        rsp.AffectedSOPClassUID = request.AffectedSOPClassUID

        # Attempt to decode the request's Identifier dataset
        try:
            identifier = decode(request.Identifier,
                                self.transfersyntax.is_implicit_VR,
                                self.transfersyntax.is_little_endian)
            LOGGER.info('Move SCP Request Identifier:')
            LOGGER.info('')
            LOGGER.debug('# DICOM Data Set')
            for elem in identifier.iterall():
                LOGGER.info(elem)
            LOGGER.info('')
        except Exception as ex:
            LOGGER.error("Failed to decode the request's Identifier dataset")
            LOGGER.exception(ex)
            # Failure: Cannot Understand - Dataset decoding error
            rsp.Status = 0xC510
            rsp.ErrorComment = 'Unable to decode the dataset'
            self.DIMSE.send_msg(rsp, self.pcid)
            return

        # Callback - C-MOVE
        try:
            # yields (addr, port), int, (status, dataset), ...
            result = self.AE.on_c_move(identifier, request.MoveDestination)
        except Exception as ex:
            LOGGER.error("Exception in user's on_c_move implementation.")
            LOGGER.exception(ex)
            # Failure - Unable to process - Error in on_c_move callback
            rsp.Status = 0xC511
            self.DIMSE.send_msg(rsp, self.pcid)
            return

        try:
            destination = next(result)
            no_suboperations = next(result)
        except StopIteration:
            LOGGER.exception("The on_c_move callback must yield the (address, "
                             "port) of the destination AE, then yield the "
                             "number of sub-operations, then yield (status "
                             "dataset) pairs.")
            # Failure - Unable to process - Error in on_c_move yield
            rsp.Status = 0xC514
            self.DIMSE.send_msg(rsp, self.pcid)
            return

        # Check number of C-STORE sub-operations
        try:
            no_suboperations = int(no_suboperations)
        except Exception as ex:
            LOGGER.error("'on_c_move' yielded an invalid number of "
                         "sub-operations value")
            LOGGER.exception(ex)
            rsp.Status = 0xC513
            self.DIMSE.send_msg(rsp, self.pcid)
            return

        # Request new association with Move Destination
        try:
            # Unknown Move Destination
            if None in destination:
                LOGGER.error('Unknown Move Destination: %s',
                             request.MoveDestination.decode('utf-8'))
                # Failure - Move destination unknown
                rsp.Status = 0xA801
                self.DIMSE.send_msg(rsp, self.pcid)
                return

            store_assoc = self.AE.associate(destination[0], destination[1],
                                            request.MoveDestination)
        except Exception as ex:
            LOGGER.error("'on_c_move' yielded an invalid destination AE (addr, "
                         "port) value")
            LOGGER.exception(ex)
            # Failure - Unable to process - Bad on_c_move destination
            rsp.Status = 0xC515
            self.DIMSE.send_msg(rsp, self.pcid)
            return

        # Track the sub operation results [remaining, failed, warning, complete]
        store_results = [no_suboperations, 0, 0, 0]

        # Store the SOP Instance UIDs from any failed C-STORE sub-operations
        failed_instances = []
        def _add_failed_instance(ds):
            if hasattr(ds, 'SOPInstanceUID'):
                failed_instances.append(ds.SOPInstanceUID)

        if store_assoc.is_established:
            # Iterate through the remaining callback (status, dataset) yields
            for ii, (rsp_status, dataset) in enumerate(result):
                # All sub-operations are complete
                if store_results[0] <= 0:
                    LOGGER.warning("'on_c_move' yielded further (status, "
                                   "dataset) results but these will be "
                                   "ignored as the sub-operations are "
                                   "complete")
                    break

                # Validate rsp_status and set rsp.Status accordingly
                rsp = self.validate_status(rsp_status, rsp)
                if rsp.Status in self.statuses:
                    status = self.statuses[rsp.Status]
                else:
                    # Unknown status
                    store_assoc.release()
                    self.DIMSE.send_msg(rsp, self.pcid)
                    return

                # If usr_status is Cancel, Failure, Warning or Success then
                #   generate a final response, if Pending then do C-STORE
                #   sub-operation
                if status[0] == 'Cancel':
                    # If cancel, then dataset is a Dataset with a
                    #   'FailedSOPInstanceUIDList' element
                    LOGGER.info('Move SCP Received C-CANCEL-MOVE RQ from peer')
                    store_assoc.release()

                    # In case user didn't include it
                    if (not isinstance(dataset, Dataset) or
                        'FailedSOPInstanceUIDList' not in dataset):
                        dataset = Dataset()
                        dataset.FailedSOPInstanceUIDList = failed_instances

                    bytestream = encode(dataset,
                                        self.transfersyntax.is_implicit_VR,
                                        self.transfersyntax.is_little_endian)

                    rsp.Identifier = BytesIO(bytestream)
                    rsp.NumberOfRemainingSuboperations = store_results[0]
                    rsp.NumberOfFailedSuboperations = store_results[1]
                    rsp.NumberOfWarningSuboperations = store_results[2]
                    rsp.NumberOfCompletedSuboperations = store_results[3]

                    self.DIMSE.send_msg(rsp, self.pcid)
                    return
                elif status[0] in ['Failure', 'Warning']:
                    # If failed or warning, then dataset is a Dataset with a
                    #   'FailedSOPInstanceUIDList' element
                    LOGGER.info('Move SCP Result (%s - %s)',
                                status[0],
                                status[1])
                    store_assoc.release()

                    # In case user didn't include it
                    if (not isinstance(dataset, Dataset) or
                        'FailedSOPInstanceUIDList' not in dataset):
                        dataset = Dataset()
                        dataset.FailedSOPInstanceUIDList = failed_instances

                    bytestream = encode(dataset,
                                        self.transfersyntax.is_implicit_VR,
                                        self.transfersyntax.is_little_endian)

                    rsp.Identifier = BytesIO(bytestream)
                    rsp.NumberOfRemainingSuboperations = None
                    rsp.NumberOfFailedSuboperations = (
                        store_results[1] + store_results[0]
                    )
                    rsp.NumberOfWarningSuboperations = store_results[2]
                    rsp.NumberOfCompletedSuboperations = store_results[3]

                    self.DIMSE.send_msg(rsp, self.pcid)
                    return
                elif status[0] == 'Success':
                    # If success, then dataset is None
                    store_assoc.release()

                    # If the user yields Success, check it
                    if store_results[1] or store_results[2]:
                        LOGGER.info('Move SCP Response: (Warning)')

                        ds = Dataset()
                        ds.FailedSOPInstanceUIDList = failed_instances
                        bytestream = encode(ds,
                                            self.transfersyntax.is_implicit_VR,
                                            self.transfersyntax.is_little_endian)

                        rsp.Identifier = BytesIO(bytestream)
                        rsp.Status = 0xB000
                    else:
                        LOGGER.info('Move SCP Response: (Warning)')
                        rsp.Identifier = None

                    rsp.NumberOfRemainingSuboperations = None
                    rsp.NumberOfFailedSuboperations = store_results[1]
                    rsp.NumberOfWarningSuboperations = store_results[2]
                    rsp.NumberOfCompletedSuboperations = store_results[3]

                    self.DIMSE.send_msg(rsp, self.pcid)
                    return
                elif status[0] == 'Pending' and dataset:
                    # If pending, then dataset is the Dataset to send
                    if not isinstance(dataset, Dataset):
                        LOGGER.error('Received invalid dataset from callback')
                        # Count as a sub-operation failure
                        store_results[1] += 1
                        failed_instances.append('')
                        rsp.Identifier = None
                        rsp.NumberOfRemainingSuboperations = store_results[0]
                        rsp.NumberOfFailedSuboperations = store_results[1]
                        rsp.NumberOfWarningSuboperations = store_results[2]
                        rsp.NumberOfCompletedSuboperations = store_results[3]
                        self.DIMSE.send_msg(rsp, self.pcid)
                        continue

                    LOGGER.info('Move SCP Response %s (Pending)', ii)

                    # Send `dataset` via C-STORE sub-operations over the
                    #   association and check that the response's Status exists
                    #   and is a known value
                    try:
                        # TODO: Consider adding the move originator
                        store_status = store_assoc.send_c_store(dataset)
                        # FIXME: Should probably split status check?
                        store_status = STORAGE_SERVICE_CLASS_STATUS[
                            store_status.Status]
                    except Exception as ex:
                        # An exception implies a C-STORE failure
                        LOGGER.warning("C-STORE sub-operation failed.")
                        store_status = ['Failure', 'Unknown']

                    LOGGER.info('Move SCP: Received Store SCU response (%s)',
                                store_status[0])

                    # Update the C-STORE sub-operation result tracker
                    if store_status[0] == 'Failure':
                        store_results[1] += 1
                        _add_failed_instance(dataset)
                    elif store_status[0] == 'Warning':
                        store_results[2] += 1
                        _add_failed_instance(dataset)
                    elif store_status[0] == 'Success':
                        store_results[3] += 1

                    store_results[0] -= 1

                    rsp.Identifier = None
                    rsp.NumberOfRemainingSuboperations = store_results[0]
                    rsp.NumberOfFailedSuboperations = store_results[1]
                    rsp.NumberOfWarningSuboperations = store_results[2]
                    rsp.NumberOfCompletedSuboperations = store_results[3]

                    self.DIMSE.send_msg(rsp, self.pcid)

            store_assoc.release()

        else:
            # Failed to associate with Move Destination AE
            LOGGER.error('Move SCP: Unable to associate with destination AE')
            rsp.Status = 0xA801
            self.DIMSE.send_msg(rsp, self.pcid)

            # FIXME - shouldn't have to manually close the socket like this
            store_assoc.dul.scu_socket.close()
            return

        # If not already done, send the final 'Success' or 'Warning' response
        if not store_results[1] and not store_results[2]:
            # Success response - no failures or warnings
            LOGGER.info('Move SCP Result: (Success)')
            rsp.Status = 0x0000
        else:
            # Warning response - one or more failures or warnings
            LOGGER.info('Move SCP Result: (Warning)')
            rsp.Status = 0xB000
            # If Warning response, need to return an Identifier with
            #   (0008, 0058) Failed SOP Instance UID List element
            ds = Dataset()
            ds.FailedSOPInstanceUIDList = failed_instances
            bytestream = encode(ds,
                                self.transfersyntax.is_implicit_VR,
                                self.transfersyntax.is_little_endian)
            rsp.Identifier = BytesIO(bytestream)

        rsp.NumberOfRemainingSuboperations = None
        rsp.NumberOfFailedSuboperations = store_results[1]
        rsp.NumberOfWarningSuboperations = store_results[2]
        rsp.NumberOfCompletedSuboperations = store_results[3]

        self.DIMSE.send_msg(rsp, self.pcid)


class QueryRetrieveGetServiceClass(ServiceClass):
    """Implements the Query/Retrieve Get Service Class."""
    statuses = QR_GET_SERVICE_CLASS_STATUS

    def SCP(self, request):
        """The SCP implementation for the Query/Retrieve Get Service Class.

        Parameters
        ----------
        request : pynetdicom3.dimse_primitives.C_GET
            The C-GET request primitive sent by the peer.

        See Also
        --------
        applicationentity.ApplicationEntity.on_c_get
        association.Association.send_c_get

        Notes
        -----
        **C-GET Request**

        *Parameters*

        | (M) Message ID
        | (M) Affected SOP Class UID
        | (M) Priority
        | (M) Identifier

        *Identifier*

        The C-GET request Identifier shall contain:

        * (0008,0052) Query/Retrieve Level.
        * Unique Key Attributes, which may include:

          - (0010,0020) Patient ID
          - (0020,000D) Study Instance UIDs
          - (0020,000E) Series Instance UIDs
          - (0008,0018) SOP Instance UIDs

        * (0008,0053) Query/Retrieve View, if Enhanced Multi-Frame Image
          Conversion has been accepted during Extended Negotiation. It shall
          not be present otherwise.
        * (0008,0005) Specific Character Set, if (0010,0020) Patient ID is
          using a character set other than the default character repertoire.

        **C-GET Response**

        *Parameters*

        | (U) Message ID
        | (M) Message ID Being Responded To
        | (U) Affected SOP Class UID
        | (U) Identifier
        | (M) Status
        | (C) Number of Remaining Sub-operations
        | (C) Number of Completed Sub-operations
        | (C) Number of Failed Sub-operations
        | (C) Number of Warning Sub-operations

        *Identifier*

        If the C-GET response Status is 'Cancelled', 'Failure', 'Refused' or
        'Warning' then the Identifier shall contain:

        * (0008,0058) Failed SOP Instance UID List

        If the C-GET response Status is 'Pending' then there is no Identifier.

        *Status*

        Success
          | ``0x0000`` Sub-operations complete: no failures or warnings

        Pending
          | ``0xFF00`` Sub-operations are continuing

        Cancel
          | ``0xFE00`` Sub-operations terminated due to Cancel indication

        Failure
          | ``0x0122`` SOP class not supported
          | ``0x0124`` Not authorised
          | ``0x0210`` Duplicate invocation
          | ``0x0211`` Unrecognised operation
          | ``0x0212`` Mistyped argument
          | ``0xA701`` Out of resources: unable to calculate number of matches
          | ``0xA702`` Out of resources: unable to perform sub-operations
          | ``0xA900`` Identifier does not match SOP class
          | ``0xC000`` to ``0xCFFF`` Unable to process

        Warning
          | ``0xB000`` Sub-operations complete: one or more failures or warnings

        *Number of X Sub-operations*

        Inclusion of the 'Number of X Sub-operations' parameters is conditional
        on the value of the response Status. For a given Status category, the
        table below states whether or not the response shall contain, shall not
        contain or may contain the 'Number of X Sub-operations' parameter.

        +-----------+------------------------------------------+
        |           | Number of "X" Sub-operations             |
        +-----------+-----------+-----------+--------+---------+
        | Status    | Remaining | Completed | Failed | Warning |
        +===========+===========+===========+========+=========+
        | Pending   | shall     | shall     | shall  | shall   |
        +-----------+-----------+-----------+--------+---------+
        | Cancelled | may       | may       | may    | may     |
        +-----------+-----------+-----------+--------+---------+
        | Warning   | shall not | may       | may    | may     |
        +-----------+-----------+-----------+--------+---------+
        | Failure   | shall not | may       | may    | may     |
        +-----------+-----------+-----------+--------+---------+
        | Success   | shall not | may       | may    | may     |
        +-----------+-----------+-----------+--------+---------+

        References
        ----------
        .. [1] DICOM Standard, Part 4, `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_C>`_.
        .. [2] DICOM Standard, Part 7, Sections
           `9.1.3 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.1.3>`_,
           `9.3.3 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.3>`_ and
           `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_.
        """
        # Build C-GET response primitive
        rsp = C_GET()
        rsp.MessageID = request.MessageID
        rsp.MessageIDBeingRespondedTo = request.MessageID
        rsp.AffectedSOPClassUID = request.AffectedSOPClassUID

        # Attempt to decode the request's Identifier dataset
        try:
            identifier = decode(request.Identifier,
                                self.transfersyntax.is_implicit_VR,
                                self.transfersyntax.is_little_endian)
            LOGGER.info('Get SCP Request Identifier:')
            LOGGER.info('')
            LOGGER.debug('# DICOM Data Set')
            for elem in identifier.iterall():
                LOGGER.info(elem)
            LOGGER.info('')
        except Exception as ex:
            LOGGER.error("Failed to decode the request's Identifier dataset")
            LOGGER.exception(ex)
            # Failure: Cannot Understand - Dataset decoding error
            rsp.Status = 0xC410
            rsp.ErrorComment = 'Unable to decode the dataset'
            self.DIMSE.send_msg(rsp, self.pcid)
            return

        # Callback - C-GET
        try:
            # yields int, (status, dataset), ...
            result = self.AE.on_c_get(identifier)
        except Exception as ex:
            LOGGER.error("Exception in user's on_c_get implementation.")
            LOGGER.exception(ex)
            rsp.Status = 0xC411
            self.DIMSE.send_msg(rsp, self.pcid)
            return

        # Number of C-STORE sub-operations
        try:
            no_suboperations = int(next(result))
        except Exception as ex:
            LOGGER.error("'on_c_get' yielded an invalid number of "
                         "sub-operations value")
            LOGGER.exception(ex)
            rsp.Status = 0xC413
            self.DIMSE.send_msg(rsp, self.pcid)
            return

        # Track the sub operation results [remaining, failed, warning, complete]
        store_results = [no_suboperations, 0, 0, 0]

        # Store the SOP Instance UIDs from any failed C-STORE sub-operations
        failed_instances = []
        def _add_failed_instance(ds):
            if hasattr(ds, 'SOPInstanceUID'):
                failed_instances.append(ds.SOPInstanceUID)

        # Iterate through the results
        # C-GET Pending responses are optional!
        for ii, (rsp_status, dataset) in enumerate(result):
            # All sub-operations are complete
            if store_results[0] <= 0:
                LOGGER.warning("'on_c_get' yielded further (status, dataset) "
                               "results but these will be ignored as the "
                               "sub-operations are complete")
                break

            # Validate rsp_status and set rsp.Status accordingly
            rsp = self.validate_status(rsp_status, rsp)
            if rsp.Status in self.statuses:
                status = self.statuses[rsp.Status]
            else:
                # Unknown status
                self.DIMSE.send_msg(rsp, self.pcid)
                return

            if status[0] == 'Cancel':
                # If cancel, dataset is a Dataset with a
                # 'FailedSOPInstanceUIDList' element
                LOGGER.info('Get SCP Received C-CANCEL-GET RQ from peer')
                rsp.NumberOfRemainingSuboperations = store_results[0]
                rsp.NumberOfFailedSuboperations = store_results[1]
                rsp.NumberOfWarningSuboperations = store_results[2]
                rsp.NumberOfCompletedSuboperations = store_results[3]

                # In case user didn't include it
                if (not isinstance(dataset, Dataset) or
                    'FailedSOPInstanceUIDList' not in dataset):
                    dataset = Dataset()
                    dataset.FailedSOPInstanceUIDList = failed_instances

                bytestream = encode(dataset,
                                    self.transfersyntax.is_implicit_VR,
                                    self.transfersyntax.is_little_endian)
                rsp.Identifier = BytesIO(bytestream)
                self.DIMSE.send_msg(rsp, self.pcid)
                return
            elif status[0] in ['Failure', 'Warning']:
                # If failure or warning, dataset is a Dataset with a
                # 'FailedSOPInstanceUIDList' element
                LOGGER.info('Get SCP Result (%s - %s)', status[0], status[1])
                rsp.NumberOfRemainingSuboperations = None
                rsp.NumberOfFailedSuboperations = (
                    store_results[1] + store_results[0]
                )
                rsp.NumberOfWarningSuboperations = store_results[2]
                rsp.NumberOfCompletedSuboperations = store_results[3]

                # In case user didn't include it
                if (not isinstance(dataset, Dataset) or
                    'FailedSOPInstanceUIDList' not in dataset):
                    dataset = Dataset()
                    dataset.FailedSOPInstanceUIDList = failed_instances

                bytestream = encode(dataset,
                                    self.transfersyntax.is_implicit_VR,
                                    self.transfersyntax.is_little_endian)
                rsp.Identifier = BytesIO(bytestream)
                self.DIMSE.send_msg(rsp, self.pcid)
                return
            elif status[0] == 'Success':
                # If user yields Success, check it
                # dataset is None
                if store_results[1] or store_results[2]:
                    LOGGER.info('Get SCP Response: (Warning)')
                    rsp.Status = 0xB000
                    ds = Dataset()
                    ds.FailedSOPInstanceUIDList = failed_instances
                    bytestream = encode(ds,
                                        self.transfersyntax.is_implicit_VR,
                                        self.transfersyntax.is_little_endian)
                    rsp.Identifier = BytesIO(bytestream)
                else:
                    LOGGER.info('Get SCP Response: (Success)')
                    rsp.Identifier = None

                rsp.NumberOfRemainingSuboperations = None
                rsp.NumberOfFailedSuboperations = store_results[1]
                rsp.NumberOfWarningSuboperations = store_results[2]
                rsp.NumberOfCompletedSuboperations = store_results[3]

                self.DIMSE.send_msg(rsp, self.pcid)
                return
            elif status[0] == 'Pending' and dataset:
                # If pending, dataset is the Dataset to send
                if not isinstance(dataset, Dataset):
                    LOGGER.error('Received invalid dataset from callback')
                    # Count as a sub-operation failure
                    store_results[1] += 1
                    failed_instances.append('')
                    rsp.Identifier = None
                    rsp.NumberOfRemainingSuboperations = store_results[0]
                    rsp.NumberOfFailedSuboperations = store_results[1]
                    rsp.NumberOfWarningSuboperations = store_results[2]
                    rsp.NumberOfCompletedSuboperations = store_results[3]
                    self.DIMSE.send_msg(rsp, self.pcid)
                    continue

                LOGGER.info('Get SCP Response: %s (Pending)', ii + 1)

                # Send `dataset` via C-STORE sub-operations over the existing
                #   association and check that the response's Status exists and
                #   is a known value
                try:
                    store_status = self.ACSE.parent.send_c_store(dataset)
                    store_status = \
                        STORAGE_SERVICE_CLASS_STATUS[store_status.Status]
                except Exception as ex:
                    # An exception implies a C-STORE failure
                    LOGGER.warning("C-STORE sub-operation failed.")
                    store_status = ['Failure', 'Unknown']

                LOGGER.info('Get SCP: Received Store SCU response (%s)',
                            store_status[0])

                # Update the C-STORE sub-operation result tracker
                if store_status[0] == 'Failure':
                    store_results[1] += 1
                    _add_failed_instance(dataset)
                elif store_status[0] == 'Warning':
                    store_results[2] += 1
                    _add_failed_instance(dataset)
                elif store_status[0] == 'Success':
                    store_results[3] += 1

                store_results[0] -= 1

                rsp.Identifier = None
                rsp.NumberOfRemainingSuboperations = store_results[0]
                rsp.NumberOfFailedSuboperations = store_results[1]
                rsp.NumberOfWarningSuboperations = store_results[2]
                rsp.NumberOfCompletedSuboperations = store_results[3]
                self.DIMSE.send_msg(rsp, self.pcid)

        # If not already done, send the final 'Success' or 'Warning' response
        if not store_results[1] and not store_results[2]:
            # Success response - no failures or warnings
            LOGGER.info('Get SCP Result: (Success)')
            rsp.Status = 0x0000
        else:
            # Warning response - one or more failures or warnings
            LOGGER.info('Get SCP Result: (Warning)')
            rsp.Status = 0xB000
            # If Warning response, need to return an Identifier with
            #   (0008,0058) Failed SOP Instance UID List element
            ds = Dataset()
            ds.FailedSOPInstanceUIDList = failed_instances
            bytestream = encode(ds,
                                self.transfersyntax.is_implicit_VR,
                                self.transfersyntax.is_little_endian)
            rsp.Identifier = BytesIO(bytestream)

        rsp.NumberOfRemainingSuboperations = None
        rsp.NumberOfFailedSuboperations = store_results[1]
        rsp.NumberOfWarningSuboperations = store_results[2]
        rsp.NumberOfCompletedSuboperations = store_results[3]

        self.DIMSE.send_msg(rsp, self.pcid)


# WORKLIST Service Classes - WIP
class BasicWorklistServiceClass(ServiceClass): pass


class ModalityWorklistServiceSOPClass(BasicWorklistServiceClass):
    """Implements the Modality Worklist Service Class.

    **Status**

    Based on PS3.4 Annex K.4.1.1.4 (FIXME)

    * Indicates service class specific status codes

    Success
        Success: Sub-operations complete, no failures - 0x0000
    Pending
        * Pending: Matches are continuing - warning that one or more Optional
            Keys were not supported for existence for this Identifier - 0xFF01
        * Pending: Matches are continuing - current match is supplied and any
            Optional Keys were supported in the same manner as Required Keys
            - 0xFF00
    Cancel
        Cancel: Sub-operations terminated due to Cancel indication - 0xFE00
    Failure
        * Refused: Out of Resources - 0xA700
        * Identifier Does Not Match SOP Class - 0xA900
        * Unable to Process - 0xCxxx
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
