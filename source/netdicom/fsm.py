#
# Copyright (c) 2012 Patrice Munger
# This file is part of pynetdicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pynetdicom.googlecode.com
#

# Implementation of the OSI Upper Layer Services
# DICOM, Part 8, Section 7
import socket
import PDU
import time
# Finite State machine action definitions

import logging
logger = logging.getLogger('netdicom.FSM')

def AE_1(provider):
    # Issue TRANSPORT CONNECT request primitive to local transport service
    provider.RemoteClientSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    provider.RemoteClientSocket.connect(provider.primitive.CalledPresentationAddress)
        
def AE_2(provider):
    # Send A-ASSOCIATE-RQ PDU
    provider.pdu = PDU.A_ASSOCIATE_RQ_PDU()
    provider.pdu.FromParams(provider.primitive)
    provider.RemoteClientSocket.send(provider.pdu.Encode())

def AE_3(provider):
    # Issue A-ASSOCIATE confirmation (accept) primitive
    provider.ToServiceUser.put(provider.primitive)

def AE_4(provider):
    # Issue A-ASSOCIATE confirmation (reject) primitive and close transport connection
    provider.ToServiceUser.put(provider.primitive)
    provider.RemoteClientSocket.close()
    provider.RemoteClientSocket = None
    
def AE_5(provider):
    # Issue connection response primitive start ARTIM timer
    # Don't need to send this primitive.
    provider.Timer.Start()
    
def AE_6(provider):
    # Stop ARTIM timer and if A-ASSOCIATE-RQ acceptable by service provider
    # - Issue A-ASSOCIATE indication primitive
    provider.Timer.Stop()
    # Accept
    provider.SM.NextState('Sta3')
    provider.ToServiceUser.put(provider.primitive)
    # otherwise????

def AE_7(provider):
    # Send A-ASSOCIATE-AC PDU
    provider.pdu =  PDU.A_ASSOCIATE_AC_PDU()
    provider.pdu.FromParams(provider.primitive)
    provider.RemoteClientSocket.send(provider.pdu.Encode())

def AE_8(provider):
    # Send A-ASSOCIATE-RJ PDU and start ARTIM timer
    provider.pdu =  PDU.A_ASSOCIATE_RJ_PDU()
    # not sure about this ...
    if provider.primitive.Diagnostic is not None:    
        provider.primitive.ResultSource = 1
    else:
        provider.primitive.Diagnostic = 1
        provider.primitive.ResultSource = 2
        
    provider.pdu.FromParams(provider.primitive)
    provider.RemoteClientSocket.send(provider.pdu.Encode())

def DT_1(provider):
    # Send P-DATA-TF PDU
    provider.pdu =  PDU.P_DATA_TF_PDU()
    provider.pdu.FromParams(provider.primitive)
    provider.RemoteClientSocket.send(provider.pdu.Encode())
    
def DT_2(provider):
    # Send P-DATA indication primitive
    provider.ToServiceUser.put(provider.primitive)
    
def AR_1(provider):
    # Send A-RELEASE-RQ PDU
    provider.pdu =  PDU.A_RELEASE_RQ_PDU()
    provider.pdu.FromParams(provider.primitive)
    provider.RemoteClientSocket.send(provider.pdu.Encode())
    
def AR_2(provider):
    # Send A-RELEASE indication primitive
    provider.ToServiceUser.put(provider.primitive)
    
def AR_3(provider):
    # Issue A-RELEASE confirmation primitive and close transport connection
    provider.ToServiceUser.put(provider.primitive)
    provider.RemoteClientSocket.close()
    provider.RemoteClientSocket = None

    
def AR_4(provider):
    # Issue A-RELEASE-RP PDU and start ARTIM timer
    provider.pdu =  PDU.A_RELEASE_RP_PDU()
    provider.pdu.FromParams(provider.primitive)
    provider.RemoteClientSocket.send(provider.pdu.Encode())
    provider.Timer.Start()

def AR_5(provider):
    # Stop ARTIM timer
    provider.Timer.Stop()

def AR_6(provider):
    # Issue P-DATA indication
    provider.ToServiceUser.put(provider.primitive)

def AR_7(provider):
    # Issue P-DATA-TF PDU
    provider.pdu =  PDU.P_DATA_TF_PDU()
    provider.pdu.FromParams(provider.primitive)
    provider.RemoteClientSocket.send(provider.pdu.Encode())
    
def AR_8(provider):
    # Issue A-RELEASE indication (release collision)
    provider.ToServiceUser.put(provider.primitive)
    if provider.requestor == 1:
        provider.SM.NextState('Sta9')
    else:
        provider.SM.NextState('Sta10')

def AR_9(provider):
    # Send A-RELEASE-RP PDU
    provider.pdu =  PDU.A_RELEASE_RP_PDU()
    provider.pdu.FromParams(provider.primitive)
    provider.RemoteClientSocket.send(provider.pdu.Encode())

def AR_10(provider):
    # Issue A-RELEASE confirmation primitive
    provider.ToServiceUser.put(provider.primitive)

def AA_1(provider):
    # Send A-ABORT PDU (service-user source) and start (or restart
    # if already started) ARTIM timer.
    provider.pdu =  PDU.A_ABORT_PDU()
    #### CHECK THIS ...
    provider.pdu.AbortSource=1
    provider.pdu.ReasonDiag=0
    provider.pdu.FromParams(provider.primitive)
    provider.RemoteClientSocket.send(provider.pdu.Encode())
    provider.Timer.Restart()

def AA_2(provider):
    # Stop ARTIM timer if running. Close transport connection.
    provider.Timer.Stop()
    provider.RemoteClientSocket.close()
    provider.RemoteClientSocket = None
    
def AA_3(provider):
    # If (service-user initiated abort):
    #   - Issue A-ABORT indication and close transport connection.
    # Otherwise (service-provider initiated abort):
    #   - Issue A-P-ABORT indication and close transport connection.
    # This action is triggered by the reception of an A-ABORT PDU
    provider.ToServiceUser.put(provider.primitive)
    provider.RemoteClientSocket.close()
    provider.RemoteClientSocket = None


def AA_4(provider):
    # Issue A-P-ABORT indication primitive.
    provider.ToServiceUser.put(provider.primitive)

def AA_5(provider):
    # Stop ARTIM timer.
    provider.Timer.Stop()

    
def AA_6(provider):
    # Ignore PDU.
    provider.primitive = None

def AA_7(provider):
    # Send A-ABORT PDU.
    provider.pdu =  PDU.A_ABORT_PDU()
    provider.pdu.FromParams(provider.primitive)
    provider.RemoteClientSocket.send(provider.pdu.Encode())

def AA_8(provider):
    # Send A-ABORT PDU (service-provider source), issue and A-P-ABORT indication,
    # and start ARTIM timer.
    # Send A-ABORT PDU
    provider.pdu =  PDU.A_ABORT_PDU()
    provider.pdu.Source = 2
    provider.pdu.ReasonDiag = 0 # No reason given
    if provider.RemoteClientSocket:
        provider.RemoteClientSocket.send(provider.pdu.Encode())
        # Issue A-P-ABORT indication
        provider.ToServiceUser.put(provider.primitive)
        provider.Timer.Start()


# Finite State Machine

# states
states = {
    # No association
    'Sta1':'Idle',
    # Association establishment
    'Sta2':'Transport Connection Open (Awaiting A-ASSOCIATE-RQ PDU)',
    'Sta3':'Awaiting Local A-ASSOCIATE response primitive (from local user)',
    'Sta4':'Awaiting transport connection opening to complete (from local transport service',
    'Sta5':'Awaiting A-ASSOCIATE-AC or A-ASSOCIATE-RJ PDU',
    # Data transfer
    'Sta6':'Association established and ready for data transfer',
    # Association release
    'Sta7':'Awaiting A-RELEASE-RP PDU',
    'Sta8':'Awaiting local A-RELEASE response primitive (from local user)',
    'Sta9':'Release collision requestor side; awaiting A-RELEASE response (from local user)',
    'Sta10':'Release collision acceptor side; awaiting A-RELEASE-RP PDU',
    'Sta11':'Release collision requestor side; awaiting A-RELEASE-RP PDU',
    'Sta12':'Release collision acceptor side; awaiting A-RELEASE response primitive (from local user)',
    'Sta13':'Awaiting Transport Connection Close Indication (Association no longer exists)'
    }


# actions
actions = {
    # Association establishment actions
    'AE-1': ('Issue TransportConnect request primitive to local transport service', AE_1,'Sta4'),
    'AE-2': ('Send A_ASSOCIATE-RQ PDU', AE_2, 'Sta5'),
    'AE-3': ('Issue A-ASSOCIATE confirmation (accept) primitive', AE_3, 'Sta6'),
    'AE-4': ('Issue A-ASSOCIATE confirmation (reject) primitive and close transport connection', AE_4, 'Sta1'),
    'AE-5': ('Issue transport connection response primitive; start ARTIM timer', AE_5, 'Sta2'),
    'AE-6': ('Check A-ASSOCIATE-RQ', AE_6, ('Sta3','Sta13')),
    'AE-7': ('Send A-ASSOCIATE-AC PDU', AE_7, 'Sta6'),
    'AE-8': ('Send A-ASSOCIATE-RJ PDU', AE_8, 'Sta13'),
    # Data transfer related actions
    'DT-1': ('Send P-DATA-TF PDU', DT_1, 'Sta6'),
    'DT-2': ('Send P-DATA indication primitive', DT_2, 'Sta6'),
    # Assocation Release related actions
    'AR-1': ('Send A-RELEASE-RQ PDU', AR_1, 'Sta7'),
    'AR-2': ('Send A-RELEASE indication primitive', AR_2, 'Sta8'),
    'AR-3': ('Issue A-RELEASE confirmation primitive and close transport connection', AR_3, 'Sta1'),
    'AR-4': ('Issue A-RELEASE-RP PDU and start ARTIM timer', AR_4, 'Sta13'),
    'AR-5': ('Stop ARTIM timer', AR_5, 'Sta1'),
    'AR-6': ('Issue P-DATA indication', AR_6, 'Sta7'),
    'AR-7': ('Issue P-DATA-TF PDU', AR_7, 'Sta8'),
    'AR-8': ('Issue A-RELEASE indication (release collision)', AR_8, ('Sta9','Sta10')),
    'AR-9': ('Send A-RELEASE-RP PDU', AR_9, 'Sta11'),
    'AR-10': ('Issue A-RELEASE confimation primitive', AR_10, 'Sta12'),
    # Association abort related actions
    'AA-1': ('Send A-ABORT PDU (service-user source) and start (or restart) ARTIM timer', AA_1, 'Sta13'),
    'AA-2': ('Stop ARTIM timer if running. Close transport connection', AA_2, 'Sta1'),
    'AA-3': ('Issue A-ABORT or A-P-ABORT indication and close transport connection', AA_3, 'Sta1'),
    'AA-4': ('Issue A-P-ABORT indication primitive', AA_4, 'Sta1'),
    'AA-5': ('Stop ARTIM timer', AA_5, 'Sta1'),
    'AA-6': ('Ignore PDU', AA_6, 'Sta13'),
    'AA-7': ('Send A-ABORT PDU', AA_6, 'Sta13'),
    'AA-8': ('Send A-ABORT PDU, issue an A-P-ABORT indication and start ARTIM timer', AA_8, 'Sta13')}


# events
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
    'Evt17': "Transport connection closed",
    'Evt18': "ARTIM timer expired (rej/rel)",
    'Evt19': "Unrecognized/invalid PDU"}


TransitionTable = {

    ('Evt1','Sta1'):'AE-1',
    
    ('Evt2','Sta4'):'AE-2',
    
    ('Evt3','Sta2'):'AA-1', 
    ('Evt3','Sta3'):'AA-8', 
    ('Evt3','Sta5'):'AE-3', 
    ('Evt3','Sta6'):'AA-8', 
    ('Evt3','Sta7'):'AA-8',     
    ('Evt3','Sta8'):'AA-8',     
    ('Evt3','Sta9'):'AA-8',     
    ('Evt3','Sta10'):'AA-8',        
    ('Evt3','Sta11'):'AA-8',        
    ('Evt3','Sta12'):'AA-8',        
    ('Evt3','Sta13'):'AA-6',        
    
    ('Evt4','Sta2'):'AA-1', 
    ('Evt4','Sta3'):'AA-8', 
    ('Evt4','Sta5'):'AE-4', 
    ('Evt4','Sta6'):'AA-8', 
    ('Evt4','Sta7'):'AA-8',     
    ('Evt4','Sta8'):'AA-8',     
    ('Evt4','Sta9'):'AA-8',     
    ('Evt4','Sta10'):'AA-8',        
    ('Evt4','Sta11'):'AA-8',        
    ('Evt4','Sta12'):'AA-8',        
    ('Evt4','Sta13'):'AA-6',        
    
    ('Evt5','Sta1'):'AE-5',
    
    ('Evt6','Sta2'):'AE-6', 
    ('Evt6','Sta3'):'AA-8', 
    ('Evt6','Sta5'):'AA-8', 
    ('Evt6','Sta6'):'AA-8', 
    ('Evt6','Sta7'):'AA-8',     
    ('Evt6','Sta8'):'AA-8',     
    ('Evt6','Sta9'):'AA-8',     
    ('Evt6','Sta10'):'AA-8',        
    ('Evt6','Sta11'):'AA-8',        
    ('Evt6','Sta12'):'AA-8',        
    ('Evt6','Sta13'):'AA-7',        
    
    ('Evt7','Sta3'):'AE-7',     
    
    ('Evt8','Sta3'):'AE-8',     
    
    ('Evt9','Sta6'):'DT-1',
    ('Evt9','Sta8'):'AR-7',
    
    ('Evt10','Sta2'):'AA-1',    
    ('Evt10','Sta3'):'AA-8',    
    ('Evt10','Sta5'):'AA-8',    
    ('Evt10','Sta6'):'DT-2',    
    ('Evt10','Sta7'):'AR-6',        
    ('Evt10','Sta8'):'AA-8',        
    ('Evt10','Sta9'):'AA-8',        
    ('Evt10','Sta10'):'AA-8',       
    ('Evt10','Sta11'):'AA-8',       
    ('Evt10','Sta12'):'AA-8',       
    ('Evt10','Sta13'):'AA-6',       
    
    ('Evt11','Sta6'):'AR-1',
    
    ('Evt12','Sta2'):'AA-1',    
    ('Evt12','Sta3'):'AA-8',    
    ('Evt12','Sta5'):'AA-8',    
    ('Evt12','Sta6'):'AR-2',    
    ('Evt12','Sta7'):'AR-8',        
    ('Evt12','Sta8'):'AA-8',        
    ('Evt12','Sta9'):'AA-8',        
    ('Evt12','Sta10'):'AA-8',       
    ('Evt12','Sta11'):'AA-8',       
    ('Evt12','Sta12'):'AA-8',       
    ('Evt12','Sta13'):'AA-6',       
    
    ('Evt13','Sta2'):'AA-1',    
    ('Evt13','Sta3'):'AA-8',    
    ('Evt13','Sta5'):'AA-8',    
    ('Evt13','Sta6'):'AA-8',    
    ('Evt13','Sta7'):'AR-3',        
    ('Evt13','Sta8'):'AA-8',        
    ('Evt13','Sta9'):'AA-8',        
    ('Evt13','Sta10'):'AR-10',      
    ('Evt13','Sta11'):'AR-3',       
    ('Evt13','Sta12'):'AA-8',       
    ('Evt13','Sta13'):'AA-6',
    
    ('Evt14','Sta8'):'AR-4',        
    ('Evt14','Sta9'):'AR-9',        
    ('Evt14','Sta12'):'AR-4',       

    ('Evt15','Sta3'):'AA-1',    
    ('Evt15','Sta4'):'AA-2',    
    ('Evt15','Sta5'):'AA-1',    
    ('Evt15','Sta6'):'AA-1',    
    ('Evt15','Sta7'):'AA-1',        
    ('Evt15','Sta8'):'AA-1',        
    ('Evt15','Sta9'):'AA-1',        
    ('Evt15','Sta10'):'AA-1',       
    ('Evt15','Sta11'):'AA-1',       
    ('Evt15','Sta12'):'AA-1',       
    
    ('Evt16','Sta2'):'AA-2',    
    ('Evt16','Sta3'):'AA-3',    
    ('Evt16','Sta5'):'AA-3',    
    ('Evt16','Sta6'):'AA-3',    
    ('Evt16','Sta7'):'AA-3',        
    ('Evt16','Sta8'):'AA-3',        
    ('Evt16','Sta9'):'AA-3',        
    ('Evt16','Sta10'):'AA-3',       
    ('Evt16','Sta11'):'AA-3',       
    ('Evt16','Sta12'):'AA-3',       
    ('Evt16','Sta13'):'AA-2',
    
    ('Evt17','Sta2'):'AA-5',
    ('Evt17','Sta3'):'AA-4',    
    ('Evt17','Sta4'):'AA-4',    
    ('Evt17','Sta5'):'AA-4',    
    ('Evt17','Sta6'):'AA-4',    
    ('Evt17','Sta7'):'AA-4',        
    ('Evt17','Sta8'):'AA-4',        
    ('Evt17','Sta9'):'AA-4',        
    ('Evt17','Sta10'):'AA-4',       
    ('Evt17','Sta11'):'AA-4',       
    ('Evt17','Sta12'):'AA-4',       
    ('Evt17','Sta13'):'AR-5',
    
    ('Evt18','Sta2'):'AA-2',
    ('Evt18','Sta13'):'AA-2',
    
    ('Evt19','Sta2'):'AA-1',    
    ('Evt19','Sta3'):'AA-8',    
    ('Evt19','Sta5'):'AA-8',    
    ('Evt19','Sta6'):'AA-8',    
    ('Evt19','Sta7'):'AA-8',        
    ('Evt19','Sta8'):'AA-8',        
    ('Evt19','Sta9'):'AA-8',        
    ('Evt19','Sta10'):'AA-8',       
    ('Evt19','Sta11'):'AA-8',       
    ('Evt19','Sta12'):'AA-8',       
    ('Evt19','Sta13'):'AA-7' }

class StateMachine:

    def __init__(self, provider):
        self.CurrentState = 'Sta1'
        self.provider = provider
    def Action(self, event, c):     
        """ Execute the action triggered by event """
        try:
            action_name = TransitionTable[(event,self.CurrentState)]
        except:
            self.provider.name, "Invalid (event,state)", event, self.CurrentState
            logger.debug('%s: current state is: %s %s' % (self.provider.name, self.CurrentState, states[self.CurrentState]))
            logger.debug('%s: event: %s %s' % (self.provider.name, event, events[event]))   
            raise
            return
        action = actions[action_name]
        try:
            logger.debug('')
            logger.debug('%s: current state is: %s %s' % (self.provider.name, self.CurrentState, states[self.CurrentState]))
            logger.debug('%s: event: %s %s' % (self.provider.name, event, events[event]))
            logger.debug('%s: entering action: (%s, %s) %s %s' % (self.provider.name, event, self.CurrentState, action_name, actions[action_name][0]))
            action[1](c)
            if type(action[2])<>type(()):
                # only one next state possible
                self.CurrentState = action[2]   
            logger.debug('%s: action complete. State is now %s %s' % (self.provider.name, self.CurrentState, states[self.CurrentState]))
        except:
            raise
            self.provider.Kill()


    def NextState(self,state):
        self.CurrentState = state




