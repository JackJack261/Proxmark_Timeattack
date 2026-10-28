import random
import re

from pm3trainer.cards import CardKind
from pm3trainer.challenges.base import Mode
from pm3trainer.challenges.hf_iclass_create import (
    BLOCK,
    READ_TEMPLATE,
    HfIclassCreate,
)
from pm3trainer.testing import FakeSession

READ_COMMAND = READ_TEMPLATE.format(block=BLOCK)


def _dump_output(data: str) -> str:
    """Canned block dump in the format parse_iclass_block understands."""
    spaced = " ".join(data[i:i + 2] for i in range(0, len(data), 2)).upper()
    return (
        "[=] --- Tag Information ---------------------\n"
        f"[=] block {BLOCK:02d}/0x{BLOCK:02x} : {spaced}\n"
    )


def _make(seed: int = 1) -> HfIclassCreate:
    return HfIclassCreate(random.Random(seed))


def test_randomizes_block_data():
    for seed in range(50):
        c = _make(seed)
        assert re.fullmatch(r"[0-9a-f]{16}", c.data)
        assert c.data in c.task_prompt.lower()
        assert str(BLOCK) in c.task_prompt
    assert len({_make(seed).data for seed in range(50)}) > 1


def test_check_passes_on_match():
    c = _make()
    session = FakeSession({READ_COMMAND: _dump_output(c.data)})
    assert c.check(session, None) is True
    assert session.sent == [READ_COMMAND]


def test_check_fails_on_mismatch():
    c = _make()
    other = "0123456789abcdef" if c.data != "0123456789abcdef" else "fedcba9876543210"
    session = FakeSession({READ_COMMAND: _dump_output(other)})
    assert c.check(session, None) is False
    session = FakeSession({READ_COMMAND: "[!] iClass card select failed\n"})
    assert c.check(session, None) is False


def test_has_hints_and_solution():
    c = _make()
    assert isinstance(c.hints, list) and c.hints
    assert all(isinstance(h, str) and h for h in c.hints)
    assert isinstance(c.solution, str) and c.solution
    assert "hf iclass" in c.solution
    assert c.data in c.solution
    assert str(BLOCK) in c.solution
    assert c.hints is not _make().hints


def test_mode_and_card():
    c = _make()
    assert c.mode is Mode.CREATE
    assert c.required_card is CardKind.WRITABLE_ICLASS
