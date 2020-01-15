"""DICOM Upper Layer PDU Items and Sub-items.

**A-ASSOCIATE-RQ PDU Items**

- ApplicationContextItem
- PresentationContextItemRQ

  - AbstractSyntaxSubItem
  - TransferSyntaxSubItem
- UserInformationItem

  - MaximumLengthSubItem
  - ImplementationClassUIDSubItem
  - ImplementationVersionNameSubItem
  - AsynchronousOperationsWindowSubItem
  - SCP_SCU_RoleSelectionSubItem
  - SOPClassExtendedNegotiationSubItem
  - SOPClassCommonExtendedNegotiationSubItem
  - UserIdentitySubItemRQ

 **A-ASSOCIATE-AC PDU Items**

 - ApplicationContextItem
 - PresentationContextItemAC

   - TransferSyntaxSubItem
 - UserInformationItem

   - MaximumLengthSubItem
   - ImplementationClassUIDSubItem
   - ImplementationVersionNameSubItem
   - AsynchronousOperationsWindowSubItem
   - SCP_SCU_RoleSelectionSubItem
   - SOPClassExtendedNegotiationSubItem
   - SOPClassCommonExtendedNegotiationSubItem
   - UserIdentitySubItemAC

**P-DATA-TF PDU Items**

- PresentationDataValueItem
"""

import codecs
import logging
from struct import Struct

from pydicom.uid import UID

from pynetdicom.presentation import PresentationContext
from pynetdicom.utils import validate_uid


LOGGER = logging.getLogger('pynetdicom.pdu_items')

# Predefine some structs to make decoding and encoding faster
UCHAR = Struct('B')
UINT2 = Struct('>H')
UINT4 = Struct('>I')

UNPACK_UCHAR = UCHAR.unpack
UNPACK_UINT2 = UINT2.unpack
UNPACK_UINT4 = UINT4.unpack

PACK_UCHAR = UCHAR.pack
PACK_UINT2 = UINT2.pack
PACK_UINT4 = UINT4.pack


class PDUItem(object):
    """Base class for PDU Items and Sub-items.

    See Also
    --------
    pdu.PDU
    """

    def decode(self, bytestream):
        """Decode `bytestream` and use the result to set the field values of
        the PDU item.

        Parameters
        ----------
        bytestream : bytes
            The PDU data to be decoded.
        """
        for (offset, length), attr_name, func, args in self._decoders:
            # Allow us to use None as a `length`
            if length:
                sl = slice(offset, offset + length)
            else:
                sl = slice(offset, None)

            setattr(self, attr_name, func(bytestream[sl], *args))

    @property
    def _decoders(self):
        """Return an iterable of tuples that contain field decoders."""
        raise NotImplementedError

    def encode(self):
        """Return the encoded PDU as bytes.

        Returns
        -------
        bytes
            The encoded PDU.
        """
        bytestream = bytes()
        for attr_name, func, args in self._encoders:
            # If attr_name is None then the field is usually reserved
            if attr_name:
                bytestream += func(getattr(self, attr_name), *args)
            else:
                bytestream += func(*args)

        return bytestream

    @property
    def _encoders(self):
        """Return an iterable of tuples that contain field encoders."""
        raise NotImplementedError

    def __eq__(self, other):
        """Return True if `self` equals `other`."""
        if other is self:
            return True

        if isinstance(other, type(self)):
            # Use the values of the class attributes that get encoded
            self_dict = {
                en[0]: getattr(self, en[0]) for en in self._encoders if en[0]
            }
            other_dict = {
                en[0]: getattr(other, en[0]) for en in other._encoders if en[0]
            }
            return self_dict == other_dict

        return NotImplemented

    @staticmethod
    def _generate_items(bytestream):
        """Yield PDU item data from `bytestream`.

        Parameters
        ----------
        bytestream : bytes
            The encoded PDU variable item data.

        Yields
        ------
        int, bytes
            The variable item's *Item Type* parameter as int, and the item's
            entire encoded data as bytes.

        Notes
        -----
        Can be used with the following PDU items/sub-items:

        - Application Context Item
        - Presentation Context Item (RQ/AC)

          - Abstract Syntax Sub-item
          - Transfer Syntax Sub-item
        - User Information Item

          - Implementation Class UID Sub-item (RQ/AC)
          - Implementation Version Name Sub-item (RQ/AC)
          - Asynchronous Operations Window Sub-item (RQ/AC)
          - SCP/SCU Role Selection Sub-item (RQ/AC)
          - SOP Class Extended Negotiation Sub-item (RQ/AC)
          - SOP Class Common Extended Negotiation Sub-item (RQ/AC)
          - User Identity Sub-item (RQ/AC)

       **Encoding**

        When encoded, PDU item and sub-item data for the above has the
        following structure, taken from various tables in of the DICOM Standard
        (offsets shown with Python indexing). Items are always encoded using
        Big Endian.

        +--------+-------------+-------------+
        | Offset | Length      | Description |
        +========+=============+=============+
        | 0      | 1           | Item type   |
        +--------+-------------+-------------+
        | 1      | 1           | Reserved    |
        +--------+-------------+-------------+
        | 2      | 2           | Item length |
        +--------+-------------+-------------+
        | 4      | Item length | Item data   |
        +--------+-------------+-------------+

        References
        ----------
        * DICOM Standard, Part 8, :dcm:`Section 9.3 <part08/sect_9.3.html>`
        * DICOM Standard, Part 8,
          :dcm:`Section 9.3.1 <part08/sect_9.3.html#sect_9.3.1>`
        """
        offset = 0
        while bytestream[offset:offset + 1]:
            item_type = UNPACK_UCHAR(bytestream[offset:offset + 1])[0]
            item_length = UNPACK_UINT2(bytestream[offset + 2:offset + 4])[0]
            item_data = bytestream[offset:offset + 4 + item_length]
            assert len(item_data) == 4 + item_length
            yield item_type, item_data
            # Move `offset` to the start of the next item
            offset += 4 + item_length

    # Python 2: Classes defining __eq__ should flag themselves as unhashable
    __hash__ = None

    @property
    def item_length(self):
        """Return the item's *Item Length* field value as :class:`int`."""
        raise NotImplementedError

    @property
    def item_type(self):
        """Return the item's *Item Type* field value as :class:`int`."""
        return _TYPE_TO_PDU_ITEM[type(self)]

    def __len__(self):
        """Return the total length of the encoded item as :class:`int`."""
        return 4 + self.item_length

    def __ne__(self, other):
        """Return True if `self` does not equal `other`."""
        return not self == other

    @staticmethod
    def _wrap_bytes(bytestream):
        """Return `bytestream` without changing it."""
        return bytestream

    @staticmethod
    def _wrap_uid_bytes(bytestream):
        """Return `bytestream` without any trailing null padding."""
        if bytestream[-1:] == b'\x00':
            return bytestream[:-1]

        return bytestream

    @staticmethod
    def _wrap_encode_items(items):
        """Return `items` encoded as bytes.

        Parameters
        ----------
        items : list of PDU items
            The items to encode.

        Returns
        -------
        bytes
            The encoded items.
        """
        bytestream = bytes()
        for item in items:
            bytestream += item.encode()

        return bytestream

    @staticmethod
    def _wrap_encode_uid(uid):
        """Return `uid` as bytes encoded using ASCII.

        Each component of Application Context, Abstract Syntax and Transfer
        Syntax UIDs should be encoded as a ISO 646:1990-Basic G0 Set Numeric
        String (characters 0-9), with each component separated by ``.``
        (``0x2e``).

        'ascii' is chosen because this is the codec Python uses for ISO 646.

        Odd-length UIDs should NOT have a trailing padding 0x00 byte to make
        them even length (as per Part 5, Section 9.1: "If ending on an odd
        byte boundary, except when used for network negotiation, one trailing
        padding character...")

        Parameters
        ----------
        uid : pydicom.uid.UID
            The UID to encode using ASCII.
        encode_as_uid : bool, optional
            If False (default) then add no trailing padding null byte for
            odd length UIDs, otherwise add the trailing null byte.

        Returns
        -------
        bytes
            The encoded `uid`.

        References
        ----------
        * DICOM Standard, part 8, :dcm:`Annex F <part08/chapter_F.html>`
        * `Python 2 codecs module
          <https://docs.python.org/3/library/codecs.html#standard-encodings>`_
        * `Python 3 codecs module
          <https://docs.python.org/2/library/codecs.html#standard-encodings>`_
        """
        return codecs.encode(uid, 'ascii')

    def _wrap_generate_items(self, bytestream):
        """Return a list of encoded PDU items generated from `bytestream`."""
        item_list = []
        for item_type, item_bytes in self._generate_items(bytestream):
            item = PDU_ITEM_TYPES[item_type]()
            item.decode(item_bytes)
            item_list.append(item)

        return item_list

    @staticmethod
    def _wrap_pack(value, packer):
        """Return `value` encoded as bytes using `packer`.

        Parameters
        ----------
        value
            The value to encode.
        packer : callable
            A callable function to use to pack the data as bytes. The
            `packer` should return the packed bytes. Example:
            struct.Struct('>I').pack

        Returns
        -------
        bytes
        """
        return packer(value)

    @staticmethod
    def _wrap_unpack(bytestream, unpacker):
        """Return the first value when `unpacker` is run on `bytestream`.

        Parameters
        ----------
        bytestream : bytes
            The encoded data to unpack.
        unpacker : callable
            A callable function to use to unpack the data in `bytestream`. The
            `unpacker` should return a tuple containing unpacked values.
            Example: struct.Struct('>I').unpack.
        """
        return unpacker(bytestream)[0]


## A-ASSOCIATE-RQ and -AC items
class ApplicationContextItem(PDUItem):
    """An Application Context Item.

    An Application Context explicitly defines the set of appliation service
    elements, related options and any other information necessary for the
    inter-working of Application Entities on an association.

    Attributes
    ----------
    application_context_name : pydicom.uid.UID
        The *Application Context Name* field value.
    item_length : int
        The number of bytes from the first byte following the *Item Length*
        field to the last byte of the Item.
    item_type : int
        The *Item Type* field value (``0x10``).

    Notes
    -----
    An Application Context Item requires the following parameters:

       * Item type (1, fixed value, ``0x10``)
       * Item length (1)
       * Application Context Name (1)

    **Application Context Names**

    Application Context Names are OSI Object Identifiers in a numeric form as
    defined by `ISO/IEC 8824-1:2015
    <https://www.iso.org/standard/68350.html>`_.
    They are encoded as an ISO 646:1990-Basic G0 Set
    Numeric String of bytes (characters 0-9), separated by the character
    ``.`` (``0x2e``). No separator or padding shall be present before the
    first digit of the first component or after the last digit of the last
    component.

    Application context names shall not exceed 64 total characters.

    A single DICOM Application Context Name is defined for the current
    version of the DICOM Standard and it is *1.2.840.10008.3.1.1.1*.

    **Encoding**

    When encoded, an Application Context Item has the following structure,
    taken from Part 7, Table 9-12 of the DICOM Standard (offsets shown with
    Python indexing). Items are always encoded using Big Endian. Encoding of
    the Application Context Name parameter follows the rules in Part 8,
    :dcm:`Annex F<part08/chapter_F.html>`

    +--------+-------------+--------------------------+
    | Offset | Length      | Description              |
    +========+=============+==========================+
    | 0      | 1           | Item type                |
    +--------+-------------+--------------------------+
    | 1      | 1           | Reserved                 |
    +--------+-------------+--------------------------+
    | 2      | 2           | Item length              |
    +--------+-------------+--------------------------+
    | 4      | Variable    | Application context name |
    +--------+-------------+--------------------------+

    References
    ----------
    * DICOM Standard, Part 7, :dcm:`Annex A<part07/chapter_A.html>`
    * DICOM Standard, Part 8, :dcm:`Annex F<part08/chapter_F.html>`
    * DICOM Standard, Part 7,
      :dcm:`Annex A.2.1<part07/sect_A.2.html#sect_A.2.1>`
    * DICOM Standard, Part 8,
      :dcm:`Section 9.3.2.1<part08/sect_9.3.2.html#sect_9.3.2.1>`
    * DICOM Standard, Part 8,
      :dcm:`Section 9.3.1<part08/sect_9.3.html#sect_9.3.1>`
    """

    def __init__(self):
        """Initialise a new Application Context Item."""
        self.application_context_name = b'1.2.840.10008.3.1.1.1'

    @property
    def application_context_name(self):
        """Return the item's *Application Context Name* field value as
        :class:`~pydicom.uid.UID`.
        """
        return self._application_context_name

    @application_context_name.setter
    def application_context_name(self, value):
        """Set the *Application Context Name* field value.

        Parameters
        ----------
        value : pydicom.uid.UID, str or bytes
            The value of the Application Context Name's UID
        """
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, UID):
            pass
        elif isinstance(value, str):
            value = UID(value)
        elif isinstance(value, bytes):
            value = UID(value.decode('ascii'))
        else:
            raise TypeError(
                'Application Context Name must be a UID, str or bytes'
            )

        if value is not None and not validate_uid(value):
            LOGGER.error("Invalid 'Application Context Name'")
            raise ValueError("Invalid 'Application Context Name'")

        self._application_context_name = value

    @property
    def _decoders(self):
        """Return an iterable of tuples that contain field decoders.

        Returns
        -------
        list of tuple
            A list of ((offset, length), attr_name, callable, [args]), where

            - offset is the byte offset to start at
            - length is how many bytes to slice (if None then will slice to the
              end of the data),
            - attr_name is the name of the attribute corresponding to the field
            - callable is a decoding function that returns the decoded value,
            - args is a list of arguments to pass callable.
        """
        return [
            ((4, None), 'application_context_name', self._wrap_uid_bytes, [])
        ]

    @property
    def _encoders(self):
        """Return an iterable of tuples that contain field decoders.

        Returns
        -------
        list of tuple
            A list of (attr_name, callable, [args]), where

            - attr_name is the name of the attribute corresponding to the field
            - callable is an encoding function that returns bytes
            - args is a list of arguments to pass callable.
        """
        return [
            ('item_type', PACK_UCHAR, []),
            (None, self._wrap_pack, [0x00, PACK_UCHAR]),
            ('item_length', PACK_UINT2, []),
            ('application_context_name', self._wrap_encode_uid, [])
        ]

    @property
    def item_length(self):
        """Return the item's *Item Length* field value as :class:`int`."""
        return len(self.application_context_name)

    def __str__(self):
        """Return a string representation of the Item."""
        s = '{0!s} ({1!s})\n'.format(
            self.application_context_name,
            self.application_context_name.name
        )
        return s


class PresentationContextItemRQ(PDUItem):
    """A Presentation Context (RQ) Item.

    Presentation Contexts (RQ) Items are used by the association requestor to
    propose Abstract Syntaxes (specifications of data elements with associated
    semantics) and Transfer Syntaxes (sets of encoding rules).

    Attributes
    ----------
    abstract_syntax : pydicom.uid.UID or None.
        The Presentation Context Item's Abstract Syntax (if available).
    abstract_transfer_syntax_sub_items : list of AbstractSyntaxSubItem and TransferSyntaxSubItem
        The *Abstract/Transfer Syntax Sub-Items* field value. The order of the
        items is not guaranteed.
    item_length : int
        The number of bytes from the first byte following the *Item Length*
        field to the last byte of the Item.
    item_type : int
        The *Item Type* field value (``0x20``).
    presentation_context_id : int or None
        The *Presentation Context ID* field value, an odd integer between 1 and
        255.
    transfer_syntax : list of pydicom.uid.UID
        The Presentation Context Item's Transfer Syntax(es) (if available).

    Notes
    -----
    A Presentation Context (RQ) Item requires the following parameters:

       * Item type (1, fixed value, ``0x20``)
       * Item length (1)
       * Presentation context ID (1)
       * Abstract/Transfer Syntax Sub-items (1)

         * Abstract Syntax Sub-item (1)

           * Item type (1, fixed, ``0x30``)
           * Item length (1)
           * Abstract syntax name (1)
         * Transfer Syntax Sub-items (1 or more)

           * Item type (1, fixed, ``0x40``)
           * Item length (1)
           * Transfer syntax name(s) (1 or more)

    **Encoding**

    When encoded, a Presentation Context (RQ) Item has the following structure,
    taken from Part 8, Table 9-13 of the DICOM Standard (offsets shown with
    Python indexing). Items are always encoded using Big Endian.

    +--------+-------------+------------------------------------+
    | Offset | Length      | Description                        |
    +========+=============+====================================+
    | 0      | 1           | Item type                          |
    +--------+-------------+------------------------------------+
    | 1      | 1           | Reserved                           |
    +--------+-------------+------------------------------------+
    | 2      | 2           | Item length                        |
    +--------+-------------+------------------------------------+
    | 4      | 1           | Presentation context ID            |
    +--------+-------------+------------------------------------+
    | 5      | 1           | Reserved                           |
    +--------+-------------+------------------------------------+
    | 6      | 1           | Reserved                           |
    +--------+-------------+------------------------------------+
    | 7      | 1           | Reserved                           |
    +--------+-------------+------------------------------------+
    | 8      | Variable    | Abstract/transfer syntax sub-items |
    +--------+-------------+------------------------------------+

    References
    ----------

    * DICOM Standard, Part 8, :dcm:`Annex B <part08/chapter_B.html>`
    * DICOM Standard, Part 8,
      :dcm:`Section 9.3.2.2 <part08/sect_9.3.2.2.2.html>`
    * DICOM Standard, Part 8,
      :dcm:`Section 9.3.1 <part08/sect_9.3.html#sect_9.3.1>`
    """

    def __init__(self):
        """Initialise a new Presentation Context (RQ) Item."""
        self.presentation_context_id = None
        self.abstract_transfer_syntax_sub_items = []

    def from_primitive(self, primitive):
        """Set the item's values using a Presentation Context primitive.

        Parameters
        ----------
        primitive : presentation.PresentationContext
            The primitive to use to set the Item's field values.
        """
        # Add presentation context ID
        self.presentation_context_id = primitive.context_id

        # Add abstract syntax
        abstract_syntax = AbstractSyntaxSubItem()
        abstract_syntax.abstract_syntax_name = primitive.abstract_syntax
        self.abstract_transfer_syntax_sub_items.append(abstract_syntax)

        # Add transfer syntax(es)
        for syntax in primitive.transfer_syntax:
            transfer_syntax = TransferSyntaxSubItem()
            transfer_syntax.transfer_syntax_name = syntax
            self.abstract_transfer_syntax_sub_items.append(transfer_syntax)

    def to_primitive(self):
        """Return a PresentationContext primitive from the current Item.

        Returns
        -------
        presentation.PresentationContext
            The primitive representation of the current Item.
        """
        context = PresentationContext()
        context.context_id = self.presentation_context_id

        # Add transfer syntax(es)
        for syntax in self.abstract_transfer_syntax_sub_items:
            if isinstance(syntax, TransferSyntaxSubItem):
                context.add_transfer_syntax(syntax.transfer_syntax_name)
            elif isinstance(syntax, AbstractSyntaxSubItem):
                context.abstract_syntax = syntax.abstract_syntax_name

        return context

    @property
    def abstract_syntax(self):
        """Return the *Abstract Syntax*, if available.

        Returns
        -------
        pydicom.uid.UID or None
        """
        for item in self.abstract_transfer_syntax_sub_items:
            if isinstance(item, AbstractSyntaxSubItem):
                return item.abstract_syntax_name

        return None

    @property
    def context_id(self):
        """Return the item's *Presentation Context ID* field value as
        :class:`int`.
        """
        return self.presentation_context_id

    @property
    def _decoders(self):
        """Return an iterable of tuples that contain field decoders.

        Returns
        -------
        list of tuple
            A list of ((offset, length), attr_name, callable, [args]), where

            - offset is the byte offset to start at
            - length is how many bytes to slice (if None then will slice to the
              end of the data),
            - attr_name is the name of the attribute corresponding to the field
            - callable is a decoding function that returns the decoded value,
            - args is a list of arguments to pass callable.
        """
        return [
            (
                (4, 1),
                'presentation_context_id',
                self._wrap_unpack,
                [UNPACK_UCHAR]
            ),
            (
                (8, None),
                'abstract_transfer_syntax_sub_items',
                self._wrap_generate_items,
                []
            )
        ]

    @property
    def _encoders(self):
        """Return an iterable of tuples that contain field decoders.

        Returns
        -------
        list of tuple
            A list of (attr_name, callable, [args]), where

            - attr_name is the name of the attribute corresponding to the field
            - callable is an encoding function that returns bytes
            - args is a list of arguments to pass callable.
        """
        return [
            ('item_type', PACK_UCHAR, []),
            (None, self._wrap_pack, [0x00, PACK_UCHAR]),
            ('item_length', PACK_UINT2, []),
            ('presentation_context_id', PACK_UCHAR, []),
            (None, self._wrap_pack, [0x00, PACK_UCHAR]),
            (None, self._wrap_pack, [0x00, PACK_UCHAR]),
            (None, self._wrap_pack, [0x00, PACK_UCHAR]),
            ('abstract_transfer_syntax_sub_items', self._wrap_encode_items, [])
        ]

    @property
    def item_length(self):
        """Return the item's *Item Length* field value as :class:`int`."""
        length = 4
        for item in self.abstract_transfer_syntax_sub_items:
            length += len(item)

        return length

    def __str__(self):
        """Return a string representation of the Item."""
        s = "Presentation Context (RQ) Item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        s += "  Context ID: {0:d}\n".format(self.context_id)

        for ii in self.abstract_transfer_syntax_sub_items:
            item_str = '{0!s}'.format(ii)
            item_str_list = item_str.split('\n')
            s += '  + {0!s}\n'.format(item_str_list[0])
            for jj in item_str_list[1:-1]:
                s += '    {0!s}\n'.format(jj)

        return s

    @property
    def transfer_syntax(self):
        """Return the *Transfer Syntax(es)*.

        Returns
        -------
        list of pydicom.uid.UID
        """
        syntaxes = []
        for item in self.abstract_transfer_syntax_sub_items:
            if isinstance(item, TransferSyntaxSubItem):
                syntaxes.append(item.transfer_syntax_name)

        return syntaxes


class PresentationContextItemAC(PDUItem):
    """A Presentation Context (AC) Ttem.

    Presentation Contexts (AC) Items are used by the association acceptor to
    signal which Abstract Syntaxes and Transfer Syntaxes have been accepted or
    rejected.

    Attributes
    ----------
    item_length : int
        The number of bytes from the first byte following the *Item Length*
        field to the last byte of the Item.
    item_type : int
        The *Item Type* field value (``0x21``).
    presentation_context_id : int or None
        The *Presentation Context ID* field value, an odd integer between 1 and
        255.
    result_reason : int
        The Presentation Context's *Result/reason* field value.
    transfer_syntax : list of pydicom.uid.UID
        The Presentation Context Item's Transfer Syntax (if available).
    transfer_syntax_sub_item : list of pynetdicom.uid.UID
        The Presentation Context Items' *Transfer Syntax Sub-item* field value.

    Notes
    -----
    A Presentation Context (AC) Item requires the following parameters:

       * Item type (1, fixed value, ``0x21``)
       * Item length (1)
       * Presentation context ID (1)
       * Result/reason (1)
       * Transfer Syntax Sub-item (1)

         * Item type (1, fixed, 0x40)
         * Item length (1)
         * Transfer syntax name (1)

    **Encoding**

    When encoded, a Presentation Context (AC) Item has the following structure,
    taken from Part 8, Table 9-13 of the DICOM Standard (offsets shown with
    Python indexing). Items are always encoded using Big Endian.

    +--------+-------------+------------------------------------+
    | Offset | Length      | Description                        |
    +========+=============+====================================+
    | 0      | 1           | Item type                          |
    +--------+-------------+------------------------------------+
    | 1      | 1           | Reserved                           |
    +--------+-------------+------------------------------------+
    | 2      | 2           | Item length                        |
    +--------+-------------+------------------------------------+
    | 4      | 1           | Presentation context ID            |
    +--------+-------------+------------------------------------+
    | 5      | 1           | Reserved                           |
    +--------+-------------+------------------------------------+
    | 6      | 1           | Result/reason                      |
    +--------+-------------+------------------------------------+
    | 7      | 1           | Reserved                           |
    +--------+-------------+------------------------------------+
    | 8      | Variable    | Transfer syntax sub-item           |
    +--------+-------------+------------------------------------+

    References
    ----------
    * DICOM Standard, Part 8, :dcm:`Section 9.3.3.2<part08/sect_9.3.3.2.html>`
    * DICOM Standard, Part 8,
      :dcm:`Section 9.3.1<part08/sect_9.3.html#sect_9.3.1>`
    """

    def __init__(self):
        """Initialise a new Presentation Context (AC) Item."""
        self.presentation_context_id = None
        self.result_reason = None
        self.transfer_syntax_sub_item = []

    def from_primitive(self, primitive):
        """Set the item's values using a Presentation Context primitive.

        Parameters
        ----------
        primitive : presentation.PresentationContext
            The primitive to use to set the Item's field values.
        """
        # Add presentation context ID
        self.presentation_context_id = primitive.context_id

        # Add reason
        self.result_reason = primitive.result

        # Add transfer syntax
        transfer_syntax = TransferSyntaxSubItem()
        transfer_syntax.transfer_syntax_name = primitive.transfer_syntax[0]
        self.transfer_syntax_sub_item = [transfer_syntax]

    def to_primitive(self):
        """Return a PresentationContext primitive from the current Item.

        Returns
        -------
        presentation.PresentationContext
            The primitive representation of the current Item.
        """
        primitive = PresentationContext()
        primitive.context_id = self.presentation_context_id
        primitive.result = self.result_reason
        if self.transfer_syntax:
            primitive.add_transfer_syntax(self.transfer_syntax)

        return primitive

    @property
    def context_id(self):
        """Return the item's *Presentation Context ID* field value."""
        return self.presentation_context_id

    @property
    def _decoders(self):
        """Return an iterable of tuples that contain field decoders.

        Returns
        -------
        list of tuple
            A list of ((offset, length), attr_name, callable, [args]), where

            - offset is the byte offset to start at
            - length is how many bytes to slice (if None then will slice to the
              end of the data),
            - attr_name is the name of the attribute corresponding to the field
            - callable is a decoding function that returns the decoded value,
            - args is a list of arguments to pass callable.
        """
        return [
            (
                (4, 1),
                'presentation_context_id',
                self._wrap_unpack,
                [UNPACK_UCHAR]
            ),
            (
                (6, 1),
                'result_reason',
                self._wrap_unpack,
                [UNPACK_UCHAR]
            ),
            (
                (8, None),
                'transfer_syntax_sub_item',
                self._wrap_generate_items,
                []
            )
        ]

    @property
    def _encoders(self):
        """Return an iterable of tuples that contain field decoders.

        Returns
        -------
        list of tuple
            A list of (attr_name, callable, [args]), where

            - attr_name is the name of the attribute corresponding to the field
            - callable is an encoding function that returns bytes
            - args is a list of arguments to pass callable.
        """
        return [
            ('item_type', PACK_UCHAR, []),
            (None, self._wrap_pack, [0x00, PACK_UCHAR]),
            ('item_length', PACK_UINT2, []),
            ('presentation_context_id', PACK_UCHAR, []),
            (None, self._wrap_pack, [0x00, PACK_UCHAR]),
            ('result_reason', PACK_UCHAR, []),
            (None, self._wrap_pack, [0x00, PACK_UCHAR]),
            ('transfer_syntax_sub_item', self._wrap_encode_items, [])
        ]

    @property
    def item_length(self):
        """Return the item's *Item Length* field value as :class:`int`."""
        if self.transfer_syntax_sub_item:
            return 4 + len(self.transfer_syntax_sub_item[0])

        return 4

    @property
    def result(self):
        """Return the item's *Result/reason* field value."""
        return self.result_reason

    @property
    def result_str(self):
        """Get a string describing the result."""
        _result = {
            0 : 'Accepted',
            1 : 'User Rejection',
            2 : 'Provider Rejection',
            3 : 'Rejected - Abstract Syntax Not Supported',
            4 : 'Rejected - Transfer Syntax Not Supported'
        }
        return _result[self.result_reason]

    def __str__(self):
        """Return a string representation of the Item."""
        s = "Presentation Context (AC) Item\n"
        s += "  Item type:   0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        s += "  Context ID: {0:d}\n".format(self.presentation_context_id)
        s += "  Result/Reason: {0!s}\n".format(self.result_str)

        if self.transfer_syntax:
            item_str = '{0!s}'.format(self.transfer_syntax.name)
            s += '  +  {0!s}\n'.format(item_str)

        return s

    @property
    def transfer_syntax(self):
        """Return the *Transfer Syntax*, if available.

        Returns
        -------
        pydicom.uid.UID or None
            If no Transfer Syntax Sub-item or an empty Transfer Syntax Sub-item
            has been sent by the Acceptor then returns None, otherwise returns
            the Transfer Syntax Sub-item's transfer syntax UID.
        """
        if self.transfer_syntax_sub_item:
            return self.transfer_syntax_sub_item[0].transfer_syntax_name

        return None

    def _wrap_generate_items(self, bytestream):
        """Return a list of decoded PDU items generated from `bytestream`."""
        item_list = []
        for item_type, item_bytes in self._generate_items(bytestream):
            item = PDU_ITEM_TYPES[item_type]()
            # Transfer Syntax items shall not have their value tested if
            #   not accepted
            if item_type == 0x40 and self.result != 0x00:
                item._skip_validation = True
            item.decode(item_bytes)
            item_list.append(item)

        return item_list


class UserInformationItem(PDUItem):
    """A User Information Item.

    Used by the association requestor and acceptor to include user information
    in the association negotiation.

    Attributes
    ----------
    async_ops_window : pdu_items.AsynchronousOperationsWindowSubItem or None
        The *Asynchronous Operations Window Sub-item* or ``None`` if not
        present.
    common_ext_neg : list of pdu_items.SOPClassCommonExtendedNegotiationSubItem
        The *SOP Class Common Extended Negotiation Sub-item(s)*.
    ext_neg : list of pdu_items.SOPClassExtendedNegotiationSubItem
        The *SOP Class Extended Negotiation Sub-item(s)*.
    implementation_class_uid : pydicom.uid.UID or None
        The implementation class UID from the *Implementation Class UID
        Sub-item*, or ``None`` if not present.
    implementation_version_name : bytes or None
        The implementation version name for the *Implementation Version Name
        Sub-item*, or ``None`` if not present.
    item_length : int
        The number of bytes from the first byte following the *Item Length*
        field to the last byte of the Item.
    item_type : int
        The *Item Type* field value (``0x50``).
    maximum_length : int or None
        The maximum length received value for the *Maximum Length Sub-item*, or
        ``None`` if not present.
    role_selection : list of pdu_items.SCP_SCU_RoleSelectionSubItem
        The *SCP/SCU Role Selection Sub-item(s)*.
    user_identity : pdu_items.UserIdentitySubItemRQ or pdu_items.UserIdentitySubItemAC or None
        The *User Identity Sub-item* (RQ or AC), or ``None`` if not present.

    Notes
    -----
    A User Information Item requires the following parameters:

    * Item type (1, fixed, ``0x50``)
    * Item length (1)
    * User data sub-items (2 or more)

     * Maximum Length Received Sub-item (1)
     * Implementation Class UID Sub-item (1)
     * Optional User Data Sub-items (0 or more)

    **Encoding**

    When encoded, a User Information Item has the following structure,
    taken from Part 8, Table 9-16 of the DICOM Standard (offsets shown with
    Python indexing). Items are always encoded using Big Endian.

    +--------+-------------+------------------------------------+
    | Offset | Length      | Description                        |
    +========+=============+====================================+
    | 0      | 1           | Item type                          |
    +--------+-------------+------------------------------------+
    | 1      | 1           | Reserved                           |
    +--------+-------------+------------------------------------+
    | 2      | 2           | Item length                        |
    +--------+-------------+------------------------------------+
    | 4      | Variable    | User data                          |
    +--------+-------------+------------------------------------+

    References
    ----------

    * DICOM Standard, Part 8,
      :dcm:`Section 9.3.2.3<part08/sect_9.3.2.3.html>`
    * DICOM Standard, Part 8,
      :dcm:`Section 9.3.1<part08/sect_9.3.html#sect_9.3.1>`

    """

    def __init__(self):
        """Initialise a new User Information Item."""
        self.user_data = []

    def from_primitive(self, primitive):
        """Set up the current Item using User Information primitives.

        Parameters
        ----------
        primitive : list of User Information primitives
            Must contain:

            - MaximumLengthNotification
            - ImplementationClassUIDNotification

            May optionally contain one or more:

            - ImplementationVersionnameNotification
            - AsynchronousOperationsWindowNegotiation
            - SCP_SCU_RoleSelectionNegotiation
            - SOPClassExtendedNegotiation
            - SOPClassCommonExtendedNegotiation
            - UserIdentityNegotiation
        """
        for item in primitive:
            self.user_data.append(item.from_primitive())

    def to_primitive(self):
        """Return a list of User Information primitives from the current Item.

        Returns
        -------
        list of User Information primitives
            Must contain:

            - MaximumLengthNotification
            - ImplementationClassUIDNotification

            May optionally contain one or more:

            - ImplementationVersionnameNotification
            - AsynchronousOperationsWindowNegotiation
            - SCP_SCU_RoleSelectionNegotiation
            - SOPClassExtendedNegotiation
            - SOPClassCommonExtendedNegotiation
            - UserIdentityNegotiation
        """
        primitive = []
        for item in self.user_data:
            primitive.append(item.to_primitive())

        return primitive

    @property
    def async_ops_window(self):
        """Return the *Asynchronous Operations Window Sub-item*, if
        available.
        """
        for item in self.user_data:
            if isinstance(item, AsynchronousOperationsWindowSubItem):
                return item

        return None

    @property
    def common_ext_neg(self):
        """Return the *SOP Class Common Extended Negotiation Sub-items*."""
        items = []
        for item in self.user_data:
            if isinstance(item, SOPClassCommonExtendedNegotiationSubItem):
                items.append(item)

        return items

    @property
    def _decoders(self):
        """Return an iterable of tuples that contain field decoders.

        Returns
        -------
        list of tuple
            A list of ((offset, length), attr_name, callable, [args]), where

            - offset is the byte offset to start at
            - length is how many bytes to slice (if None then will slice to the
              end of the data),
            - attr_name is the name of the attribute corresponding to the field
            - callable is a decoding function that returns the decoded value,
            - args is a list of arguments to pass callable.
        """
        return [
            ((4, None), 'user_data', self._wrap_generate_items, [])
        ]

    @property
    def _encoders(self):
        """Return an iterable of tuples that contain field decoders.

        Returns
        -------
        list of tuple
            A list of (attr_name, callable, [args]), where

            - attr_name is the name of the attribute corresponding to the field
            - callable is an encoding function that returns bytes
            - args is a list of arguments to pass callable.
        """
        return [
            ('item_type', PACK_UCHAR, []),
            (None, self._wrap_pack, [0x00, PACK_UCHAR]),
            ('item_length', PACK_UINT2, []),
            ('user_data', self._wrap_encode_items, [])
        ]

    @property
    def ext_neg(self):
        """Return the *SOP Class Extended Negotiation Sub-items*."""
        items = []
        for item in self.user_data:
            if isinstance(item, SOPClassExtendedNegotiationSubItem):
                items.append(item)

        return items

    @property
    def implementation_class_uid(self):
        """Return the item's *Implementation Class UID* field value, if
        available.
        """
        for item in self.user_data:
            if isinstance(item, ImplementationClassUIDSubItem):
                return item.implementation_class_uid

        return None

    @property
    def implementation_version_name(self):
        """Return the item's *Implementation Version Name* field value, if
        available.
        """
        for item in self.user_data:
            if isinstance(item, ImplementationVersionNameSubItem):
                return item.implementation_version_name

        return None

    @property
    def item_length(self):
        """Return the item's *Item Length* field value as :class:`int`."""
        length = 0
        for item in self.user_data:
            length += len(item)

        return length

    @property
    def maximum_length(self):
        """Return the item's *Maximum Length Received* field value, if
        available.
        """
        for item in self.user_data:
            if isinstance(item, MaximumLengthSubItem):
                return item.maximum_length_received

        return None

    @property
    def role_selection(self):
        """Return the *SCP/SCU Role Selection Sub-items*.

        Returns
        -------
        dict
            The SCP/SCU Role Selection items as {item.uid : item}.
        """
        roles = {}
        for item in self.user_data:
            if isinstance(item, SCP_SCU_RoleSelectionSubItem):
                roles[item.uid] = item

        return roles

    def __str__(self):
        """Return a string representation of the Item."""
        s = " User information item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d}\n".format(self.item_length)
        s += "  User Data:\n "

        for item in self.user_data:
            s += "  {0!s}".format(item)

        return s

    @property
    def user_identity(self):
        """Return the *User Identity Sub-item*, if available."""
        for item in self.user_data:
            if isinstance(item, (UserIdentitySubItemRQ,
                                 UserIdentitySubItemAC)):
                return item

        return None


## Presentation Context Item sub-items
class AbstractSyntaxSubItem(PDUItem):
    """An Abstract Syntax Sub-item.

    An Abstract Syntax is the specification of data elements with associated
    semantics. In particular it allows communicating Application Entities to
    negotiate an agreed set of DICOM Data Elements and/or Information Object
    Class definitions.

    Attributes
    ----------
    abstract_syntax_name : pydicom.uid.UID or None
        The *Abstract Syntax Name* field value.
    item_length : int
        The number of bytes from the first byte following the *Item Length*
        field to the last byte of the Item.
    item_type : int
        The *Item Type* field value (``0x30``).

    Notes
    -----
    An Abstract Syntax Sub-item requires the following parameters:

       * Item type (1, fixed value, ``0x30``)
       * Item length (1)
       * Abstract syntax name (1)

    **Abstract Syntax Names**

    Abstract Syntax Names are OSI Object Identifiers in a numeric form as
    defined by ISO 8824. They may be either DICOM registered or privately
    defined. They're encoded as an ISO 646:1990-Basic G0 Set Numeric String of
    bytes (characters 0-9), separated by the character ``.`` (``0x2e``) and
    shall not exceed 64 total characters. No separator or padding shall be
    present before the first digit of the first component or after the last
    digit of the last component.

    **Encoding**

    When encoded, an Abstract Syntax Item has the following structure,
    taken from Part 8, Table 9-14 of the DICOM Standard (offsets shown with
    Python indexing). Items are
    always encoded using Big Endian. Encoding of the Abstract Syntax Name
    parameter follows the rules in Part 8,
    :dcm:`Annex F <part08/chapter_F.html>`.

    +--------+-------------+------------------------------------+
    | Offset | Length      | Description                        |
    +========+=============+====================================+
    | 0      | 1           | Item type                          |
    +--------+-------------+------------------------------------+
    | 1      | 1           | Reserved                           |
    +--------+-------------+------------------------------------+
    | 2      | 2           | Item length                        |
    +--------+-------------+------------------------------------+
    | 4      | Variable    | Abstract syntax name               |
    +--------+-------------+------------------------------------+

    References
    ----------

    * DICOM Standard, Part 8,
      :dcm:`Annex B <part08/chapter_B.html>`
    * `ISO/IEC 8824-1:2015 <https://www.iso.org/standard/68350.html>`_
    * DICOM Standard, Part 8,
      :dcm:`Annex F <part08/chapter_F.html>`
    * DICOM Standard, Part 8,
      :dcm:`Section 9.3.2.2.1 <part08/sect_9.3.2.2.html#sect_9.3.2.2.1>`
    * DICOM Standard, Part 8,
      :dcm:`Section 9.3.1<part08/sect_9.3.html#sect_9.3.1>`
    """

    def __init__(self):
        """Initialise a new Abstract Syntax Item."""
        self.abstract_syntax_name = None

    @property
    def abstract_syntax(self):
        """Return the item's *Abstract Syntax Name* field value."""
        return self.abstract_syntax_name

    @property
    def abstract_syntax_name(self):
        """Return the item's *Abstract Syntax Name* field value."""
        return self._abstract_syntax_name

    @abstract_syntax_name.setter
    def abstract_syntax_name(self, value):
        """Set the *Abstract Syntax Name* field value.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The value for the Abstract Syntax Name.
        """
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, UID):
            pass
        elif isinstance(value, str):
            value = UID(value)
        elif isinstance(value, bytes):
            value = UID(value.decode('ascii'))
        elif value is None:
            pass
        else:
            raise TypeError(
                'Abstract Syntax Name ust be a pydicom.uid.UID, str or bytes'
            )

        if value is not None and not validate_uid(value):
            LOGGER.error("Abstract Syntax Name is an invalid UID")
            raise ValueError("Abstract Syntax Name is an invalid UID")

        self._abstract_syntax_name = value

    @property
    def _decoders(self):
        """Return an iterable of tuples that contain field decoders.

        Returns
        -------
        list of tuple
            A list of ((offset, length), attr_name, callable, [args]), where

            - offset is the byte offset to start at
            - length is how many bytes to slice (if None then will slice to the
              end of the data),
            - attr_name is the name of the attribute corresponding to the field
            - callable is a decoding function that returns the decoded value,
            - args is a list of arguments to pass callable.
        """
        return [
            ((4, None), 'abstract_syntax_name', self._wrap_uid_bytes, [])
        ]

    @property
    def _encoders(self):
        """Return an iterable of tuples that contain field decoders.

        Returns
        -------
        list of tuple
            A list of (attr_name, callable, [args]), where

            - attr_name is the name of the attribute corresponding to the field
            - callable is an encoding function that returns bytes
            - args is a list of arguments to pass callable.
        """
        return [
            ('item_type', PACK_UCHAR, []),
            (None, self._wrap_pack, [0x00, PACK_UCHAR]),
            ('item_length', PACK_UINT2, []),
            ('abstract_syntax_name', self._wrap_encode_uid, [])
        ]

    @property
    def item_length(self):
        """Return the item's *Item Length* field value as :class:`int`."""
        if self.abstract_syntax_name:
            return len(self.abstract_syntax_name)

        return 0

    def __str__(self):
        """Return a string representation of the Item."""
        s = "Abstract Syntax Sub-item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        s += '  Syntax name: ={0!s}\n'.format(self.abstract_syntax.name)

        return s


class TransferSyntaxSubItem(PDUItem):
    """A Transfer Syntax Sub-item.

    A Transfer Syntax is a set of encoding rules able to unambiguously
    represent the data elements defined by one or more Abstract Syntaxes.
    In particular, it allows communicating Application Entities to agree on the
    encoding techniques they are able to support (e.g. byte ordering,
    compression, etc).

    Attributes
    ----------
    item_length : int
        The number of bytes from the first byte following the *Item Length*
        field to the last byte of the Item.
    item_type : int
        The *Item Type* field value (``0x40``).
    transfer_syntax : pydicom.uid.UID or None
        The *Transfer Syntax Name* field value.

    Notes
    -----
    A Transfer Syntax Sub-item requires the following parameters:

       * Item type (1, fixed value, ``0x40``)
       * Item length (1)
       * Transfer syntax name (1 or more)

    **Transfer Syntax Names**

    Transfer Syntax Names are OSI Object Identifiers in a numeric form as
    defined by ISO 8824. They may be either DICOM registered or privately
    defined. They're encoded as an ISO 646:1990-Basic G0 Set Numeric String of
    bytes (characters 0-9), separated by the character ``.`` (``0x2e``) and
    shall not exceed 64 total characters. No separator or padding shall be
    present before the first digit of the first component or after the last
    digit of the last component.

    **Encoding**

    When encoded, a Transfer Syntax Item has the following structure,
    taken from Part 8, Table 9-15 of the DICOM Standard (offsets shown with
    Python indexing). Items are
    always encoded using Big Endian. Encoding of the Transfer Syntax Name
    parameter follows the rules in Part 8,
    :dcm:`Annex F <part08/chapter_F.html>`.

    +--------+-------------+------------------------------------+
    | Offset | Length      | Description                        |
    +========+=============+====================================+
    | 0      | 1           | Item type                          |
    +--------+-------------+------------------------------------+
    | 1      | 1           | Reserved                           |
    +--------+-------------+------------------------------------+
    | 2      | 2           | Item length                        |
    +--------+-------------+------------------------------------+
    | 4      | Variable    | Transfer syntax name               |
    +--------+-------------+------------------------------------+

    References
    ----------

    * DICOM Standard, Part 8,
      :dcm:`Annex B <part08/chapter_B.html>`
    * `ISO/IEC 8824-1:2015 <https://www.iso.org/standard/68350.html>`_
    * DICOM Standard, Part 8,
      :dcm:`Annex F <part08/chapter_F.html>`
    * DICOM Standard, Part 8,
      :dcm:`Section 9.3.2.2.2 <part08/sect_9.3.2.2.2.html>`
    * DICOM Standard, Part 8,
      :dcm:`Section 9.3.1<part08/sect_9.3.html#sect_9.3.1>`
    """

    def __init__(self):
        """Initialise a new Abstract Syntax Item."""
        # Should not be validated if Presentation Context was rejected
        self._skip_validation = False
        self.transfer_syntax_name = None

    @property
    def _decoders(self):
        """Return an iterable of tuples that contain field decoders.

        Returns
        -------
        list of tuple
            A list of ((offset, length), attr_name, callable, [args]), where

            - offset is the byte offset to start at
            - length is how many bytes to slice (if None then will slice to the
              end of the data),
            - attr_name is the name of the attribute corresponding to the field
            - callable is a decoding function that returns the decoded value,
            - args is a list of arguments to pass callable.
        """
        return [
            ((4, None), 'transfer_syntax_name', self._wrap_uid_bytes, [])
        ]

    @property
    def _encoders(self):
        """Return an iterable of tuples that contain field decoders.

        Returns
        -------
        list of tuple
            A list of (attr_name, callable, [args]), where

            - attr_name is the name of the attribute corresponding to the field
            - callable is an encoding function that returns bytes
            - args is a list of arguments to pass callable.
        """
        return [
            ('item_type', PACK_UCHAR, []),
            (None, self._wrap_pack, [0x00, PACK_UCHAR]),
            ('item_length', PACK_UINT2, []),
            ('transfer_syntax_name', self._wrap_encode_uid, [])
        ]

    @property
    def item_length(self):
        """Return the item's *Item Length* field value as :class:`int`."""
        if self.transfer_syntax_name:
            return len(self.transfer_syntax_name)

        return 0

    def __str__(self):
        """Return a string representation of the Item."""
        s = "Transfer syntax sub item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        if self.transfer_syntax_name:
            s += '  Transfer syntax name: ={0!s}\n'.format(
                self.transfer_syntax_name.name
            )

        return s

    @property
    def transfer_syntax(self):
        """Return the item's *Transfer Syntax Name* field value."""
        return self.transfer_syntax_name

    @property
    def transfer_syntax_name(self):
        """Return the item's *Transfer Syntax Name* field value."""
        return self._transfer_syntax_name

    @transfer_syntax_name.setter
    def transfer_syntax_name(self, value):
        """Set the *Transfer Syntax Name* field value.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The value for the Transfer Syntax Name
        """
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, UID):
            pass
        elif isinstance(value, str):
            value = UID(value)
        elif isinstance(value, bytes):
            value = UID(value.decode('ascii'))
        elif value is None:
            pass
        else:
            raise TypeError('Transfer syntax must be a pydicom.uid.UID, '
                            'bytes or str')

        if self._skip_validation:
            self._transfer_syntax_name = value or None
            return

        if value is not None and not validate_uid(value):
            LOGGER.error("Transfer Syntax Name is an invalid UID")
            raise ValueError("Transfer Syntax Name is an invalid UID")

        self._transfer_syntax_name = value or None


## User Information Item sub-items
class MaximumLengthSubItem(PDUItem):
    """A Maximum Length Sub-item.

    The Maximum Length Sub-item allows the receivers to limit the size of the
    Presentation Data Values List parameters of each P-DATA PDU.

    Attributes
    ----------
    item_length : int
        The number of bytes from the first byte following the *Item Length*
        field to the last byte of the Item.
    item_type : int
        The *Item Type* field value (``0x51``).
    maximum_length_received : int
        The *Maximum Length Received* field value.

    Notes
    -----
    A Maximum Length Sub-item requires the following parameters:

       * Item type (1, fixed, ``0x51``)
       * Item length (1)
       * Maximum length received (1)

    **Encoding**

    When encoded, a Maximum Length Sub-item has the following structure,
    taken from Table D.1-1 of the DICOM Standard (offsets shown with Python
    indexing). Items are
    always encoded using Big Endian.

    +--------+-------------+------------------------------------+
    | Offset | Length      | Description                        |
    +========+=============+====================================+
    | 0      | 1           | Item type                          |
    +--------+-------------+------------------------------------+
    | 1      | 1           | Reserved                           |
    +--------+-------------+------------------------------------+
    | 2      | 2           | Item length                        |
    +--------+-------------+------------------------------------+
    | 4      | 4           | Maximum length received            |
    +--------+-------------+------------------------------------+

    References
    ----------

    * DICOM Standard, Part 8,
      :dcm:`Annex D.1 <part08/chapter_D.html#sect_D.1.1>`
    * DICOM Standard, Part 8,
      :dcm:`Section 9.3.1<part08/sect_9.3.html#sect_9.3.1>`
    """

    def __init__(self):
        """Initialise a new Maximum Length Item."""
        self.maximum_length_received = None

    def from_primitive(self, primitive):
        """Set the item's values using a Maximum Length `primitive`.

        Parameters
        ----------
        primitive : pdu_primitives.MaximumLengthNotification
            The primitive to use to set the Item's field values.
        """
        self.maximum_length_received = primitive.maximum_length_received

    def to_primitive(self):
        """Return a Maximum Length primitive from the current Item.

        Returns
        -------
        pdu_primitives.MaximumLengthNotification
            The primitive representation of the current Item.
        """
        from pynetdicom.pdu_primitives import MaximumLengthNotification

        primitive = MaximumLengthNotification()
        primitive.maximum_length_received = self.maximum_length_received

        return primitive

    @property
    def _decoders(self):
        """Return an iterable of tuples that contain field decoders.

        Returns
        -------
        list of tuple
            A list of ((offset, length), attr_name, callable, [args]), where

            - offset is the byte offset to start at
            - length is how many bytes to slice (if None then will slice to the
              end of the data),
            - attr_name is the name of the attribute corresponding to the field
            - callable is a decoding function that returns the decoded value,
            - args is a list of arguments to pass callable.
        """
        return [
            (
                (4, None),
                'maximum_length_received',
                self._wrap_unpack,
                [UNPACK_UINT4]
            )
        ]

    @property
    def _encoders(self):
        """Return an iterable of tuples that contain field decoders.

        Returns
        -------
        list of tuple
            A list of (attr_name, callable, [args]), where

            - attr_name is the name of the attribute corresponding to the field
            - callable is an encoding function that returns bytes
            - args is a list of arguments to pass callable.
        """
        return [
            ('item_type', PACK_UCHAR, []),
            (None, self._wrap_pack, [0x00, PACK_UCHAR]),
            ('item_length', PACK_UINT2, []),
            ('maximum_length_received', PACK_UINT4, [])
        ]

    @property
    def item_length(self):
        """Return the item's *Item Length* field value as :class:`int`."""
        return 4

    def __str__(self):
        """Return a string representation of the Item."""
        s = "Maximum length Sub-item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        s += "  Maximum length received: {0:d}\n".format(
            self.maximum_length_received)
        return s


class ImplementationClassUIDSubItem(PDUItem):
    """An Implementation Class UID Sub-item.

    The Implementation Class UID Sub-item allows communicating Application
    Entities to identify each other at Association establishment.

    Attributes
    ----------
    implementation_class_uid : pydicom.uid.UID or None
        The *Implementation Class UID* field value.
    item_length : int
        The number of bytes from the first byte following the *Item Length*
        field to the last byte of the Item.
    item_type : int
        The *Item Type* field value (``0x52``).

    Notes
    -----
    An Implementation Class UID Sub-item requires the following parameters:

       * Item type (1, fixed, ``0x52``)
       * Item length (1)
       * Implementation Class UID (1)

    **Encoding**

    When encoded, an Implementation Class UID Sub-item has the following
    structure, taken from Tables D.3-1 and D.3-2 (offsets shown with
    Python indexing). Items are always encoded using Big Endian.

    +--------+-------------+------------------------------------+
    | Offset | Length      | Description                        |
    +========+=============+====================================+
    | 0      | 1           | Item type                          |
    +--------+-------------+------------------------------------+
    | 1      | 1           | Reserved                           |
    +--------+-------------+------------------------------------+
    | 2      | 2           | Item length                        |
    +--------+-------------+------------------------------------+
    | 4      | Variable    | Implementation class UID           |
    +--------+-------------+------------------------------------+

    References
    ----------

    * DICOM Standard, Part 7,
      :dcm:`Annex D.3.3.2 <part07/sect_D.3.3.2.html>`
    * DICOM Standard, Part 8,
      :dcm:`Section 9.3.1<part08/sect_9.3.html#sect_9.3.1>`
    """

    def __init__(self):
        """Initialise a new Implementation Class UID Item."""
        self.implementation_class_uid = None

    def from_primitive(self, primitive):
        """Set the item's values using an Implementation Identification
        primitive.

        Parameters
        ----------
        primitive : pdu_primitives.ImplementationClassUIDNotification
            The primitive to use to set the Item's field values.
        """
        self.implementation_class_uid = primitive.implementation_class_uid

    def to_primitive(self):
        """Return an Implementation Identification primitive from the current
        Item.

        Returns
        -------
        pdu_primitives.ImplementationClassUIDNotification
            The primitive representation of the current Item.
        """
        from pynetdicom.pdu_primitives import (
            ImplementationClassUIDNotification
        )

        primitive = ImplementationClassUIDNotification()
        primitive.implementation_class_uid = self.implementation_class_uid

        return primitive

    @property
    def _decoders(self):
        """Return an iterable of tuples that contain field decoders.

        Returns
        -------
        list of tuple
            A list of ((offset, length), attr_name, callable, [args]), where

            - offset is the byte offset to start at
            - length is how many bytes to slice (if None then will slice to the
              end of the data),
            - attr_name is the name of the attribute corresponding to the field
            - callable is a decoding function that returns the decoded value,
            - args is a list of arguments to pass callable.
        """
        return [
            ((4, None), 'implementation_class_uid', self._wrap_uid_bytes, [])
        ]

    @property
    def _encoders(self):
        """Return an iterable of tuples that contain field decoders.

        Returns
        -------
        list of tuple
            A list of (attr_name, callable, [args]), where

            - attr_name is the name of the attribute corresponding to the field
            - callable is an encoding function that returns bytes
            - args is a list of arguments to pass callable.
        """
        return [
            ('item_type', PACK_UCHAR, []),
            (None, self._wrap_pack, [0x00, PACK_UCHAR]),
            ('item_length', PACK_UINT2, []),
            ('implementation_class_uid', self._wrap_encode_uid, [])
        ]

    @property
    def implementation_class_uid(self):
        """Return the item's *Implementation Class UID* field value as UID."""
        return self._implementation_class_uid

    @implementation_class_uid.setter
    def implementation_class_uid(self, value):
        """Set the *Implementation Class UID* field value.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The value to set.
        """
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, UID):
            pass
        elif isinstance(value, str):
            value = UID(value)
        elif isinstance(value, bytes):
            value = UID(value.decode('ascii'))
        elif value is None:
            pass
        else:
            raise TypeError('implementation_class_uid must be str, bytes '
                            'or UID')

        if value is not None and not validate_uid(value):
            LOGGER.error("Implementation Class UID is an invalid UID")
            raise ValueError("Implementation Class UID is an invalid UID")

        self._implementation_class_uid = value

    @property
    def item_length(self):
        """Return the item's *Item Length* field value as :class:`int`."""
        if self.implementation_class_uid:
            return len(self.implementation_class_uid)

        return 0

    def __str__(self):
        """Return a string representation of the Item."""
        s = "Implementation Class UID Sub-item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        s += "  Implementation class UID: '{0!s}'\n".format(
            self.implementation_class_uid)

        return s


class ImplementationVersionNameSubItem(PDUItem):
    """An Implementation Version Name Sub-item.

    The Implementation Version Name Sub-item allows communicating Application
    Entities to identify each other at Association establishment.

    Attributes
    ----------
    implementation_version_name : bytes or None
        The *Implementation Version Name* field value, 1 to 16 characters.
    item_length : int
        The number of bytes from the first byte following the *Item Length*
        field to the last byte of the Item.
    item_type : int
        The *Item Type* field value (``0x55``).

    Notes
    -----
    The Implementation Class UID Sub Item requires the following parameters:

       * Item type (1, fixed, ``0x55``)
       * Item length (1)
       * Implementation version name (1)

    **Implementation Version Name**

    The Implementation Version Name shall be encoded as a string of 1 to 16
    ISO 646:1990 (basic G0 set) characters.

    **Encoding**

    When encoded, an Implementation Version Name Sub-item has the following
    structure, taken from Tables D.3-3 and D.3-4 of the DICOM Standard (offsets
    shown with
    Python indexing). Items are always encoded using Big Endian.

    +--------+-------------+------------------------------------+
    | Offset | Length      | Description                        |
    +========+=============+====================================+
    | 0      | 1           | Item type                          |
    +--------+-------------+------------------------------------+
    | 1      | 1           | Reserved                           |
    +--------+-------------+------------------------------------+
    | 2      | 2           | Item length                        |
    +--------+-------------+------------------------------------+
    | 4      | Variable    | Implementation version name        |
    +--------+-------------+------------------------------------+

    References
    ----------

    * DICOM Standard, Part 7,
      :dcm:`Annex D.3.3.2 <part07/sect_D.3.3.2.html>`
    * DICOM Standard, Part 8,
      :dcm:`Section 9.3.1<part08/sect_9.3.html#sect_9.3.1>`
    """

    def __init__(self):
        """Initialise a new Implementation Version Name Item."""
        self.implementation_version_name = None

    def from_primitive(self, primitive):
        """Set the item's values using an Implementation Identification
        primitive.

        Parameters
        ----------
        primitive : pdu_primitives.ImplementationVersionNameNotification
            The primitive to use to set the Item's field values.
        """
        self.implementation_version_name = (
            primitive.implementation_version_name
        )

    def to_primitive(self):
        """Return an Implementation Identification primitive from the current
        Item.

        Returns
        -------
        pdu_primitives.ImplementationVersionNameNotification
            The primitive representation of the current Item.
        """
        from pynetdicom.pdu_primitives import (
            ImplementationVersionNameNotification
        )

        prim = ImplementationVersionNameNotification()
        prim.implementation_version_name = self.implementation_version_name

        return prim

    @property
    def _decoders(self):
        """Return an iterable of tuples that contain field decoders.

        Returns
        -------
        list of tuple
            A list of ((offset, length), attr_name, callable, [args]), where

            - offset is the byte offset to start at
            - length is how many bytes to slice (if None then will slice to the
              end of the data),
            - attr_name is the name of the attribute corresponding to the field
            - callable is a decoding function that returns the decoded value,
            - args is a list of arguments to pass callable.
        """
        return [
            ((4, None), 'implementation_version_name', self._wrap_bytes, [])
        ]

    @property
    def _encoders(self):
        """Return an iterable of tuples that contain field decoders.

        Returns
        -------
        list of tuple
            A list of (attr_name, callable, [args]), where

            - attr_name is the name of the attribute corresponding to the field
            - callable is an encoding function that returns bytes
            - args is a list of arguments to pass callable.
        """
        return [
            ('item_type', PACK_UCHAR, []),
            (None, self._wrap_pack, [0x00, PACK_UCHAR]),
            ('item_length', PACK_UINT2, []),
            ('implementation_version_name', self._wrap_bytes, [])
        ]

    @property
    def implementation_version_name(self):
        """Return the item's *Implementation Version Name* field value."""
        return self._implementation_version_name

    @implementation_version_name.setter
    def implementation_version_name(self, value):
        """Set the *Implementation Version Name* field value."""
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, str):
            value = codecs.encode(value, 'ascii')

        self._implementation_version_name = value

    @property
    def item_length(self):
        """Return the item's *Item Length* field value as :class:`int`."""
        if self.implementation_version_name:
            return len(self.implementation_version_name)

        return 0

    def __str__(self):
        """Return a string representation of the Item."""
        s = "Implementation Version Name Sub-item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        s += "  Implementation version name: {0!s}\n".format(
            self.implementation_version_name)

        return s


class AsynchronousOperationsWindowSubItem(PDUItem):
    """An Asynchronous Operations Window Sub-item.

    Represents the Asynchronous Operations Window Sub Item used in
    A-ASSOCIATE-RQ and A-ASSOCIATE-AC PDUs.

    Attributes
    ----------
    item_length : int
        The number of bytes from the first byte following the *Item Length*
        field to the last byte of the Item.
    item_type : int
        The *Item Type* field value (``0x53``).
    maximum_number_operations_invoked : int or None
        The 'Maximum Number Operations Invoked' field value.
    maximum_number_operations_performed : int or None
        The *Maximum Number Operations Performed* field value.

    Notes
    -----
    An Asynchronous Operations Window Sub-item requires the following
    parameters:

       * Item type (1, fixed, ``0x53``)
       * Item length (1)
       * Maximum number of operations invoked (1)
       * Maximum number of operations performed (1)

    **Encoding**

    When encoded, an Asynchronous Operations Window Sub-item has the following
    structure, taken from Tables D.3-7 and D.3-8 of the DICOM Standard (offsets
    shown with
    Python indexing). Items are always encoded using Big Endian.

    +--------+-------------+-------------------------------------+
    | Offset | Length      | Description                         |
    +========+=============+=====================================+
    | 0      | 1           | Item type                           |
    +--------+-------------+-------------------------------------+
    | 1      | 1           | Reserved                            |
    +--------+-------------+-------------------------------------+
    | 2      | 2           | Item length                         |
    +--------+-------------+-------------------------------------+
    | 4      | 2           | Maximum number operations invoked   |
    +--------+-------------+-------------------------------------+
    | 6      | 2           | Maximum number operations performed |
    +--------+-------------+-------------------------------------+

    References
    ----------

    * DICOM Standard, Part 7,
      :dcm:`Annex D.3.3.3 <part07/sect_D.3.3.3.html>`
    * DICOM Standard, Part 8,
      :dcm:`Section 9.3.1<part08/sect_9.3.html#sect_9.3.1>`
    """

    def __init__(self):
        """Initialise a new Asynchronous Operations Window Item."""
        self.maximum_number_operations_invoked = None
        self.maximum_number_operations_performed = None

    def from_primitive(self, primitive):
        """Set the item's values using an Asynchronous Operations Window
        primitive.

        Parameters
        ----------
        primitive : pdu_primitives.AsynchronousOperationsWindowNegotiation
            The primitive to use to set the Item's field values.
        """
        self.maximum_number_operations_invoked = (
            primitive.maximum_number_operations_invoked
        )
        self.maximum_number_operations_performed = (
            primitive.maximum_number_operations_performed
        )

    def to_primitive(self):
        """Return an Asynchronous Operations Window primitive from the current
        Item.

        Returns
        -------
        pdu_primitives.AsynchronousOperationsWindowNegotiation
            The primitive representation of the current Item.
        """
        from pynetdicom.pdu_primitives import (
            AsynchronousOperationsWindowNegotiation
        )

        primitive = AsynchronousOperationsWindowNegotiation()
        primitive.maximum_number_operations_invoked = (
            self.maximum_number_operations_invoked
        )
        primitive.maximum_number_operations_performed = (
            self.maximum_number_operations_performed
        )

        return primitive

    @property
    def _decoders(self):
        """Return an iterable of tuples that contain field decoders.

        Returns
        -------
        list of tuple
            A list of ((offset, length), attr_name, callable, [args]), where

            - offset is the byte offset to start at
            - length is how many bytes to slice (if None then will slice to the
              end of the data),
            - attr_name is the name of the attribute corresponding to the field
            - callable is a decoding function that returns the decoded value,
            - args is a list of arguments to pass callable.
        """
        return [
            (
                (4, 2),
                'maximum_number_operations_invoked',
                self._wrap_unpack,
                [UNPACK_UINT2]
            ),
            (
                (6, 2),
                'maximum_number_operations_performed',
                self._wrap_unpack,
                [UNPACK_UINT2]
            )
        ]

    @property
    def _encoders(self):
        """Return an iterable of tuples that contain field decoders.

        Returns
        -------
        list of tuple
            A list of (attr_name, callable, [args]), where

            - attr_name is the name of the attribute corresponding to the field
            - callable is an encoding function that returns bytes
            - args is a list of arguments to pass callable.
        """
        return [
            ('item_type', PACK_UCHAR, []),
            (None, self._wrap_pack, [0x00, PACK_UCHAR]),
            ('item_length', PACK_UINT2, []),
            ('maximum_number_operations_invoked', PACK_UINT2, []),
            ('maximum_number_operations_performed', PACK_UINT2, [])
        ]

    @property
    def item_length(self):
        """Return the item's *Item Length* field value as :class:`int`."""
        return 4

    @property
    def max_operations_invoked(self):
        """Return the item's *Maximum Number Operations Invoked* field value.
        """
        return self.maximum_number_operations_invoked

    @property
    def max_operations_performed(self):
        """Return the item's *Maximum Number Operations Performed* field value.
        """
        return self.maximum_number_operations_performed

    def __str__(self):
        """Return a string representation of the Item."""
        s = "Asynchronous Operation Window Sub-item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        s += "  Max. number of operations invoked: {0:d}\n".format(
            self.maximum_number_operations_invoked)
        s += "  Max. number of operations performed: {0:d}\n".format(
            self.maximum_number_operations_performed)

        return s


class SCP_SCU_RoleSelectionSubItem(PDUItem):
    """An SCP/SCU Role Selection Sub-item.

    An SCU/SCU Role Selection Sub-item allows communicating Application
    Entities to negotiate the roles in which they will server for each SOP
    Class or Meta SOP Class supported on the association.

    Attributes
    ----------
    item_length : int
        The number of bytes from the first byte following the *Item Length*
        field to the last byte of the Item.
    item_type : int
        The *Item Type* field value (``0x54``).
    scu_role : int or None
        The *SCU Role* field value, 0 or 1 or None.
    scp_role : int or None
        The *SCP Role* field value, 0 or 1 or None.
    sop_class_uid : pydicom.uid.UID or None
        The *SOP Class UID* field value.
    uid_length : int
        The *UID Length* field value.

    Notes
    -----
    An SCP/SCU Role Selection Sub-item requires the following parameters:

       * Item type (1, fixed, ``0x51``)
       * Item length (1)
       * UID length (1)
       * SOP Class UID (1)
       * SCU role (1)
       * SCP role (1)

    **Encoding**

    When encoded, an SCP/SCU Role Section Sub-item has the following
    structure, taken from Tables D.3-9 and D.3-10 of the DICOM Standard
    (offsets shown with
    Python indexing). Items are always encoded using Big Endian.
    The SOP Class UID parameter is encoded as a UID as per the rules in
    Part 5, Section 9.1 (ie NO trailing padding null byte).

    +----------------+----------+------------------------------------+
    | Offset         | Length   | Description                        |
    +================+==========+====================================+
    | 0              | 1        | Item type                          |
    +----------------+----------+------------------------------------+
    | 1              | 1        | Reserved                           |
    +----------------+----------+------------------------------------+
    | 2              | 2        | Item length                        |
    +----------------+----------+------------------------------------+
    | 4              | 2        | UID length                         |
    +----------------+----------+------------------------------------+
    | 6              | Variable | SOP class UID                      |
    +----------------+----------+------------------------------------+
    | 6 + UID length | 1        | SCP role                           |
    +----------------+----------+------------------------------------+
    | 7 + UID length | 1        | SCU role                           |
    +----------------+----------+------------------------------------+

    References
    ----------

    * DICOM Standard, Part 5,
      :dcm:`Section 9.1<part05/chapter_9.html#sect_9.1>`
    * DICOM Standard, Part 7,
      :dcm:`Annex D.3.3.4 <part07/sect_D.3.3.4.html>`
    * DICOM Standard, Part 8,
      :dcm:`Section 9.3.1<part08/sect_9.3.html#sect_9.3.1>`
    """

    def __init__(self):
        """Initialise a new SCP/SCU Role Selection Item."""
        self._uid_length = None
        self.sop_class_uid = None
        self.scu_role = None
        self.scp_role = None

    def from_primitive(self, primitive):
        """Set the item's values using an SCP/SCU Role Selection primitive.

        Parameters
        ----------
        primitive : pdu_primitives.SCP_SCU_RoleSelectionNegotiation
            The primitive to use to set the Item's field values.
        """
        self.sop_class_uid = primitive.sop_class_uid
        if primitive.scu_role is not None:
            self.scu_role = int(primitive.scu_role)
        else:
            self.scu_role = False

        if primitive.scp_role is not None:
            self.scp_role = int(primitive.scp_role)
        else:
            self.scp_role = False

    def to_primitive(self):
        """Return an SCP/SCU Role Selection primitive from the current Item.

        Returns
        -------
        pdu_primitives.SCP_SCU_RoleSelectionNegotiation
            The primitive representation of the current Item.
        """
        from pynetdicom.pdu_primitives import SCP_SCU_RoleSelectionNegotiation

        primitive = SCP_SCU_RoleSelectionNegotiation()
        primitive.sop_class_uid = self.sop_class_uid
        primitive.scu_role = bool(self.scu_role)
        primitive.scp_role = bool(self.scp_role)

        return primitive

    @property
    def _decoders(self):
        """Yield tuples that contain field decoders.

        We use a generator because some of the offset values aren't known until
        a precursor field has been decoded.

        Yields
        -------
        tuple
            A list of ((offset, length), attr_name, callable, [args]), where

            - offset is the byte offset to start at
            - length is how many bytes to slice (if None then will slice to the
              end of the data),
            - attr_name is the name of the attribute corresponding to the field
            - callable is a decoding function that returns the decoded value,
            - args is a list of arguments to pass callable.
        """
        yield (
            (4, 2),
            '_uid_length',
            self._wrap_unpack,
            [UNPACK_UINT2]
        )

        yield (
            (6, self._uid_length),
            'sop_class_uid',
            self._wrap_uid_bytes,
            []
        )

        yield (
            (6 + self._uid_length, 1),
            'scu_role',
            self._wrap_unpack,
            [UNPACK_UCHAR]
        )

        yield (
            (7 + self._uid_length, 1),
            'scp_role',
            self._wrap_unpack,
            [UNPACK_UCHAR]
        )

    @property
    def _encoders(self):
        """Return an iterable of tuples that contain field decoders.

        Returns
        -------
        list of tuple
            A list of (attr_name, callable, [args]), where

            - attr_name is the name of the attribute corresponding to the field
            - callable is an encoding function that returns bytes
            - args is a list of arguments to pass callable.
        """
        return [
            ('item_type', PACK_UCHAR, []),
            (None, self._wrap_pack, [0x00, PACK_UCHAR]),
            ('item_length', PACK_UINT2, []),
            ('uid_length', PACK_UINT2, []),
            ('sop_class_uid', self._wrap_encode_uid, []),
            ('scu_role', PACK_UCHAR, []),
            ('scp_role', PACK_UCHAR, [])
        ]

    @property
    def item_length(self):
        """Return the item's *Item Length* field value as :class:`int`."""
        return 4 + self.uid_length

    @property
    def scu(self):
        """Return the item's *SCU Role* field value."""
        return self.scu_role

    @property
    def scu_role(self):
        """Return the item's *SCU Role* field value."""
        return self._scu_role

    @scu_role.setter
    def scu_role(self, value):
        """Set the *SCU Role* field value."""
        # pylint: disable=attribute-defined-outside-init
        if value not in [0, 1, None]:
            raise ValueError('SCU Role parameter value must be 0 or 1')
        else:
            self._scu_role = value

    @property
    def scp(self):
        """Return the item's *SCP Role* field value."""
        return self.scp_role

    @property
    def scp_role(self):
        """Return the item's *SCP Role* field value."""
        return self._scp_role

    @scp_role.setter
    def scp_role(self, value):
        """Set the *SCP Role* field value."""
        # pylint: disable=attribute-defined-outside-init
        if value not in [0, 1, None]:
            raise ValueError('SCP Role parameter value must be 0 or 1')
        else:
            self._scp_role = value

    @property
    def sop_class_uid(self):
        """Return the item's *SOP Class UID* field value."""
        return self._sop_class_uid

    @sop_class_uid.setter
    def sop_class_uid(self, value):
        """Set the SOP class uid."""
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, bytes):
            value = UID(value.decode('ascii'))
        elif isinstance(value, str):
            value = UID(value)
        elif value is None:
            pass
        else:
            raise TypeError('sop_class_uid must be str, bytes or '
                            'pydicom.uid.UID')

        if value is not None and not validate_uid(value):
            LOGGER.error("SOP Class UID is an invalid UID")
            raise ValueError("SOP Class UID is an invalid UID")

        self._sop_class_uid = value

    def __str__(self):
        """Return a string representation of the Item."""
        s = "SCP/SCU Role Selection Sub-item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        s += "  UID length: {0:d} bytes\n".format(self.uid_length)
        s += "  SOP Class UID: {0!s}\n".format(self.uid.name)
        s += "  SCU Role: {0:d}\n".format(self.scu)
        s += "  SCP Role: {0:d}\n".format(self.scp)

        return s

    @property
    def uid(self):
        """Return the item's *SOP Class UID* field value."""
        return self.sop_class_uid

    @property
    def uid_length(self):
        """Return the *UID Length* parameter value."""
        if self.sop_class_uid:
            return len(self.sop_class_uid)

        return 0


class SOPClassExtendedNegotiationSubItem(PDUItem):
    """A SOP Class Extended Negotiation Sub-item.

    A SOP Class Extended Negotation Sub-item allows peer Application Entities
    to exchange application information defined by specific Service Class
    specifications.

    Attributes
    ----------
    item_length : int
        The number of bytes from the first byte following the *Item Length*
        field to the last byte of the Item.
    item_type : int
        The *Item Type* field value (``0x56``).
    service_class_application_information : bytes
        The *Service Class Application Information* field value.
    sop_class_uid : uid
        The *SOP Class UID* field value.
    sop_class_uid_length : int
        The *SOP Class UID Length* field value.

    Notes
    -----
    A SOP Class Extended Negotiation Sub-item requires the following
    parameters:

       * Item type (1, fixed, ``0x56``)
       * Item length (1)
       * SOP Class UID length (1)
       * SOP Class UID (1)
       * Service class application information

    **Encoding**

    When encoded, a SOP Class Extended Negotiation Sub-item has the following
    structure, taken from Table D.3-11 (offsets shown with
    Python indexing). Items are always encoded using Big Endian.
    The SOP Class UID parameter is encoded as a UID as per the rules in
    Part 5, Section 9.1 (ie NO trailing padding null byte).


    +----------------+-------------+------------------------------------+
    | Offset         | Length      | Description                        |
    +================+=============+====================================+
    | 0              | 1           | Item type                          |
    +----------------+-------------+------------------------------------+
    | 1              | 1           | Reserved                           |
    +----------------+-------------+------------------------------------+
    | 2              | 2           | Item length                        |
    +----------------+-------------+------------------------------------+
    | 4              | 2           | SOP class UID length               |
    +----------------+-------------+------------------------------------+
    | 6              | Variable    | SOP class UID                      |
    +----------------+-------------+------------------------------------+
    | 6 + UID length | Variable    | Service class application info     |
    +----------------+-------------+------------------------------------+

    References
    ----------

    * DICOM Standard, Part 5,
      :dcm:`Section 9.1<part05/chapter_9.html#sect_9.1>`
    * DICOM Standard, Part 7,
      :dcm:`Annex D.3.3.5 <part07/sect_D.3.3.5.html>`
    * DICOM Standard, Part 8,
      :dcm:`Section 9.3.1<part08/sect_9.3.html#sect_9.3.1>`
    """

    def __init__(self):
        """Initialise a new SOP Class Extended Negotiation Item."""
        self._sop_class_uid_length = None
        self.sop_class_uid = None
        self.service_class_application_information = None

    def from_primitive(self, primitive):
        """Set the item's values using a SOP Class Extended Negotiation
        primitive.

        Parameters
        ----------
        primitive : pdu_primitives.SOPClassExtendedNegotiation
            The primitive to use to set the Item's field values.
        """
        self.sop_class_uid = primitive.sop_class_uid
        self.service_class_application_information = (
            primitive.service_class_application_information
        )

    def to_primitive(self):
        """Return a SOP Class Extended Negotiation primitive from the current
        Item.

        Returns
        -------
        pdu_primitives.SOPClassExtendedNegotiation
            The primitive representation of the current Item.
        """
        from pynetdicom.pdu_primitives import SOPClassExtendedNegotiation

        primitive = SOPClassExtendedNegotiation()
        primitive.sop_class_uid = self.sop_class_uid
        primitive.service_class_application_information = (
            self.service_class_application_information
        )

        return primitive

    @property
    def app_info(self):
        """Return the item's *Service Class Application Information* field
        value.
        """
        return self.service_class_application_information

    @property
    def _decoders(self):
        """Yield tuples that contain field decoders.

        We use a generator because some of the offset values aren't known until
        a precursor field has been decoded.

        Yields
        -------
        tuple
            A list of ((offset, length), attr_name, callable, [args]), where

            - offset is the byte offset to start at
            - length is how many bytes to slice (if None then will slice to the
              end of the data),
            - attr_name is the name of the attribute corresponding to the field
            - callable is a decoding function that returns the decoded value,
            - args is a list of arguments to pass callable.
        """
        yield (
            (4, 2),
            '_sop_class_uid_length',
            self._wrap_unpack,
            [UNPACK_UINT2]
        )

        yield (
            (6, self._sop_class_uid_length),
            'sop_class_uid',
            self._wrap_uid_bytes,
            []
        )

        yield (
            (6 + self._sop_class_uid_length, None),
            'service_class_application_information',
            self._wrap_bytes,
            []
        )

    @property
    def _encoders(self):
        """Return an iterable of tuples that contain field decoders.

        Returns
        -------
        list of tuple
            A list of (attr_name, callable, [args]), where

            - attr_name is the name of the attribute corresponding to the field
            - callable is an encoding function that returns bytes
            - args is a list of arguments to pass callable.
        """
        return [
            ('item_type', PACK_UCHAR, []),
            (None, self._wrap_pack, [0x00, PACK_UCHAR]),
            ('item_length', PACK_UINT2, []),
            ('sop_class_uid_length', PACK_UINT2, []),
            ('sop_class_uid', self._wrap_encode_uid, []),
            ('service_class_application_information', self._wrap_bytes, [])
        ]

    @property
    def item_length(self):
        """Return the item's *Item Length* field value as :class:`int`."""
        length = 2 + self.sop_class_uid_length
        if self.service_class_application_information:
            return length + len(self.service_class_application_information)

        return length

    @property
    def sop_class_uid(self):
        """Return the item's *SOP Class UID* field value."""
        return self._sop_class_uid

    @sop_class_uid.setter
    def sop_class_uid(self, value):
        """Set the *SOP Class UID* field value."""
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, bytes):
            value = UID(value.decode('ascii'))
        elif isinstance(value, str):
            value = UID(value)
        elif value is None:
            pass
        else:
            raise TypeError('sop_class_uid must be str, bytes or '
                            'pydicom.uid.UID')

        if value is not None and not validate_uid(value):
            LOGGER.error("SOP Class UID is an invalid UID")
            raise ValueError("SOP Class UID is an invalid UID")

        self._sop_class_uid = value

    @property
    def sop_class_uid_length(self):
        """Return the item's *SOP Class UID Length* field value."""
        if self.sop_class_uid:
            return len(self.sop_class_uid)

        return 0

    def __str__(self):
        """Return a string representation of the Item."""
        s = "SOP Class Extended Negotiation Sub-item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        s += "  SOP class UID length: {0:d} bytes\n".format(
            self.sop_class_uid_length)
        s += "  SOP class: ={0!s}\n".format(self.sop_class_uid.name)

        # Python 2 compatibility
        app_info = self.service_class_application_information
        if isinstance(app_info, str):
            app_info = "\\x" + "\\x".join(
                ['{0:02x}'.format(ord(x)) for x in app_info])

        s += "  Service class application information: {0!s}\n".format(
            app_info)

        return s

    @property
    def uid(self):
        """Return the item's *SOP Class UID* field value."""
        return self.sop_class_uid


# Overriden _generate_items, _wrap_generate_items
class SOPClassCommonExtendedNegotiationSubItem(PDUItem):
    """A SOP Class Common Extended Negotiation Sub-item.

    A SOP Class Common Extended Negotiation Sub-item allows Application
    Entities to exchange application information in a generic non-Service
    class specific form.

    Attributes
    ----------
    item_length : int
        The number of bytes from the first byte following the *Item Length*
        field to the last byte of the Item.
    item_type : int
        The *Item Type* field value (``0x57``).
    sub_item_version : int
        The *Sub Item Version* field value.
    sop_class_uid_length : int
        The *SOP Class UID Length* field value.
    sop_class_uid : pydicom.uid.UID
        The *SOP Class UID* field value.
    service_class_uid_length : int
        The *Service Class UID Length* field value.
    service_class_uid : pydicom.uid.UID
        The *Service Class UID* field value.
    related_general_sop_class_identification_length : int
        The *Related General SOP Class Identification Length* field value.
    related_general_sop_class_identification : list of pydicom.uid.UID
        The UIDs in the *Related General SOP Class UID Identification* field
        value.

    Notes
    -----
    A SOP Class Common Extended Negotiation Sub-item requires the following
    parameters:

       * Item type (1, fixed, ``0x57``)
       * Sub-item version (1, fixed, ``0x00``)
       * Item length (1)
       * SOP class UID length (1)
       * SOP class UID (1)
       * Service class UID length (1)
       * Service class UID (1)
       * Related general SOP class identification length (1)
       * Related general SOP class identification sub fields (0 or more)

         * Related general SOP class UID length (1)
         * Related general SOP class UID (1)

    **Encoding**

    When encoded, a SOP Class Common Extended Negotiation Sub-item has the
    following structure, taken from Table D.3-12 (offsets shown
    with Python indexing). Items are always encoded using Big Endian.
    The SOP Class UID, Service Class UID and the UIDs in the Related General
    SOP Class Identification parameters are encoded as UIDs as per the rules in
    Part 5, Section 9.1 (ie NO trailing padding null byte).

    +----------------------+----------+-------------------------------------+
    | Offset               | Length   | Description                         |
    +======================+==========+=====================================+
    | 0                    | 1        | Item type                           |
    +----------------------+----------+-------------------------------------+
    | 1                    | 1        | Sub item version                    |
    +----------------------+----------+-------------------------------------+
    | 2                    | 2        | Item length                         |
    +----------------------+----------+-------------------------------------+
    | 4                    | 2        | SOP class UID length                |
    +----------------------+----------+-------------------------------------+
    | 6                    | Variable | SOP class UID                       |
    +----------------------+----------+-------------------------------------+
    | 6 + SOP UID length   | 2        | Service class UID length            |
    +----------------------+----------+-------------------------------------+
    | 8 + SOP UID length   | Variable | Service class UID                   |
    +----------------------+----------+-------------------------------------+
    | 8 + SOP UID length   | 2        | Related general SOP class ID length |
    | + Service UID length |          |                                     |
    +----------------------+----------+-------------------------------------+
    | 10 + SOP UID length  | Variable | Related general SOP class ID        |
    | + Service UID length |          |                                     |
    +----------------------+----------+-------------------------------------+

    The Related General SOP Class Identification field is made up of a number
    of sub-fields with the following structure, taken from Table D.3-13.

    +--------+-------------+--------------------------------------+
    | Offset | Length      | Description                          |
    +========+=============+======================================+
    | 0      | 2           | Related general SOP class UID length |
    +--------+-------------+--------------------------------------+
    | 2      | Variable    | Related general SOP class UID        |
    +--------+-------------+--------------------------------------+

    References
    ----------

    * DICOM Standard, Part 5,
      :dcm:`Section 9.1<part05/chapter_9.html#sect_9.1>`
    * DICOM Standard, Part 7,
      :dcm:`Annex D.3.3.6 <part07/sect_D.3.3.6.html>`
    * DICOM Standard, Part 8,
      :dcm:`Section 9.3.1<part08/sect_9.3.html#sect_9.3.1>`
    """

    def __init__(self):
        """Initialise a new Implementation Version Name Item."""
        self.sub_item_version = 0x00
        self._sop_length = None
        self.sop_class_uid = None
        self._service_length = None
        self.service_class_uid = None
        self.related_general_sop_class_identification = []

    def from_primitive(self, primitive):
        """Set the item's values using a SOP Class Common Extended Negotiation
        primitive.

        Parameters
        ----------
        primitive : pdu_primitives.SOPClassCommonExtendedNegotiation
            The primitive to use to set the Item's field values.
        """
        self.sop_class_uid = primitive.sop_class_uid
        self.service_class_uid = primitive.service_class_uid
        self.related_general_sop_class_identification = (
            primitive.related_general_sop_class_identification
        )

    def to_primitive(self):
        """Return an SOP Class Common Extended Negotiation primitive from the
        current Item.

        Returns
        -------
        pdu_primitives.SOPClassCommonExtendedNegotiation
            The primitive representation of the current Item.
        """
        from pynetdicom.pdu_primitives import SOPClassCommonExtendedNegotiation

        primitive = SOPClassCommonExtendedNegotiation()
        primitive.sop_class_uid = self.sop_class_uid
        primitive.service_class_uid = self.service_class_uid
        primitive.related_general_sop_class_identification = (
            self.related_general_sop_class_identification
        )

        return primitive

    @property
    def _decoders(self):
        """Yield tuples that contain field decoders.

        We use a generator because some of the offset values aren't known until
        a precursor field has been decoded.

        Yields
        -------
        tuple
            A list of ((offset, length), attr_name, callable, [args]), where

            - offset is the byte offset to start at
            - length is how many bytes to slice (if None then will slice to the
              end of the data),
            - attr_name is the name of the attribute corresponding to the field
            - callable is a decoding function that returns the decoded value,
            - args is a list of arguments to pass callable.
        """
        yield (
            (4, 2),
            '_sop_length',
            self._wrap_unpack,
            [UNPACK_UINT2]
        )

        yield (
            (6, self._sop_length),
            'sop_class_uid',
            self._wrap_uid_bytes,
            []
        )

        yield (
            (6 + self._sop_length, 2),
            '_service_length',
            self._wrap_unpack,
            [UNPACK_UINT2]
        )

        yield (
            (8 + self._sop_length, self._service_length),
            'service_class_uid',
            self._wrap_uid_bytes,
            []
        )

        yield (
            (10 + self._sop_length + self._service_length, None),
            'related_general_sop_class_identification',
            self._generate_items,
            []
        )

    @property
    def _encoders(self):
        """Return an iterable of tuples that contain field decoders.

        Returns
        -------
        list of tuple
            A list of (attr_name, callable, [args]), where

            - attr_name is the name of the attribute corresponding to the field
            - callable is an encoding function that returns bytes
            - args is a list of arguments to pass callable.
        """
        return [
            ('item_type', PACK_UCHAR, []),
            ('sub_item_version', PACK_UCHAR, []),
            ('item_length', PACK_UINT2, []),
            ('sop_class_uid_length', PACK_UINT2, []),
            ('sop_class_uid', self._wrap_encode_uid, []),
            ('service_class_uid_length', PACK_UINT2, []),
            ('service_class_uid', self._wrap_encode_uid, []),
            (
                'related_general_sop_class_identification_length',
                PACK_UINT2, []
            ),
            ('related_general_sop_class_identification', self._wrap_list, []),
            # (None, )
        ]

    @staticmethod
    def _generate_items(bytestream):
        """Yield Related General SOP Class UIDs from `bytestream`.

        Parameters
        ----------
        bytestream : bytes
            The encoded related general SOP Class UID data.

        Yields
        ------
        pydicom.uid.UID
            The related general SOP Class UIDs.

        Notes
        -----
       **Encoding**

        The Related General SOP Class Identification field is made up of a
        number of sub-fields with the following structure, taken from
        Table D.3-13.

        +--------+-------------+--------------------------------------+
        | Offset | Length      | Description                          |
        +========+=============+======================================+
        | 0      | 2           | Related general SOP class UID length |
        +--------+-------------+--------------------------------------+
        | 2      | Variable    | Related general SOP class UID        |
        +--------+-------------+--------------------------------------+

        References
        ----------
        * DICOM Standard, Part 7,
           :dcm:`Annex D.3.3.6 <part07/sect_D.3.3.6.html>`
        * DICOM Standard, Part 8,
           :dcm:`Section 9.3.1<part08/sect_9.3.html#sect_9.3.1>`
        """
        offset = 0
        while bytestream[offset:offset + 1]:
            uid_length = UNPACK_UINT2(bytestream[offset:offset + 2])[0]
            raw_uid = bytestream[offset + 2:offset + 2 + uid_length]
            stripped_uid_length = uid_length
            if raw_uid[-1:] == b'\x00':
                raw_uid = raw_uid[:-1]
                stripped_uid_length = uid_length - 1

            uid = UID(raw_uid.decode('ascii'))
            assert len(uid) == stripped_uid_length
            yield uid
            offset += 2 + uid_length

    @property
    def item_length(self):
        """Return the item's *Item Length* field value as :class:`int`."""
        return (2 + self.sop_class_uid_length +
                2 + self.service_class_uid_length +
                2 + self.related_general_sop_class_identification_length)

    @property
    def related_general_sop_class_identification(self):
        """Return the item's *Related General SOP Class Identification* field
        value.
        """
        return self._related_general_sop_class_identification

    @related_general_sop_class_identification.setter
    def related_general_sop_class_identification(self, value_list):
        """Set the *Related General SOP Class Identification* field value.

        Parameters
        ----------
        value_list : list of pydicom.uid.UID
            A list of UIDs.
        """
        # pylint: disable=attribute-defined-outside-init
        self._related_general_sop_class_identification = []

        for value in value_list:
            if isinstance(value, bytes):
                value = UID(value.decode('ascii'))
            elif isinstance(value, str):
                value = UID(value)
            else:
                raise TypeError('related_general_sop_class_identification '
                                'must be str, bytes or pydicom.uid.UID')

            if value is not None and not validate_uid(value):
                msg = (
                    "Related General SOP Class Identification contains "
                    "an invalid UID"
                )
                LOGGER.error(msg)
                raise ValueError(msg)

            self._related_general_sop_class_identification.append(value)

    @property
    def related_general_sop_class_identification_length(self):
        """Return the item's *Related General SOP Class Identification Length*
        field value.
        """
        length = 0
        for uid in self._related_general_sop_class_identification:
            length += 2 + len(uid)

        return length

    @property
    def sop_class_uid(self):
        """Return the item's *SOP Class UID* field value."""
        return self._sop_class_uid

    @sop_class_uid.setter
    def sop_class_uid(self, value):
        """Set the *SOP Class UID* field value."""
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, bytes):
            value = UID(value.decode('ascii'))
        elif isinstance(value, str):
            value = UID(value)
        elif value is None:
            pass
        else:
            raise TypeError('sop_class_uid must be str, bytes or '
                            'pydicom.uid.UID')

        if value is not None and not validate_uid(value):
            LOGGER.error("SOP Class UID is an invalid UID")
            raise ValueError("SOP Class UID is an invalid UID")

        self._sop_class_uid = value

    @property
    def sop_class_uid_length(self):
        """Return the item's *SOP Class UID Length* field value."""
        if self.sop_class_uid:
            return len(self.sop_class_uid)

        return 0

    @property
    def service_class_uid(self):
        """Return the item's *Service Class UID* field value."""
        return self._service_class_uid

    @service_class_uid.setter
    def service_class_uid(self, value):
        """Set the *Service Class UID* field value."""
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, bytes):
            value = UID(value.decode('ascii'))
        elif isinstance(value, str):
            value = UID(value)
        elif value is None:
            pass
        else:
            raise TypeError('service_class_uid must be str, bytes or '
                            'pydicom.uid.UID')

        if value is not None and not validate_uid(value):
            LOGGER.error("Service Class UID is an invalid UID")
            raise ValueError("Service Class UID is an invalid UID")

        self._service_class_uid = value

    @property
    def service_class_uid_length(self):
        """Return the item's *Service Class UID Length* field value."""
        if self.service_class_uid:
            return len(self.service_class_uid)

        return 0

    def __str__(self):
        """Return a string representation of the Item."""
        s = "SOP Class Common Extended Negotiation Sub-item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        s += "  SOP class UID length: {0:d} bytes\n".format(
            self.sop_class_uid_length)
        s += "  SOP class: ={0!s}\n".format(self.sop_class_uid.name)
        s += "  Service class UID length: {0:d} bytes\n".format(
            self.service_class_uid_length)
        s += (
            "  Service class UID: ={0!s}\n".format(self.service_class_uid.name)
        )
        s += "  Related general SOP class ID length: {0:d} bytes\n".format(
            self.related_general_sop_class_identification_length)
        s += "  Related general SOP class ID(s):\n"

        for uid in self.related_general_sop_class_identification:
            s += "    ={0!s} ({1!s})\n".format(uid, uid.name)

        return s

    def _wrap_generate_items(self, bytestream):
        """Return a list of UID items generated from `bytestream`."""
        item_list = []
        for uid in self._generate_items(bytestream):
            item_list.append(uid)

        return item_list

    def _wrap_list(self, uid_list):
        """Return `uid_list` encoded as bytes.

        Parameters
        ----------
        uid_list : list of pydicom.uid.UID
            A list of UIDs.

        Returns
        -------
        bytes
            The UID list encoded as (for each UID in the list):

            - length of the UID, encoded as 2-byte unsigned int
            - UID, as ASCII encoded bytes
        """
        bytestream = bytes()
        for uid in uid_list:
            # UIDs are to be encoded as per normal Part 5 UID encoding rules
            #   (i.e. that odd length UIDs be null padded to even length)
            # Related general SOP class UID length
            bytestream += PACK_UINT2(len(uid))
            # Related general SOP class UID
            bytestream += self._wrap_encode_uid(uid)

        return bytestream


class UserIdentitySubItemRQ(PDUItem):
    """A User Identity (RQ) Sub-item.

    A User Identity (RQ) Sub-item is used to notify the association acceptor of
    the user identity of the requestor.

    Attributes
    ----------
    item_length : int
        The number of bytes from the first byte following the *Item Length*
        field to the last byte of the Item.
    item_type : int
        The *Item Type* field value (``0x58``).
    positive_response_requested : int
        The *Positive Response Requested* field value.
    primary_field : bytes
        The *Primary Field* field value.
    primary_field_length : int
        The *Primary Field Length* field value.
    secondary_field : bytes
        The *Secondary Field* field value.
    secondary_field_length : int
        The *Secondary Field Length* field value.
    user_identity_type : {1, 2, 3, 4}
        The *User Identity Type* field value.

    Notes
    -----
    A User Identity (RQ) Sub-item requires the following parameters:

    * Item type (1, fixed, ``0x58``)
    * Item length (1)
    * User identity type (1)
    * Positive response requested (1)
    * Primary field length (1)
    * Primary field (1)
    * Secondary field length (1)
    * Secondary field (only if user identity type = 2)

    **Encoding**

    When encoded, a User Identity (RQ) Sub-item has the following
    structure, taken from Tables D.3-14 of the DICOM Standard (offsets shown
    with
    Python indexing). Items are always encoded using Big Endian.

    +---------------------------+----------+-----------------------------+
    | Offset                    | Length   | Description                 |
    +===========================+==========+=============================+
    | 0                         | 1        | Item type                   |
    +---------------------------+----------+-----------------------------+
    | 1                         | 1        | Reserved                    |
    +---------------------------+----------+-----------------------------+
    | 2                         | 2        | Item length                 |
    +---------------------------+----------+-----------------------------+
    | 4                         | 1        | User identity type          |
    +---------------------------+----------+-----------------------------+
    | 5                         | 1        | Positive response requested |
    +---------------------------+----------+-----------------------------+
    | 6                         | 2        | Primary field length        |
    +---------------------------+----------+-----------------------------+
    | 8                         | Variable | Primary field               |
    +---------------------------+----------+-----------------------------+
    | 8 + Primary field length  | 2        | Secondary field length      |
    +---------------------------+----------+-----------------------------+
    | 10 + Primary field length | Variable | Secondary field             |
    +---------------------------+----------+-----------------------------+

    References
    ----------
    * DICOM Standard, Part 7,
      :dcm:`Annex D.3.3.7 <part07/sect_D.3.3.7.html>`
    * DICOM Standard, Part 8,
      :dcm:`Section 9.3.1<part08/sect_9.3.html#sect_9.3.1>`
    """

    def __init__(self):
        """Initialise a new User Identity (RQ) Item."""
        self.user_identity_type = None
        self.positive_response_requested = None
        self._primary_length = None
        self.primary_field = None
        self._secondary_length = None
        self.secondary_field = b''

    def from_primitive(self, primitive):
        """Set the item's values using an User Identity primitive.

        Parameters
        ----------
        primitive : pdu_primitives.UserIdentityNegotiation
            The primitive to use to set the Item's field values.
        """
        self.user_identity_type = primitive.user_identity_type
        self.positive_response_requested = (
            int(primitive.positive_response_requested)
        )
        self.primary_field = primitive.primary_field
        self.secondary_field = primitive.secondary_field

    def to_primitive(self):
        """Return an  User Identity primitive from the current Item.

        Returns
        -------
        pdu_primitives.UserIdentityNegotiation
            The primitive representation of the current Item.
        """
        from pynetdicom.pdu_primitives import UserIdentityNegotiation

        primitive = UserIdentityNegotiation()
        primitive.user_identity_type = self.user_identity_type
        primitive.positive_response_requested = (
            bool(self.positive_response_requested)
        )
        primitive.primary_field = self.primary_field
        primitive.secondary_field = self.secondary_field

        return primitive

    @property
    def _decoders(self):
        """Yield tuples that contain field decoders.

        We use a generator because some of the offset values aren't known until
        a precursor field has been decoded.

        Yields
        -------
        tuple
            A list of ((offset, length), attr_name, callable, [args]), where

            - offset is the byte offset to start at
            - length is how many bytes to slice (if None then will slice to the
              end of the data),
            - attr_name is the name of the attribute corresponding to the field
            - callable is a decoding function that returns the decoded value,
            - args is a list of arguments to pass callable.
        """
        yield (
            (4, 1),
            'user_identity_type',
            self._wrap_unpack,
            [UNPACK_UCHAR]
        )

        yield (
            (5, 1),
            'positive_response_requested',
            self._wrap_unpack,
            [UNPACK_UCHAR]
        )

        yield (
            (6, 2),
            '_primary_length',
            self._wrap_unpack,
            [UNPACK_UINT2]
        )

        yield (
            (8, self._primary_length),
            'primary_field',
            self._wrap_bytes,
            []
        )

        yield (
            (10 + self._primary_length, None),
            'secondary_field',
            self._wrap_bytes,
            []
        )

    @property
    def _encoders(self):
        """Return an iterable of tuples that contain field decoders.

        Returns
        -------
        list of tuple
            A list of (attr_name, callable, [args]), where

            - attr_name is the name of the attribute corresponding to the field
            - callable is an encoding function that returns bytes
            - args is a list of arguments to pass callable.
        """
        return [
            ('item_type', PACK_UCHAR, []),
            (None, self._wrap_pack, [0x00, PACK_UCHAR]),
            ('item_length', PACK_UINT2, []),
            ('user_identity_type', PACK_UCHAR, []),
            ('positive_response_requested', PACK_UCHAR, []),
            ('primary_field_length', PACK_UINT2, []),
            ('primary_field', self._wrap_bytes, []),
            ('secondary_field_length', PACK_UINT2, []),
            ('secondary_field', self._wrap_bytes, [])
        ]

    @property
    def id_type(self):
        """Return the item's *User Identity Type* field value."""
        return self.user_identity_type

    @property
    def id_type_str(self):
        """Return a string description of the *User Identity Type* field."""
        _types = {
            1 : 'Username',
            2 : 'Username/Password',
            3 : 'Kerberos',
            4 : 'SAML',
            5 : 'JSON Web Token',
        }

        return _types[self.user_identity_type]

    @property
    def item_length(self):
        """Return the item's *Item Length* field value as :class:`int`."""
        return 6 + self.primary_field_length + self.secondary_field_length

    @property
    def primary(self):
        """Return the item's *Primary Field* field value."""
        return self.primary_field

    @property
    def primary_field_length(self):
        """Return the item's *Primary Field Length* field value."""
        if self.primary_field:
            return len(self.primary_field)

        return 0

    @property
    def response_requested(self):
        """Return the item's *Positive Response Requested* field value as bool.
        """
        if self.positive_response_requested is not None:
            return bool(self.positive_response_requested)

        return None

    @property
    def secondary(self):
        """Return the item's *Secondary Field* field value."""
        return self.secondary_field

    @property
    def secondary_field_length(self):
        """Return the item's *Secondary Field Length* field value."""
        if self.secondary_field:
            return len(self.secondary_field)

        return 0

    def __str__(self):
        """Return a string representation of the Item."""
        s = "User Identity (RQ) Sub-item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        s += "  User identity type: {0:d}\n".format(self.user_identity_type)
        s += "  Positive response requested: {0:d}\n".format(
            self.positive_response_requested)
        s += "  Primary field length: {0:d} bytes\n".format(
            self.primary_field_length)
        s += "  Primary field: {0!s}\n".format(self.primary_field)

        if self.user_identity_type == 0x02:
            s += "  Secondary field length: {0:d} bytes\n".format(
                self.secondary_field_length)
            s += "  Secondary field: {0!s}\n".format(self.secondary_field)
        else:
            s += "  Secondary field length: (not used)\n"
            s += "  Secondary field: (not used)\n"

        return s


class UserIdentitySubItemAC(PDUItem):
    """A User Identity (AC) Sub-item.

    A User Identity (AC) Sub-item is used to response with the server identity
    to the association requestor.

    Attributes
    ----------
    item_length : int
        The number of bytes from the first byte following the *Item Length*
        field to the last byte of the Item.
    item_type : int
        The *Item Type* field value (``0x59``).
    server_response_length : int
        The *Server Response Length* field value.
    server_response : bytes
        The *Server Response* field value.

    Notes
    -----
    A User Identity (RQ) Sub-item requires the following parameters:

    * Item type (1, fixed, ``0x59``)
    * Item length (1)
    * Server response length (1)
    * Server response (1)

    **Encoding**

    When encoded, a User Identity (AC) Sub-item has the following
    structure, taken from Tables D.3-15 of the DICOM Standard (offsets shown
    with
    Python indexing). Items are always encoded using Big Endian.

    +-----------+----------+-----------------------------+
    | Offset    | Length   | Description                 |
    +===========+==========+=============================+
    | 0         | 1        | Item type                   |
    +-----------+----------+-----------------------------+
    | 1         | 1        | Reserved                    |
    +-----------+----------+-----------------------------+
    | 2         | 2        | Item length                 |
    +-----------+----------+-----------------------------+
    | 4         | 2        | Server response length      |
    +-----------+----------+-----------------------------+
    | 6         | Variable | Server response             |
    +-----------+----------+-----------------------------+

    References
    ----------
    * DICOM Standard, Part 7,
      :dcm:`Annex D.3.3.7 <part07/sect_D.3.3.7.html>`
    * DICOM Standard, Part 8,
      :dcm:`Section 9.3.1<part08/sect_9.3.html#sect_9.3.1>`
    """

    def __init__(self):
        """Initialise a new User Identity (AC) Item."""
        self.server_response = None

    def from_primitive(self, primitive):
        """Set the item's values using an User Identity primitive.

        Parameters
        ----------
        primitive : pdu_primitives.UserIdentityNegotiation
            The primitive to use to set the Item's field values.
        """
        self.server_response = primitive.server_response

    def to_primitive(self):
        """Return an  User Identity primitive from the current Item.

        Returns
        -------
        pdu_primitives.UserIdentityNegotiation
            The primitive representation of the current Item.
        """
        from pynetdicom.pdu_primitives import UserIdentityNegotiation

        primitive = UserIdentityNegotiation()
        primitive.server_response = self.server_response

        return primitive

    @property
    def _decoders(self):
        """Return an iterable of tuples that contain field decoders.

        Returns
        -------
        list of tuple
            A list of ((offset, length), attr_name, callable, [args]), where

            - offset is the byte offset to start at
            - length is how many bytes to slice (if None then will slice to the
              end of the data),
            - attr_name is the name of the attribute corresponding to the field
            - callable is a decoding function that returns the decoded value,
            - args is a list of arguments to pass callable.
        """
        return [
            ((6, None), 'server_response', self._wrap_bytes, []),
        ]

    @property
    def _encoders(self):
        """Return an iterable of tuples that contain field decoders.

        Returns
        -------
        list of tuple
            A list of (attr_name, callable, [args]), where

            - attr_name is the name of the attribute corresponding to the field
            - callable is an encoding function that returns bytes
            - args is a list of arguments to pass callable.
        """
        return [
            ('item_type', PACK_UCHAR, []),
            (None, self._wrap_pack, [0x00, PACK_UCHAR]),
            ('item_length', PACK_UINT2, []),
            ('server_response_length', PACK_UINT2, []),
            ('server_response', self._wrap_bytes, [])
        ]

    @property
    def item_length(self):
        """Return the item's *Item Length* field value as :class:`int`."""
        return 2 + self.server_response_length

    @property
    def response(self):
        """Return the item's *Server Response* field value."""
        return self.server_response

    @property
    def server_response_length(self):
        """Return the item's *Server Response Length* field value."""
        if self.server_response:
            return len(self.server_response)

        return 0

    def __str__(self):
        """Return a string representation of the Item."""
        s = "User Identity (AC) Sub-item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        s += "  Server response length: {0:d} bytes\n".format(
            self.server_response_length)
        s += "  Server response: {0!s}\n".format(self.server_response)

        return s


## P-DATA-TF Item
# Overriden item_type
class PresentationDataValueItem(PDUItem):
    """A Presentation Data Value Item.

    Presentation Data Value (PDV) Items are used to contain DIMSE Messages
    that have been fragmented into Command and Data fragments, with each
    fragment placed into its own PDV Item.

    Attributes
    ----------
    item_length : int
        The *Item Length* field value.
    presentation_context_id : int
        The *Presentation Context ID* field value.
    presentation_data_value : bytes
        The *Presentation Data Value* field value.

    Notes
    -----
    A Presentation Data Value Item requires the following parameters:

       * Item length (1)
       * Presentation context ID (1)
       * Presentation data value (1)

    **Encoding**

    When encoded, a Presentation Data Value Item has the following
    structure, taken from Tables 9.24 of the DICOM Standard (offsets shown with
    Python indexing). Items are always encoded using Big Endian.

    +---------------------------+----------+-----------------------------+
    | Offset                    | Length   | Description                 |
    +===========================+==========+=============================+
    | 0                         | 4        | Item length                 |
    +---------------------------+----------+-----------------------------+
    | 4                         | 1        | Presentation context ID     |
    +---------------------------+----------+-----------------------------+
    | 5                         | Variable | Presentation data value     |
    +---------------------------+----------+-----------------------------+

    References
    ----------
    * DICOM Standard, Part 8,
      :dcm:`Annex E <part08/chapter_E.html>`
    * DICOM Standard, Part 8,
      :dcm:`Section 9.3.5.1 <part08/sect_9.3.5.html#sect_9.3.5.1>`
    * DICOM Standard, Part 8,
      :dcm:`Section 9.3.1<part08/sect_9.3.html#sect_9.3.1>`
    """

    def __init__(self):
        """Initialise a new Presentation Data Value Item."""
        self.presentation_context_id = None
        self.presentation_data_value = None

    @property
    def context_id(self):
        """Return the item's *Presentation Context ID* field value."""
        return self.presentation_context_id

    @property
    def data(self):
        """Return the item's *Presentation Data Value* field value."""
        return self.presentation_data_value

    @property
    def _decoders(self):
        """Return an iterable of tuples that contain field decoders.

        Returns
        -------
        list of tuple
            A list of ((offset, length), attr_name, callable, [args]), where

            - offset is the byte offset to start at
            - length is how many bytes to slice (if None then will slice to the
              end of the data),
            - attr_name is the name of the attribute corresponding to the field
            - callable is a decoding function that returns the decoded value,
            - args is a list of arguments to pass callable.
        """
        return [
            (
                (4, 1),
                'presentation_context_id',
                self._wrap_unpack,
                [UNPACK_UCHAR]
            ),
            (
                (5, None),
                'presentation_data_value',
                self._wrap_bytes,
                []
            )
        ]

    @property
    def _encoders(self):
        """Return an iterable of tuples that contain field decoders.

        Returns
        -------
        list of tuple
            A list of (attr_name, callable, [args]), where

            - attr_name is the name of the attribute corresponding to the field
            - callable is an encoding function that returns bytes
            - args is a list of arguments to pass callable.
        """
        return [
            ('item_length', PACK_UINT4, []),
            ('presentation_context_id', PACK_UCHAR, []),
            ('presentation_data_value', self._wrap_bytes, [])
        ]

    @property
    def item_length(self):
        """Return the item's *Item Length* field value as :class:`int`."""
        if self.presentation_data_value:
            return 1 + len(self.presentation_data_value)

        return 1

    @property
    def item_type(self):
        """Raise NotImplementedError as Presentation Data Value Items have no
       *Item Type* field.
        """
        raise NotImplementedError

    @property
    def message_control_header_byte(self):
        """Return the message control header byte as a formatted string."""
        if self.presentation_data_value:
            return "{:08b}".format(ord(self.presentation_data_value[0:1]))

        raise ValueError("No *Presentation Data Value* field value")

    def __str__(self):
        """Return a string representation of the Item."""
        s = "Presentation Value Data Item\n"
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        s += "  Context ID: {0:d}\n".format(self.presentation_context_id)

        # Python 2 compatibility
        pdv_sample = self.presentation_data_value[:10]
        if isinstance(pdv_sample, str):
            pdv_sample = (format(ord(x), '02x') for x in pdv_sample)
        else:
            pdv_sample = (format(x, '02x') for x in pdv_sample)
        s += "  Data value: 0x{0!s} ...\n".format(' 0x'.join(pdv_sample))

        return s


# PDU items and sub-items, indexed by their type
PDU_ITEM_TYPES = {
    0x10 : ApplicationContextItem,
    0x20 : PresentationContextItemRQ,
    0x21 : PresentationContextItemAC,
    0x30 : AbstractSyntaxSubItem,
    0x40 : TransferSyntaxSubItem,
    0x50 : UserInformationItem,
    0x51 : MaximumLengthSubItem,
    0x52 : ImplementationClassUIDSubItem,
    0x53 : AsynchronousOperationsWindowSubItem,
    0x54 : SCP_SCU_RoleSelectionSubItem,
    0x55 : ImplementationVersionNameSubItem,
    0x56 : SOPClassExtendedNegotiationSubItem,
    0x57 : SOPClassCommonExtendedNegotiationSubItem,
    0x58 : UserIdentitySubItemRQ,
    0x59 : UserIdentitySubItemAC
}

_TYPE_TO_PDU_ITEM = {vv: kk for kk, vv in PDU_ITEM_TYPES.items()}
