.. _association:

Associations
============


.. toctree::
   :maxdepth: 2

   association.associating
   association.releasing


   XXX: Move to association page
   Associating
   ...........
   Once the requested presentation contexts have been added you can associate with
   a peer with the ``AE.associate()`` method which returns an Association thread:

   .. code-block: python

       from pynetdicom3 import AE
       from pynetdicom3.sop_class import VerificationSOPClass

       ae = AE()
       ae.add_requested_context(VerificationSOPClass)

       # Associate with the peer at IP address 127.0.0.1 and port 11112
       assoc = ae.associate('127.0.0.1', 11112)

   There are four potential outcomes of an association request: acceptance and
   establishment, association rejection, association abort or a connection
   failure, so its a good idea to test for acceptance prior to attempting to use
   the services provided by the SCP.

   .. code-block: python

       from pynetdicom3 import AE
       from pynetdicom3.sop_class import VerificationSOPClass

       ae = AE()
       ae.add_requested_context(VerificationSOPClass)

       # Associate with the peer at IP address 127.0.0.1 and port 11112
       assoc = ae.associate('127.0.0.1', 11112)
       if assoc.is_established:
           # Do something...
           pass
