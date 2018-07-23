"""Implementation of the Presentation service."""
from collections import namedtuple
import logging

from pydicom.uid import (
    UID,
    ImplicitVRLittleEndian,
    ExplicitVRLittleEndian,
    ExplicitVRBigEndian
)

LOGGER = logging.getLogger('pynetdicom3.presentation')

# The default transfer syntaxes used when creating Presentation Contexts
DEFAULT_TRANSFER_SYNTAXES = [
    ImplicitVRLittleEndian,
    ExplicitVRLittleEndian,
    ExplicitVRBigEndian,
]


# Used with the on_c_* callbacks to give the users access to the context
PresentationContextTuple = namedtuple('PresentationContextTuple',
                                      ['context_id',
                                       'abstract_syntax',
                                       'transfer_syntax'])


class PresentationContext(object):
    """A Presentation Context primitive.

    **Rules**

    - Each Presentation Context (request) contains:

      - One context ID, an odd integer between 1 and 255.
      - One abstract syntax.
      - One or more transfer syntaxes.
    - Each Presentation Context (response) contains:

      - One context ID, corresponding to a Presentation Context received from
        the Requestor
      - A result, one of 0x00 (acceptance), 0x01 (user rejection), 0x02
        (provider rejection), 0x03 (abstract syntax not supported) or 0x04
        (transfer syntaxes not supported).
      - If the result is 0x00, then a transfer syntax.
      - If any other result, then a transfer syntax may or may not be present.
    - If the result is not 0x00 then the transfer syntax in the reply is not
      significant.
    - The same abstract syntax can be present in more than one Presententation
      Context.
    - Only one transfer syntax can be accepted per Presentation Context.
    - The Presentation Contexts may be sent by the Requestor in any order.
    - The Presentation Contexts may be sent by the Acceptor in any order.

    Attributes
    ---------
    abstract_syntax : pydicom.uid.UID or None
        The Presentation Context's *Abstract Syntax*.
    context_id : int or None
        The Presentation Context's *Context ID*.
    result : int or None
        If part of an A-ASSOCIATE (request) then None. If part of an
        A-ASSOCIATE (response) then one of 0x00, 0x01, 0x02, 0x03, 0x04.
    transfer_syntax : list of pydicom.uid.UID
        The Presentation Context's *Transfer Syntax(es)*.

    References
    ----------

    * DICOM Standard, Part 7, Annexes
      `D.3.2 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_D.3.2>`_ and
      `D.3.3.4 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_D.3.3.4>`_
    * DICOM Standard, Part 8, Sections
      `9.3.2.2 <http://dicom.nema.org/medical/dicom/current/output/html/part08.html#sect_9.3.2.2>`_,
      `9.3.3.2 <http://dicom.nema.org/medical/dicom/current/output/html/part08.html#sect_9.3.3.2>`_ and
      `Annex B <http://dicom.nema.org/medical/dicom/current/output/html/part08.html#chapter_B>`_
    """
    def __init__(self):
        """Create a new PresentationContext."""
        self._context_id = None
        self._abstract_syntax = None
        self._transfer_syntax = []
        self.result = None

        # Used with SCP/SCU Role Selection negotiation
        self._scu_role = None
        self._scp_role = None

    @property
    def abstract_syntax(self):
        """Return the presentation context's *Abstract Syntax* as a UID.

        Returns
        -------
        pydicom.uid.UID
        """
        return self._abstract_syntax

    @abstract_syntax.setter
    def abstract_syntax(self, uid):
        """Set the presentation context's *Abstract Syntax*.

        Parameters
        ----------
        uid : str or bytes or pydicom.uid.UID
            The abstract syntax UIDs
        """
        if isinstance(uid, bytes):
            uid = UID(uid.decode('ascii'))
        elif isinstance(uid, str):
            uid = UID(uid)
        else:
            raise TypeError("'abstract_syntax' must be str or bytes or UID")

        if not uid.is_valid:
            LOGGER.warning("'abstract_syntax' set to a non-conformant UID")

        self._abstract_syntax = uid

    def add_transfer_syntax(self, syntax):
        """Append a transfer syntax to the presentation context.

        Parameters
        ----------
        syntax : pydicom.uid.UID, bytes or str
            The transfer syntax to add to the presentation context.
        """
        if isinstance(syntax, str):
            syntax = UID(syntax)
        elif isinstance(syntax, bytes):
            syntax = UID(syntax.decode('ascii'))
        else:
            LOGGER.error("Attempted to add an invalid transfer syntax")
            return

        # If the transfer syntax is rejected we may add an empty str
        if syntax not in self._transfer_syntax and syntax != '':
            if not syntax.is_valid:
                LOGGER.warning("A non-conformant UID has been added "
                               "to 'transfer_syntax'")
            if not syntax.is_private and not syntax.is_transfer_syntax:
                LOGGER.warning("A UID has been added to 'transfer_syntax' "
                               "that is not a transfer syntax")

            self._transfer_syntax.append(syntax)

    @property
    def as_tuple(self):
        """Return a namedtuple representation of the presentation context.

        Intended to be used when the result is 0x00 (accepted) as only the
        first transfer syntax item is returned in the tuple.

        Returns
        -------
        PresentationContextTuple
            A representation of an accepted presentation context.
        """
        return PresentationContextTuple(
            self.context_id, self.abstract_syntax, self.transfer_syntax[0]
        )

    @property
    def context_id(self):
        """Return the presentation context's *ID* parameter as an int."""
        return self._context_id

    @context_id.setter
    def context_id(self, value):
        """Set the presentation context's *ID* parameter.

        Parameters
        ----------
        value : int
            An odd integer between 1 and 255 (inclusive).
        """
        if value is not None and (not 1 <= value <= 255 or value % 2 == 0):
            raise ValueError("'context_id' must be an odd integer between 1 "
                             "and 255, inclusive")

        self._context_id = value

    def __eq__(self, other):
        """Return True if `self` is equal to `other`."""
        if self is other:
            return True

        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__

        return NotImplemented

    # Python 2: Classes defining __eq__ should flag themselves as unhashable
    __hash__ = None

    def __ne__(self, other):
        """Return True if `self` does not equal `other`."""
        return not self == other

    @property
    def status(self):
        """Return a descriptive str of the presentation context's *Result*.

        Returns
        -------
        str
            The string representation of the result.
        """
        if self.result is None:
            status = 'Pending'
        elif self.result == 0x00:
            status = 'Accepted'
        elif self.result == 0x01:
            status = 'User Rejected'
        elif self.result == 0x02:
            status = 'Provider Rejected'
        elif self.result == 0x03:
            status = 'Abstract Syntax Not Supported'
        elif self.result == 0x04:
            status = 'Transfer Syntax(es) Not Supported'
        else:
            status = 'Unknown'

        return status

    def __str__(self):
        """String representation of the Presentation Context."""
        s = ''
        if self.context_id is not None:
            s += 'ID: {0!s}\n'.format(self.context_id)

        if self.abstract_syntax is not None:
            s += 'Abstract Syntax: {0!s}\n'.format(self.abstract_syntax.name)

        s += 'Transfer Syntax(es):\n'
        for syntax in self.transfer_syntax[:-1]:
            s += '    ={0!s}\n'.format(syntax.name)
        s += '    ={0!s}'.format(self.transfer_syntax[-1].name)

        if self.result is not None:
            s += '\nResult: {0!s}'.format(self.status)

        return s

    @property
    def transfer_syntax(self):
        """Return the presentation context's *Transfer Syntaxes* as a list.

        Returns
        -------
        list of pydicom.uid.UID
            The transfer syntaxes.
        """
        return self._transfer_syntax

    @transfer_syntax.setter
    def transfer_syntax(self, syntaxes):
        """Set the presentation context's *Transfer Syntaxes*.

        Parameters
        ----------
        syntaxes : list of (str or bytes or pydicom.uid.UID)
            The transfer syntax UIDs to add to the Presentation Context.
        """
        if not isinstance(syntaxes, list):
            raise TypeError("'transfer_syntax' must be a list")

        self._transfer_syntax = []

        for syntax in syntaxes:
            self.add_transfer_syntax(syntax)


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

    **SCP/SCU Role Selection Negotiation**

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
            values for Context ID, Abstract Syntax and Transfer Syntax.
        ac_contexts : list of PresentationContext
            The Presentation Contexts supported by the local AE when acting
            as an Association acceptor. Each item has values for Context ID
            Abstract Syntax and Transfer Syntax.

        Returns
        -------
        result_contexts : list of PresentationContext
            The accepted presentation context items, each with a Result value
            a Context ID, an Abstract Syntax and one Transfer Syntax item.
            Items are sorted in increasing Context ID value.
        """
        result_contexts = []

        # No requestor presentation contexts
        if not rq_contexts:
            return result_contexts

        # Acceptor doesn't support any presentation contexts
        if not ac_contexts:
            for rq_context in rq_contexts:
                context = PresentationContext()
                context.context_id = rq_context.context_id
                context.abstract_syntax = rq_context.abstract_syntax
                context.transfer_syntax = [rq_context.transfer_syntax[0]]
                context.result = 0x03
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
            (cx.context_id, cx.abstract_syntax):cx for cx in rq_contexts
        }
        # Acceptor supported SOP Classes must be unique so we can use UID as
        #   the key
        acceptor_contexts = {cx.abstract_syntax:cx for cx in ac_contexts}

        for (cntx_id, ab_syntax) in requestor_contexts:
            # Convenience variable
            rq_context = requestor_contexts[(cntx_id, ab_syntax)]

            # Create a new PresentationContext item that will store the
            #   results of the negotiation
            context = PresentationContext()
            context.context_id = cntx_id
            context.abstract_syntax = ab_syntax

            # Check if the acceptor supports the Abstract Syntax
            if ab_syntax in acceptor_contexts:
                # Convenience variable
                ac_context = acceptor_contexts[ab_syntax]

                # Abstract syntax supported so check Transfer Syntax
                for tr_syntax in rq_context.transfer_syntax:

                    # If transfer syntax supported
                    if tr_syntax in ac_context.transfer_syntax:
                        context.transfer_syntax = [tr_syntax]
                        # Accept the presentation context
                        context.result = 0x00

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
                if context.result is None:
                    # Reject context - transfer syntax not supported
                    context.result = 0x04
                    context.transfer_syntax = [rq_context.transfer_syntax[0]]
                    result_contexts.append(context)
            else:
                # Reject context - abstract syntax not supported
                context.result = 0x03
                context.transfer_syntax = [rq_context.transfer_syntax[0]]
                result_contexts.append(context)

        # Sort by presentation context ID and return
        #   This isn't required by the DICOM Standard but its a nice thing to do
        return sorted(result_contexts, key=lambda x: x.context_id)

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
            List, with added Abstract Syntax value. Items are sorted in
            increasing Context ID value.
        """
        if not rq_contexts:
            raise ValueError('Requestor contexts are required')
        output = []

        # Create dicts, indexed by the presentation context ID
        requestor_contexts = {
            context.context_id:context for context in rq_contexts
        }
        acceptor_contexts = {
            context.context_id:context for context in ac_contexts
        }

        for context_id in requestor_contexts:
            # Convenience variable
            rq_context = requestor_contexts[context_id]

            context = PresentationContext()
            context.context_id = context_id
            context.abstract_syntax = rq_context.abstract_syntax

            if context_id in acceptor_contexts:
                # Convenience variable
                ac_context = acceptor_contexts[context_id]

                # Update with accepted values
                context.transfer_syntax = [ac_context.transfer_syntax[0]]
                context.result = ac_context.result

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
                context.transfer_syntax = [rq_context.transfer_syntax[0]]
                context.result = 0x02

            output.append(context)

        # Sort returned list by context ID
        return sorted(output, key=lambda x: x.context_id)


def _build_context(abstract, transfer=DEFAULT_TRANSFER_SYNTAXES):
    """Return a PresentationContext from `abstract` and `transfer`.

    Parameters
    ----------
    abstract : str or UID
        The abstract syntax UID.
    transfer : list of str/UID
        The transfer syntax UIDs.

    Returns
    -------
    presentation.PresentationContext
    """
    context = PresentationContext()
    context.abstract_syntax = abstract
    context.transfer_syntax = transfer
    return context


# Service specific pre-generated Presentation Contexts
VerificationPresentationContexts = [
    _build_context('1.2.840.10008.1.1')
]

StoragePresentationContexts = [
    _build_context('1.2.840.10008.5.1.4.1.1.1'),
    _build_context('1.2.840.10008.5.1.4.1.1.1.1'),
    _build_context('1.2.840.10008.5.1.4.1.1.1.1.1.1'),
    _build_context('1.2.840.10008.5.1.4.1.1.1.2'),
    _build_context('1.2.840.10008.5.1.4.1.1.1.2.1'),
    _build_context('1.2.840.10008.5.1.4.1.1.1.3'),
    _build_context('1.2.840.10008.5.1.1.4.1.1.3.1'),
    _build_context('1.2.840.10008.5.1.4.1.1.2'),
    _build_context('1.2.840.10008.5.1.4.1.1.2.1'),
    _build_context('1.2.840.10008.5.1.4.1.1.2.2'),
    _build_context('1.2.840.10008.5.1.4.1.1.3.1'),
    _build_context('1.2.840.10008.5.1.4.1.1.4'),
    _build_context('1.2.840.10008.5.1.4.1.1.4.1'),
    _build_context('1.2.840.10008.5.1.4.1.1.4.2'),
    _build_context('1.2.840.10008.5.1.4.1.1.4.3'),
    _build_context('1.2.840.10008.5.1.4.1.1.4.4'),
    _build_context('1.2.840.10008.5.1.4.1.1.6.1'),
    _build_context('1.2.840.10008.5.1.4.1.1.6.2'),
    _build_context('1.2.840.10008.5.1.4.1.1.7'),
    _build_context('1.2.840.10008.5.1.4.1.1.7.1'),
    _build_context('1.2.840.10008.5.1.4.1.1.7.2'),
    _build_context('1.2.840.10008.5.1.4.1.1.7.3'),
    _build_context('1.2.840.10008.5.1.4.1.1.7.4'),
    _build_context('1.2.840.10008.5.1.4.1.1.9.1.1'),
    _build_context('1.2.840.10008.5.1.4.1.1.9.1.2'),
    _build_context('1.2.840.10008.5.1.4.1.1.9.1.3'),
    _build_context('1.2.840.10008.5.1.4.1.1.9.2.1'),
    _build_context('1.2.840.10008.5.1.4.1.1.9.3.1'),
    _build_context('1.2.840.10008.5.1.4.1.1.9.4.1'),
    _build_context('1.2.840.10008.5.1.4.1.1.9.4.2'),
    _build_context('1.2.840.10008.5.1.4.1.1.9.5.1'),
    _build_context('1.2.840.10008.5.1.4.1.1.9.6.1'),
    _build_context('1.2.840.10008.5.1.4.1.1.11.1'),
    _build_context('1.2.840.10008.5.1.4.1.1.11.2'),
    _build_context('1.2.840.10008.5.1.4.1.1.11.3'),
    _build_context('1.2.840.10008.5.1.4.1.1.11.4'),
    _build_context('1.2.840.10008.5.1.4.1.1.11.5'),
    _build_context('1.2.840.10008.5.1.4.1.1.12.1'),
    _build_context('1.2.840.10008.5.1.4.1.1.12.1.1'),
    _build_context('1.2.840.10008.5.1.4.1.1.12.2'),
    _build_context('1.2.840.10008.5.1.4.1.1.12.2.1'),
    _build_context('1.2.840.10008.5.1.4.1.1.13.1.1'),
    _build_context('1.2.840.10008.5.1.4.1.1.13.1.2'),
    _build_context('1.2.840.10008.5.1.4.1.1.13.1.3'),
    _build_context('1.2.840.10008.5.1.4.1.1.13.1.4'),
    _build_context('1.2.840.10008.5.1.4.1.1.13.1.5'),
    _build_context('1.2.840.10008.5.1.4.1.1.14.1'),
    _build_context('1.2.840.10008.5.1.4.1.1.14.2'),
    _build_context('1.2.840.10008.5.1.4.1.1.20'),
    _build_context('1.2.840.10008.5.1.4.1.1.30'),
    _build_context('1.2.840.10008.5.1.4.1.1.66'),
    _build_context('1.2.840.10008.5.1.4.1.1.66.1'),
    _build_context('1.2.840.10008.5.1.4.1.1.66.2'),
    _build_context('1.2.840.10008.5.1.4.1.1.66.3'),
    _build_context('1.2.840.10008.5.1.4.1.1.66.4'),
    _build_context('1.2.840.10008.5.1.4.1.1.66.5'),
    _build_context('1.2.840.10008.5.1.4.1.1.67'),
    _build_context('1.2.840.10008.5.1.4.1.1.68.1'),
    _build_context('1.2.840.10008.5.1.4.1.1.68.2'),
    _build_context('1.2.840.10008.5.1.4.1.1.77.1.1'),
    _build_context('1.2.840.10008.5.1.4.1.1.77.1.1.1'),
    _build_context('1.2.840.10008.5.1.4.1.1.77.1.2'),
    _build_context('1.2.840.10008.5.1.4.1.1.77.1.2.1'),
    _build_context('1.2.840.10008.5.1.4.1.1.77.1.3'),
    _build_context('1.2.840.10008.5.1.4.1.1.77.1.4'),
    _build_context('1.2.840.10008.5.1.4.1.1.77.1.4.1'),
    _build_context('1.2.840.10008.5.1.4.1.1.77.1.5.1'),
    _build_context('1.2.840.10008.5.1.4.1.1.77.1.5.2'),
    _build_context('1.2.840.10008.5.1.4.1.1.77.1.5.3'),
    _build_context('1.2.840.10008.5.1.4.1.1.77.1.5.4'),
    _build_context('1.2.840.10008.5.1.4.1.1.77.1.5.5'),
    _build_context('1.2.840.10008.5.1.4.1.1.77.1.5.6'),
    _build_context('1.2.840.10008.5.1.4.1.1.77.1.6'),
    _build_context('1.2.840.10008.5.1.4.1.1.78.1'),
    _build_context('1.2.840.10008.5.1.4.1.1.78.2'),
    _build_context('1.2.840.10008.5.1.4.1.1.78.3'),
    _build_context('1.2.840.10008.5.1.4.1.1.78.4'),
    _build_context('1.2.840.10008.5.1.4.1.1.78.5'),
    _build_context('1.2.840.10008.5.1.4.1.1.78.6'),
    _build_context('1.2.840.10008.5.1.4.1.1.78.7'),
    _build_context('1.2.840.10008.5.1.4.1.1.78.8'),
    _build_context('1.2.840.10008.5.1.4.1.1.79.1'),
    _build_context('1.2.840.10008.5.1.4.1.1.80.1'),
    _build_context('1.2.840.10008.5.1.4.1.1.81.1'),
    _build_context('1.2.840.10008.5.1.4.1.1.82.1'),
    _build_context('1.2.840.10008.5.1.4.1.1.88.11'),
    _build_context('1.2.840.10008.5.1.4.1.1.88.22'),
    _build_context('1.2.840.10008.5.1.4.1.1.88.33'),
    _build_context('1.2.840.10008.5.1.4.1.1.88.34'),
    _build_context('1.2.840.10008.5.1.4.1.1.88.35'),
    _build_context('1.2.840.10008.5.1.4.1.1.88.40'),
    _build_context('1.2.840.10008.5.1.4.1.1.88.50'),
    _build_context('1.2.840.10008.5.1.4.1.1.88.59'),
    _build_context('1.2.840.10008.5.1.4.1.1.88.65'),
    _build_context('1.2.840.10008.5.1.4.1.1.88.67'),
    _build_context('1.2.840.10008.5.1.4.1.1.88.68'),
    _build_context('1.2.840.10008.5.1.4.1.1.88.69'),
    _build_context('1.2.840.10008.5.1.4.1.1.88.70'),
    _build_context('1.2.840.10008.5.1.4.1.1.104.1'),
    _build_context('1.2.840.10008.5.1.4.1.1.104.2'),
    _build_context('1.2.840.10008.5.1.4.1.1.128'),
    _build_context('1.2.840.10008.5.1.4.1.1.130'),
    _build_context('1.2.840.10008.5.1.4.1.1.128.1'),
    _build_context('1.2.840.10008.5.1.4.1.1.131'),
    _build_context('1.2.840.10008.5.1.4.1.1.481.1'),
    _build_context('1.2.840.10008.5.1.4.1.1.481.2'),
    _build_context('1.2.840.10008.5.1.4.1.1.481.3'),
    _build_context('1.2.840.10008.5.1.4.1.1.481.4'),
    _build_context('1.2.840.10008.5.1.4.1.1.481.5'),
    _build_context('1.2.840.10008.5.1.4.1.1.481.6'),
    _build_context('1.2.840.10008.5.1.4.1.1.481.7'),
    _build_context('1.2.840.10008.5.1.4.1.1.481.8'),
    _build_context('1.2.840.10008.5.1.4.1.1.481.9'),
    _build_context('1.2.840.10008.5.1.4.34.7'),
    _build_context('1.2.840.10008.5.1.4.43.1'),
    _build_context('1.2.840.10008.5.1.4.44.1'),
    _build_context('1.2.840.10008.5.1.4.45.1'),
]

QueryRetrievePresentationContexts = [
    _build_context('1.2.840.10008.5.1.4.1.2.1.1'),
    _build_context('1.2.840.10008.5.1.4.1.2.1.2'),
    _build_context('1.2.840.10008.5.1.4.1.2.1.3'),
    _build_context('1.2.840.10008.5.1.4.1.2.2.1'),
    _build_context('1.2.840.10008.5.1.4.1.2.2.2'),
    _build_context('1.2.840.10008.5.1.4.1.2.2.3'),
    _build_context('1.2.840.10008.5.1.4.1.2.3.1'),
    _build_context('1.2.840.10008.5.1.4.1.2.3.2'),
    _build_context('1.2.840.10008.5.1.4.1.2.3.3'),
]

BasicWorklistManagementPresentationContexts = [
    _build_context('1.2.840.10008.5.1.4.31'),
]
