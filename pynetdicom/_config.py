"""pynetdicom configuration options"""

from typing import Optional, Tuple


LOG_HANDLER_LEVEL: str = 'standard'
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


ENFORCE_UID_CONFORMANCE: bool = False
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


USE_SHORT_DIMSE_AET: bool = True
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


ALLOW_LONG_DIMSE_AET: bool = False
"""Allow the use of non-conformant AE titles.

.. versionadded:: 2.0

If ``False`` then elements with a VR of AE in DIMSE messages will have their
length checked to ensure conformance, otherwise no length check will be
performed.

Examples
--------

>>> from pynetdicom import _config
>>> _config.ALL_LONG_AET = True
"""


LOG_RESPONSE_IDENTIFIERS: bool = True
"""Log incoming C-FIND, C-GET and C-MOVE response *Identifier* datasets.

.. versionadded:: 1.5

If ``True`` (default) then the *Identifier* datasets received in Pending
responses to C-FIND, C-GET and C-MOVE requests will be logged.

Examples
--------

>>> from pynetdicom import _config
>>> _config.LOG_RESPONSE_IDENTIFIERS = False
"""


LOG_REQUEST_IDENTIFIERS: bool = True
"""Log incoming C-FIND, C-GET and C-MOVE request *Identifier* datasets.

.. versionadded:: 1.5

If ``True`` (default) then the *Identifier* datasets received in
C-FIND, C-GET and C-MOVE requests will be logged.

Examples
--------

>>> from pynetdicom import _config
>>> _config.LOG_REQUEST_IDENTIFIERS = False
"""


STORE_SEND_CHUNKED_DATASET: bool = False
"""Chunk a dataset file when sending it to minimise memory usage.

.. versionadded:: 2.0

If ``True``, then when using
:meth:`~pynetdicom.association.Association.send_c_store` with a file path to
a DICOM dataset, don't decode the dataset and instead send the raw encoded
data (without the File Meta Information) in chunks of no larger than
maximum PDU size allowed by the peer. This should minimise the amount of
memory required when:

* Sending large datasets
* Sending many datasets concurrently

As it's not possible to change the dataset encoding without loading it into
memory, an exact matching accepted presentation context will be required.

Default: ``False``.

Examples
--------

>>> from pynetdicom import _config
>>> _config.STORE_SEND_CHUNKED_DATASET = True
"""

STORE_RECV_CHUNKED_DATASET: bool = False
"""Chunk a dataset file when receiving it to minimise memory usage.

.. versionadded:: 2.0

If ``True``, then when receiving C-STORE requests as an SCP, don't decode
the dataset and instead write the raw data to a temporary file in the DICOM
File Format. The path to the dataset is available to the ``evt.EVT_C_STORE``
handler using the  :attr:`Event.dataset_path
<pynetdicom.events.Event.dataset_path>` attribute. This should minimise the
amount of memory required when:

* Receiving large datasets
* Receiving many datasets concurrently

Default: ``False``.

Examples
--------

>>> from pynetdicom import _config
>>> _config.STORE_RECV_CHUNKED_DATASET = True
"""

PASS_CONTEXTVARS: bool = False
"""Pass context-local state to concurrent pynetdicom code.

.. versionadded:: 2.0

If ``True``, then any ``contextvars.ContextVar`` instances defined in the
calling context will be made available to pynetdicom's concurrent contexts.
This allows the caller to define contextual behavior without modifying
pynetdicom. For example, one could add a logging filter to the pynetdicom
logger that references an externally defined ``contextvars.ContextVar``.

Default: ``False``.

Examples
--------

>>> from pynetdicom import _config
>>> _config.PASS_CONTEXTVARS = True
"""


WINDOWS_TIMER_RESOLUTION: Optional[float] = 1
"""Set the minimum timer resolution for Microsoft Windows.

.. versionadded:: 2.0

When running on Windows, the default minimum timer resolution is around 15
milliseconds, however by default *pynetdicom* runs with a resolution of 1
millisecond. This means that *pynetdicom* running on Windows may be much slower
than expected. To counteract this, *pynetdicom* uses the :mod:`ctypes` module
to set the timer resolution to ``WINDOWS_TIMER_RESOLUTION`` while the
:class:`~pynetdicom.association.Association` is active.

If ``WINDOWS_TIMER_RESOLUTION`` is set to ``None`` then no changes to the
timer resolution will be made.

Default: ``1`` (in milliseconds)

Examples
--------

>>> from pynetdicom import _config
>>> _config.WINDOWS_TIMER_RESOLUTION = 5
"""


PDU_CODECS: Tuple[str, ...] = ('ascii', 'utf-8')
"""Customise the codecs used to decode text values in PDUs.

.. versionadded:: 2.0

The specified codecs will be used when decoding the following parameters:

* A-ASSOCIATE-RQ: *Called AE Title*, *Calling AE Title*

  * Application Context Item: *Application Context Name*
  * Presentation Context Items

    * Abstract Syntax Sub-item: *Abstract Syntax Name*
    * Transfer Syntax Sub-item: *Transfer Syntax Name*
  * User Information Items

    * Implementation Class UID Sub-item: *Implementation Class UID*
    * Implementation Version Name Sub-item: *Implementation Version Name*
    * SCP/SCU Role Selection Sub-item: *SOP Class UID*
    * SOP Class Extended Negotiation Sub-item: *SOP Class UID*
    * SOP Class Common Extended Negotiation Sub-item: *SOP Class UID*, *Service
      Class UID*, *Related General SOP Class UID*
* A-ASSOCIATE-AC

  * Application Context Item: *Application Context Name*
  * Presentation Context Item:

    * Transfer Syntax Sub-item: *Transfer Syntax Name*
  * User Information Items

    * Implementation Class UID Sub-item: *Implementation Class UID*
    * Implementation Version Name Sub-item: *Implementation Version Name*
    * SCP/SCU Role Selection Sub-item: *SOP Class UID*
    * SOP Class Extended Negotiation Sub-item: *SOP Class UID*

Possible codecs are given in the Python documentation `here
<https://docs.python.org/3/library/codecs.html#standard-encodings>`_. Decoding
will be attempted in the order that the codecs appear in ``PDU_CODECS``.

The default value is ``ascii`` with ``utf-8`` as a fallback. The DICOM Standard
specifies ASCII as the only valid encoding method, however non-conformant
implementations have been known to also use UTF-8.

When values are encoded by *pynetdicom* only ASCII is used.

Examples
--------

Remove UTF-8 as a fallback codec:

>>> from pynetdicom import _config
>>> _config.PDU_CODECS = ('ascii', )
"""
