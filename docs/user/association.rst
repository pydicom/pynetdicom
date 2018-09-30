.. _association:

Association
===========

Requesting an Association (SCU)
-------------------------------

Once the requested presentation contexts have been added you can associate with
a peer by using the
:py:meth:`AE.associate() <pynetdicom3.ae.ApplicationEntity.associate>`
method which returns an
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
and the default *Called AE Title* of ``b'ANY-SCP         '``.

Specifying the Called AE Title
..............................
Some SCPs will reject an association request if the *Called AE Title* doesn't
match its own title, so this can be set using the ``ae_title`` parameter:

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
Query/Retrieve Service Class' C-GET service (in this example the QR SCU is
also acting as a Storage SCP):

::

    from pynetdicom3 import (
        AE,
        StoragePresentationContexts,
        QueryRetrievePresentationContexts
    )
    from pynetdicom3.pdu_primitives import SCP_SCU_RoleSelectionNegotiation

    ae = AE()
    ae.requested_contexts = QueryRetrievePresentationContexts
    ae.supported_contexts = StoragePresentationContexts

    negotiation_items = []
    for context in ae.supported_contexts:
        role = SCP_SCU_RoleSelectionNegotiation()
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
        # Do something with the association...
        pass

        # Once we are finished, release the association
        assoc.release()


Using an Association (SCU)
--------------------------
Once an association has been established with the peer then the agreed upon
set of services are available for use. Currently pynetdicom supports the usage
of the following DIMSE-C services:

* C-ECHO, through the assoc.send_c_echo() method
* C-STORE, through the Association.send_c_store() method
* C-FIND, through the Association.send_c_find() method
* C-GET, through the Association.send_c_get() method
* C-MOVE, through the Association.send_c_move() method

Attempting to use a service without an established association will raise a
``RuntimeError`` while attempting to use a service that is not supported by
the association will raise a ``ValueError``.

For more information on using the services available to an association please
read through the :ref:`examples <index_examples>` corresponding to the
service class you're interested in.


Handling Association Requests (SCP)
----------------------------------
