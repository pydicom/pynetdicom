
.. _concepts_uids:

UIDs
----
Unique identifiers (UIDs) are a way of identifying a wide variety
of items in a way that guarantees uniqueness across multiple countries, sites,
vendors and equipment. The UID identification scheme used by DICOM is based on
the numeric form of the OSI Object Identification as defined by
`ISO/IEC 8824 <https://www.iso.org/standard/68350.html>`_
(`ITU X.680 <https://www.itu.int/itu-t/recommendations/rec.aspx?rec=x.680>`_).

Each UID is composed of two parts, an ``<org root>`` and a ``<suffix>``:
``UID = <org root>.<suffix>``


The ``<org root>`` uniquely identifies an organisation and is composed of
numeric components as defined by ISO/IEC 8824. The ``<suffix>`` portion of the
UID is also composed of a number of numeric components, however it is generated
by the application and must be unique within the scope of the ``<org root>``.
If you don't have an ``<org root>`` and you don't want to use *pynetdicom's*
(``1.2.826.0.1.3680043.9.3811``) an ``<org root>`` can be obtained for free
from the `Medical Connections <https://www.medicalconnections.co.uk/FreeUID/>`_
website.

The DICOM ``<org root>`` is ``1.2.840.10008`` and is reserved for use for DICOM
defined items and shall not be used for privately defined items. As an example,
the official DICOM UID for *CT Image Storage* is
``1.2.840.10008.5.1.4.1.1.2``, which makes the ``<suffix>`` ``5.1.4.1.1.2``

Each component of a UID (``1``, ``2``, ``840``, ``10008`` are all components)
must not start with ``0`` unless the component itself is ``0`` (e.g.
``1.2.0.4`` is valid but ``1.2.08.4`` is invalid) and the maximum length of a
UID is 64 total characters.

More information on DICOM UIDs is available in :dcm:`Part 5 <part05.html>`
of the DICOM Standard.
