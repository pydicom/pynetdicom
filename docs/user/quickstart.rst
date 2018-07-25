Quickstart
----------

SCU
~~~

For this example we want to create an Application Entity and then request an
association with a peer with the intention of using the peer's Storage Service
to store a single CT dataset.

.. code-block:: python


   from pydicom import dcmread

   from pynetdicom3 import AE
   from pynetdicom3.sop_class import CTImageStorage

   # Initialise the Application Entity
   ae = AE()

   # Add presentation context(s)
   ae.add_requested_context(CTImageStorage)

   # Associate with peer at IP 127.0.0.1 and port 11112
   assoc = ae.associate('127.0.0.1', 11112)

   # Read in our CT dataset
   ds = dcmread('path/to/DICOM/CT/dataset')

   if assoc.is_established:
       # Send the dataset via the C-STORE service
       status = assoc.send_c_store(ds)

       # Check the status of the storage request
       if 'Status' in status:
           print('C-STORE request response: ', status.Status)

       # Release the association
       assoc.release()
   else:
       print('Association rejected or aborted')

Define the presentation contexts you want to request be supported by the peer.
Here we want a single presentation context with an Abstract Syntax for the
CT Image Storage SOP Class (UID 1.2.840.10008.5.1.4.1.1.2).

>>> from pynetdicom3.sop_class import CTImageStorage
>>> ae.add_requested_context(CTImageStorage)

Request an association with the peer at IP address '127.0.0.1' and port 11112:

>>> assoc = ae.associate('127.0.0.1', 104)

If the association is established we can send our dataset, which we have
read from file using pydicom's dcmread function.

>>> from pydicom import dcmread
>>> ds = dcmread('path/to/DICOM/CT/dataset')
>>> if assoc.is_established:
...     status = assoc.send_c_store(ds)
...     if 'Status' in status:
...         print(status.Status)
...     assoc.release()

If the peer responds to our storage request then status is a pydicom Dataset
with (at a minimum) a (0000,0900) Status element. If the peer timed out or
sent an invalid response then status will be an empty Dataset.

If the peer successfully completed the storage request then the value of the
Status element will be 0x0000 (0).



We can release our association now



Putting it all together:

>>> from pydicom import dcmread
>>> from pynetdicom3 import AE
>>> from pynetdicom3.sop_class import CTImageStorage
>>> ae = AE()
>>> ae.add_requested_context(CTImageStorage)
>>> assoc = ae.associate('127.0.0.1', 104)
>>> ds = dcmread('path/to/DICOM/CT/dataset')
>>> if assoc.is_established:
...     status = assoc.send_c_store(ds)
...     if 'Status' in status:
...         print('C-STORE request response: ', status.Status)
...     assoc.release()
>>> else:
...    print('Unable to associate')




SCP
~~~
