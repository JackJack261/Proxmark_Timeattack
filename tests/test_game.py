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

LF_SEARCH_OUT = "[+] EM 410x ID 340073B7A4\n[+] Valid EM410x ID found!\n[+] Chipset... T55xx\n"
NO_LF_OUT = "[-] No known 125/134 kHz tags found!\n"
T55_DETECT_OUT = "[=]  Chip type......... T55x7\n[=]  Password set...... No\n"


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
        if cmd == cards.LF_SEARCH_CMD:
            state["search"] = search() if callable(search) else search
            return state["search"]
        if cmd == cards.T5577_INFO_CMD:
            # Detect only succeeds when a T5577 is actually on the antenna.
            return T55_DETECT_OUT if state.get("search") == LF_SEARCH_OUT else ""
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


class StubFeedback(StubCreate):
    def check(self, session, player_input):
        data = session.run("readback").strip()
        if data != "GOOD":
            self.feedback = f"The card reads as {data}."
        return data == "GOOD"


def test_wrong_attempt_shows_challenge_feedback():
    session = FakeSession(make_responses())
    h = Harness(session, ["", "write BAD", "write GOOD"])
    h.run([StubFeedback()])
    assert "The card reads as BAD." in h.out
    assert h.printed.count("The card reads as") == 1


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
    outputs = iter([NO_LF_OUT, LF_SEARCH_OUT])
    session = FakeSession(make_responses(search=lambda: next(outputs)))
    h = Harness(session, ["", "", "write GOOD"], clock_values=[5.0, 9.0])
    results = h.run([StubCreate()])
    assert len(results) == 1
    assert session.sent.count(cards.LF_SEARCH_CMD) == 2
    # clock() is first read only after both card checks (search+detect, twice) ran
    assert h.clock_calls[0] == 4
    assert "No T5577" in h.printed  # the wrong-card detail was shown


def test_read_challenge_setup_writes_and_checks_answer():
    session = FakeSession(make_responses())
    h = Harness(session, ["", "41", "42"], clock_values=[0.0, 8.0])
    results = h.run([StubRead()])
    assert len(results) == 1
    assert results[0].elapsed == pytest.approx(8.0)
    assert "write 42" in session.sent
    assert "TASK-READ" in h.printed
    # ground truth is written BEFORE the clock starts (first clock() call)
    assert session.sent.index("write 42") < h.clock_calls[0]
    assert "write 42" in session.sent[: h.clock_calls[0]]


def test_read_setup_timeout_retries_before_clock():
    raised = []

    def on_cmd(cmd):
        if cmd == "write 42" and not raised:
            raised.append(True)
            raise Pm3Timeout("slow")

    session = FakeSession(make_responses(on_cmd=on_cmd))
    h = Harness(session, ["", "", "42"], clock_values=[0.0, 8.0])
    results = h.run([StubRead()])
    assert len(results) == 1
    assert raised == [True]
    assert "timed out" in h.printed.lower()
    assert "write 42" in session.sent[: h.clock_calls[0]]
    assert session.sent.count("write 42") == 2


def test_read_setup_disconnect_aborts_before_clock():
    def on_cmd(cmd):
        if cmd == "write 42":
            raise Pm3Disconnected("gone")

    session = FakeSession(make_responses(on_cmd=on_cmd))
    h = Harness(session, [""])
    with pytest.raises(GameAborted):
        h.run([StubRead()])
    assert h.clock_calls == []


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


def test_create_shows_command_output():
    session = FakeSession(make_responses())
    h = Harness(session, ["", "write GOOD"])
    h.run([StubCreate()])
    assert "ok" in h.out  # the command's device output is shown to the player
    assert "Correct!" in h.printed


def test_help_command_in_create_runs_without_checking_card():
    seen = []
    session = FakeSession(make_responses(on_cmd=seen.append))
    h = Harness(session, ["", "lf hid -h", "write GOOD"])
    h.run([StubCreate()])
    # the card readback ran only after the real clone, not after '-h'
    assert seen.count("readback") == 1


def test_read_runs_command_and_shows_output_then_answer():
    session = FakeSession(make_responses())
    h = Harness(session, ["", "lf search", "42"])
    results = h.run([StubRead()])
    assert len(results) == 1
    assert results[0].skipped is False
    assert "340073B7A4" in h.printed  # the read command's output was shown
    assert "Correct!" in h.printed


def test_read_command_is_not_treated_as_answer():
    session = FakeSession(make_responses())
    h = Harness(session, ["", "lf search", "42"])
    results = h.run([StubRead()])
    # running 'lf search' must not count as submitting (and failing) an answer
    assert "Not quite. Try again." not in h.printed
    assert results[0].skipped is False
