#!/usr/bin/env python
"""Test DIMSE-C operations."""

from io import BytesIO
import logging

import pytest

from pydicom.dataset import Dataset
from pydicom.uid import UID

from pynetdicom import _config
from pynetdicom.dimse_messages import (
    C_STORE_RQ, C_STORE_RSP,C_MOVE_RQ, C_MOVE_RSP, C_ECHO_RQ, C_ECHO_RSP,
    C_FIND_RQ, C_FIND_RSP, C_GET_RQ, C_GET_RSP
)
from pynetdicom.dimse_primitives import (
    C_ECHO, C_MOVE, C_STORE, C_GET, C_FIND, C_CANCEL
)
from pynetdicom.dsutils import encode
from pynetdicom.utils import validate_ae_title
#from pynetdicom.utils import pretty_bytes
from .encoded_dimse_msg import (
    c_echo_rq_cmd, c_echo_rsp_cmd, c_store_rq_cmd_b, c_store_rq_ds_b,
    c_store_rsp_cmd, c_find_rq_cmd, c_find_rq_ds, c_find_rsp_cmd,
    c_find_rsp_ds, c_get_rq_cmd, c_get_rq_ds, c_get_rsp_cmd, c_get_rsp_ds,
    c_move_rq_cmd, c_move_rq_ds, c_move_rsp_cmd, c_move_rsp_ds
)


LOGGER = logging.getLogger('pynetdicom')
LOGGER.setLevel(logging.CRITICAL)


class TestPrimitive_C_CANCEL(object):
    """Test DIMSE C-CANCEL operations."""
    def test_assignment(self):
        """ Check assignment works correctly """
        primitive = C_CANCEL()

        primitive.MessageIDBeingRespondedTo = 13
        assert primitive.MessageIDBeingRespondedTo == 13
        with pytest.raises(ValueError):
            primitive.MessageIDBeingRespondedTo = 100000
        with pytest.raises(TypeError):
            primitive.MessageIDBeingRespondedTo = 'test'


class TestPrimitive_C_STORE(object):
    """Test DIMSE C-STORE operations."""
    def setup(self):
        self.default_conformance = _config.ENFORCE_UID_CONFORMANCE
        self.default_aet_length = _config.USE_SHORT_DIMSE_AET

    def teardown(self):
        _config.ENFORCE_UID_CONFORMANCE = self.default_conformance
        _config.USE_SHORT_DIMSE_AET = self.default_aet_length

    def test_assignment(self):
        """ Check assignment works correctly """
        primitive = C_STORE()

        primitive.MessageID = 11
        assert primitive.MessageID == 11

        primitive.MessageIDBeingRespondedTo = 13
        assert primitive.MessageIDBeingRespondedTo == 13

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

        primitive.Priority = 0x02
        assert primitive.Priority == 0x02

        primitive.MoveOriginatorApplicationEntityTitle = 'UNITTEST_SCP'
        assert primitive.MoveOriginatorApplicationEntityTitle == b'UNITTEST_SCP'
        primitive.MoveOriginatorApplicationEntityTitle = b'UNITTEST_SCP'
        assert primitive.MoveOriginatorApplicationEntityTitle == b'UNITTEST_SCP'
        primitive.MoveOriginatorApplicationEntityTitle = ''
        assert primitive.MoveOriginatorApplicationEntityTitle is None
        primitive.MoveOriginatorApplicationEntityTitle = b''
        assert primitive.MoveOriginatorApplicationEntityTitle is None
        primitive.MoveOriginatorApplicationEntityTitle = '         '
        assert primitive.MoveOriginatorApplicationEntityTitle is None
        primitive.MoveOriginatorApplicationEntityTitle = b'         '
        assert primitive.MoveOriginatorApplicationEntityTitle is None

        primitive.MoveOriginatorMessageID = 15
        assert primitive.MoveOriginatorMessageID == 15

        ref_ds = Dataset()
        ref_ds.PatientID = 1234567

        primitive.DataSet = BytesIO(encode(ref_ds, True, True))
        #assert primitive.DataSet, ref_ds)

        primitive.Status = 0x0000
        assert primitive.Status == 0x0000

        primitive.Status = 0xC123
        assert primitive.Status == 0xC123

        primitive.Status = 0xEE01
        assert primitive.Status == 0xEE01

    def test_uid_exceptions_false(self):
        """Test ValueError raised with ENFORCE_UID_CONFORMANCE = False."""
        primitive = C_STORE()

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
        primitive = C_STORE()
        _config.ENFORCE_UID_CONFORMANCE = True

        with pytest.raises(ValueError):
            primitive.AffectedSOPClassUID = 'abc'

        with pytest.raises(ValueError):
            primitive.AffectedSOPInstanceUID = 'abc'

    def test_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        primitive = C_STORE()

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

        # Priority
        with pytest.raises(ValueError):
            primitive.Priority = 45.2

        with pytest.raises(ValueError):
            primitive.Priority = 'abc'

        with pytest.raises(ValueError):
            primitive.Priority = -1

        with pytest.raises(ValueError):
            primitive.Priority = 3

        # MoveOriginatorApplicationEntityTitle
        with pytest.raises(TypeError):
            primitive.MoveOriginatorApplicationEntityTitle = 45.2

        with pytest.raises(TypeError):
            primitive.MoveOriginatorApplicationEntityTitle = 100

        primitive.MoveOriginatorApplicationEntityTitle = ''
        assert primitive.MoveOriginatorApplicationEntityTitle is None

        #with pytest.raises(ValueError):
        #    primitive.MoveOriginatorApplicationEntityTitle = '    '

        # MoveOriginatorMessageID
        with pytest.raises(TypeError):
            primitive.MoveOriginatorMessageID = 'halp'

        with pytest.raises(TypeError):
            primitive.MoveOriginatorMessageID = 1.111

        with pytest.raises(ValueError):
            primitive.MoveOriginatorMessageID = 65536

        with pytest.raises(ValueError):
            primitive.MoveOriginatorMessageID = -1

        # DataSet
        msg = r"'DataSet' parameter must be a BytesIO object"
        with pytest.raises(TypeError, match=msg):
            primitive.DataSet = 'halp'

        with pytest.raises(TypeError):
            primitive.DataSet = 1.111

        with pytest.raises(TypeError):
            primitive.DataSet = 50

        with pytest.raises(TypeError):
            primitive.DataSet = [30, 10]

        # Status
        with pytest.raises(TypeError):
            primitive.Status = 19.4

    def test_conversion_rq(self):
        """ Check conversion to a -RQ PDU produces the correct output """
        primitive = C_STORE()
        primitive.MessageID = 7
        primitive.AffectedSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
        primitive.AffectedSOPInstanceUID = '1.2.392.200036.9116.2.6.1.48.' \
                                           '1215709044.1459316254.522441'
        primitive.Priority = 0x02
        primitive.MoveOriginatorApplicationEntityTitle = 'UNITTEST_SCP'
        primitive.MoveOriginatorMessageID = 3

        ref_ds = Dataset()
        ref_ds.PatientID = 'Test1101'
        ref_ds.PatientName = "Tube HeNe"

        primitive.DataSet = BytesIO(encode(ref_ds, True, True))

        dimse_msg = C_STORE_RQ()
        dimse_msg.primitive_to_message(primitive)

        pdvs = []
        for fragment in dimse_msg.encode_msg(1, 16382):
            pdvs.append(fragment)
        cs_pdv = pdvs[0].presentation_data_value_list[0][1]
        ds_pdv = pdvs[1].presentation_data_value_list[0][1]
        assert cs_pdv == c_store_rq_cmd_b
        assert ds_pdv == c_store_rq_ds_b

    def test_conversion_rsp(self):
        """ Check conversion to a -RSP PDU produces the correct output """
        primitive = C_STORE()
        primitive.MessageIDBeingRespondedTo = 5
        primitive.AffectedSOPClassUID = '1.2.4.10'
        primitive.AffectedSOPInstanceUID = '1.2.4.5.7.8'
        primitive.Status = 0x0000

        dimse_msg = C_STORE_RSP()
        dimse_msg.primitive_to_message(primitive)

        pdvs = []
        for fragment in dimse_msg.encode_msg(1, 16382):
            pdvs.append(fragment)
        cs_pdv = pdvs[0].presentation_data_value_list[0][1]
        assert cs_pdv == c_store_rsp_cmd

    def test_is_valid_request(self):
        """Test C_STORE.is_valid_request"""
        primitive = C_STORE()
        assert not primitive.is_valid_request
        primitive.MessageID = 1
        assert not primitive.is_valid_request
        primitive.AffectedSOPClassUID = '1.2'
        assert not primitive.is_valid_request
        primitive.Priority = 2
        assert not primitive.is_valid_request
        primitive.AffectedSOPInstanceUID = '1.2.1'
        assert not primitive.is_valid_request
        primitive.DataSet = BytesIO()
        assert primitive.is_valid_request

    def test_is_valid_resposne(self):
        """Test C_STORE.is_valid_response."""
        primitive = C_STORE()
        assert not primitive.is_valid_response
        primitive.MessageIDBeingRespondedTo = 1
        assert not primitive.is_valid_response
        primitive.Status = 0x0000
        assert primitive.is_valid_response

    def test_aet_short_false(self):
        """Test using long AE titles."""
        primitive = C_STORE()

        _config.USE_SHORT_DIMSE_AET = False

        primitive.MoveOriginatorApplicationEntityTitle = b'A'
        aet = primitive.MoveOriginatorApplicationEntityTitle
        assert b'A               ' == aet

    def test_aet_short_true(self):
        """Test using short AE titles."""
        primitive = C_STORE()

        _config.USE_SHORT_DIMSE_AET = True

        primitive.MoveOriginatorApplicationEntityTitle = b'A'
        aet = primitive.MoveOriginatorApplicationEntityTitle
        assert b'A' == aet

        primitive.MoveOriginatorApplicationEntityTitle = b'ABCDEFGHIJKLMNO'
        aet = primitive.MoveOriginatorApplicationEntityTitle
        assert b'ABCDEFGHIJKLMNO' == aet

        primitive.MoveOriginatorApplicationEntityTitle = b'ABCDEFGHIJKLMNOP'
        aet = primitive.MoveOriginatorApplicationEntityTitle
        assert b'ABCDEFGHIJKLMNOP' == aet

        primitive.MoveOriginatorApplicationEntityTitle = b'ABCDEFGHIJKLMNOPQ'
        aet = primitive.MoveOriginatorApplicationEntityTitle
        assert b'ABCDEFGHIJKLMNOP' == aet


class TestPrimitive_C_FIND(object):
    """Test DIMSE C-FIND operations."""
    def setup(self):
        self.default_conformance = _config.ENFORCE_UID_CONFORMANCE

    def teardown(self):
        _config.ENFORCE_UID_CONFORMANCE = self.default_conformance

    def test_assignment(self):
        """ Check assignment works correctly """
        primitive = C_FIND()

        primitive.MessageID = 11
        assert primitive.MessageID == 11

        primitive.MessageIDBeingRespondedTo = 13
        assert primitive.MessageIDBeingRespondedTo == 13

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

        primitive.Priority = 0x02
        assert primitive.Priority == 0x02

        ref_ds = Dataset()
        ref_ds.PatientID = '*'
        ref_ds.QueryRetrieveLevel = "PATIENT"

        primitive.Identifier = BytesIO(encode(ref_ds, True, True))
        #assert primitive.DataSet, ref_ds)

        primitive.Status = 0x0000
        assert primitive.Status == 0x0000

        primitive.Status = 0xC123
        assert primitive.Status == 0xC123

        primitive.Status = 0xEE01
        assert primitive.Status == 0xEE01

    def test_uid_exceptions_false(self):
        """Test ValueError raised with ENFORCE_UID_CONFORMANCE = False."""
        primitive = C_FIND()

        _config.ENFORCE_UID_CONFORMANCE = False

        primitive.AffectedSOPClassUID = 'abc'
        assert primitive.AffectedSOPClassUID == 'abc'

        # Can't have more than 64 characters
        with pytest.raises(ValueError):
            primitive.AffectedSOPClassUID = 'abc' * 22

    def test_uid_exceptions_true(self):
        """Test ValueError raised with ENFORCE_UID_CONFORMANCE = True."""
        primitive = C_FIND()
        _config.ENFORCE_UID_CONFORMANCE = True

        with pytest.raises(ValueError):
            primitive.AffectedSOPClassUID = 'abc'

    def test_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        primitive = C_FIND()

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

        # Priority
        with pytest.raises(ValueError):
            primitive.Priority = 45.2

        with pytest.raises(ValueError):
            primitive.Priority = 'abc'

        with pytest.raises(ValueError):
            primitive.Priority = -1

        with pytest.raises(ValueError):
            primitive.Priority = 3

        # Identifier
        msg = r"'Identifier' parameter must be a BytesIO object"
        with pytest.raises(TypeError, match=msg):
            primitive.Identifier = 'halp'

        with pytest.raises(TypeError):
            primitive.Identifier = 1.111

        with pytest.raises(TypeError):
            primitive.Identifier = 50

        with pytest.raises(TypeError):
            primitive.Identifier = [30, 10]

        # Status
        with pytest.raises(TypeError):
            primitive.Status = 19.4

    def test_conversion_rq(self):
        """ Check conversion to a -RQ PDU produces the correct output """
        primitive = C_FIND()
        primitive.MessageID = 7
        primitive.AffectedSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
        primitive.Priority = 0x02

        ref_identifier = Dataset()
        ref_identifier.PatientID = '*'
        ref_identifier.QueryRetrieveLevel = "PATIENT"

        primitive.Identifier = BytesIO(encode(ref_identifier, True, True))

        dimse_msg = C_FIND_RQ()
        dimse_msg.primitive_to_message(primitive)

        pdvs = []
        for fragment in dimse_msg.encode_msg(1, 16382):
            pdvs.append(fragment)
        cs_pdv = pdvs[0].presentation_data_value_list[0][1]
        ds_pdv = pdvs[1].presentation_data_value_list[0][1]
        assert cs_pdv == c_find_rq_cmd
        assert ds_pdv == c_find_rq_ds

    def test_conversion_rsp(self):
        """ Check conversion to a -RSP PDU produces the correct output """
        primitive = C_FIND()
        primitive.MessageIDBeingRespondedTo = 5
        primitive.AffectedSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
        primitive.Status = 0xFF00

        ref_identifier = Dataset()
        ref_identifier.QueryRetrieveLevel = "PATIENT"
        ref_identifier.RetrieveAETitle = validate_ae_title("FINDSCP")
        ref_identifier.PatientName = "ANON^A^B^C^D"

        primitive.Identifier = BytesIO(encode(ref_identifier, True, True))

        dimse_msg = C_FIND_RSP()
        dimse_msg.primitive_to_message(primitive)

        pdvs = []
        for fragment in dimse_msg.encode_msg(1, 16382):
            pdvs.append(fragment)
        cs_pdv = pdvs[0].presentation_data_value_list[0][1]
        ds_pdv = pdvs[1].presentation_data_value_list[0][1]
        assert cs_pdv == c_find_rsp_cmd
        assert ds_pdv == c_find_rsp_ds

    def test_is_valid_request(self):
        """Test C_FIND.is_valid_request"""
        primitive = C_FIND()
        assert not primitive.is_valid_request
        primitive.MessageID = 1
        assert not primitive.is_valid_request
        primitive.AffectedSOPClassUID = '1.2'
        assert not primitive.is_valid_request
        primitive.Priority = 2
        assert not primitive.is_valid_request
        primitive.Identifier = BytesIO()
        assert primitive.is_valid_request

    def test_is_valid_resposne(self):
        """Test C_FIND.is_valid_response."""
        primitive = C_FIND()
        assert not primitive.is_valid_response
        primitive.MessageIDBeingRespondedTo = 1
        assert not primitive.is_valid_response
        primitive.Status = 0x0000
        assert primitive.is_valid_response


class TestPrimitive_C_GET(object):
    """Test DIMSE C-GET operations."""
    def setup(self):
        self.default_conformance = _config.ENFORCE_UID_CONFORMANCE

    def teardown(self):
        _config.ENFORCE_UID_CONFORMANCE = self.default_conformance

    def test_assignment(self):
        """ Check assignment works correctly """
        primitive = C_GET()

        primitive.MessageID = 11
        assert primitive.MessageID == 11

        primitive.MessageIDBeingRespondedTo = 13
        assert primitive.MessageIDBeingRespondedTo == 13

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

        primitive.Priority = 0x02
        assert primitive.Priority == 0x02

        ref_ds = Dataset()
        ref_ds.PatientID = 1234567

        primitive.Identifier = BytesIO(encode(ref_ds, True, True))
        #assert primitive.DataSet, ref_ds)

        primitive.Status = 0x0000
        assert primitive.Status == 0x0000

        primitive.Status = 0xC123
        assert primitive.Status == 0xC123

        primitive.Status = 0xEE01
        assert primitive.Status == 0xEE01

        primitive.NumberOfRemainingSuboperations = 1
        assert primitive.NumberOfRemainingSuboperations == 1

        primitive.NumberOfCompletedSuboperations = 2
        assert primitive.NumberOfCompletedSuboperations == 2

        primitive.NumberOfFailedSuboperations = 3
        assert primitive.NumberOfFailedSuboperations == 3

        primitive.NumberOfWarningSuboperations = 4
        assert primitive.NumberOfWarningSuboperations == 4

    def test_uid_exceptions_false(self):
        """Test ValueError raised with ENFORCE_UID_CONFORMANCE = False."""
        primitive = C_GET()

        _config.ENFORCE_UID_CONFORMANCE = False

        primitive.AffectedSOPClassUID = 'abc'
        assert primitive.AffectedSOPClassUID == 'abc'

        # Can't have more than 64 characters
        with pytest.raises(ValueError):
            primitive.AffectedSOPClassUID = 'abc' * 22

    def test_uid_exceptions_true(self):
        """Test ValueError raised with ENFORCE_UID_CONFORMANCE = True."""
        primitive = C_GET()
        _config.ENFORCE_UID_CONFORMANCE = True

        with pytest.raises(ValueError):
            primitive.AffectedSOPClassUID = 'abc'

    def test_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        primitive = C_GET()

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

        # NumberOfRemainingSuboperations
        with pytest.raises(TypeError):
            primitive.NumberOfRemainingSuboperations = 'halp'
        with pytest.raises(TypeError):
            primitive.NumberOfRemainingSuboperations = 1.111
        with pytest.raises(ValueError):
            primitive.NumberOfRemainingSuboperations = -1

        # NumberOfCompletedSuboperations
        with pytest.raises(TypeError):
            primitive.NumberOfCompletedSuboperations = 'halp'
        with pytest.raises(TypeError):
            primitive.NumberOfCompletedSuboperations = 1.111
        with pytest.raises(ValueError):
            primitive.NumberOfCompletedSuboperations = -1

        # NumberOfFailedSuboperations
        with pytest.raises(TypeError):
            primitive.NumberOfFailedSuboperations = 'halp'
        with pytest.raises(TypeError):
            primitive.NumberOfFailedSuboperations = 1.111
        with pytest.raises(ValueError):
            primitive.NumberOfFailedSuboperations = -1

        # NumberOfWarningSuboperations
        with pytest.raises(TypeError):
            primitive.NumberOfWarningSuboperations = 'halp'
        with pytest.raises(TypeError):
            primitive.NumberOfWarningSuboperations = 1.111
        with pytest.raises(ValueError):
            primitive.NumberOfWarningSuboperations = -1

        # AffectedSOPClassUID
        with pytest.raises(TypeError):
            primitive.AffectedSOPClassUID = 45.2

        with pytest.raises(TypeError):
            primitive.AffectedSOPClassUID = 100

        # Priority
        with pytest.raises(ValueError):
            primitive.Priority = 45.2

        with pytest.raises(ValueError):
            primitive.Priority = 'abc'

        with pytest.raises(ValueError):
            primitive.Priority = -1

        with pytest.raises(ValueError):
            primitive.Priority = 3

        # Identifier
        msg = r"'Identifier' parameter must be a BytesIO object"
        with pytest.raises(TypeError, match=msg):
            primitive.Identifier = 'halp'

        with pytest.raises(TypeError):
            primitive.Identifier = 1.111

        with pytest.raises(TypeError):
            primitive.Identifier = 50

        with pytest.raises(TypeError):
            primitive.Identifier = [30, 10]

        # Status
        with pytest.raises(TypeError):
            primitive.Status = 19.4

    def test_conversion_rq(self):
        """ Check conversion to a -RQ PDU produces the correct output """
        primitive = C_GET()
        primitive.MessageID = 7
        primitive.AffectedSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
        primitive.Priority = 0x02

        ref_identifier = Dataset()
        ref_identifier.PatientID = '*'
        ref_identifier.QueryRetrieveLevel = "PATIENT"

        primitive.Identifier = BytesIO(encode(ref_identifier, True, True))

        dimse_msg = C_GET_RQ()
        dimse_msg.primitive_to_message(primitive)

        pdvs = []
        for fragment in dimse_msg.encode_msg(1, 16382):
            pdvs.append(fragment)
        cs_pdv = pdvs[0].presentation_data_value_list[0][1]
        ds_pdv = pdvs[1].presentation_data_value_list[0][1]
        assert cs_pdv == c_get_rq_cmd
        assert ds_pdv == c_get_rq_ds

    def test_conversion_rsp(self):
        """ Check conversion to a -RSP PDU produces the correct output """
        primitive = C_GET()
        primitive.MessageIDBeingRespondedTo = 5
        primitive.AffectedSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
        primitive.Status = 0xFF00
        primitive.NumberOfRemainingSuboperations = 3
        primitive.NumberOfCompletedSuboperations = 1
        primitive.NumberOfFailedSuboperations = 2
        primitive.NumberOfWarningSuboperations = 4

        ref_identifier = Dataset()
        ref_identifier.QueryRetrieveLevel = "PATIENT"
        ref_identifier.PatientID = "*"

        primitive.Identifier = BytesIO(encode(ref_identifier, True, True))

        dimse_msg = C_GET_RSP()
        dimse_msg.primitive_to_message(primitive)

        pdvs = []
        for fragment in dimse_msg.encode_msg(1, 16382):
            pdvs.append(fragment)
        cs_pdv = pdvs[0].presentation_data_value_list[0][1]
        ds_pdv = pdvs[1].presentation_data_value_list[0][1]
        assert cs_pdv == c_get_rsp_cmd
        assert ds_pdv == c_get_rsp_ds

    def test_is_valid_request(self):
        """Test C_GET.is_valid_request"""
        primitive = C_GET()
        assert not primitive.is_valid_request
        primitive.MessageID = 1
        assert not primitive.is_valid_request
        primitive.AffectedSOPClassUID = '1.2'
        assert not primitive.is_valid_request
        primitive.Priority = 2
        assert not primitive.is_valid_request
        primitive.Identifier = BytesIO()
        assert primitive.is_valid_request

    def test_is_valid_resposne(self):
        """Test C_GET.is_valid_response."""
        primitive = C_GET()
        assert not primitive.is_valid_response
        primitive.MessageIDBeingRespondedTo = 1
        assert not primitive.is_valid_response
        primitive.Status = 0x0000
        assert primitive.is_valid_response


class TestPrimitive_C_MOVE(object):
    """Test DIMSE C-MOVE operations."""
    def setup(self):
        self.default_conformance = _config.ENFORCE_UID_CONFORMANCE
        self.default_aet_length = _config.USE_SHORT_DIMSE_AET

    def teardown(self):
        _config.ENFORCE_UID_CONFORMANCE = self.default_conformance
        _config.USE_SHORT_DIMSE_AET = self.default_aet_length

    def test_assignment(self):
        """ Check assignment works correctly """
        primitive = C_MOVE()

        primitive.MessageID = 11
        assert primitive.MessageID == 11

        primitive.MessageIDBeingRespondedTo = 13
        assert primitive.MessageIDBeingRespondedTo == 13

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

        primitive.Priority = 0x02
        assert primitive.Priority == 0x02

        primitive.MoveDestination = 'UNITTEST_SCP'
        assert primitive.MoveDestination == b'UNITTEST_SCP'

        ref_ds = Dataset()
        ref_ds.PatientID = 1234567

        primitive.Identifier = BytesIO(encode(ref_ds, True, True))
        #assert primitive.DataSet, ref_ds)

        primitive.Status = 0x0000
        assert primitive.Status == 0x0000

        primitive.Status = 0xC123
        assert primitive.Status == 0xC123

        primitive.Status = 0xEE01
        assert primitive.Status == 0xEE01

    def test_uid_exceptions_false(self):
        """Test ValueError raised with ENFORCE_UID_CONFORMANCE = False."""
        primitive = C_MOVE()

        _config.ENFORCE_UID_CONFORMANCE = False

        primitive.AffectedSOPClassUID = 'abc'
        assert primitive.AffectedSOPClassUID == 'abc'

        # Can't have more than 64 characters
        with pytest.raises(ValueError):
            primitive.AffectedSOPClassUID = 'abc' * 22

    def test_uid_exceptions_true(self):
        """Test ValueError raised with ENFORCE_UID_CONFORMANCE = True."""
        primitive = C_MOVE()
        _config.ENFORCE_UID_CONFORMANCE = True

        with pytest.raises(ValueError):
            primitive.AffectedSOPClassUID = 'abc'

    def test_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        primitive = C_MOVE()

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

        # NumberOfRemainingSuboperations
        with pytest.raises(TypeError):
            primitive.NumberOfRemainingSuboperations = 'halp'
        with pytest.raises(TypeError):
            primitive.NumberOfRemainingSuboperations = 1.111
        with pytest.raises(ValueError):
            primitive.NumberOfRemainingSuboperations = -1

        # NumberOfCompletedSuboperations
        with pytest.raises(TypeError):
            primitive.NumberOfCompletedSuboperations = 'halp'
        with pytest.raises(TypeError):
            primitive.NumberOfCompletedSuboperations = 1.111
        with pytest.raises(ValueError):
            primitive.NumberOfCompletedSuboperations = -1

        # NumberOfFailedSuboperations
        with pytest.raises(TypeError):
            primitive.NumberOfFailedSuboperations = 'halp'
        with pytest.raises(TypeError):
            primitive.NumberOfFailedSuboperations = 1.111
        with pytest.raises(ValueError):
            primitive.NumberOfFailedSuboperations = -1

        # NumberOfWarningSuboperations
        with pytest.raises(TypeError):
            primitive.NumberOfWarningSuboperations = 'halp'
        with pytest.raises(TypeError):
            primitive.NumberOfWarningSuboperations = 1.111
        with pytest.raises(ValueError):
            primitive.NumberOfWarningSuboperations = -1

        # AffectedSOPClassUID
        with pytest.raises(TypeError):
            primitive.AffectedSOPClassUID = 45.2

        with pytest.raises(TypeError):
            primitive.AffectedSOPClassUID = 100

        # Priority
        with pytest.raises(ValueError):
            primitive.Priority = 45.2

        with pytest.raises(ValueError):
            primitive.Priority = 'abc'

        with pytest.raises(ValueError):
            primitive.Priority = -1

        with pytest.raises(ValueError):
            primitive.Priority = 3

        # MoveDestination
        with pytest.raises(TypeError):
            primitive.MoveDestination = 45.2

        with pytest.raises(TypeError):
            primitive.MoveDestination = 100

        with pytest.raises(ValueError):
            primitive.MoveDestination = ''

        with pytest.raises(ValueError):
            primitive.MoveDestination = '    '

        # Identifier
        msg = r"'Identifier' parameter must be a BytesIO object"
        with pytest.raises(TypeError, match=msg):
            primitive.Identifier = 'halp'

        with pytest.raises(TypeError):
            primitive.Identifier = 1.111

        with pytest.raises(TypeError):
            primitive.Identifier = 50

        with pytest.raises(TypeError):
            primitive.Identifier = [30, 10]

        # Status
        with pytest.raises(TypeError):
            primitive.Status = 19.4

    def test_conversion_rq(self):
        """ Check conversion to a -RQ PDU produces the correct output """
        primitive = C_MOVE()
        primitive.MessageID = 7
        primitive.AffectedSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
        primitive.Priority = 0x02
        primitive.MoveDestination = validate_ae_title("MOVE_SCP")

        ref_identifier = Dataset()
        ref_identifier.PatientID = '*'
        ref_identifier.QueryRetrieveLevel = "PATIENT"

        primitive.Identifier = BytesIO(encode(ref_identifier, True, True))

        dimse_msg = C_MOVE_RQ()
        dimse_msg.primitive_to_message(primitive)

        pdvs = []
        for fragment in dimse_msg.encode_msg(1, 16382):
            pdvs.append(fragment)

        cs_pdv = pdvs[0].presentation_data_value_list[0][1]
        ds_pdv = pdvs[1].presentation_data_value_list[0][1]
        assert cs_pdv == c_move_rq_cmd
        assert ds_pdv == c_move_rq_ds

    def test_conversion_rsp(self):
        """ Check conversion to a -RSP PDU produces the correct output """
        primitive = C_MOVE()
        primitive.MessageIDBeingRespondedTo = 5
        primitive.AffectedSOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
        primitive.Status = 0xFF00
        primitive.NumberOfRemainingSuboperations = 3
        primitive.NumberOfCompletedSuboperations = 1
        primitive.NumberOfFailedSuboperations = 2
        primitive.NumberOfWarningSuboperations = 4

        ref_identifier = Dataset()
        ref_identifier.QueryRetrieveLevel = "PATIENT"
        ref_identifier.PatientID = "*"

        primitive.Identifier = BytesIO(encode(ref_identifier, True, True))

        dimse_msg = C_MOVE_RSP()
        dimse_msg.primitive_to_message(primitive)

        pdvs = []
        for fragment in dimse_msg.encode_msg(1, 16382):
            pdvs.append(fragment)
        cs_pdv = pdvs[0].presentation_data_value_list[0][1]
        ds_pdv = pdvs[1].presentation_data_value_list[0][1]
        assert cs_pdv == c_move_rsp_cmd
        assert ds_pdv == c_move_rsp_ds

    def test_is_valid_request(self):
        """Test C_MOVE.is_valid_request"""
        primitive = C_MOVE()
        assert not primitive.is_valid_request
        primitive.MessageID = 1
        assert not primitive.is_valid_request
        primitive.AffectedSOPClassUID = '1.2'
        assert not primitive.is_valid_request
        primitive.Priority = 2
        assert not primitive.is_valid_request
        primitive.MoveDestination = b'1234567890123456'
        assert not primitive.is_valid_request
        primitive.Identifier = BytesIO()
        assert primitive.is_valid_request

    def test_is_valid_resposne(self):
        """Test C_MOVE.is_valid_response."""
        primitive = C_MOVE()
        assert not primitive.is_valid_response
        primitive.MessageIDBeingRespondedTo = 1
        assert not primitive.is_valid_response
        primitive.Status = 0x0000
        assert primitive.is_valid_response

    def test_aet_short_false(self):
        """Test using long AE titles."""
        primitive = C_MOVE()

        _config.USE_SHORT_DIMSE_AET = False

        primitive.MoveDestination = b'A'
        assert b'A               ' == primitive.MoveDestination

    def test_aet_short_true(self):
        """Test using short AE titles."""
        primitive = C_MOVE()

        _config.USE_SHORT_DIMSE_AET = True

        primitive.MoveDestination = b'A'
        aet = primitive.MoveDestination
        assert b'A' == primitive.MoveDestination

        primitive.MoveDestination = b'ABCDEFGHIJKLMNO'
        assert b'ABCDEFGHIJKLMNO' == primitive.MoveDestination

        primitive.MoveDestination = b'ABCDEFGHIJKLMNOP'
        assert b'ABCDEFGHIJKLMNOP' == primitive.MoveDestination

        primitive.MoveDestination = b'ABCDEFGHIJKLMNOPQ'
        assert b'ABCDEFGHIJKLMNOP' == primitive.MoveDestination


class TestPrimitive_C_ECHO(object):
    """Test DIMSE C-ECHO operations."""
    def setup(self):
        self.default_conformance = _config.ENFORCE_UID_CONFORMANCE

    def teardown(self):
        _config.ENFORCE_UID_CONFORMANCE = self.default_conformance

    def test_assignment(self):
        """ Check assignment works correctly """
        primitive = C_ECHO()

        primitive.MessageID = 11
        assert primitive.MessageID == 11

        primitive.MessageIDBeingRespondedTo = 13
        assert primitive.MessageIDBeingRespondedTo == 13

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

        # Known status
        primitive.Status = 0x0000
        assert primitive.Status == 0x0000
        # Unknown status
        primitive.Status = 0x9999
        assert primitive.Status == 0x9999

        primitive.Status = 0xEE01
        assert primitive.Status == 0xEE01

    def test_uid_exceptions_false(self):
        """Test ValueError raised with ENFORCE_UID_CONFORMANCE = False."""
        primitive = C_ECHO()

        _config.ENFORCE_UID_CONFORMANCE = False

        primitive.AffectedSOPClassUID = 'abc'
        assert primitive.AffectedSOPClassUID == 'abc'

        # Can't have more than 64 characters
        with pytest.raises(ValueError):
            primitive.AffectedSOPClassUID = 'abc' * 22

    def test_uid_exceptions_true(self):
        """Test ValueError raised with ENFORCE_UID_CONFORMANCE = True."""
        primitive = C_ECHO()
        _config.ENFORCE_UID_CONFORMANCE = True

        with pytest.raises(ValueError):
            primitive.AffectedSOPClassUID = 'abc'

    def test_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        primitive = C_ECHO()

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

        # Status
        with pytest.raises(TypeError):
            primitive.Status = 19.4

    def test_conversion_rq(self):
        """ Check conversion to a -RQ PDU produces the correct output """
        primitive = C_ECHO()
        primitive.MessageID = 7
        primitive.AffectedSOPClassUID = '1.2.840.10008.1.1'

        dimse_msg = C_ECHO_RQ()
        dimse_msg.primitive_to_message(primitive)

        pdvs = []
        for fragment in dimse_msg.encode_msg(1, 16382):
            pdvs.append(fragment)
        cs_pdv = pdvs[0].presentation_data_value_list[0][1]
        assert cs_pdv == c_echo_rq_cmd

    def test_conversion_rsp(self):
        """ Check conversion to a -RQ PDU produces the correct output """
        primitive = C_ECHO()
        primitive.MessageIDBeingRespondedTo = 8
        primitive.AffectedSOPClassUID = '1.2.840.10008.1.1'
        primitive.Status = 0x0000

        dimse_msg = C_ECHO_RSP()
        dimse_msg.primitive_to_message(primitive)

        pdvs = []
        for fragment in dimse_msg.encode_msg(1, 16382):
            pdvs.append(fragment)
        cs_pdv = pdvs[0].presentation_data_value_list[0][1]
        assert cs_pdv == c_echo_rsp_cmd

    def test_is_valid_request(self):
        """Test C_ECHO.is_valid_request"""
        primitive = C_ECHO()
        assert not primitive.is_valid_request
        primitive.MessageID = 1
        assert not primitive.is_valid_request
        primitive.AffectedSOPClassUID = '1.2'
        assert primitive.is_valid_request

    def test_is_valid_resposne(self):
        """Test C_ECHO.is_valid_response."""
        primitive = C_ECHO()
        assert not primitive.is_valid_response
        primitive.MessageIDBeingRespondedTo = 1
        assert not primitive.is_valid_response
        primitive.Status = 0x0000
        assert primitive.is_valid_response
