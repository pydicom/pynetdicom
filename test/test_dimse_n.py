#!/usr/bin/env python
"""Test DIMSE-N operations."""

from io import BytesIO
import logging
import unittest

from pydicom.dataset import Dataset
from pydicom.uid import UID

from pynetdicom3.DIMSEmessages import N_EVENT_REPORT_RQ, N_EVENT_REPORT_RSP, \
                                      N_GET_RQ, N_GET_RSP, \
                                      N_SET_RQ, N_SET_RSP, \
                                      N_ACTION_RQ, N_ACTION_RSP, \
                                      N_CREATE_RQ, N_CREATE_RSP, \
                                      N_DELETE_RQ, N_DELETE_RSP
from pynetdicom3.DIMSEparameters import N_EVENT_REPORT_ServiceParameters, \
                                        N_GET_ServiceParameters, \
                                        N_SET_ServiceParameters, \
                                        N_ACTION_ServiceParameters, \
                                        N_CREATE_ServiceParameters, \
                                        N_DELETE_ServiceParameters
#from pynetdicom3.utils import wrap_list
from pynetdicom3.dsutils import encode
from pynetdicom3.utils import validate_ae_title

LOGGER = logging.getLogger('pynetdicom3')
LOGGER.setLevel(logging.CRITICAL)


class TestPrimitive_N_EVENT(unittest.TestCase):
    """Test DIMSE N-EVENT-REPORT operations."""
    def test_assignment(self):
        """ Check assignment works correctly """
        primitive = N_EVENT_REPORT_ServiceParameters()

    def test_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        primitive = N_EVENT_REPORT_ServiceParameters()

    def test_conversion_rq(self):
        """ Check conversion to a -RQ PDU produces the correct output """
        primitive = N_EVENT_REPORT_ServiceParameters()

    def test_conversion_rsp(self):
        """ Check conversion to a -RSP PDU produces the correct output """
        primitive = N_EVENT_REPORT_ServiceParameters()


class TestPrimitive_N_GET(unittest.TestCase):
    """Test DIMSE N-GET operations."""
    def test_assignment(self):
        """ Check assignment works correctly """
        primitive = N_GET_ServiceParameters()

    def test_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        primitive = N_GET_ServiceParameters()

    def test_conversion_rq(self):
        """ Check conversion to a -RQ PDU produces the correct output """
        primitive = N_GET_ServiceParameters()

    def test_conversion_rsp(self):
        """ Check conversion to a -RSP PDU produces the correct output """
        primitive = N_GET_ServiceParameters()


class TestPrimitive_N_SET(unittest.TestCase):
    """Test DIMSE N-SET operations."""
    def test_assignment(self):
        """ Check assignment works correctly """
        primitive = N_SET_ServiceParameters()

    def test_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        primitive = N_SET_ServiceParameters()

    def test_conversion_rq(self):
        """ Check conversion to a -RQ PDU produces the correct output """
        primitive = N_SET_ServiceParameters()

    def test_conversion_rsp(self):
        """ Check conversion to a -RSP PDU produces the correct output """
        primitive = N_SET_ServiceParameters()


class TestPrimitive_N_ACTION(unittest.TestCase):
    """Test DIMSE N-ACTION operations."""
    def test_assignment(self):
        """ Check assignment works correctly """
        primitive = N_ACTION_ServiceParameters()

    def test_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        primitive = N_ACTION_ServiceParameters()

    def test_conversion_rq(self):
        """ Check conversion to a -RQ PDU produces the correct output """
        primitive = N_ACTION_ServiceParameters()

    def test_conversion_rsp(self):
        """ Check conversion to a -RSP PDU produces the correct output """
        primitive = N_ACTION_ServiceParameters()


class TestPrimitive_N_CREATE(unittest.TestCase):
    """Test DIMSE N-CREATE operations."""
    def test_assignment(self):
        """ Check assignment works correctly """
        primitive = N_CREATE_ServiceParameters()

    def test_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        primitive = N_CREATE_ServiceParameters()

    def test_conversion_rq(self):
        """ Check conversion to a -RQ PDU produces the correct output """
        primitive = N_CREATE_ServiceParameters()

    def test_conversion_rsp(self):
        """ Check conversion to a -RSP PDU produces the correct output """
        primitive = N_CREATE_ServiceParameters()


class TestPrimitive_N_DELETE(unittest.TestCase):
    """Test DIMSE N-DELETE operations."""
    def test_assignment(self):
        """ Check assignment works correctly """
        primitive = N_DELETE_ServiceParameters()

    def test_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        primitive = N_DELETE_ServiceParameters()

    def test_conversion_rq(self):
        """ Check conversion to a -RQ PDU produces the correct output """
        primitive = N_DELETE_ServiceParameters()

    def test_conversion_rsp(self):
        """ Check conversion to a -RSP PDU produces the correct output """
        primitive = N_DELETE_ServiceParameters()
