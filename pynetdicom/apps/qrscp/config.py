
from pynetdicom import (
    build_context, VerificationPresentationContexts,
    AllStoragePresentationContexts, QueryRetrievePresentationContexts,
)

from pynetdicom.sop_class import *

# Our listen port
PORT = 11112
# Our AE title
AE_TITLE = 'QRSCP'
# Our maximum PDU size; 0 for unlimited (faster but may cause issues with
#   poorly implementated SCUs)
MAX_PDU = 16382

# Directory where SOP Instances received from Storage SCUs will be stored
#   This directory contains the QR service's the managed SOP Instances
INSTANCES_LOCATION = 'instances'
# Location of sqlite3 database for the QR service's managed SOP Instances
DATABASE_LOCATION = 'instances.sqlite'

# Known C-MOVE Move Destinations
#   Storage SCPs must be added here before they can be used by a Move SCU
MOVE_DESTINATIONS = {
    # {bytes AE title : (str address, int port)}
    # Our Stoage SCP, although why would you have us send data to ourselves?
    b'QRSCP' : ('127.0.0.1', PORT),
}
