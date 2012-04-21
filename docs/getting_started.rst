.. _getting_started:

===============
Getting Started
===============

Introduction
============
pynetdicom is a pure python_ package implementing the DICOM network
protocol. It uses the pydicom package.

pynetdicom makes it easy to create DICOM clients (SCUs) or servers
(SCPs). The following service classes are currently supported, both as
SCU and SCP:

  * Verification
  * Storage
  * Query/Retrieve

pynetdicom is easy to install and use, and because it is a pure 
python package, it should run anywhere python runs. 

You can find examples in :ref:`here <usecases>`.

License
=======
pynetdicom uses the `MIT license 
<http://code.google.com/p/pynetdicom/source/browse/source/LICENCE.txt>`_.

Prerequisites
=============
* python_ 2.4 and higher
* pydicom_ 0.9.7 and above


Installation
============
Here are the installation options:

  * pynetdicom is registered at PyPi_, so it can be installed with any
    of the following:

    + `easy_install <http://peak.telecommunity.com/DevCenter/EasyInstall>`_
    + pip_

  * download `source package <http://pypi.python.org/pypi/pynetdicom>`_ 
    and install with::

        python setup.py install    

  * A :rel:`windows installer <''>` is also available.


Support
=======

Please join the `pynetdicom discussion group
<http://groups.google.com/group/pynetdicom>`_ to ask questions, give
feedback, post example code for others -- in other words for any
discussion about the pynetdicom code. New versions, major bug fixes,
etc.  will also be announced through the group.



.. _python: http://www.python.org
.. _pydicom: http://code.google.com/p/pydicom/
.. _pip: http://www.pip-installer.org/en/latest/installing.html
.. _PyPi: http://pypi.python.org/pypi
