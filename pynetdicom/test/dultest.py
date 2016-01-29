#
# Copyright (c) 2012 Patrice Munger
# This file is part of pynetdicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pynetdicom.googlecode.com
#

import sys
sys.path.append('../..')
import netdicom
import netdicom.DULparameters as DULparameters
from netdicom.DULprovider import DULServiceProvider
import time
from netdicom.PDU import MaximumLengthParameters
import socket
import time
hostname = socket.gethostname()
# netdicom.debug(True)


# construct DUL primitives
# self test code
server_port = 6666


ass = DULparameters.A_ASSOCIATE_ServiceParameters()
ass.ApplicationContextName = '1.2.840.10008.3.1.1.1'
ass.CallingAETitle = 'PYDICOM'
ass.CalledAETitle = 'SPIN'
MaxPDULengthPar = MaximumLengthParameters()
MaxPDULengthPar.MaximumLengthReceived = 12000
ass.UserInformation = [MaxPDULengthPar]
ass.CalledPresentationAddress = (hostname, server_port)
ass.PresentationContextDefinitionList = [
    [1, '1.2.840.10008.1.1', ['1.2.840.10008.1.2']],
]

rel = DULparameters.A_RELEASE_ServiceParameters()
rel.Reason = 1
ab = DULparameters.A_ABORT_ServiceParameters()
ab.AbortSource = 0
pdata = DULparameters.P_DATA_ServiceParameters()
pdata.PresentationDataValueList = [[1, 'toto1'], [1, 'toto2']]


print "Starting DUL2, Acceptor ... ",
dul2 = DULServiceProvider(Port=server_port, Name='Dul2, Acceptor')
print "Ok."

print "Starting DUL1, Resquestor ... ",
dul1 = DULServiceProvider(Port=4567, Name='Dul1, Requestor')
print "Ok."


def Request():
    # print "DUL1 requesting association ... ",
    dul1.Send(ass)
    # print "Ok."
    # print "DUL2 receiving association request ... ",
    ass1 = dul2.Receive(True)
    # print "Ok."
    # print "DUL2 sending association response ... ",
    ass1.PresentationContextDefinitionResultList = [
        [1, 0,  '1.2.840.10008.1.2']]
    ass1.PresentationContextDefinitionList = None
    ass1.Result = 0
    dul2.Send(ass1)
    # print "Ok."

    # print "DUL1 receiving association response ... ",
    res = dul1.Receive(True)
    # print "Ok."


def Abort():
    # print "DUL1 aborting the association ... "
    dul1.Send(ab)
    # print "Ok."

    # print "DUL2 receiving the abort notification ..."
    ab2 = dul2.Receive(True)
    # print "Ok."


def Release():
    # Release Association
    # print "Release association ... ",
    dul1.Send(rel)
    rel1 = dul2.Receive(True)
    rel1.Result = 0
    dul2.Send(rel1)
    dul1.Receive(True)
    # print "Ok."


def Send():
    # Send p-data from dul1 to dul2
    dul1.Send(pdata)
    dul2.Receive(True).PresentationDataValueList
    dul2.Send(pdata)
    dul1.Receive(True).PresentationDataValueList


N = 100
for ii in range(1, N + 1):
    try:
    # print "="*50
        print "%d/%d" % (ii, N)
        # print "="*50

        Request()
        Release()

        Request()
        Abort()

        Request()
        Send()
        Send()
        Abort()

        Request()
        Send()
        Send()
        Send()
        Send()
        Send()
        Send()
        Release()

    except KeyboardInterrupt:
        break
dul1.Kill()
dul2.Kill()
