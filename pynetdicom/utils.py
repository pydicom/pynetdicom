
from io import BytesIO

from pydicom.uid import UID

def wrap_list(lst, prefix='  ', delimiter='  ', items_per_line=16, max_size=None):
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
    def __init__(self, ID, abstract_syntax=None, transfer_syntaxes=[]):
        if 1 <= ID <= 255:
            if ID % 2 == 0:
                raise ValueError("Presentation Context ID must be an odd "
                                "integer between 1 and 255 inclusive")
        self.ID = ID
        
        if isinstance(abstract_syntax, bytes):
            abstract_syntax = UID(abstract_syntax.decode('utf-8'))
        
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
            
        return s
        
        
class AssociationInformation(object):
    """
    An interface helper for storing the Association information, namely
    the A-ASSOCIATE request and response primitives
    """
    def __init__(self, a_assoc_rq, a_assoc_ac):
        self.request_pdu = a_assoc_rq
        self.accept_pdu = a_assoc_ac
        self.max_pdu_local = None
        self.max_pdu_peer = None
        self.application_context_local = None
        self.accepted_presentation_contexts = []
        
        
    def _build_accepted_presentation_contexts(self):
        # Get accepted presentation contexts
        self.accepted_presentation_contexts = []
        for context in assoc_rsp.PresentationContextDefinitionResultList:
            # If result is 'Accepted'
            if context.Result == 0:
                # The accepted transfer syntax
                transfer_syntax = context.TransferSyntax[0]
                # The accepted Abstract Syntax 
                #   (taken from presentation_contexsts_scu)
                
                abstract_syntax = None
                for scu_context in pcdl:
                    if scu_context.ID == context.ID:
                        abstract_syntax = scu_context.AbstractSyntax
            
            # Create PresentationContext item
            accepted_context = PresentationContext(context.ID,
                                                   abstract_syntax,
                                                   transfer_syntax)
            
            # Add it to the list of accepted presentation contexts
            self.accepted_presentation_contexts.append(accepted_context)
