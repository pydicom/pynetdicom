======================
Writing your first SCU
======================

.. currentmodule:: pynetdicom

In this tutorial you will:

* Use DCMTK to start an Echo SCP
* Create an application entity (AE) using *pynetdicom* and assocate with the
  Echo SCP
* Use your AE as an Echo SCU by sending a request to the Echo SCP to use the
  verification service

If you need to install *pynetdicom* please follow the instructions in the
:doc:`installation guide</tutorials/installation>`. For this tutorial we'll
also be using DCMTK's
`storescp <https://support.dcmtk.org/docs/storescp.html>`_ application, so if
you haven't yet :ref:`installed DCMTK<tut_install_dcmtk>`, please do so.


Start the Echo SCP
==================

Before we can make association requests we need an application that acts as a
*Service Class Provider* (SCP). You can think of an SCP as being similar to
a server; it'll listen for association requests from *Service Class Users*
(SCUs) and then perform some service for them when asked. For this tutorial
we need an SCP that provides DICOM :dcm:`verification<part04/chapter_A.html>`
services, usually referred to as a *Verification SCP* or *Echo SCP* for short.
DCMTK doesn't have a standalone Echo SCP application, but the `storescp`
application also supports the verification service, so we'll use that instead.

In a new terminal start ``storescp`` on port ``11112`` with the ``-d`` debug
flag. How you start ``storescp`` will depend on your operating system. For
linux you should be able to do:

.. code-block:: text

    $ storescp 11112 -d

For Windows, **cd** to the folder containing the executable and then run:

.. code-block:: text

    $ .\storescp.exe 11112 -d

This starts the Echo SCP listening on port ``11112`` for incoming association
requests. If you get an error saying the address is already in use, try again
with a different port - just remember to adapt the port used in the Echo SCU
accordingly. Depending on your OS you may also need to allow access through
the firewall for the port you end up using.

The SCP will continue to run until you interrupt it either by closing the
terminal or by pressing ``CTRL+C``. Keep the Echo SCP running in the
background for the rest of the tutorial.

Create an Application Entity and associate
==========================================

The first thing we're going to do is create a new application entity and
request an association with the Echo SCP.

***Add more about associations.***

Create a new file ``create_scu.py``,
open it in a text editor and add the following:

.. code-block:: python
   :linenos:

    from pynetdicom import AE

    ae = AE()
    ae.add_requested_context('1.2.840.10008.1.1')
    assoc = ae.associate('localhost', 11112)
    if assoc.is_established:
        print('Association established with Echo SCP!')
        assoc.release()

There's a lot going on in these few lines, so let's look at it in two sections:

.. code-block:: python
   :linenos:
   :lineno-start: 3

    ae = AE()
    ae.add_requested_context('1.2.840.10008.1.1')

This creates an :class:`AE<ae.ApplicationEntity>` instance, then adds a single
*presentation context* to it using the
:meth:`~ae.ApplicationEntity.add_requested_context` method, which we need to
add because an association request must contain at least one.
Since all we're interested in at the moment is establishing an association
we'll go into presentation contexts a bit more later on.

.. code-block:: python
   :linenos:
   :lineno-start: 5

    assoc = ae.associate('127.0.0.1', 11112)

Here we initiate an association by sending an association request to the
IP address ``'127.0.0.1'`` on port ``11112``. ``'127.0.0.1'`` (or
``'localhost'``) is a `special IP address
<https://en.wikipedia.org/wiki/Localhost>`_ that means "the computer I'm
running on". This is the same IP address and port that we started the
``storescp`` application on earlier.

The :meth:`AE.associate()<ae.ApplicationEntity.associate>` method returns an
:class:`~association.Association` instance `assoc`, which is a subclass of
:class:`threading.Thread`.

.. code-block:: python
   :linenos:
   :lineno-start: 6

    if assoc.is_established:
        print('Association established with Echo SCP!')
        assoc.release()

In general, an SCP may do a couple of things in response to an association
request:

* Accept the association request and establish an association ʘ‿ʘ
* Reject the association request ಠ_ಠ
* Abort the association negotiation ಥ‸‸ಥ

The request may also fail because there's nothing there to associate with (a
connection failure). Because there are multiple possible outcomes, we first
test to see if the request has been accepted (and the association established)
using
:attr:`Association.is_established<association.Association.is_established>`.
Finally, we send an association release request using
:meth:`~association.Association.release` which ends the association and closes
the connection with the Echo SCP.

So, let's see what happens when we run our script. Open a new terminal and
run the file with:

.. code-block:: text

    $ python create_scu.py

You should see:

.. code-block:: text

    Association established with Echo SCP

If you don't see any output then something has gone wrong (more on
troubleshooting that in a bit). Otherwise, congratulations! Establishing an
association is the first step any DICOM application needs to take before it
can do anything useful.

By itself our output isn't very helpful in understanding what's going on.
Fortunately, by default *pynetdicom* has lots of logging output, which can be
sent to the terminal by calling :func:`~debug_logger`:

.. code-block:: python
   :linenos:

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

Troubleshooting an association request
--------------------------------------

If you see ``TCP Initialised Error: Connection refused`` double check that the
IP address and port that you're sending your association requests to is
correct and that the SCP is up and running.

Common reasons for a rejected association may include:

* ``Reason: Called AE title not recognised``: The SCP requires the *Called AE
  title* sent in the association request match it's own.
* ``Reason: Calling AE title not recognised``: The SCP requires your *Calling
  AE title* match one its familiar with.
* ``Local limit exceeded``: The SCP has too many current association, try
  again later

Receiving an abort in response to an association request is more unusual and
may be due to things like:

* The SCP uses TLS or other methods to secure the connection which you've
  forgotten to include
* A failed *User Identity* negotiation
* No accepted presentation contexts


Echo SCU
========

Since we're able to associate with the Echo SCP our next step is to request
the use of its verification service by sending a C-ECHO request:

.. code-block:: python
   :linenos:

    from pynetdicom import AE, debug_logger

    debug_logger()

    ae = AE()
    ae.add_requested_context('1.2.840.10008.1.1')
    assoc = ae.associate('localhost', 11112)
    if assoc.is_established:
        status = assoc.send_c_echo()
        assoc.release()

Our only change is to include a call to
:meth:`~association.Association.send_c_echo`, which returns `status` which is
a *pydicom* :class:`~pydicom.dataset.Dataset` instance. If we received a
response to our C-ECHO request then `status` will contain (at a minimum) a
(0000,0900) *Status* element containing the outcome of our request. If no
response was received (due to a connection failure, a timeout or because the
association was aborted) then `status` will be an empty ``Dataset``.

Presentation Contexts
---------------------
I've cheated a bit in our example by already including the presentation context
we need in order to be allowed to request the use of the verification service.
Presentation contexts are... I dunno, what's a good analogy?
