"""
Implementaion of the service parameter primitives.
"""
import codecs
import logging

from pydicom.uid import UID

from pynetdicom.pdu_items import (
    MaximumLengthSubItem,
    ImplementationClassUIDSubItem,
    ImplementationVersionNameSubItem,
    AsynchronousOperationsWindowSubItem,
    SCP_SCU_RoleSelectionSubItem,
    SOPClassExtendedNegotiationSubItem,
    SOPClassCommonExtendedNegotiationSubItem,
    UserIdentitySubItemRQ,
    UserIdentitySubItemAC
)
from pynetdicom.presentation import PresentationContext
from pynetdicom.utils import validate_ae_title, validate_uid
from pynetdicom._globals import DEFAULT_MAX_LENGTH

LOGGER = logging.getLogger('pynetdicom.pdu_primitives')


# TODO: Rename to UserInformation
class ServiceParameter(object):
    """ Base class for Service Parameters """

    def __eq__(self, other):
        """Equality of two ServiceParameters"""
        if isinstance(other, self.__class__):
            return other.__dict__ == self.__dict__

        return False

    def __ne__(self, other):
        """Inequality of two ServiceParameters"""
        return not self == other


# Association Service primitives
class A_ASSOCIATE(object):
    """
    An A-ASSOCIATE primitive.

    The establishment of an association between two AEs shall be performed
    through ACSE A-ASSOCIATE request, indication, response and confirmation
    primitives.

    The initiator of the service is called the Requestor and the user that
    receives the request is the Acceptor.

    The A-ASSOCIATE primitive is used by the DUL provider to send/receive
    information about the association. It gets converted to
    A-ASSOCIATE-RQ, -AC, -RJ PDUs that are sent to the peer DUL provider and
    gets deconverted from -RQ, -AC, -RJ PDUs received from the peer.

    +------------------+---------+------------+----------+--------------+
    | Parameter        | Request | Indication | Response | Confirmation |
    +------------------+---------+------------+----------+--------------+
    | app context name | M       | M(=)       | M        | M(=)         |
    +------------------+---------+------------+----------+--------------+
    | calling ae title | M       | M(=)       | M        | M(=)         |
    +------------------+---------+------------+----------+--------------+
    | called ae title  | M       | M(=)       | M        | M(=)         |
    +------------------+---------+------------+----------+--------------+
    | user info        | M       | M(=)       | M        | M(=)         |
    +------------------+---------+------------+----------+--------------+
    | result           |         |            | M        | M(=)         |
    +------------------+---------+------------+----------+--------------+
    | source           |         |            |          | M            |
    +------------------+---------+------------+----------+--------------+
    | diagnostic       |         |            | U        | C(=)         |
    +------------------+---------+------------+----------+--------------+
    | calling pres add | M       | M(=)       |          |              |
    +------------------+---------+------------+----------+--------------+
    | called pres add  | M       | M(=)       |          |              |
    +------------------+---------+------------+----------+--------------+
    | pres contxt list | M       | M(=)       |          |              |
    +------------------+---------+------------+----------+--------------+
    | pres list result |         |            | M        | M(=)         |
    +------------------+---------+------------+----------+--------------+
    | mode             | UF      | MF(=)      |          |              |
    +------------------+---------+------------+----------+--------------+
    | resp ae title    |         |            | MF       | MF(=)        |
    +------------------+---------+------------+----------+--------------+
    | resp pres add    |         |            | MF       | MF(=)        |
    +------------------+---------+------------+----------+--------------+
    | pres/sess req    | UF      | UF(=)      | UF       | UF(=)        |
    +------------------+---------+------------+----------+--------------+

    | U   - User option
    | UF  - User option, fixed value
    | C   - Conditional (on user option)
    | M   - Mandatory
    | MF  - Mandatory, fixed value
    | NU  - Not used
    | (=) - shall have same value as request or response


    Attributes
    ----------
    mode : str
        Fixed value of ``'normal'``.
    application_context_name : pydicom.uid.UID, bytes or str
        The application context name proposed by the *Requestor*. *Acceptor*
        returns either the same or a different name. Returned name specifies
        the application context used for the association. See the DICOM
        Standard, Part 8, :dcm:`Annex A<part08/chapter_A.html>`.
        The application context name shall be a valid UID or UID string and for
        version 3 of the DICOM Standard should be ``'1.2.840.10008.3.1.1.1'``
    calling_ae_title : str or bytes
        Identifies the *Requestor* of the A-ASSOCIATE service. Must be a valid
        AE title.
    called_ae_title : str or bytes
        Identifies the intended *Acceptor* of the A-ASSOCIATE service. Must be
        a valid AE title.
    responding_ae_title : str or bytes
        Identifies the AE that contains the actual acceptor of the
        A-ASSOCIATE service. Shall always contain the same value as the
        *Called AE Title* of the A-ASSOCIATE indication
    user_information : list
        Used by *Requestor* and *Acceptor* to include AE user information. See
        the DICOM Standard, Part 8, :dcm:`Annex D<part08/chapter_D.html>` and
        Part 7, :dcm:`Annex D.3<part07/sect_D.3.html>`
    result : int
        Provided either by the *Acceptor* of the A-ASSOCIATE request, the UL
        service provider (ACSE related) or the UL service provider
        (Presentation related). Indicates the result of the A-ASSOCIATE
        service. Allowed values are:

        * ``0``: accepted
        * ``1``: rejected (permanent)
        * ``2``: rejected (transient)

    result_source : int
        Identifies the creating source of the Result and Diagnostic parameters
        Allowed values are:

        * ``0``: UL service-user
        * ``1``: UL service-provider (ACSE related function)
        * ``2``: UL service-provider (presentation related function)

    diagnostic : int
        If the `result` parameter is ``0`` "rejected (permanent)" or ``1``
        "rejected (transient)" then this supplies diagnostic information about
        the result. If `result_source` is ``0`` "UL service-user" then allowed
        valuesare:

        * ``0``: no reason given
        * ``1``: application context name not supported
        * ``2``: calling AE title not recognised
        * ``3``: called AE title not recognised

        If `result_source` is ``1`` "UL service-provider (ACSE related
        function)" then allowed values are:

        * ``0``: no reason given
        * ``1``: no common UL version

        If `result_source` is ``2`` "UL service-provider (presentation related
        function)" then allowed values are:

        * ``0``: no reason given
        * ``1``: temporary congestion
        * ``2``: local limit exceeded
        * ``3``: called presentation address unknown
        * ``4``: presentation protocol version not supported
        * ``5``: no presentation service access point available

    calling_presentation_address : str
        TCP/IP address of the *Requestor*
    called_presentation_address : str
        TCP/IP address of the intended *Acceptor*
    responding_presentation_address : str
        Shall always contain the same value as the
        *Called Presentation Address*.
    presentation_context_definition_list : list
        List of one or more presentation contexts, with each item containing
        a presentation context ID, an Abstract Syntax and a list of one or
        more Transfer Syntax Names. Sent by the *Requestor* during
        request/indication.
    presentation_context_definition_results_list : list
        Used in response/confirmation to indicate acceptance or rejection of
        each presentation context definition.
        List of result values, with a one-to-one correspondence between each
        of the presentation contexts proposed in the Presentation Context
        Definition List parameter.
        The result values may be sent in any order and may be different than
        the order proposed.
        Only one Transfer Syntax per presentation context shall be agreed to
    presentation_requirements : str
        Fixed value of ``'Presentation Kernel'``.
    session_requirements : str
        Fixed value of ``''`` (empty string).

    References
    ----------

    * DICOM Standard, Part 8,
      :dcm:`Section 7.1.1<part08/chapter_7.html#sect_7.1.1>`
    """
    # pylint: disable=too-many-instance-attributes

    def __init__(self):
        self.application_context_name = None
        self.calling_ae_title = None
        self.called_ae_title = None
        self.user_information = []
        self.result = None
        self.result_source = None
        self.diagnostic = None
        self.calling_presentation_address = None
        self.called_presentation_address = None
        self.presentation_context_definition_list = []
        self.presentation_context_definition_results_list = []

    @property
    def mode(self):
        """Return the Mode parameter."""
        return "normal"

    @property
    def application_context_name(self):
        """Return the Application Context Name parameter."""
        return self._application_context_name

    @application_context_name.setter
    def application_context_name(self, value):
        """Set the Application Context Name parameter.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The value for the Application Context Name
        """
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, UID):
            pass
        elif isinstance(value, str):
            value = UID(value)
        elif isinstance(value, bytes):
            value = UID(value.decode('ascii'))
        elif value is None:
            pass
        else:
            raise TypeError("application_context_name must be a "
                            "pydicom.uid.UID, str or bytes")

        if value is not None and not validate_uid(value):
            LOGGER.error("application_context_name is an invalid UID")
            raise ValueError("application_context_name is an invalid UID")

        if value and not value.is_valid:
            LOGGER.warning(
                "The Application Context Name '{}' is non-conformant"
                .format(value)
            )

        self._application_context_name = value

    @property
    def calling_ae_title(self):
        """Return the Calling AE Title parameter."""
        return self._calling_ae_title

    @calling_ae_title.setter
    def calling_ae_title(self, value):
        """Set the Calling AE Title parameter.

        Parameters
        ----------
        value : str or bytes
            The Calling AE Title as a string or bytes object. Cannot be an
            empty string and will be truncated to 16 characters long
        """
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, str):
            value = codecs.encode(value, 'ascii')

        if value is not None:
            self._calling_ae_title = validate_ae_title(value)
        else:
            self._calling_ae_title = None

    @property
    def called_ae_title(self):
        """Return the Called AE Title parameter."""
        return self._called_ae_title

    @called_ae_title.setter
    def called_ae_title(self, value):
        """Set the Called AE Title parameter.

        Parameters
        ----------
        value : str or bytes
            The Called AE Title as a string or bytes object. Cannot be an empty
            string and will be truncated to 16 characters long
        """
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, str):
            value = codecs.encode(value, 'ascii')

        if value is not None:
            self._called_ae_title = validate_ae_title(value)
        else:
            self._called_ae_title = None

    @property
    def responding_ae_title(self):
        """Return the Responding AE Title parameter."""
        return self.called_ae_title

    @property
    def user_information(self):
        """Return the User Information parameter."""
        return self._user_information

    @user_information.setter
    def user_information(self, value_list):
        """Set the A-ASSOCIATE primitive's User Information parameter.

        Parameters
        ----------
        value_list : list of user information class objects
            A list of user information objects, must contain at least
            MaximumLengthNotification and ImplementationClassUIDNotification
        """
        # pylint: disable=attribute-defined-outside-init
        valid_usr_info_items = []

        if isinstance(value_list, list):
            # Iterate through the items and check they're an acceptable class
            for item in value_list:
                if item.__class__.__name__ in \
                        ["MaximumLengthNotification",
                         "ImplementationClassUIDNotification",
                         "ImplementationVersionNameNotification",
                         "AsynchronousOperationsWindowNegotiation",
                         "SCP_SCU_RoleSelectionNegotiation",
                         "SOPClassExtendedNegotiation",
                         "SOPClassCommonExtendedNegotiation",
                         "UserIdentityNegotiation"]:
                    valid_usr_info_items.append(item)
                else:
                    LOGGER.info("Attempted to set "
                                "A_ASSOCIATE.user_information to a list "
                                "which includes an unsupported item")
        else:
            LOGGER.error("A_ASSOCIATE.user_information must be a list")
            raise TypeError("A_ASSOCIATE.user_information must be a list")

        self._user_information = valid_usr_info_items

    @property
    def result(self):
        """Return te Result parameter."""
        return self._result

    @result.setter
    def result(self, value):
        """Set the A-ASSOCIATE Service primitive's Result parameter.

        Parameters
        ----------
        value : str
            One of the following:

            * 0: accepted
            * 1: rejected (permanent)
            * 2: rejected (transient)
        """
        # pylint: disable=attribute-defined-outside-init
        if value is None:
            pass
        elif value not in [0, 1, 2]:
            LOGGER.error("A_ASSOCIATE.result set to an unknown value")
            raise ValueError("Unknown A_ASSOCIATE.result value")

        self._result = value

    @property
    def result_str(self):
        """Return the result as str."""
        results = {1 : "Rejected Permanent", 2 : "Rejected Transient"}
        return results[self.result]

    @property
    def result_source(self):
        """Return the Result Source parameter."""
        return self._result_source

    @result_source.setter
    def result_source(self, value):
        """Set the A-ASSOCIATE Service primitive's Result Source parameter.

        Parameters
        ----------
        value : int
            One of the following:

            * 1: UL service-user
            * 2: UL service-provider (ACSE related function)
            * 3: UL service-provider (presentation related function)
        """
        # pylint: disable=attribute-defined-outside-init
        if value is None:
            pass
        elif value not in [1, 2, 3]:
            LOGGER.error("A_ASSOCIATE.result_source set to an unknown value")
            raise ValueError("Unknown A_ASSOCIATE.result_source value")

        self._result_source = value

    @property
    def source_str(self):
        """Return the reject source as str."""
        sources = {
            1 : 'Service User',
            2 : 'Service Provider (ACSE)',
            3 : 'Service Provider (Presentation)'
        }
        return sources[self.result_source]

    @property
    def diagnostic(self):
        """Return the Diagnostic parameter."""
        return self._diagnostic

    @diagnostic.setter
    def diagnostic(self, value):
        """
        Set the A-ASSOCIATE Service primitive's Diagnostic parameter

        Parameters
        ----------
        value : int
            If `result_source` is "UL service-user" then allowed values are:

            * 1: no reason given
            * 2: application context name not supported
            * 3: calling AE title not recognised
            * 7: called AE title not recognised

            If `result_source` is "UL service-provider (ACSE related function)"
            then allowed values are:

            * 1: no reason given
            * 2: protocol version not supported"

            If `result_source` is "UL service-provider (Presentation related
            function)" then allowed values are:

            * 1: temporary congestion
            * 2: local limit exceeded
        """
        # pylint: disable=attribute-defined-outside-init
        if value is None:
            pass
        elif value not in [1, 2, 3, 7]:
            LOGGER.error("A_ASSOCIATE.diagnostic set to an unknown value")
            raise ValueError("Unknown A_ASSOCIATE.diagnostic value")

        self._diagnostic = value

    @property
    def reason_str(self):
        """Return the rejection reason as str."""
        reasons = {
            1 : {
                1 : 'No reason given',
                2 : 'Application context name not supported',
                3 : 'Calling AE title not recognised',
                4 : 'Reserved',
                5 : 'Reserved',
                6 : 'Reserved',
                7 : 'Called AE title not recognised',
                8 : 'Reserved',
                9 : 'Reserved',
                10 : 'Reserved',
            },
            2 : {
                1 : 'No reason given',
                2 : 'Protocol version not supported'
            },
            3 : {
                0 : "Reserved",
                1 : "Temporary congestion",
                2 : "Local limit exceeded",
                3 : 'Reserved',
                4 : 'Reserved',
                5 : 'Reserved',
                6 : 'Reserved',
                7 : 'Reserved',
            }
        }
        return reasons[self.result_source][self.diagnostic]

    @property
    def calling_presentation_address(self):
        """Return the Calling Presentation Address parameter."""
        return self._calling_presentation_address

    @calling_presentation_address.setter
    def calling_presentation_address(self, value):
        """
        Set the A-ASSOCIATE Service primitive's Calling Presentation
        Address parameter

        Parameters
        ----------
        value : (str, int) tuple
            A tuple containing a valid TCP/IP address string and the port
            number as an int
        """
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, tuple):
            if len(value) == 2 and isinstance(value[0], str) \
                    and isinstance(value[1], int):
                self._calling_presentation_address = value
            else:
                LOGGER.error("A_ASSOCIATE.calling_presentation_address must "
                             "be (str, int) tuple")
                raise TypeError("A_ASSOCIATE.calling_presentation_address "
                                "must be (str, int) tuple")
        elif value is None:
            self._calling_presentation_address = value
        else:
            LOGGER.error("A_ASSOCIATE.calling_presentation_address must be "
                         "(str, int) tuple")
            raise TypeError("A_ASSOCIATE.calling_presentation_address must "
                            "be (str, int) tuple")

    @property
    def called_presentation_address(self):
        """Return the Called Presentation Address parameter."""
        return self._called_presentation_address

    @called_presentation_address.setter
    def called_presentation_address(self, value):
        """Set the Called Presentation Address parameter.

        Parameters
        ----------
        value : (str, int) tuple
            A tuple containing a valid TCP/IP address string and the port
            number as an int
        """
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, tuple):
            if len(value) == 2 and isinstance(value[0], str) \
                    and isinstance(value[1], int):
                self._called_presentation_address = value
            else:
                LOGGER.error("A_ASSOCIATE.called_presentation_address must "
                             "be (str, int) tuple")
                raise TypeError("A_ASSOCIATE.called_presentation_address "
                                "must be (str, int) tuple")
        elif value is None:
            self._called_presentation_address = value
        else:
            LOGGER.error("A_ASSOCIATE.called_presentation_address must be "
                         "(str, int) tuple")
            raise TypeError("A_ASSOCIATE.called_presentation_address must "
                            "be (str, int) tuple")

    @property
    def responding_presentation_address(self):
        """Get the Responding Presentation Address parameter."""
        return self.called_presentation_address

    @property
    def presentation_context_definition_list(self):
        """Get the Presentation Context Definition List."""
        return self._presentation_context_definition_list

    @presentation_context_definition_list.setter
    def presentation_context_definition_list(self, value_list):
        """
        Set the A-ASSOCIATE Service primitive's Presentation Context Definition
        List parameter

        Parameters
        ----------
        value_list : list of utils.PresentationContext
            The Presentation Contexts proposed by the Association Requestor
        """
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value_list, list):
            valid_items = []
            for item in value_list:
                if isinstance(item, PresentationContext):
                    valid_items.append(item)
                else:
                    LOGGER.warning(
                        "Attempted to set "
                        "A_ASSOCIATE.presentation_context_definition_list to "
                        "a list which includes an invalid items"
                    )

            self._presentation_context_definition_list = valid_items

        else:
            LOGGER.error("A_ASSOCIATE.presentation_context_definition_list "
                         "must be a list")
            raise TypeError("A_ASSOCIATE.presentation_context_definition_list "
                            "must be a list")

    @property
    def presentation_context_definition_results_list(self):
        """Get the Presentation Context Definition Results List."""
        return self._presentation_context_definition_results_list

    @presentation_context_definition_results_list.setter
    def presentation_context_definition_results_list(self, value_list):
        """Set the Presentation Context Definition Results List parameter.

        Parameters
        ----------
        value_list : list of utils.PresentationContext
            The results of the Presentation Contexts proposal by the
            Association Requestor
        """
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value_list, list):
            valid_items = []
            for item in value_list:
                if isinstance(item, PresentationContext):
                    valid_items.append(item)
                else:
                    LOGGER.warning("Attempted to set A_ASSOCIATE.presentation"
                                   "_context_definition_results_list to a "
                                   "list which includes one or more invalid "
                                   "items.")

            self._presentation_context_definition_results_list = valid_items

        else:
            LOGGER.error("A_ASSOCIATE.presentation_context_definition_"
                         "results_list must be a list")
            raise TypeError("A_ASSOCIATE.presentation_context_definition_"
                            "results_list must be a list")

    @property
    def presentation_requirements(self):
        """Get the Presentation Kernel."""
        return "Presentation Kernel"

    @property
    def session_requirements(self):
        """Get the Session Requirements."""
        return ""

    # Shortcut attributes for User Information items
    # Mandatory UI Items
    @property
    def maximum_length_received(self):
        """Get the Maximum Length Received."""
        for item in self.user_information:
            if isinstance(item, MaximumLengthNotification):
                return item.maximum_length_received

        return None

    @maximum_length_received.setter
    def maximum_length_received(self, value):
        """Set the Maximum Length Received.

        If the A_ASSOCIATE.user_information list contains a
        MaximumLengthNotification item then set its maximum_length_received
        value. If not then add a MaximumLengthNotification item and set its
        maximum_length_received value.

        Parameters
        ----------
        value : int
            The maximum length of each P-DATA in bytes
        """
        # Type and value checking for the maximum_length_received parameter is
        #   done by the MaximumLengthNotification class

        # Check for a MaximumLengthNotification item
        found_item = False

        for item in self.user_information:
            if isinstance(item, MaximumLengthNotification):
                found_item = True
                item.maximum_length_received = value

        # No MaximumLengthNotification item found
        if not found_item:
            max_length = MaximumLengthNotification()
            max_length.maximum_length_received = value
            self.user_information.append(max_length)

    @property
    def implementation_class_uid(self):
        """Return the Implementation Class UID."""
        for item in self.user_information:
            if isinstance(item, ImplementationClassUIDNotification):
                if item.implementation_class_uid is None:
                    LOGGER.error("Implementation Class UID has not been set")
                    raise ValueError("Implementation Class UID has not "
                                     "been set")

                return item.implementation_class_uid

        LOGGER.error("Implementation Class UID has not been set")
        raise ValueError("Implementation Class UID has not been set")

    @implementation_class_uid.setter
    def implementation_class_uid(self, value):
        """Set the Implementation Class UID.

        If the A_ASSOCIATE.user_information list contains an
        ImplementationClassUIDNotification item then set its
        implementation_class_uid value. If not then add a
        ImplementationClassUIDNotification item and set its
        implementation_class_uid value.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The value for the Implementation Class UID
        """
        # Type and value checking for the implementation_class_uid parameter is
        #   done by the ImplementationClassUIDNotification class

        # Check for a ImplementationClassUIDNotification item
        found_item = False
        for item in self.user_information:
            if isinstance(item, ImplementationClassUIDNotification):
                found_item = True
                item.implementation_class_uid = value

        # No ImplementationClassUIDNotification item found
        if not found_item:
            imp_uid = ImplementationClassUIDNotification()
            imp_uid.implementation_class_uid = value
            self.user_information.append(imp_uid)


class A_RELEASE(object):
    """An A-RELEASE primitive.

    +------------------+---------+------------+----------+--------------+
    | Parameter        | Request | Indication | Response | Confirmation |
    +------------------+---------+------------+----------+--------------+
    | reason           | UF      | UF(=)      | UF       | UF(=)        |
    +------------------+---------+------------+----------+--------------+
    | user info        |NU       | NU(=)      | NU       | NU(=)        |
    +------------------+---------+------------+----------+--------------+
    | result           |         |            | MF       | MF(=)        |
    +------------------+---------+------------+----------+--------------+

    | U   - User option
    | UF  - User option, fixed value
    | C   - Conditional (on user option)
    | M   - Mandatory
    | MF  - Mandatory, fixed value
    | NU  - Not used
    | (=) - shall have same value as request or response

    Attributes
    ----------
    reason : str
        Fixed value of ``'normal'``. Identifies the general level of urgency
        of the request.
    result : str or None
        Must be ``None`` for request and indication, ``'affirmative'`` for
        response and confirmation.

    References
    ----------
    * DICOM Standard, Part 8, :dcm:`Section 7.2<part08/sect_7.2.html>`
    """
    def __init__(self):
        self.result = None

    @property
    def reason(self):
        """Return the *Reason* parameter."""
        return "normal"

    @property
    def result(self):
        """Return the *Result* parameter."""
        return self._result

    @result.setter
    def result(self, value):
        """Set the Result parameter."""
        # pylint: disable=attribute-defined-outside-init
        if value is not None and value != "affirmative":
            LOGGER.error("A_RELEASE.result must be None or 'affirmative'")
            raise ValueError("A_RELEASE.result must be None or 'affirmative'")

        self._result = value


class A_ABORT(object):
    """
    An A-ABORT primitive.

    +------------------+---------+------------+
    | Parameter        | Request | Indication |
    +------------------+---------+------------+
    | abort source     |         | M          |
    +------------------+---------+------------+
    | user info        |NU       | NU(=)      |
    +------------------+---------+------------+

    | U   - User option
    | UF  - User option, fixed value
    | C   - Conditional (on user option)
    | M   - Mandatory
    | MF  - Mandatory, fixed value
    | NU  - Not used
    | (=) - shall have same value as request or response

    Attributes
    ----------
    abort_source : int
        Indicates the initiating source of the abort. Allowed values are:

        * ``0``: UL service-user
        * ``2``: UL service-provider

    References
    ----------

    * DICOM Standard, Part 8, :dcm:`Section 7.3<part08/sect_7.3.html>`
    """

    def __init__(self):
        self._abort_source = None

    @property
    def abort_source(self):
        """Return the *Abort Source*."""
        if self._abort_source is None:
            LOGGER.error("A_ABORT.abort_source value not set")
            raise ValueError("A_ABORT.abort_source value not set")

        return self._abort_source

    @abort_source.setter
    def abort_source(self, value):
        """Set the Abort Source."""
        # pylint: disable=attribute-defined-outside-init
        if value in [0, 1, 2, None]:
            self._abort_source = value
        else:
            msg = "Invalid A-ABORT 'source' value '{}'".format(value)
            LOGGER.error(msg)
            raise ValueError(msg)


class A_P_ABORT(object):
    """
    An A-P-ABORT primitive.

    +------------------+------------+
    | Parameter        | Indication |
    +------------------+------------+
    | abort source     | P          |
    +------------------+------------+

    | U   - User option
    | UF  - User option, fixed value
    | C   - Conditional (on user option)
    | M   - Mandatory
    | MF  - Mandatory, fixed value
    | NU  - Not used
    | P   - Provider initiated
    | (=) - shall have same value as request or response

    Attributes
    ----------
    provider_reason : int
        Indicates the reason for the abort. Allowed values are:

        * ``0``: reason not specified
        * ``1``: unrecognised PDU
        * ``2``: unexpected PDU
        * ``4``: unrecognised PDU parameter
        * ``5``: unexpected PDU parameter
        * ``6``: invalid PDU parameter value

    References
    ----------

    * DICOM Standard, Part 8, :dcm:`Section 7.4<part08/sect_7.4.html>`
    """
    def __init__(self):
        self._provider_reason = None

    @property
    def provider_reason(self):
        """Return the *Provider Reason*."""
        if self._provider_reason is None:
            LOGGER.error("A_ABORT.provider_reason parameter not set")
            raise ValueError("A_ABORT.provider_reason value not set")

        return self._provider_reason

    @provider_reason.setter
    def provider_reason(self, value):
        """Set the Provider Reason."""
        # pylint: disable=attribute-defined-outside-init
        if value in [0, 1, 2, 4, 5, 6, None]:
            self._provider_reason = value
        else:
            msg = (
                "Attempted to set A_P_ABORT.provider_reason to an invalid "
                "value"
            )
            LOGGER.error(msg)
            raise ValueError(msg)


class P_DATA(object):
    """
    A P-DATA primitive.

    +------------------------------+---------+------------+
    | Parameter                    | Request | Indication |
    +------------------------------+---------+------------+
    | presentation data value list | M       | M(=)       |
    +------------------------------+---------+------------+

    | U   - User option
    | UF  - User option, fixed value
    | C   - Conditional (on user option)
    | M   - Mandatory
    | MF  - Mandatory, fixed value
    | NU  - Not used
    | (=) - shall have same value as request or response

    Attributes
    ----------
    presentation_data_value_list : list of [int, bytes]
        Contains one or more Presentation Data Values (PDV), each consisting of
        a Presentation Context ID and User Data values. The User Data values
        are taken from the Abstract Syntax and encoded in the Transfer Syntax
        identified by the Presentation Context ID. Each item in the list is
        ``[Context ID, PDV Data]``

    References
    ----------

    * DICOM Standard, Part 8, :dcm:`Section 7.6<part08/sect_7.6.html>`
    """
    def __init__(self):
        self.presentation_data_value_list = []

    @property
    def presentation_data_value_list(self):
        """Return the *Presentation Data Value List*."""
        return self._presentation_data_value_list

    @presentation_data_value_list.setter
    def presentation_data_value_list(self, value_list):
        """Set the Presentation Data Value List."""
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value_list, list):
            for pdv in value_list:
                if isinstance(pdv, list):
                    if isinstance(pdv[0], int) and isinstance(pdv[1], bytes):
                        pass
                    else:
                        raise TypeError("P_DATA.presentation_data_value_list "
                                        "should be a list of [int, bytes]")
                else:
                    raise TypeError("P_DATA.presentation_data_value_list "
                                    "should be a list of [ID, PDV]")
        else:
            raise TypeError("P_DATA.presentation_data_value_list "
                            "should be a list of [int, bytes]")

        self._presentation_data_value_list = value_list

    def __str__(self):
        """String representation of the class."""
        s = 'P-DATA\n'
        for pdv in self.presentation_data_value_list:
            s += '  Context ID: {0!s}\n'.format(pdv[0])
            s += '  Value Length: {0!s} bytes\n'.format(len(pdv[1]))
            header_byte = pdv[1][0]

            # Python 2 compatibility
            if isinstance(header_byte, str):
                header_byte = ord(header_byte)

            s += "  Message Control Header Byte: {:08b}\n".format(header_byte)

            # xxxxxx01 and xxxxxx011
            if header_byte & 1:
                # xxxxxx11
                if header_byte & 2:
                    s += '    Command information, last fragment of the ' \
                         'DIMSE message\n'
                # xxxxxx01
                else:
                    s += '    Command information, not the last fragment of ' \
                         'the DIMSE message\n'
            # xxxxxx00, xxxxxxx10
            else:
                # xxxxxx10
                if header_byte & 2 != 0:
                    s += '    Dataset information, last fragment of the ' \
                         'DIMSE message\n'
                # xxxxxx00
                else:
                    s += '    Dataset information, not the last fragment of ' \
                         'the DIMSE message\n'

            # Remaining data
            #s += pretty_bytes(pdv[1][1:], '    ', max_size=512)

        return s


# User Information Negotiation primitives
class MaximumLengthNotification(ServiceParameter):
    """
    A representation of a Maximum Length Negotiation primitive.

    The maximum length notification allows communicating AEs to limit the size
    of the data for each P-DATA indication. This notification is required for
    all DICOM v3.0 conforming implementations.

    This User Information item is required during association negotiation and
    there must only be a single :class:`MaximumLengthNotification` item.

    Attributes
    ----------
    maximum_length_received : int
        The maximum length received value for the Maximum Length sub-item in
        bytes. A value of ``0`` indicates unlimited length (``31682`` bytes
        default).

    References
    ----------

    * DICOM Standard, Part 7,
      :dcm:`Annex D.3.3.1<part07/sect_D.3.3.html#sect_D.3.3.1>`
    * DICOM Standard, Part 8, :dcm:`Annex D.1<part08/chapter_D.html#sect_D.1>`
    """
    def __init__(self):
        self.maximum_length_received = DEFAULT_MAX_LENGTH

    def from_primitive(self):
        """Convert the primitive to a PDU item ready to be encoded.

        Returns
        -------
        item : pdu_items.MaximumLengthSubItem
        """
        item = MaximumLengthSubItem()
        item.from_primitive(self)

        return item

    @property
    def maximum_length_received(self):
        """Return the *Maximum Length Received*."""
        return self._maximum_length

    @maximum_length_received.setter
    def maximum_length_received(self, val):
        """User defined Maximum Length to be used during an Association.

        Parameters
        ----------
        val : int
            The maximum length of each P-DATA in bytes, must be equal to or
            greater than 0. A value of 0 indicates an unlimited maximum length.

        Raises
        ------
        ValueError
            If `maximum_length_received` is negative
        TypeError
            If `maximum_length_received` is not an int
        """
        # pylint: disable=attribute-defined-outside-init
        if isinstance(val, int):
            if val < 0:
                LOGGER.error('Maximum Length Received must be greater than 0')
                raise ValueError("Maximum Length Received must be greater "
                                 "than 0")
            else:
                self._maximum_length = val
        else:
            LOGGER.error("Maximum Length Received must be numerical")
            raise TypeError("Maximum Length Received must be numerical")

    def __str__(self):
        """String representation of the class."""
        s = "Maximum Length Negotiation\n"
        s += "  Maximum length received: {0:d} bytes\n".format(
            self.maximum_length_received)
        return s


# TODO: Combine ImplementationClass and ImplementationVersion
#   into ImplementationIdentificationNotification
class ImplementationClassUIDNotification(ServiceParameter):
    """A representation of a Implementation Class UID Notification primitive.

    The implementation identification notification allows implementations of
    communicating AEs to identify each other at association establishment time.
    It is intended to provider respective and non-ambiguous identification in
    the event of communication problems encountered between two nodes. This
    negotiation is required.

    Implementation identification relies on two pieces of information:

    - Implementation Class UID (required)
    - Implementation Version Name (optional)

    The Implementation Class UID is required during association negotiation and
    there must only be a single :class:`ImplementationClassUIDNotification`
    item.

    Attributes
    ----------
    implementation_class_uid : pydicom.uid.UID, bytes or str
        The UID to use.

    Examples
    --------

    >>> from pynetdicom.pdu_primitives import (
    ...     ImplementationClassUIDNotification
    ... )
    >>> item = ImplementationClassUIDNotification()
    >>> item.implementation_class_uid = '1.2.3.4'

    References
    ----------

    * DICOM Standard, Part 7, :dcm:`Annex D.3.3.2<part07/sect_D.3.3.2.html>`
    """
    def __init__(self):
        self.implementation_class_uid = None

    def from_primitive(self):
        """Convert the primitive to a PDU item ready to be encoded.

        Returns
        -------
        item : pdu_items.ImplementationClassUIDSubItem

        Raises
        ------
        ValueError
            If no UID is set
        """
        if self.implementation_class_uid is None:
            LOGGER.error("The Implementation Class UID must be set prior to "
                         "requesting Association")
            raise ValueError("The Implementation Class UID must be set "
                             "prior to requesting Association")

        item = ImplementationClassUIDSubItem()
        item.from_primitive(self)

        return item

    @property
    def implementation_class_uid(self):
        """Return the *Implementation Class UID*."""
        return self._implementation_class_uid

    @implementation_class_uid.setter
    def implementation_class_uid(self, value):
        """Sets the Implementation Class UID parameter.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The value for the Implementation Class UID
        """
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, UID):
            pass
        elif isinstance(value, str):
            value = UID(value)
        elif isinstance(value, bytes):
            value = UID(value.decode('ascii'))
        elif value is None:
            pass
        else:
            raise TypeError("Implementation Class UID must be a "
                            "pydicom.uid.UID, str or bytes")

        if value is not None and not validate_uid(value):
            msg = (
                "The Implementation Class UID Notification's 'Implementation "
                "Class UID' parameter value '{}' is not a valid UID"
                .format(value)
            )
            LOGGER.error(msg)
            raise ValueError(msg)

        if value and not value.is_valid:
            LOGGER.warning(
                "The Implementation Class UID '{}' is non-conformant"
                .format(value)
            )

        self._implementation_class_uid = value

    def __str__(self):
        """String representation of the class."""
        s = "Implementation Class UID\n"
        s += "  Implementation class UID: {0!s}\n" \
             .format(self.implementation_class_uid)
        return s


class ImplementationVersionNameNotification(ServiceParameter):
    """
    A representation of a Implementation Version Name Notification primitive.

    The implementation identification notification allows implementations of
    communicating AEs to identify each other at Association establishment time.
    It is intended to provider respective and non-ambiguous identification in
    the event of communication problems encountered between two nodes. This
    negotiation is required.

    Implementation identification relies on two pieces of information:

    - Implementation Class UID (required)
    - Implementation Version Name (optional)

    The Implementation Version Name is optional and there may only be a single
    :class:`ImplementationVersionNameNotification` item.

    Attributes
    ----------
    implementation_version_name : str or bytes
        The version name to use, maximum of 16 characters.

    Examples
    --------

    >>> from pynetdicom.pdu_primitives import (
    ...     ImplementationVersionNameNotification
    ... )
    >>> item = ImplementationVersionNameNotification()
    >>> item.implementation_version_name = b'SOME_NAME'

    References
    ----------

    * DICOM Standard, Part 7, :dcm:`Annex D.3.3.2<part07/sect_D.3.3.2.html>`
    """
    def __init__(self):
        self.implementation_version_name = None

    def from_primitive(self):
        """Convert the primitive to a PDU item ready to be encoded.

        Returns
        -------
        item : pdu_items.ImplementationVersionNameSubItem

        Raises
        ------
        ValueError
            If no name is set
        """
        if self.implementation_version_name is None:
            raise ValueError("Implementation Version Name must be set prior "
                             "to Association")

        item = ImplementationVersionNameSubItem()
        item.from_primitive(self)

        return item

    @property
    def implementation_version_name(self):
        """Return the *Implementation Version Name*."""
        return self._implementation_version_name

    @implementation_version_name.setter
    def implementation_version_name(self, value):
        """Sets the Implementation Version Name parameter.

        Parameters
        ----------
        value : str or bytes
            The value for the Implementation Version Name

        Raises
        ------
        TypeError
            If `value` is not a str or bytes
        ValueError
            If `value` is empty or longer than 16 characters
        """
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, str):
            value = codecs.encode(value, 'ascii')
        elif isinstance(value, bytes):
            pass
        elif value is None:
            pass
        else:
            LOGGER.error("Implementation Version Name must be a str or bytes")
            raise TypeError("Implementation Version Name must be a str "
                            "or bytes")

        if value is not None and not 0 < len(value) < 17:
            raise ValueError("Implementation Version Name must be "
                             "between 1 and 16 characters long")

        self._implementation_version_name = value

    def __str__(self):
        """String representation of the class."""
        s = "Implementation Version Name\n"
        s += "  Implementation version name: {0!s}\n".format(
            self.implementation_version_name)
        return s


class AsynchronousOperationsWindowNegotiation(ServiceParameter):
    """
    Representation of the Asynchronous Operations Window Negotiation primitive.

    Allows peer AEs to negotiate the maximum number of outstanding operation
    or sub-operation requests. This negotiation is optional.

    The Asynchronous Operations Window is optional and there may only be a
    single :class:`AsynchronousOperationsWindowNegotiation` item

    Identical for both A-ASSOCIATE-RQ and A-ASSOCIATE-AC.

    Attributes
    ----------
    maximum_number_operations_invoked : int
        The maximum number of asynchronous operations invoked by the AE. A
        value of ``0`` indicates unlimited operations (default ``1``)
    maximum_number_operations_performed : int
        The maximum number of asynchronous operations performed by the AE. A
        value of ``0`` indicates unlimited operations (default ``1``)

    Examples
    --------

    >>> from pynetdicom.pdu_primitives import (
    ...     AsynchronousOperationsWindowNegotiation
    ... )
    >>> item = AsynchronousOperationsWindowNegotiation()
    >>> item.maximum_number_operations_invoked = 2
    >>> item.maximum_number_operations_performed = 1

    References
    ----------

    * DICOM Standard, Part 7, :dcm:`Annex D.3.3.3<part07/sect_D.3.3.3.html>`
    """

    def __init__(self):
        self.maximum_number_operations_invoked = 1
        self.maximum_number_operations_performed = 1

    def from_primitive(self):
        """Convert the primitive to a PDU item ready to be encoded.

        Returns
        -------
        item : pdu_items.AsynchronousOperationsWindowSubItem
        """
        item = AsynchronousOperationsWindowSubItem()
        item.from_primitive(self)

        return item

    @property
    def maximum_number_operations_invoked(self):
        """Return the *Maximum Number Operations Invoked*."""
        return self._maximum_number_operations_invoked

    @maximum_number_operations_invoked.setter
    def maximum_number_operations_invoked(self, value):
        """Sets the Maximum Number Operations Invoked parameter.

        Parameters
        ----------
        value : int
            The maximum number of operations invoked

        Raises
        ------
        TypeError
            If `value` is not an int
        ValueError
            If `value` is less than 0
        """
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, int):
            pass
        else:
            LOGGER.error("Maximum Number Operations Invoked must be an int")
            raise TypeError("Maximum Number Operations Invoked must be an int")

        if value < 0:
            raise ValueError("Maximum Number Operations Invoked must be "
                             "greater than 0")

        self._maximum_number_operations_invoked = value

    @property
    def maximum_number_operations_performed(self):
        """Return the *Maximum Number Operations Performed*."""
        return self._maximum_number_operations_performed

    @maximum_number_operations_performed.setter
    def maximum_number_operations_performed(self, value):
        """
        Sets the Maximum Number Operations Performed parameter

        Parameters
        ----------
        value : int
            The maximum number of operations performed

        Raises
        ------
        TypeError
            If `value` is not an int
        ValueError
            If `value` is less than 0
        """
        # pylint: disable=attribute-defined-outside-init
        if not isinstance(value, int):
            LOGGER.error("Maximum Number Operations Performed must be an int")
            raise TypeError("Maximum Number Operations Performed must be "
                            "an int")

        if value < 0:
            raise ValueError("Maximum Number Operations Performed must be "
                             "greater than 0")

        self._maximum_number_operations_performed = value

    def __str__(self):
        """String representation of the class."""
        s = "Asynchronous Operations Window\n"
        s += "  Maximum number operations invoked: {0:d}\n".format(
            self.maximum_number_operations_invoked)
        s += "  Maximum number operations performed: {0:d}\n".format(
            self.maximum_number_operations_performed)
        return s


class SCP_SCU_RoleSelectionNegotiation(ServiceParameter):
    """
    A representation of the SCP/SCU Role Selection Negotiation primitive.

    Allows peer AEs to negotiate the roles in which they will serve for each
    SOP Class or Meta SOP Class supported on the association. This negotiation
    is optional.

    The association *Requestor* may use one SCP/SCU Role Selection item for
    each SOP Class as identified by its corresponding Abstract Syntax Name and
    shall be one of three role values:

    - *Requestor* is SCU only
    - *Requestor* is SCP only
    - *Requestor* is both SCU/SCP

    If the SCP/SCU Role Selection item is absent the default role for a
    *Requestor* is SCU and for an *Acceptor* is SCP.

    Identical for both A-ASSOCIATE-RQ and A-ASSOCIATE-AC.

    Attributes
    ----------
    sop_class_uid : pydicom.uid.UID, bytes or str
        The UID of the corresponding Abstract Syntax
    scu_role : bool
        ``False`` for non-support of the SCU role, ``True`` for support.
    scp_role : bool
        ``False`` for non-support of the SCP role, ``True`` for support.

    Examples
    --------

    >>> from pynetdicom.pdu_primitives import SCP_SCU_RoleSelectionNegotiation
    >>> item = SCP_SCU_RoleSelectionNegotiation()
    >>> item.sop_class_uid = '1.2.840.10008.5.1.4.1.1.2'
    >>> item.scu_role = True
    >>> item.scp_role = False

    References
    ----------

    * DICOM Standard, Part 7, :dcm:`Annex D.3.3.4<part07/sect_D.3.3.4.html>`
    """
    def __init__(self):
        self.sop_class_uid = None
        self.scu_role = None
        self.scp_role = None

    def from_primitive(self):
        """Convert the primitive to a PDU item ready to be encoded

        Returns
        -------
        item : pdu_items.SCP_SCU_RoleSelectionSubItem

        Raises
        ------
        ValueError
            If no SOP Class UID, SCU Role or SCP Role is set
        ValueError
            If SCU Role and SCP Role are both False
        """
        if self.sop_class_uid is None:
            LOGGER.error("'sop_class_uid' must be set prior to Association")
            raise ValueError(
                "'sop_class_uid' must be set prior to Association"
            )

        # To get to this point self.sop_class_uid must be set
        if not self.scu_role and not self.scp_role:
            LOGGER.error("SCU and SCP Roles cannot both be unsupported "
                         "for %s", self.sop_class_uid)
            raise ValueError("SCU and SCP Roles cannot both be unsupported "
                             "for {}".format(self.sop_class_uid))

        item = SCP_SCU_RoleSelectionSubItem()
        item.from_primitive(self)

        return item

    @property
    def scp_role(self):
        """Return the *SCP Role*."""
        return self._scp_role

    @scp_role.setter
    def scp_role(self, value):
        """Sets the SCP Role parameter.

        Parameters
        ----------
        value : bool
            True if supported, False otherwise (default)

        Raises
        ------
        TypeError
            If `value` is not a bool
        """
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, bool):
            pass
        elif value is None:
            pass
        else:
            LOGGER.error("SCP Role must be boolean")
            raise TypeError("SCP Role must be boolean")

        self._scp_role = value

    @property
    def scu_role(self):
        """Return the *SCU Role*."""
        return self._scu_role

    @scu_role.setter
    def scu_role(self, value):
        """Sets the SCU Role parameter.

        Parameters
        ----------
        value : bool
            True if supported, False otherwise

        Raises
        ------
        TypeError
            If `value` is not a bool
        """
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, bool):
            pass
        elif value is None:
            pass
        else:
            LOGGER.error("SCU Role must be boolean")
            raise TypeError("SCU Role must be boolean")

        self._scu_role = value

    @property
    def sop_class_uid(self):
        """Return the *SOP Class UID*."""
        return self._sop_class_uid

    @sop_class_uid.setter
    def sop_class_uid(self, value):
        """Sets the SOP Class UID parameter.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The corresponding Abstract Syntax UID

        Raises
        ------
        TypeError
            If `value` is not a pydicom.uid.UID, bytes or str
        """
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, UID):
            pass
        elif isinstance(value, str):
            value = UID(value)
        elif isinstance(value, bytes):
            value = UID(value.decode('ascii'))
        elif value is None:
            pass
        else:
            LOGGER.error("SOP Class UID must be a pydicom.uid.UID, str "
                         "or bytes")
            raise TypeError("SOP Class UID must be a pydicom.uid.UID, str "
                            "or bytes")

        if value is not None and not validate_uid(value):
            LOGGER.error("SOP Class UID is an invalid UID")
            raise ValueError("SOP Class UID is an invalid UID")

        if value and not value.is_valid:
            LOGGER.warning(
                "The SOP Class UID '{}' is non-conformant"
                .format(value)
            )

        self._sop_class_uid = value


class SOPClassExtendedNegotiation(ServiceParameter):
    r"""
    A representation of the SOP Class Extended Negotiation primitive.

    Allows peer AEs to exchange application information defined by specific
    Service Class specifications. Each Service Class is required to document
    the application information it supports and how this information is
    negotiated between SCUs and SCPs.

    The SOP Class Extended Negotiation is optional and there may only be a
    single :class:`SOPClassExtendedNegotiation` item for each available SOP
    Class UID.

    Identical for both A-ASSOCIATE-RQ and A-ASSOCIATE-AC

    Attributes
    ----------
    sop_class_uid : pydicom.uid.UID, bytes or str
        The UID of the SOP Class
    service_class_application_information : bytes
        The Service Class Application Information as per the Service Class
        Specifications in :dcm:`Part 4<part04/PS3.4.html>` of the DICOM
        Standard.

    Examples
    --------

    .. code-block:: python

       >>> from pynetdicom.pdu_primitives import SOPClassExtendedNegotiation
       >>> item = SOPClassExtendedNegotiation()
       >>> item.sop_class_uid = '1.2.840.10008.5.1.4.1.2.1.3'
       >>> item.service_class_application_information = b'\x01'

    References
    ----------

    * DICOM Standard, Part 7, :dcm:`Annex D.3.3.5<part07/sect_D.3.3.5.html>`
    """
    def __init__(self):
        self.sop_class_uid = None
        self.service_class_application_information = None

    def from_primitive(self):
        """Convert the primitive to a PDU item ready to be encoded.

        Returns
        -------
        item : pdu_items.SOPClassExtendedNegotiationSubItem

        Raises
        ------
        ValueError
            If `sop_class_uid` or `service_class_application_information` are
            not set
        """
        if self.sop_class_uid is None \
                or self.service_class_application_information is None:
            LOGGER.error("SOP Class UID and Service Class Application "
                         "Information must be set prior to Association "
                         "negotiation")
            raise ValueError("SOP Class UID and Service Class Application "
                             "Information must be set prior to Association "
                             "negotiation")

        item = SOPClassExtendedNegotiationSubItem()
        item.from_primitive(self)

        return item

    @property
    def service_class_application_information(self):
        """Return the *Service Class Application Information*."""
        return self._service_class_application_information

    @service_class_application_information.setter
    def service_class_application_information(self, value):
        """Sets the Service Class Application Information parameter.

        Parameters
        ----------
        value : bytes
            The Service Class Application Information as per the Service Class
            Specifications (see PS3.4)

        Raises
        ------
        TypeError
            If `value` is not a bytes object
        """
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, bytes):
            pass
        elif value is None:
            pass
        else:
            LOGGER.error("Service Class Application Information should be a "
                         "bytes object")
            raise TypeError("Service Class Application Information should "
                            "be a bytes object")

        self._service_class_application_information = value

    @property
    def sop_class_uid(self):
        """Return the *SOP Class UID*."""
        return self._sop_class_uid

    @sop_class_uid.setter
    def sop_class_uid(self, value):
        """Sets the SOP Class UID parameter.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The corresponding Abstract Syntax UID

        Raises
        ------
        TypeError
            If `value` is not a pydicom.uid.UID, bytes or str
        """
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, UID):
            pass
        elif isinstance(value, str):
            value = UID(value)
        elif isinstance(value, bytes):
            value = UID(value.decode('ascii'))
        elif value is None:
            pass
        else:
            LOGGER.error("SOP Class UID must be a pydicom.uid.UID, str "
                         "or bytes")
            raise TypeError("SOP Class UID must be a pydicom.uid.UID, str "
                            "or bytes")

        if value is not None and not validate_uid(value):
            LOGGER.error("SOP Class UID is an invalid UID")
            raise ValueError("SOP Class UID is an invalid UID")

        if value and not value.is_valid:
            LOGGER.warning(
                "The SOP Class UID '{}' is non-conformant"
                .format(value)
            )

        self._sop_class_uid = value


class SOPClassCommonExtendedNegotiation(ServiceParameter):
    """
    A representation of the SOP Class Common Extended Negotiation primitive.

    Allows peer AEs to exchange generic application information.

    The SOP Class Common Extended Negotiation is optional and there may only be
    a single :class:`SOPClassCommonExtendedNegotiation` item for each available
    SOP Class UID.

    Identical for both A-ASSOCIATE-RQ and A-ASSOCIATE-AC

    Attributes
    ----------
    sop_class_uid : pydicom.uid.UID, bytes or str
        The UID of the SOP Class
    service_class_uid : pydicom.uid.UID, bytes or str
        The UID of the corresponding Service Class
    related_general_sop_class_identification : list of UID str
        Related General SOP Class UIDs (optional)

    Examples
    --------

    >>> from pynetdicom.pdu_primitives import SOPClassCommonExtendedNegotiation
    >>> item = SOPClassCommonExtendedNegotiation()
    >>> item.sop_class_uid = '1.2.840.10008.5.1.4.1.1.88.40'
    >>> item.service_class_uid = '1.2.840.10008.4.2'
    >>> item.related_general_sop_class_identification = [
    ...     '1.2.840.10008.5.1.4.1.1.88.22'
    ... ]

    References
    ----------

    * DICOM Standard, Part 7, :dcm:`Annex D.3.3.6<part07/sect_D.3.3.6.html>`
    """
    def __init__(self):
        self.sop_class_uid = None
        self.service_class_uid = None
        self.related_general_sop_class_identification = []

    def from_primitive(self):
        """Convert the primitive to a PDU item ready to be encoded.

        Returns
        -------
        item : pdu_items.SOPClassCommonExtendedNegotiationSubItem

        Raises
        ------
        ValueError
            If `sop_class_uid` or `service_class_uid` are not set
        """
        if self.sop_class_uid is None or self.service_class_uid is None:
            LOGGER.error("SOP Class UID and Service Class UID must be set "
                         "prior to Association negotiation")
            raise ValueError("SOP Class UID and Service Class UID must be "
                             "set prior to Association negotiation")

        item = SOPClassCommonExtendedNegotiationSubItem()
        item.from_primitive(self)

        return item

    @property
    def related_general_sop_class_identification(self):
        """Return the *Related General SOP Class Identification*."""
        return self._related_general_sop_class_identification

    @related_general_sop_class_identification.setter
    def related_general_sop_class_identification(self, uid_list):
        """Sets the Service Class Application Information parameter.

        Parameters
        ----------
        uid_list : list of (pydicom.uid.UID, bytes or str)
            A list containing UIDs to be used in the Related General SOP Class
            Identification parameter

        Raises
        ------
        TypeError
            If `uid_list` is not a list
        ValueError
            If `uid_list` contains items that aren't UIDs
        """
        # pylint: disable=attribute-defined-outside-init
        if isinstance(uid_list, list):
            # Test that all the items in the list are UID compatible and
            #   convert them to pydicom.uid.UID if required
            valid_uid_list = []

            for uid in uid_list:
                if isinstance(uid, UID):
                    pass
                elif isinstance(uid, str):
                    uid = UID(uid)
                elif isinstance(uid, bytes):
                    uid = UID(uid.decode('ascii'))
                else:
                    msg = (
                        "Related General SOP Class Identification "
                        "must be a list of pydicom.uid.UID, str or bytes"
                    )
                    LOGGER.error(msg)
                    raise TypeError(msg)

                if uid is not None and not validate_uid(uid):
                    msg = (
                        "Related General SOP Class "
                        "Identification contains an invalid UID"
                    )
                    LOGGER.error(msg)
                    raise ValueError(msg)

                if uid and not uid.is_valid:
                    LOGGER.warning(
                        "The Related General SOP Class UID '{}' is "
                        "non-conformant".format(uid)
                    )

                valid_uid_list.append(uid)

            self._related_general_sop_class_identification = valid_uid_list
        else:
            msg = (
                "Related General SOP Class Identification "
                "must be a list of pydicom.uid.UID, str or bytes"
            )
            LOGGER.error(msg)
            raise TypeError(msg)

    @property
    def service_class_uid(self):
        """Return the *Service Class UID*."""
        return self._service_class_uid

    @service_class_uid.setter
    def service_class_uid(self, value):
        """Sets the Service Class UID parameter.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The corresponding Service Class UID

        Raises
        ------
        TypeError
            If `value` is not a pydicom.uid.UID, bytes or str
        """
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, UID):
            pass
        elif isinstance(value, str):
            value = UID(value)
        elif isinstance(value, bytes):
            value = UID(value.decode('ascii'))
        elif value is None:
            pass
        else:
            msg = "Service Class UID must be a pydicom.uid.UID, str or bytes"
            LOGGER.error(msg)
            raise TypeError(msg)

        if value is not None and not validate_uid(value):
            LOGGER.error("Service Class UID is an invalid UID")
            raise ValueError("Service Class UID is an invalid UID")

        if value and not value.is_valid:
            LOGGER.warning(
                "The Service Class UID '{}' is non-conformant"
                .format(value)
            )

        self._service_class_uid = value

    @property
    def sop_class_uid(self):
        """Return the *SOP Class UID*."""
        return self._sop_class_uid

    @sop_class_uid.setter
    def sop_class_uid(self, value):
        """Sets the SOP Class UID parameter.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The SOP Class UID

        Raises
        ------
        TypeError
            If `value` is not a pydicom.uid.UID, bytes or str
        """
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, UID):
            pass
        elif isinstance(value, str):
            value = UID(value)
        elif isinstance(value, bytes):
            value = UID(value.decode('ascii'))
        elif value is None:
            pass
        else:
            msg = "SOP Class UID must be a pydicom.uid.UID, str or bytes"
            LOGGER.error(msg)
            raise TypeError(msg)

        if value is not None and not validate_uid(value):
            LOGGER.error("SOP Class UID is an invalid UID")
            raise ValueError("SOP Class UID is an invalid UID")

        if value and not value.is_valid:
            LOGGER.warning(
                "The SOP Class UID '{}' is non-conformant"
                .format(value)
            )

        self._sop_class_uid = value


class UserIdentityNegotiation(ServiceParameter):
    """Representation of the User Identity Negotiation primitive.

    Allows peer AEs to exchange generic application information.

    The SOP Class Common Extended Negotiation is optional and there may only be
    a single :class:`UserIdentityNegotiation` item.

    In general, a User Identity Negotiation request that is accepted will
    result in association establishment and possibly a server response if
    requested and supported by the peer. If a server response is requested but
    not received then the *Requestor* must decide how to proceed.
    An association rejected due to an authorisation failure will be indicated
    using Rejection Permanent with a Source of "DICOM UL service provided (ACSE
    related function)".

    How the *Acceptor* handles authentication is to be implemented by the
    end-user and is outside the scope of the DICOM standard.

    A-ASSOCIATE-RQ

    | `user_identity_type`
    | `positive_response_requested`
    | `primary_field`
    | `secondary_field`

    A-ASSOCIATE-AC
    The `server_response` parameter is required when a response to the User
    Identity Negotiation request is to be issued (although this depends on
    whether or not this is supported by the *Acceptor*).

    Attributes
    ----------
    user_identity_type : int or None
        A-ASSOCIATE-RQ only. One of the following values:

        * ``1`` - Username as string in UTF-8
        * ``2`` - Username as string in UTF-8 and passcode
        * ``3`` - Kerberos Service ticket
        * ``4`` - SAML Assertion
        * ``5`` - JSON Web Token
    positive_response_requested : bool
        A-ASSOCIATE-RQ only. ``True`` when requesting a response, ``False``
        otherwise (default is ``False``)
    primary_field : bytes or None
        A-ASSOCIATE-RQ only. Contains either the username, Kerberos Service
        ticket or SAML assertion depending on `user_identity_type`.
    secondary_field : bytes or None
        A-ASSOCIATE-RQ only. Only required if the `user_identity_type` is
        ``2``, when it should contain the passcode as :class:`bytes`, ``None``
        otherwise.
    server_response : bytes or None
        A-ASSOCIATE-AC only. Shall contain the Kerberos Service ticket or SAML
        response if the `user_identity_type` is ``3`` or ``4``. Shall
        be ``None`` if `user_identity_type` was ``1`` or ``2``.

    Examples
    --------

    >>> from pynetdicom.pdu_primitives import UserIdentityNegotiation
    >>> item = UserIdentityNegotiation()
    >>> item.user_identity_type = 2
    >>> item.positive_response_requested = True
    >>> item.primary_field = b'username'
    >>> item.secondary_field = b'password'

    References
    ----------

    * DICOM Standard, Part 7, :dcm:`Annex D.3.3.7<part07/sect_D.3.3.7.html>`
    """

    def __init__(self):
        self.user_identity_type = None
        self.positive_response_requested = False
        self.primary_field = None
        self.secondary_field = b''
        self.server_response = None

    def from_primitive(self):
        """Convert the primitive to a PDU item ready to be encoded.

        Returns
        -------
        item : pdu_items.UserIdentitySubItemRQ or
            pdu_items.UserIdentitySubItemAC

        Raises
        ------
        ValueError
            If server_response is None and user_identity_type or primary_field
            are None
        ValueError
            If server_response is None and user_identity_type is 2 and
            secondary_field is None
        """
        # Determine if this primitive is an -RQ or -AC
        if self.server_response is None:
            # Then an -RQ
            if self.user_identity_type is None or self.primary_field is None:
                msg = (
                    "User Identity Type and Primary Field must be "
                    "set prior to Association negotiation"
                )
                LOGGER.error(msg)
                raise ValueError(msg)

            if self.user_identity_type == 2 and self.secondary_field == b'':
                msg = "Secondary Field must be set when User Identity is 2"
                LOGGER.error(msg)
                raise ValueError(msg)

            item = UserIdentitySubItemRQ()

        else:
            # Then an -AC
            item = UserIdentitySubItemAC()

        item.from_primitive(self)

        return item

    @property
    def positive_response_requested(self):
        """Return *Positive Response Requested*."""
        return self._positive_response_requested

    @positive_response_requested.setter
    def positive_response_requested(self, value):
        """Sets the Positive Response Requested parameter.

        Parameters
        ----------
        value : bool
            True if response requested, False otherwise

        Raises
        ------
        TypeError
            If `value` is not a bool
        """
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, bool):
            pass
        else:
            LOGGER.error("Positive Response Requested must be boolean")
            raise TypeError("Positive Response Requested must be boolean")

        self._positive_response_requested = value

    @property
    def primary_field(self):
        """Return *Primary Field*."""
        return self._primary_field

    @primary_field.setter
    def primary_field(self, value):
        """Sets the Primary Field parameter.

        Parameters
        ----------
        value : bytes or None
            The username or Kerberos Service ticket as a bytes object

        Raises
        ------
        TypeError
            If `value` is not bytes or None
        """
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, bytes):
            pass
        elif value is None:
            pass
        else:
            LOGGER.error("Primary Field must be bytes if requesting "
                         "Association, None otherwise")
            raise TypeError("Primary Field must be bytes if requesting "
                            "Association, None otherwise")

        self._primary_field = value

    @property
    def secondary_field(self):
        """Return the *Secondary Field*."""
        return self._secondary_field

    @secondary_field.setter
    def secondary_field(self, value):
        """Sets the Secondary Field parameter.

        Only used when User Identity Type is equal to 2.

        Parameters
        ----------
        value : bytes or None
            The passcode as a bytes object

        Raises
        ------
        TypeError
            If `value` is not bytes or None
        """
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, bytes):
            pass
        elif value is None:
            pass
        else:
            LOGGER.error("Secondary Field must be bytes if requesting "
                         "Association with User Identity Type equal to 2, "
                         "None otherwise")
            raise TypeError("Secondary Field must be bytes if requesting "
                            "Association with User Identity Type equal to 2, "
                            "None otherwise")

        self._secondary_field = value

    @property
    def server_response(self):
        """Return the *Server Response*."""
        return self._server_response

    @server_response.setter
    def server_response(self, value):
        """Sets the Server Response parameter.

        Parameters
        ----------
        value : bytes or None
            The server response as a bytes object

        Raises
        ------
        TypeError
            If `value` is not bytes or None
        """
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, bytes):
            pass
        elif value is None:
            pass
        else:
            LOGGER.error("Server Response must be bytes or None")
            raise TypeError("Server Response must be bytes or None")

        self._server_response = value

    def __str__(self):
        """String representation of the class."""
        s = 'User Identity Parameters\n'
        if self.server_response is None:
            s += '  User identity type: {0:d}\n'.format(
                self.user_identity_type)
            s += '  Positive response requested: {0!r}\n' \
                 .format(self.positive_response_requested)
            s += '  Primary field: {0!s}\n'.format(self.primary_field)
            s += '  Secondary field: {0!s}\n'.format(self.secondary_field)
        else:
            s += '  Server response: {0!s}\n'.format(self.server_response)

        return s

    @property
    def user_identity_type(self):
        """Return the *User Identity Type*."""
        return self._user_identity_type

    @user_identity_type.setter
    def user_identity_type(self, value):
        """Sets the User Identity Type parameter.

        Parameters
        ----------
        value : int
            One of the following:

            * 1 - Username as string in UTF-8
            * 2 - Username as string in UTF-8 and passcode
            * 3 - Kerberos Service ticket
            * 4 - SAML Assertion
            * 5 - JSON Web Token

        Raises
        ------
        TypeError
            If `value` is not an int or None
        ValueError
            If `value` is an int and is not 1, 2, 3 or 4
        """
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, int):
            if value not in [1, 2, 3, 4, 5]:
                LOGGER.error("User Identity Type must be 1, 2, 3, 4 or 5 if "
                             "requesting Association, None otherwise")
                raise ValueError("User Identity Type must be 1, 2, 3, 4 or 5 "
                                 "if requesting Association, None otherwise")
        elif value is None:
            pass
        else:
            LOGGER.error("User Identity Type must be an int or None")
            raise TypeError("User Identity Type must be an int or None")

        self._user_identity_type = value
