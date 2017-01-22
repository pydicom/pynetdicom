
"""Various utility functions"""
from io import BytesIO
import logging
from struct import unpack
import unicodedata

from pydicom.uid import UID

LOGGER = logging.getLogger('pynetdicom3.utils')

def fragment(max_pdu, byte_str):
    """Convert the given str into fragments, each of maximum size `max_pdu`

    FIXME: Add Parameters section

    Returns
    -------
    fragments : list of str
        The fragmented string
    """
    if isinstance(byte_str, BytesIO):
        byte_str = byte_str.getvalue()
    s = byte_str
    fragments = []
    maxsize = max_pdu - 6

    while 1:
        fragments.append(s[:maxsize])
        s = s[maxsize:]
        if len(s) <= maxsize:
            if len(s) > 0:
                fragments.append(s)

            return fragments

def correct_ambiguous_vr(dataset, transfer_syntax):
    """Iterate through `dataset` correct ambiguous VR elements.

    Also fixes the element.value as pydicom doesn't always handle decoding
    correctly.

    OB, string of bytes and insensitive to byte ordering
    OW, string of 16-bit words, sensitive to byte ordering
    SS, signed binary int, 16 bits in 2's complement. 2 byte fixed length.
    US, unsigned binary int. 2 byte fixed length.

    Elements with Unsolved Ambiguous VRs
    ------------------------------------
    OB or OW        0014,3050 DarkCurrentCounts (DICONDE)
    OB or OW        0014,3070 AirCounts (DICONDE)
    US or SS        0028,0071 PerimeterValue (Retired)
    US or SS        0028,1100 GrayLookupTableDescriptor (Retired)
    US or SS        0028,1111 LargeRedPaletteColorLookupTableDescriptor (Retired)
    US or SS        0028,1112 LargeGreenPaletteColorLookupTableDescriptor (Retired)
    US or SS        0028,1113 LargeBluePaletteColorLookupTableDescriptor (Retired)
    US or SS or OW  0028,1200 GrayLookupTableData (Retired)
    OB or OW        50xx,200C AudioSampleData (Retired)
    OB or OW        50xx,3000 CurveData (Retired)
    OB or OW        60xx,3000 OverlayData
    OB or OW        7Fxx,0010 VariablePixelData

    Parameters
    ----------
    dataset : pydicom.dataset.Dataset
        The dataset containing the elements with ambiguous VRs
    transfer_syntax :
        The transfer syntax the dataset will be transferred using.

    Returns
    -------
    dataset : pydicom.dataset.Dataset
        A dataset with (hopefully) unambiguous VRs.

    Raises
    ------
    ValueError
        If the ambiguous VR requires another element within the dataset to
        determine the VR to use, but this element is absent then ValueError will
        be raised.
    """
    if transfer_syntax.is_little_endian:
        byte_order = '<'
    else:
        byte_order = '>'

    # Explicit VR Little/Big Endian
    if not transfer_syntax.is_implicit_VR:
        for elem in dataset:
            if ' or ' in elem.VR:
                # OB or OW: 7fe0,0010 PixelData
                if elem.tag == 0x7fe00010:
                    # If BitsAllocated is > 8 then OW, else may be OB or OW
                    #   As per PS3.5 Annex A.2
                    elem.VR = 'OW' # Use OW for both to make it simpler

                # US or SS: 0018,9810 ZeroVelocityPixelValue
                # US or SS: 0022,1452 MappedPixelValue
                # US or SS: 0028,0104 SmallestValidPixelValue (Retired)
                # US or SS: 0028,0105 LargestValidPixelValue (Retired)
                # US or SS: 0028,0106 SmallestImagePixelValue
                # US or SS: 0028,0107 LargestImagePixelValue
                # US or SS: 0028,0108 SmallestPixelValueInSeries
                # US or SS: 0028,0109 LargestPixelValueInSeries
                # US or SS: 0028,0110 SmallestImagePixelValueInPlane (Retired)
                # US or SS: 0028,0111 LargestImagePixelValueInPlane (Retired)
                # US or SS: 0028,0120 PixelPaddingValue
                # US or SS: 0028,0121 PixelPaddingRangeLimit
                # US or SS: 0028,1101 RedPaletteColorLookupTableDescriptor
                # US or SS: 0028,1102 BluePaletteColorLookupTableDescriptor
                # US or SS: 0028,1103 GreenPaletteColorLookupTableDescriptor
                # US or SS: 0028,3002 LUTDescriptor
                # US or SS: 0040,9211 RealWorldValueLastValueMapped
                # US or SS: 0040,9216 RealWorldValueFirstValueMapped
                # US or SS: 0060,3004 HistogramFirstBinValue
                # US or SS: 0060,3006 HistogramLastBinValue
                elif elem.tag in [0x00189810, 0x00221452, 0x00280104,
                                  0x00280105,
                                  0x00280106, 0x00280107, 0x00280108,
                                  0x00280108, 0x00280110, 0x00280111,
                                  0x00280120, 0x00280121,
                                  0x00281101, 0x00281102, 0x00281103,
                                  0x00283002, 0x00409211, 0x00409216,
                                  0x00603004, 0x00603006]:
                    # US if PixelRepresenation value is 0x0000, else SS
                    #   For references, see the list at
                    #   https://github.com/scaramallion/pynetdicom3/issues/3
                    if 'PixelRepresentation' in dataset:
                        if dataset.PixelRepresentation == 0:
                            elem.VR = 'US'
                            value_type = 'H'
                        else:
                            elem.VR = 'SS'
                            value_type = 'h'
                        # Fix for pydicom not handling this correctly
                        elem.value = unpack(byte_order + value_type,
                                            elem.value)[0]

                    else:
                        raise ValueError("Cannot set VR of {} if "
                                         "PixelRepresentation is not in the"
                                         "dataset. Consider using Implicit"
                                         " VR as the transfer syntax."
                                         .format(elem.keyword))

                # OB or OW: 5400,0110 ChannelMinimumValue
                # OB or OW: 5400,0112 ChannelMaximumValue
                # OB or OW: 5400,100A WaveformPaddingValue
                # OB or OW: 5400,1010 WaveformData
                elif elem.tag in [0x54000100, 0x54000112, 0x5400100A,
                                  0x54001010]:
                    # OB if WaveformSampleInterpretation value is
                    #   SB/UB/MB/AB, else OW. See the list at
                    #   https://github.com/scaramallion/pynetdicom3/issues/3
                    if 'WaveformSampleInterpretation' in dataset:
                        if dataset.WaveformSampleInterpretation in \
                                                ['SB', 'UB', 'MB', 'AB']:
                            elem.VR = 'OB'
                        else:
                            elem.VR = 'OW'
                    else:
                        raise ValueError("Cannot set VR of {} if "
                                         "WaveformSampleInterpretation is "
                                         "not in the dataset. Consider "
                                         "using Implicit VR as the "
                                         "transfer syntax."
                                         .format(elem.keyword))

                # US or OW: 0028,3006 LUTData
                elif elem.tag in [0x00283006]:
                    if 'LUTDescriptor' in dataset:
                        # First value in LUT Descriptor is how many values in
                        #   LUTData
                        if dataset.LUTDescriptor[0] == 1:
                            elem.VR = 'US'
                        else:
                            elem.VR = 'OW'
                    else:
                        raise ValueError("Cannot set VR of {} if "
                                         "LUTDescriptor is "
                                         "not in the dataset. Consider "
                                         "using Implicit VR as the "
                                         "transfer syntax."
                                         .format(elem.keyword))
                else:
                    raise NotImplementedError("Cannot set VR of {} as the"
                                              " correct method for doing "
                                              "so is not known."
                                              .format(elem.keyword))

                LOGGER.debug("Setting VR of (%04x, %04x) %s to "
                             "'%s'.", elem.tag.group, elem.tag.elem,
                             elem.name, elem.VR)
    return dataset

def validate_ae_title(ae_title):
    """Return a valid AE title from `ae_title`, if possible.

    An AE title:
    *   Must be no more than 16 characters
    *   Leading and trailing spaces are not significant
    *   The characters should belong to the Default Character Repertoire
        excluding 5CH (backslash "\") and all control characters

    If the supplied `ae_title` is greater than 16 characters once
        non-significant spaces have been removed then the returned AE title
        will be truncated to remove the excess characters.
    If the supplied `ae_title` is less than 16 characters once non-significant
        spaces have been removed, the spare trailing characters will be
        set to space (0x20)

    Parameters
    ----------
    ae_title - str or bytes
        The AE title to check

    Returns
    -------
    str or bytes
        A valid AE title (with the same type as the supplied `ae_title`),
        truncated to 16 characters if necessary.

    Raises
    ------
    ValueError
        If `ae_title` is an empty string, contains only spaces or contains
        control characters or backslash
    TypeError
        If `ae_title` is not a string or bytes
    """
    try:
        is_bytes = False
        if isinstance(ae_title, bytes):
            is_bytes = True
            ae_title = ae_title.decode('utf-8')

        # Remove leading and trailing spaces
        significant_characters = ae_title.strip()

        # Remove trailing nulls (required as AE titles may be padded by nulls)
        #   and common control chars (optional, for convenience)
        significant_characters = significant_characters.rstrip('\0\r\t\n')

        # Check for backslash or control characters
        for char in significant_characters:
            if unicodedata.category(char)[0] == "C" or char == "\\":
                raise ValueError("Invalid value for an AE title; must not "
                                 "contain backslash or control characters")

        # AE title OK
        if 0 < len(significant_characters) <= 16:
            while len(significant_characters) < 16:
                significant_characters += ' '

            if is_bytes:
                return bytes(significant_characters, 'utf-8')
            else:
                return significant_characters

        # AE title too long - truncate
        elif len(significant_characters.strip()) > 16:
            if is_bytes:
                return bytes(significant_characters[:16], 'utf-8')
            else:
                return significant_characters[:16]

        # AE title empty str
        else:
            raise ValueError("Invalid value for an AE title; must be a "
                             "non-empty string")

    except ValueError:
        raise
    except:
        raise TypeError("Invalid value for an AE title; must be a "
                        "non-empty string")

def wrap_list(lst, prefix='  ', delimiter='  ', items_per_line=16,
              max_size=512):
    """Given a bytestring `lst` turn it into a list of nicely formatted str."""
    lines = []
    if isinstance(lst, BytesIO):
        lst = lst.getvalue()

    cutoff_output = False
    byte_count = 0
    for ii in range(0, len(lst), items_per_line):
        chunk = lst[ii:ii + items_per_line]
        byte_count += len(chunk)

        if max_size is not None:
            if byte_count <= max_size:
                line = prefix + delimiter.join(format(x, '02x') for x in chunk)
                lines.append(line)
            else:
                cutoff_output = True
                break
        else:
            line = prefix + delimiter.join(format(x, '02x') for x in chunk)
            lines.append(line)

    if cutoff_output:
        lines.insert(0, prefix + 'Only dumping {0!s} bytes.'.format(max_size))

    return lines


class PresentationContext(object):
    """
    Provides a nice interface for the A-ASSOCIATE Presentation Context item.

    PS3.8 7.1.1
    An A-ASSOCIATE request primitive will contain a Presentation Context
    Definition List, which consists or one or more presentation contexts. Each
    item contains an ID, an Abstract Syntax and a list of one or more Transfer
    Syntaxes.

    An A-ASSOCIATE response primitive will contain a Presentation Context
    Definition Result List, which takes the form of a list of result values,
    with a one-to-one correspondence with the Presentation Context Definition
    List.

    Attributes
    ----------
    ID - int
        The presentation context ID
    AbstractSyntax - pydicom.uid.UID
        The abstract syntax
    TransferSyntax - list of pydicom.uid.UID
        The transfer syntax(es)
    SCU - bool
        True if...
    SCP - bool
        True if...
    Result - int or None
        If part of the A-ASSOCIATE request then None.
        If part of the A-ASSOCIATE resposne then one of:
            0x00, 0x01, 0x02, 0x03, 0x04
    status - str
        The string representation of the Result:
            0x00 : 'acceptance',
            0x01 : 'user rejection',
            0x02 : 'provider rejection'
            0x03 : 'abstract syntax not supported'
            0x04 : 'transfer syntaxes not supported'
    """
    def __init__(self, ID, abstract_syntax=None, transfer_syntaxes=None):
        """Create a new PresentaionContext.

        Parameters
        ----------
        ID : int
            An odd integer between 1 and 255 inclusive
        abstract_syntax : pydicom.uid.UID, optional
            The context's abstract syntax
        transfer_syntaxes : list of pydicom.uid.UID, optional
            The context's transfer syntax(es)
        """
        self.ID = ID
        self.AbstractSyntax = abstract_syntax
        self.TransferSyntax = transfer_syntaxes or []
        self.SCU = None
        self.SCP = None
        self.Result = None

    def add_transfer_syntax(self, transfer_syntax):
        """Append a transfer syntax to the Presentation Context.

        Parameters
        ----------
        transfer_syntax : pydicom.uid.UID, bytes or str
            The transfer syntax to add to the Presentation Context
        """
        if isinstance(transfer_syntax, str):
            transfer_syntax = UID(transfer_syntax)
        elif isinstance(transfer_syntax, bytes):
            transfer_syntax = UID(transfer_syntax.decode('utf-8'))
        else:
            raise ValueError('transfer_syntax must be a pydicom.uid.UID,' \
                             ' bytes or str')

        if isinstance(transfer_syntax, UID):
            if transfer_syntax not in self.TransferSyntax:
                self.TransferSyntax.append(transfer_syntax)

    def __eq__(self, other):
        """Return True if `self` is equal to `other`."""
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__

        return False

    def __str__(self):
        """String representation of the Presentation Context."""
        s = 'ID: {0!s}\n'.format(self.ID)

        if self.AbstractSyntax is not None:
            s += 'Abstract Syntax: {0!s}\n'.format(self.AbstractSyntax)

        s += 'Transfer Syntax(es):\n'
        for syntax in self.TransferSyntax:
            s += '\t={0!s}\n'.format(syntax)

        #s += 'SCP/SCU: %s/%s'

        if self.Result is not None:
            s += 'Result: {0!s}\n'.format(self.status)

        return s

    @property
    def ID(self):
        """Return the Presentation Context's ID parameter."""
        return self._id

    @ID.setter
    def ID(self, value):
        """Set the Presentation Context's ID parameter.

        FIXME: Add Parameters section
        """
        # pylint: disable=attribute-defined-outside-init
        if 1 <= value <= 255:
            if value % 2 == 0:
                raise ValueError("Presentation Context ID must be an odd "
                                 "integer between 1 and 255 inclusive")
            else:
                self._id = value

    @property
    def AbstractSyntax(self):
        """Return the Presentation Context's Abstract Syntax parameter."""
        return self._abstract_syntax

    @AbstractSyntax.setter
    def AbstractSyntax(self, value):
        """Set the Presentation Context's Abstract Syntax parameter.

        FIXME: Add Parameters section
        `value` must be a pydicom.uid.UID, a string UID or a byte string UID
        """
        # pylint: disable=attribute-defined-outside-init
        if isinstance(value, bytes):
            value = UID(value.decode('utf-8'))
        elif isinstance(value, UID):
            pass
        elif isinstance(value, str):
            value = UID(value)
        elif value is None:
            pass
        else:
            raise ValueError("PresentationContext(): Invalid abstract syntax")

        self._abstract_syntax = value

    @property
    def TransferSyntax(self):
        """Return the Presentation Context's Transfer Syntax parameter."""
        return self._transfer_syntax

    @TransferSyntax.setter
    def TransferSyntax(self, value):
        """Set the Presentation Context's Transfer Syntax parameter.

        FIXME: Add Parameters section
        `value` must be a list of pydicom.uid.UIDs, string UIDs or byte string
        UIDs
        """
        # pylint: disable=attribute-defined-outside-init
        self._transfer_syntax = []
        for ii in value:
            if isinstance(value, bytes):
                ii = UID(ii.decode('utf-8'))
            elif isinstance(ii, UID):
                pass
            elif isinstance(ii, str):
                ii = UID(ii)
            else:
                raise ValueError("PresentationContext(): Invalid transfer "
                                 "syntax item")
            self._transfer_syntax.append(ii)

    @property
    def status(self):
        """Return the status of the Presentation Context"""
        if self.Result is None:
            status = 'Pending'
        elif self.Result == 0x00:
            status = 'Accepted'
        elif self.Result == 0x01:
            status = 'User Rejected'
        elif self.Result == 0x02:
            status = 'Provider Rejected'
        elif self.Result == 0x03:
            status = 'Abstract Syntax Not Supported'
        elif self.Result == 0x04:
            status = 'Transfer Syntax(es) Not Supported'
        else:
            status = 'Unknown'

        return status


class PresentationContextManager(object):
    """
    Manages the presentation contexts supplied by the association requestor and
    acceptor

    To use you should first set the `requestor_contexts` attributes using a list
    of PresentationContext items, then set the `acceptor_contexts` attribute
    using another list of PresentationContext items. The accepted contexts are
    then available in the `accepted` attribute while the rejected ones are in
    the `rejected` attribute.

    FIXME: Add Attributes section
    """
    def __init__(self, request_contexts=None, response_contexts=None):
        """Create a new PresentationContextManager.

        FIXME: Add Parameters section
        """
        # The list of PresentationContext objects sent by the requestor
        self.requestor_contexts = request_contexts or []
        # The list of PresentationContext objects sent by the acceptor
        self._acceptor_contexts = response_contexts or []
        self.accepted = []
        self.rejected = []

    def reset(self):
        """Reset the PresentationContextManager."""
        self.acceptor_contexts = []
        self.requestor_contexts = []
        self.accepted = []
        self.rejected = []

    @staticmethod
    def negotiate_scp_scu_role(request_context, result_context):
        """ Negotiates the SCP/SCU role """
        result_context.SCU = request_context.SCU
        result_context.SCP = request_context.SCP
        return result_context

    @property
    def requestor_contexts(self):
        """Return the Requestor's presentation contexts"""
        return self._requestor_contexts

    @requestor_contexts.setter
    def requestor_contexts(self, contexts):
        """Set the Requestor's presentation contexts.

        Must be a list of pynetdicom3.utils.PresentationContext
            When the local AE is making the request this is a list of
            the SCUsupported SOP classes combined with the supported Transfer
            Syntax(es)
        When the peer AE is making the request this is the contents of the
            A-ASSOCIATE PresentationContextDefinitionList parameter
        """
        # pylint: disable=attribute-defined-outside-init
        self._requestor_contexts = []
        try:
            for ii in contexts:
                if isinstance(ii, PresentationContext):
                    self._requestor_contexts.append(ii)
        except:
            raise ValueError("requestor_contexts must be a list of "
                             "PresentationContext items")

    @property
    def acceptor_contexts(self):
        """Return the Acceptor's presentation contexts"""
        return self._acceptor_contexts

    @acceptor_contexts.setter
    def acceptor_contexts(self, contexts):
        """Set the Acceptor's presentation contexts.

        Must be a list of pynetdicom3.utils.PresentationContext
        There are two possible situations
          1. The local AE issues the request and receives the response
          2. The peer AE issues the request and the local must determine
           the response
        The first situation means that the acceptor has already decided on
          a Result and (if accepted) which Transfer Syntax to use
        The second situation means that we must determine whether to accept
          or reject presentation context and which Transfer Syntax to use

          requestor_contexts cannot be an empty list
        When the local AE is making the request, this is just the contents of
        the A-ASSOCIATE PresentationContextDefinitionResultList parameter
         (Result value will not be None)
        When the peer AE is making the request this will be the list of the
          SCP supported SOP classes combined with the supported Transfer
          Syntax(es) (Result value will be None)

        FIXME: This needs to be refactored, its slow and overly complex
        FIXME: It would be better to have a separate method to call when the
            user wants the contexts evaluated
        """
        if self.requestor_contexts == []:
            raise ValueError("You can only set the Acceptor's presentation "
                             "contexts after the Requestor's")

        # Validate the supplied contexts
        self._acceptor_contexts = []
        try:
            for ii in contexts:
                if isinstance(ii, PresentationContext):
                    self._acceptor_contexts.append(ii)
        except:
            raise ValueError("acceptor_contexts must be a list of "
                             "PresentationContext items")

        # Generate accepted_contexts and rejected_contexts
        self.accepted = []
        self.rejected = []
        if self._acceptor_contexts != [] and self._requestor_contexts != []:
            # For each of the contexts available to the acceptor
            for ii_req in self._requestor_contexts:

                # Get the acceptor context with the same AbstractSyntax as
                #   the requestor context
                acc_context = None
                for ii_acc in self._acceptor_contexts:
                    # The acceptor context will only have an abstract syntax
                    #   if we are the Acceptor, otherwise we have to match
                    #   using the IDs

                    # If we are the Requestor then the Acceptor context's
                    #   will have no AbstractSyntax
                    if ii_acc.AbstractSyntax != None:
                        if ii_acc.AbstractSyntax == ii_req.AbstractSyntax:
                            acc_context = ii_acc
                    else:
                        if ii_acc.ID == ii_req.ID:
                            acc_context = ii_acc
                            # Set AbstractSyntax (for convenience)
                            ii_acc.AbstractSyntax = ii_req.AbstractSyntax

                # Create a new PresentationContext item that will store the
                #   results from the negotiation
                result = PresentationContext(ii_req.ID, ii_req.AbstractSyntax)

                # If no matching AbstractSyntax then we are the Acceptor and we
                #   reject the current context (0x03 - abstract syntax not
                #   supported)
                if acc_context is None:
                    result.Result = 0x03

                # If there is a matching AbstractSyntax then check to see if the
                #   Result attribute is None (indicates we are the Acceptor) or
                #   has a value set (indicates we are the Requestor)
                else:
                    # We are the Acceptor and must decide to accept or reject
                    #   the context
                    if acc_context.Result is None:

                        # Check the Transfer Syntaxes
                        #   We accept the first matching transfer syntax
                        for transfer_syntax in acc_context.TransferSyntax:
                            # The local transfer syntax is used in order to
                            #   enforce preference based on position
                            matching_ts = False
                            if transfer_syntax in ii_req.TransferSyntax:
                                result.TransferSyntax = [transfer_syntax]
                                result.Result = 0x00
                                result = self.negotiate_scp_scu_role(ii_req,
                                                                     result)
                                self.accepted.append(result)

                                matching_ts = True
                                break

                        # Refuse sop class because TS not supported
                        if not matching_ts:
                            result.TransferSyntax = [transfer_syntax]
                            result.Result = 0x04
                            result = self.negotiate_scp_scu_role(ii_req, result)
                            self.rejected.append(result)

                    # We are the Requestor and the Acceptor has accepted this
                    #   context
                    elif acc_context.Result == 0x00:
                        # The accepted transfer syntax (there is only 1)
                        result.TransferSyntax = [acc_context.TransferSyntax[0]]

                        # Add it to the list of accepted presentation contexts
                        self.accepted.append(result)

                    # We are the Requestor and the Acceptor has rejected this
                    #   context
                    elif acc_context.Result in [0x01, 0x02, 0x03, 0x04]:
                        # The rejected transfer syntax(es)
                        result.TransferSyntax = acc_context.TransferSyntax

                        # Add it to the list of accepted presentation contexts
                        self.rejected.append(result)

                    else:
                        raise ValueError("Invalid 'Result' parameter in the "
                                         "Acceptor's Presentation Context list")
