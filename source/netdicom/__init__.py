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
    PositronEmissionTomographyImageStorageSOPClass,\
    CRImageStorageSOPClass,\
    SCImageStorageSOPClass,\
    RTImageStorageSOPClass,\
    RTDoseStorageSOPClass,\
    RTStructureSetStorageSOPClass,\
    RTPlanStorageSOPClass,\
    EnhancedSRSOPClass,\
    XRayRadiationDoseSRSOPClass,\
    DigitalXRayImageStorageForPresentationSOPClass,\
    DigitalXRayImageStorageForProcessingSOPClass,\
    DigitalMammographyXRayImageStorageForPresentationSOPClass,\
    DigitalMammographyXRayImageStorageForProcessingSOPClass,\
    DigitalIntraOralXRayImageStorageForPresentationSOPClass,\
    DigitalIntraOralXRayImageStorageForProcessingSOPClass,\
    XRayAngiographicImageStorageSOPClass,\
    EnhancedXAImageStorageSOPClass,\
    XRayRadiofluoroscopicImageStorageSOPClass,\
    EnhancedXRFImageStorageSOPClass,\
    EnhancedCTImageStorageSOPClass,\
    NMImageStorageSOPClass,\
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


# pynetdicom defines a logger with a NullHandler only.
# Client code have the responsability to configure
# this logger.
logger = logging.getLogger('netdicom')
logger.addHandler(logging.NullHandler())

# helper functions to configure the logger. This should be
# called by the client code.


def logger_setup():
    logger = logging.getLogger('netdicom')
    handler = logging.StreamHandler()
    logger.setLevel(logging.WARNING)
    formatter = logging.Formatter("%(name)s %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    # logging.getLogger('netdicom.FSM').setLevel(logging.CRITICAL)
    logging.getLogger('netdicom.DUL').setLevel(logging.CRITICAL)


def debug(debug_on=True):
    """Turn debugging of DICOM network operations on or off."""
    logger = logging.getLogger('netdicom')
    logger.setLevel(logging.DEBUG)
