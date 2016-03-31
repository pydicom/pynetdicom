
import logging
import time

from pynetdicom.DIMSEmessages import *
from pynetdicom.DIMSEparameters import *
from pynetdicom.DULparameters import P_DATA_ServiceParameters

logger = logging.getLogger('pynetdicom.dimse')


class DIMSEServiceProvider(object):
    """
    PS3.7 6.2
    The DICOM AE uses the services provided by the DICOM Message Service Element
    (DIMSE). DIMSE specifies two sets of services.
    
    - DIMSE-C supports operations associated with composite SOP Classes and 
      provides effective compatibility with the previous versions of the DICOM
      standard.
    - DIMSE-N supports operations associated with normalised SOP Classes and 
      provides an extended set of object-orientated operations and notifications
    
    Service Overview
    ----------------
    The DIMSE service provider supports communication between peer DIMSE service
    users. A service user acts in one of two roles:
    - invoking DIMSE user
    - performing DIMSE user
    
    Service users make use of service primitives provided by the DIMSE service
    provider. A service primitive shall be one of the following types:
    - request primitive
    - indication primitive
    - response primitive
    - confirmation primitive
    
    These primitives are used as follows:
    - The invoking service user issues a request primitive to the DIMSE provider
    - The DIMSE provider receives the request primitive and issues an indication
      primitive to the performing service user
    - The performing service user receives the indication primitive and performs
      the requested service
    - The performing service user issues a response primitive to the DIMSE 
      provider
    - The DIMSE provider receives the response primitive and issues a 
      confirmation primitive to the invoking service user
    - The invoking service user receives the confirmation primitive, completing
      the DIMSE service.
    
    Service Primitive Classes
    ~~~~~~~~~~~~~~~~~~~~~~~~~
    C_ECHO_ServiceParameters
    C_STORE_ServiceParameters
    C_GET_ServiceParameters
    C_FIND_ServiceParameters
    C_MOVE_ServiceParameters
    N_EVENT_REPORT_ServiceParameters
    N_GET_ServiceParameters
    N_GET_ServiceParameters
    N_ACTION_ServiceParameters
    N_CREATE_ServiceParameters
    N_DELETE_ServiceParameters
    
    Protocol Machine
    ----------------
    PS3.7 8.1
    The DIMSE protocol machine defines the procedures and the encoding rules
    necessary to construct Messages used to exchange command requests and
    responses between peer DIMSE service users.
    
    The DIMSE protocol machine accepts service user requests and response
    service primitives and constructs Messages defined by the procedures in 
    PS3.7 9.3 and 10.3. The DIMSE protocol machine accepts Messages and passes
    them to the DIMSE service user by the means of indication and confirmation
    service primitives.
    
    Messages
    ~~~~~~~~
    C-STORE: Request/indication    - C_STORE_RQ
             Response/confirmation - C_STORE_RSP
    C-FIND:  Request/indication        - C_FIND_RQ_Message
             Response/confirmation     - C_FIND_RSP_Message
             Cancel request/indication - C_CANCEL_FIND_RQ_Message
    C-GET:   Request/indication        - C_GET_RQ_Message
             Response/confirmation     - C_GET_RSP_Message
             Cancel request/indication - C_CANCEL_GET_RQ_Message
    C-MOVE:  Request/indication    - C_MOVE_RQ_Message
             Response/confirmation - C_MOVE_RSP_Message
             Cancel request/indication - C_CANCEL_MOVE_RQ_Message
    C-ECHO:  Request/indication    - C_ECHO_RQ
             Response/confirmation - C_ECHO_RSP
    N-EVENT-REPORT: Request/indication    - N_EVENT_REPORT_RQ_Message
                    Response/confirmation - N_EVENT_REPORT_RSP_Message
    N-GET:    Request/indication    - N_GET_RQ_Message
              Response/confirmation - N_GET_RSP_Message
    N-SET:    Request/indication    - N_SET_RQ_Message
              Response/confirmation - N_SET_RSP_Message
    N-ACTION: Request/indication    - N_ACTION_RQ_Message
              Response/confirmation - N_ACTION_RSP_Message
    N-CREATE: Request/indication    - N_CREATE_RQ_Message
              Response/confirmation - N_CREATE_RSP_Message
    N-DELETE: Request/indication    - N_DELETE_RQ_Message
              Response/confirmation - N_DELETE_RSP_Message
    """
    def __init__(self, DUL, dimse_timeout=None):
        self.DUL = DUL
        self.message = None
        self.dimse_timeout = None

    def Send(self, primitive, context_id, max_pdu):
        """
        Send a DIMSE-C or DIMSE-N message to the peer AE
        
        Parameters
        ----------
        primitive : pynetdicom.DIMSEparameters
            The DIMSE service primitive to send to the peer
        context_id : int
            The ID of the presentation context to be sent under
        max_pdu : int
            The maximum send PDV size acceptable by the peer AE
        """
        if primitive.__class__ == C_ECHO_ServiceParameters:
            if primitive.MessageID is not None:
                dimse_msg = C_ECHO_RQ()
            else:
                dimse_msg = C_ECHO_RSP()
        
        elif primitive.__class__ == C_STORE_ServiceParameters:
            if primitive.MessageID is not None:
                dimse_msg = C_STORE_RQ()
            else:
                dimse_msg = C_STORE_RSP()
        
        elif primitive.__class__ == C_FIND_ServiceParameters:
            if primitive.MessageID is not None:
                dimse_msg = C_FIND_RQ()
            elif primitive.CommandField != 0x0fff:
                dimse_msg = C_FIND_RSP()
            else:
                dimse_msg = C_CANCEL_FIND_RQ()
        
        elif primitive.__class__ == C_GET_ServiceParameters:
            if primitive.MessageID is not None:
                dimse_msg = C_GET_RQ()
            elif primitive.CommandField != 0x0fff:
                dimse_msg = C_GET_RSP()
            else:
                dimse_msg = C_CANCEL_GET_RQ()
        
        elif primitive.__class__ == C_MOVE_ServiceParameters:
            if primitive.MessageID is not None:
                dimse_msg = C_MOVE_RQ()
            elif primitive.CommandField != 0x0fff:
                dimse_msg = C_MOVE_RSP()
            else:
                dimse_msg = C_CANCEL_MOVE_RQ()

        elif primitive.__class__ == N_EVENT_REPORT_ServiceParameters:
            if primitive.MessageID is not None:
                dimse_msg = N_EVENT_REPORT_RQ()
            else:
                dimse_msg = N_EVENT_REPORT_RSP()

        elif primitive.__class__ == N_GET_ServiceParameters:
            if primitive.MessageID is not None:
                dimse_msg = N_GET_RQ()
            else:
                dimse_msg = N_GET_RSP()
        
        elif primitive.__class__ == N_SET_ServiceParameters:
            if primitive.MessageID is not None:
                dimse_msg = N_SET_RQ()
            else:
                dimse_msg = N_SET_RSP()
        
        elif primitive.__class__ == N_ACTION_ServiceParameters:
            if primitive.MessageID is not None:
                dimse_msg = N_ACTION_RQ()
            else:
                dimse_msg = N_ACTION_RSP()
        
        elif primitive.__class__ == N_CREATE_ServiceParameters:
            if primitive.MessageID is not None:
                dimse_msg = N_CREATE_RQ()
            else:
                dimse_msg = N_CREATE_RSP()
        
        elif primitive.__class__ == N_DELETE_ServiceParameters:
            if primitive.MessageID is not None:
                dimse_msg = N_DELETE_RQ()
            else:
                dimse_msg = N_DELETE_RSP()

        # Convert DIMSE primitive to DIMSE Message
        dimse_msg.primitive_to_message(primitive)

        # Callbacks
        self.on_send_dimse_message(dimse_msg)

        # Split the full messages into P-DATA chunks, each below the max_pdu size
        pdvs = dimse_msg.Encode(context_id, max_pdu)

        # Send each of the P-DATA to the peer via the DUL provider
        for pp in pdvs:
            self.DUL.Send(pp)

    def Receive(self, wait=False, dimse_timeout=None):
        """
        Set the DIMSE provider in a mode ready to receive a response from the 
        peer
        
        Parameters
        ----------
        wait : bool, optional
            Wait until a response has been received (default: False)
        dimse_timeout : int, optional
            Wait `dimse_timeout` seconds for a response (default: no timeout)
            
        Returns
        -------
        pynetdicom.DIMSEmessage.DIMSEMessage, int or None, None
            Returns the complete DIMSE message and its presentation context ID 
            or None, None if 
        """
        if self.message is None:
            self.message = DIMSEMessage()

        if wait:
            # Loop until complete DIMSE message is received
            #   message may be split into 1 or more fragments
            while 1:
                time.sleep(0.001)
                
                nxt = self.DUL.Peek()
                if nxt is None:
                    continue
                
                if nxt.__class__ is not P_DATA_ServiceParameters:
                    return None, None
                
                primitive = self.DUL.Receive(wait, dimse_timeout)

                if self.message.Decode(primitive):
                    # Callback
                    self.on_receive_dimse_message(self.message)
                    dimse_msg = self.message
                    self.message = None
                    
                    context_id = dimse_msg.ID
                    dimse_msg = dimse_msg.message_to_primitive()
                    
                    return dimse_msg, context_id
                else:
                    return None, None
        else:
            cls = self.DUL.Peek().__class__

            if cls not in (type(None), P_DATA_ServiceParameters):
                return None, None

            primitive = self.DUL.Receive(wait, dimse_timeout)

            if self.message.Decode(primitive):
                # Callback
                self.on_receive_dimse_message(self.message)
                
                dimse_msg = self.message
                self.dimse_msg = None
                
                context_id = dimse_msg.ID
                dimse_msg = dimse_msg.message_to_primitive()

                return dimse_msg, context_id
            else:
                return None, None


    # Debugging and AE callbacks
    def on_send_dimse_message(self, message):
        """
        Placeholder for a function callback. Function will be called 
        immediately prior to encoding and sending a DIMSE message
        
        Parameters
        ----------
        message - pynetdicom.DIMSEmessage.DIMSEMessage
            The DIMSE message to be sent
        """
        callback = {C_ECHO_RQ  : self.debug_send_c_echo_rq,
                    C_ECHO_RSP : self.debug_send_c_echo_rsp,
                    C_FIND_RQ        : self.debug_send_c_find_rq,
                    C_FIND_RSP       : self.debug_send_c_find_rsp,
                    C_CANCEL_RQ : self.debug_send_c_cancel_rq,
                    C_GET_RQ        : self.debug_send_c_get_rq,
                    C_GET_RSP       : self.debug_send_c_get_rsp,
                    C_MOVE_RQ        : self.debug_send_c_move_rq,
                    C_MOVE_RSP       : self.debug_send_c_move_rsp,
                    C_STORE_RQ  : self.debug_send_c_store_rq,
                    C_STORE_RSP : self.debug_send_c_store_rsp,
                    N_EVENT_REPORT_RQ  : self.debug_send_n_event_report_rq,
                    N_EVENT_REPORT_RSP : self.debug_send_n_event_report_rsp,
                    N_SET_RQ  : self.debug_send_n_set_rq,
                    N_SET_RSP : self.debug_send_n_set_rsp,
                    N_GET_RQ  : self.debug_send_n_get_rq,
                    N_GET_RSP : self.debug_send_n_get_rsp,
                    N_ACTION_RQ  : self.debug_send_n_action_rq,
                    N_ACTION_RSP : self.debug_send_n_action_rsp,
                    N_CREATE_RQ  : self.debug_send_n_create_rq,
                    N_CREATE_RSP : self.debug_send_n_create_rsp,
                    N_DELETE_RQ  : self.debug_send_n_delete_rq,
                    N_DELETE_RSP : self.debug_send_n_delete_rsp}
        callback[type(message)](message)
        
    def on_receive_dimse_message(self, message):
        """
        Placeholder for a function callback. Function will be called 
        immediately after receiving and decoding a DIMSE message
        
        Parameters
        ----------
        sop_class - pynetdicom.SOPclass.SOPClass
            A SOP Class instance of the type referred to by the message
        message - pydicom.Dataset
            The DIMSE message that was received as a Dataset
        """
        callback = {C_ECHO_RQ  : self.debug_receive_c_echo_rq,
                    C_ECHO_RSP : self.debug_receive_c_echo_rsp,
                    C_FIND_RQ        : self.debug_receive_c_find_rq,
                    C_FIND_RSP       : self.debug_receive_c_find_rsp,
                    C_CANCEL_RQ : self.debug_receive_c_cancel_rq,
                    C_GET_RQ        : self.debug_receive_c_get_rq,
                    C_GET_RSP       : self.debug_receive_c_get_rsp,
                    C_MOVE_RQ        : self.debug_receive_c_move_rq,
                    C_MOVE_RSP       : self.debug_receive_c_move_rsp,
                    C_STORE_RQ  : self.debug_receive_c_store_rq,
                    C_STORE_RSP : self.debug_receive_c_store_rsp,
                    N_EVENT_REPORT_RQ  : self.debug_receive_n_event_report_rq,
                    N_EVENT_REPORT_RSP : self.debug_receive_n_event_report_rsp,
                    N_SET_RQ  : self.debug_receive_n_set_rq,
                    N_SET_RSP : self.debug_receive_n_set_rsp,
                    N_GET_RQ  : self.debug_receive_n_get_rq,
                    N_GET_RSP : self.debug_receive_n_get_rsp,
                    N_ACTION_RQ  : self.debug_receive_n_action_rq,
                    N_ACTION_RSP : self.debug_receive_n_action_rsp,
                    N_CREATE_RQ  : self.debug_receive_n_create_rq,
                    N_CREATE_RSP : self.debug_receive_n_create_rsp,
                    N_DELETE_RQ  : self.debug_receive_n_delete_rq,
                    N_DELETE_RSP : self.debug_receive_n_delete_rsp}
        callback[type(message)](message)


    # Mid-level DIMSE related logging/debugging
    def debug_send_c_echo_rq(self, dimse_msg):
        """
        Parameters
        ----------
        dimse_msg - pynetdicom.SOPclass.C_ECHO_RQ 
        """
        d = dimse_msg.command_set
        logger.info("Sending Echo Request: MsgID %s" %(d.MessageID))
        
    def debug_send_c_echo_rsp(self, dimse_msg):
        pass
    
    def debug_send_c_store_rq(self, dimse_msg):
        """
        Parameters
        ----------
        store - pynetdicom.SOPclass.C_STORE_RQ 
        """
        d = dimse_msg.command_set

        priority_str = {2 : 'Low',
                        0 : 'Medium',
                        1 : 'High'}
        priority = priority_str[d.Priority]

        dataset = 'None'
        if 'data_set' in dimse_msg.__dict__.keys():
            dataset = 'Present'

        if d.AffectedSOPClassUID.name == 'CT Image Storage':
            dataset_type = ', (CT)'
        elif d.AffectedSOPClassUID.name == 'MR Image Storage':
            dataset_type = ', (MR)'
        else:
            dataset_type = ''
        
        logger.info("Sending Store Request: MsgID %s%s" 
                %(d.MessageID, dataset_type))
        
        s = []
        s.append('===================== OUTGOING DIMSE MESSAGE ================'
                 '====')
        s.append('Message Type                  : %s' %'C-STORE RQ')
        s.append('Message ID                    : %s' %d.MessageID)
        s.append('Affected SOP Class UID        : %s' %d.AffectedSOPClassUID)
        s.append('Affected SOP Instance UID     : %s' %d.AffectedSOPInstanceUID)
        s.append('Data Set                      : %s' %dataset)
        s.append('Priority                      : %s' %priority)
        s.append('======================= END DIMSE MESSAGE ==================='
                 '====')
        for line in s:
            logger.debug(line)
    
    def debug_send_c_store_rsp(self, dimse_msg):
        pass
    
    def debug_send_c_find_rq(self, dimse_msg):
        """
        Parameters
        ----------
        dimse_msg - pynetdicom.SOPclass.C_STORE_RQ 
        """
        d = dimse_msg.command_set

        priority_str = {2 : 'Low',
                        0 : 'Medium',
                        1 : 'High'}
        priority = priority_str[d.Priority]

        dataset = 'None'
        if 'data_set' in dimse_msg.__dict__.keys():
            dataset = 'Present'

        s = []
        s.append('===================== OUTGOING DIMSE MESSAGE ================'
                 '====')
        s.append('Message Type                  : %s' %'C-FIND RQ')
        s.append('Message ID                    : %s' %d.MessageID)
        #s.append('Affected SOP Class UID        : %s' %d.AffectedSOPClassUID)
        #s.append('Affected SOP Instance UID     : %s' %d.AffectedSOPInstanceUID)
        s.append('Data Set                      : %s' %dataset)
        s.append('Priority                      : %s' %priority)
        s.append('======================= END DIMSE MESSAGE ==================='
                 '====')
        for line in s:
            logger.debug(line)
    
    def debug_send_c_find_rsp(self, dimse_msg):
        pass
    
    def debug_send_c_cancel_rq(self, dimse_msg):
        pass
    
    def debug_send_c_get_rq(self, dimse_msg):
        """
        Placeholder for a function callback. Function will be called 
        on receiving a C-GET-RQ. The C-GET service is used by a DIMSE to match
        a set of Attributes against the Attributes of a set of composite SOP
        Instances maintained by a peer DIMSE user, and retrieve all composite
        SOP Instances that match. It triggers one or more C-STORE 
        sub-operations on the same Association.
        
        Parameters
        ----------
        dimse_msg - 
            
            
        Returns
        -------
        matching_sop_instances - list of pydicom.Dataset
            The matching SOP Instances to be sent via C-STORE sub-operations. If
            no matching SOP Instances are found then return the empty list or
            None.
        """
        """
        Parameters
        ----------
        dimse_msg - pynetdicom.SOPclass.C_STORE_RQ 
        """
        d = dimse_msg.command_set

        priority_str = {2 : 'Low',
                        0 : 'Medium',
                        1 : 'High'}
        priority = priority_str[d.Priority]

        dataset = 'None'
        if 'data_set' in dimse_msg.__dict__.keys():
            dataset = 'Present'
        
        logger.info("Sending Get Request: MsgID %s" %(d.MessageID))
        
        s = []
        s.append('===================== OUTGOING DIMSE MESSAGE ================'
                 '====')
        s.append('Message Type                  : %s' %'C-GET RQ')
        s.append('Message ID                    : %s' %d.MessageID)
        s.append('Affected SOP Class UID        : %s' %d.AffectedSOPClassUID)
        s.append('Data Set                      : %s' %dataset)
        s.append('Priority                      : %s' %priority)
        s.append('======================= END DIMSE MESSAGE ==================='
                 '====')
        for line in s:
            logger.debug(line)
        
    def debug_send_c_get_rsp(self, dimse_msg):
        """
        Placeholder for a function callback. Function will be called 
        on receiving a C-GET-RQ. The C-GET service is used by a DIMSE to match
        a set of Attributes against the Attributes of a set of composite SOP
        Instances maintained by a peer DIMSE user, and retrieve all composite
        SOP Instances that match. It triggers one or more C-STORE 
        sub-operations on the same Association.
        
        Parameters
        ----------
        dimse_msg - 
            
            
        Returns
        -------
        matching_sop_instances - list of pydicom.Dataset
            The matching SOP Instances to be sent via C-STORE sub-operations. If
            no matching SOP Instances are found then return the empty list or
            None.
        """
        return None
    
    def debug_send_c_cancel_get_rq(self, dimse_msg):
        pass
    
    def debug_send_c_move_rq(self, dimse_msg):
        """
        The C-MOVE service is used by a DIMSE to match
        a set of Attributes against the Attributes of a set of composite SOP
        Instances maintained by a peer DIMSE user, and retrieve all composite
        SOP Instances that match. It triggers one or more C-STORE 
        sub-operations on the same Association.
        
        Parameters
        ----------
        dimse_msg - 
            
            
        Returns
        -------
        matching_sop_instances - list of pydicom.Dataset
            The matching SOP Instances to be sent via C-STORE sub-operations. If
            no matching SOP Instances are found then return the empty list or
            None.
        """
        """
        Parameters
        ----------
        dimse_msg - pynetdicom.SOPclass.C_STORE_RQ 
        """
        d = dimse_msg.command_set

        priority_str = {2 : 'Low',
                        0 : 'Medium',
                        1 : 'High'}
        priority = priority_str[d.Priority]

        dataset = 'None'
        if 'data_set' in dimse_msg.__dict__.keys():
            dataset = 'Present'
        
        logger.info("Sending Store Request: MsgID %s" %(d.MessageID))
        
        s = []
        s.append('===================== OUTGOING DIMSE MESSAGE ================'
                 '====')
        s.append('Message Type                  : %s' %'C-MOVE RQ')
        s.append('Message ID                    : %s' %d.MessageID)
        s.append('Affected SOP Class UID        : %s' %d.AffectedSOPClassUID)
        s.append('Move Destination              : %s' %d.MoveDestination)
        s.append('Data Set                      : %s' %dataset)
        s.append('Priority                      : %s' %priority)
        s.append('======================= END DIMSE MESSAGE ==================='
                 '====')
        for line in s:
            logger.debug(line)
        return None

    def debug_send_c_move_rsp(self, dimse_msg):
        """
        Placeholder for a function callback. Function will be called 
        on receiving a C-MOVE-RQ. The C-MOVE service is used by a DIMSE to match
        a set of Attributes against the Attributes of a set of composite SOP
        Instances maintained by a peer DIMSE user, and retrieve all composite
        SOP Instances that match. It triggers one or more C-STORE 
        sub-operations on the same Association.
        
        Parameters
        ----------
        dimse_msg - 
            
            
        Returns
        -------
        matching_sop_instances - list of pydicom.Dataset
            The matching SOP Instances to be sent via C-STORE sub-operations. If
            no matching SOP Instances are found then return the empty list or
            None.
        """
        return None
    
    def debug_send_c_cancel_move_rq(self, dimse_msg):
        pass
    
    
    def debug_receive_c_echo_rq(self, dimse_msg):
        """
        Placeholder for a function callback. Function will be called 
        after receiving and decoding a C-ECHO-RQ. The C-ECHO service is used
        to verify end-to-end communications with a peer DIMSE user.
        """
        d = dimse_msg.command_set
        
        logger.info('Received Echo Request (MsgID %s)' %d.MessageID)
        
        s = []
        s.append('===================== INCOMING DIMSE MESSAGE ================'
                 '====')
        s.append('Message Type                  : %s' %'C-ECHO RQ')
        s.append('Presentation Context ID       : %s' %dimse_msg.ID)
        s.append('Message ID                    : %s' %d.MessageID)
        s.append('Data Set                      : %s' %'none')
        s.append('======================= END DIMSE MESSAGE ==================='
                 '====')
                 
        for line in s:
            logger.debug(line)
    
    def debug_receive_c_echo_rsp(self, dimse_msg):
        """
        Parameters
        ----------
        dimse_msg - pynetdicom.SOPclass.C_ECHO_RSP
        """
        d = dimse_msg.command_set
        
        # Status must always be Success for C_ECHO_RSP
        logger.info("Received Echo Response (Status: Success)")
        
    def debug_receive_c_store_rq(self, dimse_msg):
        """
        Placeholder for a function callback. Function will be called 
        on receiving a C-STORE-RQ
        
        Parameters
        ----------
        dataset - pydicom.Dataset
            The dataset sent to the local AE
        """
        d = dimse_msg.command_set
        
        priority_str = {2 : 'Low',
                        0 : 'Medium',
                        1 : 'High'}
        priority = priority_str[d.Priority]

        dataset = 'None'
        if 'data_set' in dimse_msg.__dict__.keys():
            dataset = 'Present'
        
        logger.info('Received Store Request')
        
        s = []
        s.append('===================== INCOMING DIMSE MESSAGE ================'
                 '====')
        s.append('Message Type                  : %s' %'C-STORE RQ')
        s.append('Presentation Context ID       : %s' %dimse_msg.ID)
        s.append('Message ID                    : %s' %d.MessageID)
        s.append('Affected SOP Class UID        : %s' %d.AffectedSOPClassUID)
        s.append('Affected SOP Instance UID     : %s' %d.AffectedSOPInstanceUID)
        s.append('Data Set                      : %s' %dataset)
        s.append('Priority                      : %s' %priority)
        s.append('======================= END DIMSE MESSAGE ==================='
                 '====')
        for line in s:
            logger.debug(line)

    def debug_receive_c_store_rsp(self, dimse_msg):

        d = dimse_msg.command_set
        
        dataset = 'None'
        if 'data_set' in dimse_msg.__dict__.keys():
            if dimse_msg.DataSet.getvalue() != b'':
                dataset = 'Present'
        
        # See PS3.4 Annex B.2.3 for Storage Service Class Statuses
        status = '0x%04x' %d.Status
        if status == '0x0000':
            status += ': Success'
        elif '0xb000' in status:
            status += ': Warning - Coercion of data elements'
        elif '0xb007' in status:
            status += ': Warning - Dataset does not match SOP Class'
        elif '0xb006' in status:
            status += ': Warning - Elements discarded'
        elif '0xa7' in status:
            status += ': Failure - Out of resources'
        elif '0xa9' in status:
            status += ': Failure - Dataset does not match SOP Class'
        elif '0xc' in status or status == '0x0001':
            status += ': Failure - Cannot understand'
        else:
            pass
        
        logger.info('Received Store Response')
        s = []
        s.append('===================== INCOMING DIMSE MESSAGE ================'
                 '====')
        s.append('Message Type                  : %s' %'C-STORE RSP')
        s.append('Presentation Context ID       : %s' %dimse_msg.ID)
        s.append('Message ID Being Responded To : %s' %d.MessageIDBeingRespondedTo)
        s.append('Affected SOP Class UID        : %s' %d.AffectedSOPClassUID)
        s.append('Affected SOP Instance UID     : %s' %d.AffectedSOPInstanceUID)
        s.append('Data Set                      : %s' %dataset)
        s.append('DIMSE Status                  : %s' %status)
        
        s.append('======================= END DIMSE MESSAGE ==================='
                 '====')
                 
        for line in s:
            logger.debug(line)

    def debug_receive_c_find_rq(self, dimse_msg):
        """
        Placeholder for a function callback. Function will be called 
        on receiving a C-FIND-RQ. The C-FIND service is used by a DIMSE to match
        a set of Attributes against the Attributes of a set of composite SOP
        Instances maintained by a peer DIMSE user, and retrieve all composite
        SOP Instances that match. It triggers one or more C-STORE 
        sub-operations on the same Association.
        
        Parameters
        ----------
        attributes - pydicom.Dataset
            A Dataset containing the attributes to match against.
            
        Returns
        -------
        matching_sop_instances - list of pydicom.Dataset
            The matching SOP Instances. If no matching SOP Instances are found 
            then return the empty list or None.
        """
        return None
        
    def debug_receive_c_find_rsp(self, dimse_msg):
        """
        Placeholder for a function callback. Function will be called 
        on receiving a C-FIND-RQ. The C-FIND service is used by a DIMSE to match
        a set of Attributes against the Attributes of a set of composite SOP
        Instances maintained by a peer DIMSE user, and retrieve all composite
        SOP Instances that match. It triggers one or more C-STORE 
        sub-operations on the same Association.
        
        Parameters
        ----------
        dimse_msg - pynetdicom.DIMSEmessage.C_FIND_RSP_Message
            The received C-FIND response
        """
        logger.info("Received Find Response")
        
        d = dimse_msg.command_set
        
        dataset = 'None'
        if 'data_set' in dimse_msg.__dict__.keys():
            if dimse_msg.DataSet.getvalue() != b'':
                dataset = 'Present'
        
        if d.Status == 0x0000:
            s = []
            s.append('===================== INCOMING DIMSE MESSAGE ================'
                     '====')
            s.append('Message Type                  : %s' %'C-FIND RSP')
            s.append('Message ID Being Responded To : %s' %d.MessageIDBeingRespondedTo)
            s.append('Affected SOP Class UID        : %s' %d.AffectedSOPClassUID)
            s.append('Data Set                      : %s' %dataset)
            s.append('DIMSE Status                  : %s' %dimse_msg.Status)
            
            s.append('======================= END DIMSE MESSAGE ==================='
                     '====')
            
            for line in s:
                logger.debug(line)

    def debug_receive_c_cancel_rq(self, dimse_msg):
        pass

    def debug_receive_c_get_rq(self, dimse_msg):
        """
        Placeholder for a function callback. Function will be called 
        on receiving a C-GET-RQ. The C-GET service is used by a DIMSE to match
        a set of Attributes against the Attributes of a set of composite SOP
        Instances maintained by a peer DIMSE user, and retrieve all composite
        SOP Instances that match. It triggers one or more C-STORE 
        sub-operations on the same Association.
        
        Parameters
        ----------
        dimse_msg - pydicom.Dataset
            A Dataset containing the attributes to match against.
            
        Returns
        -------
        matching_sop_instances - list of pydicom.Dataset
            The matching SOP Instances to be sent via C-STORE sub-operations. If
            no matching SOP Instances are found then return the empty list or
            None.
        """
        return None
        
    def debug_receive_c_get_rsp(self, dimse_msg):
        """
        Placeholder for a function callback. Function will be called 
        on receiving a C-GET-RQ. The C-GET service is used by a DIMSE to match
        a set of Attributes against the Attributes of a set of composite SOP
        Instances maintained by a peer DIMSE user, and retrieve all composite
        SOP Instances that match. It triggers one or more C-STORE 
        sub-operations on the same Association.
        
        Parameters
        ----------
        dimse_msg - pydicom.Dataset
            A Dataset containing the attributes to match against.
            
        Returns
        -------
        matching_sop_instances - list of pydicom.Dataset
            The matching SOP Instances to be sent via C-STORE sub-operations. If
            no matching SOP Instances are found then return the empty list or
            None.
        """
        return None
    
    def debug_receive_c_cancel_get_rq(self, dimse_msg):
        pass
    
    def debug_receive_c_move_rq(self, dimse_msg):
        """
        Placeholder for a function callback. Function will be called 
        on receiving a C-MOVE-RQ. The C-MOVE service is used by a DIMSE to match
        a set of Attributes against the Attributes of a set of composite SOP
        Instances maintained by a peer DIMSE user, and retrieve all composite
        SOP Instances that match. It triggers one or more C-STORE 
        sub-operations on the same Association.
        
        Parameters
        ----------
        attributes - pydicom.Dataset
            A Dataset containing the attributes to match against.
            
        Returns
        -------
        matching_sop_instances - list of pydicom.Dataset
            The matching SOP Instances to be sent via C-STORE sub-operations. If
            no matching SOP Instances are found then return the empty list or
            None.
        """
        return None
    
    def debug_receive_c_move_rsp(self, dimse_msg):
        """
        Placeholder for a function callback. Function will be called 
        on receiving a C-MOVE-RQ. The C-MOVE service is used by a DIMSE to match
        a set of Attributes against the Attributes of a set of composite SOP
        Instances maintained by a peer DIMSE user, and retrieve all composite
        SOP Instances that match. It triggers one or more C-STORE 
        sub-operations on the same Association.
        
        Parameters
        ----------
        attributes - pydicom.Dataset
            A Dataset containing the attributes to match against.
            
        Returns
        -------
        matching_sop_instances - list of pydicom.Dataset
            The matching SOP Instances to be sent via C-STORE sub-operations. If
            no matching SOP Instances are found then return the empty list or
            None.
        """
        return None
    
    def debug_receive_c_cancel_move_rq(self, dimse_msg):
        pass


    def debug_send_n_event_report_rq(self, dimse_msg):
        """
        """
        raise NotImplementedError

    def debug_send_n_event_report_rsp(self, dimse_msg):
        """
        """
        raise NotImplementedError
        
    def debug_send_n_get_rq(self, dimse_msg):
        """
        """
        raise NotImplementedError
        
    def debug_send_n_get_rsp(self, dimse_msg):
        """
        """
        raise NotImplementedError
        
    def debug_send_n_set_rq(self, dimse_msg):
        """
        """
        raise NotImplementedError
        
    def debug_send_n_set_rsp(self, dimse_msg):
        """
        """
        raise NotImplementedError
        
    def debug_send_n_action_rq(self, dimse_msg):
        """
        """
        raise NotImplementedError
        
    def debug_send_n_action_rsp(self, dimse_msg):
        """
        """
        raise NotImplementedError
        
    def debug_send_n_create_rq(self, dimse_msg):
        """
        """
        raise NotImplementedError
        
    def debug_send_n_create_rsp(self, dimse_msg):
        """
        """
        raise NotImplementedError
        
    def debug_send_n_delete_rq(self, dimse_msg):
        """
        """
        raise NotImplementedError
        
    def debug_send_n_delete_rsp(self, dimse_msg):
        """
        """


    def debug_receive_n_event_report_rq(self, dimse_msg):
        """
        """
        raise NotImplementedError

    def debug_receive_n_event_report_rsp(self, dimse_msg):
        """
        """
        raise NotImplementedError
        
    def debug_receive_n_get_rq(self, dimse_msg):
        """
        """
        raise NotImplementedError
        
    def debug_receive_n_get_rsp(self, dimse_msg):
        """
        """
        raise NotImplementedError
        
    def debug_receive_n_set_rq(self, dimse_msg):
        """
        """
        raise NotImplementedError
        
    def debug_receive_n_set_rsp(self, dimse_msg):
        """
        """
        raise NotImplementedError
        
    def debug_receive_n_action_rq(self, dimse_msg):
        """
        """
        raise NotImplementedError
        
    def debug_receive_n_action_rsp(self, dimse_msg):
        """
        """
        raise NotImplementedError
        
    def debug_receive_n_create_rq(self, dimse_msg):
        """
        """
        raise NotImplementedError
        
    def debug_receive_n_create_rsp(self, dimse_msg):
        """
        """
        raise NotImplementedError
        
    def debug_receive_n_delete_rq(self, dimse_msg):
        """
        """
        raise NotImplementedError
        
    def debug_receive_n_delete_rsp(self, dimse_msg):
        """
        """
        raise NotImplementedError


    
