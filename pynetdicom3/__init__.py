"""
Set module shortcuts and globals
"""
version = ['0', '1', '0']
pynetdicom_version = 'PYNETDICOM3_' + ''.join(version)

# UID prefix provided by https://www.medicalconnections.co.uk/Free_UID
pynetdicom_uid_prefix = '1.2.826.0.1.3680043.9.3811.' + '.'.join(version)

import logging

from pynetdicom3.applicationentity import ApplicationEntity as AE
from pynetdicom3.association import Association
from pynetdicom3.ACSEprovider import ACSEServiceProvider as ACSE
from pynetdicom3.DIMSEprovider import DIMSEServiceProvider as DIMSE
from pynetdicom3.DULprovider import DULServiceProvider as DUL
from pynetdicom3.SOPclass import STORAGE_CLASS_LIST as StorageSOPClassList
from pynetdicom3.SOPclass import QR_CLASS_LIST as QueryRetrieveSOPClassList
from pynetdicom3.SOPclass import VerificationSOPClass
