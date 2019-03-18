"""pynetdicom configuration options"""


# During C-STORE operations:
#   * If True, decode the request's DataSet parameter value to a pydicom
#     Dataset before passing it to ApplicationEntity.on_c_store(),
#   * If False, skip decoding and pass the raw encoded bytes to
#     ApplicationEntity.on_c_store()
# Setting the value to False has a couple of benefits:
#   * Writing received data to file is faster since the dataset
#     decoding/encoding steps are skipped
#   * A Storage SCP should also run ~15% faster as the decode is skipped
#   * Any issues with dataset decoding (bugs, non-conformance) are bypassed
# Usage:
#   from pynetdicom import _config
#   _config.DECODE_STORE_DATASETS = (True|False)
# Deprecated and will be removed in v1.4, use the event handler system instead
#   as it provides all the benefits listed above by default
DECODE_STORE_DATASETS = True


# Default (non-user) event logging
#   * If 'none' then events will not be logged at all, however there will still
#     be some logging (warnings, errors, etc)
#   * If 'standard' then certain events will be logged (association
#     negotiation, DIMSE messaging, etc)
# Usage:
#   from pynetdicom import _config
#   _config.LOG_HANDLER_LEVEL = ('none'|'standard')
LOG_HANDLER_LEVEL = 'standard'


# Enfore UID conformance
#   * If True then UIDs will be checked to ensure they're conformant to the
#     DICOM Standard and if not then an appropriate response sent.
#   * If False then UIDs will only be checked to ensure they're no longer
#     then 64 characters and if not then an appropriate response sent.
# Usage:
#   from pynetdicom import _config
#   _config.ENFORCE_UID_CONFORMANCE = (True|False)
ENFORCE_UID_CONFORMANCE = False
