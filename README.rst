.. class:: center
.. image:: https://codecov.io/gh/pydicom/pynetdicom3/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/pydicom/pynetdicom3
.. image:: https://travis-ci.org/pydicom/pynetdicom3.svg?branch=master
    :target: https://travis-ci.org/pydicom/pynetdicom3
.. image:: https://circleci.com/gh/pydicom/pynetdicom3/tree/master.svg?style=svg
    :target: https://circleci.com/gh/pydicom/pynetdicom3/tree/master


pynetdicom3
===========

A Python 2.7/3+ implementation of the `DICOM <http://dicom.nema.org>`_
networking protocol, originally based on
`pynetdicom <https://github.com/patmun/pynetdicom_legacy>`_.


Description
-----------

`DICOM <http://dicom.nema.org>`_ is the international standard for medical
images and related information. It defines the formats and communication
protocols for media exchange in radiology, cardiology, radiotherapy and other
medical domains.

*pynetdicom3* is a pure Python (2.7/3+) program that implements the DICOM
networking protocol. Working with `pydicom <https://github.com/pydicom/pydicom>`_,
it allows the easy creation of DICOM *Service Class Users* (SCUs) and
*Service Class Providers* (SCPs).

The main user class is ``AE``, which is used to represent a DICOM Application
Entity. Once the ``AE`` has been created then you would typically either:

- Start the application as an SCP using ``AE.start()`` and wait for incoming
  association requests
- Use the application as an SCU by requesting an association with a peer SCP
  via the ``AE.associate(addr, port)`` method, which returns an ``Association``
  thread.

Once the application is associated with a peer, DICOM data can be sent between
them by utilising the DIMSE-C services (see DICOM Standard PS3.7,
Sections 7.5, 9 and 10).


Supported Service Classes
~~~~~~~~~~~~~~~~~~~~~~~~~

- `Verification Service Class <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_A>`_
- `Storage Service Class <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_B>`_
- `Query/Retrieve Service Class <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_C>`_
- `Basic Worklist Management Service Class <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_K>`_


Supported DIMSE SCU Services
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When the AE is acting as an SCU and an association has been established with a
peer SCP, the following DIMSE-C services are available (provided the peer
supports the corresponding Service Classes):

- C-ECHO: ``Association.send_c_echo()`` used to verify end-to-end
  communications with the peer.
- C-STORE: ``Association.send_c_store(dataset)`` requests the storage of the
  Composite SOP Instance *dataset* by the peer.
- C-FIND: ``Association.send_c_find(dataset)`` requests the peer search its set
  of managed SOP Instances for those that match the attributes given in
  *dataset*.
- C-GET: ``Association.send_c_get(dataset)`` requests the peer search its set
  of managed SOP Instances for those that match the attributes given in
  *dataset* then return those matching Instances to the SCU.
- C-MOVE: ``Association.send_c_move(dataset, move_aet)`` requests the peer
  search its set of managed SOP Instances for those that match the attributes
  given in *dataset* and then copy those matching Instances to the AE with title
  *move_aet* over a new association.

Where *dataset* is a pydicom `Dataset <https://pydicom.github.io/pydicom/stable/ref_guide.html#dataset>`_
object. See the `SCU Examples <docs/scu_examples.rst>`_ for more information.


Supported DIMSE SCP Services
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When the AE is acting as an SCP the following DIMSE-C services are available to
the peer once an association has been established. With the exception of
``on_c_echo()``, the user is expected to handle the required operations by
implementing the following ``AE`` callbacks:

- C-ECHO: ``AE.on_c_echo(context, info)``
- C-STORE: ``AE.on_c_store(dataset, context, info)``
- C-FIND: ``AE.on_c_find(dataset, context, info)`` and
  ``AE.on_c_find_cancel()``
- C-GET: ``AE.on_c_get(dataset, context, info)`` and
  ``AE.on_c_get_cancel()``
- C-MOVE: ``AE.on_c_move(dataset, move_aet, context, info)`` and
  ``AE.on_c_move_cancel()``

Where *dataset* is a pydicom `Dataset <https://pydicom.github.io/pydicom/stable/ref_guide.html#dataset>`_
object, *context* is a ``namedtuple`` with details of the Presentation Context
used to transfer *dataset*, *info* is a ``dict`` containing information about
the association and the message request (such as the peer's IP address and AE
title and the message priority) and *move_aet* is the Move Destination AE
title.


Documentation
-------------
Documentation is available for the current `development version
<https://pydicom.github.io/pynetdicom3/dev>`_.


Installation
-----------
Dependencies
~~~~~~~~~~~~
`pydicom <https://github.com/pydicom/pydicom>`_

Installing from github
~~~~~~~~~~~~~~~~~~~~~~
.. code-block:: sh

        $ git clone https://github.com/pydicom/pynetdicom3.git
        $ cd pynetdicom3
        $ python setup.py install

Examples
--------
- Send a DICOM C-ECHO to a peer Verification SCP (at TCP/IP address *addr*,
  listen port number *port*):

.. code-block:: python

        from pynetdicom3 import AE

        ae = AE(ae_title=b'MY_ECHO_SCU')
        # Verification SOP Class has a UID of 1.2.840.10008.1.1
        #   we can use the UID string directly when requesting the presentation
        #   contexts we want to use in the association
        ae.add_requested_context('1.2.840.10008.1.1')

        # Associate with a peer DICOM AE
        assoc = ae.associate(addr, port)

        if assoc.is_established:
            # Send a DIMSE C-ECHO request to the peer
            # `status` is a pydicom Dataset object with (at a minimum) a
            #   (0000,0900) Status element
            # If the peer hasn't accepted the requested context then this
            #   will raise a RuntimeError exception
            status = assoc.send_c_echo()

            # Output the response from the peer
            if status:
                print('C-ECHO Response: 0x{0:04x}'.format(status.Status))

            # Release the association
            assoc.release()

- Create a DICOM C-ECHO listen SCP on port 11112 (you may optionally implement
  the `AE.on_c_echo callback` if you want to return something other than a
  *Success* status):

.. code-block:: python

        from pynetdicom3 import AE, VerificationPresentationContexts

        ae = AE(ae_title=b'MY_ECHO_SCP', port=11112)
        # Or we can use the inbuilt VerificationPresentationContexts list,
        #   there's one for each of the supported Service Classes
        # In this case, we are supporting any requests to use Verification SOP
        #   Class in the association
        ae.supported_contexts = VerificationPresentationContexts

        # Start the SCP
        ae.start()

- Send the DICOM 'CT Image Storage' dataset in *file-in.dcm* to a peer Storage
  SCP (at TCP/IP address *addr*, listen port number *port*):

.. code-block:: python

        from pydicom import dcmread
        from pydicom.uid import ImplicitVRLittleEndian

        from pynetdicom3 import AE, VerificationPresentationContexts
        from pynetdicom3.sop_class import CTImageStorage, MRImageStorage

        ae = AE(ae_title=b'MY_STORAGE_SCU')
        # We can also do the same thing with the requested contexts
        ae.requested_contexts = VerificationPresentationContexts
        # Or we can use inbuilt objects like CTImageStorage.
        # The requested presentation context's transfer syntaxes can also
        #   be specified using with a str/UID or list of str/UIDs
        ae.add_requested_context(CTImageStorage,
                                 transfer_syntax=ImplicitVRLittleEndian)
        # Adding a presentation context with multiple transfer syntaxes
        #   this isn't actually required to transfer the CT dataset
        ae.add_requested_context(MRImageStorage,
                                 transfer_syntax=[ImplicitVRLittleEndian,
                                                  '1.2.840.10008.1.2.1'])

        assoc = ae.associate(addr, port)
        if assoc.is_established:
            dataset = dcmread('file-in.dcm')
            # `status` is the response from the peer to the store request
            # but may be an empty pydicom Dataset if the peer timed out or
            # sent an invalid dataset.
            status = assoc.send_c_store(dataset)

            assoc.release()
