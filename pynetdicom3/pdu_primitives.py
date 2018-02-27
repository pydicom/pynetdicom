"""
Implementaion of the service parameter primitives.
"""
import codecs
import logging

from pydicom.uid import UID

from pynetdicom3.pdu import (MaximumLengthSubItem,
                             ImplementationClassUIDSubItem,
                             ImplementationVersionNameSubItem,
                             AsynchronousOperationsWindowSubItem,
                             SCP_SCU_RoleSelectionSubItem,
                             SOPClassExtendedNegotiationSubItem,
                             SOPClassCommonExtendedNegotiationSubItem,
                             UserIdentitySubItemRQ,
                             UserIdentitySubItemAC)
from pynetdicom3.utils import validate_ae_title, PresentationContext
#from pynetdicom3.utils import pretty_bytes

LOGGER = logging.getLogger('pynetdicom3.pdu_primitives')


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

    def from_primitive(self):
        """FIXME"""
        raise NotImplementedError

    def FromParams(self):
        """FIXME"""
        return self.from_primitive()


# Association Service primitives
class A_ASSOCIATE(object):
    """
    A-ASSOCIATE Parameters

    The establishment of an association between two AEs shall be performed
    through ACSE A-ASSOCIATE request, indication, response and confirmation
    primitives.

    The initiator of the service is called the Requestor and the user that
    receives the request is the Acceptor.

    See PS3.8 Section 7.1.1

    The A-ASSOCIATE primitive is used by the DUL provider to send/receive
    information about the association. It gets converted to 
    A-ASSOCIATE-RQ, -AC, -RJ PDUs that are sent to the peer DUL provider and 
    gets deconverted from -RQ, -AC, -RJ PDUs received from the peer.

    It may be better to simply extend this with methods for containing
    the -rq, -ac, -rj possibilities rather than creating a new
    AssociationInformation class, but it would require maintaining the instance
    across the request-accept/reject path

    -rq = no Result value
    -ac = Result of 0x00
    -rj = Result != 0x00

    ::

        Parameter           Request     Indication      Response        Confirmation
        app context name    M           M(=)            M               M(=)
        calling ae title    M           M(=)            M               M(=)
        called ae title     M           M(=)            M               M(=)
        user info           M           M(=)            M               M(=)
        result                                          M               M(=)
        source                                                          M
        diagnostic                                      U               C(=)
        calling pres add    M           M(=)
        called pres add     M           M(=)
        pres context list   M           M(=)
        pres list result                                M               M(=)

        mode                UF          MF(=)
        resp ae title                                   MF              MF(=)
        resp pres add                                   MF              MF(=)
        pres and sess req   UF          UF(=)           UF              UF(=)

        U   - User option
        UF  - User option, fixed value
        C   - Conditional (on user option)
        M   - Mandatory
        MF  - Mandatory, fixed value
        (=) - shall have same value as request or response


    The Requestor sends a request primitive to the local DICOM UL provider =>
    peer UL => indication primitive to Acceptor.

    Acceptor sends response primitive to peer UL => local UL => confirmation
    primitive to Requestor

    The DICOM UL providers communicate with UL users using service primitives
    The DICOM UL providers communicate with each other using PDUs over TCP/IP

    **Service Procedure**

    1. An AE (DICOM UL service user) that desires the establish an association
       issues an A-ASSOCIATE request primitive to the DICOM UL service
       provider. The Requestor shall not issue any primitives except the
       A-ABORT request primitive until it receives an A-ASSOCIATE confirmation
       primitive.
    2. The DICOM UL service provider issues an A-ASSOCIATE indication primitive
       to the called AE
    3. The called AE shall accept or reject the association by sending an
       A-ASSOCIATE response primitive with an appropriate Result parameter. The
       DICOM UL service provider shall issue an A-ASSOCIATE confirmation
       primitive having the same Result parameter. The Result Source parameter
       shall be assigned "UL service-user"
    4. If the Acceptor accepts the association, it is established and is
       available for use. DIMSE messages can now be exchanged.
    5. If the Acceptor rejects the association, it shall not be established and
       is not available for use
    6. If the DICOM UL service provider is not capable of supporting the
       requested association it shall return an A-ASSOCIATE confirmation
       primitive to the Requestor with an appropriate Result parameter
       (rejected). The Result Source parameter shall be assigned either
       UL service provider (ACSE) or UL service provider (Presentation).
       The indication primitive shall not be issued. The association shall not
       be established.
    7. Either Requestor or Acceptor may disrupt the Service Procedure by issuing
       an A-ABORT request primitive. The remote AE receives an A-ABORT
       indication primitive. The association shall not be established

    Attributes
    ----------
    mode : str
        Fixed value of "normal"
        PS3.8 7.1.1.1, [UF, MF(=), -, -]
    application_context_name : pydicom.uid.UID, bytes or str
        The application context name proposed by the requestor. Acceptor returns
        either the same or a different name. Returned name specifies the
        application context used for the Association. See PS3.8 Annex A. The
        application context name shall be a valid UID or UID string and for
        version 3 of the DICOM Standard should be '1.2.840.10008.3.1.1.1'
        PS3.8 7.1.1.2, [M, M(=), M, M(=)]
    calling_ae_title : str or bytes
        Identifies the Requestor of the A-ASSOCIATE service. Must be a valid
        AE
        PS3.8 7.1.1.3, [M, M(=), M, M(=)]
    called_ae_title : str or bytes
        Identifies the intended Acceptor of the A-ASSOCIATE service. Must be a
        valid AE
        PS3.8 7.1.1.4, [M, M(=), M, M(=)]
    responding_ae_title : str or bytes
        Identifies the AE that contains the actual acceptor of the
        A-ASSOCIATE service. Shall always contain the same value as the
        Called AE Title of the A-ASSOCIATE indication
        PS3.8 7.1.1.5, [-, -, MF, MF(=)]
    user_information : list
        Used by Requestor and Acceptor to include AE user information. See
        PS3.8 Annex D and PS3.7 Annex D.3
        PS3.8 7.1.1.6, [M, M(=), M, M(=)]
    result : int
        Provided either by the Acceptor of the A-ASSOCIATE request, the UL
        service provider (ACSE related) or the UL service provider
        (Presentation related). Indicates the result of the A-ASSOCIATE
        service. Allowed values are:

            * 0: accepted
            * 1: rejected (permanent)
            * 2: rejected (transient)

        PS3.8 7.1.1.7, [-, -, M, M(=)]
    result_source : int
        Identifies the creating source of the Result and Diagnostic parameters
        Allowed values are:

            * 0: UL service-user
            * 1: UL service-provider (ACSE related function)
            * 2: UL service-provider (presentation related function)

        PS3.8 7.1.1.8, [-, -, -, M]
    diagnostic : int
        If the `result` parameter is 0 "rejected (permanent)" or 1 "rejected
        (transient)" then this supplies diagnostic information about the result.
        If `result_source` is 0 "UL service-user" then allowed values are:

            * 0: no reason given
            * 1: application context name not supported
            * 2: calling AE title not recognised
            * 3: called AE title not recognised

        If `result_source` is 1 "UL service-provider (ACSE related function)"
        then allowed values are:

            * 0: no reason given
            * 1: no common UL version

        If `result_source` is 2 "UL service-provider (presentation related
        function)" then allowed values are:

            * 0: no reason given
            * 1: temporary congestion
            * 2: local limit exceeded
            * 3: called presentation address unknown
            * 4: presentation protocol version not supported
            * 5: no presentation service access point available
            
        PS3.8 7.1.1.9, [-, -, U, C(=)]
    calling_presentation_address : str
        TCP/IP address of the Requestor
        PS3.8 7.1.1.10, [M, M(=), -, -]
    called_presentation_address : str
        TCP/IP address of the intended Acceptor
        PS3.8 7.1.1.11, [M, M(=), -, -]
    responding_presentation_address : str
        Shall always contain the same value as the Called Presentation Address
        PS3.8 7.1.1.12, [-, -, MF, MF(=)]
    presentation_context_definition_list : list
        List of one or more presentation contexts, with each item containing
        a presentation context ID, an Abstract Syntax and a list of one or
        more Transfer Syntax Names. Sent by the Requestor during
        request/indication
        PS3.8 7.1.1.13, [M, M(=), -, -]
    presentation_context_definition_results_list : list
        Used in response/confirmation to indicate acceptance or rejection of
        each presentation context definition.
        List of result values, with a one-to-one correspondence between each
        of the presentation contexts proposed in the Presentation Context
        Definition List parameter.
        The result values may be sent in any order and may be different than
        the order proposed.
        Only one Transfer Syntax per presentation context shall be agreed to
        PS3.8 7.1.1.14, [-, -, M, M(=)]
    presentation_requirements : str
        Fixed value of "Presentation Kernel"
        PS3.8 7.1.1.15, [UF, UF(=), UF, UF(=)]
    session_requirements : str
        Fixed value of "" (empty string)
        PS3.8 7.1.1.16, [UF, UF(=), UF, UF(=)]
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
            value = UID(value.decode('utf-8'))
        elif value is None:
            pass
        else:
            raise TypeError("application_context_name must be a "
                            "pydicom.uid.UID, str or bytes")

        if value is not None and not value.is_valid:
            LOGGER.error("application_context_name is an invalid UID")
            raise ValueError("application_context_name is an invalid UID")

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
            The Calling AE Title as a string or bytes object. Cannot be an empty
            string and will be truncated to 16 characters long
        """
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, str):
            value = codecs.encode(value, 'utf-8')

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
            value = codecs.encode(value, 'utf-8')

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
        value_list : list of pynetdicom3 user information class objects
            A list of user information objects, must contain at least
            MaximumLengthNegotiation and ImplementationClassUIDNotification
        """
        # pylint: disable=attribute-defined-outside-init
        valid_usr_info_items = []

        if isinstance(value_list, list):
            # Iterate through the items and check they're an acceptable class
            for item in value_list:
                if item.__class__.__name__ in \
                        ["MaximumLengthNegotiation",
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
            A tuple containing a valid TCP/IP address string and the port number
            as an int
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
            A tuple containing a valid TCP/IP address string and the port number
            as an int
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
        value_list : list of pynetdicom3.utils.PresentationContext
            The Presentation Contexts proposed by the Association Requestor
        """
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value_list, list):
            valid_items = []
            for item in value_list:
                if isinstance(item, PresentationContext):
                    valid_items.append(item)
                else:
                    LOGGER.warning("Attempted to set "
                                   "A_ASSOCIATE.presentation_context_definition_list to "
                                   "a list which includes an invalid items")

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
        value_list : list of pynetdicom3.utils.PresentationContext
            The results of the Presentation Contexts proposal by the Association
            Requestor
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
            if isinstance(item, MaximumLengthNegotiation):
                return item.maximum_length_received

        return None

    @maximum_length_received.setter
    def maximum_length_received(self, value):
        """Set the Maximum Length Received.

        If the A_ASSOCIATE.user_information list contains a
        MaximumLengthNegotiated item then set its maximum_length_received value.
        If not then add a MaximumLengthNegotiated item and set its
        maximum_length_received value.

        Parameters
        ----------
        value : int
            The maximum length of each P-DATA in bytes
        """
        # Type and value checking for the maximum_length_received parameter is
        #   done by the MaximumLengthNegotiated class

        # Check for a MaximumLengthNegotiation item
        found_item = False

        for item in self.user_information:
            if isinstance(item, MaximumLengthNegotiation):
                found_item = True
                item.maximum_length_received = value

        # No MaximumLengthNegotiated item found
        if not found_item:
            max_length = MaximumLengthNegotiation()
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

        # Check for a ImplementationClassUIDNegotiation item
        found_item = False
        for item in self.user_information:
            if isinstance(item, ImplementationClassUIDNotification):
                found_item = True
                item.implementation_class_uid = value

        # No ImplementationClassUIDNegotiation item found
        if not found_item:
            imp_uid = ImplementationClassUIDNotification()
            imp_uid.implementation_class_uid = value
            self.user_information.append(imp_uid)


class A_RELEASE(object):
    """
    A-RELEASE Parameters

    The release of an association between two AEs shall be performed through
    ACSE A-RELEASE request, indication, response and confirmation primitives.
    The initiator of the service is called a Requestor and the service-user that
    receives the A-RELEASE indication is called the acceptor.

    Service Procedure

    1. The user (Requestor) that desires to end the association issues an
       A-RELEASE request primitive. The Requestor shall not issue any other
       primitives other than A-ABORT until it receives an A-RELEASE confirmation
       primitive.
    2. The DUL provider issues an A-RELEASE indication to the Acceptor. The
       Acceptor shall not issue any other primitives other than A-RELEASE response,
       A-ABORT request or P-DATA request.
    3. To complete the release, the Acceptor replies using an A-RELEASE response
       primitive, with "affirmative" as the result parameter.
    4. After the Acceptor issues the A-RELEASE response it shall not issue any
       more primitives.
    5. The Requestor shall issue an A-RELEASE confirmation primitive always
       with an "affirmative" value for the Result parameter.
    6. A user may disrupt the release by issuing an A-ABORT request.
    7. A collision may occur when both users issue A-RELEASE requests
       simultaneously. In this situation both users receive an unexpect A-RELEASE
       indication primitive (instead of an A-RELEASE acceptance):

         a. The association requestor issues an A-RELEASE response primitive
         b. The association acceptor waits for an A-RELEASE confirmation
            primitive from its peer. When it receives one it issues an A-RELEASE
            response primitive
         c. The association requestor receives an A-RELEASE confirmation
            primitive.

       When both ACSE users have received an A-RELEASE confirmation primitive the
       association shall be released.

    Parameter   Request     Indication      Response        Confirmation
    reason      UF          UF(=)           UF              UF(=)
    user info   NU          NU(=)           NU              NU(=)
    result                                  MF              MF(=)

    UF - User option, fixed
    NU - Not used
    MF - Mandatory, fixed
    (=) - shall have same value as request or response

    See PS3.8 Section 7.2

    Attributes
    ----------
    reason : str
        Fixed value of "normal". Identifies the general level of urgency of the
        request
        PS3.8 7.2.1.1, [UF, UF(=), UF, UF(=)]
    result : str or None
        Must be None for request and indication, "affirmative" for response
        and confirmation
        PS3.8 7.2.1.2, [-, -, MF, MF(=)]
    """

    def __init__(self):
        self.result = None

    @property
    def reason(self):
        """Return the Reason parameter."""
        return "normal"

    @property
    def result(self):
        """Return the Result parameter."""
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
    """A-ABORT Parameters

    See PS3.8 Section 7.3.1

    Attributes
    ----------
    abort_source : int
        Indicates the initiating source of the abort. Allowed values are:
            * 0: UL service-user
            * 2: UL service-provider

        PS3.8 7.3.1.1, [-, M, X, X]
    """

    def __init__(self):
        self.abort_source = None

    @property
    def abort_source(self):
        """Return the Abort Source."""
        if self._abort_source is None:
            LOGGER.error("A_ABORT.abort_source parameter not set")
            raise ValueError("A_ABORT.abort_source value not set")

        return self._abort_source

    @abort_source.setter
    def abort_source(self, value):
        """Set the Abort Source."""
        # pylint: disable=attribute-defined-outside-init
        if value in [0, 2]:
            self._abort_source = value
        elif value is None:
            self._abort_source = None
        else:
            LOGGER.error("Attempted to set A_ABORT.abort_source to an "
                         "invalid value")
            raise ValueError("Attempted to set A_ABORT.abort_source to an "
                             "invalid value")


class A_P_ABORT(object):
    """A-P-ABORT Parameters.

    See PS3.8 Section 7.4.1

    Attributes
    ----------
    provider_reason : int
        Indicates the reason for the abort. Allowed values are:
            * 0: reason not specified
            * 1: unrecognised PDU
            * 2: unexpected PDU
            * 4: unrecognised PDU parameter
            * 5: unexpected PDU parameter
            * 6: invalid PDU parameter value

        PS3.8 7.3.1.1, [P, X, X, X]
    """

    def __init__(self):
        self.provider_reason = None

    @property
    def provider_reason(self):
        """Return the Provider Reason."""
        if self._provider_reason is None:
            LOGGER.error("A_ABORT.provider_reason parameter not set")
            raise ValueError("A_ABORT.provider_reason value not set")

        return self._provider_reason

    @provider_reason.setter
    def provider_reason(self, value):
        """Set the Provider Reason."""
        # pylint: disable=attribute-defined-outside-init
        if value in [0, 1, 2, 4, 5, 6]:
            self._provider_reason = value
        elif value is None:
            self._provider_reason = None
        else:
            LOGGER.error("Attempted to set A_ABORT.provider_reason to an "
                         "invalid value")
            raise ValueError("Attempted to set A_ABORT.provider_reason to an "
                             "invalid value")


class P_DATA(object):
    """P-DATA Parameters.

    See PS3.8 Section 7.6.1

    Attributes
    ----------
    presentation_data_value_list : list of [int, bytes]
        Contains one or more Presentation Data Values (PDV), each consisting of
        a Presentation Context ID and User Data values. The User Data values are
        taken from the Abstract Syntax and encoded in the Transfer Syntax
        identified by the Presentation Context ID. Each item in the list is
        [Context ID, PDV Data]
        PS3.8 7.6.1, [M, M(=), x, x]
    """

    def __init__(self):
        self.presentation_data_value_list = []

    @property
    def presentation_data_value_list(self):
        """Return the Presentation Data Value List."""
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
class MaximumLengthNegotiation(ServiceParameter):
    """Define the Maximum Length Negotiation primitive.

    The maximum length notification allows communicating AEs to limit the size
    of the data for each P-DATA indication. This notification is required for
    all DICOM v3.0 conforming implementations.

    This User Information item is required during Association negotiation and
    there must only be a single MaximumLengthNegotiation item

    PS3.7 Annex D.3.3.1 and PS3.8 Annex D.1

    Attributes
    ----------
    maximum_length_received : int
        The maximum length received value for the Maximum Length sub-item in
        bytes. A value of 0 indicates unlimited length (31682 bytes default).
    """

    def __init__(self):
        self.maximum_length_received = 16382

    def from_primitive(self):
        """Convert the primitive to a PDU item ready to be encoded.

        Returns
        -------
        item : pynetdicom3.pdu.MaximumLengthSubItem
        """
        item = MaximumLengthSubItem()
        item.FromParams(self)

        return item

    @property
    def maximum_length_received(self):
        """Return the Maximum Length Received."""
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


class ImplementationClassUIDNotification(ServiceParameter):
    """The Implementation Class UID Notification primitive.

    The implementation identification notification allows implementations of
    communicating AEs to identify each other at Association establishment time.
    It is intended to provider respective and non-ambiguous identification in
    the event of communication problems encountered between two nodes. This
    negotiation is required.

    Implementation identification relies on two pieces of information:
    - Implementation Class UID (required)
    - Implementation Version Name (optional)

    The Implementation Class UID is required during Association negotiation and
    there must only be a single ImplementationClassUID item

    PS3.7 Annex D.3.3.2

    Example
    -------
    impl_class_uid = ImplementationClassUID()
    impl_class_uid.implementation_class_uid = '1.1.2.2.3.3.4'

    usr_data_neg = []
    usr_data_neg.append(impl_class_uid)

    Attributes
    ----------
    implementation_class_uid : pydicom.uid.UID, bytes or str
        The UID to use
    """

    def __init__(self):
        self.implementation_class_uid = None

    def from_primitive(self):
        """Convert the primitive to a PDU item ready to be encoded.

        Returns
        -------
        item : pynetdicom3.pdu.ImplementationClassUIDSubItem

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
        item.FromParams(self)

        return item

    @property
    def implementation_class_uid(self):
        """Return the Implementation Class UID."""
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
            value = UID(value.decode('utf-8'))
        elif value is None:
            pass
        else:
            raise TypeError("Implementation Class UID must be a "
                            "pydicom.uid.UID, str or bytes")

        if value is not None and not value.is_valid:
            LOGGER.error("Implementation Class UID is an invalid UID")
            raise ValueError("Implementation Class UID is an invalid UID")

        self._implementation_class_uid = value

    def __str__(self):
        """String representation of the class."""
        s = "Implementation Class UID\n"
        s += "  Implementation class UID: {0!s}\n" \
             .format(self.implementation_class_uid)
        return s


class ImplementationVersionNameNotification(ServiceParameter):
    """The Implementation Version Name Notification primitive.

    The implementation identification notification allows implementations of
    communicating AEs to identify each other at Association establishment time.
    It is intended to provider respective and non-ambiguous identification in
    the event of communication problems encountered between two nodes. This
    negotiation is required.

    Implementation identification relies on two pieces of information:
    - Implementation Class UID (required)
    - Implementation Version Name (optional)

    The Implementation Version Name is optional and there may only be a single
    ImplementationVersionName item

    PS3.7 Annex D.3.3.2

    Attributes
    ----------
    implementation_version_name : str or bytes
        The version name to use, maximum of 16 characters
    """

    def __init__(self):
        self.implementation_version_name = None

    def from_primitive(self):
        """Convert the primitive to a PDU item ready to be encoded.

        Returns
        -------
        item : pynetdicom3.pdu.ImplementationVersionNameSubItem

        Raises
        ------
        ValueError
            If no name is set
        """
        if self.implementation_version_name is None:
            raise ValueError("Implementation Version Name must be set prior "
                             "to Association")

        item = ImplementationVersionNameSubItem()
        item.FromParams(self)

        return item

    @property
    def implementation_version_name(self):
        """Return the Implementation Version Name."""
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
            value = codecs.encode(value, 'utf-8')
        elif isinstance(value, bytes):
            pass
        elif value is None:
            pass
        else:
            LOGGER.error("Implementation Version Name must be a str or bytes")
            raise TypeError("Implementation Version Name must be a str "
                            "or bytes")

        if value is not None and not 1 < len(value) < 17:
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
    Allows peer AEs to negotiate the maximum number of outstanding operation
    or sub-operation requests. This negotiation is optional.

    The Asynchronous Operations Window is optional and there may only be a
    single AsynchronousOperationsWindowNegotiation item

    PS3.7 Annex D.3.3.3

    Identical for both A-ASSOCIATE-RQ and A-ASSOCIATE-AC

    Attributes
    ----------
    maximum_number_operations_invoked : int
        The maximum number of asynchronous operations invoked by the AE. A
        value of 0 indicates unlimited operations (default 1)
    maximum_number_operations_performed : int
        The maximum number of asynchronous operations performed by the AE. A
        value of 0 indicates unlimited operations (default 1)
    """

    def __init__(self):
        self.maximum_number_operations_invoked = 1
        self.maximum_number_operations_performed = 1

    def from_primitive(self):
        """Convert the primitive to a PDU item ready to be encoded.

        Returns
        -------
        item : pynetdicom3.pdu.AsynchronousOperationsWindowSubItem
        """
        item = AsynchronousOperationsWindowSubItem()
        item.FromParams(self)

        return item

    @property
    def maximum_number_operations_invoked(self):
        """Return the Maximum Number Operations Invoked."""
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
        """Return the Maximum Number Operations Performed."""
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
    Allows peer AEs to negotiate the roles in which they will serve for each
    SOP Class or Meta SOP Class supported on the Association. This negotiation
    is optional.

    The Association Requestor may use one SCP/SCU Role Selection item for each
    SOP Class as identified by its corresponding Abstract Syntax Name and shall
    be one of three role values:
    - Requestor is SCU only
    - Requestor is SCP only
    - Requestor is both SCU/SCP

    If the SCP/SCU Role Selection item is absent the default role for a
    Requestor is SCU and for an Acceptor is SCP.

    For a Requestor support for each SOP Class shall be one of the following
    roles:
    * Requestor is SCU only
    * Requestor is SCP only
    * Requestor is both SCU and SCP

    PS3.7 Annex D.3.3.4

    Identical for both A-ASSOCIATE-RQ and A-ASSOCIATE-AC

    Attributes
    ----------
    sop_class_uid : pydicom.uid.UID, bytes or str
        The UID of the corresponding Abstract Syntax
    scu_role : bool
        False for non-support of the SCU role, True for support
    scp_role : bool
        False for non-support of the SCP role, True for support
    """

    def __init__(self):
        self.sop_class_uid = None
        self.scu_role = None
        self.scp_role = None

    def from_primitive(self):
        """
        Convert the primitive to a PDU item ready to be encoded

        Returns
        -------
        item : pynetdicom3.pdu.SCP_SCU_RoleSelectionSubItem

        Raises
        ------
        ValueError
            If no SOP Class UID, SCU Role or SCP Role is set
        ValueError
            If SCU Role and SCP Role are both False
        """
        if self.sop_class_uid is None or self.scu_role is None \
                or self.scp_role is None:
            LOGGER.error("SOP Class UID, SCU Role and SCP Role must "
                         "to be set prior to Association")
            raise ValueError("SOP Class UID, SCU Role and SCP Role must "
                             "to be set prior to Association")

        # To get to this point self.sop_class_uid must be set
        if not self.scu_role and not self.scp_role:
            LOGGER.error("SCU and SCP Roles cannot both be unsupported "
                         "for %s", self.sop_class_uid)
            raise ValueError("SCU and SCP Roles cannot both be unsupported "
                             "for {}".format(self.sop_class_uid))

        item = SCP_SCU_RoleSelectionSubItem()
        item.FromParams(self)

        return item

    @property
    def sop_class_uid(self):
        """Return the SOP Class UID."""
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
            value = UID(value.decode('utf-8'))
        elif value is None:
            pass
        else:
            LOGGER.error("SOP Class UID must be a pydicom.uid.UID, str "
                         "or bytes")
            raise TypeError("SOP Class UID must be a pydicom.uid.UID, str "
                            "or bytes")

        if value is not None and not value.is_valid:
            LOGGER.error("Implementation Class UID is an invalid UID")
            raise ValueError("Implementation Class UID is an invalid UID")

        self._sop_class_uid = value

    @property
    def scu_role(self):
        """Return the SCU Role."""
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
    def scp_role(self):
        """Return the SCP Role."""
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


class SOPClassExtendedNegotiation(ServiceParameter):
    """
    Allows peer AEs to exchange application information defined by specific
    Service Class specifications. Each Service Class is required to document
    the application information it supports and how this information is
    negotiated between SCUs and SCPs.

    The SOP Class Extended Negotiation is optional and there may only be a
    single SOPClassExtendedNegotiation item for each available SOP Class UID.

    PS3.7 Annex D.3.3.5

    PS3.4 contains Service Class Specifications

    Identical for both A-ASSOCIATE-RQ and A-ASSOCIATE-AC

    Attributes
    ----------
    sop_class_uid : pydicom.uid.UID, bytes or str
        The UID of the SOP Class
    service_class_application_information : bytes
        The Service Class Application Information as per the Service Class
        Specifications (see PS3.4)
    """

    def __init__(self):
        self.sop_class_uid = None
        self.service_class_application_information = None

    def from_primitive(self):
        """Convert the primitive to a PDU item ready to be encoded.

        Returns
        -------
        item : pynetdicom3.pdu.SOPClassExtendedNegotiationSubItem

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
        item.FromParams(self)

        return item

    @property
    def sop_class_uid(self):
        """Return the SOP Class UID."""
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
            value = UID(value.decode('utf-8'))
        elif value is None:
            pass
        else:
            LOGGER.error("SOP Class UID must be a pydicom.uid.UID, str "
                         "or bytes")
            raise TypeError("SOP Class UID must be a pydicom.uid.UID, str "
                            "or bytes")

        if value is not None and not value.is_valid:
            LOGGER.error("Implementation Class UID is an invalid UID")
            raise ValueError("Implementation Class UID is an invalid UID")

        self._sop_class_uid = value

    @property
    def service_class_application_information(self):
        """Return the Service Class Application Information."""
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


class SOPClassCommonExtendedNegotiation(ServiceParameter):
    """
    Allows peer AEs to exchange generic application information.

    The SOP Class Common Extended Negotiation is optional and there may only be
    a single SOPClassCommonExtendedNegotiation item for each available SOP
    Class UID.

    PS3.7 Annex D.3.3.6

    Identical for both A-ASSOCIATE-RQ and A-ASSOCIATE-AC

    Attributes
    ----------
    sop_class_uid : pydicom.uid.UID, bytes or str
        The UID of the SOP Class
    service_class_uid : pydicom.uid.UID, bytes or str
        The UID of the corresponding Service Class
    related_general_sop_class_uid : list of (pydicom.uid.UID, bytes or str)
        Related General SOP Class UIDs (optional)
    """

    def __init__(self):
        self.sop_class_uid = None
        self.service_class_uid = None
        self.related_general_sop_class_identification = []

    def from_primitive(self):
        """Convert the primitive to a PDU item ready to be encoded.

        Returns
        -------
        item : pynetdicom3.pdu.SOPClassCommonExtendedNegotiationSubItem

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
        item.FromParams(self)

        return item

    @property
    def sop_class_uid(self):
        """Return the SOP Class UID."""
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
            value = UID(value.decode('utf-8'))
        elif value is None:
            pass
        else:
            LOGGER.error("SOP Class UID must be a pydicom.uid.UID, str "
                         "or bytes")
            raise TypeError("SOP Class UID must be a pydicom.uid.UID, str "
                            "or bytes")

        if value is not None and not value.is_valid:
            LOGGER.error("Implementation Class UID is an invalid UID")
            raise ValueError("Implementation Class UID is an invalid UID")

        self._sop_class_uid = value

    @property
    def service_class_uid(self):
        """Return the Service Class UID."""
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
            value = UID(value.decode('utf-8'))
        elif value is None:
            pass
        else:
            LOGGER.error("Service Class UID must be a pydicom.uid.UID, str "
                         "or bytes")
            raise TypeError("Service Class UID must be a pydicom.uid.UID, "
                            "str or bytes")

        if value is not None and not value.is_valid:
            LOGGER.error("Implementation Class UID is an invalid UID")
            raise ValueError("Implementation Class UID is an invalid UID")

        self._service_class_uid = value

    @property
    def related_general_sop_class_identification(self):
        """Return the Related General SOP Class Identification"""
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
            # Test that all the items in the list are UID compatible and convert
            #   them to pydicom.uid.UID if required
            valid_uid_list = []

            for uid in uid_list:
                if isinstance(uid, UID):
                    pass
                elif isinstance(uid, str):
                    uid = UID(uid)
                elif isinstance(uid, bytes):
                    uid = UID(uid.decode('utf-8'))
                else:
                    LOGGER.error("Related General SOP Class Identification "
                                 "must be a list of pydicom.uid.UID, str "
                                 "or bytes")
                    raise TypeError("Related General SOP Class "
                                    "Identification must be a list of "
                                    "pydicom.uid.UID, str or bytes")

                if uid is not None and not uid.is_valid:
                    LOGGER.error("Related General SOP Class "
                                 "Identification contains an invalid UID")
                    raise ValueError("Related General SOP Class contains "
                                     "an invalid UID")

                valid_uid_list.append(uid)

            self._related_general_sop_class_identification = valid_uid_list
        else:
            LOGGER.error("Related General SOP Class Identification "
                         "must be a list of pydicom.uid.UID, str "
                         "or bytes")
            raise TypeError("Related General SOP Class Identification "
                            "must be a list of pydicom.uid.UID, str "
                            "or bytes")


class UserIdentityNegotiation(ServiceParameter):
    """
    Allows peer AEs to exchange generic application information.

    The SOP Class Common Extended Negotiation is optional and there may only be
    a single SOPClassCommonExtendedNegotiation item for each available SOP
    Class UID.

    PS3.7 Annex D.3.3.7

    In general, a User Identity Negotiation request that is accepted will result
    in Association establishment and possibly a server response if requested
    and supported by the peer. If a server response is requested but not
    received then the Requestor must decide how to proceed.
    An Association rejected due to an authorisation failure will be indicated
    using Rejection Permanent with a Source of "DICOM UL service provided (ACSE
    related function)".

    How the Acceptor handles authentication is to be implemented by the end-user
    and is outside the scope of the DICOM standard.

    A-ASSOCIATE-RQ
    `user_identity_type`
    `positive_response_requested`
    `primary_field`
    `secondary_field`

    A-ASSOCIATE-AC
    The `server_response` parameter is required when a response to the User
    Identity Negotiation request is to be issued (although this depends on
    whether or not this is supported by the Acceptor).

    Attributes
    ----------
    user_identity_type : int or None
        A-ASSOCIATE-RQ only. One of the following values:
           * 1 - Username as string in UTF-8
           * 2 - Username as string in UTF-8 and passcode
           * 3 - Kerberos Service ticket
           * 4 - SAML Assertion
    positive_response_requested : bool
        A-ASSOCIATE-RQ only. True when requesting a response, False otherwise
        (default is False)
    primary_field : bytes or None
        A-ASSOCIATE-RQ only. Contains either the username, Kerberos Service
        ticket or SAML assertion depending on `user_identity_type`.
    secondary_field : bytes or None
        A-ASSOCIATE-RQ only. Only required if the `user_identity_type` is 2,
        when it should contain the passcode as a bytes object, None otherwise
    server_response : bytes or None
        A-ASSOCIATE-AC only. Shall contain the Kerberos Service ticket or SAML
        response if the `user_identity_type` in the Request was 3 or 4. Shall be
        None if `user_identity_type` was 1 or 2.
    """

    def __init__(self):
        self.user_identity_type = None
        self.positive_response_requested = False
        self.primary_field = None
        self.secondary_field = None
        self.server_response = None

    def from_primitive(self):
        """Convert the primitive to a PDU item ready to be encoded.

        Returns
        -------
        item : pynetdicom3.pdu.UserIdentitySubItemRQ or
            pynetdicom3.pdu.UserIdentitySubItemAC

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
                LOGGER.error("User Identity Type and Primary Field must be "
                             "set prior to Association negotiation")
                raise ValueError("User Identity Type and Primary Field "
                                 "must be set prior to Association negotiation")

            if self.user_identity_type == 2 and self.secondary_field is None:
                LOGGER.error("Secondary Field must be set when User Identity"
                             "is 2")
                raise ValueError("Secondary Field must be set when User "
                                 "Identity is 2")

            item = UserIdentitySubItemRQ()

        else:
            # Then an -AC
            item = UserIdentitySubItemAC()

        item.FromParams(self)

        return item

    @property
    def user_identity_type(self):
        """Return the User Identity Type."""
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

        Raises
        ------
        TypeError
            If `value` is not an int or None
        ValueError
            If `value` is an int and is not 1, 2, 3 or 4
        """
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, int):
            if value not in [1, 2, 3, 4]:
                LOGGER.error("User Identity Type must be 1, 2 3 or 4 if "
                             "requesting Association, None otherwise")
                raise ValueError("User Identity Type must be 1, 2 3 or 4 "
                                 "if requesting Association, None otherwise")
        elif value is None:
            pass
        else:
            LOGGER.error("User Identity Type must be an int or None")
            raise TypeError("User Identity Type must be an int or None")

        self._user_identity_type = value

    @property
    def positive_response_requested(self):
        """Return Positive Response Requested."""
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
        """Return Primary Field."""
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
        """Return the Secondary Field."""
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
        """Return the Server Response."""
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
