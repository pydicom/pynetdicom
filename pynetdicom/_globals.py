"""Global variables for pynetdicom."""

from typing import List, Optional, Union

from pydicom.uid import UID


# The default Maximum PDU Length (in bytes)
# Must be 0 or greater than 7.
# A value of 0 indicates unlimited maximum length
DEFAULT_MAX_LENGTH: int = 16382

# DICOM Application Context Name - see Part 7, Annex A.2.1
APPLICATION_CONTEXT_NAME: str = "1.2.840.10008.3.1.1.1"

DEFAULT_TRANSFER_SYNTAXES: List[str] = [
    "1.2.840.10008.1.2",  # Implicit VR Little Endian,
    "1.2.840.10008.1.2.1",  # Explicit VR Little Endian,
    "1.2.840.10008.1.2.1.99",  # Deflated Explicit VR Little Endian
    "1.2.840.10008.1.2.2",  # Explicit VR Big Endian,
]
"""Default transfer syntaxes used when creating presentation contexts.

* Implicit VR Little Endian
* Explicit VR Little Endian
* Deflated Explicit VR Little Endian
* Explicit VR Big Endian (retired)
"""

ALL_TRANSFER_SYNTAXES: List[str] = [
    "1.2.840.10008.1.2",  # Implicit VR Little Endian,
    "1.2.840.10008.1.2.1",  # Explicit VR Little Endian,
    "1.2.840.10008.1.2.1.99",  # Deflated Explicit VR Little Endian
    "1.2.840.10008.1.2.2",  # Explicit VR Big Endian,
    "1.2.840.10008.1.2.4.50",  # JPEG Baseline
    "1.2.840.10008.1.2.4.51",  # JPEG Extended
    "1.2.840.10008.1.2.4.57",  # JPEG Lossless P14
    "1.2.840.10008.1.2.4.70",  # JPEG Lossless
    "1.2.840.10008.1.2.4.80",  # JPEG-LS Lossless
    "1.2.840.10008.1.2.4.81",  # JPEG-LS Lossy
    "1.2.840.10008.1.2.4.90",  # JPEG 2000 Lossless
    "1.2.840.10008.1.2.4.91",  # JPEG 2000
    "1.2.840.10008.1.2.4.92",  # JPEG 2000 Multi-Component Lossless
    "1.2.840.10008.1.2.4.93",  # JPEG 2000 Multi-Component
    "1.2.840.10008.1.2.4.94",  # JPIP Referenced
    "1.2.840.10008.1.2.4.95",  # JPIP Referenced Deflate
    "1.2.840.10008.1.2.4.100",  # MPEG2 Main Profile / Main Level
    "1.2.840.10008.1.2.4.101",  # MPEG2 Main Profile / High Level
    "1.2.840.10008.1.2.4.102",  # MPEG-4 AVC/H.264 High Profile / Level 4.1
    "1.2.840.10008.1.2.4.103",  # MPEG-4 AVC/H.264 BD-compatible High Profile
    "1.2.840.10008.1.2.4.104",  # MPEG-4 AVC/H.264 High Profile For 2D Video
    "1.2.840.10008.1.2.4.105",  # MPEG-4 AVC/H.264 High Profile For 3D Video
    "1.2.840.10008.1.2.4.106",  # MPEG-4 AVC/H.264 Stereo High Profile
    "1.2.840.10008.1.2.4.107",  # HEVC/H.265 Main Profile / Level 5.1
    "1.2.840.10008.1.2.4.108",  # HEVC/H.265 Main 10 Profile / Level 5.1
    "1.2.840.10008.1.2.5",  # RLE Lossless
]
"""All current transfer syntaxes and explicit VR big endian.

* Implicit VR Little Endian
* Explicit VR Little Endian
* Deflated Explicit VR Little Endian
* Explicit VR Big Endian (retired)
* JPEG Baseline (Process 1)
* JPEG Extended (Process 2 & 4)
* JPEG Lossless (Process 14)
* JPEG Lossless (Process 14, Selection Value 1)
* JPEG-LS Lossless
* JPEG-LS Lossy
* JPEG 2000 Lossless
* JPEG 2000
* JPEG 2000 Multi-component Lossless
* JPEG 2000 Multi-component
* JPIP Referenced
* JPIP Referenced Deflate
* MPEG2 Main Profile / Main Level
* MPEG2 Main Profile / High Level
* MPEG-4 AVC/H.264 High Profile / Level 4.1
* MPEG-4 AVC/H.264 BD-compatible High Profile
* MPEG-4 AVC/H.264 High Profile For 2D Video
* MPEG-4 AVC/H.264 High Profile For 3D Video
* MPEG-4 AVC/H.264 Stereo High Profile
* HEVC/H.265 Main Profile / Level 5.1
* HEVC/H.265 Main 10 Profile / Level 5.1
* RLE Lossless
"""

# The association operation modes
MODE_ACCEPTOR: str = "acceptor"
MODE_REQUESTOR: str = "requestor"

# Status categories
STATUS_SUCCESS: str = "Success"
STATUS_FAILURE: str = "Failure"
STATUS_WARNING: str = "Warning"
STATUS_CANCEL: str = "Cancel"
STATUS_PENDING: str = "Pending"
STATUS_UNKNOWN: str = "Unknown"


# The default address that client sockets are bound to
BIND_ADDRESS = ("127.0.0.1", 0)


OptionalUIDType = Optional[Union[str, bytes, UID]]
