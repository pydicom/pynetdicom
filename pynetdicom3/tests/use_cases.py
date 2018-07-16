from pynetdicom import AE


ae = AE(ae_title=b'MYAE')

# Timeouts
# Length of time to wait for association related messages (after sending RQ)
ae.acse_timeout = 60
# Length of time to wait for DIMSE message replies
ae.dimse_timeout = 30
# Length of time to wait for network messages when a message is expected (ie while waiting for ASSOC RQ from peer)
ae.network_timeout = 60

# As SCU, set different transfer syntaxes per presentation context

from pynetdicom.presentation import PresentationContext

context = PresentationContext(abstract_syntax='1.2.840.10008.1.1',
                              transfer_syntax=['1.2.840.10008.1.2',
                                               '1.2.840.10008.1.2.1'])

## SCU
# SCU requested Presentation Contexts
# We require presentation context IDs for requests, should the user set these?
# also keep in mind we should check for validity ?
# Allow user to set but don't require it
# Add exception if too many contexts in list or if ID invalid
# Class attribute
ae.requested_contexts = [context]
ae.requested_contexts = StoragePresentationContexts

assoc = ae.associate(addr, port, calling_aet=b'ANYSCP', contexts=None,
                     pdv_size=16382, ext_neg=None, local_port=0, tls_args=None)

def associate(...):
    # Check validity of ae.requested_contexts


## SCP
# SCP supported Presentation Contexts
# No presentation context IDs required
ae.supported_contexts = [context]
# Predefine class based contexts
ae.supported_contexts = StoragePresentationContexts
ae.supported_contexts = VerificationPresentationContexts
ae.port = 104

# Callbacks -> move to registration?
ae.on_c_* = on_c_*
# Only allow singleton callbacks for these
ae.register('on-c-echo', on_c_echo)
ae.unregister('on-c-echo', on_c_echo)
ae.register('on-c-store', on_c_store)
ae.register('on-c-find', on_c_find)
ae.register('on-c-get', on_c_get)
ae.register('on-c-move', on_c_move)

# How to handle:
SCP/SCU Role Selection (via PresentationContext.scp_role and .scu_role)
Asynchronous Window (not supported)
SOP Class Common
SOP Class Common Extended
User Identity (AE.on_user_identity_negotiation() -> Default accept if not implemented)
# Singleton
ae.register('on-user-identity', on_user_identity_negotiation)
ae.register('on-sop-class-common', pass)
ae.register('on-sop-class-common-extended', pass)

ImplementationNotification (AE.implementation_version_name and .implementation_class_uid)
MaximumLengthNegotiation (AE.maximum_length_received)

# Called/Calling AET matching
ae.require_called_aet = b''
ae.require_calling_aet = b''

ae.start(port, blocking=True, tls_args=None)

# tls_args : None or dict
#    If SSL is to be used then a dict of parameters to pass to ...

## SCU
# Verification minimalist
from pynetdicom import AE, VerificationPresentationContexts

ae = AE()
assoc = ae.associate('localhost', 104, VerificationPresentationContexts)
if assoc.is_established:
    status = assoc.send_c_echo()

    assoc.release()

# Storage
from pydicom import dcmread
from pynetdicom import AE, StoragePresentationContexts

ae = AE(ae_title=b'MY_AE_TITLE')
ae.implementation_version_name = b'SOMENAME'
ae.implementation_class_uid = UID('1.2.3.4.5')
assoc = ae.associate('localhost', 104, StoragePresentationContexts, calling_aet=b'ANY-SCP')
if assoc.is_established:
    ds = dcmread('path/to/dataset.dcm')
    status = assoc.send_c_store(ds)

    assoc.release()


## SCP
# Verification minimal
from pynetdicom import AE, VerificationPresentationContexts

ae = AE()
ae.supported_contexts = VerificationPresentationContexts
ae.start(104)

# Storage
from pynetdicom import AE, StoragePresentationContexts

def on_c_store(dataset, context, info):
    return 0x0000

def on_user_identity(user_id_type, primary_field, secondary_field):
    return True

def on_association_request(primitive):
    # Allow users to tailor association responses to the requestor
    supported_contexts = [PresentationContext()]
    pdv_length = 16382

    return response

ae = AE()
ae.supported_contexts = StoragePresentationContexts
ae.require_calling_aet = b'MYAE'
ae.maximum_length_received = 16382
ae.register('on-association-request', on_assoc_rq)
ae.register('on-c-store', on_c_store)
ae.register('on-user-identity', on_user_identity)
ae.start(104)

# Alternate
# Class attribute
ae.on_c_store = on_c_store
