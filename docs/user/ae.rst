.. currentmodule:: pynetdicom3.AE

Application Entity
------------------
The first step in DICOM networking with pynetdicom is the creation of an
:ref:`Application Entity <concepts_ae>` (or AE). A minimal initialisation of ``AE`` requires no
arguments.

>>> from pynetdicom3 import AE
>>> ae = AE()

This will create an AE with an *AE Title* of ``b'PYNETDICOM      '``. The AE
title can set by supplying the ``ae_title`` parameter during initialisation:

>>> from pynetdicom3 import AE
>>> ae = AE(ae_title=b'MY_AE_TITLE')

Or afterwards with the ``AE.ae_title`` property:

>>> from pynetdicom3 import AE
>>> ae = AE()
>>> ae.ae_title = b'MY_AE_TITLE'

AE titles must meet the conditions of a DICOM data element with a
`Value Representation <http://dicom.nema.org/medical/dicom/current/output/chtml/part05/sect_6.2.html>`_
of **AE** [1]_:

* Leading and trailing spaces (``0x20``) are non-significant
* Maximum 16 characters (once non-significant characters are removed)
* Valid characters belong to the DICOM `Default Character Repertoire <http://dicom.nema.org/medical/dicom/current/output/chtml/part05/chapter_E.html>`_
  [2]_, which is the basic G0 Set of the ISO646:1990 [5]_ standard excluding
  backslash ('\\ ' ``0x5c``) and all control characters [3]_.

There's also an extra restriction on Application Entity AE titles:

* An AE title made entirely of spaces is not allowed [4]_

AE titles in *pynetdicom* are checked for validity (using
``utils.validate_ae_title``) and then stored as length 16 ``bytes``, with
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


Creating an SCU
~~~~~~~~~~~~~~~

Setting the requested Presentation Contexts
...........................................

If you intend to use your AE as a *Service Class User* then you need to
specify the :ref:`Presentation Contexts <concepts_presentation_contexts>`
that will be *requested* during
Association negotiation. This can be done in two ways:

* You can add requested contexts on a one-by-one basis using the
  :py:meth:`AE.add_requested_context() <pynetdicom3.ae.ApplicationEntity.add_requested_context>`
  method.
* You can set all the requested contexts at once using the
  :py:obj:`AE.requested_contexts <pynetdicom3.ae.ApplicationEntity.requested_contexts>` property. Additional contexts can still
  be added on a one-by-one basis afterwards.

Adding presentation contexts one-by-one:

>>> from pynetdicom3 import AE
>>> from pynetdicom3.sop_class import CTImageStorage
>>> ae = AE()
>>> ae.add_requested_context('1.2.840.10008.1.1')
>>> ae.add_requested_context(UID('1.2.840.10008.5.1.4.1.1.4'))
>>> ae.add_requested_context(CTImageStorage)

Adding presentation contexts all at once:

>>> from pynetdicom3 import AE, StoragePresentationContexts
>>> ae = AE()
>>> ae.requested_contexts = StoragePresentationContexts

Here ``StoragePresentationContexts`` is a prebuilt list of (almost) all the
Storage Service Class' supported SOP Classes, and there's a similar list for
all the supported service classes. Alternatively you can build your own list
of presentation contexts:

>>> from pynetdicom3 import AE, build_context
>>> from pynetdicom3.sop_class import CTImageStorage
>>> ae = AE()
>>> contexts = [
...     build_context(CTImageStorage),
...     build_context('1.2.840.10008.1.1')
... ]
>>> ae.requested_contexts = contexts

Combining the all-at-once and one-by-one approaches:

>>> from pynetdicom3 import AE, StoragePresentationContexts
>>> from pynetdicom3.sop_class import VerificationSOPClass
>>> ae = AE()
>>> ae.requested_contexts = StoragePresentationContexts
>>> ae.add_requested_context(VerificationSOPClass)

As the association requestor you're limited to a total of 128 requested
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
>>> from pynetdicom3 import AE
>>> from pynetdicom3.sop_class import CTImageStorage, MRImageStorage
>>> ae = AE()
>>> ae.add_requested_context(CTImageStorage, transfer_syntax='1.2.840.10008.1.2')
>>> ae.add_requested_context(MRImageStorage,
...                          [ImplicitVRLittleEndian, ExplicitVRLittleEndian])

>>> from pydicom.uid import ImplicitVRLittleEndian, ExplicitVRLittleEndian
>>> from pynetdicom3 import AE, build_context
>>> from pynetdicom3.sop_class import CTImageStorage
>>> ae = AE()
>>> context_a = build_context(CTImageStorage, ImplicitVRLittleEndian))
>>> context_b = build_context('1.2.840.10008.1.1',
...                           [ImplicitVRLittleEndian, ExplicitVRBigEndian])
>>> ae.requested_contexts = [context_a, context_b]

The requested presentation contexts can be accessed with the
:py:obj:`AE.requested_contexts <pynetdicom3.ae.ApplicationEntity.requested_contexts>` property:

>>> from pynetdicom3 import AE
>>> from pynetdicom3.sop_class import VerificationSOPClass
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
>>> from pynetdicom3 import AE
>>> from pynetdicom3.sop_class import CTImageStorage
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
requested contexts) you can use the ``context`` parameter when calling
:py:meth:`AE.associate() <pynetdicom3.ae.ApplicationEntity.associate>`.

FIXME For more information see the Association.

Specifying the network port
...........................
By default an SCU will use the first available port to communicate with a peer
AE. To specify the port number you can use the ``port`` parameter when
initialising the AE:

>>> from pynetdicom3 import AE
>>> ae = AE(port=11112)

Or you can set it afterwards:

>>> from pynetdicom3 import AE
>>> ae = AE()
>>> ae.port = 11112

Setting the value to ``0`` will revert the port to the first available.


Creating an SCP
~~~~~~~~~~~~~~~
Setting the requested Presentation Contexts
...........................................

If you intend to use your AE as a *Service Class Provider* then you need to
specify the :ref:`Presentation Contexts <concepts_presentation_contexts>`
that will be *supported* during
Association negotiation. This can be done in two ways:

* You can add supported contexts on a one-by-one basis using the
  :py:meth:`AE.add_supported_context() <pynetdicom3.ae.ApplicationEntity.add_supported_context>`
  method.
* You can set all the supported contexts at once using the
  :py:obj:`AE.supported_contexts <pynetdicom3.ae.ApplicationEntity.supported_contexts>`
  property. Additional contexts can still be added on a one-by-one basis
  afterwards.

Adding presentation contexts one-by-one:

>>> from pynetdicom3 import AE
>>> from pynetdicom3.sop_class import CTImageStorage
>>> ae = AE()
>>> ae.add_supported_context('1.2.840.10008.1.1')
>>> ae.add_supported_context(UID('1.2.840.10008.5.1.4.1.1.4'))
>>> ae.add_supported_context(CTImageStorage)

Adding presentation contexts all at once:

>>> from pynetdicom3 import AE, StoragePresentationContexts
>>> ae = AE()
>>> ae.supported_contexts = StoragePresentationContexts

Here ``StoragePresentationContexts`` is a prebuilt list of (almost) all the
Storage Service Class' supported SOP Classes, and there's a similar list for
all the supported service classes. Alternatively you can build your own list
of presentation contexts:

>>> from pynetdicom3 import AE, build_context
>>> from pynetdicom3.sop_class import CTImageStorage
>>> ae = AE()
>>> contexts = [
...     build_context(CTImageStorage),
...     build_context('1.2.840.10008.1.1')
... ]
>>> ae.supported_contexts = contexts

Combining the all-at-once and one-by-one approaches:

>>> from pynetdicom3 import AE, StoragePresentationContexts
>>> from pynetdicom3.sop_class import VerificationSOPClass
>>> ae = AE()
>>> ae.supported_contexts = StoragePresentationContexts
>>> ae.add_supported_context(VerificationSOPClass)

As the association acceptor you're not limited in the number of supported
presentation contexts.

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
>>> from pynetdicom3 import AE
>>> from pynetdicom3.sop_class import CTImageStorage, MRImageStorage
>>> ae = AE()
>>> ae.add_supported_context(CTImageStorage, transfer_syntax='1.2.840.10008.1.2')
>>> ae.add_supported_context(MRImageStorage,
...                          [ImplicitVRLittleEndian, ExplicitVRLittleEndian])

>>> from pydicom.uid import ImplicitVRLittleEndian, ExplicitVRLittleEndian
>>> from pynetdicom3 import AE, build_context
>>> from pynetdicom3.sop_class import CTImageStorage
>>> ae = AE()
>>> context_a = build_context(CTImageStorage, ImplicitVRLittleEndian))
>>> context_b = build_context('1.2.840.10008.1.1',
...                           [ImplicitVRLittleEndian, ExplicitVRBigEndian])
>>> ae.supported_contexts = [context_a, context_b]

The supported presentation contexts can be accessed with the
:py:obj:`AE.supported_contexts <pynetdicom3.ae.ApplicationEntity.supported_contexts>`
property:

>>> from pynetdicom3 import AE
>>> from pynetdicom3.sop_class import VerificationSOPClass
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

For the association acceptor its not possible to have multiple supported
presentation contexts for the same abstract syntax, instead any additional
transfer syntaxes will be combined with the pre-existing context:

>>> from pydicom.uid import ImplicitVRLittleEndian, ExplicitVRLittleEndian
>>> from pynetdicom3 import AE
>>> from pynetdicom3.sop_class import CTImageStorage
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


Specifying the network port
...........................
By default an SCP will use the first available port to listen on for
association requests, which is generally a bad idea as it makes it difficult
for SCU to know what port to communicate with. To specify the port number
you can use the ``port`` parameter when initialising the AE:

>>> from pynetdicom3 import AE
>>> ae = AE(port=11112)

Or you can set it afterwards:

>>> from pynetdicom3 import AE
>>> ae = AE()
>>> ae.port = 11112


Association
-----------
Now that you have an AE, its time to :ref:`associate <association>` it with
another AE.


References
----------

.. [1] DICOM Standard, Part 5
   `Section 6.2 <http://dicom.nema.org/medical/dicom/current/output/html/part05.html#sect_6.2>`_
.. [2] DICOM Standard, Part 5
   `Section 6.1.2.1 <http://dicom.nema.org/medical/dicom/current/output/html/part05.html#sect_6.1.3>`_
.. [3] DICOM Standard, Part 5
   `Section 6.1.3 <http://dicom.nema.org/medical/dicom/current/output/html/part05.html#sect_6.1.3>`_
.. [4] DICOM Standard, Part 8
   `Section 9.3.2 <http://dicom.nema.org/medical/dicom/current/output/html/part08.html#sect_9.3.2>`_
.. [5] `ISO/IEC 646:1991 <https://www.iso.org/standard/4777.html>`_
.. [6] DICOM Standard, Part 8
   `Annex B.1 <http://dicom.nema.org/medical/dicom/current/output/html/part08.html#sect_B.1>`_
.. [7] DICOM Standard, Part 8
   `Annex B.2 <http://dicom.nema.org/medical/dicom/current/output/html/part08.html#sect_B.2>`_
