---
name: Bug report
about: Create a report to help us improve
title: ''
labels: ''
assignees: ''

---

**Describe the bug**
A clear and concise description of what the bug is.

**Expected behavior**
What you expected to happen (please include a reference to the DICOM standard if relevant).

**Steps To Reproduce**
How to reproduce the issue. Please include a minimum working code sample, the relevant section of the logging output at the debug level (from `pynetdicom import debug_logger; debug_logger()`) and the anonymised DICOM dataset (if relevant).

**Your environment**
Please run the following and paste the output.
```bash
$ python -c "import platform; print(platform.platform())"
$ python -c "import sys; print('Python ', sys.version)"
$ python -c "import pydicom; print('pydicom ', pydicom.__version__)"
$ python -c "import pynetdicom; print('pynetdicom ', pynetdicom.__version__)"
```
