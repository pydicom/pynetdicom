
.. _assoc_scu:

.. currentmodule:: pynetdicom.association

Requesting an association
-------------------------

Assuming you :ref:`have an AE <ae_create_scu>` and have added your requested
presentation contexts then you can associate with a peer by using the
:meth:`AE.associate()<pynetdicom.ae.ApplicationEntity.associate>`
method, which returns an :class:`Association` thread:

.. code-block:: python

    from pynetdicom import AE
    from pynetdicom.sop_class import Verification

    ae = AE()
    ae.add_requested_context(Verification)

    # Associate with the peer at IPv4 address 127.0.0.1 and port 11112
    #   IPv6 is also supported
    assoc = ae.associate("127.0.0.1", 11112)

    # Release the association
    if assoc.is_established:
        assoc.release()

This sends an association request to the IPv4 address ``127.0.0.1`` on port
``11112`` with the request containing the presentation contexts from
:attr:`AE.requested_contexts<pynetdicom.ae.ApplicationEntity.requested_contexts>`
and the default *Called AE Title* parameter of ``'ANY-SCP'``.

Established associations should always be released or aborted (using
:func:`Association.release` or :func:`Association.abort`), otherwise the
association will remain open until either the peer or local AE hits a timeout
and aborts.


Specifying the Called AE Title
..............................

Some SCPs will reject an association request if the *Called AE Title* parameter
value doesn't match its own title, so this can be set using the *ae_title*
keyword parameter:

.. code-block:: python

    assoc = ae.associate("127.0.0.1", 11112, ae_title='STORE_SCP')

Specifying presentation contexts per association
................................................

Calling :meth:`AE.associate()<pynetdicom.ae.ApplicationEntity.associate>`
with only the *addr* and *port* parameters means the presentation
contexts in
:attr:`AE.requested_contexts<pynetdicom.ae.ApplicationEntity.requested_contexts>`
will be used with the association. To propose presentation contexts on a
per-association basis you can use the *contexts* keyword parameter:

.. code-block:: python

    from pynetdicom import AE, build_context

    ae = AE()
    requested_contexts = [build_context('1.2.840.10008.1.1')]
    assoc = ae.associate("127.0.0.1", 11112, contexts=requested_contexts)

    if assoc.is_established:
        assoc.release()

.. _user_assoc_extneg:

Using Extended Negotiation
..........................

If you require the use of :ref:`extended negotiation <concepts_negotiation>`
then you can supply the *ext_neg* keyword parameter. Some extended negotiation
items can only be singular and some can occur multiple times depending on the
service class and intended usage. The following example shows how to add
*SCP/SCU Role Selection Negotiation* items using
:func:`~pynetdicom.presentation.build_role` when requesting the use of the
Query/Retrieve (QR) Service Class' C-GET service (in this example the QR SCU is
also acting as a Storage SCP), plus a *User Identity Negotiation* item:

.. code-block:: python

    from pynetdicom import AE, StoragePresentationContexts, build_role
    from pynetdicom.pdu_primitives import UserIdentityNegotiation
    from pynetdicom.sop_class import PatientRootQueryRetrieveInformationModelGet

    ae = AE()
    # Contexts supported as a Storage SCP - requires Role Selection
    #   Note that we are limited to a maximum of 128 contexts.
    #   StoragePresentationContexts includes 120, it is therefore
    #   possible to add 8 additional presentation contexts if needed.
    ae.requested_contexts = StoragePresentationContexts
    # Contexts proposed as a QR SCU
    ae.add_requested_context = PatientRootQueryRetrieveInformationModelGet

    # Add role selection items for the contexts we will be supporting as an SCP
    negotiation_items = []
    for context in StoragePresentationContexts:
        role = build_role(context.abstract_syntax, scp_role=True)
        negotiation_items.append(role)

    # Add user identity negotiation request - passwords are sent in the clear!
    user_identity = UserIdentityNegotiation()
    user_identity.user_identity_type = 2
    user_identity.primary_field = b'username'
    user_identity.secondary_field = b'password'
    negotiation_items.append(user_identity)

    # Associate with the peer at IP address 127.0.0.1 and port 11112
    assoc = ae.associate("127.0.0.1", 11112, ext_neg=negotiation_items)

    if assoc.is_established:
        assoc.release()

Possible extended negotiation items are:

.. currentmodule:: pynetdicom.pdu_primitives

* :class:`Asynchronous Operations Window Negotiation
  <AsynchronousOperationsWindowNegotiation>`
* :class:`SCP/SCU Role Selection Negotiation<SCP_SCU_RoleSelectionNegotiation>`
* :class:`SOP Class Extended Negotiation<SOPClassExtendedNegotiation>`
* :class:`SOP Class Common Extended Negotiation
  <SOPClassCommonExtendedNegotiation>`
* :class:`User Identity Negotiation <UserIdentityNegotiation>`

Binding event handlers
......................

.. currentmodule:: pynetdicom.association

If you want to bind handlers to any
:ref:`events <user_events>` within a new :class:`Association` you can
use the *evt_handlers* keyword parameter:

.. code-block:: python

    import logging

    from pynetdicom import AE, evt, debug_logger
    from pynetdicom.sop_class import Verification

    debug_logger()
    LOGGER = logging.getLogger('pynetdicom')

    def handle_open(event):
        """Print the remote's (host, port) when connected."""
        LOGGER.info(f"Connected with remote at {event.address}")

    def handle_accepted(event, arg1, arg2):
        """Demonstrate the use of the optional extra parameters"""
        LOGGER.info(f"Extra args: '{arg1}' and '{arg2}'")

    # If a 2-tuple then only `event` parameter
    # If a 3-tuple then the third value should be a list of objects to pass the handler
    handlers = [
        (evt.EVT_CONN_OPEN, handle_open),
        (evt.EVT_ACCEPTED, handle_accepted, ['optional', 'parameters']),
    ]

    ae = AE()
    ae.add_requested_context(Verification)
    assoc = ae.associate("127.0.0.1", 11112, evt_handlers=handlers)

    if assoc.is_established:
        assoc.release()

Handlers can also be bound and unbound from events in an existing
:class:`Association`:

.. code-block:: python

    import logging

    from pynetdicom import AE, evt, debug_logger
    from pynetdicom.sop_class import Verification

    debug_logger()
    LOGGER = logging.getLogger('pynetdicom')

    def handle_open(event):
        """Print the remote's (host, port) when connected."""
        LOGGER.info(f"Connected with remote at {event.address}")

    def handle_close(event):
        """Print the remote's (host, port) when disconnected."""
        LOGGER.info(f"Disconnected from remote at {event.address}")

    handlers = [(evt.EVT_CONN_OPEN, handle_open)]

    ae = AE()
    ae.add_requested_context(Verification)
    assoc = ae.associate("127.0.0.1", 11112, evt_handlers=handlers)

    assoc.unbind(evt.EVT_CONN_OPEN, handle_open)
    assoc.bind(evt.EVT_CONN_CLOSE, handle_close)

    if assoc.is_established:
        assoc.release()


Using TLS connections
.....................

The client socket used for the association can be wrapped in TLS by supplying
the *tls_args* keyword parameter to
:meth:`~pynetdicom.ae.ApplicationEntity.associate`:

.. code-block:: python

    import ssl

    from pynetdicom import AE
    from pynetdicom.sop_class import Verification

    ae = AE()
    ae.add_requested_context(Verification)

    # Create the SSLContext, your requirements may vary
    ssl_cx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH, cafile='server.crt')
    ssl_cx.verify_mode = ssl.CERT_REQUIRED
    ssl_cx.load_cert_chain(certfile='client.crt', keyfile='client.key')

    assoc = ae.associate("127.0.0.1", 11112, tls_args=(ssl_cx, None))

    if assoc.is_established:
        assoc.release()

Where *tls_args* is (:class:`ssl.SSLContext`, *host*), where *host* is the
value of the *server_hostname* keyword parameter in
:meth:`~ssl.SSLContext.wrap_socket`.


Outcomes of an association request
..................................
There are four potential outcomes of an association request: acceptance and
establishment, association rejection, association abort or a connection
failure, so its a good idea to test for establishment before attempting to
use the association:

.. code-block:: python

    from pynetdicom import AE
    from pynetdicom.sop_class import Verification

    ae = AE()
    ae.add_requested_context(Verification)

    # Associate with the peer at IP address 127.0.0.1 and port 11112
    assoc = ae.associate("127.0.0.1", 11112)

    if assoc.is_established:
        # Do something useful...
        pass

        # Release
        assoc.release()


Using the association
---------------------
Once an association has been established with the peer then the agreed upon
set of services are available for use. *pynetdicom* supports the usage
of the following DIMSE services:

.. currentmodule:: pynetdicom.association.Association

* C-ECHO, through the :meth:`Association.send_c_echo()<send_c_echo>` method
* C-STORE, through the :meth:`Association.send_c_store()<send_c_store>` method
* C-FIND, through the :meth:`Association.send_c_find()<send_c_find>` method
* C-GET, through the :meth:`Association.send_c_get()<send_c_get>` method.
  Any AE that uses the C-GET service will also be providing the C-STORE
  service and must implement and bind a handler for ``evt.EVT_C_STORE`` (as
  outlined :doc:`here <association_accepting>`)
* C-MOVE, through the :meth:`Association.send_c_move()<send_c_move>` method.
  The move destination can either be a different AE or the AE that made
  the C-MOVE request (provided a non-blocking Storage SCP has been started).
* N-ACTION, through the :meth:`Association.send_n_action()<send_n_action>`
  method
* N-CREATE, through the :meth:`Association.send_n_create()<send_n_create>`
  method
* N-DELETE, through the :meth:`Association.send_n_delete()<send_n_delete>`
  method
* N-EVENT-REPORT, through the :meth:`Association.send_n_event_report()
  <send_n_event_report>` method.
* N-GET, through the :meth:`Association.send_n_get()<send_n_get>` method.
* N-SET, through the :meth:`Association.send_n_set()<send_n_set>` method.

Attempting to use a service without an established association will raise a
:class:`RuntimeError`, while attempting to use a service that is not supported
by the association will raise a :class:`ValueError`.

For more information on using the services available to an association please
read through the :doc:`examples<../examples/index>` corresponding to the
service class you're interested in.

Releasing the association
.........................

.. currentmodule:: pynetdicom.association

Once your association has been established and you've finished using it, its a
good idea to release the association using :meth:`Association.release`, otherwise
the association will remain open until the network timeout expires or the
peer aborts or closes the connection.

Accessing User Identity responses
---------------------------------

If the association *Requestor* has sent a
:dcm:`User Identity Negotiation<part07/sect_D.3.3.7.html>`
item as part of the extended negotiation and has requested a response in the
event of a positive identification then it can be accessed via the
:attr:`Association.acceptor.user_identity<ServiceUser.user_identity>`
property after the association has been established.
