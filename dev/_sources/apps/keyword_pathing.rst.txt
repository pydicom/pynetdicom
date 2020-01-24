Keyword pathing
===============

When using the `-k keyword` option it becomes possible to specify the
query dataset (the *Identifier*) without needing to create a DICOM file.
Multiple instances of `-k` can be used to build up the *Identifier*. For
example, this will produce an *Identifier* with (0008,0052) *Query Retrieve
Level* and (0010,0010) *Patient Name* elements:

.. code-block:: text

    -k QueryRetrieveLevel=PATIENT -k PatientName=

The value after the ``=`` is interpreted as the element's value, so including
any single or double quotation marks will result in
an incorrect element value. ``PatientName=Citizen^Jan`` is correct,
``PatientName="Citizen^Jan"`` is not.

Alternatively the element tags can be used instead:

.. code-block:: text

    -k (0008,0052)=PATIENT -k (0010,0010)=

Sequences can be specified using the same Python indexing syntax as used by
*pydicom*:

.. code-block:: text

    -k OtherPatientIDsSequence[2].PatientID=12345678

When both the `-f file` and `-k keyword` options are used then the keywords
will be used to update the elements in the file.


Examples
--------

Empty (0010,0010) *Patient Name* element:

.. code-block:: text

    -k PatientName=
    -k (0010,0010)=

    (0010, 0010) Patient's Name                      PN: ''

*Patient Name* set to ``Citizen^Jan``:

.. code-block:: text

    -k PatientName=Citizen^Jan
    -k (0010,0010)=Citizen^Jan

    (0010, 0010) Patient's Name                      PN: 'Citizen^Jan'

Numeric VRs like **US** and **FL** are converted to either :class:`int`
or :class:`float` depending on the VR:

.. code-block:: text

    -k Columns=1024

    (0028, 0011) Columns                             US: 1024

Byte VRs like **OB** and **OW** are converted to :class:`bytes`:

.. code-block:: text

    -k PixelData=00FFEA08

    (7fe0, 0010) Pixel Data                          OW: b'\x00\xff\xea\x08'

Elements with VM > 1 can be set by using ``\\`` (where appropriate):

.. code-block:: text

    -k AcquisitionIndex=1\\2\\3\\4

    (0020, 9518) Acquisition Index                   US: [1, 2, 3, 4]

Empty (300A,00B0) *Beam Sequence*:

.. code-block:: text

    -k BeamSequence=
    -k (300a,00b0)=

    (300a, 00b0)  Beam Sequence   0 item(s) ----

*Beam Sequence* with one empty item:

.. code-block:: text

    -k BeamSequence[0]=

    (300a, 00b0)  Beam Sequence   1 item(s) ----

       ---------

*Beam Sequence* with four empty items:

.. code-block:: text

    -k BeamSequence[3]=

    (300a, 00b0)  Beam Sequence   4 item(s) ----

       ---------

       ---------

       ---------

       ---------

*Beam Sequence* with one non-empty item:

.. code-block:: text

    -k BeamSequence[0].PatientName=CITIZEN^Jan

    (300a, 00b0)  Beam Sequence   1 item(s) ----
       (0010, 0010) Patient's Name                      PN: 'Citizen^Jan'
       ---------

Nested sequence items:

.. code-block:: text

    -k BeamSequence[0].BeamLimitingDeviceSequence[0].NumberOfLeafJawPairs=1

    (300a, 00b0)  Beam Sequence   1 item(s) ----
       (300a, 00b6)  Beam Limiting Device Sequence   1 item(s) ----
          (300a, 00bc) Number of Leaf/Jaw Pairs            IS: "1"
          ---------
       ---------
