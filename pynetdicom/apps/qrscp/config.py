
from pynetdicom import (
    build_context, VerificationPresentationContexts,
    AllStoragePresentationContexts, QueryRetrievePresentationContexts,
)

from pynetdicom.sop_class import *

PORT = 11112
AE_TITLE = 'QRSCP'
MAX_PDU = 16382

INSTANCES_LOCATION = 'instances'
DATABASE_LOCATION = 'instances.db'

KNOWN_AE = {
    # AE title : ([list of supported contexts], [list of requested contexts])
    b'ECHOSCU' : (VerificationPresentationContexts, []),
    b'FINDSCU' : None,
    b'GETSCU' : None,
    b'MOVESCU' : None,
    b'STORESCU' : (AllStoragePresentationContexts, []),
}


MOVE_DESTINATIONS = [
    # AE title : ((address, port), requested contexts)
    b'STORESCP' : (('localhost', 11113), None),
]
