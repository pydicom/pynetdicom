"""
Implementation of the service parameter primitives.
"""

import logging
from typing import Any, cast, Type, TypeAlias, TYPE_CHECKING

from pydicom.uid import UID

from pynetdicom._globals import OptionalUIDType
from pynetdicom.pdu_items import (
    MaximumLengthSubItem,
    ImplementationClassUIDSubItem,
    ImplementationVersionNameSubItem,
    AsynchronousOperationsWindowSubItem,
    SCP_SCU_RoleSelectionSubItem,
    SOPClassExtendedNegotiationSubItem,
    SOPClassCommonExtendedNegotiationSubItem,
    UserIdentitySubItemRQ,
    UserIdentitySubItemAC,
)
from pynetdicom.presentation import PresentationContext
from pynetdicom.utils import validate_uid, decode_bytes, set_ae, set_uid
from pynetdicom._globals import DEFAULT_MAX_LENGTH

if TYPE_CHECKING:  # pragma: no cover
    from pynetdicom.transport import AddressInformation


LOGGER = logging.getLogger(__name__)

_PDUPrimitiveType: TypeAlias = "A_ASSOCIATE | A_RELEASE | A_ABORT | A_P_ABORT | P_DATA"
_UserInformationPrimitiveType = list[
    "MaximumLengthNotification | ImplementationClassUIDNotification | "
    "ImplementationVersionNameNotification | AsynchronousOperationsWindowNegotiation | "
    "SCP_SCU_RoleSelectionNegotiation | SOPClassExtendedNegotiation | "
    "UserIdentityNegotiation | SOPClassCommonExtendedNegotiation"
]
_UI: TypeAlias = (
    "MaximumLengthNotification | ImplementationClassUIDNotification | "
    "ImplementationVersionNameNotification | AsynchronousOperationsWindowNegotiation | "
    "SCP_SCU_RoleSelectionNegotiation | SOPClassExtendedNegotiation | "
    "SOPClassCommonExtendedNegotiation | UserIdentityNegotiation"
)
_UITypes = (
    Type["MaximumLengthNotification"]
    | Type["ImplementationClassUIDNotification"]
    | Type["ImplementationVersionNameNotification"]
    | Type["AsynchronousOperationsWindowNegotiation"]
    | Type["SCP_SCU_RoleSelectionNegotiation"]
    | Type["SOPClassExtendedNegotiation"]
    | Type["SOPClassCommonExtendedNegotiation"]
    | Type["UserIdentityNegotiation"]
)


# TODO: Rename to UserInformation
class ServiceParameter:
    """Base class for Service Parameters"""

    def __eq__(self, other: Any) -> bool:
        """Equality of two ServiceParameters"""
        if isinstance(other, self.__class__):
            return other.__dict__ == self.__dict__

        return False

    def __ne__(self, other: Any) -> bool:
        """Inequality of two ServiceParameters"""
        return not self == other


# Association Service primitives
class A_ASSOCIATE:
    """An A-ASSOCIATE primitive.

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

    References
    ----------

    * DICOM Standard, Part 8,
      :dcm:`Section 7.1.1<part08/chapter_7.html#sect_7.1.1>`
    """

    # pylint: disable=too-many-instance-attributes

    def __init__(self) -> None:
        self._application_context_name: UID | None = None
        self._calling_ae_title: str = "DEFAULT"
        self._called_ae_title: str = "DEFAULT"
        self._user_information: _UserInformationPrimitiveType = []
        self._result: int | None = None
        self._result_source: int | None = None
        self._diagnostic: int | None = None
        self._calling_presentation_address: "AddressInformation | None" = None
        self._called_presentation_address: "AddressInformation | None" = None
        self._presentation_context_definition_list: list[PresentationContext] = []
        self._presentation_context_definition_results_list: list[
            PresentationContext
        ] = []

    @property
    def application_context_name(self) -> UID | None:
        """Get or set the *Application Context Name* parameter.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The application context name proposed by the *Requestor*.
            *Acceptor* returns either the same or a different name. Returned
            name specifies the application context used for the association.
            See the DICOM Standard, Part 8, :dcm:`Annex A
            <part08/chapter_A.html>`. The application context name shall
            be a valid UID or UID string and for version 3 of the DICOM
            Standard should be ``'1.2.840.10008.3.1.1.1'``

        Returns
        -------
        pydicom.uid.UID
        """
        return self._application_context_name

    @application_context_name.setter
    def application_context_name(self, value: OptionalUIDType) -> None:
        """Set the Application Context Name parameter."""
        self._application_context_name = set_uid(value, "Application Context Name")

    @property
    def called_ae_title(self) -> str:
        """Get or set the *Called AE Title* parameter.

        Parameters
        ----------
        value : str or bytes
            The Called AE Title as a string or bytes object. Cannot be an empty
            string and will be truncated to 16 characters long

        Returns
        -------
        bytes
        """
        return self._called_ae_title

    @called_ae_title.setter
    def called_ae_title(self, value: str) -> None:
        """Set the Called AE Title parameter."""
        self._called_ae_title = cast(
            str, set_ae(value, "Called AE Title", False, False)
        )

    @property
    def called_presentation_address(self) -> "AddressInformation | None":
        """Get or set the *Called Presentation Address* parameter.

        .. versionchanged:: 3.0

            Changed to take and return an
            :class:`~pynetdicom.transport.AddressInformation` instance.

        Parameters
        ----------
        value : pynetdicom.transport.AddressInformation | None
            IPv4 or IPv6 connection information.
        """
        return self._called_presentation_address

    @called_presentation_address.setter
    def called_presentation_address(self, value: "AddressInformation | None") -> None:
        """Set the Called Presentation Address parameter."""
        # pylint: disable=attribute-defined-outside-init
        from pynetdicom.transport import AddressInformation

        if value is None or isinstance(value, AddressInformation):
            self._called_presentation_address = value
            return

        msg = (
            "'A_ASSOCIATE.called_presentation_address' must be an AddressInformation "
            "instance or None"
        )
        LOGGER.error(msg)
        raise TypeError(msg)

    @property
    def calling_ae_title(self) -> str:
        """Get or set the *Calling AE Title* parameter.

        Parameters
        ----------
        value : str or bytes
            The Calling AE Title as a string or bytes object. Cannot be an
            empty string and will be truncated to 16 characters long.

        Returns
        -------
        bytes
        """
        return self._calling_ae_title

    @calling_ae_title.setter
    def calling_ae_title(self, value: str) -> None:
        """Set the Calling AE Title parameter."""
        self._calling_ae_title = cast(
            str, set_ae(value, "Calling AE Title", False, False)
        )

    @property
    def calling_presentation_address(self) -> "AddressInformation | None":
        """Get or set the *Calling Presentation Address* parameter.

        .. versionchanged:: 3.0

            Changed to take and return an
            :class:`~pynetdicom.transport.AddressInformation` instance.

        Parameters
        ----------
        value : pynetdicom.transport.AddressInformation | None
            IPv4 or IPv6 connection information.
        """
        return self._calling_presentation_address

    @calling_presentation_address.setter
    def calling_presentation_address(self, value: "AddressInformation | None") -> None:
        """Set the A-ASSOCIATE Service primitive's Calling Presentation
        Address parameter.
        """
        from pynetdicom.transport import AddressInformation

        # pylint: disable=attribute-defined-outside-init
        if value is None or isinstance(value, AddressInformation):
            self._calling_presentation_address = value
            return

        msg = (
            "'A_ASSOCIATE.calling_presentation_address' must be an AddressInformation "
            f"instance or None, not {type(value).__name__}"
        )
        LOGGER.error(msg)
        raise TypeError(msg)

    @property
    def diagnostic(self) -> int | None:
        """Get or set the *Diagnostic* parameter.

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
        return self._diagnostic

    @diagnostic.setter
    def diagnostic(self, value: int | None) -> None:
        """
        Set the A-ASSOCIATE Service primitive's Diagnostic parameter."""
        # pylint: disable=attribute-defined-outside-init
        if value is None:
            pass
        elif value not in [1, 2, 3, 7]:
            LOGGER.error("A_ASSOCIATE.diagnostic set to an unknown value")
            raise ValueError("Unknown A_ASSOCIATE.diagnostic value")

        self._diagnostic = value

    @property
    def implementation_class_uid(self) -> UID | None:
        """Get or set the *Implementation Class UID* as
        :class:`~pydicom.uid.UID`.

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
        for item in self.user_information:
            if isinstance(item, ImplementationClassUIDNotification):
                if item.implementation_class_uid is None:
                    LOGGER.error("Implementation Class UID has not been set")
                    raise ValueError("Implementation Class UID has not been set")

                return item.implementation_class_uid

        LOGGER.error("Implementation Class UID has not been set")
        raise ValueError("Implementation Class UID has not been set")

    @implementation_class_uid.setter
    def implementation_class_uid(self, value: OptionalUIDType) -> None:
        """Set the Implementation Class UID."""
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

    @property
    def maximum_length_received(self) -> int | None:
        """Get or set the *Maximum Length Received* as :class:`int`.

        If the A_ASSOCIATE.user_information list contains a
        MaximumLengthNotification item then set its maximum_length_received
        value. If not then add a MaximumLengthNotification item and set its
        maximum_length_received value.

        Parameters
        ----------
        value : int
            The maximum length of each P-DATA in bytes
        """
        for item in self.user_information:
            if isinstance(item, MaximumLengthNotification):
                return item.maximum_length_received

        return None

    @maximum_length_received.setter
    def maximum_length_received(self, value: int) -> None:
        """Set the Maximum Length Received."""
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
    def mode(self) -> str:
        """Return the *Mode* parameter as :class:`str`."""
        return "normal"

    @property
    def presentation_context_definition_list(self) -> list[PresentationContext]:
        """Get or set the *Presentation Context Definition List*.

        Parameters
        ----------
        value_list : list of presentation.PresentationContext
            The Presentation Contexts proposed by the Association Requestor
        """
        return self._presentation_context_definition_list

    @presentation_context_definition_list.setter
    def presentation_context_definition_list(
        self, value_list: list[PresentationContext]
    ) -> None:
        """Set the A-ASSOCIATE Service primitive's Presentation Context
        Definition List parameter.
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
            LOGGER.error(
                "A_ASSOCIATE.presentation_context_definition_list must be a list"
            )
            raise TypeError(
                "A_ASSOCIATE.presentation_context_definition_list must be a list"
            )

    @property
    def presentation_context_definition_results_list(self) -> list[PresentationContext]:
        """Get or set the *Presentation Context Definition Results List*.

        Parameters
        ----------
        value_list : list of presentation.PresentationContext
            The results of the Presentation Contexts proposal by the
            Association Requestor
        """
        return self._presentation_context_definition_results_list

    @presentation_context_definition_results_list.setter
    def presentation_context_definition_results_list(
        self, value_list: list[PresentationContext]
    ) -> None:
        """Set the Presentation Context Definition Results List parameter."""
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value_list, list):
            valid_items = []
            for item in value_list:
                if isinstance(item, PresentationContext):
                    valid_items.append(item)
                else:
                    LOGGER.warning(
                        "Attempted to set A_ASSOCIATE.presentation"
                        "_context_definition_results_list to a "
                        "list which includes one or more invalid "
                        "items"
                    )

            self._presentation_context_definition_results_list = valid_items

        else:
            LOGGER.error(
                "A_ASSOCIATE.presentation_context_definition_"
                "results_list must be a list"
            )
            raise TypeError(
                "A_ASSOCIATE.presentation_context_definition_"
                "results_list must be a list"
            )

    @property
    def presentation_requirements(self) -> str:
        """Return the *Presentation Kernel* as :class:`str`."""
        return "Presentation Kernel"

    @property
    def reason_str(self) -> str:
        """Return the rejection reason as str."""
        reasons = {
            1: {
                1: "No reason given",
                2: "Application context name not supported",
                3: "Calling AE title not recognised",
                4: "Reserved",
                5: "Reserved",
                6: "Reserved",
                7: "Called AE title not recognised",
                8: "Reserved",
                9: "Reserved",
                10: "Reserved",
            },
            2: {1: "No reason given", 2: "Protocol version not supported"},
            3: {
                0: "Reserved",
                1: "Temporary congestion",
                2: "Local limit exceeded",
                3: "Reserved",
                4: "Reserved",
                5: "Reserved",
                6: "Reserved",
                7: "Reserved",
            },
        }
        result = cast(int, self.result_source)
        diagnostic = cast(int, self.diagnostic)
        try:
            return reasons[result][diagnostic]
        except KeyError:
            LOGGER.warning(
                f"Invalid A-ASSOCIATE 'Result Source' {result} and/or "
                f"'Diagnostic' {diagnostic} values"
            )
            return "(no value available)"

    @property
    def responding_ae_title(self) -> str | None:
        """Return the *Responding AE Title* parameter."""
        return self.called_ae_title

    @property
    def responding_presentation_address(self) -> "AddressInformation | None":
        """Get the Responding Presentation Address parameter."""
        return self.called_presentation_address

    @property
    def result(self) -> int | None:
        """Get or set the *Result* parameter.

        Parameters
        ----------
        value : int
            One of the following:

            * 0: accepted
            * 1: rejected (permanent)
            * 2: rejected (transient)

        Returns
        -------
        int
        """
        return self._result

    @result.setter
    def result(self, value: int | None) -> None:
        """Set the A-ASSOCIATE Service primitive's Result parameter."""
        # pylint: disable=attribute-defined-outside-init
        if value is None:
            pass
        elif value not in [0, 1, 2]:
            LOGGER.error("A_ASSOCIATE.result set to an unknown value")
            raise ValueError("Unknown A_ASSOCIATE.result value")

        self._result = value

    @property
    def result_source(self) -> int | None:
        """Get or set the *Result Source* parameter.

        Parameters
        ----------
        value : int
            One of the following:

            * 1: UL service-user
            * 2: UL service-provider (ACSE related function)
            * 3: UL service-provider (presentation related function)

        Returns
        -------
        int
        """
        return self._result_source

    @result_source.setter
    def result_source(self, value: int | None) -> None:
        """Set the A-ASSOCIATE Service primitive's Result Source parameter."""
        # pylint: disable=attribute-defined-outside-init
        if value is None:
            pass
        elif value not in [1, 2, 3]:
            LOGGER.error("A_ASSOCIATE.result_source set to an unknown value")
            raise ValueError("Unknown A_ASSOCIATE.result_source value")

        self._result_source = value

    @property
    def result_str(self) -> str:
        """Return the result as str."""
        results = {0: "Accepted", 1: "Rejected Permanent", 2: "Rejected Transient"}

        if self.result not in results:
            LOGGER.warning(f"Invalid A-ASSOCIATE 'Result' {self.result}")
            return "(no value available)"

        return results[self.result]

    @property
    def session_requirements(self) -> str:
        """Return the *Session Requirements* as :class:`str`."""
        return ""

    @property
    def source_str(self) -> str:
        """Return the reject source as str."""
        sources = {
            1: "Service User",
            2: "Service Provider (ACSE)",
            3: "Service Provider (Presentation)",
        }
        if self.result_source not in sources:
            LOGGER.warning(f"Invalid A-ASSOCIATE 'Result Source' {self.result_source}")
            return "(no value available)"

        return sources[self.result_source]

    @property
    def user_information(self) -> _UserInformationPrimitiveType:
        """Get or set the *User Information* parameter.

        Parameters
        ----------
        value_list : list of user information class objects
            A list of user information objects, must contain at least
            MaximumLengthNotification and ImplementationClassUIDNotification
        """
        return self._user_information

    @user_information.setter
    def user_information(self, value_list: _UserInformationPrimitiveType) -> None:
        """Set the A-ASSOCIATE primitive's User Information parameter."""
        # pylint: disable=attribute-defined-outside-init
        valid_usr_info_items = []

        if isinstance(value_list, list):
            # Iterate through the items and check they're an acceptable class
            for item in value_list:
                if item.__class__.__name__ in [
                    "MaximumLengthNotification",
                    "ImplementationClassUIDNotification",
                    "ImplementationVersionNameNotification",
                    "AsynchronousOperationsWindowNegotiation",
                    "SCP_SCU_RoleSelectionNegotiation",
                    "SOPClassExtendedNegotiation",
                    "SOPClassCommonExtendedNegotiation",
                    "UserIdentityNegotiation",
                ]:
                    valid_usr_info_items.append(item)
                else:
                    LOGGER.info(
                        "Attempted to set "
                        "A_ASSOCIATE.user_information to a list "
                        "which includes an unsupported item"
                    )
        else:
            LOGGER.error("A_ASSOCIATE.user_information must be a list")
            raise TypeError("A_ASSOCIATE.user_information must be a list")

        self._user_information = valid_usr_info_items


class A_RELEASE:
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

    References
    ----------
    * DICOM Standard, Part 8, :dcm:`Section 7.2<part08/sect_7.2.html>`
    """

    def __init__(self) -> None:
        self._result: str | None = None

    @property
    def reason(self) -> str:
        """Return the *Reason* parameter."""
        return "normal"

    @property
    def result(self) -> str | None:
        """Get or set the *Result* parameter.

        Parameters
        ----------
        value : str
            Must be ``None`` for request and indication, ``'affirmative'``
            for response and confirmation.
        """
        return self._result

    @result.setter
    def result(self, value: str | None) -> None:
        """Set the Result parameter."""
        # pylint: disable=attribute-defined-outside-init
        if value is not None and value != "affirmative":
            LOGGER.error("A_RELEASE.result must be None or 'affirmative'")
            raise ValueError("A_RELEASE.result must be None or 'affirmative'")

        self._result = value


class A_ABORT:
    """An A-ABORT primitive.

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

    References
    ----------

    * DICOM Standard, Part 8, :dcm:`Section 7.3<part08/sect_7.3.html>`
    """

    def __init__(self) -> None:
        self._abort_source: int | None = None

    @property
    def abort_source(self) -> int | None:
        """Get or set the *Abort Source*.

        Parameters
        ----------
        value : int or None
            The abort source, one of:

            * ``0``: Upper layer service user
            * ``1``: Reserved
            * ``2``: Upper layer service provider
        """
        if self._abort_source is None:
            LOGGER.error("A_ABORT.abort_source value not set")
            raise ValueError("A_ABORT.abort_source value not set")

        return self._abort_source

    @abort_source.setter
    def abort_source(self, value: int | None) -> None:
        """Set the Abort Source."""
        if value in [0, 1, 2, None]:
            self._abort_source = value
        else:
            msg = f"Invalid A-ABORT 'Source' value '{value}'"
            LOGGER.error(msg)
            raise ValueError(msg)


class A_P_ABORT:
    """
    An A-P-ABORT primitive.

    +------------------+------------+
    | Parameter        | Indication |
    +------------------+------------+
    | provider reason  | P          |
    +------------------+------------+

    | U   - User option
    | UF  - User option, fixed value
    | C   - Conditional (on user option)
    | M   - Mandatory
    | MF  - Mandatory, fixed value
    | NU  - Not used
    | P   - Provider initiated
    | (=) - shall have same value as request or response

    References
    ----------

    * DICOM Standard, Part 8, :dcm:`Section 7.4<part08/sect_7.4.html>`
    """

    def __init__(self) -> None:
        self._provider_reason: int | None = None

    @property
    def provider_reason(self) -> int | None:
        """Return the *Provider Reason*.

        Parameters
        ----------
        value : int
            Indicates the reason for the abort. Allowed values are:

            * ``0``: reason not specified
            * ``1``: unrecognised PDU
            * ``2``: unexpected PDU
            * ``4``: unrecognised PDU parameter
            * ``5``: unexpected PDU parameter
            * ``6``: invalid PDU parameter value
        """
        if self._provider_reason is None:
            LOGGER.error("A_ABORT.provider_reason parameter not set")
            raise ValueError("A_ABORT.provider_reason value not set")

        return self._provider_reason

    @provider_reason.setter
    def provider_reason(self, value: int | None) -> None:
        """Set the Provider Reason."""
        if value in [0, 1, 2, 4, 5, 6, None]:
            self._provider_reason = value
        else:
            msg = "Attempted to set A_P_ABORT.provider_reason to an invalid value"
            LOGGER.error(msg)
            raise ValueError(msg)


class P_DATA:
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

    References
    ----------

    * DICOM Standard, Part 8, :dcm:`Section 7.6<part08/sect_7.6.html>`
    """

    def __init__(self) -> None:
        self._presentation_data_value_list: list[tuple[int, bytes]] = []

    @property
    def presentation_data_value_list(self) -> list[tuple[int, bytes]]:
        """Get or set the *Presentation Data Value List*.

        Parameters
        ----------
        presentation_data_value_list : list of [int, bytes]
            Contains one or more Presentation Data Values (PDV), each
            consisting of a Presentation Context ID and User Data values.
            The User Data values are taken from the Abstract Syntax and
            encoded in the Transfer Syntax identified by the Presentation
            Context ID. Each item in the list is ``[Context ID, PDV Data]``
        """
        return self._presentation_data_value_list

    @presentation_data_value_list.setter
    def presentation_data_value_list(self, value_list: list[tuple[int, bytes]]) -> None:
        """Set the Presentation Data Value List."""
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value_list, list):
            for pdv in value_list:
                if isinstance(pdv, list):
                    if isinstance(pdv[0], int) and isinstance(pdv[1], bytes):
                        pass
                    else:
                        raise TypeError(
                            "P_DATA.presentation_data_value_list "
                            "should be a list of [int, bytes]"
                        )
                else:
                    raise TypeError(
                        "P_DATA.presentation_data_value_list "
                        "should be a list of [ID, PDV]"
                    )
        else:
            raise TypeError(
                "P_DATA.presentation_data_value_list "
                "should be a list of [int, bytes]"
            )

        self._presentation_data_value_list = value_list

    def __str__(self) -> str:
        """String representation of the class."""
        s = "P-DATA\n"
        for pdv in self.presentation_data_value_list:
            header_byte = pdv[1][0]
            s += f"  Context ID: {pdv[0]}\n"
            s += f"  Value Length: {len(pdv[1])} bytes\n"
            s += f"  Message Control Header Byte: {header_byte:08b}\n"

            # xxxxxx01 and xxxxxx011
            if header_byte & 1:
                # xxxxxx11
                if header_byte & 2:
                    s += (
                        "    Command information, last fragment of the "
                        "DIMSE message\n"
                    )
                # xxxxxx01
                else:
                    s += (
                        "    Command information, not the last fragment of "
                        "the DIMSE message\n"
                    )
            # xxxxxx00, xxxxxxx10
            else:
                # xxxxxx10
                if header_byte & 2 != 0:
                    s += (
                        "    Dataset information, last fragment of the "
                        "DIMSE message\n"
                    )
                # xxxxxx00
                else:
                    s += (
                        "    Dataset information, not the last fragment of "
                        "the DIMSE message\n"
                    )

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

    References
    ----------

    * DICOM Standard, Part 7,
      :dcm:`Annex D.3.3.1<part07/sect_D.3.3.html#sect_D.3.3.1>`
    * DICOM Standard, Part 8, :dcm:`Annex D.1<part08/chapter_D.html#sect_D.1>`
    """

    def __init__(self) -> None:
        self._maximum_length: int
        self.maximum_length_received = DEFAULT_MAX_LENGTH

    def from_primitive(self) -> MaximumLengthSubItem:
        """Convert the primitive to a PDU item ready to be encoded.

        Returns
        -------
        item : pdu_items.MaximumLengthSubItem
        """
        item = MaximumLengthSubItem()
        item.from_primitive(self)

        return item

    @property
    def maximum_length_received(self) -> int:
        """Get or set the *Maximum Length Received* using :class:`int`.

        Parameters
        ----------
        val : int
            The maximum length of each P-DATA in bytes, must be equal to or
            greater than 0. A value of ``0`` indicates unlimited length
            (``31682`` bytes default).

        Raises
        ------
        ValueError
            If `maximum_length_received` is negative
        TypeError
            If `maximum_length_received` is not an int
        """
        return self._maximum_length

    @maximum_length_received.setter
    def maximum_length_received(self, val: int) -> None:
        """User defined Maximum Length to be used during an Association."""
        # pylint: disable=attribute-defined-outside-init
        if isinstance(val, int):
            if val < 0:
                LOGGER.error("Maximum Length Received must be greater than 0")
                raise ValueError("Maximum Length Received must be greater than 0")
            else:
                self._maximum_length = val
        else:
            LOGGER.error("Maximum Length Received must be numerical")
            raise TypeError("Maximum Length Received must be numerical")

    def __str__(self) -> str:
        """String representation of the class."""
        s = [
            "Maximum Length Negotiation",
            f"  Maximum length received: " f"{self.maximum_length_received:d} bytes\n",
        ]
        return "\n".join(s)


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

    def __init__(self) -> None:
        self._implementation_class_uid: UID | None = None

    def from_primitive(self) -> ImplementationClassUIDSubItem:
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
            LOGGER.error(
                "The Implementation Class UID must be set prior to "
                "requesting Association"
            )
            raise ValueError(
                "The Implementation Class UID must be set "
                "prior to requesting Association"
            )

        item = ImplementationClassUIDSubItem()
        item.from_primitive(self)

        return item

    @property
    def implementation_class_uid(self) -> UID | None:
        """Get or set the *Implementation Class UID*.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The value for the Implementation Class UID
        """
        return self._implementation_class_uid

    @implementation_class_uid.setter
    def implementation_class_uid(self, value: OptionalUIDType) -> None:
        """Sets the Implementation Class UID parameter."""
        self._implementation_class_uid = set_uid(value, "Implementation Class UID")

    def __str__(self) -> str:
        """String representation of the class."""
        s = "Implementation Class UID\n"
        s += f"  Implementation class UID: {self.implementation_class_uid}\n"
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

    def __init__(self) -> None:
        self._implementation_version_name: str | None = None

    def from_primitive(self) -> ImplementationVersionNameSubItem:
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
            raise ValueError(
                "Implementation Version Name must be set prior to Association"
            )

        item = ImplementationVersionNameSubItem()
        item.from_primitive(self)

        return item

    @property
    def implementation_version_name(self) -> str | None:
        """Get or set the *Implementation Version Name*.

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
        return self._implementation_version_name

    @implementation_version_name.setter
    def implementation_version_name(self, value: str | None) -> None:
        """Sets the Implementation Version Name parameter."""
        self._implementation_version_name = set_ae(
            value, "Implementation Version Name", True, True
        )

    def __str__(self) -> str:
        """String representation of the class."""
        version = self.implementation_version_name
        s = "Implementation Version Name\n"
        s += f"  Implementation version name: {version}\n"

        return s


class AsynchronousOperationsWindowNegotiation(ServiceParameter):
    """
    Representation of the Asynchronous Operations Window Negotiation primitive.

    Allows peer AEs to negotiate the maximum number of outstanding operation
    or sub-operation requests. This negotiation is optional.

    The Asynchronous Operations Window is optional and there may only be a
    single :class:`AsynchronousOperationsWindowNegotiation` item

    Identical for both A-ASSOCIATE-RQ and A-ASSOCIATE-AC.

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

    def __init__(self) -> None:
        self._maximum_number_operations_invoked = 1
        self._maximum_number_operations_performed = 1

    def from_primitive(self) -> AsynchronousOperationsWindowSubItem:
        """Convert the primitive to a PDU item ready to be encoded.

        Returns
        -------
        item : pdu_items.AsynchronousOperationsWindowSubItem
        """
        item = AsynchronousOperationsWindowSubItem()
        item.from_primitive(self)

        return item

    @property
    def maximum_number_operations_invoked(self) -> int:
        """Get or set the *Maximum Number Operations Invoked*.

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
        return self._maximum_number_operations_invoked

    @maximum_number_operations_invoked.setter
    def maximum_number_operations_invoked(self, value: int) -> None:
        """Sets the Maximum Number Operations Invoked parameter."""
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, int):
            pass
        else:
            LOGGER.error("Maximum Number Operations Invoked must be an int")
            raise TypeError("Maximum Number Operations Invoked must be an int")

        if value < 0:
            raise ValueError("Maximum Number Operations Invoked must be greater than 0")

        self._maximum_number_operations_invoked = value

    @property
    def maximum_number_operations_performed(self) -> int:
        """Get or set the *Maximum Number Operations Performed*.

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
        return self._maximum_number_operations_performed

    @maximum_number_operations_performed.setter
    def maximum_number_operations_performed(self, value: int) -> None:
        """Sets the Maximum Number Operations Performed parameter"""
        # pylint: disable=attribute-defined-outside-init
        if not isinstance(value, int):
            LOGGER.error("Maximum Number Operations Performed must be an int")
            raise TypeError("Maximum Number Operations Performed must be an int")

        if value < 0:
            raise ValueError(
                "Maximum Number Operations Performed must be greater than 0"
            )

        self._maximum_number_operations_performed = value

    def __str__(self) -> str:
        """String representation of the class."""
        invoked = self.maximum_number_operations_invoked
        performed = self.maximum_number_operations_performed
        s = "Asynchronous Operations Window\n"
        s += f"  Maximum number operations invoked: {invoked:d}\n"
        s += f"  Maximum number operations performed: {performed:d}\n"

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

    def __init__(self) -> None:
        self._sop_class_uid: UID | None = None
        self._scu_role: bool | None = None
        self._scp_role: bool | None = None

    def from_primitive(self) -> SCP_SCU_RoleSelectionSubItem:
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
            raise ValueError("'sop_class_uid' must be set prior to Association")

        # To get to this point self.sop_class_uid must be set
        if not self.scu_role and not self.scp_role:
            uid = self.sop_class_uid
            msg = f"SCU and SCP Roles cannot both be unsupported for '{uid}'"
            LOGGER.error(msg)
            raise ValueError(msg)

        item = SCP_SCU_RoleSelectionSubItem()
        item.from_primitive(self)

        return item

    @property
    def scp_role(self) -> bool | None:
        """Get or set the *SCP Role*.

        Parameters
        ----------
        value : bool
            True if supported, False otherwise (default)

        Raises
        ------
        TypeError
            If `value` is not a bool
        """
        return self._scp_role

    @scp_role.setter
    def scp_role(self, value: bool | None) -> None:
        """Sets the SCP Role parameter."""
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, bool) or value is None:
            pass
        else:
            LOGGER.error("SCP Role must be boolean")
            raise TypeError("SCP Role must be boolean")

        self._scp_role = value

    @property
    def scu_role(self) -> bool | None:
        """Get or set the *SCU Role*.

        Parameters
        ----------
        value : bool
            True if supported, False otherwise

        Raises
        ------
        TypeError
            If `value` is not a bool
        """
        return self._scu_role

    @scu_role.setter
    def scu_role(self, value: bool | None) -> None:
        """Sets the SCU Role parameter."""
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, bool) or value is None:
            pass
        else:
            LOGGER.error("SCU Role must be boolean")
            raise TypeError("SCU Role must be boolean")

        self._scu_role = value

    @property
    def sop_class_uid(self) -> UID | None:
        """Get or set the *SOP Class UID*.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The corresponding Abstract Syntax UID

        Raises
        ------
        TypeError
            If `value` is not a pydicom.uid.UID, bytes or str
        """
        return self._sop_class_uid

    @sop_class_uid.setter
    def sop_class_uid(self, value: OptionalUIDType) -> None:
        """Sets the SOP Class UID parameter."""
        self._sop_class_uid = set_uid(value, "SOP Class UID")


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

    def __init__(self) -> None:
        self._sop_class_uid: UID | None = None
        self._service_class_application_information: bytes | None = None

    def from_primitive(self) -> SOPClassExtendedNegotiationSubItem:
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
        if (
            self.sop_class_uid is None
            or self.service_class_application_information is None
        ):
            LOGGER.error(
                "SOP Class UID and Service Class Application "
                "Information must be set prior to Association "
                "negotiation"
            )
            raise ValueError(
                "SOP Class UID and Service Class Application "
                "Information must be set prior to Association "
                "negotiation"
            )

        item = SOPClassExtendedNegotiationSubItem()
        item.from_primitive(self)

        return item

    @property
    def service_class_application_information(self) -> bytes | None:
        """Get or set the *Service Class Application Information*.

        Parameters
        ----------
        value : bytes
            The Service Class Application Information as per the Service Class
            Specifications (see PS3.4)

        Raises
        ------
        TypeError
            If `value` is not a bytes object.
        """
        return self._service_class_application_information

    @service_class_application_information.setter
    def service_class_application_information(self, value: bytes | None) -> None:
        """Sets the Service Class Application Information parameter."""
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, bytes) or value is None:
            pass
        else:
            LOGGER.error(
                "Service Class Application Information should be a bytes object"
            )
            raise TypeError(
                "Service Class Application Information should be a bytes object"
            )

        self._service_class_application_information = value

    @property
    def sop_class_uid(self) -> UID | None:
        """Get or set the *SOP Class UID*.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The corresponding Abstract Syntax UID

        Raises
        ------
        TypeError
            If `value` is not a pydicom.uid.UID, bytes or str
        """
        return self._sop_class_uid

    @sop_class_uid.setter
    def sop_class_uid(self, value: OptionalUIDType) -> None:
        """Sets the SOP Class UID parameter."""
        self._sop_class_uid = set_uid(value, "SOP Class UID")


class SOPClassCommonExtendedNegotiation(ServiceParameter):
    """
    A representation of the SOP Class Common Extended Negotiation primitive.

    Allows peer AEs to exchange generic application information.

    The SOP Class Common Extended Negotiation is optional and there may only be
    a single :class:`SOPClassCommonExtendedNegotiation` item for each available
    SOP Class UID.

    Identical for both A-ASSOCIATE-RQ and A-ASSOCIATE-AC

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

    def __init__(self) -> None:
        self._service_class_uid: UID | None = None
        self._sop_class_uid: UID | None = None
        self._related_general_sop_class_identification: list[UID] = []

    def from_primitive(self) -> SOPClassCommonExtendedNegotiationSubItem:
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
            LOGGER.error(
                "SOP Class UID and Service Class UID must be set "
                "prior to Association negotiation"
            )
            raise ValueError(
                "SOP Class UID and Service Class UID must be "
                "set prior to Association negotiation"
            )

        item = SOPClassCommonExtendedNegotiationSubItem()
        item.from_primitive(self)

        return item

    @property
    def related_general_sop_class_identification(self) -> list[UID]:
        """Return the *Related General SOP Class Identification*.

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
        return self._related_general_sop_class_identification

    @related_general_sop_class_identification.setter
    def related_general_sop_class_identification(
        self, uid_list: list[str | bytes | UID]
    ) -> None:
        """Sets the Service Class Application Information parameter."""
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
                    uid = UID(decode_bytes(uid))
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
                        f"The Related General SOP Class UID '{uid}' is "
                        f"non-conformant"
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
    def service_class_uid(self) -> UID | None:
        """Return the *Service Class UID*.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The corresponding Service Class UID

        Raises
        ------
        TypeError
            If `value` is not a pydicom.uid.UID, bytes or str
        """
        return self._service_class_uid

    @service_class_uid.setter
    def service_class_uid(self, value: OptionalUIDType) -> None:
        """Sets the Service Class UID parameter."""
        self._service_class_uid = set_uid(value, "Service Class UID")

    @property
    def sop_class_uid(self) -> UID | None:
        """Return the *SOP Class UID*.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The SOP Class UID

        Raises
        ------
        TypeError
            If `value` is not a pydicom.uid.UID, bytes or str
        """
        return self._sop_class_uid

    @sop_class_uid.setter
    def sop_class_uid(self, value: OptionalUIDType) -> None:
        """Sets the SOP Class UID parameter."""
        self._sop_class_uid = set_uid(value, "SOP Class UID")


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

    def __init__(self) -> None:
        self._user_identity_type: int | None = None
        self._positive_response_requested: bool = False
        self._primary_field: bytes | None = None
        self._secondary_field: bytes | None = b""
        self._server_response: bytes | None = None

    def from_primitive(self) -> UserIdentitySubItemAC | UserIdentitySubItemRQ:
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
        item: UserIdentitySubItemRQ | UserIdentitySubItemAC
        if self.server_response is None:
            # Then an -RQ
            if self.user_identity_type is None or self.primary_field is None:
                msg = (
                    "User Identity Type and Primary Field must be "
                    "set prior to Association negotiation"
                )
                LOGGER.error(msg)
                raise ValueError(msg)

            if self.user_identity_type == 2 and self.secondary_field == b"":
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
    def positive_response_requested(self) -> bool:
        """Get or set *Positive Response Requested*.

        Parameters
        ----------
        value : bool
            True if response requested, False otherwise

        Raises
        ------
        TypeError
            If `value` is not a bool
        """
        return self._positive_response_requested

    @positive_response_requested.setter
    def positive_response_requested(self, value: bool) -> None:
        """Sets the Positive Response Requested parameter."""
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, bool):
            pass
        else:
            LOGGER.error("Positive Response Requested must be boolean")
            raise TypeError("Positive Response Requested must be boolean")

        self._positive_response_requested = value

    @property
    def primary_field(self) -> bytes | None:
        """Get or set *Primary Field*.

        Parameters
        ----------
        value : bytes or None
            The username, Kerberos Service ticket or SAML assertion as a
            bytes object.

        Raises
        ------
        TypeError
            If `value` is not bytes or None
        """
        return self._primary_field

    @primary_field.setter
    def primary_field(self, value: bytes | None) -> None:
        """Sets the Primary Field parameter."""
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, bytes):
            pass
        elif value is None:
            pass
        else:
            LOGGER.error(
                "Primary Field must be bytes if requesting "
                "Association, None otherwise"
            )
            raise TypeError(
                "Primary Field must be bytes if requesting "
                "Association, None otherwise"
            )

        self._primary_field = value

    @property
    def secondary_field(self) -> bytes | None:
        """Get or set the *Secondary Field*.

        Only used when User Identity Type is equal to 2.

        Parameters
        ----------
        value : bytes
            The passcode as a bytes object
        """
        return self._secondary_field

    @secondary_field.setter
    def secondary_field(self, value: bytes | None) -> None:
        """Sets the Secondary Field parameter."""
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, bytes) or value is None:
            pass
        else:
            LOGGER.error(
                "Secondary Field must be bytes if requesting "
                "Association with User Identity Type equal to 2, "
                "None otherwise"
            )
            raise TypeError(
                "Secondary Field must be bytes if requesting "
                "Association with User Identity Type equal to 2, "
                "None otherwise"
            )

        self._secondary_field = value

    @property
    def server_response(self) -> bytes | None:
        """Get or set the *Server Response*.

        A-ASSOCIATE-AC only.

        Parameters
        ----------
        value : bytes or None
            The server response as a bytes object. The Kerberos Service
            ticket, SAML response or JSON web token if the
            `user_identity_type` is ``3``, ``4`` or ``5``. Shall be
            ``None`` if `user_identity_type` was ``1`` or ``2``.

        Raises
        ------
        TypeError
            If `value` is not bytes or None
        """
        return self._server_response

    @server_response.setter
    def server_response(self, value: bytes | None) -> None:
        """Sets the Server Response parameter."""
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, bytes):
            pass
        elif value is None:
            pass
        else:
            LOGGER.error("Server Response must be bytes or None")
            raise TypeError("Server Response must be bytes or None")

        self._server_response = value

    def __str__(self) -> str:
        """String representation of the class."""
        s = "User Identity Parameters\n"
        if self.server_response is None:
            rsp_req = self.positive_response_requested
            s += f"  User identity type: {self.user_identity_type:d}\n"
            s += f"  Positive response requested: {rsp_req}\n"
            s += f"  Primary field: {self.primary_field!r}\n"
            s += f"  Secondary field: {self.secondary_field!r}\n"
        else:
            s += f"  Server response: {self.server_response!r}\n"

        return s

    @property
    def user_identity_type(self) -> int | None:
        """Return the *User Identity Type*.

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
        return self._user_identity_type

    @user_identity_type.setter
    def user_identity_type(self, value: int | None) -> None:
        """Sets the User Identity Type parameter."""
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, int):
            if value not in [1, 2, 3, 4, 5]:
                LOGGER.error(
                    "User Identity Type must be 1, 2, 3, 4 or 5 if "
                    "requesting Association, None otherwise"
                )
                raise ValueError(
                    "User Identity Type must be 1, 2, 3, 4 or 5 "
                    "if requesting Association, None otherwise"
                )
        elif value is None:
            pass
        else:
            LOGGER.error("User Identity Type must be an int or None")
            raise TypeError("User Identity Type must be an int or None")

        self._user_identity_type = value
