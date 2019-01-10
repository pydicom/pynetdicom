
# The default Maximum PDU Length (in bytes)
# Must be 0 or greater than 7.
# A value of 0 indicates unlimited maximum length
DEFAULT_MAX_LENGTH = 16382

# DICOM Application Context Name - see Part 7, Annex A.2.1
APPLICATION_CONTEXT_NAME = '1.2.840.10008.3.1.1.1'

# The default transfer syntaxes used when creating presentation contexts
DEFAULT_TRANSFER_SYNTAXES = [
    '1.2.840.10008.1.2',  # Implicit VR Little Endian,
    '1.2.840.10008.1.2.1',  # Explicit VR Little Endian,
    '1.2.840.10008.1.2.2',  # Explicit VR Big Endian,
]

# The association operation modes
MODE_ACCEPTOR = 'acceptor'
MODE_REQUESTOR = 'requestor'

# Status categories
STATUS_SUCCESS = 'Success'
STATUS_FAILURE = 'Failure'
STATUS_WARNING = 'Warning'
STATUS_CANCEL = 'Cancel'
STATUS_PENDING = 'Pending'
STATUS_UNKNOWN = 'Unknown'
