"""
Define the DIMSE Message classes

TODO: Rename Encode and Decode methods to lowercase
"""
from io import BytesIO
import logging
from struct import pack

from pydicom.dataset import Dataset
from pydicom.tag import Tag
from pydicom._dicom_dict import DicomDictionary as dcm_dict

from pynetdicom3.dimse_primitives import C_STORE, \
                                        C_FIND, \
                                        C_GET, \
                                        C_MOVE, \
                                        C_ECHO, \
                                        N_EVENT_REPORT, \
                                        N_GET, \
                                        N_SET, \
                                        N_ACTION, \
                                        N_CREATE, \
                                        N_DELETE
from pynetdicom3.dsutils import encode_element, encode, decode
from pynetdicom3.primitives import P_DATA
from pynetdicom3.utils import wrap_list

LOGGER = logging.getLogger('pynetdicom3.dimse')

MESSAGE_TYPE = {0x0001 : 'C-STORE-RQ', 0x8001 : 'C-STORE-RSP',
                0x0020 : 'C-FIND-RQ', 0x8020 : 'C-FIND-RSP',
                0x0010 : 'C-GET-RQ', 0x8010 : 'C-GET-RSP',
                0x0021 : 'C-MOVE-RQ', 0x8021 : 'C-MOVE-RSP',
                0x0030 : 'C-ECHO-RQ', 0x8030 : 'C-ECHO-RSP',
                0x0FFF : 'C-CANCEL-RQ',
                0x0100 : 'N-EVENT-REPORT-RQ', 0x8100 : 'N-EVENT-REPORT-RSP',
                0x0110 : 'N-GET-RQ', 0x8110 : 'N-GET-RSP',
                0x0120 : 'N-SET-RQ', 0x8120 : 'N-SET-RSP',
                0x0130 : 'N-ACTION-RQ', 0x8130 : 'N-ACTION-RSP',
                0x0140 : 'N-CREATE-RQ', 0x8140 : 'N-CREATE-RSP',
                0x0150 : 'N-DELETE-RQ', 0x8150 : 'N-DELETE-RSP'}

# PS3.7 Section 9.3
COMMAND_SET_ELEM = {'C-ECHO-RQ' : [0x00000000,  # CommandGroupLength
                                   0x00000002,  # AffectedSOPClassUID
                                   0x00000100,  # CommandField
                                   0x00000110,  # MessageID
                                   0x00000800], # CommandDataSetType
                    'C-ECHO-RSP' : [0x00000000, 0x00000002, 0x00000100,
                                    0x00000120,  # MessageIDBeingRespondedTo
                                    0x00000800,
                                    0x00000900], # Status
                    'C-STORE-RQ' : [0x00000000, 0x00000002, 0x00000100,
                                    0x00000110,
                                    0x00000700,  # Priority
                                    0x00000800,
                                    0x00001000,  # AffectedSOPInstanceUID
                                    # MoveOriginatorApplicationEntityTitle
                                    0x00001030,
                                    0x00001031], # MoveOriginatorMessageID
                    'C-STORE-RSP' : [0x00000000, 0x00000002, 0x00000100,
                                     0x00000120, 0x00000800, 0x00000900,
                                     0x00001000],
                    'C-FIND-RQ' : [0x00000000, 0x00000002, 0x00000100,
                                   0x00000110, 0x00000700, 0x00000800],
                    'C-FIND-RSP' : [0x00000000, 0x00000002, 0x00000100,
                                    0x00000120, 0x00000800, 0x00000900],
                    'C-CANCEL-RQ' : [0x00000000, 0x00000100, 0x00000120,
                                     0x00000800],
                    'C-GET-RQ' : [0x00000000, 0x00000002, 0x00000100,
                                  0x00000110, 0x00000700, 0x00000800],
                    'C-GET-RSP' : [0x00000000, 0x00000002, 0x00000100,
                                   0x00000120, 0x00000800, 0x00000900,
                                   0x00001020,  # NumberOfRemainingSuboperations
                                   0x00001021,  # NumberOfCompletedSuboperations
                                   0x00001022,  # NumberOfFailedSuboperations
                                   0x00001023], # NumberOfWarningSuboperations
                    'C-MOVE-RQ' : [0x00000000, 0x00000002, 0x00000100,
                                   0x00000110, 0x00000700, 0x00000800,
                                   0x00000600],
                    'C-MOVE-RSP' : [0x00000000, 0x00000002, 0x00000100,
                                    0x00000120, 0x00000800, 0x00000900,
                                    0x00001020, 0x00001021, 0x00001022,
                                    0x00001023],
                    'N-EVENT-REPORT-RQ' : [0x00000000, 0x00000002, 0x00000100,
                                           0x00000110, 0x00000800, 0x00001000,
                                           0x00001002], # EventTypeID
                    'N-EVENT-REPORT-RSP' : [0x00000000, 0x00000002, 0x00000100,
                                            0x00000120, 0x00000800, 0x00000900,
                                            0x00001000, 0x00001002],
                    'N-GET-RQ' : [0x00000000, 0x00000003, 0x00000100,
                                  0x00000110, 0x00000800,
                                  0x00001001,  # RequestedSOPInstanceUID
                                  0x00001005], # AttributeIdentifierList
                    'N-GET-RSP' : [0x00000000, 0x00000002, 0x00000100,
                                   0x00000120, 0x00000800, 0x00000900,
                                   0x00001000],
                    'N-SET-RQ' : [0x00000000, 0x00000003, 0x00000100,
                                  0x00000110, 0x00000800, 0x00001001],
                    'N-SET-RSP' : [0x00000000, 0x00000002, 0x00000100,
                                   0x00000120, 0x00000800, 0x00000900,
                                   0x00001000],
                    'N-ACTION-RQ' : [0x00000000, 0x00000003, 0x00000100,
                                     0x00000110, 0x00000800, 0x00001001,
                                     0x00001008], # ActionTypeID
                    'N-ACTION-RSP' : [0x00000000, 0x00000002, 0x00000100,
                                      0x00000120, 0x00000800, 0x00000900,
                                      0x00001000, 0x00001008],
                    'N-CREATE-RQ' : [0x00000000, 0x00000002, 0x00000100,
                                     0x00000110, 0x00000800, 0x00001000],
                    'N-CREATE-RSP' : [0x00000000, 0x00000002, 0x00000100,
                                      0x00000120, 0x00000800, 0x00000900,
                                      0x00001000],
                    'N-DELETE-RQ' : [0x00000000, 0x00000003, 0x00000100,
                                     0x00000110, 0x00000800, 0x00001001],
                    'N-DELETE-RSP' : [0x00000000, 0x00000002, 0x00000100,
                                      0x00000120, 0x00000800, 0x00000900,
                                      0x00001000]}


class DIMSEMessage(object):
    """Represents a DIMSE *Message*.

    Information is communicated across the DICOM network interface in a DICOM
    *Message*. A *Message* is composed of a Command Set followed by a
    conditional Data Set. The Command Set is used to indicate the
    operations/notifications to be performed on or with the Data Set.
    (PS3.7 6.2-3)

                        primitive_to_message         Encode
    .----------------------.  ----->   .----------.  ----->  .---------------.
    |   DIMSE parameters   |           |   DIMSE  |          |     P-DATA    |
    |       primitive      |           |  message |          |   primitive   |
    .----------------------.  <-----   .----------.  <-----  .---------------.
                        message_to_primitive         Decode

    Command Set
    -----------
    A Command Set is constructed of Command Elements. Command Elements contain
    the encoded values for each field of the Command Set per the semantics
    specified in the DIMSE protocol (PS3.7 9.2 and 10.2). Each Command Element
    is composed of an explicit Tag, Value Length and a Value field. The encoding
    of the Command Set shall be *Little Endian Implicit VR*.

    Attributes
    ----------
    command_set : pydicom.dataset.Dataset
        The message Command Set information (PS3.7 6.3)
    data_set : pydicom.dataset.Dataset
        The message Data Set (PS3.7 6.3)
    encoded_command_set : BytesIO
        During decoding of an incoming P-DATA primitive this stores the
        encoded Command Set data from the fragments
    ID : int
        The presentation context ID
    """
    def __init__(self):
        # Context ID - rename to context_id?
        self.ID = None

        # Required to save command set data from multiple fragments
        # self.command_set is added by _build_message_classes()
        # and contains the elements required by the subclass
        self.encoded_command_set = BytesIO()
        self.data_set = BytesIO()

    def Encode(self, context_id, max_pdu):
        """
        Encode the DIMSE Message as one or more P-DATA service primitives

        PS3.7 6.3.1
        The encoding of the Command Set shall be Little Endian Implicit VR

        Parameters
        ----------
        context_id : int
            The ID of the presentation context agreed to under which we are
            sending the data
        max_pdu_length : int
            The maximum PDU length in bytes

        Returns
        -------
        p_data_list : list of pynetdicom3.primitives.P_DATA
            A list of one or more P-DATA service primitives
        """
        self.ID = context_id
        p_data_list = []

        # The Command Set is always Little Endian Implicit VR (PS3.7 6.3.1)
        #   encode(dataset, is_implicit_VR, is_little_endian)
        encoded_command_set = encode(self.command_set, True, True)

        ## COMMAND SET
        # Split the command set into framents with maximum size max_pdu
        pdvs = self._fragment_pdv(encoded_command_set, max_pdu)

        # First to (n - 1)th command data fragment - b XXXXXX01
        for ii in pdvs[:-1]:
            pdata = P_DATA()
            pdata.presentation_data_value_list = [[self.ID, pack('b', 1) + ii]]

            p_data_list.append(pdata)

        # Nth command data fragment - b XXXXXX11
        pdata = P_DATA()
        pdata.presentation_data_value_list = [[self.ID,
                                               pack('b', 3) + pdvs[-1]]]

        p_data_list.append(pdata)

        ## DATASET (if available)
        # Split out dataset up into fragment with maximum size of max_pdu
        #   Check that the Data Set is not empty
        if self.data_set is None:
            pass
        elif self.data_set.getvalue() != b'':
            # Technically these are APDUs, not PDVs
            pdvs = self._fragment_pdv(self.data_set, max_pdu)

            # First to (n - 1)th dataset fragment - b XXXXXX00
            for ii in pdvs[:-1]:
                pdata = P_DATA()
                pdata.presentation_data_value_list = [[self.ID,
                                                       pack('b', 0) + ii]]
                p_data_list.append(pdata)

            # Nth dataset fragment - b XXXXXX10
            pdata = P_DATA()
            pdata.presentation_data_value_list = [[self.ID,
                                                   pack('b', 2) + pdvs[-1]]]

            p_data_list.append(pdata)

        return p_data_list

    def Decode(self, pdata):
        """ Converts a series of P-DATA primitives into data for the DIMSE
        Message

        Decodes the data from the P-DATA service primitive (which
        may contain the results of one or more P-DATA-TF PDUs) into the
        `command_set` and `data_set` attributes. Also sets the `ID` and
        `encoded_command_set` attributes

        PS3.9 Section 9.3.1: The encoding of the DICOM UL PDUs is
        big endian byte ordering, while the encoding of the PDV message
        fragments is defined by the negotiated Transfer Syntax at association
        establishment. A fragment is also known as an Application Protocol
        Data Unit (APDU) using the OSI nomenclature (PS3.7 8.1).

        Parameters
        ----------
        pdata : pynetdicom3.primitives.P_DATA
            The P-DATA service primitive to be decoded into a DIMSE message

        Returns
        -------
        bool
            True when complete, False otherwise.
        """
        # Make sure this is a P-DATA primitive
        if pdata.__class__ != P_DATA or pdata is None:
            return False

        for pdv_item in pdata.presentation_data_value_list:
            # Presentation Context ID
            self.ID = pdv_item[0]

            # The first byte of the P-DATA is the Message Control Header
            #   See PS3.8 Annex E.2
            # The standard says that only the significant bits (ie the last
            #   two) should be checked
            # xxxxxx00 - Message Dataset information, not the last fragment
            # xxxxxx01 - Command information, not the last fragment
            # xxxxxx10 - Message Dataset information, the last fragment
            # xxxxxx11 - Command information, the last fragment
            control_header_byte = pdv_item[1][0]

            ## COMMAND SET
            # P-DATA fragment contains Command information
            #   (control_header_byte is xxxxxx01 or xxxxxx11)
            if control_header_byte & 1:
                # The command set may be spread out over a number
                #   of fragments and we need to remember the elements
                #   from previous fragments, hence the encoded_command_set
                #   class attribute
                self.encoded_command_set.write(pdv_item[1][1:])

                # The P-DATA fragment is the last one (xxxxxx11)
                if control_header_byte & 2:
                    # Command Set is always encoded Implicit VR Little Endian
                    #   decode(dataset, is_implicit_VR, is_little_endian)
                    self.command_set = decode(self.encoded_command_set,
                                              True, True)

                    # Determine which DIMSE Message class to use
                    self.__class__ = \
                        MESSAGE_TYPE_CLASS[self.command_set.CommandField]

                    # (0000, 0800) CommandDataSetType US 1
                    #   if value is 0101H no dataset present
                    #   otherwise a dataset is included in the Message
                    if self.command_set.CommandDataSetType == 0x0101:
                        return True

            ## DATA SET
            # P-DATA fragment contains Message Dataset information
            #   (control_header_byte is xxxxxx00 or xxxxxx10)
            else:
                self.data_set.write(pdv_item[1][1:])

                # The P-DATA fragment is the last one (xxxxxx10)
                if control_header_byte & 2 != 0:
                    return True

        return False

    def _set_command_group_length(self):
        """
        Once the self.command_set Dataset has been built and filled with values,
        this should be called to set the CommandGroupLength element value
        correctly.
        """
        length = 0

        # Remove CommandGroupLength from dataset to prevent it from messing
        #   with our length calculation.
        # We have to use the tag value due to a bug in pydicom 1.0.0
        del self.command_set[0x00000000]
        for ii in list(self.command_set.values()):
            #   encode_element(elem, is_implicit_VR, is_little_endian)
            length += len(encode_element(ii, True, True))

        # Add the CommandGroupLength element back to the dataset with the
        #   correct value
        self.command_set.CommandGroupLength = length

    @staticmethod
    def _fragment_pdv(bytestream, fragment_length):
        """Fragment `bytestream`, each `max_size` long.

        Fragments bytestream data for use in PDVs.

        Parameters
        ----------
        bytestream : bytes or io.BytesIO
            The data to be fragmented
        fragment_length : int
            The maximum size of each fragment

        Returns
        -------
        fragments : list of bytes
            The fragmented `bytestream`
        """
        if not isinstance(bytestream, (BytesIO, bytes)):
            raise TypeError

        if fragment_length < 1:
            raise ValueError('Max bytes per PDV must be at least 1.')

        # Convert bytestream to bytes
        if isinstance(bytestream, BytesIO):
            bytestream = bytestream.getvalue()

        fragments = []
        while len(bytestream) > 0:
            # Add the fragment
            fragments.append(bytestream[:fragment_length])
            # Remove the fragment from the bytestream
            bytestream = bytestream[fragment_length:]

        return fragments

    def primitive_to_message(self, primitive):
        """
        Convert a DIMSE service parameters primitive to the current DIMSE
        message object

        Parameters
        ----------
        primitive : pynetdicom3.primitives DIMSE service parameter
            The primitive to convert to the current DIMSE Message object
        """
        ## Command Set
        # Due to the del self.command_set[elem.tag] line below this may
        #   end up permanently removing the element from the DIMSE message class
        #   so we refresh the command set elements
        cls_type_name = self.__class__.__name__.replace('_', '-')
        command_set_tags = [elem.tag for elem in self.command_set]

        if cls_type_name not in COMMAND_SET_ELEM:
            raise ValueError("Can't convert primitive to message for unknown "
                             "DIMSE message type '{}'".format(cls_type_name))

        for tag in COMMAND_SET_ELEM[cls_type_name]:
            if tag not in command_set_tags:
                tag = Tag(tag)
                vr = dcm_dict[tag][0]
                try:
                    self.command_set.add_new(tag, vr, None)
                except TypeError:
                    self.command_set.add_new(tag, vr, '')

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
                    del self.command_set[elem.tag] # Careful!

        # Theres a one-to-one relationship in the MESSAGE_TYPE dict, so invert
        #   it for convenience
        rev_type = {}
        for value in MESSAGE_TYPE:
            rev_type[MESSAGE_TYPE[value]] = value

        self.command_set.CommandField = rev_type[cls_type_name]

        ## Data Set
        # Default to no Data Set
        self.data_set = BytesIO()
        self.command_set.CommandDataSetType = 0x0101

        # These message types should (except for C-FIND-RSP) always have
        #   a Data Set
        cls_type_name = self.__class__.__name__
        if cls_type_name == 'C_STORE_RQ':
            self.data_set = primitive.DataSet
            self.command_set.CommandDataSetType = 0x0001
        elif cls_type_name in ['C_FIND_RQ', 'C_GET_RQ', 'C_GET_RSP',
                               'C_MOVE_RQ', 'C_MOVE_RSP']:
            self.data_set = primitive.Identifier
            self.command_set.CommandDataSetType = 0x0001
        # C-FIND-RSP only has a Data Set when the Status is pending (0xFF00) or
        #   Pending Warning (0xFF01)
        elif cls_type_name == 'C_FIND_RSP' and \
                        self.command_set.Status in [0xFF00, 0xFF01]:
            self.data_set = primitive.Identifier
            self.command_set.CommandDataSetType = 0x0001
        elif cls_type_name == 'N_EVENT_REPORT_RQ':
            self.data_set = primitive.EventInformation
            self.command_set.CommandDataSetType = 0x0001
        elif cls_type_name == 'N_EVENT_REPORT_RSP':
            self.data_set = primitive.EventReply
            self.command_set.CommandDataSetType = 0x0001
        elif cls_type_name in ['N_GET_RSP', 'N_SET_RSP',
                               'N_CREATE_RQ', 'N_CREATE_RSP']:
            self.data_set = primitive.AttributeList
            self.command_set.CommandDataSetType = 0x0001
        elif cls_type_name == 'N_SET_RQ':
            self.data_set = primitive.ModificationList
            self.command_set.CommandDataSetType = 0x0001
        elif cls_type_name == 'N_ACTION_RQ':
            self.data_set = primitive.ActionInformation
            self.command_set.CommandDataSetType = 0x0001
        elif cls_type_name == 'N_ACTION_RSP':
            self.data_set = primitive.ActionReply
            self.command_set.CommandDataSetType = 0x0001

        # The following message types don't have a dataset
        # 'C_ECHO_RQ', 'C_ECHO_RSP', 'N_DELETE_RQ', 'C_STORE_RSP',
        # 'C_CANCEL_RQ', 'N_DELETE_RSP', 'C_FIND_RSP'

        # Set the Command Set length
        self._set_command_group_length()

    def message_to_primitive(self):
        """Convert the DIMSEMessage class to a DIMSEServiceProvider subclass.

        Convert `self` to a DIMSE service parameters primitive object.

        Returns
        -------
        primitive : pynetdicom3.dimse_primitives DIMSE service primitive
            The primitive generated from the current DIMSE Message
        """
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
        #elif 'C_CANCEL' in cls_type_name:
        #    primitive = C_FIND()

        ## Command Set
        # For each parameter in the primitive, set the appropriate value
        #   from the Message's Command Set
        for elem in self.command_set:
            if hasattr(primitive, elem.keyword):
                setattr(primitive, elem.keyword,
                        self.command_set.__getattr__(elem.keyword))

        ## Datasets
        if cls_type_name == 'C_STORE_RQ':
            setattr(primitive, 'DataSet', self.data_set)
        elif cls_type_name in ['C_FIND_RQ', 'C_FIND_RSP', 'C_GET_RQ',
                                'C_GET_RSP', 'C_MOVE_RQ', 'C_MOVE_RSP']:
            setattr(primitive, 'Identifier', self.data_set)
        elif cls_type_name == 'N_EVENT_REPORT_RQ':
            setattr(primitive, 'EventInformation', self.data_set)
        elif cls_type_name == 'N_EVENT_REPORT_RSP':
            setattr(primitive, 'EventReply', self.data_set)
        elif cls_type_name in ['N_GET_RSP', 'N_SET_RSP',
                               'N_CREATE_RQ', 'N_CREATE_RSP']:
            setattr(primitive, 'AttributeList', self.data_set)
        elif cls_type_name == 'N_SET_RQ':
            setattr(primitive, 'ModificationList', self.data_set)
        elif cls_type_name == 'N_ACTION_RQ':
            setattr(primitive, 'ActionInformation', self.data_set)
        elif cls_type_name == 'N_ACTION_RSP':
            setattr(primitive, 'ActionReply', self.data_set)

        return primitive


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

    # Create new subclass of DIMSE Message using the supplied name
    #   but replace hyphens with underscores
    cls = type(message_name.replace('-', '_'),
               (DIMSEMessage, ),
               {"__init__": __init__})

    # Create a new Dataset object for the command_set attributes
    ds = Dataset()
    for elem_tag in COMMAND_SET_ELEM[message_name]:
        tag = Tag(elem_tag)
        vr = dcm_dict[elem_tag][0]

        # If the required command set elements are expanded this will need
        #   to be checked to ensure it functions OK
        try:
            ds.add_new(tag, vr, None)
        except TypeError:
            ds.add_new(tag, vr, '')

    # Add the Command Set dataset to the class
    cls.command_set = ds

    # Add the class to the module
    globals()[cls.__name__] = cls

    return cls

for msg_type in COMMAND_SET_ELEM:
    _build_message_classes(msg_type)

# Values from PS3.5
MESSAGE_TYPE_CLASS = {0x0001 : C_STORE_RQ, 0x8001 : C_STORE_RSP,
                      0x0020 : C_FIND_RQ, 0x8020 : C_FIND_RSP,
                      0x0FFF : C_CANCEL_RQ,
                      0x0010 : C_GET_RQ, 0x8010 : C_GET_RSP,
                      0x0021 : C_MOVE_RQ, 0x8021 : C_MOVE_RSP,
                      0x0030 : C_ECHO_RQ, 0x8030 : C_ECHO_RSP,
                      0x0100 : N_EVENT_REPORT_RQ, 0x8100 : N_EVENT_REPORT_RSP,
                      0x0110 : N_GET_RQ, 0x8110 : N_GET_RSP,
                      0x0120 : N_SET_RQ, 0x8120 : N_SET_RSP,
                      0x0130 : N_ACTION_RQ, 0x8130 : N_ACTION_RSP,
                      0x0140 : N_CREATE_RQ, 0x8140 : N_CREATE_RSP,
                      0x0150 : N_DELETE_RQ, 0x8150 : N_DELETE_RSP}
