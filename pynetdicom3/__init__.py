"""
Set module shortcuts and globals
"""
from pydicom.uid import UID

version = ['0', '9', '1']
__version__ = '.'.join(version)

# Encoded as SH, 16 bytes maximum
# TODO: UPPER_CASE, change to PYNETDICOM_IMPLEMENTATION_VERSION
pynetdicom_version = 'PYNETDICOM3_' + ''.join(version)
assert 1 <= len(pynetdicom_version) <= 16

# UID prefix provided by https://www.medicalconnections.co.uk/Free_UID
# Encoded as UI, 64 bytes maximum
# TODO: UPPER_CASE, change to PYNETDICOM_UID_PREFIX
pynetdicom_uid_prefix = '1.2.826.0.1.3680043.9.3811.'
# TODO: UPPER_CASE, change to PYNETDICOM_IMPLEMENTATION_UID
pynetdicom_implementation_uid = UID(pynetdicom_uid_prefix + '.'.join(version))
assert pynetdicom_implementation_uid.is_valid

import logging

from pynetdicom3.applicationentity import ApplicationEntity as AE
from pynetdicom3.association import Association
from pynetdicom3.acse import ACSEServiceProvider as ACSE
from pynetdicom3.dimse import DIMSEServiceProvider as DIMSE
from pynetdicom3.dul import DULServiceProvider as DUL
from pynetdicom3.sop_class import STORAGE_CLASS_LIST as StorageSOPClassList
from pynetdicom3.sop_class import QR_CLASS_LIST as QueryRetrieveSOPClassList
from pynetdicom3.sop_class import VerificationSOPClass
