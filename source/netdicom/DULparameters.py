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


A_ASSOCIATE_ResultValues = (
    'accepted',
    'rejected (permanent)',
    'rejected (transient)')
A_ASSOCIATE_ResultSourceValues = (
    'UL service-user',
    'UL service provider (ACSE)',
    'UL service provider (Presentation)')
A_ASSOCIATE_DiagnosticValues = (
    # if ResultSource == 0
    ('no-reason given', 'application-context-name not supported',
     'calling-AE-title not recognized',
     'called-AE-title not recognized',
     'calling-AE-qualifier not recognized',
     'calling-AP-invocation-identifier not recognized',
     'calling-AE-invocation-identifier not recognized',
     'called-AE-qualifier not recognized',
     'called-AP-invocation-identifier not recognized',
     'called-AE-invocation-identifier not recognized'),
    # if ReseultSource == 1
    ('no-reason-given',
     'no-common-UL version'),
    # if ResultSource == 2
    ('no-reason-given',
     'temporary-congestion',
     'local-limit-exceeded',
     'called-(Presentation)-address-unknown',
     'Presentation-protocol version not supported',
     'no-(Presentation) Service Access Point (SAP) available'))
