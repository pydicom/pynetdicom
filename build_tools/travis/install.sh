#!/bin/bash

set -e

pip install coverage
pip install pytest-cov
pip install -U pytest
pip install asv

echo ""
echo "Test suite is " $TEST_SUITE
echo ""

if [[ "$TEST_SUITE" == "pydicom_master" ]]; then
    pip install git+https://github.com/pydicom/pydicom.git
elif [[ "$TEST_SUITE" == "pydicom_release" ]]; then
    pip install pydicom
fi

python --version
python -c "import pydicom; print('pydicom version', pydicom.__version__)"
python -c "import pytest; print('pytest version', pytest.__version__)"
python -c "import ssl; print(ssl.OPENSSL_VERSION)"
