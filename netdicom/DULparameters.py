# DUL Service Parameters
# 3.8 Section 7


class ServiceParam:

    def __repr__(self):
        tmp = ''
        for ii in self.__dict__.keys():
            tmp += str(ii) + ' ' + str(self.__dict__[ii]) + ' ' + '\n'
        return tmp


#
# A-ASSOCIATE service parameters
#
class A_ASSOCIATE_ServiceParameters(ServiceParam):

    def __init__(self):
        self.Mode = "normal"
        self.ApplicationContextName = None                  # String
        self.CallingAETitle = None                          # String
        self.CalledAETitle = None                           # String
        self.RespondingAETitle = None                       # String
        # List of raw strings
        self.UserInformation = None
        self.Result = None                                  # Int in (0,1,2)
        self.ResultSource = None                            # Int in (0,1,2)
        self.Diagnostic = None                              # Int
        self.CallingPresentationAddress = None              # String
        self.CalledPresentationAddress = None               # String
        self.RespondingPresentationAddress = None           # String
        # List of [ID, AbsName, [TrNames]]
        self.PresentationContextDefinitionList = []
        # List of [ID, Result, TrName]
        self.PresentationContextDefinitionResultList = []
        self.PresentationRequirements = "Presentation Kernel"
        self.SessionRequirements = ""

#
# A-RELEASE service parameters
#


class A_RELEASE_ServiceParameters:

    def __init__(self):
        self.Reason = None
        self.Result = None   # Must be None for Request and Indication
                             # Must be "affirmative" for Response and
                             # Confirmation

#
# A-ABORT Service parameters
#


class A_ABORT_ServiceParameters:

    def __init__(self):
        self.AbortSource = None
        self.UserInformation = None

#
# A-P-ABORT Service parameters
#


class A_P_ABORT_ServiceParameters:

    def __init__(self):
        self.ProviderReason = None

#
# P-DATA Service parameters
#


class P_DATA_ServiceParameters:

    def __init__(self):
        # should be of the form [ [ID, pdv], [ID, pdv] ... ]
        self.PresentationDataValueList = None






#
# A-ASSOCIATE results
#
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



