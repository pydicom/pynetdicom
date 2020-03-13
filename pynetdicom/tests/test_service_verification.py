"""Tests for the VerificationServiceClass."""

import logging
import time

import pytest

from pydicom.dataset import Dataset

from pynetdicom import AE, evt, debug_logger
from pynetdicom.dimse_primitives import C_ECHO
from pynetdicom.service_class import VerificationServiceClass
from pynetdicom.sop_class import VerificationSOPClass


#debug_logger()


class TestVerificationServiceClass(object):
    """Test the VerifictionSOPClass"""
    def setup(self):
        """Run prior to each test"""
        self.ae = None

    def teardown(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

    def test_scp_handler_return_dataset(self):
        """Test handler returning a Dataset status"""
        def handle(event):
            status = Dataset()
            status.Status = 0x0001
            return status

        handlers = [(evt.EVT_C_ECHO, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_echo()
        assert rsp.Status == 0x0001
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_scp_handler_return_dataset_no_status(self):
        """Test handler returning a Dataset with no Status elem"""
        def handle(event):
            return Dataset()

        handlers = [(evt.EVT_C_ECHO, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_echo()
        assert rsp.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_scp_handler_return_dataset_multi(self):
        """Test handler returning a Dataset status with other elements"""
        def handle(event):
            status = Dataset()
            status.Status = 0x0001
            status.ErrorComment = 'Test'
            return status

        handlers = [(evt.EVT_C_ECHO, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_echo()
        assert rsp.Status == 0x0001
        assert rsp.ErrorComment == 'Test'
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_scp_handler_return_dataset_unknown(self):
        """Test a status ds with an unknown element."""
        def handle(event):
            status = Dataset()
            status.Status = 0x0001
            status.PatientName = 'test name'
            return status

        handlers = [(evt.EVT_C_ECHO, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_echo()
        assert rsp.Status == 0x0001
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_scp_handler_return_int(self):
        """Test handler returning an int status"""
        def handle(event):
            return 0x0002

        handlers = [(evt.EVT_C_ECHO, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_echo()
        assert rsp.Status == 0x0002
        assert not 'ErrorComment' in rsp
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_scp_handler_return_valid(self):
        """Test handler returning a valid status"""
        def handle(event):
            return 0x0000

        handlers = [(evt.EVT_C_ECHO, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_echo()
        assert rsp.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_scp_handler_no_status(self):
        """Test handler not returning a status"""
        def handle(event):
            return None

        handlers = [(evt.EVT_C_ECHO, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_echo()
        assert rsp.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_scp_handler_exception(self):
        """Test handler raising an exception"""
        def handle(event):
            raise ValueError

        handlers = [(evt.EVT_C_ECHO, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_echo()
        assert rsp.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_scp_handler_context(self):
        """Test handler event's context attribute."""
        attr = {}
        def handle(event):
            attr['assoc'] = event.assoc
            attr['context'] = event.context
            attr['request'] = event.request
            return 0x0000

        handlers = [(evt.EVT_C_ECHO, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_echo()
        assert rsp.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        cx = attr['context']
        assert cx.context_id == 1
        assert cx.abstract_syntax == '1.2.840.10008.1.1'
        assert cx.transfer_syntax == '1.2.840.10008.1.2'

        scp.shutdown()

    def test_scp_handler_assoc(self):
        """Test handler event's assoc attribute."""
        attr = {}
        def handle(event):
            attr['assoc'] = event.assoc
            attr['context'] = event.context
            attr['request'] = event.request
            return 0x0000

        handlers = [(evt.EVT_C_ECHO, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_echo()
        assert rsp.Status == 0x0000

        scp_assoc = attr['assoc']
        assert scp_assoc == scp.active_associations[0]

        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_scp_handler_request(self):
        """Test handler event's request attribute."""
        attr = {}
        def handle(event):
            attr['assoc'] = event.assoc
            attr['context'] = event.context
            attr['request'] = event.request
            return 0x0000

        handlers = [(evt.EVT_C_ECHO, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        rsp = assoc.send_c_echo()
        assert rsp.Status == 0x0000
        assoc.release()
        assert assoc.is_released

        req = attr['request']
        assert req.MessageID == 1
        assert isinstance(req, C_ECHO)

        scp.shutdown()

    def test_abort(self, caplog):
        """Test handler aborting the association"""
        def handle(event):
            event.assoc.abort()
            return 0x0000

        handlers = [(evt.EVT_C_ECHO, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            rsp = assoc.send_c_echo()
            assert rsp == Dataset()
            time.sleep(0.1)

        assert assoc.is_aborted
        scp.shutdown()

        assert "Association Aborted" in caplog.text
        assert "(A-P-ABORT)" not in caplog.text
        assert "Connection closed" not in caplog.text
        assert "DIMSE timeout reached" not in caplog.text

    def test_disconnection(self, caplog):
        """Test peer disconnecting during DIMSE messaging."""
        def handle(event):
            event.assoc.dul.socket.close()
            return 0x0000

        handlers = [(evt.EVT_C_ECHO, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            rsp = assoc.send_c_echo()
            assert rsp == Dataset()
            time.sleep(0.1)

        assert assoc.is_aborted
        scp.shutdown()

        assert "Connection closed" in caplog.text
        assert "Association Aborted (A-P-ABORT)" in caplog.text

    def test_timeout(self, caplog):
        """Test peer timing out during DIMSE messaging."""
        def handle(event):
            time.sleep(0.1)
            return 0x0000

        handlers = [(evt.EVT_C_ECHO, handle)]

        self.ae = ae = AE()
        ae.dimse_timeout = 0.05
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            rsp = assoc.send_c_echo()
        assert rsp == Dataset()

        time.sleep(0.1)
        assert assoc.is_aborted
        scp.shutdown()

        assert "DIMSE timeout reached" in caplog.text
        assert "Aborting Association" in caplog.text

    def test_dimse_network_timeout(self, caplog):
        """Regression test for #460: invalid second abort."""
        def handle(event):
            time.sleep(0.1)
            return 0x0000

        handlers = [(evt.EVT_C_ECHO, handle)]

        self.ae = ae = AE()
        ae.dimse_timeout = 0.05
        ae.network_timeout = 0.05
        ae.add_supported_context(VerificationSOPClass)
        ae.add_requested_context(VerificationSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        with caplog.at_level(logging.DEBUG, logger='pynetdicom'):
            rsp = assoc.send_c_echo()
        assert rsp == Dataset()

        time.sleep(0.1)
        assert assoc.is_aborted
        scp.shutdown()

        assert "Invalid event 'Evt15' for the current state" not in caplog.text
        assert "DIMSE timeout reached" in caplog.text
        assert "Aborting Association" in caplog.text
