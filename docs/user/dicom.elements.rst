.. _elements:

The DICOM Data Element
======================

DICOM Data Elements are used in the DICOM standard to store values. Below are
two typical elements in their raw encoded form and as displayed in a human
readable version.

.. code-block:: python

    >>> from pydicom import dcmread
    >>> from pynetdicom3.dsutils import encode_element
    >>> from pynetdicom3.utils import pretty_bytes
    >>> ds = dcmread('explicit_little.dcm')
    >>> elem = ds[0x0010, 0x0020]
    >>> elem
    (0010, 0020) Patient ID                          LO: '1CT1'
    >>> encoded_elem = encode_element(elem, is_implicit_vr=False, is_little_endian=True)
    >>> pretty_bytes(encoded_elem, prefix='')[0]
    10 00 20 00 4c 4f 04 00 31 43 54 31
    >>> encoded_elem = encode_element(elem, is_implicit_vr=False, is_little_endian=False)
    >>> pretty_bytes(encoded_elem, prefix='')[0]
    00 10 00 20 4c 4f 00 04 31 43 54 31
    >>> encoded_elem = encode_element(elem, is_implicit_vr=True, is_little_endian=True)
    >>> pretty_bytes(encoded_elem, prefix='')[0]
    10 00 20 00 04 00 00 00 31 43 54 31
    >>> encoded_elem = encode_element(elem, is_implicit_vr=True, is_little_endian=False)
    >>> pretty_bytes(encoded_elem, prefix='')[0]
    00 10 00 20 00 00 00 04 31 43 54 31

Each Data Element is made of the following fields:

Tag
  A Tag is represented by an ordered  pair of 16-bit unsigned integers that
  represent the Group and the Element numbers of the Data Element.

Value Representation (VR)
  Two single byte characters containing the VR of the Data Element. The VR
  for a given Tag shall be defined by the Data Dictionary [2]_ and encoded
  using characters from the DICOM default character set [3]_. The VR is only
  present in an encoded Data Element when one of the Explicit VR encodings [4]_
  is used.

Value Length
  Either

  - an 16- or 32-bit unsigned integer (dependent on VR and whether the encoding
    is Explicit or Implicit VR).
  - a 32-bit unsigned integer set to ``0xFFFFFFFF``, which signifies that the
    Data Element has an undefined length. Undefined lengths are used for
    Data Elements with VRs of SQ and UN. For Data Elements with VRs of OW or
    OB, undefined length may be used depending on the negotiated Transfer
    Syntax [5]_.

Value
  An even number of bytes containing the value(s) of the Data Element. The type
  of data stored is specified by the VR. The number of values stored is
  given by the Value Multiplicity (VM), which is defined in the Data Dictionary
  for a given Tag. If the VM is 1 then only one value is stored. If the VM is
  greater than 1 then multiple values are stored within the Value. Data
  Elements with undefined length have Values that are delimited through the
  use of Sequence Delimitation Items and Item Delimitation Items [6]_.

Data Element Structure
----------------------
Explicit VR, VR of OB, OD, OF, OL, OW, SQ, UC, UR, UT or UN
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
+---------------------+----------+-------------------------------------+
| Tag                 | VR       | Value Length | Value                |
+----------+----------+----------+--------------+----------------------+
| Group    | Element  | 2 single | 32-bit       | Even number of bytes |
| 16-bit   | 16-bit   | byte     | unsigned     |                      |
| unsigned | unsigned | chars    | integer      |                      |
| integer  | integer  |          |              |                      |
+==========+==========+==========+==============+======================+
| 2 bytes  | 2 bytes  | 2 bytes  | 4 bytes      | 'Value Length' bytes |
+----------+----------+----------+--------------+----------------------+

Examples
^^^^^^^^

Explicit VR, all other VRs
~~~~~~~~~~~~~~~~~~~~~~~~~~
+---------------------+----------+-------------------------------------+
| Tag                 | VR       | Value Length | Value                |
+----------+----------+----------+--------------+----------------------+
| Group    | Element  | 2 single | 16-bit       | Even number of bytes |
| 16-bit   | 16-bit   | byte     | unsigned     |                      |
| unsigned | unsigned | chars    | integer      |                      |
| integer  | integer  |          |              |                      |
+==========+==========+==========+==============+======================+
| 2 bytes  | 2 bytes  | 2 bytes  | 2 bytes      | 'Value Length' bytes |
+----------+----------+----------+--------------+----------------------+

Examples
^^^^^^^^
*All examples show encoded Data Elements, expressed in hexadecimal.*

Tag         VR Value         Length VM Keyword
(0008,0016) UI 1.2.3         6       1 SOPClassUID

``08 00 16 00 55 49 06 00 31 2E 32 2E 33 00``


Big Endian Explicit VR


Implicit VR
~~~~~~~~~~~
+---------------------+--------------+------------------------------------+
| Tag                 | Value Length | Value                              |
+----------+----------+--------------+------------------------------------+
| Group    | Element  | 32-bit       | Even number of bytes               |
| 16-bit   | 16-bit   | unsigned     |                                    |
| unsigned | unsigned | integer      |                                    |
| integer  | integer  |              |                                    |
+==========+==========+==============+====================================+
| 2 bytes  | 2 bytes  | 4 bytes      | 'Value Length' bytes or 0xFFFFFFFF |
+----------+----------+--------------+------------------------------------+

Examples
^^^^^^^^
Little Endian Implicit VR


References
----------

.. [2] DICOM Standard, Part 6.
.. [3] Reference for default character set.
.. [4] Reference for encodings.
.. [5] Reference for transfer syntaxes.
.. [6] Reference for Sequence and Item Delimitation Items.
