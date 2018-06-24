.. currentmodule:: pynetdicom3.AE

Initialisation
--------------
A minimal initialisation of ``AE`` requires either the ``scu_sop_class`` or
``scp_sop_class`` parameter, although they can be empty. We'll get into what
these parameters are used for later on.

>>> from pynetdicom3 import AE
>>> ae = AE(scu_sop_class=[])
>>> ae = AE(scp_sop_class=[])

This will create an AE with an 'AE Title' of ``b'PYNETDICOM      '``. The AE
title can be set after initialisation using ``AE.ae_title = b'MY_AE_TITLE'`` or
by supplying the ``ae_title`` keyword parameter during initialisation:

>>> from pynetdicom3 import AE
>>> ae = AE(ae_title=b'MY_AE_TITLE', scu_sop_class=[])

AE titles must meet the conditions of a DICOM data element with a
*Value Representation* (VR) of 'AE' [1]_:

* Leading and trailing spaces (``0x20``) are non-significant
* Maximum 16 characters (once non-significant characters are removed)
* Valid characters belong to the DICOM *Default Character Repertoire* [2]_,
  which is the basic G0 Set of the ISO646:1990 [5]_ standard excluding
  backslash ('\\ ', ``0x5c``) and all control characters [3]_

There's also an extra restriction on Application Entity AE titles:

* An AE title made entirely of spaces is not allowed [4]_

AE titles in pynetdicom3 are first checked for validity (using
``utils.validate_ae_title``) and then stored as length 16 bytes, with trailing
spaces added as padding if required. This can be important to remember when
dealing with AE titles as the value you set may not be the value that gets
stored.

>>> ae.ae_title = b'MY_AE_TITLE'
>>> ae.ae_title == b'MY_AE_TITLE'
False
>>> ae.ae_title
b'MY_AE_TITLE     '



Initialising an SCU
~~~~~~~~~~~~~~~~~~~
If you intend to use your AE as an SCU then the you need to supply a list of
SOP Class UIDs that will be used as abstract syntaxes [6]_ in the requested
presentation contexts during association negotiation. This can be done by
supplying the ``scu_sop_class`` keyword parameter during initialisation:

>>> from pynetdicom3 import AE
>>> ae = AE(scu_sop_class=['1.2.840.10008.1.1'])

Alternatively you can set the ``AE.scu_supported_sop`` property after
initialisation:

>>> from pynetdicom3 import AE
>>> ae = AE(scu_sop_class=[])
>>> ae.scu_supported_sop = ['1.2.840.10008.1.1']

The SCU SOP Class UIDs can be supplied as str, bytes or pydicom.uid.UID
(however all supplied values will be converted to pydicom UID objects).
pynetdicom3 also has pre-defined lists of UIDs that can be used:

>>> from pynetdicom3 import AE, VerificationSOPClass
>>> ae = AE(scu_sop_class=[VerificationSOPClass])

>>> from pynetdicom3 import AE, StorageSOPClassList
>>> ae = AE(scu_sop_class=StorageSOPClassList)

During association the requestor (the SCU) is limited to 125
presentation contexts. If you supply more than 125 SOP Class UIDs then only the
first 125 will be used.

The other requirement when creating a presentation context is the transfer
syntax [7]_. pynetdicom3 defaults to requesting the following transfer syntaxes
for each presentation context:

* Implicit VR Little Endian - 1.2.840.10008.1.2
* Explicit VR Little Endian - 1.2.840.10008.1.2.1
* Explicit VR Big Endian - 1.2.840.10008.1.2.2

To set the requested transfer syntaxes for all the presentation contexts you
can either supply the ``transfer_syntax`` keyword parameter during initialisation
or set the ``AE.transfer_syntaxes`` property:

>>> from pydicom import ImplicitVRLittleEndian
>>> from pynetdicom3 import AE, VerificationSOPClass
>>> ae = AE(scu_sop_class=[VerificationSOPClass], transfer_syntax=[ImplicitVRLittleEndian])
>>> ae.transfer_syntaxes = [ImplicitVRLittleEndian]


Initialising an SCP
~~~~~~~~~~~~~~~~~~~
If you intend to use your AE as an SCP then the you need to supply a list of
supported abstract syntax SOP Class UIDs. These supported SOP Classes will be
compared against the requested ones sent during association negotiation in
order to determine whether to accept or reject a given presentation context.
Supplying the supported SOP Classes can be done via the ``scu_sop_class``
keyword parameter during initialisation:

>>> from pynetdicom3 import AE
>>> ae = AE(scp_sop_class=['1.2.840.10008.1.1'])

Alternatively you can set the ``AE.scp_supported_sop`` property after
initialisation:

>>> from pynetdicom3 import AE
>>> ae = AE(scp_sop_class=[])
>>> ae.scp_supported_sop = ['1.2.840.10008.1.1']

As with the SCU initialisation the supported transfer syntaxes defaults to:

* Implicit VR Little Endian - 1.2.840.10008.1.2
* Explicit VR Little Endian - 1.2.840.10008.1.2.1
* Explicit VR Big Endian - 1.2.840.10008.1.2.2

When acting as an SCP the AE needs to know what TCP port to listen on for
incoming association requests. This can be set with the ``port`` keyword
parameter during initialisation or by setting the ``AE.port`` property:

>>> from pynetdicom3 import AE
>>> ae = AE(scp_sop_class=[], port=11112)
>>> ae.port = 104

If the ``port`` isn't set then it defaults to 0, which indicates to the OS that
the first available port should be used. Since this is semi-random its
generally only suitable when operating as an SCU. Port 104 the official IANA
port for DICOM SCPs, but this usually requires root access. For situations
where it isn't possible to use 104 the typical alternative is to use 11112.

Initialising a mixed SCU/SCP
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Certain service classes (such as Query Retrieve when sending a C-GET message)
may require that an AE be capable of acting as both an SCU and SCP
simultaneously. This can be done by supply both the ``scu_sop_class`` and
``scp_sop_class`` keyword parameters during initialisation:

>>> from pynetdicom3 import AE, StorageSOPClassList, QueryRetrieveSOPClassList
>>> ae = AE(scu_sop_class=QueryRetrieveSOPClassList, scp_sop_class=StorageSOPClassList)

In this example the Query/Retrieve SOP Classes will be used when creating the
SCU's requested presentation contexts and the Storage SOP Classes will be used
as the SCP's supported abstract syntaxes.

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
.. [6] DICOM Standard, Part 8
   `Annex B.1 <http://dicom.nema.org/medical/dicom/current/output/html/part08.html#sect_B.1>`_
.. [7] DICOM Standard, Part 8
   `Annex B.2 <http://dicom.nema.org/medical/dicom/current/output/html/part08.html#sect_B.2>`_
