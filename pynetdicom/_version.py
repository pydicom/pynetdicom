"""Version information for pynetdicom based on PEP396 and 440.

Parts of `extract_components` are taken from the pypa packaging project
(https://github.com/pypa/packaging) which is dual licensed:
> This file is dual licensed under the terms of the Apache License, Version
> 2.0, and the BSD License. See the LICENSE file in the root of (the pypa)
> repository for complete details.
"""

import re


__version__ = '1.5.7'


VERSION_PATTERN = r"""
    v?
    (?:
        (?:(?P<epoch>[0-9]+)!)?                           # epoch
        (?P<release>[0-9]+(?:\.[0-9]+)*)                  # release segment
        (?P<pre>                                          # pre-release
            [-_\.]?
            (?P<pre_l>(a|b|c|rc|alpha|beta|pre|preview))
            [-_\.]?
            (?P<pre_n>[0-9]+)?
        )?
        (?P<post>                                         # post release
            (?:-(?P<post_n1>[0-9]+))
            |
            (?:
                [-_\.]?
                (?P<post_l>post|rev|r)
                [-_\.]?
                (?P<post_n2>[0-9]+)?
            )
        )?
        (?P<dev>                                          # dev release
            [-_\.]?
            (?P<dev_l>dev)
            [-_\.]?
            (?P<dev_n>[0-9]+)?
        )?
    )
    (?:\+(?P<local>[a-z0-9]+(?:[-_\.][a-z0-9]+)*))?       # local version
"""


def is_canonical(version):
    """Return True if `version` is a PEP440 conformant version."""
    match = re.match(
        r'^([1-9]\d*!)?(0|[1-9]\d*)'
        r'(\.(0|[1-9]\d*))'
        r'*((a|b|rc)(0|[1-9]\d*))'
        r'?(\.post(0|[1-9]\d*))'
        r'?(\.dev(0|[1-9]\d*))?$', version)

    return match is not None


def extract_components(version):
    """Return the components from `version` as a dict"""
    if not is_canonical(version):
        raise ValueError(
            "The supplied `version` is not conformant with PEP440"
        )

    _regex = re.compile(
        r"^\s*" + VERSION_PATTERN + r"\s*$",
        re.VERBOSE | re.IGNORECASE,
    )
    match = _regex.search(version)

    _pre = None
    if match.group("pre_l"):
        _pre = (match.group("pre_l"), int(match.group("pre_n")))

    _post = None
    if match.group("post_l"):
        _post = (match.group("post_l"),
                 int(match.group("post_n1") or match.group("post_n2")))

    _dev = None
    if match.group("dev_l"):
        _dev = (match.group("dev_l"), int(match.group("dev_n")))

    components = {
        'epoch' : int(match.group("epoch")) if match.group("epoch") else 0,
        'release' : tuple(int(ii) for ii in match.group("release").split(".")),
        'pre' : _pre,
        'post' : _post,
        'dev' : _dev,
        'local' : match.group("local"),
    }

    return components


assert is_canonical(__version__)
__version_info__ = extract_components(__version__)
