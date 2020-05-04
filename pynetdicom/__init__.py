"""Set module shortcuts and globals"""

import logging

from pydicom.uid import UID

from ._version import __version__, __version_info__

# UID prefix provided by https://www.medicalconnections.co.uk/Free_UID
# Encoded as UI, 64 bytes maximum
PYNETDICOM_UID_PREFIX = '1.2.826.0.1.3680043.9.3811.'
"""``1.2.826.0.1.3680043.9.3811.``

The UID root used by *pynetdicom*.
"""

# Encoded as SH, 16 bytes maximum
PYNETDICOM_IMPLEMENTATION_VERSION = (
    'PYNETDICOM_' + ''.join([str(ii) for ii in __version_info__['release']])
)
"""The (0002,0013) *Implementation Version Name* used by *pynetdicom*"""
assert 1 <= len(PYNETDICOM_IMPLEMENTATION_VERSION) <= 16

PYNETDICOM_IMPLEMENTATION_UID = UID(
    PYNETDICOM_UID_PREFIX + '.'.join(
        [str(ii) for ii in __version_info__['release']]
    )
)
"""The (0002,0012) *Implementation Class UID* used by *pynetdicom*"""
assert PYNETDICOM_IMPLEMENTATION_UID.is_valid


# Convenience imports
from pynetdicom import events as evt
from pynetdicom.ae import ApplicationEntity as AE
from pynetdicom.association import Association
from pynetdicom._globals import (
    ALL_TRANSFER_SYNTAXES, DEFAULT_TRANSFER_SYNTAXES
)
from pynetdicom.presentation import (
    build_context,
    build_role,
    AllStoragePresentationContexts,
    ApplicationEventLoggingPresentationContexts,
    BasicWorklistManagementPresentationContexts,
    ColorPalettePresentationContexts,
    DefinedProcedureProtocolPresentationContexts,
    DisplaySystemPresentationContexts,
    HangingProtocolPresentationContexts,
    ImplantTemplatePresentationContexts,
    InstanceAvailabilityPresentationContexts,
    MediaCreationManagementPresentationContexts,
    MediaStoragePresentationContexts,
    ModalityPerformedPresentationContexts,
    NonPatientObjectPresentationContexts,
    PrintManagementPresentationContexts,
    ProcedureStepPresentationContexts,
    ProtocolApprovalPresentationContexts,
    QueryRetrievePresentationContexts,
    RelevantPatientInformationPresentationContexts,
    RTMachineVerificationPresentationContexts,
    StoragePresentationContexts,
    StorageCommitmentPresentationContexts,
    SubstanceAdministrationPresentationContexts,
    UnifiedProcedurePresentationContexts,
    VerificationPresentationContexts,
)


# Setup default logging
logging.getLogger('pynetdicom').addHandler(logging.NullHandler())


def debug_logger():
    """Setup the logging for debugging."""
    logger = logging.getLogger('pynetdicom')
    # Ensure only have one StreamHandler
    logger.handlers = []
    handler = logging.StreamHandler()
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(levelname).1s: %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)


import sys
if sys.version_info[0] == 2:
    import warnings
    msg = (
        "Python 2 will no longer be supported after the pynetdicom v1.5 "
        "release"
    )
    warnings.warn(msg, DeprecationWarning)
