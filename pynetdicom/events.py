"""Module used to support Event handling."""

from datetime import datetime
import logging


LOGGER = logging.getLogger('pynetdicom.events')


# Possible events
# (source, name, description, multiple handers)
# Transport Service
EVT_CONNECTION_OPEN = ('TRANSPORT', 'CONNECTION OPEN', 'Connection with remote opened', True)
EVT_CONNECTION_CLOSE = ('TRANSPORT', 'CONNECTION CLOSE', 'Connection with remote closed', True)

# DIMSE Service
EVT_MESSAGE_RECV = ('DIMSE', 'MESSAGE RECV', 'DIMSE message received', True)
EVT_MESSAGE_SENT = ('DIMSE', 'MESSAGE SENT', 'DIMSE message sent', True)


# Association
EVT_ESTABLISHED = ('ASSOCIATION', 'ESTABLISHED', 'Association established', True)
EVT_RELEASED = ('ASSOCIATION', 'RELEASED', 'Association release completed', True)
EVT_ABORTED = ('ASSOCIATION', 'ABORTED', 'Association aborted', True)
EVT_REJECTED = ('ASSOCIATION', 'REJECTED', 'Association rejected', True)

# ACSE Service
EVT_USER_IDENTITY = ('ACSE', 'USER IDENTITY', 'User Identity request sent/received', False)
EVT_ASYNC_OPS = ('ACSE', 'ASYNC OPERATIONS', 'Asynchronous Operations request sent/received', False)
EVT_SOP_EXTENDED = ('ACSE', 'SOP EXTENDED', 'SOP Class Extended request sent/received', False)
EVT_SOP_COMMON = ('ACSE', 'SOP COMMON', 'SOP Class Common Extended request sent/received', False)

EVT_REQUEST = ('ACSE', 'ASSOCIATION REQUEST', 'Association request sent/received')
EVT_ACCEPT = ('ACSE', 'ASSOCIATION ACCEPT', 'Association accept sent/received')
EVT_REJECT = ('ACSE', 'ASSOCIATION REJECT', 'Association reject sent/received')
EVT_ABORT = ('ACSE', 'ASSOCIATION ABORT', 'Association abort sent/received')
EVT_RELEASE = ('ACSE', 'ASSOCIATION RELEASE', 'Association release sent/received')

# Verificiation Service
EVT_ECHO = ('VERIFICATION', 'ECHO ACTION', 'C-ECHO request received by service', False)
# Storage Service
EVT_STORE = ('STORAGE', 'STORE ACTION', 'C-STORE request received by service', False)
# Query/Retrieve Service
EVT_FIND = ('QR', 'FIND ACTION', 'C-FIND request received by service', False)
EVT_GET = ('QR', 'GET ACTION', 'C-GET request received by service', False)
EVT_MOVE = ('QR', 'MOVE ACTION', 'C-MOVE request received by service', False)


def trigger(cls, event, attrs=None):
    """Trigger an `event`.

    Parameters
    ----------
    cls : object
        The object triggering the event.
    event : 3-tuple of str
        The event to trigger ('source', 'event', 'description').
    attrs : dict, optional
        The attributes to set in the Event instance that is passed to
        the event's corresponding handler functions as
        {attribute name : value}, default {}.
    is_singleton : bool, optional
        True if only one callable function is allowed, False otherwise
        (default).
    """
    if event not in cls._handlers:
        return

    attrs = attrs or {}

    evt = Event(event)
    evt.source = cls
    for kk, vv in attrs.items():
        setattr(evt, kk, vv)

    try:
        for func in cls._handlers[event]:
            func(evt)
    except Exception as exc:
        print(
            "Exception raised in user's '{}' event handler '{}'"
            .format(event[1], func.__name__)
        )
        print(exc)
        LOGGER.error(
            "Exception raised in user's '{}' event handler '{}'"
            .format(event[1], func.__name__)
        )
        LOGGER.exception(exc)


class Event(object):
    """Representation of an event.

    Attributes
    ----------
    event : 3-tuple
        The event that occurred.
    timestamp : datetime.datetime
        The date/time the event was created. Will be slightly before or after
        the actual event that this object represents.
    """
    def __init__(self, event):
        self.event = event
        self.source = None
        self.assoc = None
        self.timestamp = datetime.now()
        self._has_dataset = False
        self._has_identifier = False

    @property
    def dataset(self):
        """

        Returns
        -------

        Raises
        ------

        """
        if self._has_dataset:
            t_syntax = self.context.transfer_syntax
            ds = decode(self.message.DataSet,
                        t_syntax.is_implicit_VR,
                        t_syntax.is_little_endian)
            return ds

        raise AttributeError("")

    @property
    def identifier(self):
        pass


def default_c_echo_handler(event):
    """Default handler for when a C-ECHO request is received.

    User implementation of this event handler is optional.

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
          that is running the service
        * ``context`` : the
          :py:class:`presentation context <pynetdicom.presentation.PresentationContext>`
          the request was sent using
        * message : the dimse_messages.C_ECHO_RQ message received
        * ``timestamp`` : the `datetime <https://docs.python.org/3/library/datetime.html#datetime-objects>`_
          that the event occurred at

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
    pass


def default_c_store_handler(event):
    """

    If the user is storing the dataset in the DICOM File Format (as in the
    DICOM Standard Part 10, Section 7) then they are responsible for adding
    the DICOM File Meta Information.

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
          that is running the service
        * ``context`` : the
          :py:class:`presentation context <pynetdicom.presentation.PresentationContext>`
          the request was sent using
        * ``message`` : the received
          :py:class:`C-STORE-RQ <pynetdicom.dimse_messages.C_STORE_RQ>`
        * ``timestamp`` : the
          `date and time <https://docs.python.org/3/library/datetime.html#datetime-objects>`_
          that the event occurred at

        Event properties are:

        * ``dataset`` : the decoded
          :py:class:`Dataset <pydicom.dataset.Dataset>` contained within the
          C-STORE-RQ message's *DataSet* parameter. Because *pydicom* uses
          a deferred read when decoding data, the returned
          ``Dataset`` will only raise an exception because of a decoding
          failure at the time of use.

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
        If the handler has not been implemented and bound by the user.

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
    raise NotImplementedError(
        "No handler has been bound to evt.EVT_X "
    )
