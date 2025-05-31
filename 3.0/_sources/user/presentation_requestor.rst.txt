
.. currentmodule:: pynetdicom.presentation

Contexts and the Association Requestor
--------------------------------------

When acting as the association *requestor* (usually the SCU), you must propose
presentation contexts to be negotiated by the
association process. There are a couple of simple rules for these:

* There must be at least 1 and up to 128 proposed presentation contexts.
* You can use the same abstract syntax in more than one presentation context.
* Each presentation context must have at least one transfer syntax.

In *pynetdicom* this is accomplished through one of the following methods:

1. Setting the :attr:`AE.requested_contexts
   <pynetdicom.ae.ApplicationEntity.requested_contexts>`
   attribute directly using a list of :class:`PresentationContext` items.

   .. code-block:: python

      from pynetdicom import AE, build_context
      from pynetdicom.sop_class import Verification

      ae = AE()
      ae.requested_contexts = [build_context(Verification)]
      assoc = ae.associate("127.0.0.1", 11112)

2. Using the
   :meth:`AE.add_requested_context()
   <pynetdicom.ae.ApplicationEntity.add_requested_context>`
   method to add a new :class:`PresentationContext` to the
   :attr:`AE.requested_contexts
   <pynetdicom.ae.ApplicationEntity.requested_contexts>` attribute.

   .. code-block:: python

      from pynetdicom import AE
      from pynetdicom.sop_class import Verification

      ae = AE()
      ae.add_requested_context(Verification)
      assoc = ae.associate("127.0.0.1", 11112)

3. Supplying a list of :class:`PresentationContext` items to
   :meth:`AE.associate()<pynetdicom.ae.ApplicationEntity.associate>`
   via the *contexts* keyword parameter.

   .. code-block:: python

      from pynetdicom import AE, build_context
      from pynetdicom.sop_class import Verification

      ae = AE()
      requested = [build_context(Verification)]
      assoc = ae.associate("127.0.0.1", 11112, contexts=requested)


The abstract syntaxes you propose should match the SOP Class or Meta SOP Class
that corresponds to the service you wish to use. For example, if
you're intending to use the storage service then you'd propose one or more
abstract syntaxes from the :dcm:`corresponding SOP Class UIDs
<part04/sect_B.5.html>`.

The transfer syntaxes you propose for each abstract syntax should match the
transfer syntax of the data you wish to send. For example, if you have
a *CT Image Storage* dataset with a (0002,0010) *Transfer Syntax UID* value of
1.2.840.10008.1.2.4.50 (*JPEG Baseline*) then you won't be able to send it
unless you propose (and get accepted) a presentation context with a matching
transfer syntax.

.. note::
   Uncompressed and deflated transfer syntaxes are the exception to this rule
   as *pydicom* is able to freely convert between these (provided the
   endianness remains the same).

If you have data encoded in a variety of transfer syntaxes then you can propose
multiple presentation contexts with the same abstract syntax but different
transfer syntaxes:

.. code-block:: python

    >>> from pydicom.uid import ImplicitVRLittleEndian, JPEGBaseline
    >>> from pynetdicom import AE
    >>> from pynetdicom.sop_class import CTImageStorage
    >>> ae = AE()
    >>> ae.add_requested_context(CTImageStorage, ImplicitVRLittleEndian)
    >>> ae.add_requested_context(CTImageStorage, JPEGBaseline)
    >>> for cx in ae.requested_contexts:
    ...     print(cx)
    ...
    Abstract Syntax: CT Image Storage
    Transfer Syntax(es):
        =Implicit VR Little Endian
    Abstract Syntax: CT Image Storage
    Transfer Syntax(es):
        =JPEG Baseline (Process 1)

Provided both contexts get accepted then it becomes possible to transfer CT
Image datasets encoded in *JPEG Baseline* and/or *Implicit VR Little Endian*.
Alternatively it may be necessary to
:meth:`~pydicom.dataset.Dataset.decompress` datasets prior to sending (as
*Implicit VR Little Endian* should always be accepted).
