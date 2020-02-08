"""Unit tests for qrscp.py QR get service."""

import logging
import os
import subprocess
import sys
import time

import pytest

from pydicom import dcmread
from pydicom.uid import (
    ExplicitVRLittleEndian, ImplicitVRLittleEndian,
    DeflatedExplicitVRLittleEndian, ExplicitVRBigEndian
)

from pynetdicom import AE, evt, debug_logger, DEFAULT_TRANSFER_SYNTAXES
from pynetdicom.sop_class import VerificationSOPClass, CTImageStorage


#debug_logger()


APP_DIR = os.path.join(os.path.dirname(__file__), '../')
APP_FILE = os.path.join(APP_DIR, 'qrscp', 'qrscp.py')
DATA_DIR = os.path.join(APP_DIR, '../', 'tests', 'dicom_files')
DATASET_FILE = os.path.join(DATA_DIR, 'CTImageStorage.dcm')
