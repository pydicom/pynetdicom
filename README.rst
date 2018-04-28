.. class:: center
.. image:: https://codecov.io/gh/pydicom/pynetdicom3/branch/master/graph/badge.svg
    :target: https://codecov.io/gh/pydicom/pynetdicom3
.. image:: https://travis-ci.org/pydicom/pynetdicom3.svg?branch=master
    :target: https://travis-ci.org/pydicom/pynetdicom3
.. image:: https://circleci.com/gh/pydicom/pynetdicom3/tree/master.svg?style=svg
    :target: https://circleci.com/gh/pydicom/pynetdicom3/tree/master

pynetdicom3
===========

A Python 2.7/3+ implementation of the `DICOM <http://dicom.nema.org>`_ networking protocol,
originally based on `pynetdicom <https://github.com/patmun/pynetdicom>`_.

Description
-----------

`DICOM <http://dicom.nema.org>`_ is the international standard for medical
images and related information. It defines the formats and communication
protocols for media exchange in radiology, cardiology, radiotherapy and other
medical domains.

*pynetdicom3* is a pure Python (2.7/3+) program that implements the DICOM networking
protocol. Working with `pydicom <https://github.com/pydicom/pydicom>`_, it
allows the easy creation of DICOM clients (*Service Class Users* or SCUs) and
servers (*Service Class Providers* or SCPs).

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

Supported SCU Services
~~~~~~~~~~~~~~~~~~~~~~

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

Where *dataset* is a pydicom Dataset object. See the `SCU Examples
<docs/scu_examples.rst>`_ and the Association documentation for more
information.

Supported SCP Services
~~~~~~~~~~~~~~~~~~~~~~

When the AE is acting as an SCP the following DIMSE-C services are available to
the peer once an association has been established. With the exception of
``on_c_echo()``, the user is expected to handle the required operations by
implementing the following ``AE`` callbacks:

- C-ECHO: ``AE.on_c_echo()``
- C-STORE: ``AE.on_c_store(dataset)``
- C-FIND: ``AE.on_c_find(dataset)`` and ``AE.on_c_find_cancel()``
- C-GET: ``AE.on_c_get(dataset)`` and ``AE.on_c_get_cancel()``
- C-MOVE: ``AE.on_c_move(dataset, move_aet)`` and ``AE.on_c_move_cancel()``

Where *dataset* is a pydicom Dataset object. See the SCP Examples and the AE
documentation for more information.

Documentation
-------------
Documentation is available for stable releases as well as the current `development version. <https://pydicom.github.io/pynetdicom3/dev>`_

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

        # The Verification SOP Class has a UID of 1.2.840.10008.1.1
        #   we can use the UID string directly
        ae = AE(scu_sop_class=['1.2.840.10008.1.1'])

        # Associate with a peer DICOM AE
        assoc = ae.associate(addr, port)

        if assoc.is_established:
            # Send a DIMSE C-ECHO request to the peer
            # `status` is a pydicom Dataset object with (at a minimum) a
            # (0000,0900) Status element
            status = assoc.send_c_echo()

            # Output the response from the peer
            if status:
                print('C-ECHO Response: 0x{0:04x}'.format(status.Status))

            # Release the association
            assoc.release()

- Create a DICOM C-ECHO listen SCP on port 11112 (you may optionally implement
  the `AE.on_c_echo callback` if you want to return a non Success status):

.. code-block:: python

        from pynetdicom3 import AE, VerificationSOPClass

        # Or we can use the inbuilt Verification SOP Class
        ae = AE(port=11112, scp_sop_class=[VerificationSOPClass])

        # Start the SCP
        ae.start()

- Send the DICOM CTImageStorage dataset in *file-in.dcm* to a peer Storage SCP
  (at TCP/IP address *addr*, listen port number *port*):

.. code-block:: python

        from pydicom import read_file
        from pydicom.uid import UID

        from pynetdicom3 import AE

        # Or we can use a pydicom.uid.UID
        #   CTImageStorage has a UID of 1.2.840.10008.5.1.4.1.1.2
        ct_storage_uid = UID('1.2.840.10008.5.1.4.1.1.2')
        ae = AE(scu_sop_class=[ct_storage_uid])

        assoc = ae.associate(addr, port)
        if assoc.is_established:
            dataset = read_file('file-in.dcm')
            # `status` is the response from the peer to the store request
            # but may be an empty pydicom Dataset if the peer timed out or
            # sent an invalid dataset.
            status = assoc.send_c_store(dataset)

            assoc.release()
