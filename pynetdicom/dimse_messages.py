"""Define the DIMSE Message classes."""

from __future__ import division
from io import BytesIO
import logging
from math import ceil

from pydicom.dataset import Dataset
from pydicom.tag import Tag
from pydicom._dicom_dict import DicomDictionary as dcm_dict

from pynetdicom.dimse_primitives import (
    C_STORE, C_FIND, C_GET, C_MOVE, C_ECHO, C_CANCEL,
    N_EVENT_REPORT, N_GET, N_SET, N_ACTION, N_CREATE, N_DELETE
)
from pynetdicom.dsutils import encode_element, encode, decode
from pynetdicom.pdu_primitives import P_DATA


LOGGER = logging.getLogger('pynetdicom.dimse')

_MESSAGE_TYPES = {
    0x0001: 'C-STORE-RQ',
    0x8001: 'C-STORE-RSP',
    0x0020: 'C-FIND-RQ',
    0x8020: 'C-FIND-RSP',
    0x0010: 'C-GET-RQ',
    0x8010: 'C-GET-RSP',
    0x0021: 'C-MOVE-RQ',
    0x8021: 'C-MOVE-RSP',
    0x0030: 'C-ECHO-RQ',
    0x8030: 'C-ECHO-RSP',
    0x0FFF: 'C-CANCEL-RQ',
    0x0100: 'N-EVENT-REPORT-RQ',
    0x8100: 'N-EVENT-REPORT-RSP',
    0x0110: 'N-GET-RQ',
    0x8110: 'N-GET-RSP',
    0x0120: 'N-SET-RQ',
    0x8120: 'N-SET-RSP',
    0x0130: 'N-ACTION-RQ',
    0x8130: 'N-ACTION-RSP',
    0x0140: 'N-CREATE-RQ',
    0x8140: 'N-CREATE-RSP',
    0x0150: 'N-DELETE-RQ',
    0x8150: 'N-DELETE-RSP'
}

# PS3.7 Section 9.3
_COMMAND_SET_ELEM = {
    'C-ECHO-RQ': (
        0x00000000,  # CommandGroupLength
        0x00000002,  # AffectedSOPClassUID
        0x00000100,  # CommandField
        0x00000110,  # MessageID
        0x00000800,  # CommandDataSetType
    ),
    'C-ECHO-RSP': (
        0x00000000, 0x00000002, 0x00000100,
        0x00000120,  # MessageIDBeingRespondedTo
        0x00000800,
        0x00000900,  # Status
        0x00000902,  # ErrorComment
    ),
    'C-STORE-RQ': (
        0x00000000, 0x00000002, 0x00000100, 0x00000110,
        0x00000700,  # Priority
        0x00000800,
        0x00001000,  # AffectedSOPInstanceUID
        0x00001030,  # MoveOriginatorApplicationEntityTitle
        0x00001031,  # MoveOriginatorMessageID
    ),
    'C-STORE-RSP': (
        0x00000000, 0x00000002, 0x00000100,
        0x00000120, 0x00000800, 0x00000900,
        0x00000901,  # OffendingElement
        0x00000902, 0x00001000
    ),
    'C-FIND-RQ': (
        0x00000000, 0x00000002, 0x00000100, 0x00000110, 0x00000700, 0x00000800
    ),
    'C-FIND-RSP': (
        0x00000000, 0x00000002, 0x00000100, 0x00000120,
        0x00000800, 0x00000900, 0x00000901, 0x00000902
    ),
    'C-CANCEL-RQ': (
        0x00000000, 0x00000100, 0x00000120, 0x00000800
    ),
    'C-GET-RQ': (
        0x00000000, 0x00000002, 0x00000100, 0x00000110, 0x00000700, 0x00000800
    ),
    'C-GET-RSP': (
        0x00000000, 0x00000002, 0x00000100, 0x00000120,
        0x00000800, 0x00000900, 0x00000901, 0x00000902,
        0x00001020,  # NumberOfRemainingSuboperations
        0x00001021,  # NumberOfCompletedSuboperations
        0x00001022,  # NumberOfFailedSuboperations
        0x00001023,  # NumberOfWarningSuboperations
    ),
    'C-MOVE-RQ': (
        0x00000000, 0x00000002, 0x00000100,
        0x00000110, 0x00000700, 0x00000800,
        0x00000600,  # MoveDestination
    ),
    'C-MOVE-RSP': (
        0x00000000, 0x00000002, 0x00000100, 0x00000120,
        0x00000800, 0x00000900, 0x00000901, 0x00000902,
        0x00001020, 0x00001021, 0x00001022, 0x00001023
    ),
    'N-EVENT-REPORT-RQ': (
        0x00000000, 0x00000002, 0x00000100,
        0x00000110, 0x00000800, 0x00001000,
        0x00001002,   # EventTypeID
    ),
    'N-EVENT-REPORT-RSP': (
        0x00000000, 0x00000002, 0x00000100, 0x00000120,
        0x00000800, 0x00000900, 0x00001000, 0x00001002,
        0x00001002, 0x00000903, 0x00000902
    ),
    'N-GET-RQ': (
        0x00000000, 0x00000003, 0x00000100, 0x00000110, 0x00000800,
        0x00001001,  # RequestedSOPInstanceUID
        0x00001005,  # AttributeIdentifierList
    ),
    'N-GET-RSP': (
        0x00000000, 0x00000002, 0x00000100, 0x00000120,
        0x00000800, 0x00000900, 0x00001000, 0x00000902,
        0x00000903,  # ErrorID
    ),
    'N-SET-RQ': (
        0x00000000, 0x00000003, 0x00000100, 0x00000110, 0x00000800, 0x00001001
    ),
    'N-SET-RSP': (
        0x00000000, 0x00000002, 0x00000100, 0x00000120,
        0x00000800, 0x00000900, 0x00001000, 0x00001005, 0x00000902, 0x00000903
    ),
    'N-ACTION-RQ': (
        0x00000000, 0x00000003, 0x00000100,
        0x00000110, 0x00000800, 0x00001001,
        0x00001008,  # ActionTypeID
    ),
    'N-ACTION-RSP': (
        0x00000000, 0x00000002, 0x00000100, 0x00000120,
        0x00000800, 0x00000900, 0x00001000, 0x00001008, 0x00000903, 0x00000902
    ),
    'N-CREATE-RQ': (
        0x00000000, 0x00000002, 0x00000100,
        0x00000110, 0x00000800, 0x00001000
    ),
    'N-CREATE-RSP': (
        0x00000000, 0x00000002, 0x00000100, 0x00000120,
        0x00000800, 0x00000900, 0x00001000, 0x00000903, 0x00000902
    ),
    'N-DELETE-RQ': (
        0x00000000, 0x00000003, 0x00000100, 0x00000110, 0x00000800, 0x00001001
    ),
    'N-DELETE-RSP': (
        0x00000000, 0x00000002, 0x00000100, 0x00000120,
        0x00000800, 0x00000900, 0x00001000, 0x00000902, 0x00000903,
    )
}


class DIMSEMessage(object):
    """Represents a DIMSE Message.

    Information is communicated across the DICOM network interface in a DICOM
    Message. A Message is composed of a Command Set followed by a
    conditional Data Set. The Command Set is used to indicate the
    operations/notifications to be performed on or with the Data Set (see
    PS3.7 6.2-3).

    ::

                          primitive_to_message       encode_msg
        .--------------------.  ----->   .----------.  ----->  .------------.
        |       DIMSE        |           |   DIMSE  |          |   P-DATA   |
        |     primitive      |           |  message |          |  primitive |
        .--------------------.  <-----   .----------.  <-----  .------------.
                          message_to_primitive       decode_msg


    **Command Set**

    A Command Set is constructed of Command Elements. Command Elements contain
    the encoded values for each field of the Command Set per the semantics
    specified in the DIMSE protocol (PS3.7 9.2 and 10.2). Each Command Element
    is composed of an explicit Tag, Value Length and a Value field. The encoding
    of the Command Set shall be *Little Endian Implicit VR*.

    **Message Types**

    The following message types are available: C_STORE_RQ, C_STORE_RSP,
    C_ECHO_RQ, C_ECHO_RSP, C_FIND_RQ, C_FIND_RSP, C_GET_RQ, C_GET_RSP,
    C_MOVE_RQ, C_MOVE_RSP, C_CANCEL_RQ, N_EVENT_REPORT_RQ, N_EVENT_REPORT_RSP,
    N_SET_RQ, N_SET_RSP, N_GET_RQ, N_GET_RSP, N_ACTION_RQ, N_ACTION_RSP,
    N_CREATE_RQ, N_CREATE_RSP, N_DELETE_RQ, N_DELETE_RSP.

    Attributes
    ----------
    command_set : pydicom.dataset.Dataset
        The message Command Set information (see PS3.7 6.3).
    context_id : int
        The presentation context ID.
    data_set : io.BytesIO
        The encoded message Data Set (see PS3.7 6.3).
    encoded_command_set : BytesIO
        During decoding of an incoming P-DATA primitive this stores the
        encoded Command Set data from the fragments.
    """
    def __init__(self):
        """Create a new DIMSE Message."""
        self.context_id = None

        # Required to save command set data from multiple fragments
        # self.command_set is added by _build_message_classes()
        self.encoded_command_set = BytesIO()
        self.data_set = BytesIO()

    def decode_msg(self, primitive):
        """Converts P-DATA primitives into a DIMSEMessage sub-class.

        Decodes the data from the P-DATA service primitive (which
        may contain the results of one or more P-DATA-TF PDUs) into the
        `command_set` and `data_set` attributes. Also sets the `ID` and
        `encoded_command_set` attributes of the DIMSEMessage sub-class object.

        Parameters
        ----------
        primitive : pdu_primitives.P_DATA
            The P-DATA service primitive to be decoded into a DIMSE message.

        Returns
        -------
        bool
            True when the DIMSE message is completely decoded, False otherwise.

        References
        ----------

        * DICOM Standard, Part 8, Annex E
        """
        # Make sure this is a P-DATA primitive
        if primitive.__class__ != P_DATA or primitive is None:
            return False

        for (context_id, data) in primitive.presentation_data_value_list:

            # The first byte of the P-DATA is the Message Control Header
            #   See Part 8, Annex E.2
            # The standard says that only the significant bits (ie the last
            #   two) should be checked
            # xxxxxx00 - Message Dataset information, not the last fragment
            # xxxxxx01 - Command information, not the last fragment
            # xxxxxx10 - Message Dataset information, the last fragment
            # xxxxxx11 - Command information, the last fragment

            ## Compatibility
            # Python 2
            #   - data[0] returns length 1 str
            #   - data[:1] returns length 1 str
            # Python 3
            #   - data[0] returns int
            #   - data[:1] returns length 1 bytes
            # So grab str/bytes and convert to int rather than grab
            #   str/int and convert the str to int. The reason for this is
            #   that a type check is twice as expensive as just converting
            #   str/bytes to int
            control_header_byte = ord(data[:1])

            # LOGGER.debug('Control header byte %s', control_header_byte)
            #print('Control header byte {}'.format(control_header_byte))

            # COMMAND SET
            # P-DATA fragment contains Command Set information
            #   (control_header_byte is xxxxxx01 or xxxxxx11)
            if control_header_byte & 1:
                # The command set may be spread out over a number
                #   of fragments and P-DATA primitives and we need to remember
                #   the elements from previous fragments, hence the
                #   encoded_command_set class attribute
                # This adds all the command set data to the class object
                self.encoded_command_set.write(data[1:])

                # The final command set fragment (xxxxxx11) has been added
                #   so decode the command set
                if control_header_byte & 2:
                    # Presentation Context ID
                    #   Set this now as must only be one final command set
                    #   fragment and command set must always be present
                    self.context_id = context_id

                    # Command Set is always encoded Implicit VR Little Endian
                    #   decode(dataset, is_implicit_VR, is_little_endian)
                    # pylint: disable=attribute-defined-outside-init
                    self.command_set = decode(self.encoded_command_set,
                                              True,
                                              True)

                    # Determine which DIMSE Message class to use
                    self.__class__ = _MESSAGE_CLASS_TYPES[
                        self.command_set.CommandField
                    ]

                    # Determine if a Data Set is present by checking for
                    #   (0000, 0800) CommandDataSetType US 1. If the value is
                    #   0x0101 no dataset present, otherwise one is.
                    if self.command_set.CommandDataSetType == 0x0101:
                        # By returning True we're indicating that the message
                        #   has been completely decoded
                        return True

            # DATA SET
            # P-DATA fragment contains Data Set information
            #   (control_header_byte is xxxxxx00 or xxxxxx10)
            else:
                # As with the command set, the data set may be spread over
                #   a number of fragments in each P-DATA primitive and a
                #   number of P-DATA primitives.
                self.data_set.write(data[1:])

                # The final data set fragment (xxxxxx10) has been added
                if control_header_byte & 2 != 0:
                    # By returning True we're indicating that the message
                    #   has been completely decoded
                    return True

        # We return False to indicate that the message isn't yet fully decoded
        return False

    def encode_msg(self, context_id, max_pdu_length):
        """Yield P-DATA primitive(s) for the current DIMSE Message.

        **Encoding**

        The encoding of the Command Set shall be Little Endian Implicit VR,
        while the Data Set will be encoded as per the agreed presentation
        context.

        A P-DATA request PDV List parameter shall contain one or more PDVs.
        Each PDV is wholly contained in a given P-DATA request and doesn't
        span across several P-DATA request primitives.

        The fragmentation of any message results in a series of PDVs that shall
        be sent, on a given association, by a corresponding series of P-DATA
        requests preserving the ordering of the fragments of any message.
        No fragments of any other messages shall be sent until all fragments
        of the current message have been sent.

        Parameters
        ----------
        context_id : int
            The ID of the agreed presentation context.
        max_pdu_length : int
            The maximum PDV length in bytes.

        Yields
        ------
        pdu_primitives.P_DATA
            The current DIMSE message as one or more P-DATA service
            primitives.

        References
        ----------

        * DICOM Standard, Part 7, Section 6.3.1
        * DICOM Standard, Part 8, Annex E
        """
        self.context_id = context_id

        # The Command Set is always Little Endian Implicit VR (PS3.7 6.3.1)
        #   encode(dataset, is_implicit_VR, is_little_endian)
        encoded_command_set = encode(self.command_set, True, True)

        # COMMAND SET (always)
        # Split the command set into fragments with maximum size max_pdu_length
        if max_pdu_length == 0:
            no_fragments = 1
        else:
            no_fragments = ceil(
                len(encoded_command_set) / (max_pdu_length - 6)
            )

        cmd_fragments = self._generate_pdv_fragments(encoded_command_set,
                                                     max_pdu_length)

        # First to (n - 1)th command data fragment - bits xxxxxx01
        for ii in range(int(no_fragments - 1)):
            pdata = P_DATA()
            pdata.presentation_data_value_list.append(
                [context_id, b'\x01' + next(cmd_fragments)]
            )
            yield pdata

        # Last command data fragment - bits xxxxxx11
        pdata = P_DATA()
        pdata.presentation_data_value_list.append(
            [context_id, b'\x03' + next(cmd_fragments)]
        )
        yield pdata

        # DATASET (if available)
        #   Check that the Data Set is not empty
        if self.data_set is not None:
            encoded_data_set = self.data_set.getvalue()
            if encoded_data_set:
                # Split the data set into fragments with maximum
                #   size max_pdu_length
                if max_pdu_length == 0:
                    no_fragments = 1
                else:
                    no_fragments = ceil(
                        len(encoded_data_set) / (max_pdu_length - 6)
                    )
                ds_fragments = self._generate_pdv_fragments(encoded_data_set,
                                                            max_pdu_length)

                # First to (n - 1)th dataset fragment - bits xxxxxx00
                for ii in range(int(no_fragments - 1)):
                    pdata = P_DATA()
                    pdata.presentation_data_value_list.append(
                        [context_id, b'\x00' + next(ds_fragments)]
                    )
                    yield pdata

                # Last dataset fragment - bits xxxxxx10
                pdata = P_DATA()
                pdata.presentation_data_value_list.append(
                    [context_id, b'\x02' + next(ds_fragments)]
                )
                yield pdata

    @staticmethod
    def _generate_pdv_fragments(bytestream, fragment_length):
        """Fragment `bytestream` into chunks, each `fragment_length` long.

        Fragments bytestream data for use in PDVs.

        The Maximum Length Negotiation allows receivers to limit the size of
        the Presentation Data Values List parameters of each P-DATA indication.

        The Association requestor shall specify the maximum length in bytes for
        the PDV list parameter it is ready to receive in each P-DATA
        indication. The Association acceptor shall ensure in its fragmentation
        of the DICOM Messages that the list of PDVs included in each P-DATA
        request does not exceed this maximum length.

        Parameters
        ----------
        bytestream : bytes
            The data to be fragmented.
        fragment_length : int
            The maximum size of each fragment, a value of 0 is taken to mean
            the fragment is infinite. Cannot be between 1 and 7 as
            each Presentation Data Value Item is:
            1 - 4       | 5          | 6 ->
            Item length | Context ID | Presentation data value ->

        Yields
        ------
        fragment : bytes
            A `bytestream` fragment, with maximum length `fragment_length`, but
            may be smaller depending on the size of `bytestream`.

        References
        ----------
        DICOM Standard, Part 8, Annex D.1
        """
        if fragment_length == 0:
            yield bytestream
            return
        elif 0 < fragment_length < 7:
            raise ValueError("'fragment_length' cannot be between 1 and 7.")

        # Because the PDV item includes an extra 6 bytes of data at the start
        #   we need to decrease `fragment_length` by 6 bytes.
        fragment_length -= 6

        offset = 0
        no_pdv = ceil(len(bytestream) / fragment_length)
        for ii in range(int(no_pdv)):
            yield bytestream[offset:offset + fragment_length]
            offset += fragment_length

    def message_to_primitive(self):
        """Convert the DIMSEMessage class to a DIMSE primitive.

        Returns
        -------
        DIMSE message primitive
            One of the DIMSE message primitives from
            pynetdicom.dimse_primitives generated from
            the current DIMSEMessage.
        """
        # pylint: disable=too-many-branches
        cls_type_name = self.__class__.__name__
        if 'C_ECHO' in cls_type_name:
            primitive = C_ECHO()
        elif 'C_STORE' in cls_type_name:
            primitive = C_STORE()
        elif 'C_FIND' in cls_type_name:
            primitive = C_FIND()
        elif 'C_GET' in cls_type_name:
            primitive = C_GET()
        elif 'C_MOVE' in cls_type_name:
            primitive = C_MOVE()
        elif 'C_CANCEL' in cls_type_name:
            primitive = C_CANCEL()
        elif 'N_EVENT' in cls_type_name:
            primitive = N_EVENT_REPORT()
        elif 'N_GET' in cls_type_name:
            primitive = N_GET()
        elif 'N_SET' in cls_type_name:
            primitive = N_SET()
        elif 'N_ACTION' in cls_type_name:
            primitive = N_ACTION()
        elif 'N_CREATE' in cls_type_name:
            primitive = N_CREATE()
        elif 'N_DELETE' in cls_type_name:
            primitive = N_DELETE()

        # Command Set
        # For each parameter in the primitive, set the appropriate value
        #   from the Message's Command Set elements
        for elem in self.command_set:
            if hasattr(primitive, elem.keyword):
                setattr(primitive, elem.keyword,
                        self.command_set.__getattr__(elem.keyword))

        # Datasets
        # Set the primitive's DataSet/Identifier/etc attribute
        try:
            dataset_keyword = _DATASET_KEYWORDS[cls_type_name]
            setattr(primitive, dataset_keyword, self.data_set)
        except KeyError:
            pass

        # Set the presentation context ID the message was set under
        primitive._context_id = self.context_id

        return primitive

    def primitive_to_message(self, primitive):
        """Convert a DIMSE `primitive` to the current DIMSEMessage object.

        Parameters
        ----------
        primitive
            A DIMSE message primitive from pynetdicom.dimse_primitives
            to convert to the current DIMSEMessage object.
        """
        # pylint: disable=too-many-branches,too-many-statements
        cls_type_name = self.__class__.__name__.replace('_', '-')
        if cls_type_name not in _COMMAND_SET_ELEM:
            raise ValueError("Can't convert primitive to message for unknown "
                             "DIMSE message type '{}'".format(cls_type_name))

        # Command Set
        # Convert the message command set to the primitive attributes
        for elem in self.command_set:
            # Use the short version of the element names as these should
            #   match the parameter names in the primitive
            if hasattr(primitive, elem.keyword):
                # If value hasn't been set for a parameter then delete
                #   the corresponding element
                attr = getattr(primitive, elem.keyword)

                if attr is not None:
                    elem.value = attr
                else:
                    del self.command_set[elem.tag]

        # Theres a one-to-one relationship in the _MESSAGE_TYPES dict, so
        #   invert it for convenience
        rev_type = {}
        for value in _MESSAGE_TYPES:
            rev_type[_MESSAGE_TYPES[value]] = value

        self.command_set.CommandField = rev_type[cls_type_name]

        # Data Set
        # Default to no Data Set
        self.data_set = BytesIO()
        self.command_set.CommandDataSetType = 0x0101

        try:
            # These message types *may* have a dataset
            dataset_keyword = _DATASET_KEYWORDS[self.__class__.__name__]
            self.data_set = getattr(primitive, dataset_keyword)
            if self.data_set:
                self.command_set.CommandDataSetType = 0x0001
        except KeyError:
            # The following message types never have a dataset
            # 'C_ECHO_RQ', 'C_ECHO_RSP', 'N_DELETE_RQ', 'C_STORE_RSP',
            # 'C_CANCEL_RQ', 'N_DELETE_RSP', 'C_FIND_RSP', 'N_GET_RQ'
            pass

        # Set the Command Set length
        self._set_command_group_length()

    def _set_command_group_length(self):
        """Reset the Command Group Length element value.

        Once the self.command_set Dataset has been built and filled with
        values, this should be called to set the CommandGroupLength element
        value correctly.
        """
        # Remove CommandGroupLength to stop it messing up the length calc
        del self.command_set.CommandGroupLength

        length = 0
        for elem in self.command_set:
            # The Command Set is always Implicit VR Little Endian
            length += len(encode_element(elem, True, True))

        self.command_set.CommandGroupLength = length


def _build_message_classes(message_name):
    """
    Create a new subclass instance of DIMSEMessage for the given DIMSE
    `message_name`.

    Parameters
    ----------
    message_name : str
        The name/type of message class to construct, one of the following:
        * C-ECHO-RQ
        * C-ECHO-RSP
        * C-STORE-RQ
        * C-STORE-RSP
        * C-FIND-RQ
        * C-FIND-RSP
        * C-GET-RQ
        * C-GET-RSP
        * C-MOVE-RQ
        * C-MOVE-RSP
        * C-CANCEL-RQ
        * N-EVENT-REPORT-RQ
        * N-EVENT-REPORT-RSP
        * N-GET-RQ
        * N-GET-RSP
        * N-SET-RQ
        * N-SET-RSP
        * N-ACTION-RQ
        * N-ACTION-RSP
        * N-CREATE-RQ
        * N-CREATE-RSP
        * N-DELETE-RQ
        * N-DELETE-RSP
    """

    def __init__(self):
        DIMSEMessage.__init__(self)
        # Create a new Dataset object for the command_set attributes
        ds = Dataset()
        for elem_tag in _COMMAND_SET_ELEM[message_name]:
            tag = Tag(elem_tag)
            vr = dcm_dict[elem_tag][0]

            # If the required command set elements are expanded this will need
            #   to be checked to ensure it functions OK
            try:
                ds.add_new(tag, vr, None)
            except TypeError:
                ds.add_new(tag, vr, '')

        self.command_set = ds

    # Create new subclass of DIMSE Message using the supplied name
    #   but replace hyphens with underscores
    cls = type(message_name.replace('-', '_'),
               (DIMSEMessage, ),
               {"__init__": __init__})

    # Add the class to the module
    globals()[cls.__name__] = cls

    return cls


for __msg_type in _COMMAND_SET_ELEM:
    _build_message_classes(__msg_type)

# Values from PS3.5
_MESSAGE_CLASS_TYPES = {
    0x0001: C_STORE_RQ,
    0x8001: C_STORE_RSP,
    0x0020: C_FIND_RQ,
    0x8020: C_FIND_RSP,
    0x0FFF: C_CANCEL_RQ,
    0x0010: C_GET_RQ,
    0x8010: C_GET_RSP,
    0x0021: C_MOVE_RQ,
    0x8021: C_MOVE_RSP,
    0x0030: C_ECHO_RQ,
    0x8030: C_ECHO_RSP,
    0x0100: N_EVENT_REPORT_RQ,
    0x8100: N_EVENT_REPORT_RSP,
    0x0110: N_GET_RQ,
    0x8110: N_GET_RSP,
    0x0120: N_SET_RQ,
    0x8120: N_SET_RSP,
    0x0130: N_ACTION_RQ,
    0x8130: N_ACTION_RSP,
    0x0140: N_CREATE_RQ,
    0x8140: N_CREATE_RSP,
    0x0150: N_DELETE_RQ,
    0x8150: N_DELETE_RSP
}

_DATASET_KEYWORDS = {
    'C_STORE_RQ' : 'DataSet',
    'C_FIND_RQ' : 'Identifier',
    'C_GET_RQ' : 'Identifier',
    'C_MOVE_RQ' : 'Identifier',
    'C_FIND_RSP' : 'Identifier',
    'C_GET_RSP' : 'Identifier',
    'C_MOVE_RSP' : 'Identifier',
    'N_EVENT_REPORT_RQ' : 'EventInformation',
    'N_EVENT_REPORT_RSP' : 'EventReply',
    'N_GET_RSP' : 'AttributeList',
    'N_SET_RSP' : 'AttributeList',
    'N_CREATE_RQ' : 'AttributeList',
    'N_CREATE_RSP' : 'AttributeList',
    'N_SET_RQ' : 'ModificationList',
    'N_ACTION_RQ' : 'ActionInformation',
    'N_ACTION_RSP' : 'ActionReply',
}
