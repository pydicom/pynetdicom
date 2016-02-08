# DUL Service Parameters
# 3.8 Section 7


class ServiceParam:
    def __repr__(self):
        tmp = ''
        for ii in self.__dict__.keys():
            tmp += str(ii) + ' ' + str(self.__dict__[ii]) + ' ' + '\n'
        return tmp


class A_ASSOCIATE_ServiceParameters(ServiceParam):
    """ 
    A-ASSOCIATE Parameters
    
    See PS3.8 Section 7.1.1
    
    I'd be happier if these values were created programatically...
    """
    def __init__(self):
        # 7.1.1.1 Mode (fixed value)
        self.Mode = "normal"
        # Strings
        self.ApplicationContextName = None
        self.CallingAETitle = None
        self.CalledAETitle = None
        self.RespondingAETitle = None
        # List of raw strings
        self.UserInformation = None
        # a) accepted
        # b) rejected (permanent)
        # c) rejected (transient)
        self.Result = None
        # a) UL service-user
        # b) UL service-provider (ACSE related function)
        # c) UL service-provider (Presentation related function)
        self.ResultSource = None
        # 7.1.1.9 Diagnostic - If association is rejected then this supplies
        #   diagnostic information about the result
        self.Diagnostic = None                              # Int
        # TCP/IP Address
        self.CallingPresentationAddress = None              # String
        # TCP/IP Address
        self.CalledPresentationAddress = None               # String
        self.RespondingPresentationAddress = None           # String
        # List of [ID, AbsName, [TrNames]]
        self.PresentationContextDefinitionList = []
        # List of [ID, Result, TrName]
        self.PresentationContextDefinitionResultList = []
        # 7.1.1.15 Presentation Requirements (fixed value)
        self.PresentationRequirements = "Presentation Kernel"
        # 7.1.1.16 Session Requirements (fixed value)
        self.SessionRequirements = ""


class A_RELEASE_ServiceParameters:
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


class A_ABORT_ServiceParameters:
    """ 
    A-ABORT Parameters
    
    See PS3.8 Section 7.3.1
    """
    def __init__(self):
        # a) UL service-user
        # b) UL service-provider (ACSE related)
        self.AbortSource = None
        # 
        self.UserInformation = None


class A_P_ABORT_ServiceParameters:
    """ 
    A-P-ABORT Parameters
    
    See PS3.8 Section 7.4.1
    """
    def __init__(self):
        # 7.4.1 lists the reasons
        self.ProviderReason = None


def wrap_list(lst, prefix='D:   ', items_per_line=16, max_size=None):
    lines = []
    cutoff_output = False
    byte_count = 0
    for i in range(0, len(lst), items_per_line):
        chunk = lst[i:i + items_per_line]
        byte_count += len(chunk)
        
        if max_size is not None:
            if byte_count <= max_size:
                line = prefix + '  '.join(format(x, '02x') for x in chunk)
                lines.append(line)
            else:
                cutoff_output = True
                break
        else:
            line = prefix + '  '.join(format(x, '02x') for x in chunk)
            lines.append(line)
    
    if cutoff_output:
        lines.insert(0, prefix + 'Only dumping 512 bytes.')
    
    return "\n".join(lines)

class P_DATA_ServiceParameters:
    """ 
    P-DATA Parameters
    
    See PS3.8 Section 7.6.1
    """
    def __init__(self):
        # Should be of the form [ [context ID, pdv], [context ID, pdv] ... ]
        self.PresentationDataValueList = None
        
    def __str__(self):
        #print(dir(self))
        s = 'P-DATA\n'
        s += 'Presentation Data Value Items\n'
        for item in self.PresentationDataValueList:
            s += '  Context ID: %s\n' %item[0]
            s += '  Value Length: %s bytes\n' %len(item[1])
            header_byte = item[1][0]
            s += "  Message Control Header Byte: {:08b}\n".format(header_byte)
            s += wrap_list(item[1][1:], '    ', max_size=512) # Data value
        return s


#
# A-ASSOCIATE results
#
# This seems clunky
# In any case, constants should be all caps
A_ASSOCIATE_Result_Accepted = 0
A_ASSOCIATE_Result_RejectedPermanent = 1
A_ASSOCIATE_Result_RejectedTransient = 2

A_ASSOCIATE_ResultSource_ServiceUser = 1
A_ASSOCIATE_ResultSource_ServiceProviderACSE = 2
A_ASSOCIATE_ResultSource_ServiceProviderPresentation = 3


class A_ASSOCIATE_Diag(object):
    def __init__(self, code, source):
        self.code = code
        self.source = source

    def __int__(self):
        return self.code


A_ASSOCIATE_Diag_NoReasonUser = A_ASSOCIATE_Diag(1, A_ASSOCIATE_ResultSource_ServiceUser)
A_ASSOCIATE_Diag_AppContextNameNotRecognized = A_ASSOCIATE_Diag(2, A_ASSOCIATE_ResultSource_ServiceUser)
A_ASSOCIATE_Diag_CallingAETitleNotRecognized = A_ASSOCIATE_Diag(3, A_ASSOCIATE_ResultSource_ServiceUser)
A_ASSOCIATE_Diag_CalledAETitleNotRecognized = A_ASSOCIATE_Diag(7, A_ASSOCIATE_ResultSource_ServiceUser)

A_ASSOCIATE_Diag_NoReasonProvider = A_ASSOCIATE_Diag(1, A_ASSOCIATE_ResultSource_ServiceProviderACSE)
A_ASSOCIATE_Diag_ProtocolVersionNotSupported = A_ASSOCIATE_Diag(2, A_ASSOCIATE_ResultSource_ServiceProviderACSE)

A_ASSOCIATE_Diag_TemporaryCongestion = A_ASSOCIATE_Diag(1, A_ASSOCIATE_ResultSource_ServiceProviderPresentation)
A_ASSOCIATE_Diag_LocalLimitExceeded = A_ASSOCIATE_Diag(2, A_ASSOCIATE_ResultSource_ServiceProviderPresentation)



