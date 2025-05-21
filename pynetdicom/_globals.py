"""Global variables for pynetdicom."""

from pydicom.uid import UID


# The default Maximum PDU Length (in bytes)
# Must be 0 or greater than 7.
# A value of 0 indicates unlimited maximum length
DEFAULT_MAX_LENGTH: int = 16382

# DICOM Application Context Name - see Part 7, Annex A.2.1
APPLICATION_CONTEXT_NAME: str = "1.2.840.10008.3.1.1.1"

DEFAULT_TRANSFER_SYNTAXES: list[str] = [
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

ALL_TRANSFER_SYNTAXES: list[str] = [
    "1.2.840.10008.1.2",  # Implicit VR Little Endian,
    "1.2.840.10008.1.2.1",  # Explicit VR Little Endian,
    "1.2.840.10008.1.2.1.99",  # Deflated Explicit VR Little Endian
    "1.2.840.10008.1.2.2",  # Explicit VR Big Endian,
    "1.2.840.10008.1.2.4.50",  # JPEG Baseline 8 Bit
    "1.2.840.10008.1.2.4.51",  # JPEG Extended 12 Bit
    "1.2.840.10008.1.2.4.57",  # JPEG Lossless
    "1.2.840.10008.1.2.4.70",  # JPEG Lossless SV1
    "1.2.840.10008.1.2.4.80",  # JPEG-LS Lossless
    "1.2.840.10008.1.2.4.81",  # JPEG-LS Lossy
    "1.2.840.10008.1.2.4.90",  # JPEG 2000 Lossless
    "1.2.840.10008.1.2.4.91",  # JPEG 2000
    "1.2.840.10008.1.2.4.92",  # JPEG 2000 Multi-Component Lossless
    "1.2.840.10008.1.2.4.93",  # JPEG 2000 Multi-Component
    "1.2.840.10008.1.2.4.94",  # JPIP Referenced
    "1.2.840.10008.1.2.4.95",  # JPIP Referenced Deflate
    "1.2.840.10008.1.2.4.100",  # MPEG2 Main Profile / Main Level
    "1.2.840.10008.1.2.4.100.1",  # Fragmentable MPEG2 Main Profile / Main Level
    "1.2.840.10008.1.2.4.101",  # MPEG2 Main Profile / High Level
    "1.2.840.10008.1.2.4.101.1",  # Fragmentable MPEG2 Main Profile / High Level
    "1.2.840.10008.1.2.4.102",  # MPEG-4 AVC/H.264 High Profile / Level 4.1
    "1.2.840.10008.1.2.4.102.1",  # Fragmentable MPEG-4 AVC/H.264 High Profile / Level 4.1
    "1.2.840.10008.1.2.4.103",  # MPEG-4 AVC/H.264 BD-compatible High Profile
    "1.2.840.10008.1.2.4.103.1",  # Fragmentable MPEG-4 AVC/H.264 BD-compatible High Profile
    "1.2.840.10008.1.2.4.104",  # MPEG-4 AVC/H.264 High Profile For 2D Video
    "1.2.840.10008.1.2.4.104.1",  # Fragmentable MPEG-4 AVC/H.264 High Profile For 2D Video
    "1.2.840.10008.1.2.4.105",  # MPEG-4 AVC/H.264 High Profile For 3D Video
    "1.2.840.10008.1.2.4.105.1",  # Fragmentable MPEG-4 AVC/H.264 High Profile For 3D Video
    "1.2.840.10008.1.2.4.106",  # MPEG-4 AVC/H.264 Stereo High Profile
    "1.2.840.10008.1.2.4.106.1",  # Fragmentable MPEG-4 AVC/H.264 Stereo High Profile
    "1.2.840.10008.1.2.4.107",  # HEVC/H.265 Main Profile / Level 5.1
    "1.2.840.10008.1.2.4.108",  # HEVC/H.265 Main 10 Profile / Level 5.1
    "1.2.840.10008.1.2.4.110",  # JPEG XL Lossless
    "1.2.840.10008.1.2.4.111",  # JPEG XL JPEG Recompression
    "1.2.840.10008.1.2.4.112",  # JPEG XL
    "1.2.840.10008.1.2.4.201",  # High-Throughput JPEG 2000 Lossless
    "1.2.840.10008.1.2.4.202",  # High-Throughput JPEG 2000 RPCL
    "1.2.840.10008.1.2.4.203",  # High-Throughput JPEG 2000
    "1.2.840.10008.1.2.4.204",  # JPIP HT2K Referenced
    "1.2.840.10008.1.2.4.205",  # JPIP HTJ2k Referenced Deflate
    "1.2.840.10008.1.2.5",  # RLE Lossless
    "1.2.840.10008.1.2.7.1",  # SMPTE ST 2110-20 Uncompressed Progressive Active Video
    "1.2.840.10008.1.2.7.2",  # SMPTE ST 2110-20 Uncompressed Interlaced Active Video
    "1.2.840.10008.1.2.7.3",  # SMPTE ST 2110-30 PCM Digital Audio
    "1.2.840.10008.1.2.8.1",  # Deflated Image Frame Compression
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
* Fragmentable MPEG2 Main Profile / Main Level
* MPEG2 Main Profile / High Level
* Fragmentable MPEG2 Main Profile / High Level
* MPEG-4 AVC/H.264 High Profile / Level 4.1
* Fragmentable MPEG-4 AVC/H.264 High Profile / Level 4.1
* MPEG-4 AVC/H.264 BD-compatible High Profile
* Fragmentable MPEG-4 AVC/H.264 BD-compatible High Profile
* MPEG-4 AVC/H.264 High Profile For 2D Video
* Fragmentable MPEG-4 AVC/H.264 High Profile For 2D Video
* MPEG-4 AVC/H.264 High Profile For 3D Video
* Fragmentable MPEG-4 AVC/H.264 High Profile For 3D Video
* MPEG-4 AVC/H.264 Stereo High Profile
* Fragmentable MPEG-4 AVC/H.264 Stereo High Profile
* HEVC/H.265 Main Profile / Level 5.1
* HEVC/H.265 Main 10 Profile / Level 5.1
* JPEG XL Lossless
* JPEG XL JPEG Recompression
* JPEG XL
* High-Throughput JPEG 2000 Lossless
* High-Throughput JPEG 2000 with RPCL Lossless
* High-Throughput JPEG 2000
* JPIP HTK2K Referenced
* JPIP HTK2K Referenced Deflate
* RLE Lossless
* SMPTE ST 2110-20 Uncompressed Progressive Active Video
* SMPTE ST 2110-20 Uncompressed Interlaced Active Video
* SMPTE ST 2110-30 PCM Digital Audio
* Deflated Image Frame Compression
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


OptionalUIDType = str | bytes | UID | None
