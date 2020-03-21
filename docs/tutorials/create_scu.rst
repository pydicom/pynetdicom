======================
Writing your first SCU
======================

.. currentmodule:: pynetdicom

In this tutorial you will:

* Use DCMTK to start an Echo SCP
* Create an application entity (AE) using *pynetdicom* and associate with the
  Echo SCP
* Turn your AE into an Echo SCU by sending a verification service request to
  the Echo SCP

If you need to install *pynetdicom* please follow the instructions in the
:doc:`installation guide</tutorials/installation>`. For this tutorial we'll
also be using DCMTK's
`storescp <https://support.dcmtk.org/docs/storescp.html>`_ application, so if
you haven't yet :ref:`installed DCMTK<tut_install_dcmtk>`, please do so. If
you're unable to install DCMTK then you can also use the `storescu.py`
application included with *pynetdicom*.

About associations
==================

Communication between DICOM applications normally proceeds in three stages;

1. First the applications negotiate to establish an *association*:

  * The association *requestor* sends an association request message which
    contains information about the services it would like to use
  * The association *acceptor* receives the request and replies with
    acceptance (along with an indication of which services it's agreed to),
    rejection or aborts the negotiation
  * Only if the *requestor* receives an association acceptance message is the
    association established

2. Then the applications make use of the services agreed to during
   association negotiation by exchanging DIMSE messages.
3. Finally, the association is released and the connection between the
   applications closed.

In general, the association *acceptor* will also be the one **providing** the
DICOM services; it'll be the *Service Class Provider*, or SCP. Conversely, the
*requestor* will usually be the one **using** the services - the *Service Class
User*, or SCU. At this stage it may be helpful to think of SCPs and SCUs as
being similar servers and clients. While this isn't strictly true - a few
DICOM services don't follow this model - it's accurate enough for the most
frequently used services like verification, storage and query/retrieve.


Start the Echo SCP
==================

For this tutorial we need an SCP that provides DICOM
:dcm:`verification<part04/chapter_A.html>`
services, usually referred to as a *Verification SCP* or *Echo SCP* for short.
DCMTK doesn't have a standalone Echo SCP application, but the `storescp`
application also supports the verification service, so we'll use that instead.

In a new terminal, start ``storescp`` listening for association requests on
port ``11112`` with the ``-v`` verbose flag. How you start ``storescp`` will
depend on your operating system; for Linux you should be able to do:

.. code-block:: text

    $ storescp 11112 -v

For Windows, **cd** to the folder containing the executable and then run:

.. code-block:: text

    $ .\storescp.exe 11112 -v

If you get an error saying the address is already in use, try again
with a different port - just remember to adapt the port used when making
association requests accordingly. Depending on your OS you may also need to
allow access through the firewall for the port you end up using.

The SCP will continue to run until you interrupt it either by closing the
terminal or by pressing ``CTRL+C``. Keep the Echo SCP running in the
background for the rest of the tutorial, but you may wish to look at it's
output every now and then to get a feel for what's happening.


Create an Application Entity and associate
==========================================

Next we're going to make a new application entity and request an association
with the Echo SCP. Create a new file ``create_scu.py``, open it in a text
editor and add the following:

.. code-block:: python
   :linenos:

    from pynetdicom import AE

    ae = AE()
    ae.add_requested_context('1.2.840.10008.1.1')
    assoc = ae.associate('localhost', 11112)
    if assoc.is_established:
        print('Association established with Echo SCP!')
        assoc.release()
    else:
        # Association rejected, aborted or never connected
        print('Failed to associate')

There's a lot going on in these few lines, so let's split it up a bit:

.. code-block:: python
   :linenos:
   :lineno-start: 3

    ae = AE()
    ae.add_requested_context('1.2.840.10008.1.1')

This creates our :class:`AE<ae.ApplicationEntity>` instance, then adds a single
:doc:`presentation context<../user/presentation>` to it using the
:meth:`~ae.ApplicationEntity.add_requested_context` method.  All association
requests must contain at least one presentation context, and in this case we've
added one that proposes the use of the verification service. We'll go into
presentation contexts and how they're used a bit more later on.

.. code-block:: python
   :linenos:
   :lineno-start: 5

    assoc = ae.associate('127.0.0.1', 11112)

Here we initiate the association negotiation by sending an association request
to the IP address ``'127.0.0.1'`` on port ``11112``. ``'127.0.0.1'`` (also
known as ``'localhost'``) is a `special IP address
<https://en.wikipedia.org/wiki/Localhost>`_ that means *this computer*. This
should be the same IP address and port that we started the ``storescp`` application
on earlier, so if you used a different port you should change this value
accordingly.

The :meth:`AE.associate()<ae.ApplicationEntity.associate>` method returns an
:class:`~association.Association` instance `assoc`, which is a subclass of
:class:`threading.Thread`. This allows us to make use of the association while
*pynetdicom* monitors the connection behind the scenes.

As mentioned earlier, an *acceptor* may do a couple of things in response to an
association request:

* Accept the association request and establish an association ʘ‿ʘ
* Reject the association request ಠ_ಠ
* Abort the association negotiation ಥ‸‸ಥ

The request may also fail because there's nothing there to associate with (a
connection failure).

.. code-block:: python
   :linenos:
   :lineno-start: 6

    if assoc.is_established:
        print('Association established with Echo SCP!')
        assoc.release()
    else:
        # Association rejected, aborted or never connected
        print('Failed to associate')

Because there's more than one possible outcomes to negotiation, we check to
see if the association :attr:`~association.Association.is_established`. If it
is, we print a message and send an association
release request using :meth:`~association.Association.release`. This ends the
association and closes the connection with the Echo SCP. On the other hand,
if we failed to establish an association for whatever reason, then the
connection is closed automatically (if required), and we don't need to do
anything further.

So, let's see what happens when we run our script. Open a new terminal and
run the file with:

.. code-block:: text

    $ python create_scu.py

You should see:

.. code-block:: text

    Association established with Echo SCP

You should see ``Association established with Echo SCP``. Congratulations!
Establishing an association is the first step any DICOM application needs to
take before it can do anything useful.

If instead you saw ``Failed to associate`` then not to worry; make sure your
Echo SCP is running and that your code is correct. If you still can't
associate, move on to the next section on troubleshooting associations.

Troubleshooting associations
----------------------------

By itself our output isn't very helpful in understanding what's going on.
Fortunately, by default *pynetdicom* has lots of logging output, which can be
sent to the terminal by calling :func:`~debug_logger`:

.. code-block:: python
   :linenos:
   :emphasize-lines: 1,3

    from pynetdicom import AE, debug_logger

    debug_logger()

    ae = AE()
    ae.add_requested_context('1.2.840.10008.1.1')
    assoc = ae.associate('localhost', 11112)
    if assoc.is_established:
        assoc.release()

If you save the changes and run ``create_scu.py`` again you'll see much more
information:

.. code-block:: text

    I: Requesting Association
    D: Request Parameters:
    D: ========================= BEGIN A-ASSOCIATE-RQ PDU =========================
    D: Our Implementation Class UID:      1.2.826.0.1.3680043.9.3811.1.5.0
    D: Our Implementation Version Name:   PYNETDICOM_150
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
    D: ========================= BEGIN A-ASSOCIATE-AC PDU =========================
    D: Their Implementation Class UID:    1.2.276.0.7230010.3.0.3.6.2
    D: Their Implementation Version Name: OFFIS_DCMTK_362
    D: Application Context Name:    1.2.840.10008.3.1.1.1
    D: Calling Application Name:    PYNETDICOM
    D: Called Application Name:     ANY-SCP
    D: Their Max PDU Receive Size:  16384
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

The log can be broken down into a couple of categories:

* Information about the state of the association and services, usually
  prefixed by ``I:``
* Errors and exceptions that have occurred, prefixed by ``E:``
* The contents of various association related messages,
  such as the SCU's association request (A-ASSOCIATE-RQ) and SCP's association
  accept (A-ASSOCIATE-AC) messages, usually prefixed by ``D:``
* Later on you'll also see summaries of the various DIMSE messages that get
  exchanged

Common issues
.............

* ``TCP Initialised Error: Connection refused`` check the IP address and port
  are correct, that the SCP is up and running and that the firewall allows
  traffic on the port
* ``Called AE title not recognised``: The SCP requires the *Called AE
  title* sent in the association request match it's own. This can be set with
  the *ae_title* keyword parameter in :meth:`~ae.ApplicationEntity.associate`
* ``Calling AE title not recognised``: The SCP requires the *Calling
  AE title* match one its familiar with. This can be set with the
  :attr:`AE.ae_title<ae.ApplicationEntity.ae_title>` property. Alternatively,
  you may need to configure the SCP with the details of your SCU
* ``Local limit exceeded``: The SCP has too many current association, try
  again later
* ``Association Aborted``: this is more unusual during association negotiation,
  (typically it's seen afterwards or during DIMSE messaging) but may be due to
  the SCP using TLS or other methods to secure the connection


Echo SCU
========

Presentation Contexts
---------------------
I've cheated a bit in our example by already including the presentation context
we need in order to be allowed to request the use of the verification service;
``1.2.840.10008.1.1`` - *Verification SOP Class*.

Presentation contexts are... I dunno, what's a good analogy?



Since we're able to associate with the Echo SCP, our next step is to request
the use of its verification service. We do this by sending a DIMSE C-ECHO
request:

.. code-block:: python
   :linenos:
   :emphasize-lines: 9

    from pynetdicom import AE, debug_logger

    debug_logger()

    ae = AE()
    ae.add_requested_context('1.2.840.10008.1.1')
    assoc = ae.associate('localhost', 11112)
    if assoc.is_established:
        status = assoc.send_c_echo()
        assoc.release()

Our only change is to include a call to
:meth:`~association.Association.send_c_echo`, which returns a *pydicom*
:class:`~pydicom.dataset.Dataset` instance *status*. If we received a
response to our C-ECHO request then `status` will contain at least an
(0000,0900) *Status* element containing the outcome of our request. If no
response was received (due to a connection failure, a timeout, or because the
association was aborted) then `status` will be an empty ``Dataset``.
