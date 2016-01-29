#
# Copyright (c) 2012 Patrice Munger
# This file is part of pynetdicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pynetdicom.googlecode.com
#

import unittest
import sys
sys.path.append('../..')
import netdicom
netdicom.debug(False)
import netdicom.DULparameters as DULparameters
from netdicom.DULprovider import DULServiceProvider
from netdicom.PDU import MaximumLengthParameters
import time
import socket

assoc = DULparameters.A_ASSOCIATE_ServiceParameters()
assoc.ApplicationContextName = '1.2.840.10008.3.1.1.1'
assoc.CallingAETitle = 'PYDICOM'
assoc.CalledAETitle = 'SPIN'
MaxPDULengthPar = MaximumLengthParameters()
MaxPDULengthPar.MaximumLengthReceived = 12000
assoc.UserInformation = [MaxPDULengthPar]
server_port = 6666
assoc.CalledPresentationAddress = (socket.gethostname(), server_port)
assoc.PresentationContextDefinitionList = [[1, '1.2.840.10008.1.1',
                                            ['1.2.840.10008.1.2']]]

rel = DULparameters.A_RELEASE_ServiceParameters()
rel.Reason = 1

ab = DULparameters.A_ABORT_ServiceParameters()
ab.AbortSource = 0

pdata = DULparameters.P_DATA_ServiceParameters()
pdata.PresentationDataValueList = [[1, 'toto1'], [1, 'toto2']]


class TestAssociateService(unittest.TestCase):
    # ef setUp(self):

    def test_normal_accept(self):
        self.dul1 = DULServiceProvider(Port=None, Name='Dul1, Requestor')
        self.dul2 = DULServiceProvider(Port=server_port, Name='Dul2, Acceptor')
        self.dul1.Send(assoc)
        ass1 = self.dul2.Receive(True)
        ass1.PresentationContextDefinitionResultList = [
            [1, 0,  '1.2.840.10008.1.2']]
        ass1.PresentationContextDefinitionList = None
        ass1.Result = 0
        self.dul2.Send(ass1)
        res = self.dul1.Receive(True)
        self.dul1.Kill()
        self.dul2.Kill()

    def test_normal_reject(self):
        self.dul1 = DULServiceProvider(Port=None, Name='Dul1, Requestor')
        self.dul2 = DULServiceProvider(Port=server_port, Name='Dul2, Acceptor')
        self.dul1.Send(assoc)
        ass1 = self.dul2.Receive(True)
        ass1.PresentationContextDefinitionResultList = [
            [1, 0,  '1.2.840.10008.1.2']]
        ass1.PresentationContextDefinitionList = None
        ass1.Result = 1
        self.dul2.Send(ass1)
        res = self.dul1.Receive(True)
        self.dul1.Kill()
        self.dul2.Kill()

    def test_accept_no_acceptor(self):
        self.dul1 = DULServiceProvider(Port=4567, Name='Dul1, Requestor')
        self.assertRaises(socket.error, self.dul1.Send(assoc))
        self.dul1.Kill()

    def test_accept_long_to_respond(self):
        self.dul1 = DULServiceProvider(Port=4567, Name='Dul1, Requestor')
        self.dul2 = DULServiceProvider(Port=server_port, Name='Dul2, Acceptor')
        self.dul1.Send(assoc)
        ass1 = self.dul2.Receive(True)
        ass1.PresentationContextDefinitionResultList = [
            [1, 0,  '1.2.840.10008.1.2']]
        ass1.PresentationContextDefinitionList = None
        ass1.Result = 1
        time.sleep(10)
        self.dul2.Send(ass1)
        res = self.dul1.Receive(True)
        self.dul1.Kill()
        self.dul2.Kill()


if __name__ == '__main__':
    for ii in range(1000):
        print ii
        unittest.main()
