============
Installation
============

Install the official release
============================

*pynetdicom* requires `Python <https://www.python.org/>`_ and `pydicom
<https://pydicom.github.io/pydicom/stable/tutorials/installation.html>`_. In
addition, if you want to use the :doc:`qrscp<../apps/qrscp>` application then
`sqlalchemy <https://www.sqlalchemy.org/>`_ is also required.

Install using pip
-----------------

*pynetdicom* is available on `PyPi <https://pypi.python.org/pypi/pynetdicom/>`_,
the official third-party Python software repository. The simplest way to
install (or upgrade) from PyPi is using `pip <https://pip.pypa.io/>`_::

    python -m pip install -U pip
    python -m pip install -U pynetdicom


Install using conda
-------------------

*pynetdicom* is also available for `conda <https://docs.conda.io/>`_ on
`conda-forge <https://anaconda.org/conda-forge/pynetdicom>`_::

  conda install -c conda-forge pynetdicom

To upgrade the installed version on conda do::

  conda update pynetdicom


Install the development version
===============================

To install a snapshot of the latest code (the ``main`` branch) from
:gh:`GitHub <pynetdicom>`::

  pip install git+https://github.com/pydicom/pynetdicom

The ``main`` branch is under active development, and while it's usually
stable it may have undocumented changes or bugs.

If you want to keep up-to-date with the latest code, make sure you have
`Git <https://git-scm.com/>`_ installed and then clone the ``main``
branch (this will create a ``pynetdicom`` directory in your current directory)::

  git clone https://github.com/pydicom/pynetdicom

Create a `new virtual environment <https://docs.python.org/3/tutorial/venv.html>`_ and
in the activated environment change to the ``pynetdicom`` directory and install
*pynetdicom* and the required development packages::

    cd pynetdicom/
    python -m pip install -e .[dev]

When you want to update your copy of the source code, run ``git pull`` from
within the ``pynetdicom`` directory and Git will download and apply any
changes.
