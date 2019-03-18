### Description
A description of the issue, including the type of issue (bug report,
enhancement request, question).

### Expected behaviour
What you expected to happen, (including references to the DICOM standard is
appreciated).

### Actual behaviour
What actually happened. If an exception occurred please post the full traceback.

### Steps to reproduce
How to reproduce the issue. Please include a minimum working code sample, the
relevant section of the logging output at the debug level (`import logging; LOGGER = logging.getLogger('pynetdicom'); LOGGER.setLevel(logging.DEBUG)`) and the
anonymised DICOM dataset (if relevant).

### Your environment
Please run the following and paste the output.
```bash
$ python -c "import platform; print(platform.platform())"
$ python -c "import sys; print('Python ', sys.version)"
$ python -c "import pydicom; print('pydicom ', pydicom.__version__)"
$ python -c "import pynetdicom; print('pynetdicom ', pynetdicom.__version__)"
```
