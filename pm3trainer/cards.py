"""Card presentation & type verification.

Detection commands and expected output substrings are calibrated against a real
Iceman pm3 client where noted; HF paths are still best-effort pending on-device
calibration and are collected here as constants so they can be adjusted in one
place.
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
LF_SEARCH_CMD = "lf search"      # calibrated: prints "Chipset... T55xx" for a T5577
HF_SEARCH_CMD = "hf search"
T5577_DETECT_CMD = "lf t55xx detect"  # fallback: detects the chip even on a blank card
MAGIC_INFO_CMD = "hf 14a info"
ICLASS_INFO_CMD = "hf iclass info"

# --- Expected output patterns ------------------------------------------------
# Matches the chipset line of `lf search` ("Chipset... T55xx") and of
# `lf t55xx detect` ("Chip type......... T55x7"), regardless of punctuation.
T5577_CHIP_RE = re.compile(r"\bT55(?:xx|x7|77)\b", re.IGNORECASE)
T5577_PASSWORD_SET_RE = re.compile(r"\bPassword\s+set\W+Yes\b", re.IGNORECASE)
MAGIC_RE = re.compile(r"\bMagic\s+capabilities\b", re.IGNORECASE)
ICLASS_RE = re.compile(r"\b(?:iCLASS|PicoPass)\b", re.IGNORECASE)
# Lines carrying a negation ("No iCLASS tag found") never count as a positive match.
_NEGATED_LINE_RE = re.compile(r"\b(?:no|not|invalid|failed)\b", re.IGNORECASE)

# HF kinds: (search command, info command, chip pattern, description)
_HF_SPECS = {
    CardKind.MAGIC_MIFARE: (HF_SEARCH_CMD, MAGIC_INFO_CMD, MAGIC_RE, "a magic (UID-writable) Mifare card"),
    CardKind.WRITABLE_ICLASS: (HF_SEARCH_CMD, ICLASS_INFO_CMD, ICLASS_RE, "an iCLASS/PicoPass card"),
}


def _matches(pattern: "re.Pattern[str]", text: str) -> bool:
    return any(
        pattern.search(line) and not _NEGATED_LINE_RE.search(line)
        for line in strip_ansi(text).splitlines()
    )


def _verify_t5577(session) -> CardCheck:
    # `lf search` shows "Chipset... T55xx" when a T5577 holds readable data.
    text = session.run(LF_SEARCH_CMD)
    chip_text = text if _matches(T5577_CHIP_RE, text) else None
    if chip_text is None:
        # Fall back to the canonical detect, which also finds a blank T5577.
        detect = session.run(T5577_DETECT_CMD)
        if _matches(T5577_CHIP_RE, detect):
            chip_text = detect
    if chip_text is None:
        if parse_search_kind(text) == "HF":
            return CardCheck(False, CardState(None),
                             "Found an HF card, but this challenge needs a T5577 (LF).")
        return CardCheck(False, CardState(None),
                         "No T5577 detected. Place a T5577 (LF) card on the antenna.")
    password_set = _matches(T5577_PASSWORD_SET_RE, chip_text)
    return CardCheck(True, CardState(password_set=password_set), "Verified a T5577 chip.")


def verify_card(session, expected: CardKind) -> CardCheck:
    """Confirm the card on the reader is the `expected` kind."""
    if expected is CardKind.T5577:
        return _verify_t5577(session)

    search_cmd, info_cmd, chip_re, description = _HF_SPECS[expected]
    found = parse_search_kind(session.run(search_cmd))
    if found is None:
        return CardCheck(False, CardState(password_set=None), "No card detected on the reader.")
    if found != "HF":
        return CardCheck(
            False,
            CardState(password_set=None),
            f"Found a {found} card, but this challenge needs {description} (HF).",
        )

    info = session.run(info_cmd)
    if not _matches(chip_re, info):
        return CardCheck(
            False,
            CardState(password_set=None),
            f"An HF card is present, but it does not look like {description}.",
        )
    return CardCheck(True, CardState(password_set=None), f"Verified {description}.")
