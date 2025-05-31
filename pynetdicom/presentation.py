"""Implementation of the Presentation service."""

import logging
from typing import Any, TYPE_CHECKING, NamedTuple, cast

from pydicom.uid import UID

from pynetdicom._globals import DEFAULT_TRANSFER_SYNTAXES
from pynetdicom import sop_class as SOP_CLASS_MODULE
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
from pynetdicom.utils import validate_uid, set_uid

if TYPE_CHECKING:  # pragma: no cover
    from pynetdicom.pdu_primitives import SCP_SCU_RoleSelectionNegotiation


LOGGER = logging.getLogger(__name__)


# Used with the event handlers to give the users access to the context
class PresentationContextTuple(NamedTuple):
    """:func:`namedtuple<collections.namedtuple>` representation of an accepted
    :class:`PresentationContext`.
    """

    context_id: int
    abstract_syntax: UID
    transfer_syntax: UID


DEFAULT_ROLE = (True, False, False, True)
BOTH_SCU_SCP_ROLE = (True, True, True, True)
CONTEXT_REJECTED = (False, False, False, False)
INVERTED_ROLE = (False, True, True, False)
_RoleType = dict[
    tuple[bool | None, bool | None],
    dict[tuple[None | bool, None | bool], tuple[bool, bool, bool, bool]],
]
SCP_SCU_ROLES: _RoleType = {
    # (Requestor role, Acceptor role) : Outcome
    # No SCP/SCU Role Selection proposed
    (None, None): {
        (None, None): DEFAULT_ROLE,
        (None, True): DEFAULT_ROLE,
        (None, False): DEFAULT_ROLE,
        (True, None): DEFAULT_ROLE,
        (False, None): DEFAULT_ROLE,
        (True, True): DEFAULT_ROLE,
        (True, False): DEFAULT_ROLE,
        (False, False): DEFAULT_ROLE,
        (False, True): DEFAULT_ROLE,
    },
    (True, True): {
        (None, None): DEFAULT_ROLE,
        (None, True): DEFAULT_ROLE,
        (None, False): DEFAULT_ROLE,
        (True, None): DEFAULT_ROLE,
        (False, None): DEFAULT_ROLE,
        (True, True): BOTH_SCU_SCP_ROLE,
        (True, False): DEFAULT_ROLE,
        (False, False): CONTEXT_REJECTED,
        (False, True): INVERTED_ROLE,
    },
    (True, False): {
        (None, None): DEFAULT_ROLE,
        (None, True): DEFAULT_ROLE,
        (None, False): DEFAULT_ROLE,
        (True, None): DEFAULT_ROLE,
        (False, None): DEFAULT_ROLE,
        (True, True): DEFAULT_ROLE,  # Invalid
        (True, False): DEFAULT_ROLE,
        (False, False): CONTEXT_REJECTED,
        (False, True): CONTEXT_REJECTED,  # Invalid
    },
    (False, True): {
        (None, None): DEFAULT_ROLE,
        (None, True): DEFAULT_ROLE,
        (None, False): DEFAULT_ROLE,
        (True, None): DEFAULT_ROLE,
        (False, None): DEFAULT_ROLE,
        (True, True): INVERTED_ROLE,  # Invalid
        (True, False): CONTEXT_REJECTED,  # Invalid
        (False, False): CONTEXT_REJECTED,
        (False, True): INVERTED_ROLE,
    },
    # False, False proposed x
    (False, False): {
        (None, None): DEFAULT_ROLE,
        (None, True): DEFAULT_ROLE,
        (None, False): DEFAULT_ROLE,
        (True, None): DEFAULT_ROLE,
        (False, None): DEFAULT_ROLE,
        (True, True): CONTEXT_REJECTED,  # Invalid
        (True, False): CONTEXT_REJECTED,  # Invalid
        (False, False): CONTEXT_REJECTED,
        (False, True): CONTEXT_REJECTED,  # Invalid
    },
}
# Transfer Syntaxes not in pydicom v2.4
_PYDICOM_ADDITIONS = [
    "1.2.840.10008.1.2.4.201",  # HTJ2KLossless
    "1.2.840.10008.1.2.4.202",  # HTJ2KLosslessRPCL
    "1.2.840.10008.1.2.4.203",  # HTJ2K
    "1.2.840.10008.1.2.4.204",  # JPIPHTJ2KReferenced
    "1.2.840.10008.1.2.4.205",  # JPIPHTJ2KReferencedDeflate
]

class PresentationContext:
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

    +---------------------+---------------------+-------------------+---------+
    | Requestor           | Acceptor            | Outcome           | Notes   |
    +----------+----------+----------+----------+---------+---------+         |
    | scu_role | scp_role | scu_role | scp_role | Req.    | Acc.    |         |
    +==========+==========+==========+==========+=========+=========+=========+
    | N/A      | N/A      | N/A      | N/A      | SCU     | SCP     | Default |
    +----------+----------+----------+----------+---------+---------+---------+
    | True     | True     | False    | False    | N/A     | N/A     | Rejected|
    |          |          |          +----------+---------+---------+---------+
    |          |          |          | True     | SCP     | SCU     |         |
    |          |          +----------+----------+---------+---------+---------+
    |          |          | True     | False    | SCU     | SCP     | Default |
    |          |          |          +----------+---------+---------+---------+
    |          |          |          | True     | SCU/SCP | SCU/SCP |         |
    +----------+----------+----------+----------+---------+---------+---------+
    | True     | False    | False    | False    | N/A     | N/A     | Rejected|
    |          |          +----------+          +---------+---------+---------+
    |          |          | True     |          | SCU     | SCP     | Default |
    +----------+----------+----------+----------+---------+---------+---------+
    | False    | True     | False    | False    | N/A     | N/A     | Rejected|
    |          |          |          +----------+---------+---------+---------+
    |          |          |          | True     | SCP     | SCU     |         |
    +----------+----------+----------+----------+---------+---------+---------+
    | False    | False    | False    | False    | N/A     | N/A     | Rejected|
    +----------+----------+----------+----------+---------+---------+---------+

    As can be seen from the above table there are four possible outcomes:

    * *Requestor* is SCU, *Acceptor* is SCP (default roles)
    * *Requestor* is SCP, *Acceptor* is SCU
    * *Requestor* and *Acceptor* are both SCU/SCP
    * *Requestor* and *Acceptor* are neither (context rejected)

    Attributes
    ---------
    result : int or None
        If part of an A-ASSOCIATE (request) then ``None``. If part of an
        A-ASSOCIATE (response) then one of ``0x00``, ``0x01``, ``0x02``,
        ``0x03``, ``0x04``.

    References
    ----------

    * DICOM Standard, Part 7, Annexes :dcm:`D.3.2<part07.html#sect_D.3.2>`
      and :dcm:`D.3.3.4<part07.html#sect_D.3.3.4>`
    * DICOM Standard, Part 8, Sections :dcm:`9.3.2.2
      <part08.html#sect_9.3.2.2>`, :dcm:`9.3.3.2 <part08.html#sect_9.3.3.2>`
      and :dcm:`Annex B <part08.html#chapter_B>`
    """

    def __init__(self) -> None:
        """Create a new object."""
        self._context_id: None | int = None
        self._abstract_syntax: None | UID = None
        self._transfer_syntax: list[UID] = []
        self.result: None | int = None

        # Used with SCP/SCU Role Selection negotiation
        self._scu_role: None | bool = None
        self._scp_role: None | bool = None

        # Used to track the allowed use of the context
        self._as_scp: None | bool = None
        self._as_scu: None | bool = None

    @property
    def abstract_syntax(self) -> None | UID:
        """Get or set the context's *Abstract Syntax* as
        :class:`~pydicom.uid.UID`.

        Parameters
        ----------
        value : str or bytes or pydicom.uid.UID
            The abstract syntax UID.
        """
        return self._abstract_syntax

    @abstract_syntax.setter
    def abstract_syntax(self, value: str | bytes | UID | None) -> None:
        """Set the context's *Abstract Syntax*."""
        self._abstract_syntax = set_uid(value, "abstract_syntax", True, False, True)

    def add_transfer_syntax(self, syntax: None | str | bytes | UID) -> None:
        """Append a transfer syntax to the presentation context.

        Parameters
        ----------
        syntax : pydicom.uid.UID, bytes or str
            The transfer syntax to add to the presentation context.
        """
        if syntax is None:
            return

        if isinstance(syntax, str):  # includes UID
            syntax = UID(syntax)
        elif isinstance(syntax, bytes):
            syntax = UID(syntax.decode("ascii"))
        else:
            LOGGER.error("Attempted to add an invalid transfer syntax")
            return

        if syntax is not None and not validate_uid(syntax):
            LOGGER.error("'transfer_syntax' contains an invalid UID")
            raise ValueError("'transfer_syntax' contains an invalid UID")

        if syntax and not syntax.is_valid:
            LOGGER.warning(f"The Transfer Syntax Name '{syntax}' is non-conformant")

        # If the transfer syntax is rejected we may add an empty str
        if syntax not in self._transfer_syntax and syntax != "":
            if not syntax.is_valid:
                LOGGER.warning(
                    "A non-conformant UID has been added to 'transfer_syntax'"
                )

            if (
                not syntax.is_private
                and not syntax.is_transfer_syntax
                and syntax not in _PYDICOM_ADDITIONS
            ):
                LOGGER.warning(
                    "A UID has been added to 'transfer_syntax' that is not a "
                    f"transfer syntax: '{syntax}'"
                )

            self._transfer_syntax.append(syntax)

    @property
    def as_scp(self) -> None | bool:
        """Return ``True`` if can act as an SCP for the context.

        If ``True`` then the association *Acceptor* can act as SCP for the
        current context, otherwise it cannot. A non-``None`` value is only
        available after association negotiation has been completed.
        """
        return self._as_scp

    @property
    def as_scu(self) -> None | bool:
        """Return ``True`` if can act as an SCU for the context.

        If ``True`` then the association *Acceptor* can act as SCU for the
        current context, otherwise it cannot. A non-``None`` value is only
        available after association negotiation has been completed.
        """
        return self._as_scu

    @property
    def as_tuple(self) -> PresentationContextTuple:
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
            cast(int, self.context_id),
            cast(UID, self.abstract_syntax),
            self.transfer_syntax[0],
        )

    @property
    def context_id(self) -> None | int:
        """Return the context's *ID* parameter as an :class:`int`."""
        return self._context_id

    @context_id.setter
    def context_id(self, value: None | int) -> None:
        """Set the context's *ID* parameter.

        Parameters
        ----------
        value : int
            An odd integer between 1 and 255 (inclusive).
        """
        if value is not None and (not 1 <= value <= 255 or value % 2 == 0):
            raise ValueError(
                "'context_id' must be an odd integer between 1 and 255, inclusive"
            )

        self._context_id = value

    def __eq__(self, other: Any) -> bool:
        """Return ``True`` if `self` is equal to `other`."""
        if self is other:
            return True

        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__

        return NotImplemented

    def __hash__(self) -> int:
        """Return a hash of the context."""
        return hash(
            (
                self.abstract_syntax,
                self.context_id,
                tuple(self.transfer_syntax),
                self.as_scp,
                self.as_scu,
            )
        )

    def __ne__(self, other: Any) -> bool:
        """Return ``True`` if `self` does not equal `other`."""
        return not self == other

    def __repr__(self) -> str:
        """Representation of the Presentation Context."""
        return cast(UID, self.abstract_syntax).name

    @property
    def scp_role(self) -> None | bool:
        """Get or set if a proposed SCP role will be accepted.

        Parameters
        ----------
        val : bool or None
            If ``True`` then accept if the association *Requestor* proposes
            the SCP role for itself, ``False`` to reject the proposal. If
            ``None`` (default) then no SCP/SCU Role Selection reply will be
            sent. If either of :attr:`scu_role` or :attr:`scp_role` is ``None``
            then both will assumed to be.
        """
        return self._scp_role

    @scp_role.setter
    def scp_role(self, val: None | bool) -> None:
        """Set whether to accept the proposed SCP role (as *Acceptor*)."""
        if not isinstance(val, (bool, type(None))):
            raise TypeError("'scp_role' must be a bool or None")

        self._scp_role = val

    @property
    def scu_role(self) -> None | bool:
        """Get or set if a proposed SCU role will be accepted.

        Parameters
        ----------
        val : bool or None
            If ``True`` then accept if the association *Requestor* proposes
            the SCU role for itself, ``False`` to reject the proposal. If
            ``None`` (default) then no SCP/SCU Role Selection reply will be
            sent. If either of :attr:`scu_role` or :attr:`scp_role` is ``None``
            then both will assumed to be.
        """
        return self._scu_role

    @scu_role.setter
    def scu_role(self, val: None | bool) -> None:
        """Set whether to accept the proposed SCU role (as *Acceptor*)."""
        if not isinstance(val, (bool, type(None))):
            raise TypeError("'scu_role' must be a bool or None")

        self._scu_role = val

    @property
    def status(self) -> str:
        """Return a descriptive :class:`str` of the context's *Result*.

        Returns
        -------
        str
            The string representation of the negotiated result.
        """
        s = {
            None: "Pending",
            0x00: "Accepted",
            0x01: "User Rejected",
            0x02: "Provider Rejected",
            0x03: "Abstract Syntax Not Supported",
            0x04: "Transfer Syntax(es) Not Supported",
        }
        try:
            return s[self.result]
        except KeyError:
            return "Unknown"

    def __str__(self) -> str:
        """String representation of the Presentation Context."""
        s = []
        if self.context_id is not None:
            s.append(f"ID: {self.context_id}")

        if self.abstract_syntax is not None:
            s.append(f"Abstract Syntax: {self.abstract_syntax.name}")

        s.append("Transfer Syntax(es):")
        if not self.transfer_syntax:
            s.append("    (none)")
        else:
            s.extend(f"    ={ts.name}" for ts in self.transfer_syntax)

        if self.result is not None:
            s.append(f"Result: {self.status}")

        if None not in (self.as_scu, self.as_scp):
            if self.as_scu and not self.as_scp:
                s.append("Role: SCU only")
            elif self.as_scu and self.as_scp:
                s.append("Role: SCU and SCP")
            elif not self.as_scu and self.as_scp:
                s.append("Role: SCP only")
            else:
                s.append("Role: (none)")

        return "\n".join(s)

    @property
    def transfer_syntax(self) -> list[UID]:
        """Get or set the context's *Transfer Syntaxes* as a :class:`list`.

        Returns
        -------
        list of pydicom.uid.UID
            The context's transfer syntaxes.
        """
        return self._transfer_syntax

    @transfer_syntax.setter
    def transfer_syntax(self, syntaxes: list[str | bytes | UID]) -> None:
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


RoleType = None | dict[UID, tuple[None | bool, None | bool]]
ListCXType = list[PresentationContext]
CXNegotiationReturn = tuple[
    list[PresentationContext], list["SCP_SCU_RoleSelectionNegotiation"]
]


def negotiate_unrestricted(
    rq_contexts: ListCXType, ac_contexts: ListCXType, roles: RoleType = None
) -> CXNegotiationReturn:
    """Process the Presentation Contexts as an Association *Acceptor*
    with an unrestricted storage service.

    ..versionadded:: 2.0

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
    storage_contexts: list[PresentationContext] = []
    non_storage_contexts: list[PresentationContext] = []
    reply_roles: dict[UID, SCP_SCU_RoleSelectionNegotiation] = {}
    storage_uids = _STORAGE_CLASSES.values()

    # Split out private/unknown/storage cx's from everything else
    for cx in rq_contexts:
        ab_syntax = cast(UID, cx.abstract_syntax)
        if (
            ab_syntax.is_private
            or ab_syntax in storage_uids
            or not hasattr(SOP_CLASS_MODULE, ab_syntax.keyword)
        ):
            storage_contexts.append(cx)
        else:
            non_storage_contexts.append(cx)

    # Negotiate non-storage contexts as normal
    result_cx, result_roles = negotiate_as_acceptor(
        non_storage_contexts, ac_contexts, roles
    )

    # Accept all storage-like contexts
    for rcx in storage_contexts:
        cx = PresentationContext()
        cx.context_id = rcx.context_id
        cx.abstract_syntax = rcx.abstract_syntax
        cx.transfer_syntax = [rcx.transfer_syntax[0]]
        cx.result = 0x00
        cx._as_scu = True
        cx._as_scp = True

        # Role selection
        if rcx.abstract_syntax in roles:
            role = SCP_SCU_RoleSelectionNegotiation()
            role.sop_class_uid = rcx.abstract_syntax

            rq_roles = roles[rcx.abstract_syntax]
            outcome = SCP_SCU_ROLES[rq_roles][(True, True)]
            cx._as_scu = outcome[2]
            cx._as_scp = outcome[3]

            # Can't return 0x01 if proposed 0x00
            role.scu_role = False if not rq_roles[0] else True
            role.scp_role = False if not rq_roles[1] else True

            reply_roles[cast(UID, cx.abstract_syntax)] = role

        result_cx.append(cx)

    # Not required but a nice thing to do
    result_cx = sorted(result_cx, key=lambda x: cast(int, x.context_id))
    result_roles = sorted(
        reply_roles.values(), key=lambda x: cast(UID, x.sop_class_uid)
    )

    return result_cx, result_roles


def negotiate_as_acceptor(
    rq_contexts: ListCXType, ac_contexts: ListCXType, roles: RoleType = None
) -> CXNegotiationReturn:
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
    result_contexts: list[PresentationContext] = []
    reply_roles: dict[UID, SCP_SCU_RoleSelectionNegotiation] = {}

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
    requestor_contexts = {(cx.context_id, cx.abstract_syntax): cx for cx in rq_contexts}
    # Acceptor supported SOP Classes must be unique so we can use UID as
    #   the key
    acceptor_contexts = {cx.abstract_syntax: cx for cx in ac_contexts}

    for (cntx_id, ab_syntax), rq_context in requestor_contexts.items():
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
            ab_syntax = cast(UID, ab_syntax)
            ac_context = acceptor_contexts[ab_syntax]
            ac_roles = (ac_context.scu_role, ac_context.scp_role)
            rq_roles: tuple[None | bool, None | bool]
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

            # SCP/SCU Role Selection Negotiation
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

                reply_roles[cast(UID, context.abstract_syntax)] = role
        else:
            # Reject context - abstract syntax not supported
            context.result = 0x03
            context.transfer_syntax = [rq_context.transfer_syntax[0]]
            result_contexts.append(context)

    # Sort by presentation context ID
    #   This isn't required by the DICOM Standard but its a nice thing to do
    result_contexts = sorted(result_contexts, key=lambda x: cast(int, x.context_id))

    # Sort role selection by abstract syntax, also not required but nice
    result_roles = sorted(
        reply_roles.values(), key=lambda x: cast(UID, x.sop_class_uid)
    )

    return result_contexts, result_roles


def negotiate_as_requestor(
    rq_contexts: ListCXType, ac_contexts: ListCXType, roles: RoleType = None
) -> ListCXType:
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
        raise ValueError("Requestor contexts are required")
    output = []

    # Create dicts, indexed by the presentation context ID
    requestor_contexts = {context.context_id: context for context in rq_contexts}
    acceptor_contexts = {context.context_id: context for context in ac_contexts}

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

            # SCP/SCU Role Selection Negotiation
            rq_roles = (rq_context.scu_role, rq_context.scp_role)
            ac_roles: tuple[None | bool, None | bool]
            try:
                ac_roles = roles[cast(UID, context.abstract_syntax)]
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
    return sorted(output, key=lambda x: cast(int, x.context_id))


def build_context(
    abstract_syntax: str | UID,
    transfer_syntax: None | str | UID | list[str | UID] = None,
) -> PresentationContext:
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
        Deflated Explicit VR Little Endian, Implicit VR Big Endian]``)

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
        =Deflated Explicit VR Little Endian
        =Explicit VR Big Endian

    Specifying the abstract syntax using a *pynetdicom*
    :class:`~pynetdicom.sop_class.SOPClass` instance and a single transfer
    syntax

    >>> from pynetdicom import build_context
    >>> from pynetdicom.sop_class import Verification
    >>> context = build_context(Verification, '1.2.840.10008.1.2')
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
    context.transfer_syntax = transfer_syntax  # type: ignore

    return context


def build_role(
    uid: str | UID, scu_role: bool = False, scp_role: bool = False
) -> "SCP_SCU_RoleSelectionNegotiation":
    """Return a SCP/SCU Role Selection Negotiation item.

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
    role.sop_class_uid = UID(uid)
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

_storage = [
    "1.2.840.10008.5.1.4.1.1.9.1.3", # AmbulatoryECGWaveformStorage
    "1.2.840.10008.5.1.4.1.1.9.5.1", # ArterialPulseWaveformStorage
    "1.2.840.10008.5.1.4.1.1.78.2", # AutorefractionMeasurementsStorage
    "1.2.840.10008.5.1.4.1.1.131", # BasicStructuredDisplayStorage
    "1.2.840.10008.5.1.4.1.1.88.11", # BasicTextSRStorage
    "1.2.840.10008.5.1.4.1.1.9.4.1", # BasicVoiceAudioWaveformStorage
    "1.2.840.10008.5.1.4.1.1.11.4", # BlendingSoftcopyPresentationStateStorage
    "1.2.840.10008.5.1.4.1.1.13.1.3", # BreastTomosynthesisImageStorage
    "1.2.840.10008.5.1.4.1.1.9.3.1", # CardiacElectrophysiologyWaveformStorage
    "1.2.840.10008.5.1.4.1.1.88.65", # ChestCADSRStorage
    "1.2.840.10008.5.1.4.1.1.88.69", # ColonCADSRStorage
    "1.2.840.10008.5.1.4.1.1.11.2", # ColorSoftcopyPresentationStateStorage
    "1.2.840.10008.5.1.4.1.1.88.34", # Comprehensive3DSRStorage
    "1.2.840.10008.5.1.4.1.1.88.33", # ComprehensiveSRStorage
    "1.2.840.10008.5.1.4.1.1.1", # ComputedRadiographyImageStorage
    "1.2.840.10008.5.1.4.1.1.2", # CTImageStorage
    "1.2.840.10008.5.1.4.1.1.66.3", # DeformableSpatialRegistrationStorage
    "1.2.840.10008.5.1.4.1.1.1.3", # DigitalIntraOralXRayImageStorageForPresentation
    "1.2.840.10008.5.1.4.1.1.1.3.1", # DigitalIntraOralXRayImageStorageForProcessing
    "1.2.840.10008.5.1.4.1.1.1.2", # DigitalMammographyXRayImageStorageForPresentation
    "1.2.840.10008.5.1.4.1.1.1.2.1", # DigitalMammographyXRayImageStorageForProcessing
    "1.2.840.10008.5.1.4.1.1.1.1", # DigitalXRayImageStorageForPresentation
    "1.2.840.10008.5.1.4.1.1.1.1.1", # DigitalXRayImageStorageForProcessing
    "1.2.840.10008.5.1.4.1.1.104.2", # EncapsulatedCDAStorage
    "1.2.840.10008.5.1.4.1.1.104.1", # EncapsulatedPDFStorage
    "1.2.840.10008.5.1.4.1.1.2.1", # EnhancedCTImageStorage
    "1.2.840.10008.5.1.4.1.1.4.3", # EnhancedMRColorImageStorage
    "1.2.840.10008.5.1.4.1.1.4.1", # EnhancedMRImageStorage
    "1.2.840.10008.5.1.4.1.1.130", # EnhancedPETImageStorage
    "1.2.840.10008.5.1.4.1.1.88.22", # EnhancedSRStorage
    "1.2.840.10008.5.1.4.1.1.6.2", # EnhancedUSVolumeStorage
    "1.2.840.10008.5.1.4.1.1.12.1.1", # EnhancedXAImageStorage
    "1.2.840.10008.5.1.4.1.1.12.2.1", # EnhancedXRFImageStorage
    "1.2.840.10008.5.1.4.1.1.9.4.2", # GeneralAudioWaveformStorage
    "1.2.840.10008.5.1.4.1.1.9.1.2", # GeneralECGWaveformStorage
    "1.2.840.10008.5.1.4.1.1.11.1", # GrayscaleSoftcopyPresentationStateStorage
    "1.2.840.10008.5.1.4.1.1.9.2.1", # HemodynamicWaveformStorage
    "1.2.840.10008.5.1.4.1.1.88.70", # ImplantationPlanSRStorage
    "1.2.840.10008.5.1.4.1.1.78.8", # IntraocularLensCalculationsStorage
    "1.2.840.10008.5.1.4.1.1.14.1", # IntravascularOpticalCoherenceTomographyImageStorageForPresentation
    "1.2.840.10008.5.1.4.1.1.14.2", # IntravascularOpticalCoherenceTomographyImageStorageForProcessing
    "1.2.840.10008.5.1.4.1.1.78.3", # KeratometryMeasurementsStorage
    "1.2.840.10008.5.1.4.1.1.88.59", # KeyObjectSelectionDocumentStorage
    "1.2.840.10008.5.1.4.1.1.2.2", # LegacyConvertedEnhancedCTImageStorage
    "1.2.840.10008.5.1.4.1.1.4.4", # LegacyConvertedEnhancedMRImageStorage
    "1.2.840.10008.5.1.4.1.1.128.1", # LegacyConvertedEnhancedPETImageStorage
    "1.2.840.10008.5.1.4.1.1.78.1", # LensometryMeasurementsStorage
    "1.2.840.10008.5.1.4.1.1.79.1", # MacularGridThicknessAndVolumeReportStorage
    "1.2.840.10008.5.1.4.1.1.88.50", # MammographyCADSRStorage
    "1.2.840.10008.5.1.4.1.1.4", # MRImageStorage
    "1.2.840.10008.5.1.4.1.1.4.2", # MRSpectroscopyStorage
    "1.2.840.10008.5.1.4.1.1.7.2", # MultiframeGrayscaleByteSecondaryCaptureImageStorage
    "1.2.840.10008.5.1.4.1.1.7.3", # MultiframeGrayscaleWordSecondaryCaptureImageStorage
    "1.2.840.10008.5.1.4.1.1.7.1", # MultiframeSingleBitSecondaryCaptureImageStorage
    "1.2.840.10008.5.1.4.1.1.7.4", # MultiframeTrueColorSecondaryCaptureImageStorage
    "1.2.840.10008.5.1.4.1.1.20", # NuclearMedicineImageStorage
    "1.2.840.10008.5.1.4.1.1.78.7", # OphthalmicAxialMeasurementsStorage
    "1.2.840.10008.5.1.4.1.1.77.1.5.2", # OphthalmicPhotography16BitImageStorage
    "1.2.840.10008.5.1.4.1.1.77.1.5.1", # OphthalmicPhotography8BitImageStorage
    "1.2.840.10008.5.1.4.1.1.81.1", # OphthalmicThicknessMapStorage
    "1.2.840.10008.5.1.4.1.1.77.1.5.4", # OphthalmicTomographyImageStorage
    "1.2.840.10008.5.1.4.1.1.80.1", # OphthalmicVisualFieldStaticPerimetryMeasurementsStorage
    "1.2.840.10008.5.1.4.1.1.128", # PositronEmissionTomographyImageStorage
    "1.2.840.10008.5.1.4.1.1.88.40", # ProcedureLogStorage
    "1.2.840.10008.5.1.4.1.1.11.3", # PseudoColorSoftcopyPresentationStateStorage
    "1.2.840.10008.5.1.4.1.1.66", # RawDataStorage
    "1.2.840.10008.5.1.4.1.1.67", # RealWorldValueMappingStorage
    "1.2.840.10008.5.1.4.1.1.9.6.1", # RespiratoryWaveformStorage
    "1.2.840.10008.5.1.4.34.7", # RTBeamsDeliveryInstructionStorage
    "1.2.840.10008.5.1.4.1.1.481.4", # RTBeamsTreatmentRecordStorage
    "1.2.840.10008.5.1.4.1.1.481.6", # RTBrachyTreatmentRecordStorage
    "1.2.840.10008.5.1.4.1.1.481.2", # RTDoseStorage
    "1.2.840.10008.5.1.4.1.1.481.1", # RTImageStorage
    "1.2.840.10008.5.1.4.1.1.481.9", # RTIonBeamsTreatmentRecordStorage
    "1.2.840.10008.5.1.4.1.1.481.8", # RTIonPlanStorage
    "1.2.840.10008.5.1.4.1.1.481.5", # RTPlanStorage
    "1.2.840.10008.5.1.4.1.1.481.3", # RTStructureSetStorage
    "1.2.840.10008.5.1.4.1.1.481.7", # RTTreatmentSummaryRecordStorage
    "1.2.840.10008.5.1.4.1.1.7", # SecondaryCaptureImageStorage
    "1.2.840.10008.5.1.4.1.1.66.4", # SegmentationStorage
    "1.2.840.10008.5.1.4.1.1.66.2", # SpatialFiducialsStorage
    "1.2.840.10008.5.1.4.1.1.66.1", # SpatialRegistrationStorage
    "1.2.840.10008.5.1.4.1.1.78.6", # SpectaclePrescriptionReportStorage
    "1.2.840.10008.5.1.4.1.1.77.1.5.3", # StereometricRelationshipStorage
    "1.2.840.10008.5.1.4.1.1.78.4", # SubjectiveRefractionMeasurementsStorage
    "1.2.840.10008.5.1.4.1.1.68.1", # SurfaceScanMeshStorage
    "1.2.840.10008.5.1.4.1.1.68.2", # SurfaceScanPointCloudStorage
    "1.2.840.10008.5.1.4.1.1.66.5", # SurfaceSegmentationStorage
    "1.2.840.10008.5.1.4.1.1.9.1.1", # TwelveLeadECGWaveformStorage
    "1.2.840.10008.5.1.4.1.1.6.1", # UltrasoundImageStorage
    "1.2.840.10008.5.1.4.1.1.3.1", # UltrasoundMultiframeImageStorage
    "1.2.840.10008.5.1.4.1.1.77.1.1.1", # VideoEndoscopicImageStorage
    "1.2.840.10008.5.1.4.1.1.77.1.2.1", # VideoMicroscopicImageStorage
    "1.2.840.10008.5.1.4.1.1.77.1.4.1", # VideoPhotographicImageStorage
    "1.2.840.10008.5.1.4.1.1.78.5", # VisualAcuityMeasurementsStorage
    "1.2.840.10008.5.1.4.1.1.77.1.1", # VLEndoscopicImageStorage
    "1.2.840.10008.5.1.4.1.1.77.1.2", # VLMicroscopicImageStorage
    "1.2.840.10008.5.1.4.1.1.77.1.4", # VLPhotographicImageStorage
    "1.2.840.10008.5.1.4.1.1.77.1.3", # VLSlideCoordinatesMicroscopicImageStorage
    "1.2.840.10008.5.1.4.1.1.77.1.6", # VLWholeSlideMicroscopyImageStorage
    "1.2.840.10008.5.1.4.1.1.11.5", # XAXRFGrayscaleSoftcopyPresentationStateStorage
    "1.2.840.10008.5.1.4.1.1.13.1.1", # XRay3DAngiographicImageStorage
    "1.2.840.10008.5.1.4.1.1.13.1.2", # XRay3DCraniofacialImageStorage
    "1.2.840.10008.5.1.4.1.1.12.1", # XRayAngiographicImageStorage
    "1.2.840.10008.5.1.4.1.1.88.67", # XRayRadiationDoseSRStorage
    "1.2.840.10008.5.1.4.1.1.12.2", # XRayRadiofluoroscopicImageStorage
    ## retired but still in use
    "1.2.840.10008.5.1.1.30", # HardcopyColorImageStorage
    "1.2.840.10008.5.1.1.29", # HardcopyGrayscaleImageStorage
    "1.2.840.10008.5.1.4.1.1.5", # NuclearMedicineImageStorageRetired
    "1.2.840.10008.5.1.4.1.1.9", # StandaloneCurveStorage
    "1.2.840.10008.5.1.4.1.1.10", # StandaloneModalityLUTStorage
    "1.2.840.10008.5.1.4.1.1.8", # StandaloneOverlayStorage
    "1.2.840.10008.5.1.4.1.1.129", # StandalonePETCurveStorage
    "1.2.840.10008.5.1.4.1.1.11", # StandaloneVOILUTStorage
    "1.2.840.10008.5.1.1.27", # StoredPrintStorage
    "1.2.840.10008.5.1.4.1.1.6", # UltrasoundImageStorageRetired
    "1.2.840.10008.5.1.4.1.1.3", # UltrasoundMultiframeImageStorageRetired
    "1.2.840.10008.5.1.4.1.1.77.1", # VLImageStorage
    "1.2.840.10008.5.1.4.1.1.77.2", # VLMultiframeImageStorage
    "1.2.840.10008.5.1.4.1.1.12.3", # XRayAngiographicBiPlaneImageStorage
]
assert len(_storage) <= 120

StoragePresentationContexts = [build_context(uid) for uid in sorted(_storage)]
"""Pre-built presentation contexts for :dcm:`Storage<part04/chapter_B.html>` containing 120 selected SOP Classes."""

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
