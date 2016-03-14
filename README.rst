pynetdicom
==========

Implementation of the `DICOM <http://dicom.nema.org>`_ networking protocol.

Description
-----------

`DICOM <http://dicom.nema.org>`_ is the international standard for medical 
images and related information. It defines the formats and communication 
protocols for media exchange in radiology, cardiology, radiotherapy and other 
medical domains.

*pynetdicom* is a pure Python (3+) program that implements the DICOM networking 
protocol. Working with `pydicom <https://github.com/darcymason/pydicom>`_, it 
allows the easy creation of DICOM clients (*Service Class Users* or SCUs) and 
servers (*Service Class Providers* or SCPs). 

The main user class is AE, which represents a DICOM Application Entity. The 
user will typically create an ApplicationEntity object then either:

- Start the application as an SCP using ``AE.start()`` and wait for incoming 
  association requests
- Request an association with a peer SCP using the ``AE.associate(addr, port)`` 
  method.

Once the AE is associated with a peer, DICOM data can be sent between them by 
utilising the DIMSE-C and DIMSE-N services (see DICOM Standard PS3.7, Sections 
7.5, 9 and 10).

Supported SCU Services
~~~~~~~~~~~~~~~~~~~~~~

When the AE is acting as an SCU the following DIMSE-C services are available to 
the ``Association`` class once an association has been established with a peer 
SCP (provided that the peer supports the corresponding Service Classes):

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
- C-MOVE: ``Association.send_c_move(dataset)`` requests the peer search its set 
  of managed SOP Instances for those that match the attributes given in 
  *dataset* and then move those matching Instances to another AE.

See the SCU Examples and the Association documentation for more information.

Supported SCP Services
~~~~~~~~~~~~~~~~~~~~~~

When the AE is acting as an SCP the following DIMSE-C services are available to 
the peer once an association has been established. The user is expected to 
define their own responses via the following ``AE`` callbacks:

- C-ECHO: ``AE.on_c_echo()``
- C-STORE: ``AE.on_c_store(sop_class, dataset)``
- C-FIND: ``AE.on_c_find(sop_class, dataset)``
- C-GET: ``AE.on_c_get(sop_class, dataset)``
- C-MOVE: ``AE.on_c_move(sop_class, dataset)``
 
See the SCP Examples and the AE documentation for more information.


Installation
-----------
- From github:

.. code-block:: sh 

        $ git clone https://github.com/scaramallion/pynetdicom.git
        $ cd pynetdicom
        $ python setup.py install

Examples
--------
- Send a DICOM C-ECHO to a peer Verification SCP (at TCP/IP address *addr*, 
  listen port number *port*): 

.. code-block:: python 

        from pynetdicom import AE
        
        # The Verification SOP Class has a UID of 1.2.840.10008.1.1
        ae = AE(scu_sop_class=['1.2.840.10008.1.1'])
        
        # Associate with a peer DICOM AE
        assoc = ae.associate(addr, port)
        
        if assoc.is_established:
            # Send a DIMSE C-ECHO request to the peer
            assoc.send_c_echo()
        
            # Release the association
            assoc.release()
        
- Create a DICOM C-ECHO listen SCP on port 11112: 

.. code-block:: python 

        from pynetdicom import AE

        # The Verification SOP Class has a UID of 1.2.840.10008.1.1
        ae = AE(port=11112, scp_sop_class=['1.2.840.10008.1.1'])
        
        # Start the SCP
        ae.start()

- Send a DICOM CTImageStorage file to a peer Storage SCP (at TCP/IP address 
  *addr*, listen port number *port*): 

.. code-block:: python 

        from pydicom import read_file
        from pynetdicom import AE
        
        # The CT Image Storage SOP Class has a UID of 1.2.840.10008.5.1.4.1.1.2
        ae = AE(scu_sop_class=['1.2.840.10008.5.1.4.1.1.2'])
        
        assoc = ae.associate(addr, port)
        if assoc.is_established:
            dataset = read_file('test_file.dcm')
            assoc.send_c_store(dataset)
        
        assoc.release()

Dependencies
------------
`pydicom <https://github.com/darcymason/pydicom>`_ >= 1.0.0
