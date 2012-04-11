.. _getting_started:

============================
Getting Started with pynetdicom
============================

.. rubric:: Brief overview of pynetdicom and how to install.

Introduction
==============

pynetdicom is a pure python package implementing the DICOM network
protocol. It is build on the pydicom package.

pynetdicom makes it easy to create DICOM clients (SCUs) or servers
(SCPs). The following service classes are currently supported, both as
SCU and SCP:

  * Verification
  * Storage
  * Query/Retrieve

pynetdicom is easy to install and use, and because it is a pure 
python package, it should run anywhere python runs. 

Here are examples of some typical uses.


License
=======
pynetdicom uses the MIT `license 
<http://code.google.com/p/pydicom/source/browse/source/LICENSE.txt>`_.


Prerequisites
-------------
  * python 2.4 and higher
  * pydicom 0.9.7 and above

Python installers can be found at the python web site 
(http://python.org/download/). On Windows, the `Activepython 
<http://activestate.com/activepython>`_ distributions are also quite good.




Installing
==========

As a pure python package, pynetdicom is quite easy to install. The
pydicom package is required.


Installing on Windows
---------------------

On Windows, pynetdicom can be installed using the executable installer from the 
`Downloads <http://code.google.com/p/pynetdicom/downloads/list>`_ tab.

Alternatively, pydicom can be installed with easy_install, pip, or 
from source, as described in the sections below.


Installing using easy_install or pip (all platforms)
----------------------------------------------------

if you have `setuptools <http://pypi.python.org/pypi/setuptools>`_ installed, 
just use easy_install at the command line (you may need ``sudo`` on linux)::
    
   easy_install pydicom

Depending on your python version, there may be some warning messages, 
but the install should still be ok.

`pip <http://http://pip.openplans.org/>`_ is a newer install tool that works
quite similarly to easy_install and can also be used.


Installing from source (all platforms)
--------------------------------------
  * download the source code from the 
    `Downloads tab <http://code.google.com/p/pynetdicom/downloads/list>`_ or 
    `checkout the mercurial repository source 
    <http://code.google.com/p/pynetdicom/source/checkout>`_
  * at a command line, change to the directory with the setup.py file
  * with admin privileges, run ``python setup.py install``

    * with some linux variants, for example, use ``sudo python setup.py install``
    * with other linux variants you may have to ``su`` before running the command.

  * for python < 2.6, you may get a syntax error message when the python files 
    are "built" -- this is due to some python 2.6 specific code in one unit 
    test file. The installation seems to still be ok.



Using pynetdicom
=============

Once installed, the package can be imported at a python command line or used 
in your own python program with ``import netdicom`` (note the package name is 
``netdicom``, not ``pynetdicom`` when used in code. 
See the `examples directory 
<http://code.google.com/p/pydicom/source/browse/#hg/source/dicom/examples>`_ 
for both kinds of uses. Also see the :doc:`User Guide </pydicom_user_guide>` 
for more details of how to use the package.


Support
=======

Please join the `pynetdicom discussion group <http://groups.google.com/group/pynetdicom>`_ 
to ask questions, give feedback, post example code for others -- in other words 
for any discussion about the pynetdicom code. New versions, major bug fixes, etc. 
will also be announced through the group.


Next Steps
==========

To start learning how to use pydicom, see the :doc:`pydicom_user_guide`.
