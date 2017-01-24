"""The PDU item and sub-item classes.

ApplicationContextItem
PresentationContextItemRQ
PresentationContextItemAC
    AbstractSyntaxSubItem
    TransferSyntaxSubItem
PresentationDataValueItem
UserInformationItem
    MaximumLengthSubItem
    ImplementationClassUIDSubItem
    ImplementationVersionNameSubItem
    SCP_SCU_RoleSelectionSubItem
    AsynchronousOperationsWindowSubItem
    UserIdentitySubItemRQ
    UserIdentitySubItemAC
    SOPClassExtendedNegotiationSubItem
    SOPClassCommonExtendedNegotiationSubItem
"""
from io import BytesIO
import logging
from struct import pack, unpack, calcsize

from pydicom.uid import UID

from pynetdicom3.utils import wrap_list, PresentationContext, validate_ae_title


LOGGER = logging.getLogger('pynetdicom3.pdu_items')


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

    Used in A_ASSOCIATE_RQ_PDU - Variable items
    Used in A_ASSOCIATE_AC_PDU - Variable items

    Attributes
    ----------
    application_context_name : pydicom.uid.UID
        The UID for the Application Context Name
    length : int
        The length of the encoded Item in bytes
    """
    def __init__(self):
        self.item_type = 0x10
        self.item_length = None
        self.application_context_name = ''

        self.formats = ['B', 'B', 'H', 's']
        self.parameters = [self.item_type,
                           0x00, # Reserved
                           self.item_length,
                           self.application_context_name]

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
        bytestring : bytes
            The encoded Item used in the parent PDU
        """
        formats = '> B B H'
        parameters = [self.item_type,
                      0x00, # Reserved
                      self.item_length]

        bytestring = bytes()
        bytestring += pack(formats, *parameters)
        bytestring += bytes(self.application_context_name.title(), 'utf-8')

        return bytestring

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
         self.item_length) = unpack('> B B H', bytestream.read(4))

        self.application_context_name = bytestream.read(self.item_length)

        self._update_parameters()

    def _update_parameters(self):
        """Update the PDU parameters."""
        self.parameters = [self.item_type,
                           0x00, # Reserved
                           self.item_length,
                           self.application_context_name]

    def get_length(self):
        """Get the PDU length."""
        self._update_parameters()
        return 4 + self.item_length

    def __str__(self):
        s = '{0!s} ({1!s})\n'.format(self.application_context_name,
                          self.application_context_name.title())
        return s

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
            raise TypeError('Application Context Name must be a UID, ' \
                            'str or bytes')

        self._application_context_name = value

        # Update the item_length parameter to account fo the new value
        self.item_length = len(self.application_context_name)

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

    Used in A_ASSOCIATE_RQ_PDU - Variable items

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
        self.item_type = 0x20
        self.item_length = None
        self.presentation_context_id = None

        # AbstractTransferSyntaxSubItems is a list
        # containing the following elements:
        #   One AbstractSyntaxtSubItem
        #   One or more TransferSyntaxSubItem
        self.abstract_transfer_syntax_sub_items = []

        # Non-standard parameters
        #   Used for tracking SCP/SCU Role Negotiation
        # Consider shifting to properties?
        self.SCP = None
        self.SCU = None

        self.formats = ['B', 'B', 'H', 'B', 'B', 'B', 'B']
        self.parameters = [self.item_type,
                           0x00, # Reserved
                           self.item_length,
                           self.presentation_context_id,
                           0x00, # Reserved
                           0x00, # Reserved
                           0x00,
                           self.abstract_transfer_syntax_sub_items] # Reserved

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
        bytestring : bytes
            The encoded Item used in the parent PDU
        """
        formats = '> B B H B B B B'
        parameters = [self.item_type,
                      0x00, # Reserved
                      self.item_length,
                      self.presentation_context_id,
                      0x00, # Reserved
                      0x00, # Reserved
                      0x00] # Reserved

        bytestring = bytes()
        bytestring += pack(formats, *parameters)

        for ii in self.abstract_transfer_syntax_sub_items:
            bytestring += ii.Encode()

        return bytestring

    def Decode(self, bytestream):
        """
        Decode the parameter values for the Item from the parent PDU's byte
        stream

        Parameters
        ----------
        bytestream : io.BytesIO
            The byte stream to decode
        """
        # Decode the Item parameters up to the Abstract/Transfer Syntax
        (self.item_type,
         _,
         self.item_length,
         self.presentation_context_id,
         _,
         _,
         _) = unpack('> B B H B B B B', bytestream.read(8))

        # Decode the Abstract/Transfer Syntax Sub-items
        item = self._next_item(bytestream)
        while isinstance(item, AbstractSyntaxSubItem) or \
                            isinstance(item, TransferSyntaxSubItem):
            item.Decode(bytestream)
            self.abstract_transfer_syntax_sub_items.append(item)

            item = self._next_item(bytestream)

        self._update_parameters()

    def _update_parameters(self):
        """Update the PDU parameters."""
        self.parameters = [self.item_type,
                           0x00,
                           self.item_length,
                           self.presentation_context_id,
                           0x00,
                           0x00,
                           0x00,
                           self.abstract_transfer_syntax_sub_items]

    def _update_item_length(self):
        """Update the PDU length."""
        self.item_length = 4

        for ii in self.abstract_transfer_syntax_sub_items:
            self.item_length += ii.length

    def get_length(self):
        """Get the PDU length."""
        self._update_item_length()
        self._update_parameters()
        return 4 + self.item_length

    def __str__(self):
        s = "Presentation Context (RQ) Item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d} bytes\n".format(self.length)
        s += "  Context ID: {0:d}\n".format(self.ID)

        for ii in self.abstract_transfer_syntax_sub_items:
            item_str = '{0!s}'.format(ii)
            item_str_list = item_str.split('\n')
            s += '  + {0!s}\n'.format(item_str_list[0])
            for jj in item_str_list[1:-1]:
                s += '    {0!s}\n'.format(jj)

        return s

    @property
    def ID(self):
        """
        See PS3.8 9.3.2.2

        Returns
        -------
        int
            Odd number between 1 and 255 (inclusive)
        """
        return self.presentation_context_id

    @property
    def abstract_syntax(self):
        """Get the abstract syntax."""
        for ii in self.abstract_transfer_syntax_sub_items:
            if isinstance(ii, AbstractSyntaxSubItem):
                return ii.abstract_syntax_name

    @property
    def transfer_syntax(self):
        """Get the transfer syntaxes."""
        syntaxes = []
        for ii in self.abstract_transfer_syntax_sub_items:
            if isinstance(ii, TransferSyntaxSubItem):
                syntaxes.append(ii.transfer_syntax_name)

        return syntaxes

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

    Used in A_ASSOCIATE_AC_PDU - Variable items

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
        self.item_type = 0x21
        self.item_length = None
        self.presentation_context_id = None
        self.result_reason = None
        self.transfer_syntax_sub_item = None

        # Used for tracking SCP/SCU Role Negotiation
        self.SCP = None
        self.SCU = None

        self.formats = ['B', 'B', 'H', 'B', 'B', 'B', 'B']
        self.parameters = [self.item_type,
                           0x00, # Reserved
                           self.item_length,
                           self.presentation_context_id,
                           0x00, # Reserved
                           self.result_reason,
                           0x00, # Reserved
                           self.transfer_syntax_sub_item]

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
        bytestring : bytes
            The encoded Item used in the parent PDU
        """
        formats = '> B B H B B B B'
        parameters = [self.item_type,
                      0x00, # Reserved
                      self.item_length,
                      self.presentation_context_id,
                      0x00, # Reserved
                      self.result_reason, # Reserved
                      0x00] # Reserved

        bytestring = bytes()
        bytestring += pack(formats, *parameters)
        bytestring += self.transfer_syntax_sub_item.Encode()

        return bytestring

    def Decode(self, bytestream):
        """
        Decode the parameter values for the Item from the parent PDU's byte
        stream

        Parameters
        ----------
        bytestream : io.BytesIO
            The byte stream to decode
        """
        # Decode the Item parameters up to the Transfer Syntax
        (self.item_type,
         _,
         self.item_length,
         self.presentation_context_id,
         _,
         self.result_reason,
         _) = unpack('> B B H B B B B', bytestream.read(8))

        # Decode the Transfer Syntax
        self.transfer_syntax_sub_item = TransferSyntaxSubItem()
        self.transfer_syntax_sub_item.Decode(bytestream)

        self._update_parameters()

    def _update_parameters(self):
        """Update the parameters"""
        self.parameters = [self.item_type,
                           0x00, # Reserved
                           self.item_length,
                           self.presentation_context_id,
                           0x00, # Reserved
                           self.result_reason,
                           0x00, # Reserved
                           self.transfer_syntax_sub_item]

    def get_length(self):
        """Get the PDU length."""
        self.item_length = 4 + self.transfer_syntax_sub_item.length
        self._update_parameters()

        return 4 + self.item_length

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
    def ID(self):
        """Get the presentation context ID."""
        return self.presentation_context_id

    @property
    def result(self):
        """Get the Result parameter."""
        return self.result_reason

    @property
    def result_str(self):
        """Get a string describing the result."""
        result_options = {0 : 'Accepted',
                          1 : 'User Rejection',
                          2 : 'Provider Rejection',
                          3 : 'Abstract Syntax Not Supported',
                          4 : 'Transfer Syntax Not Supported'}
        return result_options[self.result]

    @property
    def transfer_syntax(self):
        """Get the transfer syntax."""
        return self.transfer_syntax_sub_item.transfer_syntax_name

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

    Used in A_ASSOCIATE_RQ_PDU - Variable items - Presentation Context items -
    Abstract/Transfer Syntax sub-items

    Attributes
    ----------
    abstract_syntax : pydicom.uid.UID
        The abstract syntax
    length : int
        The length of the encoded Item in bytes
    """
    def __init__(self):
        self.item_type = 0x30
        self.item_length = None
        self.abstract_syntax_name = None

        self.formats = ['B', 'B', 'H', 's']
        self.parameters = [self.item_type,
                           0x00,
                           self.item_length,
                           self.abstract_syntax_name]

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
        bytestring : bytes
            The encoded Item used in the parent PDU
        """
        formats = '> B B H'
        parameters = [self.item_type,
                      0x00, # Reserved
                      self.item_length]

        bytestring = bytes()
        bytestring += pack(formats, *parameters)
        bytestring += bytes(self.abstract_syntax_name.title(), 'utf-8')

        return bytestring

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
         self.item_length) = unpack('> B B H', bytestream.read(4))

        self.abstract_syntax_name = bytestream.read(self.item_length)

        self._update_parameters()

    def _update_parameters(self):
        """Update the PDU parameters."""
        self.parameters = [self.item_type,
                           0x00,
                           self.item_length,
                           self.abstract_syntax_name]

    def get_length(self):
        """Get the PDU length."""
        self.item_length = len(self.abstract_syntax_name)
        self._update_parameters()

        return 4 + self.item_length

    def __str__(self):
        s = "Abstract Syntax Sub-item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        s += '  Syntax name: ={0!s}\n'.format(self.abstract_syntax)

        return s

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
            raise TypeError('Abstract Syntax must be a pydicom.uid.UID, ' \
                            'str or bytes')

        self._abstract_syntax_name = value

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

    Used in A_ASSOCIATE_RQ_PDU - Variable items - Presentation Context items -
    Abstract/Transfer Syntax sub-items
    Used in A_ASSOCIATE_AC_PDU - Variable items - Presentation Context items -
    Transfer Syntax sub-item

    Attributes
    ----------
    length : int
        The length of the encoded Item in bytes
    transfer_syntax : pydicom.uid.UID
        The transfer syntax
    """
    def __init__(self):
        self.item_type = 0x40
        self.item_length = None
        self.transfer_syntax_name = None

        self.formats = ['B', 'B', 'H', 's']
        self.parameters = [self.item_type,
                           0x00, # Reserved
                           self.item_length,
                           self.transfer_syntax_name]

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
        bytestring : bytes
            The encoded Item used in the parent PDU
        """
        formats = '> B B H'
        parameters = [self.item_type,
                      0x00, # Reserved
                      self.item_length]

        bytestring = bytes()
        bytestring += pack(formats, *parameters)
        bytestring += bytes(self.transfer_syntax_name.title(), 'utf-8')

        return bytestring

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
         self.item_length) = unpack('> B B H', bytestream.read(4))

        self.transfer_syntax_name = bytestream.read(self.item_length)

        self._update_parameters()

    def _update_parameters(self):
        """Update the parameters."""
        self.parameters = [self.item_type,
                           0x00,
                           self.item_length,
                           self.transfer_syntax_name]

    def get_length(self):
        """Get the item length."""
        self.item_length = len(self.transfer_syntax_name)
        self._update_parameters()

        return 4 + self.item_length

    def __str__(self):
        s = "Transfer syntax sub item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        s += '  Transfer syntax name: ={0!s}\n'.format(self.transfer_syntax_name)

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
            raise TypeError('Transfer syntax must be a pydicom.uid.UID, ' \
                            'bytes or str')

        self._transfer_syntax_name = value

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

    Used in P_DATA_TF_PDU - Presentation data value items

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
        self.item_length = None
        self.presentation_context_id = None
        self.presentation_data_value = None

        self.formats = ['I', 'B', 's']
        self.parameters = [self.item_length,
                           self.presentation_context_id,
                           self.presentation_data_value]

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
        bytestring : bytes
            The encoded Item used in the parent PDU
        """
        formats = '> I B'
        parameters = [self.item_length,
                      self.presentation_context_id]

        bytestring = bytes()
        bytestring += pack(formats, *parameters)
        bytestring += self.presentation_data_value

        return bytestring

    def Decode(self, bytestream):
        """
        Decode the parameter values for the Item from the parent PDU's byte
        stream

        Parameters
        ----------
        bytestream : io.BytesIO
            The byte stream to decode
        """
        (self.item_length,
         self.presentation_context_id) = unpack('> I B', bytestream.read(5))

        self.presentation_data_value = \
            bytestream.read(int(self.item_length) - 1)

        self._update_parameters()

    def _update_parameters(self):
        """Update the parameters."""
        self.parameters = [self.item_length,
                           self.presentation_context_id,
                           self.presentation_data_value]

    def get_length(self):
        """Get the item length."""
        self.item_length = 1 + len(self.presentation_data_value)
        self._update_parameters()

        return 4 + self.item_length

    def __str__(self):
        s = "Presentation Value Data Item\n"
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        s += "  Context ID: {0:d}\n".format(self.presentation_context_id)
        s += "  Data value: 0x{0!s} ...\n".format(' 0x'.join(
            format(x, '02x') for x in self.presentation_data_value[:10]))

        return s

    @property
    def data(self):
        """Get the presentation data value."""
        return self.presentation_data_value

    @property
    def ID(self):
        """Get the presentation context ID."""
        return self.presentation_context_id

    @property
    def message_control_header_byte(self):
        """Get the message control header byte."""
        return "{:08b}".format(self.presentation_data_value[0])

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

    Used in A_ASSOCIATE_RQ_PDU - Variable items
    Used in A_ASSOCIATE_AC_PDU - Variable items

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
        self.item_type = 0x50
        self.item_length = None
        self.user_data = []

        self.formats = ['B', 'B', 'H']
        self.parameters = [self.item_type,
                           0x00, # Reserved
                           self.item_length,
                           self.user_data]

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
        bytestring : bytes
            The encoded Item used in the parent PDU
        """
        formats = '> B B H'
        parameters = [self.item_type,
                      0x00, # Reserved
                      self.item_length]

        bytestring = bytes()
        bytestring += pack(formats, *parameters)

        for ii in self.user_data:
            bytestring += ii.Encode()

        return bytestring

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
         self.item_length) = unpack('> B B H', bytestream.read(4))

        # Decode the User Data sub-items section
        item = self._next_item(bytestream)
        while item is not None:
            item.Decode(bytestream)
            self.user_data.append(item)

            item = self._next_item(bytestream)

        self._update_parameters()

    def _update_parameters(self):
        """Update the parameters."""
        self.parameters = [self.item_type,
                           0x00, # Reserved
                           self.item_length,
                           self.user_data]

    def _update_item_length(self):
        """Update the item length."""
        self.item_length = 0
        for ii in self.user_data:
            self.item_length += ii.length

    def get_length(self):
        """Get the item length."""
        self._update_item_length()
        self._update_parameters()
        return 4 + self.item_length

    def __str__(self):
        s = " User information item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d}\n".format(self.item_length)
        s += "  User Data:\n "

        for ii in self.user_data[1:]:
            s += "  {0!s}".format(ii)

        return s

    @property
    def async_ops_window(self):
        """Get the asynchronous operations window item."""
        for ii in self.user_data:
            if isinstance(ii, AsynchronousOperationsWindowSubItem):
                return ii

        return None

    @property
    def common_ext_neg(self):
        """Get the common extended negotiation items."""
        items = []
        for ii in self.user_data:
            if isinstance(ii, SOPClassCommonExtendedNegotiationSubItem):
                items.append(ii)

        if len(items):
            return items

        return None

    @property
    def ext_neg(self):
        """Get the extended negotiation item."""
        items = []
        for ii in self.user_data:
            if isinstance(ii, SOPClassExtendedNegotiationSubItem):
                items.append(ii)

        if len(items):
            return items

        return None

    @property
    def implementation_class_uid(self):
        """Get the implementation class UID."""
        for ii in self.user_data:
            if isinstance(ii, ImplementationClassUIDSubItem):
                return ii.implementation_class_uid

    @property
    def implementation_version_name(self):
        """Get the implementation version name."""
        for ii in self.user_data:
            if isinstance(ii, ImplementationVersionNameSubItem):
                return ii.implementation_version_name.decode('utf-8')

        return None

    @property
    def maximum_length(self):
        """Get the maximum length."""
        for ii in self.user_data:
            if isinstance(ii, MaximumLengthSubItem):
                return ii.maximum_length_received

    @property
    def max_operations_invoked(self):
        """Get the maximum number of invoked operations."""
        for ii in self.user_data:
            if isinstance(ii, AsynchronousOperationsWindowSubItem):
                return ii.max_operations_invoked

        return None

    @property
    def max_operations_performed(self):
        """Get the maximum number of performed operations."""
        for ii in self.user_data:
            if isinstance(ii, AsynchronousOperationsWindowSubItem):
                return ii.max_operations_invoked

        return None

    @property
    def role_selection(self):
        """Get the SCP/SCU role selection item."""
        roles = []
        for ii in self.user_data:
            if isinstance(ii, SCP_SCU_RoleSelectionSubItem):
                roles.append(ii)

        if len(roles):
            return roles

        return None

    @property
    def user_identity(self):
        """Get the user identity item."""
        for ii in self.user_data:
            if isinstance(ii, UserIdentitySubItemRQ):
                return ii
            elif isinstance(ii, UserIdentitySubItemAC):
                return ii

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

    Used in A_ASSOCIATE_RQ_PDU - Variable items - User Information - User Data
    Used in A_ASSOCIATE_AC_PDU - Variable items - User Information - User Data

    Attributes
    ----------
    length : int
        The length of the encoded Item in bytes
    """
    def __init__(self):
        self.item_type = 0x51
        self.item_length = 0x04
        self.maximum_length_received = None

        self.formats = ['B', 'B', 'H', 'I']
        self.parameters = [self.item_type,
                           0x00,
                           self.item_length,
                           self.maximum_length_received]

    def FromParams(self, primitive):
        """
        Set up the Item using the parameter values from the `primitive`

        Parameters
        ----------
        primitive : pynetdicom3.primitives.MaximumLengthNegotiation
            The primitive to use when setting up the Item
        """
        self.maximum_length_received = primitive.maximum_length_received

        self._update_parameters()

    def ToParams(self):
        """
        Convert the current Item to a primitive

        Returns
        -------
        pynetdicom3.primitives.MaximumLengthNegotiation
            The primitive to convert to
        """
        from pynetdicom3.primitives import MaximumLengthNegotiation

        primitive = MaximumLengthNegotiation()
        primitive.maximum_length_received = self.maximum_length_received

        return primitive

    def Encode(self):
        """
        Encode the Item's parameter values into a bytes string

        Returns
        -------
        bytestring : bytes
            The encoded Item used in the parent PDU
        """
        formats = '> B B H I'
        parameters = [self.item_type,
                      0x00,
                      0x0004,
                      self.maximum_length_received]

        bytestring = bytes()
        bytestring += pack(formats, *parameters)

        return bytestring

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
         _,
         self.maximum_length_received) = unpack('> B B H I', bytestream.read(8))

        self._update_parameters()

    def _update_parameters(self):
        """Update the parameters."""
        self.parameters = [self.item_type,
                           0x00,
                           self.item_length,
                           self.maximum_length_received]

    def get_length(self):
        """Get the item length."""
        self._update_parameters()
        return 0x08

    def __str__(self):
        s = "Maximum length Sub-item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        s += "  Maximum length received: {0:d}\n".format(self.maximum_length_received)
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

    Used in A_ASSOCIATE_RQ_PDU - Variable items - User Information - User Data
    Used in A_ASSOCIATE_AC_PDU - Variable items - User Information - User Data

    Attributes
    ----------
    implementation_class_uid : pydicom.uid.UID
        The Implementation Class UID
    length : int
        The length of the encoded Item in bytes
    """
    def __init__(self):
        self.item_type = 0x52
        self.item_length = None
        self.implementation_class_uid = None

        self.formats = ['B', 'B', 'H', 's']
        self.parameters = [self.item_type,
                           0x00,
                           self.item_length,
                           self.implementation_class_uid]

    def FromParams(self, primitive):
        """
        Set up the Item using the parameter values from the `primitive`

        Parameters
        ----------
        primitive : pynetdicom3.primitives.ImplementationClassUIDNotification
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
        pynetdicom3.primitives.ImplementationClassUIDNotification
            The primitive to convert to
        """
        from pynetdicom3.primitives import ImplementationClassUIDNotification

        primitive = ImplementationClassUIDNotification()
        primitive.implementation_class_uid = self.implementation_class_uid

        return primitive

    def Encode(self):
        """Encode the item"""
        s = b''
        s += pack('B', self.item_type)
        s += pack('B', 0x00)
        s += pack('>H', self.item_length)
        s += bytes(self.implementation_class_uid.title(), 'utf-8')
        return s

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
         self.item_length) = unpack('> B B H', bytestream.read(4))
        self.implementation_class_uid = bytestream.read(self.item_length)

        self._update_parameters()

    def _update_parameters(self):
        """Update the parameters."""
        self.parameters = [self.item_type,
                           0x00,
                           self.item_length,
                           self.implementation_class_uid]

    def get_length(self):
        """Get the item length."""
        self.item_length = len(self.implementation_class_uid)
        self._update_parameters()

        return 4 + self.item_length

    def __str__(self):
        s = "Implementation Class UID Sub-item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        s += "  Implementation class UID: '{0!s}'\n".format(self.implementation_class_uid)

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
            raise TypeError('implementation_class_uid must be str, bytes ' \
                            'or UID')

        self._implementation_class_uid = value
        if value is not None:
            self.item_length = len(self.implementation_class_uid)

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

    Used in A_ASSOCIATE_RQ_PDU - Variable items - User Information - User Data
    Used in A_ASSOCIATE_AC_PDU - Variable items - User Information - User Data

    Attributes
    ----------
    implementation_version_name : bytes
        The Implementation Version Name
    length : int
        The length of the encoded Item in bytes
    """
    def __init__(self):
        self.item_type = 0x55
        self.item_length = None
        self.implementation_version_name = None

        self.formats = ['B', 'B', 'H', 's']
        self.parameters = [self.item_type,
                           0x00,
                           self.item_length,
                           self.implementation_version_name]

    def FromParams(self, primitive):
        """
        Set up the Item using the parameter values from the `primitive`

        Parameters
        ----------
        primitive : pynetdicom3.primitives.ImplementationVersionNameNotification
            The primitive to use when setting up the Item
        """
        self.implementation_version_name = primitive.implementation_version_name

        self._update_parameters()

    def ToParams(self):
        """Convert the current Item to a primitive.

        Returns
        -------
        pynetdicom3.primitives.ImplementationVersionNameNotification
            The primitive to convert to
        """
        from pynetdicom3.primitives import ImplementationVersionNameNotification

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
         self.item_length) = unpack('> B B H', bytestream.read(4))
        self.implementation_version_name = bytestream.read(self.item_length)

        self._update_parameters()

    def _update_parameters(self):
        """Update the parameters."""
        self.parameters = [self.item_type,
                           0x00,
                           self.item_length,
                           self.implementation_version_name]

    def get_length(self):
        """Get the item length."""
        self.item_length = len(self.implementation_version_name)
        self._update_parameters()

        return 4 + self.item_length

    def __str__(self):
        s = "Implementation Version Name Sub-item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        s += "  Implementation version name: {0!s}\n".format( \
            self.implementation_version_name)

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
            value = bytes(value, 'utf-8')

        self._implementation_version_name = value
        if value is not None:
            self.item_length = len(self.implementation_version_name)

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

    Used in A_ASSOCIATE_RQ_PDU - Variable items - User Information - User Data
    Used in A_ASSOCIATE_AC_PDU - Variable items - User Information - User Data

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
        self.item_type = 0x54
        self.item_length = None
        self.uid_length = None
        self.sop_class_uid = None
        self.scu_role = None
        self.scp_role = None

        self.formats = ['B', 'B', 'H', 'H', 's', 'B', 'B']
        self.parameters = [self.item_type,
                           0x00,
                           self.item_length,
                           self.uid_length,
                           self.sop_class_uid,
                           self.scu_role,
                           self.scp_role]

    def FromParams(self, primitive):
        """
        Set up the Item using the parameter values from the `primitive`

        Parameters
        ----------
        primitive : pynetdicom3.primitives.SCP_SCU_RoleSelectionNegotiation
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
        pynetdicom3.primitives.SCP_SCU_RoleSelectionNegotiation
            The primitive to convert to
        """
        from pynetdicom3.primitives import SCP_SCU_RoleSelectionNegotiation

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

        bytestring = bytes()
        bytestring += pack(formats, *parameters)
        bytestring += bytes(self.sop_class_uid.title(), 'utf-8')
        bytestring += pack('> B B', self.scu_role, self.scp_role)

        return bytestring

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
         self.item_length,
         self.uid_length) = unpack('> B B H H', bytestream.read(6))

        self.sop_class_uid = bytestream.read(self.uid_length)

        (self.scu_role, self.scp_role) = unpack('B B', bytestream.read(2))

        self._update_parameters()

    def _update_parameters(self):
        """Update the parameters"""
        self.parameters = [self.item_type,
                           0x00,
                           self.item_length,
                           self.uid_length,
                           self.sop_class_uid,
                           self.scu_role,
                           self.scp_role]

    def get_length(self):
        """Get the item length"""
        self.item_length = 4 + len(self.sop_class_uid)
        self.uid_length = len(self.sop_class_uid)
        self._update_parameters()

        return 4 + self.item_length

    def __str__(self):
        s = "SCP/SCU Role Selection Sub-item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        s += "  UID length: {0:d} bytes\n".format(self.uid_length)
        s += "  SOP Class UID: {0!s}\n".format(self.UID)
        s += "  SCU Role: {0:d}\n".format(self.SCU)
        s += "  SCP Role: {0:d}\n".format(self.SCP)

        return s

    @property
    def UID(self):
        """Get the UID."""
        return self.sop_class_uid

    @property
    def sop_class_uid(self):
        """Get the SOP class uid."""
        return self._sop_class_uid

    @sop_class_uid.setter
    def sop_class_uid(self, value):
        """Set the SOP class uid."""
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, bytes):
            value = UID(value.decode('utf-8'))
        elif isinstance(value, str):
            value = UID(value)
        elif isinstance(value, UID):
            pass
        elif value is None:
            pass
        else:
            raise TypeError('sop_class_uid must be str, bytes or ' \
                            'pydicom.uid.UID')

        self._sop_class_uid = value

        if value is not None:
            self.uid_length = len(value)
            self.item_length = 4 + self.uid_length

    @property
    def SCU(self):
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
    def SCP(self):
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

    Used in A_ASSOCIATE_RQ_PDU - Variable items - User Information - User Data
    Used in A_ASSOCIATE_AC_PDU - Variable items - User Information - User Data

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
        self.item_type = 0x53
        self.item_length = 0x04
        self.maximum_number_operations_invoked = None
        self.maximum_number_operations_performed = None

        self.formats = ['B', 'B', 'H', 'H', 'H']
        self.parameters = [self.item_type,
                           0x00,
                           self.item_length,
                           self.maximum_number_operations_invoked,
                           self.maximum_number_operations_performed]

    def FromParams(self, primitive):
        """
        Set up the Item using the parameter values from the `primitive`

        Parameters
        ----------
        primitive :
        pynetdicom3.primitives.AsynchronousOperationsWindowNegotiation
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
        pynetdicom3.primitives.AsynchronousOperationsWindowNegotiation
            The primitive to convert to
        """
        from pynetdicom3.primitives import \
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
        bytestring : bytes
            The encoded Item used in the parent PDU
        """
        formats = '> B B H H H'
        parameters = [self.item_type,
                      0x00,
                      self.item_length,
                      self.maximum_number_operations_invoked,
                      self.maximum_number_operations_performed]

        bytestring = bytes()
        bytestring += pack(formats, *parameters)

        return bytestring

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
         self.item_length,
         self.maximum_number_operations_invoked,
         self.maximum_number_operations_performed) = \
            unpack('>B B H H H', bytestream.read(8))

        self._update_parameters()

    def _update_parameters(self):
        """Update the parameters"""
        self.parameters = [self.item_type,
                           0x00,
                           self.item_length,
                           self.maximum_number_operations_invoked,
                           self.maximum_number_operations_performed]

    def get_length(self):
        """Get the item length"""
        self._update_parameters()
        return 8

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
        s += "  Max. number of operations invoked: {0:d}\n".format( \
            self.maximum_number_operations_invoked)
        s += "  Max. number of operations performed: {0:d}\n".format( \
            self.maximum_number_operations_performed)

        return s

class UserIdentitySubItemRQ(PDU):
    """
    Represents the User Identity RQ Sub Item used in A-ASSOCIATE-RQ PDUs.

    The User Identity RQ Sub Item requires the following parameters
    (see PS3.7 Annex D.3.3.7.1):
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

    Used in A_ASSOCIATE_RQ_PDU - Variable items - User Information - User Data

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
        self.item_type = 0x58
        self.item_length = None
        self.user_identity_type = None
        self.positive_response_requested = None
        self.primary_field_length = None
        self.primary_field = None
        self.secondary_field_length = None
        self.secondary_field = None

    def __str__(self):
        s = "User Identity (RQ) Sub-item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        s += "  User identity type: {0:d}\n".format(self.user_identity_type)
        s += "  Positive response requested: {0:d}\n".format( \
            self.positive_response_requested)
        s += "  Primary field length: {0:d} bytes\n".format(self.primary_field_length)
        s += "  Primary field: {0!s}\n".format(self.primary_field)

        if self.user_identity_type == 0x02:
            s += "  Secondary field length: {0:d} bytes\n".format( \
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
        primitive : pynetdicom3.primitives.UserIdentityParameters
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
        pynetdicom3.primitives.UseIdentityParameters
            The primitive to convert to
        """
        from pynetdicom3.primitives import UserIdentityNegotiation

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
        bytestring : bytes
            The encoded Item used in the parent PDU
        """
        formats = '> B B H B B H'
        parameters = [self.item_type,
                      0x00,
                      self.item_length,
                      self.user_identity_type,
                      self.positive_response_requested,
                      self.primary_field_length]

        bytestring = bytes()
        bytestring += pack(formats, *parameters)
        bytestring += bytes(self.primary_field)
        bytestring += pack('>H', self.secondary_field_length)
        if self.user_identity_type == 0x02:
            bytestring += bytes(self.secondary_field)

        return bytestring

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
         self.item_length,
         self.user_identity_type,
         self.positive_response_requested,
         self.primary_field_length) = unpack('>B B H B B H', bytestream.read(8))

        self.primary_field = bytestream.read(self.primary_field_length)
        (self.secondary_field_length,) = unpack('>H', bytestream.read(2))

        if self.user_identity_type == 0x02:
            self.secondary_field = bytestream.read(self.secondary_field_length)

    def get_length(self):
        """Get the item length"""
        self.item_length = 6 + self.primary_field_length + \
                           self.secondary_field_length
        #self._update_parameters()

        return 4 + self.item_length

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
        id_types = {1 : 'Username',
                    2 : 'Username/Password',
                    3 : 'Kerberos',
                    4 : 'SAML'}

        return id_types[self.user_identity_type]

    @property
    def primary(self):
        """Get the primary field"""
        return self.primary_field

    @property
    def response_requested(self):
        """Get the response requested"""
        return bool(self.positive_response_requested)

    @property
    def secondary(self):
        """Get the secondary field"""
        return self.secondary_field

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

    Used in A_ASSOCIATE_AC_PDU - Variable items - User Information - User Data

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
    """
    def __init__(self):
        self.item_type = 0x58
        self.item_length = None
        self.server_response_length = None
        self.server_response = None

        self.formats = ['B', 'B', 'H', 'H', 's']
        self.parameters = [self.item_type,
                           0x00,
                           self.item_length,
                           self.server_response_length,
                           self.server_response]

    def __str__(self):
        s = "User Identity (AC) Sub-item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        s += "  Server response length: {0:d} bytes\n".format( \
            self.server_response_length)
        s += "  Server response: {0!s}\n".format(self.server_response)

        return s

    def FromParams(self, primitive):
        """
        Set up the Item using the parameter values from the `primitive`

        Parameters
        ----------
        primitive : pynetdicom3.primitives.UserIdentityParameters
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
        pynetdicom3.primitives.UseIdentityParameters
            The primitive to convert to
        """
        from pynetdicom3.primitives import UserIdentityNegotiation

        primitive = UserIdentityParameters()
        primitive.server_response = self.server_response

        return primitive

    def Encode(self):
        """
        Encode the Item's parameter values into a bytes string

        Returns
        -------
        bytestring : bytes
            The encoded Item used in the parent PDU
        """
        formats = '> B B H H'
        parameters = [self.item_type,
                      0x00,
                      self.item_length,
                      self.server_response_length]

        bytestring = bytes()
        bytestring += pack(formats, *parameters)
        bytestring += bytes(self.server_response)

        return bytestring

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
         self.item_length,
         self.server_response_length) = unpack('>B B H H', bytestream.read(6))

        self.server_response = bytestream.read(self.server_response_length)

        self._update_parameters()

    def _update_parameters(self):
        """Update the parameters"""
        self.parameters = [self.item_type,
                           0x00,
                           self.item_length,
                           self.server_response_length,
                           self.server_response]

    def get_length(self):
        """Get the item length"""
        self.item_length = 2 + self.server_response_length
        self._update_parameters()

        return 4 + self.item_length

    @property
    def response(self):
        """Get the response"""
        return self.server_response

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

    Used in A_ASSOCIATE_RQ_PDU - Variable items - User Information - User Data
    Used in A_ASSOCIATE_AC_PDU - Variable items - User Information - User Data

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
        self.item_type = 0x56
        self.item_length = None
        self.sop_class_uid_length = None
        self.sop_class_uid = None
        self.service_class_application_information = None

        self.formats = ['B', 'B', 'H', 'H', 's', 's']
        self.parameters = [self.item_type,
                           0x00,
                           self.item_length,
                           self.sop_class_uid_length,
                           self.sop_class_uid,
                           self.service_class_application_information]

    def FromParams(self, primitive):
        """
        Set up the Item using the parameter values from the `primitive`

        Parameters
        ----------
        primitive : pynetdicom3.primitives.SOPClassExtendedNegotiation
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
        pynetdicom3.primitives.SOPClassExtendedNegotiation
            The primitive to convert to
        """
        from pynetdicom3.primitives import SOPClassExtendedNegotiation

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
        bytestring : bytes
            The encoded Item used in the parent PDU
        """
        formats = '> B B H H'
        parameters = [self.item_type,
                      0x00,
                      self.item_length,
                      self.sop_class_uid_length]

        bytestring = bytes()
        bytestring += pack(formats, *parameters)
        bytestring += bytes(self.sop_class_uid.title(), 'utf-8')
        bytestring += self.service_class_application_information

        return bytestring

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
         self.item_length,
         self.sop_class_uid_length) = unpack('>B B H H', bytestream.read(6))

        self.sop_class_uid = bytestream.read(self.sop_class_uid_length)
        remaining = self.item_length - 2 - self.sop_class_uid_length
        self.service_class_application_information = bytestream.read(remaining)

        self._update_parameters()

    def _update_parameters(self):
        """Update the parameters"""
        self.parameters = [self.item_type,
                           0x00,
                           self.item_length,
                           self.sop_class_uid_length,
                           self.sop_class_uid,
                           self.service_class_application_information]

    def get_length(self):
        """Get the item length"""
        self.item_length = 2 + self.sop_class_uid_length \
                             + len(self.service_class_application_information)

        return 4 + self.item_length

    def __str__(self):
        s = "SOP Class Extended Negotiation Sub-item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        s += "  SOP class UID length: {0:d} bytes\n".format(self.sop_class_uid_length)
        s += "  SOP class: ={0!s}\n".format(self.sop_class_uid)
        s += "  Service class application information: {0!s}\n".format( \
            self.service_class_application_information)

        return s

    @property
    def UID(self):
        """Get the SOP class uid"""
        return self.sop_class_uid

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
        elif isinstance(value, UID):
            pass
        elif value is None:
            pass
        else:
            raise TypeError('sop_class_uid must be str, bytes or ' \
                            'pydicom.uid.UID')

        self._sop_class_uid = value

        if value is not None:
            self.sop_class_uid_length = len(value)

    @property
    def app_info(self):
        """Set the application information"""
        return self.service_class_application_information

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

    Used in A_ASSOCIATE_RQ_PDU - Variable items - User Information - User Data

    Attributes
    ----------
    length : int
        The length of the encoded Item in bytes
    FIXME
    """
    def __init__(self):
        self.item_type = 0x57
        self.sub_item_version = 0x00
        self.item_length = None
        self.sop_class_uid_length = None
        self.sop_class_uid = None
        self.service_class_uid_length = None
        self.service_class_uid = None
        self.related_general_sop_class_identification_length = None
        self.related_general_sop_class_identification = []

        self.formats = ['B', 'B', 'H', 'H', 's', 'H', 's', 'H']
        self.parameters = [self.item_type,
                           self.sub_item_version,
                           self.item_length,
                           self.sop_class_uid_length,
                           self.sop_class_uid,
                           self.service_class_uid_length,
                           self.service_class_uid,
                           self.related_general_sop_class_identification_length,
                           self.related_general_sop_class_identification]

    def FromParams(self, primitive):
        """
        Set up the Item using the parameter values from the `primitive`

        Parameters
        ----------
        primitive : pynetdicom3.primitives.SOPClassCommonExtendedNegotiation
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
        pynetdicom3.primitives.SOPClassCommonExtendedNegotiation
            The primitive to convert to
        """
        from pynetdicom3.primitives import SOPClassCommonExtendedNegotiation

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
        bytestring : bytes
            The encoded Item used in the parent PDU
        """
        formats = '> B B H H'
        parameters = [self.item_type,
                      self.sub_item_version,
                      self.item_length,
                      self.sop_class_uid_length]

        bytestring = bytes()
        bytestring += pack(formats, *parameters)
        bytestring += bytes(self.sop_class_uid.title(), 'utf-8')
        bytestring += pack('>H', self.service_class_uid_length)
        bytestring += bytes(self.service_class_uid, 'utf-8')
        bytestring += \
            pack('>H', self.related_general_sop_class_identification_length)

        for sub_fields in self.related_general_sop_class_identification:
            bytestring += pack('>H', len(sub_fields))
            bytestring += bytes(sub_fields.title(), 'utf-8')

        return bytestring

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

    def get_length(self):
        """Get the item length"""
        self.item_length = 4 + len(self.sop_class_uid)
        self.sop_class_uid_length = len(self.sop_class_uid)

        return 4 + self.item_length

    def __str__(self):
        s = "SOP Class Common Extended Negotiation Sub-item\n"
        s += "  Item type: 0x{0:02x}\n".format(self.item_type)
        s += "  Item length: {0:d} bytes\n".format(self.item_length)
        s += "  SOP class UID length: {0:d} bytes\n".format(self.sop_class_uid_length)
        s += "  SOP class: ={0!s}\n".format(self.sop_class_uid)
        s += "  Service class UID length: {0:d} bytes\n".format( \
            self.service_class_uid_length)
        s += "  Service class UID: ={0!s}\n".format(self.service_class_uid)
        s += "  Related general SOP class ID length: {0:d} bytes\n".format( \
            self.related_general_sop_class_identification_length)
        s += "  Related general SOP class ID(s):\n"

        for ii in self.related_general_sop_class_identification:
            s += "    ={0!s} ({1!s})\n".format(ii, ii.title())

        return s

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
        elif isinstance(value, UID):
            pass
        elif value is None:
            pass
        else:
            raise TypeError('sop_class_uid must be str, bytes or ' \
                            'pydicom.uid.UID')

        self._sop_class_uid = value

        if value is not None:
            self.sop_class_uid_length = len(value)

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
        elif isinstance(value, UID):
            pass
        elif value is None:
            pass
        else:
            raise TypeError('service_class_uid must be str, bytes or ' \
                            'pydicom.uid.UID')

        self._service_class_uid = value

        if value is not None:
            self.service_class_uid_length = len(value)

    @property
    def related_general_sop_class_identification(self):
        """Get the related general sop class ID"""
        return self._related_general_sop_class_identification

    @related_general_sop_class_identification.setter
    def related_general_sop_class_identification(self, value_list):
        """Set the related general sop class ID"""
        # pylint: disable=attribute-defined-outside-init
        self._related_general_sop_class_identification = []
        self.related_general_sop_class_identification_length = 0

        for value in value_list:
            if isinstance(value, bytes):
                value = UID(value.decode('utf-8'))
            elif isinstance(value, str):
                value = UID(value)
            elif isinstance(value, UID):
                pass
            else:
                raise TypeError('related_general_sop_class_identification ' \
                                'must be str, bytes or pydicom.uid.UID')

            self._related_general_sop_class_identification.append(value)
            self.related_general_sop_class_identification_length += len(value)
