.. currentmodule:: pynetdicom.ae

.. _ae_create_scu:

Use as an SCU
-------------

Adding requested Presentation Contexts
......................................

If you intend to use your AE as a *Service Class User* then you need to
specify the :doc:`presentation contexts<presentation_requestor>`
that will be *requested* during association negotiation. This can be done in two ways:

* You can add requested contexts on a one-by-one basis using the
  :meth:`AE.add_requested_context() <ApplicationEntity.add_requested_context>`
  method.
* You can set all the requested contexts at once using the
  :attr:`AE.requested_contexts <ApplicationEntity.requested_contexts>`
  property. Additional contexts can still be added on a one-by-one basis
  afterwards.

Adding presentation contexts one-by-one:

.. doctest::

    >>> from pydicom.uid import UID
    >>> from pynetdicom import AE
    >>> from pynetdicom.sop_class import CTImageStorage
    >>> ae = AE()
    >>> ae.add_requested_context('1.2.840.10008.1.1')
    >>> ae.add_requested_context(UID('1.2.840.10008.5.1.4.1.1.4'))
    >>> ae.add_requested_context(CTImageStorage)

Adding presentation contexts all at once:

.. doctest::

    >>> from pynetdicom import AE, StoragePresentationContexts
    >>> ae = AE()
    >>> ae.requested_contexts = StoragePresentationContexts

Here :attr:`~pynetdicom.presentation.StoragePresentationContexts` is a
prebuilt list of presentation contexts containing 120 of the most commonly used Storage
Service Classes' :dcm:`supported SOP Classes <part04/sect_B.5.html>`,
and there's a :ref:`similar list<api_presentation_prebuilt>` for all
the supported service classes.
Alternatively you can build your own list of presentation contexts, either
through creating new :class:`~pynetdicom.presentation.PresentationContext`
instances or by using the :func:`~pynetdicom.presentation.build_context`
convenience function:

.. doctest::

    >>> from pynetdicom import AE, build_context
    >>> from pynetdicom.sop_class import CTImageStorage
    >>> ae = AE()
    >>> contexts = [
    ...     build_context(CTImageStorage),
    ...     build_context('1.2.840.10008.1.1')
    ... ]
    >>> ae.requested_contexts = contexts

Combining the all-at-once and one-by-one approaches:

.. doctest::

    >>> from pynetdicom import AE, StoragePresentationContexts
    >>> from pynetdicom.sop_class import Verification
    >>> ae = AE()
    >>> ae.requested_contexts = StoragePresentationContexts
    >>> ae.add_requested_context(Verification)

As the association *Requestor* you're limited to a total of 128 requested
presentation contexts, so attempting to add more than 128 contexts will raise
a :class:`ValueError` exception.  :attr:`~pynetdicom.presentation.StoragePresentationContexts` consists of 120 of most commonly used Storage
Service Classes, therefore you are able to add 8 additional presentation contexts without rasing a :class:`ValueError` exception.

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
*transfer_syntax* keyword parameter as either a single str/UID or a list of
str/UIDs:

.. doctest::

    >>> from pydicom.uid import ImplicitVRLittleEndian, ExplicitVRLittleEndian
    >>> from pynetdicom import AE
    >>> from pynetdicom.sop_class import CTImageStorage, MRImageStorage
    >>> ae = AE()
    >>> ae.add_requested_context(CTImageStorage, transfer_syntax='1.2.840.10008.1.2')
    >>> ae.add_requested_context(
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
    >>> ae.requested_contexts = [context_a, context_b]

The requested presentation contexts can be accessed with the
:attr:`AE.requested_contexts<ApplicationEntity.requested_contexts>`
property and are returned in the order they were added.

.. doctest::

    >>> from pynetdicom import AE
    >>> from pynetdicom.sop_class import Verification
    >>> ae = AE()
    >>> len(ae.requested_contexts)
    0
    >>> ae.add_requested_context(Verification)
    >>> len(ae.requested_contexts)
    1
    >>> print(ae.requested_contexts[0])
    Abstract Syntax: Verification SOP Class
    Transfer Syntax(es):
        =Implicit VR Little Endian
        =Explicit VR Little Endian
        =Explicit VR Big Endian

It's also possible to have multiple requested presentation contexts for the
same abstract syntax.

.. doctest::

    >>> from pydicom.uid import ImplicitVRLittleEndian
    >>> from pynetdicom import AE
    >>> from pynetdicom.sop_class import CTImageStorage
    >>> ae = AE()
    >>> ae.add_requested_context(CTImageStorage)
    >>> ae.add_requested_context(CTImageStorage, ImplicitVRLittleEndian)
    >>> len(ae.requested_contexts)
    2
    >>> print(ae.requested_contexts[0])
    Abstract Syntax: CT Image Storage
    Transfer Syntax(es):
        =Implicit VR Little Endian
        =Explicit VR Little Endian
        =Explicit VR Big Endian
    >>> print(ae.requested_contexts[1])
    Abstract Syntax: CT Image Storage
    Transfer Syntax(es):
        =Implicit VR Little Endian

All the above examples set the requested presentation contexts on the
Application Entity level, i.e. the same contexts will be used for all
association requests. To set the requested presentation contexts on a
per-association basis (i.e. each association request can have different
requested contexts) you can use the *contexts* keyword parameter when calling
:meth:`AE.associate()<ApplicationEntity.associate>` (see
the :doc:`Association<association_requesting>` page for more information).

Specifying the network port
...........................
In general it shouldn't be necessary to specify the port when acting as an SCU,
as by default *pynetdicom* will use the first port available. To specify the
port number manually you can use the *bind_address* keyword parameter when
requesting an association, which takes:

* For IPv4 or IPv6 a 2-tuple of (:class:`str` *host*, :class:`int` *port*), with the
  `flowinfo` and `scope_id` defaulting to ``0`` for IPv6, or,
* For IPv6 a 4-tuple of (:class:`str` *host*, :class:`int` *port*, :class:`int`
  flowinfo, :class:`int` scope_id)

.. doctest::

    >>> from pynetdicom import AE
    >>> ae = AE()
    >>> ae.add_requested_context('1.2.840.10008.1.1')
    >>> assoc = ae.associate("127.0.0.1", 11112, bind_address=("127.0.0.1", 11113))  # doctest: +SKIP
    >>> assoc.release()
    >>> assoc = ae.associate("::1", 11112, bind_address=("::1", 11113))  # doctest: +SKIP
    >>> assoc.release()

.. note::

    When using *bind_address* you may sometimes be unable to immediately
    reconnect with the same bound address and port due to an exception about
    the socket or address already being in use. This occurs because
    the `previous TCP connection using the bound socket
    <https://hea-www.harvard.edu/~fine/Tech/addrinuse.html>`_ remains in a
    ``TIME_WAIT`` state which must expire before you are able to re-use the socket.
