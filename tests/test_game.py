import random

import pytest

from pm3trainer import cards
from pm3trainer.cards import CardKind
from pm3trainer.challenges.base import Challenge, Mode
from pm3trainer.challenges.hf_iclass_create import HfIclassCreate
from pm3trainer.challenges.hf_mf_create import HfMfCreate
from pm3trainer.challenges.hf_mf_read import HfMfRead
from pm3trainer.challenges.lf_em_create import LfEmCreate
from pm3trainer.challenges.lf_em_read import LfEmRead
from pm3trainer.challenges.lf_hid_create import LfHidCreate
from pm3trainer.game import GameAborted, build_challenges, run_game
from pm3trainer.session import Pm3Disconnected, Pm3Timeout
from pm3trainer.testing import FakeSession

LF_SEARCH_OUT = "[+] Valid T55xx tag found\n"
HF_SEARCH_OUT = "[+] ISO14443-a Information\n[+] Valid Mifare Classic tag found\n"
T55_DETECT_OUT = "[=] Chip Type      : T55x7\n[=] Password set   : No\n"


class StubCreate(Challenge):
    name = "Stub create"
    mode = Mode.CREATE
    required_card = CardKind.T5577
    present_prompt = "PRESENT-CREATE"
    task_prompt = "TASK-CREATE"
    hints = ["hint one", "hint two", "hint three"]
    solution = "write GOOD"

    def check(self, session, player_input):
        return session.run("readback").strip() == "GOOD"


class StubRead(Challenge):
    name = "Stub read"
    mode = Mode.READ
    required_card = CardKind.T5577
    present_prompt = "PRESENT-READ"
    task_prompt = "TASK-READ"
    hints = ["read hint"]
    solution = "42"

    def setup(self, session):
        session.run("write 42")

    def check(self, session, player_input):
        return player_input == "42"


def make_responses(search=LF_SEARCH_OUT, on_cmd=None):
    """Canned device: LF card present, 'write X' stores X, 'readback' returns it."""
    state = {"data": ""}

    def respond(cmd):
        if on_cmd is not None:
            on_cmd(cmd)
        if cmd == cards.SEARCH_CMD:
            return search() if callable(search) else search
        if cmd == cards.T5577_INFO_CMD:
            return T55_DETECT_OUT
        if cmd.startswith("write "):
            state["data"] = cmd[len("write "):]
            return "ok"
        if cmd == "readback":
            return state["data"]
        return ""

    return respond


class Harness:
    def __init__(self, session, lines, clock_values=(0.0, 10.0, 20.0, 30.0)):
        self.session = session
        self._lines = iter(lines)
        self._clock = iter(clock_values)
        self.out = []
        self.clock_calls = []  # len(session.sent) at each clock() call

    def input_fn(self, prompt=""):
        return next(self._lines)

    def output_fn(self, text=""):
        self.out.append(str(text))

    def clock(self):
        self.clock_calls.append(len(self.session.sent))
        return next(self._clock)

    def run(self, challenges):
        return run_game(
            self.session,
            challenges,
            input_fn=self.input_fn,
            output_fn=self.output_fn,
            clock=self.clock,
            scores=None,
        )

    @property
    def printed(self):
        return "\n".join(self.out)


def test_build_challenges_fixed_order():
    challenges = build_challenges(random.Random(1))
    assert [type(c) for c in challenges] == [
        LfHidCreate, LfEmCreate, HfMfCreate, HfIclassCreate, LfEmRead, HfMfRead,
    ]


def test_create_challenge_passes_on_correct_command():
    session = FakeSession(make_responses())
    h = Harness(session, ["", "write GOOD"], clock_values=[100.0, 112.5])
    results = h.run([StubCreate()])
    assert len(results) == 1
    assert results[0].name == "Stub create"
    assert results[0].elapsed == pytest.approx(12.5)
    assert results[0].hints_used == 0
    assert results[0].skipped is False
    assert "write GOOD" in session.sent
    assert "PRESENT-CREATE" in h.printed
    assert "TASK-CREATE" in h.printed


def test_create_challenge_retries_until_correct():
    session = FakeSession(make_responses())
    h = Harness(session, ["", "write BAD", "write GOOD"], clock_values=[0.0, 30.0])
    results = h.run([StubCreate()])
    assert len(results) == 1
    assert results[0].elapsed == pytest.approx(30.0)
    assert session.sent.count("readback") == 2
    assert [c for c in session.sent if c.startswith("write ")] == ["write BAD", "write GOOD"]


def test_guard_block_prevents_send_and_reloops():
    session = FakeSession(make_responses())
    blocked = "lf t55xx read -p 11223344"
    h = Harness(session, ["", blocked, "write GOOD"])
    results = h.run([StubCreate()])
    assert len(results) == 1
    assert blocked not in session.sent
    assert "Blocked" in h.printed
    assert "write GOOD" in session.sent


def test_wrong_card_reprompts_before_clock():
    outputs = iter([HF_SEARCH_OUT, LF_SEARCH_OUT])
    session = FakeSession(make_responses(search=lambda: next(outputs)))
    h = Harness(session, ["", "", "write GOOD"], clock_values=[5.0, 9.0])
    results = h.run([StubCreate()])
    assert len(results) == 1
    assert session.sent.count(cards.SEARCH_CMD) == 2
    # clock() is first read only after both card checks (auto, auto, detect) ran
    assert h.clock_calls[0] == 3
    assert "HF" in h.printed  # the wrong-card detail was shown


def test_read_challenge_setup_writes_and_checks_answer():
    session = FakeSession(make_responses())
    h = Harness(session, ["", "41", "42"], clock_values=[0.0, 8.0])
    results = h.run([StubRead()])
    assert len(results) == 1
    assert results[0].elapsed == pytest.approx(8.0)
    assert "write 42" in session.sent
    assert "TASK-READ" in h.printed


def test_timeout_is_recoverable():
    raised = []

    def on_cmd(cmd):
        if cmd == "write GOOD" and not raised:
            raised.append(True)
            raise Pm3Timeout("slow")

    session = FakeSession(make_responses(on_cmd=on_cmd))
    h = Harness(session, ["", "write GOOD", "write GOOD"])
    results = h.run([StubCreate()])
    assert len(results) == 1
    assert raised == [True]
    assert "timed out" in h.printed.lower()


def test_disconnect_aborts():
    def on_cmd(cmd):
        if cmd == "write GOOD":
            raise Pm3Disconnected("gone")

    session = FakeSession(make_responses(on_cmd=on_cmd))
    h = Harness(session, ["", "write GOOD"])
    with pytest.raises(GameAborted):
        h.run([StubCreate(), StubRead()])
    assert "disconnected" in h.printed.lower()
    assert "PRESENT-READ" not in h.printed


def test_hint_reveals_and_increments_without_sending():
    session = FakeSession(make_responses())
    h = Harness(session, ["", "hint", "write GOOD"])
    results = h.run([StubCreate()])
    assert "hint one" in h.printed
    assert results[0].hints_used == 1
    assert "hint" not in session.sent


def test_multiple_hints_advance_then_cap():
    session = FakeSession(make_responses())
    h = Harness(session, ["", "hint", " HINT ", "Hint", "hint", "write GOOD"])
    results = h.run([StubCreate()])
    assert results[0].hints_used == 4
    assert h.printed.count("hint one") == 1
    assert h.printed.count("hint two") == 1
    assert h.printed.count("hint three") == 2  # capped at the last hint
    assert not any("hint" in c.lower() for c in session.sent)


def test_pass_skips_and_reveals_solution():
    session = FakeSession(make_responses())
    h = Harness(session, ["", "pass"], clock_values=[0.0, 4.0])
    results = h.run([StubCreate()])
    assert len(results) == 1
    assert results[0].skipped is True
    assert results[0].elapsed == pytest.approx(4.0)
    assert "write GOOD" in h.printed  # the solution is revealed
    assert "readback" not in session.sent
    assert not any(c.startswith("write ") for c in session.sent)


def test_pass_on_read_challenge_skips_after_setup():
    session = FakeSession(make_responses())
    h = Harness(session, ["", "PASS"], clock_values=[0.0, 4.0])
    results = h.run([StubRead()])
    assert results[0].skipped is True
    assert "42" in h.printed
