"""Offline checks for password redaction in standard association logging."""

import logging
from types import SimpleNamespace

import pytest

from pynetdicom._handlers import _receive_associate_rq, _send_associate_rq
from pynetdicom.acse import APPLICATION_CONTEXT_NAME
from pynetdicom.pdu import A_ASSOCIATE_RQ
from pynetdicom.pdu_primitives import (
    A_ASSOCIATE,
    ImplementationClassUIDNotification,
    MaximumLengthNotification,
    UserIdentityNegotiation,
)


@pytest.mark.parametrize("handler", [_receive_associate_rq, _send_associate_rq])
def test_standard_association_log_redacts_password(handler, caplog):
    password = "synthetic-password-must-not-appear"
    primitive = A_ASSOCIATE()
    primitive.application_context_name = APPLICATION_CONTEXT_NAME
    primitive.calling_ae_title = "SYNTHETIC_SCU"
    primitive.called_ae_title = "SYNTHETIC_SCP"
    maximum = MaximumLengthNotification()
    maximum.maximum_length_received = 16382
    implementation = ImplementationClassUIDNotification()
    implementation.implementation_class_uid = "1.2.3.4"
    identity = UserIdentityNegotiation()
    identity.user_identity_type = 2
    identity.primary_field = b"synthetic-user"
    identity.secondary_field = password.encode("utf-8")
    identity.positive_response_requested = False
    primitive.user_information = [maximum, implementation, identity]
    pdu = A_ASSOCIATE_RQ()
    pdu.from_primitive(primitive)

    with caplog.at_level(logging.DEBUG, logger="pynetdicom"):
        lines = handler(SimpleNamespace(pdu=pdu))

    returned = "\n".join(lines)
    assert "Password: [redacted]" in returned
    assert password not in returned
    assert "Password: [redacted]" in caplog.text
    assert password not in caplog.text
