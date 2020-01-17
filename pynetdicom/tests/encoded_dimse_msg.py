"""Encoding DIMSE messages for use in testing."""
################################### C-STORE ####################################
# MCH Byte: 0x03
# MessageID: 7
# AffectedSOPClassUID: '1.1.1'
# AffectedSOPInstanceUID: '1.2.1'
# Priority: 0x02
# MoveOriginatorApplicationEntityTitle: 'UNITTEST'
# MoveOriginatorMessageID: 3
c_store_rq_cmd = (
    b'\x03\x00\x00\x00\x00\x04\x00\x00\x00\x5e'
    b'\x00\x00\x00\x00\x00\x02\x00\x06\x00\x00'
    b'\x00\x31\x2e\x31\x2e\x31\x00\x00\x00\x00'
    b'\x01\x02\x00\x00\x00\x01\x00\x00\x00\x10'
    b'\x01\x02\x00\x00\x00\x07\x00\x00\x00\x00'
    b'\x07\x02\x00\x00\x00\x02\x00\x00\x00\x00'
    b'\x08\x02\x00\x00\x00\x01\x00\x00\x00\x00'
    b'\x10\x06\x00\x00\x00\x31\x2e\x32\x2e\x31'
    b'\x00\x00\x00\x30\x10\x08\x00\x00\x00\x55'
    b'\x4e\x49\x54\x54\x45\x53\x54\x00\x00\x31'
    b'\x10\x02\x00\x00\x00\x03\x00'
)

# MCH Byte: 0x02
# PatientID: 'Test1101'
# PatientName: s'Tube^HeNe'
c_store_ds = b'\x02\x10\x00\x10\x00\x0a\x00\x00\x00\x54' \
             b'\x75\x62\x65\x5e\x48\x65\x4e\x65\x20\x10' \
             b'\x00\x20\x00\x08\x00\x00\x00\x54\x65\x73' \
             b'\x74\x31\x31\x30\x31'

c_store_rq_cmd_b = (
    b'\x03\x00\x00\x00\x00\x04\x00\x00\x00\xaa'
    b'\x00\x00\x00\x00\x00\x02\x00\x1a\x00\x00'
    b'\x00\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31'
    b'\x30\x30\x30\x38\x2e\x35\x2e\x31\x2e\x34'
    b'\x2e\x31\x2e\x31\x2e\x32\x00\x00\x00\x00'
    b'\x01\x02\x00\x00\x00\x01\x00\x00\x00\x10'
    b'\x01\x02\x00\x00\x00\x07\x00\x00\x00\x00'
    b'\x07\x02\x00\x00\x00\x02\x00\x00\x00\x00'
    b'\x08\x02\x00\x00\x00\x01\x00\x00\x00\x00'
    b'\x10\x3a\x00\x00\x00\x31\x2e\x32\x2e\x33'
    b'\x39\x32\x2e\x32\x30\x30\x30\x33\x36\x2e'
    b'\x39\x31\x31\x36\x2e\x32\x2e\x36\x2e\x31'
    b'\x2e\x34\x38\x2e\x31\x32\x31\x35\x37\x30'
    b'\x39\x30\x34\x34\x2e\x31\x34\x35\x39\x33'
    b'\x31\x36\x32\x35\x34\x2e\x35\x32\x32\x34'
    b'\x34\x31\x00\x00\x00\x30\x10\x0c\x00\x00'
    b'\x00\x55\x4e\x49\x54\x54\x45\x53\x54\x5f'
    b'\x53\x43\x50\x00\x00\x31\x10\x02\x00\x00'
    b'\x00\x03\x00'
)
c_store_rq_ds_b = b'\x02\x10\x00\x10\x00\x0a\x00\x00\x00\x54' \
                  b'\x75\x62\x65\x20\x48\x65\x4e\x65\x20\x10' \
                  b'\x00\x20\x00\x08\x00\x00\x00\x54\x65\x73' \
                  b'\x74\x31\x31\x30\x31'
c_store_rsp_cmd = b'\x03\x00\x00\x00\x00\x04\x00\x00\x00\x4c' \
                  b'\x00\x00\x00\x00\x00\x02\x00\x08\x00\x00' \
                  b'\x00\x31\x2e\x32\x2e\x34\x2e\x31\x30\x00' \
                  b'\x00\x00\x01\x02\x00\x00\x00\x01\x80\x00' \
                  b'\x00\x20\x01\x02\x00\x00\x00\x05\x00\x00' \
                  b'\x00\x00\x08\x02\x00\x00\x00\x01\x01\x00' \
                  b'\x00\x00\x09\x02\x00\x00\x00\x00\x00\x00' \
                  b'\x00\x00\x10\x0c\x00\x00\x00\x31\x2e\x32' \
                  b'\x2e\x34\x2e\x35\x2e\x37\x2e\x38\x00'

#################################### C-ECHO ####################################
#(0000, 0000) Command Group Length                UL: 56
#(0000, 0002) Affected SOP Class UID              UI: Verification SOP Class
#(0000, 0100) Command Field                       US: 48
#(0000, 0110) Message ID                          US: 7
#(0000, 0800) Command Data Set Type               US: 257
c_echo_rq_cmd = b'\x03\x00\x00\x00\x00\x04\x00\x00\x00\x38' \
                b'\x00\x00\x00\x00\x00\x02\x00\x12\x00\x00' \
                b'\x00\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31' \
                b'\x30\x30\x30\x38\x2e\x31\x2e\x31\x00\x00' \
                b'\x00\x00\x01\x02\x00\x00\x00\x30\x00\x00' \
                b'\x00\x10\x01\x02\x00\x00\x00\x07\x00\x00' \
                b'\x00\x00\x08\x02\x00\x00\x00\x01\x01'

# (0000, 0000) Command Group Length                UL: 66
# (0000, 0002) Affected SOP Class UID              UI: Verification SOP Class
# (0000, 0100) Command Field                       US: 32816
# (0000, 0120) Message ID Being Responded To       US: 8
# (0000, 0800) Command Data Set Type               US: 257
# (0000, 0900) Status                              US: 0
c_echo_rsp_cmd = b'\x03\x00\x00\x00\x00\x04\x00\x00\x00\x42' \
                 b'\x00\x00\x00\x00\x00\x02\x00\x12\x00\x00' \
                 b'\x00\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31' \
                 b'\x30\x30\x30\x38\x2e\x31\x2e\x31\x00\x00' \
                 b'\x00\x00\x01\x02\x00\x00\x00\x30\x80\x00' \
                 b'\x00\x20\x01\x02\x00\x00\x00\x08\x00\x00' \
                 b'\x00\x00\x08\x02\x00\x00\x00\x01\x01\x00' \
                 b'\x00\x00\x09\x02\x00\x00\x00\x00\x00'

#################################### C-FIND ####################################
# MCH Byte: 0x03
# CommandGroupLength 74
# AffectedSOPClassUID 1.2.840.10008.5.1.4.1.1.2
# CommandField 0x00 0x20
# MessageID 7
# Priority 2
# CommandDataSetType 1
c_find_rq_cmd = b'\x03\x00\x00\x00\x00\x04\x00\x00\x00\x4a' \
                b'\x00\x00\x00\x00\x00\x02\x00\x1a\x00\x00' \
                b'\x00\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31' \
                b'\x30\x30\x30\x38\x2e\x35\x2e\x31\x2e\x34' \
                b'\x2e\x31\x2e\x31\x2e\x32\x00\x00\x00\x00' \
                b'\x01\x02\x00\x00\x00\x20\x00\x00\x00\x10' \
                b'\x01\x02\x00\x00\x00\x07\x00\x00\x00\x00' \
                b'\x07\x02\x00\x00\x00\x02\x00\x00\x00\x00' \
                b'\x08\x02\x00\x00\x00\x01\x00'

# MCH Byte: 0x02
# QueryRetrieveLevel PATIENT
# PatientID *
c_find_rq_ds = b'\x02\x08\x00\x52\x00\x08\x00\x00\x00\x50' \
               b'\x41\x54\x49\x45\x4e\x54\x20\x10\x00\x20' \
               b'\x00\x02\x00\x00\x00\x2a\x20'
c_find_rsp_cmd = b'\x03\x00\x00\x00\x00\x04\x00\x00\x00\x4a' \
                 b'\x00\x00\x00\x00\x00\x02\x00\x1a\x00\x00' \
                 b'\x00\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31' \
                 b'\x30\x30\x30\x38\x2e\x35\x2e\x31\x2e\x34' \
                 b'\x2e\x31\x2e\x31\x2e\x32\x00\x00\x00\x00' \
                 b'\x01\x02\x00\x00\x00\x20\x80\x00\x00\x20' \
                 b'\x01\x02\x00\x00\x00\x05\x00\x00\x00\x00' \
                 b'\x08\x02\x00\x00\x00\x01\x00\x00\x00\x00' \
                 b'\x09\x02\x00\x00\x00\x00\xff'
c_find_rsp_ds = b'\x02\x08\x00\x52\x00\x08\x00\x00\x00\x50' \
                b'\x41\x54\x49\x45\x4e\x54\x20\x08\x00\x54' \
                b'\x00\x10\x00\x00\x00\x46\x49\x4e\x44\x53' \
                b'\x43\x50\x20\x20\x20\x20\x20\x20\x20\x20' \
                b'\x20\x10\x00\x10\x00\x0c\x00\x00\x00\x41' \
                b'\x4e\x4f\x4e\x5e\x41\x5e\x42\x5e\x43\x5e' \
                b'\x44'

#################################### C-MOVE ####################################
c_move_rq_cmd = (
    b'\x03\x00\x00\x00\x00\x04\x00\x00\x00\x5a'
    b'\x00\x00\x00\x00\x00\x02\x00\x1a\x00\x00'
    b'\x00\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31'
    b'\x30\x30\x30\x38\x2e\x35\x2e\x31\x2e\x34'
    b'\x2e\x31\x2e\x31\x2e\x32\x00\x00\x00\x00'
    b'\x01\x02\x00\x00\x00\x21\x00\x00\x00\x10'
    b'\x01\x02\x00\x00\x00\x07\x00\x00\x00\x00'
    b'\x06\x08\x00\x00\x00\x4d\x4f\x56\x45\x5f'
    b'\x53\x43\x50\x00\x00\x00\x07\x02\x00\x00'
    b'\x00\x02\x00\x00\x00\x00\x08\x02\x00\x00'
    b'\x00\x01\x00'
)
c_move_rq_ds = b'\x02\x08\x00\x52\x00\x08\x00\x00\x00\x50' \
               b'\x41\x54\x49\x45\x4e\x54\x20\x10\x00\x20' \
               b'\x00\x02\x00\x00\x00\x2a\x20'
c_move_rsp_cmd = b'\x03\x00\x00\x00\x00\x04\x00\x00\x00\x72' \
                 b'\x00\x00\x00\x00\x00\x02\x00\x1a\x00\x00' \
                 b'\x00\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31' \
                 b'\x30\x30\x30\x38\x2e\x35\x2e\x31\x2e\x34' \
                 b'\x2e\x31\x2e\x31\x2e\x32\x00\x00\x00\x00' \
                 b'\x01\x02\x00\x00\x00\x21\x80\x00\x00\x20' \
                 b'\x01\x02\x00\x00\x00\x05\x00\x00\x00\x00' \
                 b'\x08\x02\x00\x00\x00\x01\x00\x00\x00\x00' \
                 b'\x09\x02\x00\x00\x00\x00\xff\x00\x00\x20' \
                 b'\x10\x02\x00\x00\x00\x03\x00\x00\x00\x21' \
                 b'\x10\x02\x00\x00\x00\x01\x00\x00\x00\x22' \
                 b'\x10\x02\x00\x00\x00\x02\x00\x00\x00\x23' \
                 b'\x10\x02\x00\x00\x00\x04\x00'
c_move_rsp_ds = b'\x02\x08\x00\x52\x00\x08\x00\x00\x00\x50' \
                b'\x41\x54\x49\x45\x4e\x54\x20\x10\x00\x20' \
                b'\x00\x02\x00\x00\x00\x2a\x20'

##################################### C-GET ####################################
# (0000, 0000) Command Group Length                UL: 74
# (0000, 0002) Affected SOP Class UID              UI: CT Image Storage
# (0000, 0100) Command Field                       US: 16
# (0000, 0110) Message ID                          US: 7
# (0000, 0700) Priority                            US: 2
# (0000, 0800) Command Data Set Type               US: 1
c_get_rq_cmd = b'\x03\x00\x00\x00\x00\x04\x00\x00\x00\x4a' \
               b'\x00\x00\x00\x00\x00\x02\x00\x1a\x00\x00' \
               b'\x00\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31' \
               b'\x30\x30\x30\x38\x2e\x35\x2e\x31\x2e\x34' \
               b'\x2e\x31\x2e\x31\x2e\x32\x00\x00\x00\x00' \
               b'\x01\x02\x00\x00\x00\x10\x00\x00\x00\x10' \
               b'\x01\x02\x00\x00\x00\x07\x00\x00\x00\x00' \
               b'\x07\x02\x00\x00\x00\x02\x00\x00\x00\x00' \
               b'\x08\x02\x00\x00\x00\x01\x00'
c_get_rq_ds = b'\x02\x08\x00\x52\x00\x08\x00\x00\x00\x50' \
              b'\x41\x54\x49\x45\x4e\x54\x20\x10\x00\x20' \
              b'\x00\x02\x00\x00\x00\x2a\x20'
c_get_rsp_cmd = b'\x03\x00\x00\x00\x00\x04\x00\x00\x00\x72' \
                b'\x00\x00\x00\x00\x00\x02\x00\x1a\x00\x00' \
                b'\x00\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31' \
                b'\x30\x30\x30\x38\x2e\x35\x2e\x31\x2e\x34' \
                b'\x2e\x31\x2e\x31\x2e\x32\x00\x00\x00\x00' \
                b'\x01\x02\x00\x00\x00\x10\x80\x00\x00\x20' \
                b'\x01\x02\x00\x00\x00\x05\x00\x00\x00\x00' \
                b'\x08\x02\x00\x00\x00\x01\x00\x00\x00\x00' \
                b'\x09\x02\x00\x00\x00\x00\xff\x00\x00\x20' \
                b'\x10\x02\x00\x00\x00\x03\x00\x00\x00\x21' \
                b'\x10\x02\x00\x00\x00\x01\x00\x00\x00\x22' \
                b'\x10\x02\x00\x00\x00\x02\x00\x00\x00\x23' \
                b'\x10\x02\x00\x00\x00\x04\x00'
c_get_rsp_ds = b'\x02\x08\x00\x52\x00\x08\x00\x00\x00\x50' \
               b'\x41\x54\x49\x45\x4e\x54\x20\x10\x00\x20' \
               b'\x00\x02\x00\x00\x00\x2a\x20'
