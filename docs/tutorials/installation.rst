=========================
How to install pynetdicom
=========================

.. note::

   We recommend installing into a
   `virtual environment <https://docs.python.org/3/tutorial/venv.html>`_,
   which is an isolated Python environment that allows you to install
   packages without admin privileges. See the `pydicom virtual environments
   tutorial
   <https://pydicom.github.io/pydicom/stable/tutorials/virtualenvs.html>`_ on
   how to create and manage virtual environments.


.. _tut_install:

Install the official release
============================

*pynetdicom* requires `Python <https://www.python.org/>`_ and `pydicom
<https://pydicom.github.io/pydicom/stable/tutorials/installation.html>`_.

Install using pip
-----------------

*pynetdicom* is available on `PyPi <https://pypi.python.org/pypi/pydicom/>`_,
the official third-party Python software repository. The simplest way to
install from PyPi is using `pip <https://pip.pypa.io/>`_ with the command::

  $ pip install pynetdicom

You may need to use this instead, depending on your operating system::

  $ python -m pip install pynetdicom

*pynetdicom* is also available on `conda <https://docs.conda.io/>`_ at
`conda-forge <https://anaconda.org/conda-forge/pynetdicom>`_::

  $ conda install -c conda-forge pynetdicom


.. _tut_install_dev:

Install the development version
===============================

To install a snapshot of the latest code (the ``master`` branch) from
`GitHub <https://github.com/pydicom/pynetdicom>`_::

  $ pip install git+https://github.com/pydicom/pynetdicom.git

The ``master`` branch is under active development and while it is usually
stable, it may have undocumented changes or bugs.

If you want to keep up-to-date with the latest code, make sure you have
`Git <https://git-scm.com/>`_ installed and then clone the ``master``
branch (this will create a ``pynetdicom`` directory in your current directory)::

  $ git clone --depth=1 https://github.com/pydicom/pynetdicom.git

Then install using pip in editable (``-e``) mode::

  $ pip install -e pynetdicom/

When you want to update your copy of the source code, run ``git pull`` from
within the ``pynetdicom`` directory and Git will download and apply any
changes.


.. _tut_install_dcmtk:

Install DCMTK
=============

`DCMTK <https://dicom.offis.de/dcmtk.php.en>`_ applications are used in some
of the tutorials so you don't have to worry about writing fully
featured DICOM applications before starting to experiment with *pynetdicom*.

Installing on:

* Ubuntu/Debian: ``$ sudo apt install dcmtk``
* Fedora: ``$ sudo dnf install dcmtk``
* Windows/MacOS: check `DCMTK's website
  <https://dicom.offis.de/dcmtk.php.en>`_ for installation instructions. If
  you're interested in testing out TLS options you'll need to install the
  version with OpenSSL based security extensions.
