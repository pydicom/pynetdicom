#
# Copyright (c) 2012 Patrice Munger
# This file is part of pynetdicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pynetdicom.googlecode.com

import logging
import socket

from pynetdicom.PDU import *
from pynetdicom.DIMSEmessages import wrap_list
import pynetdicom.DULparameters


logger = logging.getLogger('netdicom.FSM')


def AE_1(provider):
    """
    Association establishment action AE-1

    From Idle state, local AE issues a connection request to a remote. This
    is the first step in associating a local AE (requestor) to a remote AE
    (acceptor).

    State-event triggers: Sta1 + Evt1

    .. [1] DICOM Standard 2015b, PS3.8, Table 9-7, "Associate Establishment 
        Related Actions"

    Parameters
    ----------
    provider - DULServiceProvider
        The DICOM Upper Layer Service Provider instance for the local AE

    Returns
    -------
    str
        Sta4, the next state of the state machine
    """
    # Issue TRANSPORT CONNECT request primitive to local transport service
    provider.RemoteClientSocket = socket.socket(socket.AF_INET, 
                                                socket.SOCK_STREAM)
    try:
        provider.RemoteClientSocket.connect(
            provider.primitive.CalledPresentationAddress)
    except socket.error:
        # cannot connect
        provider.ToServiceUser.put(None)
        
    return 'Sta4'

def AE_2(provider):
    """
    Association establishment action AE-2

    On receiving connection confirmation, send A-ASSOCIATE-RQ to the peer AE
    This send a byte stream with the format given by Table 9-11

    State-event triggers: Sta4 + Evt2
    
    .. [1] DICOM Standard 2015b, PS3.8, Table 9-7, "Associate Establishment 
        Related Actions"

    Parameters
    ----------
    provider - DULServiceProvider
        The DICOM Upper Layer Service Provider instance for the local AE

    Returns
    -------
    str
        Sta5, the next state of the state machine
    """
    # Send A-ASSOCIATE-RQ PDU
    provider.pdu = A_ASSOCIATE_RQ_PDU()
    provider.pdu.FromParams(provider.primitive)
    bytestream = provider.pdu.Encode()
    #print("AE-2")
    #print(wrap_list(bytestream))
    provider.RemoteClientSocket.send(bytestream)
    
    return 'Sta5'

def AE_3(provider):
    """
    Association establishment action AE-3

    On receiving A-ASSOCIATE-AC, issue acceptance confirmation

    State-event triggers: Sta5 + Evt3

    .. [1] DICOM Standard 2015b, PS3.8, Table 9-7, "Associate Establishment 
        Related Actions"

    Parameters
    ----------
    provider - DULServiceProvider
        The DICOM Upper Layer Service Provider instance for the local AE

    Returns
    -------
    str
        Sta6, the next state of the state machine
    """
    # Issue A-ASSOCIATE confirmation (accept) primitive
    provider.ToServiceUser.put(provider.primitive)
    
    return 'Sta6'

def AE_4(provider):
    """
    Association establishment action AE-4

    On receiving A-ASSOCIATE-RJ, issue rejection confirmation and close 
    connection

    State-event triggers: Sta5 + Evt4

    .. [1] DICOM Standard 2015b, PS3.8, Table 9-7, "Associate Establishment 
        Related Actions"

    Parameters
    ----------
    provider - DULServiceProvider
        The DICOM Upper Layer Service Provider instance for the local AE

    Returns
    -------
    str
        Sta1, the next state of the state machine
    """
    # Issue A-ASSOCIATE confirmation (reject) primitive and close transport
    # connection
    provider.ToServiceUser.put(provider.primitive)
    provider.RemoteClientSocket.close()
    provider.RemoteClientSocket = None
    
    return 'Sta1'

def AE_5(provider):
    """
    Association establishment action AE-5

    From Idle state, on receiving a remote connection attempt, respond and 
    start ARTIM. This is the first step in associating a remote AE (requestor)
    to the local AE (acceptor).

    State-event triggers: Sta1 + Evt5

    .. [1] DICOM Standard 2015b, PS3.8, Table 9-7, "Associate Establishment 
        Related Actions"

    Parameters
    ----------
    provider - DULServiceProvider
        The DICOM Upper Layer Service Provider instance for the local AE
    
    Returns
    -------
    str
        Sta2, the next state of the state machine
    """
    # Issue connection response primitive
    # not required due to implementation
    pass

    # Start ARTIM timer
    provider.Timer.start()
    
    return 'Sta2'

def AE_6(provider):
    """
    Association establishment action AE-6

    On receiving an A-ASSOCIATE-RQ either accept or reject the association

    State-event triggers: Sta2 + Evt6

    .. [1] DICOM Standard 2015b, PS3.8, Table 9-7, "Associate Establishment 
        Related Actions"

    Parameters
    ----------
    provider - DULServiceProvider
        The DICOM Upper Layer Service Provider instance for the local AE

    Returns
    -------
    str
        Either Sta3 or Sta13, the next state of the state machine
    """
    # Stop ARTIM timer
    provider.Timer.stop()

    # If A-ASSOCIATE-RQ acceptable by service provider
    if True:
        # Issue A-ASSOCIATE indication primitive and move to Sta3
        provider.ToServiceUser.put(provider.primitive)

        return 'Sta3'
    else:
        # Issue A-ASSOCIATE-RJ PDU, start ARTIM timer and move to Sta13
        raise NotImplementedError('State machine - AE-6 A-ASSOCIATE-RQ not '
            'acceptable, but issuance of A-ASSOCIATE-RJ not implemented')
        
        provider.Timer.start()
        return 'Sta13'

def AE_7(provider):
    """
    Association establishment action AE-7

    On receiving association request acceptance, issue A-ASSOCIATE-AC

    State-event triggers: Sta3 + Evt7

    .. [1] DICOM Standard 2015b, PS3.8, Table 9-7, "Associate Establishment 
        Related Actions"

    Parameters
    ----------
    provider - DULServiceProvider
        The DICOM Upper Layer Service Provider instance for the local AE

    Returns
    -------
    str
        Sta6, the next state of the state machine
    """
    # Send A-ASSOCIATE-AC PDU
    provider.pdu = A_ASSOCIATE_AC_PDU()
    provider.pdu.FromParams(provider.primitive)
    provider.RemoteClientSocket.send(provider.pdu.Encode())
    
    return 'Sta6'

def AE_8(provider):
    """
    Association establishment action AE-8

    On receiving association request rejection, issue A-ASSOCIATE-RJ

    State-event triggers: Sta3 + Evt8

    .. [1] DICOM Standard 2015b, PS3.8, Table 9-7, "Associate Establishment 
        Related Actions"

    Parameters
    ----------
    provider - DULServiceProvider
        The DICOM Upper Layer Service Provider instance for the local AE

    Returns
    -------
    str
        Sta13, the next state of the state machine
    """
    # Send A-ASSOCIATE-RJ PDU and start ARTIM timer
    provider.pdu = A_ASSOCIATE_RJ_PDU()
    
    # not sure about this ...
    if provider.primitive.Diagnostic is not None:
        provider.primitive.ResultSource = provider.primitive.Diagnostic.source
    #else:
    #    provider.primitive.Diagnostic = 1
    #    provider.primitive.ResultSource = 2

    provider.pdu.FromParams(provider.primitive)
    provider.RemoteClientSocket.send(provider.pdu.Encode())
    
    return 'Sta13'


def DT_1(provider):
    """
    Data transfer DT-1

    On receiving a P-DATA request, send P-DATA-TF

    State-event triggers: Sta6 + Evt9

    .. [1] DICOM Standard 2015b, PS3.8, Table 9-7, "Data Transfer Related 
        Actions"

    Parameters
    ----------
    provider - DULServiceProvider
        The DICOM Upper Layer Service Provider instance for the local AE

    Returns
    -------
    str
        Sta6, the next state of the state machine
    """
    # Send P-DATA-TF PDU
    provider.pdu = P_DATA_TF_PDU()
    provider.pdu.FromParams(provider.primitive)
    provider.primitive = None
    bytestream = provider.pdu.Encode()
    #print("DT-1")
    #print(wrap_list(bytestream))
    provider.RemoteClientSocket.send(bytestream)
    #provider.RemoteClientSocket.send(provider.pdu.Encode())
    
    return 'Sta6'

def DT_2(provider):
    """
    Data transfer DT-2

    On receiving a P-DATA-TF request, send P-DATA indication

    State-event triggers: Sta6 + Evt10

    .. [1] DICOM Standard 2015b, PS3.8, Table 9-7, "Data Transfer Related 
        Actions"

    Parameters
    ----------
    provider - DULServiceProvider
        The DICOM Upper Layer Service Provider instance for the local AE

    Returns
    -------
    str
        Sta6, the next state of the state machine
    """
    # Send P-DATA indication primitive
    #print("DT-2")
    #print(wrap_list(provider.primitive))
    provider.ToServiceUser.put(provider.primitive)

    return 'Sta6'


def AR_1(provider):
    """
    Association release AR-1

    Send Association release request

    State-event triggers: Sta6 + Evt11

    .. [1] DICOM Standard 2015b, PS3.8, Table 9-8, "Associate Release 
        Related Actions"

    Parameters
    ----------
    provider - DULServiceProvider
        The DICOM Upper Layer Service Provider instance for the local AE

    Returns
    -------
    str
        Sta7, the next state of the state machine
    """
    # Send A-RELEASE-RQ PDU
    provider.pdu = A_RELEASE_RQ_PDU()
    provider.pdu.FromParams(provider.primitive)
    bytestream = provider.pdu.Encode()
    #print("AR-1")
    #print(wrap_list(bytestream))
    provider.RemoteClientSocket.send(provider.pdu.Encode())
    
    return 'Sta7'

def AR_2(provider):
    """
    Association release AR-2

    On receiving an association release request, send release indication

    State-event triggers: Sta6 + Evt12

    .. [1] DICOM Standard 2015b, PS3.8, Table 9-8, "Associate Release 
        Related Actions"

    Parameters
    ----------
    provider - DULServiceProvider
        The DICOM Upper Layer Service Provider instance for the local AE

    Returns
    -------
    str
        Sta8, the next state of the state machine
    """
    # Send A-RELEASE indication primitive
    provider.ToServiceUser.put(provider.primitive)
    
    return 'Sta8'

def AR_3(provider):
    """
    Association release AR-3

    On receiving an association release response, send release confirmation,
    close connection and go back to Idle state

    State-event triggers: Sta7 + Evt13, Sta11 + Evt13

    .. [1] DICOM Standard 2015b, PS3.8, Table 9-8, "Associate Release 
        Related Actions"

    Parameters
    ----------
    provider - DULServiceProvider
        The DICOM Upper Layer Service Provider instance for the local AE

    Returns
    -------
    str
        Sta1, the next state of the state machine
    """
    # Issue A-RELEASE confirmation primitive and close transport connection
    provider.ToServiceUser.put(provider.primitive)
    provider.RemoteClientSocket.close()
    provider.RemoteClientSocket = None
    
    return 'Sta1'

def AR_4(provider):
    """
    Association release AR-4

    On receiving an association release response, send release response

    State-event triggers: Sta8 + Evt14, Sta12 + Evt14

    .. [1] DICOM Standard 2015b, PS3.8, Table 9-8, "Associate Release 
        Related Actions"

    Parameters
    ----------
    provider - DULServiceProvider
        The DICOM Upper Layer Service Provider instance for the local AE

    Returns
    -------
    str
        Sta13, the next state of the state machine
    """
    # Issue A-RELEASE-RP PDU and start ARTIM timer
    provider.pdu = A_RELEASE_RP_PDU()
    provider.pdu.FromParams(provider.primitive)
    provider.RemoteClientSocket.send(provider.pdu.Encode())
    provider.Timer.start()
    
    return 'Sta13'

def AR_5(provider):
    """
    Association release AR-5

    On receiving transport connection closed, stop the ARTIM timer and go back
    to Idle state

    State-event triggers: Sta13 + Evt17

    .. [1] DICOM Standard 2015b, PS3.8, Table 9-8, "Associate Release 
        Related Actions"

    Parameters
    ----------
    provider - DULServiceProvider
        The DICOM Upper Layer Service Provider instance for the local AE

    Returns
    -------
    str
        Sta1, the next state of the state machine
    """
    # Stop ARTIM timer
    provider.Timer.stop()
    
    return 'Sta1'

def AR_6(provider):
    """
    Association release AR-6

    On receiving P-DATA-TF during attempted association release request 
    send P-DATA indication

    State-event triggers: Sta7 + Evt10

    .. [1] DICOM Standard 2015b, PS3.8, Table 9-8, "Associate Release 
        Related Actions"

    Parameters
    ----------
    provider - DULServiceProvider
        The DICOM Upper Layer Service Provider instance for the local AE

    Returns
    -------
    str
        Sta7, the next state of the state machine
    """
    # Issue P-DATA indication
    provider.ToServiceUser.put(provider.primitive)
    
    return 'Sta7'

def AR_7(provider):
    """
    Association release AR-7

    On receiving P-DATA request during attempted association release request 
    send P-DATA-TF

    State-event triggers: Sta8 + Evt9

    .. [1] DICOM Standard 2015b, PS3.8, Table 9-8, "Associate Release 
        Related Actions"

    Parameters
    ----------
    provider - DULServiceProvider
        The DICOM Upper Layer Service Provider instance for the local AE

    Returns
    -------
    str
        Sta8, the next state of the state machine
    """
    # Issue P-DATA-TF PDU
    provider.pdu = P_DATA_TF_PDU()
    provider.pdu.FromParams(provider.primitive)
    provider.RemoteClientSocket.send(provider.pdu.Encode())
    
    return 'Sta8'

def AR_8(provider):
    """
    Association release AR-8

    On receiving association release request while local is requesting release
    then issue release collision indication

    State-event triggers: Sta7 + Evt12

    .. [1] DICOM Standard 2015b, PS3.8, Table 9-8, "Associate Release 
        Related Actions"

    Parameters
    ----------
    provider - DULServiceProvider
        The DICOM Upper Layer Service Provider instance for the local AE

    Returns
    -------
    str
        Either Sta9 or Sta10, the next state of the state machine
    """
    # Issue A-RELEASE indication (release collision)
    provider.ToServiceUser.put(provider.primitive)
    if provider.requestor == 1:
        return 'Sta9'
    else:
        return 'Sta10'
    
def AR_9(provider):
    """
    Association release AR-9

    On receiving A-RELEASE primitive, send release response

    State-event triggers: Sta9 + Evt14

    .. [1] DICOM Standard 2015b, PS3.8, Table 9-8, "Associate Release 
        Related Actions"

    Parameters
    ----------
    provider - DULServiceProvider
        The DICOM Upper Layer Service Provider instance for the local AE

    Returns
    -------
    str
        Sta11, the next state of the state machine
    """
    # Send A-RELEASE-RP PDU
    provider.pdu = A_RELEASE_RP_PDU()
    provider.pdu.FromParams(provider.primitive)
    provider.RemoteClientSocket.send(provider.pdu.Encode())
    
    return 'Sta11'

def AR_10(provider):
    """
    Association release AR-10

    On receiving A-RELEASE-RP, issue release confirmation

    State-event triggers: Sta10 + Evt13

    .. [1] DICOM Standard 2015b, PS3.8, Table 9-8, "Associate Release 
        Related Actions"

    Parameters
    ----------
    provider - DULServiceProvider
        The DICOM Upper Layer Service Provider instance for the local AE

    Returns
    -------
    str
        Sta12, the next state of the state machine
    """
    # Issue A-RELEASE confirmation primitive
    provider.ToServiceUser.put(provider.primitive)
    
    return 'Sta12'


def AA_1(provider):
    """
    Association abort AA-1

    If on sending A-ASSOCIATE-RQ we receive an invalid reply, or an abort
    request then abort

    State-event triggers: Sta2 + Evt3/Evt4/Evt10/Evt12/Evt13/Evt19, 
    Sta3/Sta5/Sta6/Sta7/Sta8/Sta9/Sta10/Sta11/Sta12 + Evt15

    .. [1] DICOM Standard 2015b, PS3.8, Table 9-9, "Associate Abort Related 
    Actions"

    Parameters
    ----------
    provider - DULServiceProvider
        The DICOM Upper Layer Service Provider instance for the local AE

    Returns
    -------
    str
        Sta13, the next state of the state machine
    """
    # Send A-ABORT PDU (service-user source) and start (or restart
    # if already started) ARTIM timer.
    provider.pdu = A_ABORT_PDU()
    # CHECK THIS ...
    provider.pdu.AbortSource = 1
    provider.pdu.ReasonDiag = 0
    provider.pdu.FromParams(provider.primitive)
    provider.RemoteClientSocket.send(provider.pdu.Encode())
    
    provider.Timer.restart()
    
    return 'Sta13'

def AA_2(provider):
    """
    Association abort AA-2

    On receiving an A-ABORT or if the ARTIM timer expires, close connection and 
    return to Idle

    State-event triggers: Sta2 + Evt16/Evt18, Sta4 + Evt15, Sta13 + Evt16/Evt18

    .. [1] DICOM Standard 2015b, PS3.8, Table 9-9, "Associate Abort Related 
    Actions"

    Parameters
    ----------
    provider - DULServiceProvider
        The DICOM Upper Layer Service Provider instance for the local AE

    Returns
    -------
    str
        Sta1, the next state of the state machine
    """
    # Stop ARTIM timer if running. Close transport connection.
    provider.Timer.stop()
    provider.RemoteClientSocket.close()
    provider.RemoteClientSocket = None
    
    return 'Sta1'

def AA_3(provider):
    """
    Association abort AA-3

    On receiving A-ABORT, issue abort indication, close connection and 
    return to Idle

    State-event triggers: Sta3/Sta5/Sta6/Sta7/Sta8/Sta9/Sta10/Sta11/Sta12 + 
    Evt16

    .. [1] DICOM Standard 2015b, PS3.8, Table 9-9, "Associate Abort Related 
    Actions"

    Parameters
    ----------
    provider - DULServiceProvider
        The DICOM Upper Layer Service Provider instance for the local AE

    Returns
    -------
    str
        Sta1, the next state of the state machine
    """
    # If (service-user initiated abort):
    #   - Issue A-ABORT indication and close transport connection.
    # Otherwise (service-provider initiated abort):
    #   - Issue A-P-ABORT indication and close transport connection.
    # This action is triggered by the reception of an A-ABORT PDU
    provider.ToServiceUser.put(provider.primitive)
    provider.RemoteClientSocket.close()
    provider.RemoteClientSocket = None
    
    return 'Sta1'

def AA_4(provider):
    """
    Association abort AA-4

    If connection closed, issue A-P-ABORT and return to Idle

    State-event triggers: Sta3/Sta4/Sta5/Sta6/Sta7/Sta8/Sta9/Sta10/Sta11/Sta12 
    + Evt17

    .. [1] DICOM Standard 2015b, PS3.8, Table 9-9, "Associate Abort Related 
    Actions"

    Parameters
    ----------
    provider - DULServiceProvider
        The DICOM Upper Layer Service Provider instance for the local AE

    Returns
    -------
    str
        Sta1, the next state of the state machine
    """
    # Issue A-P-ABORT indication primitive.
    provider.primitive = DULparameters.A_ABORT_ServiceParameters()
    provider.ToServiceUser.put(provider.primitive)
    
    return 'Sta1'

def AA_5(provider):
    """
    Association abort AA-5

    If connection closed during association request, stop ARTIM timer and return
    to Idle

    State-event triggers: Sta2 + Evt17

    .. [1] DICOM Standard 2015b, PS3.8, Table 9-9, "Associate Abort Related 
    Actions"

    Parameters
    ----------
    provider - DULServiceProvider
        The DICOM Upper Layer Service Provider instance for the local AE

    Returns
    -------
    str
        Sta1, the next state of the state machine
    """
    # Stop ARTIM timer.
    provider.Timer.stop()
    
    return 'Sta1'

def AA_6(provider):
    """
    Association abort AA-6

    If receive a PDU while waiting for connection to close, ignore it

    State-event triggers: Sta13 + Evt3/Evt4/Evt10/Evt12/Evt13

    .. [1] DICOM Standard 2015b, PS3.8, Table 9-9, "Associate Abort Related 
    Actions"

    Parameters
    ----------
    provider - DULServiceProvider
        The DICOM Upper Layer Service Provider instance for the local AE

    Returns
    -------
    str
        Sta13, the next state of the state machine
    """
    # Ignore PDU
    provider.primitive = None
    
    return 'Sta13'

def AA_7(provider):
    """
    Association abort AA-7

    If receive a association request or invalid PDU while waiting for connection 
    to close, issue A-ABORT

    State-event triggers: Sta13 + Evt6/Evt19

    .. [1] DICOM Standard 2015b, PS3.8, Table 9-9, "Associate Abort Related 
    Actions"

    Parameters
    ----------
    provider - DULServiceProvider
        The DICOM Upper Layer Service Provider instance for the local AE

    Returns
    -------
    str
        Sta13, the next state of the state machine
    """
    # Send A-ABORT PDU.
    provider.pdu = A_ABORT_PDU()
    provider.pdu.FromParams(provider.primitive)
    provider.RemoteClientSocket.send(provider.pdu.Encode())
    
    return 'Sta13'

def AA_8(provider):
    """
    Association abort AA-8

    If receive invalid event, send A-ABORT, issue A-P-ABORT indication and start
    ARTIM timer

    State-event triggers: Evt3 + Sta3/6/7/8/9/10/11/12,
    Evt4 + Sta3/5/6/7/8/9/10/11/12, Evt6 + Sta3/5/6/7/8/9/10/11/12,
    Evt10 + Sta3/5/8/9/10/11/12, Evt12 + Sta3/5/8/9/10/11/12,
    Evt13 + Sta3/5/6/8/9/12, Evt19 + Sta3/5/6/7/8/9/10/11/12

    .. [1] DICOM Standard 2015b, PS3.8, Table 9-9, "Associate Abort Related 
    Actions"

    Parameters
    ----------
    provider - DULServiceProvider
        The DICOM Upper Layer Service Provider instance for the local AE

    Returns
    -------
    str
        Sta13, the next state of the state machine
    """
    # Send A-ABORT PDU (service-provider source), issue and A-P-ABORT
    # indication, and start ARTIM timer.
    # Send A-ABORT PDU
    provider.pdu = A_ABORT_PDU()
    provider.pdu.Source = 2
    provider.pdu.ReasonDiag = 0  # No reason given
    
    if provider.RemoteClientSocket:
        provider.RemoteClientSocket.send(provider.pdu.Encode())
        # Issue A-P-ABORT indication
        provider.ToServiceUser.put(provider.primitive)
        provider.Timer.start()
        
    return 'Sta13'


# Finite State Machine
# Machine State Defintions, PS3.8 Tables 9-1, 9-2, 9-3, 9-4, 9-5
states = {
    # No association
    'Sta1': 'Idle',
    # Association establishment
    'Sta2': 'Transport connection open (Awaiting A-ASSOCIATE-RQ PDU)',
    'Sta3': 'Awaiting local A-ASSOCIATE response primitive (from local user)',
    'Sta4': 'Awaiting transport connection opening to complete (from local '
            'transport service',
    'Sta5': 'Awaiting A-ASSOCIATE-AC or A-ASSOCIATE-RJ PDU',
    # Data transfer
    'Sta6': 'Association established and ready for data transfer',
    # Association release
    'Sta7': 'Awaiting A-RELEASE-RP PDU',
    'Sta8': 'Awaiting local A-RELEASE response primitive (from local user)',
    'Sta9': 'Release collision requestor side; awaiting A-RELEASE response '
            ' (from local user)',
    'Sta10': 'Release collision acceptor side; awaiting A-RELEASE-RP PDU',
    'Sta11': 'Release collision requestor side; awaiting A-RELEASE-RP PDU',
    'Sta12': 'Release collision acceptor side; awaiting A-RELEASE response '
             'primitive (from local user)',
    'Sta13': 'Awaiting Transport Connection Close Indication (Association no '
             'longer exists)'
}

# State Machine Action Definitions, PS3.8 Tables 9-6, 9-7, 9-8, 9-9
actions = {
    # Association establishment actions
    'AE-1': ('Issue TRANSPORT CONNECT request primitive to local transport '
             'service', AE_1, 'Sta4'),
    'AE-2': ('Send A-ASSOCIATE-RQ-PDU', AE_2, 'Sta5'),
    'AE-3': ('Issue A-ASSOCIATE confirmation (accept) primitive', AE_3,
             'Sta6'),
    'AE-4': ('Issue A-ASSOCIATE confirmation (reject) primitive and close '
             'transport connection', AE_4, 'Sta1'),
    'AE-5': ('Issue Transport connection response primitive; start ARTIM '
             'timer', AE_5, 'Sta2'),
    'AE-6': ('Stop ARTIM timer and if A-ASSOCIATE-RQ acceptable by '
             'service-provider: issue A-ASSOCIATE indication primitive '
             'otherwise issue A-ASSOCIATE-RJ-PDU and start ARTIM timer', AE_6, 
             ('Sta3', 'Sta13')),
    'AE-7': ('Send A-ASSOCIATE-AC PDU', AE_7, 'Sta6'),
    'AE-8': ('Send A-ASSOCIATE-RJ PDU and start ARTIM timer', AE_8, 'Sta13'),
    # Data transfer related actions
    'DT-1': ('Send P-DATA-TF PDU', DT_1, 'Sta6'),
    'DT-2': ('Send P-DATA indication primitive', DT_2, 'Sta6'),
    # Assocation Release related actions
    'AR-1': ('Send A-RELEASE-RQ PDU', AR_1, 'Sta7'),
    'AR-2': ('Issue A-RELEASE indication primitive', AR_2, 'Sta8'),
    'AR-3': ('Issue A-RELEASE confirmation primitive and close transport '
             'connection', AR_3, 'Sta1'),
    'AR-4': ('Issue A-RELEASE-RP PDU and start ARTIM timer', AR_4, 'Sta13'),
    'AR-5': ('Stop ARTIM timer', AR_5, 'Sta1'),
    'AR-6': ('Issue P-DATA indication', AR_6, 'Sta7'),
    'AR-7': ('Issue P-DATA-TF PDU', AR_7, 'Sta8'),
    'AR-8': ('Issue A-RELEASE indication (release collision): if '
             'association-requestor, next state is Sta9, if not next state is '
             'Sta10', AR_8, ('Sta9', 'Sta10')),
    'AR-9': ('Send A-RELEASE-RP PDU', AR_9, 'Sta11'),
    'AR-10': ('Issue A-RELEASE confimation primitive', AR_10, 'Sta12'),
    # Association abort related actions
    'AA-1': ('Send A-ABORT PDU (service-user source) and start (or restart if '
             'already started) ARTIM timer', AA_1, 'Sta13'),
    'AA-2': ('Stop ARTIM timer if running. Close transport connection', AA_2,
             'Sta1'),
    'AA-3': ('If (service-user initiated abort): issue A-ABORT indication and '
             'close transport connection, otherwise (service-provider '
             'initiated abort): issue A-P-ABORT indication and close transport '
             'connection', AA_3, 'Sta1'),
    'AA-4': ('Issue A-P-ABORT indication primitive', AA_4, 'Sta1'),
    'AA-5': ('Stop ARTIM timer', AA_5, 'Sta1'),
    'AA-6': ('Ignore PDU', AA_6, 'Sta13'),
    'AA-7': ('Send A-ABORT PDU', AA_7, 'Sta13'),
    'AA-8': ('Send A-ABORT PDU (service-provider source), issue an A-P-ABORT '
             'indication and start ARTIM timer', AA_8, 'Sta13')
}

# State Machine Event Definitions, PS3.8 Table 9-10
events = {
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
TransitionTable = {
    ('Evt1',  'Sta1'): 'AE-1',

    ('Evt2',  'Sta4'): 'AE-2',

    ('Evt3',  'Sta2'): 'AA-1',
    ('Evt3',  'Sta3'): 'AA-8',
    ('Evt3',  'Sta5'): 'AE-3',
    ('Evt3',  'Sta6'): 'AA-8',
    ('Evt3',  'Sta7'): 'AA-8',
    ('Evt3',  'Sta8'): 'AA-8',
    ('Evt3',  'Sta9'): 'AA-8',
    ('Evt3', 'Sta10'): 'AA-8',
    ('Evt3', 'Sta11'): 'AA-8',
    ('Evt3', 'Sta12'): 'AA-8',
    ('Evt3', 'Sta13'): 'AA-6',

    ('Evt4',  'Sta2'): 'AA-1',
    ('Evt4',  'Sta3'): 'AA-8',
    ('Evt4',  'Sta5'): 'AE-4',
    ('Evt4',  'Sta6'): 'AA-8',
    ('Evt4',  'Sta7'): 'AA-8',
    ('Evt4',  'Sta8'): 'AA-8',
    ('Evt4',  'Sta9'): 'AA-8',
    ('Evt4', 'Sta10'): 'AA-8',
    ('Evt4', 'Sta11'): 'AA-8',
    ('Evt4', 'Sta12'): 'AA-8',
    ('Evt4', 'Sta13'): 'AA-6',

    ('Evt5',  'Sta1'): 'AE-5',

    ('Evt6',  'Sta2'): 'AE-6',
    ('Evt6',  'Sta3'): 'AA-8',
    ('Evt6',  'Sta5'): 'AA-8',
    ('Evt6',  'Sta6'): 'AA-8',
    ('Evt6',  'Sta7'): 'AA-8',
    ('Evt6',  'Sta8'): 'AA-8',
    ('Evt6',  'Sta9'): 'AA-8',
    ('Evt6', 'Sta10'): 'AA-8',
    ('Evt6', 'Sta11'): 'AA-8',
    ('Evt6', 'Sta12'): 'AA-8',
    ('Evt6', 'Sta13'): 'AA-7',

    ('Evt7',  'Sta3'): 'AE-7',

    ('Evt8',  'Sta3'): 'AE-8',

    ('Evt9',  'Sta6'): 'DT-1',
    ('Evt9',  'Sta8'): 'AR-7',

    ('Evt10',  'Sta2'): 'AA-1',
    ('Evt10',  'Sta3'): 'AA-8',
    ('Evt10',  'Sta5'): 'AA-8',
    ('Evt10',  'Sta6'): 'DT-2',
    ('Evt10',  'Sta7'): 'AR-6',
    ('Evt10',  'Sta8'): 'AA-8',
    ('Evt10',  'Sta9'): 'AA-8',
    ('Evt10', 'Sta10'): 'AA-8',
    ('Evt10', 'Sta11'): 'AA-8',
    ('Evt10', 'Sta12'): 'AA-8',
    ('Evt10', 'Sta13'): 'AA-6',

    ('Evt11',  'Sta6'): 'AR-1',

    ('Evt12',  'Sta2'): 'AA-1',
    ('Evt12',  'Sta3'): 'AA-8',
    ('Evt12',  'Sta5'): 'AA-8',
    ('Evt12',  'Sta6'): 'AR-2',
    ('Evt12',  'Sta7'): 'AR-8',
    ('Evt12',  'Sta8'): 'AA-8',
    ('Evt12',  'Sta9'): 'AA-8',
    ('Evt12', 'Sta10'): 'AA-8',
    ('Evt12', 'Sta11'): 'AA-8',
    ('Evt12', 'Sta12'): 'AA-8',
    ('Evt12', 'Sta13'): 'AA-6',

    ('Evt13',  'Sta2'): 'AA-1',
    ('Evt13',  'Sta3'): 'AA-8',
    ('Evt13',  'Sta5'): 'AA-8',
    ('Evt13',  'Sta6'): 'AA-8',
    ('Evt13',  'Sta7'): 'AR-3',
    ('Evt13',  'Sta8'): 'AA-8',
    ('Evt13',  'Sta9'): 'AA-8',
    ('Evt13', 'Sta10'): 'AR-10',
    ('Evt13', 'Sta11'): 'AR-3',
    ('Evt13', 'Sta12'): 'AA-8',
    ('Evt13', 'Sta13'): 'AA-6',

    ('Evt14',  'Sta8'): 'AR-4',
    ('Evt14',  'Sta9'): 'AR-9',
    ('Evt14', 'Sta12'): 'AR-4',

    ('Evt15',  'Sta3'): 'AA-1',
    ('Evt15',  'Sta4'): 'AA-2',
    ('Evt15',  'Sta5'): 'AA-1',
    ('Evt15',  'Sta6'): 'AA-1',
    ('Evt15',  'Sta7'): 'AA-1',
    ('Evt15',  'Sta8'): 'AA-1',
    ('Evt15',  'Sta9'): 'AA-1',
    ('Evt15', 'Sta10'): 'AA-1',
    ('Evt15', 'Sta11'): 'AA-1',
    ('Evt15', 'Sta12'): 'AA-1',

    ('Evt16',  'Sta2'): 'AA-2',
    ('Evt16',  'Sta3'): 'AA-3',
    ('Evt16',  'Sta5'): 'AA-3',
    ('Evt16',  'Sta6'): 'AA-3',
    ('Evt16',  'Sta7'): 'AA-3',
    ('Evt16',  'Sta8'): 'AA-3',
    ('Evt16',  'Sta9'): 'AA-3',
    ('Evt16', 'Sta10'): 'AA-3',
    ('Evt16', 'Sta11'): 'AA-3',
    ('Evt16', 'Sta12'): 'AA-3',
    ('Evt16', 'Sta13'): 'AA-2',

    ('Evt17',  'Sta2'): 'AA-5',
    ('Evt17',  'Sta3'): 'AA-4',
    ('Evt17',  'Sta4'): 'AA-4',
    ('Evt17',  'Sta5'): 'AA-4',
    ('Evt17',  'Sta6'): 'AA-4',
    ('Evt17',  'Sta7'): 'AA-4',
    ('Evt17',  'Sta8'): 'AA-4',
    ('Evt17',  'Sta9'): 'AA-4',
    ('Evt17', 'Sta10'): 'AA-4',
    ('Evt17', 'Sta11'): 'AA-4',
    ('Evt17', 'Sta12'): 'AA-4',
    ('Evt17', 'Sta13'): 'AR-5',

    ('Evt18',  'Sta2'): 'AA-2',
    ('Evt18', 'Sta13'): 'AA-2',

    ('Evt19',  'Sta2'): 'AA-1',
    ('Evt19',  'Sta3'): 'AA-8',
    ('Evt19',  'Sta5'): 'AA-8',
    ('Evt19',  'Sta6'): 'AA-8',
    ('Evt19',  'Sta7'): 'AA-8',
    ('Evt19',  'Sta8'): 'AA-8',
    ('Evt19',  'Sta9'): 'AA-8',
    ('Evt19', 'Sta10'): 'AA-8',
    ('Evt19', 'Sta11'): 'AA-8',
    ('Evt19', 'Sta12'): 'AA-8',
    ('Evt19', 'Sta13'): 'AA-7'
}


class StateMachine:
    """
    Implementation of the DICOM Upper Layer State Machine as per PS3.8 Section
    9.2. 
    
    Parameters
    ---------
    provider - DULServiceProvider
        The DICOM Upper Layer Service Provider instance for the local AE
    
    Attributes
    ----------
    CurrentState - str
        The current state of the state machine, Sta1 to Sta13
    """
    def __init__(self, provider):
        self.CurrentState = 'Sta1'
        self.provider = provider

    def Action(self, event, c):
        """ Execute the action triggered by `event`
        
        Parameters
        ----------
        event - str
            The event to be processed, Evt1 to Evt19
        c - DULServiceProvider
            The DICOM Upper Layer Service Provider instance for the local AE
        """
        
        # Attempt to get the action corresponding to the event-state
        try:
            action_name = TransitionTable[(event, self.CurrentState)]
        except:
            logger.debug('%s: current state is: %s %s' %
                         (self.provider.name, 
                          self.CurrentState,
                          states[self.CurrentState]))
            logger.debug('%s: event: %s %s' %
                         (self.provider.name, event, events[event]))
            raise
            return

        # action is the (description, function, state) tuple
        #   associated with the action_name
        action = actions[action_name]
        
        # Attempt to execute the action and move the state machine to its
        #   next state
        try:
            logger.debug('')
            logger.debug('%s: current state is: %s %s' %
                         (self.provider.name, self.CurrentState,
                          states[self.CurrentState]))
            logger.debug('%s: event: %s %s' %
                         (self.provider.name, event, events[event]))
            logger.debug('%s: entering action: (%s, %s) %s %s' %
                         (self.provider.name, event, self.CurrentState,
                          action_name, actions[action_name][0]))
            
            # Execute the required action 
            next_state = action[1](c)
            
            #print('SM: %s + %s -> %s -> %s' %(self.CurrentState, event, action_name, next_state))
            
            # Move the state machine to the next state
            self.NextState(next_state)    
            
            logger.debug('%s: action complete. State is now %s %s' %
                         (self.provider.name, self.CurrentState,
                          states[self.CurrentState]))
        except:
            raise
            self.provider.Kill()

    def NextState(self, state):
        """
        Transition the state machine to the next state
        
        Parameters
        ----------
        state - str
            The state to transition to, Sta1 to Sta13
            
        Raises
        ------
        ValueError
            If the state is not valid
        """
        # Validate that state is acceptable
        if state in states.keys():
            self.CurrentState = state
        else:
            raise ValueError('Invalid state for State Machine:\n\t %s' %state)
