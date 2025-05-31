.. _concepts_association:

Association
-----------
When peer AEs want to communicate they must first establish an Association.

* The AE that is initiating the association (the *Requestor*) sends
  an A-ASSOCIATE message to the peer AE (the *Acceptor*) which contains a list
  of proposed presentation contexts and association negotiation items.
* The *acceptor* receives the request and responds with:

  * acceptance, which results is an association being established, or
  * rejection, which results in no association, or
  * abort, which results in no association

An association may be rejected because none of the proposed presentation
contexts are supported, or because the *Requestor* hasn't identified itself
correctly or for a :dcm:`number of other reasons<part08/sect_9.3.4.html>`.

The full service procedure for an association is found in
:dcm:`Part 8<part08/chapter_7.html#sect_7.1.2>` of the DICOM Standard.

.. _concepts_negotiation:

Association Negotiation and Extended Negotiation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Standard association negotiation usually involves the peer AEs agreeing on a
set of abstract syntax/transfer syntax combinations through the mechanism
provided by presentation contexts. In some cases it may be necessary for
communicating AEs to exchange more detailed information about features and
services they may optionally require/support. This is accomplished by sending
additional user information items during the association request:

* Asynchronous Operations Window Negotiation
* SCP/SCU Role Selection Negotiation
* SOP Class Extended Negotiation
* SOP Class Common Extended Negotiation
* User Identity Negotiation

Some of these items are conditionally required,
depending on the requested service class (such as SCP/SCU role selection
negotiation when the Query/Retrieve service class' C-GET operation is
requested). Association negotiation involving these additional items is usually
referred to as *extended negotiation*.

Extended negotiation items are defined in :dcm:`Part 7<part07/chapter_D.html>`
and :dcm:`Part 8<part08/chapter_D.html>` of the DICOM Standard.
