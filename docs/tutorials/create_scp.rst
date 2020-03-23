======================
Writing your first SCP
======================

.. currentmodule:: pynetdicom

In this tutorial you will:

* Create a new Storage SCP application using *pynetdicom*
* Send datasets to it using *pynetdicom's* ``storescu`` application
* Something else

If you need to install *pynetdicom* please follow the instructions in the
:doc:`installation guide</tutorials/installation>`. For this tutorial we'll
also be using the :doc:`storescu<../apps/storescu>` application that comes with
*pynetdicom*.

If you haven't already seen it, it's recommended that you check out the
tutorial on :doc:`writing your first SCU<create_scu>` before continuing.

What's a Storage SCP?
=====================


.. code-block:: python

    from pynetdicom import AE, evt
    from pynetdicom.sop_class import CTImageStorage

    ae = AE()
    ae.add_supported_context(CTImageStorage)
    ae.start_server(('', 11112))
