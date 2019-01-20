"""Set module shortcuts and globals"""

from pydicom.uid import UID

from ._version import __version__, __version_info__

# UID prefix provided by https://www.medicalconnections.co.uk/Free_UID
# Encoded as UI, 64 bytes maximum
PYNETDICOM_UID_PREFIX = '1.2.826.0.1.3680043.9.3811.'

# Encoded as SH, 16 bytes maximum
PYNETDICOM_IMPLEMENTATION_VERSION = (
    'PYNETDICOM_' + ''.join([str(ii) for ii in __version_info__['release']])
)
assert 1 <= len(PYNETDICOM_IMPLEMENTATION_VERSION) <= 16

PYNETDICOM_IMPLEMENTATION_UID = UID(
    PYNETDICOM_UID_PREFIX + '.'.join(
        [str(ii) for ii in __version_info__['release']]
    )
)
assert PYNETDICOM_IMPLEMENTATION_UID.is_valid

import logging

# Convenience imports
from pynetdicom.ae import ApplicationEntity as AE
from pynetdicom.association import Association
from pynetdicom.presentation import (
    build_context,
    build_role,
    DEFAULT_TRANSFER_SYNTAXES,
    VerificationPresentationContexts,
    StoragePresentationContexts,
    QueryRetrievePresentationContexts,
    BasicWorklistManagementPresentationContexts,
    RelevantPatientInformationPresentationContexts,
    SubstanceAdministrationPresentationContexts,
    NonPatientObjectPresentationContexts,
    HangingProtocolPresentationContexts,
    DefinedProcedureProtocolPresentationContexts,
    ColorPalettePresentationContexts,
    ImplantTemplatePresentationContexts,
    DisplaySystemPresentationContexts,
)
