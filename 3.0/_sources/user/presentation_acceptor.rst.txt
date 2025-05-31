
.. currentmodule:: pynetdicom.presentation

Contexts and the Association Acceptor
-------------------------------------

When acting as the association *acceptor* (usually the SCP), you should define
which presentation contexts will be supported. Unlike the *requestor* you can
define an unlimited number of supported presentation contexts.

In *pynetdicom* this is accomplished through one of the following methods:

1. Setting the :attr:`AE.supported_contexts
   <pynetdicom.ae.ApplicationEntity.supported_contexts>`
   attribute directly using a list of :class:`PresentationContext` items.

   .. code-block:: python

        from pynetdicom import AE, build_context
        from pynetdicom.sop_class import Verification

        ae = AE()
        ae.supported_contexts = [build_context(Verification)]
        ae.start_server(("127.0.0.1", 11112))


2. Using the
   :meth:`AE.add_supported_context()
   <pynetdicom.ae.ApplicationEntity.add_supported_context>`
   method to add a new :class:`PresentationContext` to the
   :attr:`AE.supported_contexts
   <pynetdicom.ae.ApplicationEntity.supported_contexts>` attribute.

   .. code-block:: python

        from pynetdicom import AE
        from pynetdicom.sop_class import Verification

        ae = AE()
        ae.add_supported_context(Verification)
        ae.start_server(("127.0.0.1", 11112))

3. Supplying a list of :class:`PresentationContext` items to
   :meth:`AE.start_server()<pynetdicom.ae.ApplicationEntity.start_server>`
   via the `contexts` keyword parameter

   .. code-block:: python

       from pynetdicom import AE, build_context
       from pynetdicom.sop_class import Verification

       ae = AE()
       supported = [build_context(Verification)]
       ae.start_server(("127.0.0.1", 11112), contexts=supported)


The abstract syntaxes you support should correspond to the service classes that
are being offered. For example, if you offer the
:dcm:`Storage Service<part04/chapter_B.html>` then you should
support one or more of the Storage Service's :dcm:`corresponding SOP Classes
<part04/sect_B.5.html>`.

The transfer syntaxes for each abstract syntax should match the data encoding
you support.

.. note::
   In general, *pynetdicom* is able to support any transfer syntax when
   acting as an SCP.
