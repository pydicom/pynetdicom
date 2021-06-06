"""Encoding PDUs for use in testing."""
############################# A-ASSOCIATE-RQ PDU #############################
# Called AET: ANY-SCP
# Calling AET: ECHOSCU
# Application Context Name: 1.2.840.10008.3.1.1.1
# Presentation Context Items:
#   Presentation Context ID: 1
#   Abstract Syntax: 1.2.840.10008.1.1 Verification SOP Class
#   Transfer Syntax: 1.2.840.10008.1.2 Implicit VR Little Endian
# User Information
#   Max Length Received: 16382
#   Implementation Class UID: 1.2.826.0.1.3680043.9.3811.0.9.0
#   Implementation Version Name: PYNETDICOM_090
a_associate_rq = (
    b"\x01\x00\x00\x00\x00\xd1\x00\x01\x00\x00\x41\x4e\x59\x2d"
    b"\x53\x43\x50\x20\x20\x20\x20\x20\x20\x20\x20\x20\x45\x43"
    b"\x48\x4f\x53\x43\x55\x20\x20\x20\x20\x20\x20\x20\x20\x20"
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
    b"\x00\x00\x00\x00\x10\x00\x00\x15\x31\x2e\x32\x2e\x38\x34"
    b"\x30\x2e\x31\x30\x30\x30\x38\x2e\x33\x2e\x31\x2e\x31\x2e"
    b"\x31\x20\x00\x00\x2e\x01\x00\x00\x00\x30\x00\x00\x11\x31"
    b"\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x31"
    b"\x2e\x31\x40\x00\x00\x11\x31\x2e\x32\x2e\x38\x34\x30\x2e"
    b"\x31\x30\x30\x30\x38\x2e\x31\x2e\x32\x50\x00\x00\x3e\x51"
    b"\x00\x00\x04\x00\x00\x3f\xfe\x52\x00\x00\x20\x31\x2e\x32"
    b"\x2e\x38\x32\x36\x2e\x30\x2e\x31\x2e\x33\x36\x38\x30\x30"
    b"\x34\x33\x2e\x39\x2e\x33\x38\x31\x31\x2e\x30\x2e\x39\x2e"
    b"\x30\x55\x00\x00\x0e\x50\x59\x4e\x45\x54\x44\x49\x43\x4f"
    b"\x4d\x5f\x30\x39\x30"
)

# Called AET: ANY-SCP
# Calling AET: ECHOSCU
# Application Context Name: 1.2.840.10008.3.1.1.1
# Presentation Context Items:
#   Presentation Context ID: 1
#   Abstract Syntax: 1.2.840.10008.1.1 Verification SOP Class
#   Transfer Syntax: 1.2.840.10008.1.2 Implicit VR Little Endian
# User Information
#   Max Length Received: 16382
#   Implementation Class UID: 1.2.826.0.1.3680043.9.3811.0.9.0
#   Implementation Version Name: PYNETDICOM_090
#   User Identity
#       Type: 1
#       Response requested: 1
#       Primary field: pynetdicom
#       Secondary field: (none)
#   AsynchronousOperationsWindow
#       Max operations invoked: 5
#       Max operations performed: 5
a_associate_rq_user_async = (
    b'\x01\x00\x00\x00\x00\xed\x00\x01\x00\x00\x41\x4e\x59\x2d\x53\x43'
    b'\x50\x20\x20\x20\x20\x20\x20\x20\x20\x20\x45\x43\x48\x4f\x53\x43'
    b'\x55\x20\x20\x20\x20\x20\x20\x20\x20\x20\x00\x00\x00\x00\x00\x00'
    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x10\x00\x00\x15\x31\x2e'
    b'\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x33\x2e\x31\x2e'
    b'\x31\x2e\x31\x20\x00\x00\x2e\x01\x00\x00\x00\x30\x00\x00\x11\x31'
    b'\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x31\x2e\x31'
    b'\x40\x00\x00\x11\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30'
    b'\x38\x2e\x31\x2e\x32\x50\x00\x00\x5a\x51\x00\x00\x04\x00\x00\x3f'
    b'\xfe\x52\x00\x00\x20\x31\x2e\x32\x2e\x38\x32\x36\x2e\x30\x2e\x31'
    b'\x2e\x33\x36\x38\x30\x30\x34\x33\x2e\x39\x2e\x33\x38\x31\x31\x2e'
    b'\x30\x2e\x39\x2e\x30\x55\x00\x00\x0e\x50\x59\x4e\x45\x54\x44\x49'
    b'\x43\x4f\x4d\x5f\x30\x39\x30\x58\x00\x00\x10\x01\x01\x00\x0a\x70'
    b'\x79\x6e\x65\x74\x64\x69\x63\x6f\x6d\x00\x00\x53\x00\x00\x04\x00'
    b'\x05\x00\x05'
)

# Called AET: ANY-SCP
# Calling AET: GETSCU
# Application Context Name: 1.2.840.10008.3.1.1.1
# Presentation Context Items:
#   Presentation Context ID: 1
#   Abstract Syntax: 1.2.840.10008.5.1.4.1.1.2 CT Image Storage
#   Transfer Syntax: 1.2.840.10008.1.2.1 Explicit VR Little Endian
# User Information
#   Max Length Received: 16382
#   Implementation Class UID: 1.2.826.0.1.3680043.9.3811.0.9.0
#   Implementation Version Name: PYNETDICOM_090
#   SCP/SCU Role Selection
#       SOP Class: 1.2.840.10008.5.1.4.1.1.2 CT Image Storage
#       SCU Role: 0
#       SCP Role: 1
a_associate_rq_role = (
    b'\x01\x00\x00\x00\x00\xfc\x00\x01\x00\x00\x41\x4e\x59\x2d\x53\x43'
    b'\x50\x20\x20\x20\x20\x20\x20\x20\x20\x20\x47\x45\x54\x53\x43\x55'
    b'\x20\x20\x20\x20\x20\x20\x20\x20\x20\x20\x00\x00\x00\x00\x00\x00'
    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x10\x00\x00\x15\x31\x2e'
    b'\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x33\x2e\x31\x2e'
    b'\x31\x2e\x31\x20\x00\x00\x38\x01\x00\x00\x00\x30\x00\x00\x19\x31'
    b'\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x35\x2e\x31'
    b'\x2e\x34\x2e\x31\x2e\x31\x2e\x32\x40\x00\x00\x13\x31\x2e\x32\x2e'
    b'\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x31\x2e\x32\x2e\x31\x50'
    b'\x00\x00\x5f\x51\x00\x00\x04\x00\x00\x3f\xfe\x52\x00\x00\x20\x31'
    b'\x2e\x32\x2e\x38\x32\x36\x2e\x30\x2e\x31\x2e\x33\x36\x38\x30\x30'
    b'\x34\x33\x2e\x39\x2e\x33\x38\x31\x31\x2e\x30\x2e\x39\x2e\x30\x55'
    b'\x00\x00\x0e\x50\x59\x4e\x45\x54\x44\x49\x43\x4f\x4d\x5f\x30\x39'
    b'\x30\x54\x00\x00\x1d\x00\x19\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31'
    b'\x30\x30\x30\x38\x2e\x35\x2e\x31\x2e\x34\x2e\x31\x2e\x31\x2e\x32'
    b'\x00\x01'
)

# Called AET: ANY-SCP
# Calling AET: STORESCU
# Application Context Name: 1.2.840.10008.3.1.1.1
# Presentation Context Items:
#   Presentation Context ID: 1
#   Abstract Syntax: 1.2.840.10008.5.1.4.1.1.2 CT Image Storage
#   Transfer Syntax: 1.2.840.10008.1.2 Implicit VR Little Endian
#   Transfer Syntax: 1.2.840.10008.1.2.1 Explicit VR Little Endian
#   Transfer Syntax: 1.2.840.10008.1.2.2 Explicit VR Big Endian
# User Information
#   Max Length Received: 16384
#   Implementation Class UID: 1.2.276.0.7230010.3.0.3.6.0
#   Implementation Version Name: OFFIS_DCMTK_360
#   User Identity
#       Type: w
#       Response requested: 0
#       Primary field: pynetdicom
#       Secondary field: p4ssw0rd
a_associate_rq_user_id_user_pass = (
    b'\x01\x00\x00\x00\x01\x1f\x00\x01\x00\x00\x41\x4e\x59\x2d\x53\x43'
    b'\x50\x20\x20\x20\x20\x20\x20\x20\x20\x20\x53\x54\x4f\x52\x45\x53'
    b'\x43\x55\x20\x20\x20\x20\x20\x20\x20\x20\x00\x00\x00\x00\x00\x00'
    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x10\x00\x00\x15\x31\x2e'
    b'\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x33\x2e\x31\x2e'
    b'\x31\x2e\x31\x20\x00\x00\x64\x01\x00\xff\x00\x30\x00\x00\x19\x31'
    b'\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x35\x2e\x31'
    b'\x2e\x34\x2e\x31\x2e\x31\x2e\x32\x40\x00\x00\x13\x31\x2e\x32\x2e'
    b'\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x31\x2e\x32\x2e\x31\x40'
    b'\x00\x00\x13\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38'
    b'\x2e\x31\x2e\x32\x2e\x32\x40\x00\x00\x11\x31\x2e\x32\x2e\x38\x34'
    b'\x30\x2e\x31\x30\x30\x30\x38\x2e\x31\x2e\x32\x50\x00\x00\x56\x51'
    b'\x00\x00\x04\x00\x00\x40\x00\x52\x00\x00\x1b\x31\x2e\x32\x2e\x32'
    b'\x37\x36\x2e\x30\x2e\x37\x32\x33\x30\x30\x31\x30\x2e\x33\x2e\x30'
    b'\x2e\x33\x2e\x36\x2e\x30\x55\x00\x00\x0f\x4f\x46\x46\x49\x53\x5f'
    b'\x44\x43\x4d\x54\x4b\x5f\x33\x36\x30\x58\x00\x00\x18\x02\x00\x00'
    b'\x0a\x70\x79\x6e\x65\x74\x64\x69\x63\x6f\x6d\x00\x08\x70\x34\x73'
    b'\x73\x77\x30\x72\x64'
)

# Called AET: ANY-SCP
# Calling AET: ECHOSCU
# Application Context Name: 1.2.840.10008.3.1.1.1
# Presentation Context Item:
#   Presentation Context ID: 1
#   Abstract Syntax: 1.2.840.10008.1.1 Verification SOP Class
#   Transfer Syntax: 1.2.840.10008.1.2 Implicit VR Little Endian
# Presentation Context Item:
#   Presentation Context ID: 3
#   Abstract Syntax: 1.2.840.10008.5.1.4.1.1.2 CT Image Storage
#   Transfer Syntax: 1.2.840.10008.1.2 Implicit VR Little Endian
# Presentation Context Item:
#   Presentation Context ID: 5
#   Abstract Syntax: 1.2.840.10008.5.1.4.1.1.4 MR Image Storage
#   Transfer Syntax: 1.2.840.10008.1.2 Implicit VR Little Endian
# User Information
#   Max Length Received: 16384
#   Implementation Class UID: 1.2.826.0.1.3680043.9.3811.0.9.0
#   Implementation Version Name: PYNETDICOM_090
#   User Identity
#       Type: 1
#       Response requested: 1
#       Primary field: pynetdicom
#       Secondary field: (none)
#   AsynchronousOperationsWindow
#       Max operations invoked: 5
#       Max operations performed: 5
#   SOP Class Extended Negotiation Item
#       SOP Class: 1.2.840.10008.5.1.4.1.1.2 CT Image Storage
#       Service Class App Info: b'\x02\x00\x03\x00\x01\x00'
#   SOP Class Extended Negotiation Item
#       SOP Class: 1.2.840.10008.5.1.4.1.1.4 MR Image Storage
#       Service Class App Info: b'\x02\x00\x03\x00\x01\x00'
a_associate_rq_user_id_ext_neg = (
    b'\x01\x00\x00\x00\x01\xab\x00\x01\x00\x00\x41\x4e\x59\x2d\x53\x43'
    b'\x50\x20\x20\x20\x20\x20\x20\x20\x20\x20\x45\x43\x48\x4f\x53\x43'
    b'\x55\x20\x20\x20\x20\x20\x20\x20\x20\x20\x00\x00\x00\x00\x00\x00'
    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x10\x00\x00\x15\x31\x2e'
    b'\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x33\x2e\x31\x2e'
    b'\x31\x2e\x31\x20\x00\x00\x2e\x01\x00\x00\x00\x30\x00\x00\x11\x31'
    b'\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x31\x2e\x31'
    b'\x40\x00\x00\x11\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30'
    b'\x38\x2e\x31\x2e\x32\x20\x00\x00\x36\x03\x00\x00\x00\x30\x00\x00'
    b'\x19\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x35'
    b'\x2e\x31\x2e\x34\x2e\x31\x2e\x31\x2e\x32\x40\x00\x00\x11\x31\x2e'
    b'\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x31\x2e\x32\x20'
    b'\x00\x00\x36\x05\x00\x00\x00\x30\x00\x00\x19\x31\x2e\x32\x2e\x38'
    b'\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x35\x2e\x31\x2e\x34\x2e\x31'
    b'\x2e\x31\x2e\x34\x40\x00\x00\x11\x31\x2e\x32\x2e\x38\x34\x30\x2e'
    b'\x31\x30\x30\x30\x38\x2e\x31\x2e\x32\x50\x00\x00\xa4\x51\x00\x00'
    b'\x04\x00\x00\x3f\xfe\x52\x00\x00\x20\x31\x2e\x32\x2e\x38\x32\x36'
    b'\x2e\x30\x2e\x31\x2e\x33\x36\x38\x30\x30\x34\x33\x2e\x39\x2e\x33'
    b'\x38\x31\x31\x2e\x30\x2e\x39\x2e\x30\x55\x00\x00\x0e\x50\x59\x4e'
    b'\x45\x54\x44\x49\x43\x4f\x4d\x5f\x30\x39\x30\x58\x00\x00\x10\x01'
    b'\x01\x00\x0a\x70\x79\x6e\x65\x74\x64\x69\x63\x6f\x6d\x00\x00\x53'
    b'\x00\x00\x04\x00\x05\x00\x05\x56\x00\x00\x21\x00\x19\x31\x2e\x32'
    b'\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x35\x2e\x31\x2e\x34'
    b'\x2e\x31\x2e\x31\x2e\x32\x02\x00\x03\x00\x01\x00\x56\x00\x00\x21'
    b'\x00\x19\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e'
    b'\x35\x2e\x31\x2e\x34\x2e\x31\x2e\x31\x2e\x34\x02\x00\x03\x00\x01'
    b'\x00'
)

# Needs to be updated - no presentation context items?
a_associate_rq_com_ext_neg = (
    b'\x02\x00\x00\x00\x01\x49\x00\x01\x00\x00\x41\x4e\x59\x2d\x53\x43'
    b'\x50\x20\x20\x20\x20\x20\x20\x20\x20\x20\x45\x43\x48\x4f\x53\x43'
    b'\x55\x20\x20\x20\x20\x20\x20\x20\x20\x20\x00\x00\x00\x00\x00\x00'
    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x10\x00\x00\x15\x31\x2e'
    b'\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x33\x2e\x31\x2e'
    b'\x31\x2e\x31\x21\x00\x00\x19\x01\x00\x00\x00\x40\x00\x00\x11\x31'
    b'\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x31\x2e\x32'
    b'\x21\x00\x00\x19\x03\x00\x00\x00\x40\x00\x00\x11\x31\x2e\x32\x2e'
    b'\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x31\x2e\x32\x21\x00\x00'
    b'\x19\x05\x00\x00\x00\x40\x00\x00\x11\x31\x2e\x32\x2e\x38\x34\x30'
    b'\x2e\x31\x30\x30\x30\x38\x2e\x31\x2e\x32\x50\x00\x00\x91\x51\x00'
    b'\x00\x04\x00\x00\x40\x00\x52\x00\x00\x20\x31\x2e\x32\x2e\x38\x32'
    b'\x36\x2e\x30\x2e\x31\x2e\x33\x36\x38\x30\x30\x34\x33\x2e\x39\x2e'
    b'\x33\x38\x31\x31\x2e\x30\x2e\x39\x2e\x30\x55\x00\x00\x0e\x50\x59'
    b'\x4e\x45\x54\x44\x49\x43\x4f\x4d\x5f\x30\x39\x30\x57\x00\x00\x4f'
    b'\x00\x19\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e'
    b'\x35\x2e\x31\x2e\x34\x2e\x31\x2e\x31\x2e\x34\x00\x11\x31\x2e\x32'
    b'\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x34\x2e\x32\x00\x1f'
    b'\x00\x1d\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e'
    b'\x35\x2e\x31\x2e\x34\x2e\x31\x2e\x31\x2e\x38\x38\x2e\x32\x32'
)

############################# A-ASSOCIATE-AC PDU #############################
# Called AET: ANY-SCP
# Calling AET: ECHOSCU
# Application Context Name: 1.2.840.10008.3.1.1.1
# Presentation Context Items:
#   Presentation Context ID: 1
#   Result: Accepted
#   Transfer Syntax: 1.2.840.10008.1.2 Implicit VR Little Endian
# User Information
#   Max Length Received: 16384
#   Implementation Class UID: 1.2.276.0.7230010.3.0.3.6.0
#   Implementation Version Name: OFFIS_DCMTK_360
a_associate_ac = (
    b'\x02\x00\x00\x00\x00\xb8\x00\x01\x00\x00\x41\x4e\x59\x2d'
    b'\x53\x43\x50\x20\x20\x20\x20\x20\x20\x20\x20\x20\x45\x43'
    b'\x48\x4f\x53\x43\x55\x20\x20\x20\x20\x20\x20\x20\x20\x20'
    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    b'\x00\x00\x00\x00\x10\x00\x00\x15\x31\x2e\x32\x2e\x38\x34'
    b'\x30\x2e\x31\x30\x30\x30\x38\x2e\x33\x2e\x31\x2e\x31\x2e'
    b'\x31\x21\x00\x00\x19\x01\x00\x00\x00\x40\x00\x00\x11\x31'
    b'\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x31'
    b'\x2e\x32\x50\x00\x00\x3a\x51\x00\x00\x04\x00\x00\x40\x00'
    b'\x52\x00\x00\x1b\x31\x2e\x32\x2e\x32\x37\x36\x2e\x30\x2e'
    b'\x37\x32\x33\x30\x30\x31\x30\x2e\x33\x2e\x30\x2e\x33\x2e'
    b'\x36\x2e\x30\x55\x00\x00\x0f\x4f\x46\x46\x49\x53\x5f\x44'
    b'\x43\x4d\x54\x4b\x5f\x33\x36\x30'
)

# Called AET: ANY-SCP
# Calling AET: ECHOSCU
# Application Context Name: 1.2.840.10008.3.1.1.1
# Presentation Context Items:
#   Presentation Context ID: 1
#   Result: Accepted
#   Transfer Syntax: 1.2.840.10008.1.2 Implicit VR Little Endian
# User Information
#   Max Length Received: 16384
#   Implementation Class UID: 1.2.276.0.7230010.3.0.3.6.0
#   Implementation Version Name: OFFIS_DCMTK_360
#   User Identity AC
#       Server response: b'Accepted'
a_associate_ac_user = (
    b'\x02\x00\x00\x00\x00\xb8\x00\x01\x00\x00'
    b'\x41\x4e\x59\x2d\x53\x43\x50\x20\x20\x20'
    b'\x20\x20\x20\x20\x20\x20\x45\x43\x48\x4f'
    b'\x53\x43\x55\x20\x20\x20\x20\x20\x20\x20'
    b'\x20\x20\x00\x00\x00\x00\x00\x00\x00\x00'
    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    b'\x00\x00\x00\x00\x10\x00\x00\x15\x31\x2e'
    b'\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30'
    b'\x38\x2e\x33\x2e\x31\x2e\x31\x2e\x31\x21'
    b'\x00\x00\x19\x01\x00\x00\x00\x40\x00\x00'
    b'\x11\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31'
    b'\x30\x30\x30\x38\x2e\x31\x2e\x32\x50\x00'
    b'\x00\x48\x51\x00\x00\x04\x00\x00\x40\x00'
    b'\x52\x00\x00\x1b\x31\x2e\x32\x2e\x32\x37'
    b'\x36\x2e\x30\x2e\x37\x32\x33\x30\x30\x31'
    b'\x30\x2e\x33\x2e\x30\x2e\x33\x2e\x36\x2e'
    b'\x30\x55\x00\x00\x0f\x4f\x46\x46\x49\x53'
    b'\x5f\x44\x43\x4d\x54\x4b\x5f\x33\x36\x30'
    b'\x59\x00\x00\x0a\x00\x08\x41\x63\x63\x65'
    b'\x70\x74\x65\x64'
)

# Issue 342
# Called AET: ANY-SCP
# Calling AET: PYNETDICOM
# Application Context Name: 1.2.840.10008.3.1.1.1
# Presentation Context Items:
#   Presentation Context ID: 1
#       Abstract Syntax: Verification SOP Class
#       SCP/SCU Role: Default
#       Result: Accepted
#       Transfer Syntax: 1.2.840.10008.1.2.1 Explicit VR Little Endian
#   Presentation Context ID: 3
#       Abstract Syntax: Basic Grayscale Print Management Meta SOP Class
#       SCP/SCU Role: Default
#       Result: Abstract Syntax Not Supported
#       Transfer Syntax: None
# User Information
#   Max Length Received: 28672
#   Implementation Class UID: 2.16.840.1
#   Implementation Version Name: MergeCOM3_390IB2
# Extended Negotiation
#   SOP Extended: None
#   Async Ops: None
#   User ID: None
a_associate_ac_zero_ts = (
    b'\x02\x00\x00\x00\x00\xb6\x00\x01\x00\x00\x41\x4e\x59\x2d\x53\x43'
    b'\x50\x20\x20\x20\x20\x20\x20\x20\x20\x20\x50\x59\x4e\x45\x54\x44'
    b'\x49\x43\x4f\x4d\x20\x20\x20\x20\x20\x20\x00\x00\x00\x00\x00\x00'
    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x10\x00\x00\x15\x31\x2e'
    b'\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x33\x2e\x31\x2e'
    b'\x31\x2e\x31\x21\x00\x00\x1b\x01\x00\x00\x00\x40\x00\x00\x13\x31'
    b'\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x31\x2e\x32'
    b'\x2e\x31\x21\x00\x00\x08\x03\x00\x03\x00\x40\x00\x00\x00\x50\x00'
    b'\x00\x2a\x51\x00\x00\x04\x00\x00\x70\x00\x52\x00\x00\x0a\x32\x2e'
    b'\x31\x36\x2e\x38\x34\x30\x2e\x31\x55\x00\x00\x10\x4d\x65\x72\x67'
    b'\x65\x43\x4f\x4d\x33\x5f\x33\x39\x30\x49\x42\x32'
)

# Issue 361
# Called AET: ANY-SCP
# Calling AET: PYNETDICOM
# Application Context Name: 1.2.840.10008.3.1.1.1
# Presentation Context Items:
#   Presentation Context ID: 1
#       Abstract Syntax: Verification SOP Class
#       SCP/SCU Role: Default
#       Result: Reject
#       Transfer Syntax: (no Transfer Syntax Sub-Item)
# User Information
#   Max Length Received: 16382
#   Implementation Class UID: 1.2.826.0.1.3680043.9.3811.1.4.0
#   Implementation Version Name: PYNETDICOM_140
# Extended Negotiation
#   SOP Extended: None
#   Async Ops: None
#   User ID: None
a_associate_ac_no_ts = (
    b'\x02\x00\x00\x00\x00\xa7\x00\x01\x00\x00\x41\x4e\x59\x2d\x53\x43'
    b'\x50\x20\x20\x20\x20\x20\x20\x20\x20\x20\x50\x59\x4e\x45\x54\x44'
    b'\x49\x43\x4f\x4d\x20\x20\x20\x20\x20\x20\x00\x00\x00\x00\x00\x00'
    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x10\x00\x00\x15\x31\x2e'
    b'\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x33\x2e\x31\x2e'
    b'\x31\x2e\x31\x21\x00\x00\x04\x01\x00\x03\x00'
    b'\x50\x00\x00\x3e\x51\x00\x00\x04\x00\x00\x3f\xfe\x52\x00\x00\x20'
    b'\x31\x2e\x32\x2e\x38\x32\x36\x2e\x30\x2e\x31\x2e\x33\x36\x38\x30'
    b'\x30\x34\x33\x2e\x39\x2e\x33\x38\x31\x31\x2e\x31\x2e\x34\x2e\x30'
    b'\x55\x00\x00\x0e\x50\x59\x4e\x45\x54\x44\x49\x43\x4f\x4d\x5f\x31'
    b'\x34\x30'
)


############################# A-ASSOCIATE-RJ PDU #############################
# Result: Rejected (Permanent)
# Source: DUL service-user
# Reason: No reason given
a_associate_rj = b"\x03\x00\x00\x00\x00\x04\x00\x01\x01\x01"

############################## A-RELEASE-RJ PDU ##############################
a_release_rq = b"\x05\x00\x00\x00\x00\x04\x00\x00\x00\x00"

############################## A-RELEASE-RP PDU ##############################
a_release_rp = b"\x06\x00\x00\x00\x00\x04\x00\x00\x00\x00"

############################### A-ABORT-RQ PDU ###############################
# Source: DUL service-user
# Reason: No reason given
a_abort = b"\x07\x00\x00\x00\x00\x04\x00\x00\x00\x00"

############################## A-P-ABORT-RQ PDU ##############################
# Source: DUL service-provider`
# Reason: Unrecognised PDU parameter
a_p_abort = b"\x07\x00\x00\x00\x00\x04\x00\x00\x02\x04"

################################ P-DATA-TF PDU ###############################
# Contains a C-ECHO message
# Context ID: 1
# Data: \x03\x00\x00\x00\x00\x04\x00\x00\x00\x42\x00\x00\x00\x00\x00\x02\x00
#       \x12\x00\x00\x00\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38
#       \x2e\x31\x2e\x31\x00\x00\x00\x00\x01\x02\x00\x00\x00\x30\x80\x00\x00
#       \x20\x01\x02\x00\x00\x00\x01\x00\x00\x00\x00\x08\x02\x00\x00\x00\x01
#       \x01\x00\x00\x00\x09\x02\x00\x00\x00\x00\x00
# P-DATA
# PDU type: 04
# Reserved: 00
# PDU Length: 00 00 00 54 (84)
# PDU Items:
#   Item length: 00 00 00 50 (80)
#   Context ID: 01
#   PDV:
#       03 - Command information, last fragment
#       00 00 00 00 | 04 00 00 00 | 42 00  - Command Group Length (66)
#       00 00 02 00 | 12 00 00 00 | 31 2e ... 31 00- Affected SOP Class UID
#       00 00 00 01 | 02 00 00 00 | 30 80 - Command Field (32816)
#       00 00 20 01 | 02 00 00 00 | - MessageIDBeingRespondedTo (1)
#       00 00 00 08 |             | - Command Data Set Type (257)
#       00 00 00 09 | - Status (0)
p_data_tf = (
    b"\x04\x00\x00\x00\x00\x54\x00\x00\x00\x50\x01\x03\x00\x00\x00"
    b"\x00\x04\x00\x00\x00\x42\x00\x00\x00\x00\x00\x02\x00\x12\x00"
    b"\x00\x00\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38"
    b"\x2e\x31\x2e\x31\x00\x00\x00\x00\x01\x02\x00\x00\x00\x30\x80"
    b"\x00\x00\x20\x01\x02\x00\x00\x00\x01\x00\x00\x00\x00\x08\x02"
    b"\x00\x00\x00\x01\x01\x00\x00\x00\x09\x02\x00\x00\x00\x00\x00"
)

# C-ECHO RQ
p_data_tf_rq = (
    b"\x04\x00\x00\x00\x00\x4a"  # P-DATA
    b"\x00\x00\x00\x46\x01"  # PDV Item
    b"\x03"
    b"\x00\x00\x00\x00\x04\x00\x00\x00\x3a\x00"  # Command Group Length
    b"\x00\x00\x00\x00\x02\x00\x12\x00\x00\x00"  # Affected SOP Class UID
    b"\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x31\x2e\x31\x00"
    b"\x00\x00\x00\x01\x02\x00\x00\x00\x30\x00"  # Command Field
    b"\x00\x00\x10\x01\x02\x00\x00\x00\x01\x00"  # Message ID
    b"\x00\x00\x00\x08\x02\x00\x00\x00\x01\x01"  # Command Data Set Type
)

# AsynchronousOperationsWindow
#   Max operations invoked: 5
#   Max operations performed: 5
asynchronous_window_ops = b'\x53\x00\x00\x04\x00\x05\x00\x05'

############################## User Identity Sub Item ########################
# -RQ
# Type: 1
# Response requested: 0
# Primary field: pynetdicom
# Secondary field: (none)
user_identity_rq_user_nopw = (
    b'\x58\x00\x00\x10\x01\x01\x00\x0a\x70\x79\x6e\x65\x74\x64\x69\x63'
    b'\x6f\x6d\x00\x00'
)

# -RQ
# Type: 1
# Response requested: 0
# Primary field: pynetdicom
# Secondary field: p4ssw0rd
user_identity_rq_user_pass = (
    b'\x58\x00\x00\x18\x02\x00\x00\x0a\x70\x79\x6e\x65\x74\x64\x69\x63'
    b'\x6f\x6d\x00\x08\x70\x34\x73\x73\x77\x30\x72\x64'
)

# -AC
# Server response: b'Accepted'
user_identity_ac = (
    b'\x59\x00\x00\x0a\x00\x08\x41\x63\x63\x65\x70\x74\x65\x64'
)

########################### Application Context Item #########################
# Application Context Name: 1.2.840.10008.3.1.1.1
application_context = (
    b"\x10\x00\x00\x15\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31"
    b"\x30\x30\x30\x38\x2e\x33\x2e\x31\x2e\x31\x2e\x31"
)

########################## Presentation Context  Items #######################
# -RQ
# Presentation Context ID: 1
# Abstract Syntax: 1.2.840.10008.1.1 Verification SOP Class
# Transfer Syntax: 1.2.840.10008.1.2 Implicit VR Little Endian
presentation_context_rq = (
    b'\x20\x00\x00\x2e\x01\x00\x00\x00\x30\x00\x00\x11\x31\x2e\x32\x2e'
    b'\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x31\x2e\x31\x40\x00\x00'
    b'\x11\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x31'
    b'\x2e\x32'
)

# Issue 560: Non-ASCII encoded abstract syntax
presentation_context_rq_utf8 = (
    b"\x20\x00\x00\x51\x4d\x00\xff\x00"
    b"\x30\x00\x00\x32\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38"
    b"\x2e\xe2\x80\x8b\x35\x2e\xe2\x80\x8b\x31\x2e\xe2\x80\x8b\x34\x2e\xe2"
    b"\x80\x8b\x31\x2e\xe2\x80\x8b\x31\x2e\xe2\x80\x8b\x31\x30\x34\x2e\xe2"
    b"\x80\x8b\x33"
    b"\x40\x00\x00\x13\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31"
    b"\x30\x30\x30\x38\x2e\x31\x2e\x32\x2e\x31"
)


# -AC
# Presentation Context ID: 1
# Result: Accepted
# Transfer Syntax: 1.2.840.10008.1.2 Implicit VR Little Endian
presentation_context_ac = (
    b'\x21\x00\x00\x19\x01\x00\x00\x00\x40\x00\x00\x11\x31\x2e\x32\x2e'
    b'\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x31\x2e\x32'
)


############################ Abstract Syntax Sub Item ########################
# Abstract Syntax: 1.2.840.10008.1.1 Verification SOP Class
abstract_syntax = (
    b'\x30\x00\x00\x11\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30'
    b'\x38\x2e\x31\x2e\x31'
)

############################ Transfer Syntax Sub Item ########################
# Transfer Syntax: 1.2.840.10008.1.2 Implicit VR Little Endian
transfer_syntax = (
    b'\x40\x00\x00\x11\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30'
    b'\x38\x2e\x31\x2e\x32'
)

######################## Presentation Data Value Sub Item ####################
presentation_data = (
    b'\x03\x00\x00\x00\x00\x04\x00\x00\x00\x42\x00\x00\x00\x00\x00\x02'
    b'\x00\x12\x00\x00\x00\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30'
    b'\x30\x38\x2e\x31\x2e\x31\x00\x00\x00\x00\x01\x02\x00\x00\x00\x30'
    b'\x80\x00\x00\x20\x01\x02\x00\x00\x00\x01\x00\x00\x00\x00\x08\x02'
    b'\x00\x00\x00\x01\x01\x00\x00\x00\x09\x02\x00\x00\x00\x00\x00'
)

# Context ID: 1
# Data: \x03\x00\x00\x00\x00\x04\x00\x00\x00\x42\x00\x00\x00\x00\x00\x02\x00
#       \x12\x00\x00\x00\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38
#       \x2e\x31\x2e\x31\x00\x00\x00\x00\x01\x02\x00\x00\x00\x30\x80\x00\x00
#       \x20\x01\x02\x00\x00\x00\x01\x00\x00\x00\x00\x08\x02\x00\x00\x00\x01
#       \x01\x00\x00\x00\x09\x02\x00\x00\x00\x00\x00
presentation_data_value = b'\x00\x00\x00\x50\x01' + presentation_data

######################## Maximum Length Received Sub Item ####################
# Max Length Received: 16382
maximum_length_received = b'\x51\x00\x00\x04\x00\x00\x3f\xfe'

######################## Implementaion Class UID Sub Item ####################
# Implementation Class UID: 1.2.826.0.1.3680043.9.3811.0.9.0
implementation_class_uid = (
    b'\x52\x00\x00\x20\x31\x2e\x32\x2e\x38\x32\x36\x2e\x30\x2e\x31\x2e'
    b'\x33\x36\x38\x30\x30\x34\x33\x2e\x39\x2e\x33\x38\x31\x31\x2e\x30'
    b'\x2e\x39\x2e\x30'
)

##################### Implementation Version Name Sub Item ###################
# Implementation Version Name: PYNETDICOM_090
implementation_version_name = (
    b'\x55\x00\x00\x0e\x50\x59\x4e\x45\x54\x44\x49\x43\x4f\x4d\x5f'
    b'\x30\x39\x30'
)

########################### Role Selection Sub Item ##########################
# SOP Class: 1.2.840.10008.5.1.4.1.1.2 CT Image Storage
# SCU Role: 0
# SCP Role: 1
role_selection = (
    b'\x54\x00\x00\x1e'
    b'\x00\x1a'
    b'\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x35\x2e\x31\x2e'
    b'\x34\x2e\x31\x2e\x31\x2e\x32\x31'
    b'\x00\x01'
)

role_selection_odd = (
    b'\x54\x00\x00\x1d'
    b'\x00\x19'
    b'\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x35\x2e\x31\x2e'
    b'\x34\x2e\x31\x2e\x31\x2e\x32'
    b'\x00\x01'
)

############################ User Information Item ###########################
# Implementation Class UID: 1.2.826.0.1.3680043.9.3811.0.9.0
# Implementation Version Name: PYNETDICOM_090
user_information = (
    b'\x50\x00\x00\x3e\x51\x00\x00\x04\x00\x00\x3f\xfe\x52\x00\x00\x20'
    b'\x31\x2e\x32\x2e\x38\x32\x36\x2e\x30\x2e\x31\x2e\x33\x36\x38\x30'
    b'\x30\x34\x33\x2e\x39\x2e\x33\x38\x31\x31\x2e\x30\x2e\x39\x2e\x30'
    b'\x55\x00\x00\x0e\x50\x59\x4e\x45\x54\x44\x49\x43\x4f\x4d\x5f\x30'
    b'\x39\x30'
)

######################## Extended Negotiation Sub Item #######################
# SOP Class: 1.2.840.10008.5.1.4.1.1.2 CT Image Storage
# Service Class App Info: b'\x02\x00\x03\x00\x01\x00'
extended_negotiation = (
    b'\x56\x00\x00\x21\x00\x19\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30'
    b'\x30\x30\x38\x2e\x35\x2e\x31\x2e\x34\x2e\x31\x2e\x31\x2e\x32\x02'
    b'\x00\x03\x00\x01\x00'
)

#################### Common Extended Negotiation Sub Item ####################
# SOP Class: 1.2.840.10008.5.1.4.1.1.4 MR Image Storage
# Service Class: 1.2.840.10008.4.2 Storage Service Class
# Related general SOP Class ID(s):
#   1.2.840.10008.5.1.4.1.1.88.22 Enhanced SR Storage
common_extended_negotiation = (
    b'\x57\x00\x00\x4f\x00\x19\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30'
    b'\x30\x30\x38\x2e\x35\x2e\x31\x2e\x34\x2e\x31\x2e\x31\x2e\x34\x00'
    b'\x11\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30\x30\x30\x38\x2e\x34'
    b'\x2e\x32\x00\x1f\x00\x1d\x31\x2e\x32\x2e\x38\x34\x30\x2e\x31\x30'
    b'\x30\x30\x38\x2e\x35\x2e\x31\x2e\x34\x2e\x31\x2e\x31\x2e\x38\x38'
    b'\x2e\x32\x32'
)
