"""test suite configuration"""


# pynetdicom AE
AET = 'PYNETDICOM'
port = 8888

# peer AEs: (AET, host, port)
peers = [
    dict(aet='DCMTK',        host='dcmserver',   port=4000),
    dict(aet='DCM4CHEE',     host='dcmserver',   port=11112),
    dict(aet='CONQUESTSRV1', host='dcmserver',   port=5678),
    dict(aet='ORTHANC',      host='dcmserver',   port=4242),
    dict(aet='PACSONE',      host='dcmserver',   port=6000)
]
