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
install (or upgrade) from PyPi is using `pip <https://pip.pypa.io/>`_ with the
command::

  $ pip install -U pynetdicom

You may need to use this instead::

  $ python -m pip install -U pynetdicom


Install using conda
-------------------

*pynetdicom* is also available for `conda <https://docs.conda.io/>`_ on
`conda-forge <https://anaconda.org/conda-forge/pynetdicom>`_::

  $ conda install -c conda-forge pynetdicom

To upgrade the installed version on conda do::

  $ conda update pynetdicom


After installation
------------------

Now that *pynetdicom* is installed you might be interested in the
:doc:`tutorial for new users<create_scu>`.


.. _tut_install_dev:

Install the development version
===============================

To install a snapshot of the latest code (the ``master`` branch) from
`GitHub <https://github.com/pydicom/pynetdicom>`_::

  $ pip install git+https://github.com/pydicom/pynetdicom.git

The ``master`` branch is under active development, and while it's usually
stable it may have undocumented changes or bugs.

If you want to keep up-to-date with the latest code, make sure you have
`Git <https://git-scm.com/>`_ installed and then clone the ``master``
branch (this will create a ``pynetdicom`` directory in your current directory)::

  $ git clone https://github.com/pydicom/pynetdicom.git

Then install using pip in editable (``-e``) mode::

  $ pip install -e pynetdicom/

When you want to update your copy of the source code, run ``git pull`` from
within the ``pynetdicom`` directory and Git will download and apply any
changes.
