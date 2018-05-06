"""Performance tests for the pdu module."""

from io import BytesIO

from pynetdicom3.pdu import PDU, PDU_TYPES
from pynetdicom3.tests.encoded_pdu_items import (
    presentation_context_rq, a_associate_rq, a_associate_rq_user_id_ext_neg
)


class TimePDU(object):
    def setup(self):
        """Setup the test"""
        self.item_bytestream_io = BytesIO(presentation_context_rq)
        self.item_bytestream_io.seek(0)
        self.item_bytestream = presentation_context_rq
        self.pdu = PDU()
        self.pdu_bytestream = a_associate_rq_user_id_ext_neg

    def time_next_item(self):
        """Time PDU._next_item_type"""
        for ii in range(1000):
            self.pdu._next_item(self.item_bytestream_io)

    def time_decode_pdu(self):
        """Time PDU._next_item_type"""
        pdu = PDU_TYPES[0x01]()
        for ii in range(1000):
            pdu.Decode(self.pdu_bytestream)

    def time_opt_decode_pdu(self):
        """Time PDU._next_item_type"""
        pdu = PDU_TYPES[0x01]()
        for ii in range(1000):
            pdu._dev_decode(self.pdu_bytestream)
