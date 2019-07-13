.. currentmodule:: pynetdicom.AE

Application Entity
------------------
The first step in DICOM networking with *pynetdicom* is the creation of an
:ref:`Application Entity <concepts_ae>` (or AE). A minimal initialisation of
``AE`` requires no arguments.

>>> from pynetdicom import AE
>>> ae = AE()

This will create an AE with an *AE Title* of ``b'PYNETDICOM      '``. The AE
title can set by supplying the ``ae_title`` parameter during initialisation:

>>> from pynetdicom import AE
>>> ae = AE(ae_title=b'MY_AE_TITLE')

Or afterwards with the ``AE.ae_title`` property:

>>> from pynetdicom import AE
>>> ae = AE()
>>> ae.ae_title = b'MY_AE_TITLE'

AE titles must meet the conditions of a DICOM data element with a
`Value Representation <http://dicom.nema.org/medical/dicom/current/output/chtml/part05/sect_6.2.html>`_
of **AE** [1]_:

* Leading and trailing spaces (``0x20``) are non-significant
* Maximum 16 characters (once non-significant characters are removed)
* Valid characters belong to the DICOM `Default Character Repertoire <http://dicom.nema.org/medical/dicom/current/output/chtml/part05/chapter_E.html>`_
  [2]_, which is the basic G0 Set of the ISO646:1990 [5]_ (ASCII) standard
  excluding backslash ('\\ ' ``0x5c``) and all control characters [3]_.
* An AE title made entirely of spaces is not allowed [4]_

AE titles in *pynetdicom* are checked for validity (using
:py:meth:`utils.validate_ae_title() <pynetdicom.utils.validate_ae_title>`)
and then stored as length 16 ``bytes``, with
trailing spaces added as padding if required. This can be important to
remember when dealing with AE titles as the value you set may not be the
value that gets stored.

>>> ae.ae_title = b'MY_AE_TITLE'
>>> ae.ae_title == b'MY_AE_TITLE'
False
>>> ae.ae_title
b'MY_AE_TITLE     '
>>> len(ae.ae_title)
16

When creating SCPs its also possible to give each SCP its own AE title by
specifying the ``ae_title`` keyword argument in
:py:meth:`AE.start_server() <pynetdicom.ae.ApplicationEntity.start_server>`.

.. _ae_create_scu:

Creating an SCU
~~~~~~~~~~~~~~~

Adding requested Presentation Contexts
......................................

If you intend to use your AE as a *Service Class User* then you need to
specify the :ref:`Presentation Contexts <user_presentation>`
that will be *requested* during
Association negotiation. This can be done in two ways:

* You can add requested contexts on a one-by-one basis using the
  :py:meth:`AE.add_requested_context() <pynetdicom.ae.ApplicationEntity.add_requested_context>`
  method.
* You can set all the requested contexts at once using the
  :py:obj:`AE.requested_contexts <pynetdicom.ae.ApplicationEntity.requested_contexts>`
  property. Additional contexts can still be added on a one-by-one basis afterwards.

Adding presentation contexts one-by-one:

>>> from pydicom.uid import UID
>>> from pynetdicom import AE
>>> from pynetdicom.sop_class import CTImageStorage
>>> ae = AE()
>>> ae.add_requested_context('1.2.840.10008.1.1')
>>> ae.add_requested_context(UID('1.2.840.10008.5.1.4.1.1.4'))
>>> ae.add_requested_context(CTImageStorage)

Adding presentation contexts all at once:

>>> from pynetdicom import AE, StoragePresentationContexts
>>> ae = AE()
>>> ae.requested_contexts = StoragePresentationContexts

Here ``StoragePresentationContexts`` is a prebuilt list of presentation
contexts containing (almost) all the Storage Service Class'
`supported SOP Classes <http://dicom.nema.org/medical/dicom/current/output/chtml/part04/sect_B.5.html>`_,
and there's a similar list for
all the supported service classes. Alternatively you can build your own list
of presentation contexts, either through creating new
:py:class:`PresentationContext <pynetdicom.presentation.PresentationContext>`
instances or by using the
:py:meth:`build_context <pynetdicom.presentation.build_context>`
convenience function:

>>> from pynetdicom import AE, build_context
>>> from pynetdicom.sop_class import CTImageStorage
>>> ae = AE()
>>> contexts = [
...     build_context(CTImageStorage),
...     build_context('1.2.840.10008.1.1')
... ]
>>> ae.requested_contexts = contexts

Combining the all-at-once and one-by-one approaches:

>>> from pynetdicom import AE, StoragePresentationContexts
>>> from pynetdicom.sop_class import VerificationSOPClass
>>> ae = AE()
>>> ae.requested_contexts = StoragePresentationContexts
>>> ae.add_requested_context(VerificationSOPClass)

As the association *Requestor* you're limited to a total of 128 requested
presentation contexts, so attempting to add more than 128 contexts will raise
a ``ValueError`` exception.

When you add presentation contexts as shown above, the following transfer
syntaxes are used by default for each context:

+---------------------+------------------------------+
| 1.2.840.10008.1.2   | Implicit VR Little Endian    |
+---------------------+------------------------------+
| 1.2.840.10008.1.2.1 | Explicit VR Little Endian    |
+---------------------+------------------------------+
| 1.2.840.10008.1.2.2 | Explicit VR Big Endian       |
+---------------------+------------------------------+

Specifying your own transfer syntax(es) can be done with the
``transfer_syntax`` parameter as either a single str/UID or a list of str/UIDs:

>>> from pydicom.uid import ImplicitVRLittleEndian, ExplicitVRLittleEndian
>>> from pynetdicom import AE
>>> from pynetdicom.sop_class import CTImageStorage, MRImageStorage
>>> ae = AE()
>>> ae.add_requested_context(CTImageStorage, transfer_syntax='1.2.840.10008.1.2')
>>> ae.add_requested_context(MRImageStorage,
...                          [ImplicitVRLittleEndian, ExplicitVRLittleEndian])

>>> from pydicom.uid import ImplicitVRLittleEndian, ExplicitVRLittleEndian
>>> from pynetdicom import AE, build_context
>>> from pynetdicom.sop_class import CTImageStorage
>>> ae = AE()
>>> context_a = build_context(CTImageStorage, ImplicitVRLittleEndian))
>>> context_b = build_context('1.2.840.10008.1.1',
...                           [ImplicitVRLittleEndian, ExplicitVRBigEndian])
>>> ae.requested_contexts = [context_a, context_b]

The requested presentation contexts can be accessed with the
:py:obj:`AE.requested_contexts <pynetdicom.ae.ApplicationEntity.requested_contexts>`
property and they are returned in the order they were added:

>>> from pynetdicom import AE
>>> from pynetdicom.sop_class import VerificationSOPClass
>>> ae = AE()
>>> len(ae.requested_contexts)
0
>>> ae.add_requested_context(VerificationSOPClass)
>>> len(ae.requested_contexts)
1
>>> print(ae.requested_contexts[0])
Abstract Syntax: Verification SOP Class
Transfer Syntax(es):
    =Implicit VR Little Endian
    =Explicit VR Little Endian
    =Explicit VR Big Endian

Its also possible to have multiple requested presentation contexts for the
same abstract syntax.

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
requested contexts) you can use the ``context`` keyword argument when calling
:py:meth:`AE.associate() <pynetdicom.ae.ApplicationEntity.associate>` (see
the :ref:`Association <association>` page for more information).

Specifying the network port
...........................
In general it shouldn't be necessary to specify the port when acting as an SCU.
By default *pynetdicom* will use the first available port to communicate with a
peer AE. To specify the port number you can use the ``bind_address`` keyword
parameter when requesting an association, which takes a 2-tuple of
(str *host*, int *port*):

>>> from pynetdicom import AE
>>> ae = AE()
>>> ae.add_requested_context('1.2.840.10008.1.1')
>>> assoc = ae.associate('localhost', 11112, bind_address=('', 11113))


Association
...........
For information on how request an association with a peer AE when acting as an
SCU please see the :ref:`Association <association>` page.

.. _ae_create_scp:

Creating an SCP
~~~~~~~~~~~~~~~
Adding supported Presentation Contexts
......................................

If you intend to use your AE as a *Service Class Provider* then you need to
specify the :ref:`Presentation Contexts <user_presentation>`
that will be *supported* during
Association negotiation. This can be done in two ways:

* You can add supported contexts on a one-by-one basis using the
  :py:meth:`AE.add_supported_context() <pynetdicom.ae.ApplicationEntity.add_supported_context>`
  method.
* You can set all the supported contexts at once using the
  :py:obj:`AE.supported_contexts <pynetdicom.ae.ApplicationEntity.supported_contexts>`
  property. Additional contexts can still be added on a one-by-one basis
  afterwards.

Adding presentation contexts one-by-one:

>>> from pydicom.uid import UID
>>> from pynetdicom import AE
>>> from pynetdicom.sop_class import CTImageStorage
>>> ae = AE()
>>> ae.add_supported_context('1.2.840.10008.1.1')
>>> ae.add_supported_context(UID('1.2.840.10008.5.1.4.1.1.4'))
>>> ae.add_supported_context(CTImageStorage)

Adding presentation contexts all at once:

>>> from pynetdicom import AE, StoragePresentationContexts
>>> ae = AE()
>>> ae.supported_contexts = StoragePresentationContexts

Here ``StoragePresentationContexts`` is a prebuilt list of presentation
contexts containing (almost) all the Storage Service Class'
`supported SOP Classes <http://dicom.nema.org/medical/dicom/current/output/chtml/part04/sect_B.5.html>`_,
and there's a similar list for
all the supported service classes. Alternatively you can build your own list
of presentation contexts, either through creating new
:py:class:`PresentationContext <pynetdicom.presentation.PresentationContext>`
instances or by using the
:py:meth:`build_context <pynetdicom.presentation.build_context>`
convenience function:

>>> from pynetdicom import AE, build_context
>>> from pynetdicom.sop_class import CTImageStorage
>>> ae = AE()
>>> contexts = [
...     build_context(CTImageStorage),
...     build_context('1.2.840.10008.1.1')
... ]
>>> ae.supported_contexts = contexts

Combining the all-at-once and one-by-one approaches:

>>> from pynetdicom import AE, StoragePresentationContexts
>>> from pynetdicom.sop_class import VerificationSOPClass
>>> ae = AE()
>>> ae.supported_contexts = StoragePresentationContexts
>>> ae.add_supported_context(VerificationSOPClass)

As the association *Acceptor* you're not limited in the number of presentation
contexts that you can support.

When you add presentation contexts as shown above, the following transfer
syntaxes are used by default for each context:

+---------------------+------------------------------+
| 1.2.840.10008.1.2   | Implicit VR Little Endian    |
+---------------------+------------------------------+
| 1.2.840.10008.1.2.1 | Explicit VR Little Endian    |
+---------------------+------------------------------+
| 1.2.840.10008.1.2.2 | Explicit VR Big Endian       |
+---------------------+------------------------------+

Specifying your own transfer syntax(es) can be done with the
``transfer_syntax`` parameter as either a single str/UID or a list of str/UIDs:

>>> from pydicom.uid import ImplicitVRLittleEndian, ExplicitVRLittleEndian
>>> from pynetdicom import AE
>>> from pynetdicom.sop_class import CTImageStorage, MRImageStorage
>>> ae = AE()
>>> ae.add_supported_context(CTImageStorage, transfer_syntax='1.2.840.10008.1.2')
>>> ae.add_supported_context(MRImageStorage,
...                          [ImplicitVRLittleEndian, ExplicitVRLittleEndian])

>>> from pydicom.uid import ImplicitVRLittleEndian, ExplicitVRLittleEndian
>>> from pynetdicom import AE, build_context
>>> from pynetdicom.sop_class import CTImageStorage
>>> ae = AE()
>>> context_a = build_context(CTImageStorage, ImplicitVRLittleEndian))
>>> context_b = build_context('1.2.840.10008.1.1',
...                           [ImplicitVRLittleEndian, ExplicitVRBigEndian])
>>> ae.supported_contexts = [context_a, context_b]

The supported presentation contexts can be accessed with the
:py:obj:`AE.supported_contexts <pynetdicom.ae.ApplicationEntity.supported_contexts>`
property and they are returned in order of their abstract syntax UID value:

>>> from pynetdicom import AE
>>> from pynetdicom.sop_class import VerificationSOPClass
>>> ae = AE()
>>> len(ae.supported_contexts)
0
>>> ae.add_supported_context(VerificationSOPClass)
>>> len(ae.supported_contexts)
1
>>> print(ae.supported_contexts[0])
Abstract Syntax: Verification SOP Class
Transfer Syntax(es):
    =Implicit VR Little Endian
    =Explicit VR Little Endian
    =Explicit VR Big Endian

For the association *Acceptor* its not possible to have multiple supported
presentation contexts for the same abstract syntax, instead any additional
transfer syntaxes will be combined with the pre-existing context:

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
    =Implicit VR Little Endian
    =Explicit VR Little Endian


All the above examples set the supported presentation contexts on the
Application Entity level, i.e. the same contexts will be used for all
SCPs. To set the supported presentation contexts on a
per-SCP basis (i.e. each SCP can have different
supported contexts) you can use the ``context`` keyword argument when calling
:py:meth:`AE.start_server() <pynetdicom.ae.ApplicationEntity.start_server>` (see
the :ref:`Association <association>` page for more information).


Handling SCP/SCU Role Selection Negotiation
...........................................

Depending on the requirements of the service class, an association *Requestor*
may include
`SCP/SCU Role Selection Negotiation <http://dicom.nema.org/medical/dicom/current/output/chtml/part07/sect_D.3.3.4.html>`_
items in the association request and it's up to the association *Acceptor*
to decide whether or not to accept the proposed roles. This can be done
through the ``scu_role`` and ``scp_role`` parameters, which control whether
or not the association *Acceptor* will accept or reject the proposal:

>>> from pynetdicom import AE
>>> from pynetdicom.sop_class import CTImageStorage
>>> ae = AE()
>>> ae.add_supported_context(CTImageStorage, scu_role=False, scp_role=True)

If either ``scu_role`` or ``scp_role`` is None (the default) then no response
to the role selection will be sent and the default roles assumed. If you wish
to accept a proposed role then set the corresponding parameter to ``True``. In
the above example if the *Requestor* proposes the SCP role then the *Acceptor*
will accept it while rejecting the proposed SCU role (and therefore the
*Acceptor* will be SCU and *Requestor* SCP).

To reiterate, if you wish to respond to the proposed role selection then
**both** ``scu_role`` and ``scp_role`` must be set, and the value you set
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
`User Identity Negotiation <http://dicom.nema.org/medical/dicom/current/output/chtml/part07/sect_D.3.3.7.html>`_
item in the association request with the aim of providing the *Acceptor* a
method of verifying its identity. Possible forms of identity confirmation
methods are:

* Username
* Username and password (sent in the clear)
* Kerberos service ticket
* SAML assertion
* JSON web token

By default all association requests that include user identity negotiation
are accepted (provided there's no other reason to reject) and
no user identity negotiation response is sent even if one is requested.

To handle a user identity negotiation yourself you
should implement and bind a :ref:`handler <user_events>` to the
``evt.EVT_USER_ID`` event. Check the
`documentation <../reference/generated/pynetdicom._handlers.doc_handle_userid.html>`_
to see the requirements for implementations of the ``evt.EVT_USER_ID`` handler.

.. code-block:: python

    from pynetdicom import AE, evt
    from pynetdicom.sop_class import VerificationSOPClass

    def handle_user_id(event):
        """Handle evt.EVT_USER_ID."""
        # Identity verification code is outside the scope of pynetdicom
        is_verified, response = some_user_function()

        return is_verified, response

    handlers = [(evt.EVT_USER_ID, handle_user_id)]

    ae = AE()
    ae.add_supported_context(VerificationSOPClass)
    ae.start_server(('', 11112), evt_handlers=handlers)


Specifying the bind address
...........................
The bind address for the server socket is specified by the ``address``
parameter to ``start_server()`` as (str *host*, int *port*).

>>> from pynetdicom import AE
>>> ae = AE()
>>> ae.add_supported_context('1.2.840.10008.1.1')
>>> ae.start_server(('', 11112))


Association
...........
For information on how to start listening for association requests from peer
AEs and how to handle their service requests see the
:ref:`Association <association>` page.


References
..........

.. [1] DICOM Standard, Part 5
   `Section 6.2 <http://dicom.nema.org/medical/dicom/current/output/html/part05.html#sect_6.2>`_
.. [2] DICOM Standard, Part 5
   `Section 6.1.2.1 <http://dicom.nema.org/medical/dicom/current/output/html/part05.html#sect_6.1.3>`_
.. [3] DICOM Standard, Part 5
   `Section 6.1.3 <http://dicom.nema.org/medical/dicom/current/output/html/part05.html#sect_6.1.3>`_
.. [4] DICOM Standard, Part 8
   `Section 9.3.2 <http://dicom.nema.org/medical/dicom/current/output/html/part08.html#sect_9.3.2>`_
.. [5] `ISO/IEC 646:1991 <https://www.iso.org/standard/4777.html>`_
.. DICOM Standard, Part 8
   `Annex B.1 <http://dicom.nema.org/medical/dicom/current/output/html/part08.html#sect_B.1>`_
.. DICOM Standard, Part 8
   `Annex B.2 <http://dicom.nema.org/medical/dicom/current/output/html/part08.html#sect_B.2>`_
