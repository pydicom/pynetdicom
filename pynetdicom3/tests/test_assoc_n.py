"""Association testing for DIMSE-N services"""

from io import BytesIO
import logging
import os
import select
import socket
from struct import pack
import time
import threading

import pytest

from pydicom import read_file
from pydicom.dataset import Dataset
from pydicom.uid import UID, ImplicitVRLittleEndian, ExplicitVRLittleEndian

from pynetdicom3 import AE, VerificationPresentationContexts
from pynetdicom3.association import Association
from pynetdicom3.dimse_primitives import N_GET
from pynetdicom3.dsutils import encode, decode
from pynetdicom3.pdu_primitives import (
    UserIdentityNegotiation, SOPClassExtendedNegotiation,
    SOPClassCommonExtendedNegotiation
)
from pynetdicom3.sop_class import (
    DisplaySystemSOPClass,
    VerificationSOPClass,
)
from .dummy_c_scp import DummyBaseSCP, DummyVerificationSCP
from .dummy_n_scp import (
    DummyGetSCP
)

LOGGER = logging.getLogger('pynetdicom3')
#LOGGER.setLevel(logging.CRITICAL)
LOGGER.setLevel(logging.DEBUG)


class DummyDIMSE(object):
    def __init__(self):
        self.status = None

    def send_msg(self, rsp, context_id):
        self.status = rsp.Status


class TestAssociationSendNEventReport(object):
    """Run tests on Assocation send_n_event_report."""
    def setup(self):
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

    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established
        with pytest.raises(RuntimeError):
            assoc.send_n_event_report()
        self.scp.stop()

    def test_not_implemented(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        with pytest.raises(NotImplementedError):
            assoc.send_n_event_report()
        assoc.release()
        assert assoc.is_released
        self.scp.stop()


class TestAssociationSendNGet(object):
    """Run tests on Assocation send_n_get."""
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

    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyGetSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(DisplaySystemSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established
        with pytest.raises(RuntimeError):
            assoc.send_n_get(None, None, None)
        self.scp.stop()

    def test_no_abstract_syntax_match(self):
        """Test SCU when no accepted abstract syntax"""
        self.scp = DummyGetSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(DisplaySystemSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        msg = (
            r"No accepted Presentation Context for the SOP Class "
            r"UID '1.2.840.10008.1.1'"
        )
        with pytest.raises(ValueError, match=msg):
            assoc.send_n_get(None, VerificationSOPClass.uid, None)
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_ups_abstract_syntax(self):
        """Test that sending with UPS uses correct SOP Class UID"""
        pass

    def test_rsp_none(self):
        """Test no response from peer"""
        self.scp = DummyGetSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(DisplaySystemSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        class DummyDIMSE():
            def send_msg(*args, **kwargs): return

            def receive_msg(*args, **kwargs): return None, None

        assoc.dimse = DummyDIMSE()
        assert assoc.is_established
        status, ds = assoc.send_n_get([0x7fe0,0x0010],
                                      DisplaySystemSOPClass.uid,
                                      '1.2.840.10008.5.1.1.40.1')

        assert assoc.is_aborted

        self.scp.stop()

    def test_rsp_invalid(self):
        """Test invalid DIMSE message received from peer"""
        self.scp = DummyGetSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(DisplaySystemSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)

        class DummyResponse():
            is_valid_response = False

        class DummyDIMSE():
            def send_msg(*args, **kwargs): return
            def receive_msg(*args, **kwargs): return DummyResponse(), None

        assoc.dimse = DummyDIMSE()
        assert assoc.is_established
        status, ds = assoc.send_n_get([0x7fe0,0x0010],
                                      DisplaySystemSOPClass.uid,
                                      '1.2.840.10008.5.1.1.40.1')
        assert assoc.is_aborted

        self.scp.stop()

    def test_rsp_failure(self):
        """Test receiving a failure response from the peer"""
        self.scp = DummyGetSCP()
        self.scp.status = 0x0112
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
        assert status.Status == 0x0112
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rsp_warning(self):
        """Test receiving a warning response from the peer"""
        self.scp = DummyGetSCP()
        self.scp.status = 0x0116
        self.scp.start()
        ae = AE()
        ae.add_requested_context(DisplaySystemSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get([0x7fe0,0x0010],
                                      DisplaySystemSOPClass.uid,
                                      '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0x0116
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rsp_success(self):
        """Test receiving a success response from the peer"""
        self.scp = DummyGetSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(DisplaySystemSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get([0x7fe0,0x0010],
                                      DisplaySystemSOPClass.uid,
                                      '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0x0000
        assoc.release()
        assert assoc.is_released
        self.scp.stop()

    def test_rsp_unknown_status(self):
        """Test unknown status value returned by peer"""
        self.scp = DummyGetSCP()
        self.scp.status = 0xFFF0
        self.scp.start()
        ae = AE()
        ae.add_requested_context(DisplaySystemSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get([0x7fe0,0x0010],
                                      DisplaySystemSOPClass.uid,
                                      '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0xFFF0
        assoc.release()
        assert assoc.is_released
        self.scp.stop()



class TestAssociationSendNSet(object):
    """Run tests on Assocation send_n_set."""
    def setup(self):
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

    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established
        with pytest.raises(RuntimeError):
            assoc.send_n_set()
        self.scp.stop()

    def test_not_implemented(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        with pytest.raises(NotImplementedError):
            assoc.send_n_set()
        assoc.release()
        assert assoc.is_released
        self.scp.stop()


class TestAssociationSendNAction(object):
    """Run tests on Assocation send_n_action."""
    def setup(self):
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

    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established
        with pytest.raises(RuntimeError):
            assoc.send_n_action()
        self.scp.stop()

    def test_not_implemented(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        with pytest.raises(NotImplementedError):
            assoc.send_n_action()
        assoc.release()
        assert assoc.is_released
        self.scp.stop()


class TestAssociationSendNCreate(object):
    """Run tests on Assocation send_n_create."""
    def setup(self):
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

    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established
        with pytest.raises(RuntimeError):
            assoc.send_n_create()
        self.scp.stop()

    def test_not_implemented(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        with pytest.raises(NotImplementedError):
            assoc.send_n_create()
        assoc.release()
        assert assoc.is_released
        self.scp.stop()


class TestAssociationSendNDelete(object):
    """Run tests on Assocation send_n_delete."""
    def setup(self):
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

    def test_must_be_associated(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established
        with pytest.raises(RuntimeError):
            assoc.send_n_delete()
        self.scp.stop()

    def test_not_implemented(self):
        """Test can't send without association."""
        # Test raise if assoc not established
        self.scp = DummyVerificationSCP()
        self.scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        with pytest.raises(NotImplementedError):
            assoc.send_n_delete()
        assoc.release()
        assert assoc.is_released
        self.scp.stop()
