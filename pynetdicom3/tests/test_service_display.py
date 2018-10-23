"""Tests for the Display System Management Service Class."""

import logging
import os
import threading
import time

import pytest

from pydicom.dataset import Dataset

from pynetdicom3 import AE
from pynetdicom3.sop_class import (
    DisplaySystemSOPClass
)
from .dummy_c_scp import DummyBaseSCP
from .dummy_n_scp import DummyGetSCP


LOGGER = logging.getLogger('pynetdicom3')
#LOGGER.setLevel(logging.DEBUG)
LOGGER.setLevel(logging.CRITICAL)


class TestDisplayServiceClass(object):
    """Test the DisplaySystemManagementServiceClass"""
    def setup(self):
        """Run prior to each test"""
        self.scp = None

    def teardown(self):
        """Clear any active threads"""
        if self.scp:
            self.scp.abort()

        time.sleep(0.1)

        for thread in threading.enumerate():
            if isinstance(thread, DummyBaseSCP):
                thread.abort()
                thread.stop()

    def test_scp_callback_return_dataset(self):
        """Test on_n_get returning a Dataset status"""
        self.scp = DummyGetSCP()
        self.scp.status = Dataset()
        # Unknown status
        self.scp.status.Status = 0x0001
        self.scp.start()

        ae = AE()
        ae.add_requested_context(DisplaySystemSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get([(0x7fe0,0x0010)],
                                      DisplaySystemSOPClass.uid,
                                      '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0x0001
        assert ds.PatientName == 'Test'
        assoc.release()
        self.scp.stop()

    def test_scp_callback_return_dataset_multi(self):
        """Test on_n_get returning a Dataset status with other elements"""
        self.scp = DummyGetSCP()
        self.scp.status = Dataset()
        self.scp.status.Status = 0x0001
        self.scp.status.ErrorComment = 'Test'
        self.scp.status.OffendingElement = 0x00080010
        self.scp.status.ErrorID = 12
        self.scp.start()

        ae = AE()
        ae.add_requested_context(DisplaySystemSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get([(0x7fe0,0x0010)],
                                      DisplaySystemSOPClass.uid,
                                      '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0x0001
        assert status.ErrorComment == 'Test'
        assert status.ErrorID == 12
        assert 'OffendingElement' not in status
        assert ds.PatientName == 'Test'
        assoc.release()
        self.scp.stop()

    def test_scp_callback_return_int(self):
        """Test on_n_get returning an int status"""
        self.scp = DummyGetSCP()
        self.scp.status = 0x0000
        self.scp.start()

        ae = AE()
        ae.add_requested_context(DisplaySystemSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get([(0x7fe0,0x0010)],
                                      DisplaySystemSOPClass.uid,
                                      '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0x0000
        assert not 'ErrorComment' in status
        assoc.release()
        self.scp.stop()

    def test_scp_callback_return_unknown(self):
        """Test on_n_get returning a unknown status"""
        self.scp = DummyGetSCP()
        self.scp.status = 0xFFF0
        self.scp.start()

        ae = AE()
        ae.add_requested_context(DisplaySystemSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get([(0x7fe0,0x0010)],
                                      DisplaySystemSOPClass.uid,
                                      '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0xFFF0
        assert ds is None
        assoc.release()
        self.scp.stop()

    def test_scp_callback_no_status(self):
        """Test on_n_get not returning a status"""
        self.scp = DummyGetSCP()
        self.scp.status = None
        self.scp.start()

        ae = AE()
        ae.add_requested_context(DisplaySystemSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get([(0x7fe0,0x0010)],
                                      DisplaySystemSOPClass.uid,
                                      '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0xC002
        assert ds is None
        assoc.release()
        self.scp.stop()

    def test_scp_callback_exception(self):
        """Test on_n_get raising an exception"""
        self.scp = DummyGetSCP()
        def on_n_get(attr, context, assoc_info):
            raise ValueError
        self.scp.ae.on_n_get = on_n_get
        self.scp.start()

        ae = AE()
        ae.add_requested_context(DisplaySystemSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get([(0x7fe0,0x0010)],
                                      DisplaySystemSOPClass.uid,
                                      '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0x0110
        assert ds is None
        assoc.release()
        self.scp.stop()

    def test_scp_callback_context(self):
        """Test on_n_get context parameter"""
        self.scp = DummyGetSCP()
        self.scp.start()

        ae = AE()
        ae.add_requested_context(DisplaySystemSOPClass, '1.2.840.10008.1.2.1')
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get([(0x7fe0,0x0010)],
                                      DisplaySystemSOPClass.uid,
                                      '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0x0000
        assert 'PatientName' in ds
        assoc.release()
        assert assoc.is_released

        assert self.scp.context.context_id == 1
        assert self.scp.context.abstract_syntax == DisplaySystemSOPClass.UID
        assert self.scp.context.transfer_syntax == '1.2.840.10008.1.2.1'

        self.scp.stop()

    def test_scp_callback_info(self):
        """Test on_n_get caontext parameter"""
        self.scp = DummyGetSCP()
        self.scp.start()

        ae = AE()
        ae.add_requested_context(DisplaySystemSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get([(0x7fe0,0x0010)],
                                      DisplaySystemSOPClass.uid,
                                      '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0x0000
        assert 'PatientName' in ds
        assoc.release()
        assert assoc.is_released

        assert self.scp.info['requestor']['address'] == '127.0.0.1'
        assert self.scp.info['requestor']['ae_title'] == b'PYNETDICOM      '
        assert self.scp.info['requestor']['called_aet'] == b'ANY-SCP         '
        assert isinstance(self.scp.info['requestor']['port'], int)
        assert self.scp.info['acceptor']['port'] == 11112
        assert self.scp.info['acceptor']['address'] == '127.0.0.1'
        assert self.scp.info['acceptor']['ae_title'] == b'PYNETDICOM      '
        assert self.scp.info['parameters']['message_id'] == 1
        assert self.scp.info['parameters']['requested_sop_class_uid'] == DisplaySystemSOPClass.uid
        assert self.scp.info['parameters']['requested_sop_instance_uid'] == '1.2.840.10008.5.1.1.40.1'

        self.scp.stop()

    def test_scp_callback_attr(self):
        """Test on_n_get attr parameter"""
        self.scp = DummyGetSCP()
        self.scp.start()

        ae = AE()
        ae.add_requested_context(DisplaySystemSOPClass, '1.2.840.10008.1.2.1')
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get([(0x7fe0, 0x0010)],
                                      DisplaySystemSOPClass.uid,
                                      '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0x0000
        assert 'PatientName' in ds
        assoc.release()
        assert assoc.is_released

        assert self.scp.attr == [(0x7fe0, 0x0010)]

        self.scp.stop()

    def test_callback_bad_attr(self):
        """Test SCP handles a bad callback attribute list"""
        self.scp = DummyGetSCP()
        self.scp.statuses = 0x0000
        self.scp.dataset = None
        self.scp.start()

        ae = AE()
        ae.add_requested_context(DisplaySystemSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get([(0x7fe0, 0x0010)],
                                      DisplaySystemSOPClass.uid,
                                      '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0x0110
        assert ds is None

        assoc.release()
        self.scp.stop()
