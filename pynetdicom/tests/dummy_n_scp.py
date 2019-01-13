"""Dummy DIMSE-C SCPs for use in unit tests"""

import logging
import os
import socket
import time
import threading

from pydicom import read_file
from pydicom.dataset import Dataset
from pydicom.uid import UID, ImplicitVRLittleEndian

from pynetdicom import AE, VerificationPresentationContexts
from pynetdicom.sop_class import (
    DisplaySystemSOPClass,
    VerificationSOPClass,
    PrintJobSOPClass,
)
from pynetdicom.status import code_to_category
from .dummy_c_scp import DummyBaseSCP


LOGGER = logging.getLogger('pynetdicom')
LOGGER.setLevel(logging.CRITICAL)
#LOGGER.setLevel(logging.DEBUG)


class DummyEventReportSCP(DummyBaseSCP):
    """A threaded dummy event report SCP used for testing"""
    def __init__(self, port=11112):
        self.ae = AE()
        self.port = port
        self.ae.add_supported_context(PrintJobSOPClass)
        self.ae.add_supported_context(VerificationSOPClass)
        DummyBaseSCP.__init__(self)
        self.status = 0x0000
        ds = Dataset()
        ds.PatientName = 'Test'
        ds.SOPClassUID = PrintJobSOPClass
        ds.SOPInstanceUID = '1.2.3.4'
        self.dataset = ds

    def on_n_event_report(self, event_info, context, info):
        """Callback for ae.on_n_event_report"""

        self.context = context
        self.info = info
        self.event_info = event_info
        time.sleep(self.delay)

        return self.status, self.dataset


class DummyGetSCP(DummyBaseSCP):
    """A threaded dummy get SCP used for testing"""
    def __init__(self, port=11112):
        self.ae = AE()
        self.port = port
        self.ae.add_supported_context(DisplaySystemSOPClass)
        self.ae.add_supported_context(VerificationSOPClass)
        DummyBaseSCP.__init__(self)
        self.status = 0x0000
        ds = Dataset()
        ds.PatientName = 'Test'
        ds.SOPClassUID = DisplaySystemSOPClass
        ds.SOPInstanceUID = '1.2.3.4'
        self.dataset = ds

    def on_n_get(self, attr, context, info):
        """Callback for ae.on_n_get"""

        self.context = context
        self.info = info
        self.attr = attr
        time.sleep(self.delay)

        return self.status, self.dataset


class DummySetSCP(DummyBaseSCP):
    """A threaded dummy get SCP used for testing"""
    def __init__(self, port=11112):
        self.ae = AE()
        self.port = port
        self.ae.add_supported_context(PrintJobSOPClass)
        self.ae.add_supported_context(VerificationSOPClass)
        DummyBaseSCP.__init__(self)
        self.status = 0x0000
        ds = Dataset()
        ds.PatientName = 'Test'
        ds.SOPClassUID = PrintJobSOPClass
        ds.SOPInstanceUID = '1.2.3.4'
        self.dataset = ds

    def on_n_set(self, ds, context, info):
        """Callback for ae.on_n_get"""

        self.context = context
        self.info = info
        time.sleep(self.delay)

        return self.status, self.dataset


class DummyActionSCP(DummyBaseSCP):
    """A threaded dummy get SCP used for testing"""
    def __init__(self, port=11112):
        self.ae = AE()
        self.port = port
        self.ae.add_supported_context(PrintJobSOPClass)
        self.ae.add_supported_context(VerificationSOPClass)
        DummyBaseSCP.__init__(self)
        self.status = 0x0000
        ds = Dataset()
        ds.PatientName = 'Test'
        ds.SOPClassUID = PrintJobSOPClass
        ds.SOPInstanceUID = '1.2.3.4'
        self.dataset = ds

    def on_n_action(self, ds, context, info):
        """Callback for ae.on_n_action"""

        self.context = context
        self.info = info
        time.sleep(self.delay)

        return self.status, self.dataset


class DummyCreateSCP(DummyBaseSCP):
    """A threaded dummy get SCP used for testing"""
    def __init__(self, port=11112):
        self.ae = AE()
        self.port = port
        self.ae.add_supported_context(PrintJobSOPClass)
        self.ae.add_supported_context(VerificationSOPClass)
        DummyBaseSCP.__init__(self)
        self.status = 0x0000
        ds = Dataset()
        ds.PatientName = 'Test'
        ds.SOPClassUID = PrintJobSOPClass
        ds.SOPInstanceUID = '1.2.3.4'
        self.dataset = ds

    def on_n_create(self, ds, context, info):
        """Callback for ae.on_n_create"""
        self.context = context
        self.info = info
        self.ds = ds
        time.sleep(self.delay)

        return self.status, self.dataset


class DummyDeleteSCP(DummyBaseSCP):
    """A threaded dummy delete SCP used for testing"""
    def __init__(self, port=11112):
        self.ae = AE()
        self.port = port
        # Print Job SOP Class
        self.ae.add_supported_context(PrintJobSOPClass)
        self.ae.add_supported_context(VerificationSOPClass)
        DummyBaseSCP.__init__(self)
        self.status = 0x0000

    def on_n_delete(self, context, info):
        """Callback for ae.on_n_delete"""
        self.context = context
        self.info = info
        time.sleep(self.delay)

        return self.status
