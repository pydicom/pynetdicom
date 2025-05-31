
.. _concepts_presentation_contexts:

Presentation Contexts
---------------------
*Presentation Contexts* are used during the negotiation of an association to
provide a method for communicating applications to agree on a set of supported services.
Each presentation context consists of an *Abstract Syntax* and one or more
*Transfer Syntaxes*, along with an ID value.

* The association *requestor* may propose multiple presentation contexts per
  association but is limited to a maximum of 128 proposed contexts.
* Each proposed presentation context contains one Abstract Syntax and one or
  more Transfer Syntaxes.
* The *requestor* may propose multiple contexts with the same Abstract Syntax
* The association *acceptor* may accept or reject each presentation context
  individually, but only one Transfer Syntax may be accepted per presentation
  context.
* The *acceptor* selects a suitable Transfer Syntax for each accepted
  presentation context.

A more detailed guide to presentation contexts and how to use them with
*pynetdicom* is available :doc:`here <presentation_introduction>`.

.. _concepts_abstract_syntax:

Abstract Syntax
~~~~~~~~~~~~~~~
An :dcm:`Abstract Syntax<part08/chapter_B.html>` is a specification of a set of data
elements and their associated semantics. Each abstract syntax is identified by an
*Abstract Syntax Name* in the form of a UID. Abstract syntax names used with DICOM
are usually the officially registered SOP Class UIDs (and the abstract syntax is
therefore the SOP class itself), but the standard also allows the use of private
abstract syntaxes.

While *pynetdicom* can handle association negotiation containing private abstract
syntaxes the implementation of the associated services is up to the end user and should
be specified with the :func:`~pynetdicom.sop_class.register_uid` function.

.. _concepts_transfer_syntax:

Transfer Syntax
~~~~~~~~~~~~~~~
A :dcm:`Transfer Syntax<part08/sect_B.2.html>` defines a set of encoding rules able to
unambiguously represent the data elements defined by one or more abstract syntaxes. In
particular, the negotiation of transfer syntaxes allows communicating AEs to
agree on the encoding techniques they are able to support (i.e. byte ordering,
compression, etc.).

The official DICOM transfer syntaxes are defined in
:dcm:`Part 5<part05.html#chapter_8>` of the DICOM Standard and the Standard also
allows the use of privately defined transfer syntaxes.
