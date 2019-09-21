"""pynetdicom configuration options"""


LOG_HANDLER_LEVEL = 'standard'
"""Default (non-user) event logging

* If ``'none'`` then events will not be logged at all, however there will still
  be some logging (warnings, errors, etc)
* If ``'standard'`` then certain events will be logged (association
  negotiation, DIMSE messaging, etc)

Examples
--------

>>> from pynetdicom import _config
>>> _config.LOG_HANDLER_LEVEL = 'none'
"""


ENFORCE_UID_CONFORMANCE = False
"""Enforce UID conformance

If ``True`` then UIDs will be checked to ensure they're conformant to the
DICOM Standard and if not then an appropriate response sent, otherwise
UIDs will only be checked to ensure they're no longer then 64 characters and
if not then an appropriate response sent.

Examples
--------

>>> from pynetdicom import _config
>>> _config.ENFORCE_UID_CONFORMANCE = True
"""


USE_SHORT_DIMSE_AET = True
"""Use short AE titles in DIMSE messages.

If ``False`` then elements with a VR of AE in DIMSE messages will be padded
with trailing spaces up to the maximum allowable length (16 bytes), otherwise
they will be padded with zero or one space to the smallest possible even
length (i.e an AE title with 7 characters will be trailing padded to 8).

Examples
--------

>>> from pynetdicom import _config
>>> _config.USE_SHORT_DIMSE_AET = False
"""
