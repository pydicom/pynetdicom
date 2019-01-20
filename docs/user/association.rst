.. _association:

Association
===========

.. _assoc_scu:

Requesting an Association (SCU)
-------------------------------

Assuming you :ref:`have an AE <ae_create_scu>` and have added your requested presentation contexts
then you can associate with a peer by using the
:py:meth:`AE.associate() <pynetdicom.ae.ApplicationEntity.associate>`
method, which returns an
:py:class:`Association <pynetdicom.association.Association>`
thread:

::

    from pynetdicom import AE
    from pynetdicom.sop_class import VerificationSOPClass

    ae = AE()
    ae.add_requested_context(VerificationSOPClass)

    # Associate with the peer at IP address 127.0.0.1 and port 11112
    assoc = ae.associate('127.0.0.1', 11112)

This sends an association request to the IP address '127.0.0.1' on port 11112
with the request containing the presentation contexts from
:py:obj:`AE.requested_contexts <pynetdicom.ae.ApplicationEntity.requested_contexts>`
and the default *Called AE Title* parameter of ``b'ANY-SCP         '``.

Specifying the Called AE Title
..............................
Some SCPs will reject an association request if the *Called AE Title* parameter
value doesn't match its own title, so this can be set using the ``ae_title``
parameter:

>>> assoc = ae.associate('127.0.0.1', 11112, ae_title=b'STORE_SCP')

Specifying Presentation Contexts for each Association
.....................................................
Calling
:py:meth:`AE.associate() <pynetdicom.ae.ApplicationEntity.associate>`
with only the ``addr`` and ``port`` parameters means the presentation
contexts in
:py:obj:`AE.requested_contexts <pynetdicom.ae.ApplicationEntity.requested_contexts>`
will be used with the association. To propose presentation contexts on a
per-association basis you can use the ``contexts`` parameter:

::

    from pynetdicom import AE, build_context

    ae = AE()
    requested_contexts = [build_context('1.2.840.10008.1.1')]
    assoc = ae.associate('127.0.0.1', 11112, contexts=requested_contexts)

Using Extended Negotiation
..........................
If you require the use of :ref:`extended negotiation <concepts_negotiation>`
then you can supply the ``ext_neg`` parameter. Some extended negotiation
items can only be singular and some can occur multiple times depending on the
service class and intended usage. The following example shows how to add
SCP/SCU Role Selection Negotiation items when requesting the use of the
Query/Retrieve (QR) Service Class' C-GET service (in this example the QR SCU is
also acting as a Storage SCP), plus a User Identity Negotiation item:

::

    from pynetdicom import (
        AE,
        StoragePresentationContexts,
        QueryRetrievePresentationContexts
    )
    from pynetdicom.pdu_primitives import (
        SCP_SCU_RoleSelectionNegotiation,
        UserIdentityNegotiation,
    )

    ae = AE()
    # Presentation contexts proposed as a QR SCU
    ae.requested_contexts = QueryRetrievePresentationContexts
    # Presentation contexts supported as a Storage SCP: requires Role Selection
    ae.requested_contexts = StoragePresentationContexts

    # Add role selection items for the storage contexts we will be supporting
    #   as an SCP
    negotiation_items = []
    for context in StoragePresentationContexts:
        role = SCP_SCU_RoleSelectionNegotiation()
        role.sop_class_uid = context.abstract_syntax
        role.scp_role = True
        negotiation_items.append(role)

    # Add user identity negotiation request
    user_identity = UserIdentityNegotiation()
    user_identity.user_identity_type = 2
    user_identity.primary_field = b'username'
    user_identity.secondary_field = b'password'
    negotiation_items.append(user_identity)

    # Associate with the peer at IP address 127.0.0.1 and port 11112
    assoc = ae.associate('127.0.0.1', 11112, ext_neg=negotiation_items)

Possible extended negotiation items are:

* :py:class:`Asynchronous Operations Window Negotiation <pynetdicom.pdu_primitives.AsynchronousOperationsWindowNegotiation>`
* :py:class:`SCP/SCU Role Selection Negotiation <pynetdicom.pdu_primitives.SCP_SCU_RoleSelectionNegotiation>`
* :py:class:`SOP Class Extended Negotiation <pynetdicom.pdu_primitives.SOPClassExtendedNegotiation>`
* :py:class:`SOP Class Common Negotiation <pynetdicom.pdu_primitives.SOPClassCommonExtendedNegotiation>`
* :py:class:`User Identity Negotiation <pynetdicom.pdu_primitives.UserIdentityNegotiation>`


TLS
...

The client socket used for the association can be wrapped in TLS by supplying
the ``tls_args`` keyword parameter to ``associate()``:

::

    import ssl

    from pynetdicom import AE
    from pynetdicom.sop_class import VerificationSOPClass

    ae = AE()
    ae.add_requested_context(VerificationSOPClass)

    # Create the SSLContext, your requirements may vary
    ssl_cx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH, cafile='server.crt')
    ssl_cx.verify_mode = ssl.CERT_REQUIRED
    ssl_cx.load_cert_chain(certfile='client.crt', keyfile='client.key')

    assoc = ae.associate('127.0.0.1', 11112, tls_args=(ssl_cx, None))
    if assoc.is_established:
        # Do something with the association
        pass

        # Once we are finished, release the association
        assoc.release()

``tls_args`` is
(`SSLContext <https://docs.python.org/3/library/ssl.html#ssl.SSLContext.wrap_socket>`_,
*host*), where *host* is the value of the ``server_hostname`` keyword parameter in ``SSLContext.wrap_socket()``.


Outcomes of an Association Request
..................................
There are four potential outcomes of an association request: acceptance and
establishment, association rejection, association abort or a connection
failure, so its a good idea to test for establishment prior to attempting to use
the Association:

::

    from pynetdicom import AE
    from pynetdicom.sop_class import VerificationSOPClass

    ae = AE()
    ae.add_requested_context(VerificationSOPClass)

    # Associate with the peer at IP address 127.0.0.1 and port 11112
    assoc = ae.associate('127.0.0.1', 11112)
    if assoc.is_established:
        # Do something with the association
        pass

        # Once we are finished, release the association
        assoc.release()


Using an Association (SCU)
--------------------------
Once an association has been established with the peer then the agreed upon
set of services are available for use. Currently pynetdicom supports the usage
of the following DIMSE-C services:

* C-ECHO, through the
  :py:meth:`Association.send_c_echo() <pynetdicom.association.Association.send_c_echo>`
  method
* C-STORE, through the
  :py:meth:`Association.send_c_store() <pynetdicom.association.Association.send_c_store>`
  method
* C-FIND, through the
  :py:meth:`Association.send_c_find() <pynetdicom.association.Association.send_c_find>`
  method
* C-GET, through the
  :py:meth:`Association.send_c_get() <pynetdicom.association.Association.send_c_get>`
  method. Any AE that uses the C-GET service will also be providing the C-STORE
  service and must implement the
  :py:meth:`AE.on_c_store() <pynetdicom.ae.ApplicationEntity.on_c_store>`
  callback (as outlined :ref:`here <assoc_scp>`)
* C-MOVE, through the
  :py:meth:`Association.send_c_move() <pynetdicom.association.Association.send_c_move>`
  method. The performing SCP may either send the requested datasets over a new
  association to the move destination or (if the SCU is the destination) over
  the existing association so in that case you should implement the
  :py:meth:`AE.on_c_store() <pynetdicom.ae.ApplicationEntity.on_c_store>`
  callback.

Attempting to use a service without an established association will raise a
``RuntimeError``, while attempting to use a service that is not supported by
the association will raise a ``ValueError``.

For more information on using the services available to an association please
read through the :ref:`examples <index_examples>` corresponding to the
service class you're interested in.

Releasing an Association
........................

Once your association has been established and you've finished using it, its a
good idea to release the association using ``Association.release()``, otherwise
the association will remain open until the network timeout expires or the
peer aborts or closes the connection.

Accessing User Identity Responses
---------------------------------

If the association *Requestor* has sent a
`User Identity Negotiation <http://dicom.nema.org/medical/dicom/current/output/chtml/part07/sect_D.3.3.7.html>`_
item as part of the extended negotiation and has requested a response in the
event of a positive identification then it can be accessed via the
:py:meth:`Assocation.acceptor.user_identity <pynetdicom.association.Association.acceptor.user_identity>`
property after the association has been established.

.. _assoc_scp:

Listening for Association Requests (SCP)
----------------------------------------
Assuming you have added your supported presentation contexts then you can start
listening for association requests from peers with the
:py:meth:`AE.start_server() <pynetdicom.ae.ApplicationEntity.start_server>`
method:

::

    from pynetdicom import AE
    from pynetdicom.sop_class import VerificationSOPClass

    ae.add_supported_context(VerificationSOPClass)

    # Listen for association requests
    ae.start_server(('', 11112))

The above is suitable as an implementation of the Verification Service
Class, however other service classes will require that you implement one
or more of the AE service class callbacks.

The association server can be started in both blocking (default) and
non-blocking modes:

::

    from pynetdicom import AE
    from pynetdicom.sop_class import VerificationSOPClass

    ae.add_supported_context(VerificationSOPClass)

    # Returns a ThreadedAssociationServer instance
    server = ae.start_server(('', 11112), block=False)

    # Blocks
    ae.start_server(('', 11113), block=True)

The returned
:py:class:`ThreadedAssociationServer <pynetdicom.transport.ThreadedAssociationServer>`
instances can be stopped using ``shutdown()`` and all active association
can be stopped using ``AE.shutdown()``.


TLS
...

The client sockets generated by the association server can also be wrapped in
TLS by  supplying a `ssl.SSLContext <https://docs.python.org/3/library/ssl.html#ssl.SSLContext.wrap_socket>`_
instance via the ``ssl_context`` keyword parameter:

::

    import ssl

    from pynetdicom import AE
    from pynetdicom.sop_class import VerificationSOPClass

    ae.add_supported_context(VerificationSOPClass)

    # Create the SSLContext, your requirements may vary
    ssl_cx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_cx.verify_mode = ssl.CERT_REQUIRED
    ssl_cx.load_cert_chain(certfile='server.crt', keyfile='server.key')
    ssl_cx.load_verify_locations(cafile='client.crt')

    server = ae.start_server(('', 11112), block=False, ssl_context=ssl_cx)


Providing DIMSE Services (SCP)
------------------------------

If the association supports a service class that uses one or more of the
DIMSE-C services then the corresponding callback(s) should be implemented
(excluding C-ECHO which has a default implementation that always returns a
0x0000 *Success* response):

* C-ECHO: :py:meth:`AE.on_c_echo() <pynetdicom.ae.ApplicationEntity.on_c_echo>`
* C-STORE: :py:meth:`AE.on_c_store() <pynetdicom.ae.ApplicationEntity.on_c_store>`
* C-FIND: :py:meth:`AE.on_c_find() <pynetdicom.ae.ApplicationEntity.on_c_find>`
* C-GET: :py:meth:`AE.on_c_get() <pynetdicom.ae.ApplicationEntity.on_c_get>`
* C-MOVE: :py:meth:`AE.on_c_move() <pynetdicom.ae.ApplicationEntity.on_c_move>`

For instance, if your SCP is to support the Storage Service then you would
implement the ``on_c_store`` callback in manner similar to:

::

    from pynetdicom import AE
    from pynetdicom.sop_class import VerificationSOPClass

    ae = AE()
    ae.add_supported_context(VerificationSOPClass)

    def on_c_store(ds, context, info):
        """Store the pydicom Dataset `ds`.

        Parameters
        ----------
        ds : pydicom.dataset.Dataset
            The dataset that the peer has requested be stored.
        context : namedtuple
            The presentation context that the dataset was sent under.
        info : dict
            Information about the association and storage request.

        Returns
        -------
        status : int or pydicom.dataset.Dataset
            The status returned to the peer AE in the C-STORE response. Must be
            a valid C-STORE status value for the applicable Service Class as
            either an ``int`` or a ``Dataset`` object containing (at a
            minimum) a (0000,0900) *Status* element.
        """
        # This is just a toy implementation that doesn't store anything and
        # always returns a Success response
        return 0x0000

    ae.on_c_store = on_c_store

    # Listen for association requests
    ae.start_server(('', 11112))

For more detailed information on implementing the DIMSE service
provider callbacks please see their API reference documentation and the
:ref:`examples <index_examples>` corresponding to the service class you're
interested in.
