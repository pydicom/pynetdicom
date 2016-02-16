=======
echoscu
=======
echoscu [options] peer port

Description
===========
The echoscu application implements a Service Class User (SCU) for the 
*Verification SOP Class* (UID 1.2.840.10008.1.1). It establishes an Association 
with a peer Application Entity (AE) which it then sends a DICOM C-ECHO message 
and waits for a response. The application can be used to verify basic DICOM 
connectivity.

The following simple example shows what happens when it is succesfully run on 
an SCP that supports the Verification SOP Class:
::
    user@host: echoscu 192.168.2.1 11112 
    user@host: 

When attempting to send a C-ECHO to an SCP that doesn't support the 
*Verification SOP Class*:
::
    user@host: echoscu 192.168.2.1 11112 
    E: No Acceptable Presentation Contexts 
    user@host: 

When attempting to associate with a non-DICOM peer
::
    user@host: echoscu 192.168.2.1 11112 
    E: Association Request Failed: Failed to establish association 
    E: Peer aborted Association (or never connected) 
    E: TCP Initialisation Error: (Connection refused) 
    user@host: 

The echoscu application can also propose more than one Presentation Context in 
order to provide debugging assistance for association negotiation.
The supported SOP Classes are:
::
    

Unless the *--propose-ts* option is used, the echoscu application will only 
propose the *Little Endian Implicit VR Transfer Syntax* (UID 1.2.840.10008.1.2).
The supported Transfer Syntaxes are:
::
    Little Endian Implicit VR       1.2.840.10008.1.2 
    Little Endian Explicit VR       1.2.840.10008.1.2.1 
    Big Endian Explicit VR          1.2.840.10008.1.2.2 

DICOM Conformance
=================
