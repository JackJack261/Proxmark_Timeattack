import random
import re

from pm3trainer.cards import CardKind
from pm3trainer.challenges.base import Mode
from pm3trainer.challenges.lf_em_create import CLONE_TEMPLATE
from pm3trainer.challenges.lf_em_read import LfEmRead
from pm3trainer.testing import FakeSession


def _make(seed: int = 1) -> LfEmRead:
    return LfEmRead(random.Random(seed))


def _setup(seed: int = 1):
    c = _make(seed)
    session = FakeSession({})
    c.setup(session)
    return c, session


def test_setup_writes_random_id_and_records_sent():
    c, session = _setup()
    assert len(session.sent) == 1
    m = re.fullmatch(r"lf em 410x clone --id ([0-9a-f]{10})", session.sent[0])
    assert m is not None
    assert session.sent[0] == CLONE_TEMPLATE.format(id=m.group(1))
    assert len({_setup(seed)[1].sent[0] for seed in range(50)}) > 1


def test_check_passes_when_answer_matches_ground_truth():
    c, session = _setup()
    truth = c.solution
    mixed = ":".join(truth[i : i + 2] for i in range(0, 10, 2)).upper()
    session.sent.clear()
    assert c.check(session, mixed) is True
    assert c.check(session, truth) is True
    assert session.sent == []  # check never touches the device


def test_check_fails_on_wrong_answer():
    c, session = _setup()
    wrong = f"{(int(c.solution, 16) + 1) % (1 << 40):010x}"
    assert c.check(session, wrong) is False
    assert c.check(session, "") is False


def test_has_hints_and_solution():
    c, session = _setup()
    assert len(c.hints) >= 2
    assert any("lf search" in h for h in c.hints)
    assert c.solution in session.sent[0]
    assert re.fullmatch(r"[0-9a-f]{10}", c.solution)


def test_mode_is_read_and_card_is_t5577():
    c = _make()
    assert c.mode is Mode.READ
    assert c.required_card is CardKind.T5577
