"""Various utility functions."""

import codecs
from io import BytesIO
import logging
import unicodedata


LOGGER = logging.getLogger('pynetdicom.utils')


def validate_ae_title(ae_title):
    """Return a valid AE title from `ae_title`, if possible.

    An AE title:

    * Must be no more than 16 characters
    * Leading and trailing spaces are not significant
    * The characters should belong to the Default Character Repertoire
      excluding 0x5C (backslash) and all control characters

    If the supplied `ae_title` is greater than 16 characters once
    non-significant spaces have been removed then the returned AE title
    will be truncated to remove the excess characters.

    If the supplied `ae_title` is less than 16 characters once non-significant
    spaces have been removed, the spare trailing characters will be set to
    space (0x20)

    Parameters
    ----------
    ae_title : str or bytes
        The AE title to check

    Returns
    -------
    str or bytes
        A valid AE title (with the same type as the supplied `ae_title`),
        truncated to 16 characters if necessary. If Python 3 then only returns
        bytes.

    Raises
    ------
    ValueError
        If `ae_title` is an empty string, contains only spaces or contains
        control characters or backslash
    TypeError
        If `ae_title` is not a string or bytes
    """
    try:
        is_bytes = False
        if isinstance(ae_title, bytes):
            is_bytes = True
            ae_title = ae_title.decode('ascii')

        # Remove leading and trailing spaces
        significant_characters = ae_title.strip()

        # Remove trailing nulls (required as AE titles may be padded by nulls)
        #   and common control chars (optional, for convenience)
        significant_characters = significant_characters.rstrip('\0\r\t\n')

        # Check for backslash or control characters
        for char in significant_characters:
            if unicodedata.category(char)[0] == "C" or char == "\\":
                raise ValueError("Invalid value for an AE title; must not "
                                 "contain backslash or control characters")

        # AE title OK
        if 0 < len(significant_characters) <= 16:
            while len(significant_characters) < 16:
                significant_characters += ' '

            if is_bytes:
                return codecs.encode(significant_characters, 'ascii')

            return significant_characters

        # AE title too long : truncate
        elif len(significant_characters.strip()) > 16:
            if is_bytes:
                return codecs.encode(significant_characters[:16], 'ascii')

            return significant_characters[:16]

        # AE title empty str
        else:
            raise ValueError("Invalid value for an AE title; must be a "
                             "non-empty string or bytes.")
    except AttributeError:
        raise TypeError("Invalid value for an AE title; must be a "
                        "non-empty string or bytes.")
    except ValueError:
        raise
    except:
        raise TypeError("Invalid value for an AE title; must be a "
                        "non-empty string or bytes.")


def pretty_bytes(bytestream, prefix='  ', delimiter='  ', items_per_line=16,
                 max_size=512, suffix=''):
    """Turn the bytestring `bytestream` into a list of nicely formatted str.

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
        of None indicates that all of `bytestream` should be output.
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
