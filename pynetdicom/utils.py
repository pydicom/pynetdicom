"""Various utility functions."""

from contextlib import contextmanager
from io import BytesIO
import logging
import sys
from types import TracebackType
from typing import List, Optional, Iterator, Union, cast, Callable, Tuple, Type
import unicodedata

try:
    import ctypes
    HAVE_CTYPES = True
except ImportError:
    HAVE_CTYPES = False

from pydicom.uid import UID

from pynetdicom import _config


LOGGER = logging.getLogger('pynetdicom.utils')


class as_uid:
    """Context manager for converting values to UID.

    .. versionadded:: 2.0

    Examples
    --------

    >>> with as_uid(value, "Transfer Syntax Name") as uid:
    ...    self._transfer_syntax_name = uid
    """
    def __init__(
        self,
        value: Union[None, str, bytes, UID],
        name: str,
        allow_none: bool = True,
        validate: bool = True
    ) -> None:
        """Convert `value` to a UID.

        Parameters
        ----------
        value : str, bytes, UID (and optionally None)
            The value to be converted.
        name : str
            The name of the parameter being converted.
        allow_none : bool, optional
            Allow the returned value to be ``None`` if `value` is ``None``
            (default ``True``).
        validate : bool, optional
            If ``True`` (default) perform validation of the UID using
            :func:`~pynetdicom.utils.validate_uid` and raise a
            :class:`ValueError` exception if the validation fails. If ``False``
            return the UID without performing and validation.

        Returns
        -------
        pydicom.uid.UID or None
            If ``allow_none`` is ``True`` then may return ``None``, otherwise
            only a UID will be returned.
        """
        self.value = value
        self.name = name
        self.allow_none = allow_none
        self.validate = validate

    def __enter__(self) -> Optional[UID]:
        """Return the value converted to a UID, or None if allowed."""
        if self.allow_none and self.value is None:
            return None

        if isinstance(self.value, bytes):
            self.value = decode_bytes(self.value)

        if isinstance(self.value, str):  # Includes UID
            self.value = UID(self.value)

        if isinstance(self.value, UID):
            if not self.validate:
                return self.value

            # Note: conformance may be different from validity
            if self.value and not validate_uid(self.value):
                msg = (
                    f"Invalid UID '{self.value}' used with the "
                    f"'{self.name}' parameter"
                )
                LOGGER.error(msg)
                raise ValueError(msg)

            if self.value and not self.value.is_valid:
                LOGGER.warning(
                    f"Non-conformant UID '{self.value}' used with the "
                    f"'{self.name}' parameter"
                )

            # Note: an empty UID will skip validation
            return self.value

        raise TypeError(
            f"'{self.name}' must be str, bytes or UID, not "
            f"'{self.value.__class__.__name__}'"
        )

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType]
    ) -> Optional[bool]:
        # Raise any exceptions
        return None


def decode_bytes(
    encoded_value: bytes, codecs: Tuple[str, ...] = _config.PDU_CODECS
) -> str:
    """Return the decoded string from `encoded_value`.

    .. versionadded:: 2.0

    Parameters
    ----------
    encoded_value : bytes
        The encoded value to be decoded.
    codecs : Tuple[str, ...], optional
        A tuple of codec names to use when attempting to decode, defaults
        to :attr:`~pynetdicom._config.PDU_CODECS`. See the `Python
        documentation
        <https://docs.python.org/3/library/codecs.html#standard-encodings>`_
        for possible codecs.

    Returns
    -------
    str
        The decoded value

    Raises
    ------
    UnicodeDecodeError
        If unable to decode the encoded value.
    """
    for codec in codecs or ('ascii', ):
        try:
            return encoded_value.decode(codec, errors='strict')
        except UnicodeDecodeError as exc:
            LOGGER.exception(exc)

    as_hex = ' '.join([f"{b:02X}" for b in encoded_value])
    raise ValueError(
        f"Unable to decode '{as_hex}' with {', '.join(codecs)}"
    )


def make_target(target_fn: Callable) -> Callable:
    """Wraps `target_fn` in a thunk that passes all contextvars from the
    current context. It is assumed that `target_fn` is the target of a new
    ``threading.Thread``.

    Requires:
    * Python >=3.7
    * :attr:`~pynetdicom._config.PASS_CONTEXTVARS` set ``True``

    If the requirements are not met, the original `target_fn` is returned.

    Parameters
    ----------
    target_fn : Callable
        The function to wrap

    Returns
    -------
    Callable
        The wrapped `target_fn` if requirements are met, else the original
        `target_fn`.
    """
    if _config.PASS_CONTEXTVARS:
        try:
            from contextvars import copy_context
        except ImportError as e:
            raise RuntimeError("PASS_CONTEXTVARS requires Python >=3.7") from e
        ctx = copy_context()
        return lambda: ctx.run(target_fn)
    return target_fn


def pretty_bytes(
    bytestream: Union[bytes, BytesIO],
    prefix: str = '  ',
    delimiter: str = '  ',
    items_per_line: int = 16,
    max_size: Optional[int] = 512,
    suffix: str = ''
) -> List[str]:
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
        lines.insert(0, prefix + f"Only dumping {max_size} bytes.")

    return lines


@contextmanager
def set_timer_resolution(resolution: Optional[float]) -> Iterator[None]:
    """Set the Windows timer resolution.

    Parameters
    ----------
    resolution: float or None
        The desired timer resolution in milliseconds. If `resolution` is not in
        the allowed range then the timer resolution will be set to the minimum
        or maximum allowed instead. If ``None`` then the timer resolution will
        not be changed.

    Yields
    ------
    None
    """
    if HAVE_CTYPES and sys.platform == "win32" and resolution is not None:
        dll = ctypes.WinDLL("NTDLL.DLL")  # type: ignore

        minimum = ctypes.c_ulong()  # Minimum delay allowed
        maximum = ctypes.c_ulong()  # Maximum delay allowed
        current = ctypes.c_ulong()  # Current delay

        dll.NtQueryTimerResolution(
            ctypes.byref(maximum), ctypes.byref(minimum), ctypes.byref(current)
        )

        # Make sure the desired resolution is in the valid range
        # Timer resolution is in 100 ns units -> 10,000 == 1 ms
        resolution = cast(float, resolution)
        resolution = max(int(resolution * 10000), minimum.value)
        resolution = min(resolution, maximum.value)

        # Set the timer resolution
        dll.NtSetTimerResolution(resolution, 1, ctypes.byref(current))

        yield None

        # Reset the timer resolution
        dll.NtSetTimerResolution(resolution, 0, ctypes.byref(current))
    else:
        yield None


def validate_ae_title(
    ae_title: Union[str, bytes], use_short: bool = False
) -> bytes:
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
    bytes
        A valid AE title, truncated to 16 characters if necessary.

    Raises
    ------
    ValueError
        If `ae_title` is an empty string, contains only spaces or contains
        control characters or backslash.
    """
    if not isinstance(ae_title, (str, bytes)):
        raise TypeError("AE titles must be str or bytes")

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

    if not _config.ALLOW_LONG_DIMSE_AET:
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

    return ae_title.encode('ascii', errors='strict')


def validate_uid(uid: UID) -> bool:
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

    return 0 < len(uid) < 65
