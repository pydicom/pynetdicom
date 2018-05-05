"""Performance tests for the pdu module."""

from pynetdicom3.pdu import PDU
from pynetdicom3.tests.encoded_pdu_items import a_associate_rq


class TimePDU(object):
    def setup(self):
        """Setup the test"""
        self.bytestream = a_associate_rq
        self.pdu = PDU()

    def time_next_item_type(self):
        """Time PDU._next_item_type"""
        for ii in range(1000):
            self.pdu._next_item_type(self.bytestream)

        assert self.pdu._next_item_type(self.bytestream) == 0x01
