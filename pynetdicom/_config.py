"""pynetdicom configuration options"""

from typing import Callable, Any

from pynetdicom._validators import validate_ae, validate_ui


LOG_HANDLER_LEVEL: str = "standard"
"""Default (non-user) event logging

* If ``"none"`` then events will not be logged at all, however there will still
  be some logging (warnings, errors, etc)
* If ``"standard"`` then certain events will be logged (association
  negotiation, DIMSE messaging, etc)

Default: ``"standard"``

Examples
--------

>>> from pynetdicom import _config
>>> _config.LOG_HANDLER_LEVEL = "none"
"""


ENFORCE_UID_CONFORMANCE: bool = False
"""Enforce UID conformance

If ``True`` then UIDs will be checked to ensure they're conformant to the
DICOM Standard and if not then an appropriate response sent, otherwise
UIDs will only be checked to ensure they're no longer then 64 characters and
if not then an appropriate response sent.

Default: ``False``

Examples
--------

>>> from pynetdicom import _config
>>> _config.ENFORCE_UID_CONFORMANCE = True
"""


USE_SHORT_DIMSE_AET: bool = True
"""Use short AE titles in DIMSE messages.

If ``False`` then elements with a VR of AE in DIMSE messages will be padded
with trailing spaces up to the maximum allowable length (16 bytes), otherwise
no padding will be added.

Default: ``True``

Examples
--------

>>> from pynetdicom import _config
>>> _config.USE_SHORT_DIMSE_AET = False
"""


LOG_RESPONSE_IDENTIFIERS: bool = True
"""Log incoming C-FIND, C-GET and C-MOVE response *Identifier* datasets.

If ``True`` then the *Identifier* datasets received in Pending
responses to C-FIND, C-GET and C-MOVE requests will be logged.

Default: ``True``

Examples
--------

>>> from pynetdicom import _config
>>> _config.LOG_RESPONSE_IDENTIFIERS = False
"""


LOG_REQUEST_IDENTIFIERS: bool = True
"""Log incoming C-FIND, C-GET and C-MOVE request *Identifier* datasets.

If ``True`` then the *Identifier* datasets received in
C-FIND, C-GET and C-MOVE requests will be logged.

Default: ``True``

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

Default: ``False``

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

Default: ``False``

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

Default: ``False``

Examples
--------

>>> from pynetdicom import _config
>>> _config.PASS_CONTEXTVARS = True
"""


WINDOWS_TIMER_RESOLUTION: float | None = 1
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


CODECS: tuple[str, ...] = ("ascii",)
"""Customise the codecs used to decode text values.

.. versionadded:: 2.0

.. warning::

    The DICOM Standard specifies ISO 646 (ASCII) as the only valid codec for
    encoded strings. The use of additional fallback codecs may result in
    unexpected behaviour in *pynetdicom*.

    When string values are encoded by *pynetdicom* only ASCII is used.


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
will be attempted in the order that the codecs appear in ``CODECS`` and any
fallback codecs should be added after ``"ascii"``.

If a fallback successfully decodes an encoded value the string will be
converted to ASCII  using :meth:`str.encode` with the `errors` parameter set
to ``"ignore"``.

Default: ``("ascii",)``

Examples
--------

Add UTF-8 as a fallback codec:

>>> from pynetdicom import _config
>>> _config.CODECS = ("ascii", "utf-8")
"""


VALIDATORS: dict[str, Callable[[Any], tuple[bool, str]]] = {
    "AE": validate_ae,
    "UI": validate_ui,
}
"""Customise the validation performed on DIMSE elements and PDU parameters.

.. versionadded:: 2.0

**AE**
    Function signature: ``def func(value: str) -> tuple[bool, str]``

    Where `value` is the AE title to be validated as a :class:`str`.

    The function should return a :class:`tuple` of (:class:`bool`,
    :class:`str`) as the ``(result, msg)``. If the `result` is ``True``
    then `msg` is ignored, otherwise `msg` will be used to provide feedback
    about why validation has failed.

**UI**
  Function signature: ``def func(value: pydicom.uid.UID) -> tuple[bool, str]``

  Where `value` is the :class:`~pydicom.uid.UID` to be validated.

  The function should return a :class:`tuple` of (:class:`bool`,
  :class:`str`) as the ``(result, msg)``. If the `result` is ``True``
  then `msg` is ignored, otherwise `msg` will be used to provide feedback
  about why validation has failed.

The default validation functions can be found :gh:`here
<pynetdicom/blob/master/pynetdicom/_validators.py>`
.

Examples
--------

Perform no validation of **AE** DIMSE elements and AE title PDU parameters:

>>> from pynetdicom import _config
>>> def my_validator(value): return (True, "")
...
>>> _config.VALIDATORS['AE'] = my_validator
"""


UNRESTRICTED_STORAGE_SERVICE: bool = False
"""When acting as an SCP assume all presentation contexts with private or
unknown public abstract syntaxes belong to the storage service and accept all
storage service requests.

.. versionadded:: 2.0

When ``True`` it's no longer necessary to define any supported
presentation contexts from the storage service and any that have been added
will be ignored, however the supported contexts for other services will still
need to be specified.

This also applies to the Storage SCP used when making C-GET requests, however
the usual requested presentation contexts and :ref:`SCP/SCU Role Selection
items <user_presentation_role>` are still required.

Default: ``False``

Examples
--------

Always accept storage requests and treat unknown presentation contexts as
part of the storage service.

>>> from pynetdicom import _config
>>> _config.UNRESTRICTED_STORAGE_SERVICE = True
"""
