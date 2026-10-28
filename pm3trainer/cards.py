"""Card presentation & type verification.

Detection commands and expected output patterns are collected here as constants
so on-hardware calibration can adjust them in one place. The T5577 patterns are
calibrated against a real Iceman client (`lf search` prints "Chipset... T55xx").
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


# --- Detection commands ------------------------------------------------------
LF_SEARCH_CMD = "lf search"
HF_SEARCH_CMD = "hf search"
T5577_INFO_CMD = "lf t55xx detect"
MAGIC_INFO_CMD = "hf 14a info"
ICLASS_INFO_CMD = "hf iclass info"

# --- Expected output patterns ------------------------------------------------
# Matches both `lf search` ("Chipset... T55xx") and `lf t55xx detect`
# ("Chip type......... T55x7", older clients "Chip Type      : T55x7").
T5577_CHIP_RE = re.compile(r"\bChip\s*(?:set|type)\b.*\bT55[x0-9]{2}\b", re.IGNORECASE)
# "Password set...... Yes" (Iceman) or "Password set : Yes" (older clients).
T5577_PASSWORD_SET_RE = re.compile(r"\bPassword\s+set\b[\s.:]*Yes\b", re.IGNORECASE)
MAGIC_RE = re.compile(r"\bMagic\s+capabilities\b", re.IGNORECASE)
ICLASS_RE = re.compile(r"\b(?:iCLASS|PicoPass)\b", re.IGNORECASE)
# Lines carrying a negation ("No iCLASS tag found") never count as a positive match.
_NEGATED_LINE_RE = re.compile(r"\b(?:no|not|invalid|failed)\b", re.IGNORECASE)

# HF kind -> (info command, chip pattern, description)
_HF_SPECS = {
    CardKind.MAGIC_MIFARE: (MAGIC_INFO_CMD, MAGIC_RE, "a magic (UID-writable) Mifare card"),
    CardKind.WRITABLE_ICLASS: (ICLASS_INFO_CMD, ICLASS_RE, "an iCLASS/PicoPass card"),
}


def _matches(pattern: "re.Pattern[str]", text: str) -> bool:
    return any(
        pattern.search(line) and not _NEGATED_LINE_RE.search(line)
        for line in strip_ansi(text).splitlines()
    )


def _not_ok(detail: str) -> CardCheck:
    return CardCheck(False, CardState(password_set=None), detail)


def _verify_t5577(session) -> CardCheck:
    # `lf search` reports "Chipset... T55xx" for a programmed T5577; a blank
    # one may show nothing, so `lf t55xx detect` is checked too. detect also
    # reports whether a password is set.
    search = session.run(LF_SEARCH_CMD)
    info = session.run(T5577_INFO_CMD)
    if not (_matches(T5577_CHIP_RE, search) or _matches(T5577_CHIP_RE, info)):
        if parse_search_kind(search) == "LF":
            return _not_ok("An LF card is present, but it does not look like a T5577 chip.")
        return _not_ok("No T5577 card detected on the reader (LF antenna).")
    password_set = _matches(T5577_PASSWORD_SET_RE, info)
    return CardCheck(True, CardState(password_set=password_set), "Verified a T5577 chip.")


def verify_card(session, expected: CardKind) -> CardCheck:
    """Confirm the card on the reader is the `expected` kind."""
    if expected is CardKind.T5577:
        return _verify_t5577(session)

    info_cmd, chip_re, description = _HF_SPECS[expected]
    if parse_search_kind(session.run(HF_SEARCH_CMD)) != "HF":
        return _not_ok(f"No HF card detected on the reader; this challenge needs {description}.")

    if not _matches(chip_re, session.run(info_cmd)):
        return _not_ok(f"An HF card is present, but it does not look like {description}.")
    return CardCheck(True, CardState(password_set=None), f"Verified {description}.")
