"""Define the DIMSE Message classes."""

from __future__ import division
from io import BytesIO
import logging
from math import ceil

from pydicom.dataset import Dataset

from pynetdicom.dimse_primitives import (
    C_STORE, C_FIND, C_GET, C_MOVE, C_ECHO, C_CANCEL,
    N_EVENT_REPORT, N_GET, N_SET, N_ACTION, N_CREATE, N_DELETE
)
from pynetdicom.dsutils import encode, decode
from pynetdicom.pdu_primitives import P_DATA


LOGGER = logging.getLogger('pynetdicom.dimse')


# PS3.7 Section 9.3
_COMMAND_SET_KEYWORDS = {
    'C-ECHO-RQ': (
        'CommandGroupLength', 'AffectedSOPClassUID', 'CommandField',
        'MessageID', 'CommandDataSetType',
    ),
    'C-ECHO-RSP': (
        'CommandGroupLength', 'AffectedSOPClassUID', 'CommandField',
        'MessageIDBeingRespondedTo', 'CommandDataSetType', 'Status',
        'ErrorComment',
    ),
    'C-STORE-RQ': (
        'CommandGroupLength', 'AffectedSOPClassUID', 'CommandField',
        'MessageID', 'Priority', 'CommandDataSetType',
        'AffectedSOPInstanceUID', 'MoveOriginatorApplicationEntityTitle',
        'MoveOriginatorMessageID',
    ),
    'C-STORE-RSP': (
        'CommandGroupLength', 'AffectedSOPClassUID', 'CommandField',
        'MessageIDBeingRespondedTo', 'CommandDataSetType', 'Status',
        'AffectedSOPInstanceUID',
        'OffendingElement', 'ErrorComment',
    ),
    'C-FIND-RQ': (
        'CommandGroupLength', 'AffectedSOPClassUID', 'CommandField',
        'MessageID', 'Priority', 'CommandDataSetType'
    ),
    'C-FIND-RSP': (
        'CommandGroupLength', 'AffectedSOPClassUID', 'CommandField',
        'MessageIDBeingRespondedTo', 'CommandDataSetType', 'Status',
        'OffendingElement', 'ErrorComment'
    ),
    'C-CANCEL-RQ': (
        'CommandGroupLength', 'CommandField', 'MessageIDBeingRespondedTo',
        'CommandDataSetType'
    ),
    'C-GET-RQ': (
        'CommandGroupLength', 'AffectedSOPClassUID', 'CommandField',
        'MessageID', 'Priority', 'CommandDataSetType'
    ),
    'C-GET-RSP': (
        'CommandGroupLength', 'AffectedSOPClassUID', 'CommandField',
        'MessageIDBeingRespondedTo', 'CommandDataSetType', 'Status',
        'NumberOfRemainingSuboperations', 'NumberOfCompletedSuboperations',
        'NumberOfFailedSuboperations', 'NumberOfWarningSuboperations',
        'OffendingElement', 'ErrorComment',
    ),
    'C-MOVE-RQ': (
        'CommandGroupLength', 'AffectedSOPClassUID', 'CommandField',
        'MessageID', 'Priority', 'CommandDataSetType', 'MoveDestination',
    ),
    'C-MOVE-RSP': (
        'CommandGroupLength', 'AffectedSOPClassUID', 'CommandField',
        'MessageIDBeingRespondedTo', 'CommandDataSetType', 'Status',
        'NumberOfRemainingSuboperations', 'NumberOfCompletedSuboperations',
        'NumberOfFailedSuboperations', 'NumberOfWarningSuboperations',
        'OffendingElement', 'ErrorComment'
    ),
    'N-EVENT-REPORT-RQ': (
        'CommandGroupLength', 'AffectedSOPClassUID', 'CommandField',
        'MessageID', 'CommandDataSetType', 'AffectedSOPInstanceUID',
        'EventTypeID',
    ),
    'N-EVENT-REPORT-RSP': (
        'CommandGroupLength', 'AffectedSOPClassUID', 'CommandField',
        'MessageIDBeingRespondedTo', 'CommandDataSetType', 'Status',
        'AffectedSOPInstanceUID', 'EventTypeID', 'EventTypeID',
        'ErrorID', 'ErrorComment'
    ),
    'N-GET-RQ': (
        'CommandGroupLength', 'RequestedSOPClassUID', 'CommandField',
        'MessageID', 'CommandDataSetType', 'RequestedSOPInstanceUID',
        'AttributeIdentifierList',
    ),
    'N-GET-RSP': (
        'CommandGroupLength', 'AffectedSOPClassUID', 'CommandField',
        'MessageIDBeingRespondedTo', 'CommandDataSetType', 'Status',
        'AffectedSOPInstanceUID',
        'AttributeIdentifierList', 'ErrorComment', 'ErrorID',
    ),
    'N-SET-RQ': (
        'CommandGroupLength', 'RequestedSOPClassUID', 'CommandField',
        'MessageID', 'CommandDataSetType', 'RequestedSOPInstanceUID'
    ),
    'N-SET-RSP': (
        'CommandGroupLength', 'AffectedSOPClassUID', 'CommandField',
        'MessageIDBeingRespondedTo', 'CommandDataSetType', 'Status',
        'AffectedSOPInstanceUID',
        'AttributeIdentifierList', 'ErrorComment', 'ErrorID'
    ),
    'N-ACTION-RQ': (
        'CommandGroupLength', 'RequestedSOPClassUID', 'CommandField',
        'MessageID', 'CommandDataSetType', 'RequestedSOPInstanceUID',
        'ActionTypeID',
    ),
    'N-ACTION-RSP': (
        'CommandGroupLength', 'AffectedSOPClassUID', 'CommandField',
        'MessageIDBeingRespondedTo', 'CommandDataSetType', 'Status',
        'AffectedSOPInstanceUID', 'ActionTypeID',
        'ErrorID', 'ErrorComment'
    ),
    'N-CREATE-RQ': (
        'CommandGroupLength', 'AffectedSOPClassUID', 'CommandField',
        'MessageID', 'CommandDataSetType', 'AffectedSOPInstanceUID'
    ),
    'N-CREATE-RSP': (
        'CommandGroupLength', 'AffectedSOPClassUID', 'CommandField',
        'MessageIDBeingRespondedTo', 'CommandDataSetType', 'Status',
        'AffectedSOPInstanceUID',
        'ErrorID', 'ErrorComment'
    ),
    'N-DELETE-RQ': (
        'CommandGroupLength', 'RequestedSOPClassUID', 'CommandField',
        'MessageID', 'CommandDataSetType', 'RequestedSOPInstanceUID'
    ),
    'N-DELETE-RSP': (
        'CommandGroupLength', 'AffectedSOPClassUID', 'CommandField',
        'MessageIDBeingRespondedTo', 'CommandDataSetType', 'Status',
        'AffectedSOPInstanceUID',
        'ErrorComment', 'ErrorID',
    )
}

# Used with DIMSEMessage.message_to_primitive
_MSG_TO_PRIMITVE = {
    'C_ECHO' : C_ECHO,
    'C_STORE' : C_STORE,
    'C_FIND' : C_FIND,
    'C_GET' : C_GET,
    'C_MOVE' : C_MOVE,
    'C_CANCEL' : C_CANCEL,
    'N_EVENT_REPORT' : N_EVENT_REPORT,
    'N_GET' : N_GET,
    'N_SET' : N_SET,
    'N_ACTION' : N_ACTION,
    'N_CREATE' : N_CREATE,
    'N_DELETE' : N_DELETE,
}


class DIMSEMessage(object):
    """Represents a DIMSE Message.

    Information is communicated across the DICOM network interface in a DICOM
    Message. A Message is composed of a Command Set followed by a
    conditional Data Set. The Command Set is used to indicate the
    operations/notifications to be performed on or with the Data Set (see
    PS3.7 6.2-3).

    ::

                primitive_to_message()       encode_msg()
        +-------------+   --->    +-----------+   --->   +-------------+
        |    DIMSE    |           |   DIMSE   |          |   P-DATA    |
        |  primitive  |           |  Message  |          |  primitive  |
        +-------------+   <---    +-----------+   <---   +-------------+
                message_to_primitive()       decode_msg()


    **Command Set**

    A Command Set is constructed of Command Elements. Command Elements contain
    the encoded values for each field of the Command Set per the semantics
    specified in the DIMSE protocol (PS3.7 9.2 and 10.2). Each Command Element
    is composed of an explicit Tag, Value Length and a Value field. The
    encoding of the Command Set shall be *Little Endian Implicit VR*.

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
        self.encoded_command_set = BytesIO()
        self.data_set = BytesIO()
        self.command_set = Dataset()

        cls_name = self.__class__.__name__
        if cls_name == 'DIMSEMessage':
            return

        # Set the command set attributes for the subclasses
        for keyword in _COMMAND_SET_KEYWORDS[cls_name.replace('_', '-')]:
            setattr(self.command_set, keyword, None)

    def decode_msg(self, primitive):
        """Converts P-DATA primitives into a ``DIMSEMessage`` sub-class.

        Decodes the data from the P-DATA service primitive (which
        may contain the results of one or more P-DATA-TF PDUs) into the
        :attr:`~DIMSEMessage.command_set` and :attr:`~DIMSEMessage.data_set`
        attributes. Also sets the :attr:`~DIMSEMessage.context_id` and
        :attr:`~DIMSEMessage.encoded_command_set` attributes of the
        ``DIMSEMessage`` sub-class object.

        Parameters
        ----------
        primitive : pdu_primitives.P_DATA
            The P-DATA service primitive to be decoded into a DIMSE message.

        Returns
        -------
        bool
            ``True`` when the DIMSE message is completely decoded, ``False``
            otherwise.

        References
        ----------

        * DICOM Standard, Part 8, :dcm:`Annex E<part08/chapter_E.html>`
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
                    self.command_set = decode(
                        self.encoded_command_set, True, True
                    )

                    # Determine which DIMSE Message class to use
                    self.__class__ = (
                        _MESSAGE_TYPES[self.command_set.CommandField][1]
                    )

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
        """Yield P-DATA primitives for the current DIMSE Message.

        **Encoding**

        The encoding of the Command Set shall be *Little Endian Implicit VR*,
        while the *Data Set* will be encoded as per the agreed presentation
        context.

        A P-DATA request's PDV List parameter shall contain one or more PDVs.
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
            The *ID* of the agreed presentation context.
        max_pdu_length : int
            The maximum PDV length (in bytes).

        Yields
        ------
        pdu_primitives.P_DATA
            The current DIMSE message as one or more P-DATA service
            primitives.

        References
        ----------

        * DICOM Standard, Part 7,
          :dcm:`Section 6.3.1<part07/sect_6.3.html#sect_6.3.1>`
        * DICOM Standard, Part 8, :dcm:`Annex E<part08/chapter_E.html>`
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
            each Presentation Data Value Item is::

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
        """Convert the ``DIMSEMessage`` class to a DIMSE primitive.

        Returns
        -------
        DIMSEPrimitive sub-class
            One of the DIMSE message primitives from
            :ref:`pynetdicom.dimse_primitives<api_dimse_primitives>` generated
            from the current ``DIMSEMessage`` sub-class object.
        """
        cls_type_name = self.__class__.__name__
        final_underscore = cls_type_name.rfind('_R')
        primitive = _MSG_TO_PRIMITVE[cls_type_name[:final_underscore]]()

        # Command Set
        # For each parameter in the primitive, set the appropriate value
        #   from the Message's Command Set elements
        for elem in self.command_set:
            if hasattr(primitive, elem.keyword):
                setattr(primitive, elem.keyword, elem.value)

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
        """Convert a DIMSE `primitive` to the current ``DIMSEMessage`` object.

        Parameters
        ----------
        DIMSEPrimitive sub-class
            A DIMSE message primitive from
            :ref:`pynetdicom.dimse_primitives<api_dimse_primitives>`
            to convert to the current ``DIMSEMessage`` object.
        """
        # pylint: disable=too-many-branches,too-many-statements
        cls_type_name = self.__class__.__name__.replace('_', '-')
        if cls_type_name not in _COMMAND_SET_KEYWORDS:
            raise ValueError(
                "Can't convert primitive to message for unknown "
                "DIMSE message type '{}'".format(cls_type_name)
            )

        # Command Set
        # Convert the message command set to the primitive attributes
        for elem in self.command_set:
            # Use the element keyword as these should match the parameter
            #   names in the primitive
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
        rev_type = {vv[0]: kk for kk, vv in _MESSAGE_TYPES.items()}
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

        Once the `command_set` Dataset has been built and filled with
        values, this should be called to set the (Command Group Length* element
        value correctly.
        """
        # Remove CommandGroupLength to stop it messing up the length calc
        del self.command_set.CommandGroupLength

        # The Command Set is always Implicit VR Little Endian
        self.command_set.CommandGroupLength = len(
            encode(self.command_set, True, True)
        )


# Create DIMSEMessage subclasses and add them to the module
for _msg_name in _COMMAND_SET_KEYWORDS:
    cls = type(_msg_name.replace('-', '_'), (DIMSEMessage, ), {})
    globals()[cls.__name__] = cls


# Values from PS3.5
_MESSAGE_TYPES = {
    0x0001: ('C-STORE-RQ', C_STORE_RQ),
    0x8001: ('C-STORE-RSP', C_STORE_RSP),
    0x0020: ('C-FIND-RQ', C_FIND_RQ),
    0x8020: ('C-FIND-RSP', C_FIND_RSP),
    0x0010: ('C-GET-RQ', C_GET_RQ),
    0x8010: ('C-GET-RSP', C_GET_RSP),
    0x0021: ('C-MOVE-RQ', C_MOVE_RQ),
    0x8021: ('C-MOVE-RSP', C_MOVE_RSP),
    0x0030: ('C-ECHO-RQ', C_ECHO_RQ),
    0x8030: ('C-ECHO-RSP', C_ECHO_RSP),
    0x0FFF: ('C-CANCEL-RQ', C_CANCEL_RQ),
    0x0100: ('N-EVENT-REPORT-RQ', N_EVENT_REPORT_RQ),
    0x8100: ('N-EVENT-REPORT-RSP', N_EVENT_REPORT_RSP),
    0x0110: ('N-GET-RQ', N_GET_RQ),
    0x8110: ('N-GET-RSP', N_GET_RSP),
    0x0120: ('N-SET-RQ', N_SET_RQ),
    0x8120: ('N-SET-RSP', N_SET_RSP),
    0x0130: ('N-ACTION-RQ', N_ACTION_RQ),
    0x8130: ('N-ACTION-RSP', N_ACTION_RSP),
    0x0140: ('N-CREATE-RQ', N_CREATE_RQ),
    0x8140: ('N-CREATE-RSP', N_CREATE_RSP),
    0x0150: ('N-DELETE-RQ', N_DELETE_RQ),
    0x8150: ('N-DELETE-RSP', N_DELETE_RSP),
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
