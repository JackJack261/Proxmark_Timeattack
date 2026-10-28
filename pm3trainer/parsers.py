"""Pure parsers for Proxmark3 ``pm3`` client text output."""

import re
from dataclasses import dataclass
from typing import Optional

_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

_HID_RE = re.compile(r"\bFC:\s*(\d+)\s+CN:\s*(\d+)", re.IGNORECASE)
_EM410X_RE = re.compile(r"\bEM\s*410x\s+ID\s+([0-9A-Fa-f]{10})\b", re.IGNORECASE)
# 4..10 hex byte pairs (space/colon separated or contiguous). The trailing
# lookaheads reject a dangling nibble or extra byte, so truncated or odd-length
# values never produce a (wrong) shorter UID.
_MIFARE_UID_RE = re.compile(
    r"\bUID\s*:\s*([0-9A-Fa-f]{2}(?:[ \t:]?[0-9A-Fa-f]{2}){3,9})"
    r"(?![0-9A-Fa-f])(?![ \t:]?[0-9A-Fa-f](?:[0-9A-Fa-f]|\b))",
    re.IGNORECASE,
)
_VALID_UID_BYTES = {4, 7, 8, 10}  # ISO14443-A single/double/triple, ISO15693

_LF_MARKERS = re.compile(
    r"\bValid\s+(?:EM410x|HID|Indala|AWID|FDX-?B|T55xx|Pyramid|Viking|Paradox)\b"
    r"|\bEM\s*410x\s+ID\b",
    re.IGNORECASE,
)
_HF_MARKERS = re.compile(
    r"\bValid\s+(?:ISO\s*14443|Mifare|iCLASS|PicoPass|ISO\s*15693|LEGIC|DESFire)\b"
    r"|\bISO14443-a\s+Information",
    re.IGNORECASE,
)
# Lines that negate a detection ("No iCLASS tag found", "Invalid EM410x ID").
_NEGATED_LINE = re.compile(r"\b(?:no|not|invalid|failed)\b", re.IGNORECASE)


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


def parse_hid_all(text: str) -> list[HidResult]:
    """Every FC/CN pair; the client prints one line per matching Wiegand format."""
    return [HidResult(int(fc), int(cn)) for fc, cn in _HID_RE.findall(strip_ansi(text))]


def parse_em410x(text: str) -> Optional[str]:
    m = _EM410X_RE.search(strip_ansi(text))
    return m.group(1).lower() if m else None


def parse_mifare_uid(text: str) -> Optional[str]:
    m = _MIFARE_UID_RE.search(strip_ansi(text))
    if not m:
        return None
    uid = re.sub(r"[\s:]", "", m.group(1)).lower()
    if len(uid) // 2 not in _VALID_UID_BYTES:
        return None
    return uid


def parse_iclass_block(text: str, block: int) -> Optional[str]:
    # The lookahead requires the row to end after exactly 8 data bytes
    # (optionally followed by a "(", "|" or "[" annotation).
    pattern = re.compile(
        r"\bblock\s+0*%d(?:/0x[0-9A-Fa-f]+)?\s*:\s*((?:[0-9A-Fa-f]{2}[ \t]*){8})"
        r"(?=$|[(|\[])" % block,
        re.IGNORECASE | re.MULTILINE,
    )
    m = pattern.search(strip_ansi(text))
    if not m:
        return None
    return re.sub(r"\s+", "", m.group(1)).lower()


def parse_search_kind(text: str) -> Optional[str]:
    """Classify ``auto``/``search`` output as ``"LF"``, ``"HF"`` or ``None``.

    Negated lines ("No ... tag found", "Invalid ...") are ignored. If both LF
    and HF markers appear the result is ambiguous and ``None`` is returned.
    """
    lf = hf = False
    for line in strip_ansi(text).splitlines():
        if _NEGATED_LINE.search(line):
            continue
        lf = lf or bool(_LF_MARKERS.search(line))
        hf = hf or bool(_HF_MARKERS.search(line))
    if lf == hf:
        return None
    return "LF" if lf else "HF"
