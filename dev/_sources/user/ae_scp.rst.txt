.. currentmodule:: pynetdicom.ae

.. _ae_create_scp:

Use as an SCP
-------------
Adding supported Presentation Contexts
......................................

If you intend to use your AE as a *Service Class Provider* then you need to
specify the :doc:`presentation contexts<presentation_acceptor>`
that will be *supported* during association negotiation. This can be done in two ways:

* You can add supported contexts on a one-by-one basis using the
  :meth:`AE.add_supported_context()<ApplicationEntity.add_supported_context>`
  method.
* You can set all the supported contexts at once using the
  :attr:`AE.supported_contexts<ApplicationEntity.supported_contexts>`
  property. Additional contexts can still be added on a one-by-one basis
  afterwards.

Adding presentation contexts one-by-one:

.. doctest::

    >>> from pydicom.uid import UID
    >>> from pynetdicom import AE
    >>> from pynetdicom.sop_class import CTImageStorage
    >>> ae = AE()
    >>> ae.add_supported_context('1.2.840.10008.1.1')
    >>> ae.add_supported_context(UID('1.2.840.10008.5.1.4.1.1.4'))
    >>> ae.add_supported_context(CTImageStorage)

Adding presentation contexts all at once:

.. doctest::

    >>> from pynetdicom import AE, StoragePresentationContexts
    >>> ae = AE()
    >>> ae.supported_contexts = StoragePresentationContexts

Here :attr:`~pynetdicom.presentation.StoragePresentationContexts` is a prebuilt
:class:`list` of presentation contexts containing 120 of the most commonly used Storage
Service Classes' :dcm:`supported SOP Classes<part04/sect_B.5.html>`,
and there's a :ref:`similar list<api_presentation_prebuilt>` for
all the supported service classes. Alternatively you can build your own list
of presentation contexts, either through creating new
:class:`~pynetdicom.presentation.PresentationContext` instances or by using the
:func:`~pynetdicom.presentation.build_context` convenience function:

.. doctest::

    >>> from pynetdicom import AE, build_context
    >>> from pynetdicom.sop_class import CTImageStorage
    >>> ae = AE()
    >>> contexts = [
    ...     build_context(CTImageStorage),
    ...     build_context('1.2.840.10008.1.1')
    ... ]
    >>> ae.supported_contexts = contexts

Combining the all-at-once and one-by-one approaches:

.. doctest::

    >>> from pynetdicom import AE, AllStoragePresentationContexts
    >>> from pynetdicom.sop_class import Verification
    >>> ae = AE()
    >>> ae.supported_contexts = AllStoragePresentationContexts
    >>> ae.add_supported_context(Verification)

As the association *Acceptor* you're not limited in the number of presentation
contexts that you can support.

When you add presentation contexts as shown above, the following transfer
syntaxes are used by default for each context:

+------------------------+------------------------------------+
| 1.2.840.10008.1.2      | Implicit VR Little Endian          |
+------------------------+------------------------------------+
| 1.2.840.10008.1.2.1    | Explicit VR Little Endian          |
+------------------------+------------------------------------+
| 1.2.840.10008.1.2.1.99 | Deflated Explicit VR Little Endian |
+------------------------+------------------------------------+
| 1.2.840.10008.1.2.2    | Explicit VR Big Endian             |
+------------------------+------------------------------------+

Specifying your own transfer syntax(es) can be done with the
*transfer_syntax* keyword parameter as either a single str/UID or a
list of str/UIDs:

.. doctest::

    >>> from pydicom.uid import ImplicitVRLittleEndian, ExplicitVRLittleEndian
    >>> from pynetdicom import AE
    >>> from pynetdicom.sop_class import CTImageStorage, MRImageStorage
    >>> ae = AE()
    >>> ae.add_supported_context(CTImageStorage, transfer_syntax='1.2.840.10008.1.2')
    >>> ae.add_supported_context(
    ...     MRImageStorage, [ImplicitVRLittleEndian, ExplicitVRLittleEndian]
    ... )

.. doctest::

    >>> from pydicom.uid import ImplicitVRLittleEndian, ExplicitVRBigEndian
    >>> from pynetdicom import AE, build_context
    >>> from pynetdicom.sop_class import CTImageStorage
    >>> ae = AE()
    >>> context_a = build_context(CTImageStorage, ImplicitVRLittleEndian)
    >>> context_b = build_context(
    ...     '1.2.840.10008.1.1', [ImplicitVRLittleEndian, ExplicitVRBigEndian]
    ... )
    >>> ae.supported_contexts = [context_a, context_b]

The supported presentation contexts can be accessed with the
:attr:`AE.supported_contexts<ApplicationEntity.supported_contexts>`
property and are returned in order of their abstract syntax UID value:

.. doctest::

    >>> from pynetdicom import AE
    >>> from pynetdicom.sop_class import Verification
    >>> ae = AE()
    >>> len(ae.supported_contexts)
    0
    >>> ae.add_supported_context(Verification)
    >>> len(ae.supported_contexts)
    1
    >>> print(ae.supported_contexts[0])
    Abstract Syntax: Verification SOP Class
    Transfer Syntax(es):
        =Implicit VR Little Endian
        =Explicit VR Little Endian
        =Explicit VR Big Endian

For the association *Acceptor* it's not possible to have multiple supported
presentation contexts for the same abstract syntax, instead any additional
transfer syntaxes will be combined with the pre-existing context:

.. doctest::

    >>> from pydicom.uid import ImplicitVRLittleEndian, ExplicitVRLittleEndian
    >>> from pynetdicom import AE
    >>> from pynetdicom.sop_class import CTImageStorage
    >>> ae = AE()
    >>> ae.add_supported_context(CTImageStorage, ExplicitVRLittleEndian)
    >>> ae.add_supported_context(CTImageStorage, ImplicitVRLittleEndian)
    >>> len(ae.supported_contexts)
    1
    >>> print(ae.supported_contexts[0])
    Abstract Syntax: CT Image Storage
    Transfer Syntax(es):
        =Explicit VR Little Endian
        =Implicit VR Little Endian

All the above examples set the supported presentation contexts on the
Application Entity level, i.e. the same contexts will be used for all
SCPs. To set the supported presentation contexts on a
per-SCP basis (i.e. each SCP can have different
supported contexts) you can use the *contexts* keyword parameter when calling
:meth:`AE.start_server()<ApplicationEntity.start_server>` (see
the :doc:`Association<association_accepting>` page for more information).


.. _user_ae_role_negotiation:

Handling SCP/SCU Role Selection Negotiation
...........................................

Depending on the requirements of the service class, an association *Requestor*
may include
:dcm:`SCP/SCU Role Selection Negotiation <part07/sect_D.3.3.4.html>`
items in the association request and it's up to the association *Acceptor*
to decide whether or not to accept the proposed roles. This can be done
through the *scu_role* and *scp_role* keyword parameters, which control whether
or not the association *Acceptor* will accept or reject the proposal:

.. doctest::

    >>> from pynetdicom import AE
    >>> from pynetdicom.sop_class import CTImageStorage
    >>> ae = AE()
    >>> ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)

If either *scu_role* or *scp_role* is ``None`` (the default) then no response
to the role selection will be sent and the default roles assumed. If you wish
to accept a proposed role then set the corresponding parameter to ``True``. In
the above example if the *Requestor* proposes the SCP role then the *Acceptor*
will accept it while rejecting the proposed SCU role (and therefore the
*Acceptor* will be SCU and *Requestor* SCP).

To reiterate, if you wish to respond to the proposed role selection then
**both** *scu_role* and *scp_role* must be set, and the value you set
indicates whether or not to accept or reject the proposal.

There are :ref:`four possible outcomes <role_selection_negotiation>`
for the role selection negotiation, depending
on what was proposed and what was accepted:

* The proposed roles aren't acceptable and the context is rejected
* The *Acceptor* acts as the SCP and the *Requestor* the SCU (default)
* The *Acceptor* acts as the SCU and the *Requestor* the SCP
* Both *Acceptor* and *Requestor* act as SCU and SCP

Handling User Identity Negotiation
..................................

An association *Requestor* may include a
:dcm:`User Identity Negotiation <part07/sect_D.3.3.7.html>`
item in the association request with the aim of providing the *Acceptor* a
method of verifying its identity. Possible forms of identity confirmation
methods are:

* Username
* Username and password (sent in the clear)
* Kerberos service ticket
* SAML assertion
* JSON web token

By default, all association requests that include user identity negotiation
are accepted (provided there's no other reason to reject) and
no user identity negotiation response is sent even if one is requested.

To handle a user identity negotiation yourself you
should implement and bind a :ref:`handler <user_events>` to the
``evt.EVT_USER_ID`` event. Check the
`documentation <../reference/generated/pynetdicom._handlers.doc_handle_userid.html>`_
to see the requirements for implementations of the ``evt.EVT_USER_ID`` handler.

.. code-block:: python

    from pynetdicom import AE, evt
    from pynetdicom.sop_class import Verification

    from my_code import some_user_function

    def handle_user_id(event):
        """Handle evt.EVT_USER_ID."""
        # Identity verification code is outside the scope of pynetdicom
        is_verified, response = some_user_function(event)

        return is_verified, response

    handlers = [(evt.EVT_USER_ID, handle_user_id)]

    ae = AE()
    ae.add_supported_context(Verification)
    ae.start_server(("127.0.0.1", 11112), evt_handlers=handlers)


Specifying the bind address
...........................
The bind address for the server socket is specified by the *address*
parameter to :meth:`~pynetdicom.ae.ApplicationEntity.start_server` as:

* For IPv4 or IPv6 a 2-tuple of (:class:`str` *host*, :class:`int` *port*), with the
  `flowinfo` and `scope_id` defaulting to ``0`` for IPv6, or,
* For IPv6 a 4-tuple of (:class:`str` *host*, :class:`int` *port*, :class:`int`
  flowinfo, :class:`int` scope_id)

.. code-block:: python

    >>> from pynetdicom import AE
    >>> ae = AE()
    >>> ae.add_supported_context('1.2.840.10008.1.1')
    >>> server = ae.start_server(("127.0.0.1", 11112), block=False)
    >>> server.shutdown()
    >>> server = ae.start_server(("::1", 11112), block=False)
    >>> server.shutdown()
