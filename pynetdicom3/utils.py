"""Various utility functions."""

import codecs
from io import BytesIO
import logging
import unicodedata

from pydicom.uid import UID

LOGGER = logging.getLogger('pynetdicom3.utils')


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
    ae_title : str or bytes
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
                return codecs.encode(significant_characters, 'utf-8')

            return significant_characters

        # AE title too long : truncate
        elif len(significant_characters.strip()) > 16:
            if is_bytes:
                return codecs.encode(significant_characters[:16], 'utf-8')

            return significant_characters[:16]

        # AE title empty str
        else:
            raise ValueError("Invalid value for an AE title; must be a "
                             "non-empty string or bytes.")
    except AttributeError:
        raise TypeError("Invalid value for an AE title; must be a "
                        "non-empty string or bytes.")
    except ValueError:
        raise
    except:
        raise TypeError("Invalid value for an AE title; must be a "
                        "non-empty string or bytes.")

def pretty_bytes(lst, prefix='  ', delimiter='  ', items_per_line=16,
                 max_size=512, suffix=''):
    """Turn the bytestring `lst` into a list of nicely formatted str.

    Parameters
    ----------
    bytestream : bytes or io.BytesIO
        The bytes to convert to a nicely formatted string list
    prefix : str
        Insert `prefix` at the start of every item in the output string list
    delimiter : str
        Delimit each of the bytes in `lst` using `delimiter`
    items_per_line : int
        The number of bytes in each item of the output string list.
    max_size : int or None
        The maximum number of bytes to add to the output string list. A value
        of None indicates that all of `bytestream` should be output.
    suffix : str
        Append `suffix` to the end of every item in the output string list

    Returns
    -------
    list of str
        The output string list
    """
    lines = []
    if isinstance(lst, BytesIO):
        lst = lst.getvalue()

    cutoff_output = False
    byte_count = 0
    for ii in range(0, len(lst), items_per_line):
        # chunk is a bytes in python3 and a str in python2
        chunk = lst[ii:ii + items_per_line]
        byte_count += len(chunk)

        # Python 2 compatibility
        if isinstance(chunk, str):
            gen = (format(ord(x), '02x') for x in chunk)
        else:
            gen = (format(x, '02x') for x in chunk)


        if max_size is not None and byte_count <= max_size:
            line = prefix + delimiter.join(gen)
            lines.append(line + suffix)
        elif max_size is not None and byte_count > max_size:
            cutoff_output = True
            break
        else:
            line = prefix + delimiter.join(gen)
            lines.append(line + suffix)

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
    ID : int
        The presentation context ID
    AbstractSyntax : pydicom.uid.UID
        The abstract syntax
    TransferSyntax : list of pydicom.uid.UID
        The transfer syntax(es)
    SCU : bool
        True if...
    SCP : bool
        True if...
    Result : int or None
        If part of the A-ASSOCIATE request then None.
        If part of the A-ASSOCIATE resposne then one of:
            0x00, 0x01, 0x02, 0x03, 0x04
    status : str
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
            The transfer syntax to add to the Presentation Context. For
            Presentation contexts that are rejected the `transfer_syntax` may
            be an empty UID.
        """
        # UID is a subclass of str
        if isinstance(transfer_syntax, str):
            transfer_syntax = UID(transfer_syntax)
        elif isinstance(transfer_syntax, bytes):
            transfer_syntax = UID(transfer_syntax.decode('utf-8'))
        else:
            raise TypeError('transfer_syntax must be a pydicom.uid.UID,' \
                             ' bytes or str')

        if transfer_syntax not in self.TransferSyntax and \
                                                    transfer_syntax != '':

            if not transfer_syntax.is_valid:
                raise ValueError('Presentation Context attempted to add a '
                                 'invalid UID')
            # Issue #62: private transfer syntaxes may be used
            if not transfer_syntax.is_private and \
                                not transfer_syntax.is_transfer_syntax:
                raise ValueError('Presentation Context attempted to add a '
                                 'non-transfer syntax UID')
            self.TransferSyntax.append(transfer_syntax)

    def __eq__(self, other):
        """Return True if `self` is equal to `other`."""
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__

        return NotImplemented

    def __ne__(self, other):
        """Return inequality"""
        return not self == other

    def __str__(self):
        """String representation of the Presentation Context."""
        s = 'ID: {0!s}\n'.format(self.ID)

        if self.AbstractSyntax is not None:
            s += 'Abstract Syntax: {0!s}\n'.format(self.AbstractSyntax.name)

        s += 'Transfer Syntax(es):\n'
        for syntax in self.TransferSyntax:
            s += '\t={0!s}\n'.format(syntax.name)

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
        if not 1 <= value <= 255:
            raise ValueError("Presentation Context ID must be an odd "
                             "integer between 1 and 255 inclusive")
        elif value % 2 == 0:
            raise ValueError("Presentation Context ID must be an odd "
                             "integer between 1 and 255 inclusive")
        else:
            self._id = value

    @property
    def AbstractSyntax(self):
        """Return the Presentation Context's Abstract Syntax parameter."""
        return self._abstract_syntax

    @AbstractSyntax.setter
    def AbstractSyntax(self, uid):
        """Set the Presentation Context's Abstract Syntax parameter.

        Parameters
        ----------
        uid : str or bytes or pydicom.uid.UID
            The abstract syntax UIDs
        """
        # pylint: disable=attribute-defined-outside-init
        if uid is None:
            self._abstract_syntax = None
            return

        if isinstance(uid, bytes):
            uid = UID(uid.decode('utf-8'))
        elif isinstance(uid, UID):
            pass
        elif isinstance(uid, str):
            uid = UID(uid)
        else:
            raise TypeError("Presentation Context invalid type for abstract "
                            "syntax")

        if not uid.is_valid:
            LOGGER.info('Presentation Context attempted to set an invalid '
                        'abstract syntax UID')
        else:
            self._abstract_syntax = uid

    @property
    def TransferSyntax(self):
        """Return the Presentation Context's Transfer Syntax parameter."""
        return self._transfer_syntax

    @TransferSyntax.setter
    def TransferSyntax(self, uid_list):
        """Set the Presentation Context's Transfer Syntax parameter.

        Parameters
        ----------
        uid_list : list of str or bytes or pydicom.uid.UID
            The transfer syntax UIDs
        """
        # pylint: disable=attribute-defined-outside-init
        self._transfer_syntax = []
        if not isinstance(uid_list, list):
            raise TypeError("transfer_syntaxes must be a list.")

        for uid in uid_list:
            if isinstance(uid, bytes):
                uid = UID(uid.decode('utf-8'))
            elif isinstance(uid, UID):
                pass
            elif isinstance(uid, str):
                uid = UID(uid)
            else:
                raise ValueError("PresentationContext(): Invalid transfer "
                                 "syntax item")

            if not uid.is_valid:
                LOGGER.info('Presentation Context attempted to set an invalid '
                            'transfer syntax UID')
                continue

            if uid.is_private:
                self._transfer_syntax.append(uid)
            elif uid.is_transfer_syntax:
                self._transfer_syntax.append(uid)

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
            raise TypeError("requestor_contexts must be a list of "
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
            raise RuntimeError("You can only set the Acceptor's presentation "
                               "contexts after the Requestor's")

        if not isinstance(contexts, list):
            raise TypeError("acceptor_contexts must be a list of "
                            "PresentationContext items")

        # Validate the supplied contexts
        self._acceptor_contexts = []
        for ii in contexts:
            if isinstance(ii, PresentationContext):
                self._acceptor_contexts.append(ii)
            else:
                raise TypeError("acceptor_contexts must be a list of "
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

                    # If we are the Requestor then the Acceptor contexts
                    #   will have no AbstractSyntax
                    if ii_acc.AbstractSyntax is not None:
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
                    # FIXME: make pdu not require this.
                    result.TransferSyntax = [ii_req.TransferSyntax[0]]
                    result.Result = 0x03
                    result = self.negotiate_scp_scu_role(ii_req, result)
                    self.rejected.append(result)

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
                            if transfer_syntax in ii_req.TransferSyntax:
                                result.TransferSyntax = [transfer_syntax]
                                result.Result = 0x00
                                result = self.negotiate_scp_scu_role(ii_req,
                                                                     result)
                                self.accepted.append(result)
                                break

                        # Refuse sop class because TS not supported
                        else:
                            # FIXME: make pdu not require this.
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
