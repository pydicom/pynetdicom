"""Tests for the ae module."""

import logging
import os
import signal
import threading
import time

import pytest

from pydicom import read_file
from pydicom.dataset import Dataset
from pydicom.uid import UID, ImplicitVRLittleEndian

from .dummy_c_scp import (DummyVerificationSCP, DummyStorageSCP,
                          DummyFindSCP, DummyGetSCP, DummyMoveSCP,
                          DummyBaseSCP)
from pynetdicom3 import (
    AE,
    DEFAULT_TRANSFER_SYNTAXES,
    StoragePresentationContexts,
    VerificationPresentationContexts,
    PYNETDICOM_IMPLEMENTATION_UID,
    PYNETDICOM_IMPLEMENTATION_VERSION
)
from pynetdicom3.presentation import build_context
from pynetdicom3.sop_class import (
    RTImageStorage,
    VerificationSOPClass,
    PatientRootQueryRetrieveInformationModelFind,
    PatientRootQueryRetrieveInformationModelGet,
    PatientRootQueryRetrieveInformationModelMove
)


LOGGER = logging.getLogger('pynetdicom3')
LOGGER.setLevel(logging.DEBUG)
#LOGGER.setLevel(logging.CRITICAL)

TEST_DS_DIR = os.path.join(os.path.dirname(__file__), 'dicom_files')
DATASET = read_file(os.path.join(TEST_DS_DIR, 'RTImageStorage.dcm'))
COMP_DATASET = read_file(os.path.join(TEST_DS_DIR, 'MRImageStorage_JPG2000_Lossless.dcm'))


class TestAEVerificationSCP(object):
    """Check verification SCP"""
    def setup(self):
        """Run prior to each test"""
        self.scp = None

    def teardown(self):
        """Clear any active threads"""
        if self.scp:
            self.scp.abort()

        time.sleep(0.1)

        for thread in threading.enumerate():
            if isinstance(thread, (AE, DummyBaseSCP)):
                thread.abort()
                thread.stop()

    # Causing thread exiting issues
    #@pytest.mark.skip('Causes threading issues')
    def test_stop_scp_keyboard(self):
        """Test stopping the SCP with keyboard"""
        self.scp = DummyVerificationSCP()
        self.scp.start()

        def test():
            raise KeyboardInterrupt

        # This causes thread stopping issues
        pytest.raises(KeyboardInterrupt, test)

        self.scp.stop()

    def test_no_supported_contexts(self):
        """Test starting with no contexts raises"""
        """Test stopping the SCP with keyboard"""
        self.scp = DummyVerificationSCP()
        self.scp.start()

        ae = AE()
        with pytest.raises(ValueError):
            ae.start()

        self.scp.stop()

    def test_str_empty(self):
        """Test str output for default AE"""
        ae = AE()
        ae.__str__()


class TestAEPresentationSCU(object):
    """Tests for AE presentation contexts when running as an SCU"""
    def setup(self):
        """Run prior to each test"""
        self.scp = None

    def teardown(self):
        """Clear any active threads"""
        if self.scp:
            self.scp.abort()

        time.sleep(0.1)

        for thread in threading.enumerate():
            if isinstance(thread, (AE, DummyBaseSCP)):
                thread.abort()
                thread.stop()

    def test_associate_context(self):
        """Test that AE.associate doesn't modify the supplied contexts"""
        self.scp = DummyVerificationSCP()
        self.scp.start()

        # Test AE.requested_contexts
        ae = AE()
        ae.requested_contexts = VerificationPresentationContexts
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        assert ae.requested_contexts[0].context_id is None
        assert len(assoc.requested_contexts) == 1
        assert assoc.requested_contexts[0].abstract_syntax == '1.2.840.10008.1.1'
        assert assoc.requested_contexts[0].context_id == 1
        assoc.release()
        assert not assoc.is_established
        assert assoc.is_released

        # Test associate(contexts=...)
        ae.requested_contexts = []
        assoc = ae.associate('localhost', 11112, contexts=VerificationPresentationContexts)
        assert assoc.is_established

        assert VerificationPresentationContexts[0].context_id is None
        assert len(assoc.requested_contexts) == 1
        assert assoc.requested_contexts[0].abstract_syntax == '1.2.840.10008.1.1'
        assert assoc.requested_contexts[0].context_id == 1
        assoc.release()
        assert not assoc.is_established
        assert assoc.is_released

        self.scp.stop()

    def test_associate_context_raises(self):
        """Test that AE.associate raises exception if no requested contexts"""
        ae = AE()
        with pytest.raises(RuntimeError):
            assoc = ae.associate('localhost', 11112)


class TestAEGoodCallbacks(object):
    def setup(self):
        """Run prior to each test"""
        self.scp = None

    def teardown(self):
        """Clear any active threads"""
        if self.scp:
            self.scp.abort()

        time.sleep(0.1)

        for thread in threading.enumerate():
            if isinstance(thread, (AE, DummyBaseSCP)):
                thread.abort()
                thread.stop()

    def test_on_c_echo_called(self):
        """ Check that SCP AE.on_c_echo() was called """
        self.scp = DummyVerificationSCP()
        self.scp.start()

        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status = assoc.send_c_echo()
        assert isinstance(status, Dataset)
        assert 'Status' in status
        assert status.Status == 0x0000

        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established

        self.scp.stop()

    def test_on_c_store_called(self):
        """ Check that SCP AE.on_c_store(dataset) was called """
        self.scp = DummyStorageSCP()
        self.scp.start()

        ae = AE()
        ae.add_requested_context(RTImageStorage)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status = assoc.send_c_store(DATASET)
        assert isinstance(status, Dataset)
        assert 'Status' in status
        assert status.Status == 0x0000

        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established

        self.scp.stop()

    def test_on_c_find_called(self):
        """ Check that SCP AE.on_c_find(dataset) was called """
        self.scp = DummyFindSCP()
        self.scp.status = 0x0000
        self.scp.start()

        ds = Dataset()
        ds.PatientName = '*'
        ds.QueryRetrieveLevel = "PATIENT"
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        for (status, ds) in assoc.send_c_find(ds, query_model='P'):
            assert status.Status == 0x0000
        assoc.release()

        self.scp.stop()

    def test_on_c_get_called(self):
        """ Check that SCP AE.on_c_get(dataset) was called """
        self.scp = DummyGetSCP()
        self.scp.start()

        ds = Dataset()
        ds.PatientName = '*'
        ds.QueryRetrieveLevel = "PATIENT"
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        for (status, ds) in assoc.send_c_get(ds, query_model='P'):
            assert status.Status == 0x0000
        assoc.release()

        self.scp.stop()

    def test_on_c_move_called(self):
        """ Check that SCP AE.on_c_move(dataset) was called """
        self.scp = DummyMoveSCP()
        self.scp.start()

        ds = Dataset()
        ds.PatientName = '*'
        ds.QueryRetrieveLevel = "PATIENT"
        ae = AE()
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        for (status, ds) in assoc.send_c_move(ds, query_model='P', move_aet=b'TEST'):
            pass
        assoc.release()

        self.scp.stop()

    def test_on_user_identity_negotiation(self):
        """Test default callback raises exception"""
        ae = AE()
        with pytest.raises(NotImplementedError):
            ae.on_user_identity_negotiation(None, None, None)

    def test_on_c_echo(self):
        """Test default callback raises exception"""
        ae = AE()
        ae.on_c_echo(None, None)

    def test_on_c_store(self):
        """Test default callback raises exception"""
        ae = AE()
        with pytest.raises(NotImplementedError):
            ae.on_c_store(None, None, None)

    def test_on_c_find(self):
        """Test default callback raises exception"""
        ae = AE()
        with pytest.raises(NotImplementedError):
            ae.on_c_find(None, None, None)

    def test_on_c_find_cancel(self):
        """Test default callback raises exception"""
        ae = AE()
        with pytest.raises(NotImplementedError):
            ae.on_c_find_cancel()

    def test_on_c_get(self):
        """Test default callback raises exception"""
        ae = AE()
        with pytest.raises(NotImplementedError):
            ae.on_c_get(None, None, None)

    def test_on_c_get_cancel(self):
        """Test default callback raises exception"""
        ae = AE()
        with pytest.raises(NotImplementedError):
            ae.on_c_get_cancel()

    def test_on_c_move(self):
        """Test default callback raises exception"""
        ae = AE()
        with pytest.raises(NotImplementedError):
            ae.on_c_move(None, None, None, None)

    def test_on_c_move_cancel(self):
        """Test default callback raises exception"""
        ae = AE()
        with pytest.raises(NotImplementedError):
            ae.on_c_move_cancel()

    def test_on_n_event_report(self):
        """Test default callback raises exception"""
        ae = AE()
        with pytest.raises(NotImplementedError):
            ae.on_n_event_report(None, None, None)

    def test_on_n_get(self):
        """Test default callback raises exception"""
        ae = AE()
        with pytest.raises(NotImplementedError):
            ae.on_n_get(None, None, None)

    def test_on_n_set(self):
        """Test default callback raises exception"""
        ae = AE()
        with pytest.raises(NotImplementedError):
            ae.on_n_set(None, None, None)

    def test_on_n_action(self):
        """Test default callback raises exception"""
        ae = AE()
        with pytest.raises(NotImplementedError):
            ae.on_n_action(None, None, None)

    def test_on_n_create(self):
        """Test default callback raises exception"""
        ae = AE()
        with pytest.raises(NotImplementedError):
            ae.on_n_create(None, None, None)

    def test_on_n_delete(self):
        """Test default callback raises exception"""
        ae = AE()
        with pytest.raises(NotImplementedError):
            ae.on_n_delete(None, None)

    def test_on_receive_connection(self):
        """Test default callback raises exception"""
        ae = AE()
        with pytest.raises(NotImplementedError):
            ae.on_receive_connection()

    def test_on_make_connection(self):
        """Test default callback raises exception"""
        ae = AE()
        with pytest.raises(NotImplementedError):
            ae.on_make_connection()

    def test_association_requested(self):
        """Test default callback raises exception"""
        ae = AE()
        ae.on_association_requested(None)

    def test_association_accepted(self):
        """Test default callback raises exception"""
        ae = AE()
        ae.on_association_accepted(None)

    def test_association_rejected(self):
        """Test default callback raises exception"""
        ae = AE()
        ae.on_association_rejected(None)

    def test_association_released(self):
        """Test default callback raises exception"""
        ae = AE()
        ae.on_association_released(None)

    def test_association_aborted(self):
        """Test default callback raises exception"""
        ae = AE()
        ae.on_association_aborted(None)


class TestAEGoodAssociation(object):
    def setup(self):
        """Run prior to each test"""
        self.scp = None

    def teardown(self):
        """Clear any active threads"""
        if self.scp:
            self.scp.abort()

        time.sleep(0.1)

        for thread in threading.enumerate():
            if isinstance(thread, (AE, DummyBaseSCP)):
                thread.abort()
                thread.stop()

    def test_associate_establish_release(self):
        """ Check SCU Association with SCP """
        self.scp = DummyVerificationSCP()
        self.scp.start()

        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assoc.release()
        assert not assoc.is_established
        assert assoc.is_released

        self.scp.stop()

    def test_associate_max_pdu(self):
        """ Check Association has correct max PDUs on either end """
        self.scp = DummyVerificationSCP()
        self.scp.ae.maximum_pdu_size = 54321
        self.scp.start()

        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112, max_pdu=12345)
        assert self.scp.ae.active_associations[0].local_max_pdu == 54321
        assert self.scp.ae.active_associations[0].peer_max_pdu == 12345
        assert assoc.local_max_pdu == 12345
        assert assoc.peer_max_pdu == 54321
        assoc.release()

        # Check 0 max pdu value
        assoc = ae.associate('localhost', 11112, max_pdu=0)
        assert assoc.local_max_pdu == 0
        assert self.scp.ae.active_associations[0].peer_max_pdu == 0
        assoc.release()

        self.scp.stop()

    def test_association_timeouts(self):
        """ Check that the Association timeouts are being set correctly and
        work """
        self.scp = DummyVerificationSCP()
        self.scp.start()

        ae = AE()
        ae.add_requested_context(VerificationSOPClass)

        self.scp.ae.acse_timeout = 0
        self.scp.ae.dimse_timeout = 0
        self.scp.ae.network_timeout = 0.2

        ae.acse_timeout = 30
        ae.dimse_timeout = 30
        assoc = ae.associate('localhost', 11112)
        time.sleep(1)
        assert len(self.scp.ae.active_associations) == 0

        self.scp.ae.acse_timeout = None
        self.scp.ae.dimse_timeout = None
        self.scp.ae.network_timeout = None

        ae.acse_timeout = 30
        ae.dimse_timeout = 0
        self.scp.delay = 1
        assoc = ae.associate('localhost', 11112)
        assoc.send_c_echo()
        time.sleep(2)
        assert len(self.scp.ae.active_associations) == 0

        ae.acse_timeout = 0
        ae.dimse_timeout = 30
        assoc = ae.associate('localhost', 11112)
        time.sleep(1)
        assert len(self.scp.ae.active_associations) == 0

        self.scp.ae.acse_timeout = 21
        self.scp.ae.dimse_timeout = 22
        ae.acse_timeout = 31
        ae.dimse_timeout = 32

        assoc = ae.associate('localhost', 11112)
        assoc.send_c_echo()
        time.sleep(2)
        assert self.scp.ae.active_associations[0].acse_timeout == 21
        assert self.scp.ae.active_associations[0].dimse_timeout == 22
        assert assoc.acse_timeout == 31
        assert assoc.dimse_timeout == 32
        assoc.release()

        self.scp.stop()

    def test_association_contexts(self):
        """Tests for the AE.associate method's context parameter."""
        pass


class TestAEBadAssociation(object):
    def test_raise(self):
        """Test bad associate call"""
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)

        with pytest.raises(TypeError):
            ae.associate(1112, 11112)
        with pytest.raises(TypeError):
            ae.associate('localhost', '1.2.3.4')


class TestAEGoodTimeoutSetters(object):
    def test_acse_timeout(self):
        """ Check AE ACSE timeout change produces good value """
        ae = AE()
        assert ae.acse_timeout == 60
        ae.acse_timeout = None
        assert ae.acse_timeout is None
        ae.acse_timeout = -100
        assert ae.acse_timeout == 60
        ae.acse_timeout = 'a'
        assert ae.acse_timeout == 60
        ae.acse_timeout = 0
        assert ae.acse_timeout == 0
        ae.acse_timeout = 30
        assert ae.acse_timeout == 30

    def test_dimse_timeout(self):
        """ Check AE DIMSE timeout change produces good value """
        ae = AE()
        assert ae.dimse_timeout is None
        ae.dimse_timeout = None
        assert ae.dimse_timeout is None
        ae.dimse_timeout = -100
        assert ae.dimse_timeout is None
        ae.dimse_timeout = 'a'
        assert ae.dimse_timeout is None
        ae.dimse_timeout = 0
        assert ae.dimse_timeout == 0
        ae.dimse_timeout = 30
        assert ae.dimse_timeout == 30

    def test_network_timeout(self):
        """ Check AE network timeout change produces good value """
        ae = AE()
        assert ae.network_timeout is None
        ae.network_timeout = None
        assert ae.network_timeout is None
        ae.network_timeout = -100
        assert ae.network_timeout is None
        ae.network_timeout = 'a'
        assert ae.network_timeout is None
        ae.network_timeout = 0
        assert ae.network_timeout == 0
        ae.network_timeout = 30
        assert ae.network_timeout == 30


class TestAEGoodMiscSetters(object):
    def test_ae_title_good(self):
        """ Check AE title change produces good value """
        ae = AE()
        ae.ae_title = '     TEST     '
        assert ae.ae_title == 'TEST            '
        ae.ae_title = '            TEST'
        assert ae.ae_title == 'TEST            '
        ae.ae_title = '                 TEST'
        assert ae.ae_title == 'TEST            '
        ae.ae_title = 'a            TEST'
        assert ae.ae_title == 'a            TES'
        ae.ae_title = 'a        TEST'
        assert ae.ae_title == 'a        TEST   '

    def test_max_assoc_good(self):
        """ Check AE maximum association change produces good value """
        ae = AE()
        ae.maximum_associations = -10
        assert ae.maximum_associations == 1
        ae.maximum_associations = ['a']
        assert ae.maximum_associations == 1
        ae.maximum_associations = '10'
        assert ae.maximum_associations == 1
        ae.maximum_associations = 0
        assert ae.maximum_associations == 1
        ae.maximum_associations = 5
        assert ae.maximum_associations == 5

    def test_max_pdu_good(self):
        """ Check AE maximum pdu size change produces good value """
        ae = AE()
        ae.maximum_pdu_size = -10
        assert ae.maximum_pdu_size == 16382
        ae.maximum_pdu_size = 0
        assert ae.maximum_pdu_size == 0
        ae.maximum_pdu_size = 5000
        assert ae.maximum_pdu_size == 5000

    def test_require_calling_aet(self):
        """Test AE.require_calling_aet"""
        self.scp = DummyVerificationSCP()
        self.scp.start()

        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        # Test that we can associate OK initially
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established

        self.scp.ae.require_calling_aet = b'MYAE'
        assert self.scp.ae.require_calling_aet == b'MYAE            '
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_rejected

        self.scp.ae.require_calling_aet = b'PYNETDICOM      '
        assert self.scp.ae.require_calling_aet == b'PYNETDICOM      '
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assoc.release()

        self.scp.ae.require_calling_aet = b''
        assert self.scp.ae.require_calling_aet == b''
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assoc.release()

        self.scp.stop()

    def test_require_called_aet(self):
        """Test AE.require_called_aet"""
        self.scp = DummyVerificationSCP()
        self.scp.start()

        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        # Test that we can associate OK initially
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established

        self.scp.ae.require_called_aet = b'MYAE'
        assert self.scp.ae.require_called_aet == b'MYAE            '
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_rejected

        self.scp.ae.require_called_aet = b'ANY-SCP         '
        assert self.scp.ae.require_called_aet == b'ANY-SCP         '
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assoc.release()

        self.scp.ae.require_called_aet = b''
        assert self.scp.ae.require_called_aet == b''
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assoc.release()

        self.scp.stop()

    def test_req_calling_aet(self):
        """ Check AE require calling aet change produces good value """
        ae = AE()
        ae.require_calling_aet = b'10'
        assert ae.require_calling_aet == b'10              '
        ae.require_calling_aet = b'     TEST     '
        assert ae.require_calling_aet == b'TEST            '
        ae.require_calling_aet = b'           TESTB'
        assert ae.require_calling_aet == b'TESTB           '
        ae.require_calling_aet = b'a            TEST'
        assert ae.require_calling_aet == b'a            TES'

    def test_req_called_aet(self):
        """ Check AE require called aet change produces good value """
        ae = AE()
        ae.require_called_aet = b'10'
        assert ae.require_called_aet == b'10              '
        ae.require_called_aet = b'     TESTA    '
        assert ae.require_called_aet == b'TESTA           '
        ae.require_called_aet = b'           TESTB'
        assert ae.require_called_aet == b'TESTB           '
        ae.require_called_aet = b'a            TEST'
        assert ae.require_called_aet == b'a            TES'

    def test_string_output(self):
        """Test string output"""
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.require_calling_aet = b'something'
        ae.require_called_aet = b'elsething'
        assert 'Explicit VR' in ae.__str__()
        assert 'Verification' in ae.__str__()
        assert '0/2' in ae.__str__()
        assert 'something' in ae.__str__()
        assert 'elsething' in ae.__str__()
        ae.supported_contexts = StoragePresentationContexts
        assert 'CT Image' in ae.__str__()

        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        assert 'None' in ae.__str__()

        scp = DummyVerificationSCP()
        scp.start()
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assert 'Explicit VR' in ae.__str__()
        assert 'Peer' in ae.__str__()
        assoc.release()
        scp.stop()

    def test_init_implementation_class(self):
        """Test the default implementation class uid"""
        ae = AE()
        assert ae.implementation_class_uid == PYNETDICOM_IMPLEMENTATION_UID

    def test_init_implementation_version(self):
        """Test the default implementation version name"""
        ae = AE()
        assert ae.implementation_version_name == PYNETDICOM_IMPLEMENTATION_VERSION


class TestAEBadInitialisation(object):
    def test_ae_title_all_spaces(self):
        """AE should fail if ae_title is all spaces"""
        with pytest.raises(ValueError):
            AE(ae_title=b'                ', port=0)

    def test_ae_title_empty_str(self):
        """AE should fail if ae_title is an empty str"""
        with pytest.raises(ValueError):
            AE(ae_title=b'', port=0)

    def test_ae_title_invalid_chars(self):
        """ AE should fail if ae_title is not a str """
        with pytest.raises(ValueError):
            AE(ae_title=b'TEST\ME', port=0)

    def test_port_not_numeric(self):
        """AE should fail if port is not numeric"""
        with pytest.raises(ValueError):
            AE(port='a')

    def test_port_not_int(self):
        """AE should fail if port is not a int"""
        with pytest.raises(ValueError):
            AE(port=100.8)

    def test_port_not_positive(self):
        """AE should fail if port is not >= 0"""
        with pytest.raises(ValueError):
            AE(port=-1)


class TestAE_GoodRelease(object):
    def setup(self):
        """Run prior to each test"""
        self.scp = None

    def teardown(self):
        """Clear any active threads"""
        if self.scp:
            self.scp.abort()

        time.sleep(0.1)

        for thread in threading.enumerate():
            if isinstance(thread, (AE, DummyBaseSCP)):
                thread.abort()
                thread.stop()

    def test_ae_release_assoc(self):
        """ Association releases OK """
        self.scp = DummyVerificationSCP()
        self.scp.start()

        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        # Test N associate/release cycles
        for ii in range(5):
            assoc = ae.associate('localhost', 11112)
            assert assoc.is_established

            if assoc.is_established:
                assoc.release()
                assert not assoc.is_established
                assert not assoc.is_aborted
                assert assoc.is_released
                assert not assoc.is_rejected

        self.scp.stop()


class TestAE_GoodAbort(object):
    def setup(self):
        """Run prior to each test"""
        self.scp = None

    def teardown(self):
        """Clear any active threads"""
        if self.scp:
            self.scp.abort()

        time.sleep(0.1)

        for thread in threading.enumerate():
            if isinstance(thread, (AE, DummyBaseSCP)):
                thread.abort()
                thread.stop()

    def test_ae_aborts_assoc(self):
        """ Association aborts OK """
        self.scp = DummyVerificationSCP()
        self.scp.start()

        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        # Test N associate/abort cycles
        for ii in range(5):
            assoc = ae.associate('localhost', 11112)
            assert assoc.is_established

            if assoc.is_established:
                assoc.abort()
                assert not assoc.is_established
                assert assoc.is_aborted
                assert not assoc.is_released
                assert not assoc.is_rejected

        self.scp.stop()


class TestAESupportedPresentationContexts(object):
    """Tests for AE's presentation contexts when acting as an SCP"""
    def setup(self):
        self.ae = AE()

    def test_add_supported_context_str(self):
        """Tests for AE.add_supported_context using str."""
        self.ae.add_supported_context('1.2.840.10008.1.1')

        context = self.ae.supported_contexts[0]
        assert context.abstract_syntax == '1.2.840.10008.1.1'
        assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
        assert context.context_id is None

    def test_add_supported_context_sop_class(self):
        """Tests for AE.add_supported_context using SOPClass."""
        self.ae.add_supported_context(RTImageStorage)

        context = self.ae.supported_contexts[0]
        assert context.abstract_syntax == '1.2.840.10008.5.1.4.1.1.481.1'
        assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES

    def test_add_supported_context_uid(self):
        """Tests for AE.add_supported_context using UID."""
        self.ae.add_supported_context(UID('1.2.840.10008.1.1'))

        context = self.ae.supported_contexts[0]
        assert context.abstract_syntax == '1.2.840.10008.1.1'
        assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES

    def test_add_supported_context_duplicate(self):
        """Tests for AE.add_supported_context using a duplicate UID."""
        self.ae.add_supported_context(UID('1.2.840.10008.1.1'))
        self.ae.add_supported_context(UID('1.2.840.10008.1.1'))

        contexts = self.ae.supported_contexts
        assert len(contexts) == 1
        assert contexts[0].abstract_syntax == '1.2.840.10008.1.1'
        assert contexts[0].transfer_syntax == DEFAULT_TRANSFER_SYNTAXES

    def test_add_supported_context_transfer_single(self):
        """Test adding a single transfer syntax without a list"""
        self.ae.add_supported_context('1.2', '1.3')

        contexts = self.ae.supported_contexts
        assert len(contexts) == 1
        assert contexts[0].abstract_syntax == '1.2'
        assert contexts[0].transfer_syntax == ['1.3']

        self.ae.add_supported_context('1.2', UID('1.4'))

        contexts = self.ae.supported_contexts
        assert len(contexts) == 1
        assert contexts[0].abstract_syntax == '1.2'
        assert contexts[0].transfer_syntax == ['1.3', '1.4']

    def test_add_supported_context_duplicate_transfer(self):
        """Test adding duplicate transfer syntaxes."""
        self.ae.add_supported_context('1.2', ['1.3', '1.3'])

        contexts = self.ae.supported_contexts
        assert len(contexts) == 1
        assert contexts[0].abstract_syntax == '1.2'
        assert contexts[0].transfer_syntax == ['1.3']

        self.ae.supported_contexts = []
        self.ae.add_supported_context('1.2.840.10008.1.1')
        self.ae.add_supported_context('1.2.840.10008.1.1')

        contexts = self.ae.supported_contexts
        assert len(contexts) == 1
        assert contexts[0].abstract_syntax == '1.2.840.10008.1.1'
        assert contexts[0].transfer_syntax == DEFAULT_TRANSFER_SYNTAXES

        self.ae.supported_contexts = []
        self.ae.add_supported_context('1.2.840.10008.1.1')
        self.ae.add_supported_context('1.2.840.10008.1.1', [DEFAULT_TRANSFER_SYNTAXES[0]])

        contexts = self.ae.supported_contexts
        assert len(contexts) == 1
        assert contexts[0].abstract_syntax == '1.2.840.10008.1.1'
        assert contexts[0].transfer_syntax == DEFAULT_TRANSFER_SYNTAXES

    def test_add_supported_context_duplicate_multi(self):
        """Tests for AE.add_supported_context using a duplicate UID."""
        self.ae.add_supported_context('1.2.840.10008.1.1',
                                      [DEFAULT_TRANSFER_SYNTAXES[0]])
        self.ae.add_supported_context('1.2.840.10008.1.1',
                                      DEFAULT_TRANSFER_SYNTAXES[1:])


        contexts = self.ae.supported_contexts
        assert len(contexts) == 1
        assert contexts[0].abstract_syntax == '1.2.840.10008.1.1'
        assert contexts[0].transfer_syntax == DEFAULT_TRANSFER_SYNTAXES

    def test_add_supported_context_private_abs(self):
        """Test AE.add_supported_context with a private abstract syntax"""
        self.ae.add_supported_context('1.2.3.4')

        contexts = self.ae.supported_contexts
        assert len(contexts) == 1
        assert contexts[0].abstract_syntax == '1.2.3.4'
        assert contexts[0].transfer_syntax == DEFAULT_TRANSFER_SYNTAXES

    def test_add_supported_context_private_tran(self):
        """Test AE.add_supported_context with a private transfer syntax"""
        self.ae.add_supported_context('1.2.3.4',
                                      ['1.2.3', '1.2.840.10008.1.1'])

        contexts = self.ae.supported_contexts
        assert len(contexts) == 1
        assert contexts[0].abstract_syntax == '1.2.3.4'
        assert contexts[0].transfer_syntax == ['1.2.3', '1.2.840.10008.1.1']

    def test_add_supported_context_more_128(self):
        """Test adding more than 128 presentation contexts"""
        for ii in range(300):
            self.ae.add_supported_context(str(ii))

        contexts = self.ae.supported_contexts
        assert len(contexts) == 300

    def test_supported_contexts_setter(self):
        """Test the AE.supported_contexts property setter."""
        context = build_context('1.2.840.10008.1.1')
        self.ae.supported_contexts = [context]

        contexts = self.ae.supported_contexts
        assert len(contexts) == 1
        assert context.abstract_syntax == '1.2.840.10008.1.1'
        assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
        assert context.context_id is None

    def test_supported_contexts_empty(self):
        """Test the setting supported_contexts to an empty list."""
        context = build_context('1.2.840.10008.1.1')
        self.ae.supported_contexts = [context]
        assert len(self.ae.supported_contexts) == 1

        self.ae.supported_contexts = []
        assert len(self.ae.supported_contexts) == 0

    def test_supported_contexts_setter_raises(self):
        """Test the AE.supported_contexts property raises if not context."""
        with pytest.raises(ValueError):
            self.ae.supported_contexts = ['1.2.3']

    def test_supported_contexts_sorted(self):
        """Test that the supported_contexts returns contexts in order."""
        self.ae.add_supported_context('1.2.3.4')
        self.ae.add_supported_context('1.2.3.5')

        asyntaxes = [
            cntx.abstract_syntax for cntx in self.ae.supported_contexts
        ]
        assert asyntaxes == ['1.2.3.4', '1.2.3.5']

        self.ae.add_supported_context('0.1.2.3')
        self.ae.add_supported_context('2.1.2.3')
        asyntaxes = [
            cntx.abstract_syntax for cntx in self.ae.supported_contexts
        ]
        assert asyntaxes == ['0.1.2.3', '1.2.3.4', '1.2.3.5', '2.1.2.3']

    def test_supported_contexts_more_128(self):
        """Test setting supported_contexts with more than 128 contexts."""
        contexts = []
        for ii in range(300):
            contexts.append(build_context(str(ii)))

        self.ae.supported_contexts = contexts
        assert len(self.ae.supported_contexts) == 300

    def test_remove_supported_context_str(self):
        """Tests for AE.remove_supported_context using str."""
        self.ae.add_supported_context('1.2.840.10008.1.1')

        context = self.ae.supported_contexts[0]
        assert context.abstract_syntax == '1.2.840.10008.1.1'
        assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES

        self.ae.remove_supported_context('1.2.840.10008.1.1')
        assert len(self.ae.supported_contexts) == 0

        # Test multiple
        self.ae.add_supported_context('1.2.840.10008.1.1')
        self.ae.add_supported_context('1.2.840.10008.1.4', ['1.2.3.4'])

        assert len(self.ae.supported_contexts) == 2
        self.ae.remove_supported_context('1.2.840.10008.1.1')
        assert len(self.ae.supported_contexts) == 1

        for context in self.ae.supported_contexts:
            assert context.abstract_syntax != '1.2.840.10008.1.1'

    def test_remove_supported_context_uid(self):
        """Tests for AE.remove_supported_context using UID."""
        self.ae.add_supported_context('1.2.840.10008.1.1')

        context = self.ae.supported_contexts[0]
        assert context.abstract_syntax == '1.2.840.10008.1.1'
        assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES

        self.ae.remove_supported_context(UID('1.2.840.10008.1.1'))
        assert len(self.ae.supported_contexts) == 0

    def test_remove_supported_context_sop_class(self):
        """Tests for AE.remove_supported_context using SOPClass."""
        self.ae.add_supported_context(RTImageStorage)

        context = self.ae.supported_contexts[0]
        assert context.abstract_syntax == '1.2.840.10008.5.1.4.1.1.481.1'
        assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES

        self.ae.remove_supported_context(RTImageStorage)
        assert len(self.ae.supported_contexts) == 0

    def test_remove_supported_context_default(self):
        """Tests for AE.remove_supported_context with default transfers."""
        self.ae.add_supported_context('1.2.840.10008.1.1')

        context = self.ae.supported_contexts[0]
        assert context.abstract_syntax == '1.2.840.10008.1.1'
        assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
        assert len(context.transfer_syntax) == 3

        self.ae.remove_supported_context('1.2.840.10008.1.1')
        assert len(self.ae.supported_contexts) == 0

    def test_remove_supported_context_single_transfer(self):
        """Tests for AE.remove_supported_context with single transfer."""
        self.ae.add_supported_context('1.2.840.10008.1.1')

        context = self.ae.supported_contexts[0]
        assert context.abstract_syntax == '1.2.840.10008.1.1'
        assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
        assert len(context.transfer_syntax) == 3

        self.ae.remove_supported_context('1.2.840.10008.1.1', DEFAULT_TRANSFER_SYNTAXES[0])
        context = self.ae.supported_contexts[0]
        assert context.abstract_syntax == '1.2.840.10008.1.1'
        assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES[1:]

    def test_remove_supported_context_partial(self):
        """Tests for AE.remove_supported_context with partial transfers."""
        # Test singular
        self.ae.add_supported_context('1.2.840.10008.1.1')

        context = self.ae.supported_contexts[0]
        assert context.abstract_syntax == '1.2.840.10008.1.1'
        assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
        assert len(context.transfer_syntax) == 3

        self.ae.remove_supported_context('1.2.840.10008.1.1',
                                         ['1.2.840.10008.1.2'])
        assert len(self.ae.supported_contexts) == 1
        context = self.ae.supported_contexts[0]
        assert len(context.transfer_syntax) == 2
        assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES[1:]
        assert context.abstract_syntax == '1.2.840.10008.1.1'

        # Test multiple
        self.ae.add_supported_context('1.2.840.10008.1.1')
        self.ae.add_supported_context(RTImageStorage)

        self.ae.remove_supported_context('1.2.840.10008.1.1',
                                         ['1.2.840.10008.1.2'])
        assert len(self.ae.supported_contexts) == 2
        context = self.ae.supported_contexts[0]
        assert len(context.transfer_syntax) == 2
        assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES[1:]
        assert context.abstract_syntax == '1.2.840.10008.1.1'

        assert self.ae.supported_contexts[1].transfer_syntax == DEFAULT_TRANSFER_SYNTAXES

    def test_remove_supported_context_all(self):
        """Tests for AE.remove_supported_context with all transfers."""
        self.ae.add_supported_context('1.2.840.10008.1.1')

        context = self.ae.supported_contexts[0]
        assert context.abstract_syntax == '1.2.840.10008.1.1'
        assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
        assert len(context.transfer_syntax) == 3

        # Test singular
        self.ae.remove_supported_context('1.2.840.10008.1.1',
                                         DEFAULT_TRANSFER_SYNTAXES)
        assert len(self.ae.supported_contexts) == 0

        # Test multiple
        self.ae.add_supported_context('1.2.840.10008.1.1')
        self.ae.add_supported_context(RTImageStorage)

        self.ae.remove_supported_context('1.2.840.10008.1.1',
                                         DEFAULT_TRANSFER_SYNTAXES)

        context = self.ae.supported_contexts[0]
        assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
        assert context.abstract_syntax == '1.2.840.10008.5.1.4.1.1.481.1'

    def test_remove_supported_context_all_plus(self):
        """Test remove_supported_context with extra transfers"""
        tsyntax = DEFAULT_TRANSFER_SYNTAXES[:]
        tsyntax.append('1.2.3')
        self.ae.add_supported_context('1.2.840.10008.1.1')

        context = self.ae.supported_contexts[0]
        assert context.abstract_syntax == '1.2.840.10008.1.1'
        assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
        assert len(context.transfer_syntax) == 3

        self.ae.remove_supported_context('1.2.840.10008.1.1', tsyntax)
        assert len(self.ae.supported_contexts) == 0


class TestAERequestedPresentationContexts(object):
    """Tests for AE's presentation contexts when acting as an SCU"""
    def setup(self):
        self.ae = AE()

    def test_add_requested_context_str(self):
        """Tests for AE.add_requested_context using str."""
        self.ae.add_requested_context('1.2.840.10008.1.1')

        context = self.ae.requested_contexts[0]
        assert context.abstract_syntax == '1.2.840.10008.1.1'
        assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
        assert context.context_id is None

    def test_add_requested_context_sop_class(self):
        """Tests for AE.add_requested_context using SOPClass."""
        self.ae.add_requested_context(RTImageStorage)

        context = self.ae.requested_contexts[0]
        assert context.abstract_syntax == '1.2.840.10008.5.1.4.1.1.481.1'
        assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES

    def test_add_requested_context_uid(self):
        """Tests for AE.add_requested_context using UID."""
        self.ae.add_requested_context(UID('1.2.840.10008.1.1'))

        context = self.ae.requested_contexts[0]
        assert context.abstract_syntax == '1.2.840.10008.1.1'
        assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES

    def test_add_requested_context_duplicate(self):
        """Test AE.add_requested_context using a duplicate UID."""
        self.ae.add_requested_context(UID('1.2.840.10008.1.1'))
        self.ae.add_requested_context(UID('1.2.840.10008.1.1'))

        contexts = self.ae.requested_contexts
        assert len(contexts) == 2
        assert contexts[0].abstract_syntax == '1.2.840.10008.1.1'
        assert contexts[0].transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
        assert contexts[1].abstract_syntax == '1.2.840.10008.1.1'
        assert contexts[1].transfer_syntax == DEFAULT_TRANSFER_SYNTAXES

    def test_add_requested_context_duplicate_multi(self):
        """Tests for AE.add_requested_context using a duplicate UID."""
        self.ae.add_requested_context('1.2.840.10008.1.1',
                                      [DEFAULT_TRANSFER_SYNTAXES[0]])
        self.ae.add_requested_context('1.2.840.10008.1.1',
                                      DEFAULT_TRANSFER_SYNTAXES[1:])


        contexts = self.ae.requested_contexts
        assert len(contexts) == 2
        assert contexts[0].abstract_syntax == '1.2.840.10008.1.1'
        assert contexts[0].transfer_syntax == [DEFAULT_TRANSFER_SYNTAXES[0]]
        assert contexts[1].abstract_syntax == '1.2.840.10008.1.1'
        assert contexts[1].transfer_syntax == DEFAULT_TRANSFER_SYNTAXES[1:]

    def test_add_supported_context_transfer_single(self):
        """Test adding a single transfer syntax without a list"""
        self.ae.add_requested_context('1.2', '1.3')

        contexts = self.ae.requested_contexts
        assert len(contexts) == 1
        assert contexts[0].abstract_syntax == '1.2'
        assert contexts[0].transfer_syntax == ['1.3']

        self.ae.add_requested_context('1.2', UID('1.4'))

        contexts = self.ae.requested_contexts
        assert len(contexts) == 2
        assert contexts[1].abstract_syntax == '1.2'
        assert contexts[1].transfer_syntax == ['1.4']

    def test_add_requested_context_duplicate_transfer(self):
        """Test add_requested_context using duplicate transfer syntaxes"""
        self.ae.add_requested_context('1.2', ['1.3', '1.3'])
        contexts = self.ae.requested_contexts
        assert contexts[0].transfer_syntax == ['1.3']

    def test_add_requested_context_private_abs(self):
        """Test AE.add_requested_context with a private abstract syntax"""
        self.ae.add_requested_context('1.2.3.4')

        contexts = self.ae.requested_contexts
        assert len(contexts) == 1
        assert contexts[0].abstract_syntax == '1.2.3.4'
        assert contexts[0].transfer_syntax == DEFAULT_TRANSFER_SYNTAXES

    def test_add_requested_context_private_tran(self):
        """Test AE.add_requested_context with a private transfer syntax"""
        self.ae.add_requested_context('1.2.3.4',
                                      ['1.2.3', '1.2.840.10008.1.1'])

        contexts = self.ae.requested_contexts
        assert len(contexts) == 1
        assert contexts[0].abstract_syntax == '1.2.3.4'
        assert contexts[0].transfer_syntax == ['1.2.3', '1.2.840.10008.1.1']

    def test_add_requested_context_more_128_raises(self):
        """Test adding more than 128 presentation contexts"""
        for ii in range(128):
            self.ae.add_requested_context(str(ii))

        assert len(self.ae.requested_contexts) == 128

        with pytest.raises(ValueError):
            self.ae.add_requested_context('129')

        assert len(self.ae.requested_contexts) == 128

    def test_requested_contexts_setter(self):
        """Test the AE.requested_contexts property setter."""
        context = build_context('1.2.840.10008.1.1')
        self.ae.requested_contexts = [context]

        contexts = self.ae.requested_contexts
        assert len(contexts) == 1
        assert context.abstract_syntax == '1.2.840.10008.1.1'
        assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
        assert context.context_id is None

    def test_requested_contexts_empty(self):
        """Test the setting requested_contexts to an empty list."""
        context = build_context('1.2.840.10008.1.1')
        self.ae.requested_contexts = [context]
        assert len(self.ae.requested_contexts) == 1

        self.ae.requested_contexts = []
        assert len(self.ae.requested_contexts) == 0

    def test_requested_contexts_setter_raises(self):
        """Test the AE.requested_contexts property raises if not context."""
        with pytest.raises(ValueError):
            self.ae.requested_contexts = ['1.2.3']

    def test_requested_contexts_not_sorted(self):
        """Test that requested_contexts returns contexts in supplied order."""
        self.ae.add_requested_context('1.2.3.4')
        self.ae.add_requested_context('1.2.3.5')

        asyntaxes = [
            cntx.abstract_syntax for cntx in self.ae.requested_contexts
        ]
        assert asyntaxes == ['1.2.3.4', '1.2.3.5']

        self.ae.add_requested_context('0.1.2.3')
        self.ae.add_requested_context('2.1.2.3')
        asyntaxes = [
            cntx.abstract_syntax for cntx in self.ae.requested_contexts
        ]
        assert asyntaxes == ['1.2.3.4', '1.2.3.5', '0.1.2.3', '2.1.2.3']

    def test_requested_contexts_more_128(self):
        """Test setting requested_contexts with more than 128 contexts."""
        contexts = []
        for ii in range(128):
            contexts.append(build_context(str(ii)))

        self.ae.requested_contexts = contexts
        assert len(self.ae.requested_contexts) == 128

        contexts.append(build_context('129'))

        with pytest.raises(ValueError):
            self.ae.requested_contexts = contexts

    def test_remove_requested_context_str(self):
        """Tests for AE.remove_requested_context using str."""
        # Test singular
        self.ae.add_requested_context('1.2.840.10008.1.1')

        context = self.ae.requested_contexts[0]
        assert context.abstract_syntax == '1.2.840.10008.1.1'
        assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES

        self.ae.remove_requested_context('1.2.840.10008.1.1')
        assert len(self.ae.requested_contexts) == 0

        # Test multiple
        self.ae.add_requested_context('1.2.840.10008.1.1')
        self.ae.add_requested_context('1.2.840.10008.1.1', ['1.2.3.4'])
        self.ae.add_requested_context('1.2.840.10008.1.4', ['1.2.3.4'])

        assert len(self.ae.requested_contexts) == 3
        self.ae.remove_requested_context('1.2.840.10008.1.1')
        assert len(self.ae.requested_contexts) == 1

        for context in self.ae.requested_contexts:
            assert context.abstract_syntax != '1.2.840.10008.1.1'

    def test_remove_requested_context_uid(self):
        """Tests for AE.remove_requested_context using UID."""
        self.ae.add_requested_context('1.2.840.10008.1.1')

        context = self.ae.requested_contexts[0]
        assert context.abstract_syntax == '1.2.840.10008.1.1'
        assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES

        self.ae.remove_requested_context(UID('1.2.840.10008.1.1'))
        assert len(self.ae.requested_contexts) == 0

    def test_remove_requested_context_sop_class(self):
        """Tests for AE.remove_requested_context using SOPClass."""
        self.ae.add_requested_context(RTImageStorage)

        context = self.ae.requested_contexts[0]
        assert context.abstract_syntax == '1.2.840.10008.5.1.4.1.1.481.1'
        assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES

        self.ae.remove_requested_context(RTImageStorage)
        assert len(self.ae.requested_contexts) == 0

    def test_remove_requested_context_default(self):
        """Tests for AE.remove_requested_context with default transfers."""
        self.ae.add_requested_context('1.2.840.10008.1.1')

        context = self.ae.requested_contexts[0]
        assert context.abstract_syntax == '1.2.840.10008.1.1'
        assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
        assert len(context.transfer_syntax) == 3

        self.ae.remove_requested_context('1.2.840.10008.1.1')
        assert len(self.ae.requested_contexts) == 0

    def test_remove_requested_context_single(self):
        """Tests for AE.remove_requested_context with single transfer."""
        self.ae.add_requested_context('1.2.840.10008.1.1')

        context = self.ae.requested_contexts[0]
        assert context.abstract_syntax == '1.2.840.10008.1.1'
        assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
        assert len(context.transfer_syntax) == 3

        self.ae.remove_requested_context('1.2.840.10008.1.1', DEFAULT_TRANSFER_SYNTAXES[0])
        context = self.ae.requested_contexts[0]
        assert context.abstract_syntax == '1.2.840.10008.1.1'
        assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES[1:]

    def test_remove_requested_context_partial(self):
        """Tests for AE.remove_supported_context with partial transfers."""
        # Test singular
        self.ae.add_requested_context('1.2.840.10008.1.1')

        context = self.ae.requested_contexts[0]
        assert context.abstract_syntax == '1.2.840.10008.1.1'
        assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
        assert len(context.transfer_syntax) == 3

        self.ae.remove_requested_context('1.2.840.10008.1.1',
                                         ['1.2.840.10008.1.2'])
        assert len(self.ae.requested_contexts) == 1
        context = self.ae.requested_contexts[0]
        assert len(context.transfer_syntax) == 2
        assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES[1:]
        assert context.abstract_syntax == '1.2.840.10008.1.1'

        self.ae.remove_requested_context('1.2.840.10008.1.1')
        assert len(self.ae.requested_contexts) == 0

        # Test multiple
        self.ae.add_requested_context('1.2.840.10008.1.1')
        self.ae.add_requested_context(RTImageStorage)
        self.ae.add_requested_context('1.2.840.10008.1.1', ['1.2.3.4'])

        self.ae.remove_requested_context('1.2.840.10008.1.1',
                                         ['1.2.840.10008.1.2'])
        assert len(self.ae.requested_contexts) == 3
        context = self.ae.requested_contexts[0]
        assert len(context.transfer_syntax) == 2
        assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES[1:]
        assert context.abstract_syntax == '1.2.840.10008.1.1'

        assert self.ae.requested_contexts[1].transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
        assert self.ae.requested_contexts[2].transfer_syntax == ['1.2.3.4']
        assert self.ae.requested_contexts[2].abstract_syntax == '1.2.840.10008.1.1'

        self.ae.remove_requested_context('1.2.840.10008.1.1')
        assert len(self.ae.requested_contexts) == 1
        assert self.ae.requested_contexts[0].abstract_syntax == '1.2.840.10008.5.1.4.1.1.481.1'

    def test_remove_requested_context_all(self):
        """Tests for AE.remove_requested_context with all transfers."""
        self.ae.add_requested_context('1.2.840.10008.1.1')

        context = self.ae.requested_contexts[0]
        assert context.abstract_syntax == '1.2.840.10008.1.1'
        assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
        assert len(context.transfer_syntax) == 3

        # Test singular
        self.ae.remove_requested_context('1.2.840.10008.1.1',
                                         DEFAULT_TRANSFER_SYNTAXES)
        assert len(self.ae.requested_contexts) == 0

        # Test multiple
        self.ae.add_requested_context('1.2.840.10008.1.1',
                                      [DEFAULT_TRANSFER_SYNTAXES[0]])
        self.ae.add_requested_context('1.2.840.10008.1.1',
                                      DEFAULT_TRANSFER_SYNTAXES[1:])
        self.ae.add_requested_context(RTImageStorage)

        self.ae.remove_requested_context('1.2.840.10008.1.1',
                                         DEFAULT_TRANSFER_SYNTAXES)

        assert len(self.ae.requested_contexts) == 1
        context = self.ae.requested_contexts[0]
        assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
        assert context.abstract_syntax == '1.2.840.10008.5.1.4.1.1.481.1'

    def test_remove_requested_context_all_plus(self):
        """Test remove_requested_context with extra transfers"""
        tsyntax = DEFAULT_TRANSFER_SYNTAXES[:]
        tsyntax.append('1.2.3')
        # Test singular
        self.ae.add_requested_context('1.2.840.10008.1.1')

        context = self.ae.requested_contexts[0]
        assert context.abstract_syntax == '1.2.840.10008.1.1'
        assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
        assert len(context.transfer_syntax) == 3

        self.ae.remove_requested_context('1.2.840.10008.1.1', tsyntax)
        assert len(self.ae.requested_contexts) == 0

        # Test multiple
        self.ae.add_requested_context('1.2.840.10008.1.1',
                                      [DEFAULT_TRANSFER_SYNTAXES[0]])
        self.ae.add_requested_context('1.2.840.10008.1.1',
                                      DEFAULT_TRANSFER_SYNTAXES[1:])
        self.ae.add_requested_context(RTImageStorage)

        self.ae.remove_requested_context('1.2.840.10008.1.1', tsyntax)

        assert len(self.ae.requested_contexts) == 1
        context = self.ae.requested_contexts[0]
        assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
        assert context.abstract_syntax == '1.2.840.10008.5.1.4.1.1.481.1'
