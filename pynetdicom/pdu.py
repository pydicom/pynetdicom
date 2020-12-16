"""DICOM Upper Layer Protocol Data Units (PDUs).

There are seven different PDUs:

- A_ASSOCIATE_RQ
- A_ASSOCIATE_AC
- A_ASSOCIATE_RJ
- P_DATA_TF
- A_RELEASE_RQ
- A_RELEASE_RP
- A_ABORT_RQ

::

                  from_primitive               encode
  +----------------+  ------>  +------------+  ----->  +-------------+
  | DUL Primitive  |           |    PDU     |          |   Peer AE   |
  +----------------+  <------  +------------+  <-----  +-------------+
                    to_primitive               decode
"""

import codecs
import logging
from struct import Struct

from pynetdicom.pdu_items import (
    ApplicationContextItem,
    PresentationContextItemRQ,
    PresentationContextItemAC,
    UserInformationItem,
    PresentationDataValueItem,
    PDU_ITEM_TYPES
)
from pynetdicom.utils import validate_ae_title


LOGGER = logging.getLogger('pynetdicom.pdu')

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


class PDU(object):
    """Base class for PDUs.

    Protocol Data Units (PDUs) are the message formats exchanged between peer
    entities within a layer. A PDU consists of protocol control information
    and user data. PDUs are constructed by mandatory fixed fields followed by
    optional variable fields that contain one or more items and/or sub-items.

    References
    ----------
    DICOM Standard, Part 8, :dcm:`Section 9.3 <part08/sect_9.3.html>`
    """

    def decode(self, bytestream):
        """Decode `bytestream` and use the result to set the field values of
        the PDU.

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

            setattr(
                self, attr_name, func(bytestream[sl], *args)
            )

    @property
    def _decoders(self):
        """Return an iterable of tuples that contain field decoders."""
        raise NotImplementedError

    def encode(self):
        """Return the encoded PDU as :class:`bytes`.

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
        """Return ``True`` if `self` equals `other`."""
        if other is self:
            return True

        # pylint: disable=protected-access
        if isinstance(other, self.__class__):
            self_dict = {
                enc[0] : getattr(self, enc[0])
                for enc in self._encoders if enc[0]
            }
            other_dict = {
                enc[0] : getattr(other, enc[0])
                for enc in other._encoders if enc[0]
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
            The variable item's 'Item Type' parameter as int, and the item's
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
        following structure, taken from various tables in (offsets shown
        with Python indexing). Items are always encoded using Big Endian.

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
           :dcm:`Section 9.3.1<part08/sect_9.3.html#sect_9.3.1>`
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

    def __len__(self):
        """Return the total length of the encoded PDU as :class:`int`."""
        return 6 + self.pdu_length

    def __ne__(self, other):
        """Return ``True`` if `self` does not equal `other`."""
        return not self == other

    @property
    def pdu_length(self):
        """Return the *PDU Length* field value as :class:`int`."""
        raise NotImplementedError

    @property
    def pdu_type(self):
        """Return the *PDU Type* field value as :class:`int`."""
        return PDU_TYPES[self.__class__]

    @staticmethod
    def _wrap_bytes(bytestream):
        """Return `bytestream` without changing it."""
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
        String (characters 0-9), with each component separated by '.' (0x2e)
       .

        'ascii' is chosen because this is the codec Python uses for ISO 646
        [3]_.

        Parameters
        ----------
        uid : pydicom.uid.UID
            The UID to encode using ASCII.

        Returns
        -------
        bytes
            The encoded `uid`.

        References
        ----------
        * DICOM Standard, Part 8, :dcm:`Annex F <part08/chapter_F.html>`
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


class A_ASSOCIATE_RQ(PDU):
    """An A-ASSOCIATE-RQ PDU.

    An A-ASSOCIATE-RQ PDU is sent by an association requestor to initiate
    association negotiation with an acceptor.

    Attributes
    ----------
    application_context_name : pydicom.uid.UID or None
        The Application Context Item's *Application Context Name* field value
        (if available).
    called_ae_title : bytes
        The *Called AE Title* field value, which is the destination DICOM
        application name as a fixed length 16-byte value (padded with trailing
        spaces ``0x20``). Leading and trailing spaces are non-significant and a
        value of 16 spaces is not allowed.
    calling_ae_title : bytes
        The *Calling AE Title* field value, which is the destination DICOM
        application name as a fixed length 16-byte value (padded with trailing
        spaces ``0x20``). Leading and trailing spaces are non-significant and a
        value of 16 spaces is not allowed.
    pdu_length : int
        The number of bytes from the first byte following the *PDU Length*
        field to the last byte of the PDU.
    pdu_type : int
        The *PDU Type* field value (``0x01``).
    presentation_context : list of pdu_items.PresentationContextItemRQ
        The *Presentation Context Item(s)*.
    protocol_version : int
        The *Protocol Version* field value (``0x01``).
    user_information : pdu_items.UserInformationItem
        The *User Information Item* (if available).
    variable_items : list
        A list containing the A-ASSOCIATE-RQ's *Variable Items*. Contains
        one Application Context item, one or more Presentation Context items
        and one User Information item. The order of the items is not
        guaranteed.

    Notes
    -----
    An A-ASSOCIATE-RQ PDU requires the following parameters:

    * PDU type (1, fixed value, ``0x01``)
    * PDU length (1)
    * Protocol version (1, default value, ``0x01``)
    * Called AE title (1)
    * Calling AE title (1)
    * Variable items (1)

      * Application Context Item (1)

        * Item type (1, fixed value, ``0x10``)
        * Item length (1)
        * Application Context Name (1, fixed in an application)
      * Presentation Context Item(s) (1 or more)

        * Item type (1, fixed value, ``0x21``)
        * Item length (1)
        * Context ID (1)
        * Abstract/Transfer Syntax Sub-items (1)

          * Abstract Syntax Sub-item (1)

            * Item type (1, fixed, ``0x30``)
            * Item length (1)
            * Abstract syntax name (1)
          * Transfer Syntax Sub-items (1 or more)

            * Item type (1, fixed, ``0x40``)
            * Item length (1)
            * Transfer syntax name(s) (1 or more)
      * User Information Item (1)

        * Item type (1, fixed, ``0x50``)
        * Item length (1)
        * User data Sub-items (2 or more)

            * Maximum Length Received Sub-item (1)
            * Implementation Class UID Sub-item (1)
            * Optional User Data Sub-items (0 or more)

    **Encoding**

    When encoded, an A-ASSOCIATE-RQ PDU has the following structure, taken
    from `Table 9-11<part08/sect_9.3.2.html>` (offsets shown with Python
    indexing). PDUs are always encoded using Big Endian.

    +--------+-------------+------------------+
    | Offset | Length      | Description      |
    +========+=============+==================+
    | 0      | 1           | PDU type         |
    +--------+-------------+------------------+
    | 1      | 1           | Reserved         |
    +--------+-------------+------------------+
    | 2      | 4           | PDU length       |
    +--------+-------------+------------------+
    | 6      | 2           | Protocol version |
    +--------+-------------+------------------+
    | 8      | 2           | Reserved         |
    +--------+-------------+------------------+
    | 10     | 16          | Called AE title  |
    +--------+-------------+------------------+
    | 26     | 16          | Calling AE title |
    +--------+-------------+------------------+
    | 42     | 32          | Reserved         |
    +--------+-------------+------------------+
    | 74     | Variable    | Variable items   |
    +--------+-------------+------------------+

    References
    ----------
    * DICOM Standard, Part 8, Sections :dcm:`9.3.2<part08/sect_9.3.2.html>`
      and :dcm:`9.3.1<part08/sect_9.3.html#sect_9.3.1>`
    """

    def __init__(self):
        """Initialise a new A-ASSOCIATE-RQ PDU."""
        # We allow the user to modify the protocol version if so desired
        self.protocol_version = 0x01
        # Set some default values
        self.called_ae_title = "Default"
        self.calling_ae_title = "Default"

        # `variable_items` is a list containing the following:
        #   1 ApplicationContextItem
        #   1 or more PresentationContextItemRQ
        #   1 UserInformationItem
        # The order of the items in the list may not be as given above
        self.variable_items = []

    def from_primitive(self, primitive):
        """Setup the current PDU using an A-ASSOCIATE (request) primitive.

        Parameters
        ----------
        primitive : pdu_primitives.A_ASSOCIATE
            The primitive to use to set the current PDU field values.
        """
        self.calling_ae_title = primitive.calling_ae_title
        self.called_ae_title = primitive.called_ae_title

        # Add Application Context
        application_context = ApplicationContextItem()
        application_context.application_context_name = (
            primitive.application_context_name
        )
        self.variable_items.append(application_context)

        # Add Presentation Context(s)
        for contexts in primitive.presentation_context_definition_list:
            presentation_context = PresentationContextItemRQ()
            presentation_context.from_primitive(contexts)
            self.variable_items.append(presentation_context)

        # Add User Information
        user_information = UserInformationItem()
        user_information.from_primitive(primitive.user_information)
        self.variable_items.append(user_information)

    def to_primitive(self):
        """Return an A-ASSOCIATE (request) primitive from the current PDU.

        Returns
        -------
        pdu_primitives.A_ASSOCIATE
            The primitive representation of the current PDU.
        """
        from pynetdicom.pdu_primitives import A_ASSOCIATE

        primitive = A_ASSOCIATE()
        primitive.calling_ae_title = self.calling_ae_title
        primitive.called_ae_title = self.called_ae_title
        primitive.application_context_name = self.application_context_name

        for item in self.variable_items:
            # Add presentation contexts
            if isinstance(item, PresentationContextItemRQ):
                primitive.presentation_context_definition_list.append(
                    item.to_primitive())

            # Add user information
            elif isinstance(item, UserInformationItem):
                primitive.user_information = item.to_primitive()

        return primitive

    @property
    def application_context_name(self):
        """Return the *Application Context Name*, if available.

        Returns
        -------
        pydicom.uid.UID or None
            The requestor's *Application Context Name* or None if not
            available.
        """
        for item in self.variable_items:
            if isinstance(item, ApplicationContextItem):
                return item.application_context_name

        return None

    @property
    def called_ae_title(self):
        """Return the *Called AE Title* field value as :class:`bytes`."""
        return self._called_aet

    @called_ae_title.setter
    def called_ae_title(self, ae_title):
        """Set the *Called AE Title* field value.

        Will be converted to a fixed length 16-byte value (padded with trailing
        spaces ``0x20``). Leading and trailing spaces are non-significant and a
        value of 16 spaces is not allowed.

        Parameters
        ----------
        ae_title : str or bytes
            The value you wish to set. A value consisting of spaces is not
            allowed and values longer than 16 characters will be truncated.
        """
        # pylint: disable=attribute-defined-outside-init
        if isinstance(ae_title, str):
            ae_title = codecs.encode(ae_title, 'ascii')

        self._called_aet = validate_ae_title(ae_title)

    @property
    def calling_ae_title(self):
        """Return the *Calling AE Title* field value as :class:`bytes`."""
        return self._calling_aet

    @calling_ae_title.setter
    def calling_ae_title(self, ae_title):
        """Set the *Calling AE Title* field value.

        Will be converted to a fixed length 16-byte value (padded with trailing
        spaces ``0x20``). Leading and trailing spaces are non-significant and a
        value of 16 spaces is not allowed.

        Parameters
        ----------
        ae_title : str or bytes
            The value you wish to set. A value consisting of spaces is not
            allowed and values longer than 16 characters will be truncated.
        """
        # pylint: disable=attribute-defined-outside-init
        if isinstance(ae_title, str):
            ae_title = codecs.encode(ae_title, 'ascii')

        self._calling_aet = validate_ae_title(ae_title)

    @property
    def _decoders(self):
        """Return an iterable of tuples that contain field decoders.

        Returns
        -------
        list of tuple
            A list of ``((offset, length), attr_name, callable, [args])``,
            where:

            - ``offset`` is the byte offset to start at
            - ``length`` is how many bytes to slice (if None then will slice
              to the end of the data),
            - ``attr_name`` is the name of the attribute corresponding to the
              field
            - ``callable`` is a decoding function that returns the decoded
              value
            - ``args`` is a list of arguments to pass ``callable``
        """
        return [
            ((6, 2), 'protocol_version', self._wrap_unpack, [UNPACK_UINT2]),
            ((10, 16), 'called_ae_title', self._wrap_bytes, []),
            ((26, 16), 'calling_ae_title', self._wrap_bytes, []),
            ((74, None), 'variable_items', self._wrap_generate_items, [])
        ]

    @property
    def _encoders(self):
        """Return an iterable of tuples that contain field decoders.

        Returns
        -------
        list of tuple
            A list of ``(attr_name, callable, [args])``, where:

            - ``attr_name`` is the name of the attribute corresponding to the
              field
            - ``callable`` is an encoding function that returns :class:`bytes`
            - ``args`` is a :class:`list` of arguments to pass ``callable``.
        """
        return [
            ('pdu_type', PACK_UCHAR, []),
            (None, self._wrap_pack, [0x00, PACK_UCHAR]),
            ('pdu_length', PACK_UINT4, []),
            ('protocol_version', PACK_UINT2, []),
            (None, self._wrap_pack, [0x0000, PACK_UINT2]),
            ('called_ae_title', self._wrap_bytes, []),
            ('calling_ae_title', self._wrap_bytes, []),
            (None, self._wrap_pack, [0x00, PACK_UINT4]),
            (None, self._wrap_pack, [0x00, PACK_UINT4]),
            (None, self._wrap_pack, [0x00, PACK_UINT4]),
            (None, self._wrap_pack, [0x00, PACK_UINT4]),
            (None, self._wrap_pack, [0x00, PACK_UINT4]),
            (None, self._wrap_pack, [0x00, PACK_UINT4]),
            (None, self._wrap_pack, [0x00, PACK_UINT4]),
            (None, self._wrap_pack, [0x00, PACK_UINT4]),
            ('variable_items', self._wrap_encode_items, [])
        ]

    @property
    def pdu_length(self):
        """Return the *PDU Length* field value as :class:`int`."""
        length = 68
        for item in self.variable_items:
            length += len(item)

        return length

    @property
    def presentation_context(self):
        """Return a list of the Presentation Context items.

        Returns
        -------
        list of pdu_items.PresentationContextItemRQ
            The Presentation Context items.
        """
        return [item for item in self.variable_items if
                isinstance(item, PresentationContextItemRQ)]

    def __str__(self):
        """Return a string representation of the PDU."""
        s = 'A-ASSOCIATE-RQ PDU\n'
        s += '==================\n'
        s += '  PDU type: 0x{0:02x}\n'.format(self.pdu_type)
        s += '  PDU length: {0:d} bytes\n'.format(self.pdu_length)
        s += '  Protocol version: {0:d}\n'.format(self.protocol_version)
        s += '  Called AET:  {0!s}\n'.format(self.called_ae_title)
        s += '  Calling AET: {0!s}\n'.format(self.calling_ae_title)
        s += '\n'

        s += '  Variable Items:\n'
        s += '  ---------------\n'
        s += '  * Application Context Item\n'
        s += '    - Context name: ={0!s}\n'.format(
            self.application_context_name)

        s += '  * Presentation Context Item(s):\n'

        for ii in self.presentation_context:
            item_str = '{0!s}'.format(ii)
            item_str_list = item_str.split('\n')
            s += '    - {0!s}\n'.format(item_str_list[0])
            for jj in item_str_list[1:-1]:
                s += '      {0!s}\n'.format(jj)

        s += '  * User Information Item(s):\n'
        for ii in self.user_information.user_data:
            item_str = '{0!s}'.format(ii)
            item_str_list = item_str.split('\n')
            s += '    - {0!s}\n'.format(item_str_list[0])
            for jj in item_str_list[1:-1]:
                s += '      {0!s}\n'.format(jj)

        return s

    @property
    def user_information(self):
        """Return the User Information Item, if available.

        Returns
        -------
        pdu_items.UserInformationItem or None
            The requestor's User Information object or ``None``, if not
            available.
        """
        for item in self.variable_items:
            if isinstance(item, UserInformationItem):
                return item

        return None


class A_ASSOCIATE_AC(PDU):
    """An A-ASSOCIATE-AC PDU.

    An A-ASSOCIATE-AC PDU is sent by an association acceptor to indicate that
    association negotiation has been successful.

    Attributes
    ----------
    application_context_name : pydicom.uid.UID
        The Application Context Item's *Application Context Name* field value
        (if available).
    called_ae_title : bytes
        The requestor's *Called AE Title* field value, which is the destination
        DICOM application name as a 16-byte value. The value is not
        guaranteed to be the actual title and shall not be tested.
    calling_ae_title : bytes
        The requestor's *Calling AE Title* field value, which is the source
        DICOM application name as a 16-byte value. The value is not
        guaranteed to be the actual title and shall not be tested.
    pdu_length : int
        The number of bytes from the first byte following the *PDU Length*
        field to the last byte of the PDU.
    pdu_type : int
        The *PDU Type* field value (``0x02``).
    presentation_context : list of pdu_items.PresentationContextItemAC
        The *Presentation Context Item(s)*.
    protocol_version : int
        The *Protocol Version* field value (default ``0x01``).
    user_information : pdu_items.UserInformationItem
        The *User Information Item* (if available).
    variable_items : list
        A list containing the A-ASSOCIATE-AC's 'Variable Items'. Contains
        one Application Context item, one or more Presentation Context items
        and one User Information item. The order of the items is not
        guaranteed.

    Notes
    -----
    An A-ASSOCIATE-AC PDU requires the following parameters:

    * PDU type (1, fixed value, ``0x02``)
    * PDU length (1)
    * Protocol version (1, default value, ``0x01``)
    * Variable items (1)

      * Application Context Item (1)

        * Item type (1, fixed value, ``0x10``)
        * Item length (1)
        * Application Context Name (1, fixed in an application)
      * Presentation Context Item(s) (1 or more)

        * Item type (1, fixed value, ``0x21``)
        * Item length (1)
        * Context ID (1)
        * Result/reason (1)
        * Transfer Syntax Sub-items (1)

          * Item type (1, fixed, ``0x40``)
          * Item length (1)
          * Transfer syntax name(s) (1)
      * User Information Item (1)

        * Item type (1, fixed, ``0x50``)
        * Item length (1)
        * User data Sub-items (2 or more)

            * Maximum Length Received Sub-item (1)
            * Implementation Class UID Sub-item (1)
            * Optional User Data Sub-items (0 or more)

    **Encoding**

    When encoded, an A-ASSOCIATE-AC PDU has the following structure, taken
    from Table 9-17 (offsets shown with Python indexing). PDUs are always
    encoded using Big Endian.

    +--------+-------------+------------------+
    | Offset | Length      | Description      |
    +========+=============+==================+
    | 0      | 1           | PDU type         |
    +--------+-------------+------------------+
    | 1      | 1           | Reserved         |
    +--------+-------------+------------------+
    | 2      | 4           | PDU length       |
    +--------+-------------+------------------+
    | 6      | 2           | Protocol version |
    +--------+-------------+------------------+
    | 8      | 2           | Reserved         |
    +--------+-------------+------------------+
    | 10     | 16          | Reserved^        |
    +--------+-------------+------------------+
    | 26     | 16          | Reserved^        |
    +--------+-------------+------------------+
    | 42     | 32          | Reserved         |
    +--------+-------------+------------------+
    | 74     | Variable    | Variable items   |
    +--------+-------------+------------------+

    ^ The reserved fields shall be sent with a value identical to the value
    received in the A-ASSOCIATE-RQ but their values shall not be tested.

    References
    ----------
    * DICOM Standard, Part 8,
      :dcm:`Section 9.3.3 <part08/sect_9.3.3.html>`
    * DICOM Standard, Part 8,
      :dcm:`Section 9.3.1<part08/sect_9.3.html#sect_9.3.1>`
    """

    def __init__(self):
        """Initialise a new A-ASSOCIATE-AC PDU."""
        # We allow the user to modify the protocol version if so desired
        self.protocol_version = 0x01
        # Called AE Title, should be present, but no guarantees
        self._reserved_aet = None
        # Calling AE Title, should be present, but no guarantees
        self._reserved_aec = None

        # `variable_items` is a list containing the following:
        #   1 ApplicationContextItem
        #   1 or more PresentationContextItemAC
        #   1 UserInformationItem
        # The order of the items in the list may not be as given above
        self.variable_items = []

    def from_primitive(self, primitive):
        """Setup the current PDU using an A-ASSOCIATE (accept) primitive.

        Parameters
        ----------
        primitive : pdu_primitives.A_ASSOCIATE
            The primitive to use to set the current PDU field values.
        """
        self._reserved_aet = primitive.called_ae_title
        self._reserved_aec = primitive.calling_ae_title

        # Make application context
        application_context = ApplicationContextItem()
        application_context.application_context_name = (
            primitive.application_context_name
        )
        self.variable_items.append(application_context)

        # Make presentation contexts
        for ii in primitive.presentation_context_definition_results_list:
            presentation_context = PresentationContextItemAC()
            presentation_context.from_primitive(ii)
            self.variable_items.append(presentation_context)

        # Make user information
        user_information = UserInformationItem()
        user_information.from_primitive(primitive.user_information)
        self.variable_items.append(user_information)

    def to_primitive(self):
        """Return an A-ASSOCIATE (accept) primitive from the current PDU.

        Returns
        -------
        pdu_primitives.A_ASSOCIATE
            The primitive representation of the current PDU.
        """
        from pynetdicom.pdu_primitives import A_ASSOCIATE

        primitive = A_ASSOCIATE()

        # The two reserved parameters at byte offsets 11 and 27 shall be set
        #    to called and calling AET byte the value shall not be
        #   tested when received (PS3.8 Table 9-17)
        primitive.called_ae_title = self._reserved_aet
        primitive.calling_ae_title = self._reserved_aec

        for item in self.variable_items:
            # Add application context
            if isinstance(item, ApplicationContextItem):
                primitive.application_context_name = (
                    item.application_context_name
                )

            # Add presentation contexts
            elif isinstance(item, PresentationContextItemAC):
                primitive.presentation_context_definition_results_list.append(
                    item.to_primitive()
                )

            # Add user information
            elif isinstance(item, UserInformationItem):
                primitive.user_information = item.to_primitive()

        # 0x00 = Accepted
        primitive.result = 0x00

        return primitive

    @property
    def application_context_name(self):
        """Return the *Application Context Name*, if available.

        Returns
        -------
        pydicom.uid.UID or None
            The acceptor's *Application Context Name* or None if not available.
        """
        for item in self.variable_items:
            if isinstance(item, ApplicationContextItem):
                return item.application_context_name

        return None

    @property
    def called_ae_title(self):
        """Return the value sent in the *Called AE Title* reserved space.

        While the standard says this value should match the A-ASSOCIATE-RQ
        value there is no guarantee and this should not be used as a check
        value.

        Returns
        -------
        bytes
            The value the A-ASSOCIATE-AC sent in the *Called AE Title* reserved
            space.
        """
        if isinstance(self._reserved_aet, str):
            return codecs.encode(self._reserved_aet, 'ascii')

        return self._reserved_aet

    @property
    def calling_ae_title(self):
        """Return the value sent in the *Calling AE Title* reserved space.

        While the standard says this value should match the A-ASSOCIATE-RQ
        value there is no guarantee and this should not be used as a check
        value.

        Returns
        -------
        bytes
            The value the A-ASSOCIATE-AC sent in the *Calling AE Title*
            reserved space.
        """
        if isinstance(self._reserved_aec, str):
            return codecs.encode(self._reserved_aec, 'ascii')

        return self._reserved_aec

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
            ((6, 2), 'protocol_version', self._wrap_unpack, [UNPACK_UINT2]),
            ((10, 16), '_reserved_aet', self._wrap_bytes, []),
            ((26, 16), '_reserved_aec', self._wrap_bytes, []),
            ((74, None), 'variable_items', self._wrap_generate_items, [])
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
            ('pdu_type', PACK_UCHAR, []),
            (None, self._wrap_pack, [0x00, PACK_UCHAR]),
            ('pdu_length', PACK_UINT4, []),
            ('protocol_version', PACK_UINT2, []),
            (None, self._wrap_pack, [0x0000, PACK_UINT2]),
            ('_reserved_aet', self._wrap_bytes, []),
            ('_reserved_aec', self._wrap_bytes, []),
            (None, self._wrap_pack, [0x00, PACK_UINT4]),
            (None, self._wrap_pack, [0x00, PACK_UINT4]),
            (None, self._wrap_pack, [0x00, PACK_UINT4]),
            (None, self._wrap_pack, [0x00, PACK_UINT4]),
            (None, self._wrap_pack, [0x00, PACK_UINT4]),
            (None, self._wrap_pack, [0x00, PACK_UINT4]),
            (None, self._wrap_pack, [0x00, PACK_UINT4]),
            (None, self._wrap_pack, [0x00, PACK_UINT4]),
            ('variable_items', self._wrap_encode_items, [])
        ]

    @property
    def pdu_length(self):
        """Return the *PDU Length* field value as an int."""
        length = 68
        for item in self.variable_items:
            length += len(item)

        return length

    @property
    def presentation_context(self):
        """Return a list of the Presentation Context Items.

        Returns
        -------
        list of pdu_items.PresentationContextItemAC
            The Presentation Context Items.
        """
        return [item for item in self.variable_items if
                isinstance(item, PresentationContextItemAC)]

    def __str__(self):
        """Return a string representation of the PDU."""
        s = 'A-ASSOCIATE-AC PDU\n'
        s += '==================\n'
        s += '  PDU type: 0x{0:02x}\n'.format(self.pdu_type)
        s += '  PDU length: {0:d} bytes\n'.format(self.pdu_length)
        s += '  Protocol version: {0:d}\n'.format(self.protocol_version)
        s += '  Reserved (Called AET):  {0!s}\n'.format(self._reserved_aet)
        s += '  Reserved (Calling AET): {0!s}\n'.format(self._reserved_aec)
        s += '\n'

        s += '  Variable Items:\n'
        s += '  ---------------\n'
        s += '  * Application Context Item\n'
        s += '    -  Context name: ={0!s}\n'.format(
            self.application_context_name)

        s += '  * Presentation Context Item(s):\n'

        for ii in self.presentation_context:
            item_str = '{0!s}'.format(ii)
            item_str_list = item_str.split('\n')
            s += '    -  {0!s}\n'.format(item_str_list[0])
            for jj in item_str_list[1:-1]:
                s += '       {0!s}\n'.format(jj)

        s += '  * User Information Item(s):\n'
        for item in self.user_information.user_data:
            item_str = '{0!s}'.format(item)
            item_str_list = item_str.split('\n')
            s += '    -  {0!s}\n'.format(item_str_list[0])
            for jj in item_str_list[1:-1]:
                s += '       {0!s}\n'.format(jj)

        return s

    @property
    def user_information(self):
        """Return the User Information Item, if available.

        Returns
        -------
        pdu_items.UserInformationItem or None
            The acceptor's User Information object or None, if not available.
        """
        for item in self.variable_items:
            if isinstance(item, UserInformationItem):
                return item

        return None


class A_ASSOCIATE_RJ(PDU):
    """An A-ASSOCIATE-RJ PDU.

    An A-ASSOCIATE-RJ PDU is sent by an association acceptor to indicate that
    association negotiation has been unsuccessful.

    Attributes
    ----------
    pdu_length : int
        The number of bytes from the first byte following the *PDU Length*
        field to the last byte of the PDU.
    pdu_type : int
        The *PDU Type* field value (``0x03``).
    reason_diagnostic : int
        The *Reason/Diagnostic* field value.
    result : int
        The *Result* field value.
    source : int
        The *Source* field value.

    Notes
    -----
    An A-ASSOCIATE-RJ PDU requires the following parameters:

    * PDU type (1, fixed value, ``0x03``)
    * PDU length (1)
    * Result (1)
    * Source (1)
    * Reason/Diagnostic (1)

    **Encoding**

    When encoded, an A-ASSOCIATE-RJ PDU has the following structure, taken
    from Table 9-21 (offsets shown with Python indexing). PDUs are always
    encoded using Big Endian.

    +--------+-------------+-------------------+
    | Offset | Length      | Description       |
    +========+=============+===================+
    | 0      | 1           | PDU type          |
    +--------+-------------+-------------------+
    | 1      | 1           | Reserved          |
    +--------+-------------+-------------------+
    | 2      | 4           | PDU length        |
    +--------+-------------+-------------------+
    | 6      | 1           | Reserved          |
    +--------+-------------+-------------------+
    | 7      | 1           | Result            |
    +--------+-------------+-------------------+
    | 8      | 1           | Source            |
    +--------+-------------+-------------------+
    | 9      | 1           | Reason/diagnostic |
    +--------+-------------+-------------------+

    References
    ----------
    * DICOM Standard, Part 8,
      :dcm:`Section 9.3.4 <part08/sect_9.3.4.html>`
    * DICOM Standard, Part 8,
      :dcm:`Section 9.3.1<part08/sect_9.3.html#sect_9.3.1>`
    """
    def __init__(self):
        """Initialise a new A-ASSOCIATE-RJ PDU."""
        self.result = None
        self.source = None
        self.reason_diagnostic = None

    def from_primitive(self, primitive):
        """Setup the current PDU using an A-ASSOCIATE (reject) primitive.

        Parameters
        ----------
        primitive : pdu_primitives.A_ASSOCIATE
            The primitive to use to set the current PDU field values.
        """
        self.result = primitive.result
        self.source = primitive.result_source
        self.reason_diagnostic = primitive.diagnostic

    def to_primitive(self):
        """Return an A-ASSOCIATE (reject) primitive from the current PDU.

        Returns
        -------
        pdu_primitives.A_ASSOCIATE
            The primitive representation of the current PDU.
        """
        from pynetdicom.pdu_primitives import A_ASSOCIATE

        primitive = A_ASSOCIATE()
        primitive.result = self.result
        primitive.result_source = self.source
        primitive.diagnostic = self.reason_diagnostic

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
            ((7, 1), 'result', self._wrap_unpack, [UNPACK_UCHAR]),
            ((8, 1), 'source', self._wrap_unpack, [UNPACK_UCHAR]),
            ((9, 1), 'reason_diagnostic', self._wrap_unpack, [UNPACK_UCHAR])
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
            ('pdu_type', PACK_UCHAR, []),
            (None, self._wrap_pack, [0x00, PACK_UCHAR]),
            ('pdu_length', PACK_UINT4, []),
            (None, self._wrap_pack, [0x00, PACK_UCHAR]),
            ('result', PACK_UCHAR, []),
            ('source', PACK_UCHAR, []),
            ('reason_diagnostic', PACK_UCHAR, []),
        ]

    @property
    def pdu_length(self):
        """Return the *PDU Length* field value as an int."""
        return 4

    @property
    def reason_str(self):
        """Return a str describing the *Reason/Diagnostic* field value."""
        _reasons = {
            1 : {
                1 : "No reason given",
                2 : "Application context name not supported",
                3 : "Calling AE title not recognised",
                4 : "Reserved",
                5 : "Reserved",
                6 : "Reserved",
                7 : "Called AE title not recognised",
                8 : "Reserved",
                9 : "Reserved",
                10 : "Reserved"
            },
            2 : {
                1 : "No reason given",
                2 : "Protocol version not supported"
            },
            3 : {
                0 : "Reserved",
                1 : "Temporary congestion",
                2 : "Local limit exceeded",
                3 : "Reserved",
                4 : "Reserved",
                5: "Reserved",
                6 : "Reserved",
                7 : "Reserved"
            }
        }

        if self.source not in _reasons:
            LOGGER.error('Invalid value in Source field in '
                         'A-ASSOCIATE-RJ PDU')
            raise ValueError('Invalid value in Source field in '
                             'A-ASSOCIATE-RJ PDU')

        if self.reason_diagnostic not in _reasons[self.source]:
            LOGGER.error('Invalid value in Reason field in '
                         'A-ASSOCIATE-RJ PDU')
            raise ValueError('Invalid value in Reason field in '
                             'A-ASSOCIATE-RJ PDU')

        return _reasons[self.source][self.reason_diagnostic]

    @property
    def result_str(self):
        """Return a str describing the *Result* field value."""
        _results = {
            1 : 'Rejected (Permanent)',
            2 : 'Rejected (Transient)'
        }

        if self.result not in _results:
            LOGGER.error('Invalid value in Result field in '
                         'A-ASSOCIATE-RJ PDU')
            raise ValueError('Invalid value in Result field in '
                             'A-ASSOCIATE-RJ PDU')

        return _results[self.result]

    @property
    def source_str(self):
        """Return a str describing the *Source* field value."""
        _sources = {
            1 : 'DUL service-user',
            2 : 'DUL service-provider (ACSE related)',
            3 : 'DUL service-provider (presentation related)'
        }

        if self.source not in _sources:
            LOGGER.error('Invalid value in Source field in '
                         'A-ASSOCIATE-RJ PDU')
            raise ValueError('Invalid value in Source field in '
                             'A-ASSOCIATE-RJ PDU')

        return _sources[self.source]

    def __str__(self):
        """Return a string representation of the PDU."""
        s = 'A-ASSOCIATE-RJ PDU\n'
        s += '==================\n'
        s += '  PDU type: 0x{0:02x}\n'.format(self.pdu_type)
        s += '  PDU length: {0:d} bytes\n'.format(self.pdu_length)
        s += '  Result: {0!s}\n'.format(self.result_str)
        s += '  Source: {0!s}\n'.format(self.source_str)
        s += '  Reason/Diagnostic: {0!s}\n'.format(self.reason_str)

        return s


# Overridden _generate_items and _wrap_generate_items
class P_DATA_TF(PDU):
    """A P-DATA-TF PDU.

    A P-DATA-TF PDU is used once an association has been established to send
    DIMSE message data.

    Attributes
    ----------
    pdu_length : int
        The number of bytes from the first byte following the *PDU Length*
        field to the last byte of the PDU.
    pdu_type : int
        The *PDU Type* field value (``0x04``).
    presentation_data_value_items : list of pdu.PresentationDataValueItem
        The *Presentation Data Value Item(s)* field value.

    Notes
    -----
    A P-DATA-TF PDU requires the following parameters:

    * PDU type (1, fixed value, ``0x04``)
    * PDU length (1)
    * Presentation data value Item(s) (1 or more)

    **Encoding**

    When encoded, a P-DATA-TF PDU has the following structure, taken
    from Table 9-22 (offsets shown with Python indexing). PDUs are always
    encoded using Big Endian.

    +--------+-------------+-------------------------------+
    | Offset | Length      | Description                   |
    +========+=============+===============================+
    | 0      | 1           | PDU type                      |
    +--------+-------------+-------------------------------+
    | 1      | 1           | Reserved                      |
    +--------+-------------+-------------------------------+
    | 2      | 4           | PDU length                    |
    +--------+-------------+-------------------------------+
    | 6      | Variable    | Presentation data value items |
    +--------+-------------+-------------------------------+

    References
    ----------
    * DICOM Standard, Part 8,
      :dcm:`Section 9.3.5 <part08/sect_9.3.5.html>`
    * DICOM Standard, Part 8,
      :dcm:`Section 9.3.1<part08/sect_9.3.html#sect_9.3.1>`
    """

    def __init__(self):
        """Initialise a new P-DATA-TF PDU."""
        self.presentation_data_value_items = []

    def from_primitive(self, primitive):
        """Setup the current PDU using a P-DATA primitive.

        Parameters
        ----------
        primitive : pdu_primitives.P_DATA
            The primitive to use to set the current PDU field values.
        """
        for item in primitive.presentation_data_value_list:
            presentation_data_value = PresentationDataValueItem()
            presentation_data_value.presentation_context_id = item[0]
            presentation_data_value.presentation_data_value = item[1]
            self.presentation_data_value_items.append(presentation_data_value)

    def to_primitive(self):
        """Return a P-DATA primitive from the current PDU.

        Returns
        -------
        pdu_primitives.P_DATA
            The primitive representation of the current PDU.
        """
        from pynetdicom.pdu_primitives import P_DATA

        primitive = P_DATA()

        primitive.presentation_data_value_list = []
        for item in self.presentation_data_value_items:
            primitive.presentation_data_value_list.append(
                [item.presentation_context_id, item.presentation_data_value]
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
            ((6, None),
             'presentation_data_value_items',
             self._wrap_generate_items,
             [])
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
            ('pdu_type', PACK_UCHAR, []),
            (None, self._wrap_pack, [0x00, PACK_UCHAR]),
            ('pdu_length', PACK_UINT4, []),
            ('presentation_data_value_items', self._wrap_encode_items, [])
        ]

    @staticmethod
    def _generate_items(bytestream):
        """Yield the variable PDV item data from `bytestream`.

        Parameters
        ----------
        bytestream : bytes
            The encoded PDU variable item data.

        Yields
        ------
        int, bytes
            The PDV's Presentation Context ID as int, and the PDV item's
            encoded data as bytes.

        Notes
        -----
        **Encoding**
        When encoded, a Presentation Data Value Item has the following
        structure, taken from Table 9-23 (offset shown with Python
        indexing). The item is encoded using Big Endian, but the encoding of
        of the presentation data message fragments is dependent on the
        negotiated transfer syntax.

        +--------+-------------+-------------------------+
        | Offset | Length      | Description             |
        +========+=============+=========================+
        | 0      | 4           | Item length             |
        +--------+-------------+-------------------------+
        | 4      | 1           | Context ID              |
        +--------+-------------+-------------------------+
        | 5      | NN          | Presentation data value |
        +--------+-------------+-------------------------+

        References
        ----------
        * DICOM Standard, Part 8, :dcm:`Section
          9.3.5.1 <part08/sect_9.3.5.html#sect_9.3.5.1>`
        * DICOM Standard, Part 8,
          :dcm:`Section 9.3.1<part08/sect_9.3.html#sect_9.3.1>`
        """
        offset = 0
        while bytestream[offset:offset + 1]:
            item_length = UNPACK_UINT4(bytestream[offset:offset + 4])[0]
            context_id = UNPACK_UCHAR(bytestream[offset + 4:offset + 5])[0]
            data = bytestream[offset + 5:offset + 4 + item_length]
            assert len(data) == item_length - 1
            yield context_id, data
            # Change `offset` to the start of the next PDV item
            offset += 4 + item_length

    @property
    def pdu_length(self):
        """Return the *PDU Length* field value as an int."""
        length = 0
        for item in self.presentation_data_value_items:
            length += len(item)

        return length

    def __str__(self):
        """Return a string representation of the PDU."""
        s = 'P-DATA-TF PDU\n'
        s += '=============\n'
        s += '  PDU type: 0x{0:02x}\n'.format(self.pdu_type)
        s += '  PDU length: {0:d} bytes\n'.format(self.pdu_length)
        s += '\n'
        s += '  Presentation Data Value Item(s):\n'
        s += '  --------------------------------\n'

        for ii in self.presentation_data_value_items:
            item_str = '{0!s}'.format(ii)
            item_str_list = item_str.split('\n')
            s += '  *  {0!s}\n'.format(item_str_list[0])
            for jj in item_str_list[1:-1]:
                s += '     {0!s}\n'.format(jj)

        return s

    def _wrap_generate_items(self, bytestream):
        """Return a list of PDV Items generated from `bytestream`.

        Parameters
        ----------
        bytestream : bytes
            The encoded presentation data value items.

        Returns
        -------
        list of pdu_items.PresentationDataValueItem
            The presentation data value items contained in `bytestream`.
        """
        item_list = []
        for context_id, data in self._generate_items(bytestream):
            pdv_item = PresentationDataValueItem()
            pdv_item.presentation_context_id = context_id
            pdv_item.presentation_data_value = data
            item_list.append(pdv_item)

        return item_list


class A_RELEASE_RQ(PDU):
    """An A-RELEASE-RQ PDU.

    An A-RELEASE-RQ PDU is used once an association has been established to
    initiate the release of the association.

    Attributes
    ----------
    pdu_length : int
        The number of bytes from the first byte following the *PDU Length*
        field to the last byte of the PDU.
    pdu_type : int
        The *PDU Type* field value (``0x05``).

    Notes
    -----
    An A-RELEASE-RQ PDU requires the following parameters:

    * PDU type (1, fixed value, ``0x05``)
    * PDU length (1, fixed value, 4)

    **Encoding**

    When encoded, an A-RELEASE-RQ PDU has the following structure, taken
    from Table 9-24 (offsets shown with Python indexing). PDUs are always
    encoded using Big Endian.

    +--------+-------------+---------------+
    | Offset | Length      | Description   |
    +========+=============+===============+
    | 0      | 1           | PDU type      |
    +--------+-------------+---------------+
    | 1      | 1           | Reserved      |
    +--------+-------------+---------------+
    | 2      | 4           | PDU length    |
    +--------+-------------+---------------+
    | 6      | 4           | Reserved      |
    +--------+-------------+---------------+

    References
    ----------
    * DICOM Standard, Part 8,
      :dcm:`Section 9.3.6 <part08/sect_9.3.6.html>`
    * DICOM Standard, Part 8,
      :dcm:`Section 9.3.1<part08/sect_9.3.html#sect_9.3.1>`
    """

    def __init__(self):
        """Initialise a new A-RELEASE-RQ PDU."""
        pass

    @staticmethod
    def from_primitive(primitive):
        """Setup the current PDU using an A-RELEASE (request) primitive.

        Parameters
        ----------
        primitive : pdu_primitives.A_RELEASE
            The primitive to use to set the current PDU field values.
        """
        pass

    @staticmethod
    def to_primitive():
        """Return an A-RELEASE (request) primitive from the current PDU.

        Returns
        -------
        pdu_primitives.A_RELEASE
            The primitive representation of the current PDU.
        """
        from pynetdicom.pdu_primitives import A_RELEASE

        return A_RELEASE()

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
        return []

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
            ('pdu_type', PACK_UCHAR, []),
            (None, self._wrap_pack, [0x00, PACK_UCHAR]),
            ('pdu_length', PACK_UINT4, []),
            (None, self._wrap_pack, [0x00, PACK_UINT4])
        ]

    @property
    def pdu_length(self):
        """Return the *PDU Length* field value as an int."""
        return 4

    def __str__(self):
        """Return a string representation of the PDU."""
        s = 'A-RELEASE-RQ PDU\n'
        s += '================\n'
        s += '  PDU type: 0x{0:02x}\n'.format(self.pdu_type)
        s += '  PDU length: {0:d} bytes\n'.format(self.pdu_length)

        return s


class A_RELEASE_RP(PDU):
    """An A-RELEASE-RP PDU.

    An A-RELEASE-RP PDU is used once an association has been established to
    confirm the release of the association.

    Attributes
    ----------
    pdu_length : int
        The number of bytes from the first byte following the *PDU Length*
        field to the last byte of the PDU.
    pdu_type : int
        The *PDU Type* field value (``0x06``).

    Notes
    -----
    An A-RELEASE-RP PDU requires the following parameters:

    * PDU type (1, fixed value, ``0x06``)
    * PDU length (1, fixed value, ``0x00000004``)

    **Encoding**

    When encoded, an A-RELEASE-RP PDU has the following structure, taken
    from Table 9-25 (offsets shown with Python indexing). PDUs are always
    encoded using Big Endian.

    +--------+-------------+---------------+
    | Offset | Length      | Description   |
    +========+=============+===============+
    | 0      | 1           | PDU type      |
    +--------+-------------+---------------+
    | 1      | 1           | Reserved      |
    +--------+-------------+---------------+
    | 2      | 4           | PDU length    |
    +--------+-------------+---------------+
    | 6      | 4           | Reserved      |
    +--------+-------------+---------------+

    References
    ----------
    * DICOM Standard, Part 8,
      :dcm:`Section 9.3.7 <part08/sect_9.3.7.html>`
    * DICOM Standard, Part 8,
      :dcm:`Section 9.3.1<part08/sect_9.3.html#sect_9.3.1>`
    """

    def __init__(self):
        """Initialise a new A-RELEASE-RP PDU."""
        pass

    @staticmethod
    def from_primitive(primitive):
        """Setup the current PDU using an A-release (response) primitive.

        Parameters
        ----------
        primitive : pdu_primitives.A_RELEASE
            The primitive to use to set the current PDU field values.
        """
        pass

    @staticmethod
    def to_primitive():
        """Return an A-RELEASE (response) primitive from the current PDU.

        Returns
        -------
        pdu_primitives.A_RELEASE
            The primitive representation of the current PDU.
        """
        from pynetdicom.pdu_primitives import A_RELEASE

        primitive = A_RELEASE()
        primitive.result = 'affirmative'

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
        return []

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
            ('pdu_type', PACK_UCHAR, []),
            (None, self._wrap_pack, [0x00, PACK_UCHAR]),
            ('pdu_length', PACK_UINT4, []),
            (None, self._wrap_pack, [0x00, PACK_UINT4])
        ]

    @property
    def pdu_length(self):
        """Return the *PDU Length* field value as an int."""
        return 4

    def __str__(self):
        """Return a string representation of the PDU."""
        s = 'A-RELEASE-RP PDU\n'
        s += '================\n'
        s += '  PDU type: 0x{0:02x}\n'.format(self.pdu_type)
        s += '  PDU length: {0:d} bytes\n'.format(self.pdu_length)

        return s


class A_ABORT_RQ(PDU):
    """An A-ABORT-RQ PDU.

    An A-ABORT-RQ PDU is used to abort the association.

    Attributes
    ----------
    pdu_length : int
        The number of bytes from the first byte following the *PDU Length*
        field to the last byte of the PDU.
    pdu_type : int
        The *PDU Type* field value (``0x07``).
    reason_diagnostic : int
        The *Reason/Diagnostic* field value.
    source : int
        The *Source* field value.

    Notes
    -----
    An A-ABORT-RQ PDU requires the following parameters:

    * PDU type (1, fixed value, ``0x06``)
    * PDU length (1, fixed value, 4)
    * Source (1)
    * Reason/Diagnostic (1)

    **Encoding**

    When encoded, an A-ABORT-RQ PDU has the following structure, taken
    from Table 9-26 (offsets shown with Python indexing). PDUs are always
    encoded using Big Endian.

    +--------+-------------+-------------------+
    | Offset | Length      | Description       |
    +========+=============+===================+
    | 0      | 1           | PDU type          |
    +--------+-------------+-------------------+
    | 1      | 1           | Reserved          |
    +--------+-------------+-------------------+
    | 2      | 4           | PDU length        |
    +--------+-------------+-------------------+
    | 6      | 1           | Reserved          |
    +--------+-------------+-------------------+
    | 7      | 1           | Reserved          |
    +--------+-------------+-------------------+
    | 8      | 1           | Source            |
    +--------+-------------+-------------------+
    | 9      | 1           | Reason/Diagnostic |
    +--------+-------------+-------------------+

    References
    ----------
    * DICOM Standard, Part 8,
      :dcm:`Section 9.3.8 <part08/sect_9.3.8.html>`
    * DICOM Standard, Part 8,
      :dcm:`Section 9.3.1<part08/sect_9.3.html#sect_9.3.1>`
    """

    def __init__(self):
        """Initialise a new A-ABORT-RQ PDU."""
        self.source = None
        self.reason_diagnostic = None

    def from_primitive(self, primitive):
        """Setup the current PDU using an A-ABORT or A-P-ABORT primitive.

        Parameters
        ----------
        primitive : pdu_primitives.A_ABORT or pdu_primitives.A_P_ABORT
            The primitive to use to set the current PDU field values.
        """
        from pynetdicom.pdu_primitives import A_ABORT, A_P_ABORT

        # User initiated abort
        if primitive.__class__ == A_ABORT:
            # The reason field shall be 0x00 when the source is DUL
            # service-user
            self.reason_diagnostic = 0
            self.source = primitive.abort_source

        # User provider primitive abort
        elif primitive.__class__ == A_P_ABORT:
            self.reason_diagnostic = primitive.provider_reason
            self.source = 2

    def to_primitive(self):
        """Return an A-ABORT or A-P-ABORT primitive from the current PDU.

        Returns
        -------
        pdu_primitives.A_ABORT or pdu_primitives.A_P_ABORT
            The primitive representation of the current PDU.
        """
        from pynetdicom.pdu_primitives import A_ABORT, A_P_ABORT

        if self.source == 0x02:
            # User provider primitive abort
            primitive = A_P_ABORT()
            primitive.provider_reason = self.reason_diagnostic
        else:
            # User initiated abort and undefined abort source
            primitive = A_ABORT()
            primitive.abort_source = self.source


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
            ((8, 1), 'source', self._wrap_unpack, [UNPACK_UCHAR]),
            ((9, 1), 'reason_diagnostic', self._wrap_unpack, [UNPACK_UCHAR])
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
            ('pdu_type', PACK_UCHAR, []),
            (None, self._wrap_pack, [0x00, PACK_UCHAR]),
            ('pdu_length', PACK_UINT4, []),
            (None, self._wrap_pack, [0x00, PACK_UCHAR]),
            (None, self._wrap_pack, [0x00, PACK_UCHAR]),
            ('source', PACK_UCHAR, []),
            ('reason_diagnostic', PACK_UCHAR, []),
        ]

    @property
    def pdu_length(self):
        """Return the *PDU Length* field value as an int."""
        return 4

    def __str__(self):
        """Return a string representation of the PDU."""
        s = "A-ABORT PDU\n"
        s += "===========\n"
        s += "  PDU type: 0x{0:02x}\n".format(self.pdu_type)
        s += "  PDU length: {0:d} bytes\n".format(self.pdu_length)
        s += "  Abort Source: {0!s}\n".format(self.source_str)
        s += "  Reason/Diagnostic: {0!s}\n".format(self.reason_str)

        return s

    @property
    def source_str(self):
        """Return a str description of the *Source* field value."""
        _sources = {
            0 : 'DUL service-user',
            1 : 'Reserved',
            2 : 'DUL service-provider'
        }

        return _sources[self.source]

    @property
    def reason_str(self):
        """Return a str description of the *Reason/Diagnostic* field value."""
        if self.source == 2:
            _reason_str = {
                0 : "No reason given",
                1 : "Unrecognised PDU",
                2 : "Unexpected PDU",
                3 : "Reserved",
                4 : "Unrecognised PDU parameter",
                5 : "Unexpected PDU parameter",
                6 : "Invalid PDU parameter value"
            }
            return _reason_str[self.reason_diagnostic]

        return 'No reason given'


# PDUs indexed by their class
PDU_TYPES = {
    A_ASSOCIATE_RQ : 0x01,
    A_ASSOCIATE_AC : 0x02,
    A_ASSOCIATE_RJ : 0x03,
    P_DATA_TF : 0x04,
    A_RELEASE_RQ : 0x05,
    A_RELEASE_RP : 0x06,
    A_ABORT_RQ : 0x07,
}
