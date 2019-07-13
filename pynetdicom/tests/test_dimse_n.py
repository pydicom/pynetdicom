#!/usr/bin/env python
"""Test DIMSE-N operations."""

try:
    from collections.abc import MutableSequence
except ImportError:
    from collections import MutableSequence
from io import BytesIO
import logging

import pytest

from pydicom.dataset import Dataset
from pydicom.dataelem import DataElement
from pydicom.tag import Tag
from pydicom.uid import UID

from pynetdicom import _config
from pynetdicom.dimse_messages import (
    N_EVENT_REPORT_RQ, N_EVENT_REPORT_RSP, N_GET_RQ, N_GET_RSP,
    N_SET_RQ, N_SET_RSP, N_ACTION_RQ, N_ACTION_RSP, N_CREATE_RQ,
    N_CREATE_RSP, N_DELETE_RQ, N_DELETE_RSP
)
from pynetdicom.dimse_primitives import (
    N_EVENT_REPORT, N_GET, N_SET, N_ACTION, N_CREATE, N_DELETE
)
from pynetdicom.utils import pretty_bytes
from pynetdicom.dsutils import decode, encode
from pynetdicom.utils import validate_ae_title
from .encoded_dimse_n_msg import (
    n_er_rq_cmd, n_er_rq_ds, n_er_rsp_cmd, n_er_rsp_ds,
    n_get_rq_cmd, n_get_rsp_cmd, n_get_rsp_ds,
    n_delete_rq_cmd, n_delete_rsp_cmd,
    n_set_rq_cmd, n_set_rq_ds, n_set_rsp_cmd, n_set_rsp_ds,
    n_action_rq_cmd, n_action_rq_ds, n_action_rsp_cmd, n_action_rsp_ds,
    n_create_rq_cmd, n_create_rq_ds, n_create_rsp_cmd, n_create_rsp_ds
)

LOGGER = logging.getLogger('pynetdicom')
LOGGER.setLevel(logging.CRITICAL)


class TestPrimitive_N_EVENT(object):
    """Test DIMSE N-EVENT-REPORT operations."""
    def setup(self):
        self.default_conformance = _config.ENFORCE_UID_CONFORMANCE

    def teardown(self):
        _config.ENFORCE_UID_CONFORMANCE = self.default_conformance

    def test_assignment(self):
        """ Check assignment works correctly """
        primitive = N_EVENT_REPORT()

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

        # Event Information
        ds = Dataset()
        ds.PatientID = '1234567'
        primitive.EventInformation = BytesIO(encode(ds, True, True))
        ds = decode(primitive.EventInformation, True, True)
        assert ds.PatientID == '1234567'

        # Event Reply
        ds = Dataset()
        ds.PatientID = '123456'
        primitive.EventReply = BytesIO(encode(ds, True, True))
        ds = decode(primitive.EventReply, True, True)
        assert ds.PatientID == '123456'

        # Event Type ID
        primitive.EventTypeID = 0x0000
        assert primitive.EventTypeID == 0x0000

        # MessageID
        primitive.MessageID = 11
        assert 11 == primitive.MessageID

        # MessageIDBeingRespondedTo
        primitive.MessageIDBeingRespondedTo = 13
        assert 13 == primitive.MessageIDBeingRespondedTo

        # Status
        primitive.Status = 0x0000
        assert primitive.Status == 0x0000

    def test_uid_exceptions_false(self):
        """Test ValueError raised with ENFORCE_UID_CONFORMANCE = False."""
        primitive = N_EVENT_REPORT()

        _config.ENFORCE_UID_CONFORMANCE = False

        primitive.AffectedSOPClassUID = 'abc'
        assert primitive.AffectedSOPClassUID == 'abc'
        primitive.AffectedSOPInstanceUID = 'abc'
        assert primitive.AffectedSOPInstanceUID == 'abc'

        # Can't have more than 64 characters
        with pytest.raises(ValueError):
            primitive.AffectedSOPClassUID = 'abc' * 22

        with pytest.raises(ValueError):
            primitive.AffectedSOPInstanceUID = 'abc' * 22

    def test_uid_exceptions_true(self):
        """Test ValueError raised with ENFORCE_UID_CONFORMANCE = True."""
        primitive = N_EVENT_REPORT()
        _config.ENFORCE_UID_CONFORMANCE = True

        with pytest.raises(ValueError):
            primitive.AffectedSOPClassUID = 'abc'

        with pytest.raises(ValueError):
            primitive.AffectedSOPInstanceUID = 'abc'

    def test_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        primitive = N_EVENT_REPORT()

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

        # AffectedSOPInstanceUID
        with pytest.raises(TypeError):
            primitive.AffectedSOPInstanceUID = 45.2

        with pytest.raises(TypeError):
            primitive.AffectedSOPInstanceUID = 100

        # EventInformation
        msg = r"'EventInformation' parameter must be a BytesIO object"
        with pytest.raises(TypeError, match=msg):
            primitive.EventInformation = 'halp'

        with pytest.raises(TypeError):
            primitive.EventInformation = 1.111

        with pytest.raises(TypeError):
            primitive.EventInformation = 50

        with pytest.raises(TypeError):
            primitive.EventInformation = [30, 10]

        # EventReply
        msg = r"'EventReply' parameter must be a BytesIO object"
        with pytest.raises(TypeError, match=msg):
            primitive.EventReply = 'halp'

        with pytest.raises(TypeError):
            primitive.EventReply = 1.111

        with pytest.raises(TypeError):
            primitive.EventReply = 50

        with pytest.raises(TypeError):
            primitive.EventReply = [30, 10]

        # EventTypeID
        with pytest.raises(TypeError):
            primitive.EventTypeID = 19.4

        # Status
        with pytest.raises(TypeError):
            primitive.Status = 19.4

    def test_conversion_rq(self):
        """ Check conversion to a -RQ PDU produces the correct output """
        primitive = N_EVENT_REPORT()
        primitive.MessageID = 7
        primitive.AffectedSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
        primitive.AffectedSOPInstanceUID = '1.2.392.200036.9116.2.6.1.48'
        primitive.EventTypeID = 2

        ds = Dataset()
        ds.PatientID = 'Test1101'
        ds.PatientName = "Tube HeNe"

        primitive.EventInformation = BytesIO(encode(ds, True, True))

        dimse_msg = N_EVENT_REPORT_RQ()
        dimse_msg.primitive_to_message(primitive)

        pdvs = []
        for fragment in dimse_msg.encode_msg(1, 16382):
            pdvs.append(fragment)

        assert len(pdvs) == 2
        cs_pdv = pdvs[0].presentation_data_value_list[0][1]
        ds_pdv = pdvs[1].presentation_data_value_list[0][1]

        assert cs_pdv == n_er_rq_cmd
        assert ds_pdv == n_er_rq_ds

    def test_conversion_rsp(self):
        """ Check conversion to a -RSP PDU produces the correct output """
        primitive = N_EVENT_REPORT()
        primitive.MessageIDBeingRespondedTo = 5
        primitive.AffectedSOPClassUID = '1.2.4.10'
        primitive.AffectedSOPInstanceUID = '1.2.4.5.7.8'
        primitive.Status = 0x0000
        primitive.EventTypeID = 2

        ds = Dataset()
        ds.PatientID = 'Test1101'
        ds.PatientName = "Tube HeNe"

        primitive.EventReply = BytesIO(encode(ds, True, True))

        dimse_msg = N_EVENT_REPORT_RSP()
        dimse_msg.primitive_to_message(primitive)

        pdvs = []
        for fragment in dimse_msg.encode_msg(1, 16382):
            pdvs.append(fragment)

        assert len(pdvs) == 2
        cs_pdv = pdvs[0].presentation_data_value_list[0][1]
        ds_pdv = pdvs[1].presentation_data_value_list[0][1]

        assert cs_pdv == n_er_rsp_cmd
        assert ds_pdv == n_er_rsp_ds

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
    def setup(self):
        self.default_conformance = _config.ENFORCE_UID_CONFORMANCE

    def teardown(self):
        _config.ENFORCE_UID_CONFORMANCE = self.default_conformance

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
        ref_ds.PatientID = '1234567'
        primitive.AttributeList = BytesIO(encode(ref_ds, True, True))
        ds = decode(primitive.AttributeList, True, True)
        assert ds.PatientID == '1234567'

        # AttributeIdentifierList
        primitive.AttributeIdentifierList = [0x00001000, (
                                             0x0000, 0x1000),
                                             Tag(0x7fe0, 0x0010)]
        assert [Tag(0x0000,0x1000),
                Tag(0x0000,0x1000),
                Tag(0x7fe0,0x0010)] == primitive.AttributeIdentifierList
        primitive.AttributeIdentifierList = [(0x7fe0, 0x0010)]
        assert [Tag(0x7fe0,0x0010)] == primitive.AttributeIdentifierList
        primitive.AttributeIdentifierList = (0x7fe0, 0x0010)
        assert [Tag(0x7fe0,0x0010)] == primitive.AttributeIdentifierList

        elem = DataElement((0x0000, 0x0005), 'AT', [Tag(0x0000,0x1000)])
        assert isinstance(elem.value, MutableSequence)
        primitive.AttributeIdentifierList = elem.value
        assert [Tag(0x0000, 0x1000)] == primitive.AttributeIdentifierList

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

    def test_uid_exceptions_false(self):
        """Test ValueError raised with ENFORCE_UID_CONFORMANCE = False."""
        primitive = N_GET()

        _config.ENFORCE_UID_CONFORMANCE = False

        primitive.AffectedSOPClassUID = 'abc'
        assert primitive.AffectedSOPClassUID == 'abc'
        primitive.AffectedSOPInstanceUID = 'abc'
        assert primitive.AffectedSOPInstanceUID == 'abc'
        primitive.RequestedSOPClassUID = 'abc'
        assert primitive.RequestedSOPClassUID == 'abc'
        primitive.RequestedSOPInstanceUID = 'abc'
        assert primitive.RequestedSOPInstanceUID == 'abc'

        # Can't have more than 64 characters
        with pytest.raises(ValueError):
            primitive.AffectedSOPClassUID = 'abc' * 22

        with pytest.raises(ValueError):
            primitive.AffectedSOPInstanceUID = 'abc' * 22

        with pytest.raises(ValueError):
            primitive.RequestedSOPClassUID = 'abc' * 22

        with pytest.raises(ValueError):
            primitive.RequestedSOPInstanceUID = 'abc' * 22

    def test_uid_exceptions_true(self):
        """Test ValueError raised with ENFORCE_UID_CONFORMANCE = True."""
        primitive = N_GET()
        _config.ENFORCE_UID_CONFORMANCE = True

        with pytest.raises(ValueError):
            primitive.AffectedSOPClassUID = 'abc'

        with pytest.raises(ValueError):
            primitive.AffectedSOPInstanceUID = 'abc'

        with pytest.raises(ValueError):
            primitive.RequestedSOPClassUID = 'abc'

        with pytest.raises(ValueError):
            primitive.RequestedSOPInstanceUID = 'abc'

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

        # AffectedSOPInstanceUID
        with pytest.raises(TypeError):
            primitive.AffectedSOPInstanceUID = 45.2

        with pytest.raises(TypeError):
            primitive.AffectedSOPInstanceUID = 100

        # RequestedSOPClassUID
        with pytest.raises(TypeError):
            primitive.RequestedSOPClassUID = 45.2

        with pytest.raises(TypeError):
            primitive.RequestedSOPClassUID = 100

        # RequestedSOPInstanceUID
        with pytest.raises(TypeError):
            primitive.RequestedSOPInstanceUID = 45.2

        with pytest.raises(TypeError):
            primitive.RequestedSOPInstanceUID = 100

        # AttributeIdentifierList
        with pytest.raises(ValueError):
            primitive.AttributeIdentifierList = 'ijk'

        with pytest.raises(ValueError, match="Attribute Identifier List must"):
            primitive.AttributeIdentifierList = ['ijk', 'abc']

        # AttributeList
        msg = r"'AttributeList' parameter must be a BytesIO object"
        with pytest.raises(TypeError, match=msg):
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
    def setup(self):
        self.default_conformance = _config.ENFORCE_UID_CONFORMANCE

    def teardown(self):
        _config.ENFORCE_UID_CONFORMANCE = self.default_conformance

    def test_assignment(self):
        """ Check assignment works correctly """
        primitive = N_SET()

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
        ref_ds.PatientID = '1234567'
        primitive.AttributeList = BytesIO(encode(ref_ds, True, True))
        ds = decode(primitive.AttributeList, True, True)
        assert ds.PatientID == '1234567'

        #ModificationList
        ref_ds = Dataset()
        ref_ds.PatientID = '123456'
        primitive.ModificationList = BytesIO(encode(ref_ds, True, True))
        ds = decode(primitive.ModificationList, True, True)
        assert ds.PatientID == '123456'

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

    def test_uid_exceptions_false(self):
        """Test ValueError raised with ENFORCE_UID_CONFORMANCE = False."""
        primitive = N_SET()

        _config.ENFORCE_UID_CONFORMANCE = False

        primitive.AffectedSOPClassUID = 'abc'
        assert primitive.AffectedSOPClassUID == 'abc'
        primitive.AffectedSOPInstanceUID = 'abc'
        assert primitive.AffectedSOPInstanceUID == 'abc'
        primitive.RequestedSOPClassUID = 'abc'
        assert primitive.RequestedSOPClassUID == 'abc'
        primitive.RequestedSOPInstanceUID = 'abc'
        assert primitive.RequestedSOPInstanceUID == 'abc'

        # Can't have more than 64 characters
        with pytest.raises(ValueError):
            primitive.AffectedSOPClassUID = 'abc' * 22

        with pytest.raises(ValueError):
            primitive.AffectedSOPInstanceUID = 'abc' * 22

        with pytest.raises(ValueError):
            primitive.RequestedSOPClassUID = 'abc' * 22

        with pytest.raises(ValueError):
            primitive.RequestedSOPInstanceUID = 'abc' * 22

    def test_uid_exceptions_true(self):
        """Test ValueError raised with ENFORCE_UID_CONFORMANCE = True."""
        primitive = N_SET()
        _config.ENFORCE_UID_CONFORMANCE = True

        with pytest.raises(ValueError):
            primitive.AffectedSOPClassUID = 'abc'

        with pytest.raises(ValueError):
            primitive.AffectedSOPInstanceUID = 'abc'

        with pytest.raises(ValueError):
            primitive.RequestedSOPClassUID = 'abc'

        with pytest.raises(ValueError):
            primitive.RequestedSOPInstanceUID = 'abc'

    def test_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        primitive = N_SET()

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

        # AffectedSOPInstanceUID
        with pytest.raises(TypeError):
            primitive.AffectedSOPInstanceUID = 45.2

        with pytest.raises(TypeError):
            primitive.AffectedSOPInstanceUID = 100

        # RequestedSOPClassUID
        with pytest.raises(TypeError):
            primitive.RequestedSOPClassUID = 45.2

        with pytest.raises(TypeError):
            primitive.RequestedSOPClassUID = 100

        # RequestedSOPInstanceUID
        with pytest.raises(TypeError):
            primitive.RequestedSOPInstanceUID = 45.2

        with pytest.raises(TypeError):
            primitive.RequestedSOPInstanceUID = 100

        # AttributeList
        msg = r"'AttributeList' parameter must be a BytesIO object"
        with pytest.raises(TypeError, match=msg):
            primitive.AttributeList = 'halp'

        with pytest.raises(TypeError):
            primitive.AttributeList = 1.111

        with pytest.raises(TypeError):
            primitive.AttributeList = 50

        with pytest.raises(TypeError):
            primitive.AttributeList = [30, 10]

        # ModificationList
        msg = r"'ModificationList' parameter must be a BytesIO object"
        with pytest.raises(TypeError, match=msg):
            primitive.ModificationList = 'halp'

        with pytest.raises(TypeError):
            primitive.ModificationList = 1.111

        with pytest.raises(TypeError):
            primitive.ModificationList = 50

        with pytest.raises(TypeError):
            primitive.ModificationList = [30, 10]

        # Status
        with pytest.raises(TypeError):
            primitive.Status = 19.4

    def test_conversion_rq(self):
        """ Check conversion to a -RQ PDU produces the correct output """
        primitive = N_SET()
        primitive.MessageID = 7
        primitive.RequestedSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
        primitive.RequestedSOPInstanceUID = '1.2.392.200036.9116.2.6.1.48'

        ds = Dataset()
        ds.PatientID = 'Test1101'
        ds.PatientName = "Tube HeNe"

        primitive.ModificationList = BytesIO(encode(ds, True, True))

        dimse_msg = N_SET_RQ()
        dimse_msg.primitive_to_message(primitive)

        pdvs = []
        for fragment in dimse_msg.encode_msg(1, 16382):
            pdvs.append(fragment)

        assert len(pdvs) == 2
        cs_pdv = pdvs[0].presentation_data_value_list[0][1]
        ds_pdv = pdvs[1].presentation_data_value_list[0][1]

        assert cs_pdv == n_set_rq_cmd
        assert ds_pdv == n_set_rq_ds

    def test_conversion_rsp(self):
        """ Check conversion to a -RSP PDU produces the correct output """
        primitive = N_SET()
        primitive.MessageIDBeingRespondedTo = 5
        primitive.AffectedSOPClassUID = '1.2.4.10'
        primitive.AffectedSOPInstanceUID = '1.2.4.5.7.8'
        primitive.Status = 0x0000

        ds = Dataset()
        ds.PatientID = 'Test1101'
        ds.PatientName = "Tube HeNe"

        primitive.AttributeList = BytesIO(encode(ds, True, True))

        dimse_msg = N_SET_RSP()
        dimse_msg.primitive_to_message(primitive)

        pdvs = []
        for fragment in dimse_msg.encode_msg(1, 16382):
            pdvs.append(fragment)

        assert len(pdvs) == 2
        cs_pdv = pdvs[0].presentation_data_value_list[0][1]
        ds_pdv = pdvs[1].presentation_data_value_list[0][1]

        assert cs_pdv == n_set_rsp_cmd
        assert ds_pdv == n_set_rsp_ds

    def test_is_valid_request(self):
        """Test N_SET.is_valid_request"""
        primitive = N_SET()
        assert not primitive.is_valid_request
        primitive.MessageID = 1
        assert not primitive.is_valid_request
        primitive.RequestedSOPClassUID = '1.2'
        assert not primitive.is_valid_request
        primitive.RequestedSOPInstanceUID = '1.2.1'
        assert not primitive.is_valid_request
        ds = Dataset()
        ds.PatientID = 'Test1101'
        ds.PatientName = "Tube HeNe"

        primitive.ModificationList = BytesIO(encode(ds, True, True))
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
    def setup(self):
        self.default_conformance = _config.ENFORCE_UID_CONFORMANCE

    def teardown(self):
        _config.ENFORCE_UID_CONFORMANCE = self.default_conformance

    def test_assignment(self):
        """ Check assignment works correctly """
        primitive = N_ACTION()

        # Action Type ID
        primitive.ActionTypeID = 0x0000
        assert primitive.ActionTypeID == 0x0000

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

        # ActionInformation
        ds = Dataset()
        ds.PatientID = '1234567'
        primitive.ActionInformation = BytesIO(encode(ds, True, True))
        ds = decode(primitive.ActionInformation, True, True)
        assert ds.PatientID == '1234567'

        # ActionReply
        ds = Dataset()
        ds.PatientID = '123456'
        primitive.ActionReply = BytesIO(encode(ds, True, True))
        ds = decode(primitive.ActionReply, True, True)
        assert ds.PatientID == '123456'

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

    def test_uid_exceptions_false(self):
        """Test ValueError raised with ENFORCE_UID_CONFORMANCE = False."""
        primitive = N_ACTION()

        _config.ENFORCE_UID_CONFORMANCE = False

        primitive.AffectedSOPClassUID = 'abc'
        assert primitive.AffectedSOPClassUID == 'abc'
        primitive.AffectedSOPInstanceUID = 'abc'
        assert primitive.AffectedSOPInstanceUID == 'abc'
        primitive.RequestedSOPClassUID = 'abc'
        assert primitive.RequestedSOPClassUID == 'abc'
        primitive.RequestedSOPInstanceUID = 'abc'
        assert primitive.RequestedSOPInstanceUID == 'abc'

        # Can't have more than 64 characters
        with pytest.raises(ValueError):
            primitive.AffectedSOPClassUID = 'abc' * 22

        with pytest.raises(ValueError):
            primitive.AffectedSOPInstanceUID = 'abc' * 22

        with pytest.raises(ValueError):
            primitive.RequestedSOPClassUID = 'abc' * 22

        with pytest.raises(ValueError):
            primitive.RequestedSOPInstanceUID = 'abc' * 22

    def test_uid_exceptions_true(self):
        """Test ValueError raised with ENFORCE_UID_CONFORMANCE = True."""
        primitive = N_ACTION()
        _config.ENFORCE_UID_CONFORMANCE = True

        with pytest.raises(ValueError):
            primitive.AffectedSOPClassUID = 'abc'

        with pytest.raises(ValueError):
            primitive.AffectedSOPInstanceUID = 'abc'

        with pytest.raises(ValueError):
            primitive.RequestedSOPClassUID = 'abc'

        with pytest.raises(ValueError):
            primitive.RequestedSOPInstanceUID = 'abc'

    def test_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        primitive = N_ACTION()

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

        # AffectedSOPInstanceUID
        with pytest.raises(TypeError):
            primitive.AffectedSOPInstanceUID = 45.2

        with pytest.raises(TypeError):
            primitive.AffectedSOPInstanceUID = 100

        # RequestedSOPClassUID
        with pytest.raises(TypeError):
            primitive.RequestedSOPClassUID = 45.2

        with pytest.raises(TypeError):
            primitive.RequestedSOPClassUID = 100

        # RequestedSOPInstanceUID
        with pytest.raises(TypeError):
            primitive.RequestedSOPInstanceUID = 45.2

        with pytest.raises(TypeError):
            primitive.RequestedSOPInstanceUID = 100

        # ActionInformation
        msg = r"'ActionInformation' parameter must be a BytesIO object"
        with pytest.raises(TypeError, match=msg):
            primitive.ActionInformation = 'halp'

        with pytest.raises(TypeError):
            primitive.ActionInformation = 1.111

        with pytest.raises(TypeError):
            primitive.ActionInformation = 50

        with pytest.raises(TypeError):
            primitive.ActionInformation = [30, 10]

        # ActionReply
        msg = r"'ActionReply' parameter must be a BytesIO object"
        with pytest.raises(TypeError, match=msg):
            primitive.ActionReply = 'halp'

        with pytest.raises(TypeError):
            primitive.ActionReply = 1.111

        with pytest.raises(TypeError):
            primitive.ActionReply = 50

        with pytest.raises(TypeError):
            primitive.ActionReply = [30, 10]

        # ActionTypeID
        with pytest.raises(TypeError):
            primitive.ActionTypeID = 19.4

        # Status
        with pytest.raises(TypeError):
            primitive.Status = 19.4

    def test_conversion_rq(self):
        """ Check conversion to a -RQ PDU produces the correct output """
        primitive = N_ACTION()
        primitive.MessageID = 7
        primitive.RequestedSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
        primitive.RequestedSOPInstanceUID = '1.2.392.200036.9116.2.6.1.48'
        primitive.ActionTypeID = 1

        ds = Dataset()
        ds.PatientID = 'Test1101'
        ds.PatientName = "Tube HeNe"

        primitive.ActionInformation = BytesIO(encode(ds, True, True))

        dimse_msg = N_ACTION_RQ()
        dimse_msg.primitive_to_message(primitive)

        pdvs = []
        for fragment in dimse_msg.encode_msg(1, 16382):
            pdvs.append(fragment)

        assert len(pdvs) == 2
        cs_pdv = pdvs[0].presentation_data_value_list[0][1]
        ds_pdv = pdvs[1].presentation_data_value_list[0][1]

        assert cs_pdv == n_action_rq_cmd
        assert ds_pdv == n_action_rq_ds

    def test_conversion_rsp(self):
        """ Check conversion to a -RSP PDU produces the correct output """
        primitive = N_ACTION()
        primitive.MessageIDBeingRespondedTo = 5
        primitive.AffectedSOPClassUID = '1.2.4.10'
        primitive.AffectedSOPInstanceUID = '1.2.4.5.7.8'
        primitive.Status = 0x0000
        primitive.ActionTypeID = 1

        ds = Dataset()
        ds.PatientID = 'Test1101'
        ds.PatientName = "Tube HeNe"

        primitive.ActionReply = BytesIO(encode(ds, True, True))

        dimse_msg = N_ACTION_RSP()
        dimse_msg.primitive_to_message(primitive)

        pdvs = []
        for fragment in dimse_msg.encode_msg(1, 16382):
            pdvs.append(fragment)

        assert len(pdvs) == 2
        cs_pdv = pdvs[0].presentation_data_value_list[0][1]
        ds_pdv = pdvs[1].presentation_data_value_list[0][1]

        assert cs_pdv == n_action_rsp_cmd
        assert ds_pdv == n_action_rsp_ds

    def test_is_valid_request(self):
        """Test N_ACTION.is_valid_request"""
        primitive = N_ACTION()
        assert not primitive.is_valid_request
        primitive.MessageID = 1
        assert not primitive.is_valid_request
        primitive.RequestedSOPClassUID = '1.2'
        assert not primitive.is_valid_request
        primitive.RequestedSOPInstanceUID = '1.2.1'
        assert not primitive.is_valid_request
        primitive.ActionTypeID = 4
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
    def setup(self):
        self.default_conformance = _config.ENFORCE_UID_CONFORMANCE

    def teardown(self):
        _config.ENFORCE_UID_CONFORMANCE = self.default_conformance

    def test_assignment(self):
        """ Check assignment works correctly """
        primitive = N_CREATE()

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
        ref_ds.PatientID = '1234567'
        primitive.AttributeList = BytesIO(encode(ref_ds, True, True))
        ds = decode(primitive.AttributeList, True, True)
        assert ds.PatientID == '1234567'

        # MessageID
        primitive.MessageID = 11
        assert 11 == primitive.MessageID

        # MessageIDBeingRespondedTo
        primitive.MessageIDBeingRespondedTo = 13
        assert 13 == primitive.MessageIDBeingRespondedTo

        # Status
        primitive.Status = 0x0000
        assert primitive.Status == 0x0000

    def test_uid_exceptions_false(self):
        """Test ValueError raised with ENFORCE_UID_CONFORMANCE = False."""
        primitive = N_CREATE()

        _config.ENFORCE_UID_CONFORMANCE = False

        primitive.AffectedSOPClassUID = 'abc'
        assert primitive.AffectedSOPClassUID == 'abc'
        primitive.AffectedSOPInstanceUID = 'abc'
        assert primitive.AffectedSOPInstanceUID == 'abc'

        # Can't have more than 64 characters
        with pytest.raises(ValueError):
            primitive.AffectedSOPClassUID = 'abc' * 22

        with pytest.raises(ValueError):
            primitive.AffectedSOPInstanceUID = 'abc' * 22

    def test_uid_exceptions_true(self):
        """Test ValueError raised with ENFORCE_UID_CONFORMANCE = True."""
        primitive = N_CREATE()
        _config.ENFORCE_UID_CONFORMANCE = True

        with pytest.raises(ValueError):
            primitive.AffectedSOPClassUID = 'abc'

        with pytest.raises(ValueError):
            primitive.AffectedSOPInstanceUID = 'abc'

    def test_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        primitive = N_CREATE()

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

        # AffectedSOPInstanceUID
        with pytest.raises(TypeError):
            primitive.AffectedSOPInstanceUID = 45.2

        with pytest.raises(TypeError):
            primitive.AffectedSOPInstanceUID = 100

        # AttributeList
        msg = r"'AttributeList' parameter must be a BytesIO object"
        with pytest.raises(TypeError, match=msg):
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
        """Check conversion to a -RQ PDU produces the correct output."""
        primitive = N_CREATE()
        primitive.MessageID = 7
        primitive.AffectedSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
        primitive.AffectedSOPInstanceUID = '1.2.392.200036.9116.2.6.1.48'

        ds = Dataset()
        ds.PatientID = 'Test1101'
        ds.PatientName = "Tube HeNe"

        primitive.AttributeList = BytesIO(encode(ds, True, True))

        dimse_msg = N_CREATE_RQ()
        dimse_msg.primitive_to_message(primitive)

        pdvs = []
        for fragment in dimse_msg.encode_msg(1, 16382):
            pdvs.append(fragment)

        assert len(pdvs) == 2
        cs_pdv = pdvs[0].presentation_data_value_list[0][1]
        ds_pdv = pdvs[1].presentation_data_value_list[0][1]

        assert cs_pdv == n_create_rq_cmd
        assert ds_pdv == n_create_rq_ds

    def test_conversion_rsp(self):
        """ Check conversion to a -RSP PDU produces the correct output """
        primitive = N_CREATE()
        primitive.MessageIDBeingRespondedTo = 5
        primitive.AffectedSOPClassUID = '1.2.4.10'
        primitive.AffectedSOPInstanceUID = '1.2.4.5.7.8'
        primitive.Status = 0x0000

        ds = Dataset()
        ds.PatientID = 'Test1101'
        ds.PatientName = "Tube HeNe"

        primitive.AttributeList = BytesIO(encode(ds, True, True))

        dimse_msg = N_CREATE_RSP()
        dimse_msg.primitive_to_message(primitive)

        pdvs = []
        for fragment in dimse_msg.encode_msg(1, 16382):
            pdvs.append(fragment)

        assert len(pdvs) == 2
        cs_pdv = pdvs[0].presentation_data_value_list[0][1]
        ds_pdv = pdvs[1].presentation_data_value_list[0][1]

        assert cs_pdv == n_create_rsp_cmd
        assert ds_pdv == n_create_rsp_ds

    def test_is_valid_request(self):
        """Test N_CREATE.is_valid_request"""
        primitive = N_CREATE()
        assert not primitive.is_valid_request
        primitive.MessageID = 1
        assert not primitive.is_valid_request
        primitive.AffectedSOPClassUID = '1.2'
        assert primitive.is_valid_request

    def test_is_valid_response(self):
        """Test N_CREATE.is_valid_response."""
        primitive = N_CREATE()
        assert not primitive.is_valid_response
        primitive.MessageIDBeingRespondedTo = 1
        assert not primitive.is_valid_response
        primitive.Status = 0x0000
        assert primitive.is_valid_response


class TestPrimitive_N_DELETE(object):
    """Test DIMSE N-DELETE operations."""
    def setup(self):
        self.default_conformance = _config.ENFORCE_UID_CONFORMANCE

    def teardown(self):
        _config.ENFORCE_UID_CONFORMANCE = self.default_conformance

    def test_assignment(self):
        """ Check assignment works correctly """
        primitive = N_DELETE()

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

    def test_uid_exceptions_false(self):
        """Test ValueError raised with ENFORCE_UID_CONFORMANCE = False."""
        primitive = N_DELETE()

        _config.ENFORCE_UID_CONFORMANCE = False

        primitive.AffectedSOPClassUID = 'abc'
        assert primitive.AffectedSOPClassUID == 'abc'
        primitive.AffectedSOPInstanceUID = 'abc'
        assert primitive.AffectedSOPInstanceUID == 'abc'
        primitive.RequestedSOPClassUID = 'abc'
        assert primitive.RequestedSOPClassUID == 'abc'
        primitive.RequestedSOPInstanceUID = 'abc'
        assert primitive.RequestedSOPInstanceUID == 'abc'

        # Can't have more than 64 characters
        with pytest.raises(ValueError):
            primitive.AffectedSOPClassUID = 'abc' * 22

        with pytest.raises(ValueError):
            primitive.AffectedSOPInstanceUID = 'abc' * 22

        with pytest.raises(ValueError):
            primitive.RequestedSOPClassUID = 'abc' * 22

        with pytest.raises(ValueError):
            primitive.RequestedSOPInstanceUID = 'abc' * 22

    def test_uid_exceptions_true(self):
        """Test ValueError raised with ENFORCE_UID_CONFORMANCE = True."""
        primitive = N_DELETE()
        _config.ENFORCE_UID_CONFORMANCE = True

        with pytest.raises(ValueError):
            primitive.AffectedSOPClassUID = 'abc'

        with pytest.raises(ValueError):
            primitive.AffectedSOPInstanceUID = 'abc'

        with pytest.raises(ValueError):
            primitive.RequestedSOPClassUID = 'abc'

        with pytest.raises(ValueError):
            primitive.RequestedSOPInstanceUID = 'abc'

    def test_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        primitive = N_DELETE()

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

        # AffectedSOPInstanceUID
        with pytest.raises(TypeError):
            primitive.AffectedSOPInstanceUID = 45.2

        with pytest.raises(TypeError):
            primitive.AffectedSOPInstanceUID = 100

        # RequestedSOPClassUID
        with pytest.raises(TypeError):
            primitive.RequestedSOPClassUID = 45.2

        with pytest.raises(TypeError):
            primitive.RequestedSOPClassUID = 100

        # RequestedSOPInstanceUID
        with pytest.raises(TypeError):
            primitive.RequestedSOPInstanceUID = 45.2

        with pytest.raises(TypeError):
            primitive.RequestedSOPInstanceUID = 100

        # Status
        with pytest.raises(TypeError):
            primitive.Status = 19.4

    def test_conversion_rq(self):
        """ Check conversion to a -RQ PDU produces the correct output """
        primitive = N_DELETE()
        primitive.MessageID = 7
        primitive.RequestedSOPClassUID = '1.2.3'
        primitive.RequestedSOPInstanceUID = '1.2.30'

        dimse_msg = N_DELETE_RQ()
        dimse_msg.primitive_to_message(primitive)

        pdvs = []
        for fragment in dimse_msg.encode_msg(1, 16382):
            pdvs.append(fragment)

        assert len(pdvs) == 1
        cs_pdv = pdvs[0].presentation_data_value_list[0][1]

        assert cs_pdv == n_delete_rq_cmd

    def test_conversion_rsp(self):
        """ Check conversion to a -RSP PDU produces the correct output """
        primitive = N_DELETE()
        primitive.MessageIDBeingRespondedTo = 5
        primitive.AffectedSOPClassUID = '1.2.4.10'
        primitive.AffectedSOPInstanceUID = '1.2.4.5.7.8'
        primitive.Status = 0xC201

        dimse_msg = N_DELETE_RSP()
        dimse_msg.primitive_to_message(primitive)

        pdvs = []
        for fragment in dimse_msg.encode_msg(1, 16382):
            pdvs.append(fragment)

        assert len(pdvs) == 1
        cs_pdv = pdvs[0].presentation_data_value_list[0][1]

        assert cs_pdv == n_delete_rsp_cmd

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
