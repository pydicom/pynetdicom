"""Tests for the SubstanceAdministrationQueryServiceClass."""

from io import BytesIO
import time

import pytest

from pydicom.dataset import Dataset
from pydicom.uid import ExplicitVRLittleEndian

from pynetdicom import AE, evt, debug_logger, register_uid, sop_class
from pynetdicom.dimse_primitives import C_FIND
from pynetdicom.presentation import PresentationContext
from pynetdicom.service_class import (
    SubstanceAdministrationQueryServiceClass,
)
from pynetdicom.sop_class import (
    ProductCharacteristicsQuery,
    _SUBSTANCE_ADMINISTRATION_CLASSES,
)


# debug_logger()


def test_unknown_sop_class():
    """Test that starting the QR SCP with an unknown SOP Class raises"""
    service = SubstanceAdministrationQueryServiceClass(None)
    context = PresentationContext()
    context.abstract_syntax = "1.2.3.4"
    context.add_transfer_syntax("1.2")
    msg = (
        r"The supplied abstract syntax is not valid for use with the "
        r"Substance Administration Query Service Class"
    )
    with pytest.raises(ValueError, match=msg):
        service.SCP(C_FIND(), context)


@pytest.fixture()
def register_new_uid():
    register_uid(
        "1.2.3.4",
        "NewFind",
        SubstanceAdministrationQueryServiceClass,
        "C-FIND",
    )
    yield
    del _SUBSTANCE_ADMINISTRATION_CLASSES["NewFind"]
    delattr(sop_class, "NewFind")
    SubstanceAdministrationQueryServiceClass._SUPPORTED_UIDS["C-FIND"].remove("1.2.3.4")


class TestSubstanceAdministrationQueryServiceClass:
    """Test the SubstanceAdministrationQueryServiceClass.

    Subclass of QR Find Service class with its own statuses.
    """

    def setup_method(self):
        """Run prior to each test"""
        self.query = Dataset()
        self.query.QueryRetrieveLevel = "PATIENT"
        self.query.PatientName = "*"

        self.ae = None

    def teardown_method(self):
        """Clear any active threads"""
        if self.ae:
            self.ae.shutdown()

    def test_handler_status_dataset(self):
        """Test handler yielding a Dataset status"""

        def handle(event):
            status = Dataset()
            status.Status = 0xFF00
            yield status, self.query
            yield 0x0000, None

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ProductCharacteristicsQuery)
        ae.add_requested_context(ProductCharacteristicsQuery, ExplicitVRLittleEndian)
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, ProductCharacteristicsQuery)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        status, identifier = next(result)
        assert status.Status == 0x0000
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released

        scp.shutdown()

    def test_handler_status_dataset_multi(self):
        """Test handler yielding a Dataset status with other elements"""

        def handle(event):
            status = Dataset()
            status.Status = 0xFF00
            status.ErrorComment = "Test"
            status.OffendingElement = 0x00010001
            yield status, self.query

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ProductCharacteristicsQuery)
        ae.add_requested_context(ProductCharacteristicsQuery, ExplicitVRLittleEndian)
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, ProductCharacteristicsQuery)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        assert status.ErrorComment == "Test"
        assert status.OffendingElement == 0x00010001
        status, identifier = next(result)
        assert status.Status == 0x0000
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_handler_status_int(self):
        """Test handler yielding an int status"""

        def handle(event):
            yield 0xFF00, self.query

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ProductCharacteristicsQuery)
        ae.add_requested_context(ProductCharacteristicsQuery, ExplicitVRLittleEndian)
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, ProductCharacteristicsQuery)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        status, identifier = next(result)
        assert status.Status == 0x0000
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_handler_status_unknown(self):
        """Test SCP handles handler yielding a unknown status"""

        def handle(event):
            yield 0xFFF0, None

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ProductCharacteristicsQuery)
        ae.add_requested_context(ProductCharacteristicsQuery, ExplicitVRLittleEndian)
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, ProductCharacteristicsQuery)
        status, identifier = next(result)
        assert status.Status == 0xFFF0
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_handler_status_invalid(self):
        """Test SCP handles handler yielding a invalid status"""

        def handle(event):
            yield "Failure", None

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ProductCharacteristicsQuery)
        ae.add_requested_context(ProductCharacteristicsQuery, ExplicitVRLittleEndian)
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, ProductCharacteristicsQuery)
        status, identifier = next(result)
        assert status.Status == 0xC002
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_handler_status_none(self):
        """Test SCP handles handler not yielding a status"""

        def handle(event):
            yield None, self.query

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(ProductCharacteristicsQuery)
        ae.add_requested_context(ProductCharacteristicsQuery, ExplicitVRLittleEndian)
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)

        ae.acse_timeout = 5
        ae.dimse_timeout = 5
        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, ProductCharacteristicsQuery)
        status, identifier = next(result)
        assert status.Status == 0xC002
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released
        scp.shutdown()

    def test_register(self, register_new_uid):
        """Test handler yielding a Dataset status"""
        from pynetdicom.sop_class import NewFind

        def handle(event):
            status = Dataset()
            status.Status = 0xFF00
            yield status, self.query
            yield 0x0000, None

        handlers = [(evt.EVT_C_FIND, handle)]

        self.ae = ae = AE()
        ae.add_supported_context(NewFind)
        ae.add_requested_context(NewFind, ExplicitVRLittleEndian)
        scp = ae.start_server(("localhost", 11112), block=False, evt_handlers=handlers)

        assoc = ae.associate("localhost", 11112)
        assert assoc.is_established
        result = assoc.send_c_find(self.query, NewFind)
        status, identifier = next(result)
        assert status.Status == 0xFF00
        status, identifier = next(result)
        assert status.Status == 0x0000
        with pytest.raises(StopIteration):
            next(result)

        assoc.release()
        assert assoc.is_released

        scp.shutdown()
