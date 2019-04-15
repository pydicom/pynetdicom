"""pynetdicom configuration options"""


# Default (non-user) event logging
#   * If 'none' then events will not be logged at all, however there will still
#     be some logging (warnings, errors, etc)
#   * If 'standard' then certain events will be logged (association
#     negotiation, DIMSE messaging, etc)
# Usage:
#   from pynetdicom import _config
#   _config.LOG_HANDLER_LEVEL = ('none'|'standard')
LOG_HANDLER_LEVEL = 'standard'


# Enforce UID conformance
#   * If True then UIDs will be checked to ensure they're conformant to the
#     DICOM Standard and if not then an appropriate response sent.
#   * If False then UIDs will only be checked to ensure they're no longer
#     then 64 characters and if not then an appropriate response sent.
# Usage:
#   from pynetdicom import _config
#   _config.ENFORCE_UID_CONFORMANCE = (True|False)
ENFORCE_UID_CONFORMANCE = False
