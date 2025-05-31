"""
The main user class, represents a DICOM Application Entity
"""

from copy import deepcopy
from datetime import datetime
import logging
import socket
from ssl import SSLContext
import threading
from typing import (
    cast,
    TypeVar,
    Type,
    Any,
    Sequence,
)
import warnings

from pydicom.uid import UID

from pynetdicom import _config
from pynetdicom.association import Association
from pynetdicom.events import EventHandlerType
from pynetdicom.presentation import PresentationContext
from pynetdicom.pdu_primitives import _UI
from pynetdicom.transport import (
    AssociationSocket,
    AssociationServer,
    ThreadedAssociationServer,
    AddressInformation,
)
from pynetdicom.utils import make_target, set_ae, decode_bytes, set_uid
from pynetdicom._globals import (
    MODE_REQUESTOR,
    DEFAULT_MAX_LENGTH,
    DEFAULT_TRANSFER_SYNTAXES,
)


LOGGER = logging.getLogger(__name__)


_T = TypeVar("_T")
ListCXType = list[PresentationContext]
TSyntaxType = None | str | UID | Sequence[str] | Sequence[UID]


class ApplicationEntity:
    """Represents a DICOM Application Entity (AE).

    An AE may be a *Service Class Provider* (SCP), a *Service Class User* (SCU)
    or both.
    """

    # pylint: disable=too-many-instance-attributes,too-many-public-methods
    def __init__(self, ae_title: str = "PYNETDICOM") -> None:
        """Create a new Application Entity.

        .. versionchanged:: 2.0

            `ae_title` should be :class:`str`

        Parameters
        ----------
        ae_title : str, optional
            The AE title of the Application Entity as an ASCII string
            (default: ``'PYNETDICOM'``).
        """
        self._ae_title: str
        self.ae_title = ae_title

        from pynetdicom import (
            PYNETDICOM_IMPLEMENTATION_UID,
            PYNETDICOM_IMPLEMENTATION_VERSION,
        )

        # Default Implementation Class UID and Version Name
        self._implementation_uid: UID = PYNETDICOM_IMPLEMENTATION_UID
        self._implementation_version: str | None = PYNETDICOM_IMPLEMENTATION_VERSION

        # List of PresentationContext
        self._requested_contexts: ListCXType = []
        # {abstract_syntax : PresentationContext}
        self._supported_contexts: dict[UID, PresentationContext] = {}

        # Default maximum simultaneous associations
        self._maximum_associations = 10

        # Default maximum PDU receive size (in bytes)
        self._maximum_pdu_size = DEFAULT_MAX_LENGTH

        # Default timeouts - None means no timeout
        self._acse_timeout: float | None = 30
        self._connection_timeout: float | None = None
        self._dimse_timeout: float | None = 30
        self._network_timeout: float | None = 60

        # Require Calling/Called AE titles to match if value is non-empty str
        self._require_calling_aet: list[str] = []
        self._require_called_aet = False

        self._servers: list[ThreadedAssociationServer] = []
        self._lock: threading.Lock = threading.Lock()

    @property
    def acse_timeout(self) -> None | float:
        """Get or set the ACSE timeout value (in seconds).

        Parameters
        ----------
        value : int | float | None
            The maximum amount of time (in seconds) to wait for association
            related messages. A value of ``None`` means no timeout. (default:
            ``30``)
        """
        return self._acse_timeout

    @acse_timeout.setter
    def acse_timeout(self, value: float | None) -> None:
        """Set the ACSE timeout (in seconds)."""
        if value is None:
            self._acse_timeout = None
        elif isinstance(value, (int, float)) and value >= 0:
            self._acse_timeout = value
        else:
            LOGGER.warning("ACSE timeout set to 30 seconds")
            self._acse_timeout = 30

        for assoc in self.active_associations:
            assoc.acse_timeout = self.acse_timeout

    @property
    def active_associations(self) -> list[Association]:
        """Return a list of the AE's active
        :class:`~pynetdicom.association.Association` threads.

        Returns
        -------
        list of Association
            A list of all active association threads, both requestors and
            acceptors.
        """
        threads = threading.enumerate()
        t_assocs = [tt for tt in threads if isinstance(tt, Association)]

        return [tt for tt in t_assocs if tt.ae == self]

    def add_requested_context(
        self,
        abstract_syntax: str | UID,
        transfer_syntax: TSyntaxType = None,
    ) -> None:
        """Add a :doc:`presentation context</user/presentation_requestor>` to be
        proposed when requesting an association.

        When an SCU sends an association request to a peer it includes a list
        of presentation contexts it would like the peer to support. This
        method adds a single
        :class:`~pynetdicom.presentation.PresentationContext` to the list of
        the SCU's requested contexts.

        Only 128 presentation contexts can be included in the association
        request. Multiple presentation contexts may be requested with the
        same abstract syntax.

        To remove a requested context or one or more of its transfer syntaxes
        see the :meth:`remove_requested_context` method.

        Parameters
        ----------
        abstract_syntax : str | pydicom.uid.UID
            The abstract syntax of the presentation context to request.
        transfer_syntax :  str/pydicom.uid.UID or list of str/pydicom.uid.UID
            The transfer syntax(es) to request (default:
            :attr:`~pynetdicom._globals.DEFAULT_TRANSFER_SYNTAXES`).

        Raises
        ------
        ValueError
            If 128 requested presentation contexts have already been added.

        Examples
        --------
        Add a requested presentation context for *Verification SOP Class* with
        the default transfer syntaxes by using its UID value.

        >>> from pynetdicom import AE
        >>> ae = AE()
        >>> ae.add_requested_context('1.2.840.10008.1.1')
        >>> print(ae.requested_contexts[0])
        Abstract Syntax: Verification SOP Class
        Transfer Syntax(es):
            =Implicit VR Little Endian
            =Explicit VR Little Endian
            =Explicit VR Big Endian

        Add a requested presentation context for *Verification SOP Class* with
        the default transfer syntaxes by using the inbuilt
        :class:`~pynetdicom.sop_class.Verification` object.

        >>> from pynetdicom import AE
        >>> from pynetdicom.sop_class import Verification
        >>> ae = AE()
        >>> ae.add_requested_context(Verification)

        Add a requested presentation context for *Verification SOP Class* with
        a transfer syntax of *Implicit VR Little Endian*.

        >>> from pydicom.uid import ImplicitVRLittleEndian
        >>> from pynetdicom import AE
        >>> from pynetdicom.sop_class import Verification
        >>> ae = AE()
        >>> ae.add_requested_context(Verification, ImplicitVRLittleEndian)
        >>> print(ae.requested_contexts[0])
        Abstract Syntax: Verification SOP Class
        Transfer Syntax(es):
            =Implicit VR Little Endian

        Add two requested presentation contexts for *Verification SOP Class*
        using different transfer syntaxes for each.

        >>> from pydicom.uid import (
        ...     ImplicitVRLittleEndian, ExplicitVRLittleEndian, ExplicitVRBigEndian
        ... )
        >>> from pynetdicom import AE
        >>> from pynetdicom.sop_class import Verification
        >>> ae = AE()
        >>> ae.add_requested_context(
        ...     Verification, [ImplicitVRLittleEndian, ExplicitVRBigEndian]
        ... )
        >>> ae.add_requested_context(Verification, ExplicitVRLittleEndian)
        >>> len(ae.requested_contexts)
        2
        >>> print(ae.requested_contexts[0])
        Abstract Syntax: Verification SOP Class
        Transfer Syntax(es):
            =Implicit VR Little Endian
            =Explicit VR Big Endian
        >>> print(ae.requested_contexts[1])
        Abstract Syntax: Verification SOP Class
        Transfer Syntax(es):
            =Explicit VR Little Endian

        References
        ----------

        * DICOM Standard, Part 8,
          :dcm:`Section 7.1.1.13<part08.html#sect_7.1.1.13>`
        * DICOM Standard, Part 8,
          :dcm:`Table 9-18<part08.html#table_9-18>`
        """
        if transfer_syntax is None:
            transfer_syntax = DEFAULT_TRANSFER_SYNTAXES

        if len(self.requested_contexts) >= 128:
            raise ValueError(
                "Failed to add the requested presentation context as there "
                "are already the maximum allowed number of requested contexts"
            )

        # Allow single transfer syntax values for convenience
        if isinstance(transfer_syntax, str):
            transfer_syntax = [transfer_syntax]

        context = PresentationContext()
        context.abstract_syntax = UID(abstract_syntax)
        context.transfer_syntax = [UID(syntax) for syntax in transfer_syntax]

        self._requested_contexts.append(context)

    def add_supported_context(
        self,
        abstract_syntax: str | UID,
        transfer_syntax: TSyntaxType = None,
        scu_role: bool | None = None,
        scp_role: bool | None = None,
    ) -> None:
        """Add a :doc:`presentation context</user/presentation_acceptor>` to be
        supported when accepting association requests.

        When an association request is received from a peer it supplies a list
        of presentation contexts that it would like the SCP to support. This
        method adds a :class:`~pynetdicom.presentation.PresentationContext`
        to the list of the SCP's supported contexts.

        Where the abstract syntax is already supported the transfer syntaxes
        will be extended by those supplied in `transfer_syntax`. To remove
        a supported context or one or more of its transfer syntaxes see the
        :meth:`remove_supported_context` method.

        Parameters
        ----------
        abstract_syntax : str, pydicom.uid.UID
            The abstract syntax of the presentation context to be supported.
        transfer_syntax :  str/pydicom.uid.UID or list of str/pydicom.uid.UID
            The transfer syntax(es) to support (default:
            :attr:`~pynetdicom._globals.DEFAULT_TRANSFER_SYNTAXES`).
        scu_role : bool or None, optional
            If the association requestor includes an
            :doc:`SCP/SCU Role Selection Negotiation</user/presentation_role_selection>`
            item for this context then:

            * If ``None`` then ignore the proposal (if either `scp_role` or
              `scu_role` is ``None`` then both are assumed to be) and use the
              default roles.
            * If ``True`` accept the proposed SCU role
            * If ``False`` reject the proposed SCU role
        scp_role : bool or None, optional
            If the association requestor includes an
            :doc:`SCP/SCU Role Selection Negotiation</user/presentation_role_selection>`
            item for this context then:

            * If ``None`` then ignore the proposal (if either `scp_role` or
              `scu_role` is ``None`` then both are assumed to be) and use the
              default roles.
            * If ``True`` accept the proposed SCP role
            * If ``False`` reject the proposed SCP role

        Examples
        --------
        Add support for presentation contexts with an abstract syntax of
        *Verification SOP Class* and the default transfer syntaxes by using
        its UID value.

        >>> from pynetdicom import AE
        >>> ae = AE()
        >>> ae.add_supported_context('1.2.840.10008.1.1')
        >>> print(ae.supported_contexts[0])
        Abstract Syntax: Verification SOP Class
        Transfer Syntax(es):
            =Implicit VR Little Endian
            =Explicit VR Little Endian
            =Explicit VR Big Endian

        Add support for presentation contexts with an abstract syntax of
        *Verification SOP Class* and the default transfer syntaxes by using the
        inbuilt :class:`~pynetdicom.sop_class.Verification` object.

        >>> from pynetdicom import AE
        >>> from pynetdicom.sop_class import Verification
        >>> ae = AE()
        >>> ae.add_supported_context(Verification)

        Add support for presentation contexts with an abstract syntax of
        *Verification SOP Class* and a transfer syntax of *Implicit VR Little
        Endian*.

        >>> from pydicom.uid import ImplicitVRLittleEndian
        >>> from pynetdicom import AE
        >>> from pynetdicom.sop_class import Verification
        >>> ae = AE()
        >>> ae.add_supported_context(Verification, ImplicitVRLittleEndian)
        >>> print(ae.supported_contexts[0])
        Abstract Syntax: Verification SOP Class
        Transfer Syntax(es):
            =Implicit VR Little Endian

        Add support for presentation contexts with an abstract syntax of
        *Verification SOP Class* and transfer syntaxes of *Implicit VR Little
        Endian* and *Explicit VR Big Endian* and then update the context to
        also support *Explicit VR Little Endian*.

        >>> from pydicom.uid import (
        ...     ImplicitVRLittleEndian, ExplicitVRLittleEndian, ExplicitVRBigEndian
        ... )
        >>> from pynetdicom import AE
        >>> from pynetdicom.sop_class import Verification
        >>> ae = AE()
        >>> ae.add_supported_context(
        ...     Verification, [ImplicitVRLittleEndian, ExplicitVRBigEndian]
        ... )
        >>> ae.add_supported_context(Verification, ExplicitVRLittleEndian)
        >>> print(ae.supported_contexts[0])
        Abstract Syntax: Verification SOP Class
        Transfer Syntax(es):
            =Implicit VR Little Endian
            =Explicit VR Big Endian
            =Explicit VR Little Endian

        Add support for *CT Image Storage* and if the association requestor
        includes an SCP/SCU Role Selection Negotiation item for *CT Image
        Storage* requesting the SCU and SCP roles then accept the proposal.

        >>> from pynetdicom import AE
        >>> from pynetdicom.sop_class import CTImageStorage
        >>> ae = AE()
        >>> ae.add_supported_context(CTImageStorage, scu_role=True, scp_role=True)
        """
        if transfer_syntax is None:
            transfer_syntax = DEFAULT_TRANSFER_SYNTAXES  # list[str]

        abstract_syntax = UID(abstract_syntax)

        if not isinstance(scu_role, (type(None), bool)):
            raise TypeError("`scu_role` must be None or bool")

        if not isinstance(scp_role, (type(None), bool)):
            raise TypeError("`scp_role` must be None or bool")

        # For convenience allow single transfer syntax values
        if isinstance(transfer_syntax, str):
            transfer_syntax = [transfer_syntax]

        transfer_syntax = [UID(ts) for ts in transfer_syntax]

        # If the abstract syntax is already supported then update the transfer
        #   syntaxes
        if abstract_syntax in self._supported_contexts:
            context = self._supported_contexts[abstract_syntax]
            for syntax in transfer_syntax:
                context.add_transfer_syntax(syntax)
            context.scu_role = None or scu_role
            context.scp_role = None or scp_role
        else:
            context = PresentationContext()
            context.abstract_syntax = abstract_syntax
            context.transfer_syntax = transfer_syntax  # type: ignore
            context.scu_role = None or scu_role
            context.scp_role = None or scp_role

            self._supported_contexts[abstract_syntax] = context

    @property
    def ae_title(self) -> str:
        """Get or set the AE title as :class:`str`.

        .. versionchanged:: 2.0

            `ae_title` should be set using :class:`str` and returns
            :class:`str` rather than :class:`bytes`

        Parameters
        ----------
        value : str
            The AE title to use for the local Application Entity as an ASCII
            string.

        Returns
        -------
        str
            The local Application Entity's AE title.
        """
        return self._ae_title

    @ae_title.setter
    def ae_title(self, value: str) -> None:
        """Set the AE title using :class:`str`."""
        if isinstance(value, bytes):
            warnings.warn(
                "The use of bytes with 'ae_title' is deprecated, use an ASCII "
                "str instead",
                DeprecationWarning,
            )
            value = decode_bytes(value)

        self._ae_title = cast(str, set_ae(value, "ae_title", False, False))

    def associate(
        self,
        addr: str | tuple[str, int, int],
        port: int,
        contexts: ListCXType | None = None,
        ae_title: str = "ANY-SCP",
        max_pdu: int = DEFAULT_MAX_LENGTH,
        ext_neg: list[_UI] | None = None,
        bind_address: tuple[str, int] | tuple[str, int, int, int] | None = None,
        tls_args: tuple[SSLContext, str] | None = None,
        evt_handlers: list[EventHandlerType] | None = None,
    ) -> Association:
        """Request an association with a remote AE.

        An :class:`~pynetdicom.association.Association` thread is returned
        whether or not the association is accepted and should be checked using
        :attr:`Association.is_established
        <pynetdicom.association.Association.is_established>`
        before sending any messages. The returned thread will only be running
        if the association was established.

        .. versionchanged:: 2.0

            `ae_title` should now be :class:`str`

        .. versionchanged:: 3.0

            `addr` can be either an IPv4 or IPv6 address str such as ``"192.168.1.2"``
            or ``"::1"``, or a tuple containing an IPv6 address such as
            ``("2a00:1450:4001:81c::200e", 0, 0)`` where the last two items are the
            `flowinfo` and `scope_id`.

        .. versionchanged:: 3.0

            `bind_address` can be either a tuple containing IPv4 or IPv6 address
            str and port number such as ``("192.168.1.2", 11112)`` or ``("::1", 0)``,
            or a tuple containing an IPv6 address str and port number such as
            ``("2a00:1450:4001:81c::200e", 11112, 0, 0)`` where the last two items are
            the `flowinfo` and `scope_id`.

        Parameters
        ----------
        addr : str | tuple[str, int, int]
            The peer AE's TCP/IP address, as one of the following:

            * `str`: An IPv4 or IPv6 address, such as ``"192.168.1.2"`` or
              ``"2a00:1450:4001:81c::200e"``. If using IPv6 then `flowinfo` and
              `scope_id` will default to ``0``.
            * `tuple[str, int, int]`: An IPv6 address as ``(address, flowinfo,
              scope_id)``.
        port : int
            The peer AE's listen port number.
        contexts : list of presentation.PresentationContext, optional
            The presentation contexts that will be requested by the AE for
            support by the peer. If not used then the presentation contexts in
            the :attr:`requested_contexts` property will be requested instead.
        ae_title : str, optional
            The peer's AE title, will be used as the *Called AE Title*
            parameter value (default ``'ANY-SCP'``).
        max_pdu : int, optional
            The :dcm:`maximum PDV receive size<part08/chapter_D.html#sect_D.1>`
            in bytes to use when negotiating the association (default
            ``16832``). A value of ``0`` means the PDV size is unlimited.
        ext_neg : list of UserInformation objects, optional
            A list containing optional extended negotiation items:

            .. currentmodule:: pynetdicom.pdu_primitives

            * :class:`AsynchronousOperationsWindowNegotiation` (0 or 1 item)
            * :class:`~SCP_SCU_RoleSelectionNegotiation` (0 to N items)
            * :class:`~SOPClassCommonExtendedNegotiation` (0 to N items)
            * :class:`~SOPClassExtendedNegotiation` (0 to N items)
            * :class:`~UserIdentityNegotiation` (0 or 1 item)
        bind_address : tuple[str, int] | tuple[str, int, int, int], optional
            The address to bind the association's communication socket to. For IPv4 or
            IPv6 this may be the ``(str: address, int: port)``, with the `flowinfo` and
            `scope_id` defaulting to ``0`` for IPv6. Alternatively for IPv6 this
            may be the ``(str: address, int: port, int: flowinfo, int: scope_id)``.
            Default: ``("", 0)`` if `addr` uses IPv4 or ``("::0", 0)`` if `addr`
            uses IPv6.
        tls_args : 2-tuple, optional
            If TLS is required then this should be a 2-tuple containing a
            (`ssl_context`, `server_hostname`), where `ssl_context` is the
            :class:`ssl.SSLContext` instance to use to wrap the client socket
            and `server_hostname` is the value to use for the corresponding
            keyword argument in :meth:`~ssl.SSLContext.wrap_socket`. If no
            `tls_args` is supplied then TLS will not be used (default).
        evt_handlers : list of 2- or 3-tuple, optional
            A list of (*event*, *handler*) or (*event*, *handler*, *args*),
            where `event` is an ``evt.EVT_*`` event tuple, `handler` is a
            callable function that will be bound to the event and `args` is a
            :class:`list` of objects that will be passed to `handler` as
            optional extra arguments. At a minimum, `handler` should take an
            :class:`~pynetdicom.events.Event` parameter and may return or yield
            objects depending on the exact event that the handler is bound to.
            For more information see the :ref:`documentation<user_events>`.

        Returns
        -------
        assoc : association.Association
            If the association was established then a running
            :class:`~pynetdicom.association.Association` thread, otherwise
            returns a thread that hasn't been started.

        Raises
        ------
        RuntimeError
            If called with no requested presentation contexts (i.e. `contexts`
            has not been supplied and
            :attr:`~pynetdicom.ae.ApplicationEntity.requested_contexts` is
            empty).
        """
        if not isinstance(addr, (str, tuple)):
            raise TypeError("'addr' must be str or tuple[str, int, int]")

        if isinstance(addr, tuple) and (
            not isinstance(addr[0], str)
            or not isinstance(addr[1], int)
            or not isinstance(addr[2], int)
        ):
            raise TypeError("'addr' must be str or tuple[str, int, int]")

        if not isinstance(port, int):
            raise TypeError("'port' must be int")

        remote_address = AddressInformation.from_addr_port(addr, port)

        if bind_address is None:
            bind_address = ("", 0)
            if remote_address.address_family == socket.AF_INET6:
                bind_address = ("::0", 0)

        if not isinstance(bind_address, (tuple, list)):
            raise TypeError(
                "'bind_address' must be tuple[str, int] or tuple[str, int, int, int]"
            )

        if (
            len(bind_address) not in (2, 4)
            or not isinstance(bind_address[0], str)
            or not isinstance(bind_address[1], int)
        ):
            raise TypeError(
                "'bind_address' must be tuple[str, int] or tuple[str, int, int, int]"
            )

        if len(bind_address) == 4 and (
            not isinstance(bind_address[2], int) or not isinstance(bind_address[3], int)
        ):
            raise TypeError(
                "'bind_address' must be tuple[str, int] or tuple[str, int, int, int]"
            )

        local_address = AddressInformation.from_tuple(bind_address)

        # Association
        assoc = Association(self, MODE_REQUESTOR)

        # Set the thread name
        timestamp = datetime.strftime(datetime.now(), "%Y%m%d%H%M%S")
        assoc.name = f"RequestorThread@{timestamp}"

        # Setup the association's communication socket
        sock = self._create_socket(assoc, local_address, tls_args)
        assoc.set_socket(sock)

        # Association Acceptor object -> remote AE
        # `ae_title` validation is performed by the ServiceUser
        assoc.acceptor.ae_title = ae_title
        assoc.acceptor.address_info = remote_address

        # Association Requestor object -> local AE
        # Nominal address info - will get updated by AssociationSocket.connect()
        assoc.requestor.address_info = local_address
        assoc.requestor.ae_title = self.ae_title
        assoc.requestor.maximum_length = max_pdu
        assoc.requestor.implementation_class_uid = self.implementation_class_uid
        assoc.requestor.implementation_version_name = self.implementation_version_name
        for item in ext_neg or []:
            assoc.requestor.add_negotiation_item(item)

        # Requestor's presentation contexts
        contexts = contexts or self.requested_contexts
        self._validate_requested_contexts(contexts)

        # PS3.8 Table 9.11, an A-ASSOCIATE-RQ must contain one or more
        #   Presentation Context items
        if not contexts:
            raise RuntimeError(
                "At least one requested presentation context is required "
                "before associating with a peer"
            )

        # Set using a copy of the original to play nicely
        contexts = deepcopy(contexts)

        # Add the context IDs
        for ii, context in enumerate(contexts):
            context.context_id = 2 * ii + 1

        assoc.requestor.requested_contexts = contexts

        # Bind events to the handlers
        evt_handlers = evt_handlers or []
        for evt_hh_args in evt_handlers:
            assoc.bind(*evt_hh_args)

        # Send an A-ASSOCIATE request to the peer and start negotiation
        assoc.request()

        # If the result of the negotiation was acceptance then start up
        #   the Association thread
        if assoc.is_established:
            assoc.start()

        return assoc

    def _create_socket(
        self,
        assoc: Association,
        address: AddressInformation,
        tls_args: tuple[SSLContext, str] | None,
    ) -> AssociationSocket:
        """Create an :class:`~pynetdicom.transport.AssociationSocket` for the
        current association.
        """
        # Creates and binds to `address` but doesn't connect
        sock = AssociationSocket(assoc, address=address)
        sock.tls_args = tls_args
        return sock

    @property
    def connection_timeout(self) -> float | None:
        """Get or set the connection timeout (in seconds).

        .. versionadded:: 2.0

        Parameters
        ----------
        value : int, float or None
            The maximum amount of time (in seconds) to wait for a TCP
            connection to be established. A value of ``None`` (default) means
            no timeout. The value is passed to `socket.settimeout()
            <https://docs.python.org/3/library/
            socket.html#socket.socket.settimeout>`_
            and is only used during the connection phase of an association
            request.
        """
        return self._connection_timeout

    @connection_timeout.setter
    def connection_timeout(self, value: float | None) -> None:
        """Set the connection timeout."""
        if value is None:
            self._connection_timeout = None
        # Explicitly excluding zero - this would make the socket non-blocking
        elif isinstance(value, (int, float)) and value > 0:
            self._connection_timeout = value
        else:
            LOGGER.warning("connection_timeout set to None")
            self._connection_timeout = None

        for assoc in self.active_associations:
            assoc.connection_timeout = self.connection_timeout

    @property
    def dimse_timeout(self) -> float | None:
        """Get or set the DIMSE timeout (in seconds).

        Parameters
        ----------
        value : int, float or None
            The maximum amount of time (in seconds) to wait for DIMSE related
            messages. A value of ``None`` means no timeout (default: ``30``).
        """
        return self._dimse_timeout

    @dimse_timeout.setter
    def dimse_timeout(self, value: float | None) -> None:
        """Set the DIMSE timeout in seconds."""
        if value is None:
            self._dimse_timeout = None
        elif isinstance(value, (int, float)) and value >= 0:
            self._dimse_timeout = value
        else:
            LOGGER.warning("dimse_timeout set to 30 s")
            self._dimse_timeout = 30

        for assoc in self.active_associations:
            assoc.dimse_timeout = self.dimse_timeout

    @property
    def implementation_class_uid(self) -> UID:
        """Get or set the *Implementation Class UID* as
        :class:`~pydicom.uid.UID`.

        Parameters
        ----------
        value : str or pydicom.uid.UID
            The association request's *Implementation Class UID* value.
        """
        return self._implementation_uid

    @implementation_class_uid.setter
    def implementation_class_uid(self, value: str) -> None:
        """Set the *Implementation Class UID* used in association requests."""
        uid = cast(UID, set_uid(value, "implementation_class_uid", False, False, True))
        # Enforce conformance on users
        if not uid.is_valid:
            raise ValueError(f"Invalid 'implementation_class_uid' value '{uid}'")

        self._implementation_uid = uid

    @property
    def implementation_version_name(self) -> str | None:
        """Get or set the *Implementation Version Name* as :class:`str`.

        Parameters
        ----------
        value : str or None
            If set then an *Implementation Version Name* item with the
            corresponding value will be added to the association request,
            otherwise no item will be sent.

        Returns
        -------
        str or None
            The set *Implementation Version Name*.
        """
        return self._implementation_version

    @implementation_version_name.setter
    def implementation_version_name(self, value: str | None) -> None:
        """Set the *Implementation Version Name*"""
        # We allow None, but not an empty str
        if isinstance(value, str) and not value:
            raise ValueError(
                "Invalid 'implementation_version_name' value - must not be "
                "an empty str"
            )

        self._implementation_version = set_ae(value, "implementation_version_name")

    def make_server(
        self,
        address: tuple[str, int] | tuple[str, int, int, int],
        ae_title: str | None = None,
        contexts: ListCXType | None = None,
        ssl_context: SSLContext | None = None,
        evt_handlers: list[EventHandlerType] | None = None,
        server_class: Type[_T] | None = None,
        **kwargs: Any,
    ) -> _T | ThreadedAssociationServer:
        """Return an association server.

        Allows the use of a custom association server class.

        Accepts the same parameters as :meth:`start_server`. Additional keyword
        parameters are passed to the constructor of `server_class`.

        .. versionchanged:: 2.0

            `ae_title` should now be :class:`str`

        .. versionchanged:: 3.0

            `address` can be either a tuple containing IPv4 or IPv6 address
            str and port number such as ``("192.168.1.2", 11112)`` or ``("::1", 0)``,
            or a tuple containing an IPv6 address str and port number such as
            ``("2a00:1450:4001:81c::200e", 11112, 0, 0)`` where the last two items are
            the `flowinfo` and `scope_id`.

        Parameters
        ----------
        server_class : object, optional
            The class object to use when creating the server. Defaults to
            :class:`~pynetdicom.transport.AssociationServer` if not used.

        Returns
        -------
        object
            The object passed via `server_class` or the
            :class:`~pynetdicom.transport.AssociationServer`.
        """
        # If the SCP has no supported SOP Classes then there's no point
        #   running as a server
        unrestricted = _config.UNRESTRICTED_STORAGE_SERVICE
        if not unrestricted and not contexts and not self.supported_contexts:
            msg = "No supported Presentation Contexts have been defined"
            LOGGER.error(msg)
            raise ValueError(msg)

        ae_title = ae_title if ae_title else self.ae_title
        if isinstance(ae_title, bytes):
            warnings.warn(
                "The use of bytes with 'ae_title' is deprecated, use an "
                "ASCII str instead",
                DeprecationWarning,
            )
            ae_title = decode_bytes(ae_title)

        ae_title = cast(str, set_ae(ae_title, "ae_title", False, False))
        contexts = contexts or self.supported_contexts

        bad_contexts = []
        for cx in contexts:
            roles = (cx.scu_role, cx.scp_role)
            if None in roles and roles != (None, None):
                bad_contexts.append(cx.abstract_syntax)

        if bad_contexts:
            msg = (
                "The following presentation contexts have inconsistent "
                "scu_role/scp_role values (if one is None, both must be):\n  "
            )
            msg += "\n  ".join([str(cx) for cx in bad_contexts])
            raise ValueError(msg)

        server_class = server_class or AssociationServer  # type: ignore[assignment]

        return server_class(  # type: ignore
            self,
            address,
            ae_title,
            contexts,
            ssl_context,
            evt_handlers=evt_handlers or [],
            **kwargs,
        )

    @property
    def maximum_associations(self) -> int:
        """Get or set the number of maximum simultaneous associations as
        :class:`int`.

        Parameters
        ----------
        value : int
            The maximum number of simultaneous associations requested by remote
            AEs. This does not include the number of associations
            requested by the local AE (default ``10``).
        """
        return self._maximum_associations

    @maximum_associations.setter
    def maximum_associations(self, value: int) -> None:
        """Set the number of maximum associations."""
        if isinstance(value, int) and value >= 1:
            self._maximum_associations = value
        else:
            LOGGER.warning("maximum_associations set to 1")
            self._maximum_associations = 1

    @property
    def maximum_pdu_size(self) -> int:
        """Get or set the maximum PDU size accepted by the AE as :class:`int`.

        Parameters
        ----------
        value : int
            The maximum PDU receive size in bytes. A value of ``0`` means the
            PDU size is unlimited (default: ``16382``). Increasing this value
            or setting it to unlimited is an effective way of improving the
            throughput when sending large amounts of data due to the reduced
            DIMSE messaging overhead.
        """
        return self._maximum_pdu_size

    @maximum_pdu_size.setter
    def maximum_pdu_size(self, value: int) -> None:
        """Set the maximum PDU size."""
        # Bounds and type checking of the received maximum length of the
        #   variable field of P-DATA-TF PDUs (in bytes)
        #   * Must be numerical, greater than or equal to 0 (0 indicates
        #       no maximum length (PS3.8 Annex D.1.1)
        if value >= 0:
            self._maximum_pdu_size = value
        else:
            LOGGER.warning(f"maximum_pdu_size set to {DEFAULT_MAX_LENGTH}")

    @property
    def network_timeout(self) -> float | None:
        """Get or set the network timeout (in seconds).

        Parameters
        ----------
        value : int, float or None
            The maximum amount of time (in seconds) to wait for network
            messages. A value of ``None`` means no timeout (default: ``60``).
        """
        return self._network_timeout

    @network_timeout.setter
    def network_timeout(self, value: float | None) -> None:
        """Set the network timeout."""
        if value is None:
            self._network_timeout = None
        elif isinstance(value, (int, float)) and value >= 0:
            self._network_timeout = value
        else:
            LOGGER.warning("network_timeout set to 60 s")
            self._network_timeout = 60

        for assoc in self.active_associations:
            assoc.network_timeout = self.network_timeout

    def remove_requested_context(
        self,
        abstract_syntax: str | UID,
        transfer_syntax: TSyntaxType = None,
    ) -> None:
        """Remove a requested presentation context.

        Depending on the supplied parameters one of the following will occur:

        * `abstract_syntax` alone -  all contexts with a matching abstract
          syntax all be removed.
        * `abstract_syntax` and `transfer_syntax` -  for all contexts with a
          matching abstract syntax; if the supplied `transfer_syntax` list
          contains all of the context's requested transfer syntaxes then the
          entire context will be removed. Otherwise only the matching transfer
          syntaxes will be removed from the context (and the context will
          remain with one or more transfer syntaxes).

        Parameters
        ----------
        abstract_syntax : str, pydicom.uid.UID or sop_class.SOPClass
            The abstract syntax of the presentation context you wish to stop
            requesting when sending association requests.
        transfer_syntax : UID str or list of UID str, optional
            The transfer syntax(es) you wish to stop requesting. If a list of
            str/UID then only those transfer syntaxes specified will no longer
            be requested. If not specified then the abstract syntax and all
            associated transfer syntaxes will no longer be requested (default).

        Examples
        --------
        Remove all requested presentation contexts with an abstract syntax of
        *Verification SOP Class* using its UID value.

        >>> from pynetdicom import AE
        >>> ae = AE()
        >>> ae.add_requested_context('1.2.840.10008.1.1')
        >>> print(ae.requested_contexts[0])
        Abstract Syntax: Verification SOP Class
        Transfer Syntax(es):
            =Implicit VR Little Endian
            =Explicit VR Little Endian
            =Explicit VR Big Endian
        >>> ae.remove_requested_context('1.2.840.10008.1.1')
        >>> len(ae.requested_contexts)
        0

        Remove all requested presentation contexts with an abstract syntax of
        *Verification SOP Class* using the inbuilt
        :class:`~pynetdicom.sop_class.Verification` object.

        >>> from pynetdicom import AE
        >>> from pynetdicom.sop_class import Verification
        >>> ae = AE()
        >>> ae.add_requested_context(Verification)
        >>> ae.remove_requested_context(Verification)
        >>> len(ae.requested_contexts)
        0

        For all requested presentation contexts with an abstract syntax of
        *Verification SOP Class*, stop requesting a transfer syntax of
        *Implicit VR Little Endian*. If a presentation context exists which
        only has a single *Implicit VR Little Endian* transfer syntax then
        it will be completely removed, otherwise it will be kept with its
        remaining transfer syntaxes.

        Presentation context has only a single matching transfer syntax:

        >>> from pydicom.uid import ImplicitVRLittleEndian
        >>> from pynetdicom import AE
        >>> from pynetdicom.sop_class import Verification
        >>> ae.add_requested_context(Verification, ImplicitVRLittleEndian)
        >>> print(ae.requested_contexts[0])
        Abstract Syntax: Verification SOP Class
        Transfer Syntax(es):
            =Implicit VR Little Endian
        >>> ae.remove_requested_context(Verification, ImplicitVRLittleEndian)
        >>> len(ae.requested_contexts)
        0

        Presentation context has at least one remaining transfer syntax:

        >>> from pydicom.uid import ImplicitVRLittleEndian, ExplicitVRLittleEndian
        >>> from pynetdicom import AE
        >>> from pynetdicom.sop_class import Verification
        >>> ae = AE()
        >>> ae.add_requested_context(Verification)
        >>> print(ae.requested_contexts[0])
        Abstract Syntax: Verification SOP Class
        Transfer Syntax(es):
            =Implicit VR Little Endian
            =Explicit VR Little Endian
            =Explicit VR Big Endian
        >>> ae.remove_requested_context(
        ...     Verification, [ImplicitVRLittleEndian, ExplicitVRLittleEndian]
        ... )
        >>> print(ae.requested_contexts[0])
        Abstract Syntax: Verification SOP Class
        Transfer Syntax(es):
            =Explicit VR Big Endian
        """
        abstract_syntax = UID(abstract_syntax)

        # Get all the current requested contexts with the same abstract syntax
        matching_contexts = [
            cntx
            for cntx in self.requested_contexts
            if cntx.abstract_syntax == abstract_syntax
        ]

        if isinstance(transfer_syntax, str):
            transfer_syntax = [transfer_syntax]

        if transfer_syntax is None:
            # If no transfer_syntax then remove the context completely
            for context in matching_contexts:
                self._requested_contexts.remove(context)
        else:
            for context in matching_contexts:
                for tsyntax in transfer_syntax:
                    if tsyntax in context.transfer_syntax:
                        context.transfer_syntax.remove(UID(tsyntax))

                # Only if all transfer syntaxes have been removed then
                #   remove the context
                if not context.transfer_syntax:
                    self._requested_contexts.remove(context)

    def remove_supported_context(
        self,
        abstract_syntax: str | UID,
        transfer_syntax: TSyntaxType = None,
    ) -> None:
        """Remove a supported presentation context.

        Depending on the supplied parameters one of the following will occur:

        * `abstract_syntax` alone - the entire supported context will be
          removed.
        * `abstract_syntax` and `transfer_syntax` -  If the supplied
          `transfer_syntax` list contains all of the context's supported
          transfer syntaxes then the entire context will be removed.
          Otherwise only the matching transfer syntaxes will be removed from
          the context (and the context will remain with one or more transfer
          syntaxes).

        Parameters
        ----------
        abstract_syntax : str, pydicom.uid.UID or sop_class.SOPClass
            The abstract syntax of the presentation context you wish to stop
            supporting.
        transfer_syntax : UID str or list of UID str, optional
            The transfer syntax(es) you wish to stop supporting. If a list of
            str/UID then only those transfer syntaxes specified will no longer
            be supported. If not specified then the abstract syntax and all
            associated transfer syntaxes will no longer be supported (default).

        Examples
        --------
        Remove the supported presentation context with an abstract syntax of
        *Verification SOP Class* using its UID value.

        >>> from pynetdicom import AE
        >>> ae = AE()
        >>> ae.add_supported_context('1.2.840.10008.1.1')
        >>> print(ae.supported_contexts[0])
        Abstract Syntax: Verification SOP Class
        Transfer Syntax(es):
            =Implicit VR Little Endian
            =Explicit VR Little Endian
            =Explicit VR Big Endian
        >>> ae.remove_supported_context('1.2.840.10008.1.1')
        >>> len(ae.supported_contexts)
        0

        Remove the supported presentation context with an abstract syntax of
        *Verification SOP Class* using the inbuilt
        :class:`~pynetdicom.sop_class.Verification` object.

        >>> from pynetdicom import AE, VerificationPresentationContexts
        >>> from pynetdicom.sop_class import Verification
        >>> ae = AE()
        >>> ae.supported_contexts = VerificationPresentationContexts
        >>> ae.remove_supported_context(Verification)

        For the presentation contexts with an abstract syntax of
        *Verification SOP Class*, stop supporting the *Implicit VR Little
        Endian* transfer syntax. If the presentation context only has the
        single *Implicit VR Little Endian* transfer syntax then it will be
        completely removed, otherwise it will be kept with the remaining
        transfer syntaxes.

        Presentation context has only a single matching transfer syntax:

        >>> from pydicom.uid import ImplicitVRLittleEndian
        >>> from pynetdicom import AE
        >>> from pynetdicom.sop_class import Verification
        >>> ae = AE()
        >>> ae.add_supported_context(Verification, ImplicitVRLittleEndian)
        >>> print(ae.supported_contexts[0])
        Abstract Syntax: Verification SOP Class
        Transfer Syntax(es):
            =Implicit VR Little Endian
        >>> ae.remove_supported_context(Verification, ImplicitVRLittleEndian)
        >>> len(ae.supported_contexts)
        0

        Presentation context has at least one remaining transfer syntax:

        >>> from pydicom.uid import ImplicitVRLittleEndian, ExplicitVRLittleEndian
        >>> from pynetdicom import AE
        >>> from pynetdicom.sop_class import Verification
        >>> ae = AE()
        >>> ae.add_supported_context(Verification)
        >>> print(ae.supported_contexts[0])
        Abstract Syntax: Verification SOP Class
        Transfer Syntax(es):
            =Implicit VR Little Endian
            =Explicit VR Little Endian
            =Explicit VR Big Endian
        >>> ae.remove_supported_context(
        ...     Verification, [ImplicitVRLittleEndian, ExplicitVRLittleEndian]
        ... )
        >>> print(ae.supported_contexts[0])
        Abstract Syntax: Verification SOP Class
        Transfer Syntax(es):
            =Explicit VR Big Endian
        """
        abstract_syntax = UID(abstract_syntax)

        if isinstance(transfer_syntax, str):
            transfer_syntax = [transfer_syntax]

        # Check abstract syntax is actually present
        #   we don't warn if not present because by not being present its not
        #   supported and hence the user's intent has been satisfied
        if abstract_syntax in self._supported_contexts:
            if transfer_syntax is None:
                # If no transfer_syntax then remove the context completely
                del self._supported_contexts[abstract_syntax]
            else:
                # If transfer_syntax then only remove matching syntaxes
                context = self._supported_contexts[abstract_syntax]
                for tsyntax in transfer_syntax:
                    if tsyntax in context.transfer_syntax:
                        context.transfer_syntax.remove(UID(tsyntax))

                # Only if all transfer syntaxes have been removed then remove
                #   the context
                if not context.transfer_syntax:
                    del self._supported_contexts[abstract_syntax]

    @property
    def requested_contexts(self) -> ListCXType:
        """Get or set a list of the requested
        :class:`~pynetdicom.presentation.PresentationContext` items.

        Examples
        --------
        Set the requested presentation contexts using an inbuilt list of
        service specific :class:`~pynetdicom.presentation.PresentationContext`
        items:

        >>> from pynetdicom import AE, StoragePresentationContexts
        >>> ae = AE()
        >>> ae.requested_contexts = StoragePresentationContexts

        Set the requested presentation contexts using a :class:`list` of
        :class:`~pynetdicom.presentation.PresentationContext` items:

        >>> from pydicom.uid import ImplicitVRLittleEndian
        >>> from pynetdicom import AE
        >>> from pynetdicom.presentation import PresentationContext
        >>> context = PresentationContext()
        >>> context.abstract_syntax = '1.2.840.10008.1.1'
        >>> context.transfer_syntax = [ImplicitVRLittleEndian]
        >>> ae = AE()
        >>> ae.requested_contexts = [context]
        >>> print(ae.requested_contexts[0])
        Abstract Syntax: Verification SOP Class
        Transfer Syntax(es):
            =Implicit VR Little Endian

        Parameters
        ----------
        contexts : list of PresentationContext
            The presentation contexts to request when acting as an SCU.

        Raises
        ------
        ValueError
            If trying to add more than 128 requested presentation contexts.

        See Also
        --------
        ApplicationEntity.add_requested_context
            Add a single presentation context to the requested contexts using
            an abstract syntax and (optionally) a list of transfer syntaxes.
        """
        return self._requested_contexts

    @requested_contexts.setter
    def requested_contexts(self, contexts: ListCXType) -> None:
        """Set the requested presentation contexts."""
        if not contexts:
            self._requested_contexts = []
            return

        self._validate_requested_contexts(contexts)

        for context in contexts:
            self.add_requested_context(
                cast(UID, context.abstract_syntax), context.transfer_syntax
            )

    @property
    def require_called_aet(self) -> bool:
        """Get or set whether the *Called AE Title* must match the AE title.

        When an association request is received the value of the 'Called AE
        Title' supplied by the peer will be compared with the set values and
        if none match the association will be rejected. If the set value
        is an empty list then the *Called AE Title* will not be checked.

        Parameters
        ----------
        require_match : bool
            If ``True`` then any association requests that supply a
            *Called AE Title* value that does not match :attr:`ae_title`
            will be rejected. If ``False`` (default) then all association
            requests will be accepted (unless rejected for other reasons).
        """
        return self._require_called_aet

    @require_called_aet.setter
    def require_called_aet(self, require_match: bool) -> None:
        """Set whether the *Called AE Title* must match the AE title."""
        self._require_called_aet = require_match

    @property
    def require_calling_aet(self) -> list[str]:
        """Get or set the required calling AE title as a list of :class:`str`.

        When an association request is received the value of the *Calling AE
        Title* supplied by the peer will be compared with the set value and
        if none match the association will be rejected. If the set value
        is an empty list then the *Calling AE Title* will not be checked.

        .. versionchanged:: 2.0

            `ae_titles` should now be a :class:`list` of :class:`str`

        Parameters
        ----------
        ae_titles : list of str
            If not empty then any association requests that supply a
            *Calling AE Title* value that does not match one of the values in
            *ae_titles* will be rejected. If an empty list (default) then all
            association requests will be accepted (unless rejected for other
            reasons).
        """
        return self._require_calling_aet

    @require_calling_aet.setter
    def require_calling_aet(self, ae_titles: list[str]) -> None:
        """Set the required calling AE title."""
        if any([isinstance(v, bytes) for v in ae_titles]):
            warnings.warn(
                "The use of a list of bytes with 'require_calling_aet' is "
                "deprecated, use a list of ASCII str instead",
                DeprecationWarning,
            )

        values = []
        for v in ae_titles:
            if isinstance(v, bytes):
                v = decode_bytes(v)

            values.append(cast(str, set_ae(v, "require_calling_aet", False, False)))

        self._require_calling_aet = values

    def shutdown(self) -> None:
        """Stop any active association servers and threads."""
        for assoc in self.active_associations:
            assoc.abort()

        # This is a bit hackish: server.shutdown() removes the server
        #   from `_servers` so we need to workaround this
        for server in self._servers[:]:
            server.shutdown()

        self._servers = []

    def start_server(
        self,
        address: tuple[str, int] | tuple[str, int, int, int],
        block: bool = True,
        ssl_context: SSLContext | None = None,
        evt_handlers: list[EventHandlerType] | None = None,
        ae_title: str | None = None,
        contexts: ListCXType | None = None,
    ) -> ThreadedAssociationServer | None:
        """Start the AE as an association *acceptor*.

        If set to non-blocking then a running
        :class:`~pynetdicom.transport.ThreadedAssociationServer`
        instance will be returned. This can be stopped using
        :meth:`~pynetdicom.transport.AssociationServer.shutdown`.

        .. versionchanged:: 2.0

            `ae_title` should now be :class:`str`

        .. versionchanged:: 3.0

            `address` can be either a tuple containing IPv4 or IPv6 address
            str and port number such as ``("192.168.1.2", 11112)`` or ``("::1", 0)``,
            or a tuple containing an IPv6 address str and port number such as
            ``("2a00:1450:4001:81c::200e", 11112, 0, 0)`` where the last two items are
            the `flowinfo` and `scope_id`.

        Parameters
        ----------
        address : tuple[str, int] | tuple[str, int, int, int]
            The host IP address and port number to use when listening for incoming
            association requests.

            * `tuple[str, int]`: An IPv4 or IPv6 address and port number, such as
              ``("192.168.1.2", 104)`` or ``("2a00:1450:4001:81c::200e", 11112)``.
              If using IPv6 then `flowinfo` and `scope_id` will default to ``0``.
            * `tuple[str, int, int, int]`: An IPv6 address as ``(address, port,
              flowinfo, scope_id)``.
        block : bool, optional
            If ``True`` (default) then the server will be blocking, otherwise
            it will start the server in a new thread and be non-blocking.
        ssl_context : ssl.SSLContext, optional
            If TLS is required then this should the :class:`ssl.SSLContext`
            instance to use to wrap the client sockets, otherwise if ``None``
            then no TLS will be used (default).
        evt_handlers : list of 2- or 3-tuple, optional
            A list of (*event*, *handler*) or (*event*, *handler*, *args*),
            where `event` is an ``evt.EVT_*`` event tuple, `handler` is a
            callable function that will be bound to the event and `args` is a
            :class:`list` of objects that will be passed to `handler` as
            optional extra arguments. At a minimum, `handler` should take an
            :class:`~pynetdicom.events.Event` parameter and may return or yield
            objects depending on the exact event that the handler is bound to.
            For more information see the :ref:`documentation<user_events>`.
        ae_title : str, optional
            The AE title to use for the local SCP. If this keyword parameter
            is not used then the AE title from the :attr:`ae_title` property
            will be used instead (default).
        contexts : list of presentation.PresentationContext, optional
            The presentation contexts that will be supported by the SCP. If
            not used then the presentation contexts in the
            :attr:`supported_contexts` property will be used instead (default).

        Returns
        -------
        transport.ThreadedAssociationServer or None
            If `block` is ``False`` then returns the server instance, otherwise
            returns ``None``.
        """
        if block:
            # Blocking server
            server = self.make_server(
                address,
                ae_title=ae_title,
                contexts=contexts,
                ssl_context=ssl_context,
                evt_handlers=evt_handlers,
            )
            self._servers.append(server)

            try:
                # **BLOCKING**
                server.serve_forever()
            except KeyboardInterrupt:
                server.shutdown()

            return None

        # Non-blocking server
        timestamp = datetime.strftime(datetime.now(), "%Y%m%d%H%M%S")
        server = self.make_server(
            address,
            ae_title=ae_title,
            contexts=contexts,
            ssl_context=ssl_context,
            evt_handlers=evt_handlers,
            server_class=ThreadedAssociationServer,
        )

        thread = threading.Thread(
            target=make_target(server.serve_forever), name=f"AcceptorServer@{timestamp}"
        )
        thread.daemon = True
        thread.start()

        self._servers.append(server)

        return server

    def __str__(self) -> str:
        """Prints out the attribute values and status for the AE"""
        s = [""]
        s.append(f"Application Entity {self.ae_title}")

        s.append("")
        s.append("  Requested Presentation Contexts:")
        if not self.requested_contexts:
            s.append("\tNone")
        for context in self.requested_contexts:
            s.append(f"\t{cast(UID, context.abstract_syntax).name}")
            for transfer_syntax in context.transfer_syntax:
                s.append(f"\t\t{transfer_syntax.name}")

        s.append("")
        s.append("  Supported Presentation Contexts:")
        if not self.supported_contexts:
            s.append("\tNone")
        for context in self.supported_contexts:
            s.append(f"\t{cast(UID, context.abstract_syntax).name}")
            for transfer_syntax in context.transfer_syntax:
                s.append(f"\t\t{transfer_syntax.name}")

        s.append("")
        s.append(f"  ACSE timeout: {self.acse_timeout} s")
        s.append(f"  DIMSE timeout: {self.dimse_timeout} s")
        s.append(f"  Network timeout: {self.network_timeout} s")
        s.append(f"  Connection timeout: {self.connection_timeout} s")

        s.append("")
        if self.require_calling_aet != []:
            ae_titles = self.require_calling_aet
            s.append((f"  Required calling AE title(s): {', '.join(ae_titles)}"))
        s.append(f"  Require called AE title: {self.require_called_aet}")
        s.append("")

        # Association information
        s.append(
            f"  Association(s): {len(self.active_associations)}"
            f"/{self.maximum_associations}"
        )

        for assoc in self.active_associations:
            s.append(
                f"\tPeer: {assoc.remote['ae_title']} on "
                f"{assoc.remote['address']}:{assoc.remote['port']}"
            )

        return "\n".join(s)

    @property
    def supported_contexts(self) -> ListCXType:
        """Get or set a list of the supported
        :class:`~pynetdicom.presentation.PresentationContext` items.

        Examples
        --------
        Set the supported presentation contexts using a list of
        ``PresentationContext`` items:

        >>> from pydicom.uid import ImplicitVRLittleEndian
        >>> from pynetdicom import AE
        >>> from pynetdicom.presentation import PresentationContext
        >>> context = PresentationContext()
        >>> context.abstract_syntax = '1.2.840.10008.1.1'
        >>> context.transfer_syntax = [ImplicitVRLittleEndian]
        >>> ae = AE()
        >>> ae.supported_contexts = [context]

        Set the supported presentation contexts using an inbuilt list of
        service specific :class:`~pynetdicom.presentation.PresentationContext`
        items:

        >>> from pynetdicom import AE, StoragePresentationContexts
        >>> ae = AE()
        >>> ae.supported_contexts = StoragePresentationContexts

        Parameters
        ----------
        contexts : list of presentation.PresentationContext
            The presentation contexts to support when acting as an SCP.

        See Also
        --------
        ApplicationEntity.add_supported_context
            Add a single presentation context to the supported contexts using
            an abstract syntax and optionally a list of transfer syntaxes.
        """
        # The supported presentation contexts are stored internally as a dict
        return sorted(
            list(self._supported_contexts.values()),
            key=lambda cx: cast(UID, cx.abstract_syntax),
        )

    @supported_contexts.setter
    def supported_contexts(self, contexts: ListCXType) -> None:
        """Set the supported presentation contexts using a list."""
        if not contexts:
            self._supported_contexts = {}

        for item in contexts:
            if not isinstance(item, PresentationContext):
                raise ValueError(
                    "'contexts' must be a list of PresentationContext items"
                )

            self.add_supported_context(
                cast(UID, item.abstract_syntax), item.transfer_syntax
            )

    @staticmethod
    def _validate_requested_contexts(contexts: ListCXType) -> None:
        """Validate the supplied `contexts`.

        Parameters
        ----------
        contexts : list of presentation.PresentationContext
            The contexts to validate.
        """
        if len(contexts) > 128:
            raise ValueError(
                "The maximum allowed number of requested presentation "
                "contexts is 128"
            )

        invalid = [ii for ii in contexts if not isinstance(ii, PresentationContext)]
        if invalid:
            raise ValueError("'contexts' must be a list of PresentationContext items")
