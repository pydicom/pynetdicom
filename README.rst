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
.. image:: https://img.shields.io/conda/vn/conda-forge/pynetdicom.svg
   :target: https://anaconda.org/conda-forge/pynetdicom
.. image:: https://zenodo.org/badge/DOI/10.5281/zenodo.3995765.svg
   :target: https://doi.org/10.5281/zenodo.3995765
.. image:: https://badges.gitter.im/pydicom/Lobby.svg
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
networking protocol. Working with
`pydicom <https://github.com/pydicom/pydicom>`_, it allows the easy creation
of DICOM *Service Class Users* (SCUs) and *Service Class Providers* (SCPs).

*pynetdicom's* main user class is
`AE <https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom.ae.ApplicationEntity.html>`_,
which is used to represent a DICOM Application Entity. Once an ``AE`` has been
created you can:

- Start the application as an SCP by specifying the supported presentation
  contexts then calling
  `AE.start_server() <https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom.ae.ApplicationEntity.html#pynetdicom.ae.ApplicationEntity.start_server>`_
  and waiting for incoming association requests
- Use the application as an SCU by specifying the presentation contexts you
  want the peer SCP to support, then requesting an association
  via the
  `AE.associate() <https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom.ae.ApplicationEntity.html#pynetdicom.ae.ApplicationEntity.associate>`_
  method, which returns an
  `Association <https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom.association.Association.html#pynetdicom.association.Association>`_
  thread.

Once associated, the services available to the association can
be used by sending
`DIMSE-C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_9>`_
and
`DIMSE-N <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_10>`_
messages.

Documentation
-------------
The *pynetdicom*
`tutorials <https://pydicom.github.io/pynetdicom/stable/tutorials/index.html>`_,
`user guide <https://pydicom.github.io/pynetdicom/stable/user/index.html>`_,
`code examples <https://pydicom.github.io/pynetdicom/stable/examples/index.html>`_,
`application <https://pydicom.github.io/pynetdicom/stable/apps/index.html>`_ and
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
Using pip:

.. code-block:: sh

    $ pip install pynetdicom

Using conda:

.. code-block:: sh

    $ conda install -c conda-forge pynetdicom


Installing development version
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
.. code-block:: sh

    $ pip install git+git://github.com/pydicom/pynetdicom.git


Supported DIMSE Services
------------------------
SCU Services
~~~~~~~~~~~~

When the AE is acting as an SCU and an association has been established with a
peer SCP, the following DIMSE-C and -N services are available:

.. _assoc: https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom.association.Association.html
.. _echo: https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom.association.Association.html#pynetdicom.association.Association.send_c_echo
.. _find: https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom.association.Association.html#pynetdicom.association.Association.send_c_find
.. _c_get: https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom.association.Association.html#pynetdicom.association.Association.send_c_get
.. _move: https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom.association.Association.html#pynetdicom.association.Association.send_c_move
.. _store: https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom.association.Association.html#pynetdicom.association.Association.send_c_store
.. _action: https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom.association.Association.html#pynetdicom.association.Association.send_n_action
.. _create: https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom.association.Association.html#pynetdicom.association.Association.send_n_create
.. _delete: https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom.association.Association.html#pynetdicom.association.Association.send_n_delete
.. _er: https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom.association.Association.html#pynetdicom.association.Association.send_n_event_report
.. _n_get: https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom.association.Association.html#pynetdicom.association.Association.send_n_get
.. _set: https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom.association.Association.html#pynetdicom.association.Association.send_n_set


+----------------+----------------------------------------------------------------------------------------+
| DIMSE service  | `Association <assoc_>`_ method                                                         |
+================+========================================================================================+
| C-ECHO         | `Association.send_c_echo() <echo_>`_                                                   |
+----------------+----------------------------------------------------------------------------------------+
| C-FIND         | `Association.send_c_find(dataset, query_model) <find_>`_                               |
+----------------+----------------------------------------------------------------------------------------+
| C-GET          | `Association.send_c_get(dataset, query_model) <c_get_>`_                               |
+----------------+----------------------------------------------------------------------------------------+
| C-MOVE         | `Association.send_c_move(dataset, move_aet, query_model) <move_>`_                     |
+----------------+----------------------------------------------------------------------------------------+
| C-STORE        | `Association.send_c_store(dataset) <store_>`_                                          |
+----------------+----------------------------------------------------------------------------------------+
| N-ACTION       | `Association.send_n_action(dataset, action_type, class_uid, instance_uid) <action_>`_  |
+----------------+----------------------------------------------------------------------------------------+
| N-CREATE       | `Association.send_n_create(dataset, class_uid, instance_uid) <create_>`_               |
+----------------+----------------------------------------------------------------------------------------+
| N-DELETE       | `Association.send_n_delete(class_uid, instance_uid) <delete_>`_                        |
+----------------+----------------------------------------------------------------------------------------+
| N-EVENT-REPORT | `Association.send_n_event_report(dataset, event_type, class_uid, instance_uid) <er_>`_ |
+----------------+----------------------------------------------------------------------------------------+
| N-GET          | `Association.send_n_get(identifier_list, class_uid, instance_uid) <n_get_>`_           |
+----------------+----------------------------------------------------------------------------------------+
| N-SET          | `Association.send_n_set(dataset, class_uid, instance_uid) <set_>`_                     |
+----------------+----------------------------------------------------------------------------------------+

Where *dataset* is a pydicom
`Dataset <https://pydicom.github.io/pydicom/stable/ref_guide.html#dataset>`_
object, *query_model* is a UID string, *identifier_list* is a list of pydicom
`Tag <https://pydicom.github.io/pydicom/stable/api_ref.html#pydicom.tag.Tag>`_
objects, *event_type* and *action_type* are ints and *class_uid* and
*instance_uid* are UID strings. See the
`Association documentation <https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom.association.Association.html>`_
for more information.


SCP Services
~~~~~~~~~~~~

When the AE is acting as an SCP the following DIMSE-C and -N services are
available to the peer once an association has been established:

.. _hecho: https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom._handlers.doc_handle_echo.html
.. _hfind: https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom._handlers.doc_handle_find.html
.. _hc_get: https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom._handlers.doc_handle_c_get.html
.. _hmove: https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom._handlers.doc_handle_move.html
.. _hstore: https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom._handlers.doc_handle_store.html
.. _haction: https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom._handlers.doc_handle_action.html
.. _hcreate: https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom._handlers.doc_handle_create.html
.. _hdelete: https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom._handlers.doc_handle_delete.html
.. _her: https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom._handlers.doc_handle_event_report.html
.. _hn_get: https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom._handlers.doc_handle_n_get.html
.. _hset: https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom._handlers.doc_handle_set.html

+----------------+----------------------------+---------------------------------+
| DIMSE service  | Intervention Event         | Handler documentation           |
+================+============================+=================================+
| C-ECHO         | ``evt.EVT_C_ECHO``         | `Handle C-ECHO <hecho_>`_       |
+----------------+----------------------------+---------------------------------+
| C-FIND         | ``evt.EVT_C_FIND``         | `Handle C-FIND <hfind_>`_       |
+----------------+----------------------------+---------------------------------+
| C-GET          | ``evt.EVT_C_GET``          | `Handle C-GET <hc_get_>`_       |
+----------------+----------------------------+---------------------------------+
| C-MOVE         | ``evt.EVT_C_MOVE``         | `Handle C-MOVE <hmove_>`_       |
+----------------+----------------------------+---------------------------------+
| C-STORE        | ``evt.EVT_C_STORE``        | `Handle C-STORE <hstore_>`_     |
+----------------+----------------------------+---------------------------------+
| N-ACTION       | ``evt.EVT_N_ACTION``       | `Handle N-ACTION <haction_>`_   |
+----------------+----------------------------+---------------------------------+
| N-CREATE       | ``evt.EVT_N_CREATE``       | `Handle N-CREATE <hcreate_>`_   |
+----------------+----------------------------+---------------------------------+
| N-DELETE       | ``evt.EVT_N_DELETE``       | `Handle N-DELETE <hdelete_>`_   |
+----------------+----------------------------+---------------------------------+
| N-EVENT-REPORT | ``evt.EVT_N_EVENT_REPORT`` | `Handle N-EVENT-REPORT <her_>`_ |
+----------------+----------------------------+---------------------------------+
| N-GET          | ``evt.EVT_N_GET``          | `Handle N-GET <hn_get_>`_       |
+----------------+----------------------------+---------------------------------+
| N-SET          | ``evt.EVT_N_SET``          | `Handle N-SET <hset_>`_         |
+----------------+----------------------------+---------------------------------+


With the exception of the C-ECHO service, a user-defined callable function,
*handler*, must be bound to the corresponding
`intervention event <https://pydicom.github.io/pynetdicom/stable/user/events#intervention-events>`_
in order to complete a DIMSE service request. Events
can be imported with ``from pynetdicom import evt`` and a handler can be
bound to an event prior to starting an association through the *evt_handlers*
keyword arguments in
`AE.start_server() <https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom.ae.ApplicationEntity.html#pynetdicom.ae.ApplicationEntity.start_server>`_
and
`AE.associate() <https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom.ae.ApplicationEntity.html#pynetdicom.ae.ApplicationEntity.associate>`_.

When an event occurs the *handler* function is called and passed a single
parameter, *event*, which is an
`Event <https://pydicom.github.io/pynetdicom/stable/reference/generated/pynetdicom.events.Event.html>`_
object whose specific attributes
are dependent on the type of event that occurred. Handlers bound to
intervention events must  return or yield certain values. See the
`handler documentation <https://pydicom.github.io/pynetdicom/stable/reference/events>`_
for information on what attributes and properties are available in ``Event``
for each event type and the expected returns/yields for the
corresponding handlers.

Applications
------------

Some basic DICOM applications are included with *pynetdicom*:

* `echoscp <https://pydicom.github.io/pynetdicom/stable/apps/echoscp.html>`_
* `echoscu <https://pydicom.github.io/pynetdicom/stable/apps/echoscu.html>`_
* `findscu <https://pydicom.github.io/pynetdicom/stable/apps/findscu.html>`_
* `getscu <https://pydicom.github.io/pynetdicom/stable/apps/getscu.html>`_
* `movescu <https://pydicom.github.io/pynetdicom/stable/apps/movescu.html>`_
* `storescp <https://pydicom.github.io/pynetdicom/stable/apps/storescp.html>`_
* `storescu <https://pydicom.github.io/pynetdicom/stable/apps/storescu.html>`_

Code Examples
-------------

More
`code examples <https://pydicom.github.io/pynetdicom/stable/examples/index.html>`_
are available in the documentation.

Echo SCU
~~~~~~~~
Send a C-ECHO request to a Verification SCP (at TCP/IP address
*addr*, listen port number *port*):

.. code-block:: python

        from pynetdicom import AE

        ae = AE(ae_title=b'MY_ECHO_SCU')
        # Verification SOP Class has a UID of 1.2.840.10008.1.1
        #   we can use the UID str directly when adding the requested
        #   presentation context
        ae.add_requested_context('1.2.840.10008.1.1')

        # Associate with a peer AE
        assoc = ae.associate(addr, port)

        if assoc.is_established:
            # Send a DIMSE C-ECHO request to the peer
            status = assoc.send_c_echo()

            # Print the response from the peer
            if status:
                print('C-ECHO Response: 0x{0:04x}'.format(status.Status))

            # Release the association
            assoc.release()

Echo SCP
~~~~~~~~
Create a blocking Echo SCP on port ``11112`` (you may optionally
bind a handler to the ``evt.EVT_C_ECHO`` event if you want to return something
other than an ``0x0000`` *Success* status):

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
and make C-MOVE requests within the same AE.

In the next example we'll create a non-blocking Verification SCP and bind a
handler for the C-ECHO service request event ``evt.EVT_C_ECHO`` that logs the
requestor's address and port number and the timestamp for the event.

.. code-block:: python

        import logging

        from pynetdicom import AE, evt, debug_logger
        from pynetdicom.sop_class import VerificationSOPClass

        # Setup logging to use the StreamHandler at the debug level
        debug_logger()

        ae = AE(ae_title=b'MY_ECHO_SCP')
        ae.add_supported_context(VerificationSOPClass)

        # Implement the EVT_C_ECHO handler
        def handle_echo(event, logger):
            """Handle a C-ECHO service request.

            Parameters
            ----------
            event : evt.Event
                The C-ECHO service request event, this parameter is always
                present.
            logger : logging.Logger
                The logger to use, this parameter is only present because we
                bound ``evt.EVT_C_ECHO`` using a 3-tuple.

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
            logger.info(msg)

            # Return a *Success* status
            return 0x0000

        # By binding using a 3-tuple we can pass extra arguments to
        #   the handler
        handlers = [(evt.EVT_C_ECHO, handle_echo, [logging.getLogger('pynetdicom')])]

        # Start the SCP in non-blocking mode
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        # Associate and send a C-ECHO request to our own Verification SCP
        ae.add_requested_context(VerificationSOPClass)
        assoc = ae.associate('localhost', 11112)
        if assoc.is_established:
            status = assoc.send_c_echo()
            assoc.release()

        # Shutdown the SCP
        scp.shutdown()

Storage SCU
~~~~~~~~~~~
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
