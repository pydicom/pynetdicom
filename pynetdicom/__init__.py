"""Set module shortcuts and globals"""

import logging

from pydicom._uid_dict import UID_dictionary
from pydicom.uid import UID

from ._version import __version__

# fmt: off
# Update pydicom's UID dictionary with any missing transfer syntaxes
UID_dictionary.update(
    {
        '1.2.840.10008.1.2.4.110': ('JPEG XL Lossless', 'Transfer Syntax', '', '', 'JPEGXLLossless'),
        '1.2.840.10008.1.2.4.111': ('JPEG XL JPEG Recompression', 'Transfer Syntax', '', '', 'JPEGXLJPEGRecompression'),
        '1.2.840.10008.1.2.4.112': ('JPEG XL', 'Transfer Syntax', '', '', 'JPEGXL'),
        '1.2.840.10008.1.2.8.1': ('Deflated Image Frame Compression', 'Transfer Syntax', '', '', 'DeflatedImageFrameCompression'),
    }
)
# fmt: on

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
# ruff: noqa: F401
from pynetdicom import events as evt
from pynetdicom._globals import (
    ALL_TRANSFER_SYNTAXES,
    DEFAULT_TRANSFER_SYNTAXES,
)
from pynetdicom.ae import ApplicationEntity as AE
from pynetdicom.association import Association
from pynetdicom.presentation import (
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
    StorageCommitmentPresentationContexts,
    StoragePresentationContexts,
    SubstanceAdministrationPresentationContexts,
    UnifiedProcedurePresentationContexts,
    VerificationPresentationContexts,
    build_context,
    build_role,
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
    "AE",
    "ALL_TRANSFER_SYNTAXES",
    "DEFAULT_TRANSFER_SYNTAXES",
    "PYNETDICOM_IMPLEMENTATION_UID",
    "PYNETDICOM_IMPLEMENTATION_VERSION",
    "PYNETDICOM_UID_PREFIX",
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
    "RTMachineVerificationPresentationContexts",
    "RelevantPatientInformationPresentationContexts",
    "StorageCommitmentPresentationContexts",
    "StoragePresentationContexts",
    "SubstanceAdministrationPresentationContexts",
    "UnifiedProcedurePresentationContexts",
    "VerificationPresentationContexts",
    "__version__",
    "build_context",
    "build_role",
    "debug_logger",
    "evt",
    "register_uid",
]
