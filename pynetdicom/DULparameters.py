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
    
    See PS3.8 Section 7.2.1
    """
    def __init__(self):
        # 7.2.1.1 Reason (fixed value)
        self.Reason = "normal"
        # 7.2.1.2 Result (fixed value)
        self.Result = "affirmative"


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


class P_DATA_ServiceParameters:
    """ 
    P-DATA Parameters
    
    See PS3.8 Section 7.6.1
    """
    def __init__(self):
        # should be of the form [ [ID, pdv], [ID, pdv] ... ]
        self.PresentationDataValueList = None


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



