
from pynetdicom.utils import validate_ae_title


class A_ASSOCIATE_ServiceParameters():
    """ 
    A-ASSOCIATE Parameters
    
    The establishment of an association between two AEs shall be performed 
    through ACSE A-ASSOCIATE request, indication, response and confirmation
    primitives.
    
    The initiator of the service is called the Requestor and the user that 
    receives the request is the Acceptor.
    
    See PS3.8 Section 7.1.1
    
    The A-ASSOCIATE primitive is used by the DUL provider to send/receive
    information about the association. It gets converted to A-ASSOCIATE-RQ, -AC,
    -RJ PDUs that are sent to the peer DUL provider and gets deconverted from 
    -RQ, -AC, -RJ PDUs received from the peer.
    
    It may be better to simply extend this with methods for containing the 
    -rq, -ac, -rj possibilities rather than creating a new 
    AssociationInformation class, but it would require maintaining the instance
    across the request-accept/reject path
    
    -rq = no Result value
    -ac = Result of 0x00
    -rj = Result != 0x00
    
    Parameter           Request     Indication      Response        Confirmation
    app context name    M           M(=)            M               M(=)
    calling ae title    M           M(=)            M               M(=)
    called ae title     M           M(=)            M               M(=)
    user info           M           M(=)            M               M(=)
    result                                          M               M(=)
    source                                                          M
    diagnostic                                      U               C(=)
    calling pres add    M           M(=)
    called pres add     M           M(=)
    pres context list   M           M(=)
    pres list result                                M               M(=)
    
    mode                UF          MF(=)
    resp ae title                                   MF              MF(=)
    resp pres add                                   MF              MF(=)
    pres and sess req   UF          UF(=)           UF              UF(=)
    
    U   - User option
    UF  - User option, fixed value
    C   - Conditional (on user option)
    M   - Mandatory
    MF  - Mandatory, fixed value
    (=) - shall have same value as request or response
    
    
    The Requestor sends a request primitive to the local DICOM UL provider => 
        peer UL => indication primitive to Acceptor.
    
    Acceptor sends response primitive to peer UL => local UL => confirmation
        primitive to Requestor
    
    The DICOM UL providers communicate with UL users using service primitives
    The DICOM UL providers communicate with each other using PDUs over TCP/IP
    
    Service Procedure
    =================
    1. An AE (DICOM UL service user) that desires the establish an association 
        issues an A-ASSOCIATE request primitive to the DICOM UL service 
        provider. The Requestor shall not issue any primitives except the
        A-ABORT request primitive until it receives an A-ASSOCIATE confirmation
        primitive.
    2. The DICOM UL service provider issues an A-ASSOCIATE indication primitive
        to the called AE
    3. The called AE shall accept or reject the association by sending an 
        A-ASSOCIATE response primitive with an appropriate Result parameter. The
        DICOM UL service provider shall issue an A-ASSOCIATE confirmation 
        primitive having the same Result parameter. The Result Source parameter
        shall be assigned "UL service-user"
    4. If the Acceptor accepts the association, it is established and is 
        available for use. DIMSE messages can now be exchanged.
    5. If the Acceptor rejects the association, it shall not be established and
        is not available for use
    6. If the DICOM UL service provider is not capable of supporting the 
        requested association it shall return an A-ASSOCIATE confirmation 
        primitive to the Requestor with an appropriate Result parameter 
        (rejected). The Result Source parameter shall be assigned either
        UL service provider (ACSE) or UL service provider (Presentation).
        The indication primitive shall not be issued. The association shall not
        be established.
    7. Either Requestor or Acceptor may disrupt the Service Procedure by issuing
        an A-ABORT request primitive. The remote AE receives an A-ABORT 
        indication primitive. The association shall not be established
    """
    def __init__(self):
        # 7.1.1.1 Mode (fixed)  [UF, MF(=), _, _]
        self.Mode = "normal"
        
        # 7.1.1.2 Application Context Name [M, M(=), M, M(=)]
        # The name proposed by the requestor. Acceptor returns either
        #   the same or a different name. Returned name specifies the 
        #   application context used for the association. See PS3.8 Annex A
        self.ApplicationContextName = None
        
        # 7.1.1.3 Calling AE Title [M, M(=), M, M(=)]
        # Identifies the Requestor of the A-ASSOCIATE service
        self.CallingAETitle = None
        
        # 7.1.1.4 Calling AE Title [M, M(=), M, M(=)]
        # Identifies the intended Acceptor of the A-ASSOCIATE service
        self.CalledAETitle = None
        
        # 7.1.1.5 Responding AE Title (fixed) [_, _, MF, MF(=)]
        # Identifies the AE that contains the actual acceptor of the 
        #   A-ASSOCIATE service. Shall always contain the same value as the 
        #   Called AE Title of the A-ASSOCIATE indication
        self.RespondingAETitle = self.CalledAETitle
        
        # 7.1.1.6 User Information [M, M(=), M, M(=)]
        # Used by Requestor and Acceptor to include AE user information. See
        #   PS3.8 Annex D
        self.UserInformation = None
        
        # 7.1.1.7 Result [_, _, M, M(=)]
        # Provided either by the Acceptor of the A-ASSOCIATE request, the UL
        #   service provider (ACSE related) or the UL service provider 
        #   (Presentation related). Indicates the result of the A-ASSOCIATE
        #   service. Symbolic values are: accepted, rejected (permanent),
        #   rejected (transient)
        self.Result = None
        
        # 7.1.1.8 Result Source [_, _, _, M]
        # Identifies the creating source of the Result and Diagnostic parameters
        #   Symbolic values are: UL service-user, UL service-provider (ACSE 
        #   related function) or UL service-provider (Presentation related 
        #   function)
        self.ResultSource = None
        
        # 7.1.1.9 Diagnostic [_, _, U, C(=)]
        # If the Result parameter is 'rejected (permanent)' or 'rejected 
        #   (transient)' then this supplies diagnostic information about the 
        #   result.
        # If Result Source = 'UL service-user' then symbolic values are:
        #       no reason given 
        #       application context name not supported
        #       calling AE title not recognised
        #       called AE title not recognised
        # If Result Source = 'UL service-provider (ACSE related function)' then:
        #       no reason given
        #       no common UL version
        # If Result Source = 'UL service-provider (Presentation related 
        #   function)' then:
        #       no reason given
        #       temporary congestion
        #       local limit exceeded
        #       called presentation address unknown
        #       presentation protocol version not supported
        #       no presentation service access point available
        self.Diagnostic = None
        
        # 7.1.1.10 Calling Presentation Address [M, M(=), _, _]
        #  TCP/IP address of the Requestor
        self.CallingPresentationAddress = None
        
        # 7.1.1.11 Called Presentation Address [M, M(=), _, _]
        #  TCP/IP address of the intended Accetpr
        self.CalledPresentationAddress = None
        
        # 7.1.1.12 Responding Presentation Address (fixed) [_, _, MF, MF(=)]
        #  Shall always contain the same value as the Called Presentation Address
        self.RespondingPresentationAddress = self.CalledPresentationAddress
        
        # 7.1.1.13 Presentation Context Definition List [M, M(=), _, _]
        # List of one or more presentation contexts, with each item containing
        #   a presentation context ID, an Abstract Syntax and a list of one or
        #   more Transfer Syntax Names
        # Sent by the Requestor during request/indication
        self.PresentationContextDefinitionList = []
        
        # 7.1.1.14 Presentation Context Definition Result List [_, _, M, M(=)]
        # Used in response/confirmation to indicate acceptance or rejection of
        #   each presentation context definition.
        # List of result values, with a one-to-one correspondence between each
        #   of the presentation contexts proposed in the Presentation Context
        #   Definition List parameter. 
        # The result values may be sent in any order and may be different than 
        #   the order proposed.
        # Only one Transfer Syntax per presentation context shall be agreed to
        self.PresentationContextDefinitionResultList = []
        
        # 7.1.1.15 Presentation Requirements (fixed) [UF, UF(=), UF, UF(=)]
        self.PresentationRequirements = "Presentation Kernel"
        
        # 7.1.1.16 Session Requirements (fixed) [UF, UF(=), UF, UF(=)]
        self.SessionRequirements = ""

    @property
    def calling_ae_title(self):
        return self.__calling_ae_title.decode('utf-8').strip()

    @property
    def CallingAETitle(self):
        """ Returns a bytes string """
        return self.__calling_ae_title
        
    @CallingAETitle.setter
    def CallingAETitle(self, value):
        if value is not None:
            self.__calling_ae_title = validate_ae_title(value)
        else:
            self.__calling_ae_title = None
    
    @property
    def called_ae_title(self):
        return self.__called_ae_title.decode('utf-8').strip()
        
    @property
    def CalledAETitle(self):
        return self.__called_ae_title
        
    @CalledAETitle.setter
    def CalledAETitle(self, value):
        if value is not None:
            self.__called_ae_title = validate_ae_title(value)
        else:
            self.__called_ae_title = None

    # FIXME: Add properties for all user info items
    @property
    def maximum_length_received(self):
        from pynetdicom.PDU import MaximumLengthParameters
        
        for item in self.UserInformation:
            if isinstance(item, MaximumLengthParameters):
                return item.MaximumLengthReceived
        
        return 0


class A_RELEASE_ServiceParameters():
    """ 
    A-RELEASE Parameters
    
    The release of an association between two AEs shall be performed through
    ACSE A-RELEASE request, indication, response and confirmation primitives.
    The initiator of the service is called a Requestor and the service-user that 
    receives the A-RELEASE indication is called the acceptor.
    
    Service Procedure
    1. The user (Requestor) that desires to end the association issues an 
    A-RELEASE request primitive. The Requestor shall not issue any other
    primitives other than A-ABORT until it receives an A-RELEASE confirmation
    primitive.
    2. The DUL provider issues an A-RELEASE indication to the Acceptor. The
    Acceptor shall not issue any other primitives other than A-RELEASE response,
    A-ABORT request or P-DATA request.
    3. To complete the release, the Acceptor replies using an A-RELEASE response
    primitive, with "affirmative" as the result parameter.
    4. After the Acceptor issues the A-RELEASE response it shall not issue any
    more primitives.
    5. The Requestor shall issue an A-RELEASE confirmation primitive always
    with an "affirmative" value for the Result parameter.
    6. A user may disrupt the release by issuing an A-ABORT request.
    7. A collision may occur when both users issue A-RELEASE requests
    simultaneously. In this situation both users receive an unexpect A-RELEASE
    indication primitive (instead of an A-RELEASE acceptance):
        a. The association requestor issues an A-RELEASE response primitive
        b. The association acceptor waits for an A-RELEASE confirmation 
        primitive from its peer. When it receives one it issues an A-RELEASE
        response primitive
        c. The association requestor receives an A-RELEASE confirmation 
        primitive.
    When both ACSE users have received an A-RELEASE confirmation primitive the
    association shall be released.
    
    Parameter   Request     Indication      Response        Confirmation
    reason      UF          UF(=)           UF              UF(=)
    user info   NU          NU(=)           NU              NU(=)
    result                                  MF              MF(=)
    
    UF - User option, fixed
    NU - Not used
    MF - Mandatory, fixed
    (=) - shall have same value as request or response
    
    See PS3.8 Section 7.2
    """
    def __init__(self):
        # 7.2.1.1 Reason (fixed value)
        self.Reason = "normal"
        # 7.2.1.2 Result (fixed value)
        # Must be None for request and indication
        # "affirmative" for response and confirmation
        #self.Result = "affirmative"
        self.Result = None

    @property
    def Reason(self):
        return self.__reason

    @Reason.setter
    def Reason(self, value):
        self.__reason = "normal"


class A_ABORT_ServiceParameters():
    """ 
    A-ABORT Parameters
    
    See PS3.8 Section 7.3.1
    """
    def __init__(self):
        self.AbortSource = None
        self.UserInformation = None


class A_P_ABORT_ServiceParameters():
    """ 
    A-P-ABORT Parameters
    
    See PS3.8 Section 7.4.1
    """
    def __init__(self):
        # 7.4.1 lists the reasons
        self.ProviderReason = None


class P_DATA_ServiceParameters():
    """ 
    P-DATA Parameters
    
    See PS3.8 Section 7.6.1
    """
    def __init__(self):
        # Should be of the form [ [context ID, pdv], [context ID, pdv] ... ]
        self.PresentationDataValueList = None
    
    """
    def __str__(self):
        #print(dir(self))
        s = 'P-DATA\n'
        s += 'Presentation Data Value Items\n'
        for item in self.PresentationDataValueList:
            s += '  Context ID: %s\n' %item[0]
            s += '  Value Length: %s bytes\n' %len(item[1])
            header_byte = item[1][0]
            s += "  Message Control Header Byte: {:08b}\n".format(header_byte)
            
            # 00000001 and 00000011
            if header_byte & 1:
                # 00000011
                if header_byte & 2:
                    s += '  Command information, last fragment of the ' \
                                'DIMSE message\n'
                # 00000001
                else:
                    s += '  Command information, not the last fragment of ' \
                                'the DIMSE message\n'
            # 00000000, 00000010
            else:
                # 00000010
                if header_byte & 2 != 0:
                    s += '  Dataset information, last fragment of the ' \
                                'DIMSE message\n'
                # 00000000
                else:
                    s += '  Dataset information, not the last fragment of ' \
                                'the DIMSE message\n'
            
            s += wrap_list(item[1][1:], '    ', max_size=512) # Data value
        return s
    """

