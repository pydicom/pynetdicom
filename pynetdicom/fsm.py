"""
The DUL's finite state machine representation.
"""
import logging

from pynetdicom import evt
from pynetdicom.pdu import (
    A_ASSOCIATE_RQ, A_ASSOCIATE_RJ, A_ASSOCIATE_AC,
    P_DATA_TF, A_RELEASE_RQ, A_RELEASE_RP, A_ABORT_RQ
)
from pynetdicom.pdu_primitives import A_P_ABORT


LOGGER = logging.getLogger('pynetdicom.sm')


class InvalidEventError(Exception):
    """Exception for use when an invalid event occurs for a given state."""
    pass


# pylint: disable=invalid-name
class StateMachine(object):
    """Implementation of the DICOM Upper Layer State Machine.

    Attributes
    ----------
    current_state : str
        The current state of the state machine, ``'Sta1'`` to ``'Sta13'``.
    dul : dul.DULServiceProvider
        The DICOM Upper Layer service instance for the local AE

    References
    ----------

    * DICOM Standard, Part 8, :dcm:`Section 9.2<part08/sect_9.2.html>`
    """
    def __init__(self, dul):
        """Create a new :class:`StateMachine`.

        Parameters
        ---------
        dul : dul.DULServiceProvider
            The DICOM Upper Layer Service instance for the association.
        """
        self.current_state = 'Sta1'
        self.dul = dul

    def do_action(self, event):
        """Execute the action triggered by `event`.

        Parameters
        ----------
        event : str
            The event to be processed, ``'Evt1'`` to ``'Evt19'``
        """
        # Check (event + state) is valid
        if (event, self.current_state) not in TRANSITION_TABLE:
            msg = (
                "Invalid event '{}' for the current state '{}'"
                .format(event, self.current_state)
            )
            LOGGER.error(msg)
            raise InvalidEventError(msg)

        action_name = TRANSITION_TABLE[(event, self.current_state)]

        # action is the (description, function, state) tuple
        #   associated with the action_name
        action = ACTIONS[action_name]

        # Attempt to execute the action and move the state machine to its
        #   next state
        try:
            # Execute the required action
            next_state = action[1](self.dul)

            # Event handler - FSM transition
            evt.trigger(
                self.dul.assoc,
                evt.EVT_FSM_TRANSITION,
                {
                    'action' : action_name,
                    'current_state' : self.current_state,
                    'fsm_event' : event,
                    'next_state' : next_state
                }
            )
            #print(
            #    "{}: {} + {} -> {} -> {}".format(
            #        self.dul.assoc.mode[0].upper(), self.current_state,
            #        event, action_name, next_state
            #    )
            #)

            # Move the state machine to the next state
            self.transition(next_state)

        except Exception as exc:
            LOGGER.error("State Machine received an exception attempting "
                         "to perform the action '%s' while in state '%s'",
                         action_name, self.current_state)
            LOGGER.exception(exc)
            self.dul.kill_dul()
            raise

    def transition(self, state):
        """Transition the state machine to the next state.

        Parameters
        ----------
        state : str
            The state to transition to, ``'Sta1'`` to ``'Sta13'``.

        Raises
        ------
        ValueError
            If `state` is not a valid state.
        """
        # Validate that state is acceptable
        if state in STATES.keys():
            self.current_state = state
        else:
            msg = "Invalid state '{}' for State Machine".format(state)
            LOGGER.error(msg)
            raise ValueError(msg)


def AE_1(dul):
    """Association establishment action AE-1.

    *Event*

    Service user issued A-ASSOCIATE (request) to the service provider

    *Action*

    Issue TRANSPORT CONNECT request primitive to the transport service.

    *State/Event Triggers*

    - Sta1 + Evt1

    Parameters
    ----------
    dul : dul.DULServiceProvider
        The DICOM Upper Layer Service instance for the local AE

    Returns
    -------
    str
        ``'Sta4'``, the next state of the state machine.
    """
    # Issue TRANSPORT CONNECT request primitive to local transport service
    # This is our "TRANSPORT CONNECT" primitive - it attempts to connect
    #   to the peer, emitting either Evt2 or Evt17
    dul.socket.connect(dul.primitive.called_presentation_address)

    return 'Sta4'

def AE_2(dul):
    """Association establishment action AE-2.

    On receiving connection confirmation, send A-ASSOCIATE-RQ to the peer AE
    This send a byte stream with the format given by Table 9-11

    State-event triggers: Sta4 + Evt2

    Parameters
    ----------
    dul : dul.DULServiceProvider
        The DICOM Upper Layer Service instance for the local AE

    Returns
    -------
    str
        ``'Sta5'``, the next state of the state machine.
    """
    # Send A-ASSOCIATE-RQ PDU
    dul.pdu = A_ASSOCIATE_RQ()
    dul.pdu.from_primitive(dul.primitive)

    dul.socket.send(dul.pdu.encode())
    evt.trigger(dul.assoc, evt.EVT_PDU_SENT, {'pdu' : dul.pdu})

    return 'Sta5'

def AE_3(dul):
    """Association establishment action AE-3.

    On receiving A-ASSOCIATE-AC, issue acceptance confirmation

    State-event triggers: Sta5 + Evt3

    Parameters
    ----------
    dul : dul.DULServiceProvider
        The DICOM Upper Layer Service instance for the local AE

    Returns
    -------
    str
        ``'Sta6'``, the next state of the state machine
    """
    # Issue A-ASSOCIATE confirmation (accept) primitive
    dul.to_user_queue.put(dul.primitive)

    return 'Sta6'

def AE_4(dul):
    """Association establishment action AE-4.

    On receiving A-ASSOCIATE-RJ, issue rejection confirmation and close
    connection

    State-event triggers: Sta5 + Evt4

    Parameters
    ----------
    dul : dul.DULServiceProvider
        The DICOM Upper Layer Service instance for the local AE

    Returns
    -------
    str
        ``'Sta1'``, the next state of the state machine
    """
    # Issue A-ASSOCIATE confirmation (reject) primitive and close transport
    # connection
    dul.to_user_queue.put(dul.primitive)
    dul.socket.close()

    assoc = dul.assoc
    remote = assoc.acceptor if assoc.is_requestor else assoc.requestor

    address = (remote.address, remote.port)
    evt.trigger(dul.assoc, evt.EVT_CONN_CLOSE, {'address' : address})

    dul.kill_dul()

    return 'Sta1'

def AE_5(dul):
    """Association establishment action AE-5.

    From Idle state, on receiving a remote connection attempt, respond and
    start ARTIM. This is the first step in associating a remote AE (requestor)
    to the local AE (acceptor).

    State-event triggers: Sta1 + Evt5

    Parameters
    ----------
    dul : dul.DULServiceProvider
        The DICOM Upper Layer Service instance for the local AE

    Returns
    -------
    str
        ``'Sta2'``, the next state of the state machine
    """
    # Start ARTIM timer
    dul.artim_timer.start()

    return 'Sta2'

def AE_6(dul):
    """Association establishment action AE-6.

    On receiving an A-ASSOCIATE-RQ PDU from the peer then stop the ARTIM timer
    and then either

    * issue an A-ASSOCIATE indication primitive if the -RQ is acceptable or
    * issue an A-ASSOCIATE-RJ PDU to the peer and start the ARTIM timer

    This is a lower-level DUL Service Provider initiated rejection - for
    example this could be where the protocol version is checked

    State-event triggers: Sta2 + Evt6

    Parameters
    ----------
    dul : dul.DULServiceProvider
        The DICOM Upper Layer Service instance for the local AE

    Returns
    -------
    str
        Either ``'Sta3'`` or ``'Sta13'``, the next state of the state machine
    """
    # Stop ARTIM timer
    dul.artim_timer.stop()

    # If A-ASSOCIATE-RQ not acceptable by service dul provider
    #   Then set reason and send -RJ PDU back to peer
    if dul.pdu.protocol_version != 0x0001:
        LOGGER.error("A-ASSOCIATE-RQ: Unsupported protocol "
                     "version '0x%04x'",
                     dul.pdu.protocol_version)

        # Send A-ASSOCIATE-RJ PDU and start ARTIM timer
        # dul.primitive is A_ASSOCIATE
        dul.primitive.result = 0x01
        dul.primitive.result_source = 0x02
        dul.primitive.diagnostic = 0x02

        dul.pdu = A_ASSOCIATE_RJ()
        dul.pdu.from_primitive(dul.primitive)

        dul.socket.send(dul.pdu.encode())
        evt.trigger(dul.assoc, evt.EVT_PDU_SENT, {'pdu' : dul.pdu})
        dul.artim_timer.start()

        return 'Sta13'

    # If A-ASSOCIATE-RQ acceptable by service dul provider
    #   issue A-ASSOCIATE indication primitive and move to Sta3
    dul.to_user_queue.put(dul.primitive)

    return 'Sta3'

def AE_7(dul):
    """Association establishment action AE-7.

    On receiving association request acceptance, issue A-ASSOCIATE-AC

    State-event triggers: Sta3 + Evt7

    Parameters
    ----------
    dul : dul.DULServiceProvider
        The DICOM Upper Layer Service instance for the local AE

    Returns
    -------
    str
        ``'Sta6'``, the next state of the state machine
    """
    # Send A-ASSOCIATE-AC PDU
    dul.pdu = A_ASSOCIATE_AC()
    dul.pdu.from_primitive(dul.primitive)

    dul.socket.send(dul.pdu.encode())
    evt.trigger(dul.assoc, evt.EVT_PDU_SENT, {'pdu' : dul.pdu})

    return 'Sta6'

def AE_8(dul):
    """Association establishment action AE-8.

    On receiving association request rejection, issue A-ASSOCIATE-RJ

    State-event triggers: Sta3 + Evt8

    Parameters
    ----------
    dul : dul.DULServiceProvider
        The DICOM Upper Layer Service instance for the local AE

    Returns
    -------
    str
        ``'Sta13'``, the next state of the state machine
    """
    # Send A-ASSOCIATE-RJ PDU and start ARTIM timer
    dul.pdu = A_ASSOCIATE_RJ()
    dul.pdu.from_primitive(dul.primitive)

    dul.socket.send(dul.pdu.encode())
    evt.trigger(dul.assoc, evt.EVT_PDU_SENT, {'pdu' : dul.pdu})
    dul.artim_timer.start()

    return 'Sta13'


def DT_1(dul):
    """Data transfer DT-1.

    On receiving a P-DATA request, send P-DATA-TF

    State-event triggers: Sta6 + Evt9

    Parameters
    ----------
    dul : dul.DULServiceProvider
        The DICOM Upper Layer Service instance for the local AE

    Returns
    -------
    str
        ``'Sta6'``, the next state of the state machine
    """
    # Send P-DATA-TF PDU
    dul.pdu = P_DATA_TF()
    dul.pdu.from_primitive(dul.primitive)
    dul.primitive = None  # Why this?

    dul.socket.send(dul.pdu.encode())
    evt.trigger(dul.assoc, evt.EVT_PDU_SENT, {'pdu' : dul.pdu})

    return 'Sta6'

def DT_2(dul):
    """Data transfer DT-2.

    On receiving a P-DATA-TF request, send P-DATA indication

    State-event triggers: Sta6 + Evt10

    Parameters
    ----------
    dul : dul.DULServiceProvider
        The DICOM Upper Layer Service instance for the local AE

    Returns
    -------
    str
        ``'Sta6'``, the next state of the state machine
    """
    # Send P-DATA indication primitive directly to DIMSE for processing
    dul.assoc.dimse.receive_primitive(dul.primitive)

    return 'Sta6'


def AR_1(dul):
    """Association release AR-1.

    Send Association release request

    State-event triggers: Sta6 + Evt11

    Parameters
    ----------
    dul : dul.DULServiceProvider
        The DICOM Upper Layer Service instance for the local AE

    Returns
    -------
    str
        ``'Sta7'``, the next state of the state machine
    """
    # Send A-RELEASE-RQ PDU
    dul.pdu = A_RELEASE_RQ()
    dul.pdu.from_primitive(dul.primitive)

    dul.socket.send(dul.pdu.encode())
    evt.trigger(dul.assoc, evt.EVT_PDU_SENT, {'pdu' : dul.pdu})

    return 'Sta7'

def AR_2(dul):
    """Association release AR-2.

    On receiving an association release request, send release indication

    State-event triggers: Sta6 + Evt12

    Parameters
    ----------
    dul : dul.DULServiceProvider
        The DICOM Upper Layer Service instance for the local AE

    Returns
    -------
    str
        ``'Sta8'``, the next state of the state machine
    """
    # Send A-RELEASE indication primitive
    dul.to_user_queue.put(dul.primitive)

    return 'Sta8'

def AR_3(dul):
    """Association release AR-3.

    On receiving an association release response, send release confirmation,
    close connection and go back to Idle state

    State-event triggers: Sta7 + Evt13, Sta11 + Evt13

    Parameters
    ----------
    dul : dul.DULServiceProvider
        The DICOM Upper Layer Service instance for the local AE

    Returns
    -------
    str
        ``'Sta1'``, the next state of the state machine
    """
    # Issue A-RELEASE confirmation primitive and close transport connection
    dul.to_user_queue.put(dul.primitive)
    dul.socket.close()

    assoc = dul.assoc
    remote = assoc.acceptor if assoc.is_requestor else assoc.requestor

    address = (remote.address, remote.port)
    evt.trigger(dul.assoc, evt.EVT_CONN_CLOSE, {'address' : address})

    dul.kill_dul()

    return 'Sta1'

def AR_4(dul):
    """Association release AR-4.

    On receiving an association release response, send release response

    State-event triggers: Sta8 + Evt14, Sta12 + Evt14

    Parameters
    ----------
    dul : dul.DULServiceProvider
        The DICOM Upper Layer Service instance for the local AE

    Returns
    -------
    str
        ``'Sta13'``, the next state of the state machine
    """
    # Issue A-RELEASE-RP PDU and start ARTIM timer
    dul.pdu = A_RELEASE_RP()
    dul.pdu.from_primitive(dul.primitive)

    dul.socket.send(dul.pdu.encode())
    evt.trigger(dul.assoc, evt.EVT_PDU_SENT, {'pdu' : dul.pdu})
    dul.artim_timer.start()

    return 'Sta13'

def AR_5(dul):
    """Association release AR-5.

    On receiving transport connection closed, stop the ARTIM timer and go back
    to Idle state

    State-event triggers: Sta13 + Evt17

    Parameters
    ----------
    dul : dul.DULServiceProvider
        The DICOM Upper Layer Service instance for the local AE

    Returns
    -------
    str
        ``'Sta1'``, the next state of the state machine
    """
    assoc = dul.assoc
    remote = assoc.acceptor if assoc.is_requestor else assoc.requestor

    address = (remote.address, remote.port)
    evt.trigger(dul.assoc, evt.EVT_CONN_CLOSE, {'address' : address})

    # Stop ARTIM timer
    dul.artim_timer.stop()
    dul.kill_dul()

    return 'Sta1'

def AR_6(dul):
    """Association release AR-6.

    On receiving P-DATA-TF during attempted association release request
    send P-DATA indication

    State-event triggers: Sta7 + Evt10

    Parameters
    ----------
    dul : dul.DULServiceProvider
        The DICOM Upper Layer Service instance for the local AE

    Returns
    -------
    str
        ``'Sta7'``, the next state of the state machine
    """
    # Issue P-DATA indication
    dul.to_user_queue.put(dul.primitive)

    return 'Sta7'

def AR_7(dul):
    """Association release AR-7.

    On receiving P-DATA request during attempted association release request
    send P-DATA-TF

    State-event triggers: Sta8 + Evt9

    Parameters
    ----------
    dul : dul.DULServiceProvider
        The DICOM Upper Layer Service instance for the local AE

    Returns
    -------
    str
        ``'Sta8'``, the next state of the state machine
    """
    # Issue P-DATA-TF PDU
    dul.pdu = P_DATA_TF()
    dul.pdu.from_primitive(dul.primitive)

    dul.socket.send(dul.pdu.encode())
    evt.trigger(dul.assoc, evt.EVT_PDU_SENT, {'pdu' : dul.pdu})

    return 'Sta8'

def AR_8(dul):
    """Association release AR-8.

    On receiving association release request while local is requesting release
    then issue release collision indication

    State-event triggers: Sta7 + Evt12

    Parameters
    ----------
    dul : dul.DULServiceProvider
        The DICOM Upper Layer Service instance for the local AE

    Returns
    -------
    str
        Either ``'Sta9'`` or ``'Sta10'``, the next state of the state machine
    """
    # Issue A-RELEASE indication (release collision)
    dul.to_user_queue.put(dul.primitive)
    if dul.assoc.is_requestor:
        return 'Sta9'

    return 'Sta10'

def AR_9(dul):
    """Association release AR-9.

    On receiving A-RELEASE primitive, send release response

    State-event triggers: Sta9 + Evt14

    Parameters
    ----------
    dul : dul.DULServiceProvider
        The DICOM Upper Layer Service instance for the local AE

    Returns
    -------
    str
        ``'Sta11'``, the next state of the state machine
    """
    # Send A-RELEASE-RP PDU
    dul.pdu = A_RELEASE_RP()
    dul.pdu.from_primitive(dul.primitive)

    dul.socket.send(dul.pdu.encode())
    evt.trigger(dul.assoc, evt.EVT_PDU_SENT, {'pdu' : dul.pdu})

    return 'Sta11'

def AR_10(dul):
    """Association release AR-10.

    On receiving A-RELEASE-RP, issue release confirmation

    State-event triggers: Sta10 + Evt13

    Parameters
    ----------
    dul : dul.DULServiceProvider
        The DICOM Upper Layer Service instance for the local AE

    Returns
    -------
    str
        ``'Sta12'``, the next state of the state machine
    """
    # Issue A-RELEASE confirmation primitive
    dul.to_user_queue.put(dul.primitive)

    return 'Sta12'


def AA_1(dul):
    """Association abort AA-1.

    If on sending A-ASSOCIATE-RQ we receive an invalid reply, or an abort
    request then abort

    State-event triggers: Sta2 + Evt3/Evt4/Evt10/Evt12/Evt13/Evt19,
    Sta3/Sta5/Sta6/Sta7/Sta8/Sta9/Sta10/Sta11/Sta12 + Evt15

    Parameters
    ----------
    dul : dul.DULServiceProvider
        The DICOM Upper Layer Service instance for the local AE

    Returns
    -------
    str
        ``'Sta13'``, the next state of the state machine
    """
    # Send A-ABORT PDU (service-user source) and start (or restart
    # if already started) ARTIM timer.
    dul.pdu = A_ABORT_RQ()
    dul.pdu.source = 0x00
    # Reason not specified
    dul.pdu.reason_diagnostic = 0x00
    dul.pdu.from_primitive(dul.primitive)

    dul.socket.send(dul.pdu.encode())
    evt.trigger(dul.assoc, evt.EVT_PDU_SENT, {'pdu' : dul.pdu})
    dul.artim_timer.restart()

    return 'Sta13'

def AA_2(dul):
    """Association abort AA-2.

    On receiving an A-ABORT or if the ARTIM timer expires, close connection and
    return to Idle

    State-event triggers: Sta2 + Evt16/Evt18, Sta4 + Evt15, Sta13 + Evt16/Evt18

    Parameters
    ----------
    dul : dul.DULServiceProvider
        The DICOM Upper Layer Service instance for the local AE

    Returns
    -------
    str
        ``'Sta1'``, the next state of the state machine
    """
    # Stop ARTIM timer if running. Close transport connection.
    dul.artim_timer.stop()
    dul.socket.close()

    assoc = dul.assoc
    assoc.dimse.msg_queue.put((None, None))

    remote = assoc.acceptor if assoc.is_requestor else assoc.requestor
    address = (remote.address, remote.port)
    evt.trigger(dul.assoc, evt.EVT_CONN_CLOSE, {'address' : address})

    dul.kill_dul()

    return 'Sta1'

def AA_3(dul):
    """Association abort AA-3.

    On receiving A-ABORT, issue abort indication, close connection and
    return to Idle

    State-event triggers: Sta3/Sta5/Sta6/Sta7/Sta8/Sta9/Sta10/Sta11/Sta12 +
    Evt16

    Parameters
    ----------
    dul : dul.DULServiceProvider
        The DICOM Upper Layer Service instance for the local AE

    Returns
    -------
    str
        ``'Sta1'``, the next state of the state machine
    """
    # If (service-user initiated abort):
    #   - Issue A-ABORT indication and close transport connection.
    # Otherwise (service-dul initiated abort):
    #   - Issue A-P-ABORT indication and close transport connection.
    # This action is triggered by the reception of an A-ABORT PDU
    dul.to_user_queue.put(dul.primitive)
    dul.socket.close()

    assoc = dul.assoc
    assoc.dimse.msg_queue.put((None, None))

    remote = assoc.acceptor if assoc.is_requestor else assoc.requestor
    address = (remote.address, remote.port)
    evt.trigger(dul.assoc, evt.EVT_CONN_CLOSE, {'address' : address})

    dul.kill_dul()

    return 'Sta1'

def AA_4(dul):
    """Association abort AA-4.

    If connection closed, issue A-P-ABORT and return to Idle

    State-event triggers: Sta3/Sta4/Sta5/Sta6/Sta7/Sta8/Sta9/Sta10/Sta11/Sta12
    + Evt17

    Parameters
    ----------
    dul : dul.DULServiceProvider
        The DICOM Upper Layer Service instance for the local AE

    Returns
    -------
    str
        ``'Sta1'``, the next state of the state machine
    """
    assoc = dul.assoc
    assoc.dimse.msg_queue.put((None, None))

    remote = assoc.acceptor if assoc.is_requestor else assoc.requestor
    address = (remote.address, remote.port)
    evt.trigger(dul.assoc, evt.EVT_CONN_CLOSE, {'address' : address})

    # Issue A-P-ABORT indication primitive.
    primitive = A_P_ABORT()
    primitive.provider_reason = 0x00
    dul.to_user_queue.put(primitive)
    dul.kill_dul()

    return 'Sta1'

def AA_5(dul):
    """Association abort AA-5.

    If connection closed during association request, stop ARTIM timer and
    return to Idle

    State-event triggers: Sta2 + Evt17

    Parameters
    ----------
    dul : dul.DULServiceProvider
        The DICOM Upper Layer Service instance for the local AE

    Returns
    -------
    str
        ``'Sta1'``, the next state of the state machine
    """
    assoc = dul.assoc
    remote = assoc.acceptor if assoc.is_requestor else assoc.requestor

    address = (remote.address, remote.port)
    evt.trigger(dul.assoc, evt.EVT_CONN_CLOSE, {'address' : address})

    # Stop ARTIM timer.
    dul.artim_timer.stop()
    dul.kill_dul()

    return 'Sta1'

def AA_6(dul):
    """Association abort AA-6.

    If receive a PDU while waiting for connection to close, ignore it

    State-event triggers: Sta13 + Evt3/Evt4/Evt10/Evt12/Evt13

    Parameters
    ----------
    dul : dul.DULServiceProvider
        The DICOM Upper Layer Service instance for the local AE

    Returns
    -------
    str
        ``'Sta13'``, the next state of the state machine
    """
    # Ignore PDU
    dul.primitive = None

    return 'Sta13'

def AA_7(dul):
    """Association abort AA-7.

    If receive a association request or invalid PDU while waiting for
    connection to close, send A-ABORT PDU

    State-event triggers: Sta13 + Evt6/Evt19

    Parameters
    ----------
    dul : dul.DULServiceProvider
        The DICOM Upper Layer Service instance for the local AE

    Returns
    -------
    str
        ``'Sta13'``, the next state of the state machine
    """
    primitive = A_P_ABORT()
    primitive.provider_reason = 0x02

    # Send A-ABORT PDU.
    pdu = A_ABORT_RQ()
    pdu.from_primitive(primitive)

    dul.socket.send(dul.pdu.encode())
    evt.trigger(dul.assoc, evt.EVT_PDU_SENT, {'pdu' : dul.pdu})

    return 'Sta13'

def AA_8(dul):
    """Association abort AA-8.

    If receive invalid event, send A-ABORT, issue A-P-ABORT indication and
    start ARTIM timer

    State-event triggers: Evt3 + Sta3/6/7/8/9/10/11/12,
    Evt4 + Sta3/5/6/7/8/9/10/11/12, Evt6 + Sta3/5/6/7/8/9/10/11/12,
    Evt10 + Sta3/5/8/9/10/11/12, Evt12 + Sta3/5/8/9/10/11/12,
    Evt13 + Sta3/5/6/8/9/12, Evt19 + Sta3/5/6/7/8/9/10/11/12

    Parameters
    ----------
    dul : dul.DULServiceProvider
        The DICOM Upper Layer Service instance for the local AE

    Returns
    -------
    str
        ``'Sta13'``, the next state of the state machine
    """
    # Send A-ABORT PDU (service-dul source), issue A-P-ABORT
    # indication, and start ARTIM timer.
    dul.pdu = A_ABORT_RQ()
    dul.pdu.source = 0x02
    dul.pdu.reason_diagnostic = 0x00

    dul.primitive = dul.pdu.to_primitive()
    dul.primitive.abort_source = 0x02
    dul.primitive.result = 0x01
    dul.primitive.diagnostic = 0x01

    dul.socket.send(dul.pdu.encode())
    evt.trigger(dul.assoc, evt.EVT_PDU_SENT, {'pdu' : dul.pdu})

    # Issue A-P-ABORT to user
    primitive = A_P_ABORT()
    primitive.provider_reason = 0x05
    dul.to_user_queue.put(primitive)
    dul.artim_timer.start()

    return 'Sta13'


# Finite State Machine
# Machine State Defintions, PS3.8 Tables 9-1, 9-2, 9-3, 9-4, 9-5
# pylint: disable=line-too-long
STATES = {
    'Sta1': 'Idle',
    # Association establishment
    'Sta2': 'Transport connection open (Awaiting A-ASSOCIATE-RQ PDU)',
    'Sta3': 'Awaiting local A-ASSOCIATE response primitive (from local user)',
    'Sta4': 'Awaiting transport connection opening to complete (from local transport service',
    'Sta5': 'Awaiting A-ASSOCIATE-AC or A-ASSOCIATE-RJ PDU',
    # Data transfer
    'Sta6': 'Association established and ready for data transfer',
    # Association release
    'Sta7': 'Awaiting A-RELEASE-RP PDU',
    'Sta8': 'Awaiting local A-RELEASE response primitive (from local user)',
    'Sta9': 'Release collision requestor side; awaiting A-RELEASE response (from local user)',
    'Sta10': 'Release collision acceptor side; awaiting A-RELEASE-RP PDU',
    'Sta11': 'Release collision requestor side; awaiting A-RELEASE-RP PDU',
    'Sta12': 'Release collision acceptor side; awaiting A-RELEASE response primitive (from local user)',
    'Sta13': 'Awaiting Transport Connection Close Indication (Association no longer exists)'
}

# State Machine Action Definitions, PS3.8 Tables 9-6, 9-7, 9-8, 9-9
ACTIONS = {
    'AE-1': (
        'Issue TRANSPORT CONNECT request primitive to local transport service',
        AE_1,
        'Sta4'
    ),
    'AE-2': ('Send A-ASSOCIATE-RQ-PDU', AE_2, 'Sta5'),
    'AE-3': (
        'Issue A-ASSOCIATE confirmation (accept) primitive', AE_3, 'Sta6'
    ),
    'AE-4': (
        'Issue A-ASSOCIATE confirmation (reject) primitive and close '
        'transport connection',
        AE_4,
        'Sta1'
    ),
    'AE-5': (
        'Issue Transport connection response primitive; start ARTIM timer',
        AE_5,
        'Sta2'
    ),
    'AE-6': (
        'Stop ARTIM timer and if A-ASSOCIATE-RQ acceptable by '
        'service-dul: issue A-ASSOCIATE indication primitive '
        'otherwise issue A-ASSOCIATE-RJ-PDU and start ARTIM timer',
        AE_6,
        ('Sta3', 'Sta13')
    ),
    'AE-7': ('Send A-ASSOCIATE-AC PDU', AE_7, 'Sta6'),
    'AE-8': ('Send A-ASSOCIATE-RJ PDU and start ARTIM timer', AE_8, 'Sta13'),
    # Data transfer related actions
    'DT-1': ('Send P-DATA-TF PDU', DT_1, 'Sta6'),
    'DT-2': ('Send P-DATA indication primitive', DT_2, 'Sta6'),
    # Assocation Release related actions
    'AR-1': ('Send A-RELEASE-RQ PDU', AR_1, 'Sta7'),
    'AR-2': ('Issue A-RELEASE indication primitive', AR_2, 'Sta8'),
    'AR-3': (
        'Issue A-RELEASE confirmation primitive and close '
        'transport connection',
        AR_3,
        'Sta1'
    ),
    'AR-4': (
        'Issue A-RELEASE-RP PDU and start ARTIM timer', AR_4, 'Sta13'
    ),
    'AR-5': ('Stop ARTIM timer', AR_5, 'Sta1'),
    'AR-6': ('Issue P-DATA indication', AR_6, 'Sta7'),
    'AR-7': ('Issue P-DATA-TF PDU', AR_7, 'Sta8'),
    'AR-8': (
        'Issue A-RELEASE indication (release collision): if '
        'association-requestor, next state is Sta9, if not next '
        'state is Sta10',
        AR_8,
        ('Sta9', 'Sta10')
    ),
    'AR-9': ('Send A-RELEASE-RP PDU', AR_9, 'Sta11'),
    'AR-10': ('Issue A-RELEASE confimation primitive', AR_10, 'Sta12'),
    # Association abort related actions
    'AA-1': (
        'Send A-ABORT PDU (service-user source) and start (or '
        'restart if already started) ARTIM timer',
        AA_1,
        'Sta13'
    ),
    'AA-2': (
        'Stop ARTIM timer if running. Close transport connection', AA_2, 'Sta1'
    ),
    'AA-3': (
        'If (service-user initiated abort): issue A-ABORT '
        'indication and close transport connection, otherwise '
        '(service-dul initiated abort): issue A-P-ABORT indication '
        'and close transport connection',
        AA_3,
        'Sta1'
    ),
    'AA-4': ('Issue A-P-ABORT indication primitive', AA_4, 'Sta1'),
    'AA-5': ('Stop ARTIM timer', AA_5, 'Sta1'),
    'AA-6': ('Ignore PDU', AA_6, 'Sta13'),
    'AA-7': ('Send A-ABORT PDU', AA_7, 'Sta13'),
    'AA-8': (
        'Send A-ABORT PDU (service-dul source), issue an A-P-ABORT '
        'indication and start ARTIM timer',
        AA_8,
        'Sta13'
    )
}

# State Machine Event Definitions, PS3.8 Table 9-10
EVENTS = {
    'Evt1': "A-ASSOCIATE request (local user)",
    'Evt2': "Transport connect confirmation (local transport service)",
    'Evt3': "A-ASSOCIATE-AC PDU (received on transport connection)",
    'Evt4': "A-ASSOCIATE-RJ PDU (received on transport connection)",
    'Evt5': "Transport connection indication (local transport service)",
    'Evt6': "A-ASSOCIATE-RQ PDU (on tranport connection)",
    'Evt7': "A-ASSOCIATE response primitive (accept)",
    'Evt8': "A-ASSOCIATE response primitive (reject)",
    'Evt9': "P-DATA request primitive",
    'Evt10': "P-DATA-TF PDU (on transport connection)",
    'Evt11': "A-RELEASE request primitive",
    'Evt12': "A-RELEASE-RQ PDU (on transport)",
    'Evt13': "A-RELEASE-RP PDU (on transport)",
    'Evt14': "A-RELEASE response primitive",
    'Evt15': "A-ABORT request primitive",
    'Evt16': "A-ABORT PDU (on transport)",
    'Evt17': "Transport connection closed indication (local transport service)",
    'Evt18': "ARTIM timer expired (Association reject/release timer)",
    'Evt19': "Unrecognized or invalid PDU received"
}

# State Machine Transitions, PS3.8 Table 9-10
TRANSITION_TABLE = {
    ('Evt1', 'Sta1'): 'AE-1',
    ('Evt2', 'Sta4'): 'AE-2',
    ('Evt3', 'Sta2'): 'AA-1',
    ('Evt3', 'Sta3'): 'AA-8',
    ('Evt3', 'Sta5'): 'AE-3',
    ('Evt3', 'Sta6'): 'AA-8',
    ('Evt3', 'Sta7'): 'AA-8',
    ('Evt3', 'Sta8'): 'AA-8',
    ('Evt3', 'Sta9'): 'AA-8',
    ('Evt3', 'Sta10'): 'AA-8',
    ('Evt3', 'Sta11'): 'AA-8',
    ('Evt3', 'Sta12'): 'AA-8',
    ('Evt3', 'Sta13'): 'AA-6',
    ('Evt4', 'Sta2'): 'AA-1',
    ('Evt4', 'Sta3'): 'AA-8',
    ('Evt4', 'Sta5'): 'AE-4',
    ('Evt4', 'Sta6'): 'AA-8',
    ('Evt4', 'Sta7'): 'AA-8',
    ('Evt4', 'Sta8'): 'AA-8',
    ('Evt4', 'Sta9'): 'AA-8',
    ('Evt4', 'Sta10'): 'AA-8',
    ('Evt4', 'Sta11'): 'AA-8',
    ('Evt4', 'Sta12'): 'AA-8',
    ('Evt4', 'Sta13'): 'AA-6',
    ('Evt5', 'Sta1'): 'AE-5',
    ('Evt6', 'Sta2'): 'AE-6',
    ('Evt6', 'Sta3'): 'AA-8',
    ('Evt6', 'Sta5'): 'AA-8',
    ('Evt6', 'Sta6'): 'AA-8',
    ('Evt6', 'Sta7'): 'AA-8',
    ('Evt6', 'Sta8'): 'AA-8',
    ('Evt6', 'Sta9'): 'AA-8',
    ('Evt6', 'Sta10'): 'AA-8',
    ('Evt6', 'Sta11'): 'AA-8',
    ('Evt6', 'Sta12'): 'AA-8',
    ('Evt6', 'Sta13'): 'AA-7',
    ('Evt7', 'Sta3'): 'AE-7',
    ('Evt8', 'Sta3'): 'AE-8',
    ('Evt9', 'Sta6'): 'DT-1',
    ('Evt9', 'Sta8'): 'AR-7',
    ('Evt10', 'Sta2'): 'AA-1',
    ('Evt10', 'Sta3'): 'AA-8',
    ('Evt10', 'Sta5'): 'AA-8',
    ('Evt10', 'Sta6'): 'DT-2',
    ('Evt10', 'Sta7'): 'AR-6',
    ('Evt10', 'Sta8'): 'AA-8',
    ('Evt10', 'Sta9'): 'AA-8',
    ('Evt10', 'Sta10'): 'AA-8',
    ('Evt10', 'Sta11'): 'AA-8',
    ('Evt10', 'Sta12'): 'AA-8',
    ('Evt10', 'Sta13'): 'AA-6',
    ('Evt11', 'Sta6'): 'AR-1',
    ('Evt12', 'Sta2'): 'AA-1',
    ('Evt12', 'Sta3'): 'AA-8',
    ('Evt12', 'Sta5'): 'AA-8',
    ('Evt12', 'Sta6'): 'AR-2',
    ('Evt12', 'Sta7'): 'AR-8',
    ('Evt12', 'Sta8'): 'AA-8',
    ('Evt12', 'Sta9'): 'AA-8',
    ('Evt12', 'Sta10'): 'AA-8',
    ('Evt12', 'Sta11'): 'AA-8',
    ('Evt12', 'Sta12'): 'AA-8',
    ('Evt12', 'Sta13'): 'AA-6',
    ('Evt13', 'Sta2'): 'AA-1',
    ('Evt13', 'Sta3'): 'AA-8',
    ('Evt13', 'Sta5'): 'AA-8',
    ('Evt13', 'Sta6'): 'AA-8',
    ('Evt13', 'Sta7'): 'AR-3',
    ('Evt13', 'Sta8'): 'AA-8',
    ('Evt13', 'Sta9'): 'AA-8',
    ('Evt13', 'Sta10'): 'AR-10',
    ('Evt13', 'Sta11'): 'AR-3',
    ('Evt13', 'Sta12'): 'AA-8',
    ('Evt13', 'Sta13'): 'AA-6',
    ('Evt14', 'Sta8'): 'AR-4',
    ('Evt14', 'Sta9'): 'AR-9',
    ('Evt14', 'Sta12'): 'AR-4',
    ('Evt15', 'Sta3'): 'AA-1',
    ('Evt15', 'Sta4'): 'AA-2',
    ('Evt15', 'Sta5'): 'AA-1',
    ('Evt15', 'Sta6'): 'AA-1',
    ('Evt15', 'Sta7'): 'AA-1',
    ('Evt15', 'Sta8'): 'AA-1',
    ('Evt15', 'Sta9'): 'AA-1',
    ('Evt15', 'Sta10'): 'AA-1',
    ('Evt15', 'Sta11'): 'AA-1',
    ('Evt15', 'Sta12'): 'AA-1',
    ('Evt16', 'Sta2'): 'AA-2',
    ('Evt16', 'Sta3'): 'AA-3',
    ('Evt16', 'Sta5'): 'AA-3',
    ('Evt16', 'Sta6'): 'AA-3',
    ('Evt16', 'Sta7'): 'AA-3',
    ('Evt16', 'Sta8'): 'AA-3',
    ('Evt16', 'Sta9'): 'AA-3',
    ('Evt16', 'Sta10'): 'AA-3',
    ('Evt16', 'Sta11'): 'AA-3',
    ('Evt16', 'Sta12'): 'AA-3',
    ('Evt16', 'Sta13'): 'AA-2',
    ('Evt17', 'Sta2'): 'AA-5',
    ('Evt17', 'Sta3'): 'AA-4',
    ('Evt17', 'Sta4'): 'AA-4',
    ('Evt17', 'Sta5'): 'AA-4',
    ('Evt17', 'Sta6'): 'AA-4',
    ('Evt17', 'Sta7'): 'AA-4',
    ('Evt17', 'Sta8'): 'AA-4',
    ('Evt17', 'Sta9'): 'AA-4',
    ('Evt17', 'Sta10'): 'AA-4',
    ('Evt17', 'Sta11'): 'AA-4',
    ('Evt17', 'Sta12'): 'AA-4',
    ('Evt17', 'Sta13'): 'AR-5',
    ('Evt18', 'Sta2'): 'AA-2',
    ('Evt18', 'Sta13'): 'AA-2',
    ('Evt19', 'Sta2'): 'AA-1',
    ('Evt19', 'Sta3'): 'AA-8',
    ('Evt19', 'Sta5'): 'AA-8',
    ('Evt19', 'Sta6'): 'AA-8',
    ('Evt19', 'Sta7'): 'AA-8',
    ('Evt19', 'Sta8'): 'AA-8',
    ('Evt19', 'Sta9'): 'AA-8',
    ('Evt19', 'Sta10'): 'AA-8',
    ('Evt19', 'Sta11'): 'AA-8',
    ('Evt19', 'Sta12'): 'AA-8',
    ('Evt19', 'Sta13'): 'AA-7'
}
