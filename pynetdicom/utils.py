
from io import BytesIO
import unicodedata

from pydicom.uid import UID

def validate_ae_title(ae_title):
    """
    Checks the supplied `ae_title` to see if its valid. An AE title must:
    *   be no more than 16 characters
    *   leading and trailing spaces are not significant
    *   the characters should belong to the Default Character Repertoire
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

def wrap_list(lst, prefix='  ', delimiter='  ', items_per_line=16, max_size=512):
    lines = []
    if isinstance(lst, BytesIO):
        lst = lst.getvalue()
    
    cutoff_output = False
    byte_count = 0
    for i in range(0, len(lst), items_per_line):
        chunk = lst[i:i + items_per_line]
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
        lines.insert(0, prefix + 'Only dumping %s bytes.' %max_size)
    
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
    
    Parameters
    ----------
    ID - int
        An odd integer between 1 and 255 inclusive
    abstract_syntax - pydicom.uid.UID, optional
        The context's abstract syntax
    transfer_syntaxes - list of pydicom.uid.UID, optional
        The context's transfer syntax(es)
        
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
    def __init__(self, ID, abstract_syntax=None, transfer_syntaxes=[]):
        
        self.ID = ID
        self.AbstractSyntax = abstract_syntax
        self.TransferSyntax = transfer_syntaxes
        self.SCU = None
        self.SCP = None
        self.Result = None
        
    def add_transfer_syntax(self, transfer_syntax):
        """
        Parameters
        ----------
        transfer_syntax - pydicom.uid.UID
            The transfer syntax to add to the Presentation Context
        """
        if isinstance(transfer_syntax, bytes):
            transfer_syntax = UID(transfer_syntax.decode('utf-8'))
        
        if isinstance(transfer_syntax, UID):
            if transfer_syntax not in self.TransferSyntax:
                self.TransferSyntax.append(transfer_syntax)
        
    def __str__(self):
        s = 'ID: %s\n' %self.ID
        
        if self.AbstractSyntax is not None:
            s += 'Abstract Syntax: %s\n' %self.AbstractSyntax
        
        s += 'Transfer Syntax(es):\n'
        for syntax in self.TransferSyntax:
            s += '\t=%s\n' %syntax
        
        #s += 'SCP/SCU: %s/%s'
            
        if self.Result is not None:
            s += 'Result: %s\n' %self.status
            
        return s
    
    @property
    def ID(self):
        return self.__id
        
    @ID.setter
    def ID(self, value):
        if 1 <= value <= 255:
            if value % 2 == 0:
                raise ValueError("Presentation Context ID must be an odd "
                                "integer between 1 and 255 inclusive")
            else:
                self.__id = value
    
    @property
    def AbstractSyntax(self):
        return self.__abstract_syntax
        
    @AbstractSyntax.setter
    def AbstractSyntax(self, value):
        """ 
        `value` must be a pydicom.uid.UID, a string UID or a byte string UID
        """
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

        self.__abstract_syntax = value
        
    @property
    def TransferSyntax(self):
        return self.__transfer_syntax
        
    @TransferSyntax.setter
    def TransferSyntax(self, value):
        """
        `value` must be a list of pydicom.uid.UIDs, string UIDs or byte string
        UIDs
        """
        self.__transfer_syntax = []
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
            self.__transfer_syntax.append(ii)
    
    @property
    def status(self):
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
    """
    def __init__(self, request_contexts=[], response_contexts=[]):
        # The list of PresentationContext objects sent by the requestor
        self.__requestor_contexts = []
        # The list of PresentationContext objects sent by the acceptor
        self.__acceptor_contexts = []
        
        self.accepted = []
        self.rejected = []
    
    def reset(self):
        self.acceptor_contexts = []
        self.requestor_contexts = []
        self.accepted = []
        self.rejected = []
    
    def negotiate_scp_scu_role(self, request_context, result_context):
        """ Negotiates the SCP/SCU role """
        result_context.SCU = request_context.SCU
        result_context.SCP = request_context.SCP
        return result_context
    
    @property
    def requestor_contexts(self):
        return self.__requestor_contexts
        
    @requestor_contexts.setter
    def requestor_contexts(self, contexts):
        # Must be a list of pynetdicom.utils.PresentationContext
        #
        # When the local AE is making the request this is a list of the SCU
        #   supported SOP classes combined with the supported Transfer 
        #   Syntax(es)
        # When the peer AE is making the request this is the contents of the 
        #   A-ASSOCIATE PresentationContextDefinitionList parameter
        self.__requestor_contexts = []
        try:
            for ii in contexts:
                if isinstance(ii, PresentationContext):
                    self.__requestor_contexts.append(ii)
        except:
            raise ValueError("requestor_contexts must be a list of "
                    "PresentationContext items")
    
    @property
    def acceptor_contexts(self):
        return self.__acceptor_contexts
        
    @acceptor_contexts.setter
    def acceptor_contexts(self, contexts):
        # Must be a list of pynetdicom.utils.PresentationContext
        # There are two possible situations
        #   1. The local AE issues the request and receives the response
        #   2. The peer AE issues the request and the local must determine
        #       the response
        # The first situation means that the acceptor has already decided on 
        #   a Result and (if accepted) which Transfer Syntax to use
        # The second situation means that we must determine whether to accept
        #   or reject presentation context and which Transfer Syntax to use
        #
        # requestor_contexts cannot be an empty list
        #
        # When the local AE is making the request, this is just the contents of
        #   the A-ASSOCIATE PresentationContextDefinitionResultList parameter
        #   (Result value will not be None)
        # When the peer AE is making the request this will be the list of the 
        #   SCP supported SOP classes combined with the supported Transfer 
        #   Syntax(es) (Result value will be None)
        if self.requestor_contexts == []:
            raise ValueError("You can only set the Acceptor's presentation "
                    "contexts after the Requestor's")
        
        # Validate the supplied contexts
        self.__acceptor_contexts = []
        try:
            for ii in contexts:
                if isinstance(ii, PresentationContext):
                    self.__acceptor_contexts.append(ii)
        except:
            raise ValueError("acceptor_contexts must be a list of "
                    "PresentationContext items")
                    
        # Generate accepted_contexts and rejected_contexts
        self.accepted = []
        self.rejected = []
        if self.__acceptor_contexts != [] and self.__requestor_contexts != []:
            # For each of the contexts available to the acceptor
            for ii_req in self.__requestor_contexts:
                
                # Get the acceptor context with the same AbstractSyntax as 
                #   the requestor context
                acc_context = None
                for ii_acc in self.__acceptor_contexts:
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
