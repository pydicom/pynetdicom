
.. currentmodule:: pynetdicom.presentation

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
