"""Small helpers with no platform access (unit-tested offline)."""

_TRUE = ("y", "yes", "t", "true", "on", "1")
_FALSE = ("n", "no", "f", "false", "off", "0")


def strtobool(value: str) -> bool:
    """Same rules as the removed ``distutils.util.strtobool`` (gone in Python 3.12), returning a bool.

    Raises ValueError for anything else, as distutils did.
    """
    normalized = value.strip().lower()
    if normalized in _TRUE:
        return True
    if normalized in _FALSE:
        return False
    raise ValueError(f"invalid truth value {value!r}")
