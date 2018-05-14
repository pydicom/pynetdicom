"""DICOM Upper Layer PDU Items and Sub-items.

"""

import codecs
import logging
from struct import Struct

from pydicom.uid import UID

from pynetdicom3.presentation import PresentationContext


LOGGER = logging.getLogger('pynetdicom3.pdu_items')

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

    Protocol Data Units (PDUs) are the message formats exchanged between peer
    entities within a layer. A PDU consists of protocol control information
    and user data. PDUs are constructed by mandatory fixed fields followed by
    optional variable fields that contain one or more items and/or sub-items.

    References
    ----------
    DICOM Standard, Part 8, `Section 9.3 <http://dicom.nema.org/medical/dicom/current/output/html/part08.html#sect_9.3>`_
    """

    def decode(self, bytestream):
        """Decode `bytestream` and set the parameters of the PDU.

        Parameters
        ----------
        bytestream : bytes
            The PDU data to be decoded.

        Notes
        -----
        **Encoding**
        The encoding of DICOM PDUs is Big Endian [1]_.

        References
        ----------
        .. [1] DICOM Standard, Part 8,
           `Section 9.3.1 <http://dicom.nema.org/medical/dicom/current/output/html/part08.html#sect_9.3.1>`_
        """
        for (start, length), attr_name, func, args in self._decoders:
            if not hasattr(self, attr_name):
                raise ValueError('Unknown attribute name ', attr_name)

            # Allow us to use None as a `length`
            if length:
                sl = slice(start, start + length)
            else:
                sl = slice(start, None)

            setattr(
                self, attr_name, func(bytestream[sl], *args)
            )

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

        Notes
        -----
        **Encoding**
        The encoding of DICOM PDUs is Big Endian [1]_.

        References
        ----------
        .. [1] DICOM Standard, Part 8,
           `Section 9.3.1 <http://dicom.nema.org/medical/dicom/current/output/html/part08.html#sect_9.3.1>`_
        """
        bytestream = bytes()
        for attr_name, func, args in self._encoders:
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
        """Return True if self equals other."""
        if isinstance(other, self.__class__):
            _sdict = {
                kk : vv for kk, vv in self.__dict__.items() if kk[0] != '_'
            }
            _odict = {
                kk : vv for kk, vv in other.__dict__.items() if kk[0] != '_'
            }
            return _odict == _sdict

        return False

    @staticmethod
    def _generate_items(bytestream):
        """Yield the variable item data from `bytestream`.

        +--------+-------------+-------------+
        | Offset | Length      | Description |
        +========+=============+=============+
        | 0      | 1           | Item type   |
        | 1      | 1           | Reserved    |
        | 2      | 2           | Item length |
        | 3      | Item length | Item data   |
        +--------+-------------+-------------+

        Parameters
        ----------
        bytestream : bytes
            The encoded PDU variable item data.

        Yields
        ------
        int, bytes
            The variable item's 'Item Type' parameter as int, and encoded data
            as bytes.

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
        """
        offset = 0
        while bytestream[offset:offset + 1]:
            item_type = bytestream[offset:offset + 1]
            item_length = UNPACK_UINT2(bytestream[offset + 2:offset + 4])[0]
            item_data = bytestream[offset:offset + 4 + item_length]
            yield item_type, item_data
            # Change `offset` to the start of the next item
            offset += 4 + item_length

    __hash__ = None

    @property
    def item_length(self):
        """Return the 'Item Length' parameter value."""
        raise NotImplementedError

    @property
    def item_type(self):
        """Return the item type as an int."""
        raise NotImplementedError

    def __ne__(self, other):
        """Return True if self does not equal other."""
        return not self == other

    @staticmethod
    def _wrap_ascii(bytestream):
        return codecs.encode(bytestream, 'ascii')

    @staticmethod
    def _wrap_bytes(bytestream):
        """Return the `bytestream`."""
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

    def _wrap_generate_items(self, bytestream):
        """Return a list of PDU items generated from `bytestream`."""
        item_list = []
        for item_type, item_bytes in self._generate_items(bytestream):
            item = PDU_ITEM_TYPES[item_type[0]]()
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
    def _wrap_slice(bytestream):
        """Return `bytestream`."""
        return bytestream

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
    """An Application Context item.

    Represents the Application Context Item used in A-ASSOCIATE-RQ and
    A-ASSOCIATE-AC PDUs.

    The Application Context Item requires the following parameters (see PS3.8
    Section 9.3.2.1):

        * Item type (1, fixed value, 0x10)
        * Item length (1)
        * Application Context Name (1, fixed in an application)

    See PS3.8 Section 9.3.2.1 for the structure of the PDU, especially
    Table 9-12.

    Used in A_ASSOCIATE_RQ - Variable items
    Used in A_ASSOCIATE_AC - Variable items

    Attributes
    ----------
    application_context_name : pydicom.uid.UID
        The UID for the Application Context Name
    length : int
        The length of the encoded Item in bytes

    Notes
    -----
    Application context names are encoded as in Annex F, structured as UIDs as
    defined in PS3.5. and registered in PS3.7.

    Each component of a UID is encoded as an ISO 646:1990-Basic G0 Set Numeric
    String of bytes (characters 0-9). Leading 0's of each component are not
    significant and shall not be sent. Components shall not be padded.
    Components shall be separated by the character '.' (0x2e). Null components
    (no numeric value between two separators) shall not exist. Components with
    the value of zero (0) shall be encoded as (nnn.0.ppp). No separator or
    padding shall be present before the first digit of the first component or
    after the last digit of the last component.

    Application context names shall not exceed 64 total characters.

    A single DICOM Application Context Name is defined for the current version
    of the Standard and it is '1.2.840.10008.3.1.1.1'.

    References
    ----------
    DICOM Standard, Part 8, Annex F
    """

    def __init__(self):
        self.application_context_name = ''

    def FromParams(self, primitive):
        """
        Set up the Item using the parameter values from the `primitive`

        Parameters
        ----------
        primitive : pydicom.uid.UID, bytes, str or None
            The UID value to use for the Application Context Name
        """
        self.application_context_name = primitive

    def ToParams(self):
        """
        Convert the current Item to a primitive

        Returns
        -------
        pydicom.uid.UID
            The Application Context Name's UID value
        """
        return self.application_context_name

    @property
    def application_context_name(self):
        """Returns the Application Context Name as a pydicom.uid.UID."""
        return self._application_context_name

    @application_context_name.setter
    def application_context_name(self, value):
        """Set the application context name.

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
            value = UID(value.decode('utf-8'))
        else:
            raise TypeError('Application Context Name must be a UID, '
                            'str or bytes')

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
            ((4, None), 'application_context_name', self._wrap_slice, [])
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
            ('application_context_name', self._wrap_ascii, [])
        ]

    def __len__(self):
        """Return the total encoded length of the item."""
        return 4 + self.item_length

    @property
    def item_length(self):
        """Return the Item Length parameter value."""
        return len(self.application_context_name)

    @property
    def item_type(self):
        """Return the item type as an int."""
        return 0x10

    def __str__(self):
        s = '{0!s} ({1!s})\n'.format(self.application_context_name,
                                     self.application_context_name.title())
        return s


class PresentationContextItemRQ(PDUItem):
    """A Presentation Context (RQ) item.

    Represents a Presentation Context Item used in A-ASSOCIATE-RQ PDUs.

    The Presentation Context Item requires the following parameters (see PS3.8
    Section 9.3.2.2):

        * Item type (1, fixed value, 0x20)
        * Item length (1)
        * Presentation context ID (1)
        * Abstract/Transfer Syntax Sub-items (1)

          * Abstract Syntax Sub-item (1)

            * Item type (1, fixed, 0x30)
            * Item length (1)
            * Abstract syntax name (1)
          * Transfer Syntax Sub-items (1 or more)

            * Item type (1, fixed, 0x40)
            * Item length (1)
            * Transfer syntax name(s) (1 or more)

    See PS3.8 Section 9.3.2.2 for the structure of the item, especially
    Table 9-13.

    Used in A_ASSOCIATE_RQ - Variable items

    Attributes
    ----------
    abstract_syntax : pydicom.uid.UID
        The presentation context's Abstract Syntax value
    abstract_transfer_syntax_sub_items
    length : int
        The length of the encoded Item in bytes
    presentation_context_id : int
        The presentation context's ID
    transfer_syntax : list of pydicom.uid.UID
        The presentation context's Transfer Syntax(es)
    """

    def __init__(self):
        self.presentation_context_id = None
        self.abstract_transfer_syntax_sub_items = []

    def FromParams(self, primitive):
        """
        Set up the Item using the parameter values from the `primitive`

        Parameters
        ----------
        primitive : pynetdicom3.utils.PresentationContext
            The PresentationContext object to use to setup the Item
        """
        # Add presentation context ID
        self.presentation_context_id = primitive.ID

        # Add abstract syntax
        abstract_syntax = AbstractSyntaxSubItem()
        abstract_syntax.FromParams(primitive.AbstractSyntax)
        self.abstract_transfer_syntax_sub_items.append(abstract_syntax)

        # Add transfer syntax(es)
        for syntax in primitive.TransferSyntax:
            transfer_syntax = TransferSyntaxSubItem()
            transfer_syntax.FromParams(syntax)
            self.abstract_transfer_syntax_sub_items.append(transfer_syntax)

    def ToParams(self):
        """
        Convert the current Item to a primitive

        Returns
        -------
        pynetdicom3.utils.PresentationContext
            The primitive to covert the Item to
        """
        context = PresentationContext(self.presentation_context_id)

        # Add transfer syntax(es)
        for syntax in self.abstract_transfer_syntax_sub_items:
            if isinstance(syntax, TransferSyntaxSubItem):
                context.add_transfer_syntax(syntax.ToParams())
            elif isinstance(syntax, AbstractSyntaxSubItem):
                context.AbstractSyntax = syntax.ToParams()

        return context

    @property
    def abstract_syntax(self):
        """Get the abstract syntax."""
        for item in self.abstract_transfer_syntax_sub_items:
            if isinstance(item, AbstractSyntaxSubItem):
                return item.abstract_syntax_name

        return None

    @property
    def context_id(self):
        """
        See PS3.8 9.3.2.2

        Returns
        -------
        int
            Odd number between 1 and 255 (inclusive)
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
        """Return the Item Length parameter value."""
        # Start at 4: of presentation context ID, 1 byte + 3 reserved bytes
        length = 4
        for item in self.abstract_transfer_syntax_sub_items:
            length += len(item)

        return length

    @property
    def item_type(self):
        """Return the item type as an int."""
        return 0x20

    def __len__(self):
        """Return the total encoded length of the item."""
        return 4 + self.item_length

    def __str__(self):
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
        """Get the transfer syntaxes."""
        syntaxes = []
        for ii in self.abstract_transfer_syntax_sub_items:
            if isinstance(ii, TransferSyntaxSubItem):
                syntaxes.append(ii.transfer_syntax_name)

        return syntaxes

# FIXME: Transfer Syntax should be list
class PresentationContextItemAC(PDUItem):
    """A Presentation Context (AC) item.

    Represents a Presentation Context Item used in A-ASSOCIATE-AC PDUs.

    The Presentation Context Item requires the following parameters (see PS3.8
    Section 9.3.3.2):

        * Item type (1, fixed value, 0x21)
        * Item length (1)
        * Presentation context ID (1)
        * Result/reason (1)
        * Transfer Syntax Sub-item (1)

          * Item type (1, fixed, 0x40)
          * Item length (1)
          * Transfer syntax name (1)

    See PS3.8 Section 9.3.3.2 for the structure of the item, especially
    Table 9-18.

    Used in A_ASSOCIATE_AC - Variable items

    Attributes
    ----------
    presentation_context_id : int
        The presentation context's ID
    result : int
        The presentation context's result/reason value
    result_reason
    result_str : str
        The result as a string, one of ('Accepted', 'User Rejected',
        'No Reason', 'Abstract Syntax Not Supported',
        'Transfer Syntaxes Not Supported')
    transfer_syntax : pydicom.uid.UID
        The presentation context's Transfer Syntax
    transfer_syntax_sub_item
    """

    def __init__(self):
        self.presentation_context_id = None
        self.result_reason = None
        self.transfer_syntax_sub_item = None

    def FromParams(self, primitive):
        """
        Set up the Item using the parameter values from the `primitive`

        Parameters
        ----------
        primitive : pynetdicom3.utils.PresentationContext
            The PresentationContext object to use to setup the Item
        """
        # Add presentation context ID
        self.presentation_context_id = primitive.ID

        # Add reason
        self.result_reason = primitive.Result

        # Add transfer syntax
        transfer_syntax = TransferSyntaxSubItem()
        transfer_syntax.FromParams(primitive.TransferSyntax[0])
        self.transfer_syntax_sub_item = [transfer_syntax]

    def ToParams(self):
        """
        Convert the current Item to a primitive

        Returns
        -------
        pynetdicom3.utils.PresentationContext
            The primitive to covert the Item to
        """
        primitive = PresentationContext(self.presentation_context_id)
        primitive.Result = self.result_reason
        primitive.add_transfer_syntax(
            self.transfer_syntax_sub_item[0].ToParams()
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
        """Return the Item Length parameter value."""
        return 4 + len(self.transfer_syntax_sub_item[0])

    @property
    def item_type(self):
        """Return the item type as an int."""
        return 0x21

    def __len__(self):
        """Return the total encoded length of the item."""
        return 4 + self.item_length

    def __str__(self):
        s = "Presentation Context (AC) Item\n"
        s += "  Item type:   0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        s += "  Context ID: {0:d}\n".format(self.presentation_context_id)
        s += "  Result/Reason: {0!s}\n".format(self.result_str)

        item_str = '{0!s}'.format(self.transfer_syntax.name)
        item_str_list = item_str.split('\n')
        s += '  +  {0!s}\n'.format(item_str_list[0])
        for jj in item_str_list[1:-1]:
            s += '     {0!s}\n'.format(jj)

        return s

    @property
    def context_id(self):
        """Get the presentation context ID."""
        return self.presentation_context_id

    @property
    def result(self):
        """Get the Result parameter."""
        return self.result_reason

    @property
    def result_str(self):
        """Get a string describing the result."""
        result_options = {0: 'Accepted',
                          1: 'User Rejection',
                          2: 'Provider Rejection',
                          3: 'Abstract Syntax Not Supported',
                          4: 'Transfer Syntax Not Supported'}
        return result_options[self.result]

    @property
    def transfer_syntax(self):
        """Get the transfer syntax."""
        return self.transfer_syntax_sub_item[0].transfer_syntax_name


class UserInformationItem(PDUItem):
    """
    Represents the User Information Item used in A-ASSOCIATE-RQ and
    A-ASSOCIATE-AC PDUs.

    The User Information Item requires the following parameters (see PS3.8
    Section 9.3.2.3):

    * Item type (1, fixed, 0x50)
    * Item length (1)
    * User data sub-items (2 or more)
        * Maximum Length Received Sub-item (1)
        * Implementation Class UID Sub-item (1)
        * Optional User Data Sub-items (0 or more)

    See PS3.8 Section 9.3.2.3 for the structure of the PDU, especially
    Table 9-16.

    Used in A_ASSOCIATE_RQ - Variable items
    Used in A_ASSOCIATE_AC - Variable items

    Attributes
    ----------
    async_ops_window : AsynchronousOperationsWindowSubItem or None
        The AsynchronousOperationsWindowSubItem object, or None if the sub-item
        is not present.
    common_ext_neg : list of
        pynetdicom3.pdu_items.SOPClassCommonExtendedNegotiationSubItem or None
        The common extended negotiation items, or None if there aren't any
    ext_neg : list of pynetdicom3.pdu_items.SOPClassExtendedNegotiationSubItem
    or None
        The extended negotiation items, or None if there aren't any
    implementation_class_uid : pydicom.uid.UID
        The implementation class UID for the Implementation Class UID sub-item
    implementation_version_name : str or None
        The implementation version name for the Implementation Version Name
        sub-item, or None if the sub-item is not present.
    length : int
        The length of the encoded Item in bytes
    max_operations_invoked : int or None
        , or None if the sub-item is not present.
    max_operations_performed : int or None
        , or None if the sub-item is not present.
    maximum_length : int
        The maximum length received value for the Maximum Length sub-item
    role_selection : list of pynetdicom3.pdu_items.SCP_SCU_RoleSelectionSubItem
    or None
        The SCP_SCU_RoleSelectionSubItem object or None if there aren't any
    user_identity : pynetdicom3.pdu_items.UserIdentitySubItemRQ or
        pynetdicom3.pdu_items.UserIdentitySubItemAC or None
        The UserIdentitySubItemRQ/UserIdentitySubItemAC object, or None if the
        sub-item is not present.
    """

    def __init__(self):
        self.user_data = []

    def FromParams(self, primitive):
        """
        Set up the Item using the parameter values from the `primitive`

        Parameters
        ----------
        primitive : list
        """
        for item in primitive:
            self.user_data.append(item.FromParams())

    def ToParams(self):
        """
        Convert the current Item to a primitive

        Returns
        -------
        list

        """
        primitive = []
        for ii in self.user_data:
            primitive.append(ii.ToParams())

        return primitive

    @property
    def async_ops_window(self):
        """Get the asynchronous operations window item."""
        for item in self.user_data:
            if isinstance(item, AsynchronousOperationsWindowSubItem):
                return item

        return None

    @property
    def common_ext_neg(self):
        """Get the common extended negotiation items."""
        items = []
        for item in self.user_data:
            if isinstance(item, SOPClassCommonExtendedNegotiationSubItem):
                items.append(item)

        if items:
            return items

        return None

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
        """Get the extended negotiation item."""
        items = []
        for item in self.user_data:
            if isinstance(item, SOPClassExtendedNegotiationSubItem):
                items.append(item)

        if items:
            return items

        return None

    @property
    def implementation_class_uid(self):
        """Return the Implementation Class UID item."""
        for item in self.user_data:
            if isinstance(item, ImplementationClassUIDSubItem):
                return item.implementation_class_uid

        return None

    @property
    def implementation_version_name(self):
        """Return the Implementation Version Name item or None."""
        for item in self.user_data:
            if isinstance(item, ImplementationVersionNameSubItem):
                return item.implementation_version_name.decode('utf-8')

        return None

    @property
    def item_length(self):
        """Return the Item Length parameter value."""
        length = 0
        for item in self.user_data:
            length += len(item)

        return length

    @property
    def item_type(self):
        """Return the item type as an int."""
        return 0x50

    def __len__(self):
        """Return the total encoded length of the item."""
        return 4 + self.item_length

    @property
    def maximum_length(self):
        """Return the Maximum Length item."""
        for item in self.user_data:
            if isinstance(item, MaximumLengthSubItem):
                return item.maximum_length_received

        return None

    @property
    def max_operations_invoked(self):
        """Return the maximum number of invoked operations.

        Returns
        -------
        int or None
            If the A-ASSOCIATE-RQ contains an Asynchronous Windows item then
            returns the maximum number of invoked operations as an int,
            otherwise returns None.
        """
        for item in self.user_data:
            if isinstance(item, AsynchronousOperationsWindowSubItem):
                return item.max_operations_invoked

        return None

    @property
    def max_operations_performed(self):
        """Return the maximum number of performed operations.

        Returns
        -------
        int or None
            If the A-ASSOCIATE-RQ contains an Asynchronous Windows item then
            returns the maximum number of performed operations as an int,
            otherwise returns None.
        """
        for item in self.user_data:
            if isinstance(item, AsynchronousOperationsWindowSubItem):
                return item.max_operations_invoked

        return None

    @property
    def role_selection(self):
        """Return the SCP/SCU Role Selection items or None if none present.

        Returns
        -------
        dict or None
            The SCP/SCU Role Selection items as {item.uid : item} or None if
            no items.
        """
        roles = {}
        for item in self.user_data:
            if isinstance(item, SCP_SCU_RoleSelectionSubItem):
                roles[item.uid] = item

        if roles:
            return roles

        return None

    def __str__(self):
        # FIXME: Indent not applying correctly to user_data
        s = " User information item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d}\n".format(self.item_length)
        s += "  User Data:\n "

        for item in self.user_data:
            s += "  {0!s}".format(item)

        return s

    @property
    def user_identity(self):
        """Return the User Identity item or None if none present."""
        for item in self.user_data:
            if isinstance(item, (UserIdentitySubItemRQ,
                                 UserIdentitySubItemAC)):
                return item

        return None


## Presentation Context Item sub-items
class AbstractSyntaxSubItem(PDUItem):
    """
    Represents an Abstract Syntax Sub-item used in A-ASSOCIATE-RQ PDUs.

    The Abstract Syntax Sub-item requires the following parameters (see PS3.8
    Section 9.3.2.2.1):

        * Item type (1, fixed value, 0x30)
        * Item length (1)
        * Abstract syntax name (1)

    See PS3.8 Section 9.3.2.2.1 for the structure of the item, especially
    Table 9-14.

    Used in A_ASSOCIATE_RQ - Variable items - Presentation Context items -
    Abstract/Transfer Syntax sub-items

    Attributes
    ----------
    abstract_syntax : pydicom.uid.UID
        The abstract syntax
    length : int
        The length of the encoded Item in bytes
    """

    def __init__(self):
        self.abstract_syntax_name = None

    def FromParams(self, primitive):
        """
        Set up the Item using the parameter values from the `primitive`

        Parameters
        ----------
        primitive : pydicom.uid.UID, bytes or str
            The abstract syntax name
        """
        self.abstract_syntax_name = primitive

    def ToParams(self):
        """
        Convert the current Item to a primitive

        Returns
        -------
        pydicom.uid.UID
            The Abstract Syntax Name's UID value
        """
        return self.abstract_syntax_name

    @property
    def abstract_syntax(self):
        """Get the abstract syntax."""
        return self.abstract_syntax_name

    @property
    def abstract_syntax_name(self):
        """Get the abstract syntax name."""
        return self._abstract_syntax_name

    @abstract_syntax_name.setter
    def abstract_syntax_name(self, value):
        """Sets the Abstract Syntax Name parameter

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The value for the Abstract Syntax Name
        """
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, UID):
            pass
        elif isinstance(value, str):
            value = UID(value)
        elif isinstance(value, bytes):
            value = UID(value.decode('utf-8'))
        elif value is None:
            pass
        else:
            raise TypeError('Abstract Syntax must be a pydicom.uid.UID, '
                            'str or bytes')

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
            ((4, None), 'abstract_syntax_name', self._wrap_slice, [])
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
            ('abstract_syntax_name', self._wrap_ascii, [])
        ]

    @property
    def item_length(self):
        """Return the Item Length parameter value."""
        if self.abstract_syntax_name:
            return len(self.abstract_syntax_name)

        return 0x00

    @property
    def item_type(self):
        """Return the item type as an int."""
        return 0x30

    def __len__(self):
        """Return the total encoded length of the item."""
        return 4 + self.item_length

    def __str__(self):
        s = "Abstract Syntax Sub-item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        s += '  Syntax name: ={0!s}\n'.format(self.abstract_syntax.name)

        return s


class TransferSyntaxSubItem(PDUItem):
    """
    Represents a Transfer Syntax Sub-item used in A-ASSOCIATE-RQ and
    A-ASSOCIATE-AC PDUs.

    The Abstract Syntax Sub-item requires the following parameters (see PS3.8
    Section 9.3.2.2.2):

        * Item type (1, fixed value, 0x40)
        * Item length (1)
        * Transfer syntax name (1)

    See PS3.8 Section 9.3.2.2.2 for the structure of the item, especially
    Table 9-15.

    Used in A_ASSOCIATE_RQ - Variable items - Presentation Context items -
    Abstract/Transfer Syntax sub-items
    Used in A_ASSOCIATE_AC - Variable items - Presentation Context items -
    Transfer Syntax sub-item

    Attributes
    ----------
    length : int
        The length of the encoded Item in bytes
    transfer_syntax : pydicom.uid.UID
        The transfer syntax
    """

    def __init__(self):
        self.transfer_syntax_name = None

    def FromParams(self, primitive):
        """
        Set up the Item using the parameter values from the `primitive`

        Parameters
        ----------
        primitive : pydicom.uid.UID, bytes or str
            The transfer syntax name
        """
        self.transfer_syntax_name = primitive

    def ToParams(self):
        """
        Convert the current Item to a primitive

        Returns
        -------
        pydicom.uid.UID
            The Transfer Syntax Name's UID value
        """
        return self.transfer_syntax_name

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
            ((4, None), 'transfer_syntax_name', self._wrap_slice, [])
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
            ('transfer_syntax_name', self._wrap_ascii, [])
        ]

    @property
    def item_length(self):
        """Return the Item Length parameter value."""
        if self.transfer_syntax_name:
            return len(self.transfer_syntax_name)

        return 0x00

    @property
    def item_type(self):
        """Return the item type as an int."""
        return 0x40

    def __len__(self):
        """Return the total encoded length of the item."""
        return 4 + self.item_length

    def __str__(self):
        s = "Transfer syntax sub item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        s += '  Transfer syntax name: ={0!s}\n'.format(
            self.transfer_syntax_name.name)

        return s

    @property
    def transfer_syntax(self):
        """Get the transfer syntax."""
        return self.transfer_syntax_name

    @property
    def transfer_syntax_name(self):
        """Get the transfer syntax name."""
        return self._transfer_syntax_name

    @transfer_syntax_name.setter
    def transfer_syntax_name(self, value):
        """Sets the Transfer Syntax Name parameter.

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
            value = UID(value.decode('utf-8'))
        elif value is None:
            pass
        else:
            raise TypeError('Transfer syntax must be a pydicom.uid.UID, '
                            'bytes or str')

        self._transfer_syntax_name = value


## User Information Item sub-items
class MaximumLengthSubItem(PDUItem):
    """
    Represents the Maximum Length Sub Item used in A-ASSOCIATE-RQ and
    A-ASSOCIATE-AC PDUs.

    The Maximum Length Sub Item requires the following parameters (see PS3.8
    Annex D.1.1):

        * Item type (1, fixed, 0x51)
        * Item length (1)
        * Maximum Length Received (1)

    See PS3.8 Annex D.1.1 for the structure of the item, especially
    Table D.1-1.

    Used in A_ASSOCIATE_RQ - Variable items - User Information - User Data
    Used in A_ASSOCIATE_AC - Variable items - User Information - User Data

    Attributes
    ----------
    length : int
        The length of the encoded Item in bytes
    """

    def __init__(self):
        self.maximum_length_received = None

    def FromParams(self, primitive):
        """
        Set up the Item using the parameter values from the `primitive`

        Parameters
        ----------
        primitive : pynetdicom3.pdu_primitives.MaximumLengthNegotiation
            The primitive to use when setting up the Item
        """
        self.maximum_length_received = primitive.maximum_length_received

    def ToParams(self):
        """
        Convert the current Item to a primitive

        Returns
        -------
        pynetdicom3.pdu_primitives.MaximumLengthNegotiation
            The primitive to convert to
        """
        from pynetdicom3.pdu_primitives import MaximumLengthNegotiation

        primitive = MaximumLengthNegotiation()
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
        """Return the Item Length parameter value."""
        return 0x04

    @property
    def item_type(self):
        """Return the item type as an int."""
        return 0x51

    def __len__(self):
        """Return the total encoded length of the item."""
        return 0x08

    def __str__(self):
        s = "Maximum length Sub-item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        s += "  Maximum length received: {0:d}\n".format(
            self.maximum_length_received)
        return s


class ImplementationClassUIDSubItem(PDUItem):
    """
    Represents the Implementation Class UID Sub Item used in A-ASSOCIATE-RQ and
    A-ASSOCIATE-AC PDUs.

    The Implementation Class UID Sub Item requires the following parameters
    (see PS3.7 Annex D.3.3.2.1):

        * Item type (1, fixed, 0x51)
        * Item length (1)
        * Implementation Class UID (1)

    See PS3.7 Annex D.3.3.2.1-2 for the structure of the item, especially
    Tables D.3-1 and D.3-2.

    Used in A_ASSOCIATE_RQ - Variable items - User Information - User Data
    Used in A_ASSOCIATE_AC - Variable items - User Information - User Data

    Attributes
    ----------
    implementation_class_uid : pydicom.uid.UID
        The Implementation Class UID
    length : int
        The length of the encoded Item in bytes
    """

    def __init__(self):
        self.implementation_class_uid = None

    def FromParams(self, primitive):
        """
        Set up the Item using the parameter values from the `primitive`

        Parameters
        ----------
        primitive : pynetdicom3.pdu_primitives
                                .ImplementationClassUIDNotification
            The primitive to use when setting up the Item
        """
        self.implementation_class_uid = primitive.implementation_class_uid

    def ToParams(self):
        """
        Convert the current Item to a primitive

        Returns
        -------
        pynetdicom3.pdu_primitives.ImplementationClassUIDNotification
            The primitive to convert to
        """
        from pynetdicom3.pdu_primitives import \
            ImplementationClassUIDNotification

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
            ((4, None), 'implementation_class_uid', self._wrap_slice, [])
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
            ('implementation_class_uid', self._wrap_ascii, [])
        ]

    @property
    def implementation_class_uid(self):
        """Get the implementation class uid."""
        return self._implementation_class_uid

    @implementation_class_uid.setter
    def implementation_class_uid(self, value):
        """Sets the implementation class UID to `value`.

        Parameters
        ----------
        value : pydicom.uid.UID, bytes or str
            The UID value to set
        """
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, UID):
            pass
        elif isinstance(value, str):
            value = UID(value)
        elif isinstance(value, bytes):
            value = UID(value.decode('utf-8'))
        elif value is None:
            pass
        else:
            raise TypeError('implementation_class_uid must be str, bytes '
                            'or UID')

        self._implementation_class_uid = value
        #if value is not None:
        #    #self.item_length = len(self.implementation_class_uid)

    @property
    def item_length(self):
        """Return the Item Length parameter value."""
        if self.implementation_class_uid:
            return len(self.implementation_class_uid)

        return 0x00

    @property
    def item_type(self):
        """Return the item type as an int."""
        return 0x52

    def __len__(self):
        """Return the total encoded length of the item."""
        return 4 + self.item_length

    def __str__(self):
        s = "Implementation Class UID Sub-item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        s += "  Implementation class UID: '{0!s}'\n".format(
            self.implementation_class_uid)

        return s


class ImplementationVersionNameSubItem(PDUItem):
    """
    Represents the Implementation Class UID Sub Item used in A-ASSOCIATE-RQ and
    A-ASSOCIATE-AC PDUs.

    The Implementation Class UID Sub Item requires the following parameters
    (see PS3.7 Annex D.3.3.2.3):

        * Item type (1, fixed, 0x51)
        * Item length (1)
        * Implementation version name (1)

    See PS3.7 Annex D.3.3.2.3-4 for the structure of the item, especially
    Tables D.3-3 and D.3-4.

    Used in A_ASSOCIATE_RQ - Variable items - User Information - User Data
    Used in A_ASSOCIATE_AC - Variable items - User Information - User Data

    Attributes
    ----------
    implementation_version_name : bytes
        The Implementation Version Name
    length : int
        The length of the encoded Item in bytes
    """

    def __init__(self):
        self.implementation_version_name = None

    def FromParams(self, primitive):
        """
        Set up the Item using the parameter values from the `primitive`

        Parameters
        ----------
        primitive : pynetdicom3.pdu_primitives
                                    .ImplementationVersionNameNotification
            The primitive to use when setting up the Item
        """
        self.implementation_version_name = \
            primitive.implementation_version_name

    def ToParams(self):
        """Convert the current Item to a primitive.

        Returns
        -------
        pynetdicom3.pdu_primitives.ImplementationVersionNameNotification
            The primitive to convert to
        """
        from pynetdicom3.pdu_primitives import \
            ImplementationVersionNameNotification

        tmp = ImplementationVersionNameNotification()
        tmp.implementation_version_name = self.implementation_version_name

        return tmp

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
            ((4, None), 'implementation_version_name', self._wrap_slice, [])
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
        """Returns the implementation version name as bytes."""
        return self._implementation_version_name

    @implementation_version_name.setter
    def implementation_version_name(self, value):
        """Set the implementation version name."""
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, str):
            value = codecs.encode(value, 'ascii')

        self._implementation_version_name = value

    @property
    def item_length(self):
        """Return the Item Length parameter value."""
        if self.implementation_version_name:
            return len(self.implementation_version_name)

        return 0x00

    @property
    def item_type(self):
        """Return the item type as an int."""
        return 0x55

    def __len__(self):
        """Return the total encoded length of the item."""
        return 4 + self.item_length

    def __str__(self):
        s = "Implementation Version Name Sub-item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        s += "  Implementation version name: {0!s}\n".format(
            self.implementation_version_name)

        return s


class AsynchronousOperationsWindowSubItem(PDUItem):
    """
    Represents the Asynchronous Operations Window Sub Item used in
    A-ASSOCIATE-RQ and A-ASSOCIATE-AC PDUs.

    The Asynchronous Operations Window Sub Item requires the following
    parameters (see PS3.7 Annex D.3.3.3.1):

        * Item type (1, fixed, 0x51)
        * Item length (1)
        * Maximum number of operations invoked (1)
        * Maximum number of operations performed (1)

    See PS3.7 Annex D.3.3.3.1-2 for the structure of the item, especially
    Tables D.3-7 and D.3-8.

    Used in A_ASSOCIATE_RQ - Variable items - User Information - User Data
    Used in A_ASSOCIATE_AC - Variable items - User Information - User Data

    Attributes
    ----------
    length : int
        The length of the encoded Item in bytes
    max_operations_invoked : int
        The maximum number of operations invoked
    max_operations_performed : int
        The maximum number of operations performed
    """

    def __init__(self):
        self.maximum_number_operations_invoked = None
        self.maximum_number_operations_performed = None

    def FromParams(self, primitive):
        """
        Set up the Item using the parameter values from the `primitive`

        Parameters
        ----------
        primitive :
        pynetdicom3.pdu_primitives.AsynchronousOperationsWindowNegotiation
            The primitive to use when setting up the Item
        """
        self.maximum_number_operations_invoked = \
            primitive.maximum_number_operations_invoked
        self.maximum_number_operations_performed = \
            primitive.maximum_number_operations_performed

    def ToParams(self):
        """
        Convert the current Item to a primitive

        Returns
        -------
        pynetdicom3.pdu_primitives.AsynchronousOperationsWindowNegotiation
            The primitive to convert to
        """
        from pynetdicom3.pdu_primitives import \
            AsynchronousOperationsWindowNegotiation

        primitive = AsynchronousOperationsWindowNegotiation()
        primitive.maximum_number_operations_invoked = \
            self.maximum_number_operations_invoked
        primitive.maximum_number_operations_performed = \
            self.maximum_number_operations_performed

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
        """Return the Item Length parameter value."""
        return 0x04

    @property
    def item_type(self):
        """Return the item type as an int."""
        return 0x53

    def __len__(self):
        """Return the total encoded length of the item."""
        return 0x08

    @property
    def max_operations_invoked(self):
        """Get the maximum number of operations invoked"""
        return self.maximum_number_operations_invoked

    @property
    def max_operations_performed(self):
        """Get the maximum number of operations performed"""
        return self.maximum_number_operations_performed

    def __str__(self):
        s = "Asynchronous Operation Window Sub-item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        s += "  Max. number of operations invoked: {0:d}\n".format(
            self.maximum_number_operations_invoked)
        s += "  Max. number of operations performed: {0:d}\n".format(
            self.maximum_number_operations_performed)

        return s


class SCP_SCU_RoleSelectionSubItem(PDUItem):
    """
    Represents the SCP/SCU Role Selection Sub Item used in
    A-ASSOCIATE-RQ and A-ASSOCIATE-AC PDUs.

    The SCP/SCU Role Selection Sub Item requires the following parameters
    (see PS3.7 Annex D.3.3.4.1):

        * Item type (1, fixed, 0x51)
        * Item length (1)
        * UID length (1)
        * SOP Class UID (1)
        * SCU role (1)
        * SCP role (1)

    See PS3.7 Annex D.3.3.4.1-2 for the structure of the item, especially
    Tables D.3-9 and D.3-10.

    Used in A_ASSOCIATE_RQ - Variable items - User Information - User Data
    Used in A_ASSOCIATE_AC - Variable items - User Information - User Data

    Attributes
    ----------
    length : int
        The length of the encoded Item in bytes
    SCU : int
        The SCU role (0 or 1)
    SCP : int
        The SCP role (0 or 1)
    UID : pydicom.uid.UID
        The UID of the abstract syntax that this sub-item pertains
    """

    def __init__(self):
        self._uid_length = None
        self.sop_class_uid = None
        self.scu_role = None
        self.scp_role = None

    def FromParams(self, primitive):
        """
        Set up the Item using the parameter values from the `primitive`

        Parameters
        ----------
        primitive : pynetdicom3.pdu_primitives.SCP_SCU_RoleSelectionNegotiation
            The primitive to use when setting up the Item
        """
        self.sop_class_uid = primitive.sop_class_uid
        self.scu_role = int(primitive.scu_role)
        self.scp_role = int(primitive.scp_role)

    def ToParams(self):
        """
        Convert the current Item to a primitive

        Returns
        -------
        pynetdicom3.pdu_primitives.SCP_SCU_RoleSelectionNegotiation
            The primitive to convert to
        """
        from pynetdicom3.pdu_primitives import SCP_SCU_RoleSelectionNegotiation

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
            self._wrap_slice,
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
            ('sop_class_uid', self._wrap_ascii, []),
            ('scu_role', PACK_UCHAR, []),
            ('scp_role', PACK_UCHAR, [])
        ]

    @property
    def item_length(self):
        """Return the Item Length parameter value."""
        return 4 + self.uid_length

    @property
    def item_type(self):
        """Return the item type as an int."""
        return 0x54

    def __len__(self):
        """Return the total encoded length of the item."""
        return 4 + self.item_length

    @property
    def scu(self):
        """Get the SCU role"""
        return self.scu_role

    @property
    def scu_role(self):
        """Get the SCU role"""
        return self._scu_role

    @scu_role.setter
    def scu_role(self, value):
        """Set the SCU role"""
        # pylint: disable=attribute-defined-outside-init
        if value not in [0, 1, None]:
            raise ValueError('SCU Role parameter value must be 0 or 1')
        else:
            self._scu_role = value

    @property
    def scp(self):
        """Get the SCP role"""
        return self.scp_role

    @property
    def scp_role(self):
        """Get the SCP role"""
        return self._scp_role

    @scp_role.setter
    def scp_role(self, value):
        """Set the SCP role"""
        # pylint: disable=attribute-defined-outside-init
        if value not in [0, 1, None]:
            raise ValueError('SCP Role parameter value must be 0 or 1')
        else:
            self._scp_role = value

    @property
    def sop_class_uid(self):
        """Get the SOP class uid."""
        return self._sop_class_uid

    @sop_class_uid.setter
    def sop_class_uid(self, value):
        """Set the SOP class uid."""
        # pylint: disable=attribute-defined-outside-init
        # UID is a str subclass
        if isinstance(value, bytes):
            value = UID(value.decode('utf-8'))
        elif isinstance(value, str):
            value = UID(value)
        elif value is None:
            pass
        else:
            raise TypeError('sop_class_uid must be str, bytes or '
                            'pydicom.uid.UID')

        self._sop_class_uid = value

    def __str__(self):
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
        """Get the UID."""
        return self.sop_class_uid

    @property
    def uid_length(self):
        """Return the "UID Length" parameter value."""
        return len(self.sop_class_uid)


class SOPClassExtendedNegotiationSubItem(PDUItem):
    """
    Represents the SOP Class Extended Negotiation Sub Item used in
    A-ASSOCIATE-RQ and A-ASSOCIATE-AC PDUs.

    The SOP Class Extended Negotiation Sub Item requires the following
    parameters (see PS3.7 Annex D.3.3.5.1):

        * Item type (1, fixed, 0x56)
        * Item length (1)
        * UID length (1)
        * SOP Class UID (1)
        * Service class application information

    See PS3.7 Annex D.3.3.5.1-2 for the structure of the item, especially
    Tables D.3-11.

    Used in A_ASSOCIATE_RQ - Variable items - User Information - User Data
    Used in A_ASSOCIATE_AC - Variable items - User Information - User Data

    Attributes
    ----------
    length : int
        The length of the encoded Item in bytes
    UID : pydicom.uid.UID
        The UID of the abstract syntax that this sub-item pertains
    application_information :
        The application information specific to the service class identified
        by `sop_class_uid`
    """

    def __init__(self):
        self._sop_class_uid_length = None
        self.sop_class_uid = None
        self.service_class_application_information = None

    def FromParams(self, primitive):
        """
        Set up the Item using the parameter values from the `primitive`

        Parameters
        ----------
        primitive : pynetdicom3.pdu_primitives.SOPClassExtendedNegotiation
            The primitive to use when setting up the Item
        """
        self.sop_class_uid = primitive.sop_class_uid
        self.service_class_application_information = \
            primitive.service_class_application_information

    def ToParams(self):
        """
        Convert the current Item to a primitive

        Returns
        -------
        pynetdicom3.pdu_primitives.SOPClassExtendedNegotiation
            The primitive to convert to
        """
        from pynetdicom3.pdu_primitives import SOPClassExtendedNegotiation

        primitive = SOPClassExtendedNegotiation()
        primitive.sop_class_uid = self.sop_class_uid
        primitive.service_class_application_information = \
            self.service_class_application_information

        return primitive

    @property
    def app_info(self):
        """Set the application information"""
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
            self._wrap_slice,
            []
        )

        yield (
            (6 + self._sop_class_uid_length, None),
            'service_class_application_information',
            self._wrap_slice,
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
            ('sop_class_uid', self._wrap_ascii, []),
            ('service_class_application_information', self._wrap_bytes, [])
        ]

    @property
    def item_length(self):
        """Return the Item Length parameter value."""
        return (2 +
                self.sop_class_uid_length +
                len(self.service_class_application_information))

    @property
    def item_type(self):
        """Return the item type as an int."""
        return 0x56

    def __len__(self):
        """Return the total encoded length of the item."""
        return 4 + self.item_length

    @property
    def sop_class_uid(self):
        """Get the sop class uid"""
        return self._sop_class_uid

    @sop_class_uid.setter
    def sop_class_uid(self, value):
        """Set the SOP class UID"""
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, bytes):
            value = UID(value.decode('utf-8'))
        elif isinstance(value, str):
            value = UID(value)
        elif value is None:
            pass
        else:
            raise TypeError('sop_class_uid must be str, bytes or '
                            'pydicom.uid.UID')

        self._sop_class_uid = value

        #if value is not None:
        #    self.sop_class_uid_length = len(value)

    @property
    def sop_class_uid_length(self):
        """Return the "SOP Class UID Length" parameter value."""
        return len(self.sop_class_uid)

    def __str__(self):
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
        """Get the SOP class uid"""
        return self.sop_class_uid

# FIXME: non generic _generate-items and _wrap_generate_items
class SOPClassCommonExtendedNegotiationSubItem(PDUItem):
    """
    Represents the SOP Class Common Extended Negotiation Sub Item used in
    A-ASSOCIATE-RQ PDUs.

    The SOP Class Common Extended Negotiation Sub Item requires the following
    parameters (see PS3.7 Annex D.3.3.6.1):

        * Item type (1, fixed, 0x57)
        * Sub-item version (1, fixed, 0x00)
        * Item length (1)
        * SOP class UID length (1)
        * SOP class UID (1)
        * Service class UID length (1)
        * Service class UID (1)
        * Related general SOP class identification length (1)
        * Related general SOP class identification sub fields (0 or more)
          * Related general SOP class UID length (1)
          * Related general SOP class UID (1)

    See PS3.7 Annex D.3.3.6.1 for the structure of the item, especially
    Tables D.3-12 and D.3-13.

    The Requestor may only offset one SOP Class Common Extended Negotiation item
    for each SOP Class UID that's present in the A-ASSOCIATE-RQ.

    No response is necessary and the Common Extended Negotiation items shall be
    omitted in the A-ASSOCIATE response.

    Used in A_ASSOCIATE_RQ - Variable items - User Information - User Data

    Attributes
    ----------
    length : int
        The length of the encoded Item in bytes
    """

    def __init__(self):
        self.sub_item_version = 0x00
        self._sop_length = None
        self.sop_class_uid = None
        self._service_length = None
        self.service_class_uid = None
        self.related_general_sop_class_identification = []

    def FromParams(self, primitive):
        """
        Set up the Item using the parameter values from the `primitive`

        Parameters
        ----------
        primitive : pynetdicom3.pdu_primitives.SOPClassCommonExtendedNegotiation
            The primitive to use when setting up the Item
        """
        self.sop_class_uid = primitive.sop_class_uid
        self.service_class_uid = primitive.service_class_uid
        self.related_general_sop_class_identification = \
            primitive.related_general_sop_class_identification

    def ToParams(self):
        """
        Convert the current Item to a primitive

        Returns
        -------
        pynetdicom3.pdu_primitives.SOPClassCommonExtendedNegotiation
            The primitive to convert to
        """
        from pynetdicom3.pdu_primitives import SOPClassCommonExtendedNegotiation

        primitive = SOPClassCommonExtendedNegotiation()
        primitive.sop_class_uid = self.sop_class_uid
        primitive.service_class_uid = self.service_class_uid
        primitive.related_general_sop_class_identification = \
            self.related_general_sop_class_identification

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
            self._wrap_slice,
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
            self._wrap_slice,
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
            ('sop_class_uid', self._wrap_ascii, []),
            ('service_class_uid_length', PACK_UINT2, []),
            ('service_class_uid', self._wrap_ascii, []),
            ('related_general_sop_class_identification_length', PACK_UINT2, []),
            ('related_general_sop_class_identification', self._wrap_list, []),
            # (None, )
        ]

    @staticmethod
    def _generate_items(bytestream):
        """Yield the related general SOP Class UIDs from `bytestream`.

        +--------+-------------+-------------------------+
        | Offset | Length      | Description             |
        +========+=============+=========================+
        | 0      | 2           | UID length              |
        | 2      | NN          | UID                     |
        +--------+-------------+-------------------------+

        Parameters
        ----------
        bytestream : bytes
            The encoded related general SOP Class UID data.

        Yields
        ------
        pydicom.uid.UID
            The related general SOP Class UIDs.
        """
        offset = 0
        while bytestream[offset:offset + 1]:
            uid_length = UNPACK_UINT2(bytestream[offset:offset + 2])[0]
            yield UID(
                bytestream[offset + 2:offset + 2 + uid_length].decode('ascii')
            )
            offset += 2 + uid_length

    @property
    def item_length(self):
        """Return the Item Length parameter value."""
        return (2 + self.sop_class_uid_length +
                2 + self.service_class_uid_length +
                2 + self.related_general_sop_class_identification_length)

    @property
    def item_type(self):
        """Return the item type as an int."""
        return 0x57

    def __len__(self):
        """Return the total encoded length of the item."""
        return 4 + self.item_length

    @property
    def related_general_sop_class_identification(self):
        """Get the related general sop class ID"""
        return self._related_general_sop_class_identification

    @related_general_sop_class_identification.setter
    def related_general_sop_class_identification(self, value_list):
        """Set the related general sop class ID"""
        # pylint: disable=attribute-defined-outside-init
        self._related_general_sop_class_identification = []
        #self.related_general_sop_class_identification_length = 0

        for value in value_list:
            if isinstance(value, bytes):
                value = UID(value.decode('utf-8'))
            elif isinstance(value, str):
                value = UID(value)
            else:
                raise TypeError('related_general_sop_class_identification '
                                'must be str, bytes or pydicom.uid.UID')

            self._related_general_sop_class_identification.append(value)
            #self.related_general_sop_class_identification_length += len(value)

    @property
    def related_general_sop_class_identification_length(self):
        """Return the "Related General SOP Class Identification Length"."""
        length = 0
        for uid in self._related_general_sop_class_identification:
            length += 2 + len(uid)

        return length

    @property
    def sop_class_uid(self):
        """Get the SOP class uid"""
        return self._sop_class_uid

    @sop_class_uid.setter
    def sop_class_uid(self, value):
        """Set the SOP class UID"""
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, bytes):
            value = UID(value.decode('utf-8'))
        elif isinstance(value, str):
            value = UID(value)
        elif value is None:
            pass
        else:
            raise TypeError('sop_class_uid must be str, bytes or '
                            'pydicom.uid.UID')

        self._sop_class_uid = value

    @property
    def sop_class_uid_length(self):
        """Return the "SOP Class UID Length" parameter value."""
        return len(self.sop_class_uid)

    @property
    def service_class_uid(self):
        """Get the service class UID"""
        return self._service_class_uid

    @service_class_uid.setter
    def service_class_uid(self, value):
        """Set the service class UID"""
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, bytes):
            value = UID(value.decode('utf-8'))
        elif isinstance(value, str):
            value = UID(value)
        elif value is None:
            pass
        else:
            raise TypeError('service_class_uid must be str, bytes or '
                            'pydicom.uid.UID')

        self._service_class_uid = value

    @property
    def service_class_uid_length(self):
        """Return the "Service Class UID Length" parameter value."""
        return len(self.service_class_uid)

    def __str__(self):
        s = "SOP Class Common Extended Negotiation Sub-item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        s += "  SOP class UID length: {0:d} bytes\n".format(
            self.sop_class_uid_length)
        s += "  SOP class: ={0!s}\n".format(self.sop_class_uid.name)
        s += "  Service class UID length: {0:d} bytes\n".format(
            self.service_class_uid_length)
        s += "  Service class UID: ={0!s}\n".format(self.service_class_uid.name)
        s += "  Related general SOP class ID length: {0:d} bytes\n".format(
            self.related_general_sop_class_identification_length)
        s += "  Related general SOP class ID(s):\n"

        for ii in self.related_general_sop_class_identification:
            s += "    ={0!s} ({1!s})\n".format(ii.name, ii.title())

        return s

    def _wrap_generate_items(self, bytestream):
        """Return a list of UID items generated from `bytestream`."""
        item_list = []
        for uid in self._generate_items(bytestream):
            item_list.append(uid)

        return item_list

    def _wrap_list(self, uid_list):
        bytestream = bytes()
        for uid in uid_list:
            bytestream += PACK_UINT2(len(uid))
            bytestream += self._wrap_ascii(uid)

        return bytestream

# FIXME: decode
class UserIdentitySubItemRQ(PDUItem):
    """
    Represents the User Identity RQ Sub Item used in A-ASSOCIATE-RQ PDUs.

    The User Identity RQ Sub Item requires the following
    parameters (see PS3.7 Annex D.3.3.7.1):

        * Item type (1, fixed, 0x58)
        * Item length (1)
        * User identity type (1)
        * Positive response requested (1)
        * Primary field length (1)
        * Primary field (1)
        * Secondary field length (1)
        * Secondary field (1, only if user identity type = 2)

    See PS3.7 Annex D.3.3.7.1 for the structure of the item, especially
    Table D.3-14.

    Used in A_ASSOCIATE_RQ - Variable items - User Information - User Data

    Attributes
    ----------
    id_type : int
        The user identity type [1, 2, 3, 4]
    id_type_str : str
        The user identity type as a string ['Username', 'Username/Password',
        'Kerberos', 'SAML']
    length : int
        The length of the encoded Item in bytes
    primary : bytes
        The value of the primary field
    response_requested : bool
        True if a positive response is requested, False otherwise
    secondary : bytes or None
        The value of the secondary field, None if not used
    """

    def __init__(self):
        self.user_identity_type = None
        self.positive_response_requested = None
        self._primary_length = None
        self.primary_field = None
        self._secondary_length = None
        self.secondary_field = b''

    def FromParams(self, primitive):
        """
        Set up the Item using the parameter values from the `primitive`

        Parameters
        ----------
        primitive : pynetdicom3.pdu_primitives.UserIdentityParameters
                    The primitive to use when setting up the Item
        """
        self.user_identity_type = primitive.user_identity_type
        self.positive_response_requested = \
            int(primitive.positive_response_requested)
        self.primary_field = primitive.primary_field
        self.secondary_field = primitive.secondary_field

    def ToParams(self):
        """
        Convert the current Item to a primitive

        Returns
        -------
        pynetdicom3.pdu_primitives.UseIdentityParameters
            The primitive to convert to
        """
        from pynetdicom3.pdu_primitives import UserIdentityNegotiation

        primitive = UserIdentityNegotiation()
        primitive.user_identity_type = self.user_identity_type
        primitive.positive_response_requested = \
            bool(self.positive_response_requested)
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
            self._wrap_slice,
            []
        )

        yield (
            (10 + self._primary_length, None),
            'secondary_field',
            self._wrap_slice,
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
        """
        See PS3.7 D3.3.7

        Returns
        -------
        int
            1: Username as utf-8 string,
            2: Username as utf-8 string and passcode
            3: Kerberos Service ticket
            4: SAML Assertion
        """
        return self.user_identity_type

    @property
    def id_type_str(self):
        """Get a string of the ID type"""
        id_types = {1: 'Username',
                    2: 'Username/Password',
                    3: 'Kerberos',
                    4: 'SAML'}

        return id_types[self.user_identity_type]

    @property
    def item_length(self):
        """Return the Item Length parameter value."""
        return 6 + self.primary_field_length + self.secondary_field_length

    @property
    def item_type(self):
        """Return the item type as an int."""
        return 0x58

    def __len__(self):
        """Return the total encoded length of the item."""
        return 4 + self.item_length

    @property
    def primary(self):
        """Get the primary field"""
        return self.primary_field

    @property
    def primary_field_length(self):
        """Return the 'Primary Field Length' parameter value."""
        return len(self.primary_field)

    @property
    def response_requested(self):
        """Get the response requested"""
        return bool(self.positive_response_requested)

    @property
    def secondary(self):
        """Get the secondary field"""
        return self.secondary_field

    @property
    def secondary_field_length(self):
        """Return the 'Secondary Field Length' parameter value."""
        if self.secondary_field:
            return len(self.secondary_field)

        return 0x00

    def __str__(self):
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
    """
    Represents the User Identity RQ Sub Item used in A-ASSOCIATE-RQ PDUs.

    The User Identity AC Sub Item requires the following parameters
    (see PS3.7 Annex D.3.3.7.2):

        * Item type (1, fixed, 0x59)
        * Item length (1)
        * Server response length (1)
        * Server response (1)

    See PS3.7 Annex D.3.3.7.2 for the structure of the item, especially
    Table D.3-15.

    Used in A_ASSOCIATE_AC - Variable items - User Information - User Data

    Attributes
    ----------
    length : int
        The length of the encoded Item in bytes
    response : bytes
        The value for the server response. For user identity type value of
          * 1: b''
          * 2: b''
          * 3: the Kerberos server ticket, encoded as per RFC-1510
          * 4: the SAML response

    TODO: Add user interface - setter for server_response
    """

    def __init__(self):
        self.server_response = None

    def FromParams(self, primitive):
        """
        Set up the Item using the parameter values from the `primitive`

        Parameters
        ----------
        primitive : pynetdicom3.pdu_primitives.UserIdentityParameters
            The primitive to use when setting up the Item
        """
        self.server_response = primitive.server_response

    def ToParams(self):
        """
        Convert the current Item to a primitive

        Returns
        -------
        pynetdicom3.pdu_primitives.UseIdentityParameters
            The primitive to convert to
        """
        from pynetdicom3.pdu_primitives import UserIdentityNegotiation

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
            ((6, None), 'server_response', self._wrap_slice, []),
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
        """Return the Item Length parameter value."""
        return 2 + self.server_response_length

    @property
    def item_type(self):
        """Return the item type as an int."""
        return 0x59

    def __len__(self):
        """Return the total encoded length of the item."""
        return 4 + self.item_length

    @property
    def response(self):
        """Get the response"""
        return self.server_response

    @property
    def server_response_length(self):
        """Return the "Server Response Length" parameter value."""
        return len(self.server_response)

    def __str__(self):
        s = "User Identity (AC) Sub-item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        s += "  Server response length: {0:d} bytes\n".format(
            self.server_response_length)
        s += "  Server response: {0!s}\n".format(self.server_response)

        return s


## P-DATA-TF Item
class PresentationDataValueItem(PDUItem):
    """
    Represents a Presentation Data Value Item used in P-DATA-TF PDUs.

    The Presentation Data Value Item requires the following parameters (see
    PS3.8 Section 9.3.5.1):

        * Item length (1)
        * Presentation context ID (1)
        * Presentation data value (1)

    See PS3.8 Section 9.3.5.1 for the structure of the item, especially
    Table 9-23.

    Used in P_DATA_TF - Presentation data value items

    Attributes
    ----------
    data : FIXME
        The presentation data value
    ID : int
        The presentation context ID
    length : int
        The length of the encoded item in bytes
    message_control_header_byte : str
        A string containing the contents of the message control header byte
        formatted as an 8-bit binary. See PS3.8 FIXME
    """

    def __init__(self):
        self.presentation_context_id = None
        self.presentation_data_value = None

    def FromParams(self, primitive):
        """
        Set up the Item using the parameter values from the `primitive`

        Parameters
        ----------
        primitive : list of [int, bytes]
            The Presentation Data as a list [context ID, data]
        """
        self.presentation_context_id = primitive[0]
        self.presentation_data_value = primitive[1]

    def ToParams(self):
        """
        Convert the current Item to a primitive

        Returns
        -------
        list
            The Presentation Data as a list
        """
        return [self.presentation_context_id, self.presentation_data_value]

    @property
    def context_id(self):
        """Get the presentation context ID."""
        return self.presentation_context_id

    @property
    def data(self):
        """Get the presentation data value."""
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
                self._wrap_slice,
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
        """Return the Item Length parameter value."""
        return 1 + len(self.presentation_data_value)

    def __len__(self):
        """Return the total encoded length of the item."""
        return 4 + self.item_length

    @property
    def message_control_header_byte(self):
        """Return the message control header byte as a formatted string."""
        return "{:08b}".format(ord(self.presentation_data_value[0:1]))

    def __str__(self):
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
