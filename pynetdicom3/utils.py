"""Various utility functions."""

import codecs
from io import BytesIO
import logging
import sys
import unicodedata

from pydicom.uid import UID

from pynetdicom3.presentation import PresentationContext

LOGGER = logging.getLogger('pynetdicom3.utils')

IS_PYTHON3 = sys.version_info[0] == (3,)


def validate_ae_title(ae_title):
    """Return a valid AE title from `ae_title`, if possible.

    An AE title:

    * Must be no more than 16 characters
    * Leading and trailing spaces are not significant
    * The characters should belong to the Default Character Repertoire
      excluding 5CH (backslash "\") and all control characters

    If the supplied `ae_title` is greater than 16 characters once
    non-significant spaces have been removed then the returned AE title
    will be truncated to remove the excess characters.

    If the supplied `ae_title` is less than 16 characters once non-significant
    spaces have been removed, the spare trailing characters will be set to
    space (0x20)

    Parameters
    ----------
    ae_title : str or bytes
        The AE title to check

    Returns
    -------
    str or bytes
        A valid AE title (with the same type as the supplied `ae_title`),
        truncated to 16 characters if necessary. If Python 3 then only returns
        bytes.

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
            ae_title = ae_title.decode('ascii')

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
                return codecs.encode(significant_characters, 'ascii')

            return significant_characters

        # AE title too long : truncate
        elif len(significant_characters.strip()) > 16:
            if is_bytes:
                return codecs.encode(significant_characters[:16], 'ascii')

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


def pretty_bytes(bytestream, prefix='  ', delimiter='  ', items_per_line=16,
                 max_size=512, suffix=''):
    """Turn the bytestring `bytestream` into a list of nicely formatted str.

    Parameters
    ----------
    bytestream : bytes or io.BytesIO
        The bytes to convert to a nicely formatted string list
    prefix : str
        Insert `prefix` at the start of every item in the output string list
    delimiter : str
        Delimit each of the bytes in `bytestream` using `delimiter`
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
    if isinstance(bytestream, BytesIO):
        bytestream = bytestream.getvalue()

    cutoff_output = False
    byte_count = 0
    for ii in range(0, len(bytestream), items_per_line):
        # chunk is a bytes in python3 and a str in python2
        chunk = bytestream[ii:ii + items_per_line]
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


class PresentationContextManager(object):
    """
    **DEPRECATED, TO BE REMOVED**

    Manages the presentation contexts supplied by the association requestor and
    acceptor

    To use you should first set the `requestor_contexts` attributes using a list
    of PresentationContext items, then set the `acceptor_contexts` attribute
    using another list of PresentationContext items. The accepted contexts are
    then available in the `accepted` attribute while the rejected ones are in
    the `rejected` attribute.
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
        result_context._scu_role = request_context._scu_role
        result_context._scp_role = request_context._scp_role
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
                # Get the acceptor context with the same Abstract Syntax as
                #   the requestor context
                acc_context = None
                for ii_acc in self._acceptor_contexts:
                    # The acceptor context will only have an abstract syntax
                    #   if we are the Acceptor, otherwise we have to match
                    #   using the IDs

                    # If we are the Requestor then the Acceptor contexts
                    #   will have no Abstract Syntax
                    if ii_acc.abstract_syntax is not None:
                        if ii_acc.abstract_syntax == ii_req.abstract_syntax:
                            acc_context = ii_acc
                    else:
                        if ii_acc.context_id == ii_req.context_id:
                            acc_context = ii_acc
                            # Set Abstract Syntax (for convenience)
                            ii_acc.abstract_syntax = ii_req.abstract_syntax

                # Create a new PresentationContext item that will store the
                #   results from the negotiation
                result = PresentationContext()
                result.context_id = ii_req.context_id
                result.abstract_syntax = ii_req.abstract_syntax

                # If no matching Abstract Syntax then we are the Acceptor and
                #   we reject the current context (0x03 - abstract syntax not
                #   supported)
                if acc_context is None:
                    # FIXME: make pdu not require this.
                    result.transfer_syntax = [ii_req.transfer_syntax[0]]
                    result.result = 0x03
                    result = self.negotiate_scp_scu_role(ii_req, result)
                    self.rejected.append(result)

                # If there is a matching Abstract Syntax then check to see if
                #   the result is None (indicates we are the Acceptor) or
                #   has a value set (indicates we are the Requestor)
                else:
                    # We are the Acceptor and must decide to accept or reject
                    #   the context
                    if acc_context.result is None:

                        # Check the Transfer Syntaxes
                        #   We accept the first matching transfer syntax
                        for transfer_syntax in acc_context.transfer_syntax:
                            # The local transfer syntax is used in order to
                            #   enforce preference based on position
                            if transfer_syntax in ii_req.transfer_syntax:
                                result.transfer_syntax = [transfer_syntax]
                                result.result = 0x00
                                result = self.negotiate_scp_scu_role(ii_req,
                                                                     result)
                                self.accepted.append(result)
                                break

                        # Refuse sop class because TS not supported
                        else:
                            # FIXME: make pdu not require this.
                            result.transfer_syntax = [transfer_syntax]
                            result.result = 0x04
                            result = self.negotiate_scp_scu_role(ii_req, result)
                            self.rejected.append(result)

                    # We are the Requestor and the Acceptor has accepted this
                    #   context
                    elif acc_context.result == 0x00:
                        # The accepted transfer syntax (there is only 1)
                        result.transfer_syntax = [acc_context.transfer_syntax[0]]

                        # Add it to the list of accepted presentation contexts
                        self.accepted.append(result)

                    # We are the Requestor and the Acceptor has rejected this
                    #   context
                    elif acc_context.result in [0x01, 0x02, 0x03, 0x04]:
                        # The rejected transfer syntax(es)
                        result.transfer_syntax = acc_context.transfer_syntax

                        # Add it to the list of accepted presentation contexts
                        self.rejected.append(result)

                    else:
                        raise ValueError("Invalid 'Result' parameter in the "
                                         "Acceptor's Presentation Context list")
