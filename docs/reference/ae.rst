.. _ae:

Application Entity (:mod:`pynetdicom3.AE`)
==========================================

.. currentmodule:: pynetdicom3.AE

A DICOM Application Entity (AE) is the end point of DICOM information exchange.
In other words, its the software that sends or receives DICOM information
objects or messages. In pynetdicom3, an AE is the highest level of the
API and can be used to start associations with peer AEs (as a *Service Class
User*) or listen for association requests (as a *Service Class Provider*).

Initialisation
--------------
A minimal initialisation of ``AE`` requires no parameters:

>>> from pynetdicom3 import AE
>>> ae = AE()

This will create an AE with an *AE Title* of ``b'PYNETDICOM'``. The AE
title can be set after initialisation using ``AE.ae_title = b'MY_AE_TITLE'`` or
by supplying the ``ae_title`` keyword parameter during initialisation:

>>> from pynetdicom3 import AE
>>> ae = AE(ae_title=b'MY_AE_TITLE')

AE titles must meet the conditions of a DICOM data element with a
*Value Representation* (VR) of 'AE' [1]_:

* Leading and trailing spaces (``0x20``) are non-significant
* Maximum 16 bytes maximum (once non-significant characters are removed)
* Valid characters belong to the DICOM *Default Character Repertoire* [2]_,
  which is the basic G0 Set of the ISO646:1990 [5]_ standard excluding
  backslash ('\\ ', ``0x5c``) and all control characters [3]_

There's also an extra restriction on Application Entity AE titles:

* An AE title made entirely of spaces is not allowed [4]_

AE titles in pynetdicom3 are first checked for validity (using
``utils.validate_ae_title``) and then stored as length 16 bytes, with trailing
spaces added as padding if required.


Initialising an SCU
~~~~~~~~~~~~~~~~~~~
If you intend to use your AE as an SCU then you need to supply a list of
SOP Class UIDs that will be used to create the requested presentation contexts
during association negotiation. This can be done by supplying the
``scu_sop_class`` and ``transfer_syntax`` keyword parameters during
initialisation:

>>> from pynetdicom3 import AE
>>> ae = AE(scu_sop_class=['1.2.840.10008.1.1'], transfer_syntax=['1.2.840.10008.1.2'])

Alternatively you can set the ``AE.scu_supported_sop`` and
``AE.transfer_syntaxes`` properties after initialisation.

>>> from pynetdicom3 import AE
>>> ae = AE()
>>> ae.scu_supported_sop = ['1.2.840.10008.1.1']
>>> ae.transfer_syntaxes = ['1.2.840.10008.1.2']

The SCU SOP Class UIDs can be supplied as str, bytes or pydicom.uid.UID
(however all supplied values will be converted to pydicom UID objects).
pynetdicom3 also has pre-defined lists of UIDs that can be used:

>>> from pynetdicom3 import AE, VerificationSOPClass
>>> ae = AE(scu_sop_class=[VerificationSOPClass])

>>> from pynetdicom3 import AE, StorageSOPClassList
>>> ae = AE(scu_sop_class=StorageSOPClassList)

If you want to be able to specify the transfer syntaxes for each Presentation
Context individually then you should pass a list of
``presentation.PresentationContext`` items during
``AE.associate(contexts=[])``.


Initialising an SCP
~~~~~~~~~~~~~~~~~~~


References
----------

.. [1] DICOM Standard, Part 5
   `Section 6.2 <http://dicom.nema.org/medical/dicom/current/output/html/part05.html#sect_6.2>`_
.. [2] DICOM Standard, Part 5
   `Section 6.1.2.1 <http://dicom.nema.org/medical/dicom/current/output/html/part05.html#sect_6.1.3>`_
.. [3] DICOM Standard, Part 5
   `Section 6.1.3 <http://dicom.nema.org/medical/dicom/current/output/html/part05.html#sect_6.1.3>`_
.. [4] DICOM Standard, Part 8
   `Section 9.3.2 <http://dicom.nema.org/medical/dicom/current/output/html/part08.html#sect_9.3.2>`_
.. [5] `ISO/IEC 646:1991 <https://www.iso.org/standard/4777.html>`_
