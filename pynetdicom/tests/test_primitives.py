#!/usr/bin/env python
"""Test the service primitives."""

import logging

import pytest

from pydicom.uid import UID

from pynetdicom import _config
from pynetdicom.pdu import A_ASSOCIATE_RQ, A_ABORT_RQ, P_DATA_TF
from pynetdicom.pdu_primitives import (
    SOPClassExtendedNegotiation,
    SOPClassCommonExtendedNegotiation,
    MaximumLengthNotification,
    ImplementationClassUIDNotification,
    ImplementationVersionNameNotification,
    P_DATA, A_RELEASE, A_ASSOCIATE, A_P_ABORT, A_ABORT,
    SCP_SCU_RoleSelectionNegotiation,
    AsynchronousOperationsWindowNegotiation,
    UserIdentityNegotiation
)
from pynetdicom.presentation import PresentationContext
from pynetdicom.utils import pretty_bytes

LOGGER = logging.getLogger('pynetdicom')
LOGGER.setLevel(logging.CRITICAL)


def print_nice_bytes(bytestream):
    """Nice output for bytestream."""
    str_list = pretty_bytes(bytestream, prefix="b'\\x", delimiter='\\x',
                            items_per_line=10)
    for string in str_list:
        print(string)


class TestPrimitive_MaximumLengthNotification(object):
    def test_assignment_and_exceptions(self):
        """Test incorrect setter for maximum_length_received raises"""
        primitive = MaximumLengthNotification()

        # Check default assignment
        assert primitive.maximum_length_received == 16382

        # Check new assignment
        primitive.maximum_length_received = 45
        assert primitive.maximum_length_received == 45

        # Check exceptions
        with pytest.raises(TypeError):
            primitive.maximum_length_received = 45.2

        with pytest.raises(ValueError):
            primitive.maximum_length_received = -1

        with pytest.raises(TypeError):
            primitive.maximum_length_received = 'abc'

    def test_conversion(self):
        """ Check converting to PDU item works correctly """
        ## Check conversion to item using default value
        primitive = MaximumLengthNotification()
        item = primitive.from_primitive()

        # \x3F\xFE = 16382
        assert item.encode() == b"\x51\x00\x00\x04\x00\x00\x3f\xfe"

        ## Check conversion using 0 (unlimited)
        primitive.maximum_length_received = 0
        item = primitive.from_primitive()

        # \x00\x00 = 0
        assert item.encode() == b"\x51\x00\x00\x04\x00\x00\x00\x00"

    def test_string(self):
        """Check the string output."""
        primitive = MaximumLengthNotification()
        assert '16382 bytes' in primitive.__str__()


class TestPrimitive_ImplementationClassUIDNotification(object):
    def setup(self):
        self.default_conformance = _config.ENFORCE_UID_CONFORMANCE

    def teardown(self):
        _config.ENFORCE_UID_CONFORMANCE = self.default_conformance

    def test_uid_conformance_false(self):
        """Test UID conformance with ENFORCE_UID_CONFORMANCE = False"""
        _config.ENFORCE_UID_CONFORMANCE = False
        primitive = ImplementationClassUIDNotification()

        primitive.implementation_class_uid = 'abc'
        assert primitive.implementation_class_uid == 'abc'

        with pytest.raises(ValueError):
            primitive.implementation_class_uid = 'abc' * 22

    def test_uid_conformance_true(self):
        """Test UID conformance with ENFORCE_UID_CONFORMANCE = True"""
        _config.ENFORCE_UID_CONFORMANCE = True
        primitive = ImplementationClassUIDNotification()

        with pytest.raises(ValueError):
            primitive.implementation_class_uid = 'abc'

    def test_assignment_and_exceptions(self):
        """Check incorrect setter for implementation_class_uid raises"""
        primitive = ImplementationClassUIDNotification()

        ## Check assignment
        reference_uid = UID('1.2.826.0.1.3680043.9.3811.0.9.0')

        # bytes
        primitive.implementation_class_uid = (
            b'1.2.826.0.1.3680043.9.3811.0.9.0'
        )
        assert primitive.implementation_class_uid == reference_uid

        # str
        primitive.implementation_class_uid = (
            '1.2.826.0.1.3680043.9.3811.0.9.0'
        )
        assert primitive.implementation_class_uid == reference_uid

        # UID
        primitive.implementation_class_uid = UID(
            '1.2.826.0.1.3680043.9.3811.0.9.0'
        )
        assert primitive.implementation_class_uid == reference_uid

        ## Check exceptions
        primitive = ImplementationClassUIDNotification()

        # No value set
        with pytest.raises(ValueError):
            item = primitive.from_primitive()

        # Non UID, bytes or str
        with pytest.raises(TypeError):
            primitive.implementation_class_uid = 45.2

        with pytest.raises(TypeError):
            primitive.implementation_class_uid = 100

    def test_conversion(self):
        """ Check converting to PDU item works correctly """
        primitive = ImplementationClassUIDNotification()
        primitive.implementation_class_uid = UID(
            '1.2.826.0.1.3680043.9.3811.0.9.0'
        )
        item = primitive.from_primitive()

        assert item.encode() == (
            b"\x52\x00\x00\x20\x31\x2e\x32\x2e\x38\x32\x36\x2e\x30\x2e\x31"
            b"\x2e\x33\x36\x38\x30\x30\x34\x33\x2e\x39\x2e\x33\x38\x31\x31\x2e"
            b"\x30\x2e\x39\x2e\x30"
        )

    def test_string(self):
        """Check the string output."""
        primitive = ImplementationClassUIDNotification()
        primitive.implementation_class_uid = UID(
            '1.2.826.0.1.3680043.9.3811.0.9.0'
        )
        assert '1.2.826.0.1.3680043.9.3811.0.9.0' in primitive.__str__()


class TestPrimitive_ImplementationVersionNameNotification(object):
    def test_assignment_and_exceptions(self):
        """Check incorrect setting for implementation_version_name raises"""
        primitive = ImplementationVersionNameNotification()

        ## Check assignment
        reference_name = b'PYNETDICOM_090'

        ## Check maximum length allowable
        primitive.implementation_version_name = b'1234567890ABCDEF'
        assert primitive.implementation_version_name == b'1234567890ABCDEF'

        # bytes
        primitive.implementation_version_name = b'PYNETDICOM_090'
        assert primitive.implementation_version_name == reference_name

        # str
        primitive.implementation_version_name = 'PYNETDICOM_090'
        assert primitive.implementation_version_name == reference_name

        primitive.implementation_version_name = 'P'
        assert primitive.implementation_version_name == b'P'

        ## Check exceptions
        primitive = ImplementationVersionNameNotification()

        # No value set
        with pytest.raises(ValueError):
            item = primitive.from_primitive()

        # Non UID, bytes or str
        with pytest.raises(TypeError):
            primitive.implementation_version_name = 45.2

        with pytest.raises(TypeError):
            primitive.implementation_version_name = 100

        msg = (
            r"Implementation Version Name must be between 1 and 16"
            r" characters long"
        )
        with pytest.raises(ValueError, match=msg):
            primitive.implementation_version_name = 'ABCD1234ABCD12345'

        with pytest.raises(ValueError, match=msg):
            primitive.implementation_version_name = ''

    def test_conversion(self):
        """ Check converting to PDU item works correctly """
        primitive = ImplementationVersionNameNotification()
        primitive.implementation_version_name = b'PYNETDICOM_090'
        item = primitive.from_primitive()

        assert item.encode() == (
            b'\x55\x00\x00\x0e\x50\x59\x4e\x45\x54\x44\x49\x43\x4f\x4d\x5f'
            b'\x30\x39\x30'
        )

    def test_string(self):
        """Check the string output."""
        primitive = ImplementationVersionNameNotification()
        primitive.implementation_version_name = b'PYNETDICOM3_090'
        assert 'PYNETDICOM3_090' in primitive.__str__()


class TestPrimitive_AsynchronousOperationsWindowNegotiation(object):
    def test_assignment_and_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        primitive = AsynchronousOperationsWindowNegotiation()

        ## Check default assignment
        assert primitive.maximum_number_operations_invoked == 1
        assert primitive.maximum_number_operations_performed == 1

        ## Check assignment
        primitive.maximum_number_operations_invoked = 10
        assert primitive.maximum_number_operations_invoked == 10

        primitive.maximum_number_operations_performed = 11
        assert primitive.maximum_number_operations_performed == 11

        ## Check exceptions
        with pytest.raises(TypeError):
            primitive.maximum_number_operations_invoked = 45.2

        with pytest.raises(ValueError):
            primitive.maximum_number_operations_invoked = -1

        with pytest.raises(TypeError):
            primitive.maximum_number_operations_invoked = 'ABCD1234ABCD12345'

        with pytest.raises(TypeError):
            primitive.maximum_number_operations_performed = 45.2

        with pytest.raises(ValueError):
            primitive.maximum_number_operations_performed = -1

        with pytest.raises(TypeError):
            primitive.maximum_number_operations_performed = 'ABCD1234ABCD12345'

    def test_conversion(self):
        """ Check converting to PDU item works correctly """
        primitive = AsynchronousOperationsWindowNegotiation()
        primitive.maximum_number_operations_invoked = 10
        primitive.maximum_number_operations_performed = 0
        item = primitive.from_primitive()

        assert item.encode() == b'\x53\x00\x00\x04\x00\x0a\x00\x00'

    def test_string(self):
        """Check the string output."""
        primitive = AsynchronousOperationsWindowNegotiation()
        primitive.maximum_number_operations_invoked = 10
        primitive.maximum_number_operations_performed = 0
        assert 'invoked: 10' in primitive.__str__()
        assert 'performed: 0' in primitive.__str__()


class TestPrimitive_SCP_SCU_RoleSelectionNegotiation(object):
    def setup(self):
        self.default_conformance = _config.ENFORCE_UID_CONFORMANCE

    def teardown(self):
        _config.ENFORCE_UID_CONFORMANCE = self.default_conformance

    def test_uid_conformance_false(self):
        """Test UID conformance with ENFORCE_UID_CONFORMANCE = False"""
        _config.ENFORCE_UID_CONFORMANCE = False
        primitive = SCP_SCU_RoleSelectionNegotiation()

        primitive.sop_class_uid = 'abc'
        assert primitive.sop_class_uid == 'abc'

    def test_uid_conformance_true(self):
        """Test UID conformance with ENFORCE_UID_CONFORMANCE = True"""
        _config.ENFORCE_UID_CONFORMANCE = True
        primitive = SCP_SCU_RoleSelectionNegotiation()

        with pytest.raises(ValueError):
            primitive.sop_class_uid = 'abc'

    def test_assignment_and_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        primitive = SCP_SCU_RoleSelectionNegotiation()

        ## Check assignment
        # SOP Class UID
        reference_uid = UID('1.2.840.10008.5.1.4.1.1.2')

        primitive.sop_class_uid = b'1.2.840.10008.5.1.4.1.1.2'
        assert primitive.sop_class_uid == reference_uid

        primitive.sop_class_uid = '1.2.840.10008.5.1.4.1.1.2'
        assert primitive.sop_class_uid == reference_uid

        primitive.sop_class_uid = UID('1.2.840.10008.5.1.4.1.1.2')
        assert primitive.sop_class_uid == reference_uid

        # SCP Role
        primitive.scp_role = False
        assert primitive.scp_role is False

        # SCU Role
        primitive.scu_role = True
        assert primitive.scu_role is True

        ## Check exceptions
        with pytest.raises(TypeError):
            primitive.sop_class_uid = 10

        with pytest.raises(TypeError):
            primitive.sop_class_uid = 45.2

        with pytest.raises(TypeError):
            primitive.scp_role = 1

        with pytest.raises(TypeError):
            primitive.scp_role = 'abc'

        with pytest.raises(TypeError):
            primitive.scu_role = 1

        with pytest.raises(TypeError):
            primitive.scu_role = 'abc'

        # No value set
        primitive = SCP_SCU_RoleSelectionNegotiation()
        with pytest.raises(ValueError):
            item = primitive.from_primitive()

        primitive.sop_class_uid = b'1.2.840.10008.5.1.4.1.1.2'
        with pytest.raises(ValueError):
            item = primitive.from_primitive()

        primitive.scp_role = False
        with pytest.raises(ValueError):
            item = primitive.from_primitive()

        primitive = SCP_SCU_RoleSelectionNegotiation()
        primitive.sop_class_uid = b'1.2.840.10008.5.1.4.1.1.2'
        primitive.scu_role = True
        item = primitive.from_primitive()
        assert item.scu_role
        assert not item.scp_role

        primitive = SCP_SCU_RoleSelectionNegotiation()
        primitive.scp_role = True
        primitive.scu_role = True
        with pytest.raises(ValueError):
            item = primitive.from_primitive()

    def test_conversion(self):
        """ Check converting to PDU item works correctly """
        primitive = SCP_SCU_RoleSelectionNegotiation()
        primitive.sop_class_uid = b'1.2.840.10008.5.1.4.1.1.2'
        primitive.scp_role = True
        primitive.scu_role = False
        item = primitive.from_primitive()

        assert item.encode() == (
            b'\x54\x00\x00\x1d\x00\x19\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30'
            b'\x30\x30\x38\x2e\x35\x2e\x31\x2e\x34\x2e\x31\x2e\x31\x2e\x32'
            b'\x00\x01'
        )

        primitive = SCP_SCU_RoleSelectionNegotiation()
        primitive.sop_class_uid = b'1.2.840.10008.5.1.4.1.1.2'
        primitive.scp_role = False
        primitive.scu_role = False
        with pytest.raises(ValueError):
            primitive.from_primitive()


class TestPrimitive_SOPClassExtendedNegotiation(object):
    def setup(self):
        self.default_conformance = _config.ENFORCE_UID_CONFORMANCE

    def teardown(self):
        _config.ENFORCE_UID_CONFORMANCE = self.default_conformance

    def test_uid_conformance_false(self):
        """Test UID conformance with ENFORCE_UID_CONFORMANCE = False"""
        _config.ENFORCE_UID_CONFORMANCE = False
        primitive = SOPClassExtendedNegotiation()

        primitive.sop_class_uid = 'abc'
        assert primitive.sop_class_uid == 'abc'

    def test_uid_conformance_true(self):
        """Test UID conformance with ENFORCE_UID_CONFORMANCE = True"""
        _config.ENFORCE_UID_CONFORMANCE = True
        primitive = SOPClassExtendedNegotiation()

        with pytest.raises(ValueError):
            primitive.sop_class_uid = 'abc'

    def test_assignment_and_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        primitive = SOPClassExtendedNegotiation()

        ## Check assignment
        # SOP Class UID
        reference_uid = UID('1.2.840.10008.5.1.4.1.1.2')

        primitive.sop_class_uid = b'1.2.840.10008.5.1.4.1.1.2'
        assert primitive.sop_class_uid == reference_uid

        primitive.sop_class_uid = '1.2.840.10008.5.1.4.1.1.2'
        assert primitive.sop_class_uid == reference_uid

        primitive.sop_class_uid = UID('1.2.840.10008.5.1.4.1.1.2')
        assert primitive.sop_class_uid == reference_uid

        # Service Class Application Information
        primitive.service_class_application_information = (
            b'\x02\x00\x03\x00\x01\x00'
        )
        assert primitive.service_class_application_information == (
            b'\x02\x00\x03\x00\x01\x00'
        )

        ## Check exceptions
        # SOP Class UID
        with pytest.raises(TypeError):
            primitive.sop_class_uid = 10

        with pytest.raises(TypeError):
            primitive.sop_class_uid = 45.2

        # Service Class Application Information
        with pytest.raises(TypeError):
            primitive.service_class_application_information = 10

        with pytest.raises(TypeError):
            primitive.service_class_application_information = 45.2

        # Python 2 compatibility all bytes are str
        #with pytest.raises(TypeError):
        #    primitive.service_class_application_information = 'abc'

        # No value set
        primitive = SOPClassExtendedNegotiation()
        with pytest.raises(ValueError):
            item = primitive.from_primitive()

        primitive.sop_class_uid = b'1.2.840.10008.5.1.4.1.1.2'
        with pytest.raises(ValueError):
            item = primitive.from_primitive()

        primitive = SOPClassExtendedNegotiation()
        primitive.service_class_application_information = (
            b'\x02\x00\x03\x00\x01\x00'
        )
        with pytest.raises(ValueError):
            item = primitive.from_primitive()

    def test_conversion(self):
        """ Check converting to PDU item works correctly """
        primitive = SOPClassExtendedNegotiation()
        primitive.sop_class_uid = b'1.2.840.10008.5.1.4.1.1.2'
        primitive.service_class_application_information = (
            b'\x02\x00\x03\x00\x01\x00'
        )
        item = primitive.from_primitive()

        assert item.encode() == (
            b'\x56\x00\x00\x21\x00\x19\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30'
            b'\x30\x30\x38\x2e\x35\x2e\x31\x2e\x34\x2e\x31\x2e\x31\x2e\x32'
            b'\x02\x00\x03\x00\x01\x00'
        )


class TestPrimitive_SOPClassCommonExtendedNegotiation(object):
    def setup(self):
        self.default_conformance = _config.ENFORCE_UID_CONFORMANCE

    def teardown(self):
        _config.ENFORCE_UID_CONFORMANCE = self.default_conformance

    def test_uid_conformance_false(self):
        """Test UID conformance with ENFORCE_UID_CONFORMANCE = False"""
        _config.ENFORCE_UID_CONFORMANCE = False
        primitive = SOPClassCommonExtendedNegotiation()

        primitive.sop_class_uid = 'abc'
        assert primitive.sop_class_uid == 'abc'
        primitive.service_class_uid = 'abc'
        assert primitive.service_class_uid == 'abc'
        primitive.related_general_sop_class_identification = ['abc']
        assert primitive.related_general_sop_class_identification == ['abc']

        with pytest.raises(ValueError):
            primitive.sop_class_uid = 'abc' * 22

        with pytest.raises(ValueError):
            primitive.service_class_uid = 'abc' * 22

        with pytest.raises(ValueError):
            primitive.related_general_sop_class_identification = ['abc'  * 22]

    def test_uid_conformance_true(self):
        """Test UID conformance with ENFORCE_UID_CONFORMANCE = True"""
        _config.ENFORCE_UID_CONFORMANCE = True
        primitive = SOPClassCommonExtendedNegotiation()

        with pytest.raises(ValueError):
            primitive.sop_class_uid = 'abc'

        with pytest.raises(ValueError):
            primitive.service_class_uid = 'abc'

        with pytest.raises(ValueError):
            primitive.related_general_sop_class_identification = ['abc']

    def test_assignment_and_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        primitive = SOPClassCommonExtendedNegotiation()

        ## Check assignment
        # SOP Class UID
        reference_uid = UID('1.2.840.10008.5.1.4.1.1.2')

        primitive.sop_class_uid = b'1.2.840.10008.5.1.4.1.1.2'
        assert primitive.sop_class_uid == reference_uid
        primitive.sop_class_uid = 'abc'
        assert primitive.sop_class_uid == 'abc'
        primitive.sop_class_uid = '1.2.840.10008.5.1.4.1.1.2'
        assert primitive.sop_class_uid == reference_uid
        primitive.sop_class_uid = UID('1.2.840.10008.5.1.4.1.1.2')
        assert primitive.sop_class_uid == reference_uid

        # Service Class UID
        primitive.service_class_uid = b'1.2.840.10008.5.1.4.1.1.2'
        assert primitive.service_class_uid == reference_uid
        primitive.service_class_uid = 'abc'
        assert primitive.service_class_uid == 'abc'
        primitive.service_class_uid = '1.2.840.10008.5.1.4.1.1.2'
        assert primitive.service_class_uid == reference_uid
        primitive.service_class_uid = UID('1.2.840.10008.5.1.4.1.1.2')
        assert primitive.service_class_uid == reference_uid

        # Related General SOP Class Identification
        ref_list = [UID('1.2.840.10008.5.1.4.1.1.2'),
                    UID('1.2.840.10008.5.1.4.1.1.3'),
                    UID('1.2.840.10008.5.1.4.1.1.4')]

        uid_list = []
        uid_list.append(b'1.2.840.10008.5.1.4.1.1.2')
        uid_list.append('1.2.840.10008.5.1.4.1.1.3')
        uid_list.append(UID('1.2.840.10008.5.1.4.1.1.4'))
        primitive.related_general_sop_class_identification = uid_list
        assert primitive.related_general_sop_class_identification == ref_list
        primitive.related_general_sop_class_identification = ['abc']
        assert primitive.related_general_sop_class_identification == ['abc']

        with pytest.raises(TypeError):
            primitive.related_general_sop_class_identification = 'test'

        ## Check exceptions
        # SOP Class UID
        with pytest.raises(TypeError):
            primitive.sop_class_uid = 10

        with pytest.raises(TypeError):
            primitive.sop_class_uid = 45.2

        # Service Class UID
        with pytest.raises(TypeError):
            primitive.service_class_uid = 10

        with pytest.raises(TypeError):
            primitive.service_class_uid = 45.2

        # Related General SOP Class Identification
        with pytest.raises(TypeError):
            primitive.related_general_sop_class_identification = [10]

        with pytest.raises(TypeError):
            primitive.related_general_sop_class_identification = [45.2]

        # No value set
        primitive = SOPClassCommonExtendedNegotiation()
        with pytest.raises(ValueError):
            item = primitive.from_primitive()

        primitive.sop_class_uid = b'1.2.840.10008.5.1.4.1.1.2'
        with pytest.raises(ValueError):
            item = primitive.from_primitive()

        primitive = SOPClassCommonExtendedNegotiation()
        primitive.service_class_uid = b'1.2.840.10008.5.1.4.1.1.2'
        with pytest.raises(ValueError):
            item = primitive.from_primitive()

    def test_conversion(self):
        """ Check converting to PDU item works correctly """
        primitive = SOPClassCommonExtendedNegotiation()
        primitive.sop_class_uid = b'1.2.840.10008.5.1.4.1.1.4'
        primitive.service_class_uid = b'1.2.840.10008.4.2'
        primitive.related_general_sop_class_identification = [
            '1.2.840.10008.5.1.4.1.1.88.22'
        ]
        item = primitive.from_primitive()

        assert item.encode() == (
            b'\x57\x00\x00\x4f\x00\x19\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30'
            b'\x30\x30\x38\x2e\x35\x2e\x31\x2e\x34\x2e\x31\x2e\x31\x2e\x34\x00'
            b'\x11\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x34'
            b'\x2e\x32\x00\x1f\x00\x1d\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30'
            b'\x30\x30\x38\x2e\x35\x2e\x31\x2e\x34\x2e\x31\x2e\x31\x2e\x38\x38'
            b'\x2e\x32\x32'
        )


class TestPrimitive_UserIdentityNegotiation(object):
    def test_assignment_and_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        primitive = UserIdentityNegotiation()
        for type_no in [1, 2, 3, 4, 5]:
            primitive.user_identity_type = type_no
            assert primitive.user_identity_type == type_no

        with pytest.raises(ValueError):
            primitive.user_identity_type = 6

        with pytest.raises(TypeError):
            primitive.user_identity_type = 'a'

        primitive.positive_response_requested = True
        assert primitive.positive_response_requested
        with pytest.raises(TypeError):
            primitive.positive_response_requested = 'test'

        primitive.primary_field = b'\x00\x01'
        assert primitive.primary_field == b'\x00\x01'
        with pytest.raises(TypeError):
            primitive.primary_field = ['test']

        primitive.secondary_field = b'\x00\x21'
        assert primitive.secondary_field == b'\x00\x21'
        primitive.secondary_field = None
        assert primitive.secondary_field is None
        with pytest.raises(TypeError):
            primitive.secondary_field = ['test']

        primitive.server_response = b'\x00\x31'
        assert primitive.server_response == b'\x00\x31'
        with pytest.raises(TypeError):
            primitive.server_response = ['test']

        primitive = UserIdentityNegotiation()
        with pytest.raises(ValueError):
            primitive.from_primitive()

        primitive.user_identity_type = 2
        with pytest.raises(ValueError):
            primitive.from_primitive()

    def test_string(self):
        """Check string output."""
        primitive = UserIdentityNegotiation()
        primitive.user_identity_type = 1
        primitive.positive_response_requested = True
        primitive.primary_field = b'\x00\x01'
        primitive.secondary_field = b'\x00\x21'
        assert 'requested: True' in primitive.__str__()
        assert 'type: 1' in primitive.__str__()
        assert 'Primary' in primitive.__str__()
        assert 'Secondary' in primitive.__str__()

        primitive.server_response = b'\x00\x31'
        assert 'Server response' in primitive.__str__()

    def test_conversion(self):
        """ Check converting to PDU item works correctly """
        primitive = UserIdentityNegotiation()
        # -RQ
        primitive.user_identity_type = 1
        primitive.primary_field = b'test'
        item = primitive.from_primitive()

        primitive.user_identity_type = 2
        primitive.secondary_field = b''
        with pytest.raises(ValueError):
            item = primitive.from_primitive()

        # -AC
        primitive = UserIdentityNegotiation()
        primitive.server_response = b'Test'
        item = primitive.from_primitive()
        assert item.encode() == b'\x59\x00\x00\x06\x00\x04\x54\x65\x73\x74'


class TestPrimitive_A_ASSOCIATE(object):
    def setup(self):
        self.default_conformance = _config.ENFORCE_UID_CONFORMANCE

    def teardown(self):
        _config.ENFORCE_UID_CONFORMANCE = self.default_conformance

    def test_uid_conformance_false(self):
        """Test UID conformance with ENFORCE_UID_CONFORMANCE = False"""
        _config.ENFORCE_UID_CONFORMANCE = False
        primitive = A_ASSOCIATE()

        primitive.application_context_name = 'abc'
        assert primitive.application_context_name == 'abc'

    def test_uid_conformance_true(self):
        """Test UID conformance with ENFORCE_UID_CONFORMANCE = True"""
        _config.ENFORCE_UID_CONFORMANCE = True
        primitive = A_ASSOCIATE()

        with pytest.raises(ValueError):
            primitive.application_context_name = 'abc'

    def test_assignment(self):
        """ Check assignment works correctly """
        assoc = A_ASSOCIATE()

        with pytest.raises(AttributeError):
            assoc.mode = "test value"

        with pytest.raises(AttributeError):
            assoc.presentation_requirements = "test value2"

        with pytest.raises(AttributeError):
            assoc.session_requirements = "test value3"

        assoc.application_context_name = "1.2.840.10008.3.1.1.1"
        assert assoc.application_context_name == UID('1.2.840.10008.3.1.1.1')
        assoc.application_context_name = b"1.2.840.10008.3.1.1.1"
        assert assoc.application_context_name == UID('1.2.840.10008.3.1.1.1')
        assoc.application_context_name = UID("1.2.840.10008.3.1.1.1")
        assert assoc.application_context_name == UID('1.2.840.10008.3.1.1.1')

        assoc.calling_ae_title = 'ABCD1234ABCD12345'
        assert assoc.calling_ae_title == b'ABCD1234ABCD1234'

        assoc.called_ae_title = 'ABCD1234ABCD12345'
        assert assoc.called_ae_title == b'ABCD1234ABCD1234'
        assert assoc.responding_ae_title == b'ABCD1234ABCD1234'

        max_length = MaximumLengthNotification()
        max_length.maximum_length_received = 31222
        assoc.user_information.append(max_length)
        assert assoc.user_information[0].maximum_length_received == 31222

        assoc.user_information = ['a', max_length]
        assert assoc.user_information == [max_length]

        assoc.result = 0
        assert assoc.result == 0
        assoc.result = 1
        assert assoc.result == 1
        assoc.result = 2
        assert assoc.result == 2

        assoc.result_source = 1
        assert assoc.result_source == 1
        assoc.result_source = 2
        assert assoc.result_source == 2
        assoc.result_source = 3
        assert assoc.result_source == 3

        assoc.diagnostic = 1
        assert assoc.diagnostic == 1
        assoc.diagnostic = 2
        assert assoc.diagnostic == 2
        assoc.diagnostic = 3
        assert assoc.diagnostic == 3
        assoc.diagnostic = 7
        assert assoc.diagnostic == 7

        assoc.calling_presentation_address = ('10.40.94.43', 105)
        assert assoc.calling_presentation_address == ('10.40.94.43', 105)

        assoc.called_presentation_address = ('10.40.94.44', 106)
        assert assoc.called_presentation_address == ('10.40.94.44', 106)

        pc = PresentationContext()
        pc.context_id = 1
        assoc.presentation_context_definition_list = [pc]
        assert assoc.presentation_context_definition_list == [pc]
        assoc.presentation_context_definition_list = ['a', pc]
        assert assoc.presentation_context_definition_list == [pc]

        assoc.presentation_context_definition_results_list = [pc]
        assert assoc.presentation_context_definition_results_list == [pc]
        assoc.presentation_context_definition_results_list = ['a', pc]
        assert assoc.presentation_context_definition_results_list == [pc]

        assoc = A_ASSOCIATE()
        # No maximum_length_received set
        assert assoc.maximum_length_received is None

        # No MaximumLengthNotification present
        assoc.maximum_length_received = 31223
        assert assoc.user_information[0].maximum_length_received == 31223
        assert assoc.maximum_length_received == 31223

        # MaximumLengthNotification already present
        assoc.maximum_length_received = 31224
        assert assoc.maximum_length_received == 31224

        # No ImplementationClassUIDNotification present
        assoc.implementation_class_uid = '1.1.2.3.4'
        assert assoc.user_information[1].implementation_class_uid == UID(
            '1.1.2.3.4'
        )
        assert assoc.implementation_class_uid == UID('1.1.2.3.4')

        # ImplementationClassUIDNotification already present
        assoc.implementation_class_uid = '1.1.2.3.4'
        assert assoc.implementation_class_uid == UID('1.1.2.3.4')

    def test_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        assoc = A_ASSOCIATE()

        # application_context_name
        with pytest.raises(TypeError):
            assoc.application_context_name = 10

        with pytest.raises(TypeError):
            assoc.application_context_name = 45.2

        # calling_ae_title
        with pytest.raises(TypeError):
            assoc.calling_ae_title = 45.2

        with pytest.raises(TypeError):
            assoc.calling_ae_title = 100

        with pytest.raises(ValueError):
            assoc.calling_ae_title = ''

        with pytest.raises(ValueError):
            assoc.calling_ae_title = '    '

        # called_ae_title
        with pytest.raises(TypeError):
            assoc.called_ae_title = 45.2

        with pytest.raises(TypeError):
            assoc.called_ae_title = 100

        with pytest.raises(ValueError):
            assoc.called_ae_title = ''

        with pytest.raises(ValueError):
            assoc.called_ae_title = '    '

        # user_information
        with pytest.raises(TypeError):
            assoc.user_information = 45.2

        # result
        with pytest.raises(ValueError):
            assoc.result = -1

        with pytest.raises(ValueError):
            assoc.result = 3

        # result_source
        with pytest.raises(ValueError):
            assoc.result_source = 0

        # result_source
        with pytest.raises(ValueError):
            assoc.result_source = 4

        # diagnostic
        with pytest.raises(ValueError):
            assoc.diagnostic = 0

        with pytest.raises(ValueError):
            assoc.diagnostic = 4

        with pytest.raises(ValueError):
            assoc.diagnostic = 5

        with pytest.raises(ValueError):
            assoc.diagnostic = 6

        with pytest.raises(ValueError):
            assoc.diagnostic = 8

        # calling_presentation_addresss
        with pytest.raises(TypeError):
            assoc.calling_presentation_address = ['10.40.94.43', 105]

        with pytest.raises(TypeError):
            assoc.calling_presentation_address = (105, '10.40.94.43')

        # called_presentation_addresss
        with pytest.raises(TypeError):
            assoc.called_presentation_address = ['10.40.94.43', 105]

        with pytest.raises(TypeError):
            assoc.called_presentation_address = (105, '10.40.94.43')

        # presentation_context_definition_list
        with pytest.raises(TypeError):
            assoc.presentation_context_definition_list = 45.2

        # presentation_context_definition_results_list
        with pytest.raises(TypeError):
            assoc.presentation_context_definition_results_list = 45.2

        # implementation_class_uid
        with pytest.raises(ValueError):
            x = assoc.implementation_class_uid

        imp_uid = ImplementationClassUIDNotification()
        assoc.user_information.append(imp_uid)
        with pytest.raises(ValueError):
            x = assoc.implementation_class_uid

    def test_conversion(self):
        """ Check conversion to a PDU produces the correct output """
        assoc = A_ASSOCIATE()
        assoc.application_context_name = "1.2.840.10008.3.1.1.1"
        assoc.calling_ae_title = 'ECHOSCU'
        assoc.called_ae_title = 'ANY-SCP'
        assoc.maximum_length_received = 16382
        assoc.implementation_class_uid = '1.2.826.0.1.3680043.9.3811.0.9.0'

        imp_ver_name = ImplementationVersionNameNotification()
        imp_ver_name.implementation_version_name = 'PYNETDICOM_090'
        assoc.user_information.append(imp_ver_name)

        pc = PresentationContext()
        pc.context_id = 1
        pc.abstract_syntax = '1.2.840.10008.1.1'
        pc.transfer_syntax = ['1.2.840.10008.1.2']
        assoc.presentation_context_definition_list = [pc]

        pdu = A_ASSOCIATE_RQ()
        pdu.from_primitive(assoc)
        data = pdu.encode()

        assert data == (
            b"\x01\x00\x00\x00\x00\xd1\x00\x01\x00\x00\x41\x4e\x59\x2d\x53\x43"
            b"\x50\x20\x20\x20\x20\x20\x20\x20\x20\x20\x45\x43\x48\x4f\x53\x43"
            b"\x55\x20\x20\x20\x20\x20\x20\x20\x20\x20\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x10\x00\x00\x15\x31\x2e"
            b"\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x33\x2e\x31\x2e"
            b"\x31\x2e\x31\x20\x00\x00\x2e\x01\x00\x00\x00\x30\x00\x00\x11\x31"
            b"\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x31\x2e\x31"
            b"\x40\x00\x00\x11\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30"
            b"\x38\x2e\x31\x2e\x32\x50\x00\x00\x3e\x51\x00\x00\x04\x00\x00\x3f"
            b"\xfe\x52\x00\x00\x20\x31\x2e\x32\x2e\x38\x32\x36\x2e\x30\x2e\x31"
            b"\x2e\x33\x36\x38\x30\x30\x34\x33\x2e\x39\x2e\x33\x38\x31\x31\x2e"
            b"\x30\x2e\x39\x2e\x30\x55\x00\x00\x0e\x50\x59\x4e\x45\x54\x44\x49"
            b"\x43\x4f\x4d\x5f\x30\x39\x30"
        )


class TestPrimitive_A_RELEASE(object):
    def test_assignment(self):
        """ Check assignment works correctly """
        assoc = A_RELEASE()
        assert assoc.reason == "normal"

        assoc.result = "affirmative"
        assert assoc.result == "affirmative"

    def test_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        assoc = A_RELEASE()

        with pytest.raises(AttributeError):
            assoc.reason = "something"

        with pytest.raises(ValueError):
            assoc.result = "accepted"


class TestPrimitive_A_ABORT(object):
    def test_assignment(self):
        """ Check assignment works correctly """
        primitive = A_ABORT()
        primitive.abort_source = 0
        assert primitive.abort_source == 0
        primitive.abort_source = 1
        assert primitive.abort_source == 1
        primitive.abort_source = 2
        assert primitive.abort_source == 2

    def test_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        primitive = A_ABORT()

        with pytest.raises(ValueError):
            primitive.abort_source = 3

        with pytest.raises(ValueError):
            primitive.abort_source

    def test_conversion(self):
        """ Check conversion to a PDU produces the correct output """
        primitive = A_ABORT()
        primitive.abort_source = 0

        pdu = A_ABORT_RQ()
        pdu.from_primitive(primitive)
        data = pdu.encode()

        assert data == b"\x07\x00\x00\x00\x00\x04\x00\x00\x00\x00"


class TestPrimitive_A_P_ABORT(object):
    def test_assignment(self):
        """ Check assignment works correctly """
        primitive = A_P_ABORT()
        primitive.provider_reason = 0
        assert primitive.provider_reason == 0
        primitive.provider_reason = 1
        assert primitive.provider_reason == 1
        primitive.provider_reason = 2
        assert primitive.provider_reason == 2
        primitive.provider_reason = 4
        assert primitive.provider_reason == 4
        primitive.provider_reason = 5
        assert primitive.provider_reason == 5
        primitive.provider_reason = 6
        assert primitive.provider_reason == 6

    def test_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        primitive = A_P_ABORT()

        with pytest.raises(ValueError):
            primitive.provider_reason = 3
        with pytest.raises(ValueError):
            primitive.provider_reason

    def test_conversion(self):
        """ Check conversion to a PDU produces the correct output """
        primitive = A_P_ABORT()
        primitive.provider_reason = 4

        pdu = A_ABORT_RQ()
        pdu.from_primitive(primitive)
        data = pdu.encode()

        assert data == b"\x07\x00\x00\x00\x00\x04\x00\x00\x02\x04"


class TestPrimitive_P_DATA(object):
    def test_assignment(self):
        """ Check assignment works correctly """
        primitive = P_DATA()
        primitive.presentation_data_value_list = [[1, b'\x00']]
        assert primitive.presentation_data_value_list == [[1, b'\x00']]

    def test_exceptions(self):
        """ Check incorrect types/values for properties raise exceptions """
        primitive = P_DATA()

        with pytest.raises(TypeError):
            primitive.presentation_data_value_list = ([1, b'\x00'])

        with pytest.raises(TypeError):
            primitive.presentation_data_value_list = [1, b'\x00']

        with pytest.raises(TypeError):
            primitive.presentation_data_value_list = [[b'\x00', 1]]

        with pytest.raises(TypeError):
            primitive.presentation_data_value_list = 'test'

    def test_conversion(self):
        """ Check conversion to a PDU produces the correct output """
        primitive = P_DATA()
        pdv = (
            b"\x03\x00\x00\x00\x00"
            b"\x04\x00\x00\x00\x42\x00\x00\x00\x00\x00\x02\x00\x12\x00\x00"
            b"\x00\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e"
            b"\x31\x2e\x31\x00\x00\x00\x00\x01\x02\x00\x00\x00\x30\x80\x00"
            b"\x00\x20\x01\x02\x00\x00\x00\x01\x00\x00\x00\x00\x08\x02\x00"
            b"\x00\x00\x01\x01\x00\x00\x00\x09\x02\x00\x00\x00\x00\x00"
        )
        primitive.presentation_data_value_list = [[1, pdv]]

        pdu = P_DATA_TF()
        pdu.from_primitive(primitive)
        data = pdu.encode()

        assert data == b"\x04\x00\x00\x00\x00\x54\x00\x00\x00\x50\x01" + pdv

    def test_string(self):
        """ Check the string output."""
        primitive = P_DATA()
        primitive.presentation_data_value_list = [[0, b'\x00\x00']]
        assert 'Byte: 00000000' in primitive.__str__()
        primitive.presentation_data_value_list = [[0, b'\x01\x00']]
        assert 'Byte: 00000001' in primitive.__str__()
        primitive.presentation_data_value_list = [[0, b'\x02\x00']]
        assert 'Byte: 00000010' in primitive.__str__()
        primitive.presentation_data_value_list = [[0, b'\x03\x00']]
        assert 'Byte: 00000011' in primitive.__str__()


class TestServiceParameter(object):
    def test_equality(self):
        """Test equality of ServiceParameter subclasses."""
        prim_a = MaximumLengthNotification()
        prim_b = MaximumLengthNotification()
        assert prim_a == prim_b
        assert not prim_a == 'test'
        assert not prim_a != prim_b
        prim_b.maximum_length_received = 12
        assert not prim_a == prim_b
        assert prim_a != prim_b
