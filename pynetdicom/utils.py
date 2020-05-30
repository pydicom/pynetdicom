"""Various utility functions."""

from io import BytesIO
import logging
import sys
import unicodedata

from pynetdicom import _config


LOGGER = logging.getLogger('pynetdicom.utils')


def pretty_bytes(bytestream, prefix='  ', delimiter='  ', items_per_line=16,
                 max_size=512, suffix=''):
    """Turn the bytestring `bytestream` into a :class:`list` of nicely
    formatted :class:`str`.

    Parameters
    ----------
    bytestream : bytes or io.BytesIO
        The bytes to convert to a nicely formatted string list
    prefix : str
        Insert `prefix` at the start of every item in the output string list
    delimiter : str
        Delimit each of the bytes in `bytestream` using `delimiter`
    items_per_line : int
        The number of bytes in each item of the output string list.
    max_size : int or None
        The maximum number of bytes to add to the output string list. A value
        of ``None`` indicates that all of `bytestream` should be output.
    suffix : str
        Append `suffix` to the end of every item in the output string list

    Returns
    -------
    list of str
        The output string list
    """
    lines = []
    if isinstance(bytestream, BytesIO):
        bytestream = bytestream.getvalue()

    cutoff_output = False
    byte_count = 0
    for ii in range(0, len(bytestream), items_per_line):
        # chunk is a bytes in python3 and a str in python2
        chunk = bytestream[ii:ii + items_per_line]
        byte_count += len(chunk)

        # Python 2 compatibility
        if isinstance(chunk, str):
            gen = (format(ord(x), '02x') for x in chunk)
        else:
            gen = (format(x, '02x') for x in chunk)


        if max_size is not None and byte_count <= max_size:
            line = prefix + delimiter.join(gen)
            lines.append(line + suffix)
        elif max_size is not None and byte_count > max_size:
            cutoff_output = True
            break
        else:
            line = prefix + delimiter.join(gen)
            lines.append(line + suffix)

    if cutoff_output:
        lines.insert(0, prefix + 'Only dumping {0!s} bytes.'.format(max_size))

    return lines


def validate_ae_title(ae_title, use_short=False):
    """Return a valid AE title from `ae_title`, if possible.

    An AE title:

    * Must be no more than 16 characters
    * Leading and trailing spaces are not significant
    * The characters should belong to the Default Character Repertoire
      excluding ``0x5C`` (backslash) and all control characters

    If the supplied `ae_title` is greater than 16 characters once
    non-significant spaces have been removed then the returned AE title
    will be truncated to remove the excess characters.

    If the supplied `ae_title` is less than 16 characters once non-significant
    spaces have been removed, the spare trailing characters will be set to
    space (``0x20``) provided `use_short` is ``False``.

    .. versionchanged:: 1.1

        Changed to only return ``bytes`` for Python 3.

    .. versionchanged:: 1.5

        Added `use_short` keyword parameter.

    Parameters
    ----------
    ae_title : bytes
        The AE title to check.
    use_short : bool, optional
        If ``False`` (default) then pad AE titles with trailing spaces up to
        the maximum allowable length (16 bytes), otherwise no padding will
        be added.

    Returns
    -------
    str or bytes
        A valid AE title truncated to 16 characters if necessary. If Python 3
        then only returns :class:`bytes`, if Python 2 then returns
        :class:`str`.

    Raises
    ------
    ValueError
        If `ae_title` is an empty string, contains only spaces or contains
        control characters or backslash.
    """
    if not isinstance(ae_title, (str, bytes)):
        raise TypeError("AE titles must be str or bytes")

    # Python 2 - convert string to unicode
    if sys.version_info[0] == 2:
        ae_title = unicode(ae_title)

    # If bytes decode to ascii string
    if isinstance(ae_title, bytes):
        ae_title = ae_title.decode('ascii', errors='strict')

    # Strip out any leading or trailing spaces
    ae_title = ae_title.strip()
    # Strip out any leading or trailing nulls - non-conformant
    ae_title = ae_title.strip('\0')
    if not ae_title:
        raise ValueError(
            "AE titles are not allowed to consist entirely of only spaces"
        )

    # Truncate if longer than 16 characters
    ae_title = ae_title[:16]
    if not use_short:
        # Pad out to 16 characters using spaces
        ae_title = ae_title.ljust(16)

    # Unicode category: 'Cc' is control characters
    invalid = [
        char for char in ae_title
        if unicodedata.category(char)[0] == 'C' or char == '\\'
    ]
    if invalid:
        raise ValueError(
            "AE titles must not contain any control characters or backslashes"
        )

    # Return as bytes (python 3) or str (python 2)
    return ae_title.encode('ascii', errors='strict')


def validate_uid(uid):
    """Return True if `uid` is considered valid.

    If :attr:`~pynetdicom._config.ENFORCE_UID_CONFORMANCE` is ``True`` then the
    following rules apply:

    * 1-64 characters, inclusive
    * Each component may not start with 0 unless the component itself is 0
    * Components are separated by ``.``
    * Valid component characters are 0-9 of the Basic G0 Set of the
      International Reference Version of ISO 646:1990 (ASCII)

    If :attr:`~pynetdicom._config.ENFORCE_UID_CONFORMANCE` is ``False`` then
    the following rules apply:

    * 1-64 characters, inclusive

    Parameters
    ----------
    uid : pydicom.uid.UID
        The UID to check for validity.

    Returns
    -------
    bool
        ``True`` if the value is considered valid, ``False`` otherwise.
    """
    if _config.ENFORCE_UID_CONFORMANCE:
        return uid.is_valid

    if 0 < len(uid) < 65:
        return True

    return False
