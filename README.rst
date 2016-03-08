pynetdicom
==========

Implementation of the `DICOM <http://dicom.nema.org>`_ networking protocol.

Description
-----------

`DICOM <http://dicom.nema.org>`_ is the international standard for medical images 
and related information. It defines the formats and communication protocols for 
media exchange in radiology, cardiology, radiotherapy and other medical domains.

*pynetdicom* is a pure Python (3+) program that implements the DICOM networking
protocol. Working with `pydicom <https://github.com/darcymason/pydicom>`_, it allows the easy creation of DICOM clients 
(SCUs) and servers (SCPs).  
      
The main user class is ApplicationEntity, which represents a DICOM application 
entity. The user will typically create an ApplicationEntity object then either
start the application as an SCP using ApplicationEntity.start() or use the 
application as an SCU by attempting to associate with a peer SCP via the 
ApplicationEntity.associate() method and then using the association to send or 
receive DICOM data.

Installation
-----------
- From github:

.. code-block:: sh 

        $ git clone https://github.com/scaramallion/pynetdicom.git
        $ cd pynetdicom
        $ python setup.py install

Examples
--------
- Send a DICOM C-ECHO to a peer Verification SCP (at TCP/IP address *addr*, listen port number *port*): 

.. code-block:: python 

        from pynetdicom.ae import AE
        
        # The Verification SOP Class has a UID of 1.2.840.10008.1.1
        ae = AE(scu_sop_class=['1.2.840.10008.1.1'])
        
        assoc = ae.associate(addr, port)
        assoc.send_c_echo()
        assoc.Release()
        
- Create a DICOM C-ECHO listen SCP on port 11112: 

.. code-block:: python 

        from pynetdicom.ae import AE

        # The Verification SOP Class has a UID of 1.2.840.10008.1.1
        ae = AE(port=11112, scp_sop_class=['1.2.840.10008.1.1'])
        ae.start()

- Send a DICOM CTImageStorage file to a peer Storage SCP (at TCP/IP address *addr*, listen port number *port*): 

.. code-block:: python 

        from pydicom import read_file
        from pynetdicom.ae import AE
        
        # The CT Image Storage SOP Class has a UID of 1.2.840.10008.5.1.4.1.1.2
        ae = AE(scu_sop_class=['1.2.840.10008.5.1.4.1.1.2'])
        
        assoc = ae.associate(addr, port)
        if assoc.is_established:
            dataset = read_file('test_file.dcm')
            assoc.send_c_store(dataset)
        
        assoc.Release()

Dependencies
------------
`pydicom <https://github.com/darcymason/pydicom>`_ >= 1.0.0
