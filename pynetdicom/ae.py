"""
The main user class, represents a DICOM Application Entity
"""
from copy import deepcopy
from datetime import datetime
import logging
import select
import socket
from struct import pack
import threading
import time
import warnings

from pydicom.uid import UID

from pynetdicom.association import Association
from pynetdicom.presentation import PresentationContext
from pynetdicom.transport import (
    AssociationSocket, AssociationServer, ThreadedAssociationServer
)
from pynetdicom.utils import validate_ae_title
from pynetdicom._globals import (
    MODE_REQUESTOR,
    MODE_ACCEPTOR,
    DEFAULT_MAX_LENGTH,
    DEFAULT_TRANSFER_SYNTAXES
)


def setup_logger():
    """Setup the logger."""
    logger = logging.getLogger('pynetdicom')
    handler = logging.StreamHandler()
    logger.setLevel(logging.WARNING)
    formatter = logging.Formatter('%(levelname).1s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


LOGGER = setup_logger()


class ApplicationEntity(object):
    """Represents a DICOM Application Entity (AE).

    An AE may be a *Service Class Provider* (SCP), a *Service Class User* (SCU)
    or both.

    Attributes
    ----------
    acse_timeout : int or float or None
        The maximum amount of time (in seconds) to wait for association related
        messages. A value of ``None`` means no timeout. (default: 30)
    address : str
        The local AE's TCP/IP address. Deprecated and will be removed in v1.3.
    ae_title : bytes
        The local AE's AE title.
    bind_addr : str
        The network interface to listen to (default: all available network
        interfaces on the machine). This parameter is deprecated and will be
        removed in v1.3. Use the ``address`` parameter for ``start_server()``
        and the ``bind_address`` keyword parameter for ``associate()`` instead.
    dimse_timeout : int or float or None
        The maximum amount of time (in seconds) to wait for DIMSE related
        messages. A value of ``None`` means no timeout. (default: 30)
    local_socket : socket.socket
        The socket used for connections with peer AEs when acting as the
        association acceptor. Deprecated and will be removed in v1.3.
    network_timeout : int or float or None
        The maximum amount of time (in seconds) to wait for network messages.
        A value of ``None`` means no timeout. (default: 60)
    maximum_associations : int
        The maximum number of simultaneous associations requested by remote
        AEs. Note that this does not include the number of associations
        requested by the local AE (default 10).
    maximum_pdu_size : int
        The maximum PDU receive size in bytes. A value of 0 means there is no
        maximum size (default: 16382)
    port : int
        The local AE's listen port number when acting as an SCP or connection
        port when acting as an SCU. A value of 0 indicates that the operating
        system should choose the port. This parameter is deprecated and will
        be removed in v1.3. Use the ``address`` parameter for
        ``start_server()`` and the ``bind_address`` keyword parameter for
        ``associate()`` instead.
    require_calling_aet : list of bytes
        If not an empty list, the association request's *Calling AE Title*
        value must match one of the values in `require_calling_aet`. If an
        empty list then no matching will be performed (default). (Association
        acceptor only).
    require_called_aet : bool
        If True, the association request's *Called AE Title* value
        must match AE.ae_title (default False). (Association acceptor only).
    """
    # pylint: disable=too-many-instance-attributes,too-many-public-methods
    def __init__(self, ae_title=b'PYNETDICOM', port=0):
        """Create a new Application Entity.

        Parameters
        ----------
        ae_title : bytes, optional
            The AE title of the Application Entity (default: ``b'PYNETDICOM'``)
        port : int, optional
            The port number to listen for association requests when acting as
            an SCP and to use when requesting an association as an SCU. When
            set to 0 the OS will use the first available port (default ``0``).
            This parameter is deprecated and will be removed in v1.3. Use
            the ``address`` parameter for ``start_server()`` and the
            ``bind_address`` keyword parameter for ``associate()`` instead.
        """
        self.ae_title = ae_title

        from pynetdicom import (
            PYNETDICOM_IMPLEMENTATION_UID,
            PYNETDICOM_IMPLEMENTATION_VERSION
        )

        # Default Implementation Class UID and Version Name
        self.implementation_class_uid = PYNETDICOM_IMPLEMENTATION_UID
        self.implementation_version_name = PYNETDICOM_IMPLEMENTATION_VERSION

        # TODO: remove in v1.3
        self.address = socket.gethostbyname(socket.gethostname())
        # TODO: remove in v1.3
        if port != 0:
            warnings.warn(
                "The `port` keyword parameter for AE() is deprecated and will "
                "be removed in v1.3. Use the `address` parameter for "
                "AE.start_server() or the `bind_address` keyword parameter "
                "for AE.associate() instead",
                DeprecationWarning
            )
        self.port = port
        # TODO: remove in v1.3
        self._bind_addr = ''

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

        # TODO: remove in v1.3
        self.local_socket = None

        self._servers = []

        # Used to terminate AE when running as an SCP
        # TODO: remove in v1.3
        self._quit = False

    @property
    def acse_timeout(self):
        """Return the ACSE timeout value."""
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
        """Return a list of the AE's active Associations threads.

        Returns
        -------
        list of threading.Thread
            A list of all active association threads, both requestors and
            acceptors.
        """
        threads = threading.enumerate()
        t_assocs = [tt for tt in threads if isinstance(tt, Association)]

        return [tt for tt in t_assocs if tt.ae == self]

    def add_requested_context(self, abstract_syntax, transfer_syntax=None):
        """Add a Presentation Context to be proposed when sending Association
        requests.

        When an SCU sends an Association request to a peer it includes a list
        of presentation contexts it would like the peer to support [1]_. This
        method adds a single
        :py:class:`PresentationContext
        <pynetdicom.presentation.PresentationContext>`
        to the list of the SCU's requested contexts.

        Only 128 presentation contexts can be included in the association
        request [2]_. Multiple presentation contexts may be requested with the
        same abstract syntax.

        To remove a requested context or one or more of its transfer syntaxes
        see the ``remove_requested_context`` method.

        Parameters
        ----------
        abstract_syntax : str or pydicom.uid.UID
            The abstract syntax of the presentation context to request.
        transfer_syntax :  str/pydicom.uid.UID or list of str/pydicom.uid.UID
            The transfer syntax(es) to request (default: Implicit VR Little
            Endian, Explicit VR Little Endian, Explicit VR Big Endian).

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
        `VerificationSOPClass` object.

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
        >>> ae.add_requested_context(VerificationSOPClass,
        ...                          ImplicitVRLittleEndian)
        >>> print(ae.requested_contexts[0])
        Abstract Syntax: Verification SOP Class
        Transfer Syntax(es):
            =Implicit VR Little Endian

        Add two requested presentation contexts for *Verification SOP Class*
        using different transfer syntaxes for each.

        >>> from pydicom.uid import (
        ...     ImplicitVRLittleEndian, ExplicitVRLittleEndian,
        ...     ExplicitVRBigEndian
        ... )
        >>> from pynetdicom import AE
        >>> from pynetdicom.sop_class import VerificationSOPClass
        >>> ae = AE()
        >>> ae.add_requested_context(VerificationSOPClass,
        ...                          [ImplicitVRLittleEndian,
        ...                           ExplicitVRBigEndian])
        >>> ae.add_requested_context(VerificationSOPClass,
        ...                          ExplicitVRLittleEndian)
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
        .. [1] DICOM Standard, Part 8, `Section 7.1.1.13 <http://dicom.nema.org/medical/dicom/current/output/html/part08.html#sect_7.1.1.13>`_
        .. [2] DICOM Standard, Part 8, `Table 9-18 <http://dicom.nema.org/medical/dicom/current/output/html/part08.html#table_9-18>`_
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
        """Add a supported presentation context.

        When an Association request is received from a peer it supplies a list
        of presentation contexts that it would like the SCP to support. This
        method adds a `PresentationContext` to the list of the SCP's
        supported contexts.

        Where the abstract syntax is already supported the transfer syntaxes
        will be extended by the those supplied in `transfer_syntax`. To remove
        a supported context or one or more of its transfer syntaxes see the
        ``remove_supported_context`` method.

        Parameters
        ----------
        abstract_syntax : str, pydicom.uid.UID or sop_class.SOPClass
            The abstract syntax of the presentation context to be supported.
        transfer_syntax :  str/pydicom.uid.UID or list of str/pydicom.uid.UID
            The transfer syntax(es) to support (default: Implicit VR Little
            Endian, Explicit VR Little Endian, Explicit VR Big Endian).
        scu_role : bool or None, optional
            If the association requestor includes an SCP/SCU Role Selection
            Negotiation item for this context then:

            * If None then ignore the proposal (if either `scp_role` or
              `scu_role` is None then both are assumed to be) and use the
              default roles.
            * If True accept the proposed SCU role
            * If False reject the proposed SCU role
        scp_role : bool or None, optional
            If the association requestor includes an SCP/SCU Role Selection
            Negotiation item for this context then:

            * If None then ignore the proposal (if either `scp_role` or
              `scu_role` is None then both are assumed to be) and use the
              default roles.
            * If True accept the proposed SCP role
            * If False reject the proposed SCP role

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
        inbuilt `VerificationSOPClass` object.

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
        >>> ae.add_supported_context(VerificationSOPClass,
        ...                          ImplicitVRLittleEndian)
        >>> print(ae.supported_contexts[0])
        Abstract Syntax: Verification SOP Class
        Transfer Syntax(es):
            =Implicit VR Little Endian

        Add support for presentation contexts with an abstract syntax of
        *Verification SOP Class* and transfer syntaxes of *Implicit VR Little
        Endian* and *Explicit VR Big Endian* and then update the context to
        also support *Explicit VR Little Endian*.

        >>> from pydicom.uid import (
        ...     ImplicitVRLittleEndian, ExplicitVRLittleEndian,
        ...     ExplicitVRBigEndian
        ... )
        >>> from pynetdicom import AE
        >>> from pynetdicom.sop_class import VerificationSOPClass
        >>> ae = AE()
        >>> ae.add_supported_context(VerificationSOPClass,
        ...                         [ImplicitVRLittleEndian,
        ...                          ExplicitVRBigEndian])
        >>> ae.add_supported_context(VerificationSOPClass,
        ...                          ExplicitVRLittleEndian)
        >>> print(ae.supported_contexts[0])
        Abstract Syntax: Verification SOP Class
        Transfer Syntax(es):
            =Implicit VR Little Endian
            =Explicit VR Little Endian
            =Explicit VR Big Endian

        Add support for CTImageStorage and if the association requestor
        includes an SCP/SCU Role Selection Negotiation item for CT Image
        Storage requesting the SCU and SCP roles then accept the proposal.

        >>> from pynetdicom import AE
        >>> from pynetdicom.sop_class import CTImageStorage
        >>> ae = AE()
        >>> ae.add_supported_context(
        ...     CTImageStorage, scu_role=True, scp_role=True
        ... )
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
        """Get the AE title."""
        return self._ae_title

    @ae_title.setter
    def ae_title(self, value):
        """Set the AE title.

        Parameters
        ----------
        value : bytes
            The AE title to use for the local Application Entity. Leading and
            trailing spaces are non-significant.
        """
        # pylint: disable=attribute-defined-outside-init
        try:
            self._ae_title = validate_ae_title(value)
        except:
            raise

    # TODO: refactor in v1.3
    def associate(self, addr, port, contexts=None, ae_title=b'ANY-SCP',
                  max_pdu=DEFAULT_MAX_LENGTH, ext_neg=None, bind_address=None,
                  tls_args=None):
        """Request an Association with a remote AE.

        The Association thread is returned whether or not the association is
        accepted and should be checked using ``Association.is_established``
        before sending any messages. The returned thread will only be running
        if the association was established.

        Parameters
        ----------
        addr : str
            The peer AE's TCP/IP address.
        port : int
            The peer AE's listen port number.
        contexts : list of presentation.PresentationContext, optional
            The presentation contexts that will be requested by the AE for
            support by the peer. If not used then the presentation contexts in
            the `AE.requested_contexts` property will be requested instead.
        ae_title : bytes, optional
            The peer's AE title, will be used as the 'Called AE Title'
            parameter value (default b'ANY-SCP').
        max_pdu : int, optional
            The maximum PDV receive size in bytes to use when negotiating the
            association (default 16832).
        ext_neg : list of UserInformation objects, optional
            Used if extended association negotiation is required.
        bind_address : 2-tuple, optional
            The (host, port) to bind the Association's communication socket
            to. If not used then defaults to (AE.bind_addr, AE.port). After
            v1.3 it will default to ('', 0).
        tls_args : 2-tuple, optional
            If TLS is required then this should be a 2-tuple containing a
            (ssl_context, `server_hostname`), where ssl_context is the
            ssl.SSLContext instance to use to wrap the client socket and
            `server_hostname` is the value to use for the corresponding
            keyword parameter in ``SSLContext.wrap_sockets()``. If no
            `tls_args` is supplied then TLS will not be used (default).

        Returns
        -------
        assoc : association.Association
            If the association was established then a running Association
            thread, otherwise returns a thread that hasn't been started.

        Raises
        ------
        RuntimeError
            If called with no requested presentation contexts (i.e. `contexts`
            has not been supplied and ``ApplicationEntity.requested_contexts``
            is empty).
        """
        if not isinstance(addr, str):
            raise TypeError("'addr' must be a valid IPv4 string")

        if not isinstance(port, int):
            raise TypeError("'port' must be a valid port number")

        # AssociationSocket binding
        if bind_address is None:
            # Deprecated, after v1.3 this will be ('', 0)
            bind_address = (self.bind_addr, self.port)

        # Association
        assoc = Association(self, MODE_REQUESTOR)

        # Set the thread name
        timestamp = datetime.strftime(datetime.now(), "%Y%m%d%H%M%S")
        assoc.name = "RequestorThread@{}".format(timestamp)

        # Setup the association's communication socket
        sock = AssociationSocket(assoc, address=bind_address)
        sock.tls_args = tls_args or {}
        assoc.set_socket(sock)

        # Association Acceptor object -> remote AE
        assoc.acceptor.ae_title = validate_ae_title(ae_title)
        assoc.acceptor.address = addr
        assoc.acceptor.port = port

        # Association Requestor object -> local AE
        assoc.requestor.address = socket.gethostbyname(socket.gethostname())
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
        if contexts is None:
            contexts = self.requested_contexts
        else:
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

        # Send an A-ASSOCIATE request to the peer and start negotiation
        assoc.request()

        # If the result of the negotiation was acceptance then start up
        #   the Association thread
        if assoc.is_established:
            assoc.start()

        return assoc

    # TODO: remove in v1.3
    @property
    def bind_addr(self):
        """Return the `bind_addr`, deprecated and will be removd in v1.3."""
        return self._bind_addr

    @bind_addr.setter
    def bind_addr(self, addr):
        """Set the `bind_addr`, deprecated and will be removd in v1.3."""
        warnings.warn(
            "The `bind_addr` property is deprecated and will "
            "be removed in v1.3. Use the `address` parameter for "
            "AE.start_server() or the `bind_address` keyword parameter "
            "for AE.associate() instead",
            DeprecationWarning
        )
        self._bind_addr = addr

    # TODO: remove in v1.3
    def _bind_socket(self):
        """Set up and bind a socket for use with the SCP."""
        # The socket to listen for connections on, port is always specified
        # AF_INET: IPv4, SOCK_STREAM: TCP socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # SOL_SOCKET: the level, SO_REUSEADDR: allow reuse of a port
        #   stuck in TIME_WAIT, 1: set SO_REUSEADDR to 1
        # This must be called prior to socket.bind()
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if self.network_timeout is not None:
            timeout_seconds = int(self.network_timeout)
            timeout_microsec = int(self.network_timeout % 1 * 1000)
            sock.setsockopt(
                socket.SOL_SOCKET,
                socket.SO_RCVTIMEO,
                pack('ll', timeout_seconds, timeout_microsec)
            )

        # Bind the socket to an address and port
        #   If self.bind_addr is '' then the socket is reachable by any
        #   address the machine may have, otherwise is visible only on that
        #   address
        sock.bind((self.bind_addr, self.port))

        # Listen for connections made to the socket
        # socket.listen() says to queue up to as many as N connect requests
        #   before refusing outside connections
        sock.listen(5)

        return sock

    @property
    def dimse_timeout(self):
        """Get the DIMSE timeout."""
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
            assoc.dimse.dimse_timeout = self.dimse_timeout

    # TODO: remove in v1.3
    def _handle_connection(self, client_socket):
        """Start a new Association thread to handle the connection request.

        Parameters
        ----------
        client_socket : socket.socket
            The socket handling to the connection to the peer.
        """
        # Create a new Association
        assoc = Association(self, MODE_ACCEPTOR)

        # Association Acceptor object -> local AE
        assoc.acceptor.maximum_length = self.maximum_pdu_size
        assoc.acceptor.ae_title = self.ae_title
        assoc.acceptor.address = self.address
        assoc.acceptor.port = self.port
        assoc.acceptor.implementation_class_uid = (
            self.implementation_class_uid
        )
        assoc.acceptor.implementation_version_name = (
            self.implementation_version_name
        )
        assoc.acceptor.supported_contexts = deepcopy(
            self.supported_contexts
        )

        # Association Requestor object -> remote AE
        assoc.requestor.address = client_socket.getpeername()[0]
        assoc.requestor.port = client_socket.getpeername()[1]

        assoc.set_socket(AssociationSocket(assoc, client_socket))

        assoc.start()

    @property
    def implementation_class_uid(self):
        """Return the current Implementation Class UID."""
        return self._implementation_uid

    @implementation_class_uid.setter
    def implementation_class_uid(self, uid):
        """Set the Implementation Class UID used in Association requests.

        Parameters
        ----------
        uid : str or pydicom.uid.UID
            The A-ASSOCIATE-RQ's Implementation Class UID value.
        """
        uid = UID(uid)
        if uid.is_valid:
            # pylint: disable=attribute-defined-outside-init
            self._implementation_uid = uid

    @property
    def implementation_version_name(self):
        """Return the current Implementation Version Name."""
        return self._implementation_version

    @implementation_version_name.setter
    def implementation_version_name(self, value):
        """Set the Implementation Version Name used in Association requests.

        Parameters
        ----------
        value : bytes
            The A-ASSOCIATE-RQ's Implementation Version Name value.
        """
        # pylint: disable=attribute-defined-outside-init
        self._implementation_version = value

    @property
    def maximum_associations(self):
        """Return the number of maximum associations as int."""
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
        """Return the maximum PDU size accepted by the AE as int."""
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
        """Get the network timeout."""
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

    @property
    def port(self):
        """Return the port number as an int.

        This property is deprecated and will be removed in v1.3.
        """
        return self._port

    @port.setter
    def port(self, value):
        """Set the port number.

        This property is deprecated and will be removed in v1.3. Use
        the ``address`` parameter for ``start_server()`` and the
        ``bind_address`` keyword parameter for ``associate()`` instead.
        """
        warnings.warn(
            "The `port` keyword parameter for AE() is deprecated and will "
            "be removed in v1.3. Use the `address` parameter for "
            "AE.start_server() or the `bind_address` keyword parameter "
            "for AE.associate() instead",
            DeprecationWarning
        )
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, int) and value >= 0:
            self._port = value
        else:
            raise ValueError("AE port number must be an integer greater then "
                             "or equal to 0")

    def remove_requested_context(self, abstract_syntax, transfer_syntax=None):
        """Remove a requested Presentation Context.

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
            The transfer syntax(ex) you wish to stop requesting. If a list of
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
        >>> print(ae.reqested_contexts[0])
        Abstract Syntax: Verification SOP Class
        Transfer Syntax(es):
	        =Implicit VR Little Endian
	        =Explicit VR Little Endian
	        =Explicit VR Big Endian
        >>> ae.remove_requested_context('1.2.840.10008.1.1')
        >>> len(ae.requested_contexts)
        0

        Remove all requested presentation contexts with an abstract syntax of
        *Verification SOP Class* using the inbuilt `VerificationSOPClass`
        object.

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
        >>> ae.add_requested_context(VerificationSOPClass,
        ...                          ImplicitVRLittleEndian)
        >>> print(ae.requested_contexts[0])
        Abstract Syntax: Verification SOP Class
        Transfer Syntax(es):
	        =Implicit VR Little Endian
        >>> ae.remove_requested_context(VerificationSOPClass,
        ...                             ImplicitVRLittleEndian)
        >>> len(ae.requested_contexts)
        0

        Presentation context has at least one remaining transfer syntax:

        >>> from pydicom.uid import (
        ...     ImplicitVRLittleEndian, ExplicitVRLittleEndian
        ... )
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
        >>> ae.remove_requested_context(VerificationSOPClass,
        ...                             [ImplicitVRLittleEndian,
        ...                              ExplicitVRLittleEndian])
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

        * `abstract_syntax` alone-  the entire supported context will be
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
            The transfer syntax(ex) you wish to stop supporting. If a list of
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
        *Verification SOP Class* using the inbuilt `VerificationSOPClass`
        object.

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
        >>> ae.add_supported_context(VerificationSOPClass,
        ...                          ImplicitVRLittleEndian)
        >>> print(ae.supported_contexts[0])
        Abstract Syntax: Verification SOP Class
        Transfer Syntax(es):
	        =Implicit VR Little Endian
        >>> ae.remove_supported_context(VerificationSOPClass,
        ...                             ImplicitVRLittleEndian)
        >>> len(ae.supported_contexts)
        0

        Presentation context has at least one remaining transfer syntax:

        >>> from pydicom.uid import (
        ...     ImplicitVRLittleEndian, ExplicitVRLittleEndian
        ... )
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
        >>> ae.remove_supported_context(VerificationSOPClass,
        ...                             [ImplicitVRLittleEndian,
        ...                              ExplicitVRLittleEndian])
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
        """Return a list of the requested PresentationContext items.

        Returns
        -------
        list of presentation.PresentationContext
            The SCU's requested Presentation Contexts.
        """
        return self._requested_contexts

    @requested_contexts.setter
    def requested_contexts(self, contexts):
        """Set the requested Presentation Contexts using a list.

        Parameters
        ----------
        contexts : list of presentation.PresentationContext
            The Presentation Contexts to request when acting as an SCU.

        Examples
        --------
        Set the requested presentation contexts using an inbuilt list of service
        specific `PresentationContext` items:

        >>> from pynetdicom import AE, StoragePresentationContexts
        >>> ae = AE()
        >>> ae.requested_contexts = StoragePresentationContexts

        Set the requested presentation contexts using a list of
        `PresentationContext` items:

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
        """Return whether the *Called AE Title* must match ae_title."""
        return self._require_called_aet

    @require_called_aet.setter
    def require_called_aet(self, require_match):
        """Set whether the *Called AE Title* must match the AE title.

        When an Association request is received the value of the 'Called AE
        Title' supplied by the peer will be compared with the set values and
        if none match the association will be rejected. If the set value
        is an empty list then the 'Called AE Title' will not be checked.

        Parameters
        ----------
        require_match : bool
            If True then any association requests that supply a
            *Called AE Title* value that does not match AE.ae_title
            will be rejected. If False (default) then all association requests
            will be accepted (unless rejected for other reasons).
        """
        # pylint: disable=attribute-defined-outside-init
        self._require_called_aet = require_match

    @property
    def require_calling_aet(self):
        """Return the required calling AE title as a list of bytes."""
        return self._require_calling_aet

    @require_calling_aet.setter
    def require_calling_aet(self, ae_titles):
        """Set the required calling AE title.

        When an Association request is received the value of the 'Calling AE
        Title' supplied by the peer will be compared with the set value and
        if none match the association will be rejected. If the set value
        is an empty list then the 'Calling AE Title' will not be checked.

        Parameters
        ----------
        ae_titles : list of bytes
            If not empty then any association requests that supply a
            Calling AE Title value that does not match one of the values in
            `ae_titles` will be rejected. If an empty list (default) then all
            association requests will be accepted (unless rejected for other
            reasons).
        """
        # pylint: disable=attribute-defined-outside-init
        self._require_calling_aet = [
            validate_ae_title(aet) for aet in ae_titles
        ]

    # TODO: remove in v1.3
    def start(self, select_timeout=0.5):
        """Start the AE as an SCP.

        When running the AE as an SCP this needs to be called to start the main
        loop, it listens for connections on `local_socket` and if they request
        association starts a new Association thread

        This method is deprecated and will be removed in v1.3. Use
        ``start_server()`` instead.

        Parameters
        ----------
        select_timeout : float or None, optional
            The timeout (in seconds) that the select.select() call will block
            for (default 0.5). A value of 0 specifies a poll and never blocks.
            A value of None blocks until a connection is ready.
        """
        warnings.warn(
            "start() is deprecated and will be removed in v1.3. Use "
            "start_server() instead",
            DeprecationWarning
        )

        self._quit = False

        # If the SCP has no supported SOP Classes then there's no point
        #   running as a server
        if not self.supported_contexts:
            msg = "No supported Presentation Contexts have been defined"
            LOGGER.error(msg)
            raise ValueError(msg)

        bad_contexts = []
        for cx in self.supported_contexts:
            roles = (cx.scu_role, cx.scp_role)
            if None in roles and roles != (None, None):
                bad_contexts.append(cx.abstract_syntax)

        if bad_contexts:
            msg = (
                "The following presentation contexts have inconsistent "
                "scu_role/scp_role values (if one is None, both must be):\n  "
            )
            msg += '\n  '.join(bad_contexts)
            LOGGER.warning(msg)
            return

        # Bind `sock` to the specified listen port
        sock = self._bind_socket()
        self.local_socket = sock

        while not self._quit:
            try:
                # Returns a list if `sock` has data available
                #   readable, writeable, exceptional
                # `select_timeout` specifies that select blocks for
                #   that many seconds before allowing the SCP to be killed
                ready, _, _ = select.select([sock], [], [], select_timeout)

                # We check self._quit in case the kill came in during select()
                if ready and not self._quit:
                    # socket.accept() blocks until a connection is available
                    client_socket, _ = sock.accept()

                    # Start a new association (as acceptor)
                    self._handle_connection(client_socket)
            except KeyboardInterrupt:
                self.stop()

    def start_server(self, address, block=True, ssl_context=None):
        """Start the AE as an association acceptor.

        If set to non-blocking then a running ``ThreadedAssociationServer``
        instance will be returned. This can be stopped using ``shutdown()``.

        Parameters
        ----------
        address : 2-tuple
            The (host, port) to use when listening for incoming association
            requests.
        block : bool, optional
            If True (default) then the server will be blocking, otherwise it
            will start the server in a new thread and be non-blocking.
        ssl_context : ssl.SSLContext, optional
            If TLS is required then this should the SSLContext instance to
            use to wrap the client sockets, otherwise if None then no TLS will
            be used (default).

        Returns
        -------
        transport.ThreadedAssociationServer or None
            If `block` is False then returns the server instance, otherwise
            returns None.
        """
        # If the SCP has no supported SOP Classes then there's no point
        #   running as a server
        if not self.supported_contexts:
            msg = "No supported Presentation Contexts have been defined"
            LOGGER.error(msg)
            raise ValueError(msg)

        bad_contexts = []
        for cx in self.supported_contexts:
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

        if block:
            server = AssociationServer(self, address, ssl_context)
            self._servers.append(server)
            try:
                # **BLOCKING**
                server.serve_forever()
            except KeyboardInterrupt:
                server.shutdown()
        else:
            # Non-blocking server
            timestamp = datetime.strftime(datetime.now(), "%Y%m%d%H%M%S")
            server = ThreadedAssociationServer(self, address, ssl_context)
            thread = threading.Thread(
                target=server.serve_forever,
                name="AcceptorServer@{}".format(timestamp)
            )
            thread.daemon = True
            thread.start()

            self._servers.append(server)

            return server

    # TODO: remove in v1.3
    def stop(self):
        """Stop the SCP.

        When running as an SCP, calling stop() will kill all associations
        and close the listen socket.

        This method is deprecated and will be removed in v1.3. Use
        ``shutdown()`` instead.
        """
        warnings.warn(
            "stop() is deprecated and will be removed in v1.3. Use "
            "shutdown() instead",
            DeprecationWarning
        )
        self._quit = True

        if self.local_socket:
            try:
                self.local_socket.shutdown(socket.SHUT_RDWR)
            except:
                pass
            self.local_socket.close()
            self.local_socket = None

        self.shutdown()

    def shutdown(self):
        """Stop any active association servers and threads."""
        for assoc in self.active_associations:
            assoc.abort()

        # This is a bit hackish: server.shutdown() deletes the server
        #   from `_servers` so we need to workaround this
        original = self._servers[:]
        for server in original:
            server.shutdown()

        self._servers = []

    # TODO: refactor in v1.3
    def __str__(self):
        """ Prints out the attribute values and status for the AE """
        str_out = "\n"
        str_out += "Application Entity '{0!s}' on {1!s}:{2!s}\n" \
                   .format(self.ae_title, self.address, self.port)

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
        """Return a list of the supported PresentationContexts items.

        Returns
        -------
        list of presentation.PresentationContext
            The SCP's supported Presentation Contexts, ordered by abstract
            syntax.
        """
        # The supported presentation contexts are stored internally as a dict
        contexts = sorted(list(self._supported_contexts.values()),
                          key=lambda cntx: cntx.abstract_syntax)
        return contexts

    @supported_contexts.setter
    def supported_contexts(self, contexts):
        """Set the supported Presentation Contexts using a list.

        Parameters
        ----------
        contexts : list of presentation.PresentationContext
            The Presentation Contexts to support when acting as an SCP.

        Examples
        --------
        Set the supported presentation contexts using a list of
        `PresentationContext` items:

        >>> from pydicom.uid import ImplicitVRLittleEndian
        >>> from pynetdicom import AE
        >>> from pynetdicom.presentation import PresentationContext
        >>> context = PresentationContext()
        >>> context.abstract_syntax = '1.2.840.10008.1.1'
        >>> context.transfer_syntax = [ImplicitVRLittleEndian]
        >>> ae = AE()
        >>> ae.supported_contexts = [context]

        Set the supported presentation contexts using an inbuilt list of service
        specific `PresentationContext` items:

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
                "The maximum allowed number of requested presentation contexts "
                "is 128"
            )

        for item in contexts:
            if not isinstance(item, PresentationContext):
                raise ValueError(
                    "'contexts' must be a list of PresentationContext items"
                )


    # Association extended negotiation callbacks
    # pylint: disable=unused-argument,no-self-use
    def on_async_ops_window(self, nr_invoked, nr_performed):
        """Callback for when an Asynchronous Operations Window Negotiation
        item is include in the association request.

        Asynchronous operations are not supported by pynetdicom and any
        request will always return the default number of operations
        invoked/performed (1, 1), regardless of what values are returned by
        this callback.

        If the callback is not implemented then no response to the Asynchronous
        Operations Window Negotiation will be sent to the association
        requestor.

        Parameters
        ----------
        nr_invoked : int
            The *Maximum Number Operations Invoked* parameter value of the
            Asynchronous Operations Window request. If the value is 0 then
            an unlimited number of invocations are requested.
        nr_performed : int
            The *Maximum Number Operations Performed* parameter value of the
            Asynchronous Operations Window request. If the value is 0 then
            an unlimited number of performances are requested.

        Returns
        -------
        int, int
            The (maximum number operations invoked, maximum number operations
            performed). A value of 0 indicates that an unlimited number of
            operations is supported. As asynchronous operations are not
            currently supported the return value will be ignored and (1, 1).
            sent in response.
        """
        raise NotImplementedError(
            "No Asynchronous Operations Window Negotiation response will be "
            "sent"
        )

    def on_sop_class_common_extended(self, items):
        """Callback for when one or more SOP Class Common Extended Negotiation
        items are included in the association request.

        Parameters
        ----------
        items : dict
            The {*SOP Class UID* : SOPClassCommonExtendedNegotiation} items
            sent by the requestor.

        Returns
        -------
        dict
            The {*SOP Class UID* : SOPClassCommonExtendedNegotiation}
            accepted by the acceptor. When receiving DIMSE messages containing
            datasets corresponding to the SOP Class UID in an accepted item
            the corresponding Service Class will be used.

        References
        ----------

        * DICOM Standard Part 7, `Annex D.3.3.6 <http://dicom.nema.org/medical/dicom/current/output/chtml/part07/sect_D.3.3.6.html>`_
        """
        return {}

    def on_sop_class_extended(self, app_info):
        """Callback for when one or more SOP Class Extended Negotiation items
        are included in the association request.

        Parameters
        ----------
        app_info : dict of pydicom.uid.UID, bytes
            The {*SOP Class UID* : *Service Class Application Information*}
            parameter values for the included items, with the service class
            application information being the raw encoded data sent by the
            requestor.

        Returns
        -------
        dict of pydicom.uid.UID, bytes or None
            The {*SOP Class UID* : *Service Class Application Information*}
            parameter values to be sent in response to the request, with the
            service class application information being the encoded data that
            will be sent to the peer as-is. Return None if no response is to
            be sent.

        References
        ----------

        * DICOM Standard Part 7, `Annex D.3.3.5 <http://dicom.nema.org/medical/dicom/current/output/chtml/part07/sect_D.3.3.5.html>`_
        """
        return None

    def on_user_identity(self, user_id_type, primary_field,
                         secondary_field, info):
        """Callback for when a user identity negotiation item is included with
        the association request.

        If not implemented by the user then the association will be accepted
        (provided there's no other reason to reject it) and no User Identity
        response will be sent even if one is requested.

        Parameters
        ----------
        user_id_type : int
            The *User Identity Type* value, which indicates the form of user
            identity being provided:

            * 1 - Username as a UTF-8 string
            * 2 - Username as a UTF-8 string and passcode
            * 3 - Kerberos Service ticket
            * 4 - SAML Assertion
            * 5 - JSON Web Token
        primary_field : bytes
            The *Primary Field* value, contains the username, the encoded
            Kerberos ticket or the JSON web token.
        secondary_field : bytes or None
            The *Secondary Field* value. Will be ``None`` unless the
            `user_id_type` is ``2`` in which case it will be ``bytes``.
        info : dict
            A dict containing information about the association request and
            the association requestor, with the keys:

            ::

              'requestor' : {
                  'ae_title' : bytes, the requestor's AE title
                  'address' : str, the requestor's IP address
                  'port' : int, the requestor's port number
              }

        Returns
        -------
        is_verified : bool
            Return True if the user identity has been confirmed and you wish
            to proceed with association establishment, False otherwise.
        response : bytes or None
            If ``user_id_type`` is:

            * 1 or 2, then return None
            * 3 then return the Kerberos Server ticket as bytes
            * 4 then return the SAML response as bytes
            * 5 then return the JSON web token as bytes

        References
        ----------

        * DICOM Standard Part 7, `Annex D.3.3.7 <http://dicom.nema.org/medical/dicom/current/output/chtml/part07/sect_D.3.3.7.html>`_
        """
        raise NotImplementedError("User Identity Negotiation not implemented")


    # High-level DIMSE-C callbacks - user should implement these as required
    def on_c_echo(self, context, info):
        """Callback for when a C-ECHO request is received.

        User implementation is not required for the C-ECHO service, but if you
        intend to do so it should be defined prior to calling
        ``ApplicationEntity.start()`` and
        must return either an ``int`` or a pydicom ``Dataset`` containing a
        (0000,0900) *Status* element with a valid C-ECHO status value.

        **Supported Service Classes**

        *Verification Service Class*

        **Status**

        Success
          | ``0x0000`` Success

        Failure
          | ``0x0122`` Refused: SOP Class Not Supported
          | ``0x0210`` Refused: Duplicate Invocation
          | ``0x0211`` Refused: Unrecognised Operation
          | ``0x0212`` Refused: Mistyped Argument

        Parameters
        ----------
        context : presentation.PresentationContextTuple
            The presentation context that the C-ECHO message was sent under
            as a ``namedtuple`` with field names ``context_id``,
            ``abstract_syntax`` and ``transfer_syntax``.
        info : dict
            A dict containing information about the current association, with
            the keys:

            ::

              'requestor' : {
                  'ae_title' : bytes, the requestor's calling AE title
                  'called_aet' : bytes, the requestor's called AE title
                  'address' : str, the requestor's IP address
                  'port' : int, the requestor's port number
              }
              'acceptor' : {
                  'ae_title' : bytes, the acceptor's AE title
                  'address' : str, the acceptor's IP address
                  'port' : int, the acceptor's port number
              }
              'parameters' : {
                  'message_id' : int, the DIMSE message ID
                  'priority' : int, the requested operation priority
                  'originator_aet' : bytes or None, the move originator's AE
                                     title
                  'originator_message_id' : int or None, the move originator's
                                            message ID
              }
              'sop_class_extended' : {
                  SOP Class UID : Service Class Application Information,
              }

        Returns
        -------
        status : pydicom.dataset.Dataset or int
            The status returned to the peer AE in the C-ECHO response. Must be
            a valid C-ECHO status value for the applicable Service Class as
            either an ``int`` or a ``Dataset`` object containing (at a minimum)
            a (0000,0900) *Status* element. If returning a ``Dataset`` object
            then it may also contain optional elements related to the Status
            (as in the DICOM Standard Part 7, Annex C).

        See Also
        --------
        association.Association.send_c_echo
        dimse_primitives.C_ECHO
        service_class.VerificationServiceClass

        References
        ----------

        * DICOM Standard Part 4, `Annex A <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_A>`_
        * DICOM Standard Part 7, Sections
          `9.1.5 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.1.5>`_,
          `9.3.5 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.5>`_
          and `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_

        """
        # User implementation of on_c_echo is optional
        return 0x0000

    def on_c_find(self, dataset, context, info):
        """Callback for when a C-FIND request is received.

        Must be defined by the user prior to calling ``AE.start()`` and must
        yield ``(status, identifier)`` pairs, where *status* is either an
        ``int`` or pydicom ``Dataset`` containing a (0000,0900) *Status*
        element and *identifier* is a C-FIND *Identifier* ``Dataset``.

        **Supported Service Classes**

        * *Query/Retrieve Service Class*
        * *Basic Worklist Management Service*
        * *Relevant Patient Information Query Service*
        * *Substance Administration Query Service*
        * *Hanging Protocol Query/Retrieve Service*
        * *Defined Procedure Protocol Query/Retrieve Service*
        * *Color Palette Query/Retrieve Service*
        * *Implant Template Query/Retrieve Service*

        **Status**

        Success
          | ``0x0000`` Success

        Failure
          | ``0xA700`` Out of resources
          | ``0xA900`` Identifier does not match SOP class
          | ``0xC000`` to ``0xCFFF`` Unable to process

        Cancel
          | ``0xFE00`` Matching terminated due to Cancel request

        Pending
          | ``0xFF00`` Matches are continuing: current match is supplied and
             any Optional Keys were supported in the same manner as Required
             Keys
          | ``0xFF01`` Matches are continuing: warning that one or more Optional
            Keys were not supported for existence and/or matching for this
            Identifier

        Parameters
        ----------
        dataset : pydicom.dataset.Dataset
            The DICOM Identifier dataset sent by the peer in the C-FIND
            request.
        context : presentation.PresentationContextTuple
            The presentation context that the C-FIND message was sent under
            as a ``namedtuple`` with field names ``context_id``,
            ``abstract_syntax`` and ``transfer_syntax``.
        info : dict
            A dict containing information about the current association, with
            the keys:

            ::

              'requestor' : {
                  'ae_title' : bytes, the requestor's calling AE title
                  'called_aet' : bytes, the requestor's called AE title
                  'address' : str, the requestor's IP address
                  'port' : int, the requestor's port number
              }
              'acceptor' : {
                  'ae_title' : bytes, the acceptor's AE title
                  'address' : str, the acceptor's IP address
                  'port' : int, the acceptor's port number
              }
              'parameters' : {
                  'message_id' : int, the DIMSE message ID
                  'priority' : int, the requested operation priority
              }
              'sop_class_extended' : {
                  SOP Class UID : Service Class Application Information,
              }
              'cancelled' : callable_function

            Where *callable_function* is a function that takes a `msg_id`
            parameter (as int ) and returns True if a C-CANCEL message has
            been received with a *Message ID Being Responded To* value that
            corresponds to `msg_id`, False otherwise. For example:
            ``is_cancelled = info['cancelled'](msg_id)``

        Yields
        ------
        status : pydicom.dataset.Dataset or int
            The status returned to the peer AE in the C-FIND response. Must be
            a valid C-FIND status vuale for the applicable Service Class as
            either an ``int`` or a ``Dataset`` object containing (at a minimum)
            a (0000,0900) *Status* element. If returning a Dataset object then
            it may also contain optional elements related to the Status (as in
            DICOM Standard Part 7, Annex C).
        identifier : pydicom.dataset.Dataset or None
            If the status is 'Pending' then the *Identifier* ``Dataset`` for a
            matching SOP Instance. The exact requirements for the C-FIND
            response *Identifier* are Service Class specific (see the
            DICOM Standard, Part 4).

            If the status is 'Failure' or 'Cancel' then yield ``None``.

            If the status is 'Success' then yield ``None``, however yielding a
            final 'Success' status is not required and will be ignored if
            necessary.

        See Also
        --------
        association.Association.send_c_find
        dimse_primitives.C_FIND
        service_class.QueryRetrieveFindServiceClass
        service_class.BasicWorklistManagementServiceClass
        service_class.RelevantPatientInformationQueryServiceClass
        service_class.SubstanceAdministrationQueryServiceClass
        service_class.HangingProtocolQueryRetrieveServiceClass
        service_class.DefinedProcedureProtocolQueryRetrieveServiceClass
        service_class.ColorPaletteQueryRetrieveServiceClass
        service_class.ImplantTemplateQueryRetrieveServiceClass

        References
        ----------

        * DICOM Standard Part 4, Annexes
          `C <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_C>`_,
          `K <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_K>`_,
          `Q <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_Q>`_,
          `U <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_U>`_,
          `V <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_V>`_,
          `X <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_X>`_,
          `BB <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_BB>`_,
          `CC <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_CC>`_
          and `HH <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_HH>`_
        * DICOM Standard Part 7, Sections
          `9.1.2 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.1.2>`_,
          `9.3.2 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.2>`_
          and `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_
        """
        raise NotImplementedError("User must implement the AE.on_c_find "
                                  "function prior to calling AE.start()")

    def on_c_get(self, dataset, context, info):
        """Callback for when a C-GET request is received.

        Must be defined by the user prior to calling
        ``ApplicationEntity.start()`` and must yield a ``int`` containing the
        total number of C-STORE sub-operations, then yield ``(status,
        dataset)`` pairs.

        **Supported Service Classes**

        * *Query/Retrieve Service Class*
        * *Hanging Protocol Query/Retrieve Service*
        * *Defined Procedure Protocol Query/Retrieve Service*
        * *Color Palette Query/Retrieve Service*
        * *Implant Template Query/Retrieve Service*

        **Status**

        Success
          | ``0x0000`` Sub-operations complete, no failures or warnings

        Failure
          | ``0xA701`` Out of resources: unable to calculate the number of
            matches
          | ``0xA702`` Out of resources: unable to perform sub-operations
          | ``0xA900`` Identifier does not match SOP class
          | ``0xAA00`` None of the frames requested were found in the SOP
            instance
          | ``0xAA01`` Unable to create new object for this SOP class
          | ``0xAA02`` Unable to extract frames
          | ``0xAA03`` Time-based request received for a non-time-based
            original SOP Instance
          | ``0xAA04`` Invalid request
          | ``0xC000`` to ``0xCFFF`` Unable to process

        Cancel
          | ``0xFE00`` Sub-operations terminated due to Cancel request

        Warning
          | ``0xB000`` Sub-operations complete, one or more failures or
            warnings

        Pending
          | ``0xFF00`` Matches are continuing - Current Match is supplied and
            any Optional Keys were supported in the same manner as Required
            Keys

        Parameters
        ----------
        dataset : pydicom.dataset.Dataset
            The DICOM Identifier dataset sent by the peer in the C-GET request.
        context : presentation.PresentationContextTuple
            The presentation context that the C-GET message was sent under
            as a ``namedtuple`` with field names ``context_id``,
            ``abstract_syntax`` and ``transfer_syntax``.
        info : dict
            A dict containing information about the current association, with
            the keys:

            ::

              'requestor' : {
                  'ae_title' : bytes, the requestor's calling AE title
                  'called_aet' : bytes, the requestor's called AE title
                  'address' : str, the requestor's IP address
                  'port' : int, the requestor's port number
              }
              'acceptor' : {
                  'ae_title' : bytes, the acceptor's AE title
                  'address' : str, the acceptor's IP address
                  'port' : int, the acceptor's port number
              }
              'parameters' : {
                  'message_id' : int, the DIMSE message ID
                  'priority' : int, the requested operation priority
              }
              'sop_class_extended' : {
                  SOP Class UID : Service Class Application Information,
              }
              'cancelled' : callable_function

            Where *callable_function* is a function that takes a `msg_id`
            parameter (as int ) and returns True if a C-CANCEL message has
            been received with a *Message ID Being Responded To* value that
            corresponds to `msg_id`, False otherwise. For example:
            ``is_cancelled = info['cancelled'](msg_id)``

        Yields
        ------
        int
            The first yielded value should be the total number of C-STORE
            sub-operations necessary to complete the C-GET operation. In other
            words, this is the number of matching SOP Instances to be sent to
            the peer.
        status : pydicom.dataset.Dataset or int
            The status returned to the peer AE in the C-GET response. Must be a
            valid C-GET status value for the applicable Service Class as either
            an ``int`` or a ``Dataset`` object containing (at a minimum) a
            (0000,0900) *Status* element. If returning a Dataset object then
            it may also contain optional elements related to the Status (as in
            DICOM Standard Part 7, Annex C).
        dataset : pydicom.dataset.Dataset or None
            If the status is 'Pending' then yield the ``Dataset`` to send to
            the peer via a C-STORE sub-operation over the current association.

            If the status is 'Failed', 'Warning' or 'Cancel' then yield a
            ``Dataset`` with a (0008,0058) *Failed SOP Instance UID List*
            element containing a list of the C-STORE sub-operation SOP Instance
            UIDs for which the C-GET operation has failed.

            If the status is 'Success' then yield ``None``, although yielding a
            final 'Success' status is not required and will be ignored if
            necessary.

        See Also
        --------
        association.Association.send_c_get
        dimse_primitives.C_GET
        service_class.QueryRetrieveGetServiceClass
        service_class.HangingProtocolQueryRetrieveServiceClass
        service_class.DefinedProcedureProtocolQueryRetrieveServiceClass
        service_class.ColorPaletteQueryRetrieveServiceClass
        service_class.ImplantTemplateQueryRetrieveServiceClass

        References
        ----------

        * DICOM Standard Part 4, Annexes
          `C <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_C>`_,
          `U <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_U>`_,
          `X <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_X>`_,
          `Y <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_Y>`_,
          `Z <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_Z>`_,
          `BB <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_BB>`_
          and `HH <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_HH>`_
        * DICOM Standard Part 7, Sections
          `9.1.3 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.1.3>`_,
          `9.3.3 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.3>`_
          and `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_
        """
        raise NotImplementedError("User must implement the AE.on_c_get "
                                  "function prior to calling AE.start()")

    def on_c_move(self, dataset, move_aet, context, info):
        """Callback for when a C-MOVE request is received.

        Must be defined by the user prior to calling
        ``ApplicationEntity.start()``.

        The first yield should be the ``(addr, port)`` of the move destination,
        the second yield the number of required C-STORE sub-operations as an
        ``int``, and the remaining yields the ``(status, dataset)`` pairs.

        Matching SOP Instances will be sent to the peer AE with AE title
        ``move_aet`` over a new association. If ``move_aet`` is unknown then
        the SCP will send a response with a 'Failure' status of ``0xA801``
        'Move Destination Unknown'.

        **Supported Service Classes**

        * *Query/Retrieve Service*
        * *Hanging Protocol Query/Retrieve Service*
        * *Defined Procedure Protocol Query/Retrieve Service*
        * *Color Palette Query/Retrieve Service*
        * *Implant Template Query/Retrieve Service*

        **Status**

        Success
          | ``0x0000`` Sub-operations complete, no failures

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
          | ``0xA801`` Move destination unknown
          | ``0xA900`` Identifier does not match SOP class
          | ``0xAA00`` None of the frames requested were found in the SOP
            instance
          | ``0xAA01`` Unable to create new object for this SOP class
          | ``0xAA02`` Unable to extract frames
          | ``0xAA03`` Time-based request received for a non-time-based
            original SOP Instance
          | ``0xAA04`` Invalid request
          | ``0xC000`` to ``0xCFFF`` Unable to process

        Parameters
        ----------
        dataset : pydicom.dataset.Dataset
            The DICOM Identifier dataset sent by the peer in the C-MOVE request.
        move_aet : bytes
            The destination AE title that matching SOP Instances will be sent
            to using C-STORE sub-operations. ``move_aet`` will be a correctly
            formatted AE title (16 chars, with trailing spaces as padding).
        context : presentation.PresentationContextTuple
            The presentation context that the C-MOVE message was sent under
            as a ``namedtuple`` with field names ``context_id``,
            ``abstract_syntax`` and ``transfer_syntax``.
        info : dict
            A dict containing information about the current association, with
            the keys:

            ::

              'requestor' : {
                  'ae_title' : bytes, the requestor's calling AE title
                  'called_aet' : bytes, the requestor's called AE title
                  'address' : str, the requestor's IP address
                  'port' : int, the requestor's port number
              }
              'acceptor' : {
                  'ae_title' : bytes, the acceptor's AE title
                  'address' : str, the acceptor's IP address
                  'port' : int, the acceptor's port number
              }
              'parameters' : {
                  'message_id' : int, the DIMSE message ID
                  'priority' : int, the requested operation priority
              }
              'sop_class_extended' : {
                  SOP Class UID : Service Class Application Information,
              }
              'cancelled' : callable_function

            Where *callable_function* is a function that takes a `msg_id`
            parameter (as int) and returns True if a C-CANCEL message has
            been received with a *Message ID Being Responded To* value that
            corresponds to `msg_id`, False otherwise. For example:
            ``is_cancelled = info['cancelled'](msg_id)``

        Yields
        ------
        addr, port : str, int or None, None
            The first yield should be the TCP/IP address and port number of the
            destination AE (if known) or ``(None, None)`` if unknown. If
            ``(None, None)`` is yielded then the SCP will send a C-MOVE
            response with a 'Failure' Status of ``0xA801`` (move destination
            unknown), in which case nothing more needs to be yielded.
        int
            The second yield should be the number of C-STORE sub-operations
            required to complete the C-MOVE operation. In other words, this is
            the number of matching SOP Instances to be sent to the peer.
        status : pydiom.dataset.Dataset or int
            The status returned to the peer AE in the C-MOVE response. Must be
            a valid C-MOVE status value for the applicable Service Class as
            either an ``int`` or a ``Dataset`` containing (at a minimum) a
            (0000,0900) *Status* element. If returning a ``Dataset`` then it
            may also contain optional elements related to the Status (as in
            DICOM Standard Part 7, Annex C).
        dataset : pydicom.dataset.Dataset or None
            If the status is 'Pending' then yield the ``Dataset``
            to send to the peer via a C-STORE sub-operation over a new
            association.

            If the status is 'Failed', 'Warning' or 'Cancel' then yield a
            ``Dataset`` with a (0008,0058) *Failed SOP Instance UID List*
            element containing the list of the C-STORE sub-operation SOP
            Instance UIDs for which the C-MOVE operation has failed.

            If the status is 'Success' then yield ``None``, although yielding a
            final 'Success' status is not required and will be ignored if
            necessary.

        See Also
        --------
        association.Association.send_c_move
        dimse_primitives.C_MOVE
        service_class.QueryRetrieveMoveServiceClass
        service_class.HangingProtocolQueryRetrieveServiceClass
        service_class.DefinedProcedureProtocolQueryRetrieveServiceClass
        service_class.ColorPaletteQueryRetrieveServiceClass
        service_class.ImplantTemplateQueryRetrieveServiceClass

        References
        ----------

        * DICOM Standard Part 4, Annexes
          `C <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_C>`_,
          `U <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_U>`_,
          `X <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_X>`_,
          `Y <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_Y>`_,
          `BB <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_BB>`_
          and `HH <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_HH>`_
        * DICOM Standard Part 7, Sections
          `9.1.4 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.1.4>`_,
          `9.3.4 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.4>`_
          and `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_
        """
        raise NotImplementedError("User must implement the AE.on_c_move "
                                  "function prior to calling AE.start()")

    def on_c_store(self, dataset, context, info):
        """Callback for when a C-STORE request is received.

        Must be defined by the user prior to calling
        ``ApplicationEntity.start()`` and must return
        either an ``int`` or a pydicom ``Dataset`` containing a (0000,0900)
        *Status* element with a valid C-STORE status value.

        If the user is storing `dataset` in the DICOM File Format (as in the
        DICOM Standard Part 10, Section 7) then they are responsible for adding
        the DICOM File Meta Information.

        **Supported Service Classes**

        * *Storage Service Class*
        * *Non-Patient Object Storage Service Class*

        **Status**

        Success
          | ``0x0000`` - Success

        Warning
          | ``0xB000`` Coercion of data elements
          | ``0xB006`` Elements discarded
          | ``0xB007`` Dataset does not match SOP class

        Failure
          | ``0x0117`` Invalid SOP instance
          | ``0x0122`` SOP class not supported
          | ``0x0124`` Not authorised
          | ``0x0210`` Duplicate invocation
          | ``0x0211`` Unrecognised operation
          | ``0x0212`` Mistyped argument
          | ``0xA700`` to ``0xA7FF`` Out of resources
          | ``0xA900`` to ``0xA9FF`` Dataset does not match SOP class
          | ``0xC000`` to ``0xCFFF`` Cannot understand

        Parameters
        ----------
        dataset : pydicom.dataset.Dataset or bytes
            The DICOM dataset sent by the peer in the C-STORE request as a
            pydicom Dataset object (default). If _config.DECODE_STORE_DATASETS
            is set to False then returns the raw encoded dataset sent by the
            service requestor as bytes.
        context : presentation.PresentationContextTuple
            The presentation context that the C-STORE message was sent under
            as a ``namedtuple`` with field names ``context_id``,
            ``abstract_syntax`` and ``transfer_syntax``.
        info : dict
            A dict containing information about the current association, with
            the keys:

            ::

              'requestor' : {
                  'ae_title' : bytes, the requestor's calling AE title
                  'called_aet' : bytes, the requestor's called AE title
                  'address' : str, the requestor's IP address
                  'port' : int, the requestor's port number
              }
              'acceptor' : {
                  'ae_title' : bytes, the acceptor's AE title
                  'address' : str, the acceptor's IP address
                  'port' : int, the acceptor's port number
              }
              'parameters' : {
                  'message_id' : int, the DIMSE message ID
                  'priority' : int, the requested operation priority
                  'originator_aet' : bytes or None, the move originator's AE
                                     title
                  'originator_message_id' : int or None, the move originator's
                                            message ID
              }
              'sop_class_extended' : {
                  SOP Class UID : Service Class Application Information,
              }

        Returns
        -------
        status : pydicom.dataset.Dataset or int
            The status returned to the peer AE in the C-STORE response. Must be
            a valid C-STORE status value for the applicable Service Class as
            either an ``int`` or a ``Dataset`` object containing (at a
            minimum) a (0000,0900) *Status* element. If returning a Dataset
            object then it may also contain optional elements related to the
            Status (as in the DICOM Standard Part 7, Annex C).

        Raises
        ------
        NotImplementedError
            If the callback has not been implemented by the user

        See Also
        --------
        association.Association.send_c_store
        dimse_primitives.C_STORE
        service_class.StorageServiceClass
        service_class.NonPatientObjectStorageServiceClass

        References
        ----------

        * DICOM Standard Part 4, Annexes
          `B <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_B>`_,
          `AA <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_AA>`_,
          `FF <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_FF>`_
          and `GG <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_GG>`_
        * DICOM Standard Part 7, Sections
          `9.1.1 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.1.1>`_,
          `9.3.1 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.1>`_
          and `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_
        * DICOM Standard Part 10,
          `Section 7 <http://dicom.nema.org/medical/dicom/current/output/html/part10.html#chapter_7>`_
        """
        raise NotImplementedError("User must implement the AE.on_c_store "
                                  "function prior to calling AE.start()")


    # High-level DIMSE-N callbacks - user should implement these as required
    def on_n_action(self, dataset, context, info):
        """Callback for when a N-ACTION is received.

        References
        ----------
        DICOM Standard Part 4, Annexes H, J, P, S, CC and DD
        """
        raise NotImplementedError("User must implement the "
                                  "AE.on_n_action function prior to calling "
                                  "AE.start()")

    def on_n_create(self, dataset, context, info):
        """Callback for when a N-CREATE is received.

        References
        ----------
        DICOM Standard Part 4, Annexes F, H, R, S, CC and DD
        """
        raise NotImplementedError("User must implement the "
                                  "AE.on_n_create function prior to calling "
                                  "AE.start()")

    def on_n_delete(self, context, info):
        """Callback for when a N-DELETE is received.

        References
        ----------
        DICOM Standard Part 4, Annexes H and DD
        """
        raise NotImplementedError("User must implement the "
                                  "AE.on_n_delete function prior to calling "
                                  "AE.start()")

    def on_n_event_report(self, dataset, context, info):
        """Callback for when a N-EVENT-REPORT is received.

        References
        ----------
        DICOM Standard Part 4, Annexes F, H, J, CC and DD
        """
        raise NotImplementedError("User must implement the "
                                  "AE.on_n_event_report function prior to "
                                  "calling AE.start()")

    def on_n_get(self, attr, context, info):
        """Callback for when an N-GET request is received.

        Parameters
        ----------
        attr : list of pydicom.tag.Tag
            The value of the (0000,1005) *Attribute Idenfier List* element
            containing the attribute tags for the N-GET operation.
        context : presentation.PresentationContextTuple
            The presentation context that the N-GET message was sent under
            as a ``namedtuple`` with field names ``context_id``,
            ``abstract_syntax`` and ``transfer_syntax``.
        info : dict
            A dict containing information about the current association, with
            the keys:

            ::

              'requestor' : {
                  'ae_title' : bytes, the requestor's calling AE title
                  'called_aet' : bytes, the requestor's called AE title
                  'address' : str, the requestor's IP address
                  'port' : int, the requestor's port number
              }
              'acceptor' : {
                  'ae_title' : bytes, the acceptor's AE title
                  'address' : str, the acceptor's IP address
                  'port' : int, the acceptor's port number
              }
              'parameters' : {
                  'message_id' : int, the DIMSE message ID
                  'requested_sop_class' : str, the N-GET-RQ's requested SOP
                  Class UID value
                  'requested_sop_instance' : str, the N-GET-RQ's requested SOP
                  Instance UID value
              }
              'sop_class_extended' : {
                  SOP Class UID : Service Class Application Information,
              }

        Returns
        -------
        status : pydicom.dataset.Dataset or int
            The status returned to the peer AE in the N-GET response. Must be a
            valid N-GET status value for the applicable Service Class as either
            an ``int`` or a ``Dataset`` object containing (at a minimum) a
            (0000,0900) *Status* element. If returning a Dataset object then
            it may also contain optional elements related to the Status (as in
            DICOM Standard Part 7, Annex C).
        dataset : pydicom.dataset.Dataset or None
            If the status category is 'Success' or 'Warning' then a dataset
            containing elements matching the request's Attribute List
            conformant to the specifications in the corresponding Service
            Class.

            If the status is not 'Successs' or 'Warning' then return None.

        See Also
        --------
        association.Association.send_n_get
        dimse_primitives.N_GET
        service_class.DisplaySystemManagementServiceClass

        References
        ----------

        * DICOM Standart Part 4, `Annex F <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_F>`_
        * DICOM Standart Part 4, `Annex H <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_H>`_
        * DICOM Standard Part 4, `Annex S <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_S>`_
        * DICOM Standard Part 4, `Annex CC <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_CC>`_
        * DICOM Standard Part 4, `Annex DD <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_DD>`_
        * DICOM Standard Part 4, `Annex EE <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_EE>`_
        """
        raise NotImplementedError(
            "User must implement the AE.on_n_get function prior to calling "
            "AE.start()"
        )

    def on_n_set(self, dataset, context, info):
        """Callback for when a N-SET is received.

        References
        ----------
        DICOM Standard Part 4, Annexes F, H, CC and DD
        """
        raise NotImplementedError("User must implement the "
                                  "AE.on_n_set function prior to calling "
                                  "AE.start()")


    # Communication related callbacks
    def on_receive_connection(self):
        """Callback for a connection is received.
        ** NOT IMPLEMENTED **
        """
        raise NotImplementedError()

    def on_make_connection(self):
        """Callback for a connection is made.
        ** NOT IMPLEMENTED **
        """
        raise NotImplementedError()


    # High-level Association related callbacks
    def on_association_requested(self, primitive):
        """Callback for an association is requested.
        ** NOT IMPLEMENTED **
        """
        pass

    def on_association_accepted(self, primitive):
        """Callback for when an association is accepted.
        ** NOT IMPLEMENTED **
        Placeholder for a function callback. Function will be called
        when an association attempt is accepted by either the local or peer AE
        Parameters
        ----------
        pdu_primitives.A_ASSOCIATE
            The A-ASSOCIATE (accept) primitive.
        """
        pass

    def on_association_rejected(self, primitive):
        """Callback for when an association is rejected.
        ** NOT IMPLEMENTED **
        Placeholder for a function callback. Function will be called
        when an association attempt is rejected by a peer AE
        Parameters
        ----------
        associate_rq_pdu : pynetdicom.pdu.A_ASSOCIATE_RJ
            The A-ASSOCIATE-RJ PDU instance received from the peer AE
        """
        pass

    def on_association_released(self, primitive=None):
        """Callback for when an association is released.
        ** NOT IMPLEMENTED **
        """
        pass

    def on_association_aborted(self, primitive=None):
        """Callback for when an association is aborted.
        ** NOT IMPLEMENTED **
        """
        # FIXME: Need to standardise callback parameters for A-ABORT
        pass
