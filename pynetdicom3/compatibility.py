"""Compatibility module for python2.7/python3."""

import sys

IN_PYTHON2 = sys.version_info[0] == 2

if IN_PYTHON2:
    import Queue as queue
else:
    import queue
