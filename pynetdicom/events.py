"""Module used to support events and event handling, not to be confused with
the state machine events.
"""

from datetime import datetime
import logging

from pynetdicom.dsutils import decode


LOGGER = logging.getLogger('pynetdicom.events')


# Notification events
#   No returns/yields needed, can have multiple handlers per event
EVT_CONN_CLOSE = ("TRANSPORT", "Connection closed", False)  # OK
EVT_CONN_OPEN = ("TRANSPORT", "Connection opened", False)  # OK
EVT_DIMSE_RECV = ("DIMSE", "DIMSE message received", False)  # OK
EVT_DIMSE_SENT = ("DIMSE", "DIMSE message sent", False)  # OK
EVT_ACSE_RECV = ("ACSE", "ACSE message received", False)  # OK
EVT_ACSE_SENT = ("ACSE", "ACSE message sent", False)  # OK
EVT_ABORTED = ("ASSOCIATION", "Association aborted", False)
EVT_ACCEPTED = ("ASSOCIATION", "Association request accepted", False)  # OK
EVT_ESTABLISHED = ("ASSOCIATION", "Association established", False)  # OK
EVT_REJECTED = ("ASSOCIATION", "Association request rejected", False)  # OK
EVT_RELEASED = ("ASSOCIATION", "Association released", False)  # OK
EVT_REQUESTED = ("ASSOCIATION", "Association requested", False)
EVT_FSM_TRANSITION = ("DUL", "State machine transition occurred", False)  # OK
EVT_PDU_RECV = ("DUL", "PDU data received", False)  # OK
EVT_PDU_SENT = ("DUL", "PDU data sent", False)  # OK

# Intervention events
#   Returns/yields needed if bound, can only have one handler per event
EVT_ASYNC_OPS = ("ACSE", "Asynchronous operations negotiation requested", True)  # OK
EVT_SOP_COMMON = ("ACSE", "SOP class common extended negotiation requested", True)  # OK
EVT_SOP_EXTENDED = ("ACSE", "SOP class extended negotiation requested", True)  # OK
EVT_USER_ID = ("ACSE", "User identity negotiation requested", True)  # OK
EVT_C_ECHO = ("SERVICE", "C-ECHO request received", True)  # OK
EVT_C_FIND = ("SERVICE", "C-FIND request received", True)  # OK
EVT_C_GET = ("SERVICE", "C-GET request received", True)  # OK
EVT_C_MOVE = ("SERVICE", "C-MOVE request received", True)  # OK
EVT_C_STORE = ("SERVICE", "C-STORE request received", True)  # OK
EVT_N_ACTION = ("SERVICE", "N-ACTION request received", True)  # OK
EVT_N_CREATE = ("SERVICE", "N-CREATE request received", True)  # OK
EVT_N_DELETE = ("SERVICE", "N-DELETE request received", True)  # OK
EVT_N_EVENT_REPORT = ("SERVICE", "N-EVENT-REPORT request received", True)  # OK
EVT_N_GET = ("SERVICE", "N-GET request received", True)  # OK
EVT_N_SET = ("SERVICE", "N-SET request received", True)  # OK


_INTERVENTION_EVENTS = [
    EVT_ASYNC_OPS, EVT_SOP_COMMON, EVT_SOP_EXTENDED, EVT_USER_ID,
    EVT_C_ECHO, EVT_C_FIND, EVT_C_GET, EVT_C_MOVE, EVT_C_STORE,
    EVT_N_ACTION, EVT_N_CREATE, EVT_N_DELETE, EVT_N_EVENT_REPORT,
    EVT_N_GET, EVT_N_SET
]


def get_default_handler(event):
    """Get the default handler for an intervention `event`."""
    handlers = {
        EVT_ASYNC_OPS : default_async_ops_handler,
        EVT_SOP_COMMON : default_sop_common_handler,
        EVT_SOP_EXTENDED : default_sop_extended_handler,
        EVT_USER_ID : default_user_identity_handler,
        EVT_C_ECHO : default_c_echo_handler,
        EVT_C_FIND : default_c_find_handler,
        EVT_C_GET : default_c_get_handler,
        EVT_C_MOVE : default_c_move_handler,
        EVT_C_STORE : default_c_store_handler,
        EVT_N_ACTION : default_n_action_handler,
        EVT_N_CREATE : default_n_create_handler,
        EVT_N_DELETE : default_n_delete_handler,
        EVT_N_EVENT_REPORT : default_n_event_report_handler,
        EVT_N_GET : default_n_get_handler,
        EVT_N_SET : default_n_set_handler,
    }
    return handlers[event]


def trigger(assoc, event, attrs=None):
    """Trigger an `event` and call any bound handler(s).

    Notification events can be bound to multiple handlers, intervention events
    can only be bound to a single handler.

    **Intervention Events**

    * Service class requests: EVT_C_ECHO, EVT_C_FIND, EVT_C_GET, EVT_C_MOVE,
      EVT_C_STORE, EVT_N_ACTION, EVT_N_CREATE, EVT_N_DELETE,
      EVT_N_EVENT_REPORT, EVT_N_GET, EVT_N_SET
    * Association extended negotiation requests: EVT_ASYNC_OPS, EVT_SOP_COMMON,
      EVT_SOP_EXTENDED, EVT_USER_ID

    **Special Attributes**

    If `attrs` contains:

    * `_is_cancelled` key then ``Event.is_cancelled`` will be hooked into
      the value's callable function.
    * a C-STORE `request` key then ``Event.dataset`` will return the decoded
      *Data Set* parameter value.
    * a C-FIND, C-GET or C-MOVE `request` key then ``Event.identifier`` will
      return the decoded *Identifier* parameter value.
    * an N-ACTION `request` key then ``Event.action_reply`` will
      return the decoded *Action Reply* parameter value.
    * an N-EVENT-REPORT `request` key then ``Event.event_reply`` will
      return the decoded *Event Reply* parameter value.
    * an N-CREATE, N-GET or N-SET `request` key then ``Event.attribute_list``
      will return the decoded *Attribute List* parameter value.

    Parameters
    ----------
    assoc : assoc.Association
        The association in which the event occurred.
    event : 3-tuple
        The event to trigger ('source', 'description', is_interventional).
    attrs : dict, optional
        The attributes to set in the Event instance that is passed to
        the event's corresponding handler functions as
        {attribute name : value}, default {}.

    Raises
    ------
    Exception
        If an exception occurs in an intervention event handler then the
        exception will be raised. If an exception occurs in a notification
        handler then the exception will be caught and logged instead.
    """
    # Get the handler(s) bound to the event
    #   notification events: returns a list of callable
    #   intervention events: returns a callable or None
    handlers = assoc.get_handlers(event)
    if not handlers:
        return

    evt = Event(assoc, event, attrs)

    try:
        # Intervention event - only singule handler allowed
        if event[2]:
            return handlers(evt)

        # Notification event - multiple handlers are allowed
        for func in handlers:
            func(evt)
    except Exception as exc:
        # Intervention exceptions get raised
        if event[2]:
            raise

        # Capture exceptions for notification events
        LOGGER.error(
            "Exception raised in user's 'evt.{}' event handler '{}'"
            .format(event.__name__, func.__name__)
        )
        LOGGER.exception(exc)


class Event(object):
    """Representation of an event.

    Attributes
    ----------
    assoc : association.Association
        The association in which the event occurred.
    event : tuple
        The event that occurred.
    timestamp : datetime.datetime
        The date/time the event was created. Will be slightly before or after
        the actual event that this object represents.
    """
    def __init__(self, assoc, event, attrs):
        """Create a new Event.

        Parameters
        ----------
        assoc : association.Association
            The association in which the event occurred.
        event : tuple
            The representation of the event.
        attrs : dict
            The {attribute : value} to set for the Event.
        """
        self.assoc = assoc
        self.event = event
        self.timestamp = datetime.now()

        attrs = attrs or {}
        for kk, vv in attrs.items():
            setattr(self, kk, vv)

    @property
    def action_reply(self):
        """Return an N-ACTION request's `Action Reply` as a *pydicom* Dataset.

        Because *pydicom* defers data parsing during decoding until an element
        is actually required the returned ``Dataset`` may raise an exception
        when first used. It's therefore important that proper error handling
        be part of any handler bound to an event that includes a dataset.

        Returns
        -------
        pydicom.dataset.Dataset
            The decoded *Action Reply* dataset.

        Raises
        ------
        AttributeError
            If the corresponding event is not an N-ACTION request.
        """
        try:
            t_syntax = self.context.transfer_syntax
            ds = decode(self.request.ActionReply,
                        t_syntax.is_implicit_VR,
                        t_syntax.is_little_endian)
            return ds
        except AttributeError:
            pass

        raise AttributeError(
            "The corresponding event is not an N-ACTION request and has no "
            "'Action Reply' parameter"
        )

    @property
    def attribute_list(self):
        """Return an N-CREATE, N-GET or N-SET request's `Attribute List` as a
        *pydicom* Dataset.

        Because *pydicom* defers data parsing during decoding until an element
        is actually required the returned ``Dataset`` may raise an exception
        when first used. It's therefore important that proper error handling
        be part of any handler bound to an event that includes a dataset.

        Returns
        -------
        pydicom.dataset.Dataset
            The decoded *Attribute List* dataset.

        Raises
        ------
        AttributeError
            If the corresponding event is not an N-CREATE, N-GET or N-SET
            request.
        """
        try:
            t_syntax = self.context.transfer_syntax
            ds = decode(self.request.AttributeList,
                        t_syntax.is_implicit_VR,
                        t_syntax.is_little_endian)
            return ds
        except AttributeError:
            pass

        raise AttributeError(
            "The corresponding event is not an N-CREATE, N-GET or N-SET "
            "request and has no 'Attribute List' parameter"
        )

    @property
    def dataset(self):
        """Return a C-STORE request's `Data Set` as a *pydicom* Dataset.

        Because *pydicom* defers data parsing during decoding until an element
        is actually required the returned ``Dataset`` may raise an exception
        when first used. It's therefore important that proper error handling
        be part of any handler bound to an event that includes a dataset.

        Returns
        -------
        pydicom.dataset.Dataset
            The decoded *Data Set* dataset.

        Raises
        ------
        AttributeError
            If the corresponding event is not a C-STORE request.
        """
        try:
            t_syntax = self.context.transfer_syntax
            ds = decode(self.request.DataSet,
                        t_syntax.is_implicit_VR,
                        t_syntax.is_little_endian)
            return ds
        except AttributeError:
            pass

        raise AttributeError(
            "The corresponding event is not a C-STORE request and has no "
            "'Data Set' parameter"
        )

    @property
    def event_reply(self):
        """Return an N-EVENT-REPORT request's `Event Reply` as a *pydicom*
        Dataset.

        Because *pydicom* defers data parsing during decoding until an element
        is actually required the returned ``Dataset`` may raise an exception
        when first used. It's therefore important that proper error handling
        be part of any handler bound to an event that includes a dataset.

        Returns
        -------
        pydicom.dataset.Dataset
            The decoded *Event Reply* dataset.

        Raises
        ------
        AttributeError
            If the corresponding event is not an N-EVENT-REPORT request.
        """
        try:
            t_syntax = self.context.transfer_syntax
            ds = decode(self.request.EventReply,
                        t_syntax.is_implicit_VR,
                        t_syntax.is_little_endian)
            return ds
        except AttributeError:
            pass

        raise AttributeError(
            "The corresponding event is not an N-EVENT-REPORT request and has "
            "no 'Event Reply' parameter"
        )

    @property
    def identifier(self):
        """Return a C-FIND C-GET or C-MOVE request's `Identifier` as a
        *pydicom* Dataset.

        Because *pydicom* defers data parsing during decoding until an element
        is actually required the returned ``Dataset`` may raise an exception
        when first used. It's therefore important that proper error handling
        be part of any handler bound to an event that includes a dataset.

        Returns
        -------
        pydicom.dataset.Dataset
            The decoded *Identifier* dataset.

        Raises
        ------
        AttributeError
            If the corresponding event is not a C-FIND, C-GET or C-MOVE
            request.
        """
        try:
            t_syntax = self.context.transfer_syntax
            ds = decode(self.request.Identifier,
                        t_syntax.is_implicit_VR,
                        t_syntax.is_little_endian)
            return ds
        except AttributeError:
            pass

        raise AttributeError(
            "The corresponding event is not a C-FIND, C-GET or C-MOVE request "
            "and has no 'Identifier' parameter"
        )

    @property
    def is_cancelled(self):
        """Return True if a C-CANCEL request has been received.

        Returns
        -------
        bool
            If this event corresponds to a C-FIND, C-GET or C-MOVE request
            being received by a Service Class then returns True if a C-CANCEL
            request with a *MessageIDBeingRespondedTo* parameter value
            corresponding to the *MessageID* of the service request has been
            received. If no such C-CANCEL request has been received or if
            the event is not a C-FIND, C-GET or C-MOVE request then returns
            False.
        """
        try:
            msg_id = self.request.MessageID
            return self._is_cancelled(msg_id)
        except AttributeError:
            pass

        return False


# Default extended negotiation item handlers
def default_async_ops_handler(event):
    """Default handler for when an Asynchronous Operations Window Negotiation
    item is include in the association request.

    Asynchronous operations are not supported by *pynetdicom* and any
    request will always return the default number of operations
    invoked/performed (1, 1), regardless of what values are returned by
    this handler.

    If the handler is not implemented then no response to the Asynchronous
    Operations Window Negotiation will be sent in reply to the association
    requestor.

    **Event**

    ``evt.EVT_ASYNC_OPS``

    Parameters
    ----------
    event : event.Event
        The event representing an association request being received which
        contains an Asynchronous Operations Window Negotiation item. Event
        attributes are:

        * ``assoc`` : the
          :py:class:`association <pynetdicom.association.Association>`
          that is running the service that received the asynchronous operations
          window negotiation request.
        * ``nr_invoked`` : the *Maximum Number Operations Invoked* parameter
          value of the Asynchronous Operations Window request as an ``int``.
          If the value is 0 then an unlimited number of invocations are
          requested.
        * ``nr_performed`` : the *Maximum Number Operations Performed*
          parameter value of the Asynchronous Operations Window request as an
          ``int``. If the value is 0 then an unlimited number of performances
          are requested.
        * ``timestamp`` : the
          `date and time <https://docs.python.org/3/library/datetime.html#datetime-objects>`_
          that the negotiation request was processed by the ACSE.

    Returns
    -------
    int, int
        The (maximum number operations invoked, maximum number operations
        performed). A value of 0 indicates that an unlimited number of
        operations is supported. As asynchronous operations are not
        currently supported the return value will be ignored and (1, 1).
        sent in response.
    """
    raise NotImplementedError(
        "No Asynchronous Operations Window Negotiation response will be "
        "sent"
    )

def default_sop_common_handler(event):
    """Default handler for when one or more SOP Class Common Extended
    Negotiation items are included in the association request.

    **Event**

    ``evt.EVT_SOP_COMMON``

    Parameters
    ----------
    event : event.Event
        The event representing an association request being received which
        contains an Asynchronous Operations Window Negotiation item. Event
        attributes are:

        * ``assoc`` : the
          :py:class:`association <pynetdicom.association.Association>`
          that is running the service that received the SOP class common
          extended negotiation request.
        * ``items`` : the {*SOP Class UID* : SOPClassCommonExtendedNegotiation}
          items sent by the requestor.
        * ``timestamp`` : the
          `date and time <https://docs.python.org/3/library/datetime.html#datetime-objects>`_
          that the negotiation request was processed by the ACSE.

    Returns
    -------
    dict
        The {*SOP Class UID* : SOPClassCommonExtendedNegotiation}
        accepted by the acceptor. When receiving DIMSE messages containing
        datasets corresponding to the SOP Class UID in an accepted item
        the corresponding Service Class will be used.

    References
    ----------

    * DICOM Standard Part 7, `Annex D.3.3.6 <http://dicom.nema.org/medical/dicom/current/output/chtml/part07/sect_D.3.3.6.html>`_
    """
    return {}

def default_sop_extended_handler(event):
    """Default handler for when one or more SOP Class Extended Negotiation
    items are included in the association request.

    **Event**

    ``evt.EVT_SOP_EXTENDED``

    Parameters
    ----------
    event : event.Event
        The event representing an association request being received which
        contains an Asynchronous Operations Window Negotiation item. Event
        attributes are:

        * ``app_info`` : the {*SOP Class UID* : *Service Class Application
          Information*} parameter values for the included items, with the
          service class application information being the raw encoded data sent
          by the requestor (as ``bytes``).
        * ``assoc`` : the
          :py:class:`association <pynetdicom.association.Association>`
          that is running the service that received the user identity
          negotiation request.
        * ``timestamp`` : the
          `date and time <https://docs.python.org/3/library/datetime.html#datetime-objects>`_
          that the negotiation request was processed by the ACSE.

    Returns
    -------
    dict of pydicom.uid.UID, bytes or None
        The {*SOP Class UID* : *Service Class Application Information*}
        parameter values to be sent in response to the request, with the
        service class application information being the encoded data that
        will be sent to the peer as-is. Return ``None`` if no response is to
        be sent.

    References
    ----------

    * DICOM Standard Part 7, `Annex D.3.3.5 <http://dicom.nema.org/medical/dicom/current/output/chtml/part07/sect_D.3.3.5.html>`_
    """
    return None

def default_user_identity_handler(event):
    """Default hander for when a user identity negotiation item is included
    with the association request.

    If not implemented by the user then the association will be accepted
    (provided there's no other reason to reject it) and no User Identity
    response will be sent in reply even if one is requested.

    **Event**

    ``evt.EVT_USER_ID``

    Parameters
    ----------
    event : event.Event
        The event representing an association request being received which
        contains a User Identity Negotiation item. Event attributes are:

        * ``assoc`` : the
          :py:class:`association <pynetdicom.association.Association>`
          that is running the service that received the user identity
          negotiation request.
        * ``primary_field`` : the *Primary Field* value (as ``bytes``),
          contains the username, the encoded Kerberos ticket or the JSON web
          token.
        * ``secondary_field`` : the *Secondary Field* value. Will be ``None``
          unless the ``user_id_type`` is ``2`` in which case it will be
          ``bytes``.
        * ``timestamp`` : the
          `date and time <https://docs.python.org/3/library/datetime.html#datetime-objects>`_
          that the negotiation request was processed by the ACSE.
        * ``user_id_type`` : the *User Identity Type* value (as an ``int``),
          which indicates the form of user identity being provided:

          * 1 - Username as a UTF-8 string
          * 2 - Username as a UTF-8 string and passcode
          * 3 - Kerberos Service ticket
          * 4 - SAML Assertion
          * 5 - JSON Web Token

    Returns
    -------
    is_verified : bool
        Return True if the user identity has been confirmed and you wish
        to proceed with association establishment, False otherwise.
    response : bytes or None
        If ``user_id_type`` is:

        * 1 or 2, then return None
        * 3 then return the Kerberos Server ticket as bytes
        * 4 then return the SAML response as bytes
        * 5 then return the JSON web token as bytes

    References
    ----------

    * DICOM Standard Part 7, `Annex D.3.3.7 <http://dicom.nema.org/medical/dicom/current/output/chtml/part07/sect_D.3.3.7.html>`_
    """
    raise NotImplementedError("No handler has been bound to evt.EVT_USER_ID")

# Default service class request handlers
def default_c_echo_handler(event):
    """Default handler for when a C-ECHO request is received.

    User implementation of this event handler is optional.

    **Event**

    ``evt.EVT_C_ECHO``

    **Supported Service Classes**

    *Verification Service Class*

    **Status**

    Success
      | ``0x0000`` Success

    Failure
      | ``0x0122`` Refused: SOP Class Not Supported
      | ``0x0210`` Refused: Duplicate Invocation
      | ``0x0211`` Refused: Unrecognised Operation
      | ``0x0212`` Refused: Mistyped Argument

    Parameters
    ----------
    event : event.Event
        The event representing a service class receiving a C-ECHO
        request message. Event attributes are:

        * ``assoc`` : the
          :py:class:`association <pynetdicom.association.Association>`
          that is running the service that received the C-ECHO request.
        * ``context`` : the
          :py:class:`presentation context <pynetdicom.presentation.PresentationContext>`
          the request was sent under.
        * request : the
          :py:class:C-ECHO request <pynetdicom.dimse_primitives.C_ECHO>``
          received.
        * ``timestamp`` : the
          `date and time <https://docs.python.org/3/library/datetime.html#datetime-objects>`_
          that the C-ECHO request was processed by the service.

    Returns
    -------
    status : pydicom.dataset.Dataset or int
        The status returned to the peer AE in the C-ECHO response. Must be
        a valid C-ECHO status value for the applicable Service Class as
        either an ``int`` or a ``Dataset`` object containing (at a minimum)
        a (0000,0900) *Status* element. If returning a ``Dataset`` object
        then it may also contain optional elements related to the Status
        (as in the DICOM Standard Part 7, Annex C).

    See Also
    --------
    association.Association.send_c_echo
    dimse_primitives.C_ECHO
    service_class.VerificationServiceClass

    References
    ----------

    * DICOM Standard Part 4, `Annex A <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_A>`_
    * DICOM Standard Part 7, Sections
      `9.1.5 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.1.5>`_,
      `9.3.5 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.5>`_
      and `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_
    """
    return 0x0000

def default_c_find_handler(event):
    """Default handler for when a C-FIND request is received.

    User implementation of this event handler is required if one or more
    services that use C-FIND are to be supported.

    Yields ``(status, identifier)`` pairs, where *status* is either an
    ``int`` or pydicom ``Dataset`` containing a (0000,0900) *Status*
    element and *identifier* is a C-FIND *Identifier* ``Dataset``.

    **Event**

    ``evt.EVT_C_STORE``

    **Supported Service Classes**

    * *Query/Retrieve Service Class*
    * *Basic Worklist Management Service*
    * *Relevant Patient Information Query Service*
    * *Substance Administration Query Service*
    * *Hanging Protocol Query/Retrieve Service*
    * *Defined Procedure Protocol Query/Retrieve Service*
    * *Color Palette Query/Retrieve Service*
    * *Implant Template Query/Retrieve Service*

    **Status**

    Success
      | ``0x0000`` Success

    Failure
      | ``0xA700`` Out of resources
      | ``0xA900`` Identifier does not match SOP class
      | ``0xC000`` to ``0xCFFF`` Unable to process

    Cancel
      | ``0xFE00`` Matching terminated due to Cancel request

    Pending
      | ``0xFF00`` Matches are continuing: current match is supplied and
         any Optional Keys were supported in the same manner as Required
         Keys
      | ``0xFF01`` Matches are continuing: warning that one or more Optional
        Keys were not supported for existence and/or matching for this
        Identifier

    Parameters
    ----------
    event : event.Event
        The event representing a service class receiving a C-FIND
        request message. Event attributes are:

        * ``assoc`` : the
          :py:class:`association <pynetdicom.association.Association>`
          that is running the service that received the C-FIND request.
        * ``context`` : the
          :py:class:`presentation context <pynetdicom.presentation.PresentationContext>`
          the request was sent under.
        * ``request`` : the
          :py:class:`C-FIND request <pynetdicom.dimse_primitives.C_FIND>`
          that was received.
        * ``timestamp`` : the
          `date and time <https://docs.python.org/3/library/datetime.html#datetime-objects>`_
          that the C-FIND request was processed by the service.

        Event properties are:

        * ``identifier`` : the decoded
          :py:class:`Dataset <pydicom.dataset.Dataset>` contained within the
          C-FIND request's *Identifier* parameter. Because *pydicom* uses
          a deferred read when decoding data, if the decode fails the returned
          ``Dataset`` will only raise an exception at the time of use.
        * ``is_cancelled`` : returns ``True`` if a
          C-CANCEL request has been received, False otherwise. If a C-CANCEL
          is received then the handler should ``yield (0xFE00, None)`` and
          return.

    Yields
    ------
    status : pydicom.dataset.Dataset or int
        The status returned to the peer AE in the C-FIND response. Must be
        a valid C-FIND status vuale for the applicable Service Class as
        either an ``int`` or a ``Dataset`` object containing (at a minimum)
        a (0000,0900) *Status* element. If returning a Dataset object then
        it may also contain optional elements related to the Status (as in
        DICOM Standard Part 7, Annex C).
    identifier : pydicom.dataset.Dataset or None
        If the status is 'Pending' then the *Identifier* ``Dataset`` for a
        matching SOP Instance. The exact requirements for the C-FIND
        response *Identifier* are Service Class specific (see the
        DICOM Standard, Part 4).

        If the status is 'Failure' or 'Cancel' then yield ``None``.

        If the status is 'Success' then yield ``None``, however yielding a
        final 'Success' status is not required and will be ignored if
        necessary.

    See Also
    --------
    association.Association.send_c_find
    dimse_primitives.C_FIND
    service_class.QueryRetrieveFindServiceClass
    service_class.BasicWorklistManagementServiceClass
    service_class.RelevantPatientInformationQueryServiceClass
    service_class.SubstanceAdministrationQueryServiceClass
    service_class.HangingProtocolQueryRetrieveServiceClass
    service_class.DefinedProcedureProtocolQueryRetrieveServiceClass
    service_class.ColorPaletteQueryRetrieveServiceClass
    service_class.ImplantTemplateQueryRetrieveServiceClass

    References
    ----------

    * DICOM Standard Part 4, Annexes
      `C <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_C>`_,
      `K <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_K>`_,
      `Q <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_Q>`_,
      `U <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_U>`_,
      `V <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_V>`_,
      `X <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_X>`_,
      `BB <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_BB>`_,
      `CC <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_CC>`_
      and `HH <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_HH>`_
    * DICOM Standard Part 7, Sections
      `9.1.2 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.1.2>`_,
      `9.3.2 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.2>`_
      and `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_
    """
    raise NotImplementedError("No handler has been bound to evt.EVT_C_FIND")

def default_c_get_handler(event):
    """Default handler for when a C-GET request is received.

    User implementation of this event handler is required if one or more
    services that use C-GET are to be supported.

    Yields an ``int`` containing the total number of C-STORE sub-operations,
    then yields ``(status, dataset)`` pairs.

    **Event**

    ``evt.EVT_C_GET``

    **Supported Service Classes**

    * *Query/Retrieve Service Class*
    * *Hanging Protocol Query/Retrieve Service*
    * *Defined Procedure Protocol Query/Retrieve Service*
    * *Color Palette Query/Retrieve Service*
    * *Implant Template Query/Retrieve Service*

    **Status**

    Success
      | ``0x0000`` Sub-operations complete, no failures or warnings

    Failure
      | ``0xA701`` Out of resources: unable to calculate the number of
        matches
      | ``0xA702`` Out of resources: unable to perform sub-operations
      | ``0xA900`` Identifier does not match SOP class
      | ``0xAA00`` None of the frames requested were found in the SOP
        instance
      | ``0xAA01`` Unable to create new object for this SOP class
      | ``0xAA02`` Unable to extract frames
      | ``0xAA03`` Time-based request received for a non-time-based
        original SOP Instance
      | ``0xAA04`` Invalid request
      | ``0xC000`` to ``0xCFFF`` Unable to process

    Cancel
      | ``0xFE00`` Sub-operations terminated due to Cancel request

    Warning
      | ``0xB000`` Sub-operations complete, one or more failures or
        warnings

    Pending
      | ``0xFF00`` Matches are continuing - Current Match is supplied and
        any Optional Keys were supported in the same manner as Required
        Keys

    Parameters
    ----------
    event : event.Event
        The event representing a service class receiving a C-GET
        request message. Event attributes are:

        * ``assoc`` : the
          :py:class:`association <pynetdicom.association.Association>`
          that is running the service that received the C-GET request.
        * ``context`` : the
          :py:class:`presentation context <pynetdicom.presentation.PresentationContext>`
          the request was sent under.
        * ``request`` : the
          :py:class:`C-GET request <pynetdicom.dimse_primitives.C_GET>`
          that was received.
        * ``timestamp`` : the
          `date and time <https://docs.python.org/3/library/datetime.html#datetime-objects>`_
          that the C-GET request was processed by the service.

        Event properties are:

        * ``identifier`` : the decoded
          :py:class:`Dataset <pydicom.dataset.Dataset>` contained within the
          C-GET request's *Identifier* parameter. Because *pydicom* uses
          a deferred read when decoding data, if the decode fails the returned
          ``Dataset`` will only raise an exception at the time of use.
        * ``is_cancelled`` : returns ``True`` if a
          C-CANCEL request has been received, False otherwise. If a C-CANCEL
          is received then the handler should ``yield (0xFE00, None)`` and
          return.

    Yields
    ------
    int
        The first yielded value should be the total number of C-STORE
        sub-operations necessary to complete the C-GET operation. In other
        words, this is the number of matching SOP Instances to be sent to
        the peer.
    status : pydicom.dataset.Dataset or int
        The status returned to the peer AE in the C-GET response. Must be a
        valid C-GET status value for the applicable Service Class as either
        an ``int`` or a ``Dataset`` object containing (at a minimum) a
        (0000,0900) *Status* element. If returning a Dataset object then
        it may also contain optional elements related to the Status (as in
        DICOM Standard Part 7, Annex C).
    dataset : pydicom.dataset.Dataset or None
        If the status is 'Pending' then yield the ``Dataset`` to send to
        the peer via a C-STORE sub-operation over the current association.

        If the status is 'Failed', 'Warning' or 'Cancel' then yield a
        ``Dataset`` with a (0008,0058) *Failed SOP Instance UID List*
        element containing a list of the C-STORE sub-operation SOP Instance
        UIDs for which the C-GET operation has failed.

        If the status is 'Success' then yield ``None``, although yielding a
        final 'Success' status is not required and will be ignored if
        necessary.

    See Also
    --------
    association.Association.send_c_get
    dimse_primitives.C_GET
    service_class.QueryRetrieveGetServiceClass
    service_class.HangingProtocolQueryRetrieveServiceClass
    service_class.DefinedProcedureProtocolQueryRetrieveServiceClass
    service_class.ColorPaletteQueryRetrieveServiceClass
    service_class.ImplantTemplateQueryRetrieveServiceClass

    References
    ----------

    * DICOM Standard Part 4, Annexes
      `C <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_C>`_,
      `U <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_U>`_,
      `X <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_X>`_,
      `Y <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_Y>`_,
      `Z <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_Z>`_,
      `BB <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_BB>`_
      and `HH <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_HH>`_
    * DICOM Standard Part 7, Sections
      `9.1.3 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.1.3>`_,
      `9.3.3 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.3>`_
      and `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_
    """
    raise NotImplementedError("No handler has been bound to evt.EVT_C_GET")

def default_c_move_handler(event):
    """Default handler for when a C-MOVE request is received.

    User implementation of this event handler is required if one or more
    services that use C-MOVE are to be supported.

    The first yield should be the ``(addr, port)`` of the move destination,
    the second yield the number of required C-STORE sub-operations as an
    ``int``, and the remaining yields the ``(status, dataset)`` pairs.

    Matching SOP Instances will be sent to the peer AE with AE title
    ``move_aet`` over a new association. If ``move_aet`` is unknown then
    the SCP will send a response with a 'Failure' status of ``0xA801``
    'Move Destination Unknown'.

    **Event**

    ``evt.EVT_C_MOVE``

    **Supported Service Classes**

    * *Query/Retrieve Service*
    * *Hanging Protocol Query/Retrieve Service*
    * *Defined Procedure Protocol Query/Retrieve Service*
    * *Color Palette Query/Retrieve Service*
    * *Implant Template Query/Retrieve Service*

    **Status**

    Success
      | ``0x0000`` Sub-operations complete, no failures

    Pending
      | ``0xFF00`` Sub-operations are continuing

    Cancel
      | ``0xFE00`` Sub-operations terminated due to Cancel indication

    Failure
      | ``0x0122`` SOP class not supported
      | ``0x0124`` Not authorised
      | ``0x0210`` Duplicate invocation
      | ``0x0211`` Unrecognised operation
      | ``0x0212`` Mistyped argument
      | ``0xA701`` Out of resources: unable to calculate number of matches
      | ``0xA702`` Out of resources: unable to perform sub-operations
      | ``0xA801`` Move destination unknown
      | ``0xA900`` Identifier does not match SOP class
      | ``0xAA00`` None of the frames requested were found in the SOP
        instance
      | ``0xAA01`` Unable to create new object for this SOP class
      | ``0xAA02`` Unable to extract frames
      | ``0xAA03`` Time-based request received for a non-time-based
        original SOP Instance
      | ``0xAA04`` Invalid request
      | ``0xC000`` to ``0xCFFF`` Unable to process


    Parameters
    ----------
    event : event.Event
        The event representing a service class receiving a C-MOVE
        request message. Event attributes are:

        * ``assoc`` : the
          :py:class:`association <pynetdicom.association.Association>`
          that is running the service that received the C-MOVE request.
        * ``context`` : the
          :py:class:`presentation context <pynetdicom.presentation.PresentationContext>`
          the request was sent under.
        * ``request`` : the
          :py:class:`C-MOVE request <pynetdicom.dimse_primitives.C_MOVE>`
          that was received.
        * ``timestamp`` : the
          `date and time <https://docs.python.org/3/library/datetime.html#datetime-objects>`_
          that the C-MOVE request was processed by the service.

        Event properties are:

        * ``identifier`` : the decoded
          :py:class:`Dataset <pydicom.dataset.Dataset>` contained within the
          C-MOVE request's *Identifier* parameter. Because *pydicom* uses
          a deferred read when decoding data, if the decode fails the returned
          ``Dataset`` will only raise an exception at the time of use.
        * ``is_cancelled`` : returns ``True`` if a
          C-CANCEL request has been received, False otherwise. If a C-CANCEL
          is received then the handler should ``yield (0xFE00, None)`` and
          return.

    Yields
    ------
    addr, port : str, int or None, None
        The first yield should be the TCP/IP address and port number of the
        destination AE (if known) or ``(None, None)`` if unknown. If
        ``(None, None)`` is yielded then the SCP will send a C-MOVE
        response with a 'Failure' Status of ``0xA801`` (move destination
        unknown), in which case nothing more needs to be yielded.
    int
        The second yield should be the number of C-STORE sub-operations
        required to complete the C-MOVE operation. In other words, this is
        the number of matching SOP Instances to be sent to the peer.
    status : pydiom.dataset.Dataset or int
        The status returned to the peer AE in the C-MOVE response. Must be
        a valid C-MOVE status value for the applicable Service Class as
        either an ``int`` or a ``Dataset`` containing (at a minimum) a
        (0000,0900) *Status* element. If returning a ``Dataset`` then it
        may also contain optional elements related to the Status (as in
        DICOM Standard Part 7, Annex C).
    dataset : pydicom.dataset.Dataset or None
        If the status is 'Pending' then yield the ``Dataset``
        to send to the peer via a C-STORE sub-operation over a new
        association.

        If the status is 'Failed', 'Warning' or 'Cancel' then yield a
        ``Dataset`` with a (0008,0058) *Failed SOP Instance UID List*
        element containing the list of the C-STORE sub-operation SOP
        Instance UIDs for which the C-MOVE operation has failed.

        If the status is 'Success' then yield ``None``, although yielding a
        final 'Success' status is not required and will be ignored if
        necessary.

    See Also
    --------
    association.Association.send_c_move
    dimse_primitives.C_MOVE
    service_class.QueryRetrieveMoveServiceClass
    service_class.HangingProtocolQueryRetrieveServiceClass
    service_class.DefinedProcedureProtocolQueryRetrieveServiceClass
    service_class.ColorPaletteQueryRetrieveServiceClass
    service_class.ImplantTemplateQueryRetrieveServiceClass

    References
    ----------

    * DICOM Standard Part 4, Annexes
      `C <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_C>`_,
      `U <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_U>`_,
      `X <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_X>`_,
      `Y <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_Y>`_,
      `BB <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_BB>`_
      and `HH <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_HH>`_
    * DICOM Standard Part 7, Sections
      `9.1.4 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.1.4>`_,
      `9.3.4 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.4>`_
      and `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_
    """
    raise NotImplementedError("No handler has been bound to evt.EVT_C_MOVE")

def default_c_store_handler(event):
    """Default handler for when a C-STORE request is received.

    User implementation of this event handler is required if one or more
    services that use C-STORE are to be supported.

    If the user is storing the dataset in the DICOM File Format (as in the
    DICOM Standard Part 10, Section 7) then they are responsible for adding
    the DICOM File Meta Information.

    **Event**

    ``evt.EVT_C_STORE``

    **Supported Service Classes**

    * *Storage Service Class*
    * *Non-Patient Object Storage Service Class*

    **Status**

    Success
      | ``0x0000`` - Success

    Warning
      | ``0xB000`` Coercion of data elements
      | ``0xB006`` Elements discarded
      | ``0xB007`` Dataset does not match SOP class

    Failure
      | ``0x0117`` Invalid SOP instance
      | ``0x0122`` SOP class not supported
      | ``0x0124`` Not authorised
      | ``0x0210`` Duplicate invocation
      | ``0x0211`` Unrecognised operation
      | ``0x0212`` Mistyped argument
      | ``0xA700`` to ``0xA7FF`` Out of resources
      | ``0xA900`` to ``0xA9FF`` Dataset does not match SOP class
      | ``0xC000`` to ``0xCFFF`` Cannot understand

    Parameters
    ----------
    event : event.Event
        The event representing a service class receiving a C-STORE
        request message. Event attributes are:

        * ``assoc`` : the
          :py:class:`association <pynetdicom.association.Association>`
          that is running the service that received the C-STORE request.
        * ``context`` : the
          :py:class:`presentation context <pynetdicom.presentation.PresentationContext>`
          the request was sent under.
        * ``request`` : the
          :py:class:`C-STORE request <pynetdicom.dimse_primitives.C_STORE>`
          that was received.
        * ``timestamp`` : the
          `date and time <https://docs.python.org/3/library/datetime.html#datetime-objects>`_
          that the C-STORE request was processed by the service.

        Event properties are:

        * ``dataset`` : the decoded
          :py:class:`Dataset <pydicom.dataset.Dataset>` contained within the
          C-STORE request's *DataSet* parameter. Because *pydicom* uses
          a deferred read when decoding data, if the decode fails the returned
          ``Dataset`` will only raise an exception at the time of use.

    Returns
    -------
    status : pydicom.dataset.Dataset or int
        The status returned to the requesting AE in the C-STORE response. Must
        be a valid C-STORE status value for the applicable Service Class as
        either an ``int`` or a ``Dataset`` object containing (at a
        minimum) a (0000,0900) *Status* element. If returning a Dataset
        object then it may also contain optional elements related to the
        Status (as in the DICOM Standard Part 7, Annex C).

    Raises
    ------
    NotImplementedError
        If the handler has not been implemented and bound to
        ``evt.EVT_C_STORE`` by the user.

    See Also
    --------
    association.Association.send_c_store
    dimse_primitives.C_STORE
    service_class.StorageServiceClass
    service_class.NonPatientObjectStorageServiceClass

    References
    ----------

    * DICOM Standard Part 4, Annexes
      `B <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_B>`_,
      `AA <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_AA>`_,
      `FF <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_FF>`_
      and `GG <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_GG>`_
    * DICOM Standard Part 7, Sections
      `9.1.1 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.1.1>`_,
      `9.3.1 <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#sect_9.3.1>`_
      and `Annex C <http://dicom.nema.org/medical/dicom/current/output/html/part07.html#chapter_C>`_
    * DICOM Standard Part 10,
      `Section 7 <http://dicom.nema.org/medical/dicom/current/output/html/part10.html#chapter_7>`_
    """
    raise NotImplementedError("No handler has been bound to evt.EVT_C_STORE")

def default_n_action_handler(event):
    """Default handler for when an N-ACTION request is received.

    User implementation of this event handler is required if one or more
    services that use N-ACTION are to be supported.

    **Event**

    ``evt.EVT_N_ACTION``

    References
    ----------
    DICOM Standard Part 4, Annexes H, J, P, S, CC and DD
    """
    raise NotImplementedError("No handler has been bound to evt.EVT_N_ACTION")

def default_n_create_handler(event):
    """Default handler for when an N-CREATE request is received.

    User implementation of this event handler is required if one or more
    services that use N-CREATE are to be supported.

    **Event**

    ``evt.EVT_N_CREATE``

    References
    ----------
    DICOM Standard Part 4, Annexes F, H, R, S, CC and DD
    """
    raise NotImplementedError("No handler has been bound to evt.EVT_N_CREATE")

def default_n_delete_handler(event):
    """Default handler for when an N-DELETE request is received.

    User implementation of this event handler is required if one or more
    services that use N-DELETE are to be supported.

    **Event**

    ``evt.EVT_N_DELETE``

    References
    ----------
    DICOM Standard Part 4, Annexes H and DD
    """
    raise NotImplementedError("No handler has been bound to evt.EVT_N_DELETE")

def default_n_event_report_handler(event):
    """Default handler for when an N-EVENT-REPORT request is received.

    User implementation of this event handler is required if one or more
    services that use N-EVENT-REPORT are to be supported.

    **Event**

    ``evt.EVT_N_EVENT_REPORT``

    References
    ----------
    DICOM Standard Part 4, Annexes F, H, J, CC and DD
    """
    raise NotImplementedError(
        "No handler has been bound to evt.EVT_N_EVENT_REPORT"
    )

def default_n_get_handler(event):
    """Default handler for when an N-GET request is received.

    User implementation of this event handler is required if one or more
    services that use N-GET are to be supported.

    **Event**

    ``evt.EVT_N_GET``

    Parameters
    ----------
    event : event.Event
        The event representing a service class receiving an N-GET
        request message. Event attributes are:

        * ``assoc`` : the
          :py:class:`association <pynetdicom.association.Association>`
          that is running the service that received the N-GET request.
        * ``context`` : the
          :py:class:`presentation context <pynetdicom.presentation.PresentationContext>`
          the request was sent under.
        * ``request`` : the
          :py:class:`N-GET request <pynetdicom.dimse_primitives.N_GET>`
          that was received.
        * ``timestamp`` : the
          `date and time <https://docs.python.org/3/library/datetime.html#datetime-objects>`_
          that the N-GET request was processed by the service.

    Returns
    -------
    status : pydicom.dataset.Dataset or int
        The status returned to the peer AE in the N-GET response. Must be a
        valid N-GET status value for the applicable Service Class as either
        an ``int`` or a ``Dataset`` object containing (at a minimum) a
        (0000,0900) *Status* element. If returning a Dataset object then
        it may also contain optional elements related to the Status (as in
        DICOM Standard Part 7, Annex C).
    dataset : pydicom.dataset.Dataset or None
        If the status category is 'Success' or 'Warning' then a dataset
        containing elements matching the request's Attribute List
        conformant to the specifications in the corresponding Service
        Class.

        If the status is not 'Successs' or 'Warning' then return None.

    See Also
    --------
    association.Association.send_n_get
    dimse_primitives.N_GET
    service_class.DisplaySystemManagementServiceClass

    References
    ----------

    * DICOM Standart Part 4, `Annex F <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_F>`_
    * DICOM Standart Part 4, `Annex H <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_H>`_
    * DICOM Standard Part 4, `Annex S <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_S>`_
    * DICOM Standard Part 4, `Annex CC <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_CC>`_
    * DICOM Standard Part 4, `Annex DD <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_DD>`_
    * DICOM Standard Part 4, `Annex EE <http://dicom.nema.org/medical/dicom/current/output/html/part04.html#chapter_EE>`_
    """
    raise NotImplementedError("No handler has been bound to evt.EVT_N_GET")

def default_n_set_handler(event):
    """Default handler for when an N-SET request is received.

    User implementation of this event handler is required if one or more
    services that use N-SET are to be supported.

    **Event**

    ``evt.EVT_N_SET``

    References
    ----------
    DICOM Standard Part 4, Annexes H, J, P, S, CC and DD
    """
    raise NotImplementedError("No handler has been bound to evt.EVT_N_SET")
