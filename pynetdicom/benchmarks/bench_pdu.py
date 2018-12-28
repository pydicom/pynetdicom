"""Performance tests for the pdu module."""

from io import BytesIO

from pynetdicom.pdu import PDU, PDU_TYPES
from pynetdicom.tests.encoded_pdu_items import (
    presentation_context_rq,
    a_associate_rq,
    a_associate_rq_user_id_ext_neg,
    a_associate_ac,
    a_associate_rj,
    a_release_rq,
    a_release_rp,
    a_abort,
    p_data_tf,
)


class TimePDUDecode(object):
    def setup(self):
        """Setup the test"""
        pass

    def time_decode_assoc_rq_pdu(self):
        """Time decoding an A-ASSOCIATE-RQ PDU."""
        pdu = PDU_TYPES[0x01]()
        for ii in range(1000):
            pdu.decode(a_associate_rq_user_id_ext_neg)

    def time_decode_assoc_ac_pdu(self):
        """Time decoding an A-ASSOCIATE-AC PDU."""
        pdu = PDU_TYPES[0x02]()
        for ii in range(1000):
            pdu.decode(a_associate_ac)

    def time_decode_assoc_rj_pdu(self):
        """Time decoding an A-ASSOCIATE-RJ PDU."""
        pdu = PDU_TYPES[0x03]()
        for ii in range(1000):
            pdu.decode(a_associate_rj)

    def time_decode_data_tf_pdu(self):
        """Time decoding a P-DATA-TF PDU."""
        pdu = PDU_TYPES[0x04]()
        for ii in range(1000):
            pdu.decode(p_data_tf)

    def time_decode_release_rq_pdu(self):
        """Time decoding an A-RELEASE-RQ PDU."""
        pdu = PDU_TYPES[0x05]()
        for ii in range(1000):
            pdu.decode(a_release_rq)

    def time_decode_release_rp_pdu(self):
        """Time decoding an A-RELEASE-RP PDU."""
        pdu = PDU_TYPES[0x06]()
        for ii in range(1000):
            pdu.decode(a_release_rp)

    def time_decode_abort_rq_pdu(self):
        """Time decoding an A-ABORT-RQ PDU."""
        pdu = PDU_TYPES[0x07]()
        for ii in range(1000):
            pdu.decode(a_abort)


class TimePDUEncode(object):
    def setup(self):
        """Setup the test"""
        self.assoc_rq = PDU_TYPES[0x01]()
        self.assoc_rq.decode(a_associate_rq_user_id_ext_neg)

        self.assoc_ac = PDU_TYPES[0x02]()
        self.assoc_ac.decode(a_associate_ac)

        self.assoc_rj = PDU_TYPES[0x03]()
        self.assoc_rj.decode(a_associate_rj)

        self.pdata_tf = PDU_TYPES[0x04]()
        self.pdata_tf.decode(p_data_tf)

        self.release_rq = PDU_TYPES[0x05]()
        self.release_rq.decode(a_release_rq)

        self.release_rp = PDU_TYPES[0x06]()
        self.release_rp.decode(a_release_rp)

        self.abort_rq = PDU_TYPES[0x07]()
        self.abort_rq.decode(a_abort)

    def time_encode_assoc_rq_pdu(self):
        """Time encoding an A-ASSOCIATE-RQ PDU."""
        for ii in range(1000):
            self.assoc_rq.encode()

    def time_encode_assoc_ac_pdu(self):
        """Time encoding an A-ASSOCIATE-AC PDU."""
        for ii in range(1000):
            self.assoc_ac.encode()

    def time_encode_assoc_rj_pdu(self):
        """Time encoding an A-ASSOCIATE-RJ PDU."""
        for ii in range(1000):
            self.assoc_rj.encode()

    def time_encode_pdata_tf_pdu(self):
        """Time encoding a P-DATA-TF PDU."""
        for ii in range(1000):
            self.pdata_tf.encode()

    def time_encode_release_rq_pdu(self):
        """Time encoding an A-RELEASE-RQ PDU."""
        for ii in range(1000):
            self.release_rq.encode()

    def time_encode_release_rp_pdu(self):
        """Time encoding an A-RELEASE-RP PDU."""
        for ii in range(1000):
            self.release_rp.encode()

    def time_encode_abort_rq_pdu(self):
        """Time encoding an A-ABORT-RQ PDU."""
        for ii in range(1000):
            self.abort_rq.encode()
