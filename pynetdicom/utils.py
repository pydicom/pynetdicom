"""Various utility functions."""

from contextlib import contextmanager
from contextvars import copy_context
from io import BytesIO
import logging
import sys
from typing import Iterator, cast, Callable, Sequence

try:
    import ctypes

    HAVE_CTYPES = True
except ImportError:
    HAVE_CTYPES = False

from pydicom.uid import UID

from pynetdicom import _config


LOGGER = logging.getLogger(__name__)


def decode_bytes(encoded_value: bytes) -> str:
    """Return the decoded string from `encoded_value`.

    .. versionadded:: 2.0

    Parameters
    ----------
    encoded_value : bytes
        The encoded value to be decoded.

    Returns
    -------
    str
        The decoded ISO 646 (ASCII) string.
    """
    # Always try ASCII first
    try:
        return encoded_value.decode("ascii", errors="strict")
    except UnicodeDecodeError as exc:
        LOGGER.exception(exc)

    codecs: Sequence[str] = _config.CODECS
    codecs = [c for c in codecs if c not in ("ascii", "646", "us-ascii")]

    # If that fails then try the fallbacks and re-encode into ASCII
    for codec in codecs:
        try:
            value = encoded_value.decode(codec, errors="strict")
            encoded_value = value.encode("ascii", errors="ignore")
            return decode_bytes(encoded_value)
        except UnicodeError as exc:
            LOGGER.exception(exc)

    codecs.insert(0, "ascii")
    as_hex = " ".join([f"{b:02X}" for b in encoded_value])
    raise ValueError(
        f"Unable to decode '{as_hex}' using the {', '.join(codecs)} codec(s)"
    )


def make_target(target_fn: Callable) -> Callable:
    """Wraps `target_fn` in a thunk that passes all contextvars from the
    current context. It is assumed that `target_fn` is the target of a new
    ``threading.Thread``.

    Requires:

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
        ctx = copy_context()
        return lambda: ctx.run(target_fn)

    return target_fn


def pretty_bytes(
    bytestream: bytes | BytesIO,
    prefix: str = "  ",
    delimiter: str = "  ",
    items_per_line: int = 16,
    max_size: int | None = 512,
    suffix: str = "",
) -> list[str]:
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
        chunk = bytestream[ii : ii + items_per_line]
        byte_count += len(chunk)
        gen = (format(x, "02x") for x in chunk)

        if max_size is None or byte_count <= max_size:
            line = prefix + delimiter.join(gen)
            lines.append(line + suffix)
        else:
            cutoff_output = True
            break

    if cutoff_output:
        lines.insert(0, prefix + f"Only dumping {max_size} bytes.")

    return lines


def set_ae(
    value: str | None, name: str, allow_empty: bool = True, allow_none: bool = True
) -> str | None:
    """Convert `value` to an **AE** like parameter and apply validation.

    Parameters
    ----------
    value : str or None
        The value to be converted.
    name : str
        The name of the parameter being converted.
    allow_empty : bool, optional
        If ``True`` (default) skip validation when an empty string or ``None``
        is used.

    Returns
    -------
    str or None
        If ``allow_empty`` is ``True`` then may return ``None``, otherwise
        the string will be returned.
    """
    if allow_none and value is None:
        return None

    if isinstance(value, str):
        if not allow_empty and not value.strip():
            # E.g. Called and Calling AE Title may not be 16 spaces
            msg = f"Invalid '{name}' value - "
            if len(value):
                msg += "must not consist entirely of spaces"
            else:
                msg += "must not be an empty str"

            LOGGER.error(msg)
            raise ValueError(msg)

        if value:
            result, reason = _config.VALIDATORS["AE"](value)
            if not result:
                msg = f"Invalid '{name}' value '{value}' - {reason}"
                LOGGER.error(msg)
                raise ValueError(msg)

        return value

    s = "str or None" if allow_none else "str"
    raise TypeError(f"'{name}' must be {s}, not '{value.__class__.__name__}'")


def set_uid(
    value: None | str | bytes | UID,
    name: str,
    allow_empty: bool = True,
    allow_none: bool = True,
    validate: bool = True,
) -> UID | None:
    """Convert `value` to a :class:`UID` and apply validation.

    Parameters
    ----------
    value : str, bytes, UID (and optionally None)
        The value to be converted.
    name : str
        The name of the parameter being converted.
    allow_empty : bool, optional
        If ``True`` then allow an empty UID (default).
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
    if allow_none and value is None:
        return None

    if isinstance(value, bytes):
        value = decode_bytes(value)

    if isinstance(value, str):  # Includes UID
        value = UID(value)

    if isinstance(value, UID):
        if not value and not allow_empty:
            raise ValueError(f"Invalid '{name}' value - must not be an empty str")

        if not validate:
            return value

        # Note: conformance may be different from validity
        if value:
            result, reason = _config.VALIDATORS["UI"](value)
            if not result:
                msg = f"Invalid '{name}' value '{value}' - {reason}"
                LOGGER.error(msg)
                raise ValueError(msg)

        if value and not value.is_valid:
            LOGGER.warning(f"Non-conformant '{name}' value '{value}'")

        return value

    s = "str, bytes, UID or None" if allow_none else "str, bytes or UID"
    raise TypeError(f"'{name}' must be {s}, not '{value.__class__.__name__}'")


@contextmanager
def set_timer_resolution(resolution: float | None) -> Iterator[None]:
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
        original = current.value

        # Make sure the desired resolution is in the valid range
        # Timer resolution is in 100 ns units -> 10,000 == 1 ms
        resolution = cast(float, resolution)
        resolution = max(int(resolution * 10000), minimum.value)
        resolution = min(resolution, maximum.value)

        # Set the timer resolution
        dll.NtSetTimerResolution(resolution, 1, ctypes.byref(current))

        yield None

        # Reset the timer resolution to the original
        dll.NtSetTimerResolution(original, 1, ctypes.byref(current))

    else:
        yield None


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
