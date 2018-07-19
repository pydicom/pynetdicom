"""Tests for the VerificationServiceClass."""

import logging
import threading
import time

import pytest

from pydicom.dataset import Dataset

from pynetdicom3 import AE
from pynetdicom3.sop_class import (
    VerificationServiceClass,
    VerificationSOPClass
)
from .dummy_c_scp import (
    DummyBaseSCP,
    DummyVerificationSCP,
)

LOGGER = logging.getLogger('pynetdicom3')
#LOGGER.setLevel(logging.DEBUG)
LOGGER.setLevel(logging.CRITICAL)


class TestVerificationServiceClass(object):
    """Test the VerifictionSOPClass"""
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
        """Test on_c_echo returning a Dataset status"""
        self.scp = DummyVerificationSCP()
        self.scp.status = Dataset()
        self.scp.status.Status = 0x0001
        self.scp.start()

        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_echo()
        assert rsp.Status == 0x0001
        assoc.release()
        self.scp.stop()

    def test_scp_callback_return_dataset_no_status(self):
        """Test on_c_echo returning a Dataset with no Status elem"""
        self.scp = DummyVerificationSCP()
        self.scp.status = Dataset()
        self.scp.start()

        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_echo()
        assert rsp.Status == 0x0000
        assoc.release()
        self.scp.stop()

    def test_scp_callback_return_dataset_multi(self):
        """Test on_c_echo returning a Dataset status with other elements"""
        self.scp = DummyVerificationSCP()
        self.scp.status = Dataset()
        self.scp.status.Status = 0x0001
        self.scp.status.ErrorComment = 'Test'
        self.scp.start()

        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_echo()
        assert rsp.Status == 0x0001
        assert rsp.ErrorComment == 'Test'
        assoc.release()
        self.scp.stop()

    def test_scp_callback_return_dataset_unknown(self):
        """Test a status ds with an unknown element."""
        self.scp = DummyVerificationSCP()
        self.scp.status = Dataset()
        self.scp.status.Status = 0x0001
        self.scp.status.PatientName = 'test name'
        self.scp.start()

        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_echo()
        assert rsp.Status == 0x0001
        assoc.release()
        self.scp.stop()

    def test_scp_callback_return_int(self):
        """Test on_c_echo returning an int status"""
        self.scp = DummyVerificationSCP()
        self.scp.status = 0x0002
        self.scp.start()

        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_echo()
        assert rsp.Status == 0x0002
        assert not 'ErrorComment' in rsp
        assoc.release()
        self.scp.stop()

    def test_scp_callback_return_valid(self):
        """Test on_c_echo returning a valid status"""
        self.scp = DummyVerificationSCP()
        self.scp.status = 0x0000
        self.scp.start()

        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_echo()
        assert rsp.Status == 0x0000
        assoc.release()
        self.scp.stop()

    def test_scp_callback_no_status(self):
        """Test on_c_echo not returning a status"""
        self.scp = DummyVerificationSCP()
        self.scp.status = None
        self.scp.start()

        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_echo()
        assert rsp.Status == 0x0000
        assoc.release()
        self.scp.stop()

    def test_scp_callback_exception(self):
        """Test on_c_echo raising an exception"""
        self.scp = DummyVerificationSCP()
        def on_c_echo(context, info):
            raise ValueError
        self.scp.ae.on_c_echo = on_c_echo
        self.scp.start()

        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_echo()
        assert rsp.Status == 0x0000
        assoc.release()
        self.scp.stop()

    def test_scp_callback_context(self):
        """Test on_c_echo context parameter."""
        self.scp = DummyVerificationSCP()
        self.scp.start()

        ae = AE()
        ae.add_requested_context(VerificationSOPClass, '1.2.840.10008.1.2.1')
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_echo()
        assert rsp.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        assert self.scp.context.context_id == 1
        assert self.scp.context.abstract_syntax == '1.2.840.10008.1.1'
        assert self.scp.context.transfer_syntax == '1.2.840.10008.1.2.1'

        self.scp.stop()

    def test_scp_callback_info(self):
        """Test on_c_echo info parameter."""
        self.scp = DummyVerificationSCP()
        self.scp.start()

        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_echo()
        assert rsp.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        assert self.scp.info['requestor']['address'] == '127.0.0.1'
        assert self.scp.info['requestor']['ae_title'] == b'PYNETDICOM      '
        assert self.scp.info['requestor']['called_aet'] == b'ANY-SCP         '
        assert isinstance(self.scp.info['requestor']['port'], int)
        assert self.scp.info['acceptor']['port'] == 11112
        assert self.scp.info['acceptor']['address'] == '127.0.0.1'
        assert self.scp.info['acceptor']['ae_title'] == b'PYNETDICOM      '

        self.scp.stop()
