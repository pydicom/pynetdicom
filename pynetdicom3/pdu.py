"""
Implementation of Dicom Standard, PS 3.8, section 9.3
Dicom Upper Layer Protocol for TCP/IP
Data Unit Structure

There are seven different PDUs
    A_ASSOCIATE_RQ
    A_ASSOCIATE_AC
    A_ASSOCIATE_RJ
    P_DATA_TF
    A_RELEASE_RQ
    A_RELEASE_RP
    A_ABORT_RQ

    All PDU classes implement the following methods:

      FromParams(DULServiceParameterObject):  Builds a PDU from a
                                              DULServiceParameter object.
                                              Used when receiving primitives
                                              from the DULServiceUser.
      ToParams()                   :  Convert the PDU into a
                                      DULServiceParameter object.
                                      Used for sending primitives to
                                      the DULServiceUser.
      Encode()                     :  Returns the encoded PDU as a string,
                                      ready to be sent over the net.
      Decode(bytestream)           :  Construct PDU from `bytestream`.
                                      Used for reading PDU's from the peer.

::

                        FromParams                 Encode
  +--------------------+  ------>  +------------+  ----->  +------------+
  | Service Primitive  |           |    PDU     |          |    Peer    |
  +--------------------+  <------  +------------+  <-----  +------------+
                         ToParams                  Decode


TODO: Make encoding/decoding more generic
"""

import codecs
from io import BytesIO
import logging
from struct import pack, unpack, Struct, pack_into, unpack_from

from pydicom.uid import UID

from pynetdicom3.presentation import PresentationContext
from pynetdicom3.utils import pretty_bytes, validate_ae_title


LOGGER = logging.getLogger('pynetdicom3.pdu')

# Predefine some structs to make decoding and encoding faster
UCHAR = Struct('B')
UINT2 = Struct('>H')
UINT4 = Struct('>I')

UNPACK_UCHAR = UCHAR.unpack
UNPACK_UINT2 = UINT2.unpack
UNPACK_UINT4 = UINT4.unpack

STRUCT_ASSOC = Struct('> B B I H H 16s 16s 32s')


# PDU classes
class PDU(object):
    """Base class for PDUs.

    Protocol Data Units (PDUs) are the message formats exchanged between peer
    entities within a layer. A PDU consists of protocol control information
    and user data. PDUs are constructed by mandatory fixed fields followed by
    optional variable fields that contain one or more items and/or sub-items.

    References
    ----------
    DICOM Standard, Part 8, `Section 9.3 <http://dicom.nema.org/medical/dicom/current/output/html/part08.html#sect_9.3>`_
    """
    __hash__ = None

    def __init__(self):
        self.formats = None
        self.parameters = None

    def __eq__(self, other):
        """Return True if self equals other."""
        if isinstance(other, self.__class__):
            return other.__dict__ == self.__dict__

        return False

    def __ne__(self, other):
        """Return True if self does not equal other."""
        return not self == other

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
        for dest, (start, stop), (func, args) in zip(self._parameters,
                                                     self._offsets,
                                                     self._decoders):
            if func:
                setattr(self, dest, func(bytestream[start:stop], *args))

    def encode(self):
        """
        Encode the DUL

        Returns
        -------
        bytes
            The encoded PDU
        """
        no_formats = len(self.formats)

        # If a parameter is already a bytestream then determine its length
        #   and update the format
        for (ii, ff) in enumerate(self.formats):
            if ff == 's':
                if isinstance(self.parameters[ii], UID):
                    self.parameters[ii] = \
                        codecs.encode(self.parameters[ii].title(), 'utf-8')

                self.formats[ii] = '{0:d}s'.format(len(self.parameters[ii]))
                # Make sure the parameter is a bytes

        # Encode using Big Endian as per PS3.8 9.3.1 - PDU headers are Big
        #   Endian byte ordering while the encoding of PDV message fragments
        #   is defined by the negotiated Transfer Syntax
        pack_format = '> ' + ' '.join(self.formats)

        bytestream = bytes()
        bytestream += pack(pack_format, *self.parameters[:no_formats])

        # When we have more parameters then format we assume that the extra
        #   parameters is a list of objects needing their own encoding
        for ii in self.parameters[no_formats:]:
            if isinstance(ii, list):
                for item in ii:
                    bytestream += item.encode()
            else:
                bytestream += ii.encode()

        return bytestream

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
        """
        # Variable PDU items are:
        #   Application Context Item
        #   Presentation Context Item (RQ/AC)
        #     Abstract Syntax Sub-item
        #     Transfer Syntax Sub-item
        #   User Information Item
        #     Implementation Class UID Sub-item (RQ/AC)
        #     Implementation Version Name Sub-item (RQ/AC)
        #     Asynchronous Operations Window Sub-item (RQ/AC)
        #     SCP/SCU Role Selection Sub-item (RQ/AC)
        #     SOP Class Extended Negotiation Sub-item (RQ/AC)
        #     SOP Class Common Extended Negotiation Sub-item (RQ/AC)
        #     User Identity Sub-item (RQ/AC)
        offset = 0
        while bytestream[offset:offset + 1]:
            item_type = bytestream[offset:offset + 1]
            item_length = UNPACK_UINT2(bytestream[offset + 2:offset + 4])[0]
            item_data = bytestream[offset:offset + 4 + item_length]
            yield item_type, item_data
            # Change `offset` to the start of the next item
            offset += 4 + item_length

    @property
    def item_length(self):
        """Return the 'Item Length' parameter value."""
        raise NotImplementedError

    @property
    def item_type(self):
        """Return the item type as an int."""
        raise NotImplementedError

    @property
    def pdu_length(self):
        """Return the 'PDU Length' parameter value."""
        raise NotImplementedError

    @property
    def pdu_type(self):
        """Return the PDU type as an int."""
        raise NotImplementedError

    @staticmethod
    def _wrap_unpack(bytestream, unpacker):
        """Return the first value when `unpacker` is run on `bytestream`.

        Parameters
        ----------
        bytestream : bytes
            The encoded data to unpack.
        unpacker : callable
            A callable function to use to unpack the data in bytestream.
            Example: struct.Struct('>I').unpack
        """
        return unpacker(bytestream)[0]

    @staticmethod
    def _wrap_slice(bytestream):
        """Return `bytestream`."""
        return bytestream

    def _wrap_generate_items(self, bytestream):
        """Return a list of PDU items generated from `bytestream`."""
        item_list = []
        for item_type, item_bytes in self._generate_items(bytestream):
            item = PDU_ITEM_TYPES[item_type[0]]()
            item.decode(item_bytes)
            item_list.append(item)

        return item_list


class A_ASSOCIATE_RQ(PDU):
    """An A-ASSOCIATE-RQ PDU.

    When encoded, is received from/sent to the peer AE.

    The A-ASSOCIATE-RQ PDU is sent at the start of association negotiation when
    either the local or the peer AE wants to to request an association.

    An A-ASSOCIATE-RQ requires the following parameters (see PS3.8 Section
    9.3.2):

    * PDU type (1, fixed value, 0x01)
    * PDU length (1)
    * Protocol version (1, fixed value, 0x01)
    * Called AE title (1)
    * Calling AE title (1)
    * Variable items (1)

      * Application Context Item (1)
        * Item type (1, fixed value, 0x10)
        * Item length (1)
        * Application Context Name (1, fixed in an application)
      * Presentation Context Item(s) (1 or more)

        * Item type (1, fixed value, 0x21)
        * Item length (1)
        * Context ID (1)
        * Abstract/Transfer Syntax Sub-items (1)

          * Abstract Syntax Sub-item (1)
            * Item type (1, fixed, 0x30)
            * Item length (1)
            * Abstract syntax name (1)
          * Transfer Syntax Sub-items (1 or more)
            * Item type (1, fixed, 0x40)
            * Item length (1)
            * Transfer syntax name(s) (1 or more)
      * User Information Item (1)

        * Item type (1, fixed, 0x50)
        * Item length (1)
        * User data Sub-items (2 or more)

            * Maximum Length Received Sub-item (1)
            * Implementation Class UID Sub-item (1)
            * Optional User Data Sub-items (0 or more)

    See PS3.8 Section 9.3.2 for the structure of the PDU, especially Table 9-11.

    Attributes
    ----------
    application_context_name : pydicom.uid.UID
        The Association Requestor's Application Context Name as a UID. See
        PS3.8 9.3.2, 7.1.1.2
    called_ae_title : bytes
        The destination AE title as a 16-byte bytestream.
    calling_ae_title : bytes
        The source AE title as a 16-byte bytestream.
    length : int
        The length of the encoded PDU in bytes
    presentation_context : list of pynetdicom3.pdu.PresentationContextItemRQ
        The A-ASSOCIATE-RQ's Presentation Context items
    user_information : pynetdicom3.pdu.UserInformationItem
        The A-ASSOCIATE-RQ's User Information item. See PS3.8 9.3.2, 7.1.1.6
    """

    def __init__(self):
        self.protocol_version = 0x01
        self.called_ae_title = "Default"
        self.calling_ae_title = "Default"

        # `variable_items` is a list containing the following:
        #   1 ApplicationContextItem
        #   1 or more PresentationContextItemRQ
        #   1 UserInformationItem
        # The order of the items in the list may not be as given above
        self.variable_items = []


        #  Used internally for decoding and encoding
        self._offsets = [(0, 1),  # PDU type
                         (1, 2),  # Reserved
                         (2, 6),  # PDU length
                         (6, 8),  # Protocol version
                         (8, 10),  # Reserved
                         (10, 26),  # Called AE title
                         (26, 42),  # Calling AE title
                         (42, 74),  # Reserved
                         (74, None)]  # Variable items
        self._decoders = [(None, []),
                          (None, []),
                          (None, []),
                          (self._wrap_unpack, [UNPACK_UINT2]),
                          (None, []),
                          (self._wrap_slice, []),
                          (self._wrap_slice, []),
                          (None, []),
                          (self._wrap_generate_items, [])]

    def FromParams(self, primitive):
        """Setup the current PDU using an A-ASSOCIATE `primitive`.

        Parameters
        ----------
        primitive : pynetdicom3.pdu_primitives.A_ASSOCIATE
            The primitive to use for setting up the current PDU.
        """
        self.calling_ae_title = primitive.calling_ae_title
        self.called_ae_title = primitive.called_ae_title

        # Make Application Context
        application_context = ApplicationContextItem()
        application_context.FromParams(primitive.application_context_name)
        self.variable_items.append(application_context)

        # Make Presentation Context(s)
        for contexts in primitive.presentation_context_definition_list:
            presentation_context = PresentationContextItemRQ()
            presentation_context.FromParams(contexts)
            self.variable_items.append(presentation_context)

        # Make User Information
        user_information = UserInformationItem()
        user_information.FromParams(primitive.user_information)
        self.variable_items.append(user_information)

    def from_primitive(self, primitive):
        return self.FromParams(primitive)

    def ToParams(self):
        """Return an A-ASSOCIATE primitive repesentation of the current PDU.

        Returns
        -------
        pynetdicom3.pdu_primitives.A_ASSOCIATE
            The primitive representation of the current PDU.
        """
        from pynetdicom3.pdu_primitives import A_ASSOCIATE

        primitive = A_ASSOCIATE()
        primitive.calling_ae_title = self.calling_ae_title
        primitive.called_ae_title = self.called_ae_title
        primitive.application_context_name = self.application_context_name

        for item in self.variable_items:
            # Add presentation contexts
            if isinstance(item, PresentationContextItemRQ):
                primitive.presentation_context_definition_list.append(
                    item.ToParams())

            # Add user information
            elif isinstance(item, UserInformationItem):
                primitive.user_information = item.ToParams()

        return primitive

    def to_primitive(self):
        return self.ToParams()

    def Encode(self):
        """Encode the PDU's parameter values into a bytes string.

        Returns
        -------
        bytestream : bytes
            The encoded PDU that will be sent to the peer AE
        """
        LOGGER.debug('Constructing Associate RQ PDU')

        # Encode the PDU parameters up to the Variable Items
        #   See PS3.8 Table 9-11
        bytestream = bytes()
        bytestream += STRUCT_ASSOC.pack(*self._parameters[:-1])

        # Encode the Variable Items
        for item in self.variable_items:
            bytestream += item.Encode()

        return bytestream

    @property
    def _parameters(self):
        """Return a tuple containing the PDU parameters."""
        return ('pdu_type',  # Fixed, 1 byte
                0x00,  # Reserved, 1 byte
                'pdu_length',  # Variable, 2 bytes
                'protocol_version',  # Fixed, 2 bytes
                0x0000,  # Reserved, 2 bytes
                'called_ae_title',  # Variable, 16 bytes
                'calling_ae_title',  # Variable, 16 bytes
                b'\x00\x00\x00\x00\x00\x00\x00\x00',  # Reserved, 32 bytes
                'variable_items')  # Variable, N bytes

    @property
    def application_context_name(self):
        """Return the application context name."""
        for item in self.variable_items:
            if isinstance(item, ApplicationContextItem):
                return item.application_context_name

    @application_context_name.setter
    def application_context_name(self, value):
        """Set the A-ASSOCIATE-RQ's Application Context Name.

        Parameters
        ----------
        value : pydicom.uid.UID, str or bytes
            The value of the Application Context Name's UID.
        """
        for item in self.variable_items:
            if isinstance(item, ApplicationContextItem):
                item.application_context_name = value

    @property
    def called_ae_title(self):
        """Return the called AE title."""
        return self._called_aet

    @called_ae_title.setter
    def called_ae_title(self, s):
        """Set the Called-AE-title parameter to a 16-byte length byte string.

        Parameters
        ----------
        s : str or bytes
            The called AE title value you wish to set
        """
        # pylint: disable=attribute-defined-outside-init
        if isinstance(s, str):
            s = codecs.encode(s, 'utf-8')

        self._called_aet = validate_ae_title(s)

    @property
    def calling_ae_title(self):
        """Return the calling AE title."""
        return self._calling_aet

    @calling_ae_title.setter
    def calling_ae_title(self, s):
        """Set the Calling-AE-title parameter to a 16-byte length byte string.

        Parameters
        ----------
        s : str or bytes
            The calling AE title value you wish to set
        """
        # pylint: disable=attribute-defined-outside-init
        if isinstance(s, str):
            s = codecs.encode(s, 'utf-8')

        self._calling_aet = validate_ae_title(s)

    def __len__(self):
        """Return the total length of the encoded PDU as an int."""
        return 6 + self.pdu_length

    @property
    def pdu_length(self):
        """Return the 'PDU Length' parameter value as an int."""
        length = 68
        for item in self.variable_items:
            length += len(item)

        return length

    @property
    def pdu_type(self):
        """Return the PDU type as an int."""
        return 0x01

    @property
    def presentation_context(self):
        """
        See PS3.8 9.3.2, 7.1.1.13

        A list of PresentationContextItemRQ. If extended negotiation Role
        Selection is used then the SCP/SCU roles will also be set.

        See the PresentationContextItemRQ and documentation for more information

        Returns
        -------
        list of pynetdicom3.pdu.PresentationContextItemRQ
            The Requestor AE's Presentation Context objects
        """
        contexts = []
        for item in self.variable_items:
            if isinstance(item, PresentationContextItemRQ):
                # We determine if there are any SCP/SCU Role Negotiations
                #   for each Transfer Syntax in each Presentation Context
                #   and if so we set the SCP and SCU attributes.
                if self.user_information.role_selection:
                    # Iterate through the role negotiations looking for a
                    #   SOP Class match to the Abstract Syntax
                    # TODO: optimise
                    role_selection = self.user_information.role_selection
                    if item.abstract_syntax in role_selection:
                        role = role_selection[item.abstract_syntax]
                        item.SCP = role.SCP
                        item.SCU = role.SCU

                contexts.append(item)

        return contexts

    def __str__(self):
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
        """Return the user information item."""
        for item in self.variable_items:
            if isinstance(item, UserInformationItem):
                return item


class A_ASSOCIATE_AC(PDU):
    """
    Represents the A-ASSOCIATE-AC PDU that, when encoded, is received from/sent
    to the peer AE

    The A-ASSOCIATE-AC PDU is sent when the association request is accepted
    by either the local or the peer AE

    An A-ASSOCIATE-AC requires the following parameters (see PS3.8 Section
    9.3.2):

        * PDU type (1, fixed value, 0x02)
        * PDU length (1)
        * Protocol version (1, fixed value, 0x01)
        * Variable items (1)

          * Application Context Item (1)

            * Item type (1, fixed value, 0x10)
            * Item length (1)
            * Application Context Name (1, fixed in an application)
          * Presentation Context Item(s) (1 or more)
            * Item type (1, fixed value, 0x21)
            * Item length (1)
            StorageSOPClassList, \
                                 VerificationSOPClass, \
                                 QueryRetrieveSOPClassList* Context ID (1)
            * Transfer Syntax Sub-items (1)

              * Item type (1, fixed, 0x40)
              * Item length (1)
              * Transfer syntax name(s) (1)
          * User Information Item (1)

            * Item type (1, fixed, 0x50)
            * Item length (1)
            * User data Sub-items (2 or more)

                * Maximum Length Received Sub-item (1)
                * Implementation Class UID Sub-item (1)
                * Optional User Data Sub-items (0 or more)

    See PS3.8 Section 9.3.3 for the structure of the PDU, especially Table 9-17.

    Attributes
    ----------
    application_context_name : pydicom.uid.UID
        The Association Requestor's Application Context Name as a UID. See
        PS3.8 9.3.2, 7.1.1.2
    called_ae_title : bytes
        The destination AE title as a 16-byte bytestream. The value is not
        guaranteed to be the actual title and shall not be tested.
    calling_ae_title : bytes
        The source AE title as a 16-byte bytestream. The value is not
        guaranteed to be the actual title and shall not be tested.
    length : int
        The length of the encoded PDU in bytes
    presentation_context : list of pynetdicom3.pdu.PresentationContextItemAC
        The A-ASSOCIATE-AC's Presentation Context items
    user_information : pynetdicom3.pdu.UserInformationItem
        The A-ASSOCIATE-AC's User Information item. See PS3.8 9.3.2, 7.1.1.6
    """

    def __init__(self):
        # These either have a fixed value or are set programatically
        #'pdu_type' = 0x02
        #self.pdu_length = None
        self.protocol_version = 0x01

        # Shall be set to called AE title value, but no guarantee
        self.reserved_aet = None
        # Shall be set to calling AE title value, but no guarantee
        self.reserved_aec = None

        # variable_items is a list containing the following:
        #   1 ApplicationContextItem
        #   1 or more PresentationContextItemAC
        #   1 UserInformationItem
        # The order of the items in the list may not be as given above
        self.variable_items = []

        #self.formats = ['B', 'B', 'I', 'H', 'H', '16s', '16s',
        #                'I', 'I', 'I', 'I', 'I', 'I', 'I', 'I']

        #  Used internally for decoding and encoding
        self._offsets = [(0, 1),  # PDU type
                         (1, 2),  # Reserved
                         (2, 6),  # PDU length
                         (6, 8),  # Protocol version
                         (8, 10),  # Reserved
                         (10, 26),  # Called AE title
                         (26, 42),  # Calling AE title
                         (42, 74),  # Reserved
                         (74, None)]  # Variable items
        self._decoders = [(None, []),
                          (None, []),
                          (None, []),
                          (self._wrap_unpack, [UNPACK_UINT2]),
                          (None, []),
                          (self._wrap_slice, []),
                          (self._wrap_slice, []),
                          (None, []),
                          (self._wrap_generate_items, [])]

    def FromParams(self, primitive):
        """
        Set up the PDU using the parameter values from the A-ASSOCIATE
        `primitive`

        Parameters
        ----------
        primitive : pynetdicom3.pdu_primitives.A_ASSOCIATE
            The parameters to use for setting up the PDU
        """
        self.reserved_aet = primitive.called_ae_title
        self.reserved_aec = primitive.calling_ae_title

        # Make application context
        application_context = ApplicationContextItem()
        application_context.FromParams(primitive.application_context_name)
        self.variable_items.append(application_context)

        # Make presentation contexts
        for ii in primitive.presentation_context_definition_results_list:
            presentation_context = PresentationContextItemAC()
            presentation_context.FromParams(ii)
            self.variable_items.append(presentation_context)

        # Make user information
        user_information = UserInformationItem()
        user_information.FromParams(primitive.user_information)
        self.variable_items.append(user_information)

        # Compute PDU length parameter value
        self._update_pdu_length()
        self._update_parameters()

    def ToParams(self):
        """
        Convert the current A-ASSOCIATE-AC PDU to a primitive

        Returns
        -------
        pynetdicom3.pdu_primitives.A_ASSOCIATE
            The primitive to convert the PDU to
        """
        from pynetdicom3.pdu_primitives import A_ASSOCIATE

        primitive = A_ASSOCIATE()

        # The two reserved parameters at byte offsets 11 and 27 shall be set
        #    to called and calling AET byte the value shall not be
        #   tested when received (PS3.8 Table 9-17)
        primitive.called_ae_title = self.reserved_aet
        primitive.calling_ae_title = self.reserved_aec

        for ii in self.variable_items:
            # Add application context
            if isinstance(ii, ApplicationContextItem):
                primitive.application_context_name = ii.application_context_name

            # Add presentation contexts
            elif isinstance(ii, PresentationContextItemAC):
                primitive.presentation_context_definition_results_list.append(
                    ii.ToParams())

            # Add user information
            elif isinstance(ii, UserInformationItem):
                primitive.user_information = ii.ToParams()

        # 0x00 = Accepted
        primitive.result = 0x00

        return primitive

    def Encode(self):
        """
        Encode the PDU's parameter values into a bytes string

        Returns
        -------
        bytestream : bytes
            The encoded PDU that will be sent to the peer AE
        """
        if self.presentation_context:
            LOGGER.debug('Constructing Associate AC PDU')

        formats = '> B B I H H 16s 16s 8I'
        parameters = ['pdu_type',
                      0x00,  # Reserved
                      self.pdu_length,
                      self.protocol_version,
                      0x00,  # Reserved
                      self.reserved_aet,
                      self.reserved_aec,
                      0x00, 0x00, 0x00, 0x00,  # Reserved
                      0x00, 0x00, 0x00, 0x00]  # Reserved

        bytestream = bytes()
        bytestream += pack(formats, *parameters)

        for ii in self.variable_items:
            bytestream += ii.Encode()

        return bytestream

    @property
    def application_context_name(self):
        """
        See PS3.8 9.3.2, 7.1.1.2

        Returns
        -------
        pydicom.uid.UID
            The Acceptor AE's Application Context Name
        """
        for ii in self.variable_items:
            if isinstance(ii, ApplicationContextItem):
                return ii.application_context_name

    @property
    def called_ae_title(self):
        """
        While the standard says this value should match the A-ASSOCIATE-RQ
        value there is no guarantee and this should not be used as a check
        value

        Returns
        -------
        bytes
            The Requestor's AE Called AE Title
        """
        ae_title = self.reserved_aet
        if isinstance(ae_title, str):
            ae_title = codecs.encode(self.reserved_aet, 'utf-8')
        elif isinstance(ae_title, bytes):
            pass

        return ae_title

    @property
    def calling_ae_title(self):
        """
        While the standard says this value should match the A-ASSOCIATE-RQ
        value there is no guarantee and this should not be used as a check
        value

        Returns
        -------
        bytes
            The Requestor's AE Calling AE Title
        """
        ae_title = self.reserved_aec
        if isinstance(ae_title, str):
            ae_title = codecs.encode(self.reserved_aec, 'utf-8')
        elif isinstance(ae_title, bytes):
            pass

        return ae_title

    def __len__(self):
        """Return the total length of the encoded PDU as an int."""
        return 6 + self.pdu_length

    @property
    def _parameters(self):
        """Return a tuple containing the PDU parameters."""
        return ('pdu_type',  # Fixed, 1 byte
                0x00,  # Reserved, 1 byte
                'pdu_length',  # Variable, 2 bytes
                'protocol_version',  # Fixed, 2 bytes
                0x00,  # Reserved, 2 bytes
                'reserved_aet',  # Variable, 16 bytes
                'reserved_aec',  # Variable, 16 bytes
                b'\x00\x00\x00\x00\x00\x00\x00\x00',  # Reserved, 32 bytes
                'variable_items')  # Variable, N bytes

    @property
    def pdu_length(self):
        """Return the 'PDU Length' parameter value as an int."""
        length = 68
        for item in self.variable_items:
            length += len(item)

        return length

    @property
    def pdu_type(self):
        """Return the PDU type as an int."""
        return 0x02

    @property
    def presentation_context(self):
        """
        See PS3.8 9.3.2, 7.1.1.13

        Returns
        -------
        list of pynetdicom3.pdu.PresentationContextItemAC

            The Acceptor AE's Presentation Context objects. Each of the
            Presentation Context items instances in the list has been extended
            with two variables for tracking if SCP/SCU role negotiation has been
            accepted:

                SCP: Defaults to None if not used, 0 or 1 if used
                SCU: Defaults to None if not used, 0 or 1 if used
        """
        contexts = []
        for item in self.variable_items:
            if isinstance(item, PresentationContextItemAC):
                # We determine if there are any SCP/SCU Role Negotiations
                #   for each Transfer Syntax in each Presentation Context
                #   and if so we set the SCP and SCU attributes
                if self.user_information.role_selection:
                    # Iterate through the role negotiations looking for a
                    #   SOP Class match to the Abstract Syntaxes
                    #for role in self.user_information.role_selection:
                    # -AC has no Abstract Syntax, not sure how to indicate
                    #   role selection
                    # FIXME
                    pass

                contexts.append(item)

        return contexts

    def __str__(self):
        s = 'A-ASSOCIATE-AC PDU\n'
        s += '==================\n'
        s += '  PDU type: 0x{0:02x}\n'.format(self.pdu_type)
        s += '  PDU length: {0:d} bytes\n'.format(self.pdu_length)
        s += '  Protocol version: {0:d}\n'.format(self.protocol_version)
        s += '  Reserved (Called AET):  {0!s}\n'.format(self.reserved_aet)
        s += '  Reserved (Calling AET): {0!s}\n'.format(self.reserved_aec)
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
        for ii in self.user_information.user_data:
            item_str = '{0!s}'.format(ii)
            item_str_list = item_str.split('\n')
            s += '    -  {0!s}\n'.format(item_str_list[0])
            for jj in item_str_list[1:-1]:
                s += '       {0!s}\n'.format(jj)

        return s

    @property
    def user_information(self):
        """
        See PS3.8 9.3.2, 7.1.1.6

        Returns
        -------
        pynetdicom3.pdu.UserInformationItem
            The Acceptor AE's User Information object
        """
        for ii in self.variable_items:
            if isinstance(ii, UserInformationItem):
                return ii


class A_ASSOCIATE_RJ(PDU):
    """
    Represents the A-ASSOCIATE-RJ PDU that, when encoded, is received from/sent
    to the peer AE.

    The A-ASSOCIATE-RJ PDU is sent during association negotiation when
    either the local or the peer AE rejects the association request.

    An A-ASSOCIATE-RJ requires the following parameters (see PS3.8 Section
        9.3.4):
        * PDU type (1, fixed value, 0x03)
        * PDU length (1)
        * Result (1)
        * Source (1)
        * Reason/Diagnostic (1)

    See PS3.8 Section 9.3.4 for the structure of the PDU, especially Table 9-21.

    Attributes
    ----------
    length : int
        The length of the encoded PDU in bytes
    reason : int
        The raw Reason/Diagnostic parameter value
    reason_str : str
        The reason for the rejection as a string
    result : int
        The raw Result parameter value
    result_str : str
        The result of the rejection, one of ('Rejected (Permanent)',
        'Rejected (Transient)')
    source : int
        The raw Source parameter value
    source_str : str
        The source of the rejection, one of ('DUL service-user',
        'DUL service-provider (ACSE related)', 'DUL service-provider
        (presentation related)')
    """

    def __init__(self):
        self.result = None
        self.source = None
        self.reason_diagnostic = None

        #self.formats = ['B', 'B', 'I', 'B', 'B', 'B', 'B']
        #self.parameters = ['pdu_type',
        #                   0x00,  # Reserved
        #                   self.pdu_length,
        #                   0x00,
        #                   self.result,
        #                   self.source,
        #                   self.reason_diagnostic]
        self._offsets = [(0, 1),  # PDU type
                         (1, 2),  # Reserved
                         (2, 6),  # PDU length
                         (6, 7),  # Reserved
                         (7, 8),  # Result
                         (8, 9),  # Source
                         (9, 10)]  # Reason
        self._decoders = [(None, []),
                          (None, []),
                          (None, []),
                          (None, []),
                          (self._wrap_unpack, [UNPACK_UCHAR]),
                          (self._wrap_unpack, [UNPACK_UCHAR]),
                          (self._wrap_unpack, [UNPACK_UCHAR])]

    def FromParams(self, primitive):
        """
        Set up the PDU using the parameter values from the A-ASSOCIATE
        `primitive`

        Parameters
        ----------
        primitive : pynetdicom3.pdu_primitives.A_ASSOCIATE
            The parameters to use for setting up the PDU
        """
        self.result = primitive.result
        self.source = primitive.result_source
        self.reason_diagnostic = primitive.diagnostic

        self._update_parameters()

    def ToParams(self):
        """
        Convert the current A-ASSOCIATE-RQ PDU to a primitive

        Returns
        -------
        pynetdicom3.pdu_primitives.A_ASSOCIATE
            The primitive to convert the PDU to
        """
        from pynetdicom3.pdu_primitives import A_ASSOCIATE

        primitive = A_ASSOCIATE()
        primitive.result = self.result
        primitive.result_source = self.source
        primitive.diagnostic = self.reason_diagnostic

        return primitive

    def Encode(self):
        """
        Encode the PDU's parameter values into a bytes string

        Returns
        -------
        bytestream : bytes
            The encoded PDU that will be sent to the peer AE
        """
        LOGGER.debug('Constructing Associate RJ PDU')

        formats = '> B B I B B B B'
        parameters = ['pdu_type',
                      0x00,  # Reserved
                      self.pdu_length,
                      0x00,
                      self.result,
                      self.source,
                      self.reason_diagnostic]

        bytestream = bytes()
        bytestream += pack(formats, *parameters)

        return bytestream

    def __len__(self):
        """Return the total length of the encoded PDU as an int."""
        return 10

    @property
    def _parameters(self):
        """Return a tuple containing the PDU parameters."""
        return ('pdu_type',
                0x00,  # Reserved
                'pdu_length',
                0x00,  # Reserved
                'result',
                'source',
                'reason_diagnostic')

    @property
    def pdu_length(self):
        """Return the 'PDU Length' parameter value as an int."""
        return 4

    @property
    def pdu_type(self):
        """Return the PDU type as an int."""
        return 0x03

    @property
    def reason_diagnostic(self):
        """Get the reason diagnostic parameter."""
        return self._reason

    @reason_diagnostic.setter
    def reason_diagnostic(self, value):
        """Set the reason diagnostic parameter."""
        # pylint: disable=attribute-defined-outside-init
        self._reason = value

    @property
    def reason_str(self):
        """Get a string describing the reason parameter."""
        reasons = {
            1: {
                1: "No reason given",
                2: "Application context name not supported",
                3: "Calling AE title not recognised",
                4: "Reserved",
                5: "Reserved",
                6: "Reserved",
                7: "Called AE title not recognised",
                8: "Reserved",
                9: "Reserved",
                10: "Reserved"
            },
            2: {
                1: "No reason given",
                2: "Protocol version not supported"
            },
            3: {
                0: "Reserved",
                1: "Temporary congestion",
                2: "Local limit exceeded",
                3: "Reserved",
                4: "Reserved",
                5: "Reserved",
                6: "Reserved",
                7: "Reserved"
            }
        }

        if self.source not in reasons.keys():
            LOGGER.error('Invalid value in Source parameter in '
                         'A-ASSOCIATE-RJ PDU')
            raise ValueError('Invalid value in Source parameter in '
                             'A-ASSOCIATE-RJ PDU')

        source_reasons = reasons[self.source]

        if self.reason_diagnostic not in source_reasons.keys():
            LOGGER.error('Invalid value in Reason parameter in '
                         'A-ASSOCIATE-RJ PDU')
            raise ValueError('Invalid value in Reason parameter in '
                             'A-ASSOCIATE-RJ PDU')

        return source_reasons[self.reason_diagnostic]

    @property
    def result(self):
        """Get the Result parameter."""
        return self._result

    @result.setter
    def result(self, value):
        """Set the Result parameter."""
        # pylint: disable=attribute-defined-outside-init
        self._result = value

    @property
    def result_str(self):
        """Get the Result parameter in the form of a string."""
        results = {1: 'Rejected (Permanent)',
                   2: 'Rejected (Transient)'}

        if self.result not in results.keys():
            LOGGER.error('Invalid value in Result parameter in '
                         'A-ASSOCIATE-RJ PDU')
            raise ValueError('Invalid value in Result parameter in '
                             'A-ASSOCIATE-RJ PDU')

        return results[self.result]

    @property
    def source(self):
        """Get the Source parameter."""
        return self._source

    @source.setter
    def source(self, value):
        """Set the source parameter."""
        # pylint: disable=attribute-defined-outside-init
        self._source = value

    @property
    def source_str(self):
        """Get the source parameter in the form of a string."""
        sources = {1: 'DUL service-user',
                   2: 'DUL service-provider (ACSE related)',
                   3: 'DUL service-provider (presentation related)'}

        if self.source not in sources.keys():
            LOGGER.error('Invalid value in Source parameter in '
                         'A-ASSOCIATE-RJ PDU')
            raise ValueError('Invalid value in Source parameter in '
                             'A-ASSOCIATE-RJ PDU')

        return sources[self.source]

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

# FIXME non-generic _generate-items and _wrap_generate_items
class P_DATA_TF(PDU):
    """
    Represents the P-DATA-TF PDU that, when encoded, is received from/sent
    to the peer AE.

    The P-DATA-TF PDU contains data to be transmitted between two associated
    AEs.

    A P-DATA-TF requires the following parameters (see PS3.8 Section
        9.3.5):
        * PDU type (1, fixed value, 0x04)
        * PDU length (1)
        * Presentation data value Item(s) (1 or more)

    See PS3.8 Section 9.3.5 for the structure of the PDU, especially Table 9-22.

    Attributes
    ----------
    length : int
        The length of the encoded PDU in bytes
    PDVs : list of pynetdicom3.pdu.PresentationDataValueItem
        The presentation data value items
    """

    def __init__(self):
        self.presentation_data_value_items = []

        self._offsets = [(0, 1),  # PDU type
                         (1, 2),  # Reserved
                         (2, 6),  # PDU length
                         (6, None)]  # PDV items
        self._decoders = [(None, []),
                          (None, []),
                          (None, []),
                          (self._wrap_generate_items, [])]

    def FromParams(self, primitive):
        """
        Set up the PDU using the parameter values from the P-DATA `primitive`

        Parameters
        ----------
        primitive : pynetdicom3.pdu_primitives.P_DATA
            The parameters to use for setting up the PDU
        """
        for ii in primitive.presentation_data_value_list:
            presentation_data_value = PresentationDataValueItem()
            presentation_data_value.FromParams(ii)
            self.presentation_data_value_items.append(presentation_data_value)

        self._update_pdu_length()
        self._update_parameters()

    def ToParams(self):
        """
        Convert the current P-DATA-TF PDU to a primitive

        Returns
        -------
        pynetdicom3.pdu_primitives.P_DATA
            The primitive to convert the PDU to
        """
        from pynetdicom3.pdu_primitives import P_DATA

        primitive = P_DATA()

        primitive.presentation_data_value_list = []
        for ii in self.presentation_data_value_items:
            primitive.presentation_data_value_list.append(
                [ii.presentation_context_id, ii.presentation_data_value])
        return primitive

    def Encode(self):
        """
        Encode the PDU's parameter values into a bytes string

        Returns
        -------
        bytestream : bytes
            The encoded PDU that will be sent to the peer AE
        """

        formats = '> B B I'
        parameters = ['pdu_type',
                      0x00,  # Reserved
                      self.pdu_length]

        bytestream = bytes()
        bytestream += pack(formats, *parameters)

        for ii in self.presentation_data_value_items:
            bytestream += ii.Encode()

        return bytestream

    @staticmethod
    def _generate_items(bytestream):
        """Yield the variable PDV item data from `bytestream`.

        +--------+-------------+-------------------------+
        | Offset | Length      | Description             |
        +========+=============+=========================+
        | 0      | 4           | Item length             |
        | 4      | 1           | Context ID              |
        | 5      | NN          | Presentation data value |
        +--------+-------------+-------------------------+

        Parameters
        ----------
        bytestream : bytes
            The encoded PDU variable item data.

        Yields
        ------
        int, bytes
            The PDV's Presentation Context ID as int, and the PDV item's
            encoded data as bytes.
        """
        offset = 0
        while bytestream[offset:offset + 1]:
            item_length = UNPACK_UINT4(bytestream[offset:offset + 4])[0]
            context_id = UNPACK_UCHAR(bytestream[offset + 4:offset + 5])[0]
            data = bytestream[offset + 5:offset + 5 + item_length]
            yield context_id, data
            # Change `offset` to the start of the next PDV item
            offset += 5 + item_length

    def __len__(self):
        """Return the total length of the encoded PDU as an int."""
        return 6 + self.pdu_length

    @property
    def _parameters(self):
        """Return a tuple containing the PDU parameters."""
        return ('pdu_type',
                0x00,
                'pdu_length',
                'presentation_data_value_items')

    @property
    def pdu_length(self):
        """Return the 'PDU Length' parameter value as an int."""
        length = 0
        for item in self.presentation_data_value_items:
            length += len(item)

        return length

    @property
    def pdu_type(self):
        """Return the PDU type as an int."""
        return 0x04

    @property
    def PDVs(self):
        """Get the PDVs."""
        return self.presentation_data_value_items

    def __str__(self):
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
        """Return a list of PDV items generated from `bytestream`."""
        item_list = []
        for context_id, data in self._generate_items(bytestream):
            pdv_item = PresentationDataValueItem()
            pdv_item.presentation_context_id = context_id
            pdv_item.presentation_data_value = data
            item_list.append(pdv_item)

        return item_list


class A_RELEASE_RQ(PDU):
    """
    Represents the A-RELEASE-RQ PDU that, when encoded, is received from/sent
    to the peer AE.

    The A-RELEASE-RQ PDU requests that the association be released

    A A-RELEASE-RQ requires the following parameters (see PS3.8 Section
        9.3.6):
        * PDU type (1, fixed value, 0x05)
        * PDU length (1)

    See PS3.8 Section 9.3.6 for the structure of the PDU, especially Table 9-24.

    Attributes
    ----------
    length : int
        The length of the encoded PDU in bytes
    """

    def __init__(self):

        self._offsets = [(0, 1),  # PDU type
                         (1, 2),  # Reserved
                         (2, 6),  # PDU length
                         (6, 10)]  # Reserved
        self._decoders = [(None, []),
                          (None, []),
                          (None, []),
                          (None, [])]

    def FromParams(self, _):
        """
        Set up the PDU using the parameter values from the A-RELEASE `primitive`

        Parameters
        ----------
        primitive : pynetdicom3.pdu_primitives.A_RELEASE
            The parameters to use for setting up the PDU
        """
        self._update_parameters()

    def ToParams(self):
        """
        Convert the current A-RELEASE-RQ PDU to a primitive

        Returns
        -------
        pynetdicom3.pdu_primitives.A_RELEASE
            The primitive to convert the PDU to
        """
        from pynetdicom3.pdu_primitives import A_RELEASE
        primitive = A_RELEASE()

        return primitive

    def Encode(self):
        """
        Encode the PDU's parameter values into a bytes string

        Returns
        -------
        bytestream : bytes
            The encoded PDU that will be sent to the peer AE
        """
        formats = '> B B I I'
        parameters = ['pdu_type',
                      0x00,  # Reserved
                      self.pdu_length,
                      0x0000]  # Reserved

        bytestream = bytes()
        bytestream += pack(formats, *parameters)

        return bytestream

    def __len__(self):
        """Return the total length of the encoded PDU as an int."""
        return 10

    @property
    def _parameters(self):
        """Return a tuple containing the PDU parameters."""
        return ('pdu_type',
                0x00,  # Reserved
                'pdu_length',
                0x0000)  # Reserved

    @property
    def pdu_length(self):
        """Return the 'PDU Length' parameter value as an int."""
        return 4

    @property
    def pdu_type(self):
        """Return the PDU type as an int."""
        return 0x05

    def __str__(self):
        s = 'A-RELEASE-RQ PDU\n'
        s += '================\n'
        s += '  PDU type: 0x{0:02x}\n'.format(self.pdu_type)
        s += '  PDU length: {0:d} bytes\n'.format(self.pdu_length)

        return s


class A_RELEASE_RP(PDU):
    """
    Represents the A-RELEASE-RP PDU that, when encoded, is received from/sent
    to the peer AE.

    The A-RELEASE-RP PDU confirms that the association will be released

    A A-RELEASE-RP requires the following parameters (see PS3.8 Section
        9.3.7):
        * PDU type (1, fixed value, 0x06)
        * PDU length (1)

    See PS3.8 Section 9.3.7 for the structure of the PDU, especially Table 9-25.

    Attributes
    ----------
    length : int
        The length of the encoded PDU in bytes
    """

    def __init__(self):
        #self.formats = ['B', 'B', 'I', 'I']
        #self.parameters = ['pdu_type',
        #                   0x00,  # Reserved
        #                   self.pdu_length,
        #                   0x0000]  # Reserved
        self._offsets = [(0, 1),  # PDU type
                         (1, 2),  # Reserved
                         (2, 6),  # PDU length
                         (6, 10)]  # Reserved
        self._decoders = [(None, []),
                          (None, []),
                          (None, []),
                          (None, [])]

    def FromParams(self, _):
        """
        Set up the PDU using the parameter values from the A-RELEASE `primitive`

        Parameters
        ----------
        primitive : pynetdicom3.pdu_primitives.A_RELEASE
            The parameters to use for setting up the PDU
        """
        self._update_parameters()

    def ToParams(self):
        """
        Convert the current A-RELEASE-RP PDU to a primitive

        Returns
        -------
        pynetdicom3.pdu_primitives.A_RELEASE
            The primitive to convert the PDU to
        """
        from pynetdicom3.pdu_primitives import A_RELEASE
        primitive = A_RELEASE()
        primitive.result = 'affirmative'

        return primitive

    def Encode(self):
        """
        Encode the PDU's parameter values into a bytes string

        Returns
        -------
        bytestream : bytes
            The encoded PDU that will be sent to the peer AE
        """
        formats = '> B B I I'
        parameters = ['pdu_type',
                      0x00,  # Reserved
                      self.pdu_length,
                      0x0000]  # Reserved

        bytestream = bytes()
        bytestream += pack(formats, *parameters)

        return bytestream

    def __len__(self):
        """Return the total length of the encoded PDU as an int."""
        return 10

    @property
    def _parameters(self):
        """Return a tuple containing the PDU parameters."""
        return ('pdu_type',
                0x00,  # Reserved
                'pdu_length',
                0x0000)  # Reserved

    @property
    def pdu_length(self):
        """Return the 'PDU Length' parameter value as an int."""
        return 4

    @property
    def pdu_type(self):
        """Return the PDU type as an int."""
        return 0x06

    def __str__(self):
        s = 'A-RELEASE-RP PDU\n'
        s += '================\n'
        s += '  PDU type: 0x{0:02x}\n'.format(self.pdu_type)
        s += '  PDU length: {0:d} bytes\n'.format(self.pdu_length)

        return s


class A_ABORT_RQ(PDU):
    """
    Represents the A-ABORT PDU that, when encoded, is received from/sent
    to the peer AE.

    The A-ABORT PDU signals that the association will be aborted

    A A-ABORT requires the following parameters (see PS3.8 Section
        9.3.8):
        * PDU type (1, fixed value, 0x06)
        * PDU length (1)
        * Source (1)
        * Reason/Diagnostic (1)

    See PS3.8 Section 9.3.7 for the structure of the PDU, especially Table 9-25.

    Attributes
    ----------
    length : int
        The length of the encoded PDU in bytes
    reason_str : str
        The reason for the abort
    source_str : str
        The source of the abort, one of ('DUL service-user',
        'DUL service-provider')
    """

    def __init__(self):
        self.source = None
        self.reason_diagnostic = None

        #self.formats = ['B', 'B', 'I', 'B', 'B', 'B', 'B']
        #self.parameters = ['pdu_type',
        #                   0x00,  # Reserved
        #                   self.pdu_length,
        #                   0x00,  # Reserved
        #                   0x00,  # Reserved
        #                   self.source,
        #                   self.reason_diagnostic]  # Reserved

        self._offsets = [(0, 1),  # PDU type
                         (1, 2),  # Reserved
                         (2, 6),  # PDU length
                         (6, 7),  # Reserved
                         (7, 8),  # Reserved
                         (8, 9),  # Source
                         (9, 10)]  # Reason/Diagnostic
        self._decoders = [(None, []),
                          (None, []),
                          (None, []),
                          (None, []),
                          (None, []),
                          (self._wrap_unpack, [UNPACK_UCHAR]),
                          (self._wrap_unpack, [UNPACK_UCHAR])]

    def FromParams(self, primitive):
        """
        Set up the PDU using the parameter values from the A-RELEASE `primitive`

        Parameters
        ----------
        primitive : pynetdicom3.pdu_primitives.A_ABORT or
        pynetdicom3.pdu_primitives.A_P_ABORT
            The parameters to use for setting up the PDU
        """
        from pynetdicom3.pdu_primitives import A_ABORT, A_P_ABORT

        # User initiated abort
        if primitive.__class__ == A_ABORT:
            # The reason field shall be 0x00 when the source is DUL service-user
            self.reason_diagnostic = 0
            self.source = primitive.abort_source

        # User provider primitive abort
        elif primitive.__class__ == A_P_ABORT:
            self.reason_diagnostic = primitive.provider_reason
            self.source = 2

        self._update_parameters()

    def ToParams(self):
        """
        Convert the current A-ABORT PDU to a primitive

        Returns
        -------
        pynetdicom3.pdu_primitives.A_ABORT_ServiceParameters or
        pynetdicom3.pdu_primitives.A_P_ABORT_ServiceParameters
            The primitive to convert the PDU to
        """
        from pynetdicom3.pdu_primitives import A_ABORT, A_P_ABORT

        # User initiated abort
        if self.source == 0x00:
            primitive = A_ABORT()
            primitive.abort_source = self.source

        # User provider primitive abort
        elif self.source == 0x02:
            primitive = A_P_ABORT()
            primitive.provider_reason = self.reason_diagnostic

        return primitive

    def Encode(self):
        """
        Encode the PDU's parameter values into a bytes string

        Returns
        -------
        bytestream : bytes
            The encoded PDU that will be sent to the peer AE
        """
        formats = '> B B I B B B B'
        parameters = ['pdu_type',
                      0x00,  # Reserved
                      self.pdu_length,
                      0x00,  # Reserved
                      0x00,  # Reserved
                      self.source,
                      self.reason_diagnostic]

        bytestream = bytes()
        bytestream += pack(formats, *parameters)

        return bytestream

    def __len__(self):
        """Return the total length of the encoded PDU as an int."""
        return 10

    @property
    def _parameters(self):
        """Return a tuple containing the PDU parameters."""
        return ('pdu_type',
                0x00,  # Reserved
                'pdu_length',
                0x00,  # Reserved
                0x00,  # Reserved
                'source',
                'reason_diagnostic')

    @property
    def pdu_length(self):
        """Return the 'PDU Length' parameter value as an int."""
        return 4

    @property
    def pdu_type(self):
        """Return the PDU type as an int."""
        return 0x07

    def __str__(self):
        s = "A-ABORT PDU\n"
        s += "===========\n"
        s += "  PDU type: 0x{0:02x}\n".format(self.pdu_type)
        s += "  PDU length: {0:d} bytes\n".format(self.pdu_length)
        s += "  Abort Source: {0!s}\n".format(self.source_str)
        s += "  Reason/Diagnostic: {0!s}\n".format(self.reason_str)

        return s

    @property
    def source_str(self):
        """
        See PS3.8 9.3.8

        Returns
        -------
        str
            The source of the Association abort
        """
        sources = {0: 'DUL service-user',
                   1: 'Reserved',
                   2: 'DUL service-provider'}

        return sources[self.source]

    @property
    def reason_str(self):
        """
        See PS3.8 9.3.8

        Returns
        -------
        str
            The reason given for the Association abort
        """
        if self.source == 2:
            reason_str = {0: "No reason given",
                          1: "Unrecognised PDU",
                          2: "Unexpected PDU",
                          3: "Reserved",
                          4: "Unrecognised PDU parameter",
                          5: "Unexpected PDU parameter",
                          6: "Invalid PDU parameter value"}
            return reason_str[self.reason_diagnostic]
        else:
            return 'No reason given'


# PDU item and sub-item classes
class ApplicationContextItem(PDU):
    """
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
    """

    def __init__(self):
        self.application_context_name = ''

        self._offsets = [(0, 1), (1, 2), (2, 4), (4, None)]
        self._decoders = [(None, []),  # Item type
                          (None, []),  # Reserved
                          (None, []),  # Item length
                          (self._wrap_slice, [])]  # Application context name

    def FromParams(self, primitive):
        """
        Set up the Item using the parameter values from the `primitive`

        Parameters
        ----------
        primitive : pydicom.uid.UID, bytes, str or None
            The UID value to use for the Application Context Name
        """
        self.application_context_name = primitive

        self._update_parameters()

    def ToParams(self):
        """
        Convert the current Item to a primitive

        Returns
        -------
        pydicom.uid.UID
            The Application Context Name's UID value
        """
        return self.application_context_name

    def Encode(self):
        """
        Encode the Item's parameter values into a bytes string

        Returns
        -------
        bytestream : bytes
            The encoded Item used in the parent PDU
        """
        formats = '> B B H'
        parameters = [self.item_type,
                      0x00,  # Reserved
                      self.item_length]

        bytestream = bytes()
        bytestream += pack(formats, *parameters)
        bytestream += codecs.encode(
            self.application_context_name.title(), 'utf-8')

        return bytestream

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

    @property
    def _parameters(self):
        """Update the PDU parameters."""
        return ('item_type',
                0x00,  # Reserved
                'item_length',
                'application_context_name')

    def __str__(self):
        s = '{0!s} ({1!s})\n'.format(self.application_context_name,
                                     self.application_context_name.title())
        return s


class PresentationContextItemRQ(PDU):
    """
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
    length : int
        The length of the encoded Item in bytes
    ID : int
        The presentation context's ID
    transfer_syntax : list of pydicom.uid.UID
        The presentation context's Transfer Syntax(es)

    SCP : None or int
        Defaults to None if SCP/SCU role negotiation not used, 0 or 1 if used
    SCU : None or int
        Defaults to None if SCP/SCU role negotiation not used, 0 or 1 if used
    """

    def __init__(self):
        self.presentation_context_id = None

        # AbstractTransferSyntaxSubItems is a list
        # containing the following elements:
        #   One AbstractSyntaxtSubItem
        #   One or more TransferSyntaxSubItem
        self.abstract_transfer_syntax_sub_items = []

        # Non-standard parameters
        #   Used for tracking SCP/SCU Role Negotiation
        # Consider shifting to properties?
        #   or removing...
        self.SCP = None
        self.SCU = None

        self._offsets = [(0, 1),
                         (1, 2),
                         (2, 4),
                         (4, 5),
                         (5, 6),
                         (6, 7),
                         (7, 8),
                         (8, None)]
        self._decoders = [
            (None, []),  # Item type
            (None, []),  # Reserved
            (None, []),  # Item length
            (self._wrap_unpack, [UNPACK_UCHAR]),  # Presentation context ID
            (None, []),  # Reserved
            (None, []),  # Reserved
            (None, []),  # Reserved
            (self._wrap_generate_items, [])  #  Abstract/Transfer syntax items
        ]

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

        self.get_length()
        self._update_parameters()

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

    def Encode(self):
        """
        Encode the Item's parameter values into a bytes string

        Returns
        -------
        bytestream : bytes
            The encoded Item used in the parent PDU
        """
        formats = '> B B H B B B B'
        parameters = [self.item_type,
                      0x00,  # Reserved
                      self.item_length,
                      self.presentation_context_id,
                      0x00,  # Reserved
                      0x00,  # Reserved
                      0x00]  # Reserved

        bytestream = bytes()
        bytestream += pack(formats, *parameters)

        for ii in self.abstract_transfer_syntax_sub_items:
            bytestream += ii.Encode()

        return bytestream

    @property
    def abstract_syntax(self):
        """Get the abstract syntax."""
        for ii in self.abstract_transfer_syntax_sub_items:
            if isinstance(ii, AbstractSyntaxSubItem):
                return ii.abstract_syntax_name

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

    @property
    def _parameters(self):
        """Update the PDU parameters."""
        return ('item_type',
                0x00,  # Reserved
                'item_length',
                'presentation_context_id',
                0x00,  # Reserved
                0x00,  # Reserved
                0x00,  # Reserved
                'abstract_transfer_syntax_sub_items')

    def __str__(self):
        s = "Presentation Context (RQ) Item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        s += "  Context ID: {0:d}\n".format(self.ID)
        if self.SCP is not None:
            s += "  SCP Role: {0:d}\n".format(self.SCP)
        if self.SCU is not None:
            s += "  SCU Role: {0:d}\n".format(self.SCU)

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
class PresentationContextItemAC(PDU):
    """
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
    length : int
        The length of the encoded Item in bytes
    ID : int
        The presentation context's ID
    result : int
        The presentation context's result/reason value
    result_str : str
        The result as a string, one of ('Accepted', 'User Rejected',
        'No Reason', 'Abstract Syntax Not Supported',
        'Transfer Syntaxes Not Supported')
    transfer_syntax : pydicom.uid.UID
        The presentation context's Transfer Syntax

    SCP : None or int
        Defaults to None if SCP/SCU role negotiation not used, 0 or 1 if used
    SCU : None or int
        Defaults to None if SCP/SCU role negotiation not used, 0 or 1 if used
    """

    def __init__(self):
        self.presentation_context_id = None
        self.result_reason = None
        self.transfer_syntax_sub_item = None

        # Used for tracking SCP/SCU Role Negotiation
        # TODO: Remove
        self.SCP = None
        self.SCU = None

        self._offsets = [(0, 1),
                         (1, 2),
                         (2, 4),
                         (4, 5),
                         (5, 6),
                         (6, 7),
                         (7, 8),
                         (8, None)]
        self._decoders = [
            (None, []),  # Item type
            (None, []),  # Reserved
            (None, []),  # Item length
            (self._wrap_unpack, [UNPACK_UCHAR]),  # Presentation context ID
            (None, []),  # Reserved
            (self._wrap_unpack, [UNPACK_UCHAR]),  # Result/reason
            (None, []),  # Reserved
            (self._wrap_generate_items, [])  #  Transfer syntax item
        ]

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
        self.transfer_syntax_sub_item = TransferSyntaxSubItem()
        self.transfer_syntax_sub_item.FromParams(primitive.TransferSyntax[0])

        self.get_length()
        self._update_parameters()

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
        primitive.add_transfer_syntax(self.transfer_syntax_sub_item.ToParams())

        return primitive

    def Encode(self):
        """
        Encode the Item's parameter values into a bytes string

        Returns
        -------
        bytestream : bytes
            The encoded Item used in the parent PDU
        """
        formats = '> B B H B B B B'
        parameters = [self.item_type,
                      0x00,  # Reserved
                      self.item_length,
                      self.presentation_context_id,
                      0x00,  # Reserved
                      self.result_reason,  # Reserved
                      0x00]  # Reserved

        bytestream = bytes()
        bytestream += pack(formats, *parameters)
        bytestream += self.transfer_syntax_sub_item.Encode()

        return bytestream

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

    @property
    def _parameters(self):
        """Update the parameters"""
        return ('item_type',
                0x00,  # Reserved
                'item_length',
                'presentation_context_id',
                0x00,  # Reserved
                'result_reason',
                0x00,  # Reserved
                'transfer_syntax_sub_item')

    def __str__(self):
        s = "Presentation Context (AC) Item\n"
        s += "  Item type:   0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        s += "  Context ID: {0:d}\n".format(self.presentation_context_id)
        s += "  Result/Reason: {0!s}\n".format(self.result_str)

        item_str = '{0!s}'.format(self.transfer_syntax_sub_item)
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


class AbstractSyntaxSubItem(PDU):
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

        self._offsets = [(0, 1), (1, 2), (2, 4), (4, None)]
        self._decoders = [(None, []),  # Item type
                          (None, []),  # Reserved
                          (None, []),  # Item length
                          (self._wrap_slice, [])]  # Abstract syntax name

    def FromParams(self, primitive):
        """
        Set up the Item using the parameter values from the `primitive`

        Parameters
        ----------
        primitive : pydicom.uid.UID, bytes or str
            The abstract syntax name
        """
        self.abstract_syntax_name = primitive
        self.item_length = len(self.abstract_syntax_name)

        self._update_parameters()

    def ToParams(self):
        """
        Convert the current Item to a primitive

        Returns
        -------
        pydicom.uid.UID
            The Abstract Syntax Name's UID value
        """
        return self.abstract_syntax_name

    def Encode(self):
        """
        Encode the Item's parameter values into a bytes string

        Returns
        -------
        bytestream : bytes
            The encoded Item used in the parent PDU
        """
        formats = '> B B H'
        parameters = [self.item_type,
                      0x00,  # Reserved
                      self.item_length]

        bytestream = bytes()
        bytestream += pack(formats, *parameters)
        bytestream += codecs.encode(self.abstract_syntax_name.title(), 'utf-8')

        return bytestream

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

    @property
    def _parameters(self):
        """Update the PDU parameters."""
        return ('item_type',
                0x00,  # Reserved
                'item_length',
                'abstract_syntax_name')

    def __str__(self):
        s = "Abstract Syntax Sub-item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        s += '  Syntax name: ={0!s}\n'.format(self.abstract_syntax.name)

        return s


class TransferSyntaxSubItem(PDU):
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

        self._offsets = [(0, 1), (1, 2), (2, 4), (4, None)]
        self._decoders = [(None, []),  # Item type
                          (None, []),  # Reserved
                          (None, []),  # Item length
                          (self._wrap_slice, [])]  # Transfer syntax name

    def FromParams(self, primitive):
        """
        Set up the Item using the parameter values from the `primitive`

        Parameters
        ----------
        primitive : pydicom.uid.UID, bytes or str
            The transfer syntax name
        """
        self.transfer_syntax_name = primitive
        self.item_length = len(self.transfer_syntax_name)

        self._update_parameters()

    def ToParams(self):
        """
        Convert the current Item to a primitive

        Returns
        -------
        pydicom.uid.UID
            The Transfer Syntax Name's UID value
        """
        return self.transfer_syntax_name

    def Encode(self):
        """
        Encode the Item's parameter values into a bytes string

        Returns
        -------
        bytestream : bytes
            The encoded Item used in the parent PDU
        """
        formats = '> B B H'
        parameters = [self.item_type,
                      0x00,  # Reserved
                      self.item_length]

        bytestream = bytes()
        bytestream += pack(formats, *parameters)
        bytestream += codecs.encode(self.transfer_syntax_name.title(), 'utf-8')

        return bytestream

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

    @property
    def _parameters(self):
        """Update the parameters."""
        return ('item_type',
                0x00,
                'item_length',
                'transfer_syntax_name')

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


class UserInformationItem(PDU):
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
        pynetdicom3.pdu.SOPClassCommonExtendedNegotiationSubItem or None
        The common extended negotiation items, or None if there aren't any
    ext_neg : list of pynetdicom3.pdu.SOPClassExtendedNegotiationSubItem or None
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
    role_selection : list of pynetdicom3.pdu.SCP_SCU_RoleSelectionSubItem or
    None
        The SCP_SCU_RoleSelectionSubItem object or None if there aren't any
    user_identity : pynetdicom3.pdu.UserIdentitySubItemRQ or
        pynetdicom3.pdu.UserIdentitySubItemAC or None
        The UserIdentitySubItemRQ/UserIdentitySubItemAC object, or None if the
        sub-item is not present.
    """

    def __init__(self):
        self.user_data = []

        self._offsets = [(0, 1), (1, 2), (2, 4), (4, None)]
        self._decoders = [(None, []),  # Item type
                          (None, []),  # Reserved
                          (None, []),  # Item length
                          (self._wrap_generate_items, [])]  # User data

    def FromParams(self, primitive):
        """
        Set up the Item using the parameter values from the `primitive`

        Parameters
        ----------
        primitive : list
        """
        for ii in primitive:
            self.user_data.append(ii.FromParams())

        self._update_item_length()
        self._update_parameters()

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

    def Encode(self):
        """
        Encode the Item's parameter values into a bytes string

        Returns
        -------
        bytestream : bytes
            The encoded Item used in the parent PDU
        """
        formats = '> B B H'
        parameters = [self.item_type,
                      0x00,  # Reserved
                      self.item_length]

        bytestream = bytes()
        bytestream += pack(formats, *parameters)

        for ii in self.user_data:
            bytestream += ii.Encode()

        return bytestream

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

    @property
    def implementation_version_name(self):
        """Return the Implementation Version Name item or None if none present."""
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
    def _parameters(self):
        """Update the parameters."""
        return ('item_type',
                0x00,  # Reserved
                'item_length',
                'user_data')

    @property
    def role_selection(self):
        """Return the SCP/SCU Role Selection item or None if none present."""
        roles = {}
        for item in self.user_data:
            if isinstance(item, SCP_SCU_RoleSelectionSubItem):
                roles[item.UID] = item

        if roles:
            return roles

        return None

    def __str__(self):
        # FIXME: Indent not applying correctly to user_data
        s = " User information item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d}\n".format(self.item_length)
        s += "  User Data:\n "

        for ii in self.user_data[1:]:
            s += "  {0!s}".format(ii)

        return s

    @property
    def user_identity(self):
        """Return the User Identity item or None if none present."""
        for item in self.user_data:
            if isinstance(item, (UserIdentitySubItemRQ,
                                 UserIdentitySubItemAC)):
                return item

        return None


# PDU User Information Sub-item Classes
class MaximumLengthSubItem(PDU):
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

        self._offsets = [(0, 1), (1, 2), (2, 4), (4, None)]
        self._decoders = [(None, []),  # Item type
                          (None, []),  # Reserved
                          (None, []),  # Item length
                          (self._wrap_unpack, [UNPACK_UINT4])]  # Max length

    def FromParams(self, primitive):
        """
        Set up the Item using the parameter values from the `primitive`

        Parameters
        ----------
        primitive : pynetdicom3.pdu_primitives.MaximumLengthNegotiation
            The primitive to use when setting up the Item
        """
        self.maximum_length_received = primitive.maximum_length_received

        self._update_parameters()

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

    def Encode(self):
        """
        Encode the Item's parameter values into a bytes string

        Returns
        -------
        bytestream : bytes
            The encoded Item used in the parent PDU
        """
        formats = '> B B H I'
        parameters = [self.item_type,
                      0x00,
                      0x0004,
                      self.maximum_length_received]

        bytestream = bytes()
        bytestream += pack(formats, *parameters)

        return bytestream

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

    @property
    def _parameters(self):
        """Update the parameters."""
        return ('item_type',
                0x00,
                'item_length',
                'maximum_length_received')

    def __str__(self):
        s = "Maximum length Sub-item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        s += "  Maximum length received: {0:d}\n".format(
            self.maximum_length_received)
        return s


class ImplementationClassUIDSubItem(PDU):
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

        self._offsets = [(0, 1), (1, 2), (2, 4), (4, None)]
        self._decoders = [(None, []),  # Item type
                          (None, []),  # Reserved
                          (None, []),  # Item length
                          (self._wrap_slice, [])]  # Max length

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
        self.item_length = len(self.implementation_class_uid)

        self._update_parameters()

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

    def Encode(self):
        """Encode the item"""
        s = b''
        s += pack('B', self.item_type)
        s += pack('B', 0x00)
        s += pack('>H', self.item_length)
        s += codecs.encode(self.implementation_class_uid.title(), 'utf-8')
        return s

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

    @property
    def _parameters(self):
        """Update the parameters."""
        return ('item_type',
                0x00,
                'item_length',
                'implementation_class_uid')

    def __str__(self):
        s = "Implementation Class UID Sub-item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        s += "  Implementation class UID: '{0!s}'\n".format(
            self.implementation_class_uid)

        return s


class AsynchronousOperationsWindowSubItem(PDU):
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

        self._offsets = [(0, 1), (1, 2), (2, 4), (4, 6), (6, 8)]
        self._decoders = [(None, []),  # Item type
                          (None, []),  # Reserved
                          (None, []),  # Item length
                          (self._wrap_unpack, [UNPACK_UINT2]),  # Max invoked
                          (self._wrap_unpack, [UNPACK_UINT2])]  # Max performed

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

        self._update_parameters()

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

    def Encode(self):
        """
        Encode the Item's parameter values into a bytes string

        Returns
        -------
        bytestream : bytes
            The encoded Item used in the parent PDU
        """
        formats = '> B B H H H'
        parameters = [self.item_type,
                      0x00,
                      self.item_length,
                      self.maximum_number_operations_invoked,
                      self.maximum_number_operations_performed]

        bytestream = bytes()
        bytestream += pack(formats, *parameters)

        return bytestream

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
    def _parameters(self):
        """Update the parameters"""
        return ('item_type',
                0x00,  # Reserved
                'item_length',
                'maximum_number_operations_invoked',
                'maximum_number_operations_performed')

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

# FIXME: Non generic decode
class SCP_SCU_RoleSelectionSubItem(PDU):
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
        self.sop_class_uid = None
        self.scu_role = None
        self.scp_role = None

        self._offsets = [(0, 1),
                         (1, 2),
                         (2, 4),
                         (4, 6),
                         (6, 'FIXME'),
                         ('FIXME', 'FIXME + 1'),
                         ('FIXME + 1', 'FIXME + 2')]
        self._decoders = [(None, []),  # Item type
                          (None, []),  # Reserved
                          (None, []),  # Item length
                          (None, []),  # UID length
                          (self._wrap_slice, []),  # SOP Class UID
                          (self._wrap_unpack, [UNPACK_UCHAR]),  # SCU role
                          (self._wrap_unpack, [UNPACK_UCHAR])]  # SCP role

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

        self.item_length = 4 + len(self.sop_class_uid)
        self.uid_length = len(self.sop_class_uid)

        self._update_parameters()

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

    def Encode(self):
        """Encode the item"""
        formats = '> B B H H'
        parameters = [self.item_type,
                      0x00,
                      self.item_length,
                      self.uid_length]

        bytestream = bytes()
        bytestream += pack(formats, *parameters)
        bytestream += codecs.encode(self.sop_class_uid.title(), 'utf-8')
        bytestream += pack('> B B', self.scu_role, self.scp_role)

        return bytestream

    def decode(self, bytestream):
        uid_length = UNPACK_UINT2(bytestream[4:6])[0]
        self.sop_class_uid = bytestream[6:6 + uid_length]
        self.scu_role = UNPACK_UCHAR(bytestream[6 + uid_length])
        self.scp_role = UNPACK_UCHAR(bytestream[7 + uid_length])

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
    def _parameters(self):
        """Update the parameters"""
        return ('item_type',
                0x00,  # Reserved
                'item_length',
                'uid_length',
                'sop_class_uid',
                'scu_role',
                'scp_role')

    def __str__(self):
        s = "SCP/SCU Role Selection Sub-item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        s += "  UID length: {0:d} bytes\n".format(self.uid_length)
        s += "  SOP Class UID: {0!s}\n".format(self.UID.name)
        s += "  SCU Role: {0:d}\n".format(self.SCU)
        s += "  SCP Role: {0:d}\n".format(self.SCP)

        return s

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

        if value is not None:
            self.uid_length = len(value)
            self.item_length = 4 + self.uid_length

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
    def uid(self):
        """Get the UID."""
        return self.sop_class_uid

    @property
    def uid_length(self):
        """Return the "UID Length" parameter value."""
        return len(self.sop_class_uid)


class ImplementationVersionNameSubItem(PDU):
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

        self._offsets = [(0, 1),
                         (1, 2),
                         (2, 4),
                         (4, None)]
        self._decoders = [(None, []),  # Item type
                          (None, []),  # Reserved
                          (None, []),  # Item length
                          (self._wrap_slice, [])]  # Version name

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

        self._update_parameters()

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

    def Encode(self):
        """Encode the item."""
        s = bytes()
        s += pack('B', self.item_type)
        s += pack('B', 0x00)
        s += pack('>H', self.item_length)
        s += self.implementation_version_name

        return s

    @property
    def implementation_version_name(self):
        """Returns the implementation version name as bytes."""
        return self._implementation_version_name

    @implementation_version_name.setter
    def implementation_version_name(self, value):
        """Get the implementation version name."""
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, bytes):
            pass
        elif isinstance(value, str):
            value = codecs.encode(value, 'utf-8')

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

    @property
    def _parameters(self):
        """Update the parameters."""
        return ('item_type',
                0x00,  # Reserved
                'item_length',
                'implementation_version_name')

    def __str__(self):
        s = "Implementation Version Name Sub-item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        s += "  Implementation version name: {0!s}\n".format(
            self.implementation_version_name)

        return s

# FIXME: Non generic decode
class SOPClassExtendedNegotiationSubItem(PDU):
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
        self.sop_class_uid = None
        self.service_class_application_information = None

        self._offsets = [(0, 1),
                         (1, 2),
                         (2, 4),
                         (4, 6),
                         (6, 'FIXME'),
                         ('FIXME', None)]
        self._decoders = [(None, []),  # Item type
                          (None, []),  # Reserved
                          (None, []),  # Item length
                          (self._wrap_unpack, [UNPACK_UINT2]),  # UID length
                          (self._wrap_slice, []), # SOP Class UID
                          (self._wrap_slice, [])]  # Service class info

    def FromParams(self, primitive):
        """
        Set up the Item using the parameter values from the `primitive`

        Parameters
        ----------
        primitive : pynetdicom3.pdu_primitives.SOPClassExtendedNegotiation
            The primitive to use when setting up the Item
        """
        self.sop_class_uid = primitive.sop_class_uid
        self.sop_class_uid_length = len(self.sop_class_uid)
        self.service_class_application_information = \
            primitive.service_class_application_information
        self.item_length = 2 + self.sop_class_uid_length \
                             + len(self.service_class_application_information)

        self._update_parameters()

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

    def Encode(self):
        """
        Encode the Item's parameter values into a bytes string

        Returns
        -------
        bytestream : bytes
            The encoded Item used in the parent PDU
        """
        formats = '> B B H H'
        parameters = [self.item_type,
                      0x00,
                      self.item_length,
                      self.sop_class_uid_length]

        bytestream = bytes()
        bytestream += pack(formats, *parameters)
        bytestream += codecs.encode(self.sop_class_uid.title(), 'utf-8')
        bytestream += self.service_class_application_information

        return bytestream

    @property
    def app_info(self):
        """Set the application information"""
        return self.service_class_application_information

    def decode(self, bytestream):
        sop_class_uid_length = UNPACK_UINT2(bytestream[4:6])[0]
        self.sop_class_uid = bytestream[6:6 + sop_class_uid_length]
        self.service_class_application_information = bytestream[8 + sop_class_uid_length:]

    @property
    def item_length(self):
        """Return the Item Length parameter value."""
        return 2 + self.sop_class_uid_length + len(self.service_class_application_information)

    @property
    def item_type(self):
        """Return the item type as an int."""
        return 0x56

    def __len__(self):
        """Return the total encoded length of the item."""
        return 4 + self.item_length

    @property
    def _parameters(self):
        return ('item_type',
                0x00,
                'item_length',
                'sop_class_uid_length',
                'sop_class_uid',
                'service_class_application_information')

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

# FIXME: Non generic decode, non-generic _generate-items and _wrap_generate_items
class SOPClassCommonExtendedNegotiationSubItem(PDU):
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
    FIXME
    """

    def __init__(self):
        self.sub_item_version = 0x00
        self.sop_class_uid = None
        self.service_class_uid = None
        self.related_general_sop_class_identification = []

        self._offsets = [(0, 1),
                         (1, 2),
                         (2, 4),
                         (4, 6),
                         (6, 'FIXME'),
                         ('FIXME', None)]
        self._decoders = [
            (None, []),  # Item type
            (None, []),  # Reserved
            (None, []),  # Item length
            (self._wrap_unpack, [UNPACK_UINT2]),  # SOP UID length
            (self._wrap_slice, []), # SOP Class UID
            (self._wrap_unpack, [UNPACK_UINT2]),  # Service UID length
            (self._wrap_slice, []),   # Service Class UID
            (self._wrap_unpack, [UNPACK_UINT2]),  # Related info length
            (self._generate_items, [])   # Related general information
        ]

    def FromParams(self, primitive):
        """
        Set up the Item using the parameter values from the `primitive`

        Parameters
        ----------
        primitive : pynetdicom3.pdu_primitives.SOPClassCommonExtendedNegotiation
            The primitive to use when setting up the Item
        """
        self.sop_class_uid = primitive.sop_class_uid
        self.sop_class_uid_length = len(self.sop_class_uid)
        self.service_class_uid = primitive.service_class_uid
        self.service_class_uid_length = len(self.service_class_uid)
        self.related_general_sop_class_identification = \
            primitive.related_general_sop_class_identification

        self.related_general_sop_class_identification_length = 0
        for uid in self.related_general_sop_class_identification:
            self.related_general_sop_class_identification_length += len(uid)

        self.item_length = 2 + self.sop_class_uid_length + 2 + \
            self.service_class_uid_length + 2 + \
            self.related_general_sop_class_identification_length

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

    def encode(self):
        """Encode the item"""
        return self.Encode()

    def Encode(self):
        """
        Encode the Item's parameter values into a bytes string

        Returns
        -------
        bytestream : bytes
            The encoded Item used in the parent PDU
        """
        formats = '> B B H H'
        parameters = [self.item_type,
                      self.sub_item_version,
                      self.item_length,
                      self.sop_class_uid_length]

        bytestream = bytes()
        bytestream += pack(formats, *parameters)
        bytestream += codecs.encode(self.sop_class_uid.title(), 'utf-8')
        bytestream += pack('>H', self.service_class_uid_length)
        bytestream += codecs.encode(self.service_class_uid, 'utf-8')
        bytestream += \
            pack('>H', self.related_general_sop_class_identification_length)

        for sub_fields in self.related_general_sop_class_identification:
            bytestream += pack('>H', len(sub_fields))
            bytestream += codecs.encode(sub_fields.title(), 'utf-8')

        return bytestream

    def Decode(self, bytestream):
        """
        Decode the parameter values for the Item from the parent PDU's byte
        stream

        Parameters
        ----------
        bytestream : io.BytesIO
            The byte stream to decode
        """
        (self.item_type,
         self.sub_item_version,
         self.item_length,
         self.sop_class_uid_length) = unpack('>B B H H', bytestream.read(6))

        self.sop_class_uid = bytestream.read(self.sop_class_uid_length)

        (self.service_class_uid_length,) = unpack('>H', bytestream.read(2))
        self.service_class_uid = bytestream.read(self.service_class_uid_length)

        (self.related_general_sop_class_identification_length,) = \
            unpack('>H', bytestream.read(2))

        # Read remaining bytes in item
        remaining = self.related_general_sop_class_identification_length
        uids = []
        while remaining > 0:
            (uid_length,) = unpack('>H', bytestream.read(2))
            uid = bytestream.read(uid_length)
            uids.append(uid)

            remaining -= 2 + uid_length

        self.related_general_sop_class_identification = uids

    def decode(self, bytestream):
        #bytestream = BytesIO(bytestream)
        #self.Decode(bytestream)

        sop_length = UNPACK_UINT2(bytestream[4:6])[0]
        self.sop_class_uid = bytestream[6:6 + sop_length]
        service_length = UNPACK_UINT2(bytestream[6 + sop_length:8 + sop_length])[0]
        self.service_class_uid = bytestream[8 + sop_length:8 + sop_length + service_length]

        for uid in self._generate_items(bytestream[10 + sop_length + service_length:]):
            self.related_general_sop_class_identification.append(uid)

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
            yield UID(bytestream[offset + 2:offset + 2 + uid_length])
            offset += 2 + uid_length

    @property
    def item_length(self):
        """Return the Item Length parameter value."""
        return 6 + self.sop_class_uid_length + self.service_class_uid_length + self.related_general_sop_class_identification_length

    @property
    def item_type(self):
        """Return the item type as an int."""
        return 0x57

    def __len__(self):
        """Return the total encoded length of the item."""
        return 4 + self.item_length

    @property
    def _parameters(self):
        return ('item_type',
                0x00,
                'item_length',
                'sop_class_uid_length',
                'sop_class_uid',
                'service_class_uid_length',
                'service_class_uid',
                'related_general_sop_class_identification_length',
                'related_general_sop_class_identification',
                0x00)

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
        """Return the "Related General SOP Class Identification Length" parameter value."""
        length = 0
        for uid in self._related_general_sop_class_identification:
            length += len(uid)

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

        if value is not None:
            self.sop_class_uid_length = len(value)

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

        if value is not None:
            self.service_class_uid_length = len(value)

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

# FIXME: Non generic decode
class UserIdentitySubItemRQ(PDU):
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
        self.primary_field = None
        self.secondary_field = None

        self._offsets = [(0, 1),
                         (1, 2),
                         (2, 4),
                         (4, 5),
                         (5, 6),
                         (6, 8),
                         (8, 'FIXME'),
                         ('FIXME', 'FIXME + 2'),
                         ('FIXME + 2', None)]
        self._decoders = [
            (None, []),  # Item type
            (None, []),  # Reserved
            (None, []),  # Item length
            (self._wrap_unpack, [UNPACK_UCHAR]),  # Identity type
            (self._wrap_unpack, [UNPACK_UCHAR]), # Response requested
            (self._wrap_unpack, [UNPACK_UINT2]),  # Primary field length
            (self._wrap_slice, []),   # Primary field
            (self._wrap_unpack, [UNPACK_UINT2]),  # Secondary field length
            (self._generate_items, [])   # Secondary field, may not be present
        ]

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
        self.primary_field_length = len(self.primary_field)
        self.secondary_field = primitive.secondary_field

        if self.secondary_field is not None:
            self.secondary_field_length = len(self.secondary_field)
        else:
            self.secondary_field_length = 0

        self.item_length = 6 + self.primary_field_length \
                             + self.secondary_field_length

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

    def encode(self):
        """Encode the item"""
        # Override the default
        return self.Encode()

    def Encode(self):
        """
        Encode the Item's parameter values into a bytes string

        TODO:

        * Add checking prior to encode to ensure all parameters are valid
          (should check all extended negotiation items as these are
          typically user defined when local is Requesting)
        * If local requests positive response but doesn't receive then
          abort association if established

        Returns
        -------
        bytestream : bytes
            The encoded Item used in the parent PDU
        """
        formats = '> B B H B B H'
        parameters = [self.item_type,
                      0x00,
                      self.item_length,
                      self.user_identity_type,
                      self.positive_response_requested,
                      self.primary_field_length]

        bytestream = bytes()
        bytestream += pack(formats, *parameters)
        bytestream += bytes(self.primary_field)
        bytestream += pack('>H', self.secondary_field_length)
        if self.user_identity_type == 0x02:
            bytestream += bytes(self.secondary_field)

        return bytestream

    def Decode(self, bytestream):
        """
        Decode the parameter values for the Item from the parent PDU's byte
        stream

        Parameters
        ----------
        bytestream : io.BytesIO
            The byte stream to decode
        """
        (self.item_type,
         _,
         item_length,
         self.user_identity_type,
         self.positive_response_requested,
         primary_field_length) = unpack('>B B H B B H', bytestream.read(8))

        self.primary_field = bytestream.read(primary_field_length)
        (secondary_field_length,) = unpack('>H', bytestream.read(2))

        if self.user_identity_type == 0x02:
            self.secondary_field = bytestream.read(secondary_field_length)

    def decode(self, bytestream):
        self.user_identity_type = UNPACK_UCHAR(bytestream[4:5])[0]
        self.positive_response_requested = UNPACK_UCHAR(bytestream[5:6])[0]
        primary_length = UNPACK_UINT2(bytestream[6:8])[0]
        self.primary_field = bytestream[8:8 + primary_length]
        secondary_length = UNPACK_UINT2(bytestream[8 + primary_length:10 + primary_length])
        if secondary_length:
            self.secondary_field = bytestream[10 + primary_length:]

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
    def _parameters(self):
        if self.secondary_field_length:
            return ('item_type',
                    0x00,
                    'item_length',
                    'user_identity_type',
                    'positive_response_requested',
                    'primary_field_length',
                    'primary_field',
                    'secondary_field_length',
                    'secondary_field')

        return ('item_type',
                0x00,
                'item_length',
                'user_identity_type',
                'positive_response_requested',
                'primary_field_length',
                'primary_field',
                'secondary_field_length')

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


class UserIdentitySubItemAC(PDU):
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

        self._offsets = [(0, 1),
                         (1, 2),
                         (2, 4),
                         (4, 6),
                         (6, None)]
        self._decoders = [
            (None, []),  # Item type
            (None, []),  # Reserved
            (None, []),  # Item length
            (None, []),  # Response length
            (self._wrap_slice, []),   # Server response
        ]

    def FromParams(self, primitive):
        """
        Set up the Item using the parameter values from the `primitive`

        Parameters
        ----------
        primitive : pynetdicom3.pdu_primitives.UserIdentityParameters
            The primitive to use when setting up the Item
        """
        self.server_response = primitive.server_response
        self.server_response_length = len(self.server_response)

        self.item_length = 2 + self.server_response_length

        self._update_parameters()

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

    def Encode(self):
        """
        Encode the Item's parameter values into a bytes string

        Returns
        -------
        bytestream : bytes
            The encoded Item used in the parent PDU
        """
        formats = '> B B H H'
        parameters = [self.item_type,
                      0x00,
                      self.item_length,
                      self.server_response_length]

        bytestream = bytes()
        bytestream += pack(formats, *parameters)
        bytestream += bytes(self.server_response)

        return bytestream

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
    def _parameters(self):
        """Update the parameters"""
        return ('item_type',
                0x00,
                'item_length',
                'server_response_length',
                'server_response')

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


# PDV Sub-item class
class PresentationDataValueItem(PDU):
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

        self._offsets = [(0, 4),
                         (4, 5),
                         (5, None)]
        self._decoders = [
            (None, []),  # Item length
            (self._wrap_unpack, [UNPACK_UCHAR]),  # Presentation context ID
            (self._wrap_slice, []),   # PDV
        ]

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
        self.item_length = 1 + len(self.presentation_data_value)

        self._update_parameters()

    def ToParams(self):
        """
        Convert the current Item to a primitive

        Returns
        -------
        list
            The Presentation Data as a list
        """
        return [self.presentation_context_id, self.presentation_data_value]

    def Encode(self):
        """
        Encode the Item's parameter values into a bytes string

        Returns
        -------
        bytestream : bytes
            The encoded Item used in the parent PDU
        """
        formats = '> I B'
        parameters = [self.item_length,
                      self.presentation_context_id]

        bytestream = bytes()
        bytestream += pack(formats, *parameters)
        bytestream += self.presentation_data_value

        return bytestream

    @property
    def context_id(self):
        """Get the presentation context ID."""
        return self.presentation_context_id

    @property
    def data(self):
        """Get the presentation data value."""
        return self.presentation_data_value

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

    @property
    def _parameters(self):
        """Update the parameters."""
        return ('item_length',
                'presentation_context_id',
                'presentation_data_value')

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


# PDUs, PDU items and sub-items, indexed by their item type
PDU_TYPES = {
    0x01 : A_ASSOCIATE_RQ,
    0x02 : A_ASSOCIATE_AC,
    0x03 : A_ASSOCIATE_RJ,
    0x04 : P_DATA_TF,
    0x05 : A_RELEASE_RQ,
    0x06 : A_RELEASE_RP,
    0x07 : A_ABORT_RQ,
}

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
