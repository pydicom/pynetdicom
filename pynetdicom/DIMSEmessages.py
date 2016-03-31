
from io import BytesIO
import itertools
import logging
from struct import pack, unpack

from pydicom.dataset import Dataset
from pydicom.tag import Tag
from pydicom._dicom_dict import DicomDictionary as dcm_dict
from pydicom.uid import ImplicitVRLittleEndian

from pynetdicom.DIMSEparameters import *
from pynetdicom.dsutils import encode_element, encode, decode
from pynetdicom.DULparameters import *
from pynetdicom.utils import fragment

logger = logging.getLogger('pynetdicom.dimse')

message_type = {0x0001 : 'C-STORE-RQ',        0x8001 : 'C-STORE-RSP',
                0x0020 : 'C-FIND-RQ',         0x8020 : 'C-FIND-RSP',
                0x0010 : 'C-GET-RQ',          0x8010 : 'C-GET-RSP',
                0x0021 : 'C-MOVE-RQ',         0x8021 : 'C-MOVE-RSP',
                0x0030 : 'C-ECHO-RQ',         0x8030 : 'C-ECHO-RSP',
                0x0FFF : 'C-CANCEL-RQ',
                0x0100 : 'N-EVENT-REPORT-RQ', 0x8100 : 'N-EVENT-REPORT-RSP',
                0x0110 : 'N-GET-RQ',          0x8110 : 'N-GET-RSP',
                0x0120 : 'N-SET-RQ',          0x8120 : 'N-SET-RSP',
                0x0130 : 'N-ACTION-RQ',       0x8130 : 'N-ACTION-RSP',
                0x0140 : 'N-CREATE-RQ',       0x8140 : 'N-CREATE-RSP',
                0x0150 : 'N-DELETE-RQ',       0x8150 : 'N-DELETE-RSP'}

# PS3.7 Section 9.3
command_set_elem = {'C-ECHO-RQ'   : [0x00000000,  # CommandGroupLength
                                     0x00000002,  # AffectedSOPClassUID
                                     0x00000100,  # CommandField
                                     0x00000110,  # MessageID
                                     0x00000800], # CommandDataSetType
                    'C-ECHO-RSP'  : [0x00000000, 0x00000002, 0x00000100,
                                     0x00000120,  # MessageIDBeingRespondedTo
                                     0x00000800,
                                     0x00000900], # Status
                    'C-STORE-RQ'  : [0x00000000, 0x00000002, 0x00000100, 0x00000110,
                                     0x00000700,  # Priority
                                     0x00000800,
                                     0x00001000,  # AffectedSOPInstanceUID
                                     0x00001030,  # MoveOriginatorApplicationEntityTitle
                                     0x00001031], # MoveOriginatorMessageID
                    'C-STORE-RSP' : [0x00000000, 0x00000002, 0x00000100, 0x00000120, 0x00000800, 0x00000900, 0x00001000],
                    'C-FIND-RQ'   : [0x00000000, 0x00000002, 0x00000100, 0x00000110, 0x00000700, 0x00000800],
                    'C-FIND-RSP'  : [0x00000000, 0x00000002, 0x00000100, 0x00000120, 0x00000800, 0x00000900],
                    'C-CANCEL-RQ' : [0x00000000, 0x00000100, 0x00000120, 0x00000800],
                    'C-GET-RQ'    : [0x00000000, 0x00000002, 0x00000100, 0x00000110, 0x00000700, 0x00000800],
                    'C-GET-RSP'   : [0x00000000, 0x00000002, 0x00000100, 0x00000120, 0x00000800, 0x00000900,
                                     0x00001020,  # NumberOfRemainingSuboperations
                                     0x00001021,  # NumberOfCompletedSuboperations
                                     0x00001022,  # NumberOfFailedSuboperations
                                     0x00001023], # NumberOfWarningSuboperations
                    'C-MOVE-RQ'   : [0x00000000, 0x00000002, 0x00000100, 0x00000110, 0x00000700, 0x00000800, 0x00000600],
                    'C-MOVE-RSP'  : [0x00000000, 0x00000002, 0x00000100, 0x00000120, 0x00000800, 0x00000900, 0x00001020, 0x00001021, 0x00001022, 0x00001023],
                    'N-EVENT-REPORT-RQ'  : [0x00000000, 0x00000002, 0x00000100, 0x00000110, 0x00000800, 0x00001000,
                                            0x00001002], # EventTypeID
                    'N-EVENT-REPORT-RSP' : [0x00000000, 0x00000002, 0x00000100, 0x00000120, 0x00000800, 0x00000900, 0x00001000, 0x00001002],
                    'N-GET-RQ'     : [0x00000000, 0x00000003, 0x00000100, 0x00000110, 0x00000800,
                                      0x00001001,  # RequestedSOPInstanceUID
                                      0x00001005], # AttributeIdentifierList
                    'N-GET-RSP'    : [0x00000000, 0x00000002, 0x00000100, 0x00000120, 0x00000800, 0x00000900, 0x00001000],
                    'N-SET-RQ'     : [0x00000000, 0x00000003, 0x00000100, 0x00000110, 0x00000800, 0x00001001],
                    'N-SET-RSP'    : [0x00000000, 0x00000002, 0x00000100, 0x00000120, 0x00000800, 0x00000900, 0x00001000],
                    'N-ACTION-RQ'  : [0x00000000, 0x00000003, 0x00000100, 0x00000110, 0x00000800, 0x00001001,
                                      0x00001008], # ActionTypeID
                    'N-ACTION-RSP' : [0x00000000, 0x00000002, 0x00000100, 0x00000120, 0x00000800, 0x00000900, 0x00001000, 0x00001008],
                    'N-CREATE-RQ'  : [0x00000000, 0x00000002, 0x00000100, 0x00000110, 0x00000800, 0x00001000],
                    'N-CREATE-RSP' : [0x00000000, 0x00000002, 0x00000100, 0x00000120, 0x00000800, 0x00000900, 0x00001000],
                    'N-DELETE-RQ'  : [0x00000000, 0x00000003, 0x00000100, 0x00000110, 0x00000800, 0x00001001],
                    'N-DELETE-RSP' : [0x00000000, 0x00000002, 0x00000100, 0x00000120, 0x00000800, 0x00000900, 0x00001000]}


class DIMSEMessage(object):
    """
    Represents a DIMSE *Message*.
    
    Information is communicated across the DICOM network interface in a DICOM
    *Message*. A *Message* is composed of a Command Set followed by a conditional
    Data Set. The Command Set is used to indicate the operations/notifications
    to be performed on or with the Data Set. (PS3.7 6.2-3)

    Command Set
    -----------
    A Command Set is constructed of Command Elements. Command Elements contain
    the encoded values for each field of the Command Set per the semantics
    specified in the DIMSE protocol (PS3.7 9.2 and 10.2). Each Command Element
    is composed of an explicit Tag, Value Length and a Value field. The encoding
    of the Command Set shall be *Little Endian Implicit VR*.

                        primitive_to_message         Encode
    .----------------------.  ----->   .----------.  ----->  .---------------.
    |   DIMSE parameters   |           |   DIMSE  |          |     P-DATA    |
    |       primitive      |           |  message |          |   primitive   |
    .----------------------.  <-----   .----------.  <-----  .---------------.
                        message_to_primitive         Decode

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
        # self.command_set is added by __build_message_classes()
        self.encoded_command_set = BytesIO()
        self.data_set = BytesIO()

    def Encode(self, context_id, max_pdu):
        """
        Encode the DIMSE Message as one or more P-DATA service primitives
        
        PS3.7 6.3.1
        The encoding of the Command Set shall be Little Endian Implicit VR
        
        Parameters
        ----------
        context_id - int
            The ID of the presentation context agreed to under which we are
            sending the data
        max_pdu_length - int
            The maximum PDU length in bytes
            
        Returns
        -------
        p_data_list - list of pynetdicom.DULparameters.P_DATA_ServiceParameters
            A list of one or more P-DATA service primitives
        """
        self.ID = context_id
        p_data_list = []
        
        # The Command Set is always Little Endian Implicit VR (PS3.7 6.3.1)
        #   encode(dataset, is_implicit_VR, is_little_endian)
        encoded_command_set = encode(self.command_set, True, True)

        ## COMMAND SET
        # Split the command set into framents with maximum size max_pdu
        pdvs = fragment(max_pdu, encoded_command_set)
        
        # First to (n - 1)th command data fragment - b XXXXXX01
        for ii in pdvs[:-1]:
            pdata = P_DATA_ServiceParameters()
            pdata.PresentationDataValueList = [[self.ID, pack('b', 1) + ii]]
            
            p_data_list.append(pdata)
        
        # Nth command data fragment - b XXXXXX11
        pdata = P_DATA_ServiceParameters()
        pdata.PresentationDataValueList = [[self.ID, pack('b', 3) + pdvs[-1]]]
       
        p_data_list.append(pdata)


        ## DATASET (if available)
        # Split out dataset up into fragment with maximum size of max_pdu
        #   Check that we have a Data Set and its not empty
        if 'data_set' in self.__dict__ and self.data_set.getvalue() != b'':
            # Technically these are APDUs, not PDVs
            pdvs = fragment(max_pdu, self.data_set)

            # First to (n - 1)th dataset fragment - b XXXXXX00
            for ii in pdvs[:-1]:
                pdata = P_DATA_ServiceParameters()
                pdata.PresentationDataValueList = [[self.ID, pack('b', 0) + ii]]
                p_data_list.append(pdata)
            
            # Nth dataset fragment - b XXXXXX10
            pdata = P_DATA_ServiceParameters()
            pdata.PresentationDataValueList = \
                                        [[self.ID, pack('b', 2) + pdvs[-1]]]
            
            p_data_list.append(pdata)

        return p_data_list

    def Decode(self, pdata):
        """Constructs itself receiving a series of P-DATA primitives.
        
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
        pdata : pynetdicom.DULparameters.P_DATA_ServiceParameters
            The P-DATA service primitive to be decoded into a DIMSE message
        
        Returns
        -------
        bool
            True when complete, False otherwise.
        """
        # Make sure this is a P-DATA primitive
        if pdata.__class__ != P_DATA_ServiceParameters or pdata is None:
            return False
        
        for pdv_item in pdata.PresentationDataValueList:
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
            #   (xxxxxx01 and xxxxxx11)
            if control_header_byte & 1:
                # The command set may be spread out over a number
                #   of fragments and we need to remember the elements
                #   from previous fragments, hence the class attribute
                self.encoded_command_set.write(pdv_item[1][1:])

                # The P-DATA fragment is the last one (xxxxxx11)
                if control_header_byte & 2:
                    # Command Set is always encoded Implicit VR Little Endian
                    #   decode(dataset, is_implicit_VR, is_little_endian)
                    self.command_set = decode(self.encoded_command_set, 
                                              True, True)

                    # Determine which DIMSE Message class to use
                    self.__class__ = MessageType[self.command_set.CommandField]
                    
                    # (0000, 0800) CommandDataSetType US 1
                    #   if value is 0101H no dataset present
                    #   otherwise a dataset is included in the Message
                    if self.command_set.CommandDataSetType == 0x0101:
                        return True

            ## DATA SET
            # P-DATA fragment contains Message Dataset information 
            #   (xxxxxx00 and xxxxxx10)
            else:
                self.data_set.write(pdv_item[1][1:])

                # The P-DATA fragment is the last one (xxxxxx10)
                if control_header_byte & 2 != 0:
                    return True

        return False

    def set_command_group_length(self):
        """
        Once the self.command_set Dataset has been completed this should be
        called to set the CommandGroupLength element value correctly
        """
        length = 0
        
        # Remove CommandGroupLength from dataset to prevent it from messing
        #   with our length calculation.
        # We have to use the tag value due to a bug in pydicom
        del self.command_set[0x00000000]
        for ii in list(self.command_set.values()):
            #   encode_element(elem, is_implicit_VR, is_little_endian)
            length += len(encode_element(ii, True, True))
        
        # Add the CommandGroupLength element back to the dataset with the
        #   correct value
        self.command_set.CommandGroupLength = length

    def primitive_to_message(self, primitive):
        """
        Convert a DIMSE service parameters primitive to the current DIMSE 
        message object
        
        Parameters
        ----------
        primitive : pynetdicom.DIMSEparameters DIMSE service parameter
            The primitive to convert to the current DIMSE Message object
        """
        ## Command Set
        for elem in self.command_set:
            # Use the short version of the element names as these should
            #   match the parameter names in the primitive
            elem_name = elem.name.replace(' ', '')
            if elem_name in primitive.__dict__.keys():
                # If value hasn't been set for a parameter then delete
                #   the corresponding element
                if primitive.__dict__[elem_name] is not None:
                    elem.value = primitive.__dict__[elem_name]
                else:
                    del self.command_set[elem.tag]
        
        # Theres a one-to-one relationship in the message_type dict, so invert
        #   it for convenience
        rev_type = {}
        for value in message_type.keys():
            rev_type[message_type[value]]  = value
        
        cls_type_name = self.__class__.__name__.replace('_', '-')
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
        # C-FIND-RSP only has a Data Set when the Status is pending (0x0001)
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
        elif cls_type_name in ['C_ECHO_RQ', 'C_ECHO_RSP', 'N_DELETE_RQ', 
                                'C_STORE_RSP', 'C_CANCEL_RQ',
                                'N_DELETE_RSP']:
            pass
        else:
            logger.error("DIMSE - Can't convert primitive to message for "
                "unknown message type '%s'" %cls_type_name)
    
        # Set the Command Set length
        self.set_command_group_length()
        
    def message_to_primitive(self):
        """
        Convert the current DIMSE Message object to a DIMSE service parameters 
        primitive
        
        Returns
        -------
        primitive : pynetdicom.DIMSEparameters DIMSE service primitive
            The primitive generated from the current DIMSE Message
        """
        cls_type_name = self.__class__.__name__
        if 'C_ECHO' in cls_type_name:
            primitive = C_ECHO_ServiceParameters()
        elif 'C_STORE' in cls_type_name:
            primitive = C_STORE_ServiceParameters()
        elif 'C_FIND' in cls_type_name:
            primitive = C_FIND_ServiceParameters()
        elif 'C_GET' in cls_type_name:
            primitive = C_GET_ServiceParameters()
        elif 'C_MOVE' in cls_type_name:
            primitive = C_MOVE_ServiceParameters()
        elif 'N_EVENT' in cls_type_name:
            primitive = N_EVENT_REPORT_ServiceParameters()
        elif 'N_GET' in cls_type_name:
            primitive = N_GET_ServiceParameters()
        elif 'N_SET' in cls_type_name:
            primitive = N_SET_ServiceParameters()
        elif 'N_ACTION' in cls_type_name:
            primitive = N_ACTION_ServiceParameters()
        elif 'N_CREATE' in cls_type_name:
            primitive = N_CREATE_ServiceParameters()
        elif 'N_DELETE' in cls_type_name:
            primitive = N_DELETE_ServiceParameters()
        
        ## Command Set
        # For each parameter in the primitive, set the appropriate value
        #   from the Message's Command Set
        for param in primitive.__dict__.keys():
            if param in self.command_set:
                try:
                    primitive.__dict__[param] = self.command_set.__getattr__(param)
                except:
                    logger.error('DIMSE failed to convert message to primitive')

        ## Datasets
        if cls_type_name == 'C_STORE_RQ':
            primitive.__dict__['DataSet'] = self.data_set
        elif cls_type_name in ['C_FIND_RQ', 'C_FIND_RSP',
                                'C_GET_RQ',  'C_GET_RSP',
                                'C_MOVE_RQ', 'C_MOVE_RSP']:
            primitive.__dict__['Identifier'] = self.data_set
        elif cls_type_name == 'N_EVENT_REPORT_RQ':
            primitive.__dict__['EventInformation'] = self.data_set
        elif cls_type_name == 'N_EVENT_REPORT_RSP':
            primitive.__dict__['EventReply'] = self.data_set
        elif cls_type_name in ['N_GET_RSP',   'N_SET_RSP',
                                'N_CREATE_RQ', 'N_CREATE_RSP']:
            primitive.__dict__['AttributeList'] = self.data_set
        elif cls_type_name == 'N_SET_RQ':
            primitive.__dict__['ModificationList'] = self.data_set
        elif cls_type_name == 'N_ACTION_RQ':
            primitive.__dict__['ActionInformation'] = self.data_set
        elif cls_type_name == 'N_ACTION_RSP':
            primitive.__dict__['ActionReply'] = self.data_set

        return primitive


def __build_message_classes(message_name):
    """
    Create a new subclass instance of DIMSEMessage for the given DIMSE
    `message_name`.
    
    Parameters
    ----------
    message_name : str
        The name/type of message class to construct
    """
    def __init__(self):
        DIMSEMessage.__init__(self)

    # Create new subclass of DIMSE Message using the supplied name
    #   but replace hyphens with underscores
    cls = type(message_name.replace('-', '_'), 
                (DIMSEMessage,), 
                {"__init__": __init__})

    # Create a new Dataset object for the command_set attributes
    d = Dataset()
    for elem_tag in command_set_elem[message_name]:
        tag = Tag(elem_tag)
        vr = dcm_dict[elem_tag][0]

        # If the required command set elements are expanded this will need
        #   to be checked to ensure it functions OK
        try:
            d.add_new(tag, vr, None)
        except:
            d.add_new(tag, vr, '')

    cls.command_set = d

    globals()[cls.__name__] = cls
    
    return cls

for msg_type in command_set_elem.keys():
    __build_message_classes(msg_type)

MessageType = {0x0001 : C_STORE_RQ, 0x8001 : C_STORE_RSP,
               0x0020 : C_FIND_RQ,  0x8020 : C_FIND_RSP,
               0x0FFF : C_CANCEL_RQ, 
               0x0010 : C_GET_RQ,  0x8010 : C_GET_RSP,
               0x0021 : C_MOVE_RQ, 0x8021 : C_MOVE_RSP,
               0x0030 : C_ECHO_RQ, 0x8030 : C_ECHO_RSP,
               0x0100 : N_EVENT_REPORT_RQ, 0x8100 : N_EVENT_REPORT_RSP,
               0x0110 : N_GET_RQ, 0x8110 : N_GET_RSP,
               0x0120 : N_SET_RQ, 0x8120 : N_SET_RSP,
               0x0130 : N_ACTION_RQ, 0x8130 : N_ACTION_RSP,
               0x0140 : N_CREATE_RQ, 0x8140 : N_CREATE_RSP,
               0x0150 : N_DELETE_RQ, 0x8150 : N_DELETE_RSP}
