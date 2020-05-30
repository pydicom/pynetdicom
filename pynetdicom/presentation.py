"""Implementation of the Presentation service."""

from collections import namedtuple
import logging

from pydicom.uid import UID

from pynetdicom._globals import DEFAULT_TRANSFER_SYNTAXES
from pynetdicom.sop_class import (
    _APPLICATION_EVENT_CLASSES,
    _BASIC_WORKLIST_CLASSES,
    _COLOR_PALETTE_CLASSES,
    _DEFINED_PROCEDURE_CLASSES,
    _DISPLAY_SYSTEM_CLASSES,
    _HANGING_PROTOCOL_CLASSES,
    _IMPLANT_TEMPLATE_CLASSES,
    _INSTANCE_AVAILABILITY_CLASSES,
    _MEDIA_CREATION_CLASSES,
    _MEDIA_STORAGE_CLASSES,
    _NON_PATIENT_OBJECT_CLASSES,
    _PRINT_MANAGEMENT_CLASSES,
    _PROCEDURE_STEP_CLASSES,
    _PROTOCOL_APPROVAL_CLASSES,
    _QR_CLASSES,
    _RELEVANT_PATIENT_QUERY_CLASSES,
    _RT_MACHINE_VERIFICATION_CLASSES,
    _STORAGE_CLASSES,
    _STORAGE_COMMITMENT_CLASSES,
    _SUBSTANCE_ADMINISTRATION_CLASSES,
    _UNIFIED_PROCEDURE_STEP_CLASSES,
    _VERIFICATION_CLASSES,
)
from pynetdicom.utils import validate_uid


LOGGER = logging.getLogger('pynetdicom.presentation')


# Used with the event handlers to give the users access to the context
PresentationContextTuple = namedtuple(
    'PresentationContextTuple',
    ['context_id', 'abstract_syntax', 'transfer_syntax']
)
""":func:`namedtuple<collections.namedtuple>` representation of an accepted
:class:`PresentationContext`.
"""


DEFAULT_ROLE = (True, False, False, True)
BOTH_SCU_SCP_ROLE = (True, True, True, True)
CONTEXT_REJECTED = (False, False, False, False)
INVERTED_ROLE = (False, True, True, False)
SCP_SCU_ROLES = {
    # (Requestor role, Acceptor role) : Outcome
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
        the *Requestor*
      - A result, one of ``0x00`` (acceptance), ``0x01`` (user rejection),
        ``0x02`` (provider rejection), ``0x03`` (abstract syntax not supported)
        or ``0x04`` (transfer syntaxes not supported).
      - If the result is ``0x00``, then a transfer syntax.
      - If any other result, then a transfer syntax may or may not be present.
    - If the result is not ``0x00`` then the transfer syntax in the reply is
      not significant.
    - The same abstract syntax can be present in more than one Presententation
      Context.
    - Only one transfer syntax can be accepted per Presentation Context.
    - The Presentation Contexts may be sent by the *Requestor* in any order.
    - The Presentation Contexts may be sent by the *Acceptor* in any order.

    **SCP/SCU Role Selection Negotiation**

    - If no role selection negotiation then the *Requestor* is SCU and the
      *Acceptor* is SCP
    - The association *Acceptor* cannot accept a role that has not been
      proposed (i.e. cannot return 1 when the proposed value is 0).
    - The association *Requestor* may be SCP only, SCU only or both SCU and
      SCP.

    +---------------------+---------------------+-------------------+----------+
    | Requestor           | Acceptor            | Outcome           | Notes    |
    +----------+----------+----------+----------+---------+---------+          |
    | scu_role | scp_role | scu_role | scp_role | Req.    | Acc.    |          |
    +==========+==========+==========+==========+=========+=========+==========+
    | N/A      | N/A      | N/A      | N/A      | SCU     | SCP     | Default  |
    +----------+----------+----------+----------+---------+---------+----------+
    | True     | True     | False    | False    | N/A     | N/A     | Rejected |
    |          |          |          +----------+---------+---------+----------+
    |          |          |          | True     | SCP     | SCU     |          |
    |          |          +----------+----------+---------+---------+----------+
    |          |          | True     | False    | SCU     | SCP     | Default  |
    |          |          |          +----------+---------+---------+----------+
    |          |          |          | True     | SCU/SCP | SCU/SCP |          |
    +----------+----------+----------+----------+---------+---------+----------+
    | True     | False    | False    | False    | N/A     | N/A     | Rejected |
    |          |          +----------+          +---------+---------+----------+
    |          |          | True     |          | SCU     | SCP     | Default  |
    +----------+----------+----------+----------+---------+---------+----------+
    | False    | True     | False    | False    | N/A     | N/A     | Rejected |
    |          |          |          +----------+---------+---------+----------+
    |          |          |          | True     | SCP     | SCU     |          |
    +----------+----------+----------+----------+---------+---------+----------+
    | False    | False    | False    | False    | N/A     | N/A     | Rejected |
    +----------+----------+----------+----------+---------+---------+----------+

    As can be seen from the above table there are four possible outcomes:

    * *Requestor* is SCU, *Acceptor* is SCP (default roles)
    * *Requestor* is SCP, *Acceptor* is SCU
    * *Requestor* and *Acceptor* are both SCU/SCP
    * *Requestor* and *Acceptor* are neither (context rejected)

    Attributes
    ---------
    abstract_syntax : pydicom.uid.UID or None
        The context's *Abstract Syntax*.
    as_scp : bool or None
        If ``True`` then the association *Acceptor* can act as SCP for the
        current context, otherwise it cannot. A non-``None`` value is only
        available after association negotiation has been completed.
    as_scu : bool or None
        If ``True`` then the association *Acceptor* can act as SCU for the
        current context, otherwise it cannot. A non-``None`` value is only
        available after association negotiation has been completed.
    context_id : int or None
        The context's *Context ID*.
    result : int or None
        If part of an A-ASSOCIATE (request) then ``None``. If part of an
        A-ASSOCIATE (response) then one of ``0x00``, ``0x01``, ``0x02``,
        ``0x03``, ``0x04``.
    scp_role : bool or None
        Only used when acting as an association *Acceptor*. If ``True``
        then accept when the SCP role is proposed by the *Requestor*, otherwise
        reject the proposal. If ``None`` (default) then no SCP/SCU Role
        Selection reply will be sent and the default roles will be used.
    scu_role : bool
        Only used when acting as an association *Acceptor*. If ``True``
        then accept when the SCU role is proposed by the *Requestor*, otherwise
        reject the proposal. If ``None`` (default) then no SCP/SCU Role
        Selection reply will be sent and the default roles will be used.
    transfer_syntax : list of pydicom.uid.UID
        The context's *Transfer Syntax(es)*.

    References
    ----------

    * DICOM Standard, Part 7, Annexes :dcm:`D.3.2<part07.html#sect_D.3.2>`
      and :dcm:`D.3.3.4<part07.html#sect_D.3.3.4>`
    * DICOM Standard, Part 8, Sections :dcm:`9.3.2.2
      <part08.html#sect_9.3.2.2>`, :dcm:`9.3.3.2 <part08.html#sect_9.3.3.2>`
      and :dcm:`Annex B <part08.html#chapter_B>`
    """
    def __init__(self):
        """Create a new object."""
        self._context_id = None
        self._abstract_syntax = None
        self._transfer_syntax = []
        self.result = None

        # Used with SCP/SCU Role Selection negotiation
        self._scu_role = None
        self._scp_role = None

        # Used to track the allowed use of the context
        self._as_scp = None
        self._as_scu = None

    @property
    def abstract_syntax(self):
        """Return the context's *Abstract Syntax* as :class:`~pydicom.uid.UID`.

        Returns
        -------
        pydicom.uid.UID
        """
        return self._abstract_syntax

    @abstract_syntax.setter
    def abstract_syntax(self, uid):
        """Set the context's *Abstract Syntax*.

        Parameters
        ----------
        uid : str or bytes or pydicom.uid.UID
            The abstract syntax UID.
        """
        if isinstance(uid, bytes):
            uid = UID(uid.decode('ascii'))
        elif isinstance(uid, str):
            uid = UID(uid)
        else:
            raise TypeError("'abstract_syntax' must be str or bytes or UID")

        if not validate_uid(uid):
            LOGGER.error("'abstract_syntax' is an invalid UID")
            raise ValueError("'abstract_syntax' is an invalid UID")

        if uid and not uid.is_valid:
            LOGGER.warning(
                "The Abstract Syntax Name '{}' is non-conformant".format(uid)
            )

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
            if syntax is not None:
                LOGGER.error("Attempted to add an invalid transfer syntax")

            return

        if syntax is not None and not validate_uid(syntax):
            LOGGER.error("'transfer_syntax' contains an invalid UID")
            raise ValueError("'transfer_syntax' contains an invalid UID")

        if syntax and not syntax.is_valid:
            LOGGER.warning(
                "The Transfer Syntax Name '{}' is non-conformant"
                .format(syntax)
            )

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
        """Return ``True`` if can act as an SCP for the context."""
        return self._as_scp

    @property
    def as_scu(self):
        """Return ``True`` if can act as an SCU for the context."""
        return self._as_scu

    @property
    def as_tuple(self):
        """Return a :func:`namedtuple<collections.namedtuple>` representation
        of the presentation context.

        Intended to be used when the result is ``0x00`` (accepted) as only the
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
        """Return the context's *ID* parameter as an :class:`int`."""
        return self._context_id

    @context_id.setter
    def context_id(self, value):
        """Set the context's *ID* parameter.

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
        """Return ``True`` if `self` is equal to `other`."""
        if self is other:
            return True

        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__

        return NotImplemented

    def __hash__(self):
        """Return a hash of the context."""
        return hash((
            self.abstract_syntax,
            self.context_id,
            tuple(self.transfer_syntax),
            self.as_scp,
            self.as_scu
        ))

    def __ne__(self, other):
        """Return ``True`` if `self` does not equal `other`."""
        return not self == other

    def __repr__(self):
        """Representation of the Presentation Context."""
        return self.abstract_syntax.name

    @property
    def scp_role(self):
        """Return ``True`` if a proposed SCP role will be accepted."""
        return self._scp_role

    @scp_role.setter
    def scp_role(self, val):
        """Set whether to accept the proposed SCP role (as *Acceptor*).

        Parameters
        ----------
        val : bool or None
            If ``True`` then accept if the association *Requestor* proposes
            the SCP role for itself, ``False`` to reject the proposal. If
            ``None`` (default) then no SCP/SCU Role Selection reply will be
            sent. If either of :attr:`scu_role` or :attr:`scp_role` is ``None``
            then both will assumed to be.
        """
        if not isinstance(val, (bool, type(None))):
            raise TypeError("`scp_role` must be a bool or None")

        self._scp_role = val

    @property
    def scu_role(self):
        """Return ``True`` if a proposed SCU role will be accepted."""
        return self._scu_role

    @scu_role.setter
    def scu_role(self, val):
        """Set whether to accept the proposed SCU role (as *Acceptor*).

        Parameters
        ----------
        val : bool or None
            If ``True`` then accept if the association *Requestor* proposes
            the SCU role for itself, ``False`` to reject the proposal. If
            ``None`` (default) then no SCP/SCU Role Selection reply will be
            sent. If either of :attr:`scu_role` or :attr:`scp_role` is ``None``
            then both will assumed to be.
        """
        if not isinstance(val, (bool, type(None))):
            raise TypeError("`scu_role` must be a bool or None")

        self._scu_role = val

    @property
    def status(self):
        """Return a descriptive :class:`str` of the context's *Result*.

        Returns
        -------
        str
            The string representation of the negotiated result.
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
        if self.transfer_syntax:
            s += '    ={0!s}'.format(self.transfer_syntax[-1].name)
        else:
            s += '    (none)'

        if self.result is not None:
            s += '\nResult: {0!s}'.format(self.status)

        if None not in (self.as_scu, self.as_scp):
            if self.as_scu and not self.as_scp:
                s += '\nRole: SCU only'
            elif self.as_scu and self.as_scp:
                s += '\nRole: SCU and SCP'
            elif not self.as_scu and self.as_scp:
                s += '\nRole: SCP only'
            else:
                s += '\nRole: (none)'

        return s

    @property
    def transfer_syntax(self):
        """Return the context's *Transfer Syntaxes* as a :class:`list`.

        Returns
        -------
        list of pydicom.uid.UID
            The context's transfer syntaxes.
        """
        return self._transfer_syntax

    @transfer_syntax.setter
    def transfer_syntax(self, syntaxes):
        """Set the context's *Transfer Syntaxes*.

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


def negotiate_as_acceptor(rq_contexts, ac_contexts, roles=None):
    """Process the Presentation Contexts as an Association *Acceptor*.

    Parameters
    ----------
    rq_contexts : list of PresentationContext
        The Presentation Contexts proposed by the peer. Each item has
        values for Context ID, Abstract Syntax and Transfer Syntax.
    ac_contexts : list of PresentationContext
        The Presentation Contexts supported by the local AE when acting
        as an Association *Acceptor*. Each item has values for Context ID,
        Abstract Syntax and Transfer Syntax.
    roles : dict or None
        If the *Requestor* has included one or more SCP/SCU Role Selection
        Negotiation items then this will be a :class:`dict` of
        ``{'SOP Class UID' : (SCU role, SCP role)}``, otherwise ``None``
        (default)

    Returns
    -------
    list of PresentationContext
        The accepted presentation context items, each with a Result value
        a Context ID, an Abstract Syntax and one Transfer Syntax item.
        Items are sorted in increasing Context ID value.
    list of SCP_SCU_RoleSelectionNegotiation
        If `roles` is not ``None`` then this is a :class:`list` of SCP/SCU Role
        Selection Negotiation items that can be sent back to the *Requestor*.
    """
    from pynetdicom.pdu_primitives import SCP_SCU_RoleSelectionNegotiation

    roles = roles or {}
    result_contexts = []
    reply_roles = {}

    # No requestor presentation contexts
    if not rq_contexts:
        return result_contexts, []

    # Acceptor doesn't support any presentation contexts
    if not ac_contexts:
        for rq_context in rq_contexts:
            context = PresentationContext()
            context.context_id = rq_context.context_id
            context.abstract_syntax = rq_context.abstract_syntax
            context.transfer_syntax = [rq_context.transfer_syntax[0]]
            context.result = 0x03
            result_contexts.append(context)
        return result_contexts, []

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
        context._as_scu = False
        context._as_scp = False

        # Check if the acceptor supports the Abstract Syntax
        if ab_syntax in acceptor_contexts:
            # Convenience variables
            ac_context = acceptor_contexts[ab_syntax]
            ac_roles = (ac_context.scu_role, ac_context.scp_role)
            try:
                rq_roles = roles[ab_syntax]
                has_role = True
            except KeyError:
                rq_roles = (None, None)
                has_role = False

            # Abstract syntax supported so check Transfer Syntax
            for tr_syntax in ac_context.transfer_syntax:
                # If transfer syntax supported then (provisionally) accept
                if tr_syntax in rq_context.transfer_syntax:
                    context.transfer_syntax = [tr_syntax]
                    context.result = 0x00
                    result_contexts.append(context)
                    break

            ## SCP/SCU Role Selection Negotiation
            #   Only for (provisionally) accepted contexts
            if context.result == 0x00:
                if None in ac_roles:
                    # Default roles
                    context._as_scu = False
                    context._as_scp = True
                    # If either ac.scu_role or ac.scp_role is None then
                    #   don't send an SCP/SCU negotiation reply
                    has_role = False
                else:
                    # Use a LUT to make changes to outcomes easier
                    #   also its much simpler than coding if/then branches
                    outcome = SCP_SCU_ROLES[rq_roles][ac_roles]
                    context._as_scu = outcome[2]
                    context._as_scp = outcome[3]

                # If can't act as either SCU nor SCP then reject the context
                if context.as_scu is False and context.as_scp is False:
                    # User rejection
                    context.result = 0x01

            # Need to check against None as 0x00 is a possible value
            if context.result is None:
                # Reject context - transfer syntax not supported
                context.result = 0x04
                context.transfer_syntax = [rq_context.transfer_syntax[0]]
                result_contexts.append(context)
            elif context.result == 0x00 and has_role:
                # Create new SCP/SCU Role Selection Negotiation item
                role = SCP_SCU_RoleSelectionNegotiation()
                role.sop_class_uid = context.abstract_syntax

                # Can't return 0x01 if proposed 0x00
                if rq_roles[0] is False:
                    role.scu_role = False
                else:
                    role.scu_role = ac_context.scu_role

                if rq_roles[1] is False:
                    role.scp_role = False
                else:
                    role.scp_role = ac_context.scp_role

                reply_roles[context.abstract_syntax] = role
        else:
            # Reject context - abstract syntax not supported
            context.result = 0x03
            context.transfer_syntax = [rq_context.transfer_syntax[0]]
            result_contexts.append(context)

    # Sort by presentation context ID
    #   This isn't required by the DICOM Standard but its a nice thing to do
    result_contexts = sorted(result_contexts, key=lambda x: x.context_id)

    # Sort role selection by abstract syntax, also not required but nice
    reply_roles = sorted(reply_roles.values(), key=lambda x: x.sop_class_uid)

    return result_contexts, reply_roles


def negotiate_as_requestor(rq_contexts, ac_contexts, roles=None):
    """Process the Presentation Contexts as an Association *Requestor*.

    The *Acceptor* has processed the *Requestor's* presentation context
    definition list and returned the results. We want to do two things:

    - Process the SCP/SCU Role Selection Negotiation items
    - Return a nice list of :class:`PresentationContext` with the Results and
      original Abstract Syntax values to make things easier to use.

    :class:`~pynetdicom.pdu_items.PresentationContextItemRQ`

    - Presentation context ID
    - Abstract Syntax: one
    - Transfer syntax: one or more

    :class:`~pynetdicom.pdu_items.PresentationContextItemAC`

    - Presentation context ID
    - Result: one of ``0x00``, ``0x01``, ``0x02``, ``0x03`` or ``0x04``
    - Transfer syntax: one, not to be tested if result is not ``0x00``

    Parameters
    ----------
    rq_contexts : list of PresentationContext
        The Presentation Contexts sent to the peer as the A-ASSOCIATE's
        Presentation Context Definition List.
    ac_contexts : list of PresentationContext
        The Presentation Contexts return by the peer as the A-ASSOCIATE's
        Presentation Context Definition Result List.
    roles : dict or None
        If the *Acceptor* has included one or more SCP/SCU Role Selection
        Negotiation items then this will be a :class:`dict` of
        ``{'SOP Class UID' : (SCU role, SCP role)}``, otherwise ``None``
        (default)

    Returns
    -------
    list of PresentationContext
        The contexts in the returned Presentation Context Definition Result
        List, with added Abstract Syntax value. Items are sorted in
        increasing Context ID value and the SCP/SCU roles are set as per
        the negotiated outcome.
    """
    roles = roles or {}

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
        # Ensure we always have a role set
        context._as_scu = False
        context._as_scp = False

        if context_id in acceptor_contexts:
            # Convenience variable
            ac_context = acceptor_contexts[context_id]

            # Update with accepted values
            if ac_context.transfer_syntax:
                context.transfer_syntax = [ac_context.transfer_syntax[0]]
            context.result = ac_context.result

            ## SCP/SCU Role Selection Negotiation
            rq_roles = (rq_context.scu_role, rq_context.scp_role)
            try:
                ac_roles = roles[context.abstract_syntax]
            except KeyError:
                ac_roles = (None, None)

            # Skip if context rejected or acceptor ignored proposal
            if ac_context.result == 0x00 and None not in ac_roles:
                outcome = SCP_SCU_ROLES[rq_roles][ac_roles]
                context._as_scu = outcome[0]
                context._as_scp = outcome[1]
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


def build_context(abstract_syntax, transfer_syntax=None):
    """Return a :class:`PresentationContext` built from the `abstract_syntax`.

    Parameters
    ----------
    abstract_syntax : str or UID or sop_class.SOPClass
        The :class:`~pydicom.uid.UID` or subclass of
        :class:`~pynetdicom.sop_class.SOPClass` instance to use as the abstract
        syntax.
    transfer_syntax : str/UID or list of str/UID
        The transfer syntax UID(s) to use (default:
        ``[Implicit VR Little Endian, Explicit VR Little Endian,
        Implicit VR Big Endian]``)

    Examples
    --------

    Specifying a presentation context with the default transfer syntaxes

    >>> from pynetdicom import build_context
    >>> context = build_context('1.2.840.10008.1.1')
    >>> print(context)
    Abstract Syntax: Verification SOP Class
    Transfer Syntax(es):
        =Implicit VR Little Endian
        =Explicit VR Little Endian
        =Explicit VR Big Endian

    Specifying the abstract syntax using a *pynetdicom*
    :class:`~pynetdicom.sop_class.SOPClass` instance and a single transfer
    syntax

    >>> from pynetdicom import build_context
    >>> from pynetdicom.sop_class import VerificationSOPClass
    >>> context = build_context(VerificationSOPClass, '1.2.840.10008.1.2')
    >>> print(context)
    Abstract Syntax: Verification SOP Class
    Transfer Syntax(es):
        =Implicit VR Little Endian

    Specifying multiple transfer syntaxes

    >>> from pydicom.uid import UID
    >>> from pynetdicom import build_context
    >>> context = build_context(
    ...     UID('1.2.840.10008.1.1'), ['1.2.840.10008.1.2', '1.2.840.10008.1.2.4.50']
    ... )
    >>> print(context)
    Abstract Syntax: Verification SOP Class
    Transfer Syntax(es):
        =Implicit VR Little Endian
        =JPEG Baseline (Process 1)

    Returns
    -------
    presentation.PresentationContext
    """
    if transfer_syntax is None:
        transfer_syntax = DEFAULT_TRANSFER_SYNTAXES

    abstract_syntax = UID(abstract_syntax)

    # Allow single transfer syntax values for convenience
    if isinstance(transfer_syntax, str):
        transfer_syntax = [transfer_syntax]

    context = PresentationContext()
    context.abstract_syntax = abstract_syntax
    context.transfer_syntax = transfer_syntax

    return context


def build_role(uid, scu_role=False, scp_role=False):
    """Return a SCP/SCU Role Selection Negotiation item.

    .. versionadded:: 1.2

    Parameters
    ----------
    uid : str or UID or sop_class.SOPClass
        The :class:`~pydicom.uid.UID` or subclass of
        :class:`~pynetdicom.sop_class.SOPClass` instance to use as the *SOP
        Class UID* parameter value.
    scu_role : bool, optional
        ``True`` to propose the SCU role for the *Requestor*, ``False``
        otherwise (default).
    scp_role : bool, optional
        ``True`` to propose the SCP role for the *Requestor*, ``False``
        otherwise (default).

    Returns
    -------
    pdu_primitives.SCP_SCU_RoleSelectionNegotiation
        The role selection item.
    """
    from pynetdicom.pdu_primitives import SCP_SCU_RoleSelectionNegotiation

    role = SCP_SCU_RoleSelectionNegotiation()
    role.sop_class_uid = uid
    role.scu_role = scu_role
    role.scp_role = scp_role
    return role


# Service specific pre-generated Presentation Contexts
# pylint: disable=line-too-long,invalid-name
ApplicationEventLoggingPresentationContexts = [
    build_context(uid) for uid in sorted(_APPLICATION_EVENT_CLASSES.values())
]
"""Pre-built presentation contexts for :dcm:`Application Event Logging<part04/chapter_P.html>`."""

BasicWorklistManagementPresentationContexts = [
    build_context(uid) for uid in sorted(_BASIC_WORKLIST_CLASSES.values())
]
"""Pre-built presentation contexts for :dcm:`Basic Worklist Management<part04/chapter_K.html>`."""

ColorPalettePresentationContexts = [
    build_context(uid) for uid in sorted(_COLOR_PALETTE_CLASSES.values())
]
"""Pre-built presentation contexts for :dcm:`Color Palette Query/Retrieve<part04/chapter_X.html>`."""

DefinedProcedureProtocolPresentationContexts = [
    build_context(uid) for uid in sorted(_DEFINED_PROCEDURE_CLASSES.values())
]
"""Pre-built presentation contexts for :dcm:`Defined Procedure Protocol Query/Retrieve<part04/chapter_HH.html>`."""

DisplaySystemPresentationContexts = [
    build_context(uid) for uid in sorted(_DISPLAY_SYSTEM_CLASSES.values())
]
"""Pre-built presentation contexts for :dcm:`Display System Management<part04/chapter_EE.html>`."""

HangingProtocolPresentationContexts = [
    build_context(uid) for uid in sorted(_HANGING_PROTOCOL_CLASSES.values())
]
"""Pre-built presentation contexts for :dcm:`Hanging Protocol Query/Retrieve<part04/chapter_U.html>`."""

ImplantTemplatePresentationContexts = [
    build_context(uid) for uid in sorted(_IMPLANT_TEMPLATE_CLASSES.values())
]
"""Pre-built presentation contexts for :dcm:`Implant Template Query/Retrieve<part04/chapter_BB.html>`."""

InstanceAvailabilityPresentationContexts = [
    build_context(uid) for uid in sorted(_INSTANCE_AVAILABILITY_CLASSES.values())
]
"""Pre-built presentation contexts for :dcm:`Instance Availability Notification<part04/chapter_R.html>`."""

MediaCreationManagementPresentationContexts = [
    build_context(uid) for uid in sorted(_MEDIA_CREATION_CLASSES.values())
]
"""Pre-built presentation contexts for :dcm:`Media Creation Management<part04/chapter_S.html>`."""

MediaStoragePresentationContexts = [
    build_context(uid) for uid in sorted(_MEDIA_STORAGE_CLASSES.values())
]
"""Pre-built presentation contexts for :dcm:`Media Storage<part04/chapter_I.html>`."""

ModalityPerformedPresentationContexts = [
    build_context(uid) for uid in sorted(_PROCEDURE_STEP_CLASSES.values())
]
"""Pre-built presentation contexts for :dcm:`Modality Performed Procedure Step<part04/chapter_F.html>`."""

NonPatientObjectPresentationContexts = [
    build_context(uid) for uid in sorted(_NON_PATIENT_OBJECT_CLASSES.values())
]
"""Pre-built presentation contexts for :dcm:`Non-Patient Object Storage<part04/chapter_GG.html>`."""

PrintManagementPresentationContexts = [
    build_context(uid) for uid in sorted(_PRINT_MANAGEMENT_CLASSES.values())
]
"""Pre-built presentation contexts for :dcm:`Print Management<part04/chapter_H.html>`."""

ProcedureStepPresentationContexts = [
    build_context(uid) for uid in sorted(_PROCEDURE_STEP_CLASSES.values())
]
"""Pre-built presentation contexts for :dcm:`Procedure Step<part04/chapter_F.html>`."""

ProtocolApprovalPresentationContexts = [
    build_context(uid) for uid in sorted(_PROTOCOL_APPROVAL_CLASSES.values())
]
"""Pre-built presentation contexts for :dcm:`Protocol Approval Query/Retrieve<part04/chapter_II.html>`."""

QueryRetrievePresentationContexts = [
    build_context(uid) for uid in sorted(_QR_CLASSES.values())
]
"""Pre-built presentation contexts for :dcm:`Query/Retrieve<part04/chapter_C.html>`."""

RelevantPatientInformationPresentationContexts = [
    build_context(uid) for uid in sorted(_RELEVANT_PATIENT_QUERY_CLASSES.values())
]
"""Pre-built presentation contexts for :dcm:`Relevant Patient Information Query<part04/chapter_Q.html>`."""

RTMachineVerificationPresentationContexts = [
    build_context(uid) for uid in sorted(_RT_MACHINE_VERIFICATION_CLASSES.values())
]
"""Pre-built presentation contexts for :dcm:`RT Machine Verification<part04/chapter_DD.html>`."""

AllStoragePresentationContexts = [
    build_context(uid) for uid in sorted(_STORAGE_CLASSES.values())
]
"""Pre-built presentation contexts for :dcm:`Storage<part04/chapter_B.html>` containing all SOP Classes."""

StoragePresentationContexts = AllStoragePresentationContexts[:128]
"""Pre-built presentation contexts for :dcm:`Storage<part04/chapter_B.html>` containing the first 128 SOP Classes."""

StorageCommitmentPresentationContexts = [
    build_context(uid) for uid in sorted(_STORAGE_COMMITMENT_CLASSES.values())
]
"""Pre-built presentation contexts for :dcm:`Storage Commitment<part04/chapter_J.html>`."""

SubstanceAdministrationPresentationContexts = [
    build_context(uid) for uid in sorted(_SUBSTANCE_ADMINISTRATION_CLASSES.values())
]
"""Pre-built presentation contexts for :dcm:`Substance Administration Query<part04/chapter_V.html>`."""

UnifiedProcedurePresentationContexts = [
    build_context(uid) for uid in sorted(_UNIFIED_PROCEDURE_STEP_CLASSES.values())
]
"""Pre-built presentation contexts for :dcm:`Unified Procedure Step<part04/chapter_CC.html>`."""

VerificationPresentationContexts = [
    build_context(uid) for uid in sorted(_VERIFICATION_CLASSES.values())
]
"""Pre-built presentation contexts for :dcm:`Verification<part04/chapter_A.html>`."""
