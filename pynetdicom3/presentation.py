"""Implementation of the Presentation service."""
import logging

from pydicom.uid import UID

LOGGER = logging.getLogger('pyndx.presentation')


class PresentationContext(object):
    """Representation of a single A-ASSOCIATE Presentation Context item.

    PS3.8 7.1.1
    An A-ASSOCIATE request primitive will contain a Presentation Context
    Definition List, which consists or one or more presentation contexts. Each
    item contains an ID, an Abstract Syntax and a list of one or more Transfer
    Syntaxes.

    An A-ASSOCIATE response primitive will contain a Presentation Context
    Definition Result List, which takes the form of a list of result values,
    with a one-to-one correspondence with the Presentation Context Definition
    List.

    A Presentation Context defines the presentation of the data on an
    Association. It consists of three components, a Presentation Context ID,
    an Abstract Syntax Name and a list or one or more Transfer Syntax Names.

    Only one Abstract Syntax shall be offered per Presentation Context. While
    multiple Transfer Syntaxes may be offered per Presentation Context only
    one shall be accepted.

    The same Abstract Syntax can be used in more than one Presentation Context.

    Rules
    -----
    - Each Presentation Context (request) contains:
      - One ID, an odd integer between 0 and 255
      - One Abstract Syntax
      - One or more Transfer Syntaxes
    - Each Presentation Context (response) contains:
      - One ID, corresponding to a Presentation Context received from the
        Requestor
      - A Result, one of 0x00, 0x01, 0x02, 0x03 or 0x04
      - A Transfer Syntax
    - If the Result is not 0x00 then the Transfer Syntax in the reply shall be
      ignored
    - The same Abstract Syntax can be present in more than one Presententation
      Context
    - Only one Transfer Syntax can be accepted per Presentation Context.
    - The Presentation Contexts may be sent by the Requestor in any order.
    - The Presentation Contexts may be sent by the Acceptor in any order.

    Attributes
    ----------
    ID : int
        The presentation context ID, must be an odd integer between 1 and 255,
        inclusive.
    AbstractSyntax : pydicom.uid.UID
        The abstract syntax
    TransferSyntax : list of pydicom.uid.UID
        The transfer syntax(es)
    SCU : bool or None
        If an Association acceptor:
        - True to accept a requestor SCP/SCU Role Selection proposal for the
          requestor to support the SCU role.to acting as an SCU for the current context
        - False to disallow the requestor acting as an SCU (the requestor and
          acceptor then revert to their default roles)
        - None to not perform SCP/SCU Role Negotation.
        If an Association requestor then you should add one or more
        SCP_SCU_RoleSelectionSubItem items to the User Information items. If
        that is the case then the following values will be set:
        - True if the requestor act as an SCU for the current context
        - False if the requestor not act as an SCU for the current
          context
        - None if no SCP_SCU_RoleSelectionSubItem has been added for the
          context's AbstractSyntax.
    SCP : bool or None
        If an Association acceptor:
        - True to allow requestor to acting as an SCP for the current context
        - False to disallow the requestor acting as an SCP (the requestor and
          acceptor then revert to their default roles)
        - None to not perform SCP/SCU Role Negotation.
        If an Association requestor then you should add one or more
        SCP_SCU_RoleSelectionSubItem items to the User Information items. If
        that is the case then the following values will be set:
        - True if the requestor act as an SCP for the current context
        - False if the requestor not act as an SCP for the current
          context
        - None if no SCP_SCU_RoleSelectionSubItem has been added for the
          context's AbstractSyntax.
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

    References
    ----------
    DICOM Standard, Part 7, Annex D.3.2, D.3.3.4
    """
    def __init__(self, ID=None, abstract_syntax=None, transfer_syntaxes=None):
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
        self.Result = None

        # Refactor, these should be private and used in conjunction with the
        # SOPClass.SCP and .SCU values
        self.SCU = None
        self.SCP = None

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
        if value is not None:
            # pylint: disable=attribute-defined-outside-init
            if not 1 <= value <= 255:
                raise ValueError("Presentation Context ID must be an odd "
                                 "integer between 1 and 255 inclusive")
            elif value % 2 == 0:
                raise ValueError("Presentation Context ID must be an odd "
                                 "integer between 1 and 255 inclusive")

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


class PresentationService(object):
    """Provides Presentation related services to the AE.

    For each SOP Class or Meta SOP Class, a Presentation Context must be
    negotiated such that this Presentation Context supports the associated
    Abstract Syntax and a suitable Transfer Syntax.

    * The Association requestor may off multiple Presentation Contexts per
    Association.
    * Each Presentation Context supports one Abstract Syntax and one or more
    Transfer Syntaxes.
    * The Association acceptor may accept or reject each Presentation Context
    individually.
    * The Association acceptor selects a suitable Transfer Syntax for each
    Presentation Context accepted.

    SCP/SCU Role Selection Negotiation
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    The SCP/SCU role selection negotiation allows peer AEs to negotiate the
    roles in which they will server for each SOP Class or Meta SOP Class
    supported on the Association. This negotiation is optional.

    The Association requestor, for each SOP Class UID or Meta SOP Class UID,
    may use one SCP/SCU Role Selection item, with the SOP Class or Meta SOP
    Class identified by its corresponding Abstract Syntax Name, followed by
    one of the three role values:
    * Association requestor is SCU only
    * Association requestor is SCP only
    * Association requestor is both SCU and SCP

    If the SCP/SCU Role Selection item is absent then the Association requestor
    shall be SCU and the Association acceptor shall be SCP.

    References
    ----------
    DICOM Standard, Part 7, Annex D.3
    """
    def __init__(self):
        pass

    @staticmethod
    def negotiate(assoc):
        """Process an Association's Presentation Contexts."""
        if assoc._mode == 'acceptor':
            self.negotiate_as_acceptor()
        elif assoc._mode == 'requestor':
            self.negotiate_as_requestor()

    @staticmethod
    def negotiate_as_acceptor(rq_contexts, ac_contexts):
        """Process the Presentation Contexts as an Association acceptor.

        Parameters
        ----------
        rq_contexts : list of PresentationContext
            The Presentation Contexts proposed by the peer. Each item has
            values for ID, AbstractSyntax and TransferSyntax. If the SCP/SCU
            Role Selection Negotiation item was included in the A-ASSOCIATE
            request then the PresentationContext.SCP and
            PresentationContext.SCU values will be either True (supports the
            role) or False (doesn't support the role).
        ac_contexts : list of PresentationContext
            The Presentation Contexts supported by the local AE when acting
            as an Association acceptor. Each item has values for
            AbstractSyntax and TransferSyntax. If Role Selection Negotiation
            is supported then the SCU and SCP values will also both be
            non-None.

        Returns
        -------
        result_contexts : list of PresentationContext
            The accepted presentation context items, each with a Result value
            an ID, an AbstractSyntax, one TransferSyntax item and SCP and SCU
            will also have values depending on the outcome of the SCP/SCU Role
            Selection negotiation. Items are sorted in increasing ID value.
        """
        result_contexts = []

        # No requestor presentation contexts
        if not rq_contexts:
            return result_contexts

        # Acceptor doesn't support any presentation contexts
        if not ac_contexts:
            for rq_context in rq_contexts:
                context = PresentationContext(rq_context.ID,
                                              rq_context.AbstractSyntax,
                                              [rq_context.TransferSyntax[0]])
                context.Result = 0x03
                result_contexts.append(context)
            return result_contexts

        # Optimisation notes (for iterating through contexts only, not
        #   including actual context negotiation)
        # - Create dict, use set intersection/difference of dict keys: ~600 us
        # - Create dict, iterate over dict keys: ~400 us
        # - Iterate over lists: ~52000 us

        # Requestor may use the same Abstract Syntax in multiple Presentation
        #   Contexts so we need a more specific key than UID
        requestor_contexts = {
            (cntx.ID, cntx.AbstractSyntax):cntx for cntx in rq_contexts
        }
        # Acceptor supported SOP Classes must be unique so we can use UID as
        #   the key
        acceptor_contexts = {cntx.AbstractSyntax:cntx for cntx in ac_contexts}

        for (cntx_id, ab_syntax) in requestor_contexts:
            # Convenience variable
            rq_context = requestor_contexts[(cntx_id, ab_syntax)]

            # Create a new PresentationContext item that will store the
            #   results of the negotiation
            context = PresentationContext(cntx_id, ab_syntax)

            # Check if the acceptor supports the Abstract Syntax
            if ab_syntax in acceptor_contexts:
                # Convenience variable
                ac_context = acceptor_contexts[ab_syntax]

                # Abstract syntax supported so check Transfer Syntax
                for tr_syntax in rq_context.TransferSyntax:

                    # If transfer syntax supported
                    if tr_syntax in ac_context.TransferSyntax:
                        context.TransferSyntax = [tr_syntax]
                        # Accept the presentation context
                        context.Result = 0x00

                        # SCP/SCU Role Selection needs to be reimplemented as it
                        #   doesn't meet the DICOM Standard
                        '''
                        ## SCP/SCU Role Selection Negotiation
                        # Only give an answer if the acceptor supports Role
                        #   Selection Negotiation (i.e. `ac_context.SCU` and
                        #   `ac_context.SCP` are not None)
                        if None not in (ac_context.SCP, ac_context.SCU):
                            # Requestor has proposed SCP role for context
                            if rq_context.SCP:
                                if ac_context.SCP:
                                    context.SCP = True
                                else:
                                    context.SCP = False

                            # Requestor has proposed SCU role for context
                            if rq_context.SCU:
                                if ac_context.SCU:
                                    context.SCU = True
                                else:
                                    context.SCU = False
                        '''

                        result_contexts.append(context)
                        break

                # Need to check against None as 0x00 is a possible value
                if context.Result is None:
                    # Reject context - transfer syntax not supported
                    context.Result = 0x04
                    context.TransferSyntax = [rq_context.TransferSyntax[0]]
                    result_contexts.append(context)
            else:
                # Reject context - abstract syntax not supported
                context.Result = 0x03
                context.TransferSyntax = [rq_context.TransferSyntax[0]]
                result_contexts.append(context)

        # Sort by presentation context ID and return
        #   This isn't required by the DICOM Standard but its a nice thing to do
        return sorted(result_contexts, key=lambda x: x.ID)

    @staticmethod
    def negotiate_as_requestor(rq_contexts, ac_contexts):
        """Process the Presentation Contexts as an Association requestor.

        The acceptor has processed the requestor's presentation context
        definition list and returned the results. We want to do two things:
        - Process the SCP/SCU Role Selection Negotiation (if any) (TO BE
          IMPLEMENTED)
        - Return a nice list of PresentationContexts with the Results and
          original Abstract Syntax values to make things easier to use.

        Presentation Context Item (RQ)
        - Presentation context ID
        - Abstract Syntax: one
        - Transfer syntax: one or more

        Presentation Context Item (AC)
        - Presentation context ID
        - Result: 0x00, 0x01, 0x02, 0x03, 0x04
        - Transfer syntax: one, not to be tested if result is not 0x00

        Parameters
        ----------
        rq_contexts : list of PresentationContext
            The Presentation Contexts sent to the peer as the A-ASSOCIATE's
            Presentation Context Definition List.
        ac_contexts : list of PresentationContext
            The Presentation Contexts return by the peer as the A-ASSOCIATE's
            Presentation Context Definition Result List.

        Returns
        -------
        list of PresentationContext
            The contexts in the returned Presentation Context Definition Result
            List, with added AbstractSyntax value and SCP/SCU Role Selection
            values (if used). Items are sorted in increasing ID value.
        """
        if not rq_contexts:
            raise ValueError('Requestor contexts are required')
        output = []

        # Create dicts, indexed by the presentation context ID
        requestor_contexts = {context.ID:context for context in rq_contexts}
        acceptor_contexts = {context.ID:context for context in ac_contexts}

        for context_id in requestor_contexts:
            # Convenience variable
            rq_context = requestor_contexts[context_id]

            context = PresentationContext(context_id,
                                          rq_context.AbstractSyntax)

            if context_id in acceptor_contexts:
                # Convenience variable
                ac_context = acceptor_contexts[context_id]

                # Update with accepted values
                context.TransferSyntax = [ac_context.TransferSyntax[0]]
                context.Result = ac_context.Result

                # SCP/SCU Role Selection needs to be reimplemented as it
                #   doesn't meet the DICOM Standard
                '''
                ## SCP/SCU Role Selection Negotiation
                # Skip if context rejected or acceptor ignored proposal
                if (ac_context.Result == 0x00
                            and None not in (ac_context.SCP, ac_context.SCU)):
                    # Requestor has proposed SCP role for context:
                    #   acceptor agrees: use agreed role
                    #   acceptor disagrees: use default role
                    if rq_context.SCP == ac_context.SCP:
                        context.SCP = ac_context.SCP
                    else:
                        context.SCP = False

                    # Requestor has proposed SCU role for context:
                    #   acceptor agrees: use agreed role
                    #   acceptor disagrees: use default role
                    if rq_context.SCU == ac_context.SCU:
                        context.SCU = ac_context.SCU
                    else:
                        context.SCU = False
                else:
                    # We are the association requestor, so SCU role only
                    context.SCP = False
                    context.SCU = True
                '''

            # Add any missing contexts as rejected
            else:
                context.TransferSyntax = [rq_context.TransferSyntax[0]]
                context.Result = 0x02

            output.append(context)

        # Sort returned list by context ID
        return sorted(output, key=lambda x: x.ID)
