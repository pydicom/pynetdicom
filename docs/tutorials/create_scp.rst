======================
Writing your first SCP
======================

.. currentmodule:: pynetdicom

This is the second tutorial for people who are new to *pynetdicom*. If you
missed the :doc:`first one<create_scu>` you should check it out before
continuing.

In this tutorial you'll:

* Learn about DICOM Data Sets and the DICOM File Format
* Create a new Storage SCP application using *pynetdicom*
* Learn about the event-handler system and add handlers to your SCP
* Send data to your SCP using *pynetdicom's*
  :doc:`storescu<../apps/storescu>` application

If you need to install *pynetdicom* please follow the instructions in the
:doc:`installation guide</user/installation>`. For this tutorial we'll
also be using the :doc:`storescu<../apps/storescu>` application that comes with
*pynetdicom*.


The Data Set
============

This tutorial is about creating an SCP for the DICOM :dcm:`storage service
<part04/chapter_B.html>`, which is used to transfer DICOM
:dcm:`Data Sets<part05/chapter_7.html>` from one AE to another. A Data Set,
which from now on we'll just refer to as a *dataset*, is a representation of
a real world object, like a slice of a :dcm:`CT<part03/sect_A.3.html>`
or a :dcm:`structured report<part03/sect_A.35.html>`. A dataset is a
collection of :dcm:`Data Elements<part05/chapter_7.html#sect_7.1>`, where each
*element* represents an attribute of the object.

Datasets are usually used to store information from the medical procedures
undergone by a patient, however the DICOM Standard also puts them to use as
part of the networking protocol and in service provision.

.. note::

  While it's not required for this tutorial, you should be comfortable using
  :gh:`pydicom <pydicom>` to create new datasets and
  read, write or modify existing ones. If you're new to *pydicom* then you
  should start with the `Dataset Basics
  <https://pydicom.github.io/pydicom/stable/tutorials/dataset_basics.html>`_
  tutorial.


Creating a Storage SCP
======================

Let's create a simple Storage SCP for receiving *CT Image* datasets encoded
using the *Explicit VR Little Endian* transfer syntax. Create a new file
``my_scp.py``, open it in a text editor and add the following:

.. code-block:: python
   :linenos:

    from pydicom.uid import ExplicitVRLittleEndian

    from pynetdicom import AE, debug_logger
    from pynetdicom.sop_class import CTImageStorage

    debug_logger()

    ae = AE()
    ae.add_supported_context(CTImageStorage, ExplicitVRLittleEndian)
    ae.start_server(("127.0.0.1", 11112), block=True)

Let's break this down

.. code-block:: python
   :linenos:

    from pydicom.uid import ExplicitVRLittleEndian

    from pynetdicom import AE, debug_logger
    from pynetdicom.sop_class import CTImageStorage

We import the :ref:`UID<concepts_uids>` for :obj:`Explicit VR Little Endian
<pydicom.uid.ExplicitVRLittleEndian>` from *pydicom*, and
the :class:`AE<ae.ApplicationEntity>` class, :func:`~debug_logger` function and
the UID for :attr:`CT Image Storage
<sop_class.CTImageStorage>` from *pynetdicom*.

.. code-block:: python
   :linenos:
   :lineno-start: 6

    debug_logger()

    ae = AE()
    ae.add_supported_context(CTImageStorage, ExplicitVRLittleEndian)

Just as with the Echo SCU from the previous tutorial, we create a
new :class:`AE<ae.ApplicationEntity>` instance. However, because this time
we'll be the association *acceptor*, its up to us to specify what
:doc:`presentation contexts</user/presentation_acceptor>` are *supported* rather than
*requested*. Since we'll be supporting the storage of *CT Images* encoded
using the *Explicit VR Little Endian* transfer syntax we use
:meth:`~ae.ApplicationEntity.add_supported_context` to add a corresponding
presentation context.

.. code-block:: python
   :linenos:
   :lineno-start: 10

    ae.start_server(("127.0.0.1", 11112), block=True)

The call to :meth:`~ae.ApplicationEntity.start_server` starts our SCP listening
for association requests on port ``11112`` in *blocking* mode.

Open a new terminal and start our SCP running:

.. code-block:: text

    $ python my_scp.py

And in another terminal, run :doc:`storescu<../apps/storescu>` on
:gh:`this dataset
<pynetdicom/raw/master/pynetdicom/tests/dicom_files/CTImageStorage.dcm>`:

.. code-block:: text

    $ python -m pynetdicom storescu 127.0.0.1 11112 CTImageStorage.dcm -v -cx

You should see the following output:

.. code-block:: text

    I: Requesting Association
    I: Association Accepted
    I: Sending file: CTImageStorage.dcm
    I: Sending Store Request: MsgID 1, (CT)
    I: Received Store Response (Status: 0xC211 - Failure)
    I: Releasing Association

As you can see, ``storescu`` successfully associated with our SCP and sent a
store request, but received a response containing a failure status ``0xC211``.
For the storage service, :dcm:`statuses<part04/sect_B.2.3.html>` in the
``0xC000`` to ``0xCFFF`` range fall under 'cannot understand', which is a
generic failure status. In *pynetdicom's* case this range of statuses is used
to provide more specific error information; by checking the
:ref:`storage service class page<service_store_pynd>` in the
documentation you can find the corresponding error to a given status.

In the case of ``0xC211`` the error is 'Unhandled exception raised by the
handler bound to ``evt.EVT_C_STORE``', so what does the output from the SCP
look like?

.. code-block:: text

    ...
    I: Received Store Request
    D: ========================== INCOMING DIMSE MESSAGE ==========================
    D: Message Type                  : C-STORE RQ
    D: Presentation Context ID       : 1
    D: Message ID                    : 1
    D: Affected SOP Class UID        : CT Image Storage
    D: Affected SOP Instance UID     : 1.3.6.1.4.1.5962.1.1.1.1.1.20040119072730.12322
    D: Data Set                      : Present
    D: Priority                      : Low
    D: ============================ END DIMSE MESSAGE =============================
    E: Exception in the handler bound to 'evt.EVT_C_STORE'
    E: No handler has been bound to 'evt.EVT_C_STORE'
    Traceback (most recent call last):
      File ".../pynetdicom/service_class.py", line 1406, in SCP
        {'request' : req, 'context' : context.as_tuple}
      File ".../pynetdicom/events.py", line 212, in trigger
        return handlers[0](evt)
      File ".../pynetdicom/events.py", line 820, in _c_store_handler
        raise NotImplementedError("No handler has been bound to 'evt.EVT_C_STORE'")
    NotImplementedError: No handler has been bound to 'evt.EVT_C_STORE'

As the log confirms, the failure was caused by not having a handler bound to
the ``evt.EVT_C_STORE`` event, so we'd better fix that.

Events and handlers
===================

*pynetdicom* uses an :doc:`event-handler system</user/events_types>` to give
access to data exchanged between AEs and as a way to customise the responses to
service requests. Events come in two types: :ref:`notification events
<events_notification>`, where the user is notified some event has occurred,
and :ref:`intervention events<events_intervention>`,
where the user must intervene in some way. The idea is that you bind a
callable function, the *handler*, to an event, and then when the event occurs
the handler is called.

There are two areas where user intervention is required:

1. Responding to :ref:`extended negotiation<user_assoc_extneg>` items during
   association negotiation. You most likely will only have to worry about this
   if you're using :dcm:`User Identity negotiation<part07/sect_D.3.3.7.html>`.
2. Responding to a service request when acting as an
   SCP, such as when an SCU sends a store request to a Storage SCP...

So we need to :func:`bind a handler<_handlers.doc_handle_store>` to
``evt.EVT_C_STORE`` to respond to incoming store requests.

.. code-block:: python
   :linenos:
   :emphasize-lines: 3,8-10,12,16

    from pydicom.uid import ExplicitVRLittleEndian

    from pynetdicom import AE, debug_logger, evt
    from pynetdicom.sop_class import CTImageStorage

    debug_logger()

    def handle_store(event):
        """Handle EVT_C_STORE events."""
        return 0x0000

    handlers = [(evt.EVT_C_STORE, handle_store)]

    ae = AE()
    ae.add_supported_context(CTImageStorage, ExplicitVRLittleEndian)
    ae.start_server(("127.0.0.1", 11112), block=True, evt_handlers=handlers)

We import ``evt``, which contains all the events, and add a function
``handle_store`` which will be our handler. All handlers must, at a minimum,
take a single parameter `event`, which is an :class:`~events.Event` instance.
If you look at the :func:`documentation for EVT_C_STORE handlers
<_handlers.doc_handle_store>`, you'll see that they
must return *status* as either an :class:`int` or *pydicom*
:class:`~pydicom.dataset.Dataset`. This is the same (0000,0900) *Status*
value you saw in the previous tutorial, only this will be the value sent by the
SCP to the SCU. In our ``handle_store``
function we're returning an ``0x0000`` status, which indicates that the
storage operation was a success, but at this stage we're not actually storing
anything.

We bind our handler to the corresponding event by passing ``handlers``
to :func:`~ae.ApplicationEntity.start_server` via the
`evt_handlers` keyword parameter.

Interrupt the terminal running ``my_scp.py`` using ``CTRL+C`` and
then restart it. This time when you run :doc:`storescu<../apps/storescu>`
you should see:

.. code-block:: text

    $ python -m pynetdicom storescu 127.0.0.1 11112 CTImageStorage.dcm -v -cx
    I: Requesting Association
    I: Association Accepted
    I: Sending file: CTImageStorage.dcm
    I: Sending Store Request: MsgID 1, (CT)
    I: Received Store Response (Status: 0x0000 - Success)
    I: Releasing Association


Customising the handler
=======================

Our Storage SCP is returning success statuses for all incoming requests even
though we're not actually storing anything, so our next step is to modify the
handler to write the dataset to file. Before we do that we need to know a bit
about the DICOM File Format.

The DICOM File Format
---------------------

To be conformant to the DICOM Standard, when a dataset is written to file it
should be written in the :dcm:`DICOM File Format<part10/chapter_7.html>`,
which consists of four main parts:

1. A header containing an 128-byte preamble
2. A 4-byte ``DICM`` prefix (``0x4449434D`` in hex)
3. The encoded *File Meta Information*, which is a small dataset containing
   meta information about the actual dataset
4. The encoded dataset itself

The File Meta Information should contain at least the following elements:

+-------------+--------------------------------------+----+
| Tag         | Description                          | VR |
+=============+======================================+====+
| (0002,0000) | *File Meta Information Group Length* | UL |
+-------------+--------------------------------------+----+
| (0002,0001) | *File Meta Information Version*      | OB |
+-------------+--------------------------------------+----+
| (0002,0002) | *Media Storage SOP Class UID*        | UI |
+-------------+--------------------------------------+----+
| (0002,0003) | *Media Storage SOP Instance UID*     | UI |
+-------------+--------------------------------------+----+
| (0002,0010) | *Transfer Syntax UID*                | UI |
+-------------+--------------------------------------+----+
| (0002,0012) | *Implementation Class UID*           | UI |
+-------------+--------------------------------------+----+

While a dataset can be stored without the header, prefix and file meta
information, to do so is non-conformant to the DICOM Standard. It also becomes
more difficult to correctly determine the encoding of the dataset, which is
important when trying to read or transfer it. Fortunately, *pynetdicom* and
*pydicom* make it very easy to store datasets correctly. Change your handler
code to:

.. code-block:: python

    def handle_store(event):
        """Handle EVT_C_STORE events."""
        ds = event.dataset
        ds.file_meta = event.file_meta
        ds.save_as(ds.SOPInstanceUID, write_like_original=False)

        return 0x0000

Where :attr:`event.dataset<events.Event.dataset>` is the decoded dataset
received from the SCU as a *pydicom* :class:`~pydicom.dataset.Dataset` and
:attr:`event.file_meta<events.Event.file_meta>` is a
:class:`~pydicom.dataset.Dataset` containing conformant File Meta Information
elements. We set the dataset's :attr:`~pydicom.dataset.FileDataset.file_meta`
attribute and then save it to a file
named after its (0008,0018) *SOP Instance UID*,  which is an identifier unique
to each dataset that *should* be present. We pass
``write_like_original = False`` to :meth:`Dataset.save_as()
<pydicom.dataset.Dataset.save_as>` to
ensure that the file is written in the DICOM File Format.

There are a couple of things to be aware of when dealing with
:class:`Datasets<pydicom.dataset.Dataset>`:

* Because *pydicom* uses a deferred-read system, the
  :class:`Dataset<pydicom.dataset.Dataset>` returned by
  :attr:`event.dataset<events.Event.dataset>` may raise an exception when any
  element is first accessed.
* The dataset may not contain a particular element, even if it's supposed to.
  Always assume a dataset is non-conformant, check to see if what you need
  is present and handle missing elements appropriately. The
  easiest way to check if an element is in a dataset is with the
  :func:`in<operator.__contains__>` operator: ``'PatientName' in ds``, but
  :meth:`Dataset.get()<pydicom.dataset.Dataset.get>` or :func:`getattr` are
  also handy.

If you restart ``my_scp.py`` and re-send the dataset using
:doc:`storescu<../apps/storescu>` you  should see that a file containing the
transferred dataset named
``1.3.6.1.4.1.5962.1.1.1.1.1.20040119072730.12322`` has been written to the
directory containing ``my_scp.py``.

Expanding the supported data
----------------------------

Our Storage SCP is pretty limited at the moment, only handling one type of
dataset (technically, one *SOP Class*) encoded in a particular way. We can
change that to handle all the storage service's SOP Classes by adding more
supported presentation contexts:

.. code-block:: python
   :linenos:
   :emphasize-lines: 1-4,19-23

    from pynetdicom import (
        AE, debug_logger, evt, AllStoragePresentationContexts,
        ALL_TRANSFER_SYNTAXES
    )

    debug_logger()

    def handle_store(event):
        """Handle EVT_C_STORE events."""
        ds = event.dataset
        ds.file_meta = event.file_meta
        ds.save_as(ds.SOPInstanceUID, write_like_original=False)

        return 0x0000

    handlers = [(evt.EVT_C_STORE, handle_store)]

    ae = AE()
    storage_sop_classes = [
        cx.abstract_syntax for cx in AllStoragePresentationContexts
    ]
    for uid in storage_sop_classes:
        ae.add_supported_context(uid, ALL_TRANSFER_SYNTAXES)

    ae.start_server(("127.0.0.1", 11112), block=True, evt_handlers=handlers)

:attr:`~presentation.AllStoragePresentationContexts` is a list of pre-built
presentation contexts, one for every SOP Class in the storage service. However,
by default these contexts only support the uncompressed transfer syntaxes. To
support both compressed and uncompressed transfer syntaxes we separate out the
abstract syntaxes then use :meth:`~ae.ApplicationEntity.add_supported_context`
with :attr:`~ALL_TRANSFER_SYNTAXES` instead.

Optimising and passing extra arguments
--------------------------------------

If you don't actually need a decoded :class:`~pydicom.dataset.Dataset` object
then it's faster to write the encoded dataset directly to file; this skips
having to decode and then re-encode the dataset at the cost of slightly more
complex code:

.. code-block:: python
   :linenos:
   :emphasize-lines: 1-2,11,13-17,19-23,27

    import uuid
    from pathlib import Path

    from pynetdicom import (
        AE, debug_logger, evt, AllStoragePresentationContexts,
        ALL_TRANSFER_SYNTAXES
    )

    debug_logger()

    def handle_store(event, storage_dir):
        """Handle EVT_C_STORE events."""
        try:
            os.makedirs(storage_dir, exist_ok=True)
        except:
            # Unable to create output dir, return failure status
            return 0xC001

        path = Path(storage_dir) / f"{uuid.uuid4()}"
        with path.open('wb') as f:
            # Write the preamble, prefix, file meta information elements
            #   and the raw encoded dataset to `f`
            f.write(event.encoded_dataset())

        return 0x0000

    handlers = [(evt.EVT_C_STORE, handle_store, ['out'])]

    ae = AE()
    storage_sop_classes = [
        cx.abstract_syntax for cx in AllStoragePresentationContexts
    ]
    for uid in storage_sop_classes:
        ae.add_supported_context(uid, ALL_TRANSFER_SYNTAXES)

    ae.start_server(("127.0.0.1", 11112), block=True, evt_handlers=handlers)

We've modified the handler to use :meth:`~pynetdicom.events.Event.encoded_dataset`,
which writes the preamble, prefix, file meta information elements and the
:attr:`raw dataset<dimse_primitives.C_STORE.DataSet>` received in the C-STORE
request directly to file. If you need separate access to just the encoded dataset
then you can call :meth:`~pynetdicom.events.Event.encoded_dataset` with
`include_meta=False` instead.

The second change we've made is to demonstrate how extra parameters can be
passed to the handler by binding using a 3-tuple rather than a 2-tuple. The
third item in the :class:`tuple` should be a :class:`list` of objects;
each of the list's items will be passed as a separate parameter. In
our case the string ``'out'`` will be passed to the handler as the
*storage_dir* parameter.

You should also handle exceptions in your code gracefully by returning an
appropriate status value. In this case, if we failed to create the output
directory we return an ``0xC001`` status, indicating that the storage operation
has failed. However, as you've already seen, any unhandled exceptions in the
handler will automatically return an ``0xC211`` status, so you really only
need to deal with the exceptions important to you.

If you restart ``my_scp.py``, you should now be able to use
:doc:`storescu<../apps/storescu>` to send it any DICOM dataset supported by
the storage service.


Next steps
==========

That's it for the basics of *pynetdicom*. You might want to read through the
:doc:`User Guide</user/index>`, or check
out the :doc:`SCP examples</examples/index>` available in the documentation
or the :doc:`applications</examples/index>` that come with *pynetdicom*.
