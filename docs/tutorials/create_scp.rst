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
* Learn about the event-handler system used by *pynetdicom* and add handlers
  to your SCP
* Send datasets to your SCP using *pynetdicom's* ``storescu`` application

If you need to install *pynetdicom* please follow the instructions in the
:doc:`installation guide<installation>`. For this tutorial we'll
also be using the :doc:`storescu<../apps/storescu>` application that comes with
*pynetdicom*.


The Data Set
============

A DICOM :dcm:`Data Set<part05/chapter_7.html>`, which from now on we'll just
refer to as a *dataset*, is a collection of Data Elements. Each Data Element, or
*element* for short, is just a description of some value. Examples
of elements are the *Transfer Syntax UID* element, which contains the value of
the transfer syntax used to encode the dataset, *Pixel Data* which (usually)
contains image data, and *Patient's Name*, which - surprise! - contains a
patient's name. The DICOM Standard contains :dcm:`hundreds of official
elements<part06/chapter_6.html>`, and if they're not enough you can also
create your own private ones.

When *elements* are combined together they can be used to describe a *thing*
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

The DICOM File Format
---------------------

FIXME: This should be later on, I think.

When a dataset is written to file it should be written in the DICOM File
Format, which consists of four main parts:

1. A header containing an 128-byte preamble
2. A 4-byte ``DICM`` prefix (``0x4449434D`` in hex)
3. The *File Meta Information* which is a small dataset containing meta
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

A dataset stored without the File Meta Information is non-conformant to the
DICOM Standard. It also becomes more difficult to correctly determine
the encoding of the dataset, which is important when trying to read or transfer
it. Fortunately, *pynetdicom* makes it very easy to store datasets correctly.


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
using the *Implicit VR Little Endian* transfer syntax we use
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

And in another terminal, run ``storescu`` with :gh:`this dataset
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
