# adapted from pydicom source code

from __version__ import __version__
__version_info__ = __version__.split('.')

# some imports
from applicationentity import AE
from SOPclass import \
    VerificationSOPClass,\
    StorageSOPClass,\
    MRImageStorageSOPClass,\
    CTImageStorageSOPClass,\
    CRImageStorageSOPClass,\
    SCImageStorageSOPClass,\
    RTImageStorageSOPClass,\
    RTDoseStorageSOPClass,\
    RTStructureSetStorageSOPClass,\
    RTPlanStorageSOPClass,\
    PatientRootFindSOPClass,\
    PatientRootMoveSOPClass,\
    PatientRootGetSOPClass,\
    StudyRootFindSOPClass,\
    StudyRootMoveSOPClass,\
    StudyRootGetSOPClass,\
    PatientStudyOnlyFindSOPClass,\
    PatientStudyOnlyMoveSOPClass,\
    PatientStudyOnlyGetSOPClass,\
    ModalityWorklistInformationFindSOPClass




# Set up logging system for the whole package.  In each module, set
# logger=logging.getLogger('pynetdicom') and the same instance will be
# used by all At command line, turn on debugging for all pynetdicom
# functions with: import netdicom netdicom.debug(). Turn off debugging
# with netdicom.debug(False)
import logging


def debug(debug_on=True):
    """Turn debugging of DICOM network operations on or off.
    When debugging is on, file location and details about the elements
    read at that location are logged to the 'pynetdicom' logger using
    python's logging module.

    :param debug_on: True (default) to turn on debugging, False to turn off.
    """
    global logger, debugging
    if debug_on:
        logger.setLevel(logging.DEBUG)
        debugging = True
    else:
        logger.setLevel(logging.WARNING)
        debugging = False

logger = logging.getLogger('pynetdicom')
handler = logging.StreamHandler()
# formatter = logging.Formatter("%(asctime)s %(levelname)s:
# %(message)s", "%Y-%m-%d %H:%M") #'%(asctime)s %(levelname)s
# %(message)s'
formatter = logging.Formatter("%(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)
debug(False) # force level=WARNING, in case logging default is set differently (issue 102)
