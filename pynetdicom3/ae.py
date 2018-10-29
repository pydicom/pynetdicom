"""
The main user class, represents a DICOM Application Entity
"""
from copy import deepcopy
import gc
from inspect import isclass
import logging
import platform
import select
import socket
from struct import pack
import sys
import time
import warnings

from pydicom.uid import (
    ExplicitVRLittleEndian, ImplicitVRLittleEndian, ExplicitVRBigEndian, UID
)

from pynetdicom3.association import Association
from pynetdicom3.presentation import (
    PresentationContext,
    DEFAULT_TRANSFER_SYNTAXES
)
from pynetdicom3.utils import validate_ae_title


def setup_logger():
    """Setup the logger."""
    logger = logging.getLogger('pynetdicom3')
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
        messages. A value of ``None`` means no timeout. (default: 60)
    active_associations : list of association.Association
        The currently active associations between the local and peer AEs.
    address : str
        The local AE's TCP/IP address.
    ae_title : bytes
        The local AE's AE title.
    bind_addr : str
        The network interface to listen to (default: all available network
        interfaces on the machine).
    client_socket : socket.socket
        The socket used for connections with peer AEs
    dimse_timeout : int or float or None
        The maximum amount of time (in seconds) to wait for DIMSE related
        messages. A value of ``None`` means no timeout. (default: None)
    network_timeout : int or float or None
        The maximum amount of time (in seconds) to wait for network messages.
        A value of ``None`` means no timeout. (default: None)
    maximum_associations : int
        The maximum number of simultaneous associations (default: 2)
    maximum_pdu_size : int
        The maximum PDU receive size in bytes. A value of 0 means there is no
        maximum size (default: 16382)
    port : int
        The local AE's listen port number when acting as an SCP or connection
        port when acting as an SCU. A value of 0 indicates that the operating
        system should choose the port.
    require_calling_aet : bytes
        If not empty bytes, the calling AE title must match
        `require_calling_aet` (SCP only).
    require_called_aet : bytes
        If not empty bytes the called AE title must match `required_called_aet`
        (SCP only).

    Examples
    --------

    **SCP**

    To use *AE* as an SCP, you need to specify:

    * The listen `port` number that SCUs can use to send Association
      requests and DIMSE messages
    * The Presentation Contexts that the SCP supports.

    If the SCP is being used for any DICOM Service Classes other than the
    *Verification Service Class* you also need to implement one or more of
    the callbacks corresponding to the DIMSE-C services (``on_c_store``,
    ``on_c_find``, ``on_c_get``, ``on_c_move``).

    The SCP can then be started using ``ApplicationEntity.start()``

    **C-STORE SCP Example**

    .. code-block:: python

            from pynetdicom3 import AE, StoragePresentationContexts

            # Create the AE and specify the listen port
            ae = AE(port=11112)

            # Set the supported Presentation Contexts
            ae.supported_contexts = StoragePresentationContexts

            # Define the callback for receiving a C-STORE request
            def on_c_store(dataset, context, info):
                # Insert your C-STORE handling code here

                # Must return a valid C-STORE status - 0x0000 is Success
                return 0x0000

            ae.on_c_store = on_c_store

            # Start the SCP
            ae.start()

    **SCU**

    To use *AE* as an SCU you only need to specify the Presentation Contexts
    that the SCU is requesting for support by the SCP. You can then call
    ``ApplicationEntity.associate(addr, port)`` where *addr* and *port* are the
    TCP/IP address and the listen port number of the peer SCP, respectively.

    Once the Association is established you can then request the use of the
    peer's DIMSE-C services.

    **C-ECHO SCU Example**

    .. code-block:: python

            from pynetdicom3 import AE, VerificationPresentationContexts

            # Create the AE with an AE Title 'MYAE'
            ae = AE(ae_title=b'MYAE')

            # Specify which SOP Classes are supported as an SCU
            ae.requested_contexts = VerificationPresentationContexts

            # Request an association with a peer SCP
            assoc = ae.associate('192.168.2.1', 104)

            if assoc.is_established:
                # Send a C-ECHO request to the peer
                status = assoc.send_c_echo()

                # Release the association
                assoc.release()
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
        """
        from pynetdicom3 import (
            PYNETDICOM_IMPLEMENTATION_UID,
            PYNETDICOM_IMPLEMENTATION_VERSION
        )

        # Default Implementation Class UID and Version Name
        self.implementation_class_uid = PYNETDICOM_IMPLEMENTATION_UID
        self.implementation_version_name = PYNETDICOM_IMPLEMENTATION_VERSION

        self.address = platform.node()
        self.port = port
        self.bind_addr = ''
        self.ae_title = ae_title

        # List of PresentationContext
        self._requested_contexts = []
        # {abstract_syntax : PresentationContext}
        self._supported_contexts = {}

        # The user may require the use of Extended Negotiation items
        self.extended_negotiation = []

        # List of active association objects
        self.active_associations = []

        # Default maximum simultaneous associations
        self.maximum_associations = 2

        # Default maximum PDU receive size (in bytes)
        self.maximum_pdu_size = 16382

        # Default timeouts - None means no timeout
        self.acse_timeout = 60
        self.network_timeout = None
        self.dimse_timeout = None

        # Require Calling/Called AE titles to match if value is non-empty str
        self.require_calling_aet = b''
        self.require_called_aet = b''

        self.local_socket = None

        # Used to terminate AE when running as an SCP
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
            LOGGER.warning("ACSE timeout set to 60 seconds")
            self._acse_timeout = 60

        for assoc in self.active_associations:
            assoc.acse_timeout = self.acse_timeout
            assoc.acse.acse_timeout = self.acse_timeout

    def add_requested_context(self, abstract_syntax,
                              transfer_syntax=DEFAULT_TRANSFER_SYNTAXES):
        """Add a Presentation Context to be proposed when sending Association
        requests.

        When an SCU sends an Association request to a peer it includes a list
        of presentation contexts it would like the peer to support [1]_. This
        method adds a single
        :py:class:`PresentationContext <pynetdicom3.presentation.PresentationContext>`
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

        >>> from pynetdicom3 import AE
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

        >>> from pynetdicom3 import AE
        >>> from pynetdicom3.sop_class import VerificationSOPClass
        >>> ae = AE()
        >>> ae.add_requested_context(VerificationSOPClass)

        Add a requested presentation context for *Verification SOP Class* with
        a transfer syntax of *Implicit VR Little Endian*.

        >>> from pydicom.uid import ImplicitVRLittleEndian
        >>> from pynetdicom3 import AE
        >>> from pynetdicom3.sop_class import VerificationSOPClass
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
        >>> from pynetdicom3 import AE
        >>> from pynetdicom3.sop_class import VerificationSOPClass
        >>> ae = AE()
        >>> ae.add_requested_context(VerificationSOPClass,
        ...                          [ImplicitVRLittleEndian, ExplicitVRBigEndian])
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
        .. [1] DICOM Standard, Part 8, `Section 7.1.1.13 <http://dicom.nema.org/medical/dicom/current/output/html/part08.html#sect_7.1.1.13>`_
        .. [2] DICOM Standard, Part 8, `Table 9-18 <http://dicom.nema.org/medical/dicom/current/output/html/part08.html#table_9-18>`_
        """
        if len(self.requested_contexts) >= 128:
            raise ValueError(
                "Failed to add the requested presentation context as there "
                "are already the maximum allowed number of requested contexts"
            )

        if hasattr(abstract_syntax, 'uid'):
            abstract_syntax = UID(abstract_syntax.uid)
        else:
            abstract_syntax = UID(abstract_syntax)

        # Allow single transfer syntax values for convenience
        if isinstance(transfer_syntax, str):
            transfer_syntax = [transfer_syntax]

        context = PresentationContext()
        context.abstract_syntax = abstract_syntax
        context.transfer_syntax = [UID(syntax) for syntax in transfer_syntax]

        self._requested_contexts.append(context)

    def add_supported_context(self, abstract_syntax,
                              transfer_syntax=DEFAULT_TRANSFER_SYNTAXES):
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

        Examples
        --------
        Add support for presentation contexts with an abstract syntax of
        *Verification SOP Class* and the default transfer syntaxes by using
        its UID value.

        >>> from pynetdicom3 import AE
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

        >>> from pynetdicom3 import AE
        >>> from pynetdicom3.sop_class import VerificationSOPClass
        >>> ae = AE()
        >>> ae.add_supported_context(VerificationSOPClass)

        Add support for presentation contexts with an abstract syntax of
        *Verification SOP Class* and a transfer syntax of *Implicit VR Little
        Endian*.

        >>> from pydicom.uid import ImplicitVRLittleEndian
        >>> from pynetdicom3 import AE
        >>> from pynetdicom3.sop_class import VerificationSOPClass
        >>> ae = AE()
        >>> ae.add_supported_context(VerificationSOPClass, ImplicitVRLittleEndian)
        >>> print(ae.supported_contexts[0])
        Abstract Syntax: Verification SOP Class
        Transfer Syntax(es):
            =Implicit VR Little Endian

        Add support for presentation contexts with an abstract syntax of
        *Verification SOP Class* and transfer syntaxes of *Implicit VR Little
        Endian* and *Explicit VR Big Endian* and then update the context to also
        support *Explicit VR Little Endian*.

        >>> from pydicom.uid import (
        ...     ImplicitVRLittleEndian, ExplicitVRLittleEndian, ExplicitVRBigEndian
        ... )
        >>> from pynetdicom3 import AE
        >>> from pynetdicom3.sop_class import VerificationSOPClass
        >>> ae = AE()
        >>> ae.add_supported_context(VerificationSOPClass,
                                     [ImplicitVRLittleEndian, ExplicitVRBigEndian])
        >>> ae.add_supported_context(VerificationSOPClass, ExplicitVRLittleEndian)
        >>> print(ae.supported_contexts[0])
        Abstract Syntax: Verification SOP Class
        Transfer Syntax(es):
            =Implicit VR Little Endian
            =Explicit VR Little Endian
            =Explicit VR Big Endian
        """
        if hasattr(abstract_syntax, 'uid'):
            abstract_syntax = UID(abstract_syntax.uid)
        else:
            abstract_syntax = UID(abstract_syntax)

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
        else:
            context = PresentationContext()
            context.abstract_syntax = abstract_syntax
            context.transfer_syntax = transfer_syntax

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

    def associate(self, addr, port, contexts=None, ae_title=b'ANY-SCP',
                  max_pdu=16382, ext_neg=None):
        """Send an association request to a remote AE.

        When requesting an association the local AE is acting as an SCU. The
        Association thread is returned whether or not the association is
        accepted and should be checked using ``Association.is_established``
        before sending any messages.

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

        Returns
        -------
        assoc : association.Association
            The Association thread

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

        peer_ae = {'ae_title' : validate_ae_title(ae_title),
                   'address' : addr,
                   'port' : port}

        # Associate
        assoc = Association(local_ae=self,
                            peer_ae=peer_ae,
                            acse_timeout=self.acse_timeout,
                            dimse_timeout=self.dimse_timeout,
                            max_pdu=max_pdu,
                            ext_neg=ext_neg)

        if contexts is None:
            contexts = self.requested_contexts
        else:
            self._validate_requested_contexts(contexts)

        # Set using a copy of the original to play nicely
        contexts = deepcopy(contexts)

        # Add the context IDs
        for ii, context in enumerate(contexts):
            context.context_id = 2 * ii + 1

        assoc.requested_contexts = contexts

        # PS3.8 Table 9.11, an A-ASSOCIATE-RQ must contain one or more
        #   Presentation Context items
        if not assoc.requested_contexts:
            raise RuntimeError(
                "Can't start an association with no requested presentation "
                "contexts"
            )

        # Send an A-ASSOCIATE request to the peer
        assoc.start()

        # Endlessly loops while the Association negotiation is taking place
        while (not assoc.is_established and not assoc.is_rejected and
               not assoc.is_aborted and not assoc.dul._kill_thread):
            # Program loops here endlessly sometimes
            time.sleep(0.1)

        # If the Association was established
        if assoc.is_established:
            self.active_associations.append(assoc)

        return assoc

    def _bind_socket(self):
        """Set up and bind the SCP socket.

        AE.start(): Set up and bind the socket. Separated out from start() to
        enable better unit testing
        """
        # The socket to listen for connections on, port is always specified
        self.local_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.local_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.local_socket.bind((self.bind_addr, self.port))
        # Listen for connections made to the socket, the backlog argument
        #   specifies the maximum number of queued connections.
        self.local_socket.listen(1)

    def cleanup_associations(self):
        """Remove dead associations."""
        # We can use threading.enumerate() to list all alive threads
        #   assoc.is_alive() is inherited from threading.thread
        self.active_associations = [
            assoc for assoc in self.active_associations if assoc.is_alive()
        ]

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
            LOGGER.warning("dimse_timeout set to never expire")
            self._dimse_timeout = None

        for assoc in self.active_associations:
            assoc.dimse_timeout = self.dimse_timeout
            assoc.dimse.dimse_timeout = self.dimse_timeout

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
            self._implementation_uid = uid
        else:
            pass

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
            LOGGER.warning("maximum_pdu_size set to 16382")

    def _monitor_socket(self):
        """Monitor the local socket for connections.

        AE.start(): Monitors the local socket to see if anyone tries to connect
        and if so, creates a new association. Separated out from start() to
        enable better unit testing
        """
        # FIXME: this needs to be dealt with properly
        try:
            read_list, _, _ = select.select([self.local_socket], [], [], 0)
        except (socket.error, ValueError):
            return

        # If theres a connection
        if read_list:
            client_socket, _ = self.local_socket.accept()
            client_socket.setsockopt(socket.SOL_SOCKET,
                                     socket.SO_RCVTIMEO,
                                     pack('ll', 10, 0))

            # Create a new Association
            # Association(local_ae, local_socket=None, max_pdu=16382)
            assoc = Association(self,
                                client_socket=client_socket,
                                max_pdu=self.maximum_pdu_size,
                                acse_timeout=self.acse_timeout,
                                dimse_timeout=self.dimse_timeout)
            assoc.supported_contexts = self.supported_contexts

            assoc.start()
            self.active_associations.append(assoc)

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
            LOGGER.warning("network_timeout set to never expire")
            self._network_timeout = None

        for assoc in self.active_associations:
            assoc.dul.dul_timeout = self.network_timeout

    @property
    def port(self):
        """Return the port number as an int."""
        return self._port

    @port.setter
    def port(self, value):
        """Set the port number."""
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, int) and value >= 0:
            self._port = value
        else:
            raise ValueError("AE port number must be an integer greater then "
                             "or equal to 0")

    def quit(self):
        """Stop the SCP."""
        self.stop()

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
        transfer_syntax : str/pydicom.uid.UID or list of str/pydicom.uid.UID, optional
            The transfer syntax(ex) you wish to stop requesting. If a list of
            str/UID then only those transfer syntaxes specified will no longer
            be requested. If not specified then the abstract syntax and all
            associated transfer syntaxes will no longer be requested (default).

        Examples
        --------
        Remove all requested presentation contexts with an abstract syntax of
        *Verification SOP Class* using its UID value.

        >>> from pynetdicom3 import AE
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

        >>> from pynetdicom3 import AE
        >>> from pynetdicom3.sop_class import VerificationSOPClass
        >>> ae = AE()
        >>> ae.add_requested_context(VerificationSOPClass)
        >>> ae.remove_requested_context(VerificationSOPClass)
        >>> len(ae.requested_contexts)
        0

        For all requested presentation contexts with an abstract syntax of
        *Verification SOP Class*, stop requesting a transfer syntax of *Implicit
        VR Little Endian*. If a presentation context exists which only has a
        single *Implicit VR Little Endian* transfer syntax then it will be
        completely removed, otherwise it will be kept with its remaining
        transfer syntaxes.

        Presentation context has only a single matching transfer syntax:

        >>> from pydicom.uid import ImplicitVRLittleEndian
        >>> from pynetdicom3 import AE
        >>> from pynetdicom3.sop_class import VerificationSOPClass
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
        >>> from pynetdicom3 import AE
        >>> from pynetdicom3.sop_class import VerificationSOPClass
        >>> ae = AE()
        >>> ae.add_requested_context(VerificationSOPClass)
        >>> print(ae.requested_contexts[0])
        Abstract Syntax: Verification SOP Class
        Transfer Syntax(es):
	        =Implicit VR Little Endian
	        =Explicit VR Little Endian
	        =Explicit VR Big Endian
        >>> ae.remove_requested_context(VerificationSOPClass,
        ...                             [ImplicitVRLittleEndian, ExplicitVRLittleEndian])
        >>> print(ae.requested_contexts[0])
        Abstract Syntax: Verification SOP Class
        Transfer Syntax(es):
	        =Explicit VR Big Endian
        """
        if hasattr(abstract_syntax, 'uid'):
            abstract_syntax = UID(abstract_syntax.uid)
        else:
            abstract_syntax = UID(abstract_syntax)

        # Get all the current requested contexts with the same abstract syntax
        matching_contexts = [
            cntx for cntx in self.requested_contexts if cntx.abstract_syntax == abstract_syntax
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
        transfer_syntax : str/pydicom.uid.UID or list of str/pydicom.uid.UID, optional
            The transfer syntax(ex) you wish to stop supporting. If a list of
            str/UID then only those transfer syntaxes specified will no longer
            be supported. If not specified then the abstract syntax and all
            associated transfer syntaxes will no longer be supported (default).

        Examples
        --------
        Remove the supported presentation context with an abstract syntax of
        *Verification SOP Class* using its UID value.

        >>> from pynetdicom3 import AE
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

        >>> from pynetdicom3 import AE, VerificationPresentationContexts
        >>> from pynetdicom3.sop_class import VerificationSOPClass
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
        >>> from pynetdicom3.sop_class import VerificationSOPClass
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
        >>> from pynetdicom3 import AE
        >>> from pynetdicom3.sop_class import VerificationSOPClass
        >>> ae = AE()
        >>> ae.add_supported_context(VerificationSOPClass)
        >>> print(ae.supported_contexts[0])
        Abstract Syntax: Verification SOP Class
        Transfer Syntax(es):
	        =Implicit VR Little Endian
	        =Explicit VR Little Endian
	        =Explicit VR Big Endian
        >>> ae.remove_supported_context(VerificationSOPClass,
        ...                             [ImplicitVRLittleEndian, ExplicitVRLittleEndian])
        >>> print(ae.supported_contexts[0])
        Abstract Syntax: Verification SOP Class
        Transfer Syntax(es):
	        =Explicit VR Big Endian
        """
        if hasattr(abstract_syntax, 'uid'):
            abstract_syntax = UID(abstract_syntax.uid)
        else:
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

        >>> from pynetdicom3 import AE, StoragePresentationContexts
        >>> ae = AE()
        >>> ae.requested_contexts = StoragePresentationContexts

        Set the requested presentation contexts using a list of
        `PresentationContext` items:

        >>> from pydicom.uid import ImplicitVRLittleEndian
        >>> from pynetdicom3 import AE
        >>> from pynetdicom3.presentation import PresentationContext
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
        """Return the required called AE title as a length 16 ``bytes``."""
        return self._require_called_aet

    @require_called_aet.setter
    def require_called_aet(self, ae_title):
        """Set the required called AE title.

        When an Association request is received the value of the 'Called AE
        Title' supplied by the peer will be compared with the set value and
        if they don't match the association will be rejected. If the set value
        is an empty bytes then the 'Called AE Title' will not be checked.

        Parameters
        ----------
        ae_title : bytes
            If not empty then any association requests that supply a
            Called AE Title value that does not match `ae_title` will be
            rejected.
        """
        if ae_title:
            self._require_called_aet = validate_ae_title(ae_title)
        else:
            self._require_called_aet = b''

    @property
    def require_calling_aet(self):
        """Return the required calling AE title as a length 16 ``bytes``."""
        return self._require_calling_aet

    @require_calling_aet.setter
    def require_calling_aet(self, ae_title):
        """Set the required calling AE title.

        When an Association request is received the value of the 'Calling AE
        Title' supplied by the peer will be compared with the set value and
        if they don't match the association will be rejected. If the set value
        is an empty bytes then the 'Calling AE Title' will not be checked.

        Parameters
        ----------
        ae_title : bytes
            If not empty then any association requests that supply a
            Calling AE Title value that does not match `ae_title` will be
            rejected.
        """
        if ae_title:
            self._require_calling_aet = validate_ae_title(ae_title)
        else:
            self._require_calling_aet = b''

    def start(self):
        """Start the AE as an SCP.

        When running the AE as an SCP this needs to be called to start the main
        loop, it listens for connections on `local_socket` and if they request
        association starts a new Association thread

        Successful associations get added to `active_associations`
        """
        # If the SCP has no supported SOP Classes then there's no point
        #   running as a server
        if not self.supported_contexts:
            LOGGER.error("No supported Presentation Contexts have been defined")
            raise ValueError(
                "No supported Presentation Contexts have been defined"
            )

        # Bind the local_socket to the specified listen port
        #try:
        self._bind_socket()
        #except OSError:
        #    self._quit = True
        #    self.stop()
        #    return

        no_loops = 0
        while True:
            try:
                # #60: Required so we don't max out the CPU
                time.sleep(0.5)

                if self._quit:
                    break

                # Monitor client_socket for association requests and
                #   appends any associations to self.active_associations
                self._monitor_socket()

                # Delete dead associations
                self.cleanup_associations()

                # Every 50 loops run the garbage collection
                if no_loops % 51 == 0:
                    gc.collect()
                    no_loops = 0

                no_loops += 1

            except KeyboardInterrupt:
                self.stop()

    def stop(self):
        """Stop the SCP.

        When running as an SCP, calling stop() will kill all associations,
        close the listen socket and quit
        """
        self._quit = True

        for assoc in self.active_associations:
            assoc.abort()

        if self.local_socket:
            self.local_socket.close()

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
                str_out +="\t\t{0!s}\n".format(transfer_syntax.name)

        str_out += "\n"
        str_out += "  Supported Presentation Contexts:\n"
        if not self.supported_contexts:
            str_out += "\tNone\n"
        for context in self.supported_contexts:
            str_out += "\t{0!s}\n".format(context.abstract_syntax.name)
            for transfer_syntax in context.transfer_syntax:
                str_out +="\t\t{0!s}\n".format(transfer_syntax.name)

        str_out += "\n"
        str_out += "  ACSE timeout: {0!s} s\n".format(self.acse_timeout)
        str_out += "  DIMSE timeout: {0!s} s\n".format(self.dimse_timeout)
        str_out += "  Network timeout: {0!s} s\n".format(self.network_timeout)

        if self.require_called_aet != '' or self.require_calling_aet != '':
            str_out += "\n"
        if self.require_calling_aet != '':
            str_out += "  Required calling AE title: {0!s}\n" \
                       .format(self.require_calling_aet)
        if self.require_called_aet != '':
            str_out += "  Required called AE title: {0!s}\n" \
                       .format(self.require_called_aet)

        str_out += "\n"

        # Association information
        str_out += '  Association(s): {0!s}/{1!s}\n' \
                   .format(len(self.active_associations),
                           self.maximum_associations)

        for assoc in self.active_associations:
            str_out += '\tPeer: {0!s} on {1!s}:{2!s}\n' \
                       .format(assoc.peer_ae['ae_title'],
                               assoc.peer_ae['address'],
                               assoc.peer_ae['port'])

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
        >>> from pynetdicom3 import AE
        >>> from pynetdicom3.presentation import PresentationContext
        >>> context = PresentationContext()
        >>> context.abstract_syntax = '1.2.840.10008.1.1'
        >>> context.transfer_syntax = [ImplicitVRLittleEndian]
        >>> ae = AE()
        >>> ae.supported_contexts = [context]

        Set the supported presentation contexts using an inbuilt list of service
        specific `PresentationContext` items:

        >>> from pynetdicom3 import AE, StoragePresentationContexts
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

    # Association negotiation callbacks
    def on_user_identity_negotiation(self, user_id_type, primary_field,
                                     secondary_field):
        """Callback for when a peer requests user identity negotiations.

        See PS3.7 Annex D.3.3.7.1

        Experimental and will definitely change

        Parameters
        ----------
        user_id_type : int
            The *User Identity Type* value (1, 2, 3, 4).
        primary_field : bytes
            The of the *Primary Field* value.
        secondary_field : bytes or None
            The *Secondary Field* value. Will be ``None`` unless the
            *User Identity Type* is ``2``

        Returns
        -------
        response : bytes or None
            If ``user_id_type`` is :

            * 1 or 2, then return ``b''``.
            * 3 then return the Kerberos Server ticket.
            * 4 then return the SAML response.

            If the identity check fails then return ``None``.
        """
        raise NotImplementedError


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
                  'originator_aet' : bytes or None, the move originator's AE title
                  'originator_message_id' : int or None, the move originator's message ID
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
          `9.3.5 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.5>`_ and
          `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_

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
          `CC <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_CC>`_ and
          `HH <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_HH>`_
        * DICOM Standard Part 7, Sections
          `9.1.2 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.1.2>`_,
          `9.3.2 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.2>`_ and
          `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_
        """
        raise NotImplementedError("User must implement the AE.on_c_find "
                                  "function prior to calling AE.start()")

    def on_c_find_cancel(self):
        """Callback for when a C-FIND-CANCEL request is received.

        Returns
        -------
        bool
            True if you want to stop the C-FIND operation, False otherwise.
        """
        raise NotImplementedError("User must implement the "
                                  "AE.on_c_find_cancel function prior to "
                                  "calling AE.start()")

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
          | ``0xB000`` Sub-operations complete, one or more failures or warnings

        Pending
          | ``0xFF00`` Matches are continuing - Current Match is supplied and any
            Optional Keys were supported in the same manner as Required Keys

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
          `BB <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_BB>`_ and
          `HH <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_HH>`_
        * DICOM Standard Part 7, Sections
          `9.1.3 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.1.3>`_,
          `9.3.3 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.3>`_ and
          `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_
        """
        raise NotImplementedError("User must implement the AE.on_c_get "
                                  "function prior to calling AE.start()")

    def on_c_get_cancel(self):
        """Callback for when a C-GET-CANCEL request is received."""
        raise NotImplementedError("User must implement the "
                                  "AE.on_c_get_cancel function prior to "
                                  "calling AE.start()")

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
          `BB <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_BB>`_ and
          `HH <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_HH>`_
        * DICOM Standard Part 7, Sections
          `9.1.4 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.1.4>`_,
          `9.3.4 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.4>`_ and
          `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_
        """
        raise NotImplementedError("User must implement the AE.on_c_move "
                                  "function prior to calling AE.start()")

    def on_c_move_cancel(self):
        """Callback for when a C-MOVE-CANCEL request is received."""
        raise NotImplementedError("User must implement the "
                                  "AE.on_c_move_cancel function prior to "
                                  "calling AE.start()")

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
        dataset : pydicom.dataset.Dataset
            The DICOM dataset sent by the peer in the C-STORE request.
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
                  'originator_aet' : bytes or None, the move originator's AE title
                  'originator_message_id' : int or None, the move originator's message ID
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
          `FF <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_FF>`_ and
          `GG <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_GG>`_
        * DICOM Standard Part 7, Sections
          `9.1.1 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.1.1>`_,
          `9.3.1 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.1>`_ and
          `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_
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
        associate_rq_pdu : pynetdicom3.pdu.A_ASSOCIATE_RJ
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
