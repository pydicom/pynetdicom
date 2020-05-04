"""
The main user class, represents a DICOM Application Entity
"""
from copy import deepcopy
from datetime import datetime
import logging
import threading

from pydicom.uid import UID

from pynetdicom.association import Association
from pynetdicom.presentation import PresentationContext
from pynetdicom.transport import (
    AssociationSocket, AssociationServer, ThreadedAssociationServer
)
from pynetdicom.utils import validate_ae_title
from pynetdicom._globals import (
    MODE_REQUESTOR,
    DEFAULT_MAX_LENGTH,
    DEFAULT_TRANSFER_SYNTAXES
)


LOGGER = logging.getLogger('pynetdicom.ae')


class ApplicationEntity(object):
    """Represents a DICOM Application Entity (AE).

    An AE may be a *Service Class Provider* (SCP), a *Service Class User* (SCU)
    or both.

    Attributes
    ----------
    acse_timeout : int or float or None
        The maximum amount of time (in seconds) to wait for association related
        messages. A value of ``None`` means no timeout. (default: ``30``)
    ae_title : bytes
        The local AE's *AE title*.
    dimse_timeout : int or float or None
        The maximum amount of time (in seconds) to wait for DIMSE related
        messages. A value of ``None`` means no timeout. (default: ``30``)
    network_timeout : int or float or None
        The maximum amount of time (in seconds) to wait for network messages.
        A value of ``None`` means no timeout. (default: ``60``)
    maximum_associations : int
        The maximum number of simultaneous associations requested by remote
        AEs. Note that this does not include the number of associations
        requested by the local AE (default ``10``).
    maximum_pdu_size : int
        The maximum PDU receive size in bytes. A value of ``0`` means the PDU
        size is unlimited (default: ``16382``)
    require_calling_aet : list of bytes
        Association *acceptor* only. If not an empty list, the association
        request's *Calling AE Title* value must match one of the values in
        `require_calling_aet`. If an empty list then no matching will be
        performed (default).
    require_called_aet : bool
        Association *acceptor* only. If ``True``, the association request's
        *Called AE Title* value must match :attr:`ae_title` (default
        ``False``).
    """
    # pylint: disable=too-many-instance-attributes,too-many-public-methods
    def __init__(self, ae_title=b'PYNETDICOM'):
        """Create a new Application Entity.

        Parameters
        ----------
        ae_title : bytes, optional
            The AE title of the Application Entity (default: ``b'PYNETDICOM'``)
        """
        self.ae_title = ae_title

        from pynetdicom import (
            PYNETDICOM_IMPLEMENTATION_UID,
            PYNETDICOM_IMPLEMENTATION_VERSION
        )

        # Default Implementation Class UID and Version Name
        self.implementation_class_uid = PYNETDICOM_IMPLEMENTATION_UID
        self.implementation_version_name = PYNETDICOM_IMPLEMENTATION_VERSION

        # List of PresentationContext
        self._requested_contexts = []
        # {abstract_syntax : PresentationContext}
        self._supported_contexts = {}

        # Default maximum simultaneous associations
        self.maximum_associations = 10

        # Default maximum PDU receive size (in bytes)
        self.maximum_pdu_size = DEFAULT_MAX_LENGTH

        # Default timeouts - None means no timeout
        self.acse_timeout = 30
        self.dimse_timeout = 30
        self.network_timeout = 60

        # Require Calling/Called AE titles to match if value is non-empty str
        self.require_calling_aet = []
        self.require_called_aet = False

        self._servers = []
        self._lock = threading.Lock()

    @property
    def acse_timeout(self):
        """The ACSE timeout value (in seconds)."""
        return self._acse_timeout

    @acse_timeout.setter
    def acse_timeout(self, value):
        """Set the ACSE timeout (in seconds)."""
        # pylint: disable=attribute-defined-outside-init
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
    def active_associations(self):
        """Return a list of the AE's active
        :class:`~pynetdicom.association.Association` threads.

        Returns
        -------
        list of association.Association
            A list of all active association threads, both requestors and
            acceptors.
        """
        threads = threading.enumerate()
        t_assocs = [tt for tt in threads if isinstance(tt, Association)]

        return [tt for tt in t_assocs if tt.ae == self]

    def add_requested_context(self, abstract_syntax, transfer_syntax=None):
        """Add a :ref:`presentation context<user_presentation>` to be
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
        abstract_syntax : str or pydicom.uid.UID
            The abstract syntax of the presentation context to request.
        transfer_syntax :  str/pydicom.uid.UID or list of str/pydicom.uid.UID
            The transfer syntax(es) to request (default: *Implicit VR Little
            Endian*, *Explicit VR Little Endian*, *Explicit VR Big Endian*).

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
        :class:`~pynetdicom.sop_class.VerificationSOPClass` object.

        >>> from pynetdicom import AE
        >>> from pynetdicom.sop_class import VerificationSOPClass
        >>> ae = AE()
        >>> ae.add_requested_context(VerificationSOPClass)

        Add a requested presentation context for *Verification SOP Class* with
        a transfer syntax of *Implicit VR Little Endian*.

        >>> from pydicom.uid import ImplicitVRLittleEndian
        >>> from pynetdicom import AE
        >>> from pynetdicom.sop_class import VerificationSOPClass
        >>> ae = AE()
        >>> ae.add_requested_context(VerificationSOPClass, ImplicitVRLittleEndian)
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
        >>> from pynetdicom.sop_class import VerificationSOPClass
        >>> ae = AE()
        >>> ae.add_requested_context(
        ...     VerificationSOPClass, [ImplicitVRLittleEndian, ExplicitVRBigEndian]
        ... )
        >>> ae.add_requested_context(VerificationSOPClass, ExplicitVRLittleEndian)
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

        abstract_syntax = UID(abstract_syntax)

        # Allow single transfer syntax values for convenience
        if isinstance(transfer_syntax, str):
            transfer_syntax = [transfer_syntax]

        context = PresentationContext()
        context.abstract_syntax = abstract_syntax
        context.transfer_syntax = [UID(syntax) for syntax in transfer_syntax]

        self._requested_contexts.append(context)

    def add_supported_context(self, abstract_syntax, transfer_syntax=None,
                              scu_role=None, scp_role=None):
        """Add a :ref:`presentation context<user_presentation>` to be
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
        abstract_syntax : str, pydicom.uid.UID or sop_class.SOPClass
            The abstract syntax of the presentation context to be supported.
        transfer_syntax :  str/pydicom.uid.UID or list of str/pydicom.uid.UID
            The transfer syntax(es) to support (default: *Implicit VR Little
            Endian*, *Explicit VR Little Endian*, *Explicit VR Big Endian*).
        scu_role : bool or None, optional
            If the association requestor includes an
            :ref:`SCP/SCU Role Selection Negotiation<user_presentation_role>`
            item for this context then:

            * If ``None`` then ignore the proposal (if either `scp_role` or
              `scu_role` is ``None`` then both are assumed to be) and use the
              default roles.
            * If ``True`` accept the proposed SCU role
            * If ``False`` reject the proposed SCU role
        scp_role : bool or None, optional
            If the association requestor includes an
            :ref:`SCP/SCU Role Selection Negotiation<user_presentation_role>`
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
        inbuilt :class:`~pynetdicom.sop_class.VerificationSOPClass` object.

        >>> from pynetdicom import AE
        >>> from pynetdicom.sop_class import VerificationSOPClass
        >>> ae = AE()
        >>> ae.add_supported_context(VerificationSOPClass)

        Add support for presentation contexts with an abstract syntax of
        *Verification SOP Class* and a transfer syntax of *Implicit VR Little
        Endian*.

        >>> from pydicom.uid import ImplicitVRLittleEndian
        >>> from pynetdicom import AE
        >>> from pynetdicom.sop_class import VerificationSOPClass
        >>> ae = AE()
        >>> ae.add_supported_context(VerificationSOPClass, ImplicitVRLittleEndian)
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
        >>> from pynetdicom.sop_class import VerificationSOPClass
        >>> ae = AE()
        >>> ae.add_supported_context(
        ...     VerificationSOPClass, [ImplicitVRLittleEndian, ExplicitVRBigEndian]
        ... )
        >>> ae.add_supported_context(VerificationSOPClass, ExplicitVRLittleEndian)
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
            transfer_syntax = DEFAULT_TRANSFER_SYNTAXES

        abstract_syntax = UID(abstract_syntax)

        if not isinstance(scu_role, (type(None), bool)):
            raise TypeError("`scu_role` must be None or bool")

        if not isinstance(scp_role, (type(None), bool)):
            raise TypeError("`scp_role` must be None or bool")

        # For convenience allow single transfer syntax values
        if isinstance(transfer_syntax, str):
            transfer_syntax = [transfer_syntax]
        transfer_syntax = [UID(syntax) for syntax in transfer_syntax]

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
            context.transfer_syntax = transfer_syntax
            context.scu_role = None or scu_role
            context.scp_role = None or scp_role

            self._supported_contexts[abstract_syntax] = context

    @property
    def ae_title(self):
        """The AE title as length 16 :class:`bytes`."""
        return self._ae_title

    @ae_title.setter
    def ae_title(self, value):
        """Set the AE title using :class:`bytes`.

        Parameters
        ----------
        value : bytes
            The AE title to use for the local Application Entity. Leading and
            trailing spaces are non-significant.
        """
        # pylint: disable=attribute-defined-outside-init
        self._ae_title = validate_ae_title(value)

    def associate(self, addr, port, contexts=None, ae_title=b'ANY-SCP',
                  max_pdu=DEFAULT_MAX_LENGTH, ext_neg=None,
                  bind_address=('', 0), tls_args=None, evt_handlers=None):
        """Request an association with a remote AE.

        An :class:`~pynetdicom.association.Association` thread is returned
        whether or not the association is accepted and should be checked using
        :attr:`Association.is_established
        <pynetdicom.association.Association.is_established>`
        before sending any messages. The returned thread will only be running
        if the association was established.

        .. versionchanged:: 1.2

            Added `bind_address` and `tls_arg` keyword parameters

        .. versionchanged:: 1.3

            Added `evt_handlers` keyword parameter

        .. versionchanged:: 1.5

            `evt_handlers` now takes a list of 2- or 3-tuples

        Parameters
        ----------
        addr : str
            The peer AE's TCP/IP address.
        port : int
            The peer AE's listen port number.
        contexts : list of presentation.PresentationContext, optional
            The presentation contexts that will be requested by the AE for
            support by the peer. If not used then the presentation contexts in
            the :attr:`requested_contexts` property will be requested instead.
        ae_title : bytes, optional
            The peer's AE title, will be used as the *Called AE Title*
            parameter value (default ``b'ANY-SCP'``).
        max_pdu : int, optional
            The maximum PDV receive size in bytes to use when negotiating the
            association (default ``16832``). A value of ``0`` means the PDU
            size is unlimited.
        ext_neg : list of UserInformation objects, optional
            Used if extended association negotiation is required.
        bind_address : 2-tuple, optional
            The (host, port) to bind the Association's communication socket
            to, default ``('', 0)``.
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
            has not been supplied and :attr:`requested_contexts` is empty).
        """
        if not isinstance(addr, str):
            raise TypeError("'addr' must be a valid IPv4 string")

        if not isinstance(port, int):
            raise TypeError("'port' must be a valid port number")

        # Association
        assoc = Association(self, MODE_REQUESTOR)

        # Set the thread name
        timestamp = datetime.strftime(datetime.now(), "%Y%m%d%H%M%S")
        assoc.name = "RequestorThread@{}".format(timestamp)

        # Setup the association's communication socket
        sock = self._create_socket(assoc, bind_address, tls_args)
        assoc.set_socket(sock)

        # Association Acceptor object -> remote AE
        assoc.acceptor.ae_title = validate_ae_title(ae_title)
        assoc.acceptor.address = addr
        assoc.acceptor.port = port

        # Association Requestor object -> local AE
        assoc.requestor.address = sock.get_local_addr()
        assoc.requestor.port = bind_address[1]
        assoc.requestor.ae_title = self.ae_title
        assoc.requestor.maximum_length = max_pdu
        assoc.requestor.implementation_class_uid = (
            self.implementation_class_uid
        )
        assoc.requestor.implementation_version_name = (
            self.implementation_version_name
        )
        for item in (ext_neg or []):
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
        evt_handlers = evt_handlers or {}
        for evt_hh_args in evt_handlers:
            assoc.bind(*evt_hh_args)

        # Send an A-ASSOCIATE request to the peer and start negotiation
        assoc.request()

        # If the result of the negotiation was acceptance then start up
        #   the Association thread
        if assoc.is_established:
            assoc.start()

        return assoc

    def _create_socket(self, assoc, address, tls_args):
        """Create an :class:`~pynetdicom.transport.AssociationSocket` for the current association.

        .. versionadded:: 1.5
        """
        sock = AssociationSocket(assoc, address=address)
        sock.tls_args = tls_args or {}
        return sock

    @property
    def dimse_timeout(self):
        """The DIMSE timeout (in seconds)."""
        return self._dimse_timeout

    @dimse_timeout.setter
    def dimse_timeout(self, value):
        """Set the DIMSE timeout in seconds."""
        # pylint: disable=attribute-defined-outside-init
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
    def implementation_class_uid(self):
        """The current *Implementation Class UID* as :class:`str`."""
        return self._implementation_uid

    @implementation_class_uid.setter
    def implementation_class_uid(self, uid):
        """Set the *Implementation Class UID* used in association requests.

        Parameters
        ----------
        uid : str or pydicom.uid.UID
            The A-ASSOCIATE-RQ's *Implementation Class UID* value.
        """
        uid = UID(uid)
        if uid.is_valid:
            # pylint: disable=attribute-defined-outside-init
            self._implementation_uid = uid

    @property
    def implementation_version_name(self):
        """The current *Implementation Version Name* as :class:`bytes`."""
        return self._implementation_version

    @implementation_version_name.setter
    def implementation_version_name(self, value):
        """Set the *Implementation Version Name* used in association requests.

        Parameters
        ----------
        value : bytes
            The A-ASSOCIATE-RQ's *Implementation Version Name* value.
        """
        # pylint: disable=attribute-defined-outside-init
        self._implementation_version = value

    def make_server(self, address, ae_title=None, contexts=None,
                    ssl_context=None, evt_handlers=None,
                    server_class=None, **kwargs):
        """Return an association server.

        Allows the use of a custom association server class.

        Accepts the same parameters as :meth:`start_server`. Additional keyword
        parameters are passed to the constructor of `server_class`.

        .. versionadded:: 1.5
        """
        # If the SCP has no supported SOP Classes then there's no point
        #   running as a server
        if not contexts and not self.supported_contexts:
            msg = "No supported Presentation Contexts have been defined"
            LOGGER.error(msg)
            raise ValueError(msg)

        if ae_title:
            ae_title = validate_ae_title(ae_title)
        else:
            ae_title = self.ae_title

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
            msg += '\n  '.join(bad_contexts)
            raise ValueError(msg)

        evt_handlers = evt_handlers or {}

        server_class = server_class or AssociationServer
        return server_class(
            self, address, ae_title, contexts, ssl_context,
            evt_handlers=evt_handlers,
            **kwargs
        )

    @property
    def maximum_associations(self):
        """The number of maximum simultaneous associations as :class:`int`."""
        return self._maximum_associations

    @maximum_associations.setter
    def maximum_associations(self, value):
        """Set the number of maximum associations."""
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, int) and value >= 1:
            self._maximum_associations = value
        else:
            LOGGER.warning("maximum_associations set to 1")
            self._maximum_associations = 1

    @property
    def maximum_pdu_size(self):
        """The maximum PDU size accepted by the AE as :class:`int`."""
        return self._maximum_pdu_size

    @maximum_pdu_size.setter
    def maximum_pdu_size(self, value):
        """Set the maximum PDU size."""
        # pylint: disable=attribute-defined-outside-init
        # Bounds and type checking of the received maximum length of the
        #   variable field of P-DATA-TF PDUs (in bytes)
        #   * Must be numerical, greater than or equal to 0 (0 indicates
        #       no maximum length (PS3.8 Annex D.1.1)
        if value >= 0:
            self._maximum_pdu_size = value
        else:
            LOGGER.warning(
                "maximum_pdu_size set to {}".format(DEFAULT_MAX_LENGTH)
            )

    @property
    def network_timeout(self):
        """The network timeout (in seconds)."""
        return self._network_timeout

    @network_timeout.setter
    def network_timeout(self, value):
        """Set the network timeout."""
        # pylint: disable=attribute-defined-outside-init
        if value is None:
            self._network_timeout = None
        elif isinstance(value, (int, float)) and value >= 0:
            self._network_timeout = value
        else:
            LOGGER.warning("network_timeout set to 60 s")
            self._network_timeout = 60

        for assoc in self.active_associations:
            assoc.network_timeout = self.network_timeout

    def remove_requested_context(self, abstract_syntax, transfer_syntax=None):
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
        :class:`~pynetdicom.sop_class.VerificationSOPClass` object.

        >>> from pynetdicom import AE
        >>> from pynetdicom.sop_class import VerificationSOPClass
        >>> ae = AE()
        >>> ae.add_requested_context(VerificationSOPClass)
        >>> ae.remove_requested_context(VerificationSOPClass)
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
        >>> from pynetdicom.sop_class import VerificationSOPClass
        >>> ae.add_requested_context(VerificationSOPClass, ImplicitVRLittleEndian)
        >>> print(ae.requested_contexts[0])
        Abstract Syntax: Verification SOP Class
        Transfer Syntax(es):
            =Implicit VR Little Endian
        >>> ae.remove_requested_context(VerificationSOPClass, ImplicitVRLittleEndian)
        >>> len(ae.requested_contexts)
        0

        Presentation context has at least one remaining transfer syntax:

        >>> from pydicom.uid import ImplicitVRLittleEndian, ExplicitVRLittleEndian
        >>> from pynetdicom import AE
        >>> from pynetdicom.sop_class import VerificationSOPClass
        >>> ae = AE()
        >>> ae.add_requested_context(VerificationSOPClass)
        >>> print(ae.requested_contexts[0])
        Abstract Syntax: Verification SOP Class
        Transfer Syntax(es):
            =Implicit VR Little Endian
            =Explicit VR Little Endian
            =Explicit VR Big Endian
        >>> ae.remove_requested_context(
        ...     VerificationSOPClass, [ImplicitVRLittleEndian, ExplicitVRLittleEndian]
        ... )
        >>> print(ae.requested_contexts[0])
        Abstract Syntax: Verification SOP Class
        Transfer Syntax(es):
            =Explicit VR Big Endian
        """
        abstract_syntax = UID(abstract_syntax)

        # Get all the current requested contexts with the same abstract syntax
        matching_contexts = [
            cntx for cntx in self.requested_contexts
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

    def remove_supported_context(self, abstract_syntax, transfer_syntax=None):
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
        :class:`~pynetdicom.sop_class.VerificationSOPClass` object.

        >>> from pynetdicom import AE, VerificationPresentationContexts
        >>> from pynetdicom.sop_class import VerificationSOPClass
        >>> ae = AE()
        >>> ae.supported_contexts = VerificationPresentationContexts
        >>> ae.remove_supported_context(VerificationSOPClass)

        For the presentation contexts with an abstract syntax of
        *Verification SOP Class*, stop supporting the *Implicit VR Little
        Endian* transfer syntax. If the presentation context only has the
        single *Implicit VR Little Endian* transfer syntax then it will be
        completely removed, otherwise it will be kept with the remaining
        transfer syntaxes.

        Presentation context has only a single matching transfer syntax:

        >>> from pydicom.uid import ImplicitVRLittleEndian
        >>> from pynetdicom import AE
        >>> from pynetdicom.sop_class import VerificationSOPClass
        >>> ae = AE()
        >>> ae.add_supported_context(VerificationSOPClass, ImplicitVRLittleEndian)
        >>> print(ae.supported_contexts[0])
        Abstract Syntax: Verification SOP Class
        Transfer Syntax(es):
            =Implicit VR Little Endian
        >>> ae.remove_supported_context(VerificationSOPClass, ImplicitVRLittleEndian)
        >>> len(ae.supported_contexts)
        0

        Presentation context has at least one remaining transfer syntax:

        >>> from pydicom.uid import ImplicitVRLittleEndian, ExplicitVRLittleEndian
        >>> from pynetdicom import AE
        >>> from pynetdicom.sop_class import VerificationSOPClass
        >>> ae = AE()
        >>> ae.add_supported_context(VerificationSOPClass)
        >>> print(ae.supported_contexts[0])
        Abstract Syntax: Verification SOP Class
        Transfer Syntax(es):
            =Implicit VR Little Endian
            =Explicit VR Little Endian
            =Explicit VR Big Endian
        >>> ae.remove_supported_context(
        ...     VerificationSOPClass, [ImplicitVRLittleEndian, ExplicitVRLittleEndian]
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
    def requested_contexts(self):
        """A list of the requested
        :class:`~pynetdicom.presentation.PresentationContext` items.

        Returns
        -------
        list of presentation.PresentationContext
            The SCU's requested presentation contexts.
        """
        return self._requested_contexts

    @requested_contexts.setter
    def requested_contexts(self, contexts):
        """Set the requested presentation contexts.

        Parameters
        ----------
        contexts : list of presentation.PresentationContext
            The presentation contexts to request when acting as an SCU.

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
        if not contexts:
            self._requested_contexts = []
            return

        self._validate_requested_contexts(contexts)

        for context in contexts:
            self.add_requested_context(context.abstract_syntax,
                                       context.transfer_syntax)

    @property
    def require_called_aet(self):
        """Whether the *Called AE Title* must match the AE title."""
        return self._require_called_aet

    @require_called_aet.setter
    def require_called_aet(self, require_match):
        """Set whether the *Called AE Title* must match the AE title.

        When an association request is received the value of the 'Called AE
        Title' supplied by the peer will be compared with the set values and
        if none match the association will be rejected. If the set value
        is an empty list then the *Called AE Title* will not be checked.

        .. versionchanged:: 1.1

            `require_match` changed to ``bool``

        Parameters
        ----------
        require_match : bool
            If ``True`` then any association requests that supply a
            *Called AE Title* value that does not match :attr:`ae_title`
            will be rejected. If ``False`` (default) then all association
            requests will be accepted (unless rejected for other reasons).
        """
        # pylint: disable=attribute-defined-outside-init
        self._require_called_aet = require_match

    @property
    def require_calling_aet(self):
        """The required calling AE title as a list of :class:`bytes`."""
        return self._require_calling_aet

    @require_calling_aet.setter
    def require_calling_aet(self, ae_titles):
        """Set the required calling AE title.

        When an association request is received the value of the *Calling AE
        Title* supplied by the peer will be compared with the set value and
        if none match the association will be rejected. If the set value
        is an empty list then the *Calling AE Title* will not be checked.

        .. versionchanged:: 1.1

            `ae_titles` changed to ``list`` of ``bytes``

        Parameters
        ----------
        ae_titles : list of bytes
            If not empty then any association requests that supply a
            *Calling AE Title* value that does not match one of the values in
            *ae_titles* will be rejected. If an empty list (default) then all
            association requests will be accepted (unless rejected for other
            reasons).
        """
        # pylint: disable=attribute-defined-outside-init
        self._require_calling_aet = [
            validate_ae_title(aet) for aet in ae_titles
        ]

    def start_server(self, address, block=True, ssl_context=None,
                     evt_handlers=None, ae_title=None, contexts=None):
        """Start the AE as an association *acceptor*.

        .. versionadded:: 1.2

        If set to non-blocking then a running
        :class:`~pynetdicom.transport.ThreadedAssociationServer`
        instance will be returned. This can be stopped using
        :meth:`~pynetdicom.transport.AssociationServer.shutdown`.

        .. versionchanged:: 1.3

            Added `evt_handlers` keyword parameter

        .. versionchanged:: 1.4

            Added `ae_title` and `contexts` keyword parameters

        .. versionchanged:: 1.5

            `evt_handlers` now takes a list of 2- or 3-tuples

        Parameters
        ----------
        address : 2-tuple
            The (`host`, `port`) to use when listening for incoming association
            requests.
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
        ae_title : bytes, optional
            The AE title to use for the local SCP. Leading and trailing spaces
            are non-significant. If this keyword parameter is not used then
            the AE title from the :attr:`ae_title` property will be used
            instead (default).
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
                address, ae_title=ae_title, contexts=contexts, ssl_context=ssl_context,
                evt_handlers=evt_handlers,
            )
            self._servers.append(server)

            try:
                # **BLOCKING**
                server.serve_forever()
            except KeyboardInterrupt:
                server.shutdown()
        else:
            # Non-blocking server
            timestamp = datetime.strftime(datetime.now(), "%Y%m%d%H%M%S")
            server = self.make_server(
                address, ae_title=ae_title, contexts=contexts, ssl_context=ssl_context,
                evt_handlers=evt_handlers, server_class=ThreadedAssociationServer,
            )

            thread = threading.Thread(
                target=server.serve_forever,
                name="AcceptorServer@{}".format(timestamp)
            )
            thread.daemon = True
            thread.start()

            self._servers.append(server)

            return server

    def shutdown(self):
        """Stop any active association servers and threads.

        .. versionadded:: 1.2
        """
        for assoc in self.active_associations:
            assoc.abort()

        # This is a bit hackish: server.shutdown() deletes the server
        #   from `_servers` so we need to workaround this
        original = self._servers[:]
        for server in original:
            server.shutdown()

        self._servers = []

    def __str__(self):
        """ Prints out the attribute values and status for the AE """
        str_out = "\n"
        str_out += "Application Entity '{0!s}'\n".format(self.ae_title)

        str_out += "\n"
        str_out += "  Requested Presentation Contexts:\n"
        if not self.requested_contexts:
            str_out += "\tNone\n"
        for context in self.requested_contexts:
            str_out += "\t{0!s}\n".format(context.abstract_syntax.name)
            for transfer_syntax in context.transfer_syntax:
                str_out += "\t\t{0!s}\n".format(transfer_syntax.name)

        str_out += "\n"
        str_out += "  Supported Presentation Contexts:\n"
        if not self.supported_contexts:
            str_out += "\tNone\n"
        for context in self.supported_contexts:
            str_out += "\t{0!s}\n".format(context.abstract_syntax.name)
            for transfer_syntax in context.transfer_syntax:
                str_out += "\t\t{0!s}\n".format(transfer_syntax.name)

        str_out += "\n"
        str_out += "  ACSE timeout: {0!s} s\n".format(self.acse_timeout)
        str_out += "  DIMSE timeout: {0!s} s\n".format(self.dimse_timeout)
        str_out += "  Network timeout: {0!s} s\n".format(self.network_timeout)

        str_out += "\n"
        if self.require_calling_aet != []:
            ae_titles = [
                aet.decode('ascii') for aet in self.require_calling_aet
            ]
            str_out += "  Required calling AE title(s): {0!s}\n" \
                       .format(', '.join(ae_titles))
        str_out += "  Require called AE title: {0!s}\n" \
                   .format(self.require_called_aet)

        str_out += "\n"

        # Association information
        str_out += '  Association(s): {0!s}/{1!s}\n' \
                   .format(len(self.active_associations),
                           self.maximum_associations)

        for assoc in self.active_associations:
            str_out += '\tPeer: {0!s} on {1!s}:{2!s}\n' \
                       .format(assoc.remote['ae_title'],
                               assoc.remote['address'],
                               assoc.remote['port'])

        return str_out

    @property
    def supported_contexts(self):
        """A list of the supported
        :class:`~pynetdicom.presentation.PresentationContext` items.

        Returns
        -------
        list of presentation.PresentationContext
            The SCP's supported presentation contexts, ordered by abstract
            syntax.
        """
        # The supported presentation contexts are stored internally as a dict
        contexts = sorted(list(self._supported_contexts.values()),
                          key=lambda cntx: cntx.abstract_syntax)
        return contexts

    @supported_contexts.setter
    def supported_contexts(self, contexts):
        """Set the supported presentation contexts using a list.

        Parameters
        ----------
        contexts : list of presentation.PresentationContext
            The presentation contexts to support when acting as an SCP.

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

        See Also
        --------
        ApplicationEntity.add_supported_context
            Add a single presentation context to the supported contexts using
            an abstract syntax and optionally a list of transfer syntaxes.
        """
        if not contexts:
            self._supported_contexts = {}

        for item in contexts:
            if not isinstance(item, PresentationContext):
                raise ValueError(
                    "'contexts' must be a list of PresentationContext items"
                )

            self.add_supported_context(item.abstract_syntax,
                                       item.transfer_syntax)

    @staticmethod
    def _validate_requested_contexts(contexts):
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

        invalid = [
            ii for ii in contexts if not isinstance(ii, PresentationContext)
        ]
        if invalid:
            raise ValueError(
                "'contexts' must be a list of PresentationContext items"
            )
