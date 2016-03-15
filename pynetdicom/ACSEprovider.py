#
# Copyright (c) 2012 Patrice Munger
# This file is part of pynetdicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pynetdicom.googlecode.com
#

# This module provides association services

import logging
import socket
import time

from pydicom.uid import UID

from pynetdicom.DULparameters import *
from pynetdicom.PDU import MaximumLengthParameters, \
                            ImplementationClassUIDParameters, \
                            ImplementationVersionNameParameters
from pynetdicom.utils import PresentationContext, PresentationContextManager

logger = logging.getLogger('pynetdicom.acse')


class ACSEServiceProvider(object):
    """ 
    Association Control Service Element service provider

    The ACSE protocol handles association establishment, normal release of an
    association and the abnormal release of an association.

    As per PS3.7, Section 6.1-2, the ACSE is the part of the DICOM Upper Layer 
    Service that handles Associations.

    The ACSE provider sends Association related service primitives to the DICOM
    UL provider
     * sending to peer AE: DUL FSM converts primitive to PDU, encodes and sends
     * received from peer AE: DUL receives data, decodes into a PDU then 
        converts to primitive which is result of DUL.Receive()

    Parameters
    ----------
    assoc - pynetdicom.association.Association
        The parent Association that instantiated the ACSE provider
    DUL - pynetdicom.DULprovider.DULServiceProvider
        The DICOM UL service provider instance that will handle the transport of
        the association primitives sent/received by the ACSE provider
    acse_timeout - int
        The maximum time (in seconds) to wait for A-ASSOCIATE PDUs from the peer
        (default: 30)

    References
    ----------
    DICOM Standard PS3.8
    ISO/IEC 8649
    """
    def __init__(self, assoc, DUL, acse_timeout=30):
        # The DICOM Upper Layer service provider, see PS3.8
        self.DUL = DUL
        # DICOM Application Context Name, see PS3.7 Annex A.2.1
        #   UID for the DICOM Application Context Name
        self.ApplicationContextName = b'1.2.840.10008.3.1.1.1'
        # Maximum time for response from peer (in seconds)
        self.acse_timeout = acse_timeout
        
        self.parent = assoc
        
        self.local_ae = None
        self.peer_ae = None
        self.local_max_pdu = None
        self.peer_max_pdu = None
        
        self.context_manager = PresentationContextManager()

    def Request(self, local_ae, peer_ae, max_pdu_size, pcdl, userspdu=None):
        """
        Issues an A-ASSOCIATE request primitive to the DICOM UL service provider
        
        Requests an association with a remote AE and waits for association
        response (local AE is acting as an SCU)

        Parameters
        ----------
        local_ae - pynetdicom.applicationentity.ApplicationEntity
            The local AE instance
            [FIXME] Change this back to a dict as the full instance isn't req'd
        peer_ae - dict
            A dict containing the peer AE's IP/TCP address, port and title
        max_pdu_size - int
            Maximum PDU size in bytes
        pcdl - list of pynetdicom.utils.PresentationContext
            A list of the proposed Presentation Contexts for the association
            If local_ae is ApplicationEntity then this is doubled up 
            unnecessarily
        userpdu - List of UserInformation objects
            List of items to be added to the requests user information for use 
            in extended negotiation. See PS3.7 Annex D.3.3
        
        Returns
        -------
        bool
            True if the Association was accepted, False if rejected or aborted
        """
        self.LocalAE = local_ae
        self.RemoteAE = peer_ae
        
        self.MaxPDULength = max_pdu_size

        ## Build an A-ASSOCIATE request primitive
        #
        # The following parameters must be set for a request primitive
        #   ApplicationContextName
        #   CallingAETitle
        #   CalledAETitle
        #   UserInformation
        #       Maximum PDV Length (required)
        #       Implementation Identification - Class UID (required)
        #   CallingPresentationAddress
        #   CalledPresentationAddress
        #   PresentationContextDefinitionList
        assoc_rq = A_ASSOCIATE_ServiceParameters()
        assoc_rq.ApplicationContextName = self.ApplicationContextName
        assoc_rq.CallingAETitle = self.LocalAE['AET']
        assoc_rq.CalledAETitle = self.RemoteAE['AET']

        # Build User Information - PS3.7 Annex D.3.3
        #
        # Maximum Length Negotiation (required)
        max_length = MaximumLengthParameters()
        max_length.MaximumLengthReceived = max_pdu_size
        assoc_rq.UserInformationItem = [max_length]
        
        # Implementation Identification Notification (required)
        # Class UID (required)
        from pynetdicom.__init__ import pynetdicom_uid_prefix
        implementation_class_uid = ImplementationClassUIDParameters()
        implementation_class_uid.ImplementationClassUID = \
                                        bytes(pynetdicom_uid_prefix, 'utf-8')
        assoc_rq.UserInformationItem.append(implementation_class_uid)

        # Version Name (optional)
        from pynetdicom.__init__ import pynetdicom_version
        implementation_version_name = ImplementationVersionNameParameters()
        implementation_version_name.ImplementationVersionName = \
                                        bytes(pynetdicom_version, 'utf-8')
        assoc_rq.UserInformationItem.append(implementation_version_name)

        # Add the extended negotiation information (optional)
        if userspdu is not None:
            assoc_rq.UserInformationItem += userspdu

        assoc_rq.CallingPresentationAddress = (self.LocalAE['Address'], 
                                               self.LocalAE['Port'])
        assoc_rq.CalledPresentationAddress = (self.RemoteAE['Address'], 
                                              self.RemoteAE['Port'])
        assoc_rq.PresentationContextDefinitionList = pcdl
        #
        ## A-ASSOCIATE request primitive is now complete


        # Send the A-ASSOCIATE request primitive to the peer via the 
        #   DICOM UL service
        logger.info("Requesting Association")
        self.DUL.Send(assoc_rq)


        ## Receive the response from the peer
        #   This may be an A-ASSOCIATE confirmation primitive or an
        #   A-ABORT or A-P-ABORT request primitive
        #
        if self.acse_timeout == 0:
            # No timeout
            assoc_rsp = self.DUL.Receive(True, None)
        else:
            assoc_rsp = self.DUL.Receive(True, self.acse_timeout)

        # Association accepted or rejected
        if isinstance(assoc_rsp, A_ASSOCIATE_ServiceParameters):
            # Accepted
            if assoc_rsp.Result == 'Accepted':
                # Get the association accept details from the PDU and construct
                #   a pynetdicom.utils.AssociationInformation instance
                # assoc_info = AssociationInformation(assoc_rq, assoc_rsp)
                # accepted_presentation_contexts = assoc_info.AcceptedPresentationContexts
                #
                # return True, assoc_info
                
                # Get maximum pdu length from answer
                self.MaxPDULength = \
                        assoc_rsp.UserInformationItem[0].MaximumLengthReceived
                self.peer_max_pdu = self.MaxPDULength

                # Get accepted presentation contexts using the manager
                self.context_manager.requestor_contexts = pcdl
                self.context_manager.acceptor_contexts = \
                            assoc_rsp.PresentationContextDefinitionResultList
                
                # Once the context manager gets both sets of contexts it 
                #   automatically determines which are accepted and refused
                self.presentation_contexts_accepted = \
                                                self.context_manager.accepted
                self.presentation_contexts_rejected = \
                                                self.context_manager.rejected
                
                return True, assoc_rsp
            
            # Rejected
            elif assoc_rsp.Result in [0x01, 0x02]:
                # 0x01 is rejected (permanent)
                # 0x02 is rejected (transient)
                return False, assoc_rsp
            # Invalid Result value
            elif assoc_rsp.Result is None:
                return False, assoc_rsp
            else:
                logger.error("ACSE received an invalid result value from "
                    "the peer AE: '%s'" %assoc_rsp.Result)
                raise ValueError("ACSE received an invalid result value from "
                    "the peer AE: '%s'" %assoc_rsp.Result)

        # Association aborted
        elif isinstance(assoc_rsp, A_ABORT_ServiceParameters) or \
             isinstance(assoc_rsp, A_P_ABORT_ServiceParameters):
            return False, assoc_rsp
        
        elif assoc_rsp is None:
            return False, assoc_rsp
        
        else:
            raise ValueError("Unexpected response by the peer AE to the "
                                                "ACSE association request")

    def Reject(self, assoc_primitive, result, source, diagnostic):
        """
        Issues an A-ASSOCIATE response primitive to the DICOM UL service 
        provider. The response will be that the association request is 
        rejected
        
        Parameters
        ----------
        assoc_primtive - pynetdicom.DULparameters.A_ASSOCIATE_ServiceParameters
            The Association request primitive to be rejected
        result - int
            The association rejection: 0x01 or 0x02
        source - int
            The source of the rejection: 0x01, 0x02, 0x03
        diagnostic - int
            The reason for the rejection: 0x01 to 0x10
        """
        # Check valid Result and Source values
        if result not in [0x01, 0x02]:
            raise ValueError("ACSE rejection: invalid Result value "
                                                        "'%s'" %result)
                                                        
        if source not in [0x01, 0x02, 0x03]:
            raise ValueError("ACSE rejection: invalid Source value "
                                                        "'%s'" %source)

        # Send the A-ASSOCIATE primitive, rejecting the association
        assoc_primitive.PresentationContextDefinitionList = []
        assoc_primitive.PresentationContextDefinitionResultList = []
        assoc_primitive.Result = result
        assoc_primitive.ResultSource = source
        assoc_primitive.Diagnostic = diagnostic
        assoc_primitive.UserInformationItem = []
        
        self.DUL.Send(assoc_primitive)
            
        return assoc_primitive

    def Accept(self, assoc_primitive):
        """
        Issues an A-ASSOCIATE response primitive to the DICOM UL service 
        provider. The response will be that the association request is
        accepted
        
        When an AE gets a connection on its listen socket it creates an
        Association instance which creates an ACSE instance and forwards
        the socket onwards (`client_socket`).
        
        Waits for an association request from a remote AE. Upon reception
        of the request sends association response based on
        AcceptablePresentationContexts
        
        The acceptability of the proposed Transfer Syntax is checked in the 
        order of appearance in the local AE's SupportedTransferSyntax list
        """
        self.MaxPDULength = \
                assoc_primitive.UserInformationItem[0].MaximumLengthReceived

        # Send response
        assoc_primitive.PresentationContextDefinitionList = []
        assoc_primitive.PresentationContextDefinitionResultList = \
                                        self.presentation_contexts_accepted
        assoc_primitive.Result = 0
        
        self.DUL.Send(assoc_primitive)
        return assoc_primitive

    def Release(self):
        """
        Issues an A-RELEASE request primitive to the DICOM UL service provider
        
        The graceful release of an association between two AEs shall be 
        performed through ACSE A-RELEASE request, indication, response and
        confirmation primitives.
        
        Requests the release of the associations and waits for confirmation.
        A-RELEASE always gives a reason of 'normal' and a result of 
        'affirmative'.
        
        Returns
        -------
        response 
            The A-RELEASE-RSP
        """
        logger.info("Releasing Association")
        
        release = A_RELEASE_ServiceParameters()
        self.DUL.Send(release)
        response = self.DUL.Receive(Wait=True)

        return response

    def Abort(self, source=0x02, reason=0x00):
        """
        ACSE issued A-ABORT request primitive to the DICOM UL service provider.
        The source may be either the DUL service user or provider. 
        
        See PS3.8 7.3-4 and 9.3.8
        
        Parameters
        ----------
        source - int, optional
            The source of the abort request (default: 0x02 DUL provider)
                0x00 - the DUL service user
                0x01 - reserved
                0x02 - the DUL service provider
        reason - int, optional
            The reason for aborting the association (default: 0x00 reason not 
            specified). 
            If source 0x00 (DUL user):
                0x00 - reason field not significant
            If source 0x02 (DUL provider):
                0x00 - reason not specified
                0x01 - unrecognised PDU
                0x02 - unexpected PDU
                0x03 - reserved
                0x04 - unrecognised PDU parameter
                0x05 - unexpected PDU parameter
                0x06 - invalid PDU parameter value
        """
        abort = A_ABORT_ServiceParameters()

        if source in [0x00, 0x02]:
            abort.AbortSource = source
            if source == 0x00:
                abort.Reason = 0x00
            elif reason in [0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06]:
                abort.Reason = reason
            else:
                raise ValueError("ACSE.Abort() invalid reason '%s'" %reason)
                
        else:
            raise ValueError("ACSE.Abort() invalid source '%s'" %source)

        self.DUL.Send(abort)
        time.sleep(0.5)

    def CheckRelease(self):
        """Checks for release request from the remote AE. Upon reception of
        the request a confirmation is sent"""
        rel = self.DUL.Peek()
        if rel.__class__ == A_RELEASE_ServiceParameters:
            # Make sure this is a A-RELEASE request primitive
            if rel.Result == 'affirmative':
                return False
                
            self.DUL.Receive(Wait=False)
            relrsp = A_RELEASE_ServiceParameters()
            relrsp.Result = 0
            self.DUL.Send(relrsp)
            return True
        else:
            return False

    def CheckAbort(self):
        """Checks for abort indication from the remote AE. """
        rel = self.DUL.Peek()
        # Abort is a non-confirmed service no so need to worry if its a request
        #   primitive
        if rel.__class__ in (A_ABORT_ServiceParameters,
                             A_P_ABORT_ServiceParameters):
            self.DUL.Receive(Wait=False)
            return True
        else:
            return False

    def Status(self):
        return self.DUL.state_machine.current_state()

    def Kill(self):
        self.DUL.Kill()


    # ACSE logging/debugging functions
    # Local AE sending PDU to peer AE
    def debug_send_associate_rq(self, a_associate_rq):
        """
        Placeholder for a function callback. Function will be called 
        immediately prior to encoding and sending an A-ASSOCIATE-RQ to 
        a peer AE
        
        The default implementation is used for logging debugging information
        
        Parameters
        ----------
        a_associate_rq - pynetdicom.PDU.A_ASSOCIATE_RQ_PDU
            The A-ASSOCIATE-RQ PDU instance to be encoded and sent
        """
        # Shorthand
        assoc_rq = a_associate_rq
        
        app_context   = assoc_rq.ApplicationContext.__repr__()[1:-1]
        pres_contexts = assoc_rq.PresentationContext
        user_info     = assoc_rq.UserInformation
        
        s = ['Request Parameters:']
        s.append('====================== BEGIN A-ASSOCIATE-RQ ================'
                '=====')
        
        s.append('Our Implementation Class UID:      %s' 
                                        %user_info.ImplementationClassUID)
        s.append('Our Implementation Version Name:   %s' 
                                        %user_info.ImplementationVersionName)
        s.append('Application Context Name:    %s' %app_context)
        s.append('Calling Application Name:    %s' %assoc_rq.CallingAETitle)
        s.append('Called Application Name:     %s' %assoc_rq.CalledAETitle)
        s.append('Our Max PDU Receive Size:    %s' %user_info.MaximumLength)
        
        # Presentation Contexts
        if len(pres_contexts) == 1:
            s.append('Presentation Context:')
        else:
            s.append('Presentation Contexts:')

        for context in pres_contexts:
            s.append('  Context ID:        %s (Proposed)' %(context.ID))
            s.append('    Abstract Syntax: =%s' %context.AbstractSyntax)
            
            if 'SCU' in context.__dict__.keys():
                scp_scu_role = '%s/%s' %(context.SCP, context.SCU)
            else:
                scp_scu_role = 'Default'
            s.append('    Proposed SCP/SCU Role: %s' %scp_scu_role)
            
            # Transfer Syntaxes
            if len(context.TransferSyntax) == 1:
                s.append('    Proposed Transfer Syntax:')
            else:
                s.append('    Proposed Transfer Syntaxes:')
                
            for ts in context.TransferSyntax:
                s.append('      =%s' %ts.name)
        
        ext_nego = 'None'
        #if assoc_rq.UserInformation.ExtendedNegotiation is not None:
        #    ext_nego = 'Yes'
        s.append('Requested Extended Negotiation: %s' %ext_nego)
        
        usr_id = 'None'
        if assoc_rq.UserInformation.UserIdentity is not None:
            usr_id = 'Yes'
        s.append('Requested User Identity Negotiation: %s' %usr_id)
        s.append('======================= END A-ASSOCIATE-RQ =================='
                '====')
        
        for line in s:
            logger.debug(line)
        
    def debug_send_associate_ac(self, a_associate_ac):
        """
        Placeholder for a function callback. Function will be called 
        immediately prior to encoding and sending an A-ASSOCIATE-AC to a peer AE
        
        Parameters
        ----------
        a_associate_ac - pynetdicom.PDU.A_ASSOCIATE_AC_PDU
            The A-ASSOCIATE-AC PDU instance
        """
        logger.info("Association Acknowledged")
        
        # Shorthand
        assoc_ac = a_associate_ac
        
        # Needs some cleanup
        app_context   = assoc_ac.ApplicationContext.__repr__()[1:-1]
        pres_contexts = assoc_ac.PresentationContext
        user_info     = assoc_ac.UserInformation
        
        responding_ae = 'resp. AP Title'
        
        s = ['Accept Parameters:']
        s.append('====================== BEGIN A-ASSOCIATE-AC ================'
                '=====')
        
        s.append('Our Implementation Class UID:      %s' 
                                        %user_info.ImplementationClassUID)
        s.append('Our Implementation Version Name:   %s' 
                                        %user_info.ImplementationVersionName)
        s.append('Application Context Name:    %s' %app_context)
        s.append('Responding Application Name: %s' %responding_ae)
        s.append('Our Max PDU Receive Size:    %s' %user_info.MaximumLength)
        s.append('Presentation Contexts:')
        
        for item in pres_contexts:
            s.append('  Context ID:        %s (%s)' %(item.ID, item.Result))
            
            # If Presentation Context was accepted
            if item.ResultReason == 0:
                if item.SCP is None and item.SCU is None:
                    ac_scp_scu_role = 'Default'
                else:
                    ac_scp_scu_role = '%s/%s' %(item.SCP, item.SCU)
                s.append('    Accepted SCP/SCU Role: %s' %ac_scp_scu_role)
                s.append('    Accepted Transfer Syntax: =%s' %item.TransferSyntax)
                
        ext_nego = 'None'
        #if assoc_ac.UserInformation.ExtendedNegotiation is not None:
        #    ext_nego = 'Yes'
        s.append('Accepted Extended Negotiation: %s' %ext_nego)
        
        usr_id = 'None'
        if assoc_ac.UserInformation.UserIdentity is not None:
            usr_id = 'Yes'
        
        s.append('User Identity Negotiation Response:  %s' %usr_id)
        s.append('======================= END A-ASSOCIATE-AC =================='
                '====')
        
        for line in s:
            logger.debug(line)
        
    def debug_send_associate_rj(self, a_associate_rj):
        """
        Placeholder for a function callback. Function will be called 
        immediately prior to encoding and sending an A-ASSOCIATE-RJ to a peer AE
        
        Parameters
        ----------
        a_associate_rj - pynetdicom.PDU.A_ASSOCIATE_RJ_PDU
            The A-ASSOCIATE-RJ PDU instance
        """
        pass
    
    def debug_send_data_tf(self, p_data_tf):
        """
        Placeholder for a function callback. Function will be called 
        immediately prior to encoding and sending an P-DATA-TF to a peer AE
        
        Parameters
        ----------
        a_release_rq - pynetdicom.PDU.P_DATA_TF_PDU
            The P-DATA-TF PDU instance
        """
        pass
    
    def debug_send_release_rq(self, a_release_rq):
        """
        Placeholder for a function callback. Function will be called 
        immediately prior to encoding and sending an A-RELEASE-RQ to a peer AE
        
        Parameters
        ----------
        a_release_rq - pynetdicom.PDU.A_RELEASE_RQ_PDU
            The A-RELEASE-RQ PDU instance
        """
        pass
        
    def debug_send_release_rp(self, a_release_rp):
        """
        Placeholder for a function callback. Function will be called 
        immediately prior to encoding and sending an A-RELEASE-RP to a peer AE
        
        Parameters
        ----------
        a_release_rp - pynetdicom.PDU.A_RELEASE_RP_PDU
            The A-RELEASE-RP PDU instance
        """
        pass
        
    def debug_send_abort(self, a_abort):
        """
        Placeholder for a function callback. Function will be called 
        immediately prior to encoding and sending an A-ABORT to a peer AE
        
        Parameters
        ----------
        a_abort - pynetdicom.PDU.A_ABORT_PDU
            The A-ABORT PDU instance
        """
        logger.info("Aborting Association")
        
        s = ['Abort Parameters:']
        s.append('========================== BEGIN A-ABORT ===================='
                '=====')
        s.append('Abort Source: %s' %a_abort.Source)
        s.append('Abort Reason: %s' %a_abort.Reason)
        s.append('=========================== END A-ABORT ====================='
                '====')
        for line in s:
            #logger.debug(line)
            pass


    # Local AE receiving PDU from peer AE
    def debug_receive_associate_rq(self, a_associate_rq):
        """
        Placeholder for a function callback. Function will be called 
        immediately after receiving and decoding an A-ASSOCIATE-RQ
        
        Parameters
        ----------
        a_associate_rq - pynetdicom.PDU.A_ASSOCIATE_RQ_PDU
            The A-ASSOCIATE-RQ PDU instance
        """
        logger.info("Association Received")
        
        # Shorthand
        assoc_rq = a_associate_rq
        
        app_context   = assoc_rq.ApplicationContext.__repr__()[1:-1]
        pres_contexts = assoc_rq.PresentationContext
        user_info     = assoc_rq.UserInformation
        
        responding_ae = 'resp. AP Title'
        their_class_uid = 'unknown'
        their_version = 'unknown'
        
        if user_info.ImplementationClassUID:
            their_class_uid = user_info.ImplementationClassUID
        if user_info.ImplementationVersionName:
            their_version = user_info.ImplementationVersionName
        
        s = ['Request Parameters:']
        s.append('====================== BEGIN A-ASSOCIATE-RQ ================'
                '=====')
        s.append('Their Implementation Class UID:    %s' %their_class_uid)
        s.append('Their Implementation Version Name: %s' %their_version)
        s.append('Application Context Name:    %s' %app_context)
        s.append('Calling Application Name:    %s' %assoc_rq.CallingAETitle)
        s.append('Called Application Name:     %s' %assoc_rq.CalledAETitle)
        s.append('Their Max PDU Receive Size:  %s' %user_info.MaximumLength)
        s.append('Presentation Contexts:')
        for item in pres_contexts:
            s.append('  Context ID:        %s (Proposed)' %item.ID)
            s.append('    Abstract Syntax: =%s' %item.AbstractSyntax)
            
            if item.SCU is None and item.SCP is None:
                scp_scu_role = 'Default'
            else:
                scp_scu_role = '%s/%s' %(item.SCP, item.SCU)
            
            s.append('    Proposed SCP/SCU Role: %s' %scp_scu_role)
            s.append('    Proposed Transfer Syntax(es):')
            for ts in item.TransferSyntax:
                s.append('      =%s' %ts)
        
        ext_nego = 'None'
        #if assoc_rq.UserInformation.ExtendedNegotiation is not None:
        #    ext_nego = 'Yes'
        s.append('Requested Extended Negotiation: %s' %ext_nego)
        
        usr_id = 'None'
        if user_info.UserIdentity is not None:
            usr_id = 'Yes'
        s.append('Requested User Identity Negotiation: %s' %usr_id)
        s.append('======================= END A-ASSOCIATE-RQ =================='
                '====')
        
        for line in s:
            logger.debug(line)
        
    def debug_receive_associate_ac(self, a_associate_ac):
        """
        Placeholder for a function callback. Function will be called 
        immediately after receiving and decoding an A-ASSOCIATE-AC
        
        The default implementation is used for logging debugging information
        
        Most of this should be moved to on_association_accepted()
        
        Parameters
        ----------
        a_associate_ac - pynetdicom.PDU.A_ASSOCIATE_AC_PDU
            The A-ASSOCIATE-AC PDU instance
        """
        # Shorthand
        assoc_ac = a_associate_ac
        
        app_context   = assoc_ac.ApplicationContext.__repr__()[1:-1]
        pres_contexts = assoc_ac.PresentationContext
        user_info     = assoc_ac.UserInformation
        
        their_class_uid = 'unknown'
        their_version = 'unknown'
        
        if user_info.ImplementationClassUID:
            their_class_uid = user_info.ImplementationClassUID
        if user_info.ImplementationVersionName:
            their_version = user_info.ImplementationVersionName
        
        s = ['Accept Parameters:']
        s.append('====================== BEGIN A-ASSOCIATE-AC ================'
                '=====')
        
        s.append('Their Implementation Class UID:    %s' %their_class_uid)
        s.append('Their Implementation Version Name: %s' %their_version)
        s.append('Application Context Name:    %s' %app_context)
        s.append('Calling Application Name:    %s' %assoc_ac.CallingAETitle)
        s.append('Called Application Name:     %s' %assoc_ac.CalledAETitle)
        s.append('Their Max PDU Receive Size:  %s' %user_info.MaximumLength)
        s.append('Presentation Contexts:')
        
        for item in pres_contexts:
            s.append('  Context ID:        %s (%s)' %(item.ID, item.Result))

            if item.ResultReason == 0:
                if item.SCP is None and item.SCU is None:
                    ac_scp_scu_role = 'Default'
                    rq_scp_scu_role = 'Default'
                else:
                    ac_scp_scu_role = '%s/%s' %(item.SCP, item.SCU)
                s.append('    Proposed SCP/SCU Role: %s' %rq_scp_scu_role)
                s.append('    Accepted SCP/SCU Role: %s' %ac_scp_scu_role)
                s.append('    Accepted Transfer Syntax: =%s' 
                                            %item.TransferSyntax)
        
        ext_nego = 'None'
        #if assoc_ac.UserInformation.ExtendedNegotiation is not None:
        #    ext_nego = 'Yes'
        s.append('Accepted Extended Negotiation: %s' %ext_nego)
        
        usr_id = 'None'
        if assoc_ac.UserInformation.UserIdentity is not None:
            usr_id = 'Yes'
        
        s.append('User Identity Negotiation Response:  %s' %usr_id)
        s.append('======================= END A-ASSOCIATE-AC =================='
                '====')
        
        for line in s:
            logger.debug(line)
        
    def debug_receive_associate_rj(self, a_associate_rj):
        """
        Placeholder for a function callback. Function will be called 
        immediately after receiving and decoding an A-ASSOCIATE-RJ
        
        Parameters
        ----------
        a_associate_rj - pynetdicom.PDU.A_ASSOCIATE_RJ_PDU
            The A-ASSOCIATE-RJ PDU instance
        """
        # Shorthand
        assoc_rj = a_associate_rj
        
        s = ['Reject Parameters:']
        s.append('====================== BEGIN A-ASSOCIATE-RJ ================'
                '=====')
        s.append('Result:    %s' %assoc_rj.ResultString)
        s.append('Source:    %s' %assoc_rj.SourceString)
        s.append('Reason:    %s' %assoc_rj.Reason)
        s.append('======================= END A-ASSOCIATE-RJ =================='
                '====')
        for line in s:
            logger.debug(line)
    
    def debug_receive_data_tf(self, p_data_tf):
        """
        Placeholder for a function callback. Function will be called 
        immediately after receiving and decoding an P-DATA-TF
        
        Parameters
        ----------
        a_release_rq - pynetdicom.PDU.P_DATA_TF_PDU
            The P-DATA-TF PDU instance
        """
        return
        
        # Shorthand
        p_data = p_data_tf
        
        s = ['Data Parameters:']
        s.append('========================= BEGIN P-DATA-TF ==================='
                '=====')
        s.append('Number of PDVs Received: %d' %len(p_data.PDVs))
        
        for ii, pdv in enumerate(p_data.PDVs):
            s.append('PDV %d' %(ii + 1))
            s.append('  Presentation context ID: %s' %pdv.ID)
            s.append('  Message control header byte: %s' %pdv.MessageControlHeader)
            s.append('  Size: %s bytes' %pdv.Length)
        
        s.append('========================== END P-DATA-TF ===================='
                '====')
        for line in s:
            logger.debug(line)
        
    def debug_receive_release_rq(self, a_release_rq):
        """
        Placeholder for a function callback. Function will be called 
        immediately after receiving and decoding an A-RELEASE-RQ
        
        Parameters
        ----------
        a_release_rq - pynetdicom.PDU.A_RELEASE_RQ_PDU
            The A-RELEASE-RQ PDU instance
        """
        pass
        
    def debug_receive_release_rp(self, a_release_rp):
        """
        Placeholder for a function callback. Function will be called 
        immediately after receiving and decoding an A-RELEASE-RP
        
        Parameters
        ----------
        a_release_rp - pynetdicom.PDU.A_RELEASE_RP_PDU
            The A-RELEASE-RP PDU instance
        """
        pass
        
    def debug_receive_abort(self, a_abort):
        """
        Placeholder for a function callback. Function will be called 
        immediately after receiving and decoding an A-ABORT
        
        Parameters
        ----------
        a_abort - pynetdicom.PDU.A_ABORT_PDU
            The A-ABORT PDU instance
        """
        
        s = ['Abort Parameters:']
        s.append('========================== BEGIN A-ABORT ===================='
                '=====')
        s.append('Abort Source: %s' %a_abort.Source)
        s.append('Abort Reason: %s' %a_abort.Reason)
        s.append('=========================== END A-ABORT ====================='
                '====')
        for line in s:
            logger.debug(line)

