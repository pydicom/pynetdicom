"""Version information for pynetdicom3 based on PEP396 and 440.

`VERSION_PATTERN`, `_parse_letter_version` and parts of `extract_components`
are taken from the pypa packaging project (https://github.com/pypa/packaging)
which is dual licensed:
> This file is dual licensed under the terms of the Apache License, Version
> 2.0, and the BSD License. See the LICENSE file in the root of (the pypa)
> repository for complete details.

The Apache License v2.0 is available at
    https://www.apache.org/licenses/LICENSE-2.0
"""

import re


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


def _parse_letter_version(letter, number):
    """Parse the version component `letter` and `number`.

    Parameters
    ----------
    letter : str or None
    number : str or None

    Returns
    -------
    tuple or None
        Returns None if letter is None, otherwise returns a tuple containing
        the parsed component in a format that meets PEP440 for pre-release,
        post-release and dev components.
    """
    if letter:
        # We normalize any letters to their lower case form
        letter = letter.lower()

        return letter, int(number)


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

    components = {
        'epoch' : int(match.group("epoch")) if match.group("epoch") else 0,
        'release' : tuple(int(i) for i in match.group("release").split(".")),
        'pre-release' : _parse_letter_version(
            match.group("pre_l"),
            match.group("pre_n")
        ),
        'post-release' : _parse_letter_version(
            match.group("post_l"),
            match.group("post_n1") or match.group("post_n2")
        ),
        'dev' : _parse_letter_version(
            match.group("dev_l"),
            match.group("dev_n")
        ),
        'local' : match.group("local"),
    }

    return components


__version__ = '1.0.0.dev0'
assert is_canonical(__version__)
__version_info__ = extract_components(__version__)
