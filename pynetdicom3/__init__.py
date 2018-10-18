"""
Set module shortcuts and globals
"""
from pydicom.uid import UID

version = ['0', '9', '1']
__version__ = '.'.join(version)

# UID prefix provided by https://www.medicalconnections.co.uk/Free_UID
# Encoded as UI, 64 bytes maximum
PYNETDICOM_UID_PREFIX = '1.2.826.0.1.3680043.9.3811.'

# Encoded as SH, 16 bytes maximum
PYNETDICOM_IMPLEMENTATION_VERSION = 'PYNETDICOM3_' + ''.join(version)
assert 1 <= len(PYNETDICOM_IMPLEMENTATION_VERSION) <= 16

PYNETDICOM_IMPLEMENTATION_UID = UID(PYNETDICOM_UID_PREFIX + '.'.join(version))
assert PYNETDICOM_IMPLEMENTATION_UID.is_valid

# Deprecated, will be removed in v1.0
pynetdicom_uid_prefix = PYNETDICOM_UID_PREFIX
pynetdicom_version = PYNETDICOM_IMPLEMENTATION_VERSION
pynetdicom_implementation_uid = PYNETDICOM_IMPLEMENTATION_UID


import logging

# Convenience imports
from pynetdicom3.ae import ApplicationEntity as AE
from pynetdicom3.association import Association
from pynetdicom3.presentation import (
    build_context,
    DEFAULT_TRANSFER_SYNTAXES,
    VerificationPresentationContexts,
    StoragePresentationContexts,
    QueryRetrievePresentationContexts,
    BasicWorklistManagementPresentationContexts,
    RelevantPatientInformationQueryPresentationContexts,
)
