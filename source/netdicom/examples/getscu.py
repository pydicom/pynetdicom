#
# Copyright (c) 2012 Patrice Munger
# This file is part of pynetdicom, released under a modified MIT license.
#    See the file license.txt included with this distribution, also
#    available at http://pynetdicom.googlecode.com
#


"""
GetSCU AE example.

This demonstrates a simple application entity that support the Patient Root
Get SOP Class as SCU. The example sets up a SCP provider listening
on port 2001 on localhost using the dcmqrscp command from the offis toolkit. 
"""

import sys
sys.path.append('..')
import time
from applicationentity import AE
from SOPclass import *
import dicom
from dcmqrscp import start_dcmqrscp
from dicom.dataset import Dataset

# first create a partner
start_dcmqrscp(server_port=2001, server_AET='AE1', populate=True)
for ii in range(20): print

# call back
def OnAssociateResponse(association):
    print "Association response received"

def OnReceiveStore(SOPClass, DS):
    print "Received C-STORE"
    print DS
    return 0
    
# create application entity
MyAE = AE('LocalAE', 9998, [PatientRootGetSOPClass, VerificationSOPClass],[RTPlanStorageSOPClass,
									   CTImageStorageSOPClass,
									   MRImageStorageSOPClass,
									   RTImageStorageSOPClass,
									   ])
MyAE.OnAssociateResponse = OnAssociateResponse
MyAE.OnReceiveStore = OnReceiveStore

# remote application entity
RemoteAE = {'Address':'localhost','Port':2001,'AET':'AE1'}

# create association with remote AE
print "Request association"
assoc = MyAE.RequestAssociation(RemoteAE)

        
# perform a DICOM ECHO
print "DICOM Echo ... ",
st = assoc.VerificationSOPClass.EchoSCU(1)
print 'done with status "%s"' % st

# send dataset using RTPlanStorageSOPClass
print "DICOM GetSCU ... ",
d = Dataset()
d.PatientsName = '*'
d.QueryRetrieveLevel = "PATIENT"
st = assoc.PatientRootGetSOPClass.GetSCU(d, 1)
print 'done with status "%s"' % st


print "Release association"
assoc.Release(0)

# done
MyAE.Quit()





###
### Get SCU does not work at the moment with imagectn and no
### other C-GET SCP has been found to test against.
###
#import pyDicom.Encoding.Element
#import sys
#import os
#import popen2
#import time
#import params
#from pyDicom.DicomInterface.DIMSEServiceProvider import DIMSEServiceProvider
#from pyDicom.DicomInterface.ACSEServiceProvider import ACSEServiceProvider
#from pyDicom.DUL.DULServiceProvider import DULServiceProvider
#import platform
#
#
#(options, args) = params.getparams()
#remote_port = options.port
#remote_address = args[0]
#myaet = options.myaet
#theiraet = options.theiraet
#acn = '1.2.840.10008.3.1.1.1' # Default application context name
#maxpdulength = 16384
#
#DUL = DULServiceProvider()
#ACSE = ACSEServiceProvider(DUL)
#DIMSE = DIMSEServiceProvider(DUL)
#
#ext1 = pyDicom.DIMSE.Parameters.SCP_SCU_RoleSelectionParameters()
#ext1.SOPClassUID = '1.2.840.10008.5.1.4.1.1.2'
#ext1.SCURole = 1
#ext1.SCPRole = 1
#
#ext2 = pyDicom.DIMSE.Parameters.SCP_SCU_RoleSelectionParameters()
#ext2.SOPClassUID = '1.2.840.10008.5.1.4.1.1.4'
#ext2.SCURole = 1
#ext2.SCPRole = 1
#
#ext3 = pyDicom.DIMSE.Parameters.SCP_SCU_RoleSelectionParameters()
#ext3.SOPClassUID = '1.2.840.10008.5.1.4.1.1.6.1'
#ext3.SCURole = 1
#ext3.SCPRole = 1
#
#
#presentation_contexts = [
#	[1, '1.2.840.10008.5.1.4.1.2.1.3', ['1.2.840.10008.1.2']],
#	[3, '1.2.840.10008.5.1.4.1.1.2',['1.2.840.10008.1.2']],
#	[5, '1.2.840.10008.5.1.4.1.1.4',['1.2.840.10008.1.2']],
#	[7, '1.2.840.10008.5.1.4.1.1.6.1', ['1.2.840.10008.1.2']]
#	]
#
#localAE = {'Port':'', 'Address':platform.node, 'AET':myaet}
#remoteAE = {'Port':remote_port, 'Address':remote_address, 'AET':theiraet}
#
#
#localAE = dict(Address='', Port='', AET=options.myaet)
#remoteAE = dict(Address=args[0], Port=options.port, AET=options.theiraet)
#
#print localAE
#print remoteAE
#
## Request Association
#ans = ACSE.Request(localAE, remoteAE, maxpdulength, presentation_contexts, userspdu=[ext2, ext1,ext3])
#
#
#
#########
######### Their might be a problem with C-GET implementation in dcmtk
##################################3
#
#d = pyDicom.Encoding.DataSet.DataSet(AppendMode=True)
#d[(0x0010,0x0010)][0] = args[1]
#d[(0x0008,0x0052)][0] = "PATIENT"
#d.SetAppendMode(False)
#
#from StringIO import StringIO
#from pyDicom.Encoding.TransferSyntax import *
#f = StringIO()
#d.Write(LittleImplicitTransferSyntax(), f)
#
#
## association established
## build C-GET primitive
#cget = pyDicom.DIMSE.Parameters.C_GET_ServiceParameters()
#cget.MessageID = 1
#cget.AffectedSOPClassUID = "1.2.840.10008.5.1.4.1.2.1.3"
#cget.Priority = 0x0002
#cget.Identifier = f.getvalue()
#
#
#print "Send C-GET request primitive"
#DIMSE.Send(cget, 1, maxpdulength)
#
#
#print "Wait for C-GET response primitive"
#while 1:
#    # receive c-store
#    msg, id = DIMSE.Receive(Wait=True)
#    if msg.__class__ == pyDicom.DIMSE.Parameters.C_GET_ServiceParameters:
#        print "C_GET received"
#        if msg.Status == 0xFF00:
#            # pending. intermediate C-GET response
#            pass
#        else:
#            # last answer 
#            break	
#    elif  msg.__class__ == pyDicom.DIMSE.Parameters.C_STORE_ServiceParameters:
#        # send c-store response
#        print "send c-store"
#        rsp = pyDicom.DIMSE.Parameters.C_STORE_ServiceParameters()
#        rsp.MessageIDBeingRespondedTo = msg.MessageID
#        rsp.Status = 0
#        rsp.AffectedSOPInstanceUID = msg.AffectedSOPInstanceUID
#        rsp.AffectedSOPClassUID = msg.AffectedSOPClassUID
#        DIMSE.Send(rsp,1,maxpdulength)
#        print rsp.AffectedSOPInstanceUID
#
#        f = StringIO(msg.DataSet)
#        from pyDicom.Encoding.DicomStream import DicomStream
#        s = DicomStream(f, LittleImplicitTransferSyntax())
#        d = s.read()
#	#print d
#
#
#print "Release Association"
#ACSE.Release(0)
#
