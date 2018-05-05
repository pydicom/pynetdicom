"""Performance tests for the pdu module."""

from io import BytesIO

from pynetdicom3.pdu import PDU
from pynetdicom3.tests.encoded_pdu_items import a_associate_rq


class TimePDU(object):
    def setup(self):
        """Setup the test"""
        self.bytestream_io = BytesIO(a_associate_rq)
        self.bytestream_io.seek(0)
        self.bytestream = a_associate_rq
        self.pdu = PDU()

    def time_next_item_type(self):
        """Time PDU._next_item_type"""
        for ii in range(1000):
            assert self.pdu._next_item_type(self.bytestream) == 0x01

        assert self.pdu._next_item_type(b'') is None

    def time_next_item(self):
        """Time PDU._next_item_type"""
        for ii in range(1000):
            self.pdu._next_item(self.bytestream_io)

    def time_opt_next_item(self):
        """Time PDU._next_item_type"""
        for ii in range(1000):
            self.pdu._opt_next_item(self.bytestream_io)
