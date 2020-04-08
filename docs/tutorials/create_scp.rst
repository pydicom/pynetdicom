======================
Writing your first SCP
======================

.. currentmodule:: pynetdicom

This is the second tutorial for people who are new to *pynetdicom*. If you
missed the :doc:`first one<create_scu>` then it's recommended that you check
it out before continuing.

In this tutorial you'll:

* Learn about DICOM Data Sets and the DICOM File Format
* Create a new Storage SCP application using *pynetdicom*
* Learn about the event-handler system and add handlers to your SCP
* Send datasets to your SCP using *pynetdicom's*
  :doc:`storescu<../apps/storescu>` application

If you need to install *pynetdicom* please follow the instructions in the
:doc:`installation guide<installation>`. For this tutorial we'll
also be using the :doc:`storescu<../apps/storescu>` application that comes with
*pynetdicom*.


The Data Set
============

This tutorial is about creating an SCP for the DICOM :dcm:`storage service
<part04/chapter_B.html>`, which is used to transfer DICOM
:dcm:`Data Sets<part05/chapter_7.html>` from one AE to another. A Data Set,
which from now on we'll just refer to as a *dataset*, is a collection of Data
Elements, or *elements*. When the combination of elements in the dataset
follows one of the definitions in Part 3 of the Standard then the dataset is
also referred to as an *Information Object* (and the definition is an
*Information Object Definition*, or IOD)

An element is simply a formalised description of some
value. Some examples are the *Transfer Syntax UID*, which contains the value of
the transfer syntax used to encode a dataset, *Pixel Data* which (usually)
contains image data, and *Patient's Name*, which - surprise! - contains a
patient's name. The DICOM Standard contains :dcm:`thousands of official
elements<part06/chapter_6.html>`, and if that's not enough you can also
create private ones.


Part 3 of the DICOM Standard contains a bunch of official dataset definitions,

Elements can be combined together any way you desire, the recipe for that
combination is termed an *Information Object Definition*, or IOD. The product
of following that recipe is a dataset (the information object). Part 3 of the
DICOM Standard contains many IODs, such as the CT Image IOD. By following

defines particular combinations of elements an *Information
Object Definition* or IOD.

,  to describe
(the "DICOM Information Object"). What that *thing* is depends on which
elements are in the dataset, and often what their values are. If that *thing*
was a *CT Image* dataset, it'd contain the elements required by
:dcm:`Annex A.3<part03/sect_A.3.3.html>` in Part 3 of the DICOM Standard. If
the *thing* is an *X-Ray Radiation Dose Structured Report*, it'd contain the
elements required by :dcm:`Annex A.35.8<part03/sect_A.35.8.3.html>`.


So, if a patient had a CT scan, the scan data is stored would be stored as
either a number of *CT Image* datasets or as one *Enhanced CT Image* dataset.

But datasets aren't just limited to storing patient data, they're also put to
use by the DICOM networking protocol:

* The DIMSE exchange mechanism uses datasets for its messages
* The queries used by the query/retrieve service are datasets
* And most importantly for this tutorial, the storage service provides a
  mechanism for transferring datasets from one AE to another

Fortunately there's a Python package for reading, modifying and creating
datasets; *pydicom*. If you're new to *pydicom* then you should read through
the `Dataset Basics
<https://pydicom.github.io/pydicom/stable/tutorials/dataset_basics.html>`_
tutorial.

Creating a Storage SCP
======================

Let's create a Storage SCP for receiving *CT Image* instances. Create a new
file ``create_scp.py``, open it in a text editor and add the following:

.. code-block:: python
   :linenos:

    from pydicom.uid import ExplicitVRLittleEndian

    from pynetdicom import AE, debug_logger
    from pynetdicom.sop_class import CTImageStorage

    debug_logger()

    ae = AE()
    ae.add_supported_context(CTImageStorage, ExplicitVRLittleEndian)
    ae.start_server(('', 11112))

Let's break this down

.. code-block:: python
   :linenos:

    from pydicom.uid import ExplicitVRLittleEndian

    from pynetdicom import AE, debug_logger
    from pynetdicom.sop_class import CTImageStorage

    debug_logger()

    ae = AE()
    ae.add_supported_context(CTImageStorage, ExplicitVRLittleEndian)

Just as with the Echo SCU from the previous tutorial, we import and create a
new :class:`AE<ae.ApplicationEntity>` instance. However, because we'll be the
association *acceptor*, its up to us to specify what
:doc:`presentation context<../user/presentation>` are *supported* rather than
*requested*. Since we'll be supporting the storage of *CT Images* encoded
using the *Explicit VR Little Endian* transfer syntax we use
:meth:`~ae.ApplicationEntity.add_supported_context` to add a presentation
context with abstract syntax *CT Image Storage*.

.. code-block:: python
   :linenos:
   :lineno-start: 8

    ae.start_server(('', 11112))

The call to :meth:`~ae.ApplicationEntity.start_server` starts our SCP listening
for association requests on port ``11112`` in *blocking* mode. We'll
demonstrate running the SCP in *non-blocking* mode a bit later.

Open a new terminal and run the file:

.. code-block:: text

    $ python create_scp.py

And in another terminal, run :doc:`storescu<../apps/storescu>` with
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

Oh dear, our store request has returned with a failure status ``0xC211``.
Something's gone horribly wrong. What does the output for the SCP look like?

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

As the log says, the failure was caused by not having a handler bound to
``evt.EVT_C_STORE``, so we better add one.

Events and handlers
===================

*pynetdicom* uses an event-handler system to give users access to data
exchanged between AEs and as a way to customise the responses to service
requests. Events come in two types: :ref:`notification events
<events_notification>`, where
where the user is notified some event has occurred, and
:ref:`intervention events<events_intervention>`,
where the user must intervene in some way. The idea is that you bind a
callable function, the *handler*, to an event, and then when the event occurs
the handler is called.

There are two areas where user intervention is required:

1. Responding to extended negotiation items during association negotiation. You
   probably won't need to worry about this unless you using :dcm:`User
   Identity negotiation<part07/sect_D.3.3.7.html>`.
2. Except for C-ECHO, responding to a DIMSE request when acting as an
   SCP, such as when an SCU sends a C-STORE request to a Storage SCP. Hey,
   that sounds familiar...

So we need to bind a handler to :func:`EVT_C_STORE<_handlers.doc_handle_store>`
to handle incoming storage requests.

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
    ae.start_server(('', 11112), evt_handlers=handlers)

We import ``evt``, which contains all the events, then add a function
``handle_store`` which will be our handler. All handlers must, at a minimum,
take a single parameter ``event``, which is an :class:`~events.Event` instance.
If you look at the :func:`documentation for EVT_C_STORE handlers
<_handlers.doc_handle_store>`, you'll see that they
must return *status* as either a :class:`~pydicom.dataset.Dataset` or
:class:`int`. This is the same (0000,0900) *Status* value you saw in the
previous tutorial, only seen from the other end. In our ``handle_store``
function we're returning an ``0x0000`` status, which indicates that the
storage operation was a success, but we're not actually storing anything at
this stage.

We bind our handler to the corresponding event by passing the ``handlers``
:class:`list` to :func:`~ae.ApplicationEntity.start_server` via the
`evt_handlers` keyword parameter.

Interrupt the terminal running ``create_scp.py`` using ``CTRL+C`` and
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

Our Storage SCP is returning sucess statuses for all incoming requests even
though we're not actually storing anything, so our next step is to actually
write the dataset to file. Before we do that we need to know a bit about the
DICOM File Format.

The DICOM File Format
---------------------

When a dataset is written to file it should be written in the :dcm:`DICOM File
Format<part10/chapter_7.html>`, which consists of four main parts:

1. A header containing an 128-byte preamble
2. A 4-byte ``DICM`` prefix (``0x4449434D`` in hex)
3. The *File Meta Information*, which is a small dataset containing meta
   information about the actual dataset
4. The dataset itself

The File Meta Information should contain at least the following elements:

+-------------+--------------------------------------+
| Tag         | Description                          |
+=============+======================================+
| (0002,0000) | *File Meta Information Group Length* |
+-------------+--------------------------------------+
| (0002,0001) | *File Meta Information Version*      |
+-------------+--------------------------------------+
| (0002,0002) | *Media Storage SOP Class UID*        |
+-------------+--------------------------------------+
| (0002,0003) | *Media Storage SOP Instance UID*     |
+-------------+--------------------------------------+
| (0002,0010) | *Transfer Syntax UID*                |
+-------------+--------------------------------------+
| (0002,0012) | *Implementation Class UID*           |
+-------------+--------------------------------------+

A dataset stored without the header, prefix and file meta information is
non-conformant to the DICOM Standard. It also becomes more difficult to
correctly determine the encoding of the dataset, which is important when
trying to read or transfer it. Fortunately, *pynetdicom* and *pydicom*
make it very easy to store datasets correctly. Change your handler code to:

.. code-block:: python

    def handle_store(event):
        """Handle EVT_C_STORE events."""
        ds = event.dataset
        ds.file_meta = event.file_meta
        ds.save_as(ds.SOPInstanceUID, write_like_original=False)

        return 0x0000

Where :attr:`event.dataset<events.Event.dataset>` is the decoded dataset
as a *pydicom* :class:`~pydicom.dataset.Dataset` and
:attr:`event.file_meta<events.Event.file_meta>` is a
:class:`~pydicom.dataset.Dataset` containing conformant File Meta Information
elements. We set the dataset's :attr:`~pydicom.dataset.FileDataset.file_meta`
attribute and then save it to a file
named after its (0008,0018) *SOP Instance UID*,  which is an identifier unique
to each dataset that *should* be present. We pass
``write_like_original = False`` to :meth:`~pydicom.dataset.Dataset.save_as` to
ensure that the file is written in the DICOM File Format.

There are a couple of things to be aware of when dealing with
:class:`Datasets<pydicom.dataset.Dataset>`:

* Because *pydicom* uses a deferred-read system, the
  :class:`Dataset<pydicom.dataset.Dataset>` returned by
  :attr:`event.dataset<events.Event.dataset>` may raise an exception when any
  element is first accessed.
* The dataset may not contain a particular element, even it it's supposed to.
  Always assume a dataset is non-conformant, check to see if what you need
  is present and handle missing elements appropriately. The
  easiest way to check if an element is in a dataset is with the
  :func:`in<operator.__contains__>` operator: ``'PatientName' in ds``

If you restart ``create_scp.py`` and re-send the dataset using
:doc:`storescu<../apps/storescu>` you  should see that a file named
``1.3.6.1.4.1.5962.1.1.1.1.1.20040119072730.12322`` has been written to the
directory containing ``create_scp.py``.


Optimising and passing extra arguments
--------------------------------------

If you don't actually need a decoded :class:`~pydicom.dataset.Dataset`, then
it's faster to write the encoded data directly to file; this skips
having to decode and then re-encode the dataset.

.. code-block:: python
   :linenos:

    import os

    from pydicom.filewriter import write_file_meta_info
    from pydicom.uid import ExplicitVRLittleEndian

    from pynetdicom import AE, debug_logger, evt
    from pynetdicom.sop_class import CTImageStorage

    debug_logger()

    def handle_store(event, storage_dir):
        """Handle EVT_C_STORE events."""
        os.makedirs(storage_dir, exist_ok=True)

        fname = os.path.join(storage_dir, event.request.AffectedSOPInstanceUID)
        with open(fname, 'wb') as fp:
            # Write the preamble, prefix and file meta information elements
            fp.write(b'\x00' * 128)
            fp.write(b'DICM')
            write_file_meta_info(fp, event.file_meta)
            # Write the transferred dataset
            fp.write(event.request.DataSet.getvalue())

        return 0x0000

    handlers = [(evt.EVT_C_STORE, handle_store, ['out'])]

    ae = AE()
    ae.add_supported_context(CTImageStorage, ExplicitVRLittleEndian)
    ae.start_server(('', 11112), evt_handlers=handlers)

We've modified the handler to write the preamble and prefix to file,
encode and write the file meta information elements using *pydicom's*
:func:`~pydicom.filewriter.write_file_meta_info` function, then finally write
the encoded dataset.

The second change we've made is to demonstrate how extra parameters can be
passed to the handler by binding using a 3-tuple rather than a 2-tuple. The
third value in the :class:`tuple` should be a :class:`list` of objects, and
each item in the ``list`` will be passed as a separate parameter. In
our case the string ``'out'`` will be passed to the handler as the
*storage_dir* parameter.
