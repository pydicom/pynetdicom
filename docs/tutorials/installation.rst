=========================
How to install pynetdicom
=========================

.. note::

   We recommend installing into a
   `virtual environment <https://docs.python.org/3/tutorial/venv.html>`_,
   which is an isolated Python environment that allows you to install
   packages without admin privileges.


.. _tut_install:

Install the official release
============================

*pynetdicom* requires `Python <https://www.python.org/>`_ and `pydicom
<https://pydicom.github.io/pydicom/stable/tutorials/installation.html>`_. In
addition, if you want to use the :doc:`qrscp<../apps/qrscp>` application then
`sqlalchemy <https://www.sqlalchemy.org/>`_ is also required.

Install using pip
-----------------

*pynetdicom* is available on `PyPi <https://pypi.python.org/pypi/pydicom/>`_,
the official third-party Python software repository. The simplest way to
install (or upgrade) from PyPi is using `pip <https://pip.pypa.io/>`_ with the
command::

  pip install -U pynetdicom

You may need to use this instead::

  python -m pip install -U pynetdicom


Install using conda
-------------------

*pynetdicom* is also available for `conda <https://docs.conda.io/>`_ on
`conda-forge <https://anaconda.org/conda-forge/pynetdicom>`_::

  conda install -c conda-forge pynetdicom

To upgrade the installed version on conda do::

  conda update pynetdicom


After installation
------------------

Now that *pynetdicom* is installed you might be interested in the
:doc:`tutorial for new users<create_scu>`.


.. _tut_install_dev:

Install the development version
===============================

To install a snapshot of the latest code (the ``master`` branch) from
:gh:`GitHub <pynetdicom>`::

  pip install git+https://github.com/pydicom/pynetdicom

The ``master`` branch is under active development, and while it's usually
stable it may have undocumented changes or bugs.

If you want to keep up-to-date with the latest code, make sure you have
`Git <https://git-scm.com/>`_ installed and then clone the ``master``
branch (this will create a ``pynetdicom`` directory in your current directory)::

  git clone https://github.com/pydicom/pynetdicom

Create a `new virtual environment <https://docs.python.org/3/tutorial/venv.html>`_

In the activated environment install `poetry <https://python-poetry.org/>`_::

  pip install -U poetry

Change to the ``pynetdicom`` directory and install *pynetdicom* and the required
development packages using poetry::

  cd pynetdicom/
  poetry install --with dev

When you want to update your copy of the source code, run ``git pull`` from
within the ``pynetdicom`` directory and Git will download and apply any
changes.
