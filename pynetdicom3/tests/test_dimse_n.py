#!/usr/bin/env python
"""Test DIMSE-N operations."""

from io import BytesIO
import logging

import pytest

from pydicom.dataset import Dataset
from pydicom.tag import Tag
from pydicom.uid import UID

from pynetdicom3.dimse_messages import (
    N_EVENT_REPORT_RQ, N_EVENT_REPORT_RSP, N_GET_RQ, N_GET_RSP,
    N_SET_RQ, N_SET_RSP, N_ACTION_RQ, N_ACTION_RSP, N_CREATE_RQ,
    N_CREATE_RSP, N_DELETE_RQ, N_DELETE_RSP
)
from pynetdicom3.dimse_primitives import (
    N_EVENT_REPORT, N_GET, N_SET, N_ACTION, N_CREATE, N_DELETE
)
from pynetdicom3.utils import pretty_bytes
from pynetdicom3.dsutils import encode
from pynetdicom3.utils import validate_ae_title
from .encoded_dimse_n_msg import (
    n_get_rq_cmd, n_get_rsp_cmd, n_get_rsp_ds
)

LOGGER = logging.getLogger('pynetdicom3')
LOGGER.setLevel(logging.CRITICAL)


class TestPrimitive_N_EVENT(object):
    """Test DIMSE N-EVENT-REPORT operations."""
    def test_assignment(self):
        """ Check assignment works correctly """
        primitive = N_EVENT_REPORT()

        primitive.MessageID = 11
        assert 11 == primitive.MessageID

        primitive.MessageIDBeingRespondedTo = 13
        assert 13 == primitive.MessageIDBeingRespondedTo

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


class TestPrimitive_N_GET(object):
    """Test DIMSE N-GET operations."""
    def test_assignment(self):
        """Check assignment works correctly"""
        primitive = N_GET()

        # AffectedSOPClassUID
        primitive.AffectedSOPClassUID = '1.1.1'
        assert primitive.AffectedSOPClassUID == UID('1.1.1')
        assert isinstance(primitive.AffectedSOPClassUID, UID)
        primitive.AffectedSOPClassUID = UID('1.1.2')
        assert primitive.AffectedSOPClassUID == UID('1.1.2')
        assert isinstance(primitive.AffectedSOPClassUID, UID)
        primitive.AffectedSOPClassUID = b'1.1.3'
        assert primitive.AffectedSOPClassUID == UID('1.1.3')
        assert isinstance(primitive.AffectedSOPClassUID, UID)

        # AffectedSOPInstanceUID
        primitive.AffectedSOPInstanceUID = b'1.2.1'
        assert primitive.AffectedSOPInstanceUID == UID('1.2.1')
        assert isinstance(primitive.AffectedSOPClassUID, UID)
        primitive.AffectedSOPInstanceUID = UID('1.2.2')
        assert primitive.AffectedSOPInstanceUID == UID('1.2.2')
        assert isinstance(primitive.AffectedSOPClassUID, UID)
        primitive.AffectedSOPInstanceUID = '1.2.3'
        assert primitive.AffectedSOPInstanceUID == UID('1.2.3')
        assert isinstance(primitive.AffectedSOPClassUID, UID)

        # AttributeList
        ref_ds = Dataset()
        ref_ds.PatientID = 1234567
        primitive.AttributeList = BytesIO(encode(ref_ds, True, True))

        # AttributeIdentifierList
        primitive.AttributeIdentifierList = [0x00001000, (
                                             0x0000, 0x1000),
                                             Tag(0x7fe0, 0x0010)]
        assert [Tag(0x0000,0x1000),
                Tag(0x0000,0x1000),
                Tag(0x7fe0,0x0010)] == primitive.AttributeIdentifierList


        # MessageID
        primitive.MessageID = 11
        assert 11 == primitive.MessageID

        # MessageIDBeingRespondedTo
        primitive.MessageIDBeingRespondedTo = 13
        assert 13 == primitive.MessageIDBeingRespondedTo

        # RequestedSOPClassUID
        primitive.RequestedSOPClassUID = '1.1.1'
        assert primitive.RequestedSOPClassUID == UID('1.1.1')
        assert isinstance(primitive.RequestedSOPClassUID, UID)
        primitive.RequestedSOPClassUID = UID('1.1.2')
        assert primitive.RequestedSOPClassUID == UID('1.1.2')
        assert isinstance(primitive.RequestedSOPClassUID, UID)
        primitive.RequestedSOPClassUID = b'1.1.3'
        assert primitive.RequestedSOPClassUID == UID('1.1.3')
        assert isinstance(primitive.RequestedSOPClassUID, UID)

        # RequestedSOPInstanceUID
        primitive.RequestedSOPInstanceUID = b'1.2.1'
        assert primitive.RequestedSOPInstanceUID == UID('1.2.1')
        assert isinstance(primitive.RequestedSOPInstanceUID, UID)
        primitive.RequestedSOPInstanceUID = UID('1.2.2')
        assert primitive.RequestedSOPInstanceUID == UID('1.2.2')
        assert isinstance(primitive.RequestedSOPInstanceUID, UID)
        primitive.RequestedSOPInstanceUID = '1.2.3'
        assert primitive.RequestedSOPInstanceUID == UID('1.2.3')
        assert isinstance(primitive.RequestedSOPInstanceUID, UID)

        # Status
        primitive.Status = 0x0000
        assert primitive.Status == 0x0000

    def test_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        primitive = N_GET()

        # MessageID
        with pytest.raises(TypeError):
            primitive.MessageID = 'halp'

        with pytest.raises(TypeError):
            primitive.MessageID = 1.111

        with pytest.raises(ValueError):
            primitive.MessageID = 65536

        with pytest.raises(ValueError):
            primitive.MessageID = -1

        # MessageIDBeingRespondedTo
        with pytest.raises(TypeError):
            primitive.MessageIDBeingRespondedTo = 'halp'

        with pytest.raises(TypeError):
            primitive.MessageIDBeingRespondedTo = 1.111

        with pytest.raises(ValueError):
            primitive.MessageIDBeingRespondedTo = 65536

        with pytest.raises(ValueError):
            primitive.MessageIDBeingRespondedTo = -1

        # AffectedSOPClassUID
        with pytest.raises(TypeError):
            primitive.AffectedSOPClassUID = 45.2

        with pytest.raises(TypeError):
            primitive.AffectedSOPClassUID = 100

        with pytest.raises(ValueError):
            primitive.AffectedSOPClassUID = 'abc'

        # AffectedSOPInstanceUID
        with pytest.raises(TypeError):
            primitive.AffectedSOPInstanceUID = 45.2

        with pytest.raises(TypeError):
            primitive.AffectedSOPInstanceUID = 100

        with pytest.raises(ValueError):
            primitive.AffectedSOPInstanceUID = 'abc'

        # RequestedSOPClassUID
        with pytest.raises(TypeError):
            primitive.RequestedSOPClassUID = 45.2

        with pytest.raises(TypeError):
            primitive.RequestedSOPClassUID = 100

        with pytest.raises(ValueError):
            primitive.RequestedSOPClassUID = 'abc'

        # RequestedSOPInstanceUID
        with pytest.raises(TypeError):
            primitive.RequestedSOPInstanceUID = 45.2

        with pytest.raises(TypeError):
            primitive.RequestedSOPInstanceUID = 100

        with pytest.raises(ValueError):
            primitive.RequestedSOPInstanceUID = 'abc'

        # AttributeIdentifierList
        with pytest.raises(ValueError):
            primitive.AttributeIdentifierList = Tag(0x0000,0x0000)

        with pytest.raises(ValueError, match="Attribute Identifier List must"):
            primitive.AttributeIdentifierList = ['ijk', 'abc']

        # AttributeList
        with pytest.raises(TypeError):
            primitive.AttributeList = 'halp'

        with pytest.raises(TypeError):
            primitive.AttributeList = 1.111

        with pytest.raises(TypeError):
            primitive.AttributeList = 50

        with pytest.raises(TypeError):
            primitive.AttributeList = [30, 10]

        # Status
        with pytest.raises(TypeError):
            primitive.Status = 19.4

    def test_conversion_rq(self):
        """ Check conversion to a -RQ PDU produces the correct output """
        primitive = N_GET()
        primitive.MessageID = 7
        primitive.RequestedSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
        primitive.RequestedSOPInstanceUID = '1.2.392.200036.9116.2.6.1.48'
        primitive.AttributeIdentifierList = [
            (0x7fe0,0x0010), (0x0000,0x0000), (0xFFFF,0xFFFF)
        ]

        dimse_msg = N_GET_RQ()
        dimse_msg.primitive_to_message(primitive)

        pdvs = []
        for fragment in dimse_msg.encode_msg(1, 16382):
            pdvs.append(fragment)

        assert len(pdvs) == 1
        cs_pdv = pdvs[0].presentation_data_value_list[0][1]

        assert cs_pdv == n_get_rq_cmd

    def test_conversion_rsp(self):
        """ Check conversion to a -RSP PDU produces the correct output """
        primitive = N_GET()
        primitive.MessageIDBeingRespondedTo = 5
        primitive.AffectedSOPClassUID = '1.2.4.10'
        primitive.AffectedSOPInstanceUID = '1.2.4.5.7.8'
        primitive.Status = 0x0000

        ds = Dataset()
        ds.PatientID = 'Test1101'
        ds.PatientName = "Tube HeNe"

        primitive.AttributeList = BytesIO(encode(ds, True, True))

        dimse_msg = N_GET_RSP()
        dimse_msg.primitive_to_message(primitive)

        pdvs = []
        for fragment in dimse_msg.encode_msg(1, 16382):
            pdvs.append(fragment)


        for line in pretty_bytes(pdvs[1].presentation_data_value_list[0][1]):
            print(line)

        assert len(pdvs) == 2
        cs_pdv = pdvs[0].presentation_data_value_list[0][1]
        ds_pdv = pdvs[1].presentation_data_value_list[0][1]

        assert cs_pdv == n_get_rsp_cmd
        assert ds_pdv == n_get_rsp_ds

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


class TestPrimitive_N_SET(object):
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


class TestPrimitive_N_ACTION(object):
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


class TestPrimitive_N_CREATE(object):
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


class TestPrimitive_N_DELETE(object):
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
