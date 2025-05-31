======================
Writing your first SCU
======================

.. currentmodule:: pynetdicom

This tutorial is intended for people who are new to *pynetdicom*. In it you'll:

* Learn a bit about the basics of DICOM networking
* Learn how to use the :doc:`echoscp<../apps/echoscp>` application
  that comes with *pynetdicom*
* Create an new application entity (AE) and associate with a DICOM peer
* Learn how to perform some basic troubleshooting of associations
* Modify your AE to be an Echo SCU

The tutorial is written for *pynetdicom* 3.0 and higher, which supports Python
3.10+. You can tell which version of *pynetdicom* you have by running
the following command::

    $ python -m pynetdicom --version

If you get an error or if your version is earlier than 3.0, then install or
upgrade *pynetdicom* by following the instructions in the
:doc:`installation guide</user/installation>`. For
this tutorial we'll also be using the :doc:`echoscp<../apps/echoscp>`
application that comes with *pynetdicom*.


DICOM networking
================

*pynetdicom* is an implementation of the :dcm:`DICOM Upper Layer Protocol for
TCP/IP<part08/chapter_9.html>`, which is used to facilitate communication
between DICOM *Application Entities* (AEs) over a `TCP connection
<https://en.wikipedia.org/wiki/Transmission_Control_Protocol>`_. Communication
between two AEs starts by establishing a TCP connection, then progresses to
negotiating an *association*, which is the term used to describe the
communications channel between the AEs and the set of rules that govern their
expected behaviour.

The AE that initiated the connection, the *requestor*, sends an
:dcm:`A-ASSOCIATE-RQ<part08/sect_9.3.2.html>` message proposing which
:dcm:`DICOM services<part04/PS3.4.html>` it would like
to use. The receiving AE, the *acceptor*, goes through the proposal and either:

* Accepts the association and replies with an :dcm:`A-ASSOCIATE-AC
  <part08/sect_9.3.3.html>` message. However, just because an association has
  been accepted doesn't mean that the proposed services have also been
  accepted.
* Rejects the association by replying with an :dcm:`A-ASSOCIATE-RJ
  <part08/sect_9.3.4.html>` message.
* Aborts the association negotiation by sending an :dcm:`A-ABORT
  <part08/sect_9.3.8.html>` message.

When the *requestor* receives the A-ASSOCIATE-AC message the negotiation phase
ends and the association becomes *established*. The two AEs can then
use the services that were agreed upon during negotiation by exchanging
:dcm:`DIMSE-C<part07/sect_7.5.html#sect_7.5.1>` and :dcm:`DIMSE-N
<part07/sect_7.5.2.html>` messages.

When the association is no longer needed, it can be released by sending an
:dcm:`A-RELEASE-RQ<part08/sect_9.3.6.html>` message. The association can be
also be aborted at any time when either AE sends an A-ABORT message. Once
the association has been aborted or released, the TCP connection is closed
(if still open) and communication between the two AEs ends.

What *is* an SCU?
-----------------

If you're new to DICOM, you might be wondering what an Echo SCU or SCP actually
*are*. The answer lies in the DICOM services that are available to an
association; if an AE *provides* a service then it's referred to as a *Service
Class Provider*, or SCP, while if an AE *uses* a service then it's a *Service
Class User*, or SCU. A *Verification SCU* then, is an AE that uses the DICOM
:dcm:`verification service<part04/chapter_A.html>`, a *Storage SCP* is an AE
that provides the DICOM :dcm:`storage service<part04/chapter_B.html>`, and so
on. Because the verification service is the sole user of
the DIMSE :dcm:`C-ECHO<part07/chapter_9.html#sect_9.1.5>` messages, the
labels "Verification SCU" and "Verification SCP"
are frequently shortened to "Echo SCU" and "Echo SCP" instead.

The verification service itself is used to verify basic DICOM connectivity
between two AEs; the Echo SCU sends a :dcm:`C-ECHO request
<part07/sect_9.3.5.html#sect_9.3.5.1>` to the SCP, which
replies with an acknowledgement. By doing this you can test
whether a DICOM application is active and reachable by your SCU, that your
configuration is correct and that the connection isn't being blocked by a
firewall or anything else.


OK, enough about DICOM networking, let's get started.


Start the Echo SCP
==================

For this tutorial we need an Echo SCP. To make things simpler we'll use the
:doc:`echoscp <../apps/echoscp>` application that comes with
*pynetdicom*, but you could also use any third-party application that supports
the verification service as an SCP, such as DCMTK's
`storescp <https://support.dcmtk.org/docs/storescp.html>`_. To find out if
an application supports the verification service you should check their
DICOM conformance statement.

In a new terminal, start :doc:`echoscp<../apps/echoscp>` listening for
connection requests on
port ``11112`` with the ``-v`` verbose flag (or you could use the ``-d`` debug
flag for even more output):

.. code-block:: text

    $ python -m pynetdicom echoscp 11112 -v

If you get an error saying the address is already in use, try again
with a different port - just remember to adapt the port used when making
association requests accordingly. Depending on your OS or system configuration
you may also need to allow access through the firewall for the port you end
up using.

The SCP will continue to run until you interrupt it, either by closing the
terminal or by pressing ``CTRL+C``. Keep the application running in the
background for the rest of the tutorial, but you may wish to look at its
output every now and then to get a feel for what's happening at the other
end of the association.


Create an Application Entity and associate
==========================================

Next we're going to make a new application entity and request an association
with the Echo SCP. Create a new file ``my_scu.py``, open it in a text
editor and add the following:

.. code-block:: python
   :linenos:

    from pynetdicom import AE

    ae = AE()
    ae.add_requested_context("1.2.840.10008.1.1")
    assoc = ae.associate("127.0.0.1", 11112)
    if assoc.is_established:
        print("Association established with Echo SCP!")
        assoc.release()
    else:
        # Association rejected, aborted or never connected
        print("Failed to associate")

There's a lot going on in these few lines, so let's split it up a bit:

.. code-block:: python
   :linenos:
   :lineno-start: 1

    from pynetdicom import AE

    ae = AE()
    ae.add_requested_context("1.2.840.10008.1.1")

This imports the :class:`AE<ae.ApplicationEntity>` class, creates a new
``AE`` instance, `ae`, then adds a single
:doc:`presentation context</user/presentation_introduction>` with an abstract syntax of
``"1.2.840.10008.1.1"`` using the :meth:`~ae.ApplicationEntity.add_requested_context`
method.  All association requests must contain at least one presentation context,
and in this case we've proposed one with the abstract syntax for the verification service.
We'll go into presentation contexts and how they're used to define an
association's services a bit more later on.

.. code-block:: python
   :linenos:
   :lineno-start: 5

    assoc = ae.associate("127.0.0.1", 11112)

Here we initiate the association negotiation by connecting to the IP address
``"127.0.0.1"`` on port ``11112`` and sending an association request.
``"127.0.0.1"`` (also known as ``"localhost"``) is a `special IP address
<https://en.wikipedia.org/wiki/Localhost>`_ that means *this computer*. This
should be the same IP address and port that you started the
:doc:`echoscp<../apps/echoscp>` application on earlier, so if you used a
different port you should change this value accordingly.

.. note::

    If the SCP isn't running on your local computer, you call
    :meth:`AE.associate()<ae.ApplicationEntity.associate>` using
    the actual IP address and listen port of the SCP, for example
    ``ae.associate("148.60.155.4", 104)``.

The :meth:`AE.associate()<ae.ApplicationEntity.associate>` method returns an
:class:`~association.Association` instance `assoc`, which is a subclass of
:class:`threading.Thread`. This allows us to make use of the
association while *pynetdicom* monitors the connection behind the scenes.

.. code-block:: python
   :linenos:
   :lineno-start: 6

    if assoc.is_established:
        print("Association established with Echo SCP!")
        assoc.release()
    else:
        # Association rejected, aborted or never connected
        print("Failed to associate")

As mentioned earlier, an *acceptor* may do a couple of things in response to an
association request; accept it, reject it or abort the negotiation entirely.
The request may also fail because there's nothing there to associate with (a
connection failure).

Because there's more than one possible outcome to negotiation, we check to
see if the association has been established using
:attr:`~association.Association.is_established`. If it
is, we print a message and send an association
release request using :meth:`~association.Association.release`. This ends the
association and closes the connection with the Echo SCP. On the other hand,
if we failed to establish an association for whatever reason, the
connection is closed automatically (if required), and we don't need to do
anything further.

If you don't release the association yourself then it'll remain established
until the connection is closed, usually when a timeout expires on
either the *requestor* or *acceptor* AE.

So, let's see what happens when we run our code. Open a new terminal and
run the file:

.. code-block:: text

    $ python my_scu.py

If everything worked correctly, you should see:

.. code-block:: text

    Association established with Echo SCP

And if you take a look at the output for :doc:`echoscp<../apps/echoscp>` you
should see it accept
the association request and notify you of its release:

.. code-block:: text

    I: Accepting Association
    I: Association Released

If instead you saw ``Failed to associate`` then not to worry; make sure the
Echo SCP is running and your code is correct. If you still can't
associate, move on to the next section on troubleshooting associations.

Troubleshooting associations
----------------------------

By itself our output isn't very helpful in understanding what's going on.
Fortunately *pynetdicom* has lots of logging output, but by default its
configured to send it all to the :class:`~logging.NullHandler` which prevents
warnings and errors being printed to ``sys.stderr``. This can be undone by
importing :mod:`logging` and setting ``logging.getLogger("pynetdicom").handlers = []``
or by adding your own logging handlers.

If you need to troubleshoot, then a quick way to send the debugging output to
``sys.stderr`` is by calling :func:`~debug_logger`:

.. code-block:: python
   :linenos:
   :emphasize-lines: 1,3

    from pynetdicom import AE, debug_logger

    debug_logger()

    ae = AE()
    ae.add_requested_context("1.2.840.10008.1.1")
    assoc = ae.associate("127.0.0.1", 11112)
    if assoc.is_established:
        assoc.release()

If you save the changes and run ``my_scu.py`` again you'll see much more
information:

.. code-block:: text

    $ python my_scu.py
    I: Requesting Association
    D: Request Parameters:
    D: ======================= OUTGOING A-ASSOCIATE-RQ PDU ========================
    D: Our Implementation Class UID:      1.2.826.0.1.3680043.9.3811.2.0.0
    D: Our Implementation Version Name:   PYNETDICOM_200
    D: Application Context Name:    1.2.840.10008.3.1.1.1
    D: Calling Application Name:    PYNETDICOM
    D: Called Application Name:     ANY-SCP
    D: Our Max PDU Receive Size:    16382
    D: Presentation Context:
    D:   Context ID:        1 (Proposed)
    D:     Abstract Syntax: =Verification SOP Class
    D:     Proposed SCP/SCU Role: Default
    D:     Proposed Transfer Syntaxes:
    D:       =Implicit VR Little Endian
    D:       =Explicit VR Little Endian
    D:       =Explicit VR Big Endian
    D: Requested Extended Negotiation: None
    D: Requested Common Extended Negotiation: None
    D: Requested Asynchronous Operations Window Negotiation: None
    D: Requested User Identity Negotiation: None
    D: ========================== END A-ASSOCIATE-RQ PDU ==========================
    D: Accept Parameters:
    D: ======================= INCOMING A-ASSOCIATE-AC PDU ========================
    D: Their Implementation Class UID:    1.2.826.0.1.3680043.9.3811.2.0.0
    D: Their Implementation Version Name: PYNETDICOM_200
    D: Application Context Name:    1.2.840.10008.3.1.1.1
    D: Calling Application Name:    PYNETDICOM
    D: Called Application Name:     ANY-SCP
    D: Their Max PDU Receive Size:  16382
    D: Presentation Contexts:
    D:   Context ID:        1 (Accepted)
    D:     Abstract Syntax: =Verification SOP Class
    D:     Accepted SCP/SCU Role: Default
    D:     Accepted Transfer Syntax: =Explicit VR Little Endian
    D: Accepted Extended Negotiation: None
    D: Accepted Asynchronous Operations Window Negotiation: None
    D: User Identity Negotiation Response: None
    D: ========================== END A-ASSOCIATE-AC PDU ==========================
    I: Association Accepted
    I: Releasing Association

Here you can see the stages of the association:

1. The association negotiation is initiated by sending an A-ASSOCIATE-RQ
   message
2. An A-ASSOCIATE-AC message is received and the association accepted
3. The association is released.

In general, the debugging log can be broken down into a couple of categories:

* Information about the state of the association and services, usually
  prefixed by ``I:``
* Errors and exceptions that have occurred, prefixed by ``E:``
* The contents of various association related messages,
  such as the A-ASSOCIATE-RQ and A-ASSOCIATE-AC messages, as well as
  summaries of exchanged DIMSE messages (not shown here), usually prefixed by
  ``D:``

The first step to troubleshooting an association should be to look at the debug
output. Some common reasons for an association failure are:

* ``TCP Initialisation Error: Connection refused`` indicates that nothing is
  listening on the IP address and port you specified. Check they're correct,
  that the SCP is up and running, and that the firewall is allowing traffic
  through.
* ``Called AE title not recognised``: indicates that the SCP requires the
  A-ASSOCIATE-RQ's *Called AE Title* value match its own. This can
  be set with the *ae_title* keyword parameter in
  :meth:`~ae.ApplicationEntity.associate`
* ``Calling AE title not recognised``: indicates that the SCP requires the
  A-ASSOCIATE-RQ's *Calling AE Title* value match one its familiar with. This
  can be set with the :attr:`AE.ae_title<ae.ApplicationEntity.ae_title>`
  property. Alternatively, you may need to configure the SCP with the details
  of your SCU
* ``Local limit exceeded``: The SCP has too many current associations active,
  try again later
* ``Association Aborted``: this is more unusual during association negotiation,
  typically it's seen afterwards or during DIMSE messaging. It may be due to
  the SCP using TLS or other methods to secure the connection

Hopefully by this point you've managed to get your AE associating with the SCP,
so let's turn it into an Echo SCU.


Creating the Echo SCU
=====================

Presentation Contexts
---------------------

.. note::

    What follows is a basic introduction to presentation contexts. More
    information is available in the :doc:`presentation contexts
    </user/presentation_introduction>` section of the User Guide.

We've cheated a little bit in our code by including a presentation context
used to propose the use of the verification service;
``1.2.840.10008.1.1`` - *Verification SOP Class*. This is visible in the
debug output in the A-ASSOCIATE-RQ section as::

    D: Presentation Context:
    D:   Context ID:        1 (Proposed)
    D:     Abstract Syntax: =Verification SOP Class
    D:     Proposed SCP/SCU Role: Default
    D:     Proposed Transfer Syntaxes:
    D:       =Implicit VR Little Endian
    D:       =Explicit VR Little Endian
    D:       =Explicit VR Big Endian

Presentation contexts are how DICOM applications agree on which services
are available to an association. Each DICOM service has a corresponding set of
*SOP Class UIDs* which can be found in the relevant sections of :dcm:`Part 3 of
the DICOM Standard<part03/PS3.3.html>`. Setting one of these as the *abstract
syntax* parameter in a proposed presentation context indicates to the
*acceptor* that the corresponding service is requested for data matching that
SOP class. Additionally, the presentation context includes a description on
how any exchanged data is to be encoded, its *transfer syntax*.

So if you want to use the DICOM :dcm:`verification<part04/chapter_A.html>`
service, you propose a presentation context for the *Verification SOP Class*.
If you wanted to use the :dcm:`storage<part04/chapter_B.html>` service
to store *CT Images*, you'd propose a presentation context for the *CT Image
Storage* SOP class with a transfer syntax that matches the encoding of the
CT data.

When the *acceptor* receives the proposed presentation contexts it goes through
them one-by-one, either accepting or rejecting each. The results are visible
in the A-ASSOCIATE-AC section of the debug log:

.. code-block:: text

    D: Presentation Contexts:
    D:   Context ID:        1 (Accepted)
    D:     Abstract Syntax: =Verification SOP Class
    D:     Accepted SCP/SCU Role: Default
    D:     Accepted Transfer Syntax: =Explicit VR Little Endian

Here you can see that the context was accepted and any transferred data must
use ``Explicit VR Little Endian`` encoding. If a context is rejected and
you still try to use it, or if a context is accepted but your data isn't
encoded with the same transfer syntax, you'll get a ``ValueError`` exception
similar to:

.. code-block:: text

    No presentation context for 'CT Image Storage' has been accepted by the peer with 'Implicit VR Little Endian' transfer syntax for the SCU role


Turning our AE into an Echo SCU
-------------------------------

Since we're able to associate with the Echo SCP, our next step is to request
the use of it's verification service. We do this by sending a DIMSE C-ECHO
request:

.. code-block:: python
   :linenos:
   :emphasize-lines: 9

    from pynetdicom import AE, debug_logger

    debug_logger()

    ae = AE()
    ae.add_requested_context("1.2.840.10008.1.1")
    assoc = ae.associate("127.0.0.1", 11112)
    if assoc.is_established:
        status = assoc.send_c_echo()
        assoc.release()

The only thing we need to change is to include a call to
:meth:`~association.Association.send_c_echo`, which sends
the C-ECHO request and returns a *pydicom*
:class:`~pydicom.dataset.Dataset` instance *status*. If we received a
response to our C-ECHO request, then `status` will contain at least an
(0000,0900) *Status* element containing the outcome of our request. If no
response was received (due to a connection failure, a timeout, or because the
association was aborted) then `status` will be an empty
:class:`~pydicom.dataset.Dataset`.

The *Status* element value is a code that indicates the result of the C-ECHO
request. Each service class has a number of defined status codes which are
usually a mix of generic codes for each DIMSE message type and code values
specific to the service class. For example, if you look at the API reference
for :meth:`~association.Association.send_c_store` you'll see there are general
C-STORE status codes, such as ``0x0000`` (Success), as
well as service specific codes, such as ``0xC000`` (Failure - cannot
understand) for the storage
service. The API reference for each ``Association.send_*`` method contains a
list of possible status codes and their meaning.

.. note::

    Service specific status codes are defined in the corresponding sections of
    :dcm:`Part 3<part03/PS3.3.html>` of the DICOM Standard, while the general
    codes are in Sections :dcm:`9<part07/chapter_9.html>` and
    :dcm:`10<part07/chapter_10.html>` and :dcm:`Annex C<part07/chapter_C.html>`
    of Part 7.

If you run your modified code then at the end of the output you should see:

.. code-block:: text

    I: Association Accepted
    I: Sending Echo Request: MsgID 1
    D: pydicom.read_dataset() TransferSyntax="Little Endian Implicit"
    I: Received Echo Response (Status: 0x0000 - Success)
    I: Releasing Association

The SCP has responded with a ``Status: 0x0000 - Success``, which indicates that
the verification service request was successful. Congratulations, you've
written your first DICOM application using *pynetdicom*.

Next steps
==========

We recommend that you move on to :doc:`writing your first SCP<create_scp>`
next. However, you might also be interested in the
:doc:`SCU examples</examples/index>` available in the documentation, or the
:doc:`applications</examples/index>` that come with *pynetdicom*.
