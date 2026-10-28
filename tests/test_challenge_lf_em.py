import random
import re

from pm3trainer.cards import CardKind
from pm3trainer.challenges.base import Mode
from pm3trainer.challenges.lf_em_create import READ_COMMAND, LfEmCreate
from pm3trainer.testing import FakeSession


def _search_output(em_id: str) -> str:
    return f"[+] EM 410x ID {em_id}\n[+] Valid EM410x ID found!\n"


def _make(seed: int = 1) -> LfEmCreate:
    return LfEmCreate(random.Random(seed))


def test_randomizes_10hex_id():
    for seed in range(50):
        c = _make(seed)
        assert re.fullmatch(r"[0-9a-f]{10}", c.em_id)
        assert c.em_id in c.task_prompt.lower()
    assert len({_make(seed).em_id for seed in range(50)}) > 1


def test_check_passes_on_match():
    c = _make()
    session = FakeSession({READ_COMMAND: _search_output(c.em_id.upper())})
    assert c.check(session, None) is True
    assert session.sent == [READ_COMMAND]


def test_check_fails_on_mismatch():
    c = _make()
    other = "0123456789" if c.em_id != "0123456789" else "9876543210"
    session = FakeSession({READ_COMMAND: _search_output(other)})
    assert c.check(session, None) is False
    session = FakeSession({READ_COMMAND: "[!] No known/supported 125/134 kHz tags found\n"})
    assert c.check(session, None) is False


def test_has_hints_and_solution():
    c = _make()
    assert isinstance(c.hints, list) and c.hints
    assert all(isinstance(h, str) and h for h in c.hints)
    assert isinstance(c.solution, str) and c.solution
    assert "lf em 410x clone" in c.solution
    assert c.em_id in c.solution
    assert c.hints is not _make().hints


def test_mode_and_card():
    c = _make()
    assert c.mode is Mode.CREATE
    assert c.required_card is CardKind.T5577
