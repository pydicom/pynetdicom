
.. currentmodule:: pynetdicom.presentation

Introduction
------------

:dcm:`Presentation Contexts <part08/chapter_7.html#sect_7.1.1.13>`
are used in DICOM to fully define the content and the
encoding of a piece of data (typically a DICOM dataset). They consist of three
main parts; a *Context ID*, an *Abstract Syntax* and one or more
*Transfer Syntaxes*.

* The :dcm:`Context ID <part08/sect_9.3.2.2.html>`
  is an odd-integer between 1 and 255 (inclusive) and
  identifies the context. With *pynetdicom* this is not something you usually
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

In *pynetdicom* presentation contexts are represented using the
:class:`PresentationContext` class.

.. code-block:: python

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
takes the abstract syntax and optionally one or more transfer syntaxes and
returns a :class:`PresentationContext` instance:

.. code-block:: python

    >>> from pynetdicom import build_context
    >>> from pynetdicom.sop_class import Verification
    >>> Verification
    '1.2.840.10008.1.1'
    >>> cx = build_context(
    ...     Verification, ['1.2.840.10008.1.2', '1.2.840.10008.1.2.4.50']
    ... )
    ...
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

If no transfer syntaxes are supplied then the default transfer syntaxes will be
used instead.
