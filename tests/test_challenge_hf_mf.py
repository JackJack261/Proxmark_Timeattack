import random
import re

from pm3trainer.cards import CardKind
from pm3trainer.challenges.base import Mode
from pm3trainer.challenges.hf_mf_create import READ_COMMAND, HfMfCreate
from pm3trainer.testing import FakeSession


def _info_output(uid: str) -> str:
    spaced = " ".join(uid[i:i + 2] for i in range(0, len(uid), 2))
    return f"[+]  UID: {spaced.upper()}\n[+] Magic capabilities... Gen 1a\n"


def _make(seed: int = 1) -> HfMfCreate:
    return HfMfCreate(random.Random(seed))


def test_randomizes_4byte_uid():
    for seed in range(50):
        c = _make(seed)
        assert re.fullmatch(r"[0-9a-f]{8}", c.uid)
        assert c.uid in c.task_prompt.lower()
    assert len({_make(seed).uid for seed in range(50)}) > 1


def test_check_passes_on_match():
    c = _make()
    session = FakeSession({READ_COMMAND: _info_output(c.uid)})
    assert c.check(session, None) is True
    assert session.sent == [READ_COMMAND]


def test_check_fails_on_mismatch():
    c = _make()
    other = "01234567" if c.uid != "01234567" else "89abcdef"
    session = FakeSession({READ_COMMAND: _info_output(other)})
    assert c.check(session, None) is False
    session = FakeSession({READ_COMMAND: "[!] iso14443a card select failed\n"})
    assert c.check(session, None) is False


def test_has_hints_and_solution():
    c = _make()
    assert isinstance(c.hints, list) and c.hints
    assert all(isinstance(h, str) and h for h in c.hints)
    assert isinstance(c.solution, str) and c.solution
    assert "hf mf csetuid" in c.solution
    assert c.uid in c.solution
    assert c.hints is not _make().hints


def test_mode_and_card():
    c = _make()
    assert c.mode is Mode.CREATE
    assert c.required_card is CardKind.MAGIC_MIFARE


def test_uid_keeps_nxp_manufacturer_first_byte():
    import random
    from pm3trainer.challenges.hf_mf_create import HfMfCreate, UID_MANUFACTURER_BYTE
    for seed in range(50):
        uid = HfMfCreate(random.Random(seed)).uid
        assert len(uid) == 8
        assert uid.startswith(UID_MANUFACTURER_BYTE)
        assert not uid.startswith("88")  # never a cascade-tag first byte
