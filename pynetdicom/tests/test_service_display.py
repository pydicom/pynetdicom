"""Tests for the Display System Management Service Class."""

import pytest

from pydicom.dataset import Dataset

from pynetdicom import AE, evt
from pynetdicom.dimse_primitives import N_GET
from pynetdicom.sop_class import DisplaySystemSOPClass


class TestDisplayServiceClass(object):
    """Test the DisplaySystemManagementServiceClass"""
    def setup(self):
        """Run prior to each test"""
        self.ae = None

        ds = Dataset()
        ds.PatientName = 'Test'
        ds.SOPClassUID = DisplaySystemSOPClass
        ds.SOPInstanceUID = '1.2.3.4'
        self.ds = ds

    def teardown(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

    def test_scp_handler_return_dataset(self):
        """Test handler returning a Dataset status"""
        def handle(event):
            status = Dataset()
            status.Status = 0x0001
            return status, self.ds

        handlers = [(evt.EVT_N_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(DisplaySystemSOPClass)
        ae.add_requested_context(DisplaySystemSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get([(0x7fe0,0x0010)],
                                      DisplaySystemSOPClass,
                                      '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0x0001
        assert ds.PatientName == 'Test'
        assoc.release()
        scp.shutdown()

    def test_scp_handler_return_dataset_multi(self):
        """Test handler returning a Dataset status with other elements"""
        def handle(event):
            status = Dataset()
            status.Status = 0x0001
            status.ErrorComment = 'Test'
            status.OffendingElement = 0x00080010
            status.ErrorID = 12
            return status, self.ds

        handlers = [(evt.EVT_N_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(DisplaySystemSOPClass)
        ae.add_requested_context(DisplaySystemSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get([(0x7fe0,0x0010)],
                                      DisplaySystemSOPClass,
                                      '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0x0001
        assert status.ErrorComment == 'Test'
        assert status.ErrorID == 12
        assert 'OffendingElement' not in status
        assert ds.PatientName == 'Test'
        assoc.release()
        scp.shutdown()

    def test_scp_handler_return_int(self):
        """Test handler returning an int status"""
        def handle(event):
            return 0x0000, self.ds

        handlers = [(evt.EVT_N_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(DisplaySystemSOPClass)
        ae.add_requested_context(DisplaySystemSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get([(0x7fe0,0x0010)],
                                      DisplaySystemSOPClass,
                                      '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0x0000
        assert not 'ErrorComment' in status
        assoc.release()
        scp.shutdown()

    def test_scp_handler_return_unknown(self):
        """Test handler returning a unknown status"""
        def handle(event):
            return 0xFFF0, self.ds

        handlers = [(evt.EVT_N_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(DisplaySystemSOPClass)
        ae.add_requested_context(DisplaySystemSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get([(0x7fe0,0x0010)],
                                      DisplaySystemSOPClass,
                                      '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0xFFF0
        assert ds is None
        assoc.release()
        scp.shutdown()

    def test_scp_handler_no_status(self):
        """Test handler not returning a status"""
        def handle(event):
            return None, self.ds

        handlers = [(evt.EVT_N_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(DisplaySystemSOPClass)
        ae.add_requested_context(DisplaySystemSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get([(0x7fe0,0x0010)],
                                      DisplaySystemSOPClass,
                                      '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0xC002
        assert ds is None
        assoc.release()
        scp.shutdown()

    def test_scp_handler_exception(self):
        """Test handler raising an exception"""
        def handle(event):
            raise ValueError
            return 0xFFF0, self.ds

        handlers = [(evt.EVT_N_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(DisplaySystemSOPClass)
        ae.add_requested_context(DisplaySystemSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get([(0x7fe0,0x0010)],
                                      DisplaySystemSOPClass,
                                      '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0x0110
        assert ds is None
        assoc.release()
        scp.shutdown()

    def test_scp_handler_context(self):
        """Test handler event's context parameter"""
        attrs = {}
        def handle(event):
            attrs['context'] = event.context
            attrs['assoc'] = event.assoc
            attrs['request'] = event.request
            return 0x0000, self.ds

        handlers = [(evt.EVT_N_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(DisplaySystemSOPClass)
        ae.add_requested_context(DisplaySystemSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get([(0x7fe0,0x0010)],
                                      DisplaySystemSOPClass,
                                      '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0x0000
        assert 'PatientName' in ds
        assoc.release()
        assert assoc.is_released

        cx = attrs['context']
        assert cx.context_id == 1
        assert cx.abstract_syntax == DisplaySystemSOPClass
        assert cx.transfer_syntax == '1.2.840.10008.1.2'

        scp.shutdown()

    def test_scp_handler_request(self):
        """Test handler event's request parameter"""
        attrs = {}
        def handle(event):
            attrs['context'] = event.context
            attrs['assoc'] = event.assoc
            attrs['request'] = event.request
            return 0x0000, self.ds

        handlers = [(evt.EVT_N_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(DisplaySystemSOPClass)
        ae.add_requested_context(DisplaySystemSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get([(0x7fe0,0x0010)],
                                      DisplaySystemSOPClass,
                                      '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0x0000
        assert 'PatientName' in ds
        assoc.release()
        assert assoc.is_released

        req = attrs['request']
        assert isinstance(req, N_GET)
        assert req.AttributeIdentifierList == [(0x7fe0,0x0010)]

        scp.shutdown()

    def test_scp_handler_assoc(self):
        """Test handler context parameter"""
        attrs = {}
        def handle(event):
            attrs['context'] = event.context
            attrs['assoc'] = event.assoc
            attrs['request'] = event.request
            return 0x0000, self.ds

        handlers = [(evt.EVT_N_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(DisplaySystemSOPClass)
        ae.add_requested_context(DisplaySystemSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get([(0x7fe0,0x0010)],
                                      DisplaySystemSOPClass,
                                      '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0x0000
        assert 'PatientName' in ds

        scp_assoc = attrs['assoc']
        assert scp_assoc == scp.active_associations[0]

        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_handler_bad_attr(self):
        """Test SCP handles a bad handler attribute list"""
        def handle(event):
            return 0x0000, None

        handlers = [(evt.EVT_N_GET, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(DisplaySystemSOPClass)
        ae.add_requested_context(DisplaySystemSOPClass)
        scp = ae.start_server(('', 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate('localhost', 11112)
        assert assoc.is_established
        status, ds = assoc.send_n_get([(0x7fe0, 0x0010)],
                                      DisplaySystemSOPClass,
                                      '1.2.840.10008.5.1.1.40.1')
        assert status.Status == 0x0110
        assert ds is None

        assoc.release()
        scp.shutdown()
