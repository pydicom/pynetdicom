"""pynetdicom configuration options"""


# During C-STORE operations:
#   * If True, decode the request's DataSet parameter value to a pydicom
#     Dataset before passing it to ApplicationEntity.on_c_store(),
#   * If False, skip decoding and pass the raw encoded bytes to
#     ApplicationEntity.on_c_store()
# Setting the value to False has a couple of benefits:
#   * Writing received data to file is faster since the dataset
#     decoding/encoding steps are skipped
#   * A Storage SCP should also run ~15% faster as the decode is skipped
#   * Any issues with dataset decoding (bugs, non-conformance) are bypassed
# Usage:
#   from pynetdicom import _config
#   _config.DECODE_STORE_DATASETS = [True|False]
DECODE_STORE_DATASETS = True
