#
# Copyright (c) 2012 Patrice Munger
# This file is part of pynetdicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pynetdicom.googlecode.com
#
import logging
import time

from pynetdicom.DIMSEmessages import *
from pynetdicom.DIMSEparameters import *
from pynetdicom.DULparameters import P_DATA_ServiceParameters

logger = logging.getLogger('pynetdicom.dimse')


class DIMSEServiceProvider(object):
    def __init__(self, DUL, dimse_timeout=None):
        self.DUL = DUL
        self.message = None
        self.dimse_timeout = None

    def Send(self, primitive, msg_id, maxpdulength):
        """
        Send a DIMSE message to the DUL provider
        
        Parameters
        ----------
        primitive - pynetdicom.SOPclass.ServiceClass subclass
            The SOP Class primitive to send
        msg_id - int
            The DIMSE Message ID (0000,0110)
        maxpdulength - int
            The maximum send PDV size acceptable by the peer AE
        """
        # take a DIMSE primitive, convert it to one or more DUL primitive and
        #   send it
        if primitive.__class__ == C_ECHO_ServiceParameters:
            if primitive.MessageID is not None:
                dimse_msg = C_ECHO_RQ_Message()
            else:
                dimse_msg = C_ECHO_RSP_Message()
        
        elif primitive.__class__ == C_STORE_ServiceParameters:
            if primitive.MessageID is not None:
                dimse_msg = C_STORE_RQ_Message()
            else:
                dimse_msg = C_STORE_RSP_Message()
        
        elif primitive.__class__ == C_FIND_ServiceParameters:
            if primitive.MessageID is not None:
                dimse_msg = C_FIND_RQ_Message()
            else:
                dimse_msg = C_FIND_RSP_Message()
        
        elif primitive.__class__ == C_GET_ServiceParameters:
            if primitive.MessageID is not None:
                dimse_msg = C_GET_RQ_Message()
            else:
                dimse_msg = C_GET_RSP_Message()
        
        elif primitive.__class__ == C_MOVE_ServiceParameters:
            if primitive.MessageID is not None:
                dimse_msg = C_MOVE_RQ_Message()
            else:
                dimse_msg = C_MOVE_RSP_Message()
        
        # Convert to DIMSE Message
        dimse_msg.FromParams(primitive)
        
        # Callbacks
        self.DUL.local_ae.on_send_dimse_message(dimse_msg)
        self.on_send_dimse_message(dimse_msg)
        
        pdatas = dimse_msg.Encode(msg_id, maxpdulength)
        for ii, pp in enumerate(pdatas):
            self.DUL.Send(pp)

    def Receive(self, Wait=False, dimse_timeout=None):
        if self.message is None:
            self.message = DIMSEMessage()

        if Wait:
            # loop until complete DIMSE message is received
            #logger.debug('DIMSE: Entering loop for receiving DIMSE message')
            
            while 1:
                time.sleep(0.001)
                nxt = self.DUL.Peek()
                if nxt is None:
                    continue
                
                if nxt.__class__ is not P_DATA_ServiceParameters:
                    return None, None
                
                dul_obj = self.DUL.Receive(Wait, dimse_timeout)

                if self.message.Decode(dul_obj):
                    # Callbacks
                    self.DUL.local_ae.on_receive_dimse_message(self.message)
                    self.on_receive_dimse_message(self.message)
                    
                    tmp = self.message
                    self.message = None
                    ID = tmp.ID
                    tmp = tmp.ToParams()
                    
                    return tmp, ID
        else:
            cls = self.DUL.Peek().__class__
            if cls not in (type(None), P_DATA_ServiceParameters):
                return None, None
            
            dul_obj = self.DUL.Receive(Wait, dimse_timeout)

            if self.message.Decode(dul_obj):
                # Callbacks
                self.DUL.local_ae.on_receive_dimse_message(self.message)
                self.on_receive_dimse_message(self.message)
                
                tmp = self.message
                self.message = None
                ID = tmp.ID
                tmp = tmp.ToParams()

                return tmp, ID
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
        debug_callback = {C_ECHO_RQ_Message   : self.debug_send_c_echo_rq,
                          C_ECHO_RSP_Message  : self.debug_send_c_echo_rsp,
                          C_FIND_RQ_Message   : self.debug_send_c_find_rq,
                          C_FIND_RSP_Message  : self.debug_send_c_find_rsp,
                          C_CANCEL_FIND_RQ_Message  : self.debug_send_c_cancel_find_rq,
                          C_GET_RQ_Message   : self.debug_send_c_get_rq,
                          C_GET_RSP_Message  : self.debug_send_c_get_rsp,
                          C_CANCEL_GET_RQ_Message  : self.debug_send_c_cancel_get_rq,
                          C_MOVE_RQ_Message   : self.debug_send_c_move_rq,
                          C_MOVE_RSP_Message  : self.debug_send_c_move_rsp,
                          C_CANCEL_MOVE_RQ_Message  : self.debug_send_c_cancel_move_rq,
                          C_STORE_RQ_Message  : self.debug_send_c_store_rq,
                          C_STORE_RSP_Message : self.debug_send_c_store_rsp}
        debug_callback[type(message)](message)
        
        ae = self.DUL.local_ae
        ae_callback = {C_ECHO_RQ_Message   : ae.on_send_c_echo_rq,
                       C_ECHO_RSP_Message  : ae.on_send_c_echo_rsp,
                       C_FIND_RQ_Message   : ae.on_send_c_find_rq,
                       C_FIND_RSP_Message  : ae.on_send_c_find_rsp,
                       C_CANCEL_FIND_RQ_Message  : ae.on_send_c_cancel_find_rq,
                       C_GET_RQ_Message   : ae.on_send_c_get_rq,
                       C_GET_RSP_Message  : ae.on_send_c_get_rsp,
                       C_CANCEL_GET_RQ_Message  : ae.on_send_c_cancel_get_rq,
                       C_MOVE_RQ_Message   : ae.on_send_c_move_rq,
                       C_MOVE_RSP_Message  : ae.on_send_c_move_rsp,
                       C_CANCEL_MOVE_RQ_Message  : ae.on_send_c_cancel_move_rq,
                       C_STORE_RQ_Message  : ae.on_send_c_store_rq,
                       C_STORE_RSP_Message : ae.on_send_c_store_rsp}
        ae_callback[type(message)](message)
        
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
        callback = {C_ECHO_RQ_Message   : self.debug_receive_c_echo_rq,
                    C_ECHO_RSP_Message  : self.debug_receive_c_echo_rsp,
                    C_FIND_RQ_Message   : self.debug_receive_c_find_rq,
                    C_FIND_RSP_Message  : self.debug_receive_c_find_rsp,
                    C_GET_RQ_Message   : self.debug_receive_c_get_rq,
                    C_GET_RSP_Message  : self.debug_receive_c_get_rsp,
                    C_STORE_RQ_Message  : self.debug_receive_c_store_rq,
                    C_STORE_RSP_Message : self.debug_receive_c_store_rsp}
        callback[type(message)](message)
        
        ae = self.DUL.local_ae
        ae_callback = {C_ECHO_RQ_Message   : ae.on_receive_c_echo_rq,
                       C_ECHO_RSP_Message  : ae.on_receive_c_echo_rsp,
                       C_FIND_RQ_Message   : ae.on_receive_c_find_rq,
                       C_FIND_RSP_Message  : ae.on_receive_c_find_rsp,
                       C_GET_RQ_Message   : ae.on_receive_c_get_rq,
                       C_GET_RSP_Message  : ae.on_receive_c_get_rsp,
                       C_STORE_RQ_Message  : ae.on_receive_c_store_rq,
                       C_STORE_RSP_Message : ae.on_receive_c_store_rsp}
        ae_callback[type(message)](message)


    # Mid-level DIMSE related logging/debugging
    def debug_send_c_echo_rq(self, dimse_msg):
        """
        Parameters
        ----------
        dimse_msg - pynetdicom.SOPclass.C_ECHO_RQ 
        """
        d = dimse_msg.CommandSet
        logger.info("Sending Echo Request: MsgID %s" %(d.MessageID))
        
    def debug_send_c_echo_rsp(self, dimse_msg):
        pass
    
    def debug_send_c_store_rq(self, dimse_msg):
        """
        Parameters
        ----------
        store - pynetdicom.SOPclass.C_STORE_RQ 
        """
        d = dimse_msg.CommandSet

        priority_str = {2 : 'Low',
                        0 : 'Medium',
                        1 : 'High'}
        priority = priority_str[d.Priority]

        dataset = 'None'
        if 'DataSet' in dimse_msg.__dict__.keys():
            dataset = 'Present'
            
        if d.AffectedSOPClassUID == 'CT Image Storage':
            dataset_type = ', (CT)'
        if d.AffectedSOPClassUID == 'MR Image Storage':
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
        d = dimse_msg.CommandSet

        priority_str = {2 : 'Low',
                        0 : 'Medium',
                        1 : 'High'}
        priority = priority_str[d.Priority]

        dataset = 'None'
        if 'DataSet' in dimse_msg.__dict__.keys():
            dataset = 'Present'
            
        #if d.AffectedSOPClassUID == 'CT Image Storage':
        #    dataset_type = ', (CT)'
        #if d.AffectedSOPClassUID == 'MR Image Storage':
        #    dataset_type = ', (MR)'
        #else:
        #    dataset_type = ''
        
        #logger.info("Sending Store Request: MsgID %s%s" 
        #        %(d.MessageID, dataset_type))
        
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
    
    def debug_send_c_cancel_find_rq(self, dimse_msg):
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
        d = dimse_msg.CommandSet

        priority_str = {2 : 'Low',
                        0 : 'Medium',
                        1 : 'High'}
        priority = priority_str[d.Priority]

        dataset = 'None'
        if 'DataSet' in dimse_msg.__dict__.keys():
            dataset = 'Present'
        
        logger.info("Sending Store Request: MsgID %s" %(d.MessageID))
        
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
        d = dimse_msg.CommandSet
        
        logger.info('Received Echo Request')
        
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
        d = dimse_msg.CommandSet
        
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
        d = dimse_msg.CommandSet
        
        priority_str = {2 : 'Low',
                        0 : 'Medium',
                        1 : 'High'}
        priority = priority_str[d.Priority]

        dataset = 'None'
        if 'DataSet' in dimse_msg.__dict__.keys():
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

        d = dimse_msg.CommandSet
        
        dataset = 'None'
        if 'DataSet' in dimse_msg.__dict__.keys():
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
        
        d = dimse_msg.CommandSet
        
        dataset = 'None'
        if 'DataSet' in dimse_msg.__dict__.keys():
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

    def debug_receive_c_cancel_find_rq(self, dimse_msg):
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


    def debug_receive_n_event_report_rq(self, dimse_msg):
        """
        Placeholder for a function callback. Function will be called 
        on receiving an N-EVENT-REPORT-RQ. The N-EVENT-REPORT service is used 
        by a DIMSE to report an event to a peer DIMSE user.
        
        Not currently implemented
        
        Parameters
        ----------
        event - ???
            ???
        """
        raise NotImplementedError
        
    def debug_receive_n_get_rq(self, dimse_msg):
        """
        Placeholder for a function callback. Function will be called 
        on receiving an N-GET-RQ. The N-GET service is used 
        by a DIMSE to retrieve Attribute values from a peer DIMSE user.
        
        Not currently implemented
        
        Parameters
        ----------
        attributes - ???
            ???
            
        Returns
        values - ???
            The attribute values to be retrieved
        """
        raise NotImplementedError
        
    def debug_receive_n_set_rq(self, dimse_msg):
        """
        Placeholder for a function callback. Function will be called 
        on receiving an N-SET-RQ. The N-SET service is used 
        by a DIMSE to request the modification of Attribute values from a peer 
        DIMSE user.
        
        Not currently implemented
        
        Parameters
        ----------
        attributes - ???
            ???
        """
        raise NotImplementedError
        
    def debug_receive_n_action_rq(self, dimse_msg):
        """
        Placeholder for a function callback. Function will be called 
        on receiving an N-ACTION-RQ. The N-ACTION service is used 
        by a DIMSE to request an action by a peer DIMSE user.
        
        Not currently implemented
        
        Parameters
        ----------
        actions - ???
            ???
        """
        raise NotImplementedError
        
    def debug_receive_n_create_rq(self, dimse_msg):
        """
        Placeholder for a function callback. Function will be called 
        on receiving an N-CREATE-RQ. The N-CREATE service is used 
        by a DIMSE to create a new managed SOP Instance, complete with its
        identification and the values of its association Attributes to register
        its identification.
        
        Not currently implemented
        
        Parameters
        ----------
        attributes - ???
            ???
        """
        raise NotImplementedError
        
    def debug_receive_n_delete_rq(self, dimse_msg):
        """
        Placeholder for a function callback. Function will be called 
        on receiving an N-DELETE-RQ. The N-DELETE service is used 
        by a DIMSE to request a peer DIMSE user delete a managed SOP Instance
        a deregister its identification.
        
        Not currently implemented
        
        Parameters
        ----------
        attributes - ???
            ???
        """
        raise NotImplementedError


    
