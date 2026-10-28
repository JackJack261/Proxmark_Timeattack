"""Pure parsers for Proxmark3 ``pm3`` client text output."""

import re
from dataclasses import dataclass
from typing import Optional

_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

_HID_RE = re.compile(r"\bFC:\s*(\d+)\s+CN:\s*(\d+)", re.IGNORECASE)
_EM410X_RE = re.compile(r"\bEM\s*410x\s+ID\s+([0-9A-Fa-f]{10})\b", re.IGNORECASE)
_MIFARE_UID_RE = re.compile(r"\bUID\s*:\s*((?:[0-9A-Fa-f]{2}[ \t]*)+)", re.IGNORECASE)

_LF_MARKERS = re.compile(
    r"Valid\s+(?:EM410x|HID|Indala|AWID|FDX-?B|T55xx|Pyramid|Viking|Paradox)\b"
    r"|\bEM\s*410x\s+ID\b",
    re.IGNORECASE,
)
_HF_MARKERS = re.compile(
    r"Valid\s+(?:ISO\s*14443|Mifare|iCLASS|PicoPass|ISO\s*15693|LEGIC|DESFire)\b"
    r"|iCLASS\s+tag|PicoPass\s+tag|\bISO14443-a\s+Information",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class HidResult:
    fc: int
    cn: int


def strip_ansi(text: str) -> str:
    """Remove ANSI escape (color/cursor) sequences."""
    return _ANSI_RE.sub("", text)


def parse_hid(text: str) -> Optional[HidResult]:
    m = _HID_RE.search(strip_ansi(text))
    if not m:
        return None
    return HidResult(int(m.group(1)), int(m.group(2)))


def parse_em410x(text: str) -> Optional[str]:
    m = _EM410X_RE.search(strip_ansi(text))
    return m.group(1).lower() if m else None


def parse_mifare_uid(text: str) -> Optional[str]:
    m = _MIFARE_UID_RE.search(strip_ansi(text))
    if not m:
        return None
    return re.sub(r"\s+", "", m.group(1)).lower()


def parse_iclass_block(text: str, block: int) -> Optional[str]:
    pattern = re.compile(
        r"\bblock\s+0*%d(?:/0x[0-9A-Fa-f]+)?\s*:\s*((?:[0-9A-Fa-f]{2}[ \t]*){8})(?![0-9A-Fa-f])"
        % block,
        re.IGNORECASE,
    )
    m = pattern.search(strip_ansi(text))
    if not m:
        return None
    return re.sub(r"\s+", "", m.group(1)).lower()


def parse_search_kind(text: str) -> Optional[str]:
    """Classify ``auto``/``search`` output as ``"LF"``, ``"HF"`` or ``None``."""
    clean = strip_ansi(text)
    if _LF_MARKERS.search(clean):
        return "LF"
    if _HF_MARKERS.search(clean):
        return "HF"
    return None
