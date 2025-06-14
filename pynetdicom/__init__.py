"""Set module shortcuts and globals"""

import logging

from pydicom.uid import UID

from ._version import __version__


_version = __version__.split(".")[:3]

# UID prefix provided by https://www.medicalconnections.co.uk/Free_UID
# Encoded as UI, maximum 64 characters
PYNETDICOM_UID_PREFIX = "1.2.826.0.1.3680043.9.3811."
"""``1.2.826.0.1.3680043.9.3811.``

The UID root used by *pynetdicom*.
"""

# Encoded as SH, maximum 16 characters
PYNETDICOM_IMPLEMENTATION_VERSION: str = f"PYNETDICOM_{''.join(_version)}"
"""The (0002,0013) *Implementation Version Name* used by *pynetdicom*"""
assert 1 <= len(PYNETDICOM_IMPLEMENTATION_VERSION) <= 16

PYNETDICOM_IMPLEMENTATION_UID: UID = UID(f"{PYNETDICOM_UID_PREFIX}{'.'.join(_version)}")
"""The (0002,0012) *Implementation Class UID* used by *pynetdicom*"""
assert PYNETDICOM_IMPLEMENTATION_UID.is_valid


# Convenience imports
# ruff: noqa: E402,F401
from pynetdicom import events as evt
from pynetdicom.ae import ApplicationEntity as AE
from pynetdicom.association import Association
from pynetdicom._globals import (
    ALL_TRANSFER_SYNTAXES,
    DEFAULT_TRANSFER_SYNTAXES,
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
from pynetdicom.sop_class import register_uid


# Setup default logging
logging.getLogger(__name__).addHandler(logging.NullHandler())


def debug_logger() -> None:
    """Setup the logging for debugging."""
    logger = logging.getLogger(__name__)
    # Ensure only have one StreamHandler
    logger.handlers = []
    handler = logging.StreamHandler()
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(levelname).1s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


__all__ = [
    "__version__",
    "PYNETDICOM_UID_PREFIX",
    "PYNETDICOM_IMPLEMENTATION_VERSION",
    "PYNETDICOM_IMPLEMENTATION_UID",
    "evt",
    "AE",
    "ALL_TRANSFER_SYNTAXES",
    "DEFAULT_TRANSFER_SYNTAXES",
    "build_context",
    "build_role",
    "AllStoragePresentationContexts",
    "ApplicationEventLoggingPresentationContexts",
    "BasicWorklistManagementPresentationContexts",
    "ColorPalettePresentationContexts",
    "DefinedProcedureProtocolPresentationContexts",
    "DisplaySystemPresentationContexts",
    "HangingProtocolPresentationContexts",
    "ImplantTemplatePresentationContexts",
    "InstanceAvailabilityPresentationContexts",
    "MediaCreationManagementPresentationContexts",
    "MediaStoragePresentationContexts",
    "ModalityPerformedPresentationContexts",
    "NonPatientObjectPresentationContexts",
    "PrintManagementPresentationContexts",
    "ProcedureStepPresentationContexts",
    "ProtocolApprovalPresentationContexts",
    "QueryRetrievePresentationContexts",
    "RelevantPatientInformationPresentationContexts",
    "RTMachineVerificationPresentationContexts",
    "StoragePresentationContexts",
    "StorageCommitmentPresentationContexts",
    "SubstanceAdministrationPresentationContexts",
    "UnifiedProcedurePresentationContexts",
    "VerificationPresentationContexts",
    "register_uid",
    "debug_logger",
]
