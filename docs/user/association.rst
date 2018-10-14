.. _association:

Association
===========

.. _assoc_scu:

Requesting an Association (SCU)
-------------------------------

Assuming you :ref:`have an AE <ae_create_scu>` and have added your requested presentation contexts
then you can associate with a peer by using the
:py:meth:`AE.associate() <pynetdicom3.ae.ApplicationEntity.associate>`
method, which returns an
:py:class:`Association <pynetdicom3.association.Association>`
thread:

::

    from pynetdicom3 import AE
    from pynetdicom3.sop_class import VerificationSOPClass

    ae = AE()
    ae.add_requested_context(VerificationSOPClass)

    # Associate with the peer at IP address 127.0.0.1 and port 11112
    assoc = ae.associate('127.0.0.1', 11112)

This sends an association request to the IP address '127.0.0.1' on port 11112
with the request containing the presentation contexts from
:py:obj:`AE.requested_contexts <pynetdicom3.ae.ApplicationEntity.requested_contexts>`
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
:py:meth:`AE.associate() <pynetdicom3.ae.ApplicationEntity.associate>`
with only the ``addr`` and ``port`` parameters means the presentation
contexts in
:py:obj:`AE.requested_contexts <pynetdicom3.ae.ApplicationEntity.requested_contexts>`
will be used with the association. To propose presentation contexts on a
per-association basis you can use the ``contexts`` parameter:

::

    from pynetdicom3 import AE, build_context

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
also acting as a Storage SCP):

::

    from pynetdicom3 import (
        AE,
        StoragePresentationContexts,
        QueryRetrievePresentationContexts
    )
    from pynetdicom3.pdu_primitives import SCP_SCU_RoleSelectionNegotiation

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

    # Associate with the peer at IP address 127.0.0.1 and port 11112
    assoc = ae.associate('127.0.0.1', 11112, ext_neg=negotiation_items)

Possible extended negotiation items are:

* :py:class:`Asynchronous Operations Window Negotiation <pynetdicom3.pdu_primitives.AsynchronousOperationsWindowNegotiation>`
* :py:class:`SCP/SCU Role Selection Negotiation <pynetdicom3.pdu_primitives.SCP_SCU_RoleSelectionNegotiation>`
* :py:class:`SOP Class Extended Negotiation <pynetdicom3.pdu_primitives.SOPClassExtendedNegotiation>`
* :py:class:`SOP Class Common Negotiation <pynetdicom3.pdu_primitives.SOPClassCommonExtendedNegotiation>`
* :py:class:`User Identity Negotiation <pynetdicom3.pdu_primitives.UserIdentityNegotiation>`


Outcomes of an Association Request
..................................
There are four potential outcomes of an association request: acceptance and
establishment, association rejection, association abort or a connection
failure, so its a good idea to test for establishment prior to attempting to use
the Association:

::

    from pynetdicom3 import AE
    from pynetdicom3.sop_class import VerificationSOPClass

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
  :py:meth:`Association.send_c_echo() <pynetdicom3.association.Association.send_c_echo>`
  method
* C-STORE, through the
  :py:meth:`Association.send_c_store() <pynetdicom3.association.Association.send_c_store>`
  method
* C-FIND, through the
  :py:meth:`Association.send_c_find() <pynetdicom3.association.Association.send_c_find>`
  method
* C-GET, through the
  :py:meth:`Association.send_c_get() <pynetdicom3.association.Association.send_c_get>`
  method. Any AE that uses the C-GET service will also be providing the C-STORE
  service and must implement the
  :py:meth:`AE.on_c_store() <pynetdicom3.ae.ApplicationEntity.on_c_store>`
  callback (as outlined :ref:`here <assoc_scp>`)
* C-MOVE, through the
  :py:meth:`Association.send_c_move() <pynetdicom3.association.Association.send_c_move>`
  method. The current implementation of pynetdicom doesn't support the C-MOVE
  SCU being the destination for the storage of requested datasets (the C-STORE
  SCP).

Attempting to use a service without an established association will raise a
``RuntimeError``, while attempting to use a service that is not supported by
the association will raise a ``ValueError``.

For more information on using the services available to an association please
read through the :ref:`examples <index_examples>` corresponding to the
service class you're interested in.

.. _assoc_scp:

Listening for Association Requests (SCP)
----------------------------------------
Assuming you :ref:`have an AE <ae_create_scp>` set to listen on port 11112
and have added your supported presentation contexts then you can start
listening for association requests from peers with the
:py:meth:`AE.start() <pynetdicom3.ae.ApplicationEntity.start>`
method:

::

    from pynetdicom3 import AE
    from pynetdicom3.sop_class import VerificationSOPClass

    ae = AE(port=11112)
    ae.add_supported_context(VerificationSOPClass)

    # Listen for association requests
    ae.start()

The above is suitable as an implementation of the Verification Service
Class, however other service classes will require that you implement one
or more of the AE service class callbacks.

Providing DIMSE Services (SCP)
------------------------------

If the association supports a service class that uses one or more of the
DIMSE-C services then the corresponding callback(s) should be implemented
(excluding C-ECHO which has a default implementation that always returns a
0x0000 *Success* response):

* C-ECHO: :py:meth:`AE.on_c_echo() <pynetdicom3.ae.ApplicationEntity.on_c_echo>`
* C-STORE: :py:meth:`AE.on_c_store() <pynetdicom3.ae.ApplicationEntity.on_c_store>`
* C-FIND: :py:meth:`AE.on_c_find() <pynetdicom3.ae.ApplicationEntity.on_c_find>`
* C-GET: :py:meth:`AE.on_c_get() <pynetdicom3.ae.ApplicationEntity.on_c_get>`
* C-MOVE: :py:meth:`AE.on_c_move() <pynetdicom3.ae.ApplicationEntity.on_c_move>`

For instance, if your SCP is to support the Storage Service then you would
implement the ``on_c_store`` callback in manner similar to:

::

    from pynetdicom3 import AE
    from pynetdicom3.sop_class import VerificationSOPClass

    ae = AE(port=11112)
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
    ae.start()

For more detailed information on implementing the DIMSE service
provider callbacks please see their API reference documentation and the
:ref:`examples <index_examples>` corresponding to the service class you're
interested in.
