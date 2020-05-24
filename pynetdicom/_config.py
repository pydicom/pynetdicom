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

.. versionadded:: 1.3

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

.. versionadded:: 1.5

If ``False`` then elements with a VR of AE in DIMSE messages will be padded
with trailing spaces up to the maximum allowable length (16 bytes), otherwise
no padding will be added.

Examples
--------

>>> from pynetdicom import _config
>>> _config.USE_SHORT_DIMSE_AET = False
"""


LOG_RESPONSE_IDENTIFIERS = True
"""Log incoming C-FIND, C-GET and C-MOVE response *Identifier* datasets.

.. versionadded:: 1.5

If ``True`` (default) then the *Identifier* datasets received in Pending
responses to C-FIND, C-GET and C-MOVE requests will be logged.

Examples
--------

>>> from pynetdicom import _config
>>> _config.LOG_RESPONSE_IDENTIFIERS = False
"""


LOG_REQUEST_IDENTIFIERS = True
"""Log incoming C-FIND, C-GET and C-MOVE request *Identifier* datasets.

.. versionadded:: 1.5

If ``True`` (default) then the *Identifier* datasets received in
C-FIND, C-GET and C-MOVE requests will be logged.

Examples
--------

>>> from pynetdicom import _config
>>> _config.LOG_REQUEST_IDENTIFIERS = False
"""
