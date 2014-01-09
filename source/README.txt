==========
pynetdicom
==========

pynetdicom is a pure python package implementing the DICOM network
protocol.  Working with pydicom, it allows DICOM clients (SCUs) and
servers (SCPs) to be easily created.  DICOM is a standard
(http://medical.nema.org) for communicating medical images and related
information such as reports and radiotherapy objects.
      
The main class is AE and represent an application entity. User
typically create an ApplicationEntity object, specifying the SOP
service class supported as SCP and SCU, and a port to listen to. The
user then starts the ApplicationEntity which runs in a thread. The use
can initiate associations as SCU or respond to remote SCU association
with the means of callbacks.
  
