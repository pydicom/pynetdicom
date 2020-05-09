"""Default configuration file for qrscp.py"""


# Our listen port
PORT = 11112
# Our AE title
AE_TITLE = b'QRSCP'
# Our maximum PDU size; 0 for unlimited
MAX_PDU = 16382

# Directory where SOP Instances received from Storage SCUs will be stored
#   This directory contains the QR service's the managed SOP Instances
INSTANCE_LOCATION = 'instances'
# Location of sqlite3 database for the QR service's managed SOP Instances
DATABASE_LOCATION = 'instances.sqlite'

# Known C-MOVE Move Destinations
#   Storage SCPs must be added here before they can be used by a Move SCU
MOVE_DESTINATIONS = {
    # {bytes AE title : (str address, int port)}
    b'STORESCP' : ('127.0.0.1', 104),
}

## Logging options
# Log C-FIND, C-GET and C-MOVE Identifier datasets
LOG_IDENTIFIERS = True
