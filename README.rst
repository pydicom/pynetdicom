.. class:: center
.. image:: https://codecov.io/gh/pydicom/pynetdicom/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/pydicom/pynetdicom
.. image:: https://travis-ci.org/pydicom/pynetdicom.svg?branch=master
    :target: https://travis-ci.org/pydicom/pynetdicom
.. image:: https://circleci.com/gh/pydicom/pynetdicom/tree/master.svg?style=shield
    :target: https://circleci.com/gh/pydicom/pynetdicom/tree/master
.. image:: https://badge.fury.io/py/pynetdicom.svg
    :target: https://badge.fury.io/py/pynetdicom
.. image:: https://img.shields.io/pypi/pyversions/pynetdicom.svg
    :target: https://img.shields.io/pypi/pyversions/pynetdicom.svg
.. image:: https://zenodo.org/badge/DOI/10.5281/zenodo.3345559.svg
   :target: https://doi.org/10.5281/zenodo.3345559
.. image:: https://badges.gitter.im/pydicom.png
    :target: https://gitter.im/pydicom/Lobby


pynetdicom
==========

A Python implementation of the `DICOM <http://dicom.nema.org>`_
networking protocol, originally based on (legacy)
`pynetdicom <https://github.com/patmun/pynetdicom_legacy>`_.


Description
-----------

`DICOM <http://dicom.nema.org>`_ is the international standard for medical
images and related information. It defines the formats and communication
protocols for media exchange in radiology, cardiology, radiotherapy and other
medical domains.

*pynetdicom* is a pure Python (2.7/3.5+) package that implements the DICOM
networking protocol. Working with `pydicom <https://github.com/pydicom/pydicom>`_,
it allows the easy creation of DICOM *Service Class Users* (SCUs) and
*Service Class Providers* (SCPs).

The main user class is ``AE``, which is used to represent a DICOM Application
Entity. Once an ``AE`` has been created you would typically either:

- Start the application as an SCP by specifying the presentation contexts that
  you will support, then calling ``AE.start_server((host, port))`` and waiting
  for incoming association requests
- Use the application as an SCU by specifying the presentation contexts you
  want the peer SCP to support, then requesting an association
  via the ``AE.associate(host, port)`` method, which returns an ``Association``
  thread.

Once the application is associated with a peer AE, DICOM data can be sent between
them by utilising the DIMSE-C and -N services (see the DICOM Standard Part 7,
Sections `7.5 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_7.5>`_,
`9 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_9>`_,
and `10 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_10>`_).


Supported Service Classes
~~~~~~~~~~~~~~~~~~~~~~~~~
*pynetdicom* supports the following DICOM service classes:

- `Application Event Logging Service Class <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_P>`_
- `Basic Worklist Management Service Class <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_K>`_
- `Color Palette Query/Retrieve Service Class <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_X>`_
- `Defined Procedure Protocol Query/Retrieve Service Class <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_HH>`_
- `Display System Management Service Class <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_EE>`_
- `Hanging Protocol Query/Retrieve Service Class <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_U>`_
- `Implant Template Query/Retrieve Service Class <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_BB>`_
- `Instance Availability Notification Service Class <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_R>`_
- `Media Creation Management Service Class <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_S>`_
- `Modality Performed Procedure Step Management <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_F>`_
- `Non-Patient Object Storage Service Class <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_GG>`_
- `Print Management Service Class <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_H>`_
- `Protocol Approval Query/Retrieve Service Class <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_II>`_
- `Query/Retrieve Service Class <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_C>`_

  - `Composite Instance Retrieve Without Bulk Data <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_Z>`_
  - `Instance and Frame Level Retrieve <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_Y>`_
- `Relevant Patient Information Query Service Class <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_Q>`_
- `RT Machine Verification Service Class <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_DD>`_
- `Storage Service Class <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_B>`_

  - `Ophthalmic Refractive Measurements Storage <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_AA>`_
  - `Softcopy Presentation State Storage <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_N>`_
  - `Structured Reporting Storage <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_O>`_
  - `Volumetric Presentation State Storage <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_FF>`_
- `Storage Commitment Service Class <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_J>`_
- `Substance Administration Query Service Class <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_V>`_
- `Unified Procedure Step Service Class <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_CC>`_
- `Verification Service Class <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_A>`_


Supported DIMSE SCU Services
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When the AE is acting as an SCU and an association has been established with a
peer SCP, the following DIMSE-C and -N services are available (provided the
peer supports the Service Class and a corresponding Presentation Context has
been accepted):

.. _send_c_echo: https:pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom.association.Association.html#pynetdicom.association.Association.send_c_echo
.. _send_c_find: https:pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom.association.Association.html#pynetdicom.association.Association.send_c_find
.. _send_c_get: https:pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom.association.Association.html#pynetdicom.association.Association.send_c_get
.. _send_c_move: https:pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom.association.Association.html#pynetdicom.association.Association.send_c_move
.. _send_c_store: https:pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom.association.Association.html#pynetdicom.association.Association.send_c_store
.. _send_n_action: https:pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom.association.Association.html#pynetdicom.association.Association.send_n_action
.. _send_n_create: https:pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom.association.Association.html#pynetdicom.association.Association.send_n_create
.. _send_n_delete: https:pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom.association.Association.html#pynetdicom.association.Association.send_n_delete
.. _send_n_event_report: https:pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom.association.Association.html#pynetdicom.association.Association.send_n_event_report
.. _send_n_get: https:pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom.association.Association.html#pynetdicom.association.Association.send_n_get
.. _send_n_set: https:pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom.association.Association.html#pynetdicom.association.Association.send_n_set

+----------------+----------------------------------------------------------+
| DIMSE service  | ``Association`` method                                   |
+================+==========================================================+
| C-ECHO         | ``send_c_echo()``                                        |
|                |                                                          |
+----------------+----------------------------------------------------------+
| C-FIND         | ``send_c_find(dataset, query_model)``                    |
|                |                                                          |
+----------------+----------------------------------------------------------+
| C-GET          | ``send_c_get(dataset, query_model)``                     |
|                |                                                          |
+----------------+----------------------------------------------------------+
| C-MOVE         | ``send_c_move(dataset, move_aet, query_model)``          |
|                |                                                          |
+----------------+----------------------------------------------------------+
| C-STORE        | ``send_c_store(dataset)``                                |
|                |                                                          |
+----------------+----------------------------------------------------------+
| N-ACTION       | ``send_n_action(dataset, action_type, class_uid,         |
|                | instance_uid)``                                          |
+----------------+----------------------------------------------------------+
| N-CREATE       | ``send_n_create(dataset, class_uid, instance_uid)``      |
|                |                                                          |
+----------------+----------------------------------------------------------+
| N-DELETE       | ``send_n_delete(class_uid, instance_uid)``               |
|                |                                                          |
+----------------+----------------------------------------------------------+
| N-EVENT-REPORT | ``send_n_event_report(dataset, event_type,               |
|                | class_uid, instance_uid)``                               |
+----------------+----------------------------------------------------------+
| N-GET          | ``send_n_get(identifier_list, class_uid, instance_uid)`` |
|                |                                                          |
+----------------+----------------------------------------------------------+
| N-SET          | ``send_n_set(dataset, class_uid, instance_uid)``         |
|                |                                                          |
+----------------+----------------------------------------------------------+

Where *dataset* is a pydicom
`Dataset <https://pydicom.github.io/pydicom/stable/ref_guide.html#dataset>`_
object, *query_model* is a UID string, *identifier_list* is a list of pydicom
`Tag <https://pydicom.github.io/pydicom/stable/api_ref.html#pydicom.tag.Tag>`_
objects, *event_type* and *action_type* are ints and *class_uid* and
*instance_uid* are UID strings. See the
`Association documentation <https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom.association.Association.html>`_
for more information.


Supported DIMSE SCP Services
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When the AE is acting as an SCP the following DIMSE-C and -N services are
available to the peer once an association has been established:

.. _handle_echo: https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom._handlers.doc_handle_echo.html
.. _handle_find: https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom._handlers.doc_handle_find.html
.. _handle_c_get: https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom._handlers.doc_handle_c_get.html
.. _handle_move: https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom._handlers.doc_handle_move.html
.. _handle_store: https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom._handlers.doc_handle_store.html
.. _handle_action: https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom._handlers.doc_handle_action.html
.. _handle_create: https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom._handlers.doc_handle_create.html
.. _handle_delete: https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom._handlers.doc_handle_delete.html
.. _handle_event_report: https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom._handlers.doc_handle_event_report.html
.. _handle_n_get: https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom._handlers.doc_handle_n_get.html
.. _handle_set: https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom._handlers.doc_handle_set.html

+----------------+----------------------------+
| DIMSE service  | Intervention Event         |
+================+============================+
| C-ECHO         | ``evt.EVT_C_ECHO``         |
+----------------+----------------------------+
| C-FIND         | ``evt.EVT_C_FIND``         |
+----------------+----------------------------+
| C-GET          | ``evt.EVT_C_GET``          |
+----------------+----------------------------+
| C-MOVE         | ``evt.EVT_C_MOVE``         |
+----------------+----------------------------+
| C-STORE        | ``evt.EVT_C_STORE``        |
+----------------+----------------------------+
| N-ACTION       | ``evt.EVT_N_ACTION``       |
+----------------+----------------------------+
| N-CREATE       | ``evt.EVT_N_CREATE``       |
+----------------+----------------------------+
| N-DELETE       | ``evt.EVT_N_DELETE``       |
+----------------+----------------------------+
| N-EVENT-REPORT | ``evt.EVT_N_EVENT_REPORT`` |
+----------------+----------------------------+
| N-GET          | ``evt.EVT_N_GET``          |
+----------------+----------------------------+
| N-SET          | ``evt.EVT_N_SET``          |
+----------------+----------------------------+


With the exception of the C-ECHO service, a user-defined callable function,
*handler*, must be bound to the corresponding
`intervention event <https://pydicom.github.io/pynetdicom/stable/user/events#intervention-events>`_
in order to complete a DIMSE service request. Events
can be imported with ``from pynetdicom import evt`` and a handler can be
bound to an event prior to starting an association through the *evt_handlers*
keyword arguments in ``AE.start_server()`` and ``AE.associate()``.

When an event occurs the *handler* function is called and passed a single
parameter, *event*, which is an ``evt.Event`` object whose specific attributes
are dependent on the type of event that occurred. Handlers bound to
intervention events must  return or yield certain values. See the
`handler documentation <https://pydicom.github.io/pynetdicom/stable/reference/events>`_
for information on what attributes and properties are available in ``Event``
for each event type and the expected returns/yields for the
corresponding handlers.


Documentation
-------------
The *pynetdicom*
`user guide <https://pydicom.github.io/pynetdicom/stable/#user-guide>`_,
`code examples <https://pydicom.github.io/pynetdicom/stable/#examples>`_ and
`API reference <https://pydicom.github.io/pynetdicom/stable/reference/index.html>`_
documentation is available for the
`current release <https://pydicom.github.io/pynetdicom/>`_ as well as the
`development version <https://pydicom.github.io/pynetdicom/dev>`_.


Installation
------------
Dependencies
~~~~~~~~~~~~
`pydicom <https://github.com/pydicom/pydicom>`_

Installing current release
~~~~~~~~~~~~~~~~~~~~~~~~~~
.. code-block:: sh

        $ pip install pynetdicom

Installing development version
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. code-block:: sh

        $ pip install git+git://github.com/pydicom/pynetdicom.git

Examples
--------
Send a DICOM C-ECHO to a peer Verification SCP (at TCP/IP address *addr*,
listen port number *port*):

.. code-block:: python

        from pynetdicom import AE

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

Create a blocking DICOM C-ECHO listen SCP on port 11112 (you may optionally
bind a handler to the ``evt.EVT_C_ECHO`` event if you want to return something
other than a *Success* status):

.. code-block:: python

        from pynetdicom import AE, VerificationPresentationContexts

        ae = AE(ae_title=b'MY_ECHO_SCP')
        # Or we can use the inbuilt VerificationPresentationContexts list,
        #   there's one for each of the supported Service Classes
        # In this case, we are supporting any requests to use Verification SOP
        #   Class in the association
        ae.supported_contexts = VerificationPresentationContexts

        # Start the SCP on (host, port) in blocking mode
        ae.start_server(('', 11112), block=True)

Alternatively, you can start the SCP in non-blocking mode, which returns the
running server instance. This can be useful when you want to run a Storage SCP
and make C-MOVE requests within the same AE. In the next example we'll create a
non-blocking Verification SCP and bind a handler for the C-ECHO service
request event ``evt.EVT_C_ECHO`` that logs the requestor's address and port
number and the timestamp for the event.

.. code-block:: python

        import logging

        from pynetdicom import AE, evt, VerificationPresentationContexts, debug_logger

        # Setup logging to use the StreamHandler at the debug level
        debug_logger()
        LOGGER = logging.getLogger('pynetdicom')

        ae = AE(ae_title=b'MY_ECHO_SCP')
        ae.supported_contexts = VerificationPresentationContexts

        # Implement the EVT_C_ECHO handler
        def handle_echo(event):
            """Handle a C-ECHO service request.

            Parameters
            ----------
            event : evt.Event
                The C-ECHO service request event.

            Returns
            -------
            int or pydicom.dataset.Dataset
                The status returned to the peer AE in the C-ECHO response.
                Must be a valid C-ECHO status value as either an ``int`` or a
                ``Dataset`` object containing an (0000,0900) *Status* element.
            """
            # Every *Event* includes `assoc` and `timestamp` attributes
            #   which are the *Association* instance the event occurred in
            #   and the *datetime.datetime* the event occurred at
            requestor = event.assoc.requestor
            timestamp = event.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            msg = (
                "Received C-ECHO service request from ({}, {}) at {}"
                .format(requestor.address, requestor.port, timestamp)
            )
            LOGGER.info(msg)

            # Return a *Success* status
            return 0x0000

        handlers = [(evt.EVT_C_ECHO, handle_echo)]

        # Start the SCP in non-blocking mode
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        # Send a C-ECHO request to our own Verification SCP
        ae.add_requested_context('1.2.840.10008.1.1')
        assoc = ae.associate('localhost', 11112)
        if assoc.is_established:
            status = assoc.send_c_echo()
            assoc.release()

        # Shutdown the SCP
        scp.shutdown()


Send the DICOM *CT Image Storage* dataset in *file-in.dcm* to a peer Storage
SCP (at TCP/IP address *addr*, listen port number *port*):

.. code-block:: python

        from pydicom import dcmread
        from pydicom.uid import ImplicitVRLittleEndian

        from pynetdicom import AE, VerificationPresentationContexts
        from pynetdicom.sop_class import CTImageStorage, MRImageStorage

        ae = AE(ae_title=b'MY_STORAGE_SCU')
        # We can also do the same thing with the requested contexts
        ae.requested_contexts = VerificationPresentationContexts
        # Or we can use inbuilt objects like CTImageStorage.
        # The requested presentation context's transfer syntaxes can also
        #   be specified using a str/UID or list of str/UIDs
        ae.add_requested_context(CTImageStorage,
                                 transfer_syntax=ImplicitVRLittleEndian)
        # Adding a presentation context with multiple transfer syntaxes
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
