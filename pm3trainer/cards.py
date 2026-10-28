"""Card presentation & type verification.

Detection commands and expected output substrings are best-effort guesses and
are collected here as constants so on-hardware calibration (Task 15) can adjust
them in one place.
"""

import re
from dataclasses import dataclass
from enum import Enum

from pm3trainer.guard import CardState
from pm3trainer.parsers import parse_search_kind, strip_ansi


class CardKind(Enum):
    T5577 = "T5577"
    MAGIC_MIFARE = "MAGIC_MIFARE"
    WRITABLE_ICLASS = "WRITABLE_ICLASS"


@dataclass
class CardCheck:
    ok: bool
    state: CardState
    detail: str


# --- Detection commands (calibrate on hardware in Task 15) -------------------
SEARCH_CMD = "auto"
T5577_INFO_CMD = "lf t55xx detect"
MAGIC_INFO_CMD = "hf 14a info"
ICLASS_INFO_CMD = "hf iclass info"

# --- Expected output patterns (calibrate on hardware in Task 15) -------------
T5577_CHIP_RE = re.compile(r"\bChip\s+Type\s*:\s*T55", re.IGNORECASE)
T5577_PASSWORD_SET_RE = re.compile(r"\bPassword\s+set\s*:\s*Yes\b", re.IGNORECASE)
MAGIC_RE = re.compile(r"\bMagic\s+capabilities\b", re.IGNORECASE)
ICLASS_RE = re.compile(r"\b(?:iCLASS|PicoPass)\b", re.IGNORECASE)
# Lines carrying a negation ("No iCLASS tag found") never count as a positive match.
_NEGATED_LINE_RE = re.compile(r"\b(?:no|not|invalid|failed)\b", re.IGNORECASE)

# kind -> (expected band, info command, chip pattern, description)
_SPECS = {
    CardKind.T5577: ("LF", T5577_INFO_CMD, T5577_CHIP_RE, "a T5577 chip"),
    CardKind.MAGIC_MIFARE: ("HF", MAGIC_INFO_CMD, MAGIC_RE, "a magic (UID-writable) Mifare card"),
    CardKind.WRITABLE_ICLASS: ("HF", ICLASS_INFO_CMD, ICLASS_RE, "an iCLASS/PicoPass card"),
}


def _matches(pattern: "re.Pattern[str]", text: str) -> bool:
    return any(
        pattern.search(line) and not _NEGATED_LINE_RE.search(line)
        for line in strip_ansi(text).splitlines()
    )


def verify_card(session, expected: CardKind) -> CardCheck:
    """Confirm the card on the reader is the `expected` kind."""
    band, info_cmd, chip_re, description = _SPECS[expected]

    found = parse_search_kind(session.run(SEARCH_CMD))
    if found is None:
        return CardCheck(False, CardState(password_set=None), "No card detected on the reader.")
    if found != band:
        return CardCheck(
            False,
            CardState(password_set=None),
            f"Found a {found} card, but this challenge needs {description} ({band}).",
        )

    info = session.run(info_cmd)
    if not _matches(chip_re, info):
        return CardCheck(
            False,
            CardState(password_set=None),
            f"A {band} card is present, but it does not look like {description}.",
        )

    password_set = None
    if expected is CardKind.T5577:
        password_set = _matches(T5577_PASSWORD_SET_RE, info)
    return CardCheck(True, CardState(password_set=password_set), f"Verified {description}.")
