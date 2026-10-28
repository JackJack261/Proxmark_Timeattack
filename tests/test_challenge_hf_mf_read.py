import random
import re

from pm3trainer.cards import CardKind
from pm3trainer.challenges.base import Mode
from pm3trainer.challenges.hf_mf_create import SET_UID_TEMPLATE
from pm3trainer.challenges.hf_mf_read import HfMfRead
from pm3trainer.testing import FakeSession


def _make(seed: int = 1) -> HfMfRead:
    return HfMfRead(random.Random(seed))


def _setup(seed: int = 1):
    c = _make(seed)
    session = FakeSession({})
    c.setup(session)
    return c, session


def test_setup_writes_random_uid():
    c, session = _setup()
    assert len(session.sent) == 1
    m = re.fullmatch(r"hf mf csetuid -u ([0-9a-f]{8})", session.sent[0])
    assert m is not None
    assert session.sent[0] == SET_UID_TEMPLATE.format(uid=m.group(1))
    assert c.solution == m.group(1)
    assert len({_setup(seed)[1].sent[0] for seed in range(50)}) > 1


def test_check_passes_on_match():
    c, session = _setup()
    truth = c.solution
    mixed = ":".join(truth[i : i + 2] for i in range(0, 8, 2)).upper()
    session.sent.clear()
    assert c.check(session, mixed) is True
    assert c.check(session, truth) is True
    assert session.sent == []  # check never touches the device


def test_check_fails_on_mismatch():
    c, session = _setup()
    wrong = f"{(int(c.solution, 16) + 1) % (1 << 32):08x}"
    assert c.check(session, wrong) is False
    assert c.check(session, "") is False
    assert c.check(session, None) is False


def test_has_hints_and_solution():
    c, session = _setup()
    assert len(c.hints) >= 2
    assert any("hf search" in h for h in c.hints)
    assert any("hf mf info" in h for h in c.hints)
    assert c.solution in session.sent[0]
    assert re.fullmatch(r"[0-9a-f]{8}", c.solution)


def test_mode_and_card():
    c = _make()
    assert c.mode is Mode.READ
    assert c.required_card is CardKind.MAGIC_MIFARE
