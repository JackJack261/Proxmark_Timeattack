"""Answer normalization: compare player-typed hex answers loosely."""

import re

_SEPARATORS = re.compile(r"[\s:-]")


def norm_hex(s: str) -> str:
    """Lowercase a hex string and strip whitespace and ':'/'-' separators."""
    return _SEPARATORS.sub("", s.strip().lower())
