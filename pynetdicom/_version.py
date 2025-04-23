"""Version information for pynetdicom based on PEP396 and 440"""

import re


# pynetdicom version
__version__: str = "3.0.0.dev0"

# DICOM Standard version used for SOP classes and instances
__dicom_version__: str = "2025b"

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


def is_canonical(version: str) -> bool:
    """Return True if `version` is a PEP440 conformant version."""
    match = re.match(
        (
            r"^([1-9]\d*!)?(0|[1-9]\d*)"
            r"(\.(0|[1-9]\d*))"
            r"*((a|b|rc)(0|[1-9]\d*))"
            r"?(\.post(0|[1-9]\d*))"
            r"?(\.dev(0|[1-9]\d*))?$"
        ),
        version,
    )

    return match is not None


assert is_canonical(__version__)
