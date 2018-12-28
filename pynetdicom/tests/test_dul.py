#!/usr/bin/env python
"""DUL service testing"""

import logging
import socket

import pytest

from pynetdicom.dul import DULServiceProvider
from pynetdicom.pdu import A_ASSOCIATE_RQ, A_ASSOCIATE_AC, A_ASSOCIATE_RJ, \
                            A_RELEASE_RQ, A_RELEASE_RP, P_DATA_TF, A_ABORT_RQ
from pynetdicom.pdu_primitives import A_ASSOCIATE, A_RELEASE, A_ABORT, P_DATA

LOGGER = logging.getLogger('pynetdicom')
LOGGER.setLevel(logging.CRITICAL)


class DummyACSE(object):
    """Dummy ACSE class"""
    @staticmethod
    def debug_receive_associate_rq(): pass
    @staticmethod
    def debug_receive_associate_ac(): pass
    @staticmethod
    def debug_receive_associate_rj(): pass
    @staticmethod
    def debug_receive_data_tf(): pass
    @staticmethod
    def debug_receive_release_rq(): pass
    @staticmethod
    def debug_receive_release_rp(): pass
    @staticmethod
    def debug_receive_abort(): pass


class DummyAssociation(object):
    """Dummy Association class"""
    acse = DummyACSE()


class DummyDUL(DULServiceProvider):
    """Dummy DUL class"""
    def __init__(self):
        self.assoc = DummyAssociation()


class TestDUL(object):
    """Run tests on DUL service provider."""
    def test__pdu_to_event(self):
        """Test that good PDU paramters return expected results"""
        dul = DummyDUL()
        p2e = dul._pdu_to_event

        pdu_types = [A_ASSOCIATE_RQ(), A_ASSOCIATE_AC(), A_ASSOCIATE_RJ(),
                     P_DATA_TF(), A_RELEASE_RQ(), A_RELEASE_RP(),
                     A_ABORT_RQ(), 'TEST']
        event_str = ['Evt6', 'Evt3', 'Evt4',
                     'Evt10', 'Evt12', 'Evt13',
                     'Evt16', 'Evt19']

        for pdu, evt in zip(pdu_types, event_str):
            assert p2e(pdu) == evt

    def test__socket_to_pdu(self):
        """Test that good PDU paramters return expected results"""
        dul = DummyDUL()
        assert dul._socket_to_pdu(b'\x99\x98') is None

    def test__primitive_to_event(self):
        """Test that parameter returns expected results"""
        dul = DummyDUL()
        p2e = dul._primitive_to_event

        primitive = A_ASSOCIATE()
        primitive.result = None
        assert p2e(primitive) == 'Evt1'
        primitive.result = 0
        assert p2e(primitive) == 'Evt7'
        primitive.result = 1
        assert p2e(primitive) == 'Evt8'

        primitive = A_RELEASE()
        primitive.result = None
        assert p2e(primitive) == 'Evt11'
        primitive.result = 'affirmative'
        assert p2e(primitive) == 'Evt14'

        primitive = A_ABORT()
        assert p2e(primitive) == 'Evt15'

        primitive = P_DATA()
        assert p2e(primitive) == 'Evt9'

        with pytest.raises(ValueError):
            p2e('TEST')
