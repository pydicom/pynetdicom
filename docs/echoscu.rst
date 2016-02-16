=======
echoscu
=======
    echoscu [options] peer port

Description
===========
The echoscu application implements a Service Class User (SCU) for the 
*Verification SOP Class* (UID 1.2.840.10008.1.1) [#]_. It establishes an Association 
with a peer Application Entity (AE) which it then sends a DICOM C-ECHO-RQ 
message [#]_ and waits for a response. The application can be used to verify 
basic DICOM connectivity.

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

Using the *--propose-pc [n]* option, the echoscu application can also 
propose *n* Presentation Contexts [#]_ (all with an Abstract Syntax of 
*Verification SOP Class*) in order to provide debugging assistance for 
association negotiation.

DICOM Conformance
=================
The echoscu application supports the following SOP Classes as an SCU:
::
    Verification SOP Class          1.2.840.10008.1.1

Unless the *--propose-ts* option is used, the echoscu application will only 
propose the *Little Endian Implicit VR Transfer Syntax* (UID 1.2.840.10008.1.2).
The supported Transfer Syntaxes [#]_ are:
::
    Little Endian Implicit VR       1.2.840.10008.1.2 
    Little Endian Explicit VR       1.2.840.10008.1.2.1 
    Big Endian Explicit VR          1.2.840.10008.1.2.2 

.. rubric:: Footnotes::

.. [#] See DICOM Standard 2015b PS3.6 Table A-1
.. [#] See DICOM Standard 2015b PS3.7 Sections 9.1.5 and 9.3.5
.. [#] See DICOM Standard 2015b PS3.8 Sections 7.1.1.13 and 9.3.2.2
.. [#] See DICOM Standard 2015b PS3.5 Section 10 and Annex A
