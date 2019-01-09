#!/bin/bash

set -e

pip install codecov
pip install coverage
pip install pytest-cov
pip install pytest
pip install asv
#python setup.py install

echo "Test suite is " $TEST_SUITE

if [[ "$TEST_SUITE" == "pydicom_master" ]]; then
    wget https://github.com/pydicom/pydicom/archive/master.tar.gz -O /tmp/pydicom.tar.gz
    tar xzf /tmp/pydicom.tar.gz
    pip install $PWD/pydicom-master
    python -c "import pydicom; print(pydicom.__version__)"
elif [[ "$TEST_SUITE" == "pydicom_release" ]]; then
    pip install pydicom
    python -c "import pydicom; print(pydicom.__version__)"
fi

python --version
