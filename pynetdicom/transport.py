"""Implementation of the Transport Service."""


# Transport primitives
CONNECTION_INDICATION = None
CONNECTION_CONFIRMATION = None
CONNECTION_OPEN = None
CONNECTION_CLOSED = None

_UNPACK_UCHAR = Struct('B').unpack
_UNPACK_ULONG = Struct('>L').unpack


class TransportService(object):
    def __init__(self):
        pass

    def register_callback(self):
        pass

    def unregister_callback(self):
        pass

    def process_primitive(self, primitive):
        pass

    def open_connection(self, assoc):
        pass

    def close_connection(self, assoc):
        pass

    def monitor_connection(self):
        while not assoc._kill:
            try:
                ready, _, _ = select.select([assoc._socket], [], [], 0.5)
            except ValueError:
                # Evt17: closed connection indication
                assoc._event_queue.put('Evt17')
                break

            if ready:
                self.read_data(assoc._socket)

    def read_data(self, assoc):
        sock = assoc._socket

        bytestream = bytes()

        # Try and read the PDU type and length from the socket
        try:
            bytestream += sock.recv(6)
        except socket.error:
            # Evt17: connection closed indication
            primitive = CONNECTION_CLOSED()
            assoc._event_queue.put('Evt17')

        # Check that we managed to read data
        if not bytestream or len(bytestream) != 6:
            # Evt17: connection closed indication
            primitive = CONNECTION_CLOSED()
            assoc._event_queue.put('Evt17')

        # Byte 1 is always the PDU type
        pdu_type = _UNPACK_UCHAR(bytestream[0:1])[0]
        # Byte 2 is always reserved
        # Bytes 3-6 are always the PDU length
        pdu_length = _UNPACK_ULONG(bytestream[2:])[0]

        # If the `pdu_type` is unrecognised
        if pdu_type not in PDU_TYPES:
            # Evt19: unrecognised or invalid PDU
            assoc._event_queue.put('Evt19')

        # Try and read the rest of the PDU
        try:
            bytestream += sock.recv(pdu_length)
        except socket.error:
            # Evt17: connection closed indication
            primitive = CONNECTION_CLOSED()
            assoc._event_queue.put('Evt17')

        # Check that the PDU data was completely read
        if len(bytestream) != 6 + pdu_length:
            # Evt17: connection closed indication
            primitive = CONNECTION_CLOSED()
            assoc._event_queue.put('Evt17')

        # Convert the bytestream to the corresponding PDU class
        (pdu, event) = PDU_TYPES[pdu_type]
        try:
            pdu = pdu(bytestream)
        except Exception as exc:
            LOGGER.error('Unable to read the received PDU')
            LOGGER.exception(exc)
            assoc._event_queue.put(event)

        assoc.received_pdu.put(pdu)

    def send_data(assoc, pdu):
        pass


# {PDU's first byte : (PDU class, PDU received on transport connection event)}
PDU_TYPES = {
    0x01 : (A_ASSOCIATE_RQ, 'Evt6'),
    0x02 : (A_ASSOCIATE_AC, 'Evt3'),
    0x03 : (A_ASSOCIATE_RJ, 'Evt4'),
    0x04 : (P_DATA_TF, 'Evt10'),
    0x05 : (A_RELEASE_RQ, 'Evt12'),
    0x06 : (A_RELEASE_RP, 'Evt13'),
    0x07 : (A_ABORT_RQ, 'Evt16'),
}
