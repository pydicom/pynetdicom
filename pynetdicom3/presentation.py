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


DEFAULT_ROLE = (True, False, False, True)
BOTH_SCU_SCP_ROLE = (True, True, True, True)
CONTEXT_REJECTED = (False, False, False, False)
INVERTED_ROLE = (False, True, True, False)

SCP_SCU_ROLES = {
    # Req role, ac role, Outcome
    # No SCP/SCU Role Selection proposed
    (None, None) : {
        (None, None) : DEFAULT_ROLE,
        (None, True) : DEFAULT_ROLE,
        (None, False) : DEFAULT_ROLE,
        (True, None) : DEFAULT_ROLE,
        (False, None) : DEFAULT_ROLE,
        (True, True) : DEFAULT_ROLE,
        (True, False) : DEFAULT_ROLE,
        (False, False) : DEFAULT_ROLE,
        (False, True) : DEFAULT_ROLE,
    },
    (True, True) : {
        (None, None) : DEFAULT_ROLE,
        (None, True) : DEFAULT_ROLE,
        (None, False) : DEFAULT_ROLE,
        (True, None) : DEFAULT_ROLE,
        (False, None) : DEFAULT_ROLE,
        (True, True) : BOTH_SCU_SCP_ROLE,
        (True, False) : DEFAULT_ROLE,
        (False, False) : CONTEXT_REJECTED,
        (False, True) : INVERTED_ROLE,
    },
    (True, False) : {
        (None, None) : DEFAULT_ROLE,
        (None, True) : DEFAULT_ROLE,
        (None, False) : DEFAULT_ROLE,
        (True, None) : DEFAULT_ROLE,
        (False, None) : DEFAULT_ROLE,
        (True, True) : DEFAULT_ROLE,  # Invalid
        (True, False) : DEFAULT_ROLE,
        (False, False) : CONTEXT_REJECTED,
        (False, True) : CONTEXT_REJECTED,  # Invalid
    },
    (False, True) : {
        (None, None) : DEFAULT_ROLE,
        (None, True) : DEFAULT_ROLE,
        (None, False) : DEFAULT_ROLE,
        (True, None) : DEFAULT_ROLE,
        (False, None) : DEFAULT_ROLE,
        (True, True) : INVERTED_ROLE,  # Invalid
        (True, False) : CONTEXT_REJECTED,  # Invalid
        (False, False) : CONTEXT_REJECTED,
        (False, True) : INVERTED_ROLE,
    },
    # False, False proposed x
    (False, False) : {
        (None, None) : DEFAULT_ROLE,
        (None, True) : DEFAULT_ROLE,
        (None, False) : DEFAULT_ROLE,
        (True, None) : DEFAULT_ROLE,
        (False, None) : DEFAULT_ROLE,
        (True, True) : CONTEXT_REJECTED,  # Invalid
        (True, False) : CONTEXT_REJECTED,  # Invalid
        (False, False) : CONTEXT_REJECTED,
        (False, True) : CONTEXT_REJECTED,  # Invalid
    },
}


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

    **SCP/SCU Role Selection Negotiation**

    - If no role selection negotiation then the requestor is SCU and the
      acceptor is SCP
    - If the proposed role is rejected then the roles default to requestor as
      SCU and acceptor as SCP
    - If the association requestor proposes the role value of 0 then that role
      shall be the default role.
    - The association acceptor cannot return accept a role that has not been
      proposed (i.e. cannot return 1 when the proposed value is 0).
    - The association requestor may be SCP only, SCU only or both SCU and SCP.

    +---------------------+---------------------+-------------------+----------+
    | Requestor           | Acceptor            | Outcome           | Notes    |
    +----------+----------+----------+----------+---------+---------+          |
    | SCU Role | SCP Role | SCU Role | SCP Role | Req.    | Acc.    |          |
    +==========+==========+==========+==========+=========+=========+==========+
    | N/A      | N/A      | N/A      | N/A      | SCU     | SCP     | Default  |
    +----------+----------+----------+----------+---------+---------+----------+
    | 0x01     | 0x01     | 0x00     | 0x00     | N/A     | N/A     | Rejected |
    |          |          |          +----------+---------+---------+----------+
    |          |          |          | 0x01     | SCP     | SCU     |          |
    |          |          +----------+----------+---------+---------+----------+
    |          |          | 0x01     | 0x00     | SCU     | SCP     | Default  |
    |          |          |          +----------+---------+---------+----------+
    |          |          |          | 0x01     | SCU/SCP | SCU/SCP |          |
    +----------+----------+----------+----------+---------+---------+----------+
    | 0x01     | 0x00     | 0x00     | 0x00     | N/A     | N/A     | Rejected |
    |          |          +----------+          +---------+---------+----------+
    |          |          | 0x01     |          | SCU     | SCP     | Default  |
    +----------+----------+----------+----------+---------+---------+----------+
    | 0x00     | 0x01     | 0x00     | 0x00     | N/A     | N/A     | Rejected |
    |          |          |          +----------+---------+---------+----------+
    |          |          |          | 0x01     | SCP     | SCU     |          |
    +----------+----------+----------+----------+---------+---------+----------+
    | 0x00     | 0x00     | 0x00     | 0x00     | N/A     | N/A     | Rejected |
    +----------+----------+----------+----------+---------+---------+----------+

    As can be seen from the above table there are four possible outcomes:

    * Requestor is SCU, acceptor is SCP (default roles)
    * Requestor is SCP, acceptor is SCU
    * Requestor and acceptor are both SCU/SCP
    * Requestor and acceptor are neither (context rejected)

    Attributes
    ---------
    abstract_syntax : pydicom.uid.UID or None
        The Presentation Context's *Abstract Syntax*.
    as_scp : bool or None
        If True then the association acceptor can act as SCP for the current
        context, otherwise it cannot. A non-None value is only available
        after association negotiation has been completed.
    as_scu : bool or None
        If True then the association acceptor can act as SCU for the current
        context, otherwise it cannot. A non-None value is only available
        after association negotiation has been completed.
    context_id : int or None
        The Presentation Context's *Context ID*.
    result : int or None
        If part of an A-ASSOCIATE (request) then None. If part of an
        A-ASSOCIATE (response) then one of 0x00, 0x01, 0x02, 0x03, 0x04.
    scp_role : bool or None
        Only used when acting as an association acceptor. If True (default)
        then accept when the SCP role is proposed by the requestor, otherwise
        reject the proposal. If None then no SCP/SCU Role Selection reply
        will be sent and the default roles will be used.
    scu_role : bool
        Only used when acting as an association acceptor. If True (default)
        then accept when the SCU role is proposed by the requestor, otherwise
        reject the proposal. If None then no SCP/SCU Role Selection reply
        will be sent and the default roles will be used.
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
        self._scu_role = True
        self._scp_role = True

        # Used to track the allowed use of the context
        self._as_scp = None
        self._as_scu = None

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
    def as_scp(self):
        """Return True if can act as an SCP for the context."""
        return self._as_scp

    @property
    def as_scu(self):
        """Return True if can act as an SCU for the context."""
        return self._as_scu

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
    def scp_role(self):
        """Return True if a proposed SCP role will be accepted."""
        return self._scp_role

    @scp_role.setter
    def scp_role(self, val):
        """Set whether to accept the proposed SCP role (as acceptor).

        Parameters
        ----------
        val : bool or None
            If True (default) then accept if the association requestor proposes
            the SCP role for itself, False to reject the proposal. If None
            then no SCP/SCU Role Selection reply will be sent. If either of
            `scu_role` or `scp_role` is None then both will assumed to be.
        """
        if not isinstance(val, (bool, type(None))):
            raise TypeError("`scp_role` must be a bool or None")

        self._scp_role = val

    @property
    def scu_role(self):
        """Return True if a proposed SCU role will be accepted."""
        return self._scu_role

    @scu_role.setter
    def scu_role(self, val):
        """Set whether to accept the proposed SCU role (as acceptor).

        Parameters
        ----------
        val : bool or None
            If True (default) then accept if the association requestor proposes
            the SCU role for itself, False to reject the proposal. If None
            then no SCP/SCU Role Selection reply will be sent. If either of
            `scu_role` or `scp_role` is None then both will assumed to be.
        """
        if not isinstance(val, (bool, type(None))):
            raise TypeError("`scu_role` must be a bool or None")

        self._scu_role = val

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

                        ## SCP/SCU Role Selection Negotiation
                        if None not in (ac_context.scp_role,
                                        ac_context.scu_role):
                            outcomes = SCP_SCU_ROLES[
                                (ac_context.scu_role, ac_context.scp_role)
                            ]
                            outcome = outcomes[
                                (rq_context.scu_role, rq_context.scp_role)
                            ]
                            context._as_scu = outcome[2]
                            context._as_scp = outcome[3]
                        else:
                            context._as_scu = False
                            context._as_scp = True

                        if not context.as_scu and not context.as_scp:
                            # Reject as no supported role
                            # No reason (provider rejection)
                            context.result = 0x02
                        else:
                            # Accept the presentation context
                            context.result = 0x00

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

                ## SCP/SCU Role Selection Negotiation
                # Skip if context rejected or acceptor ignored proposal
                if (ac_context.result == 0x00
                        and None not in (ac_context.scp_role, ac_context.scu_role)):
                    # Requestor has proposed SCP role for context:
                    #   acceptor agrees: use agreed role
                    #   acceptor disagrees: no role
                    if rq_context.scp_role == ac_context.scp_role:
                        context._as_scp = ac_context.scp_role

                    # Requestor has proposed SCU role for context:
                    #   acceptor agrees: use agreed role
                    #   acceptor disagrees: no role
                    if rq_context.scu_role == ac_context.scu_role:
                        context._as_scu = ac_context.scu_role
                else:
                    # We are the association requestor, so SCU role only
                    context._as_scp = False
                    context._as_scu = True

            # Add any missing contexts as rejected
            else:
                context.transfer_syntax = [rq_context.transfer_syntax[0]]
                context.result = 0x02

            output.append(context)

        # Sort returned list by context ID
        return sorted(output, key=lambda x: x.context_id)


def build_context(abstract_syntax, transfer_syntax=DEFAULT_TRANSFER_SYNTAXES):
    """Return a PresentationContext built from the `abstract_syntax`.

    Parameters
    ----------
    abstract_syntax : str or UID or sop_class.SOPClass
        The UID or SOPClass instance to use as the abstract syntax.
    transfer_syntax : str/UID or list of str/UID
        The transfer syntax UID(s) to use (default: [Implicit VR Little Endian,
        Explicit VR Little Endian, Implicit VR Big Endian])

    Examples
    --------

    Specifying a presentation context with the default transfer syntaxes

    >>> from pynetdicom3 import build_context
    >>> context = build_context('1.2.840.10008.1.1')
    >>> print(context)
    Abstract Syntax: Verification SOP Class
    Transfer Syntax(es):
        =Implicit VR Little Endian
        =Explicit VR Little Endian
        =Explicit VR Big Endian

    Specifying the abstract syntax using a pynetdicom SOPClass instance and
    a single transfer syntax

    >>> from pynetdicom3 import build_context
    >>> from pynetdicom3.sop_class import VerificationSOPClass
    >>> context = build_context(VerificationSOPClass, '1.2.840.10008.1.2')
    >>> print(context)
    Abstract Syntax: Verification SOP Class
    Transfer Syntax(es):
        =Implicit VR Little Endian

    Specifying multiple transfer syntaxes

    >>> from pydicom.uid import UID
    >>> from pynetdicom3 import build_context
    >>> context = build_context(UID('1.2.840.10008.1.1'),
                                ['1.2.840.10008.1.2', '1.2.840.10008.1.2.4.50'])
    >>> print(context)
    Abstract Syntax: Verification SOP Class
    Transfer Syntax(es):
        =Implicit VR Little Endian
        =JPEG Baseline (Process 1)


    Returns
    -------
    presentation.PresentationContext
    """
    if hasattr(abstract_syntax, 'uid'):
        abstract_syntax = UID(abstract_syntax.uid)
    else:
        abstract_syntax = UID(abstract_syntax)

    # Allow single transfer syntax values for convenience
    if isinstance(transfer_syntax, str):
        transfer_syntax = [transfer_syntax]

    context = PresentationContext()
    context.abstract_syntax = abstract_syntax
    context.transfer_syntax = transfer_syntax

    return context


# Service specific pre-generated Presentation Contexts
VerificationPresentationContexts = [
    build_context('1.2.840.10008.1.1')
]

StoragePresentationContexts = [
    build_context('1.2.840.10008.5.1.4.1.1.1'),
    build_context('1.2.840.10008.5.1.4.1.1.1.1'),
    build_context('1.2.840.10008.5.1.4.1.1.1.1.1.1'),
    build_context('1.2.840.10008.5.1.4.1.1.1.2'),
    build_context('1.2.840.10008.5.1.4.1.1.1.2.1'),
    build_context('1.2.840.10008.5.1.4.1.1.1.3'),
    build_context('1.2.840.10008.5.1.1.4.1.1.3.1'),
    build_context('1.2.840.10008.5.1.4.1.1.2'),
    build_context('1.2.840.10008.5.1.4.1.1.2.1'),
    build_context('1.2.840.10008.5.1.4.1.1.2.2'),
    build_context('1.2.840.10008.5.1.4.1.1.3.1'),
    build_context('1.2.840.10008.5.1.4.1.1.4'),
    build_context('1.2.840.10008.5.1.4.1.1.4.1'),
    build_context('1.2.840.10008.5.1.4.1.1.4.2'),
    build_context('1.2.840.10008.5.1.4.1.1.4.3'),
    build_context('1.2.840.10008.5.1.4.1.1.4.4'),
    build_context('1.2.840.10008.5.1.4.1.1.6.1'),
    build_context('1.2.840.10008.5.1.4.1.1.6.2'),
    build_context('1.2.840.10008.5.1.4.1.1.7'),
    build_context('1.2.840.10008.5.1.4.1.1.7.1'),
    build_context('1.2.840.10008.5.1.4.1.1.7.2'),
    build_context('1.2.840.10008.5.1.4.1.1.7.3'),
    build_context('1.2.840.10008.5.1.4.1.1.7.4'),
    build_context('1.2.840.10008.5.1.4.1.1.9.1.1'),
    build_context('1.2.840.10008.5.1.4.1.1.9.1.2'),
    build_context('1.2.840.10008.5.1.4.1.1.9.1.3'),
    build_context('1.2.840.10008.5.1.4.1.1.9.2.1'),
    build_context('1.2.840.10008.5.1.4.1.1.9.3.1'),
    build_context('1.2.840.10008.5.1.4.1.1.9.4.1'),
    build_context('1.2.840.10008.5.1.4.1.1.9.4.2'),
    build_context('1.2.840.10008.5.1.4.1.1.9.5.1'),
    build_context('1.2.840.10008.5.1.4.1.1.9.6.1'),
    build_context('1.2.840.10008.5.1.4.1.1.11.1'),
    build_context('1.2.840.10008.5.1.4.1.1.11.2'),
    build_context('1.2.840.10008.5.1.4.1.1.11.3'),
    build_context('1.2.840.10008.5.1.4.1.1.11.4'),
    build_context('1.2.840.10008.5.1.4.1.1.11.5'),
    build_context('1.2.840.10008.5.1.4.1.1.12.1'),
    build_context('1.2.840.10008.5.1.4.1.1.12.1.1'),
    build_context('1.2.840.10008.5.1.4.1.1.12.2'),
    build_context('1.2.840.10008.5.1.4.1.1.12.2.1'),
    build_context('1.2.840.10008.5.1.4.1.1.13.1.1'),
    build_context('1.2.840.10008.5.1.4.1.1.13.1.2'),
    build_context('1.2.840.10008.5.1.4.1.1.13.1.3'),
    build_context('1.2.840.10008.5.1.4.1.1.13.1.4'),
    build_context('1.2.840.10008.5.1.4.1.1.13.1.5'),
    build_context('1.2.840.10008.5.1.4.1.1.14.1'),
    build_context('1.2.840.10008.5.1.4.1.1.14.2'),
    build_context('1.2.840.10008.5.1.4.1.1.20'),
    build_context('1.2.840.10008.5.1.4.1.1.30'),
    build_context('1.2.840.10008.5.1.4.1.1.66'),
    build_context('1.2.840.10008.5.1.4.1.1.66.1'),
    build_context('1.2.840.10008.5.1.4.1.1.66.2'),
    build_context('1.2.840.10008.5.1.4.1.1.66.3'),
    build_context('1.2.840.10008.5.1.4.1.1.66.4'),
    build_context('1.2.840.10008.5.1.4.1.1.66.5'),
    build_context('1.2.840.10008.5.1.4.1.1.67'),
    build_context('1.2.840.10008.5.1.4.1.1.68.1'),
    build_context('1.2.840.10008.5.1.4.1.1.68.2'),
    build_context('1.2.840.10008.5.1.4.1.1.77.1.1'),
    build_context('1.2.840.10008.5.1.4.1.1.77.1.1.1'),
    build_context('1.2.840.10008.5.1.4.1.1.77.1.2'),
    build_context('1.2.840.10008.5.1.4.1.1.77.1.2.1'),
    build_context('1.2.840.10008.5.1.4.1.1.77.1.3'),
    build_context('1.2.840.10008.5.1.4.1.1.77.1.4'),
    build_context('1.2.840.10008.5.1.4.1.1.77.1.4.1'),
    build_context('1.2.840.10008.5.1.4.1.1.77.1.5.1'),
    build_context('1.2.840.10008.5.1.4.1.1.77.1.5.2'),
    build_context('1.2.840.10008.5.1.4.1.1.77.1.5.3'),
    build_context('1.2.840.10008.5.1.4.1.1.77.1.5.4'),
    build_context('1.2.840.10008.5.1.4.1.1.77.1.5.5'),
    build_context('1.2.840.10008.5.1.4.1.1.77.1.5.6'),
    build_context('1.2.840.10008.5.1.4.1.1.77.1.6'),
    build_context('1.2.840.10008.5.1.4.1.1.78.1'),
    build_context('1.2.840.10008.5.1.4.1.1.78.2'),
    build_context('1.2.840.10008.5.1.4.1.1.78.3'),
    build_context('1.2.840.10008.5.1.4.1.1.78.4'),
    build_context('1.2.840.10008.5.1.4.1.1.78.5'),
    build_context('1.2.840.10008.5.1.4.1.1.78.6'),
    build_context('1.2.840.10008.5.1.4.1.1.78.7'),
    build_context('1.2.840.10008.5.1.4.1.1.78.8'),
    build_context('1.2.840.10008.5.1.4.1.1.79.1'),
    build_context('1.2.840.10008.5.1.4.1.1.80.1'),
    build_context('1.2.840.10008.5.1.4.1.1.81.1'),
    build_context('1.2.840.10008.5.1.4.1.1.82.1'),
    build_context('1.2.840.10008.5.1.4.1.1.88.11'),
    build_context('1.2.840.10008.5.1.4.1.1.88.22'),
    build_context('1.2.840.10008.5.1.4.1.1.88.33'),
    build_context('1.2.840.10008.5.1.4.1.1.88.34'),
    build_context('1.2.840.10008.5.1.4.1.1.88.35'),
    build_context('1.2.840.10008.5.1.4.1.1.88.40'),
    build_context('1.2.840.10008.5.1.4.1.1.88.50'),
    build_context('1.2.840.10008.5.1.4.1.1.88.59'),
    build_context('1.2.840.10008.5.1.4.1.1.88.65'),
    build_context('1.2.840.10008.5.1.4.1.1.88.67'),
    build_context('1.2.840.10008.5.1.4.1.1.88.68'),
    build_context('1.2.840.10008.5.1.4.1.1.88.69'),
    build_context('1.2.840.10008.5.1.4.1.1.88.70'),
    build_context('1.2.840.10008.5.1.4.1.1.104.1'),
    build_context('1.2.840.10008.5.1.4.1.1.104.2'),
    build_context('1.2.840.10008.5.1.4.1.1.128'),
    build_context('1.2.840.10008.5.1.4.1.1.130'),
    build_context('1.2.840.10008.5.1.4.1.1.128.1'),
    build_context('1.2.840.10008.5.1.4.1.1.131'),
    build_context('1.2.840.10008.5.1.4.1.1.481.1'),
    build_context('1.2.840.10008.5.1.4.1.1.481.2'),
    build_context('1.2.840.10008.5.1.4.1.1.481.3'),
    build_context('1.2.840.10008.5.1.4.1.1.481.4'),
    build_context('1.2.840.10008.5.1.4.1.1.481.5'),
    build_context('1.2.840.10008.5.1.4.1.1.481.6'),
    build_context('1.2.840.10008.5.1.4.1.1.481.7'),
    build_context('1.2.840.10008.5.1.4.1.1.481.8'),
    build_context('1.2.840.10008.5.1.4.1.1.481.9'),
    build_context('1.2.840.10008.5.1.4.34.7'),
    build_context('1.2.840.10008.5.1.4.34.10'),
]

QueryRetrievePresentationContexts = [
    build_context('1.2.840.10008.5.1.4.1.2.1.1'),
    build_context('1.2.840.10008.5.1.4.1.2.1.2'),
    build_context('1.2.840.10008.5.1.4.1.2.1.3'),
    build_context('1.2.840.10008.5.1.4.1.2.2.1'),
    build_context('1.2.840.10008.5.1.4.1.2.2.2'),
    build_context('1.2.840.10008.5.1.4.1.2.2.3'),
    build_context('1.2.840.10008.5.1.4.1.2.3.1'),
    build_context('1.2.840.10008.5.1.4.1.2.3.2'),
    build_context('1.2.840.10008.5.1.4.1.2.3.3'),
    build_context('1.2.840.10008.5.1.4.1.2.4.2'),
    build_context('1.2.840.10008.5.1.4.1.2.4.3'),
    build_context('1.2.840.10008.5.1.4.1.2.5.3'),
]

BasicWorklistManagementPresentationContexts = [
    build_context('1.2.840.10008.5.1.4.31'),
]

RelevantPatientInformationPresentationContexts = [
    build_context('1.2.840.10008.5.1.4.37.1'),
    build_context('1.2.840.10008.5.1.4.37.2'),
    build_context('1.2.840.10008.5.1.4.37.3'),
]

SubstanceAdministrationPresentationContexts = [
    build_context('1.2.840.10008.5.1.4.41'),
    build_context('1.2.840.10008.5.1.4.42'),
]

NonPatientObjectPresentationContexts = [
    build_context('1.2.840.10008.5.1.4.38.1'),
    build_context('1.2.840.10008.5.1.4.39.1'),
    build_context('1.2.840.10008.5.1.4.43.1'),
    build_context('1.2.840.10008.5.1.4.44.1'),
    build_context('1.2.840.10008.5.1.4.45.1'),
    build_context('1.2.840.10008.5.1.4.1.1.200.1'),
    build_context('1.2.840.10008.5.1.4.1.1.200.3'),
]

HangingProtocolPresentationContexts = [
    build_context('1.2.840.10008.5.1.4.38.2'),
    build_context('1.2.840.10008.5.1.4.38.3'),
    build_context('1.2.840.10008.5.1.4.38.4'),
]

DefinedProcedureProtocolPresentationContexts = [
    build_context('1.2.840.10008.5.1.4.20.1'),
    build_context('1.2.840.10008.5.1.4.20.2'),
    build_context('1.2.840.10008.5.1.4.20.3'),
]

ColorPalettePresentationContexts = [
    build_context('1.2.840.10008.5.1.4.39.2'),
    build_context('1.2.840.10008.5.1.4.39.3'),
    build_context('1.2.840.10008.5.1.4.39.4'),
]

ImplantTemplatePresentationContexts = [
    build_context('1.2.840.10008.5.1.4.43.2'),
    build_context('1.2.840.10008.5.1.4.43.3'),
    build_context('1.2.840.10008.5.1.4.43.4'),
    build_context('1.2.840.10008.5.1.4.44.2'),
    build_context('1.2.840.10008.5.1.4.44.3'),
    build_context('1.2.840.10008.5.1.4.44.4'),
    build_context('1.2.840.10008.5.1.4.45.2'),
    build_context('1.2.840.10008.5.1.4.45.3'),
    build_context('1.2.840.10008.5.1.4.45.4'),
]

DisplaySystemPresentationContexts = [
    build_context('1.2.840.10008.5.1.1.40')
]
