============
Installation
============

Install the official release
============================

*pynetdicom* requires `Python <https://www.python.org/>`_ and `pydicom
<https://pydicom.github.io/pydicom/dev/guides/user/installation.html>`_. In
addition, if you want to use the :doc:`qrscp<../apps/qrscp>` application then
`sqlalchemy <https://www.sqlalchemy.org/>`_ is also required.


.. tab-set::
    :sync-group: install
    :class: sd-width-content-min

    .. tab-item:: pip
        :sync: pip

        .. code-block:: bash

            pip install -U pynetdicom

    .. tab-item:: conda
        :sync: conda

        .. code-block:: bash

            conda install -c conda-forge pynetdicom


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
    python -m pip install -e . --group dev

When you want to update your copy of the source code, run ``git pull`` from
within the ``pynetdicom`` directory and Git will download and apply any
changes.
