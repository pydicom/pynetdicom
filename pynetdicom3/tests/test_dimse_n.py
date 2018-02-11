#!/usr/bin/env python
"""Test DIMSE-N operations."""

from io import BytesIO
import logging
import unittest

from pydicom.dataset import Dataset
from pydicom.uid import UID

from pynetdicom3.dimse_messages import N_EVENT_REPORT_RQ, N_EVENT_REPORT_RSP, \
                                      N_GET_RQ, N_GET_RSP, \
                                      N_SET_RQ, N_SET_RSP, \
                                      N_ACTION_RQ, N_ACTION_RSP, \
                                      N_CREATE_RQ, N_CREATE_RSP, \
                                      N_DELETE_RQ, N_DELETE_RSP
from pynetdicom3.dimse_primitives import N_EVENT_REPORT, \
                                        N_GET, \
                                        N_SET, \
                                        N_ACTION, \
                                        N_CREATE, \
                                        N_DELETE
#from pynetdicom3.utils import pretty_bytes
from pynetdicom3.dsutils import encode
from pynetdicom3.utils import validate_ae_title

LOGGER = logging.getLogger('pynetdicom3')
LOGGER.setLevel(logging.CRITICAL)


class TestPrimitive_N_EVENT(unittest.TestCase):
    """Test DIMSE N-EVENT-REPORT operations."""
    def test_assignment(self):
        """ Check assignment works correctly """
        primitive = N_EVENT_REPORT()

    def test_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        primitive = N_EVENT_REPORT()

    def test_conversion_rq(self):
        """ Check conversion to a -RQ PDU produces the correct output """
        primitive = N_EVENT_REPORT()

    def test_conversion_rsp(self):
        """ Check conversion to a -RSP PDU produces the correct output """
        primitive = N_EVENT_REPORT()

    def test_is_valid_request(self):
        """Test N_EVENT_REPORT.is_valid_request"""
        primitive = N_EVENT_REPORT()
        assert not primitive.is_valid_request
        primitive.MessageID = 1
        assert not primitive.is_valid_request
        primitive.AffectedSOPClassUID = '1.2'
        assert not primitive.is_valid_request
        primitive.EventTypeID = 1
        assert not primitive.is_valid_request
        primitive.AffectedSOPInstanceUID = '1.2.1'
        assert primitive.is_valid_request

    def test_is_valid_resposne(self):
        """Test N_EVENT_REPORT.is_valid_response."""
        primitive = N_EVENT_REPORT()
        assert not primitive.is_valid_response
        primitive.MessageIDBeingRespondedTo = 1
        assert not primitive.is_valid_response
        primitive.Status = 0x0000
        assert primitive.is_valid_response


class TestPrimitive_N_GET(unittest.TestCase):
    """Test DIMSE N-GET operations."""
    def test_assignment(self):
        """ Check assignment works correctly """
        primitive = N_GET()

    def test_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        primitive = N_GET()

    def test_conversion_rq(self):
        """ Check conversion to a -RQ PDU produces the correct output """
        primitive = N_GET()

    def test_conversion_rsp(self):
        """ Check conversion to a -RSP PDU produces the correct output """
        primitive = N_GET()

    def test_is_valid_request(self):
        """Test N_GET.is_valid_request"""
        primitive = N_GET()
        assert not primitive.is_valid_request
        primitive.MessageID = 1
        assert not primitive.is_valid_request
        primitive.RequestedSOPClassUID = '1.2'
        assert not primitive.is_valid_request
        primitive.RequestedSOPInstanceUID = '1.2.1'
        assert primitive.is_valid_request

    def test_is_valid_resposne(self):
        """Test N_GET.is_valid_response."""
        primitive = N_GET()
        assert not primitive.is_valid_response
        primitive.MessageIDBeingRespondedTo = 1
        assert not primitive.is_valid_response
        primitive.Status = 0x0000
        assert primitive.is_valid_response


class TestPrimitive_N_SET(unittest.TestCase):
    """Test DIMSE N-SET operations."""
    def test_assignment(self):
        """ Check assignment works correctly """
        primitive = N_SET()

    def test_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        primitive = N_SET()

    def test_conversion_rq(self):
        """ Check conversion to a -RQ PDU produces the correct output """
        primitive = N_SET()

    def test_conversion_rsp(self):
        """ Check conversion to a -RSP PDU produces the correct output """
        primitive = N_SET()

    def test_is_valid_request(self):
        """Test N_SET.is_valid_request"""
        primitive = N_SET()
        assert not primitive.is_valid_request
        primitive.MessageID = 1
        assert not primitive.is_valid_request
        primitive.RequestedSOPClassUID = '1.2'
        assert not primitive.is_valid_request
        primitive.RequestedSOPInstanceUID = '1.2.1'
        assert primitive.is_valid_request

    def test_is_valid_resposne(self):
        """Test N_SET.is_valid_response."""
        primitive = N_SET()
        assert not primitive.is_valid_response
        primitive.MessageIDBeingRespondedTo = 1
        assert not primitive.is_valid_response
        primitive.Status = 0x0000
        assert primitive.is_valid_response


class TestPrimitive_N_ACTION(unittest.TestCase):
    """Test DIMSE N-ACTION operations."""
    def test_assignment(self):
        """ Check assignment works correctly """
        primitive = N_ACTION()

    def test_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        primitive = N_ACTION()

    def test_conversion_rq(self):
        """ Check conversion to a -RQ PDU produces the correct output """
        primitive = N_ACTION()

    def test_conversion_rsp(self):
        """ Check conversion to a -RSP PDU produces the correct output """
        primitive = N_ACTION()

    def test_is_valid_request(self):
        """Test N_ACTION.is_valid_request"""
        primitive = N_ACTION()
        assert not primitive.is_valid_request
        primitive.MessageID = 1
        assert not primitive.is_valid_request
        primitive.RequestedSOPClassUID = '1.2'
        assert not primitive.is_valid_request
        primitive.RequestedSOPInstanceUID = '1.2.1'
        assert primitive.is_valid_request

    def test_is_valid_resposne(self):
        """Test N_ACTION.is_valid_response."""
        primitive = N_ACTION()
        assert not primitive.is_valid_response
        primitive.MessageIDBeingRespondedTo = 1
        assert not primitive.is_valid_response
        primitive.Status = 0x0000
        assert primitive.is_valid_response


class TestPrimitive_N_CREATE(unittest.TestCase):
    """Test DIMSE N-CREATE operations."""
    def test_assignment(self):
        """ Check assignment works correctly """
        primitive = N_CREATE()

    def test_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        primitive = N_CREATE()

    def test_conversion_rq(self):
        """ Check conversion to a -RQ PDU produces the correct output """
        primitive = N_CREATE()

    def test_conversion_rsp(self):
        """ Check conversion to a -RSP PDU produces the correct output """
        primitive = N_CREATE()

    def test_is_valid_request(self):
        """Test N_CREATE.is_valid_request"""
        primitive = N_CREATE()
        assert not primitive.is_valid_request
        primitive.MessageID = 1
        assert not primitive.is_valid_request
        primitive.AffectedSOPClassUID = '1.2'
        assert primitive.is_valid_request

    def test_is_valid_resposne(self):
        """Test N_CREATE.is_valid_response."""
        primitive = N_CREATE()
        assert not primitive.is_valid_response
        primitive.MessageIDBeingRespondedTo = 1
        assert not primitive.is_valid_response
        primitive.Status = 0x0000
        assert primitive.is_valid_response


class TestPrimitive_N_DELETE(unittest.TestCase):
    """Test DIMSE N-DELETE operations."""
    def test_assignment(self):
        """ Check assignment works correctly """
        primitive = N_DELETE()

    def test_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        primitive = N_DELETE()

    def test_conversion_rq(self):
        """ Check conversion to a -RQ PDU produces the correct output """
        primitive = N_DELETE()

    def test_conversion_rsp(self):
        """ Check conversion to a -RSP PDU produces the correct output """
        primitive = N_DELETE()

    def test_is_valid_request(self):
        """Test N_DELETE.is_valid_request"""
        primitive = N_DELETE()
        assert not primitive.is_valid_request
        primitive.MessageID = 1
        assert not primitive.is_valid_request
        primitive.RequestedSOPClassUID = '1.2'
        assert not primitive.is_valid_request
        primitive.RequestedSOPInstanceUID = '1.2.1'
        assert primitive.is_valid_request

    def test_is_valid_resposne(self):
        """Test N_DELETE.is_valid_response."""
        primitive = N_DELETE()
        assert not primitive.is_valid_response
        primitive.MessageIDBeingRespondedTo = 1
        assert not primitive.is_valid_response
        primitive.Status = 0x0000
        assert primitive.is_valid_response
