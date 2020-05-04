.. _user_presentation:

Presentation Contexts
---------------------

.. currentmodule:: pynetdicom.presentation

Introduction
............

:dcm:`Presentation Contexts <part08/chapter_7.html#sect_7.1.1.13>`
are used in DICOM to fully define the content and the
encoding of a piece of data (typically a DICOM dataset). They consist of three
main parts; a *Context ID*, an *Abstract Syntax* and one or more
*Transfer Syntaxes*.

* The :dcm:`Context ID <part08/sect_9.3.2.2.html>`
  is an odd-integer between 1 and 255 (inclusive) and
  identifies the context. With *pynetdicom* this is not something you typically
  have to worry about.
* The :dcm:`Abstract Syntax <part08/chapter_B.html>`
  defines what the data represents, usually identified by
  a DICOM *SOP Class UID* (however private abstract syntaxes are also allowed)
  such as:

  - ``1.2.840.10008.1.1`` - *Verification SOP Class*
  - ``1.2.840.10008.5.1.4.1.1`` - *CT Image Storage*
* The :dcm:`Transfer Syntax <part05/chapter_10.html>`
  defines how the data is encoded, usually identified by
  a DICOM *Transfer Syntax UID* (however private transfer syntaxes are also
  allowed) such as:

  - ``1.2.840.10008.1.2`` - *Implicit VR Little Endian*
  - ``1.2.840.10008.1.2.4.50`` - *JPEG Baseline*


Representation in pynetdicom
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In *pynetdicom* presentation contexts are represented using the
:class:`presentation.PresentationContext<PresentationContext>` class.

.. doctest::

    >>> from pynetdicom.presentation import PresentationContext
    >>> cx = PresentationContext()
    >>> cx.context_id = 1
    >>> cx.abstract_syntax = '1.2.840.10008.1.1'
    >>> cx.transfer_syntax = ['1.2.840.10008.1.2', '1.2.840.10008.1.2.4.50']
    >>> print(cx)
    ID: 1
    Abstract Syntax: Verification SOP Class
    Transfer Syntax(es):
        =Implicit VR Little Endian
        =JPEG Baseline (Process 1)

However it's easier to use the :func:`build_context` convenience function which
returns a :class:`PresentationContext` instance:

.. doctest::

    >>> from pynetdicom import build_context
    >>> cx = build_context(
    ...     '1.2.840.10008.1.1', ['1.2.840.10008.1.2', '1.2.840.10008.1.2.4.50']
    ... )
    >>> print(cx)
    Abstract Syntax: Verification SOP Class
    Transfer Syntax(es):
        =Implicit VR Little Endian
        =JPEG Baseline (Process 1)
    >>> print(build_context('1.2.840.10008.1.1'))  # Default transfer syntaxes
    Abstract Syntax: Verification SOP Class
    Transfer Syntax(es):
        =Implicit VR Little Endian
        =Explicit VR Little Endian
        =Explicit VR Big Endian


Presentation Contexts and the Association Requestor
...................................................

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
      from pynetdicom.sop_class import VerificationSOPClass

      ae = AE()
      ae.requested_contexts = [build_context(VerificationSOPClass)]
      assoc = ae.associate('127.0.0.1', 11112)

2. Using the
   :meth:`AE.add_requested_context()
   <pynetdicom.ae.ApplicationEntity.add_requested_context>`
   method to add a new :class:`PresentationContext` to the
   :attr:`AE.requested_contexts
   <pynetdicom.ae.ApplicationEntity.requested_contexts>` attribute.

   .. code-block:: python

      from pynetdicom import AE
      from pynetdicom.sop_class import VerificationSOPClass

      ae = AE()
      ae.add_requested_context(VerificationSOPClass)
      assoc = ae.associate('127.0.0.1', 11112)

3. Supplying a list of :class:`PresentationContext` items to
   :meth:`AE.associate()<pynetdicom.ae.ApplicationEntity.associate>`
   via the *contexts* keyword parameter.

   .. code-block:: python

      from pynetdicom import AE, build_context
      from pynetdicom.sop_class import VerificationSOPClass

      ae = AE()
      requested = [build_context(VerificationSOPClass)]
      assoc = ae.associate('127.0.0.1', 11112, contexts=requested)


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

.. doctest::

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


Presentation Contexts and the Association Acceptor
..................................................

When acting as the association *acceptor* (usually the SCP), you should define
which presentation contexts will be supported. Unlike the *requestor* you can
define an unlimited number of supported presentation contexts.

In *pynetdicom* this is accomplished through one of the following methods:

1. Setting the :attr:`AE.supported_contexts
   <pynetdicom.ae.ApplicationEntity.supported_contexts>`
   attribute directly using a list of :class:`PresentationContext` items.

   .. code-block:: python

        from pynetdicom import AE, build_context
        from pynetdicom.sop_class import VerificationSOPClass

        ae = AE()
        ae.supported_contexts = [build_context(VerificationSOPClass)]
        ae.start_server(('', 11112))


2. Using the
   :meth:`AE.add_supported_context()
   <pynetdicom.ae.ApplicationEntity.add_supported_context>`
   method to add a new :class:`PresentationContext` to the
   :attr:`AE.supported_contexts
   <pynetdicom.ae.ApplicationEntity.supported_contexts>` attribute.

   .. code-block:: python

        from pynetdicom import AE
        from pynetdicom.sop_class import VerificationSOPClass

        ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.start_server(('', 11112))

3. Supplying a list of :class:`PresentationContext` items to
   :meth:`AE.start_server()<pynetdicom.ae.ApplicationEntity.start_server>`
   via the `contexts` keyword parameter

   .. code-block:: python

       from pynetdicom import AE, build_context
       from pynetdicom.sop_class import VerificationSOPClass

       ae = AE()
       supported = [build_context(VerificationSOPClass)]
       ae.start_server(('', 11112), contexts=supported)


The abstract syntaxes you support should correspond to the service classes that
are being offered. For example, if you offer the
:dcm:`Storage Service<part04/chapter_B.html>` then you should
support one or more of the Storage Service's :dcm:`corresponding SOP Classes
<part04/sect_B.5.html>`.

The transfer syntaxes for each abstract syntax should match the data encoding
you support.

.. note::
   In general, *pynetdicom* is able to support any transfer syntax when
   acting as an SCP.


Presentation Context Negotiation
................................

Consider an *acceptor* that supports the following abstract syntax/transfer
syntaxes:

* Verification SOP Class

  * Implicit VR Little Endian
  * Explicit VR Little Endian
* CT Image Storage

  * Implicit VR Little Endian

* MR Image Storage

  * JPEG Baseline

And a *requestor* that proposes the following presentation contexts:

* Context 1: Verification SOP Class

  * Implicit VR Little Endian
  * Explicit VR Little Endian
  * Explicit VR Big Endian
  * JPEG Baseline
* Context 3:  CT Image Storage

  * Implicit VR Little Endian
  * Explicit VR Little Endian
  * Explicit VR Big Endian
* Context 5: MR Image Storage

  * Implicit VR Little Endian
  * Explicit VR Little Endian
* Context 7: CR Image Storage

  * Implicit VR Little Endian
  * Explicit VR Little Endian

Then the outcome of the presentation context negotiation will be:

* Context 1: Accepted (with the *acceptor* choosing either *Implicit* or
  *Explicit VR Little Endian* to use as the transfer syntax)
* Context 3: Accepted with *Implicit VR Little Endian* transfer syntax
* Context 5: Rejected (transfer syntax not supported) because the *acceptor*
  and *requestor* have no matching transfer syntax for the context.
* Context 7: Rejected (abstract syntax not supported) because the *acceptor*
  doesn't support the *CR Image Storage* abstract syntax.

Contexts 1 and 3 have been accepted and can be used for sending data while
5 and 7 have been rejected and are not available.


Implementation Note
~~~~~~~~~~~~~~~~~~~

When acting as an *acceptor*, *pynetdicom* will choose the first matching
transfer syntax in :attr:`PresentationContext.transfer_syntax`.  For example, if
the *requestor* proposes the following:

  ::

    Abstract Syntax: Verification SOP Class
    Transfer Syntax(es):
        =Implicit VR Little Endian
        =Explicit VR Little Endian
        =Explicit VR Big Endian

While the *acceptor* supports:

  ::

    Abstract Syntax: Verification SOP Class
    Transfer Syntax(es):
        =Explicit VR Little Endian
        =Implicit VR Little Endian
        =Explicit VR Big Endian

Then the accepted transfer syntax will be *Explicit VR Little Endian*.

.. _user_presentation_role:

SCP/SCU Role Selection
......................

The final wrinkle in presentation context negotiation is :dcm:`SCP/SCU Role
Selection <part07/sect_D.3.3.4.html>`,
which allows an association *requestor* to propose its role (SCU, SCP, or
SCU and SCP) for each proposed abstract syntax. Role selection is used for
services such as the Query/Retrieve Service's C-GET requests, where the
association *acceptor* sends data back to the *requestor*.

To propose SCP/SCU Role Selection as a *requestor* you should include
:class:`SCP_SCU_RoleSelectionNegotiation
<pynetdicom.pdu_primitives.SCP_SCU_RoleSelectionNegotiation>`
items in the extended negotiation, either by creating them from scratch or
using the :func:`build_role` convenience function:

.. code-block:: python

    from pynetdicom import AE, build_role
    from pynetdicom.pdu_primitives import SCP_SCU_RoleSelectionNegotiation
    from pynetdicom.sop_class import CTImageStorage, MRImageStorage

    ae = AE()
    ae.add_requested_context(CTImageStorage)
    ae.add_requested_context(MRImageStorage)

    role_a = SCP_SCU_RoleSelectionNegotiation()
    role_a.sop_class_uid = CTImageStorage
    role_a.scu_role = True
    role_a.scp_role = True

    role_b = build_role(MRImageStorage, scp_role=True)

    assoc = ae.associate('127.0.0.1', 11112, ext_neg=[role_a, role_b])

When acting as the *requestor* you can set **either or both** of *scu_role* and
*scp_role*, with the non-specified role assumed to be ``False``.

To support SCP/SCU Role Selection as an *acceptor* you can use the *scu_role*
and *scp_role* keyword parameters in :meth:`AE.add_supported_context()
<pynetdicom.ae.ApplicationEntity.add_supported_context>`:

.. code-block:: python

    from pynetdicom import AE
    from pynetdicom.pdu_primitives import SCP_SCU_RoleSelectionNegotiation
    from pynetdicom.sop_class import CTImageStorage

    ae = AE()
    ae.add_supported_context(CTImageStorage, scu_role=True, scp_role=False)
    ae.start_server(('', 11112))

When acting as the *acceptor* **both** *scu_role* and *scp_role* must be
specified. A value of ``True`` indicates that the *acceptor* will accept the
proposed role. *pynetdicom* uses the following table to decide the outcome
of role selection negotiation:

.. _role_selection_negotiation:

+---------------------+---------------------+--------------------------+----------+
| *Requestor*         | *Acceptor*          | Outcome                  | Notes    |
+----------+----------+----------+----------+-------------+------------+          |
| scu_role | scp_role | scu_role | scp_role | *Requestor* | *Acceptor* |          |
+==========+==========+==========+==========+=============+============+==========+
| N/A      | N/A      | N/A      | N/A      | SCU         | SCP        | Default  |
+----------+----------+----------+----------+-------------+------------+----------+
| True     | True     | False    | False    | N/A         | N/A        | Rejected |
|          |          |          +----------+-------------+------------+----------+
|          |          |          | True     | SCP         | SCU        |          |
|          |          +----------+----------+-------------+------------+----------+
|          |          | True     | False    | SCU         | SCP        | Default  |
|          |          |          +----------+-------------+------------+----------+
|          |          |          | True     | SCU/SCP     | SCU/SCP    |          |
+----------+----------+----------+----------+-------------+------------+----------+
| True     | False    | False    | False    | N/A         | N/A        | Rejected |
|          |          +----------+          +-------------+------------+----------+
|          |          | True     |          | SCU         | SCP        | Default  |
+----------+----------+----------+----------+-------------+------------+----------+
| False    | True     | False    | False    | N/A         | N/A        | Rejected |
|          |          |          +----------+-------------+------------+----------+
|          |          |          | True     | SCP         | SCU        |          |
+----------+----------+----------+----------+-------------+------------+----------+
| False    | False    | False    | False    | N/A         | N/A        | Rejected |
+----------+----------+----------+----------+-------------+------------+----------+

As can be seen there are four possible outcomes:

* *Requestor* is SCU, *acceptor* is SCP (default roles)
* *Requestor* is SCP, *acceptor* is SCU
* *Requestor* and *acceptor* are both SCU/SCP
* *Requestor* and *acceptor* are neither (context rejected)

.. warning::
   Role selection negotiation is not very well defined by the DICOM Standard,
   so different implementations may not give the same outcomes.
