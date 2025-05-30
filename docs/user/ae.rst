.. currentmodule:: pynetdicom.ae

Introduction
------------

The first step in DICOM networking with *pynetdicom* is the creation of an
:ref:`Application Entity <concepts_ae>` by using the
:class:`AE<ApplicationEntity>` class. A minimal initialisation of
:class:`AE<ApplicationEntity>` requires no parameters:

.. doctest::

    >>> from pynetdicom import AE
    >>> ae = AE()

This will create an :class:`AE<ApplicationEntity>` with an AE title of
``'PYNETDICOM'``. The AE title can set by supplying the *ae_title*
keyword parameter during initialisation:

.. doctest::

    >>> from pynetdicom import AE
    >>> ae = AE(ae_title='MY_AE_TITLE')

Or afterwards with the :attr:`~ApplicationEntity.ae_title` property:

.. doctest::

    >>> from pynetdicom import AE
    >>> ae = AE()
    >>> ae.ae_title = 'MY_AE_TITLE'

AE titles must meet the conditions of a DICOM data element with a
:dcm:`Value Representation <part05/sect_6.2.html>` of **AE**:

* Leading and trailing spaces (hex ``0x20``) are non-significant.
* Maximum 16 characters (once non-significant characters are removed).
* Valid characters belong to the DICOM :dcm:`Default Character Repertoire
  <part05/chapter_E.html>`, which is the basic G0 Set of the
  `ISO/IEC 646:1991 <https://www.iso.org/standard/4777.html>`_
  (ASCII) standard excluding backslash (``\`` - hex ``0x5C``) and all control
  characters (such as ``'\n'``).
* An AE title made entirely of spaces is not allowed.

When creating SCPs it's also possible to give each SCP its own AE title through
the *ae_title* keyword parameter in
:meth:`AE.start_server()<pynetdicom.ae.ApplicationEntity.start_server>`.


References
..........

* DICOM Standard, Part 5 :dcm:`Section 6.2<part05.html#sect_6.2>`
* DICOM Standard, Part 5 :dcm:`Section 6.1.2.1<part05.html#sect_6.1.3>`
* DICOM Standard, Part 5 :dcm:`Section 6.1.3<part05.html#sect_6.1.3>`
* DICOM Standard, Part 8 :dcm:`Section 9.3.2<part08.html#sect_9.3.2>`
* DICOM Standard, Part 8 :dcm:`Annex B.1<part08.html#sect_B.1>`
* DICOM Standard, Part 8 :dcm:`Annex B.2<part08.html#sect_B.2>`
