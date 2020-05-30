"""Tests for the ae module."""

import os
import signal
import threading
import time

import pytest

from pydicom import read_file
from pydicom.dataset import Dataset
from pydicom.uid import UID, ImplicitVRLittleEndian

from pynetdicom import (
    AE, evt, debug_logger, build_context,
    DEFAULT_TRANSFER_SYNTAXES,
    StoragePresentationContexts,
    VerificationPresentationContexts,
    PYNETDICOM_IMPLEMENTATION_UID,
    PYNETDICOM_IMPLEMENTATION_VERSION
)
from pynetdicom.presentation import build_context
from pynetdicom.sop_class import RTImageStorage, VerificationSOPClass
from pynetdicom.transport import AssociationServer, RequestHandler


#debug_logger()


TEST_DS_DIR = os.path.join(os.path.dirname(__file__), 'dicom_files')
DATASET = read_file(os.path.join(TEST_DS_DIR, 'RTImageStorage.dcm'))
COMP_DATASET = read_file(os.path.join(TEST_DS_DIR, 'MRImageStorage_JPG2000_Lossless.dcm'))


def test_blocking_handler():
    """Test binding events to the blocking AssociationServer."""
    ae = AE()
    ae.add_supported_context('1.2.840.10008.1.1')

    def handle_echo(event):
        return 0x0000

    handlers = [(evt.EVT_C_ECHO, handle_echo)]

    thread = threading.Thread(
        target=ae.start_server,
        args=(('', 11112), ),
        kwargs={'evt_handlers' : handlers}
    )
    thread.daemon = True
    thread.start()

    time.sleep(0.1)

    ae.shutdown()


class TestMakeServer(object):
    """Tests for AE.make_server()"""
    def setup(self):
        """Run prior to each test"""
        self.ae = None

    def teardown(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

    def test_default_arguments(self):
        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)

        server = ae.make_server(('', 11112))
        assert isinstance(server, AssociationServer)

    def test_custom_request_handler(self):
        class MyRequestHandler(RequestHandler):
            pass

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)

        server = ae.make_server(('', 11112), request_handler=MyRequestHandler)
        assert server.RequestHandlerClass is MyRequestHandler


class TestStartServer(object):
    """Tests for AE.start_server()"""
    def setup(self):
        """Run prior to each test"""
        self.ae = None

    def teardown(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

    def test_ae_title(self):
        """Test the `ae_title` keyword parameter."""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.ae_title = b'TESTAET'
        assert ae.ae_title == b'TESTAET         '

        ae.add_supported_context(VerificationSOPClass)
        server = ae.start_server(('', 11112), block=False)
        assert server.ae_title == ae.ae_title

        server.shutdown()

        server = ae.start_server(('', 11112), block=False, ae_title=b'MYAE')
        assert server.ae_title == b'MYAE            '
        ae.require_called_aet = True

        ae.add_requested_context(VerificationSOPClass)
        assoc = ae.associate('', 11112, ae_title=b'MYAE')
        assert assoc.is_established
        assoc.release()
        assert assoc.is_released

        server.shutdown()

    def test_contexts(self):
        """Test the `contexts` keyword parameter."""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.ae_title = b'TESTAET'
        assert ae.ae_title == b'TESTAET         '

        cx = build_context(VerificationSOPClass)
        server = ae.start_server(('', 11112), block=False, contexts=[cx])

        ae.add_requested_context(VerificationSOPClass)
        assoc = ae.associate('', 11112, ae_title=b'MYAE')
        assert assoc.is_established
        assert assoc.accepted_contexts[0].abstract_syntax == VerificationSOPClass
        assoc.release()
        assert assoc.is_released

        server.shutdown()


class TestAEVerificationSCP(object):
    """Check verification SCP"""
    def setup(self):
        """Run prior to each test"""
        self.ae = None

    def teardown(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

    def test_start_server_keyboard_interrupt(self):
        """Test stopping the SCP with keyboard"""
        pid = os.getpid()

        def trigger_signal():
            time.sleep(0.1)
            os.kill(pid, signal.SIGINT)

        self.ae = ae = AE()
        ae.add_supported_context('1.2.3')
        thread = threading.Thread(target=trigger_signal)
        thread.daemon = True
        thread.start()

        ae.start_server(('', 11112))

        ae.shutdown()

    def test_no_supported_contexts(self):
        """Test starting with no contexts raises"""
        ae = AE()
        with pytest.raises(ValueError, match=r"No supported Presentation"):
            ae.start_server(('', 11112))

    def test_new_scu_scp_warning(self, caplog):
        """Test that a warning is given if scu_role and scp_role bad."""
        ae = AE()
        ae.add_supported_context('1.2.3.4', scp_role=False)
        msg = r"The following presentation contexts have "
        with pytest.raises(ValueError, match=msg):
            ae.start_server(('', 11112))

    def test_str_empty(self):
        """Test str output for default AE"""
        ae = AE()
        ae.__str__()


class TestAEPresentationSCU(object):
    """Tests for AE presentation contexts when running as an SCU"""
    def setup(self):
        """Run prior to each test"""
        self.ae = None

    def teardown(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

    def test_associate_context(self):
        """Test that AE.associate doesn't modify the supplied contexts"""
        # Test AE.requested_contexts
        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)

        ae.requested_contexts = VerificationPresentationContexts
        ae.acse_timeout = 5
        ae.dimse_timeout = 5

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        assert ae.requested_contexts[0].context_id is None
        assert len(assoc.requestor.requested_contexts) == 1
        assert assoc.requestor.requested_contexts[0].abstract_syntax == (
            '1.2.840.10008.1.1'
        )
        assert assoc.requestor.requested_contexts[0].context_id == 1
        assoc.release()
        assert not assoc.is_established
        assert assoc.is_released

        # Test associate(contexts=...)
        ae.requested_contexts = []
        assoc = ae.associate('localhost', 11112,
                             contexts=VerificationPresentationContexts)
        assert assoc.is_established

        assert VerificationPresentationContexts[0].context_id is None
        assert len(assoc.requestor.requested_contexts) == 1
        assert assoc.requestor.requested_contexts[0].abstract_syntax == (
            '1.2.840.10008.1.1'
        )
        assert assoc.requestor.requested_contexts[0].context_id == 1
        assoc.release()
        assert not assoc.is_established
        assert assoc.is_released

        scp.shutdown()

    def test_associate_context_raises(self):
        """Test that AE.associate raises exception if no requested contexts"""
        self.ae = ae = AE()
        with pytest.raises(RuntimeError):
            assoc = ae.associate('localhost', 11112)


class TestAEGoodTimeoutSetters(object):
    def test_acse_timeout(self):
        """ Check AE ACSE timeout change produces good value """
        ae = AE()
        assert ae.acse_timeout == 30
        ae.acse_timeout = None
        assert ae.acse_timeout is None
        ae.acse_timeout = -100
        assert ae.acse_timeout == 30
        ae.acse_timeout = 'a'
        assert ae.acse_timeout == 30
        ae.acse_timeout = 0
        assert ae.acse_timeout == 0
        ae.acse_timeout = 30
        assert ae.acse_timeout == 30

    def test_dimse_timeout(self):
        """ Check AE DIMSE timeout change produces good value """
        ae = AE()
        assert ae.dimse_timeout == 30
        ae.dimse_timeout = None
        assert ae.dimse_timeout is None
        ae.dimse_timeout = -100
        assert ae.dimse_timeout == 30
        ae.dimse_timeout = 'a'
        assert ae.dimse_timeout == 30
        ae.dimse_timeout = 0
        assert ae.dimse_timeout == 0
        ae.dimse_timeout = 30
        assert ae.dimse_timeout == 30

    def test_network_timeout(self):
        """ Check AE network timeout change produces good value """
        ae = AE()
        assert ae.network_timeout == 60
        ae.network_timeout = None
        assert ae.network_timeout is None
        ae.network_timeout = -100
        assert ae.network_timeout == 60
        ae.network_timeout = 'a'
        assert ae.network_timeout == 60
        ae.network_timeout = 0
        assert ae.network_timeout == 0
        ae.network_timeout = 30
        assert ae.network_timeout == 30

    def test_active_acse(self):
        """Test changing acse_timeout with active associations."""
        ae = AE()
        ae.add_supported_context('1.2.840.10008.1.1')
        scp = ae.start_server(('', 11112), block=False)

        ae.add_requested_context('1.2.840.10008.1.1')
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        assert assoc.acse_timeout == 30
        ae.acse_timeout = 5
        assert assoc.acse_timeout == 5

        assoc.release()

        scp.shutdown()
        ae.shutdown()

    def test_active_dimse(self):
        """Test changing dimse_timeout with active associations."""
        ae = AE()
        ae.add_supported_context('1.2.840.10008.1.1')
        scp = ae.start_server(('', 11112), block=False)

        ae.add_requested_context('1.2.840.10008.1.1')
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        assert assoc.dimse_timeout == 30
        ae.dimse_timeout = 5
        assert assoc.dimse_timeout == 5

        assoc.release()

        scp.shutdown()

    def test_active_network(self):
        """Test changing network_timeout with active associations."""
        ae = AE()
        ae.add_supported_context('1.2.840.10008.1.1')
        scp = ae.start_server(('', 11112), block=False)

        ae.add_requested_context('1.2.840.10008.1.1')
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        assert assoc.network_timeout == 60
        ae.network_timeout = 5
        assert assoc.network_timeout == 5

        assoc.release()

        scp.shutdown()


class TestAEGoodAssociation(object):
    def setup(self):
        """Run prior to each test"""
        self.ae = None

    def teardown(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

    def test_associate_establish_release(self):
        """ Check SCU Association with SCP """
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)

        ae.add_requested_context(VerificationSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established

        assoc.release()
        assert not assoc.is_established
        assert assoc.is_released

        scp.shutdown()

    def test_associate_max_pdu(self):
        """ Check Association has correct max PDUs on either end """
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.maximum_pdu_size = 54321
        ae.add_supported_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)

        scu_ae = AE()
        scu_ae.acse_timeout = 5
        scu_ae.dimse_timeout = 5
        scu_ae.network_timeout = 5
        scu_ae.add_requested_context(VerificationSOPClass)
        assoc = scu_ae.associate('localhost', 11112, max_pdu=12345)
        assert assoc.is_established

        assert scp.active_associations[0].acceptor.maximum_length == (
            54321
        )
        assert scp.active_associations[0].requestor.maximum_length == (
            12345
        )
        assert assoc.requestor.maximum_length == 12345
        assert assoc.acceptor.maximum_length == 54321
        assoc.release()

        time.sleep(0.1)
        assert scp.active_associations == []

        # Check 0 max pdu value - max PDU value maps to 0x10000 internally
        assoc = scu_ae.associate('localhost', 11112, max_pdu=0)
        assert assoc.requestor.maximum_length == 0
        assert scp.active_associations[0].requestor.maximum_length == 0

        assoc.release()

        scp.shutdown()

    def test_association_timeouts(self):
        """ Check that the Association timeouts are being set correctly and
        work """

        DELAY = []

        def handle(event):
            if DELAY:
                time.sleep(DELAY[0])

            return 0x0000

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 0.5
        ae.add_supported_context(VerificationSOPClass)
        scp = ae.start_server(
            ('', 11112), block=False, evt_handlers=[(evt.EVT_C_ECHO, handle)]
        )

        scu_ae = AE()
        scu_ae.acse_timeout = 30
        scu_ae.dimse_timeout = 30
        scu_ae.network_timeout = 30
        scu_ae.add_requested_context(VerificationSOPClass)
        assoc = scu_ae.associate('localhost', 11112)
        assert assoc.is_established

        # Hit the network timeout
        time.sleep(1.0)
        assert assoc.is_aborted
        assert len(scp.active_associations) == 0

        ae.acse_timeout = None
        ae.dimse_timeout = None
        ae.network_timeout = None

        scu_ae.acse_timeout = 30
        scu_ae.dimse_timeout = 0

        DELAY.append(1)

        assoc = scu_ae.associate('localhost', 11112)
        assert assoc.is_established
        status = assoc.send_c_echo()
        time.sleep(1.5)
        assert assoc.is_aborted
        assert len(scp.active_associations) == 0

        scu_ae.acse_timeout = 0
        scu_ae.dimse_timeout = 30

        assoc = scu_ae.associate('localhost', 11112)
        assert not assoc.is_established
        assert len(scp.active_associations) == 0

        ae.acse_timeout = 21
        ae.dimse_timeout = 22
        scu_ae.acse_timeout = 31
        scu_ae.dimse_timeout = 32

        assoc = scu_ae.associate('localhost', 11112)
        assert assoc.is_established

        assert scp.active_associations[0].acse_timeout == 21
        assert scp.active_associations[0].dimse_timeout == 22
        assert assoc.acse_timeout == 31
        assert assoc.dimse_timeout == 32

        assoc.release()

        scp.shutdown()

    def test_select_timeout_okay(self):
        """Test that using start works OK with timeout."""
        # Multiple release/association in a sort time causes an OSError as
        # the port is still in use due to the use of select.select() with
        # a timeout. Fixed by using socket.shutdown in stop()
        for ii in range(3):
            self.ae = ae = AE()
            ae.acse_timeout = 5
            ae.dimse_timeout = 5
            ae.network_timeout = 5
            ae.add_supported_context(VerificationSOPClass)
            scp = ae.start_server(('', 11112), block=False)

            ae.add_requested_context(VerificationSOPClass)
            assoc = ae.associate('localhost', 11112)
            assert assoc.is_established
            assoc.release()
            assert assoc.is_released
            assert not assoc.is_established

            scp.shutdown()


class TestAEBadAssociation(object):
    def test_raise(self):
        """Test bad associate call"""
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)

        with pytest.raises(TypeError):
            ae.associate(1112, 11112)
        with pytest.raises(TypeError):
            ae.associate('localhost', '1.2.3.4')


class TestAEGoodMiscSetters(object):
    def setup(self):
        self.ae = None

    def teardown(self):
        if self.ae:
            self.ae.shutdown()

    def test_ae_title_good(self):
        """ Check AE title change produces good value """
        ae = AE()
        ae.ae_title = '     TEST     '
        assert ae.ae_title == b'TEST            '
        ae.ae_title = '            TEST'
        assert ae.ae_title == b'TEST            '
        ae.ae_title = '                 TEST'
        assert ae.ae_title == b'TEST            '
        ae.ae_title = 'a            TEST'
        assert ae.ae_title == b'a            TES'
        ae.ae_title = 'a        TEST'
        assert ae.ae_title == b'a        TEST   '

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
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)

        ae.add_requested_context(VerificationSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established

        ae.require_calling_aet = [b'MYAE']
        assert ae.require_calling_aet == [b'MYAE            ']
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_rejected

        ae.require_calling_aet = [b'PYNETDICOM      ']
        assert ae.require_calling_aet == [b'PYNETDICOM      ']
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assoc.release()

        with pytest.raises(ValueError, match=r"entirely of only spaces"):
            ae.require_calling_aet = [b'']
        assert ae.require_calling_aet == [b'PYNETDICOM      ']
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assoc.release()

        scp.shutdown()

    def test_require_called_aet(self):
        """Test AE.require_called_aet"""
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)

        ae.add_requested_context(VerificationSOPClass)
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established

        ae.require_called_aet = True
        assert ae.require_called_aet is True
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_rejected

        assoc = ae.associate('localhost', 11112, ae_title=b'PYNETDICOM')
        assert assoc.is_established
        assoc.release()

        scp.shutdown()

    def test_req_calling_aet(self):
        """ Check AE require calling aet change produces good value """
        ae = AE()
        ae.require_calling_aet = [b'10', b'asdf']
        assert ae.require_calling_aet == [
            b'10              ',
            b'asdf            '
        ]

    def test_req_called_aet(self):
        """ Check AE require called aet change produces good value """
        ae = AE()
        assert ae.require_called_aet is False
        ae.require_called_aet = True
        assert ae.require_called_aet is True
        ae.require_called_aet = False
        assert ae.require_called_aet is False

    def test_string_output(self):
        """Test string output"""
        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        ae.require_calling_aet = [b'something']
        ae.require_called_aet = True
        assert 'Explicit VR' in ae.__str__()
        assert 'Verification' in ae.__str__()
        assert '0/10' in ae.__str__()
        assert 'something' in ae.__str__()
        assert 'Require called AE title: True' in ae.__str__()
        ae.supported_contexts = StoragePresentationContexts
        assert 'CT Image' in ae.__str__()

        ae = AE()
        ae.add_requested_context(VerificationSOPClass)
        assert 'None' in ae.__str__()

        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)

        ae.add_requested_context(VerificationSOPClass)
        assoc = ae.associate('localhost', 11112)

        assert assoc.is_established
        assert assoc.is_established
        assert 'Explicit VR' in ae.__str__()
        assert 'Peer' in ae.__str__()

        assoc.release()
        assert assoc.is_released
        assert not assoc.is_established

        scp.shutdown()

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
            AE(ae_title=b'                ')

    def test_ae_title_empty_str(self):
        """AE should fail if ae_title is an empty str"""
        with pytest.raises(ValueError):
            AE(ae_title=b'')

    def test_ae_title_invalid_chars(self):
        """ AE should fail if ae_title is not a str """
        with pytest.raises(ValueError):
            AE(ae_title=br'TEST\ME')


class TestAE_GoodExit(object):
    def setup(self):
        """Run prior to each test"""
        self.ae = None

    def teardown(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

    def test_ae_release_assoc(self):
        """ Association releases OK """
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)

        ae.add_requested_context(VerificationSOPClass)

        # Test N associate/release cycles
        for ii in range(5):
            assoc = ae.associate('localhost', 11112)
            assert assoc.is_established
            assoc.release()
            assert not assoc.is_established
            assert not assoc.is_aborted
            assert assoc.is_released
            assert not assoc.is_rejected

        scp.shutdown()

    def test_ae_aborts_assoc(self):
        """ Association aborts OK """
        self.ae = ae = AE()
        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        ae.network_timeout = 5
        ae.add_supported_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False)

        ae.add_requested_context(VerificationSOPClass)

        # Test N associate/abort cycles
        for ii in range(5):
            assoc = ae.associate('localhost', 11112)
            assert assoc.is_established
            assoc.abort()
            assert not assoc.is_established
            assert assoc.is_aborted
            assert not assoc.is_released
            assert not assoc.is_rejected

        scp.shutdown()


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
        assert len(context.transfer_syntax) == 4

        self.ae.remove_supported_context('1.2.840.10008.1.1')
        assert len(self.ae.supported_contexts) == 0

    def test_remove_supported_context_single_transfer(self):
        """Tests for AE.remove_supported_context with single transfer."""
        self.ae.add_supported_context('1.2.840.10008.1.1')

        context = self.ae.supported_contexts[0]
        assert context.abstract_syntax == '1.2.840.10008.1.1'
        assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
        assert len(context.transfer_syntax) == 4

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
        assert len(context.transfer_syntax) == 4

        self.ae.remove_supported_context('1.2.840.10008.1.1',
                                         ['1.2.840.10008.1.2'])
        assert len(self.ae.supported_contexts) == 1
        context = self.ae.supported_contexts[0]
        assert len(context.transfer_syntax) == 3
        assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES[1:]
        assert context.abstract_syntax == '1.2.840.10008.1.1'

        # Test multiple
        self.ae.add_supported_context('1.2.840.10008.1.1')
        self.ae.add_supported_context(RTImageStorage)

        self.ae.remove_supported_context('1.2.840.10008.1.1',
                                         ['1.2.840.10008.1.2'])
        assert len(self.ae.supported_contexts) == 2
        context = self.ae.supported_contexts[0]
        assert len(context.transfer_syntax) == 3
        assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES[1:]
        assert context.abstract_syntax == '1.2.840.10008.1.1'

        assert self.ae.supported_contexts[1].transfer_syntax == DEFAULT_TRANSFER_SYNTAXES

    def test_remove_supported_context_all(self):
        """Tests for AE.remove_supported_context with all transfers."""
        self.ae.add_supported_context('1.2.840.10008.1.1')

        context = self.ae.supported_contexts[0]
        assert context.abstract_syntax == '1.2.840.10008.1.1'
        assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
        assert len(context.transfer_syntax) == 4

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
        assert len(context.transfer_syntax) == 4

        self.ae.remove_supported_context('1.2.840.10008.1.1', tsyntax)
        assert len(self.ae.supported_contexts) == 0

    def test_scu_role(self):
        """Test add_supported_context with scu_role parameter."""
        self.ae.add_supported_context('1.2.3')
        context = self.ae.supported_contexts[0]
        assert context.scu_role is None
        assert context.scp_role is None

        self.ae.supported_context = []
        self.ae.add_supported_context('1.2.3', scu_role=None)
        context = self.ae.supported_contexts[0]
        assert context.scu_role is None
        assert context.scp_role is None

        self.ae.supported_context = []
        self.ae.add_supported_context('1.2.3', scu_role=True)
        context = self.ae.supported_contexts[0]
        assert context.scu_role is True
        assert context.scp_role is None

        self.ae.supported_context = []
        self.ae.add_supported_context('1.2.3', scu_role=False)
        context = self.ae.supported_contexts[0]
        assert context.scu_role is False
        assert context.scp_role is None

    def test_scu_role_update(self):
        """Test updating add_supported_context with scu_role parameter."""
        self.ae.add_supported_context('1.2.3')
        context = self.ae.supported_contexts[0]
        assert context.scu_role is None
        assert context.scp_role is None

        self.ae.add_supported_context('1.2.3', scu_role=None)
        context = self.ae.supported_contexts[0]
        assert context.scu_role is None
        assert context.scp_role is None

        self.ae.add_supported_context('1.2.3', scu_role=True)
        context = self.ae.supported_contexts[0]
        assert context.scu_role is True
        assert context.scp_role is None

        self.ae.add_supported_context('1.2.3', scu_role=False)
        context = self.ae.supported_contexts[0]
        assert context.scu_role is False
        assert context.scp_role is None

    def test_scu_role_raises(self):
        """Test add_supported_context raises if scu_role wrong type."""
        with pytest.raises(TypeError, match=""):
            self.ae.add_supported_context('1.2.3', scu_role='abc')

        assert self.ae.supported_contexts == []

    def test_scp_role(self):
        """Test add_supported_context with scu_role parameter."""
        self.ae.add_supported_context('1.2.3')
        context = self.ae.supported_contexts[0]
        assert context.scu_role is None
        assert context.scp_role is None

        self.ae.supported_context = []
        self.ae.add_supported_context('1.2.3', scp_role=None)
        context = self.ae.supported_contexts[0]
        assert context.scu_role is None
        assert context.scp_role is None

        self.ae.supported_context = []
        self.ae.add_supported_context('1.2.3', scp_role=True)
        context = self.ae.supported_contexts[0]
        assert context.scu_role is None
        assert context.scp_role is True

        self.ae.supported_context = []
        self.ae.add_supported_context('1.2.3', scp_role=False)
        context = self.ae.supported_contexts[0]
        assert context.scu_role is None
        assert context.scp_role is False

    def test_scp_role_update(self):
        """Test updating add_supported_context with scp_role parameter."""
        self.ae.add_supported_context('1.2.3')
        context = self.ae.supported_contexts[0]
        assert context.scu_role is None
        assert context.scp_role is None

        self.ae.add_supported_context('1.2.3', scp_role=None)
        context = self.ae.supported_contexts[0]
        assert context.scu_role is None
        assert context.scp_role is None

        self.ae.add_supported_context('1.2.3', scp_role=True)
        context = self.ae.supported_contexts[0]
        assert context.scu_role is None
        assert context.scp_role is True

        self.ae.add_supported_context('1.2.3', scp_role=False)
        context = self.ae.supported_contexts[0]
        assert context.scu_role is None
        assert context.scp_role is False

    def test_scp_role_raises(self):
        """Test add_supported_context raises if scp_role wrong type."""
        with pytest.raises(TypeError, match=""):
            self.ae.add_supported_context('1.2.3', scp_role='abc')

        assert self.ae.supported_contexts == []


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
        assert len(context.transfer_syntax) == 4

        self.ae.remove_requested_context('1.2.840.10008.1.1')
        assert len(self.ae.requested_contexts) == 0

    def test_remove_requested_context_single(self):
        """Tests for AE.remove_requested_context with single transfer."""
        self.ae.add_requested_context('1.2.840.10008.1.1')

        context = self.ae.requested_contexts[0]
        assert context.abstract_syntax == '1.2.840.10008.1.1'
        assert context.transfer_syntax == DEFAULT_TRANSFER_SYNTAXES
        assert len(context.transfer_syntax) == 4

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
        assert len(context.transfer_syntax) == 4

        self.ae.remove_requested_context('1.2.840.10008.1.1',
                                         ['1.2.840.10008.1.2'])
        assert len(self.ae.requested_contexts) == 1
        context = self.ae.requested_contexts[0]
        assert len(context.transfer_syntax) == 3
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
        assert len(context.transfer_syntax) == 3
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
        assert len(context.transfer_syntax) == 4

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
        assert len(context.transfer_syntax) == 4

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
