from functools import partial
import inspect
from operator import attrgetter
import os
from pathlib import Path
import subprocess
import sys

import pynetdicom


REVISION_CMD = "git rev-parse --short HEAD"


def _get_git_revision():
    try:
        revision = subprocess.check_output(REVISION_CMD.split()).strip()
    except (subprocess.CalledProcessError, OSError):
        print("Failed to execute git to get revision")
        return None
    return revision.decode("utf-8")


def _linkcode_resolve(domain, info, package, url_fmt, revision):
    """Determine a link to online source for a class/method/function

    This is called by sphinx.ext.linkcode

    An example with a long-untouched module that everyone has
    >>> _linkcode_resolve('py', {'module': 'tty',
    ...                          'fullname': 'setraw'},
    ...                   package='tty',
    ...                   url_fmt='http://hg.python.org/cpython/file/'
    ...                           '{revision}/Lib/{package}/{path}#L{lineno}',
    ...                   revision='xxxx')
    'http://hg.python.org/cpython/file/xxxx/Lib/tty/tty.py#L18'
    """
    if revision is None:
        return

    if domain not in ("py", "pyx"):
        return

    if not info.get("module") or not info.get("fullname"):
        return

    modname = info['module']
    fullname = info['fullname']

    submod = sys.modules.get(modname)
    if submod is None:
        return None

    obj = submod
    for part in fullname.split('.'):
        try:
            obj = getattr(obj, part)
        except AttributeError:
            return None

    if inspect.isfunction(obj):
        obj = inspect.unwrap(obj)

    try:
        fn = inspect.getsourcefile(obj)
    except TypeError as exc:
        fn = None

    if not fn or fn.endswith('__init__.py'):
        # The UID gets resolved to the venv pydicom install otherwise
        if fullname == "PYNETDICOM_IMPLEMENTATION_UID":
            fn = Path(pynetdicom.__file__)
        else:
            try:
                fn = inspect.getsourcefile(sys.modules[obj.__module__])
            except (TypeError, AttributeError, KeyError):
                fn = None

    if not fn:
        return None

    startdir = Path(pynetdicom.__file__).parent
    fn = os.path.relpath(fn, start=startdir).replace(os.path.sep, "/")
    try:
        lineno = inspect.getsourcelines(obj)[1]
    except Exception:
        lineno = ""

    return url_fmt.format(revision=revision, package=package, path=fn, lineno=lineno)


def make_linkcode_resolve(package, url_fmt):
    """Returns a linkcode_resolve function for the given URL format

    revision is a git commit reference (hash or name)

    package is the name of the root module of the package

    url_fmt is along the lines of ('https://github.com/USER/PROJECT/'
                                   'blob/{revision}/{package}/'
                                   '{path}#L{lineno}')
    """
    revision = _get_git_revision()
    return partial(
        _linkcode_resolve, revision=revision, package=package, url_fmt=url_fmt
    )
